using System.Collections;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Gorō, el Martillo de Kodoyama, con su barra falsa y la fase de la armadura de roca (ítem 9 del traspaso):
    ///  * FASE 1 = la primera barra (config.maxHealth): el Gorō de siempre ('Terremoto' en su segunda mitad), sin remate.
    ///  * Cuando la barra se vacía, "le ganaste" (FakeDefeat): cae como cualquier jefe vencido (cámara lenta, la órbita de
    ///    la muerte, el golpe de victoria y la música que se va) pero sin bandera, sello ni cartel. Un silencio, la montaña
    ///    retumba y las 16 rocas de la armadura se arrancan de la pared de la cumbre y se le clavan una por una (ArmorRise,
    ///    GoroArmor), en un plano de costado. Se levanta, ruge y sale el cartel "Gorō, la Montaña Despierta".
    ///  * FASE 2: barra nueva entera, el tema de jefe vuelve y entra en su clímax (PlayBossMusic + SetBossMusicPhase(2)).
    ///    Golpes más pesados y con variantes (EnemyArchetypes.GoroPhase2), la onda que sale por el piso (SlamWave) y la
    ///    AVALANCHA (GoroAvalanche). Mientras carga un golpe la roca rebota los cortes (ArmorWindow): hay que desviar o
    ///    esquivar y pegarle después. Con la vida se le va cayendo la armadura.
    ///  * Reintento: todo vuelve a la fase 1 (la armadura, el epíteto y la barra). La sorpresa de la barra falsa es la
    ///    primera vez; las siguientes la cinemática va más rápida y sin el silencio largo. Morir en la fase 2 vuelve a la
    ///    1 porque la fase 2 se gana conociendo a Gorō entero (y la 1 se aprende rápido: ~2 min con un jugador bueno).
    /// bossId 'goro', flags, SealId.Montana y musicKey 'boss_goro' no cambian.
    /// </summary>
    public class GoroBoss : Boss, ICameraProfile
    {
        public const string ArmorSeenFlag = "goro_armor_seen";
        /// <summary>Vida de la barra de la fase 2 (la de la fase 1 es config.maxHealth).</summary>
        public float armoredHealth = 520f;
        /// <summary>
        /// Kaito no se cura en la pelea (solo +8 por "matar" la barra falsa): sin esto llegaba a la fase 2 con lo que le
        /// quedó de la 1 y moría ahí, volviendo a empezar de cero. Como los cambios de acto de Kokuyō (KokuyoBoss.RewardKaito).
        /// </summary>
        public const float TransitionHeal = 40f, TransitionSpirit = 30f;

        // clip ArmorRise (GoroAnims.fbx.json): ruge en f184 y abre los brazos en f190; dura 7 s
        const float RiseRoar = 184f / 30f, RisePeak = 190f / 30f, RiseLength = 7f;
        // FakeDefeat: cae de espaldas en f53, quieto desde f60
        const float FakeDrop = 43f / 30f, FakeHammer = 47f / 30f, FakeBack = 53f / 30f, FakeLength = 2.6f;
        // AvalancheSummon: clava el martillo en f14 y f31, llama a la montaña en f48; la armadura aguanta hasta f66
        const float AvalStrike1 = 14f / 30f, AvalStrike2 = 31f / 30f, AvalCall = 48f / 30f, AvalArmorEnd = 66f / 30f, AvalLength = 2.8f;
        const int AvalWaves = 3;
        const float AvalOpenTime = 2.4f;
        // SlamWave: el martillo cae a 3.9 m y la onda se abre por el piso en un carril
        const float HeadReach = 3.9f, WaveSpeed = 11f, WaveWidth = 3.2f, ImpactRadius = 1.8f;
        // la cumbre: la pared del cráter empieza a ~17.5 m del centro (Tools/Blender/world, mont_cumbre)
        const float RimRadius = 17.5f;
        // el retumbe antes de la primera roca; ArmorRise se para en f148
        const float RumbleTime = 0.6f, RiseStand = 148f / 30f;

        public bool Armored => armored;
        bool armored, inCinematic, assembling, wideFrame;
        float assemblyClock;
        bool holdingCutscene, holdingLetterbox;
        int shot = -1;
        GoroArmor armor;
        GoroAvalanche avalanche;
        string baseTitle, baseSubtitle;
        float baseFinisherHealth = -1f;
        int shedStage;
        bool bounceHinted;

        // ---- presentación (y la versión corta del reintento)
        string prevAnim = "";
        float introClock;
        bool introSlam;

        // ---- avalancha
        bool held, avalStrike1, avalStrike2, avalCalled, avalIdle, forceAvalanche, avalOpen, avalPause;
        float savedImbalance;

        // ---- onda del SlamWave
        bool slamLive, slamHit;
        Vector3 slamO, slamD;
        float slamFront, slamMax, slamPrevAlong, slamFx;
        AttackDef slamAttack;

        static int groundMask = -1;
        static int GroundMask { get { if (groundMask == -1) groundMask = LayerMask.GetMask("Default"); return groundMask; } }

        // ================================================================== cámara
        public float CameraPitch => 0f;
        /// <summary>Más lejos con la armadura (es más alto) y durante la avalancha (se tiene que ver la pared de arriba).</summary>
        public float CameraExtraDistance => !armored ? 1.4f : wideFrame ? 3.4f : 2.4f;

        // ================================================================== fases
        /// <summary>0 = primera barra, 1 = su segunda mitad ('Terremoto'), 2 = armado.</summary>
        public override int CurrentPhase => armored ? 2 : Health01 <= 0.5f ? 1 : 0;

        // ================================================================== setup
        protected override void Awake()
        {
            base.Awake();
            armor = new GoroArmor(transform, model);
            armor.Launched += OnPieceLaunched;
            armor.Slammed += OnPieceSlammed;
            armor.Landed += OnPieceLanded;
        }

        protected override void Start()
        {
            base.Start();
            baseTitle = title;
            baseSubtitle = subtitle;
            baseFinisherHealth = config.finisherHealth;
            ApplyFinisherGate();
            if (!Defeated) avalanche = GoroAvalanche.Create(this);
        }

        protected override void OnDestroy()
        {
            base.OnDestroy();
            HoldCutscene(false);
            if (avalanche != null) Destroy(avalanche.gameObject);
        }

        public override void ResetEnemy()
        {
            HoldCutscene(false);
            if (shot >= 0) { Game.Camera?.CancelShot(shot); shot = -1; }
            avalanche?.Clear(false);
            base.ResetEnemy();
            armored = inCinematic = assembling = wideFrame = false;
            held = forceAvalanche = avalOpen = avalPause = false;
            slamLive = false;
            shedStage = 0;
            armor.HideAll();
            if (baseTitle != null) { title = baseTitle; subtitle = baseSubtitle; }
            ApplyFinisherGate();
        }

        /// <summary>Sin remate en la primera barra: la barra se vacía a golpes y "le ganaste". El remate es del final de verdad.</summary>
        void ApplyFinisherGate()
        {
            if (baseFinisherHealth < 0f) return;
            config.finisherHealth = armored ? baseFinisherHealth : -1f;
        }

        // ================================================================== por cuadro
        protected override void Update()
        {
            base.Update();
            float dt = Time.deltaTime;
            TickIntro(dt);
            TickSlamWave(dt);
        }

        void LateUpdate()
        {
            if (assembling) armor.TickAssembly(assemblyClock);
            armor.TickFalling(Time.deltaTime);
        }

        /// <summary>
        /// La presentación (StoryDirector.BossIntroRoutine) toca 'Intro' entera: acá el martillazo al piso del cuadro 13. La
        /// re-presentación de un reintento dura 1.2 s: Intro arranca en el rugido (f26) un poco más rápida y llega a la
        /// guardia justo cuando vuelve el control (antes se cortaba en plena subida al hombro).
        /// </summary>
        void TickIntro(float dt)
        {
            string cur = anim.Current;
            bool justStarted = cur == introAnim && prevAnim != introAnim;
            prevAnim = cur;
            if (State != EnemyState.Scripted || cur != introAnim || inCinematic) return;
            if (justStarted)
            {
                introClock = 0f;
                introSlam = false;
                if (!Fighting && Game.Save.HasFlag(StoryDirector.BossSeenFlag(bossId)))
                {
                    anim.Play(introAnim, 0.15f, 26f / 84f, 1.45f);
                    prevAnim = introAnim;
                    introSlam = true;
                }
            }
            introClock += dt;
            if (!introSlam && introClock >= 13f / 30f)
            {
                introSlam = true;
                Vector3 h = transform.position + transform.forward * 1.6f;
                Game.FX?.Shockwave(h, 4f, new Color(1f, 0.75f, 0.45f));
                Game.FX?.GroundCrack(h, 2.6f);
                Game.Audio?.Play("slam", h, 0.9f);
                Game.Camera?.Shake(0.4f);
            }
        }

        // ================================================================== golpes recibidos
        public override HitResult ReceiveHit(in DamageInfo info)
        {
            if (info.sourceFaction == Faction.Player && inCinematic) return HitResult.Ignored;
            // la roca rebota los cortes mientras carga el golpe (las habilidades y los contraataques sí entran)
            if (armored && info.sourceFaction == Faction.Player && info.kind != AttackKind.Ability && !info.riposte && InArmorWindow())
            {
                LastHitTime = Time.time;
                Game.FX?.Dust(info.point.sqrMagnitude > 0f ? info.point : AimPoint, 0.6f);
                if (!bounceHinted)
                {
                    bounceHinted = true;
                    Game.UI?.ShowToast(StoryText.GoroLine("coraza"), StoryText.GoroLine("coraza_sub"), UIFactory.Gold, 3f);
                }
                return HitResult.Blocked;
            }
            return base.ReceiveHit(info);
        }

        /// <summary>¿Está cargando un golpe con la armadura puesta? (GoroAnims.fbx.json, 'armor_window' de cada clip)</summary>
        bool InArmorWindow()
        {
            var a = CurrentAttack;
            if (a == null) return false;
            if (a.special == "avalanche") return stepClock < AvalArmorEnd;
            float from, to;
            switch (a.state)
            {
                case "Combo1B": from = 6f / 54f; to = 37f / 54f; break;
                case "Combo2B": from = 4f / 46f; to = 25f / 46f; break;
                case "Combo3B": from = 5f / 54f; to = 37f / 54f; break;
                case "SlamWave": from = 5f / 64f; to = 36f / 64f; break;
                default: from = 0.08f; to = a.activeStart + 0.03f; break;
            }
            return stepNorm >= from && stepNorm <= to;
        }

        protected override void OnDamaged(in DamageInfo info)
        {
            base.OnDamaged(info);
            if (!armored) return;
            // la armadura se le va rompiendo: a los dos tercios y al tercio de la barra se le caen pedazos
            if (shedStage == 0 && Health01 <= 0.66f) { shedStage = 1; ShedGroup(info.direction, 15, 7, 3); }
            if (shedStage == 1 && Health01 <= 0.33f) { shedStage = 2; ShedGroup(info.direction, 10, 13, 9, 4); }
        }

        void ShedGroup(Vector3 dir, params int[] ids)
        {
            foreach (int i in ids)
            {
                if (!armor.IsOn(i)) continue;
                Vector3 p = armor.PiecePosition(i);
                armor.Shed(i, dir, transform.position.y);
                Game.FX?.Dust(p, 1f);
                Game.FX?.Embers(p);
            }
            Game.Audio?.Play("boulder_break", transform.position, 0.8f);
            Game.Camera?.Shake(0.25f);
        }

        // ================================================================== la barra falsa
        protected override void Die(in DamageInfo info, bool finisher = false)
        {
            if (State == EnemyState.Dead) return;
            if (!armored)
            {
                if (!inCinematic) StartCoroutine(FakeDefeat(info.direction));
                return;
            }
            // la de verdad: la armadura se le desarma mientras cae
            avalanche?.Clear(true);
            slamLive = false;
            wideFrame = false;
            HoldCutscene(false);
            title = baseTitle; subtitle = baseSubtitle;
            base.Die(info, finisher);
            StartCoroutine(Crumble(info.direction));
        }

        IEnumerator Crumble(Vector3 dir)
        {
            for (int i = GoroArmor.Count - 1; i >= 0; i--)
            {
                if (!armor.IsOn(i)) continue;
                armor.Shed(i, dir, transform.position.y);
                yield return new WaitForSeconds(0.06f);
            }
        }

        /// <summary>
        /// "Le ganaste": todo lo de un jefe vencido salvo lo que lo hace definitivo (bandera, sello, cartel). Kaito queda
        /// guionado (sin letterbox: todavía parece la victoria) y Gorō cae de espaldas. Después, el silencio y la armadura.
        /// </summary>
        IEnumerator FakeDefeat(Vector3 dir)
        {
            inCinematic = true;
            bool seen = Game.Save.HasFlag(ArmorSeenFlag);
            float sp = seen ? 1.25f : 1f;
            EnterScripted();
            Stop();
            HoldCutscene(true, false);
            Game.UI?.HideBossBar();
            var p = Game.Player;
            if (p != null) p.ScriptedFace(transform.position);
            anim.Play("FakeDefeat", 0.08f, 0f, sp);
            Game.Time?.SlowMotion(0.2f, seen ? 0.5f : 1.0f, 0.02f, 0.5f);
            shot = Game.Camera != null ? Game.Camera.PlayBossDeathShot(transform) : -1;
            Game.Audio?.Play("boss_defeat", transform.position, 1f);
            Game.Audio?.StopBossMusic(seen ? 1f : 2f);
            Game.FX?.EnemyDeath(AimPoint, dir, true);
            float t = 0f;
            bool drop = false, hammer = false, back = false;
            while (t < FakeLength / sp)
            {
                t += Time.deltaTime;
                float c = t * sp;
                if (!drop && c >= FakeDrop) { drop = true; Game.FX?.Dust(transform.position + transform.forward * 0.6f, 1f); }
                if (!hammer && c >= FakeHammer) { hammer = true; Game.Audio?.Play("rock_impact", transform.position, 0.7f); }
                if (!back && c >= FakeBack)
                {
                    back = true;
                    Game.FX?.Dust(transform.position - transform.forward * 1.2f, 2f);
                    Game.Audio?.Play("hit_heavy", transform.position, 0.9f);
                    Game.Camera?.Shake(0.35f);
                }
                yield return null;
            }
            // el silencio: la música ya se fue, queda el viento de la cumbre
            yield return new WaitForSeconds(seen ? 0.4f : 1.6f);
            if (shot >= 0) { Game.Camera?.CancelShot(shot); shot = -1; }
            yield return ArmorRise(seen);
        }

        /// <summary>La montaña responde: retumba, las rocas se le pegan y se levanta (7 s de clip, más rápido en reintentos).</summary>
        IEnumerator ArmorRise(bool seen)
        {
            float sp = seen ? 1.3f : 1f;
            SetLetterbox(true);
            Game.Audio?.Play("avalanche_rumble", transform.position, 1f);
            Game.Camera?.Shake(0.3f);
            Game.Input?.Rumble(0.5f, 0.2f, 1.2f);
            // nieve que se desprende de la pared alrededor
            for (int i = 0; i < 8; i++)
            {
                Vector3 d = Quaternion.Euler(0f, i * 45f + Random.Range(-15f, 15f), 0f) * Vector3.forward;
                Game.FX?.Dust(arenaCenter + d * (RimRadius - 1f) + Vector3.up * 2f, 1.8f);
            }
            Vector3 camDir = SideShotDirection();
            armor.PlanAssembly(arenaCenter, RimRadius, camDir, sp, GroundMask);
            float lead = armor.Lead;
            // el plano arranca con el retumbe (RumbleTime antes de la primera roca) y dura hasta el rugido y un poco más
            shot = PlayRiseShot(camDir, RumbleTime + lead + (RiseLength + 0.5f) / sp, RumbleTime + lead + RiseStand / sp);
            assemblyClock = -lead;
            assembling = true;
            // el retumbe solo antes de que vuele la primera roca
            yield return new WaitForSeconds(RumbleTime);
            bool started = false, roared = false, peaked = false;
            while (assemblyClock < RiseLength / sp)
            {
                assemblyClock += Time.deltaTime;
                if (!started && assemblyClock >= 0f)
                {
                    started = true;
                    // FakeDefeat termina exacto en la pose de arranque de ArmorRise: sin fundido
                    anim.Play("ArmorRise", 0f, 0f, sp);
                }
                if (!roared && assemblyClock * sp >= RiseRoar)
                {
                    roared = true;
                    Game.Audio?.Play("boss_roar", transform.position, 1f);
                    Game.Camera?.Shake(0.6f);
                }
                if (!peaked && assemblyClock * sp >= RisePeak)
                {
                    peaked = true;
                    Game.Camera?.Punch(-4f, 0.5f);
                    Game.FX?.Shockwave(transform.position, 7f, new Color(1f, 0.55f, 0.3f));
                    Game.FX?.FlashLight(AimPoint, new Color(1f, 0.55f, 0.25f), 6f, 12f, 0.6f);
                    Game.Input?.Rumble(0.9f, 0.6f, 0.5f);
                    Game.UI?.ShowAreaTitle(StoryText.GoroTitle, "", "IconBoss");
                    // con el rugido se vienen abajo más rocas alrededor (del lado de atrás: no pasan por el lente)
                    for (int i = 0; i < 6; i++)
                    {
                        Vector3 d = Quaternion.Euler(0f, 90f + i * 36f + Random.Range(-12f, 12f), 0f) * camDir;
                        Vector3 wall = arenaCenter + d * (RimRadius + 1.5f);
                        wall.y = transform.position.y + 6f;
                        avalanche?.Fling(wall, transform.position + d * Random.Range(4f, 7f), i * 0.12f, Random.Range(0.9f, 1.2f), Random.Range(0.5f, 0.8f));
                    }
                    var p = Game.Player;
                    if (p != null && CombatMath.FlatDistance(p.transform.position, transform.position) < 5f)
                        p.Push(p.transform.position - transform.position, 3f);
                }
                yield return null;
            }
            assembling = false;
            armor.FinishAssembly();
            Game.Save.SetFlag(ArmorSeenFlag);
            BeginArmored();
        }

        /// <summary>De costado (con un poco de frente), del lado que da al centro de la cumbre: ahí hay lugar para la cámara.</summary>
        Vector3 SideShotDirection()
        {
            Vector3 fwd = transform.forward.Flat().normalized;
            Vector3 right = Vector3.Cross(Vector3.up, fwd);
            Vector3 toCenter = (arenaCenter - transform.position).Flat();
            Vector3 side = Vector3.Dot(right, toCenter) >= 0f ? right : -right;
            Vector3 dir = (side * 0.85f + fwd * 0.45f).normalized;
            Vector3 inward = toCenter.sqrMagnitude > 0.01f ? toCenter.normalized : -fwd;
            for (int i = 0; i < 8 && ((transform.position + dir * 10.5f) - arenaCenter).Flat().magnitude > arenaRadius; i++)
                dir = Vector3.Slerp(dir, inward, 0.3f).Flat().normalized;
            return dir;
        }

        int PlayRiseShot(Vector3 dir, float duration, float stand)
        {
            if (Game.Camera == null) return -1;
            Vector3 c = transform.position;
            // tirado: cerca y bajo, se acerca mientras las rocas se le pegan; cuando se para (f148) se aleja y sube para que
            // entren las cumbres de la espalda y el martillo arriba del rugido (de 8.5 m arriba se cortaba)
            return Game.Camera.PlayShot(t =>
            {
                float a = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / stand));
                float b = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01((t - stand) / (duration - stand)));
                float dist = Mathf.Lerp(Mathf.Lerp(8.5f, 6.8f, a), 11f, b);
                Vector3 pos = c + dir * dist + Vector3.up * Mathf.Lerp(Mathf.Lerp(1.7f, 2.1f, a), 2.8f, b);
                Vector3 look = c + Vector3.up * Mathf.Lerp(Mathf.Lerp(0.7f, 1.3f, a), 3.0f, b);
                return new Pose(pos, Quaternion.LookRotation(look - pos));
            }, () => 42f, 0.9f, duration, 0.8f);
        }

        /// <summary>Barra nueva entera, el epíteto, el tema en su clímax y a pelear (la avalancha primero: se la presenta).</summary>
        void BeginArmored()
        {
            armored = true;
            inCinematic = false;
            if (shot >= 0) { Game.Camera?.CancelShot(shot); shot = -1; }
            SetLetterbox(false);
            config.maxHealth = armoredHealth;
            Health = config.maxHealth;
            Imbalance = 0f;
            // más agresivo y con ventanas un poco más cortas (Boss.ResetEnemy vuelve a la config original)
            config.attackCooldown *= 0.8f;
            config.exhaustedTime = 3.4f;
            ApplyFinisherGate();
            title = StoryText.GoroTitleBar;
            subtitle = StoryText.GoroEpithet;
            HoldCutscene(false);
            ExitScripted(false);
            SetState(EnemyState.Chase);
            IsAggro = true;
            target = Game.Player;
            nextAttackTime = Time.time + 1.4f;
            forceAvalanche = true;
            Game.UI?.ShowBossBar(this);
            Game.Audio?.PlayBossMusic(musicKey);
            Game.Audio?.SetBossMusicPhase(2);
            Game.UI?.ShowBark("Gorō", StoryText.GoroLine("fase2"), UIFactory.Crimson, 3.2f);
            var p = Game.Player;
            if (p != null && p.IsAlive)
            {
                p.Heal(TransitionHeal);
                p.AddSpirit(TransitionSpirit);
                BandanaGlow.Ensure(p)?.Pulse(BandanaGlow.Gold, 1f);
            }
        }

        // ------------------------------------------------------------------ efectos de cada roca
        void OnPieceLaunched(int i, Vector3 at)
        {
            Game.FX?.Dust(at, 1.4f);
            Game.Audio?.Play("boulder_break", at, 0.55f);
            // y otra roca grande que se desprende de la pared y cae cerca: la montaña entera se le viene encima
            Vector3 c = transform.position;
            Vector3 d = Quaternion.Euler(0f, Random.Range(-35f, 35f), 0f) * (at - c).Flat().normalized;
            Vector3 wall = arenaCenter + d * (RimRadius + 1.5f);
            wall.y = c.y + 5f;
            Vector3 land = c + Quaternion.Euler(0f, Random.Range(-40f, 40f), 0f) * d * Random.Range(2.2f, 4f);
            avalanche?.Fling(wall, land, Random.Range(0f, 0.25f), Random.Range(1.0f, 1.4f), Random.Range(0.35f, 0.6f));
        }

        void OnPieceSlammed(int i, Vector3 at)
        {
            // las grandes (hombreras, cumbres de la espalda) pesan más
            bool big = i >= 10 && i <= 13;
            Game.FX?.Dust(at, big ? 1.5f : 0.9f);
            Game.FX?.Embers(at);
            Game.Audio?.Play("rock_impact", at, big ? 1f : 0.8f);
            Game.Camera?.Shake(big ? 0.3f : 0.14f);
            Game.Input?.Rumble(big ? 0.6f : 0.3f, 0.2f, 0.12f);
        }

        void OnPieceLanded(int i, Vector3 at) => Game.FX?.Dust(at, 0.8f);

        // ------------------------------------------------------------------ cinemática propia
        /// <summary>Bloquea el control y deja a Kaito guionado e invulnerable; se suelta sí o sí en el reintento.</summary>
        void HoldCutscene(bool on, bool letterbox = false)
        {
            if (on != holdingCutscene)
            {
                holdingCutscene = on;
                Game.InCutscene = on;
                if (Game.Input != null) Game.Input.GameplayBlocked = on || Game.IsPaused;
                var p = Game.Player;
                if (p != null && p.IsAlive) { if (on) p.EnterScripted(); else p.ExitScripted(); }
                if (!on) Game.Input?.ClearBuffer();
            }
            if (on && letterbox) SetLetterbox(true);
            if (!on) SetLetterbox(false);
        }

        void SetLetterbox(bool on)
        {
            if (on == holdingLetterbox) return;
            holdingLetterbox = on;
            Game.UI?.Letterbox(on);
        }

        // ================================================================== golpes de la fase 2
        protected override bool StepHeld => held;

        protected override void OnStepStarted(AttackDef a)
        {
            base.OnStepStarted(a);
            held = false;
            switch (a.special)
            {
                case "avalanche":
                    // lleva su reloj: el clip va a su ritmo y el paso espera a que pase la última roca
                    held = true;
                    avalStrike1 = avalStrike2 = avalCalled = avalIdle = false;
                    anim.SetSpeed(1f);
                    break;
                case "slamwave":
                    // la fase activa (la arada, f34-f43) dura lo que tarda la onda en llegar al final: el aviso sigue vivo
                    slamLive = slamHit = false;
                    slamAttack = a;
                    tl.sustain = Mathf.Max(0.1f, a.specialParam / WaveSpeed);
                    break;
            }
        }

        protected override float TellTravel(AttackDef a)
        {
            if (a.special == "slamwave" && target != null)
                return Mathf.Clamp(DistToTarget - HeadReach, 0f, a.specialParam) / WaveSpeed;
            return base.TellTravel(a);
        }

        protected override float ComputeStrikeEta(AttackDef a)
        {
            switch (a.special)
            {
                case "avalanche": return target != null && avalanche != null ? avalanche.NextEta(target.transform.position, out _) : float.PositiveInfinity;
                case "slamwave": return SlamWaveEta(a);
                default: return base.ComputeStrikeEta(a);
            }
        }

        protected override bool HitAreaFor(AttackDef a, out TellArea area)
        {
            switch (a.special)
            {
                case "avalanche":
                    area = default;
                    return target != null && avalanche != null && !float.IsInfinity(avalanche.NextEta(target.transform.position, out area));
                case "slamwave":
                {
                    Vector3 o = slamLive || specialFired ? slamO : transform.position;
                    Vector3 d = slamLive || specialFired ? slamD : transform.forward.Flat().normalized;
                    area = new TellArea { lane = true, origin = o, forward = d, size = HeadReach + a.specialParam, width = WaveWidth };
                    return true;
                }
                default: return base.HitAreaFor(a, out area);
            }
        }

        protected override void TickSpecial(AttackDef a, float dt)
        {
            switch (a.special)
            {
                case "avalanche": TickAvalancheStep(a); break;
                case "slamwave":
                    if (!specialFired && stepNorm >= a.activeStart) { specialFired = true; FireSlamWave(a); }
                    // la onda ya no lo va a alcanzar (salió del carril, o el frente ya pasó): el aviso se deshace sin golpe
                    if (specialFired && !slamHit && float.IsInfinity(SlamWaveEta(a)))
                    {
                        EndTell(TellOutcome.Cancelled);
                        slamHit = true;
                    }
                    break;
                default: base.TickSpecial(a, dt); break;
            }
        }

        // ------------------------------------------------------------------ avalancha
        void TickAvalancheStep(AttackDef a)
        {
            float c = stepClock;
            if (!avalStrike1 && c >= AvalStrike1) { avalStrike1 = true; HammerToGround(0.35f); }
            if (!avalStrike2 && c >= AvalStrike2) { avalStrike2 = true; HammerToGround(0.5f); }
            if (!avalCalled && c >= AvalCall)
            {
                avalCalled = true;
                wideFrame = true;
                Game.Audio?.Play("boss_roar", transform.position, 0.9f);
                Game.Camera?.Shake(0.5f);
                Game.UI?.ShowDanger(this);
                if (!Game.Save.HasFlag("goro_avalanche_seen"))
                {
                    Game.Save.SetFlag("goro_avalanche_seen");
                    Game.UI?.ShowToast(StoryText.GoroLine("avalancha"), StoryText.GoroLine("avalancha_sub"), UIFactory.Crimson, 3.2f);
                }
                avalanche?.Begin(AvalWaves, a.specialParam, a.knockback);
            }
            if (!avalIdle && c >= AvalLength) { avalIdle = true; anim.Play(config.animGuard, 0.3f); }
            // termina cuando no queda roca: el paso sigue con su línea de tiempo (ya pasada) y cierra el patrón
            if (avalCalled && held && (avalanche == null || !avalanche.Active)) { held = false; wideFrame = false; }
        }

        void HammerToGround(float shake)
        {
            Vector3 h = transform.position + transform.forward * 2.4f;
            Game.FX?.Shockwave(h, 3.5f, new Color(1f, 0.75f, 0.45f));
            Game.FX?.GroundCrack(h, 2.4f);
            Game.FX?.Dust(h, 1.3f);
            Game.Audio?.Play("slam", h, 0.9f);
            Game.Camera?.Shake(shake);
            Game.Input?.Rumble(0.6f, 0.3f, 0.2f);
        }

        /// <summary>La avalancha se fuerza apenas se arma (se la presenta con su cartel) y después sale por sorteo.</summary>
        protected override void TickChase(float dt)
        {
            if (forceAvalanche && armored && Time.time >= nextAttackTime && target != null && target.IsAlive && Game.Combat != null && Game.Combat.RequestAttackToken(this))
            {
                forceAvalanche = false;
                pattern = FindPattern(EnemyArchetypes.GoroAvalanchePattern);
                if (pattern != null) { StartAttack(false); return; }
                ReleaseToken();
            }
            base.TickChase(dt);
        }

        AttackPattern FindPattern(string n)
        {
            if (config.patterns != null) foreach (var p in config.patterns) if (p != null && p.name == n) return p;
            return null;
        }

        /// <summary>Después de la avalancha queda abierto (resopla con la guardia baja): la recompensa por sobrevivirla.</summary>
        protected override void ComboEnd()
        {
            bool aval = pattern != null && pattern.name == EnemyArchetypes.GoroAvalanchePattern;
            if (!aval) { base.ComboEnd(); return; }
            ReleaseToken();
            pattern = null;
            nextAttackTime = Time.time + AvalOpenTime + Random.Range(config.attackCooldown.x, config.attackCooldown.y);
            avalOpen = true;
            savedImbalance = Imbalance;
            BecomeExhausted();
        }

        protected override void BecomeExhausted()
        {
            bool broken = Imbalance >= config.maxImbalance - 0.01f;
            avalPause = !broken && avalOpen;
            base.BecomeExhausted();
            if (!avalPause) return;
            stateDuration = AvalOpenTime;
            anim.Play(config.animGuard, 0.25f);
        }

        protected override bool ExhaustedFeedback => !avalPause;

        protected override void OnExhaustionEnded()
        {
            if (avalOpen) Imbalance = savedImbalance;
            avalOpen = avalPause = false;
            base.OnExhaustionEnded();
        }

        // ------------------------------------------------------------------ onda del SlamWave
        void FireSlamWave(AttackDef a)
        {
            slamO = transform.position;
            slamD = transform.forward.Flat().normalized;
            Vector3 h = slamO + slamD * HeadReach;
            Game.FX?.Shockwave(h, 3f, new Color(1f, 0.6f, 0.35f));
            Game.FX?.GroundCrack(h, 2.8f);
            Game.Camera?.Shake(0.7f);
            Game.Audio?.Play("slam", h, 1f);
            Game.Input?.Rumble(0.9f, 0.6f, 0.3f);
            slamFront = HeadReach;
            slamMax = HeadReach + a.specialParam;
            slamLive = true;
            slamFx = 0f;
            if (target == null) return;
            Vector3 k = target.transform.position;
            slamPrevAlong = Vector3.Dot((k - slamO).Flat(), slamD);
            // a quemarropa del martillo: el golpe mismo
            if (CombatMath.FlatDistance(k, h) <= ImpactRadius + target.Radius && Mathf.Abs(k.y - h.y) < 2.5f)
            {
                slamHit = true;
                HitPlayer(a, h);
            }
        }

        /// <summary>El frente de la onda corre por el carril; pega una vez, al cruzar a Kaito, y solo con su aviso vivo.</summary>
        void TickSlamWave(float dt)
        {
            if (!slamLive) return;
            float prev = slamFront;
            slamFront = Mathf.Min(slamMax, slamFront + WaveSpeed * dt);
            slamFx -= dt;
            if (slamFx <= 0f)
            {
                slamFx = 0.07f;
                Vector3 f = slamO + slamD * slamFront;
                Game.FX?.GroundCrack(f, 1.2f);
                Game.FX?.Dust(f, 0.9f);
            }
            if (!slamHit && target != null && target.IsAlive && IsAlive)
            {
                Vector3 to = (target.transform.position - slamO).Flat();
                float along = Vector3.Dot(to, slamD);
                float lat = Mathf.Abs(Vector3.Dot(to, Vector3.Cross(Vector3.up, slamD)));
                // contra dónde estaba el frame anterior: corriendo hacia Gorō se salteaba la franja de un frame
                if (lat <= WaveWidth * 0.5f + target.Radius && slamPrevAlong >= prev - target.Radius && along <= slamFront + target.Radius && along >= HeadReach - target.Radius)
                {
                    slamHit = true;
                    if (InTell && CurrentAttack == slamAttack) HitPlayer(slamAttack, slamO + slamD * slamFront);
                }
                slamPrevAlong = along;
            }
            if (slamFront >= slamMax - 1e-3f)
            {
                slamLive = false;
                Vector3 end = slamO + slamD * slamMax;
                Game.FX?.Dust(end, 1.3f);
                Game.FX?.SmokePuff(end, 0.9f);
            }
        }

        /// <summary>
        /// Cuándo llega el golpe a Kaito: antes del martillazo, lo que falta más el viaje de la onda hasta donde está (nunca
        /// infinito: todavía puede meterse en el carril); después, infinito si quedó afuera del carril o el frente ya pasó.
        /// </summary>
        float SlamWaveEta(AttackDef a)
        {
            if (target == null || slamHit) return float.PositiveInfinity;
            Vector3 o = specialFired ? slamO : transform.position;
            Vector3 d = specialFired ? slamD : transform.forward.Flat().normalized;
            Vector3 to = (target.transform.position - o).Flat();
            float along = Vector3.Dot(to, d);
            if (!specialFired)
                return Mathf.Max(0f, tl.T - stepClock) + (Mathf.Clamp(along - target.Radius, HeadReach, HeadReach + a.specialParam) - HeadReach) / WaveSpeed;
            float lat = Mathf.Abs(Vector3.Dot(to, Vector3.Cross(Vector3.up, d)));
            if (!slamLive || lat > WaveWidth * 0.5f + target.Radius || along < slamFront - target.Radius - 0.3f || along > slamMax + target.Radius)
                return float.PositiveInfinity;
            // pega cuando el frente llega al borde de Kaito (TickSlamWave): la cuenta es hasta ahí
            return Mathf.Max(0f, along - target.Radius - slamFront) / WaveSpeed;
        }

#if UNITY_EDITOR || DEVELOPMENT_BUILD
        /// <summary>Pruebas (RunCommand): vida de la barra actual (0..1). 0.02 y un golpe = la barra falsa.</summary>
        public void DebugSetHealth01(float v) => Health = Mathf.Clamp01(v) * config.maxHealth;

        /// <summary>Pruebas: salta a la fase 2 sin la cinemática (armadura puesta, barra nueva).</summary>
        public void DebugArmor()
        {
            if (armored || !IsAlive) return;
            StopAllCoroutines();
            EnterScripted();
            armor.ShowAll();
            BeginArmored();
        }

        /// <summary>Pruebas: la avalancha ya (fase 2).</summary>
        public void DebugAvalanche() { if (armored) { forceAvalanche = true; nextAttackTime = Time.time; } }
#endif
    }
}
