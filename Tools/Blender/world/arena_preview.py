"""Vistas de las cañas del claro de Chikuō (para mirar el modelo y la arena antes de exportar).

blender -b --factory-startup --python Tools/Blender/world/arena_preview.py -- --out DIR [--stalks] [--arena] [--only a,b]
  --stalks  las cuatro cañas sueltas, rectas y dobladas (cargada 30°, latigazo -45°, inclinada 70°), con una figura de
            1.5 m agachada en el posado (el alto de Chikuō agachado), de cerca y con la cámara del juego
  --arena   el mundo armado por build_world (sin exportar) con las siete cañas en world_plan.BOSS_STALKS, Kaito (1.5 m) y
            la figura en distintos lugares, con la cámara de juego (52°, 24 m, FOV 30), la de pelea (45°, CameraDirector
            con el perfil de Chikuō) y los planos de la presentación
Renders de 1280 x 720 como mucho (la memoria se comparte con Unity).
"""
import sys, os, math, json

HERE = os.path.dirname(os.path.abspath(__file__))
BL = os.path.dirname(HERE)
sys.path[:0] = [HERE, BL, os.path.join(BL, "props")]
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def arg(name, default=None):
    if name in argv:
        i = argv.index(name)
        return argv[i + 1] if i + 1 < len(argv) and not argv[i + 1].startswith("--") else True
    return default


OUT = arg("--out", os.path.join(BL, "out", "arena"))
ONLY = set(arg("--only").split(",")) if isinstance(arg("--only"), str) else None
sys.argv = [sys.argv[0], "--"]          # build_world lee sus propios flags de sys.argv

import bpy
from mathutils import Vector, Matrix, Quaternion
import nindo_lib as L
import nindo_preview as PV
import arena_stalks as AS

os.makedirs(OUT, exist_ok=True)


def B(x, z, h=0.0):
    """juego (x este, z norte, h arriba) -> Blender."""
    return Vector((-x, -z, h))


def flat_mat(name, rgb, emit=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = 0.85
    if emit:
        b.inputs["Emission Color"].default_value = (*rgb, 1)
        b.inputs["Emission Strength"].default_value = emit
    return m


def s2l(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def pal(name):
    r, g, b = AS.PAL.hex_to_rgb(dict(AS.PAL.PALETTE)[name])
    return (s2l(r), s2l(g), s2l(b))


def prim(kind, name, loc, scale, mat, rot=(0, 0, 0), parent=None):
    if kind == "cube":
        bpy.ops.mesh.primitive_cube_add(size=1.0)
    elif kind == "cyl":
        bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.5, depth=1.0)
    else:
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.5)
    o = bpy.context.active_object
    o.name = name
    o.location = loc
    o.scale = scale
    o.rotation_euler = rot
    o.data.materials.append(mat)
    if parent is not None:
        o.parent = parent
    return o


def kaito_proxy(name, x, z, h):
    """Kaito: 1.5 m, negro con la bandana amarilla (lo que se ve de él desde la cámara)."""
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    root.location = B(x, z, h)
    blk, skin, yel = flat_mat("pk_black", pal("cloth_black")), flat_mat("pk_skin", (0.75, 0.55, 0.42)), flat_mat("pk_yellow", pal("gold"))
    prim("cyl", name + "_legs", (0, 0, 0.35), (0.34, 0.26, 0.7), blk, parent=root)
    prim("cyl", name + "_body", (0, 0, 0.88), (0.42, 0.32, 0.5), blk, parent=root)
    prim("ico", name + "_head", (0, 0, 1.28), (0.42, 0.42, 0.44), skin, parent=root)
    prim("cyl", name + "_band", (0, 0, 1.36), (0.45, 0.45, 0.08), yel, parent=root)
    prim("cube", name + "_hair", (0, 0, 1.47), (0.4, 0.4, 0.14), blk, parent=root)
    return root


def chikuo_proxy(name, mw, crouch=True):
    """Chikuō agachado (1.5 m): capa de hojas oscura, gi salvia, cabeza y barba blancas, cascabeles dorados, la flauta paja.
    No es el modelo: es para medir el encuadre, el tamaño en pantalla y el contraste contra la caña y el piso."""
    root = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(root)
    root.matrix_world = mw
    cape, gi, white, gold, staff = (flat_mat("pc_cape", pal("leaf_dark")), flat_mat("pc_gi", pal("grass_teal")),
                                    flat_mat("pc_white", pal("white")), flat_mat("pc_gold", pal("straw")), flat_mat("pc_staff", pal("wheat")))
    s = 1.0 if crouch else 1.55
    prim("cyl", name + "_legs", (0, -0.12, 0.28 * s), (0.62, 0.5, 0.5 * s), gi, parent=root)
    prim("ico", name + "_cape", (0, 0.05, 0.78 * s), (0.95, 0.8, 0.95 * s), cape, parent=root)
    prim("ico", name + "_head", (0, -0.18, 1.3 * s), (0.34, 0.34, 0.36), flat_mat("pc_skin", (0.62, 0.45, 0.33)), parent=root)
    prim("cube", name + "_top", (0, -0.16, 1.55 * s), (0.12, 0.12, 0.22), white, parent=root)
    prim("cube", name + "_beard", (0, -0.36, 1.08 * s), (0.2, 0.08, 0.45), white, parent=root)
    prim("cube", name + "_brow", (0, -0.34, 1.38 * s), (0.36, 0.06, 0.06), white, parent=root)
    for i in range(6):
        a = math.pi * (0.15 + 0.7 * i / 5)
        prim("cyl", f"{name}_chime{i}", (math.cos(a) * 0.5, math.sin(a) * 0.35, 0.95 * s), (0.08, 0.08, 0.26), gold, parent=root)
    prim("cyl", name + "_staff", (0.45, -0.1, 0.9 * s), (0.07, 0.07, 2.1), staff, rot=(math.radians(60), 0, math.radians(20)), parent=root)
    return root


def game_camera(name, focus, pitch=52.0, dist=24.0, fov=30.0, yaw=0.0):
    """Cámara del juego mirando al norte (yaw 0): Blender -Y es el norte."""
    cd = bpy.data.cameras.new(name)
    cd.lens_unit = 'FOV'
    cd.sensor_fit = 'VERTICAL'
    cd.angle = math.radians(fov)
    cd.clip_end = 600
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    pr, yr = math.radians(pitch), math.radians(yaw)
    fx, fz, fh = focus
    back = Vector((-math.sin(yr) * math.cos(pr), -math.cos(yr) * math.cos(pr), math.sin(pr))) * dist
    eye = (fx + back.x, fz + back.y, fh + back.z)
    PV.look(cam, B(*eye), B(*focus))
    return cam


def shot_camera(name, eye, look, fov=34.0):
    cd = bpy.data.cameras.new(name)
    cd.lens_unit = 'FOV'
    cd.sensor_fit = 'VERTICAL'
    cd.angle = math.radians(fov)
    cd.clip_end = 600
    cam = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(cam)
    PV.look(cam, B(*eye), B(*look))
    return cam


def render(cam, name, res=(1280, 720)):
    scn = bpy.context.scene
    scn.camera = cam
    scn.render.resolution_x, scn.render.resolution_y = res
    scn.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", scn.render.filepath)


def place_stalk(kind, x, z, h, bend=0.0, bdir=(0.0, 1.0), even=0.0):
    """Arma la caña y la pone en el mundo (yaw 0: los ejes del archivo son los del mundo). bdir: dirección del arco en el
    plano del juego (x este, z norte)."""
    objs = AS.build(kind)
    root = bpy.data.objects.new(f"Inst_{kind}", None)
    bpy.context.scene.collection.objects.link(root)
    root.location = B(x, z, h)
    for o in objs.values():
        if o.parent is None:
            o.parent = root
    if "Stump" in objs:
        objs["Stump"].hide_render = True
    for n in ("Crack", "CrackUp"):
        if n in objs:
            objs[n].hide_render = True
    if bend:
        AS.apply_bend(objs, kind, bend, (-bdir[0], -bdir[1]), even)
    bpy.context.view_layer.update()
    return objs


def perch_matrix(objs, face_xz):
    """El modelo en el PerchNode: posición y giro del tramo (el cuerpo se inclina con el arco), mirando a face_xz."""
    pn = objs["PerchNode"].matrix_world
    up = (pn.to_3x3() @ Vector((0, 0, 1))).normalized()
    f = Vector((-face_xz[0], -face_xz[1], 0))
    f = (f - up * f.dot(up)).normalized()
    side = f.cross(up)
    m = Matrix((side, -f, up)).transposed().to_4x4()      # el proxy mira a -Y local
    m.translation = pn.translation
    return m


# =========================================================================== --stalks
def stalks_sheet():
    L.clear_scene()
    PV.setup_night(ground=True, ground_size=60, ground_color="path_dark", strength=1.1)
    xs = {"inner": -6.0, "north": -2.0, "outer": 2.0, "mother": 6.5}
    for k, x in xs.items():
        objs = place_stalk(k, x, 0.0, 0.0)
        chikuo_proxy(f"C_{k}", perch_matrix(objs, (0, -1)))
    kaito_proxy("K", 0.0, -3.0, 0.0)
    render(game_camera("cam_game", (0.0, 0.0, 4.0), dist=24.0), "stalks_game")
    render(shot_camera("cam_close", (3.0, -9.5, 3.5), (0.0, 0.0, 3.6), fov=40), "stalks_close")
    render(shot_camera("cam_perch", (-4.0, -2.2, 5.2), (-6.0, 0.0, 5.0), fov=30), "stalks_perch_close", res=(960, 720))
    render(shot_camera("cam_base", (-4.6, -1.8, 1.5), (-6.0, 0.0, 0.8), fov=36), "stalks_base_close", res=(960, 720))
    # dobladas: cargada 30° (hacia Kaito, al sur), latigazo -45°, inclinada 70° hacia afuera, y la rajada con el tocón
    L.clear_scene()
    PV.setup_night(ground=True, ground_size=60, ground_color="path_dark", strength=1.1)
    a = place_stalk("inner", -7.0, 0.0, 0.0, 30.0, (0.0, -1.0))
    chikuo_proxy("C_a", perch_matrix(a, (0, -1)))
    b = place_stalk("inner", -2.5, 0.0, 0.0, -45.0, (1.0, 0.0))
    c = place_stalk("outer", 2.0, 0.0, 0.0, 70.0, (1.0, 0.3), even=1.0)
    d = place_stalk("inner", 7.0, 0.0, 0.0)
    d["Crack"].hide_render = False
    d["CrackUp"].hide_render = False
    e = AS.build_stump("inner", 7)
    e.location = B(10.0, -1.0, 0.0)
    render(game_camera("cam_game2", (1.0, 0.0, 3.5), dist=24.0), "stalks_bent_game")
    render(shot_camera("cam_close2", (2.0, -11.0, 3.5), (1.0, 0.0, 3.2), fov=45), "stalks_bent_close")
    render(shot_camera("cam_crack", (8.2, -3.0, 1.4), (7.5, 0.0, 1.0), fov=34), "stalks_crack_close", res=(960, 720))
    # detalle sin la figura: el nudo del posado con el cordón y los cascabeles, la Madre, el tocón y la rajadura
    L.clear_scene()
    PV.setup_night(ground=True, ground_size=40, ground_color="path_dark", strength=1.1)
    place_stalk("inner", 0.0, 0.0, 0.0)
    place_stalk("mother", 3.0, 1.5, 0.0)
    render(shot_camera("cam_det_perch", (0.9, -2.2, 4.9), (0.0, 0.0, 4.35), fov=30), "detail_perch", res=(960, 720))
    render(shot_camera("cam_det_mother", (3.9, -1.0, 5.6), (3.0, 1.5, 5.0), fov=32), "detail_mother_perch", res=(960, 720))
    render(shot_camera("cam_det_crown", (2.0, -9.0, 9.0), (1.5, 0.5, 7.0), fov=34), "detail_crowns", res=(960, 720))


def main():
    if "--stalks" in argv:
        stalks_sheet()
    if "--arena" in argv:
        import arena_shots
        arena_shots.run(sys.modules[__name__], ONLY)


main()
