"""Chequeos propios de Gorō sobre lo horneado (build_team_anims los llama por team_clips_goro.mesh_checks).

El martillo mide 3.7 m y el mango sigue 1.2 m más allá de la mano de abajo: en los golpes con el mango acostado esa
cola atravesaba el torso (Combo2, el aterrizaje del Heavy). Los chequeos del rig miran el piso, las muñecas y los pies,
no el cuerpo contra el arma: esto lo mide cuadro a cuadro.

  * El cuerpo: un casco convexo por hueso (los vértices de la piel que ese hueso domina, en reposo) que viaja rígido con
    su hueso. La malla del equipo son varias cáscaras superpuestas con normales para cualquier lado: "adentro" por la
    normal más cercana o por paridad de rayos daba metros de falsos positivos; el casco convexo es cerrado y exacto. Sin
    las manos, los dedos y los antebrazos (agarran el mango), ni los shide de papel y el maedate de oro (cuelgan o salen
    del contorno: rozarlos no es atravesar el cuerpo).
  * El martillo: sus vértices más puntos cada 5 cm sobre sus aristas; se saltean los del mango a menos de 22 cm (a lo
    largo) de cada mano que lo agarra: el puño lo envuelve.
  * Con la armadura (clips con timing['armored']), cada roca es un casco más, rígido con su hueso.

Profundidad = cuánto se metió el punto más hondo (distancia a la cara del casco más cercana). El límite es 6 cm: el casco
de un hueso incluye la carne de la articulación vecina (el hombro, la cadera) y un mango que pasa pegado a la piel queda
2-5 cm adentro; medio mango (10 cm de grueso) atravesando el torso pasa de 10. Falla, salvo en los cuadros de
timing['clip_ok'] (rangos [a, b]), que se informan.
"""
import bpy, bmesh, os
from mathutils import Vector

# GORO_CHECKS_DEBUG=1: imprime la profundidad de cada cuadro que pasa el límite (para iterar un clip con --only)
DEBUG = os.environ.get("GORO_CHECKS_DEBUG") == "1"

DEPTH_CM = 6.0
SKIP_ALONG = 0.22
SKIP_BONES = ("Mano", "Dedo", "Puntadedo", "Antebrazo")
SKIP_MATS = ("ShideMiniJefe", "OroMiniJefe")


def _dominant(o, v):
    gs = [g for g in v.groups if g.weight > 0.0]
    if not gs:
        return ""
    return o.vertex_groups[max(gs, key=lambda g: g.weight).group].name


def hull_planes(pts):
    """Planos (normal hacia afuera, d) del casco convexo de los puntos: adentro si n.p < d en todos."""
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=bm.verts, use_existing_faces=False)
    for g in res["geom_interior"] + res["geom_unused"]:
        if isinstance(g, bmesh.types.BMVert) and g.is_valid:
            bm.verts.remove(g)
    bm.faces.ensure_lookup_table()
    c = sum((v.co for v in bm.verts), Vector()) / max(1, len(bm.verts))
    planes = []
    for f in bm.faces:
        n = f.normal.copy()
        if n.length < 1e-9:
            continue
        p0 = f.verts[0].co
        if n.dot(c - p0) > 0.0:
            n = -n
        planes.append((n, n.dot(p0)))
    rad = max((v.co - c).length for v in bm.verts) if len(bm.verts) else 0.0
    bm.free()
    return planes, c, rad


def depth_in(hull, p):
    """Cuánto está adentro p (m; <= 0 afuera). La esfera que envuelve el casco descarta casi todo sin mirar planos."""
    planes, c, rad = hull
    if (p - c).length_squared > rad * rad:
        return -1.0
    worst = 1e9
    for n, d in planes:
        s = d - n.dot(p)
        if s < worst:
            worst = s
            if worst <= 0.0:
                return worst
    return worst


class Clearance:
    """Se arma una vez por personaje: los cascos de cada hueso (marco de autoría, reposo) y los puntos del martillo."""

    def __init__(self, ch, armor=None):
        self.ch = ch
        body = next(o for o in ch.meshes if o.vertex_groups and o.name.startswith("Cylinder.001"))
        self.ham = bpy.data.objects[ch.spec["weapon"]["mesh"]]
        me = body.data
        skip_v = set()
        for p in me.polygons:
            m = body.material_slots[p.material_index].material if p.material_index < len(body.material_slots) else None
            if m is not None and any(m.name.startswith(s) or m.name.startswith("rv_" + s) for s in SKIP_MATS):
                skip_v.update(p.vertices)
        Mw = body.matrix_world
        by_bone = {}
        for v in me.vertices:
            if v.index in skip_v:
                continue
            b = _dominant(body, v)
            if not b or b.startswith(SKIP_BONES) or b not in ch.rig.names:
                continue
            by_bone.setdefault(b, []).append(ch.Pc(ch.Ai @ (Mw @ v.co)))
        self.hulls = [(b, hull_planes(pts)) for b, pts in by_bone.items() if len(pts) >= 8]
        # la armadura: cada roca es un casco rígido con su hueso (goro_armor.rocks_for_checks)
        self.armor = [(piece, b, hull_planes([Vector(p) for p in pts]), [Vector(p) for p in pts]) for piece, b, pts in (armor or [])]
        hm = self.ham.data
        M = self.ham.matrix_world
        pts = [v.co.copy() for v in hm.vertices]
        for e in hm.edges:
            a, b = hm.vertices[e.vertices[0]].co, hm.vertices[e.vertices[1]].co
            n = int(((M @ b) - (M @ a)).length / (0.05 * ch.u))
            pts += [a.lerp(b, (i + 1) / (n + 1)) for i in range(n)]
        self.ham_pts = pts

    def bone_inv(self, name):
        """Punto de la armadura en la pose actual -> el mismo punto del hueso en reposo, en el marco de autoría."""
        ch = self.ch
        pb = ch.arm.pose.bones[name]
        R = ch.arm.data.bones[name].matrix_local @ pb.matrix.inverted()
        return lambda q: ch.Pc(R @ q)

    def armor_low(self, pieces):
        """Lo más bajo de las rocas puestas (cm sobre el piso) y cuál, en la pose actual."""
        ch = self.ch
        low, where = 900.0, ""
        for piece, b, hull, pts in self.armor:
            if piece not in pieces:
                continue
            pb = ch.arm.pose.bones[b]
            M = pb.matrix @ ch.arm.data.bones[b].matrix_local.inverted()
            for p in pts:
                z = ch.Pc(M @ ch.P(p)).z * 100.0
                if z < low:
                    low, where = z, piece
        return low, where

    def frame(self, scn, f_scene, ctrl, pieces):
        """(peor profundidad en cm, dónde) en el cuadro de escena dado; 'pieces': las rocas puestas."""
        ch = self.ch
        scn.frame_set(f_scene)
        dg = bpy.context.evaluated_depsgraph_get()
        he = self.ham.evaluated_get(dg)
        Mh = ch.Ai @ he.matrix_world
        hp = [Mh @ p for p in self.ham_pts]                       # espacio de la armadura
        w = ch.weapon_info
        pb = ch.arm.pose.bones[ch.spec["weapon"]["bone"]].matrix
        base = pb.translation
        axis = (pb.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized()
        grips = []
        if (ctrl.get("drop_r") or 0.0) < 0.5:
            grips.append(w["grips"][1] - (ctrl.get("slide_r") or 0.0))
        gl = ctrl.get("grip_l")
        if gl is None or gl > 0.5:
            grips.append(w["grips"][0] + (ctrl.get("slide_l") or 0.0))
        keep = []
        for q in hp:
            t = (q - base).dot(axis) / ch.u
            radial = ((q - base) - axis * (q - base).dot(axis)).length / ch.u
            if radial < 0.15 and any(abs(t - g) < SKIP_ALONG for g in grips):
                continue
            keep.append((q, t))
        hulls = self.hulls + [(b, hull) for piece, b, hull, _ in self.armor if piece in pieces]
        worst, where = 0.0, ""
        for b, hull in hulls:
            to_rest = self.bone_inv(b)
            for q, t in keep:
                d = depth_in(hull, to_rest(q))
                if d * 100.0 > worst:
                    worst = d * 100.0
                    part = "mango" if t < w["head_center"] - 0.45 else "cabeza"
                    where = f"{part} t={t:.2f} m en {b}"
        return worst, where


_CACHE = {}


ARMOR_FLOOR_CM = -2.0


def weapon_body(ch, clip, first, check, armor=None):
    """Chequeo del martillo contra el cuerpo y, en los clips de la fase 2, contra la armadura (timing['armored']: todas
    las rocas puestas; timing['armor_from']: {pieza: cuadro desde el que está puesta}, la cinemática de armado), más las
    rocas puestas que no se meten en el piso. Devuelve lo que va al sidecar."""
    key = id(ch)
    if key not in _CACHE:
        _CACHE[key] = Clearance(ch, armor)
    cl = _CACHE[key]
    scn = bpy.context.scene
    t = clip.timing
    all_pieces = {a[0] for a in cl.armor}
    since = t.get("armor_from") or ({p: 0 for p in all_pieces} if t.get("armored") else {})
    ok_ranges = t.get("clip_ok", [])
    bad, worst_at, low_at, low_bad = [], (0.0, -1, ""), (900.0, -1, ""), []
    for f in range(clip.frames + 1):
        on = {p for p, f0 in since.items() if f >= f0}
        d, where = cl.frame(scn, first + f, clip.controls(f), on)
        if d > DEPTH_CM and not any(a <= f <= b for a, b in ok_ranges):
            bad.append(f)
            if DEBUG:
                print(f"       {clip.name} f{f}: {d:.1f} cm ({where})")
        if d > worst_at[0]:
            worst_at = (d, f, where)
        if on:
            z, piece = cl.armor_low(on)
            if z < low_at[0]:
                low_at = (z, f, piece)
            if z < ARMOR_FLOOR_CM:
                low_bad.append(f)
    msg = (f"{clip.name}: el martillo no atraviesa el cuerpo{' ni la armadura' if since else ''} "
           f"(peor {worst_at[0]:.1f} cm en f{worst_at[1]}{': ' + worst_at[2] if worst_at[2] else ''}"
           f"{'; cuadros ' + ','.join(map(str, bad)) if bad else ''})")
    check(not bad, msg)
    out = {"weapon_in_body_cm": round(worst_at[0], 1), "weapon_in_body_frame": worst_at[1], "weapon_in_body_frames": bad}
    if since:
        check(not low_bad, f"{clip.name}: las rocas de la armadura no se meten en el piso (lo más bajo {low_at[0]:.1f} cm en "
                           f"f{low_at[1]}, {low_at[2]}{'; cuadros ' + ','.join(map(str, low_bad)) if low_bad else ''})")
        out["armor_lowest_cm"] = round(low_at[0], 1)
    return out
