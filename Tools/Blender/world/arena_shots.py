"""Las tomas de la arena de Chikuō para arena_preview.py --arena (el mundo de build_world, sin exportar).

Cada toma: dónde está Kaito, en qué caña está Chikuō (o en el piso), cómo están las cañas (fase 1 rectas, fase 2
inclinadas 70° hacia afuera, fase 3 con la Madre) y qué cámara:
  game    la de exploración del pedido (pitch 52, 24 m, FOV 30) con el foco en Kaito
  fight   la de pelea de CameraDirector con el perfil de Chikuō (pitch 45; 19 + 0.35 d entre 19 y 26 m, más 2.4 posado;
          el foco a min(45 %, 6 m) de Kaito hacia la base de su caña y subido 0.45 x el alto del posado)
  shot    un plano fijo (la presentación)
"""
import math
import bpy
from mathutils import Vector

import build_world as BW
import world_plan as W

R_LOAD = 75.0       # solo se instancian los props a menos de esto del centro del claro (memoria y tiempo)


def fight_camera(P, kaito, root_xz, perch_h, ground=False):
    k = (kaito[0], 2.0 + 1.0, kaito[1])
    b = (root_xz[0], 2.0 + 1.0, root_xz[1])
    d = math.hypot(b[0] - k[0], b[2] - k[2])
    t = min(0.45, 6.0 / d) if d > 0.01 else 0.0
    f = [k[i] + (b[i] - k[i]) * t for i in range(3)]
    f[1] += 0.0 if ground else 0.45 * perch_h
    dist = min(26.0, max(19.0, 19.0 + 0.35 * d)) + (1.6 if ground else 2.4)
    return P.game_camera("cam_fight", (f[0], f[2], f[1]), pitch=45.0, dist=dist)


def load_world(P):
    BW.build_all()
    cx, cz = W.OZEKI_CENTER
    fns = BW.prop_fns()
    root = bpy.data.collections.new("PropLib")
    bpy.context.scene.collection.children.link(root)
    bpy.context.view_layer.layer_collection.children["PropLib"].exclude = True
    near = [p for p in BW.PLACED if math.hypot(p[1] - cx, p[2] - cz) < R_LOAD]
    cols = {}
    for pid in sorted({p[0] for p in near}):
        col = bpy.data.collections.new("lib_" + pid)
        root.children.link(col)
        if pid in fns:
            o = fns[pid](1)
            bpy.context.scene.collection.objects.unlink(o)
            col.objects.link(o)
        cols[pid] = col
    for pid, x, z, yaw, sc, y in near:
        e = bpy.data.objects.new("I_" + pid, None)
        e.instance_type = 'COLLECTION'
        e.instance_collection = cols[pid]
        e.location = P.B(x, z, y)
        e.rotation_euler = (0, 0, math.radians(-yaw))
        e.scale = (sc, sc, sc)
        bpy.context.scene.collection.objects.link(e)
    for o in BW.WALL_OBJS:
        o.hide_render = True
    P.PV.setup_night(ground=False, strength=1.1)
    try:
        bpy.context.scene.eevee.taa_render_samples = 16
    except Exception:
        pass


def barrier_ring(P):
    """El anillo de la barrera (r 15) como una línea dorada tenue en el piso: para ver qué queda adentro."""
    cx, cz = W.OZEKI_CENTER
    mat = P.flat_mat("p_barrier", (1.0, 0.7, 0.3), emit=1.5)
    for i in range(48):
        a = 2 * math.pi * (i + 0.5) / 48
        x, z = cx + 15 * math.cos(a), cz + 15 * math.sin(a)
        P.prim("cube", f"bar{i}", P.B(x, z, BW.mesh_H(x, z) + 0.02), (0.08, 15 * 2 * math.pi / 48, 0.03), mat,
               rot=(0, 0, -a))


class Arena:
    def __init__(self, P):
        self.P = P
        self.stalks = {}
        for sid, kind, b, r in W.BOSS_STALKS:
            x, z = W.boss_stalk_xz(b, r)
            self.stalks[sid] = dict(kind=kind, xz=(x, z), h=BW.mesh_H(x, z), objs=None, root=None)
        self.extra = []

    def setup(self, phase):
        """phase 1/3: rectas (la 3 con la Madre); 2: las seis inclinadas 70° hacia afuera (parejo)."""
        P = self.P
        for o in self.extra:
            bpy.data.objects.remove(o, do_unlink=True)
        self.extra = []
        cx, cz = W.OZEKI_CENTER
        for sid, s in self.stalks.items():
            if s["root"] is not None:
                for o in list(s["root"].children_recursive) + [s["root"]]:
                    bpy.data.objects.remove(o, do_unlink=True)
                s["root"] = None
            if sid == "M" and phase != 3:
                continue
            out = (s["xz"][0] - cx, s["xz"][1] - cz)
            L_ = math.hypot(*out) or 1.0
            out = (out[0] / L_, out[1] / L_) if sid != "M" else (0.0, -1.0)
            if phase == 2:
                objs = P.place_stalk(s["kind"], s["xz"][0], s["xz"][1], s["h"], 70.0, out, even=1.0)
            else:
                objs = P.place_stalk(s["kind"], s["xz"][0], s["xz"][1], s["h"])
            s["objs"] = objs
            s["root"] = objs["Stalk"].parent

    def chikuo_on(self, sid, face_xz, bend_to=None, deg=6.0):
        P = self.P
        s = self.stalks[sid]
        if bend_to is not None:
            d = (bend_to[0] - s["xz"][0], bend_to[1] - s["xz"][1])
            L_ = math.hypot(*d) or 1.0
            P.AS.apply_bend(s["objs"], s["kind"], deg, (-d[0] / L_, -d[1] / L_))
        f = (face_xz[0] - s["xz"][0], face_xz[1] - s["xz"][1])
        root = P.chikuo_proxy("Chikuo", P.perch_matrix(s["objs"], f))
        self.extra += [root] + list(root.children)

    def chikuo_ground(self, xz, face_xz):
        P = self.P
        from mathutils import Matrix
        f = Vector((-(face_xz[0] - xz[0]), -(face_xz[1] - xz[1]), 0)).normalized()
        up = Vector((0, 0, 1))
        side = f.cross(up)
        m = Matrix((side, -f, up)).transposed().to_4x4()
        m.translation = P.B(xz[0], xz[1], BW.mesh_H(*xz))
        root = P.chikuo_proxy("Chikuo", m, crouch=False)
        self.extra += [root] + list(root.children)

    def tells(self, sid, kaito_xz):
        """El ensō blanco de la caña cargada (1.2 m en su base, de tinta con el halo oscuro) y su nudo de la base
        encendido, y el anillo dorado de un dardo a los pies de Kaito: para mirar si se leen sobre el piso del claro."""
        P = self.P
        s = self.stalks[sid]
        for name, xz, r, rgb, emit in (("enso", s["xz"], 0.6, (1.0, 1.0, 1.0), 4.0), ("dorado", kaito_xz, 0.75, (1.0, 0.75, 0.3), 3.0)):
            for i in range(28):
                if name == "enso" and i > 24:
                    continue          # el ensō no se cierra
                a = 2 * math.pi * i / 28
                x, z = xz[0] + r * math.cos(a), xz[1] + r * math.sin(a)
                h = BW.mesh_H(x, z) + 0.03
                ink = P.prim("cube", f"{name}_ink{i}", P.B(x, z, h - 0.01), (0.16, 2 * math.pi * r / 28 * 1.1, 0.01),
                             P.flat_mat("p_ink", (0.02, 0.015, 0.02)), rot=(0, 0, -a))
                st = P.prim("cube", f"{name}{i}", P.B(x, z, h), (0.08, 2 * math.pi * r / 28 * 1.05, 0.012),
                            P.flat_mat("p_" + name, rgb, emit=emit), rot=(0, 0, -a))
                self.extra += [ink, st]
        g = s["objs"]["GlintBase"]
        m = g.data.materials[0].copy()
        m.node_tree.nodes.get("Principled BSDF").inputs["Emission Strength"].default_value = 3.0
        g.data.materials[0] = m

    def kaito(self, xz):
        root = self.P.kaito_proxy("Kaito", xz[0], xz[1], BW.mesh_H(*xz))
        self.extra += [root] + list(root.children)


# (nombre, fase, Kaito, caña de Chikuō o ("piso", x, z), cámara)
SHOTS = [
    ("f1_carga_O1", 1, (121.5, 158.5), "O1", "fight"),
    ("f1_centro_N2", 1, (124.0, 160.0), "N2", "fight"),
    ("f1_centro_N2_game", 1, (124.0, 160.0), "N2", "game"),
    ("f1_E1_N1", 1, (127.5, 156.5), "N1", "fight"),
    ("f1_oeste_O1", 1, (120.5, 158.0), "O1", "fight"),
    ("f1_sur_E2", 1, (124.0, 150.5), "E2", "fight"),
    ("f1_norte_O2", 1, (121.0, 169.0), "O2", "fight"),
    ("f1_pie_O1_sur", 1, (118.5, 159.0), "E1", "fight"),
    ("f1_pie_O1_sur_game", 1, (118.5, 159.0), "E1", "game"),
    ("f2_piso", 2, (122.0, 158.0), ("piso", 125.0, 162.5), "fight"),
    ("f3_madre", 3, (120.0, 156.0), "M", "fight"),
    ("f3_madre_game", 3, (120.0, 156.0), "M", "game"),
]


def run(P, only=None):
    load_world(P)
    barrier_ring(P)
    A = Arena(P)
    A.setup(1)
    # vista cenital del claro (norte arriba)
    if not only or "mapa" in only:
        cx, cz = W.OZEKI_CENTER
        cam = P.shot_camera("cam_top", (cx, cz - 0.01, 2.0 + 60.0), (cx, cz, 2.0), fov=30)
        P.render(cam, "arena_mapa", res=(1100, 1100))
    for name, ph, kxz, ch, cam in SHOTS:
        if only and name not in only:
            continue
        A.setup(ph)
        A.kaito(kxz)
        if isinstance(ch, tuple):
            A.chikuo_ground((ch[1], ch[2]), kxz)
            root_xz, perch, ground = (ch[1], ch[2]), 0.0, True
        else:
            A.chikuo_on(ch, kxz, bend_to=kxz, deg=8.0)
            s = A.stalks[ch]
            root_xz, perch, ground = s["xz"], P.AS.KINDS[s["kind"]]["perch"], False
        if name == "f1_carga_O1":
            A.tells("O1", kxz)
        if cam == "game":
            c = P.game_camera("cam_game", (kxz[0], kxz[1], BW.mesh_H(*kxz) + 1.0), pitch=52.0, dist=24.0)
        else:
            c = fight_camera(P, kxz, root_xz, perch, ground)
        P.render(c, name)
    # la presentación: Kaito entra por el arco y la barrera se cierra a 10.5 m del centro; Chikuō colgado de O1
    if not only or "intro" in only:
        A.setup(1)
        k = (118.9, 153.3)
        A.kaito(k)
        A.chikuo_on("O1", k, bend_to=k, deg=10.0)
        s = A.stalks["O1"]
        perch = P.AS.KINDS["inner"]["perch"] + s["h"]
        eye = (k[0] - 1.6, k[1] - 3.4, s["h"] + 1.3)
        P.render(P.shot_camera("cam_intro_up", eye, (s["xz"][0], s["xz"][1], perch + 0.4), fov=36), "intro_hacia_O1")
        # la charla con los dos en cuadro (el plano de hoy de Presentation: detrás de Kaito, 4.5 m atrás y 2.2 al costado)
        back = Vector((k[0] - s["xz"][0], k[1] - s["xz"][1], 0)).normalized()
        side = Vector((0, 0, 1)).cross(back)
        mid = (k[0] + (s["xz"][0] - k[0]) * 0.55, k[1] + (s["xz"][1] - k[1]) * 0.55)
        eye = (k[0] + back.x * 4.5 + side.x * 2.2, k[1] + back.y * 4.5 + side.y * 2.2, s["h"] + 3.2)
        P.render(P.shot_camera("cam_talk", eye, (mid[0], mid[1], s["h"] + 2.8), fov=36), "intro_charla")
