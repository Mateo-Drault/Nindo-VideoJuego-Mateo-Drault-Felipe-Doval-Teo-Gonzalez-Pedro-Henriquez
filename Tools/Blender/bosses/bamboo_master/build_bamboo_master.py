"""Chikuō, el Maestro del Bambú: modelo, esqueleto, clips de prueba, chequeos, FBX y renders de revisión.

Un solo comando, determinista:
  blender -b --factory-startup --python Tools/Blender/bosses/bamboo_master/build_bamboo_master.py -- [opciones]
    --export            escribe Nindo/Assets/Nindo/Art/Characters/BambooMaster/BambooMaster.fbx (+ BambooMaster.fbx.json)
    --renders DIR       hojas de revisión (modelo, poses de prueba, manos, elenco) en DIR
    --model-only        sin clips (iterar el modelado)
    --blend PATH        guarda el .blend resultante (para mirar a mano)
    --lineup            con --renders: solo la hoja del elenco (Kaito, el abuelo, ninja, sumo, Chikuō)
    --detail            con --renders: además las poses de prueba grandes desde tres lados (deformación)
    --report PATH       el detalle de las mediciones en JSON (con --renders va en DIR)
    --roundtrip PATH    con --export: dónde quedan algunos huesos cuadro a cuadro, para check_master_roundtrip.py
Falla (código 1) si un chequeo no pasa: frente, apoyo en el piso, presupuesto de triángulos, altura máxima de la
silueta, nada bajo el piso, alcance de manos y pies, deriva de los pies apoyados y costura de los loops.
Los clips de pelea son de la etapa 2 (master_clips.py): acá solo 'Idle' (provisorio) y 'PoseTest'.
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
import master_rig as MR
import master_model as MM

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


EXPORT = "--export" in argv
RENDERS = opt("--renders")
MODEL_ONLY = "--model-only" in argv
BLEND = opt("--blend")
REPORT = opt("--report")
OUT_DIR = os.path.join(ROOT, "Nindo", "Assets", "Nindo", "Art", "Characters", "BambooMaster")
FBX = os.path.join(OUT_DIR, "BambooMaster.fbx")
HEIGHT_CAP = 3.6         # con el bastón arriba o una patada alta; el reposo mide ~2.7
GAP = 10                 # cuadros vacíos entre clips en la toma única
BUDGET = {"body": 4800, "robe": 2400, "thrown": 500, "staff": 450}
ROUNDTRIP = opt("--roundtrip")
ROUNDTRIP_BONES = ("Hips", "Head", "Hand_R", "Hand_L", "Index_R_2", "Thumb_L_2", "Foot_R", "Toe_L", "Staff", "Acc_TieSashA_2",
                   "Robe_038_2", "Brow_R_2")
failures, warnings = [], []


def check(ok, msg, warn=False):
    print(("  ok   " if ok else ("  WARN " if warn else "  FAIL ")) + msg)
    if not ok:
        (warnings if warn else failures).append(msg)


def foot_points(rig):
    """Bola del pie (lo que apoya y no puede patinar) y los pivotes de punta y talón, en el espacio de Foot_*."""
    gp, piv = {}, {}
    for S in "RL":
        fb = "Foot_" + S
        x = MR.ANKLE.x * (1 if S == "R" else -1)
        gp[fb] = rig.rest_inv[fb] @ Vector((x, MR.SOLE_BALL_Y, 0.0))
        piv[fb] = [rig.rest_inv[fb] @ Vector((x, MR.SOLE_TOE_Y, 0.0)), rig.rest_inv[fb] @ Vector((x, MR.SOLE_HEEL_Y, 0.0))]
    return gp, piv


def lint_clip(rig, clip, frames, ctrls, roots, misses):
    rep = {}
    mh = max(max(m["hand_r"], m["hand_l"]) for m in misses)
    ml = max(m["legs"] for m in misses)
    fh = max(range(len(misses)), key=lambda i: max(misses[i]["hand_r"], misses[i]["hand_l"]))
    fl = max(range(len(misses)), key=lambda i: misses[i]["legs"])
    rep["reach_miss_cm"] = {"hands": round(mh * 100, 1), "legs": round(ml * 100, 1)}
    check(ml <= 0.02, f"{clip.name}: los pies llegan (faltó {ml * 100:.1f} cm en f{fl})")
    check(mh <= 0.02, f"{clip.name}: las manos llegan (faltó {mh * 100:.1f} cm en f{fh})", warn=mh <= 0.05)
    gp, piv = foot_points(rig)
    plants = NA.plant_report(rig, frames, roots, list(gp), gp, pivots=piv)
    worst = max([p["drift_cm"] for v in plants.values() for p in v] or [0.0])
    rep["plants"] = plants
    # la prueba de poses desliza los pies entre poses a propósito (no es un clip de juego)
    if clip.timing.get("kind") != "test":
        check(worst <= 2.0, f"{clip.name}: pies apoyados quietos (deriva máx. {worst:.2f} cm)")
    if clip.loop:
        seam, step = NA.loop_seam_deg(rig, frames)
        rep["loop_seam_deg"] = seam
        check(seam <= 0.5, f"{clip.name}: costura del loop {seam:.3f}° (salto típico {step:.2f}°)")
    return rep


def bind_height(meshes):
    """La altura que mide CharacterFactory.NormalizeHeight en la pose por defecto del FBX (el reposo): la unión de los
    bounds de bind de las mallas con skin y de las cajas locales de las piezas rígidas, ocultas incluidas."""
    lo, hi = 1e9, -1e9
    for o in meshes:
        if o.parent_type == 'BONE':
            pts = [o.matrix_world @ Vector(c) for c in o.bound_box]
        else:
            pts = [o.matrix_world @ v.co for v in o.data.vertices]
        for p in pts:
            lo, hi = min(lo, p.z), max(hi, p.z)
    return lo, hi


def main():
    t0 = time.time()
    L.clear_scene()
    scn = bpy.context.scene
    scn.render.fps = NA.FPS
    arm = NA.build_armature("BambooMaster", MR.bones(), data_name="BambooMasterRig")
    rig = NA.Rig(arm)
    meshes, tris = MM.build(arm, rig)
    print("TRIS", json.dumps(tris), "total", sum(tris.values()))
    for k, lim in BUDGET.items():
        check(tris[k] <= lim, f"{k}: {tris[k]} tris (presupuesto {lim})")
    bpy.context.view_layer.update()
    objs = list(meshes.values())
    zlo, zhi = bind_height(objs)
    bh = round(zhi - zlo, 3)
    check(abs(zlo) <= 0.005, f"nada bajo el piso en reposo y los pies en y=0 en Unity (min z {zlo:.3f})")
    print(f"  bind_height (medida de Unity) {bh}")
    fb = arm.data.bones["Facing"]
    check((fb.tail_local - fb.head_local).normalized().y < -0.99, "marcador Facing mira a -Y (Unity +Z)")
    nose = max((v.co for v in meshes["Master_Body"].data.vertices if v.co.z > 2.25), key=lambda c: -c.y)
    check(nose.y < -0.17, f"la cara mira adelante (-Y): la nariz en y {nose.y:.2f}")
    for S in "RL":
        tb = arm.data.bones["Thumb_%s_1" % S].head_local
        ib = arm.data.bones["Index_%s_1" % S].head_local
        pb = arm.data.bones["Pinky_%s_1" % S].head_local
        check(tb.y < pb.y and ib.y < pb.y, f"mano {S}: el pulgar y el índice adelante, el meñique atrás")
    info = {"fps": NA.FPS, "take": "Scene", "bind_height": bh,
            "bind_height_note": "alto que mide CharacterFactory.NormalizeHeight en la pose por defecto del FBX (el reposo, "
                                "con el saco tirado y el bastón ocultos incluidos): con este valor en NindoContent la escala es 1",
            "tris": tris, "facing": "frente +Z en Unity (Blender -Y): modelYaw 0"}

    rv = None
    if RENDERS:
        import master_review as RV
    if MODEL_ONLY:
        if RENDERS:
            rv = RV.Review(arm, meshes, RENDERS)
            if "--lineup" in argv:
                print(rv.lineup_sheet())
            else:
                print(rv.model_sheet())
        finish(t0)
        return

    # ---------------------------------------------------------------- clips
    import master_poses as MP
    solver = MR.Solver(rig)
    sprs = MR.springs(rig)
    baked, reports, rootsd, ctrlsd = [], {}, {}, {}
    for clip in MP.CLIPS:
        misses = []

        def solve(pose, c):
            misses.append(dict(solver.solve(pose, c)))
        frames, ctrls, roots = NA.bake_clip(rig, clip, solve, sprs)
        reports[clip.name] = lint_clip(rig, clip, frames, ctrls, roots, misses)
        baked.append((clip, frames))
        rootsd[clip.name] = roots
        ctrlsd[clip.name] = ctrls
    act, ranges = NA.write_pack(arm, rig, baked, start=1, gap=GAP)
    last = max(b for a, b in ranges.values())
    # techo y piso de la silueta en todos los cuadros (mallas evaluadas): el saco tirado vive escondido adentro del
    # cuerpo y el bastón solo cuenta cuando está en uso
    vis = [meshes["Master_Body"], meshes["Master_Robe"]]
    for clip, frames in baked:
        a, b = ranges[clip.name]
        rows = NA.mesh_z_frames(vis + [meshes["Master_Staff"]], range(a, b + 1))
        hi = [max(v[1] for v in r.values()) for r in rows]
        top = max(range(len(hi)), key=lambda i: hi[i])
        reports[clip.name]["max_height_m"] = round(hi[top], 2)
        check(hi[top] <= HEIGHT_CAP, f"{clip.name}: silueta {hi[top]:.2f} m en f{top} (tope {HEIGHT_CAP})")
        lows = [min((v[0], i, k) for k, v in r.items()) for i, r in enumerate(rows)]
        lo = min(lows)
        bad = [i for z, i, _ in lows if z < -0.03]
        reports[clip.name]["min_z_m"] = round(lo[0], 3)
        check(not bad, f"{clip.name}: nada atraviesa el piso (mín {lo[0]:.3f} m en f{lo[1]}, {lo[2]}; {len(bad)} cuadros bajo -3 cm)")
    scn.frame_set(0)
    if RENDERS or REPORT:
        path = REPORT or os.path.join(RENDERS, "lint_report.json")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline=chr(10)) as fh:
            json.dump(reports, fh, indent=0)

    # ---------------------------------------------------------------- export
    if EXPORT:
        if failures:
            print("NO SE EXPORTA: fallaron chequeos")
        else:
            NA.export_fbx(FBX, arm, objs, 1, last)
            # referencia para la ida y vuelta (check_master_roundtrip.py): dónde quedan algunos huesos en el mundo en
            # cuadros de toda la toma (manos, dedos, pies, bastón, una cola de la faja)
            if ROUNDTRIP:
                write_roundtrip(scn, arm, last)
            clipd = {}
            for clip, frames in baked:
                a, b = ranges[clip.name]
                rec = {"first": a, "last": b, "frames": clip.frames, "seconds": round(clip.frames / NA.FPS, 4), "loop": clip.loop,
                       "timing": clip.timing, "events": [], "notes": clip.notes,
                       "lint": {k: v for k, v in reports[clip.name].items() if k != "plants"}}
                clipd[clip.name] = rec
            info["clips"] = clipd
            info["parts"] = {
                "skinned": ["Master_Body", "Master_Robe", "Master_RobeThrown"], "rigid": {"Master_Staff": "Staff"},
                "materials": ["Nindo_Palette"] + MM.EXTRA_MATS,
                "hidden_at_spawn": ["Master_RobeThrown", "Master_Staff"],
                "notes": "Master_Robe es el saco de la fase 1 (se apaga al tirarlo); Master_RobeThrown es la copia aplanada que "
                         "vuela en el cambio de fase (huesos RobeT_*, en reposo adentro de la espalda); Master_Staff es el bastón "
                         "(hueso Staff, hijo de Root: lo mueve el clip y las manos lo agarran). Los slots Master_Glint* se encienden "
                         "por nombre con CharacterGlint.SetGlow (dorado = parry, rojo = dash) y Master_Eyes en jade en la fase 2. "
                         "Ninguno se llama 'Glint': Enemy no prende nada solo, el jefe elige el miembro que pega."}
            info["chains"] = {"runtime": ["Acc_TieWhiskerR", "Acc_TieWhiskerL", "Acc_TieSashA", "Acc_TieSashB"],
                              "colliders": [f"AccCol_{n}_{int(round(r * 100))}" for n, _, _, r in MR.CHAIN_COLLIDERS],
                              "baked": ["Brow_*", "Sleeve_*", "Robe_*"],
                              "notes": "las cadenas Acc_* van horneadas en los clips; si el jefe agrega SpringChain y llama "
                                       "Rebuild, la física del juego las reemplaza (perfil 'Tie')"}
            # colores de los materiales propios (valores de pantalla: el proyecto es Gamma); generate_assets.py los lee de acá
            info["material_rgb"] = {n: [round(c, 4) for c in rgb] for n, rgb in MM.MAT_RGB.items()}
            info["hand_shapes"] = MR.HAND_SHAPES
            info["staff"] = {"length_m": MR.STAFF_LEN, "radius_m": MR.STAFF_R, "bone": "Staff",
                             "tip_local_unity_note": "el hueso va de la punta de abajo (cabeza) a la de arriba (cola): las dos "
                                                     "puntas son la cabeza y la cabeza + Y * largo"}
            with open(FBX + ".json", "w", encoding="utf-8", newline=chr(10)) as fh:
                json.dump(info, fh, indent=1, ensure_ascii=False)
            print("EXPORTADO", FBX, "cuadros 1 ..", last, f"{os.path.getsize(FBX) / 1e6:.1f} MB")

    # ---------------------------------------------------------------- renders
    if RENDERS:
        rv = RV.Review(arm, meshes, RENDERS)
        a0, _ = ranges["Idle"]
        if "--lineup" in argv:
            print(rv.lineup_sheet(a0))
            finish(t0)
            return
        print(rv.model_sheet(frame=0))
        clip, marks = MP.pose_test_clip()
        p0, _ = ranges["PoseTest"]
        hold = {lab: p0 + f for f, lab in marks.items()}
        poses = [(a0, "Idle (guardia, fase 1)", 1, (), "gold"),
                 (hold["caballo y palma"], "caballo y palma (aviso dorado)", 1, ("Master_GlintHandR",), "gold"),
                 (hold["patada de grulla"], "patada de grulla (sin saco)", 2, ("Master_GlintFootR",), "red"),
                 (hold["patada de grulla"], "patada de grulla (con saco)", 1, (), "gold"),
                 (hold["bastón"], "bastón", 3, ("Master_GlintStaff",), "gold")]
        print(rv.pose_sheet(poses))
        if "--detail" in argv:
            print(rv.detail_sheet([(hold["caballo y palma"], "caballo y palma", 1), (hold["patada de grulla"], "patada con saco", 1),
                                   (hold["patada de grulla"], "patada sin saco", 2), (hold["bastón"], "bastón", 3),
                                   (hold["puño y espada"], "saco tirado en el aire", 2, True)]))
        print(rv.hands_sheet([(hold["caballo y palma"], "palma / puño"), (hold["garra y pico"], "garra / pico"),
                              (hold["puño y espada"], "puño / espada"), (hold["bastón"], "agarre")]))
        print(rv.lineup_sheet(a0))
    finish(t0)


def write_roundtrip(scn, arm, last):
    rt = {}
    for f in range(1, last + 1, 7):
        scn.frame_set(f)
        bpy.context.view_layer.update()
        rt[f] = {b: list(arm.matrix_world @ arm.pose.bones[b].head) for b in ROUNDTRIP_BONES}
    os.makedirs(os.path.dirname(os.path.abspath(ROUNDTRIP)), exist_ok=True)
    with open(ROUNDTRIP, "w", encoding="utf-8", newline=chr(10)) as fh:
        json.dump(rt, fh)
    scn.frame_set(0)


def finish(t0):
    if BLEND:
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print(f"listo en {time.time() - t0:.1f} s; avisos {len(warnings)}")
    if failures:
        print("FALLARON", len(failures), "chequeos:")
        for f in failures:
            print("   -", f)
        sys.exit(1)


main()
