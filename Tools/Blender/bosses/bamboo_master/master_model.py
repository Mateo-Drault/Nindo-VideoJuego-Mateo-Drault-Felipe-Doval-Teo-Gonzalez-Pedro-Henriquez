"""Geometría de Chikuō, el Maestro del Bambú: viejo maestro de kung fu de 2.6 m, low-poly facetado.

Diseño (concepto c0 de la carpeta de bocetos, elegido entre cuatro; ver build_bamboo_master.py):
* Silueta de grulla: alto y flaco, piernas largas en pantalón negro ancho que se recoge en vendas blancas,
  brazos que llegan a la rodilla, manos y pies grandes. Nada que ver con el abuelo de Kaito (bajo y redondo,
  sombrero de paja, túnica índigo, barba corta): Chikuō es pelado, sin barba, con un rodete chico arriba.
* Lo que se lee desde la cámara del juego (52°, ~170 px de alto): la cabeza pelada, las CEJAS blancas larguísimas
  que barren hacia atrás y arriba como antenas, los BIGOTES que caen hasta el pecho, el saco marfil hasta la
  rodilla con puños y faja jade, las vendas blancas de las piernas.
* Fase 1: pelea con el saco puesto y la mano izquierda en la espalda. Fase 2: tira el saco (otro objeto,
  Master_Robe) y queda con la camisa sin mangas, los brazos fibrosos y las vendas.
* Las vendas de las palmas y las zapatillas tienen material propio por miembro (Master_WrapR/L,
  Master_FootR/L): el juego enciende SOLO el miembro que pega (dorado = parry, rojo = dash). Los ojos
  (Master_Eyes) se encienden en jade en la fase 2.
Colores de la paleta compartida; nada de rojo ni dorado en el cuerpo (son los colores de los avisos).
"""
import math
import bpy, bmesh
from mathutils import Vector, Matrix
import nindo_lib as L
import master_rig as MR
from master_kit import Kit, mirror_kit, mirror_weights, tri_count, smooth01, along_bone, blend

# --------------------------------------------------------------------------- materiales propios
SLOT_WRAP_R, SLOT_WRAP_L, SLOT_FOOT_R, SLOT_FOOT_L, SLOT_EYES = 4, 5, 6, 7, 8
EXTRA_MATS = ["Master_WrapR", "Master_WrapL", "Master_FootR", "Master_FootL", "Master_Eyes"]
WRAP_RGB = (0.92, 0.9, 0.85)
FOOT_RGB = (0.11, 0.11, 0.13)
EYES_RGB = (0.16, 0.13, 0.11)
EYES_GLOW_RGB = (0.45, 1.0, 0.8)          # el jade de la fase 2 (el juego lo enciende con SetGlow)

C = dict(skin="wood_pale", skin2="wood_light", skin3="sand", hair="white", hair2="cloth_white",
         ivory="cloth_white", ivory2="plaster", ivory3="plaster_shade", jade="grass_teal", jade2="leaf_pine",
         jade3="leaf_pine_dark", black="cloth_black", black2="ink", wrap="white", wrap2="stone_light", sole="white",
         button="ink", mouth="wood_dark")

KB = {b.name: b for b in MR.bones()}


def bh(n):
    return KB[n].head.copy()


def bt(n):
    return KB[n].tail.copy()


# --------------------------------------------------------------------------- anillos de sección propia
def ring(z, rx, ryf, ryb, n=12, cy=0.0, power=2.4, pinch=None):
    """Anillo horizontal con frente (-Y) y espalda de distinta profundidad; i = 0 al frente. pinch(a) -> factor
    del radio por ángulo (mejillas hundidas, cintura)."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        s, c = math.sin(a), -math.cos(a)
        e = 2.0 / power
        x = rx * math.copysign(abs(s) ** e, s)
        ry = ryf if c < 0 else ryb
        y = cy + ry * math.copysign(abs(c) ** e, c)
        k = pinch(a) if pinch else 1.0
        pts.append(Vector((x * k, cy + (y - cy) * k, z)))
    return pts


def torso_weights(co):
    """Tronco de la cadera al cuello: Hips -> Spine -> Chest con mezclas en las uniones (la camisa y el saco
    doblan en la cintura y el pecho sin quebrarse)."""
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
HEAD_PROFILE = [  # (z, medio ancho, profundidad al frente, profundidad atrás)
    (2.125, 0.045, 0.10, 0.05), (2.165, 0.072, 0.162, 0.085), (2.215, 0.098, 0.155, 0.11), (2.27, 0.11, 0.165, 0.13),
    (2.325, 0.117, 0.16, 0.142), (2.375, 0.121, 0.152, 0.15), (2.425, 0.124, 0.165, 0.155), (2.48, 0.12, 0.158, 0.15),
    (2.53, 0.1, 0.13, 0.125), (2.565, 0.068, 0.085, 0.085), (2.585, 0.03, 0.035, 0.035),
]
HEAD_CY = 0.012


def head_surface(z, a):
    """Punto aproximado de la superficie de la cabeza a la altura z y al ángulo a (0 = frente, + = su izquierda)."""
    rs = HEAD_PROFILE
    for (z0, w0, f0, b0), (z1, w1, f1, b1) in zip(rs[:-1], rs[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            w, f, b = w0 + (w1 - w0) * t, f0 + (f1 - f0) * t, b0 + (b1 - b0) * t
            break
    else:
        w, f, b = rs[-1][1], rs[-1][2], rs[-1][3]
    r = math.radians(a)
    s, c = math.sin(r), -math.cos(r)
    e = 2.0 / 2.4
    x = w * math.copysign(abs(s) ** e, s)
    y = HEAD_CY + (f if c < 0 else b) * math.copysign(abs(c) ** e, c)
    return Vector((x, y, z))


def build_head(kits):
    def w_head(co):
        if co.z < 2.17:
            return {"Head": 0.6, "Neck": 0.4}
        return {"Head": 1.0}
    k = kits["Head"] = Kit("part_Head", "Head", weights=w_head)

    def cheek(a):
        # mejillas hundidas bajo el pómulo (el viejo flaco): el anillo de la boca se mete a los costados
        d = abs(math.degrees(a) if a <= math.pi else math.degrees(a) - 360.0)
        return 1.0 - 0.1 * max(0.0, 1.0 - abs(d - 62.0) / 28.0)

    rings = []
    for i, (z, w, f, b) in enumerate(HEAD_PROFILE):
        rings.append(ring(z, w, f, b, n=12, cy=HEAD_CY, power=2.4, pinch=cheek if i in (2, 3) else None))
    cols = [C["skin2"], C["skin"], C["skin"], C["skin2"], C["skin"], C["skin"], C["skin"], C["skin3"], C["skin3"], C["skin3"]]
    part = k.rings_loft(rings, C["skin"], True, True, cols)
    # sombra bajo los pómulos (lo hundido de la cara se lee con dos facetas más oscuras a cada lado)
    for f in part.faces:
        cc = f.calc_center_median()
        if 2.22 < cc.z < 2.30 and abs(cc.x) > 0.06 and cc.y < -0.02:
            k.tag([f], C["skin2"])
    # nariz grande y ganchuda (lo que sobresale de perfil y en 3/4)
    ny = HEAD_CY - 0.152
    k.tube([(0, ny + 0.005, 2.385), (0, ny - 0.035, 2.335), (0, ny - 0.06, 2.3), (0, ny - 0.03, 2.282)],
           [(0.022, 0.012), (0.026, 0.02), (0.03, 0.022), (0.026, 0.012)], 5, C["skin"], ups=[(0, -1, 0.3)] * 4,
           phase=math.pi / 2)
    # arco de las cejas: deja los ojos hundidos en sombra
    fy = HEAD_CY - 0.16
    k.tube([(-0.105, fy + 0.03, 2.39), (-0.05, fy - 0.004, 2.405), (0.0, fy - 0.006, 2.402), (0.05, fy - 0.004, 2.405),
            (0.105, fy + 0.03, 2.39)], [0.022, 0.024, 0.02, 0.024, 0.022], 5, C["skin"], ups=[(0, 0, 1)] * 5, phase=math.pi / 5)
    for s in (-1.0, 1.0):
        # cuenca (sombra) y ojo entrecerrado: una ranura de material propio (se enciende en jade en la fase 2)
        eye = Vector((0.05 * s, fy + 0.012, 2.362))
        k.obox(eye + Vector((0, 0.004, 0.004)), (0.05, 0.012, 0.03), (1, 0, 0.18 * s), (0, 1, 0.2), C["skin2"])
        k.obox(eye, (0.036, 0.008, 0.011), (1, 0, 0.22 * s), (0, 1, 0.1), "black", slot=SLOT_EYES)
        # arrugas de la frente: tres trazos apenas más oscuros
        for j, z in enumerate((2.44, 2.462, 2.484)):
            k.obox((0.045 * s, head_surface(z, 18 * s).y + 0.004, z), (0.06 - 0.008 * j, 0.006, 0.006), (1, 0, 0.1 * s), (0, 1, 0),
                   C["skin2"])
        # orejas grandes de lóbulo largo (el sabio de los cuentos)
        ex = 0.118 * s
        k.tube([(ex, 0.02, 2.41), (ex + 0.03 * s, 0.03, 2.37), (ex + 0.032 * s, 0.03, 2.31), (ex + 0.02 * s, 0.015, 2.255)],
               [(0.012, 0.03), (0.016, 0.042), (0.016, 0.035), (0.014, 0.022)], 5, C["skin"],
               ups=[(0, -1, 0)] * 4, phase=math.pi / 5)
        k.obox((ex + 0.034 * s, 0.025, 2.345), (0.008, 0.035, 0.06), (1, 0, 0), (0, 1, 0), C["skin2"])
    # boca (casi tapada por el bigote) y el bigote corto sobre el labio, de donde nacen los bigotes largos
    k.obox((0, HEAD_CY - 0.158, 2.232), (0.05, 0.01, 0.008), (1, 0, 0), (0, 1, 0), C["mouth"])
    k.tube([(-0.055, HEAD_CY - 0.16, 2.252), (-0.02, HEAD_CY - 0.172, 2.262), (0.02, HEAD_CY - 0.172, 2.262),
            (0.055, HEAD_CY - 0.16, 2.252)], [0.016, 0.02, 0.02, 0.016], 5, C["hair"], ups=[(0, 0, 1)] * 4)
    # corona de pelo blanco atrás, de oreja a oreja (pelado arriba)
    back = []
    for a in range(100, 261, 16):
        back.append([head_surface(2.30, a) + (head_surface(2.30, a) - Vector((0, HEAD_CY, 2.30))).normalized() * 0.012,
                     head_surface(2.385, a) + (head_surface(2.385, a) - Vector((0, HEAD_CY, 2.385))).normalized() * 0.014])
    # dos capas (afuera y 6 mm adentro, cerradas en los bordes): una cara suelta se perdía con el culling
    vb = [[k.bm.verts.new(p) for p in col] for col in back]
    vi = [[k.bm.verts.new(p - (p - Vector((0, HEAD_CY, p.z))).normalized() * 0.006) for p in col] for col in back]
    for i in range(len(vb) - 1):
        k.bm.faces.new((vb[i][0], vb[i + 1][0], vb[i + 1][1], vb[i][1]))
        k.bm.faces.new((vi[i][1], vi[i + 1][1], vi[i + 1][0], vi[i][0]))
        k.bm.faces.new((vb[i][1], vb[i + 1][1], vi[i + 1][1], vi[i][1]))
        k.bm.faces.new((vi[i][0], vi[i + 1][0], vb[i + 1][0], vb[i][0]))
    k._new([v for c_ in vb + vi for v in c_], C["hair2"], None, None)
    # rodete: bolita blanca con el lazo jade y la punta del mechón
    k.gem((0, 0.02, 2.615), 0.042, C["hair"], sides=6, height=0.045)
    k.tube([(0, 0.02, 2.578), (0, 0.02, 2.598)], [0.032, 0.03], 6, C["jade"])
    k.tube([(0, 0.02, 2.65), (0, 0.035, 2.695)], [0.016, 0.003], 4, C["hair2"])

    # cuello flaco con la nuez (la mezcla con el pecho la reparte torso_weights del lado del pecho)
    def w_neck(co):
        if co.z < 2.06:
            return {"Neck": 0.5, "Chest": 0.5}
        return {"Neck": 1.0}
    kn = kits["Neck"] = Kit("part_Neck", "Neck", weights=w_neck)
    kn.tube([(0, 0.03, 2.0), (0, 0.025, 2.09), (0, 0.015, 2.18)], [(0.06, 0.056), (0.055, 0.05), (0.06, 0.06)], 8, C["skin"],
            phase=math.pi / 8)
    kn.gem((0, -0.03, 2.095), 0.014, C["skin"], sides=4, height=0.012, axis=(0, -1, 0))
    # tendones del cuello: dos facetas oscuras
    for s in (-1, 1):
        kn.obox((0.03 * s, -0.012, 2.08), (0.012, 0.01, 0.1), (1, 0, 0), (0, 1, 0.3 * -s), C["skin2"])


def build_brows_whiskers(kits):
    """Cejas: cintas anchas que miran arriba (se leen desde la cámara alta). Bigotes: cordones que se afinan."""
    for S, sg in (("R", 1.0), ("L", -1.0)):
        b1, b2 = "Brow_%s_1" % S, "Brow_%s_2" % S
        h, m, t = bh(b1), bt(b1), bt(b2)
        k1 = kits[b1] = Kit("part_" + b1, b1)
        mid = h.lerp(m, 0.5) + Vector((0, -0.01, 0.012))
        k1.strip([h + Vector((0.01 * sg, 0.004, -0.004)), mid, m + (t - m).normalized() * 0.02], [0.072, 0.07, 0.058],
                 [(0, -0.35, 1)] * 3, C["hair"], thick=[0.03, 0.026, 0.022])
        k2 = kits[b2] = Kit("part_" + b2, b2)
        mid2 = m.lerp(t, 0.55) + Vector((0, 0, 0.02))
        k2.strip([m - (t - m).normalized() * 0.02, mid2, t + Vector((0, 0.01, -0.03))], [0.058, 0.04, 0.012],
                 [(0, -0.2, 1)] * 3, C["hair2"], thick=[0.022, 0.018, 0.01])
        for seg, rads in ((1, (0.021, 0.018)), (2, (0.018, 0.013)), (3, (0.013, 0.004))):
            bn = "Whisker_%s_%d" % (S, seg)
            kw = kits[bn] = Kit("part_" + bn, bn)
            a, b = bh(bn), bt(bn)
            d = (b - a)
            kw.tube([a - d * 0.08, a + d * 0.5, b + d * (0.06 if seg < 3 else 0.0)], [rads[0], (rads[0] + rads[1]) * 0.5, rads[1]], 4,
                    C["hair"] if seg % 2 else C["hair2"], phase=math.pi / 4)


# --------------------------------------------------------------------------- tronco (camisa sin mangas)
SHIRT = [  # (z, medio ancho, frente, espalda)
    (1.30, 0.19, 0.15, 0.145), (1.42, 0.165, 0.125, 0.12), (1.54, 0.162, 0.122, 0.118), (1.66, 0.172, 0.128, 0.122),
    (1.78, 0.192, 0.136, 0.13), (1.89, 0.2, 0.132, 0.136), (1.965, 0.175, 0.112, 0.122), (2.02, 0.085, 0.07, 0.075),
]


def shirt_front_y(x, z):
    for (z0, w0, f0, _), (z1, w1, f1, _) in zip(SHIRT[:-1], SHIRT[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            w, f = w0 + (w1 - w0) * t, f0 + (f1 - f0) * t
            u = min(0.999, abs(x) / w)
            return -f * (1.0 - u ** 2.4) ** (1 / 2.4)
    return -0.12


def build_torso(kits):
    k = kits["Torso"] = Kit("part_Torso", "Chest", weights=torso_weights)
    rings = [ring(z, w, f, b, n=12, power=2.4) for z, w, f, b in SHIRT]
    cols = [C["ivory2"], C["ivory"], C["ivory"], C["ivory"], C["ivory"], C["ivory"], C["ivory"]]
    part = k.rings_loft(rings, C["ivory"], False, False, cols)
    # escote en V y botones de sapo: la línea oscura del frente que se lee aun de lejos
    for f in part.faces:
        cc = f.calc_center_median()
        if cc.z > 1.9 and abs(cc.x) < 0.05 and cc.y < 0:
            k.tag([f], C["skin"])
    for z in (1.5, 1.6, 1.7, 1.8):
        y = shirt_front_y(0.0, z) - 0.006
        k.obox((0.0, y, z), (0.05, 0.012, 0.014), (1, 0, 0), (0, 1, 0), C["button"])
        k.gem((0.0, y - 0.006, z), 0.012, C["button"], sides=4, height=0.01, axis=(0, -1, 0))
    # esternón y clavículas de piel en el escote
    k.obox((0.0, shirt_front_y(0.0, 1.95) - 0.004, 1.95), (0.07, 0.01, 0.08), (1, 0, 0), (0, 1, 0.2), C["skin"])
    # faja negra de la fase 2 (debajo del saco en la fase 1)
    kh = kits["Belt"] = Kit("part_Belt", "Hips", weights=torso_weights)
    kh.tube([(0, 0.0, 1.26), (0, 0.0, 1.32), (0, 0.0, 1.38)], [(0.205, 0.165), (0.21, 0.168), (0.198, 0.158)], 12, C["black"],
            phase=math.pi / 12, cap0=False, cap1=False, power=2.4, ring_colors=[C["black"], C["black2"]])
    kh.obox((0.07, -0.165, 1.31), (0.09, 0.05, 0.07), (1, 0, 0), (0, 1, 0), C["black2"], bevel=0.012)
    for s in (0.05, 0.1):
        kh.strip([(s, -0.17, 1.29), (s + 0.01, -0.18, 1.18), (s + 0.02, -0.18, 1.06)], [0.06, 0.06, 0.055], [(0, -1, 0)] * 3,
                 C["black2"], thick=0.015)
    # hombros y trapecios de piel (lo que la camisa sin mangas deja ver), sobre la clavícula
    for S, sg in (("R", -1.0), ("L", 1.0)):
        def w_clav(co, S=S):
            t = abs(co.x) / 0.32
            a = 0.5 * smooth01((t - 0.75) / 0.25)
            return {"Clav_" + S: 1.0 - a, "UpperArm_" + S: a}
        kc = kits["Clav_" + S] = Kit("part_Clav_" + S, "Clav_" + S, weights=w_clav)
        kc.tube([(0.07 * sg, 0.025, 2.005), (0.17 * sg, 0.025, 1.985), (0.27 * sg, 0.02, 1.955), (0.33 * sg, 0.02, 1.91)],
                [(0.045, 0.06), (0.05, 0.068), (0.06, 0.07), (0.07, 0.07)], 6, C["skin"],
                ups=[(0, 0, 1)] * 4, phase=math.pi / 6)


# --------------------------------------------------------------------------- brazos (piel, vendas, manos)
def build_arm_r(kits):
    S, E, Wr, Kn = MR.SHOULDER, MR.ELBOW, MR.WRIST, MR.KNUCKLE
    u = (E - S).normalized()
    l = (Wr - E).normalized()

    def w_upper(co):
        t = along_bone(co, S, E)
        return blend("UpperArm_R", t, "Clav_R", "Forearm_R", 0.14, 0.16)
    k = kits["UpperArm_R"] = Kit("part_UpperArm_R", "UpperArm_R", weights=w_upper)
    # deltoides y bíceps fibrosos: el brazo de un viejo que todavía pega
    k.tube([S - u * 0.05, S + u * 0.08, S + u * 0.22, S + u * 0.34, E - u * 0.02, E + u * 0.03],
           [(0.074, 0.07), (0.07, 0.072), (0.06, 0.066), (0.056, 0.06), (0.052, 0.052), (0.05, 0.05)], 8, C["skin"],
           ups=[(0, -1, 0)] * 6, phase=math.pi / 8, cap0=True, cap1=False)

    def w_fore(co):
        t = along_bone(co, E, Wr)
        return blend("Forearm_R", t, "UpperArm_R", "Hand_R", 0.16, 0.1)
    k = kits["Forearm_R"] = Kit("part_Forearm_R", "Forearm_R", weights=w_fore)
    pts = [E - l * 0.035, E + l * 0.1, E + l * 0.22, E + l * 0.36, Wr - l * 0.05, Wr + l * 0.01]
    rads = [(0.05, 0.05), (0.056, 0.054), (0.05, 0.048), (0.046, 0.044), (0.043, 0.04), (0.045, 0.042)]
    # vendas desde la mitad del antebrazo (con franjas): la última vuelta, en la muñeca, es del material que brilla
    cols = [C["skin"], C["skin"], C["wrap"], C["wrap2"], ("white", SLOT_WRAP_R)]
    k.tube(pts, rads, 8, C["skin"], ups=[(0, -1, 0)] * 6, phase=math.pi / 8, cap0=False, cap1=False, ring_colors=cols)
    # mano grande: palma vendada (brilla en el aviso), dedos sueltos y pulgar
    hb = Vector(Wr)
    hd = (Kn - Wr).normalized()
    dors = Vector((-1.0, 0.0, 0.0))
    dors = (dors - hd * dors.dot(hd)).normalized()       # dorso (afuera en reposo)
    across = hd.cross(dors).normalized()

    def w_hand(co):
        t = along_bone(co, Wr, Kn)
        return {"Hand_R": 1.0} if t > 0.12 else {"Hand_R": 0.75, "Forearm_R": 0.25}
    k = kits["Hand_R"] = Kit("part_Hand_R", "Hand_R", weights=w_hand)
    k.tube([hb - hd * 0.01, hb + hd * 0.04, hb + hd * 0.085, Kn + hd * 0.005],
           [(0.045, 0.024), (0.056, 0.026), (0.058, 0.025), (0.055, 0.022)], 6, C["skin"],
           ups=[dors] * 4, phase=math.pi / 6, power=3.0, ring_colors=[("white", SLOT_WRAP_R), ("white", SLOT_WRAP_R), C["skin"]])
    kf = kits["Fing_R"] = Kit("part_Fing_R", "Fing_R")
    for i, off in enumerate((-0.036, -0.012, 0.012, 0.035)):
        ln = (0.085, 0.1, 0.095, 0.075)[i]
        base = Kn + across * off - dors * 0.004
        kf.tube([base - hd * 0.012, base + hd * ln * 0.5 - dors * 0.004, base + hd * ln - dors * 0.012],
                [(0.012, 0.012), (0.011, 0.011), (0.008, 0.009)], 4, C["skin"] if i % 2 else C["skin"],
                ups=[dors] * 3, phase=math.pi / 4, cap0=False)
    tb = bh("Thumb_R")
    tt = bt("Thumb_R")
    kt = kits["Thumb_R"] = Kit("part_Thumb_R", "Thumb_R")
    kt.tube([tb - (tt - tb) * 0.2, tb + (tt - tb) * 0.5, tt], [(0.017, 0.016), (0.014, 0.013), (0.009, 0.009)], 4, C["skin"],
            ups=[dors] * 3, phase=math.pi / 4)


# --------------------------------------------------------------------------- piernas (pantalón ancho, vendas, zapatillas)
FOOT_RINGS = [(0.105, 0.058, 0.072, 0.05), (0.02, 0.07, 0.078, 0.064), (-0.1, 0.078, 0.066, 0.046), (-0.21, 0.07, 0.052, 0.032),
              (-0.275, 0.045, 0.042, 0.018)]


def build_leg_r(kits):
    x0 = MR.ANKLE.x
    k = kits["Foot_R"] = Kit("part_Foot_R", "Foot_R")
    hw = [(MR.SOLE_HEEL_Y, 0.05), (0.04, 0.068), (-0.12, 0.082), (-0.23, 0.07), (MR.SOLE_TOE_Y + 0.025, 0.04), (MR.SOLE_TOE_Y, 0.012)]
    s = -1.0
    sole = [(x0 + w * s, y) for y, w in hw] + [(x0 - w * s, y) for y, w in reversed(hw)]
    k.extrude_polygon(sole, 0.0, 0.03, C["sole"], top_color=C["sole"])
    k.tube([(x0, y, z) for y, _, z, _ in FOOT_RINGS], [(w, h) for _, w, _, h in FOOT_RINGS], 8, "black", ups=[(0, 0, 1)] * 5,
           phase=math.pi / 8, power=2.4, slot=SLOT_FOOT_R)
    # tobillo vendado (la vuelta de abajo brilla con la zapatilla en las patadas)
    k.tube([(x0, 0.0, 0.095), (x0, 0.0, 0.2)], [0.072, 0.07], 8, "white", phase=math.pi / 8, cap0=False, cap1=False, slot=SLOT_FOOT_R)
    kn = MR.KNEE

    def w_shin(co):
        t = along_bone(co, MR.KNEE, MR.ANKLE)
        return blend("Shin_R", t, "Thigh_R", "Foot_R", 0.14, 0.1)
    k = kits["Shin_R"] = Kit("part_Shin_R", "Shin_R", weights=w_shin)
    # pantalón que se infla bajo la rodilla y se recoge en las vendas (franjas claras y grises hasta el tobillo)
    k.tube([(kn.x, kn.y - 0.005, 0.74), (kn.x, kn.y + 0.005, 0.64), (x0, -0.02, 0.56), (x0, -0.01, 0.49)],
           [0.13, 0.142, 0.13, 0.092], 8, C["black"], phase=math.pi / 8, cap0=False, cap1=False,
           ring_colors=[C["black"], C["black"], C["black2"]])
    zs = [0.5, 0.44, 0.38, 0.32, 0.26, 0.2]
    pts = [(x0, -0.008 + 0.002 * i, z) for i, z in enumerate(zs)]
    rads = [0.088, 0.084, 0.08, 0.077, 0.074, 0.072]
    k.tube(pts, rads, 8, C["wrap"], phase=math.pi / 8 + 0.2, cap0=False, cap1=False,
           ring_colors=[C["wrap"], C["wrap2"], C["wrap"], C["wrap2"], C["wrap"]])
    hip = MR.HIP_J

    def w_thigh(co):
        t = along_bone(co, MR.HIP_J, MR.KNEE)
        w = blend("Thigh_R", t, "Hips", "Shin_R", 0.22, 0.12)
        return w
    k = kits["Thigh_R"] = Kit("part_Thigh_R", "Thigh_R", weights=w_thigh)
    k.tube([(hip.x * 0.9, 0.0, 1.27), (hip.x * 1.02, -0.01, 1.12), (kn.x * 1.03, -0.03, 0.96), (kn.x, -0.05, 0.8), (kn.x, -0.05, 0.69)],
           [(0.16, 0.16), (0.176, 0.172), (0.172, 0.166), (0.15, 0.148), (0.13, 0.13)], 8, C["black"], phase=math.pi / 8,
           cap0=False, cap1=False, ring_colors=[C["black"], C["black"], C["black2"], C["black"]])


def build_hips(kits):
    k = kits["Hips"] = Kit("part_Hips", "Hips")
    # cadera del pantalón: tapa el tiro entre los dos muslos
    k.tube([(0, 0.0, 1.06), (0, 0.0, 1.18), (0, 0.0, 1.3)], [(0.2, 0.16), (0.225, 0.18), (0.205, 0.165)], 12, C["black"],
           phase=math.pi / 12, cap0=True, cap1=False, power=2.4)


# --------------------------------------------------------------------------- el saco (objeto aparte)
ROBE_BODY = [  # (z, medio ancho, frente, espalda): un poco más grande que la camisa
    (1.255, 0.214, 0.172, 0.166), (1.42, 0.198, 0.158, 0.152), (1.6, 0.205, 0.16, 0.155), (1.76, 0.232, 0.17, 0.165),
    (1.9, 0.262, 0.163, 0.172), (1.98, 0.215, 0.13, 0.142), (2.025, 0.095, 0.088, 0.09),
]


def robe_front_y(x, z):
    for (z0, w0, f0, _), (z1, w1, f1, _) in zip(ROBE_BODY[:-1], ROBE_BODY[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            w, f = w0 + (w1 - w0) * t, f0 + (f1 - f0) * t
            u = min(0.999, abs(x) / w)
            return -f * (1.0 - u ** 2.4) ** (1 / 2.4)
    return -0.16


def build_robe(kits):
    k = kits["Robe_Body"] = Kit("robe_Body", "Chest", weights=torso_weights)
    rings = [ring(z, w, f, b, n=14, power=2.4) for z, w, f, b in ROBE_BODY]
    k.rings_loft(rings, C["ivory"], False, False, [C["ivory2"], C["ivory"], C["ivory"], C["ivory"], C["ivory"], C["ivory"]])
    # cuello mao, la línea de botones de sapo y la abertura cruzada del frente
    k.tube([(0, 0.01, 2.015), (0, 0.012, 2.07), (0, 0.014, 2.1)], [(0.092, 0.085), (0.086, 0.08), (0.084, 0.078)], 10, C["ivory"],
           phase=math.pi / 10, cap0=False, cap1=False, ring_colors=[C["ivory"], C["ivory2"]])
    for z in (1.47, 1.58, 1.69, 1.8, 1.91):
        y = robe_front_y(0.0, z) - 0.006
        k.obox((0.0, y, z), (0.07, 0.014, 0.016), (1, 0, 0), (0, 1, 0), C["button"])
        k.gem((-0.035, y - 0.004, z), 0.013, C["button"], sides=4, height=0.011, axis=(0, -1, 0))
        k.gem((0.035, y - 0.004, z), 0.013, C["button"], sides=4, height=0.011, axis=(0, -1, 0))
    k.obox((0.0, robe_front_y(0.0, 1.72) - 0.003, 1.72), (0.012, 0.006, 0.54), (1, 0, 0), (0, 1, 0), C["ivory3"])
    # faja jade con el nudo a su izquierda, adelante
    ks = kits["Robe_Sash"] = Kit("robe_Sash", "Hips", weights=torso_weights)
    ks.tube([(0, 0.0, 1.255), (0, 0.0, 1.32), (0, 0.0, 1.41)], [(0.232, 0.186), (0.238, 0.19), (0.222, 0.178)], 14, C["jade"],
            phase=math.pi / 14, cap0=False, cap1=False, power=2.4, ring_colors=[C["jade"], C["jade2"]])
    ks.obox(MR.SASH_KNOT + Vector((0.035, -0.012, 0.02)), (0.1, 0.06, 0.085), (1, 0, 0.1), (0, 1, 0), C["jade2"], bevel=0.014,
            up_color=C["jade"])
    for bn, w0 in (("Sash_A", 0.1), ("Sash_B", 0.085)):
        for seg in (1, 2):
            b = "%s_%d" % (bn, seg)
            kk = kits[b] = Kit("robe_" + b, b)
            a_, t_ = bh(b), bt(b)
            d = t_ - a_
            kk.strip([a_ - d * 0.06, a_ + d * 0.5, t_ + d * (0.04 if seg == 1 else 0.0)], [w0, w0 * 1.04, w0 * (1.08 if seg == 2 else 1.06)],
                     [(0.1, -1, 0)] * 3, C["jade"] if seg == 1 else C["jade2"], thick=0.02)
    # faldones: dos tramos por paño, con un ruedo un tono más oscuro (la tela gruesa del saco)
    for a in MR.ROBE_ANGLES:
        half = 41.0
        cols = [a - half, a - half / 3, a + half / 3, a + half]
        for seg in (1, 2):
            bn = MR.robe_name(a, seg)
            kk = kits[bn] = Kit("robe_" + bn, bn)
            d0 = 0.0 if seg == 1 else MR.ROBE_LEN[0]
            d1 = d0 + MR.ROBE_LEN[seg - 1] + (0.03 if seg == 1 else 0.0)
            tops, bots = [], []
            for aa in cols:
                hh, dd, oo, tt = MR.robe_frame(aa)
                tops.append(hh + dd * (d0 - (0.02 if seg == 2 else 0.0)) + oo * 0.004 * seg)
                bots.append(hh + dd * d1 + oo * 0.004 * seg)
            vt = [kk.bm.verts.new(p) for p in tops]
            vb = [kk.bm.verts.new(p) for p in bots]
            # espesor: la cara de adentro, 1.8 cm hacia el cuerpo (el paño se ve igual de los dos lados al patear)
            inner = [kk.bm.verts.new(p - (MR.robe_frame(aa)[2]) * 0.018) for p, aa in zip(tops, cols)]
            innb = [kk.bm.verts.new(p - (MR.robe_frame(aa)[2]) * 0.018) for p, aa in zip(bots, cols)]
            fs_out, fs_in, rim = [], [], []
            for i in range(len(cols) - 1):
                fs_out.append(kk.bm.faces.new((vt[i], vt[i + 1], vb[i + 1], vb[i])))
                fs_in.append(kk.bm.faces.new((inner[i + 1], inner[i], innb[i], innb[i + 1])))
                rim.append(kk.bm.faces.new((vb[i], vb[i + 1], innb[i + 1], innb[i])))
            rim.append(kk.bm.faces.new((vt[0], vb[0], innb[0], inner[0])))
            rim.append(kk.bm.faces.new((vt[-1], inner[-1], innb[-1], vb[-1])))
            kk._new(vt + vb + inner + innb, C["ivory"], None, None)
            kk.tag(fs_in, C["ivory3"])
            if seg == 2:
                kk.tag(rim, C["ivory3"])
    # mangas anchas con el puño jade (la mano vendada asoma del puño)
    S, E, Wr = MR.SHOULDER, MR.ELBOW, MR.WRIST
    u = (E - S).normalized()
    l = (Wr - E).normalized()

    def w_sleeve(co):
        t_up = along_bone(co, S, E)
        if t_up < 1.0:
            return blend("UpperArm_R", t_up, "Clav_R", "Forearm_R", 0.18, 0.18)
        t = along_bone(co, E, Wr)
        return blend("Forearm_R", t, "UpperArm_R", None, 0.18, 0.1)
    k = kits["Robe_Sleeve_R"] = Kit("robe_Sleeve_R", "UpperArm_R", weights=w_sleeve)
    pts = [S - u * 0.07, S + u * 0.12, S + u * 0.3, E, E + l * 0.14, E + l * 0.27, E + l * 0.31]
    rads = [(0.098, 0.09), (0.1, 0.098), (0.102, 0.1), (0.106, 0.104), (0.118, 0.114), (0.13, 0.124), (0.132, 0.126)]
    part = k.tube(pts, rads, 8, C["ivory"], ups=[(0, -1, 0)] * 7, phase=math.pi / 8, cap0=False, cap1=False,
                  ring_colors=[C["ivory"], C["ivory"], C["ivory"], C["ivory"], C["jade"], C["jade2"]])
    # boca de la manga: el interior oscuro (desde arriba el puño se lee como un anillo jade con un hueco)
    c_end = E + l * 0.31
    k.tube([c_end - l * 0.01, c_end - l * 0.05], [(0.125, 0.12), (0.06, 0.06)], 8, C["jade3"], ups=[(0, -1, 0)] * 2,
           phase=math.pi / 8, cap0=False, cap1=False)
    kits["Robe_Sleeve_L"] = mirror_kit(k, "robe_Sleeve_L", "UpperArm_L", weights=mirror_weights(w_sleeve))


def build_robe_thrown(kits):
    """El saco tirado: un saco aplanado (frente y espalda juntos) de 2.5 cm de espesor, con sus mangas, la faja y
    los botones. Vive en la espalda (oculto) y solo se ve cuando vuela en el cambio de fase."""
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
    rows = [(1.99, 0.1), (1.94, 0.24), (1.8, 0.23), (1.6, 0.22), (1.42, 0.23), (1.28, 0.26), (1.12, 0.29)]
    cols = [C["ivory"], C["ivory"], C["ivory"], C["ivory"], C["jade"], C["ivory"]]
    rings_ = []
    for z, w in rows:
        rings_.append([Vector((-w, y0 - 0.0125, z)), Vector((w, y0 - 0.0125, z)), Vector((w, y0 + 0.0125, z)), Vector((-w, y0 + 0.0125, z))])
    k.rings_loft(rings_, C["ivory"], True, True, cols)
    for z in (1.55, 1.66, 1.77, 1.88):
        k.obox((0.0, y0 - 0.016, z), (0.07, 0.008, 0.016), (1, 0, 0), (0, 1, 0), C["button"])
    for S, sg in (("R", -1.0), ("L", 1.0)):
        def w_arm(co, S=S, sg=sg):
            x = co.x * sg
            if x > 0.2:
                return {"RobeT_Arm" + S: 1.0}
            a = smooth01((x - 0.1) / 0.1)
            return {"RobeT_Root": 1.0 - a, "RobeT_Arm" + S: a}
        ka = kits["RobeT_Arm" + S] = Kit("thrown_Arm" + S, "RobeT_Arm" + S, weights=w_arm)
        pts = [(0.12 * sg, y0, 1.9), (0.3 * sg, y0, 1.85), (0.48 * sg, y0, 1.8), (0.56 * sg, y0, 1.775)]
        rads = [(0.026, 0.1), (0.026, 0.11), (0.028, 0.125), (0.028, 0.128)]
        ka.tube(pts, rads, 4, C["ivory"], ups=[(0, 0, 1)] * 4, phase=math.pi / 4, ring_colors=[C["ivory"], C["ivory"], C["jade"]])


# --------------------------------------------------------------------------- armado
def finish_kit(kit, extra_mats):
    obj = kit.finish()
    for n in extra_mats:
        m = bpy.data.materials.get(n) or bpy.data.materials.new(n)
        obj.data.materials.append(m)
    return obj


def ensure_extra_materials():
    for n, rgb in (("Master_WrapR", WRAP_RGB), ("Master_WrapL", WRAP_RGB), ("Master_FootR", FOOT_RGB), ("Master_FootL", FOOT_RGB),
                   ("Master_Eyes", EYES_RGB)):
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
    bpy.ops.object.select_all(action='DESELECT')
    body.select_set(True)
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.material_slot_remove_unused()
    body.select_set(False)
    return body, per


def build(arm, rig):
    """Construye las tres mallas con skin (cuerpo, saco puesto, saco tirado) y las engancha a la armadura.
    Devuelve ({nombre: objeto}, stats)."""
    ensure_extra_materials()
    body_k, robe_k, thrown_k = {}, {}, {}
    build_leg_r(body_k)
    build_arm_r(body_k)
    for bn in ("Foot_R", "Shin_R", "Thigh_R", "UpperArm_R", "Forearm_R", "Hand_R", "Fing_R", "Thumb_R"):
        src = body_k[bn]
        ln = bn[:-2] + "_L"
        body_k[ln] = mirror_kit(src, "part_" + ln, ln, weights=mirror_weights(src.weights))
    # los materiales que brillan van por lado: el espejo del derecho pasa al slot del izquierdo
    for bn, (a, b) in (("Hand_L", (SLOT_WRAP_R, SLOT_WRAP_L)), ("Forearm_L", (SLOT_WRAP_R, SLOT_WRAP_L)),
                       ("Foot_L", (SLOT_FOOT_R, SLOT_FOOT_L))):
        for f in body_k[bn].bm.faces:
            if f.material_index == a:
                f.material_index = b
    build_hips(body_k)
    build_torso(body_k)
    build_head(body_k)
    build_brows_whiskers(body_k)
    build_robe(robe_k)
    build_robe_thrown(thrown_k)
    body, pb = join(body_k, "Master_Body", arm)
    robe, pr = join(robe_k, "Master_Robe", arm)
    thrown, pt = join(thrown_k, "Master_RobeThrown", arm)
    stats = {"body": tri_count(body), "robe": tri_count(robe), "thrown": tri_count(thrown)}
    print("TRIS_POR_PIEZA", sorted({**pb, **pr, **pt}.items(), key=lambda kv: -kv[1])[:14])
    return {"Master_Body": body, "Master_Robe": robe, "Master_RobeThrown": thrown}, stats
