using System.Collections;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Arriba de las cañas (fases 1 y 3; diseño 4.1, 5.1, 5.2, 7 y 2): qué decide posado, los dardos, colgado, la risa, el
    /// barrido de caña, la picada y el bastón que cae, los saltos (con la caída del cielo), la vuelta arriba (trepando, de un
    /// salto o con la garrocha), el latigazo con sus resultados (revolcón, estampado, resbalón, tropiezo) y los huecos.
    /// </summary>
    public partial class BambooMasterBoss
    {
        enum PerchAct { Dart, Dart2, Volley, Whistle, Hang, Laugh, MasterLaugh, Sweep, Leap, Dive, StaffDrop, Catapult, Tala }

        /// <summary>Las tres primeras acciones de la pelea (arrancando en la fase 1): Dardo, Dardo, Tres Notas con la
        /// inspiración exagerada (+0.6 s de carga). Es la lección: la caña reacciona, pero no así; y después, así sí.</summary>
        int firstActions;
        bool firstVolleyDone;
        const float FirstVolleyExtra = 0.6f;
        int actionsOnStalk;
        bool justLanded, hanging, leaving, revanchaPending;
        float lastSweep = -99f, lastDive = -99f, lastDrop = -99f, lastCatapult = -99f, lastTala = -99f;
        int tickles;
        /// <summary>Fase 3: cuándo toca su próxima firma (catapulta, tala o la ráfaga de cuatro); -1 = sin agendar.</summary>
        float nextSignatureAt = -1f;

        // ================================================================== el cerebro
        /// <summary>La pelea, mientras dure: en la fase 2 (o sin caña libre en la 3) pelea en el piso; si no, vuelve arriba
        /// y decide posado. Las interrupciones (latigazo, contra, cambio de fase) terminan volviendo acá.</summary>
        IEnumerator Brain()
        {
            while (IsAlive && Fighting)
            {
                bool up = body == Body.Perch && perch != null && perch.Standing;
                if (phaseIdx == 1 || !up && !HasFreeStalk()) { yield return GroundBrain(); continue; }
                if (!up)
                {
                    // (una acción cortada en el aire, o su caña ya no está): al piso y de vuelta arriba
                    if (body != Body.Ground) Landed((perch != null ? perch.Base : transform.position) + FaceDirFrom(transform.position) * 1.2f, FaceDirFrom(transform.position));
                    yield return ReturnUp(false);
                    // sin caña posible este frame no gira en el lugar
                    if (body != Body.Perch) yield return null;
                    continue;
                }
                yield return PerchTurn();
            }
        }

        /// <summary>¿Tiene una caña adonde subir? En pie y sin Kaito al pie (con todas quebradas, o Kaito debajo de la única
        /// que queda, pelea en el piso: la coda de la fase 3).</summary>
        bool HasFreeStalk()
        {
            if (grove == null) return false;
            Vector3 k = TargetPos;
            foreach (var s in grove.All)
                if (BambooGrove.Perchable(s, phaseIdx) && (s.Base - k).Flat().magnitude >= BambooMasterMoves.PerchMinDist) return true;
            return false;
        }

        bool LastSong => phaseIdx >= 2 && Health01 <= BambooMasterMoves.LastSong;

        // ================================================================== posado
        IEnumerator PerchTurn()
        {
            vuln = Vuln.Tickle;
            hanging = leaving = false;
            if (!justLanded)
            {
                // respira hamacándose con la caña (nunca quieto); recién posado arranca sin respiro
                if (clip != ChikuoTimings.PerchIdle) Play(ChikuoTimings.PerchIdle, 0.15f);
                perch.SetLoad(6f, FaceDirFrom(perch.Base));
                Vector2 b = BambooMasterMoves.Breath[phaseIdx];
                float wait = Random.Range(b.x, b.y), t = 0f;
                while (t < wait)
                {
                    if (!anim.Frozen) t += Time.deltaTime;
                    if (campFor >= BambooMasterMoves.CampTime && Time.time - lastSweep >= BambooMasterMoves.CampEvery) break;
                    yield return null;
                }
            }
            justLanded = false;
            if (LastSong) Bark("ultima");
            var a = Decide();
            if (a != PerchAct.Leap) actionsOnStalk++;
            yield return DoPerch(a);
        }

        /// <summary>Qué hace posado (sección 7.1, en orden: lo primero que se cumple).</summary>
        PerchAct Decide()
        {
            Vector3 k = TargetPos;
            float d = (k - perch.Base).Flat().magnitude;
            // 1. fuera de cuadro: salta a una caña en cuadro (nunca ataca desde fuera)
            if (!BambooGrove.Framed(BambooGrove.PerchHead(perch), k)) return PerchAct.Leap;
            // 2. las tres primeras de la pelea
            if (firstActions < 3) { firstActions++; return firstActions == 3 ? PerchAct.Volley : PerchAct.Dart; }
            // 3. acampan debajo
            if (campFor >= BambooMasterMoves.CampTime && Time.time - lastSweep >= BambooMasterMoves.CampEvery) return PerchAct.Sweep;
            // 3b. fase 3: su firma cada 9-12 s (la primera a los 5-7): la fase no es el bucle de la 1 más rápido, cambia de
            // forma (la tala con una caña rajada, la catapulta de lejos, si no la ráfaga de cuatro desde arriba)
            if (phaseIdx >= 2)
            {
                if (nextSignatureAt < 0f) nextSignatureAt = Time.time + Random.Range(BambooMasterMoves.SignatureFirst.x, BambooMasterMoves.SignatureFirst.y);
                else if (Time.time >= nextSignatureAt)
                {
                    nextSignatureAt = Time.time + Random.Range(BambooMasterMoves.SignatureEvery.x, BambooMasterMoves.SignatureEvery.y);
                    if (TalaTarget() != null) return PerchAct.Tala;
                    if (d >= BambooMasterMoves.CatapultMinDist) return PerchAct.Catapult;
                    return PerchAct.Volley;
                }
            }
            bool hit = dartHitPending;
            dartHitPending = false;
            // 4. Kaito al pie (y él sin cargar): le contesta
            if (d <= BambooMasterMoves.ReactDist)
            {
                float wH = 0.30f, wS = d <= 3.4f && Time.time - lastSweep >= 3f ? 0.20f : 0f, wD = Time.time - lastDive >= 3f ? 0.15f : 0f,
                      wB = Time.time - lastDrop >= 3f ? 0.15f : 0f, wL = 0.20f;
                float r = Random.value * (wH + wS + wD + wB + wL);
                if ((r -= wH) < 0f) return PerchAct.Hang;
                if ((r -= wS) < 0f) return PerchAct.Sweep;
                if ((r -= wD) < 0f) return PerchAct.Dive;
                if ((r -= wB) < 0f) return PerchAct.StaffDrop;
                return PerchAct.Leap;
            }
            // 5. tres cargas seguidas sin corte: la Risa del Maestro ("¿Y? ¿No me vas a bajar?")
            if (loadsUncut >= 3) { loadsUncut = 0; return PerchAct.MasterLaugh; }
            // 6. un dardo suyo le pegó: a veces se ríe (cargada)
            if (hit && Random.value < 0.3f) return PerchAct.Laugh;
            // 7. ya hizo sus acciones en esta caña
            if (actionsOnStalk >= (LastSong ? 1 : BambooMasterMoves.MaxOnStalk)) return PerchAct.Leap;
            // 8. por pesos (Kaito lejos)
            bool p3 = phaseIdx >= 2;
            float w1 = 1.0f, w2 = 0.8f, wV = d >= 3.5f ? 1.2f : 0f,
                  wW = Health01 <= BambooMasterMoves.WhistleFrom && d >= 5f ? 0.6f : 0f,
                  wHg = d <= 7f ? 0.6f : 0f, wLp = actionsOnStalk >= 1 ? 0.6f : 0f,
                  wDv = Time.time - lastDive >= 5f ? 0.4f : 0f, wSd = Time.time - lastDrop >= 5f ? 0.3f : 0f,
                  wC = p3 && d >= BambooMasterMoves.CatapultMinDist && Time.time - lastCatapult >= BambooMasterMoves.CatapultEvery ? BambooMasterMoves.CatapultWeight : 0f,
                  wT = p3 && Time.time - lastTala >= 7f && TalaTarget() != null ? 0.9f : 0f;
            float sum = w1 + w2 + wV + wW + wHg + wLp + wDv + wSd + wC + wT;
            float x = Random.value * sum;
            if ((x -= w1) < 0f) return PerchAct.Dart;
            if ((x -= w2) < 0f) return PerchAct.Dart2;
            if ((x -= wV) < 0f) return PerchAct.Volley;
            if ((x -= wW) < 0f) return PerchAct.Whistle;
            if ((x -= wHg) < 0f) return PerchAct.Hang;
            if ((x -= wLp) < 0f) return PerchAct.Leap;
            if ((x -= wDv) < 0f) return PerchAct.Dive;
            if ((x -= wSd) < 0f) return PerchAct.StaffDrop;
            if ((x -= wC) < 0f) return PerchAct.Catapult;
            return PerchAct.Tala;
        }

        IEnumerator DoPerch(PerchAct a)
        {
            bool p3 = phaseIdx >= 2;
            switch (a)
            {
                case PerchAct.Dart: return DartAct(ChikuoTimings.PerchDart, 0f);
                case PerchAct.Dart2: return DartAct(ChikuoTimings.PerchDart2, 0f);
                case PerchAct.Volley:
                {
                    // la primera Tres Notas de la pelea: la inspiración exagerada
                    float extra = firstActions == 3 && phaseIdx == 0 && !firstVolleyDone ? FirstVolleyExtra : 0f;
                    firstVolleyDone = true;
                    return DartAct(p3 ? ChikuoTimings.PerchVolley4 : ChikuoTimings.PerchVolley, extra);
                }
                case PerchAct.Whistle: return WhistleAct();
                case PerchAct.Hang: return HangAct((TargetPos - perch.Base).Flat().magnitude <= BambooMasterMoves.ReactDist);
                case PerchAct.Laugh: return LaughAct(false);
                case PerchAct.MasterLaugh: return LaughAct(true);
                case PerchAct.Sweep: return SweepAct(false);
                case PerchAct.Dive: return DiveAct();
                case PerchAct.StaffDrop: return StaffDropAct();
                case PerchAct.Catapult: return CatapultAct();
                case PerchAct.Tala: return TalaAct();
                default: return LeapAct(null);
            }
        }

        // ------------------------------------------------------------------ dardos (Dardo, Dos Dardos, Tres y Cuatro Notas)
        /// <summary>
        /// Baja la flauta de los hombros a la boca, apunta y sopla (los cascabeles de los hombros: dos golpecitos agudos). La
        /// ráfaga se echa atrás y carga la caña (Load ... Unload del sidecar): campanas blancas, ensō en la base. 'extra'
        /// estira el tramo de la carga antes del primer soplido (la inspiración exagerada de las primeras Tres Notas).
        /// </summary>
        IEnumerator DartAct(ChikuoClip c, float extra)
        {
            vuln = Vuln.Tickle;
            Play(c, 0.12f);
            float load = c.Event("Load"), unload = c.Event("Unload"), first = c.EventAt("DartSpawn", 0);
            if (extra > 0f && load >= 0f && first > load)
            {
                float seg = (first - load) * c.Seconds;
                slowFrom = load * c.Seconds;
                slowTo = first * c.Seconds;
                slowRate = seg / (seg + extra);
            }
            int n = c.EventCount("DartSpawn");
            for (int i = 0; i < n; i++) QueueDart(c.EventAt("DartSpawn", i));
            Sfx("tell_chime_hi", "pearl_ping", Voice, 0.45f);
            perch.SetLoad(6f, FaceDirFrom(perch.Base));
            bool loadedOn = false;
            int fired = 0;
            while (!ClipDone)
            {
                if (load >= 0f && !loadedOn && clipT >= load * c.Seconds)
                {
                    loadedOn = true;
                    Load(perch, RealUntil(unload));
                    // se echa atrás: la caña se arquea alejándose de Kaito
                    perch.SetLoad(20f, -FaceDirFrom(perch.Base));
                }
                while (fired < n && clipT >= c.EventAt("DartSpawn", fired) * c.Seconds - 1e-4f) { FireDart(); fired++; }
                yield return null;
            }
            while (fired < n) { FireDart(); fired++; }
        }

        // ------------------------------------------------------------------ colgado (la pose de la hoja original)
        /// <summary>
        /// Se deja caer cabeza abajo colgado de las corvas y le sopla dos dardos de cerca; vuelve con un abdominal. Cargada
        /// hasta el Unload de HangClimb: cortada, cae de cabeza. Con Kaito ya al pie ('near') la carga recién prende 0.15 s
        /// antes del primer dardo: si no, el corte llegaba antes de que existiera un dardo y el colgado era un latigazo
        /// gratis; así es "su ataque es tu hueco": parar o esquivar el primero y cortar antes del segundo.
        /// </summary>
        IEnumerator HangAct(bool near)
        {
            vuln = Vuln.Tickle;
            hanging = true;
            var drop = ChikuoTimings.HangDrop;
            var blow = ChikuoTimings.HangDart2;
            var up = ChikuoTimings.HangClimb;
            Play(drop, 0.08f);
            float total = drop.Seconds + blow.Seconds + Mathf.Max(0f, up.Event("Unload")) * up.Seconds;
            float loadAt = near ? Mathf.Max(0f, drop.Seconds + blow.EventAt("DartSpawn", 0) * blow.Seconds - BambooMasterMoves.HangNearLoadLead) : 0f;
            float t = 0f;
            bool loadedOn = false;
            perch.SetLoad(30f, FaceDirFrom(perch.Base));
            // los dos dardos por salir ya cuentan para el anillo de los pies (la ETA honesta)
            for (int i = 0; i < blow.EventCount("DartSpawn"); i++)
                pending.Add(new PendingDart { at = Time.time + drop.Seconds + blow.EventAt("DartSpawn", i) * blow.Seconds });
            while (true)
            {
                if (!loadedOn && t >= loadAt) { loadedOn = true; Load(perch, total - t); }
                if (ClipDone) break;
                yield return null;
                if (!anim.Frozen) t += Time.deltaTime;
            }
            Play(blow, 0f);
            Sfx("tell_chime_hi", "pearl_ping", Voice, 0.45f);
            int fired = 0, n = blow.EventCount("DartSpawn");
            while (!ClipDone)
            {
                if (!loadedOn && t >= loadAt) { loadedOn = true; Load(perch, total - t); }
                while (fired < n && clipT >= blow.EventAt("DartSpawn", fired) * blow.Seconds - 1e-4f) { FireDart(); fired++; }
                yield return null;
                if (!anim.Frozen) t += Time.deltaTime;
            }
            while (fired < n) { FireDart(); fired++; }
            Play(up, 0f);
            perch.SetLoad(6f, FaceDirFrom(perch.Base));
            yield return Until(1f);
            hanging = false;
        }

        // ------------------------------------------------------------------ la risa
        /// <summary>Se ríe a carcajadas sacudiendo las campanas: cargada entera (es la revancha de Kaito). La del maestro
        /// (2 s) sale después de tres cargas sin corte y trae la pista de vuelta.</summary>
        IEnumerator LaughAct(bool master)
        {
            vuln = Vuln.Tickle;
            float len = master ? 2.0f : ChikuoTimings.PerchLaugh.Seconds;
            Play(ChikuoTimings.PerchLaugh, 0.15f);
            Load(perch, len);
            perch.SetLoad(6f, FaceDirFrom(perch.Base));
            perch.Wobble(10f, 3f, len);
            if (master)
            {
                Bark("maestro", true);
                ShowTip(StoryText.Hint("bamboo_whip"));
            }
            else Bark("risa");
            yield return Wait(len);
        }

        // ------------------------------------------------------------------ el barrido de caña (rojo)
        /// <summary>
        /// Se cuelga del costado y la caña barre un disco de 3.6 m alrededor de su base (con Kaito al pie, o porque se la
        /// cortaron sin campanas: primero manotea 0.25 s). Rojo: dash o salir.
        /// </summary>
        IEnumerator SweepAct(bool afterTickle)
        {
            lastSweep = Time.time;
            campFor = 0f;
            vuln = Vuln.Tickle;
            if (afterTickle)
            {
                Play(ChikuoTimings.PerchWobble, 0.04f);
                yield return Until(1f);
            }
            var c = ChikuoTimings.StalkSweep;
            var def = BambooMasterMoves.Held("Barrido de Caña", c, AttackKind.Unblockable, c.Contact * c.Seconds, BambooMasterMoves.Dmg(BambooMasterMoves.Move.Sweep, phaseIdx), BambooMasterMoves.Sweep);
            if (!StartMove(def)) yield break;
            Play(c, 0.1f);
            heldStrikeAt = c.Contact;
            SetDiscArea(perch.Base, c.RingM);
            heldSlots = BambooMasterLook.RedSlots;
            Sfx("tell_chime_cascade", null, Voice, 0.7f);
            Vector3 toward = FaceDirFrom(perch.Base);
            while (clipT < c.Contact * c.Seconds)
            {
                perch.SetLoad(Mathf.Lerp(6f, 40f, ClipNorm / c.Contact), toward);
                yield return null;
            }
            heldStruck = true;
            EndTell(TellOutcome.Struck);
            perch.Whip();
            Game.FX?.Shockwave(perch.Base, c.RingM, new Color(0.85f, 0.8f, 0.6f));
            BambooGrove.Leaves(perch.Base + Vector3.up * 2f, 1.2f);
            Game.Audio?.Play("ability_wind", perch.Base, 0.8f, 0.1f);
            if (target != null && CombatMath.FlatDistance(TargetPos, perch.Base) <= c.RingM + target.Radius) HitPlayer(def, perch.Base);
            yield return Until(1f);
            EndMove(TellOutcome.Struck);
        }

        // ------------------------------------------------------------------ la picada de la grulla (rojo)
        /// <summary>
        /// La patada voladora del concepto: posado hasta LeaveStalk, el disco de 1.6 m sigue a Kaito hasta 0.50 s del golpe y
        /// queda fijo; el código lo lleva por el arco hasta el disco. Esquivarla con el dash perfecto le entierra los pies.
        /// </summary>
        IEnumerator DiveAct()
        {
            lastDive = Time.time;
            vuln = Vuln.Tickle;
            var c = ChikuoTimings.Dive;
            float leave = c.Event("LeaveStalk"), contact = c.Contact;
            var def = BambooMasterMoves.Held("Picada de la Grulla", c, AttackKind.Unblockable, contact * c.Seconds, BambooMasterMoves.Dmg(BambooMasterMoves.Move.Dive, phaseIdx), BambooMasterMoves.Dive, c.RingM);
            if (!StartMove(def)) yield break;
            Play(c, 0.08f);
            heldStrikeAt = contact;
            heldSlots = BambooMasterLook.KickSlots;
            Sfx("tell_chime_cascade", null, Voice, 0.7f);
            Vector3 land = TargetPos;
            bool fix = false;
            SetDiscArea(land, c.RingM);
            while (clipT < leave * c.Seconds)
            {
                if (!fix) { fix = RealUntil(contact) <= BambooMasterMoves.DiveFix; land = TargetPos; SetDiscArea(land, c.RingM); }
                yield return null;
            }
            // sale de la caña: la caña lo despide para atrás
            perch?.Shake(-FaceDirFrom(perch.Base), 120f);
            Vector3 from = model.position;
            vuln = Vuln.None;
            look.BeginLimbTrail(BambooMasterLook.KickSlots, true);
            while (clipT < contact * c.Seconds - 1e-4f)
            {
                if (!fix) { fix = RealUntil(contact) <= BambooMasterMoves.DiveFix; land = Floor(TargetPos); SetDiscArea(land, c.RingM); }
                float s = Mathf.InverseLerp(leave, contact, ClipNorm);
                Vector3 dir = (land - from).Flat();
                Carry(Arc(from, land, s, 0.5f), Quaternion.LookRotation(dir.sqrMagnitude > 1e-4f ? dir : transform.forward));
                yield return null;
            }
            heldStruck = true;
            EndTell(TellOutcome.Struck);
            land = Floor(land);
            Landed(land, (land - from).Flat());
            Game.FX?.Shockwave(land, c.RingM, new Color(1f, 0.55f, 0.4f));
            Game.FX?.GroundCrack(land, c.RingM * 0.8f);
            Game.Camera?.Shake(0.5f);
            Game.Audio?.Play("slam", land, 0.9f);
            var r = HitResult.Ignored;
            if (target != null && CombatMath.FlatDistance(TargetPos, land) <= c.RingM + target.Radius) r = HitPlayer(def, land);
            EndMove(TellOutcome.Struck);
            look.StopLimbTrail();
            if (r == HitResult.Dodged && PerfectDodge)
            {
                // los pies enterrados hasta el tobillo: tironea (la esquiva perfecta lo dejó clavado)
                Play(ChikuoTimings.FeetStuck, 0.05f);
                yield return HoleRoutine(BambooMasterMoves.Pies, null, null);
                yield return ReturnUp(true);
                yield break;
            }
            Play(ChikuoTimings.DiveLand, 0.04f);
            yield return HoleRoutine(BambooMasterMoves.Aterrizaje, null, null);
            yield return ReturnUp(false);
        }

        // ------------------------------------------------------------------ el bastón que cae (dorado)
        /// <summary>Sale de la caña, cae a 1.6 m de Kaito (de su lado) con el bastón en alto y lo baja de golpe: parry (la
        /// Contra). El lugar se elige a 0.40 s.</summary>
        IEnumerator StaffDropAct()
        {
            lastDrop = Time.time;
            vuln = Vuln.Tickle;
            var c = ChikuoTimings.StaffDrop;
            float leave = c.Event("LeaveStalk"), landN = c.Event("Land"), contact = c.Contact;
            var def = BambooMasterMoves.Held("Bastón que Cae", c, AttackKind.Heavy, contact * c.Seconds, BambooMasterMoves.Dmg(BambooMasterMoves.Move.StaffDrop, phaseIdx), BambooMasterMoves.StaffDrop);
            def.arc = 90f;
            // el bot mira el alcance del golpe desde la raíz: desde la caña llega hasta donde cae
            def.range = (TargetPos - transform.position).Flat().magnitude + c.ReachM;
            if (!StartMove(def)) yield break;
            Play(c, 0.08f);
            heldStrikeAt = contact;
            heldSlots = BambooMasterLook.DropSlots;
            Vector3 land = PickDropPoint();
            // la zona del golpe: el disco de su alcance alrededor de donde cae (el bot y el anillo la miran)
            SetDiscArea(land, c.ReachM);
            while (clipT < leave * c.Seconds) { land = PickDropPoint(); SetDiscArea(land, c.ReachM); yield return null; }
            perch?.Shake(-FaceDirFrom(perch.Base), 100f);
            Vector3 from = model.position;
            vuln = Vuln.None;
            bool picked = false;
            float start = Time.time - clipT / Mathf.Max(0.01f, clipRate);
            while (clipT < landN * c.Seconds - 1e-4f)
            {
                if (!picked && Time.time - start < BambooMasterMoves.StaffDropPick) { land = PickDropPoint(); SetDiscArea(land, c.ReachM); }
                else picked = true;
                float s = Mathf.InverseLerp(leave, landN, ClipNorm);
                Carry(Arc(from, land, s, 0.8f), Quaternion.LookRotation(FaceDirFrom(Arc(from, land, s, 0f))));
                yield return null;
            }
            Landed(land, FaceDirFrom(land));
            Game.FX?.Dust(land, 1.2f);
            while (clipT < contact * c.Seconds - 1e-4f)
            {
                // gira hacia Kaito hasta 0.2 s antes (desde ahí el bastón baja recto y correrse sirve)
                if (RealUntil(contact) > TrackingStopLead) Face(TargetPos, 1.5f, Time.deltaTime);
                yield return null;
            }
            heldStruck = true;
            EndTell(TellOutcome.Struck);
            trail?.Begin();
            Game.Audio?.Play("slam", transform.position + transform.forward * 1.6f, 0.7f, 0.1f);
            Game.FX?.Dust(transform.position + transform.forward * 1.8f, 0.9f);
            if (target != null && CombatMath.InArc(transform, TargetPos, c.ReachM, def.arc, target.Radius)) HitPlayer(def, transform.position);
            yield return Until(1f);
            trail?.Stop();
            EndMove(TellOutcome.Struck);
            Play(ChikuoTimings.StaffDropRecover, 0.05f);
            yield return Until(1f);
            yield return ReturnUp(false);
        }

        /// <summary>Dónde cae el bastón que cae: a 1.6 m de Kaito, de su lado (adentro de la arena).</summary>
        Vector3 PickDropPoint()
        {
            Vector3 k = TargetPos;
            Vector3 from = perch != null ? perch.Base : transform.position;
            Vector3 d = (from - k).Flat();
            d = d.sqrMagnitude > 1e-4f ? d.normalized : Vector3.forward;
            return grove.FlingLanding(k, d, BambooMasterMoves.StaffDropNear);
        }

        // ================================================================== saltos entre cañas
        /// <summary>
        /// Salta a otra caña: se agacha mirando la de destino (cascabeles graves; el ensō blanco aparece en el destino desde
        /// el agachado), vuela por un arco de 1.8 m de comba y se agarra (cargado 0.20 s). Sin destino posible, la picada.
        /// </summary>
        IEnumerator LeapAct(BambooStalk dest)
        {
            if (dest == null) dest = grove.PickDestination(perch, TargetPos, phaseIdx, BambooMasterMoves.LeapDest[phaseIdx]);
            if (dest == null) { yield return DiveAct(); yield break; }
            actionsOnStalk = 0;
            vuln = Vuln.Tickle;
            leaving = true;
            leapFrom = perch;
            leapDest = dest;
            dest.Mark(true);
            Sfx("tell_chime_lo", "step_wood", Voice, 0.6f);
            perchFaceLock = true;
            perchFaceDir = (dest.Base - perch.Base).Flat().normalized;
            // fase 3: mira la caña de destino un instante antes de agacharse (con el agachado a x1.57 la caída del cielo no
            // se podía leer a tiempo)
            if (BambooMasterMoves.LeapLook[phaseIdx] > 0f) yield return Wait(BambooMasterMoves.LeapLook[phaseIdx]);
            var cr = ChikuoTimings.LeapCrouch;
            Play(cr, 0.08f, 0f, BambooMasterMoves.LeapCrouchRate[phaseIdx]);
            perch.SetLoad(12f, -perchFaceDir);
            yield return Until(1f);
            yield return Flight(model.position + model.rotation * cr.RootOffset, model.rotation, dest, true, true, ChikuoTimings.LeapAir, -1f);
            // fase 3: el ping-pong (encadena otro salto al caer)
            if (phaseIdx >= 2 && Random.value < BambooMasterMoves.PingPong && perch != null && IsAlive && !phaseChanging)
            {
                var next = grove.PickDestination(perch, TargetPos, phaseIdx, BambooMasterMoves.LeapDest[phaseIdx]);
                if (next != null) yield return LeapAct(next);
            }
        }

        /// <summary>
        /// El vuelo hasta la caña 'dest' (de un salto, de la garrocha, del agachado del piso): la raíz del clip de vuelo va de
        /// 'start' al punto del agarre (el PerchNode de destino más el RootOffset de LeapGrab: llega con el culmo adelante a su
        /// derecha) en LeapBase + LeapPerM por metro. Cortar la caña de destino en los últimos 0.45 s: la caída del cielo.
        /// 'air' sigue sonando (LeapAir en loop, o el resto de la garrocha); 'duration' &lt; 0 = la del salto. La garrocha y la
        /// escena del cambio 2 no se atajan ('catchable' false: invulnerable).
        /// </summary>
        IEnumerator Flight(Vector3 start, Quaternion startRot, BambooStalk dest, bool grabLoaded, bool catchable, ChikuoClip air, float duration)
        {
            var from = perch;
            if (from != null) from.Shake(-(dest.Base - from.Base), 140f);
            if (air == ChikuoTimings.LeapAir) Play(air, 0.06f);
            float dist = (dest.S.PerchNode.position - start).Flat().magnitude;
            float T = duration > 0f ? duration : (BambooMasterMoves.LeapBase + BambooMasterMoves.LeapPerM * dist) * BambooMasterMoves.LeapK[phaseIdx];
            leapDest = dest;
            leapFrom = from ?? leapFrom;
            dest.Mark(true);
            vuln = catchable ? Vuln.Air : Vuln.None;
            leapGrabAt = catchable ? Time.time + T : -1f;
            if (catchable && (dest.Base - TargetPos).Flat().magnitude <= BambooMasterMoves.CatchHint && Teach("deny")) ShowTip(StoryText.Hint("bamboo_deny"));
            float t = 0f;
            Vector3 travel = (dest.Base - start).Flat();
            while (t < T)
            {
                if (!anim.Frozen) t += Time.deltaTime;
                float u = Mathf.Clamp01(t / T);
                Quaternion rd = DestRot(dest);
                Vector3 end = dest.S.PerchNode.position + rd * ChikuoTimings.LeapGrab.RootOffset;
                Quaternion travelRot = Quaternion.LookRotation(travel.sqrMagnitude > 1e-4f ? travel.normalized : transform.forward);
                Quaternion rot = u < 0.5f ? Quaternion.Slerp(startRot, travelRot, u * 2f) : Quaternion.Slerp(travelRot, rd, (u - 0.5f) * 2f);
                Carry(Arc(start, end, u, BambooMasterMoves.LeapArc), rot);
                leapCatchable = catchable && T - t <= BambooMasterMoves.CatchWindow[phaseIdx];
                yield return null;
            }
            leapCatchable = false;
            leapGrabAt = -1f;
            dest.Mark(false);
            leapDest = leapFrom = null;
            vuln = Vuln.None;
            leaving = false;
            PerchOn(dest);
            perchYaw = DestRot(dest);
            perchFaceLock = false;
            var g = ChikuoTimings.LeapGrab;
            Play(g, 0f);
            dest.Shake(travel, 150f);
            Sfx("step_wood", null, Voice, 0.6f);
            if (grabLoaded) Load(dest, g.Seconds); else vuln = Vuln.Tickle;
            yield return Until(1f);
            justLanded = true;
        }

        /// <summary>El giro del posado en 's' mirando a Kaito (como lo va a dibujar PlaceModel).</summary>
        Quaternion DestRot(BambooStalk s)
        {
            Vector3 up = s.S.PerchNode != null ? s.S.PerchNode.up : Vector3.up;
            Vector3 f = Vector3.ProjectOnPlane(FaceDirFrom(s.Base), up);
            return Quaternion.LookRotation(f.sqrMagnitude > 1e-4f ? f.normalized : Vector3.forward, up);
        }

        /// <summary>Un arco de 'a' a 'b' (u 0..1) con 'hump' m de comba.</summary>
        static Vector3 Arc(Vector3 a, Vector3 b, float u, float hump) => Vector3.Lerp(a, b, u) + Vector3.up * (hump * 4f * u * (1f - u));

        Vector3 Floor(Vector3 p) { p.y = grove != null ? grove.FloorY : p.y; return p; }

        /// <summary>Tocó el piso en 'p' mirando 'facing': el cuerpo vuelve a la raíz (con su agente y su cápsula).</summary>
        void Landed(Vector3 p, Vector3 facing)
        {
            p = Floor(p);
            transform.position = p;
            if (facing.Flat().sqrMagnitude > 1e-4f) transform.rotation = Quaternion.LookRotation(facing.Flat().normalized);
            SetBody(Body.Ground);
            returnCutUsed = false;
        }

        // ================================================================== vuelta arriba (5.2)
        /// <summary>
        /// De vuelta a las cañas. Después de un hueco: se levanta de un salto (invulnerable), en la fase 3 contesta con la
        /// Revancha si Kaito está encima, y sube con la garrocha (invulnerable). Después de una bajada (picada, bastón que
        /// cae): a veces un bastonazo con Kaito cerca, y trepa si cayó al lado de una caña (cargado: Resbalón) o se agacha y
        /// salta (cortarle el agachado: Tropiezo). Una sola vez por bajada se lo puede cortar volviendo.
        /// </summary>
        IEnumerator ReturnUp(bool afterHole)
        {
            if (phaseChanging) yield break;
            if (body != Body.Ground) yield break;
            if (afterHole)
            {
                vuln = Vuln.None;
                // el kip-up rápido (0.25 s): la vuelta de un hueco no es una escena
                Play(ChikuoTimings.GetUp, 0.1f, 0f, ChikuoTimings.GetUp.Seconds / BambooMasterMoves.GetUpTime);
                yield return Until(1f);
                if (revanchaPending && phaseIdx >= 2 && (TargetPos - transform.position).Flat().magnitude <= BambooMasterMoves.AfterLandStrikeDist)
                {
                    revanchaPending = false;
                    yield return GroundStrike(BambooMasterMoves.Bastonazo(phaseIdx, true));
                }
                revanchaPending = false;
                if (phaseIdx == 1 || !HasFreeStalk()) yield break;
                // cómo vuelve arriba varía (sin esto cada hueco terminaba en la misma garrocha invulnerable de 1.3 s, ~25
                // veces por pelea): lejos de Kaito, un salto común (se lo puede atajar); cerca, la garrocha, el agachado
                // cortable (el Tropiezo es chico) o dos bastonazos con la Contra y después trepa
                float d = (TargetPos - transform.position).Flat().magnitude;
                float r = Random.value;
                if (d >= BambooMasterMoves.RecoverLeapDist || r >= BambooMasterMoves.RecoverVault && r < BambooMasterMoves.RecoverVault + BambooMasterMoves.RecoverCrouch)
                {
                    returnCutUsed = false;
                    yield return CrouchLeapAct();
                }
                else if (r >= BambooMasterMoves.RecoverVault + BambooMasterMoves.RecoverCrouch && d <= BambooMasterMoves.RecoverTandaDist)
                {
                    yield return GroundTanda(BambooMasterMoves.RecoveryTanda(phaseIdx));
                    returnCutUsed = true;
                    if (body == Body.Ground && HasFreeStalk()) yield return ClimbOrCrouch();
                }
                else yield return VaultAct();
                yield break;
            }
            if ((TargetPos - transform.position).Flat().magnitude <= BambooMasterMoves.AfterLandStrikeDist && Random.value < BambooMasterMoves.AfterLandStrikeChance)
                yield return GroundStrike(BambooMasterMoves.Bastonazo(phaseIdx, false));
            if (phaseIdx == 1 || !HasFreeStalk() || body != Body.Ground) yield break;
            yield return ClimbOrCrouch();
        }

        IEnumerator ClimbOrCrouch()
        {
            var near = NearestClimbable();
            if (near != null) yield return ClimbAct(near);
            else yield return CrouchLeapAct();
        }

        /// <summary>Un bastonazo de piso con la maquinaria de Enemy (aviso dorado, parry: la Contra salvo la Revancha).</summary>
        IEnumerator GroundStrike(AttackDef a)
        {
            vuln = Vuln.Armor;
            Face(TargetPos, 99f, 1f);
            clip = null;   // el golpe lo toca Enemy con su línea de tiempo
            if (!StartMove(a)) yield break;
            while (State == EnemyState.Attack) yield return null;
            vuln = Vuln.None;
        }

        /// <summary>Una tanda corta de piso (la vuelta de un hueco): la arma Enemy; el último golpe desviado abre la Contra.</summary>
        IEnumerator GroundTanda(AttackPattern p)
        {
            vuln = Vuln.Armor;
            Face(TargetPos, 99f, 1f);
            clip = null;
            pattern = p;
            StartAttack(false);
            while (State == EnemyState.Attack) yield return null;
            vuln = Vuln.None;
        }

        BambooStalk NearestClimbable()
        {
            BambooStalk best = null;
            float bd = BambooMasterMoves.ClimbReach;
            foreach (var s in grove.All)
            {
                if (!BambooGrove.Perchable(s, phaseIdx)) continue;
                float d = (s.Base - transform.position).Flat().magnitude;
                // con Kaito al pie de esa caña no trepa (se la cortaría en la cara)
                if (d > bd || (s.Base - TargetPos).Flat().magnitude < 1.8f) continue;
                bd = d;
                best = s;
            }
            return best;
        }

        /// <summary>Trepa desde el piso (el trepar del concepto: dos tirones, los pies contra el culmo), cargado entero:
        /// cortada, se resbala (Resbalón).</summary>
        IEnumerator ClimbAct(BambooStalk s)
        {
            var c = ChikuoTimings.Climb;
            climbFrom = transform.position;
            PerchOn(s);
            climbBlend = 1f;
            Play(c, 0.1f);
            if (!returnCutUsed) { vuln = Vuln.Climb; Load(s, c.Seconds); }
            else vuln = Vuln.None;
            float grab = Mathf.Max(0.01f, c.AirEnd > 0f ? c.AirEnd : c.Event("GrabStalk"));
            while (!ClipDone)
            {
                climbBlend = 1f - Mathf.Clamp01(ClipNorm / grab);
                yield return null;
            }
            climbBlend = 0f;
            vuln = Vuln.Tickle;
            justLanded = true;
        }

        /// <summary>Se agacha (cortable: Tropiezo) y salta a una caña.</summary>
        IEnumerator CrouchLeapAct()
        {
            var dest = grove.PickDestination(null, TargetPos, phaseIdx, BambooMasterMoves.LeapDest[phaseIdx]) ?? FarthestStalk();
            if (dest == null) yield break;
            var c = ChikuoTimings.JumpCrouch;
            Vector3 dir = (dest.Base - transform.position).Flat();
            if (dir.sqrMagnitude > 1e-4f) transform.rotation = Quaternion.LookRotation(dir.normalized);
            leapFrom = null;
            leapDest = dest;
            dest.Mark(true);
            Play(c, 0.1f);
            vuln = returnCutUsed ? Vuln.None : Vuln.Crouch;
            Sfx("tell_chime_lo", "step_wood", Voice, 0.6f);
            yield return Until(1f);
            Vector3 start = model.position + model.rotation * c.RootOffset;
            yield return Flight(start, model.rotation, dest, true, true, ChikuoTimings.LeapAir, -1f);
        }

        /// <summary>La garrocha (después de un hueco): clava el bastón y salta apoyado en él a una caña a 4.5-8 m de Kaito.
        /// Invulnerable; el agarre no carga (un hueco nunca encadena otro).</summary>
        IEnumerator VaultAct()
        {
            var dest = grove.PickDestination(null, TargetPos, phaseIdx, BambooMasterMoves.VaultDest) ?? FarthestStalk();
            if (dest == null) yield break;
            var c = ChikuoTimings.Vault;
            Vector3 dir = (dest.Base - transform.position).Flat();
            if (dir.sqrMagnitude > 1e-4f) transform.rotation = Quaternion.LookRotation(dir.normalized);
            vuln = Vuln.None;
            Play(c, 0.1f);
            float plant = c.Event("Plant"), leave = c.Event("LeaveStalk");
            bool planted = false;
            // el paso hasta clavar el bastón lo avanza el código (travel_m: el pie no patina)
            while (clipT < leave * c.Seconds - 1e-4f)
            {
                ClipTravel(c);
                if (!planted && clipT >= plant * c.Seconds)
                {
                    planted = true;
                    Game.FX?.Dust(transform.position + transform.forward, 0.7f);
                    Game.Audio?.Play("step_wood", transform.position, 0.7f, 0.1f);
                }
                yield return null;
            }
            Vector3 start = model.position + model.rotation * c.RootOffset;
            yield return Flight(start, model.rotation, dest, false, false, c, (1f - leave) * c.Seconds / Mathf.Max(0.01f, clipRate));
        }

        BambooStalk FarthestStalk()
        {
            BambooStalk best = null;
            float bd = -1f;
            foreach (var s in grove.All)
            {
                if (!BambooGrove.Perchable(s, phaseIdx)) continue;
                float d = (s.Base - TargetPos).Flat().magnitude;
                if (d > bd) { bd = d; best = s; }
            }
            return best;
        }

        // ================================================================== el latigazo (sección 2)
        /// <summary>
        /// Kaito cortó la base cargada: la caña suelta el resorte y lo despide por la línea Kaito → base. Con otra caña en pie
        /// a 6 m o menos dentro de ±20°: el estampado; si no, el revolcón. En la fase 3 cada latigazo raja la caña y el
        /// segundo la quiebra. Al corte no le entra daño (la caída daña al tocar el piso).
        /// </summary>
        HitResult Whip(Vector3 dir, in DamageInfo info)
        {
            var s = loadedStalk != null ? loadedStalk : perch;
            if (s == null) return HitResult.Ignored;
            loadCut = true;
            loadsUncut = 0;
            if (Teach("first_whip"))
            {
                // el primer latigazo tiene su cámara lenta (solo esa vez)
                Game.Time?.SlowMotion(0.3f, 0.25f, 0.02f, 0.15f);
                Bark("latigazo", true);
            }
            Sfx("bamboo_whip", "fin_whoosh", s.Base + Vector3.up, 1f);
            Game.Audio?.Play("ability_wind", s.Base, 0.6f, 0.1f);
            BambooGrove.Splinters(s.Base + Vector3.up * ArenaStalk.CutHeight, -dir);
            Game.Camera?.Shake(0.35f);
            // el corazón de la pelea pesa siempre (no solo la primera vez): un hit-stop de golpe fuerte y el gamepad
            Game.Time?.HitStop(0.08f);
            Game.Input?.Rumble(0.45f, 0.35f, 0.12f);
            s.Whip();
            look.Jangle(dir * 6f + Vector3.up * 2f);
            if (phaseIdx >= 2 && !s.IsMother)
            {
                bool broke = s.Crack();
                Log("caña " + s.Id + (broke ? " quebrada" : " rajada"));
                if (!broke && Teach("crack")) { Bark("rajada", true); ShowTip(StoryText.Hint("bamboo_crack")); }
            }
            Vector3 start = hanging ? model.position - (perch != null && perch.S.PerchNode != null ? perch.S.PerchNode.up : Vector3.up) * 1.1f : model.position;
            var stamp = grove.StampTarget(s, dir, phaseIdx);
            float kd = info.source is Component src ? (src.transform.position - s.Base).Flat().magnitude : 0f;
            Log("latigazo " + s.Id + " -> " + (stamp != null ? "estampado (" + stamp.Id + ")" : "revolcón") + ", Kaito a " + kd.ToString("0.00", Inv) + " m, '" + info.attackName + "'");
            if (stamp != null) Run(StampRoutine(stamp, dir, start));
            else Run(FlingRoutine(s, dir, start, BambooMasterMoves.Revolcon(phaseIdx), BambooMasterMoves.RevolconM));
            return HitResult.Hit;
        }

        /// <summary>
        /// "¡Cosquillas!": cortar la caña sin campanas. Suena hueca, la caña se sacude, él manotea y barre (rojo; cada 2.5 s
        /// como mucho) y con el envión se va a otra caña. Al corte no le entra daño ni da Espíritu.
        /// </summary>
        HitResult Tickle(Vector3 dir, in DamageInfo info)
        {
            if (perch == null) return HitResult.Ignored;
            Sfx("bamboo_thok", "step_wood", perch.Base + Vector3.up, 0.9f);
            perch.Shake(dir, 90f);
            BambooGrove.Splinters(perch.Base + Vector3.up * ArenaStalk.CutHeight, -dir);
            tickles++;
            if (tickles == 1) Bark("cosquillas", true);
            if (tickles == 2) ShowTip(StoryText.Hint("bamboo_tickle"));
            Log("cosquillas en " + perch.Id + (CanTickleSweep ? " (barre)" : ""));
            // lo agarra posado (respirando o con los dardos sin cargar); un golpe suyo en curso sigue
            if (CanTickleSweep) Run(TickleSweep());
            return HitResult.Ignored;
        }

        bool CanTickleSweep => body == Body.Perch && !leaving && State != EnemyState.Attack && Time.time - lastSweep >= 2.5f;

        IEnumerator TickleSweep()
        {
            yield return SweepAct(true);
            if (phaseChanging) yield break;
            // "¡Gracias por el empujón!": usa el envión para irse a otra caña
            Bark("empujon");
            yield return LeapAct(null);
            yield return Brain();
        }

        /// <summary>La caída del cielo: la caña adonde salta, cortada en los últimos 0.45 s del vuelo, se le escapa de las
        /// manos: cae de espaldas al pie de esa caña (3 s abierto, 5 cortes a x1.25).</summary>
        HitResult SkyCatch(in DamageInfo info)
        {
            if (leapDest == null || !leapCatchable) return HitResult.Ignored;
            var s = leapDest;
            float early = Mathf.Max(0f, leapGrabAt - Time.time);
            Log("caída del cielo en " + s.Id + " (" + early.ToString("0.00", Inv) + " s antes del agarre)");
            Sfx("bamboo_whip", "fin_whoosh", s.Base + Vector3.up, 1f);
            BambooGrove.Splinters(s.Base + Vector3.up * ArenaStalk.CutHeight, (s.Base - TargetPos).Flat().normalized);
            s.Shake((s.Base - TargetPos).Flat(), 220f);
            Run(SkyFallRoutine(s));
            return HitResult.Hit;
        }

        /// <summary>Le cortaron el agachado de la vuelta: tropieza (rodilla al piso, 1 s, 2 cortes).</summary>
        HitResult Trip(in DamageInfo info)
        {
            returnCutUsed = true;
            Run(SimpleHole(ChikuoTimings.Stumble, BambooMasterMoves.Tropiezo, null, false));
            return HitResult.Hit;
        }

        /// <summary>Le cortaron la caña mientras trepa: se resbala y cae sentado (1 s, 2 cortes, +6).</summary>
        HitResult Slip(in DamageInfo info)
        {
            var s = perch;
            returnCutUsed = true;
            loadCut = true;
            if (s != null) { s.Whip(); Sfx("bamboo_whip", "fin_whoosh", s.Base + Vector3.up, 0.8f); }
            Run(SlipRoutine(s));
            return HitResult.Hit;
        }

        // ------------------------------------------------------------------ resultados del latigazo
        /// <summary>El revolcón: vuela 'meters' más allá de la base dando vueltas, cae rodando y queda sentado mareado.</summary>
        IEnumerator FlingRoutine(BambooStalk s, Vector3 dir, Vector3 start, BambooMasterMoves.Hole h, float meters)
        {
            vuln = Vuln.None;
            Vector3 land = grove.FlingLanding(s != null ? s.Base : transform.position, dir, meters);
            Quaternion rot = Quaternion.LookRotation(-dir);
            Play(ChikuoTimings.FlungAir, 0.05f);
            float t = 0f;
            while (t < h.fly)
            {
                if (!anim.Frozen) t += Time.deltaTime;
                Carry(Arc(start, land, Mathf.Clamp01(t / h.fly), 0.9f), rot);
                yield return null;
            }
            Landed(land, -dir);
            Play(ChikuoTimings.FlungLand, 0.04f);
            Game.FX?.Dust(land, 1.3f);
            Game.Camera?.Shake(0.3f);
            Sfx("chime_jangle", "step_wood", Voice, 0.8f);
            look.Jangle(Vector3.up * 4f);
            FallDamage(h.fall);
            if (phaseChanging || !IsAlive) yield break;
            yield return HoleRoutine(h, "DazedSit", "DazedSitHit");
            yield return ReturnUp(true);
            yield return Brain();
        }

        /// <summary>
        /// El estampado: se estrella de espaldas contra la otra caña a ~3.5 m ("¡PUM!", hojas y los cascabeles), se desliza
        /// hasta el pie y queda sentado (2.2 s abierto desde que toca el piso, 4 cortes a x1.2, +24).
        /// </summary>
        IEnumerator StampRoutine(BambooStalk other, Vector3 dir, Vector3 start)
        {
            vuln = Vuln.None;
            var h = BambooMasterMoves.Estampado(phaseIdx);
            Quaternion rot = Quaternion.LookRotation(-dir);
            // la raíz al pie del cuerpo con el eje de la otra caña 0.30 m detrás (Splat del sidecar)
            Vector3 hit = other.Base + Vector3.up * BambooMasterMoves.SplatHeight - dir * 0.30f;
            Play(ChikuoTimings.FlungAir, 0.05f);
            const float fly = 0.3f;
            float t = 0f;
            while (t < fly)
            {
                if (!anim.Frozen) t += Time.deltaTime;
                Carry(Arc(start, hit, Mathf.Clamp01(t / fly), 0.4f), rot);
                yield return null;
            }
            var sp = ChikuoTimings.Splat;
            Play(sp, 0.03f);
            Carry(hit, rot);
            yield return Until(sp.Contact);
            Sfx("bamboo_slam", "rock_impact", hit, 1f);
            other.Shake(dir, 200f);
            BambooGrove.Leaves(hit + Vector3.up * 0.8f, 1.6f);
            Game.Camera?.Shake(0.45f);
            Game.Input?.Rumble(0.5f, 0.4f, 0.15f);
            Game.Time?.HitStop(0.1f);
            look.Jangle(-dir * 5f);
            if (Teach("stamp")) { Bark("estampado", true); }
            yield return Until(1f);
            // se desliza por la caña hasta sentarse al pie (el 'land' del sidecar: el cuadro en que la raíz llega al piso)
            var sd = ChikuoTimings.SlideDown;
            Play(sd, 0f);
            float floorAt = sd.LandN > 0f ? sd.LandN : 1f;
            Vector3 bottom = Floor(hit);
            while (clipT < floorAt * sd.Seconds)
            {
                float u = Mathf.Clamp01(ClipNorm / floorAt);
                Carry(Vector3.Lerp(hit, bottom, u * u), rot);
                yield return null;
            }
            Landed(bottom, -dir);
            Game.FX?.Dust(bottom, 1f);
            FallDamage(h.fall);
            if (phaseChanging || !IsAlive) yield break;
            if (Teach("stamp_tip")) ShowTip(StoryText.Hint("bamboo_stamp"));
            revanchaPending = phaseIdx >= 2;
            yield return HoleRoutine(h, "DazedSit", "DazedSitHit");
            yield return ReturnUp(true);
            yield return Brain();
        }

        /// <summary>La caída del cielo: MissGrab desde donde iba a agarrarse, de espaldas al pie de la caña (el piso en su
        /// 'land' del sidecar), y queda pataleando.</summary>
        IEnumerator SkyFallRoutine(BambooStalk s)
        {
            vuln = Vuln.None;
            Vector3 start = model.position;
            Quaternion rot = model.rotation;
            Vector3 away = (start - s.Base).Flat();
            Vector3 bottom = Floor(s.Base + (away.sqrMagnitude > 1e-4f ? away.normalized : Vector3.back) * 0.8f);
            var c = ChikuoTimings.MissGrab;
            Play(c, 0.03f);
            float floorAt = c.LandN > 0f ? c.LandN : 1f;
            while (clipT < floorAt * c.Seconds - 1e-4f)
            {
                float u = Mathf.Clamp01(ClipNorm / floorAt);
                Carry(Vector3.Lerp(start, bottom, u * u), rot);
                yield return null;
            }
            Landed(bottom, rot * Vector3.forward);
            Game.FX?.Dust(bottom, 1.4f);
            Game.Camera?.Shake(0.4f);
            Sfx("chime_jangle", "step_wood", Voice, 0.9f);
            Bark("caida", true);
            FallDamage(BambooMasterMoves.Caida.fall);
            if (phaseChanging || !IsAlive) yield break;
            revanchaPending = phaseIdx >= 2;
            yield return HoleRoutine(BambooMasterMoves.Caida, "DazedLie", "DazedLieHit");
            yield return ReturnUp(true);
            yield return Brain();
        }

        /// <summary>El resbalón: cae sentado al pie de la caña que trepaba (el culmo 0.35 m adelante).</summary>
        IEnumerator SlipRoutine(BambooStalk s)
        {
            vuln = Vuln.None;
            Vector3 start = model.position;
            Quaternion rot = model.rotation;
            Vector3 fwd = (rot * Vector3.forward).Flat();
            Vector3 bottom = Floor(s != null ? s.Base - (fwd.sqrMagnitude > 1e-4f ? fwd.normalized : Vector3.forward) * 0.35f : transform.position);
            var c = ChikuoTimings.Slip;
            Play(c, 0.03f);
            float floorAt = c.LandN > 0f ? c.LandN : 1f;
            while (clipT < floorAt * c.Seconds - 1e-4f)
            {
                float u = Mathf.Clamp01(ClipNorm / floorAt);
                Carry(Vector3.Lerp(start, bottom, u * u), rot);
                yield return null;
            }
            Landed(bottom, fwd);
            Game.FX?.Dust(bottom, 0.9f);
            FallDamage(BambooMasterMoves.Resbalon.fall);
            if (phaseChanging || !IsAlive) yield break;
            yield return HoleRoutine(BambooMasterMoves.Resbalon, "DazedSit", "DazedSitHit");
            yield return ReturnUp(true);
            yield return Brain();
        }

        /// <summary>Un hueco en el lugar con su clip (el tropiezo, los pies enterrados, el bastón clavado, el desafinado) y
        /// después la vuelta (con la garrocha si 'getUp': el clip termina en el piso).</summary>
        IEnumerator SimpleHole(ChikuoClip c, BambooMasterMoves.Hole h, ChikuoClip loop, bool getUp)
        {
            if (body != Body.Ground) SetBody(Body.Ground);
            Play(c, 0.05f);
            yield return HoleRoutine(h, loop != null ? loop.State : null, null);
            if (phaseChanging) yield break;
            if (getUp) yield return ReturnUp(true);
            else if (phaseIdx != 1 && HasFreeStalk()) yield return VaultAct();
            yield return Brain();
        }

        // ================================================================== los huecos (sección 6)
        /// <summary>
        /// Abierto 'h.open' s (se frena con el hit-stop) a lo sumo 'h.cap' cortes a x'h.mul'. Mientras dura toca 'loop' (o
        /// sigue el clip que ya suena hasta que termina y después pasa a 'loop'). El último corte del
        /// tope lo despide un poco y se levanta enseguida (0.25 s).
        /// </summary>
        IEnumerator HoleRoutine(BambooMasterMoves.Hole h, string loop, string hit)
        {
            hole = h;
            holeLeft = h.cap;
            holeLoop = loop;
            holeHit = hit;
            holeUntil = h.open;
            vuln = Vuln.Open;
            ChikuoClip loopClip = loop != null ? ChikuoTimings.Get(loop) : null;
            while (holeUntil > 0f)
            {
                if (!anim.Frozen) holeUntil -= Time.deltaTime;
                if (body == Body.Ground) ClipTravel(clip);
                // terminó el clip de entrada (o el sacudón de un corte): al loop
                if (loopClip != null && clip != loopClip && ClipDone) Play(loopClip, 0.08f);
                yield return null;
            }
            vuln = Vuln.None;
        }

        /// <summary>Un corte en un hueco: daño x(su multiplicador) hasta el tope; pasado el tope, nada.</summary>
        HitResult HoleHit(in DamageInfo info)
        {
            if (holeLeft <= 0) return HitResult.Ignored;
            holeLeft--;
            var r = ApplyDamage(info, hole.mul);
            // el corte que cruza el piso de la fase ya arrancó la escena (StartTransition): el sacudón del hueco le pisaba
            // PhaseBow/PhaseForest y las notas, la inclinación y el salto a la Madre pasaban en 0.3 s
            if (r != HitResult.Hit || phaseChanging || !IsAlive) return r;
            Sfx("chime_jangle", null, Voice, 0.6f);
            var hc = holeHit != null ? ChikuoTimings.Get(holeHit) : null;
            if (hc != null && body == Body.Ground) Play(hc, 0.03f);
            if (holeLeft == 0) holeUntil = Mathf.Min(holeUntil, BambooMasterMoves.CapRise);
            return r;
        }

        /// <summary>La Contra: Kaito desvió el último golpe de una tanda (o el bastón que cae). Retrocede con su clip.</summary>
        IEnumerator ContraRoutine(bool perfect)
        {
            if (body != Body.Ground) Landed(transform.position, transform.forward);
            var c = perfect ? ChikuoTimings.ParriedPerfect : ChikuoTimings.Parried;
            Play(c, 0.03f);
            var h = BambooMasterMoves.Contra(perfect);
            hole = h;
            holeLeft = h.cap;
            holeHit = null;
            vuln = Vuln.Open;
            float left = h.open;
            while (left > 0f)
            {
                if (!anim.Frozen) left -= Time.deltaTime;
                ClipTravel(c);
                yield return null;
            }
            vuln = Vuln.None;
            // un hueco nunca encadena otro: arriba con la garrocha
            if (phaseIdx != 1 && HasFreeStalk()) yield return VaultAct();
            yield return Brain();
        }

        /// <summary>El cuerpo avanza lo que avanza el clip (travel_m del sidecar, hacia su frente; negativo para atrás).</summary>
        void ClipTravel(ChikuoClip c)
        {
            if (c == null || c.Travel == null || anim.Frozen) return;
            float x = c.TravelAt(ClipNorm);
            float d = x - travelDone;
            travelDone = x;
            if (Mathf.Abs(d) > 1e-5f) MoveBy(transform.forward * d);
        }
    }
}
