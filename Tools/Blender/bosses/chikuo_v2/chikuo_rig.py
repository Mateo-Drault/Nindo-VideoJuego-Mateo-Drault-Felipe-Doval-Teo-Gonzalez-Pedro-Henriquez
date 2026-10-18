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
    la barba ('TasselBeard', 4 tramos, cuelga de la cabeza), la ramita de hojas del moño ('LeafKnot'), las colas de la
    faja ('TieSashA/B') y un hueso por cascabel ('ChimesHi00..09' en los hombros, 'ChimesLo00..15' en la espalda: el
    perfil 'Chimes' de SpringChain), con las esferas 'AccCol_*' del pecho, la panza, la espalda de la capa, la cadera,
    los muslos, los brazos y la flauta (ninguna cadena queda adentro de una esfera en reposo: build_chikuo lo mide);
  * cadenas horneadas en los clips (sin el prefijo Acc_, a propósito): el moño ('Topknot_1..2'), las mangas
    ('Sleeve_*_1..2'), los cuatro paños de la falda del gi ('Skirt_<ángulo>') y los doce paños de la capa
    ('Cloak_<ángulo>_1..2' adelante y en los hombros, '_1..3' detrás del brazo y en la espalda: se doblan en el posado,
    colgado y en las patadas). SpringChain saltea toda cadena que cuelgue de otra Acc_ (SpringChain.Rebuild): si la
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
UPPER_LEN, FORE_LEN, HAND_LEN = 0.39, 0.36, 0.135
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
PALM_LOCAL = Vector((0.0, 0.076, -0.029))
GRIP_LOCAL = Vector((0.0, 0.110, -0.057))
# dedos: (nombre, corrimiento hacia el pulgar desde el centro de los nudillos, falange 1, falange 2): las manos grandes y
# huesudas del concepto (un 20 % más que una mano de su alto)
FINGERS = [("Index", 0.038, 0.072, 0.060), ("Middle", 0.012, 0.079, 0.065),
           ("Ring", -0.013, 0.074, 0.060), ("Pinky", -0.038, 0.060, 0.048)]
# en el reposo los dedos ya vienen doblados 10° por falange (la mano relajada de la hoja, no una tabla): las formas de
# HAND_SHAPES miden desde ahí
FINGER_REST_CURL = 10.0
THUMB_BASE_LOCAL = Vector((-0.040, 0.028, -0.022))
THUMB_DIR_LOCAL = Vector((-0.55, 0.78, -0.30))
THUMB_LEN = (0.060, 0.052)

# cabeza: se autora en un marco propio (los anillos y los rasgos de chikuo_model, las medidas *_S de acá abajo) y
# head_t la lleva a su lugar. Medida sobre la hoja de modelado a escala (chikuo_overlay), la cara del concepto es tan
# alta como la autorada pero 18 % más ancha (0.22 m de pómulo a pómulo) y más honda, y está 4 cm adelante y 2 abajo:
# el cuello se inclina hacia adelante (el viejo encorvado del perfil) y la barba cuelga delante del pecho
HEAD_SRC = Vector((0.0, 0.005, 2.02))        # el pivote de la cabeza en el marco de autoría
HEAD_J = Vector((0.0, -0.035, 2.0))          # el pivote de la cabeza en el modelo (la base del cráneo)
HEAD_S = Vector((1.18, 1.10, 1.06))
HEAD_SX_TOP = 1.00                           # el ancho se estira en la cara; el cráneo, arriba de las sienes, casi no
HEAD_SX_BACK = 0.35                          # y la nuca solo un tercio: de espaldas el pelo no es un casco más ancho


def head_sx(z_src, y_src):
    t = max(0.0, min(1.0, (z_src - 2.13) / 0.09))
    sx = HEAD_S.x + (HEAD_SX_TOP - HEAD_S.x) * t * t * (3.0 - 2.0 * t)
    u = max(0.0, min(1.0, (y_src + 0.02) / 0.09))
    return 1.0 + (sx - 1.0) * (1.0 + (HEAD_SX_BACK - 1.0) * u * u * (3.0 - 2.0 * u))


def head_t(p):
    """Del marco de autoría de la cabeza al modelo (el ancho depende de la altura y de la profundidad, que no cambian con
    x: la vuelta es exacta)."""
    p = Vector(p)
    d = p - HEAD_SRC
    return HEAD_J + Vector((d.x * head_sx(p.z, p.y), d.y * HEAD_S.y, d.z * HEAD_S.z))


def head_t_inv(p):
    d = Vector(p) - HEAD_J
    z = HEAD_SRC.z + d.z / HEAD_S.z
    y = HEAD_SRC.y + d.y / HEAD_S.y
    return Vector((d.x / head_sx(z, y), y, z))


# cara en el marco de autoría (lado derecho): ojo (hundido bajo el arco de la ceja), ceja, cachete, comisura de la
# sonrisa en medialuna (sube hasta el pómulo, como en la hoja de detalles)
EYE_S = Vector((-0.040, -0.083, 2.154))
# el pivote del párpado, 1.2 cm detrás del ojo: desde ahí el ojo entero entra en el casquete (cerrado lo tapa todo)
LID_S = EYE_S + Vector((0.0, 0.012, 0.0))
BROW_S = (Vector((-0.014, -0.105, 2.170)), Vector((-0.090, -0.080, 2.200)))
CHEEK_S = (Vector((-0.066, -0.054, 2.110)), Vector((-0.078, -0.078, 2.110)))
CORNER_S = (Vector((-0.064, -0.071, 2.0955)), Vector((-0.068, -0.091, 2.0965)))
JAW_S = (Vector((0.0, -0.004, 2.126)), Vector((0.0, -0.072, 2.030)))
MOUTH_S = Vector((0.0, -0.104, 2.0625))      # entre los labios: donde va la boquilla de la cerbatana
EYE_R, LID_R, MOUTH = head_t(EYE_S), head_t(LID_S), head_t(MOUTH_S)
BROW_R, CHEEK_R, CORNER_R, JAW = [tuple(head_t(p) for p in pr) for pr in (BROW_S, CHEEK_S, CORNER_S, JAW_S)]
# el moño en la coronilla, atrás de la calva, apenas inclinado hacia la nuca: de frente es una llama derecha (la hoja
# de modelado) y de perfil se va un poco atrás (la hoja original y la de detalles); se autora ya en el modelo
TOPKNOT_AXIS = Vector((0.0, math.sin(math.radians(18.0)), math.cos(math.radians(18.0))))
TOPKNOT_BASE = Vector((0.0, 0.016, 2.256))
TOPKNOT = [TOPKNOT_BASE, TOPKNOT_BASE + TOPKNOT_AXIS * 0.075, TOPKNOT_BASE + TOPKNOT_AXIS * 0.195]
# la ramita del cordón: hacia atrás y a los costados (de espaldas es un moño de hojas)
LEAF_KNOT = [TOPKNOT_BASE + TOPKNOT_AXIS * 0.03 + Vector((0, 0.03, 0)), TOPKNOT_BASE + Vector((0, 0.10, 0.012)),
             TOPKNOT_BASE + Vector((0, 0.15, -0.012)), TOPKNOT_BASE + Vector((0, 0.18, -0.04))]
# la barba cuelga del mentón delante del pecho con aire (de perfil se separa del gi, como en la hoja) y termina en el
# nudo trenzado y la punta a la altura de la faja
BEARD = [Vector((0.0, -0.140, 2.030)), Vector((0.0, -0.182, 1.915)), Vector((0.0, -0.188, 1.810)),
         Vector((0.0, -0.183, 1.720)), Vector((0.0, -0.176, 1.625)), Vector((0.0, -0.170, 1.555))]
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
# capa: doce paños por los hombros y la espalda, abierta adelante como en la hoja: entre los dos bordes (a 56° del frente:
# 0.19 m del eje en el pecho) se ve el gi entero con las solapas, y de perfil la barba queda delante de todo. Los dos
# del frente de cada lado son capas cortas de hombro; detrás del brazo y en la espalda cuelgan derecho hasta las corvas
# (la parva del concepto: de atrás angosta arriba y abierta hacia abajo)
CLOAK_ANGLES = [58.0, 80.0, 102.0, 124.0, 146.0, 168.0, 192.0, 214.0, 236.0, 258.0, 280.0, 302.0]
CLOAK_OPEN = 56.0
CLOAK_Y0 = 0.02                              # eje de la capa (la nuca, apenas atrás del eje del cuerpo)
# perfil de la caída (distancia al eje, altura) del cuello al ruedo, por ángulo. Medido sobre la hoja de modelado a
# escala: adelante la capa de hombro baja hasta 1.53 sin pasar de y -0.10 (la barba de perfil se ve entera); sobre el
# hombro cubre el brazo de la pose A (la manga queda 3-5 cm abajo) hasta el codo; detrás del brazo baja hasta la
# cadera y en la espalda hasta media pantorrilla, abriéndose hacia abajo como una parva (de espaldas, angosta arriba y
# ancha abajo: a plomo se leía como un huevo)
CLOAK_PROFILES = [
    (58.0, [(0.12, 1.985), (0.185, 1.955), (0.215, 1.88), (0.225, 1.76), (0.23, 1.64), (0.232, 1.53)]),
    (80.0, [(0.12, 1.985), (0.25, 1.96), (0.36, 1.90), (0.45, 1.80), (0.51, 1.68), (0.55, 1.55)]),
    (104.0, [(0.12, 1.985), (0.25, 1.955), (0.37, 1.885), (0.44, 1.75), (0.47, 1.56), (0.48, 1.34), (0.48, 1.05)]),
    (135.0, [(0.115, 1.985), (0.235, 1.95), (0.34, 1.86), (0.39, 1.70), (0.42, 1.45), (0.43, 1.15), (0.44, 0.78)]),
    (180.0, [(0.105, 1.985), (0.21, 1.935), (0.28, 1.80), (0.32, 1.55), (0.345, 1.20), (0.36, 0.80), (0.37, 0.45)]),
]
# tramos por paño y dónde se parten (fracción de la caída)
CLOAK_SPLITS = {2: (0.46,), 3: (0.34, 0.66)}


def cloak_segs(a):
    """Los paños del frente y de los hombros, cortos, tienen dos tramos; los de detrás del brazo y la espalda, tres."""
    return 3 if abs(((a + 180.0) % 360.0) - 180.0) > 95.0 else 2


def cloak_seg_of(a, s):
    return 1 + sum(1 for x in CLOAK_SPLITS[cloak_segs(a)] if s >= x)


def cloak_bones():
    return [cloak_name(a, i) for a in CLOAK_ANGLES for i in range(1, cloak_segs(a) + 1)]


# cascabeles, uno por uno (sin espejo): racimos de dos y tres a alturas distintas, como en la hoja (grupo, ángulo, altura
# del nudo del cordón, largo del cordón, largo del tubo, radio). Los agudos, en los dos hombros adelante (los que ve la
# cámara del juego): un racimo alto y uno más abajo de cada lado. Los graves, por toda la espalda entre 1.85 y 0.95 m, en
# racimos con huecos de 9 a 22° y largos de 0.16 a 0.30 m: en hileras parejas (como estaban) se leían como una cartuchera
# y no como los cascabeles colgados entre las hojas del concepto
CHIMES = [
    ("Hi", 57.0, 1.855, 0.035, 0.190, 0.031), ("Hi", 67.0, 1.800, 0.055, 0.240, 0.032),
    ("Hi", 84.0, 1.745, 0.030, 0.200, 0.031), ("Hi", 92.0, 1.735, 0.040, 0.180, 0.032), ("Hi", 103.0, 1.720, 0.040, 0.175, 0.031),
    ("Hi", 303.0, 1.840, 0.045, 0.215, 0.031), ("Hi", 294.0, 1.780, 0.035, 0.170, 0.032), ("Hi", 285.0, 1.860, 0.055, 0.250, 0.031),
    ("Hi", 268.0, 1.725, 0.030, 0.195, 0.032), ("Hi", 258.0, 1.640, 0.050, 0.190, 0.031),
    ("Lo", 124.0, 1.830, 0.045, 0.200, 0.032), ("Lo", 134.0, 1.740, 0.060, 0.270, 0.032), ("Lo", 143.0, 1.850, 0.035, 0.170, 0.033),
    ("Lo", 165.0, 1.640, 0.055, 0.300, 0.033), ("Lo", 175.0, 1.720, 0.040, 0.215, 0.033),
    ("Lo", 194.0, 1.845, 0.065, 0.240, 0.033), ("Lo", 204.0, 1.760, 0.035, 0.185, 0.032), ("Lo", 214.0, 1.830, 0.055, 0.280, 0.032),
    ("Lo", 230.0, 1.680, 0.040, 0.205, 0.032), ("Lo", 239.0, 1.770, 0.035, 0.160, 0.032),
    ("Lo", 146.0, 1.360, 0.035, 0.250, 0.034), ("Lo", 155.0, 1.440, 0.030, 0.190, 0.033),
    ("Lo", 207.0, 1.300, 0.050, 0.290, 0.034), ("Lo", 216.0, 1.390, 0.035, 0.210, 0.033),
    ("Lo", 176.0, 1.080, 0.040, 0.260, 0.034), ("Lo", 187.0, 0.980, 0.035, 0.220, 0.034),
]
# flauta-bastón: 2.1 m, Ø 6 cm; en reposo parada a la derecha (el juego la mueve; no cambia el alto de bind)
STAFF_LEN = 2.10
STAFF_R = 0.030
STAFF_BOTTOM = Vector((-0.86, -0.06, 0.0))
STAFF_GRIP = (0.08, 0.38)                    # el vendado, metros desde la punta de abajo
STAFF_FLUTE = 0.075                          # el agujero de soplar, metros desde la punta de arriba
# esferas de colisión de las cadenas de SpringChain (nombre, hueso, centro en el mundo de reposo, radio). Todas las
# cadenas chocan con todas: ninguna cadena puede quedar adentro de una esfera en reposo (la empujaría y temblaría), y
# build_chikuo lo mide. La del pecho deja la barba delante del gi; la de la espalda de la capa está detrás del cuerpo
# (deja los graves afuera de las hojas sin tocar la barba); los brazos y la flauta apartan la barba y los cascabeles
CHAIN_COLLIDERS = [("Chest", "Spine2", Vector((0.0, 0.01, 1.72)), 0.13), ("Belly", "Spine", Vector((0.0, 0.0, 1.38)), 0.16),
                   ("CloakBack", "Spine2", Vector((0.0, 0.10, 1.36)), 0.22), ("Rump", "Hips", Vector((0.0, 0.08, 1.04)), 0.26),
                   ("ThighR", "Thigh_R", Vector((-0.15, -0.06, 0.90)), 0.17),
                   ("ThighL", "Thigh_L", Vector((0.15, -0.06, 0.90)), 0.17)]
# las de los brazos y la flauta van a mitad de hueso y a 0.12 y 0.30 m de la boquilla (las calcula bones())
LIMB_COLLIDERS = [("UpperArmR", "UpperArm_R", 0.5, 0.09), ("UpperArmL", "UpperArm_L", 0.5, 0.09),
                  ("ForearmR", "Forearm_R", 0.5, 0.07), ("ForearmL", "Forearm_L", 0.5, 0.07)]
STAFF_COLLIDERS = [("StaffA", 0.12, 0.05), ("StaffB", 0.30, 0.05)]


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
    """Los cascabeles: [(nombre del hueso sin _0, grupo, ángulo, caída, cordón, tubo, radio)], numerados por grupo en el
    orden de la tabla; la caída es la fracción del perfil de la capa donde el nudo queda a la altura de la tabla."""
    out, n = [], {"Hi": 0, "Lo": 0}
    for g, a, z, cord, ln, r in CHIMES:
        out.append((chime_name(g, n[g]), g, a, chime_drop(a, z), cord, ln, r))
        n[g] += 1
    return out


def chime_drop(phi, z):
    """La fracción de la caída de la capa en el ángulo phi donde el nudo del cordón (afuera de las hojas) queda a la
    altura z."""
    lo, hi = 0.0, 1.0
    for _ in range(30):
        m = (lo + hi) * 0.5
        if cloak_point(phi, m, CHIME_OUT).z > z:
            lo = m
        else:
            hi = m
    return round((lo + hi) * 0.5, 4)


def collider_specs():
    """Todas las esferas: (nombre del hueso AccCol_..., hueso padre, centro en el reposo, radio)."""
    out = [(f"AccCol_{n}_{int(round(r * 100)):02d}", b, c, r) for n, b, c, r in CHAIN_COLLIDERS]
    for n, b, t, r in LIMB_COLLIDERS:
        h, tl = (ELBOW, WRIST) if b.startswith("Forearm") else (SHOULDER, ELBOW)
        p = h.lerp(tl, t)
        out.append((f"AccCol_{n}_{int(round(r * 100)):02d}", b, p if b.endswith("_R") else mx(p), r))
    top = STAFF_BOTTOM + Vector((0, 0, STAFF_LEN))
    for n, d, r in STAFF_COLLIDERS:
        out.append((f"AccCol_{n}_{int(round(r * 100)):02d}", "Staff", top - Vector((0, 0, d)), r))
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


CHIME_OUT = 0.090                            # el cordón se ata 2-3 cm afuera de las hojas: el tubo cuelga entero a la vista


def chime_attach(phi, s):
    """Donde se ata el cordón de un cascabel: afuera de las hojas de la capa (cuelga encima, se ve entero)."""
    return cloak_point(phi, s, CHIME_OUT)


CHIME_CLEAR = 0.075                          # lo que el tubo queda afuera de la cáscara en todo su largo (las hojas)


def chime_axis(phi, s, length):
    """Hacia dónde cuelga en reposo: a plomo en la espalda; en los hombros, donde la capa se abre hacia abajo, se aparta
    lo justo (de a 2°, hasta 45°) para que todo el tubo quede afuera de las hojas."""
    r0, z0 = cloak_rz(phi, s) + Vector((cloak_normal(phi, s).dot(Vector((math.sin(math.radians(phi)), -math.cos(math.radians(phi)), 0))),
                                        cloak_normal(phi, s).z)) * CHIME_OUT
    hem = cloak_rz(phi, 1.0).y

    def r_at(z):
        lo, hi = 0.0, 1.0
        for _ in range(24):
            m = (lo + hi) * 0.5
            if cloak_rz(phi, m).y > z:
                lo = m
            else:
                hi = m
        return cloak_rz(phi, (lo + hi) * 0.5).x
    th = 0.0
    for k in range(23):
        th = math.radians(2.0 * k)
        ok = True
        for i in range(1, 7):
            t = length * i / 6.0
            r, z = r0 + t * math.sin(th), z0 - t * math.cos(th)
            if z > hem and r - r_at(z) < CHIME_CLEAR:
                ok = False
                break
        if ok:
            break
    ar = math.radians(phi)
    return Vector((math.sin(ar) * math.sin(th), -math.cos(ar) * math.sin(th), -math.cos(th)))


def chime_parent(phi, s):
    """El paño (y tramo) de la capa que lleva el punto de atadura: el ángulo más cercano y el tramo según la caída."""
    a = min(CLOAK_ANGLES, key=lambda x: abs(((phi - x + 180.0) % 360.0) - 180.0))
    return cloak_name(a, cloak_seg_of(a, s))


def bones():
    B = [
        BoneDef("Root", (0, 0, 0), (0, 0, 0.3), None, True, (0, -1, 0)),
        BoneDef("Hips", (0, 0, 1.06), (0, 0, 1.24), "Root"),
        BoneDef("Spine", (0, 0, 1.24), (0, 0.0, 1.42), "Hips"),
        BoneDef("Spine1", (0, 0, 1.42), (0, 0.01, 1.62), "Spine"),
        BoneDef("Spine2", (0, 0.01, 1.62), (0, 0.03, 1.86), "Spine1"),
        BoneDef("Neck", (0, 0.03, 1.88), HEAD_J, "Spine2"),
        BoneDef("Head", HEAD_J, HEAD_J + Vector((0, 0, 0.25)), "Neck"),
        BoneDef("Jaw", JAW[0], JAW[1], "Head", True, (0, -1, 0)),
        BoneDef("Topknot_1", TOPKNOT[0], TOPKNOT[1], "Head", True, (0, -1, 0)),
        BoneDef("Topknot_2", TOPKNOT[1], TOPKNOT[2], "Topknot_1", True, (0, -1, 0)),
        # párpado: el pivote en el centro del ojo, Y hacia adelante (gira en X para cerrar)
        BoneDef("Lid_R", LID_R, LID_R + Vector((0, -0.03, 0)), "Head", True, (0, 0, 1)),
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
    c1, c2 = math.radians(FINGER_REST_CURL), math.radians(FINGER_REST_CURL * 2.0)
    d1, z1 = _h * math.cos(c1) - _DORS * math.sin(c1), _DORS * math.cos(c1) + _h * math.sin(c1)
    d2, z2 = _h * math.cos(c2) - _DORS * math.sin(c2), _DORS * math.cos(c2) + _h * math.sin(c2)
    for name, off, l1, l2 in FINGERS:
        base = KNUCKLE + _THUMB_SIDE * off - _DORS * 0.005
        mid = base + d1 * l1
        B.append(BoneDef(f"{name}_R_1", base, mid, "Hand_R", True, tuple(z1)))
        B.append(BoneDef(f"{name}_R_2", mid, mid + d2 * l2, f"{name}_R_1", True, tuple(z2)))
    Rm = basis_yz(_h, _DORS)
    tb = WRIST + Rm @ THUMB_BASE_LOCAL
    td = (Rm @ THUMB_DIR_LOCAL).normalized()
    tz = (_DORS - td * _DORS.dot(td)).normalized()
    B.append(BoneDef("Thumb_R_1", tb, tb + td * THUMB_LEN[0], "Hand_R", True, tuple(tz)))
    t2 = (td + _h * 0.35).normalized()
    B.append(BoneDef("Thumb_R_2", tb + td * THUMB_LEN[0], tb + td * THUMB_LEN[0] + t2 * THUMB_LEN[1], "Thumb_R_1", True, tuple(tz)))
    B = NA.mirrored(B)
    # cadenas con física posible (Acc_): la barba cuelga de la quijada, la ramita del cordón del moño, las colas de la faja
    # la barba cuelga de la cabeza (la quijada solo lleva las hileras del mentón): al reírse no se levanta entera
    B += chain_bones("TasselBeard", BEARD, "Head")
    B += chain_bones("LeafKnot", LEAF_KNOT, "Head")
    B += chain_bones("TieSashA", SASH_A, "Hips")
    B += chain_bones("TieSashB", SASH_B, "Hips")
    # falda del gi
    for a in SKIRT_ANGLES:
        h, t = skirt_frame(a)
        out = Vector((math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0))
        B.append(BoneDef(skirt_name(a), h, t, "Hips", True, tuple(out)))
    # capa: el primer tramo cuelga del pecho (Spine2), cada uno del anterior; Z del hueso hacia afuera
    for a in CLOAK_ANGLES:
        n = cloak_segs(a)
        ss = [0.10] + list(CLOAK_SPLITS[n]) + [1.0]
        parent = "Spine2"
        for i in range(n):
            nrm = cloak_normal(a, (ss[i] + ss[i + 1]) * 0.5)
            B.append(BoneDef(cloak_name(a, i + 1), cloak_point(a, ss[i]), cloak_point(a, ss[i + 1]), parent, True, tuple(nrm)))
            parent = cloak_name(a, i + 1)
    # cascabeles: un hueso por tubo, del nudo del cordón a la punta de abajo del tubo, hijo del tramo de capa que lo lleva
    for name, _, a, s, cord, ln, _r in chimes_full():
        top = chime_attach(a, s)
        ax = chime_axis(a, s, cord + ln)
        bot = top + ax * (cord + ln)
        nrm = cloak_normal(a, s)
        B += chain_bones(name[len("Acc_"):], [top, bot], chime_parent(a, s), roll=tuple(nrm))
    for bn, parent, c, r in collider_specs():
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

# formas de la mano: curva de la falange 1 y de la 2 por dedo (índice, medio, anular, meñique; grados hacia la palma,
# desde el reposo ya doblado FINGER_REST_CURL), apertura (grados, + = abanico) y pulgar (base, punta)
HAND_SHAPES = {
    "relaxed": dict(fing=(6, 10, 14, 18), tip=(8, 12, 16, 20), spread=3.0, thumb=(12, 10)),
    "open": dict(fing=(-8, -8, -6, -4), tip=(-6, -6, -4, -2), spread=10.0, thumb=(0, 0)),
    # la garra del ermitaño (manos huesudas que se abren: el concepto en el salto)
    "claw": dict(fing=(8, 6, 8, 12), tip=(52, 56, 58, 60), spread=14.0, thumb=(28, 36)),
    "fist": dict(fing=(78, 82, 84, 86), tip=(90, 92, 94, 96), spread=-2.0, thumb=(48, 58)),
    # puño en la caña (culmo de ~0.2 m: los dedos abrazan sin cerrarse) y en el bastón (6 cm)
    "grip_stalk": dict(fing=(36, 40, 44, 48), tip=(42, 46, 48, 52), spread=-1.0, thumb=(34, 26)),
    "grip_staff": dict(fing=(60, 64, 68, 72), tip=(72, 74, 76, 78), spread=-1.0, thumb=(42, 34)),
    # tocando la flauta: los dedos estirados apoyados en los agujeros
    "flute": dict(fing=(12, 16, 20, 24), tip=(4, 6, 8, 12), spread=-2.0, thumb=(30, 16)),
}


def hand_shape(S, name):
    """Canales de los dedos de la mano S ('r' o 'l') con la forma 'name' de HAND_SHAPES."""
    h = HAND_SHAPES[name]
    s = S.lower()
    return {f"fing_{s}": h["fing"], f"tip_{s}": h["tip"], f"spread_{s}": h["spread"], f"thumb_{s}": h["thumb"]}


LID_CLOSED_DEG = 60.0
CHEEK_PUFF = 0.024           # cuánto sale el cachete inflado (m, a lo largo del hueso: afuera y adelante)
# caras: (quijada abierta en grados, párpados 0 = el reposo (ya tapa el 40 % de arriba) .. 1 cerrados, cejas en grados
# (+ la punta de afuera sube), cachetes 0..1 inflados, comisuras (adentro m, arriba m) en el marco de la cabeza)
FACES = {
    "grin": dict(jaw=0.0, lids=0.0, brows=0.0, cheeks=0.0, corners=(0.0, 0.0)),
    "blow": dict(jaw=-1.0, lids=0.45, brows=6.0, cheeks=1.0, corners=(0.018, -0.006)),
    # la risa del concepto: la boca en medialuna abierta (las comisuras arriba), los ojos apretados en arcos, las cejas
    # arriba; la cabeza va hacia atrás en el clip del cuerpo
    "laugh": dict(jaw=14.0, lids=1.0, brows=12.0, cheeks=0.3, corners=(-0.004, 0.015)),
    "flute": dict(jaw=1.0, lids=1.0, brows=4.0, cheeks=0.35, corners=(0.010, -0.003)),
    "surprise": dict(jaw=12.0, lids=-0.25, brows=16.0, cheeks=0.0, corners=(0.008, -0.004)),
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
    # la capa de hojas pesa: cuelga de los hombros casi a plomo aunque el tronco se incline (agachado; colgado cabeza
    # abajo cae hacia el piso alrededor de la cabeza: tres tramos de hasta 95° cada uno)
    for a in CLOAK_ANGLES:
        out.append(([cloak_name(a, i) for i in range(1, cloak_segs(a) + 1)], 90.0, 0.72, 95.0))
    # los cascabeles cuelgan a plomo (colgado, del revés: el clip hornea su giro y SpringChain lo mueve alrededor)
    for name, *_ in chimes_full():
        out.append(([name + "_0"], 40.0, 0.9, 175.0))
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

    # cuánto del giro del brazo se lleva cada paño de la capa (el primer tramo): los del hombro cubren el brazo. El giro
    # que se lleva tiene tope: con los brazos arriba los paños se levantan lo justo para no atravesarlos, sin mostrarle
    # a la cámara alta el revés de la capa
    CLOAK_FOLLOW = {58.0: 0.15, 80.0: 0.34, 102.0: 0.30, 124.0: 0.14, 146.0: 0.04}
    CLOAK_FOLLOW_MAX = 38.0

    def follow_cloak(self, pose):
        """Los paños de la capa que cubren el brazo lo siguen cuando se levanta o se abre (si no, el brazo los atraviesa),
        y bajan con él: hacia dónde apunta el brazo respecto del pecho, en parte. Los cascabeles que cuelgan de ellos van
        juntos. El paso de animación hace lo mismo antes de los resortes (es la pose rígida a la que tiran). Solo cuenta la
        dirección del brazo, no su giro sobre el eje: con el giro entero, un codo que pasa al otro lado o un brazo que pasa
        por media vuelta daban vuelta el paño en un cuadro (hasta 116°)."""
        R = self.rig
        Ds2 = rot3(pose.get("Spine2")) @ rot3(R.rest["Spine2"]).transposed()
        for S, sg in (("L", 1.0), ("R", -1.0)):
            d0 = rot3(R.rest["UpperArm_" + S]).col[1]
            d1 = Ds2.transposed() @ rot3(pose.get("UpperArm_" + S)).col[1]
            q = d0.rotation_difference(d1)
            for a, f in self.CLOAK_FOLLOW.items():
                ang = a if sg > 0 else 360.0 - a
                qf = Quaternion().slerp(q, f)
                axv, rad = qf.to_axis_angle()
                if math.degrees(rad) > self.CLOAK_FOLLOW_MAX:
                    qf = Quaternion(axv, math.radians(self.CLOAK_FOLLOW_MAX))
                pose.delta(cloak_name(ang, 1), qf)

    def fingers(self, pose, S, shape):
        # una forma por nombre o sus números (los clips interpolan entre formas)
        h = HAND_SHAPES[shape] if isinstance(shape, str) else shape
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
        # los corrimientos de los cachetes y las comisuras van en el marco de la cabeza (colgado cabeza abajo el cachete
        # sale igual hacia afuera de la cara)
        Hd = rot3(pose.get("Head") @ R.rest_inv["Head"])
        # la X de la quijada mira a su derecha: abrir (el mentón baja) es girar en negativo
        ax = rot3(R.rest["Jaw"]).col[0]
        pose.delta("Jaw", Quaternion(ax, -math.radians(f["jaw"])))
        for S in "RL":
            sg = 1.0 if S == "R" else -1.0
            # párpado: el reposo deja el ojo entrecerrado (el casquete tapa arriba); cerrar es girar hacia abajo 60°
            ax = rot3(R.rest["Lid_" + S]).col[0]
            pose.delta("Lid_" + S, Quaternion(ax, -math.radians(LID_CLOSED_DEG * f["lids"])))
            # ceja: gira alrededor del eje de adelante y la punta de afuera sube (+) o baja
            pose.delta("Brow_" + S, Quaternion(Vector((0, 1, 0)), math.radians(f["brows"]) * sg))
            out = rot3(R.rest["Cheek_" + S]).col[1]
            pose.delta("Cheek_" + S, (0.0, 0.0, 0.0), loc=Hd @ (out * CHEEK_PUFF * f["cheeks"] + Vector((sg * -0.008 * f["cheeks"], 0, 0))))
            ci, cu = f["corners"]
            pose.delta("MouthCorner_" + S, (0.0, 0.0, 0.0), loc=Hd @ Vector((sg * ci, -0.4 * ci, cu)))

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
