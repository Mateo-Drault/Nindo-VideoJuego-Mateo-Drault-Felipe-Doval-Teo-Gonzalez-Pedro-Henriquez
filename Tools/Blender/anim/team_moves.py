"""Locomoción de pelea y golpes de zona del ninja y del sumo (ítem 6 del traspaso, parte del ninja y del sumo).

Rodeo (Enemy.TickStrafe): los enemigos giran alrededor de Kaito mirándolo y antes caminaban hacia adelante mientras se
movían de costado. Enemy.Locomotion.cs elige estos estados por la dirección de la velocidad en el marco del enemigo:
  StrafeL / StrafeR  de costado hacia su izquierda / derecha, a la velocidad de caminar del arquetipo
  WalkBack           para atrás en guardia (cuando Kaito se le viene encima y vuelve a su distancia)
Todos arrancan con el pie derecho apoyándose en el cuadro 0, como Walk: Enemy cruza entre ellos en la misma fase.

Golpes de zona que reusaban un clip con otra embestida (los pies patinaban la diferencia):
  ninja  Whirl   el remolino del lago: una vuelta entera en el aire con la hoja horizontal (1.1 m)
         Leap    el salto del bambú: se agacha, salta en arco alto, parte de arriba al caer (4.4 m)
  sumo   Morote  el empujón a dos manos del lago: dos pasos que empujan con los dos brazos estirados (1.6 m)
El arpón del lago (Thrust con 2.4 m en vez de 3.2) no necesita clip: en el vuelo los pies del Thrust van con el avance
del transform y aterrizan cuando terminó, así que con menos embestida el movimiento local es el mismo (lo mide
build_team_anims.variant_skate).
Marco de autoría de team_rig: metros del juego, frente -Y, izquierda del personaje +X, origen en el transform.
"""
import math
from mathutils import Matrix
import nindo_anim as NA
import team_rig as T

Key = NA.Key
FPS = T.FPS


# ============================================================================== saltos con el reloj del juego
def frame_times(n, apex, contact, windup, speed=1.0, hz=2400.0):
    """Segundo del paso (reloj de Enemy: StepTimeline) en que se muestra cada cuadro entero del clip, 0..n."""
    tl = NA.StepTimeline(n, apex, contact, windup_min=windup, speed=speed)
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


def _sway(f, n, duty):
    """(lateral, baja) de la cadera: el peso pasa sobre el pie apoyado (sobre el derecho a mitad de su apoyo) y la cadera
    baja apenas después de cada apoyo (dos veces por ciclo)."""
    a = 2.0 * math.pi * (f / n - duty * 0.5)
    b = 4.0 * math.pi * (f / n - 0.06)
    return math.cos(a), math.cos(b)


# ============================================================================== ninja
def ninja_strafe(ch, N, side):
    """De costado en guardia (rodeo) a la velocidad de caminar (2 m/s): pasos cruzados cortos, el pie de adelante (el
    derecho) sigue adelante. Hacia la derecha guía el derecho y el izquierdo cruza por detrás; hacia la izquierda guía
    el izquierdo y el derecho cruza por delante (0.36 m de fondo entre los dos: los pies nunca se pisan). La cadera
    pasa el peso sobre el pie apoyado y se inclina apenas hacia donde va, el pecho y la cabeza no dejan de mirar a Kaito
    y la hoja sigue apuntándole como en Walk. 10 cuadros por ciclo: con el de Walk (14) cada paso medía 0.47 m y los
    pies se cruzaban de más."""
    n, duty = 10, 0.58
    sgn = 1.0 if side == "L" else -1.0               # +X = su izquierda
    vel = (sgn * N.WALK_SPEED, 0.0)
    feet = {"r": (-0.13, -0.15, 8.0), "l": (0.14, 0.17, 32.0)}
    g = gait_dir(ch, n, vel, duty, feet, lift=0.07, strike=8.0, off=16.0)

    def pose(f):
        c = dict(N.STANCE)
        c.update(g(f))
        sw, bob = _sway(f, n, duty)
        a = 2.0 * math.pi * f / n
        c["hips"] = (0.035 * -sw, 0.03, -0.095 - 0.012 * bob)
        c["hips_rot"] = (5.0, sgn * 3.0 + 2.0 * sw, 18.0 - 4.0 * math.sin(a))
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
    n, duty = 14, 0.58
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


# el salto del bambú: EnemyArchetypes.NinjaBambooMoves (Hit("Leap", ...), NinjaApexLeap) desde 3.8-6.6 m
LEAP = dict(n=48, apex=14, contact=34, active_end=38, land=40, lunge=4.4, windup=0.8, height=1.0)


def ninja_leap(ch, N):
    """El salto del bambú (4.4 m): se agazapa al ras con la hoja baja adelante y la mano libre casi en el piso (aviso:
    desde arriba, el ninja más bajo y compacto, como un resorte; distinto del hasso del Attack3 con la hoja atrás de la
    cabeza), se hunde más en el
    apex y salta en un arco alto de 1 m: sube con las rodillas recogidas llevando la hoja sobre la cabeza con las dos
    manos, la echa atrás arriba del salto y parte de arriba cayendo (el golpe pega a 0.6 m del piso, todavía en el aire).
    Cae aplastado con la punta en el piso y se rearma. El vuelo dura 0.51 s del reloj del juego, de la suelta (f14) al
    aterrizaje (f40): la embestida entera del juego pasa con los dos pies en el aire. El arco es del clip; VariantMotion
    solo levanta el cuerpo si el controller no tiene este estado (vuelve al Attack3)."""
    m = LEAP
    n, apex, contact, land, lunge = m["n"], m["apex"], m["contact"], m["land"], m["lunge"]
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=m["windup"])
    times = frame_times(n, apex, contact, m["windup"])
    arc = hop_arc(times, apex, land, m["height"])
    P, FR, FL = N.P, N.FR, N.FL
    CROUCH = P(hips=(0.0, 0.06, -0.24), hips_rot=(26.0, 0.0, 22.0), spine=(14.0, 0.0, -8.0), chest=(6.0, 0.0, -14.0),
               head=(-34.0, 0.0, -8.0), knee_r=(-0.5, -1.0, 0.0), knee_l=(0.7, -0.8, 0.0),
               grip=(-0.16, -0.24, 0.50), blade=(0.10, -0.88, -0.46), edge=(-0.99, -0.11, 0.0), elbow_r=(-0.8, 0.4, -0.4),
               hand_l=(0.16, -0.40, 0.34), hand_l_dir=(0.0, -0.5, -0.85), hand_l_palm=(0.0, 0.3, -0.95), elbow_l=(0.8, -0.2, -0.6),
               fist_l=0.3, grip_l=0.0)
    HOLD = dict(CROUCH, hips=(0.0, 0.07, -0.27), head=(-36.0, 0.0, -8.0), grip=(-0.16, -0.23, 0.47), hand_l=(0.16, -0.40, 0.31))
    # despegue: las piernas estiradas, el cuerpo sale inclinado hacia Kaito, la hoja empieza a subir y la mano libre
    # va al mango (lo agarra en el aire)
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
    keys = [Key(0, P()), Key(9, CROUCH, "inout"), Key(apex, HOLD, "sine"), Key(16, PUSH, "out"), Key(22, RISE, "inout"),
            Key(29, COCK, "sine"), Key(contact, CONTACT, "in"), Key(37, FOLLOW, "out"), Key(land, LAND, "in2"),
            Key(42, PUNISH, "out"), Key(n, P(), "sine")]
    span = float(land - apex)
    tuck = lambda f: 0.26 * max(0.0, math.sin(math.pi * (f - apex) / span)) ** 1.5
    fly_r = [FR(f, tr[f] + 0.06 * (f - apex) / span, z=arc(f) + tuck(f), pitch=-6.0, ease="lin", lift=0.0)
             for f in range(apex + 1, land)]
    fly_l = [FL(f, tr[f] - 0.04, z=arc(f) + 0.85 * tuck(f), pitch=26.0 * (1.0 - (f - apex) / span), ease="lin", lift=0.0)
             for f in range(apex + 1, land + 1)]
    feet = {"r": [FR(0), FR(apex, pitch=-4.0)] + fly_r
                 + [FR(land, lunge + 0.06, pitch=-10.0, ease="lin", lift=0.0), FR(land + 2, lunge + 0.06), FR(45, lunge + 0.06),
                    FR(n, lunge, lift=0.03)],
            "l": [FL(0), FL(9), FL(apex, pitch=30.0)] + fly_l
                 + [FL(land + 2, lunge - 0.05, ease="out", lift=0.0), FL(45, lunge - 0.05), FL(n, lunge, lift=0.03)]}
    return ArcClip("Leap", n, keys, travel=tr, feet=feet, arc=arc, notes="salto del bambú: arco alto de 1 m, parte de arriba al caer",
                   timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, m["active_end"]], hold=[9, apex],
                               lunge=lunge, windup=m["windup"], state="Leap", land=land, hop_m=m["height"], reach=1.6,
                               sheet=[9, apex, 16, 22, 29, contact, 37, land, 42, n]))


# el remolino del lago: EnemyArchetypes.NinjaLakeMoves (Hit("Whirl", ...), NinjaApexWhirl); encadenado detrás del
# Attack1 (windup mínimo 0.5 s de un pesado encadenado + 0.1 de telegraph)
WHIRL = dict(n=36, apex=10, contact=20, active_end=24, land=26, lunge=1.1, windup=0.6, height=0.30)
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
    la suelta despega y gira a la izquierda (antihorario visto desde arriba) 470°: arranca de golpe, la hoja barre el
    círculo entero y pega cuando vuelve a pasar por delante (f20: el disco de 360° de Enemy), sigue 40° y cae en la
    guardia (f26) frenando el giro. Los pies giran con el cuerpo en el aire, ninguno apoyado mientras gira. Antes el
    remolino era el Attack2 girado entero por VariantMotion con los pies en el piso (patinaban 0.8 m en círculo);
    VariantMotion ya no lo gira si existe este estado. La pose del brazo es la del contacto del Attack1 (validada: el
    antebrazo cerca de neutro), girada con el cuerpo."""
    m = WHIRL
    n, apex, contact, land, lunge = m["n"], m["apex"], m["contact"], m["land"], m["lunge"]
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=m["windup"])
    times = frame_times(n, apex, contact, m["windup"])
    arc = hop_arc(times, apex, land, m["height"])
    P, FR, FL = N.P, N.FR, N.FL
    coil, after = -70.0, 40.0
    total = 360.0 - coil + after

    def g(f):
        u = min(1.0, max(0.0, (times[f] - times[apex]) / (times[land] - times[apex])))
        return 1.0 - (1.0 - u) ** 2.2

    def turn(f):
        """Giro del cuerpo respecto del tajo del Attack1 (°): enroscado en el apex, la vuelta entera y 40° más al caer."""
        if f <= apex:
            return coil
        return coil + total * g(f)

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
    keys = [Key(0, P()), Key(6, TELL, "inout"), Key(apex, HOLD, "sine")]
    for f in range(apex + 1, land):
        # en el aire: la cabeza deja de mirar atrás (gira con el cuerpo y busca a Kaito al volver); la mano libre queda
        # recogida al pecho (abierta pedía medio giro del antebrazo en un cuadro)
        q = (f - apex) / float(land - apex)
        body = dict(TUCK, hips=(0.0, -0.02, -0.11 + 0.04 * math.sin(math.pi * q)),
                    head=(-10.0, 0.0, -12.0 + 52.0 * (1.0 - min(1.0, q * 1.6))))
        keys.append(Key(f, _spin(body, turn(f)), "lin"))
    LAND = dict(TUCK, hips=(0.0, -0.02, -0.21), hips_rot=(12.0, 0.0, 16.0), spine=(14.0, 0.0, 6.0), head=(-14.0, 0.0, -10.0),
                grip=(-0.12, -0.34, 0.76))
    keys += [Key(land, _spin(LAND, coil + total), "out"),
             Key(30, _spin(dict(LAND, hips=(0.0, -0.02, -0.17)), coil + total), "sine"),
             Key(n, _spin(P(), 360.0), "sine")]
    span = float(land - apex)
    tuck = lambda f: 0.16 * max(0.0, math.sin(math.pi * (f - apex) / span)) ** 1.5

    def foot(stance, f, z):
        """Un pie en el aire: su lugar de la guardia girado con el cuerpo (una vuelta entera hasta caer) y con el avance."""
        d = 360.0 * g(f)
        x0, y0, yaw0 = stance
        p = Matrix.Rotation(math.radians(d), 3, 'Z') @ NA.V((x0, y0, 0.0))
        return T.FootKey(f, p.x, p.y - tr[f], yaw0 + d, 0.0, z, 0.0, "lin", 0.0)

    R0, L0 = N.R0, N.L0
    fly_r = [foot(R0, f, arc(f) + tuck(f)) for f in range(apex + 1, land)]
    fly_l = [foot(L0, f, arc(f) + 0.85 * tuck(f)) for f in range(apex + 1, land)]
    feet = {"r": [FR(0), FR(apex, pitch=10.0)] + fly_r + [T.FootKey(land, R0[0], R0[1] - lunge, R0[2] + 360.0, -8.0, 0.0, 0.0, "lin", 0.0),
                                                       T.FootKey(land + 2, R0[0], R0[1] - lunge, R0[2] + 360.0)],
            "l": [FL(0), FL(apex, pitch=26.0)] + fly_l + [T.FootKey(land + 1, L0[0], L0[1] - lunge, L0[2] + 360.0, 0.0, 0.0, 0.0, "out", 0.0),
                                                       T.FootKey(n, L0[0], L0[1] - lunge, L0[2] + 360.0)]}
    return ArcClip("Whirl", n, keys, travel=tr, feet=feet, arc=arc, tremble=0.006,
                   notes="remolino del lago: una vuelta entera en el aire con la hoja horizontal",
                   timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, m["active_end"]], hold=[6, apex],
                               lunge=lunge, windup=m["windup"], state="Whirl", land=land, hop_m=m["height"], spin_deg=total,
                               reach=1.6, sheet=[6, apex, 12, 14, 16, 18, contact, 22, land, n]))


def ninja_clips(ch, N):
    return [ninja_strafe(ch, N, "L"), ninja_strafe(ch, N, "R"), ninja_walk_back(ch, N), ninja_leap(ch, N), ninja_whirl(ch, N)]


# ============================================================================== sumo
def sumo_strafe(ch, S, side):
    """De costado (1.6 m/s): suri-ashi abierto, el pie que guía abre y el otro se arrima sin cruzar nunca (las piernas
    del sumo no se pueden cruzar). Los pies se separan entre 0.5 y 1.1 m y casi no se despegan del piso; la panza pasa
    de un pie al otro, los brazos cuelgan y se abren apenas del lado al que va, la cabeza no deja de mirar a Kaito."""
    n, duty = 12, 0.64
    sgn = 1.0 if side == "L" else -1.0
    vel = (sgn * S.WALK_SPEED, 0.0)
    feet = {"r": (-0.40, 0.02, -20.0), "l": (0.40, 0.02, 20.0)}
    g = gait_dir(ch, n, vel, duty, feet, lift=0.06, strike=0.0, off=10.0)

    def pose(f):
        a = 2.0 * math.pi * f / n
        c = dict(S.STANCE)
        c.update(g(f))
        sw, bob = _sway(f, n, duty)
        c["hips"] = (0.07 * -sw, 0.02, -0.12 - 0.02 * bob)
        c["hips_rot"] = (6.0, sgn * 2.0 + 4.0 * sw, 0.0)
        c["spine"] = (6.0, -3.0 * sw, 0.0)
        c["head"] = (-10.0, -sgn * 1.0 - 1.0 * sw, 0.0)
        out = 0.03 * sgn
        c["hand_r"] = (-0.64 + out - 0.02 * sw, -0.20, 1.05 + 0.02 * bob)
        c["hand_l"] = (0.64 + out - 0.02 * sw, -0.20, 1.05 + 0.02 * bob)
        return c
    name = "Strafe" + side
    return NA.ProcClip(name, n, pose, loop=True, root_vel=(vel[0], vel[1], 0.0),
                       notes=f"de costado hacia su {'izquierda' if side == 'L' else 'derecha'} a {S.WALK_SPEED:g} m/s (rodeo)")


def sumo_walk_back(ch, S):
    """Para atrás (1.6 m/s): pasos pesados de punta, la panza adelante y el peso de un pie al otro."""
    n, duty = 20, 0.62
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


# el empujón del lago: EnemyArchetypes.SumoLakeMoves (Hit("Morote", ...), SumoApexMorote); encadenado detrás de una
# bofetada (windup mínimo 0.5 s de un pesado encadenado)
MOROTE = dict(n=36, apex=12, contact=22, active_end=27, lunge=1.6, windup=0.5)


def sumo_morote(ch, S):
    """Morote-zuki (el empujón a dos manos del sumo del lago, 1.6 m: te saca lejos). Aviso: agachado y cargado atrás,
    las dos manos abiertas junto a la panza con las palmas adelante y los codos atrás (desde arriba, el sumo más ancho
    y bajo que nunca, distinto del harite de una mano arriba). Suelta: arranca de un empujón, el derecho y el izquierdo
    entran rápido (la embestida es casi toda en f12-f20) y en el contacto los dos brazos están estirados a la altura del
    pecho con el cuerpo inclinado detrás, como quien empuja una pared; sostiene, se acomoda y vuelve a la guardia. Los
    pies van en el mundo y nunca quedan apoyados lejos de la cadera: el transform corre 0.32 m en el primer cuadro de la
    suelta (u² del reloj del juego) y el izquierdo despega ahí."""
    m = MOROTE
    n, apex, contact, lunge = m["n"], m["apex"], m["contact"], m["lunge"]
    tr, _ = T.lunge_travel(n, apex, contact, lunge, windup_min=m["windup"])
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
    feet = {"r": [FR(0), FR(apex, pitch=18.0), FR(16, 0.86, pitch=-8.0, lift=0.10), FR(17, 0.86),
                  FR(21, 0.86, pitch=20.0), FR(26, lunge, lift=0.08), FR(n, lunge)],
            "l": [FL(0), FL(apex, pitch=14.0), FL(13, pitch=28.0), FL(19, 1.52, pitch=-8.0, lift=0.12),
                  FL(20, 1.52), FL(33, 1.52), FL(n, lunge, lift=0.03)]}
    return T.TeamClip("Morote", n, keys, travel=tr, feet=feet, notes="morote del lago: empuja con los dos brazos estirados",
                      timing=dict(kind="heavy", apex=apex, contact=contact, active=[contact, m["active_end"]], hold=[8, apex],
                                  lunge=lunge, windup=m["windup"], state="Morote", striker="r", reach=1.4))


# las palmas del morote en el contacto (marco de autoría): los dos brazos estirados desde los hombros del cuerpo inclinado
MOROTE_REACH = (-0.30, -1.15, 1.45)


def sumo_clips(ch, S):
    return [sumo_strafe(ch, S, "L"), sumo_strafe(ch, S, "R"), sumo_walk_back(ch, S), sumo_morote(ch, S)]
