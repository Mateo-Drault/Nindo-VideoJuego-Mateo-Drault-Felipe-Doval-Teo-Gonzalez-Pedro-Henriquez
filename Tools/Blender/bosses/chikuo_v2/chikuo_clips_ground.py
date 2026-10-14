"""Clips de piso del Chikuō ermitaño (espacio 'ground': la raíz en el transform del jefe, el avance lo aplica el código con
travel_m; 'pole': en el piso con la flauta-bastón clavada): la guardia, la locomoción, las tandas de bastón, el Paso del
Ermitaño, la Grulla en el Bastón y la Pregunta y Respuesta (diseño chikuo_v2, 16.4).

El kung fu de viejo: piernas abiertas y dobladas, todo arranca del pie que empuja y de la cadera; la flauta-bastón con la
derecha cerca de la punta de abajo y la izquierda más arriba. Los pies apoyados se autoran en el mundo (feet_track) y no
patinan con el avance del código.
"""
import math
from mathutils import Vector
import chikuo_rig as CR
from chikuo_anim import CClip, merge, free, grip, legs, staff_world, staff_spine, staff_lips
from chikuo_clips import (K, READY, READY_FEET, GOLD, RED, WHITE, CHIMES_ALL, feet_track, rolled, foot_rot, sole_low,
                          READY_R, READY_L, ANKLE_Z, BALL_REL)
from chikuo_clips_perch import kick_pose

FPS = 30.0
STAFF = "Chikuo_GlintStaff"
FOOT_R = "Chikuo_GlintFootR"
LO = ("Chikuo_GlintChimesLo",)
HI = ("Chikuo_GlintChimesHi",)


def E(f, fn):
    return {"frame": f, "fn": fn}


def face_track(*pairs):
    return [K(f, face=fc) for f, fc in pairs]


def rot_z(v, deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c, v[2])


def unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return tuple(x / n for x in v)


def staff_at(p, d, at, up=(0, 0, 1)):
    """La flauta con el punto que está a 'at' metros de la punta de abajo en p (donde la agarra una mano)."""
    d = unit(d)
    return staff_world(tuple(a - b * at for a, b in zip(p, d)), d, up)


def staff_yaw(p, d, at, yaw, up=(0, 0, 1)):
    """staff_at en el marco del cuerpo girado 'yaw' grados (las vueltas: se autoran de frente y se giran)."""
    return staff_at(rot_z(p, yaw), rot_z(d, yaw), at, rot_z(up, yaw))


def guard_grips(r=0.23, l=0.83):
    return merge(grip("r", r, elbow=(-1, 0.4, -0.6)), grip("l", l, elbow=(1, 0.2, -0.8)))


GUARD_SPINE = {}


def guard_spine(kit):
    """La flauta de la guardia (READY) pegada al pecho: en READY cae exacto donde la pone la guardia en el mundo, y en los
    saltos va con el tronco (las dos manos no se despegan al subir y la guardia empalma al caer)."""
    if not GUARD_SPINE:
        from nindo_anim import rot3
        W = kit.W(READY)
        S2 = W["Spine2"] @ kit.rig.rest_inv["Spine2"]
        M = S2.inverted() @ W["Staff"]
        R = rot3(M)
        GUARD_SPINE.update(staff_spine(tuple(M.translation), tuple(R.col[1]), tuple(R.col[2])))
    return dict(GUARD_SPINE)


def plants(*segs):
    return list(segs)


FACE_FOCUS = dict(jaw=-1.0, lids=0.35, brows=-8.0, cheeks=0.1, corners=(0.004, 0.006))
FACE_SHOUT = dict(jaw=10.0, lids=0.2, brows=-6.0, cheeks=0.0, corners=(0.0, 0.004))
FACE_PUFF = dict(jaw=-1.0, lids=0.5, brows=10.0, cheeks=1.25, corners=(0.020, -0.007))
FACE_BLOWN = dict(jaw=3.0, lids=0.15, brows=8.0, cheeks=0.12, corners=(0.016, -0.004))


# ============================================================================ la guardia
def idle():
    """En guardia rebotando sobre las puntas como un boxeador viejo (dos rebotes por vuelta), la flauta-bastón que dibuja un
    círculo chico con la punta, mira a un lado y al otro con la sonrisa pícara, tamborilea los dedos de la izquierda y
    parpadea; los cascabeles se mecen con cada rebote. La pose madre del piso (READY): f0 = f48."""
    P = READY
    bob = lambda dz, dy=0.0: dict(hips=(0.0, -0.02 + dy, -0.17 + dz))
    st = lambda dx, dz: staff_world((-0.40 + dx * 0.3, 0.21, 0.97 + dz * 0.5), unit((0.40 + dx, -0.83, 0.39 + dz)), (0, -0.3, 1))
    keys = [
        K(0, P),
        K(6, P, bob(-0.035, 0.01), st(0.0, -0.03), dict(spine2=(6, 0, 4), head=(-2, 0, 4)), ease="sine"),
        K(12, P, bob(0.0), st(0.03, 0.0), dict(spine2=(4, 0, 6), neck=(-4, 0, 6), head=(-4, 4, 12)), ease="sine"),
        K(18, P, bob(-0.035, 0.01), st(0.0, 0.03), dict(spine2=(6, 0, 6), neck=(-4, 0, 6), head=(-2, 4, 14)), ease="sine"),
        K(24, P, bob(0.0), st(-0.03, 0.0), dict(spine2=(4, 0, 2), head=(-4, 0, 2)), ease="sine"),
        K(30, P, bob(-0.035, 0.01), st(0.0, -0.03), dict(spine2=(6, 0, 0), neck=(-4, 0, -2), head=(-2, -4, -8)), ease="sine"),
        K(36, P, bob(0.0), st(0.03, 0.0), dict(spine2=(4, 0, 0), neck=(-4, 0, -2), head=(-4, -4, -8)), ease="sine"),
        K(42, P, bob(-0.035, 0.01), st(0.0, 0.03), dict(spine2=(6, 0, 3), head=(-2, 0, 0)), ease="sine"),
        K(48, P, ease="sine"),
    ]
    tap = [K(0, fing_l="grip_staff"), K(30, fing_l="grip_staff"), K(32, fing_l="grip_stalk"), K(34, fing_l="grip_staff"),
           K(36, fing_l="grip_stalk"), K(38, fing_l="grip_staff"), K(48, fing_l="grip_staff")]
    blink = [K(0, wink_r=0.0, wink_l=0.0), K(20, wink_r=0.0, wink_l=0.0), K(22, wink_r=1.0, wink_l=1.0),
             K(25, wink_r=0.0, wink_l=0.0), K(48, wink_r=0.0, wink_l=0.0)]
    return CClip("Idle", 48, keys, tracks=[tap, blink], loop=True, lag={"head": 1.5, "neck": 0.8, "spine2": 0.4},
                 timing=dict(space="ground", chain_from="READY", chain_to="READY"),
                 notes="guardia de bastón rebotando; loop (Guard, Counter y Spotted lo usan de alias)")


# ============================================================================ la locomoción
# la guardia de la locomoción: la flauta de READY (en el clip, no pegada al pecho) que sigue el rebote y el vaivén de la
# cadera; los brazos la sostienen mientras el tronco gira debajo (en el blend tree empalma con Idle sin que las manos se
# despeguen)
GUARD_POS, GUARD_DIR = Vector((-0.40, 0.21, 0.97)), Vector((0.40, -0.83, 0.39))


def seam_phase(stance):
    """La fase del ciclo en la que cae el cuadro 0: la mitad del tramo más largo sin pisadas ni despegues (son quiebres de
    la velocidad del pie y en la costura del loop se leían como un salto)."""
    ev = sorted({0.0, stance % 1.0, 0.5, (0.5 + stance) % 1.0})
    gaps = [((ev[(i + 1) % len(ev)] - a) % 1.0, a) for i, a in enumerate(ev)]
    g, a = max(gaps)
    return (a + g * 0.5) % 1.0


def hermite(p0, m0, p1, m1, t):
    t2, t3 = t * t, t * t * t
    return p0 * (2 * t3 - 3 * t2 + 1) + m0 * (t3 - 2 * t2 + t) + p1 * (-2 * t3 + 3 * t2) + m1 * (t3 - t2)


def gait(name, frames, speed, direction, stance, lift, bob, sway, yaw_amp, lean, width=0.17, hip_z=-0.12, y0=0.0,
         strike=12.0, push=26.0, flight=False, back=False, toe_out=8.0, knee_out=0.15, bounce_head=0.5, staff_drop=0.0,
         notes=""):
    """Ciclo de locomoción cuadro a cuadro: los pies apoyados se deslizan hacia atrás en el clip EXACTAMENTE a la velocidad
    del juego (en el mundo quedan quietos), el talón entra primero (la bola si camina hacia atrás) y el despegue rueda sobre
    la bola; el pie en el aire sale y llega con la velocidad del piso (en el mundo despega y se posa sin arrastrarse: una
    curva de Hermite con esas tangentes) y nunca baja a menos de 2.5 cm del piso. La cadera baja al recibir el peso (al caer,
    corriendo) y se mece sobre el pie de apoyo, el pecho contrarresta el giro de la cadera y la cabeza estabiliza.
    direction: (x, y) hacia donde avanza (frente = (0, -1))."""
    T = frames / FPS
    d = Vector((direction[0], direction[1], 0.0)).normalized()
    span = speed * stance * T
    side = abs(d.x) > 0.5
    sgn = -1.0 if back else 1.0
    ph0 = seam_phase(stance)
    step_r = int(round(frames * (1.0 - ph0))) % frames
    step_l = int(round(frames * (1.5 - ph0))) % frames
    land_p = strike if back else -strike
    land_v = "ball" if back else "heel"
    # en el aire el pie va de atrás para adelante en el clip; en las puntas lleva la velocidad del piso (hacia atrás)
    m = -d * (speed * T * (1.0 - stance))
    keys = []
    for f in range(frames + 1):
        t = (f / frames + ph0) % 1.0
        ch = {}
        for s, ph in (("r", 0.0), ("l", 0.5)):
            u = (t - ph) % 1.0
            base = Vector((-width if s == "r" else width, y0, 0.0))
            yaw = -toe_out if s == "r" else toe_out
            if u < stance:
                w = u / stance
                p = base + d * (span * (0.5 - w))
                if w < 0.15:
                    pitch, piv = land_p * (1.0 - w / 0.15), land_v
                elif w > 0.70:
                    pitch, piv = push * ((w - 0.70) / 0.30) ** 1.5, "ball"
                else:
                    pitch, piv = 0.0, "ball"
                ank, rot, toe = rolled(s, p.x, p.y, yaw, pitch, piv)
            else:
                w = (u - stance) / (1.0 - stance)
                e = w * w * (3.0 - 2.0 * w)
                p0 = base + d * (-0.5 * span)
                p1 = base + d * (0.5 * span)
                a0, _r0, t0 = rolled(s, p0.x, p0.y, yaw, push, "ball")
                a1, _r1, _t1 = rolled(s, p1.x, p1.y, yaw, land_p, land_v)
                a = hermite(Vector(a0), m, Vector(a1), m, w)
                a.z = a0[2] + (a1[2] - a0[2]) * e + lift * math.sin(math.pi * w) + \
                    (0.03 * math.sin(math.pi * w / 0.3) if w < 0.3 else 0.0)
                pitch = push * (1.0 - e) + land_p * e + (8.0 if not flight else 20.0) * math.sin(math.pi * w)
                clear = 0.025 * min(1.0, w / 0.12, (1.0 - w) / 0.12)
                a.z = max(a.z, sole_low(s, yaw, pitch) + clear)
                ank, rot, toe = tuple(a), (pitch, 0.0, yaw), t0 * (1.0 - e) ** 2
            ch["foot_" + s], ch["foot_%s_rot" % s], ch["toe_" + s], ch["fsp_" + s] = ank, rot, toe, 0.0
            ch["knee_" + s] = (-knee_out if s == "r" else knee_out, -1.0, 0.0)
        c2 = math.cos(4.0 * math.pi * (t - (stance * 0.5 if flight else 0.05)))
        drop = bob * (0.5 + 0.5 * c2)
        yw = sgn * yaw_amp * math.cos(2.0 * math.pi * t)
        sw = sway * math.sin(2.0 * math.pi * t) * (0.4 if side else 1.0)
        hy = 0.02 + (-0.03 if not back else 0.02) * (1.0 if not side else 0.0)
        ch["hips"] = (-sw, hy, hip_z - drop)
        ch["hips_rot"] = (lean, -sw * 40.0, (0.0 if side else yw) - (6.0 * d.x if side else 0.0))
        ch["spine"] = (2.0 + lean * 0.2, 0.0, -yw * 0.4)
        ch["spine1"] = (2.0, 0.0, -yw * 0.3)
        ch["spine2"] = (6.0 - lean * 0.2 + 2.0 * c2, 0.0, -yw * 0.3)
        ch["neck"] = (-4.0 - lean * 0.4, 0.0, yw * 0.1)
        ch["head"] = (-6.0 - lean * 0.5 - bounce_head * 2.0 * c2, 0.0, yw * 0.1)
        ch["clav_r"] = (0.0, 0.0, 2.0 * c2)
        ch["clav_l"] = (0.0, 0.0, -2.0 * c2)
        # la flauta sigue el rebote y el vaivén de la cadera (corriendo, la punta un poco más baja y adelante)
        sp = GUARD_POS + Vector((-sw * 0.8, hy - 0.02 - lean * 0.012, (hip_z - drop + 0.17) * 0.9 - staff_drop))
        sd = Vector(rot_z(GUARD_DIR, -yw * 0.3))
        sd.z -= staff_drop * 0.8
        k = K(f, merge(staff_world(tuple(sp), unit(tuple(sd)), (0, -0.3, 1)), guard_grips(), dict(face="grin")), ch, ease="lin")
        keys.append(k)
    return CClip(name, frames, keys, loop=True, root_vel=(d.x * speed, d.y * speed, 0.0),
                 timing=dict(space="ground", ground_speed_mps=speed, stance=stance, contacts=[step_r, step_l],
                             chain_from="READY", chain_to="READY", fade_from=0.25, fade_to=0.25),
                 events=[E(step_r, "Step"), E(step_l, "Step")], notes=notes)


def locomotion():
    return [
        gait("Walk", 30, 1.6, (0, -1), 0.60, 0.10, 0.035, 0.035, 8.0, 8.0, hip_z=-0.12,
             notes="camina encorvado con la flauta en guardia, 1.6 m/s (los pies no patinan a esa velocidad)"),
        gait("Run", 20, 5.5, (0, -1), 0.30, 0.30, 0.07, 0.02, 10.0, 22.0, width=0.15, hip_z=-0.15, y0=0.06, strike=6.0,
             push=34.0, flight=True, bounce_head=1.0, staff_drop=0.06,
             notes="corre a saltos de viejo, 5.5 m/s: rebota alto en cada pisada (vuelo largo)"),
        gait("StrafeL", 24, 1.3, (1, 0), 0.55, 0.08, 0.03, 0.0, 0.0, 6.0, width=0.30, hip_z=-0.15, strike=0.0, push=12.0,
             toe_out=14.0, knee_out=0.4, notes="paso de costado hacia su izquierda en guardia, 1.3 m/s (el controller lo "
                                               "acelera a la velocidad de rodear)"),
        gait("StrafeR", 24, 1.3, (-1, 0), 0.55, 0.08, 0.03, 0.0, 0.0, 6.0, width=0.30, hip_z=-0.15, strike=0.0, push=12.0,
             toe_out=14.0, knee_out=0.4, notes="paso de costado hacia su derecha en guardia, 1.3 m/s"),
        gait("WalkBack", 30, 1.2, (0, 1), 0.60, 0.08, 0.03, 0.03, 6.0, 6.0, hip_z=-0.15, strike=10.0, push=14.0, back=True,
             notes="retrocede en guardia, 1.2 m/s (la bola del pie entra primero)"),
    ]


# ============================================================================ la risa en el piso
def ground_laugh():
    """La carcajada parado: la flauta clavada al costado como un bastón de viejo, se dobla de risa, se palmea el muslo con
    la izquierda y se echa atrás con los ojos cerrados; los hombros rebotan a cada 'ja'. Loop de 36."""
    cane = merge(staff_world((-0.50, -0.22, 0.0), unit((0.03, 0.08, 1.0)), (0, -1, 0)), grip("r", 1.00, elbow=(-1, 0.3, -0.5)))
    feet = legs((-0.22, 0.04, 0.115), (0.22, -0.06, 0.115), rr=(0, 0, -14), rl=(0, 0, 14), kr=(-0.3, -1, 0), kl=(0.3, -1, 0))
    base = merge(cane, feet, dict(hips=(0, 0.0, -0.10), hips_rot=(0, 0, 0), spine=(2, 0, 0), spine1=(2, 0, 0), spine2=(4, 0, 0),
                                  neck=(-6, 0, 0), head=(-14, 0, 0), face="laugh"))
    up = dict(hips=(0, 0.03, -0.09), spine=(-6, 0, 0), spine1=(-6, 0, 0), spine2=(-4, 0, 0), neck=(-10, 0, 0), head=(-22, 0, 0))
    fold = dict(hips=(0, 0.06, -0.16), hips_rot=(10, 0, 0), spine=(10, 0, 0), spine1=(12, 0, 4), spine2=(16, 0, 4), neck=(4, 0, 0),
                head=(-6, 0, 6))

    def slap(f):
        return [K(f - 4, base, fold, free("l", (0.40, -0.40, 1.05), elbow=(1, 0.3, -0.3), fing="open")),
                K(f, base, dict(fold, spine2=(20, 0, 4)), free("l", (0.34, -0.30, 0.78), elbow=(1, 0.3, -0.3), fing="open"), ease="snap")]
    keys = [K(0, base, up, free("l", (0.44, -0.10, 1.10), elbow=(1, 0.2, -0.6), fing="relaxed"))]
    keys += slap(10) + [K(16, base, up, free("l", (0.46, -0.16, 1.16), elbow=(1, 0.2, -0.6), fing="relaxed"))]
    keys += slap(28) + [K(36, base, up, free("l", (0.44, -0.10, 1.10), elbow=(1, 0.2, -0.6), fing="relaxed"))]
    ja = [K(i, clav_r=(0, 0, 0), clav_l=(0, 0, 0), ease="sine") for i in range(0, 37, 6)]
    ja = sorted(ja + [K(i + 3, clav_r=(0, 0, 6), clav_l=(0, 0, -6), ease="sine") for i in range(0, 34, 6)], key=lambda k: k.frame)
    return CClip("GroundLaugh", 36, keys, tracks=[ja], loop=True, lag={"head": 1.0},
                 timing=dict(space="ground", load=[0, 36], chain_from="READY", chain_to="READY", fade_from=0.2, fade_to=0.2,
                             shots=[(10, "la risa en el piso", CHIMES_ALL, WHITE)]),
                 notes="carcajada parado apoyado en la flauta; loop")


# ============================================================================ las tandas de bastón
def thrust():
    """La Estocada (dorada, 2.4 m): recoge la flauta hacia atrás a lo largo de su eje y carga el peso en el pie de atrás,
    enroscado (aviso f9, quieto y temblando); el pie de adelante se lanza, la cadera gira hacia adelante y la derecha empuja
    la punta de abajo: la flauta sale por la izquierda como una lanza (Contact f15, el avance del código 0.45 m); se pasa,
    la recoge y vuelve a la guardia."""
    draw = merge(READY, staff_at((-0.22, 0.40, 1.04), (0.16, -0.99, 0.04), 0.12), grip("r", 0.12, elbow=(-1, 0.4, -0.5)),
                 grip("l", 0.86, elbow=(1, 0.0, -0.8)),
                 dict(hips=(0.0, 0.12, -0.25), hips_rot=(2, 0, -36), spine=(0, 0, 6), spine1=(0, 0, 6), spine2=(2, 0, 4),
                      neck=(-2, 0, 8), head=(-6, 0, 16)))
    hit = merge(READY, staff_at((-0.12, -0.36, 1.16), (0.02, -1.0, 0.02), 0.06), grip("r", 0.06, elbow=(-1, 0.3, -0.6)),
                grip("l", 0.48, elbow=(1, 0.0, -0.8)),
                dict(hips=(0.0, 0.04, -0.30), hips_rot=(16, 0, 6), spine=(6, 0, 6), spine1=(4, 0, 4), spine2=(4, 0, 2),
                     neck=(-8, 0, -6), head=(-12, 0, -10)))
    keys = [
        K(0, READY, travel=0.0),
        K(5, draw, dict(hips=(0.0, 0.10, -0.23)), travel=0.0, ease="inout"),
        K(9, draw, travel=0.0, ease="out"),
        K(10, draw, dict(hips=(0.0, 0.125, -0.255), head=(-6, 0, 17)), travel=0.0),
        # la estocada en cinco cuadros que aceleran (en dos, el brazo derecho giraba 75° en el último)
        K(15, hit, travel=0.45, ease="in"),
        K(18, hit, staff_at((-0.12, -0.40, 1.15), (0.03, -1.0, 0.0), 0.06), dict(hips=(0.0, 0.0, -0.31)), travel=0.45, ease="out"),
        K(22, merge(READY, staff_at((-0.25, 0.10, 1.04), (0.25, -0.95, 0.20), 0.15), grip("r", 0.15, elbow=(-1, 0.4, -0.6)),
                    grip("l", 0.70, elbow=(1, 0.2, -0.8))), travel=0.45, ease="inout"),
        K(27, READY, travel=0.45, ease="inout"),
    ]
    r0, l0 = READY_R, READY_L
    plan = {"l": plants((0, 11, l0[0], l0[1], l0[2]), (14, 27, l0[0], l0[1] - 0.45, l0[2])),
            "r": plants((0, 17, r0[0], r0[1], r0[2], [(11, 0.0, "ball"), (15, 28.0, "ball"), (17, 18.0, "ball")]),
                        (21, 27, r0[0], r0[1] - 0.45, r0[2]))}
    feet = feet_track(keys, 27, plan, lift=0.08)
    faces = face_track((0, "grin"), (5, FACE_FOCUS), (13, FACE_SHOUT), (19, FACE_SHOUT), (24, "grin"), (27, "grin"))
    return CClip("Thrust", 27, keys, tracks=[feet, faces], lag={"head": 1.0},
                 timing=dict(space="ground", tell=[2, 9], apex=9, contact=15, active=[14, 17], kind="parry", glow=[STAFF] + list(HI),
                             reach_m=2.4, chain_from="READY", chain_to="READY",
                             shots=[(9, "aviso (dorado)", (STAFF,) + HI, GOLD)]),
                 events=[E(15, "Contact")], notes="la Estocada: aviso f9, Contact f15 (2.4 m), el avance 0.45 m")


SW_AT = 0.32                                     # el punto de la flauta entre las manos (la derecha en 0.12, la izquierda en 0.52)


def swing_pose(yaw, alpha, hands, tilt=0.06):
    """La flauta horizontal agarrada como un bate (las dos manos cerca de la punta de abajo) apuntando a 'alpha' grados
    desde el frente del cuerpo hacia su izquierda; todo en el marco del cuerpo girado 'yaw'."""
    a = math.radians(alpha)
    d = (math.sin(a), -math.cos(a), tilt)
    return merge(staff_yaw(hands, d, SW_AT, yaw), grip("r", 0.12, elbow=rot_z((-1, 0.2, -0.6), yaw)),
                 grip("l", 0.52, elbow=rot_z((1, 0.2, -0.8), yaw)))


def body_yaw(yaw, x=0.0, y=0.0, z=-0.22, lean=6.0, twist=0.0):
    """El cuerpo girado 'yaw' (la cadera), el pecho 'twist' más allá."""
    return dict(hips=(x, y, z), hips_rot=(lean, 0, yaw), spine=(2, 0, twist * 0.4), spine1=(2, 0, twist * 0.3),
                spine2=(4, 0, twist * 0.3), neck=(-4, 0, -twist * 0.5), head=(-6, 0, -twist * 0.5))


def staff_spin2():
    """La Flauta Giratoria: se enrosca a su derecha con la flauta atrás como un bate (aviso f9, quieto y temblando), el
    barrido de derecha a izquierda por delante (Contact f17) y sin parar da la vuelta entera girando sobre la bola del pie
    izquierdo con la flauta estirada barriendo alrededor (la espiral de hojas del concepto) hasta el segundo barrido
    (Contact f29). La vuelta va pareja, cuadro a cuadro (30° por cuadro): con claves sueltas la flauta giraba 90° en uno."""
    l0, r0 = READY_L, READY_R
    b = Vector((-BALL_REL.x, BALL_REL.y, BALL_REL.z))
    piv = Vector((l0[0], l0[1], ANKLE_Z)) + foot_rot(l0[2], 0.0) @ b
    # (cuadro, giro de la cadera, hacia dónde apunta la flauta en el marco del cuerpo, las manos en el marco del cuerpo)
    tab = [(0, -22.0, 25.0, (-0.31, 0.02, 1.06)), (3, -30.0, -35.0, (-0.34, -0.36, 1.10)), (6, -42.0, -80.0, (-0.32, -0.34, 1.14)),
           (9, -48.0, -102.0, (-0.30, -0.34, 1.16)), (12, -50.0, -108.0, (-0.30, -0.32, 1.15)), (14, -36.0, -82.0, (-0.30, -0.38, 1.14)),
           (15, -22.0, -58.0, (-0.25, -0.42, 1.14)), (16, -6.0, -32.0, (-0.19, -0.50, 1.15)), (17, 10.0, -8.0, (-0.14, -0.54, 1.16)),
           (29, 370.0, -8.0, (-0.14, -0.52, 1.16)), (30, 392.0, 4.0, (-0.10, -0.53, 1.17))]

    def at(f):
        for (fa, ya, aa, ha), (fb, yb, ab, hb) in zip(tab, tab[1:]):
            if fa <= f <= fb:
                u = (f - fa) / float(fb - fa)
                if not (fa == 17 and fb == 29):
                    u = u * u * (3.0 - 2.0 * u)
                return ya + (yb - ya) * u, aa + (ab - aa) * u, tuple(x + (y - x) * u for x, y in zip(ha, hb))
        return tab[-1][1], tab[-1][2], tab[-1][3]
    keys = []
    for f in range(31):
        yaw, alpha, hands = at(f)
        if f == 0:
            keys.append(K(0, READY))
            continue
        lean = 4.0 if f <= 12 else 10.0
        twist = -30.0 if f <= 12 else 10.0
        hz = -0.26 if f <= 12 else -0.24 - (0.03 * math.sin(math.pi * (f - 17) / 12.0) if 17 < f < 29 else 0.0)
        if f <= 17:
            pose = merge(READY, body_yaw(yaw, 0.0, 0.04 if f <= 12 else -0.02, hz, lean, twist), swing_pose(yaw, alpha, hands))
        else:
            # girando, el cuerpo entero (la cadera, las manos, la flauta) da la vuelta sobre la bola del pie izquierdo
            pose = spin_about(merge(READY, body_yaw(10.0, 0.0, -0.02, hz, lean, twist), swing_pose(10.0, alpha, hands)),
                              (piv.x, piv.y), yaw - 10.0)
        keys.append(K(f, pose, ease="lin"))
    # el pie izquierdo gira sobre la bola en la vuelta; el derecho se levanta recogido y vuelve a apoyarse girado 360°
    # recogido bien alto: con la cadera baja de la vuelta, a 0.34 el pie pasaba a 10 cm del piso y barría el piso girando
    tuck = dict(foot_r=(-0.20, 0.18, 0.50), foot_r_rot=(-20, 0, -40), fsp_r=1.0, toe_r=0.0)
    for k in keys:
        if 20 <= k.frame <= 27:
            k.ctrl.update(tuck)
        elif k.frame in (18, 19):
            # despega de a poco y pasa de a poco al marco de la cadera (de golpe al recogido el muslo giraba 70° en un cuadro)
            w = k.frame - 18
            k.ctrl.update(dict(foot_r=(-0.28 + 0.04 * w, 0.16 + 0.01 * w, 0.22 + 0.12 * w), foot_r_rot=(10 - 15 * w, 0, -40),
                               fsp_r=0.5 * w, toe_r=0.0))
    feet = feet_track(keys, 30, {"r": plants((0, 17, r0[0], r0[1], r0[2], [(14, 0.0, "ball"), (17, 24.0, "ball")]),
                                             {"free": (18, 27)}, (28, 30, r0[0], r0[1], r0[2] + 360.0))})
    yaw_k = [(0, -22.0), (17, 10.0), (29, 370.0), (30, 392.0)]
    for k in feet:
        f = k.frame
        yaw = lerp_tab(yaw_k, f) + 30.0
        p = lerp_tab([(0, 0.0), (14, 0.0), (17, 22.0), (29, 22.0), (30, 10.0)], f)
        if f >= 14:
            k.ctrl.update({"foot_l": tuple(piv - foot_rot(yaw, p) @ b), "foot_l_rot": (p, 0.0, yaw), "toe_l": p, "fsp_l": 0.0})
    faces = face_track((0, "grin"), (6, FACE_FOCUS), (16, FACE_SHOUT), (21, "laugh"), (26, FACE_FOCUS), (28, FACE_SHOUT), (30, FACE_SHOUT))
    return CClip("StaffSpin2", 30, keys, tracks=[feet, faces], lag={"head": 1.0},
                 timing=dict(space="ground", tell=[2, 9], apex=9, contact=17, active=[16, 18], contacts=[17, 29], kind="parry",
                             glow=[STAFF] + list(HI), reach_m=2.3, chain_from="READY", fade_to=0.15, hang_scale=0.5,
                             shots=[(9, "aviso (dorado)", (STAFF,) + HI, GOLD)]),
                 events=[E(17, "Contact"), E(29, "Contact")],
                 notes="la Flauta Giratoria: dos barridos (Contact f17 y f29) con una vuelta entera sobre el pie izquierdo entre "
                       "los dos; termina en el seguimiento del segundo (el código funde a la guardia o a la próxima)")


def crane_kick():
    """La Patada de Grulla: pasa el peso al pie de adelante, sube la rodilla derecha bien alta y abre los brazos como alas
    (la flauta estirada en la derecha, la izquierda en garra; aviso f8, se sostiene haciendo equilibrio), la patada de
    frente sale de la rodilla (Contact f15), la recoge y apoya adelante; vuelve a la guardia."""
    wings = merge(staff_at((-0.62, -0.04, 1.56), unit((-0.55, 0.20, 0.81)), 0.23), grip("r", 0.23, elbow=(-0.6, 0.6, -0.4)),
                  free("l", (0.70, -0.06, 1.64), elbow=(0.5, 0.6, -0.4), fing="claw"))
    crane = merge(READY, wings, dict(hips=(0.18, -0.20, -0.08), hips_rot=(4, 4, -6), spine=(-2, 0, 0), spine1=(-2, 0, 0),
                                    spine2=(2, 0, 0), neck=(-6, 0, 2), head=(-8, 0, 4)),
                  dict(foot_r=(-0.06, -0.48, 0.80), foot_r_rot=(-40, 0, -10), knee_r=(0, -0.6, 0.8), fsp_r=0.0, toe_r=10.0))
    kick = merge(crane, dict(hips=(0.18, -0.10, -0.12), hips_rot=(-6, 4, -10), spine=(-6, 0, 0), spine2=(-2, 0, 0), head=(-2, 0, 4)),
                 dict(foot_r=(-0.03, -0.98, 0.92), foot_r_rot=(-55, 0, -6), knee_r=(0, -0.6, 0.8), toe_r=-10.0))
    keys = [
        K(0, READY),
        K(3, READY, dict(hips=(0.10, -0.16, -0.20), hips_rot=(6, 2, -14), spine2=(4, 0, 2)),
          free("l", (0.24, -0.46, 1.34), elbow=(1, 0.2, -0.7), fing="open"), ease="inout"),
        K(5, READY, dict(hips=(0.14, -0.20, -0.18), hips_rot=(6, 4, -10), spine2=(4, 0, 2)),
          staff_at((-0.42, -0.20, 1.24), unit((-0.30, -0.35, 0.89)), 0.23), grip("r", 0.23, elbow=(-1, 0.4, -0.5)),
          free("l", (0.50, -0.30, 1.50), elbow=(0.6, 0.5, -0.5), fing="claw"),
          dict(foot_r=(-0.20, -0.08, 0.42), foot_r_rot=(-10, 0, -24), knee_r=(0, -0.8, 0.6), fsp_r=0.0), ease="inout"),
        K(8, crane, ease="out"),
        K(10, crane, dict(hips=(0.19, -0.20, -0.07)), ease="sine"),
        K(11, crane, dict(hips=(0.18, -0.19, -0.09)), dict(foot_r=(-0.06, -0.40, 0.86), foot_r_rot=(-30, 0, -10)), ease="sine"),
        K(15, kick, ease="lin"),
        K(18, crane, dict(foot_r=(-0.08, -0.62, 0.70), foot_r_rot=(-30, 0, -10)), ease="inout"),
        K(20, crane, dict(hips=(0.12, -0.18, -0.12), foot_r=(-0.16, -0.30, 0.50), foot_r_rot=(-10, 0, -20)),
          staff_at((-0.44, -0.12, 1.36), unit((-0.15, -0.25, 0.96)), 0.23), grip("r", 0.23, elbow=(-1, 0.4, -0.5)),
          free("l", (0.50, -0.30, 1.40), elbow=(0.6, 0.4, -0.5), fing="open"), ease="inout"),
        # la pierna vuelve a su lugar y la flauta baja en la derecha; la izquierda la busca y la toma recién en f25
        K(22, READY, dict(hips=(0.08, -0.14, -0.18), hips_rot=(6, 2, -14)), staff_at((-0.30, 0.02, 1.08), unit((0.36, -0.84, 0.40)), 0.23),
          grip("r", 0.23, elbow=(-1, 0.4, -0.6)), free("l", (0.16, -0.42, 1.30), elbow=(1, 0.2, -0.7), fing="open"),
          dict(foot_r=(-0.30, 0.10, 0.26), foot_r_rot=(0, 0, -36), fsp_r=0.0), ease="inout"),
        K(25, READY, dict(hips=(0.02, -0.04, -0.19)), ease="out"),
        K(28, READY, ease="inout"),
    ]
    r0, l0 = READY_R, READY_L
    plan = {"l": plants((0, 28, l0[0], l0[1], l0[2], [(8, 0.0, "ball"), (10, 8.0, "ball"), (15, 14.0, "ball"), (18, 0.0, "ball")])),
            "r": plants((0, 3, r0[0], r0[1], r0[2]), {"free": (4, 22)}, (24, 28, r0[0], r0[1], r0[2]))}
    feet = feet_track(keys, 28, plan)
    faces = face_track((0, "grin"), (6, FACE_FOCUS), (14, FACE_SHOUT), (20, "grin"), (28, "grin"))
    return CClip("CraneKick", 28, keys, tracks=[feet, faces], lag={"head": 1.0},
                 timing=dict(space="ground", tell=[2, 8], apex=8, contact=15, active=[14, 16], kind="parry", glow=[FOOT_R] + list(HI),
                             reach_m=1.2, chain_from="READY", chain_to="READY",
                             shots=[(8, "aviso (dorado)", (FOOT_R,) + HI, GOLD)]),
                 events=[E(15, "Contact")], notes="la Patada de Grulla: rodilla arriba y brazos abiertos (aviso f8), Contact f15")


def note_smash():
    """El Golpe de Nota: levanta la flauta bien alta en las dos manos arqueándose en puntas de pie (la flauta silba una
    nota: aviso f14, la silueta más alta de toda la pelea), da un paso y la baja de golpe al piso delante (Contact f20),
    rebota y vuelve a la guardia."""
    up = merge(READY, staff_at((0.0, -0.22, 1.90), unit((0.04, 0.25, 0.97)), 0.23), grip("r", 0.23, elbow=(-1, -0.2, -0.4)),
               grip("l", 0.83, elbow=(1, -0.2, -0.4)),
               dict(hips=(0.04, 0.02, -0.04), hips_rot=(-8, 0, -6), spine=(-6, 0, 2), spine1=(-6, 0, 2), spine2=(-4, 0, 2),
                    neck=(-6, 0, 0), head=(-14, 0, 0)))
    smash = merge(READY, staff_at((-0.04, -0.52, 1.08), unit((0.04, -0.86, -0.50)), 0.23), grip("r", 0.23, elbow=(-1, 0.3, -0.6)),
                  grip("l", 0.50, elbow=(1, 0.3, -0.6)),
                  dict(hips=(0.04, -0.02, -0.34), hips_rot=(24, 0, -4), spine=(10, 0, 0), spine1=(8, 0, 0), spine2=(6, 0, 0),
                       neck=(-14, 0, 0), head=(-18, 0, 0)))
    keys = [
        K(0, READY, travel=0.0),
        K(4, READY, dict(hips=(0.0, 0.02, -0.22), spine2=(6, 0, 4)), staff_at((-0.30, 0.0, 1.30), unit((0.20, -0.40, 0.90)), 0.23),
          grip("r", 0.23, elbow=(-1, 0.2, -0.6)), grip("l", 0.83, elbow=(1, 0.2, -0.6)), travel=0.0),
        K(10, up, travel=0.0, ease="out"),
        K(14, up, dict(hips=(0.04, 0.03, -0.03)), staff_at((0.0, -0.18, 1.94), unit((0.04, 0.30, 0.95)), 0.23),
          grip("l", 0.50, elbow=(1, -0.2, -0.4)), travel=0.0, ease="sine"),
        K(16, up, dict(hips=(0.04, 0.0, -0.06)), grip("l", 0.50, elbow=(1, -0.2, -0.4)), travel=0.05),
        K(17, merge(READY, staff_at((-0.02, -0.36, 1.66), unit((0.04, -0.30, 0.95)), 0.23), grip("r", 0.23, elbow=(-1, 0.0, -0.4)),
                    grip("l", 0.50, elbow=(1, 0.0, -0.4)), dict(hips=(0.04, -0.02, -0.18), hips_rot=(8, 0, -4), spine=(4, 0, 0))),
          travel=0.25, ease="in"),
        K(20, smash, travel=0.35, ease="lin"),
        K(22, smash, staff_at((-0.04, -0.50, 1.10), unit((0.04, -0.88, -0.46)), 0.23), dict(hips=(0.04, -0.02, -0.33)), travel=0.35,
          ease="out"),
        K(26, smash, staff_at((-0.06, -0.42, 1.10), unit((0.10, -0.86, -0.40)), 0.23), dict(hips=(0.03, 0.0, -0.28)), travel=0.35,
          ease="inout"),
        K(36, READY, travel=0.35, ease="inout"),
    ]
    r0, l0 = READY_R, READY_L
    # el pie de adelante da el paso del golpe; el de atrás se arrastra detrás al final (el código avanzó 0.35 m)
    plan = {"r": plants((0, 26, r0[0], r0[1], r0[2], [(8, 0.0, "ball"), (13, 22.0, "ball"), (17, 0.0, "ball"), (20, 16.0, "ball"),
                                                   (26, 0.0, "ball")]),
                        (31, 36, r0[0], r0[1] - 0.35, r0[2])),
            "l": plants((0, 15, l0[0], l0[1], l0[2], [(8, 0.0, "ball"), (13, 18.0, "ball"), (15, 10.0, "ball")]),
                        (19, 36, l0[0], l0[1] - 0.35, l0[2]))}
    feet = feet_track(keys, 36, plan)
    faces = face_track((0, "grin"), (8, "surprise"), (14, dict(FACE_PUFF, cheeks=0.6)), (19, FACE_SHOUT), (26, "grin"), (36, "grin"))
    return CClip("NoteSmash", 36, keys, tracks=[feet, faces], lag={"head": 1.0},
                 timing=dict(space="ground", tell=[2, 14], apex=14, contact=20, active=[19, 21], kind="parry", glow=[STAFF] + list(HI),
                             reach_m=2.2, chain_from="READY", chain_to="READY",
                             shots=[(14, "aviso (dorado)", (STAFF,) + HI, GOLD)]),
                 events=[E(20, "Contact")], notes="el Golpe de Nota: la flauta arriba (aviso f14, suena una nota), Contact f20 "
                                                  "con la punta en el piso a 2.2 m")


def spin_about(c, center, deg):
    """Los controles de una pose girados 'deg' grados alrededor del punto 'center' del piso (el cuerpo que gira sobre un
    pie: la cadera, la flauta, la pierna suelta y los codos dan la vuelta con él)."""
    c = dict(c)
    cx, cy = center

    def orb(p):
        q = rot_z((p[0] - cx, p[1] - cy, 0.0), deg)
        return (cx + q[0], cy + q[1], p[2])
    for k in ("hips", "stw_pos", "foot_r", "foot_l", "hand_r", "hand_l"):
        if c.get(k) is not None:
            c[k] = orb(c[k])
    for k in ("stw_dir", "stw_up", "knee_r", "knee_l", "elbow_r", "elbow_l", "hand_r_dir", "hand_r_up", "hand_l_dir", "hand_l_up"):
        if c.get(k) is not None:
            c[k] = rot_z(c[k], deg)
    for k in ("hips_rot", "foot_r_rot", "foot_l_rot"):
        if c.get(k) is not None:
            c[k] = (c[k][0], c[k][1], c[k][2] + deg)
    return c


def lerp_tab(tab, f):
    """Valor de una tabla [(cuadro, valor), ...] en el cuadro f (suave entre cuadros de la tabla)."""
    for (fa, va), (fb, vb) in zip(tab, tab[1:]):
        if fa <= f <= fb:
            u = (f - fa) / float(fb - fa)
            return va + (vb - va) * u * u * (3.0 - 2.0 * u)
    return tab[-1][1]


def low_sweep():
    """La Barrida del Bastón (roja, disco de 2.6 m): baja hasta casi sentarse sobre el pie izquierdo con la pierna derecha
    estirada de costado (el agachado del tigre), la flauta a ras del piso por delante (aviso f16, las campanas rojas del
    ruedo); gira entero sobre la bola del pie izquierdo con la flauta barriendo el piso (Contact f24, a media vuelta) y se
    levanta a la guardia."""
    l0, r0 = READY_L, READY_R
    # el eje del giro: la bola del pie izquierdo de la guardia
    b = Vector((-BALL_REL.x, BALL_REL.y, BALL_REL.z))
    piv = Vector((l0[0], l0[1], ANKLE_Z)) + foot_rot(l0[2], 0.0) @ b
    center = (piv.x, piv.y)
    # el agachado del tigre de frente a su derecha (la cadera girada -90): sentado sobre el talón izquierdo levantado, la
    # pierna derecha estirada hacia atrás de la barrida, la flauta a ras del piso por delante hacia su derecha
    LOW = merge(READY, dict(hips=(0.10, -0.30, -0.66), hips_rot=(16, -6, -90), spine=(8, 0, 4), spine1=(6, 0, 4), spine2=(4, 0, 4),
                            neck=(-10, 0, -4), head=(-18, 0, -6)),
                staff_at((-0.30, -0.62, 0.38), unit((-0.85, 0.50, -0.06)), 0.40), grip("r", 0.20, elbow=(-0.3, 1.0, 0.2)),
                grip("l", 0.60, elbow=(0.3, 1.0, 0.2)),
                dict(foot_r=(0.88, -0.10, 0.17), foot_r_rot=(0, -80, -10), knee_r=(0, 0, 1), fsp_r=0.0, toe_r=0.0))

    def low(yaw):
        return spin_about(LOW, center, yaw + 90.0)
    keys = [
        K(0, READY),
        K(6, READY, dict(hips=(0.10, -0.12, -0.40), hips_rot=(10, -4, -50), spine2=(6, 0, 4)),
          staff_at((-0.30, -0.20, 0.80), unit((-0.50, -0.80, -0.20)), 0.20), grip("r", 0.20, elbow=(-1, 0.3, -0.4)),
          # la rodilla derecha ya a medio camino hacia arriba (la del tigre): de la guardia al agachado el polo pasaba por
          # cero con la pierna casi estirada y el muslo daba vuelta en un cuadro
          grip("l", 0.60, elbow=(1, 0.3, -0.4)), dict(foot_r=(0.20, 0.40, 0.20), foot_r_rot=(0, -30, -40), fsp_r=0.0,
                                                      knee_r=(-0.5, -0.6, 0.65)), ease="inout"),
        K(12, low(-90.0), ease="out"),
        K(16, low(-96.0), ease="out"),
        K(18, low(-92.0), ease="inout"),
        K(21, low(-10.0), ease="in"),
        K(24, low(90.0), ease="lin"),
        K(27, low(190.0), ease="lin"),
        K(29, low(250.0), ease="out"),
        K(33, merge(READY, dict(hips=(0.10, -0.04, -0.36), hips_rot=(8, 0, 320.0), spine2=(6, 0, 4)),
                    staff_at((-0.30, 0.10, 0.90), unit((0.36, -0.82, 0.10)), 0.20), grip("r", 0.20, elbow=(-1, 0.3, -0.5)),
                    grip("l", 0.66, elbow=(1, 0.2, -0.7)), dict(foot_r=(-0.40, 0.30, 0.22), foot_r_rot=(0, 0, 310.0), fsp_r=0.0)),
          ease="inout"),
        # la vuelta completa: la cadera y el pie terminan girados 360° (es la guardia)
        K(39, READY, dict(hips_rot=(6, 0, 338.0), foot_r_rot=(0, 0, 320.0)), ease="inout"),
    ]
    # el pie de apoyo: la bola quieta en el eje, el giro del pie sigue al de la cadera (en la guardia, 30° más)
    yaw_k = [(0, -22.0), (6, -50.0), (12, -90.0), (16, -96.0), (18, -92.0), (21, -10.0), (24, 90.0), (27, 190.0), (29, 250.0),
             (33, 320.0), (39, 338.0)]
    pitch_k = [(0, 0.0), (8, 24.0), (31, 24.0), (39, 0.0)]
    feet = feet_track(keys, 39, {"r": plants((0, 4, r0[0], r0[1], r0[2]), {"free": (5, 34)}, (36, 39, r0[0], r0[1], r0[2] + 360.0))})
    for k in feet:
        yaw = lerp_tab(yaw_k, k.frame) + 30.0
        p = lerp_tab(pitch_k, k.frame)
        ank = piv - foot_rot(yaw, p) @ b
        k.ctrl.update({"foot_l": tuple(ank), "foot_l_rot": (p, 0.0, yaw), "toe_l": p, "fsp_l": 0.0})
    faces = face_track((0, "grin"), (8, FACE_FOCUS), (20, FACE_SHOUT), (30, "grin"), (39, "grin"))
    return CClip("LowSweep", 39, keys, tracks=[feet, faces], lag={"head": 1.0},
                 timing=dict(space="ground", tell=[4, 16], apex=16, contact=24, active=[21, 27], kind="dodge", glow=[STAFF] + list(LO),
                             ring_m=2.6, chain_from="READY", chain_to="READY",
                             shots=[(16, "aviso (rojo)", (STAFF,) + LO, RED)]),
                 events=[E(24, "Contact")], notes="la Barrida del Bastón: agachado del tigre (aviso f16), gira sobre el pie "
                                                  "izquierdo barriendo el disco de 2.6 m (Contact f24)")


# ============================================================================ el soplo desde el piso
GROUND_AIM = (0.0, -0.990, -0.14)                # de pie apunta casi horizontal (Kaito a más de 4.5 m)


def ground_pipe(extra=None, aim=GROUND_AIM):
    d = tuple(-x for x in aim)
    return merge(READY, dict(hips=(0.0, -0.02, -0.16), hips_rot=(6, 0, -16), spine=(4, 0, 6), spine1=(4, 0, 6), spine2=(6, 0, 4),
                             neck=(2, 0, 0), head=(6, 0, 0), face="blow"),
                 staff_lips(CR.STAFF_LEN, d, (0, 0, 1)), grip("l", CR.STAFF_LEN - 0.17, elbow=(1, 0.2, -0.6)),
                 grip("r", CR.STAFF_LEN - 0.32, elbow=(-1, 0.2, -0.6)), extra or {})


def flip_to_pipe(f0):
    """De la guardia a la cerbatana: la flauta-bastón tiene la boquilla adelante, así que la tira para arriba dando media
    vuelta delante de él (f0+2 la suelta la izquierda, f0+3 la derecha) y la ataja de punta en la boca (f0+6 / f0+7)."""
    toss = lambda top, d: staff_at(top, unit(d), CR.STAFF_LEN)
    return [
        K(f0 + 2, READY, dict(hips=(0.0, -0.02, -0.21)), staff_at((-0.20, -0.30, 1.30), unit((0.30, -0.70, 0.65)), 0.23),
          grip("r", 0.23, elbow=(-1, 0.4, -0.6)), free("l", (0.36, -0.40, 1.30), elbow=(1, 0.2, -0.6), fing="relaxed"), ease="inout"),
        K(f0 + 3, READY, dict(hips=(0.0, -0.02, -0.15)), toss((0.20, -1.00, 2.55), (0.05, -0.25, 0.97)),
          free("r", (-0.30, -0.40, 1.55), elbow=(-1, 0.2, -0.6), fing="relaxed"),
          free("l", (0.40, -0.42, 1.42), elbow=(1, 0.2, -0.6), fing="open"), ease="out"),
        K(f0 + 4, READY, dict(hips=(0.0, -0.02, -0.14)), toss((0.14, -0.80, 2.75), (0.08, 0.30, 0.95)),
          free("r", (-0.32, -0.46, 1.54), elbow=(-1, 0.15, -0.6), fing="open"),
          free("l", (0.37, -0.48, 1.50), elbow=(1, 0.15, -0.6), fing="open"), ease="lin"),
        K(f0 + 5, READY, dict(hips=(0.0, -0.02, -0.14), head=(0, 0, 0)), toss((0.08, -0.50, 2.55), (0.10, 0.75, 0.65)),
          free("r", (-0.24, -0.52, 1.78), elbow=(-1, 0.1, -0.6), fing="open"),
          free("l", (0.24, -0.54, 1.82), elbow=(1, 0.1, -0.6), fing="open"), ease="lin"),
        K(f0 + 6, ground_pipe(), free("r", (-0.16, -0.62, 1.70), elbow=(-1, 0.2, -0.6), fing="grip_stalk"), gw_r=0.5,
          grip_r=CR.STAFF_LEN - 0.32, grip_r_auto=1.0),
        K(f0 + 8, ground_pipe(), ease="out"),
    ]


def ground_dart():
    """El Soplo: tira la flauta-bastón para arriba y la ataja de cerbatana (aviso f9), apunta, sopla (DartSpawn f17) con un
    culatazo y la vuelve a la guardia dándola vuelta otra vez."""
    keys = [K(0, READY)] + flip_to_pipe(0) + [
        K(12, ground_pipe(dict(head=(7, 0, 0)), aim=GROUND_AIM), ease="sine"),
        K(16, ground_pipe(dict(head=(8, 0, 0), spine2=(7, 0, 4)))),
        K(17, ground_pipe(dict(hips=(0.0, 0.02, -0.15), head=(4, 0, 0), spine2=(4, 0, 4), clav_r=(0, 0, 4), clav_l=(0, 0, -4)),
                          aim=unit((0.0, -0.99, -0.06))), ease="snap"),
        K(18, ground_pipe(dict(head=(6, 0, 0))), ease="out"),
        # la tira para arriba en tres cuadros y la ataja en tres (de a dos, la flauta giraba 60° por cuadro y llegaba a la
        # guardia atrasada, de un salto en el último cuadro)
        K(21, READY, dict(hips=(0.0, -0.02, -0.15)), staff_at((0.10, -0.60, 2.30), unit((0.05, 0.40, 0.92)), CR.STAFF_LEN),
          free("r", (-0.30, -0.42, 1.52), elbow=(-1, 0.2, -0.6), fing="open"), free("l", (0.36, -0.44, 1.50), elbow=(1, 0.2, -0.6),
                                                                                    fing="open"), ease="out"),
        K(24, READY, dict(hips=(0.0, -0.02, -0.19)), staff_at((-0.25, -0.10, 1.10), unit((0.38, -0.80, 0.46)), 0.23),
          grip("r", 0.23, elbow=(-1, 0.4, -0.6)), free("l", (0.20, -0.45, 1.25), elbow=(1, 0.2, -0.6), fing="grip_stalk"), ease="lin"),
        K(25, READY, ease="out"),
    ]
    faces = face_track((0, "grin"), (4, "surprise"), (8, FACE_PUFF), (16, dict(FACE_PUFF, cheeks=1.35)), (17, FACE_BLOWN),
                       (20, "grin"), (25, "grin"))
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 25, r0[0], r0[1], r0[2])), "l": plants((0, 25, l0[0], l0[1], l0[2]))}
    feet = feet_track(keys, 25, plan)
    return CClip("GroundDart", 25, keys, tracks=[feet, faces], lag={"head": 1.0},
                 timing=dict(space="ground", tell=[2, 9], apex=9, kind="projectile", glow=list(HI) + [STAFF], chain_from="READY",
                             chain_to="READY", shots=[(12, "aviso (dorado)", HI + (STAFF,), GOLD)]),
                 events=[E(17, "DartSpawn")], notes="el Soplo desde el piso: da vuelta la flauta a la boca, DartSpawn f17")


# ============================================================================ el Paso del Ermitaño y el salto atrás
def back_flip(kit):
    """El Paso del Ermitaño: se agacha y se tira de espaldas en un mortal atrás con las rodillas al pecho (la flauta pegada
    al costado en la derecha), cae agachado 2.5 m atrás (el avance del código) y queda en guardia: aire f2 - f10."""
    tuck = legs((-0.16, -0.40, 0.30), (0.16, -0.42, 0.36), rr=(-30, 0, 0), rl=(-30, 0, 0), kr=(-0.2, -1, 0.3), kl=(0.2, -1, 0.3),
                hips=True)
    # la flauta de la guardia pegada al pecho con las dos manos (dando la vuelta va con el cuerpo y no toca el piso)
    carry = merge(guard_spine(kit), guard_grips())
    fl = lambda rx, z, y: merge(READY, carry, tuck, dict(hips=(0.0, y, z), hips_rot=(rx, 0, -10), spine=(14, 0, 0), spine1=(12, 0, 0),
                                                     spine2=(10, 0, 0), neck=(-10, 0, 0), head=(-20, 0, 0)))
    keys = [
        K(0, READY, travel=0.0),
        K(2, READY, carry, dict(hips=(0.0, 0.06, -0.34), hips_rot=(-14, 0, -10), spine2=(-4, 0, 0), head=(-12, 0, 0)), travel=0.0,
          ease="inout"),
        # la vuelta pareja, ~41° por cuadro del despegue (f2) al aterrizaje (f10), y el tronco se desenrosca antes de caer:
        # con la vuelta concentrada en el medio la cadera giraba 86° en un cuadro
        K(4, fl(-95.0, 0.20, 0.06), travel=-0.45, ease="lin"),
        K(6, fl(-178.0, 0.66, 0.06), travel=-1.10, ease="lin"),
        K(8, fl(-254.0, 0.60, 0.04), dict(spine=(12, 0, 0), spine1=(7, 0, 0), spine2=(9, 0, 0)), travel=-2.30, ease="lin"),
        K(10, merge(READY, carry, dict(hips=(0.0, -0.04, -0.36), hips_rot=(28, 0, -16), spine=(10, 0, 0), spine2=(8, 0, 0),
                                       head=(-6, 0, 0))), dict(hips_rot=(28 - 360.0, 0, -16)), travel=-2.50, ease="lin"),
        K(12, READY, dict(hips_rot=(6 - 360.0, 0, -22)), travel=-2.50, ease="inout"),
    ]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 2, r0[0], r0[1], r0[2], [(1, 0.0, "ball"), (2, 30.0, "ball")]), {"free": (3, 9)},
                        (10, 12, r0[0], r0[1] + 2.5, r0[2])),
            "l": plants((0, 2, l0[0], l0[1], l0[2], [(1, 0.0, "ball"), (2, 30.0, "ball")]), {"free": (3, 9)},
                        (10, 12, l0[0], l0[1] + 2.5, l0[2]))}
    feet = feet_track(keys, 12, plan)
    faces = face_track((0, "grin"), (3, "laugh"), (10, "grin"), (12, "grin"))
    return CClip("BackFlip", 12, keys, tracks=[feet, faces], lag={"head": 0.5},
                 spring_vel=None,
                 timing=dict(space="ground", air=[2, 10], chain_from="READY", chain_to="READY", invulnerable=[0, 10], hang_scale=0.0),
                 notes="el Paso del Ermitaño: mortal atrás de 2.5 m (travel_m), aire f2-f10")


def hop_back(kit):
    """El salto atrás grande (antes de la pértiga y de la pregunta): se agacha, salta de espaldas 4 m con las piernas
    recogidas y la flauta alzada en la derecha, la izquierda abierta para el equilibrio, y cae agachado: aire f3 - f12."""
    air = merge(READY, dict(hips=(0.0, 0.10, 0.30), hips_rot=(-14, 0, -8), spine=(6, 0, 0), spine1=(6, 0, 0), spine2=(6, 0, 0),
                            neck=(-4, 0, 0), head=(-10, 0, 0)),
                guard_spine(kit), guard_grips(),
                legs((-0.20, -0.32, 0.42), (0.20, -0.24, 0.28), rr=(-20, 0, -10), rl=(-30, 0, 10), kr=(-0.3, -1, 0.2), kl=(0.3, -1, 0.2),
                     hips=True))
    keys = [
        K(0, READY, travel=0.0),
        # el empuje en dos cuadros (en uno la tibia giraba 77°)
        K(2, READY, dict(hips=(0.0, 0.04, -0.40), hips_rot=(16, 0, -16), spine2=(10, 0, 0), head=(-10, 0, 0)), travel=0.0, ease="inout"),
        K(4, READY, dict(hips=(0.0, 0.10, -0.26), hips_rot=(4, 0, -12), spine2=(6, 0, 0), head=(-10, 0, 0)), guard_spine(kit),
          guard_grips(), travel=-0.20, ease="inout"),
        # despegando, los pies se quedan atrás del cuerpo que sale (en el clip quedan adelante: el código lo lleva atrás)
        K(5, air, legs((-0.28, -0.20, 0.55), (0.24, -0.40, 0.58), rr=(18, 0, -36), rl=(18, 0, 8), kr=(-0.6, -1, 0), kl=(0.3, -1, 0)),
          travel=-0.70, ease="out"),
        # las piernas se recogen en dos cuadros (en uno el pie giraba 90°)
        K(7, air, travel=-1.80, ease="inout"),
        K(9, air, dict(hips=(0.0, 0.10, 0.36)), travel=-2.80, ease="lin"),
        K(11, READY, dict(hips=(0.0, 0.04, -0.14), hips_rot=(4, 0, -14), spine2=(8, 0, 0), head=(-8, 0, 0)),
          legs((-0.30, 0.20, 0.19), (0.24, -0.30, 0.19), rr=(-12, 0, -40), rl=(-12, 0, 8), kr=(-0.7, -1, 0), kl=(0.3, -1, 0)),
          guard_spine(kit), guard_grips(), travel=-3.95, ease="out"),
        K(12, merge(READY, dict(hips=(0.0, 0.0, -0.42), hips_rot=(18, 0, -18), spine2=(10, 0, 0), head=(-8, 0, 0))), travel=-4.0,
          ease="out"),
        K(14, READY, travel=-4.0, ease="inout"),
    ]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 4, r0[0], r0[1], r0[2], [(1, 0.0, "ball"), (4, 30.0, "ball")]), {"free": (5, 11)},
                        (12, 14, r0[0], r0[1] + 4.0, r0[2])),
            "l": plants((0, 4, l0[0], l0[1], l0[2], [(1, 0.0, "ball"), (4, 30.0, "ball")]), {"free": (5, 11)},
                        (12, 14, l0[0], l0[1] + 4.0, l0[2]))}
    feet = feet_track(keys, 14, plan)
    faces = face_track((0, "grin"), (4, "laugh"), (12, "grin"), (14, "grin"))
    return CClip("HopBack", 14, keys, tracks=[feet, faces], lag={"head": 0.5},
                 timing=dict(space="ground", air=[3, 12], chain_from="READY", chain_to="READY", hang_scale=0.6),
                 notes="salto atrás de 4 m (travel_m), aire f3-f12")


# ============================================================================ la Grulla en el Bastón
POLE_BASE = (0.0, -0.45, -0.12)                  # la punta de abajo clavada 12 cm en el piso delante de él
POLE = staff_world(POLE_BASE, (0, 0, 1), (0, -1, 0))
POLE_TOP = POLE_BASE[2] + CR.STAFF_LEN           # 1.98 m: donde se para


def pole_plant():
    """Clava el bastón: lo levanta con las dos manos y lo hunde vertical en el piso delante de él (Plant f8)."""
    stand = merge(READY, POLE, grip("r", 1.05, elbow=(-1, 0.2, -0.6)), grip("l", 1.40, elbow=(1, 0.2, -0.6)),
                  dict(hips=(0.0, 0.02, -0.18), hips_rot=(10, 0, -8), spine2=(6, 0, 2), head=(-4, 0, 0)))
    keys = [
        K(0, READY),
        K(4, READY, staff_world((POLE_BASE[0], POLE_BASE[1], 0.40), (0.05, 0.0, 1.0), (0, -1, 0)), grip("r", 1.05, elbow=(-1, 0.2, -0.6)),
          grip("l", 1.40, elbow=(1, 0.2, -0.6)), dict(hips=(0.0, 0.0, -0.10), hips_rot=(0, 0, -12), head=(-8, 0, 0)), ease="inout"),
        K(8, stand, dict(hips=(0.0, 0.02, -0.24)), ease="in"),
        K(10, stand, dict(hips=(0.0, 0.02, -0.21)), ease="out"),
        K(14, stand, ease="inout"),
    ]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 14, r0[0], r0[1], r0[2])), "l": plants((0, 14, l0[0], l0[1], l0[2]))}
    feet = feet_track(keys, 14, plan)
    return CClip("PolePlant", 14, keys, tracks=[feet, face_track((0, "grin"), (8, FACE_FOCUS), (14, "grin"))], lag={"head": 1.0},
                 timing=dict(space="pole", chain_from="READY", chain_to="POLE", staff_in_floor=0.13),
                 events=[E(8, "Plant")], notes="clava el bastón vertical delante (Plant f8); queda agarrado a él")


BALANCE = merge(POLE, dict(hips=(0.06, -0.47, POLE_TOP + 0.95 - 1.06), hips_rot=(2, 0, 0), spine=(-2, 0, 0), spine1=(-2, 0, 0),
                           spine2=(2, 0, 0), neck=(-6, 0, 0), head=(-10, 0, 0), face="grin"),
                legs((-0.02, -0.45, POLE_TOP + ANKLE_Z), (0.22, -0.72, POLE_TOP + 0.62), rr=(0, 0, -10), rl=(-40, 0, 10),
                     kr=(-0.2, -1, 0), kl=(0.3, -1, 0.4)),
                free("r", (-0.80, -0.44, POLE_TOP + 1.62), elbow=(-0.4, 0.5, -0.6), fing="claw"),
                free("l", (0.82, -0.48, POLE_TOP + 1.68), elbow=(0.4, 0.5, -0.6), fing="claw"))


def pole_climb():
    """Sube por el bastón de un salto: se cuelga alto con las dos manos, los pies empujan contra el caño, tira y se para en
    la punta en un pie (cargado desde Load f0)."""
    keys = [
        K(0, READY, POLE, grip("r", 1.05, elbow=(-1, 0.2, -0.6)), grip("l", 1.40, elbow=(1, 0.2, -0.6)),
          dict(hips=(0.0, 0.02, -0.18), hips_rot=(10, 0, -8), spine2=(6, 0, 2), head=(-4, 0, 0))),
        K(2, POLE, grip("r", 1.05, elbow=(-1, 0.2, -0.6)), grip("l", 1.40, elbow=(1, 0.2, -0.6)), READY_FEET,
          dict(hips=(0.0, 0.04, -0.34), hips_rot=(14, 0, -8), spine2=(8, 0, 0), head=(-8, 0, 0)), ease="inout"),
        K(5, POLE, grip("r", 1.55, elbow=(-1, 0.3, -0.5)), grip("l", 1.85, elbow=(1, 0.3, -0.5)),
          dict(hips=(0.0, -0.10, 0.30), hips_rot=(20, 0, 0), spine2=(8, 0, 0), head=(-14, 0, 0)),
          legs((-0.10, -0.36, 0.75), (0.12, -0.38, 1.05), rr=(-40, 0, 0), rl=(-40, 0, 0), kr=(-0.6, -1, 0), kl=(0.6, -1, 0)), ease="out"),
        K(8, POLE, grip("r", 1.85, elbow=(-1, 0.3, 0.2)), grip("l", 1.95, elbow=(1, 0.3, 0.2)),
          dict(hips=(0.0, -0.30, 0.90), hips_rot=(30, 0, 0), spine=(10, 0, 0), spine2=(10, 0, 0), head=(-20, 0, 0)),
          legs((-0.08, -0.42, 1.55), (0.12, -0.44, 1.60), rr=(-30, 0, 0), rl=(-30, 0, 0), kr=(-0.6, -1, 0.4), kl=(0.6, -1, 0.4)),
          ease="inout"),
        K(11, BALANCE, dict(hips=(0.06, -0.46, POLE_TOP + 0.80 - 1.06), hips_rot=(10, 0, 0)),
          free("r", (-0.60, -0.40, POLE_TOP + 0.50), elbow=(-0.4, 0.5, -0.6), fing="open"),
          free("l", (0.62, -0.46, POLE_TOP + 0.55), elbow=(0.4, 0.5, -0.6), fing="open"), ease="out"),
        K(14, BALANCE, ease="inout"),
    ]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 2, r0[0], r0[1], r0[2], [(1, 0.0, "ball"), (2, 20.0, "ball")]), {"free": (3, 14)}),
            "l": plants((0, 2, l0[0], l0[1], l0[2], [(1, 0.0, "ball"), (2, 20.0, "ball")]), {"free": (3, 14)})}
    feet = feet_track(keys, 14, plan)
    return CClip("PoleClimb", 14, keys, tracks=[feet, face_track((0, "grin"), (4, "laugh"), (14, "grin"))], lag={"head": 1.0},
                 timing=dict(space="pole", load=[0, 14], chain_from="POLE", chain_to="BALANCE", staff_in_floor=0.13),
                 events=[E(0, "Load")], notes="sube por el bastón y queda parado en la punta en un pie (Load f0)")


def pole_balance():
    """Parado en un pie sobre la punta del bastón como una grulla, los brazos abiertos en garra; hace equilibrio (la cadera
    va y viene sobre el pie, los brazos compensan) con las campanas blancas. Loop de 30."""
    sway = lambda dx, rz, ar, al: merge(BALANCE, dict(hips=(0.06 + dx, -0.47, POLE_TOP + 0.95 - 1.06), hips_rot=(2, rz, 0)),
                                        free("r", (-0.80 + dx, -0.44, POLE_TOP + 1.62 + ar), elbow=(-0.4, 0.5, -0.6), fing="claw"),
                                        free("l", (0.82 + dx, -0.48, POLE_TOP + 1.68 + al), elbow=(0.4, 0.5, -0.6), fing="claw"))
    keys = [K(0, BALANCE), K(8, sway(0.02, 3.0, -0.08, 0.10), ease="sine"), K(15, BALANCE, ease="sine"),
            K(23, sway(-0.02, -3.0, 0.10, -0.08), ease="sine"), K(30, BALANCE, ease="sine")]
    return CClip("PoleBalance", 30, keys, loop=True, lag={"head": 1.5},
                 timing=dict(space="pole", load=[0, 30], chain_from="BALANCE", chain_to="BALANCE", root_offset=["PoleDive", 0, 0],
                             staff_in_floor=0.13,
                             shots=[(8, "la grulla en el bastón (cargada)", CHIMES_ALL, WHITE)]),
                 notes="la grulla en la punta del bastón, en un pie; loop cargado")


def lowered(c, dz):
    """Una pose corrida dz en altura (la cadera, los pies, las manos sueltas y la flauta del mundo): la de la punta del
    bastón llevada a la raíz del vuelo."""
    c = dict(c)
    for k in ("hips", "foot_r", "foot_l", "hand_r", "hand_l", "stw_pos"):
        v = c.get(k)
        if v is not None and not (k.startswith("foot_") and (c.get("fsp_" + k[-1]) or 0) > 0.5) and \
                not (k.startswith("hand_") and (c.get("hsp_" + k[-1]) or 0) > 0.5):
            c[k] = (v[0], v[1], v[2] + dz)
    return c


def pole_dive():
    """La picada desde la punta (roja, disco de 1.4 m): se agacha en la punta, salta arriba y adelante llevándose el bastón
    agarrado con los dedos del pie derecho (el mono), lo pasa a la mano en el aire y cae con la patada del concepto. Espacio
    'air' como la Picada: la raíz en los pies (en f0 la punta del bastón: root_offset_m de PoleBalance), LeaveStalk f0 y
    desde ahí el código la lleva por el arco hasta el disco; Contact f28 con el pie a la altura de la raíz."""
    T = -POLE_TOP
    top = lowered(BALANCE, T)
    crouch = merge(top, dict(hips=(0.06, -0.46, 0.66 - 1.06), hips_rot=(18, 0, 0), spine2=(12, 0, 0), head=(-4, 0, 0)),
                   legs((-0.02, -0.45, ANKLE_Z), (0.20, -0.62, 0.36), rr=(0, 0, -10), rl=(-30, 0, 10), kr=(-0.2, -1, 0),
                        kl=(0.3, -1, 0.4)),
                   free("r", (-0.62, 0.0, 0.80), elbow=(-0.5, 0.5, -0.6), fing="claw"),
                   free("l", (0.64, 0.0, 0.84), elbow=(0.5, 0.5, -0.6), fing="claw"))

    def toe_staff(ank):
        # el bastón colgando del pie derecho (agarrado con los dedos): vertical debajo del tobillo
        return staff_world((ank[0], ank[1] - 0.10, ank[2] - CR.STAFF_LEN + 0.02), (0, 0.05, 1), (0, -1, 0))
    lift = merge(crouch, dict(hips=(0.04, -0.60, 1.17 - 1.06), hips_rot=(-6, 0, 0), spine=(-4, 0, 0), spine2=(-2, 0, 0),
                              head=(-14, 0, 0)),
                 legs((-0.06, -0.50, 0.47), (0.18, -0.85, 0.77), rr=(-30, 0, -10), rl=(-40, 0, 10), kr=(-0.2, -1, 0.3),
                      kl=(0.3, -1, 0.4)),
                 toe_staff((-0.06, -0.50, 0.47)),
                 free("r", (-0.80, -0.30, 1.72), elbow=(-0.5, 0.5, -0.6), fing="claw"),
                 free("l", (0.80, -0.30, 1.74), elbow=(0.5, 0.5, -0.6), fing="claw"), toe_r=30.0)
    keys = [
        K(0, top),
        K(4, crouch, ease="inout"),
        K(7, lift, ease="out"),
        K(10, lift, dict(hips=(0.04, -0.40, 1.10 - 1.06)),
          legs((-0.10, -0.40, 0.62), (0.18, -0.60, 0.74), rr=(-40, 0, -10), rl=(-40, 0, 10), kr=(-0.2, -1, 0.3), kl=(0.3, -1, 0.4)),
          staff_world((-0.30, -0.40, -0.80), unit((-0.10, 0.20, 1.0)), (0, -1, 0)), grip("r", 1.60, elbow=(-1, 0.2, -0.4)), toe_r=0.0,
          ease="inout"),
        K(15, kick_pose(0.88, 0.22, 0.28), ease="out"),
        K(22, kick_pose(0.86, 0.24, 0.22), ease="sine"),
        K(28, kick_pose(0.80, 0.22, 0.115, -30.0), ease="in"),
        K(29, kick_pose(0.78, 0.22, 0.115, -28.0), ease="out"),
    ]
    faces = face_track((0, "grin"), (4, FACE_FOCUS), (10, FACE_SHOUT), (29, FACE_SHOUT))
    return CClip("PoleDive", 29, keys, tracks=[faces], lag={"head": 1.0}, spring_vel=lambda f: (0.0, -0.10 * f, -0.06 * f),
                 timing=dict(space="air", tell=[0, 14], apex=14, contact=28, kind="dodge", glow=[FOOT_R] + list(LO), ring_m=1.4,
                             chain_from="DIVE_TOP", chain_to="DIVE_LAND", fade_to=0.06,
                             shots=[(14, "picada (rojo)", (FOOT_R,) + LO, RED)]),
                 events=[E(0, "LeaveStalk"), E(28, "Contact")],
                 notes="la picada desde la punta del bastón (disco 1.4 m): LeaveStalk f0, Contact f28. La raíz en los pies "
                       "(arranca en la punta del bastón: root_offset_m de PoleBalance) y el código la lleva por el arco; el "
                       "pie de la patada toca a la altura de la raíz en f28")


# ============================================================================ la Pregunta y Respuesta (la flauta de costado)
# la flauta traversa del concepto: horizontal delante de la boca hacia su derecha, el agujero de soplar (Staff_Flute) en los
# labios, los dedos estirados sobre los agujeros, los ojos cerrados
FLUTE_AT = CR.STAFF_LEN - 0.14                   # Staff_Flute: el agujero de soplar, cerca de la boquilla
FLUTE = merge(READY, dict(hips=(0.0, 0.0, -0.12), hips_rot=(2, 0, -6), spine=(-2, 0, 4), spine1=(-2, 0, 2), spine2=(-2, 0, 2),
                          neck=(-4, 0, 0), head=(-6, 0, 8), face="flute"),
              staff_lips(FLUTE_AT, unit((0.86, 0.48, 0.15)), (0, -1, 0.2)),
              grip("l", FLUTE_AT - 0.20, elbow=(1, 0.2, -0.6), fing="flute"),
              grip("r", FLUTE_AT - 0.62, elbow=(-1, 0.2, -0.6), fing="flute"),
              # el pie izquierdo donde lo deja la guardia (FluteRaise y Detuned no lo mueven: llegan y salen de acá con él)
              legs((-0.22, 0.10, 0.115), (READY_L[0], READY_L[1], 0.115), rr=(0, 0, -16), rl=(0, 0, READY_L[2]), kr=(-0.3, -1, 0),
                   kl=(0.3, -1, 0)))


def flute_raise():
    """Se lleva la flauta de costado a la boca (la pose del concepto): la endereza, la gira delante del pecho y cierra los
    ojos."""
    keys = [
        K(0, READY),
        K(5, READY, dict(hips=(0.0, 0.0, -0.16), spine2=(2, 0, 2), head=(-4, 0, 4)),
          staff_at((-0.30, -0.30, 1.30), unit((0.70, -0.30, 0.65)), 0.30), grip("r", 0.30, elbow=(-1, 0.3, -0.6)),
          free("l", (0.30, -0.40, 1.40), elbow=(1, 0.2, -0.6), fing="relaxed"), ease="inout"),
        K(10, FLUTE, staff_lips(FLUTE_AT, unit((0.95, 0.15, 0.25)), (0, -1, 0.2)), dict(head=(-4, 0, 6)), ease="out"),
        K(14, FLUTE, ease="inout"),
    ]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 5, r0[0], r0[1], r0[2]), (10, 14, -0.22, 0.10, -16.0)),
            "l": plants((0, 14, l0[0], l0[1], l0[2]))}
    feet = feet_track(keys, 14, plan, lift=0.06)
    faces = face_track((0, "grin"), (8, "grin"), (12, "flute"), (14, "flute"))
    return CClip("FluteRaise", 14, keys, tracks=[feet, faces], lag={"head": 1.0},
                 timing=dict(space="ground", chain_from="READY", chain_to="FLUTE"),
                 notes="se lleva la flauta de costado a la boca (la pregunta)")


def flute_note():
    """Una nota de la pregunta (Note f0): sopla con un golpe de diafragma, el cuerpo se mece con la nota y los dedos
    levantan un agujero; vuelve a la pose de flauta (el código la repite por nota)."""
    keys = [
        K(0, FLUTE),
        K(2, FLUTE, dict(hips=(0.0, 0.01, -0.13), spine2=(-4, 0, 4), head=(-9, 0, 10), clav_r=(0, 0, 3), clav_l=(0, 0, -3)), ease="out"),
        K(7, FLUTE, dict(spine2=(-3, 0, 1), head=(-7, 0, 5), hips_rot=(2, 2, -6)), ease="sine"),
        K(13, FLUTE, ease="inout"),
    ]
    fing = [K(0, fing_l="flute"), K(1, fing_l=dict(fing=(4, 30, 20, 24), tip=(2, 14, 8, 12), spread=-2.0, thumb=(30, 16))),
            K(6, fing_l=dict(fing=(4, 30, 20, 24), tip=(2, 14, 8, 12), spread=-2.0, thumb=(30, 16))), K(10, fing_l="flute"),
            K(13, fing_l="flute")]
    faces = face_track((0, "flute"), (1, dict(CR.FACES["flute"], cheeks=0.6)), (8, "flute"), (13, "flute"))
    return CClip("FluteNote", 13, keys, tracks=[fing, faces], lag={"head": 1.0},
                 timing=dict(space="ground", chain_from="FLUTE", chain_to="FLUTE"),
                 events=[E(0, "Note")], notes="una nota de la pregunta (Note f0)")


FLUTE_DIR = unit((0.86, 0.48, 0.15))
FLUTE_GRIPS = (FLUTE_AT - 0.62, FLUTE_AT - 0.20)  # derecha, izquierda: donde la toman en la flauta de costado


def flute_turned(frac, extra=None):
    """La flauta girada 'frac' (0 = de costado, 1 = de punta hacia Kaito) alrededor de la boca, sin soltarla: las manos se
    quedan donde la agarran y van con ella (de cerbatana la boquilla entra a los labios)."""
    pipe = unit((0.0, 0.97, 0.24))
    a0 = math.atan2(FLUTE_DIR[1], FLUTE_DIR[0])
    a1 = math.atan2(pipe[1], pipe[0])
    a = a0 + (a1 - a0) * frac
    zc = FLUTE_DIR[2] + (pipe[2] - FLUTE_DIR[2]) * frac
    h = math.sqrt(max(0.0, 1.0 - zc * zc))
    d = (math.cos(a) * h, math.sin(a) * h, zc)
    at = FLUTE_AT + (CR.STAFF_LEN - FLUTE_AT) * frac
    up = (0.0, -1.0 + frac, 0.2 + 0.8 * frac)
    return merge(FLUTE, staff_lips(at, d, up), grip("r", FLUTE_GRIPS[0], elbow=(-1, 0.2, -0.6), fing="flute" if frac < 0.5 else "grip_staff"),
                 grip("l", FLUTE_GRIPS[1], elbow=(1, 0.2, -0.6), fing="flute" if frac < 0.5 else "grip_staff"), extra or {})


def answer_blow():
    """La nota aguda de la respuesta: gira la flauta de costado a cerbatana sin sacarla de la boca (las manos van con
    ella) y sopla un dardo (DartSpawn f4); vuelve a la flauta de costado."""
    keys = [
        K(0, FLUTE),
        K(1, flute_turned(0.30), ease="in"),
        K(2, flute_turned(0.65, dict(head=(0, 0, 4))), ease="lin"),
        K(3, flute_turned(1.0, dict(head=(4, 0, 0), spine2=(4, 0, 0), face="blow")), ease="out"),
        K(4, flute_turned(1.0, dict(hips=(0.0, 0.03, -0.11), head=(1, 0, 0), clav_r=(0, 0, 4), clav_l=(0, 0, -4), face="blow")),
          ease="snap"),
        K(7, flute_turned(1.0, dict(head=(4, 0, 0), face="blow")), ease="out"),
        K(10, flute_turned(0.45), ease="inout"),
        K(13, FLUTE, ease="inout"),
    ]
    faces = face_track((0, "flute"), (2, FACE_PUFF), (4, FACE_BLOWN), (8, "grin"), (12, "flute"), (13, "flute"))
    return CClip("AnswerBlow", 13, keys, tracks=[faces], lag={"head": 1.0},
                 timing=dict(space="ground", kind="projectile", glow=list(HI), chain_from="FLUTE", chain_to="FLUTE",
                             shots=[(3, "respuesta aguda (dorado)", HI, GOLD)]),
                 events=[E(4, "DartSpawn")], notes="la nota aguda de la respuesta: de punta, sopla un dardo (DartSpawn f4)")


def answer_stamp():
    """La nota grave de la respuesta: baja la punta de abajo de la flauta de un golpe girándola sobre las manos y la clava
    parada en el piso a su derecha (Stamp f4: brota el retoño debajo de Kaito); la vuelve a subir de costado. Las manos no
    se deslizan: la agarran donde la tenían."""
    r_at, l_at = FLUTE_GRIPS

    def down(frac, extra=None):
        # de la flauta de costado (en los labios) a parada en el piso: gira alrededor de la derecha, que baja al costado
        d0, d1 = FLUTE_DIR, unit((0.02, 0.02, 1.0))
        d = unit(tuple(a + (b - a) * frac for a, b in zip(d0, d1)))
        hand0, hand1 = (-0.56, -0.34, 1.86), (-0.50, -0.16, r_at)
        hand = tuple(a + (b - a) * frac for a, b in zip(hand0, hand1))
        return merge(FLUTE, staff_at(hand, d, r_at), grip("r", r_at, elbow=(-1, 0.2, -0.6), fing="grip_staff"),
                     grip("l", l_at, elbow=(1, 0.2, -0.6), fing="grip_staff"), extra or {})
    stamp = down(1.0, dict(hips=(0.0, 0.0, -0.22), hips_rot=(6, 0, -10), spine2=(6, 0, -4), head=(-2, 0, -6), face="laugh"))
    keys = [
        K(0, FLUTE),
        K(2, down(0.45, dict(hips=(0.0, 0.0, -0.12))), ease="out"),
        K(4, stamp, ease="in"),
        K(7, stamp, dict(hips=(0.0, 0.0, -0.20)), ease="out"),
        K(10, down(0.45), ease="inout"),
        K(13, FLUTE, ease="inout"),
    ]
    faces = face_track((0, "flute"), (3, FACE_SHOUT), (4, "laugh"), (9, "grin"), (13, "flute"))
    return CClip("AnswerStamp", 13, keys, tracks=[faces], lag={"head": 1.0},
                 timing=dict(space="ground", kind="dodge", glow=list(LO), chain_from="FLUTE", chain_to="FLUTE",
                             shots=[(3, "respuesta grave (rojo)", LO, RED)]),
                 events=[E(4, "Stamp")], notes="la nota grave: golpea el piso con el bastón (Stamp f4) y brota el retoño")


def clips(kit):
    return ([idle()] + locomotion() +
            [back_flip(kit), hop_back(kit), thrust(), staff_spin2(), crane_kick(), note_smash(), low_sweep(), ground_dart(),
             pole_plant(), pole_climb(), pole_balance(), pole_dive(), flute_raise(), flute_note(), answer_blow(),
             answer_stamp(), ground_laugh()])
