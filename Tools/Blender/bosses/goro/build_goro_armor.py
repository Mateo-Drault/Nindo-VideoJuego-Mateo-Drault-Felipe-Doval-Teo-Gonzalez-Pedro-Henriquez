"""La armadura de roca de Gorō: kit, sidecar con el contrato de la cinemática y renders (Blender 4.4, -b).

  blender -b --factory-startup --python Tools/Blender/bosses/goro/build_goro_armor.py -- [--export]

--export   escribe Nindo/Assets/Nindo/Art/Characters/Kits/Kit_goro_armor.fbx (el esqueleto de Models/Minijefe.fbx, los
           huesos Acc_Roca_* y la malla 'Acc_Kit' con skin rígido) y Kit_goro_armor.fbx.json (piezas, huesos, orden,
           vuelo). El .meta lo escribe Tools/Unity/generate_assets.py (kit_metas: importa con la escala del modelo, x2).
Los renders de la armadura puesta (y de la cinemática) los hace goro_review.py.

Es un kit como los de Tools/Blender/characters/kits (CharacterKits.Attach cuelga los huesos Acc_* de los vivos con el
mismo local y re-apunta el skin), con un hueso por pieza para que la cinemática las pueda mover de a una. El FBX se
valida contra el modelo: los nodos que no son de la armadura tienen que existir con el mismo padre y el nodo de la
armadura con el mismo transform (si no, el kit no encaja en el esqueleto vivo).
"""
import bpy, os, sys, json

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import goro_view as GV           # noqa: E402  (rutas)
import goro_armor as GA          # noqa: E402
import goro_review as GR         # noqa: E402
import kitlib as K               # noqa: E402
import team_rig as T             # noqa: E402

OUT = os.path.join(K.KITS_DIR, "Kit_" + GA.KIT_ID + ".fbx")


def unity(v):
    """Marco de autoría (frente -Y, izquierda +X, arriba +Z) -> local del transform de Gorō en Unity (frente +Z,
    derecha +X, arriba +Y), en metros del juego."""
    return [round(-v[0], 4), round(v[2], 4), round(-v[1], 4)]


def verify(path, model):
    import fbxcheck as FC
    a, m = FC.summary(path), FC.summary(model)
    bad = []
    extra = [n for n in a["models"] if n not in m["models"] and not n.startswith("Acc_")]
    if extra:
        bad.append(f"nodos que el modelo no tiene: {extra[:5]}")
    wrong = [n for n in a["models"] if n in m["models"] and a["parents"].get(n) != m["parents"].get(n)]
    if wrong:
        bad.append(f"padres distintos del modelo: {wrong[:5]}")
    ra, ta, sa = a["local"]["Armature"]
    rm, tm, sm = m["local"]["Armature"]
    d = FC._rot3_angle(ra, rm), max(abs(x - y) for x, y in zip(ta, tm)), max(abs(x - y) for x, y in zip(sa, sm))
    if d[0] > 0.01 or d[1] > 1e-4 or d[2] > 1e-5:
        bad.append(f"nodo Armature distinto del modelo {d}")
    rocks = [n for n in a["models"] if n.startswith(GA.BONE_PREFIX)]
    if len(rocks) != len(GA.PIECES):
        bad.append(f"{len(rocks)} huesos de roca, se esperaban {len(GA.PIECES)}")
    return bad


def sidecar(armor, obj, ch):
    tris = sum(len(p.vertices) - 2 for p in obj.data.polygons)
    pieces = []
    for i, p in enumerate(GA.PIECES):
        c = armor["pieces"][p["name"]]["center"]
        pts = armor["pieces"][p["name"]]["points"]
        size = [round(max(q[k] for q in pts) - min(q[k] for q in pts), 3) for k in range(3)]
        axis = GR.spin_axis(p["name"])
        pieces.append(dict(
            name=p["name"], bone=GA.BONE_PREFIX + p["name"], parent=p["bone"], order=i,
            slam_frame=p["slam"], slam_s=round(p["slam"] / GR.FPS, 4), flight_s=p["flight"],
            launch_s=round(p["slam"] / GR.FPS - p["flight"], 4),
            start_unity=unity(p["start"]), start_authoring=list(p["start"]), arc_m=p["arc"], spin_deg=p["spin"],
            spin_axis_unity=unity(axis), spin_axis_authoring=list(axis),
            center_unity=unity(c), center_authoring=[round(x, 4) for x in c], size_authoring_m=size))
    return {
        "kit": GA.KIT_ID, "fbx": "Kit_" + GA.KIT_ID + ".fbx", "character": "goro", "model": ch.spec["fbx"],
        "tris": tris, "bones": [GA.BONE_PREFIX + p["name"] for p in GA.PIECES],
        "materials": {"Nindo_Palette": "granito (rock, rock_dark, rock_light, rock_brown) y nieve (snow, snow_shade) por UV",
                      "Nindo_Emissive": GA.EMBER + " (las vetas de brasa entre las rocas de cada pieza)"},
        "frames": "start_unity / center_unity / spin_axis_unity: metros en el espacio local del transform de Gorō (el que "
                  "tiene Enemy: +Z adelante, +X derecha, +Y arriba). *_authoring: el marco de autoría de team_rig "
                  "(frente -Y, izquierda +X, arriba +Z).",
        "contract": [
            "Vestir: CharacterKits.Attach(model, 'goro_armor') cuelga cada hueso Acc_Roca_<Pieza> del hueso vivo 'parent' "
            "con el mismo transform local y re-apunta el skin (una sola malla, 1 draw call). Para mover las piezas de a una "
            "hay que encontrar los huesos por nombre ANTES de Attach (Attach renombra la malla a 'Acc_Kit_goro_armor').",
            "Fase 1: la armadura no se ve (renderer apagado o cada hueso de roca con escala 0). Fase 2: todas puestas.",
            "Cinemática (estado ArmorRise de GoroAnims, 7 s, arranca en la pose final de FakeDefeat): cada pieza sale a "
            "launch_s = slam_s - flight_s desde start_unity (enterrada 0.3 m: se arranca del piso con polvo) y llega "
            "pegada justo en slam_s, el cuadro 'slam_<Pieza>' de los eventos del clip (polvo, sacudón, sonido de roca).",
            "Vuelo: u = (t - launch_s) / flight_s; posición = lerp(salida_mundo, pegada_mundo(t), u*u) + Vector3.up * arc_m * "
            "4u(1-u); giro = pegada_mundo(t).rotation * AngleAxis(spin_deg * (1-u)^2, spin_axis_unity). salida_mundo = "
            "transform.TransformPoint(start_unity) al empezar el clip; pegada_mundo(t) = el hueso de la pieza colgado del vivo "
            "en ese cuadro (el cuerpo se mueve: el destino se recalcula cada cuadro). Antes de launch_s la pieza no se ve.",
            "Tools/Blender/bosses/goro/goro_review.py simula esta misma fórmula: las hojas de revisión muestran cómo se ve.",
            "Gorō no se mueve durante FakeDefeat ni ArmorRise (sin travel): conviene girarlo de perfil a la cámara del juego "
            "antes de la derrota falsa (boca arriba a lo largo de la vista no se lee) o usar un plano de costado.",
        ],
        "pieces": pieces,
    }


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    export = "--export" in argv
    ch = T.TeamChar("goro", T.CHARS["goro"])
    armor = GA.build_on(ch)
    obj = armor["object"]
    print("ARMADURA", GA.KIT_ID, sum(len(p.vertices) - 2 for p in obj.data.polygons), "tris,", len(obj.vertex_groups), "huesos")
    if export:
        size = K.export_kit(GA.kit_char(ch), obj, OUT)
        bad = verify(OUT, ch.src)
        if bad:
            os.remove(OUT)
            print("FBX BORRADO:", "; ".join(bad))
            sys.exit(1)
        with open(OUT + ".json", "w", encoding="utf-8", newline="\n") as fh:
            json.dump(sidecar(armor, obj, ch), fh, indent=1, ensure_ascii=False)
        print("ESCRITO", OUT, size)


if __name__ == "__main__":
    main()
