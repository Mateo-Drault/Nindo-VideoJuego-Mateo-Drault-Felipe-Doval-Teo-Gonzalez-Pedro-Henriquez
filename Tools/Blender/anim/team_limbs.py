"""Brazos con muñecas posibles para los personajes del equipo (team_rig.TeamSolver, si CHARS[...]['wrists']).

El problema (revisión de Felipe, ítem 5: "las manos de varios ninjas se ven dobladas en las muñecas"): TeamSolver
ubicaba la muñeca con IK de dos huesos hacia el polo pedido y después ponía la mano con la orientación que pedía el
clip (la de la hoja, o la dirección y la palma de la mano libre) sin mirar el antebrazo. Medido sobre los clips de
la fase B3: la muñeca del ninja quedaba doblada 90-165° y girada sobre su eje hasta 180° (la del sumo, también),
lo que la malla dibuja como una muñeca quebrada o retorcida en caramelo.

Cómo se resuelve, sin cambiar lo que el clip pidió donde importa (la mano en su lugar, la hoja apuntando a donde
apunta, el polo del codo si no molesta):
  * el codo puede girar alrededor del eje hombro-muñeca (el giro del brazo entero en el hombro): se busca el giro
    que deja la muñeca más cómoda, cerca del codo pedido y del del cuadro anterior (sin saltos entre cuadros);
  * la mano de la katana rueda alrededor de la hoja (hasta ±80°: el filo de un arma de 3 px no se ve, la hoja sí)
    prefiriendo mostrar la cara plana a la cámara alta cuando la hoja está acostada; la que agarra el mango rueda
    alrededor del mango (sigue cerrada sobre él);
  * el giro de la mano sobre el eje del brazo (pronación) se reparte: la mitad lo toma el antebrazo (hasta 55°);
  * la mano LIBRE que igual queda fuera de lo posible se endereza hasta el límite (cambia un poco hacia dónde apuntan
    los dedos; la muñeca deja de quebrarse). La que sostiene un arma nunca se endereza: si queda fuera, el chequeo
    avisa.
Límites de la muñeca (°): flexión hacia la palma 70, extensión 60, desvío hacia el pulgar 25 y hacia el meñique 38;
el giro que queda en la muñeca, hasta 60 (más se lee como caramelo en la malla low poly). Todo medido después de
repartir el giro con el antebrazo: es la diferencia entre los dos huesos lo que dobla la malla.
"""
import math
from mathutils import Vector, Matrix, Quaternion
from nindo_anim import rot3, compose

FLEX, EXTEND, RADIAL, ULNAR = 70.0, 60.0, 25.0, 38.0
COMFORT = 0.6             # fracción del límite desde la que una muñeca empieza a costar
WRIST_TWIST = 60.0        # giro sobre el eje que se tolera en la muñeca
FORE_SHARE, FORE_MAX = 0.5, 55.0
SWIVEL = 100.0            # cuánto puede girar el codo respecto del pedido
KATANA_ROLL, GRIP_ROLL = 80.0, 60.0


def twist_angle(q, axis=1):
    """Ángulo (°, -180..180) del giro de un cuaternión alrededor del eje local (0 = X, 1 = Y, 2 = Z)."""
    c = (q.x, q.y, q.z)[axis]
    a = 2.0 * math.degrees(math.atan2(c, q.w))
    return (a + 180.0) % 360.0 - 180.0


class Limbs:
    KATANA_ROLL, GRIP_ROLL = KATANA_ROLL, GRIP_ROLL

    def __init__(self, ch):
        self.ch = ch
        R = ch.rig
        self.info = {}
        for k in "rl":
            d = ch.side[k]
            fore, hand = d["fore"], d["hand"]
            hi = ch.hand_info[k]
            Rh0 = rot3(R.rest[hand])
            self.info[k] = dict(
                rel0=rot3(R.rest[fore]).transposed() @ Rh0,          # mano respecto del antebrazo en reposo
                n=(Rh0.transposed() @ hi["M0"].col[2]).normalized(),  # palma, en el marco de la mano en reposo
                l=(Rh0.transposed() @ hi["M0"].col[1]).normalized(),  # hacia el índice (lado del pulgar)
            )
        self.up = ch.D((0.0, 0.0, 1.0))
        if ch.weapon_info and ch.weapon_info["kind"] == "katana":
            self.set_weapon_frame(ch.weapon_info["K"])
        self.prev = {}
        self.report = {"r": [], "l": []}

    def reset(self):
        """Clip nuevo: sin el codo del cuadro anterior ni lo medido."""
        self.prev = {}
        self.report = {"r": [], "l": []}

    # ------------------------------------------------------------------ medidas
    def angles(self, k, Rf, Rh):
        """(flexión, desvío, giro) de la mano respecto del antebrazo, en grados (0 = como en el reposo)."""
        i = self.info[k]
        D = (Rf @ i["rel0"]).transposed() @ Rh
        s = D.col[1]
        flex = math.degrees(math.atan2(s.dot(i["n"]), s.y))
        dev = math.degrees(math.atan2(s.dot(i["l"]), s.y))
        return flex, dev, twist_angle(D.to_quaternion())

    @staticmethod
    def excess(flex, dev):
        """Muñeca respecto de su límite elíptico (1 = en el límite)."""
        return math.hypot(flex / (FLEX if flex >= 0 else EXTEND), dev / (RADIAL if dev >= 0 else ULNAR))

    def fore_share(self, k, Rf, Rh):
        """Grados que gira el antebrazo sobre su eje para tomar su parte del giro de la mano."""
        _, _, tw = self.angles(k, Rf, Rh)
        return max(-FORE_MAX, min(FORE_MAX, FORE_SHARE * tw))

    @staticmethod
    def twisted(Rf, a):
        return Rf @ Matrix.Rotation(math.radians(a), 3, 'Y')

    def wrist(self, k, Rf, Rh):
        """(exceso, giro que queda en la muñeca, giro del antebrazo) con el reparto ya hecho."""
        a = self.fore_share(k, Rf, Rh)
        flex, dev, tw = self.angles(k, self.twisted(Rf, a), Rh)
        return self.excess(flex, dev), tw, a

    def cost(self, k, Rf, Rh):
        e, tw, _ = self.wrist(k, Rf, Rh)
        return 6.0 * max(0.0, e - COMFORT) ** 2 + 0.5 * e * e + 3.0 * max(0.0, (abs(tw) - WRIST_TWIST * 0.6) / 40.0) ** 2

    # ------------------------------------------------------------------ brazo
    def _arm(self, pose, solver, k, H, pole, phi):
        """Ubica clavícula, brazo y antebrazo para la mano H con el codo girado 'phi' (°) respecto del pedido.
        Devuelve (falta, Rf). Escribe en 'pose' (el que llama guarda y restaura si solo está probando)."""
        ch = self.ch
        d = ch.side[k]
        tgt = H @ ch.hand_info[k]["fore_tail_local"]
        solver.reach_with_clavicle(pose, k, tgt)
        S = (pose.get(d["clav"]) @ ch.rig.rel[d["upper"]]).translation
        ax = tgt - S
        p = pole
        if abs(phi) > 1e-6 and ax.length > 1e-6:
            p = Quaternion(ax.normalized(), math.radians(phi)) @ pole
        miss = pose.two_bone(d["upper"], d["fore"], tgt, p)
        return miss, rot3(pose.W[d["fore"]])

    def _search(self, pose, solver, k, H, pole, span=SWIVEL):
        """Mejor giro del codo para la mano H: (costo, phi)."""
        d = self.ch.side[k]
        keep = {n: pose.W[n].copy() for n in (d["clav"], d["upper"], d["fore"]) if n in pose.W}
        prev = self.prev.get(k)
        Rh = rot3(H)

        def total(phi):
            _, Rf = self._arm(pose, solver, k, H, pole, phi)
            c = self.cost(k, Rf, Rh) + 0.35 * (phi / 55.0) ** 2
            if prev is not None:
                c += 0.6 * ((phi - prev) / 30.0) ** 2
            for n, M in keep.items():
                pose.W[n] = M.copy()
            for n in (d["upper"], d["fore"]):
                if n not in keep:
                    pose.W.pop(n, None)
            return c
        best = min((total(p), p) for p in [x * 10.0 - span for x in range(int(2 * span / 10.0) + 1)])
        for step in (3.0, 1.0):
            c0, p0 = best
            best = min([best] + [(total(p0 + s * step), p0 + s * step) for s in (-2, -1, 1, 2)])
        return best

    def roll_weapon(self, pose, solver, k, H, pivot, axis, limit, pole, show_flat=True):
        """La mano que sostiene un arma rueda alrededor de 'axis' (la hoja o el mango) por 'pivot': el ángulo que
        deja el brazo más cómodo, hasta ±limit°. Con 'show_flat', una hoja acostada prefiere mostrar su cara plana a
        la cámara alta del juego (de canto es una línea de 1 px). Devuelve la mano nueva."""
        ax = axis.normalized()
        flat_w = (1.0 - ax.dot(self.up) ** 2) if show_flat else 0.0
        best = None
        for r in [x * 10.0 - limit for x in range(int(2 * limit / 10.0) + 1)]:
            c = self._roll_cost(pose, solver, k, H, pivot, ax, r, limit, pole, flat_w)
            if best is None or c < best[0]:
                best = (c, r)
        for step in (5.0, 2.0):
            c0, r0 = best
            best = min([best] + [(self._roll_cost(pose, solver, k, H, pivot, ax, r0 + s, limit, pole, flat_w), r0 + s)
                                 for s in (-step, step) if abs(r0 + s) <= limit])
        return self._rolled(H, pivot, ax, best[1])

    def _roll_cost(self, pose, solver, k, H, pivot, ax, r, limit, pole, flat_w):
        Hr = self._rolled(H, pivot, ax, r)
        c, _ = self._search(pose, solver, k, Hr, pole, span=70.0)
        c += 0.3 * (r / max(1.0, limit)) ** 2
        if flat_w > 0.0:
            # normal de la cara plana: perpendicular a la hoja y al filo (el eje X del marco del arma en la mano)
            n = rot3(Hr) @ self.flat_local
            c += 0.8 * flat_w * (1.0 - abs(n.dot(self.up))) ** 2
        return c

    flat_local = Vector((1.0, 0.0, 0.0))

    def set_weapon_frame(self, K):
        """K: marco del arma en la mano (team_rig.measure_katana): la cara plana es el eje X del marco del arma."""
        self.flat_local = (K.transposed() @ Vector((1.0, 0.0, 0.0))).normalized()

    @staticmethod
    def _rolled(H, pivot, axis, deg):
        if abs(deg) < 1e-6:
            return H.copy()
        Q = Matrix.Rotation(math.radians(deg), 3, axis.normalized())
        return compose(pivot + Q @ (H.translation - pivot), Q @ rot3(H))

    def place(self, pose, solver, k, H, pole, free):
        """Brazo y mano de un cuadro: el codo con la muñeca más cómoda, el giro repartido con el antebrazo y, si la
        mano está libre y la muñeca igual queda fuera, la mano enderezada hasta el límite. Devuelve (falta, H final)."""
        d = self.ch.side[k]
        _, phi = self._search(pose, solver, k, H, pole)
        self.prev[k] = phi
        miss, Rf = self._arm(pose, solver, k, H, pole, phi)
        Rh = rot3(H)
        a = self.fore_share(k, Rf, Rh)
        Rf = self.twisted(Rf, a)
        Wf = pose.W[d["fore"]]
        pose.W[d["fore"]] = compose(Wf.translation, Rf)
        if free:
            Rh = self._straighten(k, Rf, Rh)
            H = compose(H.translation, Rh)
        flex, dev, tw = self.angles(k, Rf, Rh)
        self.report[k].append((self.excess(flex, dev), tw, a))
        return miss, H

    def _straighten(self, k, Rf, Rh):
        """Mano libre fuera del límite: se acerca a la del antebrazo (giro mínimo) hasta quedar en el borde, y el giro
        que excede lo que tolera la muñeca se quita."""
        F = Rf @ self.info[k]["rel0"]
        q = (F.transposed() @ Rh).to_quaternion()
        flex, dev, _ = self.angles(k, Rf, Rh)
        if self.excess(flex, dev) > 1.0:
            lo, hi = 0.0, 1.0
            for _ in range(18):
                mid = 0.5 * (lo + hi)
                f2, d2, _ = self.angles(k, Rf, F @ Quaternion().slerp(q, mid).to_matrix())
                if self.excess(f2, d2) > 1.0:
                    hi = mid
                else:
                    lo = mid
            q = Quaternion().slerp(q, lo)
        Rh = F @ q.to_matrix()
        _, _, tw = self.angles(k, Rf, Rh)
        if abs(tw) > WRIST_TWIST:
            Rh = Rh @ Matrix.Rotation(math.radians(-math.copysign(abs(tw) - WRIST_TWIST, tw)), 3, 'Y')
        return Rh

    def summary(self):
        """Peor muñeca de lo resuelto desde el último reset: {lado: (exceso, giro en la muñeca, giro del antebrazo)}."""
        out = {}
        for k, rows in self.report.items():
            if rows:
                out[k] = (round(max(r[0] for r in rows), 2), round(max(abs(r[1]) for r in rows), 1), round(max(abs(r[2]) for r in rows), 1))
        return out
