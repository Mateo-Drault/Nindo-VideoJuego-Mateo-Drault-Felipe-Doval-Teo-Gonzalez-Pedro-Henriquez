"""Clips de bajar al piso y volver arriba del Chikuō ermitaño (diseño chikuo_v2, 16.2): la Picada de la Grulla y su
aterrizaje, los Pies Enterrados, el Bastón que Cae, la garrocha y el agachado de la vuelta.

Los tramos en el aire van en el espacio 'air' (la raíz la lleva el código por el arco, los pies a la altura de la raíz):
la Picada arranca posada (la raíz en el PerchNode, que es donde están los pies) y desde LeaveStalk el código lleva la
misma raíz por el arco hasta el disco; en Contact el pie de la patada está a la altura de la raíz, que ya llegó al piso.
"""
from nindo_anim import V
from chikuo_anim import CClip, merge, free, grip, legs, staff_world, staff_spine
from chikuo_clips import (K, PERCH, STAFF_SHOULDERS, READY, READY_FEET, AIR, AIR_STAFF, GOLD, RED, feet_track, READY_R, READY_L,
                          ANKLE_Z, rolled, tossed, spine_mix)
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
    crouch = merge(P, dict(hips=(0, -0.34, -0.70), hips_rot=(20, 0, 0), spine=(12, 0, 0), spine1=(10, 0, 0), spine2=(12, 0, 0),
                           neck=(-16, 0, 0), head=(-6, 0, 0)),
                   legs((-0.19, -0.135, 0.115), (0.19, -0.135, 0.115), rr=(0, 0, -22), rl=(0, 0, 22), kr=(-0.7, -0.8, 0.5),
                        kl=(0.7, -0.8, 0.5)))
    keys = [
        K(0, P),
        K(4, crouch, ease="inout"),
        K(8, crouch, dict(hips=(0, -0.35, -0.73), head=(-4, 0, 0)), ease="out"),
        K(10, merge(STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1)), grip("l", L_SH, elbow=(1, -0.2, -1))),
          dict(hips=(0, -0.36, -0.50), hips_rot=(24, 0, 0), spine=(10, 0, 0), spine2=(14, 0, 0), neck=(8, 0, 0), head=(10, 0, 0)),
          legs((-0.14, -0.08, 0.14), (0.14, -0.08, 0.14), rr=(-20, 0, -20), rl=(-20, 0, 20), kr=(-0.5, -1, 0.3), kl=(0.5, -1, 0.3)),
          ease="in"),
        K(12, merge(STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1))), dict(hips=(0, -0.10, -0.36), hips_rot=(6, 0, 0)),
          free("l", (0.68, 0.06, 1.88), elbow=(0.6, -0.2, -1), fing="open", chest=True),
          legs((-0.12, -0.30, 0.20), (0.14, 0.05, 0.30), rr=(-30, 0, 0), rl=(-20, 0, 0), kr=(0, -1, 0.4), kl=(0.2, -1, 0.6))),
        K(14, kick_pose(0.90, 0.10, 0.40, -16.0), free("l", (0.70, 0.16, 1.80), elbow=(1, 0.4, -0.3), fing="claw", chest=True),
          ease="inout"),
        K(17, kick_pose(0.88, 0.22, 0.28), ease="out"),
        K(22, kick_pose(0.86, 0.24, 0.22), ease="sine"),
        K(28, kick_pose(0.81, 0.22, 0.115, -31.0, land=True), ease="in"),
        K(29, LANDING, ease="out"),
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


def dive_land(kit):
    """El aterrizaje de la patada voladora (Land f0): el pie derecho clavado adelante, el izquierdo cae atrás y la
    rodilla casi toca el piso (queda cortable 0.45 s); vuelve a la guardia con un paso atrás del pie de la patada."""
    # agachado con el yugo todavía en los hombros (lo tira en f9): con la flauta de la guardia acá, la flauta y la mano
    # derecha saltaban de los hombros a la guardia en un cuadro
    low = merge(READY, STAFF_SHOULDERS, grip("r", R_SH, elbow=(-0.6, -0.2, -1)),
                dict(hips=(0.06, 0.08, -0.52), hips_rot=(22, 0, -8), spine=(10, 0, 4), spine1=(6, 0, 2), spine2=(6, 0, 0),
                     neck=(0, 0, 0), head=(-6, 0, 0), face="grin"),
                dict(foot_l=(0.24, 0.0, ANKLE_Z), foot_l_rot=(0, 0, 8), fsp_l=0.0),
                free("l", (0.50, -0.36, 0.72), elbow=(1, 0.3, -0.3), fing="open"))
    k8 = merge(low, dict(hips=(0.03, 0.08, -0.38), hips_rot=(14, 0, -14)), staff_spine((-1.00, -0.04, 2.30), (1, 0, 0.03), (0, -0.3, 1)),
               free("r", (-0.60, -0.10, 1.86), elbow=(-0.6, -0.2, -1), fing="open", chest=True),
               free("l", (0.40, -0.36, 1.30), elbow=(1, 0.3, -0.4), fing="open"))
    k10 = merge(low, dict(hips=(0.02, 0.05, -0.32), hips_rot=(10, 0, -16)), staff_world((-0.60, -0.10, 1.36), unit((0.70, -0.58, 0.40)), (0, -0.3, 1)))
    keys = [
        K(0, LANDING, travel=0.0),
        K(2, LANDING, dict(hips=(0.03, 0.18, -0.36), hips_rot=(-10, 0, -4)), free("l", (0.70, 0.0, 1.30), elbow=(1, 0.4, -0.3),
                                                                                   fing="claw", chest=True), travel=0.0, ease="out"),
        # el tronco pasa de echado atrás (la patada) a inclinado adelante en dos cuadros, no en uno
        K(4, low, dict(hips=(0.04, 0.10, -0.46)), travel=0.0, ease="inout"),
        K(6, low, travel=0.0, ease="inout"),
        # la tira de los hombros: la empuja para arriba con la derecha, la suelta y la flauta gira en el aire hacia adelante
        # mientras se endereza; la ataja con las dos manos abiertas ya en la guardia (de la suelta a la guardia en cinco
        # cuadros: en tres, el antebrazo derecho giraba 140° en un cuadro)
        K(7, low, dict(hips=(0.03, 0.10, -0.42), hips_rot=(18, 0, -12)), staff_spine((-1.00, 0.08, 2.01), (1, 0, 0.03), (0, -0.3, 1)),
          travel=-0.03, ease="inout"),
        K(8, k8, travel=-0.07, ease="out"),
        # en el aire pasa por arriba y adelante de la cabeza (mezclando el yugo alzado con la de f10 la cruzaba)
        K(9, low, dict(hips=(0.02, 0.06, -0.35), hips_rot=(12, 0, -15)), tossed(kit, kit.staff(k8), kit.staff(k10), 0.5, 0.22),
          free("r", (-0.56, -0.18, 1.62), elbow=(-1, 0.1, -0.6), fing="open"),
          free("l", (0.24, -0.40, 1.32), elbow=(1, 0.3, -0.5), fing="open"), travel=-0.12, ease="inout"),
        K(10, k10,
          free("r", (-0.48, -0.16, 1.32), elbow=(-1, 0.3, -0.6), fing="open"),
          free("l", (0.06, -0.42, 1.30), elbow=(1, 0.2, -0.6), fing="open"), travel=-0.17, ease="inout"),
        K(12, READY, dict(hips=(0.01, 0.02, -0.24)), staff_world((-0.44, 0.15, 1.02), unit((0.42, -0.82, 0.39)), (0, -0.3, 1)),
          free("r", (-0.38, 0.02, 1.13), elbow=(-1, 0.4, -0.6), fing="grip_stalk"),
          free("l", (-0.06, -0.48, 1.26), elbow=(1, 0.2, -0.8), fing="grip_stalk"), travel=-0.27, ease="inout"),
        K(13, READY, dict(hips=(0.0, 0.0, -0.20)), travel=-0.30, ease="out"),
        K(14, READY, travel=-0.30, ease="inout"),
    ]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 8, -0.10, -0.40, 0.0, [(0, -30.0, "heel"), (3, 0.0, "heel")]), (12, 14, r0[0], r0[1] + 0.30, r0[2])),
            "l": plants({"free": (0, 3)}, (5, 14, l0[0], l0[1] + 0.30, l0[2]))}
    feet = feet_track(keys, 14, plan)
    faces = face_track((0, ANGRY), (3, "surprise"), (8, "grin"), (14, "grin"))
    return CClip("DiveLand", 14, keys, tracks=[feet, faces], lag={"head": 1.0},
                 timing=dict(space="ground", open=[0, 14], chain_from="DIVE_LAND", chain_to="READY", hang_scale=0.5, fade_from=0.05),
                 events=[E(0, "Land")], notes="aterriza agachado con el pie de la patada clavado (Land f0); cortable 0.45 s")


SUNK = 0.12                                       # los pies enterrados hasta el tobillo


def feet_stuck(kit):
    """Los Pies Enterrados: aterrizó y se le hundieron los pies hasta el tobillo; tironea de una pierna y de la otra
    revoleando los brazos y la flauta, se indigna, tira con las dos manos de la rodilla y al final salta afuera."""
    z = ANKLE_Z - SUNK
    stuck = legs((-0.10, -0.40, z), (0.24, 0.0, z), rr=(0, 0, 0), rl=(0, 0, 8), kr=(-0.3, -1, 0.2), kl=(0.4, -1, 0.2))
    base = merge(READY, stuck, dict(hips=(0.06, -0.04, -0.34), hips_rot=(10, 0, 0), spine=(4, 0, 0), spine2=(6, 0, 0), neck=(-6, 0, 0),
                                    head=(-12, 0, 0)),
                 staff_spine((-0.55, 0.40, 1.10), (0.05, 0.55, 0.83), (-1, 0, 0)), grip("r", 0.85, elbow=(-1, 0.4, -0.3)),
                 free("l", (0.50, -0.30, 1.20), elbow=(1, 0.3, -0.4), fing="open"))
    tug_r = dict(hips=(0.10, 0.02, -0.31), hips_rot=(4, 6, 6), spine2=(-4, 0, 6), head=(-20, 0, 8))
    tug_l = dict(hips=(0.02, -0.06, -0.31), hips_rot=(4, -6, -6), spine2=(-4, 0, -6), head=(-20, 0, -8))
    pull = merge(dict(hips=(0.04, -0.02, -0.46), hips_rot=(26, 0, 0), spine=(14, 0, 0), spine2=(12, 0, 0), head=(-24, 0, 0)),
                 free("l", (0.12, -0.40, 0.58), elbow=(1, 0.3, -0.2), fing="fist"))
    # el pie izquierdo baja derecho donde se entierra (yendo en diagonal desde el aire seguía corriéndose bajo tierra)
    drop_l = dict(foot_l=(0.24, 0.0, ANKLE_Z + 0.05), foot_l_rot=(0, 0, 8), fsp_l=0.0)
    out_pose = merge(base, dict(hips=(0.04, -0.04, -0.40), hips_rot=(18, 0, 0), spine=(9, 0, 0), spine2=(9, 0, 0)))
    # la derecha suelta la flauta donde la tiene (con el puño como estaba: soltarla en otro lado le daba vuelta el brazo)
    hr = kit.hand(out_pose, "r")
    keys = [
        K(0, LANDING),
        # la flauta pasa del yugo a la espalda girando alrededor del puño (la mano casi quieta en el hombro): derecho de una
        # pose a la otra el puño se doblaba de más
        K(3, merge(base, LANDING), dict(hips=(0.06, 0.06, -0.38), hips_rot=(-6, 0, 0)), stuck,
          staff_spine((-1.00, 0.26, 1.54), (0.72, 0.38, 0.59), (-0.7, -0.2, 0.7)), grip("r", 0.54, elbow=(-1, 0.2, -0.6)),
          ease="inout"),
        K(7, base, dict(hips=(0.06, -0.04, -0.40)), ease="inout"),
        K(9, base, ease="inout"),
        K(12, base, tug_r, free("l", (0.80, -0.10, 1.70), elbow=(0.5, 0.5, -0.5), fing="claw"), ease="inout"),
        K(16, base, ease="inout"),
        K(20, base, tug_l, free("l", (0.70, -0.40, 1.80), elbow=(0.5, 0.5, -0.5), fing="claw"), ease="inout"),
        K(24, base, ease="inout"),
        K(29, base, pull, ease="inout"),
        K(32, base, pull, dict(hips=(0.04, 0.0, -0.42), head=(-30, 0, 0)), ease="sine"),
        K(35, base, pull, dict(hips=(0.04, -0.02, -0.48)), ease="sine"),
        K(37, out_pose, ease="inout"),
        # salta afuera: tira la flauta de la espalda por arriba del hombro, da media vuelta en el aire y la ataja en la
        # guardia (agarrada, de la espalda adelante el puño giraba 127° en un cuadro y se deslizaba por el caño)
        K(38, out_pose, dict(hips=(0.04, -0.03, -0.34)), tossed(kit, kit.staff(out_pose), kit.staff(READY), 0.06, 0.25),
          grip("r", 0.85, elbow=(-1, 0.4, -0.3)), ease="out"),
        K(39, out_pose, dict(hips=(0.04, -0.03, -0.32)), tossed(kit, kit.staff(out_pose), kit.staff(READY), 0.32, 0.25),
          free("r", tuple(V(hr[0]) + V((0.0, -0.06, 0.14))), fing="open"), ease="inout"),
        K(41, base, dict(hips=(0.04, -0.03, -0.30)), tossed(kit, kit.staff(out_pose), kit.staff(READY), 0.62, 0.25),
          free("r", (-0.46, -0.10, 1.36), elbow=(-1, 0.4, -0.5), fing="open"), free("l", (0.30, -0.40, 1.30), elbow=(1, 0.3, -0.4),
                                                                                   fing="open"), ease="inout"),
        K(44, READY, dict(hips=(0.02, 0.0, -0.06), hips_rot=(-4, 0, -12)),
          legs((-0.20, -0.04, 0.40), (0.24, 0.0, 0.38), rr=(-14, 0, -24), rl=(-20, 0, 8), kr=(-0.5, -1, 0.1), kl=(0.3, -1, 0)),
          ease="out"),
        K(48, READY, ease="in"),
    ]
    # el pie izquierdo en su propia pista: baja derecho (f2) a donde se entierra
    lt = [K(k.frame, **{ch: k.ctrl[ch] for ch in ("foot_l", "foot_l_rot", "fsp_l", "knee_l") if ch in k.ctrl}) for k in keys]
    lt.insert(1, K(2, drop_l))
    faces = face_track((0, ANGRY), (4, "surprise"), (10, FACE_EFFORT), (18, ANGRY), (26, "surprise"), (30, FACE_EFFORT),
                       (42, "surprise"), (46, "laugh"), (48, "grin"))
    return CClip("FeetStuck", 48, keys, tracks=[lt, faces], lag={"head": 1.0},
                 timing=dict(space="ground", open=[0, 44], chain_from="DIVE_LAND", chain_to="READY", sunk=SUNK + 0.04, fade_to=0.1),
                 notes="Pies Enterrados (1.6 s abierto): los pies hundidos 12 cm, tironea y salta afuera al final")


def staff_drop():
    """El Bastón que Cae (dorado): posado, alza la flauta de los hombros con la derecha, salta de la caña (LeaveStalk f6),
    en el aire la planta parada sobre la cabeza con las dos manos (desde f14: el aviso se lee desde arriba, el bastón vertical
    contra el cielo) y cae así al lado de Kaito (Land f19, apex f20); la echa atrás por encima de la cabeza (f23) y la baja de
    golpe en un arco por delante (Contact f26). Antes la tenía tendida detrás de la cabeza hasta f24: desde la cámara alta
    no se veía el arma, y del aviso al golpe giraba 84° en un cuadro."""
    P = merge(PERCH, shoulders_hold())
    lift = lambda dz: merge(staff_spine((-1.00, 0.06, 1.95 + dz), (1, 0, 0.03), (0, -0.3, 1)), grip("r", R_SH, elbow=(-0.6, -0.2, -1)),
                            grip("l", L_SH, elbow=(0.6, -0.2, -1)))
    one = lambda: merge(staff_spine((-0.30, 0.00, 2.10), unit((0.30, 0.55, 0.78)), (1, 0, 0)), grip("r", 0.28, elbow=(-1, -0.2, 0.3)),
                        free("l", (0.66, -0.10, 2.05), elbow=(0.6, -0.2, -0.6), fing="open", chest=True))
    # parada sobre la cabeza, un poco hacia adelante, las dos manos a la altura de la frente; y echada atrás para el golpe
    chop = lambda: merge(grip("r", 0.20, elbow=(-1, 0.0, -0.3)), grip("l", 0.56, elbow=(1, 0.4, -0.5)))
    high = lambda z=1.92: merge(staff_at((-0.04, -0.34, z), unit((0.10, -0.30, 0.95)), 0.20), chop())
    cock = lambda: merge(staff_at((-0.04, -0.20, 1.86), unit((0.10, 0.24, 0.97)), 0.20), chop())
    land_up = merge(READY, high(1.80), dict(hips=(0.0, 0.0, -0.36), hips_rot=(4, 0, -6), spine=(-2, 0, 0), spine1=(-4, 0, 0),
                                        spine2=(-2, 0, 0), neck=(-6, 0, 0), head=(-12, 0, 0)))
    smash = merge(READY, staff_at((-0.06, -0.62, 0.96), unit((0.04, -0.86, -0.50)), 0.20), grip("r", 0.20, elbow=(-1, 0.3, -0.6)),
                  grip("l", 0.62, elbow=(1, 0.3, -0.6)),
                  dict(hips=(0.04, 0.0, -0.40), hips_rot=(26, 0, -4), spine=(12, 0, 0), spine1=(8, 0, 0), spine2=(6, 0, 0),
                       neck=(-16, 0, 0), head=(-18, 0, 0)))
    keys = [
        K(0, P),
        K(3, P, lift(0.40), dict(hips=(0, -0.36, -0.66), hips_rot=(14, 0, 0), spine2=(4, 0, 0), head=(-6, 0, 0)), ease="inout"),
        K(6, lift(0.46), dict(hips=(0, -0.20, -0.40), hips_rot=(10, 0, 0), spine=(-4, 0, 0), spine2=(-2, 0, 0), head=(-10, 0, 0)),
          legs((-0.14, -0.06, 0.14), (0.14, -0.06, 0.14), rr=(-20, 0, -20), rl=(-20, 0, 20), kr=(-0.5, -1, 0.3), kl=(0.5, -1, 0.3)),
          ease="in"),
        # la derecha la saca de los hombros girándola sobre el puño (de golpe al alzarla el puño giraba 62° en un cuadro)
        K(8, spine_mix(lift(0.46), one(), 0.45), grip("r", 0.33, elbow=(-1, -0.2, -0.3)),
          free("l", (0.70, -0.08, 2.00), elbow=(0.6, -0.2, -0.8), fing="open", chest=True),
          dict(hips=(0, -0.08, -0.28), hips_rot=(2, 0, 0), spine=(-5, 0, 0), spine2=(-3, 0, 0), head=(-12, 0, 0)), ease="inout"),
        K(10, one(), dict(hips=(0, 0.0, -0.20), hips_rot=(-6, 0, 0), spine=(-6, 0, 0), spine2=(-4, 0, 0), head=(-14, 0, 0)),
          legs((-0.16, -0.20, 0.40), (0.16, 0.05, 0.30), rr=(-30, 0, -10), rl=(-30, 0, 10), kr=(-0.3, -1, 0.3), kl=(0.3, -1, 0.3)),
          ease="out"),
        K(14, high(), dict(hips=(0, 0.0, -0.14), hips_rot=(-4, 0, -4), spine=(-6, 0, 0), spine2=(-4, 0, 0), head=(-14, 0, 0)),
          legs((-0.22, 0.02, 0.26), (0.20, -0.12, 0.28), rr=(-16, 0, -24), rl=(-16, 0, 10), kr=(-0.5, -1, 0.1), kl=(0.3, -1, 0.1)),
          ease="inout"),
        K(16, high(), dict(hips=(0, 0.0, -0.12), hips_rot=(-4, 0, -4), spine=(-6, 0, 0), spine2=(-4, 0, 0), head=(-14, 0, 0)),
          legs((-0.26, 0.10, 0.20), (0.24, -0.20, 0.24), rr=(-10, 0, -30), rl=(-10, 0, 8), kr=(-0.6, -1, 0), kl=(0.3, -1, 0)),
          ease="sine"),
        K(19, land_up, ease="in"),
        K(20, land_up, dict(hips=(0.0, 0.0, -0.32)), ease="out"),
        K(21, merge(READY, cock(), dict(hips=(0.02, 0.03, -0.26), hips_rot=(0, 0, -5), spine=(-4, 0, 0), spine1=(-8, 0, 0),
                                        spine2=(-4, 0, 0), neck=(-6, 0, 0), head=(-14, 0, 0))), ease="inout"),
        # el arco del golpe pasa por adelante y arriba (interpolando las dos puntas en línea recta la flauta aceleraba en el
        # medio y llegaba atrasada al golpe)
        K(23, merge(READY, staff_at((-0.05, -0.50, 1.44), unit((0.12, -0.79, 0.60)), 0.20), chop(),
                    dict(hips=(0.03, 0.02, -0.33), hips_rot=(13, 0, -5), spine=(4, 0, 0), spine1=(0, 0, 0), spine2=(1, 0, 0),
                         neck=(-11, 0, 0), head=(-16, 0, 0))), ease="lin"),
        K(26, smash, ease="lin"),
        K(27, smash, dict(hips=(0.04, 0.0, -0.41)), ease="out"),
    ]
    faces = face_track((0, "grin"), (3, FACE_FOCUS), (7, "laugh"), (14, FACE_FOCUS), (23, FACE_SHOUT), (27, FACE_SHOUT))
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


def vault(kit):
    """La garrocha (invulnerable): da un paso, clava el bastón adelante (Plant f6), salta colgado de él (LeaveStalk f9),
    pasa arriba del bastón empujándolo, lo arranca del piso al subir, lo revolea para arriba (da una vuelta en el aire) y lo
    ataja alzado en la pose del salto (el código lleva el arco de 0.9 s) hasta agarrar la caña (GrabStalk f27: sigue
    LeapGrab). El bastón clavado 1.2 m adelante y menos tendido hacia él: más cerca y más tendido le atravesaba el pecho
    colgado; y agarrado del clavado a la alzada el brazo daba vuelta 121° en un cuadro."""
    plant = staff_world((0.05, -1.20, -0.08), unit((-0.04, 0.36, 0.93)), (0, -1, 0))
    fly = dict(hips=(0.0, -0.30, 0.20), hips_rot=(-10, 0, 0), spine=(-4, 0, 0), head=(-10, 0, 0))
    fly_legs = legs((-0.18, -0.10, 0.70), (0.18, -0.20, 0.80), rr=(-30, 0, 0), rl=(-30, 0, 0), kr=(-0.3, -1, 0.3), kl=(0.3, -1, 0.3),
                    hips=True)
    catch = merge(AIR_STAFF, grip("r", 0.95, elbow=(-1, 0.4, -0.4)), free("l", (0.60, -0.30, 1.70), elbow=(0.5, 0.5, -0.5), fing="claw"),
                  fly, fly_legs)
    A = (plant["stw_pos"], plant["stw_dir"], plant["stw_up"])
    # el pie derecho despega desde donde lo deja su apoyo (rodado sobre la bola en f4): en la clave de f3 (la pista manda
    # hasta f4) para que el tramo suelto arranque de ahí; desde el pie de la guardia saltaba 81° en un cuadro
    r5a, r5r, r5t = rolled("r", READY_R[0], READY_R[1] + 0.22, READY_R[2], 24.0, "ball")
    r5 = ((r5a[0], r5a[1], r5a[2] + 0.02), r5r, r5t)
    B = kit.staff(catch)
    keys = [
        K(0, READY, travel=0.0),
        K(3, READY, dict(hips=(0.0, -0.10, -0.22), hips_rot=(10, 0, -8)), staff_at((-0.20, -0.36, 1.30), unit((0.10, -0.80, 0.40)), 1.00),
          grip("r", 1.00, elbow=(-1, 0.3, -0.5)), grip("l", 1.38, elbow=(1, 0.3, -0.4)), travel=0.15,
          foot_r=r5[0], foot_r_rot=r5[1], toe_r=r5[2], fsp_r=0.0),
        K(6, plant, grip("r", 1.45, elbow=(-1, 0.3, -0.5)), grip("l", 1.75, elbow=(1, 0.3, -0.5)),
          dict(hips=(0.0, -0.12, -0.30), hips_rot=(6, 0, 0), spine2=(0, 0, 0), head=(-10, 0, 0)),
          # el pie derecho ya despegó (suelto desde f5): en el lugar de la guardia y con el avance del código patinaba 30 cm
          legs((-0.26, 0.10, 0.34), (0.24, -0.30, 0.115), rr=(16, 0, -36), rl=(0, 0, 8), kr=(-0.5, -1, 0.3), kl=(0.3, -1, 0)),
          travel=0.30, ease="inout"),
        # sube por arriba del bastón: la derecha lo suelta primero (empujando con el brazo colgado hacia abajo la muñeca se
        # doblaba de costado 65°) y la izquierda lo arranca del piso
        K(9, plant, free("r", (-0.30, -0.56, 1.42), elbow=(-1, 0.3, -0.4), fing="open"), grip("l", 1.75, elbow=(1, 0.3, -0.5)),
          dict(hips=(0.0, -0.16, -0.02), hips_rot=(4, 0, 0), spine=(-4, 0, 0), spine2=(-2, 0, 0), head=(-14, 0, 0)),
          legs((-0.14, -0.10, 0.40), (0.14, -0.30, 0.60), rr=(-6, 0, -10), rl=(-30, 0, 0), kr=(-0.3, -1, 0.3), kl=(0.3, -1, 0.3)),
          travel=0.30, ease="in"),
        # lo arranca del piso con la derecha (la izquierda ya suelta) y lo revolea
        K(10, tossed(kit, A, B, 0.04, 0.10), grip("l", 1.75, elbow=(1, 0.3, -0.5)),
          free("r", (-0.36, -0.56, 1.50), elbow=(-1, 0.3, -0.3), fing="open"),
          dict(hips=(0.0, -0.28, 0.15), hips_rot=(0, 0, 0), spine=(0, 0, 0), spine2=(2, 0, 0), head=(-12, 0, 0)), fly_legs,
          travel=0.30, ease="out"),
        K(11, tossed(kit, A, B, 0.22, 0.25), free("r", (-0.36, -0.62, 1.46), elbow=(-1, 0.3, -0.3), fing="open"),
          free("l", (0.46, -0.44, 1.52), elbow=(1, 0.3, -0.4), fing="open"), fly, fly_legs, travel=0.30, ease="inout"),
        K(13, tossed(kit, A, B, 0.70, 0.25), free("r", (-0.40, -0.10, 1.80), elbow=(-1, 0.4, -0.3), fing="open"),
          free("l", (0.56, -0.34, 1.64), elbow=(0.5, 0.5, -0.5), fing="claw"), fly, fly_legs, travel=0.30, ease="inout"),
        K(15, catch, travel=0.30, ease="out"),
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


def jump_crouch(kit):
    """El agachado de la vuelta arriba (cortable: Tropiezo): mira la caña (la cabeza gira primero), se hunde, revolea la
    flauta para arriba y la ataja alzada mientras salta (LeaveStalk f9: sigue LeapAir). Pasarla de la guardia a la alzada
    deslizándola por el puño giraba el antebrazo 90° en un cuadro."""
    deep = merge(READY, dict(hips=(0.0, 0.0, -0.46), hips_rot=(20, 0, -8), spine2=(12, 0, 0), neck=(-6, 0, 6), head=(-6, 0, 12)))
    catch = merge(deep, AIR_STAFF, grip("r", 0.95, elbow=(-1, 0.4, -0.4)), free("l", (0.50, -0.20, 0.80), elbow=(1, 0.4, -0.2), fing="claw"))
    A, B = kit.staff(deep), kit.staff(catch)

    def toss(t):
        # por arriba y por afuera del hombro derecho (en línea recta de adelante a atrás le cruzaba el pecho y la cabeza)
        return tossed(kit, A, B, t, 0.40, arc=(-0.30, 0.0, 0.0))
    keys = [
        K(0, READY),
        K(3, deep, dict(hips=(0.0, 0.0, -0.36)), ease="inout"),
        K(4, deep, dict(hips=(0.0, 0.0, -0.40)), toss(0.15), free("r", (-0.40, -0.10, 1.20), elbow=(-1, 0.4, -0.5), fing="open"),
          free("l", (0.40, -0.36, 1.10), elbow=(1, 0.3, -0.4), fing="open"), ease="out"),
        K(6, deep, toss(0.75), free("r", (-0.44, 0.10, 1.62), elbow=(-1, 0.4, -0.4), fing="open"),
          free("l", (0.46, -0.28, 0.95), elbow=(1, 0.4, -0.2), fing="open"), ease="inout"),
        K(7, catch, ease="out"),
        # despega con las puntas estiradas (las del empuje): con el pie para arriba el tobillo giraba 88° en un cuadro
        K(9, merge(AIR, dict(hips=(0, -0.05, -0.18), hips_rot=(6, 0, 0))),
          legs((-0.18, 0.10, 0.20), (0.18, -0.20, 0.30), rr=(10, 0, -10), rl=(6, 0, 10), kr=(-0.2, -1, 0), kl=(0.2, -1, 0.3)),
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
    return [dive(), dive_land(kit), feet_stuck(kit), staff_drop(), staff_drop_recover(), vault(kit), jump_crouch(kit)]
