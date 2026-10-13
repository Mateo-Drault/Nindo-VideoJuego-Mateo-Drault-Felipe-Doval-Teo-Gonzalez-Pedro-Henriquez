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
        /// <summary>Loop: se encadena consigo mismo. Once: intro o frase de entrada que desemboca en el loop de su fase
        /// (su grilla de compases se cuenta desde el final, que es donde cae el compás 0 del loop), o un tema que suena
        /// una vez (el final). Outro: el cierre del tema.</summary>
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
            public double BeatSamples => bar / 4 * rate;
        }

        /// <summary>
        /// Una fase: su loop y la frase de entrada que suena una vez antes (o null). Entrando desde el silencio, la frase
        /// arranca en 'introEntry'; desde lo que suena, el director elige cuántos tiempos de ella tocar para que 'introHit'
        /// (lo que la frase anuncia: el compás de la sección o los tambores de Gorō) caiga en un compás. 'cut': fundido de
        /// lo anterior en s cuando la fase cambia de tono (0: el de siempre). 'outro': su cierre (null: el del tema).
        /// </summary>
        public sealed class Phase
        {
            public readonly string clip, intro, outro;
            public readonly int introEntry, introHit;
            public readonly float cut;
            public Phase(string clip, string intro, int introEntry, int introHit, float cut, string outro)
            {
                this.clip = clip; this.intro = intro; this.introEntry = introEntry; this.introHit = introHit;
                this.cut = cut; this.outro = outro;
            }
        }

        /// <summary>Un tema por fases. Al caer el jefe suena el cierre de la fase (o, sin toma final, el loop se funde
        /// 'outroFade' s) y, si 'resumeExplore', después vuelve la música de la zona.</summary>
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
            public string OutroAt(int n) => PhaseAt(n).outro ?? outro;
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
    /// Un cambio de fase entra en el próximo tiempo de lo que suena con la frase de entrada de la fase nueva (los compases
    /// que en el tema llevan a esa sección) y la sección cae entera en un compás de lo que sonaba, de 2 a 5 tiempos
    /// después; lo anterior baja 10 dB en 30 ms y se apaga en un tiempo. Antes de un silencio (barra falsa de Gorō,
    /// eclipse de Kokuyō) se apaga, con o sin el golpe final, y la fase siguiente entra apenas se la pide. Lo maneja
    /// AudioManager (PlayBossMusic, SetBossMusicPhase, ...).
    /// </summary>
    public class MusicDirector : MonoBehaviour
    {
        const int VoiceCount = 6;
        // PlayScheduled necesita agendarse antes de que el DSP llegue (buffers de 256-1024 muestras y el decodificador)
        const double Lead = 0.25;
        // un cambio pedido se fija recién cuando el tiempo está a menos de esto: si llega otro antes, gana el último
        const double CommitWindow = 0.5;
        // en un reintento la intro larga (16 s de koto solo en Gorō, 14 s de apertura en Mizuchi) no se repite
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
            public bool dip;
        }

        readonly Voice[] voices = new Voice[VoiceCount];
        readonly HashSet<string> introHeard = new HashSet<string>();
        AudioManager owner;
        MusicPlan.Track track;
        int layer;              // capa actual; las anteriores se están apagando
        int head = -1, next = -1;
        int playing, target;    // fase que suena y fase pedida
        // cuándo tiene que sonar lo que anuncia la frase de entrada pedida, en el reloj del DSP (-1: lo de siempre). Absoluto:
        // como segundos desde el pedido se medía desde donde arrancaba la capa (el pedido + Lead) y se redondeaba a tiempos
        // de la frase, y los tambores de Gorō caían 0.03-0.47 s (0.25 de media) después de que se pone de pie
        double targetAt = -1;
        int requestPhase, requestFrame = -1;
        bool pendingStart, silent, inOutro;
        double startAt, outroEnd;

        /// <summary>Hay un tema dirigido sonando: una pelea, su cierre o el final. La música de zona y de combate no lo pisa.</summary>
        public bool Busy => track != null;

        /// <summary>La fase pedida en este frame antes de que arranque el tema (o 'fallback').</summary>
        public int RequestedThisFrame(int fallback) => requestFrame == Time.frameCount ? Mathf.Max(fallback, requestPhase) : fallback;

        public void Init(AudioManager audio)
        {
            owner = audio;
            for (int i = 0; i < VoiceCount; i++)
            {
                var go = new GameObject("Music" + i);
                go.transform.SetParent(transform, false);
                var s = go.AddComponent<AudioSource>();
                s.playOnAwake = false; s.loop = false; s.spatialBlend = 0f; s.priority = 0; s.volume = 0f;
                // cada voz en su objeto: los fundidos (OnAudioFilterRead) son de esa fuente sola
                voices[i] = new Voice { src = s, ramp = go.AddComponent<VoiceRamp>() };
            }
            AudioSettings.OnAudioConfigurationChanged += OnAudioReset;
        }

        void OnDestroy() => AudioSettings.OnAudioConfigurationChanged -= OnAudioReset;

        /// <summary>Para probar (RunCommand): tema, fase pedida y sonando, y cada voz con su clip, posición y volumen.</summary>
        public string Describe()
        {
            var inv = System.Globalization.CultureInfo.InvariantCulture;
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
                  .Append(" capa ").Append(v.layer).Append(" en ").Append(pos.ToString("0.00", inv))
                  .Append(" s, ganancia ").Append(Envelope(v, now).ToString("0.00", inv))
                  .Append(", fuente ").Append(v.src.timeSamples).Append(" muestras");
            }
            return sb.ToString();
        }

        /// <summary>
        /// Partida nueva en la misma sesión: las intros largas vuelven a sonar enteras la primera vez. introHeard vive en el
        /// AudioManager (no se destruye entre escenas) y la primera pelea de un jefe ya oído en otra partida se salteaba
        /// su apertura (16 s de koto en Gorō, 14 s en Mizuchi, 10.8 s en Kokuyō).
        /// </summary>
        public void ForgetHeardIntros() => introHeard.Clear();

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
            FadeAll(Now, 0.3, false);
            track = t;
            // un SetBossMusicPhase del mismo frame que llegó antes (otro orden de scripts) no se pierde
            target = t.Clamp(RequestedThisFrame(1)); playing = 0;
            silent = inOutro = false;
            pendingStart = true;
            startAt = Now + Mathf.Max(0f, delay);
            targetAt = -1;
            head = next = -1;
        }

        /// <summary>'leadIn' (s): cuánto tarda en caer lo que anuncia la frase de entrada (los tambores de Gorō cuando se
        /// levanta); -1 deja el de siempre (desde lo que suena, 2 a 5 tiempos; desde el silencio, la frase de la tabla).</summary>
        public void SetPhase(int phase, float leadIn = -1f)
        {
            requestPhase = phase; requestFrame = Time.frameCount;
            if (track == null || inOutro) return;
            phase = track.Clamp(phase);
            if (silent)
            {
                // después del silencio la fase entra apenas se la pide (la misma que sonaba o una más alta), con su
                // frase de entrada, sin esperar compás: no hay nada sonando con qué alinearse. Lo que todavía suena
                // (la cola del golpe de la barra falsa) se apaga mientras entra
                target = Mathf.Max(target, phase); targetAt = leadIn >= 0f ? Now + leadIn : -1;
                FadeAll(Now + Lead, 0.4, false);
                silent = false; pendingStart = true; startAt = Now;
                return;
            }
            if (phase <= target) return;
            target = phase; targetAt = leadIn >= 0f ? Now + leadIn : -1;
        }

        /// <summary>Apaga lo que suena sin terminar el tema: la próxima SetPhase entra desde el silencio. Con
        /// 'withOutro', en el próximo tiempo suena el golpe final de la fase (la barra falsa de Gorō: "le ganaste").</summary>
        public bool Silence(float fade, bool withOutro)
        {
            if (track == null || inOutro) return false;
            if (silent) return true;
            if (!(withOutro && !pendingStart && head >= 0 && PlayOutro(Now)))
                FadeAll(Now, Mathf.Max(0.05f, fade), false);
            head = next = -1;
            silent = true; pendingStart = false; playing = 0;
            return true;
        }

        public void Stop(float fade)
        {
            if (track == null && !AnyVoice()) return;
            FadeAll(Now, Mathf.Max(0.05f, fade), false);
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
                FadeAll(now, 1.0, false);
                Finish(track.resumeExplore);
                return true;
            }
            if (!PlayOutro(now))
            {
                double b = NextBoundary(now + Lead, 0.25);
                double f = System.Math.Max(0.5, track.outroFade);
                FadeLayer(layer, b, f, false);
                outroEnd = b + f;
            }
            head = next = -1;
            inOutro = true;
            return true;
        }

        /// <summary>El cierre de la fase que suena en el próximo tiempo; lo anterior baja 10 dB en 30 ms y se apaga en un
        /// pulso. outroEnd queda en el final del cierre. false si la fase no tiene cierre o falta el clip.</summary>
        bool PlayOutro(double now)
        {
            var o = MusicPlan.FindClip(track.OutroAt(playing));
            if (o == null || Resolve(o.key) == null || head < 0) return false;
            double b = NextBoundary(now + Lead, 0.25);
            FadeLayer(layer, b, voices[head].clip.bar / 4, true);
            layer++;
            int v = Schedule(o, 0, b, true);
            outroEnd = v >= 0 ? voices[v].end : b;
            return v >= 0;
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
                // se perdieron vueltas enteras (pausa del editor, un tirón más largo que lo agendado): lo agendado ya
                // pasó y PlayScheduled en el pasado avanzaría a los saltos. El loop vuelve a entrar limpio
                if (head >= 0 && next >= 0 && now >= voices[next].end)
                {
                    CancelLayer(layer);
                    StartLayer(System.Math.Max(1, playing), now + Lead, false);
                }
                // lo que suena terminó: sigue lo agendado y se agenda la vuelta siguiente (el loop entero, desde 0)
                if (head >= 0 && now >= voices[head].end)
                {
                    head = next; next = -1;
                    if (head >= 0 && voices[head].clip.kind == MusicPlan.ClipKind.Loop)
                        next = Schedule(voices[head].clip, 0, voices[head].end, false);
                }
                // la música de la zona vuelve cuando el cierre ya se apagó (no encima del último golpe)
                if (inOutro) { if (now >= outroEnd) Finish(track.resumeExplore); }
                // un tema que suena una vez (el final) terminó: queda el silencio
                else if (!silent && !pendingStart && head < 0) Finish(track.resumeExplore);
                else if (!silent && head >= 0 && target != playing) TryCommit(now);
            }
            float vol = owner != null ? owner.MusicVolume : 1f;
            for (int i = 0; i < VoiceCount; i++)
            {
                var v = voices[i];
                if (v.layer < 0) continue;
                bool ended = now > v.end + 0.1 && i != head && i != next;
                if (Envelope(v, now) <= 0f || ended) { Release(v); continue; }
                // el fundido lo aplica VoiceRamp a la muestra; acá solo el volumen de la música (y la pausa)
                v.src.volume = vol * v.volume;
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
            double beat = h.clip.bar / 4;
            double b = NextBoundary(now + Lead, 0.25);
            if (b - now > CommitWindow) return;
            var p = track.PhaseAt(target);
            var intro = MusicPlan.FindClip(p.intro);
            if (intro != null && Resolve(intro.key) == null) intro = null;
            int entry = 0;
            if (intro != null)
            {
                int beats;
                // con lo que suena la frase sigue su grilla: lo pedido cae en el tiempo más cercano (±medio tiempo, sin
                // el atraso de antes)
                if (targetAt >= 0) beats = Mathf.Max(1, Mathf.RoundToInt((float)((targetAt - b) * intro.rate / intro.BeatSamples)));
                else
                {
                    // la sección nueva cae en un compás de lo que sonaba, de 2 a 5 tiempos después del cambio
                    double arrive = NextBoundary(b + 2 * beat - 1e-4, 1.0);
                    beats = Mathf.Max(1, (int)System.Math.Round((arrive - b) / beat));
                }
                entry = Mathf.Max(0, p.introHit - (int)System.Math.Round(beats * intro.BeatSamples));
            }
            // lo anterior: un cambio de tono se corta en 'cut' s (los dos kotos de Gorō medio tono aparte); si no, cae
            // 10 dB en 30 ms y se apaga en un tiempo
            FadeLayer(layer, b, p.cut > 0f ? p.cut : beat, p.cut <= 0f);
            layer++;
            head = next = -1;
            if (intro != null) head = Schedule(intro, entry, b, true);
            StartLoop(MusicPlan.FindClip(p.clip), b);
            playing = target; targetAt = -1;
        }

        void StartLayer(int phase, double at, bool allowIntro)
        {
            layer++;
            var p = track.PhaseAt(phase);
            var intro = allowIntro ? MusicPlan.FindClip(p.intro) : null;
            if (intro != null && phase == 1 && introHeard.Contains(track.key) && intro.Seconds > LongIntro) intro = null;
            head = next = -1;
            if (intro != null)
            {
                int entry = p.introEntry;
                if (targetAt >= 0)
                {
                    // desde el silencio no hay con qué alinearse: la frase entra donde haga falta para que lo que anuncia
                    // caiga justo en targetAt. Si falta más que lo que la frase tiene antes, arranca desde su principio
                    // más tarde; si ya pasó, desde lo anunciado
                    long lead = (long)System.Math.Round((targetAt - at) * intro.rate);
                    if (lead > p.introHit) { at += (lead - p.introHit) / (double)intro.rate; lead = p.introHit; }
                    entry = p.introHit - (int)System.Math.Max(0L, lead);
                }
                head = Schedule(intro, entry, at, true);
            }
            StartLoop(MusicPlan.FindClip(p.clip), at);
            playing = phase; targetAt = -1;
            if (phase == 1) introHeard.Add(track.key);
        }

        /// <summary>El loop de la fase: después de la frase de entrada (head) o solo desde 'at', y su vuelta siguiente.</summary>
        void StartLoop(MusicPlan.Clip loop, double at)
        {
            if (head >= 0) { next = Schedule(loop, 0, voices[head].end, false); return; }
            head = Schedule(loop, 0, at, true);
            if (head >= 0 && loop.kind == MusicPlan.ClipKind.Loop) next = Schedule(loop, 0, voices[head].end, false);
        }

        /// <summary>Próximo límite de compás (o de 'fraction' de compás) a partir de tmin en lo que suena o en lo que
        /// sigue. Los loops arrancan en un compás; las intros y frases de entrada terminan en uno.</summary>
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

        /// <summary>'cold': la toma arranca sola (fundido de 6 ms); una vuelta o el loop después de su frase de entrada
        /// siguen la onda de lo anterior y no llevan fundido (sería un hueco de 6 ms en cada costura).</summary>
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
            v.fadeStart = double.MaxValue; v.dip = false;
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

        /// <summary>Apaga una capa desde 'at' en 'len' s (curva de VoiceRamp.Gain, con la caída rápida si 'dip'). Lo
        /// agendado de esa capa que arrancaría ya apagado se cancela; lo que arranca dentro del fundido suena y se apaga
        /// con él.</summary>
        void FadeLayer(int l, double at, double len, bool dip)
        {
            for (int i = 0; i < VoiceCount; i++) if (voices[i].layer == l) FadeVoice(voices[i], at, len, dip);
        }

        void FadeAll(double at, double len, bool dip)
        {
            for (int i = 0; i < VoiceCount; i++) if (voices[i].layer >= 0) FadeVoice(voices[i], at, len, dip);
        }

        void FadeVoice(Voice v, double at, double len, bool dip)
        {
            if (v.start >= at + len) { Release(v); return; }
            // un fundido más tardío no alarga uno que ya empezó
            if (at >= v.fadeStart) return;
            v.fadeStart = at; v.fadeLen = len; v.dip = dip;
            v.ramp.FadeOut(at, len, dip);
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

        static float Envelope(Voice v, double now) => VoiceRamp.Gain(now, v.fadeStart, v.fadeLen, v.dip);

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
            inOutro = silent = pendingStart = false;
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
            StartLayer(System.Math.Max(1, target), Now + Lead, false);
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
