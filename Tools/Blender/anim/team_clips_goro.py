"""Clips de Gorō, el Martillo de Kodoyama (Models/Minijefe.fbx), en el marco de autoría de team_rig (metros del juego,
frente -Y, izquierda +X). 3.4 m, piernas de 0.98 m, brazos de 1.04 m y un martillo de 3.7 m: el martillo ES el aviso, y
cada golpe lo lleva a un lugar distinto de la silueta.

El mango sigue 1.16 m más allá del agarre de abajo del equipo (Agarre1): con ese agarre la cola atravesaba el torso, la
cadera o el casco en casi todos los clips (goro_checks, colgado de build_team_anims por mesh_checks, lo mide contra cascos
convexos de cada hueso). Por eso:
  * la guardia lo lleva con una mano y la cola pasa por fuera del hombro derecho;
  * los golpes se blanden con las dos manos juntas en la punta del mango (SR/SL): la cabeza llega a 3.6-3.9 m del centro
    (más de lo que medía Hit range, 3.4-3.6: GoroBoss tiene que ajustar los alcances);
  * las poses se piden por la cabeza del martillo (club) y las vueltas a la guardia por tween (la mano y la cabeza en línea
    recta): mezclar grip/haft canal por canal hundía la cabeza en el piso o cruzaba la cola por el cuerpo.

Fase 1 (los de siempre, rehechos): Idle (respira, mira, el martillo apoyado), Walk, Run, Combo1 (diagonal desde arriba a
la derecha), Combo2 (revés a la altura de la cadera), Combo3 (de arriba), Heavy (salta y pega al aterrizar), Spin (el
torbellino con las manos en la punta), StunSpin/ExhaustedHit (doblado sobre el martillo), Parried/ParriedPerfect (rebota,
se le resbala en la mano y cae por su peso: parriedRecoil 0.5 s), Hit, HitHeavy, Spotted (el rugido), Death (se ataja con
el martillo clavado y se desploma) e Intro (clava el martillo, se lo apoya en el hombro, ruge y lo llama).

Fase 2 (con la armadura de roca de goro_armor): FakeDefeat (se tiene que creer que ganaste: de rodilla y de espaldas),
ArmorRise (las 16 rocas se le clavan una por una y se levanta trepando por el martillo), Combo1B (amague), Combo2B
(barrido a ras del piso), Combo3B (bombeo), SlamWave (ara el piso: la onda sale adelante) y AvalancheSummon (dos
martillazos y el rugido al cielo). Todos los demás clips, salvo Intro, FakeDefeat y ArmorRise, se miden también con la
armadura puesta (timing['armored'] en el sidecar): la fase 2 sigue caminando, corriendo, recibiendo golpes y muriendo
con las rocas encima.

El contrato con el juego está en el sidecar (GoroAnims.fbx.json: cuadros, normalizados, eventos, armor_from,
armor_window, punish) y en Kit_goro_armor.fbx.json (las piezas y la fórmula del vuelo).
"""
import math, os, sys
from mathutils import Vector
import nindo_anim as NA
import team_rig as T

GORO_TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bosses", "goro")
if GORO_TOOLS not in sys.path:
    sys.path.insert(0, GORO_TOOLS)

Key = NA.Key


# clips que solo se ven sin la armadura: el resto lo sigue usando en la fase 2 (camina, corre, recibe golpes, se marea,
# muere con la armadura puesta) y se mide también contra las rocas. ArmorRise las va sumando (timing['armor_from'])
UNARMORED = ("Intro", "FakeDefeat", "ArmorRise")


def mesh_checks(ch, clip, first, check):
    """build_team_anims: el martillo contra el cuerpo y contra la armadura de roca, y las rocas contra el piso
    (goro_checks). timing['armored'] queda en el sidecar: dice qué clips se pueden usar con la armadura puesta."""
    import goro_checks as GC, goro_armor as GA
    clip.timing.setdefault("armored", clip.name not in UNARMORED)
    out = GC.weapon_body(ch, clip, first, check, armor=GA.rocks_for_checks())
    out.update(GC.motion_checks(ch, clip, first, check))
    return out


# medidas del martillo (ch.weapon_info de Models/Minijefe.fbx, metros a lo largo del mango desde BaseM): Agarre1 (la
# izquierda) 0.513, Agarre2 (la derecha) 1.169, centro de la cabeza 2.553, la punta del mango -0.649
GRIP_L, GRIP_R, HEAD_C, BUTT = 0.513, 1.169, 2.553, -0.649


def club(head, haft, sr=0.0, sl=None):
    """El martillo pedido por su cabeza (lo que se lee del aviso y del golpe): el centro de la cabeza en 'head', el mango
    hacia 'haft' (de las manos a la cabeza) y la derecha corrida 'sr' m hacia la punta del mango. Devuelve grip / haft /
    slide_r (y slide_l). Con las manos más cerca de la punta del mango la cola que sobra detrás de la izquierda es más
    corta: con el agarre del equipo sobraban 1.16 m, que en los golpes acostados atravesaban el torso."""
    h = Vector(haft).normalized()
    g = Vector(head) - h * (HEAD_C - GRIP_R + sr)
    d = dict(grip=tuple(round(x, 4) for x in g), haft=tuple(round(x, 4) for x in h), slide_r=sr)
    if sl is not None:
        d["slide_l"] = sl
    return d


def club_points(pose):
    """(mano derecha, mano izquierda, cabeza, punta del mango) de una pose, en el marco de autoría (para planear)."""
    g, h = Vector(pose["grip"]), Vector(pose["haft"]).normalized()
    base = g - h * (GRIP_R - pose.get("slide_r", 0.0))
    return g, base + h * (GRIP_L + pose.get("slide_l", 0.0)), base + h * HEAD_C, base + h * BUTT


RUN_SPEED, WALK_SPEED = 3.8, 2.0          # EnemyArchetypes.Goro(): runSpeed, walkSpeed
LOCOMOTION = (("Idle", 0.0), ("Walk", WALK_SPEED / RUN_SPEED), ("Run", 1.0))
# cruces del Animator (clip, cuadro, otro clip, cuadro; -1 = el último): build_team_anims ancla ahí los brazos a la rama del
# otro clip y chequea que los antebrazos lleguen con el mismo giro local
BLENDS = ([("Walk", 0, "Idle", 0), ("Run", 0, "Walk", 0), ("Spin", -1, "StunSpin", 0), ("ExhaustedHit", 0, "StunSpin", 0),
           ("ExhaustedHit", -1, "StunSpin", 0)]
          + [(c, f, "Idle", 0) for c in ("Combo1", "Combo2", "Combo3", "Heavy", "Hit", "HitHeavy", "Spotted", "Intro",
                                         "Combo1B", "Combo2B", "Combo3B", "SlamWave", "AvalancheSummon") for f in (0, -1)]
          + [("ArmorRise", -1, "Idle", 0), ("ArmorRise", 0, "FakeDefeat", -1)]
          + [(c, 0, "Idle", 0) for c in ("Spin", "Death")]
          # el parry cruza desde el contacto del golpe parado (PARRY_FROM): ancla en el de Combo1
          + [(c, 0, "Combo1", 24) for c in ("Parried", "ParriedPerfect")]
          # y termina en la guardia (el corte arranca el paso siguiente desde ahí): la misma rama del brazo que el Idle
          + [(c, -1, "Idle", 0) for c in ("Parried", "ParriedPerfect")])

# ------------------------------------------------------------------ guardia
# el martillo con una mano, adelante a la derecha, la cabeza apoyada en el piso (pesa): desde ahí cada aviso lo levanta a
# un lugar distinto. El mango sube por afuera del brazo y la cola pasa 0.4 m por fuera de la cadera derecha (con el
# agarre del equipo rozaba el shimenawa y en la caminata entraba 11 cm en la cadera)
STANCE = dict(
    hips=(0.0, 0.02, -0.12), hips_rot=(6.0, 0.0, 10.0), spine=(8.0, 0.0, -6.0), head=(-8.0, 0.0, 0.0),
    knee_r=(-0.6, -1.0, 0.0), knee_l=(0.6, -1.0, 0.0),
    face=(0.98, 0.2, 0.0), grip_l=0.0,
    hand_l=(0.66, -0.15, 1.15), hand_l_dir=(0.1, -0.3, -0.95), hand_l_palm=(-1.0, 0.0, 0.0), fist_l=0.8,
    elbow_r=(-1.0, 0.3, -0.6), elbow_l=(1.0, 0.4, -0.4), breath=0.0, travel=0.0,
    **club((-0.55, -1.70, 0.535), (0.208, -0.859, -0.470), sr=0.10),
)
R0, L0 = (-0.48, -0.18, -10.0), (0.50, 0.24, 20.0)


def P(**kw):
    d = dict(STANCE)
    d.update(kw)
    return d


def flat_face(haft, hint):
    """Cara del martillo perpendicular al mango y horizontal (la cabeza de canto: lo menos que baja respecto de su centro),
    del lado de 'hint'. Para las poses en que la cabeza descansa en el piso o pasa cerca."""
    f = (-haft[1], haft[0], 0.0)
    m = math.hypot(f[0], f[1]) or 1.0
    sg = 1.0 if f[0] * hint[0] + f[1] * hint[1] >= 0.0 else -1.0
    return (sg * f[0] / m, sg * f[1] / m, 0.0)


def mix(a, b, u):
    """Pose a medio camino entre dos (canal por canal; un canal que falta en una vale lo de la otra)."""
    out = {}
    for k in set(a) | set(b):
        x, y = a.get(k, b.get(k)), b.get(k, a.get(k))
        out[k] = x + (y - x) * u if isinstance(x, (int, float)) else tuple(p + (q - p) * u for p, q in zip(x, y))
    return out


def tween(a, b, u, arc=0.0, hand=(0.0, 0.0, 0.0), head=(0.0, 0.0, 0.0)):
    """Pose intermedia entre dos con el martillo interpolado por lo que se ve: la mano derecha y la cabeza del martillo van
    en línea recta de una pose a la otra (la cabeza 'arc' m más alta en el medio) y el agarre sale de la distancia entre
    las dos ('hand' y 'head': corrimientos de la mano y la cabeza en el medio, para que la cola del mango o la cabeza
    pasen por afuera). Mezclar
    grip/haft/slide_r canal por canal mandaba la cabeza por debajo del piso en las vueltas a la guardia."""
    out = mix(a, b, u)
    ga, gb = Vector(a["grip"]), Vector(b["grip"])
    ha, hb = club_points(a)[2], club_points(b)[2]
    g = ga.lerp(gb, u) + Vector(hand) * math.sin(math.pi * u)
    h = ha.lerp(hb, u) + (Vector((0.0, 0.0, arc)) + Vector(head)) * math.sin(math.pi * u)
    out.update(aim(tuple(g), tuple(h)))
    out["slide_r"] = round((h - g).length - (HEAD_C - GRIP_R), 4)
    return out


def lift(pose, dz):
    """La pose con el martillo 'dz' m más alto (el agarre de la derecha): entre una clave con la cabeza en el piso y la
    guardia la interpolación hunde la cabeza unos centímetros; una clave intermedia apenas más alta la deja rozando."""
    g = pose["grip"]
    return dict(pose, grip=(g[0], g[1], g[2] + dz))


def P2(**kw):
    """Pose de golpe: las dos manos en el mango (en la guardia lo lleva con una sola)."""
    kw.setdefault("grip_l", 1.0)
    return P(**kw)


def FR(f, dy=0.0, dx=0.0, yaw=None, pitch=0.0, z=0.0, ease="inout", lift=None):
    return T.FootKey(f, R0[0] + dx, R0[1] - dy, R0[2] if yaw is None else yaw, pitch, z, 0.0, ease, lift)


def FL(f, dy=0.0, dx=0.0, yaw=None, pitch=0.0, z=0.0, ease="inout", lift=None):
    return T.FootKey(f, L0[0] + dx, L0[1] - dy, L0[2] if yaw is None else yaw, pitch, z, 0.0, ease, lift)


PLANTED = {"r": [FR(0)], "l": [FL(0)]}


# empujones del juego (Enemy): parry 0.4 m (perfecto 0.8; el parry no descuenta knockbackResist); los golpes de Kaito
# sí (0.9): 0.35-0.4 m de los livianos quedan en 0.04 m y 1.4-1.8 m de los pesados (HitHeavy) en 0.16 m
PARRY_BACK, PERFECT_BACK, HIT_BACK, HEAVY_BACK = 0.4, 0.8, 0.04, 0.16
knock_travel = T.knock_travel


def clips(ch):
    out = [idle()]
    out += locomotion(ch)
    out += [combo1(), combo2(), combo3(), heavy(), spin()]
    out += [stun_spin(), exhausted_hit(), parried(), parried_perfect(), hit(), hit_heavy(), spotted(), death()]
    out += [intro(ch)]
    out += [fake_defeat(), armor_rise()]
    out += [combo1b(), combo2b(), combo3b(), slam_wave(), avalanche_summon()]
    return out


def intro(ch):
    """Presentación del jefe (2.8 s; Boss.introAnim = 'Intro', con PlayBossIntroShot encima: StoryDirector la arranca con el
    rugido y el sacudón de cámara, y la re-presentación de un reintento la corta a los 1.2 s). Autorada (antes era la
    toma del equipo, con la cola del mango atravesándole la cadera): junta aire agachado, levanta el martillo con las dos
    manos y lo clava en el piso delante suyo (f13: la re-presentación de un reintento corta a los 1.2 s, ya pegó); lo
    arranca del piso y se lo apoya en el hombro derecho, ruge con el pecho afuera y el brazo izquierdo abierto, le hace a
    Kaito una seña con la mano de que se acerque y baja el martillo a la guardia."""
    n = 84
    GRAB = P(hips=(0.0, 0.04, -0.28), hips_rot=(14.0, 0.0, 6.0), spine=(12.0, 0.0, 0.0), head=(-18.0, 0.0, 0.0), breath=1.0,
             grip_l=0.4, **aim((-0.95, -0.55, 1.30), IDLE_HEAD + Vector((-0.10, -0.10, 0.25))))
    HEAVE = P2(hips=(0.0, 0.08, -0.12), hips_rot=(-6.0, 0.0, 6.0), spine=(-10.0, 0.0, 4.0), head=(4.0, 0.0, -4.0),
               elbow_r=(-1.0, -0.2, -0.4), elbow_l=(0.8, -0.4, -0.4), **club((-0.42, -1.62, 4.45), (-0.05, -0.22, 0.97), sr=SR, sl=SL))
    SLAM = P2(hips=(0.0, -0.04, -0.42), hips_rot=(16.0, 0.0, 2.0), spine=(10.0, 0.0, 0.0), head=(-18.0, 0.0, 0.0),
              face=(0.0, -0.22, -0.97), elbow_r=(-1.0, 0.3, -0.4), elbow_l=(1.0, 0.3, -0.4),
              **club((-0.25, -3.45, 0.93), (0.0, -0.97, -0.24), sr=SR, sl=SL))
    keys = [Key(0, P(grip_r=1.0, fist_r=1.0)), Key(4, GRAB, "inout"), Key(7, dict(tween(GRAB, HEAVE, 0.55, 0.30, hand=(-0.10, -0.12, 0.10)), grip_l=0.45), "in"),
            Key(9, HEAVE, "out"), Key(11, tween(HEAVE, SLAM, 0.45, 0.20), "in"), Key(13, SLAM, "expo_in"),
            Key(16, dict(SLAM, hips=(0.0, -0.04, -0.45)), "out")]
    # el martillo apoyado en el hombro derecho: el mango sobre el hombro por afuera (x -0.75, lejos del casco), la cabeza
    # arriba atrás y la cola adelante abajo
    REST = P(hips=(0.0, 0.03, -0.12), hips_rot=(-2.0, 0.0, 10.0), spine=(-4.0, 0.0, 6.0), head=(-6.0, 0.0, -6.0),
             face=(1.0, 0.0, 0.0), grip_l=0.0, elbow_r=(-1.0, 0.0, -0.6),
             hand_l=(0.66, -0.15, 1.15), hand_l_dir=(0.1, -0.3, -0.95), hand_l_palm=(-1.0, 0.0, 0.0), fist_l=0.8,
             **club((-0.78, 0.66, 3.25), (-0.02, 0.62, 0.78), sr=0.60))
    # ruge con el martillo en el hombro: el pecho afuera, la cabeza arriba y el brazo izquierdo abierto con el puño cerrado
    ROAR = dict(REST, hips=(0.0, 0.04, -0.08), hips_rot=(-8.0, 0.0, 6.0), spine=(-16.0, 0.0, 4.0), head=(20.0, 0.0, 4.0), breath=1.0,
                hand_l=(1.12, -0.30, 2.05), hand_l_dir=(0.6, -0.2, 0.75), hand_l_palm=(0.0, -1.0, 0.0), fist_l=1.0, elbow_l=(1.0, 0.0, -0.4))
    # le hace a Kaito una seña de que se acerque: la izquierda adelante, la palma arriba, los dedos que se cierran dos veces
    TAUNT = dict(REST, head=(-8.0, 0.0, -4.0), hand_l=(0.62, -0.95, 1.70), hand_l_dir=(-0.1, -0.9, 0.3), hand_l_palm=(0.0, -0.3, 0.95),
                 fist_l=0.2, elbow_l=(1.0, 0.2, -0.6))
    # de la cabeza clavada al hombro: sube por delante a la derecha (las manos todavía en la punta) y pasa por encima
    UP = P2(hips=(0.0, 0.04, -0.16), hips_rot=(4.0, 0.0, 8.0), spine=(2.0, 0.0, 4.0), head=(0.0, 0.0, 0.0), grip_l=0.4, face=(1.0, 0.0, 0.0),
            elbow_r=(-1.0, -0.1, -0.5), **club((-1.10, -1.85, 4.30), (-0.12, -0.30, 0.95), sr=1.0, sl=-1.0))
    # lo arranca del piso girándolo sobre las manos, que se quedan adelante (tirando de las manos hacia el hombro, la
    # cola del mango se le metía en el hombro derecho)
    SLAMH = dict(SLAM, hips=(0.0, -0.04, -0.45))
    keys += [Key(18, dict(swing(SLAMH, UP, 0.28, hand=(-0.05, -0.30, 0.05)), grip_l=0.95, slide_l=SL), "inout"),
             Key(19.5, dict(swing(SLAMH, UP, 0.62, hand=(-0.12, -0.30, 0.05)), grip_r=0.6, fist_r=0.85, grip_l=0.8), "inout"), Key(22, UP, "inout"),
             Key(26, dict(REST, grip_r=1.0, fist_r=1.0), "inout"), Key(30, ROAR, "out")]
    for i, f in enumerate(range(33, 49, 3)):
        sg = 1 if i % 2 else -1
        keys.append(Key(f, dict(ROAR, spine=(-16.0, 1.5 * sg, 4.0), head=(20.0, 0.0, 3.0 * sg)), "sine"))
    keys += [Key(52, REST, "sine"), Key(56, TAUNT, "out")]
    for i, f in enumerate(range(59, 69, 3)):
        keys.append(Key(f, dict(TAUNT, fist_l=0.7 if i % 2 == 0 else 0.15, hand_l=(0.62, -0.92 + (0.06 if i % 2 == 0 else 0.0), 1.72)), "sine"))
    # baja el martillo del hombro a la guardia por el costado derecho
    DOWN = P(hips=(0.0, 0.03, -0.14), hips_rot=(4.0, 0.0, 6.0), head=(-6.0, 0.0, 0.0), grip_r=0.4, fist_r=0.85, face=(0.98, 0.2, 0.0),
             **aim((-1.24, -0.55, 1.55), (-1.30, -2.05, 1.30)))
    keys += [Key(70, TAUNT, "sine"), Key(77, DOWN, "inout"), Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    feet = {"r": [FR(0), FR(8), FR(11, z=0.14), FR(13, ease="in"), FR(n)], "l": [FL(0), FL(n)]}
    return T.TeamClip("Intro", n, keys, feet=feet, tremble=0.0, notes="presentación: clava el martillo, ruge, se lo apoya en el hombro y lo llama",
                      timing=dict(sheet=[4, 9, 13, 22, 30, 40, 59, 77, 84],
                                  # levantarlo y clavarlo es un solo gesto rápido; 'rise': el martillo ya en el hombro (de
                                  # ahí arranca la re-presentación de un reintento, GoroBoss)
                                  swing_ok=[[4, 14]], impacts={"slam": [-0.25, -3.45]},
                                  events={"slam": 13, "rise": 26, "roar": 30, "taunt": 59}))


# ================================================================== quieto y locomoción
def aim(grip, head):
    """grip y haft para que el mango vaya de la mano derecha 'grip' hacia la cabeza en 'head' (la distancia la fija el
    agarre: la cabeza queda sobre esa recta a HEAD_C - GRIP_R + slide_r de la mano)."""
    g = Vector(grip)
    return dict(grip=tuple(g), haft=tuple((Vector(head) - g).normalized()))


IDLE_HEAD = club_points(STANCE)[2]


def idle():
    """3.2 s: un oni de 3.4 m que respira hondo dos veces (el pecho sube, los hombros se levantan y bajan con el aire),
    el peso que pasa de un pie al otro, la cabeza que mira a un lado y al otro buscando a Kaito y el puño libre que se
    cierra en la segunda respiración. La cabeza del martillo descansa en el piso: la mano la mece sin levantarla."""
    n = 96
    keys = []
    H = IDLE_HEAD
    g0 = Vector(STANCE["grip"])
    for f in range(0, n + 1, 8):
        a = 2.0 * math.pi * f / n
        b = 4.0 * math.pi * f / n
        inhale = 0.5 - 0.5 * math.cos(b)
        g = g0 + Vector((0.03 * math.sin(a), 0.0, 0.035 * inhale))
        keys.append(Key(f, P(hips=(0.035 * math.sin(a), 0.02, -0.12 - 0.02 * (1.0 - inhale)),
                             hips_rot=(6.0, -2.5 * math.sin(a), 10.0 + 2.0 * math.sin(a)),
                             spine=(8.0 - 3.0 * inhale, 1.5 * math.sin(a), -6.0),
                             head=(-8.0 + 4.0 * inhale, 0.0, 14.0 * math.sin(a + 0.9)),
                             clav_r=(0.0, 0.0, -4.0 * inhale), clav_l=(0.0, 0.0, 4.0 * inhale), breath=inhale,
                             fist_l=0.75 + 0.25 * max(0.0, math.sin(a - 0.4)),
                             hand_l=(0.66 - 0.02 * math.sin(a), -0.15, 1.15 + 0.03 * inhale),
                             **aim(g, H + Vector((0.02 * math.sin(a), 0.0, 0.0)))), "sine"))
    return T.TeamClip("Idle", n, keys, loop=True, feet=PLANTED, notes="respira hondo dos veces, mira a los lados; el martillo apoyado")


def locomotion(ch):
    out = []
    n = 24
    g = T.gait2(ch, n, WALK_SPEED, 0.58, {"r": (-0.44, -0.04, -10.0), "l": (0.44, 0.04, 14.0)}, lift=0.14, toe_off=20.0, heel=-10.0)
    g0 = Vector(STANCE["grip"])

    def walk(f):
        a = 2.0 * math.pi * f / n
        c = dict(STANCE)
        c.update(g(f))
        c["hips"] = (-0.05 * math.sin(a), 0.0, -0.14 - 0.03 * math.cos(2 * a))
        c["hips_rot"] = (8.0, 4.0 * math.sin(a), 10.0 + 6.0 * math.sin(a))
        c["spine"] = (8.0, -2.5 * math.sin(a), -6.0 - 4.0 * math.sin(a))
        # camina con la cabeza del martillo 20 cm sobre el piso, meciéndose con el paso (la mano por fuera de la cadera)
        c.update(aim(g0 + Vector((-0.02, 0.05 * math.sin(a), 0.10 + 0.03 * math.cos(2 * a))),
                     IDLE_HEAD + Vector((-0.04, 0.10 * math.sin(a), 0.22 + 0.03 * math.cos(2 * a)))))
        c["hand_l"] = (0.66, -0.15 + 0.12 * math.sin(a), 1.15)
        return c
    out.append(NA.ProcClip("Walk", n, walk, loop=True, root_vel=(0, -WALK_SPEED, 0), notes="caminata pesada a 2 m/s"))

    # corre con el martillo adelante a la derecha, la cabeza a la altura de la rodilla (atrás, como una cola, el blend de
    # locomoción mezclaba cada hueso por separado y a media mezcla la cabeza del martillo cruzaba el piso)
    n = 20
    g2 = T.gait2(ch, n, RUN_SPEED, 0.38, {"r": (-0.40, -0.06, -6.0), "l": (0.40, -0.06, 6.0)}, lift=0.22, toe_off=30.0, heel=-12.0)

    def run(f):
        a = 2.0 * math.pi * f / n
        c = dict(STANCE)
        c.update(g2(f))
        c["hips"] = (-0.04 * math.sin(a), 0.0, -0.16 - 0.05 * math.cos(2 * a - 0.9))
        c["hips_rot"] = (14.0, 3.0 * math.sin(a), 8.0 * math.sin(a))
        c["spine"] = (10.0, -2.0 * math.sin(a), -6.0 * math.sin(a))
        c["head"] = (-18.0, 0.0, 3.0 * math.sin(a))
        # (la cabeza 4 cm hacia adentro: la cola sale un poco para afuera y no roza la escarcela de roca de la fase 2)
        c.update(aim((-0.86, -0.36 + 0.06 * math.sin(a), 1.32 + 0.03 * math.cos(2 * a)), (-0.60, -1.72 + 0.06 * math.sin(a), 0.92)))
        c["face"] = (0.98, 0.2, 0.0)
        c["grip_l"] = 0.0
        c["hand_l"] = (0.62, -0.10 + 0.30 * math.sin(a), 1.35 - 0.05 * math.cos(a))
        c["hand_l_dir"] = (0.1, -0.5, -0.85)
        c["fist_l"] = 0.9
        c["elbow_r"] = (-1.0, 0.2, -0.5)
        return c
    run_clip = NA.ProcClip("Run", n, run, loop=True, root_vel=(0, -RUN_SPEED, 0), notes="corre a 3.8 m/s con el martillo adelante")
    # con la armadura, la cola del mango roza 3-4 cm la escarcela de roca en el paso del pie derecho (f14-f16): moverla
    # cambia la rama del antebrazo en el cruce con la caminata; a 3.8 m/s y desde la cámara no se ve
    run_clip.timing["clip_ok"] = [[14, 16]]
    out.append(run_clip)
    return out


# ================================================================== golpes
# agarre de los golpes: las dos manos juntas en la punta del mango, como se blande una maza (la derecha 1.4 m más abajo
# que en la guardia, la izquierda 1.0 m, a 26 cm una de otra): sobran 16 cm de mango detrás de la izquierda en vez de
# 1.16 m, que con el agarre del equipo atravesaban el torso en cada golpe acostado (el brazo de Gorō mide 1.04 m y el
# torso 1.16 de ancho: con 1 m de cola no hay pose de golpe que la deje afuera). La cabeza queda a 2.78 m de la derecha:
# los golpes llegan a 3.6-3.9 m del centro (lo que mide 'contact_head_m' en el sidecar). La izquierda va casi en el pomo
# (6 cm de cola, 36 cm entre las manos): con 16 cm de cola esa punta se metía en la panza o la cadera en los golpes y las
# vueltas a la guardia (goro_checks ahora mide la cola)
SR, SL = 1.40, -1.10


def sweep_pose():
    """La vuelta a la guardia de los martillazos al frente: la cabeza arrastrada por el piso a la derecha y las manos
    (todavía en la punta del mango, la izquierda soltando) por afuera de la cadera derecha y abajo, así la cola del mango
    pasa debajo del brazo derecho y no por el torso ni el bíceps."""
    d = Vector((-0.36, -0.88, -0.30)).normalized()
    hand = Vector((-1.15, -0.85, 1.30))
    pose = P(hips=(0.0, -0.02, -0.22), hips_rot=(8.0, 0.0, -6.0), spine=(6.0, 0.0, -4.0), head=(-12.0, 0.0, 8.0), grip_l=0.3,
             grip_r=0.1, fist_r=0.7, face=flat_face(tuple(d), (1.0, 0.0, 0.0)),
             **club(tuple(hand + d * (HEAD_C - GRIP_R + SR)), tuple(d), sr=SR))
    return pose


def recover(a, b, k=1.0):
    """De un golpe al piso a sweep_pose: las manos se abren 18 cm a la derecha y 12 cm adelante en el medio del tramo, así
    la cola del mango da la vuelta por afuera de la cadera derecha (en línea recta cruzaba la panza: 12 cm adentro)."""
    return tween(a, b, 0.4, 0.30, hand=(-0.18 * k, -0.12 * k, 0.05 * k))


def raise_grip():
    """El primer cuadro de los martillazos: la derecha corre hacia la punta del mango mientras levanta la cabeza del
    martillo adelante (agarre 1.3). Con la mano arriba en el mango, como en la guardia, sobraban 1.7 m de cola que al
    levantar la cabeza bajaban por detrás y le atravesaban el muslo derecho (14-21 cm); con 1.3 queda medio metro."""
    return held((-1.12, -0.75, 1.55), (-0.08, -1.45, -0.10), 1.3)


def combo1():
    """Martillazo en diagonal (abre el combo). Levanta el martillo derecho adelante (la izquierda lo agarra abajo), lo
    monta sobre el hombro derecho y queda armado: la cabeza a 4 m de altura arriba a la DERECHA y atrás, el cuerpo torcido
    a la derecha y el peso atrás (desde la cámara del juego, un brazo de 3 m que sale por arriba a la derecha). Baja en
    diagonal con un paso largo y las manos tirando hacia la cadera izquierda; la cabeza se clava adelante a la izquierda,
    a 3.7 m (castigo). La cola del mango pasa siempre por delante del pecho. 1.4 s: la vuelta a la guardia dura 0.4 s
    (arrastra la cabeza por el piso y cambia el agarre sin que el antebrazo dé media vuelta)."""
    n, apex, contact = 42, 21, 24
    lunge, windup = 1.2, 0.85
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=windup)
    # la cabeza sale del piso hacia afuera (la cola baja por fuera del muslo derecho) y sube derecha adelante
    RAISE = P(hips=(0.02, 0.03, -0.13), hips_rot=(4.0, 0.0, 0.0), head=(-8.0, 0.0, 8.0), grip_l=0.3, **raise_grip())
    LIFT = P2(hips=(0.03, 0.05, -0.14), hips_rot=(2.0, 0.0, -14.0), spine=(0.0, 0.0, -8.0), head=(-8.0, 0.0, 14.0), grip_l=0.65,
              elbow_r=(-1.0, -0.2, -0.4), elbow_l=(0.8, -0.4, -0.4),
              **club((-1.40, -1.75, 4.10), (-0.20, -0.36, 0.91), sr=1.3, sl=-0.88))
    TELL = P2(hips=(0.05, 0.12, -0.16), hips_rot=(0.0, 0.0, -34.0), spine=(-6.0, 0.0, -12.0), head=(-6.0, 0.0, 30.0),
              face=(0.6, -0.6, 0.3), elbow_r=(-1.0, 0.0, -0.3), elbow_l=(0.6, -0.8, -0.2),
              **club((-1.84, 1.07, 4.09), (-0.42, 0.55, 0.72), sr=SR, sl=SL))
    HOLD = dict(TELL, hips=(0.05, 0.13, -0.18), **club((-1.88, 1.12, 4.08), (-0.43, 0.57, 0.70), sr=SR, sl=SL))
    SMEAR = dict(HOLD, hips=(0.0, 0.0, -0.20), hips_rot=(10.0, 0.0, -8.0), spine=(4.0, 0.0, -4.0), head=(-12.0, 0.0, 10.0),
                 face=(0.3, -0.8, -0.5), **club((-0.95, -2.34, 3.70), (-0.28, -0.60, 0.75), sr=SR, sl=SL))
    # el golpe: la cara de abajo de la cabeza pega el piso (el centro a 0.82 m: la cabeza mide 1.6 m de cara a cara), las
    # manos estiradas a la altura del pecho y la espalda casi recta, con la cadera bien abajo y centrada (inclinado y con la
    # cadera adelante, el pecho bajaba sobre la cola del mango)
    CONTACT = P2(hips=(0.0, -0.02, -0.36), hips_rot=(6.0, 0.0, 14.0), spine=(4.0, 0.0, 6.0), head=(-14.0, 0.0, -8.0),
                 face=(0.0, -0.27, -0.96), elbow_r=(-1.0, 0.3, -0.5), elbow_l=(1.0, 0.3, -0.5),
                 **club((0.75, -3.66, 0.90), (0.17, -0.95, -0.25), sr=SR, sl=SL))
    FOLLOW = dict(CONTACT, hips=(0.0, -0.03, -0.40), hips_rot=(8.0, 0.0, 18.0), face=(0.05, -0.22, -0.97),
                  **club((0.86, -3.62, 0.92), (0.21, -0.94, -0.24), sr=SR, sl=SL))
    PUNISH = dict(FOLLOW, hips=(0.0, -0.02, -0.38), spine=(8.0, 0.0, 8.0), head=(-14.0, 0.0, -12.0),
                  **club((0.86, -3.62, 0.94), (0.21, -0.94, -0.24), sr=SR, sl=SL))
    # de vuelta a la guardia arrastra la cabeza por el piso hacia la derecha con las manos por fuera de la cadera: la cola
    # del mango da la vuelta por afuera del costado derecho (derecho desde el golpe, cruzaba el torso); la derecha sube
    # por el mango y la izquierda suelta
    SWEEP = sweep_pose()
    keys = [Key(0, P()), Key(3, RAISE, "inout"), Key(5, tween(RAISE, LIFT, 0.5, 0.10, hand=(-0.16, -0.12, 0.0)), "inout"), Key(7, LIFT, "inout"),
            Key(12, TELL, "inout"), Key(apex, HOLD, "sine"), Key(22, SMEAR, "in"), Key(contact, CONTACT, "lin"), Key(26, FOLLOW, "out"), Key(30, dict(PUNISH, grip_r=1.0, fist_r=1.0), "out"),
            Key(33, dict(recover(PUNISH, SWEEP), grip_r=0.15, fist_r=0.7), "sine"),
            Key(37, dict(SWEEP, grip_r=0.1, fist_r=0.7), "sine"),
            Key(40, dict(tween(SWEEP, P(), 0.6, 0.18), grip_r=0.5, fist_r=0.85), "sine"), Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    feet = {"r": [FR(0), FR(apex), FR(27, lunge, pitch=-10.0), FR(29, lunge)],
            "l": [FL(0), FL(12), FL(apex, pitch=16.0), FL(32, lunge, ease="out")]}
    return T.TeamClip("Combo1", n, keys, travel=tr, feet=feet, notes="martillazo en diagonal; aviso: martillo arriba a la derecha",
                      timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, 28], hold=[12, apex], lunge=lunge,
                                  windup=windup, state="Combo1", reach=2.5,
                                  # f36: la izquierda suelta el mango justo debajo del bíceps derecho (8 cm del casco del
                                  # brazo, el puño que se abre); desde la cámara no se ve cruzar nada
                                  clip_ok=[[36, 36]]))


def combo2():
    """Revés horizontal (encadenado). La izquierda baja al mango y las dos manos corren hasta la punta mientras la cabeza
    se arrastra por el piso hacia adelante; la lleva por la izquierda hasta atrás, a la altura de la cadera, con el cuerpo
    torcido a la izquierda (desde arriba: la cabeza del martillo sale del contorno por el otro lado que en Combo1). Barre
    de izquierda a derecha a la altura del pecho de Kaito, con las manos adelante (la cola del mango barre por delante de la
    panza) y la cabeza cae al piso a la derecha. 1.4 s; la vuelta gira el mango sobre la mano derecha por afuera de la
    cadera."""
    n, apex, contact = 42, 18, 21
    lunge, windup = 1.2, 0.5
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=windup)
    GATHER = P2(hips=(0.0, 0.0, -0.20), hips_rot=(10.0, 0.0, 10.0), spine=(8.0, 0.0, 6.0), head=(-14.0, 0.0, -6.0), grip_l=0.9,
                face=flat_face((0.10, -0.97, -0.22), (1.0, 0.0, 0.0)), elbow_r=(-1.0, 0.2, -0.5), elbow_l=(1.0, 0.2, -0.5),
                **club((-0.10, -3.45, 0.56), (0.10, -0.97, -0.22), sr=SR, sl=SL))
    TELL = P2(hips=(-0.04, 0.10, -0.20), hips_rot=(4.0, 0.0, 36.0), spine=(4.0, 0.0, 14.0), head=(-8.0, 0.0, -32.0),
              face=(-0.62, 0.72, 0.0), elbow_r=(-0.4, -0.8, -0.4), elbow_l=(1.0, 0.4, -0.3),
              **club((2.30, 1.30, 1.55), (0.66, 0.72, 0.12), sr=SR, sl=-0.98))
    HOLD = dict(TELL, hips=(-0.04, 0.11, -0.21), **club((2.32, 1.34, 1.55), (0.66, 0.73, 0.11), sr=SR, sl=-0.98))
    SMEAR = dict(HOLD, hips_rot=(6.0, 0.0, 14.0), spine=(6.0, 0.0, 6.0), head=(-10.0, 0.0, -10.0), face=(-0.82, -0.55, 0.0),
                 **club((2.30, -2.35, 1.25), (0.74, -0.67, 0.03), sr=SR, sl=SL))
    CONTACT = P2(hips=(0.0, -0.10, -0.26), hips_rot=(12.0, 0.0, -14.0), spine=(8.0, 0.0, -12.0), head=(-12.0, 0.0, 10.0),
                 face=(-1.0, 0.0, 0.0), elbow_r=(-1.0, 0.0, -0.4), elbow_l=(0.8, 0.5, -0.4),
                 **club((0.15, -3.85, 1.10), (0.20, -0.98, -0.05), sr=SR, sl=SL))
    # (la cabeza es un cilindro: la cara del seguimiento va del mismo lado que la de la guardia, así la vuelta no la
    # hace girar media vuelta por debajo del mango)
    FOLLOW = dict(CONTACT, hips_rot=(10.0, 0.0, -30.0), spine=(10.0, 0.0, -20.0), face=(0.38, -0.92, 0.0),
                  **club((-2.85, -1.80, 1.05), (-0.92, -0.38, -0.05), sr=SR, sl=SL))
    # la cabeza cae al piso a la derecha, de canto (de frente a frente cruzaba vertical por el piso)
    PUNISH = dict(FOLLOW, hips=(0.0, -0.08, -0.24), hips_rot=(12.0, 0.0, -24.0),
                  face=flat_face((-0.92, -0.32, -0.22), (1.0, 0.0, 0.0)), **club((-2.95, -1.70, 0.56), (-0.92, -0.32, -0.22), sr=SR, sl=SL))
    # vuelta: el mango gira sobre la mano derecha (afuera de la cadera) hasta apuntar adelante, la cabeza arrastrándose
    # por el piso; después la derecha sube por el mango y la izquierda suelta
    TURN = P(hips=(0.0, -0.04, -0.20), hips_rot=(8.0, 0.0, -2.0), spine=(6.0, 0.0, -4.0), head=(-10.0, 0.0, 4.0), grip_l=0.3,
             grip_r=0.15, fist_r=0.7, face=flat_face((-0.30, -0.92, -0.26), (1.0, 0.0, 0.0)),
             **aim((-1.05, -0.70, 1.30), (-1.85, -3.10, 0.56)))
    TURN["slide_r"] = round((Vector((-1.85, -3.10, 0.56)) - Vector((-1.05, -0.70, 1.30))).length - (HEAD_C - GRIP_R), 3)
    keys = [Key(0, P(grip_r=1.0, fist_r=1.0)), Key(2, dict(lift(mix(P(), GATHER, 0.3), 0.10), grip_r=0.3, fist_r=0.8), "in"),
            Key(3.75, dict(lift(mix(P(), GATHER, 0.70), 0.10), grip_r=0.3, fist_r=0.8), "inout"),
            Key(5.5, dict(GATHER, grip_r=1.0, fist_r=1.0), "sine"), Key(11, TELL, "sine"), Key(apex, HOLD, "sine"), Key(19, SMEAR, "in"),
            Key(contact, CONTACT, "lin"), Key(24, FOLLOW, "out"), Key(29, dict(PUNISH, grip_r=1.0, fist_r=1.0), "out"),
            Key(32, lift(mix(PUNISH, TURN, 0.5), 0.10), "sine"), Key(34, TURN, "sine"),
            Key(38, dict(lift(mix(TURN, P(), 0.6), 0.07), grip_r=0.5, fist_r=0.85), "sine"),
            Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    feet = {"r": [FR(0), FR(apex), FR(24, lunge, pitch=-10.0), FR(26, lunge)],
            "l": [FL(0), FL(10), FL(apex, pitch=14.0), FL(29, lunge, ease="out")]}
    return T.TeamClip("Combo2", n, keys, travel=tr, feet=feet, notes="revés horizontal; aviso: martillo atrás a la izquierda",
                      timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, 24], hold=[11, apex], lunge=lunge,
                                  windup=windup, state="Combo2", reach=2.7))


def combo3():
    """El de arriba (cierra el combo). Levanta el martillo derecho adelante y lo lleva por encima de la cabeza: las dos
    manos juntas arriba, delante del casco, el mango que pasa por encima del casco y la cabeza del martillo parada atrás
    a 5 m de altura, el pecho arqueado (desde arriba: la silueta más alta). Cae derecho al frente con todo el peso; la
    cabeza se clava a 3.9 m y queda agachado. 1.27 s; vuelve arrastrando la cabeza a la derecha, como Combo1."""
    n, apex, contact = 38, 16, 19
    lunge, windup = 1.0, 0.5
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=windup)
    RAISE = P(hips=(0.02, 0.03, -0.13), hips_rot=(4.0, 0.0, 0.0), head=(-8.0, 0.0, 6.0), grip_l=0.3, **raise_grip())
    LIFT = P2(hips=(0.0, 0.06, -0.15), hips_rot=(0.0, 0.0, -6.0), spine=(-4.0, 0.0, -4.0), head=(-4.0, 0.0, 6.0), grip_l=0.8,
              elbow_r=(-1.0, -0.2, -0.4), elbow_l=(0.8, -0.4, -0.4),
              **club((-0.95, -1.90, 4.40), (-0.20, -0.30, 0.93), sr=1.3, sl=-1.05))
    TELL = P2(hips=(0.0, 0.14, -0.10), hips_rot=(-8.0, 0.0, 4.0), spine=(-12.0, 0.0, -2.0), head=(6.0, 0.0, 0.0),
              face=(0.0, 0.62, -0.78), elbow_r=(-1.0, -0.2, 0.3), elbow_l=(1.0, -0.2, 0.3),
              **club((0.11, 1.28, 5.03), (0.04, 0.62, 0.78), sr=SR, sl=SL))
    HOLD = dict(TELL, hips=(0.0, 0.15, -0.11), **club((0.11, 1.36, 4.98), (0.04, 0.65, 0.76), sr=SR, sl=SL))
    SMEAR = dict(HOLD, hips=(0.0, 0.0, -0.18), hips_rot=(8.0, 0.0, 4.0), spine=(4.0, 0.0, 0.0), head=(-8.0, 0.0, 0.0),
                 face=(0.0, -0.95, -0.30), **club((0.0, -1.66, 5.10), (0.0, -0.30, 0.95), sr=SR, sl=SL))
    CONTACT = P2(hips=(0.0, -0.05, -0.38), hips_rot=(14.0, 0.0, 4.0), spine=(10.0, 0.0, 0.0), head=(-20.0, 0.0, 0.0),
                 face=(0.0, -0.25, -0.97), elbow_r=(-1.0, 0.3, -0.4), elbow_l=(1.0, 0.3, -0.4),
                 **club((0.05, -3.90, 0.92), (0.02, -0.97, -0.25), sr=SR, sl=SL))
    FOLLOW = dict(CONTACT, hips=(0.0, -0.05, -0.42), **club((0.05, -3.88, 0.95), (0.02, -0.97, -0.24), sr=SR, sl=SL))
    SWEEP = sweep_pose()
    keys = [Key(0, P()), Key(3, RAISE, "inout"), Key(4.5, tween(RAISE, LIFT, 0.5, 0.10, hand=(-0.16, -0.12, 0.0)), "inout"), Key(6, LIFT, "lin"),
            Key(9, TELL, "out"), Key(apex, HOLD, "sine"), Key(17, SMEAR, "in"), Key(contact, CONTACT, "lin"), Key(21, FOLLOW, "out"), Key(25, dict(FOLLOW, grip_r=1.0, fist_r=1.0), "sine"),
            Key(28, dict(recover(FOLLOW, SWEEP, 0.5), grip_r=0.15, fist_r=0.7), "sine"), Key(32, SWEEP, "sine"),
            Key(35, dict(tween(SWEEP, P(), 0.6, 0.18), grip_r=0.5, fist_r=0.85), "sine"), Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    feet = {"r": [FR(0), FR(apex), FR(22, lunge, pitch=-10.0), FR(24, lunge)],
            "l": [FL(0), FL(8), FL(apex, pitch=14.0), FL(26, lunge, ease="out")]}
    return T.TeamClip("Combo3", n, keys, travel=tr, feet=feet, notes="martillazo de arriba; aviso: martillo atrás de la cabeza",
                      timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, 22], hold=[9, apex], lunge=lunge,
                                  windup=windup, state="Combo3", reach=2.9))


def heavy():
    """Golpe sísmico (imparable, onda de 4.6-6 m). Levanta el martillo y se agacha hondo con las dos manos arriba delante
    del casco y el martillo parado derecho sobre la cabeza (aviso rojo; agachado, con el mango inclinado atrás como en
    Combo3, atravesaba el casco); salta: la cima del salto es el apex (la
    pausa del juego, si la hay, lo deja suspendido arriba con el martillo en lo más alto). Cae con el martillo por delante
    y el contacto es el aterrizaje: la cabeza del martillo a 3.6 m y los dos pies en el piso a la vez."""
    n, apex, contact = 60, 32, 40
    lunge, windup = 0.5, 1.1
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=windup)
    RAISE = P(hips=(0.02, 0.03, -0.13), hips_rot=(4.0, 0.0, 0.0), head=(-8.0, 0.0, 6.0), grip_l=0.3, **raise_grip())
    LIFT = P2(hips=(0.0, 0.06, -0.18), hips_rot=(0.0, 0.0, -6.0), spine=(-4.0, 0.0, -4.0), head=(-4.0, 0.0, 6.0), grip_l=0.8,
              elbow_r=(-1.0, -0.2, -0.4), elbow_l=(0.8, -0.4, -0.4),
              **club((-0.95, -1.90, 4.40), (-0.20, -0.30, 0.93), sr=1.3, sl=-1.05))
    CROUCH = P2(hips=(0.0, 0.10, -0.40), hips_rot=(14.0, 0.0, 0.0), spine=(-6.0, 0.0, 0.0), head=(-10.0, 0.0, 0.0),
                knee_r=(-0.8, -0.8, 0.0), knee_l=(0.8, -0.8, 0.0), face=(0.0, 0.62, -0.78),
                elbow_r=(-1.0, -0.2, 0.3), elbow_l=(1.0, -0.2, 0.3), **club((-0.04, 0.52, 5.22), (0.03, 0.35, 0.94), sr=SR, sl=SL))
    DEEP = dict(CROUCH, hips=(0.0, 0.11, -0.46), **club((-0.04, 0.56, 5.16), (0.03, 0.37, 0.93), sr=SR, sl=SL))
    TAKEOFF = dict(CROUCH, hips=(0.0, 0.04, 0.14), hips_rot=(4.0, 0.0, 0.0), spine=(-10.0, 0.0, 0.0), head=(-6.0, 0.0, 0.0),
                   **club((0.10, 1.10, 5.70), (0.04, 0.52, 0.85), sr=SR, sl=SL))
    TOP = dict(TAKEOFF, hips=(0.0, 0.0, 0.50), knee_r=(-0.6, -1.0, 0.0), knee_l=(0.6, -1.0, 0.0), spine=(-14.0, 0.0, 0.0),
               **club((0.10, 0.85, 6.10), (0.04, 0.40, 0.92), sr=SR, sl=SL))
    FALL = dict(TOP, hips=(0.0, -0.06, 0.30), hips_rot=(14.0, 0.0, 0.0), spine=(6.0, 0.0, 0.0), head=(-14.0, 0.0, 0.0),
                face=(0.0, -0.95, -0.30), **club((0.05, -1.95, 5.20), (0.02, -0.40, 0.92), sr=SR, sl=SL))
    # el aterrizaje: la cadera abajo del todo, las manos estiradas a la altura de las rodillas y la cara de abajo de la
    # cabeza en el piso (centro a 0.92 m: con el mango inclinado la cabeza pega con el canto)
    LAND = P2(hips=(0.0, -0.06, -0.50), hips_rot=(20.0, 0.0, 0.0), spine=(10.0, 0.0, 0.0), head=(-22.0, 0.0, 0.0),
              knee_r=(-0.8, -0.8, 0.0), knee_l=(0.8, -0.8, 0.0), face=(0.0, -0.20, -0.98),
              elbow_r=(-1.0, 0.3, -0.4), elbow_l=(1.0, 0.3, -0.4), **club((0.05, -3.70, 0.92), (0.02, -0.98, -0.20), sr=SR, sl=SL))
    SWEEP = sweep_pose()
    keys = [Key(0, P()), Key(3, RAISE, "inout"), Key(4.5, tween(RAISE, LIFT, 0.5, 0.10, hand=(-0.16, -0.12, 0.0)), "inout"), Key(6, LIFT, "inout"),
            Key(12, CROUCH, "inout"), Key(22, DEEP, "sine"),
            Key(26, TAKEOFF, "out"), Key(apex, TOP, "out"), Key(36, FALL, "in"), Key(contact, LAND, "expo_in"),
            Key(43, dict(LAND, hips=(0.0, -0.05, -0.46)), "out"), Key(48, dict(LAND, grip_r=1.0, fist_r=1.0), "sine"),
            Key(51, dict(recover(LAND, SWEEP), grip_r=0.15, fist_r=0.7), "sine"), Key(54, SWEEP, "sine"),
            Key(57, dict(tween(SWEEP, P(), 0.6, 0.18), grip_r=0.5, fist_r=0.85), "sine"), Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    feet = {"r": [FR(0), FR(22), FR(26, pitch=24.0), FR(apex, 0.25, z=0.40, ease="out"), FR(contact, lunge, ease="in"), FR(n - 6, lunge)],
            "l": [FL(0), FL(22), FL(26, pitch=24.0), FL(apex, 0.25, z=0.40, ease="out"), FL(contact, lunge, ease="in"), FL(n - 6, lunge)]}
    return T.TeamClip("Heavy", n, keys, travel=tr, feet=feet, notes="golpe sísmico: salta y pega al aterrizar",
                      timing=dict(kind="unblockable", apex=apex, contact=contact, active=[contact, 42], hold=[12, 22], lunge=lunge,
                                  windup=windup, state="Heavy", reach=3.1, impacts={"land": [0.05, -3.70]}))


def stun_pose(a=0.0):
    """Mareado: doblado sobre el martillo, que quedó tirado adelante a la derecha con la cabeza en el piso (de canto); la
    derecha lo sigue agarrando por la punta del mango, como en el torbellino (sin cambiar de agarre: pasar del agarre de
    la punta a uno de bastón daba media vuelta del antebrazo en un cuadro), la izquierda en la rodilla, el cuerpo en
    círculos y la cabeza colgando. Con el agarre del equipo la cola del mango atravesaba el pecho todo el loop."""
    d = Vector((-0.20, -0.94, -0.28)).normalized()
    head = Vector((-1.62 + 0.03 * math.sin(a), -3.72, 0.56))
    return P(hips=(0.04 * math.sin(a), 0.06 + 0.03 * math.cos(a), -0.24), hips_rot=(16.0 + 4.0 * math.cos(a), 6.0 * math.sin(a), 6.0),
             spine=(14.0 + 4.0 * math.sin(a), -5.0 * math.cos(a), -6.0), head=(18.0 + 8.0 * math.sin(a + 1.0), 12.0 * math.cos(a), 10.0 * math.sin(a)),
             face=flat_face(tuple(d), (1.0, 0.0, 0.0)), grip_l=0.0,
             hand_l=(0.62, -0.42, 1.05), hand_l_dir=(0.1, -0.4, -0.9), hand_l_palm=(-1.0, 0.0, 0.0), fist_l=0.3, elbow_l=(1.0, 0.3, 0.0),
             elbow_r=(-1.0, 0.4, -0.3), **club(tuple(head), tuple(d), sr=SR))


def spin():
    """Torbellino (imparable). Las dos manos corren a la punta del mango y carga torcido a la derecha con el martillo
    estirado atrás a la derecha (la cabeza a 3 m del cuerpo). En la fase activa el juego gira el modelo a 900°/s: el
    martillo va estirado horizontal hacia afuera por delante del pecho torcido, las manos juntas en la punta (con el
    agarre del equipo el mango sobraba 1.8 m hacia el otro lado y le atravesaba el torso a cada vuelta), y el cuerpo se
    inclina al otro lado como contrapeso. Al terminar suelta la izquierda, queda mareado y cae en la pose de StunSpin."""
    n, apex, contact, end = 66, 16, 19, 56
    GATHER = P2(hips=(0.03, 0.04, -0.18), hips_rot=(6.0, 0.0, -16.0), spine=(4.0, 0.0, -10.0), head=(-10.0, 0.0, 16.0), grip_l=0.8,
                face=flat_face((-0.45, -0.86, -0.24), (0.0, 1.0, 0.0)), **club((-2.00, -3.34, 0.65), (-0.45, -0.86, -0.24), sr=SR, sl=SL))
    TELL = P2(hips=(0.06, 0.10, -0.20), hips_rot=(4.0, 0.0, -40.0), spine=(0.0, 0.0, -16.0), head=(-8.0, 0.0, 40.0),
              face=(0.5, 0.85, 0.0), elbow_r=(-1.0, 0.0, -0.4), elbow_l=(0.4, -0.9, -0.3),
              **club((-2.55, 1.90, 1.70), (-0.66, 0.74, 0.08), sr=SR, sl=SL))
    HOLD = dict(TELL, hips=(0.06, 0.11, -0.22), **club((-2.58, 1.93, 1.70), (-0.66, 0.75, 0.08), sr=SR, sl=SL))
    SPINP = P2(hips=(0.04, 0.0, -0.20), hips_rot=(4.0, 10.0, -20.0), spine=(0.0, 8.0, -28.0), head=(-10.0, -6.0, 40.0),
               face=(0.69, -0.72, 0.0), elbow_r=(-1.0, 0.0, -0.3), elbow_l=(0.3, -0.9, -0.3),
               **club((-2.75, -2.70, 1.70), (-0.72, -0.69, 0.04), sr=SR, sl=SL))
    S0 = stun_pose()
    keys = [Key(0, P(grip_r=1.0, fist_r=1.0)), Key(1, tween(P(), GATHER, 0.12, 0.25), "in"),
            Key(3, dict(tween(P(), GATHER, 0.5, 0.30, hand=(-0.18, -0.08, 0.0)), grip_r=0.3, fist_r=0.8), "lin"),
            Key(6, dict(GATHER, grip_r=1.0, fist_r=1.0), "inout"), Key(8, tween(GATHER, TELL, 0.5, 0.25), "inout"), Key(10, TELL, "inout"),
            Key(apex, HOLD, "sine"), Key(contact, SPINP, "in")]
    f = contact + 4
    while f <= end:
        a = 2.0 * math.pi * (f - contact) / 12.0
        keys.append(Key(f, dict(SPINP, hips=(0.04, 0.0, -0.20 - 0.03 * math.cos(2 * a)),
                               **club((-2.75, -2.70, 1.70 + 0.06 * math.sin(a)), (-0.72, -0.69, 0.04 + 0.02 * math.sin(a)), sr=SR, sl=SL)), "sine"))
        f += 4
    # sale del giro: la cabeza del martillo baja al piso a la derecha y la izquierda suelta; la derecha sube por el mango
    # hasta el agarre del mareo
    # sale del giro: la cabeza del martillo baja al piso adelante a la derecha, la izquierda suelta y queda mareado con
    # el mismo agarre de la punta (StunSpin)
    DROP = dict(tween(SPINP, S0, 0.6, 0.25), grip_l=0.5, hips_rot=(18.0, -10.0, 4.0), head=(24.0, -14.0, 10.0))
    keys += [Key(59, DROP, "out"), Key(62, dict(tween(SPINP, S0, 0.9, 0.06), grip_l=0.0), "sine"), Key(n, S0, "sine")]
    # pisa en el lugar mientras gira (el modelo entero rota: los pies no pueden quedar clavados, 'slide_ok')
    fr_, fl_ = [FR(0), FR(10, dx=0.06, yaw=-30.0), FR(contact, dx=0.06, yaw=-30.0)], [FL(0), FL(10, -0.10), FL(contact, -0.10)]
    f, up = contact + 3, True
    while f < end:
        fr_.append(FR(f, dx=0.06, yaw=-30.0, z=0.10 if up else 0.0, lift=0.0))
        fl_.append(FL(f, -0.10, z=0.0 if up else 0.10, lift=0.0))
        f += 3
        up = not up
    fr_ += [FR(end, dx=0.06, yaw=-30.0), FR(62, -0.10, dx=0.10, yaw=-20.0)]
    fl_ += [FL(end, -0.10), FL(60, 0.05, dx=-0.08)]
    return T.TeamClip("Spin", n, keys, feet={"r": fr_, "l": fl_}, tremble=0.0, notes="torbellino: carga torcido, gira, sale mareado",
                      timing=dict(kind="unblockable", apex=apex, contact=contact, active=[contact, end], hold=[10, apex], lunge=0.0,
                                  windup=0.95, state="Spin", slide_ok=40.0, reach=3.0,
                                  # la carga es un barrido: el martillo va de adelante a atrás a la derecha en 4 cuadros
                                  swing_ok=[[6, 10]]))


STUN_FEET = {"r": [FR(0, -0.10, dx=0.10, yaw=-20.0)], "l": [FL(0, 0.05, dx=-0.08)]}


def stun_spin():
    """Mareado/agotado (loop de 2 s: el agotamiento después del torbellino o de quebrarle la postura, y la pose de la
    ejecución): apoyado en el martillo, el cuerpo da vueltas y la cabeza le cuelga."""
    n = 60
    keys = [Key(f, stun_pose(2.0 * math.pi * f / n), "sine") for f in range(0, n + 1, 10)]
    return T.TeamClip("StunSpin", n, keys, loop=True, feet=STUN_FEET, notes="mareado: apoyado en el martillo, el cuerpo en círculos")


# el golpe parado: Enemy.OnParried cruza en 0.03 s desde el golpe en curso (el contacto de Combo1/2/3, con el martillo
# adelante en la punta del mango) al cuadro 0 del parry. Antes ese cuadro era la guardia: en 0.03 s el martillo saltaba
# de adelante a la guardia. Ahora arranca en un contacto promedio de los tres
PARRY_FROM = P2(hips=(0.0, -0.04, -0.32), hips_rot=(10.0, 0.0, 6.0), spine=(6.0, 0.0, 2.0), head=(-14.0, 0.0, -4.0),
                face=(0.0, -0.20, -0.98), elbow_r=(-1.0, 0.3, -0.4), elbow_l=(1.0, 0.3, -0.4),
                **club((0.30, -3.75, 1.00), (0.08, -0.98, -0.19), sr=SR, sl=SL))
PARRY_RECOIL = 0.5          # EnemyArchetypes.Goro(): parriedRecoil


def stumble_pose(back=0.0):
    """El martillo que se le cae adelante después del rebote: la izquierda ya soltó, la derecha (corrida a la punta, por
    afuera de la cadera) lo sostiene todavía parado e inclinado adelante a la derecha. Desde acá la caída a la guardia
    hace pasar la cola del mango por afuera del muslo derecho (desde el martillo parado delante de la cara pasaba por
    el muslo)."""
    # la derecha en la punta del mango (como en los golpes): sobra solo la cola del puño; más arriba en el mango, la cola
    # colgaba 0.7 m y le atravesaba la rodillera de roca
    p = P(hips=(0.0, 0.08 + back, -0.18), hips_rot=(4.0, 0.0, -4.0), spine=(0.0, 0.0, -4.0), head=(-4.0, 0.0, 4.0), grip_l=0.0,
          face=(0.9, 0.3, 0.3), elbow_r=(-1.0, 0.2, -0.3), hand_l=(0.30, -0.55, 1.85), hand_l_dir=(0.1, -0.5, -0.85),
          **held((-1.05, -0.62, 1.62), (-0.14, -0.31, 0.94), 1.55))
    return p


def swing(a, b, s, body=None, hand=(0.0, 0.0, 0.0)):
    """Pose a medio camino en que el martillo GIRA alrededor de las manos: el mango hace slerp, el agarre va en línea
    recta y la cabeza recorre el arco (con tween la cabeza iba en línea recta y el mango daba la vuelta en un cuadro).
    'body': la fracción del cuerpo, si va adelantado o atrasado respecto del martillo."""
    out = mix(a, b, s if body is None else body)
    out["grip"] = tuple(Vector(a["grip"]).lerp(Vector(b["grip"]), s) + Vector(hand) * math.sin(math.pi * s))
    out["haft"] = tuple(Vector(a["haft"]).normalized().slerp(Vector(b["haft"]).normalized(), s))
    out["slide_r"] = a["slide_r"] + (b["slide_r"] - a["slide_r"]) * s
    return out


def recoil_keys(knock, fracs, hand=(0.0, 0.0, 0.0)):
    """El rebote del parry: del contacto (PARRY_FROM) a 'knock' girando sobre las manos, un cuadro por fracción y frenando
    (30° por cuadro al principio, cada vez menos). El cuerpo va un poco adelantado: el golpe lo sacude entero."""
    keys = [Key(0, PARRY_FROM)]
    for i, u in enumerate(fracs):
        keys.append(Key(i + 1, swing(PARRY_FROM, knock, u, body=min(1.0, u * 1.15), hand=hand) if u < 1.0 else knock, "lin"))
    return keys


def parried_clip(name, n, cut, knock, fracs, drift, stumble, tip, feet, notes, hand=(0.0, 0.0, 0.0)):
    """Parry recibido: Enemy.OnParried cruza en 0.03 s desde el golpe en curso al cuadro 0 (el contacto promedio) y corta el
    clip a los parriedRecoil s (Goro(): 0.5; x1.5 el perfecto), donde arranca el paso siguiente con un cruce de 0.08 s:
    en el cuadro del corte tiene que estar en la guardia ('chain'). El martillo rebota girando sobre las manos con el
    frenado del golpe (como mucho 30° por cuadro: antes daba la vuelta entera en un cuadro y se quedaba congelado), queda
    vivo arriba ('drift': la cabeza se sigue yendo unos centímetros mientras le tiemblan los brazos), se le vence en la
    mano ('stumble', con la derecha floja) y cae por su peso a la guardia por tween (la mano y la cabeza en línea recta)."""
    k = len(fracs)
    up = dict(knock, **club(tuple(club_points(knock)[2] + Vector(drift)), knock["haft"], sr=knock["slide_r"], sl=knock.get("slide_l")))
    keys = recoil_keys(knock, fracs, hand)
    keys += [Key(k + 2 + (1 if k > 4 else 0), up, "sine"), Key(tip, dict(stumble, grip_r=0.8, fist_r=0.9), "sine"),
             Key(tip + (cut - tip) // 2 + 1, dict(tween(stumble, P(), 0.55, 0.15, hand=(-0.16, -0.10, 0.0)), grip_r=0.25, fist_r=0.75, grip_l=0.0), "sine"),
             Key(int(cut), P(grip_r=1.0, fist_r=1.0), "sine"), Key(n, P(), "sine")]
    return T.TeamClip(name, n, keys, travel=knock_travel(n, PARRY_BACK if name == "Parried" else PERFECT_BACK), feet=feet,
                      notes=notes, timing=dict(sheet=[0, 1, 2, k, k + 2, tip, int(cut)], chain=[(round(cut, 1), "Combo1", 0, 0.12)]))


def parried():
    """El martillo rebota (parry común: 0.5 s, 0.4 m atrás): sale despedido para arriba girando sobre las manos en 4
    cuadros (30°, 28°, 24°, 18°), queda parado delante de la cara temblando, el cuerpo se echa atrás con un paso pesado;
    se le vence adelante a la derecha y cae por su peso con la izquierda que suelta: en el corte (f15) está en la
    guardia."""
    b = PARRY_BACK
    KNOCK = P2(hips=(0.0, 0.14, -0.16), hips_rot=(-12.0, 0.0, 6.0), spine=(-12.0, 0.0, 4.0), head=(12.0, 0.0, 6.0),
               face=(0.0, 0.97, -0.1), elbow_r=(-1.0, 0.0, -0.2), elbow_l=(1.0, 0.0, -0.2),
               **club((-0.18, -1.15, 4.62), (-0.03, -0.14, 0.99), sr=SR, sl=SL))
    feet = {"l": [FL(0), FL(5, -b, ease="out", lift=0.08)],
            "r": [FR(0), FR(1), FR(8, -b, pitch=-8.0, ease="out", lift=0.08), FR(9, -b)]}
    cut = PARRY_RECOIL * T.FPS
    n = int(round(cut)) + 1
    return parried_clip("Parried", n, cut, KNOCK, (0.30, 0.58, 0.82, 1.0), (0.0, 0.06, 0.08), stumble_pose(), 9, feet,
                        "parry recibido: el martillo rebota arriba girando, se le vence en la mano y cae; en guardia al corte")


def parried_perfect():
    """Parry perfecto (0.75 s, 0.8 m: Enemy lo elige si el controller lo tiene): el martillo se va para atrás por encima
    del hombro DERECHO en 6 cuadros (con el mango por encima de la cabeza, desde la cámara del juego le partía el casco en
    dos) y lo arrastra; dos pasos pesados atrás con los brazos arriba, se le vence adelante y en el corte (f22.5) vuelve
    a la guardia."""
    b = PERFECT_BACK
    # las manos al costado derecho del casco, por encima de la hombrera; el mango sube atrás y afuera
    KNOCK = P2(hips=(0.0, 0.16, -0.12), hips_rot=(-16.0, 0.0, 10.0), spine=(-16.0, 0.0, 8.0), head=(14.0, 0.0, -8.0),
               face=(0.62, 0.70, -0.35), elbow_r=(-1.0, 0.2, 0.1), elbow_l=(0.6, -0.4, 0.2),
               **club((-1.81, 1.78, 4.88), (-0.40, 0.55, 0.73), sr=SR, sl=SL))
    feet = {"l": [FL(0), FL(6, -b + 0.15, ease="out", lift=0.10), FL(8, -b + 0.15), FL(14, -b, lift=0.05)],
            "r": [FR(0), FR(1), FR(10, -b, pitch=-8.0, ease="out", lift=0.10), FR(12, -b)]}
    cut = PARRY_RECOIL * 1.5 * T.FPS
    n = int(round(cut)) + 1
    return parried_clip("ParriedPerfect", n, cut, KNOCK, (0.22, 0.44, 0.63, 0.79, 0.91, 1.0), (-0.05, 0.08, 0.05),
                        stumble_pose(back=0.04), 13, feet,
                        "parry perfecto: el martillo se va atrás por encima del hombro derecho, dos pasos atrás; en guardia al corte",
                        # las manos suben por delante del pecho (en línea recta pasaban por adentro del torso)
                        hand=(-0.10, -0.55, 0.10))


def hit():
    """Golpe recibido cuando no tiene la armadura del golpe (0.5 s): un sacudón del pecho y la cabeza, sin soltar el
    martillo; los pies quedan clavados en el mundo con los 4 cm del empujón (aguanta)."""
    n = 15
    # el martillo se sacude en la mano (la cabeza salta del piso) sin que la mano entre hacia el cuerpo: la cola del mango
    # pasa por detrás del hombro derecho, junto a las agujas de la armadura
    PEAK = P(hips=(0.0, 0.06, -0.14), hips_rot=(-4.0, 0.0, 8.0), spine=(-10.0, 0.0, 0.0), head=(14.0, 0.0, 8.0),
             **aim((-0.92, -0.38, 1.36), IDLE_HEAD + Vector((-0.05, 0.05, 0.12))))
    keys = [Key(0, P()), Key(2, PEAK, "snap"), Key(7, dict(P(), hips=(0.0, 0.0, -0.15)), "inout"), Key(n, P(), "sine")]
    b = HIT_BACK
    feet = {"r": [FR(0), FR(3), FR(9, -b, ease="out", lift=0.05)], "l": [FL(0), FL(5), FL(11, -b, ease="out", lift=0.05)]}
    return T.TeamClip("Hit", n, keys, travel=knock_travel(n, b), feet=feet, notes="sacudón; se acomoda los 4 cm del empujón")


def hit_heavy():
    """Golpe pesado recibido (corte final y habilidades de Kaito: 0.16 m después de su resistencia; Enemy lo elige
    cuando el empujón pasa de 1 m): el sacudón más grande y un paso pesado atrás del pie derecho."""
    n = 15
    b = HEAVY_BACK
    PEAK = P(hips=(0.0, 0.10, -0.12), hips_rot=(-8.0, 0.0, 10.0), spine=(-16.0, 0.0, 2.0), head=(20.0, 0.0, 10.0),
             hand_l=(0.76, -0.05, 1.30), **aim((-0.95, -0.32, 1.44), IDLE_HEAD + Vector((-0.08, 0.10, 0.20))))
    keys = [Key(0, P()), Key(2, PEAK, "snap"), Key(8, dict(P(), hips=(0.0, 0.02, -0.17)), "inout"), Key(n, P(), "sine")]
    feet = {"r": [FR(0), FR(2), FR(8, -b, ease="out", lift=0.06)], "l": [FL(0), FL(6), FL(12, -b, ease="out", lift=0.05)]}
    return T.TeamClip("HitHeavy", n, keys, travel=knock_travel(n, b), feet=feet, notes="golpe pesado: sacudón y un paso atrás")


def exhausted_hit():
    """Golpe recibido estando mareado (Enemy lo usa si existe y al terminar vuelve al loop de StunSpin): se tambalea con
    la cabeza que se va para atrás sin despegar el martillo del piso; empieza y termina en el cuadro 0 de StunSpin (con
    Hit se paraba en plena ventana de daño)."""
    n = 12
    S = stun_pose()
    PEAK = dict(S, hips=(0.0, 0.12, -0.20), hips_rot=(4.0, -6.0, 18.0), spine=(2.0, 6.0, -2.0), head=(34.0, -10.0, 14.0))
    keys = [Key(0, S), Key(2, PEAK, "snap"), Key(6, dict(S, hips=(0.03, 0.04, -0.24), head=(10.0, 8.0, 4.0)), "inout"), Key(n, S, "sine")]
    b = HIT_BACK
    feet = {k: [v[0], T.FootKey(4, v[0].x, v[0].y, v[0].yaw), T.FootKey(10, v[0].x, v[0].y + b, v[0].yaw, 0.0, 0.0, 0.0, "out", 0.05)]
            for k, v in STUN_FEET.items()}
    return T.TeamClip("ExhaustedHit", n, keys, travel=knock_travel(n, b), feet=feet,
                      notes="mareado: se tambalea con el golpe; vuelve al cuadro 0 de StunSpin",
                      timing=dict(chain=[(n, "StunSpin", 0, 0.02)]))


def spotted():
    """Rugido (1.4 s): la alerta y el cambio de fase (Boss.phaseAnim). Junta aire agachado y ruge con el pecho afuera,
    los brazos abiertos y el martillo levantado con una mano (desde arriba: la silueta más ancha)."""
    n = 42
    # el martillo se levanta parado a la derecha, con la mano por afuera del hombro: la cola baja por fuera del muslo
    # derecho (levantado sobre la cabeza con el agarre de la guardia, la cola le atravesaba la pierna)
    IN = P(hips=(0.0, 0.06, -0.24), hips_rot=(16.0, 0.0, 6.0), spine=(14.0, 0.0, 0.0), head=(-20.0, 0.0, 0.0),
           **aim((-1.05, -0.50, 1.35), (-1.30, -1.85, 0.95)))
    ROAR = P(hips=(0.0, 0.04, -0.10), hips_rot=(-6.0, 0.0, 0.0), spine=(-16.0, 0.0, 0.0), head=(18.0, 0.0, 0.0),
             face=(0.0, -1.0, 0.1), grip_l=0.0, elbow_r=(-1.0, 0.0, -0.2),
             hand_l=(1.10, -0.20, 2.10), hand_l_dir=(0.6, -0.1, 0.8), hand_l_palm=(0.0, -1.0, 0.0), fist_l=1.0, elbow_l=(1.0, 0.0, -0.4),
             **aim((-1.36, -0.18, 2.60), (-1.64, -0.24, 4.07)))
    keys = [Key(0, P()), Key(4, tween(P(), IN, 0.5, 0.10, hand=(-0.10, 0.0, 0.0)), "in"), Key(8, IN, "out"),
            Key(11, tween(IN, ROAR, 0.5, 0.0, hand=(-0.15, 0.0, 0.0)), "inout"), Key(14, ROAR, "inout")]
    for i, f in enumerate(range(16, 33, 2)):
        s = 1 if i % 2 else -1
        keys.append(Key(f, dict(ROAR, spine=(-16.0, 1.2 * s, 0.0), head=(18.0, 0.0, 2.0 * s)), "sine"))
    keys += [Key(35, dict(ROAR, hips=(0.0, 0.03, -0.12)), "sine"), Key(39, tween(ROAR, P(), 0.6, 0.10, hand=(-0.15, 0.0, 0.0)), "sine"),
             Key(n, P(), "sine")]
    feet = {"r": [FR(0), FR(10), FR(14, dx=-0.08, lift=0.06), FR(34, dx=-0.08), FR(n, lift=0.06)],
            "l": [FL(0), FL(10), FL(14, dx=0.08, lift=0.06), FL(32, dx=0.08), FL(n - 2, lift=0.06)]}
    return T.TeamClip("Spotted", n, keys, feet=feet, tremble=0.0, notes="rugido: pecho afuera, brazos abiertos")


def planted(head_world, haft, sr, travel):
    """club() con la cabeza clavada en el MUNDO: los clips autoran las manos respecto del transform del juego, que en la
    muerte se corre 0.8 m atrás (DeathRoutine); sin compensar, la cabeza apoyada patinaba por el piso con él."""
    h = Vector(head_world) + Vector((0.0, travel, 0.0))
    return club(tuple(h), haft, sr=sr)


def death():
    """Muerte (2 s, deathClipFalls): el golpe lo echa atrás y se ataja con el martillo, que queda clavado de cabeza en el
    piso a su derecha, con el mango parado; la derecha baja por el mango (la cola sube 2 m por encima de su mano, por
    afuera del hombro: de bastón, con el agarre del equipo, la cola le atravesaba la cadera). Se le doblan las rodillas,
    queda arrodillado agarrado del mango con la cabeza gacha, la mano se le resbala y se desploma hacia adelante; el
    martillo se vence solo hacia la derecha y cae acostado al piso."""
    n = 60
    slide = [-0.8 * math.sin(min(1.0, (f / T.FPS) * 1.8) * math.pi * 0.5) for f in range(n + 1)]
    # la cabeza del martillo en el mundo (respecto del transform en f0), con las caras mirando adelante y atrás: la cabeza
    # mide 1.6 m de cara a cara y 1 m de ancho; de costado le entraba en el muslo derecho
    HW = Vector((-1.42, -0.02, 0.52))
    down = Vector((0.04, 0.02, -1.0))          # de la mano a la cabeza: el mango parado
    face = (0.0, 1.0, 0.0)
    REC = P(hips=(0.0, 0.12, -0.12), hips_rot=(-6.0, 0.0, 8.0), spine=(-8.0, 0.0, 0.0), head=(14.0, 0.0, 6.0), face=face,
            grip_r=0.3, fist_r=0.75, elbow_r=(-1.0, 0.4, -0.3), **planted(HW + Vector((0.0, -0.15, 0.0)), tuple(down), -0.20, slide[4]))
    STEADY = P(hips=(0.0, 0.10, -0.20), hips_rot=(6.0, 0.0, 8.0), spine=(6.0, 0.0, 0.0), head=(16.0, 0.0, 4.0), face=face,
               elbow_r=(-1.0, 0.4, -0.3), **planted(HW, tuple(down), -0.28, slide[12]))
    KNEEL = P(hips=(0.0, 0.16, -0.58), hips_rot=(-2.0, 0.0, 8.0), spine=(10.0, 0.0, 0.0), head=(24.0, 0.0, 0.0),
              knee_r=(-0.3, -1.0, -0.3), knee_l=(0.3, -1.0, -0.3), face=face, grip_l=0.0, elbow_r=(-1.0, 0.4, -0.2),
              hand_l=(0.50, -0.30, 0.95), hand_l_dir=(0.0, -0.3, -0.95), hand_l_palm=(-1.0, 0.0, 0.0), fist_l=0.2,
              **planted(HW, tuple(down), -0.62, slide[24]))
    BOW = dict(KNEEL, spine=(26.0, 0.0, 0.0), head=(30.0, 0.0, 0.0), hips=(0.0, 0.16, -0.55),
               **planted(HW, tuple(down), -0.70, slide[44]))
    # se le resbala la mano ('drop_r': la derecha deja el mango y ataja la caída como la izquierda); el martillo se vence
    # a la derecha girando sobre la cabeza apoyada y queda acostado, la cola en el piso 3 m afuera
    TIP = Vector((0.62, 0.05, -0.78)).normalized()
    LAID = Vector((0.99, 0.05, 0.11)).normalized()      # la cola apoyada en el piso por el pomo (12 cm de radio)
    DOWN = dict(BOW, hips=(0.0, -0.10, -0.48), hips_rot=(62.0, 0.0, 10.0), spine=(18.0, 0.0, 0.0), head=(-20.0, 0.0, 20.0),
                hand_l=(0.55, -0.80, 0.40), hand_l_dir=(0.0, -0.8, -0.3), grip_r=0.15, fist_r=0.5,
                drop_r=1.0, hand_r=(-0.58, -0.82, 0.40), hand_r_dir=(0.0, -0.8, -0.3), elbow_r=(-1.0, 0.3, 0.2),
                face=flat_face(tuple(LAID), (0.0, 1.0, 0.0)), **planted(HW + Vector((0.0, 0.0, 0.03)), tuple(LAID), -0.70, slide[54]))
    TOPPLE = dict(DOWN, hips=(0.0, 0.04, -0.47), hips_rot=(38.0, 0.0, 9.0), spine=(22.0, 0.0, 0.0), drop_r=0.9, grip_r=0.4,
                  hand_r=(-0.64, -0.78, 0.80), face=face, **planted(HW, tuple(TIP), -0.70, slide[51]))
    keys = [Key(0, P(grip_r=1.0, fist_r=1.0)), Key(1, tween(P(), REC, 0.3, 0.35, hand=(-0.15, 0.0, 0.0), head=(-0.45, 0.0, 0.0)), "snap"),
            Key(2, tween(P(), REC, 0.6, 0.40, hand=(-0.28, 0.0, -0.12), head=(-0.45, 0.0, 0.0)), "lin"), Key(4, REC, "out"),
            Key(12, dict(STEADY, grip_r=1.0, fist_r=1.0), "out"), Key(24, KNEEL, "in2"),
            Key(27, dict(KNEEL, hips=(0.0, 0.16, -0.55)), "out"), Key(32, KNEEL, "sine"), Key(44, BOW, "sine"),
            Key(48, dict(BOW, grip_r=0.6, fist_r=0.8, drop_r=0.0), "in"), Key(51, TOPPLE, "lin"), Key(54, DOWN, "in"),
            Key(57, dict(DOWN, hips=(0.0, -0.10, -0.45)), "out"), Key(n, DOWN, "sine")]
    # el empujón lo lleva 0.8 m atrás: los pies retroceden con él y quedan de punta para las rodillas apoyadas
    feet = {"r": [FR(0), FR(3), FR(11, -0.70, ease="out"), FR(16, -0.70), FR(24, -1.60, yaw=0.0, pitch=60.0)],
            "l": [FL(0), FL(5, pitch=10.0), FL(14, -0.75, ease="out"), FL(18, -0.75), FL(25, -1.30, yaw=0.0, pitch=60.0)]}
    return T.TeamClip("Death", n, keys, travel=slide, feet=feet, notes="muerte: se ataja con el martillo clavado, de rodillas, se desploma",
                      timing=dict(sheet=[4, 12, 24, 32, 44, 51, 54, 60], slide_ok=6.0,
                                  # se desploma: el martillo se vence solo y los brazos sueltos caen con el cuerpo
                                  swing_ok=[[48, 56]]))


# ================================================================== fase 2: la derrota falsa y la armadura
# Lo que viene de la falsa derrota (último cuadro) y lo que arranca ArmorRise (cuadro 0): Gorō boca arriba, los brazos
# abiertos en el piso con las palmas abajo, las piernas estiradas y el martillo acostado a su derecha con el mango hacia
# su mano. Los dos clips comparten esta pose exacta (el juego los encadena sin cruce y la pausa de silencio la pone
# GoroBoss entre los dos).
# el martillo cayó para atrás girando sobre la cabeza, que quedó donde estaba clavada, adelante a su derecha (de canto:
# centro a 0.57 m, las esquinas del octógono y los zunchos llegan a 0.56; las caras mirando a los costados, como estaba
# clavado: así cae sin girar la cabeza), con el mango acostado a lo largo del brazo derecho; la derecha abierta apoyada en
# el mango, 0.8 m más arriba de la punta (desde ahí lo agarra en ArmorRise)
SUPINE_HEAD = Vector((-1.68, -0.75, 0.57))
SUPINE_HAFT = Vector((0.0, -0.995, 0.10)).normalized()      # de la mano hacia la cabeza
SUPINE_SR = 0.80
SUPINE_HAND = SUPINE_HEAD - SUPINE_HAFT * (HEAD_C - GRIP_R + SUPINE_SR)


def supine(breath=0.0, **kw):
    """Boca arriba (ver arriba). La cadera a 0.37 m del piso y el cuerpo acostado hacia atrás; la cabeza levantada del
    piso lo justo para que el casco no se meta; los pies de talón con la punta arriba ('feet' de cada clip)."""
    p = P(hips=(0.0, 0.42, -0.73), hips_rot=(-84.0, 0.0, 4.0), spine=(-2.0, 0.0, 0.0), head=(18.0, 0.0, 10.0), breath=breath,
          knee_r=(-0.2, -1.0, 0.4), knee_l=(0.2, -1.0, 0.4), grip_l=0.0, drop_r=1.0, grip_r=0.2, fist_r=0.35, fist_l=0.35,
          hand_r=tuple(SUPINE_HAND + Vector((0.0, 0.0, 0.10))), hand_r_dir=(-0.4, 0.6, -0.15), hand_r_palm=(0.0, 0.0, -1.0),
          elbow_r=(-1.0, 0.5, 0.3), hand_l=(1.32, 0.95, 0.38), hand_l_dir=(0.6, 0.6, -0.15), hand_l_palm=(0.0, 0.0, -1.0),
          elbow_l=(1.0, 0.5, 0.3), face=(1.0, 0.0, 0.0), **club(tuple(SUPINE_HEAD), tuple(SUPINE_HAFT), sr=SUPINE_SR))
    p.update(kw)
    return p


# los pies boca arriba: de talón, la punta arriba, adelante de la cadera
SUPINE_FEET = {"r": (-0.50, -0.62, -12.0), "l": (0.50, -0.58, 14.0)}


# el martillo clavado de la derrota falsa y de ArmorRise: la cabeza adelante a su derecha con las caras a los costados
# (así, cuando se vence para atrás cae sin girar la cabeza: es la de SUPINE_HEAD), 1.68 m afuera: más adentro, de
# rodilla en ArmorRise, la canillera nueva (0.45 m) se metía en la cabeza del martillo
FD_HW = Vector((-1.68, -0.75, 0.58))
FD_DOWN = (0.04, 0.02, -1.0)
FD_FACE = (1.0, 0.0, 0.0)


def kneel_pose():
    """Sobre la rodilla derecha, inclinado hacia el martillo clavado (adelante y a la derecha) y apoyado en el mango."""
    return P(hips=(0.0, 0.18, -0.52), hips_rot=(10.0, -8.0, 6.0), spine=(16.0, -10.0, 0.0), head=(28.0, 6.0, 0.0), breath=0.0,
             knee_r=(-0.3, -1.0, -0.3), knee_l=(0.4, -1.0, 0.0), face=FD_FACE, grip_l=0.0, elbow_r=(-1.0, 0.4, -0.2),
             hand_l=(0.62, -0.42, 0.98), hand_l_dir=(0.0, -0.3, -0.95), hand_l_palm=(-1.0, 0.0, 0.0), fist_l=0.3,
             **planted(FD_HW, FD_DOWN, -0.62, 0.0))


def fake_defeat():
    """Derrota falsa (2.6 s, sin armadura): la primera barra de vida se vació y se tiene que creer que ganaste. El golpe lo
    echa atrás, trastabilla, clava el martillo de cabeza en el piso y cae sobre la rodilla derecha agarrado del mango,
    con la cabeza gacha, jadeando (dos respiraciones grandes y un intento de pararse que no le sale). La mano se le
    resbala, el martillo se vence para atrás solo (pivotea sobre la cabeza clavada y el mango cae junto a su brazo), se
    sienta para atrás y se desploma de espaldas en 10 cuadros, acelerando como un cuerpo que cae (la cabeza baja 1.3 m:
    antes caía 91 cm en un cuadro); rebota 2-3 cm, los brazos sueltos rebotan después del cuerpo y queda boca arriba,
    quieto (la pose de arranque de ArmorRise). Eventos: 'knee' (la rodilla pega el piso), 'drop' (suelta el martillo),
    'hammer_land' (el mango pega el piso: lo mide goro_checks en la malla), 'back_hit' (la espalda pega: polvo y
    sacudón), 'still'."""
    n = 78
    HW, down, face = FD_HW, FD_DOWN, FD_FACE
    HIT = P(hips=(0.0, 0.14, -0.12), hips_rot=(-12.0, 0.0, -6.0), spine=(-12.0, 0.0, 4.0), head=(20.0, 0.0, -8.0),
            **aim((-0.95, -0.40, 1.42), IDLE_HEAD + Vector((-0.05, 0.10, 0.20))))
    CATCH = P(hips=(0.0, 0.16, -0.22), hips_rot=(4.0, 0.0, 6.0), spine=(6.0, 0.0, 0.0), head=(18.0, 0.0, 4.0), face=face,
              grip_r=0.3, fist_r=0.75, elbow_r=(-1.0, 0.4, -0.3), **planted(HW, down, -0.20, 0.0))
    KNEEL = kneel_pose()
    PUSH = dict(KNEEL, hips=(0.0, 0.14, -0.38), spine=(6.0, 0.0, 0.0), head=(10.0, 0.0, 0.0), breath=1.0,
                **planted(HW, down, -0.50, 0.0))
    SLIP = dict(KNEEL, hips=(0.0, 0.24, -0.58), hips_rot=(-10.0, 0.0, 4.0), spine=(0.0, 0.0, 0.0), head=(14.0, 0.0, 6.0),
                drop_r=0.0, grip_r=0.4, fist_r=0.5, hand_r=(-1.20, -0.20, 1.05), hand_r_dir=(-0.2, -0.6, -0.75),
                hand_r_palm=(-1.0, 0.0, 0.0),
                hand_l=(0.80, 0.10, 1.00), face=face, **planted(HW, (0.0, -0.32, -0.95), -0.62, 0.0))
    # se sienta para atrás: la cola al piso entre los talones, el torso todavía arriba, los brazos que se abren
    SIT = P(hips=(0.0, 0.40, -0.47), hips_rot=(-30.0, 0.0, 4.0), spine=(-6.0, 0.0, 0.0), head=(24.0, 0.0, 8.0),
            knee_r=(-0.3, -1.0, 0.5), knee_l=(0.3, -1.0, 0.5), grip_l=0.0, drop_r=1.0, grip_r=0.2, fist_r=0.4, fist_l=0.4,
            hand_r=(-1.10, 0.35, 0.95), hand_r_dir=(-0.6, 0.3, -0.7), hand_r_palm=(-0.3, 0.6, -0.4),
            hand_l=(1.10, 0.40, 0.95), hand_l_dir=(0.6, 0.3, -0.7), hand_l_palm=(0.3, 0.6, -0.4),
            elbow_r=(-1.0, 0.5, 0.2), elbow_l=(1.0, 0.5, 0.2),
            face=face, **club(tuple(SUPINE_HEAD), (0.0, -0.62, -0.78), sr=SUPINE_SR))
    LIE = supine()
    # la caída de espaldas: el cuerpo de SIT a LIE acelerando (fracciones por cuadro 0.05 -> 0.14) y el martillo, suelto,
    # con su propio tiempo: pivotea sobre la cabeza clavada y el mango llega al piso un cuadro antes que la espalda
    land = 60

    def falling(u, hu, dz=0.0):
        q = mix(SIT, LIE, u)
        q["hips"] = (q["hips"][0], q["hips"][1], q["hips"][2] + dz)
        q.update(club(tuple(SUPINE_HEAD), tuple(Vector(SIT["haft"]).normalized().slerp(SUPINE_HAFT, hu)), sr=SUPINE_SR))
        return q
    # rebota: la cadera y la cabeza suben 2-3 cm y los brazos, sueltos, rebotan un poco después del cuerpo
    BOUNCE = supine(hips=(0.0, 0.42, -0.705), head=(20.5, 0.0, 10.0))
    FLOP = supine(hand_r=tuple(SUPINE_HAND + Vector((0.0, 0.02, 0.16))), hand_l=(1.32, 0.97, 0.44))
    keys = [Key(0, P(grip_r=1.0, fist_r=1.0)), Key(3, HIT, "snap"), Key(6, dict(tween(HIT, CATCH, 0.5, 0.30, hand=(-0.20, 0.0, -0.10),
                                                                              head=(-0.40, 0.0, 0.0)), grip_r=0.3, fist_r=0.75), "lin"),
            Key(9, CATCH, "out"), Key(16, dict(KNEEL, grip_r=1.0, fist_r=1.0), "in2"), Key(18, dict(KNEEL, hips=(0.0, 0.18, -0.49)), "out"),
            Key(22, dict(KNEEL, breath=1.0, spine=(10.0, 0.0, 0.0)), "sine"), Key(27, dict(KNEEL, breath=0.0), "sine"),
            Key(31, PUSH, "inout"), Key(35, dict(KNEEL, breath=0.6), "inout"), Key(39, KNEEL, "sine"),
            Key(43, SLIP, "inout"), Key(45, dict(tween(SLIP, SIT, 0.4, 0.45), drop_r=1.0, hand_r=(-1.35, 0.30, 0.90)), "in"),
            Key(47, tween(SLIP, SIT, 0.8, 0.30), "lin"), Key(48, SIT, "lin"),
            Key(51, falling(0.15, 0.10, 0.05), "lin"), Key(54, falling(0.40, 0.36, 0.08), "lin"), Key(56, falling(0.58, 0.62, 0.07), "lin"),
            Key(57.5, falling(0.74, 0.86, 0.05), "lin"), Key(land - 1, falling(0.88, 1.0, 0.02), "lin"), Key(land, LIE, "lin"),
            Key(land + 2, BOUNCE, "out"), Key(land + 4, dict(LIE, hand_r=FLOP["hand_r"], hand_l=FLOP["hand_l"]), "in"),
            Key(land + 7, LIE, "sine"), Key(land + 10, dict(LIE, hips=(0.0, 0.42, -0.725)), "sine"), Key(land + 13, LIE, "sine"),
            Key(n, LIE, "sine")]
    rx, ry, ryaw = SUPINE_FEET["r"]
    lx, ly, lyaw = SUPINE_FEET["l"]
    # el izquierdo da un paso corto atrás con el sacudón (clavado patinaba 6 cm: la pierna no llegaba)
    feet = {"r": [FR(0), FR(3), FR(8, -0.30, ease="out"), FR(12, -0.30), FR(16, -0.75, yaw=0.0, pitch=58.0), FR(39, -0.75, yaw=0.0, pitch=58.0),
                  FR(48, -0.35, yaw=-8.0, pitch=0.0), T.FootKey(land, rx, ry, ryaw, -72.0), T.FootKey(n, rx, ry, ryaw, -72.0)],
            "l": [FL(0), FL(2), FL(7, -0.12, ease="out", lift=0.07), FL(10, -0.12), FL(16, 0.05), FL(39, 0.05),
                  FL(48, -0.05, pitch=-30.0), T.FootKey(land, lx, ly, lyaw, -72.0), T.FootKey(n, lx, ly, lyaw, -72.0)]}
    return T.TeamClip("FakeDefeat", n, keys, feet=feet, tremble=0.0, notes="derrota falsa: de rodilla agarrado del martillo y cae de espaldas",
                      timing=dict(sheet=[3, 9, 16, 31, 43, 48, 51, 54, 56, land, land + 2, 78], slide_ok=4.0,
                                  # el martillo que se vence solo y cae: gira rápido al final de la caída
                                  swing_ok=[[44, land]],
                                  events={"knee": 16, "drop": 43, "hammer_land": land - 1, "back_hit": land, "still": land + 13}))


def add(a, d):
    """Pose 'a' con los canales de 'd' sumados (giros y desplazamientos); los que 'a' no tiene salen de STANCE."""
    out = dict(a)
    for k, v in d.items():
        base = a.get(k, STANCE.get(k))
        out[k] = tuple(x + y for x, y in zip(base, v)) if isinstance(v, tuple) else base + v
    return out


def armor_rise():
    """La armadura (7 s, desde la pose final de FakeDefeat): boca arriba y quieto, la montaña se le pega encima pieza por
    pieza, en el orden de goro_armor.PIECES, y cada roca que se clava lo sacude donde pega: las de las piernas le patean
    la pierna (el pie salta 14-16 cm y la rodilla se dobla), las del pecho le hunden el pecho y le levantan de golpe la
    cabeza y los hombros, las de los antebrazos le hunden la mano; cada sacudón se asienta en 6 cuadros. Vuelve a
    respirar hondo, aprieta los puños y agarra el mango. Se quiere sentar tirando del martillo y no puede: el martillo se
    le levanta a medias, se le vence y vuelve a caer de espaldas; a la segunda empuja el piso con la izquierda, carga el
    peso sobre ese lado y tira del mango hasta sentarse (20 cuadros, la cabeza llega última). El martillo queda parado
    con la cabeza clavada donde estaba (la misma de FakeDefeat). Rueda a la rodilla agarrado del mango: las hombreras lo
    aplastan (se le doblan los brazos) y empuja; se para encorvado y las cumbres de la espalda lo doblan hacia adelante;
    se endereza de a poco, arranca el martillo del piso, los cuernos de la corona le sacuden la cabeza y ruge con el
    martillo en alto y el brazo abierto. Termina en la guardia.

    timing['armor_from']: cuadro en que cada pieza queda puesta (goro_checks mide desde ahí la armadura); 'events' trae
    'slam_<Pieza>' (el cuadro del golpe: polvo, sacudón y sonido; la roca sale 'flight' s antes, ver Kit_goro_armor.json),
    'breath', 'grab', 'sit', 'kneel', 'stand', 'pull' (el martillo sale del piso), 'roar' y 'roar_peak'."""
    import goro_armor as GA
    n = 210
    slams = {p["name"]: p["slam"] for p in GA.PIECES}
    face = FD_FACE
    LIE = supine()
    BREATH = supine(breath=1.0, hips=(0.0, 0.42, -0.71), spine=(-5.0, 0.0, 0.0), head=(14.0, 0.0, 6.0))
    # agarra el mango donde tenía la mano: la derecha se cierra sobre él
    GRAB = supine(breath=0.4, drop_r=0.0, grip_r=1.0, fist_r=1.0, fist_l=1.0, head=(24.0, -6.0, 14.0))
    # el pecho lo arquea: la cadera se levanta del piso, la cabeza para atrás
    ARCH = supine(breath=1.0, drop_r=0.0, grip_r=1.0, fist_r=1.0, fist_l=1.0, hips=(0.0, 0.42, -0.62), spine=(-14.0, 0.0, 0.0),
                  head=(-10.0, 0.0, 0.0))
    # sentado tirando del martillo, que se para sobre la cabeza clavada adelante a su derecha
    SITUP = P(hips=(0.0, 0.40, -0.36), hips_rot=(-14.0, -6.0, 6.0), spine=(16.0, -8.0, 0.0), head=(16.0, 4.0, 0.0), breath=1.0,
              knee_r=(-0.3, -1.0, 0.5), knee_l=(0.3, -1.0, 0.5), grip_l=0.0, fist_l=1.0, elbow_r=(-1.0, 0.3, -0.2),
              hand_l=(0.95, 0.30, 0.45), hand_l_dir=(0.45, -0.35, -0.25), hand_l_palm=(0.0, 0.0, -1.0), elbow_l=(1.0, 0.5, 0.2),
              face=face, **planted(FD_HW, (0.0, -0.40, -0.92), -0.10, 0.0))
    KNEEL = kneel_pose()
    SAG = add(KNEEL, dict(hips=(0.0, 0.0, 0.02), spine=(8.0, 0.0, 0.0), head=(10.0, 0.0, 0.0)))
    PUSH = dict(kneel_pose(), hips=(0.0, 0.14, -0.36), spine=(8.0, -6.0, 0.0), head=(6.0, 0.0, 0.0), breath=1.0,
                **planted(FD_HW, FD_DOWN, -0.45, 0.0))
    # parado encorvado, todavía agarrado del mango clavado: las cumbres de la espalda lo doblan adelante
    HUNCH = P(hips=(0.0, 0.10, -0.22), hips_rot=(18.0, -4.0, 6.0), spine=(18.0, -6.0, 0.0), head=(20.0, 4.0, 0.0), breath=0.6,
              grip_l=0.0, fist_l=1.0, hand_l=(0.70, -0.30, 1.20), hand_l_dir=(0.1, -0.3, -0.95), hand_l_palm=(-1.0, 0.0, 0.0),
              elbow_l=(1.0, 0.3, -0.3), elbow_r=(-1.0, 0.4, -0.3), face=face, **planted(FD_HW, FD_DOWN, -0.30, 0.0))
    UPRIGHT = dict(HUNCH, hips=(0.0, 0.04, -0.14), hips_rot=(2.0, -2.0, 6.0), spine=(-4.0, -2.0, 0.0), head=(-4.0, 0.0, 0.0),
                   breath=1.0, **planted(FD_HW, FD_DOWN, -0.18, 0.0))
    # arranca el martillo del piso y lo levanta parado a la derecha (la cola baja por fuera del muslo, como en Spotted)
    # el martillo sale del piso girando sobre la mano: la cabeza sube por delante (a la altura de la mano, adelante) y
    # después arriba; derecho de abajo a arriba la cabeza pasaba por la mano y la cola se hundía en el piso
    SWING = P(hips=(0.0, 0.04, -0.16), hips_rot=(6.0, 0.0, 6.0), spine=(4.0, 0.0, 0.0), head=(-8.0, 0.0, 0.0), grip_l=0.0, fist_l=1.0,
              face=(1.0, 0.0, 0.0), elbow_r=(-1.0, 0.1, -0.4), **aim((-1.27, -0.70, 1.65), (-1.50, -2.15, 1.80)))
    SWING["slide_r"] = round((Vector((-1.50, -2.15, 1.80)) - Vector((-1.27, -0.70, 1.65))).length - (HEAD_C - GRIP_R), 3)
    PULL = P(hips=(0.0, 0.04, -0.16), hips_rot=(4.0, 0.0, 6.0), spine=(0.0, 0.0, 0.0), head=(-6.0, 0.0, 0.0), grip_l=0.0, fist_l=1.0,
             face=(1.0, 0.0, 0.0), elbow_r=(-1.0, 0.0, -0.3), **aim((-1.32, -0.55, 1.75), (-1.62, -1.00, 3.20)))
    PULL["slide_r"] = round((Vector((-1.62, -1.00, 3.20)) - Vector((-1.32, -0.55, 1.75))).length - (HEAD_C - GRIP_R), 3)
    ROAR = P(hips=(0.0, 0.04, -0.08), hips_rot=(-8.0, 0.0, 0.0), spine=(-18.0, 0.0, 0.0), head=(22.0, 0.0, 0.0), breath=1.0,
             face=(0.0, -1.0, 0.1), grip_l=0.0, elbow_r=(-1.0, 0.0, -0.2),
             hand_l=(1.15, -0.20, 2.15), hand_l_dir=(0.6, -0.1, 0.8), hand_l_palm=(0.0, -1.0, 0.0), fist_l=1.0, elbow_l=(1.0, 0.0, -0.4),
             **aim((-1.36, -0.18, 2.62), (-1.64, -0.24, 4.09)))
    # el primer intento: tira del mango, el martillo se levanta a medias, la izquierda empuja el piso y la cabeza todavía
    # atrás (llega última); no le alcanza y vuelve a caer. El segundo carga el peso sobre la izquierda y tira hasta sentarse
    push_l = dict(hand_l=(0.98, 0.60, 0.33), hand_l_dir=(0.40, 0.60, -0.55), hand_l_palm=(0.0, 0.0, -1.0), elbow_l=(1.0, 0.4, 0.9))
    TRY = dict(tween(GRAB, SITUP, 0.32, 0.15), breath=1.0, head=(0.0, 0.0, 6.0), hips=(0.0, 0.42, -0.42), **push_l)
    FAIL = dict(tween(GRAB, SITUP, 0.12, 0.05), breath=0.3, head=(20.0, -4.0, 10.0), fist_l=0.6, hips=(0.0, 0.42, -0.66))
    HEAVE = dict(tween(GRAB, SITUP, 0.72, 0.22), breath=1.0, head=(4.0, 6.0, 4.0), hips=(0.0, 0.41, -0.40),
                 hips_rot=tween(GRAB, SITUP, 0.72)["hips_rot"][:1] + (-10.0, 6.0), spine=(12.0, -12.0, 0.0),
                 **dict(push_l, hand_l=(0.92, 0.48, 0.18), elbow_l=(1.0, 0.4, 0.3)))
    # la base: dónde está el cuerpo en cada momento; los golpes de las rocas se suman encima
    base = [(0, LIE), (16, LIE), (62, BREATH), (68, LIE), (82, dict(LIE, fist_r=0.6, fist_l=1.0)), (86, GRAB), (96, GRAB),
            (102, ARCH), (106, TRY, 0.25), (110, FAIL, 0.25), (114, HEAVE, 0.55, (0.0, 0.0, 0.35)), (118, SITUP, 0.30, (0.0, 0.0, 0.10)), (126, KNEEL), (132, SAG), (140, PUSH),
            (148, HUNCH), (158, HUNCH), (168, UPRIGHT), (172, SWING), (177, PULL), (184, ROAR), (200, ROAR), (n, P(grip_r=1.0, fist_r=1.0))]

    def at(f):
        """La base en el cuadro f; un tercer valor en la entrada de llegada levanta la cabeza del martillo en el medio
        (el martillo que se para girando sobre la cabeza apoyada: las esquinas del octógono raspaban el piso)."""
        for e0, e1 in zip(base, base[1:]):
            (f0, a), (f1, b) = e0[:2], e1[:2]
            if f0 <= f <= f1:
                u = 0.0 if f1 == f0 else (f - f0) / (f1 - f0)
                u = u * u * (3.0 - 2.0 * u)
                arc = e1[2] if len(e1) > 2 else 0.0
                # (y la mano un poco más arriba en el medio: al pararse el martillo, la cola rozaba el piso)
                hand = e1[3] if len(e1) > 3 else (0.0, 0.0, 0.0)
                return tween(a, b, u, arc, hand=hand) if a.get("drop_r", 0.0) < 0.5 and b.get("drop_r", 0.0) < 0.5 else mix(a, b, u)
        return base[-1][1]

    # cómo sacude a Gorō cada roca que se le clava (lo que se suma 2 cuadros después del golpe y se asienta en 6 más):
    # las de las piernas además patean el pie (abajo, en 'feet'); las del pecho le hunden el pecho y le levantan la cabeza
    # y los hombros (la cadera ya apoyada en el piso no puede bajar: rebota 2 cm)
    JOLT = {"Greave": dict(hips=(0.0, 0.0, -0.015), head=(-8.0, 0.0, 0.0)), "Knee": dict(hips=(0.0, 0.0, -0.02), head=(-8.0, 0.0, 0.0)),
            "Tasset": dict(hips=(0.0, 0.0, 0.015), hips_rot=(4.0, 0.0, 0.0), head=(-10.0, 0.0, 0.0)),
            "Bracer_R": dict(spine=(-4.0, 0.0, 0.0), head=(-8.0, 0.0, 0.0), hand_r=(0.0, 0.0, -0.06)),
            "Bracer_L": dict(spine=(-4.0, 0.0, 0.0), head=(-8.0, 0.0, 0.0), hand_l=(0.0, 0.0, -0.06)),
            "Chest": dict(spine=(12.0, 0.0, 0.0), head=(16.0, 0.0, 0.0), hips=(0.0, 0.0, 0.035)),
            "Pauldron": dict(hips=(0.0, 0.0, -0.06), spine=(10.0, 0.0, 0.0), head=(14.0, 0.0, 0.0)),
            "Ridge": dict(hips=(0.0, 0.0, -0.05), hips_rot=(6.0, 0.0, 0.0), spine=(12.0, 0.0, 0.0), head=(10.0, 0.0, 0.0)),
            "Horn": dict(head=(-16.0, 0.0, 0.0), spine=(-4.0, 0.0, 0.0))}
    marks = {}
    for e in base:
        marks[e[0]] = None
    # el sentarse con claves cada 2 cuadros: entre claves los canales se interpolan sueltos y el martillo que se para
    # (girando sobre la cabeza apoyada) raspaba el piso con las esquinas
    for g in range(98, 126, 2):
        marks.setdefault(g, None)
    for name, f in slams.items():
        j = dict(JOLT[name] if name in JOLT else JOLT[name.split("_")[0]])
        for g, k in ((f, 0.0), (f + 2, 1.0), (f + 8, 0.0)):
            marks[g] = (j, k) if k > 0.0 else marks.get(g)
    keys = []
    for g in sorted(marks):
        if g > n:
            continue
        pose = at(g)
        jk = marks[g]
        if jk is not None:
            j, k = jk
            pose = add(pose, {c: tuple(x * k for x in v) if isinstance(v, tuple) else v * k for c, v in j.items()})
        keys.append(Key(g, pose, "sine" if jk is None else "out"))
    rx, ry, ryaw = SUPINE_FEET["r"]
    lx, ly, lyaw = SUPINE_FEET["l"]
    sup = {"r": (rx, ry, ryaw), "l": (lx, ly, lyaw)}
    # las rocas de las piernas patean el pie de ese lado: el talón salta (z) y la punta se va para atrás, y vuelve
    kicks = {"r": [], "l": []}
    for name, f in slams.items():
        part, side = name.split("_")
        lift = {"Greave": 0.14, "Knee": 0.16, "Tasset": 0.08}.get(part)
        if lift is None or f > 96:
            continue
        x, y, yaw = sup[side.lower()]
        kicks[side.lower()] += [T.FootKey(f, x, y, yaw, -72.0), T.FootKey(f + 2, x, y + 0.04, yaw, -58.0, lift, 0.0, "out"),
                                T.FootKey(f + 8, x, y, yaw, -72.0, 0.0, 0.0, "inout")]

    def track(k, rest):
        x, y, yaw = sup[k]
        out = [T.FootKey(0, x, y, yaw, -72.0)] + sorted(kicks[k], key=lambda q: q.frame) + [T.FootKey(104, x, y, yaw, -72.0)]
        return out + rest
    # al sentarse recoge las piernas (el segundo intento) y de ahí a la rodilla
    feet = {"r": track("r", [FR(118, -0.35, yaw=-8.0), FR(126, -0.75, yaw=0.0, pitch=58.0), FR(140, -0.75, yaw=0.0, pitch=58.0),
                             FR(148, 0.0, dx=0.12), FR(168, 0.0, dx=0.12), FR(n)]),
            "l": track("l", [FL(118, pitch=-10.0), FL(126), FL(n)])}
    ev = {"slam_" + k: v for k, v in slams.items()}
    ev.update(breath=62, grab=86, sit=118, kneel=126, stand=148, pull=170, roar=184, roar_peak=190)
    return T.TeamClip("ArmorRise", n, keys, feet=feet, tremble=0.0,
                      notes="la armadura: las rocas se le clavan de a una, se levanta agarrado del martillo y ruge",
                      timing=dict(sheet=[0, 26, 46, 62, 102, 106, 110, 114, 118, 126, 140, 152, 168, 184, 210], slide_ok=4.0,
                                  armor_from=dict(slams), events=ev))


# ================================================================== fase 2: los golpes con la armadura
# Variaciones más pesadas de los golpes de siempre, autoradas y medidas con la armadura puesta (timing['armored']). Cada
# una lleva 'armor_window' (del aviso al golpe: la armadura brilla y el golpe no se interrumpe, GoroBoss decide si además
# baja el daño que recibe) y 'punish' (la vuelta: queda clavado y es cuando se lo castiga).
def key_poses(clip):
    """{cuadro: pose} de las claves de un clip ya armado (para variar un golpe sin copiar sus poses)."""
    return {k.frame: k.ctrl for k in clip.keys}


def combo1b():
    """Martillazo retardado (fase 2, desviable): arma el martillo sobre el hombro derecho como Combo1 y AMAGA: arranca la
    bajada de verdad (f12-f16: la cabeza del martillo viaja 1.6 m hacia Kaito acelerando, la cadera gira 20° y el pie de
    adelante carga), la frena en seco a ~45° del arco con dos cuadros de rebote y lo vuelve a armar más alto y más torcido
    (f18-f26): el golpe sale 0.6 s más tarde de lo que el ojo espera. Pega con un paso más largo (1.4 m) y la cabeza se
    clava a 3.8 m. El amague está antes de la pausa del aviso: el anillo se cierra con el golpe de verdad."""
    c1 = key_poses(combo1())
    n, apex, contact = 54, 32, 35
    lunge, windup = 1.4, 1.2
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=windup)
    TELL, SMEAR, CONTACT, FOLLOW, PUNISH = c1[12], c1[22], c1[24], c1[26], c1[30]
    # el amague: la bajada arranca como la de verdad y se clava en seco; 'OVER' es el rebote del frenazo (se pasa un poco)
    FEINT = dict(tween(TELL, SMEAR, 0.50, 0.35, hand=(-0.30, 0.05, 0.0)), hips=(0.02, -0.02, -0.22), hips_rot=(8.0, 0.0, -14.0), spine=(2.0, 0.0, -6.0),
                 head=(-10.0, 0.0, 20.0))
    OVER = dict(tween(TELL, SMEAR, 0.56, 0.35, hand=(-0.30, 0.05, 0.0)), hips=(0.02, -0.04, -0.23), hips_rot=(9.0, 0.0, -12.0), spine=(3.0, 0.0, -5.0),
                head=(-11.0, 0.0, 18.0))
    BACK = dict(tween(TELL, SMEAR, 0.40, 0.30, hand=(-0.25, 0.05, 0.0)), hips=(0.03, 0.02, -0.21), hips_rot=(6.0, 0.0, -18.0), spine=(0.0, 0.0, -8.0))
    RECOCK = dict(TELL, hips=(0.06, 0.15, -0.16), hips_rot=(-2.0, 0.0, -42.0), spine=(-10.0, 0.0, -14.0), head=(-6.0, 0.0, 34.0),
                  **club((-2.00, 1.25, 4.30), (-0.44, 0.56, 0.70), sr=SR, sl=SL))
    HOLD = dict(RECOCK, hips=(0.06, 0.16, -0.18), **club((-2.04, 1.30, 4.28), (-0.45, 0.57, 0.69), sr=SR, sl=SL))
    HIT = dict(CONTACT, hips=(0.0, -0.02, -0.42))
    SWEEP = sweep_pose()
    keys = [Key(0, P()), Key(3, c1[3], "inout"), Key(5, c1[5], "inout"), Key(7, c1[7], "inout"), Key(12, TELL, "inout"),
            Key(16, FEINT, "in"), Key(17, OVER, "out"), Key(18.5, BACK, "inout"), Key(26, RECOCK, "inout"), Key(apex, HOLD, "sine"),
            Key(33, SMEAR, "in"), Key(contact, HIT, "lin"), Key(37, dict(FOLLOW, hips=(0.0, -0.03, -0.45)), "out"),
            Key(41, dict(PUNISH, grip_r=1.0, fist_r=1.0), "out"),
            Key(44, dict(recover(PUNISH, SWEEP), grip_r=0.15, fist_r=0.7), "sine"), Key(48, dict(SWEEP, grip_r=0.1, fist_r=0.7), "sine"),
            Key(51, dict(tween(SWEEP, P(), 0.6, 0.18), grip_r=0.5, fist_r=0.85), "sine"), Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    # el pie de adelante carga en el amague (el talón baja, el peso adelante) y vuelve
    feet = {"r": [FR(0), FR(apex), FR(38, lunge, pitch=-10.0), FR(40, lunge)],
            "l": [FL(0), FL(12), FL(16, pitch=-8.0), FL(20), FL(apex, pitch=16.0), FL(43, lunge, ease="out")]}
    return T.TeamClip("Combo1B", n, keys, travel=tr, feet=feet, notes="fase 2: martillazo en diagonal con amague; el golpe sale tarde",
                      timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, 39], hold=[26, apex], lunge=lunge,
                                  windup=windup, state="Combo1B", reach=2.6, feint=[12, 20], armor_window=[6, 37], punish=[41, n],
                                  # el amague arranca y frena como un golpe de verdad
                                  swing_ok=[[12, 19]]))


def combo2b():
    """Barrido bajo (fase 2, desviable): agachado y torcido a la izquierda, la cabeza del martillo apoyada en el piso a
    3 m a su izquierda (desde arriba: el martillo sale del contorno por la izquierda y abajo, nada que ver con el revés de
    Combo2 a la altura de la cadera). Barre de izquierda a derecha a ras del piso, a la altura de los tobillos de Kaito, y
    la cabeza termina en el piso a la derecha. 1.53 s."""
    c2 = key_poses(combo2())
    n, apex, contact = 46, 18, 22
    lunge, windup = 1.0, 0.7
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=windup)
    GATHER = c2[5.5]
    hand = Vector((0.55, -0.75, 1.28))
    d = Vector((2.20, 0.15, -0.59)).normalized()
    TELL = P2(hips=(0.05, 0.05, -0.36), hips_rot=(10.0, 0.0, 36.0), spine=(8.0, 0.0, 14.0), head=(-10.0, 0.0, -30.0),
              knee_r=(-0.7, -0.9, 0.0), knee_l=(0.7, -0.9, 0.0), face=flat_face(tuple(d), (0.0, -1.0, 0.0)),
              elbow_r=(-0.4, -0.8, -0.4), elbow_l=(1.0, 0.4, -0.3),
              **club(tuple(hand + d * (HEAD_C - GRIP_R + SR)), tuple(d), sr=SR, sl=SL))
    HOLD = dict(TELL, hips=(0.05, 0.06, -0.38))
    SMEAR = P2(hips=(0.02, -0.02, -0.34), hips_rot=(12.0, 0.0, 12.0), spine=(10.0, 0.0, 4.0), head=(-12.0, 0.0, -8.0),
               face=(-0.85, -0.52, 0.0), elbow_r=(-1.0, 0.0, -0.4), elbow_l=(0.8, 0.5, -0.4),
               **club((1.55, -2.97, 0.64), (0.55, -0.80, -0.24), sr=SR, sl=SL))
    CONTACT = P2(hips=(0.0, -0.06, -0.34), hips_rot=(12.0, 0.0, -12.0), spine=(10.0, 0.0, -14.0), head=(-12.0, 0.0, 10.0),
                 face=(-1.0, 0.0, 0.0), elbow_r=(-1.0, 0.0, -0.4), elbow_l=(0.8, 0.5, -0.4),
                 **club((-0.30, -3.68, 0.64), (-0.05, -0.97, -0.23), sr=SR, sl=SL))
    FOLLOW = P2(hips=(0.0, -0.05, -0.32), hips_rot=(12.0, 0.0, -30.0), spine=(10.0, 0.0, -22.0), head=(-10.0, 0.0, 16.0),
                face=(0.40, -0.92, 0.0), elbow_r=(-1.0, 0.0, -0.4), elbow_l=(0.8, 0.5, -0.4),
                **club((-2.85, -2.00, 0.68), (-0.80, -0.55, -0.22), sr=SR, sl=SL))
    PUNISH = dict(FOLLOW, hips=(0.0, -0.05, -0.30), face=flat_face((-0.86, -0.42, -0.28), (1.0, 0.0, 0.0)),
                  **club((-2.95, -1.75, 0.56), (-0.86, -0.42, -0.28), sr=SR, sl=SL))
    TURN = c2[34]
    keys = [Key(0, P(grip_r=1.0, fist_r=1.0)), Key(2, dict(lift(mix(P(), GATHER, 0.3), 0.10), grip_r=0.3, fist_r=0.8), "in"),
            Key(4, dict(lift(mix(P(), GATHER, 0.75), 0.10), grip_r=0.3, fist_r=0.8), "lin"), Key(6, dict(GATHER, grip_r=1.0, fist_r=1.0), "out"),
            Key(8, tween(GATHER, TELL, 0.5, 0.30, hand=(0.05, -0.18, 0.0)), "inout"), Key(10, TELL, "inout"), Key(apex, HOLD, "sine"), Key(20, SMEAR, "in"), Key(contact, CONTACT, "lin"),
            Key(25, FOLLOW, "out"), Key(29, dict(PUNISH, grip_r=1.0, fist_r=1.0), "out"), Key(33, tween(PUNISH, TURN, 0.5, 0.10, hand=(-0.15, 0.0, -0.08)), "sine"),
            Key(37, TURN, "sine"), Key(41, dict(tween(TURN, P(), 0.6, 0.12), grip_r=0.5, fist_r=0.85), "sine"),
            Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    feet = {"r": [FR(0), FR(apex), FR(24, lunge, pitch=-10.0), FR(26, lunge)],
            "l": [FL(0), FL(10), FL(apex, pitch=14.0), FL(29, lunge, ease="out")]}
    return T.TeamClip("Combo2B", n, keys, travel=tr, feet=feet, notes="fase 2: barrido a ras del piso de izquierda a derecha",
                      timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, 26], hold=[10, apex], lunge=lunge,
                                  windup=windup, state="Combo2B", reach=2.8, armor_window=[4, 25], punish=[29, n]))


def combo3b():
    """Martillazo de arriba con bombeo (fase 2, desviable): lo levanta por encima de la cabeza como Combo3, lo baja hasta
    la cara como si pegara, lo vuelve a subir más alto con el pecho arqueado y recién ahí lo deja caer con un paso de
    1.5 m. 1.8 s. Arriba el mango va inclinado ~18° a su derecha con las manos delante del lado derecho de la cara: derecho,
    desde la cámara del juego partía el casco y la cara en dos durante toda la pausa (los cuernos y la boca no se
    leían)."""
    name, n, apex, contact, lunge, windup = "Combo3B", 54, 32, 35, 1.5, 1.2
    c3 = key_poses(combo3())
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=windup)
    SMEAR, CONTACT = c3[17], c3[19]
    TELL = dict(c3[9], hips_rot=(-8.0, 0.0, 10.0), spine=(-12.0, 0.0, 4.0), head=(6.0, 0.0, -6.0), face=(0.45, 0.55, -0.70),
                **club((-1.12, 1.11, 4.97), (-0.30, 0.57, 0.76), sr=SR, sl=-0.85))
    PUMP = dict(tween(TELL, SMEAR, 0.28), hips=(0.0, 0.08, -0.22), hips_rot=(4.0, 0.0, 8.0), spine=(-2.0, 0.0, 2.0), head=(-2.0, 0.0, -4.0))
    RISE = dict(TELL, hips=(0.0, 0.16, -0.06), hips_rot=(-10.0, 0.0, 12.0), spine=(-16.0, 0.0, 4.0), head=(8.0, 0.0, -8.0),
                **club((-1.05, 1.30, 5.03), (-0.27, 0.62, 0.74), sr=SR, sl=-0.85))
    HOLD = dict(RISE, hips=(0.0, 0.17, -0.07), **club((-1.07, 1.35, 5.00), (-0.27, 0.64, 0.72), sr=SR, sl=-0.85))
    HIT = dict(CONTACT, hips=(0.0, -0.05, -0.44), hips_rot=(16.0, 0.0, 4.0))
    SWEEP = sweep_pose()
    hold0 = apex - 6
    keys = [Key(0, P()), Key(3, c3[3], "inout"), Key(4.5, c3[4.5], "inout"), Key(6, c3[6], "lin"), Key(9, TELL, "sine"),
            Key(14, PUMP, "inout"), Key(hold0, RISE, "inout"), Key(apex, HOLD, "sine"), Key(apex + 1, SMEAR, "in"), Key(contact, HIT, "lin"),
            Key(contact + 2, dict(HIT, hips=(0.0, -0.05, -0.47)), "out"), Key(contact + 6, dict(HIT, grip_r=1.0, fist_r=1.0), "sine")]
    f = contact + 6
    keys += [Key(f + 3, dict(recover(HIT, SWEEP, 0.5), grip_r=0.15, fist_r=0.7), "sine"), Key(f + 7, dict(SWEEP, grip_r=0.1, fist_r=0.7), "sine"),
             Key(f + 10, dict(tween(SWEEP, P(), 0.6, 0.18), grip_r=0.5, fist_r=0.85), "sine"), Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    feet = {"r": [FR(0), FR(apex), FR(contact + 3, lunge, pitch=-10.0), FR(contact + 5, lunge)],
            "l": [FL(0), FL(8), FL(apex, pitch=14.0), FL(contact + 7, lunge, ease="out")]}
    return T.TeamClip(name, n, keys, travel=tr, feet=feet, notes="fase 2: martillazo de arriba con bombeo; el golpe sale tarde",
                      timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, contact + 3], hold=[hold0, apex], lunge=lunge,
                                  windup=windup, state=name, reach=3.0, pump=[9, hold0], armor_window=[5, contact + 2], punish=[f, n]))


def held(hand, d, sr):
    """El martillo con una mano en 'hand' (agarre 'sr' corrido hacia la cabeza) y el mango hacia 'd' (de la mano a la cabeza)."""
    d = Vector(d).normalized()
    return club(tuple(Vector(hand) + d * (HEAD_C - GRIP_R + sr)), tuple(d), sr=sr)


def slam_wave():
    """Onda de Kodoyama (fase 2, imparable): una silueta propia, que no se confunde con el martillazo de arriba desviable
    (Combo3B): se agacha hondo con las piernas abiertas en dos pisotones, suelta la izquierda (la mano adelante, abierta
    sobre la nieve) y ARRASTRA el martillo con la derecha, acostado en el piso a su derecha y un poco atrás, la cabeza a
    3.5 m (el aviso: lo que está en el piso es lo que va a salir por el piso; desde la cámara del juego el mango queda
    casi horizontal en la pantalla, el de Combo3B casi vertical). En la suelta lo sube por el costado derecho como un
    molino (por afuera de la hombrera), lo agarra con las dos arriba y lo clava adelante; después ara el piso 0.8 m: la
    onda sale en línea recta desde el golpe (eventos 'wave' en el contacto y 'plow_end'). 2.1 s; apex f24 (el fin del
    arrastre), contacto f34. Con la mano en la punta del mango y el arrastre girado 40° de la junta (no 60: el antebrazo
    daba media vuelta) y el codo con la misma pista que en la junta."""
    name, n, apex, contact, lunge, windup = "SlamWave", 64, 24, 34, 1.0, 1.25
    c3 = key_poses(combo3())
    # la suelta (el molino, 10 cuadros) va a 1.2x y no a 1.6x: así se lee el giro (AttackDef.releaseRate en GoroPhase2)
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=windup, release_rate=1.2)
    SMEAR, CONTACT = c3[17], c3[19]
    crouch = dict(hips=(0.0, 0.06, -0.46), hips_rot=(18.0, 0.0, -24.0), spine=(14.0, 0.0, -10.0), head=(-22.0, 0.0, 22.0),
                  knee_r=(-1.0, -0.6, 0.0), knee_l=(1.0, -0.6, 0.0), grip_l=0.0, grip_r=1.0, fist_r=1.0,
                  hand_l=(0.78, -0.80, 0.72), hand_l_dir=(0.2, -0.6, -0.75), hand_l_palm=(0.0, 0.0, -1.0), fist_l=0.3,
                  elbow_r=(-1.0, 0.4, -0.2), elbow_l=(1.0, -0.2, -0.3))
    # junta: la cabeza del martillo se arrastra por el piso hacia la derecha, la izquierda suelta
    GATHER = P(hips=(0.0, 0.03, -0.24), hips_rot=(10.0, 0.0, -12.0), spine=(8.0, 0.0, -6.0), head=(-12.0, 0.0, 12.0), grip_l=0.0,
               elbow_r=(-1.0, 0.3, -0.4), face=flat_face((-0.92, -0.30, -0.23), (0.0, 1.0, 0.0)), **held((-1.30, -0.45, 1.25), (-0.92, -0.30, -0.23), 1.55))
    COCK = P(face=flat_face((-0.86, 0.40, -0.14), (0.0, 1.0, 0.0)), **dict(crouch, elbow_r=(-1.0, 0.3, -0.4),
                                                                          **held((-1.32, 0.05, 1.04), (-0.86, 0.40, -0.14), 1.55)))
    HOLD = P(face=COCK["face"], **dict(crouch, hips=(0.0, 0.08, -0.49), spine=(16.0, 0.0, -10.0), elbow_r=(-1.0, 0.3, -0.4),
                                       **held((-1.34, 0.09, 1.03), (-0.86, 0.41, -0.13), 1.55)))
    # el molino por el costado derecho (afuera de la hombrera): la cabeza se despega del piso y sube atrás
    WIND1 = P(hips=(0.0, 0.04, -0.34), hips_rot=(10.0, 0.0, -18.0), spine=(4.0, 0.0, -8.0), head=(-14.0, 0.0, 14.0), grip_l=0.0,
              fist_l=0.6, hand_l=(0.80, -0.55, 1.30), hand_l_dir=(0.2, -0.5, -0.8), elbow_r=(-1.0, 0.2, -0.3), elbow_l=(1.0, -0.2, -0.3),
              face=(1.0, 0.0, 0.0), **held((-1.30, 0.05, 1.85), (-0.20, 0.55, 0.81), 1.55))
    WIND2 = P2(hips=(0.0, 0.06, -0.18), hips_rot=(-4.0, 0.0, -6.0), spine=(-10.0, 0.0, -4.0), head=(4.0, 0.0, 6.0), grip_l=0.5,
               elbow_r=(-1.0, 0.0, -0.2), elbow_l=(0.8, -0.4, 0.0), face=(1.0, 0.0, 0.0), **held((-1.15, -0.40, 2.55), (0.05, -0.05, 1.0), 1.4))
    HIT = dict(CONTACT, hips=(0.0, -0.05, -0.46), hips_rot=(18.0, 0.0, 4.0))
    PLOW = dict(HIT, hips=(0.0, -0.20, -0.44), hips_rot=(20.0, 0.0, 4.0), spine=(14.0, 0.0, 0.0),
                **club((0.05, -4.70, 0.95), (0.02, -0.97, -0.25), sr=SR, sl=SL))
    SWEEP = sweep_pose()
    hold0 = 14
    keys = [Key(0, P()), Key(2.5, dict(tween(P(), GATHER, 0.45, 0.35, hand=(-0.25, -0.10, 0.0)), grip_r=0.7, fist_r=0.9), "inout"),
            Key(5, GATHER, "inout"),
            Key(9, tween(GATHER, COCK, 0.55, 0.15), "inout"), Key(hold0, COCK, "inout"), Key(apex, HOLD, "sine"),
            Key(28, WIND1, "in"), Key(31, WIND2, "lin"), Key(32.5, SMEAR, "lin"), Key(contact, HIT, "lin"),
            Key(contact + 3, dict(HIT, hips=(0.0, -0.08, -0.48)), "out"), Key(contact + 9, PLOW, "inout"),
            Key(contact + 14, dict(PLOW, grip_r=1.0, fist_r=1.0), "sine")]
    f = contact + 14
    keys += [Key(f + 3, dict(recover(PLOW, SWEEP, 0.5), grip_r=0.15, fist_r=0.7), "sine"), Key(f + 7, dict(SWEEP, grip_r=0.1, fist_r=0.7), "sine"),
             Key(f + 10, dict(tween(SWEEP, P(), 0.6, 0.18), grip_r=0.5, fist_r=0.85), "sine"), Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    # dos pisotones: el derecho atrás y afuera, el izquierdo adelante y afuera (la base ancha del arrastre)
    feet = {"r": [FR(0), FR(4), FR(9, -0.22, dx=-0.28, ease="out", lift=0.10), FR(apex, -0.22, dx=-0.28),
                  FR(contact + 3, lunge - 0.15, dx=-0.20, pitch=-10.0), FR(contact + 5, lunge - 0.15, dx=-0.20),
                  FR(contact + 9, lunge + 0.10, dx=-0.20, lift=0.06), FR(contact + 12, lunge + 0.10, dx=-0.20)],
            "l": [FL(0), FL(8), FL(13, 0.22, dx=0.26, ease="out", lift=0.10), FL(apex, 0.22, dx=0.26, pitch=8.0),
                  FL(contact + 7, lunge + 0.2, dx=0.16, ease="out")]}
    return T.TeamClip(name, n, keys, travel=tr, feet=feet, notes="fase 2: arrastra el martillo atrás y lo clava adelante: la onda sale por el piso",
                      timing=dict(kind="unblockable", apex=apex, contact=contact, active=[contact, contact + 3], hold=[hold0, apex], lunge=lunge,
                                  windup=windup, state=name, reach=3.0, armor_window=[5, contact + 2], punish=[f, n], plow=[contact, contact + 9],
                                  impacts={"wave": [0.05, -3.90]}, events={"wave": contact, "plow_end": contact + 9}))


def avalanche_summon():
    """Llamado de la avalancha (fase 2, no pega): levanta el martillo y lo clava dos veces en el piso delante suyo (la
    montaña tiembla), lo vuelve a la guardia con una mano y ruge al cielo con el pecho abierto y el brazo izquierdo en
    alto, el puño cerrado: ahí arranca la avalancha (evento 'call'). Con el martillo parado arriba de la cabeza, desde la
    cámara del juego el mango le partía el casco en dos y el rugido no se leía. Eventos: 'strike1', 'strike2' (dónde pega
    la cabeza: timing['impacts']), 'call', 'roar_end'. 2.8 s."""
    c3 = key_poses(combo3())
    n = 84
    RAISE, LIFT, SMEAR = c3[3], c3[6], c3[17]
    HIGH = P2(hips=(0.0, 0.10, -0.12), hips_rot=(-6.0, 0.0, 2.0), spine=(-10.0, 0.0, 0.0), head=(6.0, 0.0, 0.0),
              face=(0.0, 0.35, -0.94), elbow_r=(-1.0, -0.2, 0.3), elbow_l=(1.0, -0.2, 0.3),
              **club((0.06, 0.65, 5.50), (0.02, 0.38, 0.93), sr=SR, sl=SL))
    H1, H2 = (-0.45, -3.67, 1.00), (0.25, -3.82, 1.00)
    HIT1 = P2(hips=(0.0, -0.04, -0.40), hips_rot=(16.0, 0.0, 6.0), spine=(10.0, 0.0, 2.0), head=(-18.0, 0.0, 0.0),
              face=(0.0, -0.25, -0.97), elbow_r=(-1.0, 0.3, -0.4), elbow_l=(1.0, 0.3, -0.4),
              **club(H1, (-0.12, -0.96, -0.25), sr=SR, sl=SL))
    HIT2 = dict(HIT1, hips_rot=(18.0, 0.0, -2.0), **club(H2, (0.06, -0.97, -0.25), sr=SR, sl=SL))
    SWEEP = sweep_pose()
    # al cielo: el martillo en la guardia (la cabeza apoyada en el piso, una mano), el pecho arqueado, la cabeza atrás y
    # el brazo izquierdo arriba con el puño cerrado
    CALL = P(hips=(0.0, 0.05, -0.06), hips_rot=(-10.0, 0.0, 6.0), spine=(-20.0, 0.0, 4.0), head=(-24.0, 0.0, -4.0), breath=1.0,
             hand_l=(0.95, -0.30, 3.05), hand_l_dir=(0.35, -0.15, 0.92), hand_l_palm=(0.0, -1.0, 0.0), fist_l=1.0, elbow_l=(1.0, 0.0, -0.3),
             clav_l=(0.0, 0.0, 8.0))
    keys = [Key(0, P()), Key(3, RAISE, "inout"), Key(4.5, c3[4.5], "inout"), Key(6, LIFT, "lin"), Key(10, HIGH, "out"), Key(12, SMEAR, "in"),
            Key(14, HIT1, "expo_in"), Key(18, dict(HIT1, hips=(0.0, -0.04, -0.44)), "out"), Key(23, dict(SMEAR, hips=(0.0, 0.04, -0.16)), "inout"),
            Key(27, HIGH, "out"), Key(29, SMEAR, "in"), Key(31, HIT2, "expo_in"), Key(35, dict(HIT2, hips=(0.0, -0.04, -0.44)), "out"),
            Key(38, dict(recover(HIT2, SWEEP), grip_r=0.15, fist_r=0.7), "sine"), Key(41, dict(SWEEP, grip_r=0.1, fist_r=0.7), "sine"),
            Key(44, dict(tween(SWEEP, P(), 0.6, 0.18), grip_r=0.5, fist_r=0.85), "sine"),
            Key(46, dict(mix(P(), CALL, 0.45), hand_l=(0.95, -0.55, 2.25), hand_l_dir=(0.3, -0.4, 0.85), fist_l=1.0), "inout"),
            Key(48.5, CALL, "inout")]
    for i, f in enumerate(range(51, 64, 3)):
        sg = 1 if i % 2 else -1
        keys.append(Key(f, dict(CALL, spine=(-20.0, 1.5 * sg, 4.0), head=(-24.0, 0.0, -4.0 + 3.0 * sg)), "sine"))
    keys += [Key(66, dict(CALL, hips=(0.0, 0.04, -0.08), breath=0.4), "sine"),
             Key(71, dict(P(), hand_l=(0.95, -0.45, 2.05), hand_l_dir=(0.2, -0.3, -0.9), fist_l=0.9), "inout"), Key(77, P(), "inout"), Key(n, P(), "sine")]
    feet = {"r": [FR(0), FR(10), FR(12, z=0.10), FR(14, ease="in"), FR(n)], "l": [FL(0), FL(27), FL(29, z=0.12), FL(31, ease="in"), FL(n)]}
    return T.TeamClip("AvalancheSummon", n, keys, feet=feet, tremble=0.0, notes="fase 2: clava el martillo dos veces y ruge al cielo: la avalancha",
                      timing=dict(sheet=[6, 10, 14, 27, 31, 41, 48, 57, 66, 84], armor_window=[0, 66],
                                  # los dos martillazos al piso (no son golpes del juego: no tienen apex ni contacto)
                                  swing_ok=[[7, 15], [24, 32], [44, 49]],
                                  impacts={"strike1": list(H1[:2]), "strike2": list(H2[:2])},
                                  events={"strike1": 14, "strike2": 31, "call": 48, "roar_end": 63}))
