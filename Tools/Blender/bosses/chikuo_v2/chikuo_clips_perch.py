"""Clips de arriba del Chikuō ermitaño (espacio 'perch': la raíz en el PerchNode, el culmo es el eje Z del clip): el
posado, los dardos, colgarse, la risa, el barrido de caña, la catapulta, el salto entre cañas, trepar y el giro de los
señuelos (diseño chikuo_v2, 16.1).

La flauta va de los hombros (pegada al pecho) a la boca de cerbatana en un barrido por afuera: la izquierda suelta el
culmo y la agarra cerca de la boquilla, la punta de abajo pasa por delante a la derecha (lejos de la cabeza) y la derecha la
toma al llegar; a la vuelta, lo mismo al revés. Cada mano que cambia de agarre pasa un cuadro suelta (la muñeca neutra):
pasar de agarrar el culmo a agarrar la flauta de un cuadro al otro le doblaba la muñeca para atrás. Los dardos salen de
Staff_Muzzle, 35° hacia abajo al frente del modelo.
"""
import math
import chikuo_rig as CR
from chikuo_anim import CClip, merge, free, grip, culm, legs, staff_world, staff_spine, staff_lips, CLIMB_Z
from chikuo_clips import (K, PERCH, PERCH_FEET, PERCH_BLOW, STAFF_SHOULDERS, HANG, HANG_Z, AIR, AIR_STAFF, AIM, GOLD, RED, WHITE,
                          CHIMES_ALL, rolled, tossed)

HI = ("Chikuo_GlintChimesHi",)
L_TOP = CR.STAFF_LEN - 0.17                  # la izquierda en la cerbatana (cerca de la boquilla)
R_TOP = CR.STAFF_LEN - 0.32
R_SH = 0.38                                  # la derecha en la flauta de los hombros (por afuera del hombro)
L_SH = 1.66                                  # la izquierda en la flauta de los hombros (por afuera del hombro)


def staff_by_top(top, d, up=(0, -0.5, 0.85)):
    """La flauta en el clip dada por su punta de arriba (la boquilla) y la dirección de abajo hacia arriba."""
    n = math.sqrt(sum(x * x for x in d))
    d = tuple(x / n for x in d)
    return staff_world(tuple(t - x * CR.STAFF_LEN for t, x in zip(top, d)), d, up)


# a mitad del barrido de los hombros a la boca: la boquilla adelante a la izquierda de la cara, la punta de abajo
# adelante a la derecha y abajo (por afuera del cuerpo)
SW_MID = staff_by_top((0.55, -1.02, 1.25), (0.82, 0.46, 0.34))
# en el aire, dando media vuelta delante del pecho (la floritura de bajarla de los hombros)
SW_UP = staff_by_top((0.45, -0.78, 1.88), (0.70, 0.40, 0.60))
# cayendo ya casi de cerbatana, un palmo adelante y arriba de la boca: ahí la atajan
SW_NEAR = staff_by_top((0.02, -1.04, 1.30), (0.05, 0.80, 0.60))
FACE_BLOWN = dict(jaw=3.0, lids=0.15, brows=8.0, cheeks=0.12, corners=(0.016, -0.004))
FACE_PUFF = dict(jaw=-1.0, lids=0.5, brows=10.0, cheeks=1.25, corners=(0.020, -0.007))
FACE_EFFORT = dict(jaw=2.0, lids=0.1, brows=10.0, cheeks=0.0, corners=(-0.004, 0.012))


def E(f, fn):
    return {"frame": f, "fn": fn}


def shoulders_hold():
    """La flauta en los hombros como un yugo, un puño por afuera de cada hombro (el posado)."""
    return merge(STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1)), grip("l", L_SH, elbow=(0.6, -0.2, -1)))


def release_left(pos=(0.34, -0.20, 1.28)):
    """La izquierda suelta (el cuadro neutro entre un agarre y otro)."""
    return free("l", pos, elbow=(1, 0.1, -0.5), fing="open")


def pipe(lean=None, aim=AIM):
    """De cerbatana: las dos manos cerca de la boquilla."""
    d = tuple(-x for x in aim)
    base = merge(PERCH_BLOW, staff_lips(CR.STAFF_LEN, d, (0, 0, 1)), grip("l", L_TOP, elbow=(1, 0.2, -0.6)),
                 grip("r", R_TOP, elbow=(-1, 0.2, -0.6)))
    return merge(base, lean or {})


def aim_dir(down_deg, yaw_deg=0.0):
    """Hacia dónde apunta la cerbatana: down_deg bajo el horizonte, yaw_deg hacia su izquierda."""
    a, y = math.radians(down_deg), math.radians(yaw_deg)
    return (math.sin(y) * math.cos(a), -math.cos(y) * math.cos(a), -math.sin(a))


def blow_keys(f, kick=1.0):
    """El soplido en el cuadro f: la cabeza empuja la boquilla, los hombros rebotan, la punta patea apenas hacia arriba."""
    return [
        K(f - 1, pipe(dict(hips=(0, -0.41, -0.61), head=(16, 0, 0), spine2=(9, 0, 0)))),
        K(f, pipe(dict(hips=(0, -0.42, -0.60), head=(12 + 2 * kick, 0, 0), spine2=(6, 0, 0), clav_r=(0, 0, 4 * kick),
                       clav_l=(0, 0, -4 * kick)), aim=aim_dir(35 - 4 * kick)), ease="snap"),
        K(f + 2, pipe(dict(hips=(0, -0.405, -0.60), head=(13, 0, 0), spine2=(7, 0, 0)), aim=aim_dir(35 - 2 * kick)), ease="out"),
    ]


def face_track(*pairs):
    return [K(f, face=fc) for f, fc in pairs]


def to_pipe(f0, P, lean=None):
    """De los hombros a la cerbatana desde el cuadro f0, con la floritura del ermitaño: encoge los hombros (f0+1), los
    sube de golpe y empuja la flauta para arriba (f0+2, f0+3), la suelta y da media vuelta en el aire delante de él
    (f0+5), cae casi de cerbatana (f0+6), la izquierda la ataja en la boca (f0+7) y la derecha después (f0+8). Con las
    dos manos sueltas en el aire cada agarre arranca de nuevo (sosteniéndola en el barrido la muñeca daba media vuelta).
    Devuelve las claves."""
    lean = lean or {}
    up = lambda dz: staff_spine((-1.00, 0.11, 1.95 + dz), (1, 0, 0.03), (0, -0.3, 1))
    hold = lambda: merge(grip("r", R_SH, elbow=(-0.6, -0.2, -1)), grip("l", L_SH, elbow=(0.6, -0.2, -1)))
    # las manos sueltas se van primero para afuera y adelante (pasar cerca del hombro con el brazo plegado daba vuelta
    # el codo) y después a buscarla
    reach = merge(free("l", (0.52, -0.62, 1.52), elbow=(0.9, -0.1, -0.7), fing="open"),
                  free("r", (-0.50, -0.64, 1.46), elbow=(-0.9, -0.1, -0.7), fing="open"))
    let_go = merge(free("l", (0.60, -0.46, 1.62), elbow=(0.8, -0.2, -0.8), fing="relaxed"),
                   free("r", (-0.57, -0.46, 1.60), elbow=(-0.8, -0.2, -0.8), fing="relaxed"))
    return [K(f0 + 1, P, dict(spine2=(12, 0, 0), neck=(9, 0, 0), head=(12, 0, 0), clav_r=(0, 0, -3), clav_l=(0, 0, 3))),
            K(f0 + 2, P, up(0.06), hold(), dict(spine2=(6, 0, 0), neck=(6, 0, 0), head=(10, 0, 0), clav_r=(0, 0, 7),
                                                clav_l=(0, 0, -7)), ease="snap"),
            K(f0 + 3, P, up(0.16), hold(), dict(spine2=(5, 0, 0), head=(8, 0, 0), clav_r=(0, 0, 8), clav_l=(0, 0, -8))),
            K(f0 + 4, merge(PERCH, up(0.30), let_go), dict(spine2=(6, 0, 0), head=(6, 0, 0)), lean, ease="out"),
            K(f0 + 5, merge(PERCH, SW_UP, reach), dict(spine2=(8, 0, 0), head=(4, 0, 0)), lean),
            K(f0 + 6, merge(PERCH, SW_NEAR, free("l", (0.26, -0.84, 1.34), elbow=(1, -0.2, -0.6), fing="grip_stalk"),
                            free("r", (-0.30, -0.88, 1.28), elbow=(-1, 0.1, -0.6), fing="relaxed")),
              dict(spine2=(10, 0, 0), head=(12, 0, 0)), lean),
            # la derecha la toma en dos cuadros (la mano gira sobre el caño de a poco)
            K(f0 + 7, pipe(lean), free("r", (-0.13, -1.02, 1.12), elbow=(-1, 0.2, -0.6), fing="grip_stalk"), gw_r=0.5,
              grip_r=R_TOP, grip_r_auto=1.0),
            K(f0 + 8, pipe(lean), ease="out")]


def from_pipe(f0, frames, P):
    """De la cerbatana a los hombros desde f0 hasta el final del clip, la misma floritura al revés: suelta la boca y la
    tira para arriba (f0+3), da la vuelta en el aire (f0+5) y cae en los hombros (f0+7), donde la atajan los dos puños."""
    a, b, c = (4, 6, 8) if frames - f0 >= 10 else (2, 4, 6)
    # las manos acompañan a la flauta que sube (la empujan) y recién arriba se abren para recibirla en los hombros: si
    # saltaban lejos de un cuadro al otro el brazo daba vuelta el codo
    push = merge(free("l", (0.16, -0.98, 1.40), elbow=(1, -0.3, -0.6), fing="relaxed"),
                 free("r", (-0.10, -1.02, 1.28), elbow=(-1, 0.2, -0.6), fing="relaxed"))
    spread = merge(free("l", (0.44, -0.62, 1.54), elbow=(0.8, -0.2, -0.8), fing="open"),
                   free("r", (-0.44, -0.64, 1.51), elbow=(-0.8, -0.2, -0.8), fing="open"))
    return [K(f0 + a, merge(PERCH, SW_MID, push), dict(spine2=(10, 0, 0), head=(10, 0, 0)), ease="out"),
            K(f0 + b, merge(PERCH, SW_UP, spread), dict(spine2=(6, 0, 0), head=(4, 0, 0), clav_r=(0, 0, 4), clav_l=(0, 0, -4))),
            K(f0 + c, P, STAFF_SHOULDERS, dict(spine2=(12, 0, 0), head=(10, 0, 0), clav_r=(0, 0, -3), clav_l=(0, 0, 3)),
              merge(free("l", (0.64, -0.40, 1.32), elbow=(0.6, -0.2, -1), fing="relaxed"),
                    free("r", (-0.64, -0.40, 1.32), elbow=(-0.6, -0.2, -1), fing="relaxed")), ease="in"),
            K(frames, P, ease="out")]


def perch_idle():
    """Agachado en el nudo, se hamaca con la caña (2 cm), mira alrededor con curiosidad (la cabeza guía, el pecho la
    sigue), tamborilea los dedos sobre la flauta y parpadea; la capa y los cascabeles se mecen solos."""
    P = merge(PERCH, shoulders_hold())
    bob = lambda dz, dy: dict(hips=(0, -0.34 + dy, -0.58 + dz))
    keys = [
        K(0, P),
        K(12, P, bob(-0.02, 0.01), spine2=(10, 0, 3), neck=(10, 0, 6), head=(6, -6, 12), ease="sine"),
        K(24, P, bob(0.0, 0.0), spine2=(7, 0, 0), neck=(7, 0, 0), head=(12, 3, -2), ease="sine"),
        K(36, P, bob(-0.02, 0.01), spine2=(10, 0, -3), neck=(10, 0, -6), head=(6, 7, -14), ease="sine"),
        K(48, P, ease="sine"),
    ]
    fingers = [K(0, fing_r="grip_staff"), K(28, fing_r="grip_staff"), K(31, fing_r="relaxed"), K(34, fing_r="grip_staff"),
               K(37, fing_r="relaxed"), K(40, fing_r="grip_staff"), K(48, fing_r="grip_staff")]
    blink = [K(0, wink_r=0.0, wink_l=0.0), K(18, wink_r=0.0, wink_l=0.0), K(20, wink_r=1.0, wink_l=1.0),
             K(23, wink_r=0.0, wink_l=0.0), K(48, wink_r=0.0, wink_l=0.0)]
    return CClip("PerchIdle", 48, keys, tracks=[fingers, blink], loop=True, lag={"head": 1.5, "neck": 0.8},
                 timing=dict(space="perch", chain_from="PERCH", chain_to="PERCH", bend=-6.0, feet_on_node=[[0, 48]]),
                 notes="agachado en el nudo, la flauta en los hombros, se hamaca y mira; loop")


def dart_clip(name, frames, spawns, notes):
    """Dardo y dos dardos: baja la flauta de los hombros a la boca (aviso en f8), sopla, y vuelve."""
    P = merge(PERCH, shoulders_hold())
    keys = [K(0, P)] + to_pipe(0, P) + [K(12, pipe(dict(hips=(0, -0.41, -0.61), spine2=(9, 0, 0), head=(15, 0, 0))))]
    faces = [(0, "grin"), (5, "grin"), (8, FACE_PUFF)]
    last = spawns[-1]
    for i, f in enumerate(spawns):
        keys += blow_keys(f)
        faces += [(f - 1, FACE_PUFF), (f, FACE_BLOWN)]
        if i + 1 < len(spawns):
            nxt = spawns[i + 1]
            # vuelve a apuntar (un poco más a su izquierda: la segunda va adonde va a estar Kaito) e infla otra vez
            keys.append(K(f + 5, pipe(dict(hips=(0, -0.405, -0.605), head=(15, 0, 0), spine2=(8, 0, 2)), aim=aim_dir(35, 4))))
            keys.append(K(nxt - 2, pipe(dict(hips=(0, -0.41, -0.61), head=(15, 0, 0), spine2=(9, 0, 2)), aim=aim_dir(35, 4))))
            faces += [(f + 3, FACE_BLOWN), (nxt - 2, FACE_PUFF)]
    keys += from_pipe(last, frames, P)
    faces += [(last + 3, "grin"), (frames, "grin")]
    return CClip(name, frames, keys, tracks=[face_track(*faces)], lag={"head": 1.0},
                 timing=dict(space="perch", tell=[2, 8], apex=8, kind="projectile", glow=list(HI), chain_from="PERCH",
                             chain_to="PERCH", bend=-8.0, feet_on_node=[[0, frames]],
                             shots=[(8, "aviso (dorado)", HI + ("Chikuo_GlintStaff",), GOLD)]),
                 events=[E(f, "DartSpawn") for f in spawns], notes=notes)


def volley_clip(name, frames, spawns, unload, notes, swing_end):
    """Tres / Cuatro Notas: baja la flauta a la boca mientras se echa atrás (la caña se arquea: Load f3), inspira con la
    cerbatana casi horizontal, se adelanta a apuntar y sopla la ráfaga con un rebote de hombros en cada dardo; Unload y
    vuelve al posado. La flauta deja los hombros antes de echarse atrás (si no, chocaba con el culmo)."""
    P = merge(PERCH, shoulders_hold())
    back = dict(hips=(0, -0.48, -0.57), hips_rot=(2, 0, 0), spine=(-8, 0, 0), spine1=(-4, 0, 0), spine2=(0, 0, 0),
                neck=(-2, 0, 0), head=(-6, 0, 0))
    keys = [K(0, P)] + to_pipe(0, P, back) + [
            K(swing_end, pipe(dict(back, spine=(-10, 0, 0), head=(-9, 0, 0)), aim=aim_dir(13)), ease="out"),
            # el pecho lleno, se adelanta a apuntar
            K(spawns[0] - 3, pipe(dict(hips=(0, -0.39, -0.60), spine2=(8, 0, 0), head=(15, 0, 0))), ease="inout")]
    faces = [(0, "grin"), (3, "surprise"), (8, FACE_PUFF), (spawns[0] - 1, FACE_PUFF)]
    sweep = [-5, 0, 5, 0]
    for i, f in enumerate(spawns):
        keys += [k for k in blow_keys(f, kick=1.2) if k.frame < (spawns[i + 1] - 3 if i + 1 < len(spawns) else unload)]
        faces += [(f, FACE_BLOWN)]
        if i + 1 < len(spawns):
            nxt = spawns[i + 1]
            y = sweep[(i + 1) % len(sweep)]
            keys.append(K(nxt - 3, pipe(dict(hips=(0, -0.405, -0.605), head=(15, 0, 0), spine2=(9, 0, y * 0.5)), aim=aim_dir(35, y))))
            faces += [(nxt - 3, FACE_PUFF)]
    keys += [K(unload, pipe(dict(hips=(0, -0.38, -0.59), head=(10, 0, 0), spine2=(6, 0, 0)), aim=aim_dir(30)), ease="out")]
    keys += from_pipe(unload, frames, P)
    faces += [(unload + 2, "grin"), (frames, "grin")]
    return CClip(name, frames, keys, tracks=[face_track(*faces)], lag={"head": 1.0},
                 timing=dict(space="perch", tell=[3, swing_end], apex=swing_end, load=[3, unload], kind="projectile",
                             glow=list(HI), chain_from="PERCH", chain_to="PERCH", bend=20.0, feet_on_node=[[0, frames]],
                             shots=[((3 + unload) // 2, "cargada (blanco)", CHIMES_ALL, WHITE)]),
                 events=[E(3, "Load")] + [E(f, "DartSpawn") for f in spawns] + [E(unload, "Unload")], notes=notes)


def perch_whistle():
    """El Silbador: gran inspiración (el pecho se infla, los hombros suben, los cachetes al máximo) con la cerbatana ya
    apuntada; en el aviso (f24) se queda quieto con todo el aire; sopla el dardo pesado con un culatazo que lo tira atrás
    (f27) y vuelve."""
    P = merge(PERCH, shoulders_hold())
    keys = [K(0, P)] + to_pipe(2, P) + [
        K(20, pipe(dict(hips=(0, -0.37, -0.57), spine=(0, 0, 0), spine1=(2, 0, 0), spine2=(2, 0, 0), head=(8, 0, 0),
                        clav_r=(0, 0, 8), clav_l=(0, 0, -8)), aim=aim_dir(32)), ease="inout"),
        K(24, pipe(dict(hips=(0, -0.38, -0.575), spine2=(3, 0, 0), head=(10, 0, 0), clav_r=(0, 0, 9), clav_l=(0, 0, -9)),
                   aim=aim_dir(35)), ease="out"),
        K(26, pipe(dict(hips=(0, -0.385, -0.578), spine2=(4, 0, 0), head=(11, 0, 0), clav_r=(0, 0, 9), clav_l=(0, 0, -9)))),
        K(27, pipe(dict(hips=(0, -0.29, -0.56), spine=(-6, 0, 0), spine2=(0, 0, 0), head=(4, 0, 0)), aim=aim_dir(26)),
          ease="snap"),
        K(30, pipe(dict(hips=(0, -0.4, -0.60), spine2=(7, 0, 0), head=(13, 0, 0)), aim=aim_dir(33)), ease="out"),
    ] + from_pipe(30, 42, P)
    big = dict(FACE_PUFF, cheeks=1.45, brows=14.0, lids=0.2)
    faces = face_track((0, "grin"), (7, "grin"), (10, FACE_PUFF), (24, big), (26, big), (27, FACE_BLOWN), (31, "grin"), (42, "grin"))
    return CClip("PerchWhistle", 42, keys, tracks=[faces], lag={"head": 1.0},
                 timing=dict(space="perch", tell=[3, 24], apex=24, load=[3, 30], kind="dodge", glow=list(HI) + ["Chikuo_GlintStaff"],
                             chain_from="PERCH", chain_to="PERCH", bend=25.0, feet_on_node=[[0, 42]],
                             shots=[(24, "aviso (rojo)", HI + ("Chikuo_GlintStaff",), RED), (16, "cargada (blanco)", CHIMES_ALL, WHITE)]),
                 events=[E(3, "Load"), E(27, "DartSpawn"), E(30, "Unload")],
                 notes="el silbador: gran inspiración, aviso quieto en f24, culatazo al soplar en f27; en la fase 3 el código "
                       "lo toca a x1.125")


def tala_shot():
    """El silbador corto a la rajadura de una caña vecina (el código gira el cuerpo hacia ella): sin la gran inspiración,
    un soplido seco con culatazo."""
    P = merge(PERCH, shoulders_hold())
    keys = [K(0, P)] + to_pipe(0, P) + [
        K(13, pipe(dict(hips=(0, -0.38, -0.58), spine2=(4, 0, 0), clav_r=(0, 0, 6), clav_l=(0, 0, -6)), aim=aim_dir(25))),
        K(14, pipe(dict(hips=(0, -0.29, -0.565), spine=(-6, 0, 0), spine2=(0, 0, 0), head=(6, 0, 0)), aim=aim_dir(18)), ease="snap"),
        K(17, pipe(dict(hips=(0, -0.37, -0.58), spine2=(6, 0, 0)), aim=aim_dir(24)), ease="out"),
    ] + from_pipe(17, 30, P)
    faces = face_track((0, "grin"), (5, "grin"), (8, FACE_PUFF), (13, dict(FACE_PUFF, cheeks=1.35)), (14, FACE_BLOWN),
                       (18, "grin"), (30, "grin"))
    return CClip("TalaShot", 30, keys, tracks=[faces], lag={"head": 1.0},
                 timing=dict(space="perch", tell=[2, 13], apex=13, kind="dodge", glow=list(HI) + ["Chikuo_GlintStaff"],
                             chain_from="PERCH", chain_to="PERCH", bend=-12.0, feet_on_node=[[0, 30]],
                             shots=[(13, "aviso (rojo)", HI + ("Chikuo_GlintStaff",), RED)]),
                 events=[E(14, "DartSpawn")], notes="el silbador corto contra la rajadura de otra caña (la tala); el código "
                                                     "gira el cuerpo hacia ella")


# ============================================================================ colgarse
def hang_pipe(extra=None, aim=AIM):
    # los codos pedidos en el marco del clip (hsp 0) aunque la clave vecina tenga una mano suelta con el pecho: si no, el
    # primer cuadro de HangClimb tomaba el marco de la clave siguiente y el codo no empalmaba con HangDart2
    d = tuple(-x for x in aim)
    return merge(HANG, staff_lips(CR.STAFF_LEN, d, (0, 0, -1)), grip("l", L_TOP, elbow=(1, -0.2, 0.6)),
                 grip("r", R_TOP, elbow=(-1, -0.2, 0.6)), dict(hsp_r=0.0, hsp_l=0.0), extra or {})


# a mitad del giro de costado: tendido sobre su derecha con las piernas trabadas en el culmo y la flauta todavía en los
# hombros como un yugo (va con el pecho: gira con él)
SIDE = merge(dict(hips=(-0.42, -0.26, -1.00), hips_rot=(6, -92, 0), spine=(-4, 0, 0), spine1=(-2, 0, 0), spine2=(2, 0, 0),
                  neck=(4, 0, 0), head=(-4, 0, 0)),
             STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1)), grip("l", L_SH, elbow=(0.6, -0.2, -1)),
             # los tobillos bien detrás del culmo y abiertos (las tibias lo abrazan por los costados: más cerca le pasaban 9 cm
             # por adentro)
             legs((-0.16, 0.26, 0.06), (0.18, 0.28, 0.42), rr=(-30, -70, 0), rl=(-30, -70, 0), kr=(-0.5, -1, -0.6), kl=(0.5, -1, 0.6)))


def hang_swap(w_lips, grip_l, free_r, extra=None):
    """Entre el yugo y la cerbatana colgado: la izquierda la tiene (la flauta gira alrededor de ese agarre, mezcla de los
    dos modos) y la derecha está suelta al lado de la cara."""
    return merge(hang_pipe(extra), STAFF_SHOULDERS, hang_pipe(extra), dict(sw_spine=1.0 - w_lips, sw_lips=w_lips),
                 grip("l", grip_l, elbow=(1, -0.2, 0.6)),
                 # el codo en el marco del pecho, que colgado está dado vuelta: el mismo lado que el (-1, -0.2, 0.6) del clip
                 # en hang_pipe (pedido igual en los dos marcos, el polo pasaba por cero al mezclarlos y el brazo daba vuelta)
                 free("r", free_r, elbow=(1, -0.2, -0.6), fing="open", chest=True))


def hang_drop(kit):
    """Se deja caer de costado (hacia su derecha) girando sobre las piernas trabadas en el culmo y queda cabeza abajo
    delante de la caña (Hang en f10). La flauta va en los hombros hasta casi dar la vuelta; ahí la suelta con un sacudón de
    hombros, la flauta da un cuarto de vuelta en el aire delante de la cara y la atajan las dos manos en la boca (girándola
    alrededor del puño izquierdo el puño se daba vuelta 92° en un cuadro)."""
    P = merge(PERCH, shoulders_hold())
    pipe_end = hang_pipe(dict(hips=(0.02, -0.27, HANG_Z - 0.02), hips_rot=(14, -181, 0), head=(-24, 0, 0)))
    A, B = kit.staff(SIDE), kit.staff(pipe_end)
    hands = lambda r, l: merge(free("r", r, elbow=(1, -0.2, -0.6), fing="open", chest=True),
                               free("l", l, elbow=(-1, -0.2, -0.6), fing="open", chest=True))
    keys = [
        K(0, P),
        K(1, P, dict(spine2=(12, 0, -3))),
        K(3, P, dict(hips=(-0.08, -0.29, -0.64), hips_rot=(10, -22, 0), spine2=(12, 0, -4), head=(10, 4, 6)),
          legs((-0.14, -0.08, 0.13), (0.14, -0.06, 0.15), rr=(-10, -20, -32), rl=(-10, -20, 32), kr=(-1, -0.6, 0.4), kl=(1, -0.6, 0.4))),
        K(6, SIDE, ease="inout"),
        K(7, SIDE, tossed(kit, A, B, 0.12, 0.08), hands((-0.56, -0.30, 2.02), (0.56, -0.30, 2.02)),
          dict(hips=(-0.30, -0.27, -1.12), hips_rot=(8, -112, 0)), ease="out"),
        K(8, hang_pipe(dict(hips=(-0.10, -0.27, HANG_Z + 0.10), hips_rot=(14, -160, 0), head=(-22, 0, 0))),
          tossed(kit, A, B, 0.50, 0.08), hands((-0.44, -0.44, 2.00), (0.42, -0.46, 2.00)), ease="inout"),
        K(9, hang_pipe(dict(hips=(0.03, -0.27, HANG_Z - 0.04), hips_rot=(16, -182, 0), head=(-26, 0, 0))),
          tossed(kit, A, B, 0.86, 0.04), hands((-0.30, -0.56, 1.98), (0.26, -0.58, 1.98)), ease="inout"),
        K(10, pipe_end, ease="out"),
        K(11, hang_pipe(dict(hips_rot=(12, -180, 0))), ease="inout"),
    ]
    faces = face_track((0, "grin"), (3, "surprise"), (8, "laugh"), (10, "blow"), (11, "blow"))
    return CClip("HangDrop", 11, keys, tracks=[faces], lag={"head": 1.0, "spine2": 0.5},
                 timing=dict(space="perch", load=[0, 11], chain_from="PERCH", chain_to="HANG", bend=-30.0, preroll=1.0,
                             feet_on_node=[[0, 1]], hang_scale=0.6, cloak_max=150.0, cloak_free=True),
                 events=[E(10, "Hang")], notes="se deja caer de costado y queda colgado de las piernas, cabeza abajo; Hang en f10")


def hang_dart2():
    """Cabeza abajo delante del culmo, sopla dos dardos (f9, f18) hamacándose de costado como un péndulo de 0.6 s (±13 cm
    y ±14°: antes era ±1 cm y el clip se veía como una foto): en cada punta del vaivén toma aire con la cabeza atrás, sopla
    al pasar por abajo (la cabeza empuja la boquilla de un golpe) y la punta patea 3° para arriba (el retroceso). La capa
    cuelga entera hacia el piso (cloak_max: con el tope de siempre quedaba en horizontal, una bandeja alrededor de la
    cabeza), la barba también. El segundo dardo es el último cuadro (sigue HangClimb). La puntería no se mueve más que eso:
    con 4° o más el planificador del giro de la izquierda daba media vuelta y el antebrazo no empalmaba con HangDrop ni con
    HangClimb (110°)."""
    # de costado: hacia el culmo se metía la cabeza en la caña y para afuera se despegaban los pies del nudo
    sway = lambda d: dict(hips=(d * 0.13, -0.27, HANG_Z), hips_rot=(12, 180, d * 14))
    keys = [
        K(0, hang_pipe(sway(0.0))),
        K(5, hang_pipe(dict(sway(-1.0), head=(-15, 0, 0))), ease="sine"),
        K(8, hang_pipe(dict(sway(-0.3), head=(-20, 0, 0)))),
        K(9, hang_pipe(dict(sway(0.02), head=(-30, 0, 0)), aim=aim_dir(31)), ease="snap"),
        K(11, hang_pipe(dict(sway(0.5), head=(-24, 0, 0)), aim=aim_dir(28)), ease="out"),
        K(15, hang_pipe(dict(sway(1.0), head=(-15, 0, 0)), aim=aim_dir(35, 4)), ease="sine"),
        K(17, hang_pipe(dict(sway(0.3), head=(-22, 0, 0)), aim=aim_dir(35, 4))),
        K(18, hang_pipe(dict(sway(0.02), head=(-26, 0, 0)), aim=aim_dir(31, 4)), ease="snap"),
    ]
    faces = face_track((0, FACE_PUFF), (8, FACE_PUFF), (9, FACE_BLOWN), (12, FACE_BLOWN), (16, FACE_PUFF), (17, FACE_PUFF),
                       (18, FACE_BLOWN))
    return CClip("HangDart2", 18, keys, tracks=[faces], lag={"head": 1.0},
                 timing=dict(space="perch", load=[0, 18], kind="projectile", glow=list(HI), chain_from="HANG", bend=-30.0,
                             hang_scale=1.0, cloak_hang=1.0, cloak_max=150.0, cloak_free=True,
                             preroll=2.0, shots=[(8, "colgado: aviso (dorado)", HI, GOLD), (4, "colgado: cargada", CHIMES_ALL, WHITE)]),
                 events=[E(9, "DartSpawn"), E(18, "DartSpawn")],
                 notes="colgado cabeza abajo, dos dardos (f9 y f18, el último cuadro); sigue HangClimb")


def hang_climb(kit):
    """El abdominal de vuelta, el mismo giro de HangDrop al revés: suelta la cerbatana con un golpe de las dos manos para
    arriba, la flauta da el cuarto de vuelta en el aire y cae en los hombros, donde la atajan los dos puños; se dobla por la
    cintura y gira de costado sobre las piernas hasta caer agachado en el nudo (Unload f8, Perch f15)."""
    P = merge(PERCH, shoulders_hold())
    first = hang_pipe(dict(hips=(0, -0.2664, HANG_Z), hips_rot=(12.4, -180, 0), head=(-26, 0, 0)), aim=aim_dir(31, 4))
    yoke = merge(hang_pipe(dict(hips_rot=(20, -170, 0), spine=(12, 0, 0), spine1=(10, 0, 0), head=(-12, 0, 0))), STAFF_SHOULDERS,
                 grip("r", R_SH, elbow=(-0.6, -0.2, -1)), grip("l", L_SH, elbow=(0.6, -0.2, -1)))
    A, B = kit.staff(first), kit.staff(yoke)
    hands = lambda r, l: merge(free("r", r, elbow=(1, -0.2, -0.6), fing="open", chest=True),
                               free("l", l, elbow=(-1, -0.2, -0.6), fing="open", chest=True))
    keys = [
        # el último cuadro de HangDart2 (el segundo dardo)
        K(0, first),
        K(1, first, tossed(kit, A, B, 0.10, 0.06), hands((-0.24, -0.62, 1.96), (0.20, -0.62, 1.98)), ease="out"),
        K(3, hang_pipe(dict(hips_rot=(14, -178, 0), spine=(4, 0, 0))), tossed(kit, A, B, 0.45, 0.10),
          hands((-0.42, -0.46, 2.02), (0.40, -0.46, 2.02)), ease="inout"),
        K(5, hang_pipe(dict(hips_rot=(17, -174, 0), spine=(8, 0, 0), spine1=(5, 0, 0), head=(-18, 0, 0))), tossed(kit, A, B, 0.84, 0.06),
          hands((-0.58, -0.30, 1.98), (0.58, -0.30, 1.98)), ease="inout"),
        K(7, yoke, ease="out"),
        K(10, SIDE, ease="inout"),
        K(13, P, dict(hips=(-0.08, -0.29, -0.60), hips_rot=(12, -18, 0), spine2=(12, 0, 0), head=(12, 0, 0)),
          legs((-0.14, -0.08, 0.14), (0.14, -0.08, 0.16), rr=(-10, -20, -32), rl=(-10, -20, 32), kr=(-1.0, -0.7, 0.35), kl=(1.0, -0.7, 0.35)),
          ease="out"),
        K(15, P, ease="inout"),
    ]
    faces = face_track((0, FACE_BLOWN), (4, "grin"), (15, "grin"))
    return CClip("HangClimb", 15, keys, tracks=[faces], lag={"head": 1.0},
                 timing=dict(space="perch", load=[0, 8], chain_from="HANG_END", chain_to="PERCH", bend=-30.0, feet_on_node=[[14, 15]],
                             hang_scale=0.6, cloak_max=150.0, cloak_free=True),
                 events=[E(8, "Unload"), E(15, "Perch")], notes="de colgado al posado: Unload f8, Perch f15")


# ============================================================================ la risa, el manoteo, el barrido
def perch_laugh():
    """La carcajada (la cara del concepto): la cabeza atrás, la boca abierta, los ojos cerrados, los hombros que se sacuden
    a cada 'ja' y la derecha que se palmea la rodilla dos veces; los cascabeles se sacuden. Loop de 36."""
    P = merge(PERCH, shoulders_hold())
    # la cabeza bien atrás (26-28°: con 18 la cara quedaba de frente al horizonte y la cámara alta no la veía)
    up = dict(neck=(-10, 0, 0), head=(-26, 0, 0), spine2=(2, 0, 0))
    lean = dict(spine=(6, 0, 0), spine1=(8, 0, -4), spine2=(14, 0, -6), neck=(6, 0, 0), head=(-2, 0, -4))

    def slap(f):
        # la mano vuelve al yugo subiendo por el costado con el codo afuera (de la rodilla al hombro derecho de un saque,
        # el eje del brazo giraba y el codo pasaba al otro lado en un cuadro)
        return [K(f - 4, P, STAFF_SHOULDERS, free("r", (-0.46, -0.58, 0.80), elbow=(-1, 0.3, -0.2), fing="open"), lean),
                K(f, P, STAFF_SHOULDERS, free("r", (-0.47, -0.50, 0.50), elbow=(-1, 0.3, -0.2), fing="open"),
                  dict(lean, spine2=(18, 0, -7)), ease="snap"),
                K(f + 3, P, STAFF_SHOULDERS, free("r", (-0.62, -0.30, 1.30), elbow=(-1, 0.1, -0.4), fing="relaxed"), lean,
                  ease="inout")]
    keys = [K(0, P, up)] + slap(9) + [K(14, P, dict(neck=(-12, 0, 0), head=(-28, 0, 4), spine2=(0, 0, 2)))]
    keys += slap(27) + [K(32, P, dict(neck=(-12, 0, 0), head=(-28, 0, -2), spine2=(0, 0, -2))), K(36, P, up)]
    # el 'ja, ja, ja': los hombros rebotan a 5 Hz encima de todo (seno: sin quiebre en la costura del loop)
    ja = [K(i, clav_r=(0, 0, 0), clav_l=(0, 0, 0), spine1=(0, 0, 0), ease="sine") for i in range(0, 37, 6)]
    ja = sorted(ja + [K(i + 3, clav_r=(0, 0, 6), clav_l=(0, 0, -6), spine1=(-4, 0, 0), ease="sine") for i in range(0, 34, 6)],
                key=lambda k: k.frame)
    faces = face_track((0, "laugh"), (36, "laugh"))
    return CClip("PerchLaugh", 36, keys, tracks=[ja, faces], loop=True, lag={"head": 1.0},
                 timing=dict(space="perch", load=[0, 36], chain_from="PERCH", chain_to="PERCH", bend=-10.0, fade_from=0.15,
                             fade_to=0.15, feet_on_node=[[0, 36]], shots=[(9, "la risa (cargada)", CHIMES_ALL, WHITE)]),
                 notes="carcajada con palmadas en la rodilla; loop (la Risa cargada, 1.2 s / 2.0 s la del maestro)")


def perch_wobble():
    """Le cortaron la caña sin campanas: manotea con la izquierda, se tambalea, abre los ojos y se vuelve a agarrar."""
    P = merge(PERCH, shoulders_hold())
    sh = merge(STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1)))
    keys = [
        K(0, P),
        K(2, P, sh, free("l", (0.62, -0.32, 1.40), elbow=(1, 0.3, -0.3), fing="open"),
          dict(hips=(0.04, -0.33, -0.56), hips_rot=(6, 7, 0), spine2=(4, 6, 0), head=(-4, -8, 0)), ease="snap"),
        K(4, P, sh, free("l", (0.50, -0.44, 1.62), elbow=(1, 0.3, -0.2), fing="open"),
          dict(hips=(-0.03, -0.35, -0.59), hips_rot=(10, -5, 0), spine2=(12, -4, 0), head=(8, 6, 0)), ease="inout"),
        K(6, P, sh, release_left((0.52, -0.30, 1.32)), dict(hips=(0.0, -0.385, -0.585), spine2=(9, 0, 0)), ease="out"),
        K(8, P, ease="inout"),
    ]
    faces = face_track((0, "grin"), (2, "surprise"), (6, "grin"), (8, "grin"))
    return CClip("PerchWobble", 8, keys, tracks=[faces], lag={"head": 1.0},
                 timing=dict(space="perch", chain_from="PERCH", chain_to="PERCH", bend=10.0, feet_on_node=[[0, 8]]),
                 notes="manotea: le cortaron la caña sin las campanas (¡Cosquillas!)")


def stalk_sweep():
    """El Barrido de Caña: la bandera humana. Colgado del culmo con la izquierda, saca el cuerpo entero hacia su derecha
    derecho como una bandera, con la flauta estirada en la derecha como un brazo más largo (Load f8); el aviso (f20) es el
    cuerpo bien afuera; la caña barre (el código) y el cuerpo la sigue estirado, la flauta barriendo adelante (Contact f26);
    vuelve a posarse."""
    P = merge(PERCH, shoulders_hold())
    # la flauta sigue en los hombros como un yugo en la derecha (de bandera queda a lo largo de la línea de los hombros):
    # sacarla a la mano y volverla a los hombros daba vuelta los brazos
    out_staff = merge(STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1)))
    # la izquierda toma el culmo del costado que da al cuerpo (su derecha) y por encima del hombro: de bandera el brazo
    # llega derecho al culmo y el cuerpo cuelga por debajo (con el agarre a la altura del hombro, al salir para afuera el
    # hombro pasaba a 11 cm de la mano y el codo daba vuelta)
    hold = culm("l", 1.36, 300.0, elbow=(0.3, 0.3, 1))

    def flag(x, z, tilt, yaw=0.0, y=-0.12):
        return dict(hips=(x, y, z - 1.06), hips_rot=(4, tilt, yaw), spine=(-4, 0, 0), spine1=(-2, 0, 0), spine2=(2, 0, 0),
                    neck=(-4, -8, 0), head=(-10, -14, 0))

    def flag_legs(x, z, tilt, spread=0.16):
        # las piernas siguen al cuerpo hacia afuera (juntas, la de arriba un poco adelante)
        r = math.radians(90.0 - tilt)
        d = (-math.cos(r), 0.0, -math.sin(r))
        # de costado su derecha queda arriba: el pie derecho va por encima del izquierdo
        return legs((x + d[0] * 0.86, -0.06, z + d[2] * 0.86 + spread), (x + d[0] * 0.88, -0.18, z + d[2] * 0.88 - 0.06),
                    rr=(-20, tilt, 0), rl=(-10, tilt, 0), kr=(0.3, -1, 0.6), kl=(0.3, -1, 0.9))
    keys = [
        K(0, P),
        # la izquierda suelta el yugo por arriba y afuera del hombro y va al culmo
        K(2, P, out_staff, free("l", (0.58, -0.12, 1.72), elbow=(0.6, -0.2, -1), fing="open"),
          dict(hips=(0, -0.40, -0.60), spine2=(10, 0, 0))),
        K(4, P, out_staff, free("l", (0.40, -0.30, 1.30), elbow=(1, 0.4, -0.2), fing="open"), dict(hips=(-0.06, -0.36, -0.59))),
        K(6, P, out_staff, hold, dict(hips=(-0.30, -0.30, -0.58), hips_rot=(10, 14, 0), spine2=(8, 0, 0))),
        K(10, out_staff, hold, flag(-0.92, 0.45, 40.0), flag_legs(-0.92, 0.45, 40.0), ease="inout"),
        K(20, out_staff, hold, flag(-1.22, 0.42, 62.0), flag_legs(-1.22, 0.42, 62.0), ease="out"),
        K(22, out_staff, hold, flag(-1.23, 0.43, 63.0), flag_legs(-1.23, 0.43, 63.0)),
        # el barrido: la caña tira y el cuerpo se estira derecho para afuera
        K(26, out_staff, hold, flag(-1.38, 0.72, 84.0, -12.0, -0.02), flag_legs(-1.38, 0.72, 84.0, 0.10), ease="in"),
        K(30, out_staff, hold, flag(-1.10, 0.55, 62.0, -4.0), flag_legs(-1.10, 0.55, 62.0), ease="out"),
        K(35, P, out_staff, hold, dict(hips=(-0.30, -0.32, -0.58), hips_rot=(10, 14, 0), spine2=(10, 0, 0)), PERCH_FEET, ease="inout"),
        K(37, P, out_staff, free("l", (0.40, -0.30, 1.30), elbow=(1, 0.4, -0.2), fing="open"), dict(hips=(-0.06, -0.36, -0.59))),
        K(39, P, out_staff, free("l", (0.58, -0.12, 1.72), elbow=(0.6, -0.2, -1), fing="open"), dict(hips=(0, -0.39, -0.59))),
        K(41, P, ease="inout"),
    ]
    faces = face_track((0, "grin"), (6, FACE_EFFORT), (26, "laugh"), (34, "grin"), (41, "grin"))
    return CClip("StalkSweep", 41, keys, tracks=[faces], lag={"head": 1.5, "spine2": 0.5},
                 timing=dict(space="perch", tell=[8, 20], apex=20, contact=26, active=[24, 28], kind="dodge", load=[8, 26],
                             glow=list(CHIMES_ALL) + ["Chikuo_GlintStaff"], chain_from="PERCH", chain_to="PERCH", bend=-30.0,
                             ring_m=3.6, feet_on_node=[[0, 4], [37, 41]],
                             shots=[(20, "aviso (rojo)", CHIMES_ALL + ("Chikuo_GlintStaff",), RED)]),
                 events=[E(8, "Load"), E(26, "Contact")],
                 notes="se cuelga del costado y la caña (código) barre el disco de 3.6 m; Load f8, aviso f20, Contact f26")


# ============================================================================ la catapulta
def catapult_draw():
    """La caña tensa como un arco (el código la dobla -35°): se enrolla agachado al fondo, las rodillas al pecho, el lomo
    curvo hacia adelante como un resorte comprimido y las dos manos en la flauta de los hombros; la cabeza levantada mira el
    carril. En AimFix (f22) se clava y en f30 se estira de golpe (LeaveStalk)."""
    P = merge(PERCH, shoulders_hold())
    both = merge(STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1)), grip("l", L_SH, elbow=(1, -0.2, -1)))
    coil = dict(hips=(0, -0.26, -0.68), hips_rot=(14, 0, 0), spine=(10, 0, 0), spine1=(8, 0, 0), spine2=(10, 0, 0),
                neck=(-14, 0, 0), head=(-4, 0, 0))
    deep = dict(hips=(0, -0.27, -0.72), hips_rot=(18, 0, 0), spine=(12, 0, 0), spine1=(10, 0, 0), spine2=(12, 0, 0),
                neck=(-20, 0, 0), head=(-2, 0, 0))
    feet = legs((-0.19, -0.135, 0.115), (0.19, -0.135, 0.115), rr=(0, 0, -22), rl=(0, 0, 22), kr=(-0.7, -0.8, 0.5), kl=(0.7, -0.8, 0.5))
    keys = [
        K(0, P),
        K(6, both, coil, feet, ease="inout"),
        K(16, both, dict(coil, hips=(0, -0.265, -0.70)), feet, ease="sine"),
        K(22, both, deep, feet, ease="out"),
        K(27, both, dict(deep, hips=(0, -0.27, -0.73), head=(0, 0, 0)), feet),
        K(30, both, dict(hips=(0, -0.36, -0.50), hips_rot=(24, 0, 0), spine=(10, 0, 0), spine2=(14, 0, 0), neck=(8, 0, 0),
                         head=(10, 0, 0)),
          legs((-0.15, -0.10, 0.14), (0.15, -0.10, 0.14), rr=(-20, 0, -20), rl=(-20, 0, 20), kr=(-0.5, -1, 0.3), kl=(0.5, -1, 0.3)),
          ease="in"),
    ]
    faces = face_track((0, "grin"), (6, dict(jaw=-1.0, lids=0.35, brows=-6.0, cheeks=0.2, corners=(0.004, 0.006))),
                       (22, dict(jaw=-1.0, lids=0.45, brows=-10.0, cheeks=0.3, corners=(0.006, 0.008))), (30, "surprise"))
    return CClip("CatapultDraw", 30, keys, tracks=[faces], lag={"head": 1.0},
                 timing=dict(space="perch", load=[0, 30], tell=[0, 22], apex=22, kind="dodge", glow=list(CHIMES_ALL) + ["Chikuo_GlintFootR"],
                             chain_from="PERCH", bend=35.0, feet_on_node=[[0, 29]],
                             shots=[(22, "aviso (rojo)", CHIMES_ALL + ("Chikuo_GlintFootR",), RED), (12, "cargada", CHIMES_ALL, WHITE)]),
                 events=[E(0, "Load"), E(22, "AimFix"), E(30, "LeaveStalk")],
                 notes="tensa la caña como un arco: Load f0, AimFix f22 (el carril queda fijo), LeaveStalk f30 (sigue CatapultKick)")


# la patada voladora: el cuerpo echado atrás, la derecha estirada adelante y abajo, la izquierda recogida, los brazos
# abiertos atrás (la flauta en la derecha); la cadera a ~0.8 m de la raíz, el pie de la patada adelante a la altura de la raíz
def kick_pose(hz, hy, foot_z, tilt=-34.0, land=False):
    """land: el pie de la patada apoyado de talón en el piso (la punta 30° arriba), como lo recibe DiveLand."""
    if land:
        ank, rot, _t = rolled("r", -0.10, hy - 0.62, 0.0, -30.0, "heel")
    else:
        ank, rot = (-0.10, hy - 0.62, foot_z), (-60, 0, 0)
    # la flauta sigue en los hombros como un yugo, en la derecha (desde el posado no gira: alzada atrás, la mano giraba
    # 100° en un cuadro); la izquierda abierta en garra
    return merge(dict(hips=(0, hy, hz - 1.06), hips_rot=(tilt, 0, 0), spine=(-4, 0, 0), spine1=(-2, 0, 0), spine2=(0, 0, 0),
                      neck=(14, 0, 0), head=(18, 0, 0)),
                 STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1)),
                 free("l", (0.62, 0.28, 1.60), elbow=(1, 0.4, -0.3), fing="claw", chest=True),
                 legs(ank, (0.16, hy + 0.05, hz - 0.30), rr=rot, rl=(-20, 0, 0), kr=(0, -1, 0.6), kl=(0.2, -1, 1)))


def catapult_kick():
    """La patada voladora por el carril (el código lleva la raíz del PerchNode al final del carril): sale estirado y se
    arma en el aire, el pie derecho adelante y abajo, y toca el piso en f15."""
    keys = [
        K(0, merge(STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1)), grip("l", L_SH, elbow=(1, -0.2, -1))),
          dict(hips=(0, -0.36, -0.50), hips_rot=(24, 0, 0), spine=(10, 0, 0), spine2=(14, 0, 0), neck=(8, 0, 0), head=(10, 0, 0)),
          legs((-0.14, -0.08, 0.14), (0.14, -0.08, 0.14), rr=(-20, 0, -20), rl=(-20, 0, 20), kr=(-0.5, -1, 0.3), kl=(0.5, -1, 0.3))),
        K(2, merge(STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1))), dict(hips=(0, -0.10, -0.36), hips_rot=(6, 0, 0)),
          free("l", (0.68, 0.06, 1.88), elbow=(0.6, -0.2, -1), fing="open", chest=True),
          legs((-0.12, -0.30, 0.20), (0.14, 0.05, 0.30), rr=(-30, 0, 0), rl=(-20, 0, 0), kr=(0, -1, 0.4), kl=(0.2, -1, 0.6))),
        K(4, kick_pose(0.90, 0.10, 0.40, -16.0), free("l", (0.70, 0.16, 1.80), elbow=(1, 0.4, -0.3), fing="claw", chest=True),
          ease="inout"),
        K(7, kick_pose(0.88, 0.22, 0.28), ease="out"),
        K(12, kick_pose(0.86, 0.24, 0.20)),
        K(15, kick_pose(0.80, 0.22, 0.115, -30.0, land=True), ease="in"),
    ]
    angry = dict(jaw=10.0, lids=-0.2, brows=-14.0, cheeks=0.0, corners=(-0.006, 0.010))
    faces = face_track((0, "surprise"), (4, angry), (15, angry))
    return CClip("CatapultKick", 15, keys, tracks=[faces], lag={"head": 1.0},
                 spring_vel=lambda f: (0.0, -0.16 * f, -0.06 * f),
                 timing=dict(space="air", contact=15, kind="dodge", glow=["Chikuo_GlintFootR"], chain_to="DIVE_LAND",
                             shots=[(8, "en vuelo (rojo)", ("Chikuo_GlintFootR",), RED)]),
                 events=[E(15, "Contact")],
                 notes="la patada voladora por el carril: el código lleva la raíz del PerchNode al final del carril (el pie "
                       "derecho a la altura de la raíz); Contact f15; sigue DiveLand")


# ============================================================================ de caña en caña
def leap_crouch():
    """El agachado del salto: la cabeza gira primero hacia la caña de destino (el código gira el cuerpo), se hunde, la
    derecha saca la flauta de los hombros y la alza, la izquierda suelta el culmo, y estira las piernas de golpe
    (LeaveStalk f7)."""
    P = merge(PERCH, shoulders_hold())
    deep = legs((-0.19, -0.135, 0.115), (0.19, -0.135, 0.115), rr=(0, 0, -24), rl=(0, 0, 24), kr=(-0.8, -0.9, 0.3), kl=(0.8, -0.9, 0.3))
    keys = [
        K(0, P),
        K(2, P, STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1)), free("l", (0.58, -0.12, 1.70), elbow=(0.6, -0.2, -1),
                                                                                  fing="open"),
          dict(hips=(0, -0.37, -0.65), hips_rot=(16, 0, 0), spine2=(13, 0, 0), neck=(10, 0, 8), head=(6, 0, 14)), deep, ease="out"),
        # la flauta de los hombros a alzada en tres cuadros (la mano se corre 57 cm por el caño: en dos, el brazo giraba 80°)
        K(5, AIR_STAFF, grip("r", 0.95, elbow=(-1, 0.4, -0.4)), dict(hips=(0, -0.38, -0.67), hips_rot=(20, 0, 0),
                                                                        spine2=(12, 0, 0), head=(4, 0, 8)),
          free("l", (0.62, -0.10, 1.30), elbow=(1, 0.4, -0.2), fing="open"), deep, ease="lin"),
        K(7, merge(AIR, dict(hips=(0, -0.10, -0.32), hips_rot=(10, 0, 0))),
          legs((-0.14, -0.04, 0.115), (0.14, -0.08, 0.20), rr=(-30, 0, -10), rl=(-40, 0, 10), kr=(-0.2, -1, 0), kl=(0.2, -1, 0.3)),
          ease="in"),
    ]
    faces = face_track((0, "grin"), (3, dict(jaw=-1.0, lids=0.2, brows=-6.0, cheeks=0.1, corners=(-0.004, 0.012))), (7, "grin"))
    return CClip("LeapCrouch", 7, keys, tracks=[faces], lag={"head": -1.0},
                 timing=dict(space="perch", chain_from="PERCH", chain_to="AIR", bend=12.0, feet_on_node=[[0, 6]], fade_to=0.08,
                             root_offset=["LeapAir", 0, 7]),
                 events=[E(7, "LeaveStalk")], notes="el agachado del salto (0.23 s; fase 3 a x1.57): LeaveStalk f7")


def leap_air():
    """En el aire (el salto del concepto): la rodilla izquierda arriba, la derecha estirada atrás, la flauta alzada, la
    izquierda abierta como una garra; las piernas pedalean apenas y la capa flamea (el viento del salto horneado)."""
    A = AIR
    keys = [
        K(0, A),
        K(6, A, dict(hips=(0, 0.05, -0.27), spine2=(2, 0, 8), head=(-10, 0, -6)),
          legs((-0.16, 0.40, 0.16), (0.18, -0.26, 0.48), rr=(-34, 0, -10), rl=(-46, 0, 10), kr=(-0.2, -1, 0), kl=(0.2, -1, 0.3)),
          free("l", (0.82, -0.08, 1.62), elbow=(0.4, 0.6, -0.6), fing="claw"), ease="sine"),
        K(12, A, ease="sine"),
    ]
    return CClip("LeapAir", 12, keys, loop=True, lag={"head": 1.0},
                 spring_vel=lambda f: (0.0, -0.14 * f, 0.0),
                 timing=dict(space="air", chain_from="AIR", chain_to="AIR"),
                 notes="en el aire entre cañas (loop); el código lleva la raíz por el arco del salto (los pies a la altura de "
                       "la raíz)")


def leap_grab():
    """Llega a la caña de destino de frente y la izquierda la agarra de su costado (GrabStalk f0): el impulso lo hace dar
    la vuelta alrededor del culmo por ese lado (la caña le queda a la derecha), la pierna derecha pasa por delante del
    culmo, la flauta vuelve a los hombros y los pies encuentran el nudo (Perch f6)."""
    P = merge(PERCH, shoulders_hold())
    keys = [
        K(0, merge(AIR, dict(hips=(0.45, 0.40, -0.32), hips_rot=(-4, 0, 10), spine2=(8, 0, 0), head=(4, 0, -6))),
          culm("l", 1.05, 80.0, elbow=(1, 0.6, -0.2)),
          legs((0.14, 0.78, 0.25), (0.48, 0.36, 0.40), rr=(-40, 0, -10), rl=(-40, 0, 10), kr=(-0.6, -1, 0.2), kl=(0.6, -1, 0.3))),
        K(2, merge(PERCH, culm("l", 1.05, 80.0, elbow=(1, 0.4, -0.3))), AIR_STAFF, grip("r", 0.95, elbow=(-1, 0.4, -0.4)),
          dict(hips=(0.42, -0.14, -0.48), hips_rot=(18, 0, 6), spine2=(12, 0, 0), head=(10, 0, 0)),
          legs((-0.10, -0.26, 0.24), (0.30, -0.06, 0.22), rr=(-10, 0, -30), rl=(-10, 0, 30), kr=(-1.0, -0.7, 0.35), kl=(1.0, -0.7, 0.35)),
          ease="out"),
        # la flauta alzada vuelve a los hombros en tres cuadros (la mano se corre 57 cm por el caño: en dos, el brazo daba
        # vuelta el codo)
        K(5, P, STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1)), release_left((0.45, -0.30, 1.25)),
          dict(hips=(0, -0.37, -0.60)), ease="lin"),
        K(6, P, dict(hips=(0, -0.38, -0.61)), ease="inout"),
    ]
    faces = face_track((0, "grin"), (6, "grin"))
    return CClip("LeapGrab", 6, keys, tracks=[faces], lag={"head": 0.5},
                 spring_vel=lambda f: (0.0, -0.25 * min(f, 2), -0.05 * min(f, 2)),
                 timing=dict(space="perch", load=[0, 6], chain_from="AIR", chain_to="PERCH", bend=12.0, feet_on_node=[[6, 6]],
                             fade_from=0.08, root_offset=["LeapAir", 0, 0]),
                 events=[E(0, "GrabStalk"), E(6, "Perch")],
                 notes="agarra la caña de destino (GrabStalk f0, cargada 0.20 s) y queda posado (Perch f6). Llega con el "
                       "culmo adelante a su derecha (el código lo trae mirando la caña) y da la vuelta por ese costado")


def climb():
    """Trepa desde el piso como un mono (la hoja de acciones: la caña a su derecha): alcanza ClimbGrip con la derecha
    (GrabStalk f4) y sube mano sobre mano (cada mano suelta antes de volver a agarrar más arriba) empujando con los pies
    contra el culmo, y se monta en el nudo (Perch f24). La flauta parada en la espalda como una aljaba; al final la derecha
    la pasa a los hombros."""
    P = merge(PERCH, shoulders_hold())
    back_staff = staff_spine((0.08, 0.22, 0.58), (0.04, -0.03, 1.0), (0, 1, 0))
    gz = CLIMB_Z
    F0 = -4.4                                # el piso en el clip (la caña de adentro: posado a 4.4 m)
    hip = lambda z: z - 1.06                 # de la altura de la cadera en el clip al control 'hips'

    # la suela derecha apoyada de canto contra el culmo (el tobillo más cerca se metía en la caña)
    def wall(zr, zl, rot_l=(-40, 25, 10), rot_r=(-10, 70, 0)):
        return legs((0.23, -0.02, zr), (0.36, -0.20, zl), rr=rot_r, rl=rot_l, kr=(-0.2, -1, 0.5), kl=(0.4, -1, 0.6))

    def body(x, y, z, rx=10.0, rz=8.0, head=(-16, 0, -8)):
        return dict(hips=(x, y, hip(z)), hips_rot=(rx, 0, rz), spine2=(2, 0, 0), head=head)
    keys = [
        # agachado para el salto con los brazos atrás (la anticipación: con la derecha a la altura del hombro el brazo
        # quedaba plegado sobre sí mismo y daba media vuelta al estirarse hacia ClimbGrip)
        K(0, back_staff, body(0.30, -0.02, F0 + 0.78, 16.0, 10.0, (-16, 0, -10)),
          free("r", (0.22, 0.24, F0 + 0.82), elbow=(-1, 0.3, -0.5), fing="open"),
          free("l", (0.66, 0.10, F0 + 0.78), elbow=(1, 0.3, -0.5), fing="relaxed"),
          legs((0.14, -0.10, F0 + 0.115), (0.50, 0.10, F0 + 0.115), rr=(0, 0, -20), rl=(0, 0, 10), kr=(-0.3, -1, 0), kl=(0.3, -1, 0))),
        # los brazos pasan por delante del pecho en el impulso (en línea recta de la cadera a ClimbGrip la mano cruzaba el
        # hombro y el brazo daba media vuelta)
        K(2, back_staff, body(0.34, -0.03, F0 + 0.95, 10.0, 10.0, (-20, 0, -11)),
          free("r", (0.12, -0.42, F0 + 1.55), elbow=(-1, 0.3, -0.5), fing="open"),
          free("l", (0.62, -0.12, F0 + 1.20), elbow=(1, 0.3, -0.5), fing="open"),
          legs((0.16, -0.08, F0 + 0.25), (0.46, 0.0, F0 + 0.115), rr=(-5, 35, -10), rl=(0, 0, 10), kr=(-0.3, -1, 0.15), kl=(0.35, -1, 0.15)),
          ease="in"),
        # la derecha alcanza ClimbGrip estirado (2.2 m: a la altura de su cabeza), el pie derecho sube al culmo
        K(4, back_staff, body(0.38, -0.04, F0 + 1.08, 4.0, 10.0, (-22, 0, -12)),
          culm("r", gz, 95.0, elbow=(-0.4, -0.4, -1)), free("l", (0.58, -0.22, F0 + 1.40), elbow=(1, 0.3, -0.5), fing="open"),
          legs((0.23, -0.02, F0 + 0.45), (0.42, -0.10, F0 + 0.115), rr=(-10, 70, 0), rl=(0, 0, 10), kr=(-0.2, -1, 0.3), kl=(0.4, -1, 0.3)),
          ease="out"),
        K(7, back_staff, body(0.41, -0.02, -2.95), culm("r", gz, 95.0, elbow=(-0.6, -0.4, -0.8)),
          free("l", (0.40, -0.26, -1.75), elbow=(1, -0.2, -0.4), fing="open"), wall(-3.55, -3.30)),
        # tirón 1: empuja con las piernas contra el culmo y tira; la izquierda agarra arriba de la cabeza, al alcance del brazo
        # (más arriba no llegaba por 20 cm)
        K(10, back_staff, body(0.40, 0.02, -2.40), culm("r", gz, 95.0, elbow=(-0.8, -0.4, -0.6)),
          culm("l", -1.25, 70.0, elbow=(1, -0.3, -0.6)), wall(-3.00, -2.85), ease="inout"),
        # la derecha suelta y sube
        K(12, back_staff, body(0.38, 0.08, -1.95), free("r", (0.05, -0.32, -0.95), elbow=(-1, -0.2, -0.4), fing="open"),
          culm("l", -1.25, 70.0, elbow=(1, -0.3, -0.6)), wall(-2.60, -2.35)),
        K(15, back_staff, body(0.36, 0.08, -1.40, 12.0, 6.0, (-14, 0, -6)), culm("r", -0.15, 75.0, elbow=(-0.8, -0.4, -0.6)),
          culm("l", -1.25, 70.0, elbow=(1, -0.3, -0.8)), wall(-2.05, -1.85), ease="inout"),
        # la izquierda suelta y va al nudo de arriba
        K(17, back_staff, body(0.42, 0.04, -1.00, 12.0, 6.0, (-12, 0, -6)), culm("r", -0.15, 75.0, elbow=(-0.8, -0.4, -0.6)),
          free("l", (0.36, -0.30, 0.55), elbow=(1, -0.2, -0.4), fing="open"), wall(-1.60, -1.40)),
        K(20, back_staff, body(0.32, -0.04, -0.10, 16.0, 4.0, (-6, 0, -2)), free("r", (0.06, -0.36, 0.95), elbow=(-1, 0.2, -0.5), fing="open"),
          culm("l", 1.12, 80.0, elbow=(1, 0.3, -0.4)), wall(-0.62, -0.45, (-60, 20, 10), (-6, 35, -15)), ease="inout"),
        # se monta en el nudo pasando adelante del culmo; la derecha suelta y va a la flauta
        K(22, merge(STAFF_SHOULDERS), dict(hips=(0.06, -0.20, hip(0.38)), hips_rot=(14, 0, 2), spine2=(10, 0, 0), head=(4, 0, 0)),
          free("r", (-0.40, -0.30, 1.30), elbow=(-1, 0, -0.5), fing="open"), release_left((0.42, -0.28, 1.30)),
          legs((-0.13, -0.10, 0.15), (0.15, -0.10, 0.16), rr=(0, 0, -30), rl=(0, 0, 30), kr=(-1.0, -0.7, 0.35), kl=(1.0, -0.7, 0.35)),
          ease="out"),
        K(24, P, ease="inout"),
    ]
    faces = face_track((0, "grin"), (4, FACE_EFFORT), (24, "grin"))
    return CClip("Climb", 24, keys, tracks=[faces], lag={"head": 1.0},
                 timing=dict(space="perch", load=[0, 24], air=[0, 4], chain_to="PERCH", bend=6.0, feet_on_node=[[23, 24]],
                             fade_from=0.1, shots=[(10, "trepando (cargada: Resbalón)", CHIMES_ALL, WHITE)]),
                 events=[E(4, "GrabStalk"), E(24, "Perch")],
                 notes="trepa desde el piso. Autorado sobre la caña de adentro: los pies arrancan en el piso 4.4 m abajo del "
                       "PerchNode. En [0, air_end] (el alcance) el código lleva el modelo desde donde está parado hasta el eje "
                       "de la caña y corrige la altura (perch - 4.4); desde GrabStalk (f4) va exacto en el PerchNode. Cargada "
                       "entera (Resbalón)")


def rot_z(v, deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2])


def clips(kit):
    out = [perch_idle(),
           dart_clip("PerchDart", 24, [14], "un dardo: baja la flauta de los hombros a la boca (aviso f8), sopla en f14 y "
                                            "vuelve"),
           dart_clip("PerchDart2", 34, [14, 24], "dos dardos (f14 y f24): reapunta entre los dos"),
           volley_clip("PerchVolley", 51, [17, 28, 39], 42, "Tres Notas: se echa atrás (Load f3), inspira, tres dardos "
                                                            "(f17, f28, f39) y Unload f42", 12),
           volley_clip("PerchVolley4", 48, [14, 22, 30, 39], 40, "Cuatro Notas (fase 3): Load f3, dardos f14, f22, f30, f39, "
                                                                 "Unload f40", 10),
           perch_whistle(), tala_shot(), hang_drop(kit), hang_dart2(), hang_climb(kit), perch_laugh(), perch_wobble(),
           stalk_sweep(), catapult_draw(), catapult_kick(), leap_crouch(), leap_air(), leap_grab(), climb()]
    return out
