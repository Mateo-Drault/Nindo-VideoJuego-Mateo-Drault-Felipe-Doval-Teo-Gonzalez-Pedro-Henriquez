"""Poses de prueba del Chikuō ermitaño: las posturas extremas que va a pedir la pelea (la hoja de acciones del concepto)
para revisar los pesos antes de animar, y el clip 'PoseTest' del FBX (para mirarlas en Unity con 'pose PoseTest').

Cada pose son controles de chikuo_rig.Poser; las cadenas (capa, cascabeles, barba, mangas, falda, colas) se asientan con
los resortes de nindo_anim sosteniendo la pose 2 s, con las esferas del cuerpo y de los brazos.
"""
import math
from mathutils import Vector
import nindo_anim as NA
import chikuo_rig as CR

S2 = math.sqrt(0.5)

POSES = {
    # parado relajado, los brazos colgando y la flauta parada en la derecha (la espera en el piso)
    "relaxed": dict(hips=(0, 0.01, -0.02), spine=(4, 0, 0), spine1=(4, 0, 0), spine2=(7, 0, 0), neck=(-7, 0, 0), head=(-5, 0, 0),
                    staff_world=((-0.42, -0.14, 0.0), (0, 0, 1), (0, -1, 0)), grip_r=(1.22, (-1, 0, 0)),
                    elbow_r=(-0.6, 0.6, -0.3), hand_l=(0.33, -0.04, 1.10), hand_l_dir=(0.12, -0.1, -1), hand_l_up=(1, 0, 0),
                    elbow_l=(0.5, 0.6, -0.4), fingers_r="grip_staff", fingers_l="relaxed"),
    # los dos brazos arriba agarrando la caña (trepar, colgarse de las manos)
    "arms_up": dict(spine1=(-3, 0, 0), spine2=(-6, 0, 0), head=(-12, 0, 0),
                    hand_r=(-0.13, -0.10, 2.60), hand_r_dir=(0.1, -0.1, 1), hand_r_up=(0, 1, 0), elbow_r=(-1, 0.3, 0),
                    hand_l=(0.13, -0.10, 2.48), hand_l_dir=(-0.1, -0.1, 1), hand_l_up=(0, 1, 0), elbow_l=(1, 0.3, 0),
                    fingers_r="grip_stalk", fingers_l="grip_stalk"),
    # trepando (la hoja de acciones): la derecha arriba en la caña, la izquierda abajo, la rodilla derecha subida
    "climb": dict(hips=(0, -0.06, 0.05), hips_rot=(8, 0, -8), spine=(4, 0, 4), spine2=(4, 0, 6), neck=(-10, 0, -10), head=(-6, 0, -18),
                  hand_r=(-0.05, -0.22, 2.44), hand_r_dir=(0.2, -0.3, 1), hand_r_up=(0.4, 1, 0), elbow_r=(-1, 0.2, -0.3),
                  hand_l=(0.08, -0.24, 1.86), hand_l_dir=(-0.2, -0.4, 0.8), hand_l_up=(-0.4, 1, 0), elbow_l=(1, 0.3, -0.6),
                  foot_r=(-0.10, -0.26, 0.82), foot_r_rot=(-20, 0, 18), knee_r=(-0.4, -1, 0.3),
                  foot_l=(0.15, -0.14, 0.30), foot_l_rot=(-10, 0, -10), knee_l=(0.3, -1, 0),
                  fingers_r="grip_stalk", fingers_l="grip_stalk", toe_l=-20),
    # posado en el nudo (cuclillas profundas, las rodillas abiertas), la izquierda arriba en el culmo y la derecha sobre
    # la flauta cruzada en los hombros (PerchIdle)
    "perch": dict(hips=(0, 0.20, -0.62), hips_rot=(30, 0, 0), spine=(8, 0, 0), spine1=(6, 0, 0), spine2=(8, 0, 0), neck=(-16, 0, 0),
                  head=(-12, 0, 0), foot_r=(-0.17, 0.02, 0.115), foot_l=(0.17, 0.02, 0.115), foot_r_rot=(0, 0, -28),
                  foot_l_rot=(0, 0, 28), knee_r=(-0.9, -1, 0.2), knee_l=(0.9, -1, 0.2),
                  staff_world=((-1.05, 0.26, 1.18), (1, -0.02, 0.06), (0, 1, 0)), grip_r=(0.62, (0, 1, 0.6)),
                  elbow_r=(-1, -0.4, -0.6), hand_l=(0.06, -0.12, 1.32), hand_l_dir=(-0.4, -0.2, 0.9), hand_l_up=(-0.3, 1, 0),
                  elbow_l=(1, -0.2, -0.5), fingers_r="grip_staff", fingers_l="grip_stalk", toe_r=12, toe_l=12),
    # colgado cabeza abajo de las corvas, soplando un dardo con la flauta de cerbatana (la hoja original)
    "hang": dict(hips=(0, 0.06, -1.40), hips_rot=(168, 0, 0), spine=(-6, 0, 0), spine2=(-8, 0, 0), neck=(18, 0, 0), head=(24, 0, 0),
                 foot_r=(-0.12, 0.34, 0.02), foot_l=(0.12, 0.34, 0.02), knee_r=(0, -1, 1), knee_l=(0, -1, 1),
                 foot_r_rot=(150, 0, 0), foot_l_rot=(150, 0, 0),
                 staff_lips=(CR.STAFF_LEN, (0.25, 0.85, 0.45), (0, 0, 1)), grip_r=(CR.STAFF_LEN - 0.34, (0, 0, -1)),
                 grip_l=(CR.STAFF_LEN - 0.18, (0, 0, -1)), elbow_r=(-1, 0, 0.3), elbow_l=(1, 0, 0.3),
                 fingers_r="grip_staff", fingers_l="grip_staff", face="blow"),
    # tocando la flauta de costado (la presentación): el agujero de soplar en los labios, la flauta hacia su derecha
    "flute": dict(spine2=(4, 0, 0), neck=(-4, 0, 0), head=(6, 0, -6),
                  staff_lips=(CR.STAFF_LEN - CR.STAFF_FLUTE, (0.92, 0.25, 0.30), (0, -1, 0.3)),
                  grip_l=(CR.STAFF_LEN - 0.24, (0, -1, 0.6), -1.0), grip_r=(CR.STAFF_LEN - 0.48, (0, -1, 0.6), -1.0),
                  elbow_r=(-1, 0.2, -0.6), elbow_l=(1, 0.2, -0.6), fingers_r="flute", fingers_l="flute", face="flute"),
    # de cerbatana desde arriba: la flauta de punta hacia Kaito (adelante y abajo), las dos manos cerca de la boquilla
    "blowpipe": dict(spine2=(10, 0, 0), neck=(-2, 0, 0), head=(12, 0, 0),
                     staff_lips=(CR.STAFF_LEN, (0, 0.82, 0.57), (0, 0, 1)), grip_l=(CR.STAFF_LEN - 0.16, (0, 0.2, 1)),
                     grip_r=(CR.STAFF_LEN - 0.33, (0, 0.2, 1)), elbow_r=(-1, 0.2, -0.4), elbow_l=(1, 0.2, -0.4),
                     fingers_r="grip_staff", fingers_l="grip_staff", face="blow"),
    # la patada voladora en picada (la hoja de acciones): la derecha estirada adelante y abajo, la izquierda recogida
    "kick": dict(hips=(0, 0.05, 0.10), hips_rot=(-24, 0, 0), spine=(-6, 0, 0), spine1=(-6, 0, 0), spine2=(-4, 0, 0), neck=(14, 0, 0),
                 head=(16, 0, 0), foot_r=(-0.10, -0.82, 0.84), foot_r_rot=(-62, 0, 0), knee_r=(0, -1, 0.6),
                 foot_l=(0.16, -0.10, 0.92), foot_l_rot=(-30, 0, 0), knee_l=(0.2, -1, 1), toe_r=-20,
                 hand_r=(-0.62, 0.30, 1.62), hand_r_dir=(-1, 0.4, 0.2), hand_r_up=(0, 0, 1), elbow_r=(-0.3, 1, -0.3),
                 hand_l=(0.62, 0.06, 1.78), hand_l_dir=(1, 0.1, 0.3), hand_l_up=(0, -1, 0.5), elbow_l=(0.3, 1, -0.3),
                 fingers_r="claw", fingers_l="claw"),
    # girando la flauta-bastón (la hoja de acciones): las piernas abiertas y dobladas, la flauta cruzada adelante
    "spin": dict(hips=(0, 0.02, -0.20), spine=(6, 0, 0), spine1=(4, 0, -6), spine2=(4, 0, -8), neck=(-6, 0, 8), head=(-4, 0, 6),
                 foot_r=(-0.48, 0.04, 0.115), foot_l=(0.48, 0.04, 0.115), foot_r_rot=(0, 0, -20), foot_l_rot=(0, 0, 20),
                 knee_r=(-0.8, -1, 0), knee_l=(0.8, -1, 0),
                 staff_world=((-1.05, -0.52, 1.30), (1, 0.08, 0.05), (0, -0.4, 1)), grip_r=(0.76, (0, -1, 0.6)),
                 grip_l=(1.36, (0, -1, 0.6)), elbow_r=(-1, 0.5, -0.5), elbow_l=(1, 0.5, -0.5), fingers_r="grip_staff",
                 fingers_l="grip_staff"),
}
# el orden de PoseTest y de las hojas, con el recorte del concepto que le corresponde y el encuadre (centro, escala)
ORDER = [("relaxed", None, (0, 0, 1.25), 2.8), ("arms_up", None, (0, 0, 1.4), 3.1), ("climb", ("climb", "trepando"), (0, -0.1, 1.35), 2.9),
         ("perch", ("perch", "posado"), (0, 0.05, 0.85), 2.2), ("hang", ("hang", "colgado"), (0, 0.05, -0.55), 2.6),
         ("flute", None, (0, 0, 1.5), 2.6), ("blowpipe", None, (0, -0.4, 1.5), 2.8), ("kick", ("leap", "salto"), (0, -0.25, 1.25), 2.9),
         ("spin", None, (0, -0.1, 1.2), 2.8)]
FACE_POSES = ("grin", "blow", "laugh", "flute")
# lo que se sube el modelo en las hojas de poses para que no quede bajo el piso (colgado: la raíz va en el nudo de la caña)
SHEET_LIFT = {"hang": 1.95}


def colliders(rig):
    """Esferas para los resortes de las poses (hueso, centro en el espacio del hueso, radio): las del cuerpo del FBX y,
    solo acá, la cabeza y los brazos (la capa no atraviesa el brazo que se levanta)."""
    out = [(b, rig.rest_inv[b] @ c, r) for _, b, c, r in CR.CHAIN_COLLIDERS]
    out.append(("Head", rig.rest_inv["Head"] @ Vector((0, 0.0, 2.14)), 0.105))
    for S in "RL":
        for bn, t, r in (("UpperArm_" + S, 0.35, 0.13), ("UpperArm_" + S, 0.8, 0.13), ("Forearm_" + S, 0.4, 0.11)):
            h = rig.rest[bn].translation
            tail = rig.rest[bn] @ Vector((0, rig.length[bn], 0))
            out.append((bn, rig.rest_inv[bn] @ h.lerp(tail, t), r))
    return out


def springs(rig):
    cols = colliders(rig)
    out = []
    for bones, k, hang, mx in CR.chains():
        out.append(NA.Spring(bones, k=k, damp=0.2, grav=3.0, max_deg=mx, hang=hang, floor=0.02 if bones[0] != "Topknot_1" else None,
                             colliders=cols))
    return out


def solve(rig, name, settle=True):
    """W (matrices en espacio de la armadura) de una pose, con las cadenas asentadas."""
    P = CR.Poser(rig)
    pose = NA.Pose(rig)
    misses = P.solve(pose, POSES[name])
    for n in rig.names:
        pose.get(n)
    W = pose.W
    if settle:
        frames = [W]
        NA.run_springs(rig, frames, springs(rig), [Vector()], loop=False, preroll=2.0)
        W = frames[0]
    return W, misses


def face_pose(rig, face):
    """El reposo con una cara (para la hoja de la cabeza)."""
    P = CR.Poser(rig)
    pose = NA.Pose(rig)
    P.solve(pose, {"face": face, "hand_r": None})
    for n in rig.names:
        pose.get(n)
    return pose.W
