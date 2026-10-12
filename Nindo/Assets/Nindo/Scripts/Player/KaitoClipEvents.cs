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
            { ("PrayIncense", "katana_down"), 0.1452f },
            { ("PrayIncense", "incense_take"), 0.3763f },
            { ("PrayIncense", "incense_light"), 0.4731f },
            { ("PrayIncense", "incense_place"), 0.6237f },
            { ("PrayIncense", "palms"), 0.6882f },
            { ("PrayIncense", "katana_up"), 0.8763f },
            { ("PrayIncense", "rise"), 0.8871f },
            { ("PrayQuick", "kneel"), 0.1667f },
            { ("PrayQuick", "katana_down"), 0.2576f },
            { ("PrayQuick", "palms"), 0.3636f },
            { ("PrayQuick", "katana_up"), 0.7424f },
            { ("PrayQuick", "rise"), 0.8030f },
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
