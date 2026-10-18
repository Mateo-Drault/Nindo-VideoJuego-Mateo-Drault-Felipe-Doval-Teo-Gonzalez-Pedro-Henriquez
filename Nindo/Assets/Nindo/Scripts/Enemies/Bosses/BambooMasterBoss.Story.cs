using System.Collections;
using UnityEngine;
using UnityEngine.AI;

namespace Nindo
{
    /// <summary>
    /// Las escenas de Chikuō (diseño 4.2, 4.4, 4.6 y 19): la presentación (colgado cabeza abajo de la punta de O1 tocando
    /// la flauta) y su versión corta en los reintentos, los dos cambios de fase ("Bailemos en el piso": las seis cañas se
    /// inclinan; "Que cante todo el bosque": se enderezan y nace la Caña Madre) y la derrota (se cae de espaldas riéndose,
    /// se sienta con las piernas cruzadas y deja el sello). Los tiempos son los eventos del sidecar (ChikuoTimings).
    /// </summary>
    public partial class BambooMasterBoss
    {
        /// <summary>Altura del posado de la caña sobre la que se autoraron los clips de arriba (sidecar 'stalk').</summary>
        const float ClimbAuthorPerch = 4.4f;
        /// <summary>El plano de la muerte de Boss (3.2 s + 1.2 de vuelta): el plano sentado espera a que termine.</summary>
        const float BossDeathShot = 4.4f;

        // ================================================================== presentación
        /// <summary>
        /// La primera vez: se oye una flauta; plano desde abajo hacia O1: cuelga cabeza abajo tocando, abre un ojo, sonríe,
        /// se ríe y le sopla un dardo que se clava a los pies de Kaito (un saludo, no pega), se suelta, da una vuelta y queda
        /// agachado en el posado; el título y la charla. En un reintento, la versión corta con una frase. Lo arranca
        /// StoryDirector.
        /// </summary>
        public IEnumerator Presentation(PlayerController p, bool first)
        {
            EnsureGrove();
            Game.Audio?.StopMusic(first ? 1.5f : 0.6f);
            if (!first || retryPhase >= 1 || grove == null)
            {
                yield return Reintro(p);
                yield break;
            }
            WaitPose();
            var s = perch;
            Vector3 b = s != null ? s.Base : transform.position;
            Vector3 kp = p != null ? p.transform.position : b + Vector3.back * 10f;
            Vector3 toK = (kp - b).Flat().normalized;
            Vector3 right = Vector3.Cross(Vector3.up, toK);
            float top = s != null ? s.S.PerchHeight + 1.2f : 5.5f;
            // desde abajo y detrás del viejo hacia arriba, con el cielo de la noche: sube con él cuando se suelta
            int shot = Game.Camera.PlayShot(t =>
            {
                float u = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / 6.2f));
                Vector3 pos = b + toK * Mathf.Lerp(7.2f, 6.2f, u) + right * Mathf.Lerp(2.6f, 1.6f, u) + Vector3.up * Mathf.Lerp(1.3f, 2.2f, u);
                Vector3 look = b + Vector3.up * Mathf.Lerp(top + 0.4f, top - 0.6f, u);
                return new Pose(pos, Quaternion.LookRotation(look - pos));
            }, () => 38f, 1.0f, 0f, 0.9f);
            Sfx("flute_phrase_intro", null, Voice, 0.9f);
            yield return new WaitForSeconds(0.6f);
            var intro = ChikuoTimings.Intro;
            Play(intro, 0.05f);
            yield return Until(intro.Event("DartSpawn"));
            // el saludo: un dardo clavado a los pies de Kaito (en la escena es invulnerable)
            if (p != null && grove != null)
            {
                Vector3 feet = p.transform.position - toK * 0.7f;
                Vector3 from = MuzzlePos;
                BambooDart.Spawn(this, from, feet - from, BambooMasterMoves.DartSpeed[0], 0f, false, grove.FloorY, true);
            }
            yield return Until(intro.Event("Perch"));
            Game.UI.ShowBossTitle(title, subtitle);
            yield return Until(1f);
            Play(ChikuoTimings.PerchIdle, 0.15f);
            Game.Camera.CancelShot(shot);
            // la charla con los dos en cuadro: detrás de Kaito, él arriba en su caña
            Vector3 mid = Vector3.Lerp(kp, b, 0.5f);
            Vector3 back = (kp - b).Flat().normalized;
            int talk = Game.Camera.PlayStaticShot(kp + back * 5.5f + Vector3.Cross(Vector3.up, back) * 2.4f + Vector3.up * 3.4f, mid + Vector3.up * 2.6f, 38f, 0f, 0.8f, 0.8f);
            yield return Game.UI.Dialogue(StoryText.Dialogue("ozeki_intro"));
            Game.Camera.CancelShot(talk);
        }

        /// <summary>Reintento: en su lugar de la fase (colgado de O1 se suelta y se posa; en la fase 2 parado; en la 3 en la
        /// Madre) con una frase distinta por intento (~2 s).</summary>
        IEnumerator Reintro(PlayerController p)
        {
            WaitPose();
            float dur = 2f;
            Transform focus = model;
            if (retryPhase == 0 && body == Body.Perch)
            {
                var intro = ChikuoTimings.Intro;
                float from = intro.Event("LeaveStalk") - 0.06f;
                Play(intro, 0.1f, Mathf.Max(0f, from));
                dur = Mathf.Max(1.2f, (1f - from) * intro.Seconds);
            }
            else if (retryPhase == 1) Play(ChikuoTimings.GroundLaugh, 0.15f);
            else Play(ChikuoTimings.PerchLaugh, 0.15f);
            Vector3 b = transform.position;
            Vector3 kp = p != null ? p.transform.position : b + Vector3.back * 10f;
            Vector3 back = (kp - b).Flat().normalized;
            float h = HeightAboveFloor + 1.4f;
            int shot = Game.Camera.PlayStaticShot(kp + back * 4.5f + Vector3.up * 2.6f, b + Vector3.up * Mathf.Max(1.6f, h * 0.7f), 38f, 0f, 0.6f, 0.7f);
            Game.UI?.ShowBark(StoryText.Chikuo, StoryText.ChikuoRetry(attempts, retryPhase), BarkColor, 3.2f);
            yield return new WaitForSeconds(dur);
            if (body == Body.Perch) Play(ChikuoTimings.PerchIdle, 0.15f);
            else Play(ChikuoTimings.Idle, 0.2f);
            Game.Camera.CancelShot(shot);
        }

        // ================================================================== cambios de fase
        void StartTransition(int next)
        {
            if (phaseChanging || !IsAlive) return;
            phaseChanging = true;
            Run(TransitionRoutine(next));
        }

        IEnumerator TransitionRoutine(int next)
        {
            vuln = Vuln.Scene;
            SetState(EnemyState.Scripted);
            BambooDart.ClearAll();
            marks?.Clear();
            if (body != Body.Ground)
            {
                // (pruebas: "chikuo fase N" con él arriba) baja al pie de su caña
                Vector3 at = (perch != null ? perch.Base : transform.position) + FaceDirFrom(transform.position) * 1.2f;
                Landed(at, FaceDirFrom(at));
            }
            Face(TargetPos, 99f, 1f);
            if (next == 1) yield return BowScene();
            else yield return ForestScene();
            phaseChanging = false;
            vuln = Vuln.None;
            yield return Brain();
        }

        /// <summary>1 → 2, "Bailemos en el piso" (4 s): cae sentado riéndose, se saca una hoja de la barba y toca tres notas;
        /// en la tercera las seis cañas se inclinan 70° hacia afuera y quedan temblando con la música.</summary>
        IEnumerator BowScene()
        {
            var c = ChikuoTimings.PhaseBow;
            Play(c, 0.2f);
            Bark("fase2", true);
            Log("fase 2 (el piso)");
            for (int i = 0; i < c.EventCount("Note"); i++)
            {
                yield return Until(c.EventAt("Note", i));
                PlayNote(i != 1, i);
                if (i < c.EventCount("Note") - 1) continue;
                foreach (var s in grove.All)
                {
                    if (s.IsMother) continue;
                    s.Lean(true, 1.2f);
                    // tiemblan con la música (136 BPM: una vez por tiempo)
                    s.Wobble(2f, 136f / 60f, 9999f);
                }
                Sfx("stalk_bow", "fin_whoosh", grove.Center + Vector3.up * 3f, 1f);
                Game.Camera?.Shake(0.25f);
            }
            phaseIdx = 1;
            config.patterns = BambooMasterMoves.GroundPatterns(1);
            nextPoleAt = nextQaAt = -1f;
            Game.Audio?.SetBossMusicPhase(2);
            subtitle = PhaseSubtitle(1);
            Game.UI?.BossRetitled(this);
            RewardKaito();
            yield return Until(1f);
        }

        /// <summary>
        /// 2 → 3, "Que cante todo el bosque" (5 s): toca la frase entera (todas las campanas en cascada), las seis cañas se
        /// enderezan de golpe (un latigazo de 0.4 s), nace la Caña Madre en el centro (1.5 s; si Kaito está encima lo corre
        /// 1 m) y salta con la garrocha a ella.
        /// </summary>
        IEnumerator ForestScene()
        {
            var c = ChikuoTimings.PhaseForest;
            Play(c, 0.15f);
            Sfx("flute_phrase_forest", null, Voice, 0.9f);
            yield return Until(c.EventAt("Note", 0));
            foreach (var s in grove.All) if (!s.IsMother) { s.Wobble(0f, 1f, 0f); s.Lean(false, 0.4f); }
            Sfx("stalk_whoosh", "ability_wind", grove.Center + Vector3.up * 3f, 1f);
            BambooGrove.Leaves(grove.Center + Vector3.up * 4f, 1.8f);
            yield return Until(c.EventAt("Note", 1));
            Game.Audio?.SetBossMusicPhase(3);
            if (grove.Mother != null) StartCoroutine(RiseMother(grove.Mother, 1.5f));
            float leave = c.Event("LeaveStalk");
            yield return Until(leave);
            phaseIdx = 2;
            config.patterns = BambooMasterMoves.GroundPatterns(2);
            nextPoleAt = nextQaAt = nextSignatureAt = -1f;
            subtitle = PhaseSubtitle(2);
            Game.UI?.BossRetitled(this);
            RewardKaito();
            var dest = grove.Mother != null ? grove.Mother : FarthestStalk();
            Bark("fase3", true);
            Log("fase 3 (el bosque entero)");
            if (dest == null) yield break;
            Vector3 start = model.position + model.rotation * c.RootOffset;
            yield return Flight(start, model.rotation, dest, false, false, c, (1f - leave) * c.Seconds);
        }

        IEnumerator RiseMother(BambooStalk m, float seconds)
        {
            Sfx("stalk_grow", "avalanche_rumble", m.Base, 1f);
            Game.FX?.Dust(m.Base, 2.2f);
            Game.Camera?.Shake(0.35f);
            var p = Game.Player;
            if (p != null && (p.transform.position - m.Base).Flat().magnitude < 1.2f)
                p.Push((p.transform.position - m.Base).Flat().sqrMagnitude > 1e-4f ? p.transform.position - m.Base : Vector3.back, 1f);
            for (float t = 0f; t < seconds; t += Time.deltaTime)
            {
                float u = t / seconds;
                m.S.SetRise(1f - (1f - u) * (1f - u));
                yield return null;
            }
            m.S.SetRise(1f);
            BambooGrove.Leaves(m.Base + Vector3.up * 6f, 1.6f);
        }

        void RewardKaito()
        {
            var p = Game.Player;
            if (p == null || !p.IsAlive) return;
            p.Heal(BambooMasterMoves.TransitionHeal);
            p.AddSpirit(BambooMasterMoves.TransitionSpirit);
            BandanaGlow.Ensure(p)?.Pulse(BandanaGlow.Gold, 1f);
        }

        // ================================================================== derrota
        protected override bool DeathBurst => false;

        /// <summary>
        /// El último golpe le cae siempre en el piso (arriba no se le pega). No muere ni se esfuma: se cae de espaldas
        /// riéndose, se sienta con las piernas cruzadas, se seca una lágrima de risa y hace la reverencia con la flauta sobre
        /// las rodillas; las campanas de la Madre suenan solas, una por una, y se callan; el sello aparece delante.
        /// </summary>
        protected override void Die(in DamageInfo info, bool finisher = false)
        {
            if (State == EnemyState.Dead) return;
            if (act != null) StopCoroutine(act);
            act = null;
            ClearActionState();
            vuln = Vuln.None;
            BambooDart.ClearAll();
            marks?.Clear();
            look?.Extinguish();
            if (body != Body.Ground) Landed(transform.position, transform.forward);
            ClearCameraBias();
            if (tipHideAt > 0f) { Game.UI?.HideTutorial(); tipHideAt = -1f; }
            Face(TargetPos, 99f, 1f);
            base.Die(info, finisher);
            anim.Play(ChikuoTimings.Defeat.State, 0.3f);
            // queda sentado en el claro y Kaito no lo atraviesa para tomar el sello (Enemy apagó los colliders)
            if (capsule != null)
            {
                capsule.radius = 0.6f;
                capsule.height = 1.4f;
                capsule.center = new Vector3(0f, 0.7f, 0f);
                capsule.enabled = true;
            }
        }

        protected override IEnumerator DeathRoutine(Vector3 dir)
        {
            var d = ChikuoTimings.Defeat;
            float t0 = Time.time;
            yield return new WaitForSeconds(d.Seconds * 0.98f);
            anim.Play(ChikuoTimings.DefeatIdle.State, 0.3f);
            // las campanas de la Madre (o de las cañas que quedan) suenan solas, una por una, y se callan
            if (grove != null)
            {
                int n = 0;
                foreach (var s in grove.All)
                {
                    if (!s.Standing && !(s.IsMother && s.S.Rise > 0.5f)) continue;
                    s.S.KickChimes(Vector3.right * (n % 2 == 0 ? 2f : -2f));
                    Sfx("tell_chime_hi", "pearl_ping", s.S.PerchNode != null ? s.S.PerchNode.position : s.Base, 0.35f);
                    n++;
                    yield return new WaitForSeconds(0.35f);
                }
            }
            yield return new WaitForSeconds(Mathf.Max(0.3f, BossDeathShot - (Time.time - t0)));
            int shot = SeatedShot();
            Game.Story?.PlayDialogueById("bamboo_defeat");
            float wait = 0f;
            while ((Game.InCutscene || (Game.UI != null && Game.UI.DialogueOpen)) && wait < 60f) { wait += Time.unscaledDeltaTime; yield return null; }
            if (shot >= 0 && Game.Camera != null) Game.Camera.CancelShot(shot);
            OnDeathFinished();
        }

        int SeatedShot()
        {
            if (Game.Camera == null) return -1;
            Vector3 c = transform.position;
            Vector3 f = transform.forward.Flat().normalized, side = Vector3.Cross(Vector3.up, f);
            // del lado de la cámara de juego: no cruza el eje
            if (Vector3.Dot(side, (Game.Camera.transform.position - c).Flat()) < 0f) side = -side;
            Vector3 pos = c + (side * 0.8f + f * 0.6f).normalized * 6.2f + Vector3.up * 2.0f;
            return Game.Camera.PlayStaticShot(pos, c + f * 1.2f + Vector3.up * 0.9f, 36f, 0f, 1.0f, 1.0f);
        }

        /// <summary>El sello aparece delante de él, entre los dos (el viejo se queda sentado en el claro).</summary>
        protected override void OnDeathFinished()
        {
            if (!hasSeal) return;
            Vector3 p = transform.position + transform.forward * 1.7f;
            if (NavMesh.SamplePosition(p, out var hit, 2f, NavMesh.AllAreas)) p = hit.position;
            var key = KeyPickup.Spawn(seal, p + Vector3.up * 0.2f);
            if (key != null && transform.parent != null) key.transform.SetParent(transform.parent, true);
            Game.FX?.Shockwave(p, 2f, BambooStalk.White);
        }

#if UNITY_EDITOR || DEVELOPMENT_BUILD
        // ================================================================== pruebas (AutoPilot "chikuo ...")
        /// <summary>
        /// "chikuo fase N" (salta a la fase 2 o 3 con su escena), "chikuo cana ID" (se posa ya), "chikuo salto ID", "chikuo
        /// mov NOMBRE" (dardo dos notas silbador colgado risa picada baston barrido catapulta tala pertiga pregunta soplo),
        /// "chikuo abrir TIPO" (revolcon estampado caida resbalon afinado pies), "chikuo canas [reset]". false = no pudo.
        /// </summary>
        public bool DebugCommand(string sub, string arg)
        {
            if (!Fighting || !IsAlive || grove == null) return false;
            switch (sub)
            {
                case "fase":
                {
                    int ph = int.Parse(arg, Inv) - 1;
                    if (ph <= phaseIdx || ph > 2 || phaseChanging) return false;
                    if (ph == 2 && phaseIdx == 0) { phaseIdx = 1; foreach (var s in grove.All) if (!s.IsMother) s.Lean(true, 0f); }
                    Health = Gates[ph] * config.maxHealth + 1f;
                    StartTransition(ph);
                    return true;
                }
                case "cana":
                {
                    var s = grove.Get(arg.ToUpperInvariant());
                    if (s == null || !BambooGrove.Perchable(s, phaseIdx) || phaseChanging) return false;
                    Run(DebugPerch(s));
                    return true;
                }
                case "salto":
                {
                    var s = grove.Get(arg.ToUpperInvariant());
                    if (s == null || !BambooGrove.Perchable(s, phaseIdx) || body != Body.Perch || s == perch) return false;
                    Run(Then(LeapAct(s)));
                    return true;
                }
                case "mov": return DebugMove(arg);
                case "abrir": return DebugOpen(arg);
                case "canas":
                    if (arg == "reset") { grove.Reset(phaseIdx); BambooDart.ClearAll(); return true; }
                    foreach (var s in grove.All)
                        Log(s.Id + ": " + (s.Fallen ? "quebrada" : s.Leaning ? "inclinada" : s.Cracks == 1 ? "rajada" : s.IsMother && s.S.Rise < 1f ? "enterrada" : "en pie") +
                            (s == perch ? " (posado)" : "") + (s.Loaded ? " (cargada)" : ""));
                    return true;
            }
            return false;
        }

        IEnumerator DebugPerch(BambooStalk s)
        {
            PerchOn(s);
            Play(ChikuoTimings.PerchIdle, 0.1f);
            justLanded = false;
            yield return Brain();
        }

        IEnumerator Then(IEnumerator a)
        {
            yield return a;
            yield return Brain();
        }

        bool DebugMove(string name)
        {
            if (phaseChanging) return false;
            bool up = body == Body.Perch && perch != null;
            IEnumerator r = null;
            switch (name)
            {
                case "dardo": if (up) r = DartAct(ChikuoTimings.PerchDart, 0f); break;
                case "dos": if (up) r = DartAct(ChikuoTimings.PerchDart2, 0f); break;
                case "notas": if (up) r = DartAct(phaseIdx >= 2 ? ChikuoTimings.PerchVolley4 : ChikuoTimings.PerchVolley, 0f); break;
                case "silbador": if (up) r = WhistleAct(); break;
                case "colgado": if (up) r = HangAct((TargetPos - perch.Base).Flat().magnitude <= BambooMasterMoves.ReactDist); break;
                case "risa": if (up) r = LaughAct(false); break;
                case "picada": if (up) r = DiveAct(); break;
                case "baston": if (up) r = StaffDropAct(); break;
                case "barrido": if (up) r = SweepAct(false); break;
                case "catapulta": if (up) r = CatapultAct(); break;
                case "tala": if (up && TalaTarget() != null) r = TalaAct(); break;
                case "pertiga": if (body == Body.Ground) r = PoleCraneAct(); break;
                case "pregunta": if (body == Body.Ground) r = QuestionAnswer(); break;
                case "soplo":
                {
                    // el patrón del piso a la fuerza (Enemy lo elegía por peso y distancia: con Kaito cerca nunca salía); solo
                    // en la pelea del piso, que es la que lo vuelve a tomar al terminar
                    var soplo = groundAI && State != EnemyState.Attack ? System.Array.Find(config.patterns, x => x.name == "Soplo") : null;
                    if (soplo == null) return false;
                    EnterGroundAI(0f);
                    pattern = soplo;
                    StartAttack(false);
                    return State == EnemyState.Attack;
                }
            }
            if (r == null) return false;
            if (body == Body.Ground) LeaveGroundAI();
            Run(Then(r));
            return true;
        }

        bool DebugOpen(string kind)
        {
            if (phaseChanging) return false;
            Vector3 dir = (transform.position - TargetPos).Flat();
            dir = dir.sqrMagnitude > 1e-4f ? dir.normalized : Vector3.forward;
            switch (kind)
            {
                case "revolcon":
                    if (body != Body.Perch || perch == null) return false;
                    Run(FlingRoutine(perch, dir, model.position, BambooMasterMoves.Revolcon(phaseIdx), BambooMasterMoves.RevolconM));
                    return true;
                case "estampado":
                {
                    if (body != Body.Perch || perch == null) return false;
                    BambooStalk other = null;
                    float best = float.PositiveInfinity;
                    foreach (var s in grove.All)
                    {
                        if (s == perch || !s.Standing || s.IsMother && phaseIdx < 2) continue;
                        float d = (s.Base - perch.Base).Flat().magnitude;
                        if (d < best) { best = d; other = s; }
                    }
                    if (other == null) return false;
                    Run(StampRoutine(other, (other.Base - perch.Base).Flat().normalized, model.position));
                    return true;
                }
                case "caida":
                    if (body != Body.Perch || perch == null) return false;
                    Run(SkyFallRoutine(perch));
                    return true;
                case "resbalon":
                    if (body != Body.Perch || perch == null) return false;
                    Run(SlipRoutine(perch));
                    return true;
                case "afinado":
                    if (body != Body.Ground) return false;
                    Run(SimpleHole(ChikuoTimings.Tuned, BambooMasterMoves.Afinado, ChikuoTimings.Tuned, true));
                    return true;
                case "pies":
                    if (body != Body.Ground) return false;
                    Run(SimpleHole(ChikuoTimings.FeetStuck, BambooMasterMoves.Pies, null, true));
                    return true;
            }
            return false;
        }
#endif
    }
}
