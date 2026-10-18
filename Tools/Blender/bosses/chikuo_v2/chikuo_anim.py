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
import numpy as np
from mathutils import Vector, Matrix, Quaternion
import nindo_anim as NA
from nindo_anim import V, euler_q, basis_yz, compose, rot3
import chikuo_rig as CR

FPS = NA.FPS
TWIST_SHARE_MAX_DEG = 100.0  # lo más que el antebrazo se lleva del giro de la mano (prona y supina ~100°)

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
        # el marco de la mano suelta (hpp_s) se toma de las claves donde está suelta: una clave agarrada que pide el codo en
        # el marco del clip (hsp 0) junto a una suelta con el pecho (hsp 1) mezclaba la posición autorada en el reposo con
        # la del pecho y la muñeca saltaba 60 cm en el cuadro de la suelta (HangClimb)
        for s in "rl":
            free_ks = [k for k in self.keys if "hsp_" + s in k.ctrl and
                       (k.ctrl.get("gw_" + s) or 0.0) + (k.ctrl.get("cw_" + s) or 0.0) < 1.0]
            for k in self.keys:
                if "hsp_" + s not in k.ctrl:
                    continue
                if k in free_ks or not free_ks:
                    k.ctrl["hpp_" + s] = k.ctrl["hsp_" + s]
                else:
                    near = min(free_ks, key=lambda q: (abs(q.frame - k.frame), q.frame < k.frame))
                    k.ctrl["hpp_" + s] = near.ctrl["hsp_" + s]
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
        # dos claves seguidas con la misma posición son un sostén: el Catmull-Rom de nindo_anim igual las curvaba con las
        # vecinas (el bastón clavado se hundía 8 cm entre dos tirones con la flauta quieta en las claves)
        ks = self.keys
        ff = max(0.0, min(float(self.frames), f))
        i = self._seg(ff)
        va, vb = ks[i].ctrl.get(channel), ks[i + 1].ctrl.get(channel)
        if isinstance(va, (tuple, Vector)) and isinstance(vb, (tuple, Vector)) and len(va) == 3 and len(vb) == 3 and \
                max(abs(x - y) for x, y in zip(va, vb)) < 1e-6:
            return V(va)
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
    FORE_MAX = math.radians(TWIST_SHARE_MAX_DEG)
    ELBOW_RATE = 30.0
    GRIP_ELBOW_RATE = 30.0
    HAND_RATE = 35.0
    KNEE_RATE = 30.0         # lo más que gira el plano de la rodilla alrededor del eje cadera-tobillo por cuadro
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
        self.last_s2_q = None
        self.last_s2_rot = None
        self.prev_knee = {}
        self.cand_q, self.fixed_q = {}, {}
        self.tw_log = {"R": {}, "L": {}}

    # agarres del culmo que se prueban: pulgar arriba / abajo y corrimientos del costado pedido (grados); y para todo
    # agarre (flauta o culmo), cuánto gira el codo alrededor del eje hombro-muñeca desde el polo pedido (grados)
    CULM_TRY = [(t, d) for t in (1.0, -1.0) for d in (-50.0, -25.0, 0.0, 25.0, 50.0)]
    SWIVELS = (-45.0, -22.5, 0.0, 22.5, 45.0)

    HISTORY = ("prev_elbow", "prev_elbow_pos", "prev_hand_rel", "prev_fing", "last_staff_z", "last_staff_q", "last_s2_q",
               "last_s2_rot", "prev_knee")

    def snapshot(self):
        """Lo que el solver recuerda del cuadro anterior (los topes de giro, el lado del codo, la flauta): con esto el clip
        que sigue a otro arranca donde terminó el de referencia."""
        cp = lambda v: v.copy() if hasattr(v, "copy") else v
        out = {}
        for k in self.HISTORY:
            v = getattr(self, k)
            out[k] = {kk: cp(vv) for kk, vv in v.items()} if isinstance(v, dict) else cp(v)
        return out

    def restore(self, snap):
        for k, v in snap.items():
            setattr(self, k, {kk: (vv.copy() if hasattr(vv, "copy") else vv) for kk, vv in v.items()} if isinstance(v, dict)
                    else (v.copy() if hasattr(v, "copy") else v))

    def begin(self, mode):
        """'collect' junta lo que le cuesta a la muñeca cada agarre posible en cada cuadro; 'replay' usa el plan."""
        self.mode = mode
        self.prev_elbow, self.cur_elbow = {}, {}
        self.prev_fing = {}
        self.prev_hand_rel = {}
        self.prev_elbow_pos = {}
        self.last_staff_z = None
        self.last_staff_q = None
        self.last_s2_q = None
        self.last_s2_rot = None
        self.prev_knee = {}
        self.tw_log = {"R": {}, "L": {}}
        if mode == "collect":
            self.costs = {"r": {}, "l": {}}
            self.ccosts = {"r": {}, "l": {}}
            self.side_hint = {}
            self.cand_q = {"r": {}, "l": {}}
            self.fixed_q = {"r": {}, "l": {}}

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
        cuesta a la muñeca y lo que cuesta cambiar de un cuadro al otro: el puño no resbala alrededor del caño, el codo no
        salta (cada paso de la grilla cuesta) y el brazo no gira de golpe (arm_step: lo que giran brazo, antebrazo y mano
        entre dos agarres de cuadros seguidos, también contra el cuadro de antes y el de después del agarre), y el meñique
        no cambia de punta en un mismo agarre (sería soltarla: se prueba cada lado entero y se queda el más barato)."""
        self.plan = {"r": {}, "l": {}}
        n = len(self.ROLLS)
        ns = len(self.SWIVELS)
        # transición fija entre estados (codo si, giro ri) -> (sj, rj): cada paso de 15° del puño cuesta (cuadrático) y
        # más de 45° de un cuadro al otro no se puede (con el costo cuadrático solo, a veces le convenía un salto grande en
        # el último cuadro de un loop); el codo pasa a lo sumo al paso vecino de la grilla
        si = np.repeat(np.arange(ns), n)
        ri = np.tile(np.arange(n), ns)
        d = np.abs(((ri[:, None] - ri[None, :] + n // 2) % n) - n // 2)
        dsw = np.abs(si[:, None] - si[None, :])
        T = 0.6 * d * d + 1.5 * dsw + np.where(d > 3, 1e5, 0.0) + np.where(dsw > 1, 1e12, 0.0)
        cols = np.arange(ns * n)
        for s in "rl":
            cs = self.costs.get(s, {})
            cq = self.cand_q.get(s, {})
            fq = self.fixed_q.get(s, {})
            for run in self.runs(frames, cs):
                best = None
                for side in (0, 1):
                    # estado = (codo, giro): índice si * n + ri; el costo del cuadro sale de la grilla de collect
                    sel = [(k * 2 + side) * n + r for k in range(ns) for r in range(n)]

                    def cost_at(fi):
                        row = []
                        # la punta hacia la que va el meñique, si la clave la pide (grip_s_side): el otro lado cuesta
                        want = self.side_hint.get((s, fi))
                        bias = 3.0 if want is not None and want != side else 0.0
                        for k, sw in enumerate(self.SWIVELS):
                            off = (k * 2 + side) * n
                            row += [v + 0.2 * abs(sw) / 22.5 + bias for v in cs[fi][off:off + n]]
                        pin = self.pins.get((s, fi))
                        if pin is not None:
                            # el agarre de la pose de encadenado: cualquier otro cuesta muchísimo
                            pr, ps, psw = pin
                            k = min(range(n), key=lambda i: abs(((self.ROLLS[i] - pr + math.pi) % (2 * math.pi)) - math.pi))
                            ks = min(range(ns), key=lambda i: abs(self.SWIVELS[i] - psw))
                            row = [v + (0.0 if (ps == side and st == ks * n + k) else 1e6) for st, v in enumerate(row)]
                        return np.array(row)

                    def quats(fi):
                        q = cq.get(fi)
                        return q[sel] if q is not None else None

                    acc = cost_at(run[0])
                    qa = quats(run[0])
                    before = fq.get(run[0] - 1)
                    if before is not None and qa is not None:
                        acc = acc + self.arm_step(before[None], qa)[0]
                    back = []
                    for fi in run[1:]:
                        qb = quats(fi)
                        M = acc[:, None] + T
                        if qa is not None and qb is not None:
                            M = M + self.arm_step(qa, qb)
                        bi = np.argmin(M, axis=0)
                        acc = M[bi, cols] + cost_at(fi)
                        back.append(bi)
                        qa = qb
                    after = fq.get(run[-1] + 1)
                    if after is not None and qa is not None:
                        acc = acc + self.arm_step(qa, after[None])[:, 0]
                    j = int(np.argmin(acc))
                    total = float(acc[j])
                    if best is not None and total >= best[0]:
                        continue
                    path = [j]
                    for bi in reversed(back):
                        j = int(bi[j])
                        path.append(j)
                    path.reverse()
                    best = (total, side, path)
                _, side, path = best
                for fi, st in zip(run, path):
                    self.plan[s][fi] = (self.ROLLS[st % n], side, self.SWIVELS[st // n])

    # lo que puede girar un hueso del brazo de un cuadro al otro sin costo (grados) y lo que cuesta pasarse: el lint corta
    # en 45°, a partir de ahí el salto cuesta como empeorar mucho la muñeca
    ARM_FREE_STEP = 25.0

    def arm_step(self, qa, qb):
        """Costo de pasar de cada agarre de qa a cada uno de qb (cuaterniones (N, 3, 4): brazo sobre la clavícula,
        antebrazo sobre el brazo, mano sobre el antebrazo): el hueso que más gira manda."""
        dots = np.abs(np.einsum("akc,bkc->kab", qa, qb))
        ang = np.degrees(2.0 * np.arccos(np.clip(dots, 0.0, 1.0))).max(axis=0)
        ex = np.maximum(0.0, ang - self.ARM_FREE_STEP)
        return 0.01 * ex * ex + np.where(ang > 45.0, 20.0, 0.0)

    def arm_quats(self, pose, S):
        """Brazo, antebrazo y mano de este cuadro, cada uno sobre su padre (para arm_step)."""
        out = []
        for par, b in (("Clav_", "UpperArm_"), ("UpperArm_", "Forearm_"), ("Forearm_", "Hand_")):
            q = rot3(pose.get(par + S)).to_quaternion().inverted() @ rot3(pose.get(b + S)).to_quaternion()
            out.append((q.w, q.x, q.y, q.z))
        return out

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
            # el lado del cuadro anterior en el marco del pecho de ese cuadro (con el de este, el lado quedaba quieto en el
            # mundo mientras el pecho giraba: en la voltereta se apartaba 140° del pedido y volvía de un salto al final)
            P2 = self.last_s2_rot if self.last_s2_rot is not None else rot3(S2)
            tz = P2.inverted() @ self.last_staff_z if self.last_staff_z is not None else None
            M = self.staff_from(g("sts_pos"), g("sts_dir"), g("sts_up", (0, 0, 1)), tz)
            mats.append((S2 @ M, w["spine"]))
        if w["lips"] > 1e-4:
            d = V(g("stl_dir")).normalized()
            mouth = pose.get("Head") @ R.rest_inv["Head"] @ CR.MOUTH
            mats.append((self.staff_from(mouth - d * g("stl_at"), d, g("stl_up", (0, 0, 1))), w["lips"]))
        carriers = [s for s in "rl" if w["h" + s] > 1e-4]
        self.misses = {}
        staff = None
        s2q = rot3(pose.get("Spine2")).to_quaternion()
        turn = s2q.rotation_difference(self.last_s2_q).angle if self.last_s2_q is not None else 0.0
        # lo que giró el pecho cuenta en lo que la flauta va pegada a él (en el mundo o en la boca no la lleva el pecho)
        wsum = sum(w.values())
        turn = min(turn, 2.0 * math.pi - turn) * (w["spine"] / wsum if wsum > 1e-6 else 0.0)
        if mats:
            # con una mano que la lleva, la de los otros modos es provisoria: la mano que pasa de agarrarla a llevarla la
            # agarra ahí (el peso de la mano decide cuánto)
            pv = self.staff_pivot(c)
            staff = self.limit_staff(blend_mats(mats, pv), pv, turn)
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
                pv = self.staff_pivot(c)
                staff = self.limit_staff(blend_mats(mats, pv), pv, turn)
                pose.place("Staff", staff)
        if staff is None:
            # sin modo: queda donde la deja el reposo (no pasa en los clips de pelea)
            pose.get("Staff")
        self.last_staff_z = rot3(pose.get("Staff")).col[2].copy()
        self.last_staff_q = rot3(pose.get("Staff")).to_quaternion()
        self.last_s2_q = s2q
        self.last_s2_rot = rot3(pose.get("Spine2") @ R.rest_inv["Spine2"])
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
            # la rodilla gira alrededor del eje cadera-tobillo a lo sumo KNEE_RATE por cuadro respecto de la cadera, y con el
            # polo pedido casi a lo largo de la pierna se queda del lado anterior: con la pierna casi estirada el plano de la
            # rodilla no está definido y la tibia daba media vuelta en un cuadro (el pie, fijo en el mundo, giraba 180° sobre
            # ella). Se mide en el marco de la cadera: dando una vuelta en el aire la rodilla va con el cuerpo
            Rh = rot3(pose.get("Hips"))
            Rhi = Rh.transposed()
            hipp = pose.head("Thigh_" + S)
            axis = Rhi @ (ank - hipp)
            pk = self.prev_knee.get(S)
            kl = Rhi @ knee
            if pk is not None and axis.length > 1e-6:
                nax = axis.normalized()
                a = pk - nax * pk.dot(nax)
                b = kl - nax * kl.dot(nax)
                if a.length > 1e-4 and b.length < 0.35 * kl.length:
                    wq = b.length / (0.35 * kl.length)
                    kl = (b.normalized() * wq if b.length > 1e-6 else Vector()) + a.normalized() * (1.0 - wq)
                    b = kl - nax * kl.dot(nax)
                if a.length > 1e-4 and b.length > 1e-4:
                    ang = a.angle(b)
                    lim = self.rate_limit(self.KNEE_RATE, ang)
                    if ang > lim:
                        cr = a.cross(b)
                        kl = Quaternion(cr.normalized() if cr.length > 1e-6 else nax, lim) @ a.normalized()
                knee = Rh @ kl
            self.prev_knee[S] = kl.copy()
            self.misses["leg_" + s] = pose.two_bone("Thigh_" + S, "Shin_" + S, ank, knee)
            pose.place("Foot_" + S, compose(pose.tail("Shin_" + S), Rf))
            ax = rot3(R.rest["Toe_" + S]).col[0]
            pose.delta("Toe_" + S, Quaternion(ax, math.radians(g("toe_" + s, 0.0))))
            fv = c.get("_fing_" + s)
            fv = list(fv) if fv is not None else list(shape_vec("relaxed"))
            pv = self.prev_fing.get(s)
            if pv is not None:
                # de un agarre a la mano abierta en un cuadro el dedo giraba 60°: se cierra o se abre a FING_RATE (o lo que
                # falta repartido en los cuadros que quedan: el último cuadro llega a la mano de la pose que sigue)
                rem = max(1, self.nframes - self.frame + 1) if self.nframes else None
                out = []
                for v, p in zip(fv, pv):
                    lim = max(self.FING_RATE, abs(v - p) / rem) if rem else self.FING_RATE
                    out.append(p + max(-lim, min(lim, v - p)))
                fv = out
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

    def rate_limit(self, rate_deg, ang):
        """El tope de giro por cuadro (codo, mano suelta, flauta) en radianes: rate_deg, o lo que falta repartido entre los
        cuadros que quedan si es más (el último cuadro tiene que llegar a la pose con la que encadena aunque el tope la haya
        atrasado; abriéndolo de golpe en los últimos tres cuadros, lo atrasado se ponía al día en un salto de 50°)."""
        lim = math.radians(rate_deg)
        if not self.nframes:
            return lim
        return max(lim, ang / max(1, self.nframes - self.frame + 1))

    @staticmethod
    def staff_pivot(c):
        """El punto de la flauta alrededor del cual se mezclan dos modos (metros desde la punta de abajo): donde la agarra
        la derecha, o la izquierda, o el medio. Mezclando por la punta de abajo el punto agarrado se iba en arco lejos de
        las dos manos."""
        for s in "rl":
            if (c.get("gw_" + s) or 0.0) > 0.01 and c.get("grip_" + s) is not None:
                return c["grip_" + s]
        return CR.STAFF_LEN * 0.5

    def limit_staff(self, M, pivot=0.0, body_turn=0.0):
        """La flauta gira a lo sumo STAFF_RATE por cuadro más lo que giró el pecho (un giro más rápido entre dos claves se
        reparte en los cuadros que siguen), alrededor del punto agarrado; las manos agarran la que queda, así que siguen
        pegadas. Lo que gira el pecho cuenta aparte: en la voltereta la flauta va con el cuerpo a 45° por cuadro y con el
        tope solo quedaba atrás y no llegaba a la guardia del final. Cerca del final el tope se abre (rate_limit)."""
        qp = self.last_staff_q
        if qp is None:
            return M
        q = rot3(M).to_quaternion()
        if q.dot(qp) < 0.0:
            q = -q
        ang = q.rotation_difference(qp).angle
        lim = self.rate_limit(self.STAFF_RATE, ang) + body_turn
        if ang <= lim:
            return M
        R = qp.slerp(q, lim / ang).to_matrix()
        p = M.translation + rot3(M).col[1] * pivot
        return compose(p - R.col[1] * pivot, R)

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
            hs = max(0.0, min(1.0, g("hpp_" + s, g("hsp_" + s, 0.0))))
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
            row, qs = [], []
            for sw in self.SWIVELS:
                for side in (0, 1):
                    for r in self.ROLLS:
                        self.roll_override, self.swivel_override = (r, side), sw
                        pose.place("Clav_" + S, clav)
                        self.place_arm(pose, c, s, staff)
                        row.append(self.wrist_cost(pose, S, self.misses[s]))
                        qs.append(self.arm_quats(pose, S))
            self.roll_override = self.swivel_override = None
            self.costs[s][self.frame] = row
            self.cand_q[s][self.frame] = np.array(qs)
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
        if self.mode == "collect" and self.frame not in self.costs[s]:
            # el brazo de los cuadros sin agarre automático: contra él se mide el salto al entrar y al salir del agarre
            self.fixed_q[s][self.frame] = np.array(self.arm_quats(pose, S))

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
            # el codo de verdad dice de qué lado va solo si el brazo está doblado (un cuarto del brazo fuera del eje): con el
            # brazo casi estirado su corrimiento del eje es ruido, se daba vuelta de lado y el brazo giraba 126° en un cuadro
            for v in (po, pe):
                if v is not None:
                    w_ = v - nax * v.dot(nax)
                    if w_.length > (0.25 if v is po else 0.05) * v.length:
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
                lim = self.rate_limit(lim_deg, ang)
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
        qs = []
        for p, Hr, wt in tg:
            if Hr is None:
                # la muñeca neutra: la relación antebrazo-mano del reposo sobre el antebrazo de este cuadro
                Hr = rot3(pose.get("Forearm_" + S)) @ self.meter.side[S][0]
            qs.append((Hr.to_quaternion(), wt))
        pr = self.prev_hand_rel.get(S)
        if len(qs) > 1 and pr is not None:
            # al soltar o al agarrar (dos giros pedidos con peso) la mezcla se hace alrededor de la mano del cuadro anterior
            # (el promedio de lo que cada giro se aparta de ella): con el slerp entre los dos, cuando el agarre y la mano
            # suelta quedaban casi opuestos el camino corto cambiaba de lado y la mano daba media vuelta en un cuadro
            ref = rot3(pose.get("Forearm_" + S)).to_quaternion() @ pr
            v, tot = Vector(), 0.0
            for qq, wt in qs:
                d = ref.rotation_difference(qq)
                if d.w < 0.0:
                    d = -d
                ax, an = d.to_axis_angle()
                v += ax * (an * wt)
                tot += wt
            v /= tot
            q = ref @ Quaternion(v.normalized(), v.length) if v.length > 1e-9 else ref.copy()
        else:
            for qq, wt in qs:
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
            lim = self.rate_limit(self.HAND_RATE, ang)
            if ang > lim:
                rel = pr.slerp(rel, lim / ang)
                q = Ff @ rel
        self.prev_hand_rel[S] = rel.copy()
        pose.place("Hand_" + S, compose(pose.tail("Forearm_" + S), q.to_matrix()))
        # el antebrazo se lleva parte del giro de la mano sobre su eje (pronación), hasta FORE_MAX. Solo depende de la
        # pose (así el primer y el último cuadro de un clip son iguales a la pose con la que encadena); el giro medido
        # salta de +180° a -180° cuando la mano pasa por media vuelta, y eso lo arregla unwind_forearms con el clip entero
        Wf = pose.get("Forearm_" + S)
        base = (Wf @ self.rig.rel["Hand_" + S]).inverted() @ pose.get("Hand_" + S)
        qb = base.to_quaternion()
        ang = (2.0 * math.atan2(qb.y, qb.w) + math.pi) % (2.0 * math.pi) - math.pi
        self.twist[S] = abs(math.degrees(ang))
        share = max(-self.FORE_MAX, min(self.FORE_MAX, ang * self.TWIST_SHARE))
        if self.mode == "replay":
            self.tw_log[S][self.frame] = (ang, share)
        pose.place("Forearm_" + S, compose(Wf.translation, rot3(Wf) @ Matrix.Rotation(share, 3, 'Y')))


def culm_local(r):
    """Dónde pasa el eje del culmo (radio r) en el espacio de la mano que lo agarra: la palma apoyada en la superficie
    (PALM_LOCAL está en la piel de la palma) y el eje a r más adentro, hacia la palma (-Z)."""
    return Vector((0.0, CR.PALM_LOCAL.y + 0.004, CR.PALM_LOCAL.z - r - 0.010))


def blend_mats(mats, pivot=0.0):
    """Mezcla de matrices de la flauta por peso: el giro con slerp y la posición del punto a 'pivot' metros por su eje Y
    (la punta de abajo con 0)."""
    tot = sum(w for _, w in mats)
    pos = sum(((M.translation + rot3(M).col[1] * pivot) * (w / tot) for M, w in mats), Vector())
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
    R = q.to_matrix()
    return compose(pos - R.col[1] * pivot, R)


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
        out.append(("Root", rig.rest_inv["Root"] @ Vector((0.0, 0.0, z)), r, "culm"))
        z += step
    # el anillo del nudo del posado (más grueso)
    out.append(("Root", rig.rest_inv["Root"] @ Vector((0.0, 0.0, -0.06)), RING_R + 0.01, "culm"))
    return out


# lo que las hojas de la capa y de la falda y los tubos graves sobresalen de la cola de sus huesos hacia el culmo: con la
# esfera del hueso solo, sentado en el posado el ruedo de atrás y el cascabel más bajo quedaban 9 cm adentro de la caña
CULM_PAD_CLOTH = 0.10


# cuánto busca colgar a plomo cada tela según cuánto se aparta su pose rígida de la vertical (HANG_LO .. HANG_HI grados):
# parado la capa, la barba, las mangas y los cascabeles conservan la forma del modelo (las hojas que se abren, los tubos
# que se apartan de las hojas) y solo se mecen; inclinado caen de a poco y cabeza abajo caen enteras hacia el piso
# alrededor de la cabeza (la hoja original)
HANG_LO, HANG_HI, HANG_FULL = 35.0, 110.0, 0.95
CARRY = 0.85                 # lo que la tela se lleva de la traslación de su raíz en cada cuadro (run_springs)
# lo más que un paño de la capa se aparta de su pose (el levante) y lo más que se apartan dos vecinos entre sí (grados): con
# 65° y sin el tope entre vecinos, en los golpes los paños se abrían como alas planas más anchas que el cuerpo
CLOAK_LIFT, CLOAK_PAIR, CLOAK_FLOOR_LIFT = 35.0, 25.0, 65.0


def chain_colliders(first, colliders):
    """Las esferas con las que choca una cadena en el horneado: ninguna con las de la flauta (en un barrido de la flauta
    pasaban a los cascabeles y a la barba de un lado al otro en un cuadro: en el juego las usa SpringChain), las mangas
    no con las de su propio brazo (cuelgan de él: empezaban adentro y temblaban) y el moño y la ramita no con la de la
    cabeza; la barba y las colas de la faja solo con el cuerpo."""
    out = []
    cloth = first.startswith(("Cloak_", "Skirt_", "Acc_ChimesLo"))
    for c in colliders:
        b = c[0]
        if len(c) > 3:
            # las del culmo: más gruesas para la tela de hojas
            out.append((c[0], c[1], c[2] + (CULM_PAD_CLOTH if cloth else 0.0)))
            continue
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


def springs(rig, colliders, floor, cloak_hang=None, hang_scale=1.0, cloak_max=None, cloak_free=False):
    """Los resortes de chikuo_rig.chains() con el colgar que depende de la inclinación (HANG_LO/HI); el moño va rígido
    (pelo duro atado). cloak_hang fija otro máximo para la capa y hang_scale escala el colgar de todas (0 dando vueltas);
    cloak_max, el giro máximo de la capa desde su pose rígida (colgado cabeza abajo: con los 65° de siempre la capa quedaba
    trabada en horizontal como una bandeja alrededor de la cabeza, en vez de caer hacia el piso como en el concepto);
    cloak_free, cada paño cuelga por su cuenta (colgado cabeza abajo: con el giro común los tramos del yugo, que salen de
    costado, giraban sobre su propio eje y quedaban en horizontal; partida la cáscara, cada paño cae hacia el piso).
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
                                ("Sleeve_", 200.0, 0.45, 35.0), ("Cloak_", 90.0, 0.30, CLOAK_LIFT), ("Skirt_", 160.0, 0.30, 60.0)):
            if b0.startswith(pre):
                k, damp, mx = kk, dd, mm
        if cloak_max is not None and b0.startswith("Cloak_"):
            mx = cloak_max
        sp = NA.Spring(bones, k=k, damp=damp, grav=3.0, max_deg=mx, hang=hang, floor=floor, colliders=colliders_b)
        # lo más que cuelga de su pose rígida: las mangas son tela pegada al brazo (no se dan vuelta), la barba y la
        # ramita están atadas a la cara; la capa, la falda y los cascabeles cuelgan enteros
        sp.hang_max = 40.0 if b0.startswith("Sleeve_") else 30.0 if b0.startswith("Acc_LeafKnot") else             100.0 if b0.startswith("Acc_TasselBeard") else 180.0
        sp.sag_ref = ("Spine2" if not cloak_free else None) if b0.startswith("Cloak_") else "Hips" if b0.startswith("Skirt_") else None
        # las hojas de la capa cuelgan debajo de la cola de cada tramo (medido en la malla: 0.10 el de arriba, 0.16 el
        # del medio, 0.27 el último) y los paños de adelante de la falda 0.22: el piso se le pide a la punta de la hoja,
        # no a la cola (en guardia la capa de atrás se metía 7 cm en el piso con las colas a 20 cm)
        sp.drop = {b: cloak_drop(b) for b in bones}
        out.append(sp)
    return out


def clamp_cloak(rig, frames, prim, max_rel=CLOAK_PAIR):
    """Dos paños vecinos de la capa no se apartan de su pose rígida más de max_rel grados uno del otro (cada uno se acerca
    a la mitad, girando sobre su raíz con lo que cuelga de él): sueltos, en los golpes y los saltos un paño se abría como un
    ala y el de al lado quedaba pegado, y el borde entre los dos se veía como una lámina."""
    lim = math.radians(max_rel)
    angs = CR.CLOAK_ANGLES
    for W, P in zip(frames, prim):
        for seg in (1, 2, 3):
            for a, b in zip(angs, angs[1:]):
                na, nb = CR.cloak_name(a, seg), CR.cloak_name(b, seg)
                if na not in W or nb not in W:
                    continue
                qa = (rot3(W[na]) @ rot3(P[na]).transposed()).to_quaternion()
                qb = (rot3(W[nb]) @ rot3(P[nb]).transposed()).to_quaternion()
                if qa.dot(qb) < 0.0:
                    qb = -qb
                d = qa.rotation_difference(qb).angle
                if d <= lim:
                    continue
                mid = qa.slerp(qb, 0.5)
                for n, q in ((na, qa), (nb, qb)):
                    corr = (q.slerp(mid, 1.0 - lim / d) @ q.inverted()).to_matrix().to_4x4()
                    h = W[n].translation.copy()
                    M = Matrix.Translation(h) @ corr @ Matrix.Translation(-h)
                    for c in rig.subtree(n):
                        W[c] = M @ W[c]


def cloak_drop(b):
    """Lo que la malla de un hueso de tela baja debajo de su cola (m): las hojas de la capa y el ruedo de la falda."""
    if b.startswith("Cloak_"):
        seg, n = int(b[-1]), CR.cloak_segs(float(b.split("_")[1]))
        return 0.27 if seg == n else 0.16 if seg > 1 else 0.10
    if b in ("Skirt_040", "Skirt_320"):
        return 0.22
    if b in ("Skirt_140", "Skirt_220"):
        # los paños de atrás son anchos: sentado o tirado el borde de abajo queda debajo de la cola
        return 0.10
    return 0.0


DEV_RATE = 32.0              # lo más que la tela cambia su apartamiento de la pose por cuadro (grados)
TWIST_KEEP = (100.0, 150.0)  # desde qué apartamiento la tela conserva el giro sobre su eje del cuadro anterior (grados)


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
            bdir = (x - h).normalized()
            q = rigid.rotation_difference(bdir)
            qp = st[4] if len(st) > 4 else None
            if qp is not None:
                # el giro más corto de la pose a la simulada no dice nada del giro del hueso sobre su eje cuando las dos
                # direcciones son casi opuestas (la capa que cuelga con el cuerpo cabeza abajo, el paño doblado contra el
                # piso): el eje saltaba y el paño daba media vuelta sobre sí mismo en un cuadro. Ahí se queda con el giro
                # sobre su eje más parecido al del cuadro anterior (con los dos apartamientos chicos manda el más corto)
                wk = max(0.0, min(1.0, (math.degrees(q.angle) - TWIST_KEEP[0]) / (TWIST_KEEP[1] - TWIST_KEEP[0])))
                if wk > 0.0:
                    r = qp @ q.inverted()
                    if r.w < 0.0:
                        r = -r
                    tw = 2.0 * math.atan2(Vector((r.x, r.y, r.z)).dot(bdir), r.w)
                    q = Quaternion(bdir, tw * wk) @ q
                # la tela no se aparta de su pose más de DEV_RATE por cuadro: en un golpe de cadera la capa o un cascabel
                # pasaban de un tope al opuesto en un cuadro (130-180°)
                if q.dot(qp) < 0.0:
                    q = -q
                ang = q.rotation_difference(qp).angle
                lim = math.radians(DEV_RATE)
                if ang > lim:
                    q = qp.slerp(q, lim / ang)
                    x = h + (q @ rigid) * L
                    if fl is not None and x.z < fl:
                        # el piso sigue mandando (el tope de cada cuadro no la mete debajo)
                        x.z = fl
                        dirn = x - h
                        if dirn.length > 1e-6:
                            x = h + dirn.normalized() * L
                        q = rigid.rotation_difference((x - h).normalized())
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
    su clip de referencia): así el fundido del código no ve la mano girar sobre el caño. pin_from trae además lo que el
    solver recordaba en ese cuadro del de referencia ("state"): el clip arranca con el codo del mismo lado (sin eso, el
    codo de un brazo casi estirado podía elegir el otro lado en el primer cuadro y el empalme se iba 160°)."""
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
        if pin_from and pin_from.get("state"):
            solver.restore(pin_from["state"])
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
    if pin_from and pin_from.get("state"):
        solver.restore(pin_from["state"])
    misses = []
    frames, ctrls, roots = [], [], []
    states = {}
    for f in range(clip.frames + 1):
        c = ctl[f]
        solver.frame = f
        pose = NA.Pose(rig)
        misses.append(dict(solver.solve(pose, c)))
        if f in (0, clip.frames):
            states[f] = solver.snapshot()
        for n in rig.names:
            pose.get(n)
        frames.append(pose.W)
        ctrls.append(c)
        roots.append(Vector((0.0, -(c.get("travel") or 0.0), 0.0)) + clip.root_vel * (f / FPS))
    unwind_forearms(rig, frames, solver.tw_log, clip.cuts)
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
    prim = [dict(W) for W in frames]
    free_cloak = bool(t.get("cloak_free"))

    def bake_cloth(cloak_max):
        out = [dict(W) for W in prim]
        run_springs(rig, out, springs(rig, cols, floor, t.get("cloak_hang"), t.get("hang_scale", 1.0), cloak_max, free_cloak), soff,
                    loop=clip.loop, preroll=t.get("preroll", 1.0), floor_offsets=lifts,
                    carry=t.get("carry", 0.6 if space == "ground" else CARRY))
        return out
    frames[:] = bake_cloth(t.get("cloak_max"))
    if not free_cloak:
        # sentado, tirado o caído la capa se apoya en el piso (el piso la aparta de su pose más que el levante): ahí vale el
        # tope de siempre y no el de los vecinos, que la metía en el piso o la hacía saltar al soltarla
        if floor is not None and any((W[b] @ Vector((0.0, rig.length[b], 0.0))).z - cloak_drop(b) < floor + lifts[i] + 0.03
                                     for i, W in enumerate(frames) for b in CR.cloak_bones()):
            frames[:] = bake_cloth(t.get("cloak_max") or CLOAK_FLOOR_LIFT)
        else:
            clamp_cloak(rig, frames, prim)
    if clip.loop:
        frames[-1] = {n: m.copy() for n, m in frames[0].items()}
    clip.grips = {"first": dict(grips_at(solver, 0), state=states[0]),
                  "last": dict(grips_at(solver, clip.frames), state=states[clip.frames])}
    return frames, ctrls, roots, misses


ARM_RATE = 40.0                # lo más que gira un hueso del brazo suelto por cuadro después del alisado (grados)


UNWIND_RATE = 20.0          # grados por cuadro que gira el antebrazo sobre su eje al volver a la vuelta de la pose


def unwind_forearms(rig, frames, log, cuts=()):
    """El giro del antebrazo sobre su eje con el clip entero a la vista. Cuadro a cuadro (place_arm) el giro de la mano se
    mide entre -180° y 180°: cuando la mano pasa por media vuelta (un agarre que gira el puño, la flauta que da vueltas)
    la medida salta de un extremo al otro y el antebrazo daba esa vuelta en un cuadro. Acá el giro sigue de corrido (sin
    saltos: se suma la vuelta entera que haga falta) y el antebrazo se lleva su parte; si al final del clip quedó en otra
    vuelta que la pose con la que encadena, vuelve a ella de a UNWIND_RATE en los últimos cuadros (lo que se ve es la manga
    que gira sobre el antebrazo, no la mano: la mano queda donde está, agarrando)."""
    n = len(frames)
    lim = math.radians(TWIST_SHARE_MAX_DEG)
    for S in "RL":
        L = log.get(S) or {}
        if len(L) != n:
            continue
        ang = [L[f][0] for f in range(n)]
        share = [L[f][1] for f in range(n)]
        u = [ang[0]]
        for f in range(1, n):
            if f in cuts:
                u.append(ang[f])
                continue
            d = (ang[f] - u[-1] + math.pi) % (2.0 * math.pi) - math.pi
            u.append(u[-1] + d)
        want = [max(-lim, min(lim, x * Solver.TWIST_SHARE)) for x in u]
        off = want[-1] - share[-1]
        if abs(off) > 1e-4:
            k = min(n - 1, max(4, int(math.ceil(math.degrees(abs(off)) / UNWIND_RATE))))
            for i in range(1, k + 1):
                f = n - 1 - k + i
                t = i / k
                want[f] -= off * t * t * (3.0 - 2.0 * t)
        fa = "Forearm_" + S
        carried = [c for c in rig.subtree(fa) if c != fa and c not in rig.subtree("Hand_" + S)]
        for f in range(n):
            delta = want[f] - share[f]
            if abs(delta) < 1e-5:
                continue
            W = frames[f]
            old = W[fa]
            new = compose(old.translation, rot3(old) @ Matrix.Rotation(delta, 3, 'Y'))
            rel = old.inverted()
            for c in carried:
                W[c] = new @ (rel @ W[c])
            W[fa] = new


def smooth_free_arms(rig, frames, ctrls, cuts=()):
    """Alisa los brazos de las manos sueltas (sin agarre: nada que despegar) donde un hueso del brazo gira más de
    ARM_RATE en un cuadro: el IK de un brazo plegado (el yugo, una mano que pasa cerca del hombro) da vuelta el codo con un
    corrimiento chico de la muñeca. Los cuadros sueltos se acercan al promedio de sus vecinos hasta que el giro entra (los
    agarrados quedan fijos y hacen de ancla); después se rearma la mano con sus dedos sobre el brazo alisado."""
    n = len(frames)
    for S in "RL":
        s = S.lower()
        chain = ["UpperArm_" + S, "Forearm_" + S, "Hand_" + S]
        # el primero y el último quedan fijos: son las poses con las que encadena
        free = [1.0 - min(1.0, (c.get("gw_" + s) or 0.0) + (c.get("cw_" + s) or 0.0)) >= 0.5 and f not in cuts
                and 0 < f < n - 1 for f, c in enumerate(ctrls)]
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
