"""Chequeo de lo EXPORTADO (TeamAnims/GrandpaAnims.fbx con su sidecar), como lo ve Unity: cada curva es el
transform local absoluto de su nodo, así que se mide la armadura del propio FBX de animación (en Blender, pasarle la
acción a la armadura del modelo la aplicaría relativa a otro reposo: el del ninja del modelo no es el del FBX).

  blender -b --factory-startup --python Tools/Blender/anim/grandpa_fbx_check.py [-- OTRO.fbx]

Mide, en metros del juego:
  * los empalmes que el código hace en seco o con un fundido corto (NPC): KidnapWait (loop y hacia Kidnap f0), Kidnap
    fin -> Dragged f0 (en seco), Dragged (loop), Bound (loop, hacia y desde BoundStruggle, hacia Freed), Freed fin ->
    Idle f0 (cada hueso que pesa en la malla, en grados, y el peor punto);
  * el agarre en Kidnap (desde que se agarran) y Dragged: la palma de cada uno sobre el antebrazo del otro (cm), los
    dedos del abuelo cerrados y los dos brazos tirantes (el codo, salvo cuando el abuelo resiste y encoge el suyo);
  * la mano derecha del ninja sobre el antebrazo del abuelo en el tirón a dos manos;
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
if "--" in sys.argv and len(sys.argv) > sys.argv.index("--") + 1:
    ANIM = sys.argv[sys.argv.index("--") + 1]


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
    # los huesos que mueven vértices del modelo (los controles de IK y las puntas de los dedos que quedaron en el FBX no)
    load(MODEL)
    weighted = set()
    for o in bpy.data.objects:
        if o.type == 'MESH':
            used = {g.group for v in o.data.vertices for g in v.groups if g.weight > 0.01}
            weighted |= {vg.name for vg in o.vertex_groups if vg.index in used}
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
            if n not in weighted:
                continue
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
    joins = [("KidnapWait fin -> f0 (loop)", c["KidnapWait"]["last"], c["KidnapWait"]["first"], 1.0, 2.0),
             ("KidnapWait f0 -> Kidnap f0", c["KidnapWait"]["first"], c["Kidnap"]["first"], 1.0, 2.0),
             ("Kidnap fin -> Dragged f0", c["Kidnap"]["last"], c["Dragged"]["first"], 1.0, 2.0),
             ("Dragged fin -> f0 (loop)", c["Dragged"]["last"], c["Dragged"]["first"], 1.0, 2.0),
             ("Bound fin -> f0 (loop)", c["Bound"]["last"], c["Bound"]["first"], 1.0, 2.0),
             ("Bound f0 -> BoundStruggle f0", c["Bound"]["first"], c["BoundStruggle"]["first"], 1.0, 2.0),
             ("BoundStruggle fin -> Bound f0", c["BoundStruggle"]["last"], c["Bound"]["first"], 1.0, 2.0),
             ("Bound f0 -> Freed f0", c["Bound"]["first"], c["Freed"]["first"], 1.0, 2.0),
             ("Freed fin -> Idle f0", c["Freed"]["last"], c["Idle"]["first"], 2.0, 3.0)]
    # (el NPC 'kidnap' no entra a Kidnap desde Idle: espera en KidnapWait, NPC.AwaitKidnap; desde Idle el ninja de la
    # pose fija del FBX saltaba 21 cm en el fundido de 0.1 s)
    # KidnapWait -> Kidnap se funde en NPC.KidnapFade desde cualquier cuadro de la espera: lo más que se separa de f0
    w = c["KidnapWait"]
    d_wait = max(compare(snap(f), snap(w["first"]))[0] for f in range(w["first"], w["last"] + 1, 3))
    print(f"     KidnapWait: lo más lejos de su f0 (el fundido a Kidnap) {d_wait:.1f} cm")
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
    ok = gw[0] <= 4.0
    print(f"{'ok  ' if ok else 'FAIL'} cada palma sobre el antebrazo del otro: peor {gw[0]:.1f} cm ({gw[1]} f{gw[2]}: abuelo {gw[3]} cm a "
          f"{gw[4]} cm de la muñeca del ninja, ninja {gw[5]} cm a {gw[6]} cm de la del abuelo), media {sum(g[0] for g in grip) / len(grip):.1f} cm")
    if not ok:
        fails.append("agarre")
    # los brazos del agarre (codo: el ángulo de brazo a antebrazo; 180 = recto) y los dedos del abuelo alrededor de la
    # muñeca del ninja (el dedo del medio contra el eje de la mano). Dragged: tirantes salvo f14-f27, cuando el abuelo
    # resiste y encoge el suyo (RESIST_SHARE: ~100°)
    def elbow(s, suf):
        a, b, e = s["Brazo.R" + suf][0], s["Antebrazo.R" + suf][0], s["Mano.R" + suf][0]
        return math.degrees((a - b).angle(e - b))

    def axis(f, n):
        scn.frame_set(f)
        bpy.context.view_layer.update()
        return (M.to_3x3() @ pb[n].matrix.to_3x3()).col[1].normalized()
    r = c["Dragged"]
    rows = []
    for f in range(r["first"], r["last"]):
        s = snap(f)
        ff = f - r["first"]
        rows.append((ff, elbow(s, ""), elbow(s, ".001"), math.degrees(axis(f, "Mano.R").angle(axis(f, "Dedo2.R")))))
    resist = [x for x in rows if 14 <= x[0] <= 27]
    taut = [x for x in rows if not 12 <= x[0] <= 29]
    gmin, nmin = min(x[1] for x in taut), min(x[2] for x in rows)
    rmin = min(x[1] for x in resist)
    curl = min(x[3] for x in rows)
    ok = gmin >= 135.0 and nmin >= 140.0 and 85.0 <= rmin <= 120.0 and curl >= 55.0
    print(f"{'ok  ' if ok else 'FAIL'} brazos del agarre en Dragged: codo del abuelo >= {gmin:.0f}° (tirante; resistiendo baja a "
          f"{rmin:.0f}°), del ninja >= {nmin:.0f}°; dedos del abuelo cerrados >= {curl:.0f}°")
    print("     codo abuelo / ninja / dedos por cuadro:", " ".join(f"f{x[0]}:{x[1]:.0f}/{x[2]:.0f}/{x[3]:.0f}" for x in rows[::4]))
    if not ok:
        fails.append("brazos")
    # el tirón a dos manos: la palma derecha del ninja sobre el antebrazo del abuelo (f23-f32)
    two = []
    for ff in range(23, 33):
        s = snap(r["first"] + ff)
        pts = [s["Mano.L.001"][0]] + [s[f"Dedo{i}.L.001"][0] for i in (1, 2, 3)]
        pc = sum(pts, Vector()) / len(pts)
        two.append(to_forearm(pc, s, "")[0])
    ok = max(two) <= 6.0
    print(f"{'ok  ' if ok else 'FAIL'} la otra mano del ninja sobre el antebrazo del abuelo (f23-f32): peor {max(two):.1f} cm del eje")
    if not ok:
        fails.append("dos manos")
    ok = not bad and not scale
    print(f"{'ok  ' if ok else 'FAIL'} curvas solo de huesos y sin escala ({bad[:3]} {scale[:3]})")
    if not ok:
        fails.append("curvas")
    print("FALLAS", fails)
    sys.exit(1 if fails else 0)


main()
