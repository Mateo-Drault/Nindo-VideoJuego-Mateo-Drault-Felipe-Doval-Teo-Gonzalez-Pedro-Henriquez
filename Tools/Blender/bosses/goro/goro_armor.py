"""La armadura de roca de Gorō (fase 2): diseño, geometría y orden de armado.

Concepto (Docs/handoff/conceptos/goro_fase2_armadura*.jpg, Higgsfield sobre un render del modelo): cuando la primera
barra se vacía, Gorō cae y la montaña se le pega encima. Exagerada a propósito: rocas de granito facetadas, gris azulado
con caras de sombra oscuras y nieve en las que miran arriba, y vetas de brasa (glow_fire) entre las rocas de cada pieza.

Se lee desde la cámara del juego (52°, 24 m): la silueta crece arriba y a los costados (dos cumbres de agujas en la
espalda que asoman por encima del casco, dos hombreras de 0.9 m, dos cuernos de piedra a los lados del casco) y el
frente conserva lo que identifica a Gorō: el maedate de oro, los ojos rojos, el shimenawa y los shide. Las agujas van en
DOS cumbres a los lados de la columna, con un paso en el medio: por ahí pasa el mango cuando levanta el martillo atrás
de la cabeza (Combo3, el golpe sísmico); los cuernos salen de los costados del casco por lo mismo.

Cada pieza es rígida con su propio hueso 'Acc_Roca_<Pieza>' (hijo del hueso del cuerpo que la lleva, con la cabeza en
el centro de la pieza): en Unity CharacterKits cuelga esos huesos de los vivos (mismo local) y la cinemática de armado
mueve cada hueso desde su punto de partida hasta su lugar (goro_review.py la simula con la misma fórmula; el contrato
está en el sidecar Kit_goro_armor.fbx.json).

Marco de autoría (el de team_rig): metros del juego, origen en el piso bajo Gorō, frente -Y, izquierda +X, arriba +Z,
en la pose de reposo del modelo. Medidas de la piel (rayos sobre la malla en reposo): torso de y -0.43 (pecho) a +0.46
(espalda) y x ±0.58; arriba del hombro z 2.41 en x ±0.6; brazo de radio ~0.20 y antebrazo ~0.16 (en reposo los brazos
van horizontales con la palma abajo: el dorso del antebrazo mira a +Z); casco hasta z 3.11 y x ±0.46; rodilla adelante
y -0.18, tibia y -0.21.
"""
import bpy, bmesh, math, os, sys, random
from mathutils import Vector, Matrix, Quaternion, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
for _p in (os.path.join(REPO, "Tools", "Blender", "characters", "kits"), os.path.join(REPO, "Tools", "Blender")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import kitlib as K               # noqa: E402

KIT_ID = "goro_armor"
BONE_PREFIX = "Acc_Roca_"
EMBER = "glow_fire"

# ------------------------------------------------------------------ piezas
# name: hueso del cuerpo que la lleva; slam: cuadro de ArmorRise (30 fps) en que la pieza se clava (team_clips_goro arma
# la reacción del cuerpo a cada golpe en ese cuadro); flight: segundos de vuelo hasta ahí; start: de dónde sale, en
# metros respecto de Gorō en el marco de autoría (la mayoría arranca enterrada 0.3 m: la arranca del piso); arc: altura
# extra de la parábola (m); spin: grados que da al volar (la tumba; termina derecha).
# El orden cuenta la subida: la montaña lo agarra por los pies, le da brazos para levantarse, el pecho, los hombros que
# lo aplastan (y aguanta), la espalda que lo endereza y la corona al final, cuando ruge.
PIECES = [
    dict(name="Greave_L", bone="Tibia.L", slam=24, flight=0.55, start=(2.6, 1.8, -0.3), arc=1.2, spin=200),
    dict(name="Greave_R", bone="Tibia.R", slam=30, flight=0.55, start=(-2.8, 1.4, -0.3), arc=1.2, spin=220),
    dict(name="Knee_L", bone="Tibia.L", slam=38, flight=0.6, start=(3.4, -1.0, -0.3), arc=1.6, spin=260),
    dict(name="Knee_R", bone="Tibia.R", slam=44, flight=0.6, start=(-3.6, -0.6, -0.3), arc=1.6, spin=240),
    dict(name="Tasset_L", bone="Pierna.L", slam=52, flight=0.6, start=(4.2, 0.6, -0.3), arc=1.8, spin=180),
    dict(name="Tasset_R", bone="Pierna.R", slam=56, flight=0.6, start=(-4.0, 1.2, -0.3), arc=1.8, spin=200),
    dict(name="Bracer_R", bone="Antebrazo.R", slam=70, flight=0.55, start=(-3.2, -2.6, -0.3), arc=1.6, spin=300),
    dict(name="Bracer_L", bone="Antebrazo.L", slam=76, flight=0.55, start=(3.4, -2.4, -0.3), arc=1.6, spin=280),
    dict(name="Chest_Low", bone="Torso", slam=92, flight=0.65, start=(0.6, -4.6, -0.3), arc=2.0, spin=160),
    dict(name="Chest_High", bone="Torso", slam=100, flight=0.65, start=(-0.8, -5.0, -0.3), arc=2.4, spin=180),
    dict(name="Pauldron_L", bone="Brazo.L", slam=118, flight=0.75, start=(5.2, 2.2, -0.3), arc=3.0, spin=220),
    dict(name="Pauldron_R", bone="Brazo.R", slam=128, flight=0.75, start=(-5.4, 1.6, -0.3), arc=3.0, spin=240),
    dict(name="Ridge_L", bone="Torso", slam=146, flight=0.8, start=(2.4, 6.0, -0.3), arc=3.6, spin=140),
    dict(name="Ridge_R", bone="Torso", slam=152, flight=0.8, start=(-2.2, 6.2, -0.3), arc=3.6, spin=160),
    dict(name="Horn_L", bone="Cabeza", slam=170, flight=0.7, start=(1.6, 4.4, 5.5), arc=1.0, spin=320),
    dict(name="Horn_R", bone="Cabeza", slam=174, flight=0.7, start=(-1.6, 4.2, 5.8), arc=1.0, spin=340),
]
PIECE = {p["name"]: p for p in PIECES}


# ------------------------------------------------------------------ geometría en el marco de autoría
class RockGeo:
    """Junta las rocas de cada pieza en el marco de autoría (m) y las pasa al Geo del kit (mundo del FBX)."""

    def __init__(self, kit, ch):
        self.kit, self.ch, self.geo = kit, ch, (kit.geo if kit is not None else None)
        self.parts = {}            # pieza -> índices de vértices del Geo
        self.local = {}            # pieza -> puntos en el marco de autoría (para el centro)
        self.rocks = {}            # pieza -> [puntos de cada roca] (sin los núcleos: cascos de goro_checks)

    def world(self, p):
        return self.ch.A @ self.ch.P(p)

    def faces(self, piece, verts, faces, color_fn):
        """Agrega un poliedro (vértices en el marco de autoría, caras con su color por normal)."""
        self.local.setdefault(piece, []).extend(verts)
        if color_fn is not ember:
            self.rocks.setdefault(piece, []).append(list(verts))
        if self.geo is None:
            return
        idx = self.geo.add([self.world(v) for v in verts])
        mid = sum(verts, Vector()) / len(verts)
        for f in faces:
            a, b, c = (verts[i] for i in f[:3])
            fc = sum((verts[i] for i in f), Vector()) / len(f)
            n = (b - a).cross(c - a)
            n = n.normalized() if n.length > 1e-9 else Vector((0, 0, 1))
            # la normal hacia afuera del poliedro (convexo): el color por normal no depende del orden de los vértices
            if n.dot(fc - mid) < 0.0:
                n = -n
            self.geo.face([idx[i] for i in f], color_fn(n, fc))
        self.parts.setdefault(piece, []).extend(idx)


def rock_color(seed, snow_z=0.78, light_z=0.5):
    """Color por cara: nieve solo en las que miran casi arriba, granito claro en las inclinadas, sombra en las que miran
    abajo; el resto alterna granito y granito oscuro (las facetas se leen sin textura). Con más nieve o más granito claro
    las rocas se leían como hielo bajo la luna."""
    rnd = random.Random(seed)

    def fn(n, c):
        if n.z > snow_z:
            return "snow" if rnd.random() < 0.75 else "snow_shade"
        if n.z > light_z:
            return "rock" if rnd.random() < 0.7 else "rock_light"
        if n.z < -0.3:
            return "rock_dark" if rnd.random() < 0.8 else "rock_brown_dark"
        u = rnd.random()
        return "rock_dark" if u < 0.5 else ("rock" if u < 0.82 else "rock_brown")
    return fn


def ember(n, c):
    return EMBER


def hull_rock(rnd, n_pts, jitter):
    """Roca de caras grandes: el casco convexo de 'n_pts' puntos al azar sobre la esfera unidad (corridos hacia adentro
    hasta 'jitter'). Es el canto rodado low poly: 20-30 triángulos irregulares en vez de una icosfera de cristal."""
    bm = bmesh.new()
    ga = math.pi * (3.0 - math.sqrt(5.0))
    for i in range(n_pts):
        z = 1.0 - 2.0 * (i + 0.5) / n_pts
        r = math.sqrt(max(0.0, 1.0 - z * z))
        a = ga * i + rnd.uniform(-0.6, 0.6)
        z += rnd.uniform(-0.18, 0.18)
        k = 1.0 - rnd.uniform(0.0, jitter)
        bm.verts.new(Vector((r * math.cos(a), r * math.sin(a), z)).normalized() * k)
    res = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    for g in res["geom_interior"] + res["geom_unused"]:
        if isinstance(g, bmesh.types.BMVert) and g.is_valid:
            bm.verts.remove(g)
    bm.verts.index_update()
    vs = [v.co.copy() for v in bm.verts]
    fs = [tuple(v.index for v in f.verts) for f in bm.faces]
    bm.free()
    return vs, fs


def rock(rg, piece, center, radii, rot=(0, 0, 0), seed=1, pts=16, jitter=0.16, flat_bottom=None, color=None, snow=0.78):
    """Roca facetada (hull_rock) escalada y girada (grados XYZ), determinista por 'seed'. flat_bottom: z local (-1..1)
    debajo del cual se aplasta (la cara que apoya en el cuerpo)."""
    rnd = random.Random(seed)
    vs, fs = hull_rock(rnd, pts, jitter)
    R = Euler(tuple(math.radians(a) for a in rot), 'XYZ').to_matrix()
    out = []
    for p in vs:
        p = p.copy()
        if flat_bottom is not None and p.z < flat_bottom:
            p.z = flat_bottom + (p.z - flat_bottom) * 0.15
        out.append(Vector(center) + R @ Vector((p.x * radii[0], p.y * radii[1], p.z * radii[2])))
    rg.faces(piece, out, fs, color or rock_color(seed, snow_z=snow))


def spire(rg, piece, base, tip, r, sides=5, seed=1, kink=0.25):
    """Aguja de roca: prisma de 'sides' lados que se afina hasta la punta, con un quiebre a 'kink' del largo (las
    agujas rectas parecen conos de plástico); nieve en las caras de arriba."""
    rnd = random.Random(seed)
    base, tip = Vector(base), Vector(tip)
    ax = (tip - base)
    L = ax.length
    ax.normalize()
    side = ax.cross(Vector((0, 0, 1)))
    if side.length < 1e-3:
        side = Vector((1, 0, 0))
    side.normalize()
    up = side.cross(ax).normalized()
    bend = (side * rnd.uniform(-1, 1) + up * rnd.uniform(-1, 1)) * L * 0.06
    rings = [(0.0, r, Vector()), (0.45, r * 0.72, bend), (0.8, r * 0.36, bend * 1.6)]
    verts, faces = [], []
    for t, rr, off in rings:
        a0 = rnd.uniform(0, 2 * math.pi)
        for j in range(sides):
            a = a0 * 0.15 + 2 * math.pi * j / sides
            jj = 1.0 + rnd.uniform(-kink, kink) * 0.5
            verts.append(base + ax * (L * t) + off + (side * math.cos(a) + up * math.sin(a)) * rr * jj)
    verts.append(tip + bend * 2.0)
    for ri in range(len(rings) - 1):
        for j in range(sides):
            k = (j + 1) % sides
            faces.append((ri * sides + j, ri * sides + k, (ri + 1) * sides + k, (ri + 1) * sides + j))
    last = (len(rings) - 1) * sides
    for j in range(sides):
        faces.append((last + j, last + (j + 1) % sides, len(verts) - 1))
    faces.append(tuple(reversed(range(sides))))
    rg.faces(piece, verts, faces, rock_color(seed + 7, snow_z=0.45))


def core(rg, piece, center, radii, rot=(0, 0, 0), seed=1):
    """Núcleo de brasa: una roca más chica adentro de las de la pieza; asoma por las vetas entre ellas."""
    rock(rg, piece, center, radii, rot, seed, pts=10, jitter=0.1, color=ember)


# ------------------------------------------------------------------ las piezas (marco de autoría, reposo)
def mirror(p, sx):
    return (p[0] * sx, p[1], p[2])


def build_pieces(rg):
    """Cada pieza son 2-3 rocas grandes con una veta de 3-6 cm entre ellas y un núcleo de brasa finito metido en la veta:
    se ve una línea de brasa, no una mancha (con el núcleo del tamaño de la pieza asomaba como un parche naranja)."""
    for s, sx in (("L", 1.0), ("R", -1.0)):
        sd = 11 if s == "L" else 23
        m = lambda p: mirror(p, sx)
        # tibia: dos lajas al frente de la canilla (y -0.21), una arriba de otra
        g = "Greave_" + s
        rock(rg, g, m((0.45, -0.31, 0.49)), (0.16, 0.10, 0.12), (8, 0, 10 * sx), sd + 1)
        rock(rg, g, m((0.48, -0.29, 0.27)), (0.15, 0.10, 0.09), (-6, 0, -8 * sx), sd + 2, pts=12)
        core(rg, g, m((0.46, -0.25, 0.375)), (0.13, 0.06, 0.03), seed=sd + 4)
        # rodilla: canto rodado sobre la rótula (y -0.18) y uno chico afuera
        k = "Knee_" + s
        rock(rg, k, m((0.43, -0.35, 0.75)), (0.21, 0.17, 0.17), (10, 0, 0), sd + 5, pts=18, jitter=0.12, snow=0.65)
        rock(rg, k, m((0.66, -0.21, 0.70)), (0.09, 0.12, 0.13), (0, 30, 0), sd + 6, pts=10)
        core(rg, k, m((0.59, -0.25, 0.72)), (0.04, 0.10, 0.10), seed=sd + 7)
        # muslo: escarcela de dos lajas al costado de la cadera (x 0.6-0.7), colgando sobre el cuero
        t = "Tasset_" + s
        rock(rg, t, m((0.73, -0.02, 1.19)), (0.10, 0.26, 0.13), (0, -14 * sx, 0), sd + 8)
        rock(rg, t, m((0.71, 0.00, 0.94)), (0.09, 0.22, 0.10), (0, -10 * sx, 8), sd + 9, pts=12)
        core(rg, t, m((0.69, -0.01, 1.065)), (0.06, 0.20, 0.03), seed=sd + 10)
        # antebrazo: guantelete en el dorso (+Z en reposo) en dos rocas con la veta cruzada, y un canto afuera
        b = "Bracer_" + s
        rock(rg, b, m((1.14, 0.07, 2.22)), (0.19, 0.19, 0.14), (0, 6 * sx, 0), sd + 12, pts=18, jitter=0.12, flat_bottom=-0.5,
             snow=0.65)
        rock(rg, b, m((1.47, 0.06, 2.14)), (0.12, 0.16, 0.10), (0, 4 * sx, 15), sd + 13, pts=12, flat_bottom=-0.4)
        rock(rg, b, m((1.27, 0.29, 2.03)), (0.14, 0.08, 0.10), (0, 0, -10 * sx), sd + 14, pts=10)
        core(rg, b, m((1.335, 0.07, 2.14)), (0.03, 0.13, 0.07), seed=sd + 15)
        # hombrera: el canto más grande partido en dos (adelante y atrás) con la veta a lo largo del hombro, la nieve
        # arriba, y uno chico que cuelga afuera; 0.9 m de ancho y apoyada en el hombro (z 2.41)
        p = "Pauldron_" + s
        rock(rg, p, m((0.86, -0.17, 2.58)), (0.46, 0.25, 0.34), (0, -16 * sx, 6 * sx), sd + 16, pts=22, jitter=0.12,
             flat_bottom=-0.55, snow=0.62)
        rock(rg, p, m((0.80, 0.31, 2.54)), (0.41, 0.21, 0.31), (0, -18 * sx, -4 * sx), sd + 17, pts=20, jitter=0.12,
             flat_bottom=-0.55, snow=0.62)
        rock(rg, p, m((1.18, 0.05, 2.30)), (0.14, 0.20, 0.17), (0, 20 * sx, 0), sd + 18, pts=10)
        core(rg, p, m((0.83, 0.08, 2.52)), (0.32, 0.05, 0.16), seed=sd + 19)
        # espalda: cumbre de tres agujas gruesas sobre el omóplato (x 0.20-0.60), inclinadas atrás y afuera; la más alta
        # pasa por encima del casco (z 3.45). El paso del medio (x < 0.16) queda libre para el mango
        r = "Ridge_" + s
        for i, (bx, by, bz, tx, ty, tz, rr) in enumerate((
                (0.30, 0.52, 2.28, 0.44, 0.92, 3.45, 0.24), (0.54, 0.48, 2.12, 0.88, 0.90, 2.98, 0.21),
                (0.27, 0.57, 1.90, 0.42, 1.06, 2.60, 0.19))):
            spire(rg, r, m((bx, by, bz)), m((tx, ty, tz)), rr, sides=5, seed=sd * 5 + i)
        rock(rg, r, m((0.40, 0.56, 2.04)), (0.25, 0.14, 0.27), (0, 0, 0), sd + 20, flat_bottom=-0.5)
        core(rg, r, m((0.42, 0.66, 2.20)), (0.10, 0.08, 0.22), seed=sd + 21)
        # corona: un cuerno de piedra a cada lado del casco (sale de x 0.40 y sube abierto hasta z 3.70), detrás del
        # maedate de oro, que sigue siendo lo que se ve de frente
        h = "Horn_" + s
        spire(rg, h, m((0.40, 0.06, 2.78)), m((0.74, 0.20, 3.70)), 0.16, sides=5, seed=sd * 7)
        spire(rg, h, m((0.44, 0.22, 2.72)), m((0.66, 0.46, 3.22)), 0.10, sides=5, seed=sd * 7 + 1)
        rock(rg, h, m((0.45, 0.12, 2.73)), (0.13, 0.15, 0.11), (0, 0, 0), sd + 22, pts=10)
        core(rg, h, m((0.50, 0.14, 2.84)), (0.05, 0.06, 0.06), seed=sd + 23)
    # pecho: dos lajas por banda con la veta vertical en el esternón (la línea de brasa que se ve de frente) y la
    # horizontal entre las dos bandas, sobre el peto de piedra del equipo (y -0.43); el shimenawa y los shide quedan a
    # la vista
    for x, sd in ((0.30, 101), (-0.30, 103)):
        rock(rg, "Chest_High", (x, -0.53, 2.20), (0.27, 0.13, 0.20), (-10, 0, 10 if x > 0 else -10), sd, pts=18, jitter=0.12)
        rock(rg, "Chest_Low", (x * 0.85, -0.51, 1.86), (0.22, 0.12, 0.14), (6, 0, -12 if x > 0 else 12), sd + 10, pts=13)
    core(rg, "Chest_High", (0.0, -0.49, 2.18), (0.05, 0.08, 0.20), seed=105)
    core(rg, "Chest_Low", (0.0, -0.47, 1.87), (0.04, 0.07, 0.13), seed=115)
    core(rg, "Chest_Low", (0.0, -0.49, 2.01), (0.36, 0.07, 0.03), seed=116)


# ------------------------------------------------------------------ armado sobre el personaje
def kit_char(ch):
    """El personaje como lo espera kitlib (Char): el FBX del equipo ya cargado por team_rig.TeamChar."""
    K.CHARS.setdefault("goro", dict(fbx=ch.spec["fbx"], body="Cylinder.001", front=(0, -1, 0), height=ch.spec["height"]))
    body = next(o for o in ch.meshes if o.vertex_groups and o.name.startswith("Cylinder.001"))
    return K.Char("goro", ch.arm, body)


def build_on(ch):
    """Arma la armadura sobre el Gorō cargado (en reposo, sin tocar la pose que tenga). Devuelve {'object', 'kit',
    'pieces': {pieza: {...centro, hueso...}}}."""
    arm = ch.arm
    prev = arm.data.pose_position
    arm.data.pose_position = 'REST'
    bpy.context.view_layer.update()
    kit = K.Kit(kit_char(ch), KIT_ID)
    rg = RockGeo(kit, ch)
    build_pieces(rg)
    centers = {}
    for p in PIECES:
        pts = rg.local[p["name"]]
        centers[p["name"]] = sum(pts, Vector()) / len(pts)
    # un hueso por pieza, con la cabeza en su centro y la cola 0.3 m arriba (la orientación no importa: es rígida)
    inv = arm.matrix_world.inverted()
    for o in bpy.context.selected_objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    eb = arm.data.edit_bones
    for p in PIECES:
        c = centers[p["name"]]
        b = eb.new(BONE_PREFIX + p["name"])
        b.head = inv @ rg.world(c)
        b.tail = inv @ rg.world(c + Vector((0.0, 0.0, 0.3)))
        b.parent = eb[p["bone"]]
        b.use_connect = False
        b.use_deform = True
    bpy.ops.object.mode_set(mode='OBJECT')
    for p in PIECES:
        K.Part(rg.geo, rg.parts[p["name"]]).rigid(BONE_PREFIX + p["name"])
    obj = kit.build()
    arm.data.pose_position = prev
    bpy.context.view_layer.update()
    pieces = {p["name"]: dict(p, center=centers[p["name"]], points=rg.local[p["name"]]) for p in PIECES}
    return {"object": obj, "kit": kit, "pieces": pieces, "rg": rg}


def rocks_for_checks():
    """[(pieza, hueso del cuerpo, puntos de una roca en reposo, marco de autoría)] sin armar nada en la escena: los cascos
    con que goro_checks mide que el martillo no atraviese la armadura y que las rocas no se metan en el piso. Una roca por
    casco (el casco de la pieza entera llenaba el hueco entre las agujas)."""
    rg = RockGeo(None, None)
    build_pieces(rg)
    return [(name, PIECE[name]["bone"], pts) for name, lst in rg.rocks.items() for pts in lst]


def review_material(look, m):
    """Material de revisión (team_review: la luz del juego) para un slot del kit: la paleta por UV, como en Unity; la
    brasa, emisión pura del color de la paleta."""
    if m.name.startswith("Nindo_Emissive"):
        import nindo_palette as P
        return look.build("rv_" + m.name, albedo_rgb=(0.0, 0.0, 0.0), emission_rgb=P.hex_to_rgb(dict(P.PALETTE)[EMBER]))
    img = K.palette_image()
    # en el juego (espacio Gamma) la textura se muestrea cruda: el píxel es el color hex de la paleta
    img.colorspace_settings.name = 'Non-Color'
    return look.build("rv_" + m.name, albedo_image=img)
