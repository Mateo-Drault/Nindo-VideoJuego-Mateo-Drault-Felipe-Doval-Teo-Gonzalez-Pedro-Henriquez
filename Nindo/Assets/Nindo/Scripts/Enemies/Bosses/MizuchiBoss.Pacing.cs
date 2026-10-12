using System.Collections;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// El ritmo de la pelea larga (vida 1440, el doble). Simulado con el bot "bueno" (que pelea pegado al koi):
    ///  * los especiales de distancia (perlas, chorro, peloteo, barrido, tormenta) piden 4-6 m o más y contra alguien
    ///    pegado no salían NUNCA: cinco de los trece patrones. La Retirada (un salto corto hacia el otro lado de la
    ///    plataforma, lejos de Kaito) los abre desde cerca: un respiro para los dos y otra cosa que leer;
    ///  * los especiales vuelven antes en cada fase (FasterCooldowns) y algunos corren más: nada más rápido bajo el agua,
    ///    la ola de la fase 3 cruza a 9 m/s y sus pilares caen más seguidos. Los avisos (el hervor, el disco rojo de 1.1 s,
    ///    la franja de 1.2 s antes de la ola) no se acortan nunca;
    ///  * cada cambio de fase le devuelve algo de vida y Espíritu a Kaito, como en Kokuyō (no hay esbirros que curen);
    ///  * todo lo que pega va a DamageScale: con la vida doble y el daño de antes, el bueno moría el doble por intento.
    /// </summary>
    public partial class MizuchiBoss
    {
        /// <summary>
        /// Daño de todos sus golpes respecto de los números de diseño (EnemyArchetypes.Mizuchi lo aplica). Simulado con el
        /// bot "bueno": con 720 moría 0.3 veces por intento (77 % sin morir); con 1440 y el daño de antes, 1.3 (40 %); con
        /// 0.85 y las curas de fase, 0.7 (62 %).
        /// </summary>
        public const float DamageScale = 0.85f;

        // cooldowns por fase (1, 2, 3) de los especiales que se aceleran; el resto queda como lo pone EnemyArchetypes
        static readonly string[] FasterNames = { "Salto del Dragón", "Ola de la Cascada", "Pilares", "Chorro barrido", "Perlas de tormenta" };
        static readonly float[,] FasterCooldowns = { { 12f, 9f, 7f }, { 15f, 13f, 10f }, { 20f, 17f, 12f }, { 8f, 8f, 6.5f }, { 6f, 6f, 5f } };
        /// <summary>Nado bajo el agua de la zambullida (antes del hervor de 0.35 s, que es el aviso): x1, x0.75, x0.6.</summary>
        static readonly float[] SwimPace = { 1f, 0.75f, 0.6f };
        /// <summary>Velocidad de la ola por fase: en la 3 cruza a 9 m/s (la franja roja avisa igual 1.2 s antes de salir).</summary>
        static readonly float[] WaveSpeeds = { 8f, 8f, 9f };
        /// <summary>Separación entre pilares por fase (cada uno con su disco de 1.1 s).</summary>
        static readonly float[] PillarGaps = { 0.45f, 0.45f, 0.38f };
        /// <summary>Cura y Espíritu a Kaito al entrar a la fase 2 (corrupción) y a la 3 (la cascada responde).</summary>
        static readonly float[] PhaseHeal = { 0f, 25f, 20f };
        const float PhaseSpirit = 20f;

        // la retirada: a esta distancia de Kaito (el chorro llega a 11 m, las perlas salen desde 6) y adentro de este radio
        const float RetreatDistance = 8f, RetreatMinDistance = 5.5f, RetreatDeck = 6.5f, RetreatTurn = 0.45f;

        int PhaseIndex => Mathf.Clamp(CurrentPhase, 0, 2);
        float SwimPaceNow => SwimPace[PhaseIndex];
        float PillarGapNow => PillarGaps[PhaseIndex];

        /// <summary>Al cambiar de fase (después de la cuenta de Boss): las esperas de los especiales de esa fase.</summary>
        void ApplyPhasePacing(int newPhase)
        {
            int i = Mathf.Clamp(newPhase, 0, 2);
            for (int n = 0; n < FasterNames.Length; n++)
            {
                var p = FindPattern(FasterNames[n]);
                if (p != null) p.cooldown = FasterCooldowns[n, i];
            }
        }

        /// <summary>La bandana le devuelve vida y Espíritu a Kaito (fin de la corrupción, la cascada de la fase 3).</summary>
        void RewardKaito(int phase)
        {
            var p = Game.Player;
            float heal = PhaseHeal[Mathf.Clamp(phase, 0, 2)];
            if (p == null || !p.IsAlive || heal <= 0f) return;
            p.Heal(heal);
            p.AddSpirit(PhaseSpirit);
            BandanaGlow.Ensure(p)?.Pulse(BandanaGlow.Gold, 1f);
        }

        /// <summary>
        /// Retirada (primer paso de los patrones "desde lejos"): se enrosca 0.27 s (se le puede pegar), salta al otro lado
        /// de la plataforma (a ~8 m de Kaito, siempre en cuadro; en el aire los tajos rebotan), cae sin daño y gira hacia
        /// Kaito. El paso siguiente es el especial de distancia, con su aviso entero.
        /// </summary>
        IEnumerator RetreatRoutine(AttackDef a)
        {
            BeginSequence();
            if (target == null) { EndSequence(); yield break; }
            Vector3 land = RetreatPoint();
            anim.Play("Dive", 0.1f);
            anim.SetSpeed(1f);
            for (float t = 0f; t < 0.27f; t += Time.deltaTime)
            {
                if (SeqBroken) { EndSequence(); yield break; }
                TurnTo(land, 10f);
                yield return null;
            }
            if (SeqBroken) { EndSequence(); yield break; }
            float air = Mathf.Clamp(CombatMath.FlatDistance(transform.position, land) / 11f, 0.6f, 1f);
            yield return Breach(transform.position, land, air, 3f, 0f, 0f, 0f);
            if (SeqBroken) { EndSequence(); yield break; }
            // vuelve al blend de nado (quieto) y encara a Kaito antes de cargar el especial
            anim.Play(config.animLocomotion, 0.2f);
            for (float t = 0f; t < RetreatTurn; t += Time.deltaTime)
            {
                if (SeqBroken) break;
                if (target != null) TurnTo(target.transform.position, 9f);
                yield return null;
            }
            // suelta el paso: su reloj ya pasó el final del clip y Enemy sigue con el paso siguiente
            EndSequence();
        }

        /// <summary>
        /// Adónde se retira: el punto a RetreatDistance de Kaito (en 12 rumbos), sobre la plataforma, en cuadro y a
        /// RetreatMinDistance o más de él; entre los que sirven, el salto más corto.
        /// </summary>
        Vector3 RetreatPoint()
        {
            Vector3 k = target.transform.position;
            Vector3 best = OnDeck(k + (transform.position - k).Flat().normalized * RetreatDistance, RetreatDeck);
            float bestScore = float.MaxValue;
            for (int i = 0; i < 12; i++)
            {
                Vector3 dir = Quaternion.AngleAxis(i * 30f, Vector3.up) * North;
                Vector3 p = OnDeck(k + dir * RetreatDistance, RetreatDeck);
                p.y = DeckHeight;
                float d = CombatMath.FlatDistance(p, k);
                if (d < RetreatMinDistance) continue;
                float score = Mathf.Abs(d - RetreatDistance) + 0.15f * CombatMath.FlatDistance(p, transform.position);
                if (!OnScreen(p + Vector3.up * 2f)) score += 20f;
                if (score < bestScore) { bestScore = score; best = p; }
            }
            best.y = DeckHeight;
            return best;
        }
    }
}
