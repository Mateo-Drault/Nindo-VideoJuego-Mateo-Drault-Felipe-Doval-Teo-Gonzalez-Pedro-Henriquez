"""Mediciones de los clips de Chikuō (sobre las poses ya resueltas, antes de exportar). Lo que llega a Unity está medido:

* alcance del IK (manos y pies que no llegan), pies apoyados que patinan (con el avance que aplica el juego), costura
  de los loops;
* cuerpo contra sí mismo: el bastón, las manos y las piernas contra cápsulas del tronco, la cabeza y las piernas
  (radios por dentro de la malla: lo que marca es una pieza metida de verdad en el cuerpo);
* golpes con el reloj del juego (StepTimeline): el avance del transform no se teletransporta, la punta que pega va
  quieta en el aviso y lenta fuera del golpe (un barrido rápido que no pega es un aviso de parry falso), alcance real;
* encadenado: la primera y la última pose contra la guardia de su fase (un salto en el crossfade se ve);
* variantes de fase con los mismos cuadros, tiempos, eventos y avance que su clip base.
"""
import math
from mathutils import Vector
import nindo_anim as NA
import master_rig as MR

ROOT_MAX = 20.0          # m/s del transform en un cuadro de juego (lo que se lee como movimiento y no como salto)
CHAIN_WARN, CHAIN_FAIL = 5.0, 12.0
# huesos que mueven los resortes o la física: no cuentan en el encadenado (se asientan solos)
SPRING_PREFIX = ("Acc_", "Brow_", "Sleeve_", "Robe_", "RobeT_")


def seg_dist(p1, q1, p2, q2):
    """Distancia mínima entre los segmentos p1-q1 y p2-q2."""
    d1, d2, r = q1 - p1, q2 - p2, p1 - p2
    a, e, f = d1.dot(d1), d2.dot(d2), d2.dot(r)
    if a <= 1e-9 and e <= 1e-9:
        return (p1 - p2).length
    if a <= 1e-9:
        s, t = 0.0, max(0.0, min(1.0, f / e))
    else:
        c = d1.dot(r)
        if e <= 1e-9:
            t, s = 0.0, max(0.0, min(1.0, -c / a))
        else:
            b = d1.dot(d2)
            den = a * e - b * b
            s = max(0.0, min(1.0, (b * f - c * e) / den)) if den > 1e-9 else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t, s = 0.0, max(0.0, min(1.0, -c / a))
            elif t > 1.0:
                t, s = 1.0, max(0.0, min(1.0, (b - c) / a))
    return ((p1 + d1 * s) - (p2 + d2 * t)).length


def capsules(rig, W):
    """Cápsulas del cuerpo en una pose: (nombre, a, b, radio). Radios por dentro de la malla (el pantalón inflado y el
    saco suman ~5 cm): una pieza que entra más que eso está adentro."""
    def tail(b):
        return W[b] @ Vector((0.0, rig.length[b], 0.0))
    cap = [("tronco", W["Hips"].translation + Vector((0, 0, 0.04)), W["Chest"].translation + (tail("Chest") - W["Chest"].translation) * 0.85,
            0.13),
           ("cabeza", W["Head"].translation + (tail("Head") - W["Head"].translation) * 0.35,
            W["Head"].translation + (tail("Head") - W["Head"].translation) * 0.6, 0.12)]
    for S in "RL":
        cap += [(f"muslo {S}", W["Thigh_" + S].translation, tail("Thigh_" + S), 0.08),
                (f"tibia {S}", W["Shin_" + S].translation, tail("Shin_" + S), 0.055),
                (f"brazo {S}", W["UpperArm_" + S].translation, tail("UpperArm_" + S), 0.045),
                (f"antebrazo {S}", W["Forearm_" + S].translation, tail("Forearm_" + S), 0.04)]
    return {c[0]: c[1:] for c in cap}


# pares que se miden: (pieza, contra qué) — el bastón contra el cuerpo y las piernas, los antebrazos contra el tronco y
# la cabeza, las piernas entre sí
PAIRS = [("bastón", t) for t in ("tronco", "cabeza", "muslo R", "muslo L", "tibia R", "tibia L")] + \
        [(f"antebrazo {S}", t) for S in "RL" for t in ("tronco", "cabeza")] + \
        [("muslo R", "muslo L"), ("tibia R", "tibia L"), ("tibia R", "muslo L"), ("tibia L", "muslo R")]


def self_clearance(rig, frames, ctrls, skip=()):
    """Holgura mínima (m, negativa = se mete) de cada par en el clip: {par: (holgura, cuadro)}."""
    out = {}
    for i, (W, c) in enumerate(zip(frames, ctrls)):
        if i in skip:
            continue
        cap = capsules(rig, W)
        if (c.get("staff_on") or 0.0) >= 0.5:
            M = W["Staff"]
            ax = NA.rot3(M).col[1]
            cap["bastón"] = (M.translation, M.translation + ax * MR.STAFF_LEN, MR.STAFF_R)
        for a, b in PAIRS:
            if a not in cap or b not in cap:
                continue
            (p1, q1, r1), (p2, q2, r2) = cap[a], cap[b]
            cl = seg_dist(p1, q1, p2, q2) - r1 - r2
            k = f"{a} / {b}"
            if k not in out or cl < out[k][0]:
                out[k] = (round(cl, 3), i)
    return out


def bone_delta_deg(rig, Wa, Wb):
    """Mayor diferencia de giro local entre dos poses (sin los huesos de resortes) y cuánto se corre la cadera."""
    la, lb = rig.to_local(Wa), rig.to_local(Wb)
    worst, wb = 0.0, ""
    for nme in rig.names:
        if nme.startswith(SPRING_PREFIX) or nme in ("Staff",):
            continue
        d = NA.quat_angle_deg(la[nme][1], lb[nme][1])
        if d > worst:
            worst, wb = d, nme
    hip = (Wa["Hips"].translation - Wb["Hips"].translation).length
    return round(worst, 2), wb, round(hip * 100.0, 1)


def strike_points(frames, roots, bone, local):
    return [W[bone] @ Vector(local) + r for W, r in zip(frames, roots)]


# ============================================================================ suela contra el piso
# puntos de la suela (reposo, z = 0): talón y bola a los dos lados y el centro de la bola (el eje de un giro), en el pie;
# la punta a los dos lados, en el dedo (se dobla aparte)
SOLE_HALF_W = 0.055
TOUCH_Z = 0.015          # bajo esto la suela toca el piso
SOLE_SLIP_MAX = 0.02     # lo que se puede correr una suela apoyada en un apoyo seguido (m)


def sole_points(rig):
    """{hueso: [puntos en el espacio del hueso]} de las dos suelas."""
    out = {}
    for S, sx in (("R", 1.0), ("L", -1.0)):
        x = MR.ANKLE.x * sx
        foot = [Vector((x + d, y, 0.0)) for y in (MR.SOLE_HEEL_Y, MR.SOLE_BALL_Y) for d in (-SOLE_HALF_W, SOLE_HALF_W)]
        foot.append(Vector((x, MR.SOLE_BALL_Y, 0.0)))
        toe = [Vector((x + d, MR.SOLE_TOE_Y, 0.0)) for d in (-0.04, 0.04)]
        out["Foot_" + S] = [rig.rest_inv["Foot_" + S] @ p for p in foot]
        out["Toe_" + S] = [rig.rest_inv["Toe_" + S] @ p for p in toe]
    return out


def sole_slip(rig, frames, roots, pts=None):
    """Lo que patina cada suela mientras toca el piso, con el avance del juego: en cada par de cuadros con puntos de la
    suela por debajo de TOUCH_Z en los dos, se toma el punto que MENOS se movió (el pivote: un pie que rueda del talón a
    la punta o gira sobre la bola no patina) y se suma a lo largo del apoyo. {pie: (patinada máx. de un apoyo m,
    [cuadro inicial, final], paso máx. de un cuadro m)}."""
    pts = pts or sole_points(rig)
    out = {}
    for S in "RL":
        tracks = []
        for bn in ("Foot_" + S, "Toe_" + S):
            for p in pts[bn]:
                tracks.append([W[bn] @ p + r for W, r in zip(frames, roots)])
        worst, wseg, wstep = 0.0, [0, 0], 0.0
        run, run_from = 0.0, None
        for i in range(1, len(frames)):
            best = None
            for tr in tracks:
                a, b = tr[i - 1], tr[i]
                if a.z < TOUCH_Z and b.z < TOUCH_Z:
                    d = Vector((b.x - a.x, b.y - a.y)).length
                    best = d if best is None else min(best, d)
            if best is None:
                run, run_from = 0.0, None
                continue
            if run_from is None:
                run_from = i - 1
            run += best
            wstep = max(wstep, best)
            if run > worst:
                worst, wseg = run, [run_from, i]
        out["Foot_" + S] = (round(worst, 4), wseg, round(wstep, 4))
    return out


def sole_dump(rig, frames, roots, pts=None):
    """Para iterar un clip (--slipdump): por cuadro y por pie, la altura del punto más bajo de la suela y lo que se movió
    el pivote (el punto apoyado que menos se movió) desde el cuadro anterior."""
    pts = pts or sole_points(rig)
    lines = []
    for S in "RL":
        tracks = [[W[bn] @ p + r for W, r in zip(frames, roots)] for bn in ("Foot_" + S, "Toe_" + S) for p in pts[bn]]
        for i in range(len(frames)):
            low = min(tr[i].z for tr in tracks)
            mv = [Vector((tr[i].x - tr[i - 1].x, tr[i].y - tr[i - 1].y)).length for tr in tracks
                  if i and tr[i].z < TOUCH_Z and tr[i - 1].z < TOUCH_Z]
            lines.append(f"    {S} f{i:3d} suela {low * 100:6.1f} cm  pivote {min(mv) * 100 if mv else -1:5.1f} cm")
    return "\n".join(lines)


# ============================================================================ muñecas
# Los límites y la medida son los de master_rig (los de team_limbs): 'exceso' 1 = en el borde de la elipse de flexión,
# extensión y desvío. El giro de la mano sobre su eje que queda en la muñeca después de twist_follow, hasta TWIST. Un cuadro
# en que la mano gira contra el antebrazo más que WRIST_JUMP es un tirón (fuera de los cortes que el clip declara en
# timing['wrist_cuts'])
TWIST = 85.0
WRIST_JUMP = 45.0


class WristMeter:
    """(flexión, desvío, giro) de cada mano respecto de su antebrazo, con la relación del reposo como muñeca neutra."""

    def __init__(self, rig):
        self.side = MR.wrist_frames(rig)

    def relative(self, W, S):
        return (NA.rot3(W["Forearm_" + S]) @ self.side[S][0]).transposed() @ NA.rot3(W["Hand_" + S])

    def angles(self, W, S):
        _, n, l = self.side[S]
        return MR.wrist_angles(self.relative(W, S), n, l)


def wrist_report(meter, frames, ctrls, cuts=()):
    """Por mano: el peor exceso (y si en ese cuadro agarra el bastón), la flexión, el desvío y el giro de ese cuadro, el
    mayor giro que queda en la muñeca y el mayor tirón de un cuadro (grados de la mano contra el antebrazo)."""
    cut = set()
    for a, b in cuts:
        cut.update(range(a, b + 1))
    out = {}
    for S in "RL":
        s = S.lower()
        worst = (0.0, 0, 0.0, 0.0, 0.0, False)
        tw_max, jump = 0.0, (0.0, 0)
        prev = None
        for i, (W, c) in enumerate(zip(frames, ctrls)):
            flex, dev, tw = meter.angles(W, S)
            ex = MR.wrist_excess(flex, dev)
            gw = c.get("grip_" + s + "_w")
            grip = (c.get("staff_on") or 0.0) >= 0.5 and c.get("grip_" + s) is not None and (1.0 if gw is None else gw) >= 0.5
            if ex > worst[0]:
                worst = (ex, i, flex, dev, tw, grip)
            tw_max = max(tw_max, abs(tw))
            D = meter.relative(W, S).to_quaternion()
            if prev is not None and i not in cut and (i - 1) not in cut:
                d = math.degrees(prev.rotation_difference(D).angle)
                d = 360.0 - d if d > 180.0 else d
                if d > jump[0]:
                    jump = (d, i)
            prev = D
        out[S] = {"excess": round(worst[0], 2), "at": worst[1], "flex": round(worst[2], 1), "dev": round(worst[3], 1),
                  "twist": round(worst[4], 1), "grip": worst[5], "twist_max": round(tw_max, 1),
                  "jump_deg": round(jump[0], 1), "jump_at": jump[1]}
    return out
