"""Geometría del Chikuō ermitaño (fase C4): el concepto elegido 'opción 6' (Docs/handoff/conceptos/chikuo_v2/elegido_*.jpg)
al pie de la letra, en el low-poly facetado de Nindō.

Lo que se lee desde la cámara del juego (52°, 24 m: un personaje de 1.5 m mide ~100 px y Chikuō parado ~160 px) es la
forma y el valor, no el detalle:
  * arriba del todo el blanco: el moño facetado con su cordón verde y la ramita, las cejas en púas más anchas que la
    cabeza y la barba larga anudada hasta el ombligo (una franja blanca de ~1 m entre las hojas verdes);
  * la capa de hojas de bambú en tres tonos (claras arriba, oscuras abajo: más oscura que sus cañas), abierta adelante
    (se ve el gi entero) y larga atrás como una parva, con 26 cascabeles huecos color paja-oro en racimos por los
    hombros y la espalda alta: la luz de la pelea (dos materiales que el juego enciende: Chikuo_GlintChimesHi en los
    hombros, Lo en la espalda);
  * el gi salvia con el ribete tostado (cuello cruzado, puños, ruedo), la faja verde ancha anudada con dos colas
    tostadas, el pantalón ancho de la misma tela que se infla en la rodilla, las polainas grises con vendas oscuras en X
    y las sandalias-zapato negras con suela de paja y una tira en diagonal;
  * la flauta-bastón paja-amarilla de 2.1 m (objeto rígido en el hueso Staff): nudos con cordón verde, seis agujeros en
    el tercio de arriba, el agujero de soplar, el vendado oscuro cerca de la punta de abajo y las bocas huecas.
De cerca (la presentación, los cambios de fase), medido sobre la hoja de modelado a escala (chikuo_overlay): la cara
ancha de pómulos altos, calvo arriba en punta de pala con el pelo blanco peinado hacia el moño, cejas en dos llamas,
orejas en punta, nariz larga y ganchuda, ojos entornados, la sonrisa en medialuna de pómulo a pómulo con dientes en punta,
arrugas en facetas; la cabeza sobre un cuello que se inclina hacia adelante (el viejo encorvado).
Colores de la paleta compartida salvo la piel (Chikuo_Skin: la paleta no tiene un tostado que no quede gris bajo la
luna) y los materiales que brillan; ningún rojo ni dorado en el cuerpo (son los colores de los avisos): el paja-oro de
los cascabeles y la flauta es el de su material propio, que nace sin emisión.
"""
import math
import random
import bpy
from mathutils import Vector, Matrix
import nindo_lib as L
import chikuo_rig as CR
from chikuo_kit import (Kit, mirror_kit, mirror_weights, tri_count, smooth01, along_bone, chain_weights, chain_samples,
                        blend, side_name)

# --------------------------------------------------------------------------- materiales propios
SLOT_SKIN, SLOT_CHIME_HI, SLOT_CHIME_LO, SLOT_STAFF, SLOT_FOOT_R, SLOT_FOOT_L, SLOT_GI = 4, 5, 6, 7, 8, 9, 10
EXTRA_MATS = ["Chikuo_Skin", "Chikuo_GlintChimesHi", "Chikuo_GlintChimesLo", "Chikuo_GlintStaff", "Chikuo_GlintFootR",
              "Chikuo_GlintFootL", "Chikuo_Gi"]
# piel curtida de ermitaño (la del concepto: #dda982 a la luz, #98694f en la sombra); las sombras van con la paleta
SKIN_RGB = (0.82, 0.63, 0.49)
# el gi salvia del concepto, en el grass_teal de la sección 14 del diseño (#3e6b55): el gris verdoso del concepto
# (#555f52) bajo la luna del juego salía gris azulado, del valor del sendero, y se perdía "el gi verde de karate"; el
# teal se separa de las hojas oliva de la capa por el tono. El pantalón es de la misma tela
GI_RGB = (0.243, 0.42, 0.333)
# cascabeles paja-oro (el concepto: #e1a96c) y la flauta paja-amarilla, más verde (bambú seco): se distinguen entre sí
CHIME_RGB = (0.90, 0.68, 0.40)
STAFF_RGB = (0.80, 0.74, 0.35)
# las sandalias-zapato: negro azulado (con 0.13 en el canal más alto CharacterFactory.LiftBlacks no las toca)
SHOE_RGB = (0.115, 0.11, 0.13)
MAT_RGB = {"Chikuo_Skin": SKIN_RGB, "Chikuo_GlintChimesHi": CHIME_RGB, "Chikuo_GlintChimesLo": CHIME_RGB,
           "Chikuo_GlintStaff": STAFF_RGB, "Chikuo_GlintFootR": SHOE_RGB, "Chikuo_GlintFootL": SHOE_RGB, "Chikuo_Gi": GI_RGB}
# el señuelo de hojas (Tricks: la misma malla con todos los slots en este material, sin brillo): no está en el FBX,
# generate_assets escribe su .mat desde el sidecar

# la piel: un solo tono (Chikuo_Skin) y una sola sombra (la del concepto, #98694f: wood_light) en las cuencas, los
# surcos y los nudillos; el ribete y las colas de la faja en el tostado del concepto (#c59b6e: wood_pale) y su sombra
C = dict(skin="lantern_paper", skin2="wood_light", skin3="wood_light", mouth="wood_dark",
         white="white", white2="cloth_white", white3="plaster_shade",
         gi="copper_green", gi2="tatami_edge", gi3="leaf_pine_dark",
         trim="wood_pale", trim2="wood_light",
         sash="moss", sash2="bamboo_dark", sash3="grass_dry",
         pants="copper_green", pants2="tatami_edge",
         leg="tatami_edge", leg2="stone_moss",
         wrap="cloth_black", wrap2="stone_dark",
         sole="rope", sole2="thatch", strap="wood_pale",
         leaf1="stone_moss", leaf1b="grass_dry", leaf1c="reed", leaf2="bamboo_dark", leaf3="tatami_edge", shell="bamboo_dark",
         shell_in="moss", leafu="bamboo_dark",
         cord="wood_dark", hole="wood_dark", node="wheat_dark",
         staff_node="bamboo_dry", staff_cord="leaf_dark", staff_grip="ink", staff_grip2="iron", staff_hole="wood_dark",
         eye="ink", eyew="paper", knot="moss", knot2="leaf_dark")

KB = {b.name: b for b in CR.bones()}


def bh(n):
    return KB[n].head.copy()


def bt(n):
    return KB[n].tail.copy()


def ramp(z, z0, z1):
    return smooth01((z - z0) / (z1 - z0))


# =========================================================================== cabeza
# La cabeza se autora en su marco propio (chikuo_rig.head_t la lleva al modelo: más ancha, adelantada y sobre el cuello
# inclinado). Perfil radial: por altura, el centro (y) y la distancia al eje a los 0, 22.5 ... 180° (0 = frente,
# espejado del otro lado). La cara del concepto: el cráneo grande y pelado arriba, las sienes anchas, el arco de la
# ceja que sobresale y hunde los ojos, los pómulos altos y marcados, las mejillas chupadas y la cara que se angosta en
# V hasta un mentón chico (bajo la barba). La banda de la boca (2.056-2.068) es el medio de la sonrisa: abajo va con la
# quijada
HEAD_RINGS = [
    (2.024, -0.030, [0.050, 0.046, 0.038, 0.032, 0.030, 0.030, 0.030, 0.030, 0.030]),
    (2.042, -0.020, [0.072, 0.067, 0.054, 0.046, 0.044, 0.044, 0.046, 0.048, 0.050]),
    (2.056, -0.014, [0.084, 0.080, 0.064, 0.055, 0.053, 0.055, 0.059, 0.063, 0.065]),
    (2.068, -0.011, [0.089, 0.085, 0.069, 0.060, 0.058, 0.060, 0.065, 0.070, 0.072]),
    (2.083, -0.009, [0.093, 0.088, 0.071, 0.063, 0.063, 0.066, 0.072, 0.077, 0.079]),
    (2.100, -0.006, [0.096, 0.092, 0.080, 0.072, 0.071, 0.077, 0.085, 0.090, 0.092]),
    (2.118, -0.004, [0.097, 0.096, 0.094, 0.090, 0.085, 0.089, 0.097, 0.102, 0.104]),
    (2.140, -0.003, [0.092, 0.088, 0.086, 0.085, 0.085, 0.090, 0.099, 0.105, 0.108]),
    (2.165, -0.002, [0.095, 0.090, 0.087, 0.084, 0.084, 0.090, 0.100, 0.107, 0.110]),
    (2.182, -0.001, [0.104, 0.102, 0.095, 0.087, 0.086, 0.092, 0.101, 0.108, 0.111]),
    (2.205, 0.002, [0.098, 0.097, 0.093, 0.088, 0.087, 0.093, 0.101, 0.107, 0.110]),
    (2.228, 0.005, [0.088, 0.088, 0.086, 0.084, 0.085, 0.091, 0.097, 0.101, 0.102]),
    (2.248, 0.008, [0.070, 0.070, 0.069, 0.068, 0.069, 0.074, 0.079, 0.081, 0.082]),
    (2.262, 0.010, [0.044, 0.044, 0.044, 0.044, 0.045, 0.048, 0.051, 0.053, 0.053]),
]
HEAD_SCALE = 1.05
HEAD_TOP = (0.0, 0.012, 2.270)
HEAD_SIDES = 16
MOUTH_Z = CR.MOUTH_S.z       # el medio de la sonrisa en el centro (sube hacia las comisuras)
GRIN_W = 0.062               # medio ancho de la sonrisa (marco de autoría; en el modelo 7.3 cm)
GRIN_RISE = 0.033            # cuánto suben las comisuras sobre el centro (la medialuna)


def head_r(z, a):
    """(centro y, radio) de la cabeza a la altura z y al ángulo a (grados, 0 = frente)."""
    a = abs(((a + 180.0) % 360.0) - 180.0)
    k = a / 22.5
    i0 = min(7, int(k))
    t = k - i0
    rows = HEAD_RINGS

    def at(row):
        return (row[2][i0] + (row[2][i0 + 1] - row[2][i0]) * t) * HEAD_SCALE
    if z <= rows[0][0]:
        return rows[0][1], at(rows[0])
    for r0, r1 in zip(rows[:-1], rows[1:]):
        if r0[0] <= z <= r1[0]:
            u = (z - r0[0]) / (r1[0] - r0[0])
            return r0[1] + (r1[1] - r0[1]) * u, at(r0) + (at(r1) - at(r0)) * u
    return rows[-1][1], at(rows[-1])


def head_surface(z, a, out=0.0):
    yc, r = head_r(z, a)
    r += out
    ar = math.radians(a)
    return Vector((math.sin(ar) * r, yc - math.cos(ar) * r, z))


def onto_head(p, out=0.0):
    """El punto de la superficie de la cabeza (más 'out') a la altura y el ángulo de p (marco de autoría)."""
    return head_surface(p.z, head_angle(p), out)


def head_angle(co):
    return math.degrees(math.atan2(co.x, -co.y))


def grin_at(x, z, out=0.0):
    """El punto de la cara (más 'out') con esa x y esa altura: el ángulo se busca para que la x no cambie."""
    a = 30.0
    for _ in range(4):
        r = head_r(z, a)[1] + out
        a = math.degrees(math.asin(max(-1.0, min(1.0, x / r))))
    return head_surface(z, a, out)


def grin_mid(x):
    """Altura del medio de la sonrisa en x (marco de autoría): sube en medialuna hasta las comisuras."""
    u = min(1.0, abs(x) / GRIN_W)
    return MOUTH_Z + GRIN_RISE * u * u


def grin_open(x):
    """Medio alto de la boca en x: los dientes se ven enteros en el centro y la boca se cierra en las comisuras."""
    u = min(1.0, abs(x) / GRIN_W)
    return 0.0115 * (1.0 - u ** 1.7) + 0.0012


def jaw_line(co):
    """La línea que separa la cabeza de la quijada: el medio de la sonrisa adelante y, hacia atrás, la bisagra delante
    de la oreja."""
    a = abs(head_angle(co))
    return grin_mid(co.x) + 0.030 * smooth01((a - 50.0) / 35.0)


def jaw_weight(co):
    """Cuánto sigue a la quijada un punto de la cara (marco de autoría): todo lo de abajo de la sonrisa adelante (las
    mejillas de abajo bajan con la boca abierta; la nuca no)."""
    a = abs(head_angle(co))
    if a > 105.0:
        return 0.0
    w = 1.0 - smooth01((co.z - (jaw_line(co) - 0.005)) / 0.010)
    return w * (1.0 - smooth01((a - 85.0) / 20.0))


def corner_falloff(x):
    """La boca abre en el centro y las comisuras quedan en la cara: la risa es una medialuna, no un cajón de dientes."""
    return 1.0 - smooth01((abs(x) - 0.030) / 0.034)


def _with_corners(co, w):
    """Suma las comisuras (MouthCorner_*) y los cachetes (Cheek_*) a unos pesos de la cara."""
    for S in "RL":
        c0 = CR.mx(CR.CHEEK_S[0]) if S == "L" else CR.CHEEK_S[0]
        d = (co - (c0 + Vector((0.0, -0.016, 0.0)))).length
        if d < 0.042 and co.z > grin_mid(co.x) + 0.004:
            k = 0.85 * (1.0 - smooth01(d / 0.042))
            w = {n: v * (1.0 - k) for n, v in w.items()}
            w["Cheek_" + S] = k
        m0 = CR.mx(CR.CORNER_S[0]) if S == "L" else CR.CORNER_S[0]
        d = (co - m0).length
        if d < 0.026:
            k = 0.75 * (1.0 - smooth01(d / 0.026))
            w = {n: v * (1.0 - k) for n, v in w.items()}
            w["MouthCorner_" + S] = w.get("MouthCorner_" + S, 0.0) + k
    return w


def face_jaw(co):
    """La quijada de la piel (marco de autoría): cerca de la boca solo se lleva el centro (las comisuras quedan en la
    cara: la risa abre una medialuna); el mentón entero baja."""
    near = smooth01((co.z - (grin_mid(co.x) - 0.030)) / 0.020)
    return jaw_weight(co) * (1.0 - near * (1.0 - corner_falloff(co.x)))


def w_face(co):
    """Pesos de la cara (marco de autoría): cabeza, quijada, cachetes y comisuras; la nuca baja con el cuello."""
    j = face_jaw(co)
    w = {"Head": 1.0 - j}
    if j > 0.0:
        w["Jaw"] = j
    w = _with_corners(co, w)
    if co.z < 2.06 and abs(head_angle(co)) > 100.0:
        k = 0.45 * (1.0 - smooth01((co.z - 2.03) / 0.03))
        w = {n: v * (1.0 - k) for n, v in w.items()}
        w["Neck"] = w.get("Neck", 0.0) + k
    return w


def w_mouth_lo(co):
    """La mitad de abajo de la boca (labio, placa oscura y dientes): con la quijada en el centro, con la cara en las
    comisuras."""
    j = corner_falloff(co.x)
    w = {"Jaw": j, "Head": 1.0 - j} if j < 1.0 else {"Jaw": 1.0}
    return _with_corners(co, {n: v for n, v in w.items() if v > 0.0})


def w_mouth_up(co):
    return _with_corners(co, {"Head": 1.0})


# las hileras de la boca (las dos de la banda y sus vecinas) se curvan en medialuna: la banda oscura sigue la sonrisa y
# queda justo debajo de sus placas (se ve solo cuando la quijada abre)
BAND = {2.042: "below", 2.056: "lo", 2.068: "hi", 2.083: "above", 2.100: "above2"}


def head_ring(z, n=HEAD_SIDES):
    pts = []
    role = BAND.get(z)
    for i in range(n):
        a = 360.0 * i / n
        p = head_surface(z, a)
        if role:
            k = 1.0 - smooth01((abs(((a + 180.0) % 360.0) - 180.0) - 50.0) / 30.0)
            zm, h = grin_mid(p.x), grin_open(p.x)
            above = max(2.083 + 0.65 * (zm - MOUTH_Z), zm + 0.85 * h + 0.006)
            zt = {"lo": zm - 0.85 * h, "hi": zm + 0.85 * h, "below": z + 0.55 * (zm - MOUTH_Z), "above": above,
                  "above2": max(z, above + 0.008)}[role]
            p = head_surface(z + (zt - z) * k, a)
        pts.append(p)
    return pts


def build_head(kits):
    k = kits["Head"] = Kit("part_Head", "Head", weights=w_face)
    rings = [head_ring(z) for z, _, _ in HEAD_RINGS]
    part = k.rings_loft(rings, C["skin"], True, False)
    top = k.bm.verts.new(HEAD_TOP)
    last = part.verts[-HEAD_SIDES:]
    k.tag([k.bm.faces.new((last[i], last[(i + 1) % HEAD_SIDES], top)) for i in range(HEAD_SIDES)], C["skin"])
    # un solo tono de piel en la cara y la calva (la hoja: una piel curtida pareja) y un solo tono de sombra en las
    # cuencas, bajo el pómulo y en el costado del mentón; la banda del medio de la boca oscura (la garganta al reírse)
    for f in part.faces:
        c = f.calc_center_median()
        a = abs(head_angle(c))
        lo, hi = grin_mid(c.x) - 0.85 * grin_open(c.x), grin_mid(c.x) + 0.85 * grin_open(c.x)
        if a < 50 and lo - 0.002 < c.z < hi + 0.002 and len(f.verts) == 4:
            k.tag([f], C["mouth"])
        elif 2.140 < c.z < 2.170 and 6 < a < 46:
            k.tag([f], C["skin3"])
        elif 2.083 < c.z < 2.100 and 52 < a < 80:
            k.tag([f], C["skin3"])
        elif c.z < 2.042 and 25 < a < 100:
            k.tag([f], C["skin3"])
    build_nose(k)
    for s in (-1.0, 1.0):
        k.gem((0.020 * s, -0.124, 2.097), 0.012, C["skin"], sides=4, height=0.009, axis=(0.6 * s, -0.75, -0.1))
        k.gem((0.020 * s, -0.128, 2.091), 0.006, C["skin3"], sides=4, height=0.004, axis=(0.3 * s, -0.5, -0.8))
        build_eye(kits, s)
        build_ear(k, s)
        # el surco de la nariz que pasa por afuera de la comisura (la sonrisa pícara) y dos arrugas de la frente
        k.strip([onto_head(Vector((0.024 * s, -0.11, 2.112)), 0.004), onto_head(Vector((0.052 * s, -0.09, 2.112)), 0.003),
                 onto_head(Vector((0.074 * s, -0.07, 2.098)), 0.002), onto_head(Vector((0.078 * s, -0.06, 2.074)), 0.002)],
                [0.0045, 0.005, 0.005, 0.004], [(0.4 * s, -1, 0.3)] * 4, C["skin3"], thick=0.003)
        for zz, w0 in ((2.214, 0.034), (2.228, 0.026)):
            k.strip([onto_head(Vector((0.010 * s, -0.1, zz - 0.004)), 0.002), onto_head(Vector(((0.010 + w0) * s, -0.09, zz)), 0.002)],
                    [0.004, 0.0035], [(0.2 * s, -1, 0.2)] * 2, C["skin3"], thick=0.003)
    build_mouth(kits)
    # los cachetes que se inflan al soplar: un domo facetado en cada uno, escondido apenas bajo la piel en reposo; el
    # hueso Cheek_* lo saca 2.4 cm y asoma redondo (con solo la piel la cara apenas cambiaba)
    for s in (-1.0, 1.0):
        S = "R" if s < 0 else "L"
        c0 = CR.CHEEK_S[0] if S == "R" else CR.mx(CR.CHEEK_S[0])
        p = onto_head(c0 + Vector((0.0, -0.016, 0.0)), 0.0)
        outv = (p - Vector((0.0, head_r(p.z, 0)[0], p.z))).normalized()
        kc = kits["Cheek_" + S] = Kit("part_Cheek_" + S, "Cheek_" + S)
        kc.gem(p - outv * 0.012, 0.030, C["skin"], sides=6, height=0.014, axis=outv)
    # cuello flaco que se inclina hacia adelante (casi todo tapado por la barba y el cuello de la capa); ya en el modelo
    kn = kits["Neck"] = Kit("part_Neck", "Neck", weights=lambda co: (
        {"Spine2": 1.0 - ramp(co.z, 1.9, 1.96), "Neck": ramp(co.z, 1.9, 1.96)} if co.z < 1.97 else
        {"Neck": 1.0 - 0.5 * ramp(co.z, 1.98, 2.03), "Head": 0.5 * ramp(co.z, 1.98, 2.03)}))
    kn.tube([(0, 0.03, 1.86), (0, 0.002, 1.95), (0, -0.030, 2.035)], [(0.058, 0.056), (0.054, 0.05), (0.056, 0.052)], 8,
            C["skin"], phase=math.pi / 8, cap0=False, cap1=False)
    # los tendones: de detrás de la quijada al esternón (de perfil se ven detrás de la barba)
    for s in (-1, 1):
        kn.strip([Vector((0.058 * s, -0.012, 2.025)), Vector((0.034 * s, -0.040, 1.975)), Vector((0.016 * s, -0.048, 1.925))],
                 [0.013, 0.012, 0.010], [(s, -0.6, 0)] * 3, C["skin3"], thick=0.010)


def build_nose(k):
    """La nariz larga en pico (la de la hoja): una cuña pegada a la cara, angosta en el entrecejo, ancha en las aletas, con
    el lomo afilado y la punta que cae; cerrada por detrás adentro de la cara."""
    B, M, T = Vector((0, -0.101, 2.172)), Vector((0, -0.135, 2.130)), Vector((0, -0.160, 2.100))
    U, Cc, I = Vector((0, -0.143, 2.090)), Vector((0, -0.120, 2.092)), Vector((0, -0.086, 2.128))
    vs = {"B": B, "M": M, "T": T, "U": U, "C": Cc, "I": I}
    for sx, nm in ((1.0, "L"), (-1.0, "R")):
        vs["W1" + nm] = Vector((0.011 * sx, -0.104, 2.152))
        vs["W2" + nm] = Vector((0.019 * sx, -0.122, 2.114))
        vs["N" + nm] = Vector((0.023 * sx, -0.114, 2.094))
    bv = {n: k.bm.verts.new(p) for n, p in vs.items()}
    faces = []
    for nm in ("L", "R"):
        tri = [("B", "W1", "M"), ("W1", "W2", "M"), ("M", "W2", "T"), ("W2", "N", "T"), ("N", "U", "T"), ("N", "C", "U"),
               ("B", "I", "W1"), ("W1", "I", "W2"), ("W2", "I", "N"), ("N", "I", "C")]
        for t in tri:
            q = [bv[x + nm if x in ("W1", "W2", "N") else x] for x in t]
            faces.append(k.bm.faces.new(q if nm == "L" else list(reversed(q))))
    k._new(list(bv.values()), C["skin"], None, None)
    for f in faces:
        f.normal_update()
        if f.normal.z < -0.35:
            k.tag([f], C["skin3"])


def build_eye(kits, s):
    """Ojo hundido bajo el arco de la ceja, almendrado, con la punta de afuera más alta (la mirada pícara del concepto):
    el blanco amarillento, el iris negro grande arriba y hacia adentro, tocando el párpado, con un punto de luz, y la
    bolsa en sombra abajo. El párpado (Lid_*) en reposo tapa el 30 % de arriba con su borde oscuro de pestaña (la
    mirada entornada) y al girar 60° cierra el ojo."""
    S = "R" if s < 0 else "L"
    E = CR.EYE_S if S == "R" else CR.mx(CR.EYE_S)
    k = kits["Head"]
    fwd = Vector((0.30 * s, -1.0, 0.0)).normalized()
    out = (Vector((s, 0.0, 0.0)) - fwd * (fwd.x * s)).normalized()      # hacia la sien, sobre la cara
    up = Vector((0.0, 0.0, 1.0))
    # el blanco: rombo chato (afuera, arriba, adentro, abajo; la punta de afuera más alta y la de adentro más baja)
    pts = [E + out * u + up * v for u, v in ((0.0235, 0.0045), (0.002, 0.0135), (-0.0225, -0.003), (0.0, -0.0105))]
    vc = k.bm.verts.new(E + fwd * 0.0062)
    vr = [k.bm.verts.new(p) for p in pts]
    for i in range(4):
        k.bm.faces.new((vr[i], vr[(i + 1) % 4], vc) if s > 0 else (vr[(i + 1) % 4], vr[i], vc))
    k.bm.faces.new(list(reversed(vr)) if s > 0 else vr)
    k._new(vr + [vc], C["eyew"], None, None)
    # el iris arriba y hacia la nariz, tocando el borde del párpado; el punto de luz arriba
    ic = E + fwd * 0.0056 - out * 0.0028 + up * 0.0030
    k.gem(ic, 0.0098, C["eye"], sides=6, height=0.0026, axis=fwd)
    k.gem(ic + fwd * 0.0024 + out * 0.0022 + up * 0.0028, 0.0019, C["white"], sides=4, height=0.0009, axis=fwd)
    # la bolsa de abajo
    k.strip([E + out * 0.017 + up * -0.007 + fwd * 0.004, E + up * -0.0125 + fwd * 0.006, E - out * 0.016 + up * -0.0105 + fwd * 0.004],
            [0.006, 0.007, 0.006], [fwd] * 3, C["skin3"], thick=0.004)
    # el párpado: casquete de esfera alrededor del pivote (1.2 cm detrás del ojo), de 13° sobre el ojo a 105° (adentro de
    # la frente), con la hilera de abajo oscura (la pestaña): en reposo tapa el 30 % de arriba y girado 60° lo cierra
    kl = kits["Lid_" + S] = Kit("part_Lid_" + S, "Lid_" + S)
    P0 = CR.LID_S if S == "R" else CR.mx(CR.LID_S)
    R = 0.0275
    rows = []
    for el in (13.0, 24.0, 50.0, 78.0, 105.0):
        row = []
        for az in (-80.0, -40.0, 0.0, 40.0, 80.0):
            e, a = math.radians(el), math.radians(az)
            d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
            d = Matrix.Rotation(math.radians(-17.0 * s), 3, 'Z') @ Matrix.Rotation(math.radians(-12.0 * s), 3, 'Y') @ d
            row.append(P0 + d * R)
        rows.append(row)
    inner = [[P0 + (p - P0) * 0.88 for p in row] for row in rows]
    vo = [[kl.bm.verts.new(p) for p in r] for r in rows]
    vi = [[kl.bm.verts.new(p) for p in r] for r in inner]
    fo, fi, lash = [], [], []
    for r in range(len(rows) - 1):
        for i in range(4):
            f = kl.bm.faces.new((vo[r][i], vo[r][i + 1], vo[r + 1][i + 1], vo[r + 1][i]))
            (lash if r == 0 else fo).append(f)
            fi.append(kl.bm.faces.new((vi[r][i + 1], vi[r][i], vi[r + 1][i], vi[r + 1][i + 1])))
    rim = [kl.bm.faces.new((vo[0][i + 1], vo[0][i], vi[0][i], vi[0][i + 1])) for i in range(4)]
    rim += [kl.bm.faces.new((vo[-1][i], vo[-1][i + 1], vi[-1][i + 1], vi[-1][i])) for i in range(4)]
    for r in range(len(rows) - 1):
        rim.append(kl.bm.faces.new((vo[r][0], vo[r + 1][0], vi[r + 1][0], vi[r][0])))
        rim.append(kl.bm.faces.new((vo[r + 1][4], vo[r][4], vi[r][4], vi[r + 1][4])))
    kl._new([v for row in vo + vi for v in row], C["skin"], None, None)
    kl.tag(rim + lash, C["mouth"])
    kl.tag(fi, C["skin3"])


def build_ear(k, s):
    """Oreja grande en punta hacia afuera y arriba (el duende del concepto): una lámina con espesor de piel, con el hueco
    en sombra adelante."""
    # contorno en el plano de la oreja: (altura, y, cuánto sale de la cabeza)
    out = [(2.090, 0.014, 0.004), (2.106, -0.008, 0.030), (2.148, 0.000, 0.056), (2.196, 0.040, 0.084), (2.164, 0.054, 0.050),
           (2.132, 0.048, 0.022), (2.104, 0.034, 0.004)]
    pts = []
    for z, y, o in out:
        p = head_surface(min(z, 2.16), 90.0 * s, 0.0)
        pts.append(Vector((p.x + o * s, y, z)))
    nrm = Vector((s * 0.6, -0.72, 0.3)).normalized()
    th = 0.0075
    n = len(pts)
    cf = sum(pts, Vector()) / n
    vf = [k.bm.verts.new(p + nrm * th) for p in pts]
    vb = [k.bm.verts.new(p - nrm * th) for p in pts]
    vcf = k.bm.verts.new(cf + nrm * th * 0.2)
    vcb = k.bm.verts.new(cf - nrm * th)
    for i in range(n):
        j = (i + 1) % n
        k.bm.faces.new((vf[i], vf[j], vcf))
        k.bm.faces.new((vb[j], vb[i], vcb))
        k.bm.faces.new((vf[j], vf[i], vb[i], vb[j]))
    k._new(vf + vb + [vcf, vcb], C["skin"], None, None)
    # el hueco de la oreja (adelante): una faceta en sombra en la mitad de abajo
    hc = pts[0].lerp(pts[3], 0.38) + nrm * (th + 0.0012)
    k.obox(hc, (0.036, 0.003, 0.016), (pts[3] - pts[0]).normalized(), nrm, C["skin3"])


def build_mouth(kits):
    """La sonrisa en medialuna de pómulo a pómulo (la hoja de detalles): la placa oscura de arriba con ocho dientes en
    punta (los colmillos más largos) y el labio de arriba en sombra, en la cabeza; la de abajo con siete dientes y el
    labio de abajo, en la quijada en el centro y en la cara en las comisuras (al reírse abre una medialuna). Todo
    1-2 mm afuera de la cara: la banda oscura de la cabeza queda debajo y se ve cuando la quijada abre."""
    ku = kits["MouthUp"] = Kit("part_MouthUp", "Head", weights=w_mouth_up)
    kd = kits["MouthLo"] = Kit("part_MouthLo", "Jaw", weights=w_mouth_lo)
    n = 13
    xs = [GRIN_W * (2.0 * i / (n - 1) - 1.0) for i in range(n)]

    def at(x, dz, out):
        return grin_at(x, grin_mid(x) + dz, out)

    for kk, sgn in ((ku, 1.0), (kd, -1.0)):
        top = [at(x, sgn * grin_open(x), 0.0018) for x in xs]
        mid = [at(x, 0.0, 0.0018) for x in xs]
        vt = [kk.bm.verts.new(p) for p in top]
        vm = [kk.bm.verts.new(p) for p in mid]
        for i in range(n - 1):
            q = (vm[i], vm[i + 1], vt[i + 1], vt[i])
            kk.bm.faces.new(q if sgn > 0 else tuple(reversed(q)))
        kk._new(vt + vm, C["mouth"], None, None)
    # los dientes: triángulos en punta desde el borde de cada labio hasta el medio de la boca
    # anchos y pegados (se tocan en la encía), llenan la boca hasta el medio y los de arriba pasan un poco entre los de
    # abajo: de frente es una fila blanca en zigzag, la sonrisa de la hoja, no un cierre de cremallera
    for kk, sgn, cnt, x0, col in ((ku, 1.0, 8, 0.050, C["white"]), (kd, -1.0, 7, 0.044, C["white2"])):
        sp = 2.0 * x0 / (cnt - 1)
        for i in range(cnt):
            x = -x0 + sp * i
            h = grin_open(x)
            canine = i in (1, cnt - 2) and sgn > 0
            ln = (h + 0.0012) * (1.30 if canine else 1.10 if sgn > 0 else 0.95)
            base = at(x, sgn * (h + 0.0012), 0.0030)
            tip = at(x, sgn * (h + 0.0012 - ln), 0.0036)
            kk.spike(base, tip, sp * 0.56, col, sides=4, side_hint=(0, -1, 0), flat=0.30, phase=0.0)
    # los labios finos y estirados: el de arriba en sombra, el de abajo en piel
    lx = [GRIN_W * 1.06 * (2.0 * i / 6 - 1.0) for i in range(7)]
    up = [at(x, grin_open(x) + 0.0032, 0.0034) for x in lx]
    ku.strip(up, [0.0045, 0.006, 0.0068, 0.007, 0.0068, 0.006, 0.0045], [(0, -1, 0.4)] * 7, C["skin3"], thick=0.0055)
    lo = [at(x, -grin_open(x) - 0.0034, 0.0030) for x in lx]
    kd.strip(lo, [0.0045, 0.0058, 0.0066, 0.007, 0.0066, 0.0058, 0.0045], [(0, -1, -0.3)] * 7, C["skin"], thick=0.0055)


def build_brows_hair(kits):
    """Cejas salvajes: dos llamas blancas, una por lado, que nacen bajas junto a la nariz (dejan piel en el entrecejo:
    la V del ceño pícaro) y suben hacia la sien: una masa gruesa con cinco púas anchas y cortas que se pisan (de frente,
    una llama más ancha que la cabeza, no un abanico de agujas); los mechones de las sienes."""
    for S in "RL":
        m = (lambda v: Vector(v)) if S == "R" else (lambda v: Vector((-v[0], v[1], v[2])))
        kb = kits["Brow_" + S] = Kit("part_Brow_" + S, "Brow_" + S)
        # la masa: nace fina junto a la nariz, engorda sobre el ojo y sube hacia la sien
        base = [m((-0.012, -0.106, 2.166)), m((-0.030, -0.106, 2.177)), m((-0.054, -0.099, 2.193)), m((-0.080, -0.085, 2.206)),
                m((-0.098, -0.068, 2.208))]
        kb.tube(base, [(0.010, 0.008), (0.017, 0.012), (0.022, 0.014), (0.022, 0.014), (0.014, 0.010)], 5, C["white"],
                ups=[m((0, -0.4, 1))] * 5, phase=math.pi / 5, ring_colors=[C["white2"], C["white"], C["white"], C["white2"]])
        # las púas: anchas en la base (4-5 cm en el modelo), de 6 a 10 cm, de casi paradas sobre el ojo a la de afuera que
        # apunta a la sien; se pisan entre sí como lenguas de una llama
        # (inclinadas hacia afuera y atrás ~40°: casi paradas, de perfil eran una cresta sobre la frente, no dos cejas)
        spikes = [((-0.024, -0.108, 2.180), (-0.052, -0.104, 2.244), 0.017),
                  ((-0.046, -0.104, 2.192), (-0.104, -0.088, 2.258), 0.020),
                  ((-0.068, -0.094, 2.202), (-0.144, -0.070, 2.250), 0.020),
                  ((-0.086, -0.082, 2.207), (-0.172, -0.044, 2.228), 0.018),
                  ((-0.094, -0.072, 2.200), (-0.176, -0.026, 2.184), 0.015)]
        # y entre cada dos, una púa corta que llena el hueco: la llama es una masa dentada, no rayos sueltos
        mids = [(a[0].lerp(b[0], 0.5), a[0].lerp(b[0], 0.5) + ((a[1] - a[0]) + (b[1] - b[0])) * 0.30, 0.016)
                for a, b in zip([(Vector(p), Vector(q), r) for p, q, r in spikes][:-1],
                                [(Vector(p), Vector(q), r) for p, q, r in spikes][1:])]
        for i, (b, t, r) in enumerate(spikes + [(tuple(p), tuple(q), r) for p, q, r in mids]):
            # chatas en profundidad: de frente (y desde la cámara alta) se ven anchas, llamas y no agujas
            kb.spike(m(b), m(t), r, C["white"] if i % 2 == 0 else C["white2"], sides=4, side_hint=(0, -1, 0.15), flat=0.45,
                     phase=0.0)
        # mechones de las sienes (salen sobre la oreja hacia afuera y atrás) y la patilla: un mechón fino que baja de la
        # sien delante de la oreja hasta la barba (de frente enmarca la cara, como en la hoja; de 2.4 cm de ancho eran dos
        # paneles blancos al costado de la cara)
        kh = kits["Hair"]
        kh.strip([m((-0.074, -0.052, 2.204)), m((-0.086, -0.040, 2.160)), m((-0.088, -0.044, 2.112)), m((-0.084, -0.052, 2.070))],
                 [0.012, 0.013, 0.011, 0.008], [m((-1, -0.35, 0))] * 4, C["white"], thick=0.007)
        for b, t, r in (((-0.090, -0.010, 2.206), (-0.150, 0.020, 2.236), 0.014), ((-0.092, 0.024, 2.180), (-0.146, 0.064, 2.176), 0.014)):
            kh.spike(m(b), m(t), r, C["white"], sides=4, side_hint=(0, 0, 1), flat=0.6, phase=math.pi / 4)


# el moño en el marco de autoría (la cabeza): las mechas del pelo terminan en un anillo alrededor de su base
TK_SRC = CR.head_t_inv(CR.TOPKNOT_BASE)


def build_hair(kits):
    """El pelo blanco de los costados y la nuca peinado hacia el moño: mechas que nacen en la línea del pelo (detrás de
    la sien, detrás de la oreja, la nuca) y suben pegadas al cráneo (a lo sumo 1 cm encima) hasta juntarse en la base del
    moño, con un lomo cada dos (las facetas convergen en el moño, como en la espalda del concepto); la calva queda adelante
    arriba, del entrecejo al cordón, y se ve de frente y de perfil."""
    k = kits["Hair"] = Kit("part_Hair", "Head", weights=lambda co: {"Head": 1.0} if co.z > 2.06 else {"Head": 0.6, "Neck": 0.4})
    # la línea del pelo: (ángulo, altura) de la sien derecha por detrás de la oreja y la nuca a la sien izquierda
    # (la línea arranca a 52° de la cara, detrás de la sien: desde 24° el pelo tapaba la coronilla de frente y de perfil, un
    # casco blanco; en el concepto la calva se ve del entrecejo al moño)
    line = [(-52.0, 2.232), (-60.0, 2.214), (-68.0, 2.198), (-78.0, 2.180), (-88.0, 2.156), (-98.0, 2.116), (-108.0, 2.072),
            (-122.0, 2.060), (-142.0, 2.054), (-162.0, 2.050), (180.0, 2.048)]
    line = line + [(-a, z) for a, z in reversed(line[:-1])]
    cols = len(line)
    rows = 7
    ring_r = 0.046
    ax = CR.TOPKNOT_AXIS
    xv = Vector((1.0, 0.0, 0.0))
    fv = xv.cross(ax).normalized()              # hacia adelante, perpendicular al eje del moño
    vo, vi = [], []
    for c, (a, z) in enumerate(line):
        h = head_surface(z, a)
        # el punto del anillo de la base del moño hacia ese lado (las mechas de la sien llegan por delante del cordón)
        ar = math.atan2(h.x - TK_SRC.x, -(h.y - TK_SRC.y))
        tk = TK_SRC + xv * (math.sin(ar) * ring_r) + fv * (math.cos(ar) * ring_r) - ax * 0.004
        ro, ri = [], []
        for r in range(rows + 1):
            t = r / rows
            p = h.lerp(tk, smooth01(t) * 0.55 + t * 0.45)
            ridge = 0.007 if c % 2 else 0.0
            # pegado al cráneo, un poco más de volumen en la nuca; arriba se va juntando en el moño (nunca a menos de
            # 6 mm: las caras planas entre dos mechas no se meten en el cráneo redondo)
            bulk = max(0.009 + 0.004 * t, (0.006 + 0.004 * max(0.0, -math.cos(math.radians(a))) + ridge) * (1.0 - 0.2 * t))
            # el pelo de las sienes peinado hacia arriba hace bulto sobre la calva: de frente sube en dos alas blancas hasta
            # el cordón y de perfil tapa la coronilla (la hoja de perfil)
            if abs(a) < 95.0:
                bulk += 0.005 * math.sin(math.pi * min(1.0, max(0.0, (t - 0.2) / 0.75)))
            else:
                # en la coronilla de atrás las mechas se juntan sobre un cráneo muy curvo: un poco más de volumen para que
                # las caras planas no lo dejen asomar
                bulk += 0.008 * smooth01((t - 0.5) / 0.3)
            surf = onto_head(p, 0.0) if p.z < 2.262 else p
            outv = Vector((surf.x, surf.y - head_r(surf.z, 0)[0], 0.0))
            outv = outv.normalized() if outv.length > 1e-6 else Vector((0, 1, 0))
            base = surf if t < 0.999 else tk
            dz = (-0.016 if c % 2 else -0.004) if r == 0 else 0.0
            ro.append(k.bm.verts.new(base + outv * bulk + Vector((0, 0, dz)) + ax * (0.004 * t)))
            ri.append(k.bm.verts.new(base - outv * 0.003 + Vector((0, 0, dz))))
        vo.append(ro)
        vi.append(ri)
    fo, edge = [], []
    for c in range(cols - 1):
        for r in range(rows):
            fo.append(k.bm.faces.new((vo[c][r], vo[c + 1][r], vo[c + 1][r + 1], vo[c][r + 1])))
        edge.append(k.bm.faces.new((vo[c + 1][0], vo[c][0], vi[c][0], vi[c + 1][0])))
    for r in range(rows):
        edge.append(k.bm.faces.new((vo[0][r + 1], vi[0][r + 1], vi[0][r], vo[0][r])))
        edge.append(k.bm.faces.new((vo[-1][r], vi[-1][r], vi[-1][r + 1], vo[-1][r + 1])))
    k._new([v for row in vo + vi for v in row], C["white"], None, None)
    for i, f in enumerate(fo):
        c = i // rows
        k.tag([f], C["white2"] if c % 2 else C["white"])
    k.tag(edge, C["white3"])


def build_topknot(kits):
    """El moño (ya en el modelo): el pelo juntado que sube de la coronilla, tres vueltas de cordón verde y el mechón
    blanco cerrado como un pimpollo o una llama de papel plegado: cinco lóbulos que se abren hasta ~14 cm y se cierran en
    una punta alta en el medio (de frente una llama, de arriba una roseta); la ramita de cuatro hojas sale del cordón
    hacia los costados y atrás (cadena LeafKnot)."""
    T0, ax = CR.TOPKNOT_BASE, CR.TOPKNOT_AXIS
    xv = Vector((1.0, 0.0, 0.0))
    yv = ax.cross(xv).normalized() * -1.0          # hacia adelante, perpendicular al eje

    def w_tk(co):
        d = (co - T0).dot(ax)
        if d < 0.05:
            b = smooth01((d - 0.035) / 0.015)
            return {"Head": 1.0 - b, "Topknot_1": b}
        a = smooth01((d - 0.07) / 0.05)
        return {"Topknot_1": 1.0 - a, "Topknot_2": a}
    k = kits["Topknot"] = Kit("part_Topknot", "Topknot_1", weights=w_tk)
    # el pelo juntado bajo el cordón (nace adentro del pelo de la coronilla)
    k.tube([T0 - ax * 0.040, T0 + ax * 0.008], [0.056, 0.036], 10, C["white"], ups=[yv] * 2, phase=math.pi / 10, cap0=False,
           cap1=False, ring_colors=[C["white2"]])
    for i, d in enumerate((0.008, 0.020, 0.032)):
        c = T0 + ax * d
        k.tube([c, c + ax * 0.0105], [0.0395 - 0.0012 * i, 0.0385 - 0.0012 * i], 8, C["knot"], ups=[yv] * 2,
               phase=math.pi / 8 + i * 0.35, cap0=False, cap1=False)
        k.tube([c + ax * 0.0105, c + ax * 0.0125], [0.034, 0.034], 8, C["knot2"], ups=[yv] * 2, phase=math.pi / 8,
               cap0=False, cap1=False)
    lobes = 5
    # (distancia sobre el eje, radio en el valle, radio en la punta del lóbulo, giro en grados): un cono que se abre del
    # cordón hasta el ancho (a dos tercios) y se cierra rápido arriba: de frente y de perfil una cometa, no un huevo; el
    # giro entre los anillos tuerce las facetas como un papel retorcido
    spec = [(0.036, 0.028, 0.031, -24.0), (0.092, 0.050, 0.058, -10.0), (0.150, 0.062, 0.073, 0.0)]
    rings = []
    for d, rm, rl, tw in spec:
        c = T0 + ax * d
        ring = []
        for i in range(lobes * 2):
            # la primera punta al frente (90° = yv): ningún valle mira a la cámara de frente
            a = math.radians(90.0 + tw + 180.0 * i / lobes)
            r = rl if i % 2 == 0 else rm
            ring.append(c + xv * (math.cos(a) * r) + yv * (math.sin(a) * r))
        rings.append(ring)
    part = k.rings_loft(rings, C["white"], True, False)
    # la boca de arriba: las puntas de los lóbulos suben y se cierran hacia el centro, los valles quedan al 60 % de su
    # altura, y en el medio la punta alta (la de la llama)
    last = part.verts[-lobes * 2:]
    c_top = T0 + ax * spec[-1][0]
    top = [v.co.copy() for v in last]
    for i in range(lobes * 2):
        rv = top[i] - c_top
        # las puntas de los lóbulos suben y se recogen; los valles quedan más abajo (al 60 %): los pliegues de arriba
        top[i] = c_top + rv * (0.64 if i % 2 == 0 else 0.84) + ax * (0.022 if i % 2 == 0 else 0.006)
    up = [k.bm.verts.new(p) for p in top]
    fz = []
    for i in range(lobes * 2):
        j = (i + 1) % (lobes * 2)
        fz.append(k.bm.faces.new((last[i], last[j], up[j], up[i])))
    last = up
    apex = k.bm.verts.new(T0 + ax * 0.206 + yv * 0.004)
    fs = [k.bm.faces.new((last[i], last[(i + 1) % (lobes * 2)], apex)) for i in range(lobes * 2)]
    k.tag(fs + fz, C["white"])
    for f in part.faces + fz + fs:
        c = f.calc_center_median() - T0
        a = math.degrees(math.atan2(c.dot(yv), c.dot(xv)))
        if int((a + 360.0 + 18.0) / 36.0) % 2:
            k.tag([f], C["white2"])
    # la ramita del cordón: cuatro hojas anchas, dos por lado, hacia afuera y atrás (de espaldas un moño de hojas)
    bones = [f"Acc_LeafKnot_{i}" for i in range(2)]
    J = list(CR.LEAF_KNOT[:3])
    kl = kits["LeafKnot"] = Kit("part_LeafKnot", bones[0], weights=chain_weights(J, bones, before="Head", span=0.03))
    root = T0 + ax * 0.026
    for sx, dy, dz, ln, col in ((1, 0.30, 0.16, 0.14, C["leaf1"]), (1, 0.75, -0.30, 0.13, C["leaf2"]),
                                (-1, 0.30, 0.16, 0.14, C["leaf1b"]), (-1, 0.75, -0.30, 0.13, C["leaf1"])):
        d = Vector((sx, dy, dz)).normalized()
        b = root + Vector((0.028 * sx, 0.012, 0.0))
        kl.leaf(b, b + d * ln, Vector((0, -0.2, 1)), 0.05, col, ridge=0.3, under=C["leafu"])


HEAD_KITS = ("Head", "MouthUp", "MouthLo", "Lid_R", "Lid_L", "Brow_R", "Brow_L", "Cheek_R", "Cheek_L", "Hair")


def place_head(kits):
    """Lleva las piezas de la cabeza autoradas en su marco al modelo (chikuo_rig.head_t) y sus pesos con ellas: los pesos
    se calculan en el marco de autoría, donde se escribieron."""
    for n in HEAD_KITS:
        kit = kits[n]
        for v in kit.bm.verts:
            v.co = CR.head_t(v.co)
        if kit.weights:
            kit.weights = (lambda f: (lambda co: f(CR.head_t_inv(co))))(kit.weights)


# =========================================================================== barba
def build_beard(kits):
    """Barba blanca larga en escudo (ya en el modelo): nace bajo el labio y sube por la quijada hasta las patillas, más
    ancha que el mentón, se afina despacio en mechones facetados (un lomo cada dos, puntas sueltas en los bordes) hasta
    el cordón verde, el nudo trenzado en tres bultos redondeados (no más anchos que la barba ahí) y la punta. Las hileras
    del mentón van con la quijada y el resto con la cadena TasselBeard, que cuelga de la cabeza."""
    bones = [f"Acc_TasselBeard_{i}" for i in range(4)]
    J = [bh(b) for b in bones] + [bt(bones[-1])]
    wch = chain_weights(J, bones, before="Head", span=0.05)

    def w_beard(co):
        src = CR.head_t_inv(co)
        if co.z > 2.025:
            j = max(0.35, face_jaw(src))
            return {"Jaw": j, "Head": 1.0 - j}
        if co.z > 1.975:
            a = smooth01((2.025 - co.z) / 0.05)
            return blend(({"Jaw": 1.0}, 1.0 - a), (wch(co), a))
        return wch(co)
    k = kits["Beard"] = Kit("part_Beard", "Jaw", weights=w_beard)
    # (z, centro y, medio ancho, frente, atrás, cuánto sube el borde por la quijada): la de arriba abraza el mentón
    # (de perfil una cuña: 14 cm de fondo bajo el mentón que se afinan hacia el nudo, con la parte de atrás llenando
    # hasta el cuello; con 7-8 cm era un colmillo curvo despegado de la quijada y se veía el cuello detrás)
    rows = [(2.042, -0.112, 0.098, 0.034, 0.074, 0.070), (2.004, -0.134, 0.096, 0.050, 0.086, 0.024),
            (1.952, -0.152, 0.094, 0.052, 0.070, 0.0), (1.882, -0.166, 0.082, 0.046, 0.052, 0.0),
            (1.812, -0.176, 0.064, 0.036, 0.036, 0.0), (1.762, -0.180, 0.048, 0.028, 0.026, 0.0),
            (1.740, -0.180, 0.038, 0.024, 0.021, 0.0)]
    rings = []
    n = 12
    # la hilera de arriba se pega a la cara: del labio de abajo por debajo de las comisuras hasta las patillas (adelante),
    # y por debajo del mentón (atrás, tapada por el cuello)
    top_z = [(0.0, 2.040), (15.0, 2.046), (45.0, 2.068), (75.0, 2.080), (90.0, 2.084)]
    ring = []
    for i in range(n):
        a = 360.0 * (i + 0.5) / n
        aa = abs(((a + 180.0) % 360.0) - 180.0)
        if aa < 90.0:
            zs = next(z0 + (z1 - z0) * (aa - a0) / (a1 - a0) for (a0, z0), (a1, z1) in zip(top_z[:-1], top_z[1:]) if a0 <= aa <= a1)
            ring.append(CR.head_t(head_surface(zs, math.copysign(aa * 0.74, math.sin(math.radians(a))), 0.006)))
        else:
            ring.append(Vector((math.sin(math.radians(a)) * 0.080, -0.072 - math.cos(math.radians(a)) * 0.012, 2.005)))
    rings.append(ring)
    for ri, (z, yc, rx, rf, rb, rise) in enumerate(rows):
        if ri == 0:
            continue
        ring = []
        for i in range(n):
            a = 2 * math.pi * (i + 0.5) / n
            sx, cy = math.sin(a), -math.cos(a)
            e = 2.0 / 1.7
            # un lomo cada dos vértices al frente: los mechones de la barba
            lump = 1.0 + (0.10 if (i % 2 and cy < 0.2) else 0.0) * (1.0 if 0 < ri < len(rows) - 1 else 0.0)
            x = rx * math.copysign(abs(sx) ** e, sx) * lump
            ry = (rf if cy < 0 else rb) * lump
            dz = rise * abs(sx) ** 1.5 - (0.010 if cy < 0 else 0.0) * (1.0 - abs(sx)) if rise else 0.0
            ring.append(Vector((x, yc + ry * math.copysign(abs(cy) ** e, cy), z + dz)))
        rings.append(ring)
    part = k.rings_loft(rings, C["white"], False, False)
    for f in part.faces:
        c = f.calc_center_median()
        col = int((math.degrees(math.atan2(c.x, -(c.y + 0.15))) + 180.0) / 30.0)
        k.tag([f], (C["white2"] if col % 2 else C["white"]) if c.z > 1.85 else (C["white3"] if col % 2 else C["white2"]))
    # puntas sueltas en los bordes (mechones que se escapan hacia abajo y afuera)
    for s in (-1.0, 1.0):
        for z, x, ln in ((1.99, 0.094, 0.07), (1.92, 0.084, 0.07), (1.85, 0.070, 0.06)):
            b = Vector((x * s, -0.166, z))
            k.spike(b, b + Vector((0.028 * s, -0.006, -ln)), 0.014, C["white2"], sides=4, side_hint=(0, -1, 0), flat=0.5,
                    phase=math.pi / 4)
    # el cordón verde y el nudo trenzado: tres bultos de ocho lados redondeados que se angostan, y la punta en mechón
    c0 = Vector((0.0, -0.180, 1.740))
    k.tube([c0 + Vector((0, 0, 0.004)), c0 - Vector((0, 0, 0.014))], [(0.040, 0.026), (0.038, 0.025)], 8, C["knot"],
           ups=[(0, -1, 0)] * 2, phase=math.pi / 8, cap0=False, cap1=False)
    zc = c0.z - 0.014
    for i, (hz, r) in enumerate(((0.034, 0.036), (0.032, 0.033), (0.028, 0.028))):
        tilt = 0.18 * (1 if i % 2 else -1)
        pts = [Vector((0.0, c0.y + 0.002 * (i % 2), zc)), Vector((tilt * 0.02, c0.y - 0.004, zc - hz * 0.5)),
               Vector((0.0, c0.y + 0.002 * (i % 2), zc - hz))]
        k.tube(pts, [(r * 0.72, r * 0.55), (r, r * 0.78), (r * 0.72, r * 0.55)], 8, C["white"] if i % 2 == 0 else C["white2"],
               ups=[(0, -1, 0)] * 3, phase=math.pi / 8, cap0=False, cap1=i == 2)
        zc -= hz * 0.92
    for t, r in (((0.0, -0.176, 1.552), 0.020), ((-0.016, -0.172, 1.580), 0.014), ((0.016, -0.172, 1.578), 0.014)):
        k.spike(Vector((0.0, c0.y + 0.002, zc + 0.006)), Vector(t), r, C["white"], sides=4, side_hint=(0, -1, 0), flat=0.7,
                phase=math.pi / 4)


# =========================================================================== tronco: gi, faja, falda
GI = [  # (z, medio ancho, frente, espalda)
    (1.30, 0.200, 0.150, 0.152), (1.39, 0.196, 0.146, 0.148), (1.50, 0.188, 0.141, 0.143), (1.60, 0.196, 0.140, 0.147),
    (1.72, 0.214, 0.140, 0.152), (1.82, 0.224, 0.131, 0.150), (1.88, 0.200, 0.112, 0.131), (1.93, 0.140, 0.086, 0.096),
    (1.97, 0.092, 0.071, 0.077),
]


def ring(z, rx, ryf, ryb, n=14, cx=0.0, cy=0.0, power=2.4):
    """Anillo horizontal con frente (-Y) y espalda de distinta profundidad; i = 0 al frente."""
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        s, c = math.sin(a), -math.cos(a)
        e = 2.0 / power
        x = rx * math.copysign(abs(s) ** e, s)
        ry = ryf if c < 0 else ryb
        y = ry * math.copysign(abs(c) ** e, c)
        pts.append(Vector((cx + x, cy + y, z)))
    return pts


def gi_y(x, z, front=True, out=0.0):
    """y de la superficie del gi (frente o espalda) en (x, z), más 'out' hacia afuera."""
    prof = GI
    for (z0, w0, f0, b0), (z1, w1, f1, b1) in zip(prof[:-1], prof[1:]):
        if z0 <= z <= z1:
            t = (z - z0) / (z1 - z0)
            w = w0 + (w1 - w0) * t
            d = (f0 + (f1 - f0) * t) if front else (b0 + (b1 - b0) * t)
            u = min(0.999, abs(x) / w)
            v = (d + out) * (1.0 - u ** 2.4) ** (1 / 2.4)
            return -v if front else v
    return -0.14 if front else 0.14


def torso_weights(co):
    """Tronco de la cadera al cuello con mezclas en las uniones; los hombros del gi siguen un poco a la clavícula."""
    z = co.z
    if z < 1.24:
        w = {"Hips": 1.0 - 0.5 * ramp(z, 1.18, 1.24), "Spine": 0.5 * ramp(z, 1.18, 1.24)}
    elif z < 1.30:
        w = {"Spine": 0.5 + 0.5 * ramp(z, 1.24, 1.30), "Hips": 0.5 - 0.5 * ramp(z, 1.24, 1.30)}
    elif z < 1.38:
        w = {"Spine": 1.0}
    elif z < 1.46:
        a = ramp(z, 1.38, 1.46)
        w = {"Spine": 1.0 - a, "Spine1": a}
    elif z < 1.58:
        w = {"Spine1": 1.0}
    elif z < 1.66:
        a = ramp(z, 1.58, 1.66)
        w = {"Spine1": 1.0 - a, "Spine2": a}
    elif z < 1.92:
        w = {"Spine2": 1.0}
    else:
        a = 0.6 * ramp(z, 1.92, 1.98)
        w = {"Spine2": 1.0 - a, "Neck": a}
    if z > 1.72 and abs(co.x) > 0.13:
        k = 0.5 * ramp(abs(co.x), 0.13, 0.21) * ramp(z, 1.72, 1.82)
        S = "R" if co.x < 0 else "L"
        w = {n: v * (1.0 - k) for n, v in w.items()}
        w["Clav_" + S] = k
    return w


def build_gi(kits):
    k = kits["Gi"] = Kit("part_Gi", "Spine2", weights=torso_weights)
    rings = [ring(z, w, f, b, n=14) for z, w, f, b in GI]
    part = k.rings_loft(rings, C["gi"], False, False)
    # facetas en sombra y el cuello en V: adentro de las dos solapas se ve la camisa de abajo (oscura)
    zc = 1.66
    for f in part.faces:
        c = f.calc_center_median()
        if c.y < 0 and c.z > zc and abs(c.x) < (c.z - zc) * 0.30:
            k.tag([f], C["gi3"])
        elif c.y > 0.05 or abs(c.x) > 0.17:
            k.tag([f], C["gi2"])
    # el cuello de la capa cubre la nuca: arriba de todo el cuello del gi (paja) asoma alrededor del cuello
    k.tube([(0, 0.012, 1.935), (0, 0.012, 1.975)], [(0.104, 0.092), (0.086, 0.08)], 12, C["trim"], phase=math.pi / 12,
           cap0=False, cap1=False, ring_colors=[C["trim"]])
    # solapas con el ribete paja: la izquierda (la de arriba) va del cuello por la izquierda (+x) cruzando a su
    # derecha hasta la cintura; la de abajo nace del lado derecho y se pierde bajo la otra en el cruce
    def lapel(xz, w):
        pts, nrm = [], []
        for x, z in xz:
            y = gi_y(x, z, True, 0.008)
            pts.append(Vector((x, y, z)))
            nrm.append(Vector((x * 1.2, -1.0, 0.25)).normalized())
        k.strip(pts, [w] * len(pts), nrm, C["trim"], thick=0.012,
                ring_colors=[C["trim"]] * (len(pts) - 1))
    lapel([(0.072, 1.952), (0.060, 1.90), (0.034, 1.80), (0.004, 1.70), (-0.034, 1.60), (-0.072, 1.52), (-0.098, 1.47)], 0.050)
    lapel([(-0.072, 1.952), (-0.060, 1.90), (-0.036, 1.80), (-0.012, 1.72)], 0.048)


def build_sash(kits):
    """Faja verde ancha (10 cm) de dos vueltas (la costura oscura en el medio), con el nudo cuadrado al frente (14 x 12 cm,
    con pliegues y las dos puntas que caen en diagonal) y las dos colas color tostado del ribete (cadenas TieSash)."""
    kh = kits["Sash"] = Kit("part_Sash", "Spine", weights=torso_weights)
    z0, z1 = CR.SASH_Z
    zm = (z0 + z1) * 0.5
    zs = [z0, zm - 0.003, zm + 0.003, z1]
    rings = []
    for z in zs:
        # la vuelta de abajo tapa el borde de arriba del paño del frente (el okumi nace debajo)
        y_f = -max(gi_y(0.0, z, True, 0.020), 0.192 if z < zm else 0.0)
        y_b = gi_y(0.0, z, False, 0.020)
        rings.append(ring(z, 0.196 + 0.020, y_f, y_b, n=14))
    part = kh.rings_loft(rings, C["sash"], False, False, [C["sash"], C["sash2"], C["sash"]])
    for f in part.faces:
        c = f.calc_center_median()
        if int((math.degrees(math.atan2(c.x, -c.y)) + 200.0) / 26.0) % 2 and abs(c.z - zm) > 0.01:
            kh.tag([f], C["sash3"])
    K = CR.SASH_KNOT
    # el nudo: un bloque achaflanado con dos pliegues cruzados encima (las vueltas que se anudan)
    kh.obox(K + Vector((0.0, -0.012, 0.0)), (0.140, 0.056, 0.118), (1, 0, 0.10), (0, 1, 0), C["sash"], bevel=0.018, up_color=C["sash3"])
    for s in (-1.0, 1.0):
        kh.obox(K + Vector((0.026 * s, -0.044, 0.004)), (0.072, 0.022, 0.040), (1, 0, 0.75 * s), (0, 1, 0), C["sash3"], bevel=0.007)
    # las dos puntas que salen del nudo y caen en diagonal (45° hacia abajo y afuera), anchas como hojas
    for s, ln, col in ((1.0, 0.13, C["sash3"]), (-1.0, 0.12, C["sash"])):
        b = K + Vector((0.040 * s, -0.040, -0.020))
        d = Vector((0.70 * s, -0.18, -0.70)).normalized()
        kh.leaf(b, b + d * ln, Vector((0, -1, 0.1)), 0.06, col, ridge=0.22, under=C["sash2"])
    # colas tostadas de 7 cm: una cinta por los huesos de cada cadena
    for t, w0 in (("A", 0.070), ("B", 0.064)):
        bones = [f"Acc_TieSash{t}_{i}" for i in range(2)]
        J = [bh(b) for b in bones] + [bt(bones[-1])]
        path, _ = chain_samples(J, 0.05)
        path[0] = path[0] + (J[0] - J[1]).normalized() * 0.02
        kk = kits["Sash" + t] = Kit("part_TieSash" + t, bones[0], weights=chain_weights(J, bones, before="Hips", span=0.05))
        face = Vector((0.05, -1, 0)).normalized()
        widths = [w0 * (1.0 + 0.08 * i / len(path)) for i in range(len(path))]
        p = kk.strip(path, widths, [face] * len(path), C["trim"], thick=0.012)
        for f in p.faces:
            f.normal_update()
            if f.normal.dot(face) < -0.5:
                kk.tag([f], C["trim2"])


def skirt_weights(co):
    """Falda del gi: arriba con la cadera, hacia el ruedo con los cuatro paños (mezclados por ángulo)."""
    a = (math.degrees(math.atan2(co.x, -co.y)) + 360.0) % 360.0
    angs = CR.SKIRT_ANGLES
    w_ang = {}
    for i in range(len(angs)):
        a0, a1 = angs[i], angs[(i + 1) % len(angs)] + (360.0 if i == len(angs) - 1 else 0.0)
        aa = a + (360.0 if a < a0 else 0.0)
        if a0 <= aa <= a1:
            t = smooth01((aa - a0) / (a1 - a0))
            w_ang = {CR.skirt_name(angs[i]): 1.0 - t, CR.skirt_name(angs[(i + 1) % len(angs)]): t}
            break
    h = smooth01((CR.SKIRT_TOP_Z - 0.02 - co.z) / 0.30)
    if h <= 0.0:
        return {"Hips": 1.0}
    return blend(({"Hips": 1.0}, 1.0 - h), (w_ang, h))


SKIRT_ROWS = [(1.40, 0.0), (1.30, 0.22), (1.18, 0.46), (1.06, 0.68), (0.96, 0.86), (0.865, 1.0)]


def skirt_r(t):
    rx = CR.SKIRT_TOP_R[0] + (CR.SKIRT_HEM_R[0] - CR.SKIRT_TOP_R[0]) * t
    ry = CR.SKIRT_TOP_R[1] + (CR.SKIRT_HEM_R[1] - CR.SKIRT_TOP_R[1]) * t
    return rx, ry


def skirt_point(a, z, t, out=0.0):
    rx, ry = skirt_r(t)
    r = math.radians(a)
    return Vector((math.sin(r) * (rx + out), -math.cos(r) * (ry + out), z))


def build_skirt(kits):
    """Falda del gi (del ruedo del saco hasta la mitad del muslo) con el ribete paja abajo y en los bordes del cruce, y
    el paño largo del frente (la solapa de arriba que baja hasta abajo de la rodilla)."""
    k = kits["Skirt"] = Kit("part_Skirt", "Hips", weights=skirt_weights)
    n = 18
    rows = []
    for z, t in SKIRT_ROWS:
        rows.append([skirt_point(360.0 * i / n, z - (0.025 if (i % 2 and t > 0.99) else 0.0), t) for i in range(n)])
    part = k.rings_loft(rows, C["gi"], False, False, [C["gi"], C["gi"], C["gi"], C["gi"], C["trim"]])
    for f in part.faces:
        c = f.calc_center_median()
        if c.z > 0.95 and (c.y > 0.12 or abs(c.x) > 0.25):
            k.tag([f], C["gi2"])
    # el revés de la falda (se ve desde abajo y en las patadas)
    inner = [[p + (Vector((p.x, p.y, 0.0)).normalized() * -0.012) for p in r] for r in rows[2:]]
    k.rings_loft([list(reversed(r)) for r in inner], C["gi3"], False, False)
    # los bordes del cruce: dos ribetes en diagonal desde la faja hacia los costados del ruedo
    for s in (-1.0, 1.0):
        pts, nr = [], []
        for z, t in SKIRT_ROWS[1:]:
            a = s * (12.0 + 46.0 * t)
            pts.append(skirt_point(a, z, t, 0.008))
            nr.append(Vector((math.sin(math.radians(a)), -math.cos(math.radians(a)), 0.0)))
        k.strip(pts, [0.046] * len(pts), nr, C["trim"], thick=0.010)
    # el paño largo del frente (okumi): baja hasta 0.64 m con el ribete paja en su borde y abajo
    ko = kits["Okumi"] = Kit("part_Okumi", "Hips", weights=skirt_weights)
    zs = [1.38, 1.20, 1.02, 0.86, 0.74, 0.64]
    xl, xr = -0.105, 0.085
    vo, vi = [], []
    for z in zs:
        t = min(1.0, (1.40 - z) / (1.40 - 0.865))
        ry = skirt_r(t)[1] + 0.022
        ro, ri = [], []
        for j, x in enumerate((xl, (xl + xr) * 0.5, xr)):
            # un pliegue al medio (la columna del centro 1.5 cm adelante): el paño no es una tabla plana y clara
            y = -ry * (1.0 - (abs(x) / 0.36) ** 2) ** 0.5 - (0.015 if j == 1 else 0.0)
            ro.append(ko.bm.verts.new((x, y, z)))
            ri.append(ko.bm.verts.new((x, y + 0.012, z)))
        vo.append(ro)
        vi.append(ri)
    fs, fb = [], []
    for r in range(len(zs) - 1):
        for i in range(2):
            fs.append(ko.bm.faces.new((vo[r][i], vo[r][i + 1], vo[r + 1][i + 1], vo[r + 1][i])))
            fb.append(ko.bm.faces.new((vi[r][i + 1], vi[r][i], vi[r + 1][i], vi[r + 1][i + 1])))
        fb.append(ko.bm.faces.new((vo[r][0], vo[r + 1][0], vi[r + 1][0], vi[r][0])))
        fb.append(ko.bm.faces.new((vo[r][2], vi[r][2], vi[r + 1][2], vo[r + 1][2])))
    fb.append(ko.bm.faces.new((vo[-1][0], vo[-1][1], vi[-1][1], vi[-1][0])))
    fb.append(ko.bm.faces.new((vo[-1][1], vo[-1][2], vi[-1][2], vi[-1][1])))
    ko._new([v for r in vo + vi for v in r], C["gi"], None, None)
    ko.tag(fb, C["gi3"])
    # abajo de la rodilla el paño queda en la sombra de la capa (de frente no es un bloque claro)
    ko.tag([f for f in fs if f.calc_center_median().z < 0.86], C["gi2"])
    # ribetes del paño: el borde de su derecha (el que se ve) y el de abajo
    edge = [Vector((xl + 0.012, vo[i][0].co.y - 0.006, z)) for i, z in enumerate(zs)]
    ko.strip(edge, [0.040] * len(edge), (0, -1, 0), C["trim"], thick=0.010)
    bot = [Vector((x, vo[-1][j].co.y - 0.006, 0.655)) for j, x in enumerate((xl, (xl + xr) * 0.5, xr))]
    ko.strip(bot, [0.036] * 3, (0, -1, 0), C["trim"], thick=0.010)


# =========================================================================== brazos: mangas, vendas, manos
def arm_points():
    S, E, W = CR.SHOULDER, CR.ELBOW, CR.WRIST
    return S, E, W, (E - S).normalized(), (W - E).normalized()


def build_sleeve_r(kits):
    """Manga ancha de kimono hasta la mitad del antebrazo, con el puño paja; el vuelo de abajo cuelga de Sleeve_R_*."""
    S, E, _, u, l = arm_points()
    cuff = E + l * 0.17
    wa = chain_weights([S, E, cuff], ["UpperArm_R", "Forearm_R"], before="Clav_R", span=0.08)
    up = Vector((0.0, 0.0, 1.0))

    def w_sleeve(co):
        t = along_bone(co, S, E)
        if t < 0.0:
            a = 0.5 * smooth01(-t / 0.2)
            return {"UpperArm_R": 1.0 - a, "Clav_R": a}
        w = wa(co)
        # la mitad de abajo del tubo (y la del puño) va con el vuelo, desde 2 cm arriba del eje del brazo hasta el borde,
        # entera a los 8 cm; el vuelo del codo pasa al del puño de a poco (la manga cae sobre el antebrazo con el brazo
        # arriba)
        axis_pt = S + u * max(0.0, min(1.0, t)) * (E - S).length if t <= 1.0 else E + l * min(0.17, (co - E).dot(l))
        below = (axis_pt - co).dot(up)
        k = smooth01((below + 0.02) / 0.10)
        if k > 0.0:
            b2 = smooth01((t - 0.75) / 0.30)
            w = {n: v * (1.0 - k) for n, v in w.items()}
            w["Sleeve_R_1"] = w.get("Sleeve_R_1", 0.0) + k * (1.0 - b2)
            w["Sleeve_R_2"] = w.get("Sleeve_R_2", 0.0) + k * b2
        return {n: v for n, v in w.items() if v > 1e-4}
    k = kits["Sleeve_R"] = Kit("part_Sleeve_R", "UpperArm_R", weights=w_sleeve)
    pts = [S - u * 0.06, S + u * 0.08, S + u * 0.22, E - u * 0.04, E + l * 0.05, E + l * 0.12, cuff - l * 0.045, cuff]
    hang = [0.0, 0.01, 0.02, 0.035, 0.05, 0.065, 0.075, 0.078]
    rads = [(0.098, 0.096), (0.110, 0.11), (0.116, 0.122), (0.122, 0.135), (0.128, 0.150), (0.135, 0.168), (0.142, 0.182),
            (0.146, 0.186)]
    ups = []
    pp = []
    for p, h in zip(pts, hang):
        pp.append(p - up * h)
        ups.append(up)
    k.tube(pp, rads, 8, C["gi"], ups=ups, phase=math.pi / 8, cap0=False, cap1=False, ring_colors=[C["gi"]] * 6 + [C["trim"]])
    # la boca de la manga: el revés oscuro (desde arriba el puño se lee como un anillo paja con un hueco)
    k.tube([cuff - up * 0.078 - l * 0.004, cuff - up * 0.06 - l * 0.06], [(0.140, 0.178), (0.06, 0.06)], 8, C["gi3"], ups=[up] * 2,
           phase=math.pi / 8, cap0=False, cap1=False)
    build_wrap_hand_r(kits)


def build_wrap_hand_r(kits):
    _, E, W, _, l = arm_points()
    wf = chain_weights([E, W, W + l * 0.05], ["Forearm_R", "Hand_R"], span=0.03)
    k = kits["Wrap_R"] = Kit("part_Wrap_R", "Forearm_R", weights=lambda co: {"Forearm_R": 1.0} if along_bone(co, E, W) < 0.9 else wf(co))
    pts = [E + l * 0.08, E + l * 0.17, E + l * 0.25, E + l * 0.31, W - l * 0.02, W + l * 0.012]
    k.tube(pts, [0.047, 0.046, 0.043, 0.040, 0.038, 0.040], 8, C["wrap"], ups=[(0, -1, 0)] * len(pts), phase=math.pi / 8, cap0=False,
           cap1=False, ring_colors=[C["wrap"], C["wrap2"], C["wrap"], C["wrap2"], C["wrap"]])
    build_hand_r(kits)


def build_hand_r(kits):
    """Mano grande y huesuda (la que agarra la caña): palma chata, nudillos marcados, dedos largos de dos falanges."""
    W, hd, dors, _ = CR.hand_frame("R")
    Kn = CR.KNUCKLE

    def w_hand(co):
        t = along_bone(co, W, Kn)
        return {"Hand_R": 1.0} if t > 0.15 else {"Hand_R": 0.7, "Forearm_R": 0.3}
    k = kits["Hand_R"] = Kit("part_Hand_R", "Hand_R", weights=w_hand)
    k.tube([W - hd * 0.012, W + hd * 0.047, W + hd * 0.100, Kn + hd * 0.006],
           [(0.045, 0.024), (0.059, 0.027), (0.065, 0.026), (0.063, 0.022)], 6, C["skin"],
           ups=[dors] * 4, phase=math.pi / 6, power=3.0, ring_colors=[C["skin"], C["skin"], C["skin2"]])
    for name, *_ in CR.FINGERS:
        b1, b2 = f"{name}_R_1", f"{name}_R_2"
        base, mid, tip = bh(b1), bh(b2), bt(b2)
        r0 = 0.0140 if name != "Pinky" else 0.0123

        def w_f(co, b1=b1, b2=b2, base=base, mid=mid, tip=tip):
            t = along_bone(co, base, mid)
            if t < 0.12:
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
        kf.tube([base - d1 * 0.012, base + d1 * 0.008, mid - d1 * 0.006, mid + d2 * 0.006, tip - d2 * 0.010, tip],
                [(r0 * 1.12, r0), (r0, r0 * 0.95), (r0 * 0.9, r0 * 0.85), (r0 * 0.95, r0 * 0.9), (r0 * 0.78, r0 * 0.72),
                 (r0 * 0.5, r0 * 0.45)], 4, C["skin"], ups=[dors] * 6, phase=math.pi / 4, power=2.6, cap0=False,
                ring_colors=[C["skin2"], C["skin"], C["skin2"], C["skin"], C["skin"]])
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
    kt.tube([tb - d1 * 0.014, tb + d1 * 0.020, tm, tm + d2 * 0.025, tt], [(0.018, 0.016), (0.017, 0.015), (0.015, 0.013),
            (0.013, 0.012), (0.007, 0.007)], 4, C["skin"], ups=[dors] * 5, phase=math.pi / 4, power=2.6)


# =========================================================================== piernas: pantalón, polainas, sandalias
def leg_axis(z):
    H, K, A = CR.HIP_J, CR.KNEE, CR.ANKLE
    if z >= K.z:
        return H.lerp(K, (H.z - z) / (H.z - K.z))
    return K.lerp(A, (K.z - z) / (K.z - A.z))


def build_leg_r(kits):
    H, K, A = CR.HIP_J, CR.KNEE, CR.ANKLE
    wl = chain_weights([H, K, A], ["Thigh_R", "Shin_R"], before="Hips", after="Foot_R", span=0.10)

    def w_leg(co):
        w = wl(co)
        if co.z > 1.06:
            a = 0.6 * smooth01((co.z - 1.06) / 0.18)
            w = {n: v * (1.0 - a) for n, v in w.items()}
            w["Hips"] = w.get("Hips", 0.0) + a
        return w
    k = kits["Leg_R"] = Kit("part_Leg_R", "Thigh_R", weights=w_leg)
    # pantalón ancho: angosto bajo el gi, se infla en la rodilla (más hacia afuera que hacia adentro) y se junta en la
    # polaina con pliegues
    rows = [(1.28, 0.125, 0.0), (1.12, 0.150, 0.01), (0.97, 0.168, 0.02), (0.84, 0.192, 0.03), (0.72, 0.214, 0.036),
            (0.62, 0.222, 0.036), (0.53, 0.208, 0.03), (0.465, 0.17, 0.02), (0.425, 0.115, 0.01), (0.400, 0.078, 0.0)]
    n = 10
    rings = []
    for z, r, out in rows:
        c = leg_axis(z)
        ring_ = []
        for i in range(n):
            a = 2 * math.pi * i / n + math.pi / n
            x, y = math.sin(a), -math.cos(a)
            # hacia adentro (x > 0 en la derecha) más chato: los dos globos no se cruzan entre las piernas
            rx = r * (0.72 if x > 0 else 1.0)
            jit = 0.012 * math.sin(i * 2.7 + z * 31.0)
            ring_.append(Vector((c.x + x * rx - out + jit * 0.5, c.y + y * (r + jit), z)))
        rings.append(ring_)
    part = k.rings_loft(rings, C["pants"], False, False)
    for f in part.faces:
        c = f.calc_center_median()
        if (int(math.degrees(math.atan2(c.x - leg_axis(c.z).x, -(c.y - leg_axis(c.z).y))) / 36.0 + c.z * 7.0)) % 5 == 0:
            k.tag([f], C["pants2"])
    # polainas vendadas: de abajo del globo al tobillo se afinan (Ø 14 a 9.5 cm: la pantorrilla flaca del viejo); siete
    # vendas oscuras y angostas inclinadas 22° una para cada lado sobre la tela gris verdosa: de frente se cruzan en X,
    # como en la hoja de detalles
    zs = [0.445, 0.395, 0.345, 0.295, 0.245, 0.195, 0.150, 0.110]

    def leg_r(z):
        return 0.0475 + (0.070 - 0.0475) * smooth01((z - 0.11) / 0.30)
    k.tube([leg_axis(zs[0] + 0.01), leg_axis(0.28), leg_axis(zs[-1])], [leg_r(0.455) - 0.006, leg_r(0.28) - 0.006, leg_r(0.11) - 0.006],
           8, C["leg2"], phase=math.pi / 8, cap0=False, cap1=False)
    for i, (z0, z1) in enumerate(zip(zs[:-1], zs[1:])):
        tilt = math.tan(math.radians(22.0)) * (1 if i % 2 else -1)
        rings = []
        zc = (z0 + z1) * 0.5
        for z in (zc - 0.011, zc + 0.011):
            c = leg_axis(z)
            r = leg_r(z) + 0.002
            rings.append([Vector((c.x + math.sin(a) * r, c.y - math.cos(a) * r, z + tilt * (math.sin(a) * r)))
                          for a in (2 * math.pi * j / 8 + math.pi / 8 for j in range(8))])
        k.rings_loft(rings, C["leg"], False, False)
    build_foot_r(kits)


def build_foot_r(kits):
    """Sandalia-zapato (la hoja de detalles): el zapato negro facetado y robusto hasta el tobillo (material que brilla
    en las patadas), ancho (el pie grande del que trepa), sobre una plataforma de paja con canto; la puntera y el talón de
    paja y dos tiras tostadas que se cruzan sobre el empeine; la punta dobla en la bola del pie (Toe_R). (Antes una
    zapatilla fina sobre una tabla: a 1:1 se leía como ojotas.)"""
    A, B = CR.ANKLE, CR.BALL
    fwd2 = Vector((B.x - A.x, B.y - A.y)).normalized()     # la punta, apenas hacia afuera
    lat2 = Vector((fwd2.y, -fwd2.x))                        # hacia afuera del pie derecho (-X)

    def F(x, y, z):
        """Del espacio del pie (x hacia afuera, y hacia adelante desde el tobillo) al reposo."""
        p = Vector((A.x, A.y)) + fwd2 * y + lat2 * x
        return Vector((p.x, p.y, z))
    ball_y = Vector((B.x - A.x, B.y - A.y)).length

    def w_foot(co):
        if co.z > 0.12:
            a = 0.5 * smooth01((co.z - 0.12) / 0.06)
            return {"Foot_R": 1.0 - a, "Shin_R": a}
        d = (co - A)
        fwd = Vector((B.x - A.x, B.y - A.y, 0)).normalized()
        along = d.dot(fwd)
        if along < ball_y - 0.02:
            return {"Foot_R": 1.0}
        if along > ball_y + 0.02:
            return {"Toe_R": 1.0}
        a = smooth01((along - (ball_y - 0.02)) / 0.04)
        return {"Foot_R": 1.0 - a, "Toe_R": a}
    k = kits["Foot_R"] = Kit("part_Foot_R", "Foot_R", weights=w_foot)
    toe = -CR.SOLE_TOE_Y
    heel = CR.SOLE_HEEL_Y
    # suela (paja) con canto: un poco más grande que el zapato
    hw = [(-heel, 0.072), (-0.04, 0.088), (0.06, 0.100), (ball_y, 0.108), (0.24, 0.096), (toe - 0.025, 0.066), (toe, 0.026)]
    poly = [(p.x, p.y) for p in [F(w, y, 0) for y, w in hw] + [F(-w, y, 0) for y, w in reversed(hw)]]
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))
    SOLE = 0.046
    k.extrude_polygon(poly if area > 0 else list(reversed(poly)), 0.0, SOLE, C["sole2"], top_color=C["sole"])
    # zapato
    # el zapato: sube hasta el tobillo (el cuello del zapato abraza la polaina), negro entero
    # (1.25 veces más alto y un poco más ancho que antes, sobre la plataforma más gruesa)
    rings = [(-heel + 0.014, 0.068, 0.100, 0.075), (-0.03, 0.086, 0.122, 0.090), (0.07, 0.098, 0.106, 0.068),
             (ball_y, 0.102, 0.086, 0.048), (0.25, 0.090, 0.070, 0.038), (toe - 0.02, 0.056, 0.060, 0.022)]
    pts = [F(0, y, z) for y, _, z, _ in rings]
    fwd = (pts[-1] - pts[0]).normalized()
    k.tube(pts, [(w, h) for _, w, _, h in rings], 8, "black", ups=[(0, 0, 1)] * len(rings), phase=math.pi / 8, power=2.4,
           slot=SLOT_FOOT_R)
    k.tube([F(0, -0.004, 0.138), F(0, -0.002, 0.182)], [(0.072, 0.070), (0.058, 0.057)], 8, "black", phase=math.pi / 8, cap0=False,
           cap1=False, slot=SLOT_FOOT_R)
    # la puntera y el talón de paja (en el concepto el negro solo queda en el empeine y el costado)
    k.tube([F(0, ball_y + 0.012, 0.080), F(0, toe - 0.016, 0.062)], [(0.106, 0.052), (0.062, 0.026)], 8, C["strap"],
           ups=[(0, 0, 1)] * 2, phase=math.pi / 8, power=2.4, cap0=False)
    k.tube([F(0, -heel + 0.004, 0.084), F(0, -heel + 0.060, 0.090)], [(0.074, 0.040), (0.090, 0.046)], 8, C["strap"],
           ups=[(0, 0, 1)] * 2, phase=math.pi / 8, power=2.4, cap1=False)
    # la tira tostada: una sola, en diagonal sobre el empeine, de la suela de adentro junto a los dedos al tobillo de
    # afuera; y el talón
    # dos tiras que se cruzan sobre el empeine (en la hoja de detalles, una X de paja)
    for sx in (1.0, -1.0):
        pts = [F(-0.104 * sx, 0.200, 0.052), F(-0.074 * sx, 0.166, 0.106), F(0.0, 0.104, 0.150), F(0.068 * sx, 0.046, 0.160),
               F(0.094 * sx, 0.000, 0.126)]
        nr = [(p - F(0, y, z0)).normalized() for p, y, z0 in zip(pts, (0.19, 0.16, 0.104, 0.046, 0.0), (0.04, 0.07, 0.09, 0.09, 0.09))]
        k.strip(pts, [0.030] * 5, nr, C["strap"], thick=0.012)
    k.strip([F(0, -heel + 0.008, SOLE), F(0, -heel + 0.002, 0.128)], [0.056, 0.048], [(-fwd.x, -fwd.y, 0)] * 2, C["strap"],
            thick=0.012)


def build_hips(kits):
    k = kits["Hips"] = Kit("part_Hips", "Hips")
    # el tiro del pantalón: tapa la entrepierna entre los dos globos
    k.tube([(0, 0.0, 0.98), (0, 0.0, 1.10), (0, 0.0, 1.28)], [(0.14, 0.13), (0.19, 0.155), (0.19, 0.15)], 10, C["pants"],
           phase=math.pi / 10, cap0=True, cap1=False, power=2.4)


# =========================================================================== capa de hojas
def cloak_param(co):
    """(ángulo, fracción de la caída) del punto de la capa más cercano a 'co'."""
    phi = (math.degrees(math.atan2(co.x, -(co.y - CR.CLOAK_Y0))) + 360.0) % 360.0
    r = math.hypot(co.x, co.y - CR.CLOAK_Y0)
    target = Vector((r, co.z))
    best = min(range(41), key=lambda i: (CR.cloak_rz(phi, i / 40.0) - target).length)
    lo, hi = max(0, best - 1) / 40.0, min(40, best + 1) / 40.0
    for _ in range(10):
        m1, m2 = lo + (hi - lo) / 3, hi - (hi - lo) / 3
        if (CR.cloak_rz(phi, m1) - target).length < (CR.cloak_rz(phi, m2) - target).length:
            hi = m2
        else:
            lo = m1
    s = (lo + hi) * 0.5
    if best == 40 and co.z < CR.cloak_rz(phi, 1.0).y:
        s = 1.0 + (CR.cloak_rz(phi, 1.0).y - co.z)
    return phi, s


def cloak_seg_weights(a, s):
    """Pesos de los tramos de un paño a la fracción s de la caída, con una rampa de ±0.08 en cada corte."""
    cuts = CR.CLOAK_SPLITS[CR.cloak_segs(a)]
    ts = [smooth01((s - (x - 0.08)) / 0.16) for x in cuts]
    w, acc = [], 1.0
    for t in ts:
        w.append(acc * (1.0 - t))
        acc *= t
    w.append(acc)
    return w


def w_cloak(co):
    """Paños de la capa: mezcla por ángulo entre los dos paños vecinos (la cáscara se estira repartida, no en escalón) y
    por la caída entre sus tramos; el cuello va con el pecho (Spine2)."""
    phi, s = cloak_param(co)
    angs = CR.CLOAK_ANGLES
    if phi <= angs[0]:
        wa = {angs[0]: 1.0}
    elif phi >= angs[-1]:
        wa = {angs[-1]: 1.0}
    else:
        i = max(j for j in range(len(angs)) if angs[j] <= phi)
        i = min(i, len(angs) - 2)
        t = smooth01((phi - angs[i]) / (angs[i + 1] - angs[i]))
        wa = {angs[i]: 1.0 - t, angs[i + 1]: t}
    w = {}
    for a, v in wa.items():
        for i, ws in enumerate(cloak_seg_weights(a, s)):
            if ws > 0.0:
                n = CR.cloak_name(a, i + 1)
                w[n] = w.get(n, 0.0) + v * ws
    c = 1.0 - smooth01((s - 0.03) / 0.13)
    if c > 0.0:
        w = {n: v * (1.0 - c) for n, v in w.items()}
        w["Spine2"] = c
    return w


def drop_len(phi):
    return sum((CR.cloak_rz(phi, (i + 1) / 24.0) - CR.cloak_rz(phi, i / 24.0)).length for i in range(24))


def arc_samples(a0, a1, s, out, spacing, rng, jitter=0.3):
    """Ángulos repartidos por largo de arco en la hilera s (una hoja al lado de la otra)."""
    phis = [a0 + (a1 - a0) * i / 120.0 for i in range(121)]
    arc = [0.0]
    for p0, p1 in zip(phis[:-1], phis[1:]):
        arc.append(arc[-1] + (CR.cloak_point(p1, s, out) - CR.cloak_point(p0, s, out)).length)
    n = max(4, int(arc[-1] / spacing))
    out_phis = []
    for j in range(n):
        u = (j + 0.5 + rng.uniform(-jitter, jitter)) / n
        d = u * arc[-1]
        idx = min(max(i for i in range(len(arc)) if arc[i] <= d), len(arc) - 2)
        out_phis.append(phis[idx] + (phis[idx + 1] - phis[idx]) * (d - arc[idx]) / max(1e-9, arc[idx + 1] - arc[idx]))
    return out_phis


def build_cloak(kits):
    """La capa: una cáscara oscura de dos caras (lo que se ve entre las hojas) con el ruedo cortado en puntas, y ~270
    hojas de bambú anchas: la gola alrededor de la nuca, dos coronas que salen del cuello en estrella y tapan los
    hombros (lo que más ve la cámara alta: oliva claro arriba), el yugo de hojas que cuelgan hacia afuera (la silueta en
    púas), cinco hileras como tejas que se tapan un tercio (oliva al medio, verde oscuro abajo) y las hojas de adentro
    (más oscuras, puntas abajo: se ven con los brazos arriba, en el salto y colgado)."""
    rng = random.Random(61)
    k = kits["Cloak"] = Kit("part_Cloak", "Spine2", weights=w_cloak)
    k.use_anchors()
    a0, a1 = CR.CLOAK_OPEN, 360.0 - CR.CLOAK_OPEN
    # la cáscara partida en un paño por hueso, con una ranura de 1.6° entre paños y cada paño pesado entero a su hueso (el
    # ancla en el centro del paño): de una sola pieza, cuando los paños se separaban (los golpes, los saltos, colgado) la
    # cáscara se estiraba entre ellos en una lona plana más ancha que el cuerpo. Cada paño termina en punta, como una hoja
    angs, gap, rows_n = CR.CLOAK_ANGLES, 1.6, 5
    for i, A in enumerate(angs):
        lo = a0 if i == 0 else 0.5 * (angs[i - 1] + A) + gap * 0.5
        hi = a1 if i == len(angs) - 1 else 0.5 * (A + angs[i + 1]) - gap * 0.5
        so, si = [], []
        for r in range(rows_n + 1):
            sr = r / rows_n
            ro, ri = [], []
            for c in range(3):
                phi = lo + (hi - lo) * c / 2.0
                ss = sr + (0.06 if (r == rows_n and c == 1) else 0.0)
                p_out = CR.cloak_point(phi, min(1.0, ss), 0.0)
                p_in = CR.cloak_point(phi, min(1.0, ss), -0.012)
                if ss > 1.0:
                    tan = (CR.cloak_point(phi, 1.0) - CR.cloak_point(phi, 0.97)).normalized()
                    p_out, p_in = p_out + tan * (ss - 1.0) * drop_len(phi), p_in + tan * (ss - 1.0) * drop_len(phi)
                anc = CR.cloak_point(A, min(1.0, ss), 0.0)
                for p_, row in ((p_out, ro), (p_in, ri)):
                    v = k.bm.verts.new(p_)
                    v[k.anchor] = anc
                    row.append(v)
            so.append(ro)
            si.append(ri)
        fo, fi = [], []
        for r in range(rows_n):
            for c in range(2):
                fo.append(k.bm.faces.new((so[r][c], so[r][c + 1], so[r + 1][c + 1], so[r + 1][c])))
                fi.append(k.bm.faces.new((si[r][c + 1], si[r][c], si[r + 1][c], si[r + 1][c + 1])))
            fo.append(k.bm.faces.new((so[r][0], so[r + 1][0], si[r + 1][0], si[r][0])))
            fo.append(k.bm.faces.new((so[r][2], si[r][2], si[r + 1][2], so[r + 1][2])))
        for c in range(2):
            fo.append(k.bm.faces.new((so[rows_n][c], so[rows_n][c + 1], si[rows_n][c + 1], si[rows_n][c])))
            fo.append(k.bm.faces.new((so[0][c + 1], so[0][c], si[0][c], si[0][c + 1])))
        k._new([v for row in so + si for v in row], C["shell"], None, None)
        # la cara de adentro en el verde medio de las hojas (se ve con la capa abierta: oscura se leía como un agujero)
        k.tag(fi, C["shell_in"])

    def leaf_at(phi, sb, ln, out_b, lift, nrm_sign, col, width=None, yaw=0.0, under=None, inner=False):
        D = drop_len(phi)
        base = CR.cloak_point(phi, sb, out_b)
        ts = sb + ln / D
        if ts <= 1.0:
            tip = CR.cloak_point(phi + yaw * ln / max(0.2, CR.cloak_rz(phi, sb).x), ts, out_b + lift)
        else:
            end = CR.cloak_point(phi, 1.0, out_b + lift)
            tan = (CR.cloak_point(phi, 1.0) - CR.cloak_point(phi, 0.96)).normalized()
            tip = end + tan * (ts - 1.0) * D
        nrm = CR.cloak_normal(phi, min(1.0, sb + 0.5 * ln / D)) * nrm_sign
        k.leaf(base, tip, nrm, width or max(0.055, ln * 0.36), col, ridge=0.16, under=under or C["leafu"], wide=0.45)

    # la gola: hojas paradas alrededor de la nuca y los costados del cuello, hacia arriba y afuera (no adelante)
    for phi in arc_samples(66.0, 294.0, 0.02, 0.01, 0.046, rng):
        base = CR.cloak_point(phi, 0.02, 0.01)
        outv = Vector((base.x, base.y - CR.CLOAK_Y0, 0.0)).normalized()
        ln = 0.15 * rng.uniform(0.9, 1.1)
        tip = base + (outv * 0.75 + Vector((0, 0, 0.75))).normalized() * ln
        k.leaf(base, tip, outv - Vector((0, 0, 0.6)), 0.046, C["leaf1b"] if rng.random() < 0.6 else C["leaf1"], ridge=0.3,
               under=C["leafu"])
    # las dos coronas del cuello: hojas que salen en estrella sobre la cáscara de los hombros y la espalda alta (la vista
    # de arriba de la hoja de detalles), bien pegadas y anchas: desde la cámara alta la cáscara solo asoma entre puntas
    for s, sp, lr, ca, cb in ((0.05, 0.060, 0.30, "leaf1b", "leaf1c"), (0.13, 0.070, 0.34, "leaf1", "leaf1b")):
        for j, phi in enumerate(arc_samples(a0 - 2.0, a1 + 2.0, s, 0.008, sp, rng)):
            ln = lr * rng.uniform(0.85, 1.1)
            col = C[ca] if (j % 3) else C[cb]
            leaf_at(phi, s + rng.uniform(-0.01, 0.01), ln, 0.008 + 0.006 * (s > 0.1), 0.012 + 0.012 * rng.random(), 1.0, col,
                    width=0.075 * rng.uniform(0.9, 1.1), yaw=rng.uniform(-10.0, 10.0))
    # el yugo: hojas anchas que salen hacia afuera y caen ~35° en todo el contorno, más en los hombros (la silueta en
    # púas del concepto, sin bigotes finos)
    for j, phi in enumerate(arc_samples(a0, a1, 0.22, 0.02, 0.085, rng)):
        side = max(0.0, 1.0 - abs(abs(((phi + 180.0) % 360.0) - 180.0) - 90.0) / 40.0)
        ln = (0.22 + 0.06 * side) * rng.uniform(0.9, 1.08)
        col = C["leaf1"] if j % 3 else C["leaf1b"]
        leaf_at(phi, 0.22 + rng.uniform(-0.015, 0.015), ln, 0.022, 0.05 + 0.07 * side, 1.0, col, width=0.07 * rng.uniform(0.9, 1.1),
                yaw=rng.uniform(-8.0, 8.0))
    # las hileras que cuelgan como tejas (las de arriba encima de las de abajo; de cada hoja se ve la parte ancha):
    # oliva al medio y verde oscuro abajo, más largas hacia el ruedo de la espalda
    # por pisos, de claro arriba a oscuro abajo (como en la hoja), menos hojas y más grandes: mezcladas de a una se leía
    # un ruido parejo y no las tejas de hojas del concepto
    for ri_, (s, ca, cb) in enumerate(((0.32, "leaf1b", "leaf1"), (0.46, "leaf1", "leaf1b"), (0.60, "leaf1", "leaf2"),
                                       (0.74, "leaf2", "leaf1"), (0.87, "leaf2", "leaf3"))):
        # la del ruedo más rala (las hojas de las ranuras la completan)
        for j, phi in enumerate(arc_samples(a0, a1, s, 0.0, 0.140 if s > 0.8 else 0.112, rng)):
            D = drop_len(phi)
            sb = s + rng.uniform(-0.015, 0.015)
            ln = (0.20 + 0.25 * min(1.0, D / 1.45)) * rng.uniform(0.9, 1.1)
            col = C[ca] if (j + ri_) % 3 else C[cb]
            leaf_at(phi, sb, ln, 0.006 + 0.026 * (1.0 - sb), 0.012 + 0.025 * rng.random(), 1.0, col,
                    yaw=rng.uniform(-9.0, 9.0) * (0.4 if D < 0.8 else 1.0))
    # dos hojas largas en cada ranura entre paños, pesadas a los dos: con la capa quieta tapan la ranura y abierta cuelgan
    # entre los paños como hojas sueltas (la silueta sigue siendo de hojas y no de paneles)
    for i in range(len(angs) - 1):
        mid = 0.5 * (angs[i] + angs[i + 1])
        for sb, ln, col in ((0.50, 0.30, C["leaf2"]), (0.76, 0.32, C["leaf1"])):
            if drop_len(mid) * (1.0 - sb) > 0.12:
                leaf_at(mid + rng.uniform(-1.5, 1.5), sb + rng.uniform(-0.02, 0.02), ln * rng.uniform(0.9, 1.1), 0.030, 0.02, 1.0, col,
                        width=0.08)
    # las hojas de adentro: en los paños de detrás del brazo y la espalda, mirando hacia el cuerpo, más oscuras, puntas
    # abajo y pasando el ruedo (con los brazos arriba, en el salto y colgado no se ve una cáscara lisa)
    for s, sp in ((0.34, 0.12), (0.52, 0.11), (0.70, 0.11), (0.88, 0.10)):
        for j, phi in enumerate(arc_samples(70.0, 290.0, s, -0.012, sp, rng)):
            D = drop_len(phi)
            if D < 0.55:
                continue
            ln = (0.16 + 0.16 * min(1.0, D / 1.45)) * rng.uniform(0.9, 1.1)
            leaf_at(phi, s + rng.uniform(-0.02, 0.02), ln, -0.020, -0.012, -1.0, C["leafu"] if j % 2 else C["leaf3"],
                    width=0.06, under=C["gi3"])


def hole_round(k, c, ax, side, nrm, d, color=None):
    """Un agujero de bambú redondo: una pirámide hexagonal muy chata y oscura de diámetro d sobre la cara del caño (sin
    base: queda contra el caño y nunca se ve; el cálculo de normales la deja mirando afuera)."""
    vs = [k.bm.verts.new(c - nrm * 0.0008 + ax * (math.sin(2 * math.pi * i / 6) * d * 0.5) +
                         side * (math.cos(2 * math.pi * i / 6) * d * 0.5)) for i in range(6)]
    tip = k.bm.verts.new(c + nrm * 0.0016)
    for i in range(6):
        k.bm.faces.new((vs[i], vs[(i + 1) % 6], tip))
    k._new(vs + [tip], color or C["hole"], None, None)


def build_chimes(kits):
    """Los cascabeles de bambú hueco (la hoja de detalles): un lazo de cordón oscuro (dos tiras de 4 lados) desde la capa
    hasta el borde del tubo, el tubo de 6 lados abierto arriba (la boca oscura), el nudo a un tercio de la altura (una
    franja más ancha color trigo oscuro), dos agujeros redondos de 2 cm en la cara que mira afuera y la boca de abajo
    oscura. El tubo es del material que brilla de su grupo (Hi = hombros, agudos; Lo = espalda, graves); cada uno entero
    en su hueso (Acc_Chimes*_0: el juego lo mueve con SpringChain)."""
    for name, g, a, s, cord, ln, r in CR.chimes_full():
        bn = name + "_0"
        top, tail = bh(bn), bt(bn)
        ax = (tail - top).normalized()
        k = kits[name] = Kit("part_" + name, bn)
        slot = SLOT_CHIME_HI if g == "Hi" else SLOT_CHIME_LO
        nrm = CR.cloak_normal(a, s)
        nrm = (nrm - ax * nrm.dot(ax)).normalized()
        side = ax.cross(nrm).normalized()
        t0 = top + ax * cord
        for sd in (-1.0, 1.0):
            k.tube([top - ax * 0.004, t0 + side * (r * 0.72 * sd) + ax * 0.006], [0.0078, 0.0078], 4, C["cord"], phase=math.pi / 4,
                   cap0=False, cap1=False)
        # el tubo: la boca de arriba, el nudo a un tercio (más ancho) y el caño hasta la boca de abajo
        zn = ln * 0.33
        pts = [t0, t0 + ax * zn, t0 + ax * (zn + 0.022), t0 + ax * ln]
        part = k.tube(pts, [r, r * 1.13, r * 1.02, r], 6, "white", ups=[nrm] * 4, phase=0.0, cap0=True, cap1=True, slot=slot,
                      ring_colors=[("white", slot), C["node"], ("white", slot)])
        for f in part.faces:
            if len(f.verts) > 4:
                k.tag([f], C["hole"])
        # dos agujeros redondos en la cara que mira afuera de la capa (y hacia la cámara)
        fc = r * math.cos(math.pi / 6)
        for z in (zn + 0.022 + (ln - zn) * 0.30, zn + 0.022 + (ln - zn) * 0.62):
            hole_round(k, t0 + ax * z + nrm * fc, ax, side, nrm, 0.020)


# =========================================================================== flauta-bastón (rígida)
def build_staff():
    """Flauta-bastón de 2.1 m: los tramos del material que brilla (se encienden enteros en el aviso), los nudos de bambú
    hinchados (1.2 veces el caño, con el lomo en cordón verde y el bambú seco abajo), los seis agujeros redondos del
    tercio de arriba y el de soplar (2 cm, un tercio del caño, como en la hoja de detalles), el vendado oscuro en vueltas
    diagonales de tinta y hierro cerca de la punta de abajo y las dos bocas huecas. Se autora a lo largo de +Z desde la
    punta de abajo (el hueso Staff va de esa punta a la de arriba)."""
    k = Kit("Chikuo_Staff", "Staff")
    Ln, r = CR.STAFF_LEN, CR.STAFF_R
    nodes = [0.40, 0.70, 0.99, 1.27, 1.54, 1.80]
    holes = [1.36, 1.44, 1.60, 1.68, 1.88, 1.95]
    g0, g1 = CR.STAFF_GRIP
    sides = 7
    ph = math.pi / 2 - math.pi / sides          # una cara mira a -Y (adelante en el reposo): ahí van los agujeros
    up = [(0, -1, 0)] * 4
    grips = [g0 + (g1 - g0) * i / 4 for i in range(5)]
    stops = sorted({0.0, Ln} | set(grips) | {z + d for z in nodes for d in (-0.018, 0.018)})
    for z0, z1 in zip(stops[:-1], stops[1:]):
        mid = (z0 + z1) * 0.5
        if any(abs(mid - z) < 0.019 for z in nodes):
            continue
        grip = g0 <= mid <= g1
        rad = r * (1.12 if grip else 1.0)
        p = k.tube([(0, 0, z0), (0, 0, z1)], [rad, rad], sides, "white", ups=up[:2], phase=ph, cap0=False, cap1=False, slot=SLOT_STAFF)
        if grip:
            # el vendado: las vueltas en diagonal (cada tramo corre la franja de hierro una cara: una espiral)
            seg = grips.index(z0)
            for f in p.faces:
                c = f.calc_center_median()
                side_i = int(((math.atan2(c.y, c.x) - ph) % (2 * math.pi)) / (2 * math.pi / sides) + 0.5) % sides
                k.tag([f], C["staff_grip2"] if (side_i + seg * 2) % sides in (0, 1) else C["staff_grip"])
    for z in nodes:
        k.tube([(0, 0, z - 0.018), (0, 0, z), (0, 0, z + 0.018)], [r * 1.0, r * 1.2, r * 1.0], sides, C["staff_node"], ups=up[:3],
               phase=ph, cap0=False, cap1=False, ring_colors=[C["staff_node"], C["staff_cord"]])
    # los seis agujeros del tercio de arriba y el de soplar, en la cara de adelante
    fc = r * math.cos(math.pi / sides)
    for z in holes + [Ln - CR.STAFF_FLUTE]:
        hole_round(k, Vector((0, -fc, z)), Vector((0, 0, 1)), Vector((1, 0, 0)), Vector((0, -1, 0)), 0.020, C["staff_hole"])
    # las bocas huecas: el canto de bambú seco y el interior oscuro, fundidos con el último anillo del caño
    for z, s in ((0.0, -1.0), (Ln, 1.0)):
        k.tube([(0, 0, z), (0, 0, z - s * 0.002), (0, 0, z - s * 0.03)], [r, r * 0.70, r * 0.45], sides, C["staff_hole"],
               ups=up[:3], phase=ph, cap0=False, cap1=True, ring_colors=[C["staff_node"], C["staff_hole"]])
    return k


# =========================================================================== armado
def finish_kit(kit):
    # la piel y el gi se autoran con colores de la paleta que ninguna otra pieza usa ('lantern_paper', 'copper_green') y
    # acá pasan a sus materiales propios
    marks = [(Vector(L.P.uv_of(C["skin"])), SLOT_SKIN), (Vector(L.P.uv_of(C["gi"])), SLOT_GI)]
    lay = kit.uv
    for f in kit.bm.faces:
        if f.material_index == L.SLOT_PALETTE and f.loops:
            uv = f.loops[0][lay].uv
            for mk, slot in marks:
                if (uv - mk).length < 1e-4:
                    f.material_index = slot
    obj = kit.finish()
    for n in EXTRA_MATS:
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
        o = finish_kit(k)
        per[bn] = tri_count(o)
        vg = {}
        anc = o.data.attributes.get("anchor")
        anchors = [Vector(d.vector) for d in anc.data] if anc else None
        for v in o.data.vertices:
            co = anchors[v.index] if anchors and anchors[v.index].length_squared > 0.0 else v.co
            w = k.weights(co) if k.weights else {k.bone: 1.0}
            # Unity pesa a lo sumo 4 huesos por vértice: los más chicos se reparten entre los que quedan
            top = sorted(((val, n_) for n_, val in w.items() if val > 1e-5), reverse=True)[:4]
            w = {n_: val for val, n_ in top}
            tot = sum(w.values())
            for n_, val in w.items():
                if n_ not in vg:
                    vg[n_] = o.vertex_groups.get(n_) or o.vertex_groups.new(name=n_)
                vg[n_].add([v.index], val / tot, 'REPLACE')
        if anc:
            o.data.attributes.remove(anc)
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
    """Pieza rígida hija de su hueso: la caña se autora a lo largo de +Z y pasa al eje Y del hueso."""
    o = finish_kit(kit)
    o.data.transform(Matrix.Rotation(-math.pi / 2, 4, 'X'))
    o.parent = arm
    o.parent_type = 'BONE'
    o.parent_bone = kit.bone
    bpy.context.view_layer.update()
    o.matrix_world = rig.rest[kit.bone]
    clean_slots(o)
    return o


def build(arm, rig):
    """Construye la malla con skin (cuerpo, ropa, capa y cascabeles) y la flauta-bastón, y las engancha a la armadura.
    Devuelve ({nombre: objeto}, triángulos por grupo)."""
    ensure_extra_materials()
    kits = {}
    build_leg_r(kits)
    build_sleeve_r(kits)
    for bn in list(kits):
        src = kits[bn]
        ln = side_name(bn)
        kits[ln] = mirror_kit(src, "part_" + ln, side_name(src.bone), weights=mirror_weights(src.weights))
    # el zapato izquierdo brilla con su propio slot
    for f in kits["Foot_L"].bm.faces:
        if f.material_index == SLOT_FOOT_R:
            f.material_index = SLOT_FOOT_L
    build_hips(kits)
    build_gi(kits)
    build_skirt(kits)
    build_sash(kits)
    build_head(kits)
    build_hair(kits)
    build_brows_hair(kits)
    place_head(kits)
    build_topknot(kits)
    build_beard(kits)
    groups = {"body": list(kits)}
    build_cloak(kits)
    groups["cloak"] = ["Cloak"]
    n0 = len(kits)
    build_chimes(kits)
    groups["chimes"] = list(kits)[n0:]
    body, per = join(kits, "Chikuo_Body", arm)
    staff = rigid(build_staff(), arm, rig)
    stats = {g: sum(per[n] for n in names) for g, names in groups.items()}
    stats["staff"] = tri_count(staff)
    print("TRIS_POR_PIEZA", sorted(per.items(), key=lambda kv: -kv[1])[:14])
    return {"Chikuo_Body": body, "Chikuo_Staff": staff}, stats
