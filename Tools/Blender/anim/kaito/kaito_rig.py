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

MUÑECAS. El bind está bien (la mano a 5° del antebrazo) y los pesos de la muñeca reparten bien entre antebrazo y
mano: lo que quebraba las muñecas (70-160° en la guardia, la carrera y los cortes) era que la mano salía entera
de la hoja autorada (puño + dirección + filo) sin mirar el antebrazo. Ahora la hoja autorada dice hacia dónde
apunta y la mano elige, cuadro a cuadro y con un camino suave en todo el clip (build_kaito: arm_path), lo que
una mano de verdad puede hacer sin mover la hoja:
  * girar la katana sobre su propio eje (el filo autorado solo desempata, y pesa más en los cuadros de corte);
  * cuánto cruza la empuñadura la palma (0-36°: la diagonal del agarre japonés, del índice al talón de la mano);
  * girar el codo alrededor de la recta hombro-muñeca (hasta 45°: el codo autorado arma la silueta).
Lo que igual quede fuera de los topes de una muñeca (WRIST_LIMIT) se recorta en la mano y la hoja la sigue
(build_kaito mide cuánto se corrió la hoja: blade_fix).
"""
import math
import bpy
import numpy as np
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


# ------------------------------------------------------------------ muñecas
# Grados de la mano respecto de la mano NEUTRA (el antebrazo resuelto con el reposo de la mano), en su marco (medido
# en el bind: el brazo en cruz con la palma abajo): Y va de la muñeca a los dedos, +Z es el dorso (arriba en el bind)
# y el pulgar está en -X en la derecha (+X en la izquierda), adelante. flex + = hacia el dorso (extensión), - = hacia
# la palma; rad + = hacia el pulgar (radial), - = hacia el meñique (cubital); twist = giro de la mano sobre su eje
# (Pose.twist_follow pasa la mitad al antebrazo). El bind (brazo en cruz, palma abajo, el codo se dobla hacia
# adelante) es el antebrazo neutro: bajando el brazo queda la palma contra el muslo y el pulgar adelante, y doblando
# el codo, el apretón de manos (el agarre de la katana, pulgar arriba). Desde ahí prona y supina ~85° para cada lado
# (supinar es twist + en la derecha y - en la izquierda: los ejes están espejados). COMFORT: lo que una mano que
# agarra hace sin esfuerzo; LIMIT: lo que no pasa nunca (se recorta). Van por lado por si hace falta separarlos
_WRIST_C = {"flex": (-40.0, 40.0), "rad": (-25.0, 10.0), "twist": (-60.0, 60.0)}
_WRIST_L = {"flex": (-65.0, 65.0), "rad": (-38.0, 20.0), "twist": (-100.0, 100.0)}
WRIST_COMFORT = {"R": dict(_WRIST_C), "L": dict(_WRIST_C)}
WRIST_LIMIT = {"R": dict(_WRIST_L), "L": dict(_WRIST_L)}
# Fuera de los cuadros que cortan, la mano de la katana no pasa de lo cómodo más SOFT_MARGIN: lo que sobre lo corrige
# la muñeca y la hoja la sigue (en el paso de una clave a otra la hoja interpolada a veces pedía una muñeca
# imposible; nadie ve que la hoja se corra 15° a mitad de un gesto, sí una muñeca quebrada). En los cuadros que
# cortan manda la hoja autorada (su arco, la estela y el alcance) y vale el tope
SOFT_MARGIN = 10.0


def widened(margin):
    """Topes de muñeca = lo cómodo más 'margin' grados, por lado."""
    return {S: {k: (lo - margin, hi + margin) for k, (lo, hi) in WRIST_COMFORT[S].items()} for S in "RL"}


SOFT_LIMIT = widened(SOFT_MARGIN)


def opened_limits(w):
    """Topes de la mano izquierda suelta entre lo cómodo (w 0) y el tope de la muñeca (w 1)."""
    if w <= 0.0:
        return WRIST_COMFORT
    w = min(1.0, w)
    return {S: {k: tuple(a + (b - a) * w for a, b in zip(WRIST_COMFORT[S][k], WRIST_LIMIT[S][k])) for k in WRIST_COMFORT[S]}
            for S in "RL"}


def mix_limits(a, b, w):
    """Topes entre 'a' (w 0) y 'b' (w 1): la mano derecha que suelta o retoma la katana pasa de los de la katana a los
    de la mano libre sin saltar."""
    return {S: {k: tuple(x + (y - x) * w for x, y in zip(a[S][k], b[S][k])) for k in a[S]} for S in "RL"}


def cutting(clip, f):
    """¿El cuadro f está en un tramo en que la hoja corta (la ventana que pega, el impacto, el tajo) o al lado?"""
    t = clip.timing
    marks = [t[k] for k in ("contact", "strike") if k in t] + list(t.get("cut", ()))
    if any(abs(f - m) <= 1.0 for m in marks):
        return True
    if "active" in t:
        a, b = t["active"]
        return a - 1 <= f <= b + 1
    return False
# El brazo también gira sobre su eje en el hombro (rotación interna / externa): la IK lo hace al girar el polo. Con
# el brazo casi recto es lo único que cambia (la silueta no) y es la forma de enderezar la muñeca de un brazo que
# cuelga, pero más de ~45° retuerce la malla del hombro como un caramelo
SHOULDER_COMFORT, SHOULDER_LIMIT = (-45.0, 45.0), (-90.0, 90.0)
# grilla de la búsqueda (build_kaito elige el camino en ella y lo suaviza): giro de la hoja sobre su eje, diagonal
# del agarre y giro del codo alrededor de la recta hombro-muñeca (el de la mano izquierda, aparte)
ROLLS = tuple(-180.0 + 20.0 * k for k in range(18))
TILTS = (0.0, 15.0, 30.0, 45.0)
TILT_PREF = 30.0
SWIVELS = tuple(-180.0 + 20.0 * k for k in range(18))
SWIVELS_L = SWIVELS
# grados de codo girado que cuestan como 10° de muñeca fuera de lo cómodo, con el codo doblado SWIVEL_BEND o más (con
# el brazo casi recto el codo no se ve: casi no cuesta, lo cuida el giro del hombro)
SWIVEL_SCALE = 25.0
SWIVEL_BEND = 45.0
ROLL_SCALE = 30.0            # idem para el giro de la hoja (multiplicado por roll_weight: más en los cortes)
# fuera de los cuadros que cortan el filo autorado casi no se ve (una hoja de 2 cm de ancho desde 24 m) y es lo que
# decide hacia qué lado gira el antebrazo: pesando lo mismo que en un corte, el camino seguía el filo autorado aunque
# la muñeca tuviera que saltar de un tope al otro (de la guardia a la espalda en el iai)
ROLL_FREE = 0.35


def _excess(x, lo, hi):
    return np.maximum(0.0, lo - x) + np.maximum(0.0, x - hi)


def wrist_cost_np(flex, rad, tw, side):
    """Costo de una muñeca (arrays en grados): fuera de lo cómodo cuadrático, fuera del tope diez veces más, y un poco
    hacia la mano recta (entre dos giros parecidos, la muñeca más derecha)."""
    c = 0.0
    for v, k, s in ((flex, "flex", 10.0), (rad, "rad", 10.0), (tw, "twist", 15.0)):
        c = c + (_excess(v, *WRIST_COMFORT[side][k]) / s) ** 2 + 10.0 * (_excess(v, *WRIST_LIMIT[side][k]) / s) ** 2
    return c + 0.01 * ((flex / 10.0) ** 2 + (rad / 10.0) ** 2)


def wrist_soft_np(flex, rad, tw, side):
    """Costo de una mano LIBRE (sin la empuñadura): lo que pase de lo cómodo se recorta al resolver (clamp_hand), así
    que solo cuenta cuánto se va a apartar la mano de la autorada, sin el castigo del tope. Con el costo completo, una
    mano libre mal orientada entre dos claves arrastraba el codo a retorcer el hombro 150°."""
    c = 0.0
    for v, k in ((flex, "flex"), (rad, "rad"), (tw, "twist")):
        c = c + (_excess(v, *WRIST_COMFORT[side][k]) / 45.0) ** 2
    return c


def rodrigues(axis, angles):
    """Matrices (…, 3, 3) de giro alrededor de 'axis' (3,) por cada ángulo (radianes, cualquier forma)."""
    a = axis / np.linalg.norm(axis)
    K = np.array([[0.0, -a[2], a[1]], [a[2], 0.0, -a[0]], [-a[1], a[0], 0.0]])
    ang = np.asarray(angles, float)
    c, s = np.cos(ang)[..., None, None], np.sin(ang)[..., None, None]
    return c * np.eye(3) + s * K + (1.0 - c) * np.outer(a, a)


# Con el polo autorado casi sobre la recta hombro-muñeca (el brazo que apunta hacia donde dice el codo) la dirección
# del codo no está definida y daba vueltas entre cuadros (en el Interact el brazo se retorcía 130°): ahí se le suma un
# codo natural, atrás, afuera y abajo. Lo usan igual la búsqueda (numpy) y la pose (mathutils)
POLE_MIN = 0.4
ELBOW_FALLBACK = {"R": (-0.4, 0.5, -0.75), "L": (0.4, 0.5, -0.75)}


def stable_pole_np(pole, nd, side):
    """(polo perpendicular a nd normalizado, cuánto estaba definido 0..1) para polos (…, 3) y rectas nd (…, 3)."""
    p = _norm(np.broadcast_to(pole, nd.shape))
    P = p - nd * np.sum(p * nd, axis=-1, keepdims=True)
    m = np.linalg.norm(P, axis=-1, keepdims=True)
    fb = np.array(ELBOW_FALLBACK[side], float)
    fb = fb / np.linalg.norm(fb)
    Fb = _norm(fb - nd * np.sum(fb * nd, axis=-1, keepdims=True))
    return _norm(P + Fb * np.maximum(0.0, POLE_MIN - m)), np.clip(m[..., 0] / POLE_MIN, 0.0, 1.0)


def stable_pole(pole, nd, side):
    P, _ = stable_pole_np(np.array(V(pole)), np.array(V(nd).normalized()), side)
    return Vector(P)


def _norm(v):
    n = np.linalg.norm(v, axis=-1, keepdims=True)
    return v / np.maximum(n, 1e-9)


def mat_to_quat(M):
    """(…, 3, 3) -> (…, 4) w, x, y, z (Shepperd: estable para cualquier giro)."""
    m = M
    tr = m[..., 0, 0] + m[..., 1, 1] + m[..., 2, 2]
    cand = np.stack([tr, m[..., 0, 0], m[..., 1, 1], m[..., 2, 2]], axis=-1)
    i = np.argmax(cand, axis=-1)
    q = np.zeros(m.shape[:-2] + (4,))
    w = 0.5 * np.sqrt(np.maximum(1e-12, 1.0 + 2.0 * np.take_along_axis(cand, i[..., None], -1)[..., 0] - tr))
    s = 0.25 / w
    sel = [i == k for k in range(4)]
    q[..., 0] = np.where(sel[0], w, np.where(sel[1], (m[..., 2, 1] - m[..., 1, 2]) * s,
                                             np.where(sel[2], (m[..., 0, 2] - m[..., 2, 0]) * s, (m[..., 1, 0] - m[..., 0, 1]) * s)))
    q[..., 1] = np.where(sel[1], w, np.where(sel[0], (m[..., 2, 1] - m[..., 1, 2]) * s,
                                             np.where(sel[2], (m[..., 0, 1] + m[..., 1, 0]) * s, (m[..., 0, 2] + m[..., 2, 0]) * s)))
    q[..., 2] = np.where(sel[2], w, np.where(sel[0], (m[..., 0, 2] - m[..., 2, 0]) * s,
                                             np.where(sel[1], (m[..., 0, 1] + m[..., 1, 0]) * s, (m[..., 1, 2] + m[..., 2, 1]) * s)))
    q[..., 3] = np.where(sel[3], w, np.where(sel[0], (m[..., 1, 0] - m[..., 0, 1]) * s,
                                             np.where(sel[1], (m[..., 0, 2] + m[..., 2, 0]) * s, (m[..., 1, 2] + m[..., 2, 1]) * s)))
    return q * np.where(q[..., :1] < 0.0, -1.0, 1.0)


def quat_to_mat(q):
    w, x, y, z = (q[..., k] for k in range(4))
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)], -1),
                     np.stack([2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)], -1),
                     np.stack([2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)], -1)], -2)


def wrist_angles_np(R, side):
    """(flex, rad, twist) en grados de la mano relativa a la neutra R (…, 3, 3) (ver WRIST_COMFORT)."""
    y = R[..., :, 1]
    flex = np.degrees(np.arctan2(y[..., 2], y[..., 1]))
    rad = np.degrees(np.arctan2(-y[..., 0] if side == "R" else y[..., 0], y[..., 1]))
    tw = np.degrees(2.0 * np.arctan2(R[..., 0, 2] - R[..., 2, 0], 1.0 + R[..., 0, 0] + R[..., 1, 1] + R[..., 2, 2]))
    return flex, rad, (tw + 180.0) % 360.0 - 180.0


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


# ------------------------------------------------------------------ bandana
# El nudo de la bandana del cuerpo (slot AmarilloBandana, atrás de la cabeza) traía dos aletas rígidas pegadas a la
# cabeza: con las colas del kit (Kit_kaito_bandana.fbx, con física) se veían dos juegos de colas. Quedan solo las del
# kit, que nacen del nudo. El nudo era el aro de la cinta agrandado (un rombo hueco): de costado salía de la cabeza como
# un cuerno amarillo y por el agujero se veía la nuca. Ahora es un moño bajo y redondo: un nudo central octogonal y dos
# lazos cortos a los costados, que no sobresale más de KNOT_DEPTH de la cinta. Coordenadas del FBX importado en reposo
# (Kaito mira a +X, la nuca hacia -X), unidades del archivo (1 u = 0.53 m)
KNOT_FRONT_X = -0.54                   # caras de la bandana más atrás que esto: el nudo (los de la cinta quedan quietos)
KNOT_CENTER = (0.0, 2.43)              # (y, z) del centro del nudo, sobre la cinta de atrás
KNOT_DEPTH = 0.065                     # cuánto sobresale de la cinta (3.4 cm)
KNOT_R = (0.045, 0.04)                 # radio (ancho, alto) del nudo central
# lazos: (ancho hasta la punta, alto en la raíz y en la punta, cuánto sube la punta, espesor)
KNOT_LOOP = (0.115, 0.035, 0.065, 0.012, 0.04)


def bandana_knot(body, slot="AmarilloBandana"):
    """Rehace el nudo (idempotente: borra las caras del slot detrás de la cinta, sea el aro viejo o un moño anterior, y
    arma el moño de siempre). Devuelve (caras borradas, caras del moño)."""
    import bmesh
    mi = {i for i, s in enumerate(body.material_slots) if s.material and s.material.name.startswith(slot)}
    M = body.matrix_world
    bm = bmesh.new()
    bm.from_mesh(body.data)
    old = [f for f in bm.faces if f.material_index in mi and (M @ f.calc_center_median()).x < KNOT_FRONT_X]
    bmesh.ops.delete(bm, geom=old, context='FACES')
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    made = knot_bow(body, bm, min(mi), M) if mi else 0
    bm.to_mesh(body.data)
    bm.free()
    body.data.update()
    return len(old), made


def knot_bow(body, bm, mat, M):
    """Moño del nudo (caras planas, todo a la cabeza): un prisma octogonal que se angosta hacia atrás y dos lazos."""
    import bmesh
    Mi = M.inverted()
    vg = body.vertex_groups.get("cabeza")
    dl = bm.verts.layers.deform.verify()
    x0 = KNOT_FRONT_X - 0.002
    cy, cz = KNOT_CENTER

    def vert(x, y, z):
        v = bm.verts.new(Mi @ Vector((x, y, z)))
        if vg is not None:
            v[dl][vg.index] = 1.0
        return v

    faces = []

    def face(vs):
        f = bm.faces.new(vs)
        f.material_index = mat
        faces.append(f)

    def prism(front, back):
        """Une dos anillos de igual largo (adelante contra la cinta, atrás) con sus tapas."""
        n = len(front)
        for k in range(n):
            face([front[k], front[(k + 1) % n], back[(k + 1) % n], back[k]])
        face(front[::-1])
        face(back)

    ry, rz = KNOT_R
    ring = [(math.cos(math.radians(22.5 + 45.0 * k)), math.sin(math.radians(22.5 + 45.0 * k))) for k in range(8)]
    prism([vert(x0, cy + ry * c, cz + rz * s_) for c, s_ in ring],
          [vert(x0 - KNOT_DEPTH, cy + 0.8 * ry * c, cz + 0.8 * rz * s_) for c, s_ in ring])
    w, h0, h1, rise, th = KNOT_LOOP
    for sy in (-1.0, 1.0):
        # de la raíz (debajo del nudo central) a la punta, un poco más alta y más abierta: el lazo de un moño
        y0, y1 = cy + sy * ry * 0.6, cy + sy * w
        quad = [(y0, cz - h0 * 0.5), (y1, cz + rise - h1 * 0.5), (y1, cz + rise + h1 * 0.5), (y0, cz + h0 * 0.5)]
        if sy < 0:
            quad = quad[::-1]
        xf, xb = x0 - 0.008, x0 - 0.008 - th
        prism([vert(xf, y, z) for y, z in quad], [vert(xb, y, z) for y, z in quad])
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return len(faces)


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
    # solo el brazo izquierdo en el espacio del pecho (el que vale es el mayor de los dos): la katana sigue en el del
    # transform y la mano libre acompaña al tronco. En la frenada el pecho se echa atrás y adelante 30° y con la mano
    # fija en el transform el brazo pasaba de estirado a doblado del todo (99 % -> 15 % del largo) y el codo daba vuelta
    "arm_space_l": 0.0,
    # la katana suelta (Death: se le cae de la mano): 0 = en la mano, 1 = en su propia pose (puño, hoja y filo en el
    # mundo del clip, sin arm_space)
    "kat_free": 0.0, "kat_pos": tuple(GRIP_REST), "kat_blade": tuple(BLADE_REST), "kat_edge": tuple(EDGE_REST),
    # ...y la mano derecha, ya sin la katana, va como la izquierda libre (muñeca, dedos, dorso)
    "hand_r": (-0.5, -0.2, 1.1), "hand_r_dir": (-0.2, -0.4, -0.9), "hand_r_up": (-1.0, 0.0, 0.0),
    # dedos de la derecha suelta (< 0: los de siempre, medio cerrados): tomar un sahumerio, apoyar la palma
    "fingers_r": -1.0,
    # el cuerpo entero (cadera, brazos, katana y rodillas, NO los pies) girado 'turn' grados alrededor del origen y
    # corrido 'shift' (u): para un clip que arranca mirando a otro lado o desde otro lugar (EndingTurn empieza de
    # espaldas y medio metro atrás del transform) se escriben las poses de siempre y no hay que rotarlas a mano. Los
    # pies van aparte, en el mundo del clip: un pie apoyado no puede girar con el cuerpo
    "turn": 0.0, "shift": (0.0, 0.0, 0.0),
    # la mano izquierda suelta se recorta a lo cómodo (0) o hasta el tope (1): un empujón con la palma o una palma que
    # frena necesitan la muñeca bien doblada hacia el dorso (60°), que en un gesto común sería quebrarla
    "wrist_l_open": 0.0,
    # ...y la derecha suelta (kat_free): las palmas en el piso (empujarse para levantarse) piden la muñeca al tope
    "wrist_r_open": 0.0,
    # la mano izquierda suelta FLOJA (0..1): en 1 sigue al antebrazo con la muñeca recta, como la mano de un brazo que
    # se balancea; la orientación autorada deja de contar. Una mano autorada que no entra en lo cómodo queda en una
    # esquina del recorte, y un cambio chico de la autorada la pasaba a la esquina opuesta (80° en un cuadro: la
    # frenada salía de la carrera con la muñeca dando vuelta)
    "hand_l_relax": 0.0,
    # rodilla guiada (0..1): el polo de la rodilla deja de ser una dirección y pasa a ser la recta de la cadera a
    # 'knee_at_r/l' (dónde va la rodilla, en el mundo del clip como los pies, interpolado en arco entre claves). Una
    # dirección fija queda casi sobre la recta cadera-tobillo cuando el tobillo la cruza (la rodilla que baja al piso
    # desde una rodilla arriba: el pie de Kaito es más largo que su tibia, con el talón arriba el tobillo llega a la
    # altura de la cadera) y la rodilla saltaba de arriba a abajo en un cuadro (132°); el punto nunca está sobre la recta
    "knee_guide_r": 0.0, "knee_guide_l": 0.0,
}
# canales que 'turn' / 'shift' mueven (posiciones) y giran (direcciones)
TURN_POS = ("grip", "hand_l", "hand_r", "kat_pos")
TURN_DIR = ("blade", "edge", "elbow_r", "hand_l_dir", "hand_l_up", "elbow_l", "kat_blade", "kat_edge", "hand_r_dir",
            "hand_r_up", "knee_r", "knee_l")
# puntos de la mano (marco de Mando: Y a los dedos, +Z el dorso) que no pueden entrar en el piso: las puntas de los
# dedos abiertos, los nudillos y el talón de la palma del puño, y el pulgar (a cada lado: -X en la derecha, +X en la
# izquierda)
HAND_FLOOR_PTS = (Vector((0.0, 0.33, 0.0)), Vector((0.07, 0.30, 0.0)), Vector((-0.07, 0.30, 0.0)),
                  Vector((0.0, 0.24, -0.05)), Vector((0.0, 0.12, -0.07)), Vector((0.13, 0.14, -0.05)),
                  Vector((-0.13, 0.14, -0.05)), Vector((0.0, 0.29, -0.09)), Vector((0.07, 0.27, -0.09)),
                  Vector((-0.07, 0.27, -0.09)),
                  # la punta del pulgar abierto (4.6 cm debajo de la palma: con la palma en el piso se metía 2 cm)
                  Vector((0.16, 0.22, -0.09)), Vector((-0.16, 0.22, -0.09)))


def floor_raise(H, floor=0.03):
    """Cuánto subir (z) una mano H (marco del hueso) para que ningún punto de HAND_FLOOR_PTS quede bajo el piso."""
    return max(0.0, floor - min((H @ p).z for p in HAND_FLOOR_PTS))


def ik_mid(S, T, a, b, pole, reach=0.999):
    """Articulación del medio (codo) de una IK de dos huesos, con la misma cuenta que Pose.two_bone pero sin escribir
    la pose."""
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


class ArmFrame:
    """Lo que la IK del brazo necesita de un cuadro (el hombro ya resuelto), en numpy: para probar cientos de muñecas
    y polos a la vez con la misma cuenta que Pose.two_bone (la del antebrazo conserva su giro respecto del plano del
    codo del reposo)."""

    def __init__(self, rig, pose, B):
        Mu = pose.get(B["clav"]) @ rig.rel[B["ua"]]
        self.S = np.array(Mu.translation)
        Fu0 = rot3(Mu)
        Fl0 = Fu0 @ rot3(rig.rel[B["fa"]])
        u0, l0 = Fu0.col[1], Fl0.col[1]
        n0 = u0.cross(l0)
        if n0.length < 1e-6:
            n0 = u0.orthogonal()
        n0.normalize()
        fr0 = Matrix((l0, n0, l0.cross(n0))).transposed()
        self.Q = np.array(fr0.transposed() @ Fl0)
        self.Qu = np.array(Matrix((u0, n0, u0.cross(n0))) @ Fu0)
        self.Fu0t = np.array(Fu0.transposed())
        self.a, self.b = rig.length[B["ua"]], rig.length[B["fa"]]

    def forearm(self, W, poles):
        """Marcos (…, 3, 3) del antebrazo para muñecas W (…, 3) y polos (…, 3) (ya giradas, mismas formas)."""
        a, b = self.a, self.b
        dv = W - self.S
        dist = np.linalg.norm(dv, axis=-1, keepdims=True)
        nd = dv / np.maximum(dist, 1e-9)
        d = np.clip(dist, abs(a - b) + 1e-4, (a + b) * 0.999)
        cosA = np.clip((a * a + d * d - b * b) / (2.0 * a * d), -1.0, 1.0)
        sinA = np.sqrt(np.maximum(0.0, 1.0 - cosA * cosA))
        P = _norm(poles - nd * np.sum(poles * nd, axis=-1, keepdims=True))
        E = self.S + nd * (a * cosA) + P * (a * sinA)
        Tc = self.S + nd * d
        u = _norm(E - self.S)
        l = _norm(Tc - E)
        nn = _norm(np.cross(u, l))
        fr = np.stack([l, nn, np.cross(l, nn)], axis=-1)
        self.bend = np.degrees(np.arccos(np.clip(np.sum(u * l, axis=-1), -1.0, 1.0)))
        # giro del brazo en el hombro: el húmero respecto de su reposo colgado de la clavícula, sin el doblez
        Rs = self.Fu0t @ (np.stack([u, nn, np.cross(u, nn)], axis=-1) @ self.Qu)
        tw = np.degrees(2.0 * np.arctan2(Rs[..., 0, 2] - Rs[..., 2, 0], 1.0 + Rs[..., 0, 0] + Rs[..., 1, 1] + Rs[..., 2, 2]))
        self.shoulder = (tw + 180.0) % 360.0 - 180.0
        return fr @ self.Q

    def shoulder_cost(self):
        return ((_excess(self.shoulder, *SHOULDER_COMFORT) / 15.0) ** 2
                + 10.0 * (_excess(self.shoulder, *SHOULDER_LIMIT) / 15.0) ** 2)

    def swivel_cost(self, swivels_deg):
        """Costo de girar el codo (misma forma que los giros), según cuánto está doblado (ver SWIVEL_BEND) y cuánto
        decía el polo autorado (uno casi sobre la recta del brazo no dice nada)."""
        w = np.clip(np.sin(np.radians(self.bend)) / math.sin(math.radians(SWIVEL_BEND)), 0.03, 1.0)
        return w * self.pole_weight * (np.asarray(swivels_deg) / SWIVEL_SCALE) ** 2

    def swiveled(self, W, pole, swivels_deg, side):
        """Polos (misma forma que W): 'pole' estabilizado y girado alrededor de la recta hombro-muñeca por cada
        ángulo (giros con la forma de W sin el último eje)."""
        nd = _norm(W - self.S)
        P, self.pole_weight = stable_pole_np(pole, nd, side)
        Q = np.cross(nd, P)
        ang = np.radians(np.asarray(swivels_deg, float))[..., None]
        return P * np.cos(ang) + Q * np.sin(ang)


class Solver:
    """Controles -> pose de todos los huesos (nindo_anim.Pose en espacio C)."""

    def __init__(self, rig):
        self.rig = rig
        R = rig
        self.K_rest = compose(GRIP_REST, basis_yz(BLADE_REST, -EDGE_REST))
        self.K_to_bone = self.K_rest.inverted() @ R.rest["KatanaBone"]
        # la katana en el marco de la mano en el bind (un martillo: la hoja sale a 90° del eje de la mano) y el eje
        # sobre el que la diagonal del agarre la inclina hacia los dedos (por el centro del puño)
        self.Krel0 = R.rest_inv["Mando.R"] @ self.K_rest
        self.grip_in_hand_r = R.rest_inv["Mando.R"] @ GRIP_REST
        self.tilt_axis = rot3(self.Krel0).col[1].cross(Vector((0.0, 1.0, 0.0))).normalized()
        self._hfk = {}
        self.fist = {"R": fist("R"), "L": fist("L")}
        # la mano en reposo respecto de su antebrazo (5°): la mano neutra de cada cuadro es el antebrazo con esto
        self.R0 = {S: rot3(R.rest["Antebrazo." + S]).transposed() @ rot3(R.rest["Mando." + S]) for S in "RL"}
        self.R0np = {S: np.array(self.R0[S]) for S in "RL"}
        self.Kr3 = np.array(rot3(self.Krel0))
        self.Kt = np.array(self.Krel0.translation)
        self.gp = np.array(self.grip_in_hand_r)
        self.tilt_np = np.array(self.tilt_axis)
        self.misses = {}
        self.wrist = {}
        self.blade_fix = 0.0

    def hand_from_K(self, tilt):
        """La mano respecto de la katana con la empuñadura cruzada 'tilt' grados en la palma."""
        key = round(float(tilt), 4)
        h = self._hfk.get(key)
        if h is None:
            gp = self.grip_in_hand_r
            D = (Matrix.Translation(gp) @ Matrix.Rotation(math.radians(tilt), 4, self.tilt_axis)
                 @ Matrix.Translation(-gp))
            h = self._hfk[key] = (D @ self.Krel0).inverted()
        return h

    def katana_frame(self, grip, blade, edge):
        return compose(V(grip), basis_yz(blade, -V(edge)))

    def left_grip(self, K, tilt):
        """Mano izquierda en la empuñadura: espejo de la derecha respecto del plano de la hoja (los dos puños
        cierran igual), GRIP_L_OFF más cerca del pomo."""
        Hr = K @ self.hand_from_K(tilt)
        X = rot3(K).col[0]
        S = Matrix(((1 - 2 * X.x * X.x, -2 * X.x * X.y, -2 * X.x * X.z),
                    (-2 * X.y * X.x, 1 - 2 * X.y * X.y, -2 * X.y * X.z),
                    (-2 * X.z * X.x, -2 * X.z * X.y, 1 - 2 * X.z * X.z)))
        Rl = S @ rot3(Hr) @ Matrix.Diagonal((-1.0, 1.0, 1.0))
        g = K.translation - rot3(K).col[1] * GRIP_L_OFF
        off = Vector((-self.grip_in_hand_r.x, self.grip_in_hand_r.y, self.grip_in_hand_r.z))
        return compose(g - Rl @ off, Rl)

    def left_hand(self, K, Hf, gl, tilt):
        """La mano izquierda entre su pose libre (Hf) y la empuñadura (gl 0..1)."""
        if gl <= 0.001:
            return Hf
        Hg = self.left_grip(K, tilt)
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

    def tip(self, K):
        return K @ (self.K_rest.inverted() @ TIP_C_REST)

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

    def fingers(self, pose, side, amount):
        for n, q in self.fist[side].items():
            Q = Quaternion().slerp(q, max(0.0, min(1.0, amount)))
            pose.place(n, pose.follow(n) @ Q.to_matrix().to_4x4())

    # ---------------------------------------------------------------- muñecas
    def wrist_angles(self, F3, H3, side):
        """(flex, rad, twist) en grados de la mano H3 respecto del antebrazo F3 (matrices 3x3)."""
        Rr = np.array((F3 @ self.R0[side]).transposed() @ H3)
        return tuple(float(v) for v in wrist_angles_np(Rr, side))

    def shoulder_twist(self, pose, B):
        """Giro (grados) del húmero sobre su eje respecto de su reposo colgado de la clavícula (ver SHOULDER_COMFORT)."""
        Rs = np.array(rot3(pose.get(B["clav"]) @ self.rig.rel[B["ua"]]).transposed() @ rot3(pose.get(B["ua"])))
        tw = math.degrees(2.0 * math.atan2(Rs[0, 2] - Rs[2, 0], 1.0 + Rs[0, 0] + Rs[1, 1] + Rs[2, 2]))
        return (tw + 180.0) % 360.0 - 180.0

    def clamp_hand(self, F3, H3, side, amount=1.0, limits=WRIST_LIMIT):
        """La mano dentro de 'limits' (por lado): si pasa un tope, vuelve hacia la neutra lo justo (giro aparte del
        doblez). amount escala la corrección (una mano que va y viene de la empuñadura)."""
        if amount <= 0.0:
            return H3
        flex, rad, tw = self.wrist_angles(F3, H3, side)
        lim = limits[side]
        cl = lambda v, k: max(lim[k][0], min(lim[k][1], v))
        f2, r2, t2 = cl(flex, "flex"), cl(rad, "rad"), cl(tw, "twist")
        if (f2, r2, t2) == (flex, rad, tw):
            return H3
        sx = -1.0 if side == "R" else 1.0
        y = Vector((sx * math.tan(math.radians(r2)), 1.0, math.tan(math.radians(f2)))).normalized()
        Rn = Vector((0.0, 1.0, 0.0)).rotation_difference(y).to_matrix() @ Matrix.Rotation(math.radians(t2), 3, 'Y')
        N = F3 @ self.R0[side]
        Hc = N @ Rn
        if amount >= 1.0:
            return Hc
        return H3.to_quaternion().slerp(Hc.to_quaternion(), amount).to_matrix()

    def lift_tip(self, H, hfk, floor=0.04):
        """Giro (3x3) de la mano H (con su muñeca) que deja la punta de la katana sobre el piso: el tope de la muñeca
        puede bajar la hoja que la autorada (ya sobre el piso, clear_floor) tenía arriba. Gira sobre la muñeca, que
        ya está en el antebrazo."""
        tip_l = (self.K_rest.inverted() @ TIP_C_REST)
        tip = H @ hfk.inverted() @ tip_l
        if tip.z >= floor:
            return rot3(H)
        w = H.translation
        ax = (tip - w).cross(Vector((0.0, 0.0, 1.0)))
        if ax.length < 1e-6:
            return rot3(H)
        ax.normalize()
        lo, hi = 0.0, math.radians(60.0)
        for _ in range(16):
            mid = 0.5 * (lo + hi)
            if (w + Matrix.Rotation(mid, 3, ax) @ (tip - w)).z >= floor:
                hi = mid
            else:
                lo = mid
        return Matrix.Rotation(hi, 3, ax) @ rot3(H)

    def lift_hand(self, W, H3, floor=0.03):
        """Giro (3x3) de una mano H3 con la muñeca en W que deja sus dedos y su puño sobre el piso (una mano libre que
        se apoya: el recorte de la muñeca la podía girar hacia abajo y los dedos entraban 20 cm en el piso)."""
        pts = [W + H3 @ p for p in HAND_FLOOR_PTS]
        low = min(pts, key=lambda p: p.z)
        if low.z >= floor:
            return H3
        ax = (low - W).cross(Vector((0.0, 0.0, 1.0)))
        if ax.length < 1e-6:
            return H3
        ax.normalize()
        lo, hi = 0.0, math.radians(100.0)
        for _ in range(16):
            mid = 0.5 * (lo + hi)
            R = Matrix.Rotation(mid, 3, ax) @ H3
            if min((W + R @ p).z for p in HAND_FLOOR_PTS) >= floor:
                hi = mid
            else:
                lo = mid
        return Matrix.Rotation(hi, 3, ax) @ H3

    def context(self, pose, c, K):
        """Lo que la búsqueda de un cuadro necesita (después de body(): hombros, katana autorada, mano izquierda)."""
        ctx = {"K3": np.array(rot3(K)), "G": np.array(K.translation), "af": ArmFrame(self.rig, pose, R_BONES),
               "pole": np.array(V(c["elbow_r"])), "gl": c["grip_l"], "afl": ArmFrame(self.rig, pose, L_BONES),
               "pole_l": np.array(V(c["elbow_l"])), "relax_l": c.get("hand_l_relax") or 0.0}
        Hf = self.free_left(c)
        ctx["hf_t"], ctx["hf_q"] = np.array(Hf.translation), np.array(Hf.to_quaternion())
        # la derecha suelta (kat_free): el codo derecho se elige para su pose libre, no para la katana
        ctx["free"] = c.get("kat_free") or 0.0
        if ctx["free"] > 1e-3:
            Hr = self.free_right(c)
            ctx["hr_t"], ctx["hr_q"] = np.array(Hr.translation), np.array(Hr.to_quaternion())
        return ctx

    def hands_np(self, ctx, roll, tilt):
        """(katana girada, mano, muñeca) para giros de la hoja y diagonales del agarre (arrays de la misma forma)."""
        K3 = ctx["K3"]
        Kp = rodrigues(K3[:, 1], np.radians(roll)) @ K3
        Rt = rodrigues(self.tilt_np, np.radians(tilt))
        M3 = Rt @ self.Kr3
        Mt = (Rt @ (self.Kt - self.gp)[:, None])[..., 0] + self.gp
        hk3 = np.swapaxes(M3, -1, -2)
        hkt = -(hk3 @ Mt[..., None])[..., 0]
        return Kp, Kp @ hk3, ctx["G"] + (Kp @ hkt[..., None])[..., 0]

    def eval_right(self, ctx, roll, tilt, swivel):
        """Costo de la muñeca y el hombro derechos (y de la izquierda si está en la empuñadura) para cada estado
        (giro de la hoja, diagonal del agarre, giro del codo; arrays que se combinan). Sin el costo de girar la hoja
        (arm_path lo suma con el peso de cada cuadro)."""
        roll, tilt, swivel = np.broadcast_arrays(*(np.asarray(v, float) for v in (roll, tilt, swivel)))
        Kp, H3, W = self.hands_np(ctx, roll, tilt)
        fr = ctx["free"]
        if fr > 1e-3:
            # suelta (o soltándola): la mano va de la empuñadura a su pose libre, como en _arms
            W = W + (ctx["hr_t"] - W) * fr
            q0 = mat_to_quat(H3)
            q1 = np.broadcast_to(ctx["hr_q"], q0.shape)
            q1 = q1 * np.where(np.sum(q1 * q0, -1, keepdims=True) < 0.0, -1.0, 1.0)
            H3 = quat_to_mat(_norm(q0 + (q1 - q0) * fr))
        af = ctx["af"]
        F3 = af.forearm(W, af.swiveled(W, ctx["pole"], swivel, "R"))
        Rr = np.swapaxes(F3 @ self.R0np["R"], -1, -2) @ H3
        ang = wrist_angles_np(Rr, "R")
        self.last_ang = (*ang, af.shoulder)
        # la libre paga solo lo que le va a corregir el recorte (como la izquierda en eval_left)
        wrist = wrist_cost_np(*ang, "R") if fr <= 1e-3 else (1.0 - fr) * wrist_cost_np(*ang, "R") + fr * wrist_soft_np(*ang, "R")
        cost = wrist + af.swivel_cost(swivel) + af.shoulder_cost() + 0.5 * ((tilt - TILT_PREF) / 20.0) ** 2
        gl = ctx["gl"]
        if gl > 0.001:
            cost = cost + gl * self._left_grip_cost(ctx, Kp, H3, gl)
        return cost

    def _left_grip_cost(self, ctx, Kp, H3, gl):
        """El mejor costo de la muñeca izquierda en la empuñadura (o camino a ella) entre sus giros de codo."""
        X = Kp[..., :, 0]
        Sref = np.eye(3) - 2.0 * X[..., :, None] * X[..., None, :]
        Rl = Sref @ H3 @ np.diag((-1.0, 1.0, 1.0))
        g = ctx["G"] - Kp[..., :, 1] * GRIP_L_OFF
        off = np.array((-self.grip_in_hand_r.x, self.grip_in_hand_r.y, self.grip_in_hand_r.z))
        Wl = g - (Rl @ off[:, None])[..., 0]
        if gl < 0.999:
            Wl = ctx["hf_t"] + (Wl - ctx["hf_t"]) * gl
            q0 = ctx["hf_q"]
            q1 = mat_to_quat(Rl)
            q1 = q1 * np.where(np.sum(q1 * q0, -1, keepdims=True) < 0.0, -1.0, 1.0)
            Rl = quat_to_mat(_norm(q0 + (q1 - q0) * gl))
        sw = np.array(SWIVELS_L, float)
        Wk = np.broadcast_to(Wl[..., None, :], Wl.shape[:-1] + (len(sw), 3))
        swk = np.broadcast_to(sw, Wk.shape[:-1])
        af = ctx["afl"]
        F3 = af.forearm(Wk, af.swiveled(Wk, ctx["pole_l"], swk, "L"))
        Rr = np.swapaxes(F3 @ self.R0np["L"], -1, -2) @ Rl[..., None, :, :]
        cost = wrist_cost_np(*wrist_angles_np(Rr, "L"), "L") + af.swivel_cost(swk) + af.shoulder_cost()
        return cost.min(axis=-1)

    def survey_right(self, pose, c, K):
        """eval_right en toda la grilla: array (ROLLS, TILTS, SWIVELS)."""
        g = np.meshgrid(np.array(ROLLS), np.array(TILTS), np.array(SWIVELS), indexing="ij")
        return self.eval_right(self.context(pose, c, K), *g)

    def eval_left(self, ctx, Hl, swivels):
        """Costo de la muñeca y el hombro izquierdos (mano Hl ya decidida) por cada giro de codo. La mano en la
        empuñadura paga la muñeca completa; la libre, solo lo que la va a corregir el recorte (wrist_soft_np)."""
        af = ctx["afl"]
        sw = np.asarray(swivels, float)
        W = np.broadcast_to(np.array(Hl.translation), sw.shape + (3,))
        F3 = af.forearm(W, af.swiveled(W, ctx["pole_l"], sw, "L"))
        Rr = np.swapaxes(F3 @ self.R0np["L"], -1, -2) @ np.array(rot3(Hl))
        ang = wrist_angles_np(Rr, "L")
        gl = ctx["gl"]
        # (floja, la mano va hacia la recta: lo que queda de la autorada)
        k = 1.0 - ctx["relax_l"] * (1.0 - gl)
        if k < 1.0:
            ang = tuple(a * k for a in ang)
        self.last_ang_l = (*ang, af.shoulder)
        wrist = gl * wrist_cost_np(*ang, "L") + (1.0 - gl) * wrist_soft_np(*ang, "L")
        return wrist + af.swivel_cost(sw) + af.shoulder_cost()

    def swivel_pole(self, pose, B, target, pole, deg, side):
        """El polo del codo estabilizado (stable_pole) y girado 'deg' grados alrededor de la recta hombro-muñeca."""
        S = (pose.get(B["clav"]) @ self.rig.rel[B["ua"]]).translation
        nd = V(target) - S
        if nd.length < 1e-6:
            return V(pole)
        nd.normalize()
        P = stable_pole(pole, nd, side)
        return Matrix.Rotation(math.radians(deg), 3, nd) @ P if abs(deg) > 1e-6 else P

    # ---------------------------------------------------------------- pose completa
    def free_left(self, c):
        """La mano izquierda libre: sobre el piso con la orientación autorada (sube la muñeca lo que haga falta: un
        puño apoyado o una palma en el piso)."""
        hl = V(c["hand_l"]) + self._upw
        hl.z = max(hl.z, 0.12)
        B = basis_yz(c["hand_l_dir"], c["hand_l_up"])
        hl.z += floor_raise(compose(hl, B))
        return compose(hl, B)

    def free_right(self, c):
        """La mano derecha suelta (sin la katana), como la izquierda libre: sobre el piso con la orientación autorada."""
        hr = V(c["hand_r"]) + self._upw
        hr.z = max(hr.z, 0.12)
        B = basis_yz(c["hand_r_dir"], c["hand_r_up"])
        hr.z += floor_raise(compose(hr, B))
        return compose(hr, B)

    def body(self, pose, c):
        """Cadera, tronco, cabeza, hombros y la katana autorada (antes de los brazos). Devuelve (controles con los
        brazos ya en el espacio del pecho, katana autorada)."""
        c = {**NEUTRAL, **{k: v for k, v in c.items() if v is not None}}
        R = self.rig
        turn, shift = c["turn"] or 0.0, V(c["shift"])
        if abs(turn) > 1e-6 or shift.length > 1e-6:
            Rz = Matrix.Rotation(math.radians(turn), 3, 'Z')
            c["hips"] = tuple(Rz @ V(c["hips"]) + shift)
            hr = c["hips_rot"]
            c["hips_rot"] = (hr[0], hr[1], hr[2] + turn)
            for k in TURN_POS:
                c[k] = tuple(Rz @ V(c[k]) + shift)
            for k in TURN_DIR:
                c[k] = tuple(Rz @ V(c[k]))
        # 'travel': lo que el juego ya movió el transform (lo clavado en el mundo se corre hacia atrás en el cuerpo);
        # 'lift': un salto (sube cadera y manos; los pies van en el mundo y el piso no se mueve)
        sh = Vector((0.0, c["travel"], 0.0))
        up = Vector((0.0, 0.0, c["lift"]))
        tr = c["tremble"]
        # ---- pelvis: baja lo justo para que los dos pies lleguen
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
        self.hip_drop = drop
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
        wl = max(w, c.get("arm_space_l") or 0.0)
        if wl > 0.0:
            A = pose.get("tronco") @ R.rest_inv["tronco"]
            A3 = rot3(A)
            for k in ("grip", "hand_l", "hand_r"):
                u = wl if k == "hand_l" else w
                c[k] = tuple(V(c[k]).lerp(A @ V(c[k]), u))
            for k in ("blade", "edge", "hand_l_dir", "hand_l_up", "hand_r_dir", "hand_r_up", "elbow_r", "elbow_l"):
                u = wl if k in ("hand_l_dir", "hand_l_up", "elbow_l") else w
                c[k] = tuple(NA.slerp_dir(V(c[k]), A3 @ V(c[k]), u))
        self._upw = up * (1.0 - w)          # con los brazos en el pecho el salto ya viene con el pecho
        # ---- katana autorada (temblor: la tensión de una espera, en el puño)
        g = V(c["grip"]) + self._upw + Vector((math.sin(tr * 37.0), math.cos(tr * 29.0), math.sin(tr * 23.0))) * (0.006 if tr else 0.0)
        g.z = max(g.z, 0.1)                 # el puño nunca atraviesa el piso
        return c, self.clear_floor(self.katana_frame(g, c["blade"], c["edge"]))

    def best_right(self, pose, c, K):
        """(giro, diagonal, codo) del mejor punto de la grilla en este cuadro (con el peso base del filo)."""
        cost = self.survey_right(pose, c, K) + roll_cost(1.0)[:, None, None]
        i, j, k = np.unravel_index(int(np.argmin(cost)), cost.shape)
        return ROLLS[i], TILTS[j], SWIVELS[k]

    def solve(self, pose, c, state=None, limits=WRIST_LIMIT):
        """state = (giro de la hoja, diagonal del agarre, codo derecho, codo izquierdo) en grados; sin él (o con
        None en algún lugar) el mejor de la grilla en este cuadro (build_kaito pasa el camino suave de todo el clip).
        limits: topes de la mano de la katana (SOFT_LIMIT fuera de los cuadros que cortan: ver cutting)."""
        c, K_auth = self.body(pose, c)
        self.c = c
        if state is None or state[0] is None:
            roll, tilt, sw_r = self.best_right(pose, c, K_auth)
            sw_l = None if state is None else state[3]
        else:
            roll, tilt, sw_r, sw_l = state
        self._arms(pose, c, K_auth, roll, tilt, sw_r, sw_l, limits)
        self._legs(pose, c)
        return self.misses

    def _arms(self, pose, c, K_auth, roll, tilt, sw_r, sw_l, limits):
        R = self.rig
        # ---- brazo de la katana: la hoja girada sobre su eje (por el puño: la hoja no se mueve), la empuñadura
        # cruzada en la palma y el codo girado; lo que la muñeca no pueda, se recorta y la katana sigue a la mano
        Bd = rot3(K_auth).col[1]
        K = compose(K_auth.translation, Matrix.Rotation(math.radians(roll), 3, Bd) @ rot3(K_auth))
        hfk = self.hand_from_K(tilt)
        Hr = K @ hfk
        free = c.get("kat_free") or 0.0
        if free > 1e-3:
            # suelta la katana: la mano va de donde la tenía a su pose libre (como la izquierda)
            Hf = self.free_right(c)
            Hr = compose(Hr.translation.lerp(Hf.translation, free), Hr.to_quaternion().slerp(Hf.to_quaternion(), free).to_matrix())
        # el giro del codo del camino (arm_path) ya es el de la mano que toca: con la katana o suelta (eval_right). Antes
        # la suelta iba con el codo autorado y la muñeca quedaba en el recorte todo el rezo (radial 20°, dorso 50°)
        pole_r = self.swivel_pole(pose, R_BONES, Hr.translation, c["elbow_r"], sw_r, "R")
        self.reach_with_clavicle(pose, R_BONES, Hr.translation)
        miss_r = pose.two_bone("Brazo.R", "Antebrazo.R", Hr.translation, pole_r)
        F_r = rot3(pose.get("Antebrazo.R"))
        self.wrist_raw = self.wrist_angles(F_r, rot3(Hr), "R")
        # suelta, la derecha se recorta como la izquierda libre (a lo cómodo, o más con wrist_r_open): con los topes de la
        # katana (lo cómodo + SOFT_MARGIN) la mano en el muslo o en el gassho quedaba 20° quebrada hacia el pulgar
        lim_r = limits if free <= 1e-3 else mix_limits(limits, opened_limits(c["wrist_r_open"]), free)
        Hc = compose(Hr.translation, self.clamp_hand(F_r, rot3(Hr), "R", 1.0, lim_r))
        H3 = self.lift_tip(Hc, hfk)
        if free > 1e-3:
            # suelta: la punta de la katana deja de contar y la que no entra en el piso es la mano
            H3 = H3.to_quaternion().slerp(self.lift_hand(pose.tail("Antebrazo.R"), rot3(Hc)).to_quaternion(), free).to_matrix()
        pose.place("Mando.R", compose(pose.tail("Antebrazo.R"), H3))
        wr = self.wrist_angles(F_r, H3, "R")
        pose.twist_follow("Antebrazo.R", "Mando.R", 0.5)
        fr = c["fingers_r"]
        self.fingers(pose, "R", (1.0 - free) + free * (fr if fr >= 0.0 else 0.4))
        Kc = pose.get("Mando.R") @ hfk.inverted()
        # (suelta, la hoja autorada ya no dice nada: no cuenta)
        self.blade_fix = math.degrees(rot3(Kc).col[1].angle(Bd, 0.0)) if free < 0.5 else 0.0
        if free > 1e-3:
            # se le cae: de la mano a su propia pose (en el piso, después del golpe y el rebote que autora el clip;
            # la punta nunca entra en el piso)
            Kf = self.clear_floor(self.katana_frame(V(c["kat_pos"]), c["kat_blade"], c["kat_edge"]))
            Kc = compose(Kc.translation.lerp(Kf.translation, free), Kc.to_quaternion().slerp(Kf.to_quaternion(), free).to_matrix())
            # entre la mano y el piso (apoyarla, levantarla) el giro intermedio podía hundir la punta
            if free < 0.999:
                Kc = self.clear_floor(Kc)
        pose.place("KatanaBone", Kc @ self.K_to_bone)
        self.katana = Kc
        # ---- mano libre / segunda mano en la empuñadura (su codo, el mejor si no viene decidido)
        gl = c["grip_l"]
        Hl = self.left_hand(Kc, self.free_left(c), gl, tilt)
        if sw_l is None:
            sw_l = SWIVELS_L[int(np.argmin(self.eval_left(self.context(pose, c, Kc), Hl, np.array(SWIVELS_L))))]
        pole_l = self.swivel_pole(pose, L_BONES, Hl.translation, c["elbow_l"], sw_l, "L")
        self.reach_with_clavicle(pose, L_BONES, Hl.translation)
        miss_l = pose.two_bone("Brazo.L", "Antebrazo.L", Hl.translation, pole_l)
        F_l = rot3(pose.get("Antebrazo.L"))
        relax = (c.get("hand_l_relax") or 0.0) * (1.0 - gl)
        Hl3 = rot3(Hl)
        if relax > 1e-3:
            Hl3 = Hl3.to_quaternion().slerp((F_l @ self.R0["L"]).to_quaternion(), relax).to_matrix()
        H3l = self.clamp_hand(F_l, Hl3, "L", 1.0 - gl, opened_limits(c["wrist_l_open"]))
        if gl < 0.999:
            H3l = self.lift_hand(pose.tail("Antebrazo.L"), H3l)
        pose.place("Mando.L", compose(pose.tail("Antebrazo.L"), H3l))
        wl = self.wrist_angles(F_l, H3l, "L")
        pose.twist_follow("Antebrazo.L", "Mando.L", 0.5)
        self.fingers(pose, "L", max(c["fingers_l"], gl))
        self.wrist = {"R": wr, "L": wl}
        self.shoulder = {"R": self.shoulder_twist(pose, R_BONES), "L": self.shoulder_twist(pose, L_BONES)}
        self.state = (roll, tilt, sw_r, sw_l)
        self.misses = {"hand_r": miss_r, "hand_l": miss_l}

    def _legs(self, pose, c):
        R = self.rig
        sh = Vector((0.0, c["travel"], 0.0))
        miss_legs = 0.0
        for B, s, S in ((R_BONES, "r", "R"), (L_BONES, "l", "L")):
            ank = V(c["foot_" + s]) + sh
            pr = c["foot_" + s + "_rot"]
            Rp = foot_rot(pr[0], pr[1], pr[2])
            Rf = Rp @ rot3(R.rest[B["foot"]])
            # ninguna esquina de la suela bajo el piso: entre dos claves (tobillo en línea recta, giro por su
            # curva) un pie que se para en punta hundía la punta 1-3 cm; el tobillo sube lo justo
            A0 = ankle_rest(S)
            low = min((ank + Rp @ (P - A0)).z for P in sole_corners(S))
            if low < 0.0:
                ank = ank + Vector((0.0, 0.0, -low))
            pole = V(c["knee_" + s]).normalized()
            w = c.get("knee_guide_" + s) or 0.0
            if w > 1e-3 and c.get("knee_at_" + s) is not None:
                hip = pose.head(B["thigh"]) if B["thigh"] in pose.W else pose.follow(B["thigh"]).translation
                to = V(c["knee_at_" + s]) + sh - hip
                if to.length > 1e-6:
                    pole = pole.lerp(to.normalized(), w)
            miss_legs = max(miss_legs, pose.two_bone(B["thigh"], B["shin"], ank, pole))
            pose.place(B["foot"], compose(pose.tail(B["shin"]), Rf))
        self.misses["legs"] = miss_legs


def frame_limits(clip, f):
    """Topes de la mano de la katana en el cuadro f del clip (ver SOFT_MARGIN)."""
    return WRIST_LIMIT if cutting(clip, f) else SOFT_LIMIT


def roll_cost(weight):
    """Costo (ROLLS,) de girar la hoja sobre su eje respecto del filo autorado, con el peso del cuadro."""
    return weight * (np.array(ROLLS) / ROLL_SCALE) ** 2


# ------------------------------------------------------------------ camino suave de un clip
# Costo por (10°)² de cambio entre dos cuadros del juego: sin esto el mejor de cada cuadro saltaba entre dos mínimos
# parecidos (la mano daba media vuelta en 33 ms)
# (el codo izquierdo cuesta más: su mano libre cambia de dirección de golpe entre claves y con el brazo casi recto el
# giro del codo es barato, así que saltaba 100° en un cuadro)
STEP_COST = {"roll": 0.6, "tilt": 0.6, "swivel": 0.8, "swivel_l": 1.2}
# ...salvo cuando la mano autorada ya se mueve mucho en ese cuadro (un golpe que la sacude, un tajo): ahí un giro de
# la mano queda escondido en el gesto. Grados de hoja (o de mano libre) + cm de puño por cuadro del juego en los que
# el costo del cambio baja a la mitad. Sin esto el camino se quedaba pegado al cuadro fijo del principio (la guardia)
# en los golpes que llegan de un cuadro al otro y la muñeca pasaba 2-4 cuadros contra el tope
STEP_EASE = 20.0
# ...pero con el costo abaratado el camino igual daba media vuelta en un cuadro donde la mano autorada se movía mucho (el
# codo 127° en el primer cuadro del Corte final, la hoja 180° sobre su eje justo al llegar al zanshin, con la cámara
# encima): un giro por cuadro del juego más grande que STEP_CAP se ve siempre, por rápido que vaya el gesto. Pasado el
# tope cada 10° cuestan CAP_PENALTY (no es infinito: entre dos cuadros fijos muy distintos el camino tiene que existir).
# En los cuadros que cortan el tope se estira (CAP_SMEAR: la estela tapa la mano) y en un corte de cámara del clip
# ('cut', el teletransporte del remate) no hay tope
STEP_CAP = {"roll": 40.0, "tilt": None, "swivel": 35.0, "swivel_l": 35.0}
CAP_SMEAR = 1.8
CAP_PENALTY = 60.0
# ...y lo mismo para la muñeca que resulta de cada estado: la grilla puede ir suave y la mano igual dar media vuelta
# respecto del antebrazo (una hoja que pasa de adelante a la espalda con la muñeca contra el tope, que el recorte
# llevaba al tope opuesto de un cuadro al otro), o el húmero girar 100° (la manga se retuerce). Doblez y giro de la
# muñeca y giro del hombro, grados por cuadro del juego
WRIST_STEP_CAP = 30.0


def step_caps(clip):
    """(n + 1,) multiplicador del tope de cambio entre f-1 y f (ver STEP_CAP); el primero no se usa."""
    n = clip.frames
    out = np.ones(n + 1)
    cuts = list(clip.timing.get("cut", ()))
    # el cuadro en que lo golpean ('impact' de los golpes recibidos y los desvíos) es un sacudón de un cuadro: ahí el
    # brazo libre vuela y el codo tiene que poder seguirlo (con tope, el hombro se retorcía 130°)
    if "impact" in clip.timing:
        cuts.append(clip.timing["impact"])
    # ...y el cuadro en que sale disparado ('burst': el Corte del Viento pasa de la carga del iai al vuelo del dash, que el
    # juego mueve a 56 m/s): los brazos cambian de pose de golpe y con tope el hombro izquierdo se retorcía 125°
    cuts += list(clip.timing.get("burst", ()))
    for f in range(1, n + 1):
        if any(f - 1 < c <= f + 1e-6 for c in cuts):
            out[f] = np.inf
        elif cutting(clip, f) or cutting(clip, f - 1):
            out[f] = CAP_SMEAR
    return out


def cap_cost(dv_deg, cap, mul, time_scale=1.0):
    """Castigo de un cambio por cuadro del juego que pasa el tope 'cap' x 'mul' (grados; arrays)."""
    if cap is None or not np.isfinite(mul):
        return 0.0
    over = np.maximum(0.0, np.abs(dv_deg) * time_scale - cap * mul)
    return CAP_PENALTY * (over / 10.0) ** 2


def step_ease(dirs, pts, time_scale=1.0):
    """(n,) multiplicador del costo de cambio entre f-1 y f (ver STEP_EASE) a partir de las direcciones (n, 3) y
    posiciones (n, 3, unidades) autoradas de la mano en cada cuadro; el primero no se usa."""
    d = _norm(np.asarray(dirs, float))
    ang = np.degrees(np.arccos(np.clip(np.sum(d[1:] * d[:-1], axis=-1), -1.0, 1.0)))
    cm = np.linalg.norm(np.diff(np.asarray(pts, float), axis=0), axis=-1) * M_PER_U * 100.0
    m = (ang + cm) * time_scale
    return np.concatenate([[1.0], 1.0 / (1.0 + (m / STEP_EASE) ** 2)])


def _wrap(d):
    return (d + 180.0) % 360.0 - 180.0


def _axis_dv(vals, wrap):
    v = np.asarray(vals, float)
    dv = v[:, None] - v[None, :]
    return _wrap(dv) if wrap else dv


def dp_path(local, axes, pins, time_scale=1.0, ease=None, caps=None, wrist=None):
    """Camino por la grilla que minimiza la suma de los costos de cada cuadro más el de cambiar entre cuadros
    (programación dinámica). local: (n, *forma de la grilla); axes: [(valores, costo por (10°)², da la vuelta[, tope
    por cuadro])] por eje; pins: {cuadro: índice plano} que quedan fijos (los empalmes con otros clips: el mismo cuadro
    tiene que salir igual en los dos); ease: (n,) multiplicador del costo de cambio de f-1 a f (step_ease); caps: (n,)
    multiplicador del tope de cada eje (step_caps; el castigo del tope no se abarata con ease); wrist: (n, 3, celdas)
    doblez y giro de la muñeca y giro del hombro de cada celda en cada cuadro (el cambio por cuadro que pasa WRIST_STEP_CAP también se
    castiga). Devuelve los valores (n, ejes) suavizados ([1 2 1] dos veces, salvo los fijos)."""
    n = local.shape[0]
    ease = np.ones(n) if ease is None else ease
    caps = np.ones(n) if caps is None else caps
    shape = local.shape[1:]
    flat = local.reshape(n, -1).astype(float).copy()
    nax = len(axes)

    def axis_sum(fn):
        T = 0.0
        for d, ax in enumerate(axes):
            c = fn(d, ax)
            if np.isscalar(c):
                continue
            sh = [1] * (2 * nax)
            sh[d], sh[nax + d] = c.shape[0], c.shape[1]
            T = T + c.reshape(sh)
        if np.isscalar(T):
            return 0.0
        return np.broadcast_to(T, shape + shape).reshape(flat.shape[1], flat.shape[1])
    T = axis_sum(lambda d, ax: ax[1] * time_scale * time_scale * (_axis_dv(ax[0], ax[2]) / 10.0) ** 2)
    pen = {}

    def penalty(mul):
        key = float(mul)
        if key not in pen:
            pen[key] = axis_sum(lambda d, ax: cap_cost(_axis_dv(ax[0], ax[2]), ax[3] if len(ax) > 3 else None, mul, time_scale)
                                if len(ax) > 3 and ax[3] is not None and np.isfinite(mul) else 0.0)
        return pen[key]
    for f, i in pins.items():
        keep = flat[f, i]
        flat[f, :] = np.inf
        flat[f, i] = keep
    cost = flat[0].copy()
    back = np.zeros((n, flat.shape[1]), dtype=np.int64)
    for f in range(1, n):
        tot = cost[:, None] + T * ease[f] + penalty(caps[f])
        if wrist is not None and np.isfinite(caps[f]):
            for k in range(len(wrist[f])):
                tot = tot + cap_cost(_wrap(wrist[f][k][None, :] - wrist[f - 1][k][:, None]), WRIST_STEP_CAP, caps[f], time_scale)
        back[f] = np.argmin(tot, axis=0)
        cost = tot[back[f], np.arange(flat.shape[1])] + flat[f]
    idx = [int(np.argmin(cost))]
    for f in range(n - 1, 0, -1):
        idx.append(int(back[f][idx[-1]]))
    idx = idx[::-1]
    out = np.array([[axes[d][0][k] for d, k in enumerate(np.unravel_index(i, shape))] for i in idx], float)
    for d, ax in enumerate(axes):
        wrap = ax[2]
        col = out[:, d]
        if wrap:
            col = np.concatenate([[col[0]], col[0] + np.cumsum(_wrap(np.diff(col)))])
        for _ in range(2):
            prev = col.copy()
            for f in range(1, n - 1):
                if f not in pins:
                    col[f] = 0.25 * prev[f - 1] + 0.5 * prev[f] + 0.25 * prev[f + 1]
        out[:, d] = _wrap(col) if wrap else col
    return out


def pinned_frames(clip):
    """Cuadros que salen igual en dos clips (el primero, el último y los empalmes de kaito_clips.CHAINS)."""
    import kaito_clips as KC
    out = {0, clip.frames}
    for a, fa, b, fb_, _ in KC.CHAINS:
        if a == clip.name:
            out.add(clip.frames if fa < 0 else fa)
        if b == clip.name:
            out.add(fb_)
    return sorted(out)


def chain_targets(clip):
    """{cuadro de este clip: (clip con el que empalma, su cuadro)} para los empalmes en que este clip es
    el que termina (kaito_clips.CHAINS): ese cuadro toma el estado de brazos del otro. Con su mejor estado propio, dos
    poses casi iguales (la caída del dash y la guardia del Corte 1) elegían codos distintos y el fundido corto del
    código los hacía saltar 40°."""
    import kaito_clips as KC
    by = {c.name: c for c in KC.CLIPS}
    out = {}
    for a, fa, b, fb_, _ in KC.CHAINS:
        if a == clip.name and b in by:
            out[clip.frames if fa < 0 else fa] = (by[b], fb_)
    return out


def refine_path(evalf, path, pins, axes, time_scale=1.0, ease=None, sweeps=4, steps=(-10.0, -5.0, -2.5, 2.5, 5.0, 10.0),
                caps=None):
    """Pulido continuo del camino de dp_path: cuadro a cuadro y eje por eje, el valor cercano que minimiza el costo
    del cuadro más el de cambiar respecto de los vecinos. Entre dos puntos de la grilla el costo no siempre es suave
    (promediar dos estados buenos podía caer en uno malo: el brazo retorcido del Interact). evalf(f, estados (m, ejes))
    -> costos (m,)."""
    out = np.array(path, float)
    n = out.shape[0]
    ease = np.ones(n) if ease is None else ease
    caps = np.ones(n) if caps is None else caps
    st = np.array((0.0,) + tuple(steps))
    for sweep in range(sweeps):
        for f in (range(n) if sweep % 2 == 0 else range(n - 1, -1, -1)):
            if f in pins:
                continue
            for d, ax in enumerate(axes):
                vals, w, wrap = ax[:3]
                cap = ax[3] if len(ax) > 3 else None
                cand = np.repeat(out[f][None, :], len(st), axis=0)
                cand[:, d] = out[f, d] + st
                if wrap:
                    cand[:, d] = _wrap(cand[:, d])
                else:
                    cand[:, d] = np.clip(cand[:, d], min(vals), max(vals))
                cost = evalf(f, cand)
                for g in (f - 1, f + 1):
                    if 0 <= g < n:
                        dv = cand[:, d] - out[g, d]
                        dv = _wrap(dv) if wrap else dv
                        cost = cost + w * ease[max(f, g)] * time_scale * time_scale * (dv / 10.0) ** 2
                        cost = cost + cap_cost(dv, cap, caps[max(f, g)], time_scale)
                out[f] = cand[int(np.argmin(cost))]
    return out


# estados de brazos de cada clip ya resuelto (las frenadas copian los de Run mientras siguen la carrera)
PATHS = {}


def _nearest(vals, v, wrap):
    d = np.asarray(vals, float) - v
    return int(np.argmin(np.abs(_wrap(d) if wrap else d)))


def follow_states(rig, solver, clip):
    """{cuadro: estado} que el clip copia de otro (timing 'arm_follow' = [clip, [[cuadro, cuadro del otro], ...]]): con
    los mismos brazos autorados, el camino propio de la frenada ya elegía otro codo para el apoyo que viene y el brazo
    izquierdo se separaba 40-50° del de la carrera en el segundo cuadro."""
    fl = clip.timing.get("arm_follow")
    if not fl:
        return {}
    import kaito_clips as KC
    if fl[0] not in PATHS:
        arm_path(rig, solver, next(c for c in KC.CLIPS if c.name == fl[0]))
    return {int(j): PATHS[fl[0]][int(k)] for j, k in fl[1]}


def arm_path(rig, solver, clip):
    """(giro de la hoja, diagonal del agarre, codo derecho, codo izquierdo) por cuadro: el camino suave de menor costo
    de muñecas y hombros de todo el clip (dp_path en la grilla y refine_path). El filo autorado pesa más cuanto más
    rápido va la punta (en un corte el filo va adelante); los cuadros de empalme quedan en su mejor punto propio con
    el peso base, así salen iguales en los dos clips; los de 'arm_follow', en el estado del otro clip."""
    follow = follow_states(rig, solver, clip)
    n = clip.frames
    ts = clip.timing.get("time_scale", 1.0)
    grid = np.meshgrid(np.array(ROLLS), np.array(TILTS), np.array(SWIVELS), indexing="ij")
    ctxs, base, tips, wr = [], [], [], []
    for f in range(n + 1):
        pose = NA.Pose(rig)
        c, K = solver.body(pose, clip.controls(f))
        ctx = solver.context(pose, c, K)
        ctxs.append(ctx)
        base.append(solver.eval_right(ctx, *grid))
        wr.append(np.stack([np.broadcast_to(solver.last_ang[k], grid[0].shape).ravel() for k in (0, 2, 3)]))
        tips.append(solver.tip(K))
    base = np.array(base)
    weight = []
    for f in range(n + 1):
        a, b = max(0, f - 1), min(n, f + 1)
        v = (tips[b] - tips[a]).length * M_PER_U * NA.FPS * ts / max(1, b - a)
        weight.append((1.0 + min(1.0, v / 8.0)) * (1.0 if cutting(clip, f) else ROLL_FREE))
    local = base + np.array([roll_cost(w) for w in weight])[:, :, None, None]
    pins = {f: int(np.argmin(base[f] + roll_cost(1.0)[:, None, None])) for f in pinned_frames(clip)}
    targets = chain_targets(clip)
    tgt_ctx = {}
    for f, (tclip, tf) in targets.items():
        pose = NA.Pose(rig)
        c, K = solver.body(pose, tclip.controls(tf))
        tgt_ctx[f] = (tclip, tf, solver.context(pose, c, K))
        pins[f] = int(np.argmin(solver.eval_right(tgt_ctx[f][2], *grid) + roll_cost(1.0)[:, None, None]))
    axes = [(ROLLS, STEP_COST["roll"], True, STEP_CAP["roll"]), (TILTS, STEP_COST["tilt"], False, STEP_CAP["tilt"]),
            (SWIVELS, STEP_COST["swivel"], False, STEP_CAP["swivel"])]
    for f, st in follow.items():
        pins[f] = int(np.ravel_multi_index(tuple(_nearest(ax[0], v, ax[2]) for ax, v in zip(axes, st[:3])), grid[0].shape))
    ease = step_ease([cx["K3"][:, 1] for cx in ctxs], [cx["G"] for cx in ctxs], ts)
    caps = step_caps(clip)
    path = dp_path(local, axes, pins, ts, ease, caps, wr)
    for f, st in follow.items():
        path[f] = st[:3]

    def ev(f, cand):
        return solver.eval_right(ctxs[f], cand[:, 0], cand[:, 1], cand[:, 2]) + weight[f] * (cand[:, 0] / ROLL_SCALE) ** 2
    path = refine_path(ev, path, pins, axes, ts, ease, caps=caps)
    # el codo izquierdo con la mano ya decidida (en la empuñadura depende de la katana)
    ctx_l, hands_l = [], []
    for f in range(n + 1):
        pose = NA.Pose(rig)
        solver.solve(pose, clip.controls(f), (*path[f], 0.0), frame_limits(clip, f))
        c = solver.c
        hands_l.append(solver.left_hand(solver.katana, solver.free_left(c), c["grip_l"], path[f][1]))
        ctx_l.append(solver.context(pose, c, solver.katana))
    # el costo de cada giro de codo y, como en el derecho, la muñeca y el hombro que resultan (el tope de cambio por cuadro
    # de dp_path: sin él el húmero izquierdo giraba 55-160° de un cuadro al otro aunque el codo fuera suave, con el brazo
    # casi recto el mismo codo es otro giro de hombro)
    loc_l, wr_l = [], []
    for f in range(n + 1):
        loc_l.append(solver.eval_left(ctx_l[f], hands_l[f], np.array(SWIVELS_L)))
        wr_l.append(np.stack([np.broadcast_to(solver.last_ang_l[k], (len(SWIVELS_L),)) for k in (0, 2, 3)]))
    loc_l = np.array(loc_l)
    pins_l = {f: int(np.argmin(loc_l[f])) for f in pins}
    for f, (tclip, tf, _) in tgt_ctx.items():
        # el codo izquierdo del cuadro con el que empalma, resuelto con su propia pose
        st = tuple(path[f])
        pose = NA.Pose(rig)
        solver.solve(pose, tclip.controls(tf), (*st, 0.0), frame_limits(tclip, tf))
        c = solver.c
        hl = solver.left_hand(solver.katana, solver.free_left(c), c["grip_l"], st[1])
        pins_l[f] = int(np.argmin(solver.eval_left(solver.context(pose, c, solver.katana), hl, np.array(SWIVELS_L))))
    axes_l = [(SWIVELS_L, STEP_COST["swivel_l"], False, STEP_CAP["swivel_l"])]
    for f, st in follow.items():
        pins_l[f] = _nearest(SWIVELS_L, st[3], False)
    ease_l = step_ease([np.array(rot3(h).col[1]) for h in hands_l], [np.array(h.translation) for h in hands_l], ts)
    path_l = dp_path(loc_l, axes_l, pins_l, ts, ease_l, caps, wr_l)
    for f, st in follow.items():
        path_l[f] = st[3:4]
    path_l = refine_path(lambda f, cand: solver.eval_left(ctx_l[f], hands_l[f], cand[:, 0]), path_l, pins_l, axes_l, ts,
                         ease_l, caps=caps)
    solver.path_ease = (ease, ease_l)          # build_kaito: los tirones que cuentan son los que el gesto no tapa
    solver.path_caps = caps
    out = [tuple(float(x) for x in path[f]) + (float(path_l[f][0]),) for f in range(n + 1)]
    PATHS[clip.name] = out
    return out
