"""Animación del Chikuō ermitaño (fase C4): de controles a huesos, el clip con pistas, la caña de la arena y el horneado.

Los clips (chikuo_clips_*.py) son claves de nindo_anim con controles propios de este personaje. Cada cuadro se resuelve
acá (IK analítica de dos huesos, en Python, sin constraints) y después los resortes de nindo_anim hornean lo secundario
(capa, cascabeles, barba, mangas, falda, colas). Ejes del modelo: Blender Z arriba, frente -Y, su derecha = -X.

Espacios (timing['space'] de cada clip, lo que el código hace con el modelo):
  * 'ground': la raíz en el piso, donde está el transform del jefe (el avance lo aplica el código: travel_m).
  * 'perch': la raíz en el PerchNode de la caña (arriba del anillo del nudo del posado: los pies), el culmo es el eje Z
    del clip (x = y = 0) y sube desde z = 0; el código pone el modelo en el PerchNode con su giro (el cuerpo se inclina con
    el arco) y lo gira alrededor del culmo para mirar a Kaito. Se autora sobre la caña de adentro (posado a 4.4 m, culmo de
    r 0.103 en el posado); GripHigh (z 0.9) y el PerchNode están en el mismo tramo (Seg_05): el arco no despega las manos.
  * 'air': la raíz la lleva el código por el arco del salto (de PerchNode a PerchNode, o a donde cae): el cuerpo se autora
    con los pies a la altura de la raíz como en el posado, así el salto empalma con el agachado y con el agarre.
  * 'pole': en el piso, con la flauta-bastón clavada en el piso del clip (la Grulla en el Bastón).

Controles (todos opcionales; los que no trae una clave se interpolan desde las vecinas):
  cuerpo   hips (metros desde el reposo), hips_rot / spine / spine1 / spine2 / neck / head / clav_r / clav_l (grados XYZ)
  mano s   libre: hand_s (muñeca, clip), hand_s_dir (los dedos), hand_s_up (el dorso), elbow_s (hacia dónde va el codo);
           en la flauta: gw_s (peso 0..1), grip_s (metros desde la punta de abajo), grip_s_dors, grip_s_sign (meñique
           hacia la punta de abajo con +1); en el culmo: cw_s (peso), cz_s (altura en el clip), ca_s (grados alrededor del
           culmo: 0 = delante del eje, 90 = a su izquierda), cs_s (+1 pulgar arriba). La mano mezcla las tres por peso.
  dedos    fing_s: forma de chikuo_rig.HAND_SHAPES (o dict con sus números): se interpolan los números
  pierna s foot_s (tobillo), foot_s_rot (grados, sobre el reposo del pie), knee_s (dirección), toe_s (grados)
  flauta   pesos sw_world / sw_spine / sw_lips / sw_hr / sw_hl (se normalizan) y lo de cada modo: stw_pos / stw_dir /
           stw_up (en el clip), sts_* (pegada al pecho: en el clip con Spine2 en reposo, se va con Spine2), stl_at / stl_dir /
           stl_up (un punto suyo en los labios), sth_at / sth_sign (en el puño de la mano que la lleva, por su eje X)
  cara     face: nombre de chikuo_rig.FACES o dict; wink_r / wink_l (0..1 cierra ese párpado además de la cara)
  extra    {hueso: grados} al final (cola de la faja que se acomoda, los pulgares...)
"""
import math
from mathutils import Vector, Matrix, Quaternion
import nindo_anim as NA
from nindo_anim import V, euler_q, basis_yz, compose, rot3
import chikuo_rig as CR

FPS = NA.FPS

# ============================================================================ la caña de la arena (contrato de c4/arena)
# Tools/Blender/world/arena_stalks.py (KINDS) y World/ArenaStalk.cs (SetBend): juntas de los tramos, alto, posado, radios.
STALKS = {
    "inner": dict(length=7.5, perch=4.4, grip=5.3, climb=2.2, r0=0.15, r1=0.07, perch_r=0.17,
                  joints=[0.0, 0.9, 1.75, 2.62, 3.47, 4.32, 5.62, 6.55]),
    "north": dict(length=7.5, perch=4.0, grip=4.9, climb=2.2, r0=0.15, r1=0.07, perch_r=0.17,
                  joints=[0.0, 0.9, 1.68, 2.46, 3.19, 3.92, 5.20, 6.35]),
    "outer": dict(length=8.5, perch=4.8, grip=5.7, climb=2.2, r0=0.15, r1=0.07, perch_r=0.17,
                  joints=[0.0, 0.9, 1.82, 2.78, 3.75, 4.72, 6.10, 7.30]),
    "mother": dict(length=10.0, perch=5.0, grip=5.9, climb=2.2, r0=0.21, r1=0.10, perch_r=0.26,
                   joints=[0.0, 0.9, 1.95, 2.95, 3.94, 4.92, 6.55, 8.15]),
}
AUTHOR = "inner"
PERCH_H = STALKS[AUTHOR]["perch"]
GRIP_Z = STALKS[AUTHOR]["grip"] - PERCH_H          # 0.9: GripHigh en el clip
CLIMB_Z = STALKS[AUTHOR]["climb"] - PERCH_H        # -2.2: ClimbGrip en el clip
RING_R = STALKS[AUTHOR]["perch_r"]                 # el anillo del nudo del posado: donde apoyan los talones


def culm_r(z, kind=AUTHOR):
    """Radio del culmo a la altura z del clip de posado (z = 0 en el PerchNode)."""
    s = STALKS[kind]
    h = z + s["perch"]
    return s["r0"] + (s["r1"] - s["r0"]) * max(0.0, min(1.0, h / s["length"]))


def bend_frames(theta, direction=(0.0, 1.0, 0.0), even=0.0, kind=AUTHOR):
    """Las matrices de los ocho tramos de la caña doblada 'theta' grados hacia 'direction' (horizontal, en el espacio del
    clip con la caña recta), con la base en z = -perch: lo mismo que ArenaStalk.SetBend (cada tramo gira theta * w_k
    alrededor del eje Cross(arriba, dirección) en su junta, sobre el giro de los de abajo)."""
    s = STALKS[kind]
    d = V(direction)
    d.z = 0.0
    d = d.normalized() if d.length > 1e-6 else Vector((0.0, 1.0, 0.0))
    ax = Vector((0.0, 0.0, 1.0)).cross(d).normalized()
    out, M = [], Matrix.Translation((0.0, 0.0, -s["perch"]))
    prev_h = 0.0
    n = len(s["joints"])
    tot = n * (n + 1) * 0.5
    for k, h in enumerate(s["joints"]):
        w = (1.0 - even) * (k + 1) / tot + even / n
        M = M @ Matrix.Translation((0.0, 0.0, h - prev_h)) @ Matrix.Rotation(math.radians(theta * w), 4, ax)
        prev_h = h
        out.append(M.copy())
    return out


def seg_of(z, kind=AUTHOR):
    s = STALKS[kind]
    h = z + s["perch"]
    return max(i for i, j in enumerate(s["joints"]) if j <= h + 1e-6) if h >= 0 else 0


def perch_frame(theta, direction=(0.0, 1.0, 0.0), kind=AUTHOR):
    """Dónde queda el PerchNode (con su giro) en la caña doblada: ahí pone el código la raíz del modelo."""
    s = STALKS[kind]
    segs = bend_frames(theta, direction, 0.0, kind)
    k = seg_of(0.0, kind)
    return segs[k] @ Matrix.Translation((0.0, 0.0, s["perch"] - s["joints"][k]))


def on_bent(p, theta, direction=(0.0, 1.0, 0.0), kind=AUTHOR):
    """Un punto del clip de posado (caña recta) llevado a la caña doblada como lo lleva el código (con el PerchNode),
    y el mismo punto del culmo recto llevado por su propio tramo: la diferencia es lo que se despega del culmo."""
    s = STALKS[kind]
    P = perch_frame(theta, direction, kind)
    segs = bend_frames(theta, direction, 0.0, kind)
    k = seg_of(p.z, kind)
    base = Matrix.Translation((0.0, 0.0, -s["perch"] + s["joints"][k]))
    on_seg = segs[k] @ base.inverted() @ V(p)
    return P @ V(p), on_seg


# ============================================================================ formas de las manos y caras como números
def shape_vec(shape):
    h = CR.HAND_SHAPES[shape] if isinstance(shape, str) else shape
    return tuple(h["fing"]) + tuple(h["tip"]) + (h["spread"],) + tuple(h["thumb"])


def vec_shape(v):
    v = list(v)
    return dict(fing=tuple(v[0:4]), tip=tuple(v[4:8]), spread=v[8], thumb=tuple(v[9:11]))


def face_vec(face):
    f = CR.FACES[face] if isinstance(face, str) else face
    return (f["jaw"], f["lids"], f["brows"], f["cheeks"], f["corners"][0], f["corners"][1])


def vec_face(v):
    return dict(jaw=v[0], lids=v[1], brows=v[2], cheeks=v[3], corners=(v[4], v[5]))


TUPLE_CH = ("_fing_r", "_fing_l", "_face")


# ============================================================================ claves con atajos
def staff_world(pos, d, up=(0, 0, 1)):
    return dict(sw_world=1.0, sw_spine=0.0, sw_lips=0.0, sw_hr=0.0, sw_hl=0.0, stw_pos=tuple(pos), stw_dir=tuple(d), stw_up=tuple(up))


def staff_spine(pos, d, up=(0, 0, 1)):
    """Pegada al pecho (cruzada en los hombros): pos/d/up en el clip con Spine2 en reposo."""
    return dict(sw_world=0.0, sw_spine=1.0, sw_lips=0.0, sw_hr=0.0, sw_hl=0.0, sts_pos=tuple(pos), sts_dir=tuple(d), sts_up=tuple(up))


def staff_lips(at, d, up=(0, 0, 1)):
    return dict(sw_world=0.0, sw_spine=0.0, sw_lips=1.0, sw_hr=0.0, sw_hl=0.0, stl_at=at, stl_dir=tuple(d), stl_up=tuple(up))


def staff_hand(s, at, sign=1.0):
    return dict(sw_world=0.0, sw_spine=0.0, sw_lips=0.0, sw_hr=1.0 if s == "r" else 0.0, sw_hl=1.0 if s == "l" else 0.0,
                sth_at=at, sth_sign=sign)


def free(s, pos, d=None, up=None, elbow=None, fing=None, chest=False):
    """La mano s libre en 'pos' (la muñeca). Sin d/up la muñeca queda neutra sobre el antebrazo (fa_s). chest: pos, d, up y
    el codo en el marco del pecho en reposo (la mano se va con el tronco)."""
    k = {"gw_" + s: 0.0, "cw_" + s: 0.0, "hand_" + s: tuple(pos), "hsp_" + s: 1.0 if chest else 0.0}
    if d is None:
        k["fa_" + s] = 1.0
    else:
        k.update({"fa_" + s: 0.0, "hand_%s_dir" % s: tuple(d), "hand_%s_up" % s: tuple(up)})
    if elbow is not None:
        k["elbow_" + s] = tuple(elbow)
    if fing is not None:
        k["fing_" + s] = fing
    return k


def grip(s, at, dors="auto", sign=None, elbow=None, fing="grip_staff"):
    """La mano s en la flauta a 'at' metros de la punta de abajo. dors 'auto' (o una dirección como pista): el giro del
    puño alrededor del caño lo elige el plan del clip (Solver.plan_rolls), el que menos le cuesta a la muñeca."""
    k = {"gw_" + s: 1.0, "cw_" + s: 0.0, "grip_" + s: at}
    if isinstance(dors, str):
        k["grip_%s_auto" % s] = 1.0
    else:
        k["grip_%s_dors" % s] = tuple(dors)
        k["grip_%s_auto" % s] = 0.0
    if sign is not None:
        k["grip_%s_sign" % s] = sign
    if elbow is not None:
        k["elbow_" + s] = tuple(elbow)
    if fing is not None:
        k["fing_" + s] = fing
    return k


GRIP_CULM = dict(fing=(32, 36, 40, 44), tip=(38, 42, 44, 48), spread=-1.0, thumb=(10, 6))


def culm(s, z, az, thumb=0.0, elbow=None, fing=GRIP_CULM):
    """La mano s en el culmo a la altura z del clip, en el costado az (grados desde adelante hacia su izquierda); thumb +1
    pulgar arriba, -1 abajo, 0 el que deja los dedos siguiendo al antebrazo."""
    k = {"gw_" + s: 0.0, "cw_" + s: 1.0, "cz_" + s: z, "ca_" + s: az, "cs_" + s: thumb}
    if elbow is not None:
        k["elbow_" + s] = tuple(elbow)
    if fing is not None:
        k["fing_" + s] = fing
    return k


def legs(fr, fl, rr=(0, 0, 0), rl=(0, 0, 0), kr=(0, -1, 0), kl=(0, -1, 0), toe=None, hips=False):
    """Los dos pies (tobillos, giro sobre el reposo, rodillas). hips: en el marco de la cadera en reposo (vuelos)."""
    k = dict(foot_r=tuple(fr), foot_l=tuple(fl), foot_r_rot=tuple(rr), foot_l_rot=tuple(rl), knee_r=tuple(kr), knee_l=tuple(kl),
             fsp_r=1.0 if hips else 0.0, fsp_l=1.0 if hips else 0.0)
    if toe is not None:
        k["toe_r"], k["toe_l"] = toe
    return k


def merge(*ds, **kw):
    out = {}
    for d in ds:
        for k, v in d.items():
            if k == "extra" and "extra" in out:
                out["extra"] = {**out["extra"], **v}
            else:
                out[k] = v
    for k, v in kw.items():
        if k == "extra" and "extra" in out:
            out["extra"] = {**out["extra"], **v}
        else:
            out[k] = v
    return out


def prep_ctrl(c):
    """Las formas de las manos y la cara por nombre pasan a números (para interpolarlas)."""
    c = dict(c)
    for s in "rl":
        if "fing_" + s in c:
            c["_fing_" + s] = shape_vec(c.pop("fing_" + s))
    if "face" in c:
        c["_face"] = face_vec(c.pop("face"))
    return c


# ============================================================================ el clip
class CClip(NA.Clip):
    """Clip de Chikuō: claves del cuerpo y pistas aparte (pies, flauta, cara, una mano) que tienen sus propias claves y
    curvas; la última pista que trae un canal manda. 'timing' va al sidecar (space, tell, apex, contact, load...)."""

    def __init__(self, name, frames, keys, tracks=(), loop=False, timing=None, events=None, notes="", lag=None,
                 spring_vel=None, cuts=(), root_vel=(0, 0, 0), bend=0.0):
        for k in keys:
            k.ctrl = prep_ctrl(k.ctrl)
        super().__init__(name, frames, keys, loop=loop, lag=lag, timing=timing, events=events, notes=notes, root_vel=root_vel)
        self.tracks = []
        for tk in tracks:
            for k in tk:
                k.ctrl = prep_ctrl(k.ctrl)
            self.tracks.append(CClip(name + "_pista", frames, tk, loop=loop))
        self.spring_vel = spring_vel          # f -> desplazamiento del cuerpo en el mundo para los resortes (vuelos)
        self.cuts = set()
        for a, b in cuts:
            self.cuts.update(range(a, b + 1))
        self.bend = bend                      # grados del arco de la caña para medir las manos y los pies en el culmo

    def sample(self, f, channel):
        if channel in TUPLE_CH:
            ks = self.keys
            ff = max(0.0, min(float(self.frames), f))
            i = self._seg(ff)
            a, b = ks[i], ks[i + 1]
            s = NA.ease(b.ease_ch.get(channel, b.ease), (ff - a.frame) / max(1e-6, b.frame - a.frame))
            va, vb = a.ctrl.get(channel), b.ctrl.get(channel)
            if va is None and vb is None:
                return None
            va = vb if va is None else va
            vb = va if vb is None else vb
            return tuple(x + (y - x) * s for x, y in zip(va, vb))
        return super().sample(f, channel)

    def controls(self, f):
        out = {}
        chans = set()
        for k in self.keys:
            chans.update(k.ctrl.keys())
        for c in chans:
            lag = self.lag.get(c, 0.0)
            if not self.loop:
                lag *= max(0.0, min(1.0, f / 3.0, (self.frames - f) / 3.0))
            ff = f - lag
            if self.loop:
                ff = ff % self.frames
            out[c] = self.sample(ff, c)
        ft = f % self.frames if self.loop else f
        for t in self.tracks:
            tch = set()
            for k in t.keys:
                tch.update(k.ctrl.keys())
            for c in tch:
                v = t.sample(ft, c)
                if v is not None:
                    out[c] = v
        return out


# ============================================================================ el solver
class Solver(CR.Poser):
    """Controles -> huesos (ver el resumen arriba). Hereda de chikuo_rig.Poser el hombro que se adelanta, los dedos, la
    cara y la capa que sigue a los brazos."""
    TWIST_SHARE = 0.6        # lo que el antebrazo se lleva del giro de la mano sobre su eje (pronación)
    FORE_MAX = math.radians(100.0)
    ELBOW_RATE = 30.0
    GRIP_ELBOW_RATE = 30.0
    HAND_RATE = 35.0
    FING_RATE = 38.0         # lo más que se cierra o se abre un dedo por cuadro (soltar o atajar es de a dos cuadros)
    ROLLS = [math.radians(a) for a in range(0, 360, 15)]

    def __init__(self, rig):
        super().__init__(rig)
        import chikuo_lint as LT
        self.meter = LT.WristMeter(rig)
        self.mode, self.frame, self.plan, self.costs = None, 0, {}, {}
        self.nframes = 0
        self.cplan, self.ccosts, self.culm_override = {}, {}, None
        self.pins, self.cpins = {}, {}
        self.side_hint = {}
        self.twist = {"R": 0.0, "L": 0.0}
        self.prev_elbow, self.cur_elbow = {}, {}
        self.prev_fing = {}
        self.prev_hand_rel = {}
        self.prev_elbow_pos = {}
        self.last_staff_z = None
        self.last_staff_q = None

    # agarres del culmo que se prueban: pulgar arriba / abajo y corrimientos del costado pedido (grados); y para todo
    # agarre (flauta o culmo), cuánto gira el codo alrededor del eje hombro-muñeca desde el polo pedido (grados)
    CULM_TRY = [(t, d) for t in (1.0, -1.0) for d in (-50.0, -25.0, 0.0, 25.0, 50.0)]
    SWIVELS = (-45.0, -22.5, 0.0, 22.5, 45.0)

    def begin(self, mode):
        """'collect' junta lo que le cuesta a la muñeca cada agarre posible en cada cuadro; 'replay' usa el plan."""
        self.mode = mode
        self.prev_elbow, self.cur_elbow = {}, {}
        self.prev_fing = {}
        self.prev_hand_rel = {}
        self.prev_elbow_pos = {}
        self.last_staff_z = None
        self.last_staff_q = None
        if mode == "collect":
            self.costs = {"r": {}, "l": {}}
            self.ccosts = {"r": {}, "l": {}}
            self.side_hint = {}

    @staticmethod
    def runs(frames, have):
        """Tramos seguidos de cuadros que están en 'have'."""
        out, f = [], 0
        while f < frames:
            if f not in have:
                f += 1
                continue
            run = []
            while f in have:
                run.append(f)
                f += 1
            out.append(run)
        return out

    def plan_culm(self, frames):
        """Por mano y por agarre seguido del culmo: el pulgar (arriba o abajo), el costado (el pedido +-50°) y el codo que
        menos le cuestan a la muñeca en todo el agarre (no cambian mientras agarra: la mano no resbala por el culmo)."""
        self.cplan = {"r": {}, "l": {}}
        tries = [(t, sw) for t in self.CULM_TRY for sw in self.SWIVELS]
        for s in "rl":
            cs = self.ccosts.get(s, {})
            for run in self.runs(frames, cs):
                # el costado y el codo pedidos pesan un poco (es lo que quiso el animador): 0.3 por cada 25° de corrimiento
                tot = [sum(cs[fi][k] for fi in run) + (0.3 * abs(t[1]) / 25.0 + 0.2 * abs(sw) / 22.5) * len(run)
                       for k, (t, sw) in enumerate(tries)]
                for fi in run:
                    pin = self.cpins.get((s, fi))
                    if pin is not None:
                        tot = [v + (0.0 if (t[0], t[1], sw) == pin else 1e6) for v, (t, sw) in zip(tot, tries)]
                k = min(range(len(tot)), key=lambda i: tot[i])
                (t, d), sw = tries[k]
                for fi in run:
                    self.cplan[s][fi] = (t, d, sw)

    def plan_rolls(self, frames):
        """Por mano, cómo agarra la flauta en cada cuadro que la agarra con 'auto': el giro del puño alrededor del caño,
        hacia qué punta va el meñique y el giro del codo. Es el camino más barato (programación dinámica) entre lo que le
        cuesta a la muñeca y lo que cuesta cambiar de un cuadro al otro: el puño no resbala alrededor del caño y el codo no
        salta (cada paso de la grilla cuesta), y el meñique no cambia de punta en un mismo agarre (sería soltarla: se prueba
        cada lado entero y se queda el más barato)."""
        self.plan = {"r": {}, "l": {}}
        n = len(self.ROLLS)
        ns = len(self.SWIVELS)
        for s in "rl":
            cs = self.costs.get(s, {})
            for run in self.runs(frames, cs):
                best = None
                for side in (0, 1):
                    # estado = (codo, giro): índice si * n + ri; el costo del cuadro sale de la grilla de collect
                    def cost_at(fi):
                        row = []
                        # la punta hacia la que va el meñique, si la clave la pide (grip_s_side): el otro lado cuesta
                        want = self.side_hint.get((s, fi))
                        bias = 3.0 if want is not None and want != side else 0.0
                        for si, sw in enumerate(self.SWIVELS):
                            off = (si * 2 + side) * n
                            row += [v + 0.2 * abs(sw) / 22.5 + bias for v in cs[fi][off:off + n]]
                        pin = self.pins.get((s, fi))
                        if pin is not None:
                            # el agarre de la pose de encadenado: cualquier otro cuesta muchísimo
                            pr, ps, psw = pin
                            k = min(range(n), key=lambda i: abs(((self.ROLLS[i] - pr + math.pi) % (2 * math.pi)) - math.pi))
                            ks = min(range(ns), key=lambda i: abs(self.SWIVELS[i] - psw))
                            row = [v + (0.0 if (ps == side and st == ks * n + k) else 1e6) for st, v in enumerate(row)]
                        return row
                    acc = [cost_at(run[0])]
                    back = []
                    for fi in run[1:]:
                        cost = cost_at(fi)
                        prev = acc[-1]
                        row, brow = [], []
                        for sj in range(ns):
                            for j in range(n):
                                bv, bi = 1e18, 0
                                for si in range(max(0, sj - 1), min(ns, sj + 2)):
                                    sc = 1.5 * abs(si - sj)
                                    base = si * n
                                    for i in range(n):
                                        d = abs(((i - j + n // 2) % n) - n // 2)
                                        # el puño no gira más de 45° alrededor del caño de un cuadro al otro (con el costo
                                        # cuadrático solo, a veces le convenía un salto grande en el último cuadro de un loop)
                                        v = prev[base + i] + 0.6 * d * d + sc + (1e5 if d > 3 else 0.0)
                                        if v < bv:
                                            bv, bi = v, base + i
                                row.append(bv + cost[sj * n + j])
                                brow.append(bi)
                        acc.append(row)
                        back.append(brow)
                    j = min(range(len(acc[-1])), key=lambda k: acc[-1][k])
                    total = acc[-1][j]
                    if best is not None and total >= best[0]:
                        continue
                    path = [j]
                    for brow in reversed(back):
                        j = brow[j]
                        path.append(j)
                    path.reverse()
                    best = (total, side, path)
                _, side, path = best
                for fi, st in zip(run, path):
                    self.plan[s][fi] = (self.ROLLS[st % n], side, self.SWIVELS[st // n])

    def wrist_cost(self, pose, S, miss):
        flex, dev, tw = self.meter.angles(pose.W, S)
        import chikuo_lint as LT
        ex = LT.wrist_excess(flex, dev)
        # la mano sobre su eje: el antebrazo prona y supina ~100°; más es la muñeca retorcida (y pasar por los 180° le da
        # media vuelta al antebrazo en un cuadro)
        roll = 0.03 * self.twist[S] + 6.0 * max(0.0, (self.twist[S] - 100.0) / 40.0) ** 2 +             60.0 * max(0.0, (self.twist[S] - 140.0) / 40.0) ** 2
        return 10.0 * max(0.0, ex - 0.55) ** 2 + 0.2 * ex + 2.0 * max(0.0, (abs(tw) - 55.0) / 45.0) ** 2 + roll + 400.0 * miss * miss

    def solve(self, pose, c):
        R = self.rig
        g = lambda k, d=None: d if c.get(k) is None else c.get(k)
        hip_rest = R.rest["Hips"]
        Hm = compose(hip_rest.translation + V(g("hips", (0, 0, 0))), euler_q(g("hips_rot", (0, 0, 0))).to_matrix() @ rot3(hip_rest))
        pose.place("Hips", Hm)
        for bn, k in (("Spine", "spine"), ("Spine1", "spine1"), ("Spine2", "spine2"), ("Neck", "neck"), ("Head", "head"),
                      ("Clav_R", "clav_r"), ("Clav_L", "clav_l")):
            pose.delta(bn, g(k, (0, 0, 0)))
        # la flauta: modos que no dependen de las manos
        w = {m: max(0.0, g("sw_" + m, 0.0)) for m in ("world", "spine", "lips", "hr", "hl")}
        mats = []
        if w["world"] > 1e-4:
            mats.append((self.staff_from(g("stw_pos"), g("stw_dir"), g("stw_up", (0, 0, 1)), self.last_staff_z), w["world"]))
        if w["spine"] > 1e-4:
            S2 = pose.get("Spine2") @ R.rest_inv["Spine2"]
            tz = rot3(S2).inverted() @ self.last_staff_z if self.last_staff_z is not None else None
            M = self.staff_from(g("sts_pos"), g("sts_dir"), g("sts_up", (0, 0, 1)), tz)
            mats.append((S2 @ M, w["spine"]))
        if w["lips"] > 1e-4:
            d = V(g("stl_dir")).normalized()
            mouth = pose.get("Head") @ R.rest_inv["Head"] @ CR.MOUTH
            mats.append((self.staff_from(mouth - d * g("stl_at"), d, g("stl_up", (0, 0, 1))), w["lips"]))
        carriers = [s for s in "rl" if w["h" + s] > 1e-4]
        self.misses = {}
        staff = None
        if mats:
            # con una mano que la lleva, la de los otros modos es provisoria: la mano que pasa de agarrarla a llevarla la
            # agarra ahí (el peso de la mano decide cuánto)
            staff = self.limit_staff(blend_mats(mats))
            pose.place("Staff", staff)
        # las manos: primero la que lleva la flauta (si la lleva una), después la otra (que puede agarrarla)
        order = carriers + [s for s in "rl" if s not in carriers]
        for s in order:
            self.arm(pose, c, s, staff)
            if s in carriers and len(mats) + len(carriers) and s == carriers[-1]:
                for cs in carriers:
                    Hw = pose.get("Hand_" + cs.upper())
                    ax = rot3(Hw).col[0] * g("sth_sign", 1.0)
                    gp = Hw @ CR.GRIP_LOCAL
                    mats.append((compose(gp - ax * g("sth_at", 1.0), basis_yz(ax, rot3(Hw).col[2])), w["h" + cs]))
                staff = self.limit_staff(blend_mats(mats))
                pose.place("Staff", staff)
        if staff is None:
            # sin modo: queda donde la deja el reposo (no pasa en los clips de pelea)
            pose.get("Staff")
        self.last_staff_z = rot3(pose.get("Staff")).col[2].copy()
        self.last_staff_q = rot3(pose.get("Staff")).to_quaternion()
        for S in "RL":
            s = S.lower()
            ank = V(g("foot_" + s, tuple(CR.ANKLE if S == "R" else CR.mx(CR.ANKLE))))
            pr = g("foot_%s_rot" % s, (0, 0, 0))
            Rf = (Matrix.Rotation(math.radians(pr[2]), 3, 'Z') @ Matrix.Rotation(math.radians(pr[0]), 3, 'X')
                  @ Matrix.Rotation(math.radians(pr[1]), 3, 'Y')) @ rot3(R.rest["Foot_" + S])
            knee = V(g("knee_" + s, (0, -1, 0)))
            fs = max(0.0, min(1.0, g("fsp_" + s, 0.0)))
            if fs > 1e-4:
                # el pie autorado en el marco de la cadera en reposo (se va con la cadera: el cuerpo que da vueltas)
                M = pose.get("Hips") @ R.rest_inv["Hips"]
                R3 = rot3(M)
                ank = ank.lerp(M @ ank, fs)
                knee = knee.lerp(R3 @ knee, fs)
                Rf = Rf.to_quaternion().slerp((R3 @ Rf).to_quaternion(), fs).to_matrix()
            self.misses["leg_" + s] = pose.two_bone("Thigh_" + S, "Shin_" + S, ank, knee)
            pose.place("Foot_" + S, compose(pose.tail("Shin_" + S), Rf))
            ax = rot3(R.rest["Toe_" + S]).col[0]
            pose.delta("Toe_" + S, Quaternion(ax, math.radians(g("toe_" + s, 0.0))))
            fv = c.get("_fing_" + s)
            fv = list(fv) if fv is not None else list(shape_vec("relaxed"))
            pv = self.prev_fing.get(s)
            if pv is not None:
                # de un agarre a la mano abierta en un cuadro el dedo giraba 60°: se cierra o se abre a FING_RATE
                fv = [p + max(-self.FING_RATE, min(self.FING_RATE, v - p)) for v, p in zip(fv, pv)]
            self.prev_fing[s] = fv
            self.fingers(pose, S, vec_shape(fv))
        self.follow_cloak(pose)
        fc = vec_face(c["_face"]) if c.get("_face") is not None else dict(CR.FACES["grin"])
        self.face(pose, fc)
        for S in "RL":
            wk = c.get("wink_" + S.lower())
            if wk:
                ax = rot3(R.rest["Lid_" + S]).col[0]
                pose.delta("Lid_" + S, Quaternion(ax, -math.radians(CR.LID_CLOSED_DEG * min(1.0, fc["lids"] + wk))))
        for bn, r in (c.get("extra") or {}).items():
            pose.delta(bn, r)
        self.prev_elbow = dict(self.cur_elbow)
        return self.misses

    STAFF_RATE = 40.0

    def limit_staff(self, M):
        """La flauta gira a lo sumo STAFF_RATE por cuadro (un giro más rápido entre dos claves se reparte en los cuadros
        que siguen); las manos agarran la que queda, así que siguen pegadas."""
        qp = self.last_staff_q
        if qp is None:
            return M
        q = rot3(M).to_quaternion()
        if q.dot(qp) < 0.0:
            q = -q
        ang = q.rotation_difference(qp).angle
        lim = math.radians(self.STAFF_RATE)
        if ang <= lim:
            return M
        return compose(M.translation, qp.slerp(q, lim / ang).to_matrix())

    def staff_from(self, bottom, d, up, transport=None):
        """La flauta con la punta de abajo en bottom, el eje d y el lado 'up' (lo que se ve de los agujeros). Si 'up' queda
        casi a lo largo del eje (la flauta parada con up (0, 0, 1)), el lado sale del cuadro anterior: sin esto la flauta
        daba media vuelta sobre su eje al pasar por la vertical. Con 'transport' (el lado del cuadro anterior, en el mismo
        marco: la flauta en el mundo o en el pecho) el lado sigue al anterior y recién en los últimos cuatro cuadros del clip
        vuelve al pedido: entre dos claves con lados distintos la flauta giraba media vuelta sobre su eje en un cuadro (en la
        cerbatana y la flauta de costado el lado es el de los agujeros y manda siempre el pedido)."""
        d = V(d).normalized()
        up = V(up)
        u = up - d * up.dot(d)
        w = max(0.0, min(1.0, (0.5 - u.length) / 0.4))
        if w > 0.0:
            prev = self.last_staff_z if self.last_staff_z is not None else d.orthogonal()
            p = prev - d * prev.dot(d)
            p = p.normalized() if p.length > 1e-6 else d.orthogonal()
            u = (u.normalized() * (1.0 - w) if u.length > 1e-6 else Vector()) + p * w
            if u.length < 1e-6:
                u = p
        if transport is not None and self.nframes:
            p = V(transport) - d * V(transport).dot(d)
            if p.length > 1e-6:
                e = max(0.0, min(1.0, (self.frame - (self.nframes - 4)) / 4.0))
                e = e * e * (3.0 - 2.0 * e)
                u = p.normalized() * (1.0 - e) + u.normalized() * e
                if u.length < 1e-6:
                    u = p
        return compose(V(bottom), basis_yz(d, u))

    def hand_targets(self, pose, c, s, staff):
        """Las tres maneras de poner la mano (libre, en la flauta, en el culmo) con su peso: [(muñeca, giro o None, peso)].
        Giro None = la muñeca neutra sobre el antebrazo que quede (mano libre con fa_s)."""
        g = lambda k, d=None: d if c.get(k) is None else c.get(k)
        S = s.upper()
        sg = 1.0 if S == "R" else -1.0
        out = []
        gw = max(0.0, min(1.0, g("gw_" + s, 0.0))) if staff is not None else 0.0
        cw = max(0.0, min(1.0, g("cw_" + s, 0.0)))
        fw = max(0.0, 1.0 - gw - cw)
        if gw > 1e-4:
            ax = rot3(staff).col[1]
            gp = staff.translation + ax * g("grip_" + s, 1.0)
            sign = g("grip_%s_sign" % s, sg)
            if g("grip_%s_auto" % s, 0.0) > 0.5:
                rs = self.roll_override if self.roll_override is not None else self.plan.get(s, {}).get(self.frame, (0.0, 0))
                roll, side = rs[0], rs[1]
                # el giro 0 es el dorso hacia el hombro: medido desde el cuerpo y no desde el eje Z de la flauta (que gira
                # sobre sí misma), el plan es continuo en el mundo aunque la flauta dé vueltas
                sh = (pose.get("Clav_" + S) @ self.rig.rel["UpperArm_" + S]).translation
                ref = sh - gp
                ref = ref - ax * ref.dot(ax)
                zf = rot3(staff).col[2]
                wz = max(0.0, min(1.0, (0.15 - ref.length) / 0.1))
                ref = (ref.normalized() * (1.0 - wz) if ref.length > 1e-6 else Vector()) + zf * wz
                dors = Quaternion(ax, roll) @ ref.normalized()
                sign = sg if side == 0 else -sg
            else:
                dors = V(g("grip_%s_dors" % s, (0, 0, 1)))
            dors = dors - ax * dors.dot(ax)
            dors = dors.normalized() if dors.length > 1e-6 else ax.orthogonal()
            xdir = ax * sign
            ydir = dors.cross(xdir).normalized()
            Hr = Matrix((xdir, ydir, dors)).transposed()
            out.append((gp - Hr @ CR.GRIP_LOCAL, Hr, gw))
        if cw > 1e-4:
            z = g("cz_" + s, GRIP_Z)
            a = math.radians(g("ca_" + s, 180.0))
            u = Vector((math.sin(a), -math.cos(a), 0.0))
            A = Vector((0.0, 0.0, z))
            cs = g("cs_" + s, 0.0)
            if not cs:
                # el pulgar y el costado que eligió el plan del clip (plan_culm), o los que se están probando
                cp = self.culm_override if self.culm_override is not None else self.cplan.get(s, {}).get(self.frame, (1.0, 0.0))
                cs, daz = cp[0], cp[1]
                a += math.radians(daz)
                u = Vector((math.sin(a), -math.cos(a), 0.0))
            # el eje X de la mano derecha mira al meñique y el de la izquierda al pulgar (espejo): pulgar arriba con +1
            xdir = Vector((0.0, 0.0, 1.0)) * (cs * -sg)
            ydir = u.cross(xdir).normalized()
            Hr = Matrix((xdir, ydir, u)).transposed()
            out.append((A - Hr @ culm_local(culm_r(z)), Hr, cw))
        if fw > 1e-4 and c.get("hand_" + s) is not None:
            pos = V(c["hand_" + s])
            hd, hu = V(g("hand_%s_dir" % s, (0, 0, -1))), V(g("hand_%s_up" % s, (-sg, 0, 0)))
            hs = max(0.0, min(1.0, g("hsp_" + s, 0.0)))
            if hs > 1e-4:
                # la mano autorada en el marco del pecho en reposo (se va con el tronco: vuelos, volteretas)
                M = pose.get("Spine2") @ self.rig.rest_inv["Spine2"]
                R3 = rot3(M)
                pos = pos.lerp(M @ pos, hs)
                hd = hd.lerp(R3 @ hd, hs)
                hu = hu.lerp(R3 @ hu, hs)
            fa = max(0.0, min(1.0, g("fa_" + s, 0.0)))
            out.append((pos, None if fa > 0.5 else basis_yz(hd, hu), fw))
        return out

    roll_override = None
    swivel_override = None

    def arm(self, pose, c, s, staff):
        S = s.upper()
        clav = pose.get("Clav_" + S).copy()
        if self.mode == "collect" and staff is not None and (c.get("gw_" + s) or 0.0) > 0.01 and (c.get("grip_%s_auto" % s) or 0.0) > 0.5:
            hint = c.get("grip_%s_side" % s)
            if hint is not None:
                self.side_hint[(s, self.frame)] = int(round(hint))
            row = []
            for sw in self.SWIVELS:
                for side in (0, 1):
                    for r in self.ROLLS:
                        self.roll_override, self.swivel_override = (r, side), sw
                        pose.place("Clav_" + S, clav)
                        self.place_arm(pose, c, s, staff)
                        row.append(self.wrist_cost(pose, S, self.misses[s]))
            self.roll_override = self.swivel_override = None
            self.costs[s][self.frame] = row
        if self.mode == "collect" and (c.get("cw_" + s) or 0.0) > 0.01 and not (c.get("cs_" + s) or 0.0):
            row = []
            for t in self.CULM_TRY:
                for sw in self.SWIVELS:
                    self.culm_override, self.swivel_override = t, sw
                    pose.place("Clav_" + S, clav)
                    self.place_arm(pose, c, s, staff)
                    row.append(self.wrist_cost(pose, S, self.misses[s]))
            self.culm_override = self.swivel_override = None
            self.ccosts[s][self.frame] = row
        pose.place("Clav_" + S, clav)
        self.place_arm(pose, c, s, staff)

    def swivel_for(self, c, s):
        """El giro del codo de este cuadro: el que se prueba, o el del plan del agarre que más pesa."""
        if self.swivel_override is not None:
            return self.swivel_override
        gw, cw = c.get("gw_" + s) or 0.0, c.get("cw_" + s) or 0.0
        # pesado por cuánto agarra: el codo entra y sale del giro del plan de a poco (al soltar vuelve al polo pedido)
        if gw >= cw and (c.get("grip_%s_auto" % s) or 0.0) > 0.5:
            p = self.plan.get(s, {}).get(self.frame)
            return p[2] * min(1.0, gw) if p else 0.0
        if cw > gw:
            p = self.cplan.get(s, {}).get(self.frame)
            return p[2] * min(1.0, cw) if p else 0.0
        return 0.0

    def place_arm(self, pose, c, s, staff):
        S = s.upper()
        sg = 1.0 if S == "R" else -1.0
        tg = self.hand_targets(pose, c, s, staff)
        if not tg:
            for bn in ("UpperArm_", "Forearm_", "Hand_"):
                pose.get(bn + S)
            self.misses[s] = 0.0
            return
        tot = sum(t[2] for t in tg)
        wrist = sum((t[0] * (t[2] / tot) for t in tg), Vector())
        self.reach_with_clavicle(pose, S, wrist)
        pole = V(c.get("elbow_" + s) or (sg * -0.3, 0.2, -1))
        hs = max(0.0, min(1.0, c.get("hsp_" + s) or 0.0))
        if hs > 1e-4:
            pole = pole.lerp(rot3(pose.get("Spine2") @ self.rig.rest_inv["Spine2"]) @ pole, hs)
        sw = self.swivel_for(c, s)
        sh = (pose.get("Clav_" + S) @ self.rig.rel["UpperArm_" + S]).translation
        axis = wrist - sh
        if sw and axis.length > 1e-6:
            pole = Quaternion(axis.normalized(), math.radians(sw)) @ pole
        pe = self.prev_elbow.get(S)
        free_w = 1.0 - min(1.0, (c.get("gw_" + s) or 0.0) + (c.get("cw_" + s) or 0.0))
        # el lado del codo del cuadro anterior (al grabar): el codo de verdad si el brazo estaba doblado, si no su polo
        po = self.prev_elbow_pos.get(S) if self.mode == "replay" else None
        if axis.length > 1e-6:
            nax = axis.normalized()
            prev_side = None
            for v in (po, pe):
                if v is not None:
                    w_ = v - nax * v.dot(nax)
                    if w_.length > 0.05 * (v.length if v is po else 1.0):
                        prev_side = w_.normalized()
                        break
            b = pole - nax * pole.dot(nax)
            if prev_side is not None and b.length < 0.35 * pole.length:
                # el polo pedido casi a lo largo del brazo (la mano afuera a la altura del hombro con el codo pedido
                # también afuera): no dice de qué lado va el codo y la IK lo daba vuelta; se queda del lado anterior
                wq = b.length / (0.35 * pole.length)
                pole = (b.normalized() * wq if b.length > 1e-6 else Vector()) + prev_side * (1.0 - wq)
        # el codo gira alrededor del eje hombro-muñeca a lo sumo ELBOW_RATE por cuadro con la mano suelta (con el brazo
        # casi estirado o casi plegado el polo pedido pasa al otro lado y la IK daba vuelta el codo en un cuadro) y
        # GRIP_ELBOW_RATE con la que agarra, solo al grabar (en 'collect' el polo del cuadro anterior es el del último
        # agarre probado; el plan no salta, pero el polo pedido entre dos claves sí podía cruzar el eje)
        lim_deg = self.ELBOW_RATE if free_w >= 0.5 else (self.GRIP_ELBOW_RATE if self.mode == "replay" else None)
        if pe is not None and axis.length > 1e-6 and lim_deg is not None:
            nax = axis.normalized()
            a = prev_side if prev_side is not None else pe - nax * pe.dot(nax)
            b = pole - nax * pole.dot(nax)
            if a.length > 1e-4 and b.length > 1e-4:
                ang = a.angle(b)
                lim = math.radians(lim_deg)
                if ang > lim:
                    cr = a.cross(b)
                    rot_ax = cr.normalized() if cr.length > 1e-6 else nax
                    pole = Quaternion(rot_ax, lim) @ a.normalized()
        self.misses[s] = pose.two_bone("UpperArm_" + S, "Forearm_" + S, wrist, pole)
        self.cur_elbow[S] = V(pole)
        if self.mode == "replay":
            self.prev_elbow_pos[S] = pose.head("Forearm_" + S) - sh
        q = None
        acc = 0.0
        for p, Hr, wt in tg:
            if Hr is None:
                # la muñeca neutra: la relación antebrazo-mano del reposo sobre el antebrazo de este cuadro
                Hr = rot3(pose.get("Forearm_" + S)) @ self.meter.side[S][0]
            qq = Hr.to_quaternion()
            if q is None:
                q, acc = qq, wt
            else:
                if q.dot(qq) < 0.0:
                    qq = -qq
                acc += wt
                q = q.slerp(qq, wt / acc)
        # la mano suelta no gira sobre el antebrazo más de HAND_RATE por cuadro: al soltar un agarre pasa de a poco a la
        # muñeca pedida (de golpe el antebrazo se llevaba media vuelta en un cuadro); la que agarra manda y deja su
        # relación para cuando suelte
        Ff = rot3(pose.get("Forearm_" + S)).to_quaternion()
        rel = Ff.inverted() @ q
        pr = self.prev_hand_rel.get(S)
        if pr is not None and free_w >= 0.5:
            if rel.dot(pr) < 0.0:
                rel = -rel
            ang = rel.rotation_difference(pr).angle
            lim = math.radians(self.HAND_RATE)
            if ang > lim:
                rel = pr.slerp(rel, lim / ang)
                q = Ff @ rel
        self.prev_hand_rel[S] = rel.copy()
        pose.place("Hand_" + S, compose(pose.tail("Forearm_" + S), q.to_matrix()))
        # el antebrazo se lleva parte del giro de la mano sobre su eje (pronación), hasta FORE_MAX. Solo depende de la
        # pose (así el primer y el último cuadro de un clip son iguales a la pose con la que encadena); pasar por los 180°
        # lo evitan el plan de agarres (wrist_cost) y, con la mano suelta, HAND_RATE
        Wf = pose.get("Forearm_" + S)
        base = (Wf @ self.rig.rel["Hand_" + S]).inverted() @ pose.get("Hand_" + S)
        qb = base.to_quaternion()
        ang = (2.0 * math.atan2(qb.y, qb.w) + math.pi) % (2.0 * math.pi) - math.pi
        self.twist[S] = abs(math.degrees(ang))

        share = max(-self.FORE_MAX, min(self.FORE_MAX, ang * self.TWIST_SHARE))
        pose.place("Forearm_" + S, compose(Wf.translation, rot3(Wf) @ Matrix.Rotation(share, 3, 'Y')))


def culm_local(r):
    """Dónde pasa el eje del culmo (radio r) en el espacio de la mano que lo agarra: la palma apoyada en la superficie
    (PALM_LOCAL está en la piel de la palma) y el eje a r más adentro, hacia la palma (-Z)."""
    return Vector((0.0, CR.PALM_LOCAL.y + 0.004, CR.PALM_LOCAL.z - r - 0.010))


def blend_mats(mats):
    tot = sum(w for _, w in mats)
    pos = sum((M.translation * (w / tot) for M, w in mats), Vector())
    q, acc = None, 0.0
    for M, w in mats:
        qq = rot3(M).to_quaternion()
        if q is None:
            q, acc = qq, w
            continue
        if q.dot(qq) < 0.0:
            qq = -qq
        acc += w
        q = q.slerp(qq, w / acc)
    return compose(pos, q.to_matrix())


class Kit:
    """Medir poses ya resueltas (sin resortes) para autorar claves que empalman: dónde queda una mano, la flauta o un
    punto del cuerpo en una pose de control."""

    def __init__(self, rig):
        self.rig = rig
        self.solver = Solver(rig)

    def W(self, ctrl):
        pose = NA.Pose(self.rig)
        self.solver.mode, self.solver.frame, self.solver.plan = None, 0, {}
        self.solver.solve(pose, prep_ctrl(merge(ctrl)))
        for n in self.rig.names:
            pose.get(n)
        return pose.W

    def hand(self, ctrl, s):
        """(muñeca, dedos, dorso) de la mano s."""
        M = self.W(ctrl)["Hand_" + s.upper()]
        R = rot3(M)
        return tuple(M.translation), tuple(R.col[1]), tuple(R.col[2])

    def staff(self, ctrl):
        """(punta de abajo, dirección, Z) de la flauta: para una clave staff_world que empalme."""
        M = self.W(ctrl)["Staff"]
        R = rot3(M)
        return tuple(M.translation), tuple(R.col[1]), tuple(R.col[2])

    def point(self, ctrl, bone, local=(0, 0, 0)):
        return tuple(self.W(ctrl)[bone] @ V(local))


# ============================================================================ resortes
def culm_spheres(rig, z0=-4.5, z1=1.6, step=0.10, pad=0.05):
    """Esferas a lo largo del culmo (en Root: la caña recta del clip de posado), para que la capa, la barba y los
    cascabeles no la atraviesen (pad: el radio de un tubo de cascabel; los resortes chocan con la punta)."""
    out = []
    z = z0
    while z <= z1 + 1e-6:
        r = culm_r(z) + pad
        out.append(("Root", rig.rest_inv["Root"] @ Vector((0.0, 0.0, z)), r))
        z += step
    # el anillo del nudo del posado (más grueso)
    out.append(("Root", rig.rest_inv["Root"] @ Vector((0.0, 0.0, -0.06)), RING_R + 0.01))
    return out


# cuánto busca colgar a plomo cada tela según cuánto se aparta su pose rígida de la vertical (HANG_LO .. HANG_HI grados):
# parado la capa, la barba, las mangas y los cascabeles conservan la forma del modelo (las hojas que se abren, los tubos
# que se apartan de las hojas) y solo se mecen; inclinado caen de a poco y cabeza abajo caen enteras hacia el piso
# alrededor de la cabeza (la hoja original)
HANG_LO, HANG_HI, HANG_FULL = 35.0, 110.0, 0.95
CARRY = 0.85                 # lo que la tela se lleva de la traslación de su raíz en cada cuadro (run_springs)


def chain_colliders(first, colliders):
    """Las esferas con las que choca una cadena en el horneado: ninguna con las de la flauta (en un barrido de la flauta
    pasaban a los cascabeles y a la barba de un lado al otro en un cuadro: en el juego las usa SpringChain), las mangas
    no con las de su propio brazo (cuelgan de él: empezaban adentro y temblaban) y el moño y la ramita no con la de la
    cabeza; la barba y las colas de la faja solo con el cuerpo."""
    out = []
    for c in colliders:
        b = c[0]
        if b == "Staff":
            continue
        if first.startswith("Sleeve_") and b.endswith("_" + first.split("_")[1]) and b.startswith(("UpperArm_", "Forearm_")):
            continue
        if first.startswith(("Topknot_", "Acc_LeafKnot")) and b == "Head":
            continue
        # la barba y las colas de la faja, solo con el cuerpo: un antebrazo que pasa delante del pecho (la cerbatana) la
        # tiraba al costado en un cuadro
        if first.startswith(("Acc_TasselBeard", "Acc_TieSash")) and b.startswith(("UpperArm_", "Forearm_", "Head")):
            continue
        out.append(c)
    return out


def springs(rig, colliders, floor, cloak_hang=None, hang_scale=1.0):
    """Los resortes de chikuo_rig.chains() con el colgar que depende de la inclinación (HANG_LO/HI); el moño va rígido
    (pelo duro atado). cloak_hang fija otro máximo para la capa y hang_scale escala el colgar de todas (0 dando vueltas).
    Los cascabeles se hornean más firmes y amortiguados que el péndulo del juego: el clip es la pose a la que tira
    SpringChain, que les pone el bamboleo encima."""
    out = []
    for bones, k, hang, mx in CR.chains():
        if bones[0] == "Topknot_1":
            # el moño es pelo duro atado: va rígido con la cabeza (con resorte vibraba entre los topes a cada cuadro)
            continue
        colliders_b = chain_colliders(bones[0], colliders)
        damp = 0.2
        hang = HANG_FULL
        if cloak_hang is not None and bones[0].startswith("Cloak_"):
            hang = cloak_hang
        # dando vueltas en el aire no hay un 'abajo' que dure: colgar hacia el piso daba vuelta la barba y los cascabeles
        # cada vez que el cuerpo pasaba cabeza abajo (timing['hang_scale'] lo apaga)
        hang *= hang_scale
        b0 = bones[0]
        # firmeza del horneado por tela (rigidez, amortiguación, tope): lo justo para que se atrasen y se asienten sin
        # darse vuelta en los golpes de cadera rápidos; la barba, la ramita y las colas tienen física en el juego encima
        for pre, kk, dd, mm in (("Acc_Chimes", 110.0, 0.45, 60.0), ("Acc_TasselBeard", 120.0, 0.42, 45.0),
                                ("Acc_LeafKnot", 160.0, 0.45, 40.0), ("Acc_TieSash", 120.0, 0.40, 50.0),
                                ("Sleeve_", 200.0, 0.45, 35.0), ("Cloak_", 90.0, 0.30, 65.0), ("Skirt_", 160.0, 0.30, 60.0)):
            if b0.startswith(pre):
                k, damp, mx = kk, dd, mm
        sp = NA.Spring(bones, k=k, damp=damp, grav=3.0, max_deg=mx, hang=hang, floor=floor, colliders=colliders_b)
        # lo más que cuelga de su pose rígida: las mangas son tela pegada al brazo (no se dan vuelta), la barba y la
        # ramita están atadas a la cara; la capa, la falda y los cascabeles cuelgan enteros
        sp.hang_max = 40.0 if b0.startswith("Sleeve_") else 30.0 if b0.startswith("Acc_LeafKnot") else             100.0 if b0.startswith("Acc_TasselBeard") else 180.0
        sp.sag_ref = "Spine2" if b0.startswith("Cloak_") else "Hips" if b0.startswith("Skirt_") else None
        # las hojas de la capa cuelgan debajo de la cola de cada tramo (medido en la malla: 0.10 el de arriba, 0.16 el
        # del medio, 0.27 el último) y los paños de adelante de la falda 0.22: el piso se le pide a la punta de la hoja,
        # no a la cola (en guardia la capa de atrás se metía 7 cm en el piso con las colas a 20 cm)
        sp.drop = {b: cloak_drop(b) for b in bones}
        out.append(sp)
    return out


def cloak_drop(b):
    """Lo que la malla de un hueso de tela baja debajo de su cola (m): las hojas de la capa y el ruedo de la falda."""
    if b.startswith("Cloak_"):
        seg, n = int(b[-1]), CR.cloak_segs(float(b.split("_")[1]))
        return 0.27 if seg == n else 0.16 if seg > 1 else 0.10
    if b in ("Skirt_040", "Skirt_320"):
        return 0.22
    return 0.0


DEV_RATE = 32.0              # lo más que la tela cambia su apartamiento de la pose por cuadro (grados)


def run_springs(rig, frames, springs, root_offsets, loop=False, preroll=1.0, substeps=4, floor_offsets=None, carry=CARRY):
    """nindo_anim.run_springs con una diferencia: el giro que se le aplica al hueso va de su dirección RÍGIDA a la
    simulada. La de nindo_anim lo mide desde la dirección que ya cuelga ('hang') y lo aplica a la rígida: con el cuerpo
    derecho casi no cambia nada, pero cabeza abajo la capa quedaba apuntando al cielo (se perdía el colgar entero). Copia
    propia para no mover los clips de los otros personajes que usan la compartida."""
    n = len(frames)
    if n == 0 or not springs:
        return
    order = []
    for s in springs:
        order += s.bones
    spring_of = {b: s for s in springs for b in s.bones}
    riders = []
    for b in order:
        for c in rig.subtree(b)[1:]:
            if c not in spring_of and c not in riders:
                riders.append(c)
    prim = [dict(W) for W in frames]

    def base_of(W, b):
        p = rig.parent[b]
        return (W[p] @ rig.rel[b]).inverted() @ W[b] if p else rig.rest_inv[b] @ W[b]

    state = {}
    dt = 1.0 / FPS / substeps
    cyc = n - 1 if loop and n > 1 else n
    seq = ([i % cyc for i in range(cyc * 4)] + list(range(cyc))) if loop else ([0] * int(preroll * FPS) + list(range(n)))
    record_from = len(seq) - cyc
    shift = (root_offsets[cyc] - root_offsets[0]) if loop and n > 1 else Vector()
    down = Vector((0.0, 0.0, -1.0))

    sag_cache = {}

    def sag_q(ref, hang, M):
        """El giro común del paño colgado de 'ref' (el pecho para la capa, la cadera para la falda) en este cuadro."""
        key = (ref, hang)
        q = sag_cache.get(key)
        if q is None:
            R3 = rot3(M)
            bdown = -R3.col[1]
            tilt = math.degrees(bdown.angle(down))
            u = max(0.0, min(1.0, (tilt - HANG_LO) / (HANG_HI - HANG_LO)))
            turn = math.radians(tilt * hang * u * u * (3.0 - 2.0 * u))
            g_ax = bdown.cross(down)
            x_ax = R3.col[0]
            if g_ax.length > 1e-6 and x_ax.dot(g_ax) < 0.0:
                x_ax = -x_ax
            wg = max(0.0, min(1.0, (g_ax.length - 0.08) / 0.25))
            ax = (g_ax.normalized() * wg + x_ax * (1.0 - wg)) if g_ax.length > 1e-6 else x_ax
            q = Quaternion(ax.normalized(), turn) if turn > 1e-5 else Quaternion()
            sag_cache[key] = q
        return q

    def solve_frame(fi, lap=0):
        sag_cache.clear()
        P = prim[fi]
        fo = floor_offsets[fi] if floor_offsets else 0.0
        Wc = dict(P)
        off = Matrix.Translation(root_offsets[fi] + shift * lap)
        offi = off.inverted()
        spheres = {}
        for b in order:
            s = spring_of[b]
            sph = []
            for cb, cl, cr in s.colliders:
                key = (cb, tuple(cl))
                if key not in spheres:
                    spheres[key] = off @ (P[cb] @ V(cl))
                sph.append((spheres[key], cr))
            p = rig.parent[b]
            Fp = (off @ Wc[p]) if p else off
            F = Fp @ rig.rel[b] @ base_of(P, b)
            h = F.translation
            L = rig.length[b]
            t = F @ Vector((0.0, L, 0.0))
            rigid = (t - h).normalized()
            if getattr(s, "sag_ref", None):
                # la capa y la falda cuelgan juntas: todo el paño gira lo mismo hacia el piso según cuánto se inclina el
                # tronco (de costado o cabeza abajo, paño por paño cada uno caía distinto y la cáscara se estiraba)
                t = h + (sag_q(s.sag_ref, s.hang, off @ P[s.sag_ref]) @ rigid) * L
            elif s.hang > 0.0:
                tilt = math.degrees(rigid.angle(down)) if rigid.length > 0 else 0.0
                u = max(0.0, min(1.0, (tilt - HANG_LO) / (HANG_HI - HANG_LO)))
                hg = s.hang * u * u * (3.0 - 2.0 * u)
                if hg > 1e-4:
                    turn = min(tilt * hg, getattr(s, "hang_max", 180.0))
                    # el eje del arco hacia abajo; casi cabeza abajo el de la gravedad se vuelve ambiguo (slerp_dir elegía
                    # uno cualquiera y la tela daba media vuelta en un cuadro): ahí se mezcla de a poco con el del eje Z del
                    # hueso, que es el mismo cuadro a cuadro
                    g_ax = rigid.cross(down)
                    z_ax = rigid.cross(rot3(F).col[2])
                    z_ax = z_ax.normalized() if z_ax.length > 1e-6 else rigid.orthogonal().normalized()
                    if g_ax.length > 1e-6 and z_ax.dot(g_ax) < 0.0:
                        z_ax = -z_ax
                    wg = max(0.0, min(1.0, (g_ax.length - 0.08) / 0.25))
                    ax = (g_ax.normalized() * wg + z_ax * (1.0 - wg)) if g_ax.length > 1e-6 else z_ax
                    ax = ax.normalized() if ax.length > 1e-6 else z_ax
                    t = h + (Quaternion(ax, math.radians(turn)) @ rigid) * L
            fl = None if s.floor is None else s.floor + fo + getattr(s, "drop", {}).get(b, 0.0)
            if fl is not None and t.z < fl:
                t.z = fl
                dv = t - h
                t = h + dv.normalized() * L if dv.length > 1e-6 else t
            st = state.get(b)
            if st is None:
                st = state[b] = [t.copy(), t.copy(), t.copy(), h.copy()]
            x, xp, tp, hp = st[:4]
            # la tela se lleva casi todo lo que se traslada su raíz en el cuadro (el aire y el roce la arrastran): sin esto
            # la corrección del largo de un cuerpo que sube rápido (trepar, la picada) quedaba como velocidad y la capa
            # salía volando para arriba
            dh = (h - hp) * carry
            x, xp = x + dh, xp + dh
            vt = (t - tp - dh) / substeps
            for _ in range(substeps):
                acc = (t - x) * s.k + Vector((0.0, 0.0, -s.grav))
                xn = x + (x - xp) * (1.0 - s.damp) + vt * s.damp + acc * dt * dt
                dirn = xn - h
                if dirn.length < 1e-6:
                    dirn = t - h
                xn = h + dirn.normalized() * L
                x_before = xn.copy()
                for cc, cr in sph:
                    dv = xn - cc
                    if dv.length < cr:
                        prev = x - cc
                        if dv.dot(prev) < 0.0 or dv.length < 1e-6:
                            dv = prev
                        xn = cc + dv.normalized() * cr
                        dirn = xn - h
                        if dirn.length > 1e-6:
                            xn = h + dirn.normalized() * L
                    else:
                        # el punto del tramo más cercano a la esfera: si entra, se gira el tramo lo justo para sacarlo
                        seg = xn - h
                        tt = max(0.0, min(1.0, (cc - h).dot(seg) / max(1e-9, seg.length_squared)))
                        if 0.15 < tt < 1.0:
                            pc = h + seg * tt
                            dd = pc - cc
                            if dd.length < cr:
                                nrm = dd.normalized() if dd.length > 1e-6 else (x - cc).normalized()
                                xn = xn + nrm * ((cr - dd.length) / tt)
                                dirn = xn - h
                                if dirn.length > 1e-6:
                                    xn = h + dirn.normalized() * L
                push = xn - x_before
                if push.length > 0.015:
                    xn = x_before + push.normalized() * 0.015
                    dirn = xn - h
                    if dirn.length > 1e-6:
                        xn = h + dirn.normalized() * L
                if fl is not None and xn.z < fl:
                    xn.z = fl
                    dirn = xn - h
                    if dirn.length > 1e-6:
                        xn = h + dirn.normalized() * L
                xp, x = x, xn
            b0 = (t - h).normalized()
            a = (x - h).normalized()
            ang = math.degrees(a.angle(b0)) if a.length > 0 and b0.length > 0 else 0.0
            if ang > s.max_deg:
                # el tope, girando por el plano entre la pose y la simulada (opuestas, por el eje Z del hueso: slerp_dir
                # elegía un eje cualquiera)
                ax = b0.cross(a)
                if ax.length < 1e-4:
                    ax = b0.cross(rot3(F).col[2])
                x = h + (Quaternion(ax.normalized(), math.radians(s.max_deg)) @ b0) * L
                if fl is not None and x.z < fl:
                    # el piso manda sobre el tope (sentado, la capa se apoya en el piso aunque se aparte más de la pose)
                    x.z = fl
                    dirn = x - h
                    if dirn.length > 1e-6:
                        x = h + dirn.normalized() * L
            q = rigid.rotation_difference((x - h).normalized())
            qp = st[4] if len(st) > 4 else None
            if qp is not None:
                # la tela no se aparta de su pose más de DEV_RATE por cuadro: en un golpe de cadera la capa o un cascabel
                # pasaban de un tope al opuesto en un cuadro (130-180°)
                if q.dot(qp) < 0.0:
                    q = -q
                ang = q.rotation_difference(qp).angle
                lim = math.radians(DEV_RATE)
                if ang > lim:
                    q = qp.slerp(q, lim / ang)
                    x = h + (q @ rigid) * L
            st[0], st[1], st[2], st[3] = x, xp, t.copy(), h.copy()
            if len(st) > 4:
                st[4] = q.copy()
            else:
                st.append(q.copy())
            Wc[b] = offi @ compose(h, q.to_matrix() @ rot3(F))
        for c in riders:
            Wc[c] = Wc[rig.parent[c]] @ rig.rel[c] @ base_of(P, c)
        return Wc

    tail = max(3, min(8, cyc // 2)) if loop else 0
    prev_lap = {}
    for i, fi in enumerate(seq):
        Wc = solve_frame(fi, i // cyc if loop else 0)
        if i >= record_from:
            frames[fi] = Wc
        elif loop and i >= record_from - cyc and fi >= cyc - tail:
            prev_lap[fi] = Wc
    if loop and n > 1:
        # la última vuelta grabada arranca donde terminó la anterior (la costura de adelante es continua); la de atrás se
        # funde en los últimos cuadros con la vuelta anterior, que es la que desemboca en el cuadro 0: la tela que choca
        # con los muslos corriendo no repite exacto y sin esto la costura del loop saltaba de velocidad
        for fi in range(cyc - tail, cyc):
            w = (fi - (cyc - tail) + 1) / float(tail)
            w = w * w * (3.0 - 2.0 * w)
            A, B = frames[fi], prev_lap[fi]
            out = dict(A)
            for b in order:
                p = rig.parent[b]
                la = A[p].inverted() @ A[b]
                lb = B[p].inverted() @ B[b]
                q = la.to_quaternion().slerp(lb.to_quaternion(), w)
                out[b] = out[p] @ compose(la.translation.lerp(lb.translation, w), q.to_matrix())
            for c in riders:
                out[c] = out[rig.parent[c]] @ (A[rig.parent[c]].inverted() @ A[c])
            frames[fi] = out
        frames[n - 1] = dict(frames[0])


def bake(rig, clip, solver, base_colliders, pin_from=None, pin_to=None):
    """Resuelve y hornea un clip: (poses W por cuadro, controles, raíces del juego por cuadro, faltas del IK por cuadro).
    pin_from / pin_to: los agarres (flauta y culmo) del primer y del último cuadro de la pose con la que encadena (los de
    su clip de referencia): así el fundido del código no ve la mano girar sobre el caño."""
    space = clip.timing.get("space", "ground")
    ctl = [clip.controls(f) for f in range(clip.frames + 1)]
    solver.nframes = clip.frames
    solver.plan, solver.cplan, solver.pins, solver.cpins = {}, {}, {}, {}
    for fr, pin in ((0, pin_from), (clip.frames, pin_to)):
        if pin:
            for s_, v in pin["roll"].items():
                solver.pins[(s_, fr)] = v
            for s_, v in pin["culm"].items():
                solver.cpins[(s_, fr)] = v
    if any((c.get("grip_r_auto") or 0) > 0.5 or (c.get("grip_l_auto") or 0) > 0.5 or (c.get("cw_r") or 0) > 0.01 or
           (c.get("cw_l") or 0) > 0.01 for c in ctl):
        solver.begin("collect")
        for f, c in enumerate(ctl):
            solver.frame = f
            solver.solve(NA.Pose(rig), c)
        solver.plan_rolls(clip.frames + 1)
        solver.plan_culm(clip.frames + 1)
        if clip.loop:
            # el loop vuelve al agarre del primer cuadro
            for s_ in "rl":
                if 0 in solver.plan.get(s_, {}) and clip.frames in solver.plan[s_]:
                    solver.pins[(s_, clip.frames)] = solver.plan[s_][0]
            solver.plan_rolls(clip.frames + 1)
    solver.begin("replay")
    misses = []
    frames, ctrls, roots = [], [], []
    for f in range(clip.frames + 1):
        c = ctl[f]
        solver.frame = f
        pose = NA.Pose(rig)
        misses.append(dict(solver.solve(pose, c)))
        for n in rig.names:
            pose.get(n)
        frames.append(pose.W)
        ctrls.append(c)
        roots.append(Vector((0.0, -(c.get("travel") or 0.0), 0.0)) + clip.root_vel * (f / FPS))
    smooth_free_arms(rig, frames, ctrls, clip.cuts)
    cols = list(base_colliders)
    if space in ("perch",):
        cols += culm_spheres(rig)
    floor = 0.02 if space in ("ground", "pole") else None
    if clip.spring_vel is not None:
        soff = [V(clip.spring_vel(f)) for f in range(clip.frames + 1)]
    else:
        soff = roots
    lifts = [min(0.0, c.get("lift") or 0.0) for c in ctrls]
    t = clip.timing
    run_springs(rig, frames, springs(rig, cols, floor, t.get("cloak_hang"), t.get("hang_scale", 1.0)), soff, loop=clip.loop,
                   preroll=t.get("preroll", 1.0), floor_offsets=lifts, carry=t.get("carry", 0.6 if space == "ground" else CARRY))
    if clip.loop:
        frames[-1] = {n: m.copy() for n, m in frames[0].items()}
    clip.grips = {"first": grips_at(solver, 0), "last": grips_at(solver, clip.frames)}
    return frames, ctrls, roots, misses


ARM_RATE = 40.0                # lo más que gira un hueso del brazo suelto por cuadro después del alisado (grados)


def smooth_free_arms(rig, frames, ctrls, cuts=()):
    """Alisa los brazos de las manos sueltas (sin agarre: nada que despegar) donde un hueso del brazo gira más de
    ARM_RATE en un cuadro: el IK de un brazo plegado (el yugo, una mano que pasa cerca del hombro) da vuelta el codo con un
    corrimiento chico de la muñeca. Los cuadros sueltos se acercan al promedio de sus vecinos hasta que el giro entra (los
    agarrados quedan fijos y hacen de ancla); después se rearma la mano con sus dedos sobre el brazo alisado."""
    n = len(frames)
    for S in "RL":
        s = S.lower()
        chain = ["UpperArm_" + S, "Forearm_" + S, "Hand_" + S]
        free = [1.0 - min(1.0, (c.get("gw_" + s) or 0.0) + (c.get("cw_" + s) or 0.0)) >= 0.5 and f not in cuts
                for f, c in enumerate(ctrls)]
        if not any(free):
            continue
        loc = [{b: ((W[rig.parent[b]] @ rig.rel[b]).inverted() @ W[b]).to_quaternion() for b in chain} for W in frames]
        changed = set()
        for _ in range(40):
            worst = 0.0
            for f in range(n):
                if not free[f]:
                    continue
                for b in chain:
                    q = loc[f][b]
                    nb = [loc[g][b] for g in (f - 1, f + 1) if 0 <= g < n]
                    big = max(NA.quat_angle_deg(q, x) for x in nb)
                    if big > ARM_RATE:
                        worst = max(worst, big)
                        if len(nb) == 2:
                            a, c = nb
                            if a.dot(c) < 0.0:
                                c = -c
                            mid = a.slerp(c, 0.5)
                        else:
                            mid = nb[0]
                        if q.dot(mid) < 0.0:
                            mid = -mid
                        loc[f][b] = q.slerp(mid, 0.5)
                        changed.add(f)
            if worst <= ARM_RATE:
                break
        sub = rig.subtree("UpperArm_" + S)
        for f in changed:
            W = frames[f]
            # lo de abajo del brazo (la mano, los dedos, las mangas) se rearma con su relación de antes
            locs = {c: (W[rig.parent[c]] @ rig.rel[c]).inverted() @ W[c] for c in sub}
            for c in sub:
                if c in chain:
                    locs[c] = compose(locs[c].translation, loc[f][c].to_matrix())
                W[c] = (W[rig.parent[c]] @ rig.rel[c]) @ locs[c]


def grips_at(solver, f):
    """Los agarres planeados de un cuadro: {"roll": {mano: (giro, lado)}, "culm": {mano: (pulgar, corrimiento)}}."""
    return {"roll": {s: solver.plan[s][f] for s in "rl" if f in solver.plan.get(s, {})},
            "culm": {s: solver.cplan[s][f] for s in "rl" if f in solver.cplan.get(s, {})}}
