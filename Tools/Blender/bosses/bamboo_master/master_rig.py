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

# ------------------------------------------------------------------ muñecas
# Ítem 3 del traspaso ("muñecas dobladas"), medido en el FBX de la fase C2: el agarre del bastón doblaba la mano 115-169°
# contra el antebrazo y la palma parada de la fase 2 ~95°. Los límites son los de team_limbs (los del resto del equipo):
# flexión 75 (hacia la palma), extensión 65, desvío radial 25 (hacia el pulgar), cubital 38, respecto de la muñeca del
# reposo; 'exceso' 1 = en el borde de esa elipse. Cómo se resuelve sin tocar lo que el clip pidió donde importa (la palma
# donde pega, el bastón donde está), en Solver.place_arm:
#   * el codo gira alrededor del eje hombro-muñeca (lo que hace un brazo de verdad) hasta que la muñeca queda cómoda,
#     cerca del polo que pidió la clave y del codo del cuadro anterior, sin subir de más ni meterse en el tronco;
#   * la mano que agarra el bastón rueda alrededor del caño hasta que el antebrazo pasa por el puño (el bastón no se
#     mueve: el agarre de la clave es solo dónde empieza a buscar);
#   * la mano libre que igual no entra (la palma parada con el antebrazo bajando: no hay codo que la haga posible) se
#     endereza hasta FREE_LIMIT, con la palma en el mismo lugar;
#   * el codo y el agarre de todo el clip salen de un camino (plan_clip, dos pasadas por clip en build_bamboo_master):
#     cambiar de solución, girar el antebrazo y torcer la mano entre dos cuadros cuesta, así no salta en el cuadro en
#     que otra solución pasó a ser apenas mejor;
#   * la mano libre no gira contra el antebrazo más de WRIST_RATE por cuadro ni sobre su eje más de TWIST_HOLD, y la
#     que agarra o suelta el bastón va o viene de donde estaba (place_arm, solve).
FLEX, EXTEND, RADIAL, ULNAR = 75.0, 65.0, 25.0, 38.0
FREE_LIMIT = 0.95
SWIVEL_MAX = 120.0
# la grilla de codos (giro alrededor del eje hombro-muñeca desde el polo pedido) y de agarres (vueltas del puño alrededor
# del caño desde el pedido), y el camino del clip: PATH_STEP de costo por paso de la grilla entre dos cuadros (al
# cuadrado), hasta PATH_REACH pasos por cuadro; el primer y el último cuadro quedan en su mejor solución
GRID_THETAS = tuple(float(x) for x in range(-int(SWIVEL_MAX), int(SWIVEL_MAX) + 1, 15))
GRID_ROLLS = tuple(float(x) for x in range(-180, 180, 15))
PATH_STEP, PATH_REACH = 1.0, 3
# por debajo de esta parte del polo perpendicular al eje hombro-muñeca, el lado del codo sale del cuadro anterior
POLE_FIRM = 0.35
# reparto del giro de la mano entre el antebrazo y la muñeca (fore_share)
FORE_SHARE, FORE_MAX = 0.8, math.radians(100.0)
# lo que cuesta en el camino del clip que el antebrazo cambie de giro entre dos cuadros: TWIST_W por cada TWIST_REF (al
# cuadrado). Una mano cuyo giro pedido pasa por los 180° le daba media vuelta al antebrazo en un cuadro (de +100° a -100°)
# o, desenrollado, le dejaba más de una vuelta a la muñeca: así el camino busca el codo que lo evita
TWIST_W, TWIST_REF = 0.5, math.radians(20.0)
# y que la mano gire contra el antebrazo entre dos cuadros más de JUMP_FREE grados (lo que master_lint mide como tirón):
# JUMP_W por cada JUMP_REF de más, al cuadrado. Con la mano en el bastón el codo y el agarre son lo único que la acompaña
# cuando el bastón gira rápido (ChopPalm_P3, DashStrike_P3)
JUMP_W, JUMP_FREE, JUMP_REF = 4.0, 20.0, 20.0
WRIST_COMFORT = 0.6       # desde acá la muñeca empieza a costar: una pose que ya entra no se toca
WRIST_GRIP_SOFT = 1.25    # y desde acá, mucho (el agarre del bastón tiene hasta 1.35 en master_lint)
RELEASE_HOLD = 0.6        # la mano que suelta el bastón lo sigue agarrando hasta que el peso del agarre baja de acá
# lo más que gira la mano libre contra su antebrazo en un cuadro (master_lint.WRIST_JUMP es 45)
WRIST_RATE = 40.0
# lo más que gira la mano libre sobre su eje: lo que toma el antebrazo (FORE_MAX) más 75° en la muñeca (master_lint.TWIST
# es 85). A una mano pedida más allá la busca por el otro lado (pasando por el medio, de a WRIST_RATE) si por ahí llega,
# y si no se queda en el tope: si siguiera, el giro cruzaba los 180° y el antebrazo daba media vuelta en un cuadro
TWIST_HOLD = FORE_MAX + math.radians(75.0)


def wrist_excess(flex, dev):
    return math.hypot(flex / (FLEX if flex >= 0.0 else EXTEND), dev / (RADIAL if dev >= 0.0 else ULNAR))


def wrist_frames(rig):
    """Por lado: (la relación antebrazo-mano del reposo, la palma y el pulgar en el marco de la mano en reposo)."""
    out = {}
    for S in "RL":
        Rf0, Rh0 = rot3(rig.rest["Forearm_" + S]), rot3(rig.rest["Hand_" + S])
        _, _, dors, thumb = hand_frame(S)
        out[S] = (Rf0.transposed() @ Rh0, (Rh0.transposed() @ -dors).normalized(), (Rh0.transposed() @ thumb).normalized())
    return out


def wrist_angles(D, n, l):
    """(flexión, desvío, giro) de la mano D (relativa a su neutra sobre ese antebrazo, en el marco de la mano neutra)."""
    y = D.col[1]
    flex = math.degrees(math.atan2(y.dot(n), y.y))
    dev = math.degrees(math.atan2(y.dot(l), y.y))
    q = D.to_quaternion()
    tw = (2.0 * math.degrees(math.atan2(q.y, q.w)) + 180.0) % 360.0 - 180.0
    return flex, dev, tw


def _seg_dist(p1, q1, p2, q2):
    """Distancia mínima entre los segmentos p1-q1 y p2-q2 (la de master_lint.seg_dist)."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1.dot(d1), d2.dot(d2), d2.dot(r)
    if a <= 1e-9 or e <= 1e-9:
        return (p1 - p2).length
    c, b = d1.dot(r), d1.dot(d2)
    den = a * e - b * b
    s = max(0.0, min(1.0, (b * f - c * e) / den)) if den > 1e-9 else 0.0
    t = (b * s + f) / e
    if t < 0.0:
        t, s = 0.0, max(0.0, min(1.0, -c / a))
    elif t > 1.0:
        t, s = 1.0, max(0.0, min(1.0, (b - c) / a))
    return ((p1 + d1 * s) - (p2 + d2 * t)).length


def fore_share(ang):
    """Lo que toma el antebrazo (rad) del giro 'ang' de la mano sobre su eje: como team_limbs, la mayor parte (el
    antebrazo prona y supina; la muñeca casi no gira), hasta FORE_MAX. Con la mitad (Pose.twist_follow) lo que quedaba en
    la muñeca llegaba a 90° y un giro rápido de la mano pedido por la clave era un tirón de la muñeca."""
    t = ang * FORE_SHARE
    return max(-FORE_MAX, min(FORE_MAX, t))


def _swing(q):
    """La parte de q que no es giro alrededor de su Y (q = swing @ giro en Y)."""
    t = Quaternion((q.w, 0.0, q.y, 0.0))
    if t.magnitude < 1e-9:
        return q.copy()
    return q @ t.normalized().inverted()


def _twist_y(M):
    """Giro (rad, -pi..pi) de M alrededor de su Y (como Pose.twist_follow)."""
    q = M.to_quaternion()
    a = 2.0 * math.atan2(q.y, q.w)
    return (a + math.pi) % (2.0 * math.pi) - math.pi


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
        self.wf = wrist_frames(rig)
        self.mode = "free"
        self.tables = {"R": [], "L": []}
        self.shares = {"R": [], "L": []}
        self.planes = {"R": [], "L": []}
        self.path = {"R": [], "L": []}
        self.frame = {"R": 0, "L": 0}
        self.share_prev = {}
        self.pole_prev = {}
        self.up_prev = {}
        self.d_prev = {}
        self.h_prev = {}
        self.ang_prev = {}
        self.ang_now = {}
        self.w_prev = {}
        self.rh_prev = {}
        self.wr_prev = {}

    def begin_clip(self, mode="free"):
        """Pasada nueva de un clip: 'collect' (junta las grillas de cada cuadro), 'replay' (el camino de plan_clip) o
        'free' (cada cuadro solo, sin historia: las poses de referencia)."""
        self.mode = mode
        self.frame = {"R": 0, "L": 0}
        self.share_prev = {}
        self.pole_prev = {}
        self.up_prev = {}
        self.d_prev = {}
        self.h_prev = {}
        self.ang_prev = {}
        self.ang_now = {}
        self.w_prev = {}
        self.rh_prev = {}
        self.wr_prev = {}
        if mode == "collect":
            self.tables = {"R": [], "L": []}
            self.shares = {"R": [], "L": []}
            self.planes = {"R": [], "L": []}

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
            qh = c.get("hand_" + s + "_q")
            if qh is not None:
                # el giro de la mano entre dos claves como un solo giro (master_clips.rigid_hands): los dedos y el dorso
                # interpolados cada uno por su lado no formaban una mano rígida y, cuando el dorso pasaba cerca de los
                # dedos, la palma daba media vuelta
                Rq = Quaternion(qh).normalized().to_matrix()
                hd, hu = Rq.col[1], Rq.col[2]
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
            Rh = self.hand_basis(S, hd, hu)
            wrist = palm - Rh @ PALM_LOCAL
            grip = None
            gw = c.get("grip_" + s + "_w")
            gw = 1.0 if gw is None else max(0.0, min(1.0, gw))
            # (una clave con la mano suelta deja el agarre de la vecina con grip_*_w en 0: esa mano es libre del todo)
            wp = self.w_prev.get(S, 0.0)
            if self.mode != "free":
                self.w_prev[S] = gw if (staff_on and g is not None) else 0.0
            if staff_on and g is not None and gw > 1e-3:
                # grip_*_w < 1: la mano va o viene del bastón (lo atrapa, lo suelta): mezcla de muñeca y giro. La que lo
                # va agarrando (el peso sube) sale de donde estaba en el cuadro anterior y cubre en este la parte que le
                # toca de lo que le falta: la mano libre de la clave de agarre es la de otra pose (la guardia de la fase
                # 1 en G3) y a mitad de camino Taunt_P3 la daba vuelta 110° en un cuadro
                catching = gw > wp + 1e-4 and S in self.rh_prev
                if catching:
                    k = (gw - wp) / max(1e-6, 1.0 - wp)
                    grip = (Ms, g, V(c["grip_" + s + "_up"]), c["grip_" + s + "_thumb"], k, self.rh_prev[S].copy(),
                            self.wr_prev[S].copy(), True)
                else:
                    # la que lo suelta no se tuerce entre el agarre y la mano de la clave siguiente mientras todavía lo
                    # sostiene: sigue agarrándolo hasta que el peso baja de RELEASE_HOLD y de ahí se abre (con el tope de
                    # WRIST_RATE de place_arm). Mezclada desde el principio, CraneKick_P3 pasaba por 1.42 de muñeca
                    gw_ = 1.0 if (gw < wp - 1e-4 and gw >= RELEASE_HOLD) else gw
                    grip = (Ms, g, V(c["grip_" + s + "_up"]), c["grip_" + s + "_thumb"], gw_, Rh.copy(), wrist.copy(), False)
                Rh, wrist = self.grip_hand(S, grip, 0.0)
            self.reach_with_clavicle(pose, S, wrist)
            Rh, wrist, pole = self.place_arm(pose, S, Rh, wrist, palm, V(elbow), grip)
            misses["hand_" + s] = pose.two_bone("UpperArm_" + S, "Forearm_" + S, wrist, pole)
            pose.place("Hand_" + S, compose(pose.tail("Forearm_" + S), Rh))
            self.twist_follow(pose, S)
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

    # ------------------------------------------------------------------ el brazo con la muñeca posible
    def hand_basis(self, S, hd, hu):
        """El giro de la mano pedido (dedos 'hd', dorso 'hu'). Con el dorso casi a lo largo de los dedos (claves que lo
        interpolan pasando cerca: el saludo de Taunt los pedía a 160°) lo que queda de él no dice hacia dónde mira la
        palma y la mano daba media vuelta en un cuadro: ahí se toma el dorso del cuadro anterior."""
        Y = hd.normalized()
        Z = hu - Y * hu.dot(Y)
        k = Z.length / max(hu.length, 1e-6)
        prev = self.up_prev.get(S)
        if prev is not None:
            w = max(0.0, min(1.0, (POLE_FIRM - k) / POLE_FIRM))
            Zp = prev - Y * prev.dot(Y)
            if w > 0.0 and Zp.length > 1e-6:
                Z = (Z.normalized() * (1.0 - w) + Zp.normalized() * w) if Z.length > 1e-6 else Zp
        R = basis_yz(Y, Z)
        if self.mode != "free":
            self.up_prev[S] = R.col[2].copy()
        return R

    def grip_hand(self, S, grip, roll):
        """La mano en el bastón con el agarre rodado 'roll' grados alrededor del caño (desde el que pidió la clave), y la
        mezcla con la mano libre si todavía va o viene del bastón. Devuelve (giro, muñeca)."""
        Ms, g, up, thumb, gw, Rh_free, w_free, _ = grip
        if abs(roll) > 1e-6:
            up = Matrix.Rotation(math.radians(roll), 3, rot3(Ms).col[1]) @ up
        Rg, wg = self.grip_frame(Ms, S, g, up, thumb)
        if gw >= 0.9999:
            return Rg, wg
        q = Rh_free.to_quaternion().slerp(Rg.to_quaternion(), gw)
        return q.to_matrix(), w_free.lerp(wg, gw)

    def arm_try(self, pose, S, wrist, pole, Rh, ref=None):
        """Las cuentas de Pose.two_bone y de twist_follow sin tocar la pose: (antebrazo final, codo, la mano
        relativa a su neutra, lo que gira el antebrazo y el giro pedido de la mano, en rad). ref: el giro pedido del
        cuadro anterior, hacia el que se desenrolla este (la mano libre, ver place_arm)."""
        R = self.rig
        ua, fa = "UpperArm_" + S, "Forearm_" + S
        Mu = pose.follow(ua)
        Sp, Fu0 = Mu.translation, rot3(Mu)
        a, b = R.length[ua], R.length[fa]
        Fl0 = Fu0 @ rot3(R.rel[fa])
        u0, l0 = Fu0.col[1], Fl0.col[1]
        n0 = u0.cross(l0)
        if n0.length < 1e-6:
            n0 = u0.orthogonal()
        n0.normalize()
        d_vec = wrist - Sp
        d = max(abs(a - b) + 1e-4, min(d_vec.length, (a + b) * 0.999))
        nd = d_vec.normalized() if d_vec.length > 1e-6 else u0
        cosA = max(-1.0, min(1.0, (a * a + d * d - b * b) / (2.0 * a * d)))
        sinA = math.sqrt(max(0.0, 1.0 - cosA * cosA))
        P = pole - nd * pole.dot(nd)
        if P.length < 1e-6:
            P = n0.cross(nd)
        P.normalize()
        E = Sp + nd * (a * cosA) + P * (a * sinA)
        u = (E - Sp).normalized()
        l = (Sp + nd * d - E).normalized()
        nn = u.cross(l)
        if nn.length < 1e-6:
            nn = n0
        nn.normalize()
        Rl = Matrix((l, nn, l.cross(nn))).transposed() @ Matrix((l0, n0, l0.cross(n0)))
        Rf = Rl @ Fl0
        rel0 = self.wf[S][0]
        ang = _twist_y((Rf @ rel0).transposed() @ Rh)
        if ref is not None:
            ang += 2.0 * math.pi * round((ref - ang) / (2.0 * math.pi))
        share = fore_share(ang)
        Rf = Rf @ Matrix.Rotation(share, 3, 'Y')
        return Rf, E, (Rf @ rel0).transposed() @ Rh, share, ang

    def place_arm(self, pose, S, Rh, wrist, palm, elbow, grip):
        """El codo (y, en el bastón, el agarre) con la muñeca más cómoda (ver 'muñecas', arriba). Devuelve (giro de la
        mano, muñeca, polo del codo). Cómo elige según el modo (begin_clip): 'free' la mejor de la grilla de este cuadro;
        'collect' además guarda la grilla para plan_clip; 'replay' el punto del camino de plan_clip para este cuadro.
        En los tres se afina alrededor del punto (5° y 2°)."""
        _, n, l = self.wf[S]
        Sp = pose.follow("UpperArm_" + S).translation
        E0 = self.arm_try(pose, S, wrist, elbow, Rh)[1]
        # el tronco como lo mide master_lint (la cápsula de la cadera al pecho, 13 cm) más el antebrazo (4 cm)
        Wc = pose.get("Chest")
        trunk_a = pose.head("Hips") + Vector((0.0, 0.0, 0.04))
        trunk_b = Wc.translation + (Wc @ Vector((0.0, self.rig.length["Chest"], 0.0)) - Wc.translation) * 0.85

        # el lado del codo del cuadro anterior (plane) es el de la primera pasada también en la segunda: con otra historia
        # el mismo codo de la grilla era otro brazo (Guard_P3 doblaba la muñeca de 55° a -34° en un cuadro)
        prevP = self.pole_prev.get(S)
        if self.mode == "collect":
            self.planes[S].append(prevP)
        elif self.mode == "replay" and self.frame[S] < len(self.planes[S]):
            prevP = self.planes[S][self.frame[S]]

        def plane(nd):
            """Hacia dónde dobla el codo, perpendicular al eje hombro-muñeca. Con el polo de la clave casi a lo largo del
            eje (el brazo que se estira hacia donde apuntaba el polo) su proyección no dice nada y saltaba de un lado al
            otro: el antebrazo daba media vuelta en un cuadro (Taunt, f34-35). Ahí se toma el lado del cuadro anterior."""
            P = elbow - nd * elbow.dot(nd)
            k = P.length / max(elbow.length, 1e-6)
            P = P.normalized() if k > 1e-6 else nd.orthogonal().normalized()
            if prevP is not None:
                w = max(0.0, min(1.0, (POLE_FIRM - k) / POLE_FIRM))
                Pp = prevP - nd * prevP.dot(nd)
                if w > 0.0 and Pp.length > 1e-6:
                    P = (P * (1.0 - w) + Pp.normalized() * w).normalized()
            return P

        prevS = self.share_prev.get(S)
        # el primer y el último cuadro sin el giro del anterior: son los que se cruzan con la guardia (lint_chains), que
        # se resuelve sola
        cont = (prevS is not None and self.mode == "replay" and 0 < self.frame[S] < len(self.path[S]) - 1)
        prevD = self.d_prev[S].to_quaternion() if S in self.d_prev else None

        def evaluate(th, r, hist=False):
            Rh_, w_ = self.grip_hand(S, grip, r) if grip is not None else (Rh, wrist)
            axis = (w_ - Sp).normalized()
            P0 = plane(axis)
            pole = Matrix.Rotation(math.radians(th), 3, axis) @ P0
            Rf, E, D, share, _ = self.arm_try(pose, S, w_, pole, Rh_)
            flex, dev, tw = wrist_angles(D, n, l)
            e = wrist_excess(flex, dev)
            cost = 3.0 * max(0.0, e - WRIST_COMFORT) ** 2 + 25.0 * max(0.0, e - 1.0) ** 2
            # con el bastón, cerca del tope de master_lint (1.35) cuesta mucho más: con los costos de los tirones el camino
            # aceptaba pasar dos cuadros por 1.6 para bajar el bastón de arriba a la guardia (PhaseStaff). La mano libre
            # no: la que no entra se endereza después, y cobrarle tanto metía el antebrazo de TwinPalm en el tronco
            if grip is not None:
                cost += 150.0 * max(0.0, e - WRIST_GRIP_SOFT) ** 2
            cost += (th / 90.0) ** 2 + (((r + 180.0) % 360.0 - 180.0) / 120.0) ** 2
            # el codo que sube de más se lee como brazo de aficionado; el antebrazo adentro del tronco, imposible
            if E.z > E0.z + 0.03:
                cost += 3.0 * ((E.z - E0.z) / 0.3) ** 2
            cl = _seg_dist(E, w_, trunk_a, trunk_b) - 0.17
            if cl < 0.02:
                cost += 60.0 * ((0.02 - cl) / 0.05) ** 2
            # lo que queda girado en la muñeca (después de lo que toma el antebrazo) se ve como un caramelo
            if abs(tw) > 35.0:
                cost += ((abs(tw) - 35.0) / 25.0) ** 2
            q = D.to_quaternion()
            if hist:
                cost += TWIST_W * ((share - prevS) / TWIST_REF) ** 2
                if prevD is not None:
                    j = 2.0 * math.degrees(math.acos(min(1.0, abs(q.dot(prevD)))))
                    cost += JUMP_W * (max(0.0, j - JUMP_FREE) / JUMP_REF) ** 2
            return cost, e, pole, Rh_, w_, Rf, D, P0, (share, q.w, q.x, q.y, q.z)

        rolls = GRID_ROLLS if grip is not None else (0.0,)
        if self.mode == "replay" and self.frame[S] < len(self.path[S]):
            th0, r0 = self.path[S][self.frame[S]]
            r0 = r0 if grip is not None else 0.0
            best = (evaluate(th0, r0, cont), th0, r0)
        else:
            table = [[0.0] * len(rolls) for _ in GRID_THETAS]
            shares = [[None] * len(rolls) for _ in GRID_THETAS]
            best = None
            for a, th in enumerate(GRID_THETAS):
                for b, r in enumerate(rolls):
                    v = evaluate(th, r)
                    table[a][b], shares[a][b] = v[0], v[-1]
                    if best is None or v[0] < best[0][0]:
                        best = (v, th, r)
            if self.mode == "collect":
                # todas las grillas del clip con todos los agarres: un cuadro con la mano libre (el bastón todavía no
                # llegó, o ya se soltó) cuesta lo mismo con cualquier agarre
                wide = (lambda t: t) if grip is not None else (lambda t: [row * len(GRID_ROLLS) for row in t])
                self.tables[S].append(wide(table))
                self.shares[S].append(wide(shares))
        self.frame[S] += 1
        for step in (5.0, 2.0):
            _, th0, r0 = best
            for dt in (-2, -1, 0, 1, 2):
                for dr in ((-2, -1, 0, 1, 2) if grip is not None else (0,)):
                    th = max(-SWIVEL_MAX, min(SWIVEL_MAX, th0 + dt * step))
                    v = evaluate(th, r0 + dr * step, cont)
                    if v[0] < best[0][0]:
                        best = (v, th, r0 + dr * step)
        (_, _, pole, Rh, wrist, Rf, D, P0, _), th, r = best
        if self.mode != "free":
            self.pole_prev[S] = P0
        # la mano libre, y la que está agarrando o soltando el bastón (grip_*_w < 1), se corrige en tres pasos, siempre
        # con la palma donde estaba (se vuelve a resolver el brazo):
        #   * sigue su giro desde el del cuadro anterior y no pasa de TWIST_HOLD;
        #   * no gira contra el antebrazo más de WRIST_RATE en un cuadro: cuando el brazo se estira de golpe (la palma
        #     parada de TwinPalm pasaba del antebrazo vertical al horizontal con la mano quieta, 54° de muñeca en un
        #     cuadro) la mano llega un cuadro después, como la de una persona; la que suelta el bastón (ver RELEASE_HOLD
        #     en solve) se abre así en vez de saltar a la mano libre de la clave;
        #   * si igual no entra se endereza (solo la que ya no agarra: grip_*_w < 0.5, que master_lint cuenta como
        #     libre): los dedos van por el camino más corto hacia el eje del antebrazo hasta quedar en FREE_LIMIT
        #     (continuo cuadro a cuadro aunque lo pedido pase de 90°)
        # La que está agarrando (el peso del agarre sube, ver solve) va desde la mano del cuadro anterior al agarre
        # completo cubriendo la parte que le toca, con el mismo reparto de giro: mezclada en el mundo, la mano iba bien
        # pero su giro contra el antebrazo cruzaba los 180° y el antebrazo daba media vuelta (Taunt_P3 f54)
        catching = grip is not None and grip[7]
        if grip is None or grip[4] < 0.999 or catching:
            loose = (grip is None or grip[4] < 0.5) and not catching
            rel0 = self.wf[S][0]
            ref = self.ang_prev.get(S)
            if catching:
                Rq, wq = self.grip_hand(S, grip[:4] + (1.0,) + grip[5:], r)
                pc = (self.wr_prev[S] + self.rh_prev[S] @ PALM_LOCAL).lerp(wq + Rq @ PALM_LOCAL, grip[4])
            else:
                Rq, pc = Rh, wrist + Rh @ PALM_LOCAL

            def place(Rh_):
                w_ = pc - Rh_ @ PALM_LOCAL
                return (Rh_, w_) + self.arm_try(pose, S, w_, pole, Rh_, ref)

            def clear(v):
                return _seg_dist(v[3], v[1], trunk_a, trunk_b) - 0.17 >= 0.005

            Rh, wrist, Rf, _, D, share, ang = place(Rh)
            Hp = self.h_prev.get(S)
            if ref is not None and Hp is not None:
                # el giro que se busca, del lado al que llega (por el otro lado si por el más corto se pasa de TWIST_HOLD:
                # la mano que venía del bastón con el antebrazo a -50° y pedía +160° iba a -200°, al tope, y al volver a
                # agarrarlo daba la vuelta en un cuadro), y el resto de la mano (swing) por separado
                s0 = _swing(Hp.to_quaternion())
                for _ in range(3):
                    F0 = self.fore0(Rf, share, S)
                    Hq = F0.transposed() @ Rq
                    tgt = _twist_y(Hq)
                    tgt += 2.0 * math.pi * round((ref - tgt) / (2.0 * math.pi))
                    if abs(tgt) > TWIST_HOLD:
                        alt = tgt - math.copysign(2.0 * math.pi, tgt)
                        if abs(alt) <= TWIST_HOLD:
                            tgt = alt
                        elif not catching:
                            tgt = math.copysign(TWIST_HOLD, tgt)
                    s1 = _swing(Hq.to_quaternion())
                    if s0.dot(s1) < 0.0:
                        s1.negate()
                    dsw = 2.0 * math.acos(min(1.0, s0.dot(s1)))
                    dtw = tgt - ref
                    if catching:
                        k = grip[4]
                    else:
                        k = min(1.0, math.radians(WRIST_RATE) / max(1e-9, math.hypot(dsw, dtw)))

                    def at(k_):
                        return place(F0 @ (s0.slerp(s1, k_).to_matrix() @ Matrix.Rotation(ref + dtw * k_, 3, 'Y')))
                    v = at(k)
                    if k < 1.0 and not catching and not clear(v):
                        # la mano que llega tarde no puede meter el antebrazo en el tronco (PhaseCoat, al sacarse el
                        # saco): ahí va lo justo más rápido
                        lo_k, hi_k = k, 1.0
                        if clear(at(1.0)):
                            for _b in range(8):
                                mid = 0.5 * (lo_k + hi_k)
                                lo_k, hi_k = (lo_k, mid) if clear(at(mid)) else (mid, hi_k)
                            v = at(hi_k)
                    Rh, wrist, Rf, _, D, share, ang = v
            Y0 = Vector((0.0, 1.0, 0.0))
            for _ in range(3 if loose else 0):
                if wrist_excess(*wrist_angles(D, n, l)[:2]) <= FREE_LIMIT + 0.01:
                    break
                y = D.col[1]
                lo, hi = 0.0, 1.0
                for _b in range(14):
                    mid = 0.5 * (lo + hi)
                    D2 = y.rotation_difference(NA.slerp_dir(y, Y0, mid)).to_matrix() @ D
                    if wrist_excess(*wrist_angles(D2, n, l)[:2]) > FREE_LIMIT:
                        lo = mid
                    else:
                        hi = mid
                Rh, wrist, Rf, _, D, share, ang = place((Rf @ rel0) @ y.rotation_difference(NA.slerp_dir(y, Y0, hi)).to_matrix() @ D)
        else:
            Rf, _, D, share, ang = self.arm_try(pose, S, wrist, pole, Rh)
        self.ang_now[S] = ang
        if self.mode != "free":
            self.d_prev[S] = D.copy()
            self.h_prev[S] = self.hand_rel(Rf, share, Rh, S)
            self.ang_prev[S] = ang
            self.rh_prev[S], self.wr_prev[S] = Rh.copy(), wrist.copy()
        return Rh, wrist, pole

    def fore0(self, Rf, share, S):
        """El marco neutro de la mano sobre el antebrazo Rf sin el giro 'share' que le pasó la mano (arm_try)."""
        return (Rf @ Matrix.Rotation(-share, 3, 'Y')) @ self.wf[S][0]

    def hand_rel(self, Rf, share, Rh, S):
        """La mano contra el antebrazo antes de repartir el giro: lo que el tope de WRIST_RATE limita (con la mano
        contra el antebrazo ya girado, un giro rápido pedido pasaba casi todo al antebrazo, que rotaba 80° en un cuadro)."""
        return self.fore0(Rf, share, S).transposed() @ Rh

    def plan_clip(self, anchors=True, prefix=None):
        """El camino del codo y del agarre de todo el clip (después de un 'collect'): el más barato sumando la grilla de
        cada cuadro y lo que cuesta cambiar entre cuadros (PATH_STEP por paso de la grilla, al cuadrado). Así el brazo
        cambia de solución, si tiene que hacerlo, repartido en varios cuadros y donde menos se nota, en vez de saltar
        en el cuadro en que la otra pasó a ser apenas mejor. Cambiar el giro del antebrazo (TWIST_W) y el de la mano
        contra él (JUMP_W) también cuesta. Con 'anchors' el primer y el último cuadro quedan en la mejor de su cuadro
        (con un ancla blanda el camino corría la primera para ahorrar tirones después y ChopPalm_P3 no encadenaba con la
        guardia: son los cuadros que se cruzan con la guardia de su fase, lint_chains, que se resuelve sola). prefix:
        {lado: [(codo, agarre)]} que los primeros cuadros siguen sí o sí (una variante de paso corto es el mismo golpe que
        su base hasta la suelta: lint_reach)."""
        import numpy as np
        self.path = {}
        for S in "RL":
            tabs = self.tables[S]
            if not tabs:
                self.path[S] = []
                continue
            C = np.array(tabs, dtype=np.float64)            # cuadros x codos x agarres
            Sh = np.array(self.shares[S], dtype=np.float64)      # cuadros x codos x agarres x (giro, cuaternión)
            F, A, B = C.shape
            if anchors:
                for f in (0, F - 1):
                    k = np.unravel_index(np.argmin(C[f]), C[f].shape)
                    keep = C[f][k]
                    C[f] = np.inf
                    C[f][k] = keep
            for f, (th, r) in enumerate((prefix or {}).get(S, ())[:F]):
                keep = C[f, GRID_THETAS.index(th), GRID_ROLLS.index(r) if B > 1 else 0]
                C[f] = np.inf
                C[f, GRID_THETAS.index(th), GRID_ROLLS.index(r) if B > 1 else 0] = keep
            acc = C[0].copy()
            back = np.zeros((F, A, B, 2), dtype=np.int16)
            for f in range(1, F):
                best = np.full((A, B), np.inf)
                arg = np.zeros((A, B, 2), dtype=np.int16)
                for da in range(-PATH_REACH, PATH_REACH + 1):
                    for db in (range(-PATH_REACH, PATH_REACH + 1) if B > 1 else (0,)):
                        # de (a - da, b - db) a (a, b): el codo no da la vuelta (bordes), el agarre sí (circular)
                        src = np.full((A, B), np.inf)
                        ssh = np.zeros((A, B, 5))
                        if da >= 0:
                            src[da:, :] = acc[:A - da, :] if da else acc
                            ssh[da:, :] = Sh[f - 1, :A - da, :] if da else Sh[f - 1]
                        else:
                            src[:da, :] = acc[-da:, :]
                            ssh[:da, :] = Sh[f - 1, -da:, :]
                        if db:
                            src, ssh = np.roll(src, db, axis=1), np.roll(ssh, db, axis=1)
                        dot = np.minimum(1.0, np.abs(np.sum(Sh[f, :, :, 1:] * ssh[:, :, 1:], axis=2)))
                        jump = np.maximum(0.0, 2.0 * np.degrees(np.arccos(dot)) - JUMP_FREE)
                        c = (src + PATH_STEP * (da * da + db * db) + TWIST_W * ((Sh[f, :, :, 0] - ssh[:, :, 0]) / TWIST_REF) ** 2
                             + JUMP_W * (jump / JUMP_REF) ** 2)
                        m = c < best
                        best[m] = c[m]
                        arg[m, 0] = da
                        arg[m, 1] = db
                acc = best + C[f]
                back[f] = arg
            a, b = np.unravel_index(np.argmin(acc), acc.shape)
            path = [None] * F
            for f in range(F - 1, -1, -1):
                path[f] = (GRID_THETAS[a], (GRID_ROLLS[b] if B > 1 else 0.0))
                if f:
                    da, db = back[f, a, b]
                    a, b = a - int(da), (b - int(db)) % B
            self.path[S] = path
        self.tables = {"R": [], "L": []}
        self.shares = {"R": [], "L": []}

    def twist_follow(self, pose, S):
        """Pose.twist_follow(antebrazo, mano) con fore_share: lo mismo que midió arm_try para el camino del clip (que es el que
        evita que el giro pedido cruce los 180°; desenrollarlo acá dejaba más de una vuelta en la muñeca y la última pose
        no encadenaba con la guardia)."""
        fa, ha = "Forearm_" + S, "Hand_" + S
        Wl, We = pose.get(fa), pose.get(ha)
        ang = _twist_y((Wl @ self.rig.rel[ha]).inverted() @ We)
        # del lado que eligió place_arm (la mano libre puede pasar de los 180° desenrollada)
        ref = self.ang_now.get(S)
        if ref is not None:
            ang += 2.0 * math.pi * round((ref - ang) / (2.0 * math.pi))
        share = fore_share(ang)
        if self.mode != "free":
            self.share_prev[S] = share
        pose.W[fa] = compose(Wl.translation, rot3(Wl) @ Matrix.Rotation(share, 3, 'Y'))

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
