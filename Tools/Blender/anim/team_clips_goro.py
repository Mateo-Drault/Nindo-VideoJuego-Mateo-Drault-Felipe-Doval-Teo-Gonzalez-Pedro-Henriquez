"""Clips de Gorō, el Martillo de Kodoyama (Models/Minijefe.fbx), en el marco de autoría de team_rig (metros del juego,
frente -Y, izquierda +X). 3.4 m, piernas de 0.98 m, brazos de 1.04 m y un martillo de 3.7 m (la cabeza a 1.38 m de la
mano de arriba): el martillo ES el aviso, y cada golpe lo lleva a un lugar distinto de la silueta.

Lo que pedía la auditoría (ANIM-01/02) y cómo quedó:
  * Combo1 (martillazo en diagonal): el martillo ARRIBA a la derecha y atrás, el cuerpo torcido; baja cruzando al frente
    izquierdo. Combo2 (revés horizontal): el martillo atrás a la IZQUIERDA a la altura de la cadera; barre de izquierda a
    derecha. Combo3 (el de arriba): el martillo parado atrás de la cabeza con el pecho arqueado; cae derecho al frente.
    Contacto = activeStart en los tres (antes pegaban con el martillo todavía arriba).
  * Heavy (golpe sísmico, imparable): se agacha con el martillo atrás, SALTA (la pausa del juego cae en la cima) y el
    martillo pega en el piso al aterrizar: la onda sale con el impacto, no al despegar.
  * Spin: carga torcido con el martillo estirado a la derecha (el juego gira el modelo a 900°/s durante la fase activa);
    sale mareado y termina en la pose de StunSpin (el agotamiento que sigue).
  * StunSpin (mareado, agotado y ejecución), Parried y ParriedPerfect (el martillo rebota para arriba), Hit y HitHeavy, ExhaustedHit, Spotted (rugido: también el
    cambio de fase), Death (cae de rodillas sin soltar el martillo y se desploma), Idle, caminar y correr (sin
    'moonwalk': los pies clavados a la velocidad del transform). La presentación ('Intro') es la toma del equipo
    (Firstinteraction) con los brazos re-resueltos: en la toma la muñeca del martillo llegaba a 96° en el primer plano.
"""
import math, os, sys
from mathutils import Vector
import nindo_anim as NA
import team_rig as T

GORO_TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bosses", "goro")
if GORO_TOOLS not in sys.path:
    sys.path.insert(0, GORO_TOOLS)

Key = NA.Key


def mesh_checks(ch, clip, first, check):
    """build_team_anims: el martillo contra el cuerpo (y contra la armadura en los clips de la fase 2), goro_checks."""
    import goro_checks as GC, goro_armor as GA
    return GC.weapon_body(ch, clip, first, check, armor=GA.rocks_for_checks())


# medidas del martillo (ch.weapon_info de Models/Minijefe.fbx, metros a lo largo del mango desde BaseM): Agarre1 (la
# izquierda) 0.513, Agarre2 (la derecha) 1.169, centro de la cabeza 2.553, la punta del mango -0.649
GRIP_L, GRIP_R, HEAD_C, BUTT = 0.513, 1.169, 2.553, -0.649


def club(head, haft, sr=0.0, sl=None):
    """El martillo pedido por su cabeza (lo que se lee del aviso y del golpe): el centro de la cabeza en 'head', el mango
    hacia 'haft' (de las manos a la cabeza) y la derecha corrida 'sr' m hacia la punta del mango. Devuelve grip / haft /
    slide_r (y slide_l). Con las manos más cerca de la punta del mango la cola que sobra detrás de la izquierda es más
    corta: con el agarre del equipo sobraban 1.16 m, que en los golpes acostados atravesaban el torso."""
    h = Vector(haft).normalized()
    g = Vector(head) - h * (HEAD_C - GRIP_R + sr)
    d = dict(grip=tuple(round(x, 4) for x in g), haft=tuple(round(x, 4) for x in h), slide_r=sr)
    if sl is not None:
        d["slide_l"] = sl
    return d


def club_points(pose):
    """(mano derecha, mano izquierda, cabeza, punta del mango) de una pose, en el marco de autoría (para planear)."""
    g, h = Vector(pose["grip"]), Vector(pose["haft"]).normalized()
    base = g - h * (GRIP_R - pose.get("slide_r", 0.0))
    return g, base + h * (GRIP_L + pose.get("slide_l", 0.0)), base + h * HEAD_C, base + h * BUTT


RUN_SPEED, WALK_SPEED = 3.8, 2.0          # EnemyArchetypes.Goro(): runSpeed, walkSpeed
LOCOMOTION = (("Idle", 0.0), ("Walk", WALK_SPEED / RUN_SPEED), ("Run", 1.0))
# cruces del Animator (clip, cuadro, otro clip, cuadro; -1 = el último): build_team_anims ancla ahí los brazos a la rama del
# otro clip y chequea que los antebrazos lleguen con el mismo giro local
BLENDS = ([("Walk", 0, "Idle", 0), ("Run", 0, "Walk", 0), ("Spin", -1, "StunSpin", 0), ("ExhaustedHit", 0, "StunSpin", 0),
           ("ExhaustedHit", -1, "StunSpin", 0)]
          + [(c, f, "Idle", 0) for c in ("Combo1", "Combo2", "Combo3", "Heavy", "Hit", "HitHeavy", "Spotted") for f in (0, -1)]
          + [(c, 0, "Idle", 0) for c in ("Spin", "Death")]
          # el parry cruza desde el contacto del golpe parado (PARRY_FROM): ancla en el de Combo1
          + [(c, 0, "Combo1", 24) for c in ("Parried", "ParriedPerfect")])

# ------------------------------------------------------------------ guardia
# el martillo con una mano, adelante a la derecha, la cabeza apoyada en el piso (pesa): desde ahí cada aviso lo levanta a
# un lugar distinto. El mango sube por afuera del brazo y la cola pasa 0.4 m por fuera de la cadera derecha (con el
# agarre del equipo rozaba el shimenawa y en la caminata entraba 11 cm en la cadera)
STANCE = dict(
    hips=(0.0, 0.02, -0.12), hips_rot=(6.0, 0.0, 10.0), spine=(8.0, 0.0, -6.0), head=(-8.0, 0.0, 0.0),
    knee_r=(-0.6, -1.0, 0.0), knee_l=(0.6, -1.0, 0.0),
    face=(0.98, 0.2, 0.0), grip_l=0.0,
    hand_l=(0.66, -0.15, 1.15), hand_l_dir=(0.1, -0.3, -0.95), hand_l_palm=(-1.0, 0.0, 0.0), fist_l=0.8,
    elbow_r=(-1.0, 0.3, -0.6), elbow_l=(1.0, 0.4, -0.4), breath=0.0, travel=0.0,
    **club((-0.55, -1.70, 0.535), (0.208, -0.859, -0.470), sr=0.10),
)
R0, L0 = (-0.48, -0.18, -10.0), (0.50, 0.24, 20.0)


def P(**kw):
    d = dict(STANCE)
    d.update(kw)
    return d


def flat_face(haft, hint):
    """Cara del martillo perpendicular al mango y horizontal (la cabeza de canto: lo menos que baja respecto de su centro),
    del lado de 'hint'. Para las poses en que la cabeza descansa en el piso o pasa cerca."""
    f = (-haft[1], haft[0], 0.0)
    m = math.hypot(f[0], f[1]) or 1.0
    sg = 1.0 if f[0] * hint[0] + f[1] * hint[1] >= 0.0 else -1.0
    return (sg * f[0] / m, sg * f[1] / m, 0.0)


def mix(a, b, u):
    """Pose a medio camino entre dos (canal por canal; un canal que falta en una vale lo de la otra)."""
    out = {}
    for k in set(a) | set(b):
        x, y = a.get(k, b.get(k)), b.get(k, a.get(k))
        out[k] = x + (y - x) * u if isinstance(x, (int, float)) else tuple(p + (q - p) * u for p, q in zip(x, y))
    return out


def tween(a, b, u, arc=0.0, hand=(0.0, 0.0, 0.0), head=(0.0, 0.0, 0.0)):
    """Pose intermedia entre dos con el martillo interpolado por lo que se ve: la mano derecha y la cabeza del martillo van
    en línea recta de una pose a la otra (la cabeza 'arc' m más alta en el medio) y el agarre sale de la distancia entre
    las dos ('hand' y 'head': corrimientos de la mano y la cabeza en el medio, para que la cola del mango o la cabeza
    pasen por afuera). Mezclar
    grip/haft/slide_r canal por canal mandaba la cabeza por debajo del piso en las vueltas a la guardia."""
    out = mix(a, b, u)
    ga, gb = Vector(a["grip"]), Vector(b["grip"])
    ha, hb = club_points(a)[2], club_points(b)[2]
    g = ga.lerp(gb, u) + Vector(hand) * math.sin(math.pi * u)
    h = ha.lerp(hb, u) + (Vector((0.0, 0.0, arc)) + Vector(head)) * math.sin(math.pi * u)
    out.update(aim(tuple(g), tuple(h)))
    out["slide_r"] = round((h - g).length - (HEAD_C - GRIP_R), 4)
    return out


def lift(pose, dz):
    """La pose con el martillo 'dz' m más alto (el agarre de la derecha): entre una clave con la cabeza en el piso y la
    guardia la interpolación hunde la cabeza unos centímetros; una clave intermedia apenas más alta la deja rozando."""
    g = pose["grip"]
    return dict(pose, grip=(g[0], g[1], g[2] + dz))


def P2(**kw):
    """Pose de golpe: las dos manos en el mango (en la guardia lo lleva con una sola)."""
    kw.setdefault("grip_l", 1.0)
    return P(**kw)


def FR(f, dy=0.0, dx=0.0, yaw=None, pitch=0.0, z=0.0, ease="inout", lift=None):
    return T.FootKey(f, R0[0] + dx, R0[1] - dy, R0[2] if yaw is None else yaw, pitch, z, 0.0, ease, lift)


def FL(f, dy=0.0, dx=0.0, yaw=None, pitch=0.0, z=0.0, ease="inout", lift=None):
    return T.FootKey(f, L0[0] + dx, L0[1] - dy, L0[2] if yaw is None else yaw, pitch, z, 0.0, ease, lift)


PLANTED = {"r": [FR(0)], "l": [FL(0)]}


# empujones del juego (Enemy): parry 0.4 m (perfecto 0.8; el parry no descuenta knockbackResist); los golpes de Kaito
# sí (0.9): 0.35-0.4 m de los livianos quedan en 0.04 m y 1.4-1.8 m de los pesados (HitHeavy) en 0.16 m
PARRY_BACK, PERFECT_BACK, HIT_BACK, HEAVY_BACK = 0.4, 0.8, 0.04, 0.16
knock_travel = T.knock_travel


def clips(ch):
    out = [idle()]
    out += locomotion(ch)
    out += [combo1(), combo2(), combo3(), heavy(), spin()]
    out += [stun_spin(), exhausted_hit(), parried(), parried_perfect(), hit(), hit_heavy(), spotted(), death()]
    out += [intro(ch)]
    return out


def intro(ch):
    """Presentación del jefe (Boss.introAnim = 'Intro', con la cámara de PlayBossIntroShot encima): la toma
    Firstinteraction del equipo, cuadros 0-77 como los usaba el controller, con el cuerpo, los pies y el martillo de la
    toma y los brazos y las muñecas otra vez por team_limbs (TakeClip)."""
    return T.TakeClip(ch, "Intro", "Firstinteraction", 0, 77, timing=dict(sheet=[0, 15, 30, 45, 60, 77], take=True),
                      notes="presentación: la toma del equipo con las muñecas arregladas")


# ================================================================== quieto y locomoción
def aim(grip, head):
    """grip y haft para que el mango vaya de la mano derecha 'grip' hacia la cabeza en 'head' (la distancia la fija el
    agarre: la cabeza queda sobre esa recta a HEAD_C - GRIP_R + slide_r de la mano)."""
    g = Vector(grip)
    return dict(grip=tuple(g), haft=tuple((Vector(head) - g).normalized()))


IDLE_HEAD = club_points(STANCE)[2]


def idle():
    """3.2 s: un oni de 3.4 m que respira hondo dos veces (el pecho sube, los hombros se levantan y bajan con el aire),
    el peso que pasa de un pie al otro, la cabeza que mira a un lado y al otro buscando a Kaito y el puño libre que se
    cierra en la segunda respiración. La cabeza del martillo descansa en el piso: la mano la mece sin levantarla."""
    n = 96
    keys = []
    H = IDLE_HEAD
    g0 = Vector(STANCE["grip"])
    for f in range(0, n + 1, 8):
        a = 2.0 * math.pi * f / n
        b = 4.0 * math.pi * f / n
        inhale = 0.5 - 0.5 * math.cos(b)
        g = g0 + Vector((0.03 * math.sin(a), 0.0, 0.035 * inhale))
        keys.append(Key(f, P(hips=(0.035 * math.sin(a), 0.02, -0.12 - 0.02 * (1.0 - inhale)),
                             hips_rot=(6.0, -2.5 * math.sin(a), 10.0 + 2.0 * math.sin(a)),
                             spine=(8.0 - 3.0 * inhale, 1.5 * math.sin(a), -6.0),
                             head=(-8.0 + 4.0 * inhale, 0.0, 14.0 * math.sin(a + 0.9)),
                             clav_r=(0.0, 0.0, -4.0 * inhale), clav_l=(0.0, 0.0, 4.0 * inhale), breath=inhale,
                             fist_l=0.75 + 0.25 * max(0.0, math.sin(a - 0.4)),
                             hand_l=(0.66 - 0.02 * math.sin(a), -0.15, 1.15 + 0.03 * inhale),
                             **aim(g, H + Vector((0.02 * math.sin(a), 0.0, 0.0)))), "sine"))
    return T.TeamClip("Idle", n, keys, loop=True, feet=PLANTED, notes="respira hondo dos veces, mira a los lados; el martillo apoyado")


def locomotion(ch):
    out = []
    n = 24
    g = T.gait2(ch, n, WALK_SPEED, 0.58, {"r": (-0.44, -0.04, -10.0), "l": (0.44, 0.04, 14.0)}, lift=0.14, toe_off=20.0, heel=-10.0)
    g0 = Vector(STANCE["grip"])

    def walk(f):
        a = 2.0 * math.pi * f / n
        c = dict(STANCE)
        c.update(g(f))
        c["hips"] = (-0.05 * math.sin(a), 0.0, -0.14 - 0.03 * math.cos(2 * a))
        c["hips_rot"] = (8.0, 4.0 * math.sin(a), 10.0 + 6.0 * math.sin(a))
        c["spine"] = (8.0, -2.5 * math.sin(a), -6.0 - 4.0 * math.sin(a))
        # camina con la cabeza del martillo 20 cm sobre el piso, meciéndose con el paso (la mano por fuera de la cadera)
        c.update(aim(g0 + Vector((-0.02, 0.05 * math.sin(a), 0.10 + 0.03 * math.cos(2 * a))),
                     IDLE_HEAD + Vector((-0.04, 0.10 * math.sin(a), 0.22 + 0.03 * math.cos(2 * a)))))
        c["hand_l"] = (0.66, -0.15 + 0.12 * math.sin(a), 1.15)
        return c
    out.append(NA.ProcClip("Walk", n, walk, loop=True, root_vel=(0, -WALK_SPEED, 0), notes="caminata pesada a 2 m/s"))

    # corre con el martillo adelante a la derecha, la cabeza a la altura de la rodilla (atrás, como una cola, el blend de
    # locomoción mezclaba cada hueso por separado y a media mezcla la cabeza del martillo cruzaba el piso)
    n = 20
    g2 = T.gait2(ch, n, RUN_SPEED, 0.38, {"r": (-0.40, -0.06, -6.0), "l": (0.40, -0.06, 6.0)}, lift=0.22, toe_off=30.0, heel=-12.0)

    def run(f):
        a = 2.0 * math.pi * f / n
        c = dict(STANCE)
        c.update(g2(f))
        c["hips"] = (-0.04 * math.sin(a), 0.0, -0.16 - 0.05 * math.cos(2 * a - 0.9))
        c["hips_rot"] = (14.0, 3.0 * math.sin(a), 8.0 * math.sin(a))
        c["spine"] = (10.0, -2.0 * math.sin(a), -6.0 * math.sin(a))
        c["head"] = (-18.0, 0.0, 3.0 * math.sin(a))
        c.update(aim((-0.86, -0.36 + 0.06 * math.sin(a), 1.32 + 0.03 * math.cos(2 * a)), (-0.64, -1.72 + 0.06 * math.sin(a), 0.92)))
        c["face"] = (0.98, 0.2, 0.0)
        c["grip_l"] = 0.0
        c["hand_l"] = (0.62, -0.10 + 0.30 * math.sin(a), 1.35 - 0.05 * math.cos(a))
        c["hand_l_dir"] = (0.1, -0.5, -0.85)
        c["fist_l"] = 0.9
        c["elbow_r"] = (-1.0, 0.2, -0.5)
        return c
    out.append(NA.ProcClip("Run", n, run, loop=True, root_vel=(0, -RUN_SPEED, 0), notes="corre a 3.8 m/s con el martillo adelante"))
    return out


# ================================================================== golpes
# agarre de los golpes: las dos manos juntas en la punta del mango, como se blande una maza (la derecha 1.4 m más abajo
# que en la guardia, la izquierda 1.0 m, a 26 cm una de otra): sobran 16 cm de mango detrás de la izquierda en vez de
# 1.16 m, que con el agarre del equipo atravesaban el torso en cada golpe acostado (el brazo de Gorō mide 1.04 m y el
# torso 1.16 de ancho: con 1 m de cola no hay pose de golpe que la deje afuera). La cabeza queda a 2.78 m de la derecha:
# los golpes llegan a 3.6-3.9 m del centro (lo que mide 'contact_head_m' en el sidecar)
SR, SL = 1.40, -1.00


def sweep_pose():
    """La vuelta a la guardia de los martillazos al frente: la cabeza arrastrada por el piso a la derecha y las manos
    (todavía en la punta del mango, la izquierda soltando) por afuera de la cadera derecha y abajo, así la cola del mango
    pasa debajo del brazo derecho y no por el torso ni el bíceps."""
    d = Vector((-0.36, -0.88, -0.30)).normalized()
    hand = Vector((-1.15, -0.85, 1.30))
    pose = P(hips=(0.0, -0.02, -0.22), hips_rot=(8.0, 0.0, -6.0), spine=(6.0, 0.0, -4.0), head=(-12.0, 0.0, 8.0), grip_l=0.3,
             grip_r=0.1, fist_r=0.7, face=flat_face(tuple(d), (1.0, 0.0, 0.0)),
             **club(tuple(hand + d * (HEAD_C - GRIP_R + SR)), tuple(d), sr=SR))
    return pose


def combo1():
    """Martillazo en diagonal (abre el combo). Levanta el martillo derecho adelante (la izquierda lo agarra abajo), lo
    monta sobre el hombro derecho y queda armado: la cabeza a 4 m de altura arriba a la DERECHA y atrás, el cuerpo torcido
    a la derecha y el peso atrás (desde la cámara del juego, un brazo de 3 m que sale por arriba a la derecha). Baja en
    diagonal con un paso largo y las manos tirando hacia la cadera izquierda; la cabeza se clava adelante a la izquierda,
    a 3.7 m (castigo). La cola del mango pasa siempre por delante del pecho. 1.4 s: la vuelta a la guardia dura 0.4 s
    (arrastra la cabeza por el piso y cambia el agarre sin que el antebrazo dé media vuelta)."""
    n, apex, contact = 42, 21, 24
    lunge, windup = 1.2, 0.85
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=windup)
    # la cabeza sale del piso hacia afuera (la cola baja por fuera del muslo derecho) y sube derecha adelante
    RAISE = P(hips=(0.02, 0.03, -0.13), hips_rot=(4.0, 0.0, 0.0), head=(-8.0, 0.0, 8.0), grip_l=0.3, **aim((-1.12, -0.60, 1.55), (-1.20, -2.05, 1.45)))
    LIFT = P2(hips=(0.03, 0.05, -0.14), hips_rot=(2.0, 0.0, -14.0), spine=(0.0, 0.0, -8.0), head=(-8.0, 0.0, 14.0), grip_l=0.8,
              elbow_r=(-1.0, -0.2, -0.4), elbow_l=(0.6, -0.6, -0.4),
              **club((-1.40, -1.70, 3.75), (-0.20, -0.36, 0.91), sr=0.70, sl=-0.50))
    TELL = P2(hips=(0.05, 0.12, -0.16), hips_rot=(0.0, 0.0, -34.0), spine=(-6.0, 0.0, -12.0), head=(-6.0, 0.0, 30.0),
              face=(0.6, -0.6, 0.3), elbow_r=(-1.0, 0.0, -0.3), elbow_l=(0.6, -0.8, -0.2),
              **club((-1.84, 1.07, 4.09), (-0.42, 0.55, 0.72), sr=SR, sl=SL))
    HOLD = dict(TELL, hips=(0.05, 0.13, -0.18), **club((-1.88, 1.12, 4.08), (-0.43, 0.57, 0.70), sr=SR, sl=SL))
    SMEAR = dict(HOLD, hips=(0.0, 0.0, -0.20), hips_rot=(10.0, 0.0, -8.0), spine=(4.0, 0.0, -4.0), head=(-12.0, 0.0, 10.0),
                 face=(0.3, -0.8, -0.5), **club((-0.95, -2.20, 3.70), (-0.28, -0.60, 0.75), sr=SR, sl=SL))
    # el golpe: la cara de abajo de la cabeza pega el piso (el centro a 0.82 m: la cabeza mide 1.6 m de cara a cara), las
    # manos estiradas a la altura del pecho y la espalda casi recta, con la cadera bien abajo y centrada (inclinado y con la
    # cadera adelante, el pecho bajaba sobre la cola del mango)
    CONTACT = P2(hips=(0.0, -0.02, -0.36), hips_rot=(6.0, 0.0, 14.0), spine=(4.0, 0.0, 6.0), head=(-14.0, 0.0, -8.0),
                 face=(0.0, -0.27, -0.96), elbow_r=(-1.0, 0.3, -0.5), elbow_l=(1.0, 0.3, -0.5),
                 **club((0.75, -3.66, 0.90), (0.17, -0.95, -0.25), sr=SR, sl=SL))
    FOLLOW = dict(CONTACT, hips=(0.0, -0.03, -0.40), hips_rot=(8.0, 0.0, 18.0), face=(0.05, -0.22, -0.97),
                  **club((0.86, -3.62, 0.92), (0.21, -0.94, -0.24), sr=SR, sl=SL))
    PUNISH = dict(FOLLOW, hips=(0.0, -0.02, -0.38), spine=(8.0, 0.0, 8.0), head=(-14.0, 0.0, -12.0),
                  **club((0.86, -3.62, 0.94), (0.21, -0.94, -0.24), sr=SR, sl=SL))
    # de vuelta a la guardia arrastra la cabeza por el piso hacia la derecha con las manos por fuera de la cadera: la cola
    # del mango da la vuelta por afuera del costado derecho (derecho desde el golpe, cruzaba el torso); la derecha sube
    # por el mango y la izquierda suelta
    SWEEP = sweep_pose()
    keys = [Key(0, P()), Key(3, RAISE, "in"), Key(6, LIFT, "out"), Key(12, TELL, "inout"), Key(apex, HOLD, "sine"),
            Key(22, SMEAR, "in"), Key(contact, CONTACT, "lin"), Key(26, FOLLOW, "out"), Key(30, dict(PUNISH, grip_r=1.0, fist_r=1.0), "out"),
            Key(33, dict(tween(PUNISH, SWEEP, 0.4, 0.30), grip_r=0.15, fist_r=0.7), "sine"),
            Key(37, dict(SWEEP, grip_r=0.1, fist_r=0.7), "sine"),
            Key(40, dict(tween(SWEEP, P(), 0.6, 0.12), grip_r=0.5, fist_r=0.85), "sine"), Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    feet = {"r": [FR(0), FR(apex), FR(27, lunge, pitch=-10.0), FR(29, lunge)],
            "l": [FL(0), FL(12), FL(apex, pitch=16.0), FL(32, lunge, ease="out")]}
    return T.TeamClip("Combo1", n, keys, travel=tr, feet=feet, notes="martillazo en diagonal; aviso: martillo arriba a la derecha",
                      timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, 28], hold=[12, apex], lunge=lunge,
                                  windup=windup, state="Combo1", reach=2.5,
                                  # f36: la izquierda suelta el mango justo debajo del bíceps derecho (8 cm del casco del
                                  # brazo, el puño que se abre); desde la cámara no se ve cruzar nada
                                  clip_ok=[[36, 36]]))


def combo2():
    """Revés horizontal (encadenado). La izquierda baja al mango y las dos manos corren hasta la punta mientras la cabeza
    se arrastra por el piso hacia adelante; la lleva por la izquierda hasta atrás, a la altura de la cadera, con el cuerpo
    torcido a la izquierda (desde arriba: la cabeza del martillo sale del contorno por el otro lado que en Combo1). Barre
    de izquierda a derecha a la altura del pecho de Kaito, con las manos adelante (la cola del mango barre por delante de la
    panza) y la cabeza cae al piso a la derecha. 1.4 s; la vuelta gira el mango sobre la mano derecha por afuera de la
    cadera."""
    n, apex, contact = 42, 18, 21
    lunge, windup = 1.2, 0.5
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=windup)
    GATHER = P2(hips=(0.0, 0.0, -0.20), hips_rot=(10.0, 0.0, 10.0), spine=(8.0, 0.0, 6.0), head=(-14.0, 0.0, -6.0), grip_l=0.9,
                face=flat_face((0.10, -0.97, -0.22), (1.0, 0.0, 0.0)), elbow_r=(-1.0, 0.2, -0.5), elbow_l=(1.0, 0.2, -0.5),
                **club((-0.10, -3.45, 0.56), (0.10, -0.97, -0.22), sr=SR, sl=SL))
    TELL = P2(hips=(-0.04, 0.10, -0.20), hips_rot=(4.0, 0.0, 36.0), spine=(4.0, 0.0, 14.0), head=(-8.0, 0.0, -32.0),
              face=(-0.62, 0.72, 0.0), elbow_r=(-0.4, -0.8, -0.4), elbow_l=(1.0, 0.4, -0.3),
              **club((2.30, 1.30, 1.55), (0.66, 0.72, 0.12), sr=SR, sl=SL))
    HOLD = dict(TELL, hips=(-0.04, 0.11, -0.21), **club((2.32, 1.34, 1.55), (0.66, 0.73, 0.11), sr=SR, sl=SL))
    SMEAR = dict(HOLD, hips_rot=(6.0, 0.0, 14.0), spine=(6.0, 0.0, 6.0), head=(-10.0, 0.0, -10.0), face=(-0.82, -0.55, 0.0),
                 **club((2.30, -2.10, 1.25), (0.74, -0.67, 0.03), sr=SR, sl=SL))
    CONTACT = P2(hips=(0.0, -0.10, -0.26), hips_rot=(12.0, 0.0, -14.0), spine=(8.0, 0.0, -12.0), head=(-12.0, 0.0, 10.0),
                 face=(-1.0, 0.0, 0.0), elbow_r=(-1.0, 0.0, -0.4), elbow_l=(0.8, 0.5, -0.4),
                 **club((0.15, -3.85, 1.10), (0.20, -0.98, -0.05), sr=SR, sl=SL))
    # (la cabeza es un cilindro: la cara del seguimiento va del mismo lado que la de la guardia, así la vuelta no la
    # hace girar media vuelta por debajo del mango)
    FOLLOW = dict(CONTACT, hips_rot=(10.0, 0.0, -30.0), spine=(10.0, 0.0, -20.0), face=(0.38, -0.92, 0.0),
                  **club((-2.85, -1.80, 1.05), (-0.92, -0.38, -0.05), sr=SR, sl=SL))
    # la cabeza cae al piso a la derecha, de canto (de frente a frente cruzaba vertical por el piso)
    PUNISH = dict(FOLLOW, hips=(0.0, -0.08, -0.24), hips_rot=(12.0, 0.0, -24.0),
                  face=flat_face((-0.92, -0.32, -0.22), (1.0, 0.0, 0.0)), **club((-2.95, -1.70, 0.56), (-0.92, -0.32, -0.22), sr=SR, sl=SL))
    # vuelta: el mango gira sobre la mano derecha (afuera de la cadera) hasta apuntar adelante, la cabeza arrastrándose
    # por el piso; después la derecha sube por el mango y la izquierda suelta
    TURN = P(hips=(0.0, -0.04, -0.20), hips_rot=(8.0, 0.0, -2.0), spine=(6.0, 0.0, -4.0), head=(-10.0, 0.0, 4.0), grip_l=0.3,
             grip_r=0.15, fist_r=0.7, face=flat_face((-0.30, -0.92, -0.26), (1.0, 0.0, 0.0)),
             **aim((-1.05, -0.70, 1.30), (-1.85, -3.10, 0.56)))
    TURN["slide_r"] = round((Vector((-1.85, -3.10, 0.56)) - Vector((-1.05, -0.70, 1.30))).length - (HEAD_C - GRIP_R), 3)
    keys = [Key(0, P(grip_r=1.0, fist_r=1.0)), Key(2, dict(lift(mix(P(), GATHER, 0.3), 0.10), grip_r=0.3, fist_r=0.8), "in"),
            Key(4, dict(lift(mix(P(), GATHER, 0.75), 0.10), grip_r=0.3, fist_r=0.8), "lin"),
            Key(6, dict(GATHER, grip_r=1.0, fist_r=1.0), "out"), Key(10, TELL, "inout"), Key(apex, HOLD, "sine"), Key(19, SMEAR, "in"),
            Key(contact, CONTACT, "lin"), Key(24, FOLLOW, "out"), Key(29, dict(PUNISH, grip_r=1.0, fist_r=1.0), "out"),
            Key(32, lift(mix(PUNISH, TURN, 0.5), 0.10), "sine"), Key(34, TURN, "sine"),
            Key(38, dict(lift(mix(TURN, P(), 0.6), 0.07), grip_r=0.5, fist_r=0.85), "sine"),
            Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    feet = {"r": [FR(0), FR(apex), FR(24, lunge, pitch=-10.0), FR(26, lunge)],
            "l": [FL(0), FL(10), FL(apex, pitch=14.0), FL(29, lunge, ease="out")]}
    return T.TeamClip("Combo2", n, keys, travel=tr, feet=feet, notes="revés horizontal; aviso: martillo atrás a la izquierda",
                      timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, 24], hold=[10, apex], lunge=lunge,
                                  windup=windup, state="Combo2", reach=2.7))


def combo3():
    """El de arriba (cierra el combo). Levanta el martillo derecho adelante y lo lleva por encima de la cabeza: las dos
    manos juntas arriba, delante del casco, el mango que pasa por encima del casco y la cabeza del martillo parada atrás
    a 5 m de altura, el pecho arqueado (desde arriba: la silueta más alta). Cae derecho al frente con todo el peso; la
    cabeza se clava a 3.9 m y queda agachado. 1.27 s; vuelve arrastrando la cabeza a la derecha, como Combo1."""
    n, apex, contact = 38, 16, 19
    lunge, windup = 1.0, 0.5
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=windup)
    RAISE = P(hips=(0.02, 0.03, -0.13), hips_rot=(4.0, 0.0, 0.0), head=(-8.0, 0.0, 6.0), grip_l=0.3,
              **aim((-1.12, -0.60, 1.55), (-1.15, -2.05, 1.50)))
    LIFT = P2(hips=(0.0, 0.06, -0.15), hips_rot=(0.0, 0.0, -6.0), spine=(-4.0, 0.0, -4.0), head=(-4.0, 0.0, 6.0), grip_l=0.8,
              elbow_r=(-1.0, -0.2, -0.4), elbow_l=(0.8, -0.4, -0.4),
              **club((-0.95, -1.80, 4.05), (-0.20, -0.30, 0.93), sr=0.90, sl=-0.70))
    TELL = P2(hips=(0.0, 0.14, -0.10), hips_rot=(-8.0, 0.0, 4.0), spine=(-12.0, 0.0, -2.0), head=(6.0, 0.0, 0.0),
              face=(0.0, 0.62, -0.78), elbow_r=(-1.0, -0.2, 0.3), elbow_l=(1.0, -0.2, 0.3),
              **club((0.11, 1.28, 5.03), (0.04, 0.62, 0.78), sr=SR, sl=SL))
    HOLD = dict(TELL, hips=(0.0, 0.15, -0.11), **club((0.11, 1.36, 4.98), (0.04, 0.65, 0.76), sr=SR, sl=SL))
    SMEAR = dict(HOLD, hips=(0.0, 0.0, -0.18), hips_rot=(8.0, 0.0, 4.0), spine=(4.0, 0.0, 0.0), head=(-8.0, 0.0, 0.0),
                 face=(0.0, -0.95, -0.30), **club((0.0, -1.66, 5.10), (0.0, -0.30, 0.95), sr=SR, sl=SL))
    CONTACT = P2(hips=(0.0, -0.05, -0.38), hips_rot=(14.0, 0.0, 4.0), spine=(10.0, 0.0, 0.0), head=(-20.0, 0.0, 0.0),
                 face=(0.0, -0.25, -0.97), elbow_r=(-1.0, 0.3, -0.4), elbow_l=(1.0, 0.3, -0.4),
                 **club((0.05, -3.90, 0.92), (0.02, -0.97, -0.25), sr=SR, sl=SL))
    FOLLOW = dict(CONTACT, hips=(0.0, -0.05, -0.42), **club((0.05, -3.88, 0.95), (0.02, -0.97, -0.24), sr=SR, sl=SL))
    SWEEP = sweep_pose()
    keys = [Key(0, P()), Key(3, RAISE, "in"), Key(5, LIFT, "out"), Key(8, TELL, "inout"), Key(apex, HOLD, "sine"),
            Key(17, SMEAR, "in"), Key(contact, CONTACT, "lin"), Key(21, FOLLOW, "out"), Key(25, dict(FOLLOW, grip_r=1.0, fist_r=1.0), "sine"),
            Key(28, dict(tween(FOLLOW, SWEEP, 0.4, 0.30), grip_r=0.15, fist_r=0.7), "sine"), Key(32, SWEEP, "sine"),
            Key(35, dict(tween(SWEEP, P(), 0.6, 0.12), grip_r=0.5, fist_r=0.85), "sine"), Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    feet = {"r": [FR(0), FR(apex), FR(22, lunge, pitch=-10.0), FR(24, lunge)],
            "l": [FL(0), FL(8), FL(apex, pitch=14.0), FL(26, lunge, ease="out")]}
    return T.TeamClip("Combo3", n, keys, travel=tr, feet=feet, notes="martillazo de arriba; aviso: martillo atrás de la cabeza",
                      timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, 22], hold=[8, apex], lunge=lunge,
                                  windup=windup, state="Combo3", reach=2.9))


def heavy():
    """Golpe sísmico (imparable, onda de 4.6-6 m). Levanta el martillo y se agacha hondo con las dos manos arriba delante
    del casco y el martillo parado derecho sobre la cabeza (aviso rojo; agachado, con el mango inclinado atrás como en
    Combo3, atravesaba el casco); salta: la cima del salto es el apex (la
    pausa del juego, si la hay, lo deja suspendido arriba con el martillo en lo más alto). Cae con el martillo por delante
    y el contacto es el aterrizaje: la cabeza del martillo a 3.6 m y los dos pies en el piso a la vez."""
    n, apex, contact = 60, 32, 40
    lunge, windup = 0.5, 1.1
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=windup)
    RAISE = P(hips=(0.02, 0.03, -0.13), hips_rot=(4.0, 0.0, 0.0), head=(-8.0, 0.0, 6.0), grip_l=0.3,
              **aim((-1.12, -0.60, 1.55), (-1.15, -2.05, 1.50)))
    LIFT = P2(hips=(0.0, 0.06, -0.18), hips_rot=(0.0, 0.0, -6.0), spine=(-4.0, 0.0, -4.0), head=(-4.0, 0.0, 6.0), grip_l=0.8,
              elbow_r=(-1.0, -0.2, -0.4), elbow_l=(0.8, -0.4, -0.4),
              **club((-0.95, -1.80, 4.05), (-0.20, -0.30, 0.93), sr=0.90, sl=-0.70))
    CROUCH = P2(hips=(0.0, 0.10, -0.40), hips_rot=(14.0, 0.0, 0.0), spine=(-6.0, 0.0, 0.0), head=(-10.0, 0.0, 0.0),
                knee_r=(-0.8, -0.8, 0.0), knee_l=(0.8, -0.8, 0.0), face=(0.0, 0.62, -0.78),
                elbow_r=(-1.0, -0.2, 0.3), elbow_l=(1.0, -0.2, 0.3), **club((-0.04, 0.52, 5.22), (0.03, 0.35, 0.94), sr=SR, sl=SL))
    DEEP = dict(CROUCH, hips=(0.0, 0.11, -0.46), **club((-0.04, 0.56, 5.16), (0.03, 0.37, 0.93), sr=SR, sl=SL))
    TAKEOFF = dict(CROUCH, hips=(0.0, 0.04, 0.14), hips_rot=(4.0, 0.0, 0.0), spine=(-10.0, 0.0, 0.0), head=(-6.0, 0.0, 0.0),
                   **club((0.10, 1.10, 5.70), (0.04, 0.52, 0.85), sr=SR, sl=SL))
    TOP = dict(TAKEOFF, hips=(0.0, 0.0, 0.50), knee_r=(-0.6, -1.0, 0.0), knee_l=(0.6, -1.0, 0.0), spine=(-14.0, 0.0, 0.0),
               **club((0.10, 0.85, 6.10), (0.04, 0.40, 0.92), sr=SR, sl=SL))
    FALL = dict(TOP, hips=(0.0, -0.06, 0.30), hips_rot=(14.0, 0.0, 0.0), spine=(6.0, 0.0, 0.0), head=(-14.0, 0.0, 0.0),
                face=(0.0, -0.95, -0.30), **club((0.05, -1.95, 5.20), (0.02, -0.40, 0.92), sr=SR, sl=SL))
    # el aterrizaje: la cadera abajo del todo, las manos estiradas a la altura de las rodillas y la cara de abajo de la
    # cabeza en el piso (centro a 0.92 m: con el mango inclinado la cabeza pega con el canto)
    LAND = P2(hips=(0.0, -0.06, -0.50), hips_rot=(20.0, 0.0, 0.0), spine=(10.0, 0.0, 0.0), head=(-22.0, 0.0, 0.0),
              knee_r=(-0.8, -0.8, 0.0), knee_l=(0.8, -0.8, 0.0), face=(0.0, -0.20, -0.98),
              elbow_r=(-1.0, 0.3, -0.4), elbow_l=(1.0, 0.3, -0.4), **club((0.05, -3.70, 0.92), (0.02, -0.98, -0.20), sr=SR, sl=SL))
    SWEEP = sweep_pose()
    keys = [Key(0, P()), Key(3, RAISE, "in"), Key(6, LIFT, "out"), Key(12, CROUCH, "inout"), Key(22, DEEP, "sine"),
            Key(26, TAKEOFF, "out"), Key(apex, TOP, "out"), Key(36, FALL, "in"), Key(contact, LAND, "expo_in"),
            Key(43, dict(LAND, hips=(0.0, -0.05, -0.46)), "out"), Key(48, dict(LAND, grip_r=1.0, fist_r=1.0), "sine"),
            Key(51, dict(tween(LAND, SWEEP, 0.4, 0.30), grip_r=0.15, fist_r=0.7), "sine"), Key(54, SWEEP, "sine"),
            Key(57, dict(tween(SWEEP, P(), 0.6, 0.12), grip_r=0.5, fist_r=0.85), "sine"), Key(n, P(grip_r=1.0, fist_r=1.0), "sine")]
    feet = {"r": [FR(0), FR(22), FR(26, pitch=24.0), FR(apex, 0.25, z=0.40, ease="out"), FR(contact, lunge, ease="in"), FR(n - 6, lunge)],
            "l": [FL(0), FL(22), FL(26, pitch=24.0), FL(apex, 0.25, z=0.40, ease="out"), FL(contact, lunge, ease="in"), FL(n - 6, lunge)]}
    return T.TeamClip("Heavy", n, keys, travel=tr, feet=feet, notes="golpe sísmico: salta y pega al aterrizar",
                      timing=dict(kind="unblockable", apex=apex, contact=contact, active=[contact, 42], hold=[12, 22], lunge=lunge,
                                  windup=windup, state="Heavy", reach=3.1))


def stun_pose(a=0.0):
    """Mareado: doblado sobre el martillo, que quedó tirado adelante a la derecha con la cabeza en el piso (de canto); la
    derecha lo sigue agarrando por la punta del mango, como en el torbellino (sin cambiar de agarre: pasar del agarre de
    la punta a uno de bastón daba media vuelta del antebrazo en un cuadro), la izquierda en la rodilla, el cuerpo en
    círculos y la cabeza colgando. Con el agarre del equipo la cola del mango atravesaba el pecho todo el loop."""
    d = Vector((-0.20, -0.94, -0.28)).normalized()
    head = Vector((-1.62 + 0.03 * math.sin(a), -3.72, 0.56))
    return P(hips=(0.04 * math.sin(a), 0.06 + 0.03 * math.cos(a), -0.24), hips_rot=(16.0 + 4.0 * math.cos(a), 6.0 * math.sin(a), 6.0),
             spine=(14.0 + 4.0 * math.sin(a), -5.0 * math.cos(a), -6.0), head=(18.0 + 8.0 * math.sin(a + 1.0), 12.0 * math.cos(a), 10.0 * math.sin(a)),
             face=flat_face(tuple(d), (1.0, 0.0, 0.0)), grip_l=0.0,
             hand_l=(0.62, -0.42, 1.05), hand_l_dir=(0.1, -0.4, -0.9), hand_l_palm=(-1.0, 0.0, 0.0), fist_l=0.3, elbow_l=(1.0, 0.3, 0.0),
             elbow_r=(-1.0, 0.4, -0.3), **club(tuple(head), tuple(d), sr=SR))


def spin():
    """Torbellino (imparable). Las dos manos corren a la punta del mango y carga torcido a la derecha con el martillo
    estirado atrás a la derecha (la cabeza a 3 m del cuerpo). En la fase activa el juego gira el modelo a 900°/s: el
    martillo va estirado horizontal hacia afuera por delante del pecho torcido, las manos juntas en la punta (con el
    agarre del equipo el mango sobraba 1.8 m hacia el otro lado y le atravesaba el torso a cada vuelta), y el cuerpo se
    inclina al otro lado como contrapeso. Al terminar suelta la izquierda, queda mareado y cae en la pose de StunSpin."""
    n, apex, contact, end = 66, 16, 19, 56
    GATHER = P2(hips=(0.03, 0.04, -0.18), hips_rot=(6.0, 0.0, -16.0), spine=(4.0, 0.0, -10.0), head=(-10.0, 0.0, 16.0), grip_l=0.8,
                face=flat_face((-0.45, -0.86, -0.24), (0.0, 1.0, 0.0)), **club((-2.00, -3.34, 0.65), (-0.45, -0.86, -0.24), sr=SR, sl=SL))
    TELL = P2(hips=(0.06, 0.10, -0.20), hips_rot=(4.0, 0.0, -40.0), spine=(0.0, 0.0, -16.0), head=(-8.0, 0.0, 40.0),
              face=(0.5, 0.85, 0.0), elbow_r=(-1.0, 0.0, -0.4), elbow_l=(0.4, -0.9, -0.3),
              **club((-2.55, 1.90, 1.70), (-0.66, 0.74, 0.08), sr=SR, sl=SL))
    HOLD = dict(TELL, hips=(0.06, 0.11, -0.22), **club((-2.58, 1.93, 1.70), (-0.66, 0.75, 0.08), sr=SR, sl=SL))
    SPINP = P2(hips=(0.04, 0.0, -0.20), hips_rot=(4.0, 10.0, -20.0), spine=(0.0, 8.0, -28.0), head=(-10.0, -6.0, 40.0),
               face=(0.69, -0.72, 0.0), elbow_r=(-1.0, 0.0, -0.3), elbow_l=(0.3, -0.9, -0.3),
               **club((-2.75, -2.70, 1.70), (-0.72, -0.69, 0.04), sr=SR, sl=SL))
    S0 = stun_pose()
    keys = [Key(0, P(grip_r=1.0, fist_r=1.0)), Key(1, tween(P(), GATHER, 0.12, 0.10), "in"),
            Key(3, dict(tween(P(), GATHER, 0.5, 0.30, hand=(-0.18, -0.08, 0.0)), grip_r=0.3, fist_r=0.8), "lin"),
            Key(6, dict(GATHER, grip_r=1.0, fist_r=1.0), "out"), Key(10, TELL, "out"), Key(apex, HOLD, "sine"), Key(contact, SPINP, "in")]
    f = contact + 4
    while f <= end:
        a = 2.0 * math.pi * (f - contact) / 12.0
        keys.append(Key(f, dict(SPINP, hips=(0.04, 0.0, -0.20 - 0.03 * math.cos(2 * a)),
                               **club((-2.75, -2.70, 1.70 + 0.06 * math.sin(a)), (-0.72, -0.69, 0.04 + 0.02 * math.sin(a)), sr=SR, sl=SL)), "sine"))
        f += 4
    # sale del giro: la cabeza del martillo baja al piso a la derecha y la izquierda suelta; la derecha sube por el mango
    # hasta el agarre del mareo
    # sale del giro: la cabeza del martillo baja al piso adelante a la derecha, la izquierda suelta y queda mareado con
    # el mismo agarre de la punta (StunSpin)
    DROP = dict(tween(SPINP, S0, 0.6, 0.25), grip_l=0.5, hips_rot=(18.0, -10.0, 4.0), head=(24.0, -14.0, 10.0))
    keys += [Key(59, DROP, "out"), Key(62, dict(tween(SPINP, S0, 0.9, 0.06), grip_l=0.0), "sine"), Key(n, S0, "sine")]
    # pisa en el lugar mientras gira (el modelo entero rota: los pies no pueden quedar clavados, 'slide_ok')
    fr_, fl_ = [FR(0), FR(10, dx=0.06, yaw=-30.0), FR(contact, dx=0.06, yaw=-30.0)], [FL(0), FL(10, -0.10), FL(contact, -0.10)]
    f, up = contact + 3, True
    while f < end:
        fr_.append(FR(f, dx=0.06, yaw=-30.0, z=0.10 if up else 0.0, lift=0.0))
        fl_.append(FL(f, -0.10, z=0.0 if up else 0.10, lift=0.0))
        f += 3
        up = not up
    fr_ += [FR(end, dx=0.06, yaw=-30.0), FR(62, -0.10, dx=0.10, yaw=-20.0)]
    fl_ += [FL(end, -0.10), FL(60, 0.05, dx=-0.08)]
    return T.TeamClip("Spin", n, keys, feet={"r": fr_, "l": fl_}, tremble=0.0, notes="torbellino: carga torcido, gira, sale mareado",
                      timing=dict(kind="unblockable", apex=apex, contact=contact, active=[contact, end], hold=[10, apex], lunge=0.0,
                                  windup=0.95, state="Spin", slide_ok=40.0, reach=3.0))


STUN_FEET = {"r": [FR(0, -0.10, dx=0.10, yaw=-20.0)], "l": [FL(0, 0.05, dx=-0.08)]}


def stun_spin():
    """Mareado/agotado (loop de 2 s: el agotamiento después del torbellino o de quebrarle la postura, y la pose de la
    ejecución): apoyado en el martillo, el cuerpo da vueltas y la cabeza le cuelga."""
    n = 60
    keys = [Key(f, stun_pose(2.0 * math.pi * f / n), "sine") for f in range(0, n + 1, 10)]
    return T.TeamClip("StunSpin", n, keys, loop=True, feet=STUN_FEET, notes="mareado: apoyado en el martillo, el cuerpo en círculos")


# el golpe parado: Enemy.OnParried cruza en 0.03 s desde el golpe en curso (el contacto de Combo1/2/3, con el martillo
# adelante en la punta del mango) al cuadro 0 del parry. Antes ese cuadro era la guardia: en 0.03 s el martillo saltaba
# de adelante a la guardia. Ahora arranca en un contacto promedio de los tres
PARRY_FROM = P2(hips=(0.0, -0.04, -0.32), hips_rot=(10.0, 0.0, 6.0), spine=(6.0, 0.0, 2.0), head=(-14.0, 0.0, -4.0),
                face=(0.0, -0.20, -0.98), elbow_r=(-1.0, 0.3, -0.4), elbow_l=(1.0, 0.3, -0.4),
                **club((0.30, -3.75, 1.00), (0.08, -0.98, -0.19), sr=SR, sl=SL))
PARRY_RECOIL = 0.5          # EnemyArchetypes.Goro(): parriedRecoil


def stumble_pose(back=0.0):
    """El martillo que se le cae adelante después del rebote: la izquierda ya soltó, la derecha (corrida a la punta, por
    afuera de la cadera) lo sostiene todavía parado e inclinado adelante a la derecha. Desde acá la caída a la guardia
    hace pasar la cola del mango por afuera del muslo derecho (desde el martillo parado delante de la cara pasaba por
    el muslo)."""
    hand, head = Vector((-0.95, -0.60, 1.60)), Vector((-1.30, -1.40, 4.00))
    p = P(hips=(0.0, 0.08 + back, -0.18), hips_rot=(4.0, 0.0, -4.0), spine=(0.0, 0.0, -4.0), head=(-4.0, 0.0, 4.0), grip_l=0.0,
          face=(0.9, 0.3, 0.3), elbow_r=(-1.0, 0.2, -0.3), **aim(tuple(hand), tuple(head)))
    p["slide_r"] = round((head - hand).length - (HEAD_C - GRIP_R), 3)
    return p


def parried_clip(name, n, settle, recoil, back, knock, hold, stumble, feet, notes):
    """Parry recibido: Enemy.OnParried corta el clip a los parriedRecoil s (Goro(): 0.5; x1.5 el perfecto) y arranca el
    paso siguiente con un cruce de 0.08 s: en el cuadro del corte tiene que estar en la guardia de los golpes ('chain').
    Con 0.32 s el martillo tenía que ir del golpe a arriba y de vuelta a la guardia en 10 cuadros y daba la vuelta por
    encima en uno o dos: con 0.5 s rebota, se le resbala en la mano y cae por su peso. La vuelta a la guardia va por
    tween (la mano y la cabeza en línea recta) con la derecha floja para cambiar de agarre."""
    up = dict(knock, **club(tuple(club_points(knock)[2] + Vector((0.0, 0.08, 0.05))), knock["haft"],
                            sr=knock["slide_r"], sl=knock.get("slide_l")))
    keys = [Key(0, PARRY_FROM), Key(2, knock, "snap"), Key(hold, up, "out"), Key(hold + 4, dict(stumble, grip_r=1.0), "inout"),
            Key(settle - 3, dict(tween(stumble, P(), 0.55, 0.15), grip_r=0.25, fist_r=0.75, grip_l=0.0), "sine"),
            Key(settle, P(grip_r=1.0, fist_r=1.0), "sine"), Key(n, P(), "sine")]
    return T.TeamClip(name, n, keys, travel=knock_travel(n, back), feet=feet, notes=notes,
                      timing=dict(sheet=[0, 2, hold, hold + 4, settle], chain=[(round(recoil * T.FPS, 1), "Combo1", 0, 0.12)]))


def parried():
    """El martillo rebota (parry común: 0.5 s, 0.4 m atrás): sale despedido para arriba, parado delante de la cara, y el
    cuerpo se echa atrás con un paso pesado; cae adelante por su peso con la izquierda que suelta, y en el corte (f15)
    está en la guardia."""
    b = PARRY_BACK
    KNOCK = P2(hips=(0.0, 0.14, -0.16), hips_rot=(-12.0, 0.0, 6.0), spine=(-12.0, 0.0, 4.0), head=(12.0, 0.0, 6.0),
               face=(0.0, 0.97, -0.1), elbow_r=(-1.0, 0.0, -0.2), elbow_l=(1.0, 0.0, -0.2),
               **club((-0.18, -1.15, 4.62), (-0.03, -0.14, 0.99), sr=SR, sl=SL))
    STUMBLE = stumble_pose()
    feet = {"l": [FL(0), FL(5, -b, ease="out", lift=0.08)],
            "r": [FR(0), FR(1), FR(8, -b, pitch=-8.0, ease="out", lift=0.08), FR(9, -b)]}
    n = int(round(PARRY_RECOIL * T.FPS)) + 1
    return parried_clip("Parried", n, n - 1, PARRY_RECOIL, b, KNOCK, 4, STUMBLE, feet,
                        "parry recibido: el martillo rebota arriba, se le resbala y cae adelante; en guardia al corte")


def parried_perfect():
    """Parry perfecto (0.75 s, 0.8 m: Enemy lo elige si el controller lo tiene): el martillo se va para atrás por encima
    de la cabeza y lo arrastra; dos pasos pesados atrás con los brazos estirados arriba y en el corte (f22.5) vuelve a
    la guardia."""
    b = PERFECT_BACK
    KNOCK = P2(hips=(0.0, 0.16, -0.12), hips_rot=(-16.0, 0.0, 6.0), spine=(-16.0, 0.0, 4.0), head=(16.0, 0.0, 6.0),
               face=(0.0, 0.81, -0.55), elbow_r=(-1.0, 0.0, 0.2), elbow_l=(1.0, 0.0, 0.2),
               **club((-0.05, 1.20, 4.95), (0.03, 0.60, 0.80), sr=SR, sl=SL))
    STUMBLE = stumble_pose(back=0.04)
    feet = {"l": [FL(0), FL(6, -b + 0.15, ease="out", lift=0.10), FL(8, -b + 0.15), FL(14, -b, lift=0.05)],
            "r": [FR(0), FR(1), FR(10, -b, pitch=-8.0, ease="out", lift=0.10), FR(12, -b)]}
    n = int(round(PARRY_RECOIL * 1.5 * T.FPS)) + 1
    return parried_clip("ParriedPerfect", n, n - 1, PARRY_RECOIL * 1.5, b, KNOCK, 7, STUMBLE, feet,
                        "parry perfecto: el martillo se va atrás por encima de la cabeza, dos pasos atrás; en guardia al corte")


def hit():
    """Golpe recibido cuando no tiene la armadura del golpe (0.5 s): un sacudón del pecho y la cabeza, sin soltar el
    martillo; los pies quedan clavados en el mundo con los 4 cm del empujón (aguanta)."""
    n = 15
    PEAK = P(hips=(0.0, 0.06, -0.14), hips_rot=(-4.0, 0.0, 14.0), spine=(-10.0, 0.0, 0.0), head=(14.0, 0.0, 8.0),
             grip=(-0.52, -0.38, 1.40))
    keys = [Key(0, P()), Key(2, PEAK, "snap"), Key(7, dict(P(), hips=(0.0, 0.0, -0.15)), "inout"), Key(n, P(), "sine")]
    b = HIT_BACK
    feet = {"r": [FR(0), FR(3), FR(9, -b, ease="out", lift=0.05)], "l": [FL(0), FL(5), FL(11, -b, ease="out", lift=0.05)]}
    return T.TeamClip("Hit", n, keys, travel=knock_travel(n, b), feet=feet, notes="sacudón; se acomoda los 4 cm del empujón")


def hit_heavy():
    """Golpe pesado recibido (corte final y habilidades de Kaito: 0.16 m después de su resistencia; Enemy lo elige
    cuando el empujón pasa de 1 m): el sacudón más grande y un paso pesado atrás del pie derecho."""
    n = 15
    b = HEAVY_BACK
    PEAK = P(hips=(0.0, 0.10, -0.12), hips_rot=(-8.0, 0.0, 18.0), spine=(-16.0, 0.0, 2.0), head=(20.0, 0.0, 10.0),
             grip=(-0.56, -0.30, 1.52), hand_l=(0.76, -0.05, 1.30))
    keys = [Key(0, P()), Key(2, PEAK, "snap"), Key(8, dict(P(), hips=(0.0, 0.02, -0.17)), "inout"), Key(n, P(), "sine")]
    feet = {"r": [FR(0), FR(2), FR(8, -b, ease="out", lift=0.06)], "l": [FL(0), FL(6), FL(12, -b, ease="out", lift=0.05)]}
    return T.TeamClip("HitHeavy", n, keys, travel=knock_travel(n, b), feet=feet, notes="golpe pesado: sacudón y un paso atrás")


def exhausted_hit():
    """Golpe recibido estando mareado (Enemy lo usa si existe y al terminar vuelve al loop de StunSpin): se tambalea con
    la cabeza que se va para atrás sin despegar el martillo del piso; empieza y termina en el cuadro 0 de StunSpin (con
    Hit se paraba en plena ventana de daño)."""
    n = 12
    S = stun_pose()
    PEAK = dict(S, hips=(0.0, 0.12, -0.20), hips_rot=(4.0, -6.0, 18.0), spine=(2.0, 6.0, -2.0), head=(34.0, -10.0, 14.0))
    keys = [Key(0, S), Key(2, PEAK, "snap"), Key(6, dict(S, hips=(0.03, 0.04, -0.24), head=(10.0, 8.0, 4.0)), "inout"), Key(n, S, "sine")]
    b = HIT_BACK
    feet = {k: [v[0], T.FootKey(4, v[0].x, v[0].y, v[0].yaw), T.FootKey(10, v[0].x, v[0].y + b, v[0].yaw, 0.0, 0.0, 0.0, "out", 0.05)]
            for k, v in STUN_FEET.items()}
    return T.TeamClip("ExhaustedHit", n, keys, travel=knock_travel(n, b), feet=feet,
                      notes="mareado: se tambalea con el golpe; vuelve al cuadro 0 de StunSpin",
                      timing=dict(chain=[(n, "StunSpin", 0, 0.02)]))


def spotted():
    """Rugido (1.4 s): la alerta y el cambio de fase (Boss.phaseAnim). Junta aire agachado y ruge con el pecho afuera,
    los brazos abiertos y el martillo levantado con una mano (desde arriba: la silueta más ancha)."""
    n = 42
    # el martillo se levanta parado a la derecha, con la mano por afuera del hombro: la cola baja por fuera del muslo
    # derecho (levantado sobre la cabeza con el agarre de la guardia, la cola le atravesaba la pierna)
    IN = P(hips=(0.0, 0.06, -0.24), hips_rot=(16.0, 0.0, 6.0), spine=(14.0, 0.0, 0.0), head=(-20.0, 0.0, 0.0),
           **aim((-1.05, -0.50, 1.35), (-1.30, -1.85, 0.95)))
    ROAR = P(hips=(0.0, 0.04, -0.10), hips_rot=(-6.0, 0.0, 0.0), spine=(-16.0, 0.0, 0.0), head=(18.0, 0.0, 0.0),
             face=(0.0, -1.0, 0.1), grip_l=0.0, elbow_r=(-1.0, 0.0, -0.2),
             hand_l=(1.10, -0.20, 2.10), hand_l_dir=(0.6, -0.1, 0.8), hand_l_palm=(0.0, -1.0, 0.0), fist_l=1.0, elbow_l=(1.0, 0.0, -0.4),
             **aim((-1.25, -0.15, 2.60), (-1.47, -0.18, 4.07)))
    keys = [Key(0, P()), Key(4, tween(P(), IN, 0.5, 0.10, hand=(-0.10, 0.0, 0.0)), "in"), Key(8, IN, "out"),
            Key(11, tween(IN, ROAR, 0.6, 0.0, hand=(-0.15, 0.0, 0.0)), "in"), Key(13, ROAR, "out")]
    for i, f in enumerate(range(16, 33, 2)):
        s = 1 if i % 2 else -1
        keys.append(Key(f, dict(ROAR, spine=(-16.0, 1.2 * s, 0.0), head=(18.0, 0.0, 2.0 * s)), "sine"))
    keys += [Key(36, dict(ROAR, hips=(0.0, 0.03, -0.12)), "sine"), Key(39, tween(ROAR, P(), 0.6, 0.10, hand=(-0.15, 0.0, 0.0)), "sine"),
             Key(n, P(), "sine")]
    feet = {"r": [FR(0), FR(10), FR(14, dx=-0.08, lift=0.06), FR(34, dx=-0.08), FR(n, lift=0.06)],
            "l": [FL(0), FL(10), FL(14, dx=0.08, lift=0.06), FL(32, dx=0.08), FL(n - 2, lift=0.06)]}
    return T.TeamClip("Spotted", n, keys, feet=feet, tremble=0.0, notes="rugido: pecho afuera, brazos abiertos")


def planted(head_world, haft, sr, travel):
    """club() con la cabeza clavada en el MUNDO: los clips autoran las manos respecto del transform del juego, que en la
    muerte se corre 0.8 m atrás (DeathRoutine); sin compensar, la cabeza apoyada patinaba por el piso con él."""
    h = Vector(head_world) + Vector((0.0, travel, 0.0))
    return club(tuple(h), haft, sr=sr)


def death():
    """Muerte (2 s, deathClipFalls): el golpe lo echa atrás y se ataja con el martillo, que queda clavado de cabeza en el
    piso a su derecha, con el mango parado; la derecha baja por el mango (la cola sube 2 m por encima de su mano, por
    afuera del hombro: de bastón, con el agarre del equipo, la cola le atravesaba la cadera). Se le doblan las rodillas,
    queda arrodillado agarrado del mango con la cabeza gacha, la mano se le resbala y se desploma hacia adelante; el
    martillo se vence solo hacia la derecha y cae acostado al piso."""
    n = 60
    slide = [-0.8 * math.sin(min(1.0, (f / T.FPS) * 1.8) * math.pi * 0.5) for f in range(n + 1)]
    # la cabeza del martillo en el mundo (respecto del transform en f0), con las caras mirando adelante y atrás: la cabeza
    # mide 1.6 m de cara a cara y 1 m de ancho; de costado le entraba en el muslo derecho
    HW = Vector((-1.32, -0.02, 0.52))
    down = Vector((0.04, 0.02, -1.0))          # de la mano a la cabeza: el mango parado
    face = (0.0, 1.0, 0.0)
    REC = P(hips=(0.0, 0.12, -0.12), hips_rot=(-6.0, 0.0, 8.0), spine=(-8.0, 0.0, 0.0), head=(14.0, 0.0, 6.0), face=face,
            grip_r=0.3, fist_r=0.75, elbow_r=(-1.0, 0.4, -0.3), **planted(HW + Vector((0.0, -0.15, 0.0)), tuple(down), -0.20, slide[4]))
    STEADY = P(hips=(0.0, 0.10, -0.20), hips_rot=(6.0, 0.0, 8.0), spine=(6.0, 0.0, 0.0), head=(16.0, 0.0, 4.0), face=face,
               elbow_r=(-1.0, 0.4, -0.3), **planted(HW, tuple(down), -0.28, slide[12]))
    KNEEL = P(hips=(0.0, 0.16, -0.58), hips_rot=(-2.0, 0.0, 8.0), spine=(10.0, 0.0, 0.0), head=(24.0, 0.0, 0.0),
              knee_r=(-0.3, -1.0, -0.3), knee_l=(0.3, -1.0, -0.3), face=face, grip_l=0.0, elbow_r=(-1.0, 0.4, -0.2),
              hand_l=(0.50, -0.30, 0.95), hand_l_dir=(0.0, -0.3, -0.95), hand_l_palm=(-1.0, 0.0, 0.0), fist_l=0.2,
              **planted(HW, tuple(down), -0.62, slide[24]))
    BOW = dict(KNEEL, spine=(26.0, 0.0, 0.0), head=(30.0, 0.0, 0.0), hips=(0.0, 0.16, -0.55),
               **planted(HW, tuple(down), -0.70, slide[44]))
    # se le resbala la mano ('drop_r': la derecha deja el mango y ataja la caída como la izquierda); el martillo se vence
    # a la derecha girando sobre la cabeza apoyada y queda acostado, la cola en el piso 3 m afuera
    TIP = Vector((0.62, 0.05, -0.78)).normalized()
    LAID = Vector((0.99, 0.05, 0.11)).normalized()      # la cola apoyada en el piso por el pomo (12 cm de radio)
    DOWN = dict(BOW, hips=(0.0, -0.10, -0.48), hips_rot=(62.0, 0.0, 10.0), spine=(18.0, 0.0, 0.0), head=(-20.0, 0.0, 20.0),
                hand_l=(0.55, -0.80, 0.40), hand_l_dir=(0.0, -0.8, -0.3), grip_r=0.15, fist_r=0.5,
                drop_r=1.0, hand_r=(-0.58, -0.82, 0.40), hand_r_dir=(0.0, -0.8, -0.3), elbow_r=(-1.0, 0.3, 0.2),
                face=flat_face(tuple(LAID), (0.0, 1.0, 0.0)), **planted(HW + Vector((0.0, 0.0, 0.03)), tuple(LAID), -0.70, slide[54]))
    TOPPLE = dict(DOWN, hips=(0.0, 0.04, -0.47), hips_rot=(38.0, 0.0, 9.0), spine=(22.0, 0.0, 0.0), drop_r=0.9, grip_r=0.4,
                  hand_r=(-0.64, -0.78, 0.80), face=face, **planted(HW, tuple(TIP), -0.70, slide[51]))
    keys = [Key(0, P(grip_r=1.0, fist_r=1.0)), Key(1, tween(P(), REC, 0.3, 0.35, hand=(-0.15, 0.0, 0.0), head=(-0.45, 0.0, 0.0)), "snap"),
            Key(2, tween(P(), REC, 0.6, 0.40, hand=(-0.15, 0.0, 0.0), head=(-0.45, 0.0, 0.0)), "lin"), Key(4, REC, "out"),
            Key(12, dict(STEADY, grip_r=1.0, fist_r=1.0), "out"), Key(24, KNEEL, "in2"),
            Key(27, dict(KNEEL, hips=(0.0, 0.16, -0.55)), "out"), Key(32, KNEEL, "sine"), Key(44, BOW, "sine"),
            Key(48, dict(BOW, grip_r=0.6, fist_r=0.8, drop_r=0.0), "in"), Key(51, TOPPLE, "lin"), Key(54, DOWN, "in"),
            Key(57, dict(DOWN, hips=(0.0, -0.10, -0.45)), "out"), Key(n, DOWN, "sine")]
    # el empujón lo lleva 0.8 m atrás: los pies retroceden con él y quedan de punta para las rodillas apoyadas
    feet = {"r": [FR(0), FR(3), FR(11, -0.70, ease="out"), FR(16, -0.70), FR(24, -1.60, yaw=0.0, pitch=60.0)],
            "l": [FL(0), FL(5, pitch=10.0), FL(14, -0.75, ease="out"), FL(18, -0.75), FL(25, -1.30, yaw=0.0, pitch=60.0)]}
    return T.TeamClip("Death", n, keys, travel=slide, feet=feet, notes="muerte: se ataja con el martillo clavado, de rodillas, se desploma",
                      timing=dict(sheet=[4, 12, 24, 32, 44, 51, 54, 60], slide_ok=6.0))
