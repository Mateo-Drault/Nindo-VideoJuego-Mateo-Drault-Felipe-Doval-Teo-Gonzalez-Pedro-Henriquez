"""Clips del abuelo (Nindo/Art/Models/Characters/Grandpa.fbx) en el marco de autoría de team_rig. 1.45 m con el
sombrero, piernas de 0.37 m y brazos cortitos (0.38 m): un viejito encorvado. El FBX trae también al ninja del secuestro
(esqueleto '.001', 1.32 m, brazos de 0.32 m): en KidnapWait, Kidnap y Dragged los dos se autoran juntos (clip.partner).

  * Idle (2.5 s): encorvado con las manos atrás, respira con los hombros, cabecea y mira alrededor.
  * Walk (0.8 s, 0.8 m/s): pasitos cortos, encorvado, las manos atrás. Es el hijo del blend de NPC (Speed 0.5) y además
    un estado propio (el final lo pide por nombre con SlideTo a WALK_SPEED).
  * KidnapWait (2.5 s, loop): antes del secuestro. El abuelo es el de Idle; el ninja, agazapado delante de él, se
    balancea de un pie al otro y no le saca los ojos de encima. Su cuadro 0 es el de Kidnap.
  * Kidnap (1.9 s, el prólogo): el ninja carga desde adelante, pasa por el costado izquierdo del abuelo y en la pasada
    le agarra la muñeca izquierda (f17); frena en seco y tira: el abuelo gira, trastabilla, los pies se le van al aire y
    cae sentado (f27). Se agarran de las muñecas (el abuelo le cierra la mano sobre la muñeca al ninja, f24-f32), clava
    los talones dos veces y los tirones del ninja se los arrastran; estira la otra mano hacia Kaito y en los últimos 10
    cuadros arranca el arrastre (el grupo acelera de 0 a DRAG_SPEED dentro del clip). Termina en el cuadro 0 de Dragged.
  * Dragged (2.67 s, loop, DRAG_SPEED m/s de promedio): el ninja camina agazapado tirando, el brazo izquierdo atrás y
    tirante; el abuelo sentado, el brazo izquierdo estirado hacia él (~140° de codo) y las dos manos trabadas en las
    muñecas, una al lado de la otra. Compases: los talones se clavan y se arrastran por turno; resiste (f13-f26: se
    endereza, encoge el brazo a ~110°, clava los dos talones y el grupo casi se frena; el ninja pierde el paso, gira el
    tronco y lo agarra también con la otra mano del antebrazo, f24-f40); el tirón (f26-f34: el ninja se trae las dos
    manos al cuerpo, el brazo del abuelo se estira de golpe y su tronco sale disparado hacia el ninja, se pasa y se
    asienta; el ninja vuelve a estirar el brazo caminando hasta f62); la mano derecha hacia Kaito (f40-f60) y rendido,
    los talones arrastrados sin parar (f60-f80). El grupo se atrasa y se pone al día respecto del transform (DRAG_LAG):
    los apoyos del ninja y los talones clavados quedan quietos en el mundo con la velocidad real de cada cuadro.
  * Bound (6 s, loop): de rodillas en seiza delante del poste, la cadera sobre los talones y las rodillas abiertas, la
    pelvis bien adelante, los hombros tirados atrás y las muñecas cruzadas a la espalda; respira, con la cabeza
    levantada (el ala del sombrero se inclina y desde la cámara del juego se le ve la cara) mira la arena de un lado al
    otro. Las vueltas de ShadowRopes se toman de los huesos de esta pose.
  * BoundStruggle (2.2 s): forcejeo suelto entre dos Bound (empieza y termina en Bound f0): junta aire, tironea con los
    hombros contra las cuerdas, levanta la cabeza, se rinde y se recompone. NPC lo dispara cada tanto.
  * Freed (3.6 s): libre, trae los brazos adelante, se frota una muñeca y la otra, levanta la vista hacia Kaito, se
    inclina sobre las rodillas, mete los dedos de los pies (el pie en arco, sin rozar), se apoya en las rodillas y se
    para (a lo viejo, sin pasos) y termina en el cuadro 0 de Idle.
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
DRAG_STEP = 20                  # un ciclo de pasos del ninja (dos pasos)
DRAG_N = 4 * DRAG_STEP
KID_N = 57
# el puño derecho del ninja al correr: los nudillos adelante y abajo, la palma hacia adentro (sin pedirlo, el antebrazo
# rodaba 76° en un cuadro al pasar la mano por el hombro)
RUN_DIR, RUN_PALM = (0.0, -0.3, -1.0), (1.0, 0.0, 0.0)
RUN_ARM = dict(hand_r_dir=RUN_DIR, hand_r_palm=RUN_PALM, elbow_r=(-1.0, 0.3, 0.0))
# agarre de muñecas: la palma de cada uno sobre el antebrazo del otro, a GRIP_R de su eje
GRIP_R = 0.022
GRAB, IMPACT, DRAG_START = 17, 27, 47
KID_TAUT = 40                   # desde acá Kidnap se funde con el arranque del arrastre (ver kidnap_and_dragged)
# lo más que cambia de un cuadro al otro el paso de la cadera del ninja en Kidnap (m por cuadro, 27 m/s²): las claves de
# la carrera con sus curvas daban 22 cm en f10 entre 14 y 14 y, al agarrar, 24 cm en f18 y 1 en f20 (se teletransportaba y
# se clavaba). Así arranca de la guardia, corre parejo y el agarre le va frenando el impulso en 5-6 cuadros
NINJA_HIP_ACC = 0.03
# lo mismo para el giro de la cadera y del tronco (° por cuadro por cuadro): al agarrar, la curva 'out' de la clave f20
# giraba el tronco 6° en el primer cuadro y, con la mano clavada en la muñeca del abuelo, el brazo del agarre saltaba 45°
NINJA_ROT_ACC = 3.0
# lo más hondo que puede ir la malla de los clips nuevos (cm del marco de autoría): los pies de Idle (y los del ninja
# escondido en la pose fija) quedan a -1.4 y el juego apoya eso en el piso, así que nada va más hondo que un pie parado.
# Sentado y de rodillas la túnica se metía 2.3-2.6 cm bajo ese piso (se veía hundido)
FLOOR_CM = -1.5

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
    wait, kid, drag = kidnap_and_dragged(ch)
    b, s, fr = bound_and_freed(ch)
    return [idle(), walk(ch), kid, wait, drag, b, s, fr]


# los cruces en seco o con fundido corto (NPC): Unity mezcla hueso por hueso y los brazos tienen que quedar en la misma
# rama del solver (team_limbs.ANCHOR_W). Se hornean en el orden de clips(): el de la izquierda se ancla al ya resuelto
BLENDS = [("KidnapWait", 0, "Kidnap", 0), ("Dragged", 0, "Kidnap", -1),
          ("BoundStruggle", 0, "Bound", 0), ("BoundStruggle", -1, "Bound", 0), ("Freed", 0, "Bound", 0)]


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


def blend_ctrls(a, b, w, keep=()):
    """Controles de a hacia b en w: posiciones y ángulos en línea, direcciones por slerp; 'keep' se queda con los de a."""
    out = dict(a)
    for k, vb in b.items():
        va = a.get(k)
        if k in keep or vb is None:
            continue
        if va is None:
            out[k] = vb
        elif isinstance(vb, (int, float)):
            out[k] = va + (vb - va) * w
        elif k.endswith(("_dir", "_palm")):
            out[k] = slerp3(va, vb, w)
        else:
            out[k] = lerp3(va, vb, w)
    return out


def smooth_track(pts, a_max, pin=2):
    """La recta más parecida a 'pts' (posiciones por cuadro) cuya aceleración no pasa de a_max (m por cuadro por cuadro):
    mínimos cuadrados con una penalidad a la segunda diferencia que crece hasta cumplir el tope. Los 'pin' cuadros de cada
    punta quedan donde estaban (posición y velocidad con las que empalma lo de antes y lo de después)."""
    import numpy as np
    P0 = np.array([tuple(p) for p in pts], dtype=float)
    n = len(P0)
    D = np.zeros((n - 2, n))
    for i in range(n - 2):
        D[i, i:i + 3] = (1.0, -2.0, 1.0)
    w = np.ones(n)
    w[:pin] = w[-pin:] = 1e6
    lam = 0.5
    while True:
        P = np.linalg.solve(np.diag(w) + lam * D.T @ D, w[:, None] * P0)
        if np.linalg.norm(np.diff(P, 2, axis=0), axis=1).max() <= a_max or lam > 1e5:
            return [tuple(float(x) for x in p) for p in P]
        lam *= 1.25


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
# agarre: las dos muñecas sobre la recta de hombro izquierdo a hombro izquierdo (la del ninja GRIP_SEP_U más allá y
# GRIP_SEP_S al costado, Duo.resolve): cada mano envuelve la muñeca del otro. Las
# palmas quedan 10.4 y 8.2 cm más allá de cada muñeca: con 6.3 cm entre muñecas cada palma cae 2-4 cm adentro del
# antebrazo del otro. Con 1 cm la corrección del contacto acortaba los dos brazos 3-4 cm (el codo del abuelo a 120°)
GRIP_SEP_U, GRIP_SEP_S = 0.063, 0.026
# brazo tirante: la muñeca a esta fracción del alcance (la mano libre del solver llega hasta el 95 %: ~145° de codo). Con
# el ninja a 0.8 m los dos brazos quedaban doblados a 58° y 130° (de la mano, como si fueran de la mano de paseo)
TAUT = 0.95
# el abuelo resiste: encoge el brazo agarrado hasta ~100° de codo y el ninja, tirante, se viene para atrás
RESIST_SHARE = 0.82
# el ninja tironea a dos manos (drag_beats 'grab'): afloja un poco el brazo del agarre (esta fracción del alcance, ~118°
# de codo) y gira el tronco hacia el abuelo para que la otra mano llegue a su antebrazo. Encogiéndolo más (0.68) el
# abuelo se lo traía 24 cm para atrás y después las piernas no alcanzaban a ponerse al día en el tirón
GRAB_TAUT = 0.86
# el tirón: el ninja se trae las dos manos al cuerpo de golpe (el brazo del agarre a esta fracción del alcance) y lo
# vuelve a estirar despacio mientras sigue caminando. Si el tirón lo daba la cadera (el ninja saltando para adelante con
# el brazo tirante) sus piernas de 0.33 m no alcanzaban: el abuelo se lo trae 20 cm cuando resiste y el ninja tenía que
# recuperarlos en un cuarto de segundo
PULL_TAUT = 0.66
GRAB_TURN = 0.3


def drag_taut(b):
    """Largo del brazo del agarre del ninja (fracción del alcance) en un cuadro de Dragged."""
    return min(TAUT + (GRAB_TAUT - TAUT) * b["grab"], TAUT + (PULL_TAUT - TAUT) * b["pull"])
# giro de cadera y de tronco del ninja hacia el abuelo en el tirón a dos manos (°; negativo: el pecho hacia el brazo del
# agarre. Con el signo al revés la otra mano quedaba a 22 cm del antebrazo del abuelo, así queda a 2)
NINJA_TWIST = (-24.0, -36.0)


class Duo:
    """Los dos personajes del FBX: conversión entre el marco del abuelo (g) y el del ninja (n), alcances y el agarre."""

    def __init__(self, ch):
        self.ch, self.kid = ch, ch.partner
        self.probe = Probe(ch)
        R = ch.rig
        # alcance del hombro a la cabeza de la mano (en el abuelo la muñeca está 4.9 cm más allá del antebrazo)
        self.reach = {who: (R.rest[c.side["l"]["hand"]].translation - R.rest[c.side["l"]["upper"]].translation).length / ch.u
                      for who, c in (("g", ch), ("n", self.kid))}
        # de la muñeca al centro de la palma (la cabeza de la mano y las de los dedos, como lo mide grandpa_fbx_check)
        self.palm_len = {}
        for who, c in (("g", ch), ("n", self.kid)):
            names = [c.side["r"]["hand"]] + [f[0] for f in c.spec["fingers"]["r"]]
            pc = sum((R.rest[b].translation for b in names), Vector()) / len(names)
            self.palm_len[who] = (pc - R.rest[c.side["r"]["hand"]].translation).length / ch.u
        self.up = ch.D((0, 0, 1))
        self.report = []
        self.shift = {}
        self.grab_miss = {}

    def g2n(self, p):
        return tuple(self.kid.Pc(self.ch.P(p)))

    def kid_rest(self):
        """La pose fija del ninja (kid_pose) leída como controles y apoyos: de ahí sale su guardia agazapada."""
        kid, kp = self.kid, self.ch.kid_pose
        c = dict(hips=tuple(kid.Pc(kp[kid.spec["pelvis"]].translation) - kid.land["pelvis"]), fist_r=0.3, fist_l=0.3)
        return c, {k: tuple(kid.Pc(kp[kid.side[k]["foot"]].translation)) for k in "rl"}

    def palm(self, pose, c, k="l"):
        names = [c.side[k]["hand"]] + [f[0] for f in c.spec["fingers"][k]]
        return sum((pose.get(b).translation for b in names), Vector()) / len(names)

    def forearm(self, pose, c):
        """(muñeca, codo) del brazo izquierdo resuelto."""
        return pose.get(c.side["l"]["hand"]).translation.copy(), pose.get(c.side["l"]["fore"]).translation.copy()

    def resolve(self, f, g, n, wa=1.0, wb=1.0, wc=1.0, share=None, grab=0.0, taut=TAUT):
        """Controles finales de un cuadro: las manos pedidas relativas al hombro ('hand_k_rel', m en el marco de cada uno)
        y el agarre de muñecas sobre la recta de hombro izquierdo a hombro izquierdo.
          * share: la muñeca del abuelo a share x su alcance del hombro y la del ninja a taut x el suyo: el ninja se
            corre sobre esa recta lo que haga falta (self.shift, en su marco). Sin share (Kidnap, mientras se agarran) el
            reparto sale de la distancia que haya.
          * wa: la muñeca del abuelo va del pedido a la recta (lo arrastran del brazo); wb: la mano del ninja llega a ella;
            wc: el abuelo cierra la mano sobre la muñeca del ninja.
          * grab: la mano derecha del ninja agarra también el antebrazo del abuelo (el tirón a dos manos)."""
        ch, kid = self.ch, self.kid
        # un canal que ninguna clave vecina pide sale None: es como no pedirlo
        g, n = ({k: v for k, v in d.items() if v is not None} for d in (g, n))
        base = lambda d: {k: v for k, v in d.items() if not k.endswith(("_rel", "_relw"))}
        # 'hand_k_relw' mezcla la mano pedida en el marco (0) con la pedida desde el hombro (1). El hombro sale del cuadro
        # resuelto, y ese cuadro necesita la mano: si no, la clavícula se estira hacia la muñeca de reposo (20°, el hombro
        # corrido 15 cm). Varias pasadas: mano desde el hombro de reposo, desde el resuelto, otra vez
        rels = []
        for c, d in ((ch, g), (kid, n)):
            for k in "rl":
                rel, w = d.pop("hand_%s_rel" % k, None), d.pop("hand_%s_relw" % k, 1.0)
                if rel is not None:
                    rels.append((c, d, k, Vector(rel), w, d.get("hand_" + k)))
                    d["hand_" + k] = tuple(c.land["shoulder_" + k] + Vector(d.get("hips", (0, 0, 0))) + Vector(rel))

        def settle(passes):
            for _ in range(passes):
                pose = self.probe.solve(base(g), base(n))
                for c, d, k, rel, w, absk in rels:
                    p = c.Pc(pose.get(c.side[k]["upper"]).translation) + rel
                    d["hand_" + k] = tuple(Vector(absk).lerp(p, w)) if absk is not None else tuple(p)
            return self.probe.solve(base(g), base(n))

        def shoulders(pose):
            Sg = pose.get(ch.side["l"]["upper"]).translation.copy()
            Sn = pose.get(kid.side["l"]["upper"]).translation.copy()
            u = Sn - Sg
            return Sg, Sn, u.length / ch.u, u.normalized()

        pose = settle(3)
        shift = Vector()
        # el agarre se recoloca varias veces desde los hombros ya resueltos: la clavícula de este rig mide 20 cm y gira
        # hacia la mano pedida, el hombro se corre hasta 14 cm hacia el otro y la muñeca puesta desde el hombro de antes
        # quedaba a 0.24 m de él (el codo a 78°, de la mano como de paseo) en vez de a share x alcance. En Kidnap, con una
        # sola pasada, cada cuadro caía en un punto distinto y el agarre saltaba 7-10 cm de un cuadro al otro. Cada pasada
        # arranca de lo que pidió el clip (los fundidos wa/wb/wc no se acumulan)
        grip_keys = [k + "_l" + x for k in ("hand",) for x in ("", "_dir", "_palm")] + ["fist_l"]
        g0, n0 = {k: g.get(k) for k in grip_keys}, {k: n.get(k) for k in grip_keys}
        for it in range(4):
            if it:
                pose = self.probe.solve(base(g), base(n))
            Sg, Sn, D, u = shoulders(pose)
            if share is not None:
                a = share * self.reach["g"]
                need = a + GRIP_SEP_U + math.sqrt((taut * self.reach["n"]) ** 2 - GRIP_SEP_S ** 2)
                for _ in range(5):
                    e = need - D
                    if abs(e) < 0.002:
                        break
                    # la cadera del ninja sobre el piso (sin subir ni bajar): la recta de hombros apenas cae hacia el abuelo
                    dn = Vector(kid.Dc(u))
                    dn.z = 0.0
                    dn = dn.normalized() * e
                    n["hips"] = tuple(Vector(n["hips"]) + dn)
                    shift += dn
                    pose = settle(1)
                    Sg, Sn, D, u = shoulders(pose)
            else:
                # (la muñeca del ninja va GRIP_SEP_U más allá: sin descontarlo su brazo se pasaba del alcance)
                a = min(self.reach["g"] * 0.94, max(D * 0.56, D - GRIP_SEP_U - self.reach["n"] * 0.92))
            if it:
                # los hombros se midieron con el agarre de la pasada anterior; la mano se vuelve a poner desde lo pedido
                for d, d0 in ((g, g0), (n, n0)):
                    for k, v in d0.items():
                        if v is None:
                            d.pop(k, None)
                        else:
                            d[k] = v
            M = Sg + u * (a * ch.u)
            # las dos muñecas una al lado de la otra (no una arriba de la otra): la mano del abuelo envuelve la del ninja
            # por encima, con los dedos cerrados del lado de afuera. Apiladas, su palma quedaba para arriba bajo la mano
            # negra del ninja con el pulgar parado: desde el costado se leían dos manos que se dan la mano
            side = u.cross(self.up).normalized()
            Wg = M - side * (0.5 * GRIP_SEP_S * ch.u)
            Wn = M + u * (GRIP_SEP_U * ch.u) + side * (0.5 * GRIP_SEP_S * ch.u)
            gW = ch.P(g["hand_l"]).lerp(Wg, wa) if "hand_l" in g else Wg
            g["hand_l"] = tuple(ch.Pc(gW))
            ug, sg = tuple(ch.Dc(u)), tuple(ch.Dc(side))
            g["hand_l_dir"] = slerp3(g.get("hand_l_dir", ug), ug, wc)
            g["hand_l_palm"] = slerp3(g.get("hand_l_palm", sg), sg, wc)
            # los dedos cerrados alrededor de la muñeca del ninja (más que un puño de 'fist' 1: falanges a 74/94°)
            g["fist_l"] = g.get("fist_l", 0.3) + (1.2 - g.get("fist_l", 0.3)) * wc
            if wb > 0.0:
                nW = kid.P(n["hand_l"]).lerp(gW + (Wn - Wg), wb) if "hand_l" in n else gW + (Wn - Wg)
                un, sn = tuple(kid.Dc(-u)), tuple(kid.Dc(-side))
                n["hand_l"] = tuple(kid.Pc(nW))
                n["hand_l_dir"] = slerp3(n.get("hand_l_dir", un), un, wb)
                n["hand_l_palm"] = slerp3(n.get("hand_l_palm", sn), sn, wb)
                n["fist_l"] = n.get("fist_l", 0.3) + (1.1 - n.get("fist_l", 0.3)) * wb
                # la palma de cada uno sobre el antebrazo del otro: a GRIP_R del eje y entre 1 y 5 cm más allá de su muñeca.
                # Solo se corrige lo que falta (hasta 3 cm por pasada): antes la corrección perseguía al puño del otro sin
                # tope y el agarre se iba metiendo hacia el abuelo hasta plegarle el brazo
                for _ in range(3):
                    pose = self.probe.solve(base(g), base(n))
                    for c, d, w, other in ((kid, n, wb, ch), (ch, g, wc, kid)):
                        if w <= 1e-3:
                            continue
                        Pp = self.palm(pose, c)
                        wo, eo = self.forearm(pose, other)
                        ax = (eo - wo).normalized()
                        t = (Pp - wo).dot(ax)
                        r = Pp - (wo + ax * t)
                        corr = r.normalized() * (GRIP_R * ch.u - r.length) if r.length > 1e-6 else Vector()
                        corr += ax * (min(max(t, 0.01 * ch.u), 0.05 * ch.u) - t)
                        if corr.length > 0.03 * ch.u:
                            corr = corr.normalized() * (0.03 * ch.u)
                        d["hand_l"] = tuple(c.Pc(c.P(d["hand_l"]) + corr * w))
        self.shift[f] = tuple(shift)
        if grab > 1e-3:
            # la otra mano del ninja sobre el antebrazo del abuelo, 8 cm detrás de su muñeca y por arriba: los dedos
            # cruzan el antebrazo hacia el lado de afuera (como se agarra una soga para tirar)
            pose = self.probe.solve(base(g), base(n))
            wo, eo = self.forearm(pose, ch)
            ax = (eo - wo).normalized()
            up = (self.up - ax * self.up.dot(ax)).normalized()
            Pp = wo + ax * (0.08 * ch.u) + up * (0.035 * ch.u)
            Sr = pose.get(kid.side["r"]["upper"]).translation
            fd = ax.cross(up)
            if fd.dot(Pp - Sr) < 0.0:
                fd = -fd
            Wt = kid.Pc(Pp - fd * (self.palm_len["n"] * ch.u))
            n["hand_r"] = tuple(Vector(n["hand_r"]).lerp(Wt, grab))
            # el giro de la mano a medias (GRAB_TURN): entero pedía 85° más de lo que da la muñeca y al soltar el antebrazo
            # rodaba 155° en un cuadro
            n["hand_r_dir"] = slerp3(n.get("hand_r_dir", RUN_DIR), tuple(kid.Dc(fd)), grab * GRAB_TURN)
            n["hand_r_palm"] = slerp3(n.get("hand_r_palm", RUN_PALM), tuple(kid.Dc(-up)), grab * GRAB_TURN)
            n["fist_r"] = n.get("fist_r", 0.9) + (1.1 - n.get("fist_r", 0.9)) * grab
            pose = self.probe.solve(base(g), base(n))
            self.grab_miss[f] = round((self.palm(pose, kid, "r") - Pp).length / ch.u * 100.0, 1)
        self.report.append((f, round(D, 3), round(wa, 2), round(wb, 2)))
        return g, n

    def contacts(self, g, n):
        """Lo que quedó de verdad: la palma de cada uno contra el antebrazo del otro (cm a su eje, cm desde la muñeca)."""
        ch, kid = self.ch, self.kid
        pose = self.probe.solve(g, n)
        out = []
        for a, b in ((ch, kid), (kid, ch)):
            F = self.palm(pose, a)
            w = pose.get(b.side["l"]["hand"]).translation
            e = pose.get(b.side["l"]["fore"]).translation
            ax = (e - w).normalized()
            t = max(0.0, (F - w).dot(ax))
            d = (F - (w + ax * t)).length
            out.append((round(d / ch.u * 100.0, 1), round(t / ch.u * 100.0, 1)))
        return out


# ---- compases del arrastre (cuadros del loop de DRAG_N)
RES_IN, RES_FULL, RES_OUT = 13, 17, 26       # empieza a frenar / ya clavado / suelta (el tirón)
V_RESIST = 0.30                              # m/s del grupo mientras el abuelo clava los talones
# el tirón: el grupo llega a su pico en YANK_UP cuadros y vuelve a DRAG_SPEED en YANK_BACK (lo atrasado se recupera en el
# resto del loop, el pico queda en ~1.05 m/s). Con 3 + 9 el pico era 2 m/s y las piernas del ninja (pasos clavados en el
# mundo) no alcanzaban a cubrir el paso: le faltaban 15-21 cm en f29-f33. El golpe del tirón lo dan el brazo y el tronco
# del abuelo, no la velocidad del grupo
YANK_UP, YANK_BACK = 6, 48


def _group_speed(f, vmax):
    """Velocidad en el mundo del grupo (m/s) en el cuadro f: frena cuando el abuelo resiste y en el tirón se pone al
    día de golpe (vmax). En promedio da DRAG_SPEED: el transform corre parejo y el grupo se atrasa y se adelanta."""
    if f < RES_IN:
        return DRAG_SPEED
    if f < RES_FULL:
        return DRAG_SPEED + (V_RESIST - DRAG_SPEED) * NA.ease("inout", (f - RES_IN) / float(RES_FULL - RES_IN))
    if f < RES_OUT:
        return V_RESIST
    if f < RES_OUT + YANK_UP:
        return V_RESIST + (vmax - V_RESIST) * NA.ease("out", (f - RES_OUT) / float(YANK_UP))
    if f < RES_OUT + YANK_UP + YANK_BACK:
        return vmax + (DRAG_SPEED - vmax) * NA.ease("inout", (f - RES_OUT - YANK_UP) / float(YANK_BACK))
    return DRAG_SPEED


def _drag_profile():
    lo, hi = DRAG_SPEED, 6.0
    for _ in range(60):
        m = 0.5 * (lo + hi)
        if sum(_group_speed(i + 0.5, m) - DRAG_SPEED for i in range(DRAG_N)) < 0.0:
            lo = m
        else:
            hi = m
    vmax = 0.5 * (lo + hi)
    lag = [0.0]
    for i in range(DRAG_N):
        lag.append(lag[-1] + (_group_speed(i + 0.5, vmax) - DRAG_SPEED) / NA.FPS)
    # lo que quede de la bisección se reparte (el loop cierra en 0 exacto)
    err = lag[-1]
    return vmax, [x - err * i / DRAG_N for i, x in enumerate(lag)]


# DRAG_LAG[f]: cuánto va atrasado el grupo respecto del transform del NPC (m, en el sentido del arrastre)
DRAG_VMAX, DRAG_LAG = _drag_profile()
# inclinaciones de los compases (°, cadera y tronco): el abuelo hacia atrás cuando resiste, el ninja hacia adelante en el
# tirón. Con los brazos tirantes cada grado mueve el hombro y el otro tiene que acompañar con la cadera (los dos con el
# largo de los brazos fijo): 27° del abuelo y 26° del ninja pedían correr al ninja 31 cm en medio segundo
LEAN = dict(g_res=(12.0, 14.0), n_yank=(6.0, 4.0))

def whip(f):
    """El tirón: el tronco del abuelo sale hacia el ninja (1), se pasa un poco (-0.25) y se asienta."""
    if RES_OUT <= f < RES_OUT + 4:
        return NA.ease("out", (f - RES_OUT) / 4.0)
    if RES_OUT + 4 <= f < RES_OUT + 8:
        return 1.0 - 1.25 * NA.ease("inout", (f - RES_OUT - 4) / 4.0)
    if RES_OUT + 8 <= f < RES_OUT + 14:
        return -0.25 * (1.0 - NA.ease("inout", (f - RES_OUT - 8) / 6.0))
    return 0.0


def drag_beats(f):
    """Capas del cuadro f (0..DRAG_N) del arrastre."""
    f = f % DRAG_N
    tau = 2.0 * math.pi
    return dict(
        surge_n=0.5 - 0.5 * math.cos(tau * (f - 4) / (DRAG_STEP / 2)),          # cada paso del ninja, al empujar
        surge_g=0.5 - 0.5 * math.cos(tau * (f - 7) / (DRAG_STEP / 2)),          # el abuelo llega 3 cuadros después
        res=ramp(f, RES_IN, RES_IN + 7) * (1.0 - ramp(f, RES_OUT, RES_OUT + 6)),
        whip=whip(f), whip_lag=whip(f - 2),
        grab=ramp(f, 14, 24) * (1.0 - ramp(f, 40, 56)),
        pull=ramp(f, RES_OUT, RES_OUT + 4, "out") * (1.0 - ramp(f, 34, 62)),
        reach=math.sin(math.pi * (f - 40) / 20.0) ** 2 if 40 <= f <= 60 else 0.0,
        limp=ramp(f, 58, 64) * (1.0 - ramp(f, 74, 80)),
    )


# disposición del arrastre (marco del abuelo): la cadera del abuelo casi en el piso, el ninja adelante en el sentido del
# arrastre (+Y: la espalda del abuelo) y 0.42 m a la izquierda del abuelo (del lado de la cámara del prólogo). La
# distancia de verdad la pone el brazo tirante (Duo.resolve corre al ninja)
G_HIPS = (0.02, 0.12, -0.18)
N_PELVIS_G = (0.42, 0.90)
# el ninja tira agazapado (la cadera NINJA_CROUCH más baja que al caminar) y con apoyos más cortos: sus piernas miden 0.33 m
# y con la cadera alta, 62 % de apoyo y los pies 7 cm detrás de la cadera no cubría más de ~0.9 m/s con los pies
# clavados; en el arrastre, cuando el abuelo resiste y se lo trae, después tiene que recuperar ese terreno
NINJA_DUTY = 0.55
NINJA_CROUCH = 0.035
NINJA_FOOT_X, NINJA_FOOT_BACK = 0.095, 0.03      # los apoyos un poco detrás de la cadera: empuja inclinado
# y más atrás cuanto más rápido va el grupo que DRAG_SPEED (s: m de apoyo por m/s de más; más adelante cuando frena). En
# la vuelta rápida después del tirón (1.0-1.5 m/s) el pie derecho apoyaba 24 cm delante de la cadera y el solver la bajaba
# 5 cm en f38-f40 para alcanzarlo (un pozo en el paso); frenado por el abuelo, los pies adelante son los de quien aguanta
NINJA_FOOT_LEAD = 0.10
# los últimos cuadros de Kidnap el grupo acelera de quieto a DRAG_SPEED: arranca LAUNCH_SHIFT m atrás de la disposición
LAUNCH = KID_N - DRAG_START
LAUNCH_SHIFT = DRAG_SPEED * LAUNCH / NA.FPS / 2.0


def g_hips(f, b):
    return (G_HIPS[0], G_HIPS[1] + DRAG_LAG[f] + 0.012 * b["surge_g"] - 0.02 * b["whip"],
            G_HIPS[2] + 0.008 * b["surge_g"] + 0.012 * max(0.0, b["whip"]) + 0.01 * b["res"]
            # rendido o estirando la mano la pelvis se echa atrás y la cola de la túnica (pesada a Root) bajaba 1.9 cm
            + 0.012 * b["limp"] + 0.006 * b["reach"])


# talones del abuelo (marco del abuelo): tramos por pie. P: clavado en el mundo (la pierna se estira mientras lo
# arrastran); S: se arrastra con la cadera (el polvo de NPC); RP: dobla la rodilla, lo levanta y lo vuelve a clavar a
# HEEL_REL0 de la cadera. En la resistencia los dos quedan clavados; en el tirón y rendido se arrastran
HEEL_REL0 = -0.20
HEEL_X = {"r": (-0.10, -18.0), "l": (0.13, 22.0)}
HEEL_SEGS = {"r": [(0, 5, "P"), (5, 11, "S"), (11, 15, "RP"), (15, 27, "P"), (27, 31, "S"), (31, 38, "RP"), (38, 43, "P"),
                   (43, 49, "S"), (49, 56, "RP"), (56, 61, "P"), (61, 76, "S"), (76, 80, "RP")],
             "l": [(0, 4, "RP"), (4, 9, "P"), (9, 11, "S"), (11, 15, "RP"), (15, 27, "P"), (27, 33, "S"), (33, 41, "RP"),
                   (41, 46, "P"), (46, 52, "S"), (52, 57, "RP"), (57, 62, "P"), (62, 80, "S")]}
HEEL_PITCH_P, HEEL_PITCH_S = -30.0, -22.0


def heel_tracks():
    """{pie: [(y, pitch, alto) por cuadro 0..DRAG_N]} en el marco del abuelo (clip). Clavado = quieto en el mundo: en el
    clip va para atrás a la velocidad del transform."""
    hy = [g_hips(f % DRAG_N, drag_beats(f))[1] for f in range(DRAG_N + 1)]
    H = lambda f: hy[f % DRAG_N]
    out = {}
    for k, segs in HEEL_SEGS.items():
        i0 = next(i for i, s in enumerate(segs) if s[2] == "P")
        cyc = segs[i0:] + [(a + DRAG_N, b + DRAG_N, m) for a, b, m in segs[:i0]]
        n2 = 2 * DRAG_N + 1
        y, pit, lift = [0.0] * n2, [0.0] * n2, [0.0] * n2
        a0 = cyc[0][0]
        y[a0], pit[a0] = H(a0) + HEEL_REL0, HEEL_PITCH_P
        for a, b, m in cyc:
            for f in range(a + 1, b + 1):
                u = (f - a) / float(b - a)
                if m == "P":
                    y[f], pit[f] = y[f - 1] - DRAG_SPEED / NA.FPS, HEEL_PITCH_P
                elif m == "S":
                    y[f] = H(f) + (y[a] - H(a))
                    pit[f] = pit[a] + (HEEL_PITCH_S - pit[a]) * NA.ease("inout", u)
                else:
                    s = NA.ease("inout", u)
                    y[f] = y[a] + (H(b) + HEEL_REL0 - y[a]) * s
                    pit[f] = pit[a] + (HEEL_PITCH_P - pit[a]) * s
                    lift[f] = 0.035 * math.sin(math.pi * u)
        fold = lambda arr: [arr[f + DRAG_N] if f < a0 else arr[f] for f in range(DRAG_N + 1)]
        yy, pp, ll = fold(y), fold(pit), fold(lift)
        assert abs(yy[0] - yy[DRAG_N]) < 1e-6 and abs(pp[0] - pp[DRAG_N]) < 1e-6, f"talón {k}: el loop no cierra"
        out[k] = list(zip(yy, pp, ll))
    return out


def ninja_gait(duo, hips_w):
    """Pasos del ninja con los apoyos quietos en el MUNDO para una cadera que no va pareja: hips_w[f] es su cadera en el
    mundo (y del marco del abuelo, sentido del arrastre), f 0..DRAG_N, con hips_w[DRAG_N] = hips_w[0] + lo que avanza el
    loop. Cada pie apoya en el cuadro 0 (derecho) o 10 (izquierdo) de su ciclo de DRAG_STEP, con el apoyo bajo donde va a
    estar la cadera a mitad del apoyo: si el grupo frena, los pasos se acortan (pierde el paso); en el tirón se alargan.
    Talón que entra y punta que despega como gait2. Devuelve fn(f) -> controles (marco del ninja); fn.one(k, f) da
    (x, y, giro, pitch, alto) para empalmar Kidnap."""
    kid = duo.kid
    n, dur, duty = DRAG_N, DRAG_STEP, NINJA_DUTY
    adv = DRAG_SPEED * n / NA.FPS
    hs, to = 0.14 * duty, 0.62 * duty

    def Hp(t):
        k = math.floor(t / n)
        r = t - k * n
        i = min(int(r), n - 1)
        return hips_w[i] + (hips_w[i + 1] - hips_w[i]) * (r - i) + k * adv

    x0 = duo.g2n((N_PELVIS_G[0], 0.0, 0.0))[0]
    feet = {"r": (x0 - NINJA_FOOT_X, -8.0, 0), "l": (x0 + NINJA_FOOT_X, 8.0, dur // 2)}
    def plant(s):
        m = s + duty * dur * 0.5
        v = (Hp(m + 0.5) - Hp(m - 0.5)) * NA.FPS
        return Hp(m) - NINJA_FOOT_BACK - NINJA_FOOT_LEAD * (v - DRAG_SPEED)

    def one(k, f):
        x, yaw, ph = feet[k]
        s = math.floor((f - ph) / dur) * dur + ph
        p = (f - s) / float(dur)
        z = 0.0
        if p < duty:
            yw = plant(s)
            if p < hs:
                pitch = -12.0 * (1.0 - NA.ease("out2", p / hs))
            elif p > to:
                pitch = 25.0 * NA.ease("in2", (p - to) / (duty - to))
            else:
                pitch = 0.0
        else:
            q = (p - duty) / (1.0 - duty)
            sq = NA.ease("inout", q)
            yw = plant(s) + (plant(s + dur) - plant(s)) * sq
            z = 0.05 * math.sin(math.pi * q) ** 0.8
            pitch = 25.0 * (1.0 - sq) - 12.0 * sq
        yn = duo.g2n((N_PELVIS_G[0], yw - DRAG_SPEED * f / NA.FPS, 0.0))[1]
        return x, yn, yaw, pitch, z

    def fn(f):
        out = {}
        for k in "rl":
            x, y, yaw, pitch, z = one(k, f)
            out["foot_" + k], out["foot_%s_rot" % k] = kid.foot_at(k, x, y, yaw, pitch, 0.0, z)
        return out
    fn.one = one
    return fn


def drag_frame(duo, f, gait, heels, shift):
    """Controles del cuadro f de Dragged para el abuelo y el ninja (manos relativas al hombro; el agarre, en resolve).
    shift: lo que Duo.resolve corrió al ninja para que el brazo quede tirante (marco del ninja)."""
    ch, kid = duo.ch, duo.kid
    b = drag_beats(f)
    res, wh, wl, grab, reach, limp = b["res"], b["whip"], b["whip_lag"], b["grab"], b["reach"], b["limp"]
    tau = 2.0 * math.pi
    st = tau * f / DRAG_STEP
    hips = g_hips(f, b)
    # resiste: el tronco se endereza hasta pasar un poco la vertical (lejos del ninja: de 21° hacia él a -5°, LEAN) y la
    # cabeza se echa atrás, la mano derecha se apoya en el piso al lado de la cadera; el tirón lo saca disparado hacia el
    # ninja (35°; la cabeza llega 2 cuadros tarde)
    brace = (-0.22, hips[1] + 0.02, 0.045)
    g = dict(
        hips=hips,
        hips_rot=(-20.0 + LEAN["g_res"][0] * res - 12.0 * wh + 2.0 * b["surge_g"] - 3.0 * limp, 4.0, 10.0 + 6.0 * wh + 4.0 * res),
        spine=(-2.0 + LEAN["g_res"][1] * res - 5.0 * wh - 2.0 * limp, 2.0, 4.0 + 2.0 * wh),
        head=(34.0 - 16.0 * reach - 20.0 * res - 9.0 * wl + 10.0 * limp, 0.0, -4.0 - 10.0 * reach + 6.0 * limp),
        breath=0.5 - 0.5 * math.cos(tau * f / (DRAG_STEP / 2)),
        knee_r=(-0.3, -1.0, 0.6), knee_l=(0.3, -1.0, 0.6),
        hand_r=brace, hand_r_relw=1.0 - res,
        hand_r_rel=lerp3(lerp3((-0.15, -0.10, -0.25), (-0.04, -0.31, -0.10), reach), (-0.20, 0.02, -0.12), max(0.0, wh)),
        fist_r=0.6 - 0.5 * reach - 0.4 * res,
        hand_r_dir=slerp3(slerp3((0.0, -0.4, -1.0), (0.0, -1.0, -0.2), reach), (-0.3, -1.0, -0.15), res),
        hand_r_palm=slerp3(slerp3((1.0, 0.0, 0.0), (0.0, -0.2, -1.0), reach), (0.0, 0.0, -1.0), res),
        elbow_r=(-1.0, 0.3, -0.5), elbow_l=(1.0, 0.0, -0.6), auto_drop=0.0,
    )
    for k in "rl":
        y, pitch, lift = heels[k][f]
        x, yaw = HEEL_X[k]
        g["foot_" + k], g["foot_%s_rot" % k] = ch.foot_at(k, x, y, yaw, pitch, 0.0, lift)
    n0 = duo.g2n((N_PELVIS_G[0], N_PELVIS_G[1], kid.land["pelvis"].z))
    bob = 0.012 * (0.5 - 0.5 * math.cos(tau * f / (DRAG_STEP / 2)))
    # el ninja: tirado para atrás cuando el abuelo resiste (se endereza, mira para atrás y lo agarra con las dos manos),
    # en el tirón se inclina con todo; el resto camina inclinado con el brazo derecho que acompaña los pasos
    look = max(res, grab)
    n = dict(
        hips=(n0[0] + shift[0], n0[1] - DRAG_LAG[f] - 0.012 * b["surge_n"] + 0.02 * wh + shift[1],
              -0.072 - NINJA_CROUCH + bob - 0.012 * wh + 0.015 * res),
        hips_rot=(22.0 - 14.0 * res + LEAN["n_yank"][0] * wh, -3.0 * math.sin(st), 10.0 + 6.0 * math.sin(st) + NINJA_TWIST[0] * grab),
        spine=(8.0 - 6.0 * res + LEAN["n_yank"][1] * wh, 0.0, 8.0 + NINJA_TWIST[1] * grab),
        head=(-16.0 + 6.0 * wh, 0.0, -10.0 + 55.0 * look),
        hand_r_rel=(-0.05, 0.10 * math.cos(st) - 0.03, -0.24), fist_r=0.9, elbow_l=(0.6, 0.2, -0.8),
        # el codo derecho, que cruza el cuerpo hacia el abuelo en el tirón a dos manos, apunta abajo y afuera
        elbow_r=slerp3((-1.0, 0.3, 0.0), (-0.5, 0.2, -0.85), grab),
        hand_r_dir=RUN_DIR, hand_r_palm=RUN_PALM,
    )
    n.update(gait(f))
    return g, n, b


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


# ---- la espera: el ninja agazapado delante del abuelo (KidnapWait, y el cuadro 0 de Kidnap)
WAIT_N = IDLE_N


def stalk_feet(kfeet):
    """Apoyos de la guardia agazapada (marco del ninja): el derecho atrás, el izquierdo adelante, más abiertos."""
    return {"r": (kfeet["r"][0] - 0.03, kfeet["r"][1] + 0.12, -14.0), "l": (kfeet["l"][0] + 0.03, kfeet["l"][1] - 0.08, 10.0)}


def stalk_pose(kr, f):
    """El ninja agazapado: el peso va de un pie al otro una vez por vuelta, la cabeza clavada en el abuelo."""
    a = 2.0 * math.pi * f / WAIT_N
    b = 2.0 * a
    sw = math.sin(a)
    br = 0.5 - 0.5 * math.cos(b)
    return dict(hips=(kr["hips"][0] + 0.03 * sw, kr["hips"][1] + 0.03, -0.11 + 0.006 * br),
                hips_rot=(18.0, 2.0 * sw, -5.0 * sw), spine=(10.0 - 1.5 * math.sin(b), 3.0 * sw, 2.0 * sw),
                head=(-16.0 + 2.0 * math.sin(b + 0.5), 0.0, 8.0 * sw), breath=br,
                hand_r_rel=(-0.05, -0.14 + 0.01 * math.sin(b), -0.20), hand_r_dir=(0.1, -0.8, -0.6), hand_r_palm=(1.0, 0.0, -0.2),
                fist_r=0.5, elbow_r=(-1.0, 0.3, -0.3),
                hand_l_rel=(0.07, 0.06, -0.25), fist_l=0.6, elbow_l=(1.0, 0.3, 0.0))


def kidnap_and_dragged(ch):
    duo = Duo(ch)
    kid = duo.kid
    zr = kid.land["pelvis"].z
    T_w = lambda f: DRAG_SPEED * f / NA.FPS

    # ---- Dragged, en pasadas: la primera mide cuánto hay que correr al ninja para que los dos brazos queden con el largo
    # pedido (share del abuelo, drag_taut del ninja) en cada cuadro; las otras arman sus pasos con esa cadera (sus apoyos,
    # clavados en el mundo) y corrigen lo que cambió
    share = lambda b: TAUT + (RESIST_SHARE - TAUT) * b["res"]
    heels = heel_tracks()
    shifts = [(0.0, 0.0)] * (DRAG_N + 1)
    for _pass in range(3):
        hips_w = [T_w(f) + N_PELVIS_G[1] + DRAG_LAG[f] - shifts[f][1] for f in range(DRAG_N + 1)]
        hips_w[DRAG_N] = hips_w[0] + DRAG_SPEED * DRAG_N / NA.FPS
        gait = ninja_gait(duo, hips_w)
        D, new = [], []
        for f in range(DRAG_N + 1):
            ff = f % DRAG_N
            g, n, b = drag_frame(duo, ff, gait, heels, shifts[ff])
            D.append(duo.resolve(ff, g, n, share=share(b), grab=b["grab"], taut=drag_taut(b)))
            s = duo.shift[ff]
            new.append((shifts[ff][0] + s[0], shifts[ff][1] + s[1]))
        shifts = new
        print("ARRASTRE pasada", _pass, "corrimiento del ninja (cm)", [round(math.hypot(*duo.shift[f][:2]) * 100, 1) for f in range(0, DRAG_N, 8)])
    D[DRAG_N] = D[0]
    raw0 = drag_frame(duo, 0, gait, heels, shifts[0])
    v = [(hips_w[f + 1] - hips_w[f]) * NA.FPS for f in range(DRAG_N)]
    print("ARRASTRE velocidad del ninja en el mundo (m/s)", round(min(v), 2), "a", round(max(v), 2),
          [round(x, 2) for x in v[::4]])

    # ---- Kidnap: claves de cada uno hasta DRAG_START; de ahí, Dragged f0 que arranca (LAUNCH_SHIFT -> 0)
    kr, kfeet = duo.kid_rest()
    sfeet = stalk_feet(kfeet)

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
         Key(21, P(hips=(0.03, 0.04, -0.06), hips_rot=(-14.0, 4.0, 30.0), spine=(-6.0, 2.0, 10.0), head=(12.0, 0.0, 20.0),
                   hand_r_rel=(-0.30, 0.06, -0.12), hand_r_dir=(-1.0, 0.0, 0.2), hand_r_palm=(0.0, -1.0, 0.0), elbow_r=(-0.6, 0.8, -0.4),
                   hand_l=(0.34, 0.12, 0.82), hand_l_dir=(0.4, 0.8, 0.3), hand_l_palm=(1.0, 0.0, 0.0), elbow_l=(1.0, 0.0, -0.6),
                   fist_r=0.1, fist_l=0.2, hand_r_relw=1.0, auto_drop=0.0), "in2"),
         # cae sentado: la cadera 3 cm sobre la de Dragged (echado atrás 24°, la cola de la túnica, pesada a Root, se metía
         # 3.8 cm en el piso) y se asienta hasta f36
         Key(IMPACT, P(hips=(0.02, G_HIPS[1] - LAUNCH_SHIFT, G_HIPS[2] + 0.04), hips_rot=(-24.0, 4.0, 13.0), spine=(-4.0, 2.0, 4.0),
                       head=(38.0, 0.0, -4.0), hand_r_rel=(-0.20, 0.0, -0.26), hand_r_dir=(0.0, -0.4, -1.0), hand_r_palm=(1.0, 0.0, 0.0),
                       elbow_r=(-1.0, 0.3, -0.5), elbow_l=(1.0, 0.0, -0.6), fist_r=0.3, fist_l=0.3, knee_r=(-0.3, -1.0, 0.6),
                       knee_l=(0.3, -1.0, 0.6)), "in2"),
         Key(31, P(hips=(0.02, G_HIPS[1] - LAUNCH_SHIFT, G_HIPS[2] + 0.022), hips_rot=(-20.0, 4.0, 11.0), spine=(-3.0, 2.0, 4.0),
                   head=(30.0, 0.0, -6.0), hand_r_rel=(-0.17, -0.04, -0.25), hand_r_dir=(0.0, -0.4, -1.0), hand_r_palm=(1.0, 0.0, 0.0),
                   elbow_r=(-1.0, 0.3, -0.5), fist_r=0.4), "out"),
         # clava los talones y se echa para atrás (lejos del ninja) contra el tirón
         Key(36, P(hips=(0.02, G_HIPS[1] - LAUNCH_SHIFT - 0.01, G_HIPS[2] + 0.025), hips_rot=(-6.0, 4.0, 12.0), spine=(5.0, 2.0, 5.0),
                   head=(14.0, 0.0, -8.0), hand_r_rel=(-0.17, -0.04, -0.25), hand_r_dir=(0.0, -0.4, -1.0), hand_r_palm=(1.0, 0.0, 0.0),
                   elbow_r=(-1.0, 0.3, -0.5), fist_r=0.6)),
         Key(41, P(hips=(0.02, G_HIPS[1] - LAUNCH_SHIFT, G_HIPS[2] + 0.015), hips_rot=(-22.0, 4.0, 10.0), spine=(-3.0, 2.0, 4.0),
                   head=(16.0, 0.0, -14.0), hand_r_rel=(-0.04, -0.31, -0.10), hand_r_dir=(0.0, -1.0, -0.2), hand_r_palm=(0.0, -0.2, -1.0),
                   elbow_r=(-1.0, 0.3, -0.5), fist_r=0.1), "out"),
         Key(DRAG_START, shift_g(raw0[0], -LAUNCH_SHIFT, feet=()))]
    # el ninja: f0 = la guardia agazapada de KidnapWait; carga, corre por el costado izquierdo del abuelo, agarra (GRAB),
    # frena en seco y tira; a los f36-41 tironea dos veces (los talones del abuelo se le van)
    d0 = D[0][1]["hips"]
    n40 = (d0[0], d0[1] + LAUNCH_SHIFT, d0[2])
    n24 = n_at(0.58, 0.52, -0.09)
    N = [Key(0, stalk_pose(kr, 0)),
         Key(6, dict(hips=n_at(0.0, -1.26, -0.08), hips_rot=(24.0, 0.0, 0.0), spine=(12.0, 0.0, 0.0), head=(-18.0, 0.0, 0.0),
                     hand_r_rel=(-0.06, 0.15, -0.21), hand_l_rel=(0.09, -0.02, -0.22), fist_r=0.8, fist_l=0.5,
                     elbow_r=(-1.0, 0.3, 0.0), hand_r_dir=RUN_DIR, hand_r_palm=RUN_PALM, elbow_l=(1.0, 0.3, 0.0))),
         Key(10, dict(hips=n_at(0.18, -0.86, -0.05), hips_rot=(26.0, 0.0, -8.0), spine=(10.0, 0.0, -4.0), head=(-20.0, 0.0, 4.0),
                      hand_r_rel=(-0.06, -0.15, -0.17), hand_l_rel=(0.07, -0.08, -0.17), fist_r=0.9, fist_l=0.5,
                      elbow_r=(-1.0, 0.3, 0.0), hand_r_dir=RUN_DIR, hand_r_palm=RUN_PALM, elbow_l=(1.0, 0.3, 0.0),
                      hand_l_dir=(0.1, -1.0, 0.2), hand_l_palm=(0.0, 0.0, -1.0)), "in2"),
         Key(14, dict(hips=n_at(0.48, -0.36, -0.045), hips_rot=(24.0, 0.0, -4.0), spine=(10.0, 0.0, 2.0), head=(-18.0, 0.0, 22.0),
                      hand_r_rel=(-0.07, 0.12, -0.20), hand_l_rel=(0.10, -0.14, -0.12), fist_r=0.9, fist_l=0.3,
                      elbow_l=(1.0, 0.3, -0.5),
                      elbow_r=(-1.0, 0.3, 0.0), hand_r_dir=RUN_DIR, hand_r_palm=RUN_PALM), "lin"),
         Key(GRAB, dict(hips=n_at(0.60, -0.02, -0.05), hips_rot=(16.0, 0.0, 8.0), spine=(6.0, 0.0, 8.0), head=(-14.0, 0.0, 40.0),
                        hand_r_rel=(-0.17, 0.04, -0.17), fist_r=0.8, **RUN_ARM,
                        # el codo del agarre abajo y afuera, como en Dragged: la mano queda en la muñeca del abuelo y el
                        # ninja pasa de largo, así que el brazo barre de adelante para atrás en 4 cuadros. Con el codo al
                        # costado el barrido pasaba por la dirección del polo y el codo se daba vuelta (97° en un cuadro)
                        elbow_l=(0.6, 0.2, -0.8)), "lin"),
         Key(20, dict(hips=n_at(0.62, 0.30, -0.10), hips_rot=(6.0, 0.0, 24.0), spine=(4.0, 0.0, 14.0), head=(-10.0, 0.0, 55.0),
                      hand_r_rel=(-0.15, -0.12, -0.17), fist_r=0.9, **RUN_ARM), "out"),
         Key(24, dict(hips=n24, hips_rot=(24.0, 0.0, 16.0), spine=(8.0, 0.0, 10.0), head=(-14.0, 0.0, 30.0),
                      hand_r_rel=(-0.05, -0.14, -0.22), fist_r=0.9, **RUN_ARM)),
         Key(30, dict(hips=lerp3(n24, n40, 0.6), hips_rot=(22.0, 0.0, 12.0), spine=(8.0, 0.0, 8.0), head=(-16.0, 0.0, -5.0),
                      hand_r_rel=(-0.05, 0.08, -0.24), fist_r=0.9, **RUN_ARM)),
         # se lo traen de vuelta (el abuelo se echa para atrás) y tironea: se inclina con todo
         Key(36, dict(hips=lerp3(lerp3(n24, n40, 0.6), n40, 0.6), hips_rot=(12.0, 0.0, 14.0), spine=(4.0, 0.0, 10.0), head=(-12.0, 0.0, 30.0),
                      hand_r_rel=(-0.05, 0.02, -0.24), fist_r=0.9, **RUN_ARM)),
         Key(40, dict(hips=n40, hips_rot=(30.0, 0.0, 10.0), spine=(14.0, 0.0, 8.0), head=(-18.0, 0.0, -10.0),
                      hand_r_rel=(-0.05, 0.07, -0.24), fist_r=0.9, **RUN_ARM)),
         Key(DRAG_START, shift_n(raw0[1], -LAUNCH_SHIFT))]
    Gs, Ns = sampler("Kidnap/g", DRAG_START, G), sampler("Kidnap/n", DRAG_START, N)
    n_smooth = {k: smooth_track([Ns(f)[k] for f in range(KID_TAUT + 1)], acc)
                for k, acc in (("hips", NINJA_HIP_ACC), ("hips_rot", NINJA_ROT_ACC), ("spine", NINJA_ROT_ACC))}

    # apoyos. Abuelo: parado; en la pasada da un paso atrás con la izquierda y al caer los pies se le van al aire (arco
    # de 7 cm que llega frenando: antes el derecho barría el piso y frenaba en seco de 3.5 m/s) a los talones de Dragged f0
    # corridos LAUNCH_SHIFT. Sentado clava los talones dos veces más adelante (f30-f34 y f34-f38) y los tirones del ninja
    # se los arrastran de vuelta (raspan a 1.4 cm por cuadro: el polvo de NPC) antes de que arranque el arrastre
    yr0, pr0, _ = heels["r"][0]
    yl0, pl0, _ = heels["l"][0]
    xr, yawr = HEEL_X["r"]
    xl, yawl = HEEL_X["l"]
    yr, yl = yr0 - LAUNCH_SHIFT, yl0 - LAUNCH_SHIFT
    # los talones caen KID_TUCK más cerca de la cadera que en Dragged (con las rodillas más dobladas: estirados hasta ahí
    # la cadera tenía que bajar 7 cm para alcanzarlos y la túnica se metía en el piso) y se estiran en las clavadas
    KID_TUCK, DIG = 0.07, 0.01
    gfeet = {"r": [FR(0), FR(19), T.FootKey(IMPACT, xr, yr + KID_TUCK, yawr, pr0, lift=0.045),
                   T.FootKey(30, xr, yr + KID_TUCK, yawr, pr0), T.FootKey(34, xr, yr - DIG, yawr, -34.0, lift=0.03),
                   T.FootKey(41, xr, yr - DIG, yawr, -34.0), T.FootKey(46, xr, yr, yawr, pr0, lift=0.0)],
             "l": [FL(0), FL(15), T.FootKey(21, 0.16, 0.12, 16.0, 0.0, lift=0.04),
                   T.FootKey(IMPACT, xl, yl + KID_TUCK, yawl, pl0, lift=0.045),
                   T.FootKey(34, xl, yl + KID_TUCK, yawl, pl0), T.FootKey(38, xl, yl - DIG, yawl, -34.0, lift=0.03),
                   T.FootKey(41, xl, yl - DIG, yawl, -34.0), T.FootKey(46, xl, yl, yawl, pl0, lift=0.0)]}

    # ninja: corre por fuera (sus apoyos derechos del lado de afuera; en la carrera el pie de atrás sube en arco alto, el
    # talón hacia la cola: con el arco bajo de los pasos el pie quedaba atrás y abajo y la cadera caía 8 cm para
    # alcanzarlo), frena con la izquierda adelantada, un paso de recuperación con la derecha y entra al ciclo: el último
    # apoyo de cada pie es el de Dragged f0 (ninja_gait)
    def nk(f, x, y, yaw=0.0, pitch=0.0, lift=None, ease="inout"):
        p = duo.g2n((x, y, 0.0))
        return T.FootKey(f, p[0], p[1], yaw, pitch, 0.0, 0.0, ease, lift)
    xr_, yr_, yawr_, pr_, _ = gait.one("r", 0)
    xl_, yl_, yawl_, pl_, _ = gait.one("l", 0)
    fr_end = T.FootKey(KID_N, xr_, yr_, yawr_, pr_, lift=0.05)
    sr, sl = sfeet["r"], sfeet["l"]
    nfeet = {"r": [T.FootKey(0, sr[0], sr[1], sr[2]), T.FootKey(4, sr[0], sr[1], sr[2], 20.0),
                   nk(10, 0.27, -0.93, -6.0, lift=0.12), nk(11, 0.27, -0.93, -6.0, 25.0),
                   nk(GRAB, 0.74, 0.06, -10.0, lift=0.16),
                   nk(20, 0.74, 0.06, -10.0), nk(26, 0.56, 0.70, -8.0), nk(48, 0.56, 0.70, -8.0, 10.0), fr_end],
             "l": [T.FootKey(0, sl[0], sl[1], sl[2]), T.FootKey(7, sl[0], sl[1], sl[2], 25.0),
                   nk(14, 0.46, -0.32, 4.0, lift=0.16), nk(16, 0.46, -0.32, 4.0, 20.0), nk(20, 0.50, 0.46, 14.0, ease="out"),
                   nk(28, 0.50, 0.46, 10.0), T.FootKey(34, xl_, yl_, yawl_), T.FootKey(KID_N, xl_, yl_, yawl_, pl_)]}

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
        if f <= KID_TAUT:
            n.update({k: v[f] for k, v in n_smooth.items()})
        for k in "rl":
            g["foot_" + k], g["foot_%s_rot" % k] = T.sample_feet(ch, k, gfeet[k], f)
            n["foot_" + k], n["foot_%s_rot" % k] = T.sample_feet(kid, k, nfeet[k], f)
        if f < 21:
            g["auto_drop"] = 1.0
        row = duo.resolve(f, g, n, wa=ramp(f, GRAB + 1, GRAB + 6), wb=ramp(f, GRAB - 8, GRAB), wc=ramp(f, 24, 32))
        if f >= KID_TAUT:
            # de KID_TAUT a DRAG_START se funde con el cuadro de arranque (Dragged f0 corrido LAUNCH_SHIFT): el reparto por
            # distancia de Kidnap y el de los brazos tirantes de Dragged dejaban al ninja 11 cm en otro lado y en f47 su
            # cadera y la mano del agarre saltaban eso en un cuadro. Los pies, los de cada uno
            w = NA.ease("inout", (f - KID_TAUT + 1) / float(DRAG_START - KID_TAUT + 1))
            tg, tn = shift_g(D[0][0], -LAUNCH_SHIFT), shift_n(D[0][1], -LAUNCH_SHIFT)
            row = tuple(blend_ctrls(r, t, w, keep=("foot_r", "foot_l", "foot_r_rot", "foot_l_rot")) for r, t in zip(row, (tg, tn)))
        K.append(row)
    # el último cuadro de Kidnap ES Dragged f0 (los pies del ninja del ciclo: mismos apoyos que ninja_gait en f0)
    K[KID_N] = D[0]
    for k in "rl":
        a = T.sample_feet(kid, k, nfeet[k], KID_N)[0]
        b = Vector(D[0][1]["foot_" + k])
        assert (a - b).length < 0.002, f"Kidnap f{KID_N}: el pie {k} del ninja no cae en el de Dragged f0 ({(a - b).length:.3f} m)"

    # ---- KidnapWait: el abuelo de Idle; el ninja en la guardia agazapada, con los pies quietos
    W = []
    for f in range(WAIT_N + 1):
        n = stalk_pose(kr, f % WAIT_N)
        for k in "rl":
            x, y, yaw = sfeet[k]
            n["foot_" + k], n["foot_%s_rot" % k] = kid.foot_at(k, x, y, yaw)
        W.append(n)
    # el cuadro 0 de Kidnap lo resolvió con la guardia (sin agarre): la espera usa las mismas manos desde el hombro
    Wr = [duo.resolve(-1 - f, dict(idle_pose(f % WAIT_N), hand_r_relw=0.0), W[f], wa=0.0, wb=0.0, wc=0.0)[1] for f in range(WAIT_N + 1)]
    Wr[WAIT_N] = Wr[0]

    for name, rows in (("Kidnap", K), ("Dragged", D)):
        print("CONTACTO", name, " ".join(f"f{f}:{duo.contacts(*rows[f])}" for f in range(0, len(rows), 4)))
    print("ALCANCE", {k: round(v, 3) for k, v in duo.reach.items()}, "palma", {k: round(v, 3) for k, v in duo.palm_len.items()})
    print("AGARRE", " ".join(f"f{f}:{d}m" for f, d, wa, wb in duo.report[::6]))
    print("MANO DERECHA DEL NINJA en el antebrazo (cm de falta)", duo.grab_miss)
    print("GRUPO pico", round(DRAG_VMAX, 2), "m/s, atraso máx", round(min(DRAG_LAG) * 100, 1), "cm")

    wait = dense("KidnapWait", WAIT_N, [idle_pose(f % WAIT_N) for f in range(WAIT_N + 1)], loop=True, feet=PLANTED,
                 timing=dict(sheet=[0, 19, 38, 56]), notes="el abuelo de Idle; el ninja agazapado se balancea delante de él")
    wait.partner = dense("KidnapWait/ninja", WAIT_N, Wr, loop=True, timing=dict(sheet=wait.timing["sheet"]))
    kid_g = dense("Kidnap", KID_N, [r[0] for r in K], timing=dict(
        sheet=[0, 6, 10, 14, GRAB, 21, 24, IMPACT, 31, 36, 41, DRAG_START, KID_N], floor_cm=FLOOR_CM,
        # lo que raspan los talones clavados cuando los tirones se los traen (f34-f53, 5 cm): con 24 cm de margen la caída
        # que barría el piso a 15 cm por cuadro pasaba igual
        slide_ok=6.0,
        events=dict(grab=GRAB, impact=IMPACT, grip=32, digs=[[30, 34], [34, 38]], drag_start=DRAG_START)),
        notes="el ninja pasa por la izquierda, le agarra la muñeca y lo tira al piso; se agarran de las muñecas, clava los "
              "talones, se los arrastran y arranca el arrastre")
    # (el tope de la cadera con medio cm para lo que la baja el solver al alcanzar los pies)
    kid_g.partner = dense("Kidnap/ninja", KID_N, [r[1] for r in K],
                          timing=dict(sheet=kid_g.timing["sheet"], hip_acc_cm=NINJA_HIP_ACC * 100.0 + 0.5))
    drag_g = dense("Dragged", DRAG_N, [r[0] for r in D], loop=True, root_vel=(0, DRAG_SPEED, 0), timing=dict(
        sheet=[0, 8, 16, 22, 26, 28, 30, 34, 40, 50, 60, 70], slide_ok=80.0, floor_cm=FLOOR_CM,
        events=dict(resist=[RES_IN, RES_OUT], yank=RES_OUT + 4, two_hands=[24, 40], pull=[RES_OUT, 34], reach=50, limp=[60, 80])),
        notes="arrastrado del brazo: el ninja camina tirando, el abuelo clava los talones, resiste, el tirón y se rinde")
    drag_g.partner = dense("Dragged/ninja", DRAG_N, [r[1] for r in D], loop=True,
                           timing=dict(sheet=drag_g.timing["sheet"], hip_acc_cm=NINJA_HIP_ACC * 100.0 + 0.5))
    return wait, kid_g, drag_g


# =============================================================================== Bound / BoundStruggle / Freed (de rodillas ante el poste)
BOUND_N, STRUGGLE_N, FREED_N = 180, 66, 108
# seiza: la cadera sobre los talones (Root a 0.165 m del piso), los muslos casi horizontales con las rodillas 18 cm
# adelante de la cadera y abiertas; los empeines en el piso con las puntas para atrás. Antes la cadera quedaba a 0.24 m
# con los muslos a 63°: desde la cámara del juego se leía un viejito parado y bajito
SEIZA_HIPS = (0.0, -0.05, -0.32)
SEIZA_Y = -0.06
# la pelvis bien adelante (la cola de la túnica, pesada a Root y que en reposo cae 30 cm detrás de la cadera, sube con
# ella; con 10° se metía 8.8 cm en el piso) y la espalda que la compensa: el tronco queda SEIZA_LEAN adelante
SEIZA_PITCH, SEIZA_LEAN = 35.0, 16.0
FOOT_X = {"r": (-0.075, -10.0), "l": (0.075, 10.0)}
SEIZA_KNEE = {"r": (-0.55, -1.0, -0.2), "l": (0.55, -1.0, -0.2)}
SEIZA_CLEAR = 0.012          # el empeine 1.2 cm sobre el piso (con 0.4 cm la canilla y el pie se metían 2.6 cm)
# dedos metidos (de rodillas sobre la punta de los pies) y parado: el apoyo de Idle (R0/L0), la punta clavada al rodar
TUCK_PITCH = 70.0
# NPC.KneelBound adelanta el transform KNEEL_FWD antes de Bound (y las cuerdas se arman ahí): el zócalo de piedra del
# binding_post arranca 0.1 m detrás del marcador y la falda de la túnica, de rodillas, se abre para atrás. Los clips
# quedan centrados en el transform y Freed termina en Idle sin correrlo
KNEEL_FWD = 0.20
# la cabeza levantada (°, negativo hacia arriba): mira a la arena, a la altura de los que pelean. Con -20 la cara quedaba
# derecha y desde la cámara del juego (52° de picada) el ala del sombrero era un disco que lo tapaba entero
BOUND_HEAD = -36.0
# las manos cruzadas atrás, sobre la cintura (las ata ShadowRopes: la vuelta de abajo y el nudo de las muñecas)
BOUND_HAND_Y, BOUND_HAND_Z = 0.13, 0.40


def seiza_feet(ch, offs):
    out = {}
    for k in "rl":
        x, yaw = FOOT_X[k]
        out["foot_" + k], out["foot_%s_rot" % k] = foot_on_floor(ch, offs[k], k, x, SEIZA_Y, 165.0, yaw, clear=SEIZA_CLEAR)
    return out


def bound_pose(f, sf):
    """Atado de rodillas: el tronco 16° adelante, los hombros tirados atrás y arriba, los codos atrás y las muñecas
    cruzadas sobre la cintura; la cabeza levantada mira la arena de un lado al otro (una vuelta por loop) y respira tres
    veces. Con la cabeza arriba el sombrero se inclina y desde la cámara del juego se ven la cara y los hombros (con la
    cabeza gacha el sombrero era un disco sobre todo el cuerpo)."""
    a = 2.0 * math.pi * f / BOUND_N
    br = 0.5 - 0.5 * math.cos(3.0 * a)
    look, look2 = math.sin(a), math.sin(2.0 * a + 0.7)
    c = dict(
        hips=(SEIZA_HIPS[0], SEIZA_HIPS[1], SEIZA_HIPS[2] + 0.004 * br), hips_rot=(SEIZA_PITCH, 0.0, 2.0 * look),
        spine=(SEIZA_LEAN - SEIZA_PITCH - 2.0 * br, 0.0, 3.0 * look), head=(BOUND_HEAD + 3.0 * math.sin(2.0 * a), 0.0, 18.0 * look + 4.0 * look2),
        breath=br, clav_r=(0.0, 8.0, -14.0 - 2.0 * br), clav_l=(0.0, -8.0, 14.0 + 2.0 * br),
        hand_r=(0.02, BOUND_HAND_Y, BOUND_HAND_Z), hand_r_dir=(1.0, 0.1, -0.4), hand_r_palm=(0.0, 1.0, 0.0), elbow_r=(-0.6, 1.0, 0.0),
        hand_l=(-0.02, BOUND_HAND_Y + 0.01, BOUND_HAND_Z - 0.01), hand_l_dir=(-1.0, 0.1, -0.4), hand_l_palm=(0.0, 1.0, 0.0),
        elbow_l=(0.6, 1.0, 0.0), fist_r=0.6, fist_l=0.6, knee_r=SEIZA_KNEE["r"], knee_l=SEIZA_KNEE["l"], auto_drop=0.0,
    )
    c.update(sf)
    return c


def struggle_delta(f):
    """Lo que el forcejeo le suma a Bound f0 (0 en los dos extremos): junta aire y se achica (f0-f8), tres tirones de
    hombros alternados con la cabeza arriba (f8-f36), se rinde con la cabeza gacha (f36-f50) y se recompone (f50-f66).
    El tronco casi no se mueve a la altura de las cuerdas (están quietas en el mundo): tironean los hombros y la cabeza."""
    gather = math.sin(math.pi * min(1.0, f / 10.0)) if f < 10 else 0.0
    fight = math.sin(math.pi * (f - 8) / 28.0) ** 2 if 8 <= f <= 36 else 0.0
    tug = math.sin(2.0 * math.pi * 1.5 * (f - 8) / 28.0) * fight
    give = math.sin(math.pi * (f - 34) / 32.0) ** 2 if 34 <= f <= 66 else 0.0
    return dict(
        # la pelvis no se echa atrás (la cola de la túnica entraba en el piso): se estira la espalda
        hips=(0.0, 0.0, 0.01 * fight), hips_rot=(2.0 * give, 2.5 * tug, 3.0 * tug),
        spine=(4.0 * gather - 9.0 * fight + 12.0 * give, 2.0 * tug, 5.0 * tug),
        head=(6.0 * gather - 14.0 * fight + 34.0 * give, 0.0, 12.0 * tug),
        clav_r=(0.0, 6.0 * fight * (0.5 + 0.5 * tug) - 4.0 * give, -8.0 * fight * (0.5 + 0.5 * tug) + 6.0 * give),
        clav_l=(0.0, -6.0 * fight * (0.5 - 0.5 * tug) + 4.0 * give, 8.0 * fight * (0.5 - 0.5 * tug) - 6.0 * give),
        breath=0.6 * gather - 0.3 * give,
        hands=(0.0, 0.01 * fight, 0.015 * fight),
    )


def bound_and_freed(ch):
    offs = {k: foot_offsets(ch, k) for k in "rl"}
    sf = seiza_feet(ch, offs)
    rows = [bound_pose(f % BOUND_N, sf) for f in range(BOUND_N + 1)]
    B0 = rows[0]
    srows = []
    for f in range(STRUGGLE_N + 1):
        d = struggle_delta(f)
        c = dict(B0)
        for key in ("hips", "hips_rot", "spine", "head", "clav_r", "clav_l"):
            c[key] = tuple(B0[key][i] + d[key][i] for i in range(3))
        c["breath"] = max(0.0, min(1.0, B0["breath"] + d["breath"]))
        for k in "rl":
            c["hand_" + k] = tuple(B0["hand_" + k][i] + d["hands"][i] for i in range(3))
        srows.append(c)
    srows[STRUGGLE_N] = B0
    # medidas para las cuerdas de sombra (NPC.BoundRope*) y el zócalo del poste
    pr = Probe(ch)
    pose = pr.solve(rows[0])
    p = lambda b: ch.Pc(pose.get(b).translation)
    sd = ch.side
    z = lambda b: round(p(b).z, 3)
    print("BOUND muñecas", z(sd["r"]["hand"]), z(sd["l"]["hand"]), "codos", z(sd["r"]["fore"]), z(sd["l"]["fore"]),
          "hombros", z(sd["r"]["upper"]), z(sd["l"]["upper"]), "rodillas", z(sd["r"]["shin"]), z(sd["l"]["shin"]),
          "cadera", z("Root"), "y muñecas", round(p(sd["r"]["hand"]).y, 3), "y rodillas", round(p(sd["r"]["shin"]).y, 3),
          "x codos", round(p(sd["r"]["fore"]).x, 3), round(p(sd["l"]["fore"]).x, 3),
          "x hombros", round(p(sd["r"]["upper"]).x, 3), round(p(sd["l"]["upper"]).x, 3))
    bound = dense("Bound", BOUND_N, rows, loop=True, timing=dict(sheet=[0, 30, 60, 90, 120, 150], floor_cm=FLOOR_CM),
                  notes="de rodillas en seiza ante el poste, las muñecas cruzadas atrás; respira y mira la arena")
    strug = dense("BoundStruggle", STRUGGLE_N, srows, timing=dict(
        sheet=[0, 6, 14, 20, 26, 32, 42, 50, 58, 66], floor_cm=FLOOR_CM, chain=[(STRUGGLE_N, "Bound", 0, 0.01)],
        events=dict(gather=[0, 8], fight=[8, 36], give_up=[36, 50], recover=[50, 66])),
        notes="forcejea con los hombros contra las cuerdas, levanta la cabeza, se rinde y vuelve a Bound f0")
    return bound, strug, freed(ch, sf, offs, B0)


def freed(ch, sf, offs, B):
    """Libre: los brazos vuelven adelante, se frota las muñecas (la derecha sobre la izquierda y al revés) delante del
    pecho, mira a Kaito, se inclina sobre las rodillas, mete los dedos de los pies, se apoya con las manos en las rodillas
    y se para sin pasos (los pies terminan en los de Idle: NPC.PlayThen lo devuelve ahí sin patinar)."""
    on_thighs = dict(hand_r=(-0.11, -0.19, 0.27), hand_r_dir=(0.0, -1.0, -0.3), hand_r_palm=(0.0, 0.0, -1.0),
                     hand_l=(0.11, -0.19, 0.27), hand_l_dir=(0.0, -1.0, -0.3), hand_l_palm=(0.0, 0.0, -1.0), elbow_r=(-1.0, 0.3, -0.4),
                     elbow_l=(1.0, 0.3, -0.4), fist_r=0.2, fist_l=0.2)
    # se frota bien adelante y a la altura del pecho: desde arriba el ala del sombrero tapaba las manos
    rub_a = dict(hand_l=(0.05, -0.32, 0.50), hand_l_dir=(-1.0, -0.3, 0.1), hand_l_palm=(0.0, 0.2, -1.0), fist_l=0.5,
                 hand_r=(-0.03, -0.31, 0.54), hand_r_dir=(1.0, -0.2, -0.3), hand_r_palm=(0.0, 0.0, -1.0), fist_r=0.6,
                 elbow_r=(-1.0, 0.3, -0.5), elbow_l=(1.0, 0.3, -0.5))
    rub_b = dict(hand_r=(-0.05, -0.32, 0.50), hand_r_dir=(1.0, -0.3, 0.1), hand_r_palm=(0.0, 0.2, -1.0), fist_r=0.5,
                 hand_l=(0.03, -0.31, 0.54), hand_l_dir=(-1.0, -0.2, -0.3), hand_l_palm=(0.0, 0.0, -1.0), fist_l=0.6,
                 elbow_r=(-1.0, 0.3, -0.5), elbow_l=(1.0, 0.3, -0.5))
    # libre, se endereza y se levanta un poco de los talones: la pelvis vuelve a 15° (con la de Bound, 35°, el tronco
    # derecho pedía la espalda arqueada 30° para atrás) y la cadera sube 6 cm para que la cola de la túnica no entre en el
    # piso (enderezado sobre los talones se metía 10 cm)
    KNEEL_UP = (0.0, SEIZA_HIPS[1], -0.26)
    up = dict(hips=KNEEL_UP, hips_rot=(15.0, 0.0, 0.0), spine=(-11.0, 0.0, 0.0))
    I0 = idle_pose(0)
    keys = [Key(0, B),
            Key(6, dict(B, clav_r=(0.0, 0.0, 0.0), clav_l=(0.0, 0.0, 0.0), hand_r=(-0.10, 0.12, 0.42), hand_l=(0.10, 0.13, 0.42),
                        head=(-6.0, 0.0, 0.0), breath=1.0), "out"),
            Key(13, dict(B, clav_r=(0.0, 0.0, 0.0), clav_l=(0.0, 0.0, 0.0), hand_r=(-0.22, -0.06, 0.38), hand_r_dir=(0.0, -0.3, -1.0),
                         hand_r_palm=(1.0, 0.0, 0.0), hand_l=(0.22, -0.06, 0.38), hand_l_dir=(0.0, -0.3, -1.0), hand_l_palm=(-1.0, 0.0, 0.0),
                         elbow_r=(-1.0, 0.3, -0.4), elbow_l=(1.0, 0.3, -0.4), head=(8.0, 0.0, 0.0), hips=KNEEL_UP,
                         hips_rot=(15.0, 0.0, 0.0), spine=(-5.0, 0.0, 0.0), breath=0.4)),
            Key(19, dict(B, **rub_a, head=(8.0, 0.0, 6.0), **up, breath=0.2)),
            Key(36, dict(B, **rub_a, head=(10.0, 0.0, 4.0), **up, breath=0.7), "sine"),
            Key(42, dict(B, **rub_b, head=(8.0, 0.0, -6.0), **up, breath=0.4)),
            Key(50, dict(B, **rub_b, head=(6.0, 0.0, -4.0), **up, breath=0.6), "sine"),
            Key(55, dict(B, **on_thighs, head=(-14.0, 0.0, 0.0), hips=KNEEL_UP, hips_rot=(15.0, 0.0, 0.0), spine=(-9.0, 0.0, 0.0),
                         breath=1.0)),
            Key(61, dict(B, **on_thighs, hips=(0.0, -0.14, -0.235), hips_rot=(18.0, 0.0, 0.0), spine=(10.0, 0.0, 0.0),
                         head=(-14.0, 0.0, 0.0), breath=0.3)),
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
        for k, t0 in (("r", 64), ("l", 66)):
            x, yaw = FOOT_X[k]
            xi, _, yawi = (R0 if k == "r" else L0)
            if f <= t0:
                ank, rot = sf["foot_" + k], sf["foot_%s_rot" % k]
            elif f <= t0 + 8:
                # mete los dedos: el pie gira de empeine a punta en el aire (el punto más bajo sube hasta 4.5 cm a mitad
                # de camino; antes rozaba el piso a 1.2 cm y patinaba 3.7 cm) y la punta se clava en el último cuadro
                u = (f - t0) / 8.0
                s = NA.ease("inout", u)
                a_s = sf["foot_" + k]
                a_t, r_t = ch.foot_at(k, xi, 0.0, yawi, TUCK_PITCH)
                pitch = 165.0 + (TUCK_PITCH - 165.0) * s
                yw = yaw + (yawi - yaw) * s
                ax, ay = a_s[0] + (a_t[0] - a_s[0]) * s, a_s[1] + (a_t[1] - a_s[1]) * s
                (_, _, zc), rot = foot_on_floor(ch, offs[k], k, ax, ay, pitch, yw, clear=SEIZA_CLEAR + 0.045 * math.sin(math.pi * u))
                if f == t0 + 8:
                    ank, rot = a_t, r_t
                else:
                    ank = (ax, ay, zc)
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
        sheet=[0, 6, 13, 19, 30, 42, 55, 61, 68, 74, 80, 86, 92, 98, 108], chain=[(FREED_N, "Idle", 0, 0.02)], floor_cm=FLOOR_CM,
        events=dict(arms_free=6, rub=[19, 50], look=55, tuck=[64, 74], push=[76, 86], stand=98)),
        notes="libre: se frota las muñecas, mira a Kaito, mete los dedos de los pies y se para apoyado en las rodillas")
