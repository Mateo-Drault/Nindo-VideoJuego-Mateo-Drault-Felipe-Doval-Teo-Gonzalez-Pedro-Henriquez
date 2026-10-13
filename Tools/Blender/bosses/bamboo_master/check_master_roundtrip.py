"""Ida y vuelta del FBX de Chikuō: lo importa en una escena vacía y compara, cuadro por cuadro, dónde quedan algunos
huesos con la referencia que escribió build_bamboo_master.py (--export --roundtrip). Detecta tomas corridas un cuadro,
curvas simplificadas de más, ejes dados vuelta y un hueso que quedó fuera del archivo.

blender -b --factory-startup --python check_master_roundtrip.py -- <BambooMaster.fbx> <roundtrip.json>
"""
import bpy, sys, json
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:]
FBX, REF = argv[0], argv[1]
ref = json.load(open(REF, encoding="utf-8"))
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.fps = 30
bpy.ops.import_scene.fbx(filepath=FBX)
arm = next(o for o in bpy.data.objects if o.type == 'ARMATURE')
act = arm.animation_data.action if arm.animation_data else None
print("ACCION", act.name if act else None, tuple(act.frame_range) if act else None)
# la toma exportada empieza en el cuadro 1 y el importador de Blender la corre (empieza en el 2): se compara cada cuadro
# de la referencia con el mismo cuadro de la toma
off = int(round(act.frame_range[0])) - 1 if act else 0
worst = (0.0, "", 0)
for f, bones in ref.items():
    bpy.context.scene.frame_set(int(f) + off)
    for b, p in bones.items():
        if b not in arm.pose.bones:
            print("FALTA EL HUESO", b)
            worst = (99.0, b, int(f))
            continue
        q = arm.matrix_world @ arm.pose.bones[b].head
        e = (Vector(p) - q).length
        if e > worst[0]:
            worst = (e, b, int(f))
print(f"RT error máx {worst[0] * 100:.2f} cm en {worst[1]} f{worst[2]}")
mats = sorted({m.name for o in bpy.data.objects if o.type == 'MESH' for m in o.data.materials if m})
print("MESHES", sorted(o.name for o in bpy.data.objects if o.type == 'MESH'), "MATERIALES", mats)
# las formas del saco vuelven con su animación (cada etapa de CoatSlip llega a 1 en PhaseCoat; Collapse al caer)


def shape_peak(obj_name, shape):
    o = bpy.data.objects.get(obj_name)
    keys = o.data.shape_keys if o is not None else None
    kb = keys.key_blocks.get(shape) if keys is not None else None
    if kb is None or not (keys.animation_data and keys.animation_data.action):
        return None if kb is None else 0.0
    act_k = keys.animation_data.action
    try:
        fcs = act_k.fcurves                      # Blender 4.x
    except AttributeError:                       # Blender 5: las curvas viven en la channelbag del slot
        from bpy_extras import anim_utils
        fcs = anim_utils.action_get_channelbag_for_slot(act_k, keys.animation_data.action_slot).fcurves
    return max((k.co[1] for fc in fcs if f'"{shape}"' in fc.data_path for k in fc.keyframe_points), default=0.0)


slip_ok = True
# las etapas del medio pasan de una a la siguiente entre dos cuadros (no llegan solas a 1); la última y Collapse sí
for obj_name, shape, need in [("Master_Robe", "CoatSlip%d" % k, 0.5) for k in range(1, 4)] +         [("Master_Robe", "CoatSlip4", 0.99), ("Master_RobeThrown", "Collapse", 0.99)]:
    pk = shape_peak(obj_name, shape)
    print(f"{shape} ({obj_name}) {'FALTA' if pk is None else 'presente'}, peso máx. {pk or 0.0:.2f}")
    slip_ok = slip_ok and pk is not None and pk > need
ok = worst[0] < 0.01 and slip_ok
print("ROUNDTRIP", "OK" if ok else "FALLA")
sys.exit(0 if ok else 1)
