"""Clips del abuelo (Nindo/Art/Models/Characters/Grandpa.fbx) en el marco de autoría de team_rig. 1.45 m con el
sombrero, piernas de 0.37 m y brazos cortitos (0.38 m): un viejito encorvado. El FBX trae también al ninja del secuestro
(esqueleto '.001', 1.32 m, brazos de 0.32 m): en Kidnap y Dragged los dos se autoran juntos (clip.partner).

  * Idle (2.5 s): encorvado con las manos atrás, respira con los hombros, cabecea y mira alrededor.
  * Walk (0.8 s, 0.8 m/s): pasitos cortos, encorvado, las manos atrás. Es el hijo del blend de NPC (Speed 0.5) y además
    un estado propio (el final lo pide por nombre con SlideTo a WALK_SPEED).
  * Kidnap (1.9 s, el prólogo): el ninja carga desde adelante, pasa por el costado izquierdo del abuelo y en la pasada
    le agarra la muñeca izquierda (f17); frena en seco y tira: el abuelo gira, trastabilla y cae sentado (f27). Se
    agarran de las muñecas (el abuelo le cierra la mano sobre la muñeca al ninja, f24-f32), el abuelo estira la otra
    mano hacia Kaito y en los últimos 10 cuadros arranca el arrastre (el grupo acelera de 0 a DRAG_SPEED dentro del
    clip). Termina en el cuadro 0 de Dragged: NPC.Kidnap pasa a Dragged en seco y empieza a correr el transform.
  * Dragged (2.67 s, loop, DRAG_SPEED m/s): el ninja camina inclinado tirando, el brazo izquierdo atrás; el abuelo
    sentado, el brazo izquierdo estirado hacia él y las dos manos trabadas en las muñecas. Los talones se clavan y se
    arrastran por turno (patalea para frenar: polvo en NPC); un tirón fuerte en el segundo ciclo, la mano derecha hacia
    Kaito en el tercero, rendido en el cuarto. Los pies del ninja quedan clavados en el mundo a la velocidad del arrastre.
  * Bound (3 s, loop): de rodillas en seiza delante del poste (el zócalo de piedra del binding_post empieza 0.1 m
    detrás de su transform: los pies no pueden ir más atrás), las muñecas cruzadas atrás, la cabeza gacha; respira y una
    vez por vuelta forcejea con los hombros y levanta la cabeza. Las vueltas de ShadowRopes van a BOUND_ROPES.
  * Freed (3.6 s): libre, trae los brazos adelante, se frota una muñeca y la otra, levanta la vista hacia Kaito, mete
    los dedos de los pies, se apoya en las rodillas y se para (a lo viejo, sin pasos) y termina en el cuadro 0 de Idle.
"""
import math
from mathutils import Vector, Euler
import bpy
import nindo_anim as NA
import team_rig as T

Key = NA.Key
WALK_SPEED = 0.8
# NPC.Update pide Speed 0.5 al caminar: con este umbral camina entero
LOCOMOTION = (("Idle", 0.0), ("Walk", 0.5))
# NPC.DragSpeed: lo que corre el transform del NPC 'kidnap' mientras suena Dragged (pasos del ninja clavados a esto)
DRAG_SPEED = 0.8
DRAG_STEP = 20                  # un ciclo de pasos del ninja (dos pasos de 0.27 m)
DRAG_N = 4 * DRAG_STEP
KID_N = 57
# el puño derecho del ninja al correr: los nudillos adelante y abajo, la palma hacia adentro (sin pedirlo, el antebrazo
# rodaba 76° en un cuadro al pasar la mano por el hombro)
RUN_DIR, RUN_PALM = (0.0, -0.3, -1.0), (1.0, 0.0, 0.0)
RUN_ARM = dict(hand_r_dir=RUN_DIR, hand_r_palm=RUN_PALM, elbow_r=(-1.0, 0.3, 0.0))
# agarre de muñecas: el puño de cada uno a GRIP_T de la muñeca del otro, sobre su antebrazo, a GRIP_R del eje
GRIP_T, GRIP_R = 0.035, 0.022
GRAB, IMPACT, DRAG_START = 17, 27, 47
# vueltas de las cuerdas de sombra (m sobre los pies) para la pose de Bound: muñecas, codos y brazos/pecho
# (NPC.BoundRopeLoops: se imprimen medidas en el log, línea BOUND)
BOUND_ROPES = (0.48, 0.58, 0.66)

STANCE = dict(
    hips=(0.0, 0.02, -0.03), hips_rot=(10.0, 0.0, 0.0), spine=(16.0, 0.0, 0.0), head=(-18.0, 0.0, 0.0),
    knee_r=(-0.2, -1.0, 0.0), knee_l=(0.2, -1.0, 0.0),
    hand_r=(-0.07, 0.17, 0.66), hand_r_dir=(0.6, 0.2, -0.75), hand_r_palm=(0.0, 1.0, 0.0), elbow_r=(-1.0, 0.6, 0.0),
    hand_l=(0.07, 0.19, 0.68), hand_l_dir=(-0.6, 0.2, -0.75), hand_l_palm=(0.0, 1.0, 0.0), elbow_l=(1.0, 0.6, 0.0),
    fist_r=0.4, fist_l=0.5, breath=0.0,
)
R0, L0 = (-0.10, 0.0, -12.0), (0.10, 0.0, 12.0)


def P(**kw):
    d = dict(STANCE)
    d.update(kw)
    return d


def FR(f, dy=0.0, dx=0.0, yaw=None, pitch=0.0, z=0.0, ease="inout", lift=None):
    return T.FootKey(f, R0[0] + dx, R0[1] - dy, R0[2] if yaw is None else yaw, pitch, z, 0.0, ease, lift)


def FL(f, dy=0.0, dx=0.0, yaw=None, pitch=0.0, z=0.0, ease="inout", lift=None):
    return T.FootKey(f, L0[0] + dx, L0[1] - dy, L0[2] if yaw is None else yaw, pitch, z, 0.0, ease, lift)


PLANTED = {"r": [FR(0)], "l": [FL(0)]}


def clips(ch):
    kid, drag = kidnap_and_dragged(ch)
    return [idle(), walk(ch), kid, drag, bound(ch), freed(ch)]


# los dos clips del secuestro arrancan/terminan en la misma pose: Unity pasa de Kidnap a Dragged sin fundido
BLENDS = [("Dragged", 0, "Kidnap", -1)]


# =============================================================================== utilidades
def ramp(f, a, b, ease="inout"):
    """0 antes de a, 1 después de b, con la curva 'ease' en el medio."""
    if b <= a:
        return 1.0 if f >= a else 0.0
    return NA.ease(ease, (f - a) / float(b - a))


def lerp3(a, b, s):
    return tuple(a[i] + (b[i] - a[i]) * s for i in range(3))


def slerp3(a, b, s):
    return tuple(NA.slerp_dir(a, b, s))


def sampler(name, n, keys, loop=False):
    """Interpolación de claves (los arcos de nindo_anim) para armar los controles cuadro a cuadro."""
    c = T.TeamClip(name, n, keys, loop=loop)
    return lambda f: dict(c.controls(f))


def dense(name, n, rows, loop=False, **kw):
    """Clip con una clave por cuadro (los controles ya calculados: contactos, pies, capas por ciclo)."""
    return T.TeamClip(name, n, [Key(f, rows[f], "lin") for f in range(n + 1)], loop=loop, **kw)


def foot_offsets(ch, k):
    """Vértices de la suela y el empeine de un pie respecto del tobillo (marco de autoría, reposo)."""
    names = {ch.side[k]["foot"]}
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    ank = ch.land["ankle_" + k]
    for o in ch.meshes:
        gi = {g.index for g in o.vertex_groups if g.name in names}
        if not gi:
            continue
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        for v in o.data.vertices:
            if sum(g.weight for g in v.groups if g.group in gi) > 0.5:
                out.append(ch.Pc(ch.Ai @ (oe.matrix_world @ me.vertices[v.index].co)) - ank)
        oe.to_mesh_clear()
    return out


def foot_on_floor(ch, offs, k, x, y, pitch, yaw=0.0, roll=0.0, clear=0.004):
    """Tobillo y giro de un pie girado 'pitch' (seiza: el empeine en el piso) con el punto más bajo a 'clear' del piso."""
    R = Euler((math.radians(pitch), math.radians(roll), math.radians(yaw)), 'XYZ').to_matrix()
    z = -min((R @ v).z for v in offs) + clear
    return (x, y, z), (pitch, roll, yaw)


class Probe:
    """Resuelve cuadros sueltos de los dos esqueletos para medir dónde quedan hombros, muñecas y puños (sin el camino
    de Viterbi del horneado: las muñecas van adonde se piden, el codo puede elegir otro giro, que no mueve la mano)."""

    def __init__(self, ch):
        self.ch, self.kid = ch, ch.partner
        self.gs, self.ks = T.TeamSolver(ch), T.TeamSolver(ch.partner)

    def solve(self, gc, kc=None):
        pose = NA.Pose(self.ch.rig)
        self.gs.solve(pose, gc)
        if kc is not None:
            T.drop_kid(self.ch, pose)
            self.ks.solve(pose, kc)
        return pose

    def shoulder(self, pose, c, k):
        return pose.get(c.side[k]["upper"]).translation.copy()

    def wrist(self, pose, c, k):
        return pose.get(c.side[k]["hand"]).translation.copy()


# =============================================================================== Idle / Walk
IDLE_N = 75


def idle_pose(f):
    a = 2.0 * math.pi * f / IDLE_N
    b = 2.0 * math.pi * 2.0 * f / IDLE_N
    return P(hips=(0.01 * math.sin(a), 0.02, -0.03 - 0.006 * (0.5 - 0.5 * math.cos(b))), breath=0.5 - 0.5 * math.cos(b),
             spine=(16.0 - 2.0 * math.sin(b), 1.5 * math.sin(a), 0.0),
             head=(-18.0 + 5.0 * math.sin(b + 0.5), 0.0, 14.0 * math.sin(a + 1.0)))


def idle():
    keys = [Key(f, idle_pose(f), "sine") for f in range(0, IDLE_N + 1, 15)]
    return T.TeamClip("Idle", IDLE_N, keys, loop=True, feet=PLANTED, notes="encorvado, manos atrás, respira y mira alrededor")


def walk(ch):
    n = 24
    g = T.gait2(ch, n, WALK_SPEED, 0.62, {"r": (-0.09, 0.0, -10.0), "l": (0.09, 0.0, 10.0)}, lift=0.05, toe_off=14.0, heel=-8.0)

    def fn(f):
        a = 2.0 * math.pi * f / n
        c = dict(STANCE)
        c.update(g(f))
        c["hips"] = (-0.015 * math.sin(a), 0.02, -0.05 - 0.008 * math.cos(2 * a))
        c["hips_rot"] = (12.0, 3.0 * math.sin(a), 5.0 * math.sin(a))
        c["spine"] = (18.0, -2.0 * math.sin(a), -4.0 * math.sin(a))
        c["head"] = (-20.0 + 2.0 * math.cos(2 * a), 0.0, 2.0 * math.sin(a))
        return c
    return NA.ProcClip("Walk", n, fn, loop=True, root_vel=(0, -WALK_SPEED, 0), notes="pasitos cortos encorvado, 0.8 m/s")


# =============================================================================== Kidnap + Dragged (los dos esqueletos)
class Duo:
    """Los dos personajes del FBX: conversión entre el marco del abuelo (g) y el del ninja (n), alcances y el agarre."""

    def __init__(self, ch):
        self.ch, self.kid = ch, ch.partner
        self.probe = Probe(ch)
        R = ch.rig
        # alcance del hombro a la cabeza de la mano (en el abuelo la muñeca está 4.9 cm más allá del antebrazo)
        self.reach = {who: (R.rest[c.side["l"]["hand"]].translation - R.rest[c.side["l"]["upper"]].translation).length / ch.u
                      for who, c in (("g", ch), ("n", self.kid))}
        self.up = ch.D((0, 0, 1))
        self.report = []

    def g2n(self, p):
        return tuple(self.kid.Pc(self.ch.P(p)))

    def kid_rest(self):
        """La pose fija del ninja (kid_pose, con la que respira el NPC 'kidnap' en Idle) leída como controles y apoyos."""
        kid, kp = self.kid, self.ch.kid_pose
        c = dict(hips=tuple(kid.Pc(kp[kid.spec["pelvis"]].translation) - kid.land["pelvis"]), fist_r=0.3, fist_l=0.3)
        for k in "rl":
            # desde el hombro, como el resto de las claves del ninja
            c["hand_%s_rel" % k] = tuple(kid.Pc(kp[kid.side[k]["hand"]].translation) - kid.Pc(kp[kid.side[k]["upper"]].translation))
        return c, {k: tuple(kid.Pc(kp[kid.side[k]["foot"]].translation)) for k in "rl"}

    def resolve(self, f, g, n, wa=1.0, wb=1.0, wc=1.0):
        """Controles finales de un cuadro: las manos pedidas relativas al hombro ('hand_k_rel', m en el marco de cada uno)
        y el agarre de muñecas. El agarre va sobre la recta de hombro izquierdo a hombro izquierdo: la muñeca del abuelo
        al 56 % (sin pasar el 94 % de su brazo), la del ninja 1 cm más allá y las dos corridas 1.3 cm a cada lado de la
        recta (la del ninja arriba, palma abajo; la del abuelo abajo, palma arriba): cada mano envuelve la muñeca del otro.
        wa: la muñeca del abuelo va del pedido a la recta (lo arrastran del brazo); wb: la mano del ninja llega a ella;
        wc: el abuelo cierra la mano sobre la muñeca del ninja."""
        ch, kid = self.ch, self.kid
        # un canal que ninguna clave vecina pide sale None: es como no pedirlo
        g, n = ({k: v for k, v in d.items() if v is not None} for d in (g, n))
        base = lambda d: {k: v for k, v in d.items() if not k.endswith(("_rel", "_relw"))}
        # 'hand_k_relw' mezcla la mano pedida en el marco (0) con la pedida desde el hombro (1). El hombro sale del cuadro
        # resuelto, y ese cuadro necesita la mano: si no, la clavícula se estira hacia la muñeca de reposo (20°, el hombro
        # corrido 15 cm). Tres pasadas: mano desde el hombro de reposo, desde el resuelto, otra vez
        rels = []
        for c, d in ((ch, g), (kid, n)):
            for k in "rl":
                rel, w = d.pop("hand_%s_rel" % k, None), d.pop("hand_%s_relw" % k, 1.0)
                if rel is not None:
                    rels.append((c, d, k, Vector(rel), w, d.get("hand_" + k)))
                    d["hand_" + k] = tuple(c.land["shoulder_" + k] + Vector(d.get("hips", (0, 0, 0))) + Vector(rel))
        for _ in range(3):
            pose = self.probe.solve(base(g), base(n))
            for c, d, k, rel, w, absk in rels:
                p = c.Pc(pose.get(c.side[k]["upper"]).translation) + rel
                d["hand_" + k] = tuple(Vector(absk).lerp(p, w)) if absk is not None else tuple(p)
        Sg = pose.get(ch.side["l"]["upper"]).translation
        Sn = pose.get(kid.side["l"]["upper"]).translation
        u = Sn - Sg
        D = u.length / ch.u
        u.normalize()
        # los dos brazos casi estirados (se lee el tirón): el del ninja hasta el 92 %, el resto lo pone el abuelo
        M = Sg + u * (min(self.reach["g"] * 0.94, max(D * 0.56, D - self.reach["n"] * 0.92)) * ch.u)
        side = (self.up - u * self.up.dot(u)).normalized()
        Wg = M - side * (0.013 * ch.u)
        Wn = M + u * (0.01 * ch.u) + side * (0.013 * ch.u)
        gW = ch.P(g["hand_l"]).lerp(Wg, wa) if "hand_l" in g else Wg
        g["hand_l"] = tuple(ch.Pc(gW))
        ug, sg = tuple(ch.Dc(u)), tuple(ch.Dc(side))
        g["hand_l_dir"] = slerp3(g.get("hand_l_dir", ug), ug, wc)
        g["hand_l_palm"] = slerp3(g.get("hand_l_palm", sg), sg, wc)
        g["fist_l"] = g.get("fist_l", 0.3) + (0.85 - g.get("fist_l", 0.3)) * wc
        if wb > 0.0:
            nW = kid.P(n["hand_l"]).lerp(gW + (Wn - Wg), wb) if "hand_l" in n else gW + (Wn - Wg)
            un, sn = tuple(kid.Dc(-u)), tuple(kid.Dc(-side))
            n["hand_l"] = tuple(kid.Pc(nW))
            n["hand_l_dir"] = slerp3(n.get("hand_l_dir", un), un, wb)
            n["hand_l_palm"] = slerp3(n.get("hand_l_palm", sn), sn, wb)
            n["fist_l"] = n.get("fist_l", 0.3) + (0.9 - n.get("fist_l", 0.3)) * wb
            # el puño de cada uno sobre el antebrazo del otro (GRIP_T más allá de su muñeca, por encima o por debajo a
            # GRIP_R del eje): se corrige con lo que da el cuadro resuelto (el puño cae donde lo dejan la muñeca y el
            # enderezado del solver, no donde se pidió). El ninja corrige entero; el abuelo, a medias y solo cuando cierra
            # la mano (el que manda es el que tira)
            t, r = GRIP_T * ch.u, GRIP_R * ch.u
            for _ in range(4):
                pose = self.probe.solve(base(g), base(n))
                Fg, Fn = self.fist(pose, ch), self.fist(pose, kid)
                wg_, eg = self.forearm(pose, ch)
                wn_, en = self.forearm(pose, kid)
                Pn = wg_ + (eg - wg_).normalized() * t + side * r
                Pg = wn_ + (en - wn_).normalized() * t - side * r
                nW = kid.P(n["hand_l"]) + (Pn - Fn) * wb
                gW = ch.P(g["hand_l"]) + (Pg - Fg) * (0.5 * wc)
                n["hand_l"], g["hand_l"] = tuple(kid.Pc(nW)), tuple(ch.Pc(gW))
        self.report.append((f, round(D, 3), round(wa, 2), round(wb, 2)))
        return g, n

    def fist(self, pose, c):
        return pose.get(c.side["l"]["hand"]) @ c.hand_info["l"]["fist"]

    def forearm(self, pose, c):
        """(muñeca, codo) del brazo izquierdo resuelto."""
        return pose.get(c.side["l"]["hand"]).translation.copy(), pose.get(c.side["l"]["fore"]).translation.copy()

    def contacts(self, g, n):
        """Lo que quedó de verdad: cada puño contra el antebrazo del otro (cm a su eje, cm desde la muñeca del otro)."""
        ch, kid = self.ch, self.kid
        pose = self.probe.solve(g, n)
        out = []
        for a, b in ((ch, kid), (kid, ch)):
            F = pose.get(a.side["l"]["hand"]) @ a.hand_info["l"]["fist"]
            w = pose.get(b.side["l"]["hand"]).translation
            e = pose.get(b.side["l"]["fore"]).translation
            ax = (e - w).normalized()
            t = max(0.0, (F - w).dot(ax))
            d = (F - (w + ax * t)).length
            out.append((round(d / ch.u * 100.0, 1), round(t / ch.u * 100.0, 1)))
        return out


def drag_waves(f):
    """Capas por cuadro del ciclo de arrastre (f en 0..DRAG_N): empujes de cada paso, el tirón, la mano hacia Kaito."""
    tau = 2.0 * math.pi
    surge_n = 0.5 - 0.5 * math.cos(tau * (f - 4) / (DRAG_STEP / 2))          # cada paso del ninja, al empujar
    surge_g = 0.5 - 0.5 * math.cos(tau * (f - 7) / (DRAG_STEP / 2))          # el abuelo llega 3 cuadros después
    yank = math.sin(math.pi * (f - 20) / 20.0) ** 2 if 20 <= f <= 40 else 0.0
    reach = math.sin(math.pi * (f - 40) / 20.0) ** 2 if 40 <= f <= 60 else 0.0
    # pataleo: entero en los tres primeros ciclos, casi nada en el cuarto (se rinde y se deja arrastrar)
    amp = 0.62 - 0.38 * math.cos(tau * (f - 70) / DRAG_N)
    return surge_n, surge_g, yank, reach, amp


# talones del abuelo en el arrastre (marco del abuelo): se clavan en el mundo un cuarto de ciclo (la pierna se estira),
# se arrastran (el polvo de NPC) y la rodilla se vuelve a doblar para clavarlos más cerca. Con 'amp' < 1 el talón
# resbala aunque lo clave: en el cuarto ciclo casi no patalea
HEEL_PLANT, HEEL_STICK = -0.08, DRAG_SPEED * (DRAG_STEP / 4) / NA.FPS
HEEL_X = {"r": (-0.10, -18.0), "l": (0.13, 22.0)}
HEEL_PHASE = {"r": 0, "l": DRAG_STEP // 2}


def heel_params(k, f, amp):
    """(x, y, yaw, pitch, alto) de un talón que patalea, fase propia de cada pie."""
    q = ((f + HEEL_PHASE[k]) % DRAG_STEP) / float(DRAG_STEP)
    y0, y1 = HEEL_PLANT, HEEL_PLANT - HEEL_STICK
    lift, pitch = 0.0, -30.0
    if q < 0.25:
        y = y0 + (y1 - y0) * (q / 0.25)
    elif q < 0.55:
        y = y1
        pitch = -30.0 + 10.0 * NA.ease("inout", (q - 0.25) / 0.3)
    else:
        u = (q - 0.55) / 0.45
        y = y1 + (y0 - y1) * NA.ease("inout", u)
        lift = 0.035 * math.sin(math.pi * u)
        pitch = -20.0 - 10.0 * NA.ease("inout", u)
    ym = 0.5 * (y0 + y1)
    x, yaw = HEEL_X[k]
    return x, ym + (y - ym) * amp, yaw, pitch, lift


# disposición del arrastre (marco del abuelo): la cadera del abuelo casi en el piso, el ninja 0.8 m adelante en el sentido
# del arrastre (+Y: la espalda del abuelo) y 0.45 m a la izquierda del abuelo (del lado de la cámara del prólogo)
G_HIPS = (0.02, 0.12, -0.205)
N_PELVIS_G = (0.42, 0.83)
NINJA_DUTY = 0.62
# los últimos cuadros de Kidnap el grupo acelera de quieto a DRAG_SPEED: arranca LAUNCH_SHIFT m atrás de la disposición
LAUNCH = KID_N - DRAG_START
LAUNCH_SHIFT = DRAG_SPEED * LAUNCH / NA.FPS / 2.0


def drag_frame(duo, f, gait):
    """Controles del cuadro f de Dragged para el abuelo y el ninja (manos relativas al hombro; el agarre, en resolve)."""
    ch, kid = duo.ch, duo.kid
    surge_n, surge_g, yank, reach, amp = drag_waves(f)
    tau = 2.0 * math.pi
    st = tau * f / DRAG_STEP
    g = dict(
        hips=(G_HIPS[0], G_HIPS[1] + 0.012 * surge_g - 0.025 * yank, G_HIPS[2] + 0.008 * surge_g + 0.01 * yank),
        hips_rot=(-20.0 - 6.0 * yank + 2.0 * surge_g, 4.0, 10.0 + 4.0 * yank),
        spine=(-2.0 - 3.0 * yank, 2.0, 4.0 + 2.0 * yank), head=(34.0 - 16.0 * reach - 6.0 * yank, 0.0, -4.0 - 10.0 * reach),
        breath=0.5 - 0.5 * math.cos(tau * f / (DRAG_STEP / 2)),
        knee_r=(-0.3, -1.0, 0.6), knee_l=(0.3, -1.0, 0.6),
        hand_r_rel=lerp3((-0.15, -0.10, -0.25), (-0.04, -0.31, -0.10), reach), fist_r=0.6 - 0.5 * reach,
        hand_r_dir=slerp3((0.0, -0.4, -1.0), (0.0, -1.0, -0.2), reach),
        hand_r_palm=slerp3((1.0, 0.0, 0.0), (0.0, -0.2, -1.0), reach),
        elbow_r=(-1.0, 0.3, -0.5), elbow_l=(1.0, 0.0, -0.6), auto_drop=0.0,
    )
    for k in "rl":
        x, y, yaw, pitch, lift = heel_params(k, f, amp)
        g["foot_" + k], g["foot_%s_rot" % k] = ch.foot_at(k, x, y, yaw, pitch, 0.0, lift)
    n0 = duo.g2n((N_PELVIS_G[0], N_PELVIS_G[1], kid.land["pelvis"].z))
    bob = 0.012 * (0.5 - 0.5 * math.cos(tau * f / (DRAG_STEP / 2)))
    n = dict(
        hips=(n0[0], n0[1] - 0.012 * surge_n + 0.02 * yank, -0.072 + bob - 0.01 * yank),
        hips_rot=(22.0 + 4.0 * yank, -3.0 * math.sin(st), 10.0 + 6.0 * math.sin(st)),
        spine=(8.0 + 4.0 * yank, 0.0, 8.0), head=(-16.0 + 6.0 * yank, 0.0, -10.0 + 55.0 * yank),
        hand_r_rel=(-0.05, 0.10 * math.cos(st) - 0.03, -0.24), fist_r=0.9, elbow_r=(-1.0, 0.3, 0.0), elbow_l=(0.6, 0.2, -0.8),
        hand_r_dir=RUN_DIR, hand_r_palm=RUN_PALM,
    )
    n.update(gait(f))
    return g, n


def shift_g(d, dy, feet=("l",)):
    """El abuelo corrido dy en el sentido del arrastre (+Y de su marco): cadera, manos y los pies pedidos."""
    d = dict(d)
    for key in ["hips", "hand_r", "hand_l"] + ["foot_" + k for k in feet]:
        if d.get(key) is not None:
            p = d[key]
            d[key] = (p[0], p[1] + dy, p[2])
    return d


def shift_n(d, dy):
    """El ninja corrido dy en el sentido del arrastre (que en su marco es -Y): cadera y manos (los pies, clavados)."""
    d = dict(d)
    for key in ("hips", "hand_r", "hand_l"):
        if d.get(key) is not None:
            p = d[key]
            d[key] = (p[0], p[1] - dy, p[2])
    return d


def kidnap_and_dragged(ch):
    duo = Duo(ch)
    kid = duo.kid
    zr = kid.land["pelvis"].z
    n0 = duo.g2n((N_PELVIS_G[0], N_PELVIS_G[1], zr))
    ym = n0[1] + 0.07                              # los apoyos un poco detrás de la cadera: empuja inclinado
    feet_n = {"r": (n0[0] - 0.095, ym, -8.0), "l": (n0[0] + 0.095, ym, 8.0)}
    gait = T.gait2(kid, DRAG_STEP, DRAG_SPEED, NINJA_DUTY, feet_n, lift=0.05, toe_off=25.0, heel=-12.0)

    # ---- Dragged: un cuadro por clave, ya con el agarre
    D = []
    for f in range(DRAG_N + 1):
        g, n = drag_frame(duo, f % DRAG_N, gait)
        D.append(duo.resolve(f, g, n))
    D[DRAG_N] = D[0]
    raw0 = drag_frame(duo, 0, gait)

    # ---- Kidnap: claves de cada uno hasta DRAG_START; de ahí, Dragged f0 que arranca (LAUNCH_SHIFT -> 0)
    kr, kfeet = duo.kid_rest()

    def n_at(x, y, dz):
        p = duo.g2n((x, y, zr))
        return (p[0], p[1], dz)
    G = [Key(0, dict(idle_pose(0), hand_r_relw=0.0)),
         Key(5, P(hips=(0.0, 0.03, -0.02), hand_r_relw=0.0, hips_rot=(5.0, 0.0, 0.0), spine=(6.0, 0.0, 0.0), head=(-14.0, 0.0, 4.0)), "out"),
         Key(10, P(hips=(0.0, 0.05, -0.03), hand_r_relw=0.0, hips_rot=(-2.0, 0.0, 6.0), spine=(-2.0, 0.0, 6.0), head=(-6.0, 0.0, 16.0),
                   hand_r=(-0.16, -0.18, 0.84), hand_r_dir=(0.1, -0.5, 0.85), hand_r_palm=(0.0, -1.0, 0.2), elbow_r=(-1.0, 0.3, -0.6),
                   hand_l=(0.18, -0.17, 0.86), hand_l_dir=(-0.1, -0.5, 0.85), hand_l_palm=(0.0, -1.0, 0.2), elbow_l=(1.0, 0.3, -0.6),
                   fist_r=0.2, fist_l=0.2)),
         Key(15, P(hips=(0.0, 0.05, -0.03), hand_r_relw=0.0, hips_rot=(-4.0, 0.0, 16.0), spine=(-3.0, 0.0, 12.0), head=(-4.0, 0.0, 40.0),
                   hand_r=(-0.06, -0.20, 0.86), hand_r_dir=(0.3, -0.5, 0.8), hand_r_palm=(0.0, -1.0, 0.2), elbow_r=(-1.0, 0.3, -0.6),
                   hand_l=(0.30, -0.04, 0.86), hand_l_dir=(0.6, -0.2, 0.8), hand_l_palm=(1.0, -0.3, 0.0), elbow_l=(1.0, 0.3, -0.6),
                   fist_r=0.2, fist_l=0.2)),
         Key(21, P(hips=(0.03, 0.04, -0.08), hips_rot=(-14.0, 4.0, 30.0), spine=(-6.0, 2.0, 10.0), head=(12.0, 0.0, 20.0),
                   hand_r_rel=(-0.30, 0.06, -0.12), hand_r_dir=(-1.0, 0.0, 0.2), hand_r_palm=(0.0, -1.0, 0.0), elbow_r=(-0.6, 0.8, -0.4),
                   hand_l=(0.34, 0.12, 0.82), hand_l_dir=(0.4, 0.8, 0.3), hand_l_palm=(1.0, 0.0, 0.0), elbow_l=(1.0, 0.0, -0.6),
                   fist_r=0.1, fist_l=0.2, hand_r_relw=1.0, auto_drop=0.0), "in2"),
         Key(IMPACT, P(hips=(0.02, G_HIPS[1] - LAUNCH_SHIFT, -0.195), hips_rot=(-24.0, 4.0, 13.0), spine=(-4.0, 2.0, 4.0),
                       head=(38.0, 0.0, -4.0), hand_r_rel=(-0.20, 0.0, -0.26), hand_r_dir=(0.0, -0.4, -1.0), hand_r_palm=(1.0, 0.0, 0.0),
                       elbow_r=(-1.0, 0.3, -0.5), elbow_l=(1.0, 0.0, -0.6), fist_r=0.3, fist_l=0.3, knee_r=(-0.3, -1.0, 0.6),
                       knee_l=(0.3, -1.0, 0.6)), "in2"),
         Key(31, P(hips=(0.02, G_HIPS[1] - LAUNCH_SHIFT, -0.198), hips_rot=(-20.0, 4.0, 11.0), spine=(-3.0, 2.0, 4.0),
                   head=(30.0, 0.0, -6.0), hand_r_rel=(-0.17, -0.04, -0.25), hand_r_dir=(0.0, -0.4, -1.0), hand_r_palm=(1.0, 0.0, 0.0),
                   elbow_r=(-1.0, 0.3, -0.5), fist_r=0.4), "out"),
         Key(39, P(hips=(0.02, G_HIPS[1] - LAUNCH_SHIFT, -0.202), hips_rot=(-21.0, 4.0, 10.0), spine=(-2.0, 2.0, 4.0),
                   head=(16.0, 0.0, -14.0), hand_r_rel=(-0.04, -0.31, -0.10), hand_r_dir=(0.0, -1.0, -0.2), hand_r_palm=(0.0, -0.2, -1.0),
                   elbow_r=(-1.0, 0.3, -0.5), fist_r=0.1)),
         Key(DRAG_START, shift_g(raw0[0], -LAUNCH_SHIFT, feet=()))]
    # el ninja: f0 = kid_pose; se agacha, corre por el costado izquierdo del abuelo, agarra (GRAB), frena en seco y tira
    N = [Key(0, kr),
         Key(6, dict(hips=n_at(0.0, -1.26, -0.08), hips_rot=(24.0, 0.0, 0.0), spine=(12.0, 0.0, 0.0), head=(-18.0, 0.0, 0.0),
                     hand_r_rel=(-0.06, 0.15, -0.21), hand_l_rel=(0.09, -0.02, -0.22), fist_r=0.8, fist_l=0.5,
                     elbow_r=(-1.0, 0.3, 0.0), hand_r_dir=RUN_DIR, hand_r_palm=RUN_PALM, elbow_l=(1.0, 0.3, 0.0))),
         Key(10, dict(hips=n_at(0.18, -0.86, -0.05), hips_rot=(26.0, 0.0, -8.0), spine=(10.0, 0.0, -4.0), head=(-20.0, 0.0, 4.0),
                      hand_r_rel=(-0.06, -0.15, -0.17), hand_l_rel=(0.07, -0.08, -0.17), fist_r=0.9, fist_l=0.5,
                      elbow_r=(-1.0, 0.3, 0.0), hand_r_dir=RUN_DIR, hand_r_palm=RUN_PALM, elbow_l=(1.0, 0.3, 0.0),
                      hand_l_dir=(0.1, -1.0, 0.2), hand_l_palm=(0.0, 0.0, -1.0)), "in2"),
         Key(14, dict(hips=n_at(0.48, -0.36, -0.045), hips_rot=(24.0, 0.0, -4.0), spine=(10.0, 0.0, 2.0), head=(-18.0, 0.0, 22.0),
                      hand_r_rel=(-0.07, 0.12, -0.20), hand_l_rel=(0.10, -0.14, -0.12), fist_r=0.9, fist_l=0.3,
                      elbow_l=(1.0, 0.3, 0.0),
                      elbow_r=(-1.0, 0.3, 0.0), hand_r_dir=RUN_DIR, hand_r_palm=RUN_PALM), "lin"),
         Key(GRAB, dict(hips=n_at(0.60, -0.02, -0.05), hips_rot=(16.0, 0.0, 8.0), spine=(6.0, 0.0, 8.0), head=(-14.0, 0.0, 40.0),
                        hand_r_rel=(-0.17, 0.04, -0.17), fist_r=0.8, **RUN_ARM), "lin"),
         Key(20, dict(hips=n_at(0.62, 0.30, -0.10), hips_rot=(6.0, 0.0, 24.0), spine=(4.0, 0.0, 14.0), head=(-10.0, 0.0, 55.0),
                      hand_r_rel=(-0.15, -0.12, -0.17), fist_r=0.9, **RUN_ARM), "out"),
         Key(24, dict(hips=n_at(0.58, 0.52, -0.09), hips_rot=(24.0, 0.0, 16.0), spine=(8.0, 0.0, 10.0), head=(-14.0, 0.0, 30.0),
                      hand_r_rel=(-0.05, -0.14, -0.22), fist_r=0.9, **RUN_ARM)),
         Key(30, dict(hips=n_at(0.47, 0.70, -0.08), hips_rot=(22.0, 0.0, 12.0), spine=(8.0, 0.0, 8.0), head=(-16.0, 0.0, -5.0),
                      hand_r_rel=(-0.05, 0.08, -0.24), fist_r=0.9, **RUN_ARM)),
         Key(40, dict(hips=n_at(N_PELVIS_G[0], N_PELVIS_G[1] - LAUNCH_SHIFT, -0.075), hips_rot=(22.0, 0.0, 10.0),
                      spine=(8.0, 0.0, 8.0), head=(-16.0, 0.0, -10.0), hand_r_rel=(-0.05, 0.07, -0.24), fist_r=0.9, **RUN_ARM)),
         Key(DRAG_START, shift_n(raw0[1], -LAUNCH_SHIFT))]
    Gs, Ns = sampler("Kidnap/g", DRAG_START, G), sampler("Kidnap/n", DRAG_START, N)

    # apoyos. Abuelo: parado; en la pasada da un paso atrás con la izquierda y al caer los pies salen para adelante, a
    # los talones de Dragged f0 corridos LAUNCH_SHIFT (viajan con el grupo: con el derecho clavado y la cadera
    # LAUNCH_SHIFT más cerca, la rodilla subía y la túnica se metía 11 cm en el piso)
    xr, yr, yawr, pr, _ = heel_params("r", 0, drag_waves(0)[4])
    xl, yl, yawl, pl, _ = heel_params("l", 0, drag_waves(0)[4])
    gfeet = {"r": [FR(0), FR(17), T.FootKey(IMPACT, xr, yr - LAUNCH_SHIFT, yawr, pr, lift=0.012, ease="in2")],
             "l": [FL(0), FL(15), T.FootKey(21, 0.16, 0.12, 16.0, 0.0, lift=0.04),
                   T.FootKey(IMPACT, xl, yl - LAUNCH_SHIFT, yawl, pl, lift=0.015, ease="in2")]}

    # ninja: corre por fuera (sus apoyos derechos del lado de afuera; en la carrera el pie de atrás sube en arco alto, el
    # talón hacia la cola: con el arco bajo de los pasos el pie quedaba atrás y abajo y la cadera caía 8 cm para alcanzarlo), frena con la izquierda adelantada, un paso de
    # recuperación con la derecha y entra al ciclo: el último apoyo de cada pie es el de Dragged f0 (gait2 en p=0 y 0.5)
    def nk(f, x, y, yaw=0.0, pitch=0.0, lift=None, ease="inout"):
        p = duo.g2n((x, y, 0.0))
        return T.FootKey(f, p[0], p[1], yaw, pitch, 0.0, 0.0, ease, lift)
    stride = DRAG_SPEED * DRAG_STEP / NA.FPS
    hs, to = 0.14 * NINJA_DUTY, 0.62 * NINJA_DUTY
    pitch_l0 = 25.0 * NA.ease("in2", (0.5 - to) / (NINJA_DUTY - to))
    fr_end = T.FootKey(KID_N, feet_n["r"][0], ym - stride * NINJA_DUTY * 0.5, feet_n["r"][2], -12.0, lift=0.05)
    fl_end = (feet_n["l"][0], ym + stride * (0.5 - NINJA_DUTY * 0.5), feet_n["l"][2])
    nfeet = {"r": [T.FootKey(0, kfeet["r"][0], kfeet["r"][1]), T.FootKey(4, kfeet["r"][0], kfeet["r"][1], 0.0, 20.0),
                   nk(10, 0.27, -0.93, -6.0, lift=0.12), nk(11, 0.27, -0.93, -6.0, 25.0),
                   nk(GRAB, 0.74, 0.06, -10.0, lift=0.16),
                   nk(20, 0.74, 0.06, -10.0), nk(26, 0.56, 0.70, -8.0), nk(48, 0.56, 0.70, -8.0, 10.0), fr_end],
             "l": [T.FootKey(0, kfeet["l"][0], kfeet["l"][1]), T.FootKey(7, kfeet["l"][0], kfeet["l"][1], 0.0, 25.0),
                   nk(14, 0.46, -0.32, 4.0, lift=0.16), nk(16, 0.46, -0.32, 4.0, 20.0), nk(20, 0.50, 0.46, 14.0, ease="out"),
                   nk(34, 0.50, 0.46, 10.0), T.FootKey(40, *fl_end), T.FootKey(KID_N, fl_end[0], fl_end[1], fl_end[2], pitch_l0)]}

    K = []
    for f in range(KID_N + 1):
        if f >= DRAG_START:
            u = (f - DRAG_START) / float(LAUNCH)
            dy = -LAUNCH_SHIFT * (1.0 - u * u)
            g, n = shift_g(D[0][0], dy, feet=("r", "l")), shift_n(D[0][1], dy)
            if f < KID_N:
                for k in "rl":
                    n["foot_" + k], n["foot_%s_rot" % k] = T.sample_feet(kid, k, nfeet[k], f)
            K.append((g, n))
            continue
        g, n = Gs(f), Ns(f)
        for k in "rl":
            g["foot_" + k], g["foot_%s_rot" % k] = T.sample_feet(ch, k, gfeet[k], f)
            n["foot_" + k], n["foot_%s_rot" % k] = T.sample_feet(kid, k, nfeet[k], f)
        if f < 21:
            g["auto_drop"] = 1.0
        K.append(duo.resolve(f, g, n, wa=ramp(f, GRAB + 1, GRAB + 6), wb=ramp(f, GRAB - 5, GRAB), wc=ramp(f, 24, 32)))
    # el último cuadro de Kidnap ES Dragged f0 (los pies del ninja del ciclo: mismos apoyos que gait2 en f0)
    K[KID_N] = D[0]
    for k in "rl":
        a = T.sample_feet(kid, k, nfeet[k], KID_N)[0]
        b = Vector(D[0][1]["foot_" + k])
        assert (a - b).length < 0.002, f"Kidnap f{KID_N}: el pie {k} del ninja no cae en el de Dragged f0 ({(a - b).length:.3f} m)"

    for name, rows in (("Kidnap", K), ("Dragged", D)):
        print("CONTACTO", name, " ".join(f"f{f}:{duo.contacts(*rows[f])}" for f in range(0, len(rows), 4)))
    print("ALCANCE", {k: round(v, 3) for k, v in duo.reach.items()})
    print("AGARRE", " ".join(f"f{f}:{d}m" for f, d, wa, wb in duo.report[::6]))

    kid_g = dense("Kidnap", KID_N, [r[0] for r in K], timing=dict(
        sheet=[0, 6, 10, 14, GRAB, 21, IMPACT, 31, 39, DRAG_START, KID_N], slide_ok=60.0,
        events=dict(grab=GRAB, impact=IMPACT, grip=32, drag_start=DRAG_START)),
        notes="el ninja pasa por la izquierda, le agarra la muñeca y lo tira al piso; se agarran de las muñecas y arranca el arrastre")
    kid_g.partner = dense("Kidnap/ninja", KID_N, [r[1] for r in K], timing=dict(sheet=kid_g.timing["sheet"]))
    drag_g = dense("Dragged", DRAG_N, [r[0] for r in D], loop=True, root_vel=(0, DRAG_SPEED, 0), timing=dict(
        sheet=list(range(0, DRAG_N, 8)), slide_ok=80.0, events=dict(yank=30, reach=50, rest=70)),
        notes="arrastrado del brazo: el ninja camina tirando, el abuelo patalea con los talones")
    drag_g.partner = dense("Dragged/ninja", DRAG_N, [r[1] for r in D], loop=True, timing=dict(sheet=drag_g.timing["sheet"]))
    return kid_g, drag_g


# =============================================================================== Bound / Freed (de rodillas ante el poste)
BOUND_N, FREED_N = 90, 108
# seiza: la cadera sobre los talones, las rodillas en el piso adelante. Los tobillos en y = SEIZA_Y y la punta de los pies
# (para atrás) a +0.06: el zócalo del binding_post arranca en +0.1
SEIZA_HIPS = (0.0, -0.127, -0.26)
SEIZA_Y = -0.06
FOOT_X = {"r": (-0.085, -8.0), "l": (0.085, 8.0)}
# dedos metidos (de rodillas sobre la punta de los pies) y parado: el apoyo de Idle (R0/L0), la punta clavada al rodar
TUCK_PITCH = 70.0
# el zócalo del binding_post arranca 0.1 m detrás del marcador del abuelo: arrodillado, la falda de la túnica se abre
# para atrás y entraba 4 cm (19 cm en cuclillas al pararse). NPC.KneelBound adelanta el transform KNEEL_FWD antes de
# Bound (y las cuerdas se arman ahí): los clips quedan centrados en el transform y Freed termina en Idle sin correrlo
KNEEL_FWD = 0.20


def seiza_feet(ch, offs):
    out = {}
    for k in "rl":
        x, yaw = FOOT_X[k]
        out["foot_" + k], out["foot_%s_rot" % k] = foot_on_floor(ch, offs[k], k, x, SEIZA_Y, 165.0, yaw)
    return out


def bound_pose(f, sf):
    """Atado de rodillas: las muñecas cruzadas atrás contra la espalda (las ata ShadowRopes al poste), la cabeza gacha,
    dos respiraciones por vuelta y un forcejeo (cuadros 48-66): se estira contra las cuerdas, tironea con los hombros y
    levanta la cabeza; después se rinde."""
    a = 2.0 * math.pi * f / BOUND_N
    k = math.sin(math.pi * (f - 48) / 18.0) ** 2 if 48 <= f <= 66 else 0.0
    shake = math.sin(math.pi * 3.0 * (f - 48) / 18.0) * k
    br = 0.5 - 0.5 * math.cos(2.0 * a)
    c = dict(
        hips=(SEIZA_HIPS[0], SEIZA_HIPS[1] - 0.01 * k, SEIZA_HIPS[2] + 0.03 * k), hips_rot=(4.0 - 4.0 * k, 2.0 * shake, 6.0 * shake),
        spine=(8.0 - 6.0 * k - 2.0 * br, 0.0, 4.0 * shake), head=(30.0 - 20.0 * k + 3.0 * math.sin(a), 0.0, 5.0 * math.sin(a * 0.5) + 14.0 * shake),
        breath=br, clav_r=(0.0, 0.0, -6.0 - 8.0 * k), clav_l=(0.0, 0.0, 6.0 + 8.0 * k),
        hand_r=(0.015, 0.16 + 0.005 * k, 0.50 + 0.01 * k), hand_r_dir=(1.0, 0.1, -0.4), hand_r_palm=(0.0, 1.0, 0.0), elbow_r=(-1.0, 0.5, 0.0),
        hand_l=(-0.015, 0.17 + 0.005 * k, 0.49 + 0.01 * k), hand_l_dir=(-1.0, 0.1, -0.4), hand_l_palm=(0.0, 1.0, 0.0), elbow_l=(1.0, 0.5, 0.0),
        fist_r=0.6, fist_l=0.6, knee_r=(-0.15, -1.0, -0.5), knee_l=(0.15, -1.0, -0.5), auto_drop=0.0,
    )
    c.update(sf)
    return c


def bound(ch):
    offs = {k: foot_offsets(ch, k) for k in "rl"}
    sf = seiza_feet(ch, offs)
    rows = [bound_pose(f % BOUND_N, sf) for f in range(BOUND_N + 1)]
    # medidas para las cuerdas de sombra (NPC.BoundRopeLoops) y el zócalo del poste
    pr = Probe(ch)
    pose = pr.solve(rows[0])
    z = lambda b: round(ch.Pc(pose.get(b).translation).z, 3)
    sd = ch.side
    print("BOUND muñecas", z(sd["r"]["hand"]), z(sd["l"]["hand"]), "codos", z(sd["r"]["fore"]), z(sd["l"]["fore"]),
          "hombros", z(sd["r"]["upper"]), z(sd["l"]["upper"]), "rodillas", z(sd["r"]["shin"]), z(sd["l"]["shin"]),
          "cuerdas", BOUND_ROPES)
    return dense("Bound", BOUND_N, rows, loop=True, timing=dict(sheet=[0, 15, 30, 48, 54, 57, 60, 66, 75], events=dict(struggle=[48, 66])),
                 notes="de rodillas en seiza ante el poste, las muñecas cruzadas atrás; respira y forcejea una vez por vuelta")


def freed(ch):
    """Libre: los brazos vuelven adelante, se frota las muñecas (la derecha sobre la izquierda y al revés), mira a Kaito,
    se inclina sobre las rodillas, mete los dedos de los pies, se apoya con las manos en las rodillas y se para sin pasos
    (los pies terminan en los de Idle: NPC.PlayThen lo devuelve ahí sin patinar)."""
    offs = {k: foot_offsets(ch, k) for k in "rl"}
    sf = seiza_feet(ch, offs)
    B = bound_pose(0, sf)
    on_thighs = dict(hand_r=(-0.10, -0.20, 0.31), hand_r_dir=(0.0, -1.0, -0.3), hand_r_palm=(0.0, 0.0, -1.0),
                     hand_l=(0.10, -0.20, 0.31), hand_l_dir=(0.0, -1.0, -0.3), hand_l_palm=(0.0, 0.0, -1.0), elbow_r=(-1.0, 0.3, -0.4),
                     elbow_l=(1.0, 0.3, -0.4), fist_r=0.2, fist_l=0.2)
    rub_a = dict(hand_l=(0.05, -0.27, 0.52), hand_l_dir=(-1.0, -0.3, 0.1), hand_l_palm=(0.0, 0.2, -1.0), fist_l=0.5,
                 hand_r=(-0.03, -0.26, 0.56), hand_r_dir=(1.0, -0.2, -0.3), hand_r_palm=(0.0, 0.0, -1.0), fist_r=0.6,
                 elbow_r=(-1.0, 0.3, -0.5), elbow_l=(1.0, 0.3, -0.5))
    rub_b = dict(hand_r=(-0.05, -0.27, 0.52), hand_r_dir=(1.0, -0.3, 0.1), hand_r_palm=(0.0, 0.2, -1.0), fist_r=0.5,
                 hand_l=(0.03, -0.26, 0.56), hand_l_dir=(-1.0, -0.2, -0.3), hand_l_palm=(0.0, 0.0, -1.0), fist_l=0.6,
                 elbow_r=(-1.0, 0.3, -0.5), elbow_l=(1.0, 0.3, -0.5))
    I0 = idle_pose(0)
    keys = [Key(0, B),
            Key(6, dict(B, clav_r=(0.0, 0.0, 0.0), clav_l=(0.0, 0.0, 0.0), hand_r=(-0.08, 0.15, 0.50), hand_l=(0.08, 0.16, 0.50),
                        head=(22.0, 0.0, 0.0), breath=1.0), "out"),
            Key(13, dict(B, clav_r=(0.0, 0.0, 0.0), clav_l=(0.0, 0.0, 0.0), hand_r=(-0.24, -0.04, 0.44), hand_r_dir=(0.0, -0.3, -1.0),
                         hand_r_palm=(1.0, 0.0, 0.0), hand_l=(0.24, -0.04, 0.44), hand_l_dir=(0.0, -0.3, -1.0), hand_l_palm=(-1.0, 0.0, 0.0),
                         elbow_r=(-1.0, 0.3, -0.4), elbow_l=(1.0, 0.3, -0.4), head=(26.0, 0.0, 0.0), spine=(10.0, 0.0, 0.0), breath=0.4)),
            Key(19, dict(B, **rub_a, head=(16.0, 0.0, 6.0), spine=(8.0, 0.0, 0.0), hips_rot=(6.0, 0.0, 0.0), breath=0.2)),
            Key(36, dict(B, **rub_a, head=(18.0, 0.0, 4.0), spine=(8.0, 0.0, 0.0), hips_rot=(6.0, 0.0, 0.0), breath=0.7), "sine"),
            Key(42, dict(B, **rub_b, head=(16.0, 0.0, -6.0), spine=(8.0, 0.0, 0.0), hips_rot=(6.0, 0.0, 0.0), breath=0.4)),
            Key(50, dict(B, **rub_b, head=(14.0, 0.0, -4.0), spine=(8.0, 0.0, 0.0), hips_rot=(6.0, 0.0, 0.0), breath=0.6), "sine"),
            Key(55, dict(B, **on_thighs, head=(-4.0, 0.0, 0.0), spine=(4.0, 0.0, 0.0), hips_rot=(2.0, 0.0, 0.0), breath=1.0)),
            Key(61, dict(B, **on_thighs, hips=(0.0, -0.16, -0.215), hips_rot=(16.0, 0.0, 0.0), spine=(10.0, 0.0, 0.0),
                         head=(-12.0, 0.0, 0.0), breath=0.3)),
            Key(76, dict(B, **on_thighs, hips=(0.0, -0.10, -0.235), hips_rot=(22.0, 0.0, 0.0), spine=(14.0, 0.0, 0.0),
                         head=(-16.0, 0.0, 0.0), breath=0.5)),
            Key(86, dict(B, **on_thighs, hips=(0.0, -0.08, -0.19), hips_rot=(34.0, 0.0, 0.0), spine=(18.0, 0.0, 0.0),
                         head=(-22.0, 0.0, 0.0), knee_r=(-0.15, -1.0, 0.3), knee_l=(0.15, -1.0, 0.3), breath=0.9), "inout"),
            Key(98, dict(I0, hips=(0.0, 0.02, -0.035), hips_rot=(12.0, 0.0, 0.0), spine=(18.0, 0.0, 0.0), head=(-12.0, 0.0, 0.0),
                         breath=1.0, auto_drop=1.0), "inout"),
            Key(FREED_N, dict(I0, breath=0.0, auto_drop=1.0), "sine")]
    S = sampler("Freed/k", FREED_N, keys)
    pr = Probe(ch)
    rows = []
    for f in range(FREED_N + 1):
        c = S(f)
        for k, t0 in (("r", 66), ("l", 68)):
            x, yaw = FOOT_X[k]
            xi, _, yawi = (R0 if k == "r" else L0)
            if f <= t0:
                ank, rot = sf["foot_" + k], sf["foot_%s_rot" % k]
            elif f <= t0 + 6:
                # mete los dedos: el pie gira de empeine a punta sobre el tobillo, que sube lo justo para no tocar el piso
                u = NA.ease("inout", (f - t0) / 6.0)
                a_s, r_s = sf["foot_" + k], sf["foot_%s_rot" % k]
                a_t, r_t = ch.foot_at(k, xi, 0.0, yawi, TUCK_PITCH)
                pitch = 165.0 + (TUCK_PITCH - 165.0) * u
                yw = yaw + (yawi - yaw) * u
                ax, ay = a_s[0] + (a_t[0] - a_s[0]) * u, a_s[1] + (a_t[1] - a_s[1]) * u
                (_, _, zc), rot = foot_on_floor(ch, offs[k], k, ax, ay, pitch, yw, clear=0.012)
                az = max(a_s[2] + (a_t[2] - a_s[2]) * u + 0.05 * math.sin(math.pi * u), zc)
                ank = (ax, ay, az)
            elif f < 86:
                ank, rot = ch.foot_at(k, xi, 0.0, yawi, TUCK_PITCH)
            else:
                # se para: el pie rueda de la punta a plano con la punta clavada (foot_at), hasta el apoyo de Idle
                u = NA.ease("inout", min(1.0, (f - 86) / 12.0))
                ank, rot = ch.foot_at(k, xi, 0.0, yawi, TUCK_PITCH * (1.0 - u))
            c["foot_" + k], c["foot_%s_rot" % k] = ank, rot
        # en el empuje las manos van a las rodillas (donde quedaron de verdad) y las sueltan al enderezarse
        hk = ramp(f, 72, 80) * (1.0 - ramp(f, 90, 98))
        if hk > 0.0:
            pose = pr.solve(c)
            for k in "rl":
                kn = ch.Pc(pose.get(ch.side[k]["shin"]).translation)
                c["hand_" + k] = tuple(Vector(c["hand_" + k]).lerp(kn + Vector((0.0, -0.03, 0.07)), hk))
                c["hand_%s_dir" % k] = slerp3(c["hand_%s_dir" % k], (0.0, -1.0, -0.5), hk)
                c["hand_%s_palm" % k] = slerp3(c["hand_%s_palm" % k], (0.0, -0.3, -1.0), hk)
        # se frota: la mano de arriba da dos vueltas chicas sobre la muñeca de la otra
        for a, b, top in ((19, 36, "r"), (42, 50, "l")):
            if a <= f <= b:
                w = math.sin(math.pi * (f - a) / (b - a))
                ph = 2.0 * math.pi * 2.0 * (f - a) / (b - a)
                p = c["hand_" + top]
                c["hand_" + top] = (p[0] + 0.022 * math.sin(ph) * w, p[1] + 0.01 * math.cos(ph) * w, p[2] + 0.012 * math.cos(ph) * w)
        rows.append(c)
    return dense("Freed", FREED_N, rows, timing=dict(
        sheet=[0, 6, 13, 19, 30, 42, 55, 61, 70, 76, 86, 92, 98, 108], chain=[(FREED_N, "Idle", 0, 0.02)],
        events=dict(arms_free=6, rub=[19, 50], look=55, tuck=[66, 74], push=[76, 86], stand=98)),
        notes="libre: se frota las muñecas, mira a Kaito, mete los dedos de los pies y se para apoyado en las rodillas")
