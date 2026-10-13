"""Chequeos propios de Gorō sobre lo horneado (build_team_anims los llama por team_clips_goro.mesh_checks).

El martillo mide 3.7 m y el mango sigue 1.2 m más allá de la mano de abajo: en los golpes con el mango acostado esa
cola atravesaba el torso (Combo2, el aterrizaje del Heavy). Los chequeos del rig miran el piso, las muñecas y los pies,
no el cuerpo contra el arma: esto lo mide cuadro a cuadro.

  * El cuerpo: un casco convexo por hueso (los vértices de la piel que ese hueso domina, en reposo) que viaja rígido con
    su hueso. La malla del equipo son varias cáscaras superpuestas con normales para cualquier lado: "adentro" por la
    normal más cercana o por paridad de rayos daba metros de falsos positivos; el casco convexo es cerrado y exacto. Sin
    las manos, los dedos y los antebrazos (agarran el mango), ni los shide de papel y el maedate de oro (cuelgan o salen
    del contorno: rozarlos no es atravesar el cuerpo).
  * El martillo: sus vértices más puntos cada 5 cm sobre sus aristas; se saltean los del mango entre las dos manos y a
    menos de 8 cm (a lo largo) de cada una: el puño lo envuelve. Con 22 cm se salteaba también la cola: con las manos en la
    punta del mango sobran 16 cm detrás de la izquierda, y esa cola entraba 12 cm en la panza en las vueltas a la
    guardia sin que nada lo viera.
  * Con la armadura (clips con timing['armored']), cada roca es un casco más, rígido con su hueso.

Profundidad = cuánto se metió el punto más hondo (distancia a la cara del casco más cercana). El límite es 6 cm para el
cuerpo: el casco de un hueso incluye la carne de la articulación vecina (el hombro, la cadera) y un mango que pasa pegado
a la piel queda 2-5 cm adentro; medio mango (10 cm de grueso) atravesando el torso pasa de 10. La cola del mango (detrás
de la mano de abajo) y las rocas de la armadura (cascos exactos, sin carne) tienen 3 cm. Falla, salvo en los cuadros de
timing['clip_ok'] (rangos [a, b]), que se informan.

Además (motion_checks), sobre lo horneado:
  * el martillo no da vueltas de golpe: el mango (BaseM) gira a lo sumo 45° de un cuadro al otro fuera del golpe (del
    apex al último activo) y de los tramos de timing['swing_ok'] (los martillazos de los clips sin golpe del juego). El
    parry lo daba vuelta por encima en un cuadro (90-133°) y quedaba congelado;
  * brazos sin tics: un hueso del brazo que gira más de 45° en un cuadro, 30° más que sus vecinos, falla fuera de esas
    mismas ventanas (build_team_anims solo avisaba y los martillazos arrancaban con un sacudón de 55-110°);
  * FakeDefeat: la cabeza no cae más de 25 cm por cuadro (caía 91 cm en uno) y 'hammer_land' se mide en la malla: el
    primer cuadro, después de 'drop', en que el punto más bajo del mango (sin la cabeza, que ya estaba apoyada) llega a
    donde queda acostado (a 2 cm; la cabeza del martillo le levanta esa punta del piso);
  * ArmorRise arranca en la pose final de FakeDefeat (el juego los encadena): peor hueso en grados.
"""
import bpy, bmesh, os
from mathutils import Vector

# GORO_CHECKS_DEBUG=1: imprime la profundidad de cada cuadro que pasa el límite (para iterar un clip con --only)
DEBUG = os.environ.get("GORO_CHECKS_DEBUG") == "1"

DEPTH_CM = 6.0
# la cola del mango y las rocas: cascos exactos, sin la carne de las articulaciones
TIGHT_CM = 3.0
SKIP_ALONG = 0.08
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
        if gl is None or gl > 0.35:
            grips.append(w["grips"][0] + (ctrl.get("slide_l") or 0.0))
        keep = []
        tail = min(grips) if grips else w["butt"]
        for q in hp:
            t = (q - base).dot(axis) / ch.u
            radial = ((q - base) - axis * (q - base).dot(axis)).length / ch.u
            # el mango entre las dos manos y 8 cm a cada lado de cada una: los puños y los antebrazos lo tapan
            if radial < 0.15 and grips and min(grips) - SKIP_ALONG < t < max(grips) + SKIP_ALONG:
                continue
            keep.append((q, t))
        # sin las rocas de los antebrazos: el guantelete está pegado al puño que agarra el mango (como el antebrazo)
        hulls = [(b, hull, False) for b, hull in self.hulls] + [(b, hull, True) for piece, b, hull, _ in self.armor
                                                                 if piece in pieces and not b.startswith(SKIP_BONES)]
        # la peor profundidad relativa a su límite: el punto que más se pasó (o el más hondo, si ninguno se pasa)
        worst, where, over = 0.0, "", -9.0
        for b, hull, rock in hulls:
            to_rest = self.bone_inv(b)
            for q, t in keep:
                d = depth_in(hull, to_rest(q)) * 100.0
                if d <= 0.0:
                    continue
                lim = TIGHT_CM if rock or t < tail - SKIP_ALONG else DEPTH_CM
                if d - lim > over:
                    over = d - lim
                    part = "cola" if t < tail - SKIP_ALONG else ("mango" if t < w["head_center"] - 0.45 else "cabeza")
                    worst, where = d, f"{part} t={t:.2f} m en {'roca ' if rock else ''}{b} (tope {lim:.0f})"
        return worst, where, over > 0.0


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
        d, where, past = cl.frame(scn, first + f, clip.controls(f), on)
        if past and not any(a <= f <= b for a, b in ok_ranges):
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
    msg = (f"{clip.name}: el martillo (con la cola) no atraviesa el cuerpo{' ni la armadura' if since else ''} "
           f"(peor {worst_at[0]:.1f} cm en f{worst_at[1]}{': ' + worst_at[2] if worst_at[2] else ''}"
           f"{'; cuadros ' + ','.join(map(str, bad)) if bad else ''})")
    check(not bad, msg)
    out = {"weapon_in_body_cm": round(worst_at[0], 1), "weapon_in_body_frame": worst_at[1], "weapon_in_body_frames": bad}
    if since:
        check(not low_bad, f"{clip.name}: las rocas de la armadura no se meten en el piso (lo más bajo {low_at[0]:.1f} cm en "
                           f"f{low_at[1]}, {low_at[2]}{'; cuadros ' + ','.join(map(str, low_bad)) if low_bad else ''})")
        out["armor_lowest_cm"] = round(low_at[0], 1)
    return out


# ---------------------------------------------------------------------------- movimiento
ARM_BONES = ("Brazo.R", "Antebrazo.R", "Mano.R", "Brazo.L", "Antebrazo.L", "Mano.L")
SNAP_DEG = 45.0             # el mango, por cuadro, fuera del golpe
POP_DEG, POP_SPIKE = 45.0, 30.0
HEAD_DROP_M = 0.25          # FakeDefeat: lo más que cae la cabeza en un cuadro
_LAST = {}                  # pose final de cada clip ya medido (FakeDefeat -> ArmorRise)


def _free_frames(clip):
    """Cuadros en que un giro rápido es legítimo: el golpe (apex .. último activo + 2) y timing['swing_ok']."""
    t = clip.timing
    ok = set()
    if "contact" in t:
        ok.update(range(t["apex"], t.get("active", [t["contact"], t["contact"] + 2])[1] + 3))
    for a, b in t.get("swing_ok", []):
        ok.update(range(a, b + 1))
    return ok


def _local_rots(ch):
    out = {}
    for n in ARM_BONES:
        pb = ch.arm.pose.bones.get(n)
        if pb is None:
            continue
        M = pb.parent.matrix.inverted() @ pb.matrix if pb.parent else pb.matrix
        out[n] = M.to_quaternion()
    return out


def motion_checks(ch, clip, first, check):
    """Ver el docstring del módulo. Devuelve lo que va al sidecar (y en FakeDefeat ajusta el evento 'hammer_land')."""
    import math
    scn = bpy.context.scene
    w = ch.weapon_info
    B = ch.spec["weapon"]["bone"]
    ham = bpy.data.objects[ch.spec["weapon"]["mesh"]]
    free = _free_frames(clip)
    loop = clip.loop
    axes, rots, heads, handle_low = [], [], [], []
    hm = ham.data
    for f in range(clip.frames + 1):
        scn.frame_set(first + f)
        pb = ch.arm.pose.bones[B]
        axes.append((pb.matrix.to_3x3() @ Vector((0.0, 1.0, 0.0))).normalized())
        rots.append(_local_rots(ch))
        hb = ch.arm.pose.bones.get("Cabeza")
        heads.append(ch.Pc(hb.tail).z if hb else 0.0)
        if clip.name == "FakeDefeat":
            dg = bpy.context.evaluated_depsgraph_get()
            Mh = ch.Ai @ ham.evaluated_get(dg).matrix_world
            base = pb.matrix.translation
            ax = axes[-1]
            low = 9.0
            for v in hm.vertices:
                q = Mh @ v.co
                if (q - base).dot(ax) / ch.u < w["head_center"] - 0.6:
                    low = min(low, ch.Pc(q).z)
            handle_low.append(low)
    out = {}
    # el mango
    snap, at = 0.0, -1
    for f in range(1, len(axes)):
        if f in free:
            continue
        a = math.degrees(axes[f - 1].angle(axes[f], 0.0))
        if a > snap:
            snap, at = a, f
    out["hammer_turn_max_deg"] = round(snap, 1)
    check(snap <= SNAP_DEG, f"{clip.name}: el martillo no da vueltas de golpe ({snap:.0f}° en f{at - 1}-f{at} fuera del golpe, tope {SNAP_DEG:.0f})")
    # tics del brazo
    bad, txt = 0.0, ""
    n = len(rots)
    for bn in ARM_BONES:
        dl = [0.0] + [math.degrees(rots[i - 1][bn].rotation_difference(rots[i][bn]).angle) for i in range(1, n) if bn in rots[i]]
        dl = [min(d, 360.0 - d) for d in dl]
        for i in range(1, len(dl)):
            if i in free or (not loop and i <= 2) or dl[i] <= POP_DEG:
                continue
            nb = [dl[j] for j in (i - 1, i + 1) if 1 <= j < len(dl)]
            spike = dl[i] - max(nb, default=0.0)
            if spike > POP_SPIKE and spike > bad:
                bad, txt = spike, f"{bn} f{i - 1}-f{i}: {dl[i]:.0f}°, vecinos {', '.join(f'{x:.0f}' for x in nb)}°"
    out["arm_pop_deg"] = round(bad, 1)
    check(bad == 0.0, f"{clip.name}: brazos sin tics fuera del golpe ({txt or 'ok'})")
    if clip.name == "FakeDefeat":
        drop, df = 0.0, -1
        for f in range(1, len(heads)):
            d = heads[f - 1] - heads[f]
            if d > drop:
                drop, df = d, f
        out["head_drop_max_m"] = round(drop, 3)
        check(drop <= HEAD_DROP_M, f"FakeDefeat: la cabeza cae con el peso, sin teletransporte ({drop * 100:.0f} cm en f{df - 1}-f{df}, "
                                   f"tope {HEAD_DROP_M * 100:.0f})")
        ev = clip.timing.setdefault("events", {})
        f0 = ev.get("drop", 0)
        rest = min(handle_low[f0:])
        land = next((f for f in range(f0, len(handle_low)) if handle_low[f] <= rest + 0.02), None)
        check(land is not None and rest < 0.25, f"FakeDefeat: el mango llega al piso (más bajo {rest * 100:.0f} cm, en f{land})")
        if land is not None:
            ev["hammer_land"] = land
            out["hammer_land_frame"] = land
        out["head_height_m"] = [round(h, 2) for h in heads]
    # FakeDefeat -> ArmorRise: la misma pose (todos los huesos)
    scn.frame_set(first + clip.frames)
    last = {pb.name: pb.matrix.to_quaternion() for pb in ch.arm.pose.bones}
    _LAST[clip.name] = last
    if clip.name == "ArmorRise" and "FakeDefeat" in _LAST:
        scn.frame_set(first)
        cur = {pb.name: pb.matrix.to_quaternion() for pb in ch.arm.pose.bones}
        prev = _LAST["FakeDefeat"]
        worst, who = 0.0, ""
        for k, q in cur.items():
            if k in prev and not k.startswith("Acc_"):
                d = math.degrees(prev[k].rotation_difference(q).angle)
                d = min(d, 360.0 - d)
                if d > worst:
                    worst, who = d, k
        out["chain_from_fakedefeat_deg"] = round(worst, 1)
        # GoroBoss los encadena con un fundido de 0.2 s: hasta 20° no se ve
        check(worst <= 20.0, f"ArmorRise f0 = FakeDefeat f{_LAST_FRAMES.get('FakeDefeat', '?')} (peor {who} {worst:.1f}°, tope 20 con el fundido de 0.2 s)",
              warn=worst <= 35.0)
    _LAST_FRAMES[clip.name] = clip.frames
    return out


_LAST_FRAMES = {}
