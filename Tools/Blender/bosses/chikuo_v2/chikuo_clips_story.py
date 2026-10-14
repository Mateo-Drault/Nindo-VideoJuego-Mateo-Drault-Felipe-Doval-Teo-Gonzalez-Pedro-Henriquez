"""Las escenas del Chikuō ermitaño (diseño chikuo_v2, 16.5 y la sección 4): la presentación colgado de O1, los dos
cambios de fase y la derrota con la reverencia.
"""
import chikuo_rig as CR
from chikuo_anim import CClip, merge, free, grip, legs, staff_world, staff_lips
from chikuo_clips import K, PERCH, HANG, READY, AIR, AIR_STAFF, feet_track, READY_R, READY_L
from chikuo_clips_perch import shoulders_hold, hang_pipe, aim_dir, FACE_PUFF, FACE_BLOWN
from chikuo_clips_ground import (FLUTE, FLUTE_AT, staff_at, unit, face_track, E, plants, FACE_FOCUS)
from chikuo_clips_react import DAZED_SIT, DAZED_LIE, OUCH

UP = 1.0                                          # colgado de la presentación: un metro más arriba que HANG


def up(c, dz=UP):
    """Una pose de colgado corrida dz para arriba (la cadera y los pies; la flauta va con la boca)."""
    c = dict(c)
    h = c["hips"]
    c["hips"] = (h[0], h[1], h[2] + dz)
    for s in "rl":
        f = c.get("foot_" + s)
        if f is not None:
            c["foot_" + s] = (f[0], f[1], f[2] + dz)
    return c


# tocando la flauta de costado cabeza abajo (la pose de la hoja): la flauta horizontal delante de la boca hacia su derecha
# (con el cuerpo dado vuelta su derecha queda en +X), los dedos en los agujeros, los ojos cerrados
HANG_FLUTE = merge(up(HANG), dict(face="flute", head=(-14, 0, 0)), staff_lips(FLUTE_AT, unit((0.98, 0.10, -0.10)), (0, -1, -0.2)),
                   grip("l", FLUTE_AT - 0.20, elbow=(1, -0.2, 0.6), fing="flute"),
                   grip("r", FLUTE_AT - 0.62, elbow=(-1, -0.2, 0.6), fing="flute"))


def intro():
    """La presentación (6.5 s): colgado cabeza abajo de las corvas en la punta de O1 tocando la flauta de costado con los
    ojos cerrados; abre un ojo, sonríe, se ríe a carcajadas colgado, da vuelta la flauta de cerbatana y le sopla un dardo a
    los pies de Kaito (DartSpawn f135), se suelta, gira de costado sobre la cadera y cae agachado en el posado (Perch f175)."""
    P = merge(PERCH, shoulders_hold())
    sway = lambda d: dict(hips=(0.0, -0.27 + 0.10 * d, -1.56 + UP), hips_rot=(12 + 10 * d, 180, 0))
    keys = [K(0, HANG_FLUTE)]
    for i, f in enumerate(range(15, 61, 15)):
        keys.append(K(f, HANG_FLUTE, sway(0.5 if i % 2 == 0 else -0.5), dict(head=(-14 + 3 * (i % 2), 0, 0)), ease="sine"))
    laugh = merge(HANG_FLUTE, dict(face="laugh", head=(-26, 0, 0), neck=(-14, 0, 0)),
                  staff_lips(FLUTE_AT, unit((0.90, 0.20, -0.38)), (0, -1, -0.2)))
    keys += [
        K(66, HANG_FLUTE, dict(head=(-18, 0, 4)), ease="inout"),
        K(74, HANG_FLUTE, dict(head=(-20, 0, 8), face="grin"), ease="inout"),
        K(82, laugh, sway(0.6), ease="out"),
    ]
    for f in range(88, 113, 6):
        keys.append(K(f, laugh, sway(0.4 if (f // 6) % 2 else 0.7), dict(spine2=(6 if (f // 6) % 2 else -2, 0, 0)), ease="sine"))
    pipe = up(hang_pipe(aim=aim_dir(55)))
    keys += [
        K(118, HANG_FLUTE, dict(face="grin"), staff_lips(FLUTE_AT, unit((0.60, 0.40, -0.69)), (0, -1, -0.2)), ease="inout"),
        K(124, pipe, dict(face=FACE_PUFF), ease="inout"),
        K(133, pipe, dict(face=FACE_PUFF, head=(-24, 0, 0)), ease="sine"),
        K(135, up(hang_pipe(dict(head=(-28, 0, 0)), aim=aim_dir(51))), dict(face=FACE_BLOWN), ease="snap"),
        K(140, pipe, dict(face="grin"), ease="out"),
        # se suelta: la flauta a los hombros, las piernas se abren del culmo y el cuerpo gira de costado sobre la cadera
        K(148, up(HANG), dict(face="grin", hips_rot=(12, 180, 0)),
          staff_lips(CR.STAFF_LEN, (0.0, 0.70, -0.71), (0, 0, -1)), grip("l", CR.STAFF_LEN - 0.17, elbow=(1, -0.2, 0.6)),
          grip("r", CR.STAFF_LEN - 0.32, elbow=(-1, -0.2, 0.6)), ease="inout"),
        K(152, up(HANG), dict(face="laugh", hips=(0.0, -0.30, -1.50 + UP), hips_rot=(10, 180, 0)),
          legs((0.30, -0.20, 1.40), (-0.30, -0.10, 1.50), rr=(-40, 180, 0), rl=(-40, 180, 0), kr=(1.0, -0.3, 0.3), kl=(-1.0, -0.3, 0.3)),
          staff_lips(CR.STAFF_LEN, (0.0, 0.70, -0.71), (0, 0, -1)), grip("l", CR.STAFF_LEN - 0.17, elbow=(1, -0.2, 0.6)),
          grip("r", CR.STAFF_LEN - 0.32, elbow=(-1, -0.2, 0.6)), ease="out"),
        K(160, AIR, dict(hips=(0.10, -0.30, -0.40 + 0.30), hips_rot=(0, 90, 0), face="laugh"),
          legs((-0.10, -0.40, 0.40), (0.20, -0.20, 0.60), rr=(-30, 0, 0), rl=(-30, 0, 0), kr=(-0.4, -1, 0.3), kl=(0.4, -1, 0.3),
               hips=True), ease="lin"),
        K(168, AIR, dict(hips=(0.0, -0.30, -0.40), hips_rot=(6, 20, 0), face="grin"), ease="out"),
        K(175, P, dict(hips=(0, -0.33, -0.66), hips_rot=(16, 0, 0), spine2=(12, 0, 0)), ease="in"),
        K(181, P, dict(hips=(0, -0.34, -0.60)), ease="out"),
        K(195, P, ease="inout"),
    ]
    blink = [K(0, wink_r=0.0, wink_l=0.0), K(60, wink_r=0.0, wink_l=0.0), K(62, wink_r=1.0, wink_l=0.0),
             K(70, wink_r=1.0, wink_l=0.0), K(73, wink_r=0.0, wink_l=0.0), K(195, wink_r=0.0, wink_l=0.0)]
    faces = face_track((0, "flute"), (58, "flute"), (62, dict(CR.FACES["flute"], lids=0.0)), (70, dict(CR.FACES["flute"], lids=0.0)),
                       (74, "grin"), (82, "laugh"), (114, "laugh"), (118, "grin"), (124, FACE_PUFF), (134, FACE_PUFF),
                       (135, FACE_BLOWN), (140, "grin"), (152, "laugh"), (168, "grin"), (195, "grin"))
    return CClip("Intro", 195, keys, tracks=[blink, faces], lag={"head": 1.5},
                 timing=dict(space="perch", chain_to="PERCH", bend=6.0, stalk="O1", cloak_hang=0.97, preroll=2.0,
                             feet_on_node=[[175, 195]]),
                 events=[E(135, "DartSpawn"), E(148, "LeaveStalk"), E(175, "Perch")],
                 notes="colgado de las corvas 1 m arriba del PerchNode de O1 tocando la flauta; DartSpawn f135 (a los pies de "
                       "Kaito), se suelta en f148 y queda posado en f175 (Perch)")


def phase_bow():
    """El cambio 1 (4.0 s): cae sentado riéndose (lo bajaron del bambú), se saca una hoja de la barba y la mira, se levanta de
    un salto, se lleva la flauta de costado y toca tres notas (Note f70, f85, f100: en la tercera las cañas se inclinan) y
    vuelve a la guardia."""
    laugh = merge(DAZED_SIT, dict(face="laugh", hips_rot=(-30, 0, 0), spine=(6, 0, 0), spine1=(4, 0, 0), spine2=(0, 0, 0),
                                  neck=(-10, 0, 0), head=(-20, 0, 0)))
    leaf = merge(DAZED_SIT, dict(face="grin", hips_rot=(-20, 0, 0), spine=(10, 0, 0), spine1=(8, 0, 0), spine2=(6, 0, 0), neck=(4, 0, 0),
                                 head=(16, 0, -6)),
                 free("l", (0.06, -0.40, 1.42), (-0.2, -0.6, 0.8), (0.9, -0.3, 0.2), elbow=(1, 0.2, -0.6), fing="relaxed"))
    look = merge(leaf, dict(head=(8, 0, 10)), free("l", (0.26, -0.62, 1.48), (0.0, -0.4, 0.9), (0.9, -0.2, 0.2), elbow=(1, 0.2, -0.6),
                                                fing=dict(fing=(30, 60, 70, 74), tip=(20, 60, 70, 74), spread=0.0, thumb=(40, 30))))
    note = lambda f: [K(f, FLUTE, dict(hips=(0.0, 0.01, -0.13), spine2=(-4, 0, 4), head=(-9, 0, 10), clav_r=(0, 0, 3), clav_l=(0, 0, -3)),
                        ease="out"),
                      K(f + 6, FLUTE, dict(spine2=(-3, 0, 1), head=(-7, 0, 5)), ease="sine")]
    keys = [K(0, DAZED_SIT, dict(hips=(0.0, 0.06, 0.40 - 1.06), face="surprise")),
            K(3, DAZED_SIT, dict(hips=(0.0, 0.08, 0.20 - 1.06), face=OUCH), ease="in"),
            K(7, laugh, ease="out")]
    for f in range(12, 37, 6):
        keys.append(K(f, laugh, dict(spine2=(4 if (f // 6) % 2 else -4, 0, 0), head=(-24 if (f // 6) % 2 else -16, 0, 0)), ease="sine"))
    keys += [K(42, leaf, ease="inout"), K(46, leaf, dict(head=(18, 0, -4)), ease="inout"), K(52, look, ease="inout"),
             K(56, look, free("l", (0.50, -0.70, 1.30), elbow=(1, 0.3, -0.5), fing="open"), ease="snap"),
             K(61, READY, dict(hips=(0.0, 0.02, -0.40), hips_rot=(16, 0, -10), face="grin"), ease="out"),
             K(66, FLUTE, staff_lips(FLUTE_AT, unit((0.95, 0.15, 0.25)), (0, -1, 0.2)), ease="inout"),
             K(69, FLUTE, ease="inout")]
    for f in (70, 85, 100):
        keys += note(f)
    keys += [K(110, FLUTE, ease="inout"), K(120, READY, ease="inout")]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants({"free": (0, 58)}, (61, 112, -0.22, 0.10, -16.0), (116, 120, r0[0], r0[1], r0[2])),
            "l": plants({"free": (0, 58)}, (61, 120, l0[0], l0[1], l0[2]))}
    feet = feet_track(keys, 120, plan, lift=0.06)
    faces = face_track((0, "surprise"), (3, OUCH), (7, "laugh"), (38, "laugh"), (42, "grin"), (64, "grin"), (68, "flute"),
                       (112, "flute"), (116, "grin"), (120, "grin"))
    return CClip("PhaseBow", 120, keys, tracks=[feet, faces], lag={"head": 1.0},
                 timing=dict(space="ground", chain_from="DAZED_SIT", chain_to="READY", fade_from=0.1),
                 events=[E(70, "Note"), E(85, "Note"), E(100, "Note")],
                 notes="'Bailemos en el piso': cae sentado riéndose, la hoja de la barba, tres notas (Note f70, f85, f100)")


def phase_forest():
    """El cambio 2 (5.0 s): toca la frase entera con todo el cuerpo (Note f60: las cañas se enderezan; Note f90: nace la
    Madre), baja la flauta riéndose, clava el bastón y salta con la garrocha a la Madre (LeaveStalk f120, GrabStalk f150:
    sigue LeapGrab)."""
    sway = lambda d: dict(hips=(0.02 * d, 0.0, -0.12), hips_rot=(2, 3 * d, -6 + 4 * d), spine2=(-2, 0, 2 + 4 * d), head=(-6, 0, 8 + 6 * d))
    keys = [K(0, READY),
            K(8, READY, dict(hips=(0.0, 0.0, -0.16), spine2=(2, 0, 2), head=(-4, 0, 4)),
              staff_at((-0.30, -0.30, 1.30), unit((0.70, -0.30, 0.65)), 0.30), grip("r", 0.30, elbow=(-1, 0.3, -0.6)),
              free("l", (0.30, -0.40, 1.40), elbow=(1, 0.2, -0.6), fing="relaxed"), ease="inout"),
            K(14, FLUTE, ease="out")]
    for i, f in enumerate(range(22, 101, 8)):
        d = 1.0 if i % 2 == 0 else -1.0
        keys.append(K(f, FLUTE, sway(d), ease="sine"))
    keys += [K(60, FLUTE, dict(hips=(0.0, 0.02, -0.10), spine2=(-8, 0, 0), head=(-14, 0, 0), clav_r=(0, 0, 6), clav_l=(0, 0, -6)),
               ease="out"),
             K(90, FLUTE, dict(hips=(0.0, 0.02, -0.08), spine2=(-10, 0, 0), head=(-16, 0, 0), clav_r=(0, 0, 8), clav_l=(0, 0, -8)),
               ease="out")]
    keys = sorted(keys, key=lambda k: k.frame)
    plant = staff_world((0.05, -1.05, -0.10), unit((-0.04, 0.42, 0.91)), (0, -1, 0))
    keys += [K(104, FLUTE, dict(face="grin"), ease="inout"),
             K(110, READY, dict(hips=(0.0, -0.06, -0.24), hips_rot=(10, 0, -8)), staff_at((-0.20, -0.30, 1.30), unit((0.10, -0.80, 0.40)), 0.80),
               grip("r", 0.80, elbow=(-1, 0.3, -0.5)), grip("l", 1.20, elbow=(1, 0.3, -0.5)), ease="inout"),
             K(116, plant, grip("r", 1.30, elbow=(-1, 0.3, -0.5)), grip("l", 1.62, elbow=(1, 0.3, -0.5)),
               dict(hips=(0.0, -0.20, -0.30), hips_rot=(16, 0, 0), spine2=(8, 0, 0), head=(-10, 0, 0)), ease="out"),
             K(120, plant, grip("r", 1.30, elbow=(-1, 0.3, 0.2)), grip("l", 1.62, elbow=(1, 0.3, 0.2)),
               dict(hips=(0.0, -0.30, 0.10), hips_rot=(30, 0, 0), spine=(10, 0, 0), spine2=(10, 0, 0), head=(-14, 0, 0)),
               legs((-0.14, -0.10, 0.40), (0.14, -0.30, 0.60), rr=(-30, 0, 0), rl=(-30, 0, 0), kr=(-0.3, -1, 0.3), kl=(0.3, -1, 0.3)),
               ease="in"),
             K(126, merge(AIR_STAFF, grip("r", 0.95, elbow=(-1, 0.4, -0.4)), free("l", (0.60, -0.30, 1.70), elbow=(0.5, 0.5, -0.5), fing="claw")),
               dict(hips=(0.0, -0.30, 0.20), hips_rot=(-10, 0, 0), spine=(-4, 0, 0), head=(-10, 0, 0)),
               legs((-0.18, -0.10, 0.70), (0.18, -0.20, 0.80), rr=(-30, 0, 0), rl=(-30, 0, 0), kr=(-0.3, -1, 0.3), kl=(0.3, -1, 0.3), hips=True),
               ease="out"),
             K(134, AIR, ease="inout"),
             K(150, AIR, dict(hips=(0, 0.04, -0.30), head=(-6, 0, 0)), ease="sine")]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 8, r0[0], r0[1], r0[2]), (14, 112, -0.22, 0.10, -16.0), {"free": (117, 150)}),
            "l": plants((0, 114, l0[0], l0[1], l0[2], [(112, 0.0, "ball"), (116, 24.0, "ball")]), {"free": (117, 150)})}
    feet = feet_track(keys, 150, plan, lift=0.06)
    faces = face_track((0, "grin"), (12, "flute"), (100, "flute"), (104, "laugh"), (112, FACE_FOCUS), (122, "laugh"), (150, "grin"))
    return CClip("PhaseForest", 150, keys, tracks=[feet, faces], lag={"head": 1.0},
                 spring_vel=lambda f: (0.0, -0.20 * max(0, f - 120), 0.0),
                 timing=dict(space="ground", air=[120, 150], chain_from="READY", chain_to="AIR", root_offset=["LeapAir", 0, 120],
                             carried_from=120, staff_in_floor=0.12),
                 events=[E(60, "Note"), E(90, "Note"), E(120, "LeaveStalk"), E(150, "GrabStalk")],
                 notes="'Que cante todo el bosque': la frase entera (Note f60, f90), la garrocha a la Madre (LeaveStalk f120: "
                       "desde ahí el código lleva la raíz como en LeapAir), GrabStalk f150 (sigue LeapGrab)")


# sentado con las piernas cruzadas y la flauta sobre las rodillas (la reverencia y la meditación)
CROSS = merge(dict(hips=(0.0, 0.04, 0.22 - 1.06), hips_rot=(-6, 0, 0), spine=(4, 0, 0), spine1=(2, 0, 0), spine2=(2, 0, 0),
                   neck=(-2, 0, 0), head=(-2, 0, 0), face="flute"),
              legs((0.14, -0.40, 0.10), (-0.16, -0.30, 0.12), rr=(-10, 30, 60), rl=(-10, -30, -60), kr=(-1.0, -0.5, 0.25),
                   kl=(1.0, -0.5, 0.25)),
              staff_world((-1.02, -0.50, 0.40), (1.0, 0.0, 0.0), (0, -0.3, 1)),
              free("r", (-0.30, -0.50, 0.50), (0.2, -0.6, -0.8), (-0.4, -0.7, 0.4), elbow=(-1, 0.3, -0.5), fing="relaxed"),
              free("l", (0.30, -0.50, 0.50), (-0.2, -0.6, -0.8), (0.4, -0.7, 0.4), elbow=(1, 0.3, -0.5), fing="relaxed"))


def defeat():
    """La derrota (5.5 s): el último golpe lo tira de espaldas riéndose a carcajadas, patalea de risa, se sienta con las
    piernas cruzadas, se seca una lágrima con el nudillo, pone la flauta sobre las rodillas y hace la reverencia."""
    lie = merge(DAZED_LIE, dict(face="laugh", neck=(10, 0, 0), head=(6, 0, 0)))
    keys = [K(0, READY),
            K(4, READY, dict(hips=(0.0, 0.14, -0.30), hips_rot=(-14, 0, -14), spine2=(-10, 0, 0), head=(-20, 0, 0), face=OUCH), ease="out"),
            K(10, lie, dict(hips=(0.0, 0.10, 0.24 - 1.06)), ease="in"),
            K(14, lie, ease="out")]
    for f in range(20, 57, 6):
        keys.append(K(f, lie, legs((-0.20, -0.66, 0.50 + (0.2 if (f // 6) % 2 else 0)), (0.20, -0.56, 0.74 - (0.2 if (f // 6) % 2 else 0)),
                                   rr=(-20, 0, -10), rl=(-20, 0, 10), kr=(-0.3, -0.3, 1.0), kl=(0.3, -0.3, 1.0)),
                      dict(head=(10, 0, 0) if (f // 6) % 2 else (2, 0, 0)), ease="sine"))
    sit = merge(CROSS, dict(face="laugh", head=(-12, 0, 0), neck=(-6, 0, 0)))
    wipe = merge(CROSS, dict(face=dict(CR.FACES["grin"], lids=0.7), head=(4, 0, 8)),
                 free("l", (0.06, -0.42, 1.92), (-0.5, -0.3, 0.8), (0.4, -0.8, 0.2), elbow=(1, 0.2, -0.6), fing="fist"))
    bow = merge(CROSS, dict(hips_rot=(10, 0, 0), spine=(14, 0, 0), spine1=(12, 0, 0), spine2=(10, 0, 0), neck=(10, 0, 0), head=(14, 0, 0)),
                free("r", (-0.30, -0.56, 0.46), (0.2, -0.6, -0.8), (-0.4, -0.7, 0.4), elbow=(-1, 0.3, -0.5), fing="relaxed"),
                free("l", (0.30, -0.56, 0.46), (-0.2, -0.6, -0.8), (0.4, -0.7, 0.4), elbow=(1, 0.3, -0.5), fing="relaxed"))
    keys += [K(62, lie, ease="inout"),
             K(72, sit, dict(hips_rot=(-30, 0, 0), spine=(10, 0, 0)), ease="inout"),
             K(82, sit, ease="out")]
    for f in range(88, 101, 6):
        keys.append(K(f, sit, dict(head=(-8 if (f // 6) % 2 else -14, 0, 0)), ease="sine"))
    keys += [K(108, wipe, ease="inout"), K(114, wipe, dict(head=(6, 0, 6)), ease="sine"), K(120, wipe, ease="sine"),
             K(128, CROSS, dict(face="grin"), ease="inout"),
             K(134, CROSS, ease="inout"),
             K(146, bow, ease="inout"),
             K(156, bow, dict(head=(16, 0, 0)), ease="sine"),
             K(165, bow, ease="inout")]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 3, r0[0], r0[1], r0[2]), {"free": (4, 165)}), "l": plants((0, 3, l0[0], l0[1], l0[2]), {"free": (4, 165)})}
    feet = feet_track(keys, 165, plan)
    faces = face_track((0, "grin"), (4, OUCH), (12, "laugh"), (90, "laugh"), (104, "grin"), (128, "grin"), (140, "flute"), (165, "flute"))
    return CClip("Defeat", 165, keys, tracks=[feet, faces], lag={"head": 1.0, "spine2": 0.5},
                 timing=dict(space="ground", chain_from="READY", chain_to="CROSS", legs_cross=[[72, 165]]),
                 notes="la derrota: de espaldas riéndose, se sienta con las piernas cruzadas, se seca una lágrima y hace la "
                       "reverencia con la flauta sobre las rodillas")


def defeat_idle():
    """Meditando sentado con las piernas cruzadas y la flauta sobre las rodillas: respira despacio (el pecho y los hombros
    suben), los ojos cerrados. Loop de 60."""
    keys = [K(0, CROSS), K(30, CROSS, dict(hips=(0.0, 0.04, 0.23 - 1.06), spine1=(0, 0, 0), spine2=(-1, 0, 0), clav_r=(0, 0, 3),
                                           clav_l=(0, 0, -3), head=(-3, 0, 0)), ease="sine"),
            K(60, CROSS, ease="sine")]
    return CClip("DefeatIdle", 60, keys, loop=True, lag={"head": 3.0},
                 timing=dict(space="ground", chain_from="CROSS", chain_to="CROSS", legs_cross=[[0, 60]]),
                 notes="meditando: respira; loop")


def clips(kit):
    return [intro(), phase_bow(), phase_forest(), defeat(), defeat_idle()]
