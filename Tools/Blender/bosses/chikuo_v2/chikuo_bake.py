"""Horneado, mediciones, sidecar y hojas de los clips del Chikuō ermitaño (lo usa build_chikuo.py).

Por clip: resuelve cada cuadro (chikuo_anim.Solver), hornea los resortes, mide (chikuo_lint) y falla lo que no cumple el
contrato de calidad. Con la toma escrita, mide la malla deformada (piso y culmo atravesados). El sidecar lleva por clip
los tiempos en cuadros y normalizados, los eventos, el avance del transform y el resumen de las mediciones.
"""
import math, os, time
import bpy
from mathutils import Vector
import nindo_anim as NA
import chikuo_anim as CA
import chikuo_lint as LT
import chikuo_poses as CP

SPACES_NOTE = {
    "ground": "la raíz en el piso, donde está el transform del jefe; el avance del clip lo aplica el código (travel_m)",
    "perch": "la raíz en el PerchNode de la caña (arriba del anillo del nudo del posado) con su giro: el culmo es el eje "
             "+Y del modelo (Unity) desde la raíz; el código gira el modelo alrededor del culmo para mirar a Kaito. Autorado "
             "sobre la caña de adentro (posado 4.4 m, culmo r 0.103): en la Madre (r 0.155) correr el modelo 5 cm hacia su "
             "frente",
    "air": "la raíz la lleva el código por el arco (de PerchNode a PerchNode, o al punto donde cae): los pies quedan a la "
           "altura de la raíz como en el posado",
    "pole": "en el piso con la flauta-bastón clavada en el piso del clip (la Grulla en el Bastón)",
}


def stalk_note():
    s = CA.STALKS[CA.AUTHOR]
    return {"author_kind": CA.AUTHOR, "perch_m": s["perch"], "grip_high_z": CA.GRIP_Z, "climb_grip_z": CA.CLIMB_Z,
            "culm_radius_at_perch": round(CA.culm_r(0.0), 4), "perch_ring_radius": CA.RING_R,
            "note": "z del clip de posado (0 = PerchNode). Las manos agarran el culmo dentro del tramo del PerchNode (Seg_05) "
                    "en los clips de arriba: el arco del código no las despega"}


def frame_label(clip, f):
    t = clip.timing
    tags = []
    if t.get("apex") == f:
        tags.append("aviso")
    if t.get("contact") == f:
        tags.append("golpe")
    for e in clip.events:
        if e["frame"] == f:
            tags.append(e["fn"])
    return f"f{f}" + (" " + "/".join(tags[:2]) if tags else "")


def bake_all(rig, clips, check):
    """{clip: {frames, ctrls, roots, misses, report}} con las mediciones y los chequeos de cada clip."""
    solver = CA.Solver(rig)
    cols = CP.colliders(rig)
    meter = LT.WristMeter(rig)
    import chikuo_clips as CC
    out = {}
    # primero los clips de referencia del encadenado: sus agarres fijan los de las puntas de los demás. Entre ellos, cada
    # uno después de los de referencia con los que encadena (DiveLand termina en la guardia de Idle: horneado antes que
    # Idle, su último agarre no quedaba fijado y el empalme se iba 20° en el brazo)
    refs = {CC.chain_ref(k)[0] for k in CC.CHAIN_REF}
    pending = [c for c in clips if c.name in refs]
    deps = {c.name: {CC.chain_ref(c.timing.get(k))[0] for k in ("chain_from", "chain_to")} & refs - {c.name} for c in pending}
    order, done = [], set()
    while pending:
        ready = [c for c in pending if deps[c.name] <= done] or pending[:1]
        for c in ready:
            order.append(c)
            done.add(c.name)
            pending.remove(c)
    order += [c for c in clips if c.name not in refs]
    ref_grips = {}
    for clip in order:
        t0 = time.time()
        t = clip.timing
        rf, wf = CC.chain_ref(t.get("chain_from"))
        rt, wt = CC.chain_ref(t.get("chain_to"))
        # con fundido el código mezcla las dos poses (la flauta tampoco coincide): fijar el agarre de la pose de encadenado
        # solo obligaba al puño a dar la vuelta alrededor del caño en los primeros o los últimos cuadros
        pf = None if t.get("fade_from") else ref_grips.get((rf, wf))
        pt = None if t.get("fade_to") else ref_grips.get((rt, wt))
        frames, ctrls, roots, misses = CA.bake(rig, clip, solver, cols, pin_from=pf, pin_to=pt)
        if clip.name in refs:
            ref_grips[(clip.name, 0)] = clip.grips["first"]
            ref_grips[(clip.name, -1)] = clip.grips["last"]
        rep = lint_clip(rig, clip, frames, ctrls, roots, misses, meter, check)
        out[clip.name] = dict(frames=frames, ctrls=ctrls, roots=roots, misses=misses, report=rep, clip=clip)
        print(f"-- {clip.name} ({clip.frames} cuadros, {time.time() - t0:.1f} s)")
    chain_checks(rig, clips, out, check)
    for clip in clips:
        ro = clip.timing.get("root_offset")
        if ro and ro[0] in out:
            # dónde tiene que estar la raíz del vuelo respecto del PerchNode al empalmar con el clip de vuelo: la cadera de
            # este clip menos la del de vuelo (en el espacio del modelo de Unity: x = -x de Blender, y = z, z = -y)
            d = out[clip.name]["frames"][ro[2]]["Hips"].translation - out[ro[0]]["frames"][ro[1]]["Hips"].translation
            out[clip.name]["report"]["root_offset_m"] = [round(-d.x, 3), round(d.z, 3), round(-d.y, 3)]
    return out


def lint_clip(rig, clip, frames, ctrls, roots, misses, meter, check):
    import chikuo_clips as CC
    t = clip.timing
    n = clip.frames
    rep = {}
    space = t.get("space", "ground")
    # eventos: los cuadros del contrato (sección 16 del diseño)
    want = CC.CONTRACT_EVENTS.get(clip.name)
    if want is not None:
        got = sorted((e["frame"], e["fn"]) for e in clip.events)
        check(got == sorted(want), f"{clip.name}: eventos del contrato {sorted(want)} (tiene {got})")
    want_n = CC.CONTRACT_FRAMES.get(clip.name)
    if want_n is not None:
        check(n == want_n, f"{clip.name}: {want_n} cuadros como el contrato (tiene {n})")
    # alcance del IK
    mh = max(max(m.get("r", 0.0), m.get("l", 0.0)) for m in misses)
    ml = max(max(m.get("leg_r", 0.0), m.get("leg_l", 0.0)) for m in misses)
    fh = max(range(len(misses)), key=lambda i: max(misses[i].get("r", 0.0), misses[i].get("l", 0.0)))
    fl = max(range(len(misses)), key=lambda i: max(misses[i].get("leg_r", 0.0), misses[i].get("leg_l", 0.0)))
    rep["reach_miss_cm"] = [round(mh * 100, 1), round(ml * 100, 1)]
    wl = "R" if misses[fl].get("leg_r", 0.0) >= misses[fl].get("leg_l", 0.0) else "L"
    wh = "R" if misses[fh].get("r", 0.0) >= misses[fh].get("l", 0.0) else "L"
    check(ml <= 0.02, f"{clip.name}: los pies llegan (faltó {ml * 100:.1f} cm en f{fl}, pie {wl})")
    check(mh <= 0.02, f"{clip.name}: las manos llegan (faltó {mh * 100:.1f} cm en f{fh}, mano {wh})")
    lq = LT.local_quats(rig, frames)
    if clip.loop:
        pose, vel = LT.loop_seam(rig, lq)
        rep["loop_seam_deg"] = [pose, vel]
        check(pose < 0.5 and vel < 1.0, f"{clip.name}: loop sin costura (pose {pose:.2f}°, salto de velocidad {vel:.2f}°)")
    sn = LT.snaps(rig, lq, clip.cuts, frames)
    rep["snap_deg"] = list(sn)
    check(sn[0] <= LT.SNAP_DEG, f"{clip.name}: ningún hueso gira más de {LT.SNAP_DEG:.0f}° en un cuadro ({sn[0]}° {sn[1]} f{sn[2]})")
    # pies en el piso (con el avance del juego)
    if space in ("ground", "pole"):
        cf = t.get("carried_from")
        # desde que el código lleva la raíz por el arco del salto los pies ya no están en el piso del clip
        gf, gr = (frames[:cf + 1], roots[:cf + 1]) if cf is not None else (frames, roots)
        ss = LT.sole_slip(rig, gf, gr)
        rep["sole_slip_cm"] = ss
        wk = max(ss, key=lambda k: ss[k][0])
        check(ss[wk][0] <= LT.SLIP_MAX * 100, f"{clip.name}: la suela apoyada no patina ({wk}: {ss[wk][0]:.1f} cm en "
                                              f"f{ss[wk][1][0]}-{ss[wk][1][1]})")
        lo = LT.sole_floor(rig, gf, gr)
        rep["sole_min_z"] = lo
        check(lo[0] >= -0.02 - (t.get("sunk") or 0.0), f"{clip.name}: las suelas no se meten en el piso ({lo[0] * 100:.1f} cm en f{lo[1]})")
    # en la caña: las manos agarradas al culmo y los pies en el nudo, con el arco del código
    theta = t.get("bend", 0.0)
    if space == "perch":
        cc = LT.culm_contacts(rig, frames, ctrls, max(abs(theta), 1e-3))
        rep["culm_hands_cm"] = cc
        for S, (cm, f) in cc.items():
            check(cm <= 2.0, f"{clip.name}: la mano {S} trabada en el culmo con {theta:.0f}° de arco ({cm:.1f} cm en f{f})")
        spans = t.get("feet_on_node")
        if spans:
            fn = LT.feet_on_node(rig, frames, ctrls, spans, max(abs(theta), 1e-3))
            rep["node_feet_cm"] = fn
            for S, (cm, f) in fn.items():
                check(cm <= 2.0, f"{clip.name}: el pie {S} en el nudo ({cm:.1f} cm en f{f})")
        sc = LT.staff_vs_culm(frames)
        rep["staff_culm_clear_m"] = sc
        check(sc[0] >= -0.005, f"{clip.name}: la flauta no atraviesa el culmo ({sc[0] * 100:.1f} cm en f{sc[1]})")
    wr = LT.wrist_report(meter, frames, ctrls)
    rep["wrists"] = wr
    for S, w in wr.items():
        lim = LT.WRIST_GRIP_MAX if w["held"] else LT.WRIST_FREE_MAX
        check(w["excess"] <= lim, f"{clip.name}: muñeca {S} posible (exceso {w['excess']:.2f} en f{w['at']}: flexión "
                                  f"{w['flex']}°, desvío {w['dev']}°{', agarrada' if w['held'] else ''})")
    cl = LT.self_clearance(rig, frames)
    rep["self_clearance_cm"] = {k: [round(v[0] * 100, 1), v[1]] for k, v in cl.items() if v[0] < 0.04}
    skip = set()
    for a, b in t.get("legs_cross", []):
        skip.update(range(a, b + 1))
    for k, (c, f) in sorted(cl.items(), key=lambda kv: kv[1][0]):
        legs = k.startswith(("muslo", "tibia")) and "flauta" not in k
        if legs and f in skip:
            continue
        if c < -0.015:
            check(c >= -0.03, f"{clip.name}: {k} se meten {-c * 100:.1f} cm en f{f}", warn=c >= -0.03)
    return rep


def chain_checks(rig, clips, data, check):
    """La primera y la última pose de cada clip contra la pose con la que encadena: más de CHAIN_WARN grados en un hueso
    se ve en el fundido del código (CHAIN_FAIL falla)."""
    import chikuo_clips as CC
    for clip in clips:
        t = clip.timing
        for which, key, i in (("primera", "chain_from", 0), ("última", "chain_to", -1)):
            nm = t.get(key)
            ref, rfi = CC.chain_ref(nm)
            if not nm or ref is None or ref not in data or (clip.loop and which == "última"):
                continue
            Wr = data[ref]["frames"][rfi]
            W = data[clip.name]["frames"][i]
            d, bone, hip, st = LT.bone_delta(rig, W, Wr)
            data[clip.name]["report"][key + "_deg"] = [d, bone, hip, st]
            ok = d <= LT.CHAIN_WARN and hip <= 3.0
            fade = t.get("fade_" + key[6:])
            check(ok or (d <= LT.CHAIN_FAIL and hip <= 8.0), f"{clip.name}: la {which} pose encadena con {nm}: {d:.1f}° en "
                                                             f"{bone}, cadera {hip:.1f} cm, flauta {st:.1f} cm"
                                                             f"{f' (fundido del código {fade} s)' if fade else ''}",
                  warn=not ok and (d <= LT.CHAIN_FAIL and hip <= 8.0) or bool(fade))


def mesh_checks(scn, meshes, data, ranges, check):
    """Con la toma escrita: la malla deformada no atraviesa el piso (clips de piso) ni el culmo (clips de arriba)."""
    import numpy as np
    body = meshes["Chikuo_Body"]
    staff = meshes["Chikuo_Staff"]
    vg = {g.index: g.name for g in body.vertex_groups}
    dom = np.array([max(v.groups, key=lambda g: g.weight).group for v in body.data.vertices])
    for name, d in data.items():
        clip = d["clip"]
        a, b = ranges[name]
        space = clip.timing.get("space", "ground")
        worst_floor, worst_culm = (9.0, 0, []), (0, 0.0, 0, [])
        lim = clip.timing.get("floor_min", -(clip.timing.get("sunk") or 0.03))
        cf = clip.timing.get("carried_from")
        for i, f in enumerate(range(a, b + 1)):
            if cf is not None and i > cf and space in ("ground", "pole"):
                break
            scn.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            w = NA.world_verts(body, dg)
            ws = NA.world_verts(staff, dg)
            if space in ("ground", "pole"):
                # la flauta clavada a propósito (la pértiga, el bastón clavado) cuenta desde lo que se hunde
                zb, zs_ = float(w[:, 2].min()), float(ws[:, 2].min()) + (clip.timing.get("staff_in_floor") or 0.0)
                z = min(zb, zs_)
                if z < worst_floor[0]:
                    # qué se mete: los grupos dominantes de los vértices debajo del límite (y la flauta)
                    parts = {}
                    for gi in dom[w[:, 2] < lim]:
                        parts[vg[int(gi)]] = parts.get(vg[int(gi)], 0) + 1
                    if zs_ < lim:
                        parts["flauta"] = int((ws[:, 2] + (clip.timing.get("staff_in_floor") or 0.0) < lim).sum())
                    worst_floor = (round(z, 3), i, sorted(parts.items(), key=lambda kv: -kv[1])[:4])
            elif space == "perch":
                zs = w[:, 2]
                rad = np.sqrt(w[:, 0] ** 2 + w[:, 1] ** 2)
                s = CA.STALKS[CA.AUTHOR]
                rr = s["r0"] + (s["r1"] - s["r0"]) * np.clip((zs + s["perch"]) / s["length"], 0, 1)
                depth = rr - rad
                inside = (depth > 0.015) & (zs > -s["perch"])
                n_in = int(inside.sum())
                dmax = float(depth[inside].max()) if n_in else 0.0
                if n_in > worst_culm[0]:
                    parts = {}
                    for gi in dom[inside]:
                        parts[vg[int(gi)]] = parts.get(vg[int(gi)], 0) + 1
                    worst_culm = (n_in, round(dmax, 3), i, sorted(parts.items(), key=lambda kv: -kv[1])[:4])
        if space in ("ground", "pole"):
            d["report"]["mesh_min_z"] = list(worst_floor[:2])
            check(worst_floor[0] >= lim, f"{name}: nada atraviesa el piso (mín {worst_floor[0] * 100:.1f} cm en f{worst_floor[1]}: "
                                         f"{worst_floor[2]})")
        elif space == "perch":
            d["report"]["culm_inside_verts"] = worst_culm
            check(worst_culm[0] <= 12, f"{name}: el cuerpo no atraviesa el culmo ({worst_culm[0]} vértices a más de 1.5 cm "
                                       f"adentro en f{worst_culm[2]}, hasta {worst_culm[1] * 100:.1f} cm: "
                                       f"{worst_culm[3] if len(worst_culm) > 3 else ''})", warn=worst_culm[0] <= 40)
    scn.frame_set(0)


def sidecar_clip(c, a, b, d):
    t = dict(c.timing)
    n = float(max(1, c.frames))
    nrm = {}
    for k in ("apex", "contact"):
        if k in t:
            nrm[k] = round(t[k] / n, 4)
    for k in ("tell", "active", "load", "air", "recover", "open"):
        if k in t:
            nrm[k] = [round(t[k][0] / n, 4), round(t[k][1] / n, 4)]
    rec = {"first": a, "last": b, "frames": c.frames, "seconds": round(c.frames / NA.FPS, 4), "loop": c.loop,
           "timing": t, "normalized": nrm,
           "events": [{"frame": e["frame"], "t": round(e["frame"] / n, 4), "fn": e["fn"]} for e in c.events],
           "notes": c.notes}
    if d is not None:
        tr = [round(cc.get("travel") or 0.0, 4) for cc in d["ctrls"]]
        if any(abs(v) > 1e-4 for v in tr):
            rec["travel_m"] = tr
        rise = [round(cc.get("rise") or 0.0, 4) for cc in d["ctrls"]]
        if any(abs(v) > 1e-4 for v in rise):
            rec["rise_m"] = rise
        if c.root_vel.length > 0:
            rec["root_velocity_mps"] = round(c.root_vel.length, 3)
        rep = d["report"]
        rec["lint"] = {k: v for k, v in rep.items() if k in ("reach_miss_cm", "loop_seam_deg", "snap_deg", "sole_slip_cm",
                                                            "culm_hands_cm", "node_feet_cm", "chain_from_deg", "chain_to_deg",
                                                            "mesh_min_z", "culm_inside_verts")}
        for k in ("muzzle", "root_offset_m"):
            if k in rep:
                rec[k] = rep[k]
    return rec


# los clips de cerbatana posados que el código gira hacia la pantalla mientras sopla (BambooMasterBoss.aimClips)
AIM_CLIPS = ("PerchDart", "PerchDart2", "PerchVolley", "PerchVolley4", "PerchWhistle")


def clip_sheets(arm, rig, meshes, out_dir, baked, data, pattern):
    import fnmatch
    import chikuo_clip_review as CRV
    import chikuo_clips as CC
    rv = CRV.ClipReview(arm, rig, meshes, out_dir)
    shots = []
    for clip, frames in baked:
        if clip.name not in data:
            continue
        if pattern and not any(fnmatch.fnmatch(clip.name, p.strip()) for p in pattern.split(",")):
            continue
        d = data[clip.name]
        picks = sheet_frames(clip)
        rep = d["report"]
        line = []
        if "loop_seam_deg" in rep:
            line.append(f"costura {rep['loop_seam_deg'][1]:.2f}°")
        line.append(f"tirón máx {rep['snap_deg'][0]}°")
        if "sole_slip_cm" in rep:
            line.append("patina " + "/".join(f"{v[0]:.1f}" for v in rep["sole_slip_cm"].values()) + " cm")
        print(rv.clip_sheet(clip, frames, d["roots"], picks, [frame_label(clip, f) for f in picks], ", ".join(line)))
        for f, lab, slots, color in CC.tell_shots(clip):
            shots.append((f"{clip.name} {lab}", frames[f], clip.timing.get("space", "ground"), slots, color, clip.timing.get("bend", 0.0),
                          clip.name in AIM_CLIPS))
    for i in range(0, len(shots), 8):
        print(rv.game_tells(shots[i:i + 8], name=f"tells_{i // 8}"))


def sheet_frames(clip, most=9):
    fs = sorted({k.frame for k in clip.keys} | {e["frame"] for e in clip.events})
    t = clip.timing
    for k in ("apex", "contact"):
        if k in t:
            fs.append(t[k])
    fs = sorted(set(f for f in fs if 0 <= f <= clip.frames))
    if len(fs) > most:
        must = {t[k] for k in ("apex", "contact") if k in t} | {e["frame"] for e in clip.events}
        step = (len(fs) - 1) / (most - 1.0)
        fs = sorted({fs[round(i * step)] for i in range(most)} | (must & set(fs)))
    return fs


def lab_sheet(arm, rig, meshes, out_dir, names):
    """Poses sueltas de chikuo_clips.LAB (iterar las poses madre antes de armar los clips): cada una asentada con los
    resortes, desde cuatro lados en estudio y con la cámara del juego."""
    import chikuo_clip_review as CRV
    import chikuo_clips as CC
    from mathutils import Matrix
    rv = CRV.ClipReview(arm, rig, meshes, out_dir)
    solver = CA.Solver(rig)
    cols = CP.colliders(rig)
    meter = LT.WristMeter(rig)
    rows = []
    for nm in names:
        ctrl, space, extra = (CC.LAB[nm] + ({},))[:3]
        clip = CA.CClip("lab_" + nm, 1, [NA.Key(0, dict(ctrl)), NA.Key(1, dict(ctrl))], timing=dict(space=space, preroll=2.5, **extra))
        frames, ctrls, roots, misses = CA.bake(rig, clip, solver, cols)
        W = frames[-1]
        wr = LT.wrist_report(meter, [W], [ctrls[-1]])
        cl = {k: v for k, v in LT.self_clearance(rig, [W]).items() if v[0] < -0.01}
        miss = max(misses[-1].values()) if misses[-1] else 0.0
        print(f"  lab {nm}: falta IK {miss * 100:.1f} cm, muñecas " +
              ", ".join(f"{S} {w['excess']:.2f} (flex {w['flex']}, desv {w['dev']})" for S, w in wr.items()) +
              (f", choques {cl}" if cl else ""))
        up = space == "perch"
        rv.use("studio")
        rv.floor()
        tiles = []
        for az, el in ((15, 4), (100, 4), (200, 8), (-60, 30)):
            if up:
                rv.place_stalk((0.0, 0.0))
                rv.hide_stalk(False)
            else:
                rv.hide_stalk(True)
            rv.put(W, Matrix.Translation((0, 0, CA.PERCH_H if up else 0.0)))
            pts = rv.body_points()
            c = sum(pts, Vector()) / len(pts)
            hz = max(p.z for p in pts) - min(p.z for p in pts)
            rv.set_studio_light(Matrix.Rotation(math.radians(az), 3, 'Z') @ Vector((-0.45, -0.7, 0.75)))
            rv.ortho(c, max(2.6, hz + 0.4), az, el)
            big = len(names) <= 2
            tiles.append({"img": rv.render(rv.tile(f"lab_{nm}_{az}"), res=(560, 700) if big else (360, 420)), "label": f"{nm} {az}°"})
        rows.append({"label": nm, "tiles": tiles})
    rv.hide_stalk(True)
    rv.arm.matrix_world = Matrix.Identity(4)
    out = os.path.join(out_dir, "lab.png")
    big = len(names) <= 2
    rv.sheet({"out": out, "title": "Poses madre (estudio)", "width": 1800 if big else 1460, "tile_h": 440 if big else 300, "rows": rows})
    print(out)
