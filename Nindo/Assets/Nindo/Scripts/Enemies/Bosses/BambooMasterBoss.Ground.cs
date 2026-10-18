using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// En el piso (fase 2 "El Piso" y la coda de la 3 cuando no le queda caña libre; diseño 4.3 y 5.3): pelea rápida con la
    /// flauta-bastón SIN guardia. Las tandas las elige y las acerca Enemy (Chase, los patrones de BambooMasterMoves); el
    /// jefe agrega lo que no es de Enemy: el Paso del Ermitaño (el corte en neutral le entra a x0.6 y se va de una
    /// voltereta), la armadura de la carga (x0.35), la Flauta Giratoria de dos golpes, la Barrida del Bastón (dash perfecto:
    /// Bastón Clavado), el Soplo, la Grulla en el Bastón (su verticalidad en chico: el bastón también se corta) y Pregunta y
    /// Respuesta (la flauta toca la frase y la repite como golpes).
    /// </summary>
    public partial class BambooMasterBoss
    {
        float nextPoleAt = -1f, nextQaAt = -1f;
        bool onPole, fluting, qaFailed;

        // locomoción de costado y hacia atrás (el blend tree solo tiene quieto, camina y corre)
        string strafeWanted = "Locomotion";
        float strafeWantedFor;
        bool sideSpeedSet;

        /// <summary>
        /// Pelea en el piso hasta que la fase cambie (o, en la coda de la 3, hasta que tenga una caña libre). Enemy maneja el
        /// acercarse, rodear y las tandas; acá corren los relojes de la Grulla en el Bastón y de Pregunta y Respuesta.
        /// </summary>
        IEnumerator GroundBrain()
        {
            if (body != Body.Ground) Landed(transform.position, transform.forward);
            EnterGroundAI(0.35f);
            float now = Time.time;
            if (nextPoleAt < 0f) nextPoleAt = now + Random.Range(BambooMasterMoves.PoleFirst.x, BambooMasterMoves.PoleFirst.y);
            if (nextQaAt < 0f) nextQaAt = now + Random.Range(BambooMasterMoves.QaFirst.x, BambooMasterMoves.QaFirst.y);
            while (IsAlive && Fighting)
            {
                bool idle = State == EnemyState.Chase || State == EnemyState.Strafe;
                if (phaseIdx != 1 && HasFreeStalk() && idle) { LeaveGroundAI(); yield break; }
                if (idle && Time.time >= nextPoleAt)
                {
                    LeaveGroundAI();
                    yield return PoleCraneAct();
                    nextPoleAt = Time.time + Random.Range(BambooMasterMoves.PoleEvery.x, BambooMasterMoves.PoleEvery.y);
                    EnterGroundAI(0.35f);
                    continue;
                }
                if (idle && phaseIdx == 1 && Time.time >= nextQaAt)
                {
                    LeaveGroundAI();
                    yield return QuestionAnswer();
                    nextQaAt = Time.time + Random.Range(BambooMasterMoves.QaEvery.x, BambooMasterMoves.QaEvery.y);
                    EnterGroundAI(0.35f);
                    continue;
                }
                UpdateStrafeAnim(Time.deltaTime);
                yield return null;
            }
        }

        void EnterGroundAI(float firstIn)
        {
            if (body != Body.Ground) SetBody(Body.Ground);
            groundAI = true;
            vuln = Vuln.Neutral;
            clip = null;   // las tandas y la locomoción las toca Enemy
            config.animLocomotion = "Locomotion";
            strafeWanted = config.animLocomotion;
            nextAttackTime = Time.time + firstIn;
            SetState(EnemyState.Chase);
        }

        void LeaveGroundAI()
        {
            groundAI = false;
            config.animLocomotion = "Locomotion";
            if (State != EnemyState.Attack) SetState(EnemyState.Scripted);
            vuln = Vuln.None;
        }

        /// <summary>
        /// El Paso del Ermitaño en lugar de la guardia: el corte en neutral le entra a x0.6 (lo roza mientras se va) y se va
        /// de una voltereta 2.5 m (0.35 s invulnerable); 0.25 s después arranca una tanda.
        /// </summary>
        HitResult NeutralHit(in DamageInfo info)
        {
            var r = ApplyDamage(info, BambooMasterMoves.NeutralMul);
            if (r == HitResult.Hit && !phaseChanging) Run(HermitStep());
            return r;
        }

        IEnumerator HermitStep()
        {
            vuln = Vuln.None;
            if (body != Body.Ground) SetBody(Body.Ground);
            Face(TargetPos, 99f, 1f);
            var c = ChikuoTimings.BackFlip;
            Play(c, 0.05f);
            float inv = 0.35f;
            while (!ClipDone)
            {
                ClipTravel(c);
                if (inv > 0f && clipT >= inv) vuln = Vuln.Neutral;
                yield return null;
            }
            EnterGroundAI(BambooMasterMoves.AfterFlip);
            yield return Brain();
        }

        /// <summary>Rodea y retrocede con sus clips: el agente se mueve de costado o hacia atrás y Run no lo dice (los clips
        /// van a walkSpeed: el controller los acelera; acá se los toca a la velocidad real para que los pies no patinen).</summary>
        void UpdateStrafeAnim(float dt)
        {
            string want = "Locomotion";
            float side = 0f;
            if (State == EnemyState.Strafe && agent != null && agent.enabled)
            {
                Vector3 v = transform.InverseTransformDirection(agent.velocity);
                if (Mathf.Abs(v.x) > 0.6f && Mathf.Abs(v.x) > Mathf.Abs(v.z) * 1.2f) { want = v.x > 0f ? "StrafeR" : "StrafeL"; side = Mathf.Abs(v.x); }
                else if (v.z < -0.6f && -v.z > Mathf.Abs(v.x) * 1.2f) { want = "WalkBack"; side = -v.z; }
            }
            if (want != strafeWanted) { strafeWanted = want; strafeWantedFor = 0f; }
            else strafeWantedFor += dt;
            if (strafeWantedFor > 0.15f || want == "Locomotion") config.animLocomotion = strafeWanted;
            bool sideClip = State == EnemyState.Strafe && (anim.Current == "StrafeL" || anim.Current == "StrafeR" || anim.Current == "WalkBack");
            if (sideClip)
            {
                if (side <= 0f && agent != null) side = agent.velocity.magnitude;
                anim.SetSpeed(Mathf.Clamp(side / config.walkSpeed, 0.4f, 1.2f));
                sideSpeedSet = true;
            }
            else if (sideSpeedSet)
            {
                sideSpeedSet = false;
                if (State != EnemyState.Attack) anim.SetSpeed(1f);
            }
        }

        // ================================================================== golpes de piso (los de Enemy, con lo del clip)
        /// <summary>El cuerpo avanza lo que avanza el clip del golpe (travel_m) y frena delante de Kaito (no lo atraviesa).</summary>
        void GroundTravel(AttackDef a)
        {
            if (stepClip == null || stepClip.Travel == null || anim.Frozen || target == null) return;
            float x = stepClip.TravelAt(stepNorm);
            float d = x - travelDone;
            travelDone = x;
            if (d <= 0f) { if (d < 0f) MoveBy(transform.forward * d); return; }
            float room = Mathf.Max(0f, DistToTarget - (Radius + target.Radius + 0.25f));
            float move = Mathf.Min(d, room);
            if (move > 0f) MoveBy(transform.forward * move);
        }

        /// <summary>La Barrida del Bastón: el disco de 2.6 m a ras del piso; el dash perfecto le clava el bastón.</summary>
        void TickLowSweep(AttackDef a)
        {
            GroundTravel(a);
            if (stepHit || stepNorm < a.activeStart) return;
            stepHit = true;
            Game.FX?.Shockwave(transform.position, a.specialParam, new Color(0.85f, 0.8f, 0.6f));
            Game.FX?.Dust(transform.position, 1.3f);
            Game.Audio?.Play("ability_wind", transform.position, 0.7f, 0.1f);
            if (target == null || CombatMath.FlatDistance(TargetPos, transform.position) - target.Radius > a.specialParam) return;
            var r = HitPlayer(a, transform.position);
            if (r == HitResult.Dodged && PerfectDodge) Run(SimpleHole(ChikuoTimings.StaffStuck, BambooMasterMoves.Clavado, null, false));
        }

        /// <summary>El Soplo: un dardo desde el piso (Kaito lejos). El anillo es el de sus pies, con la ETA del dardo.</summary>
        void TickSoplo(AttackDef a)
        {
            if (specialFired || stepClip == null) return;
            if (stepNorm < Mathf.Max(0f, stepClip.EventAt("DartSpawn", 0))) return;
            specialFired = true;
            FireDart();
        }

        // ------------------------------------------------------------------ la Flauta Giratoria (dos golpes en un clip)
        int spinHit;
        bool spinTicked2, spinGlint2;
        float spinC1, spinC2;

        void BeginSpin(AttackDef a)
        {
            var c = ChikuoTimings.StaffSpin2;
            spinHit = 0;
            spinTicked2 = spinGlint2 = false;
            spinC1 = c.EventAt("Contact", 0);
            spinC2 = Mathf.Max(spinC1, c.EventAt("Contact", 1));
            Play(c, 0.08f, 0f, spinC1 * c.Seconds / Mathf.Max(0.1f, a.windup));
            heldStrikeAt = spinC1;
        }

        float SpinEta() => spinHit >= 2 ? float.PositiveInfinity : RealUntil(spinHit == 0 ? spinC1 : spinC2);

        void TickSpin(AttackDef a, float dt)
        {
            if (clip != ChikuoTimings.StaffSpin2) return;
            if (stepClock < tl.ReleaseTime) Face(TargetPos, 1.3f, dt);
            if (spinHit == 0 && clipT >= spinC1 * clip.Seconds)
            {
                spinHit = 1;
                clipRate = 1f;   // el segundo barrido a velocidad de clip (0.40 s después del primero)
                trail?.Begin();
                SpinStrike(a);
            }
            else if (spinHit == 1)
            {
                // el "¡ya!" y el destello del segundo (Enemy los da una vez por paso)
                float eta = SpinEta();
                if (!spinTicked2 && AudioManager.CueDue(eta, TellStyle.TickParryable))
                {
                    spinTicked2 = true;
                    Game.Audio?.Play("tell_tick", DistToTarget < 8f ? (Vector3?)null : transform.position, 0.8f, 0.03f);
                    GameEvents.RaiseStrikeCue(this, false);
                }
                if (!spinGlint2 && eta <= a.TellBias) { spinGlint2 = true; Game.FX?.BladeGlint(MuzzlePos, false); }
                if (clipT >= spinC2 * clip.Seconds)
                {
                    spinHit = 2;
                    heldStruck = true;
                    SpinStrike(a);
                    EndTell(TellOutcome.Struck);
                }
            }
            if (spinHit >= 2 && ClipDone) { trail?.Stop(); EndMove(TellOutcome.Struck); }
        }

        void SpinStrike(AttackDef a)
        {
            Game.Audio?.Play(a.sfx, transform.position, 0.65f, 0.1f);
            BambooGrove.Leaves(transform.position + Vector3.up * 1.2f, 0.8f);
            if (target != null && CombatMath.InArc(transform, TargetPos, a.range, 220f, target.Radius)) HitPlayer(a, transform.position);
        }

        // ================================================================== la Grulla en el Bastón
        /// <summary>
        /// Salta 4 m atrás, clava el bastón, se sube a la punta y se para en un pie como una grulla con las campanas blancas
        /// (cargada de 0.45 a 1.40 s desde que clava: cortarle el bastón lo tira, el revolcón desde 2.4 m); después se tira en
        /// picada desde la punta (disco rojo de 1.4 m fijo a 0.45 s del golpe).
        /// </summary>
        IEnumerator PoleCraneAct()
        {
            if (Teach("pole")) { Bark("grulla", true); ShowTip(StoryText.Hint("bamboo_staff")); }
            vuln = Vuln.None;
            SetState(EnemyState.Scripted);
            Face(TargetPos, 99f, 1f);
            yield return HopBack(BambooMasterMoves.PoleHop);
            var plant = ChikuoTimings.PolePlant;
            var climb = ChikuoTimings.PoleClimb;
            var bal = ChikuoTimings.PoleBalance;
            var dive = ChikuoTimings.PoleDive;
            float plantT = plant.Event("Plant") * plant.Seconds;
            // de que clava: 0.45-1.40 cargado, sale a 1.40 y pega 0.93 s después (el Contact de PoleDive)
            const float loadFrom = 0.45f, leaveAt = 1.40f;
            float strike = plantT + leaveAt + dive.Contact * dive.Seconds;
            var def = BambooMasterMoves.Held("Picada de la Pértiga", plant, AttackKind.Unblockable, strike, BambooMasterMoves.Dmg(BambooMasterMoves.Move.PoleDive, phaseIdx), BambooMasterMoves.PoleDive, dive.RingM);
            if (!StartMove(def)) yield break;
            Play(plant, 0.08f);
            heldSlots = BambooMasterLook.KickSlots;
            float t0 = Time.time, t = 0f;
            Vector3 land = TargetPos;
            SetDiscArea(land, dive.RingM);
            heldStrikeAt = 1f;
            bool planted = false, loaded = false;
            // en el piso con el bastón clavado: PolePlant, PoleClimb y la grulla en la punta (PoleBalance en loop)
            while (t < plantT + leaveAt)
            {
                if (!anim.Frozen) t += Time.deltaTime;
                heldTravel = Mathf.Max(0f, strike - t - RealUntil(1f));
                if (!planted && t >= plantT) { planted = true; Game.Audio?.Play("step_wood", transform.position, 0.9f, 0.1f); Game.FX?.Dust(transform.position + transform.forward * 0.4f, 0.6f); }
                if (clip == plant && ClipDone) Play(climb, 0f);
                else if (clip == climb && ClipDone) Play(bal, 0.05f);
                if (!loaded && t >= plantT + loadFrom)
                {
                    loaded = true;
                    onPole = true;
                    vuln = Vuln.Loaded;
                    loadedStalk = null;
                    look.Loaded = true;
                    loadUntil = Time.time + (leaveAt - loadFrom);
                    Sfx("tell_chime_shimmer", "parry_ready", Voice, 0.5f);
                }
                if (loaded && t >= plantT + leaveAt - 0.02f) { onPole = false; look.Loaded = false; vuln = Vuln.None; }
                land = Floor(TargetPos);
                SetDiscArea(land, dive.RingM);
                yield return null;
            }
            onPole = false;
            look.Loaded = false;
            vuln = Vuln.None;
            // la picada desde la punta (la raíz en los pies: root_offset de PoleBalance) hasta el disco
            Vector3 from = transform.position + transform.rotation * bal.RootOffset;
            Play(dive, 0f);
            heldStrikeAt = dive.Contact;
            heldTravel = 0f;
            bool fix = false;
            look.BeginLimbTrail(BambooMasterLook.KickSlots, true);
            while (clipT < dive.Contact * dive.Seconds - 1e-4f)
            {
                if (!fix) { fix = RealUntil(dive.Contact) <= BambooMasterMoves.SproutFix; land = Floor(TargetPos); SetDiscArea(land, dive.RingM); }
                Vector3 dir = (land - from).Flat();
                Carry(Arc(from, land, ClipNorm / dive.Contact, 0.6f), Quaternion.LookRotation(dir.sqrMagnitude > 1e-4f ? dir.normalized : transform.forward));
                yield return null;
            }
            heldStruck = true;
            EndTell(TellOutcome.Struck);
            Landed(land, (land - from).Flat());
            Game.FX?.Shockwave(land, dive.RingM, new Color(1f, 0.55f, 0.4f));
            Game.Camera?.Shake(0.45f);
            Game.Audio?.Play("slam", land, 0.8f);
            if (target != null && CombatMath.FlatDistance(TargetPos, land) <= dive.RingM + target.Radius) HitPlayer(def, land);
            look.StopLimbTrail();
            EndMove(TellOutcome.Struck);
            Play(ChikuoTimings.DiveLand, 0.04f);
            yield return HoleRoutine(BambooMasterMoves.Aterrizaje, null, null);
        }

        /// <summary>Le cortaron el bastón con las campanas blancas: se dobla y lo tira (el revolcón desde la pértiga).</summary>
        HitResult PoleWhip(Vector3 dir)
        {
            onPole = false;
            Log("latigazo a la pértiga");
            Sfx("bamboo_whip", "fin_whoosh", transform.position + Vector3.up * 1.2f, 1f);
            BambooGrove.Splinters(transform.position + Vector3.up * 1.2f, -dir);
            Run(PoleFallRoutine(dir));
            return HitResult.Hit;
        }

        IEnumerator PoleFallRoutine(Vector3 dir)
        {
            vuln = Vuln.None;
            var pf = ChikuoTimings.PoleFall;
            transform.rotation = Quaternion.LookRotation(-dir);
            Play(pf, 0.04f);
            yield return Until(1f);
            Vector3 start = transform.position + transform.rotation * pf.RootOffset;
            yield return FlingRoutine(null, dir, start, BambooMasterMoves.PoleRevolcon, BambooMasterMoves.PoleFlingM);
        }

        /// <summary>El salto atrás de 'meters' (HopBack, travel_m de 4 m escalado: todo el avance va en el aire).</summary>
        IEnumerator HopBack(float meters)
        {
            var c = ChikuoTimings.HopBack;
            float full = Mathf.Abs(c.TravelAt(1f));
            float room = ArenaRoom(transform.position, -transform.forward) - 1f;
            float k = full > 0.1f ? Mathf.Clamp(Mathf.Min(meters, room) / full, 0.2f, 1f) : 1f;
            Play(c, 0.06f);
            while (!ClipDone)
            {
                float x = c.TravelAt(ClipNorm) * k;
                float d = x - travelDone;
                travelDone = x;
                if (Mathf.Abs(d) > 1e-5f && !anim.Frozen) MoveBy(transform.forward * d);
                yield return null;
            }
        }

        /// <summary>Hasta dónde se puede ir por esa línea sin salir de la arena.</summary>
        float ArenaRoom(Vector3 o, Vector3 d)
        {
            Vector3 c = (o - arenaCenter).Flat();
            float r = Mathf.Max(1f, arenaRadius - 0.5f);
            float b = Vector3.Dot(c, d), disc = b * b - (c.sqrMagnitude - r * r);
            return disc <= 0f ? 0f : Mathf.Max(0f, -b + Mathf.Sqrt(disc));
        }

        // ================================================================== Pregunta y Respuesta
        struct Sprout { public float at; public Vector3 center; public bool fixd, cued, shown; public MizuchiMarks.Mark mark; }
        readonly List<Sprout> sprouts = new List<Sprout>(4);
        static readonly string[] Phrases3 = { "AAG", "AGA", "GAA" }, Phrases4 = { "AAAG", "AGAG", "GAGA" };

        /// <summary>
        /// Salta 3 m atrás y toca una frase de tres notas (cuatro desde el 52 %) con la flauta de costado; en el compás
        /// siguiente la repite como golpes con el mismo ritmo: nota aguda = dardo dorado (anillo a los pies), grave = brote
        /// rojo bajo Kaito (disco de 1 m fijo a 0.45 s). Contestarla entera sin recibir un golpe: Afinado (2.5 s, 4 cortes
        /// a x1.2). Cortarlo mientras toca: Desafinado (1.4 s, 2 cortes) y la frase se apaga.
        /// </summary>
        IEnumerator QuestionAnswer()
        {
            if (Teach("flute")) ShowTip(StoryText.Hint("bamboo_flute"));
            SetState(EnemyState.Scripted);
            vuln = Vuln.None;
            Face(TargetPos, 99f, 1f);
            yield return HopBack(3f);
            string phrase = Health01 <= BambooMasterMoves.QaFourFrom ? Phrases4[Random.Range(0, Phrases4.Length)] : Phrases3[Random.Range(0, Phrases3.Length)];
            fluting = true;
            qaFailed = false;
            var raise = ChikuoTimings.FluteRaise;
            Play(raise, 0.08f);
            vuln = Vuln.Flute;
            yield return Until(1f);
            float gap = BambooMasterMoves.NoteGap;
            // la pregunta: cada nota con su altura y su color (aguda: los hombros en dorado; grave: el ruedo en rojo)
            for (int i = 0; i < phrase.Length; i++)
            {
                bool high = phrase[i] == 'A';
                Play(ChikuoTimings.FluteNote, 0.03f);
                PlayNote(high, i);
                look.Tell(high ? BambooMasterLook.DartSlots : new[] { BambooMasterLook.ChimesLo }, !high, 0.8f);
                yield return Wait(gap);
                look.ClearTell();
            }
            // la respuesta: el mismo ritmo como golpes; la primera 0.85 s después de la última nota de la pregunta
            float first = Time.time + BambooMasterMoves.AnswerLead - gap;
            var def = BambooMasterMoves.Held("Respuesta", ChikuoTimings.FluteNote, AttackKind.Unblockable, BambooMasterMoves.AnswerLead, BambooMasterMoves.Dmg(BambooMasterMoves.Move.Sprout, phaseIdx), BambooMasterMoves.Answer);
            if (!StartMove(def)) { fluting = false; yield break; }
            Play(ChikuoTimings.FluteNote, 0.05f, 0.9f, 0.2f);
            sprouts.Clear();
            for (int i = 0; i < phrase.Length; i++)
            {
                float at = first + i * gap;
                if (phrase[i] == 'A') pending.Add(new PendingDart { at = at });
                else sprouts.Add(new Sprout { at = at, center = Floor(TargetPos) });
            }
            for (int i = 0; i < phrase.Length; i++)
            {
                float at = first + i * gap;
                bool high = phrase[i] == 'A';
                // la nota de la respuesta arranca su clip antes de su golpe (AnswerBlow/AnswerStamp pegan en el cuadro 4)
                var nc = high ? ChikuoTimings.AnswerBlow : ChikuoTimings.AnswerStamp;
                float hitN = high ? nc.EventAt("DartSpawn", 0) : nc.Event("Stamp");
                float startAt = at - Mathf.Max(0f, hitN) * nc.Seconds;
                while (Time.time < startAt) { TickSprouts(def); yield return null; }
                Play(nc, 0.03f);
                PlayNote(high, i);
                while (Time.time < at) { TickSprouts(def); yield return null; }
                if (high) FireDart();
                else Stamp(def);
            }
            while (sprouts.Count > 0) { TickSprouts(def); yield return null; }
            EndMove(TellOutcome.Struck);
            fluting = false;
            vuln = Vuln.None;
            if (!qaFailed)
            {
                Bark("afinado", true);
                Log("afinado");
                Play(ChikuoTimings.Tuned, 0.2f);
                yield return HoleRoutine(BambooMasterMoves.Afinado, "Tuned", null);
                yield return ReturnUp(true);
            }
        }

        void PlayNote(bool high, int i)
        {
            // la escala del tema: agudas y graves con su altura (sin las notas sintetizadas, el ping y el toc de madera)
            Sfx("flute_note_" + (high ? 4 + i % 2 : 1 + i % 2), high ? "pearl_ping" : "step_wood", Voice, 0.8f);
        }

        /// <summary>Los brotes por salir: el disco sigue a Kaito hasta 0.45 s antes y queda fijo; el "¡ya!" de cada uno.</summary>
        void TickSprouts(AttackDef def)
        {
            for (int i = 0; i < sprouts.Count; i++)
            {
                var s = sprouts[i];
                float eta = s.at - Time.time;
                if (!s.fixd)
                {
                    s.fixd = eta <= BambooMasterMoves.SproutFix;
                    s.center = Floor(TargetPos);
                }
                if (!s.shown && eta <= TellStyle.MaxUnblockable)
                {
                    s.shown = true;
                    if (Settings.ShowUnblockableAids) s.mark = marks?.Disc(s.center, BambooMasterMoves.SproutRadius);
                    Game.UI?.ShowDanger(this);
                    Game.Audio?.Play("tell_danger", s.center, 0.8f, 0.03f);
                }
                if (s.mark != null)
                {
                    s.mark.Move(s.center);
                    s.mark.Progress = 1f - Mathf.Clamp01((eta - TellStyle.BiasUnblockable) / (TellStyle.MaxUnblockable - TellStyle.BiasUnblockable));
                }
                if (!s.cued && AudioManager.CueDue(eta, TellStyle.TickUnblockable))
                {
                    s.cued = true;
                    Game.Audio?.Play("tell_tick", null, 0.8f, 0.03f);
                    GameEvents.RaiseStrikeCue(this, true);
                }
                sprouts[i] = s;
            }
        }

        /// <summary>La nota grave: golpea el piso con el bastón y brota el retoño donde quedó fijo el disco.</summary>
        void Stamp(AttackDef def)
        {
            if (sprouts.Count == 0) return;
            var s = sprouts[0];
            sprouts.RemoveAt(0);
            if (s.mark != null) marks.Finish(s.mark, true);
            Game.FX?.Shockwave(s.center, BambooMasterMoves.SproutRadius, new Color(0.6f, 0.85f, 0.4f));
            BambooGrove.Leaves(s.center + Vector3.up * 0.3f, 1f);
            Game.Audio?.Play("rock_impact", s.center, 0.5f, 0.1f);
            if (target != null && CombatMath.FlatDistance(TargetPos, s.center) <= BambooMasterMoves.SproutRadius + target.Radius)
            {
                var r = HitPlayer(def, s.center);
                if (r == HitResult.Hit || r == HitResult.Killed) qaFailed = true;
            }
        }

        bool NextSproutArea(out TellArea area)
        {
            area = default;
            if (sprouts.Count == 0) return false;
            area = new TellArea { origin = sprouts[0].center, size = BambooMasterMoves.SproutRadius };
            return true;
        }

        void ClearSprouts()
        {
            foreach (var s in sprouts) if (s.mark != null) marks?.Finish(s.mark, false);
            sprouts.Clear();
            fluting = false;
        }

        /// <summary>Lo cortaron mientras toca: "¡Me hiciste desafinar!" (1.4 s, 2 cortes) y la frase se apaga en gris.</summary>
        HitResult Detune(in DamageInfo info)
        {
            Bark("desafinado", true);
            Log("desafinado");
            Sfx("flute_squeak", "parry_whiff", Voice, 0.8f);
            Run(SimpleHole(ChikuoTimings.Detuned, BambooMasterMoves.Desafinado, null, false));
            return HitResult.Hit;
        }
    }
}
