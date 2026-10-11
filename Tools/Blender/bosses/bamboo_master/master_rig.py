"""Esqueleto de Chikuō (el Maestro del Bambú) y traducción de controles de animación a huesos.

Un viejo maestro de kung fu de 2.6 m, flaco y de miembros largos (la grulla): la caricatura está en las manos y
los pies grandes, los brazos que le llegan a la rodilla y la cabeza un poco grande para que la cara (cejas y
bigotes larguísimos) se lea desde la cámara del juego. Esqueleto de juego limpio, como el de Kokuyō: manos bajo
antebrazos, pies bajo tibias, sin huesos de IK en el FBX. Además de la cadena humana tiene:
  * dedos en un bloque (Fing_*) y pulgar (Thumb_*): palma abierta, puño (el saludo puño contra palma), garra;
  * cejas (Brow_*_1..2) y bigotes (Whisker_*_1..3) en cadenas que se mueven solas (resortes horneados);
  * el saco: cuatro faldones de dos tramos (Robe_<ángulo>_1..2) y las dos colas de la faja (Sash_A/B_1..2);
  * el saco TIRADO (RobeT_*): una copia aplanada que vuela en el cambio de fase (oculta fuera de ese clip).

Ejes: Blender Z arriba, frente -Y, derecha del personaje = -X.
"""
import math
from mathutils import Vector, Matrix, Quaternion
import nindo_anim as NA
from nindo_anim import BoneDef, V, euler_q, basis_yz, compose, rot3

# ------------------------------------------------------------------ medidas (metros, pose de reposo)
ANKLE_Z = 0.13
HIP_J = Vector((-0.15, 0.0, 1.22))          # cabeza del muslo derecho
KNEE = Vector((-0.16, -0.05, 0.68))         # rodilla apenas adelantada: el IK sabe para dónde doblar
ANKLE = Vector((-0.16, 0.0, ANKLE_Z))
TOE = Vector((-0.16, -0.27, 0.04))
# punta y talón de la suela respecto del tobillo en y (la suela apoya en z 0): pivotes de un pie que se para en
# punta o se echa atrás sobre el talón. Pies grandes (40 cm): la caricatura del que está bien plantado
SOLE_TOE_Y, SOLE_HEEL_Y = -0.30, 0.11
SHOULDER = Vector((-0.30, 0.02, 1.95))
UPPER_LEN, FORE_LEN, HAND_LEN, FING_LEN = 0.44, 0.40, 0.11, 0.105
_u = Vector((-math.sin(math.radians(40)), 0.0, -math.cos(math.radians(40))))
ELBOW = SHOULDER + _u * UPPER_LEN
_l = (_u + Vector((0.0, -0.18, 0.0))).normalized()        # codo apenas doblado
WRIST = ELBOW + _l * FORE_LEN
_h = (_l + Vector((0.0, -0.05, 0.0))).normalized()
KNUCKLE = WRIST + _h * HAND_LEN
# centro de la palma en el espacio del hueso de la mano (Z del hueso = dorso): los controles de las manos dicen
# dónde está la PALMA (lo que pega en un golpe de palma), no la muñeca
PALM_LOCAL = Vector((0.0, 0.07, -0.03))
# pulgar: nace del costado de la palma cerca de la muñeca y apunta al índice
THUMB_BASE_LOCAL = Vector((0.035, 0.035, -0.025))

# faldones del saco: 4 paños de dos tramos (0° = frente, + = hacia su izquierda). Abiertos a los costados
# (las aberturas del saco largo): las piernas pasan entre los paños delanteros y traseros
ROBE_ANGLES = [38.0, 142.0, 218.0, 322.0]
ROBE_TOP_Z = 1.30
ROBE_R = (0.235, 0.19)
ROBE_FLARE = 9.0
ROBE_LEN = (0.27, 0.27)


def robe_name(a, seg):
    return f"Robe_{int(round(a)) % 360:03d}_{seg}"


def robe_frame(a):
    """(cabeza, dirección hacia abajo con el vuelo, normal hacia afuera, tangente) de un faldón."""
    r = math.radians(a)
    out = Vector((math.sin(r), -math.cos(r), 0.0))
    head = Vector((math.sin(r) * ROBE_R[0], -math.cos(r) * ROBE_R[1], ROBE_TOP_Z))
    down = (Vector((0, 0, -1)) * math.cos(math.radians(ROBE_FLARE)) + out * math.sin(math.radians(ROBE_FLARE))).normalized()
    tang = Vector((0, 0, 1)).cross(out).normalized()
    return head, down, out, tang


# cara (para el modelo y los resortes): frente de la cara en y, alto de las cejas y del labio
FACE_Y = -0.175
BROW_Z, LIP_Z = 2.385, 2.245
# faja: el nudo al frente a su izquierda, de donde cuelgan dos colas
SASH_Z = 1.34
SASH_KNOT = Vector((0.11, -0.215, 1.31))


def bones():
    B = [
        BoneDef("Root", (0, 0, 0), (0, 0, 0.3), None, True, (0, -1, 0)),
        BoneDef("Hips", (0, 0, 1.18), (0, 0, 1.38), "Root"),
        BoneDef("Spine", (0, 0, 1.40), (0, 0, 1.70), "Hips"),
        BoneDef("Chest", (0, 0, 1.72), (0, 0, 2.02), "Spine"),
        BoneDef("Neck", (0, 0.035, 2.03), (0, 0.0, 2.16), "Chest"),
        BoneDef("Head", (0, 0, 2.16), (0, 0, 2.56), "Neck"),
        # cejas: nacen sobre los ojos y barren hacia afuera, atrás y arriba como antenas (lo que se ve desde arriba)
        BoneDef("Brow_R_1", (-0.075, FACE_Y + 0.01, BROW_Z), (-0.25, -0.08, BROW_Z + 0.07), "Head", True, (0, -1, 0.3)),
        BoneDef("Brow_R_2", (-0.25, -0.08, BROW_Z + 0.07), (-0.42, 0.04, BROW_Z + 0.05), "Brow_R_1", True, (0, -1, 0.3)),
        # bigotes: caen de los costados de la boca hasta el pecho
        BoneDef("Whisker_R_1", (-0.045, FACE_Y - 0.035, LIP_Z), (-0.085, FACE_Y - 0.03, LIP_Z - 0.15), "Head", True, (0, -1, 0)),
        BoneDef("Whisker_R_2", (-0.085, FACE_Y - 0.03, LIP_Z - 0.15), (-0.095, FACE_Y - 0.01, LIP_Z - 0.32), "Whisker_R_1", True, (0, -1, 0)),
        BoneDef("Whisker_R_3", (-0.095, FACE_Y - 0.01, LIP_Z - 0.32), (-0.09, FACE_Y + 0.01, LIP_Z - 0.48), "Whisker_R_2", True, (0, -1, 0)),
        BoneDef("Clav_R", (-0.05, 0.02, 1.95), (-0.28, 0.02, 1.95), "Chest", True, (0, 0, 1)),
        BoneDef("UpperArm_R", SHOULDER, ELBOW, "Clav_R", True, (0, -1, 0)),
        BoneDef("Forearm_R", ELBOW, WRIST, "UpperArm_R", True, (0, -1, 0)),
        # mano: el eje Z es el dorso (hacia afuera en reposo: la palma mira al muslo)
        BoneDef("Hand_R", WRIST, KNUCKLE, "Forearm_R", True, (-1, 0, 0)),
        BoneDef("Fing_R", KNUCKLE, KNUCKLE + _h * FING_LEN, "Hand_R", True, (-1, 0, 0)),
        BoneDef("Thigh_R", HIP_J, KNEE, "Hips", True, (0, -1, 0)),
        BoneDef("Shin_R", KNEE, ANKLE, "Thigh_R", True, (0, -1, 0)),
        BoneDef("Foot_R", ANKLE, TOE, "Shin_R", True, (0, 0, 1)),
    ]
    B = NA.mirrored(B)
    # pulgares: el espejo de la tabla no sirve (el hueso nace en un punto del espacio de la mano); se ubican con
    # la orientación de reposo de cada mano
    for S, sg in (("R", 1.0), ("L", -1.0)):
        wr = Vector((WRIST.x * sg, WRIST.y, WRIST.z))
        hd = Vector((_h.x * sg, _h.y, _h.z))
        out = Vector((-sg, 0.0, 0.0))                       # dorso hacia afuera
        Rm = basis_yz(hd, out)
        base = wr + Rm @ Vector((THUMB_BASE_LOCAL.x * sg, THUMB_BASE_LOCAL.y, THUMB_BASE_LOCAL.z))
        tip_dir = (Rm @ Vector((0.45 * sg, 0.85, -0.35))).normalized()
        B.append(BoneDef("Thumb_" + S, base, base + tip_dir * 0.085, "Hand_" + S, True, tuple(out)))
    # faja: dos colas que cuelgan del nudo (a su izquierda, adelante)
    k = SASH_KNOT
    B += [
        BoneDef("Sash_A_1", k, k + Vector((0.01, -0.02, -0.24)), "Hips", True, (0, -1, 0)),
        BoneDef("Sash_A_2", k + Vector((0.01, -0.02, -0.24)), k + Vector((0.02, -0.03, -0.50)), "Sash_A_1", True, (0, -1, 0)),
        BoneDef("Sash_B_1", k + Vector((0.07, 0.0, -0.01)), k + Vector((0.09, -0.01, -0.21)), "Hips", True, (0, -1, 0)),
        BoneDef("Sash_B_2", k + Vector((0.09, -0.01, -0.21)), k + Vector((0.11, -0.02, -0.42)), "Sash_B_1", True, (0, -1, 0)),
    ]
    for a in ROBE_ANGLES:
        h, d, o, t = robe_frame(a)
        m = h + d * ROBE_LEN[0]
        B.append(BoneDef(robe_name(a, 1), h, m, "Hips", True, o))
        B.append(BoneDef(robe_name(a, 2), m, m + d * ROBE_LEN[1], robe_name(a, 1), True, o))
    # el saco tirado (cambio de fase): en reposo queda adentro de la espalda (oculto en el juego hasta ese clip);
    # cuello -> ruedo y las dos mangas abiertas: un saco aplanado que vuela y cae al piso
    B += [
        BoneDef("RobeT_Root", (0, 0.06, 1.98), (0, 0.06, 1.62), "Root", True, (0, -1, 0)),
        BoneDef("RobeT_Hem", (0, 0.06, 1.62), (0, 0.06, 1.12), "RobeT_Root", True, (0, -1, 0)),
        BoneDef("RobeT_ArmR", (-0.12, 0.06, 1.90), (-0.52, 0.06, 1.78), "RobeT_Root", True, (0, -1, 0)),
        BoneDef("RobeT_ArmL", (0.12, 0.06, 1.90), (0.52, 0.06, 1.78), "RobeT_Root", True, (0, -1, 0)),
        # marcador de frente (exportado: el validador de Unity comprueba que mire a +Z)
        BoneDef("Facing", (0, -0.35, 2.0), (0, -0.65, 2.0), "Root", True, (0, 0, 1)),
    ]
    return B


# huesos que resuelve el IK o la cadena principal: los 'extra' no pueden tocar a sus padres
IK_BONES = {"UpperArm_R", "Forearm_R", "Hand_R", "UpperArm_L", "Forearm_L", "Hand_L",
            "Thigh_R", "Shin_R", "Foot_R", "Thigh_L", "Shin_L", "Foot_L"}
ROBE_T = ("RobeT_Root", "RobeT_Hem", "RobeT_ArmR", "RobeT_ArmL")


def palm_rest(S):
    sg = 1.0 if S == "R" else -1.0
    wr = Vector((WRIST.x * sg, WRIST.y, WRIST.z))
    Rm = basis_yz(Vector((_h.x * sg, _h.y, _h.z)), Vector((-sg, 0.0, 0.0)))
    return wr + Rm @ PALM_LOCAL, Vector((_h.x * sg, _h.y, _h.z)), Vector((-sg, 0.0, 0.0))


_PR, _PRD, _PRU = palm_rest("R")
_PL, _PLD, _PLU = palm_rest("L")

# ------------------------------------------------------------------ controles por defecto
NEUTRAL = {
    "hips": (0.0, 0.0, 0.0), "hips_rot": (0.0, 0.0, 0.0),
    "spine": (0.0, 0.0, 0.0), "chest": (0.0, 0.0, 0.0), "neck": (0.0, 0.0, 0.0), "head": (0.0, 0.0, 0.0),
    "clav_r": (0.0, 0.0, 0.0), "clav_l": (0.0, 0.0, 0.0),
    # manos: centro de la PALMA, hacia dónde apuntan los dedos y hacia dónde mira el dorso
    "hand_r": tuple(_PR), "hand_r_dir": tuple(_PRD), "hand_r_up": tuple(_PRU), "elbow_r": (-0.4, 0.8, -0.2),
    "hand_l": tuple(_PL), "hand_l_dir": tuple(_PLD), "hand_l_up": tuple(_PLU), "elbow_l": (0.4, 0.8, -0.2),
    # dedos: 0 = palma abierta (golpe de palma), 95 = puño; pulgar: 0 = abierto, 60 = cruzado sobre la palma
    "fing_r": 0.0, "fing_l": 0.0, "thumb_r": 0.0, "thumb_l": 0.0,
    "foot_r": tuple(ANKLE), "foot_r_rot": (0.0, 0.0, 0.0), "knee_r": (-0.1, -1.0, 0.0),
    "foot_l": (-ANKLE.x, ANKLE.y, ANKLE.z), "foot_l_rot": (0.0, 0.0, 0.0), "knee_l": (0.1, -1.0, 0.0),
    "travel": 0.0, "lift": 0.0, "breath": 0.0, "extra": {},
    # el saco tirado: 0 = guardado adentro del cuerpo; 1 = libre en el mundo (robe_pos/robe_rot/robe_fold)
    "robe_free": 0.0,
}


class Solver:
    """Traduce un diccionario de controles a la pose de todos los huesos (ver nindo_anim.Pose)."""

    def __init__(self, rig):
        self.rig = rig
        self.misses = {}
        R = rig
        # ejes de curvatura de dedos y pulgar en el reposo (giran sobre su eje X propio)
        self.curl_axis = {n: rot3(R.rest[n]).col[0].normalized() for n in ("Fing_R", "Fing_L", "Thumb_R", "Thumb_L")}

    def solve(self, pose, c):
        c = {**NEUTRAL, **{k: v for k, v in c.items() if v is not None}}
        R = self.rig
        # el cuerpo (cadera, manos) se autora relativo al transform del juego; lo que queda clavado en el MUNDO (pies
        # apoyados, el saco tirado en el piso) se corre con el avance del golpe
        sh = Vector((0.0, c["travel"], c["lift"]))
        up = Vector((0.0, 0.0, c["lift"]))
        # ---- cadera y tronco
        hip_rest = R.rest["Hips"]
        Hm = compose(hip_rest.translation + V(c["hips"]) + up, euler_q(c["hips_rot"]).to_matrix() @ rot3(hip_rest))
        # la cadera baja lo justo para que los dos pies lleguen a su apoyo (pies clavados aunque la clave pida una
        # cadera un poco alta)
        drop = 0.0
        for s_ in ("r", "l"):
            S_ = s_.upper()
            J = (Hm @ R.rel["Thigh_" + S_]).translation
            A = V(c["foot_" + s_]) + sh
            reach = (R.length["Thigh_" + S_] + R.length["Shin_" + S_]) * 0.985
            dxy = Vector((J.x - A.x, J.y - A.y)).length
            if dxy < reach:
                need = (J.z - A.z) - math.sqrt(reach * reach - dxy * dxy)
                drop = max(drop, need)
        if drop > 0.0:
            Hm.translation.z -= drop
        self.hip_drop = drop
        pose.place("Hips", Hm)
        br = c["breath"]
        pose.delta("Spine", c["spine"])
        pose.delta("Chest", V(c["chest"]) + Vector((-2.5 * br, 0.0, 0.0)))
        pose.delta("Neck", V(c["neck"]) + Vector((1.2 * br, 0.0, 0.0)))
        pose.delta("Head", c["head"])
        pose.delta("Clav_R", V(c["clav_r"]) + Vector((0.0, -1.8 * br, 0.0)))
        pose.delta("Clav_L", V(c["clav_l"]) + Vector((0.0, 1.8 * br, 0.0)))
        # ---- brazos: la palma va donde dice el control
        misses = {}
        for s in ("r", "l"):
            S = s.upper()
            Rh = basis_yz(c["hand_" + s + "_dir"], c["hand_" + s + "_up"])
            palm = V(c["hand_" + s]) + up
            wrist = palm - Rh @ PALM_LOCAL
            self.reach_with_clavicle(pose, S, wrist)
            misses["hand_" + s] = pose.two_bone("UpperArm_" + S, "Forearm_" + S, wrist, c["elbow_" + s])
            pose.place("Hand_" + S, compose(pose.tail("Forearm_" + S), Rh))
            pose.twist_follow("Forearm_" + S, "Hand_" + S, 0.5)
            # dedos y pulgar: giran sobre su eje (hacia la palma con ángulo positivo)
            pose.delta("Fing_" + S, Quaternion(self.curl_axis["Fing_" + S], -math.radians(c["fing_" + s])))
            pose.delta("Thumb_" + S, Quaternion(self.curl_axis["Thumb_" + S], -math.radians(c["thumb_" + s])))
        # ---- piernas
        miss_legs = 0.0
        for s in ("r", "l"):
            S = s.upper()
            ank = V(c["foot_" + s]) + sh
            pr = c["foot_" + s + "_rot"]
            Rf = (Matrix.Rotation(math.radians(pr[2]), 3, 'Z') @ Matrix.Rotation(math.radians(pr[0]), 3, 'X')
                  @ Matrix.Rotation(math.radians(pr[1]), 3, 'Y')) @ rot3(R.rest["Foot_" + S])
            miss_legs = max(miss_legs, pose.two_bone("Thigh_" + S, "Shin_" + S, ank, c["knee_" + s]))
            pose.place("Foot_" + S, compose(pose.tail("Shin_" + S), Rf))
        # ---- el saco tirado: libre en el mundo (vuela y cae); los pliegues doblan el ruedo y las mangas
        if (c.get("robe_free", 0.0) or 0.0) >= 0.5:
            Mr = compose(V(c["robe_pos"]) + sh, euler_q(c["robe_rot"]).to_matrix() @ rot3(R.rest["RobeT_Root"]))
            pose.place("RobeT_Root", Mr)
            fold = c.get("robe_fold", (0.0, 0.0, 0.0))
            pose.delta("RobeT_Hem", (fold[0], 0.0, 0.0))
            pose.delta("RobeT_ArmR", (0.0, fold[1], -fold[2]))
            pose.delta("RobeT_ArmL", (0.0, -fold[1], fold[2]))
        # ---- giros extra de huesos secundarios (cejas, bigotes, faldones...)
        for bn, r in sorted(c["extra"].items(), key=lambda kv: R.names.index(kv[0])):
            assert bn not in IK_BONES, bn
            pose.delta(bn, r)
        misses["legs"] = miss_legs
        self.misses = misses
        return misses

    def reach_with_clavicle(self, pose, S, target, max_deg=26.0):
        """Si la muñeca no llega, el hombro se adelanta (la clavícula gira hacia el objetivo, como la escápula al
        estirarse): un golpe de palma estirado gana ~15 cm sin despegar la mano de donde tiene que pegar."""
        R = self.rig
        cl, ua, fa = "Clav_" + S, "UpperArm_" + S, "Forearm_" + S
        reach = (R.length[ua] + R.length[fa]) * 0.985
        for _ in range(2):
            shp = (pose.get(cl) @ R.rel[ua]).translation
            ex = (V(target) - shp).length - reach
            if ex <= 0.0:
                return
            ch = pose.head(cl)
            a = (shp - ch)
            b = (V(target) - ch)
            ax = a.cross(b)
            if ax.length < 1e-6:
                return
            ang = min(ex / max(a.length, 1e-3), math.radians(max_deg))
            M = pose.get(cl)
            Rq = Quaternion(ax.normalized(), ang).to_matrix()
            pose.place(cl, compose(ch, Rq @ rot3(M)))
