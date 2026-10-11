"""Geometría de Chikuō, el Maestro del Bambú: viejo maestro de kung fu de 2.7 m, low-poly facetado.

Diseño (hojas de concepto n0..n3 de la carpeta de bocetos, refinadas del concepto c0 elegido entre cuatro):
* Silueta de grulla: alto y flaco, piernas largas en un pantalón negro que se infla bajo la rodilla y se recoge en
  vendas blancas, brazos largos, manos y pies grandes. Nada que ver con el abuelo de Kaito (1.45 m, redondo, sombrero
  de paja, kimono índigo, faja roja, barba en punta y ojos que sonríen): Chikuō es pelado, sin barba, con un rodete
  blanco arriba, cara seria de ojos hundidos y nariz ganchuda, y viste marfil, jade y negro.
* Lo que se lee desde la cámara del juego (52°, ~180 px de alto): la cabeza pelada con el rodete, las CEJAS blancas
  larguísimas que barren hacia atrás y arriba (desde arriba son una V blanca), los BIGOTES que caen hasta el pecho,
  el saco marfil hasta la rodilla con puños y faja jade de colas largas, las vendas blancas de las piernas.
* Fase 1: pelea con el saco puesto y la mano izquierda en la espalda. Fase 2: tira el saco (otro objeto,
  Master_Robe, y su copia que vuela, Master_RobeThrown) y queda con el chaleco sin mangas, los brazos fibrosos y las
  vendas. Fase 3: el bastón de bambú (Master_Staff, oculto hasta entonces).
* Lo que el juego enciende tiene material propio: las vendas de cada palma (Master_GlintHandR/L), cada zapatilla
  (Master_GlintFootR/L) y el bastón (Master_GlintStaff): solo se prende el miembro que pega (dorado = parry, rojo =
  dash). Los ojos (Master_Eyes) se encienden en jade en la fase 2.
Colores de la paleta compartida; nada de rojo ni dorado en el cuerpo (son los colores de los avisos).
"""
import math
import bpy
from mathutils import Vector, Matrix
import nindo_lib as L
import nindo_anim as NA
import master_rig as MR
from master_kit import Kit, mirror_kit, mirror_weights, tri_count, smooth01, along_bone, chain_weights

# --------------------------------------------------------------------------- materiales propios
SLOT_HAND_R, SLOT_HAND_L, SLOT_FOOT_R, SLOT_FOOT_L, SLOT_EYES, SLOT_STAFF, SLOT_SKIN = 4, 5, 6, 7, 8, 9, 10
EXTRA_MATS = ["Master_GlintHandR", "Master_GlintHandL", "Master_GlintFootR", "Master_GlintFootL", "Master_Eyes", "Master_GlintStaff",
              "Master_Skin"]
WRAP_RGB = (0.93, 0.91, 0.86)
FOOT_RGB = (0.11, 0.11, 0.13)
EYES_RGB = (0.12, 0.1, 0.09)
EYES_GLOW_RGB = (0.45, 1.0, 0.8)          # el jade de la fase 2 (el juego lo enciende con SetGlow)
STAFF_RGB = (0.50, 0.63, 0.25)            # bambú verde (el 'bamboo' de la paleta, apenas más claro de noche)
# piel curtida: más cálida y oscura que la del abuelo (#e3ab84, rosada) y del mismo tono que el elenco de noche (en la
# paleta no hay un tostado que no quede gris bajo la luna). Las sombras de la cara siguen en la paleta
SKIN_RGB = (0.80, 0.56, 0.38)
MAT_RGB = {"Master_GlintHandR": WRAP_RGB, "Master_GlintHandL": WRAP_RGB, "Master_GlintFootR": FOOT_RGB,
           "Master_GlintFootL": FOOT_RGB, "Master_Eyes": EYES_RGB, "Master_GlintStaff": STAFF_RGB, "Master_Skin": SKIN_RGB}

C = dict(skin="lantern_paper", skin2="wood_pale", skin3="clay", hair="white", hair2="cloth_white",
         ivory="cloth_white", ivory2="plaster", ivory3="plaster_shade", jade="copper_green", jade2="grass_teal",
         jade3="leaf_pine_dark", black="cloth_black", black2="ink", wrap="white", wrap2="plaster_shade", sole="white",
         button="ink", mouth="wood_dark", node="bamboo_dark", node2="bamboo_dry")

KB = {b.name: b for b in MR.bones()}


def bh(n):
    return KB[n].head.copy()


def bt(n):
    return KB[n].tail.copy()


# --------------------------------------------------------------------------- anillos de sección propia
def ring(z, rx, ryf, ryb, n=12, cx=0.0, cy=0.0, power=2.4, pinch=None):
    """Anillo horizontal con frente (-Y) y espalda de distinta profundidad; i = 0 al frente. pinch(a) -> factor
    del radio por ángulo (mejillas hundidas, cintura)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        s, c = math.sin(a), -math.cos(a)
        e = 2.0 / power
        x = rx * math.copysign(abs(s) ** e, s)
        ry = ryf if c < 0 else ryb
        y = ry * math.copysign(abs(c) ** e, c)
        k = pinch(a) if pinch else 1.0
        pts.append(Vector((cx + x * k, cy + y * k, z)))
    return pts


def section_y(prof, x, z, front=True):
    """y de la superficie (frente o espalda) de un perfil [(z, medio ancho, frente, espalda)] en (x, z)."""
    for (z0, w0, f0, b0), (z1, w1, f1, b1) in zip(prof[:-1], prof[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            w = w0 + (w1 - w0) * t
            d = (f0 + (f1 - f0) * t) if front else (b0 + (b1 - b0) * t)
            u = min(0.999, abs(x) / w)
            return (-d if front else d) * (1.0 - u ** 2.4) ** (1 / 2.4)
    return -0.12 if front else 0.12


def torso_weights(co):
    """Tronco de la cadera al cuello: Hips -> Spine -> Chest con mezclas en las uniones (el chaleco y el saco doblan
    en la cintura y el pecho sin quebrarse)."""
    z = co.z
    if z < 1.36:
        a = 0.5 * smooth01((z - 1.30) / 0.08) if z > 1.30 else 0.0
        return {"Hips": 1.0 - a, "Spine": a}
    if z < 1.44:
        a = 0.5 * smooth01((1.44 - z) / 0.08)
        return {"Spine": 1.0 - a, "Hips": a}
    if z < 1.66:
        return {"Spine": 1.0}
    if z < 1.76:
        a = smooth01((z - 1.66) / 0.10)
        return {"Spine": 1.0 - a, "Chest": a}
    if z > 2.0:
        a = 0.5 * smooth01((z - 2.0) / 0.06)
        return {"Chest": 1.0 - a, "Neck": a}
    return {"Chest": 1.0}


# --------------------------------------------------------------------------- cabeza
# perfil radial de la cabeza: por altura, la distancia al eje (x = 0, y = 0) a los 0, 22.5, ... 180° (0 = frente,
# espejado del otro lado). La cara se arma en el perfil: el arco de la ceja que sobresale, las cuencas hundidas, el
# pómulo alto, la mejilla hundida bajo el pómulo, la mandíbula angosta y el cráneo largo hacia atrás (el viejo flaco
# de cara larga; nada de la cara redonda y risueña del abuelo)
HEAD_RINGS = [
    (2.160, [0.105, 0.098, 0.075, 0.062, 0.062, 0.06, 0.058, 0.058, 0.058]),
    (2.200, [0.138, 0.125, 0.096, 0.082, 0.084, 0.078, 0.072, 0.07, 0.07]),
    (2.245, [0.150, 0.136, 0.106, 0.094, 0.100, 0.097, 0.095, 0.098, 0.1]),
    (2.285, [0.156, 0.146, 0.115, 0.104, 0.112, 0.114, 0.115, 0.122, 0.125]),
    (2.325, [0.152, 0.142, 0.14, 0.126, 0.119, 0.124, 0.13, 0.138, 0.142]),
    (2.362, [0.150, 0.134, 0.136, 0.13, 0.122, 0.13, 0.14, 0.147, 0.15]),
    (2.398, [0.166, 0.165, 0.152, 0.134, 0.124, 0.134, 0.142, 0.148, 0.149]),
    (2.430, [0.156, 0.152, 0.142, 0.13, 0.122, 0.132, 0.14, 0.145, 0.146]),
    (2.470, [0.144, 0.14, 0.132, 0.122, 0.118, 0.127, 0.135, 0.14, 0.141]),
    (2.505, [0.126, 0.123, 0.117, 0.11, 0.107, 0.114, 0.121, 0.125, 0.126]),
    (2.535, [0.097, 0.095, 0.091, 0.086, 0.084, 0.089, 0.094, 0.097, 0.098]),
    (2.556, [0.058, 0.057, 0.055, 0.052, 0.051, 0.054, 0.057, 0.059, 0.06]),
]
HEAD_TOP = 2.566
HEAD_SIDES = 16


def head_r(z, a):
    """Radio de la cabeza a la altura z y al ángulo a (grados, 0 = frente, + = su izquierda), interpolado."""
    a = abs(((a + 180.0) % 360.0) - 180.0)
    k = a / 22.5
    i0 = min(7, int(k))
    t = k - i0
    rows = HEAD_RINGS
    if z <= rows[0][0]:
        r0 = rows[0][1]
        return r0[i0] + (r0[i0 + 1] - r0[i0]) * t
    for (z0, r0), (z1, r1) in zip(rows[:-1], rows[1:]):
        if z0 <= z <= z1:
            u = (z - z0) / (z1 - z0)
            a0 = r0[i0] + (r0[i0 + 1] - r0[i0]) * t
            a1 = r1[i0] + (r1[i0 + 1] - r1[i0]) * t
            return a0 + (a1 - a0) * u
    r1 = rows[-1][1]
    return r1[i0] + (r1[i0 + 1] - r1[i0]) * t


def head_surface(z, a, out=0.0):
    """Punto de la superficie de la cabeza (más 'out' metros hacia afuera)."""
    r = head_r(z, a) + out
    ar = math.radians(a)
    return Vector((math.sin(ar) * r, -math.cos(ar) * r, z))


def build_head(kits):
    def w_head(co):
        if co.z < 2.19:
            return {"Head": 0.6, "Neck": 0.4}
        return {"Head": 1.0}
    k = kits["Head"] = Kit("part_Head", "Head", weights=w_head)
    rings = []
    for z, rs in HEAD_RINGS:
        rings.append([head_surface(z, 360.0 * i / HEAD_SIDES) for i in range(HEAD_SIDES)])
    part = k.rings_loft(rings, C["skin"], True, False)
    top = k.bm.verts.new((0.0, 0.0, HEAD_TOP))
    last = [v for v in part.verts][-HEAD_SIDES:]
    fs = [k.bm.faces.new((last[i], last[(i + 1) % HEAD_SIDES], top)) for i in range(HEAD_SIDES)]
    k.tag(fs, C["skin"])
    # sombras de la cara (facetas un tono más oscuras): cuencas de los ojos, debajo del pómulo, el surco de la nariz a
    # la boca y la mandíbula; la coronilla un tono más clara (lo que agarra la luna desde arriba)
    for f in part.faces:
        c = f.calc_center_median()
        a = abs(math.degrees(math.atan2(c.x, -c.y)))
        if 2.34 < c.z < 2.39 and 8 < a < 52:
            k.tag([f], C["skin2"])
        elif 2.25 < c.z < 2.31 and 34 < a < 75:
            k.tag([f], C["skin2"])
        elif c.z < 2.22 and 40 < a < 95:
            k.tag([f], C["skin2"])
    # nariz grande y ganchuda (lo que sobresale de perfil y en 3/4): lomo en punta, la punta cae sobre el bigote
    k.tube([(0, -0.152, 2.392), (0, -0.178, 2.345), (0, -0.206, 2.305), (0, -0.214, 2.284), (0, -0.192, 2.268)],
           [(0.016, 0.012), (0.019, 0.017), (0.026, 0.022), (0.03, 0.02), (0.022, 0.01)], 4, C["skin"], ups=[(0, -1, 0.35)] * 5,
           phase=math.pi / 4, ring_colors=[C["skin"], C["skin"], C["skin"], C["skin2"]])
    for s in (-1.0, 1.0):
        # aletas de la nariz
        k.gem((0.022 * s, -0.19, 2.283), 0.013, C["skin2"], sides=4, height=0.01, axis=(0.6 * s, -0.8, 0))
        # ojo entrecerrado y serio (la punta de adentro más baja): ranura de material propio, se enciende en jade
        eye = head_surface(2.362, 25.0 * s, -0.004)
        k.obox(eye, (0.046, 0.01, 0.012), (1.0, 0.35 * s, -0.22 * s), (0, 0, 1), "black", slot=SLOT_EYES)
        # bolsa bajo el ojo y pata de gallo: dos facetas
        k.obox(head_surface(2.34, 30.0 * s, 0.002), (0.04, 0.012, 0.01), (1.0, 0.4 * s, 0.1 * s), (0, 0, 1), C["skin2"])
        build_ear(k, s)
    # boca casi tapada por el bigote; bigote grueso que nace bajo la nariz y baja a las comisuras (de ahí salen los largos)
    k.obox((0, -0.153, 2.236), (0.05, 0.01, 0.008), (1, 0, 0), (0, 1, 0), C["mouth"])
    k.tube([(-0.05, -0.198, 2.256), (-0.026, -0.21, 2.266), (0.0, -0.208, 2.27), (0.026, -0.21, 2.266), (0.05, -0.198, 2.256)],
           [0.014, 0.018, 0.016, 0.018, 0.014], 6, C["hair"], ups=[(0, -0.3, 1)] * 5, phase=math.pi / 6)
    # corona de pelo blanco de oreja a oreja por la nuca (pelado arriba), con el borde de abajo en mechones
    cols = []
    for i, a in enumerate(range(78, 283, 12)):
        dz = 0.022 if i % 2 else 0.0
        # pegado al cráneo arriba (sin escalón) y apenas más grueso abajo, donde terminan los mechones
        cols.append([head_surface(2.262 - dz, a, 0.011), head_surface(2.405, a, 0.003)])
    vb = [[k.bm.verts.new(p) for p in col] for col in cols]
    vi = [[k.bm.verts.new(p - Vector((p.x, p.y, 0)).normalized() * 0.009) for p in col] for col in cols]
    for i in range(len(vb) - 1):
        k.bm.faces.new((vb[i][0], vb[i + 1][0], vb[i + 1][1], vb[i][1]))
        k.bm.faces.new((vi[i][1], vi[i + 1][1], vi[i + 1][0], vi[i][0]))
        k.bm.faces.new((vb[i][1], vb[i + 1][1], vi[i + 1][1], vi[i][1]))
        k.bm.faces.new((vi[i][0], vi[i + 1][0], vb[i + 1][0], vb[i][0]))
    k.bm.faces.new((vb[0][0], vb[0][1], vi[0][1], vi[0][0]))
    k.bm.faces.new((vb[-1][1], vb[-1][0], vi[-1][0], vi[-1][1]))
    hair = k._new([v for c_ in vb + vi for v in c_], C["hair2"], None, None)
    k.up_shade(hair, C["hair"], 0.3)
    # mechones de las sienes: se paran un poco hacia atrás sobre las orejas (ensanchan la cabeza desde el frente)
    for s in (-1.0, 1.0):
        a = 100.0 * s
        p0 = head_surface(2.395, a, 0.01)
        k.tube([p0, p0 + Vector((0.035 * s, 0.05, 0.012)), p0 + Vector((0.05 * s, 0.11, 0.0))], [(0.022, 0.012), (0.018, 0.01),
               (0.004, 0.004)], 4, C["hair"], ups=[(0, 0, 1)] * 3, phase=math.pi / 4)
    # rodete: moño redondo de pelo blanco, el cordón jade en la base y una horquilla de madera que lo atraviesa
    by = 0.03
    k.tube([(0, by, 2.566), (0, by, 2.592), (0, by + 0.004, 2.625), (0, by + 0.006, 2.655), (0, by + 0.006, 2.672)],
           [0.032, 0.05, 0.054, 0.044, 0.018], 8, C["hair"], phase=math.pi / 8, cap0=False, cap1=True,
           ring_colors=[C["hair2"], C["hair"], C["hair"], C["hair"]])
    k.tube([(0, by, 2.574), (0, by, 2.592)], [0.04, 0.04], 8, C["jade"], phase=math.pi / 8, cap0=False, cap1=False)
    k.obox((0.0, by + 0.004, 2.628), (0.16, 0.012, 0.012), (1, 0, 0.18), (0, 1, 0), C["mouth"])

    # cuello flaco con la nuez y los tendones (la mezcla con el pecho la reparte el lado del pecho)
    def w_neck(co):
        if co.z < 2.06:
            return {"Neck": 0.5, "Chest": 0.5}
        return {"Neck": 1.0}
    kn = kits["Neck"] = Kit("part_Neck", "Neck", weights=w_neck)
    kn.tube([(0, 0.02, 2.0), (0, 0.018, 2.09), (0, 0.012, 2.19)], [(0.058, 0.056), (0.052, 0.05), (0.058, 0.058)], 8, C["skin"],
            phase=math.pi / 8)
    kn.gem((0, -0.034, 2.1), 0.013, C["skin"], sides=4, height=0.012, axis=(0, -1, 0))
    for s in (-1, 1):
        kn.obox((0.03 * s, -0.016, 2.09), (0.012, 0.01, 0.11), (1, 0, 0), (0, 1, 0.3 * -s), C["skin2"])


def build_ear(k, s):
    """Oreja grande de lóbulo largo (el sabio de los cuentos): una hoja con espesor, separada arriba y pegada abajo."""
    pts, rads = [], []
    for z, out, w, y in ((2.405, 0.008, 0.02, 0.03), (2.37, 0.018, 0.032, 0.03), (2.32, 0.018, 0.03, 0.024),
                         (2.275, 0.012, 0.021, 0.012), (2.245, 0.008, 0.012, 0.004)):
        p = head_surface(z, 92.0 * s, out)
        pts.append(Vector((p.x, y, z)))
        rads.append((w, 0.011))
    k.tube(pts, rads, 6, C["skin"], ups=[(s, 0, 0)] * len(pts), phase=0.0, ring_colors=[C["skin"], C["skin2"], C["skin"], C["skin"]])
    # hueco de la oreja: una faceta oscura hacia afuera
    c = pts[2] + Vector((0.008 * s, 0.0, 0.01))
    k.obox(c, (0.006, 0.026, 0.05), (1, 0, 0), (0, 1, 0), C["skin3"])


def build_brows_whiskers(kits):
    """Cejas: un mechón grueso pegado al arco de la ceja que sigue en una pluma larga hacia afuera y atrás (desde arriba
    es una V blanca). Bigotes: cordones que se afinan y caen sobre el pecho."""
    for S, sg in (("R", 1.0), ("L", -1.0)):
        m = (lambda v: Vector(v)) if S == "R" else (lambda v: Vector((-v[0], v[1], v[2])))
        # mechón de adentro, en la cabeza: nace bajo, junto a la nariz (el ceño serio) y cubre el arco de la ceja
        kh = kits["Head"]
        root = [m((-0.022, -0.168, 2.388)), m((-0.06, -0.17, 2.4)), m((-0.104, -0.15, 2.407))]
        kh.tube(root, [(0.022, 0.018), (0.034, 0.023), (0.036, 0.024)], 6, C["hair"],
                ups=[m((0, -1, 0.3))] * 3, phase=math.pi / 6)
        b1, b2 = "Brow_%s_1" % S, "Brow_%s_2" % S
        h, j, t = bh(b1), bt(b1), bt(b2)
        k1 = kits[b1] = Kit("part_" + b1, b1)
        d1 = (j - h).normalized()
        k1.tube([h - d1 * 0.02, h.lerp(j, 0.45) + Vector((0, 0, 0.01)), j + d1 * 0.012],
                [(0.036, 0.024), (0.031, 0.021), (0.024, 0.017)], 6, C["hair"], ups=[(0, -0.4, 1)] * 3, phase=math.pi / 6)
        k2 = kits[b2] = Kit("part_" + b2, b2)
        d2 = (t - j).normalized()
        k2.tube([j - d2 * 0.012, j.lerp(t, 0.5) + Vector((0, 0, 0.006)), t], [(0.024, 0.017), (0.016, 0.012), (0.004, 0.003)], 6,
                C["hair2"], ups=[(0, -0.1, 1)] * 3, phase=math.pi / 6)
        for seg, rads, bow in ((0, (0.012, 0.0095), 0.012), (1, (0.0095, 0.0068), 0.008), (2, (0.0068, 0.0022), -0.004)):
            bn = f"Acc_TieWhisker{S}_{seg}"
            kw = kits[bn] = Kit("part_" + bn, bn)
            a, b = bh(bn), bt(bn)
            d = (b - a)
            mid = a + d * 0.5 + Vector((-bow * sg, 0.0, 0.0))
            kw.tube([a - d * 0.06, mid, b + d * (0.05 if seg < 2 else 0.0)], [rads[0], (rads[0] + rads[1]) * 0.5, rads[1]], 6,
                    C["hair"] if seg % 2 == 0 else C["hair2"], phase=math.pi / 6)


# --------------------------------------------------------------------------- tronco (chaleco sin mangas)
VEST = [  # (z, medio ancho, frente, espalda)
    (1.24, 0.235, 0.18, 0.17), (1.32, 0.222, 0.165, 0.158), (1.44, 0.205, 0.15, 0.142), (1.56, 0.2, 0.146, 0.14),
    (1.68, 0.208, 0.15, 0.142), (1.80, 0.222, 0.152, 0.146), (1.90, 0.222, 0.142, 0.15), (1.965, 0.19, 0.118, 0.13),
    (2.02, 0.088, 0.072, 0.078),
]
VEST_FLAP = 0.13            # los faldones cortos del chaleco (fase 2) cuelgan de los primeros tramos del saco


def build_torso(kits):
    k = kits["Torso"] = Kit("part_Torso", "Chest", weights=torso_weights)
    rings = [ring(z, w, f, b, n=12, power=2.4) for z, w, f, b in VEST]
    cols = [C["ivory2"], C["ivory"], C["ivory"], C["ivory"], C["ivory"], C["ivory"], C["ivory"], C["ivory2"]]
    part = k.rings_loft(rings, C["ivory"], False, False, cols)
    k.tube([(0, 0.008, 2.0), (0, 0.01, 2.05), (0, 0.012, 2.08)], [(0.086, 0.08), (0.08, 0.075), (0.077, 0.072)], 10, C["ivory"],
           phase=math.pi / 10, cap0=False, cap1=False, ring_colors=[C["ivory"], C["ivory2"]])
    # escote en V con la piel del esternón: la línea del frente que se lee aun de lejos
    for f in part.faces:
        cc = f.calc_center_median()
        if cc.z > 1.92 and abs(cc.x) < 0.05 and cc.y < 0:
            k.tag([f], C["skin"])
    # botones de sapo del chaleco: cordón oscuro con dos bolitas
    for z in (1.5, 1.61, 1.72, 1.83):
        y = section_y(VEST, 0.0, z) - 0.006
        k.obox((0.0, y, z), (0.06, 0.012, 0.014), (1, 0, 0), (0, 1, 0), C["button"])
        k.gem((0.0, y - 0.006, z), 0.012, C["button"], sides=4, height=0.01, axis=(0, -1, 0))
    k.obox((0.0, section_y(VEST, 0.0, 1.62) - 0.003, 1.64), (0.012, 0.006, 0.4), (1, 0, 0), (0, 1, 0), C["ivory3"])
    # sisas: el canto del chaleco alrededor del hombro, un poco más oscuro (separa el marfil de la piel del brazo)
    for s in (-1.0, 1.0):
        k.tube([(0.2 * s, -0.08, 1.80), (0.235 * s, -0.03, 1.95), (0.2 * s, 0.07, 1.98), (0.21 * s, 0.11, 1.82)],
               [0.018, 0.02, 0.02, 0.018], 5, C["ivory3"], ups=[(s, 0, 0.2)] * 4, phase=math.pi / 5)
    # faldones cortos del chaleco (se ven en la fase 2): cuelgan de los primeros tramos del saco
    for a in MR.ROBE_ANGLES:
        bn = MR.robe_name(a, 1)

        def w_flap(co, bn=bn):
            t = smooth01((1.26 - co.z) / 0.08)
            return {"Hips": 1.0 - t, bn: t} if t < 1.0 else {bn: 1.0}
        kk = kits["Vest_" + bn] = Kit("vest_" + bn, bn, weights=w_flap)
        panel(kk, a, 1.28, 0.0, VEST_FLAP, 0.95, 41.0, C["ivory"], C["ivory3"], 0.012)


def panel(kk, a, top_z, d0, d1, scale, half, color, inner, thick, cols=5):
    """Paño de faldón con espesor (la cara de adentro 'thick' hacia el cuerpo): 'cols' columnas sobre el arco del saco
    a escala 'scale' (1 = el radio del saco), de d0 a d1 metros por debajo de 'top_z' siguiendo el vuelo."""
    angs = [a - half + 2.0 * half * i / (cols - 1) for i in range(cols)]
    tops, bots, outs = [], [], []
    for aa in angs:
        hh, dd, oo, tt = MR.robe_frame(aa)
        hh = Vector((hh.x * scale, hh.y * scale, top_z))
        tops.append(hh + dd * d0)
        bots.append(hh + dd * d1)
        outs.append(oo)
    vt = [kk.bm.verts.new(p) for p in tops]
    vb = [kk.bm.verts.new(p) for p in bots]
    it = [kk.bm.verts.new(p - o * thick) for p, o in zip(tops, outs)]
    ib = [kk.bm.verts.new(p - o * thick) for p, o in zip(bots, outs)]
    fo, fi, rim = [], [], []
    for i in range(cols - 1):
        fo.append(kk.bm.faces.new((vt[i], vt[i + 1], vb[i + 1], vb[i])))
        fi.append(kk.bm.faces.new((it[i + 1], it[i], ib[i], ib[i + 1])))
        rim.append(kk.bm.faces.new((vb[i], vb[i + 1], ib[i + 1], ib[i])))
    rim.append(kk.bm.faces.new((vt[0], vb[0], ib[0], it[0])))
    rim.append(kk.bm.faces.new((vt[-1], it[-1], ib[-1], vb[-1])))
    kk._new(vt + vb + it + ib, color, None, None)
    kk.tag(fi, inner)
    kk.tag(rim, inner)
    return vt, vb


def build_sash(kits):
    """Faja jade: anillo a la medida del chaleco, nudo grueso adelante a su izquierda (a la medida del saco: apoya en
    los dos) y dos colas largas que son cadenas con física."""
    kh = kits["Sash"] = Kit("part_Sash", "Hips", weights=torso_weights)
    kh.tube([(0, 0.0, 1.235), (0, 0.0, 1.30), (0, 0.0, 1.37)], [(0.248, 0.19), (0.252, 0.193), (0.24, 0.183)], 12, C["jade"],
            phase=math.pi / 12, cap0=False, cap1=False, power=2.4, ring_colors=[C["jade"], C["jade2"]])
    knot = MR.SASH_KNOT
    kh.obox(knot + Vector((0.03, 0.025, 0.005)), (0.11, 0.11, 0.095), (1, 0, 0.1), (0, 1, 0), C["jade2"], bevel=0.016,
            up_color=C["jade"])
    for t, w0 in (("A", 0.105), ("B", 0.09)):
        for seg in range(3):
            bn = f"Acc_TieSash{t}_{seg}"
            kk = kits[bn] = Kit("part_" + bn, bn)
            a_, t_ = bh(bn), bt(bn)
            d = t_ - a_
            w1 = w0 * (1.0 + 0.04 * seg)
            kk.strip([a_ - d * 0.06, a_ + d * 0.5, t_ + d * (0.05 if seg < 2 else 0.0)], [w1, w1 * 1.03, w1 * 1.06],
                     [(0.1, -1, 0)] * 3, C["jade"] if seg % 2 == 0 else C["jade2"], thick=0.02)


# --------------------------------------------------------------------------- brazos (piel, vendas, manos)
def arm_points():
    S, E, W = MR.SHOULDER, MR.ELBOW, MR.WRIST
    u = (E - S).normalized()
    l = (W - E).normalized()
    return S, E, W, u, l


def build_arm_r(kits):
    S, E, W, u, l = arm_points()
    # un solo tubo del hombro a la muñeca: anillos a los dos lados del codo (dobla limpio) y pesos repartidos
    wf = chain_weights([S, E, W], ["UpperArm_R", "Forearm_R"], before="Clav_R", after="Hand_R", span=0.06)

    def w_arm(co):
        # el tope del deltoides sigue un poco a la clavícula (el hombro sube con ella)
        t = along_bone(co, S, E)
        if t < 0.0:
            a = 0.5 * smooth01(-t / 0.15)
            return {"UpperArm_R": 1.0 - a, "Clav_R": a}
        return wf(co)
    k = kits["Arm_R"] = Kit("part_Arm_R", "UpperArm_R", weights=w_arm)
    pts = [S - u * 0.06, S + u * 0.05, S + u * 0.16, S + u * 0.29, E - u * 0.05, E, E + l * 0.06, E + l * 0.16, E + l * 0.25,
           E + l * 0.33, W - l * 0.03, W + l * 0.012]
    rads = [(0.062, 0.066), (0.075, 0.074), (0.068, 0.07), (0.06, 0.064), (0.053, 0.054), (0.051, 0.052), (0.056, 0.055),
            (0.054, 0.052), (0.049, 0.047), (0.046, 0.044), (0.043, 0.04), (0.045, 0.042)]
    # vendas desde la mitad del antebrazo (franjas): la última vuelta, en la muñeca, es del material que brilla
    cols = [C["skin"]] * 7 + [C["wrap"], C["wrap2"], C["wrap"], ("white", SLOT_HAND_R)]
    k.tube(pts, rads, 8, C["skin"], ups=[(0, -1, 0)] * len(pts), phase=math.pi / 8, cap0=True, cap1=False, ring_colors=cols)
    build_hand_r(kits)


def build_hand_r(kits):
    W, hd, dors, thumb = MR.hand_frame("R")
    Kn = MR.KNUCKLE
    across = -thumb               # hacia el meñique

    def w_hand(co):
        t = along_bone(co, W, Kn)
        return {"Hand_R": 1.0} if t > 0.15 else {"Hand_R": 0.7, "Forearm_R": 0.3}
    k = kits["Hand_R"] = Kit("part_Hand_R", "Hand_R", weights=w_hand)
    # palma grande y chata, vendada (brilla en el aviso); el canto de los nudillos es de piel
    k.tube([W - hd * 0.01, W + hd * 0.035, W + hd * 0.075, Kn + hd * 0.008],
           [(0.04, 0.024), (0.052, 0.026), (0.056, 0.025), (0.054, 0.021)], 6, C["skin"],
           ups=[dors] * 4, phase=math.pi / 6, power=3.0,
           ring_colors=[("white", SLOT_HAND_R), ("white", SLOT_HAND_R), C["skin"]])
    for name, off, l1, l2 in MR.FINGERS:
        b1, b2 = f"{name}_R_1", f"{name}_R_2"
        base, mid, tip = bh(b1), bh(b2), bt(b2)
        r0 = 0.0162 if name != "Pinky" else 0.0138

        def w_f(co, b1=b1, b2=b2, base=base, mid=mid, tip=tip):
            t = along_bone(co, base, mid)
            if t < 0.15:
                return {b1: 0.7, "Hand_R": 0.3}
            if t < 0.85:
                return {b1: 1.0}
            t2 = along_bone(co, mid, tip)
            if t2 < 0.18:
                return {b1: 0.5, b2: 0.5}
            return {b2: 1.0}
        kf = kits[b1] = Kit("part_" + b1, b1, weights=w_f)
        d1 = (mid - base).normalized()
        d2 = (tip - mid).normalized()
        kf.tube([base - d1 * 0.012, base + d1 * 0.012, mid - d1 * 0.004, mid + d2 * 0.008, tip - d2 * 0.008, tip],
                [(r0, r0 * 0.95), (r0, r0 * 0.95), (r0 * 0.92, r0 * 0.86), (r0 * 0.88, r0 * 0.84), (r0 * 0.78, r0 * 0.72),
                 (r0 * 0.55, r0 * 0.5)], 4, C["skin"], ups=[dors] * 6, phase=math.pi / 4, power=2.6, cap0=False)
    tb, tm, tt = bh("Thumb_R_1"), bh("Thumb_R_2"), bt("Thumb_R_2")

    def w_t(co):
        t = along_bone(co, tb, tm)
        if t < 0.2:
            return {"Thumb_R_1": 0.6, "Hand_R": 0.4}
        if t < 0.85:
            return {"Thumb_R_1": 1.0}
        t2 = along_bone(co, tm, tt)
        return {"Thumb_R_1": 0.5, "Thumb_R_2": 0.5} if t2 < 0.18 else {"Thumb_R_2": 1.0}
    kt = kits["Thumb_R_1"] = Kit("part_Thumb_R", "Thumb_R_1", weights=w_t)
    d1 = (tm - tb).normalized()
    d2 = (tt - tm).normalized()
    kt.tube([tb - d1 * 0.012, tb + d1 * 0.016, tm, tm + d2 * 0.02, tt], [(0.017, 0.015), (0.016, 0.014), (0.014, 0.013),
            (0.013, 0.012), (0.007, 0.007)], 4, C["skin"], ups=[dors] * 5, phase=math.pi / 4, power=2.6)


# --------------------------------------------------------------------------- piernas (pantalón ancho, vendas, zapatillas)
def build_leg_r(kits):
    x0 = MR.ANKLE.x
    H, K, A, B, T = MR.HIP_J, MR.KNEE, MR.ANKLE, MR.BALL, MR.TOE_TIP

    # ---- zapatilla: la suela y la capellada doblan en la bola del pie (la punta es otro hueso)
    def w_foot(co):
        if co.z > 0.11:
            a = 0.5 * smooth01((co.z - 0.11) / 0.06)
            return {"Foot_R": 1.0 - a, "Shin_R": a}
        dy = co.y - B.y
        if dy > 0.02:
            return {"Foot_R": 1.0}
        if dy < -0.02:
            return {"Toe_R": 1.0}
        a = smooth01((0.02 - dy) / 0.04)
        return {"Foot_R": 1.0 - a, "Toe_R": a}
    k = kits["Foot_R"] = Kit("part_Foot_R", "Foot_R", weights=w_foot)
    hw = [(MR.SOLE_HEEL_Y, 0.05), (0.04, 0.066), (-0.08, 0.078), (B.y + 0.02, 0.082), (B.y - 0.02, 0.08), (-0.25, 0.068),
          (MR.SOLE_TOE_Y + 0.025, 0.042), (MR.SOLE_TOE_Y, 0.014)]
    s = -1.0
    sole = [(x0 + w * s, y) for y, w in hw] + [(x0 - w * s, y) for y, w in reversed(hw)]
    k.extrude_polygon(sole, 0.0, 0.03, C["sole"], top_color=C["sole"])
    FOOT_RINGS = [(0.105, 0.056, 0.07, 0.048), (0.02, 0.068, 0.076, 0.062), (-0.09, 0.076, 0.066, 0.046),
                  (B.y + 0.01, 0.078, 0.058, 0.036), (B.y - 0.03, 0.074, 0.052, 0.03), (-0.26, 0.06, 0.044, 0.024),
                  (-0.295, 0.036, 0.038, 0.014)]
    k.tube([(x0, y, z) for y, _, z, _ in FOOT_RINGS], [(w, h) for _, w, _, h in FOOT_RINGS], 8, "black",
           ups=[(0, 0, 1)] * len(FOOT_RINGS), phase=math.pi / 8, power=2.4, slot=SLOT_FOOT_R)
    # tobillo vendado (la vuelta de abajo brilla con la zapatilla en las patadas)
    k.tube([(x0, 0.0, 0.095), (x0, 0.0, 0.17)], [0.07, 0.068], 8, "white", phase=math.pi / 8, cap0=False, cap1=False,
           slot=SLOT_FOOT_R)

    # ---- pantalón: un solo tubo de la cadera al tobillo (anillos a los dos lados de la rodilla), que se infla bajo la
    # rodilla y se recoge en las vendas
    wl = chain_weights([H, K, A], ["Thigh_R", "Shin_R"], before="Hips", after="Foot_R", span=0.07)
    k = kits["Leg_R"] = Kit("part_Leg_R", "Thigh_R", weights=wl)

    def on_leg(z, dx=0.0, dy=0.0):
        # punto del eje de la pierna a la altura z (cadera -> rodilla -> tobillo)
        if z >= K.z:
            t = (H.z - z) / (H.z - K.z)
            p = H.lerp(K, t)
        else:
            t = (K.z - z) / (K.z - A.z)
            p = K.lerp(A, t)
        return Vector((p.x + dx, p.y + dy, z))
    zs = [1.30, 1.16, 1.0, 0.85, 0.74, 0.66, 0.58, 0.52, 0.47]
    rads = [(0.13, 0.13), (0.142, 0.14), (0.15, 0.148), (0.148, 0.146), (0.15, 0.15), (0.166, 0.166), (0.17, 0.17),
            (0.142, 0.142), (0.094, 0.094)]
    offs = [(0.035, 0.0), (0.012, 0.0), (0.0, -0.01), (0.0, -0.015), (0.0, -0.02), (0.0, -0.015), (0.0, -0.005), (0.0, 0.0),
            (0.0, 0.0)]
    pts = [on_leg(z, dx, dy) for z, (dx, dy) in zip(zs, offs)]
    k.tube(pts, rads, 8, C["black"], ups=[(0, -1, 0)] * len(pts), phase=math.pi / 8, cap0=False, cap1=False,
           ring_colors=[C["black"], C["black"], C["black"], C["black2"], C["black"], C["black"], C["black2"], C["black"]])
    # vendas de la rodilla al tobillo (franjas claras y grises que se leen desde arriba)
    zs = [0.50, 0.44, 0.38, 0.32, 0.26, 0.20, 0.155]
    pts = [on_leg(z, 0.0, -0.006 + 0.002 * i) for i, z in enumerate(zs)]
    rads = [0.088, 0.084, 0.08, 0.077, 0.074, 0.072, 0.072]
    k.tube(pts, rads, 8, C["wrap"], phase=math.pi / 8 + 0.2, cap0=False, cap1=False,
           ring_colors=[C["wrap"], C["wrap2"], C["wrap"], C["wrap2"], C["wrap"], C["wrap2"]])


def build_hips(kits):
    k = kits["Hips"] = Kit("part_Hips", "Hips")
    # cadera del pantalón: tapa el tiro entre los dos muslos
    k.tube([(0, 0.0, 1.06), (0, 0.0, 1.16), (0, 0.0, 1.26)], [(0.19, 0.15), (0.205, 0.165), (0.2, 0.16)], 12, C["black"],
           phase=math.pi / 12, cap0=True, cap1=False, power=2.4)


# --------------------------------------------------------------------------- el saco (objeto aparte)
ROBE_BODY = [  # (z, medio ancho, frente, espalda): un poco más grande que el chaleco, del ancho de los faldones abajo
    (1.25, MR.ROBE_R[0] + 0.004, MR.ROBE_R[1] + 0.004, MR.ROBE_R[1]), (1.42, 0.238, 0.178, 0.17), (1.6, 0.232, 0.17, 0.162),
    (1.76, 0.246, 0.172, 0.164), (1.9, 0.258, 0.164, 0.17), (1.98, 0.215, 0.134, 0.144), (2.025, 0.098, 0.09, 0.092),
]


def build_robe(kits):
    k = kits["Robe_Body"] = Kit("robe_Body", "Chest", weights=torso_weights)
    rings = [ring(z, w, f, b, n=14, power=2.4) for z, w, f, b in ROBE_BODY]
    k.rings_loft(rings, C["ivory"], False, False, [C["ivory2"], C["ivory"], C["ivory"], C["ivory"], C["ivory"], C["ivory"]])
    # cuello mao, la línea de botones de sapo y la abertura del frente
    k.tube([(0, 0.01, 2.015), (0, 0.012, 2.07), (0, 0.014, 2.1)], [(0.096, 0.088), (0.09, 0.083), (0.087, 0.08)], 10, C["ivory"],
           phase=math.pi / 10, cap0=False, cap1=False, ring_colors=[C["ivory"], C["ivory2"]])
    for z in (1.5, 1.61, 1.72, 1.83, 1.93):
        y = section_y(ROBE_BODY, 0.0, z) - 0.006
        k.obox((0.0, y, z), (0.07, 0.014, 0.016), (1, 0, 0), (0, 1, 0), C["button"])
        k.gem((-0.035, y - 0.004, z), 0.013, C["button"], sides=4, height=0.011, axis=(0, -1, 0))
        k.gem((0.035, y - 0.004, z), 0.013, C["button"], sides=4, height=0.011, axis=(0, -1, 0))
    k.obox((0.0, section_y(ROBE_BODY, 0.0, 1.72) - 0.003, 1.72), (0.012, 0.006, 0.54), (1, 0, 0), (0, 1, 0), C["ivory3"])
    # la faja a la medida del saco (el nudo y las colas son del cuerpo: quedan en la fase 2)
    ks = kits["Robe_Sash"] = Kit("robe_Sash", "Hips", weights=torso_weights)
    ks.tube([(0, 0.0, 1.235), (0, 0.0, 1.30), (0, 0.0, 1.38)],
            [(MR.ROBE_R[0] + 0.02, MR.ROBE_R[1] + 0.02), (MR.ROBE_R[0] + 0.024, MR.ROBE_R[1] + 0.022), (0.256, 0.196)], 14,
            C["jade"], phase=math.pi / 14, cap0=False, cap1=False, power=2.4, ring_colors=[C["jade"], C["jade2"]])
    # faldones: dos tramos por paño, con la cara de adentro y el ruedo un tono más oscuros (la tela gruesa del saco)
    for a in MR.ROBE_ANGLES:
        for seg in (1, 2):
            bn = MR.robe_name(a, seg)
            kk = kits["Robe_" + bn] = Kit("robe_" + bn, bn)
            d0 = 0.0 if seg == 1 else MR.ROBE_LEN[0] - 0.02
            d1 = MR.ROBE_LEN[0] + (0.03 if seg == 1 else MR.ROBE_LEN[1])
            panel(kk, a, MR.ROBE_TOP_Z, d0, d1, 1.0 + 0.012 * seg, 41.0, C["ivory"], C["ivory3"], 0.018)
    # mangas anchas con el puño jade (la mano vendada asoma del puño); el borde de abajo cuelga de Sleeve_R
    S, E, W, u, l = arm_points()
    wa = chain_weights([S, E, W], ["UpperArm_R", "Forearm_R"], before="Clav_R", span=0.08)
    sl_h, sl_t = bh("Sleeve_R"), bt("Sleeve_R")

    def w_sleeve(co):
        t = along_bone(co, S, E)
        if t < 0.0:
            a = 0.5 * smooth01(-t / 0.15)
            return {"UpperArm_R": 1.0 - a, "Clav_R": a}
        w = wa(co)
        ts = along_bone(co, sl_h, sl_t)
        if ts > 0.0 and along_bone(co, E, W) > 0.3:
            a = 0.85 * smooth01(ts / 0.9)
            w = {n: v * (1.0 - a) for n, v in w.items()}
            w["Sleeve_R"] = w.get("Sleeve_R", 0.0) + a
        return w
    k = kits["Robe_Sleeve_R"] = Kit("robe_Sleeve_R", "UpperArm_R", weights=w_sleeve)
    pts = [S - u * 0.08, S + u * 0.1, S + u * 0.28, E - u * 0.04, E + l * 0.04, E + l * 0.15, E + l * 0.27, E + l * 0.32]
    rads = [(0.105, 0.096), (0.112, 0.106), (0.116, 0.112), (0.122, 0.118), (0.134, 0.13), (0.152, 0.146), (0.17, 0.164),
            (0.174, 0.168)]
    k.tube(pts, rads, 8, C["ivory"], ups=[(0, -1, 0)] * len(pts), phase=math.pi / 8, cap0=False, cap1=False,
           ring_colors=[C["ivory"]] * 5 + [C["jade"], C["jade2"]])
    # boca de la manga: el interior oscuro (desde arriba el puño se lee como un anillo jade con un hueco)
    c_end = E + l * 0.32
    k.tube([c_end - l * 0.01, c_end - l * 0.07], [(0.166, 0.16), (0.07, 0.068)], 8, C["jade3"], ups=[(0, -1, 0)] * 2,
           phase=math.pi / 8, cap0=False, cap1=False)
    kits["Robe_Sleeve_L"] = mirror_kit(k, "robe_Sleeve_L", "UpperArm_L", weights=mirror_weights(w_sleeve))


def build_robe_thrown(kits):
    """El saco tirado: el mismo saco aplanado (frente y espalda a pocos centímetros, como queda una tela vacía en el
    aire), con el cuello mao, los botones, las mangas con su puño jade y el ruedo abierto en dos por el tajo de atrás.
    En reposo vive adentro de la espalda (el juego lo oculta) y solo se ve cuando vuela en el cambio de fase."""
    y0 = 0.06

    def w_body(co):
        z = co.z
        if z > 1.68:
            return {"RobeT_Root": 1.0}
        if z < 1.56:
            return {"RobeT_Hem": 1.0}
        a = smooth01((1.68 - z) / 0.12)
        return {"RobeT_Root": 1.0 - a, "RobeT_Hem": a}
    k = kits["RobeT_Body"] = Kit("thrown_Body", "RobeT_Root", weights=w_body)
    # (z, medio ancho, medio espesor): con volumen arriba (hombros y pecho) y finito en el ruedo
    # (el ruedo no pasa del ancho de los muslos: en reposo no asoma por las aberturas del saco puesto)
    rows = [(1.995, 0.1, 0.045), (1.955, 0.225, 0.055), (1.8, 0.222, 0.058), (1.6, 0.214, 0.054), (1.42, 0.222, 0.05),
            (1.25, 0.245, 0.04), (1.05, 0.268, 0.03), (0.86, 0.288, 0.022)]
    rings = [ring(z, w, d, d, n=10, cy=y0, power=3.2) for z, w, d in rows]
    k.rings_loft(rings, C["ivory"], True, True, [C["ivory2"]] + [C["ivory"]] * 5 + [C["ivory2"]])
    k.up_shade(L.Part(k, list(k.bm.verts)), C["ivory2"], 0.6)
    # cuello mao
    k.tube([(0, y0, 1.985), (0, y0, 2.03)], [(0.092, 0.05), (0.086, 0.046)], 10, C["ivory"], phase=math.pi / 10, cap0=False,
           cap1=False)
    for z in (1.5, 1.61, 1.72, 1.83, 1.93):
        k.obox((0.0, y0 - section_depth(rows, z) - 0.004, z), (0.07, 0.01, 0.016), (1, 0, 0), (0, 1, 0), C["button"])
    for S in ("R", "L"):
        bn = "RobeT_Arm" + S
        h, t = bh(bn), bt(bn)
        d = (t - h).normalized()
        # aplanada como el cuerpo: el lado ancho mira adelante (Y), el espesor va en el plano del saco
        flat = Vector((0, 1, 0))

        def w_arm(co, h=h, t=t, bn=bn):
            u = along_bone(co, h, t)
            if u > 0.25:
                return {bn: 1.0}
            a = smooth01((u + 0.15) / 0.4)
            return {"RobeT_Root": 1.0 - a, bn: a}
        ka = kits[bn] = Kit("thrown_Arm" + S, bn, weights=w_arm)
        pts = [h - d * 0.04, h + d * 0.12, h + d * 0.26, h + d * 0.38, h + d * 0.42]
        rads = [(0.1, 0.04), (0.11, 0.042), (0.125, 0.046), (0.142, 0.05), (0.145, 0.05)]
        ka.tube(pts, rads, 6, C["ivory"], ups=[flat] * len(pts), phase=0.0,
                ring_colors=[C["ivory"], C["ivory"], C["ivory"], C["jade"]])
        # boca de la manga: el interior oscuro
        e = pts[-1]
        ka.tube([e - d * 0.005, e - d * 0.05], [(0.134, 0.044), (0.06, 0.02)], 6, C["jade3"], ups=[flat] * 2, phase=0.0,
                cap0=False, cap1=True)


def section_depth(rows, z):
    """Medio espesor del saco tirado a la altura z."""
    for (z0, _, d0), (z1, _, d1) in zip(rows[1:], rows[:-1]):
        if z0 <= z <= z1:
            return d0 + (d1 - d0) * (z - z0) / (z1 - z0)
    return rows[-1][2]


# --------------------------------------------------------------------------- el bastón (objeto rígido)
def build_staff():
    """Caña de bambú de 2.3 m: tramos de material propio (se encienden enteros en el aviso), nudos más oscuros que
    sobresalen, el atado jade del medio con dos cintas cortas y las puntas cortadas en bisel."""
    k = Kit("Master_Staff", "Staff")
    Lh = MR.STAFF_LEN * 0.5
    r = MR.STAFF_R
    nodes = [-Lh + 0.02, -0.78, -0.42, -0.08, 0.08, 0.42, 0.78, Lh - 0.02]
    # tramos entre nudos (cada uno un prisma de 7 lados, apenas más fino en el medio)
    for a, b in zip(nodes[:-1], nodes[1:]):
        if a == -0.08:
            continue
        m = (a + b) * 0.5
        k.tube([(0, 0, a), (0, 0, m), (0, 0, b)], [r * 0.97, r * 0.93, r * 0.97], 7, "white", ups=[(0, -1, 0)] * 3,
               phase=0.2, cap0=False, cap1=False, slot=SLOT_STAFF)
    for z in nodes[1:-1]:
        if abs(z) < 0.1:
            continue
        k.tube([(0, 0, z - 0.012), (0, 0, z), (0, 0, z + 0.012)], [r * 1.02, r * 1.16, r * 1.02], 7, C["node"], ups=[(0, -1, 0)] * 3,
               phase=0.2, cap0=False, cap1=False)
    # atado del medio: cordón jade con dos cintas que cuelgan
    k.tube([(0, 0, -0.1), (0, 0, 0.0), (0, 0, 0.1)], [r * 1.12, r * 1.18, r * 1.12], 7, C["jade"], ups=[(0, -1, 0)] * 3, phase=0.2,
           cap0=False, cap1=False, ring_colors=[C["jade"], C["jade2"]])
    for dx in (-0.012, 0.012):
        k.strip([(dx, -r * 1.2, 0.0), (dx * 1.6, -r * 1.25, -0.08), (dx * 2.2, -r * 1.3, -0.16)], [0.022, 0.024, 0.018],
                [(0, -1, 0)] * 3, C["jade"], thick=0.008)
    # puntas: tapa del caño en bisel, del color seco del bambú cortado
    for s in (-1.0, 1.0):
        z = s * (Lh - 0.02)
        k.tube([(0, 0, z), (0, 0, z + s * 0.018)], [r * 0.97, r * 0.9], 7, C["node2"], ups=[(0, -1, 0)] * 2, phase=0.2,
               cap0=False, cap1=True)
    return k


# --------------------------------------------------------------------------- armado
def finish_kit(kit, extra_mats):
    # la piel se autora con el color de paleta C["skin"] (que ninguna otra pieza usa) y acá pasa a Master_Skin
    uv = L.P.uv_of(C["skin"])
    lay = kit.uv
    for f in kit.bm.faces:
        if f.material_index == L.SLOT_PALETTE and f.loops and (f.loops[0][lay].uv - Vector(uv)).length < 1e-4:
            f.material_index = SLOT_SKIN
    obj = kit.finish()
    for n in extra_mats:
        m = bpy.data.materials.get(n) or bpy.data.materials.new(n)
        obj.data.materials.append(m)
    return obj


def ensure_extra_materials():
    for n, rgb in MAT_RGB.items():
        m = bpy.data.materials.get(n) or bpy.data.materials.new(n)
        m.diffuse_color = (*rgb, 1.0)


def join(kits, name, arm):
    objs, per = [], {}
    for bn, k in kits.items():
        o = finish_kit(k, EXTRA_MATS)
        per[bn] = tri_count(o)
        vg = {}
        for v in o.data.vertices:
            w = k.weights(v.co) if k.weights else {k.bone: 1.0}
            tot = sum(w.values())
            for n_, val in w.items():
                if n_ not in vg:
                    vg[n_] = o.vertex_groups.get(n_) or o.vertex_groups.new(name=n_)
                vg[n_].add([v.index], val / tot, 'REPLACE')
        objs.append(o)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    body = bpy.context.view_layer.objects.active
    body.name = name
    body.data.name = name
    body.parent = arm
    mod = body.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    clean_slots(body)
    return body, per


def clean_slots(o):
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.material_slot_remove_unused()
    o.select_set(False)


def rigid(kit, arm, rig):
    """Pieza rígida hija de su hueso (como la espada de Kokuyō): la malla queda en el espacio del hueso."""
    o = finish_kit(kit, EXTRA_MATS)
    M = rig.rest[kit.bone]
    # la caña se autora a lo largo de Z con el centro en el origen: se lleva a lo largo del hueso (Y) con el centro
    # en la mitad del hueso
    R = Matrix.Translation((0.0, MR.STAFF_LEN * 0.5, 0.0)) @ Matrix.Rotation(-math.pi / 2, 4, 'X')
    o.data.transform(R)
    o.parent = arm
    o.parent_type = 'BONE'
    o.parent_bone = kit.bone
    bpy.context.view_layer.update()
    o.matrix_world = M
    clean_slots(o)
    return o


def build(arm, rig):
    """Construye las mallas con skin (cuerpo, saco puesto, saco tirado) y el bastón, y las engancha a la armadura.
    Devuelve ({nombre: objeto}, stats)."""
    ensure_extra_materials()
    body_k, robe_k, thrown_k = {}, {}, {}
    build_leg_r(body_k)
    build_arm_r(body_k)
    right = [n for n in body_k]
    for bn in right:
        src = body_k[bn]
        ln = bn.replace("_R_", "_L_") if "_R_" in bn else bn[:-2] + "_L"
        body_k[ln] = mirror_kit(src, "part_" + ln, NA.side_swap(src.bone) or src.bone, weights=mirror_weights(src.weights))
    # los materiales que brillan van por lado: el espejo del derecho pasa al slot del izquierdo
    for bn, (a, b) in (("Hand_L", (SLOT_HAND_R, SLOT_HAND_L)), ("Arm_L", (SLOT_HAND_R, SLOT_HAND_L)),
                       ("Foot_L", (SLOT_FOOT_R, SLOT_FOOT_L))):
        for f in body_k[bn].bm.faces:
            if f.material_index == a:
                f.material_index = b
    build_hips(body_k)
    build_torso(body_k)
    build_sash(body_k)
    build_head(body_k)
    build_brows_whiskers(body_k)
    build_robe(robe_k)
    build_robe_thrown(thrown_k)
    body, pb = join(body_k, "Master_Body", arm)
    robe, pr = join(robe_k, "Master_Robe", arm)
    thrown, pt = join(thrown_k, "Master_RobeThrown", arm)
    staff = rigid(build_staff(), arm, rig)
    stats = {"body": tri_count(body), "robe": tri_count(robe), "thrown": tri_count(thrown), "staff": tri_count(staff)}
    print("TRIS_POR_PIEZA", sorted({**pb, **pr, **pt}.items(), key=lambda kv: -kv[1])[:16])
    return {"Master_Body": body, "Master_Robe": robe, "Master_RobeThrown": thrown, "Master_Staff": staff}, stats
