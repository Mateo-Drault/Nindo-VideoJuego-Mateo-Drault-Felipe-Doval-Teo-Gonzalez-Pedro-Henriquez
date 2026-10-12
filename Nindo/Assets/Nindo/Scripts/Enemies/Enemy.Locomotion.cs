using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Cómo se mueve el cuerpo del enemigo cuando camina en la pelea, aparte de la IA de Enemy.cs:
    ///  * rodeo y retroceso con su clip: rodeando a Kaito (TickStrafe) el enemigo lo mira y se mueve de costado o para
    ///    atrás, y con el blend tree de locomoción caminaba hacia adelante con los pies patinando de costado. Se elige
    ///    StrafeL / StrafeR / WalkBack por la dirección de la velocidad en su marco, con histéresis de ángulo y de
    ///    velocidad, una espera mínima entre cambios y un cruce en la misma fase del paso (los ciclos pisan con el
    ///    derecho en el cuadro 0). Sin esos estados en el controller queda el blend tree de siempre;
    ///  * los clips de variante: un golpe de zona con clip propio (Whirl, Leap, Morote) vuelve al de siempre con sus
    ///    tiempos si el controller no lo tiene (AttackClipFallback);
    ///  * el imán del golpe: si Kaito está pegado, la embestida del transform se corta (no lo atraviesa) pero el clip
    ///    la sigue contando y el pie apoyado patinaba para atrás. Hasta 'lungeSlack' metros el MODELO sigue avanzando
    ///    solo (el cuerpo visible está más adentro que la cápsula: no llega a tocar a Kaito) y esa diferencia se le
    ///    devuelve al transform en cuanto hay lugar, sin que nada se mueva en pantalla.
    /// </summary>
    public partial class Enemy
    {
        public const string StrafeLState = "StrafeL", StrafeRState = "StrafeR", WalkBackState = "WalkBack";

        enum Gait { Blend, Left, Right, Back }

        // velocidad (m/s) para entrar a un ciclo direccional y para salir (histéresis: rodeando, la velocidad oscila)
        const float GaitEnter = 0.55f, GaitExit = 0.3f;
        // medio ángulo del sector de adelante y del de atrás (°), y cuánto se agranda el sector en el que ya está
        const float GaitFwdHalf = 50f, GaitBackHalf = 45f, GaitHyst = 12f;
        // cruce entre ciclos y tiempo mínimo en uno (s): sin espera, a 45° de la velocidad cambiaba cada pocos cuadros
        const float GaitFade = 0.18f, GaitDwell = 0.22f;
        // el ritmo del ciclo sigue a la velocidad real, sin pasar de esto (más lento parece cámara lenta)
        const float GaitRateMin = 0.6f, GaitRateMax = 1.5f;

        Gait gait;
        float gaitSince = -99f;
        int gaitMask = -1;          // bits: 1 StrafeL, 2 StrafeR, 4 WalkBack (se mira una vez)
        float gaitClipSpeed;        // m/s a los que pisan los clips direccionales a velocidad 1

        // embestida que el imán cortó y el modelo siguió adelante (m, en el frente del transform)
        float lungeWarp;

        /// <summary>Corrimiento local del modelo respecto de su pose base (la embestida cortada por el imán): VariantMotion
        /// lo suma cuando escribe la posición del modelo (los saltos de zona).</summary>
        public Vector3 ModelNudge { get; private set; }

        /// <summary>Está en un ciclo de locomoción (el blend tree o el direccional que eligió): ahí VariantMotion pone su sabor.</summary>
        public bool InLocomotionPose => anim.Current == config.animLocomotion || (gait != Gait.Blend && anim.Current == GaitState(gait));

        static string GaitState(Gait g) => g == Gait.Left ? StrafeLState : g == Gait.Right ? StrafeRState : g == Gait.Back ? WalkBackState : null;

        bool HasGait(Gait g)
        {
            if (g == Gait.Blend) return true;
            if (gaitMask < 0)
            {
                // los jefes no: Kokuyō tiene sus propios StrafeL/StrafeR y los elige él (KokuyoBoss.UpdateStrafeAnim)
                gaitMask = this is Boss ? 0 : (anim.HasState(StrafeLState) ? 1 : 0) | (anim.HasState(StrafeRState) ? 2 : 0) | (anim.HasState(WalkBackState) ? 4 : 0);
                // los clips pisan a la velocidad de caminar del arquetipo (la variante la multiplica, y su modelo escalado
                // da pasos más largos): el ritmo del ciclo es la velocidad real sobre esta
                var vm = model != null ? model.GetComponent<VariantMotion>() : null;
                gaitClipSpeed = config.walkSpeed / Mathf.Max(0.1f, vm != null ? vm.moveSpeed : 1f) * Mathf.Max(0.3f, config.scale);
            }
            int bit = g == Gait.Left ? 1 : g == Gait.Right ? 2 : 4;
            return (gaitMask & bit) != 0;
        }

        /// <summary>
        /// Locomoción del cuerpo en Chase / Strafe / Idle (llamado desde Enemy.Update). Los controllers no tienen
        /// transiciones: al volver a moverse hay que reentrar a la locomoción, si no se desliza congelado en la última pose
        /// (fin de Spotted, Guard, Hit, Counter, intro de jefe...).
        /// </summary>
        void TickLocomotionAnim(float dt)
        {
            bool moving = State == EnemyState.Chase || State == EnemyState.Strafe || State == EnemyState.Idle;
            if (!moving || (Ambient != null && Ambient.HoldsPose)) { gait = Gait.Blend; return; }
            // Chase y Strafe se alternan seguido rodeando (se compromete, se aleja): el ciclo elegido sigue entre los dos
            if (stateTime <= 0.02f) return;
            Vector3 vel = useAgent ? agent.velocity.Flat() : Vector3.zero;
            float speed = vel.magnitude;
            // volviendo a su lugar sin pelea (perdió a Kaito) mira adonde camina: de espaldas al lugar caminaba para atrás
            if (State == EnemyState.Idle && !IsAggro && speed > GaitExit) Face(transform.position + vel, 1f, dt);

            // fuera del ciclo que corresponde (otro estado, o el jefe que cambió animLocomotion): de vuelta a la locomoción
            if (anim.Current != config.animLocomotion && (gait == Gait.Blend || anim.Current != GaitState(gait)))
            {
                gait = Gait.Blend;
                anim.Play(config.animLocomotion, 0.15f);
                return;
            }
            Gait want = DesiredGait(transform.InverseTransformDirection(vel), speed);
            if (want != gait && Time.time - gaitSince >= GaitDwell)
            {
                // misma fase del paso: los dos ciclos apoyan el derecho en el cuadro 0
                float phase = anim.Phase;
                gait = want;
                gaitSince = Time.time;
                if (want == Gait.Blend) anim.PlayAtPhase(config.animLocomotion, GaitFade, phase);
                else anim.PlayAtPhase(GaitState(want), GaitFade, phase, GaitRate(speed));
            }
            else if (gait != Gait.Blend) anim.SetStateSpeed(GaitRate(speed));
        }

        float GaitRate(float speed) => Mathf.Clamp(speed / Mathf.Max(0.1f, gaitClipSpeed), GaitRateMin, GaitRateMax);

        Gait DesiredGait(Vector3 local, float speed)
        {
            // corriendo (persecución) siempre el blend tree: los ciclos direccionales son de caminar
            if (speed < (gait == Gait.Blend ? GaitEnter : GaitExit) || speed > config.walkSpeed * 1.6f) return Gait.Blend;
            float ang = Mathf.Atan2(local.x, local.z) * Mathf.Rad2Deg;   // 0 adelante, + a su derecha
            if (InSector(gait, ang, GaitHyst)) return gait;
            float a = Mathf.Abs(ang);
            Gait g = a <= GaitFwdHalf ? Gait.Blend : a >= 180f - GaitBackHalf ? Gait.Back : ang > 0f ? Gait.Right : Gait.Left;
            return HasGait(g) ? g : Gait.Blend;
        }

        bool InSector(Gait g, float ang, float grow)
        {
            float a = Mathf.Abs(ang);
            switch (g)
            {
                case Gait.Blend: return a <= GaitFwdHalf + grow;
                case Gait.Back: return a >= 180f - GaitBackHalf - grow && HasGait(g);
                case Gait.Right: return ang > 0f && a > GaitFwdHalf - grow && a < 180f - GaitBackHalf + grow && HasGait(g);
                default: return ang < 0f && a > GaitFwdHalf - grow && a < 180f - GaitBackHalf + grow && HasGait(g);
            }
        }

        // ---------------------------------------------------------------- clips de variante
        /// <summary>Un golpe de zona con clip propio vuelve al estado y los tiempos de siempre si el controller no lo tiene
        /// (otra rama sin el FBX nuevo, un personaje que reusa el arquetipo). Una vez, antes de la primera pelea.</summary>
        void ResolveClipVariants()
        {
            if (config.patterns == null || !anim.Valid) return;
            foreach (var p in config.patterns)
            {
                if (p == null || p.steps == null) continue;
                foreach (var s in p.steps)
                    if (s != null && s.fallback != null && !anim.HasState(s.state)) s.fallback.ApplyTo(s);
            }
        }

        // ---------------------------------------------------------------- imán del golpe
        /// <summary>
        /// El imán cortó 'meters' de la embestida este frame y quedan 'left' por recorrer: el modelo hace solo los últimos
        /// lungeSlack metros. Ahí es donde el clip apoya el pie (el ninja cae del salto corto; el sumo arrima el de atrás)
        /// y donde se veía patinar: medido en build_team_anims (magnet_curve_cm), con 0.15 m el ninja ya no patina nada
        /// y el sumo, con 0.35, solo si Kaito no lo deja avanzar ni el 40 % de la embestida.
        /// </summary>
        void WarpLunge(float meters, float left)
        {
            float cap = config.lungeSlack * Mathf.Max(0.5f, config.scale);
            if (meters <= 0f || cap <= 0f) return;
            float within = Mathf.Clamp(cap - left, 0f, meters);
            lungeWarp = Mathf.Min(cap, lungeWarp + within);
        }

        /// <summary>Devuelve el adelanto del modelo al transform apenas hay lugar (nada se mueve en pantalla); caminando lo
        /// suelta de a poco (los pies ya se mueven y no se nota). Llamado desde Enemy.Update.</summary>
        void TickLungeWarp(float dt)
        {
            if (lungeWarp <= 0f)
            {
                if (ModelNudge != Vector3.zero) ApplyNudge(0f);
                return;
            }
            if (!IsAlive) { lungeWarp = 0f; ApplyNudge(0f); return; }
            if (target != null && !anim.Frozen)
            {
                float room = DistToTarget - Radius - target.Radius - 0.3f;
                if (room > 0.01f)
                {
                    float m = Mathf.Min(lungeWarp, room);
                    MoveBy(transform.forward * m);
                    lungeWarp -= m;
                }
            }
            if (State == EnemyState.Chase || State == EnemyState.Strafe) lungeWarp = Mathf.MoveTowards(lungeWarp, 0f, 1.2f * dt);
            ApplyNudge(lungeWarp);
        }

        void ApplyNudge(float forward)
        {
            if (model == null || model == transform) return;
            Vector3 w = transform.forward * forward;
            ModelNudge = model.parent != null ? model.parent.InverseTransformVector(w) : w;
            model.localPosition = modelBasePos + ModelNudge;
        }

        /// <summary>Vuelve a la pose base (ResetEnemy, la muerte): sin adelanto del modelo ni ciclo direccional.</summary>
        void ResetLocomotionAnim()
        {
            lungeWarp = 0f;
            ModelNudge = Vector3.zero;
            gait = Gait.Blend;
        }
    }

    /// <summary>El estado y los tiempos del clip de siempre para un golpe de zona con clip propio (EnemyArchetypes): si
    /// el controller no tiene el estado nuevo, el golpe vuelve a ese clip con sus números (los del clip, no los del golpe:
    /// el daño, el alcance y la embestida quedan).</summary>
    public class AttackClipFallback
    {
        public string state;
        public float activeStart, activeEnd, apex;

        public void ApplyTo(AttackDef a)
        {
            a.state = state;
            a.activeStart = activeStart;
            a.activeEnd = activeEnd;
            a.apex = apex;
            a.fallback = null;
        }
    }
}
