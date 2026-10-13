"""Genera Scripts/Story/KaitoTimings.cs desde Animations teo/kaitooo.fbx.json (el sidecar del build de Kaito).

Las escenas de la historia (rezo en los santuarios, la muralla, la puerta de los sellos, el despertar del prólogo y
el final) disparan cosas en momentos de los clips de Kaito: el incienso aparece en la mano, la palma empuja la luz,
levanta la cabeza... Esos momentos son eventos del sidecar (los escribe build_kaito.py junto con el FBX). Antes
eran fracciones escritas a mano en cada escena para clips que todavía no existían: cuando llegaran, el incienso iba
a aparecer en una mano vacía. Este script copia los eventos de los clips del contrato a una tabla; cada escena
pregunta KaitoTimings.Event(estado, evento, respaldo) y, si el clip o el evento no está, usa su fracción de siempre.
Si se rehace un clip de Kaito, se corre este script y se recompila (generate_assets.py kaito_assets también lo corre).
Las fracciones de respaldo de cada escena son las del clip entregado por kaito-anim (para que una fusión sin
regenerar no dispare nada a destiempo).

Eventos que leen las escenas (el contrato con kaito-anim):
  PrayIncense: incense_take, incense_light, incense_place, palms, rise   (StoryDirector.Shrines)
  PrayQuick:   kneel, palms                                               (StoryDirector.Shrines)
  BandanaPower: glow, release                                             (StoryDirector.Wall / .SealGate)
  WakeUp:      see (levanta la cabeza y ve el secuestro), stand           (StoryDirector.Prologue)
  EndingTurn:  ribbon (el puño toma la cinta del cinturón), offer (el brazo ya extendido con ella)
               (StoryDirector.Ending), y EndingTurnShift: cuánto más cerca de Kokuyō termina que donde arranca (timing.shift_m)
Es el único generador de esta tabla (build_kaito.py lo llama al exportar).

Uso: python Tools/Unity/kaito_timings.py [--src otro/kaitooo.fbx.json]
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unity_yaml as U

SRC = os.path.join(U.ASSETS, "Animations teo", "kaitooo.fbx.json")
DST = os.path.join(U.ASSETS, "Nindo", "Scripts", "Story", "KaitoTimings.cs")
# solo los clips que usan las escenas: el resto de los eventos (pasos, golpes) los lee el combate a su manera
STATES = ("PrayIncense", "PrayQuick", "BandanaPower", "WakeUp", "EndingTurn")


def f(x):
    s = ("%.4f" % float(x)).rstrip("0")
    if s.endswith("."):
        s += "0"
    return s + "f"


def lst(xs):
    xs = list(xs)
    return "{ " + ", ".join(xs) + " }" if xs else "{ }"


def main(src=SRC):
    if not os.path.exists(src):
        print("sin", os.path.relpath(src, U.REPO), "- KaitoTimings.cs queda como está")
        return
    clips = json.load(open(src, encoding="utf-8")).get("clips", {})
    rows = []
    # el clip arranca 'shift_m' detrás del transform y termina en él: el transform va primero ahí (StoryDirector.OfferRibbon)
    shift = float(clips.get("EndingTurn", {}).get("timing", {}).get("shift_m", 0.55))
    for st in STATES:
        c = clips.get(st)
        if not c:
            continue
        for e in c.get("events", []):
            t = float(e["t"])
            if 0.0 <= t <= 1.0:
                rows.append((st, e["fn"], t))
    out = []
    w = out.append
    w("// Generado por Tools/Unity/kaito_timings.py desde Animations teo/kaitooo.fbx.json: no editar a mano.")
    w("namespace Nindo")
    w("{")
    w("    /// <summary>")
    w("    /// Momentos (normalizados 0..1) de los clips de Kaito que usan las escenas de la historia, copiados de los eventos")
    w("    /// del sidecar. Clips del contrato presentes: %s." % (", ".join(sorted({r[0] for r in rows})) or "ninguno todavía"))
    w("    /// </summary>")
    w("    public static class KaitoTimings")
    w("    {")
    w("        static readonly string[] states = %s;" % lst('"%s"' % r[0] for r in rows))
    w("        static readonly string[] names = %s;" % lst('"%s"' % r[1] for r in rows))
    w("        static readonly float[] times = %s;" % lst(f(r[2]) for r in rows))
    w("")
    w("        /// <summary>EndingTurn arranca con el cuerpo este tanto (m) detrás del transform y termina parado en él.</summary>")
    w("        public const float EndingTurnShift = %s;" % f(shift))
    w("")
    w("        /// <summary>El primer evento 'name' del clip 'state' o, si el clip no lo trae, 'fallback'.</summary>")
    w("        public static float Event(string state, string name, float fallback)")
    w("        {")
    w("            for (int i = 0; i < states.Length; i++) if (states[i] == state && names[i] == name) return times[i];")
    w("            return fallback;")
    w("        }")
    w("    }")
    w("}")
    U.write(DST, "\n".join(out) + "\n")
    U.write_meta(DST, U.MONO_META)
    print("escrito", os.path.relpath(DST, U.REPO), "-", len(rows), "eventos")


if __name__ == "__main__":
    # --src: el sidecar de otra rama (p. ej. la de kaito-anim antes de fusionar), para no esperar al merge
    main(os.path.abspath(sys.argv[sys.argv.index("--src") + 1]) if "--src" in sys.argv else SRC)
