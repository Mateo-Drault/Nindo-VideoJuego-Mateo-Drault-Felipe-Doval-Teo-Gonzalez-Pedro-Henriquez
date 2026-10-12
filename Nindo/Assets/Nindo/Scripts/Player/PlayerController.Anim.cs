using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Kaito: qué clip toca según la situación y el paso de la locomoción (clips de Tools/Blender/anim/kaito/kaito_clips.py):
    ///  * HitFrom: el golpe liviano según de dónde viene (HitBack / HitLeft / HitRight; de frente, Hit).
    ///  * TryRunStop: la frenada al soltar el stick corriendo; StartGesture: el resto de un clip como gesto que se corta
    ///    (la frenada, la vuelta a la guardia después del zanshin del remate y de las habilidades).
    ///  * LocomotionCadence: el blend tree mezcla quieto / camina / trota / corre por Speed y Unity le da el largo
    ///    promedio de los clips mezclados; entre dos umbrales la zancada mezclada no coincide con lo que avanza Kaito y
    ///    el pie apoyado patinaba (60 % entre quieto y caminar, 6 % entre caminar y trotar). Se corrige la velocidad del
    ///    Animator para que el suelo que recorre el pie apoyado sea el que recorre el personaje, y GaitSpeed elige el
    ///    Speed por zonas para no quedarse en las mezclas que patinan igual.
    ///  * RiposteReady: la réplica del parry sale a tiempo (el desviado todavía aturdido) y con el desvío ya en la carga
    ///    del Corte 1 (sin salto de pose).
    /// </summary>
    public partial class PlayerController
    {
        // =============================================================== golpes según de dónde vienen
        // grados respecto de hacia dónde mira: hasta 50 es de frente, desde 130 de atrás, en el medio de un costado
        const float HitFrontAngle = 50f, HitBackAngle = 130f;

        /// <summary>
        /// Clip del golpe liviano que llega en 'dir' (plano, del atacante hacia Kaito). Los de costado y de atrás no lo
        /// dan vuelta (antes todos los golpes se veían de frente); sin esos clips, "Hit".
        /// </summary>
        string HitFrom(Vector3 dir)
        {
            Vector3 from = transform.InverseTransformDirection(-dir);
            float a = Mathf.Atan2(from.x, from.z) * Mathf.Rad2Deg;      // 0 = adelante, + = a su derecha
            string s = Mathf.Abs(a) <= HitFrontAngle ? "Hit" : Mathf.Abs(a) >= HitBackAngle ? "HitBack" : a > 0f ? "HitRight" : "HitLeft";
            return s == "Hit" || anim.HasState(s) ? s : "Hit";
        }

        // =============================================================== frenada
        // Cuatro frenadas autoradas con el frenado del juego desde la carrera (config.acceleration 40 m/s²: de 6.2 m/s a 0
        // en 0.155 s y 0.48 m, que el clip descuenta de los pies): RunStop y RunStopReach clavan el talón derecho, RunStopL
        // y RunStopLReach el izquierdo. Cada una arranca en un cuadro de Run (RunStopPhases: kaitooo.fbx.json, timing
        // 'run_phase'), una cada 0.1 s del ciclo, y sigue la carrera hasta que apoya ('lead'). Al confirmar que soltó, si la
        // carrera pasó hace poco la fase de una (lo que esa frenada todavía sigue a la carrera: RunStopLead) arranca ya,
        // metida en su tramo de carrera; si no, Kaito sigue corriendo (sin frenar) hasta la fase de la próxima, como mucho
        // 0.08 s del ciclo. Así el fundido mezcla dos poses que se mueven igual (con dos frenadas elegidas por la más
        // cercana, a mitad de camino las piernas quedaban 45-124° separadas en el fundido; simulado sobre el FBX en las 48
        // fases: 8° como mucho al cambiar y ningún cuadro del fundido gira más que la carrera sola). Se arranca en el cuadro
        // en que el frenado autorado va a la velocidad que trae: con el stick a medias o ya frenando el pie clavado no
        // patina. Solo corriendo hacia donde mira y sin fijar (con un objetivo fijado se mueve de costado y el clip frena
        // hacia adelante)
        const float RunStopMinSpeed = 4.5f, RunStopAlign = 0.96f, RunStopAuthoredSpeed = 6.2f, RunStopMaxSkip = 0.15f;
        // soltar = el stick quieto RunStopDebounce s (al dar vuelta con el teclado hay un cuadro vacío: la frenada arrancaba
        // y se cortaba al cuadro siguiente); vale haber corrido rápido hasta RunStopMemory s antes (lo que tarda en soltar).
        // RunStopMaxWait: a la cadencia más lenta de la carrera (x0.73 a 4.5 m/s) 0.1 s del ciclo son 0.14 s
        const float RunStopDebounce = 0.04f, RunStopMemory = 0.1f, RunStopFade = 0.1f, RunStopMaxWait = 0.16f;
        const string RunStopState = "RunStop";
        static readonly string[] RunStopStates = { "RunStop", "RunStopL", "RunStopReach", "RunStopLReach" };
        static readonly float[] RunStopPhases = { 8f / 24f, 20f / 24f, 2f / 24f, 14f / 24f };
        // segundos del principio de cada frenada que todavía son la carrera (kaito_clips: 'lead' 2 y 3 cuadros, el último
        // ya es el apoyo)
        static readonly float[] RunStopLead = { 1f / 30f, 1f / 30f, 2f / 30f, 2f / 30f };
        float fastRunUntil = -9f, stickReleasedAt = -9f, runStopWaitFrom, runStopPrevPhase;
        int runStopWaitFrame = -9;

        bool InRunStop => gestureState != null && gestureState.StartsWith(RunStopState);
        // esperando la fase de la próxima frenada (TickLocomotion no frena mientras tanto); vence solo si no se pidió este
        // cuadro o el anterior (un ataque o un golpe en el medio la cortan)
        bool RunStopWaiting => runStopWaitFrame >= Time.frameCount - 1;

        /// <summary>Si soltó el stick corriendo, arranca la frenada como un gesto (el stick o un ataque la cortan).</summary>
        bool TryRunStop(Vector3 wish)
        {
            float v = velocity.magnitude;
            bool waiting = RunStopWaiting;
            runStopWaitFrame = -9;
            if (!waiting) runStopWaitFrom = -1f;
            if (v >= RunStopMinSpeed && Vector3.Dot(velocity, transform.forward) >= RunStopAlign * v) fastRunUntil = Time.time + RunStopMemory;
            if (wish.sqrMagnitude > 0.01f) { stickReleasedAt = -9f; return false; }
            if (stickReleasedAt < 0f) stickReleasedAt = Time.time;
            if (!waiting && Time.time > fastRunUntil) return false;
            if (lockTarget != null || anim.Current != "Locomotion" || !IsGrounded || v < 0.5f || !anim.HasState(RunStopState)) return false;
            // mientras confirma que soltó también sigue a la velocidad que traía: frenando esos 0.04 s (dos cuadros a 30 fps)
            // la frenada arrancaba a 3.5 m/s, ya pasado el apoyo, y la fase que sigue a la carrera no se llegaba a ver
            runStopWaitFrame = Time.frameCount;
            if (Time.time - stickReleasedAt < RunStopDebounce) return false;
            float skip = Mathf.Clamp((RunStopAuthoredSpeed - v) / Mathf.Max(1f, config.acceleration), 0f, RunStopMaxSkip);
            string state = RunStopState;
            float offset = skip;
            // el blend tree sincroniza los ciclos: su tiempo normalizado es la fase de Run. La frenada i arrancada en 'skip'
            // sigue a la carrera cuando esta va por RunStopPhases[i] + skip / runLen; se toma la última que la carrera pasó
            // (desde el cuadro anterior, o hace tan poco que la frenada todavía sigue a la carrera) y se entra lo que pasó
            if (anim.TryNormalizedTime("Locomotion", out float n))
            {
                float runLen = anim.Length("Run", LocoFallbackLength[3]);
                float ph = n - Mathf.Floor(n);
                if (runStopWaitFrom < 0f) { runStopWaitFrom = Time.time; runStopPrevPhase = ph - 1f / 24f; }
                float stepped = Mathf.Repeat(ph - runStopPrevPhase, 1f);
                int best = -1, near = 0;
                float bestD = 2f, nearD = 2f;
                for (int i = 0; i < RunStopStates.Length; i++)
                {
                    if (!anim.HasState(RunStopStates[i])) continue;
                    float d = Mathf.Repeat(ph - RunStopPhases[i] - skip / runLen, 1f);
                    if ((d <= stepped || skip + d * runLen <= RunStopLead[i]) && d < bestD) { best = i; bestD = d; }
                    float e = Mathf.Min(d, 1f - d);
                    if (e < nearD) { near = i; nearD = e; }
                }
                if (best < 0 && Time.time - runStopWaitFrom < RunStopMaxWait)
                {
                    runStopPrevPhase = ph;
                    return false;
                }
                // (si se pasó del tope sin cruzar ninguna, p. ej. con la carrera frenada por una pared: la más cercana)
                if (best < 0) { best = near; bestD = 0f; }
                state = RunStopStates[best];
                offset = skip + bestD * runLen;
            }
            fastRunUntil = -9f;
            runStopWaitFrame = -9;
            float len = anim.Length(state, 0.5333f);
            anim.Play(state, RunStopFade, offset / len);
            StartGesture(state, len - offset);
            // el clip frena derecho hacia adelante, a la velocidad que lleva el cuadro en que arranca
            velocity = transform.forward * Mathf.Min(v, Mathf.Max(0f, RunStopAuthoredSpeed - config.acceleration * offset));
            return true;
        }

        /// <summary>
        /// El clip que ya está tocando 'state' sigue 'seconds' más como un gesto de Locomotion (TickLocomotion): quieto hasta
        /// que termina; el stick o una acción de combate lo cortan.
        /// </summary>
        void StartGesture(string state, float seconds)
        {
            gestureState = state;
            gestureUntil = Time.time + seconds;
        }

        // =============================================================== cadencia de la locomoción
        // umbrales del blend tree = velocidad a la que se autoró cada ciclo / runSpeed (generate_assets.py, kaito_clips.py
        // WALK_MPS / JOG_MPS / RUN_MPS); el largo de cada ciclo sale de NindoContent (kaitooo.fbx.json, 'seconds')
        static readonly string[] LocoClips = { "Idle", "Walk", "Jog", "Run" };
        static readonly float[] LocoSpeeds = { 0f, 1.2f, 3.4f, 6.2f };
        static readonly float[] LocoFallbackLength = { 2.4f, 0.6f, 0.4667f, 0.4f };
        // fuera de esto el ciclo se ve acelerado o en cámara lenta: mejor un resto de patinada que un paso ridículo
        const float CadenceMin = 0.5f, CadenceMax = 2f;
        float[] locoLength;

        /// <summary>Velocidad del Animator para que la locomoción mezclada avance 'speed' m/s sin patinar.</summary>
        float LocomotionCadence(float speed)
        {
            if (locoLength == null)
            {
                locoLength = new float[LocoClips.Length];
                for (int i = 0; i < LocoClips.Length; i++) locoLength[i] = anim.Length(LocoClips[i], LocoFallbackLength[i]);
            }
            // el Speed amortiguado que usa el blend tree, en m/s (cada umbral es la velocidad de su ciclo)
            float p = anim.LocomotionParam * config.runSpeed;
            int k = 0;
            while (k < LocoSpeeds.Length - 2 && p > LocoSpeeds[k + 1]) k++;
            float w = Mathf.Clamp01((p - LocoSpeeds[k]) / (LocoSpeeds[k + 1] - LocoSpeeds[k]));
            // Unity: el largo mezclado es el promedio de los largos; la zancada del pie apoyado, la de cada ciclo pesada
            float length = Mathf.Lerp(locoLength[k], locoLength[k + 1], w);
            float stride = Mathf.Lerp(LocoSpeeds[k] * locoLength[k], LocoSpeeds[k + 1] * locoLength[k + 1], w);
            float ground = stride / Mathf.Max(0.01f, length);
            if (ground < 0.05f) return 1f;          // quieto: el Idle respira a su ritmo
            return Mathf.Clamp(speed / ground, CadenceMin, CadenceMax);
        }

        /// <summary>En Locomotion la velocidad del Animator es la cadencia (la furia no acelera los pasos: patinaban).</summary>
        void ApplyLocomotionCadence()
        {
            anim.SetSpeed(anim.Current == "Locomotion" ? LocomotionCadence(velocity.magnitude) : 1f);
        }

        // Speed del blend tree por zonas. Aun con la cadencia corregida, las mezclas de dos ciclos con apoyos muy distintos
        // patinan: la caminata apoya el 60 % del ciclo, el trote el 30 % y la carrera el 17 %, y con poco de uno el pie
        // mezclado se arrastra (simulación con los pies horneados, Tools/Blender/anim/kaito: 11 cm por ciclo a 1.6 m/s,
        // 3.9 a 4.4 m/s). Cada ciclo cubre su zona acelerado o frenado por la cadencia y entre zonas se pasa a una mezcla
        // pareja (lo que tarda la amortiguación del Animator); con eso queda en 0.6-1.8 cm por ciclo a cualquier
        // velocidad (antes 36 cm entre quieto y caminar). Histéresis para no ir y venir en el borde. La caminata pura llega
        // hasta 1.7 m/s (cadencia x1.42 como mucho: hasta 2.1 m/s llegaba a x1.75, un pasito apurado que se notaba con el
        // stick a medias); de 1.7 a 2.1 la mezcla con el trote va a x0.75-0.93 y patina 0.6-0.7 cm por ciclo (sim_gait)
        static readonly float[] GaitUp = { 1.7f, 4.4f }, GaitDown = { 1.5f, 4.2f };
        int gaitZone;

        /// <summary>Speed (m/s, antes de dividir por runSpeed) que se le pasa al blend tree para ir a 'v' m/s.</summary>
        float GaitSpeed(float v)
        {
            if (v < 0.05f) { gaitZone = 0; return 0f; }
            while (gaitZone < GaitUp.Length && v >= GaitUp[gaitZone]) gaitZone++;
            while (gaitZone > 0 && v < GaitDown[gaitZone - 1]) gaitZone--;
            switch (gaitZone)
            {
                case 0: return Mathf.Min(LocoSpeeds[1], 2f * v);        // camina (y de quieto a caminar, mezclado)
                case 1: return Mathf.Clamp(v, 2.4f, 3.5f);              // trota, con algo de caminata abajo
                default: return Mathf.Max(4.6f, v);                    // corre, con algo de trote abajo
            }
        }

        // =============================================================== réplica del parry
        // Los desvíos llegan a la carga del Corte 1 (COUNTER = Attack1 f2, donde arranca la réplica) en su cuadro
        // 'counter_ready' (kaitooo.fbx.json; kaito_clips.CHAINS lo mide contra la carga). La réplica es la recompensa del
        // parry: tiene que pegar con el desviado todavía aturdido (Enemy.parriedRecoil 0.32 s; el Corte 1 desde la carga
        // pega a los 0.08 s), así que arranca a lo sumo a los RiposteBy s del desvío (antes de los 0.06 s no: el choque),
        // en el perfecto igual que en el normal. Mientras está pedida, el desvío corre hacia la carga lo justo para llegar a
        // tiempo (sin su quieto autorado: el código ya pone el hit-stop); si igual no llegó, el fundido es más largo. Antes
        // salía desde el primer cuadro del desvío y el fundido saltaba de pose (100° el brazo en el perfecto), y después
        // esperaba la carga a velocidad de clip: pegaba recién cuando el desviado ya se recuperaba
        bool ripostePending;
        float riposteFade;
        const float RiposteMin = 0.06f, RiposteBy = 0.11f, RiposteRushMax = 4f, RiposteFade = 0.06f, RiposteLateFade = 0.1f;
        const float ParryReadyN = 5f / 12f, PerfectReadyN = 8f / 14f;

        /// <summary>¿Sale ya la réplica pedida? (y con qué fundido)</summary>
        bool RiposteReady(out float fade)
        {
            fade = RiposteFade;
            string s = anim.Current;
            if (!anim.TryNormalizedTime(s, out float n)) { fade = RiposteLateFade; return stateTime >= RiposteBy; }
            float ready = s == "PerfectParry" ? PerfectReadyN : ParryReadyN;
            if (n >= ready) return stateTime >= RiposteMin;
            float time = RiposteBy - stateTime;
            if (time <= 0f) { fade = RiposteLateFade; return true; }
            anim.SetSpeed(Mathf.Clamp((ready - n) * anim.Length(s, 0.4f) / time, 1f, RiposteRushMax));
            return false;
        }
    }
}
