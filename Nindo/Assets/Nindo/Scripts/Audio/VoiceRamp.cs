using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Fundido de 6 ms al comienzo de cada toma, en el hilo de audio. Las entradas en medio de un tema (la sección del
    /// desarrollo, el acto 3 después del eclipse) arrancan en una muestra que no es cero: sin esto, un tic. El corte de
    /// cada compás deja 8 ms antes del tiempo fuerte, así que el ataque queda entero.
    /// </summary>
    public class VoiceRamp : MonoBehaviour
    {
        const int Length = 265;   // 6 ms a 44.1 kHz
        volatile bool armed;
        int done;

        /// <summary>Al agendar la voz: con 'on' false queda sin fundido (una continuación).</summary>
        public void Arm(bool on) { done = 0; armed = on; }

        void OnAudioFilterRead(float[] data, int channels)
        {
            if (!armed) return;
            int frames = data.Length / channels, i = 0;
            // antes del PlayScheduled la fuente entrega ceros: el fundido empieza en la primera muestra que suena
            if (done == 0)
            {
                while (i < frames && IsSilent(data, i * channels, channels)) i++;
                if (i == frames) return;
            }
            for (; i < frames && done < Length; i++, done++)
            {
                float k = done / (float)Length;
                for (int c = 0; c < channels; c++) data[i * channels + c] *= k;
            }
            if (done >= Length) armed = false;
        }

        static bool IsSilent(float[] d, int at, int channels)
        {
            for (int c = 0; c < channels; c++) if (d[at + c] != 0f) return false;
            return true;
        }
    }
}
