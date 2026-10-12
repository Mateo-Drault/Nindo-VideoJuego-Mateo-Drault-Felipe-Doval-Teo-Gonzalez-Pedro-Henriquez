"""Los kits de zona (Tools/Blender/characters/kits) puestos sobre las poses de los idles ambientales: que las variantes
del lago, la montaña y el bambú se sigan viendo bien sentadas, practicando o durmiendo (las cadenas con física quedan en
su reposo: SpringChain las mueve en el juego).

  blender -b --factory-startup --python Tools/Blender/anim/ambient_kits.py -- OUT_DIR [ninja|sumo]

Lee los cuadros de cada clip del sidecar de TeamAnims y escribe ambient_kits_<personaje>.png: por kit, una fila con la
cámara del juego (1080p x2) en las poses que más se apartan del Idle.
"""
import bpy, os, sys, json
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
KITS = os.path.join(REPO, "Tools", "Blender", "characters", "kits")
sys.path.insert(0, KITS)
import kitlib as K          # noqa: E402
import preview_kits as PV   # noqa: E402
import build_kits as B      # noqa: E402

TEAM = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Art", "Characters", "TeamAnims")
POSES = {
    "ninja": (["ninja_default", "ninja_elite", "ninja_mountain", "ninja_lake", "ninja_bamboo", "ninja_bamboo_elite"],
              [("IdleMeditate", 0), ("AmbientAlert", 14), ("IdleSparA", 15), ("IdleSparA", 63), ("IdleInspect", 77)]),
    "sumo": (["sumo_default", "sumo_mountain", "sumo_lake", "sumo_bamboo"],
             [("IdleSleep", 48), ("AmbientAlert", 32), ("AmbientAlert", 42), ("IdleShiko", 36)]),
}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = argv[0]
    chars = [a for a in argv[1:] if a in POSES] or list(POSES)
    tmp = os.path.join(out, "_k")      # nombres cortos: el scratch ya está cerca del límite de 260 caracteres
    os.makedirs(tmp, exist_ok=True)
    for char in chars:
        fbx = os.path.join(TEAM, char.capitalize() + "Anims.fbx")
        info = json.load(open(fbx + ".json", encoding="utf-8"))
        kits, poses = POSES[char]
        cells = []
        for ki, kit_name in enumerate(kits):
            ch = K.load_char(char, None, fbx)
            k = K.Kit(ch, kit_name)
            B.KITS[kit_name][1](k)
            k.build()
            B.recolor_body(ch, B.BODY_COLORS.get(kit_name, {}))
            PV.night_scene()
            PV.place(ch, (0, 0, 0), 0, B.GAME_SCALE.get(kit_name, 1.0))
            K.use_action(ch.arm, "Scene")
            h = K.CHARS[char]["height"]
            for pi, (clip, f) in enumerate(poses):
                bpy.context.scene.frame_set(info["clips"][clip]["first"] + f)
                bpy.context.view_layer.update()
                p = os.path.join(tmp, f"{ki}{pi}.png")
                cells.append(PV.game_view(p, Vector((0, 0, h * 0.4)), 20, *PV.CELL[char]))
                print("POSE", kit_name, clip, f)
        PV.sheet(cells, os.path.join(out, f"ambient_kits_{char}.png"), len(poses), scale_game=2)


main()
