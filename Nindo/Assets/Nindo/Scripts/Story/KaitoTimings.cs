// Generado por Tools/Unity/kaito_timings.py desde Animations teo/kaitooo.fbx.json: no editar a mano.
namespace Nindo
{
    /// <summary>
    /// Momentos (normalizados 0..1) de los clips de Kaito que usan las escenas de la historia, copiados de los eventos
    /// del sidecar. Clips del contrato presentes: ninguno todavía.
    /// </summary>
    public static class KaitoTimings
    {
        static readonly string[] states = { };
        static readonly string[] names = { };
        static readonly float[] times = { };

        /// <summary>El primer evento 'name' del clip 'state' o, si el clip no lo trae, 'fallback'.</summary>
        public static float Event(string state, string name, float fallback)
        {
            for (int i = 0; i < states.Length; i++) if (states[i] == state && names[i] == name) return times[i];
            return fallback;
        }
    }
}
