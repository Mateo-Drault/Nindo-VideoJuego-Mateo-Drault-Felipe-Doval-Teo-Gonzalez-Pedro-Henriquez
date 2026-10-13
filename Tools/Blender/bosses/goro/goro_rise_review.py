"""La cinemática de la armadura tal como la arma el juego (GoroArmor.PlanAssembly + GoroBoss.PlayRiseShot), en Blender:

  "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --python Tools/Blender/bosses/goro/goro_rise_review.py -- OUT

Las rocas que se pegan mientras está tirado (antes de 'kneel') salen del piso a 4.6-5.2 m de él, a un costado del plano
(perpendicular a la cámara, un poco hacia atrás) y vuelan bajas (arco 1.3-1.5 m): cruzan la pantalla. Las demás salen
de la pared del cráter de la cumbre (radio 17.5 m alrededor del centro de la arena; acá Gorō está a 4.5 m del centro) a
6.5-9 m, las que vendrían del lado de la cámara espejadas al otro lado, con arco 2.2 + 0.3 d. Vuelan 0.8-1.2 s, 2.2
veces más grandes al salir, y llegan pegadas en el cuadro 'slam_<Pieza>' de ArmorRise. La cámara
es el plano de costado del juego (GoroBoss.PlayRiseShot: por su IZQUIERDA, el lado contrario al martillo clavado, 85 % de
costado y 45 % de frente; de 7.2 a 6 m mientras está tirado y desde que se arrodilla hasta el rugido se aleja a 12.5 m
mirando a 3.4 m de altura; FOV 42). Hoja: OUT/goro_ArmorRise_juego.png
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
RIM = 17.5
SHOT_START, SHOT_NEAR, SHOT_FAR = 7.2, 6.0, 12.5
SIDE_DIST, SIDE_BACK, SIDE_ARC = 4.6, 0.38, 1.3   # GoroArmor: las que se tiran de costado
FLIGHT_SCALE = 1.2                 # GoroArmor.FlightScale
# GoroArmor.Specs: giro (grados), eje y dirección de salida en el marco de Gorō de Unity (+Z adelante, +X derecha)
SPECS = {
    "Greave_L": (200, (0.8876, 0.4379, -0.1429), (-2.6, -1.8)), "Greave_R": (220, (0.1171, 0.879, -0.4622), (2.8, -1.4)),
    "Knee_L": (260, (0.6669, 0.2002, -0.7178), (-3.4, 1.0)), "Knee_R": (240, (0.2791, 0.5968, -0.7523), (3.6, 0.6)),
    "Tasset_L": (180, (-0.1669, 0.7071, -0.6871), (-4.2, -0.6)), "Tasset_R": (200, (-0.6266, 0.5556, -0.5465), (4.0, -1.2)),
    "Bracer_R": (300, (0.329, 0.6242, 0.7086), (3.2, 2.6)), "Bracer_L": (280, (0.5998, 0.5965, 0.5333), (-3.4, 2.4)),
    "Chest_Low": (160, (0.3482, 0.6562, 0.6694), (-0.6, 4.6)), "Chest_High": (180, (0.6125, 0.6774, -0.4075), (0.8, 5.0)),
    "Pauldron_L": (220, (0.5757, 0.4057, -0.7099), (-5.2, -2.2)), "Pauldron_R": (240, (-0.6935, 0.3359, -0.6374), (5.4, -1.6)),
    "Ridge_L": (140, (0.9774, 0.2073, -0.0406), (-2.4, -6.0)), "Ridge_R": (160, (-0.7908, 0.585, -0.1799), (2.2, -6.2)),
    "Horn_L": (320, (-0.6987, 0.6839, 0.21), (-1.6, -4.4)), "Horn_R": (340, (-0.8706, 0.1879, 0.4547), (1.6, -4.2)),
}


def u2b(x, y, z):
    """Unity (marco de Gorō) -> Blender de la escena de revisión (Gorō mira a -Y): x -> -x, z -> -y, y -> z."""
    return Vector((-x, -z, y))


def plan(center, side_until):
    """GoroArmor.PlanAssembly con Gorō en el origen mirando a -Y ('side_until': s de ArmorRise, el 'kneel')."""
    c = Vector((0.0, 0.0, 0.0))
    fwd, right = u2b(0, 0, 1), u2b(1, 0, 0)
    to_c = (center - c); to_c.z = 0
    cam_dir = (-right * 0.85 + fwd * 0.45).normalized()
    inward = to_c.normalized() if to_c.length > 0.1 else -fwd
    for _ in range(8):
        far = c + cam_dir * SHOT_FAR - center
        far.z = 0
        if far.length <= RIM - 1.5:
            break
        cam_dir = cam_dir.slerp(inward, 0.3)
        cam_dir.z = 0
        cam_dir.normalize()
    out = {}
    cs = cam_dir.copy(); cs.z = 0; cs.normalize()
    # Vector3.Cross(up, camSide) de Unity llevado a esta escena (u2b invierte la mano)
    across = -Vector((0.0, 0.0, 1.0)).cross(cs)
    for i, p in enumerate(GA.PIECES):
        spin, axis, frm = SPECS[p["name"]]
        d = u2b(frm[0], 0, frm[1]); d.z = 0; d.normalize()
        side_throw = p["slam"] / FPS < side_until
        if side_throw:
            d = (across * (1.0 if d.dot(across) >= 0 else -1.0) - cs * SIDE_BACK).normalized()
            dist = SIDE_DIST + 0.3 * (i % 3)
        else:
            k = d.dot(cs)
            if k > 0.15:
                d = (d - cs * (2 * k)).normalized()
            o = c - center; o.z = 0
            b = o.dot(d)
            disc = b * b - (o.length_squared - RIM * RIM)
            dist = min(9.0, max(6.5, -b + math.sqrt(disc) if disc > 0 else 9.0))
        q = c + d * dist
        q.z = 0.2                      # el piso de la cumbre (la escena es plana)
        real = (q - Vector((0, 0, 1.6))).length
        flight = min(1.2, max(0.8, real / 10.0))
        slam = p["slam"] / FPS
        out[p["name"]] = dict(start=q, flight=flight, launch=slam - flight, slam=slam,
                              arc=SIDE_ARC + 0.1 * (i % 3) if side_throw else 2.2 + 0.3 * real,
                              spin=spin * 1.6, axis=u2b(*axis).normalized())
    return out, cam_dir


def apply(v, plans, t, f):
    arm = v.ch.arm
    for name in plans:
        arm.pose.bones[GA.BONE_PREFIX + name].matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    A = arm.matrix_world
    for name, p in plans.items():
        pb = arm.pose.bones[GA.BONE_PREFIX + name]
        if t < p["launch"]:
            pb.matrix_basis = Matrix.Diagonal((0.0001, 0.0001, 0.0001, 1.0))
            continue
        u = min(1.0, (t - p["launch"]) / p["flight"])
        if u >= 1.0:
            continue
        att = A @ pb.matrix
        pos = p["start"].lerp(att.translation, u * u) + Vector((0, 0, p["arc"] * 4 * u * (1 - u)))
        R = Quaternion(p["axis"], math.radians(p["spin"]) * (1 - u) ** 2) @ att.to_quaternion()
        sc = 1 + FLIGHT_SCALE * (1 - u)
        pb.matrix = A.inverted() @ (Matrix.Translation(pos) @ R.to_matrix().to_4x4() @ Matrix.Diagonal((sc, sc, sc, 1.0)))
    bpy.context.view_layer.update()


def ss(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def lerp(a, b, k):
    return a + (b - a) * k


def side_camera(cam, cam_dir, ts, kneel, roar):
    """GoroBoss.PlayRiseShot: cerca y bajo mientras está tirado; desde que se arrodilla se aleja y sube hasta el rugido."""
    a, b = ss(ts / kneel), ss((ts - kneel) / max(0.1, roar - kneel))
    c = Vector((0.0, 0.0, 0.0))
    pos = c + cam_dir * lerp(lerp(SHOT_START, SHOT_NEAR, a), SHOT_FAR, b) + Vector((0, 0, lerp(lerp(1.7, 2.1, a), 3.0, b)))
    look = c + Vector((0, 0, lerp(lerp(0.7, 1.3, a), 3.4, b)))
    cd = cam.data
    cd.type = 'PERSP'
    cd.sensor_fit = 'VERTICAL'
    cd.angle_y = math.radians(42)
    cd.clip_start, cd.clip_end = 0.1, 300
    cam.location = pos
    cam.rotation_euler = (look - pos).to_track_quat('-Z', 'Y').to_euler()


def main():
    out = sys.argv[sys.argv.index("--") + 1]
    os.makedirs(out, exist_ok=True)
    v = GV.GoroView(out, clips=("ArmorRise",), armor=True, res=(1280, 720))
    side = os.path.join(HERE, "..", "..", "..", "..", "Nindo", "Assets", "Nindo", "Art", "Characters", "TeamAnims", "GoroAnims.fbx.json")
    ev = json.load(open(side, encoding="utf-8"))["clips"]["ArmorRise"]["timing"]["events"]
    plans, cam_dir = plan(Vector((-3.2, -3.2, 0.0)), ev["kneel"] / FPS)
    lead = max(-p["launch"] for p in plans.values())
    print("piezas:", {n: (round(p["launch"], 2), round(p["flight"], 2), round((p["start"] - Vector((0, 0, 0))).length, 1)) for n, p in plans.items()})
    print(f"la primera sale {lead:.2f} s antes del clip")
    obj = v.armor["object"]
    obj.hide_render = False
    # los cuadros del clip exportado (GoroAnims.fbx.json): el plano se aleja desde 'kneel' hasta 'roar'
    kneel = 0.6 + lead + ev["kneel"] / FPS
    roar = 0.6 + lead + ev["roar"] / FPS
    tiles = []
    # las grandes (f112-f170: hombreras y cumbres) con más cuadros: el martillo clavado no puede taparlas
    for t in (0.2, 0.45, 0.65, 0.95, 1.15, 1.4, 1.65, 2.1, 2.45, 2.85, 3.2, 3.73, 4.27, 4.87, 5.4, 6.13):
        f = max(0, min(210, int(round(t * FPS))))
        v.set_frame("ArmorRise", f, moving=False)
        apply(v, plans, t, f)
        ts = 0.6 + lead + t        # el plano arranca con el retumbe: 0.6 s antes de la primera roca
        side_camera(v.rv.cam, cam_dir, ts, kneel, roar)
        v.rv.look.set_moon(Vector((0.4, -0.8, 0.6)), scale=1.0)
        p = os.path.join(out, f"_rise_{f:03d}.png")
        v.render(p, framed=False)
        tiles.append({"img": p, "label": f"t {t:+.2f} s (f{f})"})
    lay = {"out": os.path.join(out, "goro_ArmorRise_juego.png"), "title": "Gorō · ArmorRise como en el juego (plano de costado)",
           "width": 1280, "tile_h": 240, "rows": [{"label": "ArmorRise", "tiles": tiles}], "delete": True}
    pj = os.path.join(out, "_layout.json")
    json.dump(lay, open(pj, "w", encoding="utf-8"), indent=1)
    NA.compose_sheet(pj)


if __name__ == "__main__":
    main()
