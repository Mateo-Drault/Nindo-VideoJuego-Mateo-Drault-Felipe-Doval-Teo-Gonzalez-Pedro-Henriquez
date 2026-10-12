"""Simulación offline de la pelea de Chikuō (BambooMasterBoss) contra el bot de AutoPilot.

Sin Unity: lee los tiempos de los clips del sidecar (BambooMaster.fbx.json) y repite las cuentas de
BambooMasterMoves.M (windup = anticipación natural + pausa del apex por fase), StepTimeline.Build (cuándo pega cada
golpe) y las reglas del juego que deciden la pelea:
  * el bot oye el "¡ya!" (hyōshigi) 0.38 s antes de un dorado y 0.42 s antes de un rojo y aprieta su tiempo de
    reacción después (AutoPilot.Skill: bueno N(0.28, 0.06), promedio N(0.32, 0.08); no lo ve, se confunde de botón);
  * parry: ventana de 0.24 s (perfecto los primeros 0.11), guardia imperfecta 0.15 s más (35 % del daño); dash:
    i-frames de 0.02 a 0.24 s; contra una zona (marca del salto, barrida, carril) un dash temprano igual lo saca;
  * un combo con un parry termina en agotado (4 s o 5 golpes); la postura llena (4) lo quiebra en el acto; la
    postura del bambú: el bot no le pega a una guardia, así que espera y Chikuō baja la guardia (3 golpes abierto);
  * entre combos Kaito le pega lo que deja la pausa (2 golpes antes de que se cubra);
  * pisos de vida por fase (66 %, 33 %), las escenas de cambio de fase (+15 de vida para Kaito) y los reintentos
    (llegar al bastón hace que el próximo intento arranque en la fase 2).
Dice la duración de la pelea (la que gana y la total con los intentos perdidos), las muertes y el reparto por fase,
y una tabla de lectura de cada golpe (cuánto antes se ve el anillo y cuán seguido el bot lo resuelve).

Uso: python Tools/Dev/sim_bamboo_master.py [--runs 400] [--seed 1]
"""
import argparse, json, math, os, random

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIDE = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Art", "Characters", "BambooMaster", "BambooMaster.fbx.json")

# --------------------------------------------------------------------------- números del juego (C#)
PARRY_HOLD = [0.30, 0.22, 0.16]          # BambooMasterMoves.ParryHold
DODGE_HOLD = [0.14, 0.10, 0.08]          # BambooMasterMoves.DodgeHold
CHAINED = 0.6                            # ChainedHold
GATES = [1.0, 0.66, 0.33, 0.0]           # BambooMasterBoss.Gates
STANCE_CHANCE = [0.35, 0.30, 0.25]
STANCE_TIME = (1.4, 2.0)
COOLDOWN = [(0.8, 1.4), (0.6, 1.1), (0.5, 0.9)]
HEALTH = 1400.0
MAX_IMB = 4
EXHAUSTED_TIME = 4.0
KNEEL_CAP, TAUNT_CAP = 5, 3
TAUNT_TIME = 1.8
GUARD_TIME = 0.7
PARRIED_RECOIL = 0.4                     # x1.5 el perfecto
TRANSITION = [3.67, 3.0]                 # PhaseCoat, PhaseStaff
TRANSITION_HEAL = 15.0
EXH_MUL = 1.3
# Kaito (PlayerConfig)
K_HP = 100.0
K_COMBO = [10.0, 11.0, 18.0]
K_TAP = 0.32                             # el bot ataca cada 0.32 s
K_FINAL = 0.57                           # el corte final hasta poder volver a empezar
RIPOSTE = 1.5
RAGE_HIT, RAGE_PARRY, RAGE_PERFECT, RAGE_LOSS, RAGE_TIME, RAGE_MUL = 4, 14, 20, 40, 9.0, 1.45
PARRY_WIN, PERFECT_WIN, IMPERFECT, IMPERFECT_DMG = 0.24, 0.11, 0.15, 0.35
IFRAME = (0.02, 0.24)
TICK = {"gold": 0.38, "red": 0.42}
DEATH_AND_RETRY = 3.6 + 2.6 + 4.0        # muerte -> reaparición, caminar a la arena, re-presentación
SKILLS = {
    "experto": dict(rt=(0.25, 0.04), miss=0.0, wrong=0.0),
    "bueno": dict(rt=(0.28, 0.06), miss=0.10, wrong=0.05),
    "promedio": dict(rt=(0.32, 0.08), miss=0.25, wrong=0.10),
}


def load():
    return json.load(open(SIDE, encoding="utf-8"))["clips"]


CLIPS = load()


def suffix(phase):
    return "" if phase == 0 else "_P2" if phase == 1 else "_P3"


class Step:
    def __init__(self, base, phase, dmg, chained=False, special="strike"):
        c = CLIPS.get(base + suffix(phase)) or CLIPS[base]
        nm, t = c["normalized"], c["timing"]
        self.name = base + suffix(phase)
        self.red = t.get("kind") == "dodge"
        self.dmg = dmg
        self.special = special
        S, ap, co = c["seconds"], nm["apex"], nm["contact"]
        rr = c.get("release_rate", 1.6)
        hold = (DODGE_HOLD if self.red else PARRY_HOLD)[phase] * (CHAINED if chained else 1.0)
        natural = ap * S / 0.85 + (co - ap) * S / rr
        # MinWindup: el windup explícito (con la compensación del 0.9 de las fases 2 y 3) y los mínimos del tipo
        self.T = max(natural + hold, 0.70 if self.red else 0.38)
        self.after = (1 - co) * S          # resto del clip después del golpe (velocidad 1)
        self.ring = min(self.T, 1.0 if self.red else 0.85)
        self.area = special in ("leap", "sweep", "dash")


def patterns(phase):
    P = []
    def add(name, w, cd, steps, ranged=False):
        P.append(dict(name=name, w=w, cd=cd, steps=steps, ranged=ranged, last=-99.0))
    if phase == 0:
        add("Palma", 1.3, 0, [Step("Palm", 0, 14)])
        add("Palma y Sable", 1.6, 0, [Step("Palm", 0, 14), Step("ChopPalm", 0, 16, True)])
        add("Pico de Grulla", 1.0, 2, [Step("CraneKick", 0, 16)])
        add("Sable y Grulla", 1.2, 4, [Step("ChopPalm", 0, 16), Step("CraneKick", 0, 16, True)])
        add("Tres de una Mano", 0.8, 8, [Step("Palm", 0, 14), Step("ChopPalm", 0, 16, True), Step("CraneKick", 0, 16, True)])
        add("Grulla Voladora", 1.0, 6, [Step("LeapKick", 0, 22, special="leap")], True)
    elif phase == 1:
        add("Palmas Gemelas", 1.2, 0, [Step("TwinPalm", 1, 20)])
        add("Palma y Viento", 1.4, 3, [Step("Palm", 1, 16), Step("SpinKick", 1, 20, True)])
        add("Sable y Gemelas", 1.2, 3, [Step("ChopPalm", 1, 18), Step("TwinPalm", 1, 20, True)])
        add("Grulla y Barrida", 1.0, 6, [Step("CraneKick", 1, 18), Step("Sweep", 1, 20, True, "sweep")])
        add("Barrida", 0.6, 6, [Step("Sweep", 1, 20, special="sweep")])
        add("Cuatro Vientos", 0.7, 9, [Step("Palm", 1, 16), Step("ChopPalm", 1, 18, True), Step("TwinPalm", 1, 20, True), Step("SpinKick", 1, 20, True)])
        add("Onda de Qi", 0.9, 9, [Step("QiWave", 1, 22, special="qi")], True)
        add("Paso del Viento", 1.1, 6, [Step("DashStrike", 1, 24, special="dash")], True)
        add("Grulla Voladora", 0.8, 7, [Step("LeapKick", 1, 24, special="leap")], True)
    else:
        add("Estocada", 1.2, 0, [Step("Palm", 2, 18)])
        add("Estocada y Bambú", 1.4, 0, [Step("Palm", 2, 18), Step("ChopPalm", 2, 20, True)])
        add("El Bambú Vuelve", 1.1, 6, [Step("Palm", 2, 18), Step("ChopPalm", 2, 20, True), Step("Sweep", 2, 24, True, "sweep")])
        add("Grulla y Estocada", 1.0, 3, [Step("CraneKick", 2, 20), Step("Palm", 2, 18, True)])
        add("Barrida del Bastón", 0.6, 6, [Step("Sweep", 2, 24, special="sweep")])
        add("La Última Lección", 0.6, 12, [Step("Palm", 2, 18), Step("ChopPalm", 2, 20, True), Step("Palm", 2, 18, True), Step("QiWave", 2, 24, True, "qi")])
        add("Raíz del Bambú", 0.8, 8, [Step("QiWave", 2, 24, special="qi")], True)
        add("Viento y Bambú", 1.0, 6, [Step("DashStrike", 2, 26, special="dash"), Step("ChopPalm", 2, 20, True)], True)
        add("Grulla y Estocada (salto)", 0.8, 7, [Step("LeapKick", 2, 26, special="leap"), Step("Palm", 2, 18, True)], True)
    return P


def counter_step(phase):
    return Step("CounterStrike", phase, 14 + 2 * phase)


# --------------------------------------------------------------------------- defensa del bot
def defend(step, skill, rng):
    """'parry', 'perfect', 'imperfect', 'dodge' o 'hit'."""
    if rng.random() < skill["miss"]:
        return "hit"
    m, sd = skill["rt"]
    rt = min(0.55, max(0.15, rng.gauss(m, sd)))
    kind = "red" if step.red else "gold"
    press = -TICK[kind] + rt + 1 / 60.0      # respecto del golpe (0)
    dash = step.red != (rng.random() < skill["wrong"])
    if dash:
        if IFRAME[0] <= -press <= IFRAME[1]:
            return "dodge"
        # contra una zona, el dash temprano igual lo saca (6.5 m); la onda de qi lo alcanza igual
        if step.red and step.area and -press > IFRAME[1] and rng.random() < 0.7:
            return "dodge"
        return "hit"
    if step.red:
        return "hit"                         # parry a un rojo
    if 0 <= -press <= PARRY_WIN:
        return "perfect" if -press <= PERFECT_WIN else "parry"
    if PARRY_WIN < -press <= PARRY_WIN + IMPERFECT:
        return "imperfect"
    return "hit"


# --------------------------------------------------------------------------- una pelea
class Fight:
    def __init__(self, skill, rng):
        self.s, self.rng = skill, rng
        self.t = 0.0

    def run(self):
        rng = self.rng
        total, attempts, retry_phase = 0.0, 0, 0
        phase_time = [0.0, 0.0, 0.0]
        while attempts < 12:
            attempts += 1
            won, dt, reached, per_phase = self.attempt(retry_phase)
            total += dt
            for i in range(3):
                phase_time[i] += per_phase[i]
            if won:
                return dict(win_time=dt, total=total, deaths=attempts - 1, phase_time=phase_time)
            total += DEATH_AND_RETRY
            if reached >= 2:
                retry_phase = 1
        return dict(win_time=None, total=total, deaths=attempts, phase_time=phase_time)

    def attempt(self, start_phase):
        rng = self.rng
        t = 0.0
        hp = HEALTH * GATES[start_phase]
        k_hp = K_HP
        rage, rage_until = 0.0, -1.0
        phase = start_phase
        pats = patterns(phase)
        per_phase = [0.0, 0.0, 0.0]
        stance_last = False
        first_stance = start_phase == 0
        near = True
        imb = 0.0

        def k_damage(base, mult=1.0):
            nonlocal rage, rage_until
            r = RAGE_MUL if t < rage_until else 1.0
            return base * mult * r

        def add_rage(x):
            nonlocal rage, rage_until
            if t < rage_until:
                rage_until += 0.6 if x == RAGE_HIT else 0
                return
            rage = min(100.0, rage + x)
            if rage >= 100.0:
                rage, rage_until = 0.0, t + RAGE_TIME

        def floor():
            return HEALTH * GATES[phase + 1]

        def hit_boss(dmg):
            nonlocal hp
            hp = max(floor(), hp - dmg) if phase < 2 else hp - dmg

        def kaito_window(hits, mult, riposte):
            """Kaito le pega 'hits' golpes del combo (reiniciándolo); devuelve el tiempo que tardó."""
            nonlocal t
            dur = 0.0
            for i in range(hits):
                base = K_COMBO[i % 3]
                m = mult * (RIPOSTE if (riposte and i == 0) else 1.0)
                hit_boss(k_damage(base, m))
                add_rage(RAGE_HIT)
                dur += K_FINAL if i % 3 == 2 else K_TAP
                if hp <= floor() + 0.01 and phase < 2 or hp <= 0:
                    break
            return dur

        while True:
            ph_start = t
            if hp <= 0:
                per_phase[phase] += 0
                return True, t, phase, per_phase
            if k_hp <= 0:
                return False, t, phase, per_phase
            # cambio de fase
            if phase < 2 and hp <= floor() + 0.01:
                t += TRANSITION[phase]
                per_phase[phase] += TRANSITION[phase]
                phase += 1
                pats = patterns(phase)
                k_hp = min(K_HP, k_hp + TRANSITION_HEAL)
                imb = 0.0
                continue
            # elige patrón (lejos: los de distancia pesan; cerca: los de cerca)
            avail = [p for p in pats if t - p["last"] >= p["cd"] and (p["ranged"] == (not near) or not near and not p["ranged"] and rng.random() < 0.3)]
            if not avail:
                avail = [p for p in pats if t - p["last"] >= p["cd"] and not p["ranged"]] or pats
            tot = sum(p["w"] for p in avail)
            r = rng.random() * tot
            pat = avail[-1]
            for p in avail:
                r -= p["w"]
                if r <= 0:
                    pat = p
                    break
            pat["last"] = t
            if not near:
                near = True
            parried_any = False
            broken = False
            for st in pat["steps"]:
                out = defend(st, self.s, rng)
                t += st.T
                if out in ("parry", "perfect"):
                    parried_any = True
                    imb += 1.5 if out == "perfect" else 1.0
                    add_rage(RAGE_PERFECT if out == "perfect" else RAGE_PARRY)
                    t += PARRIED_RECOIL * (1.5 if out == "perfect" else 1.0)
                    if imb >= MAX_IMB:
                        broken = True
                        break
                else:
                    t += st.after
                    if out == "imperfect":
                        k_hp -= st.dmg * IMPERFECT_DMG
                        imb += 0.34
                        rage = max(0.0, rage - RAGE_LOSS * IMPERFECT_DMG)
                    elif out == "hit":
                        k_hp -= st.dmg
                        rage = max(0.0, rage - RAGE_LOSS)
                        if st.red or st.dmg >= 20:
                            near = rng.random() > 0.6
                    elif out == "dodge":
                        near = rng.random() > 0.5
                if k_hp <= 0:
                    per_phase[phase] += t - ph_start
                    return False, t, phase, per_phase
            if broken or imb >= 1.0 - 1e-3:
                # agotado: de rodillas hasta 5 golpes o 4 s (el bot llega si quedó lejos)
                walk = 0.0 if near else 0.9
                dur = kaito_window(KNEEL_CAP, EXH_MUL, True)
                t += max(walk + dur, min(EXHAUSTED_TIME, walk + dur + 0.3))
                imb = 0.0
                near = True
            else:
                want = first_stance or (not stance_last and rng.random() < STANCE_CHANCE[phase])
                first_stance = False
                stance_last = want
                if want:
                    # el bot no le pega a una guardia: espera, Chikuō baja la guardia y lo llama
                    t += rng.uniform(*STANCE_TIME)
                    dur = kaito_window(TAUNT_CAP, EXH_MUL, False)
                    t += max(dur, TAUNT_TIME * 0.7)
                else:
                    t += GUARD_TIME * rng.uniform(0.7, 1.2)
            # la pausa entre combos: si está cerca, dos golpes antes de que se cubra
            gap = rng.uniform(*COOLDOWN[phase])
            if near and gap > 0.5:
                kaito_window(2, 1.0, False)
            t += gap + (0.0 if near else 0.6)
            per_phase[phase] += t - ph_start


def reading_table():
    print("golpe              fase  windup  anillo  'ya!'  bot bueno  bot promedio")
    rng = random.Random(3)
    seen = set()
    for ph in range(3):
        for p in patterns(ph) + [dict(steps=[counter_step(ph)])]:
            for st in p["steps"]:
                if st.name in seen:
                    continue
                seen.add(st.name)
                res = {}
                for sk in ("bueno", "promedio"):
                    n, ok = 4000, 0
                    for _ in range(n):
                        o = defend(st, SKILLS[sk], rng)
                        ok += o in ("parry", "perfect", "dodge")
                    res[sk] = ok / n
                print("%-18s %d     %.2f s  %.2f s  %.2f s   %3.0f %%      %3.0f %%" % (
                    st.name, ph + 1, st.T, st.ring, TICK["red" if st.red else "gold"], 100 * res["bueno"], 100 * res["promedio"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=400)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    reading_table()
    for sk in ("experto", "bueno", "promedio"):
        rng = random.Random(a.seed)
        rs = [Fight(SKILLS[sk], rng).run() for _ in range(a.runs)]
        wins = [r for r in rs if r["win_time"] is not None]
        wt = sorted(r["win_time"] for r in wins)
        tt = sorted(r["total"] for r in rs)
        deaths = [r["deaths"] for r in rs]
        pt = [sum(r["phase_time"][i] for r in rs) / len(rs) for i in range(3)]
        med = lambda xs: xs[len(xs) // 2] if xs else float("nan")
        print("\n%s: gana %d/%d | intento ganador %.0f s (p10 %.0f, p90 %.0f) | total con intentos %.0f s | muertes media %.2f (%.0f %% sin morir)" % (
            sk, len(wins), len(rs), med(wt), wt[len(wt) // 10] if wt else 0, wt[9 * len(wt) // 10] if wt else 0, med(tt),
            sum(deaths) / len(deaths), 100 * sum(1 for d in deaths if d == 0) / len(deaths)))
        print("   tiempo medio por fase (todos los intentos): %.0f / %.0f / %.0f s" % tuple(pt))


if __name__ == "__main__":
    main()
