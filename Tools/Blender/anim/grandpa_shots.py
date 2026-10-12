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
        for label, pos, look, fov in CAMS.get(clip.name, []):
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
                p = os.path.join(OUT, f"_{clip.name}_{label}_{f:03d}.png")
                NA.render(scn, p)
                tiles.append({"img": p, "label": f"f{f}"})
            rows.append({"label": f"{clip.name} · {label} (el abuelo ~{px:.0f} px a 1080p)", "tiles": tiles})
    out = os.path.join(OUT, "grandpa_shots_" + "_".join(ONLY) + ".png")
    rv.sheet({"out": out, "title": "abuelo: planos de las escenas", "width": 1280, "tile_h": 200, "rows": rows, "delete": True})
    print("SHEET", out)


main()
