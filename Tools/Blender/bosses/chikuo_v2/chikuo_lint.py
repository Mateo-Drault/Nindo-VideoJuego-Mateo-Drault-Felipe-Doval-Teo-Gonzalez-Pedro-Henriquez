"""Mediciones de los clips del Chikuō ermitaño (sobre las poses resueltas y horneadas, antes de exportar). Lo que llega
a Unity está medido (contrato de calidad, Docs/handoff/diseno/chikuo_v2.md 16.7):

* el IK llega (manos en la flauta y en el culmo, pies en el piso o en el nudo);
* los loops no tienen costura (ni de pose ni de velocidad: < 1°);
* los pies apoyados no patinan con el avance que aplica el juego (< 2 cm), y la suela que toca el piso tampoco;
* manos y pies en la caña trabados (< 2 cm) con el arco del código aplicado;
* ningún hueso gira más de 45° en un cuadro fuera de un corte declarado;
* la muñeca dentro de lo que dobla una persona (la elipse de flexión y desvío de team_limbs);
* el cuerpo contra sí mismo (cápsulas por dentro de la malla: la flauta, los antebrazos, las piernas) y la flauta contra
  el culmo;
* la primera y la última pose contra la pose con la que encadena (< 5° o la tapa el fundido del código);
* (con la malla, en el build) nada atraviesa el piso ni el culmo.
"""
import math
from mathutils import Vector
import nindo_anim as NA
import chikuo_rig as CR
import chikuo_anim as CA

SNAP_DEG = 45.0
CHAIN_WARN, CHAIN_FAIL = 5.0, 12.0
SPRING_PREFIX = ("Acc_", "Cloak_", "Sleeve_", "Skirt_", "Topknot_", "AccCol_")
# muñeca (la de master_rig / team_limbs): flexión, extensión, desvío radial y cubital en grados
FLEX, EXTEND, RADIAL, ULNAR = 75.0, 65.0, 25.0, 38.0
WRIST_FREE_MAX, WRIST_GRIP_MAX = 1.0, 1.35
TWIST_MAX = 85.0
SOLE_TOUCH = 0.015
SLIP_MAX = 0.02


def seg_dist(p1, q1, p2, q2):
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


# ------------------------------------------------------------------ cápsulas del cuerpo (por dentro de la malla)
def capsules(rig, W):
    def tail(b, t=1.0):
        return W[b] @ Vector((0.0, rig.length[b] * t, 0.0))
    cap = {"tronco": (W["Hips"].translation + Vector((0, 0, 0.0)), tail("Spine2", 0.8), 0.12),
           "cabeza": (tail("Head", 0.2), tail("Head", 0.55), 0.10)}
    for S in "RL":
        cap[f"muslo {S}"] = (W["Thigh_" + S].translation, tail("Thigh_" + S), 0.075)
        cap[f"tibia {S}"] = (W["Shin_" + S].translation, tail("Shin_" + S), 0.05)
        cap[f"brazo {S}"] = (W["UpperArm_" + S].translation, tail("UpperArm_" + S), 0.045)
        cap[f"antebrazo {S}"] = (W["Forearm_" + S].translation, tail("Forearm_" + S, 0.85), 0.035)
    M = W["Staff"]
    ax = NA.rot3(M).col[1]
    cap["flauta"] = (M.translation, M.translation + ax * CR.STAFF_LEN, CR.STAFF_R)
    return cap


PAIRS = [("flauta", t) for t in ("tronco", "cabeza", "muslo R", "muslo L", "tibia R", "tibia L")] + \
        [(f"antebrazo {S}", t) for S in "RL" for t in ("tronco", "cabeza")] + \
        [("muslo R", "muslo L"), ("tibia R", "tibia L"), ("tibia R", "muslo L"), ("tibia L", "muslo R")]


def self_clearance(rig, frames):
    out = {}
    for i, W in enumerate(frames):
        cap = capsules(rig, W)
        for a, b in PAIRS:
            (p1, q1, r1), (p2, q2, r2) = cap[a], cap[b]
            cl = seg_dist(p1, q1, p2, q2) - r1 - r2
            k = f"{a} / {b}"
            if k not in out or cl < out[k][0]:
                out[k] = (round(cl, 3), i)
    return out


def staff_vs_culm(frames, z_lo=-4.4, z_hi=3.0):
    """Holgura mínima (m) entre la flauta y el culmo recto del clip de posado: (holgura, cuadro)."""
    best = (9.0, 0)
    for i, W in enumerate(frames):
        M = W["Staff"]
        a = M.translation
        b = a + NA.rot3(M).col[1] * CR.STAFF_LEN
        d = seg_dist(a, b, Vector((0, 0, z_lo)), Vector((0, 0, z_hi)))
        # el radio del culmo a la altura del punto más cercano (aproximado por el medio del bastón)
        cl = d - CA.culm_r(max(z_lo, min(z_hi, (a.z + b.z) * 0.5))) - CR.STAFF_R
        if cl < best[0]:
            best = (round(cl, 3), i)
    return best


# ------------------------------------------------------------------ giros por cuadro
def local_quats(rig, frames):
    return [{n: q for n, (l, q) in rig.to_local(W).items()} for W in frames]


def snaps(rig, lq, cuts=()):
    """El mayor giro local de un hueso entre dos cuadros seguidos (fuera de los cortes): (grados, hueso, cuadro)."""
    worst = (0.0, "", 0)
    for i in range(1, len(lq)):
        if i in cuts or (i - 1) in cuts:
            continue
        a, b = lq[i - 1], lq[i]
        for n in rig.names:
            d = NA.quat_angle_deg(a[n], b[n])
            if d > worst[0]:
                worst = (round(d, 1), n, i)
    return worst


def loop_seam(rig, lq):
    """Costura del loop: el último cuadro contra el primero (pose) y el salto de velocidad a través de la costura (grados):
    cuánto más cambia la velocidad de un hueso en la costura que en el peor de los cuadros de adentro del mismo loop (la
    segunda diferencia contra las vecinas). Corriendo, la tibia cambia de velocidad 8° por cuadro en cualquier cuadro: lo
    que se ve saltar es una costura peor que eso, no un número fijo."""
    n = len(lq) - 1
    pose = max(NA.quat_angle_deg(lq[0][b], lq[n][b]) for b in rig.names)
    vel = 0.0
    for b in rig.names:
        if b.startswith("AccCol_"):
            continue
        d = [NA.quat_angle_deg(lq[i][b], lq[i + 1][b]) for i in range(n)]

        def exc(i):
            dp, di, do, dn = d[(i - 2) % n], d[(i - 1) % n], d[i % n], d[(i + 1) % n]
            return abs(do - di) - max(abs(di - dp), abs(dn - do))
        inside = max([exc(i) for i in range(2, n - 1)] or [0.0])
        vel = max(vel, exc(0) - max(0.0, inside))
    return round(pose, 3), round(max(0.0, vel), 3)


# ------------------------------------------------------------------ muñecas
class WristMeter:
    def __init__(self, rig):
        self.side = {}
        for S in "RL":
            Rf0, Rh0 = NA.rot3(rig.rest["Forearm_" + S]), NA.rot3(rig.rest["Hand_" + S])
            _, _, dors, thumb = CR.hand_frame(S)
            self.side[S] = (Rf0.transposed() @ Rh0, (Rh0.transposed() @ -dors).normalized(), (Rh0.transposed() @ thumb).normalized())

    def angles(self, W, S):
        n0, n, l = self.side[S]
        D = (NA.rot3(W["Forearm_" + S]) @ n0).transposed() @ NA.rot3(W["Hand_" + S])
        y = D.col[1]
        flex = math.degrees(math.atan2(y.dot(n), y.y))
        dev = math.degrees(math.atan2(y.dot(l), y.y))
        q = D.to_quaternion()
        tw = (2.0 * math.degrees(math.atan2(q.y, q.w)) + 180.0) % 360.0 - 180.0
        return flex, dev, tw


def wrist_excess(flex, dev):
    return math.hypot(flex / (FLEX if flex >= 0.0 else EXTEND), dev / (RADIAL if dev >= 0.0 else ULNAR))


def wrist_report(meter, frames, ctrls):
    out = {}
    for S in "RL":
        s = S.lower()
        worst = (0.0, 0, 0.0, 0.0, False)
        tw_max = 0.0
        for i, (W, c) in enumerate(zip(frames, ctrls)):
            flex, dev, tw = meter.angles(W, S)
            ex = wrist_excess(flex, dev)
            held = (c.get("gw_" + s) or 0.0) >= 0.5 or (c.get("cw_" + s) or 0.0) >= 0.5 or \
                   (c.get("sw_h" + s) or 0.0) >= 0.5
            lim = WRIST_GRIP_MAX if held else WRIST_FREE_MAX
            if ex / lim > worst[0] / (WRIST_GRIP_MAX if worst[4] else WRIST_FREE_MAX):
                worst = (ex, i, flex, dev, held)
            tw_max = max(tw_max, abs(tw))
        out[S] = {"excess": round(worst[0], 2), "at": worst[1], "flex": round(worst[2]), "dev": round(worst[3]),
                  "held": worst[4], "twist_max": round(tw_max)}
    return out


# ------------------------------------------------------------------ pies
def sole_points(rig):
    out = {}
    for S, sx in (("R", 1.0), ("L", -1.0)):
        x = CR.ANKLE.x * sx
        foot = [Vector((x + d, y, 0.0)) for y in (CR.SOLE_HEEL_Y, CR.BALL.y) for d in (-0.06, 0.06)]
        # los centros de la bola y del talón: girar sobre la bola (la barrida, los giros) no es patinar
        foot += [Vector((CR.BALL.x * sx, CR.BALL.y, 0.0)), Vector((x, CR.SOLE_HEEL_Y, 0.0))]
        toe = [Vector((CR.TOE_TIP.x * sx + d, CR.SOLE_TOE_Y, 0.0)) for d in (-0.045, 0.045)]
        out["Foot_" + S] = [rig.rest_inv["Foot_" + S] @ p for p in foot]
        out["Toe_" + S] = [rig.rest_inv["Toe_" + S] @ p for p in toe]
    return out


def sole_slip(rig, frames, roots, floor_z=0.0):
    """Lo que patina cada suela mientras toca el piso, con el avance del juego (el punto apoyado que MENOS se mueve en
    cada par de cuadros: rodar del talón a la punta no es patinar). {pie: (cm del peor apoyo, [desde, hasta])}."""
    pts = sole_points(rig)
    out = {}
    for S in "RL":
        tracks = [[W[bn] @ p + r for W, r in zip(frames, roots)] for bn in ("Foot_" + S, "Toe_" + S) for p in pts[bn]]
        worst, wseg, run, run_from = 0.0, [0, 0], 0.0, None
        for i in range(1, len(frames)):
            best = None
            for tr in tracks:
                a, b = tr[i - 1], tr[i]
                if a.z < floor_z + SOLE_TOUCH and b.z < floor_z + SOLE_TOUCH:
                    d = Vector((b.x - a.x, b.y - a.y)).length
                    best = d if best is None else min(best, d)
            if best is None:
                run, run_from = 0.0, None
                continue
            if run_from is None:
                run_from = i - 1
            run += best
            if run > worst:
                worst, wseg = run, [run_from, i]
        out[S] = (round(worst * 100.0, 2), wseg)
    return out


def sole_floor(rig, frames, roots):
    """El punto más bajo de las suelas (m) y en qué cuadro: los pies no se meten en el piso."""
    pts = sole_points(rig)
    lo = (9.0, 0)
    for i, (W, r) in enumerate(zip(frames, roots)):
        for S in "RL":
            for bn in ("Foot_" + S, "Toe_" + S):
                for p in pts[bn]:
                    z = (W[bn] @ p).z
                    if z < lo[0]:
                        lo = (round(z, 3), i)
    return lo


# ------------------------------------------------------------------ contactos con la caña
def culm_contacts(rig, frames, ctrls, theta):
    """Manos agarradas al culmo (cw >= 0.99): cuánto se despega su punto de agarre del culmo DOBLADO 'theta' grados (con
    el modelo en el PerchNode, como lo pone el código) a lo largo de cada agarre seguido, en las dos direcciones del arco
    (el peso para adelante y para atrás). Devuelve {mano: (cm, cuadro)}."""
    out = {}
    for s in "rl":
        S = s.upper()
        worst = (0.0, 0)
        for d in ((0.0, 1.0, 0.0), (0.0, -1.0, 0.0), (1.0, 0.0, 0.0)):
            start = None
            for i, (W, c) in enumerate(zip(frames, ctrls)):
                if (c.get("cw_" + s) or 0.0) < 0.99:
                    start = None
                    continue
                p = W["Hand_" + S] @ CA.culm_local(CA.culm_r(c.get("cz_" + s) or 0.0))
                code, on_seg = CA.on_bent(p, theta, d)
                if start is None:
                    start = on_seg - code
                err = (on_seg - code - start).length + 0.0
                # y además: el eje del culmo recto pasa por el punto del agarre (el IK llegó)
                axis = Vector((p.x, p.y, 0.0)).length
                err = max(err, axis)
                if err > worst[0]:
                    worst = (err, i)
        out[S] = (round(worst[0] * 100.0, 2), worst[1])
    return out


def feet_on_node(rig, frames, ctrls, spans, theta):
    """Pies apoyados en el anillo del nudo (spans = [(desde, hasta)] del clip): la suela no se corre en el tramo del nudo
    (con el arco aplicado) y no se mete en el anillo ni queda en el aire (la suela más baja a 0 +- 2 cm)."""
    pts = sole_points(rig)
    out = {}
    for S in "RL":
        worst = (0.0, 0)
        for a, b in spans:
            ref = None
            for i in range(a, b + 1):
                W = frames[i]
                ps = [W[bn] @ p for bn in ("Foot_" + S,) for p in pts[bn]]
                low = min(p.z for p in ps)
                ank = W["Foot_" + S].translation
                code, on_seg = CA.on_bent(ank, theta, (0.0, 1.0, 0.0))
                if ref is None:
                    ref = on_seg - code
                err = max((on_seg - code - ref).length, abs(low) - 0.02 if abs(low) > 0.02 else 0.0)
                if err > worst[0]:
                    worst = (err, i)
        out[S] = (round(worst[0] * 100.0, 2), worst[1])
    return out


# ------------------------------------------------------------------ encadenado
def bone_delta(rig, Wa, Wb):
    la, lb = rig.to_local(Wa), rig.to_local(Wb)
    worst, wb = 0.0, ""
    for n in rig.names:
        if n.startswith(SPRING_PREFIX) or n == "Staff":
            continue
        d = NA.quat_angle_deg(la[n][1], lb[n][1])
        if d > worst:
            worst, wb = d, n
    hip = (Wa["Hips"].translation - Wb["Hips"].translation).length
    st = (Wa["Staff"].translation - Wb["Staff"].translation).length
    return round(worst, 2), wb, round(hip * 100.0, 1), round(st * 100.0, 1)
