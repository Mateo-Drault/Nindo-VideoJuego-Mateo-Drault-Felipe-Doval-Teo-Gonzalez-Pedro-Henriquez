"""Chikuō, el Maestro del Bambú: modelo, esqueleto, clips, chequeos, FBX y renders de revisión.

Un solo comando, determinista:
  blender -b --factory-startup --python Tools/Blender/bosses/bamboo_master/build_bamboo_master.py -- [opciones]
    --export            escribe Nindo/Assets/Nindo/Art/Characters/BambooMaster/BambooMaster.fbx (+ BambooMaster.fbx.json)
    --renders DIR       hojas de revisión (modelo, una por clip, elenco) en DIR
    --only A,B          solo esos clips (para iterar; no exporta). Acepta prefijos con '*' (Palm*)
    --sheets A,B        con --renders: solo las hojas de esos clips (todos se miden igual)
    --lab A,B           con --renders: hoja de las poses con nombre de master_clips.POSES (iterar poses sueltas)
    --model-only        sin clips (iterar el modelado)
    --blend PATH        guarda el .blend resultante (para mirar a mano)
    --lineup            con --renders: solo la hoja del elenco (Kaito, el abuelo, ninja, sumo, Chikuō)
    --detail            con --renders: además las poses de prueba grandes desde tres lados (deformación)
    --report PATH       el detalle de las mediciones en JSON (con --renders va en DIR)
    --roundtrip PATH    con --export: dónde quedan algunos huesos cuadro a cuadro, para check_master_roundtrip.py
    --slipdump A,B      la altura de la suela y el pivote de cada pie cuadro a cuadro (iterar los apoyos)
    --frames 1,5,9      con --sheets: esos cuadros en las hojas (en vez de las claves)
Falla (código 1) si un chequeo no pasa: frente, apoyo en el piso, presupuesto de triángulos, altura de la silueta, nada
bajo el piso, alcance de manos y pies, deriva de los pies apoyados, costura de los loops, cuerpo contra sí mismo,
avance que se teletransporta con el reloj del juego, punta rápida fuera del golpe, aviso que no cambia la silueta,
encadenado contra la guardia y variantes de fase distintas de su clip base.
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
import master_rig as MR
import master_model as MM
import master_lint as ML
import master_springs as MS

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


EXPORT = "--export" in argv
RENDERS = opt("--renders")
ONLY = opt("--only")
SHEETS = opt("--sheets")
LAB = opt("--lab")
MODEL_ONLY = "--model-only" in argv
BLEND = opt("--blend")
REPORT = opt("--report")
OUT_DIR = os.path.join(ROOT, "Nindo", "Assets", "Nindo", "Art", "Characters", "BambooMaster")
FBX = os.path.join(OUT_DIR, "BambooMaster.fbx")
HEIGHT_CAP = 3.6         # con el bastón arriba o una patada alta; el reposo mide ~2.7
GAP = 10                 # cuadros vacíos entre clips en la toma única
BUDGET = {"body": 4800, "robe": 2400, "thrown": 500, "staff": 450}
ROUNDTRIP = opt("--roundtrip")
SLIPDUMP = opt("--slipdump")
SHEET_FRAMES = opt("--frames")
ROUNDTRIP_BONES = ("Hips", "Head", "Hand_R", "Hand_L", "Index_R_2", "Thumb_L_2", "Foot_R", "Toe_L", "Staff", "Acc_TieSashA_2",
                   "Robe_038_2", "Brow_R_2")
# la cámara del juego (Kaito de espaldas mirando al jefe): lo que se lee desde arriba es la forma, no el detalle
TELL_CAM = dict(focus=(0.0, -1.6, 1.0), pitch=52.0, dist=24.0, fov=30.0)
TELL_MIN = 0.15
GUARD_MIN = 0.15
SOLE_WARN_ONLY = False
GUARD_PAIR_MIN = 0.25   # postura / abierto / guardia entre sí (lo que no está en las dos, sobre la más grande)    # la palma estirada hacia Kaito medía 12 % (apunta a la cámara); la grulla con las alas abiertas, 16-31 %
# el agarre del bastón: hasta este exceso de muñeca con aviso (ver lint_clip)
WRIST_GRIP_WARN = 1.35
WRISTS = None
failures, warnings = [], []


def check(ok, msg, warn=False):
    print(("  ok   " if ok else ("  WARN " if warn else "  FAIL ")) + msg)
    if not ok:
        (warnings if warn else failures).append(msg)


REGRIP_W = 0.2


def gripped(c, s):
    """Cuánto agarra la mano s el bastón en el control c (0 = libre)."""
    if (c.get("staff_on") or 0.0) < 0.5 or c.get("grip_" + s) is None:
        return 0.0
    w = c.get("grip_" + s + "_w")
    return 1.0 if w is None else w


def wanted(name, pattern):
    return any(fnmatch.fnmatch(name, p.strip()) for p in pattern.split(","))


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
    t = clip.timing
    n = clip.frames
    test = t.get("kind") == "test"
    # alcance: el IK no puede quedarse corto (mano que se despega del bastón, pie que flota)
    mh = max(max(m["hand_r"], m["hand_l"]) for m in misses)
    ml = max(m["legs"] for m in misses)
    fh = max(range(len(misses)), key=lambda i: max(misses[i]["hand_r"], misses[i]["hand_l"]))
    fl = max(range(len(misses)), key=lambda i: misses[i]["legs"])
    rep["reach_miss_cm"] = {"hands": round(mh * 100, 1), "legs": round(ml * 100, 1)}
    check(ml <= 0.02, f"{clip.name}: los pies llegan (faltó {ml * 100:.1f} cm en f{fl})")
    check(mh <= 0.02, f"{clip.name}: las manos llegan (faltó {mh * 100:.1f} cm en f{fh})", warn=mh <= 0.05)
    # pies apoyados: no patinan (con el avance que aplica el juego: 'roots')
    gp, piv = foot_points(rig)
    plants = NA.plant_report(rig, frames, roots, list(gp), gp, pivots=piv)
    worst = max([p["drift_cm"] for v in plants.values() for p in v] or [0.0])
    wseg = [(k, p["frames"]) for k, v in plants.items() for p in v if p["drift_cm"] == worst]
    rep["plants"] = plants
    rep["plant_drift_cm"] = worst
    if not test:
        check(worst <= 2.0, f"{clip.name}: pies apoyados quietos (deriva máx. {worst:.2f} cm {wseg[:1]})")
    # la suela que toca el piso tampoco se arrastra (el apoyo de arriba solo ve el pie quieto; un pie que baja todavía
    # moviéndose, o que gira con el eje lejos de la bola, patinaba sin que lo marcara)
    ss = ML.sole_slip(rig, frames, roots)
    rep["sole_slip_cm"] = {k: [round(v[0] * 100, 1), v[1], round(v[2] * 100, 1)] for k, v in ss.items()}
    wk = max(ss, key=lambda k: ss[k][0])
    if SLIPDUMP and wanted(clip.name, SLIPDUMP):
        print(ML.sole_dump(rig, frames, roots))
    if not test:
        check(ss[wk][0] <= ML.SOLE_SLIP_MAX, f"{clip.name}: la suela apoyada no se arrastra ({wk}: {ss[wk][0] * 100:.1f} cm en "
                                             f"f{ss[wk][1][0]}-{ss[wk][1][1]})", warn=SOLE_WARN_ONLY)
    if clip.loop:
        seam, step = NA.loop_seam_deg(rig, frames)
        rep["loop_seam_deg"] = seam
        check(seam <= 0.5, f"{clip.name}: costura del loop {seam:.3f}° (salto típico {step:.2f}°)")
    # el pulgar no pasa de mirar a una punta del bastón a la otra con la mano cerrada: es media vuelta de la mano en un
    # cuadro alrededor del caño (Guard_P3 la daba en f2). Para cambiar de agarre la mano lo suelta (grip_*_w hasta
    # REGRIP_W o menos en ese cuadro)
    for s in "rl":
        flips = [i for i in range(1, len(ctrls)) if all(gripped(ctrls[j], s) > REGRIP_W for j in (i - 1, i))
                 and (ctrls[i]["grip_" + s + "_thumb"] >= 0.0) != (ctrls[i - 1]["grip_" + s + "_thumb"] >= 0.0)]
        check(not flips, f"{clip.name}: la mano {s.upper()} no da vuelta el agarre sin soltar el bastón"
                         f"{f' (f{flips[0]})' if flips else ''}")
    # muñecas (ítem 3): dentro de los límites de una persona, y sin tirones de un cuadro. El agarre del bastón puede
    # pasarse un poco con aviso (el puño envuelve el caño y la manga tapa la muñeca), nunca más que WRIST_GRIP_WARN
    wr = ML.wrist_report(WRISTS, frames, ctrls, t.get("wrist_cuts", ()))
    rep["wrists"] = wr
    if not test:
        for S, w in wr.items():
            lim = WRIST_GRIP_WARN if w["grip"] else 1.0
            check(w["excess"] <= lim, f"{clip.name}: muñeca {S} posible (exceso {w['excess']:.2f} en f{w['at']}: flexión "
                                      f"{w['flex']:.0f}°, desvío {w['dev']:.0f}°{', con el bastón' if w['grip'] else ''})",
                  warn=w["grip"] and w["excess"] <= WRIST_GRIP_WARN and w["excess"] > 1.0)
            check(w["twist_max"] <= ML.TWIST, f"{clip.name}: giro que queda en la muñeca {S} {w['twist_max']:.0f}° (tope {ML.TWIST:.0f})")
            check(w["jump_deg"] <= ML.WRIST_JUMP, f"{clip.name}: la mano {S} no da tirones ({w['jump_deg']:.0f}° en un cuadro, f{w['jump_at']})")
    # el cuerpo contra sí mismo
    skip = set()
    for a, b in t.get("legs_cross", []):
        skip.update(range(a, b + 1))
    cl = ML.self_clearance(rig, frames, ctrls)
    rep["self_clearance_cm"] = {k: [round(v[0] * 100, 1), v[1]] for k, v in cl.items() if v[0] < 0.06}
    if not test:
        for k, (c, f) in sorted(cl.items(), key=lambda kv: kv[1][0]):
            legs = k.startswith(("muslo", "tibia")) and k.count("/") == 1 and "bastón" not in k
            if legs and f in skip:
                continue
            # el bastón y los antebrazos contra el tronco y la cabeza: las cápsulas ya van por dentro de la malla, así que
            # cualquier cruce es un bastón metido en el chaleco (con -1 cm medio bastón quedaba adentro en toda la fase 3)
            rigid = k.startswith(("bastón", "antebrazo")) and k.endswith(("tronco", "cabeza"))
            if rigid and c < -0.005:
                check(False, f"{clip.name}: {k} se meten {-c * 100:.1f} cm en f{f}")
            elif c < -0.015:
                check(c >= -0.04, f"{clip.name}: {k} se meten {-c * 100:.1f} cm en f{f}", warn=c >= -0.04)
    # golpes con el reloj del juego
    tr = [c.get("travel") or 0.0 for c in ctrls]
    rr = t.get("release_rate", 1.6)
    rmax = t.get("root_max", ML.ROOT_MAX)
    if any(abs(v) > 1e-4 for v in tr) and not clip.root_vel.length:
        if "contact" in t and "apex" in t:
            peak = (0.0, 0.0)
            for wmin in (0.38, 0.55, 0.8):
                tl = NA.StepTimeline(n, t["apex"], t["contact"], rr, wmin, 0.0)
                for s, f, v in NA.clock_speeds(tr, tl):
                    if v > peak[0]:
                        peak = (v, f)
        else:
            peak = max(((abs(tr[i] - tr[i - 1]) * NA.FPS, i) for i in range(1, len(tr))), default=(0.0, 0))
        rep["root_peak_mps_60hz"] = round(peak[0], 1)
        check(peak[0] <= rmax, f"{clip.name}: el transform no se teletransporta (pico {peak[0]:.1f} m/s en el cuadro "
                               f"{peak[1]:.1f} del clip, release_rate {rr}; tope {rmax:.0f})")
    st = t.get("strike")
    if st and "contact" in t:
        pts = ML.strike_points(frames, roots, st[0], st[1])
        a0, a1 = t["active"]
        reach = max(Vector((pts[i].x - roots[i].x, pts[i].y - roots[i].y)).length for i in range(a0, a1 + 1))
        rep["reach_m"] = round(reach, 2)
        hz = [round(pts[i].z, 2) for i in range(a0, a1 + 1)]
        rep["strike_height_m"] = [min(hz), max(hz)]
        print(f"  info {clip.name}: alcance {reach:.2f} m desde el transform, altura {min(hz)}-{max(hz)} m (f{a0}-{a1})")
        if t.get("kind") in ("parry", "dodge") and not t.get("spin"):
            apex = t["apex"]
            t0 = t.get("tell", [0])[0]
            tl = NA.StepTimeline(n, apex, t["contact"], rr, 0.38, 0.0)
            gs = NA.clock_speeds(pts, tl)
            peak = max(v for s, f, v in gs if a0 - 1 <= f <= a1 + 2)
            outside = [(v, f) for s, f, v in gs if f > t0 and not (apex < f <= a1 + 3)]
            worst_o = max(outside) if outside else (0.0, 0)
            ratio = worst_o[0] / peak if peak > 0 else 0.0
            rep["tip_peak_mps"] = round(peak, 1)
            rep["tip_outside_ratio"] = round(ratio, 2)
            lim = t.get("tip_ratio_max", 0.35)
            check(ratio <= lim, f"{clip.name}: lo que pega va lento fuera del golpe con el reloj del juego "
                                f"({ratio * 100:.0f} % del pico en el cuadro {worst_o[1]:.1f}; tope {lim * 100:.0f} %, pico "
                                f"{peak:.1f} m/s)")
            sp = [0.0] + [(pts[i] - pts[i - 1]).length * NA.FPS for i in range(1, len(pts))]
            still = [sp[i] for i in (apex, apex + 1)]
            rep["apex_tip_mps"] = [round(v, 1) for v in still]
            check(max(still) < 4.0, f"{clip.name}: el aviso se sostiene quieto ({max(still):.1f} m/s en f{apex}-{apex + 1})")
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


def visible(clip, f, meshes):
    """Las mallas que se ven en el cuadro f del clip (el saco solo en la fase 1, el bastón en la 3, el saco tirado mientras
    vuela)."""
    t = clip.timing
    ph = getattr(clip, "phase", 1)
    robe_off = t.get("robe_off")
    out = [meshes["Master_Body"]]
    if ph == 1 and (robe_off is None or f < robe_off):
        out.append(meshes["Master_Robe"])
    if robe_off is not None and f >= robe_off:
        out.append(meshes["Master_RobeThrown"])
    sf = t.get("staff_from")
    if ph == 3 or (sf is not None and f >= sf):
        out.append(meshes["Master_Staff"])
    return out


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
            print(rv.lineup_sheet() if "--lineup" in argv else rv.model_sheet())
        finish(t0)
        return

    # ---------------------------------------------------------------- clips
    import master_clips as MC
    import master_poses as MP
    solver = MR.Solver(rig)
    global WRISTS
    WRISTS = ML.WristMeter(rig)
    clips = list(MC.init(solver)) + [c for c in MP.CLIPS if c.name == "PoseTest"]
    lab = None
    if LAB:
        lab = MC.lab_clip([s.strip() for s in LAB.split(",")])
        clips = [lab]
    elif ONLY:
        clips = [c for c in clips if wanted(c.name, ONLY)]
    sprs = MR.springs(rig)
    baked, reports, rootsd, ctrlsd, framesd = [], {}, {}, {}, {}
    # las variantes de paso corto siguen el camino de los brazos de su base hasta la suelta (lint_reach)
    paths, reach_of = {}, {}
    for c in clips:
        for v in c.timing.get("reach_variants") or ():
            reach_of[v] = (c.name, reach_upto(c))
    for clip in clips:
        misses = []

        def solve(pose, c):
            misses.append(dict(solver.solve(pose, c)))
        # dos pasadas por clip (master_rig.Solver.plan_clip): la primera junta las soluciones posibles de cada brazo en
        # cada cuadro y elige el camino del clip entero; la segunda lo aplica
        solver.begin_clip("collect")
        MS.bake_clip(rig, clip, solve, sprs)
        base, upto = reach_of.get(clip.name, (None, 0))
        solver.plan_clip(prefix={S: p[:upto + 1] for S, p in paths[base].items()} if base in paths else None)
        paths[clip.name] = {S: list(p) for S, p in solver.path.items()}
        misses.clear()
        solver.begin_clip("replay")
        frames, ctrls, roots = MS.bake_clip(rig, clip, solve, sprs)
        solver.begin_clip("free")
        print(f"-- {clip.name} ({clip.frames} cuadros)")
        reports[clip.name] = lint_clip(rig, clip, frames, ctrls, roots, misses) if clip is not lab else {}
        baked.append((clip, frames))
        rootsd[clip.name], ctrlsd[clip.name], framesd[clip.name] = roots, ctrls, frames
    if not lab:
        lint_chains(rig, MC, clips, framesd, reports)
        lint_variants(clips, ctrlsd, reports)
        lint_reach(rig, clips, framesd, reports)
    act, ranges = NA.write_pack(arm, rig, baked, start=1, gap=GAP)
    last = max(b for a, b in ranges.values())
    # techo y piso de la silueta en todos los cuadros (mallas evaluadas, solo las que se ven en ese cuadro)
    for clip, frames in ([] if lab else baked):
        a, b = ranges[clip.name]
        mm = [meshes["Master_Body"], meshes["Master_Robe"], meshes["Master_Staff"], meshes["Master_RobeThrown"]]
        rows = NA.mesh_z_frames(mm, range(a, b + 1))
        his, lows = [], []
        for i, r in enumerate(rows):
            vis = {o.name for o in visible(clip, i, meshes)}
            if clip.timing.get("staff_high") and "Master_Staff" in vis:
                vis_h = vis - {"Master_Staff"}
            else:
                vis_h = vis
            his.append(max(v[1] for k, v in r.items() if k in vis_h))
            lows.append(min((v[0], i, k) for k, v in r.items() if k in vis))
        top = max(range(len(his)), key=lambda i: his[i])
        reports[clip.name]["max_height_m"] = round(his[top], 2)
        cap = clip.timing.get("height_cap", HEIGHT_CAP)     # la grulla voladora sube 1.35 m: lo dice su clip
        check(his[top] <= cap, f"{clip.name}: silueta {his[top]:.2f} m en f{top} (tope {cap})")
        lo = min(lows)
        bad = [i for z, i, _ in lows if z < -0.03]
        reports[clip.name]["min_z_m"] = round(lo[0], 3)
        check(not bad, f"{clip.name}: nada atraviesa el piso (mín {lo[0]:.3f} m en f{lo[1]}, {lo[2]}; {len(bad)} cuadros bajo -3 cm)")
    if not lab:
        lint_tells(scn, arm, meshes, baked, ranges, rootsd, reports)
    scn.frame_set(0)
    if RENDERS or REPORT:
        path = REPORT or os.path.join(RENDERS, "lint_report.json")
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline=chr(10)) as fh:
            json.dump(reports, fh, indent=0)

    # ---------------------------------------------------------------- export
    if EXPORT and not ONLY and not LAB:
        if failures:
            print("NO SE EXPORTA: fallaron chequeos")
        else:
            NA.export_fbx(FBX, arm, objs, 1, last)
            if ROUNDTRIP:
                write_roundtrip(scn, arm, last)
            info["clips"] = sidecar_clips(baked, ranges, ctrlsd, reports)
            info["phase_variants"] = phase_variants(clips)
            info["parts"] = {
                "skinned": ["Master_Body", "Master_Robe", "Master_RobeThrown"], "rigid": {"Master_Staff": "Staff"},
                "materials": ["Nindo_Palette"] + MM.EXTRA_MATS,
                "hidden_at_spawn": ["Master_RobeThrown", "Master_Staff"],
                "notes": "Master_Robe es el saco de la fase 1 (se apaga al tirarlo: evento CoatOff de PhaseCoat); Master_RobeThrown "
                         "es la copia aplanada que vuela en el cambio de fase (huesos RobeT_*, en reposo adentro de la espalda: "
                         "se enciende en CoatOff y, cuando queda en el piso (CoatRest), conviene hornearla con "
                         "SkinnedMeshRenderer.BakeMesh en un objeto quieto y apagarla, porque los demás clips la guardan otra "
                         "vez en la espalda); Master_Staff es el bastón (hueso Staff, hijo de Root: lo mueve el clip y las "
                         "manos lo agarran), visible desde StaffAppear de PhaseStaff y en todos los clips _P3, Defeat, "
                         "Meditate y SeatedBow. Los slots Master_Glint* se encienden por nombre con CharacterGlint.SetGlow "
                         "(timing.glow de cada golpe; dorado = parry, rojo = dash) y Master_Eyes en jade desde EyesIgnite. "
                         "Ninguno se llama 'Glint': Enemy no prende nada solo, el jefe elige el miembro que pega."}
            info["chains"] = {"runtime": ["Acc_TieWhiskerR", "Acc_TieWhiskerL", "Acc_TieSashA", "Acc_TieSashB"],
                              "colliders": [f"AccCol_{n}_{int(round(r * 100))}" for n, _, _, r in MR.CHAIN_COLLIDERS],
                              "baked": ["Brow_*", "Sleeve_*", "Robe_*"],
                              "notes": "las cadenas Acc_* van horneadas en los clips; si el jefe agrega SpringChain y llama "
                                       "Rebuild, la física del juego las reemplaza (perfil 'Tie')"}
            info["material_rgb"] = {n: [round(c, 4) for c in rgb] for n, rgb in MM.MAT_RGB.items()}
            info["hand_shapes"] = MR.HAND_SHAPES
            info["staff"] = {"length_m": MR.STAFF_LEN, "radius_m": MR.STAFF_R, "bone": "Staff",
                             "tip_local_unity_note": "el hueso va de la punta de abajo (cabeza) a la de arriba (cola): las dos "
                                                     "puntas son la cabeza y la cabeza + Y * largo"}
            info["root_travel"] = MC.ROOT_TRAVEL_NOTE
            with open(FBX + ".json", "w", encoding="utf-8", newline=chr(10)) as fh:
                json.dump(info, fh, indent=1, ensure_ascii=False)
            print("EXPORTADO", FBX, "cuadros 1 ..", last, f"{os.path.getsize(FBX) / 1e6:.1f} MB")

    # ---------------------------------------------------------------- renders
    if RENDERS:
        rv = RV.Review(arm, meshes, RENDERS)
        if lab:
            print(rv.lab_sheet(lab, ranges[lab.name][0]))
            finish(t0)
            return
        if "--lineup" in argv:
            print(rv.lineup_sheet(ranges["Idle"][0] if "Idle" in ranges else 0))
            finish(t0)
            return
        if not ONLY and not SHEETS:
            print(rv.model_sheet(frame=0))
        for clip, frames in baked:
            if clip.name == "PoseTest" or (SHEETS and not wanted(clip.name, SHEETS)):
                continue
            a, _ = ranges[clip.name]
            fs = sheet_frames(clip)
            print(rv.clip_sheet(clip, a, rootsd[clip.name], fs, [frame_label(clip, f) for f in fs], reports.get(clip.name),
                                lambda f, c=clip: visible(c, f, meshes)))
        if "PoseTest" in ranges and not ONLY and not SHEETS:
            pose_test_sheets(rv, ranges)
    finish(t0)


def lint_chains(rig, MC, clips, framesd, reports):
    """La primera y la última pose de cada clip contra la pose con la que encadena (la guardia de su fase, la rodilla en
    el piso...): un salto de más de 5° en un hueso se ve en el crossfade de 0.08 s."""
    ref = {}
    for clip in clips:
        t = clip.timing
        ph = getattr(clip, "phase", 1)
        fr = framesd[clip.name]
        for which, key, W in (("primera", "chain_from", fr[0]), ("última", "chain_to", fr[-1])):
            nm = t.get(key)
            if not nm or clip.loop and which == "última":
                continue
            pose = MC.chain_pose(nm, ph)
            if pose is None:
                continue
            k = (nm, ph)
            if k not in ref:
                ref[k] = MC.solved(pose)
            d, bone, hip = ML.bone_delta_deg(rig, W, ref[k])
            reports[clip.name][f"chain_{key}_deg"] = [d, bone, hip]
            ok = d <= ML.CHAIN_WARN and hip <= 3.0
            check(ok or (d <= ML.CHAIN_FAIL and hip <= 6.0), f"{clip.name}: la {which} pose encadena con {nm} (fase {ph}): "
                                                             f"{d:.1f}° en {bone}, cadera {hip:.1f} cm", warn=not ok and d <= ML.CHAIN_FAIL and hip <= 6.0)


def lint_variants(clips, ctrlsd, reports):
    """Una variante de fase (X_P2, X_P3) tiene que ser intercambiable con su clip base en el Animator: mismos cuadros,
    tiempos, eventos y avance."""
    by = {c.name: c for c in clips}
    for c in clips:
        b = getattr(c, "base", None)
        if not b or b not in by:
            continue
        o = by[b]
        # el miembro que pega y su brillo pueden cambiar (la palma de la fase 1 es el bastón de la 3); los tiempos no
        # (el anillo y el bastón alto también: la barrida con el bastón llega más lejos que la de la pierna sola)
        own = ("phase", "glow", "notes", "strike", "tip_ratio_max", "ring_m", "staff_high", "reach_variants", "height_cap")
        tc = {k: v for k, v in c.timing.items() if k not in own}
        to = {k: v for k, v in o.timing.items() if k not in own}
        same = c.frames == o.frames and c.loop == o.loop and tc == to and \
            [(e["frame"], e["fn"]) for e in c.events] == [(e["frame"], e["fn"]) for e in o.events]
        tr_c = [round(x.get("travel") or 0.0, 4) for x in ctrlsd[c.name]]
        tr_o = [round(x.get("travel") or 0.0, 4) for x in ctrlsd[b]]
        same = same and tr_c == tr_o and (c.root_vel - o.root_vel).length < 1e-6
        check(same, f"{c.name}: variante de {b} con los mismos cuadros, tiempos, eventos y avance")


def reach_upto(c):
    """Hasta qué cuadro una variante de paso corto es el golpe de su base: el jefe cambia de variante cuando arranca la
    suelta (el apex más lo que avanza la pausa), con un cuadro de margen."""
    ap, hold = c.timing["apex"], c.timing.get("hold", [0, 0])[1]
    return ap + 1 if hold > ap else ap


def lint_reach(rig, clips, framesd, reports):
    """Las variantes de paso corto (timing.reach_variants) son el MISMO golpe hasta la suelta: el jefe pasa de una a otra
    sin fundido en el cuadro de la suelta (BambooMasterBoss.PickReach), así que hasta el final de la pausa del aviso
    no puede haber diferencia de giro en ningún hueso."""
    for c in clips:
        vs = c.timing.get("reach_variants")
        if not vs:
            continue
        upto = reach_upto(c)
        for v in vs:
            if v not in framesd:
                check(False, f"{c.name}: falta la variante {v}")
                continue
            worst = max((ML.bone_delta_deg(rig, framesd[c.name][f], framesd[v][f]) + (f,) for f in range(upto + 1)),
                        key=lambda x: x[0])
            reports[c.name].setdefault("reach_same_deg", {})[v] = [worst[0], worst[1], worst[3]]
            check(worst[0] <= 0.5 and worst[2] <= 0.5, f"{c.name}: {v} igual hasta la suelta (f{upto}): {worst[0]:.2f}° en "
                                                       f"{worst[1]} (f{worst[3]}), cadera {worst[2]:.1f} cm")


def lint_tells(scn, arm, meshes, baked, ranges, rootsd, reports):
    """Silueta de cada pose de aviso contra la de la guardia de su fase, desde la cámara del juego: la parte del aviso
    que cae FUERA de la guardia, sobre el área de la guardia (>= 15 %)."""
    cam = NA.camera(scn, "LintCam")
    NA.game_camera(cam, **TELL_CAM)
    idles = {}
    for clip, frames in baked:
        if clip.name in ("Idle", "Idle_P2", "Idle_P3"):
            scn.frame_set(ranges[clip.name][0])
            arm.location = (0, 0, 0)
            bpy.context.view_layer.update()
            m = NA.silhouette_mask(visible(clip, 0, meshes), cam)
            idles[getattr(clip, "phase", 1)] = (m, max(1, int(m.sum())))
    for clip, frames in baked:
        t = clip.timing
        ph = getattr(clip, "phase", 1)
        if t.get("kind") not in ("parry", "dodge") or "apex" not in t or ph not in idles:
            continue
        f = t["apex"]
        scn.frame_set(ranges[clip.name][0] + f)
        arm.location = rootsd[clip.name][f]
        bpy.context.view_layer.update()
        m = NA.silhouette_mask(visible(clip, f, meshes), cam)
        idle, area = idles[ph]
        change = float((m & ~idle).sum()) / area
        reports[clip.name]["tell_silhouette_change"] = round(change, 3)
        check(change >= TELL_MIN, f"{clip.name}: el aviso (f{f}) cambia la silueta desde la cámara del juego "
                                  f"{change * 100:.0f} % (mín. {TELL_MIN * 100:.0f} %)")
    # la guardia también es un aviso (pegarle es el error que enseña paciencia): desde arriba tiene que dejar de ser la
    # silueta de la espera, no una palma escondida delante de la cara
    guards = {}
    for clip, frames in baked:
        ph = getattr(clip, "phase", 1)
        if clip.name.split("_")[0] not in ("Guard", "Stance", "Taunt") or ph not in idles:
            continue
        kind = clip.name.split("_")[0]
        # la guardia y la postura se miran en su último cuadro (el que deja el juego); abierto, en el medio de la pausa
        f = clip.frames if kind != "Taunt" else sum(clip.timing["open"]) // 2
        scn.frame_set(ranges[clip.name][0] + f)
        arm.location = (0, 0, 0)
        bpy.context.view_layer.update()
        m = NA.silhouette_mask(visible(clip, f, meshes), cam)
        idle, area = idles[ph]
        change = float((m & ~idle).sum()) / area
        reports[clip.name]["guard_silhouette_change"] = round(change, 3)
        check(change >= GUARD_MIN, f"{clip.name}: cambia la silueta de la espera desde la cámara del juego "
                                   f"{change * 100:.0f} % (mín. {GUARD_MIN * 100:.0f} %)")
        guards.setdefault(ph, {})[kind] = (m, max(1, int(m.sum())))
    # la postura del bambú (no le pegues) y abierto (pegale) tienen que leerse distintas de la guardia y entre sí
    for ph, g in guards.items():
        for a_, b_ in (("Stance", "Guard"), ("Taunt", "Guard"), ("Taunt", "Stance")):
            if a_ not in g or b_ not in g:
                continue
            (ma, aa), (mb, ab) = g[a_], g[b_]
            ch = float((ma ^ mb).sum()) / max(aa, ab)
            nm = a_ + {1: "", 2: "_P2", 3: "_P3"}[ph]
            reports[nm][f"vs_{b_.lower()}_silhouette"] = round(ch, 3)
            check(ch >= GUARD_PAIR_MIN, f"{nm}: se distingue de {b_} desde la cámara del juego {ch * 100:.0f} % "
                                        f"(mín. {GUARD_PAIR_MIN * 100:.0f} %)", warn=True)
    arm.location = (0, 0, 0)


def sidecar_clips(baked, ranges, ctrlsd, reports):
    out = {}
    for clip, frames in baked:
        a, b = ranges[clip.name]
        t = dict(clip.timing)
        nrm = {}
        n = float(clip.frames)
        for k in ("apex", "contact", "resume"):
            if k in t:
                nrm[k] = round(t[k] / n, 4)
        for k in ("tell", "hold", "active", "recover", "air"):
            if k in t:
                nrm[k] = [round(t[k][0] / n, 4), round(t[k][1] / n, 4)]
        if "lunge" in t:
            nrm["lunge"] = [round(t["lunge"][0] / n, 4), round(t["lunge"][1] / n, 4), t["lunge"][2]]
        rec = {"first": a, "last": b, "frames": clip.frames, "seconds": round(clip.frames / NA.FPS, 4), "loop": clip.loop,
               "phase": getattr(clip, "phase", 1), "variant_of": getattr(clip, "base", None), "timing": t, "normalized": nrm,
               "events": [{"frame": e["frame"], "t": round(e["frame"] / n, 4), "fn": e["fn"]} for e in clip.events],
               "notes": clip.notes}
        rep = reports.get(clip.name, {})
        for k in ("reach_m", "strike_height_m"):
            if k in rep:
                rec[k] = rep[k]
        if "contact" in t:
            rec["release_rate"] = t.get("release_rate", 1.6)
        tr = [round(c.get("travel") or 0.0, 4) for c in ctrlsd[clip.name]]
        if any(abs(v) > 1e-4 for v in tr) and not clip.root_vel.length:
            rec["travel_m"] = tr
        if clip.root_vel.length > 0:
            rec["root_velocity_mps"] = round(clip.root_vel.length, 3)
        rec["lint"] = {k: v for k, v in rep.items() if k not in ("plants",)}
        out[clip.name] = rec
    return out


def phase_variants(clips):
    """{clip base: {"2": variante, "3": variante}}: lo que el jefe cambia con un AnimatorOverrideController."""
    out = {}
    for c in clips:
        b = getattr(c, "base", None)
        if b:
            out.setdefault(b, {})[str(c.phase)] = c.name
    return dict(sorted(out.items()))


def sheet_frames(clip):
    if SHEET_FRAMES:
        return [int(x) for x in SHEET_FRAMES.split(",") if int(x) <= clip.frames]
    fs = sorted({k.frame for k in clip.keys})
    t = clip.timing
    for k in ("apex", "contact"):
        if k in t:
            fs.append(t[k])
    fs = sorted(set(fs))
    if len(fs) > 10:
        must = {t[k] for k in ("apex", "contact") if k in t}
        step = (len(fs) - 1) / 9.0
        fs = sorted({fs[round(i * step)] for i in range(10)} | must)
    return fs


def frame_label(clip, f):
    t = clip.timing
    tags = []
    if t.get("apex") == f:
        tags.append("aviso")
    if t.get("contact") == f:
        tags.append("impacto")
    if "active" in t and t["active"][1] == f:
        tags.append("fin golpe")
    for e in clip.events:
        if e["frame"] == f and e["fn"] not in ("Apex", "Strike", "Step"):
            tags.append(e["fn"])
    return f"f{f}" + (" " + "/".join(tags[:2]) if tags else "")


def pose_test_sheets(rv, ranges):
    import master_poses as MP
    a0, _ = ranges["Idle"] if "Idle" in ranges else (0, 0)
    clip, marks = MP.pose_test_clip()
    p0, _ = ranges["PoseTest"]
    hold = {lab: p0 + f for f, lab in marks.items()}
    if "--detail" in argv:
        print(rv.detail_sheet([(hold["caballo y palma"], "caballo y palma", 1), (hold["patada de grulla"], "patada con saco", 1),
                               (hold["patada de grulla"], "patada sin saco", 2), (hold["bastón"], "bastón", 3),
                               (hold["puño y espada"], "saco tirado en el aire", 2, True)]))
    print(rv.hands_sheet([(hold["caballo y palma"], "palma / puño"), (hold["garra y pico"], "garra / pico"),
                          (hold["puño y espada"], "puño / espada"), (hold["bastón"], "agarre")]))
    print(rv.lineup_sheet(a0))


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
    for w in warnings:
        print("   aviso:", w)
    if failures:
        print("FALLARON", len(failures), "chequeos:")
        for f in failures:
            print("   -", f)
        sys.exit(1)


main()
