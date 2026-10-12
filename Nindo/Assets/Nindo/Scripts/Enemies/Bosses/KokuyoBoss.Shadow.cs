using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// La sombra viva en los tres actos: el director del dúo cuerpo + sombra (el cómo de cada golpe está en
    /// KageShadow, la regla de lectura en KokuyoDuet).
    ///  * Turnos: cuando él termina un combo, a veces le toca a la sombra (Acto 1: 40 %, Acto 2: 60 %, Acto 3: 50 %);
    ///    si la sombra lleva mucho sin atacar (11 / 5.5 / 6.5 s) ataca igual en el próximo hueco. Nunca dos turnos de la
    ///    sombra más juntos que 5.5 / 2.6 / 3.2 s. La primera vez en el Acto 1 es a los ~15 s, con el grito del abuelo.
    ///    El turno de la sombra le saca lugar a él (no se suma): él vuelve a atacar recién 0.6 s después del golpe de la
    ///    sombra (en el Acto 1 se queda quieto hasta que vuelve a sus pies). Simulado con el bot: la sombra hace ~30-40 %
    ///    de los golpes en los Actos 2 y 3 y el daño por minuto queda como antes (±5 %).
    ///  * Dúos: los patrones DuetPattern de KokuyoMoves meten un golpe de la sombra en el combo del cuerpo (antes,
    ///    mientras él carga; o entre dos de sus cortes, del otro lado de Kaito).
    ///  * La regla: el que arranca después pega después, a Gap(primero, segundo) del otro (0.9 / 1.05 / 1.1 s; 1.2 s
    ///    entre el Nobi y el golpe siguiente de él; 1.3 s entre un golpe de él y el corte desde la oscuridad, que sale
    ///    1.05 s antes). PlanWindup (cuerpo) y ShadowWindup (sombra) estiran el windup.
    ///  * Nada de sombra con él de rodillas, en una escena o en la última resistencia (y nada nuevo mientras está hundido).
    /// Cada desvío a la sombra le suma postura a él (es parte suya) y, si estaba entre combos, lo tira de rodillas.
    /// </summary>
    public partial class KokuyoBoss
    {
        static readonly float[] TurnChance = { 0f, 0.4f, 0.6f, 0.5f };
        static readonly float[] TurnMinGap = { 0f, 5.5f, 2.6f, 3.2f };
        static readonly float[] MaxQuiet = { 0f, 11f, 5.5f, 6.5f };
        /// <summary>Segundos desde que arranca cada acto hasta el primer turno de la sombra (en el Acto 1, los imparables
        /// se enseñan antes: a los 12 y 20 s).</summary>
        static readonly float[] FirstTurnAfter = { 0f, 15f, 1.6f, 2.5f };
        /// <summary>Después del Nobi él espera más: su sombra tiene que volver a sus pies para avisarle el golpe.</summary>
        const float GapAfterNobi = 1.2f;

        /// <summary>El modelo animado (la sombra pegada gira desde su rotación).</summary>
        public Transform Body => model;

        // libro de golpes: cuándo pegó cada uno por última vez (la regla se mide contra esto y contra lo que viene)
        float bodyPendingAt = -1f, bodyLastAt = -99f, shadowPendingAt = -1f, shadowLastAt = -99f;
        AttackKind bodyPendingKind, bodyLastKind, shadowPendingKind, shadowLastKind;
        string shadowPendingMove = "", shadowLastMove = "";
        // turnos
        float actStart, lastShadowTurn = -99f;
        bool shadowTurnAsked, nobiTaught, darkTaught;
        AttackPattern duetTeach;
        // para el informe de cada acto (consola): cuántos golpes de cada uno, el par más junto y, en el eclipse, la
        // salida de la oscuridad más pegada a un golpe de él
        int statBody, statShadow, statShadowParried, statDuet;
        float statMinGap = 99f, statEmergeClear = 99f, lastEmergeAt = -99f;

        /// <summary>Él está entre combos: ni atacando, ni comprometido con un ataque, ni de rodillas.</summary>
        bool BodyFree => (State == EnemyState.Chase || State == EnemyState.Strafe || State == EnemyState.Guard)
                         && (Game.Combat == null || !Game.Combat.HasToken(this));

        /// <summary>La sombra puede pelear: no hay escena, él no está de rodillas, no es la última resistencia.</summary>
        bool ShadowAllowed => Fighting && IsAlive && transition == null && !LastStand
                              && State != EnemyState.Exhausted && State != EnemyState.Executed;

        void ResetShadowDirector()
        {
            bodyPendingAt = shadowPendingAt = -1f;
            bodyLastAt = shadowLastAt = -99f;
            shadowPendingMove = shadowLastMove = "";
            lastShadowTurn = -99f;
            shadowTurnAsked = false;
            actStart = Time.time;
            statBody = statShadow = statShadowParried = statDuet = 0;
            statMinGap = statEmergeClear = 99f;
            lastEmergeAt = -99f;
        }

        void BeginActShadow()
        {
            ResetPacing();
            actStart = Time.time;
            lastShadowTurn = -99f;
            shadowTurnAsked = false;
            kage?.SetAct(Act);
            duetTeach = null;
            foreach (var p in config.patterns) if (p.name == KokuyoMoves.DuetTeachName) duetTeach = p;
        }

        // ------------------------------------------------------------------ la regla
        /// <summary>Lo más temprano que puede pegar un golpe 'kind' del cuerpo que pegaría en 't' (Time.time).</summary>
        float EarliestBodyImpact(float t, AttackKind kind)
        {
            if (kage != null)
            {
                // antes de un corte desde la oscuridad tiene que caber también su salida (EmergeLead antes)
                float before = kage.FromDark ? KokuyoDuet.GapBeforeDark(kind, kage.PendingKind) : KokuyoDuet.Gap(kind, kage.PendingKind);
                t = Fit(t, kage.PendingImpactAt, before, GapAfter(kage.PendingKind, kage.PendingMove, kind));
            }
            return Mathf.Max(t, shadowLastAt + GapAfter(shadowLastKind, shadowLastMove, kind));
        }

        static float GapAfter(AttackKind shadowKind, string shadowMove, AttackKind bodyKind) =>
            Mathf.Max(KokuyoDuet.Gap(shadowKind, bodyKind), shadowMove == KokuyoMoves.Nobi ? GapAfterNobi : 0f);

        /// <summary>Lo más temprano que puede pegar un golpe 'kind' de la sombra que pegaría en 't' (Time.time).</summary>
        public float EarliestShadowImpact(float t, AttackKind kind)
        {
            bool dark = kage != null && kage.FromDark;
            float bp = State == EnemyState.Attack && !float.IsInfinity(StrikeEta) ? Time.time + StrikeEta : -1f;
            t = Fit(t, bp, KokuyoDuet.Gap(kind, StepKind), dark ? KokuyoDuet.GapBeforeDark(StepKind, kind) : KokuyoDuet.Gap(StepKind, kind));
            return Mathf.Max(t, bodyLastAt + (dark ? KokuyoDuet.GapBeforeDark(bodyLastKind, kind) : KokuyoDuet.Gap(bodyLastKind, kind)));
        }

        /// <summary>
        /// Un golpe que pegaría en 't' frente al golpe en camino del otro (en 'pending'): si entra antes con su
        /// separación ('gapBefore'), va antes (así lo planeado se respeta); si no, a 'gapAfter' después del otro.
        /// </summary>
        static float Fit(float t, float pending, float gapBefore, float gapAfter)
        {
            if (pending <= Time.time || t + gapBefore <= pending) return t;
            return Mathf.Max(t, pending + gapAfter);
        }

        /// <summary>Windup de un golpe de la sombra (KageShadow.PlanWindup).</summary>
        public float ShadowWindup(AttackDef a, float windup) => EarliestShadowImpact(Time.time + windup, a.kind) - Time.time;

        /// <summary>
        /// Cada golpe del cuerpo: si es un dúo que pega DESPUÉS de su sombra, primero arranca la sombra; después el
        /// golpe se estira hasta quedar a la distancia de la regla de cualquier golpe de la sombra en camino.
        /// </summary>
        protected override float PlanWindup(AttackDef a, float windup)
        {
            if (look == null) return windup;
            RunCues(true);
            return EarliestBodyImpact(Time.time + windup, a.kind) - Time.time;
        }

        /// <summary>Los golpes de la sombra de este paso del dúo (before = antes del golpe del cuerpo).</summary>
        void RunCues(bool before)
        {
            if (!(pattern is DuetPattern dp) || dp.cues == null || kage == null || !ShadowAllowed) return;
            foreach (var c in dp.cues)
            {
                if (c.step != step || c.before != before) continue;
                if (kage.TryStrike(c.move, c.side)) { statDuet++; OnShadowTurn(c.move); }
            }
        }

        // ------------------------------------------------------------------ por frame
        void UpdateShadowDirector()
        {
            TrackImpacts();
            if (kage == null) return;
            if (!ShadowAllowed)
            {
                // de rodillas o en escena: la sombra suelta lo que estaba cargando (si todavía no dio el "¡ahora!")
                if (kage.Busy) kage.Abort(transition != null || !IsAlive);
                return;
            }
            float now = Time.time;
            if (Act == 1 && duetTeach != null) duetTeach.weight = nobiTaught ? 0.9f : 0f;
            // hundido en el Paso de Sombra no arranca nada nuevo (lo que ya venía sigue)
            if (sinking || !BodyFree || kage.Busy || !kage.CanStrike) return;
            if (now < actStart + FirstTurnAfter[Act] || now < lastShadowTurn + TurnMinGap[Act] * ShadowPace) return;
            bool quiet = now >= Mathf.Max(lastShadowTurn, actStart) + MaxQuiet[Act] * ShadowPace;
            if (!shadowTurnAsked && !quiet && !(Act == 1 && !nobiTaught)) return;
            if (TryShadowTurn()) shadowTurnAsked = false;
        }

        /// <summary>El turno de la sombra sola: Nobi (Acto 1); Giri, Nui o Watari (Acto 2); Giri desde la oscuridad (3).</summary>
        bool TryShadowTurn()
        {
            string move;
            ShadowSide side = ShadowSide.Any;
            if (Act == 1) move = KokuyoMoves.Nobi;
            else if (Act == 2)
            {
                float r = Random.value;
                move = r < 0.5f ? KokuyoMoves.Giri : r < 0.8f ? KokuyoMoves.Nui : KokuyoMoves.Watari;
            }
            else { move = KokuyoMoves.Giri; side = ShadowSide.Opposite; }
            bool ok = kage.TryStrike(move, side);
            // si no se pudo (lejos para el Nui, sin lugar para cruzar) corta como él
            if (!ok && move != KokuyoMoves.Giri && Act >= 2) ok = kage.TryStrike(move = KokuyoMoves.Giri, side);
            if (!ok) return false;
            OnShadowTurn(move);
            float impact = kage.PendingImpactAt;
            // él no le pisa el turno: en el Acto 1 se queda quieto hasta que la sombra vuelve (HoldsBody); en el 2 y el 3
            // vuelve a atacar 0.6 s después del golpe de la sombra (el turno de ella le saca lugar a él, no se suma)
            if (impact > 0f) nextAttackTime = Mathf.Max(nextAttackTime, impact + (Act == 1 ? 0.4f : 0.6f));
            return true;
        }

        void OnShadowTurn(string move)
        {
            lastShadowTurn = Time.time;
            if (move == KokuyoMoves.Nobi && !nobiTaught)
            {
                nobiTaught = true;
                Bark("kokuyo_hint_sombra");
            }
        }

        /// <summary>Él no se mueve ni ataca mientras su sombra pegada ataca (Acto 1).</summary>
        bool HoldForShadow(float dt)
        {
            if (kage == null || !kage.HoldsBody || !Fighting) return false;
            Stop();
            if (target != null) Face(target.transform.position, 0.8f, dt);
            return true;
        }

        protected override void TickChase(float dt) { if (!HoldForShadow(dt)) base.TickChase(dt); }
        protected override void TickStrafe(float dt) { if (!HoldForShadow(dt)) base.TickStrafe(dt); }

        /// <summary>Anota cuándo pegó cada uno (el golpe en camino que deja de estarlo cerca de su hora, pegó o lo desviaron).</summary>
        void TrackImpacts()
        {
            float now = Time.time;
            float bp = State == EnemyState.Attack && !float.IsInfinity(StrikeEta) ? now + StrikeEta : -1f;
            if (bp < 0f && bodyPendingAt > 0f && now >= bodyPendingAt - 0.2f)
            {
                bodyLastAt = Mathf.Min(now, bodyPendingAt);
                bodyLastKind = bodyPendingKind;
                statBody++;
                statMinGap = Mathf.Min(statMinGap, Mathf.Abs(bodyLastAt - shadowLastAt));
                statEmergeClear = Mathf.Min(statEmergeClear, bodyLastAt - lastEmergeAt);
            }
            bodyPendingAt = bp;
            if (bp > 0f) bodyPendingKind = StepKind;

            float sp = kage != null && kage.State == EnemyState.Attack ? kage.PendingImpactAt : -1f;
            if (sp < 0f && shadowPendingAt > 0f && now >= shadowPendingAt - 0.2f)
            {
                shadowLastAt = Mathf.Min(now, shadowPendingAt);
                shadowLastKind = shadowPendingKind;
                shadowLastMove = shadowPendingMove;
                statShadow++;
                statMinGap = Mathf.Min(statMinGap, Mathf.Abs(shadowLastAt - bodyLastAt));
            }
            shadowPendingAt = sp;
            if (sp > 0f) { shadowPendingKind = kage.PendingKind; shadowPendingMove = kage.PendingMove; }
        }

        /// <summary>Informe para probar con el bot: golpes de cada uno en el acto, el par más junto (nunca &lt; 0.9 s) y en
        /// el eclipse la salida más pegada a un golpe de él (nunca &lt; 0.25 s).</summary>
        void LogShadowStats(string why)
        {
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            string dark = Act >= 3 && statEmergeClear < 98f ? $", salida más pegada a un golpe de él {statEmergeClear.ToString("0.00", inv)} s" : "";
            Debug.Log($"[Nindo] Kokuyō acto {Act} ({why}): {(Time.time - actStart).ToString("0", inv)} s, " +
                      $"{statBody} golpes de él, {statShadow} de la sombra ({statDuet} en dúos, {statShadowParried} desviados), " +
                      $"par más junto {statMinGap.ToString("0.00", inv)} s{dark}");
            statBody = statShadow = statShadowParried = statDuet = 0;
            statMinGap = statEmergeClear = 99f;
        }

        // ------------------------------------------------------------------ lo que le pasa a la sombra
        /// <summary>Kaito desvió a la sombra: la postura es de él (le cruje una grieta) y entre combos cae de rodillas.</summary>
        public void OnShadowParried(bool perfect, Vector3 at)
        {
            statShadowParried++;
            if (!IsAlive || transition != null) return;
            int before = Mathf.FloorToInt(Imbalance + 0.001f);
            AddImbalance(perfect ? 1.5f : 1f);
            int after = Mathf.FloorToInt(Imbalance + 0.001f);
            for (int k = before; k < after && k < 5; k++) look?.FlareCrack(k, AimPoint);
            Game.Camera?.Shake(perfect ? 0.3f : 0.2f);
            if (Act >= 3 && fx != null && Game.Player != null)
                fx.ParryLight(Game.Player.transform.position + (at - Game.Player.transform.position).Flat().normalized * 0.8f, perfect);
            float need = Act == 1 ? KneelThresholdFirst : KneelThreshold;
            if (State != EnemyState.Exhausted && BodyFree && Imbalance >= need - 0.01f) BecomeExhausted();
        }

        /// <summary>Salió de la oscuridad (eclipse). La primera vez, el abuelo avisa.</summary>
        public void OnShadowEmerged()
        {
            lastEmergeAt = Time.time;
            statEmergeClear = Mathf.Min(statEmergeClear, Time.time - bodyLastAt);
            if (darkTaught) return;
            darkTaught = true;
            Bark("kokuyo_hint_oscuridad");
        }

#if UNITY_EDITOR || DEVELOPMENT_BUILD
        /// <summary>Pruebas (AutoPilot "kokuyo sombra MOV [lado]"): la sombra ataca ya con ese golpe si puede.</summary>
        public bool DebugShadow(string move, string side)
        {
            if (kage == null || !ShadowAllowed) return false;
            string m = move == "nobi" ? KokuyoMoves.Nobi : move == "nui" ? KokuyoMoves.Nui : move == "watari" ? KokuyoMoves.Watari : KokuyoMoves.Giri;
            var s = side == "flanco" ? ShadowSide.Flank : side == "opuesto" ? ShadowSide.Opposite : ShadowSide.Any;
            if (!kage.TryStrike(m, s)) return false;
            OnShadowTurn(m);
            return true;
        }
#endif
    }
}
