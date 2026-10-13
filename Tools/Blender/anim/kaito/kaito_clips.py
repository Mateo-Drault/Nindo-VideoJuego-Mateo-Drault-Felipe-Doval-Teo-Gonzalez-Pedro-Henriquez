"""Clips de Kaito: poses clave, curvas y tiempos. Fuente única de los tiempos del FBX (kaitooo.fbx.json).

Espacio C (ver kaito_rig): unidades del archivo (1 u = 0.53 m), frente -Y, su derecha -X, piso z 0.
Giros en grados: x + = adelante, y + = hacia su izquierda, z + = gira a su izquierda (visto desde arriba).
Los pies van en el MUNDO del clip (antes de restar 'travel', el avance que el juego aplica al transform);
la cadera, las manos y la katana van relativas al transform del juego.

Gramática de los golpes de Kaito (es el jugador: el arranque tiene que ser inmediato, pero con peso):
  anticipación corta (2-3 cuadros: la cadera y el hombro se cargan hacia atrás, la hoja sale de la
  silueta) -> golpe de 1-2 cuadros por un arco limpio, el pie de adelante apoya en el impacto -> se pasa
  (follow-through) -> pose de encadenado. La cadera va un cuadro adelante de la hoja, la cabeza uno atrás.
Las poses de encadenado comparten el final de un clip y el principio del siguiente (A1_END = principio
del Corte 2, A2_END = principio del Corte final): el crossfade de 0.03 s del combo nunca salta de pose.

'timing' (cuadros a 30 fps; va al .fbx.json y de ahí salen los números de PlayerConfig):
  apex        carga máxima de la anticipación
  contact     primer cuadro que pega (AttackDef.activeStart = contact / frames)
  active      [a, b] ventana que pega (activeStart, activeEnd)
  combo       desde acá se puede encadenar (comboWindow)
  lunge       [a, b, metros] avance que el JUEGO aplica al transform, lineal (lungeStart, lungeEnd, lunge)
  strike      cuadro del tajo del remate (PlayerController.FinisherStrikeFrame)
  hold        [a, b] pose final quieta (zanshin del remate y de las habilidades: el plano de cámara la sostiene)
  phases      tramos con nombre que el código espera en segundos (habilidades)
"""
import copy, math
from mathutils import Vector
import nindo_anim as NA
from nindo_anim import Key, Clip
import kaito_rig as KR
import kaito_gait as G

U = KR.U_PER_M          # metros -> unidades
CLIPS = []
LEAD = {"hips": -0.6, "hips_rot": -0.6, "spine": -0.3, "head": 1.0, "hand_l": 0.6}


def mod(base, **kw):
    p = copy.deepcopy(base)
    p.update(kw)
    return p


class Planted(tuple):
    """(tobillo, giro) de un pie APOYADO que además recuerda su huella en el mundo (lado, x, y, pivote). Entre
    dos claves con la misma huella KClip recalcula el tobillo desde la huella y el cabeceo interpolado: el
    borde que apoya (punta, bola o talón) queda clavado. Interpolando el tobillo en línea recta, un talón que
    se levanta sobre la punta corría la punta 3-15 cm."""

    def __new__(cls, side, x, y, pitch=0.0, yaw=0.0, pivot="flat"):
        t = super().__new__(cls, KR.foot_on(side, x, y, pitch, yaw, pivot))
        t.print = (side, x, y, pivot)
        return t


def feet(p, r=None, l=None):
    """r / l = (tobillo, giro) de un pie: Planted (flat / toe / plant) o en el aire (air / fa)."""
    q = mod(p)
    for s, v in (("r", r), ("l", l)):
        if v is None:
            continue
        q["foot_" + s], q["foot_" + s + "_rot"] = v
        if isinstance(v, Planted):
            q["_print_" + s] = v.print
        else:
            q.pop("_print_" + s, None)
    return q


def plant(side, x, y, pitch=0.0, yaw=0.0, pivot="flat"):
    return Planted(side, x, y, pitch, yaw, pivot)


def flat(side, x, y, yaw=0.0):
    return Planted(side, x, y, 0.0, yaw)


def toe(side, x, y, yaw=0.0, heel=30.0):
    return Planted(side, x, y, heel, yaw, "toe")


def air(x, y, z, pitch=0.0, yaw=0.0):
    """Pie en el aire: tobillo (x, y, z) con su giro."""
    return (x, y, z), (pitch, 0.0, yaw)


def hover(side, x, y, yaw=0.0, dz=0.05, pitch=0.0):
    """Pie en el aire JUSTO arriba de su huella: la clave anterior a apoyar. Sin ella el tobillo iba en línea recta
    desde el vuelo y la suela llegaba al piso todavía corriéndose (entraba patinando)."""
    return air(x, y, KR.ankle_rest(side).z + dz, pitch, yaw)


def lifted(side, x, y, clear=0.06, pitch=0.0, yaw=0.0):
    """Pie en el aire con la esquina más baja de la suela a 'clear' (u) del piso: un paso que se levanta de verdad
    (con un 'air' a mano, un pie con la punta abajo seguía rozando y se arrastraba mientras el cuerpo cambiaba)."""
    R = KR.foot_rot(pitch, 0.0, yaw)
    A = KR.ankle_rest(side)
    low = min((R @ (P - A)).z for P in KR.sole_corners(side))
    return air(x, y, clear - low, pitch, yaw)


def swung(side, x, y, z, rot, clear=0.04):
    """Pie en el aire con cualquier giro (cabeceo, vuelta, giro: el pie que da la vuelta por el costado al arrodillarse):
    el tobillo en (x, y, z) o más alto, lo justo para que ninguna esquina de la suela quede a menos de 'clear' (u) del
    piso. Rozando, el lint lo ve patinar (la suela se arrastra mientras el pie viaja)."""
    R = KR.foot_rot(*rot)
    A = KR.ankle_rest(side)
    low = min((R @ (P - A)).z for P in KR.sole_corners(side))
    return (x, y, max(z, clear - low)), tuple(rot)


def ankle_of(planted):
    """Tobillo (x, y, z) de un pie apoyado (para levantarlo desde donde está)."""
    return tuple(planted[0])


def inter(a, b, u):
    """Pose a la fracción u entre dos poses (para una clave de paso: después se le cambian los pies con feet()).
    Una clave con canales sueltos no sirve: los que faltan se quedarían quietos en todo el tramo."""
    pa = {k: v for k, v in a.items() if not k.startswith("_print_")}
    pb = {k: v for k, v in b.items() if not k.startswith("_print_")}
    tmp = Clip("_", 1, [Key(0, pa, "lin"), Key(1, pb, "lin")])
    out = {ch: tmp.sample(u, ch) for ch in set(pa) | set(pb)}
    return {k: (tuple(v) if isinstance(v, Vector) else v) for k, v in out.items()}


def at_travel(p, travel):
    """La misma pose cuando el cuerpo ya avanzó 'travel' (u): solo se corre lo clavado en el mundo."""
    q = copy.deepcopy(p)
    for s_ in ("r", "l"):
        x, y, z = q["foot_" + s_]
        q["foot_" + s_] = (x, y - travel, z)
        if "_print_" + s_ in q:
            side, px, py, piv = q["_print_" + s_]
            q["_print_" + s_] = (side, px, py - travel, piv)
    q["travel"] = travel
    return q


def perp(b, hint):
    """Filo perpendicular a la hoja 'b', lo más parecido a 'hint' (el filo autorado solo desempata en kaito_rig)."""
    B, H = Vector(b).normalized(), Vector(hint)
    e = H - B * H.dot(B)
    return tuple(round(x, 3) for x in e.normalized())


def lunge_travel(frames, f0, f1, meters):
    """Avance (u) en cada cuadro con la ley del juego (PlayerController.TickAttack: velocidad constante entre
    lungeStart y lungeEnd)."""
    L = meters * U
    return [0.0 if f <= f0 else L if f >= f1 else L * (f - f0) / (f1 - f0) for f in range(frames + 1)]


class KClip(Clip):
    """Clip con los adelantos/atrasos ('lag') que se apagan en los 3 primeros y 3 últimos cuadros de un clip suelto:
    así el primer y el último cuadro son EXACTAMENTE las poses clave y los clips encadenados (A1_END -> Corte 2,
    GUARD -> desvío) empalman sin salto. Con el lag completo, una cadera que adelanta 0.6 cuadros arrancaba el
    clip ya metida en el primer tramo."""

    def controls(self, f):
        if self.loop:
            return self.step_arc(f, self.pivot_feet(f, super().controls(f)))
        k = max(0.0, min(1.0, f / 3.0, (self.frames - f) / 3.0))
        # timing 'cut': un corte (el teletransporte del remate) entre dos cuadros. A los dos lados el lag se apaga:
        # con la cadera adelantada, el cuadro anterior ya traía la cadera del otro lado y las piernas no llegaban
        for c in self.timing.get("cut", ()):
            k = min(k, max(0.0, abs(f - c) - 0.5) / 1.5)
        keep = self.lag
        self.lag = {c: v * k for c, v in keep.items()}
        try:
            return self.step_arc(f, self.pivot_feet(f, super().controls(f)))
        finally:
            self.lag = keep

    def step_arc(self, f, c):
        """Un pie que despega (clave apoyada -> clave en el aire) primero SUBE y después va; uno que aterriza
        (aire -> apoyado) llega arriba de su huella y después BAJA. En línea recta la suela se corría rozando el piso
        el primer cuadro del despegue y el último de la llegada (1-5 cm por cuadro)."""
        ks = self.keys
        ff = max(0.0, min(float(self.frames), f))
        i = self._seg(ff)
        a, b = ks[i], ks[i + 1]
        u = (ff - a.frame) / max(1e-6, b.frame - a.frame)
        for s_ in ("r", "l"):
            ch = "foot_" + s_
            pa, pb = s_ in a.prints, s_ in b.prints
            if pa == pb or ch not in a.ctrl or ch not in b.ctrl:
                continue
            e = NA.ease(b.ease_ch.get(ch, b.ease), u)
            up, along = (1.0 - (1.0 - e) ** 2, e * e) if pa else (e * e, 1.0 - (1.0 - e) ** 2)
            A, B = Vector(a.ctrl[ch]), Vector(b.ctrl[ch])
            c[ch] = (A.x + (B.x - A.x) * along, A.y + (B.y - A.y) * along, A.z + (B.z - A.z) * up)
        return c

    def pivot_feet(self, f, c):
        """Un pie con la misma huella en las dos claves del tramo gira sobre su borde (ver Planted): el tobillo
        sale de la huella y del cabeceo interpolado, que no cruza el cero (sobre la punta no se levanta la
        punta: el Catmull-Rom del giro se pasaba unos grados y el borde se despegaba)."""
        ks = self.keys
        ff = max(0.0, min(float(self.frames), f))
        i = self._seg(ff)
        a, b = ks[i], ks[i + 1]
        for s_ in ("r", "l"):
            pa, pb = a.prints.get(s_), b.prints.get(s_)
            if not pa or not pb or abs(pa[1] - pb[1]) > 1e-4 or abs(pa[2] - pb[2]) > 1e-4:
                continue
            pivs = {pa[3], pb[3]} - {"flat"}
            if len(pivs) > 1:
                continue
            piv = pivs.pop() if pivs else "flat"
            pitch, roll, yaw = c["foot_" + s_ + "_rot"]
            pitch = max(0.0, pitch) if piv in ("toe", "ball") else min(0.0, pitch) if piv == "heel" else pitch
            ank, rot = KR.foot_on(pa[0], pa[1], pa[2], pitch, yaw, piv, roll)
            c["foot_" + s_], c["foot_" + s_ + "_rot"] = ank, rot
        return c


def add(name, frames, keys, loop=False, lag=None, timing=None, events=None, notes="", travel=None):
    """keys: (cuadro, pose, curva[, {canal: curva, 'stop': (canales,)}]). travel: avance del juego por cuadro
    (lunge_travel): se escribe en cada clave y se interpola lineal (es una recta en el juego)."""
    def key(k):
        ch = dict(k[3]) if len(k) > 3 else {}
        stops = ch.pop("stop", ())
        p = copy.deepcopy(k[1])
        prints = {s_: p.pop("_print_" + s_) for s_ in ("r", "l") if "_print_" + s_ in p}
        if travel is not None:
            p["travel"] = travel[k[0]]
            ch.setdefault("travel", "lin")
        out = Key(k[0], p, k[2], ch, stops)
        out.prints = prints
        return out
    ks = [key(k) for k in keys]
    if travel is not None:
        # una clave de avance en cada quiebre de la recta (si no, el tramo entre dos claves lo curvaría)
        have = {k.frame for k in ks}
        for f in range(1, frames):
            if f not in have and (travel[f] - travel[f - 1]) != (travel[f + 1] - travel[f]):
                prev = max((k for k in ks if k.frame < f), key=lambda k: k.frame)
                nxt = min((k for k in ks if k.frame > f), key=lambda k: k.frame)
                ks.append(_travel_key(f, travel[f], prev, nxt))
        ks.sort(key=lambda k: k.frame)
    c = KClip(name, frames, ks, loop=loop, lag=LEAD if lag is None else lag, timing=timing or {}, events=events, notes=notes)
    CLIPS.append(c)
    return c


def _travel_key(f, tv, prev, nxt):
    """Clave intermedia que solo fija el avance: el resto de los canales se completa interpolando prev -> nxt
    en ese cuadro (así la clave no cambia la pose)."""
    tmp = Clip("_", nxt.frame - prev.frame, [Key(0, prev.ctrl, "lin"), Key(nxt.frame - prev.frame, nxt.ctrl, nxt.ease, nxt.ease_ch)])
    ctrl = {ch: tmp.sample(f - prev.frame, ch) for ch in set(prev.ctrl) | set(nxt.ctrl)}
    ctrl = {k: (tuple(v) if isinstance(v, Vector) else v) for k, v in ctrl.items()}
    ctrl["travel"] = tv
    out = Key(f, ctrl, "lin", dict(nxt.ease_ch, travel="lin"))
    # la clave intermedia conserva las huellas que comparten sus vecinas (el pie sigue clavado)
    out.prints = {s_: v for s_, v in prev.prints.items() if nxt.prints.get(s_) == v}
    return out


# =========================================================================== poses base
R_FOOT = (-0.22, -0.14, 6.0)          # huella del pie derecho (adelante) en guardia: x, y, giro
L_FOOT = (0.30, 0.22, 34.0)           # el izquierdo atrás y abierto

READY = feet({
    "hips": (0.0, 0.02, -0.07), "hips_rot": (3.0, 0.0, 14.0), "spine": (7.0, 0.0, -9.0), "head": (-7.0, 0.0, -4.0),
    "clav_r": (0.0, 0.0, 0.0), "clav_l": (0.0, 0.0, 0.0),
    # katana baja a su derecha, la punta adelante y afuera apenas levantada: desde arriba es una línea larga
    # que sale de la silueta hacia el enemigo; el filo mira abajo-adelante
    "grip": (-0.56, -0.3, 1.0), "blade": (-0.5, -0.8, 0.3), "edge": (0.05, -0.38, -0.92), "elbow_r": (-0.7, 0.5, -0.5),
    "hand_l": (0.36, -0.34, 1.18), "hand_l_dir": (-0.3, -0.75, -0.4), "hand_l_up": (0.8, 0.0, 0.6), "elbow_l": (0.7, 0.4, -0.6),
    "fingers_l": 0.55, "grip_l": 0.0,
    "knee_r": (-0.25, -1.0, 0.0), "knee_l": (0.55, -1.0, 0.0),
    # escalares explícitos en la pose base: una clave sin el canal tomaría el valor de su vecina
    "lift": 0.0, "breath": 0.0, "tremble": 0.0, "arm_space": 0.0, "arm_space_l": 0.0,
    "kat_free": 0.0, "fingers_r": -1.0, "wrist_l_open": 0.0, "wrist_r_open": 0.0, "turn": 0.0, "shift": (0.0, 0.0, 0.0),
    "hand_l_relax": 0.0, "knee_guide_r": 0.0, "knee_guide_l": 0.0,
}, r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))


# =========================================================================== guardia que respira
_breath = mod(READY, breath=1.0, hips=(0.012, 0.025, -0.085), grip=(-0.565, -0.305, 1.02), blade=(-0.51, -0.79, 0.32),
              hand_l=(0.365, -0.335, 1.21), head=(-9.0, 0.0, -3.0))
_shift = mod(READY, hips=(-0.03, 0.02, -0.08), hips_rot=(3.0, 0.0, 12.0), spine=(7.0, -1.5, -8.0), head=(-6.0, 1.5, -6.0),
             grip=(-0.55, -0.31, 0.98), blade=(-0.49, -0.81, 0.29))
add("Idle", 72, [(0, READY, "sine"), (24, _breath, "sine"), (44, _shift, "sine"), (60, mod(_breath, breath=0.5), "sine"),
                 (72, READY, "sine")], loop=True, lag={"head": 3.0, "grip": 2.0, "hand_l": 3.0, "spine": 1.0},
    notes="guardia de una mano: katana baja adelante, respiración y un cambio de peso por vuelta (2.4 s)")


# =========================================================================== locomoción
# LA KATANA EN LOS CICLOS: baja adelante y afuera, como una guardia relajada (la punta adelante de su pie derecho y
# un poco abajo). Con el agarre de la katana (la hoja sale del lado del pulgar) un brazo que cuelga suelto la deja
# apuntando adelante; para llevarla atrás como una cola hacía falta girar el antebrazo y el hombro hasta el tope
# (la muñeca quedaba quebrada 30-50° en todo el ciclo, el pedido de "muñecas dobladas"). Así la mano sigue al
# antebrazo y la caminata empalma con la guardia del Idle (el mismo brazo). En la carrera se abre más hacia afuera
# (desde arriba es una raya en diagonal que sale de la silueta) y se mece con el brazo
def body_walk(ph):
    """Paso corto y ligero (chibi): la katana baja adelante a su derecha, se mece apenas con el brazo."""
    s2 = math.cos(G.TAU * (2.0 * ph - 0.62))
    yaw = -6.0 * math.cos(G.TAU * (ph + 0.02))
    a = G.TAU * (ph - 0.5 - 0.06)
    sw = math.cos(G.TAU * (ph - 0.06))
    return {
        "hips": (0.03 * math.cos(G.TAU * (ph - 0.25)), 0.03, -0.035 + 0.025 * s2), "hips_rot": (3.0, 2.5 * math.cos(G.TAU * (ph - 0.25)), yaw),
        "spine": (4.0, -1.5 * math.cos(G.TAU * (ph - 0.25)), -yaw * 1.2), "head": (-4.0, 1.0 * math.cos(G.TAU * (ph - 0.3)), yaw * 0.3),
        "grip": (-0.55 + 0.01 * sw, -0.2 + 0.08 * sw, 0.92 + 0.02 * abs(sw)), "blade": (-0.45 - 0.03 * sw, -0.85 + 0.06 * sw, -0.12),
        "edge": (0.2, -0.1, -0.97), "elbow_r": (-0.7, 0.6, -0.3),
        "hand_l": (0.43, -0.02 - 0.2 * math.cos(a), 1.0 + 0.06 * math.cos(a)), "hand_l_dir": (0.15, -0.35 * math.cos(a), -0.95),
        "hand_l_up": (1.0, 0.0, 0.0), "elbow_l": (0.6, 0.8, -0.2), "fingers_l": 0.45,
        "knee_r": (-0.12, -1.0, 0.0), "knee_l": (0.12, -1.0, 0.0),
    }


def body_jog(ph):
    s2 = math.cos(G.TAU * (2.0 * ph - 2.0 * 0.12))
    yaw = -8.0 * math.cos(G.TAU * (ph + 0.03))
    a = G.TAU * (ph - 0.5 - 0.05)
    sw = math.cos(G.TAU * (ph - 0.05))
    return {
        "hips": (0.015 * math.sin(G.TAU * ph), 0.03, -0.05 + 0.04 * s2), "hips_rot": (6.0, 2.5 * math.cos(G.TAU * 2 * (ph - 0.12)), yaw),
        "spine": (6.0, 0.0, -yaw * 1.3), "head": (-4.0, 0.0, yaw * 0.35),
        "grip": (-0.57 - 0.02 * sw, -0.14 + 0.1 * sw, 0.92 + 0.04 * sw), "blade": (-0.62 - 0.04 * sw, -0.72 + 0.1 * sw, -0.2),
        "edge": (0.2, -0.1, -0.97), "elbow_r": (-0.7, 0.5, -0.5),
        "hand_l": (0.34 - 0.03 * math.cos(a), 0.02 - 0.2 * math.cos(a), 1.12 + 0.07 * math.cos(a)),
        "hand_l_dir": (0.0, -0.4 * math.cos(a) - 0.2, -0.9), "hand_l_up": (1.0, 0.0, 0.0), "elbow_l": (0.5, 0.9, -0.3), "fingers_l": 0.8,
        "knee_r": (-0.1, -1.0, 0.05), "knee_l": (0.1, -1.0, 0.05),
    }


def body_run(ph):
    """Carrera: cadera que se hunde en cada apoyo, todo el cuerpo inclinado (ProceduralMotion le suma 9°) y
    contragiro; la katana baja y abierta a su derecha, la punta adelante y afuera, mecida por el brazo."""
    s2 = math.cos(G.TAU * (2.0 * ph - 2.0 * 0.0833))      # mínimo a mitad de cada apoyo (2 cuadros de 12)
    yaw = -10.0 * math.cos(G.TAU * (ph + 0.04))
    lean = 10.0 + 2.5 * math.cos(G.TAU * (2.0 * ph - 0.3))
    a = G.TAU * (ph - 0.5 - 0.04)                          # el brazo izquierdo va contra la pierna izquierda
    hand_l = (0.33 - 0.03 * math.cos(a), 0.04 - 0.25 * math.cos(a), 1.14 + 0.1 * math.cos(a) + 0.04 * math.sin(a))
    swing_r = math.cos(G.TAU * (ph - 0.04))
    return {
        "hips": (0.012 * math.sin(G.TAU * ph), 0.06, -0.07 + 0.07 * s2), "hips_rot": (lean, 3.0 * math.cos(G.TAU * 2 * (ph - 0.1)), yaw),
        "spine": (8.0, 0.0, -yaw * 1.4), "head": (-(lean + 8.0) * 0.3 + 2.0 * math.cos(G.TAU * 2 * (ph - 0.3)), 0.0, yaw * 0.35),
        "grip": (-0.58 - 0.03 * swing_r, -0.1 + 0.12 * swing_r, 0.93 + 0.04 * swing_r),
        "blade": (-0.75 - 0.03 * swing_r, -0.6 + 0.12 * swing_r, -0.25), "edge": (0.2, -0.1, -0.97), "elbow_r": (-0.7, 0.4, -0.6),
        "hand_l": hand_l, "hand_l_dir": (0.0, -0.45 * math.cos(a) - 0.2, -0.9), "hand_l_up": (1.0, 0.0, 0.0),
        "elbow_l": (0.5, 0.9, -0.3), "fingers_l": 0.9,
        "knee_r": (-0.1, -1.0, 0.1), "knee_l": (0.1, -1.0, 0.1),
    }


# velocidades de los umbrales del blend tree (generate_assets.py KAITO_LOCO): Speed = v / 6.2
WALK_MPS, JOG_MPS, RUN_MPS = 1.2, 3.4, 6.2
WALK_SWING = [(0.5, -0.02, 0.33, -6.0)]
WALK = G.Gait("Walk", WALK_MPS, 18, {
    "l": G.FootCycle("L", WALK_MPS * U, 0.6, 0.62, 0.23, y_mid=0.04, heel=0.18, toe=0.3, pitch_in=-14.0, pitch_out=26.0,
                     swing=WALK_SWING, yaw=8.0),
    "r": G.FootCycle("R", WALK_MPS * U, 0.6, 0.62, -0.23, y_mid=0.04, heel=0.18, toe=0.3, pitch_in=-14.0, pitch_out=26.0,
                     swing=WALK_SWING, yaw=-8.0),
}, body_walk, notes=f"paso a {WALK_MPS} m/s: 18 cuadros, talón -> punta")
JOG_SWING = [(0.3, 0.28, 0.45, 40.0), (0.7, -0.24, 0.4, -4.0)]
JOG = G.Gait("Jog", JOG_MPS, 14, {
    "l": G.FootCycle("L", JOG_MPS * U, 14 / 30.0, 0.3, 0.21, y_mid=0.08, pitch_in=4.0, pitch_out=40.0, toe=1.0, swing=JOG_SWING,
                     yaw=6.0, pivot="toe"),
    "r": G.FootCycle("R", JOG_MPS * U, 14 / 30.0, 0.3, -0.21, y_mid=0.08, pitch_in=4.0, pitch_out=40.0, toe=1.0, swing=JOG_SWING,
                     yaw=-6.0, pivot="toe"),
}, body_jog, notes=f"trote a {JOG_MPS} m/s: 14 cuadros")
RUN_SWING = [(0.18, 0.40, 0.55, 62.0), (0.45, 0.10, 0.62, 30.0), (0.75, -0.42, 0.42, -6.0)]
RUN = G.Gait("Run", RUN_MPS, 12, {
    "l": G.FootCycle("L", RUN_MPS * U, 0.4, 2.0 / 12.0, 0.2, y_mid=0.1, pitch_in=6.0, pitch_out=48.0, toe=1.0, swing=RUN_SWING,
                     yaw=6.0, pivot="toe"),
    "r": G.FootCycle("R", RUN_MPS * U, 0.4, 2.0 / 12.0, -0.2, y_mid=0.1, pitch_in=6.0, pitch_out=48.0, toe=1.0, swing=RUN_SWING,
                     yaw=-6.0, pivot="toe"),
}, body_run, notes="carrera a 6.2 m/s (PlayerConfig.runSpeed): 12 cuadros, apoyo de 2 cuadros por pie sobre la bola")
for _g in (WALK, JOG, RUN):
    CLIPS.append(_g.clip())


# =========================================================================== golpes: pies relativos al cuerpo
def fr(side, x, y_rel, tv, yaw=0.0, heel=0.0):
    """Pie apoyado (o en punta con 'heel' grados) a 'y_rel' del cuerpo cuando ya avanzó 'tv' (u): la huella en
    el mundo es y_rel - tv (dos claves con la misma huella en el mundo = pie clavado)."""
    return toe(side, x, y_rel - tv, yaw, heel) if heel else flat(side, x, y_rel - tv, yaw)


def fa(x, y_rel, z, tv, pitch=0.0, yaw=0.0):
    """Pie en el aire a 'y_rel' del cuerpo."""
    return air(x, y_rel - tv, z, pitch, yaw)


# =========================================================================== corte 1 (derecha -> izquierda)
# carga: la hoja atrás de su hombro derecho y AFUERA (desde arriba sale de la silueta por la derecha), cadera
# cargada a la derecha, los dos talones arriba sobre la huella de la guardia (empuja); salto corto hacia adelante
# (los 0.9 m los mueve el juego, f2-f5), los dos pies en el aire mientras avanza, la hoja barre por su derecha
# hasta cruzar adelante (impacto) y termina envuelta a su izquierda; el pie derecho apoya al terminar el avance y
# el izquierdo un cuadro después.
# Los pies NUNCA tocan el piso mientras el juego mueve el cuerpo: el imán del ataque corta el avance contra un
# enemigo pegado (PlayerController.TickAttack) y un pie clavado en el mundo patinaba 22-60 cm hacia atrás; en el
# aire, un avance más corto es solo un salto más corto
A1_N = 13
A1_TR = lunge_travel(A1_N, 2, 5, 0.9)
T1 = A1_TR
_a1_cock = feet(mod(READY, hips=(0.0, 0.08, -0.1), hips_rot=(0.0, 0.0, -20.0), spine=(2.0, -3.0, -18.0), head=(-4.0, 0.0, 16.0),
                    clav_r=(0.0, 6.0, 0.0), grip=(-0.61, 0.06, 1.42), blade=(-0.12, 0.25, 0.96), edge=(-0.29, -0.93, 0.21),
                    elbow_r=(-0.6, 0.5, 0.5), hand_l=(0.48, -0.42, 1.32), hand_l_dir=(0.1, -0.9, 0.1), hand_l_up=(0.3, 0.0, 1.0),
                    fingers_l=0.15),
                r=fr("R", R_FOOT[0], R_FOOT[1], T1[2], R_FOOT[2], 22.0), l=fr("L", L_FOOT[0], L_FOOT[1], T1[2], L_FOOT[2], 30.0))
# la mano libre se va atrás con el tajo (el contrapeso): un tercio en el barrido y el resto en el impacto. Entera en el
# impacto daba vuelta 69° en un cuadro que la estela no tapa (la estela es de la katana)
_A1_ARM_L = dict(hand_l=(0.55, 0.05, 1.25), hand_l_dir=(0.6, 0.6, -0.3), hand_l_up=(0.0, 0.0, 1.0))


def _a1_arm_l(u):
    """La mano libre a la fracción u de su vuelta atrás, de la carga al impacto."""
    return {k: v for k, v in inter(_a1_cock, mod(_a1_cock, **_A1_ARM_L), u).items() if k in _A1_ARM_L}


# (el pie de atrás despega en dos cuadros: subiendo entero en f3 la pierna giraba 77° en un cuadro)
_a1_sweep = feet(mod(_a1_cock, lift=0.08, hips=(0.0, -0.02, -0.06), hips_rot=(10.0, 0.0, -4.0), spine=(9.0, 0.0, -6.0),
                     head=(-8.0, 0.0, 6.0), grip=(-0.6, -0.36, 1.28), blade=(-0.8, -0.35, 0.48), edge=(-0.37, -0.34, -0.86),
                     elbow_r=(-0.6, 0.4, -0.3), **_a1_arm_l(0.35)),
                 r=fa(-0.24, -0.42, 0.44, T1[3], -10.0, 6.0), l=fa(0.3, 0.25, 0.3, T1[3], 8.0, 30.0))
_a1_hit = feet(mod(READY, lift=0.06, hips=(0.0, -0.1, -0.12), hips_rot=(14.0, 0.0, 16.0), spine=(12.0, 0.0, 10.0),
                   head=(-14.0, 0.0, -10.0), clav_r=(0.0, 0.0, 8.0), grip=(-0.11, -0.65, 1.13), blade=(0.08, -1.0, 0.0),
                   edge=(0.77, 0.03, -0.64), elbow_r=(-0.5, 0.1, -0.9), fingers_l=0.3, **_A1_ARM_L),
               r=fa(-0.24, -0.4, 0.36, T1[4], -12.0, 4.0), l=fa(0.3, 0.3, 0.46, T1[4], 18.0, 30.0))
_a1_cross = feet(mod(_a1_hit, lift=0.0, hips_rot=(14.0, 0.0, 26.0), spine=(12.0, 0.0, 18.0), head=(-13.0, 0.0, -16.0),
                     grip=(0.08, -0.53, 1.05), blade=(0.75, -0.61, -0.26), edge=(0.4, 0.73, -0.55), elbow_r=(-0.3, -0.1, -0.9)),
                 r=fr("R", -0.24, -0.2, T1[5], 2.0), l=fa(0.3, 0.32, 0.4, T1[5], 10.0, 30.0))
_a1_over = feet(mod(_a1_cross, hips=(0.02, -0.06, -0.15), hips_rot=(12.0, 0.0, 34.0), spine=(10.0, 0.0, 22.0), head=(-12.0, 0.0, -20.0),
                    grip=(0.29, -0.28, 0.9), blade=(0.94, 0.24, -0.24), edge=(-0.32, 0.85, -0.41), elbow_r=(-0.2, -0.2, -0.9)),
                r=fr("R", -0.24, -0.2, T1[6], 2.0), l=fr("L", 0.3, 0.3, T1[6], 30.0))
# El final del Corte 1 (y principio del Corte 2): la hoja termina adelante a su izquierda, baja y afuera de la silueta, y
# de ahí vuelve a la guardia si no encadena (envuelta hacia la carga del revés quedaba con la punta a 3 cm del piso, escondida
# detrás de él desde la cámara del juego, y el fundido a la guardia le hacía dar media vuelta, 141°)
A1_END = feet(mod(READY, hips=(0.0, 0.0, -0.11), hips_rot=(6.0, 0.0, 26.0), spine=(8.0, 0.0, 14.0), head=(-8.0, 0.0, -16.0),
                  grip=(0.2, -0.39, 0.91), blade=(0.76, -0.53, -0.37), edge=(0.29, 0.79, -0.55), elbow_r=(-0.3, 0.0, -0.9),
                  hand_l=(0.5, 0.0, 1.15), hand_l_dir=(0.4, 0.5, -0.7), hand_l_up=(0.3, 0.0, 1.0), fingers_l=0.5),
              r=flat("R", -0.24, -0.2, 2.0), l=flat("L", 0.3, 0.3, 30.0))
# a f8 ya está en la pose de empalme (el combo se puede encadenar desde f7: el crossfade de 0.03 s no salta)
_a1_settle = feet(mod(A1_END, hips=(0.0, 0.0, -0.14), grip=(0.19, -0.39, 0.94), blade=(0.78, -0.51, -0.37)), r=fr("R", -0.24, -0.2, T1[8], 2.0),
                  l=fr("L", 0.3, 0.3, T1[8], 30.0))
add("Attack1", A1_N, [
    # (la carga con curva pareja: con "out" el 88 % entraba en el primer cuadro y la mano giraba 75°)
    (0, READY, "sine"), (2, _a1_cock, "sine"), (3, _a1_sweep, "in2"), (4, _a1_hit, "lin"), (5, _a1_cross, "out2"),
    (6, _a1_over, "out"), (8, _a1_settle, "sine"), (13, at_travel(A1_END, T1[13]), "sine")],
    travel=A1_TR,
    timing={"apex": 2, "contact": 4, "active": [4, 7], "combo": 7, "lunge": [2, 5, 0.9], "riposte_from": 2, "chain_to": "A1_END"},
    events=[{"frame": 4, "fn": "Strike"}, {"frame": 5, "fn": "FootR"}, {"frame": 6, "fn": "FootL"}],
    notes="tajo de derecha a izquierda con salto corto (en el aire mientras avanza); el pie derecho apoya al terminar el avance")

# =========================================================================== corte 2 (revés ascendente)
# desde A1_END: la muñeca se enrosca atrás a su izquierda en dos cuadros (los dos talones arriba: empuja; en f2 ya salta
# con la cadera que empieza a desenroscarse y la hoja todavía atrás), la hoja sube cruzando por delante en un cuadro, debajo
# de la estela (impacto), hasta arriba a su derecha; el pie izquierdo (el de atrás) pasa adelante en el aire y apoya al
# terminar el avance (f4), el derecho tres cuadros después. La carga es corta (un 60 % de A2_COIL_ARM, la de antes) y la
# hoja se enrosca con el filo casi como lo dejó el Corte 1: se da vuelta en el tajo, debajo de la estela (empieza en f2.1).
# Con la carga entera y el filo dado vuelta en f1 la mano de la katana daba 131° en un cuadro que la estela no tapa, y con
# la carga entera en f2 la muñeca quedaba 40° pasada
A2_N = 11
A2_TR = lunge_travel(A2_N, 1, 4, 1.0)
T2 = A2_TR
A2_COIL_ARM = dict(grip=(0.38, -0.14, 0.88), blade=(0.6, 0.6, -0.5), edge=(-0.780, 0.343, -0.524), elbow_r=(-0.1, 0.2, -0.95))
_a2_coil = feet(mod(A1_END, hips=(0.0, 0.0, -0.14), hips_rot=(8.0, 0.0, 29.0), spine=(10.0, 0.0, 18.0), head=(-8.0, 0.0, -22.0),
                    **{k: v for k, v in inter(A1_END, mod(A1_END, **A2_COIL_ARM), 0.3).items() if k in A2_COIL_ARM}),
                r=fr("R", -0.24, -0.2, T2[1], 2.0, 24.0), l=fr("L", 0.3, 0.3, T2[1], 30.0, 34.0))
# (los pies se cruzan en el aire en dos cuadros, f2-f4: cruzándolos en el primero la pierna derecha giraba 98° en un cuadro)
_a2_low = feet(mod(_a2_coil, lift=0.06, hips=(0.0, -0.06, -0.14), hips_rot=(10.0, 0.0, 24.0), spine=(11.0, 0.0, 15.0),
                   head=(-11.0, 0.0, -8.0), hand_l=(0.58, -0.15, 1.2),
                   **{k: v for k, v in inter(A1_END, mod(A1_END, **A2_COIL_ARM), 0.6).items() if k in A2_COIL_ARM}),
               r=fa(-0.25, -0.08, 0.36, T2[2], 4.0, 2.0), l=fa(0.25, 0.06, 0.38, T2[2], 6.0, 20.0))
_a2_hit = feet(mod(READY, lift=0.05, hips=(0.0, -0.1, -0.12), hips_rot=(10.0, 0.0, -4.0), spine=(10.0, 4.0, -8.0),
                   head=(-12.0, -4.0, 6.0), clav_r=(0.0, 6.0, 0.0), grip=(-0.28, -0.71, 1.28), blade=(0.38, -0.88, 0.27),
                   edge=(-0.8, -0.46, -0.39), elbow_r=(-0.5, 0.3, -0.8), hand_l=(0.55, -0.25, 1.18), hand_l_dir=(0.5, 0.5, -0.7),
                   hand_l_up=(0.2, 0.0, 1.0), fingers_l=0.4),
               r=fa(-0.28, 0.18, 0.42, T2[3], 16.0, 0.0), l=fa(0.22, -0.18, 0.36, T2[3], -8.0, 12.0))
A2_END = feet(mod(READY, hips=(0.0, 0.04, -0.09), hips_rot=(2.0, 0.0, -22.0), spine=(2.0, 4.0, -20.0), head=(-6.0, -4.0, 18.0),
                  clav_r=(0.0, 10.0, 0.0), grip=(-0.42, -0.03, 1.69), blade=(-0.06, 0.56, 0.83), edge=(-0.13, -0.82, 0.56),
                  elbow_r=(-0.7, 0.4, 0.3), hand_l=(0.2, -0.55, 1.42), hand_l_dir=(-0.4, -0.5, 0.6), hand_l_up=(0.5, -0.5, 0.5),
                  fingers_l=0.35),
              r=flat("R", -0.3, 0.18, 0.0), l=flat("L", 0.22, -0.3, 10.0))
# el brazo libre, abierto a su izquierda por el tajo, vuelve parejo por el costado a adelante del pecho (A2_END: la mano que va
# a tomar la empuñadura en el Corte final) de f3 a f7, floja mientras viaja (sigue al antebrazo) y siempre a más de medio
# brazo del hombro. En dos cuadros (f5-f7) la mano daba vuelta 144° y el brazo iba de la cadera a la horizontal y se plegaba
# entero contra el hombro (la mano a 6 cm); la estela tapa la katana, no esta mano
_A2_ARM_L = ("hand_l", "hand_l_dir", "hand_l_up", "elbow_l")
_A2_BACK = {ch: "lin" for ch in _A2_ARM_L + ("hand_l_relax",)}


def _a2_arm(u, hand, relax):
    """El brazo izquierdo a la fracción u de su vuelta del tajo (f3) a adelante del pecho (A2_END), la muñeca en 'hand' y la
    mano floja 'relax'."""
    return dict({k: v for k, v in inter(_a2_hit, A2_END, u).items() if k in _A2_ARM_L}, hand_l=hand, hand_l_relax=relax)


_a2_rise = feet(mod(_a2_hit, lift=0.0, hips_rot=(8.0, 0.0, -16.0), spine=(7.0, 5.0, -16.0), head=(-11.0, -5.0, 14.0),
                    clav_r=(0.0, 12.0, 0.0), grip=(-0.49, -0.53, 1.54), blade=(-0.31, -0.6, 0.73), edge=(-0.29, -0.67, -0.68),
                    elbow_r=(-0.6, 0.3, -0.2), **_a2_arm(0.25, (0.55, -0.42, 1.25), 0.6)),
                r=fa(-0.3, 0.14, 0.37, T2[4], 12.0, 0.0), l=fr("L", 0.22, -0.3, T2[4], 10.0))
_a2_over = feet(mod(_a2_rise, hips=(0.0, -0.06, -0.1), hips_rot=(6.0, 0.0, -26.0), spine=(4.0, 6.0, -24.0), head=(-10.0, -6.0, 20.0),
                    clav_r=(0.0, 14.0, 0.0), grip=(-0.46, -0.2, 1.72), blade=(-0.21, 0.35, 0.91), edge=(-0.19, -0.93, 0.32),
                    elbow_r=(-0.7, 0.4, 0.2), **_a2_arm(0.5, (0.5, -0.55, 1.32), 1.0)),
                r=fa(-0.3, 0.17, 0.33, T2[5], 2.0, 0.0), l=fr("L", 0.22, -0.3, T2[5], 10.0))
add("Attack2", A2_N, [
    (0, A1_END, "sine"), (1, _a2_coil, "out"), (2, _a2_low, "in2"), (3, _a2_hit, "lin"), (4, _a2_rise, "out2", _A2_BACK),
    (5, _a2_over, "out", _A2_BACK), (7, feet(mod(A2_END, hips=(0.0, 0.03, -0.12), hand_l_relax=0.0), r=fr("R", -0.3, 0.18, T2[7], 0.0),
                                                l=fr("L", 0.22, -0.3, T2[7], 10.0)), "sine", _A2_BACK),
    (11, at_travel(A2_END, T2[11]), "sine")],
    travel=A2_TR,
    timing={"apex": 2, "contact": 3, "active": [3, 6], "combo": 6, "lunge": [1, 4, 1.0], "chain_from": "A1_END", "chain_to": "A2_END"},
    events=[{"frame": 3, "fn": "Strike"}, {"frame": 4, "fn": "FootL"}, {"frame": 7, "fn": "FootR"}],
    notes="revés ascendente con un salto; el pie izquierdo pasa adelante en el aire y apoya al terminar el avance")

# =========================================================================== corte final (salto a dos manos)
# desde A2_END: sube la hoja con las dos manos por encima de su hombro derecho y la tira AFUERA y atrás (la
# punta 0.9 m a su derecha: desde la cámara del juego sale de la silueta por el costado; atrás de la cabeza la
# tapaban la cabeza y el pelo y el corte final no se distinguía de los otros dos), se agacha, salta 1.6 m, la hoja
# pasa por arriba y baja en diagonal: cruza adelante en el impacto y queda baja y abierta a su izquierda al caer
# (una línea larga que sale del cuerpo, no metida debajo de la cabeza); 3 cuadros de impacto quieto
A3_N = 20
A3_TR = lunge_travel(A3_N, 3, 7, 1.6)
T3 = A3_TR
_a3_raise = feet(mod(A2_END, hips=(0.0, 0.1, -0.22), hips_rot=(-4.0, 0.0, -26.0), spine=(-8.0, 4.0, -18.0), head=(-2.0, -4.0, 20.0),
                     clav_r=(0.0, 14.0, 0.0), clav_l=(0.0, -10.0, 0.0), grip=(-0.34, -0.18, 1.86), blade=(-0.95, -0.25, -0.17),
                     edge=(-0.03, -0.46, 0.88), elbow_r=(-0.8, 0.2, 0.4), grip_l=1.0, elbow_l=(0.8, 0.2, 0.2), fingers_l=1.0,
                     # (la mano izquierda suelta, donde va a quedar en la empuñadura: mientras la toma de a poco, f3-f5, la
                     # mezcla no la hace volver adelante del pecho)
                     hand_l=(-0.04, -0.1, 1.88), hand_l_dir=(-0.434, -0.399, 0.808), hand_l_up=(-0.163, 0.917, 0.365)),
                 r=fr("R", -0.3, 0.18, T3[3], 0.0, 26.0), l=fr("L", 0.22, -0.3, T3[3], 10.0, 26.0))
# (los pies cambian de lado en el aire en cuatro cuadros, f3-f7: recogidos y cruzados ya en f5 la pierna izquierda giraba
# 127° en el despegue)
_a3_air = feet(mod(_a3_raise, hips=(0.0, 0.02, -0.08), hips_rot=(4.0, 0.0, -22.0), spine=(-4.0, 3.0, -16.0), lift=0.36,
                   grip=(-0.36, -0.22, 2.0), blade=(-0.96, -0.23, -0.14), edge=(-0.05, -0.36, 0.93)),
               r=fa(-0.3, 0.06, 0.52, T3[5], -4.0, 0.0), l=fa(0.24, -0.04, 0.54, T3[5], 14.0, 12.0))
_a3_over = feet(mod(_a3_air, hips=(0.0, -0.04, -0.06), hips_rot=(10.0, 0.0, -8.0), spine=(6.0, 0.0, -6.0), head=(-12.0, 0.0, 6.0), lift=0.2,
                    grip=(-0.22, -0.36, 2.06), blade=(-0.99, -0.14, 0.02), edge=(0.07, -0.38, 0.92)),
                r=fa(-0.3, -0.4, 0.42, T3[6], -14.0, 2.0), l=fa(0.26, 0.3, 0.45, T3[6], 20.0, 20.0))
# El impacto, con las DOS manos en la empuñadura (el hit-stop lo congela 0.11 s): la hoja adelante y un poco abajo (17°), el
# filo como lo pone el camino (ahí la mano derecha no lo puede llevar abajo: con la hoja acostada y el filo a su izquierda el
# camino la giraba 88° en este cuadro). Con la hoja apuntando adelante a su derecha la izquierda no tenía cómo tomar la
# empuñadura (la muñeca dada vuelta 110-120°) y se soltaba acá: el puño saltaba al lado de la cabeza (130° en un cuadro).
# El codo izquierdo va abajo y atrás (timing 'pin_l': el camino lo dejaba de punta) y el derecho afuera, sin bajar (con el
# polo abajo el camino del despegue giraba ese codo 60° por cuadro de f2 a f5 y el húmero daba 64° en f4-f5)
_a3_hit = feet(mod(READY, lift=0.0, hips=(0.0, -0.12, -0.15), hips_rot=(18.0, 0.0, 10.0), spine=(18.0, 0.0, 6.0), head=(-22.0, 0.0, -6.0),
                   clav_r=(0.0, -4.0, 4.0), clav_l=(0.0, 4.0, 4.0), grip=(-0.06, -0.68, 1.29), blade=(-0.01, -0.96, -0.29),
                   edge=(-0.59, -0.23, 0.77), elbow_r=(-0.8, 0.3, 0.0), grip_l=1.0, elbow_l=(0.2, 0.7, -0.7), fingers_l=1.0),
               r=fr("R", -0.27, -0.42, T3[7], 4.0), l=fr("L", 0.3, 0.38, T3[7], 26.0, 34.0))
# la mano izquierda suelta la empuñadura DESPUÉS del impacto, mientras la hoja sigue sola abajo a su izquierda, y cae floja
# delante de la cadera izquierda: casi la mitad del camino en f8 y el resto, que el brazo termina de acomodar, en la pose
# quieta (f8-f11, 'settle_l'). La muñeca se desenrosca de la empuñadura a recta de a poco (hand_l_relax 0.5 en f8, 1 en f11) y
# sigue floja en la vuelta; los dedos se abren en los mismos cuadros (de golpe en f8 daban 74°). Abierta a su izquierda y
# atrás, como antes, el brazo tenía que dar 150° desde la empuñadura (adelante y adentro) en esos cuatro cuadros; quieta
# delante del pecho quedaba con el puño bajo el mentón y el codo atrás
A3_LOW = feet(mod(_a3_hit, hips=(0.0, -0.16, -0.27), hips_rot=(22.0, 0.0, 18.0), spine=(22.0, 0.0, 10.0), head=(-26.0, 0.0, -10.0),
                  grip=(0.2, -0.49, 0.5), blade=(0.98, 0.07, 0.19), edge=(0.17, 0.22, -0.96), grip_l=0.0, fingers_l=0.65,
                  hand_l=(0.178, -0.473, 1.029), hand_l_dir=(-0.521, -0.145, 0.841), hand_l_up=(-0.838, 0.272, -0.472), hand_l_relax=0.5,
                  elbow_l=(0.4, 0.7, -0.6)),
              r=fr("R", -0.27, -0.42, T3[8], 4.0), l=fr("L", 0.3, 0.38, T3[8], 26.0, 34.0))
_a3_hold = feet(mod(A3_LOW, hips=(0.0, -0.17, -0.29), grip=(0.21, -0.48, 0.51), blade=(0.98, 0.06, 0.17), head=(-27.0, 0.0, -10.0),
                    hand_l=(0.368, -0.539, 0.816), hand_l_relax=1.0, fingers_l=0.3),
                r=fr("R", -0.27, -0.42, T3[11], 4.0), l=fr("L", 0.3, 0.38, T3[11], 26.0, 34.0))
# (floja también en la vuelta y recién en la guardia toma la suya: de la empuñadura a la de la guardia la mano gira 172°, y
# con la dirección y el dorso autorados y mezclados por separado el dorso daba media vuelta en f16 y el húmero se retorcía 65°)
_a3_rec = feet(mod(READY, hips=(0.0, 0.0, -0.14), grip_l=0.0, fingers_l=0.8, hand_l_relax=1.0,
                   **{k: v for k, v in inter(_a3_hold, READY, 0.5).items() if k in ("hand_l", "elbow_l")}),
               r=fa(-0.24, -0.3, 0.3, T3[15], 0.0, 6.0), l=fr("L", 0.3, 0.38, T3[15], 30.0))
_A3_FREE = ("hand_l", "hand_l_dir", "hand_l_up", "elbow_l", "hand_l_relax", "fingers_l")
# la mano izquierda gira libre hacia el agarre (el dorso pasa de adelante a atrás) ANTES de tomar la empuñadura: girando
# a mitad de camino con el agarre a medias la muñeca se quebraba 30° y el antebrazo daba media vuelta
# ...y la hoja pasa vertical junto a la cabeza, el puño a la altura de la sien y el filo adelante y a su derecha (un hasso
# alto): de ahí se acuesta afuera a su derecha con el filo arriba. Con el filo a su derecha en la vertical la mano tenía que
# darse vuelta 177° en el despegue, y con el filo adelante el camino pasaba el codo por el otro lado del brazo
_a3_reach = feet(mod(inter(A2_END, _a3_raise, 0.6), grip_l=0.0, hand_l=(0.06, -0.25, 1.62), hand_l_dir=(-0.43, -0.46, 0.77),
                     hand_l_up=(0.38, 0.31, 0.87), fingers_l=0.6, grip=(-0.42, -0.1, 1.7), blade=(0.0, 0.02, 1.0),
                     edge=(-0.643, -0.766, 0.0), elbow_r=(-0.7, 0.4, -0.3)),
                 r=fr("R", -0.3, 0.18, T3[2], 0.0, 17.0), l=fr("L", 0.22, -0.3, T3[2], 10.0, 17.0))
# El despegue (f0-f5: el juego lo lanza 1.6 m entre f3 y f7) pasa de A2_END, la mano supinada por el revés, a la pose a dos
# manos con la hoja acostada a su derecha, la mano pronada: la mano de la katana se da vuelta ~140°. Va parejo en cinco
# cuadros (la hoja, el filo, el puño y el codo en línea recta de la vertical en f2 a f5; tramo 'swing', ver kaito_rig.step_caps)
# mientras la izquierda llega a la empuñadura de a poco (un 20 % en f3, un 60 % en f4, entera en f5). Antes el camino se
# quedaba supinado hasta el despegue y se daba vuelta de un cuadro al otro (la mano 171°, sin estela: empieza en f5.4)
_A3_ARM = ("grip", "blade", "edge", "elbow_r")
_A3_LIFT = {ch: "lin" for ch in _A3_ARM}


def _a3_takeoff(u):
    """La katana a la fracción u del despegue (de _a3_reach en f2 a _a3_air en f5)."""
    return {k: v for k, v in inter(_a3_reach, _a3_air, u).items() if k in _A3_ARM}


_a3_mid = feet(mod(inter(_a3_reach, _a3_raise, 0.3), grip_l=0.2, fingers_l=0.8, **_a3_takeoff(0.4)),
               r=fr("R", -0.3, 0.18, T3[3], 0.0, 26.0), l=fr("L", 0.22, -0.3, T3[3], 10.0, 26.0))
_a3_raise4 = feet(mod(_a3_raise, lift=0.16, grip_l=0.6, **_a3_takeoff(0.6)),
                  # (el pie izquierdo, el que empuja, se va arrastrando atrás y abajo y recién se recoge en f5: recogido ya en
                  # f4 la tibia giraba 78° en el despegue)
                  r=fa(-0.3, 0.12, 0.42, T3[4], 0.0, 0.0), l=lifted("L", 0.23, -0.24 - T3[4], 0.05, 24.0, 12.0))
add("Attack3", A3_N, [
    # (de A2_END a la carga parejo: con "out" el 87 % entraba en f1 y los dos codos se estiraban 70° de golpe)
    (0, A2_END, "sine"), (2, _a3_reach, "sine"), (3, _a3_mid, "inout", _A3_LIFT), (4, _a3_raise4, "out", _A3_LIFT),
    (5, _a3_air, "inout", _A3_LIFT), (6, _a3_over, "in2"), (7, _a3_hit, "lin"),
    (8, A3_LOW, "out"), (11, _a3_hold, "lin", {ch: "lin" for ch in _A3_FREE}), (15, _a3_rec, "sine"),
    (17, feet(mod(READY, hips=(0.0, 0.01, -0.09)), r=fr("R", R_FOOT[0], R_FOOT[1], T3[17], R_FOOT[2]), l=fa(L_FOOT[0], L_FOOT[1], 0.4, T3[17], 8.0, L_FOOT[2])),
     "sine"),
    (20, feet(READY, r=fr("R", R_FOOT[0], R_FOOT[1], T3[20], R_FOOT[2]), l=fr("L", L_FOOT[0], L_FOOT[1], T3[20], L_FOOT[2])), "sine")],
    travel=A3_TR,
    timing={"apex": 3, "contact": 7, "active": [7, 10], "hold": [8, 11], "lunge": [3, 7, 1.6], "chain_from": "A2_END",
            "chain_to": "READY", "swing": [[0, 6]], "pin_l": [7], "settle_l": [[8, 11]]},
    # (la mano izquierda sin retraso: con el de LEAD, en el impacto la libre seguía 0.6 cuadros atrás, arriba de la cabeza)
    lag=mod(LEAD, hand_l=0.0),
    events=[{"frame": 7, "fn": "Strike"}, {"frame": 7, "fn": "Land"}],
    notes="salto con las dos manos, la hoja pasa por arriba y cruza en diagonal; cae con la hoja baja y queda quieto 3 cuadros")


# =========================================================================== dash mágico
# El juego lo toca a 1.4x (PlayerController.TryDash): 14 cuadros = 0.33 s reales. TickDash lo mueve desde el
# primer cuadro (40 m/s que bajan a 10 m/s en 0.26 s = f11) y después lo frena en 0.125 s (0.6 m más, hasta f14).
# Sin anticipación: arranca ya en el aire, en la pose aerodinámica (cuerpo bajo e inclinado, el brazo izquierdo
# atrás, la katana baja y adelante a su derecha como en la guardia, la rodilla derecha arriba adelante y la pierna
# izquierda estirada atrás: desde arriba es una flecha, y ningún pie roza el piso mientras viaja: la punta de atrás se
# arrastraba los 6.5 m). La katana iba atrás con el brazo, pero con el agarre (la hoja sale del lado del pulgar) eso
# pedía girar antebrazo y hombro hasta el tope: la muñeca quedaba quebrada 40° todo el dash. En f11 cae sobre
# la huella de la guardia, el talón derecho adelante con la punta arriba y la punta izquierda atrás: lo que
# todavía frena el juego se lee como un frenazo. Termina en la guardia (Dash -> Locomotion y Dash -> Corte 1 no
# saltan: antes terminaba de costado con los pies cambiados)
# los brazos quedan atrás y abajo como alas con el cuerpo inclinado. Van en el espacio del transform, escritos como quedaban
# en el del pecho (arm_space 1, pasados con Solver.body): de la carga del Corte del Viento (y a la caída del Dash), que van en
# el del transform, la mezcla de los dos espacios ponía las manos en un punto que no era ninguno y los brazos daban vuelta
# 110-170° en un cuadro. El izquierdo va al costado y un poco atrás (no del todo atrás): de ahí vuelve a la guardia en los
# cinco cuadros de la caída sin pasar 40° por cuadro autorado (el juego lo toca a x1.4); bien atrás daba 94° por cuadro
_DASH_ARMS = dict(grip=(-0.5, -0.283, 0.695), blade=(-0.505, -0.525, -0.685), edge=(0.201, 0.239, -0.95), elbow_r=(-0.667, 0.389, 0.636),
                  hand_l=(0.44, -0.107, 0.923), hand_l_dir=(0.202, 0.898, -0.39), hand_l_up=(1.0, 0.0, 0.0), elbow_l=(0.667, 0.389, 0.636))
_dash = feet(mod(READY, hips=(0.0, -0.04, -0.2), hips_rot=(24.0, 0.0, 0.0), spine=(8.0, 0.0, 0.0), head=(-22.0, 0.0, 0.0),
                 fingers_l=0.1, knee_r=(-0.1, -1.0, 0.2), hand_l_relax=1.0, **_DASH_ARMS),
             r=air(-0.2, -0.26, 0.44, -6.0, -4.0), l=air(0.22, 0.44, 0.52, 34.0, 8.0))
_dash_launch = feet(mod(_dash, hips=(0.0, -0.02, -0.18), hips_rot=(16.0, 0.0, 0.0), grip=(-0.5, -0.237, 0.747), blade=(-0.505, -0.615, -0.606),
                        edge=(0.201, 0.104, -0.974), elbow_r=(-0.667, 0.473, 0.576), hand_l=(0.44, -0.031, 0.948),
                        hand_l_dir=(0.202, 0.835, -0.512), elbow_l=(0.667, 0.473, 0.576)),
                    r=air(-0.2, -0.18, 0.38, -4.0, -4.0), l=air(0.22, 0.34, 0.46, 30.0, 8.0))
_dash_b = feet(mod(_dash, hips=(0.0, -0.04, -0.18), grip=(-0.51, -0.285, 0.737), hand_l=(0.45, -0.101, 0.97), head=(-21.0, 0.0, 0.0)),
               r=air(-0.2, -0.28, 0.46, -8.0, -4.0), l=air(0.22, 0.46, 0.54, 36.0, 8.0))
# la caída es la guardia frenando (cadera apenas atrás, talón derecho adelante con la punta arriba) con los brazos
# y la hoja YA en la guardia: un corte buffereado arranca desde acá con 0.1 s de fundido. Con el tronco más echado
# atrás (5° de cadera y 3° de pecho) el antebrazo izquierdo saltaba 38° en ese fundido: con brazos de 30 cm, unos
# centímetros de hombro son un codo entero
# (el talón apenas levantado, 3°, y la cadera casi en la de la guardia: con 8°, la punta de atrás en el aire y la cadera 3 cm más baja el
# corte buffereado entraba con la rodilla 26° de golpe y los pies corriéndose 3.6 cm)
_dash_land = feet(mod(READY, hips=(0.0, 0.03, -0.085), hips_rot=(2.5, 0.0, 14.0), arm_space=0.0),
                  r=plant("R", R_FOOT[0], R_FOOT[1], -3.0, R_FOOT[2], "heel"), l=flat("L", *L_FOOT))
DASH_END = feet(mod(READY, hips=(0.0, 0.04, -0.1)), r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))
# al caer (f11) la mano izquierda y la cabeza ya están en la guardia, sin atraso: con el atraso de LEAD todavía
# venían de las "alas" y un corte buffereado (TickDash: Attack1 con 0.05 s de fundido desde f11) los hacía saltar
# (f6-f11: del vuelo a la caída en cinco tiempos parejos, con los pies todavía en el aire bajando a sus huellas: de la
# flecha a la guardia en un cuadro los brazos y las piernas daban vuelta 65-104°, en tres el brazo izquierdo 80-94° por
# cuadro del juego)
_dash_pre00 = feet(inter(_dash, _dash_land, 0.12), r=air(-0.2, -0.26, 0.42, -6.0, -4.0), l=air(0.22, 0.4, 0.48, 32.0, 8.0))
_dash_pre0 = feet(inter(_dash, _dash_land, 0.3), r=lifted("R", R_FOOT[0], R_FOOT[1] - 0.12, 0.18, -5.0, R_FOOT[2]),
                  l=lifted("L", L_FOOT[0], L_FOOT[1] + 0.22, 0.2, 26.0, L_FOOT[2]))
_dash_pre = feet(inter(_dash, _dash_land, 0.52), r=lifted("R", R_FOOT[0], R_FOOT[1] - 0.06, 0.12, -4.0, R_FOOT[2]),
                 l=lifted("L", L_FOOT[0], L_FOOT[1] + 0.12, 0.14, 20.0, L_FOOT[2]))
_dash_pre2 = feet(inter(_dash, _dash_land, 0.76), r=lifted("R", R_FOOT[0], R_FOOT[1], 0.06, -3.0, R_FOOT[2]),
                  l=lifted("L", L_FOOT[0], L_FOOT[1] + 0.04, 0.07, 10.0, L_FOOT[2]))
add("Dash", 14, [(0, _dash_launch, "lin"), (2, _dash, "out"), (4, _dash_b, "sine"), (6, _dash, "sine"), (7, _dash_pre00, "sine"), (8, _dash_pre0, "lin"), (9, _dash_pre, "lin"), (10, _dash_pre2, "lin"),
                 (11, _dash_land, "lin"), (14, DASH_END, "sine")], lag=mod(LEAD, hand_l=0.0, head=0.0),
    timing={"travel_frames": [0, 11], "airborne": [0, 10], "play_speed": 1.4},
    notes="se toca a 1.4x: f0-f10 en el aire mientras viaja (0.26 s), cae en f11 en la guardia y frena (el juego lo desliza 0.6 m)")

# =========================================================================== parry
# GUARDIA: la hoja cruzada adelante a la altura del mentón, la punta a su izquierda y el filo hacia afuera, la
# palma izquierda apoyada en el lomo: desde arriba es una barra que cruza adelante de la cabeza. Sale en 2
# cuadros (la ventana del parry ya corre) y espera temblando; si no llegó nada, en 0.28 s vuelve a la guardia
GUARD = feet(mod(READY, hips=(0.0, 0.04, -0.13), hips_rot=(6.0, 0.0, 10.0), spine=(6.0, 0.0, -10.0), head=(-8.0, 0.0, 0.0),
                 clav_r=(0.0, 6.0, 0.0), grip=(-0.32, -0.32, 1.42), blade=(0.92, -0.2, 0.34), edge=(0.0, -0.95, 0.3),
                 elbow_r=(-0.7, 0.2, -0.6), hand_l=(0.11, -0.33, 1.46), hand_l_dir=(0.1, -0.15, 0.98), hand_l_up=(0.0, 1.0, 0.0),
                 elbow_l=(0.8, 0.3, -0.5), fingers_l=0.0),
             r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))
_guard_hold = mod(GUARD, hips=(0.0, 0.05, -0.15), tremble=1.0, grip=(-0.32, -0.33, 1.41), head=(-9.0, 0.0, 0.0))
# La guardia sube de un golpe: el 85 % en el primer cuadro (33 ms) y se asienta en el segundo. El parry perfecto dura 0.11 s
# y el desvío (ParrySuccessR/L, PerfectParry) arranca de la guardia con 0.02 s de fundido: repartida en 3 cuadros, en f1 la
# hoja todavía iba baja y horizontal (se leía como un tajo, no como una guardia) y un desvío temprano la levantaba 90° de
# golpe. Ese primer cuadro es un tirón a propósito ('snap_ok', como el cuadro del golpe recibido)
_guard_up = feet(inter(READY, GUARD, 0.85), r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))
add("ParryStance", 16, [(0, READY, "lin"), (1, _guard_up, "out"), (2, GUARD, "sine"), (5, mod(_guard_hold, tremble=0.4), "sine"),
                        (9, _guard_hold, "sine"), (16, READY, "sine")],
    # (sin atrasos: la palma tiene que llegar al lomo con la hoja y el desvío que arranca en la guardia no salta)
    lag={},
    timing={"guard": 2, "hold": [2, 9], "recover": [9, 16], "snap_ok": [[0, 1]]},
    notes="guardia en 2 cuadros (el 85 % en el primero), espera que tiembla hasta 0.3 s (ventana 0.24 s), vuelve a la "
          "guardia (ParryRecover 0.28 s)")

# contraataque listo: EXACTAMENTE la carga del Corte 1 (su f2, RIPOSTE_FRAME): la hoja atrás de su hombro derecho y
# los talones arriba. El contraataque (TickParrySuccess) arranca el Corte 1 en ese cuadro: sale del desvío sin
# volver a cargar, y desde el final del desvío no hay salto (antes la muñeca daba 130-160° en el fundido de 0.05 s)
COUNTER = _a1_cock

_defl_r = mod(GUARD, hips=(0.0, 0.1, -0.12), hips_rot=(0.0, 0.0, -12.0), spine=(0.0, 0.0, -14.0), head=(-4.0, 0.0, 10.0),
              grip=(-0.44, -0.42, 1.48), blade=(-0.24, -0.61, 0.75), edge=(-0.31, -0.71, -0.64), elbow_r=(-0.8, 0.2, -0.3),
              hand_l=(0.4, -0.42, 1.36), hand_l_dir=(0.0, -0.25, 0.97), hand_l_up=(0.0, 1.0, 0.0), fingers_l=0.0)
_defl_r2 = mod(_defl_r, hips=(0.0, 0.11, -0.13), grip=(-0.46, -0.41, 1.48), blade=(-0.26, -0.6, 0.76))
# Los desvíos llegan a la carga en 'counter_ready' (f5; el perfecto en f8) y ahí respiran: la réplica pedida sale desde
# ese cuadro (PlayerController.RiposteReady acelera el desvío hasta ahí) y tiene que pegar con el desviado todavía aturdido
# (Enemy.parriedRecoil 0.32 s). Con la carga en f7 / f13 la réplica llegaba cuando el enemigo ya se recuperaba
# (de la hoja abierta arriba a su derecha a la carga, un tercio en f3 con la cabeza y la mano libre a mitad de camino, como
# en el desvío a la izquierda: en un solo tramo el codo se doblaba 63° en el cuadro del medio)
_defl_r3 = feet(mod(inter(_defl_r2, COUNTER, 0.3),
                    **{k: v for k, v in inter(_defl_r2, COUNTER, 0.5).items() if k in ("head", "hand_l", "hand_l_dir", "hand_l_up", "elbow_l")}),
                r=toe("R", *R_FOOT, 7.0), l=toe("L", *L_FOOT, 9.0))
add("ParrySuccessR", 12, [(0, GUARD, "lin"), (1, _defl_r, "snap"), (2, _defl_r2, "lin"), (3, _defl_r3, "inout"), (5, COUNTER, "sine"),
                          (9, mod(COUNTER, hips=(0.0, 0.1, -0.14)), "sine"), (12, COUNTER, "sine")],
    timing={"impact": 1, "hold": [1, 2], "counter_ready": 5, "chain_to": "COUNTER"},
    notes="desvía hacia su derecha: la hoja se abre afuera y arriba, la palma empuja; un cuadro quieto y en f5 queda cargado")
_defl_l = mod(GUARD, hips=(0.0, 0.1, -0.15), hips_rot=(8.0, 0.0, 24.0), spine=(6.0, 0.0, 14.0), head=(-8.0, 0.0, -14.0),
              grip=(-0.1, -0.43, 1.17), blade=(0.66, -0.73, 0.17), edge=(0.6, 0.35, -0.7), elbow_r=(-0.5, 0.0, -0.85),
              hand_l=(0.5, 0.12, 1.24), hand_l_dir=(0.6, 0.6, -0.4), hand_l_up=(0.2, 0.0, 1.0), fingers_l=0.2)
_defl_l2 = mod(_defl_l, hips=(0.0, 0.11, -0.16), grip=(-0.1, -0.44, 1.16), blade=(0.68, -0.71, 0.18))
# (de la hoja baja a su izquierda a la carga arriba-atrás hay 140° de mano: un tercio en f3 y el resto parejo hasta f5; de una
# sola vez el cuadro del medio se llevaba 70°)
# (la cabeza y la mano libre, que llegan con atraso, ya a mitad de camino: el contraataque empalma en f5 como antes)
_defl_l3 = feet(mod(inter(_defl_l2, COUNTER, 0.3),
                    **{k: v for k, v in inter(_defl_l2, COUNTER, 0.5).items() if k in ("head", "hand_l", "hand_l_dir", "hand_l_up", "elbow_l")}),
                r=toe("R", *R_FOOT, 7.0), l=toe("L", *L_FOOT, 9.0))
add("ParrySuccessL", 12, [(0, GUARD, "lin"), (1, _defl_l, "snap"), (2, _defl_l2, "lin"), (3, _defl_l3, "inout"), (5, COUNTER, "sine"),
                          (9, mod(COUNTER, hips=(0.0, 0.1, -0.14)), "sine"), (12, COUNTER, "sine")],
    timing={"impact": 1, "hold": [1, 2], "counter_ready": 5, "chain_to": "COUNTER"},
    notes="desvía hacia su izquierda y abajo, el cuerpo gira con el golpe; un cuadro quieto y en f5 queda cargado")
# PERFECTO: la hoja salta arriba con la palma adelante (el destello), queda arriba 2 cuadros, baja girando y en f8 está en
# la carga del contraataque (COUNTER: el Corte 1 sale sin salto); si no contraataca se agazapa un poco más, la hoja atrás
# apuntando ("ahora te toca a vos"), y vuelve a la carga
_flick = feet(mod(GUARD, hips=(0.0, 0.06, -0.04), hips_rot=(-2.0, 0.0, 4.0), spine=(-6.0, 0.0, -4.0), head=(-4.0, 0.0, 0.0),
                  clav_r=(0.0, 12.0, 0.0), grip=(-0.33, -0.31, 1.86), blade=(0.26, -0.28, 0.92), edge=(0.0, -0.95, -0.3),
                  elbow_r=(-0.8, 0.3, 0.0), hand_l=(0.36, -0.5, 1.42), hand_l_dir=(0.0, -0.3, 0.95), hand_l_up=(0.0, 1.0, 0.0),
                  fingers_l=0.0),
              r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))
_flick2 = mod(_flick, hips=(0.0, 0.06, -0.05), grip=(-0.34, -0.31, 1.87), blade=(0.23, -0.26, 0.94))
LOW_COUNTER = feet(mod(READY, hips=(0.0, 0.08, -0.24), hips_rot=(10.0, 0.0, -18.0), spine=(14.0, 0.0, -14.0), head=(-22.0, 0.0, 12.0),
                       grip=(-0.5, 0.03, 0.93), blade=(-0.04, 0.92, 0.4), edge=(0.34, 0.39, -0.86), elbow_r=(-0.6, 0.6, 0.2),
                       hand_l=(0.36, -0.45, 1.02), hand_l_dir=(0.0, -0.9, -0.3), hand_l_up=(0.0, 0.0, 1.0), fingers_l=0.2),
                   r=flat("R", *R_FOOT), l=toe("L", *L_FOOT, 20.0))
add("PerfectParry", 14, [(0, GUARD, "lin"), (1, _flick, "snap"), (3, _flick2, "lin"), (5, mod(_flick, grip=(-0.45, -0.1, 1.49),
                                                                                       blade=(-0.43, 0.3, 0.85), edge=(0.34, -0.85, 0.41)), "in2"),
                         (8, COUNTER, "out"), (11, inter(COUNTER, LOW_COUNTER, 0.35), "sine"), (14, COUNTER, "sine")],
    timing={"impact": 1, "hold": [1, 3], "counter_ready": 8, "chain_to": "COUNTER"},
    notes="parry perfecto: la hoja salta arriba y la palma adelante (3 cuadros), baja girando a una guardia agazapada y "
          "queda cargado como el Corte 1")

# =========================================================================== golpe propio desviado
# el enemigo devuelve el golpe (Blocked): la hoja sale despedida arriba y atrás, el cuerpo se va hacia atrás
# con un saltito y cae agachado SOBRE LAS HUELLAS DE LA GUARDIA (después no se corre nada: el clip termina en la
# guardia sin arrastrar los pies). El empujón del juego (Push 0.9: ~1.3 m en 0.3 s) lo desliza en el mundo hasta
# f9: esos dos cuadros de patinada al caer son a propósito (frena sobre las suelas)
_knock = feet(mod(READY, hips=(0.0, 0.14, -0.06), hips_rot=(-12.0, 0.0, -8.0), spine=(-14.0, 0.0, -6.0), head=(4.0, 0.0, 8.0),
                  clav_r=(0.0, 14.0, 0.0), grip=(-0.46, 0.05, 1.76), blade=(-0.23, 0.56, 0.79), edge=(0.0, -0.8, 0.6),
                  elbow_r=(-0.8, 0.4, 0.3), hand_l=(0.55, 0.18, 1.36), hand_l_dir=(0.6, 0.4, 0.5), hand_l_up=(0.0, 0.5, 0.8),
                  fingers_l=0.05),
              r=toe("R", *R_FOOT, 30.0), l=flat("L", *L_FOOT))
# (cae con la katana adelante y el brazo medio estirado: con el puño pegado debajo del hombro el brazo quedaba plegado
# del todo y el codo daba vuelta con cualquier cambio chico)
_knock_land = feet(mod(READY, hips=(0.0, 0.1, -0.18), hips_rot=(8.0, 0.0, 6.0), spine=(14.0, 0.0, -4.0), head=(-14.0, 0.0, 0.0),
                       grip=(-0.62, -0.3, 1.08), blade=(-0.45, -0.55, 0.7), edge=(-0.2, -0.75, -0.6), hand_l=(0.48, -0.2, 1.1),
                       fingers_l=0.3),
                   r=flat("R", *R_FOOT), l=toe("L", *L_FOOT, 20.0))
# en el saltito los brazos ya empiezan a volver (un 30 %): cayendo enteros de la pose del rebote en los últimos 3 cuadros,
# los codos daban vuelta 65-77° por cuadro
_KN_ARMS = ("grip", "blade", "edge", "elbow_r", "clav_r", "hand_l", "hand_l_dir", "hand_l_up", "elbow_l", "fingers_l")
# ...y el pecho ya empieza a volver adelante (un 35 %) y termina de cerrarse después de caer (f7-f9): echado atrás 20° hasta
# f4 y cerrado adelante en f6, el hombro se corría 20 cm en un cuadro, la mano quedaba atrás y el brazo se plegaba entero
# (el húmero 100° en un cuadro)
_KN_CHEST = ("hips_rot", "spine", "head")
_knock_air = feet(mod(_knock, hips=(0.0, 0.12, -0.04), lift=0.12,
                      **{k: v for k, v in inter(mod(_knock, hips_rot=(-8.0, 0.0, -6.0)), _knock_land, 0.35).items() if k in _KN_CHEST},
                      **{k: v for k, v in inter(_knock, _knock_land, 0.3).items() if k in _KN_ARMS}),
                  r=air(-0.24, -0.25, 0.42, -16.0, 6.0), l=air(0.3, 0.2, 0.36, 10.0, 30.0))
_knock_touch = mod(_knock_land, **{k: v for k, v in inter(_knock_air, _knock_land, 0.85).items() if k in _KN_CHEST})
# (después del golpe la hoja sigue subiendo y el pecho se va atrás parejos hasta el saltito: con "out" el 70 % del tramo entraba en
# f1-f2 y el codo derecho se doblaba 105° por cuadro del juego, y cayendo con el 70 % en f6 el húmero daba 62°)
add("Blocked", 14, [(0, READY, "lin"), (1, _knock, "snap"), (4, _knock_air, "lin"),
                    (6, feet(inter(_knock_air, _knock_land, 0.5), r=hover("R", R_FOOT[0], R_FOOT[1], R_FOOT[2], 0.04),
                             l=hover("L", L_FOOT[0], L_FOOT[1], L_FOOT[2], 0.06)), "sine"),
                    (7, _knock_touch, "in2"), (9, _knock_land, "out"), (14, READY, "sine")],
    # (la guardia imperfecta lo toca a x1.3: PlayerController.ImperfectGuard)
    timing={"impact": 1, "slide_ok": True, "play_speed": 1.3},
    notes="rebote contra la guardia: la hoja sale despedida arriba-atrás, saltito hacia atrás, cae agachado en la guardia")

# =========================================================================== recibir daño
# el juego lo empuja (Push: 0.8-1.5 m en 0.3-0.5 s) y lo da vuelta hacia el golpe: los pies apoyados patinan EN EL
# MUNDO a propósito (frena sobre las suelas); dentro del clip no se corren (el final es la guardia sin arrastre)
_hit = feet(mod(READY, hips=(0.0, 0.12, -0.08), hips_rot=(-12.0, 0.0, 8.0), spine=(-14.0, 0.0, 6.0), head=(8.0, 4.0, 10.0),
                clav_r=(0.0, 8.0, 0.0), clav_l=(0.0, -8.0, 0.0), grip=(-0.6, -0.05, 1.15), blade=(-0.4, -0.7, 0.6),
                edge=(0.0, -0.65, -0.76), elbow_r=(-0.8, 0.3, 0.0), hand_l=(0.56, 0.12, 1.3), hand_l_dir=(0.7, 0.3, 0.4),
                hand_l_up=(0.0, 0.0, 1.0), fingers_l=0.05),
            r=toe("R", *R_FOOT, 20.0), l=flat("L", *L_FOOT))
_hit2 = mod(_hit, hips=(0.0, 0.13, -0.1), spine=(-12.0, 0.0, 6.0), head=(6.0, 4.0, 10.0))
_hit_rec = feet(mod(READY, hips=(0.0, 0.07, -0.13), spine=(12.0, 0.0, -6.0), head=(-12.0, 0.0, -2.0), grip=(-0.58, -0.22, 0.98)),
                r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))
add("Hit", 11, [(0, READY, "lin"), (1, _hit, "snap"), (3, _hit2, "lin"), (6, _hit_rec, "sine"), (11, READY, "sine")],
    timing={"impact": 1, "slide_ok": True},
    notes="golpe liviano: la cabeza y el pecho se van atrás de golpe, los brazos se abren; recupera la guardia en 0.37 s")
# golpes según de dónde vienen: PlayerController.TakeDamage elige el clip por el lado del que llega el golpe respecto de
# hacia dónde mira Kaito y en esos ya no lo da vuelta hacia el atacante (antes todos los golpes se veían de frente):
# de frente "Hit" (lo gira, como siempre), de atrás "HitBack", desde su izquierda "HitLeft" y desde su derecha
# "HitRight". Mismos tiempos que Hit (impacto en f1, guardia en f11: 0.37 s), el juego lo empuja hacia donde va el golpe
# (los pies patinan en el mundo a propósito; dentro del clip no se corren) y la cabeza llega un cuadro tarde
# de atrás: la cadera y el pecho se van adelante, la cabeza latiguea atrás, los brazos se abren; el pie de atrás en punta
_hb = feet(mod(READY, hips=(0.0, -0.12, -0.08), hips_rot=(16.0, 0.0, 6.0), spine=(14.0, 0.0, 4.0), head=(-16.0, 0.0, 6.0),
               clav_r=(0.0, 10.0, 0.0), clav_l=(0.0, -10.0, 0.0), grip=(-0.6, -0.1, 1.15), blade=(-0.4, -0.7, 0.6),
               edge=(0.0, -0.65, -0.76), elbow_r=(-0.8, 0.5, 0.1), hand_l=(0.6, -0.08, 1.4), hand_l_dir=(0.7, -0.1, 0.7),
               hand_l_up=(0.0, -1.0, 0.0), elbow_l=(0.8, 0.5, -0.3), fingers_l=0.05),
           r=flat("R", *R_FOOT), l=toe("L", *L_FOOT, 26.0))
_hb2 = mod(_hb, hips=(0.0, -0.13, -0.1), spine=(16.0, 0.0, 4.0), head=(-10.0, 0.0, 4.0))


def _arm_back(hit, u):
    """El brazo libre a la fracción u de su vuelta desde la pose del golpe a la guardia: llega último (con la guardia
    entera ya en f6 la mano daba 70-100° por cuadro al volver)."""
    m = inter(hit, READY, u)
    return {k: m[k] for k in ("hand_l", "hand_l_dir", "hand_l_up", "elbow_l", "fingers_l")}


_hb_rec = feet(mod(READY, hips=(0.0, 0.0, -0.12), spine=(10.0, 0.0, -6.0), head=(-10.0, 0.0, -2.0), **_arm_back(_hb2, 0.4)),
               r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))
add("HitBack", 11, [(0, READY, "lin"), (1, _hb, "snap"), (3, _hb2, "lin"), (6, _hb_rec, "sine"), (11, READY, "sine")],
    timing={"impact": 1, "slide_ok": True},
    notes="golpe de atrás: el cuerpo se va adelante y la cabeza atrás, los brazos se abren; guardia en 0.37 s")
# desde su izquierda: la cadera se corre a su derecha, el tronco se dobla y gira hacia la derecha (se aleja del golpe), la
# cabeza latiguea a la derecha; el brazo izquierdo vuela afuera y arriba, la katana se abre a su derecha; el peso queda
# en el pie derecho (el izquierdo en punta)
_hl = feet(mod(READY, hips=(-0.08, 0.03, -0.08), hips_rot=(-2.0, -8.0, -16.0), spine=(-4.0, -12.0, -12.0), head=(2.0, -14.0, -18.0),
               clav_l=(0.0, -12.0, 0.0), grip=(-0.66, -0.05, 1.05), blade=(-0.7, -0.55, 0.45), edge=(0.2, -0.5, -0.84),
               elbow_r=(-0.8, 0.4, -0.3), hand_l=(0.62, -0.1, 1.42), hand_l_dir=(0.7, -0.2, 0.6), hand_l_up=(0.0, -1.0, 0.0),
               fingers_l=0.05),
           r=flat("R", *R_FOOT), l=toe("L", *L_FOOT, 24.0))
_hl2 = mod(_hl, hips=(-0.09, 0.03, -0.1), spine=(-2.0, -11.0, -10.0), head=(0.0, -10.0, -12.0))
_hl_rec = feet(mod(READY, hips=(-0.02, 0.01, -0.12), hips_rot=(4.0, -2.0, 10.0), spine=(9.0, -2.0, -9.0), head=(-9.0, -2.0, -6.0),
                   **_arm_back(_hl2, 0.4)),
               r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))
add("HitLeft", 11, [(0, READY, "lin"), (1, _hl, "snap"), (3, _hl2, "lin"), (6, _hl_rec, "sine"), (11, READY, "sine")],
    timing={"impact": 1, "slide_ok": True},
    notes="golpe desde su izquierda: se dobla y gira a su derecha, la cabeza latiguea a la derecha; guardia en 0.37 s")
# desde su derecha: el espejo, con la katana empujada hacia arriba y adentro (le pegaron del lado del arma) y el peso en el
# pie izquierdo (el derecho en punta)
_hr = feet(mod(READY, hips=(0.08, 0.03, -0.08), hips_rot=(-2.0, 8.0, 16.0), spine=(-4.0, 12.0, 12.0), head=(2.0, 14.0, 18.0),
               clav_r=(0.0, 12.0, 0.0), grip=(-0.45, -0.25, 1.3), blade=(-0.2, -0.75, 0.63), edge=(0.0, -0.64, -0.77),
               elbow_r=(-0.8, 0.3, -0.4), hand_l=(0.6, 0.05, 1.18), hand_l_dir=(0.8, 0.2, -0.3), hand_l_up=(0.0, 0.0, 1.0),
               fingers_l=0.1),
           r=toe("R", *R_FOOT, 24.0), l=flat("L", *L_FOOT))
_hr2 = mod(_hr, hips=(0.09, 0.03, -0.1), spine=(-2.0, 11.0, 13.0), head=(0.0, 10.0, 14.0))
_hr_rec = feet(mod(READY, hips=(0.02, 0.01, -0.12), hips_rot=(4.0, 2.0, 16.0), spine=(9.0, 2.0, -7.0), head=(-9.0, 2.0, -2.0)),
               r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))
add("HitRight", 11, [(0, READY, "lin"), (1, _hr, "snap"), (3, _hr2, "lin"), (6, _hr_rec, "sine"), (11, READY, "sine")],
    timing={"impact": 1, "slide_ok": True},
    notes="golpe desde su derecha: se dobla y gira a su izquierda, la katana se va arriba; guardia en 0.37 s")
_hh = mod(_hit, hips=(0.0, 0.16, -0.06), hips_rot=(-20.0, 0.0, 10.0), spine=(-18.0, 0.0, 8.0), head=(14.0, 6.0, 14.0),
          grip=(-0.62, 0.05, 1.25), blade=(-0.4, -0.7, 0.6), hand_l=(0.6, 0.2, 1.42))
# cae en tres apoyos: los dos pies (sobre las huellas de la guardia: después no se arrastran) y la mano izquierda en
# el piso, agachado (se lee "me voltearon")
_hh_land = feet(mod(READY, hips=(0.0, 0.16, -0.3), hips_rot=(24.0, 0.0, 10.0), spine=(18.0, 0.0, 0.0), head=(-20.0, 0.0, 0.0),
                    grip=(-0.62, -0.05, 0.85), blade=(-0.6, 0.2, 0.77), edge=(-0.6, -0.5, -0.6), hand_l=(0.42, -0.5, 0.46),
                    hand_l_dir=(0.1, -0.8, -0.6), hand_l_up=(0.0, 0.0, 1.0), elbow_l=(0.8, 0.2, 0.4), fingers_l=0.0),
                r=flat("R", *R_FOOT), l=toe("L", *L_FOOT, 30.0))
_hh_land2 = mod(_hh_land, hips=(0.0, 0.17, -0.32), hand_l=(0.42, -0.5, 0.45))
# en el aire los brazos ya van hacia la caída (un 35 %) y el pecho empieza a volver (un 30 %; como en Blocked): bajando
# enteros entre f3 y f6 el codo izquierdo, que pasa de abajo a arriba para apoyar la mano, daba vuelta 106° en un cuadro y
# el hombro se corría 25 cm
_hh_air = feet(mod(_hh, lift=0.16, hips=(0.0, 0.14, -0.06),
                   **{k: v for k, v in inter(mod(_hh, hips_rot=(-14.0, 0.0, 6.0)), _hh_land, 0.3).items() if k in _KN_CHEST},
                   **{k: v for k, v in inter(_hh, _hh_land, 0.35).items() if k in _KN_ARMS}),
               r=air(-0.24, -0.3, 0.45, -20.0, 6.0), l=air(0.3, 0.05, 0.4, -8.0, 30.0))
# (la mano izquierda baja al piso por delante, sin atraso: el cuerpo cae adelante más rápido que ella y con la mano
# detrás el hombro le caía encima, el codo se plegaba entero en f4 y se volvía a estirar en f5, 89° por cuadro)
add("HitHeavy", 20, [(0, READY, "lin"), (1, _hh, "snap"), (3, _hh_air, "out"),
                     (4, mod(inter(_hh_air, _hh_land, 0.4), hand_l=(0.48, -0.25, 0.9)), "inout"),
                     (5, feet(inter(_hh_air, _hh_land, 0.75), r=hover("R", R_FOOT[0], R_FOOT[1], R_FOOT[2], 0.05),
                              l=hover("L", L_FOOT[0], L_FOOT[1], L_FOOT[2], 0.07)), "sine"),
                     (6, _hh_land, "in2"), (11, _hh_land2, "sine"), (20, READY, "sine")],
    lag=mod(LEAD, hand_l=0.0),
    timing={"impact": 1, "slide_ok": True},
    notes="golpe pesado: lo levanta, cae en tres apoyos con la mano en el piso y se para (0.65 s)")

# =========================================================================== muerte
# Con peso (pedido del usuario: la de antes se doblaba sin peso y la katana quedaba parada en el aire): el golpe lo
# echa atrás (f2), el pie derecho da un paso para no caerse (f5-f8) y el peso le vuelve adelante; se le va la
# rodilla izquierda y cae de golpe sobre ella (f17, acelerando: la cadera rebota apenas en f19 y la cabeza llega un
# cuadro tarde). Arrodillado, el puño izquierdo se apoya en el piso y la katana cuelga con la punta apoyada; respira
# pesado y tiembla (f19-f28). La mano se abre (f29): la katana se le cae de costado, pega en el piso y rebota
# (f31-f37) mientras el brazo izquierdo cede y se va adelante y de costado (pecho en el piso en f35, la cabeza en
# f36, rebote en f38); queda tendido. Ningún pie se arrastra. Die lo arranca en cámara lenta (x0.25 1.6 s): el
# golpe y el paso se ven lentos, la caída a velocidad normal
# (el brazo libre se abre un tercio de lo que se abre en el golpe pesado: entero, la mano daba 97° en el primer cuadro de
# la muerte, que se ve de cerca. La mano queda cerca del pecho que se echa atrás: donde la dejaba el tercio, el brazo se
# estiraba entero, no llegaba por 3 cm y el codo se volvía a doblar de golpe al volver el peso adelante)
_d_snap = mod(_hh, hips=(0.0, 0.14, -0.06), head=(16.0, 6.0, 12.0), kat_free=0.0, hand_l=(0.4, -0.05, 1.18),
              **{k: v for k, v in inter(READY, _hh, 0.35).items() if k in ("hand_l_dir", "hand_l_up", "elbow_l", "fingers_l")})
_d_stag = feet(mod(READY, hips=(0.0, 0.08, -0.16), hips_rot=(16.0, 0.0, -6.0), spine=(20.0, 0.0, -4.0), head=(14.0, -4.0, -6.0),
                   clav_r=(0.0, -6.0, 0.0), clav_l=(0.0, 6.0, 0.0), grip=(-0.5, -0.22, 0.86), blade=(-0.45, -0.78, -0.42),
                   edge=(0.1, -0.45, -0.89), elbow_r=(-0.6, 0.3, -0.7), hand_l=(0.3, -0.25, 0.95), hand_l_dir=(0.0, -0.4, -0.9),
                   hand_l_up=(1.0, 0.0, 0.0), fingers_l=0.5, kat_free=0.0),
               r=flat("R", -0.24, -0.3, 4.0), l=toe("L", *L_FOOT, 20.0))
# una rodilla en el piso (la izquierda), el puño izquierdo apoyado adelante; la katana cuelga de la mano con la punta
# en el piso a su derecha. Los brazos en el espacio del pecho (cuelgan con el tronco vencido)
_D_KNEE_L = plant("L", 0.28, 0.5, 70.0, 20.0, "toe")
_d_knee = feet(mod(READY, hips=(0.0, 0.12, -0.36), hips_rot=(20.0, 0.0, -4.0), spine=(24.0, 0.0, -4.0), head=(22.0, -6.0, -4.0),
                   clav_r=(0.0, -8.0, 0.0), clav_l=(0.0, 8.0, 0.0), arm_space=1.0, grip=(-0.5, -0.32, 0.98),
                   blade=(-0.35, -0.7, -0.62), edge=(0.2, -0.55, -0.81), elbow_r=(-0.6, 0.4, -0.6), hand_l=(0.4, -0.5, 0.82),
                   hand_l_dir=(0.05, -0.3, -0.95), hand_l_up=(0.0, -1.0, 0.0), elbow_l=(0.8, 0.4, -0.3), fingers_l=1.0,
                   knee_l=(0.2, -0.6, -0.8), kat_free=0.0),
               r=flat("R", -0.24, -0.3, 4.0), l=_D_KNEE_L)
_d_knee_up = mod(_d_knee, hips=(0.0, 0.12, -0.335), head=(18.0, -6.0, -4.0), spine=(22.0, 0.0, -4.0))
_d_knee_b = mod(_d_knee, breath=1.0, hips=(0.0, 0.12, -0.35), head=(25.0, -6.0, -2.0), tremble=1.0)
_d_knee_b2 = mod(_d_knee, breath=0.4, hips=(0.0, 0.12, -0.355), head=(23.0, -6.0, -6.0), tremble=1.4)
# la mano se abre: la katana y la mano arrancan donde las tenía en f28, la katana se va de costado sobre su lomo y cae
# plana. Desde acá los brazos van en el espacio del transform (los valores son los de las poses de antes en el del
# pecho, pasados con Solver.body): la caída los lleva al piso adelante, en ese espacio, y mezclando los dos espacios
# entre f31 y f35 la mano izquierda caía en un punto que no era ninguno y el húmero giraba 82-109° en un cuadro. El
# cambio de espacio queda entre f24 y f28, con el pecho quieto
_d_let = mod(_d_knee_b2, arm_space=0.0, kat_free=0.0, kat_pos=(-0.532, -0.139, 0.407), kat_blade=(-0.964, -0.096, -0.248),
             kat_edge=(0.228, 0.185, -0.956), grip=(-0.538, -0.133, 0.402), blade=(-0.381, -0.039, -0.924),
             edge=(0.196, 0.124, -0.973), elbow_r=(-0.537, 0.828, -0.162), hand_l=(0.344, -0.276, 0.141),
             hand_l_dir=(0.086, 0.421, -0.903), hand_l_up=(-0.115, -0.723, -0.681), elbow_l=(0.912, 0.408, 0.036),
             hand_r=(-0.467, -0.134, 0.535), hand_r_dir=(-0.441, 0.136, -0.887), hand_r_up=(-0.051, 0.983, 0.175))
# el pecho se vence: el puño izquierdo todavía en el piso debajo del hombro, la derecha suelta
_d_sink = feet(mod(_d_knee, hips=(0.04, 0.1, -0.38), hips_rot=(30.0, 12.0, -2.0), spine=(26.0, 4.0, -2.0), head=(26.0, 4.0, 0.0),
                   arm_space=0.0, grip=(-0.478, -0.193, 0.446), blade=(-0.595, 0.143, -0.791), edge=(-0.055, 0.368, -0.928),
                   elbow_r=(-0.591, 0.787, 0.179), hand_l=(0.364, -0.075, 0.14), hand_l_dir=(-0.154, 0.628, -0.763),
                   hand_l_up=(-0.252, -0.55, -0.796), elbow_l=(0.889, 0.293, -0.352), kat_free=1.0, kat_pos=(-0.58, -0.16, 0.24),
                   kat_blade=(-0.98, -0.13, -0.06), kat_edge=(0.05, 0.75, -0.66), hand_r=(-0.394, -0.201, 0.45),
                   hand_r_dir=(-0.544, 0.235, -0.806), hand_r_up=(-0.154, 0.875, 0.46)),
               r=flat("R", -0.24, -0.3, 4.0), l=_D_KNEE_L)
# los brazos ceden: el pecho y la mejilla pegan en el piso (f35), la cabeza y los hombros rebotan apenas (f38) y queda
# TENDIDO boca abajo y un poco de costado, como el prólogo (WakeUp: PRONE): la cadera a 12 cm, la cabeza de lado sobre el
# piso, las piernas estiradas atrás con el empeine en el piso (el pie derecho, que estaba adelante, va atrás en el aire
# mientras cae; las rodillas no se arrastran). Las manos flojas de canto en el piso a los costados de la cabeza (con la
# palma plana la muñeca quedaba 60° doblada hacia el dorso) y la katana plana
# a su derecha. Antes terminaba en cuatro patas con la cabeza levantada: desde la cámara del juego parecía gatear
_D_DY = -0.55                     # PRONE (cadera 0.62 atrás del transform) corrido hasta donde cae desde la rodilla
_d_fall = feet(mod(READY, hips=(0.04, 0.62 + _D_DY, -0.26), hips_rot=(78.0, 14.0, 4.0), spine=(2.0, 4.0, 0.0), head=(-28.0, 8.0, 52.0),
                   arm_space=0.0, kat_free=1.0, kat_pos=(-0.62, -0.2, 0.06), kat_blade=(-0.97, -0.22, 0.0), kat_edge=(-0.22, 0.97, 0.0),
                   hand_r=(-0.62, -0.3 + _D_DY, 0.16), hand_r_dir=(-0.15, -0.9, -0.4), hand_r_up=(-0.95, 0.0, 0.3), fingers_r=0.5,
                   hand_l=(0.55, -0.7 + _D_DY, 0.16), hand_l_dir=(0.2, -0.9, -0.4), hand_l_up=(0.95, 0.0, 0.3), elbow_l=(0.8, 0.2, 0.3),
                   elbow_r=(-0.8, 0.4, 0.2), fingers_l=0.3, wrist_l_open=0.3, wrist_r_open=0.3, knee_r=(-0.1, -0.6, -0.8),
                   knee_l=(0.1, -0.6, -0.8)),
               r=((-0.22, 1.07 + _D_DY, 0.15), (30.0, 180.0, -186.0)), l=air(0.22, 1.09 + _D_DY, 0.15, 152.0, 6.0))
_d_bounce = feet(mod(_d_fall, hips=(0.04, 0.62 + _D_DY, -0.27), hips_rot=(82.0, 16.0, 4.0), head=(-32.0, 8.0, 60.0),
                     kat_pos=(-0.63, -0.21, 0.1), kat_blade=(-0.95, -0.22, 0.2), kat_edge=(-0.22, 0.95, 0.2)),
                 r=((-0.22, 1.07 + _D_DY, 0.14), (24.0, 180.0, -186.0)), l=air(0.22, 1.09 + _D_DY, 0.14, 158.0, 6.0))
# tendido: se asienta (la cadera baja, la cabeza termina de girar de costado)
_d_rest = feet(mod(_d_fall, hips=(0.05, 0.62 + _D_DY, -0.31), hips_rot=(86.0, 16.0, 4.0), spine=(4.0, 4.0, 0.0), head=(-36.0, 8.0, 68.0),
                   hand_r=(-0.62, -0.28 + _D_DY, 0.14), hand_l=(0.55, -0.72 + _D_DY, 0.14), fingers_l=0.55, fingers_r=0.55),
               r=((-0.22, 1.07 + _D_DY, 0.13), (20.0, 180.0, -186.0)), l=air(0.22, 1.09 + _D_DY, 0.13, 162.0, 6.0))


def _d_knees(kr, kl, pole_r=None, guide_r=0.0):
    """Las rodillas guiadas mientras cae (ver knee_guide en kaito_rig): las piernas se estiran atrás entre f31 y f41. La
    derecha (adelante) se abre hacia afuera y el pie da la vuelta por el costado hasta quedar con el empeine en el piso
    (como al arrodillarse en PrayIncense: el pie del tendido escrito con la vuelta de 180°); la izquierda se corre de
    rodillas por el piso. Antes las dos se estiraban de un cuadro al otro (f34-35: las rodillas 19-29 cm y los pies 34-65 cm)."""
    out = dict(knee_at_r=kr, knee_at_l=kl, knee_guide_r=1.0, knee_guide_l=1.0)
    # pole_r: la rodilla derecha por dirección (de adelante a abajo) con el punto guiado apagándose (guide_r): mientras la
    # pierna se estira atrás el tobillo pasa por debajo de la cadera y un punto guiado cerca de la recta cadera-tobillo
    # hacía dar vuelta la rodilla de un cuadro al otro (137°)
    if pole_r is not None:
        out.update(knee_r=pole_r, knee_guide_r=guide_r)
    return out


# (las piernas a ritmo parejo mientras el cuerpo cae acelerando: con la curva del cuerpo se juntaba todo en un cuadro)
_D_LEGS_LIN = {ch: "lin" for ch in ("foot_r", "foot_l", "foot_r_rot", "foot_l_rot", "knee_at_r", "knee_at_l")}
_D_HAND_LIN = {ch: "lin" for ch in ("hand_l", "hand_l_dir", "hand_l_up", "elbow_l")}


add("Death", 48, [(0, mod(READY, kat_free=0.0), "lin"), (2, _d_snap, "out2"),
                  (5, feet(inter(_d_snap, _d_stag, 0.5), r=lifted("R", -0.23, -0.24, 0.07, -6.0, 5.0), l=toe("L", *L_FOOT, 20.0)), "out"),
                  (8, _d_stag, "inout"),
                  (13, feet(inter(_d_stag, _d_knee, 0.4), l=lifted("L", 0.29, 0.4, 0.07, 62.0, 22.0)), "inout"),
                  (17, _d_knee, "in2"), (19, _d_knee_up, "out"), (24, _d_knee_b, "sine"), (28, _d_let, "sine"),
                  (31, mod(_d_sink, **_d_knees((-0.17, -0.23, 0.48), (0.44, -0.1, 0.24))), "in2"),
                  # (el pecho cae acelerando parejo, como en caída libre: a f33 un 38 % y el resto en dos cuadros; con "in"
                  # dos veces el 40 % de la caída entraba en f32-f33 y las piernas giraban 71° en ese cuadro)
                  # (el pie derecho da la vuelta en doce cuadros parejos, ~16° por cuadro, y casi no se levanta: termina de
                  # estirarse atrás después de que el pecho pega en el piso (f35-f44, la pierna sigue al cuerpo). Girado 35°
                  # ya en f33 el tobillo tenía que subir 8 cm para que la suela no entre en el piso, la pierna se plegaba y la
                  # rodilla saltaba arriba y abajo, 71° de tibia en un cuadro. La mano izquierda se va adelante y afuera por
                  # el piso mientras el brazo cede, floja: sigue al antebrazo como una mano muerta y recién en f39 apoya de
                  # canto; con su orientación autorada daba 48-52° en un cuadro. Se desliza a ritmo parejo, no con la caída
                  # del pecho: con su curva viajaba 33 cm en f32-f33 y el codo se plegaba 57° en ese cuadro)
                  (33, feet(mod(inter(_d_sink, _d_fall, 0.38), hand_l=(0.46, -0.36, 0.16), hand_l_relax=0.5, **_d_knees((-0.3, -0.2, 0.44), (0.44, -0.06, 0.22),
                                                                                                     (-0.12, -0.95, -0.2), 0.4),
                                **{k: v for k, v in inter(_d_sink, _d_fall, 0.35).items() if k in ("hand_l_dir", "hand_l_up", "elbow_l")}),
                            r=swung("R", -0.3, -0.24, 0.2, (2.0, 14.0, -14.0)), l=swung("L", 0.42, 0.1, 0.47, (78.0, 0.0, 20.0))),
                  "in2", {**_D_LEGS_LIN, **_D_HAND_LIN}),
                  (35, feet(mod(_d_fall, **_d_knees((-0.34, -0.06, 0.3), (0.34, 0.08, 0.18), (-0.15, -0.8, -0.6)), hand_l=(0.53, -0.76, 0.18), hand_l_relax=0.5,
                                **{k: v for k, v in inter(_d_sink, _d_fall, 0.55).items() if k in ("hand_l_dir", "hand_l_up", "elbow_l")}),
                            r=swung("R", -0.38, -0.1, 0.2, (5.0, 42.0, -45.0)), l=swung("L", 0.3, 0.34, 0.36, (110.0, 0.0, 12.0))),
                  "lin", _D_LEGS_LIN),
                  # (el brazo izquierdo termina de acomodarse en el piso después de que pega el pecho, f35-f39)
                  (37, feet(mod(inter(_d_fall, _d_bounce, 0.7), **_d_knees((-0.3, 0.05, 0.24), (0.25, 0.2, 0.15), (-0.15, -0.4, -0.9)),
                                hand_l=(0.55, -1.06, 0.17), hand_l_relax=0.25,
                                **{k: v for k, v in inter(_d_sink, _d_fall, 0.82).items() if k in ("hand_l_dir", "hand_l_up", "elbow_l")}),
                            r=swung("R", -0.43, 0.08, 0.2, (9.0, 84.0, -92.0)), l=swung("L", 0.24, 0.46, 0.23, (140.0, 0.0, 7.0))),
                  "out", {**_D_LEGS_LIN, **_D_HAND_LIN}),
                  (39, feet(mod(_d_bounce, **_d_knees((-0.25, 0.16, 0.22), (0.23, 0.24, 0.14), (-0.1, 0.0, -1.0))),
                            r=swung("R", -0.38, 0.28, 0.17, (13.0, 125.0, -130.0)), l=((0.22, 0.53, 0.16), (155.0, 0.0, 6.0))),
                  "sine", _D_LEGS_LIN),
                  (41, feet(mod(_d_rest, hips=(0.05, 0.62 + _D_DY, -0.29), **_d_knees((-0.19, 0.23, 0.23), (0.22, 0.25, 0.14), (-0.1, -0.3, -0.95))),
                            r=((-0.3, 0.42, 0.15), (17.0, 158.0, -164.0))), "sine", _D_LEGS_LIN),
                  (44, mod(_d_rest, hips=(0.05, 0.62 + _D_DY, -0.3)), "sine", _D_LEGS_LIN),
                  (48, _d_rest, "sine")],
    # (la mano libre sin atraso y el giro de la cadera sin adelanto, como en el golpe pesado: el pecho se iba adelante antes
    # que la mano y el hombro le caía encima, el codo se plegaba 54° en f5-f6. La cadera sí se adelanta: sin eso, al caer
    # la tibia derecha giraba 46° en f33-f34)
    lag=mod(LEAD, hand_l=0.0, hips_rot=0.0),
    # (el golpe entra en f1, como en Hit y HitHeavy: el sacudón de f0-f1 es el impacto)
    timing={"impact": 1, "knee": 17, "release": 29, "ground": 35, "slide_ok": True, "slow": True},
    notes="el golpe lo echa atrás, un paso, cae de golpe sobre una rodilla con el puño en el piso, respira; se le cae "
          "la katana, los brazos ceden y queda tendido boca abajo con la cabeza de costado (1.6 s; la cámara lenta de Die lo estira)")

# =========================================================================== remate (iai)
# El tajo cae en f54.4 (PlayerController.FinisherStrikeFrame: el juego lo teletransporta detrás del enemigo en ese
# instante). Antes: da un paso adelante con el pie derecho y se planta agachado, girado, con la katana baja atrás a
# su derecha (wakigamae: desde arriba es una cola larga que sale por detrás; Kaito tiene brazos de 30 cm y no
# llega a desenvainar desde la cadera izquierda) y la palma izquierda apuntando al enemigo; espera respirando y
# temblando cada vez más y se comprime en f50-54. En f55 ya está del otro lado (el teletransporte: f54-f55 es un
# corte, los pies cambian de lugar), de espaldas al enemigo, estirado en una zancada baja con la hoja afuera a su
# derecha, la hoja arriba. ZANSHIN (pedido del usuario: "un segundo de Kaito en la pose final"): el impulso del corte
# lo lleva un poco más abajo y la hoja baja por su costado (f55-f58), se asienta en f64 con el brazo estirado a su
# derecha, la hoja baja y atrás y el puño izquierdo cargado en la cadera (donde iría la vaina), inspira, en f77-f81 mira
# por encima del hombro derecho hacia el que cortó y en f86 vuelve la vista adelante. El cinemático toca ese tramo a
# velocidad 1 (f55-f86: ~1 s con la cámara en ZanshinShot); el corto lo corta a los 0.2 s y salta a f86. Las manos de
# estas poses salen de la búsqueda de muñecas cómodas (el brazo estirado al costado con la hoja atrás pedía 25° de
# muñeca de más). Desde f86 (FinisherHoldEndFrame) es un gesto que el stick o
# un ataque cortan: chiburi, el pie derecho vuelve con un paso y en f98 está en la guardia. El pie izquierdo no se
# mueve de su huella de la guardia en todo el clip (gira sobre la punta)
IAI = feet(mod(READY, hips=(0.0, 0.1, -0.3), hips_rot=(12.0, 0.0, -28.0), spine=(10.0, 0.0, -8.0), head=(-14.0, 0.0, 30.0),
               clav_r=(0.0, 4.0, 0.0), grip=(-0.44, 0.2, 0.9), blade=(-0.46, 0.87, -0.16), edge=perp((-0.46, 0.87, -0.16), (0.0, 0.35, -0.94)),
               elbow_r=(-0.2, 0.5, 0.8), hand_l=(0.22, -0.48, 1.3), hand_l_dir=(-0.1, -0.5, 0.86), hand_l_up=(0.0, 1.0, 0.3),
               elbow_l=(0.8, 0.2, -0.5), fingers_l=0.0, knee_l=(0.6, -0.8, 0.0)),
           r=flat("R", -0.3, -0.35, 10.0), l=flat("L", *L_FOOT))
# de la guardia a la espalda la hoja pasa por abajo a su derecha y el codo sube: a mitad de camino apunta afuera (la
# mano todavía supinada, como en la guardia) y un cuadro después atrás y abajo (ya pronada, el codo arriba). Por arriba
# (hoja atrás y alta) no hay muñeca que llegue, y en línea recta de una pose a la otra el recorte la daba vuelta
# 150-170° en un cuadro justo al plantarse, con la cámara del remate encima
_step_mid = inter(READY, IAI, 0.5)
_step_in = feet(mod(_step_mid, grip=(-0.38, -0.16, 1.04), blade=(-0.96, -0.2, -0.08), edge=perp((-0.96, -0.2, -0.08), _step_mid["edge"]),
                    elbow_r=(-0.2, 0.5, 0.8)),
                r=lifted("R", -0.27, -0.27, 0.08, -6.0, 8.0), l=flat("L", *L_FOOT))
_step_back = feet(mod(inter(READY, IAI, 0.8), grip=(-0.38, 0.04, 0.92), blade=(-0.78, 0.47, -0.42),
                      edge=perp((-0.78, 0.47, -0.42), IAI["edge"]), elbow_r=(-0.2, 0.5, 0.8)),
                  r=hover("R", -0.3, -0.35, 10.0, 0.04), l=flat("L", *L_FOOT))
_iai_b = mod(IAI, breath=1.0, hips=(0.0, 0.1, -0.31), head=(-15.0, 0.0, 30.0), tremble=0.3)
_iai_deep = mod(IAI, hips=(0.0, 0.12, -0.35), hips_rot=(18.0, 0.0, -30.0), head=(-18.0, 0.0, 30.0), tremble=1.0,
                grip=(-0.46, 0.18, 0.84), blade=(-0.44, 0.88, -0.2))
_iai_cmp = mod(IAI, hips=(0.0, 0.11, -0.36), hips_rot=(20.0, 0.0, -30.0), spine=(16.0, 0.0, -10.0), head=(-22.0, 0.0, 30.0),
               tremble=1.6, grip=(-0.45, 0.18, 0.86), blade=(-0.5, 0.85, -0.17), edge=perp((-0.5, 0.85, -0.17), (0.59, 0.51, -0.63)),
               hand_l=(0.2, -0.52, 1.24))
# llega: la hoja recién pasó y sigue arriba y afuera a su derecha (el final del arco); el brazo izquierdo todavía
# abierto atrás por el envión, con la mano floja (sigue al antebrazo: el puño se arma recién en la cadera, f58-f64; con
# la mano autorada abierta atrás y el puño adelante en la cadera, la muñeca daba 80° en un cuadro dentro del zanshin)
AFTER_CUT = feet(mod(READY, hips=(0.0, -0.25, -0.32), hips_rot=(16.0, 0.0, -32.0), spine=(12.0, 0.0, -18.0), head=(-8.0, 0.0, 14.0),
                     clav_r=(0.0, 12.0, 0.0), grip=(-1.02, 0.0, 1.14), blade=(-0.88, -0.4, -0.25),
                     # (la mano libre atrás a casi todo el brazo: más lejos el brazo se estiraba de golpe al llegar)
                     edge=perp((-0.88, -0.4, -0.25), (0.2, 1.0, 0.4)), elbow_r=(-0.7, 0.6, 0.3), hand_l=(0.36, -0.08, 1.0),
                     hand_l_dir=(0.6, 0.75, -0.2), hand_l_up=(0.0, 0.0, 1.0), elbow_l=(0.6, 0.6, -0.3), fingers_l=0.05,
                     hand_l_relax=1.0),
                 r=flat("R", -0.28, -0.64, 4.0), l=toe("L", *L_FOOT, 30.0))
# el envión: la cadera baja un poco más y la hoja sigue hacia atrás y abajo
_zan_over = mod(AFTER_CUT, hips=(0.0, -0.27, -0.36), hips_rot=(18.0, 0.0, -28.0), spine=(13.0, 0.0, -15.0), head=(-11.0, 0.0, 16.0),
                grip=(-1.06, 0.08, 1.08), blade=(-0.86, -0.35, -0.38), edge=perp((-0.86, -0.35, -0.38), (0.2, 1.0, 0.4)),
                elbow_r=(-0.7, 0.6, 0.3),
                hand_l=(0.34, 0.04, 0.82), hand_l_dir=(0.05, -0.9, -0.3), hand_l_up=(0.3, 0.0, -0.95), elbow_l=(0.6, 0.8, -0.2),
                fingers_l=0.37, hand_l_relax=1.0)
# asentado: el brazo derecho estirado a su costado, la hoja baja y atrás (desde arriba, una raya larga que sale de la
# silueta por la derecha y hacia atrás), el puño izquierdo cerrado en la cadera, el pecho abierto y la vista adelante. El
# puño flojo (sigue al antebrazo): el puño autorado no entra en lo cómodo con el codo del zanshin y el recorte lo
# pasaba de un tope de doblez al otro (80° en un cuadro, dos veces en la pose quieta). El brazo derecho casi entero: con
# la mano a -1.0 el codo llegaba al tope de la IK suave y al girar el pecho la mano quedaba 2 cm corta
ZANSHIN = mod(_zan_over, hips=(0.0, -0.26, -0.35), hips_rot=(16.0, 0.0, -26.0), spine=(11.0, 0.0, -14.0), head=(-10.0, 0.0, 16.0),
              clav_r=(0.0, 10.0, 0.0), grip=(-0.97, 0.16, 1.04), blade=(-0.86, -0.12, -0.5),
              edge=perp((-0.86, -0.12, -0.5), (0.3, 1.0, 0.3)), elbow_r=(-0.7, 0.6, 0.3), hand_l=(0.33, 0.02, 0.77), hand_l_dir=(0.0, -1.0, 0.05),
              hand_l_up=(0.15, 0.0, -1.0), elbow_l=(0.6, 0.8, -0.2), fingers_l=1.0, hand_l_relax=1.0)
_zan_in = mod(ZANSHIN, breath=1.0, hips=(0.0, -0.26, -0.345), head=(-11.0, 0.0, 15.0))
# exhala y mira por encima del hombro derecho hacia el que cortó (la hoja no se mueve)
_zan_look = mod(ZANSHIN, breath=0.2, hips=(0.0, -0.26, -0.355), spine=(10.0, 0.0, -17.0), head=(-6.0, -4.0, -28.0))
# ...y vuelve la vista adelante antes del chiburi (el corto salta acá desde f71 con 0.12 s de fundido: la cabeza tiene
# que estar donde estaba)
ZAN_END = mod(_zan_look, breath=0.0, spine=(11.0, 0.0, -14.0), head=(-10.0, 0.0, 15.0))
# chiburi: la cabeza vuelve adelante, la hoja sube adelante y baja de un latigazo a su derecha
_chi_up = mod(ZAN_END, head=(-8.0, 0.0, 6.0), grip=(-0.74, -0.36, 1.3), blade=(-0.53, -0.2, 0.82), edge=(-0.25, -0.88, -0.38))
_chi_snap = mod(ZAN_END, hips=(0.0, -0.24, -0.34), head=(-9.0, 0.0, 8.0), grip=(-0.75, -0.25, 0.89), blade=(-0.64, -0.73, -0.24),
                edge=(0.2, 0.14, -0.97))
_CHI_RISE = {ch: "lin" for ch in ("grip", "blade", "edge", "elbow_r")}
# vuelta a la guardia: el pie derecho se levanta de la zancada y apoya en su huella; el izquierdo baja el talón
_step_out = feet(inter(_chi_snap, READY, 0.45), r=lifted("R", -0.25, -0.4, 0.08, -8.0, 5.0), l=toe("L", *L_FOOT, 18.0))
FINISHER_HOLD_END = 86          # PlayerController.FinisherHoldEndFrame
FINISHER_SKIP_FROM = 71         # el corto salta de acá a FINISHER_HOLD_END (0.2 s después del tajo a x2.8)
add("Finisher", 106, [
    (0, READY, "sine"), (4, _step_in, "inout"), (8, _step_back, "inout"), (12, IAI, "inout"), (22, _iai_b, "sine"), (36, mod(IAI, tremble=0.6), "sine"),
    # (el puño izquierdo se cierra parejo de f55 a f64: en la pose quieta, cerrándose en 6 cuadros con curva, la punta
    # de los dedos giraba 27° por cuadro y se veía como un tic. El brazo izquierdo baja parejo a la cadera en f55-f58: con
    # la curva del cuerpo la mitad del viaje caía en el primer cuadro después del corte y el codo se daba vuelta, la mano
    # 35° en un cuadro con la cámara encima)
    (50, _iai_deep, "sine"), (54, _iai_cmp, "in2"), (55, AFTER_CUT, "hold"),
    (58, _zan_over, "out", {k: "lin" for k in ("fingers_l", "hand_l", "hand_l_dir", "hand_l_up", "elbow_l", "hand_l_relax")}),
    (64, ZANSHIN, "sine", {"fingers_l": "lin"}),
    (72, _zan_in, "sine"), (77, _zan_look, "inout"), (81, mod(_zan_look, head=(-6.0, -4.0, -31.0)), "sine"),
    # chiburi: la hoja sube parejo (con "inout" el codo se doblaba 66° en el cuadro del medio) y baja de un latigazo seco en
    # un cuadro (f89-f90: el tirón es el gesto, 'snap_ok'; repartido en tres se volvía un barrido sin golpe)
    (FINISHER_HOLD_END, ZAN_END, "inout"), (89, _chi_up, "inout", _CHI_RISE),
    (91, _chi_snap, "snap"), (92, mod(_chi_snap, grip=(-0.75, -0.26, 0.9)), "lin"), (95, _step_out, "inout"),
    (98, READY, "in2"), (102, _breath, "sine"), (106, READY, "sine")],
    timing={"strike": 54, "zanshin": [55, FINISHER_HOLD_END], "hold": [55, FINISHER_HOLD_END], "skip": [FINISHER_SKIP_FROM, FINISHER_HOLD_END],
            "chiburi": [FINISHER_HOLD_END, 92], "guard": 98, "skid": [[54, 55]], "cut": [54.5], "snap_ok": [[89, 90]],
            # el cinemático toca la carga a x1.7 y el zanshin a x1; el corto (el de casi todos los enemigos) toca a x2.8 hasta
            # que salta del zanshin al chiburi 0.2 s después del tajo (f71.2: el paso f71-f72 se ve en parte; PlayerController
            # TryFinisher / TickFinisher). Desde el chiburi, en los dos, es un gesto a x1 (EndFinisher): a la velocidad del
            # remate el latigazo daba 83-114° por cuadro (x1.7) y 137-188° (x2.8)
            "play_speed": [[0, 55, 1.7]], "play_speed_fast": [[0, FINISHER_SKIP_FROM + 1, 2.8]]},
    events=[{"frame": 54, "fn": "Strike"}],
    notes="iai: cargado y temblando hasta f54, en f55 ya cortó y está del otro lado; zanshin hasta f86 (el cinemático lo "
          "toca a x1 con la cámara encima), chiburi, un paso y en f98 está en la guardia")

# =========================================================================== Corte del Viento (habilidad 1)
# PlayerController.TickWindSlash: 0.32 s de preparación (cámara sobre el hombro y cámara lenta), 0.16 s de viaje
# (9 m), los cortes aparecen 0.06 s después (f16.2), mientras él ya está quieto de espaldas a los cortados: el iaido.
# Prepara como el iai (con el mismo paso adelante), viaja en el aire en la pose del dash (f10-f14: el juego lo mueve a
# 56 m/s) y llega en el zanshin del remate (las mismas poses): se asienta y queda hasta f45 (WindSlashHoldEnd 1.5 s, con
# ZanshinShot de frente); de ahí en más es un gesto que se corta: chiburi, un paso atrás y la guardia (f57). La cadera
# sin adelanto: con él, en f14 ya bajaba a la zancada y las piernas no llegaban a los pies del dash
_ws_cmp = mod(_iai_cmp, tremble=1.2)
# llega en dos tiempos (f14 con los pies todavía en el aire arriba de sus huellas, f15 el zanshin): del vuelo a la zancada
# en un cuadro las manos daban 73° y las puntas de los pies barrían 24 cm junto al piso
# (la katana ya a un 60 % de su pose de llegada y la mano libre a un 25 %: con las dos al 40 % la katana daba 63° en el último
# cuadro y el codo izquierdo se estiraba 61° en el anterior)
_WS_ARM_R = ("grip", "blade", "edge", "elbow_r")
_WS_ARM_L = ("hand_l", "hand_l_dir", "hand_l_up", "elbow_l", "hand_l_relax", "fingers_l")
_ws_arrive = feet(mod(inter(_dash_b, AFTER_CUT, 0.4), **{k: v for k, v in inter(_dash_b, AFTER_CUT, 0.6).items() if k in _WS_ARM_R},
                      **{k: v for k, v in inter(_dash_b, AFTER_CUT, 0.25).items() if k in _WS_ARM_L}),
                  r=lifted("R", -0.28, -0.6, 0.07, 0.0, 4.0), l=lifted("L", L_FOOT[0], L_FOOT[1] + 0.04, 0.07, 24.0, L_FOOT[2]))
# Sale disparado en tres cuadros (f10-f12, ya en el aire): el cuerpo y los brazos pasan parejos de la carga del iai al vuelo
# del dash. En uno, la hoja barría 110-170° (el juego lo mueve a 56 m/s, pero los brazos se ven). La mano libre da la vuelta
# por afuera, a su izquierda, floja: derecho de adelante del pecho a atrás pasaba por el hombro, el brazo se plegaba entero y
# el codo daba vuelta 120° en un cuadro


def _ws_launch(u, hand):
    """Cuadro del arranque: la fracción u de la carga al vuelo, la mano libre en 'hand'; la cadera, las rodillas y los pies
    ya en el vuelo. Con la cadera todavía baja en la carga y los pies ya arriba, las piernas se desplegaban en el aire de
    un cuadro al otro (90° de muslo en f10-f11): el salto del cuerpo queda en el cuadro del arranque ('burst') y las dos
    manos, escritas respecto de la cadera que pasa, suben con ella lo que le falta a la cadera recorrer."""
    d = [(1.0 - u) * (a - b) for a, b in zip(_dash["hips"], _ws_cmp["hips"])]
    q = inter(_ws_cmp, _dash, u)
    return feet(mod(q, hand_l_relax=1.0, hand_l=tuple(h + x for h, x in zip(hand, d)), grip=tuple(h + x for h, x in zip(q["grip"], d)),
                    **{k: _dash[k] for k in ("hips", "knee_r", "knee_l")}),
                r=(_dash["foot_r"], _dash["foot_r_rot"]), l=(_dash["foot_l"], _dash["foot_l_rot"]))

add("WindSlash", 58, [
    (0, READY, "sine"), (2, _step_in, "sine"), (4, _step_back, "sine"), (6, IAI, "inout"), (8, _iai_deep, "sine"), (9, _ws_cmp, "in2"),
    (10, _ws_launch(0.25, (0.4, -0.52, 1.18)), "lin"), (11, _ws_launch(0.5, (0.5, -0.38, 1.08)), "lin"),
    (12, _ws_launch(0.75, (0.5, -0.22, 0.98)), "lin"), (13, _dash, "lin"),
    # (el puño izquierdo se cierra parejo de f15 a f24, como en el remate: con la curva de la cadera los dedos giraban
    # 24-38° por cuadro en la pose quieta)
    (14, _ws_arrive, "sine"), (15, AFTER_CUT, "out"), (18, _zan_over, "out", {"fingers_l": "lin"}),
    (24, ZANSHIN, "sine", {"fingers_l": "lin"}), (30, _zan_in, "sine"),
    (35, _zan_look, "inout"), (40, mod(_zan_look, head=(-6.0, -4.0, -31.0)), "sine"), (45, ZAN_END, "inout"), (48, _chi_up, "inout", _CHI_RISE),
    (50, _chi_snap, "snap"), (51, mod(_chi_snap, grip=(-0.75, -0.26, 0.9)), "lin"), (54, _step_out, "inout"),
    # (a la guardia parejo, salvo el pie que apoya: con la curva del pie todo el cuerpo llegaba en el último cuadro y el
    # brazo izquierdo daba 62° ahí)
    (57, READY, "lin", {ch: "in2" for ch in ("foot_r", "foot_r_rot", "foot_l", "foot_l_rot")}), (58, READY, "sine")],
    # (la mano libre sin atraso: cada cuadro del arranque la deja donde va)
    lag=mod(LEAD, hips=0.0, hips_rot=0.0, hand_l=0.0),
    timing={"phases": {"prep": [0, 9.6], "travel": [9.6, 14.4], "slashes": 16.2, "hold": [15, 45], "end": 58},
            "hold": [15, 45], "airborne": [10, 14], "burst": [10], "snap_ok": [[48, 49]]},
    notes="prepara (iai) 0.32 s, viaja 0.16 s en el aire en la pose del dash, llega de espaldas en zanshin y queda 1 s "
          "mientras aparecen los cortes; chiburi, un paso y guardia")

# =========================================================================== Torbellino de Hojas (habilidad 2)
# PlayerController.TickWhirlwind gira el MODELO 720° (horario visto desde arriba) entre 0.12 y 0.74 s (f3.6-f22.2): el
# clip no gira, pone la pose del trompo. Se enrosca a su izquierda (contra el giro) sobre las puntas de los pies en
# las huellas de la guardia, y en f4 ya está en el aire: el giro arranca rapidísimo (EaseOut: 30° en el primer medio
# cuadro) y un pie apoyado dibujaría un círculo en el piso. En el aire los pies van juntos bajo el centro, la hoja
# estirada a su derecha a la altura de la cintura con el filo hacia atrás (al girar horario, el lado derecho barre
# hacia atrás) y el brazo izquierdo abierto; baja casi vertical sobre las huellas de la guardia cuando ya no gira y cae
# en la pose del final (f24): agachado y girado a su derecha, la hoja sigue el giro afuera y atrás a su derecha y la mano
# izquierda abierta adelante, como quien frena las hojas que caen. Se hunde (f27), levanta la vista (f33) y queda hasta
# f54 (WhirlwindHoldEnd 1.8 s, la órbita baja frenando); después se para en la guardia como un gesto que se corta.
# El enrosque lleva la hoja atrás de la cadera izquierda con la punta hacia abajo y el codo pegado al cuerpo: con la
# hoja apuntando arriba, el brazo pasaba de un lado al otro del hombro al desenroscarse (166° de giro en un cuadro)
_wh_coil = feet(mod(READY, hips=(0.0, 0.04, -0.2), hips_rot=(10.0, 0.0, 30.0), spine=(10.0, 0.0, 24.0), head=(-12.0, 0.0, -20.0),
                    grip=(-0.05, -0.52, 1.04), blade=(0.8, -0.3, -0.25), edge=(0.24, -0.91, -0.34), elbow_r=(-0.2, -0.5, -0.8),
                    hand_l=(0.6, 0.12, 0.98), fingers_l=0.6),
                r=toe("R", *R_FOOT, 26.0), l=toe("L", *L_FOOT, 26.0))
_wh_spin = feet(mod(READY, hips=(0.0, 0.0, -0.06), lift=0.2, hips_rot=(6.0, 6.0, 0.0), spine=(4.0, 6.0, -6.0), head=(-6.0, 0.0, 4.0),
                    clav_r=(0.0, 10.0, 0.0), clav_l=(0.0, -10.0, 0.0), grip=(-0.73, 0.05, 1.29), blade=(-0.99, 0.0, 0.12),
                    edge=(-0.12, -0.2, -0.97), elbow_r=(-0.6, 0.6, -0.5), hand_l=(0.98, -0.04, 1.36), hand_l_dir=(0.95, 0.1, 0.1),
                    hand_l_up=(0.0, 0.0, 1.0), elbow_l=(0.4, 0.6, -0.6), fingers_l=0.05),
                r=air(-0.12, 0.02, 0.4, 20.0, 0.0), l=air(0.12, 0.04, 0.46, 30.0, 0.0))
_wh_spin2 = feet(mod(_wh_spin, lift=0.3, hips=(0.0, 0.0, -0.04), grip=(-0.75, 0.06, 1.32), blade=(-0.99, 0.03, 0.13)),
                 r=air(-0.12, 0.0, 0.5, 24.0, 0.0), l=air(0.12, 0.02, 0.56, 34.0, 0.0))
WH_LAND = feet(mod(READY, hips=(0.0, 0.02, -0.3), hips_rot=(16.0, 0.0, -16.0), spine=(14.0, 0.0, -12.0), head=(-16.0, 0.0, 10.0),
                   clav_r=(0.0, 6.0, 0.0), grip=(-0.8, 0.06, 0.94), blade=(-0.9, 0.39, 0.22),
                   edge=perp((-0.9, 0.39, 0.22), (0.2, 1.0, 0.0)), elbow_r=(-0.7, 0.5, -0.5), hand_l=(0.52, -0.4, 1.22),
                   hand_l_dir=(0.35, -0.92, 0.1), hand_l_up=(0.0, 0.15, 1.0), elbow_l=(0.7, 0.3, -0.6), fingers_l=0.1),
               r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))
_wh_over = mod(WH_LAND, hips=(0.0, 0.02, -0.35), hips_rot=(19.0, 0.0, -18.0), spine=(16.0, 0.0, -13.0), head=(-19.0, 0.0, 12.0),
               grip=(-0.8, 0.08, 0.9), blade=(-0.9, 0.42, 0.12), edge=perp((-0.9, 0.42, 0.12), (0.2, 1.0, 0.0)))
WH_FINISH = mod(WH_LAND, hips=(0.0, 0.02, -0.32), head=(-11.0, 0.0, 14.0))
_wh_fin_b = mod(WH_FINISH, breath=1.0, hips=(0.0, 0.02, -0.315), head=(-12.0, 0.0, 13.0))
WH_FIN_END = mod(WH_FINISH, breath=0.3, hips=(0.0, 0.02, -0.325), head=(-10.0, 0.0, 11.0))
WHIRL_HOLD_END = 54             # PlayerController.WhirlwindHoldEnd (1.8 s)
def _wh_arms(u):
    """Los brazos a la fracción u del desenrosque (el cuerpo va por su lado): la katana sale del enrosque en cuatro
    cuadros parejos (f4-f7) en vez de uno solo, donde el modelo además gira 77°."""
    return {k: v for k, v in inter(_wh_coil, _wh_spin, u).items() if k in ("grip", "blade", "edge", "elbow_r", "clav_r", "clav_l", "hand_l", "hand_l_dir", "hand_l_up", "elbow_l", "fingers_l", "arm_space", "hand_l_relax")}


add("Whirlwind", 66, [
    # (la katana se enrosca a ritmo parejo, el cuerpo con su curva: con "out" la mano daba el 70 % del giro en el primer
    # cuadro, 78°, y con "sine" la mitad en el del medio)
    (0, READY, "sine"), (3, _wh_coil, "sine", {"grip": "lin", "blade": "lin", "edge": "lin", "elbow_r": "lin"}), (4, feet(mod(inter(_wh_coil, _wh_spin, 0.75), **_wh_arms(0.25)), r=air(-0.14, -0.05, 0.4, 20.0, 0.0), l=air(0.18, 0.055, 0.46, 30.0, 0.0)), "out"),
    (5, mod(_wh_spin, **_wh_arms(0.5)), "out"), (6, mod(inter(_wh_spin, _wh_spin2, 0.04), **_wh_arms(0.75)), "lin"),
    (7, mod(inter(_wh_spin, _wh_spin2, 0.15), **_wh_arms(1.0)), "lin"), (13, _wh_spin2, "sine"), (21, _wh_spin, "sine"),
    (23, feet(inter(_wh_spin, WH_LAND, 0.6), r=hover("R", R_FOOT[0], R_FOOT[1], R_FOOT[2], 0.05),
              l=hover("L", L_FOOT[0], L_FOOT[1], L_FOOT[2], 0.05)), "sine"),
    (24, WH_LAND, "in2"), (27, _wh_over, "out"), (33, WH_FINISH, "sine"), (43, _wh_fin_b, "sine"), (WHIRL_HOLD_END, WH_FIN_END, "sine"),
    (60, inter(WH_FIN_END, READY, 0.6), "inout"), (66, READY, "sine")],
    # (la mano libre sin atraso: con él terminaba de caer en f24-f25, ya en la pose quieta; la cadera y el tronco
    # tampoco se adelantan: con el adelanto el cuerpo ya giraba en f3 y el brazo enroscado se retorcía contra él)
    lag=mod(LEAD, hand_l=0.0, hips=0.0, hips_rot=0.0, spine=0.0),
    timing={"phases": {"coil": [0, 3.6], "spin": [3.6, 22.2], "land": 24, "hold": [24, WHIRL_HOLD_END], "end": 66},
            "hold": [24, WHIRL_HOLD_END], "spin": [3.6, 22.2, -720.0], "airborne": [4, 22],
            # f3-f4 es el arranque del trompo: el código gira el modelo 77° por cuadro en ese momento y el brazo de la katana
            # se desenrosca con él (como el despegue del Corte del Viento: sin topes ni chequeo de tirones)
            "burst": [4]},
    notes="enrosque en puntas, trompo en el aire con la hoja afuera a su derecha (el código gira el modelo 720°), cae "
          "agachado con la hoja siguiendo el giro y la mano izquierda adelante; queda 1 s y se para en la guardia")

# =========================================================================== frenada
# PlayerController la toca al soltar el stick corriendo (más de 4.5 m/s): el juego frena a 40 m/s² (acceleration), de 6.2
# m/s a 0 en 0.155 s y 0.48 m (stop_travel, el avance que el clip descuenta de los pies). El primer cuadro de cada frenada
# ES un cuadro de la carrera y los que siguen hasta que apoya CONTINÚAN la carrera (Run va a 60 fps: el cuadro j de la
# frenada es Run en la fase + 2j), con el cuerpo que recién empieza a echarse atrás: el fundido de 0.1 s mezcla dos poses
# que se mueven igual. Antes la pose de frenada entraba entera en el segundo cuadro (el tronco 39°, la cabeza 36° y el
# brazo izquierdo 128° de un cuadro al otro).
# Cuatro frenadas, una cada 6 cuadros del ciclo de Run (0.1 s): el código espera en la carrera hasta la fase de la
# siguiente (PlayerController.TryRunStop) y arranca ahí, así el fundido nunca mezcla piernas de fases distintas (con
# dos, a medio camino quedaban 45-124° entre las piernas). Fases 8 y 20: el pie que frena está adelante en el aire y apoya
# en f2 (donde la carrera lo apoyaría); fases 2 y 14 ('Reach'): el otro pie recién apoyó, el que frena viene por debajo
# del cuerpo, se estira y apoya en f3. Después: el talón clavado con el cuerpo echado atrás y la cadera que baja (un
# cuadro después de apoyar), el impulso lo pasa por encima del pie (el pecho se va adelante, la katana sigue de largo) y
# se rearma en la guardia del Idle. Ningún pie apoyado patina con el frenado del juego
def stop_travel(n):
    return [U * min(0.155, f / 30.0) * (6.2 - 20.0 * min(0.155, f / 30.0)) for f in range(n + 1)]


STOP_N = 16
STOP_TR = stop_travel(STOP_N + 1)
_S_R = (R_FOOT[0], R_FOOT[1] - STOP_TR[STOP_N])   # huellas en el mundo del clip: al final, las de la guardia
_S_L = (L_FOOT[0], L_FOOT[1] - STOP_TR[STOP_N])
_SL_PLANT = (0.3, -0.95)                          # el talón izquierdo clava un poco adelante de su huella de la guardia
RUN_STOP_PHASE = {"RunStop": 8, "RunStopL": 20, "RunStopReach": 2, "RunStopLReach": 14}   # cuadros del ciclo de Run (24)


def run_frame(f):
    """La pose de la carrera en el cuadro f de su ciclo horneado (los pies en el aire, como los pone el ciclo)."""
    c = RUN.controls(f % RUN.n)
    body = {k: v for k, v in c.items() if not k.startswith("foot_")}
    return feet(mod(READY, **body), r=(c["foot_r"], c["foot_r_rot"]), l=(c["foot_l"], c["foot_l_rot"]))


def run_lead(ph, j, tr, pose=None, u=0.0):
    """Cuadro j de una frenada que arranca en la fase ph: la carrera que sigue (Run en ph + 2j, los pies corridos al
    mundo del clip con lo que ya frenó) con la pose 'pose' entrando en u (los pies salen de la carrera)."""
    run = at_travel(run_frame(ph + 2 * j), tr[j])
    if pose is None or u <= 0.0:
        return run
    q = feet(inter(run, pose, u), r=(run["foot_r"], run["foot_r_rot"]), l=(run["foot_l"], run["foot_l_rot"]))
    # el brazo izquierdo, el de la carrera hasta que apoya (la frenada lo lleva en el espacio del pecho: mezclar los dos
    # espacios lo estiraba y lo doblaba de un cuadro al otro)
    q.update({k: run[k] for k in _ARM_KEYS})
    return q


def toe_print(side, ank, rot):
    """(x, y) de la huella de un pie que apoya la punta con el tobillo y el giro dados (la inversa de KR.foot_on)."""
    toe, _, _ = KR.sole_points(side)
    A = KR.ankle_rest(side)
    pitch, roll, yaw = rot
    Pw = Vector(ank) - KR.foot_rot(pitch, roll, yaw) @ (A - toe)
    base = Pw - KR.foot_rot(0.0, 0.0, yaw) @ (toe - A)
    return base.x, base.y


_RUN_STANCE = {"r": set(RUN.feet["r"].stance_frames(RUN.n, 0.5)), "l": set(RUN.feet["l"].stance_frames(RUN.n, 0.0))}


# el talón clavado con el cuerpo echado atrás (la carga máxima, un cuadro después de apoyar)
# El brazo izquierdo sigue el vaivén de la carrera (en la carrera va contra la pierna izquierda): frenando sobre el pie
# derecho viene adelante y sigue subiendo por el envión; sobre el izquierdo viene atrás y pasa adelante con el pecho. La
# mano va floja (hand_l_relax: sigue al antebrazo) y en el espacio del pecho (arm_space_l: acompaña al tronco que se echa
# atrás y adelante) hasta que vuelve a la guardia. Con una mano autorada aparte (adelante, la palma abierta) y fija en el
# transform la muñeca pasaba de un tope al otro y el codo daba vuelta en un cuadro
_ARM_FWD = dict(hand_l=(0.31, -0.16, 1.32), hand_l_dir=(0.0, -0.68, -0.8), hand_l_up=(1.0, 0.0, 0.0), elbow_l=(0.5, 0.9, -0.3),
                fingers_l=0.85, hand_l_relax=1.0, arm_space_l=1.0)
_ARM_BACK = dict(hand_l=(0.36, 0.2, 1.1), hand_l_dir=(0.0, 0.2, -0.95), hand_l_up=(1.0, 0.0, 0.0), elbow_l=(0.5, 0.9, -0.3),
                 fingers_l=0.85, hand_l_relax=1.0, arm_space_l=1.0)
# a medio camino: las frenadas 'Reach' apoyan con el brazo todavía al costado (viniendo de atrás sobre el pie derecho, yendo
# atrás sobre el izquierdo)
_ARM_MID = dict(hand_l=(0.34, 0.02, 1.18), hand_l_dir=(0.0, -0.3, -0.95), hand_l_up=(1.0, 0.0, 0.0), elbow_l=(0.5, 0.9, -0.3),
                fingers_l=0.85, hand_l_relax=0.6, arm_space_l=1.0)
_ARM_MID_L = dict(_ARM_MID, hand_l=(0.35, 0.1, 1.14), hand_l_dir=(0.0, -0.1, -0.97), hand_l_relax=0.5)
_ARM_OVER = dict(hand_l=(0.34, -0.22, 1.2), hand_l_dir=(-0.1, -0.72, -0.68), hand_l_up=(0.95, 0.0, 0.3), elbow_l=(0.5, 0.9, -0.3),
                 fingers_l=0.7, hand_l_relax=0.8, arm_space_l=1.0)
_ARM_KEYS = tuple(_ARM_FWD)
# (la katana como en la carrera, apenas levantada: con la punta más arriba la muñeca pedía girar la hoja 35° en el apoyo)
_st_plant = mod(READY, hips=(0.0, 0.06, -0.2), hips_rot=(-14.0, 0.0, 6.0), spine=(-8.0, 0.0, -4.0), head=(2.0, 0.0, -2.0),
                grip=(-0.6, -0.2, 0.98), blade=(-0.74, -0.62, -0.18), edge=(0.2, -0.1, -0.97), **_ARM_FWD)
_st_over = mod(READY, hips=(0.0, 0.0, -0.2), hips_rot=(18.0, 0.0, 10.0), spine=(18.0, 0.0, -8.0), head=(-20.0, 0.0, -4.0),
               grip=(-0.6, -0.38, 0.92), blade=(-0.48, -0.86, -0.15), edge=(0.2, -0.1, -0.97), **_ARM_OVER)
_st_land = mod(READY, hips=(0.0, 0.03, -0.12), hips_rot=(5.0, 0.0, 13.0), spine=(9.0, 0.0, -9.0), head=(-9.0, 0.0, -4.0))
# sobre el pie izquierdo: el mismo cuerpo con la cadera girada al revés y el brazo izquierdo que viene de atrás
# (la katana atrás, como la lleva la carrera cuando apoya el izquierdo)
_stl_plant = mod(_st_plant, hips_rot=(-14.0, 0.0, -4.0), spine=(-8.0, 0.0, 2.0), grip=(-0.61, -0.02, 0.97), blade=(-0.77, -0.52, -0.2),
                 **_ARM_BACK)
_stl_over = mod(_st_over, hips_rot=(18.0, 0.0, 6.0), **_ARM_OVER)
_stl_land = mod(_st_land, hips=(0.0, -0.02, -0.12))
# cuánto de la pose de frenada entra en cada cuadro antes de apoyar (el resto es la carrera que sigue), por cuadro de apoyo
_ST_LEAD_U = {2: (0.0, 0.1), 3: (0.0, 0.05, 0.1)}


def run_stop(name, side, plant_f):
    """Frenada sobre el pie 'side' que apoya en plant_f (ver arriba). R: el izquierdo pasa en el aire a su huella de la
    guardia; L: el derecho pasa adelante a la suya y el izquierdo se acomoda atrás con un pasito. Termina en la guardia."""
    ph, P = RUN_STOP_PHASE[name], plant_f
    n = STOP_N + P - 2
    tr = STOP_TR[:n + 1]
    body_plant, body_over, body_land = (_st_plant, _st_over, _st_land) if side == "R" else (_stl_plant, _stl_over, _stl_land)
    # el pie que en la carrera está apoyado (en 'Reach', el que no frena) se queda clavado en su huella de la punta mientras
    # el juego frena: con los pies de la carrera corrido por el avance del clip resbalaba 2 cm
    prints = {}
    keys = []
    for j in range(P):
        q = run_lead(ph, j, tr, body_plant, _ST_LEAD_U[P][j])
        # la mano se afloja de a poco (la de la carrera es la autorada, recortada a lo cómodo: de una a la otra hay 40-50°)
        q["hand_l_relax"] = 0.3 * j / P
        for s_ in ("r", "l"):
            if (ph + 2 * j) % RUN.n in _RUN_STANCE[s_]:
                ank, rot = q["foot_" + s_], q["foot_" + s_ + "_rot"]
                S = s_.upper()
                xy = prints.setdefault(s_, toe_print(S, ank, rot))
                q = feet(q, **{s_: plant(S, xy[0], xy[1], max(0.0, rot[0]), rot[2], "toe")})
        keys.append((j, q, "lin"))
    # al apoyar el cuerpo todavía trae la mitad de la carrera: se echa atrás en 3 cuadros (de golpe, con el brazo casi recto
    # de la carrera, el húmero izquierdo giraba 60° en un cuadro)
    hit = inter(run_lead(ph, P, tr), body_plant, 0.4)
    # ...pero el brazo izquierdo ya en el pecho: mezclado a medias entre el espacio del transform y el del pecho, la mano
    # caía en un punto que no era ninguno de los dos y el brazo se estiraba de golpe
    hit.update({k: body_plant[k] for k in _ARM_KEYS})
    # (un cuadro después de apoyar, el brazo de la 'Reach' a mitad de camino entre el costado y adelante)
    after = body_plant
    if P == 3:
        mid, arm = (_ARM_MID, _ARM_FWD) if side == "R" else (_ARM_MID_L, _ARM_BACK)
        hit.update(mid)
        after = mod(body_plant, **{k: v for k, v in inter(mid, arm, 0.5).items() if k in _ARM_KEYS})
    hit["hand_l_relax"] = min(hit["hand_l_relax"], 0.6)
    # el pie que no frena sigue el vuelo de la carrera (alto atrás) y recién después baja hacia su huella: bajándolo al
    # piso en el cuadro del apoyo la pierna giraba 60-78° de golpe
    run_p = run_lead(ph, P, tr)
    free = "l" if side == "R" else "r"
    trail = (run_p["foot_" + free], run_p["foot_" + free + "_rot"])

    def toward(target, u):
        (a, ra), (b, rb) = trail, target
        return tuple(x + (y - x) * u for x, y in zip(a, b)), tuple(x + (y - x) * u for x, y in zip(ra, rb))
    if side == "R":
        l_over = lifted("L", 0.27, 0.3 - tr[P + 4], 0.07, 14.0, 34.0)
        keys += [
            (P, feet(hit, r=plant("R", *_S_R, -18.0, 6.0, "heel"), l=trail), "out", {"foot_r": "lin", "foot_l": "lin"}),
            (P + 1, feet(after, r=plant("R", *_S_R, -13.0, 6.0, "heel"), l=toward(l_over, 0.4)), "out"),
            (P + 4, feet(body_over, r=flat("R", *_S_R, 6.0), l=l_over), "sine"),
            (P + 6, feet(inter(body_over, body_land, 0.6), r=flat("R", *_S_R, 6.0), l=hover("L", _S_L[0], _S_L[1], L_FOOT[2], 0.05)),
             "sine"),
            (P + 7, feet(body_land, r=flat("R", *_S_R, 6.0), l=flat("L", *_S_L, L_FOOT[2])), "in2"),
            (P + 10, feet(mod(READY, hips=(0.0, 0.02, -0.08)), r=flat("R", *_S_R, 6.0), l=flat("L", *_S_L, L_FOOT[2])), "sine"),
            (n, feet(READY, r=flat("R", *_S_R, 6.0), l=flat("L", *_S_L, L_FOOT[2])), "sine")]
        timing = {"plant": P, "settle": P + 7}
        events = [{"frame": P, "fn": "FootR"}, {"frame": P + 7, "fn": "FootL"}]
        note = "clava el talón derecho, el impulso lo pasa por encima y se rearma en la guardia"
    else:
        keys += [
            (P, feet(hit, r=trail, l=plant("L", *_SL_PLANT, -18.0, 30.0, "heel")), "out", {"foot_r": "lin", "foot_l": "lin"}),
            (P + 1, feet(after, r=toward(lifted("R", -0.24, -0.1 - tr[P + 4], 0.08, 10.0, 4.0), 0.4),
                         l=plant("L", *_SL_PLANT, -13.0, 30.0, "heel")), "out"),
            (P + 4, feet(body_over, r=lifted("R", -0.24, -0.1 - tr[P + 4], 0.08, 10.0, 4.0), l=flat("L", *_SL_PLANT, 30.0)), "sine"),
            (P + 6, feet(inter(body_over, body_land, 0.6), r=hover("R", _S_R[0], _S_R[1], 6.0, 0.05), l=flat("L", *_SL_PLANT, 30.0)), "sine"),
            (P + 7, feet(body_land, r=flat("R", *_S_R, 6.0), l=flat("L", *_SL_PLANT, 30.0)), "in2"),
            (P + 9, feet(mod(READY, hips=(0.0, 0.03, -0.1)), r=flat("R", *_S_R, 6.0),
                         l=lifted("L", 0.3, (_SL_PLANT[1] + _S_L[1]) * 0.5, 0.05, 6.0, 32.0)), "inout"),
            (P + 11, feet(mod(READY, hips=(0.0, 0.02, -0.09)), r=flat("R", *_S_R, 6.0), l=flat("L", *_S_L, L_FOOT[2])), "in2"),
            (n, feet(READY, r=flat("R", *_S_R, 6.0), l=flat("L", *_S_L, L_FOOT[2])), "sine")]
        timing = {"plant": P, "settle": P + 11}
        events = [{"frame": P, "fn": "FootL"}, {"frame": P + 7, "fn": "FootR"}, {"frame": P + 11, "fn": "FootL"}]
        note = "clava el talón izquierdo, el derecho pasa adelante y el izquierdo se acomoda"
    # mientras sigue la carrera, los brazos de Run (kaito_rig.follow_states)
    timing.update({"travel_fixed": True, "run_phase": ph / RUN.n, "lead": P,
                   "arm_follow": ["Run", [[j, (ph + 2 * j) % RUN.n] for j in range(P)]]})
    # sin el adelanto de la cadera ni el atraso de la mano libre: con ellos los cuadros que siguen la carrera ya traían algo
    # del apoyo (la mano en un punto entre el espacio del transform y el del pecho, la cadera más baja)
    add(name, n, keys, travel=tr, timing=timing, events=events, lag=mod(LEAD, hips=0.0, hips_rot=0.0, hand_l=0.0),
        notes=f"frenada desde la fase {ph}/{RUN.n} de la carrera: {note} ({n / 30.0:.2f} s)")


run_stop("RunStop", "R", 2)
run_stop("RunStopL", "L", 2)
run_stop("RunStopReach", "R", 3)
run_stop("RunStopLReach", "L", 3)


# =========================================================================== gestos de exploración
# Rezar en el santuario (Checkpoint): el pie izquierdo da un paso atrás y apoya la rodilla; la katana ofrecida hacia
# el santuario, la punta arriba y adelante y las dos manos juntas en la empuñadura a la altura del pecho (el voto del
# samurái), la cabeza inclinada. Vertical quedaba escondida atrás del pelo desde la cámara del juego; inclinada 40°
# hacia adelante es una raya que sale de la silueta por delante y por arriba: se lee "reza" y no "se agachó".
# Respira y la cabeza se inclina un poco más (espera que se mueve); el pie vuelve con otro paso. Moverse lo corta
# (PlayerController.TickLocomotion)
_pray = feet(mod(READY, hips=(0.0, 0.1, -0.34), hips_rot=(4.0, 0.0, 0.0), spine=(6.0, 0.0, 0.0), head=(18.0, 0.0, 0.0),
                 grip=(-0.05, -0.56, 1.05), blade=(-0.05, -0.6, 0.8), edge=(0.0, -0.8, -0.6), elbow_r=(-0.8, 0.1, -0.6),
                 grip_l=1.0, elbow_l=(0.8, 0.1, -0.6), fingers_l=1.0, knee_l=(0.2, -0.6, -0.8)),
             r=flat("R", *R_FOOT), l=plant("L", 0.26, 0.46, 70.0, 10.0, "toe"))
_pray_b = mod(_pray, breath=1.0, hips=(0.0, 0.1, -0.35), head=(22.0, 0.0, 0.0))
_pray_d = mod(_pray, hips=(0.0, 0.1, -0.355), head=(24.0, 0.0, 0.0), spine=(8.0, 0.0, 0.0))
# (la rodilla se levanta del piso en 6 cuadros: en 5 la tibia giraba 46° en uno)
add("Pray", 40, [(0, READY, "sine"), (5, feet(inter(READY, _pray, 0.45), l=lifted("L", 0.27, 0.4, 0.07, 62.0, 12.0)), "inout"),
                 (10, _pray, "in2"), (17, _pray_b, "sine"), (24, _pray_d, "sine"), (30, _pray, "sine"),
                 (36, feet(inter(_pray, READY, 0.55), l=lifted("L", 0.28, 0.38, 0.06, 40.0, 24.0)), "inout"), (40, READY, "in2")],
    timing={"kneel": 10, "rise": 30, "slow": True},
    notes="paso atrás y rodilla al piso, la katana ofrecida hacia adelante y arriba con las dos manos (1.33 s)")
# Juntar algo (la mitad de la llave): se agacha, la mano izquierda baja, la cierra y se para
_reach = feet(mod(READY, hips=(0.0, 0.06, -0.26), hips_rot=(18.0, 0.0, 6.0), spine=(22.0, 0.0, 4.0), head=(16.0, 0.0, -4.0),
                  arm_space=0.0, grip=(-0.57, -0.34, 0.98), blade=(-0.53, -0.78, 0.32), edge=(-0.78, 0.3, -0.53),
                  hand_l=(0.26, -0.5, 0.42), hand_l_dir=(0.0, -0.6, -0.8), hand_l_up=(1.0, 0.0, 0.0),
                  elbow_l=(0.8, 0.2, -0.4), fingers_l=0.0),
              r=flat("R", *R_FOOT), l=toe("L", *L_FOOT, 20.0))
add("Interact", 20, [(0, READY, "sine"), (7, _reach, "inout"), (10, mod(_reach, fingers_l=1.0, hand_l=(0.26, -0.48, 0.44)), "out"),
                     (20, READY, "inout")],
    timing={"grab": 10, "slow": True}, notes="se agacha a juntar algo con la mano izquierda (0.67 s)")


# =========================================================================== historia
# Clips de las escenas (los toca StoryDirector / el santuario con ScriptedPlay; cada uno termina en la guardia del Idle
# salvo EndingTurn, que se queda ofreciendo la cinta). Se leen desde la cámara del juego y desde planos de historia más
# cercanos; los eventos ('events', en el .fbx.json) marcan dónde el código pone utilería y efectos.

# Rodillas en el piso: la tibia de Kaito (0.28 u) es más corta que su pie y con los dedos doblados (kiza) la rodilla no
# llegaba al piso, quedaba en cuclillas: el pie que se arrodilla va estirado atrás con el empeine apoyado (seiza), el
# tobillo una tibia detrás de la rodilla
KNEE_L = air(0.22, 0.36, 0.16, 160.0, 6.0)


# Un pie que da la vuelta en el aire (de empeine en el piso a plano, al arrodillarse o al pararse) va a ritmo parejo entre
# sus claves: con la curva de cada tramo el giro se juntaba en el medio y la punta barría 15-20 cm en un cuadro junto al piso
LIN_R = {"foot_r": "lin", "foot_r_rot": "lin", "knee_at_r": "lin"}
LIN_L = {"foot_l": "lin", "foot_l_rot": "lin", "knee_at_l": "lin"}


def knee_up(x, y, yaw):
    """El pie de la rodilla en el aire a mitad de camino: el tobillo alto y la punta abajo, lejos del piso."""
    return air(x, y, 0.34, 135.0, yaw)

# ------------------------------------------------------------------ rezo con sahumerio (primera visita)
# Para una cámara de costado, lento y respetuoso. Rodilla izquierda al piso; se inclina y apoya la katana en el piso a su
# derecha (la empuñadura junto a la rodilla, la hoja adelante y abierta hacia afuera: PI_KAT), la suelta
# y se endereza; baja la otra rodilla y queda sentado sobre los talones (kiza, los dedos de los pies doblados). Toma un
# sahumerio de la caja a su derecha (incense_take), lo sube a la llama, al centro y a la altura del mentón, con la
# izquierda haciendo de pantalla (incense_light), lo apaga con dos abanicos de la izquierda, lo lleva adelante y abajo con
# la izquierda sosteniendo la muñeca derecha y lo clava en el sahumador inclinándose (incense_place). Palmas juntas delante del pecho (palms), reverencia larga por el abuelo,
# levanta la cabeza, vuelve a tomar la katana y se para (rise). El santuario va ADELANTE (-Y). Dónde está la muñeca
# derecha (Mando.R) en cada evento, en metros respecto del transform (derecha, arriba, adelante), medido en el horneado:
# timing 'hand_r_m' (va al .fbx.json); la punta del sahumerio queda ~10 cm más adelante. Los pies no se corren: cada uno
# pasa de apoyado a arrodillado con un paso en el aire
# la katana en el piso a su derecha: el puño junto a la rodilla, la hoja adelante y abierta 30° hacia afuera (lejos del
# santuario), el filo hacia afuera: la mano la apoya con la palma abajo, como cualquier cosa que se deja en el piso.
# Con la hoja hacia atrás la mano tenía que darla vuelta 180° al dejarla y al retomarla (la muñeca saltaba de un tope
# de giro al otro en un cuadro, 140°), y con el filo hacia él había que supinar la mano 90° (al tope: la hoja se hundía
# en el piso al soltarla)
PI_KAT = (-0.66, -0.3, 0.125)
PI_KAT_BLADE = (-0.5, -0.866, 0.0)
PI_KAT_EDGE = perp(PI_KAT_BLADE, (-1.0, 0.0, 0.0))
_PI_L = KNEE_L
# (el mismo giro que air(..., 160, -6) escrito como 20° de cabeceo, 180 de vuelta y -186 de giro: al arrodillarse el pie
# derecho va de plano adelante a este dando la vuelta hacia afuera, no por la punta abajo. El pie de Kaito es más largo
# que su tibia: con la punta abajo el tobillo subía por encima de la cadera y la rodilla saltaba de arriba a abajo)
_PI_R = ((-0.22, 0.36, 0.18), (20.0, 180.0, -186.0))
_pi_k1 = feet(mod(READY, hips=(0.0, 0.1, -0.34), hips_rot=(4.0, 0.0, 0.0), spine=(5.0, 0.0, 0.0), head=(8.0, 0.0, 0.0),
                  grip=(-0.5, -0.3, 0.7), blade=(-0.25, -0.93, -0.27), edge=perp((-0.25, -0.93, -0.27), (-1.0, 0.0, 0.0)),
                  elbow_r=(-0.8, 0.4, -0.4), hand_l=(0.36, -0.3, 0.74), hand_l_dir=(0.0, -1.0, -0.2), hand_l_up=(0.2, 0.0, 1.0),
                  elbow_l=(0.8, 0.4, -0.4), fingers_l=0.35, knee_l=(0.2, -0.6, -0.8), kat_free=0.0, fingers_r=0.3,
                  kat_pos=PI_KAT, kat_blade=PI_KAT_BLADE, kat_edge=PI_KAT_EDGE,
                  hand_r=(-0.62, -0.3, 0.22), hand_r_dir=(0.0, -1.0, -0.3), hand_r_up=(0.0, 0.3, 1.0)),
              r=flat("R", *R_FOOT), l=_PI_L)
# se inclina hacia su derecha y apoya la katana (la mano izquierda en el muslo sostiene el peso)
_pi_lean = mod(_pi_k1, hips=(-0.04, 0.12, -0.36), hips_rot=(30.0, -10.0, -12.0), spine=(22.0, -8.0, -8.0), head=(6.0, 6.0, 6.0),
               grip=(-0.66, -0.31, 0.26), blade=(-0.48, -0.87, -0.06), edge=perp((-0.48, -0.87, -0.06), (-1.0, 0.0, 0.0)),
               elbow_r=(-0.8, 0.5, 0.2), hand_l=(0.3, -0.36, 0.66))
# La katana se da vuelta a su pose del piso (plana) EN EL AIRE, 7 cm arriba del piso (la mano no llega a ponerla plana:
# en la mano queda 60° de canto), y recién después baja derecha y la mano la suelta. Girándola en el piso, la hoja curva
# se balanceaba sobre su lomo y la punta saltaba hacia la cámara un cuadro. Al retomarla, lo mismo al revés
PI_KAT_UP = (PI_KAT[0], PI_KAT[1], PI_KAT[2] + 0.13)
_PI_HAND = dict(hand_r_dir=(0.05, -0.99, -0.1), hand_r_up=(-0.3, 0.0, 0.95))
# (la mano que suelta o retoma la katana pasa de una pose a la otra a ritmo parejo: con la curva del tramo giraba 46° en
# el cuadro del medio)
_KAT_HAND = {"kat_free": "lin", "hand_r": "lin", "hand_r_dir": "lin", "hand_r_up": "lin"}
_pi_roll = mod(_pi_lean, kat_free=1.0, kat_pos=PI_KAT_UP, fingers_r=0.6, hand_r=(-0.64, -0.36, 0.38), **_PI_HAND)
_pi_set = mod(_pi_roll, kat_pos=PI_KAT, hand_r=(-0.64, -0.36, 0.25), hips=(-0.05, 0.12, -0.37))
_pi_let = mod(_pi_set, fingers_r=0.15)
# se endereza: la mano derecha al muslo
_pi_up = mod(_pi_k1, kat_free=1.0, fingers_r=0.3, hand_r=(-0.34, -0.3, 0.72), hand_r_dir=(0.0, -1.0, -0.2), hand_r_up=(-0.2, 0.0, 1.0))
# kiza: las dos rodillas al piso, sentado sobre los talones, la espalda derecha, las manos en los muslos
KIZA = feet(mod(_pi_up, hips=(0.0, 0.22, -0.390), hips_rot=(-2.0, 0.0, 0.0), spine=(4.0, 0.0, 0.0), head=(6.0, 0.0, 0.0),
                hand_l=(0.3, -0.24, 0.6), hand_r=(-0.3, -0.24, 0.6), knee_r=(-0.15, -1.0, -0.3), knee_l=(0.15, -1.0, -0.3)),
            r=_PI_R, l=_PI_L)
_kiza_b = mod(KIZA, breath=1.0, hips=(0.0, 0.22, -0.385), head=(4.0, 0.0, 0.0))
# Los cuatro momentos van en lugares distintos (con todos en la misma caja de 13 cm delante del regazo no se leían ni de
# costado): la caja de sahumerios a su derecha y abajo (se inclina hacia ella y la cabeza sigue a la mano), la llama
# arriba al centro, a la altura del mentón (la izquierda hace de pantalla abajo), dos abanicos de la izquierda de 13 cm
# junto a la punta, y el sahumador adelante y abajo: se inclina 15° y lo clava con las dos manos. Los brazos miden 30 cm:
# es lo más lejos que llega sin levantarse
# toma el sahumerio de la caja (a su derecha): pellizca con la derecha
_pi_reach = mod(KIZA, hips=(-0.03, 0.2, -0.375), hips_rot=(12.0, -8.0, -16.0), spine=(10.0, -8.0, -10.0), head=(18.0, -6.0, -18.0),
                hand_r=(-0.56, -0.48, 0.6), hand_r_dir=(-0.3, -0.85, -0.4), hand_r_up=(-0.5, 0.0, 0.85), fingers_r=0.2)
_pi_take = mod(_pi_reach, fingers_r=0.75, hand_r=(-0.55, -0.48, 0.64))
# a la llama (arriba al centro, a la altura del mentón), la izquierda hace de pantalla debajo de la punta
_pi_flame = mod(KIZA, hips=(0.0, 0.2, -0.370), hips_rot=(6.0, 0.0, 0.0), spine=(6.0, 0.0, 0.0), head=(8.0, 0.0, 0.0),
                hand_r=(-0.08, -0.62, 1.0), hand_r_dir=(0.25, -0.75, 0.6), hand_r_up=(-0.3, 0.5, 0.8), fingers_r=0.75,
                hand_l=(0.12, -0.62, 0.9), hand_l_dir=(-0.3, -0.7, 0.65), hand_l_up=(0.9, 0.1, 0.4), elbow_l=(0.8, 0.3, -0.5),
                fingers_l=0.2)
_pi_flame2 = mod(_pi_flame, hand_r=(-0.08, -0.63, 1.01), hand_l=(0.11, -0.63, 0.91), head=(9.0, 0.0, 0.0), breath=0.6)
# dos abanicos de la izquierda junto a la punta para apagar la llama (no se sopla): 13 cm de lado a lado
_pi_fan_a = mod(_pi_flame2, hand_l=(0.3, -0.58, 1.06), hand_l_dir=(-0.4, -0.6, 0.7), hand_l_up=(0.9, 0.2, 0.4))
_pi_fan_b = mod(_pi_flame2, hand_l=(0.05, -0.66, 1.02), hand_l_dir=(-0.2, -0.7, 0.68))
# lo lleva al sahumador (adelante y abajo) con la izquierda sosteniendo la muñeca derecha, se inclina y lo clava
_pi_carry = mod(KIZA, hips=(0.0, 0.16, -0.360), hips_rot=(16.0, 0.0, 0.0), spine=(14.0, 0.0, 0.0), head=(18.0, 0.0, 0.0),
                hand_r=(-0.04, -0.82, 0.72), hand_r_dir=(0.1, -0.7, 0.7), hand_r_up=(-0.3, 0.7, 0.65), fingers_r=0.75,
                hand_l=(0.06, -0.64, 0.64), hand_l_dir=(-0.9, -0.3, 0.3), hand_l_up=(-0.2, 0.2, 0.96), elbow_l=(0.8, 0.2, -0.6),
                fingers_l=0.45)
_pi_place = mod(_pi_carry, hips=(0.0, 0.12, -0.360), hips_rot=(22.0, 0.0, 0.0), spine=(18.0, 0.0, 0.0), head=(22.0, 0.0, 0.0),
                hand_r=(-0.03, -0.9, 0.5), hand_l=(0.07, -0.74, 0.46))
_pi_after = mod(_pi_place, fingers_r=0.3, hand_r=(-0.07, -0.82, 0.7))
# gassho: las palmas juntas delante del pecho, los dedos arriba y los codos doblados (más adelante los brazos quedaban
# estirados del todo y se plegaban de golpe al soltarlas)
_pi_palms = mod(KIZA, hips=(0.0, 0.22, -0.385), hips_rot=(2.0, 0.0, 0.0), spine=(6.0, 0.0, 0.0), head=(10.0, 0.0, 0.0),
                hand_r=(-0.05, -0.42, 1.0), hand_r_dir=(0.0, -0.15, 1.0), hand_r_up=(-1.0, 0.0, 0.0), fingers_r=0.0,
                hand_l=(0.05, -0.42, 1.0), hand_l_dir=(0.0, -0.15, 1.0), hand_l_up=(1.0, 0.0, 0.0), elbow_l=(0.8, 0.3, -0.5),
                fingers_l=0.0)
_pi_bow = mod(_pi_palms, breath=1.0, hips=(0.0, 0.2, -0.390), hips_rot=(10.0, 0.0, 0.0), spine=(16.0, 0.0, 0.0), head=(24.0, 0.0, 0.0))
_pi_bow2 = mod(_pi_bow, breath=0.2, head=(27.0, 0.0, 0.0), hips=(0.0, 0.2, -0.395))
_pi_lift = mod(_pi_palms, head=(4.0, 0.0, 0.0))
# (la mano izquierda baja de las palmas al muslo por delante del cuerpo y pareja: con la curva del tramo el codo se doblaba 46°
# en el cuadro del medio)
_PQ_ARM_L = {ch: "lin" for ch in ("hand_l", "hand_l_dir", "hand_l_up", "elbow_l")}
# vuelve a tomar la katana: se inclina, la mano derecha va al puño, la toma y la levanta
_pi_grab = feet(mod(_pi_lean, hips=(-0.05, 0.2, -0.37), kat_free=1.0, fingers_r=0.2, hand_r=(-0.64, -0.36, 0.25),
                   hand_l=(0.3, -0.24, 0.6), grip=PI_KAT_UP, blade=PI_KAT_BLADE, edge=PI_KAT_EDGE, knee_r=(-0.15, -1.0, -0.3),
                   knee_l=(0.15, -1.0, -0.3), **_PI_HAND),
                r=_PI_R, l=_PI_L)
_pi_grip = mod(_pi_grab, fingers_r=0.6)
_pi_raise = mod(_pi_grip, kat_pos=PI_KAT_UP, hand_r=(-0.64, -0.36, 0.38))
_pi_hold = mod(_pi_grab, kat_free=0.0, fingers_r=0.3)
_pi_lift_k = feet(mod(_pi_k1, hips=(0.0, 0.2, -0.35), hips_rot=(10.0, 0.0, -4.0), spine=(8.0, 0.0, -2.0), head=(4.0, 0.0, 0.0),
                      grip=(-0.56, -0.2, 0.6), blade=(-0.3, -0.93, -0.2), edge=perp((-0.3, -0.93, -0.2), (-1.0, 0.0, 0.0)),
                      hand_l=(0.3, -0.24, 0.62)),
                  r=lifted("R", -0.24, 0.2, 0.12, 30.0, 0.0), l=_PI_L)
_pi_k2 = feet(mod(_pi_k1, hips=(0.0, 0.1, -0.34), hand_l=(0.36, -0.3, 0.74)), r=flat("R", *R_FOOT), l=_PI_L)
_pi_down = mod(inter(_pi_lift, _pi_grab, 0.45), hand_l=(0.2, -0.4, 0.8))
# la rodilla derecha baja al piso (y vuelve a subir): levanta el talón, la rodilla sale hacia afuera (a su derecha) y baja
# por el costado mientras el pie da la vuelta por atrás hasta quedar con el empeine en el piso. Lento (13 cuadros). La
# rodilla va guiada (knee_at): el muslo y la tibia giran por afuera, de la rodilla arriba al kiza (u, rodilla, tobillo y
# giro del pie; la rodilla a un muslo de la cadera y el tobillo a una tibia de la rodilla). Con un polo fijo, al pasar el tobillo por la altura de la cadera la rodilla saltaba de arriba a abajo en un cuadro
# (el giro del pie repartido parejo entre las claves, ~20° por cuadro: con casi la mitad de la vuelta en el primer tramo la
# punta barría 15-18 cm por cuadro junto al piso)
_PI_KNEE = [(0.2, (-0.24, -0.15, 0.56), None),
            (0.35, (-0.32, -0.11, 0.49), swung("R", -0.4, -0.07, 0.23, (14.0, 25.0, -38.0))),
            (0.5, (-0.37, -0.08, 0.4), swung("R", -0.49, 0.05, 0.2, (15.0, 70.0, -90.0))),
            (0.7, (-0.38, -0.01, 0.27), swung("R", -0.49, 0.22, 0.19, (17.0, 120.0, -135.0))),
            (0.85, (-0.35, 0.04, 0.17), swung("R", -0.4, 0.31, 0.19, (19.0, 160.0, -168.0)))]


def pi_knee_keys(frames, half, kiza, first):
    """Claves de la rodilla derecha entre la pose de rodilla arriba 'half' y la de kiza (u de _PI_KNEE), en 'frames';
    'first' = el pie de la clave junto a la rodilla arriba (al bajar levanta el talón; al subir llega en el aire arriba de
    su huella: apoyando en punta y bajando el talón la suela se corría 3 cm)."""
    out = []
    for f, (u, knee, foot) in zip(frames, _PI_KNEE):
        p_ = mod(inter(half, kiza, u), knee_at_r=knee, knee_guide_r=1.0)
        # la clave junto al pie apoyado es un tope del giro del pie: el Catmull-Rom traía el giro de la clave siguiente
        # (el pie que da la vuelta, 40° de rolido) y entre el pie plano y el talón levantado la punta rotaba y se corría
        # 2.8 cm por el piso
        ch = {"stop": ("foot_r_rot",)} if foot is None else {}
        out.append((f, feet(p_, r=foot or first), "inout", ch))
    return sorted(out, key=lambda k: k[0])


add("PrayIncense", 188, [
    (0, READY, "sine"),
    (6, feet(inter(READY, _pi_k1, 0.45), l=lifted("L", 0.26, 0.4, 0.07, 62.0, 8.0)), "inout"),
    (10, feet(inter(READY, _pi_k1, 0.75), l=knee_up(0.23, 0.37, 7.0)), "inout"), (13, _pi_k1, "in2"),
    (22, _pi_lean, "inout"), (25, _pi_roll, "inout", _KAT_HAND), (28, _pi_set, "inout"), (31, _pi_let, "sine"), (38, _pi_up, "inout"),
] + pi_knee_keys((41, 44, 47, 50, 52), _pi_up, KIZA, toe("R", R_FOOT[0], R_FOOT[1], R_FOOT[2], 10.0)) + [
    (54, KIZA, "in2"), (58, _kiza_b, "sine"),
    (66, _pi_reach, "inout"), (70, _pi_take, "sine"),
    (80, _pi_flame, "inout"), (88, _pi_flame2, "sine"), (92, _pi_fan_a, "inout"), (95, _pi_fan_b, "inout"),
    (98, _pi_fan_a, "inout"), (101, _pi_fan_b, "inout"),
    (110, _pi_carry, "inout"), (116, _pi_place, "inout"), (120, _pi_after, "sine"),
    # (de las palmas juntas a la mano en el muslo en 8 cuadros: en 6 el brazo izquierdo giraba 51° en un cuadro)
    (128, _pi_palms, "inout"), (138, _pi_bow, "sine"), (145, _pi_bow2, "sine"), (149, _pi_lift, "sine"),
    (153, _pi_down, "sine", _PQ_ARM_L), (157, _pi_grab, "inout", _PQ_ARM_L), (159, _pi_grip, "sine"), (162, _pi_raise, "inout"), (165, _pi_hold, "inout", _KAT_HAND),
] + pi_knee_keys((177, 175, 172, 169, 167), _pi_lift_k, _pi_hold, hover("R", R_FOOT[0], R_FOOT[1], R_FOOT[2], 0.06)) + [
    (178, _pi_k2, "in2"),
    (180, feet(inter(_pi_k2, READY, 0.3), l=knee_up(0.24, 0.36, 12.0)), "inout", LIN_L),
    (184, feet(inter(_pi_k2, READY, 0.65), l=lifted("L", 0.28, 0.3, 0.07, 30.0, 26.0)), "inout", LIN_L),
    (188, READY, "sine")],
    # al pararse la punta del pie izquierdo roza el piso mientras el empeine se da vuelta (la rodilla ya subió): a propósito
    timing={"skid": [[180, 184]], "hand_r_m": {"incense_take": [0.29, 0.34, 0.25], "incense_light": [0.04, 0.53, 0.33],
                                                  "incense_place": [0.02, 0.27, 0.47], "katana_down": [0.31, 0.13, 0.14]},
            # dónde queda la katana en el piso (m, como hand_r_m): el centro del puño y la punta; el santuario no la tiene
            # que tapar
            "katana_floor_m": {"grip": [0.35, 0.07, 0.16], "tip": [0.79, 0.07, 0.92]},
            "katana_down": 28, "kiza": 54, "incense_take": 70, "incense_light": 88, "incense_place": 116, "palms": 128,
            "katana_up": 159, "rise": 166, "story": True},
    events=[{"frame": 28, "fn": "katana_down"}, {"frame": 70, "fn": "incense_take"}, {"frame": 88, "fn": "incense_light"},
            {"frame": 116, "fn": "incense_place"}, {"frame": 128, "fn": "palms"}, {"frame": 159, "fn": "katana_up"},
            {"frame": 166, "fn": "rise"}],
    notes="rezo con sahumerio: deja la katana, kiza, toma el sahumerio, lo prende, lo apaga con la mano, lo clava, palmas "
          "juntas y reverencia por el abuelo, retoma la katana y se para (6 s)")

# ------------------------------------------------------------------ rezo corto (visitas siguientes al santuario)
# Paso atrás con el pie izquierdo y rodilla al piso; al bajar se inclina a su derecha y apoya la katana en el piso como en
# el rezo largo (PI_KAT: el puño junto al pie, la hoja adelante y abierta), se endereza y junta las palmas delante del
# pecho (gassho: con la katana en la mano rezaba con una sola), reverencia; vuelve a tomar la katana y se para con otro
# paso. 2.3 s
# (las palmas junto al pecho, los codos doblados: a 30 cm del pecho los dos brazos quedaban estirados del todo y el codo
# izquierdo se doblaba 66° en un cuadro al soltarlas)
_pq_palms = mod(_pi_up, hips=(0.0, 0.1, -0.345), hips_rot=(4.0, 0.0, 0.0), spine=(6.0, 0.0, 0.0), head=(10.0, 0.0, 0.0),
                hand_r=(-0.05, -0.45, 1.05), hand_r_dir=(0.0, -0.15, 1.0), hand_r_up=(-1.0, 0.0, 0.0), fingers_r=0.0,
                hand_l=(0.05, -0.45, 1.05), hand_l_dir=(0.0, -0.15, 1.0), hand_l_up=(1.0, 0.0, 0.0), elbow_l=(0.8, 0.3, -0.5),
                fingers_l=0.0)
_pq_bow = mod(_pq_palms, breath=1.0, hips=(0.0, 0.1, -0.35), hips_rot=(10.0, 0.0, 0.0), spine=(14.0, 0.0, 0.0), head=(24.0, 0.0, 0.0))
_pq_bow2 = mod(_pq_bow, breath=0.3, hips=(0.0, 0.1, -0.355), head=(27.0, 0.0, 0.0))
_pq_lift = mod(_pq_palms, head=(6.0, 0.0, 0.0))
# vuelve a la katana (inclinado como al dejarla) y la levanta
# (la katana se da vuelta en el aire antes de apoyarla y después de levantarla, como en el rezo largo)
_pq_grab = mod(_pi_let, fingers_r=0.2)
# La mano izquierda va y viene de las palmas al muslo pareja (y la espalda se endereza pareja): con la curva de cada tramo el
# brazo giraba 50-57° en el cuadro del medio. Arranca a subir apenas suelta la katana (un 20 % en f23) y baja por delante del
# cuerpo (f43) mientras se inclina a buscarla
_PQ_UP = dict(_PQ_ARM_L, hips="lin", hips_rot="lin", spine="lin")
_pq_let = mod(_pi_let, **{k: v for k, v in inter(_pi_let, _pq_palms, 0.2).items() if k in _PQ_ARM_L})
_pq_down = mod(inter(_pq_lift, _pq_grab, 0.4), hand_l=(0.18, -0.45, 0.92))
add("PrayQuick", 70, [
    (0, READY, "sine"), (5, feet(inter(READY, _pi_k1, 0.45), l=lifted("L", 0.27, 0.4, 0.07, 62.0, 12.0)), "inout"),
    (8, feet(inter(READY, _pi_k1, 0.75), l=knee_up(0.24, 0.37, 10.0)), "inout"), (11, _pi_k1, "in2"),
    (15, _pi_lean, "inout"), (18, _pi_roll, "inout", _KAT_HAND), (21, _pi_set, "inout"), (23, _pq_let, "sine"),
    (28, _pq_palms, "inout", _PQ_UP),
    # (la reverencia más corta y la mano izquierda baja de las palmas al muslo en 7 cuadros: en 4 giraba 75° en uno)
    (33, _pq_bow, "sine"), (37, _pq_bow2, "sine"), (40, _pq_lift, "sine"),
    (43, _pq_down, "sine", _PQ_ARM_L), (47, _pq_grab, "inout", _PQ_ARM_L), (49, _pi_set, "sine"), (51, _pi_roll, "inout"),
    (54, _pi_lean, "inout", _KAT_HAND), (57, _pi_k2, "inout"),
    # (el pie izquierdo pasa de la punta abajo a plano en dos tiempos con la punta lejos del piso: de una vez giraba 58° en
    # un cuadro y, parejo sin la clave del medio, la punta rozaba el piso)
    (60, feet(inter(_pi_k2, READY, 0.3), l=knee_up(0.24, 0.36, 12.0)), "inout", LIN_L),
    (62, feet(inter(_pi_k2, READY, 0.5), l=swung("L", 0.26, 0.33, 0.27, (82.0, 0.0, 20.0), 0.07)), "lin", LIN_L),
    (64, feet(inter(_pi_k2, READY, 0.7), l=lifted("L", 0.28, 0.3, 0.07, 30.0, 26.0)), "inout", LIN_L),
    (67, READY, "sine"), (70, READY, "sine")],
    timing={"kneel": 11, "katana_down": 21, "palms": 28, "katana_up": 49, "rise": 57, "story": True,
            "katana_floor_m": {"grip": [0.35, 0.07, 0.16], "tip": [0.79, 0.07, 0.92]}},
    events=[{"frame": 11, "fn": "kneel"}, {"frame": 21, "fn": "katana_down"}, {"frame": 28, "fn": "palms"},
            {"frame": 49, "fn": "katana_up"}, {"frame": 57, "fn": "rise"}],
    notes="rezo corto: rodilla al piso, deja la katana a su derecha, palmas juntas y reverencia, la retoma y se para (2.3 s)")

# ------------------------------------------------------------------ el poder de la bandana (abre la muralla)
# Se planta, la mano izquierda sube a la sien y toca la bandana (glow: el código la hace brillar), baja la cabeza y junta
# fuerza (se hunde, respira), lleva la mano a la cadera (como un puño cargado) y empuja la palma adelante dando un paso con el pie izquierdo (release: la
# palma estirada hacia la muralla, los dedos arriba, el código suelta la energía), sostiene el empujón y vuelve a la
# guardia. La katana queda baja adelante a su derecha, como en la guardia (no apunta a nadie). 2.5 s
_bp_k = dict(grip=(-0.64, -0.12, 0.9), blade=(-0.2, -0.95, -0.25), edge=perp((-0.2, -0.95, -0.25), (0.0, 0.0, -1.0)),
             elbow_r=(-0.7, 0.5, -0.5))
_bp_touch = feet(mod(READY, hips=(0.0, 0.03, -0.12), hips_rot=(4.0, 0.0, 6.0), spine=(6.0, 0.0, 4.0), head=(14.0, 4.0, -6.0),
                     hand_l=(0.47, -0.3, 1.88), hand_l_dir=(-0.1, -0.2, 1.0), hand_l_up=(0.95, 0.2, 0.0), elbow_l=(0.8, 0.0, -0.5),
                     fingers_l=0.2, **_bp_k),
                 r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))
_bp_focus = mod(_bp_touch, breath=1.0, hips=(0.0, 0.04, -0.17), spine=(10.0, 0.0, 4.0), head=(20.0, 4.0, -6.0),
                hand_l=(0.46, -0.32, 1.84))
_bp_wind = feet(mod(READY, hips=(0.0, 0.06, -0.2), hips_rot=(4.0, 0.0, 22.0), spine=(4.0, 0.0, 14.0), head=(-4.0, 0.0, -24.0),
                    hand_l=(0.4, 0.1, 0.96), hand_l_dir=(0.0, -1.0, 0.05), hand_l_up=(0.15, 0.0, -1.0), elbow_l=(0.6, 0.8, -0.2),
                    fingers_l=0.6, wrist_l_open=0.0, **_bp_k),
                r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))
# la mano baja de la bandana a la cadera por delante del cuerpo, lejos del hombro: derecho, pasaba a 15 cm de él y el brazo
# se plegaba entero y se volvía a abrir (el codo 54° en un cuadro)
_bp_from_head = mod(inter(_bp_focus, _bp_wind, 0.3), hand_l=(0.5, -0.32, 1.6))
_bp_to_hip = mod(inter(_bp_focus, _bp_wind, 0.7), hand_l=(0.5, -0.18, 1.2))
_BP_LF = (0.24, -0.5, 10.0)
# el empujón con el brazo ESTIRADO (la palma a un 90 % del largo del brazo delante del hombro): antes el cuerpo avanzaba 43
# cm con el paso y la mano solo 52, así que el brazo se doblaba a mitad de camino (la muñeca pasaba a 8 cm del hombro, f38)
# y llegaba doblado: con el brazo plegado el codo y el húmero daban vuelta de un cuadro al otro (la mano 117°, el húmero 94°)
_bp_push = feet(mod(READY, hips=(0.0, -0.22, -0.2), hips_rot=(12.0, 0.0, -18.0), spine=(6.0, 0.0, -10.0), head=(-8.0, 0.0, 16.0),
                    hand_l=(0.12, -1.06, 1.36), hand_l_dir=(0.0, -0.35, 0.94), hand_l_up=(0.34, 0.9, 0.27), elbow_l=(0.7, 0.2, -0.7),
                    fingers_l=0.0, wrist_l_open=0.6, clav_l=(0.0, -10.0, 0.0), **_bp_k),
                r=toe("R", *R_FOOT, 14.0), l=flat("L", *_BP_LF))
# el envión en cuatro tiempos (la mano siempre adelante del hombro, que avanza con la cadera): carga en la cadera (f32), la
# cadera arranca y el pie izquierdo despega con la mano todavía cargada (f35), la mano sale por delante del pecho con el
# pie en el aire (f37-f39) y el pie apoya con la palma estirada (f40). Antes iba de la carga al empujón en 7 cuadros y el pie
# barría 38 cm en 3 (19 cm por cuadro junto al piso)
# (las manos de cada tiempo salen del hombro de ese cuadro: la muñeca recorre derecho la cuerda que va de la carga al
# empujón medida desde el hombro, así nunca queda a menos de un 60 % del largo del brazo)
_bp_drive = feet(mod(inter(_bp_wind, _bp_push, 0.22), hand_l=(0.42, -0.16, 1.02), fingers_l=0.6, wrist_l_open=0.1),
                 r=toe("R", *R_FOOT, 6.0), l=lifted("L", 0.29, 0.1, 0.07, 8.0, 30.0))
_bp_thrust = feet(mod(inter(_bp_wind, _bp_push, 0.6), hand_l=(0.3, -0.62, 1.16), fingers_l=0.3, wrist_l_open=0.3),
                  r=toe("R", *R_FOOT, 10.0), l=lifted("L", 0.26, -0.16, 0.09, -2.0, 20.0))
_bp_reach = feet(mod(inter(_bp_wind, _bp_push, 0.92), hand_l=(0.15, -0.98, 1.32), fingers_l=0.06, wrist_l_open=0.55),
                 r=toe("R", *R_FOOT, 13.0), l=hover("L", *_BP_LF, 0.04))
_bp_hold = mod(_bp_push, hips=(0.0, -0.23, -0.22), hand_l=(0.12, -1.08, 1.37), head=(-9.0, 0.0, 16.0))
_bp_ease = mod(_bp_push, hips=(0.0, -0.18, -0.16), hand_l=(0.2, -0.86, 1.28), hand_l_dir=(0.1, -0.6, 0.8), fingers_l=0.3,
               wrist_l_open=0.3, head=(-4.0, 0.0, 10.0))
add("BandanaPower", 75, [
    (0, READY, "sine"), (8, _bp_touch, "inout"), (14, mod(_bp_touch, hips=(0.0, 0.03, -0.14)), "sine"), (26, _bp_focus, "sine"),
    (28, _bp_from_head, "inout"), (30, _bp_to_hip, "lin"), (32, _bp_wind, "inout"), (35, _bp_drive, "in2"), (37, _bp_thrust, "lin"), (39, _bp_reach, "lin"),
    (40, _bp_push, "out"), (48, _bp_hold, "sine"), (56, mod(_bp_hold, hips=(0.0, -0.21, -0.18)), "sine"), (61, _bp_ease, "sine"),
    (66, feet(inter(_bp_ease, READY, 0.5), r=flat("R", *R_FOOT), l=lifted("L", 0.26, -0.1, 0.07, -4.0, 22.0)), "inout"),
    (70, feet(mod(READY, hips=(0.0, 0.02, -0.09)), r=flat("R", *R_FOOT), l=flat("L", *L_FOOT)), "in2"), (75, READY, "sine")],
    # (la mano sin atraso: cada tiempo del envión la deja donde la mide el hombro)
    lag=mod(LEAD, hand_l=0.0),
    timing={"glow": 14, "release": 40, "story": True, "hand_l_m": {"release": [-0.06, 0.72, 0.56]}},
    events=[{"frame": 14, "fn": "glow"}, {"frame": 40, "fn": "release"}],
    notes="toca la bandana (glow), junta fuerza y empuja la palma hacia la muralla con un paso (release); vuelve a la guardia")

# ------------------------------------------------------------------ final: se da vuelta y le ofrece la media cinta a Kokuyō
# El transform ya mira a Kokuyō y está medio metro más cerca de él (StoryDirector.OfferRibbon): el clip arranca
# con el cuerpo como estaba (de espaldas, mirando al abuelo, 0.55 m atrás: 'turn' 180 y 'shift') y cuadro a cuadro gira
# a su derecha y se acerca en tres pasos (la cabeza adelante del pecho y el pecho de la cadera); se endereza, saca la
# cinta del cinturón con la izquierda (ribbon) y se la ofrece con la palma arriba, con una reverencia chica (offer). La
# katana va baja a su derecha, la punta adelante y abajo, lejos del piso. Queda ofreciendo (la escena sigue con Kokuyō)
ET_SHIFT = 0.55 * U
_ET_R0 = (0.22, 0.14 + ET_SHIFT, 186.0)          # las huellas de la guardia giradas 180° y corridas
_ET_L0 = (-0.30, -0.22 + ET_SHIFT, 214.0)
# la katana baja adelante y abierta a su derecha, la punta a 13 cm del piso (envainar no puede: no tiene vaina): con la
# punta atrás la arrastraba por el piso los 2.3 m del giro y de los pasos, y la muñeca iba al tope
_et_k = dict(grip=(-0.68, -0.08, 0.98), blade=(-0.25, -0.86, -0.45), edge=perp((-0.25, -0.86, -0.45), (-0.89, 0.4, -0.21)),
             elbow_r=(-0.7, 0.5, -0.5))
_et0 = feet(mod(READY, turn=180.0, shift=(0.0, ET_SHIFT, 0.0)), r=flat("R", *_ET_R0), l=flat("L", *_ET_L0))
_et_look = feet(mod(READY, turn=176.0, shift=(0.0, ET_SHIFT, 0.0), spine=(6.0, 0.0, -24.0), head=(-4.0, 0.0, -48.0)),
                r=flat("R", *_ET_R0), l=flat("L", *_ET_L0))
_et_s1 = feet(mod(READY, turn=128.0, shift=(0.0, 0.82 * ET_SHIFT, 0.0), hips_rot=(4.0, 0.0, -10.0), spine=(5.0, 0.0, -18.0),
                  head=(-4.0, 0.0, -24.0), **_et_k),
              r=lifted("R", 0.14, 0.86, 0.09, 0.0, 160.0), l=flat("L", *_ET_L0))
_ET_R1 = (0.03, 0.52, 92.0)
_et_s1b = feet(mod(_et_s1, turn=96.0, shift=(0.0, 0.62 * ET_SHIFT, 0.0), head=(-4.0, 0.0, -18.0)), r=flat("R", *_ET_R1),
               l=toe("L", *_ET_L0, 14.0))
# el pie izquierdo que despega del giro sobre la punta ya va medio desenroscado con el cuerpo (130°: sale de 214° y apoya en
# 34°) y viaja parejo: con 196° viajaba de espaldas al cuerpo y giraba 160° en el aire, 56° por cuadro antes de apoyar
_et_s2 = feet(mod(_et_s1b, turn=52.0, shift=(0.0, 0.34 * ET_SHIFT, 0.0), spine=(5.0, 0.0, -10.0), head=(-4.0, 0.0, -10.0)),
              r=flat("R", *_ET_R1), l=lifted("L", 0.05, 0.42, 0.09, 4.0, 130.0))
_et_s2b = feet(mod(_et_s2, turn=22.0, shift=(0.0, 0.14 * ET_SHIFT, 0.0), spine=(5.0, 0.0, -4.0), head=(-2.0, 0.0, -4.0)),
               r=toe("R", *_ET_R1, 14.0), l=flat("L", *L_FOOT))
_et_s3 = feet(mod(_et_s2b, turn=6.0, shift=(0.0, 0.04 * ET_SHIFT, 0.0), head=(0.0, 0.0, 0.0)),
              r=lifted("R", -0.12, 0.16, 0.09, 0.0, 74.0), l=flat("L", *L_FOOT))
_et_stand = feet(mod(READY, turn=0.0, shift=(0.0, 0.0, 0.0), hips=(0.0, 0.03, -0.06), hips_rot=(0.0, 0.0, 10.0), spine=(2.0, 0.0, -6.0), head=(2.0, 0.0, -4.0),
                     hand_l=(0.34, -0.22, 1.08), **_et_k),
                 r=flat("R", *R_FOOT), l=flat("L", *L_FOOT))
# saca la cinta del cinturón (adelante a su izquierda)
_et_take = mod(_et_stand, head=(14.0, 0.0, 0.0), hand_l=(0.22, -0.4, 0.98), hand_l_dir=(-0.3, -0.6, -0.75), hand_l_up=(0.8, -0.5, 0.3),
               elbow_l=(0.8, 0.3, -0.5), fingers_l=0.7)
# la ofrece con la palma arriba y una reverencia chica, mirando a Kokuyō (arrodillado: más abajo que él)
_et_offer = mod(_et_stand, hips=(0.0, 0.05, -0.08), hips_rot=(6.0, 0.0, 6.0), spine=(12.0, 0.0, -2.0), head=(16.0, 0.0, -2.0),
                hand_l=(0.12, -0.76, 1.2), hand_l_dir=(-0.1, -0.99, 0.05), hand_l_up=(0.0, 0.0, -1.0), elbow_l=(0.6, 0.5, -0.6),
                fingers_l=0.3)
_et_offer_b = mod(_et_offer, breath=1.0, head=(18.0, 3.0, -2.0), hand_l=(0.12, -0.77, 1.21))
_et_offer_c = mod(_et_offer, breath=0.3, head=(17.0, 4.0, -2.0))
# el giro de cada pie cambia mucho de un paso al otro (hasta 180°): sin tope en cada clave, el arco de la curva se pasaba
# de largo y un pie ya apoyado seguía girando (la punta barría 1-3 cm por cuadro)
_ET_STOP = ("foot_r_rot", "foot_l_rot")
add("EndingTurn", 84, [
    (0, _et0, "sine"), (7, _et_look, "inout", {"stop": _ET_STOP}), (13, _et_s1, "inout", {"turn": "sine", "stop": _ET_STOP}),
    (18, _et_s1b, "in2", {"turn": "lin", "stop": _ET_STOP}), (24, _et_s2, "inout", {"turn": "lin", "foot_l": "lin", "stop": _ET_STOP}),
    (29, _et_s2b, "in2", {"turn": "sine", "stop": _ET_STOP}), (34, _et_s3, "inout", {"stop": _ET_STOP}),
    (39, _et_stand, "in2", {"stop": _ET_STOP}),
    (46, _et_take, "inout"), (50, mod(_et_take, fingers_l=1.0), "sine"), (61, _et_offer, "inout"), (72, _et_offer_b, "sine"),
    (84, _et_offer_c, "sine")],
    timing={"turned": 39, "ribbon": 50, "offer": 61, "story": True, "shift_m": 0.55,
            "hand_l_m": {"ribbon": [-0.12, 0.51, 0.21], "offer": [-0.06, 0.64, 0.4]}},
    events=[{"frame": 39, "fn": "turned"}, {"frame": 50, "fn": "ribbon"}, {"frame": 61, "fn": "offer"}],
    notes="se da vuelta hacia Kokuyō en tres pasos acercándose 0.55 m, saca la media cinta y se la ofrece con la palma "
          "arriba; queda ofreciendo (2.8 s)")

# ------------------------------------------------------------------ prólogo: se despierta
# Sin katana (todavía es la guadaña: el código la esconde): la mano derecha va suelta todo el clip y recién al final
# vuelve a la guardia de siempre (la del Idle, con el puño cerrado). Boca abajo después del golpe, la cara de costado;
# respira, los dedos se mueven; levanta la cabeza aturdido, las manos debajo de los hombros, se empuja con los brazos
# (cuesta: el pecho sube en dos tiempos), sacude la cabeza, trae las rodillas y queda en cuatro patas, adelanta el pie
# derecho (una rodilla), se toca la cabeza, VE el secuestro (la cabeza se levanta de golpe, los hombros suben) y se para
# de un envión, un paso adelante con la mano estirada hacia el abuelo; termina en la guardia. El abuelo va ADELANTE (el
# código lo pone mirando hacia él). 3.6 s
_wk = dict(kat_free=1.0, kat_pos=(-0.9, 0.2, 0.06), kat_blade=(0.0, 1.0, 0.0), kat_edge=(1.0, 0.0, 0.0), arm_space=0.0)
_WK_LEGS = dict(knee_r=(-0.1, -0.2, -1.0), knee_l=(0.1, -0.2, -1.0))
PRONE = feet(mod(READY, hips=(0.0, 0.62, -0.31), hips_rot=(86.0, 0.0, 4.0), spine=(4.0, 0.0, 0.0), head=(-36.0, 6.0, 70.0),
                 hand_r=(-0.62, -0.28, 0.14), hand_r_dir=(-0.2, -0.95, 0.0), hand_r_up=(0.0, 0.0, 1.0), fingers_r=0.35,
                 hand_l=(0.55, -0.72, 0.14), hand_l_dir=(0.3, -0.9, 0.0), hand_l_up=(0.0, 0.0, 1.0), elbow_l=(0.8, 0.2, 0.3),
                 elbow_r=(-0.8, 0.4, 0.2), fingers_l=0.4, wrist_l_open=0.75, wrist_r_open=0.75, **_wk, **_WK_LEGS),
             r=((-0.22, 1.07, 0.13), (20.0, 180.0, -186.0)), l=((0.22, 1.09, 0.13), (18.0, -180.0, 186.0)))
_wk_breath = mod(PRONE, breath=1.0, hips=(0.0, 0.62, -0.30))
_wk_twitch = mod(PRONE, fingers_l=0.85, hand_l=(0.55, -0.7, 0.14))
# levanta la cabeza (sigue de costado) y trae las manos debajo de los hombros
_wk_hands = mod(PRONE, head=(-34.0, 4.0, 40.0), hand_r=(-0.5, -0.32, 0.18), hand_r_dir=(-0.1, -0.99, 0.0),
                hand_l=(0.5, -0.32, 0.18), hand_l_dir=(0.1, -0.99, 0.0), fingers_l=0.15, fingers_r=0.15,
                elbow_l=(0.8, 0.5, 0.2), elbow_r=(-0.8, 0.5, 0.2))
_wk_push1 = mod(_wk_hands, hips=(0.0, 0.62, -0.23), hips_rot=(76.0, 0.0, 2.0), spine=(-2.0, 0.0, 0.0), head=(-8.0, 0.0, 10.0))
_wk_sag = mod(_wk_push1, hips=(0.0, 0.62, -0.25), hips_rot=(80.0, 0.0, 2.0), head=(4.0, 0.0, 6.0))
_wk_push2 = mod(_wk_hands, hips=(0.0, 0.62, -0.22), hips_rot=(70.0, 0.0, 0.0), spine=(-6.0, 0.0, 0.0), head=(10.0, 0.0, -14.0))
_wk_shake = mod(_wk_push2, head=(12.0, 0.0, 14.0))
# cuatro patas: las rodillas debajo de la cadera, los dedos de los pies doblados
# (los pies con el empeine en el piso escritos con la vuelta de 180°, como el kiza de PrayIncense: para pasar a una
# rodilla cada pie da la vuelta por el costado, con la punta abajo el tobillo subía hasta la cadera y la rodilla saltaba)
_WK_KR, _WK_KL = ((-0.21, 0.9, 0.13), (20.0, 180.0, -184.0)), ((0.21, 0.9, 0.13), (20.0, -180.0, 184.0))
_wk_fours = feet(mod(_wk_push2, hips=(0.0, 0.62, -0.26), hips_rot=(76.0, 0.0, 0.0), hand_r=(-0.5, -0.32, 0.18), hand_l=(0.5, -0.32, 0.18), spine=(-4.0, 0.0, 0.0), head=(-6.0, 0.0, -6.0),
                     knee_r=(-0.1, -0.7, -0.7), knee_l=(0.1, -0.7, -0.7)),
                 r=_WK_KR, l=_WK_KL)
_wk_knees = feet(inter(_wk_push2, _wk_fours, 0.5), r=((-0.21, 1.02, 0.2), (20.0, 180.0, -185.0)),
                 l=((0.21, 1.02, 0.2), (20.0, -180.0, 185.0)))
# una rodilla: el pie derecho adelante, el torso se levanta, la mano izquierda a la cabeza
_WK_RF = (-0.24, 0.28, 4.0)
_wk_one = feet(mod(_wk_fours, hips=(0.0, 0.46, -0.32), hips_rot=(14.0, 0.0, 4.0), spine=(10.0, 0.0, 0.0), head=(18.0, 0.0, 10.0),
                   hand_r=(-0.32, 0.12, 0.74), hand_r_dir=(0.0, -0.9, -0.4), hand_r_up=(-0.3, 0.0, 0.95),
                   hand_l=(0.4, -0.22, 1.72), hand_l_dir=(-0.2, 0.1, 1.0), hand_l_up=(0.95, -0.2, 0.1), elbow_l=(0.8, -0.3, -0.5),
                   fingers_l=0.3, knee_r=(-0.2, -1.0, 0.0), wrist_l_open=0.0, wrist_r_open=0.0),
               r=flat("R", *_WK_RF), l=_WK_KL)
_wk_step_r = feet(inter(_wk_fours, _wk_one, 0.5), r=lifted("R", -0.23, 0.6, 0.09, 20.0, 0.0), l=_WK_KL)
_wk_daze = mod(_wk_one, head=(22.0, -4.0, 14.0), hand_l=(0.4, -0.2, 1.7))
# lo ve: la cabeza arriba de golpe, los hombros suben, la mano baja
_wk_see = mod(_wk_one, hips_rot=(4.0, 0.0, 0.0), spine=(-2.0, 0.0, 0.0), head=(-14.0, 0.0, 0.0), clav_r=(0.0, -6.0, 0.0),
              clav_l=(0.0, 6.0, 0.0), hand_l=(0.44, -0.3, 1.2), hand_l_dir=(0.1, -0.6, 0.8), hand_l_up=(0.9, 0.0, -0.4),
              fingers_l=0.1)
_wk_see2 = mod(_wk_see, head=(-16.0, 0.0, 2.0), hips=(0.0, 0.46, -0.31))
# envión: se para sobre la derecha, el pie izquierdo viene a su huella
_wk_rise = feet(mod(READY, hips=(0.0, 0.24, -0.2), hips_rot=(20.0, 0.0, 6.0), spine=(10.0, 0.0, 0.0), head=(-14.0, 0.0, -2.0),
                    hand_r=(-0.4, 0.1, 0.9), hand_r_dir=(0.0, -0.6, -0.8), hand_r_up=(-0.9, 0.0, 0.3),
                    hand_l=(0.4, -0.44, 1.22), hand_l_dir=(0.1, -0.8, 0.5), hand_l_up=(0.9, 0.0, -0.3), fingers_l=0.1, **_wk),
                r=flat("R", *_WK_RF), l=lifted("L", 0.28, 0.52, 0.09, 30.0, 20.0))
_wk_up = feet(mod(_wk_rise, hips=(0.0, 0.12, -0.1), hips_rot=(16.0, 0.0, 8.0), head=(-12.0, 0.0, -2.0)),
              r=toe("R", *_WK_RF, 20.0), l=flat("L", *L_FOOT))
# un paso adelante con la derecha, estirando la mano hacia el abuelo
_wk_reach = feet(mod(_wk_up, hips=(0.0, -0.06, -0.1), hips_rot=(18.0, 0.0, 10.0), spine=(8.0, 0.0, -4.0), head=(-12.0, 0.0, -4.0),
                     hand_l=(0.3, -0.84, 1.3), hand_l_dir=(-0.1, -0.95, 0.2), hand_l_up=(0.2, 0.0, 0.98), fingers_l=0.15),
                 r=flat("R", *R_FOOT), l=toe("L", *L_FOOT, 24.0))
_wk_step = feet(inter(_wk_up, _wk_reach, 0.5), r=lifted("R", -0.23, 0.08, 0.08, -4.0, 4.0), l=toe("L", *L_FOOT, 14.0))
# la guardia (sin katana: el puño derecho vuelve al lugar del agarre del Idle)
_wk_ready = mod(READY, hips=(0.0, 0.0, -0.1), hips_rot=(8.0, 0.0, 12.0), head=(-10.0, 0.0, -4.0), kat_free=0.4,
                kat_pos=(-0.9, 0.2, 0.06), kat_blade=(0.0, 1.0, 0.0), kat_edge=(1.0, 0.0, 0.0),
                hand_r=(-0.56, -0.28, 1.0), hand_r_dir=(-0.2, -0.9, -0.3), hand_r_up=(-0.9, 0.2, 0.3), fingers_r=0.8)
add("WakeUp", 108, [
    (0, PRONE, "sine"), (8, _wk_breath, "sine"), (13, _wk_twitch, "sine"), (18, PRONE, "sine"),
    (28, _wk_hands, "inout"), (36, _wk_push1, "out"), (40, _wk_sag, "sine"), (47, _wk_push2, "inout"), (51, _wk_shake, "sine"),
    (55, _wk_push2, "sine"),
    # (el pie derecho da la vuelta de empeine en el piso a plano en 14 cuadros, ~20° por cuadro: en 11 la punta barría 12-14
    # cm por cuadro junto al piso)
    # (la mano izquierda sube del piso a la sien pareja, ~11 cm por cuadro: con la mezcla de las poses subía 38 cm en dos
    # cuadros mientras el hombro subía la mitad y el codo, estirado empujando el piso, se doblaba 52° en uno)
    (59, _wk_knees, "inout"), (62, _wk_fours, "in2"),
    (64, feet(mod(inter(_wk_fours, _wk_step_r, 0.5), hand_l=(0.486, -0.306, 0.4), knee_at_r=(-0.33, 0.55, 0.18), knee_guide_r=1.0),
              r=swung("R", -0.41, 0.8, 0.2, (18.0, 140.0, -150.0))), "inout", LIN_R),
    (67, feet(mod(_wk_step_r, hand_l=(0.464, -0.284, 0.73), knee_at_r=(-0.39, 0.42, 0.25), knee_guide_r=1.0), r=swung("R", -0.5, 0.62, 0.2, (15.0, 90.0, -115.0), 0.08)),
     "inout", LIN_R),
    (71, feet(mod(inter(_wk_step_r, _wk_one, 0.25), hand_l=(0.436, -0.256, 1.17), knee_at_r=(-0.33, 0.3, 0.31), knee_guide_r=1.0),
              r=swung("R", -0.44, 0.48, 0.25, (12.0, 52.0, -68.0), 0.08)), "inout", LIN_R),
    (74, feet(mod(inter(_wk_step_r, _wk_one, 0.5), hand_l=(0.414, -0.234, 1.5), knee_at_r=(-0.28, 0.2, 0.38), knee_guide_r=1.0),
              r=swung("R", -0.32, 0.34, 0.23, (8.0, 16.0, -22.0), 0.08)), "inout", LIN_R),
    (76, mod(_wk_one, knee_at_r=(-0.21, 0.12, 0.44), knee_guide_r=1.0), "sine", LIN_R), (78, _wk_daze, "sine"),
    # (la cabeza se levanta de golpe; la mano que baja de la sien y el cuerpo, no: con la misma curva la mano giraba 51° en un
    # cuadro y la cadera, que va adelantada, ya pegaba el salto en f77-f78 y estiraba el brazo derecho 47°)
    (80, _wk_see, "snap", {"hand_l": "inout", "hand_l_dir": "inout", "hand_l_up": "inout", "hips": "inout", "hips_rot": "inout", "spine": "inout"}), (84, _wk_see2, "sine"),
    # (el pie izquierdo del envión gira parejo, ~20° por cuadro)
    (86, feet(mod(inter(_wk_see2, _wk_rise, 0.4), knee_at_l=(0.33, 0.46, 0.25), knee_guide_l=1.0),
              r=flat("R", *_WK_RF), l=swung("L", 0.41, 0.7, 0.2, (18.0, -140.0, 150.0))), "inout", LIN_L),
    (89, feet(mod(_wk_rise, knee_at_l=(0.39, 0.27, 0.33), knee_guide_l=1.0), l=swung("L", 0.46, 0.46, 0.24, (15.0, -90.0, 110.0))),
     "out", LIN_L),
    # (el pie derecho a medio levantar el talón sobre su punta: mezclada, la clave lo dejaba fuera del giro sobre la
    # punta y la suela se corría 2.9 cm antes del envión)
    (91, feet(mod(inter(_wk_rise, _wk_up, 0.5), knee_at_l=(0.37, 0.12, 0.38), knee_guide_l=1.0),
              r=toe("R", *_WK_RF, 10.0), l=swung("L", 0.4, 0.34, 0.26, (11.0, -45.0, 62.0))), "inout", LIN_L),
    (93, _wk_up, "in2", LIN_L), (96, _wk_step, "inout"), (99, _wk_reach, "in2"),
    (104, _wk_ready, "sine"), (108, mod(READY, fingers_r=1.0), "sine")],
    lag=mod(LEAD, hand_l=0.0),
    timing={"push": 36, "fours": 63, "see": 80, "stand": 93, "story": True},
    events=[{"frame": 28, "fn": "stir"}, {"frame": 80, "fn": "see"}, {"frame": 93, "fn": "stand"}],
    notes="boca abajo y aturdido, se empuja con los brazos, cuatro patas, una rodilla, ve el secuestro y se para de un "
          "envión con un paso hacia el abuelo (3.6 s)")


# =========================================================================== empalmes
# (clip, cuadro (-1 = el último), clip siguiente, cuadro en que arranca, tope en grados): los crossfades cortos
# del código. Los del combo son exactos, los del contraataque casi (en el f2 del Corte 1 la mano libre todavía
# trae 0.4 cuadros de atraso: 4°); el corte buffereado desde el dash (0.05 s de
# fundido desde f11) tolera la caída, y el salto del remate corto (0.12 s de fundido de f71 al final del zanshin) el
# giro de la cabeza
RIPOSTE_FRAME = 2
CHAINS = [
    ("Attack1", -1, "Attack2", 0, 1.0), ("Attack2", -1, "Attack3", 0, 1.0), ("Attack3", -1, "Attack1", 0, 1.0),
    ("Attack3", -1, "Idle", 0, 1.0),
    ("ParrySuccessR", -1, "Attack1", RIPOSTE_FRAME, 6.0), ("ParrySuccessL", -1, "Attack1", RIPOSTE_FRAME, 6.0),
    ("PerfectParry", -1, "Attack1", RIPOSTE_FRAME, 6.0), ("ParryStance", 2, "ParrySuccessR", 0, 1.0),
    # la réplica pedida sale en la carga (PlayerController.RiposteReady: el desvío se acelera hasta ahí) con 0.06 s de
    # fundido: f5 de los desvíos, f8 del perfecto ('counter_ready')
    ("ParrySuccessR", 5, "Attack1", RIPOSTE_FRAME, 8.0), ("ParrySuccessL", 5, "Attack1", RIPOSTE_FRAME, 8.0),
    ("PerfectParry", 8, "Attack1", RIPOSTE_FRAME, 6.0),
    ("Dash", 11, "Attack1", 0, 10.0), ("Dash", -1, "Idle", 0, 12.0), ("ParryStance", -1, "Idle", 0, 1.0),
    ("Blocked", -1, "Idle", 0, 1.0), ("Hit", -1, "Idle", 0, 1.0), ("HitHeavy", -1, "Idle", 0, 1.0),
    ("Finisher", FINISHER_SKIP_FROM, "Finisher", FINISHER_HOLD_END, 20.0), ("Finisher", -1, "Idle", 0, 1.0), ("WindSlash", -1, "Idle", 0, 1.0),
    ("Whirlwind", -1, "Idle", 0, 1.0), ("Pray", -1, "Idle", 0, 1.0), ("Interact", -1, "Idle", 0, 1.0),
    ("HitBack", -1, "Idle", 0, 1.0), ("HitLeft", -1, "Idle", 0, 1.0), ("HitRight", -1, "Idle", 0, 1.0),
    ("PrayQuick", -1, "Idle", 0, 1.0), ("PrayIncense", -1, "Idle", 0, 1.0),
    ("BandanaPower", -1, "Idle", 0, 1.0), ("WakeUp", -1, "Idle", 0, 1.0),
] + [(st, -1, "Idle", 0, 1.0) for st in RUN_STOP_PHASE] + [("Run", ph, st, 0, 2.0) for st, ph in RUN_STOP_PHASE.items()]
# vueltas a la guardia sin empalme (clip, guardia, tope en grados de la katana): un corte que no encadena espera en su pose
# final y Locomotion entra con 0.12 s de fundido (PlayerController.TickAttack). Se miden en build_kaito (return_report)
RETURNS = [("Attack1", "Idle", 110.0), ("Attack2", "Idle", 150.0)]
