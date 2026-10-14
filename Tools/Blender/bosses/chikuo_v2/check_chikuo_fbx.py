"""Chequeo del FBX del Chikuō ermitaño sin Blender ni Unity (Python del sistema): lo que Unity va a ligar.

python Tools/Blender/bosses/chikuo_v2/check_chikuo_fbx.py [ruta del .fbx]   -> exit 1 si algo no cumple

* Jerarquía: en la raíz del archivo la armadura 'BambooMaster' y la malla con skin 'Chikuo_Body' (más de un nodo raíz).
  Con un solo nodo raíz Unity funde la armadura con la raíz del prefab (lo que aplanó los FBX de solo animación en octubre:
  escala x100, enemigos invisibles); con dos, los clips de este archivo quedan con las mismas rutas que los huesos
  ('BambooMaster/Root/Hips/...') y se ligan solos. La flauta rígida 'Chikuo_Staff' cuelga del hueso Staff.
* Ninguna curva que se MUEVA apunta a algo que no sea un hueso, ni al hueso 'Root' (la raíz del modelo no se anima), y
  ninguna escala se mueve. Cada hueso animado tiene su ruta bajo 'BambooMaster/Root/'.
* Están los huesos del contrato (el de build_chikuo.CONTRACT_BONES, leído del sidecar) y las esferas AccCol_* con su '_r'.
* Una sola toma ('Scene') que cubre los cuadros del sidecar, a 30 fps, sin texturas embebidas, unidades en metros.
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "Tools", "Blender", "characters"))
import fbxcheck as FC

FBX = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "Nindo", "Assets", "Nindo", "Art", "Characters", "BambooMaster",
                                                         "BambooMaster.fbx")
fails = []


def check(ok, msg):
    print(("  ok   " if ok else "  FAIL ") + msg)
    if not ok:
        fails.append(msg)


root, ver = FC.parse(FBX)
objs, up, down = {}, {}, {}
for e in root.elems:
    if e.id == b"Objects":
        objs = {o.props[0]: o for o in e.elems if o.props}
    elif e.id == b"Connections":
        for c in e.elems:
            kid, par = c.props[1], c.props[2]
            prop = c.props[3].decode("utf-8", "replace") if len(c.props) > 3 else None
            down.setdefault(par, []).append((kid, prop))
            up.setdefault(kid, []).append((par, prop))
models = {i: o for i, o in objs.items() if o.id == b"Model"}
kind = {FC.obj_name(o): o.props[2].decode() for o in models.values()}
name_of = {i: FC.obj_name(o) for i, o in models.items()}
roots = sorted(name_of[i] for i in models if any(p == 0 for p, _ in up.get(i, ())))
check(roots == ["BambooMaster", "Chikuo_Body"], f"en la raíz la armadura y la malla con skin: más de un nodo (raíces: {roots})")
rid = next((i for i, n in name_of.items() if n == "BambooMaster"), None)
kids = sorted(name_of[k] for k, _ in down.get(rid, ()) if k in models)
check(kids == ["Root"], f"la armadura cuelga del hueso Root (hijos: {kids})")
meshes = sorted(n for n, k in kind.items() if k == "Mesh")
check(meshes == ["Chikuo_Body", "Chikuo_Staff"], f"las dos mallas ({meshes})")
par = FC.parents(root)
check(par.get("Chikuo_Staff") == "Staff", f"la flauta cuelga del hueso Staff (padre: {par.get('Chikuo_Staff')})")
bones = {n for n, k in kind.items() if k == "LimbNode"}
info = json.load(open(FBX + ".json", encoding="utf-8"))
need = set(info.get("contract_bones", []))
missing = sorted(need - bones)
check(bool(need) and not missing, f"huesos del contrato ({len(bones)} huesos, {len(need)} pedidos; faltan {missing[:8]})")
cols = [n for n in bones if n.startswith("AccCol_") and not n.endswith("_r")]
check(len(cols) == len(info["chains"]["colliders"]) and all(c + "_r" in bones for c in cols),
      f"esferas AccCol con su marca de radio ({sorted(cols)})")
for mid, o in models.items():
    if kind[name_of[mid]] != "Mesh":
        continue
    mats = sorted(FC.obj_name(objs[k]) for k, _ in down.get(mid, ()) if k in objs and objs[k].id == b"Material")
    print(f"  info {name_of[mid]}: {mats}")
    want = set(info["parts"]["materials"])
    check(set(mats) <= want, f"{name_of[mid]}: solo materiales del sidecar (sobran {sorted(set(mats) - want)})")
mv = FC.motion(root)
moving = {n for st in mv.values() for n, prop, ax in st}
other = sorted(n for n in moving if kind.get(n) != "LimbNode")
check(not other, f"ninguna curva que se mueva anima la armadura ni una malla ({other})")
check("Root" not in moving, "la raíz del modelo ('Root') no se anima")
moving_scale = sorted({n for st in mv.values() for n, prop, ax in st if prop == "Lcl Scaling"})
check(not moving_scale, f"ninguna escala se mueve ({moving_scale[:6]})")
bad_path = sorted(n for n in moving if not FC.path_of(par, n).startswith("BambooMaster/Root/"))
check(not bad_path, f"cada hueso animado liga bajo 'BambooMaster/Root/' ({bad_path[:6]})")
print("  info rutas de ejemplo:", [FC.path_of(par, n) for n in ("Hips", "Hand_R", "Acc_ChimesHi00_0", "Staff") if n in par])
s = FC.summary(FBX)
last = max(r["last"] for r in info["clips"].values())
st = s["stacks"]
check(list(st) == ["Scene"], f"una sola toma 'Scene' ({list(st)})")
if "Scene" in st:
    a, b = st["Scene"]
    check(abs(b * s["fps"] - last) < 1.01, f"la toma llega al último cuadro del sidecar ({b * s['fps']:.1f} vs {last})")
check(s["fps"] == 30, f"30 fps ({s['fps']})")
check(abs((s.get("unit") or 1.0) - 100.0) < 1e-3,
      f"unidades del archivo como el FBX de antes y Kokuyo.fbx ({s.get('unit')} cm por unidad; useFileScale del .meta)")
check(s["video_bytes"] == 0, f"sin texturas embebidas ({s['videos']} referencias, {s['video_bytes']} bytes)")
print("FBX", "OK" if not fails else f"FALLA ({len(fails)})")
sys.exit(1 if fails else 0)
