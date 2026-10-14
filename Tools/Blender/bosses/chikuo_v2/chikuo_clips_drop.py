"""Clips de bajar al piso y volver arriba del Chikuō ermitaño (diseño chikuo_v2, 16.2): la Picada de la Grulla y su
aterrizaje, los Pies Enterrados, el Bastón que Cae, la garrocha y el agachado de la vuelta.

Los tramos en el aire van en el espacio 'air' (la raíz la lleva el código por el arco, los pies a la altura de la raíz):
la Picada arranca posada (la raíz en el PerchNode, que es donde están los pies) y desde LeaveStalk el código lleva la
misma raíz por el arco hasta el disco; en Contact el pie de la patada está a la altura de la raíz, que ya llegó al piso.
"""
from chikuo_anim import CClip, merge, free, grip, legs, staff_world, staff_spine
from chikuo_clips import (K, PERCH, STAFF_SHOULDERS, READY, READY_FEET, AIR, AIR_STAFF, GOLD, RED, feet_track, READY_R, READY_L,
                          ANKLE_Z)
from chikuo_clips_perch import shoulders_hold, kick_pose, R_SH, L_SH, FACE_EFFORT
from chikuo_clips_ground import staff_at, unit, face_track, E, FACE_FOCUS, FACE_SHOUT, plants, STAFF, FOOT_R, LO, HI

ANGRY = dict(jaw=10.0, lids=-0.2, brows=-14.0, cheeks=0.0, corners=(-0.006, 0.010))
# la pose con la que toca el piso de una patada voladora (el último cuadro de Dive, CatapultKick y PoleDive): la patada
# derecha clavada adelante, el cuerpo echado atrás, la izquierda recogida
LANDING = kick_pose(0.80, 0.22, 0.115, -30.0, land=True)


def dive():
    """La Picada de la Grulla (roja): posado, se agacha mirando a Kaito con la flauta todavía en los hombros (el aviso: el
    disco queda fijo a 0.50 s), salta de la caña (LeaveStalk f10), se arma en el aire con la patada del concepto y cae con
    el pie derecho clavado (Contact f28)."""
    P = merge(PERCH, shoulders_hold())
    crouch = merge(P, dict(hips=(0, -0.30, -0.70), hips_rot=(20, 0, 0), spine=(12, 0, 0), spine1=(10, 0, 0), spine2=(12, 0, 0),
                           neck=(-16, 0, 0), head=(-6, 0, 0)),
                   legs((-0.15, -0.115, 0.115), (0.15, -0.115, 0.115), rr=(0, 0, -26), rl=(0, 0, 26), kr=(-0.7, -0.8, 0.5),
                        kl=(0.7, -0.8, 0.5)))
    keys = [
        K(0, P),
        K(4, crouch, ease="inout"),
        K(8, crouch, dict(hips=(0, -0.31, -0.73), head=(-4, 0, 0)), ease="out"),
        K(10, merge(STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1)), grip("l", L_SH, elbow=(1, -0.2, -1))),
          dict(hips=(0, -0.32, -0.50), hips_rot=(24, 0, 0), spine=(10, 0, 0), spine2=(14, 0, 0), neck=(8, 0, 0), head=(10, 0, 0)),
          legs((-0.14, -0.08, 0.14), (0.14, -0.08, 0.14), rr=(-20, 0, -20), rl=(-20, 0, 20), kr=(-0.5, -1, 0.3), kl=(0.5, -1, 0.3)),
          ease="in"),
        K(12, merge(STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1))), dict(hips=(0, -0.10, -0.36), hips_rot=(6, 0, 0)),
          free("l", (0.68, 0.06, 1.88), elbow=(0.6, -0.2, -1), fing="open", chest=True),
          legs((-0.12, -0.30, 0.20), (0.14, 0.05, 0.30), rr=(-30, 0, 0), rl=(-20, 0, 0), kr=(0, -1, 0.4), kl=(0.2, -1, 0.6))),
        K(14, kick_pose(0.90, 0.10, 0.40, -16.0), free("l", (0.70, 0.16, 1.80), elbow=(1, 0.4, -0.3), fing="claw", chest=True),
          ease="inout"),
        K(17, kick_pose(0.88, 0.22, 0.28), ease="out"),
        K(22, kick_pose(0.86, 0.24, 0.22), ease="sine"),
        K(28, LANDING, ease="in"),
        K(29, kick_pose(0.78, 0.22, 0.115, -28.0, land=True), ease="out"),
    ]
    faces = face_track((0, "grin"), (4, FACE_FOCUS), (11, "surprise"), (14, ANGRY), (29, ANGRY))
    return CClip("Dive", 29, keys, tracks=[faces], lag={"head": 1.0},
                 spring_vel=lambda f: (0.0, -0.18 * max(0, f - 10), -0.10 * max(0, f - 10)),
                 timing=dict(space="air", tell=[2, 10], apex=8, contact=28, kind="dodge", glow=[FOOT_R] + list(LO), ring_m=1.6,
                             marker_m=1.6, chain_from="PERCH", chain_to="DIVE_LAND", bend=8.0, feet_on_node=[[0, 9]],
                             shots=[(8, "aviso (rojo)", (FOOT_R,) + LO, RED), (20, "en vuelo (rojo)", (FOOT_R,), RED)]),
                 events=[E(10, "LeaveStalk"), E(28, "Contact")],
                 notes="la Picada de la Grulla: posado hasta LeaveStalk f10 (la raíz en el PerchNode), después el código lleva "
                       "la raíz por el arco hasta el disco de 1.6 m; el pie derecho toca a la altura de la raíz en Contact f28")


def dive_land():
    """El aterrizaje de la patada voladora (Land f0): el pie derecho clavado adelante, el izquierdo cae atrás y la
    rodilla casi toca el piso (queda cortable 0.45 s); vuelve a la guardia con un paso atrás del pie de la patada."""
    low = merge(READY, dict(hips=(0.06, 0.08, -0.52), hips_rot=(22, 0, -8), spine=(10, 0, 4), spine1=(6, 0, 2), spine2=(6, 0, 0),
                            neck=(0, 0, 0), head=(-6, 0, 0), face="grin"),
                dict(foot_l=(0.24, 0.0, ANKLE_Z), foot_l_rot=(0, 0, 8), fsp_l=0.0),
                free("l", (0.50, -0.36, 0.72), elbow=(1, 0.3, -0.3), fing="open"))
    keys = [
        K(0, LANDING, travel=0.0),
        K(2, LANDING, dict(hips=(0.03, 0.18, -0.36), hips_rot=(-10, 0, -4)), free("l", (0.70, 0.0, 1.30), elbow=(1, 0.4, -0.3),
                                                                                   fing="claw", chest=True), travel=0.0, ease="out"),
        K(3, low, dict(hips=(0.04, 0.10, -0.44)), travel=0.0, ease="out"),
        K(6, low, travel=0.0, ease="inout"),
        K(8, low, dict(hips=(0.03, 0.10, -0.42), hips_rot=(18, 0, -12)), travel=-0.06, ease="inout"),
        # la tira de los hombros: sube y gira en el aire hacia adelante, las dos manos abiertas para atajarla
        K(9, low, dict(hips=(0.03, 0.08, -0.36), hips_rot=(14, 0, -14)), staff_spine((-1.00, 0.06, 2.08), (1, 0, 0.03), (0, -0.3, 1)),
          free("r", (-0.62, -0.10, 1.90), elbow=(-0.6, -0.2, -1), fing="open", chest=True),
          free("l", (0.40, -0.36, 1.30), elbow=(1, 0.3, -0.4), fing="open"), travel=-0.10, ease="out"),
        K(10, low, dict(hips=(0.02, 0.06, -0.32)), staff_world((-0.62, -0.10, 1.40), unit((0.75, -0.55, 0.38)), (0, -0.3, 1)),
          free("r", (-0.46, -0.20, 1.40), elbow=(-1, 0.3, -0.6), fing="open"),
          free("l", (0.24, -0.40, 1.30), elbow=(1, 0.2, -0.6), fing="open"), travel=-0.16, ease="lin"),
        K(11, READY, dict(hips=(0.01, 0.03, -0.26)), staff_world((-0.48, 0.12, 1.06), unit((0.42, -0.82, 0.39)), (0, -0.3, 1)),
          free("r", (-0.36, 0.0, 1.12), elbow=(-1, 0.4, -0.6), fing="grip_stalk"),
          free("l", (-0.10, -0.46, 1.26), elbow=(1, 0.2, -0.8), fing="grip_stalk"), travel=-0.24, ease="lin"),
        K(12, READY, dict(hips=(0.0, 0.0, -0.22)), travel=-0.30, ease="out"),
        K(14, READY, travel=-0.30, ease="inout"),
    ]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 8, -0.10, -0.40, 0.0, [(0, -30.0, "heel"), (3, 0.0, "heel")]), (12, 14, r0[0], r0[1] + 0.30, r0[2])),
            "l": plants({"free": (0, 2)}, (3, 14, l0[0], l0[1] + 0.30, l0[2]))}
    feet = feet_track(keys, 14, plan)
    faces = face_track((0, ANGRY), (3, "surprise"), (8, "grin"), (14, "grin"))
    return CClip("DiveLand", 14, keys, tracks=[feet, faces], lag={"head": 1.0},
                 timing=dict(space="ground", open=[0, 14], chain_from="DIVE_LAND", chain_to="READY", hang_scale=0.5),
                 events=[E(0, "Land")], notes="aterriza agachado con el pie de la patada clavado (Land f0); cortable 0.45 s")


SUNK = 0.12                                       # los pies enterrados hasta el tobillo


def feet_stuck():
    """Los Pies Enterrados: aterrizó y se le hundieron los pies hasta el tobillo; tironea de una pierna y de la otra
    revoleando los brazos y la flauta, se indigna, tira con las dos manos de la rodilla y al final salta afuera."""
    z = ANKLE_Z - SUNK
    stuck = legs((-0.10, -0.40, z), (0.24, 0.0, z), rr=(0, 0, 0), rl=(0, 0, 8), kr=(-0.3, -1, 0.2), kl=(0.4, -1, 0.2))
    base = merge(READY, stuck, dict(hips=(0.06, -0.04, -0.34), hips_rot=(10, 0, 0), spine=(4, 0, 0), spine2=(6, 0, 0), neck=(-6, 0, 0),
                                    head=(-12, 0, 0)),
                 staff_spine((-0.55, 0.40, 1.10), (0.05, 0.55, 0.83), (-1, 0, 0)), grip("r", 0.85, elbow=(-1, 0.4, -0.3)),
                 free("l", (0.50, -0.30, 1.20), elbow=(1, 0.3, -0.4), fing="open"))
    tug_r = dict(hips=(0.10, 0.02, -0.26), hips_rot=(4, 6, 6), spine2=(-4, 0, 6), head=(-20, 0, 8))
    tug_l = dict(hips=(0.02, -0.06, -0.26), hips_rot=(4, -6, -6), spine2=(-4, 0, -6), head=(-20, 0, -8))
    pull = merge(dict(hips=(0.04, -0.02, -0.46), hips_rot=(26, 0, 0), spine=(14, 0, 0), spine2=(12, 0, 0), head=(-24, 0, 0)),
                 free("l", (0.12, -0.40, 0.58), elbow=(1, 0.3, -0.2), fing="fist"))
    keys = [
        K(0, LANDING),
        K(4, base, dict(hips=(0.06, -0.04, -0.40)), ease="out"),
        K(8, base, ease="inout"),
        K(12, base, tug_r, free("l", (0.80, -0.10, 1.70), elbow=(0.5, 0.5, -0.5), fing="claw"), ease="inout"),
        K(16, base, ease="inout"),
        K(20, base, tug_l, free("l", (0.70, -0.40, 1.80), elbow=(0.5, 0.5, -0.5), fing="claw"), ease="inout"),
        K(24, base, ease="inout"),
        K(29, base, pull, ease="inout"),
        K(33, base, pull, dict(hips=(0.04, 0.0, -0.42), head=(-30, 0, 0)), ease="sine"),
        K(37, base, pull, dict(hips=(0.04, -0.02, -0.48)), ease="sine"),
        K(41, base, dict(hips=(0.04, -0.04, -0.40)), ease="inout"),
        # salta afuera: la flauta pasa por delante del hombro a la guardia
        K(42, base, dict(hips=(0.04, -0.03, -0.30)), staff_at((-0.42, 0.0, 1.40), unit((0.30, -0.60, 0.74)), 0.60),
          grip("r", 0.60, elbow=(-1, 0.4, -0.5)), free("l", (0.40, -0.30, 1.30), elbow=(1, 0.3, -0.4), fing="open"), ease="out"),
        K(44, READY, dict(hips=(0.02, 0.0, -0.06), hips_rot=(-4, 0, -12)),
          legs((-0.22, 0.10, 0.40), (0.24, -0.10, 0.38), rr=(-20, 0, -30), rl=(-20, 0, 8), kr=(-0.6, -1, 0), kl=(0.3, -1, 0)),
          ease="out"),
        K(48, READY, ease="in"),
    ]
    faces = face_track((0, ANGRY), (4, "surprise"), (10, FACE_EFFORT), (18, ANGRY), (26, "surprise"), (30, FACE_EFFORT),
                       (42, "surprise"), (46, "laugh"), (48, "grin"))
    return CClip("FeetStuck", 48, keys, tracks=[faces], lag={"head": 1.0},
                 timing=dict(space="ground", open=[0, 44], chain_from="DIVE_LAND", chain_to="READY", sunk=SUNK + 0.04, fade_to=0.1),
                 notes="Pies Enterrados (1.6 s abierto): los pies hundidos 12 cm, tironea y salta afuera al final")


def staff_drop():
    """El Bastón que Cae (dorado): posado, alza la flauta de los hombros sobre la cabeza con las dos manos, salta de la caña
    (LeaveStalk f6) y cae al lado de Kaito (Land f19) con la flauta arriba (apex f20), la baja de golpe en un arco de 90°
    (Contact f26)."""
    P = merge(PERCH, shoulders_hold())
    lift = lambda dz: merge(staff_spine((-1.00, 0.06, 1.95 + dz), (1, 0, 0.03), (0, -0.3, 1)), grip("r", R_SH, elbow=(-0.6, -0.2, -1)),
                            grip("l", L_SH, elbow=(0.6, -0.2, -1)))
    over = lambda: merge(staff_spine((0.0, 0.10, 2.55), unit((0.10, 0.62, 0.78)), (1, 0, 0)), grip("r", 0.20, elbow=(-1, -0.2, 0.3)),
                         grip("l", 0.62, elbow=(1, -0.2, 0.3)))
    one = lambda: merge(staff_spine((-0.30, 0.00, 2.45), unit((0.30, 0.55, 0.78)), (1, 0, 0)), grip("r", 0.28, elbow=(-1, -0.2, 0.3)),
                        free("l", (0.66, -0.10, 2.05), elbow=(0.6, -0.2, -0.6), fing="open", chest=True))
    land_up = merge(READY, over(), dict(hips=(0.0, 0.0, -0.36), hips_rot=(4, 0, -6), spine=(-4, 0, 0), spine1=(-6, 0, 0),
                                        spine2=(-4, 0, 0), neck=(-6, 0, 0), head=(-12, 0, 0)))
    smash = merge(READY, staff_at((-0.06, -0.62, 0.96), unit((0.04, -0.86, -0.50)), 0.20), grip("r", 0.20, elbow=(-1, 0.3, -0.6)),
                  grip("l", 0.62, elbow=(1, 0.3, -0.6)),
                  dict(hips=(0.04, 0.0, -0.40), hips_rot=(26, 0, -4), spine=(12, 0, 0), spine1=(8, 0, 0), spine2=(6, 0, 0),
                       neck=(-16, 0, 0), head=(-18, 0, 0)))
    keys = [
        K(0, P),
        K(3, P, lift(0.40), dict(hips=(0, -0.32, -0.66), hips_rot=(14, 0, 0), spine2=(4, 0, 0), head=(-6, 0, 0)), ease="inout"),
        K(6, lift(0.62), dict(hips=(0, -0.20, -0.40), hips_rot=(10, 0, 0), spine=(-4, 0, 0), spine2=(-2, 0, 0), head=(-10, 0, 0)),
          legs((-0.14, -0.06, 0.14), (0.14, -0.06, 0.14), rr=(-20, 0, -20), rl=(-20, 0, 20), kr=(-0.5, -1, 0.3), kl=(0.5, -1, 0.3)),
          ease="in"),
        K(10, one(), dict(hips=(0, 0.0, -0.20), hips_rot=(-6, 0, 0), spine=(-6, 0, 0), spine2=(-4, 0, 0), head=(-14, 0, 0)),
          legs((-0.16, -0.20, 0.40), (0.16, 0.05, 0.30), rr=(-30, 0, -10), rl=(-30, 0, 10), kr=(-0.3, -1, 0.3), kl=(0.3, -1, 0.3)),
          ease="out"),
        K(16, over(), dict(hips=(0, 0.0, -0.12), hips_rot=(-4, 0, -4), spine=(-6, 0, 0), spine2=(-4, 0, 0), head=(-14, 0, 0)),
          legs((-0.26, 0.10, 0.20), (0.24, -0.20, 0.24), rr=(-10, 0, -30), rl=(-10, 0, 8), kr=(-0.6, -1, 0), kl=(0.3, -1, 0)),
          ease="sine"),
        K(19, land_up, ease="in"),
        K(20, land_up, dict(hips=(0.0, 0.0, -0.32)), ease="out"),
        K(22, land_up, dict(hips=(0.0, 0.02, -0.28), spine1=(-8, 0, 0)), ease="inout"),
        K(24, merge(READY, staff_at((-0.02, -0.40, 1.90), unit((0.04, -0.50, 0.86)), 0.20), grip("r", 0.20, elbow=(-1, 0.0, -0.4)),
                    grip("l", 0.62, elbow=(1, 0.0, -0.4)), dict(hips=(0.04, -0.02, -0.26), hips_rot=(10, 0, -4), spine=(4, 0, 0))),
          ease="in"),
        K(26, smash, ease="in"),
        K(27, smash, dict(hips=(0.04, 0.0, -0.41)), ease="out"),
    ]
    faces = face_track((0, "grin"), (3, FACE_FOCUS), (7, "laugh"), (18, FACE_FOCUS), (25, FACE_SHOUT), (27, FACE_SHOUT))
    return CClip("StaffDrop", 27, keys, tracks=[faces], lag={"head": 1.0},
                 spring_vel=lambda f: (0.0, -0.15 * min(max(0, f - 6), 13), -0.12 * min(max(0, f - 6), 13)),
                 timing=dict(space="air", tell=[2, 20], apex=20, contact=26, active=[25, 27], kind="parry", glow=[STAFF] + list(HI),
                             reach_m=2.4, arc_deg=90.0, air=[6, 19], chain_from="PERCH", chain_to="STAFF_DOWN", bend=8.0,
                             feet_on_node=[[0, 5]], shots=[(20, "aviso (dorado)", (STAFF,) + HI, GOLD)]),
                 events=[E(6, "LeaveStalk"), E(19, "Land"), E(26, "Contact")],
                 notes="el Bastón que Cae: posado hasta LeaveStalk f6, el código lo lleva por el arco hasta 1.6 m de Kaito "
                       "(Land f19: los pies a la altura de la raíz en el piso); la flauta arriba en f20, el bastonazo de 90° "
                       "y 2.4 m en Contact f26")


def staff_drop_recover():
    """Después del bastonazo: saca la flauta del piso, se endereza resoplando y vuelve a la guardia (la Contra: 0.40 s)."""
    end = merge(READY, staff_at((-0.06, -0.62, 0.96), unit((0.04, -0.86, -0.50)), 0.20), grip("r", 0.20, elbow=(-1, 0.3, -0.6)),
                grip("l", 0.62, elbow=(1, 0.3, -0.6)),
                dict(hips=(0.04, 0.0, -0.41), hips_rot=(26, 0, -4), spine=(12, 0, 0), spine1=(8, 0, 0), spine2=(6, 0, 0),
                     neck=(-16, 0, 0), head=(-18, 0, 0)))
    keys = [
        K(0, end),
        K(4, end, staff_at((-0.08, -0.55, 1.00), unit((0.10, -0.90, -0.30)), 0.20), dict(hips=(0.04, 0.0, -0.38), head=(-10, 0, 0)),
          ease="inout"),
        K(8, READY, dict(hips=(0.0, 0.0, -0.20), spine2=(6, 0, 4)), ease="inout"),
        K(12, READY, ease="inout"),
    ]
    r0, l0 = READY_R, READY_L
    feet = feet_track(keys, 12, {"r": plants((0, 12, r0[0], r0[1], r0[2])), "l": plants((0, 12, l0[0], l0[1], l0[2]))})
    faces = face_track((0, FACE_SHOUT), (3, dict(FACE_FOCUS, cheeks=0.5)), (8, "grin"), (12, "grin"))
    return CClip("StaffDropRecover", 12, keys, tracks=[feet, faces], lag={"head": 1.0},
                 timing=dict(space="ground", open=[0, 12], chain_from="STAFF_DOWN", chain_to="READY"),
                 notes="vuelve a la guardia después del Bastón que Cae (la Contra, 0.40 s)")


def vault():
    """La garrocha (invulnerable): da un paso, clava el bastón adelante (Plant f6), salta colgado de él (LeaveStalk f9),
    pasa arriba del bastón empujándolo, lo arranca del piso al subir y vuela en la pose del salto (el código lleva el arco
    de 0.9 s) hasta agarrar la caña (GrabStalk f27: sigue LeapGrab)."""
    plant = staff_world((0.05, -1.05, -0.10), unit((-0.04, 0.42, 0.91)), (0, -1, 0))
    keys = [
        K(0, READY, travel=0.0),
        K(3, READY, dict(hips=(0.0, -0.10, -0.22), hips_rot=(10, 0, -8)), staff_at((-0.20, -0.30, 1.30), unit((0.10, -0.80, 0.40)), 0.80),
          grip("r", 0.80, elbow=(-1, 0.3, -0.5)), grip("l", 1.20, elbow=(1, 0.3, -0.5)), travel=0.15),
        K(6, plant, grip("r", 1.30, elbow=(-1, 0.3, -0.5)), grip("l", 1.62, elbow=(1, 0.3, -0.5)),
          dict(hips=(0.0, -0.20, -0.30), hips_rot=(16, 0, 0), spine2=(8, 0, 0), head=(-10, 0, 0)), READY_FEET, travel=0.30, ease="out"),
        K(9, plant, grip("r", 1.30, elbow=(-1, 0.3, 0.2)), grip("l", 1.62, elbow=(1, 0.3, 0.2)),
          dict(hips=(0.0, -0.30, 0.10), hips_rot=(30, 0, 0), spine=(10, 0, 0), spine2=(10, 0, 0), head=(-14, 0, 0)),
          legs((-0.14, -0.10, 0.40), (0.14, -0.30, 0.60), rr=(-30, 0, 0), rl=(-30, 0, 0), kr=(-0.3, -1, 0.3), kl=(0.3, -1, 0.3)),
          travel=0.30, ease="in"),
        K(13, merge(AIR_STAFF, grip("r", 0.95, elbow=(-1, 0.4, -0.4)), free("l", (0.60, -0.30, 1.70), elbow=(0.5, 0.5, -0.5), fing="claw")),
          dict(hips=(0.0, -0.30, 0.20), hips_rot=(-10, 0, 0), spine=(-4, 0, 0), head=(-10, 0, 0)),
          legs((-0.18, -0.10, 0.70), (0.18, -0.20, 0.80), rr=(-30, 0, 0), rl=(-30, 0, 0), kr=(-0.3, -1, 0.3), kl=(0.3, -1, 0.3), hips=True),
          travel=0.30, ease="out"),
        K(19, AIR, travel=0.30, ease="inout"),
        K(27, AIR, dict(hips=(0, 0.04, -0.30), head=(-6, 0, 0)), travel=0.30, ease="sine"),
    ]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 4, r0[0], r0[1], r0[2], [(2, 0.0, "ball"), (4, 20.0, "ball")]), {"free": (5, 27)}),
            "l": plants((0, 1, l0[0], l0[1], l0[2]), (4, 7, l0[0], l0[1] - 0.30, l0[2], [(6, 0.0, "ball"), (7, 26.0, "ball")]),
                        {"free": (8, 27)})}
    feet = feet_track(keys, 27, plan)
    faces = face_track((0, "grin"), (5, FACE_FOCUS), (10, "laugh"), (27, "grin"))
    return CClip("Vault", 27, keys, tracks=[feet, faces], lag={"head": 1.0},
                 spring_vel=lambda f: (0.0, -0.20 * max(0, f - 9), 0.0),
                 timing=dict(space="ground", air=[9, 27], chain_from="READY", chain_to="AIR", invulnerable=[0, 27],
                             root_offset=["LeapAir", 0, 9], carried_from=9, staff_in_floor=0.12),
                 events=[E(6, "Plant"), E(9, "LeaveStalk"), E(27, "GrabStalk")],
                 notes="la garrocha: Plant f6 (el bastón 1 m adelante), LeaveStalk f9 (desde ahí el código lleva la raíz por "
                       "el arco como en LeapAir: root_offset_m), GrabStalk f27 (sigue LeapGrab)")


def jump_crouch():
    """El agachado de la vuelta arriba (cortable: Tropiezo): mira la caña (la cabeza gira primero), se hunde, alza la flauta
    y salta (LeaveStalk f9: sigue LeapAir)."""
    deep = merge(READY, dict(hips=(0.0, 0.0, -0.46), hips_rot=(20, 0, -8), spine2=(12, 0, 0), neck=(-6, 0, 6), head=(-6, 0, 12)))
    keys = [
        K(0, READY),
        K(3, deep, dict(hips=(0.0, 0.0, -0.36)), ease="inout"),
        K(5, deep, staff_at((-0.40, -0.10, 1.40), unit((0.10, -0.30, 0.95)), 0.70), grip("r", 0.70, elbow=(-1, 0.4, -0.5)),
          free("l", (0.40, -0.36, 1.10), elbow=(1, 0.3, -0.4), fing="open"), ease="inout"),
        K(7, deep, AIR_STAFF, grip("r", 0.95, elbow=(-1, 0.4, -0.4)), free("l", (0.50, -0.20, 0.80), elbow=(1, 0.4, -0.2), fing="open"),
          ease="out"),
        K(9, merge(AIR, dict(hips=(0, -0.05, -0.18), hips_rot=(6, 0, 0))),
          legs((-0.18, 0.10, 0.20), (0.18, -0.20, 0.30), rr=(-30, 0, -10), rl=(-40, 0, 10), kr=(-0.2, -1, 0), kl=(0.2, -1, 0.3)),
          ease="in"),
    ]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 8, r0[0], r0[1], r0[2], [(6, 0.0, "ball"), (8, 28.0, "ball")]), {"free": (9, 9)}),
            "l": plants((0, 8, l0[0], l0[1], l0[2], [(6, 0.0, "ball"), (8, 28.0, "ball")]), {"free": (9, 9)})}
    feet = feet_track(keys, 9, plan)
    faces = face_track((0, "grin"), (3, FACE_FOCUS), (9, "grin"))
    return CClip("JumpCrouch", 9, keys, tracks=[feet, faces], lag={"head": -1.0},
                 timing=dict(space="ground", chain_from="READY", chain_to="AIR", fade_to=0.08, root_offset=["LeapAir", 0, 9],
                             carried_from=9),
                 events=[E(9, "LeaveStalk")], notes="el agachado del salto desde el piso (cortable: Tropiezo); LeaveStalk f9")


def clips(kit):
    return [dive(), dive_land(), feet_stuck(), staff_drop(), staff_drop_recover(), vault(), jump_crouch()]
