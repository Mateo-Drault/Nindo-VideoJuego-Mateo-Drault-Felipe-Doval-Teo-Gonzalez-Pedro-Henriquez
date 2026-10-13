using System.Collections;
using UnityEngine;
using UnityEngine.AI;

namespace Nindo
{
    /// <summary>
    /// Las escenas de Chikuō: la presentación (y su versión corta en los reintentos), los dos cambios de fase (se saca el
    /// saco; llama al bastón) y la derrota (se rinde, se sienta a meditar, saluda y deja el sello). Los tiempos son los
    /// eventos del sidecar (BambooMasterTimings), así lo que pasa en el juego cae en el cuadro que se ve.
    /// </summary>
    public partial class BambooMasterBoss
    {
        /// <summary>Al cambiar de fase Kaito recupera un poco (no hay esbirros que curen): el maestro le deja respirar. Con
        /// 15 el bot "bueno" llegaba a la fase 3 con ~30 de vida y la mitad de sus muertes eran ahí.</summary>
        const float TransitionHeal = 30f, TransitionSpirit = 30f;
        /// <summary>Re-presentación: el Intro desde un poco antes del saludo hasta la guardia (~2 s).</summary>
        const float ReintroFromFrame = 44f;

        // reintentos: cuántas veces cayó Kaito y desde qué fase se vuelve a empezar (la más alta a la que llegó)
        int attempts, retryPhase;

        // ================================================================== presentación
        /// <summary>
        /// La primera vez: espera con las manos en la espalda, levanta la cabeza (el título), saluda puño en palma, hace
        /// la reverencia, toma la guardia de una mano y habla. En un reintento: el saludo y la guardia (~2 s) con una frase
        /// distinta cada vez; si ya se había sacado el saco, solo llama a Kaito con la mano. Lo arranca StoryDirector.
        /// </summary>
        public IEnumerator Presentation(PlayerController p, bool first)
        {
            var intro = BambooMasterTimings.Intro;
            Vector3 b = transform.position;
            Vector3 f = transform.forward.Flat().normalized;   // hacia Kaito (BossIntroRoutine ya lo giró)
            Vector3 right = Vector3.Cross(Vector3.up, f);
            Game.Audio?.StopMusic(first ? 1.5f : 0.6f);
            if (!first)
            {
                yield return Reintro(b, f, right);
                yield break;
            }
            WaitPose();
            // de frente, bajo y cerca: sube con él cuando levanta la cabeza
            int shot = Game.Camera.PlayShot(t =>
            {
                float u = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / 4.6f));
                Vector3 pos = b + f * Mathf.Lerp(7.5f, 6f, u) + right * Mathf.Lerp(2.4f, 1.2f, u) + Vector3.up * Mathf.Lerp(1.0f, 2.1f, u);
                Vector3 look = b + Vector3.up * Mathf.Lerp(1.5f, 2.0f, u);
                return new Pose(pos, Quaternion.LookRotation(look - pos));
            }, () => 34f, 1.0f, 0f, 0.9f);
            yield return new WaitForSeconds(0.9f);
            anim.Play(intro.State, 0.05f, 0f, 1f);
            yield return new WaitForSeconds(intro.Event("HeadRise") * intro.Seconds);
            Game.UI.ShowAreaTitle(title, subtitle);
            yield return new WaitForSeconds((intro.Event("Salute") - intro.Event("HeadRise")) * intro.Seconds);
            Game.Audio?.Play("clang", transform.position, 0.35f, 0.02f);   // puño contra palma, seco
            yield return new WaitForSeconds((intro.Event("Guard") - intro.Event("Salute")) * intro.Seconds + 0.4f);
            // la charla con los dos en cuadro: detrás de Kaito, él arriba en el claro
            Vector3 kp = p != null ? p.transform.position : b + f * 10f;
            Vector3 mid = Vector3.Lerp(kp, b, 0.55f);
            Vector3 back = (kp - b).Flat().normalized;
            Game.Camera.CancelShot(shot);
            int talk = Game.Camera.PlayStaticShot(kp + back * 4.5f + Vector3.Cross(Vector3.up, back) * 2.2f + Vector3.up * 3.2f, mid + Vector3.up * 1.6f, 36f, 0f, 0.8f, 0.8f);
            yield return Game.UI.Dialogue(StoryText.Dialogue("ozeki_intro"));
            Game.Camera.CancelShot(talk);
            anim.Play("Locomotion", 0.3f);
        }

        IEnumerator Reintro(Vector3 b, Vector3 f, Vector3 right)
        {
            WaitPose();
            bool coatOff = retryPhase >= 1;
            var intro = BambooMasterTimings.Intro;
            var clipR = coatOff ? (BambooMasterTimings.Get("Taunt" + BambooMasterMoves.Suffix(retryPhase)) ?? BambooMasterTimings.Taunt) : intro;
            float from = coatOff ? 0f : intro.FrameNorm(ReintroFromFrame);
            float to = coatOff ? 1f : intro.Event("Guard");
            float dur = Mathf.Max(0.8f, (to - from) * clipR.Seconds);
            anim.Play(clipR.State, 0.15f, from, 1f);
            int shot = Game.Camera.PlayBossIntroShot(transform, 2.6f, dur, 0f, 0.7f);
            Bark(StoryText.ChikuoRetry(attempts, retryPhase));
            yield return new WaitForSeconds(dur);
            Game.Camera.CancelShot(shot);
        }

        // ================================================================== cambios de fase
        void StartTransition(int next)
        {
            if (transition != null) return;
            transition = StartCoroutine(TransitionRoutine(next));
        }

        IEnumerator TransitionRoutine(int next)
        {
            // el corte que lo baja al umbral puede ser el último de la rodilla: Enemy ya lo dio por levantado (Guard) en el
            // mismo golpe, y sin esto la escena lo paraba en 0.15 s
            bool fromKneel = kneelAtHit || State == EnemyState.Exhausted && !taunt;
            ReleaseToken();
            stance = taunt = false;
            look.SetStance(false);
            look.ClearTell();
            ClearQiWave(false);
            SetState(EnemyState.Alert);   // mira a Kaito; los golpes rebotan; sigue fijable (no se pierde el fijado)
            stateDuration = 99f;
            Imbalance = 0f;
            if (fromKneel)
            {
                // de rodillas: primero se para (si no, el fundido lo levantaba en 0.15 s)
                var rise = BambooMasterTimings.Get("ExhaustedRise" + suffix);
                anim.Play(rise.State, 0.08f);
                yield return new WaitForSeconds(rise.Seconds * 0.9f);
            }
            if (next == 1) yield return CoatOff();
            else yield return StaffCall();
            transition = null;
            if (!IsAlive) yield break;
            ReleaseToken();
            SetState(EnemyState.Chase);
            nextAttackTime = Time.time + 0.5f;
        }

        /// <summary>1 → 2: los ojos se encienden en jade, se saca el saco de un tirón y lo tira atrás; queda con las dos manos.</summary>
        IEnumerator CoatOff()
        {
            var c = BambooMasterTimings.PhaseCoat;
            anim.Play(c.State, 0.15f);
            Bark(StoryText.ChikuoLine("fase2"));
            sceneDone = 0f;
            yield return WaitEvent(c, "EyesIgnite");
            look.IgniteEyes(1f);
            Game.FX?.FlashLight(AimPoint + Vector3.up * 0.8f, BambooMasterLook.Jade, 3f, 4f, 0.5f);
            yield return WaitEvent(c, "CoatOff");
            look.ThrowCoat();
            Game.Audio?.Play("fin_whoosh", transform.position, 1f, 0.05f);
            Game.Audio?.SetBossMusicPhase(2);
            Game.Camera?.Punch(-3f, 0.4f);
            PushKaito(3.2f, 2f);
            yield return WaitEvent(c, "CoatLand");
            // cae detrás, a su izquierda (donde lo deja PhaseCoat): un golpe de polvo y el roce de la tela
            Vector3 land = transform.position - transform.forward * 2.5f - transform.right * 1.05f;
            Game.FX?.Dust(land, 1.6f);
            Game.Audio?.Play("fin_whoosh", land, 0.45f, 0.1f);
            yield return WaitEvent(c, "CoatRest");
            look.RestCoat(transform.parent);
            yield return WaitEvent(c, "Guard");
            SetPhase(1);
            subtitle = PhaseSubtitle(1);
            Game.UI?.BossRetitled(this);
            RewardKaito();
            yield return new WaitForSeconds(Mathf.Max(0f, (1f - c.Event("Guard")) * c.Seconds - 0.15f));
        }

        /// <summary>2 → 3: llama al bambú con la derecha; el bastón sale de entre las cañas, gira en el aire y lo atrapa.</summary>
        IEnumerator StaffCall()
        {
            var c = BambooMasterTimings.PhaseStaff;
            anim.Play(c.State, 0.15f);
            sceneDone = 0f;
            yield return WaitEvent(c, "StaffAppear");
            look.ShowStaff(true);
            Vector3 at = transform.position + transform.right * 3.4f + Vector3.up * 1.4f;
            Emit(SplinterTemplate(), at, Quaternion.LookRotation(-transform.right + Vector3.up * 0.4f), 1.2f);
            Emit(LeafTemplate(), at + Vector3.up * 0.8f, Quaternion.identity, 1.8f);
            Game.Audio?.Play("step_wood", at, 1f, 0.1f);
            Game.Audio?.Play("ability_wind", at, 0.6f, 0.05f);
            yield return WaitEvent(c, "StaffCatch");
            Game.Audio?.Play("clang", transform.position, 0.6f, 0.04f);
            Game.Audio?.SetBossMusicPhase(3);
            Game.Camera?.Shake(0.3f);
            yield return WaitEvent(c, "StaffPresent");
            Bark(StoryText.ChikuoLine("fase3"));
            Game.FX?.Shockwave(transform.position, 3f, BambooMasterLook.Jade);
            PushKaito(3.2f, 1.6f);
            yield return WaitEvent(c, "Guard");
            SetPhase(2);
            subtitle = PhaseSubtitle(2);
            Game.UI?.BossRetitled(this);
            RewardKaito();
            yield return new WaitForSeconds(Mathf.Max(0f, (1f - c.Event("Guard")) * c.Seconds - 0.15f));
        }

        /// <summary>Espera hasta el evento del clip de la escena (sceneDone = segundos del clip ya esperados).</summary>
        WaitForSeconds WaitEvent(MasterClip c, string ev)
        {
            float at = Mathf.Max(0f, c.Event(ev)) * c.Seconds;
            float w = Mathf.Max(0f, at - sceneDone);
            sceneDone = Mathf.Max(sceneDone, at);
            return new WaitForSeconds(w);
        }

        float sceneDone;

        void RewardKaito()
        {
            var p = Game.Player;
            if (p == null || !p.IsAlive) return;
            p.Heal(TransitionHeal);
            p.AddSpirit(TransitionSpirit);
            Game.FX?.HealBurst(p.transform.position);
            BandanaGlow.Ensure(p)?.Pulse(BandanaGlow.Gold, 1f);
        }

        // ================================================================== derrota
        /// <summary>Cuadro de Defeat desde el que sigue si lo vencen de rodillas: ya agachado con las piernas cruzadas y el
        /// bastón en el piso (de pie, Defeat arranca en la guardia y lo paraba 0.55 m en 0.3 s para volver a sentarlo).</summary>
        const float DefeatFromKneelFrame = 86f;
        /// <summary>El plano de la muerte de Boss (3.2 s + 1.2 de vuelta): el plano sentado espera a que termine.</summary>
        const float BossDeathShot = 4.4f;
        float defeatFrom;

        protected override bool DeathBurst => false;

        protected override void Die(in DamageInfo info, bool finisher = false)
        {
            if (State == EnemyState.Dead) return;
            bool knelt = State == EnemyState.Exhausted && !taunt;
            ClearQiWave(true);
            stance = taunt = false;
            look?.Extinguish();
            look?.ShowStanceRing(false);
            look?.StopLimbTrail();
            if (tipHideAt > 0f) { Game.UI?.HideTutorial(); tipHideAt = -1f; }
            base.Die(info, finisher);
            // Enemy cruza a Defeat en 0.06 s desde donde lo agarró el golpe: el clip arranca en la guardia del bastón
            var d = BambooMasterTimings.Defeat;
            defeatFrom = knelt ? d.FrameNorm(DefeatFromKneelFrame) : 0f;
            anim.Play(d.State, knelt ? 0.4f : 0.3f, defeatFrom);
            // no se esfuma: queda sentado en el claro y Kaito no lo atraviesa para tomar el sello (Enemy apagó los
            // colliders; el de la raíz vuelve a la medida del cuerpo sentado). Los golpes van por Combat, no por física
            var col = GetComponent<CapsuleCollider>();
            if (col != null)
            {
                col.radius = 0.6f;
                col.height = 1.5f;
                col.center = new Vector3(0f, 0.75f, 0f);
                col.enabled = true;
            }
        }

        /// <summary>
        /// No cae ni se hace humo: apoya el bastón, respira, lo suelta, se sienta a meditar y, ya con Kaito delante, le
        /// hace la reverencia mientras le da su última lección. Recién ahí deja el sello (OnDeathFinished).
        /// </summary>
        protected override IEnumerator DeathRoutine(Vector3 dir)
        {
            var d = BambooMasterTimings.Defeat;
            float t0 = Time.time;
            // el bastón contra el piso (de rodillas ya lo tenía apoyado: lo baja en el fundido)
            float land = d.Event("StaffLand");
            float toLand = land > defeatFrom ? (land - defeatFrom) * d.Seconds : 0.35f;
            yield return new WaitForSeconds(toLand);
            Game.Audio?.Play("step_wood", transform.position, land > defeatFrom ? 0.9f : 0.5f, 0.1f);
            Game.Audio?.Play("clang", transform.position, land > defeatFrom ? 0.25f : 0.12f, 0.15f);
            yield return new WaitForSeconds(Mathf.Max(0f, (1f - defeatFrom) * d.Seconds * 0.98f - toLand));
            anim.Play(BambooMasterTimings.Meditate.State, 0.3f);
            // los dos en cuadro, de costado, cuando terminó el plano de la muerte
            yield return new WaitForSeconds(Mathf.Max(0.6f, BossDeathShot - (Time.time - t0)));
            int shot = SeatedShot();
            anim.Play(BambooMasterTimings.SeatedBow.State, 0.25f);
            Game.Story?.PlayDialogueById("bamboo_defeat");
            yield return new WaitForSeconds(BambooMasterTimings.SeatedBow.Seconds);
            anim.Play(BambooMasterTimings.Meditate.State, 0.3f);
            // la última lección dura lo que el jugador tarde en leerla
            float wait = 0f;
            while ((Game.InCutscene || (Game.UI != null && Game.UI.DialogueOpen)) && wait < 60f) { wait += Time.unscaledDeltaTime; yield return null; }
            if (shot >= 0 && Game.Camera != null) Game.Camera.CancelShot(shot);
            OnDeathFinished();
            // los ojos se apagan despacio: la pelea terminó
            for (float t = 0f; t < 2f; t += Time.deltaTime) { look?.DimEyes(1f - t / 2f); yield return null; }
            look?.DimEyes(0f);
        }

        int SeatedShot()
        {
            if (Game.Camera == null) return -1;
            Vector3 c = transform.position;
            Vector3 f = transform.forward.Flat().normalized, side = Vector3.Cross(Vector3.up, f);
            // del lado de la cámara de juego: no cruza el eje
            if (Vector3.Dot(side, (Game.Camera.transform.position - c).Flat()) < 0f) side = -side;
            Vector3 pos = c + (side * 0.8f + f * 0.6f).normalized * 6.5f + Vector3.up * 2.2f;
            return Game.Camera.PlayStaticShot(pos, c + f * 1.2f + Vector3.up * 1.0f, 36f, 0f, 1.0f, 1.0f);
        }

        /// <summary>El sello aparece delante de él, entre los dos (el jefe se queda meditando en el claro).</summary>
        protected override void OnDeathFinished()
        {
            if (!hasSeal) return;
            Vector3 p = transform.position + transform.forward * 1.7f;
            if (NavMesh.SamplePosition(p, out var hit, 2f, NavMesh.AllAreas)) p = hit.position;
            var key = KeyPickup.Spawn(seal, p + Vector3.up * 0.2f);
            if (key != null && transform.parent != null) key.transform.SetParent(transform.parent, true);
            Game.FX?.Shockwave(p, 2f, BambooMasterLook.Jade);
        }

        // ================================================================== astillas y hojas del bastón
        static GameObject splinterTpl, leafTpl;

        static GameObject SplinterTemplate()
        {
            if (splinterTpl != null) return splinterTpl;
            splinterTpl = FXFactory.Sparks(new Color(0.78f, 0.72f, 0.38f), 16, 24, 8f, "BambooSplinters");
            splinterTpl.GetComponent<ParticleSystemRenderer>().sharedMaterial = FXMaterials.Alpha;
            var m = splinterTpl.GetComponent<ParticleSystem>().main;
            m.startSize = new ParticleSystem.MinMaxCurve(0.06f, 0.14f);
            m.startLifetime = new ParticleSystem.MinMaxCurve(0.3f, 0.7f);
            return splinterTpl;
        }

        static GameObject LeafTemplate()
        {
            if (leafTpl != null) return leafTpl;
            leafTpl = FXFactory.Leaves(new Color(0.42f, 0.66f, 0.3f), new Color(0.68f, 0.82f, 0.38f), 26, 1.2f, 1.5f, "BambooLeaves");
            return leafTpl;
        }

        static void Emit(GameObject tpl, Vector3 pos, Quaternion rot, float life)
        {
            var go = Pool.Spawn(tpl, pos, rot);
            var ps = go.GetComponent<ParticleSystem>();
            if (ps != null) { ps.Clear(true); ps.Play(true); }
            Pool.Despawn(go, life);
        }
    }
}
