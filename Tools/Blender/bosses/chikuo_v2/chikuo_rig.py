"""Esqueleto del Chikuō ermitaño (fase C4) y la traducción de controles de pose a huesos.

El concepto elegido (Docs/handoff/conceptos/chikuo_v2/elegido_*.jpg): un viejo ermitaño flaco de 2.45 m hasta la punta
del moño, de miembros largos, manos y pies grandes para trepar, con gi salvia, capa de hojas con cascabeles huecos y
una flauta-bastón. Esqueleto de juego limpio (manos bajo antebrazos, pies bajo tibias, ningún hueso de IK en el FBX,
una sola raíz 'Root' que ningún clip anima). Además de la cadena humana (Hips, Spine, Spine1, Spine2, Neck, Head):
  * la cara: 'Jaw' (la risa, soplar), 'Lid_*' (los párpados: cierran los ojos al tocar y al reírse), 'Brow_*' (las
    cejas en púas, rígidas), 'Cheek_*' (los cachetes que se inflan al soplar) y 'MouthCorner_*' (la sonrisa que se
    junta en la boquilla);
  * dedos de dos falanges y 'Toe_*' para agarrar la caña y el bastón (HAND_SHAPES);
  * 'Staff' (la flauta-bastón, hijo de Root: libre en el mundo, las manos la agarran) con sus enchufes
    'Staff_Muzzle' (la punta de abajo, de donde salen los dardos), 'Staff_Mouth' (la punta de arriba, la boquilla de
    la cerbatana), 'Staff_Flute' (el agujero de soplar de costado) y 'Staff_Grip' (el centro del vendado);
  * cadenas que el juego puede mover con SpringChain ('Acc_<Nombre>_0..n' + '_end', la convención de los kits):
    la barba ('TasselBeard', 4 tramos), la ramita de hojas del moño ('LeafKnot'), las colas de la faja
    ('TieSashA/B') y un hueso por cascabel ('ChimesHi00..09' en los hombros, 'ChimesLo00..11' en la espalda: el
    perfil 'Chimes' de SpringChain), con las esferas 'AccCol_*' del pecho, la panza, la espalda y los muslos;
  * cadenas horneadas en los clips (sin el prefijo Acc_, a propósito): el moño ('Topknot_1..2'), las mangas
    ('Sleeve_*_1..2'), los cuatro paños de la falda del gi ('Skirt_<ángulo>') y los doce paños de la capa
    ('Cloak_<ángulo>_1..2'). SpringChain saltea toda cadena que cuelgue de otra Acc_ (SpringChain.Rebuild): si la
    capa fuera Acc_ los cascabeles, que cuelgan de ella y tienen que sonar y moverse solos, quedarían quietos.

Ejes: Blender Z arriba, frente -Y, derecha del personaje = -X. Los ángulos alrededor del cuerpo se miden desde el frente
y crecen hacia la izquierda del personaje (+X): 90 = su izquierda, 270 = su derecha.
"""
import math
from mathutils import Vector, Matrix, Quaternion
import nindo_anim as NA
from nindo_anim import BoneDef, V, euler_q, basis_yz, compose, rot3

# ------------------------------------------------------------------ medidas (metros, pose de reposo)
TOP = 2.45                                   # punta del moño
# piernas abiertas 8° (el pantalón inflado no se cruza entre las rodillas) y los pies apenas hacia afuera
HIP_J = Vector((-0.12, 0.0, 1.10))           # cabeza del muslo derecho
KNEE = Vector((-0.175, -0.045, 0.60))        # rodilla adelantada: el IK sabe para dónde doblar
ANKLE = Vector((-0.23, 0.0, 0.115))
BALL = Vector((-0.245, -0.17, 0.035))        # bola del pie: de acá dobla la punta
TOE_TIP = Vector((-0.258, -0.295, 0.03))
SOLE_TOE_Y, SOLE_HEEL_Y = -0.305, 0.115      # punta y talón de la suela (pies de 42 cm: los de alguien que trepa)
SHOULDER = Vector((-0.20, 0.03, 1.85))
UPPER_LEN, FORE_LEN, HAND_LEN = 0.39, 0.36, 0.115
ARM_OUT_DEG = 35.0                           # pose A: el brazo abierto 35° (deforma limpio el hombro)
_u = Vector((-math.sin(math.radians(ARM_OUT_DEG)), 0.0, -math.cos(math.radians(ARM_OUT_DEG))))
ELBOW = SHOULDER + _u * UPPER_LEN
_l = (_u + Vector((0.0, -0.15, 0.0))).normalized()        # codo apenas doblado
WRIST = ELBOW + _l * FORE_LEN
_h = (_l + Vector((0.0, -0.05, 0.0))).normalized()        # la mano sigue al antebrazo
KNUCKLE = WRIST + _h * HAND_LEN
# marco de la mano derecha en reposo: dedos (_h), dorso (afuera) y hacia el pulgar (adelante): la palma mira al muslo
_DORS = (Vector((-1.0, 0.0, 0.0)) - _h * Vector((-1.0, 0.0, 0.0)).dot(_h)).normalized()
_THUMB_SIDE = -(_h.cross(_DORS)).normalized()
# centro de la palma y punto por donde pasa un caño agarrado con el puño (espacio del hueso de la mano: Y dedos, Z dorso)
PALM_LOCAL = Vector((0.0, 0.065, -0.026))
GRIP_LOCAL = Vector((0.0, 0.095, -0.052))
# dedos: (nombre, corrimiento hacia el pulgar desde el centro de los nudillos, falange 1, falange 2)
FINGERS = [("Index", 0.034, 0.060, 0.050), ("Middle", 0.011, 0.066, 0.054),
           ("Ring", -0.012, 0.062, 0.050), ("Pinky", -0.034, 0.050, 0.040)]
THUMB_BASE_LOCAL = Vector((-0.036, 0.024, -0.020))
THUMB_DIR_LOCAL = Vector((-0.55, 0.78, -0.30))
THUMB_LEN = (0.052, 0.045)

# cara (lado derecho): ojo (hundido bajo el arco de la ceja), ceja, cachete, comisura de la sonrisa ancha
EYE_R = Vector((-0.036, -0.083, 2.154))
BROW_R = (Vector((-0.014, -0.106, 2.176)), Vector((-0.092, -0.080, 2.198)))
CHEEK_R = (Vector((-0.058, -0.062, 2.108)), Vector((-0.068, -0.088, 2.108)))
CORNER_R = (Vector((-0.050, -0.074, 2.090)), Vector((-0.054, -0.094, 2.092)))
JAW = (Vector((0.0, -0.004, 2.126)), Vector((0.0, -0.072, 2.036)))
# el moño arriba y atrás, inclinado 25° hacia atrás (de perfil se va para la nuca)
TOPKNOT_AXIS = Vector((0.0, math.sin(math.radians(25.0)), math.cos(math.radians(25.0))))
TOPKNOT_BASE = Vector((0.0, 0.046, 2.247))
TOPKNOT = [TOPKNOT_BASE, TOPKNOT_BASE + TOPKNOT_AXIS * 0.09, TOPKNOT_BASE + TOPKNOT_AXIS * 0.215]
LEAF_KNOT = [TOPKNOT_BASE + TOPKNOT_AXIS * 0.022 + Vector((0, 0.03, 0)), Vector((0.0, 0.12, 2.258)),
             Vector((0.0, 0.16, 2.232)), Vector((0.0, 0.19, 2.205))]
# la barba cuelga delante del pecho con aire (de perfil se separa del gi, como en la hoja)
BEARD = [Vector((0.0, -0.078, 2.035)), Vector((0.0, -0.150, 1.905)), Vector((0.0, -0.174, 1.79)),
         Vector((0.0, -0.180, 1.69)), Vector((0.0, -0.182, 1.585)), Vector((0.0, -0.178, 1.52))]
MOUTH = Vector((0.0, -0.106, 2.080))          # entre los labios: donde va la boquilla de la cerbatana
# faja: el nudo al frente, de donde cuelgan las dos colas color paja
SASH_Z = (1.395, 1.495)
SASH_KNOT = Vector((0.012, -0.176, 1.447))
SASH_A = [SASH_KNOT + Vector((-0.016, -0.022, -0.03)), SASH_KNOT + Vector((-0.024, -0.042, -0.22)),
          SASH_KNOT + Vector((-0.026, -0.052, -0.42)), SASH_KNOT + Vector((-0.026, -0.054, -0.47))]
SASH_B = [SASH_KNOT + Vector((0.03, -0.018, -0.035)), SASH_KNOT + Vector((0.052, -0.036, -0.21)),
          SASH_KNOT + Vector((0.066, -0.046, -0.37)), SASH_KNOT + Vector((0.068, -0.048, -0.42))]
# falda del gi: cuatro paños (ángulo desde el frente, + hacia su izquierda) de la cintura al ruedo
SKIRT_ANGLES = [40.0, 140.0, 220.0, 320.0]
SKIRT_TOP_Z, SKIRT_HEM_Z = 1.40, 0.86
SKIRT_TOP_R = (0.205, 0.158)
SKIRT_HEM_R = (0.345, 0.285)
# capa: doce paños de dos tramos por los hombros y la espalda; abierta adelante (de -25° a 25° se ve el gi)
CLOAK_ANGLES = [38.0, 64.0, 90.0, 116.0, 142.0, 168.0, 192.0, 218.0, 244.0, 270.0, 296.0, 322.0]
CLOAK_OPEN = 25.0
CLOAK_Y0 = 0.02                              # eje de la capa (la nuca, apenas atrás del eje del cuerpo)
# perfil de la caída (distancia al eje, altura) del cuello al ruedo, por ángulo. Como en el concepto: adelante cuelga a
# los lados del pecho hasta la faja (por dentro del brazo); al costado cubre el hombro y el brazo (en la pose A la
# manga queda 5-9 cm abajo); atrás del brazo baja hasta la cadera y en la espalda hasta las corvas
CLOAK_PROFILES = [
    (38.0, [(0.105, 1.975), (0.17, 1.945), (0.22, 1.86), (0.245, 1.70), (0.255, 1.50), (0.265, 1.32)]),
    (64.0, [(0.11, 1.975), (0.21, 1.95), (0.30, 1.87), (0.34, 1.70), (0.35, 1.50), (0.36, 1.34)]),
    (90.0, [(0.11, 1.975), (0.25, 1.955), (0.38, 1.87), (0.50, 1.72), (0.58, 1.55)]),
    (116.0, [(0.11, 1.975), (0.24, 1.95), (0.35, 1.85), (0.40, 1.65), (0.42, 1.40), (0.44, 1.16)]),
    (140.0, [(0.105, 1.975), (0.22, 1.94), (0.32, 1.82), (0.37, 1.60), (0.39, 1.30), (0.41, 0.98)]),
    (180.0, [(0.10, 1.975), (0.19, 1.925), (0.235, 1.76), (0.255, 1.46), (0.29, 1.10), (0.33, 0.72)]),
]
CLOAK_SPLIT = 0.46                           # dónde se parte cada paño en sus dos tramos (fracción de la caída)
# cascabeles: (grupo, ángulo, fracción de la caída donde se ata el cordón, largo del cordón, largo del tubo, radio)
CHIMES = [
    # los agudos: tres adelante en el hombro (los que ve la cámara del juego) y dos arriba de la espalda
    ("Hi", 42.0, 0.30, 0.035, 0.150, 0.033), ("Hi", 62.0, 0.36, 0.05, 0.165, 0.034), ("Hi", 84.0, 0.40, 0.04, 0.155, 0.033),
    ("Hi", 150.0, 0.24, 0.045, 0.160, 0.034), ("Hi", 170.0, 0.21, 0.035, 0.145, 0.033),
    # los graves: dos hileras en la espalda, más largos y gruesos
    ("Lo", 120.0, 0.50, 0.05, 0.205, 0.036), ("Lo", 140.0, 0.56, 0.065, 0.23, 0.037), ("Lo", 160.0, 0.50, 0.05, 0.24, 0.037),
    ("Lo", 176.0, 0.62, 0.06, 0.22, 0.037), ("Lo", 132.0, 0.80, 0.05, 0.25, 0.038), ("Lo", 156.0, 0.78, 0.045, 0.21, 0.037),
]
# flauta-bastón: 2.1 m, Ø 6 cm; en reposo parada a la derecha (el juego la mueve; no cambia el alto de bind)
STAFF_LEN = 2.10
STAFF_R = 0.030
STAFF_BOTTOM = Vector((-0.86, -0.06, 0.0))
STAFF_GRIP = (0.08, 0.38)                    # el vendado, metros desde la punta de abajo
STAFF_FLUTE = 0.075                          # el agujero de soplar, metros desde la punta de arriba
# esferas de colisión de las cadenas (nombre, hueso, centro en el mundo de reposo, radio)
CHAIN_COLLIDERS = [("Chest", "Spine2", Vector((0.0, -0.02, 1.75)), 0.16), ("Belly", "Spine", Vector((0.0, -0.03, 1.40)), 0.17),
                   ("Back", "Spine2", Vector((0.0, 0.0, 1.56)), 0.26), ("Rump", "Hips", Vector((0.0, 0.05, 1.06)), 0.28),
                   ("ThighR", "Thigh_R", Vector((-0.15, -0.06, 0.90)), 0.17),
                   ("ThighL", "Thigh_L", Vector((0.15, -0.06, 0.90)), 0.17)]


def mx(v):
    return Vector((-v.x, v.y, v.z))


def ang_name(a):
    return f"{int(round(a)) % 360:03d}"


def skirt_name(a):
    return "Skirt_" + ang_name(a)


def cloak_name(a, seg):
    return f"Cloak_{ang_name(a)}_{seg}"


def chime_name(group, i):
    return f"Acc_Chimes{group}{i:02d}"


def chimes_full():
    """Los cascabeles de los dos lados: [(nombre del hueso sin _0, grupo, ángulo, caída, cordón, tubo, radio)]; los de
    su izquierda son los de la tabla y los de su derecha su espejo, numerados por grupo."""
    out, n = [], {"Hi": 0, "Lo": 0}
    for side in (1, -1):
        for g, a, s, cord, ln, r in CHIMES:
            out.append((chime_name(g, n[g]), g, a if side > 0 else 360.0 - a, s, cord, ln, r))
            n[g] += 1
    return out


def _resample(pts, n):
    """Puntos (r, z) repartidos por largo de arco en n muestras."""
    P = [Vector((r, z)) for r, z in pts]
    acc = [0.0]
    for a, b in zip(P[:-1], P[1:]):
        acc.append(acc[-1] + (b - a).length)
    out = []
    for i in range(n):
        s = acc[-1] * i / (n - 1)
        j = max(k for k in range(len(acc)) if acc[k] <= s + 1e-9)
        j = min(j, len(P) - 2)
        u = (s - acc[j]) / max(1e-9, acc[j + 1] - acc[j])
        out.append(P[j].lerp(P[j + 1], u))
    return out


_PROF_N = 13
_PROF = [(a, _resample(p, _PROF_N)) for a, p in CLOAK_PROFILES]


def cloak_rz(phi, s):
    """(distancia al eje, altura) de la capa en el ángulo phi (grados) y la fracción s de la caída."""
    a = abs(((phi + 180.0) % 360.0) - 180.0)
    a = max(_PROF[0][0], min(_PROF[-1][0], a))
    for (a0, p0), (a1, p1) in zip(_PROF[:-1], _PROF[1:]):
        if a0 <= a <= a1:
            t = (a - a0) / (a1 - a0)
            t = t * t * (3 - 2 * t)
            break
    k = max(0.0, min(1.0, s)) * (_PROF_N - 1)
    i = min(int(k), _PROF_N - 2)
    u = k - i
    q0 = p0[i].lerp(p0[i + 1], u)
    q1 = p1[i].lerp(p1[i + 1], u)
    return q0.lerp(q1, t)


def cloak_point(phi, s, out=0.0):
    """Punto de la superficie de la capa (más 'out' metros hacia afuera, en el plano del perfil)."""
    rz = cloak_rz(phi, s)
    # normal del perfil (hacia afuera y arriba): perpendicular a la tangente de la caída
    e = 0.02
    t = (cloak_rz(phi, min(1.0, s + e)) - cloak_rz(phi, max(0.0, s - e)))
    nrm = Vector((t.y, -t.x)).normalized() if t.length > 1e-9 else Vector((1.0, 0.0))
    if nrm.x < 0:
        nrm = -nrm
    r, z = rz.x + nrm.x * out, rz.y + nrm.y * out
    ar = math.radians(phi)
    return Vector((math.sin(ar) * r, CLOAK_Y0 - math.cos(ar) * r, z))


def cloak_normal(phi, s):
    return (cloak_point(phi, s, 0.01) - cloak_point(phi, s, 0.0)).normalized()


def skirt_frame(a):
    """(cabeza en la cintura, punta en el ruedo) del paño de la falda en el ángulo a."""
    r = math.radians(a)
    h = Vector((math.sin(r) * SKIRT_TOP_R[0], -math.cos(r) * SKIRT_TOP_R[1], SKIRT_TOP_Z))
    t = Vector((math.sin(r) * SKIRT_HEM_R[0], -math.cos(r) * SKIRT_HEM_R[1], SKIRT_HEM_Z))
    return h, t


def chain_bones(name, pts, parent, roll=(0, -1, 0), prefix="Acc_"):
    """Cadena '<prefix><name>_0..n-1' por los puntos y su punta '_end' (sin pesos: SpringChain la necesita para saber
    dónde termina el último tramo)."""
    out = []
    p = parent
    for i in range(len(pts) - 1):
        bn = f"{prefix}{name}_{i}"
        out.append(BoneDef(bn, pts[i], pts[i + 1], p, True, roll))
        p = bn
    d = (pts[-1] - pts[-2]).normalized()
    out.append(BoneDef(f"{prefix}{name}_end", pts[-1], pts[-1] + d * 0.04, p, True, roll))
    return out


def hand_frame(S):
    """(muñeca, dedos, dorso, hacia el pulgar) de la mano S en reposo."""
    m = (lambda v: v) if S == "R" else mx
    return m(WRIST), m(_h), m(_DORS), m(_THUMB_SIDE)


def sleeve_points(S):
    """(cabeza, cola) de los dos huesos del vuelo de la manga: cuelgan hacia abajo del brazo, uno a la altura del codo
    y otro cerca del puño."""
    m = (lambda v: v) if S == "R" else mx
    a = SHOULDER + _u * (UPPER_LEN * 0.72)
    b = ELBOW + _l * 0.12
    down = Vector((0.0, 0.0, -1.0))
    return (m(a), m(a + down * 0.13)), (m(b), m(b + down * 0.15))


CHIME_OUT = 0.058                            # el cordón se ata sobre las hojas (la hoja de arriba de esa hilera)


def chime_attach(phi, s):
    """Donde se ata el cordón de un cascabel: afuera de las hojas de la capa (cuelga encima, se ve entero)."""
    return cloak_point(phi, s, CHIME_OUT)


def chime_axis(phi, s):
    """Hacia dónde cuelga en reposo: casi vertical, apenas apoyado en la capa (la sigue cuando se abre hacia el ruedo)."""
    e = 0.03
    t = (cloak_point(phi, min(1.0, s + e), CHIME_OUT) - cloak_point(phi, max(0.0, s - e), CHIME_OUT)).normalized()
    return (Vector((0.0, 0.0, -1.0)) * 0.55 + t * 0.45).normalized()


def chime_parent(phi, s):
    """El paño (y tramo) de la capa que lleva el punto de atadura: el ángulo más cercano y el tramo según la caída."""
    a = min(CLOAK_ANGLES, key=lambda x: abs(((phi - x + 180.0) % 360.0) - 180.0))
    return cloak_name(a, 1 if s < CLOAK_SPLIT else 2)


def bones():
    B = [
        BoneDef("Root", (0, 0, 0), (0, 0, 0.3), None, True, (0, -1, 0)),
        BoneDef("Hips", (0, 0, 1.06), (0, 0, 1.24), "Root"),
        BoneDef("Spine", (0, 0, 1.24), (0, 0.0, 1.42), "Hips"),
        BoneDef("Spine1", (0, 0, 1.42), (0, 0.01, 1.62), "Spine"),
        BoneDef("Spine2", (0, 0.01, 1.62), (0, 0.03, 1.86), "Spine1"),
        BoneDef("Neck", (0, 0.03, 1.88), (0, 0.005, 2.02), "Spine2"),
        BoneDef("Head", (0, 0.005, 2.02), (0, 0.005, 2.27), "Neck"),
        BoneDef("Jaw", JAW[0], JAW[1], "Head", True, (0, -1, 0)),
        BoneDef("Topknot_1", TOPKNOT[0], TOPKNOT[1], "Head", True, (0, -1, 0)),
        BoneDef("Topknot_2", TOPKNOT[1], TOPKNOT[2], "Topknot_1", True, (0, -1, 0)),
        # párpado: el pivote en el centro del ojo, Y hacia adelante (gira en X para cerrar)
        BoneDef("Lid_R", EYE_R, EYE_R + Vector((0, -0.03, 0)), "Head", True, (0, 0, 1)),
        BoneDef("Brow_R", BROW_R[0], BROW_R[1], "Head", True, (0, -0.3, 1)),
        BoneDef("Cheek_R", CHEEK_R[0], CHEEK_R[1], "Head", True, (0, 0, 1)),
        BoneDef("MouthCorner_R", CORNER_R[0], CORNER_R[1], "Head", True, (0, 0, 1)),
        BoneDef("Clav_R", (-0.035, 0.02, 1.83), SHOULDER, "Spine2", True, (0, 0, 1)),
        BoneDef("UpperArm_R", SHOULDER, ELBOW, "Clav_R", True, (0, -1, 0)),
        BoneDef("Forearm_R", ELBOW, WRIST, "UpperArm_R", True, (0, -1, 0)),
        BoneDef("Hand_R", WRIST, KNUCKLE, "Forearm_R", True, tuple(_DORS)),
        BoneDef("Thigh_R", HIP_J, KNEE, "Hips", True, (0, -1, 0)),
        BoneDef("Shin_R", KNEE, ANKLE, "Thigh_R", True, (0, -1, 0)),
        BoneDef("Foot_R", ANKLE, BALL, "Shin_R", True, (0, 0, 1)),
        BoneDef("Toe_R", BALL, TOE_TIP, "Foot_R", True, (0, 0, 1)),
    ]
    (s1h, s1t), (s2h, s2t) = sleeve_points("R")
    B.append(BoneDef("Sleeve_R_1", s1h, s1t, "UpperArm_R", True, (0, -1, 0)))
    B.append(BoneDef("Sleeve_R_2", s2h, s2t, "Forearm_R", True, (0, -1, 0)))
    for name, off, l1, l2 in FINGERS:
        base = KNUCKLE + _THUMB_SIDE * off - _DORS * 0.005
        mid = base + _h * l1
        B.append(BoneDef(f"{name}_R_1", base, mid, "Hand_R", True, tuple(_DORS)))
        B.append(BoneDef(f"{name}_R_2", mid, mid + _h * l2, f"{name}_R_1", True, tuple(_DORS)))
    Rm = basis_yz(_h, _DORS)
    tb = WRIST + Rm @ THUMB_BASE_LOCAL
    td = (Rm @ THUMB_DIR_LOCAL).normalized()
    tz = (_DORS - td * _DORS.dot(td)).normalized()
    B.append(BoneDef("Thumb_R_1", tb, tb + td * THUMB_LEN[0], "Hand_R", True, tuple(tz)))
    t2 = (td + _h * 0.35).normalized()
    B.append(BoneDef("Thumb_R_2", tb + td * THUMB_LEN[0], tb + td * THUMB_LEN[0] + t2 * THUMB_LEN[1], "Thumb_R_1", True, tuple(tz)))
    B = NA.mirrored(B)
    # cadenas con física posible (Acc_): la barba cuelga de la quijada, la ramita del cordón del moño, las colas de la faja
    B += chain_bones("TasselBeard", BEARD, "Jaw")
    B += chain_bones("LeafKnot", LEAF_KNOT, "Head")
    B += chain_bones("TieSashA", SASH_A, "Hips")
    B += chain_bones("TieSashB", SASH_B, "Hips")
    # falda del gi
    for a in SKIRT_ANGLES:
        h, t = skirt_frame(a)
        out = Vector((math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0))
        B.append(BoneDef(skirt_name(a), h, t, "Hips", True, tuple(out)))
    # capa: el primer tramo cuelga del pecho (Spine2), el segundo del primero; Z del hueso hacia afuera
    for a in CLOAK_ANGLES:
        p0, p1, p2 = cloak_point(a, 0.10), cloak_point(a, CLOAK_SPLIT), cloak_point(a, 1.0)
        nrm = cloak_normal(a, 0.3)
        B.append(BoneDef(cloak_name(a, 1), p0, p1, "Spine2", True, tuple(nrm)))
        B.append(BoneDef(cloak_name(a, 2), p1, p2, cloak_name(a, 1), True, tuple(cloak_normal(a, 0.75))))
    # cascabeles: un hueso por tubo, del nudo del cordón a la punta de abajo del tubo, hijo del tramo de capa que lo lleva
    for name, g, a, s, cord, ln, r in chimes_full():
        top = chime_attach(a, s)
        ax = chime_axis(a, s)
        bot = top + ax * (cord + ln)
        nrm = cloak_normal(a, s)
        B += chain_bones(name[len("Acc_"):], [top, bot], chime_parent(a, s), roll=tuple(nrm))
    for name, parent, c, r in CHAIN_COLLIDERS:
        bn = f"AccCol_{name}_{int(round(r * 100))}"
        B.append(BoneDef(bn, c, c + Vector((0, 0, 0.05)), parent, True, (0, -1, 0)))
        B.append(BoneDef(bn + "_r", c + Vector((r, 0, 0)), c + Vector((r, 0, 0.05)), bn, True, (0, -1, 0)))
    # flauta-bastón: Y a lo largo, de la punta de abajo (la boca de los dardos) a la de arriba (la boquilla)
    top = STAFF_BOTTOM + Vector((0, 0, STAFF_LEN))
    B += [
        BoneDef("Staff", STAFF_BOTTOM, top, "Root", True, (0, -1, 0)),
        BoneDef("Staff_Muzzle", STAFF_BOTTOM, STAFF_BOTTOM - Vector((0, 0, 0.05)), "Staff", True, (0, -1, 0)),
        BoneDef("Staff_Mouth", top, top + Vector((0, 0, 0.05)), "Staff", True, (0, -1, 0)),
        BoneDef("Staff_Flute", top - Vector((0, 0, STAFF_FLUTE)), top - Vector((0, 0.05, STAFF_FLUTE)), "Staff", True, (0, 0, 1)),
        BoneDef("Staff_Grip", STAFF_BOTTOM + Vector((0, 0, sum(STAFF_GRIP) * 0.5)),
                STAFF_BOTTOM + Vector((0, 0, sum(STAFF_GRIP) * 0.5 + 0.05)), "Staff", True, (0, -1, 0)),
        # marcador de frente (exportado: el validador de Unity comprueba que mire a +Z)
        BoneDef("Facing", (0, -0.35, 2.0), (0, -0.65, 2.0), "Root", True, (0, 0, 1)),
    ]
    return B


FINGER_BONES = [f"{n}_{S}_{i}" for S in "RL" for n, *_ in FINGERS for i in (1, 2)] + [f"Thumb_{S}_{i}" for S in "RL" for i in (1, 2)]

# formas de la mano: curva de la falange 1 y de la 2 por dedo (índice, medio, anular, meñique; grados hacia la palma),
# apertura (grados, + = abanico) y pulgar (base, punta)
HAND_SHAPES = {
    "relaxed": dict(fing=(16, 20, 24, 28), tip=(18, 22, 26, 30), spread=3.0, thumb=(12, 10)),
    "open": dict(fing=(2, 2, 4, 6), tip=(4, 4, 6, 8), spread=10.0, thumb=(0, 0)),
    # la garra del ermitaño (manos huesudas que se abren: el concepto en el salto)
    "claw": dict(fing=(18, 16, 18, 22), tip=(62, 66, 68, 70), spread=14.0, thumb=(28, 36)),
    "fist": dict(fing=(88, 92, 94, 96), tip=(100, 102, 104, 106), spread=-2.0, thumb=(48, 58)),
    # puño en la caña (culmo de ~0.2 m: los dedos abrazan sin cerrarse) y en el bastón (6 cm)
    "grip_stalk": dict(fing=(46, 50, 54, 58), tip=(52, 56, 58, 62), spread=-1.0, thumb=(34, 26)),
    "grip_staff": dict(fing=(70, 74, 78, 82), tip=(82, 84, 86, 88), spread=-1.0, thumb=(42, 34)),
    # tocando la flauta: los dedos estirados apoyados en los agujeros
    "flute": dict(fing=(22, 26, 30, 34), tip=(14, 16, 18, 22), spread=-2.0, thumb=(30, 16)),
}


def hand_shape(S, name):
    """Canales de los dedos de la mano S ('r' o 'l') con la forma 'name' de HAND_SHAPES."""
    h = HAND_SHAPES[name]
    s = S.lower()
    return {f"fing_{s}": h["fing"], f"tip_{s}": h["tip"], f"spread_{s}": h["spread"], f"thumb_{s}": h["thumb"]}


# caras: (quijada abierta en grados, párpados 0 abiertos .. 1 cerrados, cejas en grados (+ arriba), cachetes 0..1
# inflados, comisuras (adentro m, arriba m))
FACES = {
    "grin": dict(jaw=0.0, lids=0.25, brows=0.0, cheeks=0.0, corners=(0.0, 0.0)),
    "blow": dict(jaw=-1.5, lids=0.45, brows=6.0, cheeks=1.0, corners=(0.014, -0.004)),
    "laugh": dict(jaw=19.0, lids=1.0, brows=12.0, cheeks=0.0, corners=(-0.004, 0.006)),
    "flute": dict(jaw=1.0, lids=1.0, brows=4.0, cheeks=0.35, corners=(0.008, -0.002)),
    "surprise": dict(jaw=12.0, lids=0.0, brows=16.0, cheeks=0.0, corners=(0.006, -0.004)),
}


def chains():
    """Las cadenas que cuelgan en una pose de prueba (resortes de nindo_anim): (huesos, rigidez, cuánto busca colgar,
    tope en grados). Las mismas que el paso de animación hornea."""
    out = []
    out.append((["Acc_TasselBeard_%d" % i for i in range(4)], 60.0, 0.55, 70.0))
    out.append((["Topknot_1", "Topknot_2"], 400.0, 0.05, 15.0))
    out.append((["Acc_LeafKnot_0", "Acc_LeafKnot_1"], 120.0, 0.35, 60.0))
    out.append((["Acc_TieSashA_0", "Acc_TieSashA_1"], 50.0, 0.7, 85.0))
    out.append((["Acc_TieSashB_0", "Acc_TieSashB_1"], 50.0, 0.7, 85.0))
    for S in "RL":
        out.append(([f"Sleeve_{S}_1"], 80.0, 0.6, 70.0))
        out.append(([f"Sleeve_{S}_2"], 80.0, 0.6, 70.0))
    for a in SKIRT_ANGLES:
        out.append(([skirt_name(a)], 160.0, 0.35, 60.0))
    # la capa de hojas pesa: cuelga de los hombros casi a plomo aunque el tronco se incline (agachado, colgado)
    for a in CLOAK_ANGLES:
        out.append(([cloak_name(a, 1), cloak_name(a, 2)], 90.0, 0.72, 85.0))
    for name, *_ in chimes_full():
        out.append(([name + "_0"], 40.0, 0.9, 80.0))
    return out


# ------------------------------------------------------------------ pose de prueba (controles -> huesos)
NEUTRAL = {
    "hips": (0.0, 0.0, 0.0), "hips_rot": (0.0, 0.0, 0.0),
    "spine": (0.0, 0.0, 0.0), "spine1": (0.0, 0.0, 0.0), "spine2": (0.0, 0.0, 0.0), "neck": (0.0, 0.0, 0.0),
    "head": (0.0, 0.0, 0.0), "clav_r": (0.0, 0.0, 0.0), "clav_l": (0.0, 0.0, 0.0),
    "foot_r": tuple(ANKLE), "foot_l": tuple(mx(ANKLE)), "foot_r_rot": (0.0, 0.0, 0.0), "foot_l_rot": (0.0, 0.0, 0.0),
    "knee_r": (0.0, -1.0, 0.0), "knee_l": (0.0, -1.0, 0.0), "toe_r": 0.0, "toe_l": 0.0,
    "face": "grin", "extra": {},
}


class Poser:
    """Resuelve una pose de prueba: cadera y tronco por giros, brazos y piernas por IK de dos huesos (o FK si la pose
    no pide la mano), dedos por forma, la flauta-bastón en el mundo o en una mano, y la cara."""

    def __init__(self, rig):
        self.rig = rig

    def solve(self, pose, c):
        c = {**NEUTRAL, **{k: v for k, v in c.items() if v is not None}}
        R = self.rig
        hip_rest = R.rest["Hips"]
        Hm = compose(hip_rest.translation + V(c["hips"]), euler_q(c["hips_rot"]).to_matrix() @ rot3(hip_rest))
        pose.place("Hips", Hm)
        for bn, k in (("Spine", "spine"), ("Spine1", "spine1"), ("Spine2", "spine2"), ("Neck", "neck"), ("Head", "head"),
                      ("Clav_R", "clav_r"), ("Clav_L", "clav_l")):
            pose.delta(bn, c[k])
        # la flauta-bastón en el mundo (antes de las manos que la agarran): dada, o con un punto suyo en los labios
        # ('staff_lips': metros desde la punta de abajo, dirección de abajo hacia arriba, hacia dónde mira su Z)
        st = c.get("staff_world")
        lips = c.get("staff_lips")
        if lips:
            at, d, up = lips
            d = V(d).normalized()
            mouth = pose.get("Head") @ R.rest_inv["Head"] @ MOUTH
            st = (mouth - d * at, d, up)
        if st:
            bottom, d, up = V(st[0]), V(st[1]).normalized(), V(st[2] if len(st) > 2 else (0, 0, 1))
            pose.place("Staff", compose(bottom, basis_yz(d, up - d * up.dot(d) if (up - d * up.dot(d)).length > 1e-4
                                                          else d.orthogonal())))
        misses = {}
        for S in "RL":
            s = S.lower()
            sg = 1.0 if S == "R" else -1.0
            grip = c.get("grip_" + s)            # (distancia desde la punta de abajo, hacia dónde mira el dorso)
            target = c.get("hand_" + s)
            if grip is not None and st:
                Wst = pose.get("Staff")
                ax = rot3(Wst).col[1]
                gp = Wst.translation + ax * grip[0]
                dors = V(grip[1])
                dors = (dors - ax * dors.dot(ax)).normalized()
                # el caño cruza la palma por el eje X del hueso de la mano: el meñique hacia la punta de abajo si 'grip[2]'
                xdir = ax * (sg if len(grip) < 3 else grip[2])
                ydir = dors.cross(xdir).normalized()
                Hr = Matrix((xdir, ydir, dors)).transposed()
                wrist = gp - Hr @ GRIP_LOCAL
                self.reach_with_clavicle(pose, S, wrist)
                misses[s] = pose.two_bone("UpperArm_" + S, "Forearm_" + S, wrist, c.get("elbow_" + s, (sg * -0.3, 0.2, -1)))
                pose.place("Hand_" + S, compose(pose.tail("Forearm_" + S), Hr))
                pose.twist_follow("Forearm_" + S, "Hand_" + S, 0.5)
            elif target is not None:
                hd, hu = V(c.get("hand_%s_dir" % s, (0, 0, -1))), V(c.get("hand_%s_up" % s, (-sg, 0, 0)))
                Hr = basis_yz(hd, hu)
                wrist = V(target)
                self.reach_with_clavicle(pose, S, wrist)
                misses[s] = pose.two_bone("UpperArm_" + S, "Forearm_" + S, wrist, c.get("elbow_" + s, (sg * -0.3, 0.2, -1)))
                pose.place("Hand_" + S, compose(pose.tail("Forearm_" + S), Hr))
                pose.twist_follow("Forearm_" + S, "Hand_" + S, 0.5)
            else:
                for bn in ("UpperArm_", "Forearm_", "Hand_"):
                    pose.delta(bn + S, c.get(bn.lower() + s, (0.0, 0.0, 0.0)))
            self.fingers(pose, S, c.get("fingers_" + s, "relaxed"))
            # piernas
            ank = V(c["foot_" + s])
            pr = c["foot_" + s + "_rot"]
            Rf = (Matrix.Rotation(math.radians(pr[2]), 3, 'Z') @ Matrix.Rotation(math.radians(pr[0]), 3, 'X')
                  @ Matrix.Rotation(math.radians(pr[1]), 3, 'Y')) @ rot3(R.rest["Foot_" + S])
            misses["leg_" + s] = pose.two_bone("Thigh_" + S, "Shin_" + S, ank, c["knee_" + s])
            pose.place("Foot_" + S, compose(pose.tail("Shin_" + S), Rf))
            ax = rot3(R.rest["Toe_" + S]).col[0]
            pose.delta("Toe_" + S, Quaternion(ax, math.radians(c["toe_" + s])))
        if not st:
            sh = c.get("staff_hand")
            if sh:
                # la flauta en una mano (el puño la atraviesa): (mano, distancia desde la punta de abajo, signo)
                S, at, sign = sh
                Hw = pose.get("Hand_" + S)
                ax = rot3(Hw).col[0] * sign
                gp = Hw @ GRIP_LOCAL
                bottom = gp - ax * at
                up = rot3(Hw).col[2]
                pose.place("Staff", compose(bottom, basis_yz(ax, up)))
        self.follow_cloak(pose)
        self.face(pose, c["face"])
        for bn, r in c["extra"].items():
            pose.delta(bn, r)
        self.misses = misses
        return misses

    # cuánto del giro del brazo se lleva cada paño de la capa (el primer tramo): los de los costados cubren el brazo
    CLOAK_FOLLOW = {38.0: 0.15, 64.0: 0.28, 90.0: 0.38, 116.0: 0.25, 142.0: 0.08}

    def follow_cloak(self, pose):
        """Los paños de la capa que cubren el brazo lo siguen cuando se levanta o se abre (si no, el brazo los atraviesa),
        y bajan con él: el giro del brazo respecto del pecho, en parte. Los cascabeles que cuelgan de ellos van juntos.
        El paso de animación hace lo mismo antes de los resortes (es la pose rígida a la que tiran)."""
        R = self.rig
        Ds2 = rot3(pose.get("Spine2")) @ rot3(R.rest["Spine2"]).transposed()
        for S, sg in (("L", 1.0), ("R", -1.0)):
            Dua = rot3(pose.get("UpperArm_" + S)) @ rot3(R.rest["UpperArm_" + S]).transposed()
            q = (Ds2.transposed() @ Dua).to_quaternion()
            for a, f in self.CLOAK_FOLLOW.items():
                ang = a if sg > 0 else 360.0 - a
                pose.delta(cloak_name(ang, 1), Quaternion().slerp(q, f))

    def fingers(self, pose, S, shape):
        h = HAND_SHAPES[shape]
        R = self.rig
        for i, (name, *_r) in enumerate(FINGERS):
            for j, key in ((1, "fing"), (2, "tip")):
                bn = f"{name}_{S}_{j}"
                ax = rot3(R.rest[bn]).col[0]
                q = Quaternion(ax, -math.radians(h[key][i]))
                if j == 1:
                    # abanico: alrededor del dorso, cada dedo hacia su lado del centro de la mano
                    zx = rot3(R.rest[bn]).col[2]
                    fan = (1.5 - i) * h["spread"] / 1.5
                    sgn = 1.0 if S == "R" else -1.0
                    q = Quaternion(zx, math.radians(fan) * sgn) @ q
                pose.delta(bn, q)
        for j, v in ((1, h["thumb"][0]), (2, h["thumb"][1])):
            bn = f"Thumb_{S}_{j}"
            ax = rot3(R.rest[bn]).col[0]
            pose.delta(bn, Quaternion(ax, -math.radians(v)))

    def face(self, pose, name):
        f = FACES[name] if isinstance(name, str) else name
        R = self.rig
        # la X de la quijada mira a su derecha: abrir (el mentón baja) es girar en negativo
        ax = rot3(R.rest["Jaw"]).col[0]
        pose.delta("Jaw", Quaternion(ax, -math.radians(f["jaw"])))
        for S in "RL":
            sg = 1.0 if S == "R" else -1.0
            # párpado: el reposo es el ojo abierto entero; cerrar es girar hacia abajo 38°
            ax = rot3(R.rest["Lid_" + S]).col[0]
            pose.delta("Lid_" + S, Quaternion(ax, -math.radians(38.0 * f["lids"])))
            # ceja: gira alrededor del eje de adelante y la punta de afuera sube (+) o baja
            pose.delta("Brow_" + S, Quaternion(Vector((0, 1, 0)), math.radians(f["brows"]) * sg))
            out = rot3(R.rest["Cheek_" + S]).col[1]
            pose.delta("Cheek_" + S, (0.0, 0.0, 0.0), loc=out * 0.014 * f["cheeks"] + Vector((sg * -0.006 * f["cheeks"], 0, 0)))
            ci, cu = f["corners"]
            pose.delta("MouthCorner_" + S, (0.0, 0.0, 0.0), loc=Vector((sg * ci, -0.4 * ci, cu)))

    def reach_with_clavicle(self, pose, S, target, max_deg=26.0):
        """Si la muñeca no llega, el hombro se adelanta (la clavícula gira hacia el objetivo)."""
        R = self.rig
        cl, ua, fa = "Clav_" + S, "UpperArm_" + S, "Forearm_" + S
        reach = (R.length[ua] + R.length[fa]) * 0.985
        for _ in range(2):
            sh = (pose.get(cl) @ R.rel[ua]).translation
            ex = (V(target) - sh).length - reach
            if ex <= 0.0:
                return
            ch = pose.head(cl)
            a = (sh - ch)
            b = (V(target) - ch)
            axv = a.cross(b)
            if axv.length < 1e-6:
                return
            ang = min(ex / max(a.length, 1e-3), math.radians(max_deg))
            M = pose.get(cl)
            Rq = Quaternion(axv.normalized(), ang).to_matrix()
            pose.place(cl, compose(ch, Rq @ rot3(M)))
