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
