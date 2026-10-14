"""Geometría del Chikuō ermitaño (fase C4): el concepto elegido 'opción 6' (Docs/handoff/conceptos/chikuo_v2/elegido_*.jpg)
al pie de la letra, en el low-poly facetado de Nindō.

Lo que se lee desde la cámara del juego (52°, 24 m: un personaje de 1.5 m mide ~100 px y Chikuō parado ~160 px) es la
forma y el valor, no el detalle:
  * arriba del todo el blanco: el moño facetado con su cordón verde y la ramita, las cejas en púas más anchas que la
    cabeza y la barba larga anudada hasta el ombligo (una franja blanca de ~1 m entre las hojas verdes);
  * la capa de hojas de bambú en tres tonos (claras arriba, oscuras abajo: más oscura que sus cañas) con 22 cascabeles
    huecos color paja-oro alrededor: la luz de la pelea (dos materiales que el juego enciende: Chikuo_GlintChimesHi en
    los hombros, Lo en la espalda);
  * el gi salvia con el ribete paja (cuello cruzado, puños, ruedo), la faja verde anudada con dos colas paja, el
    pantalón ancho que se infla en la rodilla, las polainas vendadas y las sandalias-zapato negras con suela y tiras paja;
  * la flauta-bastón paja-amarilla de 2.1 m (objeto rígido en el hueso Staff): nudos con cordón verde, seis agujeros en
    el tercio de arriba, el agujero de soplar, el vendado oscuro cerca de la punta de abajo y las bocas huecas.
De cerca (la presentación, los cambios de fase): calvo arriba con el pelo blanco peinado hacia el moño, orejas en punta,
nariz larga y ganchuda, ojos chicos entrecerrados, la sonrisa ancha con dientes en punta, arrugas en facetas.
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
SLOT_SKIN, SLOT_CHIME_HI, SLOT_CHIME_LO, SLOT_STAFF, SLOT_FOOT_R, SLOT_FOOT_L = 4, 5, 6, 7, 8, 9
EXTRA_MATS = ["Chikuo_Skin", "Chikuo_GlintChimesHi", "Chikuo_GlintChimesLo", "Chikuo_GlintStaff", "Chikuo_GlintFootR",
              "Chikuo_GlintFootL"]
# piel curtida de ermitaño (la del concepto: #dda982 a la luz, #98694f en la sombra); las sombras van con la paleta
SKIN_RGB = (0.84, 0.62, 0.45)
# cascabeles paja-oro (el concepto: #e1a96c) y la flauta paja-amarilla, más verde (bambú seco): se distinguen entre sí
CHIME_RGB = (0.86, 0.64, 0.38)
STAFF_RGB = (0.80, 0.74, 0.35)
# las sandalias-zapato: negro azulado (con 0.13 en el canal más alto CharacterFactory.LiftBlacks no las toca)
SHOE_RGB = (0.115, 0.11, 0.13)
MAT_RGB = {"Chikuo_Skin": SKIN_RGB, "Chikuo_GlintChimesHi": CHIME_RGB, "Chikuo_GlintChimesLo": CHIME_RGB,
           "Chikuo_GlintStaff": STAFF_RGB, "Chikuo_GlintFootR": SHOE_RGB, "Chikuo_GlintFootL": SHOE_RGB}
# el señuelo de hojas (Tricks: la misma malla con todos los slots en este material, sin brillo): no está en el FBX,
# generate_assets escribe su .mat desde el sidecar
DECOY_MAT, DECOY_RGB = "Chikuo_Decoy", (0.30, 0.54, 0.24)

C = dict(skin="lantern_paper", skin2="wood_pale", skin3="clay", mouth="wood_dark",
         white="white", white2="cloth_white", white3="plaster_shade",
         gi="stone_moss", gi2="tatami_edge", gi3="leaf_pine_dark",
         trim="straw", trim2="thatch",
         sash="leaf", sash2="leaf_dark", sash3="bamboo",
         pants="tatami_edge", pants2="leaf_pine_dark",
         leg="stone_moss", leg2="tatami_edge",
         wrap="cloth_black", wrap2="stone_dark",
         sole="rope", sole2="thatch", strap="straw",
         leaf1="moss", leaf1b="bamboo", leaf1c="grass_dry", leaf2="bamboo_dark", leaf3="leaf_dark", shell="leaf_dark",
         cord="rope", hole="gold_dark", node="wheat_dark",
         staff_node="bamboo_dry", staff_cord="leaf", staff_grip="ink", staff_grip2="iron", staff_hole="wood_dark",
         eye="ink", eyew="paper", knot="leaf", knot2="leaf_dark")

KB = {b.name: b for b in CR.bones()}


def bh(n):
    return KB[n].head.copy()


def bt(n):
    return KB[n].tail.copy()


def ramp(z, z0, z1):
    return smooth01((z - z0) / (z1 - z0))


# =========================================================================== cabeza
# perfil radial de la cabeza: por altura, el centro (y) y la distancia al eje a los 0, 22.5 ... 180° (0 = frente,
# espejado del otro lado). La cara del concepto: el cráneo grande y pelado arriba, las sienes anchas, el arco de la
# ceja que sobresale y hunde los ojos, los pómulos altos, las mejillas chupadas y la cara que se angosta en V hasta un
# mentón chico (bajo la barba). La banda de la boca (2.074-2.083) es la de la sonrisa: abajo va con la quijada
HEAD_RINGS = [
    (2.030, -0.030, [0.050, 0.046, 0.038, 0.032, 0.030, 0.030, 0.030, 0.030, 0.030]),
    (2.050, -0.020, [0.074, 0.068, 0.054, 0.046, 0.044, 0.044, 0.046, 0.048, 0.050]),
    (2.066, -0.014, [0.087, 0.081, 0.063, 0.055, 0.053, 0.055, 0.059, 0.063, 0.065]),
    (2.074, -0.011, [0.090, 0.085, 0.067, 0.059, 0.058, 0.060, 0.065, 0.070, 0.072]),
    (2.083, -0.009, [0.093, 0.087, 0.070, 0.063, 0.063, 0.066, 0.072, 0.077, 0.079]),
    (2.100, -0.006, [0.096, 0.090, 0.074, 0.069, 0.071, 0.077, 0.085, 0.090, 0.092]),
    (2.122, -0.004, [0.097, 0.095, 0.091, 0.087, 0.085, 0.089, 0.097, 0.102, 0.104]),
    (2.145, -0.003, [0.092, 0.087, 0.085, 0.088, 0.089, 0.094, 0.101, 0.106, 0.108]),
    (2.165, -0.002, [0.095, 0.090, 0.088, 0.089, 0.091, 0.097, 0.104, 0.109, 0.111]),
    (2.182, -0.001, [0.104, 0.102, 0.096, 0.091, 0.092, 0.098, 0.105, 0.110, 0.112]),
    (2.205, 0.002, [0.098, 0.097, 0.094, 0.091, 0.091, 0.098, 0.105, 0.109, 0.111]),
    (2.228, 0.005, [0.088, 0.088, 0.086, 0.084, 0.085, 0.091, 0.097, 0.101, 0.102]),
    (2.248, 0.008, [0.070, 0.070, 0.069, 0.068, 0.069, 0.074, 0.079, 0.081, 0.082]),
    (2.262, 0.010, [0.044, 0.044, 0.044, 0.044, 0.045, 0.048, 0.051, 0.053, 0.053]),
]
HEAD_SCALE = 1.05            # un poco más grande que la medida del concepto: la cara se lee desde más lejos
HEAD_TOP = (0.0, 0.012, 2.270)
HEAD_SIDES = 16
MOUTH_Z = 2.078              # el medio de la banda de la boca


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


def head_angle(co):
    return math.degrees(math.atan2(co.x, -co.y))


def jaw_weight(co):
    """Cuánto sigue a la quijada un punto de la cara: todo lo de abajo de la boca adelante, y hacia atrás la línea sube a
    la bisagra delante de la oreja (las mejillas de abajo bajan con la boca abierta; la nuca no)."""
    a = abs(head_angle(co))
    if a > 105.0:
        return 0.0
    line = MOUTH_Z + 0.046 * smooth01((a - 40.0) / 40.0)
    w = 1.0 - smooth01((co.z - (line - 0.005)) / 0.010)
    return w * (1.0 - smooth01((a - 85.0) / 20.0))


def w_face(co):
    """Pesos de la cara: cabeza, quijada, cachetes y comisuras."""
    j = jaw_weight(co)
    w = {"Head": 1.0 - j}
    if j > 0.0:
        w["Jaw"] = j
    for S in "RL":
        c0 = CR.mx(CR.CHEEK_R[0]) if S == "L" else CR.CHEEK_R[0]
        d = (co - (c0 + Vector((0.0, -0.02, 0.0)))).length
        if d < 0.034 and co.z > MOUTH_Z + 0.006:
            k = 0.75 * (1.0 - smooth01(d / 0.034))
            w = {n: v * (1.0 - k) for n, v in w.items()}
            w["Cheek_" + S] = k
        m0 = CR.mx(CR.CORNER_R[0]) if S == "L" else CR.CORNER_R[0]
        d = (co - m0).length
        if d < 0.024:
            k = 0.7 * (1.0 - smooth01(d / 0.024))
            w = {n: v * (1.0 - k) for n, v in w.items()}
            w["MouthCorner_" + S] = k
    if co.z < 2.06 and abs(head_angle(co)) > 100.0:
        k = 0.45 * (1.0 - smooth01((co.z - 2.03) / 0.03))
        w = {n: v * (1.0 - k) for n, v in w.items()}
        w["Neck"] = w.get("Neck", 0.0) + k
    return w


def build_head(kits):
    k = kits["Head"] = Kit("part_Head", "Head", weights=w_face)
    rings = [[head_surface(z, 360.0 * i / HEAD_SIDES) for i in range(HEAD_SIDES)] for z, _, _ in HEAD_RINGS]
    part = k.rings_loft(rings, C["skin"], True, False)
    top = k.bm.verts.new(HEAD_TOP)
    last = part.verts[-HEAD_SIDES:]
    k.tag([k.bm.faces.new((last[i], last[(i + 1) % HEAD_SIDES], top)) for i in range(HEAD_SIDES)], C["skin"])
    # facetas en sombra (la cara del concepto está tallada): las cuencas, la mejilla chupada bajo el pómulo, el surco de
    # la nariz a la sonrisa, las arrugas de la frente, el costado de la quijada; la banda de la boca oscura (la garganta)
    for f in part.faces:
        c = f.calc_center_median()
        a = abs(head_angle(c))
        if 2.074 < c.z < 2.083 and a < 62:
            k.tag([f], C["mouth"])
        elif 2.140 < c.z < 2.174 and 6 < a < 44:
            k.tag([f], C["skin3"])
        elif 2.083 < c.z < 2.122 and 28 < a < 72:
            k.tag([f], C["skin2"])
        elif 2.19 < c.z < 2.214 and a < 42:
            k.tag([f], C["skin2"])
        elif c.z < 2.066 and 25 < a < 100:
            k.tag([f], C["skin2"])
    build_nose(k)
    for s in (-1.0, 1.0):
        k.gem((0.020 * s, -0.124, 2.097), 0.012, C["skin2"], sides=4, height=0.009, axis=(0.6 * s, -0.75, -0.1))
        k.gem((0.020 * s, -0.128, 2.091), 0.006, C["skin3"], sides=4, height=0.004, axis=(0.3 * s, -0.5, -0.8))
        build_eye(kits, s)
        build_ear(k, s)
        # el surco de la nariz a la comisura (las arrugas de la sonrisa pícara)
        k.strip([Vector((0.024 * s, -0.112, 2.104)), Vector((0.040 * s, -0.098, 2.099)), Vector((0.054 * s, -0.080, 2.094))],
                [0.006, 0.007, 0.006], [(0.4 * s, -1, 0.3)] * 3, C["skin3"], thick=0.004)
    build_mouth(kits)
    # cuello flaco (casi todo tapado por la barba y el cuello de la capa)
    kn = kits["Neck"] = Kit("part_Neck", "Neck", weights=lambda co: (
        {"Spine2": 1.0 - ramp(co.z, 1.9, 1.96), "Neck": ramp(co.z, 1.9, 1.96)} if co.z < 1.97 else
        {"Neck": 1.0 - 0.5 * ramp(co.z, 2.0, 2.05), "Head": 0.5 * ramp(co.z, 2.0, 2.05)}))
    kn.tube([(0, 0.03, 1.86), (0, 0.022, 1.95), (0, 0.012, 2.05)], [(0.056, 0.054), (0.05, 0.048), (0.05, 0.048)], 8, C["skin"],
            phase=math.pi / 8, cap0=False, cap1=False)
    for s in (-1, 1):
        kn.obox((0.026 * s, -0.022, 1.98), (0.010, 0.010, 0.10), (1, 0, 0), (0, 1, 0.25 * -s), C["skin2"])


def build_nose(k):
    """La nariz larga en pico (la de la hoja): una cuña pegada a la cara, angosta en el entrecejo, ancha en las aletas, con
    el lomo afilado y la punta que cae; cerrada por detrás adentro de la cara."""
    B, M, T = Vector((0, -0.101, 2.172)), Vector((0, -0.140, 2.130)), Vector((0, -0.170, 2.101))
    U, Cc, I = Vector((0, -0.151, 2.090)), Vector((0, -0.122, 2.092)), Vector((0, -0.086, 2.128))
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
        elif abs(f.normal.x) > 0.6:
            k.tag([f], C["skin2"])


def build_eye(kits, s):
    """Ojo hundido bajo el arco de la ceja, almendrado y torcido (la punta de adentro más baja: la mirada pícara): el
    blanco amarillento, la pupila negra con un punto de luz y la bolsa oscura abajo. El párpado de arriba (Lid_*) en
    reposo tapa la parte de arriba y al girar 60° cierra el ojo."""
    S = "R" if s < 0 else "L"
    E = CR.EYE_R if S == "R" else CR.mx(CR.EYE_R)
    k = kits["Head"]
    fwd = Vector((0.30 * s, -1.0, 0.0)).normalized()
    side = Vector((0, 0, 1)).cross(fwd).normalized()
    # el blanco: rombo chato inclinado (la punta de afuera más alta)
    tilt = Matrix.Rotation(math.radians(-14.0 * s), 3, fwd)
    pts = [E + tilt @ (side * dx + Vector((0, 0, dz))) for dx, dz in ((0.021, 0.0), (0.0, 0.0102), (-0.021, 0.0), (0.0, -0.0086))]
    vc = k.bm.verts.new(E + fwd * 0.0075)
    vr = [k.bm.verts.new(p) for p in pts]
    for i in range(4):
        k.bm.faces.new((vr[i], vr[(i + 1) % 4], vc))
    k.bm.faces.new(list(reversed(vr)))
    k._new(vr + [vc], C["eyew"], None, None)
    k.gem(E + fwd * 0.0068 + side * (0.002 * s), 0.0094, C["eye"], sides=6, height=0.0034, axis=fwd)
    k.gem(E + fwd * 0.0092 + side * (-0.0025 * s) + Vector((0, 0, 0.0028)), 0.0021, C["white"], sides=4, height=0.0011, axis=fwd)
    # la bolsa de abajo
    k.strip([E + tilt @ (side * 0.016 + Vector((0, 0, -0.010))) + fwd * 0.004, E + Vector((0, 0, -0.012)) + fwd * 0.006,
             E + tilt @ (side * -0.016 + Vector((0, 0, -0.008))) + fwd * 0.004], [0.006, 0.007, 0.006], [fwd] * 3, C["skin3"],
            thick=0.004)
    # el párpado: casquete de un cuarto de esfera alrededor del centro del ojo (más grande que el ojo)
    kl = kits["Lid_" + S] = Kit("part_Lid_" + S, "Lid_" + S)
    R = 0.0150
    rows = []
    for el in (18.0, 46.0, 78.0):
        row = []
        for az in (-64.0, -32.0, 0.0, 32.0, 64.0):
            e, a = math.radians(el), math.radians(az)
            d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
            d = Matrix.Rotation(math.radians(-17.0 * s), 3, 'Z') @ Matrix.Rotation(math.radians(-12.0 * s), 3, 'Y') @ d
            row.append(E + d * R)
        rows.append(row)
    inner = [[E + (p - E) * 0.86 for p in row] for row in rows]
    vo = [[kl.bm.verts.new(p) for p in r] for r in rows]
    vi = [[kl.bm.verts.new(p) for p in r] for r in inner]
    fo, fi = [], []
    for r in range(len(rows) - 1):
        for i in range(4):
            fo.append(kl.bm.faces.new((vo[r][i], vo[r][i + 1], vo[r + 1][i + 1], vo[r + 1][i])))
            fi.append(kl.bm.faces.new((vi[r][i + 1], vi[r][i], vi[r + 1][i], vi[r + 1][i + 1])))
    rim = [kl.bm.faces.new((vo[0][i + 1], vo[0][i], vi[0][i], vi[0][i + 1])) for i in range(4)]
    kl._new([v for row in vo + vi for v in row], C["skin2"], None, None)
    kl.tag(rim, C["mouth"])
    kl.tag(fi, C["skin3"])


def build_ear(k, s):
    """Oreja grande en punta hacia afuera y arriba (el duende del concepto): una lámina con espesor, afuera piel, el
    hueco oscuro adelante."""
    # contorno en el plano de la oreja: (altura, y, cuánto sale de la cabeza)
    out = [(2.118, 0.010, 0.002), (2.132, -0.008, 0.030), (2.165, 0.006, 0.056), (2.228, 0.058, 0.084), (2.180, 0.054, 0.052),
           (2.148, 0.046, 0.026), (2.126, 0.032, 0.004)]
    pts = []
    for z, y, o in out:
        p = head_surface(min(z, 2.17), 90.0 * s, 0.0)
        pts.append(Vector((p.x + o * s, y, z)))
    nrm = Vector((s * 0.6, -0.72, 0.3)).normalized()
    th = 0.0075
    n = len(pts)
    cf = sum(pts, Vector()) / n
    vf = [k.bm.verts.new(p + nrm * th) for p in pts]
    vb = [k.bm.verts.new(p - nrm * th) for p in pts]
    vcf = k.bm.verts.new(cf + nrm * th)
    vcb = k.bm.verts.new(cf - nrm * th)
    fb, rim = [], []
    for i in range(n):
        j = (i + 1) % n
        k.bm.faces.new((vf[i], vf[j], vcf))
        fb.append(k.bm.faces.new((vb[j], vb[i], vcb)))
        rim.append(k.bm.faces.new((vf[j], vf[i], vb[i], vb[j])))
    k._new(vf + vb + [vcf, vcb], C["skin"], None, None)
    k.tag(fb, C["skin2"])
    k.tag(rim, C["skin2"])
    # el hueco de la oreja (adelante): una faceta oscura en la mitad de abajo
    hc = pts[0].lerp(pts[3], 0.40) + nrm * (th + 0.0012)
    k.obox(hc, (0.040, 0.003, 0.018), (pts[3] - pts[0]).normalized(), nrm, C["skin3"])


def grin_point(x, row):
    """Punto de la sonrisa sobre la cara: la curva sube fuerte en las comisuras. row 1 = encía de arriba, 0 = de abajo."""
    u = min(1.0, abs(x) / 0.056)
    z = MOUTH_Z + 0.003 * (2 * row - 1) + 0.014 * u * u
    a = math.degrees(math.asin(max(-1.0, min(1.0, x / 0.098))))
    p = head_surface(z, a, 0.002 - 0.003 * u)
    return Vector((x, p.y, z))


def build_mouth(kits):
    """La sonrisa ancha de oreja a oreja con dientes en punta (el rasgo de la hoja): los de arriba en la cabeza, los de
    abajo en la quijada, la garganta oscura detrás (se ve al reírse) y los labios finos estirados."""
    kh = kits["Head"]
    kj = kits["Jaw"] = Kit("part_Jaw", "Jaw", weights=w_face)
    n_up = 13
    for i in range(n_up):
        x = -0.050 + 0.100 * i / (n_up - 1)
        u = min(1.0, abs(x) / 0.056)
        p = grin_point(x, 1)
        base = p + Vector((0, 0.001, 0.0045))
        kh.spike(base, base + Vector((0.0, -0.0012, -0.0150 + 0.004 * u)), 0.0047, C["white"], sides=3, side_hint=(0, -1, 0),
                 flat=0.55, phase=math.pi / 2)
    n_lo = 12
    for i in range(n_lo):
        x = -0.046 + 0.092 * i / (n_lo - 1)
        u = min(1.0, abs(x) / 0.056)
        p = grin_point(x, 0) + Vector((0.0, 0.0022, 0.0))
        base = p - Vector((0, 0, 0.0045))
        kj.spike(base, base + Vector((0.0, -0.0008, 0.0128 - 0.004 * u)), 0.0044, C["white2"], sides=3, side_hint=(0, -1, 0),
                 flat=0.55, phase=math.pi / 2)
    # la garganta: placas oscuras detrás de los dientes (arriba en la cabeza, abajo en la quijada)
    for kk, row, dz in ((kh, 1, 0.006), (kj, 0, -0.006)):
        pts = [grin_point(x, row) + Vector((0, 0.008, dz)) for x in (-0.054, -0.028, 0.0, 0.028, 0.054)]
        kk.strip(pts, [0.016] * 5, (0, -1, 0), C["mouth"], thick=0.004)
    # labios finos y estirados (arriba piel en sombra, abajo apenas más claro)
    up = [grin_point(x, 1) + Vector((0, -0.0015, 0.0085)) for x in (-0.058, -0.036, 0.0, 0.036, 0.058)]
    kh.strip(up, [0.0055, 0.0065, 0.007, 0.0065, 0.0055], (0, -1, 0.4), C["skin2"], thick=0.006)
    lo = [grin_point(x, 0) + Vector((0, -0.001, -0.0085)) for x in (-0.054, -0.030, 0.0, 0.030, 0.054)]
    kj.strip(lo, [0.005, 0.0065, 0.007, 0.0065, 0.005], (0, -1, -0.3), C["skin"], thick=0.006)


def build_brows_hair(kits):
    """Cejas salvajes: una masa blanca del entrecejo a la sien con púas anchas hacia arriba y afuera (de frente son una
    corona más ancha que la cabeza), mechones en punta en las sienes, el pelo blanco peinado hacia atrás (pelado
    arriba adelante) y el moño."""
    for S, s in (("R", -1.0), ("L", 1.0)):
        m = (lambda v: Vector(v)) if S == "R" else (lambda v: Vector((-v[0], v[1], v[2])))
        kb = kits["Brow_" + S] = Kit("part_Brow_" + S, "Brow_" + S)
        # la masa nace baja junto a la nariz y sube hacia la sien (la V del ceño); las púas forman una llama que sube
        # hacia afuera y cae sobre la oreja
        base = [m((-0.010, -0.106, 2.164)), m((-0.034, -0.104, 2.178)), m((-0.062, -0.094, 2.194)), m((-0.090, -0.078, 2.206))]
        kb.tube(base, [(0.012, 0.010), (0.016, 0.013), (0.017, 0.013), (0.013, 0.011)], 5, C["white"], ups=[m((0, -0.5, 1))] * 4,
                phase=math.pi / 5, ring_colors=[C["white"], C["white2"], C["white"]])
        spikes = [((-0.014, -0.107, 2.168), (-0.002, -0.122, 2.200), 0.012),
                  ((-0.028, -0.106, 2.175), (-0.030, -0.128, 2.232), 0.015),
                  ((-0.044, -0.102, 2.184), (-0.066, -0.124, 2.262), 0.016),
                  ((-0.058, -0.096, 2.191), (-0.106, -0.112, 2.272), 0.016),
                  ((-0.072, -0.090, 2.198), (-0.146, -0.094, 2.262), 0.016),
                  ((-0.084, -0.082, 2.204), (-0.180, -0.070, 2.236), 0.015),
                  ((-0.090, -0.078, 2.204), (-0.192, -0.050, 2.198), 0.014),
                  ((-0.088, -0.076, 2.196), (-0.168, -0.040, 2.160), 0.012)]
        for i, (b, t, r) in enumerate(spikes):
            kb.spike(m(b), m(t), r * 1.25, C["white"] if i % 2 == 0 else C["white2"], sides=4, side_hint=(0, -0.3, 1), flat=0.45,
                     phase=math.pi / 4)
        # mechones de las sienes: salen sobre la oreja hacia afuera y atrás
        kh = kits["Hair"]
        for b, t, r in (((-0.088, -0.030, 2.208), (-0.162, -0.012, 2.244), 0.016), ((-0.094, -0.004, 2.190), (-0.172, 0.026, 2.190), 0.017),
                        ((-0.090, 0.022, 2.214), (-0.150, 0.074, 2.262), 0.015), ((-0.090, 0.03, 2.160), (-0.140, 0.086, 2.134), 0.014)):
            kh.spike(m(b), m(t), r, C["white"], sides=4, side_hint=(0, 0, 1), flat=0.6, phase=math.pi / 4)
        # patilla blanca de la sien a la barba, delante de la oreja
        kh.strip([m((-0.088, -0.018, 2.170)), m((-0.090, -0.034, 2.128)), m((-0.084, -0.052, 2.090)), m((-0.080, -0.060, 2.062))],
                 [0.030, 0.032, 0.032, 0.030], [m((-1, -0.25, 0))] * 4, C["white"], thick=0.014)
    build_topknot(kits)


def build_hair(kits):
    """El pelo blanco de los costados y la nuca peinado hacia el moño: un casco grueso sobre el cráneo (borde visible),
    mechones en surcos y puntas que caen sobre la nuca; arriba adelante queda la calva."""
    k = kits["Hair"] = Kit("part_Hair", "Head", weights=lambda co: {"Head": 1.0} if co.z > 2.06 else {"Head": 0.6, "Neck": 0.4})
    zs = [2.060, 2.092, 2.128, 2.162, 2.194, 2.222, 2.244, 2.258, 2.266]
    a0 = [118.0, 100.0, 70.0, 50.0, 46.0, 42.0, 40.0, 50.0, 80.0]
    cols = 20
    vo, vi = [], []
    for zi, (z, a) in enumerate(zip(zs, a0)):
        ro, ri = [], []
        for c in range(cols + 1):
            ang = a + (360.0 - 2 * a) * c / cols
            ridge = 0.010 if c % 2 else 0.0
            # el volumen crece hacia atrás y arriba (el pelo juntado hacia el moño)
            bulk = 0.018 + 0.012 * max(0.0, -math.cos(math.radians(ang))) * smooth01((z - 2.08) / 0.12)
            dz = (-0.022 if c % 2 else -0.006) if zi == 0 else 0.0
            ro.append(k.bm.verts.new(head_surface(z, ang, bulk + ridge) + Vector((0, 0, dz))))
            ri.append(k.bm.verts.new(head_surface(z, ang, -0.003) + Vector((0, 0, dz))))
        vo.append(ro)
        vi.append(ri)
    fo, edge = [], []
    for r in range(len(zs) - 1):
        for c in range(cols):
            fo.append(k.bm.faces.new((vo[r][c], vo[r + 1][c], vo[r + 1][c + 1], vo[r][c + 1])))
        edge.append(k.bm.faces.new((vo[r][0], vi[r][0], vi[r + 1][0], vo[r + 1][0])))
        edge.append(k.bm.faces.new((vo[r][cols], vo[r + 1][cols], vi[r + 1][cols], vi[r][cols])))
    for c in range(cols):
        edge.append(k.bm.faces.new((vo[0][c], vo[0][c + 1], vi[0][c + 1], vi[0][c])))
        edge.append(k.bm.faces.new((vo[-1][c + 1], vo[-1][c], vi[-1][c], vi[-1][c + 1])))
    k._new([v for row in vo + vi for v in row], C["white"], None, None)
    for f in fo:
        c = f.calc_center_median()
        k.tag([f], C["white2"] if (int(abs(head_angle(c)) / 9) % 2) else C["white"])
    k.tag(edge, C["white3"])


def build_topknot(kits):
    """El moño arriba y atrás: el pelo juntado bajo el cordón, tres vueltas de cordón verde y el mechón blanco
    facetado como una tela plegada que se abre hacia arriba en cinco puntas; la ramita de hojas sale del cordón hacia
    los costados y atrás (cadena LeafKnot)."""
    T0, ax = CR.TOPKNOT_BASE, CR.TOPKNOT_AXIS
    xv = Vector((1.0, 0.0, 0.0))
    yv = ax.cross(xv).normalized() * -1.0
    kh = kits["Hair"]
    kh.tube([T0 - ax * 0.03 + Vector((0, -0.01, 0)), T0 + ax * 0.004], [0.052, 0.036], 8, C["white"], ups=[yv] * 2,
            phase=math.pi / 8, cap0=False, cap1=False)
    for i, d in enumerate((0.004, 0.018, 0.032)):
        c = T0 + ax * d
        kh.tube([c, c + ax * 0.011], [0.0395 - 0.0015 * i, 0.0385 - 0.0015 * i], 8, C["knot"], ups=[yv] * 2,
                phase=math.pi / 8 + i * 0.35, cap0=False, cap1=False)
        kh.tube([c + ax * 0.011, c + ax * 0.0135], [0.034, 0.034], 8, C["knot2"], ups=[yv] * 2, phase=math.pi / 8,
                cap0=False, cap1=False)

    def w_tk(co):
        d = (co - T0).dot(ax)
        if d < 0.05:
            b = smooth01((d - 0.035) / 0.015)
            return {"Head": 1.0 - b, "Topknot_1": b}
        a = smooth01((d - 0.07) / 0.05)
        return {"Topknot_1": 1.0 - a, "Topknot_2": a}
    k = kits["Topknot"] = Kit("part_Topknot", "Topknot_1", weights=w_tk)
    lobes = 4
    spec = [(0.040, 0.028, 0.030, 0.0), (0.065, 0.034, 0.047, 14.0), (0.100, 0.040, 0.064, 30.0), (0.138, 0.044, 0.074, 44.0)]
    rings = []
    for d, rm, rl, tw in spec:
        c = T0 + ax * d
        ring = []
        for i in range(lobes * 2):
            a = math.radians(tw + 180.0 * i / lobes)
            r = rl if i % 2 == 0 else rm
            ring.append(c + xv * (math.cos(a) * r) + yv * (math.sin(a) * r))
        rings.append(ring)
    part = k.rings_loft(rings, C["white"], True, False)
    # la boca de arriba: cinco puntas (los pliegues) que suben y cinco valles que se hunden hacia el centro
    last = part.verts[-lobes * 2:]
    ctop = T0 + ax * 0.128
    vc = k.bm.verts.new(ctop)
    for i in range(lobes * 2):
        if i % 2 == 0:
            last[i].co = last[i].co + ax * 0.058 + (last[i].co - (T0 + ax * 0.138)) * 0.12
        else:
            last[i].co = last[i].co + ax * 0.004
    fs = [k.bm.faces.new((last[i], last[(i + 1) % (lobes * 2)], vc)) for i in range(lobes * 2)]
    k.tag(fs, C["white"])
    for f in part.faces + fs:
        c = f.calc_center_median() - T0
        a = math.degrees(math.atan2(c.dot(yv), c.dot(xv)))
        if int((a + 360.0) / 36.0) % 2:
            k.tag([f], C["white2"])
    # la ramita del cordón: cuatro hojas de bambú, dos por lado, hacia afuera y un poco atrás (de frente, un moño verde)
    bones = [f"Acc_LeafKnot_{i}" for i in range(2)]
    J = list(CR.LEAF_KNOT[:3])
    kl = kits["LeafKnot"] = Kit("part_LeafKnot", bones[0], weights=chain_weights(J, bones, before="Head", span=0.03))
    root = T0 + ax * 0.02
    for sx, dy, dz, ln, col in ((1, 0.25, 0.10, 0.12, C["leaf1"]), (1, 0.45, -0.25, 0.11, C["leaf2"]),
                                (-1, 0.25, 0.10, 0.12, C["leaf1b"]), (-1, 0.45, -0.25, 0.11, C["leaf1"])):
        d = Vector((sx, dy, dz)).normalized()
        b = root + Vector((0.030 * sx, 0.01, 0.0))
        kl.leaf(b, b + d * ln, Vector((0, 0, 1)), 0.032, col, ridge=0.3, under=C["leaf3"])


# =========================================================================== barba
def build_beard(kits):
    """Barba blanca larga en escudo: nace bajo la sonrisa y en la quijada, más ancha que la cara, se afina despacio hasta
    el cordón verde, el nudo trenzado en tres bultos y la punta. Cuelga de la quijada y de la cadena TasselBeard."""
    bones = [f"Acc_TasselBeard_{i}" for i in range(4)]
    J = [bh(b) for b in bones] + [bt(bones[-1])]
    wch = chain_weights(J, bones, before="Jaw", span=0.05)

    def w_beard(co):
        if co.z > 2.02:
            j = max(0.35, jaw_weight(co))
            return {"Jaw": j, "Head": 1.0 - j}
        if co.z > 1.97:
            a = smooth01((2.02 - co.z) / 0.05)
            return blend(({"Jaw": 1.0}, 1.0 - a), (wch(co), a))
        return wch(co)
    k = kits["Beard"] = Kit("part_Beard", "Jaw", weights=w_beard)
    # (z, centro y, medio ancho, frente, atrás): la de arriba abraza el mentón (la parte de atrás queda en la cara)
    rows = [(2.072, -0.054, 0.086, 0.040, 0.030), (2.044, -0.068, 0.092, 0.044, 0.032), (2.004, -0.088, 0.086, 0.042, 0.032),
            (1.952, -0.114, 0.074, 0.036, 0.030), (1.882, -0.150, 0.060, 0.032, 0.026), (1.810, -0.168, 0.048, 0.028, 0.024),
            (1.752, -0.176, 0.040, 0.025, 0.022), (1.712, -0.178, 0.033, 0.022, 0.020)]
    rings = []
    n = 10
    for z, yc, rx, rf, rb in rows:
        ring = []
        for i in range(n):
            a = 2 * math.pi * (i + 0.5) / n
            sx, cy = math.sin(a), -math.cos(a)
            e = 2.0 / 1.7
            x = rx * math.copysign(abs(sx) ** e, sx)
            ry = rf if cy < 0 else rb
            # el borde de arriba sube por la quijada hacia las patillas (los costados de la barba más altos)
            dz = (0.034 * abs(sx) ** 1.5 - 0.006) if z > 2.06 else 0.0
            ring.append(Vector((x, yc + ry * math.copysign(abs(cy) ** e, cy), z + dz)))
        rings.append(ring)
    part = k.rings_loft(rings, C["white"], False, False)
    for f in part.faces:
        c = f.calc_center_median()
        col = int((math.degrees(math.atan2(c.x, -(c.y + 0.11))) + 180.0) / 36.0)
        k.tag([f], C["white2"] if col % 2 else C["white"])
    # el cordón verde sobre el nudo y el nudo trenzado
    c0 = Vector((0.0, -0.179, 1.706))
    k.tube([c0 + Vector((0, 0, 0.012)), c0 - Vector((0, 0, 0.004))], [(0.042, 0.027), (0.040, 0.026)], 8, C["knot"],
           ups=[(0, -1, 0)] * 2, phase=math.pi / 8, cap0=False, cap1=False)
    for i, (dz, r) in enumerate(((-0.028, 0.042), (-0.062, 0.040), (-0.094, 0.034))):
        k.gem(c0 + Vector((0.0, 0.002 * (i % 2), dz)), r, C["white"] if i % 2 == 0 else C["white2"], sides=6, height=0.024,
              axis=(0.18 * (1 if i % 2 else -1), 0.0, 1.0))
    # la punta: tres púas que caen (la del medio más larga)
    tb = c0 + Vector((0.0, 0.0, -0.110))
    for t, r in (((0.0, -0.186, 1.515), 0.021), ((-0.020, -0.172, 1.545), 0.015), ((0.020, -0.172, 1.542), 0.015)):
        k.spike(tb, Vector(t), r, C["white"], sides=4, side_hint=(0, -1, 0), flat=0.7, phase=math.pi / 4)


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
    """Faja verde anudada: el nudo al frente con dos puntas como hojas y las dos colas paja (cadenas TieSash)."""
    kh = kits["Sash"] = Kit("part_Sash", "Spine", weights=torso_weights)
    z0, z1 = CR.SASH_Z
    zs = [z0, (z0 + z1) * 0.5, z1]
    rings = []
    for z in zs:
        y_f = -gi_y(0.0, z, True, 0.014)
        y_b = gi_y(0.0, z, False, 0.014)
        rings.append(ring(z, 0.196 + 0.014, y_f, y_b, n=14))
    part = kh.rings_loft(rings, C["sash"], False, False, [C["sash"], C["sash2"]])
    for f in part.faces:
        c = f.calc_center_median()
        if int((math.degrees(math.atan2(c.x, -c.y)) + 200.0) / 26.0) % 2 and c.z > (z0 + z1) * 0.5:
            kh.tag([f], C["sash3"])
    K = CR.SASH_KNOT
    kh.obox(K + Vector((0.0, -0.008, 0.0)), (0.080, 0.050, 0.075), (1, 0, 0.12), (0, 1, 0), C["sash"], bevel=0.014, up_color=C["sash3"])
    # las puntas del nudo, abiertas como hojas (el concepto)
    for s, dz, ln in ((1, 0.022, 0.12), (-1, 0.018, 0.11), (1, -0.02, 0.09)):
        d = Vector((s * 0.9, -0.28, dz * 9.0)).normalized()
        kh.leaf(K + Vector((0.02 * s, -0.03, 0.0)), K + Vector((0.02 * s, -0.03, 0.0)) + d * ln, Vector((0, -1, 0.2)), 0.05,
                C["sash3"] if s > 0 else C["sash"], ridge=0.25, under=C["sash2"])
    # colas paja: una cinta por los huesos de cada cadena
    for t, w0 in (("A", 0.056), ("B", 0.050)):
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
            if f.normal.dot(face) < 0.5:
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
    ip = k.rings_loft([list(reversed(r)) for r in inner], C["gi3"], False, False)
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
        for x in (xl, (xl + xr) * 0.5, xr):
            y = -ry * (1.0 - (abs(x) / 0.36) ** 2) ** 0.5
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
    S, E, W, u, l = arm_points()
    cuff = E + l * 0.17
    wa = chain_weights([S, E, cuff], ["UpperArm_R", "Forearm_R"], before="Clav_R", span=0.08)
    up = Vector((0.0, 0.0, 1.0))

    def w_sleeve(co):
        t = along_bone(co, S, E)
        if t < 0.0:
            a = 0.5 * smooth01(-t / 0.2)
            return {"UpperArm_R": 1.0 - a, "Clav_R": a}
        w = wa(co)
        # lo que cuelga debajo del brazo va con el vuelo (de a poco: el borde de abajo, entero)
        axis_pt = S + u * max(0.0, min(1.0, t)) * (E - S).length if t <= 1.0 else E + l * min(0.17, (co - E).dot(l))
        below = (axis_pt - co).dot(up)
        k = 0.85 * smooth01((below - 0.05) / 0.10)
        if k > 0.0:
            bn = "Sleeve_R_1" if t <= 0.9 else "Sleeve_R_2"
            w = {n: v * (1.0 - k) for n, v in w.items()}
            w[bn] = w.get(bn, 0.0) + k
        return w
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
    S, E, W, u, l = arm_points()
    wf = chain_weights([E, W, W + l * 0.05], ["Forearm_R", "Hand_R"], span=0.03)
    k = kits["Wrap_R"] = Kit("part_Wrap_R", "Forearm_R", weights=lambda co: {"Forearm_R": 1.0} if along_bone(co, E, W) < 0.9 else wf(co))
    pts = [E + l * 0.08, E + l * 0.17, E + l * 0.25, E + l * 0.31, W - l * 0.02, W + l * 0.012]
    k.tube(pts, [0.047, 0.046, 0.043, 0.040, 0.038, 0.040], 8, C["wrap"], ups=[(0, -1, 0)] * len(pts), phase=math.pi / 8, cap0=False,
           cap1=False, ring_colors=[C["wrap"], C["wrap2"], C["wrap"], C["wrap2"], C["wrap"]])
    build_hand_r(kits)


def build_hand_r(kits):
    """Mano grande y huesuda (la que agarra la caña): palma chata, nudillos marcados, dedos largos de dos falanges."""
    W, hd, dors, thumb = CR.hand_frame("R")
    Kn = CR.KNUCKLE

    def w_hand(co):
        t = along_bone(co, W, Kn)
        return {"Hand_R": 1.0} if t > 0.15 else {"Hand_R": 0.7, "Forearm_R": 0.3}
    k = kits["Hand_R"] = Kit("part_Hand_R", "Hand_R", weights=w_hand)
    k.tube([W - hd * 0.012, W + hd * 0.04, W + hd * 0.085, Kn + hd * 0.006],
           [(0.040, 0.022), (0.052, 0.024), (0.058, 0.023), (0.056, 0.020)], 6, C["skin"],
           ups=[dors] * 4, phase=math.pi / 6, power=3.0, ring_colors=[C["skin"], C["skin"], C["skin2"]])
    for name, off, l1, l2 in CR.FINGERS:
        b1, b2 = f"{name}_R_1", f"{name}_R_2"
        base, mid, tip = bh(b1), bh(b2), bt(b2)
        r0 = 0.0128 if name != "Pinky" else 0.0112

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
    kt.tube([tb - d1 * 0.014, tb + d1 * 0.018, tm, tm + d2 * 0.022, tt], [(0.016, 0.014), (0.015, 0.013), (0.013, 0.012),
            (0.012, 0.011), (0.006, 0.006)], 4, C["skin"], ups=[dors] * 5, phase=math.pi / 4, power=2.6)


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
    # polainas vendadas: de abajo del globo al tobillo, siete vueltas de venda inclinadas una para cada lado (de frente
    # se cruzan en V, como en la hoja) sobre un alma oscura
    zs = [0.445, 0.395, 0.345, 0.295, 0.245, 0.195, 0.150, 0.110]
    k.tube([leg_axis(zs[0] + 0.01), leg_axis(zs[-1])], [0.064, 0.058], 8, C["leg2"], phase=math.pi / 8, cap0=False, cap1=False)
    for i, (z0, z1) in enumerate(zip(zs[:-1], zs[1:])):
        tilt = math.tan(math.radians(10.0)) * (1 if i % 2 else -1)
        rings = []
        for z, r in ((z0 + 0.010, 0.072 - 0.0014 * i), (z1 - 0.008, 0.068 - 0.0014 * i)):
            c = leg_axis(z)
            rings.append([Vector((c.x + math.sin(a) * r, c.y - math.cos(a) * r, z + tilt * (-math.cos(a) * r)))
                          for a in (2 * math.pi * j / 8 + math.pi / 8 for j in range(8))])
        k.rings_loft(rings, C["leg"], False, False)
    build_foot_r(kits)


def build_foot_r(kits):
    """Sandalia-zapato: zapato negro facetado (material que brilla en las patadas), suela gruesa paja con canto, tira
    del tobillo, la de arriba del pie y la del dedo; la punta dobla en la bola del pie (Toe_R)."""
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
    hw = [(-heel, 0.056), (-0.04, 0.068), (0.06, 0.078), (ball_y, 0.084), (0.24, 0.074), (toe - 0.025, 0.05), (toe, 0.02)]
    poly = [(p.x, p.y) for p in [F(w, y, 0) for y, w in hw] + [F(-w, y, 0) for y, w in reversed(hw)]]
    area = sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(poly, poly[1:] + poly[:1]))
    k.extrude_polygon(poly if area > 0 else list(reversed(poly)), 0.0, 0.034, C["sole2"], top_color=C["sole"])
    # zapato
    rings = [(-heel + 0.012, 0.050, 0.075, 0.050), (-0.03, 0.062, 0.088, 0.064), (0.07, 0.072, 0.080, 0.050),
             (ball_y, 0.074, 0.068, 0.036), (0.25, 0.064, 0.056, 0.028), (toe - 0.02, 0.040, 0.050, 0.016)]
    pts = [F(0, y, z) for y, _, z, _ in rings]
    fwd = (pts[-1] - pts[0]).normalized()
    k.tube(pts, [(w, h) for _, w, _, h in rings], 8, "black", ups=[(0, 0, 1)] * len(rings), phase=math.pi / 8, power=2.4,
           slot=SLOT_FOOT_R)
    # tiras paja (la hoja de detalles): la vuelta ancha del tobillo, dos tiras cruzadas en X sobre el empeine que bajan
    # hasta la suela, el borde de la punta y el talón
    k.tube([F(0, 0.0, 0.092), F(0, 0.0, 0.150)], [(0.082, 0.080), (0.077, 0.075)], 8, C["strap"], phase=math.pi / 8, cap0=False,
           cap1=False, ring_colors=[C["strap"]])
    for sx in (-1.0, 1.0):
        pts = [F(0.078 * sx, 0.200, 0.040), F(0.052 * sx, 0.170, 0.094), F(0.0, 0.112, 0.130), F(-0.050 * sx, 0.060, 0.136),
               F(-0.080 * sx, 0.020, 0.070)]
        nr = [(p - F(0, y, z0)).normalized() for p, y, z0 in zip(pts, (0.2, 0.17, 0.112, 0.06, 0.02), (0.03, 0.06, 0.08, 0.08, 0.06))]
        k.strip(pts, [0.030] * 5, nr, C["strap"], thick=0.012)
    k.strip([F(0.058, toe - 0.040, 0.040), F(0.0, toe - 0.012, 0.068), F(-0.058, toe - 0.040, 0.040)], [0.026, 0.028, 0.026],
            [F(0.6, 1, 0.3) - F(0, 0, 0), F(0, 1, 0.4) - F(0, 0, 0), F(-0.6, 1, 0.3) - F(0, 0, 0)], C["strap"], thick=0.010)
    k.strip([F(0, -heel + 0.006, 0.034), F(0, -heel - 0.002, 0.095)], [0.046, 0.040], [(-fwd.x, -fwd.y, 0)] * 2, C["strap"],
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


def w_cloak(co):
    """Paños de la capa: mezcla por ángulo entre los dos paños vecinos y por la caída entre los dos tramos; el cuello
    va con el pecho (Spine2)."""
    phi, s = cloak_param(co)
    angs = CR.CLOAK_ANGLES
    if phi <= angs[0]:
        wa = {angs[0]: 1.0}
    elif phi >= angs[-1]:
        wa = {angs[-1]: 1.0}
    else:
        i = max(j for j in range(len(angs)) if angs[j] <= phi)
        i = min(i, len(angs) - 2)
        t = (phi - angs[i]) / (angs[i + 1] - angs[i])
        wa = {angs[i]: 1.0 - t, angs[i + 1]: t}
    t2 = smooth01((s - (CR.CLOAK_SPLIT - 0.10)) / 0.20)
    w = {}
    for a, v in wa.items():
        w[CR.cloak_name(a, 1)] = w.get(CR.cloak_name(a, 1), 0.0) + v * (1.0 - t2)
        w[CR.cloak_name(a, 2)] = w.get(CR.cloak_name(a, 2), 0.0) + v * t2
    c = 1.0 - smooth01((s - 0.03) / 0.13)
    if c > 0.0:
        w = {n: v * (1.0 - c) for n, v in w.items()}
        w["Spine2"] = c
    return w


def drop_len(phi):
    return sum((CR.cloak_rz(phi, (i + 1) / 24.0) - CR.cloak_rz(phi, i / 24.0)).length for i in range(24))


def build_cloak(kits):
    """La capa: una cáscara oscura de dos caras (lo que se ve entre las hojas y por dentro) y ~260 hojas de bambú en
    hileras como tejas (las de arriba encima de las de abajo), en tres tonos, más largas hacia el ruedo de la espalda; en
    los hombros se paran hacia afuera (la silueta en púas del concepto) y en el cuello hacen una gola."""
    rng = random.Random(61)
    k = kits["Cloak"] = Kit("part_Cloak", "Spine2", weights=w_cloak)
    k.use_anchors()
    a0, a1 = CR.CLOAK_OPEN, 360.0 - CR.CLOAK_OPEN
    cols, rows_n = 18, 6
    so, si = [], []
    for r in range(rows_n + 1):
        s = r / rows_n
        ro, ri = [], []
        for c in range(cols + 1):
            phi = a0 + (a1 - a0) * c / cols
            ro.append(k.bm.verts.new(CR.cloak_point(phi, s, 0.0)))
            ri.append(k.bm.verts.new(CR.cloak_point(phi, s, -0.012)))
        so.append(ro)
        si.append(ri)
    fo, fi = [], []
    for r in range(rows_n):
        for c in range(cols):
            fo.append(k.bm.faces.new((so[r][c], so[r][c + 1], so[r + 1][c + 1], so[r + 1][c])))
            fi.append(k.bm.faces.new((si[r][c + 1], si[r][c], si[r + 1][c], si[r + 1][c + 1])))
        fi.append(k.bm.faces.new((so[r][0], so[r + 1][0], si[r + 1][0], si[r][0])))
        fi.append(k.bm.faces.new((so[r][cols], si[r][cols], si[r + 1][cols], so[r + 1][cols])))
    for c in range(cols):
        fi.append(k.bm.faces.new((so[rows_n][c], so[rows_n][c + 1], si[rows_n][c + 1], si[rows_n][c])))
        fi.append(k.bm.faces.new((so[0][c + 1], so[0][c], si[0][c], si[0][c + 1])))
    k._new([v for r in so + si for v in r], C["shell"], None, None)
    k.tag(fi, C["gi3"])
    # hileras de hojas: (fracción de la caída, largo relativo, tono de arriba, tono de abajo)
    # seis hileras (tejas que se tapan un tercio: de cada hoja se ve la parte ancha, como en la hoja de la espalda)
    rows = [(0.03, 0.55, "leaf1", "leaf1c"), (0.10, 0.62, "leaf1", "leaf1c"), (0.26, 0.85, "leaf1", "leaf1b"),
            (0.43, 0.95, "leaf2", "leaf1"), (0.60, 1.0, "leaf2", "leaf1"), (0.76, 1.0, "leaf3", "leaf2"),
            (0.90, 1.0, "leaf3", "leaf2")]
    for ri_, (s, lr, ca, cb) in enumerate(rows):
        # largo de arco de la hilera para repartir las hojas cada ~5.6 cm
        phis = [a0 + (a1 - a0) * i / 120.0 for i in range(121)]
        arc = [0.0]
        for p0, p1 in zip(phis[:-1], phis[1:]):
            arc.append(arc[-1] + (CR.cloak_point(p1, s) - CR.cloak_point(p0, s)).length)
        spacing = (0.088 if s < 0.5 else 0.078) if ri_ > 0 else 0.06
        n = max(6, int(arc[-1] / spacing))
        for j in range(n):
            u = (j + 0.5 + rng.uniform(-0.3, 0.3)) / n
            d = u * arc[-1]
            idx = max(i for i in range(len(arc)) if arc[i] <= d)
            idx = min(idx, len(arc) - 2)
            phi = phis[idx] + (phis[idx + 1] - phis[idx]) * (d - arc[idx]) / max(1e-9, arc[idx + 1] - arc[idx])
            D = drop_len(phi)
            sb = s + rng.uniform(-0.015, 0.015)
            ln = (0.14 + 0.22 * min(1.0, D / 1.45)) * lr * rng.uniform(0.88, 1.12)
            out_b = 0.006 + 0.026 * (1.0 - sb)
            side = max(0.0, 1.0 - abs(abs(((phi + 180.0) % 360.0) - 180.0) - 90.0) / 38.0)
            # en los hombros las hojas de arriba se paran hacia afuera: la silueta en púas del concepto
            lift = 0.012 + 0.03 * rng.random() + (0.16 * side * (1.0 - min(1.0, sb / 0.45)) if ri_ > 0 else 0.0)
            col = C[ca] if (j + ri_) % 3 else C[cb]
            if ri_ == 0:
                # la gola: hojas paradas alrededor del cuello, apuntando arriba y afuera (no adelante)
                if 60.0 < phi < 300.0:
                    base = CR.cloak_point(phi, 0.02, 0.01)
                    outv = Vector((base.x, base.y - CR.CLOAK_Y0, 0.0)).normalized()
                    tip = base + (outv * 0.75 + Vector((0, 0, 0.75))).normalized() * ln
                    k.leaf(base, tip, outv - Vector((0, 0, 0.6)), 0.042, col, ridge=0.3, under=C["leaf3"])
                continue
            base = CR.cloak_point(phi, sb, out_b)
            ts = sb + ln / D
            yaw = rng.uniform(-9.0, 9.0) * (0.4 if D < 0.8 else 1.0)
            if ts <= 1.0:
                tip = CR.cloak_point(phi + yaw * ln / max(0.2, CR.cloak_rz(phi, sb).x), ts, out_b + lift)
            else:
                end = CR.cloak_point(phi, 1.0, out_b + lift)
                tan = (CR.cloak_point(phi, 1.0) - CR.cloak_point(phi, 0.96)).normalized()
                tip = end + tan * (ts - 1.0) * D
            nrm = CR.cloak_normal(phi, min(1.0, sb + 0.5 * ln / D))
            k.leaf(base, tip, nrm, max(0.05, ln * 0.31), col, ridge=0.22, under=C["leaf3"], wide=0.45)


def hole_mark(k, c, ax, side, nrm, h, w, color=None):
    """Un agujero de bambú: pirámide chata (base en la cara del caño, la punta 2 mm afuera), 6 triángulos oscuros."""
    vs = [k.bm.verts.new(c + ax * (h * 0.5 * a) + side * (w * 0.5 * b)) for a, b in ((-1, -1), (-1, 1), (1, 1), (1, -1))]
    tip = k.bm.verts.new(c + nrm * 0.0025)
    for i in range(4):
        k.bm.faces.new((vs[i], vs[(i + 1) % 4], tip))
    k.bm.faces.new(list(reversed(vs)))
    k._new(vs + [tip], color or C["hole"], None, None)


def build_chimes(kits):
    """22 cascabeles de bambú hueco: el cordón (paja) desde la capa y el tubo de 6 lados con el nudo, dos o tres agujeros
    oscuros y la boca hueca abajo. El tubo es del material que brilla de su grupo (Hi = hombros, agudos; Lo = espalda,
    graves); cada uno entero en su hueso (Acc_Chimes*_0: el juego lo mueve con SpringChain)."""
    for name, g, a, s, cord, ln, r in CR.chimes_full():
        bn = name + "_0"
        top, tail = bh(bn), bt(bn)
        ax = (tail - top).normalized()
        k = kits[name] = Kit("part_" + name, bn)
        slot = SLOT_CHIME_HI if g == "Hi" else SLOT_CHIME_LO
        nrm = CR.cloak_normal(a, s)
        nrm = (nrm - ax * nrm.dot(ax)).normalized()
        k.tube([top - ax * 0.008, top + ax * (cord + 0.006)], [0.0075, 0.0075], 3, C["cord"], phase=0.3, cap0=False, cap1=False)
        t0 = top + ax * cord
        # el tubo: el nudo arriba (bambú seco) y el caño del material que brilla, con una cara mirando afuera de la capa
        # (phase 0: el centro de una cara sobre 'nrm'); abajo, la boca hueca oscura
        pts = [t0, t0 + ax * 0.022, t0 + ax * 0.036, t0 + ax * ln]
        part = k.tube(pts, [r * 0.95, r * 1.12, r, r], 6, "white", ups=[nrm] * 4, phase=0.0, cap0=True, cap1=True, slot=slot,
                      ring_colors=[C["node"], C["node"], ("white", slot)])
        bot = [f for f in part.faces if len(f.verts) > 4 and (f.calc_center_median() - t0).dot(ax) > ln - 0.001]
        k.tag(bot, C["hole"])
        # dos agujeros: pirámides chatas oscuras sobre la cara que mira a la cámara (cerradas: el cálculo de normales
        # no las da vuelta)
        side = ax.cross(nrm).normalized()
        for z, h in ((ln * 0.42, 0.016), (ln * 0.68, 0.014)):
            c = t0 + ax * z + nrm * (r * math.cos(math.pi / 6) - 0.0005)
            hole_mark(k, c, ax, side, nrm, h, 0.012)


# =========================================================================== flauta-bastón (rígida)
def build_staff():
    """Flauta-bastón de 2.1 m: los tramos del material que brilla (se encienden enteros en el aviso), nudos de bambú
    seco con dos vueltas de cordón verde, los seis agujeros del tercio de arriba y el de soplar (caras oscuras), el
    vendado oscuro cerca de la punta de abajo y las dos bocas huecas. Se autora a lo largo de +Z desde la punta de
    abajo (el hueso Staff va de esa punta a la de arriba)."""
    k = Kit("Chikuo_Staff", "Staff")
    Ln, r = CR.STAFF_LEN, CR.STAFF_R
    nodes = [0.40, 0.70, 0.99, 1.27, 1.54, 1.80]
    holes = [1.36, 1.44, 1.60, 1.68, 1.88, 1.95]
    g0, g1 = CR.STAFF_GRIP
    sides = 7
    ph = math.pi / 2 - math.pi / sides          # una cara mira a -Y (adelante en el reposo): ahí van los agujeros
    up = [(0, -1, 0)] * 4
    stops = sorted({0.0, g0, (g0 + g1) * 0.5, g1, Ln} | {z + d for z in nodes for d in (-0.016, 0.016)})
    for z0, z1 in zip(stops[:-1], stops[1:]):
        mid = (z0 + z1) * 0.5
        if any(abs(mid - z) < 0.017 for z in nodes):
            continue
        grip = g0 <= mid <= g1
        rad = r * (1.12 if grip else 1.0)
        p = k.tube([(0, 0, z0), (0, 0, z1)], [rad, rad], sides, "white", ups=up[:2], phase=ph, cap0=False, cap1=False, slot=SLOT_STAFF)
        if grip:
            # el vendado: dos tramos oscuros con las vueltas cruzadas en facetas (tinta y hierro)
            for i, f in enumerate(p.faces):
                k.tag([f], C["staff_grip2"] if (i + int(mid * 10)) % 3 == 0 else C["staff_grip"])
    for z in nodes:
        k.tube([(0, 0, z - 0.016), (0, 0, z), (0, 0, z + 0.016)], [r * 1.0, r * 1.17, r * 1.0], sides, C["staff_cord"], ups=up[:3],
               phase=ph, cap0=False, cap1=False, ring_colors=[C["staff_cord"], C["staff_node"]])
    # los seis agujeros del tercio de arriba y el de soplar, en la cara de adelante
    fc = r * math.cos(math.pi / sides) - 0.0005
    for z in holes + [Ln - CR.STAFF_FLUTE]:
        hole_mark(k, Vector((0, -fc, z)), Vector((0, 0, 1)), Vector((1, 0, 0)), Vector((0, -1, 0)), 0.017, 0.016,
                  C["staff_hole"])
    # las bocas huecas: el canto de bambú seco y el interior oscuro, fundidos con el último anillo del caño
    for z, s in ((0.0, -1.0), (Ln, 1.0)):
        k.tube([(0, 0, z), (0, 0, z - s * 0.002), (0, 0, z - s * 0.03)], [r, r * 0.70, r * 0.45], sides, C["staff_hole"],
               ups=up[:3], phase=ph, cap0=False, cap1=True, ring_colors=[C["staff_node"], C["staff_hole"]])
    return k


# =========================================================================== armado
def finish_kit(kit):
    # la piel se autora con 'lantern_paper' (que ninguna otra pieza usa) y acá pasa a Chikuo_Skin
    uv = L.P.uv_of(C["skin"])
    lay = kit.uv
    for f in kit.bm.faces:
        if f.material_index == L.SLOT_PALETTE and f.loops and (f.loops[0][lay].uv - Vector(uv)).length < 1e-4:
            f.material_index = SLOT_SKIN
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
