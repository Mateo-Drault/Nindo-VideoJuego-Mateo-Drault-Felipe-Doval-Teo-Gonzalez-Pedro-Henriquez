"""Hojas de los clips del abuelo con las cámaras de las escenas que los usan (no la del juego): el plano que sigue al
secuestro en StoryDirector.Intro, el contraplano por encima del hombro de Kaito (WakeOverShoulderShot, a 17 m), el
plano del bosque (ForestReveal) y un costado cerrado para juzgar los contactos.

  blender -b --factory-startup --python Tools/Blender/anim/grandpa_shots.py -- SALIDA [Clip,Clip...]

El transform del NPC 'kidnap' mira hacia donde lo arrastran (+Y del mundo de la hoja; el abuelo mira a -Y, hacia
Kaito); las cámaras salen de los offsets del código pasados a ese transform. Sin el avance del transform: los planos
lo siguen. Un número por hoja: lo que mide el abuelo en pantalla a 1080p.
"""
import bpy, sys, os, math, json
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import nindo_anim as NA        # noqa: E402
import team_rig as T           # noqa: E402
import team_review as TR       # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = argv[0]
ONLY = argv[1].split(",") if len(argv) > 1 else ["Kidnap", "Dragged"]
os.makedirs(OUT, exist_ok=True)

# (nombre, posición, mira, fov vertical): StoryDirector.Intro shot2 = PlayFollowShot(offset mundo (-3.5, 3.2, -6), mira 1 m,
# fov 32) con el transform mirando a kidnap_exit (de (-14,-150) a (6,-128)); el bosque: (-5, 4.5, -7), 1 m, 34, de
# forest_kidnap_a a _b; Kaito a 17 m detrás del abuelo, la cámara 2.3 m detrás de él, 0.85 al costado, 1.35 de alto
CAMS = {
    "Kidnap": [("prologo", (1.45, -6.8, 3.2), (0, 0, 1.0), 32.0), ("prologo B", (4.6, -3.4, 2.4), (0, 0.35, 0.7), 32.0), ("ojos de Kaito", (0.85, -19.3, 1.35), (0, 0, 0.9), 28.0),
               ("costado", (3.2, 0.3, 1.0), (0.2, 0.3, 0.55), 30.0)],
    "Dragged": [("prologo", (1.45, -6.8, 3.2), (0, 0, 1.0), 32.0), ("prologo B", (4.6, -3.4, 2.4), (0, 0.35, 0.7), 32.0),
                ("bosque", (-6.08, -6.08, 4.5), (0, 0, 1.0), 34.0), ("bosque B", (5.5, -5.0, 3.6), (0, 0.35, 0.7), 34.0),
                ("costado", (3.2, 0.3, 1.0), (0.2, 0.3, 0.55), 30.0)],
    "Bound": [("final", (3.6, -4.2, 1.9), (0, 0, 0.7), 34.0), ("costado", (3.4, 0.0, 0.75), (0, 0.0, 0.6), 30.0)],
    "Freed": [("final", (3.6, -4.2, 1.9), (0, 0, 0.8), 34.0), ("costado", (3.4, 0.0, 0.75), (0, 0.0, 0.6), 30.0)],
}
# la cámara del juego (pitch 52°, a 24 m, FOV 30: el abuelo parado ~100 px a 1080p), de 3/4 por delante y por detrás,
# a tamaño real y a 3x (el recorte con que se juzga la silueta)
def game_cam(az, zoom=1.0, look=(0.0, 0.0, 0.5)):
    pit, d = math.radians(52.0), 24.0
    x, y = math.sin(math.radians(az)) * math.cos(pit) * d, -math.cos(math.radians(az)) * math.cos(pit) * d
    return (look[0] + x, look[1] + y, look[2] + math.sin(pit) * d), look, 30.0 / zoom


GAME = [("juego 3/4 adelante", *game_cam(35.0)), ("juego 3/4 adelante x3", *game_cam(35.0, 3.0)),
        ("juego 3/4 atrás x3", *game_cam(150.0, 3.0))]
for _c in ("Bound", "Freed"):
    CAMS[_c] = CAMS[_c] + GAME
CAMS["BoundStruggle"] = CAMS["Bound"]
CAMS["Dragged"] = CAMS["Dragged"] + [("juego x3", *game_cam(70.0, 3.0, (0.2, 0.4, 0.5)))]
CAMS["KidnapWait"] = [("prologo B", (4.6, -3.4, 2.4), (0, 0.35, 0.7), 32.0), ("ojos de Kaito", (0.85, -19.3, 1.35), (0, 0, 0.9), 28.0)]
POST_CLIPS = ("Bound", "BoundStruggle", "Freed")
ROPES = []      # las cuerdas de la réplica (en Freed ya se deshicieron)


def verts(ch, o, dg, skip):
    """Vértices de una malla deformada en el marco de autoría del abuelo (m), sin los que pesan en 'skip'."""
    import numpy as np
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    oe.to_mesh_clear()
    M = np.array(oe.matrix_world)
    w = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    c = (w - np.array(ch.O)) @ np.array(ch.Rcw) / ch.u
    key = (o.name, frozenset(skip))
    if key not in _KEEP:
        _KEEP[key] = np.array([not any(o.vertex_groups[g.group].name in skip and g.weight > 0.3 for g in v.groups)
                               for v in o.data.vertices])
    return c[_KEEP[key]]


_KEEP = {}


def clearance(ch, clip, first):
    """Lo que el cuerpo del abuelo y el del ninja se acercan (sin las manos ni los antebrazos izquierdos, que se agarran)
    y, en los clips del poste, lo que el abuelo se mete en el poste y en su zócalo (binding_post: zócalo de 0.8 m y 0.24 m
    de alto centrado 0.5 m detrás del marcador, poste de 0.3 m; NPC.KneelBound adelanta el transform KNEEL_FWD)."""
    import numpy as np
    scn = bpy.context.scene
    body = next(o for o in ch.meshes if o.name.startswith("Cuerpo"))
    kidm = next((o for o in ch.meshes if o.name.startswith("Cube")), None)
    hands = set()
    for c in (ch, ch.partner):
        for b in ch.rig.names:
            p = b
            while p is not None and p not in (c.side["l"]["fore"],):
                p = ch.rig.parent.get(p)
            if p is not None:
                hands.add(b)
    worst, worst_f, post = 9.0, 0, []
    duo = getattr(clip, "partner", None) is not None
    for f in range(clip.frames + 1):
        scn.frame_set(first + f)
        dg = bpy.context.evaluated_depsgraph_get()
        g = verts(ch, body, dg, hands if duo else set())
        if duo and kidm is not None:
            k = verts(ch, kidm, dg, hands)
            # rejilla de 8 cm: cada vértice del abuelo contra los del ninja de su celda y las vecinas
            cell = {}
            for i, p in enumerate(np.floor(k / 0.08).astype(int)):
                cell.setdefault(tuple(p), []).append(i)
            best = 9.0
            for p, q in zip(np.floor(g / 0.08).astype(int), g):
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        for dz in (-1, 0, 1):
                            idx = cell.get((p[0] + dx, p[1] + dy, p[2] + dz))
                            if idx:
                                best = min(best, float(np.min(np.linalg.norm(k[idx] - q, axis=1))))
            if best < worst:
                worst, worst_f = best, f
        else:
            import team_clips_grandpa as G
            low = g[(np.abs(g[:, 0]) < 0.4) & (g[:, 2] < 0.24)]
            base_in = float(low[:, 1].max()) - (0.1 + G.KNEEL_FWD) if len(low) else -1.0
            post_in = bool(((np.abs(g[:, 0]) < 0.15) & (np.abs(g[:, 1] - 0.5 - G.KNEEL_FWD) < 0.15)).any())
            if base_in > 0.0 or post_in:
                post.append((f, round(base_in * 100.0, 1), post_in))
    if duo:
        print(f"CLEAR {clip.name}: lo más cerca que pasan los cuerpos (sin las manos que se agarran) {worst * 100:.1f} cm en f{worst_f}")
    else:
        print(f"CLEAR {clip.name}: el abuelo dentro del zócalo (cm) o del poste en {len(post)} cuadros; peor "
              f"{max(post, key=lambda r: r[1]) if post else None}; {post[::10]}")


def post_and_ropes(ch, rv, first):
    """El binding_post (zócalo, escalón y poste) y una réplica de ShadowRopes.BuildWraps con los huesos de Bound f0: lo
    que se ve en la arena. El poste está 0.5 m detrás del marcador y el transform, KNEEL_FWD adelante."""
    import team_clips_grandpa as G
    py = 0.5 + G.KNEEL_FWD
    mat = rv.look.build("rv_post", albedo_rgb=(0.2, 0.17, 0.14))
    for size, z in (((0.8, 0.8, 0.24), 0.12), ((0.5, 0.5, 0.08), 0.26), ((0.3, 0.3, 2.5), 1.53)):
        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, py, z))
        o = bpy.context.active_object
        o.scale = size
        o.data.materials.append(mat)
    scn = bpy.context.scene
    scn.frame_set(first)
    bpy.context.view_layer.update()
    pb = ch.arm.pose.bones
    B = lambda n: ch.Pc(pb[n].head)
    hl, hr, el, er, sl, sr, hip = (B(n) for n in ("Mano.L", "Mano.R", "Antebrazo.L", "Antebrazo.R", "Brazo.L", "Brazo.R", "Root"))
    post = Vector((0.0, py, 0.0))
    axis, side = Vector((0.0, -1.0, 0.0)), Vector((1.0, 0.0, 0.0))
    RopeR, Gap, PostR, HalfD, Limb, HW = 0.027, 0.03, 0.16, 0.12, 0.05, 0.21
    wrist, sh = (hl + hr) * 0.5, (sl + sr) * 0.5
    zW, zE, zC = wrist.z, (el.z + er.z) * 0.5, sh.z - 0.05
    if zC - zE < 0.08:          # ShadowRopes.MinLoopGap
        zE = (zW + zC) * 0.5
    shalf = abs((sl - sr).dot(side)) * 0.5

    def at(z):
        k = (z - hip.z) / (sh.z - hip.z)
        return hip.lerp(sh, k)

    def circle(o, c, r, n):
        o += [(c.x + math.cos(i * 2 * math.pi / n) * r, c.y + math.sin(i * 2 * math.pi / n) * r) for i in range(n)]

    def hull(pts):
        pts = sorted(set(pts))
        cr = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
        lo, up = [], []
        for q in pts:
            while len(lo) >= 2 and cr(lo[-2], lo[-1], q) <= 0:
                lo.pop()
            lo.append(q)
        for q in reversed(pts):
            while len(up) >= 2 and cr(up[-2], up[-1], q) <= 0:
                up.pop()
            up.append(q)
        return lo[:-1] + up[:-1]
    rmat = rv.look.build("rv_rope", albedo_rgb=(0.25, 0.08, 0.45), emission_rgb=(0.45, 0.2, 0.9))

    def tube(points, r, closed):
        cu = bpy.data.curves.new("rope", "CURVE")
        cu.dimensions = "3D"
        cu.bevel_depth = r
        cu.bevel_resolution = 1
        sp = cu.splines.new("POLY")
        sp.points.add(len(points) - 1)
        for i, q in enumerate(points):
            sp.points[i].co = (q[0], q[1], q[2], 1.0)
        sp.use_cyclic_u = closed
        o = bpy.data.objects.new("rope", cu)
        o.data.materials.append(rmat)
        scn.collection.objects.link(o)
        ROPES.append(o)
    for k, z in enumerate((zW, zE, zC)):
        t = at(z)
        pts = []
        circle(pts, post, PostR + Gap, 12)
        hw = (shalf + Limb + 0.02) if k == 2 else min(HW, shalf)
        pts += [(t.x + side.x * math.cos(a) * (hw + Gap) + axis.x * math.sin(a) * (HalfD + Gap),
                 t.y + side.y * math.cos(a) * (hw + Gap) + axis.y * math.sin(a) * (HalfD + Gap))
                for a in (i * 2 * math.pi / 16 for i in range(16))]
        if k == 0:
            circle(pts, wrist, Limb + Gap, 8)
        if k == 1:
            circle(pts, el, Limb + Gap, 8)
            circle(pts, er, Limb + Gap, 8)
        tube([(x, y, z) for x, y in hull(pts)], RopeR, True)
    across = (hl - hr).normalized()
    a1 = across.cross(Vector((0, 0, 1))).normalized()
    a2 = across.cross(a1)
    for w in (0.02, -0.02):
        o = wrist + across * w
        tube([tuple(o + (a1 * math.cos(i * 2 * math.pi / 10) + a2 * math.sin(i * 2 * math.pi / 10)) * (Limb + 0.005)) for i in range(10)], 0.02, True)
    ch_, md = at(zC), at(zE)
    fC, w2 = HalfD + Gap, shalf * 0.75
    tube([tuple(ch_ + axis * fC + side * w2), tuple(md + axis * fC - side * w2)], 0.024, False)
    tube([tuple(ch_ + axis * fC - side * w2), tuple(md + axis * fC + side * w2)], 0.024, False)
    print(f"CUERDAS alturas muñecas {zW:.3f} codos {zE:.3f} pecho {zC:.3f}; medio ancho de hombros {shalf:.3f}; muñecas "
          f"a {wrist.y:.3f} (poste a {py - 0.15:.3f})")


def main():
    ch = T.TeamChar("grandpa", T.CHARS["grandpa"])
    import team_clips_grandpa as G
    clips = [c for c in G.clips(ch) if c.name in ONLY]
    solver = T.TeamSolver(ch)
    baked = []
    for clip in clips:
        frames, *_ = T.bake(ch, clip, solver)
        baked.append((clip, frames))
    _, ranges = NA.write_pack(ch.arm, ch.rig, baked, start=1, gap=10)
    for clip in clips:
        clearance(ch, clip, ranges[clip.name][0])
    rv = TR.Review(ch, OUT, partner=any(getattr(c, "partner", None) is not None for c in clips))
    rv.show_kaito(False)
    rv.face(0.0)
    posted = [c for c in clips if c.name in POST_CLIPS]
    if posted:
        first = ranges["Bound"][0] if "Bound" in ranges else ranges[posted[0].name][0]
        post_and_ropes(ch, rv, first)
    scn = rv.scn
    scn.render.resolution_x, scn.render.resolution_y = 960, 540
    cam = rv.cam
    cam.data.type = 'PERSP'
    cam.data.sensor_fit = 'VERTICAL'
    cam.data.clip_start, cam.data.clip_end = 0.1, 300.0
    rows = []
    for clip in clips:
        first = ranges[clip.name][0]
        fs = clip.timing.get("sheet") or list(range(0, clip.frames + 1, max(1, clip.frames // 8)))
        for o in ROPES:
            o.hide_render = clip.name == "Freed"
        for ci, (label, pos, look, fov) in enumerate(CAMS.get(clip.name, [])):
            cam.location = Vector(pos)
            cam.rotation_euler = (Vector(look) - Vector(pos)).to_track_quat('-Z', 'Y').to_euler()
            cam.data.angle_y = math.radians(fov)
            rv.look.set_moon()
            # alto del abuelo en pantalla (1080p): 1.45 m a la distancia de la mira
            dist = (Vector(look) - Vector(pos)).length
            px = 1.45 / (2.0 * dist * math.tan(math.radians(fov) * 0.5)) * 1080.0
            tiles = []
            for f in fs:
                scn.frame_set(first + f)
                # el plano por número: su nombre lleva '3/4' y la ruta del scratch ya roza los 260 caracteres de Windows
                p = os.path.join(OUT, f"_{clip.name}_{ci}_{f:03d}.png")
                NA.render(scn, p)
                tiles.append({"img": p, "label": f"f{f}"})
            rows.append({"label": f"{clip.name} · {label} (el abuelo ~{px:.0f} px a 1080p)", "tiles": tiles})
    out = os.path.join(OUT, "grandpa_shots_" + "_".join(ONLY) + ".png")
    rv.sheet({"out": out, "title": "abuelo: planos de las escenas", "width": 1280, "tile_h": 200, "rows": rows, "delete": True})
    print("SHEET", out)


main()
