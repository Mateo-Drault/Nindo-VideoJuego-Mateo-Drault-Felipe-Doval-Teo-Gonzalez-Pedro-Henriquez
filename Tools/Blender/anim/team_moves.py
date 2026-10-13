"""Locomoción de pelea y golpes de zona del ninja y del sumo (ítem 6 del traspaso, parte del ninja y del sumo).

Locomoción direccional (Enemy.Locomotion.cs): los controllers del ninja y del sumo tienen un blend tree 2D (VelX/VelZ, la
velocidad en el marco del enemigo) con estos ciclos alrededor de un LocoIdle quieto, TODOS del largo de Walk (Unity los
mezcla normalizados en el tiempo: con largos distintos el paso cambiaba de ritmo en cada mezcla y los pies patinaban):
  StrafeL / StrafeR  de costado hacia su izquierda / derecha, a la velocidad de caminar del arquetipo
  WalkBack           para atrás en guardia (cuando Kaito se le viene encima y vuelve a su distancia)
  LocoIdle           la guardia quieta del centro: mezclada con un ciclo acorta el paso sin cambiar el ritmo
Todos apoyan el pie derecho en el cuadro 0, como Walk (las mezclas no cruzan los pies).

Golpes de zona que reusaban un clip con otra embestida (los pies patinaban la diferencia):
  ninja  Whirl    el remolino del lago: una vuelta entera en el aire con la hoja horizontal (1.1 m)
         Leap     el salto del bambú: se agacha, salta en arco alto, parte de arriba al caer (4.4 m)
         HopBack  el repliegue del bambú: agachado, empuja y salta 3 m para atrás en arco, cae amortiguando
  sumo   Morote   el empujón a dos manos del lago: dos pasos que empujan con los dos brazos estirados (1.6 m)
         HopSideR / HopSideL  la finta del bambú: un salto pesado de 2.6 m de costado (Enemy elige el lado)
El arpón del lago (Thrust con 2.4 m en vez de 3.2) no necesita clip: en el vuelo los pies del Thrust van con el avance
del transform y aterrizan cuando terminó (lo mide build_team_anims.variant_skate).
Las embestidas van en cuadros del clip (clip_lunge_travel, AttackDef.lungeFrom).
Marco de autoría de team_rig: metros del juego, frente -Y, izquierda del personaje +X, origen en el transform.
"""
import math
from mathutils import Matrix
import nindo_anim as NA
import team_rig as T

Key = NA.Key
FPS = T.FPS


# ============================================================================== embestida en cuadros del clip
# Enemy.Locomotion.cs (AttackDef.lungeFrom): la embestida arranca en el cuadro 'lunge_from' y el transform recorre en cada
# cuadro entero del clip lo que dice esta tabla (la embestida en el tiempo tomada cuando el clip llega a ese cuadro),
# interpolando entre cuadros con la misma curva que Unity le pone al clip. Con el avance lineal en el tiempo y la suelta
# acelerando (u²) el transform se adelantaba hasta 0.6 m dentro del primer cuadro de la suelta y los pies apoyados
# patinaban. La embestida acelera pareja al arrancar y, en el piso, frena pareja al final (sin quiebres donde el pie
# despega o queda clavado).
MAX_CLIP_LUNGE = 16.0        # Enemy.MaxClipLunge (m/s, lo más rápido)
LUNGE_ACCEL, LUNGE_BRAKE = 0.2, 0.2     # Enemy.LungeAccel / LungeBrake


def lunge_peak(brake):
    return 1.0 / (1.0 - 0.5 * LUNGE_ACCEL - 0.5 * brake)


def lunge_profile(u, brake):
    """Enemy.ProfileLunge: parte del recorrido hecha a la fracción u del tiempo de la embestida."""
    u = min(1.0, max(0.0, u))
    a = LUNGE_ACCEL
    if u < a:
        g = u * u / (2.0 * a)
    elif u <= 1.0 - brake:
        g = u - 0.5 * a
    else:
        g = 1.0 - 0.5 * a - 0.5 * brake - (1.0 - u) ** 2 / (2.0 * max(1e-4, brake))
    return g * lunge_peak(brake)


def time_at(tl, norm):
    """StepTimeline.TimeAt: el primer segundo del paso en que el clip llega a 'norm' (NormAt es monótona)."""
    lo, hi = 0.0, 30.0
    for _ in range(90):
        m = 0.5 * (lo + hi)
        if tl.norm_at(m) >= norm:
            hi = m
        else:
            lo = m
    return hi


def clip_lunge_travel(n, apex, contact, lunge, windup, lunge_from, speed=1.0, end_frame=None, air=False):
    """(recorrido del transform en cada cuadro 0..n, StepTimeline) de Enemy.SetupLunge/LungeAt: de lunge_from al golpe más
    0.05 del paso (sin pasar de MAX_CLIP_LUNGE) o, en los saltos sin daño, hasta el cuadro en que cae ('end_frame'). 'air'
    (AttackDef.lungeAir): no frena al final."""
    tl = NA.StepTimeline(n, apex, contact, windup_min=windup, speed=speed, creep_in=True)
    brake = 0.0 if air else LUNGE_BRAKE
    s = time_at(tl, lunge_from / float(n))
    e = time_at(tl, end_frame / float(n)) if end_frame is not None else max(tl.T + 0.05 * tl.step_len, s + lunge * lunge_peak(brake) / MAX_CLIP_LUNGE)
    return [round(lunge * lunge_profile((time_at(tl, k / float(n)) - s) / max(0.01, e - s), brake), 4) for k in range(n + 1)], tl


def knot_tangent(a, b, c):
    """Enemy.Tangent: la media de los dos tramos, cero en un extremo o un tramo quieto, como mucho 3 veces el más corto."""
    d0, d1 = b - a, c - b
    if d0 * d1 <= 0.0:
        return 0.0
    lim = 3.0 * min(abs(d0), abs(d1))
    return max(-lim, min(lim, 0.5 * (d0 + d1)))


def knot_curve(tr, f):
    """Enemy.LungeAt entre cuadros: cúbica por la tabla con tangentes automáticas que no se pasan (como la curva de Unity)."""
    n = len(tr) - 1
    k = min(int(f), n - 1)
    K = lambda i: tr[min(n, max(0, i))]
    p0, a, b, p3 = K(k - 1), K(k), K(k + 1), K(k + 2)
    ma, mb = knot_tangent(p0, a, b), knot_tangent(a, b, p3)
    s = f - k
    s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * a + (s3 - 2 * s2 + s) * ma + (-2 * s3 + 3 * s2) * b + (s3 - s2) * mb


# ============================================================================== saltos con el reloj del juego
def frame_times(n, apex, contact, windup, speed=1.0, hz=2400.0):
    """Segundo del paso (reloj de Enemy: StepTimeline, con la pausa que deriva hasta el apex de los golpes con lungeFrom) en
    que se muestra cada cuadro entero del clip, 0..n."""
    tl = NA.StepTimeline(n, apex, contact, windup_min=windup, speed=speed, creep_in=True)
    out, t, f = [0.0], 0.0, 1
    while f <= n:
        t += 1.0 / hz
        if tl.norm_at(t) * n >= f - 1e-9:
            out.append(t)
            f += 1
    return out


def hop_arc(times, f0, f1, height):
    """Altura (m) de un salto balístico que despega en el cuadro f0 y cae en f1, medida con el reloj del juego (la
    suelta acelera el clip: un arco autorado por cuadros quedaba torcido en el tiempo, subía lento y caía de golpe)."""
    t0, t1 = times[f0], times[f1]

    def z(f):
        i = max(0, min(len(times) - 2, int(math.floor(f))))
        t = times[i] + (times[i + 1] - times[i]) * (f - i)
        if t <= t0 or t >= t1:
            return 0.0
        u = (t - t0) / (t1 - t0)
        return 4.0 * height * u * (1.0 - u)
    return z


class ArcClip(T.TeamClip):
    """TeamClip con el arco de un salto sumado a la cadera y a las manos (los pies llevan el suyo en sus FootKey): las
    claves dicen la pose del cuerpo y el arco cuánto subió el cuerpo entero en ese cuadro."""

    def __init__(self, *a, arc=None, **kw):
        super().__init__(*a, **kw)
        self.arc = arc

    # lo que se pide en el marco de autoría (no relativo al cuerpo) sube con el arco: si no, las manos se quedaban abajo
    LIFTED = ("hips", "grip", "hand_r", "hand_l")

    def controls(self, f):
        c = super().controls(f)
        dz = self.arc(f) if self.arc is not None else 0.0
        if dz:
            for k in self.LIFTED:
                if c.get(k) is not None:
                    p = NA.V(c[k])
                    c[k] = (p.x, p.y, p.z + dz)
        return c


def static_loop(name, n, pose, feet, note):
    """Una pose quieta en loop (el centro del blend tree 2D): mismo largo que los ciclos con los que se mezcla."""
    return T.TeamClip(name, n, [Key(0, pose), Key(n, pose, "sine")], loop=True, feet=feet, tremble=0.0, notes=note)


# ============================================================================== pasos en cualquier dirección
def gait_dir(ch, frames, vel, duty, feet, lift=0.06, strike=-10.0, off=20.0, phase_l=0.5, swing_ease="inout"):
    """Ciclo en el lugar con el transform yendo a 'vel' (vx, vy) m/s del marco de autoría y los pies clavados en el MUNDO:
    el apoyado va en el clip para el otro lado exactamente a la velocidad del suelo; el vuelo sale y llega quieto en el
    mundo. feet = {k: (x medio, y medio, yaw)}. 'strike' es el giro del pie al apoyar (< 0 de talón, > 0 de punta) y
    'off' al despegar (> 0 sobre la punta, < 0 sobre el talón): para atrás se apoya de punta y se despega de talón.
    Devuelve fn(f) -> {foot_k, foot_k_rot}."""
    Tc = frames / FPS
    vx, vy = vel

    def one(k, f):
        x, y, yaw = feet[k]
        p = ((f / frames) + (phase_l if k == "l" else 0.0)) % 1.0
        if p < duty:
            u = p - duty * 0.5
            hs, to = 0.14 * duty, 0.62 * duty
            if p < hs:
                pitch = strike * (1.0 - NA.ease("out2", p / hs))
            elif p > to:
                pitch = off * NA.ease("in2", (p - to) / (duty - to))
            else:
                pitch = 0.0
            return ch.foot_at(k, x - vx * Tc * u, y - vy * Tc * u, yaw, pitch)
        q = (p - duty) / (1.0 - duty)
        s = NA.ease(swing_ease, q)
        x0, y0 = x - vx * Tc * duty * 0.5, y - vy * Tc * duty * 0.5
        px = x0 - vx * Tc * (1.0 - duty) * q + vx * Tc * s
        py = y0 - vy * Tc * (1.0 - duty) * q + vy * Tc * s
        z = lift * math.sin(math.pi * q) ** 0.8
        return ch.foot_at(k, px, py, yaw, off * (1.0 - s) + strike * s, 0.0, z)

    def fn(f):
        out = {}
        for k in "rl":
            out["foot_" + k], out["foot_%s_rot" % k] = one(k, f)
        return out
    return fn


def step_close(ch, sub, speed, sgn, x_mid, feet, lift=0.045, off=8.0):
    """Paso y arrime de costado (suri-ashi del sumo) a 'speed' m/s hacia +X ('sgn' 1) o -X: en cada tramo de 'sub' cuadros
    el pie de adelante abre largo y despacio, y después el de atrás se arrima rápido, sin cruzarse nunca. Los pies van
    clavados en el MUNDO (el apoyado va en el clip para el otro lado a la velocidad del suelo) y casi no se despegan.
    feet = {k: (y, yaw)}; x_mid = {k: x medio}. Devuelve fn(f) -> {foot_k, foot_k_rot}."""
    D = speed * sub / FPS
    lead = "l" if sgn > 0 else "r"
    win = {lead: (0.0, 0.40), ("r" if lead == "l" else "l"): (0.50, 0.78)}

    def prog(k, u):
        a, b = win[k]
        if u <= a:
            return 0.0, -1.0
        if u >= b:
            return 1.0, -1.0
        q = (u - a) / (b - a)
        return NA.ease("inout", q), q

    def mean_s(k):
        a, b = win[k]
        return 1.0 - 0.5 * (a + b)

    def one(k, f):
        u = (f % sub) / float(sub)
        s, q = prog(k, u)
        y, yaw = feet[k]
        x = x_mid[k] + sgn * D * (s - u - (mean_s(k) - 0.5))
        z = lift * math.sin(math.pi * q) if q >= 0.0 else 0.0
        pitch = off * math.sin(math.pi * q) if q >= 0.0 else 0.0
        return ch.foot_at(k, x, y, yaw, pitch, 0.0, z)

    def fn(f):
        out = {}
        for k in "rl":
            out["foot_" + k], out["foot_%s_rot" % k] = one(k, f)
        return out
    return fn, win


def _sway(f, n, duty):
    """(lateral, baja) de la cadera: el peso pasa sobre el pie apoyado (sobre el derecho a mitad de su apoyo) y la cadera
    baja apenas después de cada apoyo (dos veces por ciclo)."""
    a = 2.0 * math.pi * (f / n - duty * 0.5)
    b = 4.0 * math.pi * (f / n - 0.06)
    return math.cos(a), math.cos(b)


# ============================================================================== ninja
NINJA_CYCLE = 14             # cuadros de Walk (team_clips_ninja.locomotion): los ciclos del blend tree tienen este largo


def ninja_strafe(ch, N, side):
    """De costado en guardia (rodeo) a la velocidad de caminar (2 m/s) y con el ritmo de Walk (14 cuadros, 4.3 pasos por
    segundo): pasos cruzados de ~0.47 m, el pie de adelante (el derecho) sigue adelante. Hacia la derecha guía el derecho y
    el izquierdo cruza por detrás; hacia la izquierda guía el izquierdo y el derecho cruza por delante (0.32 m de fondo
    entre los dos: los pies nunca se pisan). La cadera pasa el peso sobre el pie apoyado y se inclina apenas hacia donde
    va, el pecho y la cabeza no dejan de mirar a Kaito y la hoja sigue apuntándole como en Walk."""
    n, duty = NINJA_CYCLE, 0.52
    sgn = 1.0 if side == "L" else -1.0               # +X = su izquierda
    vel = (sgn * N.WALK_SPEED, 0.0)
    feet = {"r": (-0.16, -0.15, 8.0), "l": (0.16, 0.17, 32.0)}
    g = gait_dir(ch, n, vel, duty, feet, lift=0.08, strike=8.0, off=16.0)

    def pose(f):
        c = dict(N.STANCE)
        c.update(g(f))
        sw, bob = _sway(f, n, duty)
        a = 2.0 * math.pi * f / n
        c["hips"] = (0.04 * -sw, 0.03, -0.10 - 0.014 * bob)
        c["hips_rot"] = (5.0, sgn * 3.0 + 2.5 * sw, 18.0 - 4.0 * math.sin(a))
        c["spine"] = (6.0, -sgn * 1.5 - 1.5 * sw, -6.0 + 2.0 * math.sin(a))
        c["chest"] = (4.0, -1.0 * sw, -8.0 + 2.0 * math.sin(a))
        c["head"] = (-8.0, -sgn * 1.5, -4.0)
        c["grip"] = (-0.16, -0.30, 0.78 + 0.01 * math.cos(2 * a + 0.6))
        c["edge"] = N.LOOP_EDGE
        c["hand_l"] = (0.11, -0.17, 0.86 + 0.008 * math.cos(2 * a + 0.9))
        return c
    name = "Strafe" + side
    return NA.ProcClip(name, n, pose, loop=True, root_vel=(vel[0], vel[1], 0.0),
                       notes=f"de costado hacia su {'izquierda' if side == 'L' else 'derecha'} a {N.WALK_SPEED:g} m/s (rodeo)")


def ninja_walk_back(ch, N):
    """Para atrás en guardia a 2 m/s (Kaito se le viene encima y vuelve a su distancia): apoya de punta y despega de
    talón, el cuerpo apenas más erguido que en Walk y la hoja adelante como en la guardia."""
    n, duty = NINJA_CYCLE, 0.58
    vel = (0.0, N.WALK_SPEED)
    g = gait_dir(ch, n, vel, duty, {"r": (-0.12, -0.07, 6.0), "l": (0.15, 0.07, 26.0)}, lift=0.06, strike=16.0, off=-10.0)

    def pose(f):
        a = 2.0 * math.pi * f / n
        c = dict(N.STANCE)
        c.update(g(f))
        c["hips"] = (0.012 * math.sin(a), 0.04, -0.095 - 0.014 * math.cos(2 * a))
        c["hips_rot"] = (2.0, 2.0 * math.sin(a), 18.0 - 5.0 * math.sin(a))
        c["spine"] = (4.0, 0.0, -6.0)
        c["chest"] = (2.0, 1.5 * math.sin(a), -8.0 + 4.0 * math.sin(a))
        c["head"] = (-8.0, 0.0, -4.0 + 1.5 * math.sin(a))
        c["grip"] = (-0.16, -0.30, 0.78 + 0.012 * math.cos(2 * a + 0.6))
        c["edge"] = N.LOOP_EDGE
        c["hand_l"] = (0.11, -0.17, 0.86 + 0.01 * math.cos(2 * a + 0.9))
        return c
    return NA.ProcClip("WalkBack", n, pose, loop=True, root_vel=(0.0, vel[1], 0.0), notes="para atrás en guardia a 2 m/s")


def ninja_loco_idle(N):
    return static_loop("LocoIdle", NINJA_CYCLE, N.idle().keys[0].ctrl, N.PLANTED,
                       "la guardia quieta del centro del blend tree (cuadro 0 de Idle)")


# el salto del bambú: EnemyArchetypes.NinjaBambooMoves (Hit("Leap", ...), NinjaApexLeap) desde 3.8-6.6 m; despega en 'to'
LEAP = dict(n=48, apex=14, to=16, contact=34, active_end=38, land=40, lunge=4.4, windup=0.8, height=1.0)


def ninja_leap(ch, N):
    """El salto del bambú (4.4 m): se agazapa al ras con la hoja baja adelante y la mano libre casi en el piso (aviso:
    desde arriba, el ninja más bajo y compacto, como un resorte; distinto del hasso del Attack3 con la hoja atrás de la
    cabeza) y se hunde más en el apex. Empuja dos cuadros con el transform quieto (f15 las piernas se estiran y el pie de
    atrás se suelta, f16 estirado del todo sobre la punta del de adelante: el último en el piso) y salta en un arco alto de
    1 m: sube con las rodillas recogidas llevando la hoja sobre la cabeza con las dos manos, la echa atrás arriba del salto
    y parte de arriba cayendo (el golpe pega a 0.6 m del piso, todavía en el aire). Cae aplastado con la punta en el piso
    y se rearma. La embestida entera del juego pasa con los dos pies en el aire (de f16 al aterrizaje, f40). El arco es
    del clip; VariantMotion solo levanta el cuerpo si el controller no tiene este estado (vuelve al Attack3)."""
    m = LEAP
    n, apex, to, contact, land, lunge = m["n"], m["apex"], m["to"], m["contact"], m["land"], m["lunge"]
    tr, _ = clip_lunge_travel(n, apex, contact, lunge, m["windup"], to, air=True)
    times = frame_times(n, apex, contact, m["windup"])
    arc = hop_arc(times, to, land, m["height"])
    P, FR, FL = N.P, N.FR, N.FL
    CROUCH = P(hips=(0.0, 0.06, -0.24), hips_rot=(26.0, 0.0, 22.0), spine=(14.0, 0.0, -8.0), chest=(6.0, 0.0, -14.0),
               head=(-34.0, 0.0, -8.0), knee_r=(-0.5, -1.0, 0.0), knee_l=(0.7, -0.8, 0.0),
               grip=(-0.16, -0.24, 0.50), blade=(0.10, -0.88, -0.46), edge=(-0.99, -0.11, 0.0), elbow_r=(-0.8, 0.4, -0.4),
               hand_l=(0.16, -0.40, 0.34), hand_l_dir=(0.0, -0.5, -0.85), hand_l_palm=(0.0, 0.3, -0.95), elbow_l=(0.8, -0.2, -0.6),
               fist_l=0.3, grip_l=0.0)
    HOLD = dict(CROUCH, hips=(0.0, 0.07, -0.27), head=(-36.0, 0.0, -8.0), grip=(-0.16, -0.23, 0.47), hand_l=(0.16, -0.40, 0.31))
    # despegue: las piernas se estiran (f15) y en f16 el cuerpo sale inclinado hacia Kaito sobre la punta del pie de
    # adelante, la hoja empieza a subir y la mano libre va al mango (lo agarra en el aire)
    PUSH0 = dict(HOLD, hips=(0.0, 0.03, -0.15), hips_rot=(22.0, 0.0, 19.0), spine=(11.0, 0.0, -7.0), chest=(3.0, 0.0, -11.0),
                 head=(-28.0, 0.0, -7.0), knee_r=(-0.35, -1.0, 0.0), knee_l=(0.6, -0.9, 0.0), grip=(-0.16, -0.27, 0.62),
                 blade=(0.10, -0.80, 0.30), edge=(-0.92, -0.33, -0.15), hand_l=(0.15, -0.40, 0.50))
    PUSH = dict(HOLD, hips=(0.0, -0.04, -0.02), hips_rot=(18.0, 0.0, 16.0), spine=(8.0, 0.0, -6.0), chest=(0.0, 0.0, -8.0),
                head=(-20.0, 0.0, -6.0), knee_r=(-0.25, -1.0, 0.0), knee_l=(0.55, -1.0, 0.0), grip=(-0.16, -0.30, 0.80),
                blade=(0.10, -0.60, 0.79), edge=(-0.79, -0.53, -0.30), hand_l=(0.14, -0.40, 0.70))
    # arriba: recogido, las dos manos sobre la cabeza y la hoja vertical (la silueta más alta que el ninja puede hacer)
    RISE = P(hips=(0.0, 0.0, -0.10), hips_rot=(-2.0, 0.0, 10.0), spine=(-4.0, 0.0, 0.0), chest=(-10.0, 0.0, -4.0),
             head=(-6.0, 0.0, -4.0), knee_r=(-0.2, -1.0, 0.3), knee_l=(0.2, -1.0, 0.3),
             grip=(-0.20, -0.14, 1.38), blade=(0.08, 0.20, 0.98), edge=(0.0, -1.0, 0.1), elbow_r=(-0.9, 0.2, -0.3),
             grip_l=1.0, elbow_l=(0.8, -0.2, -0.4), fist_l=1.0)
    COCK = dict(RISE, hips=(0.0, -0.02, -0.11), chest=(-14.0, 0.0, -4.0), head=(-10.0, 0.0, -4.0),
                grip=(-0.20, -0.10, 1.40), blade=(0.06, 0.42, 0.91))
    CONTACT = dict(RISE, hips=(0.0, -0.06, -0.08), hips_rot=(16.0, 0.0, 10.0), spine=(16.0, 0.0, 0.0), chest=(10.0, 0.0, -4.0),
                   head=(-18.0, 0.0, -4.0), grip=(-0.08, -0.46, 0.92), blade=(0.25, -0.93, 0.25), edge=(0.67, -0.02, -0.74),
                   elbow_r=(-0.8, 0.3, -0.4), elbow_l=(0.8, 0.3, -0.4), knee_r=(-0.2, -1.0, 0.1), knee_l=(0.2, -1.0, 0.1))
    FOLLOW = dict(CONTACT, hips=(0.0, -0.08, -0.06), hips_rot=(20.0, 0.0, 12.0), spine=(18.0, 0.0, 0.0), head=(-22.0, 0.0, -4.0),
                  grip=(-0.06, -0.44, 0.70), blade=(0.18, -0.80, -0.57), edge=(0.58, 0.56, -0.60))
    LAND = dict(FOLLOW, hips=(0.0, -0.07, -0.29), hips_rot=(24.0, 0.0, 14.0), spine=(20.0, 0.0, 0.0), chest=(14.0, 0.0, -4.0),
                head=(-26.0, 0.0, -4.0), grip=(-0.06, -0.40, 0.46), blade=(0.15, -0.89, -0.41), edge=(0.58, 0.42, -0.70))
    PUNISH = dict(LAND, hips=(0.0, -0.06, -0.24), grip=(-0.06, -0.38, 0.49), blade=(0.0, -0.91, -0.41))
    keys = [Key(0, P()), Key(9, CROUCH, "inout"), Key(apex, HOLD, "sine"), Key(15, PUSH0, "in"), Key(to, PUSH, "out"),
            Key(22, RISE, "inout"), Key(29, COCK, "sine"), Key(contact, CONTACT, "in"), Key(37, FOLLOW, "out"), Key(land, LAND, "in2"),
            Key(42, PUNISH, "out"), Key(n, P(), "sine")]
    span = float(land - to)
    tuck = lambda f: 0.26 * max(0.0, math.sin(math.pi * (f - to) / span)) ** 1.5
    # el primer cuadro del vuelo los pies quedan atrás de lo que avanzó el transform: salen del piso sin arrastrarse
    trail = lambda f: 0.22 * max(0.0, 1.0 - (f - to - 1) / 3.0)
    fly_r = [FR(f, max(0.0, tr[f] - trail(f)) + 0.06 * (f - to) / span, z=arc(f) + tuck(f), pitch=-6.0 + 30.0 * trail(f) / 0.22,
                ease="lin", lift=0.0) for f in range(to + 1, land)]
    fly_l = [FL(f, max(0.0, tr[f] - trail(f)) - 0.04 * min(1.0, (f - to) / 3.0), z=arc(f) + 0.85 * tuck(f), pitch=36.0 * (1.0 - (f - to) / span),
                ease="lin", lift=0.0) for f in range(to + 1, land + 1)]
    feet = {"r": [FR(0), FR(apex, pitch=-4.0), FR(15, pitch=14.0, lift=0.0), FR(to, pitch=34.0, lift=0.0)] + fly_r
                 + [FR(land, lunge + 0.06, pitch=-10.0, ease="lin", lift=0.0), FR(land + 2, lunge + 0.06), FR(45, lunge + 0.06),
                    FR(n, lunge, lift=0.03)],
            "l": [FL(0), FL(9), FL(apex, pitch=30.0), FL(15, pitch=46.0, z=0.02, ease="out", lift=0.0), FL(to, pitch=48.0, z=0.06, ease="lin", lift=0.0)]
                 + fly_l + [FL(land + 2, lunge - 0.05, ease="out", lift=0.0), FL(45, lunge - 0.05), FL(n, lunge, lift=0.03)]}
    return ArcClip("Leap", n, keys, travel=tr, feet=feet, arc=arc, notes="salto del bambú: arco alto de 1 m, parte de arriba al caer",
                   timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, m["active_end"]], hold=[9, apex],
                               lunge=lunge, windup=m["windup"], state="Leap", land=land, hop_m=m["height"], reach=1.6, lunge_from=to, lunge_air=True,
                               sheet=[9, apex, 15, to, 22, 29, contact, 37, land, 42, n]))


# el remolino del lago: EnemyArchetypes.NinjaLakeMoves (Hit("Whirl", ...), NinjaApexWhirl); encadenado detrás del
# Attack1 (windup mínimo 0.5 s de un pesado encadenado + 0.1 de telegraph); despega en 'to'
WHIRL = dict(n=36, apex=10, to=11, contact=20, active_end=24, land=26, lunge=1.1, windup=0.6, height=0.30)
# canales que giran con el cuerpo: posiciones y direcciones pedidas en el marco de autoría
SPUN = ("grip", "blade", "edge", "elbow_r", "elbow_l", "hand_l", "hand_l_dir", "hand_l_palm", "knee_r", "knee_l")


def _spin(pose, deg):
    """La pose girada 'deg' grados alrededor del transform (z+ = hacia su izquierda): las posiciones y direcciones que
    se piden en el marco de autoría giran, la cadera suma el giro."""
    R = Matrix.Rotation(math.radians(deg), 3, 'Z')
    out = dict(pose)
    for k in SPUN:
        if out.get(k) is not None:
            out[k] = tuple(R @ NA.V(out[k]))
    h = NA.V(out["hips"])
    hx, hy, _ = R @ NA.V((h.x, h.y, 0.0))
    out["hips"] = (hx, hy, h.z)
    hr = out["hips_rot"]
    out["hips_rot"] = (hr[0], hr[1], hr[2] + deg)
    return out


def ninja_whirl(ch, N):
    """Remolino del lago (golpe de 360°, 1.1 m): una vuelta entera en el aire con la hoja horizontal adelante, el tajo
    del Attack1 que no para. Aviso: agachado y enroscado 70° a SU derecha (la contra del giro) con la hoja horizontal
    afuera a la derecha a la altura de la cintura y la mano libre recogida al pecho; desde arriba, una barra que sale del
    contorno a la derecha, más baja y más girada que el aviso del Attack1 (que es parado y apunta con la mano libre). En
    f11 empuja sobre las puntas (la cadera ya pre-gira 14° sobre los pies), en f12 los dos pies dejan el piso SIN girar
    y recién ahí gira a la izquierda (antihorario visto desde arriba) 470°: la hoja barre el círculo entero, el disco de
    360° de Enemy pega en f20 y la hoja vuelve a pasar por delante en f21, sigue 40° y cae en la guardia (f26) frenando
    el giro. Los pies giran con el cuerpo en el aire, ninguno apoyado mientras gira. Antes el giro arrancaba en f11 con
    la punta derecha todavía en el piso: 107° de cadera en un cuadro, y la rotación interpolada de la pierna barría la
    suela apoyada 16 cm entre f11 y f11.6 (medido en el FBX con fbx_skate.py; entre cuadros enteros no se veía).
    VariantMotion ya no lo gira si existe este estado. La pose del brazo es la del contacto del Attack1 (validada: el
    antebrazo cerca de neutro), girada con el cuerpo."""
    m = WHIRL
    n, apex, to, contact, land, lunge = m["n"], m["apex"], m["to"], m["contact"], m["land"], m["lunge"]
    tr, _ = clip_lunge_travel(n, apex, contact, lunge, m["windup"], to, air=True)
    times = frame_times(n, apex, contact, m["windup"])
    arc = hop_arc(times, to, land, m["height"])
    P, FR, FL = N.P, N.FR, N.FL
    coil, after, pre = -70.0, 40.0, 14.0
    total = 360.0 - coil + after
    # el giro (cuerpo y pies) arranca en el primer cuadro en el aire, to + 1, y frena con esta potencia: con 2.5 la hoja
    # vuelve a pasar por delante en f21.3 como cuando arrancaba un cuadro antes con 2.2, y el cuadro más rápido gira 104°
    # (eran 107°)
    spin_from, spin_ease = to + 1, 2.5

    def g(f):
        u = min(1.0, max(0.0, (times[f] - times[spin_from]) / (times[land] - times[spin_from])))
        return 1.0 - (1.0 - u) ** spin_ease

    def turn(f):
        """Giro del cuerpo respecto del tajo del Attack1 (°): enroscado en el apex, un poco sobre los pies al empujar (y así
        en el cuadro que despega), la vuelta entera en el aire y 40° más al caer."""
        if f <= apex:
            return coil
        if f <= spin_from:
            return coil + pre
        return coil + pre + (total - pre) * g(f)

    # el contacto del Attack1 (la hoja adelante, el filo hacia su izquierda: va adelante del barrido antihorario)
    SPIN = P(hips=(0.0, -0.02, -0.11), hips_rot=(6.0, 0.0, 16.0), spine=(10.0, 0.0, 6.0), chest=(6.0, -2.0, 10.0),
             head=(-10.0, 0.0, -12.0), knee_r=(-0.2, -1.0, 0.2), knee_l=(0.2, -1.0, 0.2),
             grip=(-0.14, -0.36, 0.86), blade=(0.04, -0.99, 0.10), edge=(0.96, 0.06, 0.0), elbow_r=(-0.8, 0.3, -0.4),
             hand_l=(0.28, -0.05, 0.92), hand_l_dir=(0.6, 0.6, 0.2), hand_l_palm=(0.0, 0.0, -1.0), elbow_l=(0.8, 0.3, -0.4),
             fist_l=0.3, grip_l=0.0)
    TUCK = dict(SPIN, hand_l=(0.16, -0.12, 0.98), hand_l_dir=(-0.3, -0.7, 0.6), hand_l_palm=(0.0, 0.6, -0.8))
    TELL = _spin(dict(TUCK, hips=(0.0, 0.04, -0.17), spine=(12.0, 0.0, 8.0), chest=(8.0, -2.0, 10.0), head=(-12.0, 0.0, 40.0),
                      knee_r=(-0.4, -1.0, 0.0), knee_l=(0.6, -1.0, 0.0)), coil)
    HOLD = _spin(dict(TUCK, hips=(0.0, 0.04, -0.20), spine=(13.0, 0.0, 9.0), chest=(8.0, -2.0, 11.0), head=(-12.0, 0.0, 44.0),
                      knee_r=(-0.4, -1.0, 0.0), knee_l=(0.6, -1.0, 0.0)), coil)
    PUSH = _spin(dict(TUCK, hips=(0.0, 0.01, -0.07), spine=(10.0, 0.0, 7.0), chest=(6.0, -2.0, 10.0), head=(-11.0, 0.0, 30.0),
                      knee_r=(-0.25, -1.0, 0.1), knee_l=(0.35, -1.0, 0.1)), coil + pre)
    keys = [Key(0, P()), Key(6, TELL, "inout"), Key(apex, HOLD, "sine"), Key(to, PUSH, "in")]
    for f in range(to + 1, land):
        # en el aire: la cabeza deja de mirar atrás (gira con el cuerpo y busca a Kaito al volver); la mano libre queda
        # recogida al pecho (abierta pedía medio giro del antebrazo en un cuadro)
        q = (f - to) / float(land - to)
        body = dict(TUCK, hips=(0.0, -0.02, -0.11 + 0.04 * math.sin(math.pi * q)),
                    head=(-10.0, 0.0, -12.0 + 42.0 * (1.0 - min(1.0, q * 1.6))))
        keys.append(Key(f, _spin(body, turn(f)), "lin"))
    LAND = dict(TUCK, hips=(0.0, -0.02, -0.21), hips_rot=(12.0, 0.0, 16.0), spine=(14.0, 0.0, 6.0), head=(-14.0, 0.0, -10.0),
                grip=(-0.12, -0.34, 0.76), hand_l=(0.16, -0.14, 0.88))
    keys += [Key(land, _spin(LAND, coil + total), "out"),
             Key(30, _spin(dict(LAND, hips=(0.0, -0.02, -0.17)), coil + total), "sine"),
             Key(n, _spin(P(), 360.0), "sine")]
    span = float(land - to)
    tuck = lambda f: 0.16 * max(0.0, math.sin(math.pi * (f - to) / span)) ** 1.5
    trail = lambda f: 0.10 * max(0.0, 1.0 - (f - to - 1) / 2.0)

    def foot(stance, f, z):
        """Un pie en el aire: su lugar de la guardia girado con el cuerpo (una vuelta entera hasta caer) y con el avance. Gira
        recién desde el primer cuadro en el aire, a la par del cuerpo (girando mientras dejaba el piso, la punta barría
        el suelo)."""
        d = 360.0 * g(f)
        x0, y0, yaw0 = stance
        p = Matrix.Rotation(math.radians(d), 3, 'Z') @ NA.V((x0, y0, 0.0))
        # la punta sigue para abajo los primeros cuadros del vuelo (aplanada de golpe al despegar, barría el piso)
        pitch = 30.0 * max(0.0, 1.0 - (f - to) / 3.0)
        return T.FootKey(f, p.x, p.y - max(0.0, tr[f] - trail(f)), yaw0 + d, pitch, z, 0.0, "lin", 0.0)

    R0, L0 = N.R0, N.L0
    fly_r = [foot(R0, f, arc(f) + tuck(f)) for f in range(to + 1, land)]
    fly_l = [foot(L0, f, arc(f) + 0.85 * tuck(f)) for f in range(to + 1, land)]
    feet = {"r": [FR(0), FR(apex, pitch=10.0), FR(to, pitch=30.0, lift=0.0)] + fly_r
                 + [T.FootKey(land, R0[0], R0[1] - lunge, R0[2] + 360.0, -8.0, 0.0, 0.0, "lin", 0.0),
                    T.FootKey(land + 2, R0[0], R0[1] - lunge, R0[2] + 360.0)],
            "l": [FL(0), FL(apex, pitch=26.0), FL(to, pitch=40.0, z=0.03, ease="out", lift=0.0)] + fly_l
                 + [T.FootKey(land + 1, L0[0], L0[1] - lunge, L0[2] + 360.0, 0.0, 0.0, 0.0, "out", 0.0),
                    T.FootKey(n, L0[0], L0[1] - lunge, L0[2] + 360.0)]}
    return ArcClip("Whirl", n, keys, travel=tr, feet=feet, arc=arc, tremble=0.006,
                   notes="remolino del lago: una vuelta entera en el aire con la hoja horizontal",
                   timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, m["active_end"]], hold=[6, apex],
                               lunge=lunge, windup=m["windup"], state="Whirl", land=land, hop_m=m["height"], spin_deg=total,
                               reach=1.6, lunge_from=to, lunge_air=True, sheet=[6, apex, to, 12, 14, 16, 18, contact, 22, land, n]))


# el repliegue del bambú: EnemyArchetypes.NinjaBambooMoves (Hit("HopBack", ...), special hop_back de 3 m). Sin daño: el
# windup es su telegraph (0.12 s) y Enemy lo lleva en cuadros del clip de 'to' (el último con la punta en el piso) a 'land'
HOP_BACK = dict(n=32, apex=5, to=7, land=27, meters=3.0, telegraph=0.12, height=0.45)


def ninja_hop_back(ch, N):
    """Repliegue (después de un combo, 3 m para atrás sin daño): se agacha (f5, 0.15 m), empuja con las dos piernas
    estiradas sobre las puntas (f7, el último cuadro en el piso: recién ahí arranca el salto del juego), vuela de espaldas
    en un arco de 0.45 m con las rodillas recogidas y la hoja en guardia apuntando a Kaito, estira las piernas para
    recibir el piso y cae sobre las puntas (f27) amortiguando hasta las cuclillas; se rearma en guardia. Antes era el
    Spotted levantado por VariantMotion: una pose parada que flotaba 3 m para atrás."""
    m = HOP_BACK
    n, apex, to, land, meters = m["n"], m["apex"], m["to"], m["land"], m["meters"]
    tr, _ = clip_lunge_travel(n, apex, to, meters, m["telegraph"], to, end_frame=land)
    times = frame_times(n, apex, to, m["telegraph"])
    arc = hop_arc(times, to, land, m["height"])
    P, FR, FL = N.P, N.FR, N.FL
    G = P()
    CROUCH = dict(G, hips=(0.0, -0.01, -0.23), hips_rot=(16.0, 0.0, 16.0), spine=(10.0, 0.0, -6.0), chest=(6.0, 0.0, -8.0),
                  head=(-22.0, 0.0, -4.0), knee_r=(-0.3, -1.0, 0.0), knee_l=(0.6, -1.0, 0.0), grip=(-0.16, -0.32, 0.66),
                  hand_l=(0.12, -0.20, 0.70))
    PUSH = dict(G, hips=(0.0, 0.05, -0.02), hips_rot=(-6.0, 0.0, 16.0), spine=(-4.0, 0.0, -6.0), chest=(-4.0, 0.0, -8.0),
                head=(-4.0, 0.0, -4.0), knee_r=(-0.2, -1.0, 0.0), knee_l=(0.4, -1.0, 0.0), grip=(-0.16, -0.30, 0.86))
    TUCKED = dict(G, hips=(0.0, 0.02, -0.10), hips_rot=(-4.0, 0.0, 14.0), spine=(2.0, 0.0, -6.0), chest=(2.0, 0.0, -8.0),
                  head=(-10.0, 0.0, -4.0), knee_r=(-0.2, -1.0, 0.4), knee_l=(0.3, -1.0, 0.4), grip=(-0.16, -0.30, 0.84))
    REACH = dict(TUCKED, hips=(0.0, 0.03, -0.06), hips_rot=(2.0, 0.0, 16.0), spine=(6.0, 0.0, -6.0), head=(-12.0, 0.0, -4.0),
                 knee_r=(-0.25, -1.0, 0.0), knee_l=(0.5, -1.0, 0.0))
    LAND = dict(CROUCH, hips=(0.0, -0.02, -0.26), hips_rot=(20.0, 0.0, 16.0), spine=(14.0, 0.0, -6.0), head=(-24.0, 0.0, -4.0),
                grip=(-0.16, -0.30, 0.62), hand_l=(0.12, -0.20, 0.66))
    RISE = dict(G, hips=(0.0, 0.02, -0.12), hips_rot=(8.0, 0.0, 17.0), spine=(8.0, 0.0, -6.0), head=(-12.0, 0.0, -4.0))
    keys = [Key(0, G), Key(apex, CROUCH, "inout"), Key(to, PUSH, "in"), Key(13, TUCKED, "out"), Key(21, REACH, "inout"),
            Key(land, LAND, "in2"), Key(29, dict(LAND, hips=(0.0, -0.02, -0.24)), "out"), Key(31, RISE, "inout"), Key(n, G, "sine")]
    # la mano libre cerrada al costado de la cadera, con el puño hacia adentro y a la altura de la cadera en cada pose (quieta
    # en el marco de autoría mientras el cuerpo se hundía y se estiraba, el antebrazo daba vuelta en el empujón)
    # hasta el final: la vuelta a la mano de la guardia la hace el cruce a la locomoción (girándola en un cuadro, el
    # antebrazo daba vuelta)
    side = {"hand_l_dir": (0.1, -0.5, -0.85), "hand_l_palm": (-1.0, 0.0, 0.0), "fist_l": 0.6}
    for k in keys[1:]:
        hz = k.ctrl["hips"][2]
        k.ctrl = dict(k.ctrl, hand_l=(0.22, -0.05, 0.84 + hz), **side)
    span = float(land - to)
    tuck = lambda f: 0.20 * max(0.0, math.sin(math.pi * (f - to) / span)) ** 1.5
    # para atrás: lo que avanzó el transform va hacia +Y (dy negativo en FR/FL); los pies quedan adelante el primer cuadro
    trail = lambda f: 0.16 * max(0.0, 1.0 - (f - to - 1) / 3.0)
    fly_r = [FR(f, -max(0.0, tr[f] - trail(f)), z=arc(f) + tuck(f), pitch=28.0 * (1.0 - (f - to) / span), ease="lin", lift=0.0)
             for f in range(to + 1, land)]
    fly_l = [FL(f, -max(0.0, tr[f] - trail(f)), z=arc(f) + 0.9 * tuck(f), pitch=30.0 * (1.0 - (f - to) / span), ease="lin", lift=0.0)
             for f in range(to + 1, land)]
    feet = {"r": [FR(0), FR(apex - 1), FR(apex, pitch=6.0), FR(to, pitch=36.0, lift=0.0)] + fly_r
                 + [FR(land, -meters, pitch=22.0, ease="lin", lift=0.0), FR(land + 2, -meters), FR(n, -meters)],
            "l": [FL(0), FL(apex - 1), FL(apex, pitch=8.0), FL(to, pitch=38.0, lift=0.0)] + fly_l
                 + [FL(land, -meters, pitch=24.0, ease="lin", lift=0.0), FL(land + 2, -meters), FL(n, -meters)]}
    c = ArcClip("HopBack", n, keys, travel=tr, feet=feet, arc=arc, tremble=0.0, notes="repliegue: salto de 3 m para atrás en arco",
                timing=dict(hop=dict(apex=apex, takeoff=to, land=land), state="HopBack", lunge=meters, lunge_from=to,
                            windup=m["telegraph"], hop_m=m["height"], sheet=[0, apex, to, 13, 17, 21, land, 29, n]))
    c.travel_dir = (0.0, 1.0)
    return c


def ninja_clips(ch, N):
    return [ninja_loco_idle(N), ninja_strafe(ch, N, "L"), ninja_strafe(ch, N, "R"), ninja_walk_back(ch, N),
            ninja_leap(ch, N), ninja_whirl(ch, N), ninja_hop_back(ch, N)]


# ============================================================================== sumo
SUMO_CYCLE = 22              # cuadros de Walk del sumo


def sumo_strafe(ch, S, side):
    """De costado (1.6 m/s) con el ritmo de Walk (22 cuadros): dos suri-ashi por ciclo, paso y arrime. El pie que guía
    abre largo y despacio (0.59 m) y el otro se arrima rápido, sin cruzar nunca (las piernas del sumo no se pueden
    cruzar): 2.7 pasos y arrimes por segundo, el mismo ritmo que sus pasos de Walk. Los pies casi no se despegan del piso
    y entre 0.5 y 1.1 m de separación; la panza va sobre el pie que queda apoyado (10 cm de lado a lado, lo que se lee
    desde arriba: las piernas las tapa la panza), la cadera baja en cada apoyo y la cabeza no deja de mirar a Kaito."""
    n, sub = SUMO_CYCLE, SUMO_CYCLE // 2
    sgn = 1.0 if side == "L" else -1.0
    fn, win = step_close(ch, sub, S.WALK_SPEED, sgn, {"r": -0.42, "l": 0.42}, {"r": (0.02, -20.0), "l": (0.02, 20.0)})
    lead = "l" if sgn > 0 else "r"

    def pose(f):
        u = (f % sub) / float(sub)
        c = dict(S.STANCE)
        c.update(fn(f))
        # el peso sobre el pie que queda apoyado: hacia el de atrás mientras abre el de adelante, hacia el de adelante
        # mientras se arrima el otro
        w = math.cos(2.0 * math.pi * (u - 0.66))
        dip = math.cos(4.0 * math.pi * (u - 0.45))
        c["hips"] = (sgn * 0.10 * w, 0.02, -0.12 - 0.022 * max(0.0, dip))
        c["hips_rot"] = (6.0, sgn * (2.0 + 5.0 * w), 0.0)
        c["spine"] = (6.0, -sgn * 4.0 * w, 0.0)
        c["head"] = (-10.0, -sgn * (1.0 + 2.0 * w), 0.0)
        out = 0.04 * sgn
        c["hand_r"] = (-0.64 + out + 0.03 * sgn * w, -0.20, 1.05 + 0.02 * dip)
        c["hand_l"] = (0.64 + out + 0.03 * sgn * w, -0.20, 1.05 + 0.02 * dip)
        return c
    name = "Strafe" + side
    return NA.ProcClip(name, n, pose, loop=True, root_vel=(sgn * S.WALK_SPEED, 0.0, 0.0),
                       notes=f"suri-ashi de costado hacia su {'izquierda' if side == 'L' else 'derecha'} a {S.WALK_SPEED:g} m/s "
                             f"(guía el {'izquierdo' if lead == 'l' else 'derecho'})")


def sumo_walk_back(ch, S):
    """Para atrás (1.6 m/s) con el ritmo de Walk (22 cuadros): pasos pesados de punta, la panza adelante y el peso de un
    pie al otro."""
    n, duty = SUMO_CYCLE, 0.62
    vel = (0.0, S.WALK_SPEED)
    g = gait_dir(ch, n, vel, duty, {"r": (-0.40, 0.0, -18.0), "l": (0.40, 0.0, 18.0)}, lift=0.08, strike=12.0, off=-8.0)

    def pose(f):
        a = 2.0 * math.pi * f / n
        c = dict(S.STANCE)
        c.update(g(f))
        c["hips"] = (-0.06 * math.sin(a), 0.03, -0.11 - 0.02 * math.cos(2 * a))
        c["hips_rot"] = (4.0, 5.0 * math.sin(a), -5.0 * math.sin(a))
        c["spine"] = (4.0, -3.0 * math.sin(a), 3.0 * math.sin(a))
        c["head"] = (-8.0, -2.0 * math.sin(a), -2.0 * math.sin(a))
        c["hand_r"] = (-0.64, -0.20 - 0.08 * math.sin(a + math.pi), 1.05 + 0.02 * math.cos(2 * a))
        c["hand_l"] = (0.64, -0.20 - 0.08 * math.sin(a), 1.05 + 0.02 * math.cos(2 * a))
        return c
    return NA.ProcClip("WalkBack", n, pose, loop=True, root_vel=(0.0, vel[1], 0.0), notes="para atrás a 1.6 m/s")


def sumo_loco_idle(S):
    return static_loop("LocoIdle", SUMO_CYCLE, S.idle().keys[0].ctrl, S.PLANTED,
                       "la guardia quieta del centro del blend tree (cuadro 0 de Idle)")


# el empujón del lago: EnemyArchetypes.SumoLakeMoves (Hit("Morote", ...), SumoApexMorote); encadenado detrás de una
# bofetada (windup mínimo 0.5 s de un pesado encadenado); la embestida arranca en 'from', el primero de la suelta
MOROTE = dict(n=36, apex=12, contact=22, active_end=27, lunge=1.6, windup=0.5, frm=13)


def sumo_morote(ch, S):
    """Morote-zuki (el empujón a dos manos del sumo del lago, 1.6 m: te saca lejos). Aviso: agachado y cargado atrás,
    las dos manos abiertas junto a la panza con las palmas adelante y los codos atrás (desde arriba, el sumo más ancho
    y bajo que nunca, distinto del harite de una mano arriba). Suelta: arranca de un empujón, el derecho y el izquierdo
    entran rápido y en el contacto los dos brazos están estirados a la altura del pecho con el cuerpo inclinado detrás,
    como quien empuja una pared; sostiene, se acomoda y vuelve a la guardia. Los pies van en el mundo y nunca quedan
    apoyados lejos de la cadera."""
    m = MOROTE
    n, apex, contact, lunge = m["n"], m["apex"], m["contact"], m["lunge"]
    tr, _ = clip_lunge_travel(n, apex, contact, lunge, m["windup"], m["frm"])
    P = S.P
    WIND = P(hips=(0.0, 0.12, -0.24), hips_rot=(16.0, 0.0, 0.0), spine=(4.0, 0.0, 0.0), head=(-26.0, 0.0, 0.0),
             knee_r=(-0.9, -0.5, 0.0), knee_l=(0.9, -0.5, 0.0),
             hand_r=(-0.60, 0.12, 1.02), hand_r_dir=(0.0, -0.6, 0.8), hand_r_palm=(0.0, -0.8, -0.6), elbow_r=(-0.7, 0.9, -0.3),
             hand_l=(0.60, 0.12, 1.02), hand_l_dir=(0.0, -0.6, 0.8), hand_l_palm=(0.0, -0.8, -0.6), elbow_l=(0.7, 0.9, -0.3),
             fist_r=0.0, fist_l=0.0)
    HOLD = dict(WIND, hips=(0.0, 0.13, -0.25), head=(-28.0, 0.0, 0.0))
    DRIVE = dict(WIND, hips=(0.0, -0.08, -0.16), hips_rot=(22.0, 0.0, 0.0), spine=(8.0, 0.0, 0.0), head=(-30.0, 0.0, 0.0),
                 hand_r=(-0.52, -0.40, 1.30), hand_r_dir=(0.0, -0.4, 0.9), hand_r_palm=(0.0, -0.9, -0.4),
                 hand_l=(0.52, -0.40, 1.30), hand_l_dir=(0.0, -0.4, 0.9), hand_l_palm=(0.0, -0.9, -0.4),
                 elbow_r=(-0.9, 0.4, -0.5), elbow_l=(0.9, 0.4, -0.5))
    PUSH = dict(DRIVE, hips=(0.0, -0.17, -0.19), hips_rot=(24.0, 0.0, 0.0), spine=(8.0, 0.0, 0.0), head=(-32.0, 0.0, 0.0),
                hand_r=MOROTE_REACH, hand_r_dir=(0.0, -0.42, 0.91), hand_r_palm=(0.0, -0.91, -0.42),
                hand_l=(-MOROTE_REACH[0], MOROTE_REACH[1], MOROTE_REACH[2]), hand_l_dir=(0.0, -0.42, 0.91), hand_l_palm=(0.0, -0.91, -0.42),
                elbow_r=(-0.9, 0.2, -0.6), elbow_l=(0.9, 0.2, -0.6))
    FOLLOW = dict(PUSH, hips=(0.0, -0.19, -0.20), hips_rot=(25.0, 0.0, 0.0),
                  hand_r=(MOROTE_REACH[0], MOROTE_REACH[1] - 0.04, MOROTE_REACH[2] - 0.02),
                  hand_l=(-MOROTE_REACH[0], MOROTE_REACH[1] - 0.04, MOROTE_REACH[2] - 0.02))
    SETTLE = dict(FOLLOW, hips=(0.0, -0.06, -0.15), hips_rot=(12.0, 0.0, 0.0), spine=(6.0, 0.0, 0.0), head=(-16.0, 0.0, 0.0),
                  hand_r=(-0.50, -0.62, 1.28), hand_r_dir=(0.0, -0.6, 0.6), hand_r_palm=(0.0, -0.7, -0.7),
                  hand_l=(0.50, -0.62, 1.28), hand_l_dir=(0.0, -0.6, 0.6), hand_l_palm=(0.0, -0.7, -0.7),
                  elbow_r=(-1.0, 0.3, -0.4), elbow_l=(1.0, 0.3, -0.4))
    keys = [Key(0, P()), Key(8, WIND, "inout"), Key(apex, HOLD, "sine"), Key(16, DRIVE, "in"), Key(contact, PUSH, "out"),
            Key(25, FOLLOW, "out"), Key(30, SETTLE, "inout"), Key(n, P(), "sine")]
    FR, FL = S.FR, S.FL
    # (cuadro, metros adelante en el mundo): cada pie despega antes de quedar más de ~0.35 m detrás de la cadera
    # mientras el transform avanza, cada pie se apoya y se despega en vertical (un cuadro antes ya está sobre su lugar a
    # 2 cm, un cuadro después del despegue sigue ahí): Unity interpola el clip con curvas suaves y un pie que llegaba
    # todavía yendo se corría ~2 cm al apoyar
    feet = {"r": [FR(0), FR(apex, pitch=18.0), FR(13, 0.01, pitch=24.0, z=0.03, lift=0.0), FR(16, 0.85, pitch=-6.0, z=0.02, lift=0.10),
                  FR(17, 0.86, pitch=-8.0, lift=0.0), FR(18, 0.86), FR(21, 0.86, pitch=20.0), FR(22, 0.87, pitch=24.0, z=0.02, lift=0.0),
                  FR(25, lunge - 0.01, z=0.02, lift=0.08), FR(26, lunge, lift=0.0), FR(n, lunge)],
            "l": [FL(0), FL(apex, pitch=14.0), FL(13, pitch=28.0),
                  FL(19, 1.50, pitch=-6.0, z=0.02, lift=0.12), FL(20, 1.52, pitch=-8.0, lift=0.0),
                  FL(21, 1.52), FL(33, 1.52), FL(n, lunge, lift=0.03)]}
    return T.TeamClip("Morote", n, keys, travel=tr, feet=feet, notes="morote del lago: empuja con los dos brazos estirados",
                      timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, m["active_end"]], hold=[8, apex],
                                  lunge=lunge, windup=m["windup"], state="Morote", striker="r", reach=1.4, lunge_from=m["frm"]))


# las palmas del morote en el contacto (marco de autoría): los dos brazos estirados desde los hombros del cuerpo inclinado
MOROTE_REACH = (-0.30, -1.15, 1.45)

# la finta del bambú: EnemyArchetypes.SumoBambooMoves (Hit("HopSideR", ...), special hop_side de 2.6 m; Enemy toca HopSideL
# cuando salta a su izquierda). Sin daño: windup = su telegraph (0.1 s)
HOP_SIDE = dict(n=36, apex=8, to=11, land=26, meters=2.6, telegraph=0.10, height=0.38)


def sumo_hop_side(ch, S, side):
    """Finta (2.6 m de costado sin daño, antes de la embestida): pasa el peso al pie de afuera y se hunde en cuclillas con
    los brazos recogidos (f8), empuja con las dos piernas (f11, el último cuadro en el piso: recién ahí arranca el salto
    del juego), vuela pesado de costado en un arco bajo de 0.38 m con las rodillas abiertas y los brazos que suben a
    equilibrar, cae con los dos pies a la vez (f26) hundiéndose hasta abajo (el peso se ve) y se rearma. Antes era el
    Spotted levantado 0.45 m por VariantMotion y corrido 2.6 m: una pose plantada que flotaba de costado."""
    m = HOP_SIDE
    n, apex, to, land, meters = m["n"], m["apex"], m["to"], m["land"], m["meters"]
    sgn = -1.0 if side == "R" else 1.0               # +X = su izquierda
    tr, _ = clip_lunge_travel(n, apex, to, meters, m["telegraph"], to, end_frame=land)
    times = frame_times(n, apex, to, m["telegraph"])
    arc = hop_arc(times, to, land, m["height"])
    P, FR, FL = S.P, S.FR, S.FL
    G = P()
    LOAD = dict(G, hips=(-sgn * 0.08, 0.02, -0.18), hips_rot=(8.0, -sgn * 6.0, 0.0), spine=(8.0, sgn * 4.0, 0.0), head=(-12.0, 0.0, 0.0))
    CROUCH = dict(G, hips=(-sgn * 0.06, 0.03, -0.32), hips_rot=(14.0, -sgn * 4.0, 0.0), spine=(12.0, sgn * 3.0, 0.0), head=(-18.0, 0.0, 0.0),
                  knee_r=(-1.0, -0.4, 0.0), knee_l=(1.0, -0.4, 0.0),
                  hand_r=(-0.52, -0.34, 0.92), hand_l=(0.52, -0.34, 0.92))
    PUSH = dict(G, hips=(sgn * 0.08, 0.02, -0.06), hips_rot=(4.0, sgn * 8.0, 0.0), spine=(4.0, -sgn * 6.0, 0.0), head=(-10.0, 0.0, 0.0),
                hand_r=(-0.66, -0.20, 1.20), hand_l=(0.66, -0.20, 1.20))
    AIR = dict(G, hips=(sgn * 0.04, 0.02, -0.12), hips_rot=(6.0, sgn * 4.0, 0.0), spine=(6.0, -sgn * 3.0, 0.0), head=(-10.0, 0.0, 0.0),
               knee_r=(-1.0, -0.5, 0.2), knee_l=(1.0, -0.5, 0.2),
               hand_r=(-0.82, -0.14, 1.46), hand_l=(0.82, -0.14, 1.46))
    LAND = dict(CROUCH, hips=(0.0, 0.02, -0.34), hips_rot=(16.0, 0.0, 0.0), spine=(14.0, 0.0, 0.0), head=(-20.0, 0.0, 0.0),
                hand_r=(-0.60, -0.36, 0.86), hand_l=(0.60, -0.36, 0.86))
    keys = [Key(0, G), Key(4, LOAD, "inout"), Key(apex, CROUCH, "inout"), Key(to, PUSH, "in"), Key(18, AIR, "out"),
            Key(land, LAND, "in2"), Key(29, dict(LAND, hips=(0.0, 0.02, -0.31)), "out"), Key(n, G, "sine")]
    span = float(land - to)
    tuck = lambda f: 0.10 * max(0.0, math.sin(math.pi * (f - to) / span)) ** 1.5
    trail = lambda f: 0.18 * max(0.0, 1.0 - (f - to - 1) / 3.0)
    # de costado: lo que avanzó el transform va por X (dx); el pie de atrás del salto se queda un poco el primer cuadro
    far, near = ("l", "r") if sgn < 0 else ("r", "l")

    def fly(k, f):
        F = FR if k == "r" else FL
        lag = trail(f) if k == far else 0.6 * trail(f)
        return F(f, dx=sgn * max(0.0, tr[f] - lag), z=arc(f) + tuck(f), pitch=24.0 * (1.0 - (f - to) / span), ease="lin", lift=0.0)
    feet = {}
    for k in "rl":
        F = FR if k == "r" else FL
        feet[k] = ([F(0), F(apex), F(to, pitch=30.0 if k == far else 24.0, lift=0.0)] + [fly(k, f) for f in range(to + 1, land)]
                   + [F(land, dx=sgn * meters, pitch=8.0, ease="lin", lift=0.0), F(land + 2, dx=sgn * meters), F(n, dx=sgn * meters)])
    c = ArcClip("HopSide" + side, n, keys, travel=tr, feet=feet, arc=arc, tremble=0.0,
                notes=f"finta: salto pesado de 2.6 m hacia su {'derecha' if side == 'R' else 'izquierda'}",
                timing=dict(hop=dict(apex=apex, takeoff=to, land=land), state="HopSide" + side, lunge=meters, lunge_from=to,
                            windup=m["telegraph"], hop_m=m["height"], sheet=[0, 4, apex, to, 14, 18, 22, land, 29, n]))
    c.travel_dir = (sgn, 0.0)
    return c


def sumo_clips(ch, S):
    return [sumo_loco_idle(S), sumo_strafe(ch, S, "L"), sumo_strafe(ch, S, "R"), sumo_walk_back(ch, S), sumo_morote(ch, S),
            sumo_hop_side(ch, S, "R"), sumo_hop_side(ch, S, "L")]
