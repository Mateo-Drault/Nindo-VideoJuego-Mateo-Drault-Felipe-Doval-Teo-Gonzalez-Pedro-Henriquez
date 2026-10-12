using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// La onda de qi (y en la fase 3 la raíz del bambú: el bastón clavado en el piso). Junta el qi en el vientre (Gather),
    /// pisa y empuja con las palmas (QiRelease) y un aro rojo se abre por el piso desde el borde de su cuerpo a
    /// QiSpeed m/s hasta QiRadius. Pega una sola vez, en el frame en que Kaito pasa de afuera a adentro del frente: el
    /// dash cuando llega el aro lo cruza; afuera del disco no pasa nada. El aviso cuenta hasta que el frente llega a
    /// Kaito (y se deshace si ya no lo va a alcanzar): "¡ya!" y anillo nunca mienten. Es la onda del shiko del sumo de
    /// antes (ShockRing), con su misma lógica de cruce.
    /// </summary>
    public partial class BambooMasterBoss
    {
        bool qiLive, qiHit, qiOwnedByStep, qiGathered, qiPending;
        Vector3 qiCenter;
        float qiR, qiMax, qiPrev;   // qiPrev: distancia de Kaito al centro el frame anterior (para el cruce)
        AttackDef qiAttack;
        ShockRing qiRing;

        float QiStart => Radius + 0.6f;
        float QiSpeedNow => BambooMasterMoves.QiSpeed[Mathf.Clamp(phaseIdx, 0, 2)];

        void BeginQiStep(AttackDef a)
        {
            // la fase activa del clip dura lo que tarda la onda en abrirse: el paso (y el aviso) sigue vivo hasta que la
            // onda pasa por donde está Kaito
            tl.sustain = Mathf.Max(0.1f, (a.specialParam - QiStart) / QiSpeedNow);
            qiOwnedByStep = false;
            qiGathered = false;
        }

        float QiTravel(AttackDef a) => target == null ? 0f : Mathf.Clamp(DistToTarget - QiStart, 0f, a.specialParam) / QiSpeedNow;

        /// <summary>Lo que falta para soltarla más el viaje del frente. Antes de soltarla nunca es infinito (afuera del
        /// disco cuenta hasta el borde: puede volver a entrar); después, infinito si Kaito quedó afuera o ya pegó.</summary>
        float QiEta(AttackDef a)
        {
            if (qiPending) return 0f;   // el frente ya lo tocó: pega en el próximo cuadro (ver ResolveQiHit)
            if (target == null || stepHit) return float.PositiveInfinity;
            if (!specialFired)
            {
                float d = Mathf.Min(CombatMath.FlatDistance(target.transform.position, transform.position), a.specialParam);
                return Mathf.Max(0f, tl.T - stepClock) + Mathf.Max(0f, d - QiStart) / QiSpeedNow;
            }
            if (!qiLive || qiHit || !qiOwnedByStep) return float.PositiveInfinity;
            float dw = CombatMath.FlatDistance(target.transform.position, qiCenter);
            if (dw > qiMax) return float.PositiveInfinity;
            return Mathf.Max(0f, dw - qiR) / QiSpeedNow;
        }

        void TickQiStep(AttackDef a)
        {
            // el qi se junta en el vientre: un respiro de luz jade en las manos y el zumbido de la carga
            if (!qiGathered && clip != null && stepNorm >= Mathf.Max(0f, clip.Event("Gather")))
            {
                qiGathered = true;
                Game.Audio?.Play("ability_charge", transform.position, 0.7f, 0.05f);
                Game.FX?.FlashLight(AimPoint, BambooMasterLook.Jade, 2.2f, 4f, 0.6f);
            }
            if (!specialFired && stepNorm >= a.activeStart)
            {
                specialFired = true;
                ReleaseQi(a);
            }
            // ya no lo va a alcanzar: el aviso se deshace sin destello y la onda queda desarmada (sin aviso no hay golpe)
            if (specialFired && !qiHit && float.IsInfinity(QiEta(a)))
            {
                EndTell(TellOutcome.Cancelled);
                qiHit = true;
            }
        }

        void ReleaseQi(AttackDef a)
        {
            Vector3 c = transform.position;
            Game.FX?.Shockwave(c, 3f, BambooMasterLook.Jade);
            Game.FX?.GroundCrack(c, phaseIdx >= 2 ? 2.4f : 1.6f);
            Game.Camera?.Shake(0.6f);
            Game.Audio?.Play("slam", c, 0.9f);
            Game.Audio?.Play("wave", c, 0.8f, 0.05f);
            Game.Input?.Rumble(0.8f, 0.5f, 0.3f);
            qiLive = true; qiHit = false; qiOwnedByStep = true;
            qiCenter = c; qiR = 0f; qiMax = a.specialParam; qiAttack = a;
            qiPrev = target != null ? CombatMath.FlatDistance(target.transform.position, c) : float.PositiveInfinity;
            if (qiRing == null) qiRing = ShockRing.Create();
            qiRing.Show(c);
        }

        void TickQiWave(float dt)
        {
            if (!qiLive) return;
            float prev = qiR;
            // el primer frame cubre de golpe hasta el borde del cuerpo (a quemarropa, el empuje mismo)
            qiR = prev <= 0f ? QiStart : Mathf.Min(qiMax, qiR + QiSpeedNow * dt);
            if (!qiHit && target != null && target.IsAlive && IsAlive)
            {
                // un solo golpe por onda, en el frame en que Kaito pasa de afuera a adentro del frente; se compara contra
                // dónde estaba él el frame anterior (corriendo hacia el centro salteaba la franja de un frame). Solo pega
                // con su aviso vivo: un cambio de fase o un aviso cortado la desarman
                float d = CombatMath.FlatDistance(target.transform.position, qiCenter);
                if ((prev <= 0f || qiPrev > prev) && d <= qiR)
                {
                    qiHit = true;
                    qiPending = qiOwnedByStep && InTell;
                }
                qiPrev = d;
            }
            if (qiRing != null) qiRing.Tick(qiR, qiMax);
            if (qiR >= qiMax - 1e-3f) ClearQiWave(false);
        }

        /// <summary>
        /// El golpe de la onda sale un cuadro después de que el frente cruza a Kaito. El que hace dash HACIA el centro (sin
        /// stick el dash sale hacia adelante) cruzaba el frente en el primer cuadro del dash, antes de los i-frames (0.02 s):
        /// el bot "bueno" se comía el 28 % de las ondas contra el ~16 % de cualquier otro golpe. Un cuadro después ya está
        /// en los i-frames si apretó a tiempo, y al que no hizo nada le pega igual (16 ms no se ven). Corre antes que
        /// Enemy.Update para que el aviso siga vivo hasta el golpe.
        /// </summary>
        void ResolveQiHit()
        {
            if (!qiPending) return;
            qiPending = false;
            if (target != null && target.IsAlive && IsAlive && qiOwnedByStep && InTell) HitPlayer(qiAttack, qiCenter);
        }

        void ClearQiWave(bool destroy)
        {
            qiLive = false;
            qiPending = false;
            if (qiRing == null) return;
            if (destroy) { Destroy(qiRing.gameObject); qiRing = null; }
            else qiRing.Hide();
        }
    }
}
