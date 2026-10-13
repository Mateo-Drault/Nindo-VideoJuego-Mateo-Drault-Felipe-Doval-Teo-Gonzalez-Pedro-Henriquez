// Generado por Tools/Unity/kaito_timings.py desde Animations teo/kaitooo.fbx.json: no editar a mano.
namespace Nindo
{
    /// <summary>
    /// Momentos (normalizados 0..1) de los clips de Kaito que usan las escenas de la historia, copiados de los eventos
    /// del sidecar. Clips del contrato presentes: BandanaPower, EndingTurn, PrayIncense, PrayQuick, WakeUp.
    /// </summary>
    public static class KaitoTimings
    {
        static readonly string[] states = { "PrayIncense", "PrayIncense", "PrayIncense", "PrayIncense", "PrayIncense", "PrayIncense", "PrayIncense", "PrayQuick", "PrayQuick", "PrayQuick", "PrayQuick", "PrayQuick", "BandanaPower", "BandanaPower", "WakeUp", "WakeUp", "WakeUp", "EndingTurn", "EndingTurn", "EndingTurn" };
        static readonly string[] names = { "katana_down", "incense_take", "incense_light", "incense_place", "palms", "katana_up", "rise", "kneel", "katana_down", "palms", "katana_up", "rise", "glow", "release", "stir", "see", "stand", "turned", "ribbon", "offer" };
        static readonly float[] times = { 0.1489f, 0.3723f, 0.4681f, 0.617f, 0.6809f, 0.8457f, 0.883f, 0.1571f, 0.3f, 0.4f, 0.7f, 0.8143f, 0.1867f, 0.5333f, 0.2593f, 0.7407f, 0.8611f, 0.4643f, 0.5952f, 0.7262f };

        /// <summary>EndingTurn arranca con el cuerpo este tanto (m) detrás del transform y termina parado en él.</summary>
        public const float EndingTurnShift = 0.55f;

        /// <summary>El primer evento 'name' del clip 'state' o, si el clip no lo trae, 'fallback'.</summary>
        public static float Event(string state, string name, float fallback)
        {
            for (int i = 0; i < states.Length; i++) if (states[i] == state && names[i] == name) return times[i];
            return fallback;
        }
    }
}
