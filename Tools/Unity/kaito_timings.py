"""Genera Scripts/Story/KaitoTimings.cs desde Animations teo/kaitooo.fbx.json (el sidecar del build de Kaito).

Las escenas de la historia (rezo en los santuarios, la muralla, la puerta de los sellos, el despertar del prólogo y
el final) disparan cosas en momentos de los clips de Kaito: el incienso aparece en la mano, la palma empuja la luz,
levanta la cabeza... Esos momentos son eventos del sidecar (los escribe build_kaito.py junto con el FBX). Antes
eran fracciones escritas a mano en cada escena para clips que todavía no existían: cuando llegaran, el incienso iba
a aparecer en una mano vacía. Este script copia los eventos de los clips del contrato a una tabla; cada escena
pregunta KaitoTimings.Event(estado, evento, respaldo) y, si el clip o el evento no está, usa su fracción de siempre.
Si se rehace un clip de Kaito, se corre este script y se recompila.

Eventos que leen las escenas (el contrato con kaito-anim):
  PrayIncense: incense_take, incense_light, incense_place, palms, rise   (StoryDirector.Shrines)
  PrayQuick:   palms                                                      (StoryDirector.Shrines)
  BandanaPower: release                                                   (StoryDirector.Wall / .SealGate)
  WakeUp:      sees   (levanta la cabeza y ve el secuestro)               (StoryDirector.Prologue)
  EndingTurn:  offer  (el brazo ya extendido con la media cinta)          (StoryDirector.Ending)

Uso: python Tools/Unity/kaito_timings.py
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


def main():
    clips = json.load(open(SRC, encoding="utf-8")).get("clips", {})
    rows = []
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
    main()
