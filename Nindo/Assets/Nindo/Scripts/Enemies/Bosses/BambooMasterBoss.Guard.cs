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
