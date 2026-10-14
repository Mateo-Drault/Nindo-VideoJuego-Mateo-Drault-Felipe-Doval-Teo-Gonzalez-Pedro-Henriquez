"""Ida y vuelta del FBX del Chikuō ermitaño en Blender: se importa BambooMaster.fbx y se compara cuadro a cuadro con lo
que dejó build_chikuo.py --export --roundtrip PATH (huesos en el mundo y la caja y el centro de la malla deformada). Si el
skin, los ejes de los huesos o la toma se rompen en el FBX, acá se ve antes de llegar a Unity.

  blender -b --factory-startup --python Tools/Blender/bosses/chikuo_v2/check_chikuo_roundtrip.py -- PATH   -> exit 1 si no
"""
import sys, os, json
import bpy
from mathutils import Vector
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "Tools", "Blender", "anim"))
import nindo_anim as NA

argv = sys.argv[sys.argv.index("--") + 1:]
ref = json.load(open(argv[0], encoding="utf-8"))
FBX = os.path.join(ROOT, "Nindo", "Assets", "Nindo", "Art", "Characters", "BambooMaster", "BambooMaster.fbx")
bpy.ops.wm.read_factory_settings(use_empty=True)
# sin el corrimiento de un cuadro que el importador de Blender pone por defecto (anim_offset 1): la toma 1..N queda en
# los mismos cuadros que en el armado
bpy.ops.import_scene.fbx(filepath=FBX, anim_offset=0.0)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
body = bpy.data.objects["Chikuo_Body"]
scn = bpy.context.scene
worst_b, worst_m = (0.0, None), (0.0, None)
for f, r in sorted(ref.items(), key=lambda kv: int(kv[0])):
    scn.frame_set(int(f))
    bpy.context.view_layer.update()
    for b, p in r["bones"].items():
        d = ((arm.matrix_world @ arm.pose.bones[b].head) - Vector(p)).length
        if d > worst_b[0]:
            worst_b = (d, f"{b} f{f}")
    w = NA.world_verts(body, bpy.context.evaluated_depsgraph_get())
    got = [w.min(axis=0).tolist(), w.max(axis=0).tolist(), w.mean(axis=0).tolist()]
    for a, b, lab in zip(got, r["mesh"], ("mín", "máx", "centro")):
        d = (Vector(a) - Vector(b)).length
        if d > worst_m[0]:
            worst_m = (d, f"{lab} f{f}")
print(f"huesos: peor {worst_b[0] * 1000:.2f} mm ({worst_b[1]}); malla: peor {worst_m[0] * 1000:.2f} mm ({worst_m[1]})")
ok = worst_b[0] <= 0.002 and worst_m[0] <= 0.005
print("IDA Y VUELTA", "OK" if ok else "FALLA")
sys.exit(0 if ok else 1)
