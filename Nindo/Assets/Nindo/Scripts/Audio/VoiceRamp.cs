using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Los fundidos de una voz de música, en el hilo de audio y a la muestra. Al entrar: 6 ms al comienzo de cada toma
    /// que arranca sola (una frase de entrada o un acto que empieza en una muestra que no es cero hace tic sin esto; el
    /// corte de cada compás deja 8 ms antes del tiempo fuerte, así que el ataque queda entero). Al salir: la curva de
    /// Gain desde un tiempo de DSP exacto. Con el volumen de la fuente cambiado frame a frame, una caída de 10 dB en 30
    /// ms eran dos escalones de 16 ms: se oían como un chasquido.
    /// </summary>
    public class VoiceRamp : MonoBehaviour
    {
        const int Length = 265;   // 6 ms a 44.1 kHz
        // lo que sonaba cae 10 dB en 30 ms apenas entra lo nuevo y el resto se apaga en el largo del fundido: la
        // armonía vieja no ensucia el tiempo fuerte de la sección nueva (sonaba a 3-6 dB de ella durante un cuarto
        // de compás) y tampoco se corta en seco
        public const float DipGain = 0.316f;
        public const double DipTime = 0.03;

        volatile bool armed;
        int done;
        double fadeStart = double.MaxValue, fadeLen = 1.0;
        bool dip;
        double rate = 48000.0;

        /// <summary>Al agendar la voz: con 'on' false queda sin fundido de entrada (una continuación).</summary>
        public void Arm(bool on)
        {
            rate = AudioSettings.outputSampleRate;
            fadeStart = double.MaxValue;
            done = 0; armed = on;
        }

        /// <summary>Apaga la voz desde 'start' (tiempo de DSP) en 'len' s; 'withDip': la caída rápida de 10 dB primero.</summary>
        public void FadeOut(double start, double len, bool withDip)
        {
            fadeLen = System.Math.Max(1e-3, len);
            dip = withDip;
            fadeStart = start;
        }

        /// <summary>Ganancia del fundido de salida en el tiempo t: (1-u)² y, con 'withDip', la caída de 10 dB en 30 ms.</summary>
        public static float Gain(double t, double start, double len, bool withDip)
        {
            if (t <= start) return 1f;
            double e = t - start, u = e / System.Math.Max(1e-3, len);
            if (u >= 1.0) return 0f;
            float k = 1f - (float)u;
            k *= k;
            if (withDip) k *= e >= DipTime ? DipGain : 1f - (1f - DipGain) * (float)(e / DipTime);
            return k;
        }

        void OnAudioFilterRead(float[] data, int channels)
        {
            int frames = data.Length / channels;
            if (armed)
            {
                int i = 0;
                // antes del PlayScheduled la fuente entrega ceros: el fundido empieza en la primera muestra que suena
                if (done == 0)
                {
                    while (i < frames && IsSilent(data, i * channels, channels)) i++;
                }
                for (; i < frames && done < Length; i++, done++)
                {
                    float k = done / (float)Length;
                    for (int c = 0; c < channels; c++) data[i * channels + c] *= k;
                }
                if (done >= Length) armed = false;
            }
            double fs = fadeStart;
            if (fs == double.MaxValue) return;
            // dspTime en este callback es el comienzo del bloque que se está mezclando
            double t0 = AudioSettings.dspTime;
            if (t0 + frames / rate <= fs) return;
            double len = fadeLen;
            bool d = dip;
            for (int i = 0; i < frames; i++)
            {
                float g = Gain(t0 + i / rate, fs, len, d);
                for (int c = 0; c < channels; c++) data[i * channels + c] *= g;
            }
        }

        static bool IsSilent(float[] d, int at, int channels)
        {
            for (int c = 0; c < channels; c++) if (d[at + c] != 0f) return false;
            return true;
        }
    }
}
