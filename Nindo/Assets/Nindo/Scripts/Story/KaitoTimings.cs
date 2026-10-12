// Generado por Tools/Unity/kaito_timings.py desde Animations teo/kaitooo.fbx.json: no editar a mano.
namespace Nindo
{
    /// <summary>
    /// Momentos (normalizados 0..1) de los clips de Kaito que usan las escenas de la historia, copiados de los eventos
    /// del sidecar. Clips del contrato presentes: BandanaPower, EndingTurn, PrayIncense, PrayQuick, WakeUp.
    /// </summary>
    public static class KaitoTimings
    {
        static readonly string[] states = { "PrayIncense", "PrayIncense", "PrayIncense", "PrayIncense", "PrayIncense", "PrayIncense", "PrayIncense", "PrayQuick", "PrayQuick", "PrayQuick", "BandanaPower", "BandanaPower", "WakeUp", "WakeUp", "WakeUp", "EndingTurn", "EndingTurn", "EndingTurn" };
        static readonly string[] names = { "katana_down", "incense_take", "incense_light", "incense_place", "palms", "katana_up", "rise", "kneel", "palms", "rise", "glow", "release", "stir", "see", "stand", "turned", "ribbon", "offer" };
        static readonly float[] times = { 0.1452f, 0.3763f, 0.4731f, 0.6237f, 0.6882f, 0.8763f, 0.8871f, 0.1833f, 0.2667f, 0.7f, 0.1867f, 0.5333f, 0.2593f, 0.7407f, 0.8611f, 0.4643f, 0.5952f, 0.7262f };

        /// <summary>El primer evento 'name' del clip 'state' o, si el clip no lo trae, 'fallback'.</summary>
        public static float Event(string state, string name, float fallback)
        {
            for (int i = 0; i < states.Length; i++) if (states[i] == state && names[i] == name) return times[i];
            return fallback;
        }
    }
}
