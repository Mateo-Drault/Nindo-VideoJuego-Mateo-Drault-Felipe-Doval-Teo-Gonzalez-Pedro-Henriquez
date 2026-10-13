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
    ///  * cada postura rota (el koi varado por los 4 pips, no los varados gratis de la zambullida y los pilares) le
    ///    devuelve vida a Kaito: como los tramos de la armadura de Gorō, la pelea larga no es puro desgaste.
    /// Todas las perillas del balance juntas acá abajo: vida, daño y sustento.
    /// </summary>
    public partial class MizuchiBoss
    {
        /// <summary>
        /// Las perillas del balance final. HealthScale multiplica la vida pedida (1440, el doble de antes) y DamageScale
        /// el daño de diseño de todos sus golpes (perlas, saltos, ola y pilares incluidos); EnemyArchetypes.Mizuchi aplica
        /// las dos. PostureHeal es lo que Kaito recupera en cada postura rota y PhaseHeal lo de cada cambio de fase.
        /// Simulado con los bots de AutoPilot, el reintento por fase y la cura por postura
        /// (Tools/Dev/boss_sims/mz_run.py tuning bueno,promedio,humano 200; minutos simulados hasta ganar con los reintentos):
        ///   vida 2160, daño 0.35, sin cura por postura: bueno 2.4 min; promedio 4.7 min, 1.9 muertes y 7 % gana sin morir
        ///                          (lo de antes: el bueno muy corto y el promedio casi siempre muere);
        ///   vida 3240, daño 0.33, sin cura por postura: bueno 3.6 min; promedio ~5 muertes (la pelea larga desgasta);
        ///   vida 2880, daño 0.33, postura 14: bueno 3.2 min; promedio 4.4 min, 0.7 muertes y 50 % sin morir;
        ///   vida 3240, daño 0.33, postura 10: bueno 3.6 min; promedio 6.1 min, 1.7 muertes;
        ///   vida 3240, daño 0.33, postura 14: bueno 3.6 min; promedio 5.6 min, 1.1 muertes y 29 % sin morir; humano
        ///                          3.8 min y 0.1 muertes (lo de hoy: ~11 posturas rotas por pelea el bueno, ~9 el promedio).
        /// El bot promedio falla ~45 % de los golpes del koi (el bueno 25 %). El tiempo real es ~1.4 veces el simulado
        /// (un solo dato): medirlo con "bot on bueno" y "bot on promedio" y ajustar acá. Más vida alarga la pelea del bueno
        /// casi en proporción; más PostureHeal le baja las muertes al promedio sin acortarla.
        /// </summary>
        public const float HealthScale = 2.25f, DamageScale = 0.33f, PostureHeal = 14f;
        /// <summary>Cura y Espíritu a Kaito al entrar a la fase 2 (corrupción) y a la 3 (la cascada responde). Pesa menos
        /// que la de la postura: el reintento arranca en la fase y no la cobra.</summary>
        static readonly float[] PhaseHeal = { 0f, 25f, 20f };
        const float PhaseSpirit = 20f;

        /// <summary>
        /// Reintento: la pelea vuelve en la fase más alta a la que llegó Kaito (como las fases de Chikuō y los actos de
        /// Kokuyō). Con la vida doble, morir en la fase 3 y volver a la plataforma sana dejaba al bot promedio ~10 muertes
        /// por pelea: cada fase es una lección ya aprendida.
        /// </summary>
        int retryPhase;

        void OnPlayerDied()
        {
            if (Fighting) retryPhase = Mathf.Max(retryPhase, Mathf.Min(CurrentPhase, phaseThresholds.Length));
        }

        /// <summary>
        /// Arranca la pelea en la fase del reintento como queda al terminar su transición: el cuerpo corrompido, la cascada
        /// crecida e inundando la plataforma y, en la 3, a pleno con el arcoíris doble; las esperas, las firmas y la cadencia
        /// de cada fase saltada; la vida en el umbral. Sin la escena de 5.5 s ni la cura (Kaito reapareció entero). El tema
        /// entra en su fase: esto corre en el mismo frame que PlayBossMusic (Boss.BeginFight).
        /// </summary>
        void ResumeRetryPhase()
        {
            int n = retryPhase;
            ResumeAtPhase(n);
            for (int i = 1; i <= n; i++) ApplyPhasePacing(i);
            Imbalance = 0f;
            CorruptedStats();
            body?.SetPhase(1);
            if (Falls != null)
            {
                Falls.Corruption = 0.35f;
                Falls.Intensity = n >= 2 ? 1.6f : 1.4f;
                if (n >= 2) Falls.MoonbowBoost = 2f;
                Falls.Flood?.Rise(2f);
            }
            Health = Mathf.Min(Health, config.maxHealth * phaseThresholds[n - 1]);
            StaggerCooldowns(n, 0.6f);
            QueueSignatures(n);
            Game.Audio?.SetBossMusicPhase(n + 1);
        }

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
        /// Le rompió la postura (el koi queda varado por los 4 pips o por el peloteo fallado): la bandana le devuelve
        /// PostureHeal. Los varados gratis (después de la zambullida y los pilares) no: esos no los ganó Kaito.
        /// </summary>
        void RewardPosture()
        {
            var p = Game.Player;
            if (p == null || !p.IsAlive || PostureHeal <= 0f) return;
            p.Heal(PostureHeal);
            Game.FX?.HealBurst(p.transform.position);
            BandanaGlow.Ensure(p)?.Pulse(BandanaGlow.Gold, 0.6f);
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
