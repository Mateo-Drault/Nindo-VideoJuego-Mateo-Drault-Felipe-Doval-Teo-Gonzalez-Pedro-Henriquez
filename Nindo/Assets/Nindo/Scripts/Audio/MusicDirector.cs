using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Tabla de la música por fases: los datos (MusicPlan.cs) los genera Tools/Audio/build_boss_music.py desde lo que
    /// midió al cortar los temas (largo exacto, compás, muestras de entrada). Los tipos y la búsqueda viven acá.
    /// </summary>
    public static partial class MusicPlan
    {
        /// <summary>Loop: se encadena consigo mismo. Once: intro o transición que desemboca en el loop de su fase (su
        /// grilla de compases se cuenta desde el final, que es donde cae el compás 0 del loop). Outro: el cierre del tema.</summary>
        public enum ClipKind { Loop, Once, Outro }

        public sealed class Clip
        {
            public readonly string key;
            public readonly int samples, rate;
            public readonly double bar;
            public readonly ClipKind kind;
            public Clip(string key, int samples, int rate, double bar, ClipKind kind)
            {
                this.key = key; this.samples = samples; this.rate = rate; this.bar = bar; this.kind = kind;
            }
            public double Seconds => samples / (double)rate;
        }

        /// <summary>Una fase: el loop, la intro o transición que suena una vez antes (o null), desde qué muestra del
        /// loop se entra (otra sección del mismo tema) y desde qué muestra de la intro (una transición más corta).</summary>
        public sealed class Phase
        {
            public readonly string clip, intro;
            public readonly int entry, introEntry;
            public Phase(string clip, string intro, int entry, int introEntry)
            {
                this.clip = clip; this.intro = intro; this.entry = entry; this.introEntry = introEntry;
            }
        }

        /// <summary>Un tema por fases. Al caer el jefe suena 'outro' (o, sin toma final, el loop se funde 'outroFade' s)
        /// y, si 'resumeExplore', después vuelve la música de la zona.</summary>
        public sealed class Track
        {
            public readonly string key, outro;
            public readonly Phase[] phases;
            public readonly float outroFade;
            public readonly bool resumeExplore;
            public Track(string key, Phase[] phases, string outro, float outroFade, bool resumeExplore)
            {
                this.key = key; this.phases = phases; this.outro = outro; this.outroFade = outroFade; this.resumeExplore = resumeExplore;
            }
            /// <summary>Una fase más alta que las que tiene el tema se queda en la última (pedir la 3 a Gorō no rompe nada).</summary>
            public Phase PhaseAt(int n) => phases[Mathf.Clamp(n, 1, phases.Length) - 1];
            public int Clamp(int n) => Mathf.Clamp(n, 1, phases.Length);
        }

        static Dictionary<string, Clip> clipMap;
        static Dictionary<string, Track> trackMap;

        public static Clip FindClip(string key)
        {
            if (clipMap == null)
            {
                clipMap = new Dictionary<string, Clip>();
                foreach (var c in clips) clipMap[c.key] = c;
            }
            return key != null && clipMap.TryGetValue(key, out var r) ? r : null;
        }

        public static Track Find(string key)
        {
            if (trackMap == null)
            {
                trackMap = new Dictionary<string, Track>();
                foreach (var t in tracks) trackMap[t.key] = t;
            }
            return key != null && trackMap.TryGetValue(key, out var r) ? r : null;
        }
    }

    /// <summary>
    /// Música de jefe por fases y tema del final, encadenados a la muestra con AudioSource.PlayScheduled sobre el reloj
    /// del DSP. Ningún clip usa AudioSource.loop: cada vuelta se agenda al terminar la anterior con el largo de la tabla,
    /// así la costura es la que se midió al cortar el tema aunque el importador de Unity agregue cola al Vorbis.
    /// Un cambio de fase espera el próximo compás de lo que suena: la sección nueva entra entera en ese tiempo fuerte y
    /// lo anterior se apaga en un pulso. Antes de un silencio (barra falsa de Gorō, eclipse de Kokuyō) se apaga y la
    /// fase siguiente entra apenas se la pide. Lo maneja AudioManager (PlayBossMusic, SetBossMusicPhase, ...).
    /// </summary>
    public class MusicDirector : MonoBehaviour
    {
        const int VoiceCount = 6;
        // PlayScheduled necesita agendarse antes de que el DSP llegue (buffers de 256-1024 muestras y el decodificador)
        const double Lead = 0.25;
        // un cambio pedido se fija recién cuando el compás está a menos de esto: si llega otro antes, gana el último
        const double CommitWindow = 0.5;
        // en un reintento la intro larga (16 s de koto solo en Gorō, 13 s de latido en Kokuyō) no se repite
        const float LongIntro = 4f;

        sealed class Voice
        {
            public AudioSource src;
            public VoiceRamp ramp;
            public MusicPlan.Clip clip;
            public int layer = -1;          // -1: libre
            public double start, end;       // tiempos de DSP
            public int offset;              // muestra del clip donde arranca
            public float volume;            // volumen de la entrada de NindoContent
            public double fadeStart = double.MaxValue, fadeLen;
        }

        readonly Voice[] voices = new Voice[VoiceCount];
        readonly HashSet<string> introHeard = new HashSet<string>();
        AudioManager owner;
        MusicPlan.Track track;
        int layer;              // capa actual; las anteriores se están apagando
        int head = -1, next = -1;
        int playing, target;    // fase que suena y fase pedida
        bool pendingStart, silent, inOutro;
        double startAt, outroEnd;

        /// <summary>Hay un tema dirigido sonando: una pelea, su cierre o el final. La música de zona y de combate no lo pisa.</summary>
        public bool Busy => track != null;

        public void Init(AudioManager audio)
        {
            owner = audio;
            for (int i = 0; i < VoiceCount; i++)
            {
                var go = new GameObject("Music" + i);
                go.transform.SetParent(transform, false);
                var s = go.AddComponent<AudioSource>();
                s.playOnAwake = false; s.loop = false; s.spatialBlend = 0f; s.priority = 0; s.volume = 0f;
                // cada voz en su objeto: el fundido de entrada (OnAudioFilterRead) es de esa fuente sola
                voices[i] = new Voice { src = s, ramp = go.AddComponent<VoiceRamp>() };
            }
            AudioSettings.OnAudioConfigurationChanged += OnAudioReset;
        }

        void OnDestroy() => AudioSettings.OnAudioConfigurationChanged -= OnAudioReset;

        /// <summary>Para probar (RunCommand): tema, fase pedida y sonando, y cada voz con su clip, posición y volumen.</summary>
        public string Describe()
        {
            var sb = new System.Text.StringBuilder();
            sb.Append(track != null ? track.key : "(nada)").Append(" fase ").Append(playing).Append('/').Append(target);
            if (silent) sb.Append(" silencio");
            if (inOutro) sb.Append(" cierre");
            double now = Now;
            for (int i = 0; i < VoiceCount; i++)
            {
                var v = voices[i];
                if (v.layer < 0) continue;
                double pos = (v.offset + (now - v.start) * v.clip.rate) / v.clip.rate;
                sb.Append("\n  ").Append(i == head ? "> " : i == next ? "+ " : "  ").Append(v.clip.key)
                  .Append(" capa ").Append(v.layer).Append(" en ").Append(pos.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture))
                  .Append(" s, vol ").Append(v.src.volume.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture))
                  .Append(", fuente ").Append(v.src.timeSamples).Append(" muestras");
            }
            return sb.ToString();
        }

        /// <summary>¿Este tema es por fases y está en NindoContent? Si falta el clip se usa el camino de siempre.</summary>
        public bool Handles(string key)
        {
            var t = MusicPlan.Find(key);
            return t != null && Resolve(t.PhaseAt(1).clip) != null;
        }

        // ------------------------------------------------------------------ API (la usa AudioManager)
        /// <summary>Arranca el tema en la fase 1 (o en la que se pida en este mismo frame), 'delay' s después.</summary>
        public void Play(string key, float delay = 0f)
        {
            var t = MusicPlan.Find(key);
            if (t == null) return;
            if (t == track && !silent && !inOutro && (playing > 0 || pendingStart)) return;
            FadeAll(Now, 0.3);
            track = t;
            target = 1; playing = 0;
            silent = inOutro = false;
            pendingStart = true;
            startAt = Now + Mathf.Max(0f, delay);
            head = next = -1;
        }

        public void SetPhase(int phase)
        {
            if (track == null || inOutro) return;
            phase = track.Clamp(phase);
            if (silent)
            {
                // después del silencio la fase entra apenas se la pide (la misma que sonaba o una más alta), con su
                // intro o transición, sin esperar compás: no hay nada sonando con qué alinearse
                target = Mathf.Max(target, phase);
                silent = false; pendingStart = true; startAt = Now;
                return;
            }
            if (phase <= target) return;
            target = phase;
        }

        /// <summary>Apaga lo que suena sin terminar el tema: la próxima SetPhase entra desde el silencio.</summary>
        public bool Silence(float fade)
        {
            if (track == null || inOutro) return false;
            FadeAll(Now, Mathf.Max(0.05f, fade));
            head = next = -1;
            silent = true; pendingStart = false; playing = 0;
            return true;
        }

        public void Stop(float fade)
        {
            if (track == null && !AnyVoice()) return;
            FadeAll(Now, Mathf.Max(0.05f, fade));
            track = null;
            head = next = -1;
            pendingStart = silent = inOutro = false;
            playing = target = 0;
        }

        /// <summary>
        /// El jefe cayó: en el próximo tiempo (no compás: el golpe final tiene que llegar con el remate) entra el cierre
        /// escrito del tema y lo que sonaba se apaga en un pulso; sin cierre, el loop se funde. false si no había tema.
        /// </summary>
        public bool End()
        {
            if (track == null) return false;
            if (inOutro) return true;
            double now = Now;
            if (silent || pendingStart || head < 0)
            {
                FadeAll(now, 1.0);
                Finish(track.resumeExplore);
                return true;
            }
            double b = NextBoundary(now + Lead, 0.25);
            var o = MusicPlan.FindClip(track.outro);
            if (o != null && Resolve(o.key) == null) o = null;
            if (o != null)
            {
                double pulse = voices[head].clip.bar / 4;
                FadeLayer(layer, b, pulse);
                layer++;
                int v = Schedule(o, 0, b, true);
                head = v; next = -1;
                outroEnd = v >= 0 ? voices[v].end : b + pulse;
            }
            else
            {
                double f = System.Math.Max(0.5, track.outroFade);
                FadeLayer(layer, b, f);
                head = next = -1;
                outroEnd = b + f;
            }
            inOutro = true;
            return true;
        }

        // ------------------------------------------------------------------ motor
        static double Now => AudioSettings.dspTime;

        // en LateUpdate: un PlayBossMusic y un SetBossMusicPhase del mismo frame (en cualquier orden de scripts) se
        // resuelven juntos y el tema arranca directo en la fase pedida
        void LateUpdate()
        {
            double now = Now;
            if (track != null)
            {
                if (pendingStart)
                {
                    pendingStart = false;
                    StartLayer(target, System.Math.Max(startAt, now + Lead), true);
                }
                // lo que suena terminó: sigue lo agendado y se agenda la vuelta siguiente (el loop entero, desde 0)
                if (head >= 0 && now >= voices[head].end)
                {
                    head = next; next = -1;
                    if (head >= 0 && voices[head].clip.kind == MusicPlan.ClipKind.Loop)
                        next = Schedule(voices[head].clip, 0, voices[head].end, false);
                }
                // la música de la zona vuelve cuando el cierre ya se apagó (no encima del último golpe)
                if (inOutro && now >= outroEnd) Finish(track.resumeExplore);
                else if (!inOutro && !silent && head >= 0 && target != playing) TryCommit(now);
            }
            float vol = owner != null ? owner.MusicVolume : 1f;
            for (int i = 0; i < VoiceCount; i++)
            {
                var v = voices[i];
                if (v.layer < 0) continue;
                float env = Envelope(v, now);
                bool ended = now > v.end + 0.1 && i != head && i != next;
                if (env <= 0f || ended) { Release(v); continue; }
                v.src.volume = vol * v.volume * env;
            }
        }

        void TryCommit(double now)
        {
            var h = voices[head];
            // todavía no se oye (se pidió en el frame siguiente al arranque): se reemplaza en el mismo instante
            if (h.start > now + 0.05)
            {
                double at = h.start;
                CancelLayer(layer);
                StartLayer(target, at, true);
                return;
            }
            // la fase nueva es una sección más adelante del mismo loop y ya se está tocando esa parte (el desarrollo de
            // Mizuchi, la sección C del bambú): volver a su comienzo repetiría compases; sigue como está
            var p = track.PhaseAt(target);
            var prev = track.PhaseAt(playing);
            if (h.clip.kind == MusicPlan.ClipKind.Loop && h.clip.key == p.clip && prev.clip == p.clip && p.entry >= prev.entry &&
                h.offset + (now - h.start) * h.clip.rate >= p.entry)
            {
                playing = target;
                return;
            }
            double b = NextBoundary(now + Lead, 1.0);
            if (b - now > CommitWindow) return;
            FadeLayer(layer, b, h.clip.bar / 4);
            StartLayer(target, b, true);
        }

        void StartLayer(int phase, double at, bool allowIntro)
        {
            layer++;
            var p = track.PhaseAt(phase);
            var loop = MusicPlan.FindClip(p.clip);
            var intro = allowIntro ? MusicPlan.FindClip(p.intro) : null;
            if (intro != null && phase == 1 && introHeard.Contains(track.key) && intro.Seconds > LongIntro) intro = null;
            head = next = -1;
            if (intro != null) head = Schedule(intro, p.introEntry, at, true);
            if (head >= 0) next = Schedule(loop, p.entry, voices[head].end, false);
            else
            {
                head = Schedule(loop, p.entry, at, true);
                if (head >= 0) next = Schedule(loop, 0, voices[head].end, false);
            }
            playing = phase;
            if (phase == 1) introHeard.Add(track.key);
        }

        /// <summary>Próximo límite de compás (o de 'fraction' de compás) a partir de tmin en lo que suena o en lo que
        /// sigue. Los loops arrancan en un compás; las intros y transiciones terminan en uno.</summary>
        double NextBoundary(double tmin, double fraction)
        {
            double b = head >= 0 ? Boundary(voices[head], tmin, fraction) : -1;
            if (b < 0 && next >= 0) b = Boundary(voices[next], tmin, fraction);
            return b < 0 ? tmin : b;
        }

        static double Boundary(Voice v, double tmin, double fraction)
        {
            if (tmin >= v.end) return -1;
            var c = v.clip;
            double unit = c.bar * fraction * c.rate;
            double pos = v.offset + System.Math.Max(0.0, tmin - v.start) * c.rate;
            double b;
            if (c.kind == MusicPlan.ClipKind.Once)
                b = c.samples - System.Math.Floor((c.samples - pos) / unit) * unit;
            else
            {
                b = System.Math.Ceiling(pos / unit - 1e-6) * unit;
                // una astilla antes del final de la vuelta: mejor la vuelta misma (lo que sigue arranca ahí)
                if (b > c.samples - unit * 0.05) b = c.samples;
            }
            return v.start + (b - v.offset) / c.rate;
        }

        /// <summary>'cold': la toma arranca sola (fundido de 6 ms); una vuelta o el loop después de su intro siguen la
        /// onda de lo anterior y no llevan fundido (sería un hueco de 6 ms en cada costura).</summary>
        int Schedule(MusicPlan.Clip c, int offset, double at, bool cold)
        {
            if (c == null) return -1;
            var ac = Resolve(c.key);
            if (ac == null) return -1;
            int i = FreeVoice();
            if (i < 0) return -1;
            var v = voices[i];
            if (ac.loadState != AudioDataLoadState.Loaded) ac.LoadAudioData();
            v.clip = c; v.layer = layer; v.offset = offset;
            v.start = at;
            v.end = at + (c.samples - offset) / (double)c.rate;
            v.fadeStart = double.MaxValue;
            v.volume = EntryVolume(c.key);
            v.src.clip = ac;
            // la tabla está en muestras a la frecuencia del clip original; si Unity lo importó a otra, se escala
            v.src.timeSamples = Mathf.Clamp((int)((long)offset * ac.frequency / c.rate), 0, Mathf.Max(0, ac.samples - 1));
            v.src.volume = (owner != null ? owner.MusicVolume : 1f) * v.volume;
            v.ramp.Arm(cold);
            v.src.PlayScheduled(at);
            v.src.SetScheduledEndTime(v.end);
            return i;
        }

        int FreeVoice()
        {
            int best = -1;
            for (int i = 0; i < VoiceCount; i++)
            {
                if (voices[i].layer < 0) return i;
                // sin voces libres (no debería pasar con 6): la que lleva más tiempo apagándose
                if (i != head && i != next && voices[i].fadeStart < double.MaxValue && (best < 0 || voices[i].fadeStart < voices[best].fadeStart)) best = i;
            }
            if (best >= 0) Release(voices[best]);
            return best;
        }

        /// <summary>Apaga una capa desde 'at' en 'len' s. Curva (1-u)²: a un cuarto del fundido ya bajó 5 dB, así lo
        /// que entra entero en el tiempo fuerte no se suma a lo anterior a pleno (dos cumbres juntas pasaban de 0 dBFS).
        /// Lo agendado de esa capa que arrancaría ya apagado se cancela; lo que arranca dentro del fundido suena y se
        /// apaga con él.</summary>
        void FadeLayer(int l, double at, double len)
        {
            for (int i = 0; i < VoiceCount; i++)
            {
                var v = voices[i];
                if (v.layer != l) continue;
                if (v.start >= at + len) { Release(v); continue; }
                if (at < v.fadeStart) { v.fadeStart = at; v.fadeLen = len; }
            }
        }

        void FadeAll(double at, double len)
        {
            for (int i = 0; i < VoiceCount; i++)
            {
                var v = voices[i];
                if (v.layer < 0) continue;
                if (v.start >= at + len) { Release(v); continue; }
                if (at < v.fadeStart) { v.fadeStart = at; v.fadeLen = len; }
            }
        }

        void CancelLayer(int l)
        {
            for (int i = 0; i < VoiceCount; i++) if (voices[i].layer == l) Release(voices[i]);
        }

        bool AnyVoice()
        {
            for (int i = 0; i < VoiceCount; i++) if (voices[i].layer >= 0) return true;
            return false;
        }

        static float Envelope(Voice v, double now)
        {
            if (now <= v.fadeStart) return 1f;
            double u = (now - v.fadeStart) / System.Math.Max(1e-3, v.fadeLen);
            float k = 1f - (float)u;
            return u >= 1.0 ? 0f : k * k;
        }

        void Release(Voice v)
        {
            v.src.Stop();
            v.src.clip = null;
            v.layer = -1;
            v.clip = null;
            v.fadeStart = double.MaxValue;
        }

        void Finish(bool resume)
        {
            track = null;
            inOutro = false;
            head = next = -1;
            playing = target = 0;
            owner?.OnDirectedMusicEnded(resume);
        }

        /// <summary>Cambio de dispositivo (auriculares, HDMI): Unity reinicia el audio y corta todas las fuentes. El tema
        /// vuelve desde el loop de la fase que sonaba (sin intro).</summary>
        void OnAudioReset(bool deviceWasChanged)
        {
            if (!deviceWasChanged) return;
            for (int i = 0; i < VoiceCount; i++) if (voices[i].layer >= 0) Release(voices[i]);
            head = next = -1;
            if (track == null) return;
            if (inOutro) { Finish(track.resumeExplore); return; }
            if (silent) return;
            pendingStart = false;
            StartLayer(target, Now + Lead, false);
        }

        static AudioClip Resolve(string key)
        {
            if (key == null) return null;
            var c = Game.LoadContent();
            var e = c != null ? c.Music(key) : null;
            return e != null && e.clips != null && e.clips.Length > 0 ? e.clips[0] : null;
        }

        static float EntryVolume(string key)
        {
            var c = Game.LoadContent();
            var e = c != null ? c.Music(key) : null;
            return e != null ? e.volume : 1f;
        }
    }
}
