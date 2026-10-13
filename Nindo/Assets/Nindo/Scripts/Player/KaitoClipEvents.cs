using System.Collections.Generic;

namespace Nindo
{
    /// <summary>
    /// GENERADO por Tools/Blender/anim/kaito/build_kaito.py (no editar a mano): tiempo normalizado (0..1 del clip) de
    /// cada momento con nombre de los clips de historia de Kaito (incense_take, palms, release, offer...), sacado de
    /// los 'events' de kaitooo.fbx.json. Lo lee PlayerController.ClipEventTime.
    /// </summary>
    public static class KaitoClipEvents
    {
        static readonly Dictionary<(string, string), float> times = new Dictionary<(string, string), float>
        {
            { ("PrayIncense", "katana_down"), 0.1489f },
            { ("PrayIncense", "incense_take"), 0.3723f },
            { ("PrayIncense", "incense_light"), 0.4681f },
            { ("PrayIncense", "incense_place"), 0.6170f },
            { ("PrayIncense", "palms"), 0.6809f },
            { ("PrayIncense", "katana_up"), 0.8457f },
            { ("PrayIncense", "rise"), 0.8830f },
            { ("PrayQuick", "kneel"), 0.1571f },
            { ("PrayQuick", "katana_down"), 0.3000f },
            { ("PrayQuick", "palms"), 0.4000f },
            { ("PrayQuick", "katana_up"), 0.7000f },
            { ("PrayQuick", "rise"), 0.8143f },
            { ("BandanaPower", "glow"), 0.1867f },
            { ("BandanaPower", "release"), 0.5333f },
            { ("EndingTurn", "turned"), 0.4643f },
            { ("EndingTurn", "ribbon"), 0.5952f },
            { ("EndingTurn", "offer"), 0.7262f },
            { ("WakeUp", "stir"), 0.2593f },
            { ("WakeUp", "see"), 0.7407f },
            { ("WakeUp", "stand"), 0.8611f },
        };

        public static bool TryGet(string state, string evt, out float normalized) => times.TryGetValue((state, evt), out normalized);
    }
}
