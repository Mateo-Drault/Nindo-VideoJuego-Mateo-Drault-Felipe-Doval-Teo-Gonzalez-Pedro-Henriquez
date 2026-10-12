"""Chequeo de lo EXPORTADO (TeamAnims/GrandpaAnims.fbx con su sidecar), como lo ve Unity: cada curva es el
transform local absoluto de su nodo, así que se mide la armadura del propio FBX de animación (en Blender, pasarle la
acción a la armadura del modelo la aplicaría relativa a otro reposo: el del ninja del modelo no es el del FBX).

  blender -b --factory-startup --python Tools/Blender/anim/grandpa_fbx_check.py

Mide, en metros del juego:
  * los empalmes que el código hace en seco o con un fundido corto (NPC): Kidnap fin -> Dragged f0 (en seco),
    Dragged fin -> f0 (loop), Bound f0 -> Freed f0, Freed fin -> Idle f0 (cada hueso, en grados, y el peor punto);
  * el agarre en Kidnap (desde que se agarran) y Dragged: la palma de cada uno sobre el antebrazo del otro (cm);
  * que el Root de cada esqueleto no tenga curvas de escala ni salga del lugar (el bug de los enemigos invisibles).
Sale con código 1 si algo pasa de los topes.
"""
import bpy, sys, os, json, math
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
A = os.path.join(REPO, "Nindo", "Assets")
MODEL = os.path.join(A, "Nindo", "Art", "Models", "Characters", "Grandpa.fbx")
ANIM = os.path.join(A, "Nindo", "Art", "Characters", "TeamAnims", "GrandpaAnims.fbx")


def load(path):
    before = set(bpy.data.objects)
    acts0 = set(bpy.data.actions)
    # anim_offset 0: el importador de Blender corre la toma un cuadro (por omisión 1); Unity lee el cuadro del FBX
    bpy.ops.import_scene.fbx(filepath=path, anim_offset=0.0)
    new = [o for o in bpy.data.objects if o not in before]
    arm = next(o for o in new if o.type == 'ARMATURE')
    acts = [a for a in bpy.data.actions if a not in acts0]
    return arm, acts


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    side = json.load(open(ANIM + ".json", encoding="utf-8"))
    model, acts = load(ANIM)
    act = acts[0]
    moving = lambda fc: max(k.co[1] for k in fc.keyframe_points) - min(k.co[1] for k in fc.keyframe_points) > 1e-4
    bad = [fc.data_path for fc in act.fcurves if not fc.data_path.startswith("pose.bones") and moving(fc)]
    scale = [fc.data_path for fc in act.fcurves if fc.data_path.endswith(".scale") and any(abs(k.co[1] - 1.0) > 1e-3 for k in fc.keyframe_points)]
    scn = bpy.context.scene
    M = model.matrix_world
    pb = model.pose.bones

    def snap(f):
        scn.frame_set(f)
        bpy.context.view_layer.update()
        return {b.name: (M @ b.head.copy(), (M.to_quaternion() @ b.matrix.to_quaternion())) for b in pb}

    def compare(a, b):
        worst_d, worst_a, wa = 0.0, 0.0, ""
        for n in a:
            d = (a[n][0] - b[n][0]).length / U
            ang = math.degrees(a[n][1].rotation_difference(b[n][1]).angle)
            ang = min(ang, 360.0 - ang)
            worst_d = max(worst_d, d)
            if ang > worst_a:
                worst_a, wa = ang, n
        return worst_d * 100.0, worst_a, wa

    c = side["clips"]
    fails = []
    # unidades: lo que sube la cadera de Idle f0 sobre la suela (0.455 m en el marco de autoría)
    global U
    s0 = snap(c["Idle"]["first"])
    U = (s0["Root"][0].z - min(s0["Pie.L"][0].z, s0["Pie.R"][0].z)) / (0.455 - 0.102)
    print(f"unidades por metro {U:.3f} (sidecar {side['units_per_meter']})")
    joins = [("Kidnap fin -> Dragged f0", c["Kidnap"]["last"], c["Dragged"]["first"], 1.0, 2.0),
             ("Dragged fin -> f0 (loop)", c["Dragged"]["last"], c["Dragged"]["first"], 1.0, 2.0),
             ("Bound fin -> f0 (loop)", c["Bound"]["last"], c["Bound"]["first"], 1.0, 2.0),
             ("Bound f0 -> Freed f0", c["Bound"]["first"], c["Freed"]["first"], 1.0, 2.0),
             ("Freed fin -> Idle f0", c["Freed"]["last"], c["Idle"]["first"], 2.0, 3.0)]
    for name, fa, fb, tol_cm, tol_deg in joins:
        d, ang, n = compare(snap(fa), snap(fb))
        ok = d <= tol_cm and ang <= tol_deg
        print(f"{'ok  ' if ok else 'FAIL'} {name}: peor punto {d:.2f} cm, peor giro {ang:.2f}° ({n})")
        if not ok:
            fails.append(name)
    # agarre: el centro de la palma de cada mano izquierda (la cabeza de la mano y las de los dedos) contra el antebrazo
    # del otro (de su muñeca a su codo). Las dos manos se cruzan sobre la muñeca del otro: cerca de 3 cm del eje
    def palm(s, suf):
        pts = [s["Mano.R" + suf][0]] + [s[f"Dedo{i}.R" + suf][0] for i in (1, 2, 3)]
        return sum(pts, Vector()) / len(pts)

    def to_forearm(p, s, suf):
        w, e = s["Mano.R" + suf][0], s["Antebrazo.R" + suf][0]
        ax = (e - w).normalized()
        t = max(0.0, min((e - w).length, (p - w).dot(ax)))
        return (p - (w + ax * t)).length / U * 100.0, t / U * 100.0

    grip = []
    for clip, f0 in (("Kidnap", 30), ("Dragged", 0)):
        r = c[clip]
        for f in range(r["first"] + f0, r["last"] + 1):
            s = snap(f)
            dg, tg = to_forearm(palm(s, ""), s, ".001")
            dn, tn = to_forearm(palm(s, ".001"), s, "")
            grip.append((max(dg, dn), clip, f - r["first"], round(dg, 1), round(tg, 1), round(dn, 1), round(tn, 1)))
    gw = max(grip)
    ok = gw[0] <= 4.5
    print(f"{'ok  ' if ok else 'FAIL'} cada palma sobre el antebrazo del otro: peor {gw[0]:.1f} cm ({gw[1]} f{gw[2]}: abuelo {gw[3]} cm a "
          f"{gw[4]} cm de la muñeca del ninja, ninja {gw[5]} cm a {gw[6]} cm de la del abuelo), media {sum(g[0] for g in grip) / len(grip):.1f} cm")
    if not ok:
        fails.append("agarre")
    ok = not bad and not scale
    print(f"{'ok  ' if ok else 'FAIL'} curvas solo de huesos y sin escala ({bad[:3]} {scale[:3]})")
    if not ok:
        fails.append("curvas")
    print("FALLAS", fails)
    sys.exit(1 if fails else 0)


main()
