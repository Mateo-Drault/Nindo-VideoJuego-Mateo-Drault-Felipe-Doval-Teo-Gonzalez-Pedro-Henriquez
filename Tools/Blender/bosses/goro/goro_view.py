"""Vistas de revisión de Gorō (Blender 4.4, -b): el modelo del equipo con la luz del juego (team_review.Review), los
clips de team_clips_goro horneados y, si se pide, la armadura de roca de la fase 2 (goro_armor) colgada de los
mismos huesos. Lo usan build_goro_armor.py (renders de la armadura) y goro_review.py (la cinemática de las rocas).

Marco: el de team_review: el personaje en metros del juego, parado en el origen y mirando a -Y del mundo de Blender
(hacia la cámara del juego).
"""
import bpy, os, sys, math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
for _p in (os.path.join(REPO, "Tools", "Blender", "anim"), os.path.join(REPO, "Tools", "Blender", "characters"),
           os.path.join(REPO, "Tools", "Blender", "characters", "kits"), os.path.join(REPO, "Tools", "Blender"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
sys.dont_write_bytecode = True

import nindo_anim as NA          # noqa: E402
import team_rig as T             # noqa: E402
import team_review as TR         # noqa: E402


class GoroView:
    """Gorō en la escena de revisión. clips: nombres de team_clips_goro a hornear (en una sola acción, como el export)."""

    def __init__(self, out_dir, clips=(), armor=False, kaito=False, res=(1280, 1280)):
        import importlib
        self.ch = T.TeamChar("goro", T.CHARS["goro"])
        self.mod = importlib.import_module("team_clips_goro")
        self.ranges, self.baked = {}, {}
        if clips:
            solver = T.TeamSolver(self.ch)
            want = [c for c in self.mod.clips(self.ch) if c.name in clips]
            baked = []
            for clip in want:
                frames, ctrls, roots, _, _ = T.bake(self.ch, clip, solver)
                travel = [(c.get("travel") or 0.0) + clip.root_vel.length * (f / T.FPS) for f, c in enumerate(ctrls)]
                self.baked[clip.name] = (clip, frames, travel)
                baked.append((clip, frames))
            _, self.ranges = NA.write_pack(self.ch.arm, self.ch.rig, baked, start=1, gap=10)
        self.armor = None
        if armor:
            import goro_armor as GA
            self.armor = GA.build_on(self.ch)
        self.rv = TR.Review(self.ch, out_dir, kaito=kaito)
        self.scn = self.rv.scn
        self.scn.render.resolution_x, self.scn.render.resolution_y = res
        if self.armor is not None:
            self.dress_armor()

    def dress_armor(self):
        """Materiales de revisión para la armadura (la misma luz que el cuerpo) y la cuenta en el encuadre."""
        import goro_armor as GA
        o = self.armor["object"]
        done = {}
        for s in o.material_slots:
            m = s.material
            if m.name not in done:
                done[m.name] = GA.review_material(self.rv.look, m)
            s.material = done[m.name]
        if o not in self.ch.meshes:
            self.ch.meshes.append(o)

    def set_frame(self, clip, f, moving=True, yaw=0.0):
        """Cuadro f del clip, con el avance del transform del juego si 'moving'."""
        c, _, travel = self.baked[clip]
        self.scn.frame_set(self.ranges[clip][0] + f)
        self.rv.face(yaw, Vector((0.0, -travel[min(f, len(travel) - 1)], 0.0)) if moving else Vector())

    def hero_camera(self, target=(0.0, 0.0, 1.7), azimuth=-35.0, elevation=12.0, dist=11.0, fov=32.0):
        """Perspectiva de 3/4 para mirar el modelado (azimuth 0 = de frente; negativo = desde su derecha)."""
        cam = self.rv.cam
        cam.data.type = 'PERSP'
        cam.data.sensor_fit = 'VERTICAL'
        cam.data.angle_y = math.radians(fov)
        cam.data.clip_start, cam.data.clip_end = 0.1, 200.0
        a, e = math.radians(azimuth), math.radians(elevation)
        d = Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e)))
        cam.location = Vector(target) + d * dist
        cam.rotation_euler = (-d).to_track_quat('-Z', 'Y').to_euler()
        self.rv.look.set_moon(Vector((0.4, -0.8, 0.6)), scale=1.0)

    def game_camera(self, focus=(0.0, 0.0, 0.8), yaw=0.0):
        NA.game_camera(self.rv.cam, focus, pitch=52.0, dist=24.0, fov=30.0, yaw=yaw)
        self.rv.look.set_moon()

    def render(self, path, framed=True, margin=0.04):
        if framed:
            return self.rv.render_framed(path, None, margin)
        self.scn.render.use_border = False
        NA.render(self.scn, path)
