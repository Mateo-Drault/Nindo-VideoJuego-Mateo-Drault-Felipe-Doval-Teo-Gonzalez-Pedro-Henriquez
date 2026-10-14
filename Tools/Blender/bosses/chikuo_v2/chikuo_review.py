"""Renders de revisión del Chikuō ermitaño: cómo se ve EN EL JUEGO (cámara 52°/24 m, FOV 30, la luz de luna en Gamma, la
niebla, el rim frío de CharacterLit y los colores de la arena de bambú: el piso claro del claro, las cañas bambú claro y
el bosque oscuro) y las hojas de comparación con el concepto elegido (mismas vistas: frente, 3/4, perfil, espalda y la
cabeza de cerca), más las poses de prueba de la deformación y el elenco (Kaito y Kokuyō al lado).

Se usa después de construir el modelo: cambia los materiales de los objetos por los de revisión.
"""
import json, math, os
import bpy
from mathutils import Vector, Matrix
from bpy_extras.object_utils import world_to_camera_view
import nindo_anim as NA
import nindo_palette as P
import nindo_lib as L
import chikuo_model as CM
import chikuo_rig as CR

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
KAITO_FBX = os.path.join(REPO, "Nindo", "Assets", "Animations teo", "kaitooo.fbx")
KOKUYO_FBX = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Art", "Characters", "Kokuyo", "Kokuyo.fbx")
PALETTE_PNG = os.path.join(REPO, "Tools", "Blender", "out", "NindoPalette.png")
CONCEPT = os.path.join(REPO, "Docs", "handoff", "conceptos", "chikuo_v2")
BLACK_FLOOR = 0.13                  # CharacterFactory.BlackFloor
RIM_RGB, RIM_STRENGTH, RIM_POWER = (0.624, 0.761, 1.0), 0.3, 3.0      # NindoCharacterLit.shader
GOLD = (1.0, 0.72, 0.24)            # TellStyle.Gold
CRIMSON = (0.92, 0.157, 0.118)
WHITE_TELL = (1.0, 1.0, 1.0)
STUDIO = Vector((-0.45, -0.7, 0.75))
# recortes del concepto (píxeles del original 2688 x 1520) para comparar vista por vista
CUTS = {"front": ("elegido_modelado.jpg", (40, 40, 690, 1330)), "q34": ("elegido_modelado.jpg", (740, 40, 1280, 1330)),
        "side": ("elegido_modelado.jpg", (1380, 40, 1840, 1330)), "back": ("elegido_modelado.jpg", (1900, 40, 2640, 1330)),
        "head_front": ("elegido_detalles.jpg", (20, 0, 640, 720)), "head_side": ("elegido_detalles.jpg", (680, 0, 1240, 720)),
        "head_q": ("elegido_detalles.jpg", (1230, 30, 1660, 720)), "head_flute": ("elegido_detalles.jpg", (1660, 30, 2200, 720)),
        "head_laugh": ("elegido_detalles.jpg", (2190, 30, 2688, 720)), "staff": ("elegido_detalles.jpg", (1380, 720, 2050, 1520)),
        "feet": ("elegido_detalles.jpg", (1950, 1100, 2688, 1520)), "cloak_back": ("elegido_detalles.jpg", (690, 720, 1330, 1520)),
        "hang": ("elegido_hoja_original.jpg", (1880, 0, 2688, 1000)), "perch": ("elegido_acciones.jpg", (420, 150, 900, 1100)),
        "leap": ("elegido_acciones.jpg", (1150, 150, 1850, 820)), "climb": ("elegido_acciones.jpg", (0, 150, 420, 1150))}


def concept_tile(key, label):
    f, crop = CUTS[key]
    return {"img": os.path.join(CONCEPT, f), "crop": list(crop), "label": "concepto: " + label}


class Review:
    def __init__(self, arm, rig, meshes, out_dir, res=(1280, 720)):
        self.arm, self.rig, self.meshes = arm, rig, meshes
        self.out = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.scn = NA.setup_review_scene(res)
        self.look = NA.GameLook()
        self.cam = NA.camera(self.scn)
        self.palette = bpy.data.images.load(PALETTE_PNG, check_existing=False)
        self.palette.colorspace_settings.name = 'Non-Color'
        self.mats = {"Nindo_Palette": self.build_mat("rv_palette", image=self.palette),
                     "Nindo_Emissive": self.build_mat("rv_emissive", image=self.palette, emission=(1, 1, 1))}
        for n, rgb in CM.MAT_RGB.items():
            c = tuple(max(v, BLACK_FLOOR * v / max(rgb)) for v in rgb) if max(rgb) < BLACK_FLOOR else rgb
            self.mats[n] = self.build_mat("rv_" + n, rgb=c)
        self.lit = {}
        for n, rgb in CM.MAT_RGB.items():
            for key, col in (("gold", GOLD), ("red", CRIMSON), ("white", WHITE_TELL)):
                self.lit[(n, key)] = self.build_mat(f"rv_{key}_{n}", rgb=rgb, emission=col, gain=2.0)
        self._orig = {o.name: [s.material.name if s.material else "" for s in o.material_slots] for o in meshes.values()}
        # luz de estudio neutra para compararse con el concepto (la de la hoja: blanca y pareja); la del juego es la luna
        self._studio_dirs = []
        self.studio = {"Nindo_Palette": self.studio_mat("st_palette", image=self.palette)}
        for n, rgb in CM.MAT_RGB.items():
            self.studio[n] = self.studio_mat("st_" + n, rgb=rgb)
        self.assign(meshes.values())
        self.ground = None
        self.extra = []
        self.kaito_piv = None
        self.mode = "game"

    def studio_mat(self, name, image=None, rgb=None):
        """albedo * (0.42 de ambiente + 0.18 del cielo por arriba + 0.62 * N·L de una luz blanca) + un rim gris chico."""
        m = bpy.data.materials.new(name)
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        N, Lk = nt.nodes.new, nt.links.new
        out = N("ShaderNodeOutputMaterial")
        em = N("ShaderNodeEmission")
        Lk(em.outputs[0], out.inputs[0])
        if image is not None:
            tex = N("ShaderNodeTexImage"); tex.image = image; tex.interpolation = 'Closest'
            alb = tex.outputs[0]
        else:
            c = N("ShaderNodeRGB"); c.outputs[0].default_value = (*rgb, 1.0)
            alb = c.outputs[0]
        geo = N("ShaderNodeNewGeometry")
        ld = N("ShaderNodeCombineXYZ")
        self._studio_dirs.append(ld)
        dot = N("ShaderNodeVectorMath"); dot.operation = 'DOT_PRODUCT'
        Lk(geo.outputs["Normal"], dot.inputs[0]); Lk(ld.outputs[0], dot.inputs[1])
        mxn = N("ShaderNodeMath"); mxn.operation = 'MAXIMUM'; mxn.inputs[1].default_value = 0.0
        Lk(dot.outputs["Value"], mxn.inputs[0])
        k = N("ShaderNodeMath"); k.operation = 'MULTIPLY_ADD'; k.inputs[1].default_value = 0.62; k.inputs[2].default_value = 0.42
        Lk(mxn.outputs[0], k.inputs[0])
        sep = N("ShaderNodeSeparateXYZ"); Lk(geo.outputs["Normal"], sep.inputs[0])
        sky = N("ShaderNodeMath"); sky.operation = 'MULTIPLY_ADD'; sky.inputs[1].default_value = 0.09; sky.inputs[2].default_value = 0.09
        Lk(sep.outputs[2], sky.inputs[0])
        tot = N("ShaderNodeMath"); tot.operation = 'ADD'
        Lk(k.outputs[0], tot.inputs[0]); Lk(sky.outputs[0], tot.inputs[1])
        lit = N("ShaderNodeVectorMath"); lit.operation = 'SCALE'
        Lk(alb, lit.inputs[0]); Lk(tot.outputs[0], lit.inputs["Scale"])
        Lk(lit.outputs[0], em.inputs["Color"])
        self.set_studio_light(STUDIO)
        return m

    def set_studio_light(self, d):
        d = Vector(d).normalized()
        for n in self._studio_dirs:
            n.inputs[0].default_value, n.inputs[1].default_value, n.inputs[2].default_value = d

    def use(self, mode):
        """'studio' (comparar con el concepto) o 'game' (la luna, la niebla y el rim del juego)."""
        self.mode = mode
        src = self.studio if mode == "studio" else self.mats
        for o in self.meshes.values():
            for i, slot in enumerate(o.material_slots):
                name = self._orig[o.name][i]
                if name in src:
                    slot.material = src[name]
        self.scn.world.node_tree.nodes["Background"].inputs[0].default_value = \
            (0.11, 0.11, 0.12, 1) if mode == "studio" else (*NA.GameLook.FOG, 1)

    # ------------------------------------------------------------------ materiales (GameLook + el rim de CharacterLit)
    def build_mat(self, name, image=None, rgb=None, emission=(0, 0, 0), gain=1.0, rim=True):
        m = self.look.build(name, albedo_image=image, albedo_rgb=rgb, emission_rgb=emission, emission_gain=gain)
        if not rim:
            return m
        nt = m.node_tree
        fog = next(n for n in nt.nodes if n.bl_idname == "ShaderNodeMix" and n.inputs["Factor"].is_linked
                   and n.inputs["A"].is_linked and not n.inputs["B"].is_linked)
        col_src = fog.inputs["A"].links[0].from_socket
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        dot = nt.nodes.new("ShaderNodeVectorMath"); dot.operation = 'DOT_PRODUCT'
        nt.links.new(geo.outputs["Normal"], dot.inputs[0]); nt.links.new(geo.outputs["Incoming"], dot.inputs[1])
        cl = nt.nodes.new("ShaderNodeClamp")
        nt.links.new(dot.outputs["Value"], cl.inputs[0])
        inv = nt.nodes.new("ShaderNodeMath"); inv.operation = 'SUBTRACT'; inv.inputs[0].default_value = 1.0
        nt.links.new(cl.outputs[0], inv.inputs[1])
        pw = nt.nodes.new("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = RIM_POWER
        nt.links.new(inv.outputs[0], pw.inputs[0])
        k = nt.nodes.new("ShaderNodeMath"); k.operation = 'MULTIPLY'; k.inputs[1].default_value = RIM_STRENGTH
        nt.links.new(pw.outputs[0], k.inputs[0])
        rc = nt.nodes.new("ShaderNodeCombineXYZ")
        rc.inputs[0].default_value, rc.inputs[1].default_value, rc.inputs[2].default_value = RIM_RGB
        sc = nt.nodes.new("ShaderNodeVectorMath"); sc.operation = 'SCALE'
        nt.links.new(rc.outputs[0], sc.inputs[0]); nt.links.new(k.outputs[0], sc.inputs["Scale"])
        add = nt.nodes.new("ShaderNodeVectorMath"); add.operation = 'ADD'
        nt.links.new(col_src, add.inputs[0]); nt.links.new(sc.outputs[0], add.inputs[1])
        nt.links.new(add.outputs[0], fog.inputs["A"])
        return m

    def assign(self, objs):
        for o in objs:
            for s in o.material_slots:
                if s.material and s.material.name in self.mats:
                    s.material = self.mats[s.material.name]

    def glow(self, slots=(), color="gold"):
        """Enciende solo los slots que pide el aviso (como CharacterGlint.SetGlow por nombre)."""
        for o in self.meshes.values():
            for i, slot in enumerate(o.material_slots):
                name = self._orig[o.name][i]
                if name in CM.MAT_RGB:
                    slot.material = self.lit[(name, color)] if name in slots else self.mats[name]

    # ------------------------------------------------------------------ pose
    def apply(self, W):
        """Pone la armadura en la pose W {hueso: matriz en espacio de armadura} (None = reposo)."""
        if W is None:
            for pb in self.arm.pose.bones:
                pb.location = (0, 0, 0)
                pb.rotation_quaternion = (1, 0, 0, 0)
        else:
            for n, (l, q) in self.rig.to_local(W).items():
                pb = self.arm.pose.bones[n]
                pb.location = l
                pb.rotation_quaternion = q
        bpy.context.view_layer.update()

    # ------------------------------------------------------------------ escenario
    def floor(self, color="path", size=80):
        if self.ground:
            bpy.data.objects.remove(self.ground)
        bpy.ops.mesh.primitive_plane_add(size=size, location=(0, 0, 0))
        self.ground = bpy.context.active_object
        m = self.studio_mat("st_ground", rgb=(0.16, 0.16, 0.17)) if self.mode == "studio" else \
            self.build_mat("rv_ground_" + color, rgb=P.hex_to_rgb(dict(P.PALETTE)[color]), rim=False)
        self.ground.data.materials.append(m)

    def stalk(self, x, y, height, perch, light=True, name="Stalk"):
        """Una caña de la arena (contrato de c4/arena, diseño 8.2): culmo facetado de Ø 0.26 a 0.12 m, nudos cada ~0.9 m,
        el nudo del posado más grueso con dos cascabeles y la copa de hojas desde el 75 %."""
        mb = L.MeshBuilder(name, seed=int(abs(x * 7 + y * 13)) + 3)
        col = "bamboo_light" if light else "bamboo"
        node = "bamboo_dry" if light else "bamboo_dark"
        zs = [i * 0.9 for i in range(int(height / 0.9) + 1)] + [height]
        for z0, z1 in zip(zs[:-1], zs[1:]):
            r0 = 0.13 - 0.07 * z0 / height
            r1 = 0.13 - 0.07 * z1 / height
            mb.prism((0, 0, z0), r0, z1 - z0, 7, col, radius_top=r1)
            mb.prism((0, 0, z1 - 0.03), r1 * 1.12, 0.06, 7, node)
        mb.prism((0, 0, perch - 0.05), 0.15 * (1 - 0.3 * perch / height), 0.1, 7, node)
        for i in range(14):
            a = i * 2.4
            z = height * (0.75 + 0.25 * (i / 14.0))
            d = Vector((math.cos(a), math.sin(a), -0.35)).normalized()
            p0 = Vector((0, 0, z))
            mb.face([p0, p0 + d * 0.9 + Vector((0, 0, 0.12)), p0 + d * 1.1, p0 + d * 0.9 - Vector((0, 0, 0.12))],
                    "leaf_light" if i % 2 else "leaf", double=True)
        o = mb.finish()
        o.location = (x, y, 0)
        self.assign([o])
        self.extra.append(o)
        return o

    def forest(self):
        """El bosque oscuro alrededor del claro (fuera del cuadro de 52°/24 m queda solo el fondo)."""
        import random
        rng = random.Random(5)
        for i in range(26):
            a = rng.uniform(0, 2 * math.pi)
            r = rng.uniform(14.5, 20.0)
            self.stalk(math.cos(a) * r, math.sin(a) * r + 2.0, rng.uniform(8.0, 10.0), 99.0, light=False, name="Forest%d" % i)

    def clear_extra(self):
        for o in self.extra:
            bpy.data.objects.remove(o)
        self.extra = []

    def import_ref(self, path, height, name="Ref"):
        if not os.path.exists(path):
            return None
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        arm = next((o for o in new if o.type == 'ARMATURE'), None)
        ms = [o for o in new if o.type == 'MESH']
        if arm is not None:
            arm.data.pose_position = 'REST'
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        zs = []
        for o in ms:
            oe = o.evaluated_get(dg)
            me = oe.to_mesh()
            zs += [(oe.matrix_world @ v.co).z for v in me.vertices]
            oe.to_mesh_clear()
        piv = bpy.data.objects.new(name + "Pivot", None)
        self.scn.collection.objects.link(piv)
        for o in new:
            if o.parent is None:
                o.parent = piv
        s = height / (max(zs) - min(zs)) if height else 1.0
        piv.scale = (s, s, s)
        z0 = -min(zs) * s
        for o in ms:
            for sl in o.material_slots:
                m = sl.material
                if m is None:
                    continue
                if m.name.startswith("Nindo_Palette"):
                    sl.material = self.mats["Nindo_Palette"]
                    continue
                if m.name in self.mats:
                    sl.material = self.mats[m.name]
                    continue
                c = list(m.diffuse_color[:3])
                mxv = max(c)
                if mxv < BLACK_FLOOR:
                    c = [x / mxv * BLACK_FLOOR for x in c] if mxv > 0.005 else [0.85 * BLACK_FLOOR, 0.9 * BLACK_FLOOR, BLACK_FLOOR]
                sl.material = self.build_mat("rv_ref_" + m.name, rgb=tuple(c))
        return piv, z0, new

    def kaito(self, xy=(0.9, -3.4), face_deg=0.0):
        """Kaito (1.5 m, el modelo del juego) de espaldas a la cámara mirando al jefe (face 0 = mira a +Y)."""
        if self.kaito_piv is None:
            r = self.import_ref(KAITO_FBX, 1.5, name="Kaito")
            if r is None:
                return
            self.kaito_piv, self.kaito_z0, self.kaito_objs = r
        self.kaito_piv.location = (xy[0], xy[1], self.kaito_z0)
        self.kaito_piv.rotation_euler = (0, 0, math.radians(90.0 + face_deg))

    def show(self, objs, on):
        for o in objs:
            o.hide_render = not on

    # ------------------------------------------------------------------ cámaras y render
    def ortho(self, center, scale, az, el=0.0):
        NA.ortho_camera(self.cam, center, scale, az, el)

    def game_view(self, focus=(0, -1.6, 1.0), pitch=52.0, dist=24.0, fov=30.0, yaw=0.0):
        NA.game_camera(self.cam, focus, pitch, dist, fov, yaw)

    def render(self, path, res=None, border=None):
        scn = self.scn
        if res:
            scn.render.resolution_x, scn.render.resolution_y = res
        scn.render.use_border = border is not None
        scn.render.use_crop_to_border = border is not None
        if border:
            scn.render.border_min_x, scn.render.border_max_x, scn.render.border_min_y, scn.render.border_max_y = border
        NA.render(scn, path)
        scn.render.use_border = False
        return path

    def border_around(self, pts, margin=0.04):
        bpy.context.view_layer.update()
        uv = [world_to_camera_view(self.scn, self.cam, Vector(p)) for p in pts]
        return (max(0.0, min(u.x for u in uv) - margin), min(1.0, max(u.x for u in uv) + margin),
                max(0.0, min(u.y for u in uv) - margin), min(1.0, max(u.y for u in uv) + margin))

    def body_points(self):
        dg = bpy.context.evaluated_depsgraph_get()
        pts = []
        for o in self.meshes.values():
            if o.hide_render:
                continue
            oe = o.evaluated_get(dg)
            me = oe.to_mesh()
            M = oe.matrix_world
            vs = me.vertices
            step = max(1, len(vs) // 400)
            pts += [M @ vs[i].co for i in range(0, len(vs), step)]
            oe.to_mesh_clear()
        return pts

    def sheet(self, layout):
        p = os.path.join(self.out, "_layout.json")
        json.dump(layout, open(p, "w", encoding="utf-8"), indent=1)
        NA.compose_sheet(p)
        try:
            os.remove(p)
        except OSError:
            pass

    def tile(self, name):
        return os.path.join(self.out, "_t_" + name + ".png")

    # ------------------------------------------------------------------ hojas
    def turnaround_sheet(self):
        """Frente, 3/4, perfil y espalda en ortográfica con luz de estudio, al lado de las mismas vistas del concepto."""
        self.use("studio")
        self.floor()
        self.apply(None)
        rows = []
        for key, az, lab in (("front", 0, "frente"), ("q34", 42, "3/4"), ("side", 90, "perfil"), ("back", 180, "espalda")):
            self.set_studio_light(STUDIO if az < 150 else Vector((0.4, 0.75, 0.7)))
            self.ortho((0, 0, 1.25), 2.7, az, 2)
            p = self.render(self.tile("ta_" + key), res=(720, 1280))
            rows.append({"label": lab, "tiles": [concept_tile(key, lab), {"img": p, "label": "modelo: " + lab}]})
        out = os.path.join(self.out, "turnaround_sheet.png")
        self.sheet({"out": out, "title": "Chikuō ermitaño: modelo contra el concepto (ortográfica, luz de estudio)", "width": 1280,
                    "tile_h": 600, "rows": [{"label": "", "tiles": rows[0]["tiles"] + rows[1]["tiles"]},
                                            {"label": "", "tiles": rows[2]["tiles"] + rows[3]["tiles"]}]})
        return out

    def head_sheet(self, faces):
        """La cabeza de frente, de perfil y de 3/4 (sonrisa pícara) y las caras (soplando, tocando, riéndose) junto al
        concepto. faces = {nombre: W de la pose con esa cara}."""
        self.use("studio")
        self.floor()
        self.set_studio_light(STUDIO)
        tiles_c, tiles_m = [], []
        for key, az, el, face, lab in (("head_front", 0, 4, "grin", "frente"), ("head_side", 90, 2, "grin", "perfil"),
                                       ("head_q", 18, 6, "grin", "3/4"), ("head_flute", 10, 6, "flute", "tocando"),
                                       ("head_laugh", 25, 4, "laugh", "riéndose")):
            self.apply(faces.get(face))
            hb = self.arm.matrix_world @ self.arm.pose.bones["Head"].head
            self.ortho(hb + Vector((0, 0, 0.12)), 0.62, az, el)
            p = self.render(self.tile("head_" + key), res=(560, 640))
            tiles_c.append(concept_tile(key, lab))
            tiles_m.append({"img": p, "label": "modelo: " + lab + ("" if face == "grin" else " (" + face + ")")})
        self.apply(faces.get("blow"))
        hb = self.arm.matrix_world @ self.arm.pose.bones["Head"].head
        self.ortho(hb + Vector((0, 0, 0.1)), 0.55, 30, 4)
        tiles_m.append({"img": self.render(self.tile("head_blow"), res=(560, 640)), "label": "modelo: soplando (cerbatana)"})
        self.apply(None)
        out = os.path.join(self.out, "head_sheet.png")
        self.sheet({"out": out, "title": "Chikuō ermitaño: la cabeza y las caras contra la hoja de detalles", "width": 1280,
                    "tile_h": 300, "rows": [{"label": "concepto", "tiles": tiles_c}, {"label": "modelo", "tiles": tiles_m}]})
        return out

    def details_sheet(self):
        """La capa desde atrás, la flauta-bastón, las sandalias, una mano y los cascabeles, al lado del concepto."""
        self.use("studio")
        self.floor()
        self.set_studio_light(Vector((0.4, 0.75, 0.7)))
        self.apply(None)
        t = []
        self.ortho((0, 0.1, 1.35), 2.0, 180, 25)
        t.append({"img": self.render(self.tile("d_cloak"), res=(640, 640)), "label": "modelo: capa desde atrás"})
        self.set_studio_light(STUDIO)
        sb = self.arm.matrix_world @ self.arm.pose.bones["Staff"].head
        self.ortho(sb + Vector((0, 0, 1.6)), 0.95, 0, 0)
        t.append({"img": self.render(self.tile("d_staff_top"), res=(360, 640)), "label": "modelo: flauta (arriba)"})
        self.ortho(sb + Vector((0, 0, 0.3)), 0.95, 20, 0)
        t.append({"img": self.render(self.tile("d_staff_bot"), res=(360, 640)), "label": "modelo: flauta (vendado)"})
        self.ortho(Vector((-0.24, -0.06, 0.22)), 0.62, 25, 12)
        t.append({"img": self.render(self.tile("d_foot"), res=(640, 640)), "label": "modelo: sandalia"})
        hb = self.arm.matrix_world @ self.arm.pose.bones["Hand_R"].head
        self.ortho(hb + Vector((-0.02, -0.03, -0.07)), 0.40, -60, 8)
        t.append({"img": self.render(self.tile("d_hand"), res=(640, 640)), "label": "modelo: mano"})
        self.ortho(Vector((-0.3, -0.05, 1.72)), 0.75, 30, 10)
        t.append({"img": self.render(self.tile("d_chimes"), res=(640, 640)), "label": "modelo: cascabeles del hombro"})
        out = os.path.join(self.out, "details_sheet.png")
        self.sheet({"out": out, "title": "Chikuō ermitaño: detalles contra la hoja de detalles", "width": 1280, "tile_h": 300,
                    "rows": [{"label": "concepto", "tiles": [concept_tile("cloak_back", "capa"), concept_tile("staff", "flauta-bastón"),
                                                            concept_tile("feet", "sandalias")]},
                             {"label": "modelo", "tiles": t}]})
        return out

    def game_sheet(self, perch_W=None, hang_W=None, tells=()):
        """La lectura en el juego: cámara 52°/24 m, FOV 30, en el claro de bambú de noche (piso claro, cañas bambú claro,
        bosque oscuro) con Kaito al lado; parado en el piso, posado en una caña a 4.4 m y colgado, con y sin aviso."""
        self.use("game")
        self.look.set_moon(None)
        self.floor("path")
        self.clear_extra()
        self.forest()
        self.stalk(0.0, 0.0, 7.5, 4.4)
        self.stalk(-5.0, 1.0, 8.5, 4.8)
        self.stalk(4.3, -2.5, 7.5, 4.4)
        self.kaito((0.6, -4.5), 0.0)
        tiles = []

        def shot(name, label, focus, slots=(), color="gold", zoom=None):
            self.glow(slots, color)
            self.game_view(focus=focus)
            p = self.render(self.tile("g_" + name), res=(1280, 720))
            tiles.append({"img": p, "label": label})
            if zoom:
                pts = self.body_points() + [Vector((0.6, -4.5, 0.0)), Vector((0.6, -4.5, 1.5))]
                p2 = self.render(self.tile("g_" + name + "_z"), res=(1280, 720), border=self.border_around(pts, 0.03))
                tiles.append({"img": p2, "label": label + " (recorte 1:1)"})
            self.glow(())
        # parado en el piso, al lado de su caña
        self.arm.location = (0.9, 0.2, 0.0)
        self.apply(None)
        shot("ground", "parado (pose A) en el claro, Kaito adelante", (0.6, -1.8, 1.0), zoom=True)
        if perch_W is not None:
            # posado en el nudo de la caña: la raíz del modelo en el PerchNode (4.4 m)
            self.arm.location = (0.0, 0.0, 4.4)
            self.apply(perch_W)
            shot("perch", "posado en una caña a 4.4 m", (0.4, -2.4, 2.4), zoom=True)
            shot("perch_hi", "posado: aviso de dardo (cascabeles de los hombros en dorado)", (0.4, -2.4, 2.4),
                 slots=("Chikuo_GlintChimesHi", "Chikuo_GlintStaff"), zoom=True)
            shot("perch_white", "posado: caña cargada (todos los cascabeles en blanco)", (0.4, -2.4, 2.4),
                 slots=("Chikuo_GlintChimesHi", "Chikuo_GlintChimesLo"), color="white", zoom=True)
        if hang_W is not None:
            self.arm.location = (0.0, 0.0, 4.0)
            self.apply(hang_W)
            shot("hang", "colgado cabeza abajo de la caña", (0.4, -2.4, 2.2), zoom=True)
        self.arm.location = (0, 0, 0)
        self.apply(None)
        self.clear_extra()
        out = os.path.join(self.out, "game_sheet.png")
        self.sheet({"out": out, "title": "Chikuō ermitaño en la cámara del juego (52°, 24 m, FOV 30) en el claro de bambú",
                    "width": 1280, "tile_h": 360, "rows": [{"label": "", "tiles": tiles}]})
        return out

    def pose_sheet(self, poses, title, name, concept=(), lift=None):
        """Poses de prueba de la deformación desde tres lados (luz de estudio). poses = [(etiqueta, W, centro, escala)];
        lift = {etiqueta: metros que se sube el modelo (y la cámara) para que no quede bajo el piso}."""
        self.use("studio")
        self.floor()
        rows = []
        for i, (lab, W, center, scale) in enumerate(poses):
            self.apply(W)
            up = (lift or {}).get(lab, 0.0)
            self.arm.location = (0, 0, up)
            tiles = []
            for az in (20, 110, 200):
                self.set_studio_light(STUDIO if az < 150 else Vector((0.4, 0.75, 0.7)))
                self.ortho(Vector(center) + Vector((0, 0, up)), scale, az, 8)
                tiles.append({"img": self.render(self.tile(f"p_{name}_{i}_{az}"), res=(560, 640)), "label": f"{lab} ({az}°)"})
            if i < len(concept) and concept[i]:
                tiles.insert(0, concept_tile(*concept[i]))
            rows.append({"label": lab, "tiles": tiles})
        self.arm.location = (0, 0, 0)
        self.apply(None)
        out = os.path.join(self.out, name + "_sheet.png")
        self.sheet({"out": out, "title": title, "width": 1280, "tile_h": 300, "rows": rows})
        return out

    def lineup_sheet(self):
        """El elenco a escala (Kaito 1.5 m, Kokuyō, Chikuō) de frente y en la cámara del juego: el estilo, la escala y el
        valor contra los otros modelos."""
        self.use("game")
        self.floor("path")
        self.apply(None)
        self.kaito((-1.4, 0.0), 180.0)
        ko = self.import_ref(KOKUYO_FBX, None, name="Kokuyo")
        if ko:
            ko[0].location = (1.6, 0.0, ko[1])
        tiles = []
        self.look.set_moon(STUDIO)
        self.ortho((0.1, 0, 2.3), 5.2, 0, 3)
        tiles.append({"img": self.render(self.tile("lineup_front"), res=(1280, 720)), "label": "Kaito, Chikuō, Kokuyō (luz de estudio)"})
        self.look.set_moon(None)
        self.game_view(focus=(0.1, -1.0, 1.4))
        tiles.append({"img": self.render(self.tile("lineup_game"), res=(1280, 720)), "label": "cámara del juego, luna del mundo"})
        if ko:
            for o in ko[2]:
                bpy.data.objects.remove(o)
        out = os.path.join(self.out, "lineup_sheet.png")
        self.sheet({"out": out, "title": "El elenco a escala", "width": 1280, "tile_h": 360, "rows": [{"label": "", "tiles": tiles}]})
        return out
