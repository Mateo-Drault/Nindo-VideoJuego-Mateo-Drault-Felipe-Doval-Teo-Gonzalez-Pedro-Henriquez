"""Las rocas de la avalancha de Gorō (fase 2): un prop 'goro_boulders' con tres rocas para rodar y cuatro pedazos.

    "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --python Tools/Blender/bosses/goro/build_goro_boulders.py -- [--export] [--preview DIR]

Las rocas del mundo (props_nature.build_rock) son lajas chatas apoyadas en el piso: rodando se leían como platos. Estas
son cascos convexos de puntos sobre una esfera achatada al azar (granito facetado como la armadura, con manchas de nieve
pegada: bajan de la pared nevada de la cumbre), centradas en el origen para girar sobre su centro. Miden 1 m de diámetro;
GoroAvalanche las escala a 2r (r = 0.75-0.9 m). Los pedazos ('Shard_*') también miden 1 m y se escalan al romperse.

El FBX lleva todos los objetos juntos (Boulder_A..C, Shard_A..D): GoroAvalanche toma las mallas del prefab por nombre.
Sin colisión (no las toca la física: el rodar es cuenta propia).
"""
import bpy, math, os, sys, random
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BL = os.path.abspath(os.path.join(HERE, "..", ".."))
REPO = os.path.abspath(os.path.join(BL, "..", ".."))
for _p in (BL, os.path.join(BL, "props")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import nindo_lib as L          # noqa: E402
import props_nature as N       # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
EXPORT = "--export" in argv
PREVIEW = argv[argv.index("--preview") + 1] if "--preview" in argv else None
OUT_FBX = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Art", "Models", "Props", "goro_boulders.fbx")

TAU = 2 * math.pi


def sphere_pts(rng, n, radius, squash, jitter):
    """n puntos en espiral de Fibonacci sobre una esfera (achatada en z por 'squash'), con el radio movido al azar:
    el casco sale facetado e irregular pero redondo (rueda sin trabarse)."""
    pts = []
    off = rng.uniform(0, TAU)
    for i in range(n):
        z = 1 - 2 * (i + 0.5) / n
        r = math.sqrt(max(0.0, 1 - z * z))
        a = off + i * math.pi * (3 - math.sqrt(5))
        k = radius * rng.uniform(1 - jitter, 1.0)
        pts.append((math.cos(a) * r * k, math.sin(a) * r * k, z * k * squash))
    return pts


def boulder(name, seed, n, squash, jitter, snow):
    rng = random.Random(seed)
    mb = L.MeshBuilder(name, seed)
    # caja con los cantos muy biselados (como las rocas del mundo, props_nature.chamfer_box_pts) casi cúbica, más unos
    # puntos sobre la esfera que la redondean: caras grandes y planas de roca, pero rueda sin trabarse. Solo la esfera
    # daba un dado de icosaedro, demasiado regular
    pts = N.chamfer_box_pts(rng, (0, 0, 0), 0.5, 0.5 * rng.uniform(0.88, 0.98), 0.5 * squash, chamfer=0.62, jit=0.14, taper=0.9)
    pts += sphere_pts(rng, n, 0.53, squash, jitter)
    p = N.hull(mb, pts, "rock")
    # nieve pegada en las caras de arriba (contrasta con el granito gris), granito facetado en el resto
    N.rock_colors(p, rng, light="rock", mid="rock", dark="rock_dark",
                  top="snow" if snow else None, top_alt="snow_shade", top_t=0.45, p_top=0.9)
    mb.collider_none()
    return mb.finish()


def shard(name, seed):
    rng = random.Random(seed)
    mb = L.MeshBuilder(name, seed)
    pts = sphere_pts(rng, 9, 0.5, rng.uniform(0.45, 0.7), 0.45)
    p = N.hull(mb, pts, "rock")
    N.rock_colors(p, rng, top="snow_shade", top_t=0.6, p_top=0.5)
    mb.collider_none()
    return mb.finish()


def build():
    L.clear_scene()
    objs = [
        boulder("Boulder_A", 11, 8, 0.92, 0.2, True),
        boulder("Boulder_B", 23, 7, 0.84, 0.25, True),
        boulder("Boulder_C", 37, 6, 0.95, 0.3, False),
    ]
    objs += [shard(f"Shard_{c}", 50 + i) for i, c in enumerate("ABCD")]
    for o in objs:
        tris = len(o.data.polygons)
        mn = Vector((min(v.co.x for v in o.data.vertices), min(v.co.y for v in o.data.vertices), min(v.co.z for v in o.data.vertices)))
        mx = Vector((max(v.co.x for v in o.data.vertices), max(v.co.y for v in o.data.vertices), max(v.co.z for v in o.data.vertices)))
        print(f"{o.name}: {tris} tris, tamaño {tuple(round(c, 2) for c in (mx - mn))}")
    return objs


def preview(objs, out_dir):
    """La avalancha vista con la cámara del juego (52°, 24 m, FOV 30, 1280x720): tres rocas rodando por carriles rojos
    sobre la nieve de la cumbre y un Kaito de referencia (1.5 m)."""
    import nindo_preview as PV
    os.makedirs(out_dir, exist_ok=True)
    scn = bpy.context.scene
    PV.setup_night(ground=True, ground_size=60, ground_color="snow")
    scn.render.resolution_x, scn.render.resolution_y = 1280, 720
    mb = L.MeshBuilder("Lanes")
    # carriles: 2.3 m de ancho (2 (r + 0.35)), bajan hacia la cámara (Blender +Y = abajo en pantalla)
    for x in (-4.6, 0.0, 4.6):
        w = 1.15
        mb.face([(x - w, -12, 0.01), (x + w, -12, 0.01), (x + w, 8, 0.01), (x - w, 8, 0.01)], "cloth_red")
    lanes = mb.finish()
    for o in objs:
        o.location = (0, 40, -5)
    placed = []
    for i, (x, y) in enumerate(((-4.6, -6.0), (0.0, -2.0), (4.6, -8.5))):
        src = objs[i % 3]
        o = src.copy(); o.data = src.data
        scn.collection.objects.link(o)
        s = 1.65
        o.scale = (s, s, s)
        o.location = (x, y, 0.5 * s)
        o.rotation_euler = (math.radians(30 * i + 10), math.radians(20 * i), math.radians(50 * i))
        placed.append(o)
    # Kaito de referencia: cápsula de 1.5 m en el pasillo
    bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=1.5, location=(2.3, 3.0, 0.75))
    k = bpy.context.active_object
    k.data.materials.append(L.get_material("Nindo_Palette"))
    cam = PV._camera("CamJuego", 30)
    cam.data.sensor_fit = 'VERTICAL'     # el FOV 30 del juego es vertical
    pitch = math.radians(52)
    tgt = Vector((0, 0, 1.0))
    PV.look(cam, tgt + Vector((0, math.cos(pitch) * 24, math.sin(pitch) * 24)), tgt)
    scn.camera = cam
    scn.render.filepath = os.path.join(out_dir, "goro_boulders_game.png")
    bpy.ops.render.render(write_still=True)
    # de cerca, las siete mallas en fila
    for o in placed + [lanes, k]:
        o.hide_render = True
    for i, o in enumerate(objs):
        o.location = ((i - 3) * 1.4, 0, 0.5)
    cam2 = PV._camera("CamCerca", 35)
    PV.look(cam2, Vector((0, -9, 4)), Vector((0, 0, 0.4)))
    scn.camera = cam2
    scn.render.filepath = os.path.join(out_dir, "goro_boulders_close.png")
    bpy.ops.render.render(write_still=True)
    for i, o in enumerate(objs):
        o.location = (0, 0, 0)


objs = build()
if PREVIEW:
    preview(objs, PREVIEW)
if EXPORT:
    for o in objs:
        o.location = (0, 0, 0)
    L.export_fbx(objs, OUT_FBX)
    print("exportado", OUT_FBX)
