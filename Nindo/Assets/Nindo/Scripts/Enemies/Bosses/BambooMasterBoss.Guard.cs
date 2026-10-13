using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Chikuō entre golpe y golpe: cuándo se cubre y cómo sale de la guardia. Fuera de sus huecos los cortes no le entran
    /// (Bounce): lo que hace que eso no se sienta una pared es que se vea venir (la guardia de la grulla arriba) y que
    /// siempre tenga respuesta (el manotazo y su combo enseguida).
    ///  * Después de un contraataque de Kaito se toma su descanso (ReceiveHit) y lo pasa en la guardia (RestGuard):
    ///    rondando, cada toque suelto de ese rato era otro desvío (~3 por contraataque contra el bot "bueno").
    ///  * La guardia que termina cuando ya le toca atacar sale directo con el golpe (AnswerFromGuard): con un cuadro
    ///    rondando en el medio, el corte que Kaito largaba al ver bajar la guardia le caía encima del aviso.
    ///  * El manotazo le sale al encuentro al corte (ReadCut): la palma encuentra la hoja en el contacto.
    /// Con las dos cosas, contra el bot "bueno" los cortes que no entran bajan de 52 a ~30 por minuto (Tools/Dev/sim_bamboo_master.py).
    /// </summary>
    public partial class BambooMasterBoss
    {
        // hasta cuándo descansa después de un contraataque de Kaito (el desvío que contesta no lo acorta)
        float restUntil = -1f;

        /// <summary>Lo que tiene que sobrar del descanso para que valga cubrirse (si no, sale a rondar y ataca).</summary>
        const float RestGuardMin = 0.3f;

        /// <summary>Le entró el contraataque y ya se le acabó al jugador: se cubre hasta que vuelve a atacar.</summary>
        void RestGuard()
        {
            if (!Fighting || transition != null || target == null) return;
            if (State != EnemyState.Chase && State != EnemyState.Strafe && State != EnemyState.Idle) return;
            if (Time.time > restUntil - RestGuardMin || RiposteOpen) return;
            ReleaseToken();
            EnterGuard();
            stateDuration = restUntil - Time.time;
        }

        // cuándo salió el manotazo al encuentro de un corte (ReadCut): Bounce no lo vuelve a tocar y lo da por usado (el
        // segundo corte del combo arranca 0.1 s después del primer contacto y tiene que poder leerse)
        float swatReadAt = -9f;

        /// <summary>Lo que tarda la palma (o el bastón) de GuardHit en llegar a la hoja (el encuentro, f3 del clip).</summary>
        const float SwatLead = 0.1f;
        /// <summary>Desde dónde le llega un corte de Kaito (el avance del corte más su alcance, de centro a centro), cuánto de
        /// frente tiene que venir (grados) y cuánto vale la lectura si el corte no llega (si llega, Bounce la usa).</summary>
        const float SwatReadRange = 3.4f, SwatReadArc = 60f, SwatReadKeep = 0.25f;

        /// <summary>
        /// Le sale al encuentro al corte de Kaito: con la hoja a SwatLead s del contacto arranca el manotazo del lado por
        /// donde viene, así la palma encuentra la hoja en el contacto y la acompaña. Antes salía recién con el golpe: la mano
        /// alzada no llegaba nunca a la hoja (que a esa altura ya cruzaba a la altura del muslo) y se leía como un tic más el
        /// trazo de jade. Solo parado y donde ese corte se apartaría (Bounces); si el corte no llega, igual lo leyó.
        /// </summary>
        void ReadCut()
        {
            if (!Fighting || transition != null || stance || target == null || Time.time - swatReadAt < SwatReadKeep) return;
            if (State != EnemyState.Guard && State != EnemyState.Chase && State != EnemyState.Strafe && State != EnemyState.Idle) return;
            if (target.CutEta > SwatLead || !Bounces()) return;
            Vector3 to = (transform.position - target.transform.position).Flat();
            if (to.magnitude > SwatReadRange || Vector3.Angle(target.transform.forward.Flat(), to) > SwatReadArc) return;
            swatReadAt = Time.time;
            bool guarding = State == EnemyState.Guard;
            if (!guarding) { ReleaseToken(); EnterGuard(); }
            transform.rotation = Quaternion.LookRotation(-to.normalized + transform.forward * 0.001f);
            PlaySwat(CutGoesLeft(target.CutName), guarding);
        }

        /// <summary>GuardHit (o GuardHitL para el revés) desde la guardia; desde la pose de la locomoción el fundido de 0.03 s
        /// cruzaba el brazo en un cuadro.</summary>
        void PlaySwat(bool left, bool guarding) =>
            anim.Play(left && anim.HasState(guardHitLName) ? guardHitLName : guardHitName, guarding ? 0.03f : 0.08f);

        /// <summary>¿El manotazo de este corte ya salió a su encuentro? (ReadCut)</summary>
        bool SwatRead => Time.time - swatReadAt < SwatReadKeep;

        /// <summary>
        /// La guardia termina y ya le toca atacar: sale con el golpe en el mismo cuadro (como el contragolpe sale de
        /// Counter), si el patrón que elige le entra desde donde está. Si Kaito se alejó, Enemy lo pone a rondar.
        /// </summary>
        void AnswerFromGuard()
        {
            if (!Fighting || transition != null || stance || State != EnemyState.Guard || target == null) return;
            if (stateTime + Time.deltaTime < stateDuration || Time.time < nextAttackTime) return;
            float d = DistToTarget;
            if (!PickPattern(d, out var p) || d > p.maxRange) return;
            if (Game.Combat == null || !Game.Combat.RequestAttackToken(this)) return;
            pattern = p;
            StartAttack(false);
        }
    }
}
