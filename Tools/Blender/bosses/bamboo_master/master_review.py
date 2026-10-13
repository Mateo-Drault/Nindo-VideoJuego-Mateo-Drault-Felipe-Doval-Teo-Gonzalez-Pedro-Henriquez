"""Renders de revisión de Chikuō: cómo se ve EN EL JUEGO (cámara 52°/24 m, luz de luna en Gamma, niebla, el piso
oscuro del claro de bambú) y hojas de poses junto a Kaito (1.5 m, el modelo real del juego). También la fila del
elenco con el ABUELO al lado: el maestro no se le tiene que parecer.

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
STUDIO = Vector((-0.45, -0.7, 0.75))


class Review:
    def __init__(self, arm, meshes, out_dir, kaito=True, res=(1280, 720)):
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
        self.mats = {"Nindo_Palette": L.build("rv_palette", albedo_image=img),
                     "Nindo_Emissive": L.build("rv_emissive", albedo_image=img, emission_rgb=(1, 1, 1), emission_gain=1.0)}
        for n, rgb in MM.MAT_RGB.items():
            # los negros con el piso del juego (CharacterFactory.LiftBlacks)
            c = tuple(max(v, BLACK_FLOOR * v / max(rgb)) for v in rgb) if max(rgb) < BLACK_FLOOR else rgb
            self.mats[n] = L.build("rv_" + n, albedo_rgb=c)
        # versiones encendidas (el aviso de un golpe y los ojos de la fase 2), por slot
        self.lit = {}
        for n, rgb in MM.MAT_RGB.items():
            self.lit[(n, "gold")] = L.build("rv_gold_" + n, albedo_rgb=rgb, emission_rgb=GOLD, emission_gain=2.2)
            self.lit[(n, "red")] = L.build("rv_red_" + n, albedo_rgb=rgb, emission_rgb=CRIMSON, emission_gain=2.2)
        self.lit[("Master_Eyes", "jade")] = L.build("rv_eyes_lit", albedo_rgb=MM.EYES_RGB, emission_rgb=MM.EYES_GLOW_RGB,
                                                    emission_gain=1.6)
        # nombres originales de los slots (glow() los enciende por nombre)
        self._orig = {o.name: [s.material.name if s.material else "" for s in o.material_slots] for o in meshes.values()}
        for o in meshes.values():
            for s in o.material_slots:
                if s.material and s.material.name in self.mats:
                    s.material = self.mats[s.material.name]
        # piso del claro de bambú (pasto oscuro bajo la luna)
        bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
        self.ground = bpy.context.active_object
        self.ground.data.materials.append(L.build("rv_ground", albedo_rgb=hx("grass_dark")))
        self.kaito = self.import_kaito() if kaito else None
        self.set_phase(1)

    # ------------------------------------------------------------------ estado del modelo
    def set_phase(self, phase, thrown=False):
        """1 = con saco; 2 = sin saco; 3 = sin saco y con el bastón. 'thrown' muestra el saco que vuela."""
        m = self.meshes
        m["Master_Robe"].hide_render = phase != 1
        m["Master_RobeThrown"].hide_render = not thrown
        m["Master_Staff"].hide_render = phase != 3

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

    def border_from(self, pts, margin=0.04, min_px=(240, 240)):
        scn = self.scn
        bpy.context.view_layer.update()
        uv = [world_to_camera_view(scn, self.cam, p) for p in pts]
        x0, x1 = max(0.0, min(u.x for u in uv) - margin), min(1.0, max(u.x for u in uv) + margin)
        y0, y1 = max(0.0, min(u.y for u in uv) - margin), min(1.0, max(u.y for u in uv) + margin)
        W, H = scn.render.resolution_x, scn.render.resolution_y
        if (x1 - x0) * W < min_px[0]:
            c = (x0 + x1) / 2; x0, x1 = max(0, c - min_px[0] / W / 2), min(1, c + min_px[0] / W / 2)
        if (y1 - y0) * H < min_px[1]:
            c = (y0 + y1) / 2; y0, y1 = max(0, c - min_px[1] / H / 2), min(1, c + min_px[1] / H / 2)
        return x0, x1, y0, y1

    def render_border(self, path, b):
        scn = self.scn
        scn.render.use_border = True
        scn.render.use_crop_to_border = True
        scn.render.border_min_x, scn.render.border_max_x, scn.render.border_min_y, scn.render.border_max_y = b
        NA.render(scn, path)
        scn.render.use_border = False
        return path

    def render_framed(self, path, extra_pts=(), margin=0.04, with_kaito=False):
        pts = self.subject_points() + [Vector(p) for p in extra_pts]
        if with_kaito and getattr(self, "kaito_piv", None):
            k = self.kaito_piv.location
            pts += [Vector((k.x, k.y, 0.0)), Vector((k.x, k.y, 1.55))]
        return self.render_border(path, self.border_from(pts, margin))

    def render_square(self, path, size=560):
        scn = self.scn
        rx, ry = scn.render.resolution_x, scn.render.resolution_y
        scn.render.resolution_x = scn.render.resolution_y = size
        scn.render.use_border = False
        NA.render(scn, path)
        scn.render.resolution_x, scn.render.resolution_y = rx, ry

    def game_view(self, focus=(0, -1.6, 1.0), pitch=52.0, dist=24.0, fov=30.0, yaw=0.0):
        NA.game_camera(self.cam, focus, pitch, dist, fov, yaw)

    def ortho(self, center=(0, 0, 1.35), scale=3.4, azimuth=0.0, elevation=0.0):
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
    def glow(self, slots=(), color="gold", eyes=False):
        """Enciende solo los slots que pegan (como el juego: 'Master_GlintHandR'...) y los ojos de la fase 2."""
        for o in self.meshes.values():
            for i, slot in enumerate(o.material_slots):
                name = self._orig[o.name][i]
                if name == "Master_Eyes":
                    slot.material = self.lit[(name, "jade")] if eyes else self.mats[name]
                elif name in MM.MAT_RGB:
                    slot.material = self.lit[(name, color)] if name in slots else self.mats[name]

    # ------------------------------------------------------------------ hojas
    def model_sheet(self, tag="model", frame=None, title="Chikuō: modelo"):
        """Frente/perfil/espalda/3-4 con luz de estudio, detalles de cerca, las tres fases y la lectura del juego."""
        L = self.look
        if frame is not None:
            self.scn.frame_set(frame)
        self.show_kaito(False)
        self.set_phase(1)
        tiles = []
        for az, name, sd in ((0, "frente", STUDIO), (90, "perfil (izq.)", Vector((0.7, -0.3, 0.7))),
                             (180, "espalda", Vector((0.4, 0.75, 0.7))), (35, "3/4", STUDIO), (0, "desde arriba", STUDIO)):
            L.set_moon(sd, scale=1.0)
            self.ortho((0, 0, 1.35), 3.0, az, 70 if "arriba" in name else 6)
            p = os.path.join(self.out, f"_{tag}_{len(tiles)}.png")
            self.render_framed(p, margin=0.03)
            tiles.append({"img": p, "label": name + " (luz de estudio)"})
        close = []
        L.set_moon(STUDIO)
        for name, center, scale, az, el in (("cabeza", (0, -0.05, 2.38), 0.95, 25, 8),
                                            ("cabeza de perfil", (0, -0.05, 2.35), 0.95, 90, 4),
                                            ("cabeza desde arriba", (0, 0.0, 2.4), 1.1, 0, 62),
                                            ("mano", self.bone_head("Hand_R") + Vector((0.0, -0.03, -0.02)), 0.42, -70, 10),
                                            ("pie", (-0.16, -0.08, 0.2), 0.75, 30, 12)):
            self.ortho(center, scale, az, el)
            p = os.path.join(self.out, f"_{tag}_close_{len(close)}.png")
            self.render_square(p)
            close.append({"img": p, "label": name})
        phases = []
        for ph, az, lab in ((2, 0, "fase 2 (sin saco) frente"), (2, 180, "fase 2 espalda"), (3, 30, "fase 3 (bastón)")):
            self.set_phase(ph)
            self.ortho((0, 0, 1.35), 3.0, az, 6)
            p = os.path.join(self.out, f"_{tag}_ph_{len(phases)}.png")
            self.render_framed(p, margin=0.03)
            phases.append({"img": p, "label": lab})
        row3 = []
        self.show_kaito(True)
        self.place_kaito((0.9, -3.4), 0)
        for lab, ph, slots, col, eyes in (("52°/24 m, luna del mundo", 1, (), "gold", False),
                                          ("aviso dorado: palma derecha", 1, ("Master_GlintHandR",), "gold", False),
                                          ("fase 2, ojos jade, patada roja", 2, ("Master_GlintFootR",), "red", True),
                                          ("fase 3, bastón dorado", 3, ("Master_GlintStaff",), "gold", True)):
            L.set_moon(None)
            self.set_phase(ph)
            self.glow(slots, col, eyes)
            self.game_view()
            p = os.path.join(self.out, f"_{tag}_game_{len(row3)}.png")
            self.render_framed(p, with_kaito=True)
            row3.append({"img": p, "label": lab})
        self.glow(())
        self.set_phase(1)
        L.set_moon(None)
        self.show_kaito(False)
        out = os.path.join(self.out, f"{tag}_sheet.png")
        self.sheet({"out": out, "title": title, "width": 1280, "tile_h": 330, "delete": True,
                    "rows": [{"label": "modelo (ortográfica)", "tiles": tiles}, {"label": "de cerca", "tiles": close},
                             {"label": "fases", "tiles": phases},
                             {"label": "lectura en el juego (cámara 52°, 24 m, Kaito a 3.4 m)", "tiles": row3}]})
        return out

    def pose_sheet(self, poses, title="Chikuō: poses de prueba (PoseTest)", tag="poses"):
        """poses = [(cuadro de la escena, rótulo, fase, slots encendidos, color)]: el frente con luz de estudio y la
        cámara del juego con Kaito, para ver cómo deforma el esqueleto (hombros, rodillas, faldones, dedos)."""
        L = self.look
        rows = []
        for kind in ("front", "side", "game"):
            tiles = []
            for i, (f, lab, ph, slots, col) in enumerate(poses):
                self.scn.frame_set(f)
                self.set_phase(ph)
                self.glow(slots, col, ph >= 2)
                if kind == "game":
                    L.set_moon(None)
                    self.show_kaito(True)
                    self.place_kaito((0.9, -3.6), 0)
                    self.game_view()
                    p = os.path.join(self.out, f"_{tag}_{kind}_{i}.png")
                    self.render_framed(p, with_kaito=True)
                else:
                    L.set_moon(STUDIO if kind == "front" else Vector((-0.8, -0.35, 0.6)), scale=1.0)
                    self.show_kaito(False)
                    self.ortho((0, -0.3, 1.35), 3.3, 0 if kind == "front" else -90, 6)
                    p = os.path.join(self.out, f"_{tag}_{kind}_{i}.png")
                    self.render_framed(p, margin=0.03)
                tiles.append({"img": p, "label": lab})
            rows.append({"label": {"front": "frente (estudio)", "side": "perfil desde su derecha", "game": "cámara del juego"}[kind],
                         "tiles": tiles})
        self.glow(())
        self.set_phase(1)
        L.set_moon(None)
        out = os.path.join(self.out, f"{tag}_sheet.png")
        self.sheet({"out": out, "title": title, "width": 1280, "tile_h": 260, "delete": True, "rows": rows})
        return out

    def detail_sheet(self, poses, title="Chikuō: deformación de cerca", tag="detail"):
        """Las poses de prueba grandes desde tres lados (3/4 de frente, perfil y 3/4 de atrás) para revisar hombros,
        codos, rodillas, faldones, mangas y colas. poses = [(cuadro, rótulo, fase[, saco tirado visible])]."""
        L = self.look
        self.show_kaito(False)
        rows = []
        for i, (f, lab, ph, *rest) in enumerate(poses):
            self.scn.frame_set(f)
            self.set_phase(ph, thrown=bool(rest and rest[0]))
            self.glow((), "gold", ph >= 2)
            tiles = []
            for az, sd in ((30, STUDIO), (-90, Vector((-0.8, -0.35, 0.6))), (150, Vector((0.4, 0.75, 0.7)))):
                L.set_moon(sd, scale=1.0)
                self.ortho((0, -0.3, 1.35), 3.3, az, 8)
                p = os.path.join(self.out, f"_{tag}_{i}_{az}.png")
                self.render_framed(p, margin=0.02)
                tiles.append({"img": p, "label": f"{lab} ({az}°)"})
            rows.append({"label": lab, "tiles": tiles})
        self.set_phase(1)
        L.set_moon(None)
        out = os.path.join(self.out, f"{tag}_sheet.png")
        self.sheet({"out": out, "title": title, "width": 1280, "tile_h": 420, "delete": True, "rows": rows})
        return out

    def hands_sheet(self, frames, title="Chikuō: manos (palma, puño, pico de grulla, garra, espada, agarre)"):
        """Primeros planos de las dos manos en los cuadros dados: [(cuadro, rótulo)]."""
        L = self.look
        L.set_moon(STUDIO, scale=1.0)
        self.show_kaito(False)
        tiles = []
        for f, lab in frames:
            self.scn.frame_set(f)
            self.set_phase(2)
            for S, az in (("R", -60), ("L", 60)):
                c = self.bone_head("Hand_" + S) + (self.bone_head("Middle_%s_1" % S) - self.bone_head("Hand_" + S)) * 0.6
                self.ortho(c, 0.36, az, 12)
                p = os.path.join(self.out, f"_hand_{f}_{S}.png")
                self.render_square(p, 420)
                tiles.append({"img": p, "label": f"{lab} ({'der.' if S == 'R' else 'izq.'})"})
        self.set_phase(1)
        L.set_moon(None)
        out = os.path.join(self.out, "hands_sheet.png")
        self.sheet({"out": out, "title": title, "width": 1280, "tile_h": 250, "delete": True, "rows": [{"label": "", "tiles": tiles}]})
        return out

    # ------------------------------------------------------------------ clips
    def show_only(self, objs):
        names = {o.name for o in objs}
        for o in self.meshes.values():
            o.hide_render = o.name not in names

    def clip_sheet(self, clip, start, roots, show, labels, report=None, visfn=None):
        """Tres filas con el MISMO encuadre en todos los cuadros (se ve el recorrido): la cámara del juego (52°/24 m) con
        Kaito a 3.6 m, el perfil desde su derecha y el frente con luz de estudio. Se enciende el slot que pega desde el
        aviso hasta el fin del golpe (como en el juego) y los ojos jade en las fases 2 y 3."""
        scn = self.scn
        L = self.look
        t = clip.timing
        ph = getattr(clip, "phase", 1)
        glow_slot = t.get("glow")
        col = "red" if t.get("kind") == "dodge" else "gold"
        a0 = t.get("tell", [t.get("apex", 0)])[0]
        a1 = t.get("active", [0, -1])[1]
        eyes_from = next((e["frame"] for e in clip.events if e["fn"] == "EyesIgnite"), None)
        rows = []
        for title, kind in (("juego 52°/24 m (luna del mundo, Kaito a 3.6 m)", "game"), ("perfil (desde su derecha)", "side"),
                            ("frente (luz de estudio)", "front")):
            if kind == "game":
                L.set_moon(None)
                self.show_kaito(True)
                self.place_kaito((0.6, -3.6), 0)
                self.game_view(focus=(0, -1.6, 1.0), pitch=52, dist=24)
            else:
                L.set_moon(Vector((-0.8, -0.35, 0.6)) if kind == "side" else STUDIO, scale=1.0)
                self.show_kaito(False)
            pts = []
            for f in show:
                scn.frame_set(start + f)
                self.arm.location = roots[f]
                if visfn:
                    self.show_only(visfn(f))
                bpy.context.view_layer.update()
                pts += self.subject_points()
            if kind != "game":
                ax = 1 if kind == "side" else 0
                hs = [p[ax] for p in pts]
                zs = [p.z for p in pts]
                ch, cz = (min(hs) + max(hs)) / 2, (max(zs) + min(0.0, min(zs))) / 2
                span = max(max(zs) - min(0.0, min(zs)), (max(hs) - min(hs)) * 720 / 1280) + 0.5
                c = (0, ch, cz) if kind == "side" else (ch, 0, cz)
                self.ortho(c, span, -90 if kind == "side" else 0, 0)
            else:
                k = self.kaito_piv.location
                pts += [Vector((k.x, k.y, 0.0)), Vector((k.x, k.y, 1.55))]
            b = self.border_from(pts, 0.03)
            tiles = []
            for f, lab in zip(show, labels):
                scn.frame_set(start + f)
                self.arm.location = roots[f]
                if visfn:
                    self.show_only(visfn(f))
                eyes = ph >= 2 or (eyes_from is not None and f >= eyes_from)
                slots = tuple(glow_slot) if isinstance(glow_slot, (list, tuple)) else (glow_slot,)
                self.glow(slots if glow_slot and a0 <= f <= a1 else (), col, eyes)
                p = os.path.join(self.out, f"_{clip.name}_{kind}_{f:03d}.png")
                self.render_border(p, b)
                tiles.append({"img": p, "label": lab})
            rows.append({"label": title, "tiles": tiles})
        self.arm.location = (0, 0, 0)
        self.glow(())
        self.set_phase(1)
        L.set_moon(None)
        sub = ""
        if report:
            bits = []
            for k, lab in (("reach_m", "alcance {} m"), ("max_height_m", "alto máx {} m"), ("root_peak_mps_60hz", "avance pico {} m/s"),
                           ("tip_peak_mps", "golpe {} m/s"), ("tell_silhouette_change", "aviso {}"), ("loop_seam_deg", "costura {}°"),
                           ("plant_drift_cm", "pies {} cm")):
                if k in report:
                    bits.append(lab.format(report[k]))
            sub = "  |  " + ", ".join(bits)
        out = os.path.join(self.out, f"clip_{clip.name}.png")
        self.sheet({"out": out, "title": f"{clip.name}  ({clip.frames} cuadros, {clip.frames / NA.FPS:.2f} s){sub}", "width": 1280,
                    "tile_h": 210, "delete": True, "rows": rows})
        return out

    def lab_sheet(self, clip, start):
        """Las poses sueltas de --lab (cada una sostenida 12 cuadros): frente, perfil y cámara del juego."""
        names = clip.timing["names"]
        poses = []
        for i, nm in enumerate(names):
            ph = 3 if "3" in nm.split()[-1] else (2 if "2" in nm.split()[-1] else 1)
            poses.append((start + 12 * (i + 1) - 1, nm, ph, (), "gold"))
        return self.pose_sheet(poses, title="Chikuō: laboratorio de poses", tag="lab")

    # ------------------------------------------------------------------ al lado del elenco del juego
    TEAM = [  # (fbx relativo a Assets, alto en el juego, hacia dónde mira en Blender: 0 = -Y, 90 = +X, 180 = +Y)
        ("Nindo/Art/Models/Characters/Grandpa.fbx", 1.45, 180.0),
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
        # el FBX del abuelo trae también al ninja del secuestro ('Cube'): en la fila del elenco tapa al abuelo
        if "Grandpa" in rel:
            for o in meshes:
                if o.name.startswith("Cube"):
                    o.hide_render = True
        return piv

    def lineup_sheet(self, frame=1):
        """El elenco en fila con la cámara del juego: Kaito, el abuelo (¡no se le tiene que parecer!), un ninja, el
        sumo y Chikuō, con y sin saco."""
        scn = self.scn
        scn.frame_set(frame)
        self.arm.location = (3.0, 0.0, 0.0)
        self.place_kaito((-4.2, -1.0), 180.0)
        self.show_kaito(True)
        x = -2.9
        for rel, h, az in self.TEAM:
            self.import_team(rel, h, az, x)
            x += 1.5 if h < 2 else 2.1
        L = self.look
        tiles = []
        for lab, ph in (("cámara 52°, luna del mundo", 1), ("cámara 52°, fase 2", 2)):
            L.set_moon(None)
            self.set_phase(ph)
            self.game_view(focus=(-0.5, -0.8, 1.0), pitch=52, dist=24)
            p = os.path.join(self.out, f"_lineup_{len(tiles)}.png")
            self.render_framed(p, extra_pts=[(-4.4, -1.0, 0.0), (-4.4, -1.0, 1.5)], margin=0.03)
            tiles.append({"img": p, "label": lab})
        self.set_phase(1)
        L.set_moon(STUDIO)
        self.ortho((-0.5, -1.0, 1.4), 9.0, 0, 4)
        p = os.path.join(self.out, "_lineup_front.png")
        self.render_framed(p, extra_pts=[(-4.4, -1.0, 0.0), (-4.4, -1.0, 1.5)], margin=0.02)
        tiles.append({"img": p, "label": "frente (luz de estudio)"})
        L.set_moon(None)
        out = os.path.join(self.out, "lineup_sheet.png")
        self.sheet({"out": out, "title": "Chikuō junto al elenco: Kaito, el abuelo, ninja, sumo", "width": 1280, "tile_h": 340,
                    "delete": True, "rows": [{"label": "", "tiles": tiles}]})
        self.arm.location = (0, 0, 0)
        return out
