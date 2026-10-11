"""Renders de revisión de Chikuō: cómo se ve EN EL JUEGO (cámara 52°/24 m, luz de luna en Gamma, niebla, el piso
verde oscuro del claro de bambú) y hojas de contacto por clip junto a Kaito (1.5 m, el modelo real del juego).
También la fila del elenco con el ABUELO al lado: el maestro no se le tiene que parecer.

Se usa después de exportar: cambia los materiales de los objetos por los de revisión.
"""
import json, math, os
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
import nindo_anim as NA
import nindo_palette as P
import master_model as MM

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
KAITO_FBX = os.path.join(REPO, "Nindo", "Assets", "Animations teo", "kaitooo.fbx")
PALETTE_PNG = os.path.join(REPO, "Tools", "Blender", "out", "NindoPalette.png")
BLACK_FLOOR = 0.13          # CharacterFactory.BlackFloor
GOLD = (1.0, 0.72, 0.24)    # TellStyle.Gold
CRIMSON = (0.92, 0.157, 0.118)


class Review:
    def __init__(self, arm, meshes, out_dir, kaito=True, res=(1920, 1080)):
        self.arm, self.meshes = arm, meshes
        self.out = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.scn = NA.setup_review_scene(res)
        self.look = NA.GameLook()
        self.cam = NA.camera(self.scn)
        img = bpy.data.images.load(PALETTE_PNG, check_existing=False)
        img.colorspace_settings.name = 'Non-Color'
        L = self.look
        hx = lambda n: P.hex_to_rgb(dict(P.PALETTE)[n])
        self.mats = {
            "Nindo_Palette": L.build("rv_palette", albedo_image=img),
            "Nindo_Emissive": L.build("rv_emissive", albedo_image=img, emission_rgb=(1, 1, 1), emission_gain=1.0),
            "Master_WrapR": L.build("rv_wrap_r", albedo_rgb=MM.WRAP_RGB),
            "Master_WrapL": L.build("rv_wrap_l", albedo_rgb=MM.WRAP_RGB),
            "Master_FootR": L.build("rv_foot_r", albedo_rgb=(BLACK_FLOOR,) * 3),
            "Master_FootL": L.build("rv_foot_l", albedo_rgb=(BLACK_FLOOR,) * 3),
            "Master_Eyes": L.build("rv_eyes", albedo_rgb=MM.EYES_RGB),
        }
        # versiones encendidas (el aviso de un golpe y los ojos de la fase 2)
        self.lit = {"gold": L.build("rv_glow_gold", albedo_rgb=MM.WRAP_RGB, emission_rgb=GOLD, emission_gain=2.2),
                    "red": L.build("rv_glow_red", albedo_rgb=MM.WRAP_RGB, emission_rgb=CRIMSON, emission_gain=2.2),
                    "eyes": L.build("rv_eyes_lit", albedo_rgb=MM.EYES_RGB, emission_rgb=MM.EYES_GLOW_RGB, emission_gain=1.6)}
        # nombres originales de los slots del cuerpo (glow() los enciende por nombre)
        self._orig = [s.material.name if s.material else "" for s in meshes["Master_Body"].material_slots]
        for o in meshes.values():
            for s in o.material_slots:
                if s.material and s.material.name in self.mats:
                    s.material = self.mats[s.material.name]
        # piso del claro de bambú (pasto oscuro bajo la luna)
        bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
        self.ground = bpy.context.active_object
        self.ground.data.materials.append(L.build("rv_ground", albedo_rgb=hx("grass_dark")))
        self.kaito = self.import_kaito() if kaito else None
        self.set_thrown(False)

    # ------------------------------------------------------------------ estado del modelo
    def set_thrown(self, thrown_visible, robe_visible=True):
        self.meshes["Master_RobeThrown"].hide_render = not thrown_visible
        self.meshes["Master_Robe"].hide_render = not robe_visible

    # ------------------------------------------------------------------ Kaito de referencia
    def import_kaito(self):
        if not os.path.exists(KAITO_FBX):
            return None
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=KAITO_FBX)
        new = [o for o in bpy.data.objects if o not in before]
        arm = next(o for o in new if o.type == 'ARMATURE')
        meshes = [o for o in new if o.type == 'MESH']
        act = next((a for a in bpy.data.actions if a.name.endswith("|Idle")), None)
        if act:
            arm.animation_data_create()
            arm.animation_data.action = act
            try:
                if arm.animation_data.action_slot is None and len(act.slots):
                    arm.animation_data.action_slot = act.slots[0]
            except AttributeError:
                pass
        arm.data.pose_position = 'REST'
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        zs = []
        for o in meshes:
            oe = o.evaluated_get(dg)
            me = oe.to_mesh()
            zs += [(oe.matrix_world @ v.co).z for v in me.vertices]
            oe.to_mesh_clear()
        arm.data.pose_position = 'POSE'
        s = 1.5 / (max(zs) - min(zs))
        piv = bpy.data.objects.new("KaitoPivot", None)
        self.scn.collection.objects.link(piv)
        for o in new:
            if o.parent is None:
                o.parent = piv
        piv.scale = (s, s, s)
        self.kaito_z0 = -min(zs) * s
        self.lift_materials(meshes, "rv_k_")
        self.kaito_piv = piv
        self.place_kaito((0, -3.6), 0.0)
        return piv

    def lift_materials(self, meshes, prefix):
        # materiales del equipo con el piso de negros del juego (CharacterFactory.LiftBlacks)
        for o in meshes:
            for sl in o.material_slots:
                m = sl.material
                if m is None:
                    continue
                c = list(m.diffuse_color[:3])
                mx = max(c)
                if mx < BLACK_FLOOR:
                    c = [x / mx * BLACK_FLOOR for x in c] if mx > 0.005 else [0.85 * BLACK_FLOOR, 0.9 * BLACK_FLOOR, BLACK_FLOOR]
                sl.material = self.look.build(prefix + m.name, albedo_rgb=tuple(c))

    def place_kaito(self, xy, face_deg):
        """face_deg 0 = Kaito mira a +Y (hacia el jefe, de espaldas a la cámara del juego)."""
        if getattr(self, "kaito_piv", None) is None:
            return
        self.kaito_piv.location = (xy[0], xy[1], self.kaito_z0)
        self.kaito_piv.rotation_euler = (0, 0, math.radians(90.0 + face_deg))

    def show_kaito(self, on):
        if getattr(self, "kaito_piv", None) is None:
            return
        for o in self.kaito_piv.children_recursive:
            o.hide_render = not on

    # ------------------------------------------------------------------ encuadre y render
    def subject_points(self):
        dg = bpy.context.evaluated_depsgraph_get()
        pts = []
        for o in self.meshes.values():
            if o.hide_render:
                continue
            oe = o.evaluated_get(dg)
            for c in oe.bound_box:
                pts.append(oe.matrix_world @ Vector(c))
        return pts

    def render_framed(self, path, extra_pts=(), margin=0.06, min_size=(260, 260)):
        scn = self.scn
        bpy.context.view_layer.update()
        pts = self.subject_points() + [Vector(p) for p in extra_pts]
        if getattr(self, "kaito_piv", None) and not self.kaito_piv.children[0].hide_render:
            k = self.kaito_piv.location
            pts += [Vector((k.x, k.y, 0.0)), Vector((k.x, k.y, 1.55))]
        uv = [world_to_camera_view(scn, self.cam, p) for p in pts]
        xs = [u.x for u in uv]
        ys = [u.y for u in uv]
        x0, x1 = max(0.0, min(xs) - margin), min(1.0, max(xs) + margin)
        y0, y1 = max(0.0, min(ys) - margin), min(1.0, max(ys) + margin)
        W, H = scn.render.resolution_x, scn.render.resolution_y
        if (x1 - x0) * W < min_size[0]:
            c = (x0 + x1) / 2; x0, x1 = max(0, c - min_size[0] / W / 2), min(1, c + min_size[0] / W / 2)
        if (y1 - y0) * H < min_size[1]:
            c = (y0 + y1) / 2; y0, y1 = max(0, c - min_size[1] / H / 2), min(1, c + min_size[1] / H / 2)
        scn.render.use_border = True
        scn.render.use_crop_to_border = True
        scn.render.border_min_x, scn.render.border_max_x = x0, x1
        scn.render.border_min_y, scn.render.border_max_y = y0, y1
        NA.render(scn, path)
        scn.render.use_border = False
        return path

    def render_full_square(self, path, size=600):
        scn = self.scn
        rx, ry = scn.render.resolution_x, scn.render.resolution_y
        scn.render.resolution_x = scn.render.resolution_y = size
        scn.render.use_border = False
        NA.render(scn, path)
        scn.render.resolution_x, scn.render.resolution_y = rx, ry

    def game_view(self, focus=(0, -1.6, 1.0), pitch=52.0, dist=24.0, fov=30.0, yaw=0.0):
        NA.game_camera(self.cam, focus, pitch, dist, fov, yaw)

    def ortho(self, center=(0, 0, 1.3), scale=3.4, azimuth=0.0, elevation=0.0):
        NA.ortho_camera(self.cam, center, scale, azimuth, elevation)

    def sheet(self, layout):
        p = os.path.join(self.out, "_layout.json")
        json.dump(layout, open(p, "w", encoding="utf-8"), indent=1)
        NA.compose_sheet(p)
        try:
            os.remove(p)
        except OSError:
            pass

    def bone_head(self, name):
        bpy.context.view_layer.update()
        return self.arm.matrix_world @ self.arm.pose.bones[name].head

    # ------------------------------------------------------------------ brillo de los avisos
    def glow(self, limbs=(), color="gold", eyes=False):
        """Enciende solo el material de los miembros que pegan (como el juego) y los ojos de la fase 2."""
        body = self.meshes["Master_Body"]
        for i, slot in enumerate(body.material_slots):
            name = self._orig[i]
            if name.startswith("Master_") and name != "Master_Eyes":
                on = name[len("Master_"):] in limbs
                slot.material = self.lit[color] if on else self.mats[name]
            elif name == "Master_Eyes":
                slot.material = self.lit["eyes"] if eyes else self.mats[name]

    # ------------------------------------------------------------------ hojas
    def model_sheet(self, tag="model", frame=None, title="Chikuō - modelo"):
        """Frente/perfil/espalda/3-4 con luz de estudio, detalles de cerca y la lectura del juego (luna del mundo,
        con y sin saco, el aviso dorado en la palma)."""
        L = self.look
        if frame is not None:
            self.scn.frame_set(frame)
        tiles = []
        self.show_kaito(False)
        studio = Vector((-0.45, -0.7, 0.75))
        for az, name, sd in ((0, "frente", studio), (90, "perfil (izq.)", Vector((0.7, -0.3, 0.7))),
                             (180, "espalda", Vector((0.4, 0.75, 0.7))), (35, "3/4", studio)):
            L.set_moon(sd, scale=1.0)
            self.ortho((0, 0, 1.32), 2.9, az, 6)
            p = os.path.join(self.out, f"_{tag}_{az}.png")
            self.render_framed(p, margin=0.03)
            tiles.append({"img": p, "label": name + " (luz de estudio)"})
        close = []
        L.set_moon(studio)
        for name, center, scale, az, el in (("cabeza", (0, -0.05, 2.36), 0.9, 25, 8),
                                            ("cabeza de perfil", (0, -0.05, 2.33), 0.9, 90, 4),
                                            ("mano y puño", self.bone_head("Hand_R") + Vector((0.0, -0.05, 0.0)), 0.6, -60, 15),
                                            ("pies y vendas", (-0.16, -0.08, 0.3), 0.85, 25, 10)):
            self.ortho(center, scale, az, el)
            p = os.path.join(self.out, f"_{tag}_close_{len(close)}.png")
            self.render_full_square(p)
            close.append({"img": p, "label": name})
        # fase 2: sin saco, de frente y de espalda
        self.set_thrown(False, robe_visible=False)
        for az in (0, 180):
            self.ortho((0, 0, 1.32), 2.9, az, 6)
            p = os.path.join(self.out, f"_{tag}_p2_{az}.png")
            self.render_framed(p, margin=0.03)
            close.append({"img": p, "label": "fase 2 (sin saco) " + ("frente" if az == 0 else "espalda")})
        self.set_thrown(False, robe_visible=True)
        row3 = []
        self.show_kaito(True)
        self.place_kaito((0.9, -3.4), 0)
        for lab, robe, glow, eyes in (("52°/24 m, luna del mundo", True, (), False), ("aviso dorado: palma derecha", True, ("WrapR",), False),
                                      ("fase 2 (sin saco), ojos jade", False, (), True), ("fase 2, patada roja (pie derecho)", False, ("FootR",), True)):
            L.set_moon(None)
            self.set_thrown(False, robe_visible=robe)
            self.glow(glow, "red" if "Foot" in "".join(glow) else "gold", eyes)
            self.game_view()
            p = os.path.join(self.out, f"_{tag}_game_{len(row3)}.png")
            self.render_framed(p)
            row3.append({"img": p, "label": lab})
        self.glow(())
        self.set_thrown(False, robe_visible=True)
        L.set_moon(None)
        self.show_kaito(False)
        out = os.path.join(self.out, f"{tag}_sheet.png")
        self.sheet({"out": out, "title": title, "width": 1280, "tile_h": 380, "delete": True,
                    "rows": [{"label": "modelo (ortográfica)", "tiles": tiles}, {"label": "de cerca / fase 2", "tiles": close},
                             {"label": "lectura en el juego (cámara 52°, 24 m)", "tiles": row3}]})
        return out

    def _border_from(self, pts, margin=0.04):
        scn = self.scn
        bpy.context.view_layer.update()
        uv = [world_to_camera_view(scn, self.cam, p) for p in pts]
        x0, x1 = max(0.0, min(u.x for u in uv) - margin), min(1.0, max(u.x for u in uv) + margin)
        y0, y1 = max(0.0, min(u.y for u in uv) - margin), min(1.0, max(u.y for u in uv) + margin)
        return x0, x1, y0, y1

    def _render_border(self, path, b):
        scn = self.scn
        scn.render.use_border = True
        scn.render.use_crop_to_border = True
        scn.render.border_min_x, scn.render.border_max_x, scn.render.border_min_y, scn.render.border_max_y = b
        NA.render(scn, path)
        scn.render.use_border = False

    def clip_sheet(self, clip, start, roots, show, labels, report=None, robe=True, thrown=None, glow_at=None):
        """Tres filas con el MISMO encuadre en todos los cuadros (se ve el recorrido): la cámara del juego (52°/24 m)
        con Kaito a 3.6 m, el perfil desde su derecha y el frente. glow_at(f) -> (miembros, color) enciende el aviso."""
        scn = self.scn
        L = self.look
        rows = []
        views = [("juego 52°/24 m (luna del mundo)", "game"), ("perfil (desde su derecha)", "side"), ("frente", "front")]
        for title, kind in views:
            if kind == "game":
                L.set_moon(None)
                self.show_kaito(True)
                self.place_kaito((0.9, -3.6), 0)
                self.game_view()
            else:
                L.set_moon(Vector((-0.8, -0.35, 0.6)) if kind == "side" else Vector((-0.45, -0.7, 0.75)))
                self.show_kaito(False)
            pts = []
            for f in show:
                scn.frame_set(start + f)
                self.arm.location = roots[f]
                self.set_thrown(thrown(f) if thrown else False, robe)
                bpy.context.view_layer.update()
                pts += self.subject_points()
            if kind != "game":
                axis = 1 if kind == "side" else 0
                hs = [p.y if kind == "side" else p.x for p in pts]
                zs = [p.z for p in pts]
                ch, cz = (min(hs) + max(hs)) / 2, (max(zs) + min(0.0, min(zs))) / 2
                span = max(max(zs) - min(0.0, min(zs)), (max(hs) - min(hs)) * 1080 / 1920) + 0.4
                c = (0, ch, cz) if kind == "side" else (ch, 0, cz)
                self.ortho(c, span, -90 if kind == "side" else 0, 0)
            if kind == "game":
                k = self.kaito_piv.location
                pts += [Vector((k.x, k.y, 0.0)), Vector((k.x, k.y, 1.55))]
            b = self._border_from(pts)
            tiles = []
            for f, lab in zip(show, labels):
                scn.frame_set(start + f)
                self.arm.location = roots[f]
                self.set_thrown(thrown(f) if thrown else False, robe)
                if glow_at:
                    g = glow_at(f)
                    self.glow(g[0], g[1], g[2] if len(g) > 2 else False)
                p = os.path.join(self.out, f"_{clip.name}_{kind}_{f:03d}.png")
                self._render_border(p, b)
                tiles.append({"img": p, "label": lab})
            rows.append({"label": title, "tiles": tiles})
        self.glow(())
        self.arm.location = (0, 0, 0)
        self.set_thrown(False, True)
        L.set_moon(None)
        sub = ""
        if report:
            bits = []
            for k_, lab in (("max_height_m", "alto máx {} m"), ("hit_peak_mps", "punto que pega: pico {} m/s"),
                            ("hit_outside_ratio", "fuera del golpe {}"), ("root_peak_mps_60hz", "avance pico {} m/s"),
                            ("loop_seam_deg", "costura {}°"), ("tell_silhouette_change", "cambio de silueta {}")):
                if k_ in report:
                    bits.append(lab.format(report[k_]))
            sub = "  |  " + ", ".join(bits)
        out = os.path.join(self.out, f"clip_{clip.name}.png")
        self.sheet({"out": out, "title": f"{clip.name}  ({clip.frames} cuadros, {clip.frames / NA.FPS:.2f} s){sub}", "width": 1280,
                    "tile_h": 190, "delete": True, "rows": rows})
        return out

    # ------------------------------------------------------------------ al lado del elenco del juego
    TEAM = [  # (fbx relativo a Assets, alto en el juego, hacia dónde mira en Blender: 0 = -Y, 90 = +X, 180 = +Y)
        ("Nindo/Art/Models/Characters/Grandpa.fbx", 1.45, 0.0),
        ("Models/Ninja/Ninja 1.fbx", 1.7, 90.0),
        ("Characters/Sumo/luchadorsumo.fbx", 2.5, 180.0),
    ]

    def import_team(self, rel, height, front_az, x):
        path = os.path.join(REPO, "Nindo", "Assets", rel)
        if not os.path.exists(path):
            return None
        before, acts = set(bpy.data.objects), set(bpy.data.actions)
        bpy.ops.import_scene.fbx(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        arm = next((o for o in new if o.type == 'ARMATURE'), None)
        meshes = [o for o in new if o.type == 'MESH']
        if arm is not None:
            act = next((a for a in bpy.data.actions if a not in acts and a.name.endswith("|Idle")), None)
            if act:
                arm.animation_data_create()
                arm.animation_data.action = act
                try:
                    if arm.animation_data.action_slot is None and len(act.slots):
                        arm.animation_data.action_slot = act.slots[0]
                except AttributeError:
                    pass
            arm.data.pose_position = 'REST'
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        zs = []
        for o in meshes:
            oe = o.evaluated_get(dg)
            me = oe.to_mesh()
            zs += [(oe.matrix_world @ v.co).z for v in me.vertices]
            oe.to_mesh_clear()
        if arm is not None:
            arm.data.pose_position = 'POSE'
        s = height / (max(zs) - min(zs))
        piv = bpy.data.objects.new("TeamPivot", None)
        self.scn.collection.objects.link(piv)
        for o in new:
            if o.parent is None:
                o.parent = piv
        piv.scale = (s, s, s)
        piv.location = (x, -1.0, -min(zs) * s)
        piv.rotation_euler = (0, 0, math.radians(-front_az))
        self.lift_materials(meshes, "rv_t_")
        return piv

    def lineup_sheet(self, frame=1):
        """El elenco en fila con la cámara del juego: Kaito, el abuelo (¡no se le tiene que parecer!), un ninja, el
        sumo y Chikuō, con y sin saco."""
        scn = self.scn
        scn.frame_set(frame)
        self.arm.location = (3.2, 0.0, 0.0)
        self.place_kaito((-4.4, -1.0), 180.0)
        self.show_kaito(True)
        x = -3.0
        for rel, h, az in self.TEAM:
            self.import_team(rel, h, az, x)
            x += 1.6 if h < 2 else 2.2
        L = self.look
        tiles = []
        for lab, robe in (("cámara 52° - luna del mundo", True), ("cámara 52° - fase 2", False)):
            L.set_moon(None)
            self.set_thrown(False, robe)
            self.game_view(focus=(-0.4, -0.8, 1.0), pitch=52, dist=24)
            p = os.path.join(self.out, f"_lineup_{len(tiles)}.png")
            self.render_framed(p, margin=0.03)
            tiles.append({"img": p, "label": lab})
        self.set_thrown(False, True)
        L.set_moon(Vector((-0.45, -0.7, 0.75)))
        self.ortho((-0.4, -1.0, 1.3), 3.3, 0, 4)
        p = os.path.join(self.out, "_lineup_front.png")
        self.render_framed(p, margin=0.02)
        tiles.append({"img": p, "label": "frente (luz de estudio)"})
        L.set_moon(None)
        out = os.path.join(self.out, "lineup_sheet.png")
        self.sheet({"out": out, "title": "Chikuō junto al elenco: Kaito, el abuelo, ninja, sumo", "width": 1280, "tile_h": 340,
                    "delete": True, "rows": [{"label": "", "tiles": tiles}]})
        self.arm.location = (0, 0, 0)
        return out
