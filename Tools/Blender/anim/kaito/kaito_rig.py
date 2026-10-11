"""Esqueleto de juego de Kaito y traducción de controles de animación a huesos.

ESQUELETO DE JUEGO (audit_anim ANIM-04/12). El rig del equipo colgaba las manos (Mando) y los pies (Pie)
de huesos de IK que nacen en la raíz de la armadura (Targetbrazo / Targetpie): Unity mezcla cada transform
por separado, así que en cada crossfade la muñeca y el tobillo se despegaban del antebrazo y la tibia
(4-9 % del alto). Acá:
  * Mando.L/R pasan a ser hijos de Antebrazo.L/R y Pie.L/R de Tibia.L/R (misma cabeza, cola y roll: el
    bind pose de cada hueso no cambia, solo su padre);
  * los pesos de Targetbrazo -> Mando, Targetpie -> Pie y Polebrazo.R (7 vértices del codo) -> el hueso
    más cercano del brazo: con el rig viejo esos vértices ya seguían a la mano y al pie;
  * los Target/Pole QUEDAN en el FBX, sin pesos y quietos en reposo: los kits de zona
    (Characters/Kits/Kit_kaito_bandana.fbx) traen el esqueleto completo de Kaito en su skin y
    CharacterKits.Attach no viste el kit si falta un solo nombre. Ningún clip nuevo los mueve.
  * nada más cambia: nombres, slots de material, objeto Isan colgado de KatanaBone, orientación de la
    armadura (el kit se arma con la misma; Kaito sigue con modelYaw 90).

ESPACIO DE AUTORÍA ("C"). La armadura de Kaito mira a +Y y tiene el piso en z = -0.8128 (unidades del
archivo: 2.833 u = 1.5 m en el juego). Para escribir las poses con las convenciones de nindo_anim (frente
-Y, derecha del personaje -X, piso en z 0, x+ = inclinarse adelante, z+ = girar a su izquierda) el Rig se
arma con el reposo llevado a C (giro de 180° en Z y el piso a 0). Las bases locales que escribe
Rig.to_local no dependen de ese cambio (es el mismo para todos los huesos), así que lo que se exporta es
la pose real de la armadura.
"""
import math
import bpy
from mathutils import Vector, Matrix, Quaternion
import nindo_anim as NA
from nindo_anim import V, euler_q, basis_yz, compose, rot3

# ------------------------------------------------------------------ medidas
GROUND_ARM_Z = -0.8128                 # suela en la pose de bind (lo que NormalizeHeight pone en y = 0)
TO_C = Matrix.Translation((0.0, 0.0, -GROUND_ARM_Z)) @ Matrix.Rotation(math.pi, 4, 'Z')
HEIGHT_U = 2.833                       # alto de bind (unión de Cuerpo + Isan) en unidades del archivo
M_PER_U = 1.5 / HEIGHT_U               # metros del juego por unidad (NindoContent: height 1.5)
U_PER_M = 1.0 / M_PER_U

# katana (medida sobre la malla Isan, espacio C en reposo): eje de la hoja, punto del puño derecho, punta.
# El filo mira a -X (la derecha de Kaito) con la hoja adelante: el slot Glint está de ese lado del eje.
BLADE_REST = Vector((0.088, -0.996, 0.022)).normalized()
EDGE_REST = Vector((-1.0, 0.088, 0.0)).normalized()
GRIP_REST = Vector((-1.083, 0.039, 1.499))         # centro del puño derecho sobre la empuñadura
TIP_C_REST = Vector((-0.893, -1.600, 1.536))
GRIP_L_OFF = 0.25                                  # la mano izquierda va 25 cm (u) más cerca del pomo
# Empuñadura en diagonal (tenouchi): en el bind la hoja sale del puño a 90° del eje de la mano, como un martillo; así
# una hoja que sigue al brazo (cada impacto, la guardia, la carrera con la katana atrás) pedía 90° de muñeca. La
# empuñadura real cruza la palma en diagonal, del índice al talón de la mano: la katana gira sobre el puño hacia los
# dedos. Se anima en KatanaBone (constante en todos los clips): el bind del FBX no cambia.
GRIP_TILT_DEG = 30.0

# pie (espacio C, lado derecho; el izquierdo es el espejo en X): tobillo, punta y talón de la suela
ANKLE_R = Vector((-0.243, 0.082, 0.215))
SOLE_TOE_Y, SOLE_HEEL_Y, SOLE_BALL_Y = -0.349, 0.24, -0.19

R_BONES = dict(clav="Hombro.R", ua="Brazo.R", fa="Antebrazo.R", hand="Mando.R", thigh="Pierna.r", shin="Tibia.R", foot="Pie.R")
L_BONES = dict(clav="Hombro.L", ua="Brazo.L", fa="Antebrazo.L", hand="Mando.L", thigh="Pierna.l", shin="Tibia.L", foot="Pie.L")
LEGACY = ("Targetbrazo.L", "Targetbrazo.R", "Targetpie.L", "Targetpie.R", "Polebrazo.L", "Polebrazo.R", "Polepie.L", "Polepie.R")
FINGERS = ("Dedo1", "Dedo2", "Dedo3", "Pulgar", "Puntadedo1", "Puntadedo2", "Puntadedo3", "Puntapulgar")

# puño cerrado del Idle del equipo (base local w, x, y, z de la mano derecha; la izquierda es su espejo):
# la derecha agarra siempre la empuñadura; la izquierda va de abierta (reposo) a este puño con 'fingers_l'
FIST_R = {
    "Dedo1": (0.9047, -0.4116, 0.093, 0.0595), "Puntadedo1": (0.6958, -0.6018, 0.0834, 0.3831),
    "Dedo2": (0.9397, -0.2904, 0.1801, -0.0133), "Puntadedo2": (0.6051, -0.4048, -0.0911, 0.6795),
    "Dedo3": (0.797, -0.5918, 0.0716, 0.0965), "Puntadedo3": (0.7542, -0.3223, -0.1842, 0.5416),
    "Pulgar": (0.9121, -0.4099, 0.0, 0.0), "Puntapulgar": (0.9108, 0.3595, -0.0746, -0.1891),
}


def fist(side):
    out = {}
    for f, (w, x, y, z) in FIST_R.items():
        out[f + "." + side] = Quaternion((w, x, y, z)) if side == "R" else Quaternion((w, x, -y, -z))
    return out


# formas de mano (cuánto del puño lleva cada dedo; 0 = la mano relajada del reposo, < 0 = más abierta). Dedo1 es el
# índice (al lado del pulgar), Dedo2 el medio y Dedo3 el anular y el meñique juntos (el modelo tiene tres dedos):
#   seal   índice y medio estirados, el resto cerrado con el pulgar encima (el sello ninja de la bandana)
#   pinch  el pulgar y el índice juntos sosteniendo algo fino (la varita de incienso)
#   flat   la palma abierta y plana (empujar el piso, las palmas juntas del rezo, el empujón de la bandana)
HAND_SHAPES = {
    "seal": {"Dedo1": -0.15, "Puntadedo1": -0.25, "Dedo2": -0.15, "Puntadedo2": -0.25, "Dedo3": 1.0, "Puntadedo3": 1.0,
             "Pulgar": 0.9, "Puntapulgar": 0.9},
    "pinch": {"Dedo1": 0.5, "Puntadedo1": 0.45, "Dedo2": 0.75, "Puntadedo2": 0.85, "Dedo3": 0.95, "Puntadedo3": 1.0,
              "Pulgar": 0.75, "Puntapulgar": 0.5},
    "flat": {"Dedo1": -0.2, "Puntadedo1": -0.45, "Dedo2": -0.2, "Puntadedo2": -0.45, "Dedo3": -0.2, "Puntadedo3": -0.45,
             "Pulgar": -0.1, "Puntapulgar": -0.2},
}


def qpow(q, t):
    """q elevado a t (t puede ser negativo o mayor que 1): el mismo giro, escalado."""
    ax, ang = q.to_axis_angle()
    return Quaternion(ax, ang * t)


# ------------------------------------------------------------------ muñecas
# Grados de la muñeca medidos en el marco de la MANO con el reposo descontado: flexión + hacia la palma (- es
# extensión), desvío cubital + hacia el meñique (- es radial, hacia el pulgar), giro de la mano sobre el antebrazo.
# Las poses del B3 decían la hoja y su filo; la muñeca salía de ahí y quedaba doblada 70-160° (el puño "quebrado" que
# se veía en el juego). COMFORT: lo que la katana busca (gira sobre su propio eje y el codo rota alrededor del eje
# hombro-muñeca para quedar adentro); LIMIT: lo que una mano libre nunca pasa (se recorta).
# El giro es la pronación/supinación respecto de la bisagra del codo: 0 es el neutro (con el brazo colgando, el
# pulgar adelante; medido en twist_test), + supina en la derecha (la palma mira adelante) y prona en la izquierda.
WRIST_COMFORT = {"flex": (-28.0, 32.0), "ulnar": (-8.0, 32.0), "twist": (-65.0, 65.0)}
WRIST_LIMIT = {"flex": (-62.0, 66.0), "ulnar": (-18.0, 40.0), "twist": (-85.0, 85.0)}
MAX_SWIVEL = 50.0           # grados que el codo puede girar alrededor del eje hombro-muñeca
ROLL_HINT = 260.0           # costo (grados² de muñeca) de girar la hoja 180° respecto del filo autorado
SWIVEL_COST = 2.0           # costo por (10°)² de codo girado: solo lo necesario
ROLL_GRID = 72              # giros de la hoja probados por cuadro (cada 5°)
ROLL_SMOOTH = 14.0          # costo por (10°)² de giro de la hoja entre dos cuadros del juego (roll_path)


def roll_path(tables, pinned, loop=False, time_scale=1.0):
    """Giro de la hoja (grados) para cada cuadro de un clip: el camino de la grilla que minimiza el costo de las
    muñecas más un costo por girar entre cuadros (programación dinámica). Elegir el mejor giro cuadro a cuadro daba
    saltos de 120-170° entre dos mínimos parecidos (la mano daba media vuelta en 33 ms). 'pinned': {cuadro: grados}
    que quedan fijos (el primero y el último: los empalmes con otros clips salen de los mismos controles)."""
    n = len(tables)
    G = ROLL_GRID
    grid = [-180.0 + 360.0 / G * k for k in range(G)]
    lam = ROLL_SMOOTH * time_scale * time_scale / 100.0

    def wrap(d):
        return (d + 180.0) % 360.0 - 180.0

    def local(f, k):
        if f in pinned:
            return 0.0 if abs(wrap(grid[k] - pinned[f])) <= 180.0 / G + 1e-6 else 1e9
        t = tables[f]
        return t[k] if t is not None else 0.0
    INF = float("inf")
    cost = [[INF] * G for _ in range(n)]
    back = [[0] * G for _ in range(n)]
    for k in range(G):
        cost[0][k] = local(0, k)
    for f in range(1, n):
        for k in range(G):
            lc = local(f, k)
            best, arg = INF, 0
            for j in range(G):
                v = cost[f - 1][j] + lam * wrap(grid[k] - grid[j]) ** 2
                if v < best:
                    best, arg = v, j
            cost[f][k] = best + lc
            back[f][k] = arg
    k = min(range(G), key=lambda q: cost[n - 1][q])
    path = [0] * n
    for f in range(n - 1, -1, -1):
        path[f] = k
        k = back[f][k]
    # sin escalones de 5°: se desenrolla y se suaviza ([1 2 1] dos veces) todo lo que no está fijo
    out = [grid[path[0]] if 0 not in pinned else pinned[0]]
    for f in range(1, n):
        v = pinned[f] if f in pinned else grid[path[f]]
        out.append(out[-1] + wrap(v - out[-1]))
    for _ in range(2):
        prev = list(out)
        for f in range(1, n - 1):
            if f not in pinned:
                out[f] = 0.25 * prev[f - 1] + 0.5 * prev[f] + 0.25 * prev[f + 1]
    return [wrap(v) for v in out]


# ------------------------------------------------------------------ esqueleto de juego
def game_skeleton(arm, body):
    """Reparenta manos y pies y pasa los pesos de los huesos de IK (idempotente). Devuelve un resumen."""
    bpy.context.view_layer.objects.active = arm
    for o in bpy.context.selected_objects:
        o.select_set(False)
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    changed = []
    for child, parent in (("Mando.L", "Antebrazo.L"), ("Mando.R", "Antebrazo.R"), ("Pie.L", "Tibia.L"), ("Pie.R", "Tibia.R")):
        if eb[child].parent is None or eb[child].parent.name != parent:
            eb[child].use_connect = False
            eb[child].parent = eb[parent]
            changed.append(child)
    bpy.ops.object.mode_set(mode='OBJECT')
    moved = {}
    vg = body.vertex_groups

    def merge(src, dst_pick):
        if src not in vg:
            return
        si = vg[src].index
        n = 0
        for v in body.data.vertices:
            w = next((g.weight for g in v.groups if g.group == si), 0.0)
            if w <= 0.0:
                continue
            dst = dst_pick(v)
            if dst not in vg:
                vg.new(name=dst)
            vg[dst].add([v.index], w, 'ADD')
            n += 1
        vg[src].remove([v.index for v in body.data.vertices])
        if n:
            moved[src] = n
    for S in "LR":
        merge("Targetbrazo." + S, lambda v, S=S: "Mando." + S)
        merge("Targetpie." + S, lambda v, S=S: "Pie." + S)
    # el codo derecho: al hueso del brazo cuya recta pasa más cerca de cada vértice
    arm_bones = [arm.data.bones[n] for n in ("Brazo.R", "Antebrazo.R")]
    Mi = arm.matrix_world.inverted() @ body.matrix_world

    def nearest(v):
        p = Mi @ v.co
        best = None
        for b in arm_bones:
            a, c = b.head_local, b.tail_local
            t = max(0.0, min(1.0, (p - a).dot(c - a) / max(1e-9, (c - a).length_squared)))
            d = (a + (c - a) * t - p).length
            if best is None or d < best[0]:
                best = (d, b.name)
        return best[1]
    merge("Polebrazo.R", nearest)
    for n in LEGACY:
        if n in vg:
            vg[n].remove([v.index for v in body.data.vertices])
    return {"reparented": changed, "weights_moved": moved}


def c_rig(arm):
    """Rig de nindo_anim con el reposo en el espacio C (ver arriba)."""
    rig = NA.Rig(arm)
    for n in rig.names:
        rig.rest[n] = TO_C @ rig.rest[n]
        rig.rest_inv[n] = rig.rest[n].inverted()
    for n in rig.names:
        p = rig.parent[n]
        rig.rel[n] = (rig.rest_inv[p] @ rig.rest[n]) if p else rig.rest[n].copy()
    return rig


def sole_points(side):
    """(punta, talón, bola) de la suela en reposo, espacio C, para un lado."""
    sx = 1.0 if side == "R" else -1.0
    ax = ANKLE_R.x * sx
    return (Vector((ax, SOLE_TOE_Y, 0.0)), Vector((ax, SOLE_HEEL_Y, 0.0)), Vector((ax, SOLE_BALL_Y, 0.0)))


def sole_corners(side):
    """Las cuatro esquinas de la suela (punta y talón, adentro y afuera) en reposo, espacio C."""
    sx = 1.0 if side == "R" else -1.0
    xs = (-0.408 * sx, -0.09 * sx) if side == "R" else (0.408, 0.09)
    return [Vector((x, y, 0.0)) for x in xs for y in (SOLE_TOE_Y, SOLE_HEEL_Y)]


def ankle_rest(side):
    return Vector((ANKLE_R.x * (1.0 if side == "R" else -1.0), ANKLE_R.y, ANKLE_R.z))


def foot_rot(pitch, roll=0.0, yaw=0.0):
    """Giro del pie (grados): cabeceo + = la punta baja (el talón sube), giro + = la punta hacia su izquierda."""
    return (Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Matrix.Rotation(math.radians(pitch), 3, 'X')
            @ Matrix.Rotation(math.radians(roll), 3, 'Y'))


def foot_on(side, x, y, pitch=0.0, yaw=0.0, pivot="flat", roll=0.0):
    """Tobillo (x, y, z) y giro del pie para una huella apoyada en (x, y) del piso (la huella = dónde queda
    el tobillo con el pie plano). pivot 'toe' / 'ball' / 'heel': el pie gira 'pitch' sobre el borde de la
    punta, la bola o el talón, que no se mueve (pararse en punta no patina ni mete la suela en el piso)."""
    toe, heel, ball = sole_points(side)
    A = ankle_rest(side)
    R = foot_rot(pitch, roll, yaw)
    Ry = Matrix.Rotation(math.radians(yaw), 3, 'Z')
    base = Vector((x, y, A.z))
    if pivot == "flat" or abs(pitch) < 1e-6:
        return tuple(base), (pitch, roll, yaw)
    P = {"toe": toe, "heel": heel, "ball": ball}[pivot]
    Pw = base + Ry @ (P - A)                       # el borde que apoya, con el pie plano
    ank = Pw + R @ (A - P)
    return tuple(ank), (pitch, roll, yaw)


# ------------------------------------------------------------------ controles por defecto
NEUTRAL = {
    "hips": (0.0, 0.0, 0.0), "hips_rot": (0.0, 0.0, 0.0), "spine": (0.0, 0.0, 0.0), "head": (0.0, 0.0, 0.0),
    "clav_r": (0.0, 0.0, 0.0), "clav_l": (0.0, 0.0, 0.0),
    "grip": tuple(GRIP_REST), "blade": tuple(BLADE_REST), "edge": tuple(EDGE_REST), "elbow_r": (-0.3, 0.6, -0.6),
    "hand_l": (0.5, -0.2, 1.1), "hand_l_dir": (0.2, -0.4, -0.9), "hand_l_up": (1.0, 0.0, 0.0), "elbow_l": (0.4, 0.6, -0.5),
    "grip_l": 0.0, "fingers_l": 0.6,
    "foot_r": tuple(ankle_rest("R")), "foot_r_rot": (0.0, 0.0, 0.0), "knee_r": (-0.15, -1.0, 0.0),
    "foot_l": tuple(ankle_rest("L")), "foot_l_rot": (0.0, 0.0, 0.0), "knee_l": (0.15, -1.0, 0.0),
    "travel": 0.0, "lift": 0.0, "breath": 0.0, "tremble": 0.0, "arm_space": 0.0,
    # mano derecha libre (free_r 0..1: 0 = agarra la katana, 1 = va a hand_r con su giro) y katana suelta (katana_free
    # 0..1: la hoja queda donde dicen grip/blade/edge, p. ej. apoyada en el piso, y la mano se puede ir). roll_opt: cuánto
    # gira la hoja sobre su eje para enderezar las muñecas (0 = el filo autorado exacto: mientras la deja o la levanta)
    "free_r": 0.0, "hand_r": (-0.5, -0.2, 1.1), "hand_r_dir": (-0.2, -0.4, -0.9), "hand_r_up": (-1.0, 0.0, 0.0),
    "katana_free": 0.0, "roll_opt": 1.0,
    # formas de mano (HAND_SHAPES): puño de la derecha (1 = agarra), sello / pinza / palma plana de cada lado
    "fist_r": 1.0, "seal_l": 0.0, "pinch_r": 0.0, "flat_r": 0.0, "flat_l": 0.0, "seal_r": 0.0,
}


KNEE_FLOOR_U = 0.085        # altura de la articulación de una rodilla apoyada (el radio de la malla de la rodilla)


def ik_mid(S, T, a, b, pole, reach=0.999):
    """Articulación del medio (codo, rodilla) de una IK de dos huesos, con la misma cuenta que Pose.two_bone pero
    sin escribir la pose (para probar polos y alturas antes de elegir)."""
    d_vec = T - S
    d = max(abs(a - b) + 1e-4, min(d_vec.length, (a + b) * reach))
    nd = d_vec.normalized() if d_vec.length > 1e-6 else Vector((0.0, 0.0, -1.0))
    cosA = max(-1.0, min(1.0, (a * a + d * d - b * b) / (2.0 * a * d)))
    sinA = math.sqrt(max(0.0, 1.0 - cosA * cosA))
    P = V(pole) - nd * V(pole).dot(nd)
    if P.length < 1e-6:
        P = nd.orthogonal()
    P.normalize()
    return S + nd * (a * cosA) + P * (a * sinA), S + nd * d


class Solver:
    """Controles -> pose de todos los huesos (nindo_anim.Pose en espacio C)."""

    def __init__(self, rig):
        self.rig = rig
        R = rig
        self.K_rest = compose(GRIP_REST, basis_yz(BLADE_REST, -EDGE_REST))
        # la katana en el marco de la mano, girada GRIP_TILT_DEG sobre el centro del puño hacia los dedos
        Krel0 = R.rest_inv["Mando.R"] @ self.K_rest
        gp = R.rest_inv["Mando.R"] @ GRIP_REST
        ax = rot3(Krel0).col[1].cross(Vector((0.0, 1.0, 0.0))).normalized()
        D = Matrix.Translation(gp) @ Matrix.Rotation(math.radians(GRIP_TILT_DEG), 4, ax) @ Matrix.Translation(-gp)
        self.hand_from_K = (D @ Krel0).inverted()
        self.K_to_bone = self.K_rest.inverted() @ R.rest["KatanaBone"]
        # la mano izquierda: dónde queda su puño respecto de la muñeca (espejo de la derecha)
        self.grip_in_hand_r = R.rest_inv["Mando.R"] @ GRIP_REST
        self.fist = {"R": fist("R"), "L": fist("L")}
        # la mano en reposo respecto de su antebrazo (5°): se descuenta para medir la muñeca
        self.R0t = {S: (rot3(R.rest["Antebrazo." + S]).transposed() @ rot3(R.rest["Mando." + S])).transposed() for S in "RL"}
        self.misses = {}
        self.wrist = {}
        self.roll_deg = 0.0
        # build_kaito elige el giro de la hoja de todo un clip a la vez (ver roll_path): la primera pasada guarda el
        # costo de cada giro de la grilla por cuadro (roll_table), la segunda fuerza el elegido (force_roll, grados)
        self.roll_table = None
        self.force_roll = None

    def katana_frame(self, grip, blade, edge):
        return compose(V(grip), basis_yz(blade, -V(edge)))

    def left_grip(self, K):
        """Mano izquierda en la empuñadura: espejo de la derecha respecto del plano de la hoja (los dos puños
        cierran igual), GRIP_L_OFF más cerca del pomo."""
        Hr = K @ self.hand_from_K
        X = rot3(K).col[0]
        S = Matrix(((1 - 2 * X.x * X.x, -2 * X.x * X.y, -2 * X.x * X.z),
                    (-2 * X.y * X.x, 1 - 2 * X.y * X.y, -2 * X.y * X.z),
                    (-2 * X.z * X.x, -2 * X.z * X.y, 1 - 2 * X.z * X.z)))
        Rl = S @ rot3(Hr) @ Matrix.Diagonal((-1.0, 1.0, 1.0))
        g = K.translation - rot3(K).col[1] * GRIP_L_OFF
        off = Vector((-self.grip_in_hand_r.x, self.grip_in_hand_r.y, self.grip_in_hand_r.z))
        return compose(g - Rl @ off, Rl)

    def left_hand(self, K, Hf, gl):
        """La mano izquierda entre su pose libre (Hf) y la empuñadura (gl 0..1)."""
        if gl <= 0.001:
            return Hf
        Hg = self.left_grip(K)
        return compose(Hf.translation.lerp(Hg.translation, gl), Hf.to_quaternion().slerp(Hg.to_quaternion(), gl).to_matrix())

    def clear_floor(self, K, floor=0.04):
        """Si la punta de la hoja atravesaría el piso, la hoja gira hacia arriba sobre el puño lo justo (la deja
        rozar el piso: caídas, golpes bajos)."""
        tip_local = self.K_rest.inverted() @ TIP_C_REST
        tip = K @ tip_local
        if tip.z >= floor:
            return K
        g = K.translation
        bd = rot3(K).col[1]
        ax = bd.cross(Vector((0.0, 0.0, 1.0)))
        if ax.length < 1e-4:
            ax = rot3(K).col[0]
        ax.normalize()
        lo, hi = 0.0, math.radians(85.0)
        for _ in range(18):
            mid = (lo + hi) * 0.5
            if (g + Matrix.Rotation(mid, 3, ax) @ (tip - g)).z >= floor:
                hi = mid
            else:
                lo = mid
        return compose(g, Matrix.Rotation(hi, 3, ax) @ rot3(K))

    def reach_with_clavicle(self, pose, B, target, max_deg=22.0):
        """Brazos cortos (0.3 m): si la muñeca no llega, el hombro se estira hacia el objetivo."""
        R = self.rig
        reach = (R.length[B["ua"]] + R.length[B["fa"]]) * 0.985
        for _ in range(2):
            sh = (pose.get(B["clav"]) @ R.rel[B["ua"]]).translation
            ex = (V(target) - sh).length - reach
            if ex <= 0.0:
                return
            ch = pose.head(B["clav"])
            a, b = sh - ch, V(target) - ch
            ax = a.cross(b)
            if ax.length < 1e-6:
                return
            ang = min(ex / max(a.length, 1e-3), math.radians(max_deg))
            M = pose.get(B["clav"])
            pose.place(B["clav"], compose(ch, Quaternion(ax.normalized(), ang).to_matrix() @ rot3(M)))

    # ---------------------------------------------------------------- muñecas
    def wrist_eval(self, F, H, S, limits):
        """(doblez total, doblez permitido en esa dirección, giro) en grados de la mano H respecto del antebrazo F
        (matrices 3x3). El permitido sale de una elipse con los topes de flexión/extensión y desvío de 'limits'."""
        He = H @ self.R0t[S]
        e = He.transposed() @ F.col[1]                  # el antebrazo visto desde la mano
        flex_c = e.z
        ul_c = -e.x if S == "R" else e.x                # el meñique es +X en la derecha y -X en la izquierda
        beta = math.degrees(math.acos(max(-1.0, min(1.0, e.y))))
        r = math.hypot(flex_c, ul_c)
        if r < 1e-6:
            bmax = min(-limits["flex"][0], limits["flex"][1], -limits["ulnar"][0], limits["ulnar"][1])
        else:
            ca, sa = flex_c / r, ul_c / r
            lf = limits["flex"][1] if ca > 0 else -limits["flex"][0]
            lu = limits["ulnar"][1] if sa > 0 else -limits["ulnar"][0]
            bmax = 1.0 / math.sqrt((ca / lf) ** 2 + (sa / lu) ** 2)
        Rl = F.transposed() @ He
        d = Rl.col[1]
        sw = Vector((0.0, 1.0, 0.0)).rotation_difference(d).to_matrix()
        Tw = sw.transposed() @ Rl
        tau = math.degrees(math.atan2(Tw[0][2], Tw[0][0]))
        return beta, bmax, tau

    @staticmethod
    def twist_range(limits, S):
        lo, hi = limits["twist"]
        return (lo, hi) if S == "R" else (-hi, -lo)

    def wrist_cost(self, F, H, S, limits=WRIST_COMFORT):
        beta, bmax, tau = self.wrist_eval(F, H, S, limits)
        lo, hi = self.twist_range(limits, S)
        return max(0.0, beta - bmax) ** 2 + 0.06 * beta * beta + max(0.0, lo - tau, tau - hi) ** 2

    def arm_frame(self, pose, B, target, pole):
        """Marco del antebrazo que dejaría Pose.two_bone (misma cuenta) para un objetivo y un polo."""
        R = self.rig
        upper, lower = B["ua"], B["fa"]
        Mu = pose.get(B["clav"]) @ R.rel[upper]
        S = Mu.translation
        a, b = R.length[upper], R.length[lower]
        Fu0 = rot3(Mu)
        Fl0 = Fu0 @ rot3(R.rel[lower])
        u0, l0 = Fu0.col[1], Fl0.col[1]
        n0 = u0.cross(l0)
        if n0.length < 1e-6:
            n0 = u0.orthogonal()
        n0.normalize()
        E, Tc = ik_mid(S, V(target), a, b, pole)
        u = (E - S).normalized()
        l = (Tc - E).normalized()
        nn = u.cross(l)
        if nn.length < 1e-6:
            nn = n0
        nn.normalize()

        def frame(y, n):
            return Matrix((y, n, y.cross(n))).transposed()
        return frame(l, nn) @ frame(l0, n0).transposed() @ Fl0

    def elbow_choice(self, pose, B, S, H, pole, limits=WRIST_COMFORT):
        """(costo, polo) del codo: gira alrededor del eje hombro-muñeca hacia donde la muñeca queda derecha (el polo
        opuesto a la mano), solo lo necesario y hasta MAX_SWIVEL: el codo autorado arma la silueta."""
        R = self.rig
        T = H.translation
        Sh = (pose.get(B["clav"]) @ R.rel[B["ua"]]).translation
        nd = (T - Sh).normalized()
        Pa = V(pole) - nd * V(pole).dot(nd)
        hy = rot3(H).col[1]
        hp = hy - nd * hy.dot(nd)
        cands = [None]
        if Pa.length > 1e-5 and hp.length > 1e-5:
            Pa.normalize()
            Po = -hp.normalized()
            ang = math.atan2(nd.dot(Pa.cross(Po)), Pa.dot(Po))
            lim = math.radians(MAX_SWIVEL)
            angc = max(-lim, min(lim, ang))
            cands = [angc * k / 3.0 for k in range(4)]
        best = None
        H3 = rot3(H)
        for psi in cands:
            P = V(pole) if psi is None else Matrix.Rotation(psi, 3, nd) @ Pa
            F = self.arm_frame(pose, B, T, P)
            cost = self.wrist_cost(F, H3, S, limits) + (SWIVEL_COST * (math.degrees(psi) / 10.0) ** 2 if psi else 0.0)
            if best is None or cost < best[0]:
                best = (cost, tuple(P))
        return best

    def katana_roll(self, pose, K, c, gl, Hf_l):
        """Gira la katana sobre el eje de su hoja (por el puño: la hoja y la punta no se mueven) para que las dos
        muñecas queden naturales; el filo autorado solo desempata (ROLL_HINT). Devuelve (K, polo der., polo izq.)."""
        G = K.translation
        Bd = rot3(K).col[1]
        K3 = rot3(K)

        def at(phi):
            return compose(G, Matrix.Rotation(phi, 3, Bd) @ K3)

        def total(phi):
            Kp = at(phi)
            cr, pr = self.elbow_choice(pose, R_BONES, "R", Kp @ self.hand_from_K, c["elbow_r"])
            pl = None
            cost = cr
            if gl > 0.001:
                cl, pl = self.elbow_choice(pose, L_BONES, "L", self.left_hand(Kp, Hf_l, gl), c["elbow_l"])
                cost += gl * cl
            return cost + ROLL_HINT * 0.5 * (1.0 - math.cos(phi)), pr, pl
        ro = c["roll_opt"]
        if ro <= 0.0:
            self.roll_deg = 0.0
            self.roll_table = None
            _, pr, pl = total(0.0)
            return K, pr, pl
        if self.force_roll is not None:
            # segunda pasada de build_kaito: el giro ya elegido para todo el clip (sin saltos entre cuadros)
            phi = math.radians(self.force_roll) * min(1.0, ro)
            self.roll_deg = math.degrees(phi)
            _, pr, pl = total(phi)
            return at(phi), pr, pl
        step = math.radians(360.0 / ROLL_GRID)
        phis = [-math.pi + step * i for i in range(ROLL_GRID)]
        vals = [total(p)[0] for p in phis]
        self.roll_table = vals
        i = min(range(len(phis)), key=lambda k: vals[k])
        lo, hi = phis[i] - step, phis[i] + step
        gr = (math.sqrt(5.0) - 1.0) / 2.0
        x1, x2 = hi - gr * (hi - lo), lo + gr * (hi - lo)
        f1, f2 = total(x1)[0], total(x2)[0]
        for _ in range(9):
            if f1 < f2:
                hi, x2, f2 = x2, x1, f1
                x1 = hi - gr * (hi - lo)
                f1 = total(x1)[0]
            else:
                lo, x1, f1 = x1, x2, f2
                x2 = lo + gr * (hi - lo)
                f2 = total(x2)[0]
        mid = 0.5 * (lo + hi)
        phi = math.atan2(math.sin(mid), math.cos(mid)) * min(1.0, ro)
        self.roll_deg = math.degrees(phi)
        _, pr, pl = total(phi)
        return at(phi), pr, pl

    def clamp_hand(self, F, H3, S, amount=1.0):
        """Mano libre: si la muñeca pasa los topes de WRIST_LIMIT la mano vuelve hacia el antebrazo lo justo (y el
        giro sobre el antebrazo también). amount escala la corrección (manos que van y vienen de la empuñadura)."""
        if amount <= 0.0:
            return H3
        beta, bmax, _ = self.wrist_eval(F, H3, S, WRIST_LIMIT)
        out = H3
        if beta > bmax:
            ax = (H3 @ self.R0t[S]).col[1].cross(F.col[1])
            if ax.length > 1e-6:
                out = Matrix.Rotation(math.radians(beta - bmax) * amount, 3, ax.normalized()) @ out
        _, _, tau = self.wrist_eval(F, out, S, WRIST_LIMIT)
        lo, hi = self.twist_range(WRIST_LIMIT, S)
        if not lo <= tau <= hi:
            out = Matrix.Rotation(-math.radians(tau - max(lo, min(hi, tau))) * amount, 3, (out @ self.R0t[S]).col[1]) @ out
        return out

    def measure_wrist(self, pose, S):
        """(doblez, giro) en grados de la muñeca ya resuelta (para los chequeos)."""
        F = rot3(pose.get("Antebrazo." + S))
        H = rot3(pose.get("Mando." + S))
        beta, _, tau = self.wrist_eval(F, H, S, WRIST_LIMIT)
        return round(beta, 1), round(tau, 1)

    # ---------------------------------------------------------------- dedos
    def hand_shape(self, pose, side, fist_amt, seal=0.0, pinch=0.0, flat=0.0):
        """Dedos: el puño en 'fist_amt' y las formas de HAND_SHAPES encima (cada una 0..1)."""
        for n, q in self.fist[side].items():
            base = n.split(".")[0]
            t = max(0.0, min(1.0, fist_amt))
            for shape, amt in (("seal", seal), ("pinch", pinch), ("flat", flat)):
                if amt > 0.0:
                    t += (HAND_SHAPES[shape][base] - t) * min(1.0, amt)
            pose.place(n, pose.follow(n) @ qpow(q, t).to_matrix().to_4x4())

    # ---------------------------------------------------------------- piernas
    def ankle_for(self, c, s, S, sh):
        """Tobillo del pie 's' (con lo que avanzó el juego) y su giro, subido lo justo para que ninguna esquina de
        la suela quede bajo el piso: entre dos claves (tobillo en línea recta, giro por su curva) un pie que se para
        en punta hundía la punta 1-3 cm."""
        ank = V(c["foot_" + s]) + sh
        pr = c["foot_" + s + "_rot"]
        Rp = foot_rot(pr[0], pr[1], pr[2])
        A0 = ankle_rest(S)
        low = min((ank + Rp @ (P - A0)).z for P in sole_corners(S))
        if low < 0.0:
            ank = ank + Vector((0.0, 0.0, -low))
        return ank, Rp

    def kneel_drop(self, Hm, c, sh):
        """Cuánto más baja la pelvis para que las rodillas marcadas (kneel_r / kneel_l 0..1) apoyen en el piso."""
        R = self.rig
        extra = 0.0
        for B, s, S in ((R_BONES, "r", "R"), (L_BONES, "l", "L")):
            k = c.get("kneel_" + s) or 0.0
            if k <= 0.0:
                continue
            A, _ = self.ankle_for(c, s, S, sh)
            a, b = R.length[B["thigh"]], R.length[B["shin"]]

            def knee_z(dz):
                M = Hm.copy()
                M.translation.z -= dz
                J = (M @ R.rel[B["thigh"]]).translation
                return ik_mid(J, A, a, b, c["knee_" + s])[0].z
            lo, hi = 0.0, 0.9
            if knee_z(lo) <= KNEE_FLOOR_U:
                continue
            for _ in range(22):
                mid = 0.5 * (lo + hi)
                if knee_z(mid) > KNEE_FLOOR_U:
                    lo = mid
                else:
                    hi = mid
            extra = max(extra, k * hi)
        return extra

    # ---------------------------------------------------------------- pose completa
    def solve(self, pose, c):
        c = {**NEUTRAL, **{k: v for k, v in c.items() if v is not None}}
        R = self.rig
        # 'travel': lo que el juego ya movió el transform (lo clavado en el mundo se corre hacia atrás en el cuerpo);
        # 'lift': un salto (sube cadera y manos; los pies van en el mundo y el piso no se mueve)
        sh = Vector((0.0, c["travel"], 0.0))
        up = Vector((0.0, 0.0, c["lift"]))
        tr = c["tremble"]
        # ---- pelvis: baja lo justo para que los dos pies lleguen (y las rodillas que se arrodillan, al piso)
        rr = R.rest["Root"]
        Hm = compose(rr.translation + V(c["hips"]) + up, euler_q(c["hips_rot"]).to_matrix() @ rot3(rr))
        drop = 0.0
        for B, s in ((R_BONES, "r"), (L_BONES, "l")):
            J = (Hm @ R.rel[B["thigh"]]).translation
            A = V(c["foot_" + s]) + sh
            reach = (R.length[B["thigh"]] + R.length[B["shin"]]) * 0.985
            dxy = Vector((J.x - A.x, J.y - A.y)).length
            if dxy < reach:
                drop = max(drop, (J.z - A.z) - math.sqrt(reach * reach - dxy * dxy))
        if drop > 0.0:
            Hm.translation.z -= drop
        kd = self.kneel_drop(Hm, c, sh)
        Hm.translation.z -= kd
        self.hip_drop = drop + kd
        pose.place("Root", Hm)
        br = c["breath"]
        pose.delta("tronco", V(c["spine"]) + Vector((-2.5 * br, 0.0, 0.0)))
        pose.delta("cabeza", V(c["head"]) + Vector((1.5 * br, 0.0, 0.0)))
        pose.delta("Hombro.R", V(c["clav_r"]) + Vector((0.0, -2.0 * br, 0.0)))
        pose.delta("Hombro.L", V(c["clav_l"]) + Vector((0.0, 2.0 * br, 0.0)))
        # ---- brazos en el espacio del pecho ('arm_space' 0..1): con el tronco muy girado (dash, caídas) es más fácil
        # decir dónde van las manos respecto del pecho que del transform; 1 = las posiciones y direcciones de las
        # manos y la hoja se leen como si el pecho estuviera en reposo y lo siguen
        w = c.get("arm_space") or 0.0
        if w > 0.0:
            A = pose.get("tronco") @ R.rest_inv["tronco"]
            A3 = rot3(A)
            for k in ("grip", "hand_l", "hand_r"):
                c[k] = tuple(V(c[k]).lerp(A @ V(c[k]), w))
            for k in ("blade", "edge", "hand_l_dir", "hand_l_up", "hand_r_dir", "hand_r_up", "elbow_r", "elbow_l"):
                c[k] = tuple(NA.slerp_dir(V(c[k]), A3 @ V(c[k]), w))
        upw = up * (1.0 - w)                # con los brazos en el pecho el salto ya viene con el pecho
        # ---- mano izquierda libre (antes de la katana: la empuñadura a dos manos entra en el giro de la hoja)
        gl = c["grip_l"]
        hl = V(c["hand_l"]) + upw
        hl.z = max(hl.z, 0.12)
        Hf_l = compose(hl, basis_yz(c["hand_l_dir"], c["hand_l_up"]))
        # ---- brazo de la katana (temblor: la tensión de una espera, en el puño)
        g = V(c["grip"]) + upw + Vector((math.sin(tr * 37.0), math.cos(tr * 29.0), math.sin(tr * 23.0))) * (0.006 if tr else 0.0)
        g.z = max(g.z, 0.1)                 # el puño nunca atraviesa el piso
        K_auth = self.clear_floor(self.katana_frame(g, c["blade"], c["edge"]))
        fr = c["free_r"]
        if fr < 0.999:
            K, pole_r, pole_l = self.katana_roll(pose, K_auth, c, gl, Hf_l)
            Hr = K @ self.hand_from_K
        else:
            K, pole_r, pole_l, Hr = K_auth, c["elbow_r"], None, None
        if fr > 0.001:
            hr = V(c["hand_r"]) + upw
            hr.z = max(hr.z, 0.12)
            Hf_r = compose(hr, basis_yz(c["hand_r_dir"], c["hand_r_up"]))
            Hr = Hf_r if Hr is None else compose(Hr.translation.lerp(Hf_r.translation, fr),
                                                  Hr.to_quaternion().slerp(Hf_r.to_quaternion(), fr).to_matrix())
            _, pole_r = self.elbow_choice(pose, R_BONES, "R", Hr, c["elbow_r"])
        self.reach_with_clavicle(pose, R_BONES, Hr.translation)
        miss_r = pose.two_bone("Brazo.R", "Antebrazo.R", Hr.translation, pole_r)
        H3 = self.clamp_hand(rot3(pose.get("Antebrazo.R")), rot3(Hr), "R", fr)
        pose.place("Mando.R", compose(pose.tail("Antebrazo.R"), H3))
        pose.twist_follow("Antebrazo.R", "Mando.R", 0.5)
        self.hand_shape(pose, "R", 1.0 + (c["fist_r"] - 1.0) * fr, c["seal_r"] * fr, c["pinch_r"] * fr, c["flat_r"] * fr)
        # la katana en el puño con la empuñadura en diagonal (GRIP_TILT_DEG) o suelta: queda donde la dejan los
        # controles de la hoja (en el piso) y la mano se va sola
        Kc = pose.get("Mando.R") @ self.hand_from_K.inverted()
        kf = c["katana_free"]
        if kf > 0.001:
            Kc = compose(Kc.translation.lerp(K_auth.translation, kf), Kc.to_quaternion().slerp(K_auth.to_quaternion(), kf).to_matrix())
        pose.place("KatanaBone", Kc @ self.K_to_bone)
        # ---- mano libre / segunda mano en la empuñadura
        Hl = self.left_hand(Kc, Hf_l, gl)
        if pole_l is None:
            _, pole_l = self.elbow_choice(pose, L_BONES, "L", Hl, c["elbow_l"])
        self.reach_with_clavicle(pose, L_BONES, Hl.translation)
        miss_l = pose.two_bone("Brazo.L", "Antebrazo.L", Hl.translation, pole_l)
        H3 = self.clamp_hand(rot3(pose.get("Antebrazo.L")), rot3(Hl), "L", 1.0 - gl)
        pose.place("Mando.L", compose(pose.tail("Antebrazo.L"), H3))
        pose.twist_follow("Antebrazo.L", "Mando.L", 0.5)
        free_l = 1.0 - gl
        self.hand_shape(pose, "L", max(c["fingers_l"], gl), c["seal_l"] * free_l, 0.0, c["flat_l"] * free_l)
        self.wrist = {"R": self.measure_wrist(pose, "R"), "L": self.measure_wrist(pose, "L")}
        # ---- piernas
        miss_legs = 0.0
        for B, s, S in ((R_BONES, "r", "R"), (L_BONES, "l", "L")):
            ank, Rp = self.ankle_for(c, s, S, sh)
            Rf = Rp @ rot3(R.rest[B["foot"]])
            miss_legs = max(miss_legs, pose.two_bone(B["thigh"], B["shin"], ank, c["knee_" + s]))
            pose.place(B["foot"], compose(pose.tail(B["shin"]), Rf))
        self.misses = {"hand_r": miss_r, "hand_l": miss_l, "legs": miss_legs}
        return self.misses
