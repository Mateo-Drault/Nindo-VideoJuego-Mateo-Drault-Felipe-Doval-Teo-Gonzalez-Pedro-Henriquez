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
    ///  * cada fase muestra lo suyo enseguida (PhaseSignatures): la ola y los pilares en la 2, la tormenta en la 3. Con
    ///    las esperas escalonadas de entrada la mitad de las peleas no veía nunca la ola ni los pilares y dos de cada
    ///    tres no veían la tormenta; y de la fase 2 en adelante la mordida y el aletazo pesan menos;
    ///  * cada especial tiene UNA espera aunque lo usen dos patrones (el de cerca y el "desde lejos"): antes la
    ///    retirada con tormenta podía seguir con otra tormenta enseguida. Y después de una retirada los especiales de
    ///    distancia esperan un poco (Kaito vuelve; no es una ráfaga de dos especiales).
    /// Perillas del balance final: HealthScale (la vida) y DamageScale (lo que pega).
    /// </summary>
    public partial class MizuchiBoss
    {
        /// <summary>
        /// Las dos perillas del balance final (EnemyArchetypes.Mizuchi las aplica): HealthScale multiplica la vida pedida
        /// (1440, el doble de antes) y DamageScale el daño de diseño de todos sus golpes (perlas, saltos, ola y pilares
        /// incluidos). Simulado (pelea entera, minutos hasta ganar con los reintentos, 40 peleas por punto; "humano" =
        /// ve el aviso y se equivoca un poco más que el bot):
        ///   vida 1440, daño 1.0:  bueno 4.0 min y 2.3 muertes; humano 15 min y 8.2 muertes (con la ola, los pilares y la
        ///                          tormenta siempre en su fase la pelea doble es mucho más peligrosa que la de 720);
        ///   vida 1440, daño 0.7:  bueno 1.8 min y 0.7 muertes; humano 4.0 min y 2.3 muertes   (lo de hoy);
        ///   vida 1800, daño 0.5:  bueno 2.1 min y 0.3 muertes; humano 3.8 min y 1.2 muertes   (más larga y más pareja).
        /// El tiempo real es ~1.4 veces el simulado (un solo dato: medirlo con "bot on bueno"). Para la hora de partida,
        /// la última fila (HealthScale 1.25, DamageScale 0.5) es la candidata.
        /// </summary>
        public const float HealthScale = 1f, DamageScale = 0.7f;

        // cooldowns por fase (1, 2, 3) de los especiales que se aceleran; el resto queda como lo pone EnemyArchetypes
        static readonly string[] FasterNames = { "Salto del Dragón", "Ola de la Cascada", "Pilares", "Chorro barrido", "Perlas de tormenta" };
        static readonly float[,] FasterCooldowns = { { 12f, 9f, 7f }, { 15f, 13f, 10f }, { 20f, 17f, 12f }, { 8f, 8f, 6.5f }, { 6f, 6f, 5f } };
        /// <summary>Nado bajo el agua de la zambullida (antes del hervor de 0.35 s, que es el aviso): x1, x0.75, x0.6.</summary>
        static readonly float[] SwimPace = { 1f, 0.75f, 0.6f };
        /// <summary>Velocidad de la ola por fase: en la 3 cruza a 9 m/s (la franja roja avisa igual 1.2 s antes de salir).</summary>
        static readonly float[] WaveSpeeds = { 8f, 8f, 9f };
        /// <summary>Separación entre pilares por fase (cada uno con su disco de 1.1 s).</summary>
        static readonly float[] PillarGaps = { 0.45f, 0.45f, 0.38f };
        /// <summary>De la fase 2 en adelante los golpes de cerca pesan menos (la mezcla deja lugar a lo nuevo).</summary>
        static readonly string[] MeleeNames = { "Mordida", "Aletazo" };
        static readonly float[,] MeleeWeights = { { 1.6f, 1.2f, 1.2f }, { 1.5f, 1.1f, 1.1f } };
        /// <summary>
        /// Lo que cada fase muestra enseguida: el patrón queda listo a estos segundos de volver a pelear y pesa tanto
        /// (SignatureBoost) que es lo primero que elige en cuanto está listo y a tiro; al salir vuelve a su peso y a su
        /// espera. Con el triple seguía siendo una lotería: la tormenta salía en el 40 % de las peleas. En la fase 2, la ola primero y los pilares
        /// después (los dos juntos eran demasiado rojo de golpe); en la 3, la tormenta (con la retirada, para que salga
        /// aunque Kaito esté pegado).
        /// </summary>
        static readonly string[][] PhaseSignatures = { new string[0], new[] { "Ola de la Cascada", "Pilares" }, new[] { "Tormenta desde lejos" } };
        static readonly float[][] SignatureReadyIn = { new float[0], new[] { 2.5f, 10f }, new[] { 2.5f } };
        const float SignatureBoost = 50f;
        /// <summary>Después de una retirada, los otros especiales de distancia esperan al menos esto (Kaito vuelve).</summary>
        const float AfterRetreatRangedGap = 3f;
        static readonly string[] RangedSpecials = { "pearls", "jet", "rally", "jetsweep", "storm" };

        // las firmas de la fase en curso que todavía no salieron, con su peso de siempre (como mucho dos)
        readonly AttackPattern[] signature = new AttackPattern[2];
        readonly float[] signatureWeight = new float[2];

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
            for (int n = 0; n < MeleeNames.Length; n++)
            {
                var p = FindPattern(MeleeNames[n]);
                if (p != null) p.weight = MeleeWeights[n, i];
            }
        }

        /// <summary>
        /// Al volver a pelear en una fase nueva (después de StaggerCooldowns): sus firmas quedan listas en
        /// SignatureReadyIn y pesan SignatureBoost hasta que salen. Lo que no salió de la fase anterior vuelve a su peso.
        /// </summary>
        void QueueSignatures(int phase)
        {
            ClearSignatures();
            int i = Mathf.Clamp(phase, 0, PhaseSignatures.Length - 1);
            var names = PhaseSignatures[i];
            for (int n = 0; n < names.Length && n < signature.Length; n++)
            {
                var p = FindPattern(names[n]);
                if (p == null) continue;
                p.lastUsed = Time.time - p.cooldown + SignatureReadyIn[i][n];
                signature[n] = p;
                signatureWeight[n] = p.weight;
                p.weight *= SignatureBoost;
            }
        }

        void ClearSignatures()
        {
            for (int n = 0; n < signature.Length; n++)
            {
                if (signature[n] != null) signature[n].weight = signatureWeight[n];
                signature[n] = null;
            }
        }

        /// <summary>
        /// Cada paso que arranca: si abre una firma, vuelve a su peso; si es un especial, todos los patrones que usan ese
        /// mismo golpe cuentan su espera desde ahora (los AttackDef se comparten entre patrones, también en los clones
        /// del reintento); si es una retirada, los otros especiales de distancia esperan AfterRetreatRangedGap.
        /// </summary>
        void PaceStep(AttackDef a)
        {
            if (pattern == null || config.patterns == null) return;
            if (step == 0)
                for (int n = 0; n < signature.Length; n++)
                    if (signature[n] == pattern) { pattern.weight = signatureWeight[n]; signature[n] = null; }
            float now = Time.time;
            if (a.special == "retreat")
            {
                foreach (var p in config.patterns)
                    if (p != null && p != pattern && p.minRange >= 4f) p.lastUsed = Mathf.Max(p.lastUsed, now - p.cooldown + AfterRetreatRangedGap);
                return;
            }
            if (System.Array.IndexOf(RangedSpecials, a.special) < 0) return;
            foreach (var p in config.patterns)
                if (p != null && p != pattern && System.Array.IndexOf(p.steps, a) >= 0) p.lastUsed = now;
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
