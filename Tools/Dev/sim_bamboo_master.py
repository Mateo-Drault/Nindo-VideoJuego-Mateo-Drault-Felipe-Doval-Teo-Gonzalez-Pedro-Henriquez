"""Simulación offline de la pelea de Chikuō (BambooMasterBoss) contra el bot de AutoPilot, cuadro a cuadro.

Sin Unity. Porta las reglas que deciden la pelea, con los números del código (si se cambian allá, se cambian acá):
  * Enemy.cs: estados (Chase, Strafe, Attack, Recoil, Guard, Counter, Exhausted, Stagger), contraataque de Kaito
    en el Recoil, postura (parry 1, perfecto 1.5, guardia imperfecta 0.34), agotado (x exhaustedDamageMul, tope
    de golpes), StepTimeline.Build / MinWindup / NormAt (cuándo pega cada paso) y el "¡ya!" (TickLead).
  * BambooMasterBoss / Moves: los tiempos de cada clip (sidecar BambooMaster.fbx.json), pausas del apex por fase,
    pisos de vida (66 % / 33 %) y escenas de cambio de fase, lo que pasa fuera de sus huecos (Bounce: parado, el
    primer corte lo aparta con la palma sin clang (Swat: Kaito se frena 0.05 s) y contesta con su combo answer s después
    saliendo de la guardia, nunca antes del descanso de después de un contraataque de Kaito, que pasa cubierto; el 2.º
    dentro de BounceWindow también lo aparta y lo hace contestar swat_answer s después aunque esté descansando; el 3.º se
    contragolpea; cargando un dorado aparta el primero; lo demás rebota con clang), postura del
    bambú (desvío + contragolpe, cuya parada perfecta lo arrodilla; esperarla lo deja abierto), de rodillas solo con la
    postura llena, la onda de qi (frente a QiSpeed m/s), la grulla voladora (cae sobre Kaito; de cerca primero el salto
    atrás hasta LeapFrom, x20 desde los 14 s hasta que sale), la barrida (disco), el paso del viento (desde LeapFrom o con
    el salto atrás antes, x4 hasta que sale en la fase: de frente con el vuelo escalado entre 0.5 y 1.4 para frenar sobre
    donde va a estar Kaito, o, si para eso tendría que volar menos de la mitad, la variante que le pasa al costado a
    pass_beside con el cruce en el contacto; el vuelo corto en menos tiempo y con más pausa agachado: PlanDash, PlanPass y
    CompressFlight; el carril sigue a Kaito hasta que despega y ahí se vuelve a planear el vuelo: FixLane; sin la arena:
    es 1D, con Kaito a pass_beside del carril o, más cerca, a 0.87 d), las variantes de paso de los golpes que avanzan (en la suelta, la más larga que
    entra donde va a estar Kaito o la de paso más largo si esa no llega; lo que no entra corre a Kaito con el cuerpo:
    PickReach y Travel), el contraataque de Kaito (2 cortes después de un parry, 3 después de uno perfecto), el hueco del
    final del último golpe de un combo, las habilidades (rebotan fuera de los huecos y suman postura) y el reintento desde
    la fase más alta a la que llegó Kaito.
  * PlayerController: combo de Kaito (clips de 0.43 / 0.37 / 0.70 s, golpe en f4 / f3 / f7), parry 0.24 s
    (perfecto 0.11), guardia imperfecta 0.15 s, encadenar parries 0.18 s, contraataque x1.5 por 0.7 s, dash
    6.5 m con i-frames 0.02-0.24 y 15 de Espíritu (sin Espíritu: paso sin i-frames), aturdido 0.65 s, 0.7 s
    invulnerable después de un golpe, Furia (x1.45 por 9 s), Espíritu y Furia que suman golpes y parries.
  * AutoPilot (bot): aprieta parry/dash un tiempo de reacción después del "¡ya!" (bueno N(0.28, 0.06), promedio
    N(0.32, 0.08); a veces no lo ve o se confunde), se acerca hasta 2.2 m, ataca cada 0.32 s a menos de 2.6 m si
    no hay un anillo encima (salvo de apurado) y nunca contra una guardia.
Geometría en 1D (distancia entre los dos): el bot siempre va hacia el jefe y su dash sale hacia él (sin dirección
de stick sale hacia adelante), como en el juego.

Dice cuánto dura la pelea (el intento ganador y el total con las muertes), en qué fase se muere, de dónde sale el
daño a Chikuō y una tabla de lectura de cada golpe (windup, anillo, "¡ya!" y qué tan seguido lo resuelve el bot).

Con --abilities Kaito usa el Corte del Viento como un jugador (en los huecos, con Espíritu de sobra); el bot de AutoPilot
no las usa. "avance perdido" cuenta lo que Travel no pudo mover del avance autorado (el pie apoyado patina eso).
"rebotes" son los cortes que chocan con clang (Blocked) y "desvios_suaves" los que aparta sin clang (Swat); "cortes
rechazados" cuenta los dos y los contragolpes, por minuto y según lo que hacía el maestro; "embestida" dice a qué
distancia salió, cuánto voló y si frenó de frente o le pasó al costado. Con --human P el bot le pega igual a la guardia
en esa parte de sus decisiones de atacar (como un jugador apurado: el de AutoPilot nunca); con --masher P vuelve a tirar
en cada cuadro (un jugador que no para nunca: era el --human de la ronda anterior).

Uso: python Tools/Dev/sim_bamboo_master.py [--runs 200] [--seed 1] [--skill bueno|promedio|experto|all] [--table] [--fair]
     [--abilities] [--human 0.5] [--masher 0.5]
"""
import argparse, json, math, os, random

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIDE = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Art", "Characters", "BambooMaster", "BambooMaster.fbx.json")
CLIPS = json.load(open(SIDE, encoding="utf-8"))["clips"]
DT = 1.0 / 60.0

# --------------------------------------------------------------------------- Chikuō (BambooMasterBoss / Moves)
P = dict(
    health=2200.0,
    gates=[1.0, 0.66, 0.33, 0.0],
    parry_hold=[0.30, 0.22, 0.16], dodge_hold=[0.14, 0.10, 0.08], chained=0.6, phase_mul=0.9,
    cooldown=[(1.8, 2.6), (1.4, 2.2), (1.1, 1.8)],      # BambooMasterMoves.Cooldown
    stance_chance=[0.45, 0.40, 0.35], stance_time=(1.8, 2.6),
    kneel_cap=3, taunt_cap=2, exh_mul=1.15, exh_time=4.0, taunt_time=2.0,
    max_imb=8.0, guard_time=0.7, stagger=0.35, bounce_window=0.55,
    recoil=0.4,                          # Parried.Seconds * 0.4 (x1.5 el perfecto)
    run=4.0, walk=1.6, pref=3.6, radius=0.5,
    qi_speed=[9.0, 9.0, 10.0], qi_radius=[9.0, 9.0, 10.5], leap_min=2.6, leap_max=7.4, leap_minr=2.5,
    dash_from=4.8, dash_minr=4.8, hop_min=0.25, dash_k=(0.5, 1.4), dash_flight=0.1, leap_from=4.8, leap_near=0.5,
    # la que pasa al costado (DashStrike_Pass): a PassBeside del carril, el cruce PassOver pasado de Kaito en el contacto,
    # el vuelo escalado entre pass_k (y en menos tiempo); en el contacto le pega si está a pass_reach por el carril
    pass_beside=1.2, pass_over=0.1, pass_k=(0.2, 1.4), pass_reach=1.1,
    # BambooMasterBoss.FixLane: el vuelo que se vuelve a planear al despegar (contra la compresión de la suelta) y lo más
    # rápido que corre el clip en el corte del cruce (sustain)
    replan=(0.6, 1.8), cut_rate=2.0, pass_gap=1.15,
    # el primer corte fuera de un hueco (en neutral o en la guardia): lo desvía con el manotazo (HitResult.Deflected:
    # Kaito se frena 0.05 s y resbala deflect_push m) y contesta con su combo answer[fase] s después, nunca antes del
    # descanso que se toma después de un contraataque de Kaito (BambooMasterBoss.Swat)
    deflect_freeze=0.05, answer=0.6, rest_guard_min=0.3, swat_answer=0.12,
    riposte_grace=0.3, riposte_cuts=(2, 3), hole_delay=0.1, ability_posture=2.0,
    transition=[3.67, 3.0], heal=30.0, spirit_gift=30.0,
    counter_clip=0.5333, guardhit_extra=0.5,
    dmg_mul=[1.0, 1.0, 1.0],
    retry_max=2,                         # fase más alta desde la que puede arrancar un reintento (0..2; OnPlayerDied)             # para probar: multiplica el daño de los golpes de cada fase
)
K_R = 0.35                               # radio de Kaito (CharacterController)
CONTACT = P["radius"] + K_R + 0.25       # Travel() frena acá contra Kaito
REACH_OVERRUN = 0.03                     # BambooMasterBoss.ReachOverrun

# --------------------------------------------------------------------------- Kaito (PlayerConfig)
K = dict(hp=100.0, spirit0=40.0, run=6.2,
         combo=[dict(dmg=10, len=0.4333, hit=0.308, win=0.538, cut_end=0.538, range=2.3, kb=0.35, stop=0.06, kind="light"),
                dict(dmg=11, len=0.3667, hit=0.273, win=0.545, cut_end=0.545, range=2.3, kb=0.4, stop=0.06, kind="light"),
                dict(dmg=18, len=0.6667 / 0.95, hit=0.35, win=0.95, cut_end=0.5, range=2.6, kb=1.6, stop=0.11, kind="heavy")],
         restart=0.85, grace=0.25, parry_win=0.24, perfect=0.11, parry_recover=0.28, imperfect=0.15, imperfect_dmg=0.35,
         chain_parry=0.18, riposte_win=0.7, riposte_mul=1.5, riposte_start=0.154,
         dash_cost=15.0, dash_len=0.26, dash_recover=0.08, iframe=(0.02, 0.24), dash_dist=6.5, tired_cd=0.8,
         hurt_heavy=0.65, invuln=0.7, blocked=0.5,
         rage_hit=4, rage_parry=14, rage_perfect=20, rage_loss=40, rage_time=9.0, rage_mul=1.45, rage_ext=0.6,
         sp_hit=3, sp_parry=12, sp_perfect=18, slash_cost=35.0, slash_dmg=32.0)
TICK = {False: 0.38, True: 0.42}         # TellStyle.TickParryable / TickUnblockable
MAXLEAD = {False: 0.85, True: 1.0}
SKILLS = {
    "experto": dict(rt=(0.25, 0.04), miss=0.0, wrong=0.0, greedy=0.0),
    "bueno": dict(rt=(0.28, 0.06), miss=0.10, wrong=0.05, greedy=0.1),
    # Input/AutoPilot.cs Skill.Average, recalibrado (antes miss 0.25, wrong 0.10, greedy 0.25): los mismos números que
    # goro_fight_sim.py y boss_sims/kaito.py
    "promedio": dict(rt=(0.32, 0.08), miss=0.15, wrong=0.07, greedy=0.15),
}
DEATH_AND_RETRY = 3.6 + 3.0              # muerte → reaparición y caminar del santuario a la arena
REINTRO = 2.0


def suffix(ph):
    return "" if ph == 0 else "_P2" if ph == 1 else "_P3"


def clip(base, ph):
    return CLIPS.get(base + suffix(ph)) or CLIPS[base]


# --------------------------------------------------------------------------- golpes (BambooMasterMoves.M)
class Step:
    def __init__(self, base, ph, dmg, chained=False, special="strike", counter=False, name=None):
        c = clip(base, ph)
        nm, t = c["normalized"], c["timing"]
        self.name = name or (base + suffix(ph))
        self.state = base + suffix(ph)
        self.red = t.get("kind") == "dodge"
        self.dmg, self.special, self.counter = dmg * P["dmg_mul"][ph], special, counter
        self.S = c["seconds"]
        self.apex, self.contact = nm["apex"], nm["contact"]
        self.active_end = nm["active"][1]
        self.rr = c.get("release_rate", 1.6)
        self.reach = c.get("reach_m", 1.3)
        self.ring = t.get("ring_m", 0.0)
        self.marker = t.get("marker_m", 0.0)
        tr = c.get("travel_m")
        self.travel = tr
        self.frames = c["frames"]
        air = nm.get("air")
        self.air = air if air and air[1] > air[0] else None
        # BambooMasterBoss.StretchSpan: la embestida escala del pie que empuja (DashStart) al que se clava (el contacto,
        # o el apoyo DashEnd en la que pasa al costado)
        ds = [e["t"] for e in c.get("events", []) if e["fn"] == "DashStart"]
        de = [e["t"] for e in c.get("events", []) if e["fn"] == "DashEnd"]
        if ds:
            self.air = [ds[0], max([nm["contact"]] + de)]
        # la variante que pasa al costado (mismos tiempos: se cambia en la suelta)
        pv = t.get("pass_variant")
        self.pass_step = Step(pv[:-3] if pv.endswith("_P3") else pv, ph, dmg / P["dmg_mul"][ph], chained, special) \
            if pv and special == "dash" else None
        self.base = base
        # las variantes de paso corto (PickReach): (avance total, alcance, travel_m)
        self.variants = []
        for v in t.get("reach_variants") or []:
            cv = CLIPS[v]
            self.variants.append((cv["travel_m"][-1], cv.get("reach_m", self.reach), cv["travel_m"]))
        hold = (P["dodge_hold"] if self.red else P["parry_hold"])[ph] * (P["chained"] if chained else 1.0)
        natural = self.apex * self.S / 0.85 + (self.contact - self.apex) * self.S / self.rr
        self.windup = natural + hold
        if ph >= 1:
            self.windup /= P["phase_mul"]
        self.ph = ph
        self.range = self.reach + self.travel_at(self.contact)
        if special == "qi":
            self.ring = P["qi_radius"][ph]
        if special == "hop":
            self.windup = 0.0
        self.bias = 0.16 if self.red else 0.10

    def travel_at(self, n, tr=None):
        tr = tr or self.travel
        if not tr:
            return 0.0
        x = min(max(n, 0.0), 1.0) * self.frames
        i = min(int(x), len(tr) - 1)
        j = min(i + 1, len(tr) - 1)
        return tr[i] + (tr[j] - tr[i]) * (x - i)

    def stretched(self, n, k, tr=None):
        """BambooMasterBoss.StretchedTravel: el tramo del despegue a la caída escalado por k."""
        x = self.travel_at(n, tr)
        if k != 1.0 and self.air:
            a0, a1 = self.air
            x += (k - 1.0) * (self.travel_at(min(max(n, a0), a1), tr) - self.travel_at(a0, tr))
        return x


def min_windup(a, counter, ph):
    if a.special == "hop":
        return 0.0                       # sin daño: su ritmo natural (StepTimeline con windup = telegraph = 0)
    b = a.windup
    if counter:
        b = max(b, 0.5)
    if ph >= 1:
        b *= 0.9
    return max(b, 0.70 if a.red else 0.38)


class Timeline:
    """StepTimeline.Build + NormAt."""
    def __init__(self, a, windup):
        L = a.S
        self.L = L
        self.act = max(a.contact, 0.02)
        self.act_end = max(self.act, a.active_end)
        self.apex = min(max(a.apex, 0.0), self.act - 0.02)
        self.tA = self.apex * L / 0.85
        self.tR = (self.act - self.apex) * L / a.rr
        extra = max(0.0, windup - (self.tA + self.tR))
        self.hold = min(extra, 0.45)
        self.tA += extra - self.hold
        self.T = self.tA + self.hold + self.tR
        self.creep = min(0.01, (self.act - self.apex) * 0.25)
        self.sustain = 0.0

    @property
    def release(self):
        return self.tA + self.hold

    def norm(self, t):
        if t <= 0:
            return 0.0
        if t < self.tA:
            return self.apex * math.sin(t / self.tA * math.pi * 0.5)
        t -= self.tA
        if t < self.hold:
            return self.apex + self.creep * t / max(self.hold, 1e-6)
        t -= self.hold
        fr = self.apex + self.creep
        if t < self.tR:
            u = t / self.tR
            return fr + (self.act - fr) * u * u
        t -= self.tR
        if self.sustain > 0:
            return self.act + (self.act_end - self.act) * t / self.sustain if t < self.sustain else self.act_end + (t - self.sustain) / self.L
        r0 = max(1.0, 2.0 * (self.act - fr) / self.tR * self.L)
        return self.act + (t + (r0 - 1.0) * 0.06 * (1.0 - math.exp(-t / 0.06))) / self.L


def patterns(ph):
    S = Step
    out = []

    def add(name, w, minr, cd, steps, maxr=None):
        a = steps[0]
        if maxr is None:
            maxr = a.range + 0.1 if a.special == "strike" else a.ring + 0.2 if a.special == "sweep" else a.range
        out.append(dict(name=name, w=w, minr=minr, maxr=maxr, cd=cd, steps=steps, last=-99.0))

    def twins(name, wfar, wnear, cd, minr, maxr, steps):
        # BambooMasterMoves.Twins: el directo desde minr y el que se arrima y salta hacia atrás primero (mismo nombre:
        # comparten la pausa entre usos, BambooMasterBoss.ShareCooldown)
        add(name, wfar, minr, cd, steps, maxr)
        add(name, wnear, 0, cd, [S("BackHop", ph, 0, special="hop")] + steps, minr + 0.4)
        out[-1]["near"] = True

    def dash(name, w, cd, steps):
        # BambooMasterMoves.DashPatterns: desde lejos directo, de cerca con el salto atrás antes (el peso repartido)
        twins(name, w * 0.5, w * 0.5, cd, P["dash_minr"], 7.6, steps)

    def leap(name, w, cd, steps):
        # BambooMasterMoves.LeapPatterns
        twins(name, w, w * P["leap_near"], cd, P["leap_minr"], P["leap_max"] - 0.4, steps)

    D = DMG
    if ph == 0:
        palm, chopC = S("Palm", 0, D[0]["palm"]), S("ChopPalm", 0, D[0]["palm"], True)
        add("Palma", 1.3, 0, 0, [palm])
        add("Palma y Sable", 1.6, 0, 0, [palm, chopC])
        add("Pico de Grulla", 1.0, 0, 2, [S("CraneKick", 0, D[0]["palm"])])
        add("Sable y Grulla", 1.2, 0, 4, [S("ChopPalm", 0, D[0]["palm"]), S("CraneKick", 0, D[0]["palm"], True)])
        add("Tres de una Mano", 0.8, 0, 8, [palm, chopC, S("CraneKick", 0, D[0]["palm"], True)])
        leap("Grulla Voladora", 1.0, 6, [S("LeapKick", 0, D[0]["leap"], special="leap")])
    elif ph == 1:
        d = D[1]
        palm, chop = S("Palm", 1, d["palm"]), S("ChopPalm", 1, d["gold"])
        twin, twinC = S("TwinPalm", 1, d["gold"]), S("TwinPalm", 1, d["gold"], True)
        spinC = S("SpinKick", 1, d["gold"], True)
        add("Palmas Gemelas", 1.2, 0, 0, [twin])
        add("Palma y Viento", 1.4, 0, 3, [palm, spinC])
        add("Sable y Gemelas", 1.2, 0, 3, [chop, twinC])
        add("Grulla y Barrida", 1.0, 0, 6, [S("CraneKick", 1, d["gold"]), S("Sweep", 1, d["red"], True, "sweep")])
        add("Barrida", 0.6, 0, 6, [S("Sweep", 1, d["red"], special="sweep")])
        add("Cuatro Vientos", 0.7, 0, 9, [palm, S("ChopPalm", 1, d["gold"], True), twinC, spinC])
        add("Onda de Qi", 0.9, 0, 9, [S("QiWave", 1, d["red"], special="qi")], 7.0)
        dash("Paso del Viento", 1.1, 6, [S("DashStrike", 1, d["leap"], special="dash")])
        leap("Grulla Voladora", 0.8, 7, [S("LeapKick", 1, d["leap"], special="leap")])
    else:
        d = D[2]
        thrust, thrustC = S("Palm", 2, d["palm"]), S("Palm", 2, d["palm"], True)
        smashC = S("ChopPalm", 2, d["gold"], True)
        add("Estocada", 1.2, 0, 0, [thrust])
        add("Estocada y Bambú", 1.4, 0, 0, [thrust, smashC])
        add("El Bambú Vuelve", 1.1, 0, 6, [thrust, smashC, S("Sweep", 2, d["red"], True, "sweep")])
        add("Grulla y Estocada", 1.0, 0, 3, [S("CraneKick", 2, d["gold"]), thrustC])
        add("Barrida del Bastón", 0.6, 0, 6, [S("Sweep", 2, d["red"], special="sweep")])
        add("La Última Lección", 0.6, 0, 12, [thrust, smashC, thrustC, S("QiWave", 2, d["red"], True, "qi")])
        add("Raíz del Bambú", 0.8, 0, 8, [S("QiWave", 2, d["red"], special="qi")], 7.0)
        dash("Viento y Bambú", 1.0, 6, [S("DashStrike", 2, d["leap"], special="dash"), smashC])
        leap("Grulla Voladora y Estocada", 0.8, 7, [S("LeapKick", 2, d["leap"], special="leap"), thrustC])
    return out




# BambooMasterMoves: daño por fase (palma, los otros dorados, los rojos de piso, salto y embestida, contragolpe)
DMG = [dict(palm=4, gold=4, red=5, leap=5, counter=4), dict(palm=4, gold=4, red=5, leap=5, counter=4),
       dict(palm=4, gold=4.5, red=5.5, leap=5.5, counter=4)]


def counter_step(ph):
    return Step("CounterStrike", ph, DMG[ph]["counter"], counter=True)


def gauss(rng, m, s):
    return rng.gauss(m, s)


# --------------------------------------------------------------------------- la pelea
class Fight:
    def __init__(self, skill, rng, start_phase=0, stats=None, abilities=False):
        self.sk, self.rng = skill, rng
        self.abilities = abilities
        self.t = 0.0
        self.st = stats if stats is not None else {}
        # jefe
        self.ph = start_phase
        self.hp = P["health"] * P["gates"][start_phase]
        self.imb = 0.0
        self.bs = "chase"
        self.bt = 0.0              # tiempo en el estado
        self.bdur = 0.0
        self.next_attack = 0.6
        self.pats = patterns(self.ph)
        self.pat, self.step = None, 0
        self.counter_pat = dict(name="Contragolpe", steps=[counter_step(self.ph)], maxr=99, minr=0, w=1, cd=0, last=-99)
        self.stance = self.taunt = False
        self.stance_until = 0.0
        self.stance_last = False
        self.force_stance = start_phase == 0
        self.saved_imb = 0.0
        self.bounces_n, self.last_bounce = 0, -99.0
        self.exh_hits = 0
        self.frozen_until = 0.0
        self.knock = 0.0
        self.trans_until = -1.0
        self.fight_start = 0.0
        self.phase_start = 0.0
        self.counter_attack = False
        self.stance_counter = False
        self.leaps_f1 = 0
        self.commit, self.commit_until = None, 0.0
        # paso
        self.a = None
        self.clock = 0.0
        self.tl = None
        self.tell_start = 0.0
        self.tell_on = False
        self.ticked = False
        self.hit_done = False
        self.travel_done = 0.0
        self.leap_target = None
        self.qi_r = None
        self.qi_pending = False
        self.k_stretch = 1.0
        self.flight, self.behind, self.through = 1.0, False, False
        self.v_travel, self.v_reach, self.picked = None, None, False
        self.riposte_until_b, self.riposte_left, self.last_perfect = -1.0, 0, False
        self.rest_until = -1.0     # el descanso después de un contraataque de Kaito (la respuesta al desvío no lo pisa)
        # Kaito
        self.k_hp = K["hp"]
        self.sp = K["spirit0"]
        self.rage, self.rage_until, self.nodmg = 0.0, -1.0, 0.0
        self.ks = "loco"
        self.kt = 0.0
        self.k_combo = 0
        self.k_norm = 0.0
        self.k_hit_done = False
        self.k_buf = {}            # acción -> tiempo de la pulsación
        self.riposte_until = -1.0
        self.invuln_until = -1.0
        self.dash_tired = False
        self.tired_ready = -9.0
        self.parry_mul = 1.0
        self.last_whiff = -9.0
        self.parry_threat = False
        self.k_frozen_until = 0.0
        self.hurt_dur = 0.0
        # distancia y bot
        self.d = 11.0
        self.pending = []          # (tiempo, acción)
        self.next_bot = 0.0

    # ------------------------------------------------------------------ utilidades
    def stat(self, k, v=1):
        self.st[k] = self.st.get(k, 0) + v

    def rage_on(self):
        return self.t < self.rage_until

    def add_rage(self, v):
        if self.rage_on():
            self.rage_until = min(self.t + K["rage_time"], self.rage_until + K["rage_ext"] * (1 if v > 0 else -1))
            return
        streak = 1.0 + 0.6 * min(1.0, self.nodmg / 20.0)
        self.rage = min(100.0, self.rage + v * streak)
        if self.rage >= 100.0 - 1e-6:
            self.rage, self.rage_until = 0.0, self.t + K["rage_time"]
            self.stat("furia")

    def floor_hp(self):
        return P["health"] * P["gates"][self.ph + 1] if self.ph < 2 else -1e9

    def in_tell(self):
        return self.bs == "attack" and self.tell_on and self.clock >= self.tell_start

    def strike_reach(self):
        a = self.a
        if a is None:
            return 0.0
        return a.range

    def strike_eta(self):
        """Segundos hasta que el paso pega (infinito si ya pegó o no pega)."""
        a = self.a
        if self.bs != "attack" or a is None or self.hit_done:
            return math.inf
        if a.special == "qi":
            front_from = self.d if self.qi_r is None else self.d
            if self.qi_r is None:
                return max(0.0, self.tl.T - self.clock) + max(0.0, min(self.d, a.ring) - CONTACT_QI) / P["qi_speed"][self.ph]
            if self.d > a.ring:
                return math.inf
            return max(0.0, self.d - max(self.qi_r, CONTACT_QI)) / P["qi_speed"][self.ph]
        return self.tl.T - self.clock if self.clock < self.tl.T else math.inf

    # ------------------------------------------------------------------ paso del viento (BambooMasterBoss)
    def closing(self):
        """Lo que se acerca Kaito (PlayerController.Velocity contra el carril, a lo sumo a la carrera)."""
        if self.ks == "loco" and self.d > 2.2:
            return K["run"]
        if self.ks == "dash" and self.kt < K["dash_len"]:
            return K["run"]
        if self.ks == "attack" and self.d > 1.2 and self.k_norm < K["combo"][self.k_combo]["hit"] + 0.1:
            return K["run"]
        return 0.0

    def pass_along(self):
        """Kaito por el carril de la que pasa: AimPass le apunta a PassBeside de su costado, salvo de muy cerca (el giro
        llega a 60°: a 0.87 d)."""
        return math.sqrt(max(0.0, self.d ** 2 - min(P["pass_beside"], 0.87 * self.d) ** 2))

    def closing_along_pass(self):
        """Lo que se acerca Kaito por el carril de la que pasa al costado: corriendo o en su dash. El avance de su corte va
        hacia el maestro, que vuela por al lado: en el plano es casi de costado (lo abre PassAside), no por el carril."""
        return self.closing() if self.ks in ("loco", "dash") else 0.0

    def plan_dash(self, lead):
        """PlanDash: el factor del vuelo para frenar con la mano sobre donde va a estar Kaito en el contacto (sin
        límites: abajo de dash_k[0] no frena, lo atraviesa)."""
        a = self.a
        span = a.travel_at(a.air[1]) - a.travel_at(a.air[0])
        before, after = a.travel_at(a.air[0]), a.travel[-1] - a.travel_at(a.air[1])
        along = max(self.d - self.closing() * lead, CONTACT)
        return (along - CONTACT - before - after) / span

    def fix_lane(self):
        """BambooMasterBoss.FixLane: despega. El carril siguió a Kaito en la pausa agachado (AimPass): se vuelve a medir
        dónde está y el vuelo se vuelve a planear a la velocidad que eligió la suelta (entre replan[0] y replan[1] veces la
        compresión); la que pasa corta con sustain (la ventana activa a lo sumo a cut_rate veces el clip)."""
        a, tl = self.a, self.tl
        self.lane_fixed = True
        lead = max(0.0, tl.T - self.clock)
        lo, hi = self.flight * P["replan"][0], self.flight * P["replan"][1]
        if self.through:
            self.d_along = self.pass_along()
            self.pass_close = self.closing_along_pass()
            before = a.travel_at(a.air[0])
            k = (self.d_along - self.pass_close * lead + P["pass_over"] - before) / (a.travel_at(a.contact) - before)
            self.k_stretch = min(hi, max(lo, min(P["pass_k"][1], max(P["pass_k"][0], k))))
            r0 = max(1.0, 2.0 * (tl.act - (tl.apex + tl.creep)) / tl.tR * tl.L)
            tl.sustain = (tl.act_end - tl.act) * tl.L / min(r0, P["cut_rate"])
        else:
            self.k_stretch = min(hi, max(lo, min(P["dash_k"][1], max(P["dash_k"][0], self.plan_dash(lead)))))
        self.stat("embestida_k_al_despegar", self.k_stretch)

    def can_reach(self):
        """Enemy.StrikeCanReach(Kaito, radio + 0.5): ¿el bot lo considera suyo?"""
        a = self.a
        pad = K_R + 0.5
        if a.special == "strike":
            return self.d <= a.range + pad
        if a.special == "leap":
            land = min(max(self.d, P["leap_min"]), P["leap_max"])
            return abs(self.d - land) <= a.ring + pad
        if a.special in ("sweep",):
            return self.d <= a.ring + pad
        if a.special == "qi":
            return self.d <= a.ring + pad
        if a.special == "dash":
            return self.d <= a.range + pad + 2.0
        return True

    # ------------------------------------------------------------------ jefe
    def set_bs(self, s):
        if self.bs == "attack" and s != "attack":
            self.tell_on = False
        self.bs, self.bt = s, 0.0

    def pick(self, dist):
        ok = [p for p in self.pats if dist >= p["minr"] and self.t - p["last"] >= p["cd"]]
        if not ok:
            return None
        if self.ph == 0:
            # TeachLeap: desde los 14 s, hasta que sale, las dos grullas pesan x20
            leaps = [p for p in self.pats if any(st.special == "leap" for st in p["steps"])]
            used = any(p["last"] >= self.fight_start for p in leaps)
            for p in leaps:
                p.setdefault("w0", p["w"])
                p["w"] = p["w0"] * (20.0 if self.t - self.fight_start > 14 and not used else 1.0)
        else:
            # TeachDash: el paso del viento (los dos) pesa x4 hasta que sale una vez en la fase
            dashes = [p for p in self.pats if any(st.special == "dash" for st in p["steps"])]
            used = any(p["last"] >= self.phase_start for p in dashes)
            for p in dashes:
                p.setdefault("w0", p["w"])
                p["w"] = p["w0"] if used else p["w0"] * 4.0
        tot = sum(p["w"] for p in ok)
        r = self.rng.random() * tot
        for p in ok:
            r -= p["w"]
            if r <= 0:
                return p
        return ok[-1]

    def start_attack(self, counter):
        if self.pat is not None:
            self.stat("uso_" + self.pat["name"])
        if self.pat is None:
            self.pat = self.pick(0.0)
            if self.pat is None:
                self.set_bs("chase")
                return
        self.pat["last"] = self.t
        if not counter:
            for p in self.pats:
                if p is not self.pat and p["name"] == self.pat["name"]:
                    p["last"] = self.t
            if self.ph == 0 and any(st.special == "leap" for st in self.pat["steps"]):
                self.leaps_f1 += 1
            if self.pat.get("near"):
                self.stat("con_salto_atras_" + self.pat["steps"][1].special + "_f%d" % (self.ph + 1))
        self.step = 0
        self.counter_attack = counter
        self.set_bs("attack")
        self.begin_step()

    def begin_step(self):
        a = self.pat["steps"][self.step]
        self.a = a
        self.clock = 0.0
        self.hit_done = False
        self.ticked = False
        self.travel_done = 0.0
        self.leap_target = None
        self.qi_r = None
        self.qi_pending = False
        self.k_stretch = 1.0
        self.flight, self.behind, self.through = 1.0, False, False
        self.lane_fixed = True
        self.passing = False
        self.v_travel, self.v_reach, self.picked = None, None, False
        self.step_yield = False
        self.end_step_stats()
        self.cue_at = None
        if a.special == "hop":
            # BambooMasterBoss.HopScale: hasta DashFrom de Kaito, como poco un cuarto del salto
            full = -a.travel[-1]
            nxt = self.pat["steps"][self.step + 1].special if self.step + 1 < len(self.pat["steps"]) else ""
            want = P["leap_from"] if nxt == "leap" else P["dash_from"]
            self.k_stretch = min(1.0, max(P["hop_min"], (want - self.d) / full))
        w = min_windup(a, self.counter_attack and self.step == 0, self.ph)
        self.tl = Timeline(a, w)
        travel = 0.0
        if a.special == "qi":
            travel = min(max(self.d - CONTACT_QI, 0.0), a.ring) / P["qi_speed"][self.ph]
            self.tl.sustain = max(0.1, (a.ring - CONTACT_QI) / P["qi_speed"][self.ph])
        self.tell_start = max(0.0, self.tl.T + travel - MAXLEAD[a.red])
        self.tell_on = a.dmg > 0
        self.stat("pasos")

    def end_step_stats(self):
        """Lo que patinó el pie apoyado (avance perdido) y lo que corrió a Kaito en el paso que termina."""
        lost, sh = getattr(self, "step_lost", 0.0), getattr(self, "step_shove", 0.0)
        if lost > 0.0:
            self.st["avance_perdido_max"] = max(self.st.get("avance_perdido_max", 0.0), lost)
            if lost > 0.05:
                self.stat("pasos_patinan_gt5cm")
        if sh > 0.0:
            self.st["empuje_max"] = max(self.st.get("empuje_max", 0.0), sh)
        self.step_lost = self.step_shove = 0.0

    def boss_receive(self, dmg, kind, riposte, stop):
        """Enemy.ReceiveHit + BambooMasterBoss.ReceiveHit. Devuelve 'hit', 'blocked', 'guarded', 'ignored'."""
        if self.bs == "dead":
            return "ignored"
        if self.t < self.trans_until:
            return "blocked"
        if kind == "ability":
            # BambooMasterBoss.AbilityAgainstGuard: fuera de los huecos rebota y le dobla la postura
            kind = "heavy"
            if self.bounces():
                self.stat("habilidad_a_la_guardia")
                if self.stance and self.bs == "guard":
                    self.deflect("desvios_habilidad")
                self.add_imb(P["ability_posture"])
                return "blocked"
        guardable = kind in ("light", "heavy")
        if self.stance and self.bs == "guard" and guardable:
            return self.deflect("desvios")
        if guardable and self.bounces():
            return self.bounce()
        if self.ph < 2:
            mul = P["exh_mul"] if self.bs == "exhausted" else 1.0
            dmg = min(dmg, max(0.0, self.hp - self.floor_hp()) / mul)
        src = self.bs
        if src == "attack":
            src = "attack_" + ("rojo" if self.a.red else "dorado") + ("_tras" if self.clock >= self.tl.T else "_antes")
        was_recoil = self.bs == "recoil"
        self.bdur_recoil, self.bt_recoil = self.bdur, self.bt
        in_riposte = self.bs in ("stagger", "chase", "strafe") and self.t < self.riposte_until_b and self.riposte_left > 0
        if self.bs == "exhausted":
            dmg *= P["exh_mul"]
            self.exh_hits += 1
            self.bdur = max(self.bdur, self.bt + 0.6)
        self.hp -= dmg
        self.stat("dano_" + src, dmg)
        self.frozen_until = max(self.frozen_until, self.t + stop)
        if self.hp <= 0:
            self.bs = "dead"
            return "hit"
        if self.bs == "exhausted":
            cap = P["taunt_cap"] if self.taunt else P["kneel_cap"]
            if self.exh_hits >= cap:
                self.end_exhaustion()
        elif self.bs == "attack":
            pass                                         # hyperArmor
        elif self.bs != "counter":
            self.set_bs("stagger")
            self.bdur = P["stagger"] * (1.6 if kind == "heavy" else 1.0)
            # se rehace antes de volver a atacar
            self.next_attack = max(self.next_attack, self.t + self.bdur + self.rng.uniform(*P["cooldown"][self.ph]))
            self.rest_until = self.next_attack
        # el contraataque de Kaito: 2 cortes después de un parry, 3 después de uno perfecto
        if was_recoil:
            # los cortes que siguen entran mientras le dure el retroceso del parry (más el margen): el perfecto dura 1.5x
            pf = 1 if self.last_perfect else 0
            self.riposte_until_b = self.t + max(0.0, self.bdur_recoil - self.bt_recoil) + P["riposte_grace"]
            self.riposte_left = P["riposte_cuts"][pf] - 1
        elif in_riposte:
            self.riposte_left -= 1
        # cambio de fase (OnDamaged)
        if self.ph < 2 and self.hp <= self.floor_hp() + 0.5 and self.t >= self.trans_until:
            self.start_transition()
        return "hit"

    def bounces(self):
        """BambooMasterBoss.Bounces: fuera de sus huecos los cortes rebotan."""
        if self.bs == "attack":
            a = self.a
            if a.red and self.strike_eta() == math.inf:
                return False
            last = self.pat is not None and self.step == len(self.pat["steps"]) - 1
            n = self.tl.norm(self.clock)
            return not (last and a.dmg > 0 and n > a.active_end + P["hole_delay"] / a.S)
        if self.bs in ("stagger", "chase", "strafe") and self.t < self.riposte_until_b and self.riposte_left > 0:
            return False
        return self.bs in ("counter", "guard", "chase", "strafe", "alert", "stagger")

    def bounce(self):
        if self.bs not in ("attack", "counter"):
            if self.t - self.last_bounce > P["bounce_window"]:
                self.bounces_n = 0
            self.bounces_n += 1
            if self.bounces_n >= 3:
                self.bounces_n, self.last_bounce = 0, -99.0
                return self.deflect("contra_guardia")
            if self.bs != "guard":
                self.enter_guard()
            self.last_bounce = self.t
            if self.bounces_n == 2:
                # BambooMasterBoss.Bounce: el segundo seguido lo aparta y toma la palabra (contesta enseguida, aunque
                # estuviera descansando de un contraataque de Kaito)
                self.rest_until = min(self.rest_until, self.t)
                self.next_attack = self.t + P["swat_answer"]
                self.bdur = self.bt + P["swat_answer"]
                self.stat("desvio_que_contesta")
                return "deflected"
            # BambooMasterBoss.Swat: el primero no rebota, lo desvía con la palma y le contesta (sin pisar el descanso
            # que se tomó después de un contraataque de Kaito)
            self.next_attack = min(self.next_attack, max(self.t + P["answer"], self.rest_until))
            # se queda en la guardia hasta que contesta (rondando, el corte siguiente le caía en el aviso)
            self.bdur = max(self.bdur, self.bt + max(P["guardhit_extra"], self.next_attack - self.t))
            return "deflected"
        if self.bs == "attack" and not self.a.red and self.a.dmg > 0 and self.clock < self.tl.release and not self.step_yield:
            # cargando un dorado: la mano libre desvía el primer corte; el golpe sale igual
            self.step_yield = True
            return "deflected"
        self.stat("rebotes_jefe")
        self.last_bounce = self.t
        return "blocked"

    def deflect(self, why):
        # solo el contragolpe de la postura del bambú se quiebra con la parada perfecta (BambooMasterBoss.stanceCounter)
        self.stance_counter = why == "desvios"
        self.stance = False
        self.pat = self.counter_pat
        self.set_bs("counter")
        self.bdur = P["counter_clip"]
        self.next_attack = self.t
        self.stat(why)
        return "guarded"

    def start_transition(self):
        if self.ph == 0:
            self.stat("grulla_f1_%d" % min(2, self.leaps_f1))
        knelt = self.bs == "exhausted" and not self.taunt
        self.stance = self.taunt = False
        self.imb = 0.0
        dur = P["transition"][self.ph] + (0.66 if knelt else 0.0)
        self.trans_until = self.t + dur
        self.set_bs("alert")
        self.bdur = dur
        self.trans_next = self.ph + 1
        self.stat("transiciones")

    def finish_transition(self):
        self.ph = self.trans_next
        self.phase_start = self.t
        self.pats = patterns(self.ph)
        self.counter_pat = dict(name="Contragolpe", steps=[counter_step(self.ph)], maxr=99, minr=0, w=1, cd=0, last=-99)
        self.k_hp = min(K["hp"], self.k_hp + P["heal"])
        self.sp = min(100.0, self.sp + P["spirit_gift"])
        self.set_bs("chase")
        self.next_attack = self.t + 0.5

    def add_imb(self, v):
        if self.bs == "exhausted":
            return
        self.imb = min(P["max_imb"], self.imb + v)
        if self.imb >= P["max_imb"] - 0.01:
            self.become_exhausted(False)
            self.stat("quiebres")

    def enter_guard(self):
        self.set_bs("guard")
        self.bdur = P["guard_time"] * self.rng.uniform(0.7, 1.2)

    def enter_stance(self):
        self.enter_guard()
        self.stance = True
        hold = self.rng.uniform(*P["stance_time"])
        self.stance_until = self.t + hold
        self.bdur = hold + 5.0
        self.stat("posturas")

    def become_exhausted(self, taunt):
        self.stance = False
        self.taunt = taunt
        self.exh_hits = 0
        if taunt:
            self.saved_imb = self.imb
        self.set_bs("exhausted")
        self.bdur = P["taunt_time"] if taunt else P["exh_time"]
        self.stat("abierto_espera" if taunt else "rodillas")

    def end_exhaustion(self):
        self.imb = 0.0
        if self.taunt:
            self.imb = self.saved_imb
        self.taunt = False
        self.enter_guard()

    def combo_end(self):
        self.pat = None
        self.next_attack = self.t + self.rng.uniform(*P["cooldown"][self.ph])
        want = self.force_stance or (not self.stance_last and self.rng.random() < P["stance_chance"][self.ph])
        self.force_stance = False
        self.stance_last = want
        if want:
            self.enter_stance()
        else:
            self.enter_guard()

    def on_parried(self, perfect):
        self.last_perfect = perfect
        self.imb = min(P["max_imb"], self.imb + (1.5 if perfect else 1.0))
        self.tell_on = False
        counter = self.pat is self.counter_pat
        self.set_bs("recoil")
        self.bdur = P["recoil"] * (1.5 if perfect else 1.0)
        self.knock += 0.8 if perfect else 0.4
        if self.imb >= P["max_imb"] - 0.01:
            self.become_exhausted(False)
            self.stat("quiebres")
        elif counter and perfect and self.stance_counter:
            self.imb = P["max_imb"]
            self.become_exhausted(False)
            self.stat("quiebres_contra")

    def boss_tick(self):
        dt = DT
        frozen = self.t < self.frozen_until
        self.bt += dt
        s = self.bs
        if s == "dead":
            return
        if s == "alert":
            if self.t >= self.trans_until:
                self.finish_transition()
            return
        if s in ("chase", "strafe"):
            if self.t < self.rest_until - P["rest_guard_min"] and not (self.t < self.riposte_until_b and self.riposte_left > 0):
                # BambooMasterBoss.RestGuard: le entró el contraataque y se recompone en la guardia hasta que vuelve a
                # atacar (rondando, cada toque suelto era otro desvío: ~3 por contraataque contra el bot "bueno")
                self.set_bs("guard")
                self.bdur = self.rest_until - self.t
                self.stat("guardia_de_descanso")
                return
            if self.t >= self.next_attack:
                # Enemy: elige un patrón nuevo cada vez (el de un combo cortado no sigue); desde Strafe se compromete
                # con uno y se acerca hasta tenerlo en rango (2.5 s como mucho)
                if self.commit is None or self.t > self.commit_until:
                    self.commit = self.pick(self.d + (0.6 if s == "strafe" else 0.0))
                    self.commit_until = self.t + 2.5
                p = self.commit
                if p is not None:
                    if self.d <= p["maxr"]:
                        self.pat, self.commit = p, None
                        self.start_attack(False)
                        return
                    self.move_boss(+P["run"] * dt)        # se acerca a su alcance
                    return
            if self.d > P["pref"] + 1.2:
                self.move_boss(+P["run"] * dt)
            elif self.d < P["pref"]:
                self.move_boss(-P["walk"] * 0.5 * dt)    # rodea abriéndose hacia su distancia
            self.bs = "strafe" if self.d <= P["pref"] + 1.2 else "chase"
            return
        if s == "attack":
            self.attack_tick(frozen)
            return
        if s == "recoil":
            if self.bt >= self.bdur:
                self.continue_combo()
            return
        if s == "counter":
            if self.bt >= self.bdur:
                self.start_attack(True)
            return
        if s == "guard":
            if self.stance and self.t >= self.stance_until:
                self.stance = False
                self.become_exhausted(True)
                return
            if self.bt >= self.bdur:
                self.stance = False
                if self.t >= self.next_attack:
                    # BambooMasterBoss.AnswerFromGuard: si ya le toca atacar sale de la guardia con el golpe (un cuadro
                    # rondando entre la guardia y el golpe era el que Kaito usaba para meterle el corte en el aviso)
                    p = self.pick(self.d)
                    if p is not None and self.d <= p["maxr"]:
                        self.pat = p
                        self.start_attack(False)
                        return
                self.set_bs("chase")
            return
        if s == "exhausted":
            if self.bt >= self.bdur:
                self.end_exhaustion()
            return
        if s == "stagger":
            if self.bt >= self.bdur:
                self.set_bs("chase")
            return

    def continue_combo(self):
        if self.imb >= P["max_imb"]:
            self.become_exhausted(False)
            return
        self.step += 1
        if self.pat is not None and self.step < len(self.pat["steps"]):
            self.set_bs("attack")
            self.begin_step()
        else:
            self.combo_end()

    def move_boss(self, toward):
        self.d = max(CONTACT, self.d - toward)

    def attack_tick(self, frozen):
        a, tl = self.a, self.tl
        if not frozen:
            self.clock += DT
        n = tl.norm(self.clock)
        # avance del clip (frena contra Kaito; la grulla cae sobre él)
        if a.special == "leap":
            if self.leap_target is None and self.clock >= tl.release:
                self.leap_target = min(max(self.d, P["leap_min"]), min(P["leap_max"], 13.0))
                self.leap_from = self.d
        elif a.travel:
            if not self.picked and self.clock >= tl.release:
                self.picked = True
                if a.special == "dash":
                    # PlanDash: el vuelo entero escalado para frenar con la mano sobre donde va a estar Kaito al contacto;
                    # si para eso el vuelo baja de dash_k[0], la variante que pasa al costado (ReleaseDash): el cruce en el
                    # contacto (tl.T, lo que dijo el "¡ya!") donde va a estar Kaito por el carril
                    lead = max(0.0, tl.T - self.clock)
                    raw = self.plan_dash(lead)
                    self.through = raw < P["dash_k"][0] and a.pass_step is not None
                    if self.through:
                        a = self.a = a.pass_step
                        # (1D: Kaito por el carril a PassBeside del costado; sigue acercándose lo que venía hasta el cruce)
                        self.d_along = self.pass_along()
                        self.pass_close = self.closing_along_pass()
                        before = a.travel_at(a.air[0])
                        # (KaitoAlong: por el carril, que ya apunta a PassBeside de su costado)
                        along = self.pass_along() - self.pass_close * lead
                        self.k_stretch = min(P["pass_k"][1], max(P["pass_k"][0], (along + P["pass_over"] - before) /
                                                                 (a.travel_at(a.contact) - before)))
                        floor = P["pass_k"][0]
                    else:
                        self.k_stretch = min(P["dash_k"][1], max(P["dash_k"][0], raw))
                        floor = P["dash_flight"]
                    # CompressFlight: el vuelo corto a la misma velocidad y en menos tiempo, la pausa agachado se alarga
                    # lo mismo y el golpe sigue en tl.T
                    c = min(1.0, max(floor, self.k_stretch))
                    cut = tl.tR * (1.0 - c)
                    tl.tR -= cut
                    tl.hold += cut
                    self.flight = c
                    self.lane_fixed = False
                    self.stat("embestida")
                    self.stat("embestida_d", self.d)
                    self.stat("embestida_k", self.k_stretch)
                    self.stat("embestida_vuelo_m", a.stretched(1.0, self.k_stretch))
                    self.stat("embestida_al_costado" if self.through else "embestida_de_frente")
                elif a.variants:
                    # PickReach: la variante más larga cuyo paso entra (5 cm de gracia); si esa no llega a Kaito en el
                    # contacto, la de paso más largo aunque se pase hasta REACH_OVERRUN (frena antes y pega)
                    # donde va a estar Kaito en el contacto (lo que se viene acercando, hasta tocarlo como poco)
                    along = self.d - min(self.closing() * max(0.0, tl.T - self.clock), max(0.0, self.d - P["radius"] - K_R))
                    room = along - CONTACT + self.travel_done + 0.05
                    cands = [(a.travel[-1], a.reach, None)] + a.variants
                    i = next((j for j, v in enumerate(cands) if v[0] <= room), len(cands) - 1)
                    tr = lambda v: v[2] or a.travel
                    hits = lambda v: along - a.travel_at(a.contact, tr(v)) <= v[1] + 0.1 + K_R - 0.02
                    if i > 0 and not hits(cands[i]) and cands[i - 1][0] - room <= REACH_OVERRUN:
                        i -= 1
                    pick = cands[i]
                    self.v_travel, self.v_reach = pick[2], (pick[1] if i else None)
                    self.stat("variante_" + ("entera" if i == 0 else "corta" if i == len(cands) - 1 else "media"))
            if a.special == "dash" and self.picked and not self.lane_fixed and (self.clock >= tl.release or tl.T - self.clock <= 0.2):
                self.fix_lane()
            x = a.stretched(n, self.k_stretch, self.v_travel)
            dx = x - self.travel_done
            self.travel_done = x
            if dx > 0 and a.special == "dash" and self.through:
                # la que pasa al costado: s = dónde está Kaito sobre el carril desde el jefe (negativo: ya lo pasó; Kaito
                # también se mueve), a PassBeside del carril. Termina mirándolo (el giro en el aire): la distancia es
                # la de los dos
                s = (-self.d_along if self.behind else self.d_along) - dx
                if n < a.contact:
                    s -= self.pass_close * DT
                self.behind = s < 0.0
                self.d_along = abs(s)
                # (en el vuelo PassAside lo deja a PassGap del costado como poco)
                self.d = math.hypot(self.d_along, max(P["pass_gap"], min(P["pass_beside"], 0.87 * self.d)))
            elif dx > 0 and a.special == "dash":
                # de frente frena contra Kaito (la red de seguridad de Travel)
                self.d = max(CONTACT, self.d - dx)
            elif dx > 0:
                room = self.d - CONTACT
                if dx > room and self.ks != "dash":
                    # Travel: lo que no entra corre a Kaito con el cuerpo (PlayerController.Shove); el que se le mete con
                    # el dash pasa por al lado (con i-frames: el paso no frena)
                    over = dx - max(0.0, room)
                    self.stat("empuje_m", over)
                    self.stat("empujes")
                    self.step_shove += over
                self.d = max(CONTACT if self.ks != "dash" else 0.9, self.d - dx)
            elif dx < 0:
                self.d -= dx                                   # el salto atrás
        eta = self.strike_eta()
        # "¡ya!": el bot oye y aprieta
        if self.tell_on and not self.ticked and eta <= TICK[a.red] + 0.5 * DT:
            self.ticked = True
            self.cue_at = self.t
            self.bot_cue(a)
        # golpe
        if a.special == "qi":
            if self.qi_r is None and self.clock >= tl.T:
                self.qi_r = 0.0
                self.qi_prev = self.d
            if self.qi_r is not None and not self.hit_done:
                if self.qi_pending:
                    self.qi_pending = False
                    self.hit_done = True
                    self.tell_on = False
                    if self.d <= self.qi_r:
                        self.kaito_receive(a)
                else:
                    prev = self.qi_r
                    self.qi_r = CONTACT_QI if prev <= 0 else min(a.ring, self.qi_r + P["qi_speed"][self.ph] * DT)
                    if (prev <= 0 or self.qi_prev > prev) and self.d <= self.qi_r:
                        if QI_ONE_FRAME_LATE:
                            self.qi_pending = True
                        else:
                            self.hit_done = True
                            self.tell_on = False
                            self.kaito_receive(a)
                    elif self.d > a.ring:
                        self.hit_done = True
                        self.tell_on = False
                    self.qi_prev = self.d
        elif not self.hit_done and self.clock >= tl.T:
            self.hit_done = True
            self.tell_on = False
            ok = False
            if a.special == "hop":
                ok = False
                self.hit_done = True
            elif a.special == "strike":
                ok = self.d <= (self.v_reach or a.reach) + 0.1 + K_R
            elif a.special == "leap":
                ok = abs(self.d - self.leap_target) <= a.ring + K_R
                self.d = max(CONTACT, abs(self.d - self.leap_target))
            elif a.special == "sweep":
                ok = self.d - K_R <= a.ring
            elif a.special == "dash":
                # el primer cuadro después del contacto prueba aunque ya haya pasado la ventana entera (TickDash: antes,
                # con el vuelo comprimido, un cuadro de 60 Hz saltaba los 2 cuadros del clip y el golpe no salía)
                self.stat("embestida_cuadro_salta_ventana", n > a.active_end)
                # de frente: la mano sobre Kaito; al costado: el cruce a su alcance por el carril (el que lo esquiva con
                # el dash queda en los i-frames, kaito_receive)
                ok = self.d_along <= P["pass_reach"] if self.through else self.d - K_R <= a.reach + 0.3
                if self.through:
                    self.stat("cruce_n")
                    self.stat("cruce_s", self.d_along)
                    # (el que se le cruza con el dash pasa por adentro: queda lejos del cruce y está en sus i-frames)
                    self.stat("cruce_fuera", self.d_along > P["pass_reach"] and self.ks != "dash")
                    self.stat("cruce_esquiva", self.ks == "dash")
                if self.cue_at is not None:
                    err = self.t - (self.cue_at + TICK[True])
                    self.stat("cue_err_n")
                    self.stat("cue_err_sum", err)
                    self.stat("cue_err_abs_gt_0.03", abs(err) > 0.03)
            if ok:
                self.kaito_receive(a)
            elif a.special != "hop":
                self.stat("fuera_de_alcance")
        if self.bs != "attack":
            return
        if n >= 1.0:
            self.step += 1
            if self.step < len(self.pat["steps"]):
                self.begin_step()
            else:
                self.combo_end()

    # ------------------------------------------------------------------ Kaito
    def kaito_receive(self, a):
        """PlayerController.ReceiveHit."""
        ks, kt = self.ks, self.kt
        if ks == "ability":
            return                                         # abilityInvulnerable
        if ks == "dash" and not self.dash_tired and K["iframe"][0] <= kt <= K["iframe"][1]:
            self.stat("esquivas")
            return
        if self.t < self.invuln_until:
            return
        parryable = not a.red
        if ks == "parry" and parryable and kt <= K["parry_win"] * self.parry_mul:
            perfect = kt <= K["perfect"] * self.parry_mul
            self.parry_success(perfect)
            return
        if ks == "parry_ok" and parryable and kt < K["chain_parry"]:
            self.parry_success(False)
            return
        if ks == "parry_rec" and parryable and kt < K["imperfect"]:
            d = a.dmg * K["imperfect_dmg"]
            self.k_hp -= d
            self.stat("dano_kaito", d)
            self.stat("imperfectas")
            if not self.rage_on():
                self.rage = max(0.0, self.rage - K["rage_loss"] * K["imperfect_dmg"])
            self.nodmg = 0.0
            self.add_imb(0.34)
            return
        self.k_hp -= a.dmg
        self.stat("dano_kaito", a.dmg)
        self.stat("golpes_a_kaito")
        self.stat("golpe_" + a.name)
        self.nodmg = 0.0
        if not self.rage_on():
            self.rage = max(0.0, self.rage - K["rage_loss"])
        self.invuln_until = self.t + K["invuln"]
        self.frozen_until = max(self.frozen_until, self.t + 0.1)
        if self.k_hp <= 0:
            return
        self.set_ks("hurt")
        self.hurt_dur = K["hurt_heavy"]
        self.d += 2.4 + 1.2 * 0.6                   # empujón (knockback del golpe + 1.2, con fricción)

    def parry_success(self, perfect):
        self.stat("parries_perfectos" if perfect else "parries")
        self.set_ks("parry_ok")
        self.riposte_until = self.t + K["riposte_win"]
        self.sp = min(100.0, self.sp + (K["sp_perfect"] if perfect else K["sp_parry"]))
        self.add_rage(K["rage_perfect"] if perfect else K["rage_parry"])
        self.d += 0.25 if perfect else 0.55
        self.on_parried(perfect)

    def set_ks(self, s):
        self.ks, self.kt = s, 0.0

    def tap(self, act):
        self.k_buf[act] = self.t

    def buffered(self, act, window):
        t = self.k_buf.get(act)
        return t is not None and self.t - t <= window

    def consume(self, act):
        self.k_buf.pop(act, None)

    def start_parry(self):
        self.parry_mul = 0.75 if self.t - self.last_whiff < 0.35 else 1.0
        self.parry_threat = self.boss_threat()
        self.set_ks("parry")

    def boss_threat(self):
        return self.strike_eta() < 0.6 and self.d < 6.0

    def try_dash(self):
        tired = self.sp + 0.01 < K["dash_cost"]
        if tired:
            if self.t < self.tired_ready:
                return False
            self.tired_ready = self.t + K["tired_cd"]
            self.stat("dash_sin_espiritu")
        else:
            self.sp -= K["dash_cost"]
        self.dash_tired = tired
        self.set_ks("dash")
        self.stat("dashes")
        return True

    def start_attack_k(self, i, start=0.0):
        self.k_combo = i
        self.k_norm = start
        self.k_hit_done = False
        self.set_ks("attack")

    def kaito_tick(self):
        dt = DT
        self.kt += dt
        self.nodmg += dt
        s = self.ks
        if s == "ability":
            # Corte del Viento: el tajo llega a los 0.48 s y termina a los 1.03 s (PlayerController.TickWindSlash)
            if not self.k_hit_done and self.kt >= 0.48:
                self.k_hit_done = True
                dmg = K["slash_dmg"] * (K["rage_mul"] if self.rage_on() else 1.0)
                r = self.boss_receive(dmg, "ability", False, 0.08)
                if r == "hit":
                    self.stat("habilidades_que_entran")
            if self.kt >= 1.03:
                self.set_ks("loco")
            return
        if s == "loco":
            if self.abilities and self.ability_hole():
                self.sp -= K["slash_cost"]
                self.k_hit_done = False
                self.set_ks("ability")
                self.stat("habilidades")
                return
            if self.buffered("parry", 0.2):
                self.consume("parry"); self.start_parry(); return
            if self.buffered("dash", 0.2):
                self.consume("dash")
                if self.try_dash():
                    return
            if self.buffered("attack", 0.3):
                self.consume("attack"); self.start_attack_k(0); return
            return
        if s == "attack":
            c = K["combo"][self.k_combo]
            frozen = self.t < self.k_frozen_until
            speed = K["rage_spd"] if self.rage_on() else 1.0
            if not frozen:
                self.k_norm += dt * speed / c["len"]
            # avance del corte: se acerca hasta pegarse (el imán)
            if self.k_norm < c["hit"] + 0.1:
                self.d = max(1.2, self.d - 1.0 * dt / (c["len"] * 0.25))
            if not self.k_hit_done and self.k_norm >= c["hit"]:
                self.k_hit_done = True
                if self.d <= c["range"] + P["radius"] + 0.05:
                    self.kaito_hits(c)
            cutting = c["hit"] <= self.k_norm <= c["cut_end"]
            if not cutting:
                if self.buffered("parry", 0.2 + (0.15 if self.k_norm > c["cut_end"] else 0.0)):
                    self.consume("parry"); self.start_parry(); return
                if self.buffered("dash", 0.35):
                    self.consume("dash")
                    if self.try_dash():
                        return
            if self.k_norm >= c["win"] and self.k_combo < 2 and self.buffered("attack", 0.3):
                self.consume("attack"); self.start_attack_k(self.k_combo + 1); return
            if self.k_combo == 2 and self.k_norm >= K["restart"] and self.buffered("attack", 0.3):
                self.consume("attack"); self.start_attack_k(0); return
            if self.k_norm >= 1.0 + K["grace"] / c["len"]:
                self.set_ks("loco")
            return
        if s == "parry":
            if self.kt > K["parry_win"] * self.parry_mul:
                if not self.parry_threat:
                    self.last_whiff = self.t
                self.set_ks("parry_rec")
                self.stat("parry_al_aire")
            return
        if s == "parry_rec":
            if self.kt >= K["parry_recover"]:
                self.set_ks("loco")
            return
        if s == "parry_ok":
            if self.kt > 0.06:
                if self.buffered("attack", 0.25):
                    self.consume("attack"); self.start_attack_k(0, K["riposte_start"]); return
                if self.buffered("parry", 0.2):
                    self.consume("parry"); self.start_parry(); return
                if self.buffered("dash", 0.2):
                    self.consume("dash")
                    if self.try_dash():
                        return
            if self.kt >= 0.38:
                self.set_ks("loco")
            return
        if s == "dash":
            if self.kt < K["dash_len"]:
                dist = 3.0 if self.dash_tired else K["dash_dist"]
                v = dist / K["dash_len"] * (1.6 - 1.2 * self.kt / K["dash_len"])
                # hacia el jefe: pasa por al lado y sigue (sin chocar de frente)
                # hacia el jefe (sin stick sale hacia adelante): el CharacterController frena contra su cápsula
                self.d = max(0.9, self.d - v * DT)
            else:
                if self.buffered("attack", 0.25):
                    self.consume("attack"); self.start_attack_k(0); return
                if self.buffered("parry", 0.2):
                    self.consume("parry"); self.start_parry(); return
                if self.kt >= K["dash_len"] + K["dash_recover"]:
                    self.set_ks("loco")
            return
        if s == "hurt":
            if self.kt >= self.hurt_dur:
                self.set_ks("loco")
                return
            if self.kt > self.hurt_dur * 0.6 and self.buffered("dash", 0.2):
                self.consume("dash"); self.try_dash()
            return
        if s == "blocked":
            if self.kt > 0.28 and self.buffered("parry", 0.2):
                self.consume("parry"); self.start_parry(); return
            if self.kt > 0.32 and self.buffered("dash", 0.2):
                self.consume("dash")
                if self.try_dash():
                    return
            if self.kt >= K["blocked"]:
                self.set_ks("loco")

    def ability_hole(self):
        """Lo que haría un jugador con Espíritu de sobra (35 del corte + un dash): el corte en un hueco largo."""
        if self.sp < K["slash_cost"] + K["dash_cost"] or self.d > 8.0:
            return False
        if self.bs == "exhausted" and not self.taunt:
            return self.bdur - self.bt > 1.0
        return self.bs == "attack" and self.a.red and self.strike_eta() == math.inf and self.tl.T + 0.15 > self.clock

    def kaito_hits(self, c):
        riposte = self.t < self.riposte_until
        dmg = c["dmg"] * (K["rage_mul"] if self.rage_on() else 1.0) * (K["riposte_mul"] if riposte else 1.0)
        where = self.bs
        if where == "attack":
            where = "attack_" + ("aviso" if self.in_tell() else "carga" if self.clock < self.tl.T else "tras")
        r = self.boss_receive(dmg, c["kind"], riposte, c["stop"])
        self.stat("cortes")
        if r != "hit":
            # los cortes que no entran, según lo que estaba haciendo el maestro (rechazados por minuto: los que pesan)
            self.stat("rechazo")
            self.stat("rechazo_" + where)
        if r == "hit":
            self.k_frozen_until = self.t + c["stop"]
            self.sp = min(100.0, self.sp + K["sp_hit"])
            self.add_rage(K["rage_hit"])
            if riposte:
                self.riposte_until = -1
                self.stat("contraataques")
            if self.bs not in ("exhausted", "attack", "counter"):
                self.d += (0.42 if c["kb"] > 1.0 else 0.12) * 0.5
        elif r == "blocked":
            # PlayerController.Push(-dir, 0.3): sale a 3 m/s y frena a 30 m/s², 0.15 m
            self.stat("rebotes")
            self.k_frozen_until = self.t + 0.06
            self.d += 0.15
        elif r == "deflected":
            # PlayerController con Deflected: se frena un instante (sin clang) y resbala un poco hacia atrás
            self.stat("desvios_suaves")
            self.k_frozen_until = self.t + P["deflect_freeze"]
        elif r == "guarded":
            # GetCountered: Push(0.9) sale a 9 m/s y frena a 30 m/s², 1.35 m
            self.set_ks("blocked")
            self.d += 1.35

    # ------------------------------------------------------------------ bot
    def bot_cue(self, a):
        if not self.can_reach():
            return
        rng, sk = self.rng, self.sk
        if rng.random() < sk["miss"]:
            self.stat("bot_no_vio")
            return
        rt = min(0.55, max(0.15, gauss(rng, *sk["rt"]))) + 1.0 / 60.0
        dash = a.red != (rng.random() < sk["wrong"])
        self.pending.append((self.t + rt, "dash" if dash else "parry"))

    def bot_tick(self):
        for i, (when, act) in enumerate(self.pending):
            if self.t >= when:
                self.pending.pop(i)
                self.tap(act)
                self.next_bot = self.t + 0.25
                return
        # se acerca
        if self.d > 2.2 and self.ks in ("loco",):
            self.d = max(2.2, self.d - K["run"] * DT)
        if self.t < self.next_bot:
            return
        threatened = self.in_tell() and self.d < max(7.0, self.strike_reach() + 2.0)
        greedy = self.rng.random() < self.sk["greedy"] * DT * 4.0
        # el bot de AutoPilot no le pega a una guardia; --human P: en una parte P de sus decisiones de atacar sí (como un
        # jugador apurado; si no, espera a la decisión siguiente); --masher P: vuelve a tirar en cada cuadro (era el
        # --human de antes: con cualquier P le pegaba a la guardia a los 1-2 cuadros, un jugador que no para nunca)
        guard_ok = self.bs != "guard" or self.rng.random() < HUMAN_GUARD
        if not guard_ok and not MASHER:
            self.next_bot = self.t + 0.32
        if self.d < 2.6 and (not threatened or greedy) and not self.pending and guard_ok and self.bs != "dead":
            self.tap("attack")
            self.next_bot = self.t + 0.32
            self.stat("bot_ataques")

    # ------------------------------------------------------------------ bucle
    def run(self, limit=900.0):
        self.fight_start = self.t
        while self.t < limit:
            self.bot_tick()
            self.kaito_tick()
            if self.bs != "dead":
                self.boss_tick()
            if self.knock > 0:
                k = self.knock * min(1.0, DT * 10)
                self.knock -= k
                self.d += k
            if self.rage_on():
                pass
            self.t += DT
            if self.bs == "dead":
                return True, self.t, self.ph
            if self.k_hp <= 0:
                return False, self.t, self.ph
        return False, self.t, self.ph


CONTACT_QI = P["radius"] + 0.6
HUMAN_GUARD = 0.0                      # --human: probabilidad de pegarle igual a la guardia en cada decisión de atacar
MASHER = False                         # --masher: la misma probabilidad, pero vuelve a tirar en cada cuadro
QI_ONE_FRAME_LATE = True               # BambooMasterBoss.ResolveQiHit (False = el cruce pega en el mismo cuadro)
K["rage_spd"] = 1.12


def campaign(skill, rng, stats, abilities=False):
    """Intentos hasta ganar: muerte → reaparece y vuelve; llegar al bastón hace arrancar el próximo en la fase 2."""
    total, deaths, retry = 0.0, 0, 0
    reached = []
    while deaths < 15:
        f = Fight(skill, rng, retry, stats, abilities)
        won, t, ph = f.run()
        total += t + (REINTRO if deaths else 0.0)
        if won:
            return dict(win_time=t, total=total, deaths=deaths, died_in=reached)
        reached.append(ph)
        deaths += 1
        total += DEATH_AND_RETRY
        # reintento: arranca en la fase más alta a la que llegó (BambooMasterBoss.OnPlayerDied); retry_max limita
        retry = max(retry, min(ph, P["retry_max"]))
    return dict(win_time=None, total=total, deaths=deaths, died_in=reached)


def reading_table():
    print("golpe               fase  windup  anillo  '¡ya!'   apex quieto")
    seen = set()
    for ph in range(3):
        for p in patterns(ph) + [dict(steps=[counter_step(ph)])]:
            for i, st in enumerate(p["steps"]):
                key = (st.name, i > 0)
                if key in seen:
                    continue
                seen.add(key)
                tl = Timeline(st, min_windup(st, st.counter, ph))
                print("%-19s  %d %s  %.2f s  %.2f s  %.2f s   %.2f s" % (st.name, ph + 1, "c" if i > 0 else " ", tl.T,
                      min(tl.T, MAXLEAD[st.red]), TICK[st.red], tl.hold))


def window_frames():
    """El paso del viento con el vuelo comprimido: en cuántas fases del cuadro (60 y 30 Hz) ningún cuadro cae en la ventana
    activa (con la prueba de antes, el golpe no salía nunca) y cuántos cuadros se ven con el clip en el corte (f16.5-f20 de
    la que pasa, con su sustain: FixLane)."""
    print("\n-- paso del viento: la ventana activa en pantalla según el vuelo (fases de cuadro uniformes)")
    for base, floor, cut in (("de frente", P["dash_flight"], False), ("al costado", P["pass_k"][0], True)):
        st = Step("DashStrike", 1, 0, special="dash")
        if cut:
            st = st.pass_step
        for fps in (60, 30):
            row = []
            for k in (0.1, 0.2, 0.3, 0.43, 0.7, 1.0):
                tl = Timeline(st, min_windup(st, False, 1))
                c = min(1.0, max(floor, k))
                cutr = tl.tR * (1.0 - c)
                tl.tR -= cutr
                tl.hold += cutr
                if cut:
                    r0 = max(1.0, 2.0 * (tl.act - (tl.apex + tl.creep)) / tl.tR * tl.L)
                    tl.sustain = (tl.act_end - tl.act) * tl.L / min(r0, P["cut_rate"])
                skip, shown = 0, 0
                phases = 40
                for i in range(phases):
                    t0 = tl.T - 0.3 + (i / phases) / fps
                    ns = [tl.norm(t0 + j / fps) for j in range(int(0.6 * fps))]
                    if not any(tl.act <= n <= tl.act_end for n in ns):
                        skip += 1
                    shown += sum(1 for n in ns if 16.5 / st.frames <= n <= 20.0 / st.frames)
                row.append("x%.2f %3.0f %% / %.1f" % (k, 100.0 * skip / phases, shown / phases))
            print("   %-10s %d Hz: %s" % (base, fps, ", ".join(row)))
    print("   (vuelo x, % de fases sin ningún cuadro en la ventana: la prueba de antes no pegaba; / cuadros con el clip en "
          "el corte f16.5-f20. TickDash prueba ahora en el primer cuadro que pasa el contacto)")


def fairness():
    """Lo que se puede medir sin jugar: el "¡ya!" contra la reacción del bot, cuánto hay que correr para salir de cada
    rojo y si cada golpe arranca dentro del cuadro de la cámara de pelea con un jefe."""
    from statistics import NormalDist
    print("\n-- reacción: el bot aprieta rt + 1/60 s después del '¡ya!' (la latencia de audio se suma a los dos lados)")
    for sk in ("bueno", "promedio"):
        m, sd = SKILLS[sk]["rt"]
        nd = NormalDist(m, sd)
        late_gold = 1.0 - nd.cdf(TICK[False] - 1.0 / 60.0)            # parry: tiene que apretar antes del contacto
        # dash: los i-frames (0.02-0.24 s después de apretar) tienen que cubrir el contacto
        lo, hi = TICK[True] - K["iframe"][1] - 1.0 / 60.0, TICK[True] - K["iframe"][0] - 1.0 / 60.0
        bad_red = nd.cdf(lo) + 1.0 - nd.cdf(hi)
        print("   %-8s tarde al dorado %4.1f %%, fuera de los i-frames del rojo %4.1f %% (más 'no lo vio' %.0f %%)" % (
            sk, 100 * late_gold, 100 * bad_red, 100 * SKILLS[sk]["miss"]))
    print("\n-- escape de los rojos corriendo (Kaito a %.1f m/s, sin contar la aceleración)" % K["run"])
    for ph in range(3):
        for base, special in (("LeapKick", "leap"), ("Sweep", "sweep"), ("DashStrike", "dash"), ("QiWave", "qi")):
            if ph == 0 and base != "LeapKick":
                continue
            st = Step(base, ph, 0, special=special)
            tl = Timeline(st, min_windup(st, False, ph))
            if special == "leap":
                # la marca queda fija en la suelta, sobre Kaito: hay que salir del anillo entre la suelta y la caída
                t, need = tl.tR, st.ring + K_R
                what = "suelta→caída %.2f s, salir %.2f m del centro" % (t, need)
            elif special == "sweep":
                t, need = tl.T, st.ring + K_R - CONTACT
                what = "aviso→vuelta %.2f s, salir %.2f m (pegado a él)" % (t, need)
            elif special == "dash":
                # de cerca le pasa al costado (PassBeside) con el vuelo escalado ~0.45 en ese tiempo (CompressFlight): salir
                # del carril (que llega PassLaneOut más allá de Kaito) es sacar el cuerpo entero hacia afuera
                t, need = tl.tR * 0.45, 0.45 + K_R
                what = "carril fijo→contacto %.2f s de lejos, %.2f s al costado; correrse %.2f m hacia afuera" % (tl.tR, t, need)
            else:
                v, r = P["qi_speed"][ph], P["qi_radius"][ph]
                t = tl.T + (r - CONTACT_QI) / v
                need = r + K_R - CONTACT
                what = "suelta en %.2f s + frente a %.0f m/s: salir del disco (%.1f m) desde el cuerpo a pie: %.2f s" % (
                    tl.T, v, r, need / K["run"])
                print("   fase %d %-11s %s -> o el dash cuando llega el frente" % (ph + 1, base, what))
                continue
            print("   fase %d %-11s %s -> %.2f s de carrera (%s)" % (ph + 1, base, what, need / K["run"], "ok" if need / K["run"] < t - 0.15 else "JUSTO"))
    window_frames()
    print("\n-- cuadro de la cámara de pelea con jefe (CameraDirector: 19 + 0.35 d m + %.1f del perfil, 45°, FOV 30, 16:9)" % 1.6)
    import math as _m
    for d in (2.0, 4.0, 6.0, 7.6, 10.0):
        dist = min(26.0, 19.0 + 0.35 * d) + 1.6
        lean = min(0.45, 6.0 / d)
        pitch = _m.radians(45.0)
        fv = _m.radians(15.0)
        worst = []
        for sign in (1.0, -1.0):                     # el jefe "arriba" de la pantalla (lejos) o "abajo" (cerca)
            # plano vertical de la cámara: y = profundidad en el piso desde Kaito hacia arriba de la pantalla
            focus_y, focus_h = sign * d * lean, 1.0 * lean
            cam_y, cam_h = focus_y - _m.cos(pitch) * dist, focus_h + _m.sin(pitch) * dist
            def ang(y, h):
                a = _m.atan2(cam_h - h, y - cam_y)   # bajada desde la horizontal
                return a - pitch                     # >0: debajo del centro
            pts = [(0.0, 0.0), (0.0, 1.5), (sign * d, 0.0), (sign * d, 2.67)]
            worst.append(max(abs(ang(y, h)) for y, h in pts) / fv)
        print("   jefe a %4.1f m: lo más alejado del centro usa el %3.0f %% de media pantalla (jefe arriba) / %3.0f %% (abajo)" % (
            d, 100 * worst[0], 100 * worst[1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=200)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--skill", default="all")
    ap.add_argument("--table", action="store_true")
    ap.add_argument("--fair", action="store_true", help="reacción, escapes de los rojos y cuadro de la cámara")
    ap.add_argument("--abilities", action="store_true", help="Kaito usa el Corte del Viento en los huecos (el bot no)")
    ap.add_argument("--human", type=float, default=0.0, help="probabilidad de pegarle a la guardia (el bot: 0)")
    ap.add_argument("--masher", type=float, default=0.0, help="como --human, pero vuelve a tirar en cada cuadro (no para)")
    a = ap.parse_args()
    global HUMAN_GUARD, MASHER
    HUMAN_GUARD = a.masher or a.human
    MASHER = a.masher > 0
    if a.table:
        reading_table()
    if a.fair:
        fairness()
        if a.skill == "all" and a.runs == 200:
            return
    skills = list(SKILLS) if a.skill == "all" else [a.skill]
    for sk in skills:
        rng = random.Random(a.seed)
        stats = {}
        rs = [campaign(SKILLS[sk], rng, stats, a.abilities) for _ in range(a.runs)]
        wins = sorted(r["win_time"] for r in rs if r["win_time"] is not None)
        tot = sorted(r["total"] for r in rs)
        deaths = [r["deaths"] for r in rs]
        died = [0, 0, 0]
        for r in rs:
            for ph in r["died_in"]:
                died[ph] += 1
        q = lambda xs, f: xs[min(len(xs) - 1, int(f * len(xs)))] if xs else float("nan")
        print("\n%s: gana %d/%d | intento ganador %.0f s (p10 %.0f, p90 %.0f) | total con muertes %.0f s (p90 %.0f)"
              " | muertes media %.2f, sin morir %.0f %% | murió en fase 1/2/3: %d/%d/%d" % (
                  sk, len(wins), len(rs), q(wins, 0.5), q(wins, 0.1), q(wins, 0.9), q(tot, 0.5), q(tot, 0.9),
                  sum(deaths) / len(deaths), 100.0 * sum(1 for d in deaths if d == 0) / len(deaths), *died))
        n = float(a.runs)
        dmg = {k[5:]: v / n for k, v in stats.items() if k.startswith("dano_") and k != "dano_kaito"}
        tot_d = sum(dmg.values()) or 1
        print("   daño a Chikuō por estado: " + ", ".join("%s %.0f%%" % (k, 100 * v / tot_d) for k, v in sorted(dmg.items(), key=lambda x: -x[1])))
        keys = ["pasos", "parries", "parries_perfectos", "imperfectas", "esquivas", "golpes_a_kaito", "contraataques",
                "rodillas", "quiebres", "quiebres_contra", "posturas", "abierto_espera", "desvios", "contra_guardia",
                "rebotes", "desvios_suaves", "dash_sin_espiritu", "furia", "bot_no_vio", "fuera_de_alcance", "habilidades",
                "habilidades_que_entran", "habilidad_a_la_guardia", "variante_entera", "variante_media", "variante_corta",
                "embestida", "embestida_al_costado", "embestida_de_frente",
                "con_salto_atras_leap_f1", "con_salto_atras_leap_f2", "con_salto_atras_leap_f3",
                "con_salto_atras_dash_f2", "con_salto_atras_dash_f3", "avance_perdido"]
        print("   por pelea: " + ", ".join("%s %.1f" % (k, stats.get(k, 0) / n) for k in keys))
        if stats.get("cortes"):
            # cortes de Kaito que no entran (clang, desvío suave, contragolpe), por minuto de pelea y por lo que hacía el
            # maestro: la "pared" que se siente
            mins = sum(r["total"] for r in rs) / 60.0
            rej = sorted(((k[8:], v / n) for k, v in stats.items() if k.startswith("rechazo_")), key=lambda x: -x[1])
            print("   cortes rechazados: %.0f %% de %.1f por pelea, %.1f por minuto (%s)" % (
                100.0 * stats.get("rechazo", 0) / stats["cortes"], stats["cortes"] / n, stats.get("rechazo", 0) / mins,
                ", ".join("%s %.1f" % kv for kv in rej)))
        if stats.get("embestida"):
            print("   embestida: Kaito a %.2f m en la suelta, vuelo x%.2f, recorre %.2f m (medias)" % (
                stats["embestida_d"] / stats["embestida"], stats["embestida_k"] / stats["embestida"],
                stats["embestida_vuelo_m"] / stats["embestida"]))
        if stats.get("cruce_n"):
            print("   al costado: en el contacto Kaito a %.2f m del cruce por el carril (media), %.0f %% fuera del alcance sin "
                  "esquivarlo (%.0f %% se le cruza con el dash); vuelo al despegar x%.2f" % (
                      stats["cruce_s"] / stats["cruce_n"], 100.0 * stats.get("cruce_fuera", 0) / stats["cruce_n"],
                      100.0 * stats.get("cruce_esquiva", 0) / stats["cruce_n"],
                      stats.get("embestida_k_al_despegar", 0) / stats["embestida"]))
        if stats.get("embestida"):
            print("   embestida: el primer cuadro después del contacto ya pasó la ventana activa en el %.1f %% (el juego prueba "
                  "el golpe igual en ese cuadro: TickDash)" % (100.0 * stats.get("embestida_cuadro_salta_ventana", 0) / stats["embestida"]))
        if stats.get("cue_err_n"):
            print("   embestida: el golpe llega %.3f s después del '¡ya!' + %.2f (media), %.0f %% a más de 0.03 s" % (
                stats["cue_err_sum"] / stats["cue_err_n"], TICK[True], 100.0 * stats.get("cue_err_abs_gt_0.03", 0) / stats["cue_err_n"]))
        leaps = [stats.get("grulla_f1_%d" % i, 0) for i in range(3)]
        print("   grulla voladora en la fase 1 por pelea: " + ", ".join("%s %.0f %%" % (lbl, 100.0 * v / n) for lbl, v in zip(("ninguna", "una", "dos o más"), leaps)))
        uses = sorted(((k[4:], v / n) for k, v in stats.items() if k.startswith("uso_")), key=lambda x: -x[1])
        print("   patrones: " + ", ".join("%s %.1f" % kv for kv in uses))
        hits = sorted(((k[6:], v / n) for k, v in stats.items() if k.startswith("golpe_")), key=lambda x: -x[1])
        print("   golpes que más le pegan: " + ", ".join("%s %.1f" % kv for kv in hits[:8]))
        print("   paso contra Kaito: lo corre con el cuerpo %.1f veces por pelea (%.2f m en total, máx. %.2f m en un paso); el pie "
              "patina (Kaito en su dash) %.2f m por pelea, máx. %.3f m en un paso, %.1f pasos de más de 5 cm" % (
                  stats.get("empujes", 0) / n, stats.get("empuje_m", 0.0) / n, stats.get("empuje_max", 0.0),
                  stats.get("avance_perdido", 0.0) / n, stats.get("avance_perdido_max", 0.0), stats.get("pasos_patinan_gt5cm", 0) / n))
        lost = sorted(((k[15:], v / n) for k, v in stats.items() if k.startswith("avance_perdido_") and k != "avance_perdido_max"), key=lambda x: -x[1])
        print("   avance perdido contra Kaito (m por pelea): " + (", ".join("%s %.2f" % kv for kv in lost) or "nada"))


if __name__ == "__main__":
    main()
