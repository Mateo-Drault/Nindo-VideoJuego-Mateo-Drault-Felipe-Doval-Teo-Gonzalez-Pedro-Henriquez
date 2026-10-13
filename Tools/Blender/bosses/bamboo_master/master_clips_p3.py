"""Clips de la fase 3 de Chikuō (el bastón de bambú), el cambio de fase 2 -> 3 y la derrota.

Los golpes del bastón son VARIANTES de los de las fases 1 y 2 (Palm_P3, ChopPalm_P3...): mismos cuadros, tiempos,
eventos y avance que su clip base, así el jefe cambia de fase con un AnimatorOverrideController y los AttackDef, los
anillos y las marcas siguen valiendo. El cuerpo y los pies salen de las claves del clip base (con el tronco corregido
donde la mecánica del bastón pide otro giro) y los brazos y el bastón van en una pista aparte (overlay) con sus propias
claves: el bastón necesita más claves que el cuerpo para no cruzarlo.

Reglas del bastón (ver master_clips.staff_pose):
  * staff_dir va de la punta de abajo a la de arriba; la de abajo (la cabeza del hueso Staff) es la que pega;
  * en la guardia (STAFF_GUARD) la punta que pega apunta a Kaito, baja, y la de atrás queda detrás de la cadera
    izquierda: para pararlo, levantarlo o apoyarlo primero se DESLIZA entre las manos hacia adelante (así la punta de
    atrás sale del cuerpo por su eje) y recién después gira;
  * la mano que suelta el bastón va a lo que diga la clave del cuerpo (grip_*_w = 0).
"""
import copy, math
from mathutils import Vector
from nindo_anim import Key
import nindo_anim as NA
import master_rig as MR
import master_clips as MC
from master_clips import mod, n, feet, mix, hand, staff_pose, staff_hands, arms, flat, air, ball, land_xy, rz

HALF = MR.STAFF_LEN * 0.5
STAFF_TIP = ("Staff", (0.0, 0.0, 0.0))           # la punta de abajo: la que pega


def G3():
    """La guardia del bastón (anclada al pecho), la pose con la que empiezan y terminan todos los golpes."""
    return arms(MC.BODY, 3, right=True)


# ============================================================================ pista de brazos
_SIDE_KEYS = ("hand_{s}", "elbow_{s}", "fing_{s}", "tip_{s}", "spread_{s}", "thumb_{s}", "back_{s}")


def arm_track(p, sides="rl"):
    """Los canales de brazos y bastón de una pose (los de las manos de 'sides'): lo que pisa la pista aparte. El
    agarre de las dos manos va siempre (una mano que suelta tiene que decirlo: grip_*_w = 0)."""
    out = {k: v for k, v in p.items() if k.startswith(("staff_", "grip_"))}
    for s in sides:
        for k, v in p.items():
            if any(k.startswith(t.format(s=s)) for t in _SIDE_KEYS):
                out[k] = v
        # la mano que manda la pista no queda pegada al ancla de la guardia del clip base (la de la fase 2 torcía la
        # izquierda 5.6° contra el agarre del bastón)
        out.setdefault(f"hand_{s}_follow", 0.0)
    return copy.deepcopy(out)


def line(p, hr, hl, tip_from_r, gru=(0.0, 0.0, 1.0), glu=(0.0, 0.0, 1.0), rt=1.0, lt=-1.0, **kw):
    """El bastón por las dos manos con la punta que pega a tip_from_r metros de la derecha, del lado opuesto a la
    izquierda (la izquierda queda hacia la punta de atrás)."""
    hr, hl = Vector(hr), Vector(hl)
    d = (hl - hr).normalized()
    tip = hr - d * tip_from_r
    return staff_hands(p, tuple(tip + d * HALF), tuple(d), hr=tuple(hr), hl=tuple(hl), rt=rt, lt=lt, gru=gru, glu=glu, **kw)


def end_grip(p, hr, hl, end=0.15, **kw):
    """El bastón agarrado cerca de la punta de atrás (la izquierda a 'end' de ella): golpes de arriba y apoyos."""
    tip_from_r = MR.STAFF_LEN - end - (Vector(hl) - Vector(hr)).length
    return line(p, hr, hl, tip_from_r, **kw)


def p3_from(base, track, body=None, notes="", glow="Master_GlintStaff", strike=STAFF_TIP, timing=None, sides="rl"):
    """Variante _P3 del clip 'base': las claves del cuerpo del base (body(f, ctrl) corrige el tronco) y la pista de
    brazos 'track' = [(cuadro, pose, curva)] o una función (cuadro, ctrl del cuerpo) -> pose con una clave por cuadro.
    sides: de qué manos manda la pista (la otra la deja el clip base: la mano libre de la patada)."""
    b = next(c for c in MC.CLIPS if c.name == base)
    keys, ov = [], []
    for k in b.keys:
        ctrl = copy.deepcopy(k.ctrl)
        if body is not None:
            ctrl = body(k.frame, ctrl) or ctrl
        keys.append(Key(k.frame, ctrl, k.ease, dict(k.ease_ch), set(k.stops)))
        if callable(track):
            ov.append(Key(k.frame, arm_track(track(k.frame, ctrl), sides), "lin"))
    if not callable(track):
        # (cuadro, pose, curva[, {"stop": canales}]): un tope en la clave del apoyo (el bastón clavado no se pasa del piso)
        ov = [Key(k[0], arm_track(k[1], sides), k[2], None, (k[3] if len(k) > 3 else {}).get("stop", ())) for k in track]
    t = dict(b.timing)
    t.update(phase=3, glow=glow, strike=strike)
    if "reach_variants" in t:
        t["reach_variants"] = MC.reach_names(base, 3)
    if "pass_variant" in t:
        t["pass_variant"] = t["pass_variant"] + "_P3"
    t.update(timing or {})
    # los pasos del clip base (su pista de pies) siguen valiendo: los brazos y el bastón van encima
    c = MC.MClip(base + "_P3", b.frames, keys, phase=3, base=base, loop=b.loop, lag=dict(b.lag), timing=t,
                 events=copy.deepcopy(b.events), notes=notes, overlay=ov, overlays=b.overlays)
    MC.CLIPS.append(c)
    return c


def torso(over):
    """body() de p3_from: {cuadro: cambios del tronco}."""
    return lambda f, ctrl: mod(ctrl, **over[f]) if f in over else ctrl


# ============================================================================ golpes del bastón (variantes)
def thrust_p3(var=None):
    """Palm_P3, tsuki del bastón (dorado): el AVISO es el bastón recogido hacia atrás por la izquierda, que lo tira
    hasta la cadera de atrás, el tronco enroscado hacia su izquierda y la punta apenas delante de la derecha (desde
    arriba una línea larga que sale por detrás de él apuntando a Kaito). Con el paso del tui zhang la izquierda empuja,
    el bastón se desliza en la derecha y la punta llega a ~2.2 m del transform a la altura del pecho de Kaito; el tronco
    gira hacia su derecha (el hombro izquierdo va adelante con la mano que empuja). En las variantes de paso corto lo
    empuja menos y lo agarra más largo: con Kaito a 1.2-1.5 m la punta llega a ~1.45 m (con la entera lo atravesaba)."""
    k = 1.0 if var is None else MC.REACH_K[var]
    L3 = lambda a, b: tuple(Vector(a).lerp(Vector(b), k))
    over = {4: dict(hips_rot=(0.0, -1.0, 18.0), chest=(1.0, 0.0, 6.0), neck=(-1.0, 0.0, -10.0), head=(-4.0, 0.0, -14.0)),
            10: dict(hips_rot=(0.0, -2.0, 26.0), spine=(0.0, 0.0, 6.0), chest=(-2.0, 0.0, 6.0), neck=(0.0, 0.0, -16.0),
                     head=(-3.0, 0.0, -20.0), clav_r=(0.0, 0.0, 0.0)),
            12: dict(hips_rot=(0.0, -2.0, 27.0), spine=(0.0, 0.0, 6.0), chest=(-2.0, 0.0, 6.0), neck=(0.0, 0.0, -16.0),
                     head=(-3.5, 0.0, -20.5), clav_r=(0.0, 0.0, 0.0)),
            13: dict(hips_rot=(4.0, 0.0, 12.0), spine=(6.0, 0.0, 0.0), chest=(2.0, 0.0, -2.0), neck=(-3.0, 0.0, -4.0),
                     head=(-6.0, 0.0, -4.0)),
            # la cadera gira poco (con la pierna de adelante estirada no llegaba al pie): el giro lo hacen pecho y hombros
            15: dict(hips_rot=(8.0, 0.0, 10.0), spine=(10.0, 0.0, -10.0), chest=(4.0, 0.0, -10.0), neck=(-6.0, 0.0, 4.0),
                     head=(-10.0, 0.0, 8.0), clav_r=(0.0, 0.0, 0.0), clav_l=(0.0, 4.0, -6.0)),
            17: dict(hips_rot=(9.0, 0.0, 9.0), spine=(12.0, 0.0, -10.0), chest=(4.0, 0.0, -10.0), neck=(-6.0, 0.0, 5.0),
                     head=(-10.0, 0.0, 8.0), clav_r=(0.0, 0.0, 0.0), clav_l=(0.0, 4.0, -6.0))}
    B = MC.BODY
    er, el = dict(elbow_r=(-0.8, 0.2, -0.6), elbow_l=(0.8, 0.5, -0.4)), dict(elbow_r=(-0.6, 0.1, -0.8), elbow_l=(0.5, 0.3, -0.8))
    coil = line(B, (0.02, -0.44, 1.16), (0.3, 0.36, 1.18), 0.42, **er)
    hold = line(B, (0.02, -0.43, 1.165), (0.31, 0.38, 1.18), 0.41, **er)
    MC.POSES["tsuki aviso 3"] = coil
    track = [(0, G3(), "lin"), (4, line(B, (0.03, -0.5, 1.13), (0.25, 0.28, 1.25), 0.62, **er), "inout"),
             (10, coil, "inout"), (12, hold, "sine", {"stop": tuple(hold)}),
             (13, line(B, L3((0.02, -0.5, 1.16), (0.0, -0.58, 1.16)), L3((0.26, 0.2, 1.2), (0.22, 0.08, 1.2)),
                       0.55 + 0.2 * k, **er), "in2"),
             (15, line(B, L3((-0.03, -0.7, 1.15), (-0.06, -0.94, 1.14)), L3((0.16, -0.36, 1.19), (0.1, -0.6, 1.18)),
                       0.55 + 0.83 * k, **el), "expo_in"),
             (17, line(B, L3((-0.04, -0.74, 1.13), (-0.07, -1.0, 1.11)), L3((0.15, -0.4, 1.18), (0.09, -0.66, 1.16)),
                       0.59 + 0.83 * k, **el), "out"),
             # al recoger, la izquierda vuelve por fuera de la cadera (por delante del vientre cruzaba el tronco)
             (21, line(B, (0.0, -0.7, 1.12), (0.3, -0.22, 1.22), 1.05, **er), "inout"),
             (26, line(B, (0.09, -0.53, 1.13), (0.26, 0.18, 1.28), 0.8, **er), "inout"), (34, G3(), "sine")]
    return p3_from("Palm" if var is None else "Palm_" + var, track, torso(over),
                   notes="tsuki del bastón: lo recoge por la izquierda hasta la cadera de atrás (aviso f10) y con el paso lo "
                         "empuja; se desliza en la derecha y la punta pega a ~2.2 m en f15" +
                         ("" if var is None else ". Variante de paso corto (agarre largo)"))


def smash_p3(var=None):
    """ChopPalm_P3, el bastón que cae de arriba (dorado): lo desliza hasta agarrarlo de la punta de atrás y levanta la
    punta que pega por delante, por encima y hacia atrás; el AVISO es el bastón alzado detrás de la cabeza, casi 4 m de
    alto (desde la cámara del juego una vara larga que se va hacia atrás), el cuerpo estirado sobre la pierna de atrás.
    Baja en arco por encima de la cabeza y la punta cae a la altura del hombro de Kaito a ~2.6 m cuando el pie de
    adelante se clava. En las variantes de paso corto el bastón se le desliza entre las manos al bajar (lo agarra más
    corto): con Kaito pegado la punta cae a ~1.5 m."""
    k = 1.0 if var is None else MC.REACH_K[var]
    L3 = lambda a_, b_: tuple(Vector(a_).lerp(Vector(b_), k))
    over = {11: dict(clav_l=(0.0, -10.0, 0.0)), 13: dict(clav_l=(0.0, -10.0, 0.0))}
    B = MC.BODY
    up = dict(elbow_r=(-0.7, 0.3, 0.6), elbow_l=(0.7, 0.3, 0.5))
    lo = dict(elbow_r=(-0.6, 0.2, -0.8), elbow_l=(0.6, 0.2, -0.8))
    vert = dict(gru=(0.0, -1.0, 0.0), glu=(0.0, -1.0, 0.0))
    # la derecha agarra como una espada (el pulgar hacia la punta que pega) desde que lo alza hasta que vuelve: con los
    # pulgares mirándose de la guardia el bastón le salía por el lado del meñique y la muñeca se doblaba 47° hacia el
    # pulgar en la caída (1.95 de exceso). Lo suelta y lo vuelve a tomar mientras la izquierda lo sostiene (f0-5 y f28-36)
    sw = dict(rt=-1.0)
    raised = end_grip(B, (0.0, 0.02, 2.6), (0.06, -0.24, 2.38), **up, **sw)
    hold = end_grip(B, (0.0, 0.03, 2.61), (0.06, -0.23, 2.39), **up, **sw)
    MC.POSES["bastón alzado aviso 3"] = raised
    end_c = 0.12 + 1.08 * (1.0 - k)
    # (la izquierda 6 cm más cerca del hombro y con los nudillos arriba como en la guardia: en (0.28, -0.42, 1.32) y con
    # los nudillos hacia Kaito el brazo llegaba estirado del todo y el puño daba más de media vuelta alrededor del caño,
    # 55° de muñeca en un cuadro)
    stand = end_grip(B, (0.16, -0.6, 1.66), (0.27, -0.38, 1.37), end=0.3, gru=vert["gru"], **lo, **sw)
    back = line(B, (0.09, -0.53, 1.13), (0.26, 0.18, 1.28), 0.8, elbow_r=(-0.8, 0.2, -0.6), elbow_l=(0.8, 0.5, -0.4), **sw)
    track = [(0, G3(), "lin"),
             (2, mod(mix(G3(), stand, 0.5), grip_r_w=0.0, grip_r_thumb=0.0), "sine"),
             # se para delante a su izquierda: la izquierda sale de la cadera de atrás por afuera del vientre
             (5, stand, "inout"),
             # llega arriba en f9 y se asienta hasta el aviso: la punta, a 4 m de las manos, llegaba todavía rápida
             (9, end_grip(B, (0.0, -0.02, 2.56), (0.06, -0.28, 2.34), **up, **sw), "inout"),
             (11, raised, "sine", {"stop": ("staff_pos",)}),
             (13, hold, "sine", {"stop": tuple(hold)}),
             (15, end_grip(B, (-0.01, -0.5, 2.42), (0.06, -0.4, 2.06), end=0.15 + 0.5 * (1.0 - k), **vert, **up, **sw), "in2"),
             # las manos terminan adelante y abajo, lejos del pecho que se dobla: el bastón cae en diagonal
             (17, end_grip(B, L3((0.12, -0.86, 1.3), (-0.06, -1.16, 1.04)), L3((0.24, -0.6, 1.5), (0.08, -0.82, 1.2)), end=end_c,
                           **lo, **sw), "expo_in"),
             (19, end_grip(B, L3((0.12, -0.88, 1.2), (-0.06, -1.18, 0.92)), L3((0.24, -0.63, 1.41), (0.08, -0.85, 1.1)), end=end_c,
                           **lo, **sw), "out"),
             (23, line(B, (0.0, -0.74, 1.12), (0.3, -0.3, 1.22), 1.0, **lo, **sw), "inout"),
             (28, back, "inout"),
             (30, mod(mix(back, G3(), 0.3), grip_r_w=0.0, grip_r_thumb=0.0), "inout"),
             (36, G3(), "sine")]
    return p3_from("ChopPalm" if var is None else "ChopPalm_" + var, track, torso(over), timing={"staff_high": True},
                   notes="el bastón cae de arriba: alzado detrás de la cabeza (aviso f11, la punta a ~4 m), baja en arco y "
                         "pega a la altura del hombro de Kaito a ~2.6 m en f17" +
                         ("" if var is None else ". Variante de paso corto (el bastón se desliza a un agarre corto)"))


def side_staff(z=1.32, grip=0.2):
    """El bastón parado al costado izquierdo en la mano izquierda (la derecha libre: patadas), anclado al pecho. La
    punta que pega queda ARRIBA: sale de la guardia levantando la punta de adelante (la izquierda, con el pulgar hacia
    ella, queda con el pulgar arriba y el bastón se desliza en la mano hasta casi el piso). Con la punta abajo el
    pulgar quedaba para abajo y el antebrazo llegaba a 150° de giro."""
    p = staff_pose(MC.BODY, (0.5, -0.18, z), (0.0, -0.08, -1.0), upv=(0.0, -1.0, 0.0), gr=None, gl=-grip,
                   glu=(1.0, 0.0, 0.0), elbow_l=(0.85, 0.3, -0.45))
    q = MC.to_chest(p, ("staff",))
    return mod(p, **{k: q[k] for k in ("staff_cpos", "staff_cdir", "staff_cup", "staff_follow")})


def grip_ends(last):
    """body() que deja la derecha con forma de agarre en la primera y la última clave (la pista solo manda la
    izquierda: la derecha agarra el bastón de la guardia en los extremos y entre medio es la del clip base)."""
    return lambda f, ctrl: mod(ctrl, **MR.hand_shape("r", "grip")) if f in (0, last) else ctrl


def crane_p3():
    """CraneKick_P3: la grulla con el bastón parado en la izquierda, al costado de la pierna de apoyo (una garza al lado
    de una caña); la derecha es el ala de la grulla y patea igual que en la fase 1."""
    s = side_staff()
    # la derecha suelta el bastón en los primeros 3 cuadros (el ala se abre después): soltándolo en 6 la mano quedaba a
    # mitad de camino entre el agarre y el ala, con la muñeca en 1.42
    let_go = mod(mix(G3(), s, 0.5), grip_r_w=0.0)
    track = [(0, G3(), "lin"), (3, let_go, "inout"), (6, s, "inout"), (34, s, "lin"), (42, G3(), "inout")]
    return p3_from("CraneKick", track, body=grip_ends(42), sides="l", glow="Master_GlintFootR", strike=MC.TOE_R,
                   notes="grulla con el bastón parado en la izquierda (aviso f13), patada de frente (f18)")


def bar(z, y, out=0.36, lean=0.0):
    """El bastón cruzado de lado a lado (la punta que pega a su derecha) con las dos manos a 'out' del centro, anclado
    al pecho de la guardia: acompaña la agachada y el vuelo."""
    c = Vector((0.04, y, z))
    d = Vector((1.0, 0.0, lean)).normalized()
    p = staff_hands(MC.BODY, tuple(c), tuple(d), hr=tuple(c - d * out), hl=tuple(c + d * out),
                    gru=(0.0, -0.2, 1.0), glu=(0.0, -0.2, 1.0), elbow_r=(-0.8, 0.3, -0.5), elbow_l=(0.8, 0.3, -0.5))
    q = MC.to_chest(p, ("staff",))
    return mod(p, **{k: q[k] for k in ("staff_cpos", "staff_cdir", "staff_cup", "staff_follow")})


def leap_p3():
    """LeapKick_P3: la patada voladora con el bastón cruzado: bajo delante del vientre en la agachada (gira de la
    guardia a cruzado por su costado izquierdo, por fuera del cuerpo), alzado sobre la cabeza en el vuelo y otra vez
    abajo al caer sobre la marca. Parado al costado chocaba con la rodilla izquierda en la agachada."""
    low, high = bar(1.52, -0.5, lean=-0.06), bar(2.42, -0.12, out=0.42)
    track = [(0, G3(), "lin"), (9, low, "inout"), (19, low, "lin"), (24, high, "out2"), (30, high, "lin"),
             (34, bar(1.62, -0.72, lean=-0.06), "in2"), (46, low, "inout"), (56, G3(), "inout")]
    return p3_from("LeapKick", track, glow="Master_GlintFootR", strike=("Foot_R", (0.0, 0.0, 0.0)), timing={"staff_high": True},
                   notes="patada voladora con el bastón cruzado: abajo en la agachada (aviso f19), alzado en el vuelo y abajo "
                         "al caer sobre la marca (f33); mismos tiempos y marca que LeapKick")


def anchored(p):
    """La pose p con su bastón pegado al pecho tal como queda resuelto en la guardia (acompaña giros y agachadas)."""
    q = MC.to_chest(p, ("staff",))
    return mod(p, **{k: q[k] for k in ("staff_cpos", "staff_cdir", "staff_cup", "staff_follow")})


MC_SWEEP_APEX = 12


def sweep_p3():
    """Sweep_P3, la barrida con el bastón (roja, anillo más grande): el bastón queda del lado de la guardia, pegado al
    pecho y deslizado hacia adelante, con la punta levantada lo justo para que la agachada la deje a ras del piso: gira
    con el cuerpo como un rayo de la rueda, por delante, mientras la pierna derecha barre por su costado. Llevarlo
    estirado a la derecha obligaba a cruzarlo por delante de la cadera, que en la barrida se corre sobre el pie de
    apoyo y quedaba justo en el camino."""
    # la pose del bastón se arma sobre el cuerpo agachado del aviso (f12) y se ancla a ESE pecho: las dos manos
    # delante de las rodillas y la punta a ras del piso hacia adelante
    ctrl = next(k.ctrl for k in next(c for c in MC.CLIPS if c.name == "Sweep").keys if k.frame == MC_SWEEP_APEX)
    d = ctrl["hips_rot"][2] - 14.0
    hc = Vector(ctrl["hips"][:2])

    def loc(x, y, z):
        q = rz(d, (x, y, 0.0))
        return (hc.x + q.x, hc.y + q.y, z)
    low = anchored(line(mod(ctrl, **{k: v for k, v in G3().items() if k.startswith(("staff_", "grip_"))}),
                        loc(-0.12, -0.62, 0.52), loc(0.2, -0.22, 0.66), 1.62, gru=tuple(rz(d, (0.0, 0.0, 1.0))),
                        glu=tuple(rz(d, (0.0, 0.0, 1.0))), elbow_r=tuple(rz(d, (-0.7, 0.3, -0.6))),
                        elbow_l=tuple(rz(d, (0.7, 0.4, -0.6)))))
    MC.POSES["barrida con bastón 3"] = low

    # a mitad de camino, la guardia deslizada 0.5 m por su eje, abierta y con la punta un poco más alta (la de atrás pasa
    # por el costado y la de adelante no toca el piso cuando el pecho se inclina)
    slid = anchored(line(MC.BODY, (0.06, -0.56, 1.24), (0.3, 0.12, 1.26), 1.3, elbow_r=(-0.8, 0.2, -0.6),
                         elbow_l=(0.8, 0.5, -0.4)))

    def track(f, ctrl):
        w = NA.ease("inout", max(0.0, min(1.0, (f - 3) / 7.0))) * NA.ease("inout", max(0.0, min(1.0, (42 - f) / 8.0)))
        q = mix(G3(), slid, w / 0.4) if w < 0.4 else mix(slid, low, (w - 0.4) / 0.6)
        # los codos giran con el cuerpo (un polo fijo en el espacio del personaje metía el codo en el pecho a 180°)
        dn = ctrl["hips_rot"][2] - 14.0
        k = max(0.0, min(1.0, (w - 0.4) / 0.6))
        q["elbow_r"] = tuple(NA.slerp_dir(Vector(q["elbow_r"]), rz(dn, (-0.7, 0.3, -0.6)), k))
        q["elbow_l"] = tuple(NA.slerp_dir(Vector(q["elbow_l"]), rz(dn, (0.7, 0.4, -0.6)), k))
        return q
    return p3_from("Sweep", track, timing={"ring_m": 2.3},
                   notes="barrida con el bastón: la pierna derecha a ras del piso y el bastón por delante giran juntos la "
                         "vuelta entera (f16-30); anillo rojo de ring_m")


def qi_p3():
    """QiWave_P3, el bastón que se clava (rojo, anillo): lo desliza hacia adelante hasta agarrarlo de la punta de atrás,
    lo para delante del cuerpo, lo alza con las dos manos mientras junta el qi (AVISO: el bastón vertical en alto, casi
    4 m), y con el pisotón lo clava en el piso delante de él: de ahí sale el anillo (QiRelease)."""
    B = MC.BODY
    vert = dict(gru=(0.0, -1.0, 0.0), glu=(0.0, -1.0, 0.0), elbow_r=(-0.8, 0.0, -0.6), elbow_l=(0.8, 0.0, -0.6))
    g_r, g_l = (0.09, -0.53, 1.13), (0.26, 0.18, 1.28)
    # delante a su izquierda (x 0.2): la izquierda llega desde la cadera de atrás sin cruzar el vientre
    high = end_grip(B, (0.28, -0.56, 2.26), (0.31, -0.55, 1.92), end=0.2, **vert)
    MC.POSES["bastón en alto aviso 3"] = high
    # clavado bien adelante: en el empuje el tronco se inclina y la cabeza se le venía encima
    planted = end_grip(B, (0.28, -0.8, 1.3), (0.3, -0.82, 0.96), end=0.95, **vert)
    track = [(0, G3(), "lin"), (5, line(B, g_r, g_l, 1.7, elbow_r=(-0.8, 0.2, -0.6), elbow_l=(0.8, 0.5, -0.4)), "inout"),
             (9, line(B, (0.1, -0.62, 1.22), (0.32, -0.2, 1.22), 1.75, elbow_r=(-0.8, 0.1, -0.6), elbow_l=(0.8, 0.3, -0.5)), "inout"),
             # (la derecha con los nudillos arriba como en la guardia: girada hacia Kaito el puño daba la vuelta al caño y la
             # muñeca 56° en un cuadro)
             (13, end_grip(B, (0.28, -0.6, 1.5), (0.32, -0.57, 1.12), end=0.2, **dict(vert, gru=(0.0, 0.0, 1.0))), "inout"),
             (21, high, "inout"), (30, end_grip(B, (0.28, -0.56, 2.27), (0.31, -0.55, 1.93), end=0.2, **vert), "sine"),
             (33, end_grip(B, (0.28, -0.56, 2.34), (0.31, -0.55, 2.0), end=0.2, **vert), "out2"),
             # el clavado acelera hasta el piso (con expo_in casi todo el camino caía en el último cuadro: los brazos bajaban
             # de la cabeza a la cadera de golpe y la muñeca izquierda daba 51° en un cuadro)
             (36, planted, "in2", {"stop": ("staff_pos",)}), (40, planted, "lin", {"stop": ("staff_pos",)}),
             # al sacarlo del piso la punta de atrás sale por fuera del muslo izquierdo
             (45, line(B, (0.16, -0.66, 1.45), (0.35, -0.4, 1.22), 1.2, elbow_r=(-0.7, 0.1, -0.7), elbow_l=(0.8, 0.3, -0.5)), "inout"),
             (50, line(B, (0.08, -0.55, 1.15), (0.26, 0.1, 1.27), 0.95, elbow_r=(-0.8, 0.2, -0.6), elbow_l=(0.8, 0.5, -0.4)), "inout"),
             (56, G3(), "sine")]
    # lo que pega es la punta de atrás (la de arriba del hueso: la que se clava)
    return p3_from("QiWave", track, glow=["Master_GlintStaff"], strike=("Staff", (0.0, MR.STAFF_LEN, 0.0)),
                   timing={"staff_high": True},
                   notes="el bastón se clava: alzado vertical con las dos manos (aviso f30), pisotón y lo clava delante en "
                         "f36 (QiRelease: el anillo sale del transform)")


def dash_p3():
    """DashStrike_P3, la embestida con el bastón (roja): el aviso es el tsuki recogido, se dispara a ras del piso con
    el bastón adelante y lo clava con la estocada al frenar."""
    B = MC.BODY
    er, el = dict(elbow_r=(-0.8, 0.2, -0.6), elbow_l=(0.8, 0.5, -0.4)), dict(elbow_r=(-0.6, 0.1, -0.8), elbow_l=(0.5, 0.3, -0.8))
    coil = line(B, (0.11, -0.46, 1.02), (0.5, 0.28, 1.0), 0.42, **er)
    track = [(0, G3(), "lin"), (6, coil, "inout"), (8, line(B, (0.11, -0.45, 1.01), (0.5, 0.29, 1.0), 0.41, **er), "sine"),
             # en el vuelo lo lleva bajo, pegado a la cadera izquierda y por afuera: el tronco va inclinado encima
             (10, line(B, (0.15, -0.7, 0.95), (0.5, -0.06, 0.95), 0.8, **er), "in2"),
             (15, line(B, (0.08, -0.8, 0.98), (0.4, -0.22, 1.0), 1.0, **el), "inout"),
             # el cuerpo de la estocada se inclina y gira: las manos van bien adelante y abajo, lejos del pecho
             (17, line(B, (-0.1, -1.08, 1.0), (0.24, -0.78, 1.02), 1.42, **el), "expo_in"),
             (21, line(B, (-0.1, -1.1, 0.98), (0.24, -0.8, 1.0), 1.44, **el), "out"),
             (25, line(B, (0.0, -0.8, 1.08), (0.32, -0.32, 1.18), 1.15, **er), "inout"),
             (30, line(B, (0.08, -0.56, 1.13), (0.27, 0.12, 1.27), 0.82, **er), "inout"), (36, G3(), "sine")]
    return p3_from("DashStrike", track, glow="Master_GlintStaff",
                   notes="embestida con el bastón: tsuki recogido (aviso f8), sale en f9 y clava la punta al frenar (f17)")


def dash_pass_p3():
    """DashStrike_Pass_P3, el paso del viento al costado con el bastón (rojo): el cuerpo de DashStrike_Pass y, hasta la
    suelta, los brazos de DashStrike_P3. En el vuelo lo lleva bajo y en diagonal por delante y en el cruce se lo clava a
    Kaito con la punta de abajo, las dos manos adelante y el resto del bastón hacia atrás por afuera de su cadera
    izquierda (de frente a Kaito, la punta llega a ~1.1 m: lo toca sin que el cuerpo pase por él) y se la sostiene encima
    mientras le pasa (f17-f20); gira con él en el aire y lo recoge a la guardia al frenar."""
    B = MC.BODY
    er, el = dict(elbow_r=(-0.8, 0.2, -0.6), elbow_l=(0.8, 0.5, -0.4)), dict(elbow_r=(-0.6, 0.1, -0.8), elbow_l=(0.5, 0.3, -0.8))
    coil = line(B, (0.11, -0.46, 1.02), (0.5, 0.28, 1.0), 0.42, **er)
    track = [(0, G3(), "lin"), (6, coil, "inout"), (8, line(B, (0.11, -0.45, 1.01), (0.5, 0.29, 1.0), 0.41, **er), "sine"),
             # sale como DashStrike_P3 (el bastón bajo, adelante a su izquierda) y lo lleva así todo el vuelo: el cuerpo
             # gira hacia Kaito por encima y el bastón queda en diagonal por delante
             (10, line(B, (0.15, -0.7, 0.95), (0.5, -0.06, 0.95), 0.8, **er), "in2"),
             (13, line(B, (0.08, -0.7, 1.0), (0.45, -0.12, 0.98), 0.6, **er), "inout"),
             (15, line(B, (0.06, -0.6, 1.06), (0.4, -0.1, 1.0), 0.5, **el), "inout"),
             # el cruce: la punta de abajo a la altura del pecho de Kaito, las manos adelante y el bastón casi por la línea
             # que va a él (el resto hacia atrás, por afuera de su cadera izquierda); la sostiene sobre él mientras le pasa
             # (f17-f20: el jefe lo hace mirar a Kaito), corriéndola un poco hacia su derecha
             (17, line(B, (0.06, -0.6, 1.12), (0.23, -0.14, 1.04), 0.5, **el), "expo_in"),
             (18, line(B, (0.04, -0.61, 1.12), (0.22, -0.14, 1.05), 0.5, **el), "lin"),
             (19, line(B, (0.02, -0.61, 1.12), (0.21, -0.13, 1.05), 0.51, **el), "lin"),
             (20, line(B, (-0.01, -0.6, 1.12), (0.21, -0.12, 1.05), 0.52, **el), "lin"),
             # la suelta y gira con él; lo recoge al apoyar
             (21, line(B, (-0.1, -0.46, 1.12), (0.3, 0.04, 1.06), 0.55, **el), "out"),
             (23, line(B, (0.0, -0.66, 1.04), (0.38, 0.0, 1.02), 0.7, **er), "inout"),
             (29, line(B, (0.08, -0.56, 1.13), (0.27, 0.12, 1.27), 0.82, **er), "inout"), (36, G3(), "sine")]
    return p3_from("DashStrike_Pass", track, glow="Master_GlintStaff",
                   notes="paso del viento al costado con el bastón: tsuki recogido (aviso f8), vuela por al lado de Kaito "
                         "y se lo clava de frente en el cruce (f17), lo sostiene sobre él hasta f20, gira en el aire y apoya "
                         "frenando hacia atrás")


# ============================================================================ derrota: se sienta a meditar y saluda
# rendido, apoya la punta del bastón en el piso adelante a su izquierda y lo suelta: cae de costado (gira sobre esa
# punta) y queda en el piso a su izquierda apuntando a Kaito, como quien deja la espada al costado
DROP_TIP = Vector((0.44, -1.25, MR.STAFF_R + 0.005))
# (3 cm más arriba y adentro que con el pulgar hacia la punta de arriba: con el de la fase 3, hacia la de abajo, el puño
# queda del otro lado del caño y la mano no llegaba por 2.3 cm)
DROP_HAND = Vector((0.48, -0.22, 1.08))
FLOOR_DIR = Vector((0.24, 0.97, 0.0)).normalized()


def staff_from_tip(p, d, hl=None, upv=(0.0, 0.0, 1.0)):
    """El bastón con la punta que pega apoyada en DROP_TIP y el eje d (hacia la punta de arriba); hl = la izquierda que
    lo sostiene (None = suelto)."""
    d = Vector(d).normalized()
    c = DROP_TIP + d * HALF
    if hl is None:
        return staff_pose(p, tuple(c), tuple(d), upv=upv, gr=None, gl=None)
    return staff_hands(p, tuple(c), tuple(d), hl=tuple(hl), glu=(1.0, 0.0, 0.2), elbow_l=(0.8, 0.4, -0.4))


def floor_staff(p):
    return staff_from_tip(p, FLOOR_DIR)


def seated(breath=0.0, bow=0.0, hands="knees"):
    """Sentado con las piernas cruzadas (el pie derecho delante de la tibia izquierda), la espalda derecha, las manos
    sobre las rodillas con las palmas arriba. bow 0..1: la reverencia desde la cadera."""
    p = feet(mod(MC.BODY, hips=(0.0, 0.06, -0.945 - 0.006 * breath), hips_rot=(4.0 + 22.0 * bow, 0.0, 0.0),
                 spine=(3.0 + 10.0 * bow, 0.0, 0.0), chest=(1.0 + 6.0 * bow - 2.0 * breath, 0.0, 0.0),
                 neck=(-2.0 + 6.0 * bow, 0.0, 0.0), head=(6.0 + 10.0 * bow, 0.0, 0.0), breath=breath,
                 knee_r=(-1.0, -0.45, 0.25), knee_l=(1.0, -0.45, 0.25)),
             r=((0.12, -0.43, 0.21), (0.0, -55.0, 95.0), 0.0), l=((-0.14, -0.2, 0.148), (0.0, 55.0, -95.0), 0.0))
    if hands == "knees":
        p = hand(p, "r", (-0.44, -0.42, 0.44 - 0.004 * breath), (0.2, -0.95, -0.1), (0.0, 0.0, -1.0), elbow=(-0.6, 0.6, -0.4),
                 shape="relaxed")
        p = hand(p, "l", (0.44, -0.42, 0.44 - 0.004 * breath), (-0.2, -0.95, -0.1), (0.0, 0.0, -1.0), elbow=(0.6, 0.6, -0.4),
                 shape="relaxed")
    return floor_staff(mod(p, back_l=0.0, back_r=0.0))


def _side_hand(p, s_):
    """La mano s_ colgando al costado del muslo, floja (ya no pelea)."""
    x = -0.36 if s_ == "r" else 0.36
    # a la altura del muslo con el codo apenas doblado hacia atrás (más arriba quedaba en jarra, con las manos en la cadera)
    return hand(p, s_, (x * 0.95, 0.0, 1.06), (0.0, 0.05, -1.0), (-1.0 if s_ == "r" else 1.0, 0.0, 0.0),
                elbow=(-0.3 if s_ == "r" else 0.3, 0.95, 0.0), shape="relaxed")


def defeat():
    """Defeat (fase 3, 5 s): baja la guardia, apoya la punta del bastón adelante a su izquierda y la derecha cae al
    costado; respira hondo mirando a Kaito y suelta el bastón, que cae de costado y queda en el piso (StaffDrop /
    StaffLand). Cruza el pie derecho por delante del izquierdo, acomoda el izquierdo y se sienta con las piernas
    cruzadas (SitDown); las manos van a las rodillas y queda meditando: encadena con Meditate."""
    B = MC.BODY
    a0 = (DROP_HAND - DROP_TIP).normalized()
    tired = feet(_side_hand(mod(B, hips=(0.02, 0.1, -0.13), hips_rot=(4.0, 0.0, 10.0), spine=(8.0, 0.0, 2.0), chest=(4.0, 0.0, 2.0),
                                neck=(4.0, 0.0, -6.0), head=(8.0, 0.0, -6.0), breath=0.3), "r"))
    tired = staff_from_tip(tired, a0, hl=DROP_HAND)
    breathe = staff_from_tip(_side_hand(mod(tired, hips=(0.02, 0.06, -0.06), spine=(2.0, 0.0, 2.0), chest=(-3.0, 0.0, 2.0),
                                            neck=(-2.0, 0.0, -6.0), head=(-4.0, 0.0, -6.0), breath=1.0), "r"), a0,
                             hl=DROP_HAND + Vector((0.0, 0.0, 0.03)))
    look = staff_from_tip(mod(breathe, breath=0.2, head=(-2.0, 0.0, -5.0)), a0, hl=DROP_HAND)
    # suelta: la izquierda se abre y el bastón cae girando sobre la punta apoyada (más rápido a medida que cae)
    free = _side_hand(_side_hand(mod(look, breath=0.0, head=(6.0, 0.0, -4.0), neck=(2.0, 0.0, -4.0)), "r"), "l")
    fall = []
    for i, f in enumerate(range(30, 41, 2)):
        u = (f - 28) / 12.0
        dd = NA.slerp_dir(a0, FLOOR_DIR, min(1.0, u * u))
        fall.append((f, staff_from_tip(free, dd), "lin"))
    rest = floor_staff(free)
    # cruza las piernas de pie (paso del derecho por delante del izquierdo, después acomoda el izquierdo) y baja
    RX, RY, RYAW = land_xy(MC.FOOT_R0)
    LX, LY, LYAW = land_xy(MC.FOOT_L0)
    sr, sl = seated()["foot_r"], seated()["foot_l"]
    cr = flat(sr[0], sr[1], 95.0 - 60.0)
    cl = flat(sl[0], sl[1], -40.0)
    step_r = feet(mod(rest, hips=(0.04, 0.06, -0.1), hips_rot=(0.0, 0.0, 6.0)), r=air((RX + sr[0]) * 0.5, (RY + sr[1]) * 0.5, 0.3,
                                                                                        yaw=30.0))
    crossed = feet(mod(rest, hips=(0.03, 0.02, -0.12), hips_rot=(0.0, 0.0, 0.0), head=(4.0, 0.0, 0.0), neck=(0.0, 0.0, 0.0),
                       spine=(4.0, 0.0, 0.0), chest=(2.0, 0.0, 0.0)), r=cr)
    step_l = feet(mod(crossed, hips=(0.0, 0.04, -0.12)), l=air((LX + sl[0]) * 0.5, (LY + sl[1]) * 0.5, 0.26, yaw=-10.0))
    both = feet(mod(crossed, hips=(0.0, 0.05, -0.16)), l=cl)
    low = mod(seated(), hips=(0.0, 0.08, -0.55), spine=(14.0, 0.0, 0.0), head=(-2.0, 0.0, 0.0))
    # baja con los pies planos (de plano a la bola, mezclado, el pie se corría ~4 cm)
    low = feet(_side_hand(_side_hand(low, "r"), "l"), r=cr, l=cl)
    sit = seated()
    sat = mod(sit, hips=(0.0, 0.06, -0.955), breath=0.5)
    MC.POSES["piernas cruzadas de pie 3"] = both
    def lifted(ft, dz):
        return (tuple(Vector(ft[0]) + Vector((0.0, 0.0, dz))), ft[1], ft[2])
    fr_low = (low["foot_r"], low["foot_r_rot"], low.get("toe_r", 0.0))
    fl_low = (low["foot_l"], low["foot_l_rot"], low.get("toe_l", 0.0))
    fr_sit = (sit["foot_r"], sit["foot_r_rot"], sit.get("toe_r", 0.0))
    fl_sit = (sit["foot_l"], sit["foot_l_rot"], sit.get("toe_l", 0.0))
    mid_r = (tuple(Vector(fr_low[0]).lerp(Vector(fr_sit[0]), 0.5) + Vector((0.0, 0.0, 0.07))),
             tuple(Vector(fr_low[1]).lerp(Vector(fr_sit[1]), 0.5)), (fr_low[2] + fr_sit[2]) * 0.5)
    mid_l = (tuple(Vector(fl_low[0]).lerp(Vector(fl_sit[0]), 0.5) + Vector((0.0, 0.0, 0.07))),
             tuple(Vector(fl_low[1]).lerp(Vector(fl_sit[1]), 0.5)), (fl_low[2] + fl_sit[2]) * 0.5)
    feet_keys = {"r": [(86, fr_low, "lin"), (88, lifted(fr_low, 0.05), "out2"), (93, mid_r, "inout"),
                       (96, lifted(fr_sit, 0.03), "inout"), (98, fr_sit, "in2"), (150, fr_sit, "lin")],
                 "l": [(86, fl_low, "lin"), (89, lifted(fl_low, 0.05), "out2"), (94, mid_l, "inout"),
                       (97, lifted(fl_sit, 0.03), "inout"), (99, fl_sit, "in2"), (150, fl_sit, "lin")]}
    tr = {sd: [(0, ks[0][1], "lin")] + ks for sd, ks in feet_keys.items()}
    steps = [(f, {sd: MC._foot_at(tr[sd], f) for sd in ("r", "l")}, "lin") for f in range(86, 151)]
    keys = [(0, G3(), "sine"), (10, tired, "inout"), (20, breathe, "sine"), (28, look, "inout")] + fall + \
           [(44, rest, "out"), (54, step_r, "out2"), (60, crossed, "in2"), (66, step_l, "out2"), (72, both, "in2"),
            (86, low, "inout"), (98, sat, "out"), (112, sit, "inout"), (150, sit, "sine")]
    return MC.add("Defeat", 150, keys, ph=3, variant=False, lag={"head": 2.0, "neck": 1.0}, steps=steps,
                  timing={"kind": "none", "chain_from": "READY", "chain_to": "MEDITATE", "legs_cross": [[56, 150]],
                          "staff_drop": 30, "staff_rest": 40},
                  events=[{"frame": 20, "fn": "Exhale"}, {"frame": 30, "fn": "StaffDrop"}, {"frame": 40, "fn": "StaffLand"},
                          {"frame": 60, "fn": "Step"}, {"frame": 72, "fn": "Step"}, {"frame": 98, "fn": "SitDown"},
                          {"frame": 112, "fn": "Meditate"}],
                  notes="se rinde: apoya el bastón y respira (f20), lo suelta y cae a su izquierda (f30-40), cruza las "
                        "piernas de pie y se sienta (f98); en f112 ya medita (encadenar con Meditate)")


def meditate():
    """Meditate (loop 3.2 s): sentado con las piernas cruzadas, respira lento; la cabeza apenas sube con el aire."""
    a = seated()
    b = mod(seated(1.0), head=(4.5, 0.0, 0.0))
    MC.CHAIN["MEDITATE"] = {3: a}
    return MC.add("Meditate", 96, [(0, a, "sine"), (44, b, "sine"), (96, a, "sine")], ph=3, variant=False, loop=True,
                  lag={"head": 3.0, "neck": 1.5},
                  timing={"kind": "idle", "chain_from": "MEDITATE", "chain_to": "MEDITATE", "legs_cross": [[0, 96]]},
                  notes="medita sentado (después de Defeat): inspira en 1.5 s y suelta el aire")


def seated_bow():
    """SeatedBow (2.3 s): desde la meditación junta el puño derecho en la palma izquierda delante del pecho (el saludo
    del principio de la pelea), se inclina desde la cadera hacia Kaito, se sostiene, se endereza y las manos vuelven a
    las rodillas."""
    a = seated()
    sal = seated(0.3, hands=None)
    sal = hand(sal, "r", (-0.03, -0.38, 0.86), (1.0, -0.1, 0.0), (0.0, -1.0, 0.2), elbow=(-0.8, 0.2, -0.5), shape="fist")
    sal = hand(sal, "l", (0.08, -0.4, 0.89), (0.0, -0.1, 1.0), (1.0, 0.0, 0.0), elbow=(0.8, 0.2, -0.5), shape="palm")
    sal = MC.to_chest(sal, ("r", "l"))
    MC.POSES["saludo sentado 3"] = sal
    bow = mod(sal, hips_rot=(26.0, 0.0, 0.0), spine=(12.0, 0.0, 0.0), chest=(8.0, 0.0, 0.0), neck=(6.0, 0.0, 0.0),
              head=(12.0, 0.0, 0.0), breath=0.0)
    MC.POSES["reverencia sentado 3"] = bow
    keys = [(0, a, "sine"), (12, sal, "inout"), (18, sal, "sine"), (30, bow, "inout"), (42, mod(bow, head=(13.0, 0.0, 0.0)), "sine"),
            (54, sal, "inout"), (60, mod(sal, breath=0.5), "sine"), (70, a, "inout")]
    return MC.add("SeatedBow", 70, keys, ph=3, variant=False, lag={"head": 2.0, "neck": 1.0},
                  timing={"kind": "none", "chain_from": "MEDITATE", "chain_to": "MEDITATE", "legs_cross": [[0, 70]]},
                  events=[{"frame": 12, "fn": "Salute"}, {"frame": 30, "fn": "Bow"}, {"frame": 54, "fn": "BowEnd"}],
                  notes="saludo sentado: puño en la palma (f12), reverencia a Kaito (f30-42) y vuelve a meditar (f70)")


# ============================================================================ cambio de fase 2 -> 3: el bastón
SPAWN = Vector((-3.4, -0.6, 2.2))          # de donde viene el bastón (el bambú a su derecha): StaffAppear


def phase_staff():
    """PhaseStaff (fase 2 -> 3, 3 s): se para derecho y estira el brazo derecho hacia el bambú con la palma abierta
    (StaffCall); el bastón aparece en el aire a 3.4 m a su derecha (StaffAppear: el juego enciende Master_Staff con un
    golpe de hojas) y vuela dando una vuelta y cuarto hasta su mano (StaffCatch). Lo hace girar por arriba de la
    cabeza hasta cruzarlo con las dos manos en alto (StaffPresent: 'El bambú se dobla...'), y lo baja por delante a la
    guardia del bastón."""
    B = MC.BODY
    g2 = arms(B, 2, right=True)
    call = arms(mod(B, hips=(0.0, 0.08, -0.08), hips_rot=(0.0, 0.0, 8.0), spine=(-2.0, 0.0, -2.0), chest=(-4.0, -4.0, -4.0),
                    neck=(-2.0, 0.0, -2.0), head=(-4.0, 0.0, -4.0), breath=1.0), 2)
    # el brazo estirado al costado con el pulgar arriba y la palma hacia adelante (con el dorso adelante el antebrazo
    # quedaba girado 155° y no había cómo llegar al agarre del bastón sin media vuelta)
    call = hand(call, "r", (-1.02, -0.22, 1.84), (-1.0, -0.1, 0.25), (0.0, 1.0, 0.1), elbow=(0.0, 0.3, -1.0), shape="palm")
    MC.POSES["llama al bastón 2"] = call
    catch_pos = Vector((-0.98, -0.24, 1.84))
    keys = [(0, mod(g2, staff_on=1.0, staff_pos=tuple(SPAWN), staff_dir=(0.0, 0.0, 1.0), staff_up=(0.0, -1.0, 0.0)), "sine")]
    k_call = mod(call, staff_on=1.0, staff_pos=tuple(SPAWN), staff_dir=(0.0, 0.0, 1.0), staff_up=(0.0, -1.0, 0.0))
    keys += [(8, k_call, "inout"), (12, k_call, "lin")]
    # mientras el bastón vuela la palma abierta gira a recibirlo (los dedos adelante y afuera, la palma hacia adelante y
    # adentro: la mano del agarre de f25); si esperaba con los dedos hacia afuera, al atraparlo la mano daba 58° en un
    # cuadro
    k_ready = hand(k_call, "r", (-1.0, -0.24, 1.84), (-0.7, -0.7, 0.1), (-0.7, 0.7, 0.0), elbow=(0.0, 0.3, -1.0), shape="palm")
    # vuelo: de SPAWN a la mano en un arco, girando en el plano del frente 1.25 vueltas (termina vertical)
    for f in range(13, 25):
        u = (f - 12) / 12.0
        e = 1.0 - (1.0 - u) ** 1.6
        c = SPAWN.lerp(catch_pos, e) + Vector((0.0, 0.0, 0.5 * math.sin(math.pi * e)))
        ang = math.radians(-450.0 * (1.0 - e))
        dd = (math.sin(ang), 0.0, math.cos(ang))
        kf = mix(k_call, k_ready, NA.ease("inout", max(0.0, min(1.0, (f - 14) / 9.0))))
        keys.append((f, staff_pose(kf, tuple(c), dd, upv=(0.0, -1.0, 0.0), gr=None, gl=None), "lin"))
    caught = staff_pose(call, tuple(catch_pos), (0.0, 0.0, 1.0), upv=(0.0, -1.0, 0.0), gr=0.0, gl=None, rt=1.0, gru=(0.0, -1.0, 0.0))
    absorb = staff_pose(mod(call, hips=(0.0, 0.1, -0.12), chest=(-2.0, -2.0, -6.0)), (-0.92, -0.2, 1.74), (0.08, 0.0, 1.0),
                        upv=(0.0, -1.0, 0.0), gr=0.0, gl=None, rt=1.0, gru=(0.0, -1.0, 0.0), elbow_r=(0.0, 0.4, -1.0))
    # la punta de abajo sale hacia afuera y arriba (por fuera del cuerpo) y la de arriba pasa por encima de la cabeza
    swing = staff_pose(mod(B, hips=(0.0, 0.06, -0.06), breath=0.8, head=(-6.0, 0.0, -6.0)), (-0.7, -0.22, 2.4), n(0.75, 0.0, 0.66),
                       upv=(0.0, -1.0, 0.0), gr=-0.12, gl=None, rt=1.0, gru=(0.0, -1.0, 0.0), elbow_r=(-0.6, 0.4, -0.6))
    swing = hand(swing, "l", (0.36, -0.34, 1.5), (0.2, -0.3, 1.0), (0.25, 1.0, 0.25), elbow=(0.7, 0.3, -0.7), shape="palm")
    present = staff_pose(mod(B, hips=(0.0, 0.04, -0.02), spine=(-3.0, 0.0, 0.0), chest=(-4.0, 0.0, 0.0), neck=(-2.0, 0.0, 0.0),
                             head=(-6.0, 0.0, 0.0), breath=1.0), (0.0, -0.18, 2.58), (1.0, 0.0, 0.0), upv=(0.0, -1.0, 0.0),
                         gr=-0.4, gl=0.4, gru=(0.0, -0.3, 1.0), glu=(0.0, -0.3, 1.0), elbow_r=(-0.9, 0.2, -0.3),
                         elbow_l=(0.9, 0.2, -0.3))
    MC.POSES["presenta el bastón 3"] = present
    hold = mod(present, breath=0.3, staff_pos=(0.0, -0.18, 2.55), head=(-5.0, 0.0, 0.0))
    # baja por delante girando a la guardia: el centro bien adelante (si no, la punta de atrás le pasaba por el hombro)
    lower = staff_pose(mod(B, hips=(0.02, 0.08, -0.12), head=(-6.0, 0.0, -10.0)), (0.04, -0.62, 1.7), n(0.75, 0.62, 0.05),
                       upv=(0.0, 0.0, 1.0), gr=-0.36, gl=0.4, elbow_r=(-0.8, 0.2, -0.6), elbow_l=(0.8, 0.4, -0.4))
    g3 = G3()
    keys += [(25, caught, "out"), (29, absorb, "out"), (38, swing, "inout"), (46, present, "inout"), (60, hold, "sine"),
             (70, lower, "inout"), (80, mod(g3, hips=(0.02, 0.07, -0.09)), "inout"), (90, g3, "sine")]
    return MC.add("PhaseStaff", 90, keys, ph=2, variant=False, lag={"head": 2.0, "neck": 1.0},
                  timing={"kind": "none", "staff_from": 12, "staff_high": True, "chain_from": "READY", "chain_to": "READY3",
                          "next_phase": 3},
                  events=[{"frame": 6, "fn": "StaffCall"}, {"frame": 12, "fn": "StaffAppear"}, {"frame": 25, "fn": "StaffCatch"},
                          {"frame": 46, "fn": "StaffPresent"}, {"frame": 80, "fn": "Guard"}],
                  notes="llama al bastón con la derecha (f6), aparece a 3.4 m a su derecha (f12: prender Master_Staff), lo "
                        "atrapa (f25), lo cruza en alto con las dos manos (f46, la frase) y toma la guardia del bastón (f80)")


# ============================================================================ registro
def define():
    thrust_p3()
    for v in MC.REACH_K:
        thrust_p3(v)
    smash_p3()
    for v in MC.REACH_K:
        smash_p3(v)
    crane_p3()
    leap_p3()
    sweep_p3()
    qi_p3()
    dash_p3()
    dash_pass_p3()
    phase_staff()
    defeat()
    meditate()
    seated_bow()
    MC.POSES["sentado 3"] = seated()
    MC.POSES["sentado inspira 3"] = seated(1.0)
