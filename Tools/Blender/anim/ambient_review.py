"""Revisión de los idles ambientales (team_ambient): hojas con la cámara del juego y mediciones que build_team_anims no
puede hacer porque miran DOS cosas a la vez (la roca del que medita, la pareja que practica).

  blender -b --factory-startup --python Tools/Blender/anim/ambient_review.py -- <ninja|sumo> --out DIR
          [--clips A,B] [--frames Clip:0,10,20;Otro:5] [--yaw GRADOS]

Por clip: una fila con la cámara del juego a la escala de 1080p (la de 1280x720 con el FOV recortado: misma
perspectiva, 84 px por metro) y otra de 3/4 más cerca. Con IdleMeditate / AmbientAlert del ninja pone la roca de
EnemyAmbient (rock_small_a escalada) y mide la cola contra su cara de arriba; con IdleSparA pone al compañero (IdleSparB
a SPAR_GAP m, girado 180°) y mide, en los cuadros del choque, la distancia entre las dos hojas y si alguna atraviesa el
cuerpo del otro. Escribe ambient_<personaje>.json con las medidas.
"""
import sys, os, json, math, importlib
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for p in (HERE, os.path.join(ROOT, "Tools", "Blender"), os.path.join(ROOT, "Tools", "Blender", "characters")):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True
import bpy
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view
import nindo_anim as NA
import team_rig as T
import team_review as TR
import team_ambient as AMB

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
CHAR = argv[0]


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


OUT = opt("--out")
ONLY = opt("--clips")
YAW = float(opt("--yaw", "35"))
TILE = int(opt("--tile", "190"))
ROCK_FBX = os.path.join(ROOT, "Nindo", "Assets", "Nindo", "Art", "Models", "Props", AMB.ROCK_ID + ".fbx")
# 1280x720 con el FOV que deja 84 px por metro a 24 m, como el juego en 1080p con FOV 30 (la misma cámara, recortada)
GAME_FOV = math.degrees(2.0 * math.atan(math.tan(math.radians(15.0)) * 720.0 / 1080.0))


def frames_opt():
    out = {}
    s = opt("--frames")
    if s:
        for part in s.split(";"):
            n, fs = part.split(":")
            out[n] = [int(x) for x in fs.split(",")]
    return out


def mesh_points(objs, dg):
    pts = []
    for o in objs:
        if o.hide_render:
            continue
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        M = oe.matrix_world
        pts += [M @ v.co for v in me.vertices]
        oe.to_mesh_clear()
    return pts


def import_rock(rv):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=ROCK_FBX)
    new = [o for o in bpy.data.objects if o not in before]
    piv = bpy.data.objects.new("RockPivot", None)
    rv.scn.collection.objects.link(piv)
    mat = rv.look.build("rv_rock", albedo_rgb=(0.36, 0.37, 0.4))
    for o in new:
        if o.parent is None:
            o.parent = piv
        if o.type == 'MESH':
            o.data.materials.clear()
            o.data.materials.append(mat)
    # la escala de EnemyAmbient (Unity x, y, z = ancho, alto, fondo) pasada a Blender (x, z, y)
    sx, sy, sz = AMB.ROCK_SCALE
    piv.scale = (sx, sz, sy)
    piv.parent = rv.piv
    piv.location = (0.0, AMB.SEAT_BACK, 0.0)
    return piv, [o for o in new if o.type == 'MESH']


class Partner:
    """Una copia del personaje (armadura y mallas compartiendo los datos) con su propia acción y su pivote."""

    def __init__(self, rv, ch):
        self.arm = ch.arm.copy()
        rv.scn.collection.objects.link(self.arm)
        self.arm.animation_data_clear()
        self.meshes = []
        for o in ch.meshes:
            c = o.copy()
            rv.scn.collection.objects.link(c)
            for m in c.modifiers:
                if m.type == 'ARMATURE':
                    m.object = self.arm
            if c.parent == ch.arm:
                c.parent = self.arm
            self.meshes.append(c)
        self.piv = bpy.data.objects.new("PartnerPivot", None)
        rv.scn.collection.objects.link(self.piv)
        self.arm.parent = self.piv
        self.arm.matrix_parent_inverse = ch.arm.matrix_parent_inverse.copy()

    def place(self, rv, gap):
        """El compañero 'gap' m delante del personaje y mirándolo (girado 180°), en el mismo giro de la revisión."""
        R = Matrix.Rotation(math.radians(rv.yaw), 4, 'Z')
        self.piv.matrix_world = R @ Matrix.Translation((0.0, -gap, 0.0)) @ Matrix.Rotation(math.pi, 4, 'Z')


def blade_segment(ch, W, arm_obj):
    """Punta y pomo de la katana en el mundo de Blender en la pose W (espacio de la armadura de 'arm_obj')."""
    w = ch.weapon_info
    B = W[ch.spec["weapon"]["bone"]]
    tip = arm_obj.matrix_world @ (B @ w["tip_local"])
    Fk = B.to_3x3().normalized() @ w["KB"].transposed()
    base = arm_obj.matrix_world @ (B.translation - Fk @ w["hb"])
    return base, tip


def seg_dist(p1, q1, p2, q2):
    """Distancia mínima entre dos segmentos y los parámetros (0..1) del punto más cercano de cada uno."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1.dot(d1), d2.dot(d2), d2.dot(r)
    c = d1.dot(r)
    b = d1.dot(d2)
    den = a * e - b * b
    s = max(0.0, min(1.0, (b * f - c * e) / den)) if den > 1e-9 else 0.0
    t = (b * s + f) / e
    if t < 0.0:
        t, s = 0.0, max(0.0, min(1.0, -c / a))
    elif t > 1.0:
        t, s = 1.0, max(0.0, min(1.0, (b - c) / a))
    return ((p1 + d1 * s) - (p2 + d2 * t)).length, s, t


def main():
    os.makedirs(OUT, exist_ok=True)
    ch = T.TeamChar(CHAR, T.CHARS[CHAR])
    mod = importlib.import_module("team_clips_" + CHAR)
    clips = mod.clips(ch)
    want = ONLY.split(",") if ONLY else [c.name for c in clips if c.timing.get("ambient")]
    if "IdleSparA" in want and "IdleSparB" not in want:
        want.append("IdleSparB")
    clips = [c for c in clips if c.name in want]
    solver = T.TeamSolver(ch)
    baked = []
    for clip in clips:
        frames, ctrls, roots, drops, misses = T.bake(ch, clip, solver)
        baked.append((clip, frames))
        print(f"[{clip.name}] horneado, {clip.frames} cuadros")
    act, ranges = NA.write_pack(ch.arm, ch.rig, baked, start=1, gap=10)
    by = {c.name: (c, fr) for c, fr in baked}
    rv = TR.Review(ch, OUT, kaito=False)
    scn = rv.scn
    scn.render.resolution_x, scn.render.resolution_y = 1280, 720
    rock, rock_meshes = (import_rock(rv) if CHAR == "ninja" else (None, []))
    partner = None
    if "IdleSparA" in by:
        partner = Partner(rv, ch)
        ca, fa = by["IdleSparA"]
        cb, fb = by["IdleSparB"]
        NA.write_pack(partner.arm, ch.rig, [(cb, fb)], start=ranges["IdleSparA"][0], gap=10)
    report = {}
    fsel = frames_opt()
    dg = bpy.context.evaluated_depsgraph_get

    def subject(clip):
        objs = list(ch.meshes) + (rock_meshes if clip.timing.get("ambient", "").endswith("meditate") else [])
        if partner is not None and clip.name == "IdleSparA":
            objs += partner.meshes
        return objs

    for clip, frames in baked:
        if clip.name == "IdleSparB":
            continue
        first = ranges[clip.name][0]
        med = clip.timing.get("ambient", "").endswith("meditate")
        for o in rock_meshes:
            o.hide_render = not med
        for o in (partner.meshes if partner else []):
            o.hide_render = clip.name != "IdleSparA"
        fs = fsel.get(clip.name) or clip.timing.get("sheet") or sorted(set(range(0, clip.frames + 1, max(1, clip.frames // 8))))
        rep = report.setdefault(clip.name, {})
        # ---- medidas
        if med and rock is not None:
            # lo más bajo del personaje que cae sobre la huella de la roca (la cola) contra la cara de arriba
            rows = []
            for f in range(0, clip.frames + 1, 2):
                scn.frame_set(first + f)
                bpy.context.view_layer.update()
                rp = mesh_points(rock_meshes, dg())
                top = max(p.z for p in rp)
                xs, ys = [p.x for p in rp], [p.y for p in rp]
                lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
                cp = []
                for o in ch.meshes:
                    oe = o.evaluated_get(dg())
                    me = oe.to_mesh()
                    for v in me.vertices:
                        p = oe.matrix_world @ v.co
                        if lo_x + 0.05 < p.x < hi_x - 0.05 and lo_y + 0.05 < p.y < hi_y - 0.05:
                            cp.append((p.z, o, v.index))
                    oe.to_mesh_clear()
                low, lo_o, lo_i = min(cp, key=lambda r: r[0], default=(9.0, None, 0))
                # qué se mete en la roca (el hueso que más pesa en el vértice más bajo)
                part = ""
                if lo_o is not None and low < top - 0.02:
                    gs = lo_o.data.vertices[lo_i].groups
                    part = lo_o.vertex_groups[max(gs, key=lambda g: g.weight).group].name if len(gs) else lo_o.name
                rows.append((f, round((low - top) * 100.0, 1), part))
            rep["seat_gap_cm"] = rows
            print(f"  {clip.name}: cola - cara de la roca (cm): " + " ".join(f"f{f}:{g}{'(' + w + ')' if w else ''}" for f, g, w in rows))
        if clip.name == "IdleSparA" and partner is not None:
            rows = []
            for f in range(clip.frames + 1):
                scn.frame_set(first + f)
                bpy.context.view_layer.update()
                partner.place(rv, AMB.SPAR_GAP)
                bpy.context.view_layer.update()
                a0, a1 = blade_segment(ch, frames[f], ch.arm)
                b0, b1 = blade_segment(ch, by["IdleSparB"][1][f], partner.arm)
                d, s, t = seg_dist(a0, a1, b0, b1)
                rows.append((f, round(d * 100.0, 1), round(s, 2), round(t, 2)))
            rep["blade_gap_cm"] = rows
            for f in AMB.SPAR_CLASH:
                r = rows[f]
                print(f"  choque f{f}: hojas a {r[1]} cm (A en {r[2]:.2f} de su largo, B en {r[3]:.2f})")
            # lo más cerca que pasan las hojas fuera de los choques (que no se crucen en el aire)
            print("  hojas, mínimo por cuadro (cm):", " ".join(f"{f}:{d}" for f, d, _, _ in rows if f % 3 == 0))
            # la hoja de cada uno contra el cuerpo del otro (puntos de la malla a menos de 3 cm del segmento)
            hits = []
            for f in range(0, clip.frames + 1, 2):
                scn.frame_set(first + f)
                bpy.context.view_layer.update()
                partner.place(rv, AMB.SPAR_GAP)
                bpy.context.view_layer.update()
                a0, a1 = blade_segment(ch, frames[f], ch.arm)
                b0, b1 = blade_segment(ch, by["IdleSparB"][1][f], partner.arm)
                body_b = [p for o in partner.meshes if o.vertex_groups for p in mesh_points([o], dg())]
                body_a = [p for o in ch.meshes if o.vertex_groups for p in mesh_points([o], dg())]
                for nm, (p0, p1), body in (("A->B", (a0, a1), body_b), ("B->A", (b0, b1), body_a)):
                    dmin = min(seg_dist(p0, p1, q, q + Vector((0, 0, 1e-4)))[0] for q in body[::3])
                    if dmin < 0.03:
                        hits.append((f, nm, round(dmin * 100, 1)))
            rep["blade_body_hits"] = hits
            print("  hoja contra el cuerpo del otro (<3 cm):", hits or "ninguna")
        # ---- hojas
        rows = []
        for view, dist, fov in (("juego 1:1 (1080p)", 24.0, GAME_FOV), ("3/4 de cerca", 9.0, 30.0), ("perfil", 0.0, 0.0)):
            # la pareja, en el juego, practica sobre la horizontal de la pantalla (EnemyAmbient.PairSpot): de perfil
            spar_side = clip.name == "IdleSparA" and view.startswith("juego")
            rv.face(YAW if view.startswith("3/4") else 90.0 if view == "perfil" or spar_side else 0.0)
            if partner is not None:
                partner.place(rv, AMB.SPAR_GAP)
            tiles = []
            # una caja para toda la fila: se ve cuánto se mueve
            lo_x, hi_x, lo_y, hi_y = 1, 0, 1, 0
            focus = Vector((0.0, -AMB.SPAR_GAP * 0.5 if clip.name == "IdleSparA" else 0.0, 0.7))
            focus = Matrix.Rotation(math.radians(rv.yaw), 3, 'Z') @ focus
            if view == "perfil":
                hgt = ch.spec["height"]
                NA.ortho_camera(rv.cam, (0.0, 0.0, hgt * 0.47), hgt * 1.5 if clip.name != "IdleSparA" else 3.4, azimuth=0.0, elevation=8.0)
                rv.look.set_moon(Vector((0.5, -0.7, 0.6)), scale=1.0)
            else:
                NA.game_camera(rv.cam, focus, pitch=52.0, dist=dist, fov=fov)
                rv.look.set_moon()
            for f in fs:
                scn.frame_set(first + f)
                bpy.context.view_layer.update()
                for p in mesh_points(subject(clip), dg())[::4]:
                    u = world_to_camera_view(scn, rv.cam, p)
                    lo_x, hi_x, lo_y, hi_y = min(lo_x, u.x), max(hi_x, u.x), min(lo_y, u.y), max(hi_y, u.y)
            m = 0.02
            box = (max(0.0, lo_x - m), min(1.0, hi_x + m), max(0.0, lo_y - m), min(1.0, hi_y + m))
            for f in fs:
                scn.frame_set(first + f)
                p = os.path.join(OUT, f"_{clip.name}_{view[0]}_{f:03d}.png")
                rv.render_framed(p, box)
                tiles.append({"img": p, "label": f"f{f}"})
            rows.append({"label": view, "tiles": tiles})
        out = os.path.join(OUT, f"amb_{CHAR}_{clip.name}.png")
        rv.sheet({"out": out, "title": f"{CHAR} · {clip.name} · {clip.frames} cuadros ({clip.frames / NA.FPS:.2f} s)",
                  "width": 1280, "tile_h": TILE, "rows": rows, "delete": True})
        print("HOJA", out)
    json.dump(report, open(os.path.join(OUT, f"ambient_{CHAR}.json"), "w", encoding="utf-8"), indent=0)


main()
