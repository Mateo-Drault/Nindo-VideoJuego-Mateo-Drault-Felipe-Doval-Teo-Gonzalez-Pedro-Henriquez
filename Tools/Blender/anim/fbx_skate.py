"""Pies que patinan medidos sobre el FBX EXPORTADO (re-importado sobre el modelo), con la interpolación de rotaciones
de las curvas entre cuadros y el reloj del juego (StepTimeline + la embestida en cuadros del clip de Enemy.Locomotion,
portados acá tal cual del C#).

  blender -b --factory-startup --python Tools/Blender/anim/fbx_skate.py -- <ninja|sumo|...> [--fbx PATH] [--only A,B] [--out JSON]

Por qué aparte de build_team_anims.replay_skate: aquel interpola las POSICIONES de los vértices entre cuadros enteros
con una cúbica que no se pasa, y así no ve lo que hace una pierna cuando la cadera gira mucho en un cuadro: entre f11 y
f12 del Whirl la rotación interpolada de cada hueso llevaba la suela apoyada 15 cm fuera de la cuerda que une los dos
cuadros (0.1 cm en replay_skate, 16 cm en el juego). Acá la malla se deforma con las curvas del FBX evaluadas en
subcuadros, como las muestrea Unity.

build_team_anims lo llama solo después de exportar (run(), en el mismo proceso de Blender). Falla si una suela que toca
el piso se corre más de MAX_DRIFT cm desde que apoyó, o más de MAX_STEP cm en una muestra de 1/120 s."""
import sys, os, math, json
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ASSETS = os.path.join(ROOT, "Nindo", "Assets")
for p in (HERE, os.path.join(ROOT, "Tools", "Blender")):
    if p not in sys.path:
        sys.path.insert(0, p)

import bpy
import numpy as np
from mathutils import Vector

HZ = 120.0          # muestras por segundo del juego (un frame a 120 fps: lo más fino que se ve)
THR = 0.01          # una suela "toca" a menos de 1 cm del piso
MAX_DRIFT, WARN_DRIFT, MAX_STEP = 3.0, 2.0, 2.0

# ---------------------------------------------------------------- port del C# (StepTimeline.cs, Enemy.Locomotion.cs)
MAX_HOLD, ANTIC_RATE, FOLLOW_TAU = 0.45, 0.85, 0.06
LUNGE_ACCEL, LUNGE_BRAKE, MAX_CLIP_LUNGE = 0.2, 0.2, 16.0


class Timeline:
    """StepTimeline.Build / NormAt / TimeAt."""

    def __init__(s, clip_len, speed, apex, a_start, a_end, windup_min, release=1.6, creep_in=True):
        s.step = max(0.05, clip_len) / max(0.05, speed)
        s.a0 = min(max(a_start, 0.02), 1.0)
        s.a1 = max(s.a0, a_end)
        s.apex = min(max(apex, 0.0), s.a0 - 0.02)
        s.tA = s.apex * s.step / ANTIC_RATE
        s.tR = (s.a0 - s.apex) * s.step / release
        extra = max(0.0, windup_min - (s.tA + s.tR))
        s.hold = min(extra, MAX_HOLD)
        s.tA += extra - s.hold
        s.T = s.tA + s.hold + s.tR
        s.creep = min(0.01, (s.a0 - s.apex) * 0.25) if s.hold > 0 else 0.0
        # creepIn: todo lo que mide este lint son golpes con lungeFrom (o saltos), que derivan hasta el apex
        s.h0 = s.apex - s.creep if creep_in else s.apex

    def _r0(s):
        return max(1.0, 2.0 * (s.a0 - s.h0 - s.creep) / s.tR * s.step)

    def norm(s, t):
        if t <= 0:
            return 0.0
        if t < s.tA:
            return s.h0 * math.sin(t / s.tA * math.pi * 0.5)
        t -= s.tA
        if t < s.hold:
            return s.h0 + s.creep * t / s.hold
        t -= s.hold
        frm = s.h0 + s.creep
        if t < s.tR:
            u = t / s.tR
            return frm + (s.a0 - frm) * u * u
        t -= s.tR
        r0 = s._r0()
        return s.a0 + (t + (r0 - 1) * FOLLOW_TAU * (1 - math.exp(-t / FOLLOW_TAU))) / s.step

    def time_at(s, n):
        if n <= 0:
            return 0.0
        if n < s.h0:
            return s.tA * math.asin(min(1.0, max(0.0, n / s.h0))) * 2 / math.pi
        frm = s.h0 + s.creep
        if n < frm:
            return s.tA + (s.hold * (n - s.h0) / s.creep if s.creep > 0 else 0.0)
        t0 = s.tA + s.hold
        if n < s.a0:
            return t0 + s.tR * math.sqrt((n - frm) / max(1e-5, s.a0 - frm))
        t0 += s.tR
        r0 = s._r0()
        target = (n - s.a0) * s.step
        x = target / r0
        for _ in range(6):
            e = math.exp(-x / FOLLOW_TAU)
            x -= (x + (r0 - 1) * FOLLOW_TAU * (1 - e) - target) / (1 + (r0 - 1) * e)
        return t0 + max(0.0, x)


def _peak(brake):
    return 1.0 / (1.0 - 0.5 * LUNGE_ACCEL - 0.5 * brake)


def _tangent(a, b, c):
    d0, d1 = b - a, c - b
    if d0 * d1 <= 0:
        return 0.0
    lim = 3 * min(abs(d0), abs(d1))
    return max(-lim, min(lim, 0.5 * (d0 + d1)))


class Lunge:
    """Enemy.SetupLunge / ProfileLunge / Knot / LungeAt (la embestida en cuadros del clip). 'decided': el largo que decide
    un salto al despegar con Kaito cerca (TickLunge; None = el autorado)."""

    def __init__(s, tl, frames, length, frm, air, hop_end=None, decided=None):
        s.tl, s.N, s.len = tl, frames, length
        s.brake = 0.0 if air else LUNGE_BRAKE
        s.start = tl.time_at(frm)
        s.end = (tl.time_at(hop_end) if hop_end is not None
                 else max(tl.T + 0.05 * tl.step, s.start + length * _peak(s.brake) / MAX_CLIP_LUNGE))
        s.decided = length if decided is None else decided
        s.keep = min(frames, int(round(frm * frames)) + 1)
        s.keep_at = s.profile(tl.time_at(s.keep / frames))

    def profile(s, t):
        u = min(1.0, max(0.0, (t - s.start) / max(0.01, s.end - s.start)))
        A, B = LUNGE_ACCEL, s.brake
        if u < A:
            g = u * u / (2 * A)
        elif u <= 1 - B:
            g = u - 0.5 * A
        else:
            g = 1 - 0.5 * A - 0.5 * B - (1 - u) ** 2 / (2 * max(1e-4, B))
        return s.len * g * _peak(B)

    def knot(s, k):
        full = s.profile(s.tl.time_at(min(max(k, 0), s.N) / s.N))
        if s.decided >= s.len:
            return full
        if s.keep_at >= s.decided:
            return full * s.decided / s.len
        if k <= s.keep:
            return full
        return s.keep_at + (full - s.keep_at) * (s.decided - s.keep_at) / max(1e-4, s.len - s.keep_at)

    def at(s, clock):
        f = min(1.0, max(0.0, s.tl.norm(clock))) * s.N
        k = min(int(f), s.N - 1)
        p0, a, b, p3 = s.knot(k - 1), s.knot(k), s.knot(k + 1), s.knot(k + 2)
        ma, mb = _tangent(p0, a, b), _tangent(a, b, p3)
        x = f - k
        return (2 * x ** 3 - 3 * x ** 2 + 1) * a + (x ** 3 - 2 * x ** 2 + x) * ma + (-2 * x ** 3 + 3 * x ** 2) * b + (x ** 3 - x ** 2) * mb


# ---------------------------------------------------------------- escena: modelo + FBX de animación
def _import(path):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.fbx(filepath=path, anim_offset=0.0)
    return [o for o in bpy.data.objects if o not in before]


def _mesh_world(o, dg):
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get("co", co)
    oe.to_mesh_clear()
    M = np.array(oe.matrix_world)
    return co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


class Scene:
    """El modelo del juego con cada hueso copiando al del esqueleto del FBX de animación (Unity reproduce las curvas
    locales sobre la misma jerarquía) y la raíz del FBX colgada de un vacío que hace de transform del enemigo."""

    def __init__(s, char, fbx):
        import team_rig as T
        spec = T.CHARS[char]
        s.side = json.load(open(fbx + ".json", encoding="utf-8"))
        s.U = s.side["units_per_meter"]
        bpy.ops.wm.read_factory_settings(use_empty=True)
        s.scn = bpy.context.scene
        s.scn.render.fps = 30
        mobjs = _import(os.path.join(ASSETS, s.side["model"]))
        marm = next(o for o in mobjs if o.type == 'ARMATURE')
        if marm.animation_data:
            marm.animation_data.action = None
        aobjs = _import(fbx)
        aarm = next(o for o in aobjs if o.type == 'ARMATURE')
        for o in aobjs:
            if o.type == 'MESH':
                o.hide_viewport = o.hide_render = True
        s.rig = bpy.data.objects.new("TransformDelJuego", None)
        s.scn.collection.objects.link(s.rig)
        aarm.parent = s.rig
        for pb in marm.pose.bones:
            if pb.name in aarm.pose.bones:
                c = pb.constraints.new('COPY_TRANSFORMS')
                c.target, c.subtarget = aarm, pb.name
        # suelas: vértices que pesan más de 0.9 en el pie (o su control); con 0.3 entraban los de la tibia, que se
        # estiran con la piel y marcaban patinadas que no son
        s.feet = {}
        for k, tag in (("r", spec["right_tag"]), ("l", spec["left_tag"])):
            names = {spec["foot"].format(tag)} | ({spec["foot_ctrl"].format(tag)} if spec.get("foot_ctrl") else set())
            for o in mobjs:
                if o.type != 'MESH':
                    continue
                gi = {g.index for g in o.vertex_groups if g.name in names}
                idx = [v.index for v in o.data.vertices if sum(g.weight for g in v.groups if g.group in gi) > 0.9]
                if idx:
                    s.feet.setdefault(k, []).append((o, np.array(idx)))
        s.fwd = np.array(spec["fwd"], dtype=np.float64)
        s.left = np.cross([0.0, 0.0, 1.0], s.fwd)
        meshes = [o for o in mobjs if o.type == 'MESH']
        mods = [(m, m.show_viewport) for o in meshes for m in o.modifiers]
        for m, _ in mods:
            m.show_viewport = False
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        s.floor = min(float((_mesh_world(o, dg) / s.U)[:, 2].min()) for o in meshes)
        for m, v in mods:
            m.show_viewport = v

    def world_dir(s, td):
        """Dirección del marco de autoría (frente -Y, +X a su izquierda) en el mundo de Blender."""
        return td[0] * s.left - td[1] * s.fwd

    def soles(s, frame_f, offset):
        f = int(math.floor(frame_f))
        s.scn.frame_set(f, subframe=frame_f - f)
        s.rig.location = Vector(offset) * s.U
        bpy.context.view_layer.update()
        dg = bpy.context.evaluated_depsgraph_get()
        out = {}
        for k, lst in s.feet.items():
            out[k] = np.concatenate([(_mesh_world(o, dg) / s.U)[idx] for o, idx in lst])
        return out


def track(sc, samples):
    """samples: (t, cuadro de la escena fraccionario, desplazamiento del transform en m). Por pie y por tirada de apoyo:
    lo que se corrió desde que apoyó (drift: de los vértices que tocan desde el principio, el que menos) y el peor paso
    entre dos muestras (de los que tocan en las dos, el que menos: una suela que rueda tiene uno quieto)."""
    prev, cur, start, runs = {}, {}, {}, []
    for t, fl, off in samples:
        S = sc.soles(fl, off)
        for k, P in S.items():
            on = P[:, 2] - sc.floor < THR
            if k in prev:
                pP, pon = prev[k]
                both = on & pon
                if both.any():
                    d = float(np.min(np.linalg.norm((P[both] - pP[both])[:, :2], axis=1))) * 100
                    if cur.get(k) is None:
                        cur[k] = {"pie": k, "f0": round(fl, 2), "t0": round(t, 3), "max": 0.0, "drift": 0.0}
                        start[k] = (pP.copy(), pon.copy())
                    r = cur[k]
                    r["max"] = max(r["max"], d)
                    r["f1"] = round(fl, 2)
                    sP, son = start[k]
                    keep = son & on
                    if keep.any():
                        r["drift"] = max(r["drift"], float(np.min(np.linalg.norm((P[keep] - sP[keep])[:, :2], axis=1))) * 100)
                elif cur.get(k) is not None:
                    runs.append(cur.pop(k))
            prev[k] = (P, on)
    runs += [r for r in cur.values() if r is not None]
    for r in runs:
        r["max"], r["drift"] = round(r["max"], 2), round(r["drift"], 2)
    return runs


def cases(clip, hits=()):
    """Las variantes del reloj del juego que cambian dónde cae cada subcuadro: el windup del clip y uno más largo (una
    pausa del director en el apex), en el aire el salto decidido corto (Enemy: 35% como mínimo) y cada Hit de
    EnemyArchetypes que usa el clip con otra velocidad o embestida (build_team_anims.archetype_hits). [(nombre, caso,
    grave)]: un Hit con otra embestida que la autorada es el respaldo de otro clip (el Whirl cae al Attack2 si el
    controller no lo tiene) y solo avisa."""
    t, n = clip["timing"], clip["frames"]
    w = t.get("windup", 0.55)
    if "hop" in t:
        h = t["hop"]
        base = dict(apex=h["apex"] / n, a0=h["takeoff"] / n, a1=h["land"] / n, frm=h["takeoff"] / n, air=False,
                    hop_end=h["land"] / n, length=t["lunge"])
    else:
        base = dict(apex=t["apex"] / n, a0=t["contact"] / n, a1=t["active"][1] / n, frm=t["lunge_from"] / n,
                    air=bool(t.get("lunge_air")), hop_end=None, length=t["lunge"])
    out = [("clip", dict(base, windup=w, speed=1.0), True), ("pausa", dict(base, windup=w + 0.35, speed=1.0), True)]
    if base["air"]:
        out.append(("corto", dict(base, windup=w, speed=1.0, decided=base["length"] * 0.35), True))
    for a0, a1, apex, fn, hl, hs, frm, air in hits:
        if frm is None or hl <= 0.0 or (abs(hs - 1.0) < 1e-3 and abs(hl - base["length"]) < 1e-3):
            continue
        out.append((f"{fn} {hl:g} m x{hs:g}", dict(base, windup=w, speed=hs, length=hl), abs(hl - base["length"]) < 1e-3))
    return out


def measure(sc, name, clip, c):
    n = clip["frames"]
    tl = Timeline(n / 30.0, c["speed"], c["apex"], c["a0"], c["a1"], c["windup"])
    L = Lunge(tl, n, c["length"], c["frm"], c["air"], c["hop_end"], c.get("decided"))
    d = sc.world_dir(clip["timing"].get("travel_dir", (0.0, -1.0)))
    samples, t = [], 0.0
    while True:
        nt = min(1.0, tl.norm(t))
        samples.append((t, clip["first"] + nt * n, d * L.at(t)))
        if nt >= 1.0:
            break
        t += 1.0 / HZ
    return track(sc, samples)


def run(char, fbx, only=None, out=None, hits=None):
    """Devuelve (fallas, avisos, resultados por clip). 'hits': {estado: [Hit de EnemyArchetypes]} de
    build_team_anims.archetype_hits (sin eso, solo los casos del clip). Deja la escena con el modelo y el FBX importados."""
    sc = Scene(char, fbx)
    fails, warns, res = [], [], {}
    for name, clip in sc.side["clips"].items():
        t = clip["timing"]
        if only and name not in only:
            continue
        if not t.get("lunge") or not ("hop" in t or "lunge_from" in t):
            continue
        res[name] = {}
        for tag, c, grave in cases(clip, (hits or {}).get(t.get("state", name), ())):
            runs = measure(sc, name, clip, c)
            worst = max(runs, key=lambda r: (r["drift"], r["max"]), default=None)
            res[name][tag] = {"drift_cm": worst["drift"] if worst else 0.0, "max_step_cm": max([r["max"] for r in runs] or [0.0]),
                              "runs": [r for r in runs if r["drift"] > 1.0 or r["max"] > 1.0]}
            dr, mx = res[name][tag]["drift_cm"], res[name][tag]["max_step_cm"]
            where = f"pie {worst['pie']} cuadros {worst['f0'] - clip['first']:.2f}-{worst['f1'] - clip['first']:.2f}" if worst else ""
            msg = f"{name} [{tag}]: suela apoyada en el FBX se corre {dr:.1f} cm, peor muestra {mx:.1f} cm ({where})"
            if (dr > MAX_DRIFT or mx > MAX_STEP) and grave:
                fails.append(msg)
                print("FALLA", msg)
            elif dr > WARN_DRIFT or mx > MAX_STEP:
                warns.append(msg)
                print("AVISO", msg)
            else:
                print("  ok ", msg)
    if out:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=1)
    return fails, warns, res


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    char = argv[0]
    opt = lambda k: argv[argv.index(k) + 1] if k in argv else None
    fbx = opt("--fbx") or os.path.join(ASSETS, "Nindo", "Art", "Characters", "TeamAnims", char.capitalize() + "Anims.fbx")
    only = opt("--only")
    fails, warns, _ = run(char, fbx, only.split(",") if only else None, opt("--out"))
    print(f"fbx_skate {char}: {len(fails)} fallas, {len(warns)} avisos")
    sys.exit(1 if fails else 0)
