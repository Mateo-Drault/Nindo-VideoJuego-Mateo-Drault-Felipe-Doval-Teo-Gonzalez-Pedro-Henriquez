"""Hojas de revisión de los clips del Chikuō ermitaño: cada clip en cuadros clave (luz de estudio, 3/4 y perfil, con la
caña de la arena cuando el clip es de arriba) y las poses de aviso con la cámara del juego (52°, 24 m, FOV 30) en el claro
de noche, recortadas a escala 1:1 de una pantalla de 1080 px (lo que de verdad ve el jugador: ~100 px de alto).

La caña es la de verdad (Nindo/Assets/Nindo/Art/Models/Props/arena_stalk_inner.fbx de la rama c4/arena, solo se lee), con
el arco del código (ArenaStalk.SetBend: cada tramo gira theta * w_k) para mirar al viejo sobre la caña cargada.
"""
import math, os
import bpy
from mathutils import Vector, Matrix
import chikuo_review as RV
import chikuo_anim as CA

ARENA_WT = os.path.abspath(os.path.join(RV.REPO, "..", "c4-arena"))
STALK_FBX = [os.path.join(ARENA_WT, "Nindo", "Assets", "Nindo", "Art", "Models", "Props", "arena_stalk_inner.fbx"),
             os.path.join(RV.REPO, "Nindo", "Assets", "Nindo", "Art", "Models", "Props", "arena_stalk_inner.fbx")]


class ClipReview(RV.Review):
    def __init__(self, arm, rig, meshes, out_dir):
        super().__init__(arm, rig, meshes, out_dir)
        self.real = None
        self.real_segs = []

    # ------------------------------------------------------------------ la caña de la arena
    def real_stalk(self):
        """Importa una vez la caña de adentro de c4/arena; devuelve su raíz (pivote en la base) o None."""
        if self.real is not None:
            return self.real
        path = next((p for p in STALK_FBX if os.path.exists(p)), None)
        if path is None:
            return None
        before = set(bpy.data.objects)
        bpy.ops.import_scene.fbx(filepath=path)
        new = [o for o in bpy.data.objects if o not in before]
        piv = bpy.data.objects.new("StalkPivot", None)
        self.scn.collection.objects.link(piv)
        for o in new:
            if o.parent is None:
                o.parent = piv
        for o in new:
            if o.type == 'MESH':
                self.assign([o])
                for sl in o.material_slots:
                    m = sl.material
                    if m is not None and m.name not in [x.name for x in self.mats.values()]:
                        sl.material = self.mats["Nindo_Palette"]
        self.real = piv
        self.real_objs = new
        segs = {o.name.split(".")[0]: o for o in new}
        self.real_segs = [segs.get(f"Seg_{k:02d}") for k in range(8)]
        self.real_rest = [s.matrix_basis.copy() if s else None for s in self.real_segs]
        bpy.context.view_layer.update()
        pn = segs.get("PerchNode")
        self.real_perch = pn
        return piv

    def place_stalk(self, base_xy, theta=0.0, direction=(0, 1, 0)):
        """La caña con la base en (x, y, 0) y el arco del código; devuelve dónde quedó el PerchNode (matriz de mundo)."""
        piv = self.real_stalk()
        if piv is None:
            self.stalk(base_xy[0], base_xy[1], 7.5, 4.4)
            return Matrix.Translation((base_xy[0], base_xy[1], CA.PERCH_H))
        piv.location = (base_xy[0], base_xy[1], 0.0)
        bpy.context.view_layer.update()
        d = Vector(direction)
        d.z = 0
        d.normalize()
        axw = Vector((0, 0, 1)).cross(d).normalized()
        n = 8
        tot = n * (n + 1) * 0.5
        for k, s in enumerate(self.real_segs):
            if s is None:
                continue
            s.matrix_basis = self.real_rest[k]
            bpy.context.view_layer.update()
            # el eje del mundo llevado al espacio del padre del tramo (como ArenaStalk: parentInv[k] * axis)
            Pm = s.parent.matrix_world.to_3x3().normalized() if s.parent else Matrix.Identity(3)
            ax = (Pm.inverted() @ axw).normalized()
            w = (k + 1) / tot
            s.matrix_basis = Matrix.Translation(self.real_rest[k].translation) @ Matrix.Rotation(math.radians(theta * w), 4, ax) \
                @ self.real_rest[k].to_3x3().to_4x4()
            bpy.context.view_layer.update()
        if self.real_perch is not None:
            return self.real_perch.matrix_world.copy()
        return Matrix.Translation((base_xy[0], base_xy[1], CA.PERCH_H))

    def hide_stalk(self, hide=True):
        if self.real is not None:
            for o in self.real_objs:
                o.hide_render = hide

    def fixed_box(self, pts, w_px, h_px, res=(1920, 1080)):
        """Un recorte de w x h píxeles de la pantalla de 1080p centrado en los puntos (escala 1:1 en la hoja)."""
        from bpy_extras.object_utils import world_to_camera_view
        bpy.context.view_layer.update()
        uv = [world_to_camera_view(self.scn, self.cam, Vector(p)) for p in pts]
        cx = (min(u.x for u in uv) + max(u.x for u in uv)) * 0.5
        cy = (min(u.y for u in uv) + max(u.y for u in uv)) * 0.5
        hw, hh = w_px / res[0] * 0.5, h_px / res[1] * 0.5
        cx, cy = max(hw, min(1 - hw, cx)), max(hh, min(1 - hh, cy))
        return (cx - hw, cx + hw, cy - hh, cy + hh)

    # ------------------------------------------------------------------ hojas de un clip
    def put(self, W, M=None):
        """Pose W con la raíz del modelo en la matriz de mundo M (el PerchNode, el piso...)."""
        self.apply(W)
        self.arm.matrix_world = M if M is not None else Matrix.Identity(4)
        bpy.context.view_layer.update()

    def clip_sheet(self, clip, frames, roots, picks, labels, report_line="", views=((35, 6), (100, 4))):
        """Cuadros 'picks' del clip en estudio desde dos lados (con la caña recta en los de arriba)."""
        self.use("studio")
        self.floor()
        space = clip.timing.get("space", "ground")
        up = space in ("perch",)
        rows = []
        if up:
            self.place_stalk((0.0, 0.0))
            self.hide_stalk(False)
        else:
            self.hide_stalk(True)
        for az, el in views:
            tiles = []
            for f, lab in zip(picks, labels):
                r = roots[f]
                M = Matrix.Translation((r.x, r.y, CA.PERCH_H if up else 0.0))
                self.put(frames[f], M)
                pts = self.body_points()
                zc = sum(p.z for p in pts) / len(pts)
                xc = sum(p.x for p in pts) / len(pts)
                yc = sum(p.y for p in pts) / len(pts)
                hz = max(p.z for p in pts) - min(p.z for p in pts)
                self.set_studio_light(Matrix.Rotation(math.radians(az), 3, 'Z') @ RV.STUDIO)
                self.ortho(Vector((xc, yc, zc)), max(2.9, hz + 0.6), az, el)
                tiles.append({"img": self.render(self.tile(f"c_{clip.name}_{az}_{f}"), res=(300, 400)), "label": lab})
            rows.append({"label": f"{az}°", "tiles": tiles})
        self.arm.matrix_world = Matrix.Identity(4)
        self.hide_stalk(True)
        out = os.path.join(self.out, f"clip_{clip.name}.png")
        self.sheet({"out": out, "title": f"{clip.name} ({clip.frames} cuadros){'  ' + report_line if report_line else ''}",
                    "width": 1280, "tile_h": 300, "rows": rows})
        return out

    def game_tells(self, shots, name="tells"):
        """Las poses de aviso con la cámara del juego en el claro de noche, recortadas 1:1 de 1920x1080. shots =
        [(etiqueta, W, 'perch'|'ground', slots que brillan, color, theta del arco)]."""
        self.use("game")
        self.look.set_moon(None)
        self.floor("path")
        self.clear_extra()
        self.forest()
        self.kaito((0.8, -6.0), 0.0)
        tiles = []
        for i, (lab, W, space, slots, color, theta) in enumerate(shots):
            if space == "perch":
                M = self.place_stalk((0.0, 0.0), theta, (0.0, 1.0, 0.0))
                self.hide_stalk(False)
            else:
                self.hide_stalk(True)
                M = Matrix.Translation((0.0, -1.0, 0.0))
            self.put(W, M)
            self.glow(slots, color)
            focus = (0.5, -3.0, 1.6 if space == "perch" else 0.9)
            self.game_view(focus=focus, pitch=52.0, dist=24.0, fov=30.0)
            p = self.render(self.tile(f"g_{name}_{i}"), res=(1920, 1080), border=self.fixed_box(self.body_points(), 380, 300))
            tiles.append({"img": p, "label": lab})
            self.glow(())
        self.arm.matrix_world = Matrix.Identity(4)
        self.hide_stalk(True)
        self.clear_extra()
        out = os.path.join(self.out, name + ".png")
        self.sheet({"out": out, "title": "Avisos con la cámara del juego (52°, 24 m, FOV 30), recorte 1:1 de 1080p",
                    "width": 1280, "tile_h": 300, "rows": [{"label": "", "tiles": tiles}]})
        return out
