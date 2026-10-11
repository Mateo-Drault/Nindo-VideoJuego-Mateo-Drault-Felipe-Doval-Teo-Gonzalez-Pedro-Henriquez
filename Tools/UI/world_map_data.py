"""Datos del mundo para el mapa del juego (lo lee Tools/UI/build_world_map.py).

Corre Tools/Blender/world/build_world.py tal cual (sin --export ni --preview: no escribe nada del juego) para
tener EXACTAMENTE los mismos props que exporta el mundo (mismo sorteo de árboles, rocas, casas...) y los vuelca
a un JSON. Va en Blender porque build_world importa bpy; las alturas y regiones el mapa las calcula después con
world_terrain.py, que es Python puro.

  blender -b --factory-startup --python Tools/UI/world_map_data.py -- SALIDA.json
"""
import json
import os
import runpy
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
out = argv[0] if argv else os.path.join(REPO, "Tools", "Blender", "out", "world", "map_props.json")

# build_world mira los argumentos después de '--': sin banderas solo arma la escena en memoria
sys.argv = [sys.argv[0], "--"]
g = runpy.run_path(os.path.join(REPO, "Tools", "Blender", "world", "build_world.py"), run_name="build_world")

placed = [[p, round(x, 2), round(z, 2), round(yaw, 1), round(sc, 3), round(y, 2)] for p, x, z, yaw, sc, y in g["PLACED"]]
# de la decoración fusionada solo lo que se ve desde arriba como mancha (arbustos, flores, juncos); las matas de
# pasto son miles y a la escala del mapa no se distinguen
placed += [[p, round(x, 2), round(z, 2), round(yaw, 1), round(sc, 3), round(y, 2)] for p, x, z, yaw, sc, y in g["DECOR_PLACED"]
           if not p.startswith(("grass_tuft", "rice_patch", "wheat_patch"))]
sizes = {}
for mf in sorted(os.listdir(os.path.join(REPO, "Tools", "Blender", "out"))):
    if mf.startswith("manifest_") and mf.endswith(".json"):
        for pid, m in json.load(open(os.path.join(REPO, "Tools", "Blender", "out", mf))).items():
            sizes[pid] = m.get("size", [2, 2, 2])
os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
json.dump({"placed": placed, "sizes": sizes}, open(out, "w"))
print("map data:", len(placed), "props ->", out)
