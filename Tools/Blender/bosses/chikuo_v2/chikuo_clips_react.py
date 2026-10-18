"""Los huecos y las reacciones del Chikuō ermitaño (diseño chikuo_v2, 16.3 y 16.5): el revolcón (volando, cayendo,
mareado sentado), el estampado contra otra caña, la caída del cielo, el resbalón, el tropiezo, el bastón cortado, el kip-up,
el desafinado y el afinado, el bastón clavado, los golpes y los parries. Es un viejo que se ríe de sí mismo: cae como un
muñeco de trapo, se marea con los ojos entrecerrados y se levanta de un salto.

Espacios: los de piso en 'ground'; volando ('air') el código lleva la raíz (FlungAir, Splat y SlideDown con la otra caña
detrás de él en x = 0, y = +0.30, MissGrab y Slip hasta tocar el piso a la altura de la raíz).

En los huecos la flauta va en el puño derecho: se ubica en el mundo o pegada al pecho (vuela con el tronco) y la mano la
agarra con el plan de agarres; llevada por la mano (staff_hand) seguía el giro del antebrazo y daba vueltas.
"""
import math
import chikuo_rig as CR
from chikuo_anim import CClip, merge, free, grip, legs, staff_world, staff_spine
from chikuo_clips import K, READY, AIR, AIR_STAFF, feet_track, rolled, READY_R, READY_L, ANKLE_Z
from chikuo_clips_ground import staff_at, unit, E, plants, FLUTE, BALANCE, POLE_BASE
from chikuo_clips_perch import FACE_EFFORT

DIZZY = dict(jaw=6.0, lids=0.55, brows=10.0, cheeks=0.0, corners=(0.004, -0.002))
OUCH = dict(jaw=9.0, lids=0.85, brows=-10.0, cheeks=0.2, corners=(-0.004, -0.006))
SQUASH = dict(jaw=12.0, lids=0.9, brows=-14.0, cheeks=0.6, corners=(-0.006, -0.008))


def held_r(pos, sdir, elbow=(-1, 0.4, -0.3), chest=True, at=0.95, up=(0, -1, 0.3)):
    """La flauta en el puño derecho: el punto de la flauta que agarra (a 'at' de la punta de abajo) en pos y la flauta hacia
    sdir, pegada al pecho (chest: vuela con el tronco) o en el mundo; la mano la agarra con el plan."""
    d = unit(sdir)
    bottom = tuple(p - x * at for p, x in zip(pos, d))
    st = staff_spine(bottom, d, up) if chest else staff_world(bottom, d, up)
    return merge(st, grip("r", at, elbow=elbow))


def sit_legs(spread=0.0):
    """Las piernas estiradas adelante con los talones apoyados (las puntas arriba)."""
    ar, _r, _t = rolled("r", -0.30 - spread, -0.82, -20.0, -40.0, "heel")
    al, _l, _u = rolled("l", 0.32 + spread, -0.78, 20.0, -40.0, "heel")
    return legs(ar, al, rr=(-40, 0, -20), rl=(-40, 0, 20), kr=(-0.5, -0.5, 1.0), kl=(0.5, -0.5, 1.0))


# ============================================================================ las poses de los huecos
# sentado en el piso mareado: la cadera apoyada, las piernas estiradas adelante con las rodillas apenas arriba, el tronco
# vencido hacia adelante, la flauta cruzada sobre los muslos en el puño derecho (los dedos por encima, el dorso adelante),
# la izquierda en la rodilla
DAZED_SIT = merge(dict(hips=(0.0, 0.06, 0.31 - 1.06), hips_rot=(-24, 0, 0), spine=(14, 0, 0), spine1=(12, 0, 0), spine2=(10, 0, 0),
                       neck=(6, 0, 0), head=(4, 0, 0), face=DIZZY),
                  sit_legs(),
                  held_r((-0.34, -0.58, 0.58), (1.0, 0.02, 0.03), elbow=(-1, 0.3, -0.4), chest=False),
                  free("l", (0.30, -0.56, 0.62), elbow=(1, 0.3, -0.4), fing="relaxed"))
# de espaldas en el piso pataleando como una tortuga: la cabeza levantada, la flauta en el puño derecho a lo largo del
# cuerpo apoyada en el piso (los dedos hacia el piso, el dorso afuera), la izquierda revoleándose sobre el pecho
DAZED_LIE = merge(dict(hips=(0.0, 0.10, 0.32 - 1.06), hips_rot=(-86, 0, 0), spine=(6, 0, 0), spine1=(4, 0, 0), spine2=(4, 0, 0),
                       neck=(18, 0, 0), head=(22, 0, 0), face=DIZZY),
                  legs((-0.20, -0.66, 0.50), (0.20, -0.56, 0.74), rr=(-20, 0, -10), rl=(-20, 0, 10), kr=(-0.3, -0.3, 1.0), kl=(0.3, -0.3, 1.0)),
                  held_r((-0.40, 0.30, 0.12), (0.05, -1.0, 0.0), elbow=(-1, 0.3, 0.3), chest=False, at=0.60, up=(0, 0, 1)),
                  # el meñique hacia la misma punta que en el salto: MissGrab llega acá sin soltar la flauta
                  dict(grip_r_side=1.0),
                  free("l", (0.40, 0.55, 0.82), elbow=(1, 0.3, -0.3), fing="open"))
# dando vueltas en el aire: abierto como una estrella, la flauta en el puño derecho
FLUNG = merge(dict(hips=(0.0, 0.0, 0.0), hips_rot=(0, 0, 0), spine=(-6, 0, 0), spine1=(-4, 0, 0), spine2=(-4, 0, 0), neck=(-8, 0, 0),
                   head=(-12, 0, 0), face="surprise"),
              legs((-0.26, -0.20, 0.26), (0.24, 0.12, 0.18), rr=(-30, 0, -10), rl=(-20, 0, 10), kr=(-0.4, -1, 0.3), kl=(0.4, -1, 0.3),
                   hips=True),
              held_r((-0.78, 0.0, 1.70), (-0.2, 0.3, 0.93), elbow=(-0.5, 0.5, -0.5)),
              free("l", (0.78, 0.0, 1.70), elbow=(0.5, 0.5, -0.5), fing="open", chest=True))


def flung_air():
    """El revolcón en el aire: da vueltas para atrás abierto como una estrella con la flauta en la mano, los cascabeles en
    estela. Loop de 12 (una vuelta)."""
    keys = [K(0, FLUNG), K(6, FLUNG, legs((-0.22, -0.10, 0.36), (0.26, 0.20, 0.12), rr=(-30, 0, -10), rl=(-20, 0, 10),
                                         kr=(-0.4, -1, 0.3), kl=(0.4, -1, 0.3), hips=True),
                                    free("l", (0.74, 0.20, 1.80), elbow=(0.5, 0.5, -0.5), fing="open", chest=True), ease="sine"),
            K(12, FLUNG, ease="sine")]
    # la vuelta cuadro a cuadro (con claves cada cuadro el giro va parejo y no pasa por la costura del loop)
    spin = [K(f, hips_rot=(-30.0 * f, 0, 0), ease="lin") for f in range(13)]
    return CClip("FlungAir", 12, keys, tracks=[spin], loop=True, lag={"head": 1.0},
                 spring_vel=lambda f: (0.0, 0.12 * f, 0.0),
                 timing=dict(space="air", chain_from="FLUNG", chain_to="FLUNG", hang_scale=0.0),
                 notes="el revolcón volando (loop de una vuelta para atrás); el código lleva la raíz por el arco")


def flung_land():
    """Toca el piso: cae de cola, rebota con las piernas para arriba y queda sentado mareado (sigue DazedSit)."""
    # cae de cola con las piernas arriba (viene dando vueltas para atrás): la flauta alzada al costado en la derecha, fuera
    # de las piernas que suben (cruzada sobre los muslos la atravesaban)
    hit = merge(DAZED_SIT, dict(hips=(0.0, 0.10, 0.26 - 1.06), hips_rot=(-40, 0, 0), spine=(20, 0, 0), spine1=(16, 0, 0),
                                spine2=(12, 0, 0), head=(16, 0, 0), face=OUCH),
                legs((-0.30, -0.60, 0.60), (0.30, -0.50, 0.70), rr=(-20, 0, -20), rl=(-20, 0, 20), kr=(-0.5, -0.5, 1.0), kl=(0.5, -0.5, 1.0)),
                held_r((-0.62, -0.28, 0.80), (0.55, -0.45, 0.70), elbow=(-1, 0.3, -0.4), chest=False),
                free("l", (0.58, -0.08, 0.62), elbow=(1, 0.3, -0.4), fing="open"))
    # el primer cuadro: la vuelta del revolcón con la cola a medio metro del piso (el código ya puso la raíz en el piso)
    # y las rodillas recogidas adelante, en el marco de la cadera como en el vuelo
    keys = [
        K(0, FLUNG, dict(hips=(0.0, 0.04, -0.48), hips_rot=(-48, 0, 0)),
          legs((-0.24, -0.42, 0.42), (0.24, -0.36, 0.50), rr=(8, 0, -10), rl=(10, 0, 10), kr=(-0.4, -1, 0.3), kl=(0.4, -1, 0.3),
               hips=True)),
        K(3, hit, ease="lin"),
        K(6, hit, dict(hips=(0.0, 0.08, 0.38 - 1.06), hips_rot=(-30, 0, 0)), ease="out"),
        K(9, DAZED_SIT, dict(hips=(0.0, 0.06, 0.26 - 1.06)), ease="in"),
        K(11, DAZED_SIT, ease="out"),
    ]
    return CClip("FlungLand", 11, keys, lag={"head": 1.0},
                 timing=dict(space="ground", chain_from="FLUNG", chain_to="DAZED_SIT", fade_from=0.06, hang_scale=0.5),
                 notes="toca el piso de cola y rebota hasta quedar sentado (sigue DazedSit)")


def dazed_sit():
    """Sentado y mareado: la cabeza da una vuelta grande y floja (20°; las hojas que le giran encima son del código), el
    tronco la sigue tarde hamacándose, cabecea como dormido y se despierta de un respingo; parpadea con los ojos
    entrecerrados. Loop de 30 (con 10° y sin el cabeceo se veía como una foto: es el hueco donde más se lo mira)."""
    hd = [(8, 0, 6), (14, 16, 20), (-8, 10, 6), (24, 0, 0), (-10, 0, -4), (4, -16, -20)]
    keys = [K(0, DAZED_SIT, dict(head=hd[0], neck=(6, 0, 2), spine2=(10, 0, 2)))]
    for f, h, ease in ((6, hd[1], "sine"), (12, hd[2], "sine"), (18, hd[3], "in"), (20, hd[4], "snap"), (25, hd[5], "sine")):
        keys.append(K(f, DAZED_SIT, dict(head=h, neck=(4 + h[0] * 0.3, 0, h[2] * 0.4), spine2=(10 + h[0] * 0.15, 0, h[2] * 0.4)),
                      ease=ease))
    keys.append(K(30, DAZED_SIT, dict(head=hd[0], neck=(6, 0, 2), spine2=(10, 0, 2)), ease="sine"))
    blink = [K(0, wink_r=0.0, wink_l=0.0), K(12, wink_r=0.0, wink_l=0.0), K(15, wink_r=1.0, wink_l=1.0),
             K(19, wink_r=0.0, wink_l=0.0), K(30, wink_r=0.0, wink_l=0.0)]
    return CClip("DazedSit", 30, keys, tracks=[blink], loop=True, lag={"spine2": 2.0, "neck": 1.0},
                 timing=dict(space="ground", open=[0, 30], chain_from="DAZED_SIT", chain_to="DAZED_SIT"),
                 notes="sentado mareado (revolcón, estampado, resbalón, tropiezo; Exhausted lo usa de alias); loop")


def dazed_sit_hit():
    """El sacudón de cada corte sentado: los hombros se encogen, la cabeza salta atrás, los cascabeles suenan."""
    rest = dict(head=(8, 0, 6), neck=(6, 0, 2), spine2=(10, 0, 2))
    keys = [K(0, DAZED_SIT, rest),
            K(3, DAZED_SIT, dict(hips=(0.0, 0.10, 0.29 - 1.06), spine=(8, 0, 0), spine2=(4, 0, 4), neck=(-8, 0, 0), head=(-12, 0, 8),
                                 clav_r=(0, 0, 10), clav_l=(0, 0, -10), face=OUCH),
              held_r((-0.34, -0.52, 0.64), (1.0, 0.02, 0.05), elbow=(-1, 0.3, -0.4), chest=False),
              free("l", (0.30, -0.46, 0.70), elbow=(1, 0.3, -0.4), fing="open"), ease="out"),
            K(6, DAZED_SIT, dict(spine2=(14, 0, 0), head=(14, 0, -4), face=OUCH), ease="inout"),
            K(10, DAZED_SIT, rest, ease="inout")]
    return CClip("DazedSitHit", 10, keys, lag={"head": 1.0},
                 timing=dict(space="ground", open=[0, 10], chain_from="DAZED_SIT", chain_to="DAZED_SIT"),
                 notes="el sacudón de un corte sentado (ExhaustedHit lo usa de alias)")


def dazed_lie():
    """De espaldas pataleando como una tortuga dada vuelta, revoleando el brazo libre. Loop de 30."""
    kick = lambda a: legs((-0.20, -0.66 + 0.10 * a, 0.50 + 0.22 * a), (0.20, -0.56 - 0.10 * a, 0.74 - 0.22 * a), rr=(-20, 0, -10),
                          rl=(-20, 0, 10), kr=(-0.3, -0.3, 1.0), kl=(0.3, -0.3, 1.0))
    wave = lambda a: free("l", (0.40 + 0.10 * a, 0.55 - 0.10 * a, 0.74 + 0.06 * a), elbow=(1, 0.3, -0.3), fing="open" if a >= 0 else "claw")
    keys = [K(0, DAZED_LIE, kick(0.0), wave(0.0)),
            K(4, DAZED_LIE, kick(1.0), wave(1.0), dict(head=(18, 0, 8)), ease="sine"),
            K(11, DAZED_LIE, kick(-1.0), wave(-1.0), dict(head=(24, 0, -6)), ease="sine"),
            K(18, DAZED_LIE, kick(1.0), wave(1.0), dict(head=(18, 0, 6)), ease="sine"),
            K(25, DAZED_LIE, kick(-1.0), wave(-1.0), dict(head=(24, 0, -4)), ease="sine"),
            K(30, DAZED_LIE, kick(0.0), wave(0.0), ease="sine")]
    return CClip("DazedLie", 30, keys, loop=True, lag={"head": 1.0},
                 timing=dict(space="ground", open=[0, 30], chain_from="DAZED_LIE", chain_to="DAZED_LIE"),
                 notes="de espaldas pataleando (la caída del cielo); loop")


def dazed_lie_hit():
    keys = [K(0, DAZED_LIE),
            K(3, DAZED_LIE, dict(hips=(0.0, 0.10, 0.21 - 1.06), spine2=(-6, 0, 0), neck=(6, 0, 0), head=(8, 0, 0), face=OUCH),
              legs((-0.24, -0.70, 0.70), (0.24, -0.60, 0.86), rr=(-20, 0, -10), rl=(-20, 0, 10), kr=(-0.3, -0.3, 1.0), kl=(0.3, -0.3, 1.0)),
              ease="out"),
            K(6, DAZED_LIE, dict(neck=(22, 0, 0), head=(26, 0, 0), face=OUCH), ease="inout"),
            K(10, DAZED_LIE, ease="inout")]
    return CClip("DazedLieHit", 10, keys, lag={"head": 1.0},
                 timing=dict(space="ground", open=[0, 10], chain_from="DAZED_LIE", chain_to="DAZED_LIE"),
                 notes="el sacudón de un corte de espaldas")


# ============================================================================ el estampado
CULM_Y = 0.30                                    # la otra caña detrás de él (Splat y SlideDown)
SPREAD = merge(dict(hips=(0.0, CULM_Y - 0.24, 0.0), hips_rot=(-4, 0, 0), spine=(-4, 0, 0), spine1=(-2, 0, 0), spine2=(-2, 0, 0),
                    neck=(-14, 0, 0), head=(-18, 0, 0), face=SQUASH),
               legs((-0.36, CULM_Y - 0.26, 0.20), (0.38, CULM_Y - 0.24, 0.24), rr=(-10, 0, -30), rl=(-10, 0, 30), kr=(-1, -0.4, 0.2),
                    kl=(1, -0.4, 0.2)),
               held_r((-0.74, CULM_Y - 0.22, 1.80), (-0.3, 0.0, 0.95), elbow=(-0.6, -0.4, -0.6), chest=False),
               free("l", (0.74, CULM_Y - 0.22, 1.82), elbow=(0.6, -0.4, -0.6), fing="open"))


def splat():
    """El estampado: vuela de espaldas contra la otra caña (Contact f2), queda pegado abierto como una estrella con la
    cara aplastada, rebota apenas y se queda pegado mareado (sigue SlideDown)."""
    keys = [K(0, FLUNG, dict(hips=(0.0, -0.10, 0.0), hips_rot=(10, 0, 0))),
            K(2, SPREAD, ease="in"),
            K(4, SPREAD, dict(hips=(0.0, CULM_Y - 0.30, 0.02), spine2=(6, 0, 0), head=(-4, 0, 0)), ease="out"),
            K(7, SPREAD, dict(face=DIZZY), ease="inout"),
            K(9, SPREAD, dict(face=DIZZY), ease="inout")]
    return CClip("Splat", 9, keys, lag={"head": 1.0},
                 spring_vel=lambda f: (0.0, 0.25 * min(f, 2), 0.0),
                 # el revolcón llega en cualquier punto de su vuelta: el código entra con un fundido corto
                 timing=dict(space="air", contact=2, chain_from="FLUNG", chain_to="SPLAT", culm_behind_m=CULM_Y, fade_from=0.06),
                 events=[E(2, "Contact")],
                 notes="se estrella de espaldas contra la otra caña (Contact f2): el código pone la raíz al pie del cuerpo con el "
                       "eje de esa caña 0.30 m detrás (y +0.30 en Blender)")


def slide_down():
    """Se desliza de espaldas por la caña (el código baja la raíz hasta el piso): los brazos arriba rozando el culmo, las
    piernas colgando, y cae sentado al pie (sigue DazedSit)."""
    slide = merge(SPREAD, dict(face=DIZZY, hips=(0.0, CULM_Y - 0.26, -0.04)),
                  held_r((-0.40, CULM_Y - 0.12, 2.00), (-0.2, 0.0, 0.98), elbow=(-0.8, -0.3, -0.4), chest=False),
                  free("l", (0.40, CULM_Y - 0.12, 2.02), elbow=(0.8, -0.3, -0.4), fing="open"),
                  legs((-0.16, CULM_Y - 0.40, 0.12), (0.18, CULM_Y - 0.36, 0.14), rr=(-40, 0, -10), rl=(-40, 0, 10), kr=(-0.3, -1, 0.2),
                       kl=(0.3, -1, 0.2)))
    keys = [K(0, SPREAD, dict(face=DIZZY)),
            K(4, slide, ease="inout"),
            K(10, slide, dict(hips=(0.0, CULM_Y - 0.28, -0.08)), ease="sine"),
            K(13, slide, dict(hips=(0.0, CULM_Y - 0.24, -0.06)), legs((-0.22, -0.30, 0.12), (0.24, -0.28, 0.14), rr=(-30, 0, -10),
                                                                      rl=(-30, 0, 10), kr=(-0.4, -1, 0.3), kl=(0.4, -1, 0.3)),
              held_r((-0.42, -0.24, 1.32), (1.0, 0.02, 0.30), elbow=(-1, 0.2, -0.4), chest=False),
              free("l", (0.42, -0.10, 1.40), elbow=(1, 0.2, -0.4), fing="open"), ease="lin"),
            K(16, DAZED_SIT, dict(hips=(0.0, 0.06, 0.22 - 1.06), face=OUCH), ease="in"),
            K(18, DAZED_SIT, ease="out")]
    return CClip("SlideDown", 18, keys, lag={"head": 1.0},
                 timing=dict(space="air", chain_from="SPLAT", chain_to="DAZED_SIT", culm_behind_m=CULM_Y, land=13),
                 notes="se desliza por la caña hasta sentarse al pie (el código baja la raíz hasta el piso en f13)")


# ============================================================================ la caída del cielo, el resbalón, el tropiezo
def miss_grab():
    """La caída del cielo: llega a la caña de destino con las dos manos estiradas, agarra aire (la cortaron), se da cuenta,
    revolea los brazos y cae de espaldas (el código lo baja: 0.45 s) hasta quedar tirado (sigue DazedLie)."""
    reach = merge(AIR, dict(hips=(0.0, -0.06, -0.24), hips_rot=(6, 0, 0), spine2=(6, 0, 0), head=(-12, 0, 0), face="grin"),
                  free("l", (0.22, -0.80, 1.92), (0.2, -0.9, 0.3), (0.9, 0.0, 0.3), elbow=(1, 0.3, -0.3), fing="open"))
    grab_air = merge(reach, dict(face="surprise"), free("l", (0.20, -0.76, 1.88), elbow=(1, 0.3, -0.3), fing="fist"))
    # manotea con la izquierda; la derecha sigue con la flauta alzada del salto (pasarla al puño mientras cae le giraba
    # la mano 135° en un cuadro) y la flauta baja con él hasta el piso
    flail = merge(FLUNG, AIR_STAFF, grip("r", 0.95, elbow=(-1, 0.4, -0.3)), dict(hips=(0.0, 0.10, -0.20), hips_rot=(-40, 0, 0), face="surprise"),
                  legs((-0.24, -0.30, 0.30), (0.24, -0.20, 0.20), rr=(-30, 0, -10), rl=(-20, 0, 10), kr=(-0.4, -1, 0.3), kl=(0.4, -1, 0.3),
                       hips=True))
    keys = [K(0, AIR),
            K(3, reach, ease="out"),
            K(5, grab_air),
            K(7, flail, dict(hips_rot=(-20, 0, 0)), ease="inout"),
            K(9, flail, dict(face=OUCH), ease="inout"),
            # cinco cuadros hasta quedar tirado: la flauta alzada baja al piso y el brazo gira 135° alrededor del hombro (en
            # tres, a más de 45° por cuadro, la flauta se atrasaba y llegaba de un salto en el último)
            K(14, DAZED_LIE, ease="inout")]
    return CClip("MissGrab", 14, keys, lag={"head": 1.0},
                 spring_vel=lambda f: (0.0, -0.05 * min(f, 5), 0.10 * max(0, f - 5)),
                 timing=dict(space="air", chain_from="AIR", chain_to="DAZED_LIE", land=14, hang_scale=0.5),
                 notes="la caña se le escapa de las manos y cae de espaldas (el código lo baja hasta el piso en f14); sigue "
                       "DazedLie")


def slip():
    """El resbalón: trepando, las manos se le escapan del culmo (que está adelante: y -0.35), cae para atrás revoleando
    los brazos, la derecha manotea la flauta de la espalda y queda sentado con ella (el código lo baja: 0.30 s); sigue
    DazedSit."""
    back = staff_spine((0.08, 0.22, 0.58), (0.04, -0.03, 1.0), (0, 1, 0))
    cling = merge(dict(hips=(0.0, 0.0, 0.0), hips_rot=(10, 0, 0), spine2=(4, 0, 0), head=(-20, 0, 0), face=FACE_EFFORT),
                  legs((-0.14, -0.20, 0.50), (0.16, -0.18, 0.32), rr=(-40, 0, -10), rl=(-30, 0, 10), kr=(-0.4, -1, 0.3), kl=(0.4, -1, 0.3)),
                  back, free("r", (-0.10, -0.26, 2.05), elbow=(-1, 0.3, -0.4), fing="grip_stalk"),
                  free("l", (0.10, -0.26, 1.75), elbow=(1, 0.3, -0.4), fing="grip_stalk"))
    keys = [K(0, cling),
            K(2, cling, free("r", (-0.10, -0.24, 1.80), elbow=(-1, 0.3, -0.4), fing="grip_stalk"),
              free("l", (0.10, -0.24, 1.50), elbow=(1, 0.3, -0.4), fing="grip_stalk"), dict(face="surprise", hips=(0.0, 0.02, -0.20))),
            # cae para atrás; la derecha va a la flauta de la espalda (la agarra en f6) y la saca
            K(4, cling, dict(hips=(0.0, 0.14, -0.26), hips_rot=(-20, 0, 0), spine2=(-6, 0, 0), head=(-8, 0, 0), face="surprise"),
              free("r", (-0.26, 0.12, 2.20), elbow=(-1, 0.3, -0.3), fing="open", chest=True),
              free("l", (0.70, -0.10, 1.70), elbow=(0.5, 0.5, -0.5), fing="open", chest=True), ease="out"),
            # el puño con el dorso pedido en la sacada (el plan lo daba vuelta 100° en un cuadro al pasar al mundo)
            K(5, back, grip("r", 1.95, dors=(0, 1, 0.2), elbow=(-1, 0.3, -0.3)), dict(hips=(0.0, 0.17, -0.32), hips_rot=(-26, 0, 0),
                                                                                    face="surprise"),
              free("l", (0.70, -0.10, 1.70), elbow=(0.5, 0.5, -0.5), fing="open", chest=True)),
            # la flauta sale de la espalda por arriba del hombro derecho, cruzada atrás (de la espalda directo adelante la mano
            # saltaba 80 cm en un cuadro y la flauta atravesaba la cara)
            K(6, staff_world((1.23, 0.92, 0.72), unit((-1.30, -0.35, 1.25)), (0, -1, 0)), grip("r", 1.95, dors=(0, 0.7, 0.7), elbow=(-1, 0.3, -0.3)),
              dict(hips=(0.0, 0.16, -0.42), hips_rot=(-27, 0, 0), spine=(4, 0, 0), spine2=(2, 0, 0), face="surprise"),
              free("l", (0.66, -0.20, 1.45), elbow=(0.5, 0.5, -0.5), fing="open"), ease="inout"),
            # horizontal adelante a la altura del pecho que cae antes de caer sentado: en tres cuadros desde la espalda (en dos
            # el brazo giraba 118° en uno) y al alcance (más alta faltaban 20 cm)
            K(8, staff_world((1.15, -0.48, 1.17), unit((-1.0, 0.05, 0.05)), (0, -0.3, 1)), grip("r", 1.60, dors=(0, 0, 1), elbow=(-1, 0.3, -0.3)),
              dict(hips=(0.0, 0.12, -0.60), hips_rot=(-26, 0, 0), spine=(8, 0, 0), spine2=(6, 0, 0), face="surprise"),
              free("l", (0.60, -0.30, 1.20), elbow=(0.5, 0.5, -0.5), fing="open"), ease="inout"),
            K(10, DAZED_SIT, dict(hips=(0.0, 0.08, 0.24 - 1.06), face=OUCH), ease="in"),
            K(12, DAZED_SIT, dict(hips=(0.0, 0.06, 0.32 - 1.06)), ease="out"),
            K(15, DAZED_SIT, ease="in")]
    return CClip("Slip", 15, keys, lag={"head": 1.0},
                 timing=dict(space="air", chain_to="DAZED_SIT", land=10, culm_front_m=0.35, hang_scale=0.5),
                 notes="resbala trepando y cae sentado (el código baja la raíz hasta el piso en f10); el culmo 0.35 m adelante")


def stumble():
    """El tropiezo: en el agachado de la vuelta el pie se le va, la rodilla derecha al piso, la izquierda se apoya en la
    rodilla y la flauta clavada de bastón; sacude la cabeza mareado y se levanta a la guardia (abierto 1.0 s)."""
    knee = merge(READY, dict(hips=(0.04, 0.10, -0.60), hips_rot=(18, 0, -10), spine=(12, 0, 4), spine1=(8, 0, 2), spine2=(8, 0, 0),
                             neck=(-6, 0, 0), head=(-4, 0, 0), face=DIZZY),
                 staff_world((-0.50, -0.40, 0.0), unit((0.05, 0.05, 1.0)), (0, -1, 0)), grip("r", 1.00, elbow=(-1, 0.3, -0.5)),
                 free("l", (0.36, -0.42, 0.74), elbow=(1, 0.3, -0.4), fing="relaxed"),
                 dict(knee_r=(-0.3, -1, -0.6)))
    keys = [K(0, READY, dict(hips=(0.0, 0.0, -0.46), hips_rot=(20, 0, -8), spine2=(12, 0, 0))),
            K(3, READY, dict(hips=(0.02, 0.06, -0.50), hips_rot=(10, 8, -8), face="surprise"),
              free("l", (0.66, -0.20, 1.40), elbow=(0.5, 0.5, -0.5), fing="open"), ease="out"),
            K(7, knee, ease="in"),
            K(10, knee, dict(head=(10, 0, 10)), ease="sine"),
            K(14, knee, dict(head=(10, 0, -10)), ease="sine"),
            K(18, knee, dict(head=(8, 0, 8)), ease="sine"),
            K(22, knee, dict(head=(4, 0, 0), face="grin"), ease="sine"),
            K(26, READY, dict(hips=(0.0, 0.04, -0.34), hips_rot=(14, 0, -14)), ease="inout"),
            K(30, READY, ease="inout")]
    r0, l0 = READY_R, READY_L
    # el pie derecho atrás de punta con los dedos doblados mientras la rodilla toca el piso
    plan = {"l": plants((0, 30, l0[0], l0[1], l0[2])),
            "r": plants((0, 2, r0[0], r0[1], r0[2]), (6, 23, -0.26, 0.50, -24.0, [(6, 62.0, "ball")]), (27, 30, r0[0], r0[1], r0[2]))}
    feet = feet_track(keys, 30, plan)
    return CClip("Stumble", 30, keys, tracks=[feet], lag={"head": 1.0},
                 timing=dict(space="ground", open=[0, 30], chain_from="READY", chain_to="READY", fade_from=0.08),
                 notes="el tropiezo: rodilla al piso, mareado; abierto 1.0 s")


def pole_fall():
    """Le cortaron el bastón con las campanas blancas: el bastón se vence hacia adelante con él arriba, revolea los brazos,
    el bastón lo tira como una catapulta, lo atrapa en el aire y sale volando dando vueltas (sigue FlungAir)."""
    def top(deg):
        r = math.radians(deg)
        return (0.0, POLE_BASE[1] - math.sin(r) * CR.STAFF_LEN, POLE_BASE[2] + math.cos(r) * CR.STAFF_LEN)

    def tilt(deg):
        r = math.radians(deg)
        return staff_world(POLE_BASE, (0.0, -math.sin(r), math.cos(r)), (0, -1, 0))

    def on_top(deg, hz, hy, rx, ar, al):
        t = top(deg)
        return merge(BALANCE, tilt(deg), dict(hips=(0.06, t[1] + hy, t[2] + hz - 1.06), hips_rot=(rx, 4, 0), face="surprise"),
                     legs((-0.02, t[1], t[2] + ANKLE_Z), (0.24, t[1] - 0.30, t[2] + 0.55), rr=(deg * 0.6, 0, -10), rl=(-40, 0, 10),
                          kr=(-0.2, -1, 0), kl=(0.3, -1, 0.4)),
                     free("r", ar, elbow=(-0.5, 0.5, -0.6), fing="open", chest=True),
                     free("l", al, elbow=(0.5, 0.5, -0.6), fing="open", chest=True))
    keys = [K(0, BALANCE),
            K(3, on_top(12.0, 0.92, -0.02, -6.0, (-0.66, -0.10, 2.10), (0.66, -0.20, 1.50)), ease="inout"),
            K(6, on_top(38.0, 0.82, 0.10, -30.0, (-0.62, 0.10, 1.50), (0.66, -0.30, 2.10)), ease="in"),
            # lo tira: la derecha manotea el bastón que se le escapa de abajo de los pies
            K(9, FLUNG, dict(hips=(0.0, -1.70, 1.60 - 1.06), hips_rot=(-80, 0, 0)), ease="out"),
            K(14, FLUNG, dict(hips=(0.0, -2.20, 1.90 - 1.06), hips_rot=(-150, 0, 0)), ease="lin")]
    return CClip("PoleFall", 14, keys, lag={"head": 1.0},
                 spring_vel=lambda f: (0.0, -0.10 * f, 0.0),
                 timing=dict(space="pole", chain_from="BALANCE", chain_to="FLUNG", fade_to=0.1, root_offset=["FlungAir", 0, 14],
                             hang_scale=0.0, staff_in_floor=0.13),
                 notes="el bastón cortado se vence y lo tira (el revolcón): sale volando dando vueltas con el bastón en la mano; "
                       "sigue FlungAir desde root_offset_m")


def get_up():
    """De un salto (kip-up, invulnerable): de espaldas se hamaca atrás con las rodillas al pecho, patea al cielo, arquea la
    espalda y cae parado agachado; a la guardia."""
    # se hamaca sobre los omóplatos: la cadera arriba (a 0.30 la espalda se metía 22 cm en el piso), la flauta sube con
    # la derecha al costado del cuerpo
    rock = merge(DAZED_LIE, dict(hips=(0.0, 0.22, 0.52 - 1.06), hips_rot=(-118, 0, 0), spine=(8, 0, 0), spine2=(6, 0, 0),
                                 neck=(24, 0, 0), head=(20, 0, 0), face="grin"),
                 legs((-0.16, 0.06, 0.96), (0.16, 0.06, 1.00), rr=(-60, 0, -10), rl=(-60, 0, 10), kr=(-0.3, 0.3, 1.0), kl=(0.3, 0.3, 1.0)),
                 held_r((-0.46, 0.24, 0.40), (-0.30, -0.20, 0.93), elbow=(-1, 0.3, 0.3), chest=False, at=0.30, up=(0, -1, 0)),
                 free("l", (0.36, 0.70, 0.30), elbow=(1, 0.3, 0.3), fing="open"))
    kip = merge(READY, dict(hips=(0.0, 0.10, 0.62 - 1.06), hips_rot=(-30, 0, 0), spine=(-14, 0, 0), spine1=(-10, 0, 0), spine2=(-8, 0, 0),
                            neck=(-10, 0, 0), head=(-14, 0, 0), face="laugh"),
                legs((-0.20, -0.40, 0.30), (0.20, -0.30, 0.40), rr=(-30, 0, -10), rl=(-30, 0, 10), kr=(-0.3, -1, 0.2), kl=(0.3, -1, 0.2)),
                held_r((-0.52, 0.10, 0.84), (0.05, -1.0, 0.1), elbow=(-1, 0.3, -0.3), chest=False, at=0.60, up=(0, 0, 1)),
                free("l", (0.56, 0.20, 0.86), elbow=(1, 0.3, -0.3), fing="open"))
    land = merge(READY, dict(hips=(0.0, 0.02, -0.46), hips_rot=(20, 0, -14), spine2=(10, 0, 0), face="grin"),
                 free("l", (0.30, -0.42, 1.10), elbow=(1, 0.2, -0.6), fing="open"))
    keys = [K(0, DAZED_LIE),
            K(3, rock, ease="inout"),
            K(6, kip, ease="lin"),
            K(9, land, ease="out"),
            K(12, READY, ease="inout")]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants({"free": (0, 7)}, (9, 12, r0[0], r0[1], r0[2])), "l": plants({"free": (0, 7)}, (9, 12, l0[0], l0[1], l0[2]))}
    feet = feet_track(keys, 12, plan)
    return CClip("GetUp", 12, keys, tracks=[feet], lag={"head": 1.0},
                 timing=dict(space="ground", air=[6, 9], chain_from="DAZED_LIE", chain_to="READY", invulnerable=[0, 12], fade_from=0.1,
                             hang_scale=0.0),
                 notes="kip-up de espaldas a la guardia (invulnerable; ExhaustedRise lo usa de alias)")


# ============================================================================ la flauta: desafinado y afinado
def detuned():
    """Desafinado: la flauta chilla (los ojos se le salen), la saca de la boca, tose hojas tres veces doblado con la
    izquierda en la boca, sacude la cabeza y vuelve a la guardia (abierto 1.4 s)."""
    # la flauta sale de la boca de costado (sigue en los labios unos cuadros, después en la derecha)
    off_lips = merge(FLUTE, dict(head=(-14, 0, 0), spine2=(-8, 0, 0), clav_r=(0, 0, 10), clav_l=(0, 0, -10), face="surprise"))
    away = merge(FLUTE, staff_at((-0.36, -0.42, 1.36), unit((0.85, -0.20, 0.45)), 0.70), grip("r", 0.70, elbow=(-1, 0.3, -0.6)),
                 free("l", (0.10, -0.26, 1.84), elbow=(1, 0.3, -0.6), fing="fist"))
    cough = lambda a: merge(away, dict(hips=(0.0, 0.06, -0.20), hips_rot=(14 + 6 * a, 0, -6), spine=(10 + 6 * a, 0, 0),
                                       spine1=(10 + 4 * a, 0, 0), spine2=(12 + 4 * a, 0, 0), neck=(4, 0, 0), head=(10 + 8 * a, 0, 0),
                                       face=OUCH if a else "surprise"))
    keys = [K(0, FLUTE),
            K(2, off_lips, ease="out"),
            K(4, merge(FLUTE, staff_at((-0.30, -0.50, 1.50), unit((0.90, -0.15, 0.40)), 0.70), grip("r", 0.70, elbow=(-1, 0.3, -0.6)),
                       free("l", (0.30, -0.40, 1.50), elbow=(1, 0.3, -0.6), fing="open"), dict(face="surprise")), ease="inout"),
            K(7, cough(0.0), ease="inout")]
    for f in (10, 18, 26):
        keys += [K(f, cough(1.0), ease="out"), K(f + 4, cough(0.2), ease="inout")]
    keys += [K(33, away, dict(head=(0, 0, 14), face=DIZZY), ease="sine"), K(36, away, dict(head=(0, 0, -14), face=DIZZY), ease="sine"),
             K(42, READY, ease="inout")]
    r0, l0 = READY_R, READY_L
    feet = feet_track(keys, 42, {"r": plants((0, 36, -0.22, 0.10, -16.0), (39, 42, r0[0], r0[1], r0[2])),
                                 "l": plants((0, 42, l0[0], l0[1], l0[2]))}, lift=0.06)
    return CClip("Detuned", 42, keys, tracks=[feet], lag={"head": 1.0},
                 timing=dict(space="ground", open=[0, 42], chain_from="FLUTE", chain_to="READY"),
                 notes="Desafinado (1.4 s abierto): la flauta chilla, tose hojas (el código las larga en f10, f18 y f26)")


def tuned():
    """Afinado: se le aflojaron las piernas, sentado con la flauta sobre los muslos aplaude despacio, sonriendo. Loop de
    36 (dos aplausos)."""
    sit = merge(DAZED_SIT, dict(hips_rot=(-16, 0, 0), spine=(6, 0, 0), spine1=(4, 0, 0), spine2=(2, 0, 0), neck=(-4, 0, 0),
                                head=(-6, 0, 0), face="grin"),
                staff_world((-1.00, -0.52, 0.50), (1.0, 0.04, 0.04), (0, -0.3, 1)))
    clap = lambda f, apart: K(f, sit, free("r", (-0.10 - 0.14 * apart, -0.50, 1.20 + 0.04 * apart), elbow=(-1, 0.2, -0.6), fing="relaxed"),
                              free("l", (0.10 + 0.14 * apart, -0.50, 1.20 + 0.04 * apart), elbow=(1, 0.2, -0.6), fing="relaxed"),
                              dict(head=(-6 + 4 * (1 - apart), 0, 0)), ease="sine")
    keys = [clap(0, 0.0), clap(9, 1.0), clap(18, 0.0), clap(27, 1.0), clap(36, 0.0)]
    return CClip("Tuned", 36, keys, loop=True, lag={"head": 1.0},
                 timing=dict(space="ground", open=[0, 36], chain_from="DAZED_SIT", chain_to="DAZED_SIT", fade_from=0.2),
                 notes="Afinado (2.5 s abierto): sentado aplaudiendo despacio; loop (aplausos en f0 y f18)")


def staff_stuck():
    """El Bastón Clavado: la flauta se le clavó en el piso en la barrida; tira de ella con las dos manos echado atrás y los
    pies afirmados, tres tirones; al tercero sale, trastabilla para atrás y vuelve a la guardia."""
    # el bastón clavado delante de él con la punta de arriba hacia su pecho, las dos manos a la altura del pecho con los
    # antebrazos casi horizontales: con las manos en la faja el antebrazo bajaba 45° y la muñeca se doblaba 62° hacia el
    # pulgar para seguir la flauta; con la flauta más cerca y la cadera atrás los brazos quedaban estirados y el codo,
    # sin plano, daba vuelta en cada tirón
    stuck = staff_world((0.04, -0.86, -0.12), unit((-0.04, 0.30, 0.95)), (0, -1, 0))
    pull = lambda a: merge(READY, stuck, grip("r", 1.32, elbow=(-1, 0.2, -0.7)), grip("l", 1.66, elbow=(1, 0.2, -0.7)),
                           dict(hips=(0.0, 0.02 + 0.03 * a, -0.30 - 0.05 * a), hips_rot=(-4 - 6 * a, 0, -10), spine=(2 - 4 * a, 0, 0),
                                spine2=(-2 - 4 * a, 0, 0), neck=(-4, 0, 0), head=(-6 - 8 * a, 0, 0), face=FACE_EFFORT if a else "surprise"))
    keys = [K(0, READY, travel=0.0), K(4, pull(0.0), travel=0.0, ease="inout")]
    for f in (8, 14):
        keys += [K(f, pull(1.0), travel=0.0, ease="in"), K(f + 3, pull(0.2), travel=0.0, ease="out")]
    # el tercer tirón la saca: la flauta sube por delante del pecho, él se va para atrás dos pasos y la deja caer entre
    # los puños hasta el vendado (la guardia)
    keys += [K(20, pull(1.0), travel=0.0, ease="in"),
             K(23, READY, staff_at((-0.06, -0.58, 1.30), unit((0.0, 0.10, 0.99)), 1.32), grip("r", 1.32, elbow=(-1, 0.2, -0.7)),
               grip("l", 1.66, elbow=(1, 0.2, -0.7)), dict(hips=(0.0, 0.14, -0.24), hips_rot=(-10, 0, -10), face="surprise"),
               travel=-0.20, ease="out"),
             # la deja correr entre los puños en dos tiempos (de golpe, el brazo derecho giraba 133° en un cuadro)
             K(25, READY, staff_at((-0.12, -0.50, 1.16), unit((0.10, -0.22, 0.97)), 1.00), grip("r", 1.00, elbow=(-1, 0.25, -0.65)),
               grip("l", 1.38, elbow=(1, 0.2, -0.7)), dict(hips=(0.0, 0.11, -0.23), hips_rot=(-6, 0, -12), face="surprise"),
               travel=-0.30, ease="inout"),
             K(27, READY, staff_at((-0.24, -0.48, 1.10), unit((0.20, -0.40, 0.89)), 0.70), grip("r", 0.70, elbow=(-1, 0.3, -0.6)),
               grip("l", 1.10, elbow=(1, 0.2, -0.7)), dict(hips=(0.0, 0.08, -0.22), hips_rot=(-2, 0, -14), face="grin"),
               travel=-0.40, ease="inout"),
             K(33, READY, travel=-0.40, ease="inout")]
    r0, l0 = READY_R, READY_L
    plan = {"r": plants((0, 21, r0[0], r0[1], r0[2]), (25, 33, r0[0], r0[1] + 0.40, r0[2])),
            "l": plants((0, 23, l0[0], l0[1], l0[2]), (27, 33, l0[0], l0[1] + 0.40, l0[2]))}
    feet = feet_track(keys, 33, plan)
    return CClip("StaffStuck", 33, keys, tracks=[feet], lag={"head": 1.0},
                 timing=dict(space="ground", open=[0, 33], chain_from="READY", chain_to="READY", fade_from=0.1, staff_in_floor=0.15),
                 notes="Bastón Clavado (1.1 s abierto): tres tirones y sale al tercero")


# ============================================================================ los golpes y los parries
def hit(name, frames, travel, big):
    """El golpe en el piso: la cabeza va atrás, el tronco se tuerce, un paso atrás (el avance del código) y se recompone
    sacudiendo la cabeza."""
    snap = merge(READY, dict(hips=(0.0, 0.10, -0.20), hips_rot=(-4 - 6 * big, 0, -14 - 10 * big), spine=(-6 * big, 0, 6),
                             spine2=(-8 - 6 * big, 0, 8), neck=(-8, 0, 6), head=(-14 - 6 * big, 0, 12), clav_r=(0, 0, 8),
                             clav_l=(0, 0, -8), face=OUCH),
                 staff_at((-0.30, 0.20, 1.20), unit((0.30, -0.70, 0.65)), 0.23), grip("r", 0.23, elbow=(-1, 0.4, -0.6)),
                 free("l", (0.50, -0.10, 1.40 + 0.20 * big), elbow=(0.6, 0.4, -0.5), fing="open"))
    keys = [K(0, READY, travel=0.0),
            K(3, snap, travel=travel * 0.6, ease="out"),
            K(5 + 2 * big, snap, dict(hips=(0.0, 0.14, -0.26)), travel=travel, ease="inout"),
            K(frames - 3, READY, dict(hips=(0.0, 0.02, -0.20), head=(-2, 0, 4)), guard_l(), travel=travel, ease="inout"),
            K(frames, READY, travel=travel, ease="inout")]
    r0, l0 = READY_R, READY_L
    t = -travel
    plan = {"l": plants((0, 1, l0[0], l0[1], l0[2]), (4 + 2 * big, frames, l0[0], l0[1] + t, l0[2])),
            "r": plants((0, 2 + big, r0[0], r0[1], r0[2]), (5 + 3 * big, frames, r0[0], r0[1] + t, r0[2]))}
    feet = feet_track(keys, frames, plan, lift=0.08)
    return CClip(name, frames, keys, tracks=[feet], lag={"head": 0.6},
                 timing=dict(space="ground", chain_from="READY", chain_to="READY", fade_from=0.06, hang_scale=0.6),
                 notes=f"golpe en el piso ({frames} cuadros): retrocede {-travel:.2f} m (travel_m)")


def guard_l():
    """La izquierda vuelve a la flauta de la guardia (la toma en el último cuadro)."""
    return free("l", (0.0, -0.40, 1.24), elbow=(1, 0.2, -0.8), fing="grip_stalk")


def parried(name, frames, travel, big):
    """El retroceso del parry: la flauta le rebota para arriba y atrás por encima del hombro derecho, el cuerpo se echa
    atrás y retrocede; el perfecto lo deja revoleando la izquierda y riéndose antes de recomponerse."""
    # la mano derecha queda adelante del hombro con el codo doblado, no pegada a él: con la muñeca a 20 cm del hombro el
    # codo podía ir a cualquier lado y daba vuelta en un cuadro
    up = merge(READY, staff_at((-0.40, 0.08, 1.48), unit((0.12, 0.40, 0.91)), 0.23), grip("r", 0.23, elbow=(-1, 0.0, -0.4)),
               free("l", (0.62, -0.20, 1.50 + 0.30 * big), elbow=(0.6, 0.5, -0.5), fing="open"),
               dict(hips=(0.0, 0.12, -0.16), hips_rot=(-10 - 6 * big, 0, -20), spine=(-6, 0, 4), spine2=(-8 - 4 * big, 0, 6),
                    neck=(-8, 0, 0), head=(-14, 0, 6), face="surprise"))
    mid = merge(READY, staff_at((-0.38, 0.06, 1.34), unit((0.30, -0.20, 0.93)), 0.23), grip("r", 0.23, elbow=(-1, 0.2, -0.5)),
                free("l", (0.50, -0.20, 1.40), elbow=(0.6, 0.4, -0.5), fing="open"), dict(hips=(0.0, 0.06, -0.18), neck=(0, 12, 0), head=(0, 12, 0), face="surprise"))  # la cabeza se aparta de la flauta que sube
    keys = [K(0, READY, travel=0.0),
            K(2, mid, travel=travel * 0.3, ease="out"),
            K(4, up, travel=travel * 0.7, ease="inout"),
            K(6 + 3 * big, up, dict(hips=(0.0, 0.16, -0.20)), travel=travel, ease="inout")]
    if big:
        keys += [K(12, up, dict(hips=(0.06, 0.12, -0.14), hips_rot=(-6, 6, -14), face="laugh"),
                   free("l", (0.76, -0.30, 1.86), elbow=(0.6, 0.5, -0.5), fing="claw"), travel=travel, ease="sine")]
    keys += [K(frames - 3, READY, dict(hips=(0.0, 0.02, -0.20)), guard_l(), travel=travel, ease="inout"),
             K(frames, READY, travel=travel, ease="inout")]
    r0, l0 = READY_R, READY_L
    t = -travel
    plan = {"l": plants((0, 1, l0[0], l0[1], l0[2]), (4, frames, l0[0], l0[1] + t, l0[2])),
            "r": plants((0, 2, r0[0], r0[1], r0[2]), (5 + big, frames, r0[0], r0[1] + t, r0[2]))}
    feet = feet_track(keys, frames, plan, lift=0.08)
    return CClip(name, frames, keys, tracks=[feet], lag={"head": 0.6},
                 timing=dict(space="ground", open=[0, frames], chain_from="READY", chain_to="READY", fade_from=0.06, hang_scale=0.6),
                 notes=f"el retroceso del parry ({frames / 30.0:.2f} s): retrocede {-travel:.2f} m (travel_m)")


def clips(kit):
    return [flung_air(), flung_land(), dazed_sit(), dazed_sit_hit(), splat(), slide_down(), miss_grab(), dazed_lie(),
            dazed_lie_hit(), slip(), stumble(), pole_fall(), get_up(), detuned(), tuned(), staff_stuck(),
            hit("Hit", 10, -0.25, 0), hit("HitHeavy", 16, -0.60, 1), parried("Parried", 12, -0.35, 0),
            parried("ParriedPerfect", 18, -0.55, 1)]
