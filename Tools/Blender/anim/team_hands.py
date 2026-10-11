"""Manos que agarran: muñecas posibles, manos pegadas a otro hueso y el compañero de escena, para los clips de Gorō y
del abuelo (con el ninja del secuestro). Lo usan team_clips_goro / team_clips_grandpa (su 'Solver'); el núcleo de
team_rig queda como está para el ninja y el sumo.

1. Muñecas posibles (ítem 5 de la revisión de Felipe: "las manos se ven dobladas en las muñecas"). TeamSolver pone la
   mano con la orientación que pide el clip y el codo hacia el polo pedido sin mirar el antebrazo. Medido sobre los
   clips de la fase B3: la muñeca de Gorō quedaba doblada hasta 137° y girada ~170° sobre el eje del brazo, y la del
   abuelo, con las manos atrás, girada ~165°: en la malla se ve una muñeca quebrada o retorcida como un caramelo.
   HandSolver:
     * gira el codo alrededor del eje hombro-muñeca (el giro del brazo entero en el hombro) hasta dejar el antebrazo
       alineado con la mano (la muñeca neutra del reposo), cerca del polo pedido, del codo del cuadro anterior (sin
       saltos) y sin meter el codo en el cuerpo;
     * la mano que agarra el mango del martillo puede rodar alrededor del mango (sigue cerrada sobre él);
     * el giro sobre el eje del brazo (pronación) se reparte: una parte lo toma el antebrazo;
     * la mano LIBRE que igual queda fuera de lo posible se endereza hasta el límite; la que agarra algo nunca se
       mueve de su lugar (si queda fuera, el chequeo lo dice).
   Límites (°): flexión hacia la palma 70, extensión 60, desvío hacia el pulgar 25 y hacia el meñique 38; el giro que
   queda en la muñeca, hasta 60 (más se lee como caramelo en la malla low poly).
2. Manos pegadas a otro hueso: 'hand_r_on' = dict(who, bone, at, dir, palm) pone la mano en un punto del cuerpo de
   'who' en reposo (su marco de autoría) que acompaña al hueso 'bone': el ninja agarra el cuello del kimono del
   abuelo y lo sigue aunque el abuelo forcejee, sin que el clip tenga que adivinar dónde quedó.
3. Compañero: el FBX del abuelo trae también al ninja del secuestro (un segundo esqueleto '.001' en el mismo
   Armature). partner() lo carga como otro TeamChar sobre la MISMA armadura, con el mismo origen y unidades que el
   abuelo y su propio frente: su marco de autoría es el del abuelo girado 180° (flip()). Sus controles van en
   c['partner'] (PairClip) y se resuelven después del abuelo, en la misma pose.
"""
import math
from mathutils import Vector, Matrix, Quaternion
import nindo_anim as NA
import team_rig as T
from nindo_anim import V, rot3, compose

FLEX, EXTEND, RADIAL, ULNAR = 70.0, 60.0, 25.0, 38.0
WRIST_TWIST = 60.0
FORE_SHARE, FORE_MAX = 0.55, 60.0     # parte del giro que toma el antebrazo y su tope
SWIVEL, SWIVEL_STEP = 110, 5          # cuánto puede girar el codo respecto del pedido (°) y el paso de la búsqueda
GRIP_ROLL, GRIP_STEP = 40, 10         # la mano sobre el mango rueda hasta esto (°)


def flip(v):
    """Punto o dirección del marco del abuelo al del compañero (girado 180° alrededor de la vertical)."""
    return None if v is None else (-v[0], -v[1], v[2])


def flip_rot(r):
    """Giro XYZ (°) expresado en los ejes del abuelo -> ejes del compañero (conjugado por el giro de 180°)."""
    return (-r[0], -r[1], r[2])


def twist_deg(q):
    a = 2.0 * math.degrees(math.atan2(q.y, q.w))
    return (a + 180.0) % 360.0 - 180.0


# =============================================================================== compañero
def partner(host, spec):
    """El ninja del secuestro como TeamChar sobre la armadura del abuelo: mismo origen, unidades y piso; su frente,
    lados, manos y pies medidos en su propio esqueleto."""
    ch = T.TeamChar.__new__(T.TeamChar)
    ch.name, ch.spec = spec["name"], spec
    ch.src, ch.arm, ch.take_actions, ch.kid_pose = host.src, host.arm, host.take_actions, {}
    ch.meshes = [o for o in host.meshes if o.name in set(spec["meshes"])]
    ch.rig = host.rig
    ch.A, ch.Ai = host.A, host.Ai
    ch.ground, ch.u, ch.O = host.ground, host.u, host.O.copy()
    F = Vector(spec["fwd"]).normalized()
    Z = Vector((0, 0, 1))
    ch.Rcw = Matrix((Z.cross(F), -F, Z)).transposed()
    ch.Rc = rot3(ch.Ai) @ ch.Rcw
    ch.Rci = ch.Rc.transposed()
    ch.side = {}
    for k, tag in (("r", spec["right_tag"]), ("l", spec["left_tag"])):
        ch.side[k] = {role: (spec[role].format(tag) if spec[role] else None)
                      for role in ("clav", "upper", "fore", "hand", "hand_ctrl", "thigh", "shin", "foot", "foot_ctrl")}
    ch.measure()
    return ch


class PairClip(T.TeamClip):
    """Clip de dos: el principal (el abuelo) y 'partner' (un TeamClip del compañero, autorado en SU marco). Los dos
    comparten el reloj, el avance del transform (root_vel/travel) y la toma."""

    def __init__(self, name, frames, keys, partner_clip, partner_ch, **kw):
        super().__init__(name, frames, keys, **kw)
        self.partner_clip, self.partner_ch = partner_clip, partner_ch
        assert partner_clip.frames == frames, f"{name}: el compañero dura {partner_clip.frames} y el clip {frames}"

    def controls(self, f):
        c = super().controls(f)
        self.partner_clip.ch = self.partner_ch
        c["partner"] = self.partner_clip.controls(f)
        return c


# =============================================================================== resolución
class HandSolver(T.TeamSolver):
    """TeamSolver con muñecas posibles, manos pegadas a otro hueso y el compañero (ver el encabezado)."""

    def __init__(self, ch, partner_ch=None, others=None):
        super().__init__(ch)
        self.others = dict(others or {})
        self.others.setdefault(ch.name, ch)
        self.partner = None
        if partner_ch is not None:
            self.others[partner_ch.name] = partner_ch
            self.partner = HandSolver(partner_ch, others=self.others)
        R = ch.rig
        self.info = {}
        for k in "rl":
            d = ch.side[k]
            hi = ch.hand_info[k]
            Rh0 = rot3(R.rest[d["hand"]])
            self.info[k] = dict(
                rel0=rot3(R.rest[d["fore"]]).transposed() @ Rh0,                     # mano respecto del antebrazo en reposo
                fore=(Rh0.transposed() @ rot3(R.rest[d["fore"]]).col[1]).normalized(),   # antebrazo visto desde la mano
                n=(Rh0.transposed() @ hi["M0"].col[2]).normalized(),                 # palma (marco de la mano en reposo)
                l=(Rh0.transposed() @ hi["M0"].col[1]).normalized(),                 # hacia el índice
            )
        self.begin(None)

    # ---------------------------------------------------------------- reloj del clip
    def begin(self, clip):
        """Clip nuevo: sin el codo del cuadro anterior ni lo medido. En un loop se resuelven antes los últimos cuadros:
        el codo del cuadro 0 sigue al del final y la costura no salta."""
        self.prev, self.report, self.grip_kind = {}, {"r": [], "l": []}, {}
        if self.partner:
            self.partner.begin(None)
        if clip is not None and clip.loop:
            clip.ch = self.ch
            for f in range(max(0, clip.frames - 8), clip.frames):
                self.solve(NA.Pose(self.rig), clip.controls(f))
            self.report = {"r": [], "l": []}
            if self.partner:
                self.partner.report = {"r": [], "l": []}

    # ---------------------------------------------------------------- muñeca
    def angles(self, k, Rf, Rh):
        """(flexión, desvío, giro) de la mano respecto del antebrazo en grados (0 = como en el reposo)."""
        i = self.info[k]
        D = (Rf @ i["rel0"]).transposed() @ Rh
        s = D.col[1]
        flex = math.degrees(math.atan2(s.dot(i["n"]), s.y))
        dev = math.degrees(math.atan2(s.dot(i["l"]), s.y))
        return flex, dev, twist_deg(D.to_quaternion())

    @staticmethod
    def excess(flex, dev):
        """Muñeca respecto de su límite elíptico (1 = en el límite)."""
        return math.hypot(flex / (FLEX if flex >= 0 else EXTEND), dev / (RADIAL if dev >= 0 else ULNAR))

    def elbow_options(self, pose, k, tgt, pole):
        """Polos candidatos alrededor del eje hombro-muñeca: [(grados respecto del pedido, polo, codo, dirección del
        antebrazo)]. Con el brazo estirado (sin codo que girar) devuelve solo el pedido."""
        ch, R = self.ch, self.rig
        d = ch.side[k]
        S = (pose.get(d["clav"]) @ R.rel[d["upper"]]).translation
        a, b = R.length[d["upper"]], R.length[d["fore"]]
        dv = V(tgt) - S
        dist = max(abs(a - b) + 1e-4, min(dv.length, (a + b) * 0.999))
        nd = dv.normalized() if dv.length > 1e-6 else Vector((0, 0, -1))
        P0 = V(pole) - nd * V(pole).dot(nd)
        if P0.length < 1e-6:
            P0 = nd.orthogonal()
        P0.normalize()
        Q0 = nd.cross(P0)
        cosA = max(-1.0, min(1.0, (a * a + dist * dist - b * b) / (2.0 * a * dist)))
        sinA = math.sqrt(max(0.0, 1.0 - cosA * cosA))
        T_ = S + nd * dist
        out = []
        for deg in range(-SWIVEL, SWIVEL + 1, SWIVEL_STEP):
            t = math.radians(deg)
            P = P0 * math.cos(t) + Q0 * math.sin(t)
            E = S + nd * (a * cosA) + P * (a * sinA)
            out.append((deg, P, E, (T_ - E).normalized()))
            if sinA < 0.02:
                break
        return out

    def body_penalty(self, pose, E):
        """El codo no se mete en el tronco: distancia al eje cadera-cabeza contra el radio del cuerpo (spec 'body_r')."""
        r = self.ch.spec.get("body_r", 0.0) * self.ch.u
        if r <= 0.0:
            return 0.0
        a, b = pose.head(self.ch.spec["pelvis"]), pose.head(self.ch.spec["head"])
        ab = b - a
        t = max(0.0, min(1.0, (E - a).dot(ab) / max(ab.length_squared, 1e-9)))
        dd = (a + ab * t - E).length
        return 0.0 if dd >= r else 400.0 * (1.0 - dd / r)

    def best_arm(self, pose, k, H, pole, roll_axis=None, roll_pt=None):
        """(polo, mano) que dejan la muñeca más cómoda. roll_axis/roll_pt: la mano puede rodar alrededor de ese eje
        (el mango) por ese punto, hasta GRIP_ROLL."""
        hi = self.ch.hand_info[k]
        i = self.info[k]
        rolls = [0]
        if roll_axis is not None:
            rolls = list(range(-GRIP_ROLL, GRIP_ROLL + 1, GRIP_STEP))
        prev = self.prev.get(k)
        best = None
        for rd in rolls:
            if rd:
                Rr = Matrix.Rotation(math.radians(rd), 4, V(roll_axis))
                Hc = Matrix.Translation(roll_pt) @ Rr @ Matrix.Translation(-V(roll_pt)) @ H
            else:
                Hc = H
            Rh = rot3(Hc)
            want = (Rh @ i["fore"]).normalized()
            tgt = Hc @ hi["fore_tail_local"]
            for deg, P, E, fd in self.elbow_options(pose, k, tgt, pole):
                bend = math.degrees(math.acos(max(-1.0, min(1.0, fd.dot(want)))))
                cost = bend + 0.12 * abs(deg) + 0.25 * abs(rd) + self.body_penalty(pose, E)
                if prev is not None:
                    cost += 0.8 * abs(deg - prev[0]) + 0.5 * abs(rd - prev[1])
                if best is None or cost < best[0]:
                    best = (cost, deg, rd, P, Hc)
        self.prev[k] = (best[1], best[2])
        return best[3], best[4]

    def spread_twist(self, pose, k):
        """El antebrazo toma parte del giro de la mano sobre el eje del brazo (gira sobre su propio eje: la punta no se
        mueve); el resto queda en la muñeca."""
        d = self.ch.side[k]
        fa, h = d["fore"], d["hand"]
        Wf, Wh = pose.get(fa), pose.get(h)
        D = (rot3(Wf) @ self.info[k]["rel0"]).transposed() @ rot3(Wh)
        tw = twist_deg(D.to_quaternion())
        take = max(-FORE_MAX, min(FORE_MAX, tw * FORE_SHARE))
        pose.place(fa, compose(Wf.translation, rot3(Wf) @ Matrix.Rotation(math.radians(take), 3, 'Y')))

    def straighten(self, k, Rf, Rh):
        """Mano libre fuera del límite: se acerca a la muñeca neutra (conservando el giro) hasta entrar."""
        flex, dev, tw = self.angles(k, Rf, Rh)
        if self.excess(flex, dev) <= 1.0:
            return Rh
        N = Rf @ self.info[k]["rel0"]
        D = (N.transposed() @ Rh).to_quaternion()
        twist = Quaternion((0, 1, 0), math.radians(tw))
        swing = D @ twist.inverted()
        lo, hi = 0.0, 1.0
        for _ in range(12):
            m = (lo + hi) * 0.5
            q = Quaternion().slerp(swing, m) @ twist
            f2, d2, _ = self.angles(k, Rf, N @ q.to_matrix())
            if self.excess(f2, d2) <= 0.98:
                lo = m
            else:
                hi = m
        return N @ (Quaternion().slerp(swing, lo) @ twist).to_matrix()

    def place_hand(self, pose, k, H, pole_c, *args, **kw):
        """Brazo y mano con la muñeca más cómoda posible; la mano queda donde se pidió (si el brazo no llega, la
        falta la mide 'miss' como siempre)."""
        ch, R = self.ch, self.rig
        d = ch.side[k]
        hi = ch.hand_info[k]
        grip = self.grip_kind.get(k)
        axis = pt = None
        if grip is not None:
            axis, pt = grip
        pole, H = self.best_arm(pose, k, H, ch.D(pole_c), axis, pt)
        tgt = H @ hi["fore_tail_local"]
        self.reach_with_clavicle(pose, k, tgt)
        miss = pose.two_bone(d["upper"], d["fore"], tgt, pole)
        if grip is None:
            Rh = self.straighten(k, rot3(pose.get(d["fore"])), rot3(H))
            H = compose(H.translation, Rh)
        if d["hand_ctrl"]:
            pose.place(d["hand_ctrl"], H @ R.rel[d["hand"]].inverted())
        pose.place(d["hand"], H)
        self.spread_twist(pose, k)
        self.report[k].append(self.angles(k, rot3(pose.get(d["fore"])), rot3(pose.get(d["hand"]))) + (grip is not None,))
        return miss

    def grip_frame(self, k, haft_arm, shoulder_arm, stick_pt):
        # la mano sobre el mango puede rodar alrededor de él (place_hand busca el giro que mejor deja la muñeca)
        self.grip_kind[k] = (haft_arm.normalized(), stick_pt.copy())
        return super().grip_frame(k, haft_arm, shoulder_arm, stick_pt)

    # ---------------------------------------------------------------- manos pegadas a otro hueso
    def resolve_on(self, pose, c, k):
        """Convierte 'hand_k_on' en posición/dirección/palma de esta mano según cómo quedó el hueso al que se pega."""
        on = c.get("hand_%s_on" % k)
        if not on:
            return False
        owner = self.others[on["who"]]
        b = on["bone"]
        Dm = pose.get(b) @ self.rig.rest_inv[b]
        p = Dm @ owner.P(on["at"])
        c["hand_" + k] = self.ch.Pc(p)
        if on.get("dir") is not None:
            c["hand_%s_dir" % k] = self.ch.Dc(rot3(Dm) @ owner.D(on["dir"]))
        if on.get("palm") is not None:
            c["hand_%s_palm" % k] = self.ch.Dc(rot3(Dm) @ owner.D(on["palm"]))
        return True

    def solve(self, pose, c):
        self.grip_kind = {}
        later = []
        for k in "rl":
            on = c.get("hand_%s_on" % k)
            if on and on["who"] != self.ch.name and on["bone"] not in pose.W:
                later.append(k)              # se pega al compañero: va después de resolverlo
            else:
                self.resolve_on(pose, c, k)
        misses = super().solve(pose, c)
        if self.partner and c.get("partner") is not None:
            pm = self.partner.solve(pose, dict(c["partner"]))
            misses["partner_hands"] = max(pm["hand_r"], pm["hand_l"])
            misses["partner_legs"] = pm["legs"]
        for k in later:
            if self.resolve_on(pose, c, k):
                dflt = (-0.3, 0.6, -0.4) if k == "r" else (0.3, 0.6, -0.4)
                misses["hand_" + k] = self.place_hand(pose, k, self.free_hand(c, k), c.get("elbow_" + k) or dflt)
                fist = c.get("fist_" + k)
                self.curl(pose, k, 0.0 if fist is None else fist)
        self.misses = misses
        return misses


# =============================================================================== chequeos
def lint(ch, solver, clip, check, report):
    """Muñecas de cada clip (y las del compañero): fuera del límite o con mucho giro, falla. Agrega a 'report'."""
    for who, s in (("", solver), ("compañero ", solver.partner)):
        if s is None:
            continue
        for k in "rl":
            rows = s.report[k]
            if not rows:
                continue
            ex = max(HandSolver.excess(f, d) for f, d, t, g in rows)
            tw = max(abs(t) for f, d, t, g in rows)
            fl = max(abs(f) for f, d, t, g in rows)
            report.setdefault("wrist", {})[who + k] = dict(excess=round(ex, 2), max_twist=round(tw, 1), max_flex=round(fl, 1))
            check(ex <= 1.12 and tw <= WRIST_TWIST + 10.0,
                  f"{clip.name}: muñeca {who}{'derecha' if k == 'r' else 'izquierda'} posible (límite x{ex:.2f}, flexión "
                  f"{fl:.0f}°, giro {tw:.0f}°)", warn=ex <= 1.3 and tw <= WRIST_TWIST + 25.0)
