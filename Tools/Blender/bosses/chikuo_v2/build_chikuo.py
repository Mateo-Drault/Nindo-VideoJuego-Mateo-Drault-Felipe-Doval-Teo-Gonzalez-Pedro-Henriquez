"""Chikuō ermitaño (fase C4): modelo, esqueleto, clips de pelea, chequeos, FBX y renders de revisión.

Un solo comando, determinista:
  blender -b --factory-startup --python Tools/Blender/bosses/chikuo_v2/build_chikuo.py -- [opciones]
    --export            escribe Nindo/Assets/Nindo/Art/Characters/BambooMaster/BambooMaster.fbx (+ BambooMaster.fbx.json):
                        el modelo con 'BindPose' (el reposo) y todos los clips del contrato (chikuo_clips)
    --only A,B          solo esos clips (iterar; no exporta). Acepta '*' (Perch*)
    --model-only        sin clips: el modelo con BindPose, Idle (la pose relajada) y PoseTest (las poses de prueba), para
                        revisar el modelado
    --renders DIR       hojas de revisión en DIR: una por clip (o las de --sheets) y los avisos con la cámara del juego
    --sheets A,B        con --renders: solo las hojas de esos clips ('none' = ninguna); 'model' suma las del modelo
    --model-sheets A,B  con --renders: hojas del modelo (turnaround, head, details, game, poses, lineup, metric)
    --blend PATH        guarda el .blend resultante (para mirar a mano)
    --roundtrip PATH    con --export: huesos y malla deformada en algunos cuadros, para check_chikuo_roundtrip.py
    --report PATH       las mediciones de cada clip en JSON
    --allow-fail        con --export: exporta aunque fallen chequeos de los clips (los fallidos quedan en el sidecar,
                        'lint_failures', para que se vean en la revisión); los del modelo y del FBX siguen bloqueando
    --lab A,B           con --renders: las poses madre de chikuo_clips.LAB desde cuatro lados (iterar poses sueltas)
Falla (código 1) si un chequeo no pasa: presupuesto de triángulos, alto y piso del reposo, frente, pesos, huesos del
contrato, y en cada clip las mediciones de chikuo_lint (alcance, costura, patinaje, caña, tirones, muñecas, el cuerpo
contra sí mismo, encadenado, piso y culmo atravesados, eventos del contrato).
"""
import sys, os, json, time, fnmatch
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
for p in (HERE, os.path.join(ROOT, "Tools", "Blender"), os.path.join(ROOT, "Tools", "Blender", "anim")):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True

import bpy
from mathutils import Vector
import nindo_lib as L
import nindo_anim as NA
import chikuo_rig as CR
import chikuo_model as CM
import chikuo_poses as CP

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


EXPORT = "--export" in argv
RENDERS = opt("--renders")
ONLY = opt("--only")
MODEL_ONLY = "--model-only" in argv
SHEETS = opt("--sheets")
MODEL_SHEETS = opt("--model-sheets")
BLEND = opt("--blend")
ROUNDTRIP = opt("--roundtrip")
REPORT = opt("--report")
LAB = opt("--lab")
ALLOW_FAIL = "--allow-fail" in argv
RT_BONES = ("Hips", "Head", "Jaw", "Hand_R", "Index_L_2", "Thumb_R_2", "Foot_L", "Toe_R", "Staff", "Staff_Muzzle",
            "Acc_TasselBeard_3", "Cloak_168_2", "Acc_ChimesLo03_0", "Sleeve_L_2", "Lid_R", "Topknot_2")
OUT_DIR = os.path.join(ROOT, "Nindo", "Assets", "Nindo", "Art", "Characters", "BambooMaster")
FBX = os.path.join(OUT_DIR, "BambooMaster.fbx")
# el diseño pedía ~9000 en total (doc chikuo_v2 sección 14); la revisión de arte contra el concepto sumó las hojas de
# adentro de la capa (colgado y con los brazos arriba no se ve la cáscara), las dos coronas del cuello (lo que ve la
# cámara alta) y 26 cascabeles con nudo, lazo y agujeros redondos: ~10.4k, un 13 % más que Mizuchi (un jefe solo en
# pantalla). Por grupo, lo que costó llegar al concepto
BUDGET = {"body": 5650, "cloak": 2500, "chimes": 1900, "staff": 480}
TOTAL_BUDGET = 10450
HOLD = 20                   # cuadros de cada pose en PoseTest (--model-only)
GAP = 4                     # cuadros vacíos entre clips en la toma única (Unity corta por cuadros: no se mezclan)
# huesos de los que dependen el código y los pasos que siguen (animación, pelea): si falta uno, no se exporta
CONTRACT_BONES = (["Root", "Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "Jaw", "Topknot_1", "Topknot_2", "Staff",
                   "Staff_Muzzle", "Staff_Mouth", "Staff_Flute", "Staff_Grip", "Facing"] +
                  [f"{b}_{S}" for S in "RL" for b in ("Clav", "UpperArm", "Forearm", "Hand", "Thigh", "Shin", "Foot", "Toe", "Lid",
                                                     "Brow", "Cheek", "MouthCorner")] +
                  [f"Sleeve_{S}_{i}" for S in "RL" for i in (1, 2)] + CR.FINGER_BONES +
                  [f"Acc_TasselBeard_{i}" for i in range(4)] + ["Acc_TasselBeard_end", "Acc_LeafKnot_0", "Acc_LeafKnot_1",
                                                                "Acc_LeafKnot_end"] +
                  [f"Acc_TieSash{t}_{i}" for t in "AB" for i in (0, 1)] + ["Acc_TieSashA_end", "Acc_TieSashB_end"] +
                  [CR.skirt_name(a) for a in CR.SKIRT_ANGLES] + CR.cloak_bones() +
                  [n + sfx for n, *_ in CR.chimes_full() for sfx in ("_0", "_end")])
failures, warnings = [], []
MODEL_FAILS = []


def check(ok, msg, warn=False):
    print(("  ok   " if ok else ("  WARN " if warn else "  FAIL ")) + msg)
    if not ok:
        (warnings if warn else failures).append(msg)


def wanted(name, pattern):
    return any(fnmatch.fnmatch(name, p.strip()) for p in pattern.split(","))


class HeldClip:
    """Un clip hecho de poses ya resueltas (W por cuadro): lo que write_pack necesita."""

    def __init__(self, name, frames_W, loop, notes):
        self.name, self.loop, self.notes = name, loop, notes
        self.frames = len(frames_W) - 1
        self.W = frames_W
        self.timing, self.events = {"space": "ground"}, []


def bind_height(meshes):
    """La altura que mide CharacterFactory.NormalizeHeight en la pose por defecto del FBX (el reposo): bounds de bind de
    la malla con skin y la caja local de la pieza rígida (la flauta, en el hueso Staff)."""
    lo, hi = 1e9, -1e9
    for o in meshes:
        pts = [o.matrix_world @ Vector(c) for c in o.bound_box] if o.parent_type == 'BONE' else \
            [o.matrix_world @ v.co for v in o.data.vertices]
        for p in pts:
            lo, hi = min(lo, p.z), max(hi, p.z)
    return lo, hi


def check_weights(body):
    """Todo vértice con hueso, la suma en 1 y a lo sumo 4 influencias (Unity corta en 4: lo de más se perdería)."""
    gi = {g.index: g.name for g in body.vertex_groups}
    bones = set(b.name for b in body.parent.data.bones)
    bad_none, bad_sum, bad_many, unknown = 0, 0, 0, set()
    for v in body.data.vertices:
        ws = [(gi[g.group], g.weight) for g in v.groups if g.weight > 1e-5]
        if not ws:
            bad_none += 1
            continue
        if abs(sum(w for _, w in ws) - 1.0) > 0.01:
            bad_sum += 1
        if len(ws) > 4:
            bad_many += 1
        unknown |= {n for n, _ in ws if n not in bones}
    check(bad_none == 0, f"todo vértice tiene hueso ({bad_none} sin pesos)")
    check(bad_sum == 0, f"los pesos suman 1 ({bad_sum} vértices fuera)")
    check(bad_many == 0, f"a lo sumo 4 influencias por vértice ({bad_many} con más)")
    check(not unknown, f"los grupos son huesos del esqueleto (sobran {sorted(unknown)[:6]})")


# grosor de cada perfil de SpringChain (SpringChain.ProfileFor, 'radius'): la esfera más esto no puede tocar la cadena
SPRING_RADIUS = {"Tassel": 0.05, "Leaf": 0.03, "Tie": 0.04, "Chimes": 0.05}
RUNTIME_CHAINS = [("TasselBeard", 4, "Tassel"), ("LeafKnot", 2, "Leaf"), ("TieSashA", 2, "Tie"), ("TieSashB", 2, "Tie")]


def check_chain_clearance(W, label):
    """Ninguna articulación que simula SpringChain (de la segunda a la punta) arranca adentro de una esfera AccCol_*:
    la esfera la empujaría en reposo y la cadena temblaría o quedaría corrida (todas las cadenas chocan con todas)."""
    chains = RUNTIME_CHAINS + [(n[len("Acc_"):], 1, "Chimes") for n, *_ in CR.chimes_full()]
    spheres = [(W[bn].translation, r, bn) for bn, _, _, r in CR.collider_specs()]
    bad = []
    for name, n, kind in chains:
        joints = [W[f"Acc_{name}_{i}"].translation for i in range(1, n)] + [W[f"Acc_{name}_end"].translation]
        for j in joints:
            for c, r, bn in spheres:
                d = (j - c).length - r - SPRING_RADIUS[kind]
                if d < -0.002:
                    bad.append(f"{name}/{bn} {d * 100:.1f} cm")
    check(not bad, f"{label}: ninguna cadena arranca adentro de una esfera ({len(bad)}: {bad[:4]})")


def seg_dist(p0, p1, q0, q1):
    """Distancia mínima entre dos segmentos (muestreada: los tubos son cortos)."""
    best = 1e9
    for i in range(9):
        a = p0.lerp(p1, i / 8.0)
        d = q1 - q0
        t = max(0.0, min(1.0, (a - q0).dot(d) / max(1e-9, d.length_squared)))
        best = min(best, (a - (q0 + d * t)).length)
    return best


def check_chime_spacing(W, label):
    """Los ejes de dos tubos nunca a menos de 2.2 radios en reposo (no se tocan ni se funden en uno)."""
    tubes = []
    for n, g, a, s, cord, ln, r in CR.chimes_full():
        h, t = W[n + "_0"].translation, W[n + "_end"].translation
        ax = (t - h).normalized()
        tubes.append((n, h + ax * cord, t, r))
    bad = []
    for i in range(len(tubes)):
        for j in range(i + 1, len(tubes)):
            ni, a0, a1, ri = tubes[i]
            nj, b0, b1, rj = tubes[j]
            d = seg_dist(a0, a1, b0, b1)
            if d < 2.2 * max(ri, rj):
                bad.append(f"{ni[-4:]}/{nj[-4:]} {d * 100:.1f} cm")
    check(not bad, f"{label}: cascabeles separados (ejes a 2.2 r o más; {len(bad)} pares: {bad[:4]})")


def model_and_checks():
    L.clear_scene()
    scn = bpy.context.scene
    scn.render.fps = NA.FPS
    arm = NA.build_armature("BambooMaster", CR.bones(), data_name="BambooMasterRig")
    rig = NA.Rig(arm)
    meshes, tris = CM.build(arm, rig)
    total = sum(tris.values())
    print("TRIS", json.dumps(tris), "total", total)
    for k, lim in BUDGET.items():
        check(tris[k] <= lim, f"{k}: {tris[k]} tris (presupuesto {lim})")
    check(total <= TOTAL_BUDGET, f"total {total} tris (presupuesto {TOTAL_BUDGET})")
    bpy.context.view_layer.update()
    objs = list(meshes.values())
    zlo, zhi = bind_height(objs)
    bh = round(zhi - zlo, 3)
    check(abs(zlo) <= 0.005, f"nada bajo el piso en reposo y los pies en y=0 en Unity (min z {zlo:.3f})")
    check(abs(zhi - CR.TOP) <= 0.02, f"alto hasta la punta del moño {zhi:.3f} m (diseño {CR.TOP})")
    print(f"  bind_height (medida de Unity) {bh}")
    fb = arm.data.bones["Facing"]
    check((fb.tail_local - fb.head_local).normalized().y < -0.99, "marcador Facing mira a -Y (Unity +Z)")
    body = meshes["Chikuo_Body"]
    nose = min((v.co for v in body.data.vertices if 2.08 < v.co.z < 2.2), key=lambda c: c.y)
    check(nose.y < -0.15, f"la cara mira adelante (-Y): la nariz en y {nose.y:.2f}")
    for S in "RL":
        tb = arm.data.bones["Thumb_%s_1" % S].head_local
        pb = arm.data.bones["Pinky_%s_1" % S].head_local
        check(tb.y < pb.y, f"mano {S}: el pulgar adelante, el meñique atrás")
    names = set(b.name for b in arm.data.bones)
    missing = [n for n in CONTRACT_BONES if n not in names]
    check(not missing, f"huesos del contrato ({len(names)} huesos; faltan {missing[:8]})")
    check_weights(body)
    return scn, arm, rig, meshes, tris, bh


def main():
    t0 = time.time()
    scn, arm, rig, meshes, tris, bh = model_and_checks()
    # los del modelo (presupuesto, alto, pesos, huesos) bloquean la exportación aun con --allow-fail
    MODEL_FAILS.extend(failures)
    if LAB:
        import chikuo_bake as CB
        CB.lab_sheet(arm, rig, meshes, RENDERS, [n.strip() for n in LAB.split(",")])
        finish(t0)
        return
    objs = list(meshes.values())
    body = meshes["Chikuo_Body"]
    rest = NA.Pose(rig)
    for n in rig.names:
        rest.get(n)
    bind = HeldClip("BindPose", [rest.W] * 31, True, "el reposo (pose A, la del skin): para revisar el modelo en Unity")
    posed = {}
    reports = {}
    if MODEL_ONLY:
        for name, *_ in CP.ORDER:
            W, misses = CP.solve(rig, name)
            posed[name] = W
            worst = max(misses.values()) if misses else 0.0
            check(worst <= 0.02, f"pose {name}: las manos y los pies llegan (faltó {worst * 100:.1f} cm)", warn=worst <= 0.05)
        idle = HeldClip("Idle", [posed["relaxed"]] * 31, True, "parado relajado con la flauta en la derecha")
        ptW = []
        for name, *_ in CP.ORDER:
            ptW += [posed[name]] * HOLD
        pt = HeldClip("PoseTest", ptW, False, "las poses de prueba de la deformación, " + str(HOLD) + " cuadros cada una")
        baked = [(bind, bind.W), (idle, idle.W), (pt, pt.W)]
        data = {}
    else:
        import chikuo_clips as CC
        import chikuo_bake as CB
        clips = CC.clips(rig)
        if ONLY:
            keep = [c for c in clips if wanted(c.name, ONLY)]
            # las poses de referencia del encadenado se hornean igual (el lint compara contra ellas), y las de ellas
            by_name = {c.name: c for c in clips}
            refs, todo = set(), list(keep)
            while todo:
                c = todo.pop()
                for k in (c.timing.get("chain_from"), c.timing.get("chain_to")):
                    r = CC.chain_ref(k)[0] if k in CC.CHAIN_REF else None
                    if r and r not in refs and r in by_name:
                        refs.add(r)
                        todo.append(by_name[r])
            clips = [c for c in clips if c in keep or c.name in refs]
        data = CB.bake_all(rig, clips, check)
        reports = {n: d["report"] for n, d in data.items()}
        baked = [(bind, bind.W)] + [(c, data[c.name]["frames"]) for c in clips]
    _, ranges = NA.write_pack(arm, rig, baked, start=1, gap=GAP)
    last = max(b for _, b in ranges.values())
    scn.frame_set(0)
    n0 = len(failures)
    check_chain_clearance(rest.W, "reposo")
    check_chime_spacing(rest.W, "reposo")
    MODEL_FAILS.extend(failures[n0:])
    if not MODEL_ONLY:
        import chikuo_bake as CB
        CB.mesh_checks(scn, meshes, data, ranges, check)
    if REPORT:
        os.makedirs(os.path.dirname(os.path.abspath(REPORT)), exist_ok=True)
        with open(REPORT, "w", encoding="utf-8", newline=chr(10)) as fh:
            json.dump(reports, fh, indent=1, ensure_ascii=False)

    # ---------------------------------------------------------------- export
    if EXPORT:
        model_fails = [f for f in failures if f in MODEL_FAILS]
        if failures and (not ALLOW_FAIL or model_fails):
            print("NO SE EXPORTA: fallaron chequeos")
        elif ONLY:
            print("NO SE EXPORTA: --only hornea una parte de los clips")
        else:
            NA.export_fbx(FBX, arm, objs, 1, last)
            write_sidecar(ranges, baked, data, tris, bh, failures)
            if ROUNDTRIP:
                write_roundtrip(scn, arm, body, ranges, baked)
            print("EXPORTADO", FBX, "cuadros 1 ..", last, f"{os.path.getsize(FBX) / 1e6:.1f} MB")

    # ---------------------------------------------------------------- renders
    if RENDERS:
        scn.frame_set(0)
        arm.animation_data.action = None
        if MODEL_SHEETS or MODEL_ONLY:
            model_sheets(arm, rig, meshes, posed or {n: CP.solve(rig, n)[0] for n, *_ in CP.ORDER})
        if not MODEL_ONLY and SHEETS != "none":
            import chikuo_bake as CB
            CB.clip_sheets(arm, rig, meshes, RENDERS, baked, data, SHEETS)
    finish(t0)


def model_sheets(arm, rig, meshes, posed):
    import chikuo_review as RV
    sheets = set((MODEL_SHEETS or "turnaround,head,details,game,poses,lineup,metric").split(","))
    rv = RV.Review(arm, rig, meshes, RENDERS)
    if "turnaround" in sheets:
        print(rv.turnaround_sheet())
    if "head" in sheets:
        print(rv.head_sheet({f: CP.face_pose(rig, f) for f in CP.FACE_POSES}))
    if "details" in sheets:
        print(rv.details_sheet())
    if "game" in sheets:
        print(rv.game_sheet(perch_W=posed["perch"], hang_W=posed["hang"]))
    if "poses" in sheets:
        ps = [(n, posed[n], c, s) for n, _, c, s in CP.ORDER]
        print(rv.pose_sheet(ps[:5], "Chikuō ermitaño: poses de prueba (1/2)", "poses1", [cc for _, cc, _, _ in CP.ORDER[:5]],
                            CP.SHEET_LIFT))
        print(rv.pose_sheet(ps[5:], "Chikuō ermitaño: poses de prueba (2/2)", "poses2", [cc for _, cc, _, _ in CP.ORDER[5:]],
                            CP.SHEET_LIFT))
    if "lineup" in sheets:
        print(rv.lineup_sheet())
    if "metric" in sheets:
        print(rv.metric_sheet(("front", "side"), "metric_body"))
        print(rv.metric_sheet(("q34", "back"), "metric_body2"))
        print(rv.metric_sheet(("head_front", "head_side", "head_back"), "metric_head"))


def write_sidecar(ranges, baked, data, tris, bh, fails=()):
    import chikuo_bake as CB
    import chikuo_clips as CC
    clips = {}
    for c, _ in baked:
        a, b = ranges[c.name]
        clips[c.name] = CB.sidecar_clip(c, a, b, data.get(c.name))
    info = {
        "fps": NA.FPS, "take": "Scene", "bind_height": bh,
        "bind_height_note": "alto que mide CharacterFactory.NormalizeHeight en la pose por defecto del FBX (el reposo, con la "
                            "flauta parada a la derecha): con este valor en NindoContent la escala es 1",
        "tris": tris, "facing": "frente +Z en Unity (Blender -Y): modelYaw 0",
        "stage": "clips de pelea (fase C4): el contrato de Docs/handoff/diseno/chikuo_v2.md sección 16",
        "clips": clips,
        "lint_failures": list(fails),
        "aliases": CC.ALIASES,
        "spaces": CB.SPACES_NOTE,
        "stalk": CB.stalk_note(),
        "contract_bones": CONTRACT_BONES,
        "parts": {"skinned": ["Chikuo_Body"], "rigid": {"Chikuo_Staff": "Staff"}, "materials": ["Nindo_Palette"] + CM.EXTRA_MATS,
                  "notes": "una sola malla con skin (cuerpo, ropa, capa de hojas y los 26 cascabeles) y la flauta-bastón rígida "
                           "en el hueso Staff (siempre visible). Los slots Chikuo_Glint* nacen sin emisión: el jefe los "
                           "enciende por nombre con CharacterGlint.SetGlow (dorado = parry, rojo = dash, blanco = la caña "
                           "cargada). Ninguno se llama 'Glint': Enemy no prende nada solo."},
        "material_rgb": {n: [round(c, 4) for c in rgb] for n, rgb in CM.MAT_RGB.items()},
        "chains": {"runtime": ["Acc_TasselBeard", "Acc_LeafKnot", "Acc_TieSashA", "Acc_TieSashB"] +
                              [n for n, *_ in CR.chimes_full()],
                   "colliders": [n for n, *_ in CR.collider_specs()],
                   "baked": ["Topknot_*", "Sleeve_*", "Skirt_*", "Cloak_*"],
                   "notes": "las Acc_* son cadenas de SpringChain (TasselBeard = perfil Tassel, LeafKnot = Leaf, TieSash = Tie, "
                            "Chimes* = Chimes, un hueso por cascabel) y vienen horneadas en cada clip (la física del juego "
                            "las sigue con stiffness y un tope de ángulo desde esa pose: colgado, los cascabeles ya caen al "
                            "piso en el clip). La capa, las mangas, la falda y el moño van horneados y NO son Acc_: "
                            "SpringChain saltea las cadenas colgadas de otra Acc_ y los cascabeles cuelgan de la capa."},
        "chimes": {n: {"group": g, "angle_deg": a, "drop": s, "cord_m": cord, "tube_m": ln, "radius_m": r,
                       "parent": CR.chime_parent(a, s)} for n, g, a, s, cord, ln, r in CR.chimes_full()},
        "sockets": {"Staff_Muzzle": "la punta de abajo: de donde salen los dardos", "Staff_Mouth": "la punta de arriba: la "
                    "boquilla de la cerbatana", "Staff_Flute": f"el agujero de soplar de costado ({CR.STAFF_FLUTE} m de la punta "
                    "de arriba)", "Staff_Grip": f"el centro del vendado ({CR.STAFF_GRIP[0]}-{CR.STAFF_GRIP[1]} m de la punta de abajo)"},
        "staff": {"length_m": CR.STAFF_LEN, "radius_m": CR.STAFF_R, "bone": "Staff",
                  "note": "el hueso va de la punta de abajo (cabeza) a la de arriba (cola): Y a lo largo"},
        "face": {"bones": ["Jaw", "Lid_R", "Lid_L", "Brow_R", "Brow_L", "Cheek_R", "Cheek_L", "MouthCorner_R", "MouthCorner_L"],
                 "poses": CR.FACES},
        "hand_shapes": CR.HAND_SHAPES,
        "anchors": {"grip_local": list(CR.GRIP_LOCAL), "palm_local": list(CR.PALM_LOCAL),
                    "note": "espacio del hueso de la mano (Y dedos, Z dorso): donde pasa un caño agarrado con el puño"},
    }
    with open(FBX + ".json", "w", encoding="utf-8", newline=chr(10)) as fh:
        json.dump(info, fh, indent=1, ensure_ascii=False)


def write_roundtrip(scn, arm, body, ranges, baked):
    """Dónde quedan algunos huesos y la caja y el centro de la malla deformada en el reposo y en el primer cuadro, el
    del medio y el último de algunos clips (el FBX importado tiene que dar lo mismo: un corrimiento de un cuadro en la
    toma se ve ahí)."""
    frames = [0]
    for c, _ in baked[:: max(1, len(baked) // 14)]:
        a, b = ranges[c.name]
        frames += [a, (a + b) // 2, b]
    rt = {}
    for f in frames:
        scn.frame_set(f)
        bpy.context.view_layer.update()
        w = NA.world_verts(body, bpy.context.evaluated_depsgraph_get())
        rt[f] = {"bones": {b: list(arm.matrix_world @ arm.pose.bones[b].head) for b in RT_BONES},
                 "mesh": [w.min(axis=0).tolist(), w.max(axis=0).tolist(), w.mean(axis=0).tolist()]}
    os.makedirs(os.path.dirname(os.path.abspath(ROUNDTRIP)), exist_ok=True)
    with open(ROUNDTRIP, "w", encoding="utf-8", newline=chr(10)) as fh:
        json.dump(rt, fh)
    scn.frame_set(0)


def finish(t0):
    if BLEND:
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print(f"listo en {time.time() - t0:.1f} s; avisos {len(warnings)}")
    for w in warnings:
        print("   aviso:", w)
    if failures:
        print("FALLARON", len(failures), "chequeos:")
        for f in failures:
            print("   -", f)
        sys.exit(1)


main()
