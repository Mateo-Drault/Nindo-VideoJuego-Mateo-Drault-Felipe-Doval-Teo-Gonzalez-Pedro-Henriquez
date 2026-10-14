"""Chikuō ermitaño (fase C4): modelo, esqueleto, poses de prueba, chequeos, FBX y renders de revisión.

Un solo comando, determinista:
  blender -b --factory-startup --python Tools/Blender/bosses/chikuo_v2/build_chikuo.py -- [opciones]
    --export            escribe Nindo/Assets/Nindo/Art/Characters/BambooMaster/BambooMaster.fbx (+ BambooMaster.fbx.json):
                        el modelo nuevo con los clips de este paso ('BindPose' = el reposo, 'Idle' = parado relajado,
                        'PoseTest' = las poses de prueba); los de la pelea los agrega el paso de animación sobre este
                        mismo esqueleto
    --renders DIR       hojas de revisión en DIR (todas, o las de --sheets)
    --sheets A,B        turnaround, head, details, game, poses, lineup
    --blend PATH        guarda el .blend resultante (para mirar a mano)
    --roundtrip PATH    con --export: huesos y malla deformada en algunos cuadros, para check_chikuo_roundtrip.py
Falla (código 1) si un chequeo no pasa: presupuesto de triángulos, alto y piso del reposo, frente, pesos (todo vértice
con hueso, a lo sumo 4 influencias), huesos del contrato, alcance del IK en las poses de prueba.
"""
import sys, os, json, time
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
SHEETS = set((opt("--sheets") or "turnaround,head,details,game,poses,lineup").split(","))
BLEND = opt("--blend")
ROUNDTRIP = opt("--roundtrip")
RT_BONES = ("Hips", "Head", "Jaw", "Hand_R", "Index_L_2", "Thumb_R_2", "Foot_L", "Toe_R", "Staff", "Staff_Muzzle",
            "Acc_TasselBeard_3", "Cloak_168_2", "Acc_ChimesLo03_0", "Sleeve_L_2", "Lid_R", "Topknot_2")
OUT_DIR = os.path.join(ROOT, "Nindo", "Assets", "Nindo", "Art", "Characters", "BambooMaster")
FBX = os.path.join(OUT_DIR, "BambooMaster.fbx")
# el diseño pide ~9000 en total (doc chikuo_v2 sección 14); por grupo, lo que costó llegar al concepto
BUDGET = {"body": 5400, "cloak": 2300, "chimes": 1400, "staff": 450}
TOTAL_BUDGET = 9200
HOLD = 20                   # cuadros de cada pose en PoseTest
GAP = 10
# huesos de los que dependen el código y los pasos que siguen (animación, pelea): si falta uno, no se exporta
CONTRACT_BONES = (["Root", "Hips", "Spine", "Spine1", "Spine2", "Neck", "Head", "Jaw", "Topknot_1", "Topknot_2", "Staff",
                   "Staff_Muzzle", "Staff_Mouth", "Staff_Flute", "Staff_Grip", "Facing"] +
                  [f"{b}_{S}" for S in "RL" for b in ("Clav", "UpperArm", "Forearm", "Hand", "Thigh", "Shin", "Foot", "Toe", "Lid",
                                                     "Brow", "Cheek", "MouthCorner")] +
                  [f"Sleeve_{S}_{i}" for S in "RL" for i in (1, 2)] + CR.FINGER_BONES +
                  [f"Acc_TasselBeard_{i}" for i in range(4)] + ["Acc_TasselBeard_end", "Acc_LeafKnot_0", "Acc_LeafKnot_1",
                                                                "Acc_LeafKnot_end"] +
                  [f"Acc_TieSash{t}_{i}" for t in "AB" for i in (0, 1)] + ["Acc_TieSashA_end", "Acc_TieSashB_end"] +
                  [CR.skirt_name(a) for a in CR.SKIRT_ANGLES] + [CR.cloak_name(a, s) for a in CR.CLOAK_ANGLES for s in (1, 2)] +
                  [n + sfx for n, *_ in CR.chimes_full() for sfx in ("_0", "_end")])
failures, warnings = [], []


def check(ok, msg, warn=False):
    print(("  ok   " if ok else ("  WARN " if warn else "  FAIL ")) + msg)
    if not ok:
        (warnings if warn else failures).append(msg)


class HeldClip:
    """Un clip hecho de poses ya resueltas (W por cuadro): lo que write_pack necesita."""

    def __init__(self, name, frames_W, loop, notes):
        self.name, self.loop, self.notes = name, loop, notes
        self.frames = len(frames_W) - 1
        self.W = frames_W


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


def main():
    t0 = time.time()
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

    # ---------------------------------------------------------------- poses de prueba
    posed = {}
    for name, *_ in CP.ORDER:
        W, misses = CP.solve(rig, name)
        posed[name] = W
        worst = max(misses.values()) if misses else 0.0
        check(worst <= 0.02, f"pose {name}: las manos y los pies llegan (faltó {worst * 100:.1f} cm)", warn=worst <= 0.05)
    rest = NA.Pose(rig)
    for n in rig.names:
        rest.get(n)
    bind = HeldClip("BindPose", [rest.W] * 31, True, "el reposo (pose A, la del skin): para revisar el modelo en Unity")
    idle = HeldClip("Idle", [posed["relaxed"]] * 31, True, "parado relajado con la flauta en la derecha (la pose 'relaxed' "
                    "quieta): el estado por defecto y la locomoción hasta que el paso de animación traiga los clips")
    ptW = []
    for name, *_ in CP.ORDER:
        ptW += [posed[name]] * HOLD
    pt = HeldClip("PoseTest", ptW, False, "las poses de prueba de la deformación, " + str(HOLD) + " cuadros cada una: "
                  + ", ".join(n for n, *_ in CP.ORDER))
    baked = [(bind, bind.W), (idle, idle.W), (pt, pt.W)]
    act, ranges = NA.write_pack(arm, rig, baked, start=1, gap=GAP)
    last = max(b for a, b in ranges.values())
    scn.frame_set(0)

    # ---------------------------------------------------------------- export
    if EXPORT:
        if failures:
            print("NO SE EXPORTA: fallaron chequeos")
        else:
            NA.export_fbx(FBX, arm, objs, 1, last)
            write_sidecar(ranges, baked, tris, bh)
            if ROUNDTRIP:
                write_roundtrip(scn, arm, meshes["Chikuo_Body"], ranges)
            print("EXPORTADO", FBX, "cuadros 1 ..", last, f"{os.path.getsize(FBX) / 1e6:.1f} MB")

    # ---------------------------------------------------------------- renders
    if RENDERS:
        import chikuo_review as RV
        scn.frame_set(0)
        arm.animation_data.action = None
        rv = RV.Review(arm, rig, meshes, RENDERS)
        if "turnaround" in SHEETS:
            print(rv.turnaround_sheet())
        if "head" in SHEETS:
            print(rv.head_sheet({f: CP.face_pose(rig, f) for f in CP.FACE_POSES}))
        if "details" in SHEETS:
            print(rv.details_sheet())
        if "game" in SHEETS:
            print(rv.game_sheet(perch_W=posed["perch"], hang_W=posed["hang"]))
        if "poses" in SHEETS:
            ps = [(n, posed[n], c, s) for n, _, c, s in CP.ORDER]
            print(rv.pose_sheet(ps[:5], "Chikuō ermitaño: poses de prueba (1/2)", "poses1", [cc for _, cc, _, _ in CP.ORDER[:5]],
                                CP.SHEET_LIFT))
            print(rv.pose_sheet(ps[5:], "Chikuō ermitaño: poses de prueba (2/2)", "poses2", [cc for _, cc, _, _ in CP.ORDER[5:]],
                                CP.SHEET_LIFT))
        if "lineup" in SHEETS:
            print(rv.lineup_sheet())
    finish(t0)


def write_sidecar(ranges, baked, tris, bh):
    clips = {}
    for c, _ in baked:
        a, b = ranges[c.name]
        clips[c.name] = {"first": a, "last": b, "frames": c.frames, "seconds": round(c.frames / NA.FPS, 4), "loop": c.loop,
                         "notes": c.notes}
    info = {
        "fps": NA.FPS, "take": "Scene", "bind_height": bh,
        "bind_height_note": "alto que mide CharacterFactory.NormalizeHeight en la pose por defecto del FBX (el reposo, con la "
                            "flauta parada a la derecha): con este valor en NindoContent la escala es 1",
        "tris": tris, "facing": "frente +Z en Unity (Blender -Y): modelYaw 0",
        "stage": "modelo (fase C4): solo los clips BindPose, Idle (parado relajado) y PoseTest; los de la pelea los agrega el "
                 "paso de animación",
        "clips": clips,
        "pose_test": [n for n, *_ in CP.ORDER], "pose_test_hold_frames": HOLD,
        "contract_bones": CONTRACT_BONES,
        "parts": {"skinned": ["Chikuo_Body"], "rigid": {"Chikuo_Staff": "Staff"}, "materials": ["Nindo_Palette"] + CM.EXTRA_MATS,
                  "notes": "una sola malla con skin (cuerpo, ropa, capa de hojas y los 22 cascabeles) y la flauta-bastón rígida "
                           "en el hueso Staff (siempre visible). Los slots Chikuo_Glint* nacen sin emisión: el jefe los "
                           "enciende por nombre con CharacterGlint.SetGlow (dorado = parry, rojo = dash, blanco = la caña "
                           "cargada). Ninguno se llama 'Glint': Enemy no prende nada solo."},
        "material_rgb": {n: [round(c, 4) for c in rgb] for n, rgb in CM.MAT_RGB.items()},
        "extra_materials": {CM.DECOY_MAT: {"rgb": list(CM.DECOY_RGB), "smoothness": 0.05,
                                           "use": "el señuelo de hojas: la misma malla con todos los slots en este material"}},
        "chains": {"runtime": ["Acc_TasselBeard", "Acc_LeafKnot", "Acc_TieSashA", "Acc_TieSashB"] +
                              [n for n, *_ in CR.chimes_full()],
                   "colliders": [f"AccCol_{n}_{int(round(r * 100))}" for n, _, _, r in CR.CHAIN_COLLIDERS],
                   "baked": ["Topknot_*", "Sleeve_*", "Skirt_*", "Cloak_*"],
                   "notes": "las Acc_* son cadenas de SpringChain (TasselBeard = perfil Tassel, LeafKnot = Leaf, TieSash = Tie, "
                            "Chimes* = Chimes, un hueso por cascabel). La capa, las mangas, la falda y el moño van horneados "
                            "en los clips y NO son Acc_: SpringChain saltea las cadenas colgadas de otra Acc_ y los cascabeles "
                            "cuelgan de la capa. Los paños de la capa que cubren los brazos siguen al brazo en parte "
                            "(chikuo_rig.Poser.follow_cloak, la pose rígida antes de los resortes)."},
        "chimes": {n: {"group": g, "angle_deg": a, "drop": s, "cord_m": cord, "tube_m": ln, "radius_m": r,
                       "parent": CR.chime_parent(a, s)} for n, g, a, s, cord, ln, r in CR.chimes_full()},
        "sockets": {"Staff_Muzzle": "la punta de abajo: de donde salen los dardos", "Staff_Mouth": "la punta de arriba: la "
                    "boquilla de la cerbatana", "Staff_Flute": f"el agujero de soplar de costado ({CR.STAFF_FLUTE} m de la punta "
                    "de arriba)", "Staff_Grip": f"el centro del vendado ({CR.STAFF_GRIP[0]}-{CR.STAFF_GRIP[1]} m de la punta de abajo)"},
        "staff": {"length_m": CR.STAFF_LEN, "radius_m": CR.STAFF_R, "bone": "Staff",
                  "note": "el hueso va de la punta de abajo (cabeza) a la de arriba (cola): Y a lo largo"},
        "face": {"bones": ["Jaw", "Lid_R", "Lid_L", "Brow_R", "Brow_L", "Cheek_R", "Cheek_L", "MouthCorner_R", "MouthCorner_L"],
                 "poses": CR.FACES,
                 "notes": "jaw en grados (+ abre), lids 0 = el reposo (ya entrecerrado) .. 1 = cerrado (60° hacia abajo), brows en "
                          "grados (+ la punta de afuera sube), cheeks 0..1 (1.4 cm afuera), corners (adentro, arriba) en metros"},
        "hand_shapes": CR.HAND_SHAPES,
        "anchors": {"grip_local": list(CR.GRIP_LOCAL), "palm_local": list(CR.PALM_LOCAL),
                    "note": "espacio del hueso de la mano (Y dedos, Z dorso): donde pasa un caño agarrado con el puño"},
    }
    with open(FBX + ".json", "w", encoding="utf-8", newline=chr(10)) as fh:
        json.dump(info, fh, indent=1, ensure_ascii=False)


def write_roundtrip(scn, arm, body, ranges):
    """Dónde quedan algunos huesos y la caja y el centro de la malla deformada en el reposo, en Idle y en el medio de cada
    pose de PoseTest (el FBX importado tiene que dar lo mismo)."""
    a0, _ = ranges["PoseTest"]
    frames = [0, ranges["Idle"][0] + 5] + [a0 + i * HOLD + HOLD // 2 for i in range(len(CP.ORDER))]
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
