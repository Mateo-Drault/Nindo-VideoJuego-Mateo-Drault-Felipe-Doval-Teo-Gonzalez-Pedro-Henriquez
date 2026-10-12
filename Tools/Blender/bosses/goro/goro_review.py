"""Hojas de revisión de Gorō con la armadura de roca (Blender 4.4, -b), incluida la cinemática de armado.

  blender -b --factory-startup --python Tools/Blender/bosses/goro/goro_review.py -- OUT [--clips FakeDefeat,ArmorRise]
          [--frames 0,24,...] [--hero]

Hornea los clips pedidos de team_clips_goro (como build_team_anims), arma la armadura (goro_armor) colgada de los mismos
huesos y renderiza cada cuadro con la cámara del juego (52°, 24 m, FOV 30) y, con --hero, un plano de 3/4 más cerca. En
ArmorRise las rocas vuelan con la MISMA fórmula que tiene que usar el juego (flight_pose, contrato en Kit_goro_armor.json):
sirve para ver la cinemática antes de programarla. En el resto de los clips, la armadura está puesta si timing['armored'].
"""
import bpy, os, sys, math, json
from mathutils import Vector, Matrix, Quaternion

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import goro_view as GV       # noqa: E402
import goro_armor as GA      # noqa: E402
import nindo_anim as NA      # noqa: E402

FPS = 30.0


def flight_pose(piece, t, attached, root=Matrix.Identity(4)):
    """Dónde está la roca 'piece' a los t s del clip (None: todavía no salió). attached: su matriz de mundo pegada al
    cuerpo en ese instante (posición y giro). root: el transform de Gorō (la salida 'start' es respecto de él).

    La fórmula del contrato: sale a t0 = slam/30 - flight desde start (enterrada 0.3 m: se arranca del piso) y llega a
    la pieza pegada justo en slam/30; u = (t - t0) / flight; posición = lerp(salida, pegada, u^2) + arriba * arc * 4u(1-u)
    (acelera hacia el cuerpo: se clava); giro = el de pegada por una vuelta de 'spin' grados alrededor de un eje fijo de
    la pieza que se deshace con (1 - u)^2 (llega derecha)."""
    t1 = piece["slam"] / FPS
    t0 = t1 - piece["flight"]
    if t < t0:
        return None
    if t >= t1:
        return attached
    u = (t - t0) / piece["flight"]
    start = root @ Vector(piece["start"])
    end = attached.translation
    pos = start.lerp(end, u * u) + Vector((0.0, 0.0, piece["arc"] * 4.0 * u * (1.0 - u)))
    axis = Vector(spin_axis(piece["name"]))
    q = Quaternion(axis, math.radians(piece["spin"]) * (1.0 - u) ** 2)
    R = attached.to_quaternion() @ q
    return Matrix.Translation(pos) @ R.to_matrix().to_4x4()


def spin_axis(name):
    """Eje de la vuelta de cada pieza (determinista, normalizado; también va al sidecar)."""
    h = sum(ord(c) * (i + 1) for i, c in enumerate(name))
    v = Vector((math.sin(h * 0.37), math.cos(h * 0.53), 0.6 + 0.4 * math.sin(h * 0.11)))
    return tuple(round(x, 4) for x in v.normalized())


class ArmorFlight:
    """Mueve los huesos Acc_Roca_* de la armadura armada en la escena según flight_pose (y los esconde antes de salir)."""

    def __init__(self, view):
        self.v = view
        ch = view.ch
        self.arm = ch.arm
        self.pieces = {p["name"]: p for p in GA.PIECES}
        # el marco de autoría en el mundo de la escena de revisión: Gorō parado en el origen mirando a -Y (team_review)
        self.root = Matrix.Identity(4)

    def apply(self, t, clip):
        arm = self.arm
        bpy.context.view_layer.update()
        A = arm.matrix_world
        for name, p in self.pieces.items():
            pb = arm.pose.bones[GA.BONE_PREFIX + name]
            pb.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        if clip != "ArmorRise":
            return
        for name, p in self.pieces.items():
            pb = arm.pose.bones[GA.BONE_PREFIX + name]
            attached = A @ pb.matrix
            M = flight_pose(p, t, attached, self.root)
            if M is None:
                pb.matrix_basis = Matrix.Diagonal((0.0001, 0.0001, 0.0001, 1.0))
            else:
                pb.matrix = A.inverted() @ M
        bpy.context.view_layer.update()


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    out = argv[0]
    clips = ("FakeDefeat", "ArmorRise")
    frames = None
    hero = "--hero" in argv
    for i, a in enumerate(argv):
        if a == "--clips":
            clips = tuple(argv[i + 1].split(","))
        if a == "--frames":
            frames = [int(x) for x in argv[i + 1].split(",")]
    os.makedirs(out, exist_ok=True)
    v = GV.GoroView(out, clips=clips, armor=True, res=(1280, 1280))
    fl = ArmorFlight(v)
    obj = v.armor["object"]
    rows = []
    for name in clips:
        clip, _, _ = v.baked[name]
        fs = frames or clip.timing.get("sheet") or list(range(0, clip.frames + 1, 10))
        armored = clip.timing.get("armored", name not in ("Intro", "FakeDefeat", "ArmorRise"))
        tiles = []
        for f in fs:
            v.set_frame(name, f, moving=True)
            obj.hide_render = not (armored or name == "ArmorRise")
            fl.apply(f / FPS, name)
            if hero:
                v.hero_camera(target=(0.0, 0.3, 1.2), azimuth=-40.0, elevation=24.0, dist=13.0)
                p = os.path.join(out, f"_{name}_hero_{f:03d}.png")
                v.render(p, framed=False)
                tiles.append({"img": p, "label": f"f{f}"})
            v.game_camera(focus=(0.0, 0.3, 0.8))
            p = os.path.join(out, f"_{name}_game_{f:03d}.png")
            v.render(p, framed=False)
            tiles.append({"img": p, "label": f"f{f} juego"})
        rows.append({"label": name, "tiles": tiles})
    for r in rows:
        lay = {"out": os.path.join(out, f"goro_{r['label']}.png"), "title": f"Gorō · {r['label']} (armadura de roca)",
               "width": 1280, "tile_h": 300, "rows": [r], "delete": True}
        p = os.path.join(out, "_layout.json")
        json.dump(lay, open(p, "w", encoding="utf-8"), indent=1)
        NA.compose_sheet(p)


if __name__ == "__main__":
    main()
