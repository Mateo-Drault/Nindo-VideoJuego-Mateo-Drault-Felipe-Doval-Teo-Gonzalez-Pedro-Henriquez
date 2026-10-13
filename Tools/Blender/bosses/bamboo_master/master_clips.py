"""Clips de pelea de Chikuō: claves, tiempos y eventos. Fuente única de los tiempos de BambooMaster.fbx.

Gramática de cada golpe (la misma de Kokuyō, para que el parry se lea igual en todo el juego):
  anticipación (contra-movimiento) -> pose de AVISO que rompe la silueta vista desde arriba -> espera que se mueve
  (nunca congelada) -> golpe de 2-3 cuadros por un arco limpio -> se pasa (follow-through) -> recuperación hasta la
  guardia de su fase. La cadera arranca el golpe (fa jin: el pie de atrás empuja, la cadera gira, el hombro y la mano
  llegan después) y la mano o el pie que pega llega en el cuadro en que el pie de adelante se clava.

Fases y variantes. Las tres fases comparten piernas y cadera; cambian los brazos:
  * fase 1 (con saco): la izquierda en la espalda (enseña con una mano) -> canal back_l del Solver;
  * fase 2 (sin saco, ojos jade): las dos manos en guardia;
  * fase 3: el bastón, pegado al pecho en las reacciones y la locomoción (staff_follow).
Un clip base (fase 1) puede tener variantes 'X_P2' y 'X_P3' con EXACTAMENTE los mismos cuadros, tiempos, eventos y
avance: el jefe las cambia con un AnimatorOverrideController (Idle, Walk, Hit... no cambian de nombre de estado, así
Enemy.cs sigue tocando 'Hit', 'Parried', 'Exhausted' y el blend tree 'Locomotion') o las toca por nombre.

'timing' de cada clip (cuadros a 30 fps, se copia al .fbx.json; ver build_bamboo_master.py):
  tell [inicio, apex]   la anticipación hasta la pose de aviso   apex  cuadro de la pose de aviso
  hold [a, b]           la espera que se mueve                   contact  primer cuadro que pega (activeStart)
  active [a, b]         ventana que pega                         recover [a, b]  castigo / recuperación
  lunge [a, b, m]       avance que el JUEGO aplica al transform (travel_m en el sidecar)
  air [a, b]            cuadros con los dos pies en el aire: el juego puede escalar el avance de ese tramo (salto a
                        la marca) sin que patinen los pies
  kind                  parry (dorado) | dodge (rojo, imparable) | none
  glow                  slot de CharacterGlint que se enciende en el aviso (Master_GlintHandR...)
  strike                hueso y punto (espacio del hueso, Blender) que pega: alcance y velocidad medidos
  ring_m / marker_m     radio del anillo rojo (barrida, onda de qi) / distancia de la marca del salto
  release_rate          AttackDef.releaseRate con el que se midieron avance y punta (StepTimeline; 1.6 si falta)
  knock_m / resume      retroceso que el juego aplica en la reacción (Enemy.knock) / cuadro desde el que ya puede
                        seguir el combo
  chain_from / chain_to la pose con la que empieza / termina (READY = la guardia de su fase)

Posiciones en metros, frente = -Y, su derecha = -X; cadera y manos relativas al transform del juego; pies, saco tirado
y bastón clavado en el MUNDO del clip (un pie apoyado tiene la misma coordenada en todas las claves). Giros en grados
(x + = adelante, y + = hacia su izquierda, z + = gira a su izquierda).
"""
import copy, math
from mathutils import Vector, Matrix
import nindo_anim as NA
from nindo_anim import Key, Clip
import master_rig as MR

AZ = MR.ANKLE_Z
FPS = NA.FPS
# canales de dirección propios de Chikuō: se interpolan por el arco más corto (los de nindo_anim son los de Kokuyō)
DIRS = {"staff_dir", "staff_up", "grip_r_up", "grip_l_up", "staff_cdir", "staff_cup", "hand_r_cdir", "hand_r_cup",
        "hand_l_cdir", "hand_l_cup", "hand_r_celbow", "hand_l_celbow"}
# lo que se autora en el MUNDO del clip (se corre con el avance)
WORLD_POS = ("foot_r", "foot_l", "robe_pos")
GOLD, RED = "parry", "dodge"
PALM_R = ("Hand_R", tuple(MR.PALM_LOCAL))
PALM_L = ("Hand_L", tuple(MR.PALM_LOCAL))


class MClip(Clip):
    """Clip de Chikuō: los canales de DIRS van por slerp (un bastón que gira no pasa por el largo cero) y lleva la fase
    y de qué clip base es variante."""

    def __init__(self, name, frames, keys, phase=1, base=None, overlay=None, overlays=(), overlay_start=0, **kw):
        super().__init__(name, frames, keys, **kw)
        rigid_hands(self.keys)
        self.phase, self.base = phase, base
        # pista aparte para los pies (sin el atraso de 'lag'): los pasos de una reacción no caen en las mismas claves que
        # el cuerpo
        # (MClip: las direcciones del bastón de una pista de brazos también van por slerp)
        self.overlay = MClip(name + "_feet", frames, overlay, loop=kw.get("loop", False)) if overlay else None
        if self.overlay is not None:
            # una pista que arranca a mitad del clip (antes de su primera clave manda el cuerpo)
            self.overlay.start = overlay_start
        # más pistas ya armadas (la variante _P3 suma la de los pies del clip base a la de brazos y bastón); la última manda
        self.overlays = [o for o in overlays if o is not None] + ([self.overlay] if self.overlay is not None else [])

    def controls(self, f):
        # el atraso de 'lag' se apaga en los 3 primeros y los 3 últimos cuadros de un clip suelto: la primera y la
        # última pose son exactamente las de encadenado (si no, la cadera que guía arrancaba ya corrida)
        chans = set()
        for k in self.keys:
            chans.update(k.ctrl.keys())
        out = {}
        for c in chans:
            lag = self.lag.get(c, 0.0)
            if not self.loop:
                lag *= max(0.0, min(1.0, f / 3.0, (self.frames - f) / 3.0))
            ff = f - lag
            if self.loop:
                ff = ff % self.frames
            out[c] = self.sample(ff, c)
        for o in self.overlays:
            if f >= getattr(o, "start", 0):
                oc = {k: v for k, v in o.controls(f).items() if v is not None}
                for s in "rl":
                    # una pista que pisa los dedos o el dorso sin traer su giro: el de las claves de abajo ya no vale
                    if f"hand_{s}_q" not in oc and (f"hand_{s}_dir" in oc or f"hand_{s}_up" in oc):
                        out.pop(f"hand_{s}_q", None)
                out.update(oc)
        return out

    def sample(self, f, channel):
        if channel not in DIRS:
            return super().sample(f, channel)
        ks = self.keys
        f = max(0.0, min(float(self.frames), f))
        i = self._seg(f)
        a, b = ks[i], ks[i + 1]
        s = NA.ease(b.ease_ch.get(channel, b.ease), (f - a.frame) / max(1e-6, b.frame - a.frame))
        va, vb = a.ctrl.get(channel), b.ctrl.get(channel)
        if va is None and vb is None:
            return None
        va = vb if va is None else va
        vb = va if vb is None else vb
        return tuple(NA.slerp_dir(va, vb, s))


# ============================================================================ utilidades de poses
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


def flat(x, y, yaw=0.0):
    """Pie apoyado plano: tobillo sobre (x, y), la punta girada 'yaw' (+ = hacia su izquierda)."""
    return (x, y, AZ), (0.0, 0.0, yaw), 0.0


def _pivot(x, y, yaw, py, ang):
    """Tobillo de un pie con la MISMA huella que flat(x, y, yaw) girado 'ang' grados (+ = talón arriba) sobre la línea
    del piso que pasa a 'py' del tobillo (negativo = adelante): ese borde no se mueve, el pie no patina."""
    R = Matrix.Rotation(math.radians(yaw), 3, 'Z')
    piv = Vector((x, y, AZ)) + R @ Vector((0.0, py, -AZ))
    a = math.radians(ang)
    v = Vector((0.0, -py, AZ))
    vr = Vector((0.0, v.y * math.cos(a) - v.z * math.sin(a), v.y * math.sin(a) + v.z * math.cos(a)))
    return tuple(piv + R @ vr)


def on_ball(bx, by, yaw=0.0, heel=0.0):
    """Pie apoyado por la BOLA en (bx, by): para un pie que gira sobre la bola (el eje de un giro) la bola queda fija
    con cualquier 'yaw' y el talón levantado 'heel' grados."""
    R = Matrix.Rotation(math.radians(yaw), 3, 'Z')
    a = Vector((bx, by, 0.0)) - R @ Vector((0.0, MR.SOLE_BALL_Y, 0.0))
    return ball(a.x, a.y, yaw, heel)


def ball(x, y, yaw=0.0, heel=20.0):
    """En la bola del pie: el talón sube 'heel' grados y los dedos quedan planos en el piso (se doblan lo mismo)."""
    return _pivot(x, y, yaw, MR.SOLE_BALL_Y, heel), (heel, 0.0, yaw), heel


def tiptoe(x, y, yaw=0.0, heel=40.0, toe=10.0):
    """En punta (la punta de la suela fija): para el empuje de un salto."""
    return _pivot(x, y, yaw, MR.SOLE_TOE_Y, heel), (heel, 0.0, yaw), toe


def heel(x, y, yaw=0.0, toe_up=15.0):
    """Sobre el talón (el borde de atrás fijo), la punta levantada 'toe_up' grados."""
    return _pivot(x, y, yaw, MR.SOLE_HEEL_Y, -toe_up), (-toe_up, 0.0, yaw), 0.0


def air(x, y, z, pitch=0.0, yaw=0.0, toe=0.0, roll=0.0):
    """Pie en el aire: tobillo en (x, y, z) del mundo del clip."""
    return (x, y, z), (pitch, roll, yaw), toe


def feet(p, r=None, l=None):
    q = mod(p)
    for s, f in (("r", r), ("l", l)):
        if f is not None:
            q["foot_" + s], q["foot_" + s + "_rot"], q["toe_" + s] = f
    return q


def at_travel(p, travel):
    """La misma pose (en el espacio del personaje) cuando el transform ya avanzó 'travel' metros: solo se corre lo que
    está en el mundo."""
    q = copy.deepcopy(p)
    for k in WORLD_POS:
        if q.get(k) is not None:
            x, y, z = q[k]
            q[k] = (x, y - travel, z)
    q["travel"] = travel
    return q


def mix(p, q, w):
    """Pose intermedia (w = 0 -> p, 1 -> q): posiciones y giros en línea recta, direcciones por slerp."""
    out = mod(p)
    for k, vb in q.items():
        va = p.get(k)
        if k == "extra" or k.startswith("_") or va is None or vb is None:
            out[k] = copy.deepcopy(vb if va is None else va)
        elif isinstance(vb, (int, float)):
            out[k] = va + (vb - va) * w
        elif k in DIRS or k in NA.DIR_CHANNELS:
            out[k] = tuple(NA.slerp_dir(va, vb, w))
        else:
            out[k] = tuple(Vector(va).lerp(Vector(vb), w))
    return out


def hand(p, s, pos, fingers, dorsum, elbow=None, shape=None):
    """La mano s ('r' / 'l') con la palma en pos, los dedos hacia 'fingers' y el dorso hacia 'dorsum'."""
    # una mano autorada a mano no está pegada al pecho (si no, la mezcla con una clave anclada la dejaría anclada)
    kw = {f"hand_{s}": pos, f"hand_{s}_dir": n(*fingers), f"hand_{s}_up": n(*dorsum), f"hand_{s}_follow": 0.0}
    if elbow is not None:
        kw[f"elbow_{s}"] = elbow
    if shape:
        kw.update(MR.hand_shape(s, shape))
    return mod(p, **kw)


# ============================================================================ el Solver, para medir poses
SOLVER = None


def solved(p):
    """Matrices de todos los huesos de una pose (sin resortes), sin la historia del brazo de lo que se horneaba (el
    codo del cuadro anterior: la guardia de referencia tiene que salir igual que el primer cuadro de un clip)."""
    pose = NA.Pose(SOLVER.rig)
    names = ("share_prev", "pole_prev", "up_prev", "d_prev", "h_prev", "ang_prev", "ang_now", "w_prev", "rh_prev", "wr_prev")
    keep = (SOLVER.mode, dict(SOLVER.frame)) + tuple(dict(getattr(SOLVER, k)) for k in names)
    SOLVER.mode = "free"
    for k in names:
        setattr(SOLVER, k, {})
    SOLVER.solve(pose, p)
    SOLVER.mode, SOLVER.frame = keep[:2]
    for k, v in zip(names, keep[2:]):
        setattr(SOLVER, k, v)
    for b in SOLVER.rig.names:
        pose.get(b)
    return pose.W


def to_chest(p, parts):
    """Ancla al pecho las manos ('r', 'l') y/o el bastón ('staff') de la pose p, tal como quedan resueltas: desde acá
    se pueden mover cadera y tronco y esas piezas lo acompañan (staff_follow / hand_*_follow)."""
    W = solved(p)
    Ci = W["Chest"].inverted()
    C3 = NA.rot3(W["Chest"]).transposed()
    q = mod(p)
    for s in ("r", "l"):
        if s not in parts:
            continue
        S = s.upper()
        H = W["Hand_" + S]
        palm = H @ MR.PALM_LOCAL
        el = W["Forearm_" + S].translation - (W["UpperArm_" + S].translation + palm) * 0.5
        q[f"hand_{s}_cpos"] = tuple(Ci @ palm)
        q[f"hand_{s}_cdir"] = tuple(C3 @ NA.rot3(H).col[1])
        q[f"hand_{s}_cup"] = tuple(C3 @ NA.rot3(H).col[2])
        q[f"hand_{s}_celbow"] = tuple(C3 @ el.normalized())
        q[f"hand_{s}_follow"] = 1.0
    if "staff" in parts:
        M = W["Staff"]
        ctr = M.translation + NA.rot3(M).col[1] * (MR.STAFF_LEN * 0.5)
        q["staff_cpos"] = tuple(Ci @ ctr)
        q["staff_cdir"] = tuple(C3 @ NA.rot3(M).col[1])
        q["staff_cup"] = tuple(C3 @ NA.rot3(M).col[2])
        q["staff_follow"] = 1.0
    return q


def unfollow(p):
    """La pose sin anclas al pecho (para autorar claves sueltas a partir de una pose de guardia)."""
    q = mod(p)
    for k in [k for k in q if k.endswith("_follow")]:
        q[k] = 0.0
    return q


# ============================================================================ guardias
REST = {k: v for k, v in MR.NEUTRAL.items() if v is not None and k != "extra"}
FOOT_R0 = flat(-0.20, -0.24, 4.0)          # el pie de adelante (el derecho, hacia Kaito)
FOOT_L0 = flat(0.25, 0.24, 34.0)           # el de atrás, abierto: el peso descansa acá
# la guardia del maestro: alto y tranquilo, el peso atrás, la derecha adelante con la palma hacia Kaito. Las tres fases
# comparten piernas, cadera y tronco: el combo de una fase y la reacción de otra encadenan sin saltos
BODY = feet(mod(REST, hips=(0.02, 0.06, -0.08), hips_rot=(0.0, 0.0, 14.0), spine=(3.0, 0.0, 4.0), chest=(2.0, 0.0, 4.0),
                neck=(-2.0, 0.0, -10.0), head=(-5.0, 0.0, -11.0), knee_r=(-0.25, -1.0, 0.0), knee_l=(0.45, -1.0, 0.0)),
            r=FOOT_R0, l=FOOT_L0)
# la palma derecha a la altura de la cara y abierta hacia su derecha (no tapa el pecho: desde arriba es un brazo que sale
# de la silueta), los dedos arriba
_GUARD_R = dict(pos=(-0.25, -0.47, 1.84), fingers=(0.08, -0.25, 1.0), dorsum=(-0.25, 1.0, 0.22), elbow=(-0.75, 0.25, -0.65),
                shape="palm")
# la izquierda de la fase 2: más abajo y abierta al costado, la palma también hacia Kaito (el abrazo del concepto)
_GUARD_L = dict(pos=(0.36, -0.36, 1.42), fingers=(0.2, -0.3, 1.0), dorsum=(0.25, 1.0, 0.25), elbow=(0.7, 0.3, -0.7),
                shape="palm")
READY2 = hand(hand(BODY, "r", **_GUARD_R), "l", **_GUARD_L)
READY1 = mod(READY2, back_l=1.0, **MR.hand_shape("l", "relaxed"))
# fase 3: el bastón apuntando a Kaito por delante a su izquierda, la derecha adelante y la izquierda en la cadera de atrás
# (5 cm afuera del costado: más adentro el bastón quedaba medio metido en el chaleco en toda la fase 3)
# los pulgares se miran en toda la fase 3: la derecha (del lado de la punta de abajo, la que pega) con el pulgar hacia
# la de arriba y la izquierda hacia la de abajo (staff_pose: rt=1, lt=-1), la de adelante por arriba y la de atrás por
# abajo. Con la derecha de esta guardia al revés (los dos pulgares hacia la punta), cada golpe que salía de ella daba
# vuelta la mano alrededor del caño en un cuadro (Guard_P3 f2, Taunt_P3, CraneKick_P3, Defeat...)
STAFF_GUARD = dict(staff_on=1.0, staff_pos=(0.17, -0.18, 1.2), staff_dir=n(0.22, 0.95, 0.2), staff_up=(0.0, 0.0, 1.0),
                   grip_r=-0.36, grip_l=0.4, grip_r_up=(0.0, 0.0, 1.0), grip_l_up=(0.0, 0.0, 1.0), grip_r_thumb=1.0,
                   grip_l_thumb=-1.0, elbow_r=(-0.8, 0.2, -0.6), elbow_l=(0.8, 0.5, -0.4), grip_r_w=1.0, grip_l_w=1.0,
                   back_l=0.0, **MR.hand_shape("r", "grip"), **MR.hand_shape("l", "grip"))
READY3 = mod(READY2, **STAFF_GUARD)
READY = {1: READY1, 2: READY2, 3: READY3}


ANCHOR_KEYS = tuple(f"hand_{s}_{k}" for s in "rl" for k in ("cpos", "cdir", "cup", "celbow", "follow")) +     ("staff_cpos", "staff_cdir", "staff_cup", "staff_follow")
# anclas al pecho de cada guardia (las calcula init con el Solver): 'r' = la derecha de la guardia, 'l' = la izquierda
# de la fase 2, 'staff' = el bastón de la fase 3
ANCHOR = {}


def anchor(p, *parts, **offsets):
    """La pose p con esas piezas de la guardia pegadas al pecho. offsets: r=(dx, dy, dz) / l=... / staff=... corren el
    ancla en el espacio de Chest (la mano que se sacude en una reacción, el bastón que se recoge)."""
    q = mod(p)
    for part in parts:
        for k, v in ANCHOR[part].items():
            q[k] = v
        off = offsets.get(part)
        if off is not None:
            k = "staff_cpos" if part == "staff" else f"hand_{part}_cpos"
            q[k] = tuple(Vector(ANCHOR[part][k]) + Vector(off))
    return q


def arms(p, ph, r=None, l=None, staff=None, right=False, left=None):
    """Los brazos de la fase ph sobre una pose de cuerpo: fase 1 la izquierda en la espalda, fase 2 la izquierda de la
    guardia pegada al pecho, fase 3 el bastón pegado al pecho (con las dos manos en él). right=True ancla también la
    derecha de la guardia (reacciones, locomoción); si no, la derecha es la que autoró la pose (el golpe). left = dict de
    hand() para la izquierda de la fase 2 cuando el golpe la usa (las dos alas de la grulla)."""
    if ph == 3:
        q = mod(p, **STAFF_GUARD)
        q.pop("_left_p2", None)
        return anchor(q, "staff", staff=staff)
    parts = ["r"] if right else []
    q = mod(p, back_l=1.0, hand_l_follow=0.0, **MR.hand_shape("l", "relaxed")) if ph == 1 else mod(p, back_l=0.0)
    q.pop("_left_p2", None)
    if ph == 2 and left is not None:
        q = hand(q, "l", **left)
        q["hand_l_follow"] = 0.0
    elif ph == 2:
        parts.append("l")
        q.update(MR.hand_shape("l", "palm"))
    if right:
        q.update(MR.hand_shape("r", "palm"))
    return anchor(q, *parts, r=r, l=l)


def init(solver):
    """Lo que necesita la pose resuelta (las anclas de las guardias) y después arma todos los clips."""
    global SOLVER
    SOLVER = solver
    for part, pose, parts in (("r", READY1, ("r",)), ("l", READY2, ("l",)), ("staff", READY3, ("staff",))):
        q = to_chest(pose, parts)
        keys = [k for k in ANCHOR_KEYS if (k.startswith("staff") if part == "staff" else k.startswith(f"hand_{part}_"))]
        ANCHOR[part] = {k: q[k] for k in keys}
    CLIPS.clear()
    define_clips()
    return CLIPS


CLIPS = []


# ============================================================================ registro
SUFFIX = {1: "", 2: "_P2", 3: "_P3"}
POSES = {}          # poses con nombre para la hoja de laboratorio (--lab)


def add(name, frames, keys, ph=1, base=None, loop=False, lag=None, timing=None, events=None, notes="", steps=None, variant=True):
    """keys: (cuadro, pose, curva) o (cuadro, pose, curva, {canal: curva, "stop": (canales,)}). steps: claves solo de los
    pies [(cuadro, {r: pie, l: pie}, curva)] que pisan las del cuerpo (ver feet())."""
    def key(k):
        ch = dict(k[3]) if len(k) > 3 else {}
        stops = ch.pop("stop", ())
        return Key(k[0], copy.deepcopy(k[1]), k[2], ch, stops)
    t = dict(timing or {})
    t.setdefault("phase", ph)
    ov, ov_start = None, 0
    if steps and steps[0][0] > 0:
        ov_start = steps[0][0]
        steps = [(0,) + tuple(steps[0][1:])] + list(steps)
    if steps:
        # pista aparte: pies ('r', 'l' con feet()) y cualquier otro canal (el saco que vuela)
        ov = [Key(f, {**feet({}, r=st.get("r"), l=st.get("l")), **{k: v for k, v in st.items() if k not in ("r", "l")}}, e)
              for f, st, e in steps]
    # un golpe propio de una fase (TwinPalm, los del bastón) no es variante de nadie: va sin sufijo
    nm = name + (SUFFIX[ph] if variant else "")
    c = MClip(nm, frames, [key(k) for k in keys], phase=ph, base=base or (name if ph > 1 and variant else None), loop=loop,
              lag=LEAD if lag is None else lag, timing=t, events=events, notes=notes, overlay=ov, overlay_start=ov_start)
    CLIPS.append(c)
    return c


def rigid_hands(ks):
    """El giro de cada mano en cada clave como cuaternión ('hand_r_q', 'hand_l_q', del mismo lado que el de la clave
    anterior): el clip lo interpola como un giro (Clip.sample, normalizado en el Solver) en vez de los dedos y el dorso
    por separado: con los dos vectores sueltos, la llamada de Taunt pasaba el dorso a 160° de los dedos y la palma daba
    media vuelta en un cuadro. Se rehace con los dedos y el dorso de cada clave (una variante que copia las claves de su
    base y les cambia la mano no hereda el giro viejo)."""
    for s in "rl":
        prev = None
        for k in ks:
            d, u = k.ctrl.get(f"hand_{s}_dir"), k.ctrl.get(f"hand_{s}_up")
            if d is None or u is None:
                k.ctrl.pop(f"hand_{s}_q", None)
                continue
            q = NA.basis_yz(d, u).to_quaternion()
            if prev is not None and prev.dot(q) < 0.0:
                q.negate()
            k.ctrl[f"hand_{s}_q"] = tuple(q)
            prev = q


# la cadera guía y la cabeza llega después (las articulaciones se rompen en sucesión)
LEAD = {"hips": -0.6, "hips_rot": -0.6, "spine": -0.3, "head": 1.0, "neck": 0.5}


class Gait(NA.ProcClip):
    """Ciclo de locomoción: los pies apoyados se deslizan hacia atrás EXACTAMENTE a la velocidad del juego (en el mundo
    quedan quietos), el talón entra primero y el despegue rueda sobre la bola del pie. La cadera baja al recibir el peso
    y se mece sobre el pie de apoyo; el pecho contrarresta el giro de la cadera."""

    def __init__(self, name, frames, fn, ph, base, **kw):
        super().__init__(name, frames, fn, **kw)
        self.phase, self.base = ph, base


def gait(name, ph, frames, speed, direction, stance, lift, bob, sway, yaw_amp, lean, width=0.19, hip_z=-0.14, yaw0=8.0,
         heel_max=22.0, strike=8.0, flight=False, notes="", staff_off=None):
    """direction: (x, y) hacia donde avanza (frente = (0, -1)); speed en m/s; width = medio ancho entre tobillos."""
    T = frames / FPS
    d = Vector((direction[0], direction[1], 0.0)).normalized()
    span = speed * stance * T
    side = abs(d.x) > 0.5
    base_r, base_l = Vector((-width, 0.0, 0.0)), Vector((width, 0.0, 0.0))
    yaw_r, yaw_l = (-6.0, 6.0) if not side else (2.0, 10.0)

    def foot(u, base, yaw):
        if u < stance:
            w = u / stance
            p = base + d * (span * (0.5 - w))
            if w < 0.14 and strike > 0.0:
                return heel(p.x, p.y, yaw, strike * (1.0 - w / 0.14))
            if w > 0.68:
                return ball(p.x, p.y, yaw, heel_max * (w - 0.68) / 0.32)
            return flat(p.x, p.y, yaw)
        # vuelo: de la bola del despegue al talón del apoyo siguiente, en arco
        w = (u - stance) / (1.0 - stance)
        s = w * w * (3.0 - 2.0 * w)
        p0 = base + d * (-0.5 * span)
        p1 = base + d * (0.5 * span)
        a0, _, _ = ball(p0.x, p0.y, yaw, heel_max)
        a1, _, _ = heel(p1.x, p1.y, yaw, strike)
        early = 0.03 * math.sin(math.pi * w / 0.3) if w < 0.3 else 0.0
        a = Vector(a0).lerp(Vector(a1), s) + Vector((0.0, 0.0, lift * math.sin(math.pi * w) + early))
        pitch = heel_max * (1.0 - s) - strike * s - 10.0 * math.sin(math.pi * w)
        return tuple(a), (pitch, 0.0, yaw), heel_max * (1.0 - s) ** 2

    def fn(f):
        t = f / frames
        ur, ul = t % 1.0, (t + 0.5) % 1.0
        c2 = math.cos(4.0 * math.pi * (t - 0.06))            # dos bajadas por ciclo, justo después de apoyar
        yw = yaw_amp * math.sin(2.0 * math.pi * (t + 0.25))
        sw = sway * math.sin(2.0 * math.pi * t)
        lv = Vector((d.x, d.y, 0.0)) * 0.04
        drop = bob * (0.5 + 0.5 * c2)
        if flight:                                             # corriendo, el cuerpo sube en el vuelo
            drop = bob * (0.5 - 0.5 * c2)
        p = mod(BODY, hips=(sw * (0.0 if side else 1.0) + lv.x, 0.03 + lv.y, hip_z - drop),
                hips_rot=(lean * (0.0 if side else 0.4), sw * 8.0 * (0.0 if side else 1.0), yaw0 + (0.0 if side else yw)),
                spine=(3.0 + lean * 0.4, 0.0, 2.0 - yw * 0.7), chest=(2.0 + lean * 0.3, 0.0, 2.0 - yw * 0.9),
                neck=(-2.0 - lean * 0.4, 0.0, -yaw0 * 0.6 + yw * 0.4), head=(-5.0 - lean * 0.4, 0.0, -yaw0 * 0.6 + yw * 0.2),
                knee_r=(-0.1, -1.0, 0.0), knee_l=(0.1, -1.0, 0.0), breath=0.3 + 0.2 * c2)
        p = feet(p, r=foot(ur, base_r, yaw_r), l=foot(ul, base_l, yaw_l))
        # las manos de guardia acompañan el paso (un poco adelante y atrás contra la pierna, y el peso al apoyar): el tronco
        # que contrarresta la cadera y las manos quietas se leían como un muñeco rígido
        sw2 = math.sin(2.0 * math.pi * t)
        hr = (0.0, 0.03 * sw2 * (0.0 if side else 1.0), -0.012 * c2)
        hl = (0.0, -0.03 * sw2 * (0.0 if side else 1.0), -0.012 * c2)
        so = tuple(Vector(staff_off or (0.0, 0.0, 0.0)) + Vector((0.0, -0.012 * c2, 0.02 * sw2 * (0.0 if side else 1.0))))
        return arms(p, ph, right=True, r=hr, l=hl, staff=so)
    c = Gait(name + SUFFIX[ph], frames, fn, ph, name if ph > 1 else None, loop=True, root_vel=(d.x * speed, d.y * speed, 0.0),
             timing={"ground_speed_mps": speed, "stance": stance, "contacts": [0, frames // 2], "phase": ph},
             events=[{"frame": 0, "fn": "Step"}, {"frame": frames // 2, "fn": "Step"}], notes=notes,
             sheet_frames=[round(frames * k / 8) for k in range(9)])
    CLIPS.append(c)
    return c


ROOT_TRAVEL_NOTE = ("travel_m[f] = metros que el transform tiene que haber avanzado hacia su frente (negativo = hacia atrás) en el "
                    "cuadro f del clip. Los pies apoyados quedan clavados solo si el juego mueve el transform por deltas de "
                    "travel_m(stepNorm * frames) con el reloj del paso y AttackDef.lunge = 0 (como KokuyoBoss: la embestida "
                    "lineal de Enemy.cs no sigue la curva). Está medido con StepTimeline y el release_rate de cada clip. En "
                    "timing.air (los dos pies en el aire) el juego puede estirar o acortar el avance para caer en la marca. "
                    "Las reacciones (Hit, Parried...) llevan knock_m: lo que Enemy.knock tiene que empujar con su curva "
                    "1 - e^(-10 t)")
# poses de encadenado por fase (chain_from / chain_to de los clips)
CHAIN = {}


def chain_pose(name, ph):
    if name == "READY":
        return arms(BODY, ph, right=True)
    if name in ("READY2", "READY3"):
        return arms(BODY, int(name[-1]), right=True)
    v = CHAIN.get(name)
    if v is None:
        return None
    return v.get(ph) if isinstance(v, dict) else v


def lab_clip(names):
    """Las poses de POSES sostenidas 12 cuadros cada una (los resortes se asientan): la hoja --lab."""
    keys, f = [(0, POSES[names[0]], "hold")], 0
    for nm in names:
        keys.append((f + 1, POSES[nm], "hold"))
        f += 12
        keys.append((f, POSES[nm], "hold"))
    c = MClip("_lab", f, [Key(k[0], copy.deepcopy(k[1]), k[2]) for k in keys], timing={"kind": "test", "names": names})
    return c


# ============================================================================ los clips
def define_clips():
    for ph in (1, 2, 3):
        idle(ph)
        locomotion(ph)
    for ph in (1, 2):
        palm(ph)
        for v in REACH_K:
            palm(ph, v)
        chop(ph)
        crane(ph)
        leap(ph)
    for ph in (1, 2, 3):
        guard(ph)
        guard_hit(ph)
        guard_hit_l(ph)
        counter(ph)
        counter_strike(ph)
        for v in REACH_K:
            counter_strike(ph, v)
        taunt(ph)
        stance(ph)
        hit(ph)
        hit_heavy(ph)
        parried(ph)
        parried_perfect(ph)
        exhausted(ph)
        exhausted_hit(ph)
        exhausted_rise(ph)
    intro()
    phase_coat()
    twin_palm()
    spin_kick()
    sweep()
    qi_wave()
    dash_strike()
    dash_pass()
    for ph in (1, 2, 3):
        back_hop(ph)
    # fase 3 (el bastón), el cambio de fase 2 -> 3 y la derrota: master_clips_p3.py
    import master_clips_p3 as P3
    P3.define()
    # (al final de la toma: los clips de antes quedan en sus mismos cuadros del FBX)
    for ph in (1, 2, 3):
        guard_hit_low(ph)


def knock(f, K):
    """Retroceso de Enemy.knock (se descuenta K * min(1, 10 dt) por cuadro): -K (1 - e^(-10 t))."""
    return -K * (1.0 - math.exp(-10.0 * f / FPS))


def step_back(p, s, k, dy, lift=0.04):
    """El pie s ('r'/'l') de la pose p corrido dy metros hacia adelante (- = atrás) en el mundo, en el aire 'lift' m:
    clave del medio de un paso de reacción."""
    x, y, z = p["foot_" + s]
    q = mod(p)
    q["foot_" + s] = (x, y + dy * k, z + lift)
    return q


def idle(ph):
    """Guardia que respira (3.2 s, loop): inspira lento con el pecho y los hombros que suben, el peso se mece al pie de
    atrás y vuelve, la cabeza acompaña y la mano de adelante flota con el pecho. Con 2-3 cm y 2° no se veía nada desde la
    cámara del juego (dos cuadros a 1.5 s eran el mismo dibujo): ahora la cadera se mece ~7 cm y la cabeza ~5°."""
    a = arms(BODY, ph, right=True)
    b = arms(mod(BODY, breath=1.0, hips=(0.07, 0.04, -0.092), hips_rot=(0.0, 2.0, 16.0), spine=(1.5, 0.0, 4.5), chest=(-1.0, 0.0, 4.5),
                 neck=(-3.0, 0.0, -11.0), head=(-9.0, 2.5, -14.0)), ph, right=True,
             r=(0.0, 0.03, 0.025), l=(0.0, 0.025, 0.02), staff=(0.0, 0.025, 0.0))
    c = arms(mod(BODY, breath=0.2, hips=(-0.01, 0.075, -0.072), hips_rot=(0.0, -1.5, 12.0), spine=(3.5, 0.0, 3.5),
                 neck=(-1.0, 0.0, -9.0), head=(-2.5, -2.0, -8.5)), ph, right=True, r=(0.0, -0.01, -0.01), staff=(0.0, -0.01, 0.0))
    POSES[f"guardia {ph}"] = a
    return add("Idle", 96, [(0, a, "sine"), (44, b, "sine"), (72, c, "sine"), (96, a, "sine")], ph=ph, loop=True,
               lag={"head": 3.0, "neck": 1.5}, timing={"kind": "idle", "chain_from": "READY", "chain_to": "READY"},
               notes="guardia de la fase %d respirando: inspira en 1.5 s, el peso se mece al pie de atrás" % ph)


def locomotion(ph):
    gait("Walk", ph, 36, 1.6, (0.0, -1.0), stance=0.6, lift=0.12, bob=0.035, sway=0.03, yaw_amp=6.0, lean=3.0,
         notes="camina a 1.6 m/s (walkSpeed): pasos de 0.96 m, rodillas flojas (se desliza, no rebota)")
    gait("Run", ph, 22, 4.0, (0.0, -1.0), stance=0.36, lift=0.3, bob=0.05, sway=0.02, yaw_amp=9.0, lean=12.0, hip_z=-0.12,
         heel_max=30.0, strike=4.0, flight=True, notes="corre a 4.0 m/s (runSpeed): trancos de 1.47 m con vuelo, erguido",
         staff_off=(0.05, 0.1, 0.0))
    gait("StrafeL", ph, 24, 1.3, (1.0, 0.0), stance=0.56, lift=0.1, bob=0.03, sway=0.0, yaw_amp=0.0, lean=2.0, width=0.36,
         strike=0.0, heel_max=10.0, notes="rodea hacia su izquierda a 1.3 m/s sin cruzar los pies (paso y junta)")
    gait("StrafeR", ph, 24, 1.3, (-1.0, 0.0), stance=0.56, lift=0.1, bob=0.03, sway=0.0, yaw_amp=0.0, lean=2.0, width=0.36,
         strike=0.0, heel_max=10.0, notes="rodea hacia su derecha a 1.3 m/s")
    gait("WalkBack", ph, 36, 1.2, (0.0, 1.0), stance=0.62, lift=0.1, bob=0.03, sway=0.025, yaw_amp=4.0, lean=-2.0,
         strike=0.0, heel_max=14.0, notes="retrocede a 1.2 m/s mirando a Kaito")


# ============================================================================ golpes de palma (fase 1 y 2)
R0 = hand(BODY, "r", **_GUARD_R)              # la guardia con la derecha explícita (los golpes la mueven)
LF0, RF0 = FOOT_L0, FOOT_R0
# largos del paso de los golpes que avanzan: el autorado (Palm 0.95 m...), el medio y el corto. Las variantes son el
# mismo golpe hasta la suelta (cuadro por cuadro) y el jefe elige en la suelta la más larga que entra hasta Kaito
# (BambooMasterBoss.PickReach): antes el paso entero chocaba contra Kaito pegado, se perdía el 60-80 % del avance y el
# pie apoyado patinaba lo mismo. Mezclarlas en un blend tree no sirve: la mezcla de giros de las piernas (una estirada
# 1.4 m, la otra en 0.6 m) hundía el pie de atrás 17 cm en el piso
REACH_K = {"Mid": 0.53, "Close": 0.13}    # fracción del paso autorado (Palm: 0.5 y 0.12 m)


def reach_names(base, ph):
    """Las variantes cortas de un golpe con paso, de la más larga a la más corta (con el sufijo de la fase)."""
    return [f"{base}_{v}{SUFFIX[ph]}" for v in REACH_K]


def lerp3(a, b, k):
    return tuple(Vector(a).lerp(Vector(b), k))


def ready(ph, travel=0.0):
    """La guardia de la fase tal como encadena (chain_pose READY), corrida 'travel' metros: el primer y el último cuadro
    de un golpe. Con la derecha autorada a mano (R0) el primer cuadro se apartaba 2.6° del brazo de la guardia y el
    fundido de 0.08 s lo hacía saltar."""
    return at_travel(chain_pose("READY", ph), travel) if travel else chain_pose("READY", ph)


def framed(ph, keys, frames, travel=0.0, ease0="sine", ease1="sine"):
    """Las claves de un golpe entre la guardia exacta del cuadro 0 y la del último (corrida lo que avanzó)."""
    return [(0, ready(ph), ease0)] + list(keys) + [(frames, ready(ph, travel), ease1)]


def blend_ends(keys, ph, frames, n=4):
    """Claves de un giro procedural (una por cuadro): los primeros y los últimos 'n' cuadros se funden con la guardia
    exacta con la que encadena (sus rodillas y manos de giro se apartaban 5-7° y el fundido de 0.08 s saltaba)."""
    g0 = ready(ph)
    out = []
    for f, p_, e in keys:
        w = min(1.0, f / n, (frames - f) / n)
        if w >= 1.0:
            out.append((f, p_, e))
            continue
        # la guardia con los giros (yaw) en la misma vuelta que el cuadro del giro: 374° y 14° son la misma pose
        g = mod(g0)
        for ch in ("hips_rot", "foot_r_rot", "foot_l_rot"):
            a_, b_ = g.get(ch), p_.get(ch)
            if a_ is not None and b_ is not None:
                g[ch] = (a_[0], a_[1], a_[2] + 360.0 * round((b_[2] - a_[2]) / 360.0))
        out.append((f, mix(g, p_, max(0.0, w)), e))
    return out


def front_step(c, T, drive_f=None):
    """El pie de adelante del paso de un golpe (claves de la pista de pies): sale de la bola del de la guardia, va por el
    aire, apoya el talón en el cuadro anterior al impacto ya encima de la huella (no llega patinando) y rueda a plano en
    el impacto 'c'. T = metros que avanza la huella."""
    RX, RY, RYAW = land_xy(RF0)
    ly = RY - T
    d = drive_f if drive_f is not None else c - 2
    return [(d, air(RX, RY + (ly - RY) * 0.55, AZ + 0.12 + 0.04 * min(1.0, T / 0.5), pitch=-14.0, yaw=2.0), "in2"),
            (c - 1, heel(RX, ly, RYAW, toe_up=12.0), "lin"), (c, flat(RX, ly, RYAW), "lin")]


def follow_step(c, T, end, lift_f=None):
    """El pie de atrás alcanza después del golpe (paso de seguimiento) sin arrastrarse: empuja sobre la bola, despega
    rodando sobre la punta, levanta la suela bien del piso, llega ENCIMA de su huella nueva frenando y recién ahí baja
    (talón y plano). Antes bajaba todavía corriéndose: la suela se arrastraba ~29 cm. Claves de la pista de pies desde
    el impacto 'c' hasta 'end'."""
    LX, LY, LYAW = land_xy(LF0)
    ly = LY - T
    k = min(1.0, T / 0.5)
    f0 = lift_f if lift_f is not None else c + 3
    toe = tiptoe(LX, LY, LYAW, heel=56.0, toe=14.0)
    # la punta despega hacia arriba antes de ir adelante (si no, la punta raspaba el piso al salir)
    up = (tuple(Vector(toe[0]) + Vector((0.0, -0.02 - 0.05 * k, 0.07))), toe[1], toe[2])
    return [(c, ball(LX, LY, LYAW, heel=26.0), "lin"), (c + 2, ball(LX, LY, LYAW, heel=40.0), "inout"),
            (f0, toe, "inout"), (f0 + 1, up, "in2"),
            (f0 + 2, air(LX + 0.02, LY - T * 0.5, AZ + 0.08 + 0.08 * k, pitch=16.0, yaw=LYAW - 6.0, toe=6.0), "lin"),
            (f0 + 4, air(LX, ly, AZ + 0.045, pitch=-5.0, yaw=LYAW), "out"),
            (f0 + 6, heel(LX, ly, LYAW, toe_up=6.0), "inout"), (f0 + 7, flat(LX, ly, LYAW), "lin"), (end, flat(LX, ly, LYAW), "lin")]


def feet_track(front, back, frames, r0=None, l0=None):
    """Pista de pies de un golpe con paso: [(cuadro, pie, curva)] de cada pie desde que deja la guardia. Sale una clave
    por cuadro con los dos pies, cada uno interpolado con SUS claves y curvas (una clave de un pie no le cambia la curva
    al otro)."""
    tracks = {"r": [(0, r0 or RF0, "lin")] + list(front), "l": [(0, l0 or LF0, "lin")] + list(back)}
    out = []
    for f in range(frames + 1):
        out.append((f, {s_: _foot_at(tracks[s_], f) for s_ in ("r", "l")}, "lin"))
    return out


def foot_track(side, keys, frames, start):
    """Pista de UN pie ('r' / 'l'), una clave por cuadro: el otro pie sigue las claves del cuerpo."""
    pts = [(0, start, "lin")] + list(keys)
    return [(f, {side: _foot_at(pts, f)}, "lin") for f in range(frames + 1)]


def _foot_at(pts, f):
    """El pie de una pista en el cuadro f: la clave de ese cuadro o la mezcla entre las dos que lo rodean con la curva de
    la que llega (después de la última, quieto)."""
    prev = max((p for p in pts if p[0] <= f), key=lambda p: p[0])
    nxt = min((p for p in pts if p[0] > f), key=lambda p: p[0], default=None)
    if nxt is None or prev[0] == f:
        return prev[1]
    u = NA.ease(nxt[2], (f - prev[0]) / (nxt[0] - prev[0]))
    (pa, ra, ta), (pb, rb, tb) = prev[1], nxt[1]
    return (tuple(Vector(pa).lerp(Vector(pb), u)), tuple(Vector(ra).lerp(Vector(rb), u)), ta + (tb - ta) * u)


def palm(ph, var=None):
    """Tui zhang (palma que empuja), dorado. AVISO: se enrosca hacia su derecha con la palma recogida junto a la oreja y
    el codo afuera (desde arriba el brazo sale de la silueta por su derecha y el pecho gira 38°), el peso atrás y el pie de
    adelante liviano. El pie de atrás empuja, la cadera gira y la palma llega cuando el pie de adelante se clava, T m
    más adelante; el de atrás alcanza en la recuperación (paso de seguimiento). Las variantes ('Mid', 'Close') son la
    misma palma con un paso más corto y el cuerpo más alto (la corta es casi un pisotón desde la guardia)."""
    A = lambda p: arms(p, ph)
    T = 0.95 * (1.0 if var is None else REACH_K[var])
    k = T / 0.95
    name = "Palm" if var is None else "Palm_" + var
    k_pre = mod(R0, hips=(0.03, 0.1, -0.11), hips_rot=(0.0, -1.0, 6.0), spine=(2.0, 0.0, 0.0), chest=(1.0, 0.0, 0.0),
                neck=(-1.0, 0.0, -2.0), head=(-4.0, 0.0, -4.0),
                hand_r=(-0.34, -0.2, 1.8), hand_r_dir=n(0.05, -0.3, 1.0), hand_r_up=n(-0.3, 1.0, 0.0))
    coil = mod(R0, hips=(0.03, 0.17, -0.16), hips_rot=(0.0, -2.0, -12.0), spine=(0.0, 0.0, -6.0), chest=(-2.0, 0.0, -6.0),
               neck=(0.0, 0.0, 12.0), head=(-3.0, 0.0, 14.0), clav_r=(0.0, 6.0, -4.0),
               hand_r=(-0.46, 0.14, 1.78), hand_r_dir=n(0.0, -0.3, 1.0), hand_r_up=n(-0.3, 1.0, -0.1),
               elbow_r=(-0.5, 0.7, -0.6), knee_l=(0.6, -1.0, 0.0))
    POSES[f"palma aviso {ph}"] = A(coil)
    hold = mod(coil, hips=(0.03, 0.18, -0.17), hand_r=(-0.47, 0.155, 1.79), head=(-3.5, 0.0, 14.5))
    drive = mod(R0, hips=lerp3((0.02, 0.1, -0.24), (0.0, 0.02, -0.3), k), hips_rot=(4.0, 0.0, 6.0), spine=(6.0, 0.0, 2.0),
                chest=(2.0, 0.0, 2.0), neck=(-3.0, 0.0, -4.0), head=(-6.0, 0.0, -4.0),
                hand_r=(-0.32, -0.35, 1.58), hand_r_dir=n(0.0, -0.4, 1.0), hand_r_up=n(-0.1, 1.0, 0.0), elbow_r=(-0.5, 0.4, -0.8),
                travel=T * 0.26)
    strike = mod(R0, hips=lerp3((0.0, 0.07, -0.23), (-0.02, -0.06, -0.38), k), hips_rot=(5.0 + 3.0 * k, 0.0, 18.0),
                 spine=(8.0 + 4.0 * k, 0.0, 8.0), chest=(4.0, 0.0, 6.0), neck=(-6.0, 0.0, -14.0), head=(-10.0, 0.0, -16.0),
                 clav_r=(0.0, -4.0 - 2.0 * (1.0 - k), 8.0),
                 hand_r=lerp3((-0.06, -1.02, 1.34), (-0.06, -1.22, 1.26), k), hand_r_dir=n(0.0, -0.15, 1.0), hand_r_up=(0.0, 1.0, 0.0),
                 elbow_r=(-0.4, 0.3, -0.85), travel=T * 0.63)
    POSES[f"palma golpe {ph}"] = A(strike)
    over = mod(strike, hips=tuple(Vector(strike["hips"]) + Vector((-0.01, -0.04, -0.04))), spine=(10.0 + 4.0 * k, 0.0, 8.0),
               hand_r=tuple(Vector(strike["hand_r"]) + Vector((0.01, -0.08, -0.04))), travel=T * 0.86)
    rec_a = mod(R0, hips=lerp3((0.02, 0.05, -0.2), (0.0, -0.02, -0.26), k), hips_rot=(3.0, 0.0, 14.0), spine=(6.0, 0.0, 6.0),
                chest=(2.0, 0.0, 4.0), neck=(-3.0, 0.0, -10.0), head=(-7.0, 0.0, -12.0),
                hand_r=lerp3((-0.18, -0.68, 1.6), (-0.18, -0.78, 1.56), k), hand_r_dir=n(0.05, -0.3, 1.0), hand_r_up=n(-0.2, 1.0, 0.2),
                travel=T * 0.96)
    rec_b = mod(at_travel(R0, T), hips=(0.02, 0.04, -0.12), hand_r=(-0.24, -0.55, 1.78))
    end = at_travel(R0, T)
    # la pausa del aviso es un tope de todos los canales: hasta la suelta la curva no ve el paso, que cambia con la variante
    keys = [(4, k_pre, "inout"), (10, coil, "inout"), (12, hold, "sine", {"stop": tuple(hold)}),
            (13, drive, "in2", {"travel": "lin"}), (15, strike, "expo_in", {"travel": "lin"}),
            (17, over, "out", {"travel": "out2"}), (21, rec_a, "inout", {"travel": "out2"}), (26, rec_b, "inout")]
    RX, RY, RYAW = land_xy(RF0)
    LX, LY, LYAW = land_xy(LF0)
    front = [(4, ball(RX, RY, RYAW, heel=5.0), "inout"), (10, ball(RX, RY, RYAW, heel=10.0), "inout"),
             (12, ball(RX, RY, RYAW, heel=10.0), "sine")] + front_step(15, T)
    back = [(12, flat(LX, LY, LYAW), "lin"), (13, ball(LX, LY, LYAW, heel=16.0), "in2")] + follow_step(15, T, 34)
    t = {"tell": [0, 10], "apex": 10, "hold": [10, 12], "contact": 15, "active": [15, 17], "recover": [17, 34],
         "lunge": [12, 26, T], "kind": GOLD, "glow": "Master_GlintHandR", "strike": PALM_R, "chain_from": "READY",
         "chain_to": "READY"}
    if var is None:
        t["reach_variants"] = reach_names("Palm", ph)
    return add(name, 34, framed(ph, [(k_[0], A(k_[1])) + tuple(k_[2:]) for k_ in keys], 34, T), ph=ph, steps=feet_track(front, back, 34),
               timing=t,
               events=[{"frame": 10, "fn": "Apex"}, {"frame": 15, "fn": "Strike"}, {"frame": 14, "fn": "Step"},
                       {"frame": 24, "fn": "Step"}],
               notes=("tui zhang: se enrosca con la palma junto a la oreja (aviso f10), el pie de atrás empuja y la palma pega "
                      "cuando el de adelante se clava (f15) a %.2f m; el de atrás alcanza en f24" % T) +
                     ("" if var is None else ". Variante de paso corto de Palm (la elige el jefe en la suelta)"))


def land_xy(foot):
    """(x, y, yaw) de la huella de un pie dado como flat()."""
    (x, y, _), (_, _, yaw), _ = foot
    return x, y, yaw


# ============================================================================ guardia, desvío y contraataque
# la guardia cerrada es la grulla que abre las alas (la postura del taichí): el peso todo atrás, el pie de adelante en la
# bola (postura del gato), la palma derecha alzada al costado de la cabeza y abierta hacia Kaito, el codo afuera. Desde
# arriba es un brazo alto que sale de la silueta de la espera (una palma estirada hacia Kaito apunta a la cámara y casi no
# se ve; delante de la cara la tapaba la cabeza). Atacarla es el error que enseña paciencia
G_BODY = feet(mod(BODY, hips=(0.03, 0.15, -0.17), hips_rot=(0.0, 0.0, 18.0), spine=(2.0, 0.0, 4.0), chest=(-2.0, 0.0, 4.0),
                  neck=(-2.0, 0.0, -12.0), head=(-6.0, 0.0, -14.0), knee_l=(0.55, -1.0, 0.0)),
              r=ball(*land_xy(FOOT_R0), heel=14.0))
_G_R = dict(pos=(-0.47, -0.3, 2.3), fingers=(-0.3, -0.15, 1.0), dorsum=(0.35, 0.9, 0.15), elbow=(-1.0, 0.15, -0.45), shape="palm")
# la otra ala (fase 2): la izquierda baja junto a la cadera de adelante, la palma hacia el piso, los dedos hacia Kaito
# (más afuera y adelante que la izquierda de la espera de la fase 2, que está casi en el mismo lugar 22 cm más arriba:
# desde la cámara del juego la guardia quedaba en 15 % de cambio)
_G_L = dict(pos=(0.48, -0.48, 1.18), fingers=(0.25, -1.0, -0.05), dorsum=(0.1, 0.0, 1.0), elbow=(0.8, 0.4, -0.45), shape="palm")
# fase 3: el bastón horizontal delante del pecho, las manos abiertas a lo ancho (bloqueo alto)
_G_STAFF = dict(staff_on=1.0, staff_follow=0.0, staff_pos=(0.02, -0.5, 1.72), staff_dir=n(1.0, 0.1, 0.06), staff_up=(0.0, -1.0, 0.0),
                grip_r=-0.4, grip_l=0.4, grip_r_up=(0.0, 0.0, 1.0), grip_l_up=(0.0, 0.0, 1.0), grip_r_thumb=1.0, grip_l_thumb=-1.0,
                elbow_r=(-0.7, 0.2, -0.7), elbow_l=(0.7, 0.2, -0.7), **MR.hand_shape("r", "grip"), **MR.hand_shape("l", "grip"))


def staff_pose(p, pos, d, upv=(0.0, 0.0, 1.0), gr=-0.4, gl=0.4, rt=1.0, lt=-1.0, gru=(0.0, 0.0, 1.0), glu=(0.0, 0.0, 1.0), **kw):
    """El bastón en el espacio del personaje (centro, eje de la punta de abajo a la de arriba, cara) y dónde lo agarra cada
    mano (metros desde el centro, None = suelta)."""
    # una mano suelta no deja de tener su número de agarre (se interpola): grip_*_w = 0 la despega del bastón
    q = mod(p, staff_on=1.0, staff_follow=0.0, staff_pos=pos, staff_dir=n(*d), staff_up=n(*upv),
            grip_r=0.0 if gr is None else gr, grip_l=0.0 if gl is None else gl, grip_r_w=0.0 if gr is None else 1.0,
            grip_l_w=0.0 if gl is None else 1.0, grip_r_thumb=rt, grip_l_thumb=lt, grip_r_up=n(*gru), grip_l_up=n(*glu),
            back_l=0.0, **kw)
    if gr is not None:
        q.update(MR.hand_shape("r", "grip"))
    if gl is not None:
        q.update(MR.hand_shape("l", "grip"))
    return q


def staff_hands(p, center, d, hr=None, hl=None, **kw):
    """El bastón por su centro y su eje, con cada mano donde cae la proyección de 'hr' / 'hl' sobre el eje (None = suelta):
    se autora dónde van las manos y el agarre sale solo (el bastón se desliza entre los dedos en una estocada)."""
    c, a = Vector(center), Vector(d).normalized()
    gr = None if hr is None else (Vector(hr) - c).dot(a)
    gl = None if hl is None else (Vector(hl) - c).dot(a)
    return staff_pose(p, center, d, gr=gr, gl=gl, **kw)


def guard_arms(p, ph, r=None, l=None, staff=None):
    """Brazos de la guardia cerrada: la derecha alzada (r = corrimiento en el mundo y, opcional, el dorso), la izquierda
    baja de la fase 2 (l = corrimiento), el bastón horizontal de la fase 3 (staff = corrimiento del centro y, opcional,
    el eje)."""
    if ph == 3:
        q = mod(p, **_G_STAFF)
        if staff:
            q["staff_pos"] = tuple(Vector(_G_STAFF["staff_pos"]) + Vector(staff[:3]))
            if len(staff) > 3:
                q["staff_dir"] = n(*staff[3])
        return q
    gr = dict(_G_R)
    if r:
        gr["pos"] = tuple(Vector(gr["pos"]) + Vector(r[:3]))
        if len(r) > 3:
            gr["dorsum"] = r[3]
    gl = dict(_G_L)
    if l:
        gl["pos"] = tuple(Vector(gl["pos"]) + Vector(l[:3]))
    q = hand(p, "r", **gr)
    return arms(q, ph, left=gl if ph == 2 else None)


def guard(ph):
    """Entra en la guardia cerrada y se queda quieto (el juego deja el último cuadro: Enemy.EnterGuard)."""
    a = arms(BODY, ph, right=True)
    mid = guard_arms(mod(G_BODY, hips=(0.03, 0.16, -0.18), head=(-7.0, 0.0, -14.0)), ph, r=(0.01, -0.02, 0.03), staff=(0.0, -0.02, 0.03))
    g = guard_arms(G_BODY, ph)
    CHAIN.setdefault("GUARD", {})[ph] = g
    POSES[f"guardia cerrada {ph}"] = g
    return add("Guard", 20, [(0, a, "sine"), (9, mid, "out"), (15, g, "inout"), (20, g, "sine")], ph=ph,
               timing={"kind": "none", "hold_last": True, "chain_from": "READY", "chain_to": "GUARD"},
               notes="guardia cerrada (la grulla abre las alas): el peso atrás en la postura del gato, la palma derecha "
                     "alzada al costado de la cabeza, la izquierda baja en la fase 2, el bastón cruzado en la 3. Pose quieta "
                     "desde f15: el juego deja el último cuadro")


# el desvío (BambooMasterBoss.Swat): dónde está la hoja de Kaito cuando llega (kaitooo.fbx, Kaito a 1.4 m de centro a
# centro, en el espacio del maestro) y para dónde sigue. El primer corte y el final cruzan bajando de su izquierda a su
# derecha (la mitad de la hoja en x +0.05..0.14, 0.6 m adelante, a 0.65 m: el muslo del maestro) y el revés sube de su
# derecha a su izquierda (x -0.06, 0.64 m adelante, a 0.85 m). El jefe arranca el manotazo antes del contacto (ReadCut)
# para que la palma (o el bastón) encuentre la hoja en f3; desde ahí la acompaña para donde va
SWAT_MEET = 3


def _swat_body(u, yaw=0.0):
    """El cuerpo que se inclina hacia la hoja (u = 0 la guardia, 1 lo más bajo): la cadera baja y atrás, el tronco
    adelante, la cabeza mira la hoja; yaw gira la cadera y el tronco con el barrido (+ = hacia su izquierda)."""
    return mod(G_BODY, hips=(0.03, 0.15 + 0.1 * u, -0.17 - 0.18 * u), hips_rot=(7.0 * u, 0.0, 18.0 + yaw),
               spine=(2.0 + 30.0 * u, 0.0, 4.0 + 0.5 * yaw), chest=(-2.0 + 10.0 * u, 0.0, 4.0 + 0.3 * yaw),
               neck=(-2.0 + 2.0 * u, 0.0, -12.0), head=(-6.0 - 6.0 * u, 0.0, -14.0))


def _swat_keys(ph, track, staff_track, bows):
    """Claves del desvío: track = (cuadro, mano que barre (pos, dedos, dorso), la otra (pos, dedos, dorso) o None) para
    las fases 1 y 2 (la derecha en la 1; en la 2 la mano que está del lado por donde entra la hoja), staff_track =
    (cuadro, corrimiento del centro, eje) para la 3 y bows = (cuadro, u, yaw)."""
    g = guard_arms(G_BODY, ph)
    keys = [(0, g, "lin")]
    eases = {1: "in2", 2: "lin", SWAT_MEET: "out", 5: "inout", 7: "inout", 10: "inout"}
    for (f, u, yaw), tr, st in zip(bows, track, staff_track):
        body = _swat_body(u, yaw)
        if ph == 3:
            q = guard_arms(body, 3, staff=st[1] + (st[2],))
        else:
            side, hs, other = tr[1], tr[2], tr[3]
            q = hand(body, side, hs[0], hs[1], hs[2], shape="palm")
            if ph == 1:
                q = arms(q, 1)
            else:
                o = "l" if side == "r" else "r"
                if other is None:
                    other = (_G_L if o == "l" else _G_R)
                    other = (other["pos"], other["fingers"], other["dorsum"])
                if o == "l":
                    q = arms(q, 2, left=dict(pos=other[0], fingers=other[1], dorsum=other[2], elbow=_G_L["elbow"], shape="palm"))
                else:
                    q = arms(hand(q, "r", other[0], other[1], other[2], elbow=_G_R["elbow"], shape="palm"), 2,
                             left=dict(pos=hs[0], fingers=hs[1], dorsum=hs[2], elbow=_G_L["elbow"], shape="palm"))
        keys.append((f, q, eases[f]))
    keys.append((15, g, "sine"))
    return keys


def guard_hit(ph):
    """El primer corte de Kaito fuera de un hueco, cuando cruza bajando de su izquierda a su derecha (el primer corte y
    el final): lo aparta sin clang (HitResult.Deflected). Se inclina hacia la hoja, la palma la encuentra a la altura del
    muslo (f3) y la acompaña hacia su derecha y abajo, lejos del cuerpo; vuelve a la guardia en f15. En la fase 1 con la
    derecha (la izquierda en la espalda), en la 2 con la izquierda (la baja, del lado por donde entra la hoja) y en la 3
    con la punta derecha del bastón, que baja a la hoja y barre. Antes la palma alzada se sacudía hacia su derecha a la
    altura de la cabeza, del otro lado de la hoja."""
    bows = [(1, 0.3, 0.0), (2, 0.75, 0.0), (SWAT_MEET, 1.0, -2.0), (5, 1.0, -9.0), (7, 0.6, -6.0), (10, 0.2, -2.0)]
    if ph == 1:
        track = [(1, "r", ((-0.38, -0.42, 1.85), (0.2, -0.6, -0.75), (-0.4, 0.3, 0.85)), None),
                 (2, "r", ((-0.15, -0.55, 1.15), (0.45, -0.85, -0.3), (0.0, 0.1, 1.0)), None),
                 (SWAT_MEET, "r", ((0.06, -0.6, 0.76), (0.55, -0.8, -0.2), (0.05, 0.05, 1.0)), None),
                 (5, "r", ((-0.28, -0.58, 0.64), (0.2, -1.0, -0.2), (-0.3, 0.1, 0.95)), None),
                 (7, "r", ((-0.44, -0.48, 0.8), (-0.2, -1.0, 0.2), (-0.6, 0.2, 0.75)), None),
                 (10, "r", ((-0.45, -0.38, 1.5), (-0.1, -0.6, 0.8), (-0.4, 0.6, 0.5)), None)]
    else:
        # fase 2: la izquierda baja encuentra la hoja y la lleva cruzando por delante; la derecha se alza un poco atrás
        rr = ((-0.5, -0.22, 2.22), _G_R["fingers"], _G_R["dorsum"])
        track = [(1, "l", ((0.36, -0.55, 1.02), (-0.1, -0.9, -0.3), (0.2, 0.1, 1.0)), rr),
                 (2, "l", ((0.18, -0.6, 0.86), (-0.25, -0.9, -0.3), (0.1, 0.05, 1.0)), rr),
                 (SWAT_MEET, "l", ((0.06, -0.6, 0.76), (-0.35, -0.9, -0.2), (0.05, 0.0, 1.0)), rr),
                 (5, "l", ((-0.12, -0.58, 0.64), (-0.6, -0.8, -0.1), (0.15, 0.0, 1.0)), rr),
                 (7, "l", ((0.0, -0.52, 0.82), (-0.4, -0.85, 0.2), (0.3, 0.2, 0.9)), rr),
                 (10, "l", ((0.32, -0.5, 1.06), (0.1, -0.7, 0.6), (0.2, 0.7, 0.6)), None)]
    staff = [(1, (0.03, -0.03, -0.32), (1.0, 0.1, 0.25)), (2, (0.06, -0.06, -0.7), (1.0, 0.15, 0.45)),
             (SWAT_MEET, (0.12, -0.08, -0.92), (1.0, 0.2, 0.5)), (5, (0.0, -0.06, -0.9), (1.0, 0.15, 0.6)),
             (7, (-0.02, -0.03, -0.6), (1.0, 0.1, 0.5)), (10, (0.0, 0.0, -0.2), (1.0, 0.1, 0.15))]
    return add("GuardHit", 15, _swat_keys(ph, track, staff, bows), ph=ph, lag={"head": 1.0},
               timing={"kind": "none", "chain_from": "GUARD", "chain_to": "GUARD", "swat_meet": SWAT_MEET},
               events=[{"frame": SWAT_MEET, "fn": "Deflect"}],
               notes="desvío del corte que cruza bajando hacia su derecha: se inclina, la palma (o el bastón) encuentra la "
                     "hoja a la altura del muslo en f3 y la acompaña hacia afuera y abajo; vuelve a la guardia en f15")


def guard_hit_l(ph):
    """El revés de Kaito (Corte 2), que sube de su derecha a su izquierda: la mano derecha (la del lado por donde entra)
    baja a la hoja a la altura de la cadera (f3) y la lleva hacia su izquierda y arriba, por delante; en la fase 3 el
    bastón la toma por arriba y la levanta. Va con GuardHit: BambooMasterBoss elige por el corte de Kaito."""
    bows = [(1, 0.25, 0.0), (2, 0.55, 2.0), (SWAT_MEET, 0.7, 4.0), (5, 0.55, 10.0), (7, 0.35, 8.0), (10, 0.1, 3.0)]
    other = None if ph == 1 else ((0.5, -0.36, 1.26), _G_L["fingers"], _G_L["dorsum"])
    track = [(1, "r", ((-0.42, -0.45, 1.8), (0.25, -0.6, -0.7), (-0.6, 0.2, 0.75)), other),
             (2, "r", ((-0.22, -0.58, 1.25), (0.5, -0.8, -0.2), (-0.6, 0.0, 0.8)), other),
             (SWAT_MEET, "r", ((-0.08, -0.64, 0.98), (0.6, -0.75, 0.1), (-0.5, 0.0, 0.85)), other),
             (5, "r", ((0.26, -0.66, 1.24), (0.5, -0.8, 0.4), (-0.6, 0.0, 0.8)), other),
             (7, "r", ((0.36, -0.55, 1.45), (0.3, -0.7, 0.65), (-0.7, 0.2, 0.6)), other),
             (10, "r", ((-0.05, -0.42, 1.85), (0.1, -0.4, 0.9), (-0.4, 0.8, 0.3)), None)]
    staff = [(1, (0.02, -0.03, -0.28), (1.0, 0.1, 0.0)), (2, (0.04, -0.07, -0.62), (1.0, 0.05, -0.1)),
             (SWAT_MEET, (0.06, -0.1, -0.82), (1.0, 0.0, -0.15)), (5, (0.18, -0.12, -0.5), (1.0, 0.05, 0.35)),
             (7, (0.12, -0.08, -0.25), (1.0, 0.1, 0.25)), (10, (0.03, -0.02, -0.1), (1.0, 0.1, 0.1))]
    return add("GuardHitL", 15, _swat_keys(ph, track, staff, bows), ph=ph, lag={"head": 1.0},
               timing={"kind": "none", "chain_from": "GUARD", "chain_to": "GUARD", "swat_meet": SWAT_MEET},
               events=[{"frame": SWAT_MEET, "fn": "Deflect"}],
               notes="desvío del revés que sube hacia su izquierda: la derecha (o el bastón) encuentra la hoja a la altura "
                     "de la cadera en f3 y la lleva hacia afuera y arriba; vuelve a la guardia en f15")


def guard_hit_low(ph):
    """El Corte final de Kaito, que llega con las dos manos en la empuñadura y la punta adelante y 17° abajo: en el
    contacto (f7, el cuadro que congela el hit-stop) la hoja cruza a 0.59 m del piso, 0.65 m adelante (0.54-0.64 m con
    Kaito de 1.6 a 1.25 m). GuardHit la encontraba a 0.76 m: la palma paraba 15-24 cm arriba de la hoja y se leía como un
    manotazo al aire (swat2.py). Es GuardHit con la reverencia más honda y la palma (o la mano baja de la fase 2, o el
    bastón) a la altura de la rodilla en f3; la acompaña hacia su derecha y abajo y vuelve a la guardia en f15. Mismos
    tiempos que GuardHit (BambooMasterBoss.PlaySwat la elige por el nombre del corte)."""
    bows = [(1, 0.35, 0.0), (2, 0.9, 0.0), (SWAT_MEET, 1.25, -2.0), (5, 1.2, -9.0), (7, 0.7, -6.0), (10, 0.25, -2.0)]
    if ph == 1:
        track = [(1, "r", ((-0.38, -0.42, 1.85), (0.2, -0.6, -0.75), (-0.4, 0.3, 0.85)), None),
                 (2, "r", ((-0.15, -0.58, 1.05), (0.45, -0.85, -0.3), (0.0, 0.1, 1.0)), None),
                 (SWAT_MEET, "r", ((0.05, -0.64, 0.65), (0.55, -0.8, -0.2), (0.05, 0.05, 1.0)), None),
                 (5, "r", ((-0.24, -0.64, 0.5), (0.2, -1.0, -0.2), (-0.3, 0.1, 0.95)), None),
                 (7, "r", ((-0.44, -0.5, 0.7), (-0.2, -1.0, 0.2), (-0.6, 0.2, 0.75)), None),
                 (10, "r", ((-0.45, -0.38, 1.5), (-0.1, -0.6, 0.8), (-0.4, 0.6, 0.5)), None)]
    else:
        rr = ((-0.5, -0.22, 2.22), _G_R["fingers"], _G_R["dorsum"])
        track = [(1, "l", ((0.36, -0.55, 0.98), (-0.1, -0.9, -0.3), (0.2, 0.1, 1.0)), rr),
                 (2, "l", ((0.18, -0.6, 0.78), (-0.25, -0.9, -0.3), (0.1, 0.05, 1.0)), rr),
                 (SWAT_MEET, "l", ((0.05, -0.64, 0.65), (-0.35, -0.9, -0.2), (0.05, 0.0, 1.0)), rr),
                 (5, "l", ((-0.1, -0.6, 0.55), (-0.6, -0.8, -0.1), (0.15, 0.0, 1.0)), rr),
                 (7, "l", ((0.0, -0.53, 0.76), (-0.4, -0.85, 0.2), (0.3, 0.2, 0.9)), rr),
                 (10, "l", ((0.32, -0.5, 1.06), (0.1, -0.7, 0.6), (0.2, 0.7, 0.6)), None)]
    staff = [(1, (0.03, -0.03, -0.34), (1.0, 0.1, 0.25)), (2, (0.06, -0.07, -0.78), (1.0, 0.15, 0.45)),
             (SWAT_MEET, (0.12, -0.1, -1.03), (1.0, 0.2, 0.5)), (5, (0.0, -0.08, -1.02), (1.0, 0.15, 0.6)),
             (7, (-0.02, -0.04, -0.66), (1.0, 0.1, 0.5)), (10, (0.0, 0.0, -0.22), (1.0, 0.1, 0.15))]
    return add("GuardHitLow", 15, _swat_keys(ph, track, staff, bows), ph=ph, lag={"head": 1.0},
               timing={"kind": "none", "chain_from": "GUARD", "chain_to": "GUARD", "swat_meet": SWAT_MEET},
               events=[{"frame": SWAT_MEET, "fn": "Deflect"}],
               notes="desvío del Corte final (la hoja baja, con las dos manos): la reverencia más honda, la palma (o el "
                     "bastón) encuentra la hoja a la altura de la rodilla en f3 y la acompaña hacia afuera y abajo; vuelve a "
                     "la guardia en f15")


C_BODY = feet(mod(G_BODY, hips=(0.03, 0.16, -0.18), hips_rot=(0.0, -2.0, -10.0), spine=(0.0, 0.0, -6.0), chest=(-2.0, 0.0, -6.0),
                  neck=(0.0, 0.0, 10.0), head=(-4.0, 0.0, 12.0), clav_r=(0.0, 6.0, -4.0)),
              r=ball(*land_xy(FOOT_R0), heel=10.0))


def coil_arms(p, ph):
    """Enroscado para pegar: la palma recogida junto a la oreja (fases 1 y 2) o el bastón recogido atrás apuntando a Kaito."""
    if ph == 3:
        # el bastón de la guardia pegado al pecho y recogido 0.35 m por su eje: la derecha (adelante) queda donde estaba y
        # el bastón se desliza en ella; la izquierda tira hacia atrás con él
        q = anchor(mod(p, **STAFF_GUARD), "staff", staff=tuple(Vector(ANCHOR["staff"]["staff_cdir"]) * 0.35))
        q["grip_r"] = STAFF_GUARD["grip_r"] - 0.35
        return q
    q = hand(p, "r", (-0.46, 0.12, 1.76), (0.0, -0.3, 1.0), (-0.3, 1.0, -0.1), elbow=(-0.5, 0.7, -0.6), shape="palm")
    return arms(q, ph, l=(-0.22, 0.12, 0.1))


def counter(ph):
    """Enemy.Counter (0.2-0.6 s): el segundo golpe contra la guardia. La mano dibuja un círculo que lleva la hoja de Kaito
    hacia afuera (o el bastón la barre), el cuerpo gira con ella y vuelve a enroscarse hacia su derecha: queda en COIL,
    de donde sale CounterStrike."""
    g = guard_arms(G_BODY, ph)
    turn = mod(G_BODY, hips_rot=(0.0, 0.0, 34.0), spine=(4.0, 0.0, 8.0), chest=(2.0, 0.0, 8.0), neck=(-2.0, 0.0, -22.0),
               head=(-6.0, 0.0, -24.0))
    if ph == 3:
        cross = staff_pose(turn, (0.08, -0.44, 1.5), (0.85, -0.45, 0.3), gr=-0.34, gl=0.34, rt=1.0, lt=-1.0)
    else:
        cross = arms(hand(turn, "r", (0.18, -0.62, 1.62), (0.9, -0.35, 0.2), (0.0, 0.3, 1.0), elbow=(-0.2, -0.3, -1.0), shape="palm"),
                     ph, l=(-0.18, 0.12, 0.05))
    coil = coil_arms(C_BODY, ph)
    CHAIN.setdefault("COIL", {})[ph] = coil
    POSES[f"enroscado {ph}"] = coil
    mid = mix(cross, coil, 0.55)
    return add("Counter", 16, [(0, g, "lin"), (3, cross, "out"), (8, mid, "inout"), (13, coil, "inout"), (16, coil, "sine")], ph=ph,
               timing={"kind": "none", "deflect": 3, "chain_from": "GUARD", "chain_to": "COIL"}, events=[{"frame": 2, "fn": "Deflect"}],
               notes="desvío circular (la hoja de Kaito sale hacia la izquierda del maestro en f2-3) y se enrosca: termina en "
                     "COIL para el golpe del contraataque (CounterStrike)")


# ============================================================================ reacciones
def _feet0():
    (rx, ry, _), (_, _, ryaw), _ = FOOT_R0
    (lx, ly, _), (_, _, lyaw), _ = FOOT_L0
    return rx, ry, ryaw, lx, ly, lyaw


def hit(ph):
    """Golpe liviano (Enemy.ReceiveHit 'Hit'): el pecho y la cabeza se van atrás, la mano de guardia salta hacia la cara y
    el cuerpo retrocede knock_m con la curva de Enemy.knock: el pie de atrás se acomoda primero y el de adelante lo sigue."""
    K = 0.12
    A = lambda p, **o: arms(p, ph, right=True, **o)
    snap = A(mod(BODY, hips=(0.02, 0.1, -0.1), hips_rot=(-4.0, 2.0, 16.0), spine=(-8.0, 2.0, 2.0), chest=(-6.0, 0.0, 2.0),
                 neck=(-4.0, 0.0, -8.0), head=(-15.0, 4.0, -9.0), travel=knock(2, K)),
             r=(0.02, 0.05, -0.07), l=(-0.03, 0.05, -0.06), staff=(0.0, 0.04, -0.06))
    reb = A(mod(BODY, hips=(0.02, 0.08, -0.1), spine=(-1.0, 0.0, 3.0), head=(-7.0, 0.0, -11.0), travel=knock(6, K)), r=(0.0, 0.01, 0.0))
    near = A(mod(BODY, hips=(0.02, 0.065, -0.085), travel=knock(10, K)))
    end = A(at_travel(BODY, -K))
    rx, ry, ryaw, lx, ly, lyaw = _feet0()
    R1, L1 = flat(rx, ry + K, ryaw), flat(lx, ly + K, lyaw)
    st = [(0, {"r": FOOT_R0, "l": FOOT_L0}, "lin"), (1, {"r": FOOT_R0, "l": FOOT_L0}, "lin"),
          (3, {"r": FOOT_R0, "l": air(lx, ly + 0.07, AZ + 0.04, yaw=lyaw)}, "out2"), (5, {"r": FOOT_R0, "l": L1}, "in2"),
          (6, {"r": FOOT_R0, "l": L1}, "lin"), (8, {"r": air(rx, ry + 0.07, AZ + 0.035, yaw=ryaw), "l": L1}, "out2"),
          (10, {"r": R1, "l": L1}, "in2"), (18, {"r": R1, "l": L1}, "lin")]
    return add("Hit", 18, [(0, A(BODY), "lin"), (2, snap, "snap", {"travel": "lin"}), (6, reb, "out", {"travel": "lin"}),
                           (10, near, "sine", {"travel": "lin"}), (18, end, "sine", {"travel": "out2"})], ph=ph,
               lag={"head": 1.0, "neck": 0.5}, steps=st,
               timing={"kind": "none", "knock_m": K, "knock_curve": "1 - exp(-10 t)", "recover": [0, 18], "chain_from": "READY",
                       "chain_to": "READY"},
               notes="reacción liviana: retrocede knock_m (0.12 m) con la curva de Enemy.knock; el pie de atrás se acomoda en "
                     "f1-5 y el de adelante en f6-10. El juego tiene que empujarlo eso (knockbackResist del jefe)")


def hit_heavy(ph):
    """Golpe fuerte (corte final, habilidades: 'HitHeavy'): se dobla sobre el estómago y retrocede un paso entero."""
    K = 0.42
    A = lambda p, **o: arms(p, ph, right=True, **o)
    k = 0.55 if ph == 3 else 1.0
    fold = A(mod(BODY, hips=(0.03, 0.16, -0.16), hips_rot=(6.0 * k, -2.0, 10.0), spine=(18.0 * k, -2.0, 0.0), chest=(10.0 * k, 0.0, 0.0),
                 neck=(6.0 * k, 0.0, -6.0), head=(-6.0, 0.0, -6.0), travel=knock(3, K)),
             r=(0.06, -0.12, -0.08), l=(-0.08, -0.1, -0.04), staff=(0.0, -0.02, 0.05))
    reel = A(mod(BODY, hips=(0.02, 0.14, -0.14), hips_rot=(-2.0, 2.0, 16.0), spine=(-4.0, 2.0, 4.0), chest=(-8.0, 0.0, 4.0),
                 neck=(-6.0, 0.0, -10.0), head=(-14.0, 3.0, -10.0), travel=knock(8, K)), r=(0.02, 0.06, -0.06), l=(0.0, 0.05, -0.05),
             staff=(0.0, 0.05, -0.04))
    gather = A(mod(BODY, hips=(0.02, 0.09, -0.11), spine=(2.0, 0.0, 4.0), head=(-7.0, 0.0, -11.0), travel=knock(14, K)))
    end = A(at_travel(BODY, -K))
    rx, ry, ryaw, lx, ly, lyaw = _feet0()
    R1, L1 = flat(rx, ry + K, ryaw), flat(lx, ly + K, lyaw)
    st = [(0, {"r": FOOT_R0, "l": FOOT_L0}, "lin"), (2, {"r": FOOT_R0, "l": FOOT_L0}, "lin"),
          (5, {"r": FOOT_R0, "l": air(lx, ly + 0.22, AZ + 0.07, pitch=-6.0, yaw=lyaw)}, "out2"),
          (8, {"r": ball(*land_xy(FOOT_R0), heel=12.0), "l": L1}, "in2"),
          (11, {"r": air(rx, ry + 0.24, AZ + 0.08, pitch=-8.0, yaw=ryaw), "l": L1}, "out2"), (14, {"r": R1, "l": L1}, "in2"),
          (27, {"r": R1, "l": L1}, "lin")]
    return add("HitHeavy", 27, [(0, A(BODY), "lin"), (3, fold, "snap", {"travel": "lin"}), (8, reel, "inout", {"travel": "lin"}),
                                (14, gather, "inout", {"travel": "lin"}), (27, end, "sine", {"travel": "out2"})], ph=ph,
               lag={"head": 1.5, "neck": 0.8}, steps=st,
               timing={"kind": "none", "knock_m": K, "knock_curve": "1 - exp(-10 t)", "recover": [0, 27], "chain_from": "READY",
                       "chain_to": "READY"},
               notes="golpe fuerte: se dobla (f3), se endereza tambaleando y da un paso atrás entero (knock_m 0.42: el de atrás "
                     "en f2-8, el de adelante en f8-14)")


def _parried(ph, name, K, frames, resume, big):
    """El parry de Kaito le saca el brazo del golpe hacia arriba y afuera, la cabeza atrás, y lo empuja K metros (Enemy:
    0.4 el normal, 0.8 el perfecto) con la curva de Enemy.knock; en 'resume' ya está en guardia para seguir el combo."""
    s = 1.0 if not big else 1.5
    A = lambda p, **o: arms(p, ph, right=True, **o)
    if ph == 3:
        def fling(p, w):
            return arms(p, 3, staff=(0.0, 0.16 * w, 0.06 * w))
    else:
        def fling(p, w):
            # la palma del golpe sale hacia arriba y afuera (anclada al pecho: acompaña el arco de la espalda)
            return arms(p, ph, right=True, r=(-0.2 * w, 0.3 * w, -0.24 * w), l=(0.04 * w, 0.06 * w, -0.08 * w))
    fr = round(resume * 0.4)
    hit_ = fling(mod(BODY, hips=(0.02, 0.13 + 0.04 * s, -0.12), hips_rot=(-6.0 * s, 2.0, 2.0), spine=(-10.0 * s, 2.0, -4.0),
                     chest=(-8.0 * s, 0.0, -2.0), neck=(-6.0, 0.0, -2.0), head=(-16.0 - 6.0 * s, 4.0, -4.0), travel=knock(2, K)), s)
    rock = fling(mod(BODY, hips=(0.02, 0.17 + 0.05 * s, -0.15), hips_rot=(-8.0 * s, 2.0, 4.0), spine=(-12.0 * s, 2.0, -2.0),
                     chest=(-8.0 * s, 0.0, 0.0), neck=(-6.0, 0.0, -4.0), head=(-18.0 - 6.0 * s, 4.0, -6.0), travel=knock(fr, K)),
                 s * 1.05)
    rec = A(mod(BODY, hips=(0.02, 0.09, -0.11), spine=(1.0, 0.0, 3.0), head=(-8.0, 0.0, -11.0), travel=knock(resume, K)))
    end = A(at_travel(BODY, -K))
    rx, ry, ryaw, lx, ly, lyaw = _feet0()
    R1, L1 = flat(rx, ry + K, ryaw), flat(lx, ly + K, lyaw)
    if not big:
        # 0.4 m: el de atrás retrocede primero (f1-5) y el de adelante lo sigue (f5-12)
        f2 = round(resume * 0.45)
        st = [(0, {"r": FOOT_R0, "l": FOOT_L0}, "lin"), (1, {"r": FOOT_R0, "l": FOOT_L0}, "lin"),
              (3, {"r": FOOT_R0, "l": air(lx, ly + K * 0.5, AZ + 0.06, pitch=-8.0, yaw=lyaw)}, "out2"),
              (f2, {"r": heel(*land_xy(FOOT_R0), toe_up=10.0), "l": L1}, "in2"),
              (f2 + 2, {"r": air(rx, ry + K * 0.45, AZ + 0.06, pitch=-6.0, yaw=ryaw), "l": L1}, "out2"),
              (round(resume * 0.8) + 2, {"r": R1, "l": L1}, "in2"), (frames, {"r": R1, "l": L1}, "lin")]
    else:
        # 0.8 m: el empujón lo hace saltar hacia atrás (los dos pies dejan el piso en f2-4) y el de atrás se vuelve a
        # acomodar en f8-12; antes el de adelante quedaba clavado y la pierna no llegaba
        f2 = 6
        Lh = flat(lx, ly + 0.45, lyaw)
        st = [(0, {"r": FOOT_R0, "l": FOOT_L0}, "lin"), (1, {"r": FOOT_R0, "l": FOOT_L0}, "lin"),
              (2, {"r": ball(*land_xy(FOOT_R0), heel=18.0), "l": air(lx, ly + 0.16, AZ + 0.07, pitch=-8.0, yaw=lyaw)}, "out2"),
              (4, {"r": air(rx, ry + 0.38, AZ + 0.12, pitch=-10.0, yaw=ryaw), "l": Lh}, "in2"),
              (6, {"r": R1, "l": Lh}, "in2"), (8, {"r": R1, "l": Lh}, "lin"),
              (10, {"r": R1, "l": air(lx, ly + 0.64, AZ + 0.05, pitch=-6.0, yaw=lyaw)}, "out2"),
              (12, {"r": R1, "l": L1}, "in2"), (frames, {"r": R1, "l": L1}, "lin")]
    return add(name, frames, [(0, A(BODY), "lin"), (2, hit_, "snap", {"travel": "lin"}), (fr, rock, "out", {"travel": "lin"}),
                              (resume, rec, "inout", {"travel": "lin"}), (frames, end, "sine", {"travel": "out2"})], ph=ph,
               lag={"head": 2.0, "neck": 1.0}, steps=st,
               timing={"kind": "none", "knock_m": K, "knock_curve": "1 - exp(-10 t)", "recover": [0, frames], "resume": resume,
                       "chain_to": "READY"},
               events=[{"frame": 0, "fn": "Parried"}, {"frame": f2, "fn": "Step"}],
               notes=f"le desviaron el golpe: el brazo sale arriba y afuera y retrocede knock_m ({K} m) con la curva de "
                     f"Enemy.knock (Enemy.OnParried empuja {K}); en f{resume} ya está en guardia (el combo puede seguir)")


def parried(ph):
    return _parried(ph, "Parried", 0.4, 30, 12, False)


def parried_perfect(ph):
    return _parried(ph, "ParriedPerfect", 0.8, 36, 18, True)


# ============================================================================ más golpes de la fase 1 (y su variante 2)
def shorten(p, k):
    """La pose de golpe de una variante de paso corto (k = fracción del paso): el cuerpo más alto y menos volcado y la
    mano (o las dos) más cerca: con el paso corto la palma no llega a donde llegaba con la estocada entera."""
    if k >= 0.999:
        return p
    q = mod(p)
    u = 1.0 - k
    q["hips"] = tuple(Vector(p["hips"]) + Vector((0.01, 0.11, 0.1)) * u)
    for ch in ("spine", "hips_rot"):
        x = p.get(ch)
        if x is not None:
            q[ch] = (x[0] * (1.0 - 0.4 * u), x[1], x[2])
    q["hand_r"] = tuple(Vector(p["hand_r"]) + Vector((0.0, 0.2, 0.06)) * u)
    left = p.get("_left_p2")
    if left:
        q["_left_p2"] = dict(left, pos=tuple(Vector(left["pos"]) + Vector((0.0, 0.2, 0.06)) * u))
    return q


def _step_in(ph, frames, apex_f, contact_f, coil, strike, over, travel, glow, strike_pt, name, notes, events_extra=(),
             variant=True, var=None):
    """Golpe con paso adelante: el pie de adelante se clava en el impacto 'travel' m más adelante y el de atrás alcanza
    en la recuperación (las mismas reglas del tui zhang, con sus pistas de pies). var = variante de paso corto (Mid,
    Close): el mismo golpe hasta la suelta y un paso de REACH_K del autorado."""
    A = lambda p: arms(p, ph, left=p.get("_left_p2"))
    k = 1.0 if var is None else REACH_K[var]
    T = travel * k
    strike, over = shorten(strike, k), shorten(over, k)
    hold = mod(coil, hips=tuple(Vector(coil["hips"]) + Vector((0.0, 0.01, -0.01))))
    if coil.get("_left_p2"):
        hold["_left_p2"] = dict(coil["_left_p2"])
    drive = mix(coil, strike, 0.35)
    drive["_left_p2"] = coil.get("_left_p2")
    drive["travel"] = T * 0.28
    strike = mod(strike, travel=T * 0.62)
    over = mod(over, travel=T * 0.86)
    rec_a = mod(R0, hips=lerp3((0.02, 0.05, -0.2), (0.0, -0.02, -0.26), k), hips_rot=(3.0, 0.0, 14.0), spine=(6.0, 0.0, 6.0),
                chest=(2.0, 0.0, 4.0), neck=(-3.0, 0.0, -10.0), head=(-7.0, 0.0, -12.0),
                hand_r=lerp3((-0.2, -0.6, 1.66), (-0.2, -0.7, 1.62), k), hand_r_dir=n(0.05, -0.3, 1.0), hand_r_up=n(-0.2, 1.0, 0.2),
                travel=T * 0.96)
    rec_b = mod(at_travel(R0, T), hips=(0.02, 0.04, -0.12), hand_r=(-0.24, -0.52, 1.8))
    c = contact_f
    pre = mix(R0, coil, 0.45)
    pre["_left_p2"] = coil.get("_left_p2")
    keys = [(round(apex_f * 0.45), pre, "inout"), (apex_f, coil, "inout"),
            (apex_f + 2, hold, "sine", {"stop": tuple(hold)}),
            (c - 2, drive, "in2", {"travel": "lin"}), (c, strike, "expo_in", {"travel": "lin"}),
            (c + 2, over, "out", {"travel": "out2"}), (c + 6, rec_a, "inout", {"travel": "out2"}),
            (c + 11, rec_b, "inout")]
    RX, RY, RYAW = land_xy(RF0)
    LX, LY, LYAW = land_xy(LF0)
    front = [(round(apex_f * 0.45), ball(RX, RY, RYAW, heel=5.0), "inout"), (apex_f, ball(RX, RY, RYAW, heel=10.0), "inout"),
             (apex_f + 2, ball(RX, RY, RYAW, heel=10.0), "sine")] + front_step(c, T)
    back = [(apex_f + 2, flat(LX, LY, LYAW), "lin"), (c - 2, ball(LX, LY, LYAW, heel=16.0), "in2")] + follow_step(c, T, frames)
    nm = name if var is None else name + "_" + var
    t = {"tell": [0, apex_f], "apex": apex_f, "hold": [apex_f, apex_f + 2], "contact": c, "active": [c, c + 2],
         "recover": [c + 2, frames], "lunge": [c - 3, c + 11, T], "kind": GOLD, "glow": glow, "strike": strike_pt,
         "chain_from": "READY", "chain_to": "READY"}
    if var is None:
        t["reach_variants"] = reach_names(name, ph) if variant else [name + "_" + v for v in REACH_K]
    return add(nm, frames, framed(ph, [(k_[0], A(k_[1])) + tuple(k_[2:]) for k_ in keys], frames, T), ph=ph,
               steps=feet_track(front, back, frames), timing=t,
               events=[{"frame": apex_f, "fn": "Apex"}, {"frame": c, "fn": "Strike"}, {"frame": c - 1, "fn": "Step"},
                       {"frame": c + 9, "fn": "Step"}] + list(events_extra),
               notes=notes + ("" if var is None else ". Variante de paso corto de " + name + " (la elige el jefe en la suelta)"),
               variant=variant)


def chop(ph):
    """Pi zhang (la palma que parte), dorado: el AVISO es el brazo derecho alzado por encima y detrás de la cabeza, el cuerpo
    estirado sobre la pierna de atrás (desde arriba la silueta se alarga hacia atrás); baja cortando con el filo de la mano
    a la altura del hombro de Kaito mientras el pie de adelante se clava."""
    coil = mod(R0, hips=(0.03, 0.13, -0.05), hips_rot=(-3.0, 0.0, 4.0), spine=(-6.0, 0.0, 0.0), chest=(-5.0, 0.0, 2.0),
               neck=(-2.0, 0.0, -2.0), head=(-2.0, 0.0, -4.0), clav_r=(0.0, 12.0, 0.0),
               hand_r=(-0.22, 0.1, 2.78), hand_r_dir=n(0.05, 0.4, 1.0), hand_r_up=n(-1.0, 0.0, 0.1), elbow_r=(-0.7, 0.2, 0.6),
               knee_l=(0.5, -1.0, 0.0))
    strike = mod(R0, hips=(0.0, -0.04, -0.34), hips_rot=(10.0, 0.0, 16.0), spine=(22.0, 0.0, 6.0), chest=(10.0, 0.0, 4.0),
                 neck=(-8.0, 0.0, -12.0), head=(-14.0, 0.0, -14.0), clav_r=(0.0, -4.0, 6.0),
                 hand_r=(-0.08, -1.2, 1.38), hand_r_dir=n(0.0, -1.0, -0.3), hand_r_up=n(-1.0, 0.0, 0.15), elbow_r=(-0.6, 0.2, -0.6))
    over = mod(strike, hips=(0.0, -0.08, -0.38), spine=(26.0, 0.0, 6.0), hand_r=(-0.06, -1.24, 1.08), hand_r_dir=n(0.0, -0.8, -0.6))
    POSES[f"tajo aviso {ph}"] = arms(coil, ph)
    for var in (None,) + tuple(REACH_K):
        _step_in(ph, 36, 11, 17, coil, strike, over, 0.9, "Master_GlintHandR", PALM_R, "ChopPalm",
                 "pi zhang: el brazo alzado detrás de la cabeza (aviso f11) baja cortando con el filo de la mano (f17) "
                 "mientras el pie de adelante se clava a 0.9 m", var=var)


TOE_R = ("Toe_R", (0.0, 0.12, 0.0))
TOE_TIP_L = ("Toe_L", (0.0, 0.12, 0.0))


def _wings(p, ph, r_pos, l_pos, fingers_r=(-0.2, 0.1, -1.0), up_r=(-0.6, 0.0, 0.5)):
    """Las alas de la grulla: el brazo derecho abierto con la mano en pico (y el izquierdo en la fase 2)."""
    q = hand(p, "r", r_pos, fingers_r, up_r, elbow=(-0.1, 0.6, -0.8), shape="beak")
    left = dict(pos=l_pos, fingers=(-fingers_r[0], fingers_r[1], fingers_r[2]), dorsum=(-up_r[0], up_r[1], up_r[2]),
                elbow=(0.1, 0.6, -0.8), shape="beak")
    q["_left_p2"] = left
    return q


def crane(ph):
    """Patada de grulla, dorada. AVISO: parado sobre la pierna de atrás con la rodilla derecha arriba, el pie colgando
    en punta y los brazos abiertos como alas con las manos en pico (desde arriba: una cruz). Patea de frente al pecho de
    Kaito con la punta estirada, vuelve a recoger la pierna y la apoya adelante."""
    A = lambda p: arms(p, ph, left=p.get("_left_p2"))
    LX, LY, LYAW = land_xy(LF0)
    shift = feet(_wings(mod(R0, hips=(0.1, 0.14, -0.09), hips_rot=(0.0, -2.0, 10.0), spine=(2.0, -2.0, 2.0), chest=(1.0, 0.0, 2.0),
                            neck=(-1.0, 0.0, -6.0), head=(-3.0, 0.0, -6.0)), ph, (-0.62, -0.2, 1.75), (0.62, -0.2, 1.75)),
                 r=ball(*land_xy(RF0), heel=18.0))
    crane_ = feet(_wings(mod(R0, hips=(0.16, 0.17, -0.06), hips_rot=(-4.0, -5.0, 6.0), spine=(3.0, -2.0, 0.0), chest=(2.0, 2.0, 2.0),
                             neck=(2.0, 0.0, -4.0), head=(4.0, 0.0, -4.0), knee_l=(0.3, -1.0, 0.0), knee_r=(0.0, -1.0, 0.7)),
                         ph, (-0.92, 0.0, 2.0), (0.92, 0.0, 2.0)),
                  r=air(-0.02, -0.28, 0.8, pitch=58.0, yaw=0.0, toe=-12.0))
    POSES[f"grulla aviso {ph}"] = A(crane_)
    hold = mod(crane_, hips=(0.165, 0.175, -0.055), foot_r=(-0.02, -0.29, 0.81))
    chamber = feet(mod(crane_, hips=(0.15, 0.16, -0.06), hips_rot=(-8.0, -4.0, 6.0), spine=(0.0, 0.0, 0.0),
                       knee_r=(0.0, -1.0, 0.4)), r=air(-0.04, -0.55, 1.0, pitch=10.0, toe=-16.0))
    kick = feet(_wings(mod(R0, hips=(0.13, 0.12, -0.08), hips_rot=(-14.0, -3.0, 4.0), spine=(-6.0, 0.0, 0.0), chest=(2.0, 0.0, 0.0),
                           neck=(4.0, 0.0, -4.0), head=(6.0, 0.0, -4.0), knee_l=(0.3, -1.0, 0.0), knee_r=(0.0, 0.0, 1.0)),
                       ph, (-0.86, 0.32, 1.86), (0.86, 0.32, 1.86)),
                r=air(-0.08, -0.98, 1.12, pitch=-30.0, toe=-22.0))
    over = feet(mod(kick, hips=(0.13, 0.11, -0.08)), r=air(-0.08, -1.0, 1.16, pitch=-30.0, toe=-24.0))
    retract = feet(mod(chamber, hips=(0.12, 0.08, -0.1), hips_rot=(-4.0, -2.0, 8.0)), r=air(-0.1, -0.62, 0.6, pitch=30.0, toe=-8.0))
    T = 0.45
    land = feet(mod(R0, hips=(0.04, -0.02, -0.2), hips_rot=(4.0, 0.0, 12.0), spine=(6.0, 0.0, 4.0), travel=0.12,
                    hand_r=(-0.4, -0.35, 1.8), hand_r_dir=n(0.0, -0.3, 1.0), hand_r_up=n(-0.3, 1.0, 0.0)),
                r=flat(-0.2, RF0[0][1] - T, 0.0), l=ball(LX, LY, LYAW, heel=20.0))
    follow = feet(mod(at_travel(R0, 0.4), hips=(0.02, 0.02, -0.14)), r=flat(-0.2, RF0[0][1] - T, 2.0),
                  l=air(0.27, LY - 0.25, 0.16, pitch=-8.0, yaw=26.0))
    end = at_travel(R0, T)
    keys = [(0, ready(ph), "sine"), (6, shift, "inout"), (13, crane_, "inout", {"foot_r": "inout"}), (15, hold, "sine"),
            (16, chamber, "in2"), (18, kick, "expo_in"), (20, over, "out"), (24, retract, "inout"),
            (28, land, "in2", {"foot_r": "in2"}), (34, follow, "inout", {"travel": "inout"}),
            (37, feet(mod(at_travel(R0, T), hips=(0.02, 0.05, -0.1)), l=flat(LX, LY - T, LYAW)), "inout"), (42, ready(ph, T), "sine")]
    # el de apoyo alcanza con el paso de seguimiento (bajaba todavía corriéndose: la suela se arrastraba 14 cm)
    back = [(24, flat(LX, LY, LYAW), "lin"), (28, ball(LX, LY, LYAW, heel=20.0), "inout")] + follow_step(28, T, 42)[1:]
    return add("CraneKick", 42, [(k[0], A(k[1])) + tuple(k[2:]) for k in keys], ph=ph, steps=foot_track("l", back, 42, LF0),
               timing={"tell": [0, 13], "apex": 13, "hold": [13, 15], "contact": 18, "active": [18, 20], "recover": [20, 42],
                       "lunge": [28, 37, T], "kind": GOLD, "glow": "Master_GlintFootR", "strike": TOE_R, "tip_ratio_max": 0.45,
                       "chain_from": "READY", "chain_to": "READY"},
               events=[{"frame": 13, "fn": "Apex"}, {"frame": 18, "fn": "Strike"}, {"frame": 28, "fn": "Step"},
                       {"frame": 36, "fn": "Step"}],
               notes="grulla: rodilla arriba y alas abiertas (aviso f13), patada de frente con la punta (f18), recoge la "
                     "pierna y la apoya adelante (f28); avanza 0.45 m después de apoyar")


def smooth(a, b, x):
    """0 antes de a, 1 después de b, suave entre medio."""
    u = max(0.0, min(1.0, (x - a) / (b - a)))
    return u * u * (3.0 - 2.0 * u)


def leap(ph):
    """Grulla voladora, ROJA (imparable) con marca en el piso. AVISO: se agacha hondo con los brazos atrás (desde arriba la
    silueta se achica y los brazos salen por atrás) y salta: sube recogido, arriba abre las alas (los brazos bien
    abiertos) con la rodilla derecha montada contra el pecho, y desde ahí estira la pierna hacia adelante y abajo (la
    patada que cae: el talón primero) mientras las alas se van atrás y la otra pierna queda recogida atrás. Cae con el
    pie derecho sobre la marca, se clava agachado (4 cuadros quieto con el polvo) y se levanta. El vuelo es parabólico EN
    EL RELOJ DEL JUEGO (la suelta se toca con u², StepTimeline: el clip lleva el avance y la altura remapeados con la
    raíz) y va en el espacio del personaje: del pie que empuja (timing.air[0]) al que cae (air[1]) el juego escala el
    avance para caer donde está Kaito sin que los pies patinen (marker_m es la distancia de la marca autorada). Antes
    subía 0.9 m con la pierna recogida y solo la estiraba al caer: se leía como un saltito con pisotón."""
    A = lambda p: arms(p, ph, left=p.get("_left_p2"))
    LX, LY, LYAW = land_xy(LF0)
    RX, RY, RYAW = land_xy(RF0)
    APEX, TAKE, LAND, N = 19, 21, 33, 56
    PUSH, AIR_D, H = 0.15, 4.4, 1.35
    T_LAND = PUSH + AIR_D
    RR = 0.6
    crouch = feet(_wings(mod(R0, hips=(0.0, 0.07, -0.46), hips_rot=(14.0, 0.0, 10.0), spine=(20.0, 0.0, 2.0), chest=(8.0, 0.0, 0.0),
                             neck=(-12.0, 0.0, -6.0), head=(-18.0, 0.0, -6.0), knee_r=(-0.3, -1.0, 0.0), knee_l=(0.5, -1.0, 0.0)),
                         ph, (-0.55, 0.5, 1.3), (0.55, 0.5, 1.3), fingers_r=(-0.2, 0.6, -0.8), up_r=(-0.3, -0.3, 0.9)),
                  r=flat(RX, RY, RYAW), l=flat(LX, LY, LYAW))
    POSES[f"salto aviso {ph}"] = A(crouch)
    pre = mix(R0, crouch, 0.5)
    pre["_left_p2"] = crouch["_left_p2"]
    hold = mod(crouch, hips=(0.0, 0.08, -0.48), head=(-19.0, 0.0, -6.0))
    hold["_left_p2"] = dict(crouch["_left_p2"])
    push = feet(_wings(mod(crouch, hips=(0.0, -0.06, -0.2), hips_rot=(10.0, 0.0, 8.0), spine=(12.0, 0.0, 2.0), head=(-12.0, 0.0, -6.0),
                           travel=PUSH), ph, (-0.62, 0.36, 1.62), (0.62, 0.36, 1.62), fingers_r=(-0.3, 0.5, -0.6), up_r=(-0.4, -0.2, 0.9)),
                r=ball(RX, RY, RYAW, heel=45.0), l=ball(LX, LY, LYAW, heel=50.0))
    # los pies empujan rodando sobre la bola con los dedos planos (de plano a punta, mezclado, la punta se corría 2.7 cm)
    roll = feet(mix(hold, push, 0.45), r=ball(RX, RY, RYAW, heel=22.0), l=ball(LX, LY, LYAW, heel=24.0))
    roll["travel"] = 0.0
    roll["_left_p2"] = dict(push["_left_p2"])

    def flight(w):
        """Pose del vuelo a la fracción w del tiempo de vuelo (en el reloj del juego)."""
        trv = PUSH + AIR_D * w
        z = H * 4.0 * w * (1.0 - w)
        tuck = smooth(0.0, 0.3, w)                    # sube recogido
        cham = smooth(0.2, 0.45, w) * (1.0 - smooth(0.6, 0.78, w))   # rodilla montada arriba
        ext = smooth(0.55, 0.82, w)                   # la patada que se estira hacia adelante y abajo
        land = smooth(0.84, 1.0, w)                   # baja a la marca
        wing = smooth(0.15, 0.45, w)                  # las alas se abren
        back = smooth(0.55, 0.85, w)                  # y se van atrás con la patada
        # el pie derecho en el espacio del personaje: recogido, montado arriba, estirado adelante y abajo, y a la marca
        fr = Vector((-0.12, -0.2, 0.62)).lerp(Vector((-0.1, -0.32, 1.02)), cham)
        fr = fr.lerp(Vector((-0.17, -0.98, 0.5)), ext).lerp(Vector((RX, RY - 0.06, AZ + 0.1)), land)
        fl = Vector((0.2, 0.3, 0.72)).lerp(Vector((0.24, 0.6, 0.62)), ext).lerp(Vector((0.25, 0.36, 0.42)), land)
        hz = -0.12 + z - 0.2 * land
        lean = -12.0 * ext + 14.0 * land              # se echa atrás para estirar la patada; al caer se vuelca adelante
        p = _wings(mod(R0, hips=(0.0, -0.04 + 0.08 * ext, hz), hips_rot=(4.0 + lean * 0.6, 0.0, 8.0),
                       spine=(10.0 * tuck * (1.0 - ext) + lean * 0.5, 0.0, 2.0), chest=(2.0 + lean * 0.3, 0.0, 0.0),
                       neck=(-6.0 + 8.0 * ext, 0.0, -6.0), head=(-12.0 + 10.0 * ext + 8.0 * land, 0.0, -6.0),
                       knee_r=(0.0, -1.0, 0.5), knee_l=(0.2, -1.0, 0.3), travel=trv),
                   ph, (-0.62 - 0.25 * wing, 0.36 + 0.1 * back, 1.62 + z + 0.12 * wing - 0.18 * back - 0.14 * land),
                   (0.62 + 0.25 * wing, 0.36 + 0.1 * back, 1.62 + z + 0.12 * wing - 0.18 * back - 0.14 * land),
                   fingers_r=(-0.5 - 0.3 * wing, 0.4 + 0.3 * back, -0.6 + 0.4 * wing), up_r=(-0.4, -0.2, 0.9))
        # el talón primero: la punta arriba en la patada, plana al caer
        return feet(p, r=air(fr.x, fr.y - trv, fr.z + z, pitch=24.0 * (1.0 - ext) - 34.0 * ext * (1.0 - land) - 6.0 * land,
                             toe=-10.0 * ext * (1.0 - land)),
                    l=air(fl.x, fl.y - trv, fl.z + z, pitch=40.0 - 10.0 * ext, toe=-6.0))
    # cuadros del clip -> fracción del vuelo: en la suelta el clip avanza como u² del tiempo (StepTimeline)
    u0 = math.sqrt((TAKE - APEX) / (LAND - APEX))
    air_keys = []
    for f in range(TAKE + 1, LAND):
        u = math.sqrt((f - APEX) / (LAND - APEX))
        air_keys.append((f, flight((u - u0) / (1.0 - u0)), "lin"))
    land = feet(_wings(mod(R0, hips=(-0.02, -0.12, -0.52), hips_rot=(16.0, 0.0, 12.0), spine=(22.0, 0.0, 4.0), chest=(8.0, 0.0, 2.0),
                           neck=(-10.0, 0.0, -8.0), head=(-14.0, 0.0, -8.0), knee_r=(-0.3, -1.0, 0.2), travel=T_LAND),
                       ph, (-0.74, 0.12, 1.38), (0.74, 0.12, 1.38), fingers_r=(-0.6, 0.4, -0.6), up_r=(-0.5, 0.0, 0.8)),
                r=flat(RX, RY - T_LAND, RYAW), l=air(LX, LY - T_LAND + 0.08, 0.3, pitch=10.0, yaw=LYAW))
    absorb = feet(mod(land, hips=(-0.02, -0.06, -0.56), spine=(26.0, 0.0, 4.0)), l=flat(LX, LY - T_LAND, LYAW))
    absorb["_left_p2"] = dict(land["_left_p2"])
    # se queda clavado agachado con las alas abiertas (lo que se lee del golpe: el polvo y la pose quieta)
    held = mod(absorb, hips=(-0.02, -0.055, -0.555), head=(-13.0, 0.0, -8.0))
    held["_left_p2"] = dict(land["_left_p2"])
    rise = mod(at_travel(R0, T_LAND), hips=(0.02, 0.02, -0.22), spine=(8.0, 0.0, 4.0), hand_r=(-0.4, -0.3, 1.7))
    keys = [(8, pre, "inout"), (16, crouch, "inout"), (APEX, hold, "sine"), (20, roll, "in2"), (TAKE, push, "in2", {"travel": "lin"})]
    keys += air_keys
    keys += [(LAND, land, "lin", {"foot_r": "lin"}), (36, absorb, "out"), (40, held, "sine"), (49, rise, "inout")]
    # el pie de atrás baja detrás después de la caída: encima de su lugar y recién ahí apoya
    l_air = land["foot_l"], land["foot_l_rot"], land.get("toe_l", 0.0)
    back = [(LAND, l_air, "lin"), (35, air(LX, LY - T_LAND, AZ + 0.04, pitch=-2.0, yaw=LYAW), "out"),
            (36, flat(LX, LY - T_LAND, LYAW), "in2"), (N, flat(LX, LY - T_LAND, LYAW), "lin")]
    steps = [st for st in foot_track("l", back, N, l_air) if st[0] >= LAND]
    return add("LeapKick", N, framed(ph, [(k[0], A(k[1])) + tuple(k[2:]) for k in keys], N, T_LAND), ph=ph, steps=steps,
               timing={"tell": [0, APEX], "apex": APEX, "hold": [16, APEX], "contact": LAND, "active": [LAND, LAND + 3],
                       "recover": [LAND + 3, N], "lunge": [APEX, LAND, T_LAND], "air": [TAKE, LAND], "release_rate": RR,
                       "root_max": 16.0, "kind": RED, "glow": "Master_GlintFootR", "strike": ("Foot_R", (0.0, 0.0, 0.0)),
                       "marker_m": round(T_LAND - RY, 2), "ring_m": 1.8, "spin": True, "chain_from": "READY", "chain_to": "READY",
                       "height_cap": 4.0},
               events=[{"frame": APEX, "fn": "Apex"}, {"frame": TAKE, "fn": "TakeOff"}, {"frame": LAND, "fn": "Strike"},
                       {"frame": LAND, "fn": "Land"}, {"frame": 36, "fn": "Step"}],
               notes=f"se agacha (aviso rojo f{APEX}), salta en f{TAKE}, arriba abre las alas con la rodilla montada y estira la "
                     f"patada hacia abajo; cae sobre la marca en f{LAND} a marker_m del transform inicial (el pie derecho) y se "
                     f"queda clavado hasta f40. AttackDef.releaseRate = {RR}: el vuelo dura ~0.5 s; el juego escala el avance "
                     f"de timing.air (del despegue a la caída) para caer donde está Kaito (onda de ring_m al caer)")


RED_ = RED


def counter_strike(ph, var=None):
    """El golpe del contraataque desde COIL: rápido (Enemy lo toca con el windup mínimo de contraataque, 0.5 s) y corto;
    dorado. Fase 3: la estocada del bastón desde el bastón recogido. El contragolpe sale casi siempre a quemarropa (Kaito
    acaba de pegarle): las variantes de paso corto (var) son las que más se usan."""
    coil = CHAIN["COIL"][ph]
    k = 1.0 if var is None else REACH_K[var]
    T = 0.6 * k
    RX, RY, RYAW = land_xy(RF0)
    LX, LY, LYAW = land_xy(LF0)
    if ph == 3:
        a = Vector(n(0.14, 0.99, 0.05))
        lh = Vector((0.32, -0.28, 1.28))
        # con el paso corto lo empuja menos: el centro del bastón queda más cerca de la izquierda
        c = lh - a * (1.0 - 0.9 * (1.0 - k))
        strike = staff_hands(mod(C_BODY, hips=(0.0, -0.04, -0.3), hips_rot=(6.0, 0.0, 22.0), spine=(10.0, 0.0, 8.0),
                                 chest=(4.0, 0.0, 6.0), neck=(-6.0, 0.0, -18.0), head=(-8.0, 0.0, -18.0)),
                             tuple(c), tuple(a), hr=tuple(lh - a * 0.6), hl=tuple(lh),
                             elbow_r=(-0.6, -0.2, -0.8), elbow_l=(0.9, 0.3, -0.3))
        strike["hips"] = tuple(Vector(strike["hips"]) + Vector((0.01, 0.11, 0.1)) * (1.0 - k))
        glow, pt = "Master_GlintStaff", ("Staff", (0.0, 0.0, 0.0))
    else:
        strike = shorten(arms(hand(mod(C_BODY, hips=(-0.02, -0.06, -0.34), hips_rot=(8.0, 0.0, 18.0), spine=(12.0, 0.0, 8.0),
                                       chest=(4.0, 0.0, 6.0), neck=(-6.0, 0.0, -14.0), head=(-10.0, 0.0, -16.0),
                                       clav_r=(0.0, -4.0, 8.0)),
                                  "r", (-0.06, -1.2, 1.3), (0.0, -0.15, 1.0), (0.0, 1.0, 0.0), elbow=(-0.4, 0.3, -0.85), shape="palm"),
                             ph, l=(-0.22, 0.1, 0.06)), k)
        glow, pt = "Master_GlintHandR", PALM_R
    strike["travel"] = T * 0.6
    hold = mod(coil, hips=(0.03, 0.17, -0.19))
    drive = mix(coil, strike, 0.4)
    drive["travel"] = T * 0.25
    over = mod(strike, travel=T * 0.85, hips=tuple(Vector(strike["hips"]) + Vector((0.0, -0.04, -0.03))))
    if ph == 3:
        over["staff_pos"] = tuple(Vector(strike["staff_pos"]) + Vector((0.0, -0.06, -0.02)))
    else:
        over["hand_r"] = tuple(Vector(strike["hand_r"]) + Vector((0.0, -0.06, -0.03)))
    rec = mix(at_travel(arms(BODY, ph, right=True), T), over, 0.4)
    rec["travel"] = T * 0.97
    end = ready(ph, T)
    keys = [(0, coil, "lin"), (3, hold, "sine", {"stop": tuple(hold)}), (5, drive, "expo_in", {"travel": "lin"}),
            (7, strike, "expo_in", {"travel": "lin"}), (9, over, "out", {"travel": "out2"}), (14, rec, "inout", {"travel": "out2"}),
            (19, mod(end), "inout"), (26, end, "sine")]
    front = [(3, ball(RX, RY, RYAW, heel=10.0), "lin")] + front_step(7, T, drive_f=5)
    back = [(3, flat(LX, LY, LYAW), "lin"), (5, ball(LX, LY, LYAW, heel=14.0), "in2")] + follow_step(7, T, 26)
    nm = "CounterStrike" if var is None else "CounterStrike_" + var
    t = {"tell": [0, 3], "apex": 3, "hold": [0, 3], "contact": 7, "active": [7, 9], "recover": [9, 26],
         "lunge": [3, 19, T], "kind": GOLD, "glow": glow, "strike": pt, "chain_from": "COIL", "chain_to": "READY"}
    if var is None:
        t["reach_variants"] = reach_names("CounterStrike", ph)
    # sin el adelanto de la cadera (LEAD): con claves tan juntas la cadera que guía ya arrastraba el golpe al aviso
    return add(nm, 26, keys, ph=ph, lag={"head": 1.0}, steps=feet_track(front, back, 26, r0=ball(RX, RY, RYAW, heel=10.0)),
               timing=t,
               events=[{"frame": 3, "fn": "Apex"}, {"frame": 7, "fn": "Strike"}, {"frame": 6, "fn": "Step"}, {"frame": 16, "fn": "Step"}],
               notes="sale de COIL (el final de Counter): palma corta con medio paso (o la estocada del bastón), pega en f7" +
                     ("" if var is None else ". Variante de paso corto (la elige el jefe en la suelta)"))


# la postura del bambú: hundido en el gato (más bajo que la guardia, el peso todo atrás), el pecho apenas adelante y
# las dos palmas cruzadas por las muñecas delante del pecho, abiertas hacia Kaito: una pared. Desde arriba es otra
# silueta que la guardia (que es un brazo alto al costado de la cabeza): una X adelante del cuerpo
S_BODY = feet(mod(BODY, hips=(0.03, 0.17, -0.3), hips_rot=(4.0, 0.0, 10.0), spine=(8.0, 0.0, 2.0), chest=(4.0, 0.0, 2.0),
                  neck=(-6.0, 0.0, -8.0), head=(-10.0, 0.0, -8.0), knee_l=(0.6, -1.0, 0.0), knee_r=(-0.3, -1.0, 0.0)),
              r=ball(*land_xy(FOOT_R0), heel=22.0))
# las palmas cruzadas en X delante de la cara, los dedos siguiendo al antebrazo que sube desde el codo bien abierto:
# paradas del todo con los codos afuera la muñeca tenía que doblarse 90° de costado y el brazo, para que entrara, bajaba
# los codos 45° (la postura perdía el ancho y desde la cámara del juego quedaba en 13-15 % de cambio contra la espera)
_S_R = dict(pos=(-0.02, -0.64, 1.74), fingers=(0.5, -0.35, 0.8), dorsum=(0.3, 0.9, 0.1), elbow=(-1.0, 0.2, -0.2), shape="palm")
_S_L = dict(pos=(0.02, -0.66, 1.68), fingers=(-0.5, -0.35, 0.8), dorsum=(-0.3, 0.9, 0.1), elbow=(1.0, 0.2, -0.2), shape="palm")


def stance_arms(p, ph, w=1.0):
    """Las dos palmas cruzadas adelante (w = cuánto: 0 = la guardia común de las manos), o el bastón parado adelante con
    la punta apoyada en el piso en la derecha y la palma izquierda parada al lado (fase 3)."""
    if ph == 3:
        # parado adelante y un poco a su izquierda (donde lo tiene la guardia: no cruza el cuerpo), en la derecha sola con
        # el pulgar hacia arriba, y la palma izquierda parada al lado. Con las dos manos, la izquierda (la de arriba)
        # quedaba con el pulgar hacia el piso y el antebrazo girado 125°: para llegar desde la guardia el giro cruzaba los
        # 180° y la mano daba 75° en un cuadro
        top = Vector((0.16, -0.6, 1.76))
        tip = Vector((0.2, -0.7, MR.STAFF_R + 0.01))
        a = (top - tip).normalized()
        q = staff_hands(p, tuple(tip + a * (MR.STAFF_LEN * 0.5)), tuple(a), hr=(0.16, -0.62, 1.56), hl=None,
                        gru=(-1.0, 0.0, 0.0), elbow_r=(-0.9, 0.2, -0.4))
        q = hand(q, "l", (0.36, -0.56, 1.66), (-0.3, -0.35, 0.9), (-0.15, 0.95, 0.3), elbow=(1.0, 0.2, -0.3), shape="palm")
        q["back_l"] = 0.0
        return q
    q = hand(p, "r", **_S_R)
    q = hand(q, "l", **_S_L)
    q["back_l"] = 0.0
    return q


def stance(ph):
    """Postura del bambú (BambooMasterBoss.EnterStance): de la guardia baja al gato y cruza las dos palmas adelante (en la
    fase 1 la izquierda sale de la espalda: lo único que la saca es esta postura); el juego deja el último cuadro. Pegarle
    acá es lo que él espera: desvía y contragolpea; esperar lo abre (Taunt)."""
    a = arms(BODY, ph, right=True)
    mid_b = mix(BODY, S_BODY, 0.6)
    if ph == 3:
        # primero lo desliza hacia adelante entre las manos (la punta de atrás sale del cuerpo por su eje) y recién después
        # lo para: girarlo desde la guardia lo pasaba por el pecho
        mid = anchor(mod(mid_b, **STAFF_GUARD), "staff", staff=tuple(Vector(ANCHOR["staff"]["staff_cdir"]) * -0.45))
        mid["grip_r"] = STAFF_GUARD["grip_r"] + 0.45
        mid["grip_l"] = STAFF_GUARD["grip_l"] + 0.45
    else:
        mid = mix(a, stance_arms(mid_b, ph), 0.55)
    s_ = stance_arms(S_BODY, ph)
    CHAIN.setdefault("STANCE", {})[ph] = s_
    POSES[f"postura del bambú {ph}"] = s_
    return add("Stance", 20, [(0, a, "sine"), (8, mid, "out"), (14, mod(s_, breath=0.6), "inout"), (20, s_, "sine")], ph=ph,
               lag={"head": 1.5, "neck": 0.8},
               timing={"kind": "none", "hold_last": True, "chain_from": "READY", "chain_to": "STANCE"},
               notes="postura del bambú: hundido en el gato, las dos palmas cruzadas adelante (el bastón parado en la fase 3); "
                     "pose quieta desde f14: el juego deja el último cuadro (BambooMasterBoss.EnterStance)")


def taunt(ph):
    """Abierto (Taunt, Kaito esperó la postura): recoge el pie de adelante y se para alto, los brazos bajan y se abren a
    los costados con las palmas hacia Kaito, el pecho arriba y el mentón alto ('pegame'); se queda así ~0.8 s y llama una
    vez con todo el antebrazo derecho; vuelve a la guardia con el paso. Desde la cámara del juego es la silueta más
    abierta de la pelea (antes era la guardia con los dedos curvándose). Fase 3: el bastón parado en la izquierda, al
    costado. Sirve también de re-entrada corta en los reintentos."""
    g = arms(BODY, ph, right=True)
    RX, RY, RYAW = land_xy(FOOT_R0)
    LX, LY, LYAW = land_xy(FOOT_L0)
    tall = mod(BODY, hips=(0.02, 0.1, -0.02), hips_rot=(-2.0, 0.0, 8.0), spine=(-6.0, 0.0, 2.0), chest=(-8.0, 0.0, 2.0),
               neck=(-6.0, 0.0, -6.0), head=(-12.0, 0.0, -8.0), breath=1.0, knee_r=(-0.1, -1.0, 0.0), knee_l=(0.1, -1.0, 0.0))
    # los brazos abiertos y bajos, las palmas hacia adelante
    open_r = dict(pos=(-0.62, -0.22, 1.18), fingers=(-0.35, -0.2, -1.0), dorsum=(0.0, 1.0, -0.2), elbow=(-0.6, 0.6, -0.4), shape="palm")
    open_l = dict(pos=(0.62, -0.22, 1.18), fingers=(0.35, -0.2, -1.0), dorsum=(0.0, 1.0, -0.2), elbow=(0.6, 0.6, -0.4), shape="palm")
    # la llamada: el antebrazo derecho estirado adelante con la palma arriba y después recogido hacia él
    call_out = dict(pos=(-0.36, -0.72, 1.42), fingers=(0.1, -1.0, 0.1), dorsum=(0.0, 0.0, -1.0), elbow=(-0.8, 0.2, -0.5), shape="palm")
    # recogida: el antebrazo sube con la palma hacia él (el dorso hacia Kaito). Con el dorso hacia él la mano tenía que
    # dar media vuelta contra el antebrazo entre la palma arriba de la llamada y esta
    call_in = dict(pos=(-0.32, -0.38, 1.72), fingers=(0.1, -0.2, 1.0), dorsum=(0.0, -0.95, -0.2), elbow=(-0.85, 0.1, -0.5), shape="relaxed")
    # (la punta que pega arriba y el pulgar izquierdo hacia ella, como master_clips_p3.side_staff)
    rest3 = staff_pose(BODY, (0.5, -0.12, 1.17), (0.0, 0.0, -1.0), upv=(0.0, -1.0, 0.0), gr=None, gl=-0.32, glu=(1.0, 0.0, 0.0),
                       elbow_l=(0.85, 0.3, -0.4))

    def pose(body, r, l=open_l):
        q = hand(body, "r", **r)
        if ph == 3:
            q = mod(q, **{k: rest3[k] for k in rest3 if k.startswith(("staff", "grip", "elbow_l"))})
            q.update(MR.hand_shape("l", "grip"))
            return q
        q = hand(q, "l", **l)
        q["back_l"] = 0.0
        return q
    gather = pose(mix(BODY, tall, 0.4), dict(open_r, pos=(-0.5, -0.32, 1.4)), dict(open_l, pos=(0.5, -0.32, 1.4)))
    wide = pose(tall, open_r)
    wide2 = pose(mod(tall, breath=0.6, head=(-13.0, 2.0, -8.0)), dict(open_r, pos=(-0.64, -0.2, 1.16)), dict(open_l, pos=(0.64, -0.2, 1.16)))
    out_ = pose(mod(tall, head=(-11.0, 3.0, -8.0)), call_out)
    in_ = pose(mod(tall, head=(-12.0, 4.0, -8.0), spine=(-7.0, 0.0, 2.0)), call_in)
    POSES[f"abierto {ph}"] = wide
    back_r = ball(RX, RY, RYAW, heel=8.0)
    keys = [(0, g, "sine"), (8, gather, "inout"), (14, wide, "inout"), (26, wide2, "sine"), (31, out_, "inout"), (37, in_, "inout"),
            (43, wide2, "inout"), (50, mix(wide2, g, 0.5), "inout"), (60, g, "sine")]
    # el pie de adelante se recoge junto al de atrás (parado alto, nada adelante) y vuelve a la guardia al final
    tuck = (RX + 0.06, RY + 0.36, RYAW + 10.0)
    front = [(4, back_r, "inout"), (6, air(RX + 0.03, RY + 0.16, AZ + 0.07, pitch=6.0, yaw=RYAW + 5.0), "out2"),
             (8, air(tuck[0], tuck[1], AZ + 0.03, pitch=-2.0, yaw=tuck[2]), "out"), (10, flat(*tuck), "inout"), (45, flat(*tuck), "lin"),
             (47, ball(*tuck, heel=16.0), "inout"), (49, air(RX + 0.03, RY + 0.18, AZ + 0.07, pitch=-4.0, yaw=RYAW + 5.0), "in2"),
             (51, air(RX, RY, AZ + 0.03, pitch=-6.0, yaw=RYAW), "out"), (53, heel(RX, RY, RYAW, toe_up=6.0), "inout"),
             (54, flat(RX, RY, RYAW), "lin"), (60, flat(RX, RY, RYAW), "lin")]
    return add("Taunt", 60, keys, ph=ph, lag={"head": 2.0, "neck": 1.0}, steps=foot_track("r", front, 60, FOOT_R0),
               timing={"kind": "none", "open": [14, 46], "chain_from": "READY", "chain_to": "READY"},
               events=[{"frame": 10, "fn": "Step"}, {"frame": 14, "fn": "Open"}, {"frame": 33, "fn": "Beckon"},
                       {"frame": 54, "fn": "Step"}],
               notes="abierto: recoge el pie de adelante, se para alto con los brazos abiertos (f14-46) y llama una vez con el "
                     "antebrazo (f33); vuelve a la guardia (f60)")


# ============================================================================ agotado (postura quebrada)
def _kneel_body(breath=0.0, bob=0.0):
    """Rodilla izquierda en el piso (la pierna de atrás), el pie derecho plantado adelante, el tronco caído sobre la rodilla
    derecha: el castigo largo de la postura quebrada."""
    return feet(mod(BODY, hips=(0.04, 0.12, -0.57 - bob), hips_rot=(8.0, 0.0, 10.0), spine=(22.0 - 3.0 * breath, 0.0, 2.0),
                    chest=(10.0 - 4.0 * breath, 0.0, 2.0), neck=(4.0, 0.0, -6.0), head=(14.0 - 6.0 * breath, 0.0, -6.0),
                    knee_l=(0.2, -1.0, -0.2), knee_r=(-0.2, -1.0, 0.3), breath=breath),
                l=KNEEL_FOOT_L)


def _kneel_arms(p, ph, w=0.0):
    """La derecha apoyada en la rodilla derecha; fase 2: la izquierda en el muslo izquierdo; fase 3: la izquierda sigue
    en el bastón, que queda a su izquierda con la punta de adelante apoyada en el piso (el mismo lado y casi el mismo
    rumbo de la guardia: así entra y sale de la rodilla sin que el bastón cruce el cuerpo)."""
    q = hand(p, "r", (-0.22, -0.4, 0.84 - 0.01 * w), (0.15, -0.9, -0.3), (0.0, 0.3, 1.0), elbow=(-0.6, 0.3, -0.6), shape="relaxed")
    if ph == 1:
        return arms(q, 1)
    if ph == 3:
        tip, lh = Vector(KNEEL_STAFF_TIP), Vector((0.44, -0.2, 0.74 - 0.012 * w))
        a = (lh - tip).normalized()
        return staff_hands(q, tuple(tip + a * (MR.STAFF_LEN * 0.5)), tuple(a), hl=tuple(lh), lt=-1.0,
                           glu=(1.0, 0.0, 0.3), elbow_l=(0.8, 0.4, -0.3))
    return hand(q, "l", (0.3, -0.05, 0.86 - 0.01 * w), (-0.1, -0.9, -0.4), (0.2, 0.2, 1.0), elbow=(0.7, 0.3, -0.5), shape="relaxed")


# la punta del bastón apoyada en el piso adelante a su izquierda mientras está de rodillas (fase 3)
KNEEL_STAFF_TIP = (0.24, -1.12, 0.03)


def kneel_pose(ph, breath=0.0, bob=0.0):
    return _kneel_arms(_kneel_body(breath, bob), ph, breath)


# el pie de atrás en punta, con la rodilla en el piso: los dedos un poco más doblados que el pie (si no, la punta se
# metía 2 cm en el piso)
KNEEL_FOOT_L = ball(0.26, 0.64, 30.0, heel=62.0)[:2] + (70.0,)


def kneel_steps(f_down, f_rise, frames):
    """El pie de atrás al caer sobre la rodilla y al levantarse (una pista aparte del cuerpo): despega, va por el aire,
    llega encima de su lugar y recién ahí apoya. Antes lo arrastraba ~26 cm por el piso al caer y al pararse."""
    LX, LY, LYAW = land_xy(LF0)
    (kx, ky, kz), krot, ktoe = KNEEL_FOOT_L
    keys = []
    if f_down is not None:
        toe = tiptoe(LX, LY, LYAW, heel=40.0, toe=10.0)
        keys += [(f_down, flat(LX, LY, LYAW), "lin"), (f_down + 1, toe, "inout"),
                 (f_down + 2, (tuple(Vector(toe[0]) + Vector((0.0, 0.01, 0.07))), toe[1], toe[2]), "out2"),
                 (f_down + 5, air(kx, ky - 0.06, kz + 0.14, pitch=40.0, yaw=krot[2]), "inout"),
                 (f_down + 8, ((kx, ky, kz + 0.04), krot, ktoe), "out"), (f_down + 10, KNEEL_FOOT_L, "inout")]
    keys += [(f_rise, KNEEL_FOOT_L, "lin"), (f_rise + 2, ((kx, ky - 0.01, kz + 0.07), krot, ktoe), "out2"),
             (f_rise + 3, air(kx, ky - 0.04, kz + 0.1, pitch=46.0, yaw=krot[2]), "lin"),
             (f_rise + 6, air(LX, LY + 0.12, AZ + 0.12, pitch=10.0, yaw=LYAW), "lin"),
             (f_rise + 8, air(LX, LY, AZ + 0.04, pitch=-4.0, yaw=LYAW), "out"), (f_rise + 10, heel(LX, LY, LYAW, toe_up=5.0), "inout"),
             (f_rise + 11, flat(LX, LY, LYAW), "lin"), (frames, flat(LX, LY, LYAW), "lin")]
    return foot_track("l", keys, frames, LF0 if f_down is not None else KNEEL_FOOT_L)


def _rise_keys(K0, g, ph, f0):
    """Claves para levantarse de la rodilla (desde el cuadro f0): empuja con la pierna de atrás y se para; el pie de
    atrás va en su pista (kneel_steps). En la fase 3 la derecha vuelve a agarrar el bastón por delante mientras se para
    (grip_r_w)."""
    push = mix(K0, g, 0.35)
    stand = mix(K0, g, 0.75)
    if ph == 3:
        # de pie, la izquierda lleva el bastón abierta al costado de la cadera y la derecha lo vuelve a tomar por delante:
        # la mezcla directa con la guardia pasaba el antebrazo izquierdo por la cadera
        hr, hl = Vector((0.04, -0.5, 1.1)), Vector((0.38, 0.08, 1.18))
        a = (hl - hr).normalized()
        stand = staff_hands(mod(stand, staff_follow=0.0), tuple(hr + a * 0.38), tuple(a), hr=tuple(hr), hl=tuple(hl),
                            elbow_r=(-0.8, 0.2, -0.6), elbow_l=(0.85, 0.45, -0.3))
    return [(f0 + 6, push, "inout"), (f0 + 12, stand, "inout")]


def exhausted(ph):
    """Postura quebrada (Enemy.BecomeExhausted, 4 s): se tambalea, cae sobre la rodilla de atrás con la mano en la otra
    rodilla (fase 3: apoyado en el bastón), jadea tres veces y se levanta. La ventana de golpes libres es 'kneel'."""
    g = arms(BODY, ph, right=True)
    K0 = kneel_pose(ph)
    CHAIN["KNEEL"] = CHAIN.get("KNEEL", {})
    CHAIN["KNEEL"][ph] = K0
    POSES[f"rodilla {ph}"] = K0
    LX, LY, LYAW = land_xy(LF0)
    reel = arms(mod(BODY, hips=(0.03, 0.14, -0.14), hips_rot=(-4.0, 3.0, 12.0), spine=(-6.0, 2.0, 2.0), chest=(-6.0, 0.0, 2.0),
                    head=(-16.0, 4.0, -8.0)), ph, right=True, r=(0.03, 0.06, -0.08), staff=(0.0, 0.05, 0.05))
    drop = mix(reel, K0, 0.55)
    if ph == 3:
        # la derecha suelta el bastón en el tambaleo y la punta de adelante baja al piso: el bastón queda en la izquierda,
        # de su lado, y lo frena al caer
        drop = mod(drop, grip_r_w=0.0)
    keys = [(0, g, "lin"), (5, reel, "out"), (10, drop, "in2"), (15, kneel_pose(ph, 0.0, 0.03), "out2"), (20, K0, "sine")]
    f = 20
    for i in range(6):
        f += 13
        keys.append((f, kneel_pose(ph, 1.0, 0.012) if i % 2 == 0 else K0, "sine"))
    # se levanta: empuja con la pierna de atrás, el pie vuelve a la guardia y se para
    keys += _rise_keys(K0, g, ph, 98) + [(120, g, "sine")]
    return add("Exhausted", 120, keys, ph=ph, lag={"head": 2.0, "neck": 1.0}, steps=kneel_steps(5, 100, 120),
               timing={"kind": "none", "kneel": [15, 100], "rise": [100, 120], "chain_from": "READY", "chain_to": "READY",
                       "legs_cross": []},
               events=[{"frame": 15, "fn": "Kneel"}] + [{"frame": 20 + 13 * k + 6, "fn": "Breath"} for k in (0, 2, 4)],
               notes="postura quebrada: cae sobre la rodilla izquierda en f15, jadea (Breath f26, f52, f78) y se levanta en "
                     "f100-120. Dura exhaustedTime = 4.0 s; si termina antes, ExhaustedRise")


def exhausted_hit(ph):
    """Golpe mientras está de rodillas ('ExhaustedHit'): la cabeza y el pecho saltan y vuelve a la rodilla."""
    K0 = kneel_pose(ph)
    jolt = mod(K0, spine=(14.0, 0.0, 2.0), chest=(2.0, 0.0, 2.0), head=(-4.0, 4.0, -4.0), neck=(-4.0, 0.0, -6.0))
    return add("ExhaustedHit", 16, [(0, K0, "lin"), (2, jolt, "snap"), (7, mod(K0, head=(8.0, 0.0, -6.0)), "out"), (16, K0, "sine")],
               ph=ph, lag={"head": 1.0}, timing={"kind": "none", "chain_from": "KNEEL", "chain_to": "KNEEL"},
               notes="sacudón en el piso: vuelve a la rodilla en f16")


def exhausted_rise(ph):
    """Se levanta de la rodilla cuando el agotamiento termina antes (que el crossfade a la guardia no lo pare de golpe)."""
    K0 = kneel_pose(ph)
    g = arms(BODY, ph, right=True)
    return add("ExhaustedRise", 22, [(0, K0, "lin")] + _rise_keys(K0, g, ph, 1) + [(22, g, "sine")], ph=ph,
               steps=kneel_steps(None, 2, 22),
               timing={"kind": "none", "chain_from": "KNEEL", "chain_to": "READY"}, notes="de la rodilla a la guardia en 0.73 s")


# ============================================================================ presentación y cambio de fase 1 -> 2
WAIT_BODY = feet(mod(BODY, hips=(0.0, 0.02, -0.02), hips_rot=(0.0, 0.0, 4.0), spine=(2.0, 0.0, 1.0), chest=(1.0, 0.0, 1.0),
                     neck=(4.0, 0.0, -2.0), head=(16.0, 0.0, -2.0), back_r=1.0, back_l=1.0, hand_r_follow=0.0, hand_l_follow=0.0,
                     knee_r=(-0.1, -1.0, 0.0), knee_l=(0.1, -1.0, 0.0), **MR.hand_shape("r", "relaxed"), **MR.hand_shape("l", "relaxed")),
                 r=flat(-0.14, -0.04, -4.0), l=flat(0.15, 0.06, 10.0))


def _salute(p):
    """Saludo de kung fu (bao quan): el puño derecho tapado por la palma izquierda delante del pecho, los codos afuera."""
    q = hand(p, "r", (-0.03, -0.36, 1.72), (1.0, -0.1, 0.0), (0.0, -1.0, 0.2), elbow=(-0.8, 0.2, -0.5), shape="fist")
    q = hand(q, "l", (0.08, -0.38, 1.75), (0.0, -0.1, 1.0), (1.0, 0.0, 0.0), elbow=(0.8, 0.2, -0.5), shape="palm")
    return mod(q, back_r=0.0, back_l=0.0)


def intro():
    """La entrada del maestro (solo fase 1): espera erguido con las dos manos en la espalda y la cabeza gacha, la levanta
    hacia Kaito, saluda (puño en la palma), hace una reverencia corta, y toma la guardia de una sola mano: la izquierda
    vuelve a la espalda y el pie derecho se adelanta."""
    w0 = WAIT_BODY
    w1 = mod(w0, breath=1.0, head=(15.0, 0.0, -2.0))
    look = mod(w0, neck=(-2.0, 0.0, -2.0), head=(-4.0, 0.0, -4.0))
    look2 = mod(look, head=(-3.0, 5.0, -4.0))
    # las manos colgando con los dedos apenas adelante: la palma del saludo los tiene arriba y apenas adelante, y desde
    # unos dedos apenas atrás el giro más corto los pasaba por detrás (la muñeca izquierda daba 59° en un cuadro)
    side = hand(hand(mod(look, back_r=0.0, back_l=0.0), "r", (-0.36, 0.04, 1.3), (0.0, -0.1, -1.0), (-1.0, 0.0, 0.0),
                     elbow=(-0.8, 0.4, -0.2), shape="relaxed"),
                "l", (0.36, 0.06, 1.3), (0.0, -0.1, -1.0), (1.0, 0.0, 0.0), elbow=(0.8, 0.4, -0.2), shape="relaxed")
    sal = _salute(mod(look, head=(-4.0, 0.0, -3.0)))
    POSES["saludo"] = sal
    sal_a = to_chest(sal, ("r", "l"))
    bow = mod(sal_a, hips=(0.0, 0.05, -0.04), spine=(18.0, 0.0, 1.0), chest=(12.0, 0.0, 1.0), neck=(8.0, 0.0, -2.0), head=(12.0, 0.0, -2.0))
    POSES["reverencia"] = bow
    up = mod(sal_a, head=(-5.0, 0.0, -4.0))
    # se separan: la derecha baja a la guardia por adelante, la izquierda vuelve a la espalda por el costado de la cadera
    sep = feet(hand(hand(mod(BODY, hips=(0.01, 0.04, -0.05), back_r=0.0, back_l=0.0), "r", (-0.3, -0.42, 1.62), (0.05, -0.4, 1.0),
                         (-0.2, 1.0, 0.2), elbow=(-0.7, 0.3, -0.6), shape="palm"),
                    "l", (0.38, 0.08, 1.34), (0.0, 0.2, -1.0), (1.0, 0.0, 0.0), elbow=(0.8, 0.4, -0.2), shape="relaxed"),
               r=air(-0.17, -0.14, 0.2, pitch=-8.0, yaw=0.0), l=flat(0.15, 0.06, 10.0))
    # los pasos a la guardia: cada pie despega rodando sobre la bola (no se arrastra) y apoya en su lugar de la guardia
    lift_r = feet(mix(up, sep, 0.25), r=ball(-0.14, -0.04, -4.0, heel=20.0))
    plant_r = feet(mix(sep, R0, 0.45), r=FOOT_R0, l=ball(0.15, 0.06, 10.0, heel=18.0))
    plant_r.update(back_l=0.0)
    guard_in = feet(mod(R0, back_l=1.0, hips=(0.02, 0.05, -0.07), **MR.hand_shape("l", "relaxed")), l=air(0.21, 0.16, 0.16, pitch=-6.0, yaw=24.0))
    keys = [(0, w0, "sine"), (18, w1, "sine"), (28, look, "inout"), (36, look2, "sine"), (44, side, "inout"), (52, sal, "inout"),
            (58, sal_a, "sine"), (68, bow, "inout"), (76, bow, "sine"), (86, up, "inout"), (89, lift_r, "in2"), (93, sep, "out2"),
            (96, plant_r, "in2"), (100, guard_in, "out2"), (104, feet(mod(R0, back_l=1.0, hips=(0.02, 0.06, -0.075)), l=FOOT_L0), "in2"),
            (120, ready(1), "sine")]
    CHAIN["WAIT"] = {1: WAIT_BODY}
    LX, LY, LYAW = land_xy(FOOT_L0)
    w_l = flat(0.15, 0.06, 10.0)
    back = [(96, ball(0.15, 0.06, 10.0, heel=18.0), "in2"), (98, air(0.18, 0.11, AZ + 0.08, pitch=6.0, yaw=18.0), "out2"),
            (100, air(0.23, 0.2, AZ + 0.06, pitch=-4.0, yaw=28.0), "lin"), (102, air(LX, LY, AZ + 0.035, pitch=-4.0, yaw=LYAW), "out"),
            (104, FOOT_L0, "inout"), (120, FOOT_L0, "lin")]
    steps = [st for st in foot_track("l", [(93, w_l, "lin")] + back, 120, w_l) if st[0] >= 93]
    return add("Intro", 120, keys, ph=1, lag={"head": 2.0, "neck": 1.0}, steps=steps,
               timing={"kind": "none", "chain_from": "WAIT", "chain_to": "READY"},
               events=[{"frame": 26, "fn": "HeadRise"}, {"frame": 52, "fn": "Salute"}, {"frame": 70, "fn": "Bow"},
                       {"frame": 96, "fn": "Step"}, {"frame": 104, "fn": "Guard"}],
               notes="espera con las manos en la espalda y la cabeza gacha; mira a Kaito (f26), saluda puño en palma (f52), "
                     "reverencia (f70) y toma la guardia de una mano (f104)")


# cuánto salió el saco puesto en cada cuadro de PhaseCoat (0 = puesto, 1 = la copia que vuela en CoatOff, f41): lo abre con
# los puños (f30-35) y se le desliza cada vez más rápido por la espalda y los brazos, así llega a CoatOff a toda velocidad y
# la copia sigue el movimiento (con una sola clave 'inout' en f38 frenaba ahí y saltaba 32 % en el cuadro siguiente).
# master_coat.write_coat_slip lo pasa a las etapas CoatSlip1..4
SLIP_CURVE = [[30, 0.0], [31, 0.01], [32, 0.03], [33, 0.05], [34, 0.08], [35, 0.12], [36, 0.18], [37, 0.3], [38, 0.46],
              [39, 0.62], [40, 0.81], [41, 1.0]]


def add3(a, b):
    return tuple(x + y for x, y in zip(a, b))


def mixf(a, b, w):
    return tuple(x + (y - x) * w for x, y in zip(a, b))


def coat_off_place(p):
    """(robe_pos, robe_rot, robe_fold) que dejan los RobeT_* donde los pondría el cuerpo de la pose p como al saco puesto:
    RobeT_Root con el pecho, las mangas con los brazos (desde su reposo). En CoatOff la copia es el saco puesto (skin
    inverso), así que con esto las mangas giran alrededor de los hombros del saco y el ruedo cuelga del cuello."""
    W = solved(p)
    R = SOLVER.rig
    Mr = W["Chest"] @ R.rest_inv["Chest"] @ R.rest["RobeT_Root"]
    rr = (NA.rot3(Mr) @ NA.rot3(R.rest["RobeT_Root"]).inverted()).to_euler('XYZ')
    A = Mr @ R.rest_inv["RobeT_Root"]
    want = NA.rot3(W["UpperArm_R"] @ R.rest_inv["UpperArm_R"] @ R.rest["RobeT_ArmR"])
    ea = (NA.rot3(A).inverted() @ want @ NA.rot3(R.rest["RobeT_ArmR"]).inverted()).to_euler('XYZ')
    # el antebrazo: solo el codo (fold[5] gira RobeT_ArmR_2 sobre su x desde el tramo de arriba)
    Wa = A @ Matrix.Translation(R.head_rest("RobeT_ArmR")) @ ea.to_matrix().to_4x4() @ Matrix.Translation(-R.head_rest("RobeT_ArmR")) \
        @ R.rest["RobeT_ArmR"]
    want2 = NA.rot3(W["Forearm_R"] @ R.rest_inv["Forearm_R"] @ R.rest["RobeT_ArmR_2"])
    e2 = (NA.rot3(Wa @ R.rest_inv["RobeT_ArmR"]).inverted() @ want2 @ NA.rot3(R.rest["RobeT_ArmR_2"]).inverted()).to_euler('XYZ')
    d = math.degrees
    return tuple(Mr.translation), (d(rr.x), d(rr.y), d(rr.z)), (0.0, d(ea.y), -d(ea.z), 0.0, 0.0, d(e2.x), d(ea.x))


# la copia que vuela se aplana (forma Collapse de Master_RobeThrown) del cuadro de CoatOff a la caída (CoatLand, f64)
COLLAPSE_CURVE = [[41, 0.0], [43, 0.12], [46, 0.42], [49, 0.66], [54, 0.86], [64, 1.0]]


def phase_coat():
    """Fase 1 -> 2 (solo base): se endereza, los ojos se encienden en jade (EyesIgnite), saca la izquierda de la espalda,
    agarra el saco por el pecho, lo abre y lo tira hacia atrás de un tirón (CoatOff: el juego apaga Master_Robe y prende
    Master_RobeThrown, que ya está en el aire detrás de los hombros) y el saco vuela y cae al piso detrás a su izquierda
    (CoatRest). Hace un círculo de tai chi con los dos brazos y toma la guardia de la fase 2."""
    g1 = READY1
    tall = mod(R0, back_l=1.0, hips=(0.02, 0.05, -0.04), spine=(-2.0, 0.0, 3.0), chest=(-4.0, 0.0, 3.0), head=(-8.0, 0.0, -10.0),
               breath=1.0, hand_r=(-0.24, -0.4, 1.86))
    out_l = hand(mod(tall, back_l=0.0, breath=0.6), "l", (0.4, 0.05, 1.36), (0.0, 0.0, -1.0), (1.0, 0.0, 0.0), elbow=(0.8, 0.4, -0.2),
                 shape="relaxed")
    grab = hand(hand(mod(BODY, hips=(0.02, 0.05, -0.08), spine=(4.0, 0.0, 2.0), chest=(2.0, 0.0, 2.0), head=(-2.0, 0.0, -10.0)),
                     "r", (-0.1, -0.25, 1.84), (0.2, 0.2, 1.0), (0.0, -1.0, 0.0), elbow=(-0.7, -0.2, -0.7), shape="fist"),
                "l", (0.1, -0.25, 1.84), (-0.2, 0.2, 1.0), (0.0, -1.0, 0.0), elbow=(0.7, -0.2, -0.7), shape="fist")
    opn = hand(hand(mod(grab, hips=(0.02, 0.07, -0.13), spine=(8.0, 0.0, 2.0), chest=(4.0, 0.0, 2.0)),
                    "r", (-0.34, -0.12, 1.96), (0.3, 0.3, 1.0), (-0.5, -0.8, 0.0), elbow=(-0.8, -0.1, -0.6), shape="fist"),
               "l", (0.34, -0.12, 1.96), (-0.3, 0.3, 1.0), (0.5, -0.8, 0.0), elbow=(0.8, -0.1, -0.6), shape="fist")
    fling = hand(hand(mod(BODY, hips=(0.02, 0.0, -0.06), spine=(-6.0, 0.0, 2.0), chest=(-10.0, 0.0, 2.0), neck=(-4.0, 0.0, -8.0),
                          head=(-10.0, 0.0, -10.0), clav_r=(0.0, 10.0, 0.0), clav_l=(0.0, -10.0, 0.0), breath=1.0),
                     "r", (-0.62, 0.36, 1.62), (-0.3, 0.6, -0.7), (-0.6, -0.2, 0.7), elbow=(-0.6, 0.6, -0.3), shape="palm"),
                "l", (0.62, 0.36, 1.62), (0.3, 0.6, -0.7), (0.6, -0.2, 0.7), elbow=(0.6, 0.6, -0.3), shape="palm")
    POSES["saco afuera"] = fling
    # el saco sale de los hombros: los hombros atrás, el pecho afuera y los brazos que barren hacia abajo y atrás (las
    # mangas se le deslizan por los brazos); recién con el saco detrás del cuerpo se cambia por la copia que vuela
    shrug = hand(hand(mod(BODY, hips=(0.02, 0.0, -0.08), spine=(-8.0, 0.0, 2.0), chest=(-12.0, 0.0, 2.0), neck=(-2.0, 0.0, -8.0),
                          head=(-6.0, 0.0, -10.0), clav_r=(0.0, 14.0, 0.0), clav_l=(0.0, -14.0, 0.0), breath=1.0),
                      "r", (-0.4, 0.3, 1.24), (-0.1, 0.4, -1.0), (-0.9, 0.2, 0.2), elbow=(-0.5, 0.7, 0.1), shape="relaxed"),
                 "l", (0.4, 0.3, 1.24), (0.1, 0.4, -1.0), (0.9, 0.2, 0.2), elbow=(0.5, 0.7, 0.1), shape="relaxed")
    slip = hand(hand(mod(shrug, spine=(-9.0, 0.0, 2.0), chest=(-13.0, 0.0, 2.0)),
                     "r", (-0.36, 0.42, 1.08), (-0.05, 0.5, -1.0), (-0.95, 0.1, 0.1), elbow=(-0.4, 0.8, 0.1), shape="palm"),
                "l", (0.36, 0.42, 1.08), (0.05, 0.5, -1.0), (0.95, 0.1, 0.1), elbow=(0.4, 0.8, 0.1), shape="palm")
    POSES["se saca el saco"] = slip
    roll = hand(hand(mod(BODY, hips=(0.02, 0.04, -0.1), spine=(4.0, 0.0, 3.0), chest=(2.0, 0.0, 3.0), head=(-4.0, 0.0, -10.0)),
                     "r", (-0.44, 0.0, 1.42), (0.0, 0.1, -1.0), (-1.0, 0.1, 0.0), elbow=(-0.8, 0.3, -0.3), shape="relaxed"),
                "l", (0.44, 0.0, 1.42), (0.0, 0.1, -1.0), (1.0, 0.1, 0.0), elbow=(0.8, 0.3, -0.3), shape="relaxed")
    # círculo de tai chi: las dos manos suben por delante hasta la cara y bajan abriéndose a la guardia
    rise = hand(hand(mod(BODY, hips=(0.02, 0.04, -0.04), breath=1.0, head=(-6.0, 0.0, -10.0)),
                     "r", (-0.22, -0.5, 1.98), (0.0, -0.3, 1.0), (0.0, 1.0, 0.2), elbow=(-0.5, 0.0, -0.9), shape="palm"),
                "l", (0.22, -0.5, 1.98), (0.0, -0.3, 1.0), (0.0, 1.0, 0.2), elbow=(0.5, 0.0, -0.9), shape="palm")
    sink = hand(hand(mod(BODY, hips=(0.02, 0.07, -0.14), head=(-5.0, 0.0, -11.0)),
                     "r", (-0.4, -0.5, 1.5), (0.1, -0.3, 1.0), (-0.3, 1.0, 0.2), elbow=(-0.7, 0.3, -0.7), shape="palm"),
                "l", (0.42, -0.4, 1.36), (0.2, -0.3, 1.0), (0.3, 1.0, 0.2), elbow=(0.7, 0.3, -0.7), shape="palm")
    POSES["círculo tai chi"] = rise
    # el saco tirado: en CoatOff (f41) es el mismo saco puesto (master_coat.rebuild_thrown), con los RobeT_* donde los
    # pone el cuerpo en esa pose (coat_off_place: el cuello con el pecho, las mangas con los brazos); de ahí se le va de los
    # brazos hacia atrás y abajo (las manos salen por los puños), sale volando hacia arriba y atrás con el tirón, vuela a
    # su izquierda ondeando el ruedo, se aplana (Collapse) y cae arrugado detrás a su izquierda (el ruedo doblado en zigzag,
    # las mangas quebradas). robe_pos/robe_rot = cabeza y giro de RobeT_Root desde su reposo
    # robe_fold = (ruedo, mangas abiertas, mangas giradas, tramo 2, tramo 3, codo de las mangas, mangas atrás)
    p41, r41, f41 = coat_off_place(slip)
    path = [(41, p41, r41, f41),
            (43, add3(p41, (0.0, 0.13, -0.07)), add3(r41, (6.0, 0.0, 1.0)), mixf(f41, (4.0, 0.0, 2.0, 4.0, 2.0, 8.0, 12.0), 0.3)),
            (45, add3(p41, (0.03, 0.34, 0.06)), add3(r41, (22.0, 3.0, 8.0)), mixf(f41, (12.0, 10.0, 8.0, 8.0, 6.0, 18.0, 18.0), 0.7)),
            (48, (0.14, 0.8, 2.42), (58.0, 10.0, 26.0), (22.0, 36.0, 18.0, 26.0, -18.0, 30.0, 0.0)),
            (52, (0.44, 1.36, 2.48), (98.0, 20.0, 60.0), (34.0, 52.0, 20.0, -24.0, 30.0, 18.0, 0.0)),
            (56, (0.74, 1.88, 1.86), (116.0, 25.0, 90.0), (20.0, 40.0, 15.0, 30.0, -20.0, 34.0, 0.0)),
            (60, (0.95, 2.26, 0.92), (104.0, 15.0, 110.0), (10.0, 30.0, 12.0, -18.0, 26.0, 22.0, 0.0)),
            (64, (1.05, 2.48, 0.14), (92.0, 6.0, 122.0), (8.0, 22.0, 8.0, 34.0, -30.0, 40.0, 0.0)),
            (67, (1.08, 2.54, 0.15), (90.0, 3.0, 126.0), (14.0, 28.0, 10.0, 52.0, -46.0, 52.0, 0.0)),
            (72, (1.1, 2.58, 0.08), (90.0, 0.0, 128.0), (18.0, 32.0, 12.0, 62.0, -58.0, 58.0, 0.0))]
    track = [(f, dict(robe_free=1.0, robe_pos=pos, robe_rot=rot, robe_fold=fold), "inout" if k else "hold")
             for k, (f, pos, rot, fold) in enumerate(path)]
    track = [(0, dict(robe_free=0.0, robe_pos=path[0][1], robe_rot=path[0][2], robe_fold=path[0][3]), "lin"),
             (40, dict(robe_free=0.0, robe_pos=path[0][1], robe_rot=path[0][2], robe_fold=path[0][3]), "lin")] + track + \
            [(110, dict(robe_free=1.0, robe_pos=path[-1][1], robe_rot=path[-1][2], robe_fold=path[-1][3]), "lin")]
    keys = [(0, ready(1), "sine"), (10, tall, "inout"), (18, mod(tall, breath=0.8), "sine"), (24, out_l, "inout"),
            (30, grab, "inout"), (35, opn, "inout"), (38, shrug, "inout"),
            (41, slip, "out"), (44, fling, "expo_out"),
            (48, mod(fling, spine=(-4.0, 0.0, 2.0), breath=0.7), "out"), (57, roll, "inout"), (66, rise, "inout"), (78, sink, "inout"),
            (92, mod(READY2, hips=(0.02, 0.065, -0.09)), "inout"), (110, ready(2), "sine")]
    return add("PhaseCoat", 110, keys, ph=1, lag={"head": 2.0, "neck": 1.0}, steps=track,
               timing={"kind": "none", "robe_off": 41, "chain_from": "READY", "chain_to": "READY2", "next_phase": 2,
                       "slip_curve": SLIP_CURVE, "collapse_curve": COLLAPSE_CURVE},
               events=[{"frame": 18, "fn": "EyesIgnite"}, {"frame": 30, "fn": "CoatGrab"}, {"frame": 38, "fn": "Shrug"},
                       {"frame": 41, "fn": "CoatOff"}, {"frame": 64, "fn": "CoatLand"}, {"frame": 72, "fn": "CoatRest"},
                       {"frame": 92, "fn": "Guard"}],
               notes="se saca el saco: ojos jade en f18, lo agarra (f30), lo abre y se lo saca de los hombros con los brazos "
                     "atrás (f38-41: en f41 apagar Master_Robe y prender Master_RobeThrown, ya detrás del cuerpo); sale de los "
                     "brazos hacia atrás, cae detrás a su izquierda (f64) y queda arrugado en f72 (hornearlo ahí); termina en "
                     "la guardia de la fase 2")


# ============================================================================ golpes propios de la fase 2 (sin saco)
def curve(pts, f):
    """Valor en el cuadro f de una curva por puntos (cuadro, valor) con Catmull-Rom: velocidad continua en los puntos
    (un giro de 360° que no frena en cada clave)."""
    if f <= pts[0][0]:
        return pts[0][1]
    if f >= pts[-1][0]:
        return pts[-1][1]
    i = max(k for k in range(len(pts) - 1) if pts[k][0] <= f)
    f0, v0 = pts[i]
    f1, v1 = pts[i + 1]
    vp = pts[i - 1][1] if i > 0 else v0 - (v1 - v0)
    vn = pts[i + 2][1] if i + 2 < len(pts) else v1 + (v1 - v0)
    u = (f - f0) / (f1 - f0)
    # tangentes escaladas por el largo de los tramos vecinos (Catmull-Rom no uniforme): sin sobrepasos en tramos cortos
    fp = pts[i - 1][0] if i > 0 else f0 - (f1 - f0)
    fn = pts[i + 2][0] if i + 2 < len(pts) else f1 + (f1 - f0)
    m0 = (v1 - vp) / (f1 - fp) * (f1 - f0)
    m1 = (vn - v0) / (fn - f0) * (f1 - f0)
    h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
    return h00 * v0 + h10 * m0 + h01 * v1 + h11 * m1


def vcurve(pts, f):
    return Vector([curve([(k, v[i]) for k, v in pts], f) for i in range(len(pts[0][1]))])


def rz(deg, v):
    return Matrix.Rotation(math.radians(deg), 3, 'Z') @ Vector(v)


def twin_palm():
    """Shuang tui zhang (las dos palmas), dorado: el AVISO son las dos palmas recogidas a los costados de la cintura con los
    codos atrás y el pecho que se llena de aire, hundido en el caballo; da el paso y empuja con las dos a la vez (la derecha
    con los dedos arriba, la izquierda abajo: la boca del tigre) cuando el pie de adelante se clava."""
    coil = hand(mod(R0, hips=(0.02, 0.15, -0.3), hips_rot=(0.0, 0.0, 4.0), spine=(-4.0, 0.0, 0.0), chest=(-6.0, 0.0, 0.0),
                    neck=(-2.0, 0.0, -4.0), head=(-4.0, 0.0, -4.0), breath=1.0, knee_l=(0.6, -1.0, 0.0), knee_r=(-0.5, -1.0, 0.0)),
                "r", (-0.44, 0.17, 1.36), (0.0, -0.25, 1.0), (0.0, 1.0, 0.1), elbow=(-0.6, 0.8, -0.2), shape="palm")
    coil["_left_p2"] = dict(pos=(0.44, 0.17, 1.36), fingers=(0.0, -0.25, 1.0), dorsum=(0.0, 1.0, 0.1), elbow=(0.6, 0.8, -0.2), shape="palm")
    strike = hand(mod(R0, hips=(-0.02, -0.06, -0.4), hips_rot=(8.0, 0.0, 6.0), spine=(12.0, 0.0, 2.0), chest=(4.0, 0.0, 2.0),
                      neck=(-6.0, 0.0, -4.0), head=(-10.0, 0.0, -4.0), clav_r=(0.0, -4.0, 6.0), clav_l=(0.0, 4.0, -6.0)),
                  "r", (-0.14, -1.14, 1.32), (0.0, -0.15, 1.0), (0.0, 1.0, 0.0), elbow=(-0.4, 0.3, -0.85), shape="palm")
    strike["_left_p2"] = dict(pos=(0.12, -1.14, 1.08), fingers=(0.0, -0.15, -1.0), dorsum=(0.0, 1.0, 0.0), elbow=(0.4, 0.3, -0.85),
                              shape="palm")
    over = mod(strike, hips=(-0.03, -0.1, -0.43), hand_r=(-0.13, -1.2, 1.3))
    over["_left_p2"] = dict(strike["_left_p2"], pos=(0.12, -1.2, 1.06))
    POSES["dos palmas aviso 2"] = arms(coil, 2, left=coil["_left_p2"])
    for var in (None,) + tuple(REACH_K):
        _step_in(2, 38, 12, 17, coil, strike, over, 0.95, ["Master_GlintHandR", "Master_GlintHandL"], PALM_R, "TwinPalm",
                 "dos palmas: recogidas a la cintura con el pecho lleno (aviso f12), paso y empuje doble en f17 (0.95 m)",
                 variant=False, var=var)


def spin_kick():
    """Patada de gancho girando, dorada (fase 2): pivota sobre la bola del pie derecho y gira a su izquierda; el AVISO es
    de espaldas a Kaito mirándolo por encima del hombro izquierdo (desde arriba se ve el chaleco de atrás, más oscuro, y la
    rodilla izquierda recogida), y la pierna izquierda barre horizontal a la altura del pecho cuando la cadera pasa los
    270°. Termina de girar y la pierna vuelve a su lugar de la guardia (el giro completo deja los pies donde estaban)."""
    N, APEX, CONTACT = 44, 14, 19
    bx, by = (Vector(RF0[0][:2]) + rz(RF0[1][2], (0.0, MR.SOLE_BALL_Y, 0.0)).to_2d())
    th = [(0, 14.0), (5, 22.0), (10, 110.0), (APEX, 180.0), (16, 190.0), (CONTACT, 270.0), (21, 302.0), (26, 345.0), (31, 372.0),
          (36, 374.0), (N, 374.0)]
    rest_l = rz(-14.0, (LF0[0][0] - bx, LF0[0][1] - by, 0.0)).to_2d()
    # pie izquierdo en el marco que gira con el cuerpo (relativo a la bola del derecho): atrás a su izquierda, recogido de
    # espaldas, estirado al costado en el golpe, y de vuelta a su lugar
    lpath = [(0, (rest_l.x, rest_l.y, AZ)), (4, (rest_l.x, rest_l.y, AZ)), (8, (0.6, 0.5, 0.32)), (APEX, (0.62, 0.42, 0.62)),
             (16, (0.7, 0.36, 0.72)), (CONTACT, (1.3, 0.06, 1.12)), (21, (1.18, 0.18, 1.02)), (26, (0.74, 0.42, 0.48)),
             (31, (rest_l.x, rest_l.y, AZ + 0.06)), (33, (rest_l.x, rest_l.y, AZ)), (N, (rest_l.x, rest_l.y, AZ))]
    lean = [(0, 0.0), (8, 4.0), (APEX, 8.0), (CONTACT, -16.0), (21, -14.0), (28, -4.0), (34, 0.0), (N, 0.0)]
    drop = [(0, 0.0), (6, 0.05), (APEX, 0.08), (CONTACT, 0.04), (26, 0.06), (33, 0.02), (N, 0.0)]
    c_rest = Vector((0.02, 0.06))
    keys = []
    for f in range(0, N + 1):
        t = curve(th, f)
        d = t - 14.0
        w = max(0.0, min(1.0, f / 5.0)) * max(0.0, min(1.0, (N - 2 - f) / 8.0))
        # la cadera sobre el pie que pivota (la pierna derecha bajo su cadera), y vuelve a la guardia al final
        piv = Vector((bx, by)) + rz(t, (0.17, 0.12, 0.0)).to_2d()
        hc = c_rest.lerp(piv, w)
        # el pecho llega un poco después que la cadera y la cabeza busca a Kaito por encima del hombro (270° = -Y)
        lag = (curve(th, f) - curve(th, max(0, f - 2))) * 0.25
        chest_y = t - lag + 8.0
        look = max(-75.0, min(75.0, ((270.0 - chest_y + 180.0) % 360.0) - 180.0)) if w > 0.05 else -21.0
        look = -21.0 + (look + 21.0) * w
        L = curve(lean, f)
        p = mod(R0, hips=(hc.x, hc.y, -0.08 - curve(drop, f)), hips_rot=(L * 0.4, -L * 0.5, t), spine=(3.0, 0.0, 4.0 - lag),
                chest=(2.0, L * 0.3, 4.0 - lag), neck=(-2.0, 0.0, look * 0.45), head=(-5.0, 0.0, look * 0.55),
                knee_r=tuple(rz(t - 14.0, (-0.25, -1.0, 0.0))), knee_l=tuple(rz(t - 14.0, (0.3, -0.6, 0.6) if 6 < f < 31 else (0.45, -1.0, 0.0))))
        # las manos de guardia giran con el cuerpo; en el golpe se abren para equilibrar
        op = max(0.0, min(1.0, 1.0 - abs(f - CONTACT) / 5.0))
        hr0, hl0 = Vector(_GUARD_R["pos"]), Vector(_GUARD_L["pos"])
        hr0 = hr0.lerp(Vector((-0.5, 0.25, 1.75)), op)
        hl0 = hl0.lerp(Vector((0.1, -0.3, 1.8)), op)
        def spin(v):
            q = rz(d, Vector((v.x - c_rest.x, v.y - c_rest.y, 0.0)))
            return (hc.x + q.x, hc.y + q.y, v.z - curve(drop, f))
        p = hand(p, "r", spin(hr0), tuple(rz(d, _GUARD_R["fingers"])), tuple(rz(d, _GUARD_R["dorsum"])),
                 elbow=tuple(rz(d, _GUARD_R["elbow"])), shape="palm")
        p["_left_p2"] = dict(pos=spin(hl0), fingers=tuple(rz(d, _GUARD_L["fingers"])), dorsum=tuple(rz(d, _GUARD_L["dorsum"])),
                             elbow=tuple(rz(d, _GUARD_L["elbow"])), shape="palm")
        lp = vcurve(lpath, f)
        lw = Vector((bx, by)) + rz(t, (lp.x, lp.y, 0.0)).to_2d()
        planted_l = f <= 4 or f >= 33
        if planted_l:
            fl = flat(LF0[0][0], LF0[0][1], LF0[1][2])
        else:
            # despega desde donde estaba apoyado (el camino que gira con el cuerpo lo toma en 3 cuadros)
            k = min(1.0, (f - 4) / 3.0)
            lw = Vector(LF0[0][:2]).lerp(lw, k)
            # cerca del piso el pie va plano (con la punta abajo raspaba al apoyar)
            pitch = (30.0 if lp.z < 0.8 else -20.0) * max(0.0, min(1.0, (lp.z - 0.2) / 0.25))
            fl = air(lw.x, lw.y, lp.z, pitch=pitch, yaw=LF0[1][2] + (t + 20.0 - LF0[1][2]) * k, toe=-10.0 if lp.z > 0.8 else 0.0)
        heel_r = 12.0 * w
        fr = on_ball(bx, by, RF0[1][2] + d, heel_r)
        p = feet(p, r=fr, l=fl)
        keys.append((f, arms(p, 2, left=p["_left_p2"]), "lin"))
    keys = blend_ends(keys, 2, N)
    POSES["giro aviso 2"] = keys[APEX][1]
    return add("SpinKick", N, keys, ph=2, variant=False, lag={},
               timing={"tell": [0, APEX], "apex": APEX, "hold": [APEX, 16], "contact": CONTACT, "active": [CONTACT, 21],
                       "recover": [21, N], "kind": GOLD, "glow": "Master_GlintFootL", "strike": TOE_TIP_L, "spin": True,
                       "chain_from": "READY", "chain_to": "READY"},
               events=[{"frame": APEX, "fn": "Apex"}, {"frame": CONTACT, "fn": "Strike"}, {"frame": 33, "fn": "Step"}],
               notes="gancho girando sobre la bola del pie derecho: de espaldas a Kaito en el aviso (f14), la pierna izquierda "
                     "barre a la altura del pecho al pasar los 270° (f19) y termina el giro en la guardia (f33)")


def sweep():
    """Barrida baja de 360°, ROJA (anillo): se deja caer sobre la pierna de atrás (sobre la bola, el talón arriba) con la
    pierna derecha estirada a ras del piso y las dos manos apoyadas adelante (AVISO: la silueta se hunde a la mitad); gira
    una vuelta entera a su izquierda barriendo con la pierna estirada. Se esquiva con dash a través o saliendo del anillo."""
    N, APEX, CONTACT, END = 48, 12, 16, 30
    LX, LY, LYAW = land_xy(LF0)
    bx, by = (Vector((LX, LY)) + rz(LYAW, (0.0, MR.SOLE_BALL_Y, 0.0)).to_2d())
    th = [(0, 14.0), (8, 6.0), (APEX, 4.0), (14, 6.0), (CONTACT, 30.0), (END - 2, 340.0), (END, 362.0), (34, 370.0), (40, 374.0),
          (N, 374.0)]
    down = [(0, 0.0), (5, 0.25), (9, 0.55), (APEX, 0.6), (14, 0.61), (END, 0.58), (34, 0.45), (40, 0.18), (N, 0.0)]
    c_rest = Vector((0.02, 0.06))
    # la pierna derecha en el marco que gira, relativa a la bola del izquierdo: de la guardia a estirada a su derecha
    rest_r = rz(-14.0, (RF0[0][0] - bx, RF0[0][1] - by, 0.0)).to_2d()
    rpath = [(0, (rest_r.x, rest_r.y, AZ)), (2, (rest_r.x, rest_r.y, AZ)), (3, (rest_r.x, rest_r.y - 0.02, AZ + 0.05)),
             (6, (-0.75, -0.55, 0.24)), (9, (-1.12, -0.25, AZ + 0.08)),
             (CONTACT, (-1.16, -0.18, AZ + 0.09)), (END, (-1.16, -0.18, AZ + 0.09)), (34, (-0.8, -0.45, 0.26)),
             (37, (rest_r.x, rest_r.y, AZ + 0.06)), (39, (rest_r.x, rest_r.y, AZ + 0.012)), (40, (rest_r.x, rest_r.y, AZ)),
             (N, (rest_r.x, rest_r.y, AZ))]
    keys = []
    for f in range(0, N + 1):
        t = curve(th, f)
        d = t - 14.0
        dz = curve(down, f)
        w = min(1.0, dz / 0.55)
        piv = Vector((bx, by)) + rz(t, (-0.1, 0.18, 0.0)).to_2d()
        hc = c_rest.lerp(piv, w)
        p = mod(R0, hips=(hc.x, hc.y, -0.08 - dz), hips_rot=(18.0 * w, 0.0, t), spine=(22.0 * w + 3.0, 0.0, 4.0 - 8.0 * w),
                chest=(10.0 * w + 2.0, 0.0, 4.0 - 4.0 * w), neck=(-18.0 * w - 2.0, 0.0, -10.0 + 10.0 * w),
                head=(-20.0 * w - 5.0, 0.0, -11.0 + 9.0 * w),
                knee_l=tuple(rz(d, (0.6, -1.0, 0.0))), knee_r=tuple(rz(d, (-0.3, -0.2, 1.0) if 4 < f < 36 else (-0.25, -1.0, 0.0))))
        # manos: de la guardia (girando con el cuerpo) al piso en el aviso, y al despegar se abren a los costados para
        # equilibrar el giro. Un solo peso para la guardia: antes la mezcla piso + despegue valía 0.33 en el cuadro del
        # despegue y la mano volvía a la guardia SIN girar, cruzando el pecho
        mixw = max(0.0, min(1.0, (f - 6) / 4.0)) * max(0.0, min(1.0, (36 - f) / 4.0))
        lift = max(0.0, min(1.0, (f - CONTACT) / 3.0))

        def place(local, z):
            q = Vector((bx, by)) + rz(t, local).to_2d()
            return Vector((q.x, q.y, z))

        def guard_pos(v):
            q = rz(d, Vector((v[0] - c_rest.x, v[1] - c_rest.y, 0.0)))
            return Vector((hc.x + q.x, hc.y + q.y, v[2] - dz))
        hr = place((-0.33, -0.57, 0.0), 0.0).lerp(place((-0.72, -0.3, 0.0), 0.8), lift)
        hl = place((0.03, -0.61, 0.0), 0.0).lerp(place((0.66, -0.2, 0.0), 0.86), lift)
        hr.z = max(hr.z, 0.06)
        hl.z = max(hl.z, 0.06)
        pr = guard_pos(_GUARD_R["pos"]).lerp(hr, mixw)
        pl = guard_pos(_GUARD_L["pos"]).lerp(hl, mixw)
        # direcciones de la guardia a las de la mano apoyada (las dos giran con el cuerpo)
        sl = lambda a_, b_: tuple(NA.slerp_dir(rz(d, a_), rz(d, b_), mixw))
        p = hand(p, "r", tuple(pr), sl(_GUARD_R["fingers"], (0.0, -1.0, -0.2)), sl(_GUARD_R["dorsum"], (0.0, 0.0, 1.0)),
                 elbow=sl(_GUARD_R["elbow"], (-0.7, 0.4, 0.2)), shape="palm")
        p["_left_p2"] = dict(pos=tuple(pl), fingers=sl(_GUARD_L["fingers"], (0.0, -1.0, -0.2)), dorsum=sl(_GUARD_L["dorsum"], (0.0, 0.0, 1.0)),
                             elbow=sl(_GUARD_L["elbow"], (0.7, 0.4, 0.2)), shape="palm")
        rp = vcurve(rpath, f)
        rw = Vector((bx, by)) + rz(t, (rp.x, rp.y, 0.0)).to_2d()
        planted_r = f <= 2 or f >= 40
        fr = flat(*land_xy(RF0)) if planted_r else air(rw.x, rw.y, rp.z, pitch=-30.0 if 8 < f < 33 else 0.0, yaw=t - 10.0,
                                                         toe=-10.0 if f < 35 else 0.0)
        fl = on_ball(bx, by, LYAW + d, 40.0 * w)
        p = feet(p, r=fr, l=fl)
        keys.append((f, arms(p, 2, left=p.get("_left_p2")), "lin"))
    keys = blend_ends(keys, 2, N)
    POSES["barrida aviso 2"] = keys[APEX][1]
    return add("Sweep", N, keys, ph=2, variant=False, lag={},
               timing={"tell": [0, APEX], "apex": APEX, "hold": [APEX, 14], "contact": CONTACT, "active": [CONTACT, END],
                       "recover": [END, N], "kind": RED, "glow": "Master_GlintFootR", "strike": TOE_R, "spin": True,
                       "ring_m": 1.9, "legs_cross": [[CONTACT, END]], "chain_from": "READY", "chain_to": "READY"},
               events=[{"frame": APEX, "fn": "Apex"}, {"frame": CONTACT, "fn": "Strike"}, {"frame": END, "fn": "SweepEnd"},
                       {"frame": 38, "fn": "Step"}],
               notes="barrida: se deja caer con la pierna derecha estirada y las manos en el piso (aviso f12), una vuelta "
                     "entera en f16-30 a ras del piso (anillo de ring_m), se levanta a la guardia")


def qi_wave():
    """Onda de qi, ROJA (anillo que se abre): se hunde en el caballo, los brazos dibujan un círculo grande (afuera, arriba
    y abajo) y juntan la bola de qi delante del vientre, inspira y tiembla (AVISO), golpea el piso con el pie derecho y empuja
    las dos palmas hacia adelante y abajo: QiRelease es cuando sale el anillo."""
    N, APEX, CONTACT = 56, 30, 36
    LX, LY, LYAW = land_xy(LF0)
    RX, RY, RYAW = land_xy(RF0)
    horse = mod(R0, hips=(0.02, 0.0, -0.3), hips_rot=(0.0, 0.0, 6.0), spine=(4.0, 0.0, 2.0), chest=(2.0, 0.0, 2.0),
                neck=(-2.0, 0.0, -4.0), head=(-4.0, 0.0, -4.0), knee_l=(0.8, -0.6, 0.0), knee_r=(-0.8, -0.6, 0.0))

    def hands(p, r, l, rf=(0.0, -0.3, 1.0), lf=(0.0, -0.3, 1.0), rd=(0.0, 1.0, 0.1), ld=(0.0, 1.0, 0.1), shape="palm", er=(-0.7, 0.3, -0.6),
              el=(0.7, 0.3, -0.6)):
        q = hand(p, "r", r, rf, rd, elbow=er, shape=shape)
        q["_left_p2"] = dict(pos=l, fingers=lf, dorsum=ld, elbow=el, shape=shape)
        return q
    k_sink = hands(mod(horse, hips=(0.02, 0.03, -0.2)), (-0.5, -0.3, 1.5), (0.5, -0.3, 1.5))
    k_out = hands(mod(horse, breath=0.5), (-0.95, -0.05, 1.85), (0.95, -0.05, 1.85), rf=(-1.0, 0.0, 0.3), lf=(1.0, 0.0, 0.3),
                  rd=(0.0, 0.0, 1.0), ld=(0.0, 0.0, 1.0), er=(0.0, 0.3, -1.0), el=(0.0, 0.3, -1.0))
    k_up = hands(mod(horse, breath=0.9, chest=(-2.0, 0.0, 2.0), head=(-8.0, 0.0, -4.0)), (-0.38, -0.22, 2.5), (0.38, -0.22, 2.5),
                 rf=(-0.2, 0.0, 1.0), lf=(0.2, 0.0, 1.0), rd=(-0.5, 0.0, 0.0), ld=(0.5, 0.0, 0.0), er=(-0.8, 0.2, 0.3), el=(0.8, 0.2, 0.3))
    k_ball = hands(mod(horse, hips=(0.02, 0.02, -0.34), breath=1.0, spine=(8.0, 0.0, 2.0)), (-0.08, -0.42, 1.42), (0.06, -0.42, 1.18),
                   rf=(0.3, -0.6, 0.0), lf=(-0.3, -0.6, 0.0), rd=(0.0, 0.0, 1.0), ld=(0.0, 0.0, -1.0), shape="claw",
                   er=(-0.8, 0.2, -0.4), el=(0.8, 0.2, -0.4))
    POSES["onda de qi aviso 2"] = arms(k_ball, 2, left=k_ball["_left_p2"])
    k_hold = mod(k_ball, hips=(0.02, 0.025, -0.36), head=(-5.0, 0.0, -4.0))
    k_hold["_left_p2"] = dict(k_ball["_left_p2"])
    k_stomp_up = feet(mod(k_hold, hips=(0.0, 0.05, -0.3)), r=air(RX, RY + 0.02, 0.3, pitch=-10.0, yaw=RYAW))
    k_stomp_up["_left_p2"] = dict(k_ball["_left_p2"])
    k_push = feet(hands(mod(horse, hips=(0.02, -0.04, -0.42), hips_rot=(6.0, 0.0, 6.0), spine=(16.0, 0.0, 2.0), chest=(6.0, 0.0, 2.0),
                            neck=(-10.0, 0.0, -4.0), head=(-12.0, 0.0, -4.0), clav_r=(0.0, -4.0, 6.0), clav_l=(0.0, 4.0, -6.0)),
                        (-0.2, -1.0, 1.0), (0.2, -1.0, 1.0), rf=(0.0, -0.3, 1.0), lf=(0.0, -0.3, 1.0), rd=(0.0, 1.0, 0.3), ld=(0.0, 1.0, 0.3),
                        shape="claw", er=(-0.5, 0.2, -0.8), el=(0.5, 0.2, -0.8)),
                  r=flat(RX, RY, RYAW))
    k_over = mod(k_push, hips=(0.02, -0.06, -0.44), hand_r=(-0.2, -1.05, 0.95))
    k_over["_left_p2"] = dict(k_push["_left_p2"], pos=(0.2, -1.05, 0.95))
    k_rec = feet(mix(R0, k_push, 0.4), r=flat(RX, RY, RYAW))
    k_rec["_left_p2"] = None
    keys = [(0, ready(2), "sine"), (8, k_sink, "inout"), (15, k_out, "inout"), (21, k_up, "inout"), (27, k_ball, "inout"), (APEX, k_hold, "sine"),
            (33, k_stomp_up, "out2"), (CONTACT, k_push, "expo_in", {"foot_r": "in2"}), (39, k_over, "out"),
            (46, feet(mod(R0, hips=(0.02, 0.04, -0.14)), r=flat(RX, RY, RYAW)), "inout"), (N, ready(2), "sine")]
    return add("QiWave", N, [(k[0], arms(k[1], 2, left=k[1].get("_left_p2"))) + tuple(k[2:]) for k in keys], ph=2, variant=False,
               timing={"tell": [0, APEX], "apex": APEX, "hold": [APEX, 33], "contact": CONTACT, "active": [CONTACT, 39],
                       "recover": [39, N], "kind": RED, "glow": ["Master_GlintHandR", "Master_GlintHandL"], "strike": PALM_R,
                       "spin": True, "ring_from": "transform", "chain_from": "READY", "chain_to": "READY"},
               events=[{"frame": 21, "fn": "Gather"}, {"frame": APEX, "fn": "Apex"}, {"frame": CONTACT, "fn": "Stomp"},
                       {"frame": CONTACT, "fn": "QiRelease"}, {"frame": CONTACT, "fn": "Strike"}],
               notes="onda de qi: círculo de brazos y la bola de qi en el vientre (aviso f30, tiembla hasta f33), pisotón y "
                     "empuje de las dos palmas en f36 (QiRelease: el anillo rojo sale del transform)")


def back_hop(ph):
    """El salto atrás que toma distancia antes del paso del viento (fases 2 y 3) y de la grulla voladora (las tres; en la
    fase 1 con la izquierda en la espalda), sin daño: se agacha un instante, empuja con las dos bolas y vuela hacia atrás
    recogido, cae con los dos pies en su lugar de la guardia y amortigua. Todo el avance (HOP m hacia atrás) va entre el despegue y la caída en el espacio del
    personaje (timing.air): el jefe lo acorta para no salirse de la arena sin que los pies patinen. El vuelo es parejo EN
    EL RELOJ DEL JUEGO (la suelta se toca con u²)."""
    N, APEX, TAKE, LAND = 22, 6, 9, 15
    HOP = 2.6
    RX, RY, RYAW = land_xy(RF0)
    LX, LY, LYAW = land_xy(LF0)
    A = lambda p: arms(p, ph, right=True, r=(0.02, 0.06, -0.04), l=(-0.02, 0.06, -0.04))
    sink = feet(mod(BODY, hips=(0.02, 0.0, -0.3), hips_rot=(10.0, 0.0, 12.0), spine=(14.0, 0.0, 3.0), chest=(6.0, 0.0, 2.0),
                    head=(-12.0, 0.0, -10.0)), r=flat(RX, RY, RYAW), l=flat(LX, LY, LYAW))
    push = feet(mod(BODY, hips=(0.02, 0.1, -0.16), hips_rot=(2.0, 0.0, 12.0), spine=(4.0, 0.0, 3.0), head=(-8.0, 0.0, -10.0)),
                r=ball(RX, RY, RYAW, heel=20.0), l=ball(LX, LY, LYAW, heel=22.0))

    def flight(w):
        trv = -HOP * w
        z = 0.34 * 4.0 * w * (1.0 - w)
        tuck = math.sin(math.pi * w)
        p = mod(BODY, hips=(0.02, 0.1 - 0.06 * tuck, -0.1 + z - 0.06 * tuck), hips_rot=(-6.0 * tuck, 0.0, 12.0),
                spine=(-4.0 * tuck, 0.0, 3.0), chest=(-4.0 * tuck, 0.0, 2.0), head=(-6.0 + 4.0 * tuck, 0.0, -10.0), travel=trv)
        # los pies adelante del cuerpo (vuela hacia atrás), recogidos, y bajando a su lugar de la guardia
        return feet(p, r=air(RX, RY - 0.14 * tuck, AZ + 0.16 * tuck + z, pitch=-10.0 * tuck, yaw=RYAW),
                    l=air(LX, LY - 0.1 * tuck, AZ + 0.2 * tuck + z, pitch=-6.0 * tuck, yaw=LYAW))
    u0 = math.sqrt((TAKE - APEX) / (LAND - APEX))
    air_keys = []
    for f in range(TAKE + 1, LAND):
        u = math.sqrt((f - APEX) / (LAND - APEX))
        air_keys.append((f, flight((u - u0) / (1.0 - u0)), "lin"))
    # los pies vuelan en el espacio del personaje: en el mundo están corridos lo que avanzó (at_travel)
    air_keys = [(f, at_travel_feet(p_, p_["travel"]), e) for f, p_, e in air_keys]
    land = feet(mod(at_travel(BODY, -HOP), hips=(0.02, 0.04, -0.26), hips_rot=(8.0, 0.0, 12.0), spine=(12.0, 0.0, 3.0),
                    head=(-12.0, 0.0, -10.0)), r=flat(RX, RY + HOP, RYAW), l=flat(LX, LY + HOP, LYAW))
    land["travel"] = -HOP
    absorb = mod(land, hips=(0.02, 0.05, -0.3), spine=(14.0, 0.0, 3.0))
    keys = [(0, ready(ph), "sine"), (4, A(mix(BODY, sink, 0.6)), "inout"), (APEX, A(sink), "inout"), (8, A(push), "in2"),
            (TAKE, A(feet(mod(push, hips=(0.02, 0.12, -0.08)), r=ball(RX, RY, RYAW, heel=34.0),
                         l=ball(LX, LY, LYAW, heel=36.0))), "in2")]
    keys += [(f, A(p_), e) for f, p_, e in air_keys]
    keys += [(LAND, A(land), "lin"), (18, A(absorb), "out"), (N, ready(ph, -HOP), "inout")]
    # BackHop (fase 1), BackHop_P2 y BackHop_P3, como el resto de los clips con variante de fase
    return add("BackHop", N, keys, ph=ph, lag={"head": 1.5, "neck": 0.8},
               timing={"kind": "none", "apex": APEX, "hold": [APEX, APEX], "contact": LAND, "active": [LAND, LAND],
                       "recover": [LAND, N], "air": [TAKE, LAND], "release_rate": 1.0, "root_max": 26.0,
                       "chain_from": "READY", "chain_to": "READY"},
               events=[{"frame": TAKE, "fn": "TakeOff"}, {"frame": LAND, "fn": "Land"}],
               notes=f"salto atrás de {HOP} m (sin golpe): se agacha (f{APEX}), despega en f{TAKE} y cae en f{LAND} en su lugar "
                     "de la guardia; el avance va todo en timing.air (el jefe lo acorta)")


def at_travel_feet(p, travel):
    """Los pies de una pose autorada en el espacio del personaje, pasados al mundo del clip (el transform avanzó
    'travel')."""
    q = mod(p)
    for k in ("foot_r", "foot_l"):
        x, y, z = q[k]
        q[k] = (x, y - travel, z)
    return q


def dash_strike():
    """Embestida relámpago, ROJA (la especial rápida): se agacha un instante con la derecha recogida en dedos de espada y la
    izquierda adelante, se dispara a ras del piso ~6 m (el juego dibuja las imágenes residuales en timing.air) y clava la
    estocada de los dedos frenando sobre el pie derecho. El vuelo es parejo EN EL RELOJ DEL JUEGO (avance remapeado con la
    raíz de StepTimeline) y en timing.air el juego puede acortarlo para frenar delante de Kaito."""
    N, APEX, PUSH, CONTACT = 36, 8, 9, 17
    RR = 0.68
    D = 6.0
    RX, RY, RYAW = land_xy(RF0)
    LX, LY, LYAW = land_xy(LF0)
    set_ = feet(hand(mod(R0, hips=(0.0, 0.12, -0.34), hips_rot=(10.0, 0.0, 20.0), spine=(18.0, 0.0, 6.0), chest=(6.0, 0.0, 4.0),
                         neck=(-14.0, 0.0, -14.0), head=(-18.0, 0.0, -14.0), knee_r=(-0.3, -1.0, 0.0), knee_l=(0.5, -1.0, 0.0)),
                     "r", (-0.4, 0.2, 1.22), (0.0, -1.0, 0.1), (-0.3, 0.0, 1.0), elbow=(-0.5, 0.8, 0.0), shape="sword"),
                r=ball(RX, RY, RYAW, heel=8.0))
    set_["_left_p2"] = dict(pos=(0.42, -0.55, 1.52), fingers=(0.0, -0.4, 1.0), dorsum=(0.2, 1.0, 0.2), elbow=(0.8, 0.0, -0.6), shape="palm")
    POSES["embestida aviso 2"] = arms(set_, 2, left=set_["_left_p2"])
    hold = mod(set_, hips=(0.0, 0.13, -0.355))
    hold["_left_p2"] = dict(set_["_left_p2"])
    push = feet(mod(set_, hips=(0.0, -0.1, -0.3), spine=(26.0, 0.0, 6.0), travel=0.3), r=air(RX, RY - 0.5, 0.2, pitch=-10.0),
                l=tiptoe(LX, LY, LYAW, heel=50.0, toe=14.0))
    push["_left_p2"] = dict(set_["_left_p2"])
    DASH_EARLY.update(set=set_, hold=hold, push=push)

    def glide(w):
        trv = 0.3 + (D - 0.3) * w
        p = hand(mod(R0, hips=(0.0, -0.2, -0.36), hips_rot=(16.0, 0.0, 24.0), spine=(26.0, 0.0, 6.0), chest=(6.0, 0.0, 4.0),
                     neck=(-16.0, 0.0, -14.0), head=(-20.0, 0.0, -14.0), travel=trv, knee_r=(-0.2, -1.0, 0.2), knee_l=(0.3, -1.0, 0.3)),
                 "r", (-0.36, 0.05 - 0.5 * w, 1.3), (0.0, -1.0, 0.1), (-0.3, 0.0, 1.0), elbow=(-0.5, 0.8, 0.0), shape="sword")
        p["_left_p2"] = dict(pos=(0.34, -0.5 + 0.5 * w, 1.5), fingers=(0.0, -0.4, 1.0), dorsum=(0.2, 1.0, 0.2), elbow=(0.7, 0.0, -0.7),
                             shape="palm")
        # a ras del piso: el pie de adelante estirado, el de atrás arrastrado atrás, los dos en el aire
        # el de atrás va arriba y estirado con la punta hacia atrás (a 0.3 m la punta raspaba el piso todo el vuelo)
        return feet(p, r=air(-0.22, -0.72 - trv, 0.2 + 0.04 * math.sin(math.pi * w), pitch=-14.0),
                    l=air(0.22, 0.52 - trv, 0.42, pitch=28.0, yaw=LYAW, toe=14.0))
    air_keys = []
    u0 = math.sqrt((PUSH - APEX) / (CONTACT - APEX))
    for f in range(PUSH + 1, CONTACT):
        u = math.sqrt((f - APEX) / (CONTACT - APEX))
        air_keys.append((f, glide((u - u0) / (1.0 - u0)), "lin"))
    land_y = RY - D - 0.5
    stab = feet(hand(mod(R0, hips=(0.0, -0.3, -0.42), hips_rot=(14.0, 0.0, 30.0), spine=(22.0, 0.0, 8.0), chest=(6.0, 0.0, 6.0),
                         neck=(-14.0, 0.0, -18.0), head=(-18.0, 0.0, -18.0), clav_r=(0.0, -4.0, 8.0), travel=D),
                     "r", (-0.1, -1.4, 1.3), (0.0, -1.0, 0.05), (0.0, 0.0, 1.0), elbow=(-0.3, 0.3, -0.9), shape="sword"),
                r=flat(-0.2, land_y, 0.0), l=air(0.24, 0.45 - D, 0.26, pitch=30.0, yaw=LYAW))
    stab["_left_p2"] = dict(pos=(0.28, 0.0, 1.45), fingers=(0.3, 0.5, -0.8), dorsum=(0.6, 0.0, 0.8), elbow=(0.8, 0.4, -0.2), shape="palm")
    # avance final: el pie derecho clavado en land_y queda en su lugar de la guardia
    T_END = -(land_y - RY)
    slide = mod(stab, travel=D + 0.3, hips=(0.0, -0.18, -0.4))
    slide["_left_p2"] = dict(stab["_left_p2"])
    rec = feet(mod(at_travel(R0, T_END), hips=(0.02, 0.0, -0.2)), r=flat(-0.2, land_y, 2.0))
    keys = [(0, ready(2), "sine"), (6, set_, "inout"), (APEX, hold, "sine"), (PUSH, push, "in2", {"travel": "lin"})] + air_keys + \
           [(CONTACT, stab, "lin", {"foot_r": "lin"}), (21, slide, "out", {"travel": "out2"}), (28, rec, "inout", {"travel": "inout"}),
            (N, ready(2, T_END), "sine")]
    # el de atrás baja después de la estocada: llega encima de su lugar y recién ahí apoya (antes se arrastraba 43 cm)
    l0 = (stab["foot_l"], stab["foot_l_rot"], stab.get("toe_l", 0.0))
    back = [(20, air(LX, LY - T_END + 0.1, AZ + 0.14, pitch=6.0, yaw=LYAW), "inout"),
            (22, air(LX, LY - T_END, AZ + 0.04, pitch=-4.0, yaw=LYAW), "out"), (24, heel(LX, LY - T_END, LYAW, toe_up=5.0), "inout"),
            (25, flat(LX, LY - T_END, LYAW), "lin"), (N, flat(LX, LY - T_END, LYAW), "lin")]
    steps = [(f, st, e) for f, st, e in foot_track("l", [(CONTACT, l0, "lin")] + back, N, l0) if f >= CONTACT]
    return add("DashStrike", N, [(k[0], arms(k[1], 2, left=k[1].get("_left_p2"))) + tuple(k[2:]) for k in keys], ph=2, variant=False,
               steps=steps,
               timing={"tell": [0, APEX], "apex": APEX, "hold": [6, APEX], "contact": CONTACT, "active": [CONTACT, 19],
                       "recover": [19, N], "lunge": [APEX, 28, round(T_END, 3)], "air": [PUSH + 1, CONTACT - 1], "release_rate": RR,
                       "root_max": 26.0, "kind": RED, "glow": "Master_GlintHandR", "strike": PALM_R, "spin": True,
                       "chain_from": "READY", "chain_to": "READY", "pass_variant": "DashStrike_Pass"},
               events=[{"frame": APEX, "fn": "Apex"}, {"frame": PUSH, "fn": "DashStart"}, {"frame": CONTACT, "fn": "DashEnd"},
                       {"frame": CONTACT, "fn": "Strike"}, {"frame": 24, "fn": "Step"}],
               notes=f"embestida: se agacha (aviso f{APEX}), sale en f{PUSH} a ~20 m/s en el reloj del juego (releaseRate {RR}) y "
                     f"clava los dedos de espada frenando sobre el pie derecho (f{CONTACT}); imágenes residuales en DashStart-DashEnd")


# las poses del paso del viento hasta la suelta (dash_strike): la variante que pasa al costado arranca igual
DASH_EARLY = {}


def at_pose(p, travel, turn):
    """La misma pose (en el espacio del personaje) con el transform corrido 'travel' por el carril y girado 'turn' grados:
    lo que está en el mundo (pies) se pasa al mundo del clip."""
    q = copy.deepcopy(p)
    R = Matrix.Rotation(math.radians(turn), 3, 'Z')
    for k in ("foot_r", "foot_l"):
        if q.get(k) is None:
            continue
        w = R @ Vector(q[k])
        q[k] = (w.x, w.y - travel, w.z)
        r = q.get(k + "_rot")
        if r is not None:
            q[k + "_rot"] = (r[0], r[1], r[2] + turn)
    q["travel"], q["turn"] = travel, turn
    return q


def dash_pass():
    """DashStrike_Pass, el paso del viento que le pasa al COSTADO a Kaito (rojo): la variante que el jefe elige en la
    suelta cuando Kaito quedó demasiado cerca para frenar de frente (BambooMasterBoss.PlanDash). Hasta la suelta es
    DashStrike cuadro por cuadro; sale volando por al lado de Kaito (que queda a su derecha) y el transform GIRA en el
    vuelo (turn, como el avance: lo aplica el jefe): en el cruce (el contacto, f17) ya lo mira y le clava los dedos de
    espada de frente, y los SOSTIENE sobre él mientras le pasa por al lado (f17-f20: el jefe lo hace mirar a Kaito en ese
    tramo, BambooMasterBoss.CutTrack, y corre el clip con sustain); recién después gira en el aire hasta quedar de
    espaldas al carril, de frente a Kaito, y frena hacia atrás en dos pasos hasta la guardia. Antes la mano extendida era
    un solo cuadro (f17) y salía a su derecha girando en f18: a la velocidad del juego casi nunca se veía llegar. El jefe
    escala el avance de DashStart a DashEnd para que el cruce caiga sobre Kaito."""
    N, APEX, PUSH, CONTACT, HOLD, LAND = 36, 8, 9, 17, 20, 23
    RR = 0.68
    TC = 4.0                         # avance en el cruce con el vuelo autorado (el jefe lo escala: 0.3 + k * 3.7)
    TL = 5.6                         # y al apoyar (DashEnd)
    T_END = TL + 0.75                # frenando hacia atrás después de apoyar
    RX, RY, RYAW = land_xy(RF0)
    LX, LY, LYAW = land_xy(LF0)
    E = DASH_EARLY

    def turn_at(f):
        # de frente a Kaito en el cruce y siguiéndolo mientras le pasa (~15°/cuadro con el vuelo típico, x0.3-0.45); el
        # giro grande, después del corte
        return curve([(11, 0.0), (13, -14.0), (15, -46.0), (CONTACT, -82.0), (18, -95.0), (19, -108.0), (HOLD, -121.0),
                      (21, -145.0), (22, -168.0), (LAND, -179.0), (24, -180.0)], f)

    def trav(f):
        # después del cruce el vuelo se frena hasta apoyar (el corte lo frena: el jefe además corre el clip más lento ahí)
        return curve([(PUSH, 0.3), (CONTACT, TC), (HOLD, TC + 1.0), (LAND, TL), (26, TL + 0.5), (29, TL + 0.7), (31, T_END)], f)

    def air_feet(p, f, r, l):
        """Pies en el aire autorados en el espacio del personaje (se pasan al mundo con el avance y el giro del cuadro)."""
        q = feet(p, r=r, l=l)
        return at_pose(q, trav(f), turn_at(f))

    def body(f, hips, hrot, spine, chest, neck, head, hr, hr_dir, hr_up, el_r, hl, hl_dir, hl_up, el_l, r, l, **kw):
        p = hand(mod(R0, hips=hips, hips_rot=hrot, spine=spine, chest=chest, neck=neck, head=head, **kw),
                 "r", hr, hr_dir, hr_up, elbow=el_r, shape="sword")
        p["_left_p2"] = dict(pos=hl, fingers=hl_dir, dorsum=hl_up, elbow=el_l, shape="palm")
        return air_feet(p, f, r, l)

    keys = [(0, ready(2), "sine"), (6, E["set"], "inout"), (APEX, E["hold"], "sine"), (PUSH, E["push"], "in2", {"travel": "lin"})]
    # el vuelo: bajo y estirado hacia el costado de Kaito, la derecha recogida en la cadera para el corte, la izquierda
    # atrás; desde f13 el cuerpo gira hacia él (los pies quedan colgando del lado de afuera del giro)
    for f in range(PUSH + 1, CONTACT):
        w = (f - PUSH) / (CONTACT - PUSH)
        g = smooth(0.35, 1.0, w)
        p = body(f, hips=(0.0, -0.18, -0.36 - 0.02 * g), hrot=(16.0 - 4.0 * g, 6.0 * g, 24.0 - 12.0 * g),
                 spine=(26.0 - 6.0 * g, 0.0, 6.0 - 12.0 * g), chest=(6.0, 0.0, 4.0 - 10.0 * g), neck=(-16.0, 0.0, -14.0 + 10.0 * g),
                 head=(-20.0 + 4.0 * g, 0.0, -14.0 + 12.0 * g),
                 hr=(-0.36 + 0.14 * g, 0.05 - 0.2 * g, 1.3 - 0.06 * g), hr_dir=(0.1 * g, -1.0, 0.1), hr_up=(-0.3, 0.0, 1.0),
                 el_r=(-0.6, 0.7, -0.1), hl=(0.34 + 0.08 * g, -0.45 + 0.85 * g, 1.48), hl_dir=(0.2 * g, -0.4 + 1.2 * g, 0.6),
                 hl_up=(0.6 * g, 0.4, 0.6), el_l=(0.7, 0.2, -0.6),
                 r=air(-0.22 - 0.1 * g, -0.6 + 0.52 * g, 0.22 + 0.1 * g, pitch=-14.0 + 10.0 * g, yaw=0.0),
                 l=air(0.22 - 0.24 * g, 0.5 - 0.1 * g, 0.42 + 0.04 * g, pitch=28.0 - 8.0 * g, yaw=LYAW * (1.0 - g)))
        keys.append((f, p, "lin", {"turn": "lin", "travel": "lin"}))
    # el cruce: de frente a Kaito (que va a su derecha), los dedos de espada clavados a la altura de su pecho; la izquierda
    # abierta atrás para el equilibrio y las piernas recogidas del lado de afuera. De f17 a f20 los sostiene sobre él
    # (la mano corre un poco hacia su derecha, con Kaito que pasa) y el tronco empieza a girar
    def cut_pose(f, u):
        return body(f, hips=(0.0, -0.1, -0.42 + 0.01 * u), hrot=(10.0 - 2.0 * u, 8.0 - 3.0 * u, 6.0 - 8.0 * u),
                    spine=(18.0 - 2.0 * u, 0.0, -10.0 - 6.0 * u), chest=(6.0, 0.0, -12.0 - 4.0 * u),
                    neck=(-12.0, 0.0, 8.0 + 2.0 * u), head=(-14.0, 0.0, 10.0 + 2.0 * u), clav_r=(0.0, -4.0, 8.0),
                    hr=(-0.12 - 0.06 * u, -1.08 + 0.02 * u, 1.16 + 0.02 * u), hr_dir=(-0.06 - 0.12 * u, -1.0, -0.04),
                    hr_up=(0.0, 0.0, 1.0), el_r=(-0.3, 0.3, -0.9),
                    hl=(0.5 - 0.04 * u, 0.42 + 0.02 * u, 1.42), hl_dir=(0.4, 0.8, -0.2), hl_up=(0.5, -0.2, 0.85), el_l=(0.8, 0.2, -0.4),
                    r=air(-0.4 + 0.04 * u, -0.1 + 0.08 * u, 0.32 - 0.02 * u, pitch=-6.0 + 3.0 * u, yaw=-20.0 + 6.0 * u),
                    l=air(-0.06 + 0.06 * u, 0.34 + 0.02 * u, 0.5 - 0.05 * u, pitch=24.0 - 6.0 * u, yaw=10.0 + 4.0 * u))
    cut = cut_pose(CONTACT, 0.0)
    POSES["paso del viento al costado"] = arms(cut, 2, left=cut["_left_p2"])
    keys.append((CONTACT, cut, "lin", {"turn": "lin", "travel": "lin"}))
    keys.append((18, cut_pose(18, 0.33), "lin", {"turn": "lin", "travel": "lin"}))
    keys.append((19, cut_pose(19, 0.67), "lin", {"turn": "lin", "travel": "lin"}))
    keys.append((HOLD, cut_pose(HOLD, 1.0), "lin", {"turn": "lin", "travel": "lin"}))
    # suelta el corte y gira en el aire: la derecha barre hasta su derecha y atrás, la izquierda viene adelante y las
    # piernas pasan por debajo para apoyar de espaldas al carril
    sw = body(21, hips=(0.0, -0.04, -0.41), hrot=(8.0, 4.0, -2.0), spine=(15.0, 0.0, -14.0), chest=(5.0, 0.0, -12.0),
              neck=(-11.0, 0.0, 10.0), head=(-13.0, 0.0, 12.0),
              hr=(-0.62, -0.52, 1.24), hr_dir=(-0.8, -0.6, 0.05), hr_up=(0.0, -0.1, 1.0), el_r=(-0.3, 0.5, -0.8),
              hl=(0.42, -0.06, 1.4), hl_dir=(0.1, -1.0, 0.2), hl_up=(0.4, 0.0, 1.0), el_l=(0.8, 0.15, -0.45),
              r=air(-0.34, 0.04, 0.28, pitch=2.0, yaw=-12.0), l=air(0.08, 0.38, 0.38, pitch=14.0, yaw=16.0))
    keys.append((21, sw, "out", {"turn": "lin", "travel": "lin"}))
    spin = body(22, hips=(0.0, 0.02, -0.41), hrot=(8.0, 4.0, -8.0), spine=(14.0, 0.0, -14.0), chest=(4.0, 0.0, -10.0),
                neck=(-10.0, 0.0, 10.0), head=(-12.0, 0.0, 12.0),
                hr=(-0.8, -0.1, 1.3), hr_dir=(-1.0, 0.1, 0.1), hr_up=(0.0, -0.2, 1.0), el_r=(-0.3, 0.6, -0.7),
                hl=(0.32, -0.46, 1.38), hl_dir=(-0.2, -1.0, 0.2), hl_up=(0.3, 0.0, 1.0), el_l=(0.8, 0.1, -0.5),
                r=air(-0.3, 0.12, 0.26, pitch=4.0, yaw=-8.0), l=air(0.18, 0.4, 0.3, pitch=10.0, yaw=20.0))
    keys.append((22, spin, "out", {"turn": "lin", "travel": "lin"}))
    # apoya (DashEnd): el derecho adelante del frenado (detrás de él, para donde va), el izquierdo todavía en el aire;
    # los pies quedan clavados donde termina en la guardia (el cuerpo frena pasando por encima)
    fin = at_pose(arms(BODY, 2, right=True), T_END, -180.0)
    RF, LF = fin["foot_r"], fin["foot_l"]
    land = body(LAND, hips=(0.0, 0.1, -0.45), hrot=(12.0, 0.0, 12.0), spine=(18.0, 0.0, 0.0), chest=(6.0, 0.0, 0.0),
                neck=(-10.0, 0.0, -6.0), head=(-14.0, 0.0, -8.0),
                hr=(-0.4, -0.5, 1.5), hr_dir=(0.0, -0.4, 1.0), hr_up=(-0.3, 1.0, 0.2), el_r=(-0.7, 0.3, -0.6),
                hl=(0.42, -0.36, 1.32), hl_dir=(0.2, -0.3, 1.0), hl_up=(0.25, 1.0, 0.25), el_l=(0.7, 0.3, -0.7),
                r=None, l=air(0.26, 0.1, 0.24, pitch=-8.0, yaw=34.0))
    land["foot_r"], land["foot_r_rot"], land["toe_r"] = RF, fin["foot_r_rot"], 0.0
    keys.append((LAND, land, "out", {"turn": "lin", "travel": "lin"}))
    absorb = mod(land, hips=(0.0, 0.08, -0.36), spine=(10.0, 0.0, 2.0))
    keys.append((26, mod(absorb, travel=trav(26)), "out", {"travel": "out2"}))
    settle = mod(fin, hips=(0.02, 0.07, -0.16), travel=trav(29))
    settle["foot_r"], settle["foot_l"] = RF, LF
    keys.append((29, settle, "inout", {"travel": "out2"}))
    keys.append((32, mod(fin, hips=(0.02, 0.065, -0.1)), "inout"))
    keys.append((N, fin, "sine"))
    for k in keys:
        if k[0] > PUSH:
            k[1]["turn"] = turn_at(k[0])
    # los apoyos (pista aparte de los pies, una clave por cuadro): el derecho baja ENCIMA de su huella en f22 y apoya en
    # f23; el izquierdo, en f26 sobre su lugar de la guardia
    s21 = keys[[k[0] for k in keys].index(21)][1]
    rtrack = [(21, (s21["foot_r"], s21["foot_r_rot"], 0.0), "lin"),
              (22, (tuple(Vector(RF) + Vector((0.0, 0.0, 0.06))), fin["foot_r_rot"], 0.0), "out"),
              (LAND, (tuple(RF), fin["foot_r_rot"], 0.0), "in2"), (N, (tuple(RF), fin["foot_r_rot"], 0.0), "lin")]
    ltrack = [(21, (s21["foot_l"], s21["foot_l_rot"], 0.0), "lin"), (LAND, (land["foot_l"], land["foot_l_rot"], 0.0), "lin"),
              (25, (tuple(Vector(LF) + Vector((0.0, 0.08, 0.05))), fin["foot_l_rot"], 0.0), "out"),
              (26, (tuple(LF), fin["foot_l_rot"], 0.0), "inout"), (N, (tuple(LF), fin["foot_l_rot"], 0.0), "lin")]
    steps = [(f, st, e) for f, st, e in feet_track(rtrack, ltrack, N, r0=rtrack[0][1], l0=ltrack[0][1]) if f >= 21]
    keys = [(k[0], arms(k[1], 2, left=k[1].get("_left_p2")) if k[0] < 29 else arms(k[1], 2, right=True)) + tuple(k[2:]) for k in keys]
    return add("DashStrike_Pass", N, keys, ph=2, variant=False, steps=steps,
               timing={"tell": [0, APEX], "apex": APEX, "hold": [6, APEX], "contact": CONTACT, "active": [CONTACT, 20],
                       "recover": [20, N], "lunge": [APEX, 31, round(T_END, 3)], "air": [PUSH + 1, LAND - 1], "release_rate": RR,
                       "root_max": 26.0, "kind": RED, "glow": "Master_GlintHandR", "strike": PALM_R, "spin": True,
                       "chain_from": "READY", "chain_to": "READY"},
               events=[{"frame": APEX, "fn": "Apex"}, {"frame": PUSH, "fn": "DashStart"}, {"frame": CONTACT, "fn": "Strike"},
                       {"frame": LAND, "fn": "DashEnd"}, {"frame": LAND, "fn": "Step"}, {"frame": 26, "fn": "Step"}],
               notes=f"paso del viento al costado: igual que DashStrike hasta la suelta (f{APEX}), vuela por al lado de Kaito "
                     f"girando hacia él (turn, el jefe gira el transform), lo corta de frente en el cruce (f{CONTACT}) y le "
                     f"sostiene los dedos encima hasta f{HOLD}, gira en el aire hasta quedar de espaldas al carril y apoya en "
                     f"f{LAND} y f26 frenando hacia atrás hasta la guardia")
