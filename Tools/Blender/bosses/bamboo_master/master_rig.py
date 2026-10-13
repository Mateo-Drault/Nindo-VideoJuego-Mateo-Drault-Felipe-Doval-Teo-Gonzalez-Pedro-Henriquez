"""Esqueleto de Chikuō (el Maestro del Bambú) y traducción de controles de animación a huesos.

Un viejo maestro de kung fu de 2.7 m (con el rodete), flaco y de miembros largos: la grulla. La caricatura está en
las manos y los pies grandes, los brazos largos y la cabeza un poco grande para que la cara (cejas larguísimas y
bigotes) se lea desde la cámara del juego. Esqueleto de juego limpio, como el de Kokuyō: manos bajo antebrazos, pies
bajo tibias, sin huesos de IK en el FBX. Además de la cadena humana tiene:
  * cuatro dedos de dos falanges y el pulgar de dos: la palma abierta, el puño, el pico de grulla, la garra de tigre
    y los dedos de espada salen de los mismos huesos (HAND_SHAPES);
  * la punta del pie (Toe_*): parado en punta, la patada con la punta estirada;
  * cejas (Brow_*_1..2, rígidas, resortes horneados) y mangas anchas (Sleeve_*: el borde de la manga cuelga cuando
    el brazo se levanta);
  * bigotes y colas de la faja como cadenas 'Acc_Tie<Nombre>_0..2' + '_end' (la convención de los kits): el clip
    las hornea con resortes y, si el jefe agrega SpringChain en el juego, las mueve la física de verdad con las
    esferas 'AccCol_*' del pecho, la cadera y los muslos;
  * el saco: cuatro faldones de dos tramos (Robe_<ángulo>_1..2, el chaleco de la fase 2 cuelga de los primeros);
  * el saco TIRADO (RobeT_*): una copia aplanada que vuela en el cambio de fase (oculta fuera de ese clip);
  * el bastón de bambú (Staff, hijo de Root): se mueve libre en el mundo y las manos lo agarran por IK, así se
    puede girar y pasar de una mano a la otra.

Ejes: Blender Z arriba, frente -Y, derecha del personaje = -X.
"""
import math
from mathutils import Vector, Matrix, Quaternion
import nindo_anim as NA
from nindo_anim import BoneDef, V, euler_q, basis_yz, compose, rot3

# ------------------------------------------------------------------ medidas (metros, pose de reposo)
ANKLE_Z = 0.13
HIP_J = Vector((-0.15, 0.0, 1.22))          # cabeza del muslo derecho
KNEE = Vector((-0.16, -0.05, 0.68))         # rodilla apenas adelantada: el IK sabe para dónde doblar
ANKLE = Vector((-0.16, 0.0, ANKLE_Z))
BALL = Vector((-0.16, -0.19, 0.035))        # bola del pie: de acá dobla la punta
TOE_TIP = Vector((-0.16, -0.31, 0.03))
# punta y talón de la suela respecto del tobillo en y (la suela apoya en z 0): pivotes de un pie que se para en
# punta o se echa atrás sobre el talón. Pies grandes (41 cm): la caricatura del que está bien plantado
SOLE_TOE_Y, SOLE_HEEL_Y = -0.31, 0.11
SOLE_BALL_Y = BALL.y
SHOULDER = Vector((-0.30, 0.02, 1.95))
UPPER_LEN, FORE_LEN, HAND_LEN = 0.44, 0.40, 0.105
ARM_OUT_DEG = 40.0                           # pose A: el brazo abierto 40° (deforma limpio el hombro)
_u = Vector((-math.sin(math.radians(ARM_OUT_DEG)), 0.0, -math.cos(math.radians(ARM_OUT_DEG))))
ELBOW = SHOULDER + _u * UPPER_LEN
_l = (_u + Vector((0.0, -0.18, 0.0))).normalized()        # codo apenas doblado
WRIST = ELBOW + _l * FORE_LEN
_h = (_l + Vector((0.0, -0.05, 0.0))).normalized()        # la mano sigue al antebrazo
KNUCKLE = WRIST + _h * HAND_LEN
# marco de la mano derecha en reposo: dedos (_h), dorso (afuera-arriba) y hacia el pulgar (adelante). La palma mira al
# muslo; el índice queda adelante y el meñique atrás
_DORS = (Vector((-1.0, 0.0, 0.0)) - _h * Vector((-1.0, 0.0, 0.0)).dot(_h)).normalized()
_THUMB_SIDE = -(_h.cross(_DORS)).normalized()             # -X local del hueso de la mano = hacia el pulgar
# centro de la palma en el espacio del hueso de la mano (Y = dedos, Z = dorso): los controles de las manos dicen dónde
# está la PALMA (lo que pega en un golpe de palma), no la muñeca
PALM_LOCAL = Vector((0.0, 0.06, -0.022))
# donde pasa el bastón en un puño cerrado (base de los dedos, del lado de la palma)
GRIP_LOCAL = Vector((0.0, 0.088, -0.048))
# dedos: (nombre, corrimiento hacia el pulgar desde el centro de los nudillos, largo de la falange 1, de la 2)
FINGERS = [("Index", 0.036, 0.048, 0.042), ("Middle", 0.012, 0.054, 0.046),
           ("Ring", -0.012, 0.050, 0.043), ("Pinky", -0.035, 0.040, 0.034)]
# pulgar: nace del costado de la palma cerca de la muñeca (local del hueso de la mano) y apunta al índice
THUMB_BASE_LOCAL = Vector((-0.032, 0.022, -0.018))
THUMB_DIR_LOCAL = Vector((-0.55, 0.78, -0.30))
THUMB_LEN = (0.045, 0.040)

# faldones del saco: 4 paños de dos tramos (0° = frente, + = hacia su izquierda). Abiertos a los costados
# (las aberturas del saco largo) y con un tajo adelante y atrás: cada pierna empuja su paño en una patada
ROBE_ANGLES = [38.0, 142.0, 218.0, 322.0]
ROBE_TOP_Z = 1.30
ROBE_R = (0.26, 0.20)           # ancho de los muslos: el pantalón no asoma por los paños
ROBE_FLARE = 12.0
ROBE_LEN = (0.32, 0.32)
# faja: el nudo al frente a su izquierda, de donde cuelgan dos colas
SASH_Z = 1.31
SASH_KNOT = Vector((0.10, -0.225, 1.30))
# hombro del saco tirado (la manga cuelga de acá)
ROBE_T_SHOULDER = Vector((-0.2, 0.06, 1.93))
# bastón de bambú: 2.3 m, en reposo parado al costado derecho (oculto en el juego hasta la fase del bastón)
STAFF_LEN = 2.30
STAFF_R = 0.028
STAFF_REST = Vector((-0.62, 0.10, STAFF_LEN * 0.5 + 0.01))

# la mano en la espalda (fase 1: enseña con una sola mano): centro de la palma, dedos y dorso en el MUNDO de reposo; el
# Solver la lleva pegada a la cadera (Hips), así acompaña cada giro y cada caída de la cadera sin autorarla clave por
# clave. El dorso apoya sobre la faja (radio de atrás 0.22 m a esa altura) y los dedos apuntan al otro lado
BACK_HAND_L = (Vector((0.03, 0.285, 1.34)), Vector((-1.0, 0.1, -0.28)).normalized(), Vector((0.0, -1.0, 0.12)).normalized())
BACK_ELBOW_L = Vector((1.0, 0.55, -0.15)).normalized()
# la derecha, cuando las dos van atrás (la espera del maestro en la intro): agarra la muñeca izquierda por encima
BACK_HAND_R = (Vector((-0.09, 0.3, 1.37)), Vector((0.95, 0.1, -0.3)).normalized(), Vector((0.0, -1.0, 0.25)).normalized())
BACK_ELBOW_R = Vector((-1.0, 0.55, -0.15)).normalized()

# cadenas con física (convención de los kits: Acc_<Nombre>_<i> ... _end): bigotes y colas de la faja
WHISKER_R = [Vector((-0.048, -0.204, 2.258)), Vector((-0.07, -0.2, 2.12)), Vector((-0.076, -0.196, 1.96)),
             Vector((-0.07, -0.19, 1.80))]
# cejas: el mechón nace sobre el ojo (pegado al arco de la ceja, en la cabeza) y el hueso arranca en la punta de afuera
BROW_R = [Vector((-0.104, -0.15, 2.405)), Vector((-0.228, -0.07, 2.41)), Vector((-0.345, 0.06, 2.322))]
SASH_A = [SASH_KNOT + Vector((0.0, -0.025, -0.04)), SASH_KNOT + Vector((0.005, -0.05, -0.27)),
          SASH_KNOT + Vector((0.012, -0.08, -0.5)), SASH_KNOT + Vector((0.02, -0.11, -0.74))]
SASH_B = [SASH_KNOT + Vector((0.07, -0.015, -0.05)), SASH_KNOT + Vector((0.11, -0.035, -0.25)),
          SASH_KNOT + Vector((0.145, -0.058, -0.45)), SASH_KNOT + Vector((0.17, -0.08, -0.63))]
# esferas de colisión de las cadenas (hueso, centro en el mundo de reposo, radio): pecho, vientre y muslos
CHAIN_COLLIDERS = [("Chest", "Chest", Vector((0.0, -0.02, 1.80)), 0.17), ("Belly", "Hips", Vector((0.0, -0.03, 1.22)), 0.19),
                   ("ThighR", "Thigh_R", Vector((-0.155, -0.05, 0.98)), 0.15),
                   ("ThighL", "Thigh_L", Vector((0.155, -0.05, 0.98)), 0.15)]


def robe_name(a, seg):
    return f"Robe_{int(round(a)) % 360:03d}_{seg}"


def robe_frame(a):
    """(cabeza, dirección hacia abajo con el vuelo, normal hacia afuera, tangente) de un faldón."""
    r = math.radians(a)
    out = Vector((math.sin(r), -math.cos(r), 0.0))
    head = Vector((math.sin(r) * ROBE_R[0], -math.cos(r) * ROBE_R[1], ROBE_TOP_Z))
    down = (Vector((0, 0, -1)) * math.cos(math.radians(ROBE_FLARE)) + out * math.sin(math.radians(ROBE_FLARE))).normalized()
    tang = Vector((0, 0, 1)).cross(out).normalized()
    return head, down, out, tang


def chain_bones(name, pts, parent, roll=(0, -1, 0)):
    """Cadena 'Acc_<name>_0..n-1' por los puntos y su punta 'Acc_<name>_end' (sin pesos: SpringChain la necesita
    para saber dónde termina el último tramo)."""
    out = []
    p = parent
    for i in range(len(pts) - 1):
        bn = f"Acc_{name}_{i}"
        out.append(BoneDef(bn, pts[i], pts[i + 1], p, True, roll))
        p = bn
    d = (pts[-1] - pts[-2]).normalized()
    out.append(BoneDef(f"Acc_{name}_end", pts[-1], pts[-1] + d * 0.05, p, True, roll))
    return out


def chain_names(name, n):
    return [f"Acc_{name}_{i}" for i in range(n)]


def mx(v):
    return Vector((-v.x, v.y, v.z))


def hand_frame(S):
    """(muñeca, dedos, dorso, hacia el pulgar) de la mano S en reposo."""
    m = (lambda v: v) if S == "R" else mx
    return m(WRIST), m(_h), m(_DORS), m(_THUMB_SIDE)


def bones():
    B = [
        BoneDef("Root", (0, 0, 0), (0, 0, 0.3), None, True, (0, -1, 0)),
        BoneDef("Hips", (0, 0, 1.18), (0, 0, 1.38), "Root"),
        BoneDef("Spine", (0, 0, 1.40), (0, 0, 1.70), "Hips"),
        BoneDef("Chest", (0, 0, 1.72), (0, 0, 2.02), "Spine"),
        BoneDef("Neck", (0, 0.035, 2.03), (0, 0.0, 2.16), "Chest"),
        BoneDef("Head", (0, 0, 2.16), (0, 0, 2.56), "Neck"),
        # cejas: nacen sobre los ojos y barren hacia afuera, atrás y arriba como plumas de grulla (lo que se ve
        # desde arriba)
        BoneDef("Brow_R_1", BROW_R[0], BROW_R[1], "Head", True, (0, -0.3, 1)),
        BoneDef("Brow_R_2", BROW_R[1], BROW_R[2], "Brow_R_1", True, (0, -0.1, 1)),
        BoneDef("Clav_R", (-0.05, 0.02, 1.95), (-0.28, 0.02, 1.95), "Chest", True, (0, 0, 1)),
        BoneDef("UpperArm_R", SHOULDER, ELBOW, "Clav_R", True, (0, -1, 0)),
        BoneDef("Forearm_R", ELBOW, WRIST, "UpperArm_R", True, (0, -1, 0)),
        # mano: el eje Z es el dorso (afuera en reposo: la palma mira al muslo)
        BoneDef("Hand_R", WRIST, KNUCKLE, "Forearm_R", True, tuple(_DORS)),
        # manga ancha: el borde de abajo cuelga de la mitad del antebrazo
        BoneDef("Sleeve_R", ELBOW + _l * 0.16, ELBOW + _l * 0.36, "Forearm_R", True, (0, -1, 0)),
        BoneDef("Thigh_R", HIP_J, KNEE, "Hips", True, (0, -1, 0)),
        BoneDef("Shin_R", KNEE, ANKLE, "Thigh_R", True, (0, -1, 0)),
        BoneDef("Foot_R", ANKLE, BALL, "Shin_R", True, (0, 0, 1)),
        BoneDef("Toe_R", BALL, TOE_TIP, "Foot_R", True, (0, 0, 1)),
    ]
    # dedos: dos falanges cada uno, nacen en la fila de nudillos y miran como la mano (Z = dorso)
    for name, off, l1, l2 in FINGERS:
        base = KNUCKLE + _THUMB_SIDE * off - _DORS * 0.004
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
    # cadenas con física (a mano a los dos lados: los nombres de los kits no llevan _R/_L)
    B += chain_bones("TieWhiskerR", WHISKER_R, "Head")
    B += chain_bones("TieWhiskerL", [mx(p) for p in WHISKER_R], "Head")
    B += chain_bones("TieSashA", SASH_A, "Hips")
    B += chain_bones("TieSashB", SASH_B, "Hips")
    for name, parent, c, r in CHAIN_COLLIDERS:
        bn = f"AccCol_{name}_{int(round(r * 100))}"
        B.append(BoneDef(bn, c, c + Vector((0, 0, 0.05)), parent, True, (0, -1, 0)))
        B.append(BoneDef(bn + "_r", c + Vector((r, 0, 0)), c + Vector((r, 0, 0.05)), bn, True, (0, -1, 0)))
    for a in ROBE_ANGLES:
        h, d, o, t = robe_frame(a)
        m = h + d * ROBE_LEN[0]
        B.append(BoneDef(robe_name(a, 1), h, m, "Hips", True, o))
        B.append(BoneDef(robe_name(a, 2), m, m + d * ROBE_LEN[1], robe_name(a, 1), True, o))
    B += [
        # el saco tirado (cambio de fase): en reposo queda adentro de la espalda (oculto en el juego fuera de ese
        # clip); cuello -> ruedo y las dos mangas abiertas: un saco aplanado que vuela y cae al piso
        BoneDef("RobeT_Root", (0, 0.06, 1.98), (0, 0.06, 1.62), "Root", True, (0, -1, 0)),
        # el ruedo en tres tramos (de la cintura a la rodilla): dobla como tela en el vuelo y queda arrugado en el piso
        BoneDef("RobeT_Hem", (0, 0.06, 1.62), (0, 0.06, 1.3), "RobeT_Root", True, (0, -1, 0)),
        BoneDef("RobeT_Hem_1", (0, 0.06, 1.3), (0, 0.06, 1.08), "RobeT_Hem", True, (0, -1, 0)),
        BoneDef("RobeT_Hem_2", (0, 0.06, 1.08), (0, 0.06, 0.86), "RobeT_Hem_1", True, (0, -1, 0)),
        # las mangas en reposo siguen a las del saco puesto (pose A): quedan adentro de las mangas anchas; dos tramos
        BoneDef("RobeT_ArmR", ROBE_T_SHOULDER, ROBE_T_SHOULDER + _u * 0.24, "RobeT_Root", True, (0, -1, 0)),
        BoneDef("RobeT_ArmR_2", ROBE_T_SHOULDER + _u * 0.24, ROBE_T_SHOULDER + _u * 0.42, "RobeT_ArmR", True, (0, -1, 0)),
        BoneDef("RobeT_ArmL", mx(ROBE_T_SHOULDER), mx(ROBE_T_SHOULDER + _u * 0.24), "RobeT_Root", True, (0, -1, 0)),
        BoneDef("RobeT_ArmL_2", mx(ROBE_T_SHOULDER + _u * 0.24), mx(ROBE_T_SHOULDER + _u * 0.42), "RobeT_ArmL", True, (0, -1, 0)),
        # bastón: Y = a lo largo (de la punta de abajo a la de arriba), libre en el mundo
        BoneDef("Staff", STAFF_REST - Vector((0, 0, STAFF_LEN * 0.5)), STAFF_REST + Vector((0, 0, STAFF_LEN * 0.5)), "Root", True,
                (0, -1, 0)),
        # marcador de frente (exportado: el validador de Unity comprueba que mire a +Z)
        BoneDef("Facing", (0, -0.35, 2.0), (0, -0.65, 2.0), "Root", True, (0, 0, 1)),
    ]
    return B


# huesos que resuelve el IK o la cadena principal: los 'extra' no pueden tocar a sus padres
IK_BONES = {"UpperArm_R", "Forearm_R", "Hand_R", "UpperArm_L", "Forearm_L", "Hand_L",
            "Thigh_R", "Shin_R", "Foot_R", "Thigh_L", "Shin_L", "Foot_L", "Staff"}
ROBE_T = ("RobeT_Root", "RobeT_Hem", "RobeT_Hem_1", "RobeT_Hem_2", "RobeT_ArmR", "RobeT_ArmR_2", "RobeT_ArmL", "RobeT_ArmL_2")
FINGER_BONES = [f"{n}_{S}_{i}" for S in "RL" for n, *_ in FINGERS for i in (1, 2)] + [f"Thumb_{S}_{i}" for S in "RL" for i in (1, 2)]

# formas de la mano: curva de la falange 1 y de la 2 por dedo (índice, medio, anular, meñique; grados hacia la palma),
# apertura de los dedos (grados, + = se abren en abanico) y pulgar (base, punta). La muñeca la da hand_*_dir/up.
HAND_SHAPES = {
    "relaxed": dict(fing=(14, 17, 20, 24), tip=(16, 19, 22, 26), spread=2.0, thumb=(12, 10)),
    # golpe de palma: dedos juntos y derechos, el pulgar pegado al costado
    "palm": dict(fing=(0, 0, 0, 0), tip=(2, 2, 2, 2), spread=-2.0, thumb=(6, 4)),
    "fist": dict(fing=(88, 92, 94, 96), tip=(100, 102, 104, 106), spread=-2.0, thumb=(48, 58)),
    # pico de grulla: las yemas se juntan con la del pulgar (la muñeca doblada hacia abajo la pone la clave)
    "beak": dict(fing=(34, 30, 34, 42), tip=(30, 30, 32, 36), spread=-7.0, thumb=(52, 22)),
    # garra de tigre: nudillos casi derechos, falanges cerradas y los dedos abiertos
    "claw": dict(fing=(22, 20, 22, 26), tip=(78, 82, 84, 86), spread=16.0, thumb=(34, 46)),
    # dedos de espada: índice y medio estirados, anular y meñique cerrados bajo el pulgar
    "sword": dict(fing=(0, 0, 90, 94), tip=(2, 2, 104, 106), spread=-3.0, thumb=(55, 62)),
    # agarre del bastón: puño abierto alrededor de un caño de 5.6 cm
    "grip": dict(fing=(62, 66, 70, 74), tip=(78, 80, 82, 84), spread=-1.0, thumb=(40, 30)),
}


def hand_shape(S, name):
    """Canales de los dedos de la mano S ('r' o 'l') con la forma 'name' de HAND_SHAPES."""
    h = HAND_SHAPES[name]
    s = S.lower()
    return {f"fing_{s}": h["fing"], f"tip_{s}": h["tip"], f"spread_{s}": h["spread"], f"thumb_{s}": h["thumb"]}


def palm_rest(S):
    w, hd, dors, thumb = hand_frame(S)
    Rm = basis_yz(hd, dors)
    return w + Rm @ PALM_LOCAL, hd, dors


_PR, _PRD, _PRU = palm_rest("R")
_PL, _PLD, _PLU = palm_rest("L")

# ------------------------------------------------------------------ controles por defecto
NEUTRAL = {
    "hips": (0.0, 0.0, 0.0), "hips_rot": (0.0, 0.0, 0.0),
    "spine": (0.0, 0.0, 0.0), "chest": (0.0, 0.0, 0.0), "neck": (0.0, 0.0, 0.0), "head": (0.0, 0.0, 0.0),
    "clav_r": (0.0, 0.0, 0.0), "clav_l": (0.0, 0.0, 0.0),
    # manos: centro de la PALMA, hacia dónde apuntan los dedos y hacia dónde mira el dorso
    "hand_r": tuple(_PR), "hand_r_dir": tuple(_PRD), "hand_r_up": tuple(_PRU), "elbow_r": (-0.4, 0.8, -0.2),
    "hand_l": tuple(_PL), "hand_l_dir": tuple(_PLD), "hand_l_up": tuple(_PLU), "elbow_l": (0.4, 0.8, -0.2),
    **hand_shape("r", "relaxed"), **hand_shape("l", "relaxed"),
    "foot_r": tuple(ANKLE), "foot_r_rot": (0.0, 0.0, 0.0), "knee_r": (-0.1, -1.0, 0.0), "toe_r": 0.0,
    "foot_l": tuple(mx(ANKLE)), "foot_l_rot": (0.0, 0.0, 0.0), "knee_l": (0.1, -1.0, 0.0), "toe_l": 0.0,
    "travel": 0.0, "lift": 0.0, "breath": 0.0, "extra": {},
    # el saco tirado: 0 = guardado adentro del cuerpo; 1 = libre en el mundo (robe_pos/robe_rot/robe_fold)
    "robe_free": 0.0,
    # bastón: 0 = en reposo (oculto); 1 = libre (staff_pos = centro, staff_dir = de la punta de abajo a la de arriba,
    # staff_up = hacia dónde mira la cara 'Z' del hueso). grip_r/grip_l = metros desde el centro donde agarra cada mano
    # (None = mano libre): la mano va al bastón por IK, la palma lo envuelve
    "staff_on": 0.0, "staff_pos": tuple(STAFF_REST), "staff_dir": (0.0, 0.0, 1.0), "staff_up": (0.0, -1.0, 0.0),
    "grip_r": None, "grip_l": None, "grip_r_up": (0.0, 0.0, 1.0), "grip_l_up": (0.0, 0.0, 1.0),
    # hacia qué punta mira cada pulgar (+1 = la de arriba): por defecto los pulgares se miran (agarre de bō)
    "grip_r_thumb": 1.0, "grip_l_thumb": -1.0,
    # 0..1: cuánto va cada mano a su lugar en la espalda (BACK_HAND_*), pegada a la cadera; en el medio se mezcla con el
    # control explícito de la mano (para sacarla de la espalda hace falta una clave intermedia al costado de la cadera:
    # la mezcla directa cruzaría el cuerpo)
    "back_r": 0.0, "back_l": 0.0,
    # bastón relativo al personaje (0) o clavado en el mundo del clip (1); staff_follow 0..1 lo pega al pecho
    "staff_world": 0.0, "staff_follow": 0.0, "staff_cpos": None, "staff_cdir": None, "staff_cup": None,
}


class Solver:
    """Traduce un diccionario de controles a la pose de todos los huesos (ver nindo_anim.Pose)."""

    def __init__(self, rig):
        self.rig = rig
        self.misses = {}
        R = rig
        # ejes de reposo de dedos y pulgar en espacio de la armadura: curva = X propio, apertura = Z propio (dorso)
        self.axes = {n: (rot3(R.rest[n]).col[0].normalized(), rot3(R.rest[n]).col[2].normalized()) for n in FINGER_BONES}
        # lugar de las manos en la espalda en el espacio de la cadera de reposo (posición, dedos, dorso) y su codo
        hi = R.rest_inv["Hips"]
        h3 = rot3(R.rest["Hips"]).transposed()
        self.back = {S: (hi @ p, h3 @ d, h3 @ u) for S, (p, d, u) in (("R", BACK_HAND_R), ("L", BACK_HAND_L))}
        self.back_elbow = {"R": h3 @ BACK_ELBOW_R, "L": h3 @ BACK_ELBOW_L}

    def solve(self, pose, c):
        c = {**NEUTRAL, **{k: v for k, v in c.items() if v is not None}}
        R = self.rig
        # el cuerpo (cadera, manos) se autora relativo al transform del juego; lo que queda clavado en el MUNDO (pies
        # apoyados, el saco tirado en el piso, el bastón apoyado) se corre con el avance del golpe
        sh = Vector((0.0, c["travel"], c["lift"]))
        up = Vector((0.0, 0.0, c["lift"]))
        # ---- cadera y tronco
        hip_rest = R.rest["Hips"]
        Hm = compose(hip_rest.translation + V(c["hips"]) + up, euler_q(c["hips_rot"]).to_matrix() @ rot3(hip_rest))
        # la cadera baja lo justo para que los dos pies lleguen a su apoyo (pies clavados aunque la clave pida una
        # cadera un poco alta)
        drop = 0.0
        for s_ in ("r", "l"):
            S_ = s_.upper()
            J = (Hm @ R.rel["Thigh_" + S_]).translation
            A = V(c["foot_" + s_]) + sh
            reach = (R.length["Thigh_" + S_] + R.length["Shin_" + S_]) * 0.985
            dxy = Vector((J.x - A.x, J.y - A.y)).length
            if dxy < reach:
                need = (J.z - A.z) - math.sqrt(reach * reach - dxy * dxy)
                drop = max(drop, need)
        if drop > 0.0:
            Hm.translation.z -= drop
        self.hip_drop = drop
        pose.place("Hips", Hm)
        br = c["breath"]
        pose.delta("Spine", c["spine"])
        pose.delta("Chest", V(c["chest"]) + Vector((-2.5 * br, 0.0, 0.0)))
        pose.delta("Neck", V(c["neck"]) + Vector((1.2 * br, 0.0, 0.0)))
        pose.delta("Head", c["head"])
        pose.delta("Clav_R", V(c["clav_r"]) + Vector((0.0, -1.8 * br, 0.0)))
        pose.delta("Clav_L", V(c["clav_l"]) + Vector((0.0, 1.8 * br, 0.0)))
        # ---- bastón (antes que las manos: las manos lo agarran)
        staff_on = (c.get("staff_on") or 0.0) >= 0.5
        Ms = None
        if staff_on:
            # el bastón en la mano va relativo al personaje (como las manos); clavado en el piso o tirado va en el
            # MUNDO del clip (staff_world = 1: se corre con el avance, como un pie apoyado)
            sw = sh if (c.get("staff_world") or 0.0) >= 0.5 else up
            Ms = compose(V(c["staff_pos"]) + sw, basis_yz(c["staff_dir"], c["staff_up"]))
            sf = max(0.0, min(1.0, c.get("staff_follow") or 0.0))
            if sf > 1e-4 and c.get("staff_cpos") is not None:
                # agarrado contra el pecho: el bastón acompaña al tronco (las reacciones de la fase 3 son las de las
                # otras fases con el bastón pegado al pecho; si quedara quieto en el aire las manos se despegarían).
                # staff_cpos/cdir/cup: centro, eje y cara del bastón en el espacio del hueso Chest
                p_, d_, u_ = c["staff_cpos"], c["staff_cdir"], c["staff_cup"]
                Wc = pose.get("Chest")
                Rc = rot3(Wc)
                pos = Ms.translation.lerp(Wc @ V(p_), sf)
                dd = NA.slerp_dir(rot3(Ms).col[1], Rc @ V(d_), sf)
                uu = NA.slerp_dir(rot3(Ms).col[2], Rc @ V(u_), sf)
                Ms = compose(pos, basis_yz(dd, uu))
            # la cabeza del hueso es la punta de abajo: el control dice el centro
            Ms.translation = Ms.translation - rot3(Ms).col[1] * (STAFF_LEN * 0.5)
            pose.place("Staff", Ms)
        # ---- brazos: la palma va donde dice el control (o al bastón)
        misses = {}
        for s in ("r", "l"):
            S = s.upper()
            g = c.get("grip_" + s)
            elbow = c["elbow_" + s]
            palm, hd, hu = V(c["hand_" + s]) + up, V(c["hand_" + s + "_dir"]), V(c["hand_" + s + "_up"])
            hf = max(0.0, min(1.0, c.get("hand_" + s + "_follow") or 0.0))
            if hf > 1e-4 and c.get("hand_" + s + "_cpos") is not None:
                # la mano de guardia pegada al pecho (caminar, reacciones): hand_*_cpos/cdir/cup/celbow en el espacio de
                # Chest; así acompaña el giro y el rebote del tronco en vez de quedar flotando donde estaba
                Wc = pose.get("Chest")
                Rc = rot3(Wc)
                palm = palm.lerp(Wc @ V(c["hand_" + s + "_cpos"]), hf)
                hd = NA.slerp_dir(hd, Rc @ V(c["hand_" + s + "_cdir"]), hf)
                hu = NA.slerp_dir(hu, Rc @ V(c["hand_" + s + "_cup"]), hf)
                elbow = NA.slerp_dir(elbow, Rc @ V(c["hand_" + s + "_celbow"]), hf)
            wb = max(0.0, min(1.0, c.get("back_" + s) or 0.0))
            if wb > 1e-4:
                # la mano en la espalda viaja con la cadera: su lugar de reposo llevado por el giro de Hips
                bp, bd, bu = self.back[S]
                palm = palm.lerp(Hm @ bp, wb)
                hd = NA.slerp_dir(hd, rot3(Hm) @ bd, wb)
                hu = NA.slerp_dir(hu, rot3(Hm) @ bu, wb)
                elbow = NA.slerp_dir(elbow, rot3(Hm) @ self.back_elbow[S], wb)
            Rh = basis_yz(hd, hu)
            wrist = palm - Rh @ PALM_LOCAL
            if staff_on and g is not None:
                Rg, wg = self.grip_frame(Ms, S, g, c["grip_" + s + "_up"], c["grip_" + s + "_thumb"])
                # grip_*_w < 1: la mano va o viene del bastón (lo atrapa, lo suelta): mezcla de muñeca y giro
                gw = c.get("grip_" + s + "_w")
                gw = 1.0 if gw is None else max(0.0, min(1.0, gw))
                if gw >= 0.9999:
                    Rh, wrist = Rg, wg
                else:
                    q = Rh.to_quaternion().slerp(Rg.to_quaternion(), gw)
                    Rh, wrist = q.to_matrix(), wrist.lerp(wg, gw)
            self.reach_with_clavicle(pose, S, wrist)
            misses["hand_" + s] = pose.two_bone("UpperArm_" + S, "Forearm_" + S, wrist, elbow)
            pose.place("Hand_" + S, compose(pose.tail("Forearm_" + S), Rh))
            pose.twist_follow("Forearm_" + S, "Hand_" + S, 0.5)
            self.fingers(pose, S, c)
        # ---- piernas
        miss_legs = 0.0
        for s in ("r", "l"):
            S = s.upper()
            ank = V(c["foot_" + s]) + sh
            pr = c["foot_" + s + "_rot"]
            Rf = (Matrix.Rotation(math.radians(pr[2]), 3, 'Z') @ Matrix.Rotation(math.radians(pr[0]), 3, 'X')
                  @ Matrix.Rotation(math.radians(pr[1]), 3, 'Y')) @ rot3(R.rest["Foot_" + S])
            miss_legs = max(miss_legs, pose.two_bone("Thigh_" + S, "Shin_" + S, ank, c["knee_" + s]))
            pose.place("Foot_" + S, compose(pose.tail("Shin_" + S), Rf))
            # punta del pie: + = los dedos se doblan hacia arriba (parado en punta); - = punta estirada (patada)
            t = c.get("toe_" + s) or 0.0
            if abs(t) > 1e-4:
                ax = rot3(R.rest["Toe_" + S]).col[0]
                pose.delta("Toe_" + S, Quaternion(ax, math.radians(t)))
        # ---- el saco tirado: libre en el mundo (vuela y cae); los pliegues doblan el ruedo y las mangas
        if (c.get("robe_free", 0.0) or 0.0) >= 0.5:
            Mr = compose(V(c["robe_pos"]) + sh, euler_q(c["robe_rot"]).to_matrix() @ rot3(R.rest["RobeT_Root"]))
            pose.place("RobeT_Root", Mr)
            # robe_fold: (ruedo, mangas abiertas, mangas giradas[, tramo 2 del ruedo, tramo 3, codo de las mangas, mangas
            # hacia atrás]): con los tramos el ruedo ondea en el vuelo y queda arrugado en el piso
            fold = tuple(c.get("robe_fold", (0.0, 0.0, 0.0))) + (0.0,) * 4
            pose.delta("RobeT_Hem", (fold[0], 0.0, 0.0))
            pose.delta("RobeT_Hem_1", (fold[3], 0.0, 0.0))
            pose.delta("RobeT_Hem_2", (fold[4], 0.0, 0.0))
            pose.delta("RobeT_ArmR", (fold[6], fold[1], -fold[2]))
            pose.delta("RobeT_ArmL", (fold[6], -fold[1], fold[2]))
            pose.delta("RobeT_ArmR_2", (fold[5], 0.0, 0.0))
            pose.delta("RobeT_ArmL_2", (fold[5], 0.0, 0.0))
        # ---- giros extra de huesos secundarios (cejas, faldones, mangas...)
        for bn, r in sorted(c["extra"].items(), key=lambda kv: R.names.index(kv[0])):
            assert bn not in IK_BONES and bn not in FINGER_BONES, bn
            pose.delta(bn, r)
        misses["legs"] = miss_legs
        self.misses = misses
        return misses

    def fingers(self, pose, S, c):
        """Curva de las dos falanges de cada dedo (sobre su X de reposo), apertura en abanico de la primera (sobre su Z)
        y el pulgar. Los giros son en ejes de la armadura en reposo: Pose.delta los compone con el giro de la mano."""
        s = S.lower()
        sg = 1.0 if S == "R" else -1.0
        fing, tip, spread, thumb = c["fing_" + s], c["tip_" + s], c["spread_" + s], c["thumb_" + s]
        for i, (name, off, *_r) in enumerate(FINGERS):
            b1, b2 = f"{name}_{S}_1", f"{name}_{S}_2"
            x1, z1 = self.axes[b1]
            # el abanico abre el índice hacia el pulgar y el meñique hacia el otro lado (el medio casi no se mueve)
            fan = (0.9, 0.25, -0.45, -1.0)[i] * spread
            q = Quaternion(z1, sg * math.radians(fan)) @ Quaternion(x1, -math.radians(fing[i]))
            pose.delta(b1, q)
            x2, _ = self.axes[b2]
            pose.delta(b2, Quaternion(x2, -math.radians(tip[i])))
        for k, bn in enumerate((f"Thumb_{S}_1", f"Thumb_{S}_2")):
            x, _ = self.axes[bn]
            pose.delta(bn, Quaternion(x, -math.radians(thumb[k])))

    def grip_frame(self, Ms, S, g, up_hint, thumb):
        """Marco de la mano S agarrando el bastón a 'g' metros de su centro: el bastón pasa por el puño de lado (X de
        la mano a lo largo del bastón), el pulgar apunta a la punta de arriba (thumb +1) o a la de abajo (-1) y los
        nudillos miran lo más parecido a 'up_hint'. Devuelve (rotación, muñeca)."""
        ax = rot3(Ms).col[1]
        center = Ms.translation + ax * (STAFF_LEN * 0.5 + g)
        # el pulgar está del lado -X en la mano derecha y +X en la izquierda (huesos espejados)
        tdir = ax * (1.0 if thumb >= 0 else -1.0)
        x_hand = -tdir if S == "R" else tdir
        # dedos (Y de la mano) perpendiculares al bastón, lo más parecido al pedido
        y = V(up_hint) - ax * V(up_hint).dot(ax)
        if y.length < 1e-4:
            y = ax.orthogonal()
        y.normalize()
        z = x_hand.cross(y).normalized()          # X = Y x Z  ->  Z = X x Y
        Rh = Matrix((x_hand, y, z)).transposed()
        # el caño pasa por la base de los dedos, del lado de la palma
        wrist = center - Rh @ GRIP_LOCAL
        return Rh, wrist

    def reach_with_clavicle(self, pose, S, target, max_deg=26.0):
        """Si la muñeca no llega, el hombro se adelanta (la clavícula gira hacia el objetivo, como la escápula al
        estirarse): un golpe de palma estirado gana ~15 cm sin despegar la mano de donde tiene que pegar."""
        R = self.rig
        cl, ua, fa = "Clav_" + S, "UpperArm_" + S, "Forearm_" + S
        reach = (R.length[ua] + R.length[fa]) * 0.985
        for _ in range(2):
            shp = (pose.get(cl) @ R.rel[ua]).translation
            ex = (V(target) - shp).length - reach
            if ex <= 0.0:
                return
            ch = pose.head(cl)
            a = (shp - ch)
            b = (V(target) - ch)
            ax = a.cross(b)
            if ax.length < 1e-6:
                return
            ang = min(ex / max(a.length, 1e-3), math.radians(max_deg))
            M = pose.get(cl)
            Rq = Quaternion(ax.normalized(), ang).to_matrix()
            pose.place(cl, compose(ch, Rq @ rot3(M)))


def springs(rig):
    """Cadenas secundarias horneadas en los clips (las mismas que SpringChain movería en el juego, más las rígidas)."""
    def local(bone, p):
        return rig.rest_inv[bone] @ Vector(p)
    chest = [("Chest", local("Chest", (0.0, -0.02, 1.80)), 0.17)]
    belly = [("Hips", local("Hips", (0.0, -0.03, 1.22)), 0.19), ("Hips", local("Hips", (0.0, -0.06, 1.38)), 0.18)]
    thighs = [("Thigh_R", local("Thigh_R", (-0.155, -0.05, 0.98)), 0.15), ("Thigh_L", local("Thigh_L", (0.155, -0.05, 0.98)), 0.15)]
    sp = []
    for S in "RL":
        # cejas: pelo duro, apenas rebotan (si no, en un golpe seco se doblan sobre la cara)
        sp.append(NA.Spring([f"Brow_{S}_1", f"Brow_{S}_2"], k=420.0, damp=0.3, grav=0.5, max_deg=12.0))
        # bigotes: caen sobre el pecho y se atrasan al girar la cabeza
        sp.append(NA.Spring(chain_names("TieWhisker" + S, 3), k=110.0, damp=0.12, grav=6.0, max_deg=55.0, hang=0.5,
                            colliders=chest))
        # mangas anchas: el borde pesa y cuelga cuando el brazo se levanta
        sp.append(NA.Spring([f"Sleeve_{S}"], k=160.0, damp=0.2, grav=7.0, max_deg=28.0, hang=0.35))
    for t in ("A", "B"):
        # tope de desvío amplio: en una postura baja la cola rígida queda bajo el piso y con 70° el tope la volvía a meter
        # después de que el piso la empujara arriba (la barrida y el caballo bajo la clavaban 20 cm)
        sp.append(NA.Spring(chain_names("TieSash" + t, 3), k=95.0, damp=0.12, grav=6.0, max_deg=120.0, floor=0.06, hang=0.65,
                            colliders=belly + thighs))
    # faldones del saco (y los del chaleco, que cuelgan de los mismos huesos): tela gruesa; el muslo los empuja en una
    # patada (si no, la pierna los atraviesa) y la rodilla no deja que el tramo de abajo se le meta adentro
    hips_rest = rot3(rig.rest["Hips"])
    thigh_rest = {S: rot3(rig.rest["Thigh_" + S]).col[1] for S in "RL"}
    hipj = {S: rig.head_rest("Thigh_" + S) for S in "RL"}
    plate = {robe_name(a, 1): robe_frame(a) for a in ROBE_ANGLES}

    def thigh_push(W, b):
        if b not in plate:
            return None
        h, d, o, t = plate[b]
        Rh = rot3(W["Hips"]) @ hips_rest.transposed()
        oo, tt = Rh @ o, Rh @ t
        best = 0.0
        for S in "RL":
            cur = rot3(W["Thigh_" + S]).col[1]
            fol = Rh @ thigh_rest[S]
            ang = math.acos(max(-1.0, min(1.0, cur.dot(fol))))
            sw = cur - fol
            sw.z = 0.0
            if sw.length < 1e-5 or ang < 1e-3:
                continue
            c = max(0.0, sw.normalized().dot(oo))
            dist = Vector((h.x - hipj[S].x, h.y - hipj[S].y)).length
            w = max(0.0, min(1.0, 1.45 - dist / 0.30))
            best = max(best, ang * c * w)
        if best < 1e-3:
            return None
        return Quaternion(tt, -min(best * 1.15, math.radians(88.0)))
    knees = [("Shin_R", local("Shin_R", KNEE), 0.15), ("Shin_L", local("Shin_L", mx(KNEE)), 0.15)]
    for a in ROBE_ANGLES:
        sp.append(NA.Spring([robe_name(a, 1), robe_name(a, 2)], k=200.0, damp=0.2, grav=3.0, max_deg=35.0, push=thigh_push,
                            floor=0.05, colliders=knees + thighs))
    return sp
