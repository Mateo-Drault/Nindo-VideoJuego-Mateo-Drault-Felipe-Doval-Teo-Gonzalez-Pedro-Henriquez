"""Chequeo del FBX de Chikuō sin Blender ni Unity (Python del sistema): lo que Unity va a ligar.

python Tools/Blender/bosses/bamboo_master/check_master_fbx.py [ruta del .fbx]   -> exit 1 si algo no cumple

* Jerarquía: en la raíz del archivo la armadura 'BambooMaster' y las tres mallas con skin (como Kokuyo.fbx). Con más
  de un nodo raíz Unity NO funde la armadura con la raíz del prefab (lo que aplanó los FBX de solo animación en
  octubre: escala x100, enemigos invisibles): los clips del mismo archivo quedan con las mismas rutas que los huesos
  ('BambooMaster/Root/Hips/...') y se ligan solos. Además ninguna curva que se MUEVA puede apuntar a algo que no sea
  un hueso: el exportador deja curvas constantes en la armadura y en el bastón (su transform de siempre).
* Están los huesos de los que dependen el código y las etapas siguientes (dedos, Toe, Staff, Facing, las cadenas
  Acc_* con su '_end' y las esferas AccCol_* con su '_r') y las cuatro mallas, cada una con sus materiales.
* Una sola toma ('Scene') que cubre los cuadros del sidecar, a 30 fps.
* Las formas CoatSlip1..4 de Master_Robe (el saco que se desliza antes de CoatOff) y Collapse de Master_RobeThrown (la
  copia que se aplana al caer), con sus curvas DeformPercent, que solo pesan dentro de PhaseCoat (el .meta tiene que
  importar blend shapes: generate_assets.bamboo_master_assets).
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
roots = [name_of[i] for i in models if any(p == 0 for p, _ in up.get(i, ()))]
check(sorted(roots) == ["BambooMaster", "Master_Body", "Master_Robe", "Master_RobeThrown"],
      f"en la raíz la armadura y las mallas con skin, más de un nodo (raíces: {roots})")
rid = next((i for i, n in name_of.items() if n == "BambooMaster"), None)
kids = sorted(name_of[k] for k, _ in down.get(rid, ()) if k in models)
check(kids == ["Root"], f"la armadura cuelga del hueso Root (hijos: {kids})")
meshes = sorted(n for n, k in kind.items() if k == "Mesh")
check(meshes == ["Master_Body", "Master_Robe", "Master_RobeThrown", "Master_Staff"], f"las cuatro mallas ({meshes})")
bones = {n for n, k in kind.items() if k == "LimbNode"}
need = {"Root", "Hips", "Spine", "Chest", "Neck", "Head", "Staff", "Facing", "RobeT_Root"}
for S in "RL":
    need |= {f"{b}_{S}" for b in ("Clav", "UpperArm", "Forearm", "Hand", "Sleeve", "Thigh", "Shin", "Foot", "Toe")}
    need |= {f"{f}_{S}_{i}" for f in ("Index", "Middle", "Ring", "Pinky", "Thumb") for i in (1, 2)}
    need |= {f"Brow_{S}_{i}" for i in (1, 2)}
    need |= {f"Acc_TieWhisker{S}_{i}" for i in (0, 1, 2)} | {f"Acc_TieWhisker{S}_end"}
for t in "AB":
    need |= {f"Acc_TieSash{t}_{i}" for i in (0, 1, 2)} | {f"Acc_TieSash{t}_end"}
cols = [n for n in bones if n.startswith("AccCol_") and not n.endswith("_r")]
missing = sorted(need - bones)
check(not missing, f"huesos que usan el código y las etapas 2-3 ({len(bones)} huesos; faltan {missing[:8]})")
check(len(cols) == 4 and all(c + "_r" in bones for c in cols), f"esferas AccCol con su marca de radio ({sorted(cols)})")
# materiales por malla
for mid, o in models.items():
    if kind[name_of[mid]] != "Mesh":
        continue
    mats = sorted(FC.obj_name(objs[k]) for k, _ in down.get(mid, ()) if k in objs and objs[k].id == b"Material")
    print(f"  info {name_of[mid]}: {mats}")
# curvas: todas a huesos, ninguna a la raíz ni a una malla
targets = {}
for cn, o in objs.items():
    if o.id != b"AnimationCurveNode":
        continue
    for m, prop in up.get(cn, ()):
        if m in models:
            targets.setdefault(name_of[m], set()).add(prop)
mv = FC.motion(root)
other = sorted(n for n in targets if kind.get(n) != "LimbNode")
moving_other = sorted({n for st in mv.values() for n, prop, ax in st if kind.get(n) != "LimbNode"})
check(not moving_other, f"ninguna curva que se mueva anima la armadura ni una malla (con curvas constantes: {other}; "
                        f"que se mueven: {moving_other})")
scale_nodes = sorted(n for n, p in targets.items() if "Lcl Scaling" in p)
moving_scale = sorted({n for st in mv.values() for n, prop, ax in st if prop == "Lcl Scaling"})
check(not moving_scale, f"ninguna escala se mueve (curvas de escala constantes en {len(scale_nodes)} huesos)")
s = FC.summary(FBX)
info = json.load(open(FBX + ".json", encoding="utf-8"))
# las formas del saco: CoatSlip1..4 en Master_Robe y Collapse en Master_RobeThrown, animadas solo dentro de PhaseCoat
# (Unity: blendShape.CoatSlipK / blendShape.Collapse)
chans = {i: o for i, o in objs.items() if o.id == b"Deformer" and len(o.props) > 2 and o.props[2] == b"BlendShapeChannel"}
SHAPES = [("CoatSlip%d" % k, "Master_Robe") for k in range(1, 5)] + [("Collapse", "Master_RobeThrown")]


def owner_mesh(cid):
    """El Model de la malla que deforma un canal: canal -> BlendShape -> Geometry -> Model."""
    for bs, _ in up.get(cid, ()):
        for geo, _ in up.get(bs, ()):
            for m, _ in up.get(geo, ()):
                if m in models:
                    return name_of[m]
    return None


pc = info["clips"].get("PhaseCoat")
for shape, mesh in SHAPES:
    ch = next((i for i, o in chans.items() if FC.obj_name(o) == shape), None)
    check(ch is not None and owner_mesh(ch) == mesh,
          f"forma {shape} en {mesh} (canales: {sorted(FC.obj_name(o) + '@' + str(owner_mesh(i)) for i, o in chans.items())})")
    if ch is None:
        continue
    curves = [k for cn, prop in down.get(ch, ()) if cn in objs and objs[cn].id == b"AnimationCurveNode" and prop == "DeformPercent"
              for k, _ in down.get(cn, ()) if k in objs and objs[k].id == b"AnimationCurve"]
    on = []
    for k in curves:
        el = {x.id: x.props[0] for x in objs[k].elems if x.id in (b"KeyTime", b"KeyValueFloat")}
        on += [round(t / FC.KTIME * s["fps"]) for t, v in zip(el.get(b"KeyTime", ()), el.get(b"KeyValueFloat", ())) if v > 0.5]
    inside = pc is not None and on and all(pc["first"] <= f <= pc["last"] for f in on)
    check(bool(curves) and inside, f"{shape} animada solo en PhaseCoat (cuadros con peso: {min(on) if on else '-'}..{max(on) if on else '-'}; "
                                   f"PhaseCoat {pc['first'] if pc else '?'}..{pc['last'] if pc else '?'})")
last = max(r["last"] for r in info["clips"].values())
st = s["stacks"]
check(list(st) == ["Scene"], f"una sola toma 'Scene' ({list(st)})")
if "Scene" in st:
    a, b = st["Scene"]
    check(abs(b * s["fps"] - last) < 1.01, f"la toma llega al último cuadro del sidecar ({b * s['fps']:.1f} vs {last})")
check(s["fps"] == 30, f"30 fps ({s['fps']})")
check(s["video_bytes"] == 0, f"sin texturas embebidas ({s['videos']} referencias, {s['video_bytes']} bytes)")
print("FBX", "OK" if not fails else f"FALLA ({len(fails)})")
sys.exit(1 if fails else 0)
