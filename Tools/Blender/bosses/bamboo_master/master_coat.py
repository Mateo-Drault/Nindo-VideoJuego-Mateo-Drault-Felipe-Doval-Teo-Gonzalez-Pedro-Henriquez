"""El saco de Chikuō en PhaseCoat: se le desliza puesto (formas CoatSlip1..N de Master_Robe) y en CoatOff lo reemplaza
la copia que vuela (Master_RobeThrown), que es el MISMO saco en ese cuadro, vértice por vértice.

Lo que hace build_bamboo_master con esto, después de hornear los clips:
  * write_coat_slip: el peso de cada etapa en la toma única (timing.slip_curve de PhaseCoat: de 0 a 1 en f30..f41);
  * refine_slip: corrige las etapas contra el cuerpo con la pose de cada cuadro (el saco no se mete en el pecho, los
    brazos ni las manos más que lo que ya se metía puesto);
  * rebuild_thrown: arma Master_RobeThrown con la malla del saco puesto, pesada a los huesos RobeT_*, con el reposo que
    hace que en CoatOff quede exactamente donde estaba el puesto (skin inverso). Antes era una tela aplanada: en el cambio
    de malla la silueta perdía el 78 % del saco y los brazos aparecían desnudos en un cuadro;
  * write_collapse: la forma Collapse de la copia (el saco vacío se aplana mientras vuela y cae);
  * lint: penetraciones del saco en el cuerpo y el salto de silueta en CoatOff desde las cámaras del juego.
"""
import math
import bpy
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
import nindo_anim as NA
import master_model as MM

CLEAR = 0.01             # lo que el saco queda afuera del cuerpo cuando la corrección lo saca (m)
DEEP = 0.14              # más adentro que esto el más cercano es del otro lado de una pieza: no se corrige
STEP_MAX = 0.04          # lo más que se corre un vértice en una pasada (las pasadas siguientes completan)
W_MIN = 0.4              # peso de etapa desde el que se corrige un cuadro
PEN_WORSE_MAX = 0.02     # lint: lo más que un vértice del saco puede quedar más adentro que con el saco puesto (m)
PEN_SHARE_MAX = 0.02     # lint: fracción de vértices que pueden quedar 1 cm más adentro que puesto


# ============================================================================ pesos de las etapas
def stage_weights(s):
    """Peso de CoatSlip1..N para una salida s (0..1): de una etapa a la siguiente en línea recta (cada etapa ya es el
    punto girado de verdad: la cuerda entre dos etapas seguidas se aparta poco del arco)."""
    x = max(0.0, min(1.0, s)) * MM.SLIP_STAGES
    return [max(0.0, 1.0 - abs(x - k)) for k in range(1, MM.SLIP_STAGES + 1)]


def slip_curve(clip):
    """{cuadro del clip: salida 0..1} de timing.slip_curve (lineal entre sus puntos); desde robe_off vale 1."""
    pts = clip.timing.get("slip_curve")
    if not pts:
        return {}
    off = clip.timing.get("robe_off")
    out = {}
    for f in range(clip.frames + 1):
        if off is not None and f >= off:
            out[f] = 1.0
            continue
        if f <= pts[0][0]:
            out[f] = float(pts[0][1])
            continue
        if f >= pts[-1][0]:
            out[f] = float(pts[-1][1])
            continue
        i = max(k for k in range(len(pts) - 1) if pts[k][0] <= f)
        (f0, v0), (f1, v1) = pts[i], pts[i + 1]
        out[f] = v0 + (v1 - v0) * (f - f0) / (f1 - f0)
    return out


def slip_keys(robe):
    keys = robe.data.shape_keys if robe is not None and robe.type == 'MESH' else None
    if keys is None:
        return []
    return [keys.key_blocks[n] for n in MM.slip_names() if n in keys.key_blocks]


def write_coat_slip(robe, baked, ranges, last):
    """El peso de cada etapa CoatSlip en la toma única: lo que dice timing.slip_curve en los clips que la tienen
    (PhaseCoat) y 0 en todos los demás cuadros. El FBX lo lleva como DeformPercent y Unity como blendShape.CoatSlipK de
    Master_Robe. Devuelve {cuadro de la toma: salida} de los cuadros con peso."""
    kbs = slip_keys(robe)
    if not kbs:
        return {}
    vals = {0: [0.0] * len(kbs), last: [0.0] * len(kbs)}
    on = {}
    for clip, frames in baked:
        sc = slip_curve(clip)
        if not sc or not any(v > 0.0 for v in sc.values()):
            continue
        a, b = ranges[clip.name]
        off = clip.timing.get("robe_off")
        vals[a - 1] = [0.0] * len(kbs)
        for f, s in sc.items():
            vals[a + f] = stage_weights(s)
            # desde CoatOff el saco puesto está apagado: solo cuenta el cuadro del cambio (la copia sale de ahí)
            if s > 0.0 and (off is None or f <= off):
                on[a + f] = s
        vals[b + 1] = [0.0] * len(kbs)
    for f in sorted(vals):
        for kb, w in zip(kbs, vals[f]):
            kb.value = w
            kb.keyframe_insert("value", frame=f)
    for kb in kbs:
        kb.value = 0.0
    # lineal: entre las claves de cada cuadro no hay nada que suavizar y afuera de PhaseCoat queda en 0 parejo
    ad = robe.data.shape_keys.animation_data
    if ad is not None and ad.action is not None:
        for fc in ad.action.fcurves:      # (bl_compat: la channelbag del slot de las formas)
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'
    print(f"  {robe.name}: {len(kbs)} etapas CoatSlip animadas en {len(on)} cuadros")
    return on


# ============================================================================ el saco contra el cuerpo
def _mesh_world(o, dg):
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    M = oe.matrix_world.copy()
    vs = [M @ v.co for v in me.vertices]
    tris = None
    if o.type == 'MESH':
        me.calc_loop_triangles()
        tris = [tuple(t.vertices) for t in me.loop_triangles]
    oe.to_mesh_clear()
    return vs, tris


class _Part:
    """Superficie con árbol y normales suaves por vértice (la normal de la cara sola cambiaba de signo en las aristas y
    daba "adentro" a 5 cm afuera)."""
    def __init__(self, vs, tris):
        self.vs, self.tris = vs, tris
        self.tree = BVHTree.FromPolygons(vs, tris)
        nr = {}
        for a, b, c in tris:
            fn = (vs[b] - vs[a]).cross(vs[c] - vs[a])     # largo = doble del área: pesa por área
            for i in (a, b, c):
                nr[i] = nr.get(i, Vector()) + fn
        self.nr = {i: (n.normalized() if n.length > 1e-12 else Vector((0.0, 0.0, 1.0))) for i, n in nr.items()}
        used = [vs[i] for i in nr]
        self.c = sum(used, Vector()) / max(1, len(used))
        self.r = max((p - self.c).length for p in used) if used else 0.0

    def signed(self, p):
        loc, fnrm, idx, _ = self.tree.find_nearest(p)
        if loc is None:
            return 9.0, Vector((0.0, 0.0, 1.0))
        a, b, c = self.tris[idx]
        A, B, C = self.vs[a], self.vs[b], self.vs[c]
        v0, v1, v2 = B - A, C - A, loc - A
        d00, d01, d11, d20, d21 = v0.dot(v0), v0.dot(v1), v1.dot(v1), v2.dot(v0), v2.dot(v1)
        den = d00 * d11 - d01 * d01
        n = fnrm
        if abs(den) > 1e-14:
            wb = (d11 * d20 - d01 * d21) / den
            wc = (d00 * d21 - d01 * d20) / den
            m = self.nr[a] * (1.0 - wb - wc) + self.nr[b] * wb + self.nr[c] * wc
            if m.length > 1e-9:
                n = m.normalized()
        return (p - loc).dot(n), n


class Surface(_Part):
    """El cuerpo evaluado en un cuadro (sin lo que cuelga suelto) como una sola superficie con normales suaves."""


def _signed(surf, pts):
    """Distancia con signo (+ afuera) de cada punto al cuerpo y la normal hacia afuera en el punto más cercano."""
    return [surf.signed(p) for p in pts]


# lo que cuelga suelto del cuerpo (colas de la faja, bigotes, cejas) no cuenta como cuerpo: una cinta fina tiene dos
# caras y el más cercano daba "adentro" a un metro de lo que importa
LOOSE = ("Acc_", "Brow_", "Whisker")
_SOLID = {}


def _solid_tris(body, tris):
    key = (body.name, len(tris))
    if key not in _SOLID:
        dom = []
        for v in body.data.vertices:
            g = max(v.groups, key=lambda g: g.weight, default=None)
            dom.append(body.vertex_groups[g.group].name if g is not None else "")
        _SOLID[key] = [t for t in tris if not any(dom[i].startswith(LOOSE) for i in t)]
    return _SOLID[key]


def _body_tree(body, dg):
    vs, tris = _mesh_world(body, dg)
    return Surface(vs, _solid_tris(body, tris))


def _with_slip_muted(kbs, fn):
    saved = [kb.mute for kb in kbs]
    for kb in kbs:
        kb.mute = True
    try:
        return fn()
    finally:
        for kb, m in zip(kbs, saved):
            kb.mute = m


def skin_matrix(arm, o, idx, cache):
    """La matriz de skin (lineal) del vértice idx de o con la pose actual: suma de peso · pose · reposo⁻¹."""
    v = o.data.vertices[idx]
    S = Matrix(((0.0,) * 4,) * 4)
    tot = 0.0
    for g in v.groups:
        nm = o.vertex_groups[g.group].name
        m = cache.get(nm)
        if m is None:
            pb = arm.pose.bones.get(nm)
            if pb is None:
                continue
            m = cache[nm] = pb.matrix @ arm.data.bones[nm].matrix_local.inverted()
        S += m * g.weight
        tot += g.weight
    if tot <= 1e-8:
        return Matrix.Identity(4)
    return S * (1.0 / tot)


def refine_slip(scn, arm, robe, body, frames, sweeps=5):
    """Saca el saco del cuerpo en los cuadros con peso de CoatSlip ('frames': {cuadro de la toma: salida}). En cada
    cuadro, los vértices que quedan a menos de CLEAR afuera (o más adentro que con el saco puesto en esa misma pose: lo
    que ya se metía no es de las formas) se corren por la normal del cuerpo; el corrimiento vuelve al reposo con la
    matriz de skin del vértice y se reparte entre las etapas que pesan en ese cuadro."""
    kbs = slip_keys(robe)
    if not kbs or not frames:
        return
    Mr = robe.matrix_world.copy()
    Ri = Mr.inverted().to_3x3()
    moved_tot, worst = 0, 0.0
    for sweep in range(sweeps):
        n_fix = 0
        for F in sorted(frames):
            scn.frame_set(F)
            dg = bpy.context.evaluated_depsgraph_get()
            tree = _body_tree(body, dg)
            ws = [kb.value for kb in kbs]
            sw2 = sum(w * w for w in ws)
            # con poco peso (recién lo abre) es el saco puesto: corregir ahí multiplicaba el corrimiento por 1/peso
            if max(ws) < W_MIN:
                continue
            cur, _ = _mesh_world(robe, dg)
            base, _ = _with_slip_muted(kbs, lambda: _mesh_world(robe, bpy.context.evaluated_depsgraph_get()))
            dc = _signed(tree, cur)
            db = _signed(tree, base)
            cache = {}
            for i, ((d, nrm), (d0, _)) in enumerate(zip(dc, db)):
                # la distancia no puede cambiar más de lo que se movió el vértice: más que eso es el signo que salta
                # entre dos piezas del cuerpo que se cruzan (los puños contra el pecho), no un saco metido
                d = max(d, d0 - (cur[i] - base[i]).length)
                want = min(CLEAR, d0) if d0 < CLEAR else CLEAR
                # más hondo que DEEP no es un saco metido: es el lado de adentro de otra pieza del cuerpo
                if d >= want - 1e-4 or d < -DEEP:
                    continue
                push = Ri @ (nrm * min(STEP_MAX, want - d))
                S = skin_matrix(arm, robe, i, cache).to_3x3()
                try:
                    dbind = S.inverted() @ push
                except ValueError:
                    continue
                for kb, w in zip(kbs, ws):
                    if w > 1e-4:
                        kb.data[i].co = kb.data[i].co + dbind * (w / sw2)
                n_fix += 1
                worst = max(worst, want - d)
            robe.data.update()
            robe.update_tag()
        moved_tot += n_fix
        print(f"  saco contra el cuerpo: pasada {sweep + 1}, {n_fix} correcciones")
        if n_fix == 0:
            break
    print(f"  saco contra el cuerpo: {moved_tot} correcciones (la peor {worst * 100:.1f} cm)")


def penetration_report(scn, robe, body, frames):
    """{cuadro: (vértices 1 cm más adentro que puesto, el peor exceso m, vértices adentro > 1 cm, más hondo m)}."""
    kbs = slip_keys(robe)
    rep = {}
    for F in sorted(frames):
        scn.frame_set(F)
        dg = bpy.context.evaluated_depsgraph_get()
        tree = _body_tree(body, dg)
        cur, _ = _mesh_world(robe, dg)
        base, _ = _with_slip_muted(kbs, lambda: _mesh_world(robe, bpy.context.evaluated_depsgraph_get()))
        db = [d for d, _ in _signed(tree, base)]
        # (acotada por lo que se movió cada vértice, como en refine_slip)
        dc = [max(d, d0 - (c - b).length) for (d, _), d0, c, b in zip(_signed(tree, cur), db, cur, base)]
        worse = [min(0.0, d) - min(0.0, d0) for d, d0 in zip(dc, db)]
        n_worse = sum(1 for w in worse if w < -0.01)
        rep[F] = (n_worse, -min(worse), sum(1 for d in dc if d < -0.01), -min(dc))
    return rep


# ============================================================================ la copia que vuela
SLEEVE_GROUPS = ("UpperArm_", "Forearm_", "Sleeve_", "Clav_", "Hand_")
HEM_CUTS = (("RobeT_Root", 1.62), ("RobeT_Hem", 1.30), ("RobeT_Hem_1", 1.08))   # dónde empieza cada tramo del ruedo
COLLAPSE = "Collapse"
COLLAPSE_DEPTH = 0.3     # el saco vacío en el piso: lo que le queda del espesor de adelante hacia atrás
COLLAPSE_WIDEN = 1.12    # y cuánto se ensancha el cuerpo del saco al aplanarse
COLLAPSE_Y = 0.03        # el plano al que se aplana (y de reposo: el eje del tronco)


def _smooth01(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def thrown_weights(robe):
    """Los pesos de la copia a los huesos RobeT_*, desde el saco puesto en reposo: las mangas a los dos tramos de su
    manga (con el hombro mezclado con el cuello del saco) y lo demás al ruedo por la altura."""
    S0, E0, W0, u0, l0 = MM.arm_points()
    out = []
    for v in robe.data.vertices:
        g = max(v.groups, key=lambda g: g.weight, default=None)
        name = robe.vertex_groups[g.group].name if g is not None else "Chest"
        co = v.co
        if name.startswith(SLEEVE_GROUPS):
            s = "R" if co.x < 0.0 else "L"
            k = 1.0 if s == "R" else -1.0
            Sh, Wr = Vector((S0.x * k, S0.y, S0.z)), Vector((W0.x * k, W0.y, W0.z))
            d = Wr - Sh
            t = (co - Sh).dot(d) / max(1e-6, d.length_squared)
            w2 = _smooth01((t - 0.42) / 0.26)
            root = _smooth01((0.1 - t) / 0.22)
            w = {"RobeT_Root": root, "RobeT_Arm" + s: (1.0 - w2) * (1.0 - root), "RobeT_Arm" + s + "_2": w2 * (1.0 - root)}
        else:
            z = co.z
            w = {"RobeT_Hem_2": 1.0}
            for i, (b, c) in enumerate(HEM_CUTS):
                nxt = HEM_CUTS[i + 1][0] if i + 1 < len(HEM_CUTS) else "RobeT_Hem_2"
                if z > c + 0.06:
                    w = {b: 1.0}
                    break
                if z > c - 0.06:
                    a = _smooth01((c + 0.06 - z) / 0.12)
                    w = {b: 1.0 - a, nxt: a}
                    break
        tot = sum(w.values())
        out.append({b: x / tot for b, x in w.items() if x > 1e-4})
    return out


def rebuild_thrown(scn, arm, meshes, F):
    """Master_RobeThrown nuevo: la malla del saco puesto (sin sus formas), pesada a RobeT_* y con el reposo que la deja,
    con la pose de los RobeT_* en el cuadro F (CoatOff), exactamente donde está el saco puesto en ese cuadro (skin
    inverso: reposo = (suma de peso * pose * reposo^-1)^-1 * destino). En F los RobeT_* están donde los pondría el cuerpo
    (master_clips.coat_off_place), así que el reposo queda cerca del saco puesto en reposo (y adentro del alto de bind).
    Devuelve el objeto nuevo."""
    import master_rig as MR
    robe, old = meshes["Master_Robe"], meshes["Master_RobeThrown"]
    scn.frame_set(F)
    dg = bpy.context.evaluated_depsgraph_get()
    target, _ = _mesh_world(robe, dg)
    me = robe.data.copy()
    o = bpy.data.objects.new("_thrown", me)
    scn.collection.objects.link(o)
    if me.shape_keys is not None:
        o.shape_key_clear()
    weights = thrown_weights(robe)
    # la copia trae los pesos del saco puesto con sus índices de grupo: se borran con los grupos de esos nombres (si no,
    # los índices 0..7 quedaban como pesos a los RobeT_* nuevos)
    for g in robe.vertex_groups:
        o.vertex_groups.new(name=g.name)
    o.vertex_groups.clear()
    groups = {b: o.vertex_groups.new(name=b) for b in MR.ROBE_T}
    for i, w in enumerate(weights):
        for b, x in w.items():
            groups[b].add([i], x, 'REPLACE')
    M = {b: arm.pose.bones[b].matrix @ arm.data.bones[b].matrix_local.inverted() for b in MR.ROBE_T}
    Ai = arm.matrix_world.inverted()
    for i, v in enumerate(me.vertices):
        S = Matrix(((0.0,) * 4,) * 4)
        for b, x in weights[i].items():
            S += M[b] * x
        v.co = S.inverted() @ (Ai @ target[i])
    me.update()
    name, mname = old.name, old.data.name
    old_me = old.data
    bpy.data.objects.remove(old, do_unlink=True)
    if old_me.users == 0:
        bpy.data.meshes.remove(old_me)
    o.name, me.name = name, mname
    o.parent = arm
    mod = o.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    meshes["Master_RobeThrown"] = o
    # el saco vacío aplanado (la forma Collapse): de adelante hacia atrás al espesor de una tela y un poco más ancho
    o.shape_key_add(name="Basis", from_mix=False)
    kb = o.shape_key_add(name=COLLAPSE, from_mix=False)
    for i, v in enumerate(me.vertices):
        sleeve = any(b.startswith("RobeT_Arm") for b in weights[i])
        x = v.co.x if sleeve else v.co.x * COLLAPSE_WIDEN
        kb.data[i].co = Vector((x, COLLAPSE_Y + (v.co.y - COLLAPSE_Y) * COLLAPSE_DEPTH, v.co.z))
    print(f"  {name}: copia del saco puesto en el cuadro {F} ({len(me.vertices)} vértices, {len(me.polygons)} caras)")
    return o


def _curve_at(pts, f):
    if f <= pts[0][0]:
        return float(pts[0][1])
    if f >= pts[-1][0]:
        return float(pts[-1][1])
    i = max(k for k in range(len(pts) - 1) if pts[k][0] <= f)
    (f0, v0), (f1, v1) = pts[i], pts[i + 1]
    return v0 + (v1 - v0) * (f - f0) / (f1 - f0)


def write_collapse(thrown, baked, ranges, last):
    """El peso de Collapse en la toma: timing.collapse_curve de PhaseCoat (0 en CoatOff, 1 al caer) y 0 afuera."""
    keys = thrown.data.shape_keys
    if keys is None or COLLAPSE not in keys.key_blocks:
        return
    kb = keys.key_blocks[COLLAPSE]
    vals = {0: 0.0, last: 0.0}
    for clip, frames in baked:
        pts = clip.timing.get("collapse_curve")
        if not pts:
            continue
        a, b = ranges[clip.name]
        vals[a - 1] = 0.0
        for f in range(clip.frames + 1):
            vals[a + f] = _curve_at(pts, f)
        vals[b + 1] = 0.0
    for f in sorted(vals):
        kb.value = vals[f]
        kb.keyframe_insert("value", frame=f)
    kb.value = 0.0
    ad = keys.animation_data
    if ad is not None and ad.action is not None:
        for fc in ad.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = 'LINEAR'


# ============================================================================ el cambio de malla desde las cámaras
CAMS = {"juego": dict(focus=(0.0, -1.6, 1.0), pitch=52.0, dist=24.0, fov=30.0),
        "pelea": dict(focus=(0.0, -1.6, 1.0), pitch=45.0, dist=20.6, fov=30.0)}
IOU_MIN = 0.9            # silueta de la figura entre el último cuadro con el saco puesto y CoatOff
COAT_RATIO_MIN = 0.8     # píxeles de la copia en CoatOff sobre los del saco puesto en el cuadro anterior


def swap_report(scn, meshes, F_off):
    """Silueta de la figura y del saco en F_off - 1 (saco puesto) y F_off (la copia), desde las dos cámaras:
    {cámara: (IoU de la figura, píxeles de la copia / del puesto, px del puesto, px de la copia)}."""
    cam = NA.camera(scn, "CoatCam")
    body, robe, thrown = meshes["Master_Body"], meshes["Master_Robe"], meshes["Master_RobeThrown"]
    out = {}
    saved = (robe.hide_render, thrown.hide_render, scn.camera)
    for nm, c in CAMS.items():
        NA.game_camera(cam, **c)
        masks = {}
        for F, coat in ((F_off - 1, robe), (F_off, thrown)):
            scn.frame_set(F)
            robe.hide_render, thrown.hide_render = coat is not robe, coat is not thrown
            masks[F] = (NA.silhouette_mask([body, coat], cam, scn), NA.silhouette_mask([coat], cam, scn))
        (fa, ca), (fb, cb) = masks[F_off - 1], masks[F_off]
        iou = float((fa & fb).sum()) / max(1, int((fa | fb).sum()))
        ratio = float(cb.sum()) / max(1, int(ca.sum()))
        out[nm] = (round(iou, 3), round(ratio, 3), int(ca.sum()), int(cb.sum()))
    robe.hide_render, thrown.hide_render, scn.camera = saved
    return out
