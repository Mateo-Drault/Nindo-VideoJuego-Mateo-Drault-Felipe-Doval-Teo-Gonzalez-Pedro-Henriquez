"""Brazos con muñecas posibles para los personajes del equipo: lo usa team_rig.TeamSolver en TODOS los clips.

El problema (ítem 3 de la revisión de Felipe: "muñecas y brazos doblados" en ninjas, sumo, Gorō y el abuelo). Medido
sobre lo que se exportaba (las rotaciones locales que lee Unity, no las matrices del solver), la mano quedaba doblada
contra el antebrazo 80-178° y girada sobre su eje hasta 180° en los cuatro personajes. Dos causas, ninguna del modelo
(en el reposo la mano sigue al antebrazo dentro de 6-13° y los pesos de la muñeca son los del equipo):
  1. TeamSolver.hand_frame armaba el marco (dedos, índice, palma) espejado: toda mano con 'hand_k_dir'/'hand_k_palm'
     (la libre del ninja, las dos del sumo y del abuelo, la libre de Gorō) tenía determinante -1 y, pasada a cuaternión,
     quedaba girada 180° alrededor del eje índice-meñique: la mano doblada para atrás sobre el antebrazo.
  2. la mano que sostiene el arma seguía al arma sin mirar el antebrazo: el codo iba al polo del clip y la muñeca se
     tragaba toda la diferencia (80-165° en la katana del ninja y el martillo de Gorō).

Cómo se resuelve sin cambiar lo que el clip pidió donde importa (la mano en su lugar, la hoja o el mango donde apuntan):
  * el codo gira alrededor del eje hombro-muñeca (el giro del brazo en el hombro) hasta alinear el antebrazo con la mano,
    cerca del polo del clip y del codo del cuadro anterior (sin saltos entre cuadros) y sin meterse en el cuerpo;
  * la mano que agarra un mango rueda alrededor de él y se acomoda en diagonal sobre la palma. Con la katana la hoja no
    se mueve: el hueso 'Katana' (hijo de la mano) se anima aparte y el mango gira dentro del puño; con el martillo de
    Gorō el mango es redondo y el martillo es su propio hueso;
  * el giro de la mano sobre el eje del brazo lo toma el antebrazo, dentro de la pronación y la supinación de una persona
    (PRON_MIN a PRON_MAX, medidas como la anatomía: 0 con el pulgar arriba, ver Arm.pronation): en la muñeca queda lo
    poco que la malla low poly disimula. Los cuatro modelos están en T con la palma abajo (pronados del todo), así que
    el reposo no sirve de centro;
  * la mano LIBRE que igual queda fuera de lo posible se endereza hasta el borde (los dedos apuntan un poco distinto de
    lo pedido; el chequeo lo informa). La que agarra algo nunca se endereza: si no entra, el chequeo falla.

Medidas: flexión (hacia la palma +), desvío (hacia el pulgar +) y giro de la mano respecto del antebrazo, con el reposo
del modelo como muñeca neutra. Límites anatómicos con margen: flexión 75, extensión 65, desvío radial 25, cubital 38;
'exceso' 1 = en el borde de esa elipse. El giro que queda en la muñeca después del reparto, hasta WRIST_TWIST.
"""
import math
from mathutils import Vector, Matrix, Quaternion
from nindo_anim import V, rot3, compose

FLEX, EXTEND, RADIAL, ULNAR = 75.0, 65.0, 25.0, 38.0
COMFORT = 0.55            # fracción del límite desde la que una muñeca empieza a costar caro
WRIST_TWIST = 30.0        # giro sobre el eje que puede quedar en la muñeca
PRON_MIN, PRON_MAX = -85.0, 90.0   # pronación y supinación del antebrazo (°, 0 = pulgar arriba; una persona: 80 y 85-90)
FORE_SHARE = 0.85         # parte del giro de la mano que toma el antebrazo
SWIVEL = 120.0            # cuánto puede girar el codo respecto del polo pedido
# libertades de una mano que agarra un mango (grados): rodar alrededor del mango (cualquier vuelta, con un costo que crece
# desde el agarre pedido: 'soft') y la diagonal sobre la palma. El filo de la katana sigue al agarre pedido mientras la
# muñeca dé; en una pose imposible (la hoja paralela al antebrazo) gira el filo antes que quebrar la muñeca
KATANA_ROLL, KATANA_SOFT, KATANA_DIAG = 180.0, 45.0, 20.0
CLUB_ROLL, CLUB_SOFT, CLUB_DIAG = 180.0, 90.0, 35.0
# hasta dónde se endereza la muñeca que lleva el arma (y el arma con ella): la katana hasta el borde; el martillo de Gorō
# ES el aviso (cada golpe lo lleva a otro lugar de la silueta) y su mano es enorme: solo lo que pasa de 1.3 veces el borde
KATANA_BEND, CLUB_BEND = 0.99, 1.0
# la mano libre se endereza hasta el 85 % del borde: muchas palmas de los clips se pidieron cuando la mano salía doblada (no
# se podía ver qué pedían) y, llevadas justo al límite, las manos se veían forzadas en los primeros planos
FREE_BEND = 0.85
# costo de correr el arma: por cada 10 cm que se corre la punta (o la cabeza del martillo) de lo pedido, al cuadrado
BEND_COST = 1.5
# cuánto más barata (en unidades de ArmSolver.cost) tiene que ser la solución sin historia para dejar el valle del cuadro
# anterior: menos y el codo salta entre dos soluciones parecidas; más y queda en una mala cuando la pose ya cambió
HYSTERESIS = 1.0
# camino de un clip entero (ArmSolver.plan_path): cuánto cuesta que el codo, la pronación o el agarre cambien de un cuadro al
# otro más de lo que giró la mano pedida (grados -> unidades de cost: un salto de 100° cuesta ~44, 10° de más por cuadro 0.4)
TRANS_SCALE = 15.0
# un cambio de solución de más de RAMP_JUMP grados (más de lo que giró la mano pedida) entre dos cuadros se reparte en
# rampas de estos largos (cuadros a cada lado del salto; ver plan_path)
RAMP_JUMP = 25.0
RAMPS = (2, 3, 4, 6)
# cuánto se ve la pronación al medir saltos (un antebrazo low poly casi cilíndrico que gira sobre su eje se nota menos
# que el codo o la mano)
VIS_FORE = 0.6
MAX_CANDS = 6


def twist_deg(q):
    """Ángulo (°, -180..180) del giro de un cuaternión alrededor de su eje Y local (descomposición giro/columpio)."""
    a = 2.0 * math.degrees(math.atan2(q.y, q.w))
    return (a + 180.0) % 360.0 - 180.0


def excess(flex, dev):
    """Muñeca respecto de su límite elíptico (1 = en el borde)."""
    return math.hypot(flex / (FLEX if flex >= 0.0 else EXTEND), dev / (RADIAL if dev >= 0.0 else ULNAR))


def soft(x, cap):
    """x hasta 'cap'; después crece como un logaritmo (sigue prefiriendo lo menos malo sin perseguirlo a saltos)."""
    return x if x <= cap else cap + math.log1p(x - cap)


def _frame(y, n):
    return Matrix((y, n, y.cross(n))).transposed()


def two_bone(S, a, b, Fu0, Fl0, T, pole, reach=0.999):
    """Las mismas cuentas que nindo_anim.Pose.two_bone en una función pura (para probar muchos codos sin tocar la pose).
    S: hombro; Fu0/Fl0: giro del brazo y del antebrazo si siguieran a su padre. Devuelve (giro del brazo, giro del
    antebrazo, codo, cuánto faltó)."""
    u0, l0 = Fu0.col[1], Fl0.col[1]
    n0 = u0.cross(l0)
    if n0.length < 1e-6:
        n0 = u0.orthogonal()
    n0.normalize()
    d_vec = T - S
    d = d_vec.length
    miss = max(0.0, d - (a + b) * reach)
    d = max(abs(a - b) + 1e-4, min(d, (a + b) * reach))
    nd = d_vec.normalized() if d_vec.length > 1e-6 else u0
    cosA = max(-1.0, min(1.0, (a * a + d * d - b * b) / (2.0 * a * d)))
    sinA = math.sqrt(max(0.0, 1.0 - cosA * cosA))
    P = pole - nd * pole.dot(nd)
    if P.length < 1e-6:
        P = n0.cross(nd)
    P.normalize()
    E = S + nd * (a * cosA) + P * (a * sinA)
    Tc = S + nd * d
    u = (E - S).normalized()
    l = (Tc - E).normalized()
    nn = u.cross(l)
    if nn.length < 1e-6:
        nn = n0
    nn.normalize()
    Ru = _frame(u, nn) @ _frame(u0, n0).transposed() @ Fu0
    Rl = _frame(l, nn) @ _frame(l0, n0).transposed() @ Fl0
    return Ru, Rl, E, miss


def change_deg(a, b, qa, qb):
    """Cuánto se ve el cambio entre dos soluciones (costo, giro en el mango, diagonal, codo, pronación, ...) con las manos
    qa y qb (giro en la armadura), en grados: el codo que gira alrededor del eje del brazo y el giro de la mano se ven
    enteros; la pronación (un antebrazo low poly casi cilíndrico gira sobre su eje), a VIS_FORE. La mano se mide en el
    espacio (no por el giro en el mango): la referencia del agarre puede girar sola de un cuadro al otro."""
    dh = math.degrees(qa.rotation_difference(qb).angle)
    dh = min(dh, 360.0 - dh)
    return math.sqrt((b[3] - a[3]) ** 2 + (VIS_FORE * (b[4] - a[4])) ** 2 + dh ** 2)


def _grid(lim, step):
    if lim <= 0.0:
        return [0.0]
    n = int(lim // step)
    return [i * step for i in range(-n, n + 1)]


class Arm:
    """Medidas de reposo de un brazo: la relación antebrazo-mano neutra, la palma y el índice en el marco de la mano y
    dónde cae la cabeza de la mano en el marco del antebrazo (la articulación de la muñeca del esqueleto de juego: en el
    abuelo y en Gorō no es la cola del antebrazo, está 4.9 y 2 cm más allá)."""

    def __init__(self, ch, k):
        R = ch.rig
        d = ch.side[k]
        self.k = k
        self.clav, self.upper, self.fore, self.hand = d["clav"], d["upper"], d["fore"], d["hand"]
        self.a, self.b = R.length[self.upper], R.length[self.fore]
        Rf0, Rh0 = rot3(R.rest[self.fore]), rot3(R.rest[self.hand])
        self.rel0 = Rf0.transposed() @ Rh0
        self.rel0_t = self.rel0.transposed()
        hi = ch.hand_info[k]
        self.n = (Rh0.transposed() @ hi["M0"].col[2]).normalized()
        self.l = (Rh0.transposed() @ hi["M0"].col[1]).normalized()
        self.head_f = R.rest_inv[self.fore] @ R.rest[self.hand].translation
        self.off_f = self.head_f - Vector((0.0, self.b, 0.0))
        # el giro del antebrazo 't' (respecto de su roll de reposo llevado al plano del codo) y la pronación anatómica
        # difieren en una constante y en el signo (los dos brazos son espejo): se miden con el codo a 90° al costado del
        # cuerpo y de ahí salen los topes de 't'
        Fu0, Fl0 = rot3(R.rest[self.upper]), rot3(R.rest[self.fore])
        S = R.rest[self.upper].translation
        Ru, Rl, _, _ = two_bone(S, self.a, self.b, Fu0, Fl0, S + ch.D((0, 0, -1)) * self.a + ch.D((0, -1, 0)) * self.b,
                                ch.D((0, 1, 0)))
        a0 = self.pronation(Ru, Rl)[0]
        a1 = self.pronation(Ru, Rl @ Matrix.Rotation(math.radians(30.0), 3, 'Y'))[0]
        sg = 1.0 if ((a1 - a0 + 180.0) % 360.0 - 180.0) > 0.0 else -1.0
        self.t_lo, self.t_hi = sorted(((PRON_MIN - a0) * sg, (PRON_MAX - a0) * sg))
        self.t_mid = -a0 * sg

    def angles(self, Rf, Rh):
        """(flexión, desvío, giro) de la mano respecto del antebrazo, en grados (0 = como en el reposo)."""
        D = (Rf @ self.rel0).transposed() @ Rh
        y = D.col[1]
        flex = math.degrees(math.atan2(y.dot(self.n), y.y))
        dev = math.degrees(math.atan2(y.dot(self.l), y.y))
        return flex, dev, twist_deg(D.to_quaternion())

    def pronation(self, Ru, Rf):
        """Pronación anatómica del antebrazo (°): 0 con el pulgar arriba (la palma hacia el cuerpo, en el plano del
        codo), +90 la palma hacia arriba (supinación), -90 hacia abajo (pronación). Se mide con la palma de la mano
        neutra sobre ese antebrazo contra el plano del codo, que solo existe con el codo doblado: devuelve también
        cuánto vale la medida (0 con el brazo derecho, donde el giro del hombro hace lo mismo; 1 desde 30° de codo)."""
        u, l = Ru.col[1], Rf.col[1]
        nn = u.cross(l)
        s = nn.length
        w = max(0.0, min(1.0, (s - 0.17) / 0.33))
        if s < 1e-6:
            return 0.0, 0.0
        nn /= s
        medial = -nn if self.k == "r" else nn
        up = -(u - l * u.dot(l)).normalized()
        palm = Rf @ self.rel0 @ self.n
        return math.degrees(math.atan2(palm.dot(up), palm.dot(medial))), w * w * (3.0 - 2.0 * w)

    def share(self, Rf, Rh, t_ref=None):
        """Antebrazo girado sobre su eje para tomar su parte del giro de la mano: (antebrazo, grados que giró). Con
        't_ref' (el giro del cuadro anterior) el pedido se desenrolla hacia él: una mano que pide más de media vuelta pasa
        de +180 a -180 y, sin esto, el antebrazo daba media vuelta en un cuadro para seguirla."""
        _, _, tw = self.angles(Rf, Rh)
        if t_ref is not None:
            tw += 360.0 * round((t_ref / FORE_SHARE - tw) / 360.0)
        t = max(self.t_lo, min(self.t_hi, FORE_SHARE * tw))
        return Rf @ Matrix.Rotation(math.radians(t), 3, 'Y'), t


class ArmSolver:
    """Brazo y mano de cada cuadro con la muñeca más cómoda. Recuerda el codo y el agarre del cuadro anterior por lado
    (reset() al empezar un clip). 'rows' junta lo medido de cada cuadro para el chequeo del clip.

    Un clip se hornea en dos pasadas (team_rig.bake): la primera ('collect') junta en cada cuadro los fondos de valle
    distintos del costo (codo arriba o abajo, pronación o supinación, el puño rodado en el mango) y plan_path elige el
    camino más barato del clip entero, sumando el costo de cada cuadro y el de cambiar de un cuadro al otro más de lo
    que giró la mano pedida (en un loop, el camino cierra sobre sí mismo); la segunda ('replay') aplica ese camino.
    Así el brazo cambia de solución (si tiene que hacerlo) donde menos se nota en vez de saltar en el cuadro en que la
    otra pasó a ser apenas mejor, y no se arrastra detrás de la pose: con el tirón hacia el cuadro anterior que había
    antes, en las pausas del aviso el codo seguía acomodándose y la punta del arma se movía 4 m/s con la pose quieta.
    Un cuadro suelto ('free', fuera de bake) usa la mejor solución sin historia y, con un cuadro anterior, se queda en
    su valle salvo que la otra sea más barata por HYSTERESIS."""

    def __init__(self, ch, solver):
        self.ch, self.solver = ch, solver
        self.rig = ch.rig
        self.arms = {k: Arm(ch, k) for k in "rl"}
        self.body_r = body_radius(ch)
        self.reset()

    def reset(self):
        self.prev = {}
        self.elbow = {}
        self.req_tw = {}
        self.rows = {"r": [], "l": []}
        self.mode = "free"
        self.cands, self.reqs = {"r": [], "l": []}, {"r": [], "l": []}
        self.evals = {"r": [], "l": []}
        self.index = {"r": 0, "l": 0}
        self.plan = {}

    def begin(self, mode):
        """Pasada nueva: 'collect', 'replay' (con el camino de plan_path) o 'free' (ver la clase)."""
        plan = self.plan
        self.reset()
        self.mode = mode
        if mode == "replay":
            self.plan = plan

    # ------------------------------------------------------------------ piezas
    def target(self, arm, H, Rf):
        """Dónde tiene que quedar la cola del antebrazo para que la cabeza de la mano caiga en H con el antebrazo Rf."""
        return H.translation - Rf @ arm.off_f

    @staticmethod
    def turn(H, hold, r, g):
        """La mano H girada 'r' grados alrededor del mango y 'g' en diagonal (alrededor de la normal de la palma), las dos
        por el punto de agarre."""
        if hold is None or (abs(r) < 1e-9 and abs(g) < 1e-9):
            return H.copy()
        piv = hold["pivot"]
        Q = Matrix.Rotation(math.radians(r), 3, hold["axis"])
        if abs(g) > 1e-9:
            Q = Matrix.Rotation(math.radians(g), 3, (rot3(H) @ hold["palm"]).normalized()) @ Q
        return compose(piv + Q @ (H.translation - piv), Q @ rot3(H))

    def body_cost(self, pose, E):
        """El codo no se mete en el tronco: distancia al eje cadera-cabeza contra el radio medido del cuerpo."""
        r = self.body_r
        if r <= 0.0:
            return 0.0
        sp = self.ch.spec
        a, b = pose.head(sp["pelvis"]), pose.head(sp["head"])
        ab = b - a
        t = max(0.0, min(1.0, (E - a).dot(ab) / max(ab.length_squared, 1e-12)))
        dd = (a + ab * t - E).length
        return 0.0 if dd >= r else 40.0 * (1.0 - dd / r) ** 2

    def cost(self, pose, arm, S, Fu0, Fl0, Hc, pole, nd, th, r, g, hold, t_ref=None, t_fix=None):
        """Lo que cuesta un codo (th) y un agarre (r, g): la muñeca respecto de su límite, el giro que queda en ella y el
        del antebrazo, lo que se aparta del polo y del agarre pedidos y el codo en el cuerpo. Devuelve (costo, pronación).
        t_fix: la pronación dada (un puente entre dos soluciones, ver candidates) en vez de la que reparte 'share'."""
        Rh = rot3(Hc)
        T = self.target(arm, Hc, Rh @ arm.rel0_t)
        p = Quaternion(nd, math.radians(th)) @ pole
        Ru, Rl, E, miss = two_bone(S, arm.a, arm.b, Fu0, Fl0, T, p)
        if t_fix is None:
            Rf, t = arm.share(Rl, Rh, t_ref)
        else:
            Rf, t = Rl @ Matrix.Rotation(math.radians(t_fix), 3, 'Y'), t_fix
        flex, dev, tw = arm.angles(Rf, Rh)
        # La muñeca dentro de su límite cuesta según lo cerca que está del borde. Lo que no entra depende de la mano: una
        # libre se endereza después (cuesta lo que se aparta de lo pedido, en grados: que el codo vaya a donde la mano
        # pedida entra, pero sin perseguir a saltos una pose imposible), la de la katana y la del martillo también pero
        # llevándose el arma (el aviso del golpe: caro) y, el martillo, recién pasado 'bend_to' (antes la muñeca se
        # fuerza), y la que agarra un mango sin poder enderezarse (la otra mano del arma) se fuerza (muy caro, con tope).
        free = hold is None
        ex = excess(flex, dev)
        sw = math.hypot(flex, dev)
        b = FREE_BEND if free else (hold.get("bend_to", 0.99) if hold.get("bend") else None)
        e1 = min(ex, 1.0)
        c = e1 * e1 + 10.0 * max(0.0, e1 - COMFORT) ** 2 + 0.5 * (min(abs(tw), WRIST_TWIST) / WRIST_TWIST) ** 2
        if b is None:
            c += 25.0 * max(0.0, soft(ex, 1.6) - 1.0) ** 2 + 6.0 * max(0.0, soft(abs(tw) / WRIST_TWIST, 3.0) - 1.0) ** 2
        else:
            c += 25.0 * max(0.0, min(ex, b) - 1.0) ** 2
            over = sw * (1.0 - b / ex) if ex > b else 0.0
            tov = max(0.0, abs(tw) - WRIST_TWIST * b)
            ov = math.hypot(over, tov)
            if free:
                c += 3.0 * (ov / 45.0) ** 2
            else:
                # el arma corrida es el aviso que miente y cuesta por lo que se corre la punta o la cabeza: 10° de la
                # katana (17 cm) cuestan como dos muñecas en el borde y los mismos 10° del martillo de Gorō (la cabeza,
                # 24 cm) el doble. Con un costo en grados igual para las dos, el martillo aterrizaba corrido 40 cm
                # una mano que afloja el mango para cambiar de agarre ('loose', ver TeamSolver.solve) se aparta de lo pedido
                # sin llevarse el arma: cuesta poco, como el puño que gira sobre el palo
                lo = hold.get("loose", 0.0)
                c += (1.0 - lo) ** 2 * BEND_COST * (1.0 + 3.0 * hold.get("look", 0.0)) * (math.radians(ov) * hold.get("reach", 1.0) / 0.1) ** 2
                c += lo * (ov / 90.0) ** 2
        # el codo pedido es lo que más se ve desde arriba: una mano libre no lo saca de lugar por una palma que igual no
        # entra; una que agarra un mango sí puede (la muñeca no tiene otra salida)
        c += 0.25 * ((t - arm.t_mid) / (0.5 * (PRON_MAX - PRON_MIN))) ** 2 + (2.0 if free else 0.6) * (th / 60.0) ** 2 + self.body_cost(pose, E)
        if hold is not None:
            c += 0.35 * (r / hold["soft"]) ** 2 + 0.35 * (g / max(1.0, hold["diag"] or 1.0)) ** 2
        return c, t

    def steady_pole(self, k, pole, nd, Fu0):
        """El polo pedido casi paralelo al eje hombro-muñeca no dice para qué lado va el codo (la mano justo en la línea
        del polo: el sumo con el brazo abierto al costado, el ninja volviendo a la guardia) y, de un cuadro al otro, el
        codo daba media vuelta. Ahí se mezcla con hacia dónde estaba el codo en el cuadro anterior."""
        p = pole - nd * pole.dot(nd)
        L = p.length
        if L >= 0.4:
            return pole
        fb = self.elbow.get(k)
        if fb is None:
            fb = Fu0.col[2]
        fb = fb - nd * fb.dot(nd)
        if fb.length < 1e-6:
            return pole
        u = (0.4 - L) / 0.4
        u = u * u * (3.0 - 2.0 * u)
        q = (p.normalized() if L > 1e-6 else fb.normalized()) * (1.0 - u) + fb.normalized() * u
        return q.normalized() if q.length > 1e-6 else fb.normalized()

    def swivel_seed(self, arm, Hc, pole, nd):
        """Giro del codo (°, respecto del polo) que deja el antebrazo más alineado con la mano neutra: en el círculo del
        codo, el que minimiza la proyección del codo sobre la dirección deseada del antebrazo."""
        f = (rot3(Hc) @ arm.rel0_t).col[1]
        P0 = pole - nd * pole.dot(nd)
        if P0.length < 1e-6:
            return 0.0
        P0.normalize()
        Q0 = nd.cross(P0)
        return math.degrees(math.atan2(-f.dot(Q0), -f.dot(P0)))

    def plausible(self, arm, k, S, Fu0, Fl0, H, pole):
        """Mano LIBRE pedida fuera de lo posible: se la acerca a la neutra del brazo hacia el polo pedido antes de buscar
        el codo, con el giro sobre el brazo hasta lo que dan antebrazo y muñeca juntos y la flexión y el
        desvío hasta FREE_BEND del borde. Una mano pedida al revés (muchas palmas de los clips se autoraron cuando la mano
        salía espejada) tiene dos soluciones igual de malas, codo arriba o abajo; sin esto el codo saltaba entre las dos
        de un cuadro al otro. El giro que pasa de 180 sigue para el lado del cuadro anterior (sin la vuelta de golpe)."""
        T = self.target(arm, H, rot3(H) @ arm.rel0_t)
        _, Rl, _, _ = two_bone(S, arm.a, arm.b, Fu0, Fl0, T, pole)
        N = Rl @ arm.rel0
        Rh = rot3(H)
        D = (N.transposed() @ Rh).to_quaternion()
        tw = twist_deg(D)
        twist = Quaternion((0.0, 1.0, 0.0), math.radians(tw))
        swing = D @ twist.inverted()
        prev = self.req_tw.get(k)
        if prev is not None and abs(tw - prev) > 180.0:
            tw -= math.copysign(360.0, tw - prev)
        tw_c = max(arm.t_lo - WRIST_TWIST * FREE_BEND, min(arm.t_hi + WRIST_TWIST * FREE_BEND, tw))
        self.req_tw[k] = tw
        twist_c = Quaternion((0.0, 1.0, 0.0), math.radians(tw_c))
        sw_m = N @ swing.to_matrix()
        flex, dev, _ = arm.angles(Rl, sw_m)
        if excess(flex, dev) > FREE_BEND:
            lo, hi = 0.0, 1.0
            for _ in range(16):
                m = 0.5 * (lo + hi)
                f2, d2, _ = arm.angles(Rl, N @ Quaternion().slerp(swing, m).to_matrix())
                if excess(f2, d2) <= FREE_BEND:
                    lo = m
                else:
                    hi = m
            swing = Quaternion().slerp(swing, lo)
        return compose(H.translation, N @ (swing @ twist_c).to_matrix())

    # ------------------------------------------------------------------ búsqueda
    def evaluator(self, pose, arm, S, Fu0, Fl0, H, pole, hold, t_ref):
        """f(th, r, g) -> (costo, pronación) con memoria, para la búsqueda global y la local."""
        memo = {}
        frames = {}

        def frame(r, g):
            key = (round(r, 4), round(g, 4))
            if key not in frames:
                Hc = self.turn(H, hold, r, g)
                T = self.target(arm, Hc, rot3(Hc) @ arm.rel0_t)
                nd = T - S
                nd = nd.normalized() if nd.length > 1e-6 else Fu0.col[1]
                frames[key] = (Hc, nd)
            return frames[key]

        def f(th, r, g):
            th = max(-SWIVEL, min(SWIVEL, th))
            key = (round(th, 4), round(r, 4), round(g, 4))
            if key not in memo:
                Hc, nd = frame(r, g)
                memo[key] = self.cost(pose, arm, S, Fu0, Fl0, Hc, pole, nd, th, r, g, hold, t_ref)
            return memo[key]

        def seed(r, g):
            Hc, nd = frame(r, g)
            return self.swivel_seed(arm, Hc, pole, nd)

        def hand(r, g):
            return frame(r, g)[0].to_quaternion()

        def fixed(th, r, g, t):
            Hc, nd = frame(r, g)
            return self.cost(pose, arm, S, Fu0, Fl0, Hc, pole, nd, max(-SWIVEL, min(SWIVEL, th)), r, g, hold, t_fix=t)[0]
        f.seed = seed
        f.fixed = fixed
        f.hand = hand
        return f

    def best_elbow(self, f, r, g, starts):
        """El mejor codo para un agarre (r, g): los puntos de partida y después pasos cada vez más finos."""
        best = None
        for th in starts:
            th = max(-SWIVEL, min(SWIVEL, th))
            c, t = f(th, r, g)
            if best is None or c < best[0]:
                best = (c, th, t)
        for step in (8.0, 3.0, 1.0):
            for sg in (-step, step):
                th = max(-SWIVEL, min(SWIVEL, best[1] + sg))
                c, t = f(th, r, g)
                if c < best[0]:
                    best = (c, th, t)
        return best

    def search(self, f, hold):
        """La mejor solución de la pose sin historia: (costo, giro en el mango, diagonal, codo, pronación)."""
        coarse = [-90.0, -60.0, -30.0, 0.0, 30.0, 60.0, 90.0]
        if hold is None:
            cands = [(0.0, 0.0)]
        else:
            # una vuelta entera es la misma mano: -180 sobra
            cands = [(r, g) for r in _grid(hold["roll"], 30.0) for g in _grid(hold["diag"], 10.0) if r > -180.0]
        best = None
        for r, g in cands:
            c, th, t = self.best_elbow(f, r, g, coarse + [round(f.seed(r, g), 1)])
            if best is None or c < best[0]:
                best = (c, r, g, th, t)
        if hold is not None:
            for step in (12.0, 5.0, 2.0):
                _, r0, g0, t0, _ = best
                for dr, dg in ((step, 0), (-step, 0), (0, step), (0, -step)):
                    r, g = self.clamp_hold(hold, r0 + dr, g0 + dg)
                    if r is None:
                        continue
                    c, th, t = self.best_elbow(f, r, g, [t0])
                    if c < best[0]:
                        best = (c, r, g, th, t)
        return best

    @staticmethod
    def clamp_hold(hold, r, g):
        """(r, g) dentro de las libertades del agarre, o (None, None) si se sale."""
        if abs(g) > hold["diag"] + 1e-6:
            return None, None
        if hold["roll"] >= 180.0:
            r = (r + 180.0) % 360.0 - 180.0
        elif abs(r) > hold["roll"] + 1e-6:
            return None, None
        return r, g

    def descend(self, f, start, hold):
        """Desde 'start' (codo, giro, diagonal) hasta el fondo de su valle, de a pasos cada vez más finos:
        (costo, giro, diagonal, codo, pronación)."""
        th, r, g = start
        if hold is not None:
            r, g = self.clamp_hold(hold, r, g)
            if r is None:
                th, r, g = start[0], 0.0, 0.0
        else:
            r = g = 0.0
        c, t = f(th, r, g)
        for s_th, s_rg in ((8.0, 12.0), (3.0, 5.0), (1.0, 2.0)):
            moves = [(s_th, 0.0, 0.0), (-s_th, 0.0, 0.0)]
            if hold is not None:
                moves += [(0.0, s_rg, 0.0), (0.0, -s_rg, 0.0), (0.0, 0.0, s_rg), (0.0, 0.0, -s_rg)]
            for _ in range(40):
                better = None
                for dth, dr, dg in moves:
                    th2 = max(-SWIVEL, min(SWIVEL, th + dth))
                    r2, g2 = (self.clamp_hold(hold, r + dr, g + dg) if hold is not None else (0.0, 0.0))
                    if r2 is None:
                        continue
                    c2, t2 = f(th2, r2, g2)
                    if c2 < c - 1e-9 and (better is None or c2 < better[0]):
                        better = (c2, th2, r2, g2, t2)
                if better is None:
                    break
                c, th, r, g, t = better
        return c, r, g, th, t

    @staticmethod
    def same(a, b):
        """Dos soluciones (costo, giro, diagonal, codo, pronación, ...) que son la misma (el mismo valle)."""
        return (abs(a[3] - b[3]) < 6.0 and abs(a[4] - b[4]) < 8.0 and abs((a[1] - b[1] + 180.0) % 360.0 - 180.0) < 10.0
                and abs(a[2] - b[2]) < 6.0)

    def candidates(self, pose, arm, S, Fu0, Fl0, H, pole, hold, canon):
        """Los fondos de valle distintos de la pose, de las semillas de codo y agarre y de los dos desenrollados del giro
        (pronación o supinación): [(costo, giro, diagonal, codo, pronación, t_ref)], los MAX_CANDS más baratos."""
        out = [tuple(canon) + (None,)]
        seeds_r = (0.0,) if hold is None else (-120.0, 0.0, 120.0)
        for t_ref in (None, arm.t_hi, arm.t_lo):
            f = self.evaluator(pose, arm, S, Fu0, Fl0, H, pole, hold, t_ref)
            for th in (-90.0, -30.0, 30.0, 90.0):
                for r in seeds_r:
                    cand = self.descend(f, (th, r, 0.0), hold) + (t_ref,)
                    if not any(self.same(cand, o) for o in out):
                        out.append(cand)
        out.sort(key=lambda c: c[0])
        out = out[:MAX_CANDS]
        # puentes: estados entre cada par de soluciones (codo, agarre y pronación interpolados, la pronación dada). Con
        # solo los fondos de valle, cuando el camino tiene que pasar de una solución a la otra (la mano que va al mango
        # desde la guardia: el antebrazo de pronación a supinación) lo hacía en un cuadro; con los puentes el camino puede
        # repartir el cambio en tres o cuatro cuadros, pagando la muñeca un poco peor en el medio
        f = self.evaluator(pose, arm, S, Fu0, Fl0, H, pole, hold, None)
        bridges = []
        for i in range(len(out)):
            for j in range(i + 1, len(out)):
                a, b = out[i], out[j]
                dr = (b[1] - a[1] + 180.0) % 360.0 - 180.0
                for u in (0.25, 0.5, 0.75):
                    th, r, g, t = a[3] + (b[3] - a[3]) * u, a[1] + dr * u, a[2] + (b[2] - a[2]) * u, a[4] + (b[4] - a[4]) * u
                    if hold is not None:
                        r, g = self.clamp_hold(hold, r, g)
                        if r is None:
                            continue
                    bridges.append((f.fixed(th, r, g, t), r, g, th, t, None, True))
        return out + bridges

    def plan_path(self, loop):
        """El camino más barato por los candidatos de cada cuadro (Viterbi): el costo de cada uno más el de pasar de un
        cuadro al otro (TRANS_SCALE). En un loop el último cuadro vuelve al primero: se prueba cada arranque.
        Donde el camino igual salta (un valle que desaparece de un cuadro al otro: el martillo de Gorō volviendo del
        piso a la guardia en cinco cuadros), se le ofrecen estados intermedios entre las dos soluciones en los cuadros
        de alrededor (rampas de 2 a 6 cuadros) y se vuelve a buscar: el cambio se reparte donde la muñeca lo tolera."""
        self.plan = {}
        for k, frames in self.cands.items():
            if not frames:
                continue
            reqs = self.reqs[k]
            n = len(frames)
            frames = [list(c) for c in frames]

            def asked_deg(i):
                a = math.degrees(reqs[i - 1].rotation_difference(reqs[i % n]).angle)
                return min(a, 360.0 - a)

            ev = self.evals[k]
            hq = {}

            def hand(i, a):
                key = (i, round(a[1], 3), round(a[2], 3))
                if key not in hq:
                    hq[key] = ev[i][0].hand(a[1], a[2])
                return hq[key]

            def moved(i, a, b):
                """Lo que se ve cambiar de a (cuadro i-1) a b (cuadro i) más allá de lo que se movió lo pedido."""
                return change_deg(a, b, hand((i - 1) % n, a), hand(i % n, b)) - asked_deg(i)

            def trans(i, a, b):
                return (max(0.0, moved(i, a, b)) / TRANS_SCALE) ** 2

            def viterbi(first, tm):
                acc = [[(c[0], None) if (first is None or j == first) else (float("inf"), None) for j, c in enumerate(frames[0])]]
                for i in range(1, n):
                    row = []
                    for j, b in enumerate(frames[i]):
                        c, q = min(((acc[i - 1][q][0] + tm[i][j][q], q) for q in range(len(frames[i - 1]))), key=lambda x: x[0])
                        row.append((c + b[0], q))
                    acc.append(row)
                return acc

            def solve():
                # las transiciones se calculan una vez (en un loop, Viterbi corre una vez por cada arranque)
                tm = [None] + [[[trans(i, a, b) for a in frames[i - 1]] for b in frames[i]] for i in range(1, n)]
                best = None
                for s0 in (range(len(frames[0])) if loop else [None]):
                    acc = viterbi(s0, tm)
                    for j, (c, _) in enumerate(acc[-1]):
                        if loop:
                            c += trans(n, frames[n - 1][j], frames[0][s0])
                        if best is None or c < best[0]:
                            best = (c, j, acc)
                _, j, acc = best
                path = [None] * n
                for i in range(n - 1, -1, -1):
                    path[i] = frames[i][j]
                    j = acc[i][j][1]
                return path

            path = solve()
            for _ in range(2):
                jumps = [i for i in range(1, n) if moved(i, path[i - 1], path[i]) > RAMP_JUMP]
                if not jumps:
                    break
                for i in jumps:
                    self.add_ramps(k, frames, path[i - 1], path[i], i, loop)
                path = solve()
            self.plan[k] = path

    def add_ramps(self, k, frames, a, b, i, loop):
        """Estados entre la solución 'a' (antes del salto en el cuadro i) y 'b' (después), evaluados con la pose de cada
        cuadro de alrededor (la pronación dada, como los puentes de candidates): rampas suaves de RAMPS cuadros que
        terminan en i, y algunos pasos sueltos en cada cuadro de la ventana para que el camino arme la suya."""
        n = len(frames)
        dr = (b[1] - a[1] + 180.0) % 360.0 - 180.0
        want = {}
        for w in RAMPS:
            for s in range(-w, w):
                u = (s + w + 0.5) / (2 * w)
                want.setdefault(i + s, set()).add(round(u * u * (3.0 - 2.0 * u), 3))
        for j in range(i - RAMPS[-1], i + RAMPS[-1]):
            want.setdefault(j, set()).update((0.2, 0.4, 0.6, 0.8))
        for j, us in want.items():
            if not loop and not (0 <= j < n):
                continue
            jj = j % n
            f, hold = self.evals[k][jj]
            for u in sorted(us):
                th, r, g, t = a[3] + (b[3] - a[3]) * u, a[1] + dr * u, a[2] + (b[2] - a[2]) * u, a[4] + (b[4] - a[4]) * u
                if hold is not None:
                    r, g = self.clamp_hold(hold, r, g)
                    if r is None:
                        continue
                frames[jj].append((f.fixed(th, r, g, t), r, g, th, t, None, True))

    # ------------------------------------------------------------------ un brazo
    def place(self, pose, k, H, pole, hold=None):
        """Ubica clavícula, brazo y antebrazo para la mano H (matriz de la armadura) y devuelve (falta, mano final, mano
        antes de enderezarla). hold = None (mano libre: se endereza si no entra) o dict(axis, pivot, palm, roll, soft, diag,
        bend, bend_to) de un agarre; con 'bend' (la katana, el martillo) también se endereza hasta 'bend_to' y el arma la
        sigue: el que llama lleva el arma con el mismo giro (mano final @ inversa de la de antes)."""
        arm = self.arms[k]
        R = self.rig
        sv = self.solver
        prev = self.prev.get(k)
        free = hold is None
        bend = free or bool(hold.get("bend"))
        pole = V(pole).normalized()
        sv.reach_with_clavicle(pose, k, self.target(arm, H, rot3(H) @ arm.rel0_t))
        Pc = pose.get(arm.clav) @ R.rel[arm.upper]
        S, Fu0 = Pc.translation.copy(), rot3(Pc)
        Fl0 = Fu0 @ rot3(R.rel[arm.fore])
        nd0 = self.target(arm, H, rot3(H) @ arm.rel0_t) - S
        if nd0.length > 1e-6:
            pole = self.steady_pole(k, pole, nd0.normalized(), Fu0)
        if free:
            H = self.plausible(arm, k, S, Fu0, Fl0, H, pole)
        # la del camino del clip o, suelta, la mejor sin historia y el valle del cuadro anterior (ver la clase).
        # La pronación del cuadro anterior solo desenrolla el giro pedido del que se queda (una mano que pasa la media
        # vuelta sigue para el mismo lado); la otra se evalúa con el suyo: desenrollada hacia el cuadro anterior, una
        # solución de otro valle salía carísima y el brazo se quedaba en uno malo (el desvío del ninja: el arma corrida 17°)
        i = self.index[k]
        self.index[k] += 1
        t_ref = None
        t_fix = None
        if self.mode == "replay" and self.plan.get(k):
            path = self.plan[k]
            # el estado del camino se aplica tal cual, con su pronación: volver a bajar al valle desde ahí desenrollaba el
            # giro hacia la referencia con que se encontró el candidato y no hacia el suyo (Gorō al desplomarse: el
            # antebrazo daba media vuelta en el cuadro en que el camino no la daba)
            st = path[i % len(path)]
            best, t_fix = st[:5], st[4]
        else:
            best = self.search(self.evaluator(pose, arm, S, Fu0, Fl0, H, pole, hold, None), hold)
            if self.mode == "collect":
                self.cands[k].append(self.candidates(pose, arm, S, Fu0, Fl0, H, pole, hold, best))
                self.reqs[k].append(self.asked_frame(H, hold))
                # para las rampas de plan_path: el costo de un estado cualquiera con la pose de este cuadro
                self.evals[k].append((self.evaluator(pose, arm, S, Fu0, Fl0, H, pole, hold, None), hold))
            elif prev is not None:
                stay = self.descend(self.evaluator(pose, arm, S, Fu0, Fl0, H, pole, hold, prev[3]), prev[:3], hold)
                if stay[0] <= best[0] + HYSTERESIS:
                    best, t_ref = stay, prev[3]
        c, r, g, th, _ = best
        # ---- se aplica lo elegido
        Hc = self.turn(H, hold, r, g)
        Rh = rot3(Hc)
        Rf_guess = Rh @ arm.rel0_t
        for _ in range(2):
            T = self.target(arm, Hc, Rf_guess)
            nd = (T - S).normalized() if (T - S).length > 1e-6 else Fu0.col[1]
            p = Quaternion(nd, math.radians(th)) @ pole
            miss = pose.two_bone(arm.upper, arm.fore, T, p)
            if t_fix is None:
                Rf, t = arm.share(rot3(pose.W[arm.fore]), Rh, t_ref)
            else:
                Rf, t = rot3(pose.W[arm.fore]) @ Matrix.Rotation(math.radians(t_fix), 3, 'Y'), t_fix
            Rf_guess = Rf
        pose.place(arm.fore, compose(pose.W[arm.fore].translation, Rf))
        self.prev[k] = (th, r, g, t)
        self.elbow[k] = (pose.W[arm.fore].translation - S).normalized()
        clamp = 0.0
        if bend:
            Rh2 = self.straighten(arm, Rf, Rh, FREE_BEND if free else hold.get("bend_to", 0.99))
            a = math.degrees(Rh.to_quaternion().rotation_difference(Rh2.to_quaternion()).angle)
            clamp = min(a, 360.0 - a)
            Rh = Rh2
        # la mano va donde la pone el antebrazo (la muñeca del esqueleto de juego): si el brazo no llegó, falta 'miss'
        head = pose.W[arm.fore] @ arm.head_f
        Hf = compose(head if miss < 1e-6 else Hc.translation, Rh)
        flex, dev, tw = arm.angles(Rf, Rh)
        pron, pw = arm.pronation(rot3(pose.W[arm.upper]), Rf)
        self.rows[k].append(dict(excess=excess(flex, dev), flex=flex, dev=dev, twist=tw, fore=t, swivel=th, roll=r, diag=g,
                                 clamp=clamp, held=not free, req=self.asked_frame(H, hold), hand=Rh.to_quaternion(), cost=c,
                                 pron=pron, pron_w=pw))
        return miss, Hf, Hc

    @staticmethod
    def asked_frame(H, hold):
        """Contra qué se miden los saltos del brazo: el giro pedido del arma si la mano la agarra, si no la mano pedida."""
        if hold is not None and hold.get("frame") is not None:
            return hold["frame"]
        return rot3(H).to_quaternion()

    def straighten(self, arm, Rf, Rh, limit=0.99):
        """Mano fuera del límite: se acerca a la neutra (conservando el giro) hasta que el exceso baja a 'limit', y el
        giro que excede lo que tolera la muñeca se quita."""
        flex, dev, tw = arm.angles(Rf, Rh)
        N = Rf @ arm.rel0
        if excess(flex, dev) > limit:
            D = (N.transposed() @ Rh).to_quaternion()
            twist = Quaternion((0.0, 1.0, 0.0), math.radians(tw))
            swing = D @ twist.inverted()
            lo, hi = 0.0, 1.0
            for _ in range(16):
                m = 0.5 * (lo + hi)
                f2, d2, _ = arm.angles(Rf, N @ (Quaternion().slerp(swing, m) @ twist).to_matrix())
                if excess(f2, d2) <= limit:
                    lo = m
                else:
                    hi = m
            Rh = N @ (Quaternion().slerp(swing, lo) @ twist).to_matrix()
            flex, dev, tw = arm.angles(Rf, Rh)
        lim = WRIST_TWIST * limit
        if abs(tw) > lim:
            Rh = Rh @ Matrix.Rotation(math.radians(-math.copysign(abs(tw) - lim, tw)), 3, 'Y')
        return Rh

    # ------------------------------------------------------------------ resumen del clip
    def summary(self):
        """Peor muñeca de lo resuelto desde el último reset, por lado."""
        out = {}
        for k, rows in self.rows.items():
            if not rows:
                continue
            out[k] = dict(excess=round(max(r["excess"] for r in rows), 2), twist=round(max(abs(r["twist"]) for r in rows), 1),
                          fore=round(max(abs(r["fore"]) for r in rows), 1), swivel=round(max(abs(r["swivel"]) for r in rows), 1),
                          roll=round(max(abs(r["roll"]) for r in rows), 1), diag=round(max(abs(r["diag"]) for r in rows), 1),
                          clamp=round(max(r["clamp"] for r in rows), 1),
                          worst_frame=max(range(len(rows)), key=lambda i: rows[i]["excess"]))
        return out


def body_radius(ch):
    """Radio del tronco para que el codo no se meta en él: la distancia horizontal típica (percentil 70) de los vértices
    que pesan en la pelvis y la columna al eje cadera-cabeza, en la pose de reposo (unidades de la armadura)."""
    import bpy
    R = ch.rig
    sp = ch.spec
    names = {sp["pelvis"]} | set(sp["spine"]) | set(sp["chest"])
    a, b = R.rest[sp["pelvis"]].translation, R.rest[sp["head"]].translation
    ab = b - a
    dg = bpy.context.evaluated_depsgraph_get()
    ds = []
    for o in ch.meshes:
        gi = {g.index for g in o.vertex_groups if g.name in names}
        if not gi:
            continue
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        M = ch.Ai @ oe.matrix_world
        for v in o.data.vertices:
            if sum(g.weight for g in v.groups if g.group in gi) < 0.8:
                continue
            p = M @ me.vertices[v.index].co
            t = max(0.0, min(1.0, (p - a).dot(ab) / max(ab.length_squared, 1e-12)))
            ds.append((a + ab * t - p).length)
        oe.to_mesh_clear()
    if not ds:
        return 0.0
    ds.sort()
    return ds[int(0.7 * (len(ds) - 1))]
