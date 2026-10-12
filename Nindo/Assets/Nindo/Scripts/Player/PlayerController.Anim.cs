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
        // RunStop (clava el talón derecho) y RunStopL (el izquierdo) están autorados con el frenado del juego desde la
        // carrera (config.acceleration 40 m/s²: de 6.2 m/s a 0 en 0.155 s y 0.48 m, que el clip descuenta de los pies) y
        // su primer cuadro es un cuadro de Run (fase RunStopPhase*: kaitooo.fbx.json, timing 'run_phase'). Se elige el que
        // sigue la fase en que va la carrera (con uno solo, la mitad de las veces las piernas se cruzaban en el fundido)
        // y se arranca en el cuadro en que el frenado autorado va a la velocidad que trae: con el stick a medias o ya
        // frenando, el pie clavado no patina (antes 4-12 cm por debajo de 6.2 m/s). Solo corriendo hacia donde mira y sin
        // fijar (con un objetivo fijado se mueve de costado y el clip frena hacia adelante)
        const float RunStopMinSpeed = 4.5f, RunStopAlign = 0.96f, RunStopAuthoredSpeed = 6.2f, RunStopMaxSkip = 0.15f;
        // soltar = el stick quieto RunStopDebounce s (al dar vuelta con el teclado hay un cuadro vacío: la frenada arrancaba
        // y se cortaba al cuadro siguiente); vale haber corrido rápido hasta RunStopMemory s antes (lo que tarda en soltar)
        const float RunStopDebounce = 0.04f, RunStopMemory = 0.1f, RunStopFade = 0.1f;
        const float RunStopPhaseR = 8f / 24f, RunStopPhaseL = 20f / 24f;
        const string RunStopState = "RunStop", RunStopLState = "RunStopL";
        float fastRunUntil = -9f, stickReleasedAt = -9f;

        bool InRunStop => gestureState == RunStopState || gestureState == RunStopLState;

        /// <summary>Si soltó el stick corriendo, arranca la frenada como un gesto (el stick o un ataque la cortan).</summary>
        bool TryRunStop(Vector3 wish)
        {
            float v = velocity.magnitude;
            if (v >= RunStopMinSpeed && Vector3.Dot(velocity, transform.forward) >= RunStopAlign * v) fastRunUntil = Time.time + RunStopMemory;
            if (wish.sqrMagnitude > 0.01f) { stickReleasedAt = -9f; return false; }
            if (stickReleasedAt < 0f) stickReleasedAt = Time.time;
            if (Time.time - stickReleasedAt < RunStopDebounce || Time.time > fastRunUntil) return false;
            if (lockTarget != null || anim.Current != "Locomotion" || !IsGrounded || v < 0.5f || !anim.HasState(RunStopState)) return false;
            fastRunUntil = -9f;
            float skip = Mathf.Clamp((RunStopAuthoredSpeed - v) / Mathf.Max(1f, config.acceleration), 0f, RunStopMaxSkip);
            // fase de la carrera en el primer cuadro que se va a ver de cada frenada (el blend tree sincroniza los ciclos:
            // su tiempo normalizado es la fase de Run)
            string state = RunStopState;
            if (anim.HasState(RunStopLState) && anim.TryNormalizedTime("Locomotion", out float n))
            {
                float runLen = anim.Length("Run", LocoFallbackLength[3]);
                float ph = n - Mathf.Floor(n) - skip / runLen;
                float eR = Mathf.Abs(Mathf.Repeat(ph - RunStopPhaseR + 0.5f, 1f) - 0.5f);
                float eL = Mathf.Abs(Mathf.Repeat(ph - RunStopPhaseL + 0.5f, 1f) - 0.5f);
                if (eL < eR) state = RunStopLState;
            }
            float len = anim.Length(state, 0.5333f);
            anim.Play(state, RunStopFade, skip / len);
            StartGesture(state, len - skip);
            // el clip frena derecho hacia adelante
            velocity = transform.forward * v;
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
