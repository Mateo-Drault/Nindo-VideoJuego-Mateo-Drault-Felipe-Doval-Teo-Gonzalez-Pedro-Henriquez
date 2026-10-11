"""Poses de prueba del esqueleto de Chikuō y los dos clips de la etapa del modelo: 'Idle' (la guardia de la fase 1,
respirando) y 'PoseTest' (reposo -> guardia -> caballo con palma -> patada de grulla -> bastón -> manos -> reposo),
para ver en Unity cómo deforman hombros, rodillas, faldones, mangas y dedos. Los clips de pelea son de la etapa 2.

Posiciones en metros. Cadera y manos van relativas al transform del personaje; pies en el MUNDO del clip. Frente = -Y,
su derecha = -X; giros en grados (x + = adelante, y + = hacia su izquierda, z + = gira a su izquierda). Un pie apoyado
plano tiene el tobillo en z = 0.13 y cabeceo 0.
"""
import copy
from mathutils import Vector
import master_rig as MR
from nindo_anim import Key, Clip

AZ = MR.ANKLE_Z


def mod(base, **kw):
    """Copia de una pose con cambios; 'extra' se combina hueso por hueso."""
    p = copy.deepcopy(base)
    ex = kw.pop("extra", None)
    p.update(kw)
    if ex:
        e = dict(p.get("extra", {}))
        e.update(ex)
        p["extra"] = e
    return p


def n(*v):
    return tuple(Vector(v).normalized())


# ------------------------------------------------------------------ poses
# todas las poses parten del reposo completo: un canal que falta en una clave toma el valor de la vecina (Clip.sample)
# y en el tramo siguiente saltaría al neutro del Solver
REST = {k: v for k, v in MR.NEUTRAL.items() if v is not None and k != "extra"}

# guardia de la fase 1: erguido y tranquilo, la mano derecha arriba con la palma hacia Kaito y la izquierda en la
# espalda (enseña con una sola mano); el peso atrás, sobre la pierna izquierda
GUARD = mod(
    REST,
    staff_on=0.0, hips=(0.0, 0.02, -0.05), hips_rot=(0.0, 0.0, 6.0), spine=(2.0, 0.0, 3.0), chest=(3.0, 0.0, 5.0),
    neck=(-2.0, 0.0, -6.0), head=(-3.0, 0.0, -5.0),
    foot_r=(-0.2, -0.16, AZ), foot_r_rot=(0.0, 0.0, 4.0), knee_r=(-0.25, -1.0, 0.0),
    foot_l=(0.22, 0.2, AZ), foot_l_rot=(0.0, 0.0, 28.0), knee_l=(0.4, -1.0, 0.0),
    hand_r=(-0.16, -0.42, 1.6), hand_r_dir=n(0.15, -0.25, 1.0), hand_r_up=n(0.25, 1.0, 0.2), elbow_r=(-0.6, 0.2, -0.8),
    hand_l=(0.06, 0.25, 1.33), hand_l_dir=n(-1.0, 0.15, -0.1), hand_l_up=(0.0, 1.0, 0.0), elbow_l=(0.9, 0.6, -0.2),
    **MR.hand_shape("r", "palm"), **MR.hand_shape("l", "relaxed"),
)

# caballo bajo con la palma derecha estirada y el puño izquierdo cargado en la cadera
HORSE_PALM = mod(
    REST,
    staff_on=0.0, hips=(0.0, 0.03, -0.34), hips_rot=(0.0, 0.0, 10.0), spine=(4.0, 0.0, 6.0), chest=(2.0, 0.0, 10.0),
    neck=(-4.0, 0.0, -10.0), head=(-2.0, 0.0, -8.0),
    foot_r=(-0.5, 0.0, AZ), foot_r_rot=(0.0, 0.0, -14.0), knee_r=(-0.7, -1.0, 0.0),
    foot_l=(0.5, 0.0, AZ), foot_l_rot=(0.0, 0.0, 14.0), knee_l=(0.7, -1.0, 0.0),
    hand_r=(-0.05, -0.9, 1.42), hand_r_dir=n(0.0, -0.15, 1.0), hand_r_up=n(0.0, 1.0, 0.15), elbow_r=(-0.4, 0.3, -1.0),
    hand_l=(0.25, 0.06, 1.02), hand_l_dir=(0.0, -1.0, 0.0), hand_l_up=(0.0, 0.0, -1.0), elbow_l=(0.6, 1.0, -0.2),
    clav_r=(0.0, 0.0, 6.0),
    **MR.hand_shape("r", "palm"), **MR.hand_shape("l", "fist"),
)

# patada de grulla: parado sobre la izquierda, la rodilla derecha arriba y el pie que pega adelante con la punta
# estirada; los brazos abiertos como alas, las manos en pico
CRANE_KICK = mod(
    REST,
    staff_on=0.0, hips=(0.0, 0.08, -0.03), hips_rot=(-14.0, 0.0, 4.0), spine=(-4.0, 0.0, 0.0), chest=(2.0, 0.0, 0.0),
    neck=(4.0, 0.0, 0.0), head=(6.0, 0.0, 0.0),
    foot_l=(0.13, 0.08, AZ), foot_l_rot=(0.0, 0.0, 22.0), knee_l=(0.25, -1.0, 0.0),
    foot_r=(-0.13, -0.78, 1.18), foot_r_rot=(-70.0, 0.0, 0.0), knee_r=(-0.1, -0.3, 1.0), toe_r=-20.0,
    hand_r=(-0.86, 0.12, 1.86), hand_r_dir=n(-0.2, 0.1, -1.0), hand_r_up=n(-0.6, 0.2, 0.6), elbow_r=(-0.4, 0.4, 0.8),
    hand_l=(0.86, 0.12, 1.86), hand_l_dir=n(0.2, 0.1, -1.0), hand_l_up=n(0.6, 0.2, 0.6), elbow_l=(0.4, 0.4, 0.8),
    clav_r=(0.0, 0.0, -8.0), clav_l=(0.0, 0.0, 8.0),
    **MR.hand_shape("r", "beak"), **MR.hand_shape("l", "beak"),
)

# bastón en guardia: cruzado delante del cuerpo, la punta de abajo adelante y a su izquierda; paso adelantado
STAFF_READY = mod(
    REST,
    staff_on=1.0, hips=(0.0, 0.04, -0.18), hips_rot=(0.0, 0.0, 14.0), spine=(4.0, 0.0, 4.0), chest=(2.0, 0.0, 6.0),
    neck=(-3.0, 0.0, -10.0), head=(-2.0, 0.0, -8.0),
    foot_r=(-0.24, -0.34, AZ), foot_r_rot=(0.0, 0.0, 8.0), knee_r=(-0.35, -1.0, 0.0),
    foot_l=(0.3, 0.38, AZ), foot_l_rot=(0.0, 0.0, 38.0), knee_l=(0.6, -1.0, 0.0),
    staff_pos=(-0.06, -0.5, 1.3), staff_dir=n(-0.62, 0.12, 0.78), staff_up=(0.0, -1.0, 0.0),
    grip_r=-0.28, grip_l=0.34, grip_r_up=(0.0, -1.0, 0.2), grip_l_up=(0.0, -1.0, 0.0), grip_r_thumb=1.0, grip_l_thumb=-1.0,
    elbow_r=(-0.7, 0.4, -0.6), elbow_l=(0.6, 0.6, -0.5),
    **MR.hand_shape("r", "grip"), **MR.hand_shape("l", "grip"),
)

# las manos adelante para mirar los dedos: garra y pico, después puño y dedos de espada
HANDS_A = mod(
    REST,
    staff_on=0.0, hips=(0.0, 0.0, -0.06), foot_r=(-0.2, 0.0, AZ), foot_l=(0.2, 0.0, AZ),
    hand_r=(-0.28, -0.55, 1.55), hand_r_dir=n(0.0, -0.3, 1.0), hand_r_up=n(0.0, 1.0, 0.3), elbow_r=(-0.8, 0.2, -0.6),
    hand_l=(0.28, -0.5, 1.45), hand_l_dir=n(0.1, -0.5, -1.0), hand_l_up=n(0.0, -0.8, 0.5), elbow_l=(0.8, 0.2, -0.6),
    **MR.hand_shape("r", "claw"), **MR.hand_shape("l", "beak"),
)
# además el saco tirado en el aire, adelante a su izquierda (cómo se ve la copia aplanada que vuela en el cambio de fase)
HANDS_B = mod(HANDS_A, hand_l_dir=n(0.0, -0.3, 1.0), hand_l_up=n(0.0, 1.0, 0.3),
              robe_free=1.0, robe_pos=(1.1, -0.7, 1.9), robe_rot=(-55.0, 15.0, 35.0), robe_fold=(25.0, 30.0, 12.0),
              **MR.hand_shape("r", "fist"), **MR.hand_shape("l", "sword"))


def idle_clip():
    """Guardia de la fase 1 respirando (2.4 s, loop): el pecho sube y la mano de adelante acompaña apenas."""
    f = 72
    a = mod(GUARD, breath=0.0)
    b = mod(GUARD, breath=1.0, hips=(0.0, 0.02, -0.06), hand_r=(-0.16, -0.43, 1.615), head=(-4.0, 0.0, -5.0))
    return Clip("Idle", f, [Key(0, a), Key(36, b, "sine"), Key(f, a, "sine")], loop=True,
                timing={"kind": "idle"}, notes="guardia de la fase 1 (la mano izquierda en la espalda); provisorio hasta la etapa 2")


def pose_test_clip():
    """Reposo y cinco poses sostenidas (lo bastante para que los resortes se asienten): la prueba de deformación."""
    seq = [("reposo", REST), ("guardia", GUARD), ("caballo y palma", HORSE_PALM), ("patada de grulla", CRANE_KICK),
           ("bastón", STAFF_READY), ("garra y pico", HANDS_A), ("puño y espada", HANDS_B), ("reposo", REST)]
    keys, marks = [Key(0, REST)], {}
    f = 0
    for i, (lab, p) in enumerate(seq[1:]):
        f += 16
        keys.append(Key(f, p, "inout"))
        if i < len(seq) - 2:
            marks[f + 14] = lab
            f += 20
            keys.append(Key(f, p, "hold"))
    clip = Clip("PoseTest", f, keys, loop=False, timing={"kind": "test", "holds": marks},
                notes="poses de prueba del esqueleto (no es un clip de pelea)")
    return clip, marks


CLIPS = [idle_clip(), pose_test_clip()[0]]
