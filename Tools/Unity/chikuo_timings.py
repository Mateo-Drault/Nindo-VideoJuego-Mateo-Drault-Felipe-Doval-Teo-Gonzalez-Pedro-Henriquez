"""Genera Scripts/Enemies/Bosses/ChikuoTimings.cs desde Art/Characters/BambooMaster/BambooMaster.fbx.json (el Chikuō
ermitaño de la fase C4).

El JSON lo escribe Tools/Blender/bosses/chikuo_v2/build_chikuo.py junto con el FBX: es la única fuente de los tiempos de
cada clip (aviso, golpe, ventana, carga, aire, los eventos del contrato: Load / Unload / DartSpawn / LeaveStalk /
GrabStalk / Perch / Hang / Land / Contact / Plant / Note / Stamp / AimFix, el avance que el código le aplica al transform,
el espacio de la raíz y dónde va la raíz al empalmar un clip de vuelo). Así el jefe nuevo no se despega de lo que se ve:
si se rehace un clip, se corre este script y se recompila.

Reemplaza a BambooMasterTimings.cs (el del Chikuō viejo, que sigue mientras el BambooMasterBoss viejo lo use: sus nombres
de estado ya no existen en el FBX nuevo).

Uso: python Tools/Unity/chikuo_timings.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unity_yaml as U

SRC = os.path.join(U.ASSETS, "Nindo", "Art", "Characters", "BambooMaster", "BambooMaster.fbx.json")
DST = os.path.join(U.ASSETS, "Nindo", "Scripts", "Enemies", "Bosses", "ChikuoTimings.cs")
KINDS = {"parry": 1, "dodge": 2, "projectile": 3}
SPACES = {"ground": 0, "perch": 1, "air": 2, "pole": 3}


def f(x):
    s = ("%.4f" % float(x)).rstrip("0")
    if s.endswith("."):
        s += "0"
    return s + "f"


def arr(xs):
    return "null" if not xs else "new[] { " + ", ".join(f(x) for x in xs) + " }"


def strs(xs):
    return "new string[0]" if not xs else "new[] { " + ", ".join('"%s"' % x for x in xs) + " }"


def span(nm, key):
    v = nm.get(key)
    return (v[0], v[1]) if v else (0.0, 0.0)


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    clips = {n: c for n, c in data["clips"].items() if n != "BindPose"}
    out = []
    w = out.append
    w("// Generado por Tools/Unity/chikuo_timings.py desde BambooMaster.fbx.json: no editar a mano.")
    w("using System.Collections.Generic;")
    w("using UnityEngine;")
    w("")
    w("namespace Nindo")
    w("{")
    w("    /// <summary>Tiempos de un clip del Chikuō ermitaño tal como los mide el build de Blender (normalizados 0..1 salvo")
    w("    /// que el nombre diga otra cosa).</summary>")
    w("    public sealed class ChikuoClip")
    w("    {")
    w("        public readonly string State;")
    w("        public readonly int Frames;")
    w("        public readonly float Seconds;")
    w("        public readonly bool Loop;")
    w("        /// <summary>0 = piso (la raíz en el transform), 1 = posado (la raíz en el PerchNode de la caña), 2 = vuelo (la")
    w("        /// raíz la lleva el código por el arco, los pies a su altura), 3 = en el piso con el bastón clavado.</summary>")
    w("        public readonly int Space;")
    w("        /// <summary>0 = no pega, 1 = dorado (parry), 2 = rojo (dash), 3 = dardo (el golpe lo hace el proyectil).</summary>")
    w("        public readonly int Kind;")
    w("        public readonly float Apex, Contact, ActiveStart, ActiveEnd, TellStart, TellEnd, LoadStart, LoadEnd, AirStart,")
    w("            AirEnd, OpenStart, OpenEnd;")
    w("        /// <summary>Radio del disco rojo (barrida, picadas: 0 = sin disco), dónde cae la marca del salto y el alcance")
    w("        /// del golpe medidos en metros.</summary>")
    w("        public readonly float RingM, MarkerM, ReachM;")
    w("        /// <summary>Metros por segundo a los que la locomoción no patina (0 = no es locomoción).</summary>")
    w("        public readonly float GroundSpeed;")
    w("        /// <summary>Slots de CharacterGlint que se encienden con el aviso.</summary>")
    w("        public readonly string[] Glow;")
    w("        /// <summary>Metros que avanzó el transform hacia su frente en cada cuadro (null = no se mueve).</summary>")
    w("        public readonly float[] Travel;")
    w("        /// <summary>Pose con la que empieza y con la que termina (PERCH, READY, HANG, AIR...) y los segundos del")
    w("        /// fundido que necesita el empalme (0 = empalma exacto).</summary>")
    w("        public readonly string ChainFrom, ChainTo;")
    w("        public readonly float FadeFrom, FadeTo;")
    w("        /// <summary>Dónde va la raíz del clip de vuelo que sigue respecto de la de este (espacio del modelo de Unity;")
    w("        /// Vector3.zero = no cambia de espacio).</summary>")
    w("        public readonly Vector3 RootOffset;")
    w("        readonly string[] eventNames;")
    w("        readonly float[] eventTimes;")
    w("")
    w("        public ChikuoClip(string state, int frames, float seconds, bool loop, int space, int kind, float apex, float contact,")
    w("            float activeStart, float activeEnd, float tellStart, float tellEnd, float loadStart, float loadEnd, float airStart,")
    w("            float airEnd, float openStart, float openEnd, float ringM, float markerM, float reachM, float groundSpeed,")
    w("            string[] glow, float[] travel, string chainFrom, string chainTo, float fadeFrom, float fadeTo, Vector3 rootOffset,")
    w("            string[] eventNames, float[] eventTimes)")
    w("        {")
    w("            State = state; Frames = frames; Seconds = seconds; Loop = loop; Space = space; Kind = kind; Apex = apex;")
    w("            Contact = contact; ActiveStart = activeStart; ActiveEnd = activeEnd; TellStart = tellStart; TellEnd = tellEnd;")
    w("            LoadStart = loadStart; LoadEnd = loadEnd; AirStart = airStart; AirEnd = airEnd; OpenStart = openStart;")
    w("            OpenEnd = openEnd; RingM = ringM; MarkerM = markerM; ReachM = reachM; GroundSpeed = groundSpeed; Glow = glow;")
    w("            Travel = travel; ChainFrom = chainFrom; ChainTo = chainTo; FadeFrom = fadeFrom; FadeTo = fadeTo;")
    w("            RootOffset = rootOffset; this.eventNames = eventNames; this.eventTimes = eventTimes;")
    w("        }")
    w("")
    w("        /// <summary>Tiempo normalizado del primer evento con ese nombre (-1 si el clip no lo tiene).</summary>")
    w("        public float Event(string name) => EventAt(name, 0);")
    w("")
    w("        /// <summary>Tiempo normalizado del evento número 'index' con ese nombre (los dardos de una ráfaga: -1 si no hay).</summary>")
    w("        public float EventAt(string name, int index)")
    w("        {")
    w("            for (int i = 0; i < eventNames.Length; i++)")
    w("            {")
    w("                if (eventNames[i] != name) continue;")
    w("                if (index == 0) return eventTimes[i];")
    w("                index--;")
    w("            }")
    w("            return -1f;")
    w("        }")
    w("")
    w("        /// <summary>Cuántos eventos con ese nombre trae el clip.</summary>")
    w("        public int EventCount(string name)")
    w("        {")
    w("            int n = 0;")
    w("            for (int i = 0; i < eventNames.Length; i++) if (eventNames[i] == name) n++;")
    w("            return n;")
    w("        }")
    w("")
    w("        /// <summary>Normalizado de un cuadro del clip.</summary>")
    w("        public float FrameNorm(float frame) => Frames > 0 ? frame / Frames : 0f;")
    w("")
    w("        /// <summary>Metros avanzados en el tiempo normalizado 'n' (interpolado entre cuadros).</summary>")
    w("        public float TravelAt(float n)")
    w("        {")
    w("            if (Travel == null) return 0f;")
    w("            float x = Mathf.Clamp(n, 0f, 1f) * Frames;")
    w("            int i = Mathf.Min((int)x, Travel.Length - 1);")
    w("            int j = Mathf.Min(i + 1, Travel.Length - 1);")
    w("            return Travel[i] + (Travel[j] - Travel[i]) * (x - i);")
    w("        }")
    w("    }")
    w("")
    w("    public static class ChikuoTimings")
    w("    {")
    w("        public const float BindHeight = %s;" % f(data["bind_height"]))
    w("        /// <summary>Largo de la flauta-bastón (m): el hueso Staff va de la punta de abajo a la de arriba.</summary>")
    w("        public const float StaffLength = %s;" % f(data["staff"]["length_m"]))
    names = []
    for name, c in clips.items():
        nm = c.get("normalized", {})
        t = c.get("timing", {})
        act = nm.get("active")
        contact = nm.get("contact", act[0] if act else 0.0)
        a0, a1 = (act[0], act[1]) if act else (contact, contact)
        tell = span(nm, "tell")
        load = span(nm, "load")
        air = span(nm, "air")
        opn = span(nm, "open")
        glow = t.get("glow") or []
        evs = c.get("events", [])
        en = strs([e["fn"] for e in evs])
        et = "new[] { " + ", ".join(f(e["t"]) for e in evs) + " }" if evs else "new float[0]"
        ro = c.get("root_offset_m") or [0.0, 0.0, 0.0]
        w("        public static readonly ChikuoClip %s = new ChikuoClip(\"%s\", %d, %s, %s, %d, %d," % (
            name, name, c["frames"], f(c["seconds"]), "true" if c.get("loop") else "false",
            SPACES.get(t.get("space", "ground"), 0), KINDS.get(t.get("kind"), 0)))
        w("            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s," % (
            f(nm.get("apex", 0.0)), f(contact), f(a0), f(a1), f(tell[0]), f(tell[1]), f(load[0]), f(load[1]), f(air[0]),
            f(air[1]), f(opn[0]), f(opn[1])))
        w("            %s, %s, %s, %s, %s," % (f(t.get("ring_m") or 0.0), f(t.get("marker_m") or 0.0), f(t.get("reach_m") or 0.0),
                                           f(t.get("ground_speed_mps") or 0.0), strs(glow)))
        w("            %s," % arr(c.get("travel_m")))
        w("            \"%s\", \"%s\", %s, %s, new Vector3(%s, %s, %s), %s, %s);" % (
            t.get("chain_from", ""), t.get("chain_to", ""), f(t.get("fade_from") or 0.0), f(t.get("fade_to") or 0.0),
            f(ro[0]), f(ro[1]), f(ro[2]), en, et))
        names.append(name)
    aliases = data.get("aliases", {})
    w("")
    w("        /// <summary>Los nombres que Enemy toca por config y no son clips propios (el controller los tiene como estados")
    w("        /// con el clip de otro).</summary>")
    w("        static readonly Dictionary<string, string> aliases = new Dictionary<string, string>")
    w("        {")
    for a, b in aliases.items():
        w("            { \"%s\", \"%s\" }," % (a, b))
    w("        };")
    w("")
    w("        static Dictionary<string, ChikuoClip> all;")
    w("        /// <summary>El clip de un estado o de un alias (null si el FBX no lo tiene).</summary>")
    w("        public static ChikuoClip Get(string state)")
    w("        {")
    w("            if (all == null)")
    w("            {")
    w("                all = new Dictionary<string, ChikuoClip>();")
    w("                foreach (var c in new[] { " + ", ".join(names) + " })")
    w("                    all[c.State] = c;")
    w("            }")
    w("            if (state == null) return null;")
    w("            if (aliases.TryGetValue(state, out var real)) state = real;")
    w("            return all.TryGetValue(state, out var r) ? r : null;")
    w("        }")
    w("    }")
    w("}")
    U.write(DST, "\n".join(out) + "\n")
    U.write_meta(DST, U.MONO_META)
    U.ensure_folder_metas(os.path.dirname(DST))
    print("escrito", os.path.relpath(DST, U.REPO), len(names), "clips")


if __name__ == "__main__":
    main()
