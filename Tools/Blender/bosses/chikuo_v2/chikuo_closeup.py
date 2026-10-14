"""Primeros planos de iteración del modelo (luz de estudio): la cabeza, el cuerpo, los pies o una pose de prueba de cerca.

  blender -b --factory-startup --python Tools/Blender/bosses/chikuo_v2/chikuo_closeup.py -- DIR cabeza|cuerpo|pies
  blender -b ... -- DIR pose NOMBRE x,y,z ESCALA     (una pose de chikuo_poses de cerca, alrededor de x,y,z, desde 4 lados)
"""
import sys, os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
for p in (HERE, os.path.join(ROOT, "Tools", "Blender"), os.path.join(ROOT, "Tools", "Blender", "anim")):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True
from mathutils import Vector
import nindo_lib as L
import nindo_anim as NA
import chikuo_rig as CR
import chikuo_model as CM
import chikuo_poses as CP
import chikuo_review as RV

argv = sys.argv[sys.argv.index("--") + 1:]
out = argv[0]
what = argv[1] if len(argv) > 1 else "cabeza"
L.clear_scene()
arm = NA.build_armature("BambooMaster", CR.bones(), data_name="BambooMasterRig")
rig = NA.Rig(arm)
meshes, _ = CM.build(arm, rig)
rv = RV.Review(arm, rig, meshes, out)
rv.use("studio")
rv.floor()
tag = what
if what == "pose":
    name = argv[2]
    c = Vector(tuple(float(v) for v in argv[3].split(",")))
    sc = float(argv[4])
    W, _ = CP.solve(rig, name)
    rv.apply(W)
    up = CP.SHEET_LIFT.get(name, 0.0)
    arm.location = (0, 0, up)
    views = [(c + Vector((0, 0, up)), sc, a, e) for a, e in ((0, 5), (70, 5), (160, 10), (250, 5))]
    tag = f"{name}_{argv[3]}"
else:
    views = {"cabeza": [((0, 0.0, 2.22), 0.54, a, e) for a, e in ((0, 3), (90, 2), (35, 5), (-90, 2), (180, 8), (0, 60))],
             "cuerpo": [((0, 0, 1.55), 1.2, a, e) for a, e in ((0, 3), (90, 2), (35, 5), (180, 8))],
             "pies": [((-0.24, -0.06, 0.2), 0.6, a, e) for a, e in ((0, 3), (90, 2), (35, 15), (180, 8))]}[what]
tiles = []
for i, (c, s, a, e) in enumerate(views):
    rv.set_studio_light(RV.STUDIO if abs(a) < 150 else Vector((0.4, 0.75, 0.7)))
    rv.ortho(c, s, a, e)
    tiles.append({"img": rv.render(rv.tile(f"cu_{i}"), res=(640, 640)), "label": f"{tag} {a}° / {e}°"})
rv.sheet({"out": os.path.join(out, f"closeup_{tag}.png"), "title": "primer plano: " + tag, "width": 1280, "tile_h": 420,
          "rows": [{"label": "", "tiles": tiles}]})
