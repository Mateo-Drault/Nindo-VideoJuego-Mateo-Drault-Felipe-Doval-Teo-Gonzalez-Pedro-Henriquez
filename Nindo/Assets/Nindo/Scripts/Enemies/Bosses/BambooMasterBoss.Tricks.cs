using System.Collections;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Los rojos largos desde la caña (diseño 5.1): el Silbador (fase 1 desde el 85 % y fase 3), la Catapulta y la Tala
    /// (fase 3). Los tres cargan o usan la caña: el silbador y la catapulta se pueden latigar en plena carga, y la tala usa
    /// las rajaduras que dejaron los latigazos de Kaito ("tus latigazos se vuelven sus armas").
    /// </summary>
    public partial class BambooMasterBoss
    {
        BambooDart whistleDart;
        string[] heldSlots;

        /// <summary>Zona del paso held: un disco (barrido, picadas) o un carril (silbador, catapulta, tala).</summary>
        void SetDiscArea(Vector3 center, float radius)
        {
            heldAreaLane = false;
            heldAreaOrigin = Floor(center);
            heldAreaDir = Vector3.forward;
            heldAreaSize = radius;
            heldAreaWidth = 0f;
        }

        void SetLaneArea(Vector3 from, Vector3 dir, float length, float width)
        {
            heldAreaLane = true;
            heldAreaOrigin = Floor(from);
            Vector3 d = dir.Flat();
            heldAreaDir = d.sqrMagnitude > 1e-4f ? d.normalized : Vector3.forward;
            heldAreaSize = length;
            heldAreaWidth = width;
        }

        // ------------------------------------------------------------------ el Silbador
        /// <summary>
        /// Gran inspiración con los cachetes inflados (cargada: se la puede latigar), el carril rojo de 1.0 m sigue a Kaito
        /// hasta 0.25 s antes de soplar y queda fijo; sopla un dardo pesado a 22 m/s por el carril. En la fase 3 el clip va a
        /// x1.125. Rojo: salir del carril o el dash.
        /// </summary>
        IEnumerator WhistleAct()
        {
            vuln = Vuln.Tickle;
            var c = ChikuoTimings.PerchWhistle;
            float rate = phaseIdx >= 2 ? 1.125f : 1f;
            float blow = c.EventAt("DartSpawn", 0), load = c.Event("Load"), unload = c.Event("Unload");
            Vector3 muzzle0 = MuzzlePos;
            float flight = Mathf.Max(0f, Vector3.Distance(muzzle0, TargetPos + Vector3.up * 0.9f) - 0.6f) / BambooMasterMoves.WhistleSpeed;
            var def = BambooMasterMoves.Held("Silbador", c, AttackKind.Unblockable, blow * c.Seconds / rate + flight, BambooMasterMoves.Dmg(BambooMasterMoves.Move.Whistle, phaseIdx), BambooMasterMoves.Whistle);
            if (!StartMove(def)) yield break;
            Play(c, 0.1f, 0f, rate);
            heldStrikeAt = blow;
            heldTravel = flight;
            heldSlots = BambooMasterLook.RedSlots;
            Sfx("tell_chime_cascade", null, Voice, 0.6f);
            Vector3 lane = FaceDirFrom(perch.Base);
            bool loadedOn = false, fixedLane = false;
            while (clipT < blow * c.Seconds - 1e-4f)
            {
                if (!loadedOn && clipT >= load * c.Seconds) { loadedOn = true; Load(perch, RealUntil(unload)); perch.SetLoad(25f, -lane); }
                if (!fixedLane)
                {
                    fixedLane = RealUntil(blow) <= BambooMasterMoves.WhistleFix;
                    lane = FaceDirFrom(perch.Base);
                    perchFaceLock = fixedLane;
                    perchFaceDir = lane;
                }
                heldTravel = Mathf.Max(0f, (TargetPos - perch.Base).Flat().magnitude - 0.4f) / BambooMasterMoves.WhistleSpeed;
                float len = (TargetPos - perch.Base).Flat().magnitude + 4f;
                SetLaneArea(perch.Base, lane, Mathf.Min(len, 26f), BambooMasterMoves.WhistleLane);
                yield return null;
            }
            // sopla: el dardo pesado sale por el carril fijo (apunta al pecho de donde estaba Kaito al fijarlo, y sigue)
            Vector3 from = MuzzlePos;
            Vector3 aim = Floor(perch.Base) + lane * Mathf.Max(2f, (TargetPos - perch.Base).Flat().magnitude) + Vector3.up * 0.9f;
            whistleDart = BambooDart.Spawn(this, from, aim - from, BambooMasterMoves.WhistleSpeed, def.damage, true, grove.FloorY, true);
            Game.FX?.Dust(from, 0.4f);
            perchFaceLock = false;
            // el aviso dura hasta que el dardo pasa a Kaito (o le pega)
            while (whistleDart != null && whistleDart.isActiveAndEnabled && !float.IsInfinity(whistleDart.EtaTo(TargetPos)) && !ClipDone) yield return null;
            heldStruck = true;
            whistleDart = null;
            EndTell(TellOutcome.Struck);
            yield return Until(1f);
            EndMove(TellOutcome.Struck);
        }

        // ------------------------------------------------------------------ la Catapulta (fase 3)
        /// <summary>
        /// La pose del concepto "agachado sobre la caña que se dobla" llevada a golpe: tensa la caña hacia atrás como un arco
        /// (cargada 1 s: cortarla tensa = el tiro sale errado, el latigazo), el carril rojo de 1.8 m sigue a Kaito hasta 0.75 s
        /// y queda fijo; sale con la patada voladora por el carril y pega al final (1.50 s), aterriza 2 m más allá.
        /// </summary>
        IEnumerator CatapultAct()
        {
            lastCatapult = Time.time;
            vuln = Vuln.Tickle;
            var draw = ChikuoTimings.CatapultDraw;
            var kick = ChikuoTimings.CatapultKick;
            float strike = draw.Seconds + kick.Contact * kick.Seconds;
            var def = BambooMasterMoves.Held("Catapulta", draw, AttackKind.Unblockable, strike, BambooMasterMoves.Dmg(BambooMasterMoves.Move.Catapult, phaseIdx), BambooMasterMoves.Catapult);
            if (!StartMove(def)) yield break;
            Play(draw, 0.12f);
            heldSlots = BambooMasterLook.KickSlots;
            Load(perch, draw.Seconds);
            Vector3 lane = FaceDirFrom(perch.Base);
            float aimFix = draw.Event("AimFix");
            float t0 = Time.time;
            bool fixedLane = false;
            Vector3 end = Vector3.zero;
            var stalk = perch;
            while (!ClipDone)
            {
                // otra rutina se lo llevó de la caña en medio del arco (dos NullReference en la fase 3, probando con el bot)
                if (perch != stalk) yield break;
                // ETA hasta el golpe: lo que falta del arco más la patada
                heldStrikeAt = 1f;
                heldTravel = kick.Contact * kick.Seconds;
                perch.SetLoad(Mathf.Lerp(6f, 35f, ClipNorm), -lane);
                if (!fixedLane)
                {
                    fixedLane = clipT >= aimFix * draw.Seconds;
                    lane = FaceDirFrom(perch.Base);
                    // adentro de la arena (con Kaito contra la barrera caía afuera y Boss.Update lo traía de un tirón)
                    end = grove.FlingLanding(Floor(TargetPos), lane, 2f);
                    perchFaceDir = lane;
                    perchFaceLock = fixedLane;
                }
                SetLaneArea(perch.Base, lane, (end - perch.Base).Flat().magnitude + 0.5f, 1.8f);
                yield return null;
            }
            if (perch != stalk) yield break;
            // la caña lo dispara: sale por el carril
            perch.Whip();
            Sfx("bamboo_whip", "fin_whoosh", perch.Base + Vector3.up * 3f, 0.9f);
            Vector3 from = model.position;
            Quaternion rot = Quaternion.LookRotation(lane);
            vuln = Vuln.None;
            Play(kick, 0f);
            heldStrikeAt = kick.Contact;
            heldTravel = 0f;
            look.BeginLimbTrail(BambooMasterLook.KickSlots, true);
            while (clipT < kick.Contact * kick.Seconds - 1e-4f)
            {
                Carry(Arc(from, end, ClipNorm / kick.Contact, 0.3f), rot);
                yield return null;
            }
            heldStruck = true;
            EndTell(TellOutcome.Struck);
            var area = new TellArea { lane = true, origin = heldAreaOrigin, forward = heldAreaDir, size = heldAreaSize, width = heldAreaWidth };
            if (target != null && area.Contains(TargetPos, target.Radius)) HitPlayer(def, from);
            Landed(end, lane);
            Game.FX?.Dust(end, 1.2f);
            Game.Camera?.Shake(0.4f);
            Game.Audio?.Play("slam", end, 0.8f);
            look.StopLimbTrail();
            EndMove(TellOutcome.Struck);
            Play(ChikuoTimings.DiveLand, 0.04f);
            yield return HoleRoutine(BambooMasterMoves.Aterrizaje, null, null);
            yield return ReturnUp(false);
        }

        // ------------------------------------------------------------------ la Tala (fase 3)
        /// <summary>Una caña rajada en pie que, al caer hacia Kaito, lo alcanza (su largo); null si no hay.</summary>
        BambooStalk TalaTarget()
        {
            if (grove == null) return null;
            BambooStalk best = null;
            float bd = float.PositiveInfinity;
            foreach (var s in grove.All)
            {
                if (s.Cracks != 1 || !s.Standing || s == perch) continue;
                float d = (s.Base - TargetPos).Flat().magnitude;
                if (d > s.S.Length - 0.5f || d < 1.5f) continue;
                if (d < bd) { bd = d; best = s; }
            }
            return best;
        }

        /// <summary>
        /// Le sopla el silbador corto a la rajadura de una caña rajada (el código gira el cuerpo hacia ella), la caña cruje y
        /// cae hacia Kaito: carril rojo de 1.6 m del largo de la caña, fijo a 0.65 s, pega a 1.10 s. Queda tumbada 5 s.
        /// </summary>
        IEnumerator TalaAct()
        {
            var victim = TalaTarget();
            if (victim == null) { yield return DartAct(ChikuoTimings.PerchDart, 0f); yield break; }
            lastTala = Time.time;
            vuln = Vuln.Tickle;
            var c = ChikuoTimings.TalaShot;
            float fixAt = BambooMasterMoves.TalaFix, impact = BambooMasterMoves.TalaImpact;
            var def = BambooMasterMoves.Held("La Tala", c, AttackKind.Unblockable, impact, BambooMasterMoves.Dmg(BambooMasterMoves.Move.Tala, phaseIdx), BambooMasterMoves.Tala);
            if (!StartMove(def)) yield break;
            Play(c, 0.1f);
            heldSlots = BambooMasterLook.RedSlots;
            perchFaceLock = true;
            perchFaceDir = (victim.Base - perch.Base).Flat().normalized;
            float shot = c.EventAt("DartSpawn", 0);
            float t = 0f;
            Vector3 lane = (TargetPos - victim.Base).Flat().normalized;
            bool fired = false, fell = false;
            while (t < impact)
            {
                if (!anim.Frozen) t += Time.deltaTime;
                heldStrikeAt = 1f;
                heldTravel = Mathf.Max(0f, impact - t - RealUntil(1f));
                if (!fired && clipT >= shot * c.Seconds)
                {
                    fired = true;
                    Vector3 crack = victim.Base + Vector3.up * 1.2f;
                    SlashLineFX.Spawn(MuzzlePos, crack, TellStyle.TrailDanger, 0.18f, 0.3f);
                    Sfx("bamboo_crack", "boulder_break", crack, 0.9f);
                    victim.Shake(lane, 60f);
                }
                if (t < fixAt) lane = (TargetPos - victim.Base).Flat().sqrMagnitude > 1e-4f ? (TargetPos - victim.Base).Flat().normalized : lane;
                else if (!fell)
                {
                    fell = true;
                    victim.Fell(lane, impact - t);
                    Log("caña " + victim.Id + " talada");
                }
                SetLaneArea(victim.Base, lane, victim.S.Length, 1.6f);
                yield return null;
            }
            heldStruck = true;
            EndTell(TellOutcome.Struck);
            var area = new TellArea { lane = true, origin = heldAreaOrigin, forward = heldAreaDir, size = heldAreaSize, width = heldAreaWidth };
            if (target != null && area.Contains(TargetPos, target.Radius)) HitPlayer(def, victim.Base);
            perchFaceLock = false;
            yield return Until(1f);
            EndMove(TellOutcome.Struck);
        }
    }
}
