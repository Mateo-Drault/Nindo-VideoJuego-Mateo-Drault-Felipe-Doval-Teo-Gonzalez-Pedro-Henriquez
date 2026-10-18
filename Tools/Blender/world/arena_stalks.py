"""Las cañas del claro de Chikuō (la arena del bambú, fase C4; contrato en Docs/handoff/diseno/chikuo_v2.md, sección 8).

blender -b --factory-startup --python Tools/Blender/world/arena_stalks.py -- [--export] [--check] [--preview DIR]

Cada caña es una jerarquía (no un prop de una malla): el código la dobla girando sus tramos (World/ArenaStalk.cs):
  arena_stalk_<tipo>.fbx
    Base            el montículo de tierra al pie (quieto)
    Stump           el tocón de 1 m con el corte en diagonal (apagado: lo prende ArenaStalk.SetBroken)
    Stalk           raíz vacía, pivote en la base, sin animar
      Seg_00        primer tramo (con el ensanche del pie); cada Seg_k es hijo del anterior, pivote abajo, en un nudo
        Crack       rajadura del tramo de abajo (apagada; fase 3)
        Seg_01      lleva el nudo de la base: GlintBase (material Stalk_GlintBase, el que el código hace brillar)
          BaseCut   el punto del corte (0.9 m)
          CrackUp   la rajadura sigue en este tramo
          Seg_02    ClimbGrip (2.2 m, donde agarra al trepar)
            ...
              Seg_05  el nudo del posado (grueso, con el cordón y los cascabeles): PerchNode encima, GripHigh 0.9 m arriba,
                      ChimeL / ChimeR (pivotes de los cascabeles; la Madre tiene cinco: ChimeL, ChimeR, Chime3..5)
                Seg_06
                  Seg_07  Crown (la copa, desde esta junta: por encima de la cabeza de Chikuō) y Tip (la punta)
Los nudos están en las juntas: el anillo del nudo (del tramo de arriba) tapa la junta cuando el tramo gira.

Las cañas se instancian todas con yaw 0 (los ejes del archivo = los del mundo, la cámara de la zona mira al norte): así
las caras claras quedan del lado de la luna, los cascabeles a los costados en pantalla y la rajadura de cara a la cámara.
ArenaStalk gira solo las anclas para que +Z mire al centro del claro.

Ejes: Blender Z = Unity Y (a lo largo del culmo); Blender -Y = Unity +Z; Blender +X = Unity -X.
"""
import sys, os, math, json, random

HERE = os.path.dirname(os.path.abspath(__file__))
BL = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(BL))
sys.path[:0] = [HERE, BL, os.path.join(BL, "props")]

import bpy, bmesh
from mathutils import Vector, Matrix, Quaternion
import nindo_lib as L
import nindo_palette as PAL
import props_nature as PN

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT_DIR = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Art", "Models", "Props")
MANIFEST = os.path.join(BL, "out", "manifest_world_arena_stalks.json")   # después de los props_*: PropsManifest las suma al final
GLINT_MAT = "Stalk_GlintBase"
SIDES = 8
FOL = L.SLOT_FOLIAGE
CUT_H = 0.9                  # el nudo de la base (el corte de Kaito a la altura de la cadera, como BaseCut)
OVERLAP = 0.02               # cada culmo entra este tanto en el anillo del tramo de arriba

# Juntas (altura de la base de cada Seg_k) por tipo. El nudo del posado es la junta 5 y PerchNode queda arriba de su
# anillo, a la altura del contrato; ClimbGrip y GripHigh caen a mitad de un entrenudo (la mano no agarra el anillo).
# r0 / r1: radio del culmo en la base y en la punta. El diseño pedía Ø 0.26 -> 0.12; con eso, desde la cámara del juego
# (24 m) eran postes del mismo grosor que el bambú del bosque de atrás: van un 15 % más gruesas (Ø 0.30 en la base, 0.21
# en el posado), que es lo que las marca como "las suyas" junto con el color más claro y los nudos de paja.
KINDS = {
    "inner": dict(length=7.5, perch=4.4, grip=5.3, climb=2.2, r0=0.15, r1=0.07, perch_r=0.17, chimes=2, cord="rope",
                  joints=[0.0, CUT_H, 1.75, 2.62, 3.47, 4.32, 5.62, 6.55], extra_nodes=[]),
    "north": dict(length=7.5, perch=4.0, grip=4.9, climb=2.2, r0=0.15, r1=0.07, perch_r=0.17, chimes=2, cord="rope",
                  joints=[0.0, CUT_H, 1.68, 2.46, 3.19, 3.92, 5.20, 6.35], extra_nodes=[]),
    "outer": dict(length=8.5, perch=4.8, grip=5.7, climb=2.2, r0=0.15, r1=0.07, perch_r=0.17, chimes=2, cord="rope",
                  joints=[0.0, CUT_H, 1.82, 2.78, 3.75, 4.72, 6.10, 7.30], extra_nodes=[]),
    # la Caña Madre: Ø 0.42, diez nudos (las juntas más tres de adorno), cordón rojo y cinco cascabeles; no se quiebra
    "mother": dict(length=10.0, perch=5.0, grip=5.9, climb=2.2, r0=0.21, r1=0.10, perch_r=0.26, chimes=5, cord="cloth_red",
                   joints=[0.0, CUT_H, 1.95, 2.95, 3.94, 4.92, 6.55, 8.15], extra_nodes=[7.35, 8.95, 9.45]),
}
PERCH_J = 5
PERCH_HALF = 0.08            # medio alto del anillo del posado: PerchNode = junta 5 + esto
NODE_LO, NODE_HI = 0.05, 0.05
GLINT_LO, GLINT_HI = 0.07, 0.07


def radius_at(k, h):
    """Radio del culmo a la altura h (afinado lineal de r0 a r1)."""
    c = KINDS[k]
    return c["r0"] + (c["r1"] - c["r0"]) * max(0.0, min(1.0, h / c["length"]))


def seg_range(k, i):
    j = KINDS[k]["joints"]
    return j[i], (j[i + 1] if i + 1 < len(j) else KINDS[k]["length"])


def seg_of(k, h):
    j = KINDS[k]["joints"]
    i = max(n for n in range(len(j)) if j[n] <= h + 1e-6)
    return i


# =========================================================================== geometría
PHASE = math.pi / SIDES      # una arista de frente a la cámara: el culmo se lee con dos caras, clara y en sombra


def ring(z, r, sides=SIDES, phase=PHASE, cx=0.0, cy=0.0):
    return [Vector((cx + r * math.cos(phase + 2 * math.pi * i / sides), cy + r * math.sin(phase + 2 * math.pi * i / sides), z))
            for i in range(sides)]


def lit(n, t=-0.12):
    """La cara mira a la luna (que llega del sureste y de arriba, como en el resto de los props: props_nature.culm)."""
    return (-n.x * 0.6 + n.y * 0.5 + n.z) > t


def culm(mb, k, h0, h1, z0, z1, slot=None):
    """Culmo entre las alturas h0 y h1 del mundo de la caña, en coordenadas locales z0..z1. Seis de sus ocho caras en
    bamboo_light y las dos de atrás en bamboo: más claro que el bosque (bamboo con alguna cara clara), como pide el diseño."""
    p = mb.loft([ring(z0, radius_at(k, h0)), ring(z1, radius_at(k, h1))], "bamboo", slot=slot)
    p.color_faces(lambda f: "bamboo_light" if lit(PN.nrm(f), -0.45) else None)
    return p


def node_ring(mb, rb, rn, ra, lo, hi, slot=None, dark="bamboo_dark", band="bamboo_dry", top="straw"):
    """Anillo de nudo centrado en z = 0 del tramo: labio de abajo oscuro (la sombra que lo dibuja), banda paja y la cara
    de arriba más clara (la que ve la cámara alta)."""
    rings = [ring(-lo, rb), ring(-lo * 0.35, rn), ring(hi * 0.35, rn), ring(hi, ra)]
    p = mb.loft(rings, band, slot=slot)

    def fn(f):
        n = PN.nrm(f)
        if n.z < -0.25:
            return dark
        if n.z > 0.25:
            return top
        return band
    p.color_faces(fn)
    return p


def cord_band(mb, r, z, h, color, slot=None):
    p = mb.loft([ring(z - h * 0.5, r), ring(z + h * 0.5, r)], color, slot=slot)
    return p


def leaf_spray(mb, rng, base, ang, n, length, spread=0.55, width=0.16, droop=(0.25, 0.45),
               colors=("leaf", "leaf_light", "bamboo_light")):
    leaves = []
    for i in range(n):
        a = ang + (i - (n - 1) / 2) * spread * rng.uniform(0.8, 1.15)
        Ln = length * rng.uniform(0.82, 1.1)
        c = colors[0] if rng.random() < 0.5 else (colors[1] if rng.random() < 0.6 else colors[2])
        lf = PN.leaf_tent(mb, base, PN.dirvec(a), Ln, width * rng.uniform(0.9, 1.15), Ln * rng.uniform(*droop), c, rng)
        wind_by_reach(lf, Vector(base), Ln)
        leaves.append(lf)
    return leaves


def wind_by_reach(part, origin, reach, w0=0.15, w1=1.0):
    """Peso del viento por la distancia al punto donde nace la hoja (la base fija, la punta se mueve entera)."""
    cl = part.mb.col
    for f in part.faces:
        for l in f.loops:
            t = max(0.0, min(1.0, (l.vert.co - origin).length / max(reach, 1e-3)))
            c = l[cl]
            l[cl] = (w0 + (w1 - w0) * t, c[1], c[2], 1.0)


def branch(mb, rng, k, z_local, h_world, ang, length=0.7, rise=45.0, fans=((0.5, 3, 0.8), (1.0, 4, 1.0)), leaf_len=0.9):
    """Rama que sale del nudo hacia afuera y arriba, con abanicos de hojas colgando a lo largo (en la mitad y en la
    punta): las hojas cuelgan en racimos lejos del culmo y la copa no se lee como una palmera desde arriba."""
    r = radius_at(k, h_world)
    d = PN.dirvec(ang)
    p0 = Vector((d.x * r * 0.8, d.y * r * 0.8, z_local + 0.03))
    p1 = p0 + d * length * math.cos(math.radians(rise)) + Vector((0, 0, length * math.sin(math.radians(rise))))
    tw = PN.tube(mb, [p0, p1], [0.03, 0.018], 4, "bamboo", rng, phase=0.3)
    tw.color_faces(lambda f: "bamboo_light" if lit(PN.nrm(f)) else "bamboo_dark")
    leaves = []
    for t, n, sc in fans:
        # el abanico del medio se abre a los costados de la rama, el de la punta sigue su dirección
        off = rng.choice((-1, 1)) * rng.uniform(0.5, 0.9) if t < 0.99 else rng.uniform(-0.25, 0.25)
        leaves += leaf_spray(mb, rng, p0.lerp(p1, t), ang + off, n, leaf_len * sc, spread=0.62, droop=(0.45, 0.85))
    return leaves


def mound(mb, rng, r0):
    """Tierra removida al pie (quieta): baja y chica, para no tapar el ensō de 1.2 m de la base."""
    n = 7
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n + rng.uniform(-0.2, 0.2)
        rr = (r0 + 0.17) * rng.uniform(0.9, 1.12)
        pts.append(Vector((math.cos(a) * rr, math.sin(a) * rr, -0.02)))
    mid = [Vector((p.x * 0.62, p.y * 0.62, 0.05 + rng.uniform(0, 0.02))) for p in pts]
    rings = [pts, mid, ring(0.07, r0 * 1.02, n, 0.2)]
    p = mb.loft(rings, "dirt_dark")
    p.color_faces(lambda f: "moss" if PN.nrm(f).z > 0.8 else ("dirt" if lit(PN.nrm(f)) else "dirt_dark"))
    return p


# =========================================================================== objetos
def new_empty(name, parent, loc):
    e = bpy.data.objects.new(name, None)
    e.empty_display_size = 0.15
    e.empty_display_type = 'ARROWS'
    bpy.context.scene.collection.objects.link(e)
    e.parent = parent
    e.location = loc
    return e


def finish(mb, name, parent, loc, extra_mats=()):
    o = mb.finish()
    o.name = name
    o.data.name = name
    for m in extra_mats:
        o.data.materials.append(m)
    o.parent = parent
    o.location = loc
    return o


def glint_material():
    m = bpy.data.materials.get(GLINT_MAT)
    if m:
        return m
    m = bpy.data.materials.new(GLINT_MAT)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = L.palette_image()
    tex.interpolation = 'Closest'
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    b.inputs["Emission Color"].default_value = (1, 1, 1, 1)
    b.inputs["Emission Strength"].default_value = 0.0
    return m


def build(k, seed=7):
    """Arma la caña 'k' en la escena (en el origen). Devuelve {nombre: objeto}."""
    c = KINDS[k]
    rng = random.Random(seed + len(k) * 31)
    objs = {}
    J = c["joints"]
    Ln = c["length"]

    # ---- raíces
    stalk = new_empty("Stalk", None, (0, 0, 0))
    objs["Stalk"] = stalk
    mb = L.MeshBuilder("Base", seed)
    mound(mb, rng, c["r0"])
    mb.collider_none()
    objs["Base"] = finish(mb, "Base", None, (0, 0, 0))
    if k != "mother":
        objs["Stump"] = build_stump(k, seed)

    parent = stalk
    for i in range(len(J)):
        h0, h1 = seg_range(k, i)
        mb = L.MeshBuilder(f"Seg_{i:02d}", seed + i)
        top = h1 - h0 + (OVERLAP if i + 1 < len(J) else 0.0)
        if i == 0:
            # ensanche del pie: entra en la tierra (el tramo gira con el arco y no deja ver dónde termina)
            flare = mb.loft([ring(-0.08, c["r0"] * 1.32), ring(0.0, c["r0"] * 1.3), ring(0.16, c["r0"] * 1.04)], "bamboo")
            flare.color_faces(lambda f: "bamboo_light" if lit(PN.nrm(f)) else "bamboo_dark")
            culm(mb, k, 0.16, h1 + OVERLAP, 0.16, top)
        elif i + 1 < len(J):
            culm(mb, k, h0, h1 + OVERLAP, 0.0, top)
        else:
            # último tramo: afina hasta la punta (un poco antes, para no dejar una aguja de 1 cm)
            p = mb.loft([ring(0.0, radius_at(k, h0)), ring(top - 0.35, radius_at(k, h1 - 0.35)),
                         ring(top, 0.012)], "bamboo")
            p.color_faces(lambda f: "bamboo_light" if lit(PN.nrm(f)) else None)
        # anillo del nudo de esta junta (el de la base va aparte, en su material de brillo; el del posado es el grueso)
        if i >= 2 and i != PERCH_J:
            rb, ra = radius_at(k, h0 - NODE_LO), radius_at(k, h0 + NODE_HI)
            node_ring(mb, rb, max(rb, ra) * 1.14, ra, NODE_LO, NODE_HI)
        if i == PERCH_J:
            build_perch(mb, k, rng)
        for hz in c["extra_nodes"]:
            if h0 + 0.2 < hz < h1 - 0.2:
                rr = radius_at(k, hz)
                node_ring(mb, rr, rr * 1.1, rr, 0.03, 0.03).transform(loc=(0, 0, hz - h0))
        mb.collider_none()
        seg = finish(mb, f"Seg_{i:02d}", parent, (0, 0, h0 - (J[i - 1] if i else 0.0)))
        objs[f"Seg_{i:02d}"] = seg
        parent = seg

    seg = lambda h: objs[f"Seg_{seg_of(k, h):02d}"]
    base_of = lambda h: J[seg_of(k, h)]
    # ---- el nudo de la base (Stalk_GlintBase): un objeto propio para que el brillo no saque al culmo del batching
    s1 = objs["Seg_01"]
    mb = L.MeshBuilder("GlintBase", seed + 50)
    rb, ra = radius_at(k, CUT_H - GLINT_LO), radius_at(k, CUT_H + GLINT_HI)
    gr = node_ring(mb, rb, rb * 1.3, ra, GLINT_LO, GLINT_HI, slot=4)
    mb.collider_none()
    g = mb.finish()
    g.name = g.data.name = "GlintBase"
    g.data.materials.clear()
    g.data.materials.append(glint_material())
    for p in g.data.polygons:
        p.material_index = 0
    g.parent = s1
    g.location = (0, 0, 0)
    objs["GlintBase"] = g
    # ---- anclas
    objs["BaseCut"] = new_empty("BaseCut", s1, (0, 0, 0))
    objs["ClimbGrip"] = new_empty("ClimbGrip", seg(c["climb"]), (0, 0, c["climb"] - base_of(c["climb"])))
    sp = objs[f"Seg_{PERCH_J:02d}"]
    objs["PerchNode"] = new_empty("PerchNode", sp, (0, 0, PERCH_HALF))
    objs["GripHigh"] = new_empty("GripHigh", seg(c["grip"]), (0, 0, c["grip"] - base_of(c["grip"])))
    top_seg = objs[f"Seg_{len(J) - 1:02d}"]
    objs["Tip"] = new_empty("Tip", top_seg, (0, 0, Ln - J[-1]))
    build_chimes(k, sp, objs, rng)
    objs["Crown"] = build_crown(k, top_seg, rng, seed)
    if k != "mother":
        objs["Crack"] = build_crack(k, objs["Seg_00"], 0, rng, "Crack")
        objs["CrackUp"] = build_crack(k, s1, 1, rng, "CrackUp")
    # sin esto el exportador lee matrix_world viejas (identidad) en los objetos recién creados y escribe la jerarquía mal
    # (cada tramo corrido y girado 90° en profundidades alternas: lo encontró fbx_check)
    bpy.context.view_layer.update()
    return objs


def build_perch(mb, k, rng):
    """El nudo del posado: grueso, con un cordón atado (y el nudo del cordón mirando al sur: se ve desde la cámara)."""
    c = KINDS[k]
    h = c["joints"][PERCH_J]
    rb, ra = radius_at(k, h - 0.11), radius_at(k, h + 0.10)
    pr = c["perch_r"]
    rings = [ring(-0.11, rb), ring(-0.06, pr * 0.92), ring(-0.025, pr), ring(0.03, pr), ring(0.065, pr * 0.9), ring(0.10, ra)]
    p = mb.loft(rings, "bamboo_dry")

    def fn(f):
        n = PN.nrm(f)
        if n.z < -0.3:
            return "bamboo_dark"
        if n.z > 0.3:
            return "straw"
        return "bamboo_dry" if lit(n) else "wheat_dark"
    p.color_faces(fn)
    cord = c["cord"]
    dark = "cloth_red" if cord == "cloth_red" else "rope"
    cord_band(mb, pr * 1.04, -0.045, 0.035, dark)
    cord_band(mb, pr * 1.04, 0.012, 0.035, cord)
    # nudo y dos puntas colgando (al sur: Blender +Y)
    kn = mb.box((0, pr * 1.06, -0.02), (0.075, 0.06, 0.07), cord)
    for sx, ln in ((-0.025, 0.2), (0.03, 0.15)):
        mb.box((sx, pr * 1.08, -0.02 - ln * 0.5 - 0.03), (0.04, 0.025, ln), cord, rot=(0, 0, rng.uniform(-8, 8)))


def build_chimes(k, seg_obj, objs, rng):
    """Cascabeles de paja (tubos huecos de seis caras, abiertos: las tapas oscuras son el agujero) colgando del nudo del
    posado. El pivote (Chime*) está arriba del cordón: ArenaStalk lo hace péndulo."""
    c = KINDS[k]
    n = c["chimes"]
    pr = c["perch_r"]
    if n == 2:
        spots = [("ChimeL", math.pi), ("ChimeR", 0.0)]        # Unity -X / +X (Blender +X / -X): a los costados en pantalla
    else:
        spots = [("ChimeL", math.pi), ("ChimeR", 0.0)] + [(f"Chime{i + 3}", math.pi * 0.5 + (i - 1) * 0.75) for i in range(n - 2)]
    for name, a in spots:
        x, y = -math.cos(a) * (pr + 0.01), math.sin(a) * (pr + 0.01)
        piv = new_empty(name, seg_obj, (x, y, -0.06))
        objs[name] = piv
        mb = L.MeshBuilder(name + "_Mesh", 99 + len(objs))
        ln = rng.uniform(0.26, 0.32) * (1.15 if k == "mother" else 1.0)
        top, bot = -0.075, -0.075 - ln
        mb.box((0, 0, -0.04), (0.035, 0.035, 0.085), "rope")
        r = 0.04
        rings = [ring(top, r, 6, 0.0), ring(bot, r, 6, 0.0)]
        t = mb.loft(rings, "straw", cap_start=True, cap_end=True)
        t.color_faces(lambda f: "gold_dark" if abs(PN.nrm(f).z) > 0.9 else ("straw" if lit(PN.nrm(f)) else "wheat"))
        # dos agujeros (una cara oscura chica en el medio de dos lados)
        for ha in (0.0, math.pi):
            hx, hy = math.cos(ha + 0.52) * (r * 0.92 + 0.004), math.sin(ha + 0.52) * (r * 0.92 + 0.004)
            mb.box((hx, hy, (top + bot) * 0.5), (0.022, 0.022, 0.05), "gold_dark", rot=(0, 0, math.degrees(ha + 0.52)))
        mb.collider_none()
        objs[name + "_Mesh"] = finish(mb, name + "_Mesh", piv, (0, 0, 0))


def build_crown(k, top_seg, rng, seed):
    """La copa, en tres pisos (el último nudo, la mitad del último tramo y la punta) para que se lea como un penacho de
    bambú y no como una palmera vista de arriba (con un solo abanico en la punta, eso era). Todo en el material con viento.
    Arranca en la última junta, 0.65-1.3 m por encima de la cabeza de Chikuō agachado en el posado: con las hojas a la
    altura de su cabeza (la copa desde 0.75 del alto que pedía el diseño) su capa verde oscura quedaba contra hojas verdes
    desde la cámara de pelea; así, detrás de su cuerpo queda el piso claro del claro."""
    c = KINDS[k]
    J = c["joints"]
    Ln = c["length"]
    mb = L.MeshBuilder("Crown", seed + 77)
    big = k == "mother"
    top = Ln - J[-1]
    a0 = rng.uniform(0, 6.28)
    for n in range(5 + big):
        branch(mb, rng, k, 0.0, J[-1], a0 + n * 6.28 / (5 + big) + rng.uniform(-0.3, 0.3), length=0.75 if not big else 0.95,
               rise=45.0, leaf_len=1.0 if not big else 1.2)
    zm = top * 0.5
    for n in range(3 + big):
        branch(mb, rng, k, zm, J[-1] + zm, a0 + 0.8 + n * 6.28 / (3 + big) + rng.uniform(-0.3, 0.3), length=0.5,
               rise=55.0, fans=((1.0, 4, 1.0),), leaf_len=0.85 if not big else 1.0)
    # la punta: hojas cortas que suben y se abren poco (un penacho)
    tip = Vector((0, 0, top - 0.18))
    for n in range(5):
        a = a0 + n * 1.26 + rng.uniform(-0.2, 0.2)
        Lf = rng.uniform(0.55, 0.75) * (1.2 if big else 1.0)
        lf = PN.leaf_tent(mb, tip, PN.dirvec(a), Lf, 0.15, -Lf * rng.uniform(0.15, 0.55), "leaf_light" if n % 2 else "leaf", rng)
        wind_by_reach(lf, tip, Lf)
    mb.collider_none()
    return finish(mb, "Crown", top_seg, (0, 0, 0))


def build_crack(k, seg_obj, i, rng, name):
    """La rajadura de la fase 3: el culmo amarillea (una funda apenas más gruesa) y una grieta en zigzag, paja clara
    con el fondo oscuro, del lado de la cámara y del de atrás (las cañas van con yaw 0: la cámara siempre las ve del sur)."""
    h0, h1 = seg_range(k, i)
    z0 = 0.25 if i == 0 else 0.09
    z1 = (h1 - h0) - (0.05 if i == 0 else 0.05)
    mb = L.MeshBuilder(name, 300 + i)
    off = 0.007
    p = mb.loft([ring(z0, radius_at(k, h0 + z0) + off), ring(z1, radius_at(k, h0 + z1) + off)], "bamboo_dry")
    p.color_faces(lambda f: "bamboo_dry" if lit(PN.nrm(f)) else "wheat_dark")
    for side in (math.pi * 0.5, math.pi * 1.5):        # el lado que da a la cámara (sur, Blender +Y) y el de atrás
        pts = []
        steps = 5
        for s in range(steps + 1):
            t = s / steps
            z = z0 + (z1 - z0) * t
            a = side + 0.9 * (t - 0.5) + (0.18 if s % 2 else -0.18)
            pts.append((z, a))
        for (za, aa), (zb, ab) in zip(pts, pts[1:]):
            ra, rb = radius_at(k, h0 + za) + off * 2.2, radius_at(k, h0 + zb) + off * 2.2
            pa = Vector((math.cos(aa) * ra, math.sin(aa) * ra, za))
            pb = Vector((math.cos(ab) * rb, math.sin(ab) * rb, zb))
            for w, col in ((0.06, "straw"), (0.024, "wood_dark")):
                na = Vector((-math.sin(aa), math.cos(aa), 0)) * w
                nb = Vector((-math.sin(ab), math.cos(ab), 0)) * w
                lift = 0.004 if col == "wood_dark" else 0.0
                oa, ob = Vector((math.cos(aa), math.sin(aa), 0)) * lift, Vector((math.cos(ab), math.sin(ab), 0)) * lift
                mb.face([pa - na + oa, pb - nb + ob, pb + nb + ob, pa + na + oa], col)
    mb.collider_none()
    o = mb.finish()
    o.name = o.data.name = name
    # caras sueltas: la normal hacia afuera del culmo (recalc_face_normals elige un lado cualquiera en una cara aislada)
    for poly in o.data.polygons:
        cx, cy = poly.center.x, poly.center.y
        if poly.normal.x * cx + poly.normal.y * cy < 0:
            poly.flip()
    o.parent = seg_obj
    o.location = (0, 0, 0)
    return o


def build_stump(k, seed):
    """El tocón (queda cuando la caña se quiebra): 1 m, corte en diagonal de cara clara con astillas."""
    c = KINDS[k]
    rng = random.Random(seed + 5)
    mb = L.MeshBuilder("Stump", seed + 9)
    r0 = c["r0"]
    flare = mb.loft([ring(-0.08, r0 * 1.32), ring(0.0, r0 * 1.3), ring(0.16, r0 * 1.04)], "bamboo")
    flare.color_faces(lambda f: "bamboo_light" if lit(PN.nrm(f)) else "bamboo_dark")
    lo, hi = 0.78, 1.06
    bot = ring(0.16, radius_at(k, 0.16))
    topr = []
    for v in ring(0.0, radius_at(k, 1.0)):
        t = (v.x / radius_at(k, 1.0) + 1) * 0.5        # el corte baja hacia +X de Blender
        topr.append(Vector((v.x, v.y, hi + (lo - hi) * t)))
    p = mb.loft([bot, topr], "bamboo")
    p.color_faces(lambda f: "bamboo_light" if lit(PN.nrm(f)) else None)
    # la cara del corte (paja clara) con el hueco del culmo (oscuro) en el medio
    ctr = sum(topr, Vector()) / len(topr)
    inner = [ctr + (v - ctr) * 0.62 for v in topr]
    for a, b, ia, ib in zip(topr, topr[1:] + topr[:1], inner, inner[1:] + inner[:1]):
        mb.face([a, b, ib, ia], "straw")
    for a, b in zip(inner, inner[1:] + inner[:1]):
        mb.face([a, b, ctr - Vector((0, 0, 0.05))], "wood_dark")
    # astillas del lado alto
    for s in range(3):
        a = math.pi + (s - 1) * 0.5
        base = Vector((math.cos(a) * radius_at(k, 1.0) * 0.85, math.sin(a) * radius_at(k, 1.0) * 0.85, hi - 0.02))
        mb.cone(tuple(base), 0.03, rng.uniform(0.12, 0.2), 4, "bamboo_dry", rot=(rng.uniform(-12, 12), rng.uniform(-12, 12), 0))
    mb.collider_none()
    o = mb.finish()
    o.name = o.data.name = "Stump"
    for poly in o.data.polygons:
        # las caras del corte miran hacia arriba
        if abs(poly.center.x) + abs(poly.center.y) < 0.2 and poly.center.z > 0.7 and poly.normal.z < 0:
            poly.flip()
    return o


# =========================================================================== arco (lo mismo que ArenaStalk.SetBend)
def weights(n, evenness=0.0):
    """w_k ∝ (k + 1), normalizado (dobla más arriba: una caña de pescar); evenness 1 = parejo (la inclinación de la fase 2)."""
    a = [(i + 1) for i in range(n)]
    s = float(sum(a))
    return [(1 - evenness) * x / s + evenness / n for x in a]


def apply_bend(objs, k, deg, dir_xy=(0.0, 1.0), evenness=0.0):
    """Gira cada Seg_k deg * w_k alrededor del eje horizontal perpendicular a dir (en el espacio de la caña)."""
    n = len(KINDS[k]["joints"])
    d = Vector((dir_xy[0], dir_xy[1], 0)).normalized()
    axis = Vector((0, 0, 1)).cross(d).normalized()
    for i, w in enumerate(weights(n, evenness)):
        o = objs[f"Seg_{i:02d}"]
        o.rotation_mode = 'QUATERNION'
        o.rotation_quaternion = Quaternion(axis, math.radians(deg * w))
    bpy.context.view_layer.update()


def joint_gaps(k, deg, evenness=0.0):
    """Lo que se abre en cada junta (m) cuando el tramo de arriba gira: el borde del culmo de abajo sale del anillo del
    tramo de arriba si r * sin(alfa) supera lo que el anillo baja de la junta."""
    n = len(KINDS[k]["joints"])
    out = []
    for i, w in enumerate(weights(n, evenness)):
        if i == 0:
            continue
        a = math.radians(abs(deg * w))
        h = KINDS[k]["joints"][i]
        lo = PERCH_HALF + 0.03 if i == PERCH_J else (GLINT_LO if i == 1 else NODE_LO)
        out.append((i, radius_at(k, h) * math.sin(a) - lo * 0.9))
    return out


# =========================================================================== exportación
def export_kind(k):
    L.clear_scene()
    objs = build(k)
    path = os.path.join(OUT_DIR, f"arena_stalk_{k}.fbx")
    sel = [o for o in objs.values()]
    # en una escena limpia: un nombre con sufijo (Seg_01.001) rompería las anclas que busca ArenaStalk
    wrong = [f"{key} -> {o.name}" for key, o in objs.items() if o.name != key]
    assert not wrong, wrong
    export_hierarchy(sel, path)
    tris = sum(len(o.data.polygons) for o in sel if o.type == 'MESH' and o.name != "Stump")
    c = KINDS[k]
    entry = {"module": "arena_stalks", "tris": tris, "size": [round(c["perch_r"] * 2, 3), c["length"], round(c["perch_r"] * 2, 3)],
             # sin collider en el manifest: la cápsula del pie la pone ArenaStalk en la capa Ignore Raycast (con la del
             # manifest, en Default, los rayos al piso del ensō y del apoyo del jefe se paraban arriba de ella, a 1.4 m)
             "collider": {"type": "none"}, "slots": [0, 2],
             "tags": ["occluder", "nonstatic"],
             "stalk": {"length": c["length"], "perch": c["perch"], "grip": c["grip"], "climb": c["climb"], "cut": CUT_H,
                       "r0": c["r0"], "r1": c["r1"], "joints": c["joints"]}}
    return path, entry


def export_hierarchy(objs, path):
    """Como nindo_lib.export_fbx pero SIN bake_space_transform: con él, el exportador de Blender escribe mal las
    jerarquías (cada objeto hijo corrido y girado 90° en profundidades alternas; reimportado, el posado quedaba a -1.7 m).
    Así las raíces (Stalk, Base, Stump) llevan el giro de ejes y cada hijo su transform local de Blender (Z a lo largo
    del culmo); el mundo queda igual que el de los props (-Y de Blender = +Z de Unity). ArenaStalk no supone giros de
    reposo: mide los que trae el FBX."""
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={'MESH', 'EMPTY'},
                             apply_unit_scale=True, apply_scale_options='FBX_SCALE_UNITS',
                             axis_forward='-Z', axis_up='Y', bake_space_transform=False,
                             mesh_smooth_type='FACE', use_mesh_modifiers=True, add_leaf_bones=False,
                             bake_anim=False, path_mode='STRIP', embed_textures=False,
                             use_custom_props=False, colors_type='LINEAR')


def export_stump():
    L.clear_scene()
    o = build_stump("inner", 7)
    path = os.path.join(OUT_DIR, "arena_stalk_stump.fbx")
    L.export_fbx([o], path)
    # el tocón suelto (si el jefe lo quiere instanciar aparte): el mismo pie que la caña entera, sin collider propio
    return path, {"module": "arena_stalks", "tris": len(o.data.polygons), "size": [0.4, 1.1, 0.4],
                  "collider": {"type": "none"}, "slots": [0], "tags": ["nonstatic"]}


def check():
    """Lint: juntas sin abrirse con los arcos del diseño, anclas a la altura del contrato, triángulos."""
    bad = 0
    for k, c in KINDS.items():
        L.clear_scene()
        objs = build(k)
        bpy.context.view_layer.update()
        wz = lambda n: objs[n].matrix_world.translation.z
        print(f"== {k}: largo {c['length']} m, PerchNode {wz('PerchNode'):.3f} (contrato {c['perch']}), GripHigh {wz('GripHigh'):.3f} "
              f"({c['grip']}), ClimbGrip {wz('ClimbGrip'):.3f} ({c['climb']}), BaseCut {wz('BaseCut'):.3f} ({CUT_H}), Tip {wz('Tip'):.3f}")
        for n, want in (("PerchNode", c["perch"]), ("GripHigh", c["grip"]), ("ClimbGrip", c["climb"]), ("BaseCut", CUT_H), ("Tip", c["length"])):
            if abs(wz(n) - want) > 0.005:
                print(f"   FAIL {n} a {wz(n):.3f}, el contrato dice {want}")
                bad += 1
        # la mano no agarra un anillo: a 8 cm o más de cualquier junta
        for n in ("GripHigh", "ClimbGrip"):
            dj = min(abs(wz(n) - j) for j in c["joints"][1:])
            if dj < 0.08:
                print(f"   FAIL {n} a {dj:.2f} m de un nudo")
                bad += 1
        tris = sum(len(o.data.polygons) for o in objs.values() if o.type == 'MESH' and o.name not in ("Stump",))
        # son props de pelea (siete en el mapa): un poco más que un árbol (700 en STYLE.md), por los nudos, el posado y la copa
        print(f"   triángulos {tris} (sin el tocón)")
        if tris > (1400 if k == "mother" else 1100):
            print("   FAIL demasiados triángulos")
            bad += 1
        for deg, ev, what in ((35, 0.0, "cargada 35°"), (-50, 0.0, "latigazo -50°"), (70, 1.0, "inclinada 70° pareja (fase 2)")):
            worst = max(joint_gaps(k, deg, ev), key=lambda t: t[1])
            ok = worst[1] <= 0.0
            print(f"   {what}: peor junta {worst[0]} con {worst[1] * 100:+.1f} cm {'(tapada)' if ok else 'FAIL'}")
            bad += 0 if ok else 1
        # dónde queda el posado con el arco del diseño (el código lo lee del transform)
        for deg in (6, 20, 30):
            apply_bend(objs, k, deg)
            p = objs["PerchNode"].matrix_world.translation
            print(f"   arco {deg:2d}°: PerchNode a {p.z:.3f} m de alto, corrido {math.hypot(p.x, p.y):.3f} m")
        apply_bend(objs, k, 70, evenness=1.0)
        t = objs["Tip"].matrix_world.translation
        print(f"   inclinada 70° pareja: la punta a {math.hypot(t.x, t.y):.2f} m del pie y {t.z:.2f} m de alto")
    bad += check_csharp()
    print("CHECK", "OK" if bad == 0 else f"{bad} FAIL")
    return bad


def check_csharp():
    """Las medidas de cada tipo en World/ArenaStalk.cs (CulmRadius, alturas) tienen que ser las de KINDS."""
    import re
    cs = open(os.path.join(REPO, "Nindo", "Assets", "Nindo", "Scripts", "World", "ArenaStalk.cs"), encoding="utf-8").read()
    bad = 0
    for k, c in KINDS.items():
        m = re.search(r'kind = "%s", length = ([\d.]+)f, perch = ([\d.]+)f, grip = ([\d.]+)f, climb = ([\d.]+)f, r0 = ([\d.]+)f, r1 = ([\d.]+)f' % k, cs)
        if not m:
            print(f"   FAIL ArenaStalk.cs no tiene la fila de '{k}'")
            bad += 1
            continue
        got = [float(g) for g in m.groups()]
        want = [c["length"], c["perch"], c["grip"], c["climb"], c["r0"], c["r1"]]
        if any(abs(a - b) > 1e-4 for a, b in zip(got, want)):
            print(f"   FAIL ArenaStalk.cs '{k}': {got}, arena_stalks.py: {want}")
            bad += 1
    if f"CutHeight = {CUT_H}f" not in cs:
        print("   FAIL ArenaStalk.CutHeight no es CUT_H")
        bad += 1
    return bad


def main():
    if "--check" in argv:
        check()
    if "--export" in argv:
        man = {}
        for k in KINDS:
            path, entry = export_kind(k)
            man[f"arena_stalk_{k}"] = entry
            print("EXPORTED", path, entry["tris"], "tris")
        path, entry = export_stump()
        man["arena_stalk_stump"] = entry
        print("EXPORTED", path)
        os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
        with open(MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(man, fh, indent=1, sort_keys=True)


if __name__ == "__main__":
    main()
