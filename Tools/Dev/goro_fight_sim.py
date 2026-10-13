"""Simulación offline de la pelea con Gorō (barra falsa + fase armada) contra los bots de AutoPilot.

    python Tools/Dev/goro_fight_sim.py [--runs 400] [--bot bueno|promedio|experto] [--p1 V] [--p2 V] [--dmg 1.0]
                                       [--p1dmg K] [--p2dmg K] [--shed-heal V] [--sheds 0.75,0.5,0.25] [--no-retry-armored]
(los valores por omisión son los del juego: el bloque de balance de GoroBoss.cs, que este script lee de ahí, y los
tiempos de cada golpe salen de GoroAnims.fbx.json)
    python Tools/Dev/goro_fight_sim.py --grid [--runs 150]   (barre las perillas de GoroBoss contra el objetivo)

Modelo a nivel de golpe (no de cuadro), con los números del código:
  * Gorō (EnemyArchetypes.Goro / GoroPhase2): patrones con su peso, enfriamiento y fase; cada paso con su clip
    (GoroAnims.fbx.json) y su windup; pausa entre combos attackCooldown (x0.8 armado), guardia 0.6 s x U(0.7, 1.2).
  * Bot (AutoPilot): reacciona al toc (TellStyle.TickParryable 0.38 s / TickUnblockable 0.42 s antes del golpe) con
    N(rt, sd); no lo ve 'miss'; confunde parry y dash 'wrong'. Parry: ventana 0.24 s (perfecta 0.11) desde que
    aprieta; guardia imperfecta si llega hasta 0.15 s después (35 % del daño). Dash: i-frames 0.02-0.24.
  * Daño de Kaito: combo 10 / 11 / 18 (un toque cada 0.32 s), contraataque x1.5 tras un parry (y lo tumba: corta el
    combo), agotado x1.3 hasta 4 golpes o exhaustedTime. Postura: parry +1, perfecto +1.5, guardia imperfecta +0.34;
    con 1 al terminar el combo queda agotado; con 4 se quiebra. En neutral aguanta 5 golpes (poiseHits) y se cubre.
  * Fase 1: sin remate (GoroBoss.ApplyFinisherGate); fase 2: remate con <= 12 % y agotado (cinemática: muere).
  * Fase 2: la roca rebota los cortes mientras carga cada golpe (GoroBoss.InArmorWindow): el bot pierde los que mete
    en la anticipación. Avalancha: ~0.55 rocas le pegan al bueno (goro_avalanche_check.py), después queda abierto.
  * Kaito tiene 100 de vida y no se cura salvo: +8 al "matar" la barra falsa, +40 al terminar la cinemática de la
    armadura (GoroBoss.TransitionHeal) y 'shed-heal' cada vez que se le rompe un tramo de la armadura ('sheds': las
    fracciones de la segunda barra, GoroBoss.ShedAt y shedHeal). Si muere en la primera barra vuelve a ella; si muere
    armado, el reintento arranca armado (GoroBoss.retryArmored: sin la cinemática, re-presentación 1.2 s) salvo con
    --no-retry-armored. Cada muerte suma 3.6 s.
  * 'p1dmg' escala el daño de Gorō en la primera barra (GoroBoss.firstBarDamageScale) y 'p2dmg' el de Gorō armado
    (GoroBoss.armoredDamageScale: golpes, onda y avalancha); los dos respecto de EnemyArchetypes.Goro.
  * No modela al bot que camina: el bot de verdad se le pega a Gorō, y antes del arreglo de la avalancha (las rocas
    saltan por encima de Gorō, la armadura aguanta toda la llamada) ese lugar era inmune; ahora no.
Es un modelo: sirve para comparar vidas y ver órdenes de magnitud; el número final sale del bot en Unity.
"""
import argparse, json, math, os, random, re, sys

# los mismos niveles que Input/AutoPilot.cs (Skill): si se cambian allá, se cambian acá y en sim_bamboo_master.py y
# kokuyo_mizuchi_sim.py. El promedio de antes (miss 0.25, wrong 0.10, greedy 0.25) perdía contra todos los jefes un
# orden de magnitud más que el bueno: no se parecía a una persona que juega por primera vez, sino a una que no mira
BOTS = {
    "experto": dict(rt=0.25, sd=0.04, miss=0.0, wrong=0.0, greedy=0.0),
    "bueno": dict(rt=0.28, sd=0.06, miss=0.10, wrong=0.05, greedy=0.10),
    "promedio": dict(rt=0.32, sd=0.08, miss=0.15, wrong=0.07, greedy=0.15),
}

H, U = "heavy", "unblockable"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
SIDECAR = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Art", "Characters", "TeamAnims", "GoroAnims.fbx.json")
GOROBOSS = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Scripts", "Enemies", "Bosses", "GoroBoss.cs")
ARCHETYPES = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Scripts", "Enemies", "EnemyArchetypes.cs")


def load_balance():
    """El bloque de balance de GoroBoss.cs (public const float FirstBarHealth = ...f, ...): los valores por omisión del
    script son los del juego, sin copiarlos a mano."""
    src = open(GOROBOSS, encoding="utf-8").read()
    vals = {m.group(1): float(m.group(2)) for m in re.finditer(r"\b(\w+)\s*=\s*(-?[\d.]+)f\b", src)}
    sheds = re.search(r"ShedAt\s*=\s*\{([^}]*)\}", src).group(1)
    return dict(p1=vals["FirstBarHealth"], p2=vals["ArmoredHealth"], p1dmg=vals["FirstBarDamage"], p2dmg=vals["ArmoredDamage"],
                shed_heal=vals["ShedHealAmount"], heal=vals["TransitionHeal"], sheds=",".join(x.strip().rstrip("f") for x in sheds.split(",")))


# paso: (estado, tipo, daño, velocidad del AttackDef). Del sidecar (GoroAnims.fbx.json: apex, contacto, windup y suelta de
# cada clip) sale T, de que empieza el paso al golpe, y lo que dura el paso: T más lo que queda del clip a velocidad 1
# después del golpe (StepTimeline: la anticipación, la pausa y la suelta se estiran o se comprimen, el seguimiento no),
# a la velocidad del paso (c1f/c2f/c3f a 1.1/1.1/1.05x). La ventana de armadura antes del golpe (GoroBoss.InArmorWindow:
# del principio de la anticipación al contacto) es ~0.85 T en todos los clips
STEP_DEFS = {
    "c1": ("Combo1", H, 22, 1.0), "c2": ("Combo2", H, 24, 1.0), "c3": ("Combo3", H, 28, 1.0),
    "slam": ("Heavy", U, 38, 1.0), "slam2": ("Heavy", U, 42, 1.0), "spin": ("Spin", U, 20, 1.0),
    "c1f": ("Combo1", H, 22, 1.1), "c2f": ("Combo2", H, 24, 1.1), "c3f": ("Combo3", H, 28, 1.05),
    "c1b": ("Combo1B", H, 26, 1.0), "c2b": ("Combo2B", H, 24, 1.0), "c3b": ("Combo3B", H, 30, 1.0),
    "wave": ("SlamWave", U, 40, 1.0), "spin2": ("Spin", U, 24, 1.0),
}
ARMOR_OF_T = 0.85
# StepTimeline.FollowTau: después del golpe el clip sale a r0 veces su velocidad (la de la suelta) y frena hacia 1
FOLLOW_TAU = 0.06


def wave_extra(clip):
    """Lo que GoroBoss alarga el SlamWave: tl.sustain = specialParam / WaveSpeed REEMPLAZA la fase activa del paso (de
    activeStart a activeEnd del Hit, la arada entera: StepTimeline.NormAt), no se le suma. De GoroBoss.cs (WaveSpeed) y
    EnemyArchetypes.cs (wave.specialParam y el Hit); antes era 0.87 a mano y sobraban 0.26 s por onda."""
    ws = float(re.search(r"WaveSpeed\s*=\s*([\d.]+)f", open(GOROBOSS, encoding="utf-8").read()).group(1))
    arch = open(ARCHETYPES, encoding="utf-8").read()
    sp = float(re.search(r"wave\.specialParam\s*=\s*([\d.]+)f", arch).group(1))
    a0, a1 = (float(x) for x in re.search(r'Hit\("SlamWave",\s*[\d.]+,\s*([\d.]+)f,\s*([\d.]+)f', arch).groups())
    return sp / ws - (a1 - a0) * clip["frames"] / 30.0


def step_T(clip, speed=1.0):
    """(T, segundos que dura el paso) con el reloj del juego (StepTimeline.Build: T = la anticipación a 0.85x más la
    suelta a releaseRate, o el windup si es más largo; tools/Blender/anim/nindo_anim.StepTimeline). Después del golpe el
    clip arranca a r0 = 2 x releaseRate veces su velocidad y frena hacia 1 en FollowTau: el seguimiento dura
    (r0 - 1) FollowTau menos que el resto del clip a velocidad 1."""
    t = dict(clip["timing"], **clip["timing"].get("clock", {}))
    n = float(clip["frames"])
    L = n / 30.0 / speed
    apex, contact = t["apex"] / n, t["contact"] / n
    rr = t.get("release_rate", 1.6)
    T = max(apex * L / 0.85 + (contact - apex) * L / rr, t.get("windup", 0.55))
    r0 = max(1.0, 2.0 * rr)
    return T, T + max(0.0, (1.0 - contact) * L - (r0 - 1.0) * FOLLOW_TAU)


def load_steps():
    """{paso: (estado, tipo, daño, T, segundos que dura el paso, ventana de armadura)} y la llamada de la avalancha (s)."""
    clips = json.load(open(SIDECAR, encoding="utf-8"))["clips"]
    extra = {"SlamWave": wave_extra(clips["SlamWave"])}
    out = {}
    for k, (st, kind, dmg, sp) in STEP_DEFS.items():
        T, dur = step_T(clips[st], sp)
        out[k] = (st, kind, dmg, round(T, 3), round(dur + extra.get(st, 0.0), 3), round(ARMOR_OF_T * T, 3))
    # AvalancheSummon: de que empieza el paso a la llamada (el 'contacto' del clip)
    return out, step_T(clips["AvalancheSummon"])[0]


STEPS, AVAL_CALL = load_steps()
# (nombre, pasos, peso, enfriamiento, fase mínima, fase máxima, agotado al final)
PATTERNS = [
    ("Martillazo", ["c1"], 1.2, 0, 0, 1, False), ("Doble", ["c1", "c2"], 1.5, 0, 0, 1, False),
    ("Combo completo", ["c1", "c2", "c3"], 1.2, 0, 0, 1, False), ("Torbellino", ["spin"], 1.0, 9, 0, 1, True),
    ("Terremoto", ["c1", "slam2"], 1.3, 7, 1, 1, False),
    ("Amague", ["c1b"], 1.0, 0, 2, 9, False), ("Barrido", ["c1f", "c2b"], 1.1, 0, 2, 9, False),
    ("Derrumbe", ["c1f", "c2b", "c3b"], 1.3, 0, 2, 9, False), ("Cuatro", ["c1b", "c2f", "c3f", "c2b"], 0.9, 6, 2, 9, False),
    ("Onda", ["wave"], 1.0, 6, 2, 9, False), ("Martillo y onda", ["c1f", "wave"], 1.0, 8, 2, 9, False),
    ("Terremoto de piedra", ["c2b", "slam2"], 0.9, 8, 2, 9, False), ("Torbellino de piedra", ["spin2"], 0.8, 11, 2, 9, True),
    ("Avalancha", ["aval"], 1.2, 20, 2, 9, False),
    ("Golpe sísmico", ["slam"], 1.0, 6, 0, 9, False),
]
TICK_P, TICK_U = 0.38, 0.42
PARRY_W, PERFECT_W, IMPERFECT = 0.24, 0.11, 0.15
DASH_I0, DASH_I1 = 0.02, 0.24
KAITO_HITS = (10, 11, 18)
TAP = 0.32


class Sim:
    def __init__(self, bot, rng, p1, p2, dmg_mul, heal, p2dmg=1.0, shed_heal=0.0, p1dmg=1.0, sheds=(0.66, 0.33), retry_armored=True):
        self.b, self.rng, self.p1, self.p2, self.dmg_mul, self.heal = bot, rng, p1, p2, dmg_mul, heal
        self.p1dmg, self.p2dmg, self.shed_heal = p1dmg, p2dmg, shed_heal
        self.sheds, self.retry_armored = tuple(sheds), retry_armored
        self.combo_i = 0

    def kaito_hit(self, mul=1.0):
        d = KAITO_HITS[self.combo_i % 3] * mul
        self.combo_i += 1
        return d

    def defend(self, kind):
        """'parry', 'perfect', 'imperfect', 'dodge' o 'hit'."""
        b, r = self.b, self.rng
        if r.random() < b["miss"]:
            return "hit"
        dash = (kind == U) != (r.random() < b["wrong"])
        rt = min(0.55, max(0.15, r.gauss(b["rt"], b["sd"])))
        lead = TICK_U if kind == U else TICK_P
        gap = lead - rt - 1 / 60          # segundos entre que aprieta y el golpe
        if dash:
            return "dodge" if DASH_I0 <= gap <= DASH_I1 else "hit"
        if kind == U:
            return "hit"
        if 0 <= gap <= PARRY_W:
            return "perfect" if gap <= PERFECT_W else "parry"
        if PARRY_W < gap <= PARRY_W + IMPERFECT:
            return "imperfect"
        return "hit"

    def attempt(self, t_limit=1800, start_armored=False):
        """Un intento entero desde la fase 1 (o, con 'start_armored', desde la armada: el reintento después de morir
        armado). Devuelve (ganó, segundos, fase alcanzada)."""
        r = self.rng
        t, hp = 0.0, 100.0
        armored, health, maxh = start_armored, (self.p2 if start_armored else self.p1), (self.p2 if start_armored else self.p1)
        imb = 0.0
        last_used = {p[0]: -99.0 for p in PATTERNS}
        forced_aval = False
        shed = 0
        while t < t_limit:
            # la armadura se rompe en tramos de la segunda barra (GoroBoss.OnDamaged, ShedAt): cada tramo cura
            if armored:
                while shed < len(self.sheds) and health / maxh <= self.sheds[shed]:
                    shed += 1
                    hp = min(100.0, hp + self.shed_heal)
            phase = 2 if armored else (1 if health / maxh <= 0.5 else 0)
            # ---- neutral: guardia (el bot no pega) y la pausa entre combos (pega hasta que se cubre)
            guard = 0.6 * r.uniform(0.7, 1.2)
            cool = r.uniform(0.9, 1.8) * (0.8 if armored else 1.0)
            t += guard + cool
            n = min(5, int(max(0.0, cool - 0.2) / TAP))
            for _ in range(n):
                health -= self.kaito_hit()
            if health <= 0:
                if not armored:
                    armored, forced_aval = True, True
                    hp = min(100.0, hp + 8 + self.heal)
                    t += 12.5            # derrota falsa, silencio y armadura
                    health = maxh = self.p2
                    imb = 0.0
                    continue
                return True, t, 2
            # ---- patrón
            if forced_aval:
                pat = next(p for p in PATTERNS if p[0] == "Avalancha")
                forced_aval = False
            else:
                ok = [p for p in PATTERNS if p[4] <= phase <= p[5] and t - last_used[p[0]] >= p[3]]
                tot = sum(p[2] for p in ok)
                x = r.random() * tot
                pat = ok[-1]
                for p in ok:
                    x -= p[2]
                    if x <= 0:
                        pat = p
                        break
            last_used[pat[0]] = t
            staggered = False
            for si, sk in enumerate(pat[1]):
                if sk == "aval":
                    # dos martillazos, la llamada, tres olas: ~0.55 rocas al bueno (más al promedio) y la pausa abierta
                    t += AVAL_CALL + 4.6
                    expected = {"experto": 0.05, "bueno": 0.55, "promedio": 1.1}[self.bname]
                    k = sum(1 for _ in range(6) if r.random() < expected / 6)
                    hp -= 24 * k * self.dmg_mul * self.p2dmg
                    if hp <= 0:
                        return False, t, 2
                    # la pausa: 2.4 s abierto, 4 golpes x1.3
                    t += 1.4
                    for _ in range(4):
                        health -= self.kaito_hit(1.3)
                    break
                state, kind, dmg, T, dur, armor = STEPS[sk]
                # el bot pega en la anticipación antes de que aparezca el anillo (sin armadura entra el daño)
                tell = 0.85 if kind == H else 1.0
                free = max(0.0, T - tell)
                taps = int(free / TAP) + (1 if r.random() < self.b["greedy"] * 0.5 else 0)
                for _ in range(taps):
                    if armored and free <= armor + 0.05:
                        continue                 # rebota en la roca
                    health -= self.kaito_hit()
                res = self.defend(kind)
                t += T
                if res == "hit":
                    hp -= dmg * self.dmg_mul * (self.p2dmg if armored else self.p1dmg)
                    t += 0.65                    # aturdido
                elif res == "imperfect":
                    hp -= dmg * 0.35 * self.dmg_mul * (self.p2dmg if armored else self.p1dmg)
                    imb += 0.34
                elif res in ("parry", "perfect"):
                    imb += 1.5 if res == "perfect" else 1.0
                    # contraataque: lo tumba (corta el combo)
                    if r.random() < 0.7:
                        health -= self.kaito_hit(1.5)
                        t += 0.5
                        staggered = True
                if hp <= 0:
                    return False, t, 2 if armored else 1
                if imb >= 4:
                    break
                if staggered:
                    break
                t += max(0.0, dur - T) * (0.5 if res in ("parry", "perfect") else 1.0)
            if health <= 0 and not armored:
                armored, forced_aval = True, True
                hp = min(100.0, hp + 8 + self.heal)
                t += 12.5
                health = maxh = self.p2
                imb = 0.0
                continue
            # ---- fin del combo: agotado (postura, o el torbellino), o guardia
            if imb >= 1 and not staggered or imb >= 4 or pat[6]:
                broken = imb >= 4 or pat[6]
                for _ in range(4):
                    health -= self.kaito_hit(1.3)
                t += 4 * TAP + 0.6
                imb = 0.0
                if armored and broken and 0 < health / maxh <= 0.12:
                    return True, t + 3, 2        # remate
            if health <= 0:
                if not armored:
                    armored, forced_aval = True, True
                    hp = min(100.0, hp + 8 + self.heal)
                    t += 12.5
                    health = maxh = self.p2
                    imb = 0.0
                    continue
                return True, t, 2
        return False, t, 2

    def fight(self, bname, max_attempts=30):
        self.bname = bname
        total, deaths, phases = 0.0, 0, []
        armored_retry = False
        for a in range(max_attempts):
            won, secs, ph = self.attempt(start_armored=armored_retry)
            total += secs + (1.2 if a > 0 else 6.0)
            phases.append(ph)
            if won:
                return total, deaths, phases
            deaths += 1
            total += 3.6
            if self.retry_armored and ph == 2:
                armored_retry = True
        return total, deaths, phases


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    bal = load_balance()
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=400)
    ap.add_argument("--bot", default="bueno")
    ap.add_argument("--p1", type=float, default=bal["p1"], help="vida de la barra falsa (GoroBoss.FirstBarHealth)")
    ap.add_argument("--p2", type=float, default=bal["p2"], help="vida de la barra armada (GoroBoss.ArmoredHealth)")
    ap.add_argument("--dmg", type=float, default=1.0, help="multiplicador del daño de Gorō")
    ap.add_argument("--heal", type=float, default=bal["heal"])
    ap.add_argument("--p1dmg", type=float, default=bal["p1dmg"], help="multiplicador del daño de Gorō en la primera barra (GoroBoss.FirstBarDamage)")
    ap.add_argument("--p2dmg", type=float, default=bal["p2dmg"], help="multiplicador del daño de Gorō armado (GoroBoss.ArmoredDamage)")
    ap.add_argument("--shed-heal", type=float, default=bal["shed_heal"], help="vida que recupera Kaito con cada tramo de armadura roto (GoroBoss.ShedHealAmount)")
    ap.add_argument("--sheds", default=bal["sheds"], help="fracciones de la segunda barra en que se rompe un tramo (GoroBoss.ShedAt)")
    ap.add_argument("--no-retry-armored", action="store_true", help="el reintento vuelve siempre a la fase 1 (como antes)")
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--grid", action="store_true", help="barre vidas y perillas y lista las que más se acercan al objetivo")
    a = ap.parse_args()
    a.sheds = tuple(float(x) for x in a.sheds.split(",") if x.strip())
    a.retry = not a.no_retry_armored
    if a.grid:
        return grid(a)
    rng = random.Random(a.seed)
    times, deaths, first_try, p2_deaths = [], [], 0, 0
    one = []
    for _ in range(a.runs):
        s = Sim(BOTS[a.bot], rng, a.p1, a.p2, a.dmg, a.heal, a.p2dmg, a.shed_heal, a.p1dmg, a.sheds, a.retry)
        tt, d, ph = s.fight(a.bot)
        times.append(tt); deaths.append(d)
        first_try += d == 0
        p2_deaths += sum(1 for p in ph[:-1] if p == 2)
        s2 = Sim(BOTS[a.bot], rng, a.p1, a.p2, a.dmg, a.heal, a.p2dmg, a.shed_heal, a.p1dmg, a.sheds, a.retry)
        s2.bname = a.bot
        won, secs, _ = s2.attempt()
        if won:
            one.append(secs)
    times.sort()
    med = times[len(times) // 2]
    md = sum(deaths) / len(deaths)
    print(f"bot {a.bot}, barras {a.p1:.0f} + {a.p2:.0f}, daño x{a.dmg} (primera barra x{a.p1dmg}, armado x{a.p2dmg}), "
          f"cura de transición {a.heal:.0f}, "
          f"cura por tramo roto {a.shed_heal:.0f} en {a.sheds}, reintento armado {'sí' if a.retry else 'no'}")
    print(f"  pelea hasta ganar (con reintentos): mediana {med / 60:.1f} min, p10 {times[len(times) // 10] / 60:.1f}, p90 {times[len(times) * 9 // 10] / 60:.1f}")
    print(f"  muertes por pelea: media {md:.2f}, gana al primer intento {first_try / len(deaths) * 100:.0f} %, "
          f"muertes en la fase armada {p2_deaths / max(1, sum(deaths)) * 100:.0f} % de las muertes")
    if a.bot in REAL_PER_SIM:
        k, kd = REAL_PER_SIM[a.bot]
        print(f"  en Unity (calibrado con el bot de verdad): ~{med / 60 * k:.1f} min reales y ~{md * kd:.1f} muertes")
    if one:
        one.sort()
        print(f"  un intento ganado: mediana {one[len(one) // 2] / 60:.1f} min")


def stats(bot, p1, p2, p1dmg, p2dmg, shed, runs, seed, heal=40.0, sheds=(0.75, 0.5, 0.25), retry=True):
    """(mediana en min, muertes medias, % que gana al primer intento, % de las muertes que son en la primera barra)."""
    rng = random.Random(seed)
    times, deaths, first, p1_deaths = [], [], 0, 0
    for _ in range(runs):
        s = Sim(BOTS[bot], rng, p1, p2, 1.0, heal, p2dmg, shed, p1dmg, sheds, retry)
        tt, d, ph = s.fight(bot)
        times.append(tt)
        deaths.append(d)
        first += d == 0
        p1_deaths += sum(1 for p in ph[:-1] if p != 2)
    times.sort()
    return times[len(times) // 2] / 60.0, sum(deaths) / runs, first * 100.0 / runs, p1_deaths * 100.0 / max(1, sum(deaths))


# Calibrado con el bot de verdad en Unity (main 76be027, 1000 + 1600, daño x0.5 / x0.4, cura por tramo 25): el bueno
# ganó en 2:24 reales sin morir (acá 3.4 min) y el promedio en 4:04 con 2 muertes (acá 5.2 min y 1.46 muertes). El bot
# real es MÁS rápido que el modelo con Gorō (0.71x: se le pega y le mete los cortes de la vuelta a la guardia que el
# modelo no cuenta), al revés que con los otros jefes. (tiempo real / simulado, muertes reales / simuladas)
REAL_PER_SIM = {"bueno": (0.71, 1.0), "promedio": (0.78, 1.37)}
# objetivo del diseño: el bueno gana en ~4.5 min reales (4-5) casi sin morir; el promedio muere 1-2 veces
TARGET_MIN, TARGET_MAX = 4.0 / REAL_PER_SIM["bueno"][0], 5.0 / REAL_PER_SIM["bueno"][0]
TARGET_DEATHS = (1.0 / REAL_PER_SIM["promedio"][1], 2.0 / REAL_PER_SIM["promedio"][1])


def grid(a):
    """Objetivo del diseño: el bot bueno gana en ~4.5 min reales (TARGET_MIN-TARGET_MAX simulados) casi sin morir y el
    promedio muere 1-2 veces por pelea en Unity (TARGET_DEATHS simuladas). Barre las dos barras juntas (la proporción de
    la barra falsa no cambia), el daño de cada barra y la cura por tramo, y lista las 15 combinaciones que más se acercan
    (la distancia suma lo que falta o sobra de cada cosa, en minutos y muertes reales)."""
    bal = load_balance()
    kb, kp, kpd = REAL_PER_SIM["bueno"][0], REAL_PER_SIM["promedio"][0], REAL_PER_SIM["promedio"][1]
    rows = []
    for scale in (0.9, 1.0, 1.1):
        p1, p2 = round(bal["p1"] * scale / 10) * 10, round(bal["p2"] * scale / 10) * 10
        for p1d in (bal["p1dmg"] - 0.05, bal["p1dmg"], bal["p1dmg"] + 0.05):
            for p2d in (bal["p2dmg"] - 0.03, bal["p2dmg"], bal["p2dmg"] + 0.03):
                for shed in (bal["shed_heal"] - 10, bal["shed_heal"], bal["shed_heal"] + 10):
                    b = stats("bueno", p1, p2, p1d, p2d, shed, a.runs, a.seed, sheds=a.sheds, retry=a.retry)
                    if b[1] > 0.3:
                        continue
                    pr = stats("promedio", p1, p2, p1d, p2d, shed, a.runs, a.seed + 1, sheds=a.sheds, retry=a.retry)
                    miss = (max(0.0, TARGET_MIN - b[0]) + max(0.0, b[0] - TARGET_MAX)) * kb +                            (max(0.0, TARGET_DEATHS[0] - pr[1]) + max(0.0, pr[1] - TARGET_DEATHS[1])) * kpd
                    rows.append((miss, p1, p2, p1d, p2d, shed, b, pr))
    rows.sort(key=lambda r: r[0])
    print("vida1 vida2 daño1 daño2 cura | bueno: min (reales) muertes | promedio: min (reales) muertes (reales) 1er% barra1%")
    for miss, p1, p2, p1d, p2d, shed, b, pr in rows[:15]:
        print(f"{p1:5d} {p2:5d} {p1d:5.2f} {p2d:5.2f} {shed:4.0f} | {b[0]:4.1f} ({b[0] * kb:3.1f}) {b[1]:5.2f} | "
              f"{pr[0]:4.1f} ({pr[0] * kp:3.1f}) {pr[1]:5.2f} ({pr[1] * kpd:3.1f}) {pr[2]:4.0f} {pr[3]:4.0f}   (distancia {miss:.2f})")


if __name__ == "__main__":
    main()
