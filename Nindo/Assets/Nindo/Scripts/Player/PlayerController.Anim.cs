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
    ///  * RiposteReady: la réplica del parry sale cuando el desvío ya llegó a la carga del Corte 1 (sin salto de pose).
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
        // RunStop está autorado con el frenado del juego desde la carrera (config.acceleration 40 m/s²: de 6.2 m/s a 0 en
        // 0.155 s y 0.48 m, que el clip descuenta de los pies). Solo cuando corre hacia donde mira y sin fijar: con un
        // objetivo fijado se mueve de costado y el clip frena hacia adelante
        const float RunStopMinSpeed = 4.5f, RunStopAlign = 0.8f;
        const string RunStopState = "RunStop";

        /// <summary>Si soltó el stick corriendo, arranca la frenada como un gesto (el stick o un ataque la cortan).</summary>
        bool TryRunStop(Vector3 wish)
        {
            if (wish.sqrMagnitude > 0.01f || lockTarget != null || anim.Current != "Locomotion") return false;
            float v = velocity.magnitude;
            if (v < RunStopMinSpeed || Vector3.Dot(velocity / v, transform.forward) < RunStopAlign || !anim.HasState(RunStopState)) return false;
            anim.Play(RunStopState, 0.08f);
            StartGesture(RunStopState, anim.Length(RunStopState));
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
        // velocidad (antes 36 cm entre quieto y caminar). Histéresis para no ir y venir en el borde
        static readonly float[] GaitUp = { 2.1f, 4.4f }, GaitDown = { 1.9f, 4.2f };
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
        // los desvíos terminan en la carga del Corte 1 (COUNTER = Attack1 f2, donde arranca la réplica). Antes la réplica
        // salía a los 0.06 s, desde el desvío, y el fundido saltaba de pose (100° el brazo en el perfecto, que pasa por
        // una guardia agazapada). Ahora queda pedida y sale cuando el desvío llega a la carga (kaitooo.fbx.json y
        // kaito_clips.CHAINS: f7 de 12 en ParrySuccessR/L, a 10° de la carga; f13 de 14 en PerfectParry, a 8°); para que
        // no se sienta lenta, pasado su quieto (el hit-stop autorado: f3 / f4) el desvío se toca más rápido hasta ahí
        bool ripostePending;
        const float RiposteFade = 0.06f, RiposteRush = 2.5f;

        bool RiposteReady()
        {
            string s = anim.Current;
            bool perfect = s == "PerfectParry";
            float ready = perfect ? 13f / 14f : 7f / 12f, hold = perfect ? 4f / 14f : 3f / 12f;
            if (anim.TryNormalizedTime(s, out float n))
            {
                if (n >= hold) anim.SetSpeed(RiposteRush);
                return n >= ready;
            }
            return stateTime >= (perfect ? 0.36f : 0.22f);
        }
    }
}
