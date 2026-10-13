"""Genera Scripts/Enemies/Bosses/BambooMasterTimings.cs desde Art/Characters/BambooMaster/BambooMaster.fbx.json.

El JSON lo escribe Tools/Blender/bosses/bamboo_master/build_bamboo_master.py junto con el FBX: es la única fuente de
los tiempos de cada clip de Chikuō (apex, contacto, ventana activa, ritmo de la suelta, alcance, avance del
transform por cuadro, tramo en el aire, anillo, marca del salto, eventos, qué miembro brilla). Así los AttackDef de
BambooMasterMoves.cs no pueden despegarse de lo que se ve: si se rehace un clip, se corre este script y se recompila.

Uso: python Tools/Unity/bamboo_master_timings.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unity_yaml as U

SRC = os.path.join(U.ASSETS, "Nindo", "Art", "Characters", "BambooMaster", "BambooMaster.fbx.json")
DST = os.path.join(U.ASSETS, "Nindo", "Scripts", "Enemies", "Bosses", "BambooMasterTimings.cs")
KINDS = {"parry": 1, "dodge": 2}


def f(x):
    s = ("%.4f" % float(x)).rstrip("0")
    if s.endswith("."):
        s += "0"
    return s + "f"


def arr(xs):
    return "null" if not xs else "new[] { " + ", ".join(f(x) for x in xs) + " }"


def strs(xs):
    return "new string[0]" if not xs else "new[] { " + ", ".join('"%s"' % x for x in xs) + " }"


def main():
    data = json.load(open(SRC, encoding="utf-8"))
    clips = data["clips"]
    out = []
    w = out.append
    w("// Generado por Tools/Unity/bamboo_master_timings.py desde BambooMaster.fbx.json: no editar a mano.")
    w("using System.Collections.Generic;")
    w("")
    w("namespace Nindo")
    w("{")
    w("    /// <summary>Tiempos de un clip de Chikuō tal como los mide el build de Blender (normalizados 0..1).</summary>")
    w("    public sealed class MasterClip")
    w("    {")
    w("        public readonly string State;")
    w("        public readonly int Frames;")
    w("        public readonly float Seconds, Apex, Contact, ActiveEnd, ReleaseRate, Reach;")
    w("        /// <summary>0 = no pega, 1 = dorado (parry), 2 = rojo (dash).</summary>")
    w("        public readonly int Kind;")
    w("        /// <summary>Slots de CharacterGlint que se encienden con el aviso (la mano, el pie o el bastón que pega).</summary>")
    w("        public readonly string[] Glow;")
    w("        /// <summary>Radio del anillo rojo (barrida, caída del salto; 0 = sin anillo), dónde cae el pie del salto")
    w("        /// medido desde el transform inicial (0 = no salta) y metros que retrocede una reacción (knock_m).</summary>")
    w("        public readonly float RingM, MarkerM, KnockM;")
    w("        /// <summary>Tramo con los dos pies en el aire (normalizado; AirEnd 0 = no tiene): ahí se puede estirar el avance.</summary>")
    w("        public readonly float AirStart, AirEnd;")
    w("        /// <summary>Metros que avanzó el transform en cada cuadro del clip (null = no se mueve).</summary>")
    w("        public readonly float[] Travel;")
    w("        /// <summary>Pose con la que empieza y con la que termina (READY, GUARD, COIL...) y cuántos grados se aparta su")
    w("        /// primer cuadro de esa pose (lo mide el build: arriba de 2° un fundido de 0.08 s se ve saltar).</summary>")
    w("        public readonly string ChainFrom, ChainTo;")
    w("        public readonly float ChainFromDeg;")
    w("        /// <summary>Las variantes de paso más corto del mismo golpe, de la más larga a la más corta (vacío = no tiene):")
    w("        /// mismos cuadros, tiempos y poses hasta la suelta; el jefe pasa a la que entra hasta Kaito en la suelta.</summary>")
    w("        public readonly string[] Variants;")
    w("        /// <summary>Grados que gira el transform en cada cuadro del clip (+ = hacia su izquierda, como en Blender; null =")
    w("        /// no gira): el paso del viento que pasa al costado gira en el vuelo y el jefe lo aplica como el avance.</summary>")
    w("        public readonly float[] Turn;")
    w("        /// <summary>La variante del paso del viento que le pasa al costado a Kaito (mismos cuadros hasta la suelta; null =")
    w("        /// no tiene).</summary>")
    w("        public readonly string Pass;")
    w("        readonly string[] eventNames;")
    w("        readonly float[] eventTimes;")
    w("")
    w("        public MasterClip(string state, int frames, float seconds, float apex, float contact, float activeEnd, float releaseRate,")
    w("            float reach, int kind, string[] glow, float ringM, float markerM, float knockM, float airStart, float airEnd,")
    w("            float[] travel, string chainFrom, string chainTo, float chainFromDeg, string[] variants, string[] eventNames,")
    w("            float[] eventTimes, float[] turn = null, string pass = null)")
    w("        {")
    w("            State = state; Frames = frames; Seconds = seconds; Apex = apex; Contact = contact; ActiveEnd = activeEnd;")
    w("            ReleaseRate = releaseRate; Reach = reach; Kind = kind; Glow = glow; RingM = ringM; MarkerM = markerM; KnockM = knockM;")
    w("            AirStart = airStart; AirEnd = airEnd; Travel = travel; ChainFrom = chainFrom; ChainTo = chainTo;")
    w("            ChainFromDeg = chainFromDeg; Variants = variants; Turn = turn; Pass = pass;")
    w("            this.eventNames = eventNames; this.eventTimes = eventTimes;")
    w("        }")
    w("")
    w("        /// <summary>Tiempo normalizado del primer evento con ese nombre (-1 si el clip no lo tiene).</summary>")
    w("        public float Event(string name)")
    w("        {")
    w("            for (int i = 0; i < eventNames.Length; i++) if (eventNames[i] == name) return eventTimes[i];")
    w("            return -1f;")
    w("        }")
    w("")
    w("        /// <summary>Normalizado de un cuadro del clip.</summary>")
    w("        public float FrameNorm(float frame) => Frames > 0 ? frame / Frames : 0f;")
    w("")
    w("        /// <summary>Metros avanzados en el tiempo normalizado 'n' (interpolado entre cuadros).</summary>")
    w("        public float TravelAt(float n)")
    w("        {")
    w("            if (Travel == null) return 0f;")
    w("            float x = UnityEngine.Mathf.Clamp(n, 0f, 1f) * Frames;")
    w("            int i = UnityEngine.Mathf.Min((int)x, Travel.Length - 1);")
    w("            int j = UnityEngine.Mathf.Min(i + 1, Travel.Length - 1);")
    w("            return Travel[i] + (Travel[j] - Travel[i]) * (x - i);")
    w("        }")
    w("")
    w("        /// <summary>Grados girados en el tiempo normalizado 'n' (0 si el clip no gira).</summary>")
    w("        public float TurnAt(float n)")
    w("        {")
    w("            if (Turn == null) return 0f;")
    w("            float x = UnityEngine.Mathf.Clamp(n, 0f, 1f) * Frames;")
    w("            int i = UnityEngine.Mathf.Min((int)x, Turn.Length - 1);")
    w("            int j = UnityEngine.Mathf.Min(i + 1, Turn.Length - 1);")
    w("            return Turn[i] + (Turn[j] - Turn[i]) * (x - i);")
    w("        }")
    w("")
    w("        /// <summary>Lo que avanza el cuerpo hasta el golpe (para saber desde qué distancia llega).</summary>")
    w("        public float TravelToContact => TravelAt(Contact);")
    w("    }")
    w("")
    w("    public static class BambooMasterTimings")
    w("    {")
    w("        public const float BindHeight = %s;" % f(data["bind_height"]))
    w("        /// <summary>Largo del bastón (m): el hueso Staff va de la punta de abajo a la de arriba.</summary>")
    w("        public const float StaffLength = %s;" % f(data["staff"]["length_m"]))
    names = []
    for name, c in clips.items():
        nm = c.get("normalized", {})
        t = c.get("timing", {})
        act = nm.get("active")
        contact = nm.get("contact", act[0] if act else 0.0)
        active_end = act[1] if act else contact
        apex = nm.get("apex", 0.0)
        rr = c.get("release_rate") or t.get("release_rate") or 1.6
        glow = t.get("glow") or []
        if isinstance(glow, str):
            glow = [glow]
        air = nm.get("air") or [0.0, 0.0]
        evs = c.get("events", [])
        en = strs([e["fn"] for e in evs])
        et = "new[] { " + ", ".join(f(e["t"]) for e in evs) + " }" if evs else "new float[0]"
        w("        public static readonly MasterClip %s = new MasterClip(\"%s\", %d, %s, %s, %s, %s, %s, %s, %d, %s," % (
            name, name, c["frames"], f(c["seconds"]), f(apex), f(contact), f(active_end), f(rr), f(c.get("reach_m") or 0.0),
            KINDS.get(t.get("kind"), 0), strs(glow)))
        w("            %s, %s, %s, %s, %s," % (f(t.get("ring_m") or 0.0), f(t.get("marker_m") or 0.0), f(t.get("knock_m") or 0.0),
                                            f(air[0]), f(air[1])))
        w("            %s," % arr(c.get("travel_m")))
        cd = (c.get("lint", {}).get("chain_chain_from_deg") or [0.0])[0]
        extra = ""
        if c.get("turn_deg"):
            extra += ", turn: %s" % arr(c["turn_deg"])
        if t.get("pass_variant"):
            extra += ", pass: \"%s\"" % t["pass_variant"]
        w("            \"%s\", \"%s\", %s, %s, %s, %s%s);" % (t.get("chain_from", ""), t.get("chain_to", ""), f(cd),
                                                    strs(t.get("reach_variants") or []), en, et, extra))
        names.append(name)
    w("")
    w("        static Dictionary<string, MasterClip> all;")
    w("        /// <summary>El clip de un estado (null si el FBX no lo tiene).</summary>")
    w("        public static MasterClip Get(string state)")
    w("        {")
    w("            if (all == null)")
    w("            {")
    w("                all = new Dictionary<string, MasterClip>();")
    w("                foreach (var c in new[] { " + ", ".join(names) + " })")
    w("                    all[c.State] = c;")
    w("            }")
    w("            return state != null && all.TryGetValue(state, out var r) ? r : null;")
    w("        }")
    w("    }")
    w("}")
    U.write(DST, "\n".join(out) + "\n")
    U.write_meta(DST, U.MONO_META)
    U.ensure_folder_metas(os.path.dirname(DST))
    print("escrito", os.path.relpath(DST, U.REPO), len(names), "clips")


if __name__ == "__main__":
    main()
