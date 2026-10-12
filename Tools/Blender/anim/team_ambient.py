"""Idles ambientales del ninja y del sumo (ítem 5 del traspaso): lo que hacen ANTES de que empiece la pelea, para que
los enemigos no estén parados esperando. Los usa Enemies/EnemyAmbient.cs (estados del Animator con estos nombres):

  ninja  IdleMeditate  sentado con las piernas cruzadas sobre una roca chica (EnemyAmbient la pone), la katana cruzada
                       sobre los muslos, respira hondo                                                  loop 4 s
         AmbientAlert  desde IdleMeditate: se sobresalta, apoya la mano en la roca, salta adelante al piso y desenvaina
                       hasta la guardia (termina en el cuadro 0 de Idle)                                0.0-1.47 s
         IdleSparA/B   práctica de a dos, enfrentados a SPAR_GAP m: A corta, B para (choque de hojas en el cuadro
                       SPAR_CLASH), después al revés. B es A corrido medio ciclo: se tocan en los mismos cuadros  loop 3.2 s
         IdleInspect   parado y suelto, mira el filo, pasa los dedos por el lomo, lo da vuelta y sacude la hoja (chiburi)
  sumo   IdleSleep     sentado en el piso con las piernas abiertas, las manos en la panza, la cabeza caída: respira y
                       ronca (EnemyAmbient suelta el humito en SLEEP_SNORE)                              loop 4 s
         AmbientAlert  desde IdleSleep, más lento (despertar justo y legible): resopla, mira a los costados, ve a Kaito,
                       recoge los pies, se levanta empujando en las rodillas y se palmea los muslos      2.4 s
         IdleShiko     el estiramiento del shiko de los dos lados: sube una pierna al costado, la sostiene, pisa y baja
                       en cuclillas (EnemyAmbient levanta polvo en SHIKO_STOMPS)                         loop 5 s

Los idles parados (Spar, Inspect, Shiko) despiertan con el Spotted de siempre: el saltito del ninja o el palmeo del sumo
esconden el cruce. Los sentados tienen su AmbientAlert, que termina en el Idle y nunca ataca desde la pose ambiental.
El marco de autoría es el de team_rig (frente -Y, izquierda +X, metros del juego, origen en el transform del juego).
"""
import math
import nindo_anim as NA
import team_rig as T

Key = NA.Key

# ============================================================================================ ninja
# la roca del que medita: rock_small_a escalada (EnemyAmbient.cs, RockScale) con el centro SEAT_BACK m detrás del
# transform, así el salto del despertar cae en el lugar del enemigo (en la guardia, delante de la roca)
SEAT_BACK = 0.72
ROCK_ID = "rock_small_a"     # 0.70 x 0.30 x 0.64 m (ancho, alto, fondo); la cara de arriba es plana
ROCK_SCALE = (1.3, 1.32, 1.12)  # escala en Unity (x ancho, y alto, z fondo): 0.91 x 0.40 x 0.72 m
ROCK_TOP = 0.40              # alto de la cara de arriba de la roca escalada (m)
ROCK_FRONT = SEAT_BACK - 0.36   # borde delantero de la roca (y): el pie de atrás de la guardia queda delante
# pareja que practica: distancia entre los transforms y cuadros del choque de las hojas (IdleSparA; en B son los mismos)
SPAR_GAP = 1.70
SPAR_CLASH = (15, 63)


def _meditate_pose(N, br=0.0):
    """Sentado en la roca con las piernas cruzadas (los pies juntos delante de la entrepierna: las piernas del ninja son
    cortas), la espalda derecha y la cabeza apenas inclinada; la derecha descansa en la rodilla con el mango, la hoja
    cruzada sobre los muslos hacia la izquierda; la izquierda apoyada en la rodilla. 'br' 0..1 respira."""
    z0 = ROCK_TOP
    return N.P(hips=(0.011, SEAT_BACK, z0 + 0.135 - 0.638 + 0.012 * br), hips_rot=(-4.0, 0.0, 0.0),
               spine=(4.0 - 2.5 * br, 0.0, 0.0), chest=(-2.0 - 4.0 * br, 0.0, 0.0), head=(16.0 - 7.0 * br, 0.0, 0.0),
               clav_r=(0.0, 0.0, 4.0 * br), clav_l=(0.0, 0.0, -4.0 * br), breath=br,
               knee_r=(-1.0, -0.55, 0.35), knee_l=(1.0, -0.55, 0.35),
               grip=(-0.24, SEAT_BACK - 0.32, z0 + 0.25), blade=(1.0, 0.06, -0.02), edge=(0.0, -1.0, 0.0), elbow_r=(-0.9, 0.4, -0.3),
               hand_l=(0.26, SEAT_BACK - 0.30, z0 + 0.27), hand_l_dir=(0.15, -0.85, -0.5), hand_l_palm=(0.0, -0.3, -1.0),
               elbow_l=(0.9, 0.4, -0.3), fist_l=0.35, grip_l=0.0, auto_drop=0.0)


def _seat_feet(f):
    """Los pies cruzados sobre la roca: el derecho delante del izquierdo, de canto y con la punta hacia adentro."""
    z = ROCK_TOP
    return (T.FootKey(f, 0.05, SEAT_BACK - 0.27, 62.0, 0.0, z + 0.02, -38.0),
            T.FootKey(f, -0.05, SEAT_BACK - 0.20, -62.0, 0.0, z + 0.03, 38.0))


def meditate(N):
    n = 120
    keys = [Key(f, _meditate_pose(N, 0.5 - 0.5 * math.cos(2.0 * math.pi * f / n)), "sine") for f in (0, 30, 60, 90, 120)]
    fr, fl = _seat_feet(0)
    return T.TeamClip("IdleMeditate", n, keys, loop=True, feet={"r": [fr], "l": [fl]}, tremble=0.0,
                      notes="medita sentado en la roca, la katana sobre los muslos",
                      timing=dict(ambient="meditate", seat_back=SEAT_BACK, rock_top=ROCK_TOP))


def ambient_alert(N):
    """Desde la meditación: f0 sentado; f3-f6 el sobresalto (la cabeza sube de golpe, los hombros se encogen, aprieta el
    mango); f6-f11 se inclina adelante, apoya la izquierda en la roca y descruza las piernas; f11-f14 empuja; vuela
    f14-f20 con la hoja que sube vertical delante de la cara; cae en f20 en cuclillas en su lugar y amortigua; desenvaina
    hacia abajo hasta la guardia (f28-f34) y se acomoda. EnemyAmbient no lo deja girar hacia Kaito hasta que aterriza
    (LAND): sentado en la roca, el giro lo sacaría de ella."""
    n = 44
    z0 = ROCK_TOP
    M = _meditate_pose(N, 0.0)
    I0 = N.idle().keys[0].ctrl          # termina en el cuadro 0 de Idle (Enemy entra a la locomoción con un cruce)
    # el sobresalto se tiene que leer a 100 px: el cuerpo da un respingo en el asiento (4 cm), se echa atrás, la cabeza
    # sube de golpe y las manos se despegan de las rodillas
    STARTLE = dict(M, hips=(0.011, SEAT_BACK + 0.02, z0 + 0.135 - 0.638 + 0.045), spine=(-8.0, 0.0, 0.0), chest=(-8.0, 0.0, 0.0),
                   head=(-18.0, 0.0, 0.0), clav_r=(0.0, 0.0, 10.0), clav_l=(0.0, 0.0, -10.0),
                   grip=(-0.25, SEAT_BACK - 0.33, z0 + 0.32), hand_l=(0.28, SEAT_BACK - 0.30, z0 + 0.34))
    LEAN = dict(STARTLE, hips=(0.011, SEAT_BACK - 0.10, z0 + 0.135 - 0.638 + 0.01), hips_rot=(14.0, 0.0, 0.0), spine=(16.0, 0.0, 0.0),
                chest=(4.0, 0.0, 0.0), head=(-22.0, 0.0, 0.0),
                grip=(-0.26, SEAT_BACK - 0.42, z0 + 0.36), blade=(0.75, -0.15, 0.65), edge=(0.0, -1.0, 0.0),
                # se apoya en los nudillos sobre la roca (la palma plana no entra en la muñeca con el brazo vertical: la
                # mano se enderezaba y los dedos se metían 11 cm en la roca)
                hand_l=(0.36, SEAT_BACK - 0.10, z0 + 0.145), hand_l_dir=(0.1, -0.25, -0.96), hand_l_palm=(0.0, 1.0, 0.0),
                elbow_l=(1.0, 0.6, 0.1), fist_l=0.85, knee_r=(-0.4, -1.0, 0.0), knee_l=(0.4, -1.0, 0.0))
    PUSH = dict(LEAN, hips=(0.011, SEAT_BACK - 0.28, z0 + 0.135 - 0.638 + 0.10), hips_rot=(18.0, 0.0, 0.0), spine=(12.0, 0.0, 0.0),
                head=(-20.0, 0.0, 0.0), grip=(-0.22, SEAT_BACK - 0.58, z0 + 0.55), blade=(0.3, -0.25, 0.92), edge=(0.0, -1.0, 0.0),
                hand_l=(0.36, SEAT_BACK - 0.14, z0 + 0.15))
    AIR = N.P(hips=(0.0, 0.18, 0.02), hips_rot=(6.0, 0.0, 6.0), spine=(4.0, 0.0, 0.0), chest=(-4.0, 0.0, -4.0), head=(-12.0, 0.0, 0.0),
                      knee_r=(-0.3, -1.0, 0.2), knee_l=(0.4, -1.0, 0.2),
                      grip=(-0.12, -0.18, 1.05), blade=(0.0, -0.18, 1.0), edge=(0.0, -1.0, 0.0), elbow_r=(-0.9, 0.2, -0.3),
                      # la izquierda se abre para equilibrar el salto con la palma abajo, como estaba apoyada en la roca
                      hand_l=(0.30, -0.10, 0.90), hand_l_dir=(0.3, -0.6, -0.7), hand_l_palm=(0.0, -0.3, -0.95), fist_l=0.2, auto_drop=0.0)
    LAND = N.P(hips=(0.0, 0.05, -0.20), hips_rot=(14.0, 0.0, 16.0), spine=(12.0, 0.0, -4.0), chest=(4.0, 0.0, -6.0), head=(-20.0, 0.0, -4.0),
               knee_r=(-0.25, -1.0, 0.0), knee_l=(0.55, -1.0, 0.0),
               grip=(-0.14, -0.26, 0.86), blade=(0.05, -0.30, 0.95), edge=(0.0, -1.0, 0.0),
               hand_l=(0.20, -0.08, 0.80), hand_l_dir=(-0.3, -0.5, 0.7), hand_l_palm=(-0.7, -0.5, 0.0))
    SINK = dict(LAND, hips=(0.0, 0.04, -0.23), grip=(-0.15, -0.27, 0.82))
    DRAW = N.P(hips=(0.0, 0.03, -0.12), hips_rot=(6.0, 0.0, 20.0), spine=(8.0, 0.0, -6.0), chest=(4.0, 0.0, -9.0), head=(-10.0, 0.0, -4.0),
               grip=(-0.17, -0.32, 0.80), blade=(0.26, -0.90, 0.30), edge=N.LOOP_EDGE)
    keys = [Key(0, M), Key(3, STARTLE, "snap"), Key(6, dict(STARTLE, hips=(0.011, SEAT_BACK + 0.01, z0 + 0.135 - 0.638 + 0.03), head=(-14.0, 0.0, 0.0)), "out"),
            Key(11, LEAN, "inout"), Key(14, PUSH, "in"), Key(17, AIR, "out"), Key(20, LAND, "in2"), Key(24, SINK, "out"),
            Key(30, DRAW, "inout"), Key(36, dict(I0, hips=(0.0, 0.034, -0.085)), "sine"), Key(n, I0, "sine")]
    fr, fl = _seat_feet(0)
    # descruza: los pies salen al borde de la roca a la altura de su cara (f10), bajan por delante de ella (f13: con los pies
    # todavía sobre la roca las canillas la atravesaban 13 cm) y caen en la guardia
    feet = {"r": [fr, T.FootKey(6, fr.x, fr.y, fr.yaw, 0.0, fr.z, fr.roll),
                  T.FootKey(10, -0.10, ROCK_FRONT - 0.06, 20.0, 10.0, z0 + 0.01, 0.0, "inout", 0.0),
                  T.FootKey(13, -0.11, ROCK_FRONT - 0.13, 14.0, 24.0, z0 - 0.07, 0.0, "inout", 0.0),
                  T.FootKey(16, -0.12, -0.08, 8.0, 30.0, 0.16, 0.0, "out", 0.0),
                  N.FR(20, ease="in", lift=0.0), N.FR(n)],
            "l": [fl, T.FootKey(6, fl.x, fl.y, fl.yaw, 0.0, fl.z, fl.roll),
                  T.FootKey(10, 0.12, ROCK_FRONT - 0.05, 30.0, 10.0, z0 + 0.01, 0.0, "inout", 0.0),
                  T.FootKey(13, 0.13, ROCK_FRONT - 0.11, 32.0, 24.0, z0 - 0.06, 0.0, "inout", 0.0),
                  T.FootKey(16, 0.16, 0.12, 36.0, 30.0, 0.18, 0.0, "out", 0.0),
                  N.FL(20, pitch=10.0, ease="in", lift=0.0), N.FL(23), N.FL(n)]}
    return T.TeamClip("AmbientAlert", n, keys, feet=feet, tremble=0.0,
                      notes="se sobresalta en la roca, salta adelante y desenvaina a la guardia",
                      timing=dict(ambient="alert_meditate", land=20, sheet=[0, 3, 6, 11, 14, 17, 20, 24, 30, 36, n],
                                  chain=[(n, "Idle", 0, 0.03)], slide_ok=3.0))


def _n(v):
    l = math.sqrt(sum(x * x for x in v))
    return tuple(x / l for x in v)


def spar_geometry():
    """Dónde se tocan las hojas. B para con la hoja casi vertical a su derecha (delante del hombro, 0.10 m atrás de su
    lugar); el choque es a media hoja de B (SPAR_SB) y a SPAR_SA de la de A, que corta en diagonal de arriba a la derecha
    hacia abajo a la izquierda, todavía alto. Con la cabeza enorme del ninja no hay parada por arriba de la cabeza: la
    mano no llega ahí (hombros a 1.11 m, brazos de 0.46). En el marco de A un punto (x, y, z) de B es (-x, -GAP - y, z).
    Devuelve (agarre y hoja de B en su marco, agarre y hoja de A en el suyo, punto del choque en el marco de A)."""
    gB, bB = (-0.24, -0.20, 0.98), _n((-0.22, -0.35, 0.91))
    pB = tuple(g + SPAR_SB * b for g, b in zip(gB, bB))
    C = (-pB[0], -SPAR_GAP - pB[1], pB[2])
    gx, gz = -0.05, 1.18
    bx, bz = (C[0] - gx) / SPAR_SA, (C[2] - gz) / SPAR_SA
    bA = (bx, -math.sqrt(max(0.0, 1.0 - bx * bx - bz * bz)), bz)
    gA = (gx, C[1] - SPAR_SA * bA[1], gz)
    return gB, bB, gA, bA, C


SPAR_SA, SPAR_SB = 0.70, 0.50
SPAR_N, SPAR_HALF = 96, 48
SPAR_STEP_IN, SPAR_STEP_BACK = 0.40, 0.10


def _spar_halves(N):
    """Las dos mitades del ejercicio en el marco del que las hace, cada una de READY a READY: (claves, pies) de 'corta'
    y de 'para'. A = corta + para, B = para + corta (los choques caen en los mismos cuadros)."""
    gB, bB, gA, bA, C = spar_geometry()
    c = SPAR_CLASH[0]
    # guardia del medio de práctica (seigan): las dos manos en el mango y la punta a la garganta del otro, abierta hacia
    # la izquierda (como la guardia de pelea): las puntas de los dos se cruzan en la vista de perfil pero pasan a ~0.3 m
    # una de la otra (cada una hacia su izquierda); con la punta al centro las hojas se tocaban todo el tiempo
    READY = N.P(hips=(0.0, 0.03, -0.085), hips_rot=(4.0, 0.0, 14.0), spine=(6.0, 0.0, -4.0), chest=(2.0, 0.0, -6.0), head=(-8.0, 0.0, -4.0),
                grip=(-0.14, -0.28, 0.82), blade=_n((-0.05, -0.90, 0.40)), edge=(0.05, -0.35, -1.0), elbow_r=(-0.8, 0.3, -0.6),
                grip_l=1.0, elbow_l=(0.8, 0.3, -0.6), fist_l=1.0)
    PRESS = dict(READY, hips=(0.0, 0.0, -0.09), spine=(9.0, 0.0, -4.0), grip=(-0.13, -0.31, 0.86), blade=_n((-0.04, -0.86, 0.50)))
    # furikaburi: las manos sobre el hombro derecho y la punta atrás y arriba; el peso pasa al pie de atrás
    # (las manos y la hoja del hasso del Attack3, que el brazo izquierdo en el mango ya resuelve sin saltos)
    RAISE = N.P(hips=(0.0, 0.08, -0.09), hips_rot=(-2.0, 0.0, 14.0), spine=(-6.0, 0.0, -6.0), chest=(-10.0, 0.0, -10.0), head=(2.0, 0.0, -6.0),
                grip=(-0.18, -0.08, 1.32), blade=_n((-0.30, 0.55, 0.78)), edge=_n((0.37, -0.68, 0.62)), elbow_r=(-0.9, 0.2, -0.3),
                grip_l=1.0, elbow_l=(0.8, -0.2, -0.4), fist_l=1.0)
    s_in = SPAR_STEP_IN
    HIT = N.P(hips=(0.0, 0.03 - s_in * 0.75, -0.13), hips_rot=(10.0, 0.0, 6.0), spine=(12.0, 0.0, 2.0), chest=(4.0, 0.0, 2.0), head=(-14.0, 0.0, 0.0),
              grip=gA, blade=bA, edge=_n((0.27, -0.26, -0.92)), elbow_r=(-0.8, 0.3, -0.4),
              grip_l=1.0, elbow_l=(0.8, 0.3, -0.5), fist_l=1.0)
    # el rebote del choque: las hojas se separan unos centímetros y el cuerpo amortigua
    BOUNCE = dict(HIT, hips=(0.0, 0.05 - s_in * 0.85, -0.13), grip=(gA[0] - 0.03, gA[1] + 0.06, gA[2] + 0.04), blade=_n((bA[0] - 0.12, bA[1], bA[2] + 0.10)))
    BACK = dict(READY, hips=(0.0, 0.03 - s_in * 0.6, -0.10), spine=(8.0, 0.0, 0.0), grip=(-0.13, -0.30, 0.86))
    # el tajo en 4 cuadros con la hoja por arriba (SWING): en 3, de atrás del hombro al frente, el antebrazo rodaba de golpe
    SWING = dict(RAISE, hips=(0.0, 0.03 - s_in * 0.35, -0.10), hips_rot=(6.0, 0.0, 10.0), spine=(4.0, 0.0, 0.0), chest=(-4.0, 0.0, -4.0),
                 head=(-6.0, 0.0, -4.0), grip=(-0.14, -0.32, 1.34), blade=_n((0.20, -0.30, 0.93)), edge=_n((0.05, -0.97, 0.25)),
                 elbow_r=(-0.9, 0.1, -0.4), elbow_l=(0.8, 0.1, -0.5), knee_r=(-0.2, -1.0, 0.2))
    # sube en dos tiempos (adelante y arriba, después atrás del hombro): de la guardia al hasso de un saque la hoja giraba
    # 130° en 3 cuadros y la izquierda se soltaba del mango
    LIFT = dict(RAISE, hips=(0.0, 0.05, -0.09), hips_rot=(2.0, 0.0, 14.0), spine=(2.0, 0.0, -4.0), chest=(-4.0, 0.0, -6.0), head=(-4.0, 0.0, -4.0),
                grip=(-0.14, -0.26, 1.10), blade=_n((-0.05, -0.45, 0.89)), edge=_n((0.0, -0.89, -0.45)))
    attack = [Key(0, READY), Key(4, PRESS, "inout"), Key(8, LIFT, "inout"), Key(c - 4, RAISE, "out"), Key(c - 2, SWING, "in"), Key(c, HIT, "lin"),
              Key(c + 3, BOUNCE, "out"), Key(c + 10, BACK, "inout"), Key(c + 17, READY, "inout"), Key(SPAR_HALF, READY, "sine")]
    fa = {"r": [N.FR(0), N.FR(c - 4), N.FR(c, s_in, pitch=-6.0, ease="in", lift=0.04), N.FR(c + 6, s_in), N.FR(c + 14, 0.0, ease="inout")],
          "l": [N.FL(0), N.FL(c - 2), N.FL(c + 3, s_in - 0.02, ease="out"), N.FL(c + 8, s_in - 0.02), N.FL(c + 12, 0.0, ease="inout")]}
    # parada: mira cómo levanta el otro, retrocede 0.10 m (primero el pie de atrás) y para en el cuadro del choque
    s_b = SPAR_STEP_BACK
    WATCH = dict(READY, hips=(0.0, 0.04, -0.09), head=(-10.0, 0.0, -2.0), grip=(-0.08, -0.27, 0.86))
    BLOCK = N.P(hips=(0.0, 0.03 + s_b, -0.10), hips_rot=(2.0, 0.0, 14.0), spine=(2.0, 0.0, -4.0), chest=(-2.0, 0.0, -6.0), head=(-6.0, 0.0, 6.0),
                grip=(gB[0], gB[1], gB[2]), blade=bB, edge=_n((0.4, -0.9, -0.1)), elbow_r=(-0.9, 0.0, -0.4),
                grip_l=1.0, elbow_l=(0.6, -0.4, -0.6), fist_l=1.0)
    PUSHED = dict(BLOCK, hips=(0.0, 0.05 + s_b, -0.11), grip=(gB[0] - 0.02, gB[1] + 0.04, gB[2] - 0.01), blade=_n((bB[0] - 0.06, bB[1] + 0.10, bB[2])))
    defend = [Key(0, READY), Key(8, WATCH, "inout"), Key(c - 4, dict(READY, hips=(0.0, 0.03 + s_b * 0.5, -0.10)), "inout"),
              Key(c, BLOCK, "out"), Key(c + 3, PUSHED, "out"), Key(c + 8, BLOCK, "inout"), Key(c + 18, READY, "inout"), Key(SPAR_HALF, READY, "sine")]
    fd = {"l": [N.FL(0), N.FL(c - 6), N.FL(c - 2, -s_b, ease="out", lift=0.03), N.FL(c + 10, -s_b), N.FL(c + 16, 0.0)],
          "r": [N.FR(0), N.FR(c - 4), N.FR(c, -s_b, ease="out", lift=0.03), N.FR(c + 12, -s_b), N.FR(c + 18, 0.0)]}
    return (attack, fa), (defend, fd)


def _join(h1, h2, off):
    keys = list(h1[0]) + [Key(k.frame + off, k.ctrl, k.ease, k.ease_ch) for k in h2[0] if k.frame > 0]
    feet = {}
    for k in ("r", "l"):
        feet[k] = list(h1[1][k]) + [T.FootKey(fk.frame + off, fk.x, fk.y, fk.yaw, fk.pitch, fk.z, fk.roll, fk.ease, fk.lift)
                                     for fk in h2[1][k] if fk.frame > 0]
    return keys, feet


def spar(N):
    att, dfn = _spar_halves(N)
    out = []
    for name, (h1, h2), note in (("IdleSparA", (att, dfn), "práctica: corta primero, después para"),
                                 ("IdleSparB", (dfn, att), "práctica: para primero, después corta")):
        keys, feet = _join(h1, h2, SPAR_HALF)
        out.append(T.TeamClip(name, SPAR_N, keys, loop=True, feet=feet, tremble=0.0, notes=note,
                              timing=dict(ambient="spar", gap=SPAR_GAP, clash=list(SPAR_CLASH), read=list(SPAR_CLASH),
                                          sheet=[0, 7, 12, 15, 18, 25, 32, 48, 56, 60, 63, 66, 75, 96])))
    return out


def _along(grip, blade, s, off):
    """Punto de la hoja a 's' m del puño, corrido 'off' (m, vector del marco de autoría)."""
    return tuple(g + s * b + o for g, b, o in zip(grip, blade, off))


def inspect(N):
    """Parado y suelto (los pies de la guardia, así el Spotted entra sin arrastrarlos), mira el filo a lo largo con la hoja
    adelante y en diagonal y pasa los dedos de la izquierda por el lomo (f0-f40), la gira para ver la otra cara (f40-f58), la
    baja y la sacude de un tirón (chiburi, f70-f78: la hoja barre abajo y afuera a la derecha), la mira de nuevo y la
    vuelve a subir. Desde la cámara del juego: la hoja vertical y después la sacudida que abre la silueta."""
    n = 120
    # la hoja adelante y en diagonal hacia arriba a la izquierda, a la altura del pecho, la mira a lo largo (parada delante
    # de la cara no se veía desde arriba: quedaba tapada por la cabeza)
    gU, bU = (-0.14, -0.26, 0.98), _n((0.45, -0.80, 0.40))
    # la izquierda sigue la hoja: la yema sobre la cara de arriba y los dedos hacia la punta. Los filos de todo el loop
    # (mirar, girar, bajar, sacudir) son de la misma rama del antebrazo (supinado, 15° a 85°): con el filo hacia la derecha
    # al mirar, el antebrazo pronado tenía que dar 125° de vuelta para la sacudida y saltaba de golpe al volver
    back = (0.0, 0.0, 0.03)
    BASE = dict(hips=(0.0, 0.03, -0.055), hips_rot=(2.0, 0.0, 22.0), spine=(4.0, 0.0, -8.0), chest=(2.0, 0.0, -8.0),
                head=(-16.0, 4.0, 10.0), knee_r=(-0.25, -1.0, 0.0), knee_l=(0.55, -1.0, 0.0), elbow_r=(-0.9, 0.3, -0.4),
                elbow_l=(0.9, 0.0, -0.5), grip_l=0.0)
    LOOK0 = N.P(**BASE, grip=gU, blade=bU, edge=_n((0.74, 0.10, -0.66)),
                hand_l=_along(gU, bU, 0.22, back), hand_l_dir=bU, hand_l_palm=(0.0, 0.0, -1.0), fist_l=0.25)
    g1 = (-0.13, -0.27, 1.00)
    LOOK1 = dict(LOOK0, head=(-12.0, 4.0, 20.0), grip=g1, hand_l=_along(g1, bU, 0.50, back))
    # la izquierda se va a la cadera y la hoja gira: se ve la otra cara
    TURN = dict(LOOK1, head=(-14.0, -2.0, 16.0), grip=(-0.13, -0.28, 1.02), blade=_n((0.42, -0.78, 0.46)), edge=_n((0.20, -0.35, -0.92)),
                hand_l=(0.22, -0.04, 0.80), hand_l_dir=(0.1, -0.3, -0.95), hand_l_palm=(-1.0, 0.0, 0.0), fist_l=0.4)
    LOW = dict(TURN, head=(-8.0, 0.0, 6.0), hips_rot=(2.0, 0.0, 16.0), grip=(-0.06, -0.34, 1.06), blade=_n((0.30, -0.50, 0.81)),
               edge=_n((0.42, -0.70, -0.58)))
    # chiburi: la hoja barre de arriba a la izquierda hacia abajo y afuera a la derecha y frena de golpe
    FLICK = dict(LOW, hips=(0.0, 0.03, -0.075), hips_rot=(4.0, 0.0, 28.0), chest=(2.0, 0.0, -14.0), head=(-12.0, 0.0, -10.0),
                 grip=(-0.34, -0.22, 0.80), blade=_n((-0.55, -0.75, -0.36)), edge=_n((0.81, -0.37, -0.47)), elbow_r=(-0.9, 0.4, -0.2))
    HOLD = dict(FLICK, grip=(-0.33, -0.23, 0.81), head=(-12.0, 0.0, -14.0))
    keys = [Key(0, LOOK0), Key(38, LOOK1, "sine"), Key(48, TURN, "inout"), Key(58, dict(TURN, blade=_n((0.40, -0.80, 0.45))), "sine"),
            Key(70, LOW, "inout"), Key(73, dict(LOW, grip=(-0.04, -0.33, 1.10), blade=_n((0.40, -0.45, 0.80))), "out"),
            Key(77, FLICK, "in"), Key(79, dict(FLICK, grip=(-0.35, -0.22, 0.79)), "out"), Key(92, HOLD, "sine"),
            # vuelve por el mismo camino de la ida (la hoja arriba como en LOW y después girada como en TURN), con la izquierda
            # todavía en la cadera; recién después la mano va a la hoja (de la sacudida directo a mirar el filo, el antebrazo
            # de la espada cambiaba de rama: 116° en un cuadro)
            Key(100, dict(LOW, head=(-10.0, 0.0, 8.0)), "inout"),
            Key(107, dict(TURN, hand_l=_along(gU, bU, 0.05, (0.0, 0.06, 0.05)), hand_l_dir=bU, hand_l_palm=(0.0, 0.0, -1.0)), "inout"),
            Key(114, LOOK0, "inout"), Key(n, LOOK0, "sine")]
    return T.TeamClip("IdleInspect", n, keys, loop=True, feet=N.PLANTED, tremble=0.0,
                      notes="mira el filo, pasa los dedos por el lomo, la gira y la sacude",
                      timing=dict(ambient="inspect", read=[0, 40, 78], sheet=[0, 20, 38, 48, 58, 70, 74, 77, 79, 92, 100, 107, 114]))


def ninja_clips(ch, N):
    return [meditate(N), ambient_alert(N)] + spar(N) + [inspect(N)]


# ============================================================================================ sumo
# sentado en el piso: la cadera SLEEP_BACK m detrás del transform (al levantarse queda parado en su lugar, sobre los pies)
SLEEP_BACK = 0.30
SLEEP_SNORE = 52             # cuadro del ronquido (exhala): EnemyAmbient suelta un humito en la boca
SHIKO_STOMPS = (47, 122)     # cuadros de los pisotones de IdleShiko: polvo y un golpe sordo


def _sleep_pose(S, br=0.0):
    """Sentado en el piso con las piernas abiertas adelante (las rodillas apenas dobladas, los pies de talón y con las
    puntas afuera), la espalda un poco atrás, la panza adelante con las dos manos encima y la cabeza caída de costado.
    'br' 0..1 respira: la panza sube, los hombros suben y la cabeza se levanta un poco."""
    # la cabeza caída adelante y de costado (los ojos no se cierran: el sueño se lee en la postura), la espalda echada
    # atrás para que la panza quede arriba, y las manos encima de la panza con los dedos hacia el ombligo
    # (la respiración tiene que moverse 3-4 px en la cámara del juego: el pecho sube 2.5 cm y la cabeza 14°)
    return S.P(hips=(0.0, SLEEP_BACK, -0.37 + 0.025 * br), hips_rot=(-18.0 - 6.0 * br, 0.0, 0.0), spine=(4.0 - 5.0 * br, 0.0, 0.0),
               head=(44.0 - 14.0 * br, 26.0 - 6.0 * br, 10.0), clav_r=(0.0, 0.0, 6.0 * br), clav_l=(0.0, 0.0, -6.0 * br), breath=br,
               knee_r=(-0.5, -0.4, 1.0), knee_l=(0.5, -0.4, 1.0),
               # (la panza sentada sobresale hasta y -0.16 entre 0.60 y 0.85 m: ahí van las manos, sobre lo más alto de ella)
               hand_r=(-0.20, -0.25 - 0.015 * br, 0.90 + 0.02 * br), hand_r_dir=(0.7, -0.1, -0.7), hand_r_palm=(0.0, 0.9, 0.35),
               elbow_r=(-1.0, 0.5, -0.2),
               hand_l=(0.22, -0.24 - 0.015 * br, 0.88 + 0.02 * br), hand_l_dir=(-0.7, -0.1, -0.7), hand_l_palm=(0.0, 0.9, 0.35),
               elbow_l=(1.0, 0.5, -0.2), fist_r=0.35, fist_l=0.35, auto_drop=0.0)


def _sleep_feet(S, f):
    return (S.FR(f, 0.36, dx=-0.10, yaw=-40.0, pitch=-30.0), S.FL(f, 0.34, dx=0.10, yaw=42.0, pitch=-28.0))


def sleep(S):
    """4 s: inhala en 1.6 s (la panza y los hombros suben, la cabeza se levanta) y exhala lento en 2.4 s con el
    ronquido al principio de la exhalación."""
    n = 120
    keys = [Key(0, _sleep_pose(S, 0.0)), Key(36, _sleep_pose(S, 0.85), "inout"), Key(48, _sleep_pose(S, 1.0), "out"),
            Key(56, _sleep_pose(S, 0.8), "in"), Key(n, _sleep_pose(S, 0.0), "sine")]
    fr, fl = _sleep_feet(S, 0)
    return T.TeamClip("IdleSleep", n, keys, loop=True, feet={"r": [fr], "l": [fl]}, tremble=0.0,
                      notes="duerme sentado con las manos en la panza; ronca al exhalar",
                      timing=dict(ambient="sleep", snore=SLEEP_SNORE, seat_back=SLEEP_BACK))


def sumo_alert(S):
    """El despertar (2.4 s, más lento que el del ninja: justo y legible): resopla y levanta la cabeza (f5), mira a la
    izquierda y a la derecha medio dormido (f10-f28), ve a Kaito y se echa atrás con las manos arriba (f32), recoge los
    pies y se inclina adelante (f42), se para empujando con las manos en las rodillas (f48-f55), se palmea los muslos con
    un pisotón (f61) y queda en la guardia (= cuadro 0 de Idle). EnemyAmbient no lo deja girar hasta que se para
    ('land')."""
    n = 72
    I0 = S.idle().keys[0].ctrl
    Z = _sleep_pose(S, 0.0)
    SNORT = dict(Z, hips=(0.0, SLEEP_BACK, -0.36), head=(-6.0, 0.0, 0.0), spine=(2.0, 0.0, 0.0), clav_r=(0.0, 0.0, 6.0), clav_l=(0.0, 0.0, -6.0))
    LOOK_L = dict(SNORT, head=(4.0, 0.0, 50.0), spine=(4.0, 0.0, 12.0))
    LOOK_R = dict(SNORT, head=(2.0, 0.0, -46.0), spine=(4.0, 0.0, -12.0))
    SEE = dict(Z, hips=(0.0, SLEEP_BACK + 0.02, -0.34), hips_rot=(-20.0, 0.0, 0.0), spine=(-6.0, 0.0, 0.0), head=(-14.0, 0.0, 0.0),
               hand_r=(-0.55, -0.40, 1.20), hand_r_dir=(-0.2, -0.3, 0.93), hand_r_palm=(0.0, -1.0, 0.0), elbow_r=(-1.0, 0.2, -0.4),
               hand_l=(0.55, -0.40, 1.20), hand_l_dir=(0.2, -0.3, 0.93), hand_l_palm=(0.0, -1.0, 0.0), elbow_l=(1.0, 0.2, -0.4),
               fist_r=0.0, fist_l=0.0, clav_r=(0.0, 0.0, 8.0), clav_l=(0.0, 0.0, -8.0))
    # recoge los pies y carga el peso adelante, las manos a las rodillas
    GATHER = S.P(hips=(0.0, SLEEP_BACK - 0.05, -0.37), hips_rot=(18.0, 0.0, 0.0), spine=(16.0, 0.0, 0.0), head=(-24.0, 0.0, 0.0),
                 knee_r=(-0.8, -0.6, 0.3), knee_l=(0.8, -0.6, 0.3),
                 hand_r=(-0.46, -0.30, 0.62), hand_r_dir=(0.0, -0.4, -0.9), hand_r_palm=(0.0, 1.0, 0.0), elbow_r=(-1.0, 0.3, 0.2),
                 hand_l=(0.46, -0.30, 0.62), hand_l_dir=(0.0, -0.4, -0.9), hand_l_palm=(0.0, 1.0, 0.0), elbow_l=(1.0, 0.3, 0.2),
                 fist_r=0.2, fist_l=0.2, auto_drop=0.0)
    PUSH = dict(GATHER, hips=(0.0, 0.10, -0.32), hips_rot=(26.0, 0.0, 0.0), spine=(20.0, 0.0, 0.0), head=(-30.0, 0.0, 0.0),
                hand_r=(-0.48, -0.32, 0.70), hand_l=(0.48, -0.32, 0.70), auto_drop=1.0)
    STAND = S.P(hips=(0.0, 0.03, -0.16), hips_rot=(12.0, 0.0, 0.0), spine=(10.0, 0.0, 0.0), head=(-18.0, 0.0, 0.0),
                hand_r=(-0.56, -0.30, 0.92), hand_r_dir=(0.0, -0.3, -0.95), hand_r_palm=(0.0, 1.0, 0.0),
                hand_l=(0.56, -0.30, 0.92), hand_l_dir=(0.0, -0.3, -0.95), hand_l_palm=(0.0, 1.0, 0.0), fist_r=0.0, fist_l=0.0)
    SLAP = S.P(hips=(0.0, 0.02, -0.18), hips_rot=(14.0, 0.0, 0.0), spine=(10.0, 0.0, 0.0), head=(-18.0, 0.0, 0.0),
               hand_r=(-0.50, -0.30, 0.78), hand_r_dir=(0.0, -0.3, -0.95), hand_r_palm=(0.0, 1.0, 0.0),
               hand_l=(0.50, -0.30, 0.78), hand_l_dir=(0.0, -0.3, -0.95), hand_l_palm=(0.0, 1.0, 0.0), fist_r=0.0, fist_l=0.0)
    keys = [Key(0, Z), Key(5, SNORT, "snap"), Key(9, dict(SNORT, head=(6.0, 4.0, 4.0)), "out"), Key(17, LOOK_L, "inout"),
            Key(26, LOOK_R, "inout"), Key(32, SEE, "snap"), Key(35, dict(SEE, hand_r=(-0.56, -0.42, 1.24), hand_l=(0.56, -0.42, 1.24)), "out"),
            Key(42, GATHER, "inout"), Key(48, PUSH, "in"), Key(55, STAND, "out"),
            Key(59, dict(STAND, hand_r=(-0.62, -0.30, 1.05), hand_l=(0.62, -0.30, 1.05)), "inout"),
            Key(61, SLAP, "expo_in"), Key(63, dict(SLAP, hips=(0.0, 0.02, -0.16)), "out"), Key(n, I0, "sine")]
    fr, fl = _sleep_feet(S, 0)
    feet = {"r": [fr, S.FR(34, 0.36, dx=-0.10, yaw=-40.0, pitch=-30.0), S.FR(41, 0.12, dx=-0.04, yaw=-28.0, pitch=0.0, lift=0.06),
                  S.FR(58, 0.12, dx=-0.04, yaw=-28.0), S.FR(61, ease="expo_in", lift=0.06), S.FR(n)],
            "l": [fl, S.FL(35, 0.34, dx=0.10, yaw=42.0, pitch=-28.0), S.FL(43, 0.10, dx=0.04, yaw=28.0, pitch=0.0, lift=0.06),
                  S.FL(56, 0.10, dx=0.04, yaw=28.0), S.FL(60, lift=0.04), S.FL(n)]}
    return T.TeamClip("AmbientAlert", n, keys, feet=feet, tremble=0.0,
                      notes="se despierta, mira alrededor, ve a Kaito, se levanta y se palmea los muslos",
                      timing=dict(ambient="alert_sleep", land=55, sheet=[0, 5, 17, 26, 32, 38, 42, 48, 55, 61, n],
                                  chain=[(n, "Idle", 0, 0.03)], slide_ok=3.0))


def shiko(S):
    """5 s, los dos lados: en cuclillas abiertas con las manos en los muslos, pasa el peso a un pie, sube la otra pierna
    abierta al costado y la sostiene, la baja de golpe y se hunde en cuclillas; después el otro lado. Más lento y más
    hondo que el shiko del ataque (Attack3), y sin aviso: es el ejercicio."""
    n, h = 150, 75
    st = SHIKO_STOMPS[0]
    KOSHI = S.P(hips=(0.0, 0.02, -0.20), hips_rot=(10.0, 0.0, 0.0), spine=(8.0, 0.0, 0.0), head=(-14.0, 0.0, 0.0),
                knee_r=(-1.0, -0.4, 0.0), knee_l=(1.0, -0.4, 0.0),
                hand_r=(-0.56, -0.34, 0.80), hand_r_dir=(0.0, -0.3, -0.95), hand_r_palm=(0.0, 1.0, 0.0), elbow_r=(-1.0, 0.0, 0.3),
                hand_l=(0.56, -0.34, 0.80), hand_l_dir=(0.0, -0.3, -0.95), hand_l_palm=(0.0, 1.0, 0.0), elbow_l=(1.0, 0.0, 0.3),
                fist_r=0.3, fist_l=0.3)
    SHIFT = dict(KOSHI, hips=(0.16, 0.02, -0.14), hips_rot=(4.0, 8.0, 0.0), spine=(4.0, 6.0, 0.0), head=(-10.0, -6.0, 0.0),
                 hand_l=(0.56, -0.32, 0.90))
    # la pierna arriba: la cadera se inclina hacia el pie de apoyo (24°) y el pecho la compensa, así el pie sube a 0.7 m y
    # sale del contorno (con las piernas cortas del sumo, sin inclinar la cadera no pasaba de la rodilla del otro lado)
    UP = dict(KOSHI, hips=(0.22, 0.04, -0.04), hips_rot=(2.0, 24.0, 0.0), spine=(6.0, -16.0, 0.0), head=(-10.0, -10.0, 0.0),
              knee_r=(-1.0, -0.3, 0.6),
              hand_r=(-0.62, -0.25, 1.30), hand_r_dir=(-0.2, -0.4, -0.9), hand_r_palm=(0.0, 1.0, 0.0), elbow_r=(-1.0, 0.3, 0.2),
              hand_l=(0.62, -0.30, 0.92), hand_l_dir=(0.1, -0.5, -0.85), hand_l_palm=(0.0, 1.0, 0.0), elbow_l=(1.0, 0.2, 0.2))
    HOLD = dict(UP, hips=(0.23, 0.04, -0.03), hips_rot=(2.0, 26.0, 0.0))
    STOMP = dict(KOSHI, hips=(0.0, 0.0, -0.32), hips_rot=(16.0, 0.0, 0.0), spine=(12.0, 0.0, 0.0), head=(-18.0, 0.0, 0.0),
                 hand_r=(-0.60, -0.40, 0.72), hand_l=(0.60, -0.40, 0.72))
    SINK = dict(STOMP, hips=(0.0, 0.0, -0.28))
    BREATHE = dict(KOSHI, hips=(0.0, 0.02, -0.24), breath=1.0)
    half = [Key(0, KOSHI), Key(12, SHIFT, "inout"), Key(28, UP, "out"), Key(36, HOLD, "sine"), Key(44, dict(UP, hips=(0.22, 0.04, -0.045)), "sine"),
            Key(st, STOMP, "expo_in"), Key(50, SINK, "out"), Key(54, STOMP, "sine"), Key(64, BREATHE, "inout"), Key(h, KOSHI, "sine")]
    feet_r = [S.FR(0), S.FR(12), S.FR(28, dx=-0.20, yaw=-35.0, z=0.66, roll=-32.0, ease="out"),
              S.FR(36, dx=-0.22, yaw=-35.0, z=0.70, roll=-35.0, ease="sine"), S.FR(44, dx=-0.21, yaw=-35.0, z=0.68, roll=-34.0, ease="sine"),
              S.FR(st, ease="expo_in", lift=0.0), S.FR(h)]
    feet_l = [S.FL(0), S.FL(h)]
    keys = list(half) + [Key(k.frame + h, S.mirror(k.ctrl), k.ease) for k in half if k.frame > 0]

    def mfoot(fk, off):
        return T.FootKey(fk.frame + off, -fk.x, fk.y, -fk.yaw, fk.pitch, fk.z, -fk.roll, fk.ease, fk.lift)
    # la segunda mitad es la primera espejada: el pie izquierdo hace lo que hizo el derecho
    feet = {"r": feet_r + [mfoot(fk, h) for fk in feet_l if fk.frame > 0],
            "l": feet_l + [mfoot(fk, h) for fk in feet_r if fk.frame > 0]}
    return T.TeamClip("IdleShiko", n, keys, loop=True, feet=feet, tremble=0.0,
                      notes="shiko de los dos lados: sube la pierna al costado, la sostiene, pisa y se hunde",
                      timing=dict(ambient="shiko", stomps=list(SHIKO_STOMPS), sheet=[0, 12, 28, 40, 47, 54, 64, 75, 103, 115, 122, 139]))


def sumo_clips(ch, S):
    return [sleep(S), sumo_alert(S), shiko(S)]
