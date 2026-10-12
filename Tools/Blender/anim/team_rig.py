"""Animación por script de los personajes del EQUIPO (ninja, sumo, Gorō, abuelo) sobre sus esqueletos
originales (Blender 4.4). Módulo hermano de nindo_anim.py: usa su núcleo (Rig, Pose, IK analítica, claves,
StepTimeline, mediciones) sin tocarlo, y agrega lo que cambia con un esqueleto que NO se hizo para esto.

Esqueleto de juego (desde la fase C): en el sumo, Gorō y el abuelo (con el ninja del secuestro) las manos y los pies
colgaban de huesos de IK en la raíz (TargetBrazo, TargetPie, AntebrazoTarget...) y Unity, que mezcla cada hueso por
separado, despegaba muñecas y tobillos en cada cruce de clips y en todo el blend de locomoción. Los export_<personaje>.py
los pasan a hijos del antebrazo y la tibia (charlib.game_limbs: mismos nombres, cabezas, colas y rolls; los pesos de los
controles pasan a la mano/pie; las tomas del equipo se re-hornean con la misma pose). El solver mira la jerarquía que
trae el modelo, así sirve igual para un FBX viejo:
  * si la mano o el pie todavía cuelgan de su control, el control se pone pegado a ellos (con su offset de reposo);
  * los polos que pesan vértices van rígidos con la tibia ('follow'); sin pesos quedan en reposo;
  * el resto de la ayuda de IK queda en reposo respecto de su padre (no pesa nada y ningún clip la mueve).
Brazos y muñecas los resuelve team_limbs.ArmSolver (codo que gira, agarre que rueda en el mango, pronación en el
antebrazo, muñeca dentro de sus límites): ver su encabezado y README_team_rig.md.

Marco de autoría (el mismo para los cuatro, en METROS DEL JUEGO): origen en el piso bajo el transform del
juego, frente = -Y, izquierda del personaje = +X, arriba = +Z (convención de nindo_anim / STYLE.md). Cada
personaje del equipo mira a otro eje de Blender y está en otras unidades; la conversión vive en TeamChar y
los clips no se enteran. Giros en grados XYZ de ese marco: x + = inclinarse hacia adelante, y + = hacia su
izquierda, z + = girar hacia su izquierda.
"""
import bpy, math, os, sys, json
from mathutils import Vector, Matrix, Quaternion, Euler

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ASSETS = os.path.join(REPO, "Nindo", "Assets")
for _p in (HERE, os.path.join(REPO, "Tools", "Blender", "characters")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import nindo_anim as NA                         # noqa: E402
from nindo_anim import V, compose, rot3, basis_yz   # noqa: E402
import team_limbs as TL                         # noqa: E402

FPS = NA.FPS


def side_names(fmt, right, left):
    """Nombres de un hueso de cada lado: los FBX del equipo no respetan .L/.R respecto del personaje
    (el ninja y el sumo miran a +X/+Y, así que su '.L' queda del lado DERECHO). Se mapea por geometría."""
    return {"r": fmt.format(right), "l": fmt.format(left)}


# =============================================================================== fichas de personaje
# u: unidades del FBX por metro del juego = alto de la unión de bounds que mide CharacterFactory.NormalizeHeight
# dividido por el 'height' de NindoContent (se recalcula al cargar y se compara con este valor de control).
# fwd: hacia dónde mira el personaje en el mundo de Blender (medido con los ojos de la malla).
CHARS = {
    "ninja": dict(
        fbx="Models/Ninja/Ninja 1.fbx", height=1.7, fwd=(1, 0, 0), right_tag="L", left_tag="R",
        pelvis="Root", spine=["EspaldaBaja"], chest=["EspaldaAlta"], head="Cabeza",
        clav="Hombro.{}", upper="Brazo.{}", fore="Antebrazo.{}", hand="Mano.{}", hand_ctrl=None,
        thigh="Pierna.{}", shin="Tibia.{}", foot="Pie.{}", foot_ctrl=None,
        fingers={"r": [["Dedo1.L", "PuntaDedo.L"], ["Dedo2.l", "PuntaDedo2.L"], ["Dedo3.L", "PuntaDedo3.L"]],
                 "l": [["Dedo1.R", "PuntaDedo1.R"], ["Dedo2.R", "PuntaDedo2.R"], ["Dedo3.R", "PuntaDedo3.R"]]},
        thumb={"r": ["Pulgar.L", "PuntaPulgar.L"], "l": ["Pulgar.R", "PuntaPulgar.R"]},
        index_pinky={"r": ("Dedo1.L", "Dedo3.L"), "l": ("Dedo1.R", "Dedo3.R")},
        weapon=dict(kind="katana", bone="Katana", mesh="Katana", hand="r"),
        follow={}, kidnapper=None,
    ),
    "sumo": dict(
        fbx="Characters/Sumo/luchadorsumo.fbx", height=2.6, fwd=(0, 1, 0), right_tag="L", left_tag="R",
        pelvis="Root", spine=["Torso"], chest=[], head="Cabeza",
        clav="Hombro.{}", upper="Brazo.{}", fore="Antebrazo.{}", hand="Palma.{}", hand_ctrl="TargetBrazo.{}",
        thigh="Pierna.{}", shin="Tibia.{}", foot="pie.{}", foot_ctrl="TargetPie.{}",
        fingers={s: [[f"Dedo1.{t}", f"PuntaDedo1.{t}"], [f"Dedo2.{t}", f"PuntaDedo2.{t}"], [f"Dedo3.{t}", f"PuntaDedo3.{t}"]]
                 for s, t in (("r", "L"), ("l", "R"))},
        thumb={"r": ["Pulgar.L", "PuntaPulgar.L"], "l": ["Pulgar.R", "PuntaPulgar.R"]},
        index_pinky={"r": ("Dedo1.L", "Dedo3.L"), "l": ("Dedo1.R", "Dedo3.R")},
        weapon=None,
        # las rodillas pesan vértices en el polo (35 por pierna): van rígidos con la tibia
        follow={"PolePie.L": "Tibia.L", "PolePie.R": "Tibia.R", "PoleBrazo.L": "Antebrazo.L", "PoleBrazo.R": "Antebrazo.R"},
        kidnapper=None,
    ),
    "goro": dict(
        fbx="Models/Minijefe.fbx", height=3.41, fwd=(0, -1, 0), right_tag="R", left_tag="L",
        pelvis="Root", spine=["Torso"], chest=[], head="Cabeza",
        clav="Hombro.{}", upper="Brazo.{}", fore="Antebrazo.{}", hand="Mano.{}", hand_ctrl="TargetBrazo.{}",
        thigh="Pierna.{}", shin="Tibia.{}", foot="Pie.{}", foot_ctrl="TargetPie.{}",
        fingers={s: [[f"Dedo2.{t}", f"Puntadedo2.{t}"], [f"Dedo2.{t}.001", f"Puntadedo2.{t}.001"],
                     [f"Dedo2.{t}.002", f"Puntadedo2.{t}.002"]] for s, t in (("r", "R"), ("l", "L"))},
        thumb={s: [f"Dedo1.001.{t}", f"Puntadedo1.001.{t}"] for s, t in (("r", "R"), ("l", "L"))},
        index_pinky={"r": ("Dedo2.R.002", "Dedo2.R.001"), "l": ("Dedo2.L.002", "Dedo2.L.001")},
        weapon=dict(kind="club", bone="BaseM", mesh="Cylinder.005", grips=("Agarre1", "Agarre2")),
        follow={}, kidnapper=None,
    ),
    "grandpa": dict(
        fbx="Nindo/Art/Models/Characters/Grandpa.fbx", height=1.45, fwd=(0, 1, 0), right_tag="L", left_tag="R",
        pelvis="Root", spine=["Torso"], chest=[], head="Cabeza",
        clav="Hombro.{}", upper="Brazo.{}", fore="Antebrazo.{}", hand="Mano.{}", hand_ctrl="AntebrazoTarget.{}",
        thigh="Pierna.{}", shin="Tibia.{}", foot="Pie.{}", foot_ctrl="TibiaTarget.{}",
        fingers={s: [[f"Dedo1.{t}", f"PuntaDedo1.{t}"], [f"Dedo2.{t}", f"PuntaDedo2.{t}"], [f"Dedo3.{t}", f"PuntaDedo3.{t}"]]
                 for s, t in (("r", "L"), ("l", "R"))},
        thumb={"r": ["Pulgar.L", "PuntaPulgar.L"], "l": ["Pulgar.R", "PuntaPulgar.R"]},
        index_pinky={"r": ("Dedo1.L", "Dedo3.L"), "l": ("Dedo1.R", "Dedo3.R")},
        weapon=None, follow={},
        # el FBX del abuelo trae también al ninja del secuestro (esqueleto '.001'): en los clips nuevos queda
        # quieto en la pose del cuadro 2 del secuestro (parado, con las manos a los costados), que es lo que se ve del
        # NPC 'kidnap' mientras el abuelo respira antes de la toma del equipo
        # (partner_spec / TeamChar.partner: el mismo esqueleto con '.001', parado 1.3 m adelante del abuelo y mirándolo)
        kidnapper=dict(suffix=".001", take_frame=2, fwd=(0, -1, 0)),
        export_kw=dict(apply_scale_options='FBX_SCALE_UNITS'),
    ),
}


def partner_spec(spec, kd):
    """Ficha del segundo esqueleto que viaja en el FBX de otro personaje (el ninja del secuestro en el del abuelo: los
    mismos nombres con 'suffix'). Se resuelve con su propio TeamSolver sobre la MISMA pose (bake con clip.partner) y se
    autora en su propio marco: origen en el piso bajo su cadera de reposo y frente hacia donde mira ('fwd' del mundo de
    Blender, medido con los pulgares y las rodillas de su reposo)."""
    suf = kd["suffix"]
    out = dict(spec)
    for key in ("pelvis", "head", "clav", "upper", "fore", "hand", "hand_ctrl", "thigh", "shin", "foot", "foot_ctrl"):
        out[key] = spec[key] + suf if spec[key] else None
    out["spine"] = [x + suf for x in spec["spine"]]
    out["chest"] = [x + suf for x in spec["chest"]]
    out["fingers"] = {k: [[a + suf, b + suf] for a, b in v] for k, v in spec["fingers"].items()}
    out["thumb"] = {k: [a + suf for a in v] for k, v in spec["thumb"].items()}
    out["index_pinky"] = {k: tuple(a + suf for a in v) for k, v in spec["index_pinky"].items()}
    out["follow"] = {a + suf: b + suf for a, b in spec["follow"].items()}
    out.update(weapon=None, kidnapper=None, fwd=kd["fwd"], suffix=suf)
    return out


# una toma del equipo re-resuelta (TakeClip): la otra mano agarra el mango si en la toma su puño quedaba a menos de esto (m)
TAKE_GRIP = 0.10
# polo del codo cuando el clip no lo pide: atrás, afuera y abajo
ARM_POLE = {"r": (-0.3, 0.6, -0.4), "l": (0.3, 0.6, -0.4)}
GRIP_CURL = (62.0, 78.0)          # grados de cada falange al cerrar el puño del todo
THUMB_CURL = (26.0, 34.0)


class TeamChar:
    """Un personaje del equipo cargado en la escena, con la conversión del marco de autoría al esqueleto."""

    def __init__(self, name, spec, base=None):
        """base: el personaje cuyo FBX ya está cargado y que trae a este como segundo esqueleto (partner_spec): se
        comparten la armadura, el Rig y las unidades; el marco de autoría es el propio (ver partner_spec)."""
        self.name, self.spec = name, spec
        self._partner = None
        if base is None:
            import charlib as C
            src = os.path.join(ASSETS, spec["fbx"])
            self.src = src
            self.arm = C.load(src)
            self.take_actions = [a for a in bpy.data.actions]
            self.kid_pose = self.sample_kidnapper() if spec.get("kidnapper") else {}
        else:
            self.src, self.arm, self.take_actions, self.kid_pose = base.src, base.arm, base.take_actions, {}
        arm = self.arm
        if arm.animation_data:
            arm.animation_data.action = None
        for pb in arm.pose.bones:
            pb.location = (0, 0, 0)
            pb.rotation_mode = 'QUATERNION'
            pb.rotation_quaternion = (1, 0, 0, 0)
            pb.scale = (1, 1, 1)
        bpy.context.view_layer.update()
        self.meshes = [o for o in bpy.data.objects if o.type == 'MESH']
        if base is not None:
            # solo las mallas que pesan en sus huesos (el radio del cuerpo y las suelas se miden en ellas)
            own = {n for n in base.rig.names if n.endswith(spec["suffix"])}
            self.meshes = [o for o in self.meshes if any(g.name in own for g in o.vertex_groups)]
        self.rig = base.rig if base is not None else NA.Rig(arm)
        # huesos que mueven vértices: un polo sin pesos (el esqueleto de juego ya los pasó a la tibia) queda en reposo
        self.weighted = set()
        for o in self.meshes:
            used = {gg.group for v in o.data.vertices for gg in v.groups if gg.weight > 0.01}
            self.weighted |= {g.name for g in o.vertex_groups if g.index in used}
        A = arm.matrix_world.copy()
        self.A, self.Ai = A, A.inverted()
        # alto que mide NormalizeHeight (unión de bounds de las mallas con skin en su pose de bind) -> unidades por
        # metro. Las piezas rígidas (katana, martillo) cuelgan de un hueso: en reposo el martillo de Gorō queda
        # parado en el piso adelante y estiraría la cuenta; en el prefab están en la mano y no la cambian
        if base is None:
            dg = bpy.context.evaluated_depsgraph_get()
            lo, hi = 1e9, -1e9
            for o in self.meshes:
                if not o.vertex_groups:
                    continue
                oe = o.evaluated_get(dg)
                me = oe.to_mesh()
                for v in me.vertices:
                    z = (oe.matrix_world @ v.co).z
                    lo, hi = min(lo, z), max(hi, z)
                oe.to_mesh_clear()
            self.ground = lo
            self.u = (hi - lo) / spec["height"]
        else:
            # mismas unidades y mismo piso que el personaje del FBX (los dos viven en el mismo transform del juego)
            self.ground, self.u = base.ground, base.u
        F = Vector(spec["fwd"]).normalized()
        Z = Vector((0, 0, 1))
        # columnas = adónde va cada eje del marco de autoría: +X (izquierda), +Y (atrás), +Z (arriba)
        self.Rcw = Matrix((Z.cross(F), -F, Z)).transposed()
        self.Rc = rot3(self.Ai) @ self.Rcw            # marco de autoría -> ejes de la armadura
        self.Rci = self.Rc.transposed()
        self.O = Vector((0.0, 0.0, self.ground))
        if base is not None:
            # origen en el piso bajo su cadera de reposo: sus clips se autoran como los de cualquiera
            pw = self.A @ self.rig.rest[spec["pelvis"]].translation
            self.O = Vector((pw.x, pw.y, self.ground))
        # hacia dónde corre el piso en el marco de autoría cuando el transform del juego avanza ('travel', ver solve):
        # +Y para el personaje del FBX; para el segundo esqueleto, el mismo vector del mundo visto desde su marco
        self.travel_axis = Vector((0.0, 1.0, 0.0)) if base is None else self.Rcw.transposed() @ (base.Rcw @ Vector((0.0, 1.0, 0.0)))
        s = spec
        self.side = {}
        for k, tag in (("r", s["right_tag"]), ("l", s["left_tag"])):
            d = {}
            for role in ("clav", "upper", "fore", "hand", "hand_ctrl", "thigh", "shin", "foot", "foot_ctrl"):
                d[role] = s[role].format(tag) if s[role] else None
            # el control solo se mueve si la mano/el pie todavía cuelgan de él (FBX anterior al esqueleto de juego)
            for end, ctrl in (("hand", "hand_ctrl"), ("foot", "foot_ctrl")):
                if d[ctrl] and self.rig.parent.get(d[end]) != d[ctrl]:
                    d[ctrl] = None
            self.side[k] = d
        self.measure()
        if self.kid_pose:
            self.kid_pose = self.straighten_kid_hands(self.kid_pose)

    @property
    def partner(self):
        """El segundo personaje del FBX (el ninja del secuestro en el del abuelo) como TeamChar propio, o None."""
        kd = self.spec.get("kidnapper")
        if kd is None:
            return None
        if self._partner is None:
            self._partner = TeamChar(self.name + "_partner", partner_spec(self.spec, kd), base=self)
        return self._partner

    # ------------------------------------------------------------------ conversión de marcos
    def P(self, p):
        """Punto del marco de autoría (m) -> espacio de la armadura."""
        return self.Ai @ (self.O + (self.Rcw @ V(p)) * self.u)

    def D(self, d):
        """Dirección del marco de autoría -> ejes de la armadura."""
        return (self.Rc @ V(d)).normalized()

    def Q(self, r):
        """Giro (grados XYZ del marco de autoría, o Quaternion en ese marco) -> Quaternion en ejes de la armadura."""
        q = r if isinstance(r, Quaternion) else NA.euler_q(r)
        return (self.Rc @ q.to_matrix() @ self.Rci).to_quaternion()

    def Pc(self, p_arm):
        """Punto de la armadura -> marco de autoría (m)."""
        return (self.Rcw.transposed() @ ((self.A @ V(p_arm)) - self.O)) / self.u

    def Dc(self, d_arm):
        return (self.Rci @ V(d_arm)).normalized()

    def offset_arm(self, d):
        """Desplazamiento del marco de autoría (m) -> desplazamiento en la armadura."""
        return self.Rc @ V(d) * self.u

    # ------------------------------------------------------------------ medidas de reposo
    def head(self, n):
        return self.rig.rest[n].translation.copy()

    def tail(self, n):
        return self.rig.rest[n] @ Vector((0.0, self.rig.length[n], 0.0))

    def measure(self):
        """Marcas de reposo en el marco de autoría y los marcos fijos de manos, pies y arma."""
        R = self.rig
        L = self.land = {}
        sp = self.spec
        L["pelvis"] = self.Pc(self.head(sp["pelvis"]))
        L["head"] = self.Pc(self.head(sp["head"]))
        self.hand_info, self.foot_info = {}, {}
        for k, d in self.side.items():
            L["shoulder_" + k] = self.Pc(self.head(d["upper"]))
            L["elbow_" + k] = self.Pc(self.head(d["fore"]))
            L["wrist_" + k] = self.Pc(self.head(d["hand"]))
            L["hip_" + k] = self.Pc(self.head(d["thigh"]))
            L["knee_" + k] = self.Pc(self.head(d["shin"]))
            L["ankle_" + k] = self.Pc(self.head(d["foot"]))
            # mano: dónde queda la punta del antebrazo vista desde la mano (IK apunta ahí), el dedo y la palma
            h = d["hand"]
            Rh0 = rot3(R.rest[h])
            fore_tail_local = R.rest_inv[h] @ self.tail(d["fore"])
            fdir = Rh0.col[1].normalized()
            ip = sp["index_pinky"][k]
            lat = (self.head(ip[0]) - self.head(ip[1]))
            lat = (lat - fdir * lat.dot(fdir)).normalized()          # hacia el índice
            n = self.palm_normal(k, h, fdir, lat)
            chi = 1.0 if n.dot(lat.cross(fdir)) > 0 else -1.0
            M0 = Matrix((fdir, lat, n)).transposed()
            hand_len = self.hand_length(k, h)
            curl = self.finger_axes(k, n)
            self.hand_info[k] = dict(Rh0=Rh0, fore_tail_local=fore_tail_local, M0=M0, chi=chi, len=hand_len, curl=curl,
                                     fist=R.rest_inv[h] @ self.fist_hole(k, h, fdir, n, curl, hand_len))
            f = d["foot"]
            self.foot_info[k] = dict(shin_tail_local=R.rest_inv[f] @ self.tail(d["shin"]), Rf0=rot3(R.rest[f]))
        L["sole_z"] = {k: self.Pc(self.head(self.side[k]["foot"])).z for k in "rl"}
        w = sp.get("weapon")
        self.weapon_info = None
        if w and w["kind"] == "katana":
            self.weapon_info = self.measure_katana(w)
        elif w and w["kind"] == "club":
            self.weapon_info = self.measure_club(w)
        self.leg_len = {k: (R.length[self.side[k]["thigh"]] + R.length[self.side[k]["shin"]]) / self.u for k in "rl"}
        self.arm_len = {k: (R.length[self.side[k]["upper"]] + R.length[self.side[k]["fore"]]) / self.u for k in "rl"}
        self.measure_feet()

    def measure_feet(self):
        """Punta y talón de cada suela (malla en reposo) respecto del tobillo, en el marco de autoría: el pie que
        despega rueda sobre la punta y el que apoya, sobre el talón, con ese punto quieto en el piso."""
        dg = bpy.context.evaluated_depsgraph_get()
        self.sole = {}
        for k in "rl":
            names = {self.side[k]["foot"]} | ({self.side[k]["foot_ctrl"]} if self.side[k]["foot_ctrl"] else set())
            pts = []
            for o in self.meshes:
                gi = {g.index for g in o.vertex_groups if g.name in names}
                if not gi:
                    continue
                oe = o.evaluated_get(dg)
                me = oe.to_mesh()
                for v in o.data.vertices:
                    if sum(g.weight for g in v.groups if g.group in gi) > 0.5:
                        pts.append(self.Pc(self.Ai @ (oe.matrix_world @ me.vertices[v.index].co)))
                oe.to_mesh_clear()
            ank = self.land["ankle_" + k]
            low = [p for p in pts if p.z < min(q.z for q in pts) + 0.025]
            toe = min(low, key=lambda p: p.y)
            heel = max(low, key=lambda p: p.y)
            self.sole[k] = dict(toe=Vector((ank.x, toe.y, toe.z)) - ank, heel=Vector((ank.x, heel.y, heel.z)) - ank)

    def foot_at(self, k, x, y, yaw=0.0, pitch=0.0, roll=0.0, z=0.0):
        """Tobillo y giro de un pie apoyado en (x, y) del piso (m, marco de autoría) con la punta girada 'yaw' (° hacia
        la izquierda del personaje). pitch > 0 levanta el talón rodando sobre la punta, < 0 levanta la punta sobre el
        talón: el punto de apoyo queda clavado. z sube el pie entero (vuelo). Devuelve (tobillo, (pitch, roll, yaw))."""
        base = Vector((x, y, self.land["sole_z"][k] + z))
        R0 = Euler((0.0, math.radians(roll), math.radians(yaw)), 'XYZ').to_matrix()
        R = Euler((math.radians(pitch), math.radians(roll), math.radians(yaw)), 'XYZ').to_matrix()
        if abs(pitch) < 1e-6:
            return base, (0.0, roll, yaw)
        v = self.sole[k]["toe" if pitch > 0 else "heel"]
        pivot = base + R0 @ v
        return pivot - R @ v, (pitch, roll, yaw)

    def palm_normal(self, k, h, fdir, lat):
        """Hacia dónde mira la palma (perpendicular a los dedos y al índice). Sale de cómo están doblados los dedos en el
        reposo (todo modelo los deja apenas curvados hacia la palma); el pulgar solo si los dedos vienen derechos. Con el
        pulgar solo (como antes) la palma del ninja y del abuelo quedaba del lado del dorso: el puño se cerraba para atrás
        y la katana, que el equipo dejó bajo los dedos de la mano abierta, quedaba afuera del puño."""
        R = self.rig
        sp = self.spec
        bend = Vector()
        for a, b in sp["fingers"][k]:
            if a in R.rest and b in R.rest:
                d1, d2 = rot3(R.rest[a]).col[1], rot3(R.rest[b]).col[1]
                bend += d2 - d1 * d2.dot(d1)
        nb = bend - fdir * bend.dot(fdir) - lat * bend.dot(lat)
        thumb = self.head(sp["thumb"][k][1]) - self.head(h)
        nt = thumb - fdir * thumb.dot(fdir) - lat * thumb.dot(lat)
        n = nb if nb.length > 0.15 else nt
        if n.length < 1e-5:
            n = fdir.cross(lat)
        return n.normalized()

    def hand_length(self, k, h):
        """Largo de la mano: la distancia media de la muñeca a la base de los dedos y del pulgar. No el largo del hueso:
        el FBX no lo guarda y el importador de Blender lo reconstruye como la distancia media a TODOS los hijos. Con el
        esqueleto de juego el martillo de Gorō (BaseM) cuelga de su mano derecha: el hueso medía 0.83 en vez de 0.26, el
        hueco del puño quedaba 20 cm más allá de los dedos y el puño flotaba al costado del mango (lo mismo, apenas, con la
        Katana hija de la mano del ninja)."""
        R = self.rig
        digits = {c[0] for c in self.spec["fingers"][k]} | {self.spec["thumb"][k][0]}
        kids = [c for c in R.children[h] if c in digits]
        if not kids:
            return R.length[h]
        return sum((R.rest[c].translation - R.rest[h].translation).length for c in kids) / len(kids)

    def fist_hole(self, k, h, fdir, n, curl, hand_len):
        """Centro del hueco del puño cerrado (espacio de la armadura, reposo): el promedio de los nudillos, de las
        articulaciones del medio y de las puntas de los dedos ya cerrados con 'curl', y de la palma bajo los nudillos.
        Ahí va el mango: con un punto fijo a media palma (como antes) el mango quedaba sobre los nudillos."""
        R = self.rig
        pts = []
        for a, b in self.spec["fingers"][k]:
            if a not in R.rest or b not in R.rest or a not in curl:
                continue
            B = R.rest[a].translation
            ax0, an0 = curl[a]
            Q0 = Matrix.Rotation(an0, 3, rot3(R.rest[a]) @ ax0)
            M = B + Q0 @ (R.rest[b].translation - B)
            ax1, an1 = curl.get(b, (Vector((1, 0, 0)), 0.0))
            Q1 = Matrix.Rotation(an1, 3, Q0 @ rot3(R.rest[b]) @ ax1)
            tip = R.rest[b] @ Vector((0.0, R.length[b], 0.0))
            T = M + Q1 @ Q0 @ (tip - R.rest[b].translation)
            pts += [B, M, T]
        palm = self.head(h) + fdir * (hand_len * 0.85)
        if not pts:
            return palm + n * (hand_len * 0.25)
        c = sum(pts, Vector()) / len(pts)
        return (c * 3.0 + palm) / 4.0

    def finger_axes(self, k, palm_n):
        """Eje de cierre de cada falange (espacio local del hueso): la punta va hacia la palma."""
        R = self.rig
        out = {}
        chains = [(c, GRIP_CURL) for c in self.spec["fingers"][k]] + [(self.spec["thumb"][k], THUMB_CURL)]
        for chain, angs in chains:
            for i, b in enumerate(chain):
                if b not in R.rest:
                    continue
                d = rot3(R.rest[b]).col[1].normalized()
                ax = d.cross(palm_n)
                if ax.length < 1e-4:
                    continue
                ax.normalize()
                # rota d hacia la palma: (eje x d) tiene que apuntar hacia n
                if ax.cross(d).dot(palm_n) < 0:
                    ax = -ax
                out[b] = (rot3(R.rest[b]).transposed() @ ax, math.radians(angs[min(i, 1)]))
        return out

    def measure_katana(self, w):
        """Eje de la hoja y del filo medidos en la malla de la katana, en el espacio de la mano."""
        k = w["hand"]
        h = self.side[k]["hand"]
        o = bpy.data.objects[w["mesh"]]
        dg = bpy.context.evaluated_depsgraph_get()
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        mats = [m.name if m else "" for m in me.materials]
        vs = [self.Ai @ (oe.matrix_world @ v.co) for v in me.vertices]
        hand0 = self.head(h)
        tip = max(vs, key=lambda v: (v - hand0).length)
        pom = min(vs, key=lambda v: (v - tip).length * -1.0)     # el más lejano a la punta: el pomo
        axis = (tip - pom).normalized()
        glint = Vector()
        for p in me.polygons:
            if mats[p.material_index] == "Glint":
                glint += (rot3(oe.matrix_world) @ p.normal) * p.area
        oe.to_mesh_clear()
        glint = rot3(self.Ai) @ glint
        edge = (glint - axis * glint.dot(axis)).normalized()
        # punto del mango que agarra el puño: el más cercano del eje al centro del puño de reposo
        fist_arm = self.rig.rest[h] @ self.hand_info[k]["fist"]
        t = (fist_arm - pom).dot(axis)
        grip = pom + axis * t
        Rh0 = rot3(self.rig.rest[h])
        F0 = basis_yz(axis, edge)
        # el hueso de la katana respecto del marco de la hoja (giro y cabeza desde el agarre): se anima aparte de la mano,
        # así la hoja queda donde la pide el clip aunque el puño ruede sobre el mango (team_limbs)
        B0 = self.rig.rest[w["bone"]]
        # el mango va en el hueco del puño (grip_local): en el reposo del equipo la katana está bajo los dedos de la mano
        # abierta, 3 cm más allá de donde cierra el puño
        return dict(kind="katana", hand=k, K=F0.transposed() @ Rh0, grip_local=self.hand_info[k]["fist"].copy(),
                    KB=F0.transposed() @ rot3(B0), hb=F0.transposed() @ (B0.translation - grip),
                    tip_local=self.rig.rest_inv[w["bone"]] @ tip, length=(tip - grip).length / self.u,
                    pommel_back=(grip - pom).length / self.u)

    def measure_club(self, w):
        """El martillo de Gorō cuelga de un hueso suelto ('BaseM'): el mango es su eje Y, la cabeza sale hacia +X
        del mundo en reposo. Agarre1 (abajo) y Agarre2 (arriba) son los dos puntos de agarre."""
        R = self.rig
        b = w["bone"]
        RB0 = rot3(R.rest[b])
        haft0 = RB0.col[1].normalized()
        o = bpy.data.objects[w["mesh"]]
        dg = bpy.context.evaluated_depsgraph_get()
        oe = o.evaluated_get(dg)
        me = oe.to_mesh()
        vs = [self.Ai @ (oe.matrix_world @ v.co) for v in me.vertices]
        oe.to_mesh_clear()
        base = self.head(b)
        ts = [(v - base).dot(haft0) for v in vs]
        far = max(ts)
        # la cabeza: los vértices del último tercio del largo; su eje es la dirección de mayor extensión
        head_vs = [v for v, t in zip(vs, ts) if t > far - 1.2 * self.u]
        c = sum(head_vs, Vector()) / len(head_vs)
        ext = max(head_vs, key=lambda v: ((v - c) - haft0 * (v - c).dot(haft0)).length)
        face0 = (ext - c) - haft0 * (ext - c).dot(haft0)
        face0.normalize()
        F0 = basis_yz(haft0, face0)
        g1, g2 = (self.head(n) for n in w["grips"])
        tips = sorted(vs, key=lambda v: (v - base).dot(haft0))
        return dict(kind="club", K=F0.transposed() @ RB0, base_local=Vector(), grips=[(g - base).dot(haft0) / self.u for g in (g1, g2)],
                    head_center=(c - base).dot(haft0) / self.u, head_radius=max(((v - c) - haft0 * (v - c).dot(haft0)).length for v in head_vs) / self.u,
                    butt=(tips[0] - base).dot(haft0) / self.u, top=(tips[-1] - base).dot(haft0) / self.u)

    def sample_kidnapper(self):
        """Pose (espacio de armadura) de los huesos del ninja del secuestro en el cuadro pedido de la toma del equipo."""
        kd = self.spec["kidnapper"]
        arm = self.arm
        acts = [a for a in bpy.data.actions]
        if not acts:
            return {}
        import charlib as C
        C.use_action(arm, acts[0])
        bpy.context.scene.frame_set(kd["take_frame"])
        bpy.context.view_layer.update()
        out = {pb.name: pb.matrix.copy() for pb in arm.pose.bones if pb.name.endswith(kd["suffix"])}
        return out

    def straighten_kid_hands(self, kp):
        """La pose fija del ninja del secuestro (cuadro de la toma del equipo) con las muñecas dentro de lo posible:
        en esa toma la mano seguía al control de IK sin mirar el antebrazo (la derecha, 35° pasada del borde). Se
        endereza como una mano libre de team_limbs (hasta FREE_BEND) y los dedos la siguen."""
        kid = self.partner
        R = self.rig
        out = dict(kp)
        for k in "rl":
            arm = TL.Arm(kid, k)
            H = out[arm.hand]
            Rh2 = TL.ArmSolver.straighten(None, arm, rot3(out[arm.fore]), rot3(H), TL.FREE_BEND)
            Dm = compose(H.translation, Rh2) @ H.inverted()
            for n in R.names:
                p = R.parent.get(n)
                while p is not None and p != arm.hand:
                    p = R.parent.get(p)
                if (n == arm.hand or p == arm.hand) and n in out:
                    out[n] = Dm @ out[n]
        return out

    def report(self):
        r = {k: [round(x, 3) for x in v] if isinstance(v, Vector) else v for k, v in self.land.items()}
        r["u"] = round(self.u, 4)
        r["leg_len"] = {k: round(v, 3) for k, v in self.leg_len.items()}
        r["arm_len"] = {k: round(v, 3) for k, v in self.arm_len.items()}
        if self.weapon_info:
            r["weapon"] = {k: (round(v, 3) if isinstance(v, float) else [round(x, 3) for x in v] if isinstance(v, list) else None)
                           for k, v in self.weapon_info.items() if isinstance(v, (float, list))}
        return r


# =============================================================================== resolución de controles
class TeamSolver:
    """Traduce los controles de un cuadro (marco de autoría) a la pose de todos los huesos del personaje.

    Controles (todos opcionales; lo que falta queda en reposo):
      hips (m, desde el reposo), hips_rot, spine, chest, head, clav_r/l (grados)
      foot_r/l (tobillo, m absolutos), foot_r/l_rot (grados sobre el pie de reposo), knee_r/l (dirección)
      hand_r/l (muñeca, m absolutos), hand_r/l_dir (hacia dónde apuntan los dedos), hand_r/l_palm (normal
      de la palma), elbow_r/l (dirección), fist_r/l (0 abierta .. 1 puño)
      katana: grip (punto del mango en el puño), blade, edge (direcciones); grip_l > 0 lleva la izquierda al mango
      martillo: grip (mano derecha en el mango), haft (del extremo a la cabeza), face (cara de la cabeza que
      golpea), grip_l (0..1 la izquierda en el mango), slide_r/l (dónde agarra cada mano, m desde Agarre2/Agarre1)
      travel (m que avanzó el transform del juego: lo apoyado en el mundo se corre para atrás), breath (0..1)
      extra {hueso: grados} para lo que no tiene control propio."""

    def __init__(self, ch):
        self.ch = ch
        self.rig = ch.rig
        self.misses = {}
        self.hip_drop = 0.0
        self.limbs = TL.ArmSolver(ch, self)
        self._partner = None

    def partner_solver(self):
        """El TeamSolver del segundo esqueleto del FBX (ver TeamChar.partner), creado la primera vez."""
        if self._partner is None:
            self._partner = TeamSolver(self.ch.partner)
        return self._partner

    # ---------------------------------------------------------------- piezas
    def hand_frame(self, k, d, palm):
        """Giro de la mano con los dedos hacia 'd' y la palma hacia 'palm' (marco de autoría). El marco (dedos, índice,
        palma) se arma con la misma orientación que M0 (lat = chi * dedos x palma): con palma x dedos salía espejado
        (determinante -1) y la mano se exportaba doblada 180° sobre el antebrazo."""
        hi = self.ch.hand_info[k]
        fd = self.ch.D(d)
        n = self.ch.D(palm)
        n = (n - fd * n.dot(fd)).normalized()
        lat = fd.cross(n) * hi["chi"]
        M = Matrix((fd, lat, n)).transposed()
        return M @ hi["M0"].transposed() @ hi["Rh0"]

    def grip_frame(self, k, haft_arm, shoulder_arm, stick_pt, flip=False):
        """Mano cerrada sobre un mango: los nudillos cruzan el palo apuntando lejos del hombro, el índice hacia la
        cabeza del arma (team_limbs la hace rodar alrededor del mango hasta que la muñeca queda cómoda). 'flip': el
        meñique hacia la cabeza, como quien se apoya en un bastón (Gorō arrodillado con el martillo en el piso)."""
        hi = self.ch.hand_info[k]
        hv = -haft_arm.normalized() if flip else haft_arm.normalized()
        fd = stick_pt - shoulder_arm
        fd = fd - hv * fd.dot(hv)
        if fd.length < 1e-5:
            fd = hv.orthogonal()
        fd.normalize()
        lat = hv
        n = lat.cross(fd) * hi["chi"]
        M = Matrix((fd, lat, n.normalized())).transposed()
        Rh = M @ hi["M0"].transposed() @ hi["Rh0"]
        wrist = stick_pt - Rh @ (hi["fist"] - Vector())     # fist está en el espacio de la mano (origen en la muñeca)
        return compose(wrist, Rh)

    def hold(self, k, axis, pivot, roll, soft, diag, bend=None, reach=1.0, look=0.0, loose=0.0, frame=None, diag0=0.0):
        """Agarre de un mango para team_limbs: la mano puede rodar alrededor de 'axis' por 'pivot' (hasta 'roll' grados,
        con un costo que crece en 'soft') y girar en diagonal alrededor de la normal de su palma. 'bend': si igual no
        entra, la muñeca se endereza hasta ese exceso y el arma la sigue (la katana, el martillo); 'reach' (m, del puño a
        la punta o a la cabeza) dice cuánto se corre lo que se ve del arma por cada grado; 'look' (0..1, el canal del
        clip) marca los cuadros que se leen (el aviso, la pausa y el golpe): ahí correr el arma cuesta cuatro veces más;
        'loose' (0..1) es la mano que afloja el mango para cambiar de agarre: se endereza sin llevarse el arma. 'frame': el
        giro pedido del arma; con él team_limbs mide los saltos del brazo contra lo que se movió el arma (la referencia
        del agarre de un mango puede girar sola, ver grip_frame) y no contra la mano pedida."""
        return dict(axis=V(axis).normalized(), pivot=V(pivot), palm=self.limbs.arms[k].n, roll=roll, soft=soft, diag=diag, diag0=diag0,
                    bend=bend is not None, bend_to=bend or 0.99, reach=reach, look=look, loose=loose,
                    frame=frame.to_quaternion() if frame is not None else None)

    def partial_hold(self, k, axis, H, gl, soft, diag, diag0=0.0):
        """La otra mano yendo al mango (grip_l entre 0 y 1): rueda alrededor de él por donde quedó el puño, con un giro
        que vuelve a cero a medida que suelta (si no, al soltar el agarre la mano perdía de golpe lo que había rodado y el
        antebrazo daba media vuelta en un cuadro) y, mientras no agarra del todo, puede enderezarse (se acerca al mango)."""
        return self.hold(k, axis, H @ self.ch.hand_info[k]["fist"], 180.0, soft * max(gl, 0.05), diag * gl,
                         bend=None if gl >= 0.75 else 0.99, diag0=diag0 * gl)

    def place_hand(self, pose, k, H, pole_c, hold=None):
        """Brazo y mano con la muñeca posible (team_limbs.ArmSolver). Devuelve cuánto faltó para llegar (m de la
        armadura; si el brazo no llega la mano queda donde se pidió, despegada eso)."""
        ch, R = self.ch, self.rig
        d = ch.side[k]
        miss, H, H0 = self.limbs.place(pose, k, H, ch.D(pole_c), hold)
        # lo que se enderezó la muñeca (la katana lo sigue)
        self.bent = H @ H0.inverted()
        if d["hand_ctrl"]:
            pose.place(d["hand_ctrl"], H @ R.rel[d["hand"]].inverted())
        pose.place(d["hand"], H)
        return miss

    def reach_with_clavicle(self, pose, k, target, max_deg=20.0):
        """Si la muñeca no llega, la clavícula gira hacia el objetivo (la escápula al estirarse)."""
        R = self.rig
        d = self.ch.side[k]
        cl, ua, fa = d["clav"], d["upper"], d["fore"]
        reach = (R.length[ua] + R.length[fa]) * 0.985
        for _ in range(2):
            sh = (pose.get(cl) @ R.rel[ua]).translation
            ex = (V(target) - sh).length - reach
            if ex <= 0.0:
                return
            c0 = pose.head(cl)
            a, b = sh - c0, V(target) - c0
            ax = a.cross(b)
            if ax.length < 1e-6:
                return
            ang = min(ex / max(a.length, 1e-3), math.radians(max_deg))
            M = pose.get(cl)
            pose.place(cl, compose(c0, Quaternion(ax.normalized(), ang).to_matrix() @ rot3(M)))

    def curl(self, pose, k, amount):
        if amount <= 1e-4:
            return
        R = self.rig
        for b, (ax, ang) in self.ch.hand_info[k]["curl"].items():
            p = R.parent[b]
            Wb = pose.get(p) @ R.rel[b] @ Matrix.Rotation(ang * amount, 4, ax)
            pose.place(b, Wb)

    # ---------------------------------------------------------------- cuadro completo
    def solve(self, pose, c):
        if c.get("take") is not None:
            return self.solve_take(pose, c)
        ch, R = self.ch, self.rig
        sp = ch.spec
        g = lambda k, dflt=None: c.get(k) if c.get(k) is not None else dflt
        travel = g("travel", 0.0)
        # lo clavado en el mundo (pies) se autora en el mundo: en el clip se corre lo que avanzó el transform
        sh = ch.travel_axis * travel
        # ---- cadera
        prest = R.rest[sp["pelvis"]]
        Hm = compose(prest.translation + ch.offset_arm(g("hips", (0, 0, 0))),
                     ch.Q(g("hips_rot", (0, 0, 0))).to_matrix() @ rot3(prest))
        feet = {}
        for k in "rl":
            d = ch.side[k]
            fi = ch.foot_info[k]
            ank = g("foot_" + k)
            if ank is None:
                ank = ch.land["ankle_" + k]
            fr = g("foot_%s_rot" % k, (0, 0, 0))
            Rf = ch.Q(fr).to_matrix() @ fi["Rf0"]
            F = compose(ch.P(V(ank) + sh), Rf)
            feet[k] = F
        drop = 0.0
        if g("auto_drop", 1.0) > 0.5:
            for k in "rl":
                d = ch.side[k]
                J = (Hm @ R.rel[d["thigh"]]).translation
                A_ = feet[k] @ ch.foot_info[k]["shin_tail_local"]
                reach = (R.length[d["thigh"]] + R.length[d["shin"]]) * 0.985
                dxy = Vector((J.x - A_.x, J.y - A_.y, J.z - A_.z))
                # la caída se mide en el eje 'arriba' del personaje (Z del mundo; las armaduras no están giradas)
                hor = Vector((dxy.x, dxy.y, 0.0)).length
                if hor < reach:
                    need = dxy.z - math.sqrt(reach * reach - hor * hor)
                    drop = max(drop, need)
        if drop > 0.0:
            Hm.translation.z -= drop
        self.hip_drop = drop / ch.u
        pose.place(sp["pelvis"], Hm)
        # ---- tronco y cabeza
        br = g("breath", 0.0)
        qs = ch.Q(V(g("spine", (0, 0, 0))))
        qc = ch.Q(V(g("chest", (0, 0, 0))) + Vector((-2.0 * br, 0.0, 0.0)))
        if sp["chest"]:
            pose.delta(sp["spine"][0], qs)
            pose.delta(sp["chest"][0], qc)
        else:
            pose.delta(sp["spine"][0], qc @ qs)
        pose.delta(sp["head"], ch.Q(V(g("head", (0, 0, 0))) + Vector((1.2 * br, 0.0, 0.0))))
        for k in "rl":
            sgn = -1.0 if k == "r" else 1.0
            pose.delta(ch.side[k]["clav"], ch.Q(V(g("clav_" + k, (0, 0, 0))) + Vector((0.0, sgn * 1.4 * br, 0.0))))
        # ---- brazos
        misses = {}
        w = ch.weapon_info
        poles = {k: g("elbow_" + k, ARM_POLE[k]) for k in "rl"}
        if w and w["kind"] == "katana":
            k = w["hand"]
            blade, edge = ch.D(g("blade", (0, -1, 0.3))), ch.D(g("edge", (0, -0.3, -1)))
            Fk = basis_yz(blade, edge - blade * edge.dot(blade))
            grip = ch.P(g("grip", ch.land["wrist_" + k]))
            # el agarre ideal (la relación mano-hoja del modelo); team_limbs lo hace rodar en el mango y, si la muñeca
            # igual no da, la endereza llevándose la hoja ('bent': lo que giró, para la katana y la otra mano)
            Rh = Fk @ w["K"]
            ideal = compose(grip - Rh @ w["grip_local"], Rh)
            hold = self.hold(k, Fk.col[1], grip, TL.KATANA_ROLL, TL.KATANA_SOFT, TL.KATANA_DIAG, bend=TL.KATANA_BEND,
                             reach=w["length"], look=g("look", 0.0), frame=Fk, diag0=TL.KATANA_DIAG0)
            misses["hand_" + k] = self.place_hand(pose, k, ideal, poles[k], hold)
            self.curl(pose, k, g("fist_" + k, 1.0))
            bent = self.bent
            pose.place(sp["weapon"]["bone"], bent @ compose(grip + Fk @ w["hb"], Fk @ w["KB"]))
            o = "l" if k == "r" else "r"
            H = self.free_hand(pose, c, o, poles[o])
            gl = g("grip_l", 0.0)
            hold = None
            if gl > 1e-3:
                # la otra mano va al mango de la hoja que quedó: espejo del agarre ideal de la del arma
                Hg = self.katana_left(bent @ ideal)
                H = compose(H.translation.lerp(Hg.translation, gl), H.to_quaternion().slerp(Hg.to_quaternion(), gl).to_matrix())
                hold = self.partial_hold(o, rot3(bent) @ Fk.col[1], H, gl, TL.KATANA_SOFT, TL.KATANA_DIAG, TL.KATANA_LDIAG0)
            misses["hand_" + o] = self.place_hand(pose, o, H, poles[o], hold)
            self.curl(pose, o, g("fist_" + o, 0.0))
        elif w and w["kind"] == "club":
            haft = ch.D(g("haft", (0, 0, 1)))
            face = ch.D(g("face", (0, -1, 0)))
            face = (face - haft * face.dot(haft)).normalized()
            RB = basis_yz(haft, face) @ w["K"]
            # 'grip' es la mano derecha; la base del mango queda 'slide_r' más abajo de Agarre2
            grip_r = ch.P(g("grip", (0, -0.6, 1.4)))
            t_r = w["grips"][1] - g("slide_r", 0.0)
            base = grip_r - haft * (t_r * ch.u)
            # la derecha manda (como la mano de la katana): rueda en el mango y, si la muñeca igual no da, se endereza y
            # el martillo la sigue; la izquierda agarra el mango donde quedó
            sh_r = (pose.get(ch.side["r"]["clav"]) @ R.rel[ch.side["r"]["upper"]]).translation
            # 'grip_r' < 1 afloja la derecha para cambiar de agarre: entre dos agarres que la muñeca no une (Gorō que
            # vuelve del golpe sísmico con el antebrazo de supinación a pronación) la mano puede enderezarse y girar en el
            # mango sin llevarse el martillo
            gr = max(0.0, min(1.0, g("grip_r", 1.0)))
            hold = self.hold("r", haft, grip_r, TL.CLUB_ROLL, TL.CLUB_SOFT, TL.CLUB_DIAG,
                             bend=TL.CLUB_BEND + (0.99 - TL.CLUB_BEND) * (1.0 - gr), reach=w["head_center"] - t_r, look=g("look", 0.0),
                             loose=1.0 - gr, frame=RB)
            flip = g("grip_flip", 0.0) > 0.5
            dr = max(0.0, min(1.0, g("drop_r", 0.0)))
            if dr > 1e-3:
                # 'drop_r' 0..1: la derecha SUELTA el mango y va a donde la piden hand_r/_dir/_palm (mano libre); el martillo
                # queda donde lo ponen grip/haft/face, sin mano (BaseM se anima aparte de Mano.R). Gorō al desplomarse: con
                # el puño todavía en el mango, el hombro que cae pasaba a 5 cm de la mano y el brazo se plegaba del todo
                # (mientras suelta, rueda sobre el puño como la otra mano que va al mango: así arranca del agarre que tenía y
                # no del ideal, que con la mano enorme de Gorō estaba a 36 cm)
                Hg = self.grip_frame("r", haft, sh_r, grip_r, flip)
                Hf = self.free_hand(pose, c, "r", poles["r"])
                H = compose(Hg.translation.lerp(Hf.translation, dr), Hg.to_quaternion().slerp(Hf.to_quaternion(), dr).to_matrix())
                hold = self.partial_hold("r", haft, H, 1.0 - dr, TL.CLUB_SOFT, TL.CLUB_DIAG) if dr < 0.999 else None
                misses["hand_r"] = self.place_hand(pose, "r", H, poles["r"], hold)
                self.curl(pose, "r", g("fist_r", 1.0))
                bent = Matrix.Identity(4)
                Bw = compose(base, RB)
            else:
                misses["hand_r"] = self.place_hand(pose, "r", self.grip_frame("r", haft, sh_r, grip_r, flip), poles["r"], hold)
                self.curl(pose, "r", g("fist_r", 1.0))
                bent = self.bent
                if gr < 0.999:
                    bent = compose(bent.translation * gr, Quaternion().slerp(bent.to_quaternion(), gr).to_matrix())
                Bw = bent @ compose(base, RB)
            pose.place(sp["weapon"]["bone"], Bw)
            base, haft = Bw.translation.copy(), (rot3(bent) @ haft).normalized()
            self.club = (base, haft, (rot3(bent) @ face).normalized())
            gl = g("grip_l", 1.0)
            H = self.free_hand(pose, c, "l", poles["l"])
            hold = None
            if gl > 1e-3:
                t_l = w["grips"][0] + g("slide_l", 0.0)
                stick = base + haft * (t_l * ch.u)
                sh_l = (pose.get(ch.side["l"]["clav"]) @ R.rel[ch.side["l"]["upper"]]).translation
                Hg = self.grip_frame("l", haft, sh_l, stick, g("grip_flip_l", 0.0) > 0.5)
                H = compose(H.translation.lerp(Hg.translation, gl), H.to_quaternion().slerp(Hg.to_quaternion(), gl).to_matrix())
                hold = self.partial_hold("l", haft, H, gl, TL.CLUB_SOFT, TL.CLUB_DIAG)
            misses["hand_l"] = self.place_hand(pose, "l", H, poles["l"], hold)
            self.curl(pose, "l", g("fist_l", 1.0))
        else:
            for k in "rl":
                misses["hand_" + k] = self.place_hand(pose, k, self.free_hand(pose, c, k, poles[k]), poles[k])
                self.curl(pose, k, g("fist_" + k, 0.0))
        # ---- piernas
        ml = 0.0
        for k in "rl":
            d = ch.side[k]
            F = feet[k]
            tgt = F @ ch.foot_info[k]["shin_tail_local"]
            ml = max(ml, pose.two_bone(d["thigh"], d["shin"], tgt, ch.D(g("knee_" + k, (0, -1, 0)))))
            if d["foot_ctrl"]:
                pose.place(d["foot_ctrl"], F @ R.rel[d["foot"]].inverted())
            pose.place(d["foot"], F)
        misses["legs"] = ml
        # ---- huesos que siguen rígidos a otro (polos que todavía pesan vértices)
        for b, t in sp["follow"].items():
            if b in R.rest and b in ch.weighted:
                pose.place(b, pose.get(t) @ R.rest_inv[t] @ R.rest[b])
        for b, M in ch.kid_pose.items():
            pose.place(b, M)
        for bn, r in sorted((g("extra", {}) or {}).items(), key=lambda kv: R.names.index(kv[0])):
            pose.delta(bn, ch.Q(V(r)))
        self.misses = misses
        return misses

    def solve_take(self, pose, c):
        """Un cuadro de una toma del equipo (TakeClip) con las muñecas arregladas: todo el cuerpo queda como en la toma y
        solo se vuelven a resolver los brazos con team_limbs (la mano donde la puso la toma, el codo hacia donde estaba).
        La mano que sostiene el martillo rueda en su mango y, si igual no entra, se endereza llevándose el martillo, como en
        los clips nuevos; la otra agarra el mango si en la toma lo agarraba (a menos de TAKE_GRIP del eje) o queda libre.
        Los huesos que cuelgan del brazo (dedos) conservan lo local de la toma."""
        ch, R = self.ch, self.rig
        take = c["take"]
        for n in R.names:
            pose.place(n, take[n])
        if c.get("take_raw"):
            # la toma tal cual (para comparar con lo re-resuelto)
            self.hip_drop, self.misses = 0.0, {"legs": 0.0, "hand_r": 0.0, "hand_l": 0.0}
            return self.misses
        w = ch.weapon_info
        wb = ch.spec["weapon"]["bone"] if w else None
        misses = {"legs": 0.0}
        placed = set()
        bent = Matrix.Identity(4)

        def pole_of(k):
            d = ch.side[k]
            S, E, Hh = (take[d[r]].translation for r in ("upper", "fore", "hand"))
            ax = Hh - S
            q = (E - S) - ax * ((E - S).dot(ax) / max(ax.length_squared, 1e-12))
            return tuple(ch.Dc(q if q.length > 1e-6 else (E - S)))

        for k in "rl":
            d = ch.side[k]
            H = take[d["hand"]]
            hold = None
            if w and w["kind"] == "club":
                B = bent @ take[wb]
                base, haft = B.translation, rot3(B).col[1].normalized()
                fist = (bent @ H) @ ch.hand_info[k]["fist"]
                t = (fist - base).dot(haft)
                gap = (base + haft * t - fist).length / ch.u
                if k == "r":
                    hold = self.hold("r", haft, base + haft * t, TL.CLUB_ROLL, TL.CLUB_SOFT, TL.CLUB_DIAG, bend=TL.CLUB_BEND,
                                     reach=max(0.2, w["head_center"] - t / ch.u), frame=rot3(B))
                elif gap < TAKE_GRIP:
                    # el puño de la toma se cierra sobre el mango (la IK del equipo dejaba la palma atravesada por el palo)
                    sh = (pose.get(d["clav"]) @ R.rel[d["upper"]]).translation
                    H = self.grip_frame("l", haft, sh, base + haft * t)
                    hold = self.partial_hold("l", haft, H, 1.0, TL.CLUB_SOFT, TL.CLUB_DIAG)
                # lo que agarra cada mano, para los chequeos del puño en el mango
                c["grip_" + k] = 1.0 if hold is not None else 0.0
            misses["hand_" + k] = self.place_hand(pose, k, H, pole_of(k), hold)
            placed |= {d["upper"], d["fore"], d["hand"]}
            if w and w["kind"] == "club" and k == "r":
                bent = self.bent
                pose.place(wb, bent @ take[wb])
                placed.add(wb)
        # lo que cuelga de los brazos sigue a su padre con lo local de la toma
        for k in "rl":
            for b in R.subtree(ch.side[k]["upper"]):
                if b in placed:
                    continue
                p = R.parent[b]
                pose.place(b, pose.get(p) @ take[p].inverted() @ take[b])
        self.hip_drop = 0.0
        self.misses = misses
        return misses

    def free_hand(self, pose, c, k, pole_c):
        """Mano libre: muñeca en 'hand_k'. Con dirección y palma, ese marco; con solo la dirección, el giro mínimo desde
        la mano neutra; sin ninguna, la neutra (la mano sigue al antebrazo, la muñeca derecha). La neutra sale del brazo
        resuelto hacia el polo pedido (team_limbs después elige el codo y endereza lo que no entre). Una palma casi paralela
        a los dedos se mezcla con el giro mínimo."""
        ch = self.ch
        pos = c.get("hand_" + k)
        if pos is None:
            pos = ch.land["wrist_" + k]
        d, n = c.get("hand_%s_dir" % k), c.get("hand_%s_palm" % k)
        p = ch.P(pos)
        N = self.neutral_hand(pose, k, p, ch.D(pole_c))
        if d is None:
            return compose(p, N)
        hi = ch.hand_info[k]
        cur = (N @ hi["Rh0"].transposed() @ hi["M0"].col[0]).normalized()
        Hd = cur.rotation_difference(ch.D(d)).to_matrix() @ N
        if n is None:
            return compose(p, Hd)
        # la palma pedida casi paralela a los dedos no dice nada del giro (y entre dos claves, cada canal interpolado por
        # su lado, pasa por ahí: la mano daba media vuelta en un cuadro): se mezcla con la de giro mínimo según cuánto
        # de la palma queda perpendicular a los dedos
        fd, pn = Vector(d).normalized(), Vector(n).normalized()
        w = (pn - fd * pn.dot(fd)).length
        Hf = self.hand_frame(k, d, n)
        if w >= 0.5:
            return compose(p, Hf)
        u = max(0.0, min(1.0, (w - 0.15) / 0.35))
        u = u * u * (3.0 - 2.0 * u)
        return compose(p, Hd.to_quaternion().slerp(Hf.to_quaternion(), u).to_matrix())

    def neutral_hand(self, pose, k, p, pole):
        """Giro de la mano que deja la muñeca neutra con el brazo resuelto hacia 'pole' (sin tocar la pose)."""
        arm = self.limbs.arms[k]
        R = self.rig
        Pc = pose.get(arm.clav) @ R.rel[arm.upper]
        Fu0 = rot3(Pc)
        _, Rl, _, _ = TL.two_bone(Pc.translation, arm.a, arm.b, Fu0, Fu0 @ rot3(R.rel[arm.fore]), p, pole)
        return Rl @ arm.rel0

    def katana_left(self, Hr):
        """Mano izquierda en el mango: espejo de la derecha respecto del plano de la hoja, más cerca del pomo."""
        ch = self.ch
        w = ch.weapon_info
        k = w["hand"]
        grip = Hr @ w["grip_local"]
        Rr = rot3(Hr)
        Fk = Rr @ w["K"].transposed()
        blade = Fk.col[1]
        X = Fk.col[0]
        S = Matrix.Identity(3) - 2.0 * Matrix(((X.x * X.x, X.x * X.y, X.x * X.z), (X.y * X.x, X.y * X.y, X.y * X.z), (X.z * X.x, X.z * X.y, X.z * X.z)))
        hl, hr = ch.hand_info["l"], ch.hand_info[k]
        # la izquierda es la derecha reflejada: su marco (dedo, índice, palma) es el reflejo del de la derecha, que ya
        # tiene la orientación de M0 de la izquierda (los dos lados del modelo son espejo). Solo si no la tuviera se da
        # vuelta el índice: forzar el determinante +1 (como antes) dejaba la mano izquierda espejada en el ninja
        Mr = Rr @ hr["Rh0"].transposed() @ hr["M0"]
        Ml = S @ Mr
        if Ml.determinant() * hl["M0"].determinant() < 0:
            Ml = Matrix((Ml.col[0], -Ml.col[1], Ml.col[2])).transposed()
        Rl = Ml @ hl["M0"].transposed() @ hl["Rh0"]
        g_l = grip - blade * (0.11 * ch.u)
        fist = hl["fist"]
        return compose(g_l - Rl @ fist, Rl)


# =============================================================================== pasos
class FootKey:
    """Un pie en el piso del mundo en el cuadro 'frame': (x, y) del tobillo con el pie plano, punta girada 'yaw',
    'pitch' > 0 talón arriba (rueda sobre la punta) / < 0 punta arriba (sobre el talón), 'z' lo despega entero.
    El tramo que TERMINA acá usa 'ease' (inout: sale y llega quieto en el mundo, sin patinar) y, si el pie se
    traslada, sube en arco 'lift' m (por defecto un tercio de lo que recorre, hasta 8 cm): nunca se arrastra."""

    def __init__(self, frame, x, y, yaw=0.0, pitch=0.0, z=0.0, roll=0.0, ease="inout", lift=None):
        self.frame, self.x, self.y, self.yaw, self.pitch, self.z, self.roll = frame, x, y, yaw, pitch, z, roll
        self.ease, self.lift = ease, lift


def sample_feet(ch, k, track, f):
    ks = track
    if f <= ks[0].frame:
        a = b = ks[0]
        s = u = 0.0
    elif f >= ks[-1].frame:
        a = b = ks[-1]
        s = u = 1.0
    else:
        i = max(j for j in range(len(ks) - 1) if ks[j].frame <= f)
        a, b = ks[i], ks[i + 1]
        u = (f - a.frame) / max(1e-6, b.frame - a.frame)
        s = NA.ease(b.ease, u)
    lerp = lambda p, q: p + (q - p) * s
    d = math.hypot(b.x - a.x, b.y - a.y)
    lift = b.lift if b.lift is not None else (min(0.08, d / 3.0) if d > 0.01 else 0.0)
    # el arco va con el tiempo, no con la curva: con 'out' el pie llega adelante enseguida y baja vertical (no roza)
    z = lerp(a.z, b.z) + lift * math.sin(math.pi * u)
    return ch.foot_at(k, lerp(a.x, b.x), lerp(a.y, b.y), lerp(a.yaw, b.yaw), lerp(a.pitch, b.pitch), lerp(a.roll, b.roll), z)


def gait2(ch, frames, speed, duty, feet, lift=0.08, toe_off=30.0, heel=-14.0, phase_l=0.5, swing_ease="inout"):
    """Ciclo de locomoción en el lugar (el transform del juego avanza 'speed' m/s) con los pies clavados en el MUNDO:
    el apoyado no se mueve (en el clip va para atrás exactamente a la velocidad del suelo), apoya de talón y rueda
    hasta quedar plano, despega rodando sobre la punta, y el vuelo va de un apoyo al siguiente saliendo y llegando
    quieto en el mundo (sin el resbalón del pie que aterriza todavía yendo para adelante).
    feet = {k: (x, y medio del apoyo, yaw)}. Devuelve fn(f) -> {foot_k, foot_k_rot}."""
    T = frames / FPS
    stride = speed * T

    def one(k, f):
        x, ym, yaw = feet[k]
        p = ((f / frames) + (phase_l if k == "l" else 0.0)) % 1.0
        if p < duty:
            y = ym + stride * (p - duty * 0.5)
            hs, to = 0.14 * duty, 0.62 * duty
            if p < hs:
                pitch = heel * (1.0 - NA.ease("out2", p / hs))
            elif p > to:
                pitch = toe_off * NA.ease("in2", (p - to) / (duty - to))
            else:
                pitch = 0.0
            return ch.foot_at(k, x, y, yaw, pitch)
        q = (p - duty) / (1.0 - duty)
        s = NA.ease(swing_ease, q)
        y0 = ym + stride * duty * 0.5
        y = y0 + speed * T * (1.0 - duty) * q - stride * s
        z = lift * math.sin(math.pi * q) ** 0.8
        pitch = toe_off * (1.0 - s) + heel * s
        return ch.foot_at(k, x, y, yaw, pitch, 0.0, z)

    def fn(f):
        out = {}
        for k in "rl":
            out["foot_" + k], out["foot_%s_rot" % k] = one(k, f)
        return out
    return fn


# =============================================================================== horneado
def bake(ch, clip, solver):
    """Resuelve todos los cuadros: (poses W, controles, desplazamiento del transform del juego en la armadura,
    caída automática de cadera por cuadro, faltas de alcance)."""
    frames, ctrls, roots, drops, misses = [], [], [], [], []
    clip.ch = ch
    # el segundo esqueleto del FBX (clip.partner, del mismo largo, autorado para ch.partner) se resuelve en la misma
    # pose después del primero: lo que no pide queda en la pose fija de kid_pose
    duo = getattr(clip, "partner", None)
    ps = None
    if duo is not None:
        ps = solver.partner_solver()
        duo.ch = ch.partner
        duo.ctrls, duo.drops, duo.misses = [], [], []
    # dos pasadas (team_limbs.ArmSolver): la primera junta las soluciones posibles de cada brazo en cada cuadro y elige el
    # camino del clip entero (en un loop, cerrado sobre sí mismo: la costura no salta); la segunda lo aplica
    sols = [(solver, clip)] + ([(ps, duo)] if ps else [])
    for sv, _ in sols:
        sv.limbs.begin("collect")
    for f in range(clip.frames if clip.loop else clip.frames + 1):
        pose = NA.Pose(ch.rig)
        for sv, cl in sols:
            sv.solve(pose, cl.controls(f))
    for sv, _ in sols:
        sv.limbs.plan_path(clip.loop)
        sv.limbs.begin("replay")
    for f in range(clip.frames + 1):
        c = clip.controls(f)
        pose = NA.Pose(ch.rig)
        m = solver.solve(pose, c)
        if ps:
            dc = duo.controls(f)
            duo.misses.append(dict(ps.solve(pose, dc)))
            duo.ctrls.append(dc)
            duo.drops.append(ps.hip_drop)
        for n in ch.rig.names:
            pose.get(n)
        frames.append(pose.W)
        ctrls.append(c)
        roots.append(ch.offset_arm((0.0, -(c.get("travel") or 0.0), 0.0)) + ch.offset_arm(clip.root_vel * (f / FPS)))
        drops.append(solver.hip_drop)
        misses.append(dict(m))
    if clip.loop:
        # costura real: el último cuadro resuelto contra el primero, antes de copiarlo encima (con 'loop_seam_deg' del
        # cuadro ya copiado daba 0 siempre)
        a, b = ch.rig.to_local(frames[0]), ch.rig.to_local(frames[-1])
        clip.seam_deg = max(NA.quat_angle_deg(a[n][1], b[n][1]) for n in ch.rig.names)
        frames[-1] = {n: M.copy() for n, M in frames[0].items()}
    return frames, ctrls, roots, drops, misses


# =============================================================================== clips
class TeamClip(NA.Clip):
    """Clip de pose a pose con lo que piden los golpes del juego:
      * 'travel' sale del reloj real del golpe (lunge_travel): el transform del juego avanza AttackDef.lunge
        entre la suelta y el golpe; los pies se autoran en el mundo y quedan clavados aunque el cuerpo avance;
      * pausas que se mueven ('tremble'): en los cuadros de 'hold' la mano del arma tiembla 0.5-1 cm, nunca
        una pose muerta (ANIM-02);
      * timing: apex (fin de la pausa: la pose de máxima carga), contact (= activeStart), active, hold,
        kind (light/heavy/unblockable), lunge, windup del juego para medir con StepTimeline."""

    def __init__(self, name, frames, keys, loop=False, timing=None, lag=None, notes="", root_vel=(0, 0, 0),
                 travel=None, tremble=0.006, feet=None):
        super().__init__(name, frames, keys, loop=loop, lag=lag, timing=timing, notes=notes, root_vel=root_vel)
        self.travel_table = travel
        self.tremble = tremble
        # pasos: {k: [FootKey...]} en el piso del mundo (antes del avance del golpe); mandan sobre foot_k de las claves
        self.feet = feet or {}
        self.ch = None
        # clip del segundo esqueleto del FBX (TeamChar.partner) que se hornea junto con este (ver bake)
        self.partner = None

    # canales propios de los personajes del equipo que no son posiciones (nindo_anim no los conoce)
    SCALARS = ("fist_r", "fist_l", "grip_l", "grip_r", "grip_flip", "grip_flip_l", "slide_r", "slide_l", "auto_drop", "look", "drop_r")
    DIRS = ("hand_r_palm", "hand_l_palm", "haft", "face")

    def sample(self, f, channel):
        if channel not in self.SCALARS and channel not in self.DIRS:
            return super().sample(f, channel)
        ks = self.keys
        f = max(0.0, min(float(self.frames), f))
        i = self._seg(f)
        a, b = ks[i], ks[i + 1]
        s = NA.ease(b.ease_ch.get(channel, b.ease), (f - a.frame) / max(1e-6, b.frame - a.frame))
        va, vb = a.ctrl.get(channel), b.ctrl.get(channel)
        if va is None and vb is None:
            return None
        va = vb if va is None else va
        vb = va if vb is None else vb
        if channel in self.SCALARS:
            return va + (vb - va) * s
        return NA.slerp_dir(va, vb, s)

    # pares (dirección, normal) que se interpolan como un marco: los dedos y la palma de cada mano. La hoja y el filo no:
    # su camino entre claves es el arco del tajo que autoró el clip (como marco, el tajo cambiaba de recorrido)
    FRAME_PAIRS = (("hand_r_dir", "hand_r_palm"), ("hand_l_dir", "hand_l_palm"))

    def frame_pair(self, f, dn, pn):
        """Dos direcciones de un mismo marco (los dedos y la palma, la hoja y el filo) entre dos claves interpoladas como
        UN marco (slerp del giro), no cada una por su arco: entre una mano que apunta atrás y otra que apunta adelante (la
        Thrust de vuelta a la guardia) los dos arcos sueltos dejaban la palma casi paralela a los dedos a mitad de camino y
        la mano pedida daba media vuelta en un cuadro. None si alguna de las dos claves no pide las dos."""
        ks = self.keys
        f = max(0.0, min(float(self.frames), f))
        i = self._seg(f)
        a, b = ks[i], ks[i + 1]
        fr = []
        for key in (a, b):
            d, p = key.ctrl.get(dn), key.ctrl.get(pn)
            if d is None or p is None:
                return None
            d, p = V(d).normalized(), V(p).normalized()
            p = p - d * p.dot(d)
            if p.length < 0.2:
                return None
            p.normalize()
            fr.append(Matrix((d, p, d.cross(p))).transposed().to_quaternion())
        s = NA.ease(b.ease_ch.get(dn, b.ease), (f - a.frame) / max(1e-6, b.frame - a.frame))
        if fr[0].dot(fr[1]) < 0.0:
            fr[1].negate()
        M = fr[0].slerp(fr[1], s).to_matrix()
        return tuple(M.col[0]), tuple(M.col[1])

    def controls(self, f):
        c = super().controls(f)
        for dn, pn in self.FRAME_PAIRS:
            fp = self.frame_pair(f, dn, pn)
            if fp is not None:
                c[dn], c[pn] = fp
        for k, track in self.feet.items():
            c["foot_" + k], c["foot_%s_rot" % k] = sample_feet(self.ch, k, track, f)
        if self.travel_table is not None:
            i = max(0, min(len(self.travel_table) - 1, int(round(f))))
            c["travel"] = self.travel_table[i]
        h = self.timing.get("hold")
        # los cuadros que se leen del golpe (de la pausa del aviso al primero activo; un clip puede pedir otros con
        # una clave 'look'): ahí el arma va donde se pidió
        if h and "contact" in self.timing and c.get("look") is None:
            c["look"] = 1.0 if h[0] <= f <= self.timing["contact"] + 1 else 0.0
        if h and self.tremble > 0 and h[0] <= f <= h[1]:
            w = math.sin(math.pi * (f - h[0]) / max(1, h[1] - h[0]))       # entra y sale de la pausa sin salto
            tr = Vector((math.sin(f * 2.7), math.cos(f * 3.3), math.sin(f * 4.1 + 1.0))) * (self.tremble * w)
            for k in ("grip", "hand_r", "hand_l"):
                if c.get(k) is not None:
                    c[k] = V(c[k]) + tr
        return c


class TakeClip(TeamClip):
    """Una toma del equipo (las acciones que trae el FBX del modelo) re-resuelta con las muñecas arregladas
    (TeamSolver.solve_take): el cuerpo, los pies y el arma quedan como en la toma, los brazos los vuelve a poner
    team_limbs. Para las tomas que el juego todavía usa tal cual (la presentación de Gorō, 'Intro'): en la toma la
    muñeca de la mano del martillo llegaba a 96° (rest 12°) y se ve en el primer plano de la cámara del jefe.
    'action': nombre de la acción; 'first'/'last': cuadros de la toma (los mismos que el controller del equipo)."""

    def __init__(self, ch, name, action, first, last, notes="", timing=None):
        n = last - first
        super().__init__(name, n, [NA.Key(0, {}), NA.Key(n, {})], loop=False, timing=timing or {}, notes=notes, tremble=0.0)
        self.take = sample_take(ch, action, first, last)

    def controls(self, f):
        i = max(0, min(len(self.take) - 1, int(round(f))))
        return {"take": self.take[i], "travel": 0.0}


def sample_take(ch, action, first, last):
    """{hueso: matriz en espacio de la armadura} de cada cuadro de una acción del FBX (de 'first' a 'last' de la toma,
    como los cuenta el controller: el cuadro 0 es el primero de la acción). Deja la armadura en reposo."""
    import charlib as C
    act = next(a for a in ch.take_actions if a.name.endswith(action))
    arm = ch.arm
    C.use_action(arm, act)
    scn = bpy.context.scene
    f0 = int(round(act.frame_range[0]))
    out = []
    for f in range(first, last + 1):
        scn.frame_set(f0 + f)
        bpy.context.view_layer.update()
        out.append({pb.name: pb.matrix.copy() for pb in arm.pose.bones})
    arm.animation_data.action = None
    for pb in arm.pose.bones:
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.rotation_euler = (0, 0, 0)
        pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()
    return out


def knock_travel(n, meters, delay=0):
    """Empujón que Enemy aplica al transform (golpe recibido, parry, sacudón): cada frame avanza min(1, dt*10) de lo
    que falta, o sea que a 60 fps queda 5/6 por frame (90 % en 0.2 s). Metros hacia ADELANTE en cada cuadro del clip
    (negativo = para atrás): los pies se autoran en el mundo y quedan clavados mientras lo empujan."""
    return [-meters * (1.0 - (5.0 / 6.0) ** (2.0 * max(0.0, f - delay))) for f in range(n + 1)]


def lunge_travel(frames, apex, contact, lunge, windup_min, speed=1.0, release_rate=1.6, hz=240.0):
    """Cuánto avanzó el transform del juego (m) en cada cuadro del clip durante un golpe con embestida, con el
    mismo reloj que Enemy.BeginStep/TickAttack: el avance va de la suelta (apex) a T + 0.05 * largo del paso a
    velocidad constante (y nunca a más de 12 m/s). Supone que Kaito no lo frena (con Kaito pegado avanza menos y
    el pie de atrás patina: es el caso raro)."""
    tl = NA.StepTimeline(frames, apex, contact, release_rate=release_rate, windup_min=windup_min, speed=speed)
    T = tl.T
    end = T + 0.05 * tl.step_len
    release = tl.tA + tl.hold
    start = max(0.0, end - max(end - release, lunge / 12.0))
    samples = []
    t = 0.0
    while True:
        n = min(1.0, tl.norm_at(t))
        tr = 0.0 if t <= start else lunge * min(1.0, (t - start) / max(1e-4, end - start))
        samples.append((n * frames, tr))
        if n >= 1.0:
            break
        t += 1.0 / hz
    out = []
    j = 0
    for f in range(frames + 1):
        while j + 1 < len(samples) and samples[j + 1][0] <= f:
            j += 1
        out.append(round(samples[j][1], 4))
    return out, tl


def gait(frames, speed, duty, feet, sole_z, lift=0.08, toe_off=25.0, heel=-12.0, phase_l=0.5):
    """Trayectorias de pies de un ciclo de locomoción en el lugar (el transform del juego avanza 'speed' m/s):
    durante el apoyo el pie va para atrás exactamente a la velocidad del suelo (clavado en el mundo), en el
    vuelo vuelve adelante en arco, despega en punta y apoya de talón. feet = {k: (x, y_medio)}.
    Devuelve fn(f) -> {foot_k, foot_k_rot} y la fase de apoyo (0..1) por pie."""
    T = frames / FPS
    span = speed * T * duty

    def foot(k, f):
        x, ym = feet[k]
        p = ((f / frames) + (phase_l if k == "l" else 0.0)) % 1.0
        if p < duty:
            y = ym - span * 0.5 + span * (p / duty)
            # el pie apoyado se despega del talón al final del apoyo (rueda sobre la punta)
            roll = max(0.0, (p / duty - 0.75) / 0.25)
            return Vector((x, y, sole_z + 0.01 * roll)), (toe_off * 0.6 * roll * roll, 0.0, 0.0), p
        q = (p - duty) / (1.0 - duty)
        s = 0.5 - 0.5 * math.cos(math.pi * q)
        y = ym + span * 0.5 - span * s
        z = sole_z + lift * math.sin(math.pi * min(1.0, q * 1.1)) ** 0.8
        pitch = toe_off * (1.0 - q) ** 2 * (q < 0.5) + heel * max(0.0, (q - 0.6) / 0.4) ** 1.5
        return Vector((x, y, z)), (pitch, 0.0, 0.0), p

    return foot
