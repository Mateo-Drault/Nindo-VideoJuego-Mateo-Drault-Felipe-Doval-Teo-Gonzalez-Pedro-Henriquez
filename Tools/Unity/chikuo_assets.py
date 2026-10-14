"""Regenera SOLO lo de Chikuō (personaje 'bamboo_master') sin correr generate_assets.py entero (que reescribe entradas de
otros): los .mat propios y el .meta de BambooMaster.fbx (generate_assets.bamboo_master_assets), BambooMaster.controller
(bamboo_master_controller) y su fila en Resources/NindoContent.asset (alto de bind, brillo de los materiales, estados y
duraciones). Todo sale del sidecar BambooMaster.fbx.json que escribe Tools/Blender/bosses/chikuo_v2/build_chikuo.py.

  python Tools/Unity/chikuo_assets.py [--prune]
    --prune   borra los .mat (con su .meta) de la carpeta BambooMaster que el sidecar ya no nombra (los del Chikuō viejo)
"""
import os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "Blender"))
import generate_assets as G

MODEL = 919132149155446097      # fileID del prefab de modelo (el de content_asset)


def content_row(res, info):
    """La fila de 'bamboo_master' como la escribe content_asset.chars()."""
    cg, lens = res["bamboo_master"]
    names = "".join(f"\n    - {n}" for n in lens) or " []"
    secs = "".join(f"\n    - {lens[n]}" for n in lens) or " []"
    return f"""  - id: bamboo_master
    model: {G.ref(G.ensure_guid(G.BAMBOO_FBX), MODEL, 3)}
    controller: {G.ref(cg, 9100000, 2)}
    height: {round(info["bind_height"], 2)}
    modelYaw: 0
    materialSwaps:{G.material_swaps("bamboo_master")}
    stateNames:{names}
    stateLengths:{secs}
"""


def main():
    info = G.bamboo_master_info()
    assert info, "falta BambooMaster.fbx o su sidecar"
    mats = {"palette": G.read_guid(os.path.join(G.P_MAT, "Nindo_Palette.mat")),
            "emissive": G.read_guid(os.path.join(G.P_MAT, "Nindo_Emissive.mat"))}
    assert all(mats.values()), "faltan los .meta de Nindo_Palette.mat / Nindo_Emissive.mat"
    G.bamboo_master_assets(mats)
    res = G.bamboo_master_controller()
    path = os.path.join(G.P_RES, "NindoContent.asset")
    txt = open(path, encoding="utf-8").read()
    # la fila va desde '  - id: bamboo_master' hasta la próxima fila o la próxima lista de primer nivel
    m = re.search(r"^  - id: bamboo_master\n(?:    .*\n)*", txt, re.M)
    assert m, "NindoContent.asset no tiene la fila de bamboo_master"
    txt = txt[:m.start()] + content_row(res, info) + txt[m.end():]
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(txt)
    if "--prune" in sys.argv:
        keep = set(info["material_rgb"]) | set(info.get("extra_materials", {}))
        for f in sorted(os.listdir(G.P_BAMBOO)):
            if f.endswith(".mat") and f[:-4] not in keep:
                os.remove(os.path.join(G.P_BAMBOO, f))
                if os.path.exists(os.path.join(G.P_BAMBOO, f + ".meta")):
                    os.remove(os.path.join(G.P_BAMBOO, f + ".meta"))
                print("borrado", f)
    print("bamboo_master:", len(res["bamboo_master"][1]), "estados; alto", info["bind_height"])


if __name__ == "__main__":
    main()
