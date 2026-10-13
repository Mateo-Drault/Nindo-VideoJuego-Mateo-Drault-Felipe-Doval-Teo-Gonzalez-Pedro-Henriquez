using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Gorō, el Martillo de Kodoyama, con su barra falsa y la fase de la armadura de roca (ítem 9 del traspaso):
    ///  * FASE 1 = la primera barra (config.maxHealth): el Gorō de siempre ('Terremoto' en su segunda mitad), sin remate.
    ///  * Cuando la barra se vacía, "le ganaste" (FakeDefeat): cae como cualquier jefe vencido (cámara lenta, la órbita de
    ///    la muerte, el golpe de victoria y la música que se va) pero sin bandera, sello ni cartel. Un silencio, la montaña
    ///    retumba y las 16 rocas de la armadura se arrancan de la pared de la cumbre y se le clavan una por una (ArmorRise,
    ///    GoroArmor), en un plano de costado. Se levanta, ruge y sale el cartel "Gorō / La Montaña Despierta".
    ///  * FASE 2: barra nueva entera, el tema de jefe vuelve y entra en su clímax: la barra falsa toca el golpe final de
    ///    la fase 1 y deja el silencio (SilenceBossMusic), y cuando vuelan las rocas SetBossMusicPhase(2, ...) agenda los
    ///    tambores para el instante en que se pone de pie.
    ///    Golpes más pesados y con variantes (EnemyArchetypes.GoroPhase2), la onda que sale por el piso (SlamWave) y la
    ///    AVALANCHA (GoroAvalanche). Mientras carga un golpe la roca rebota los cortes (ArmorWindow): hay que desviar o
    ///    esquivar y pegarle después. Con la vida se le va cayendo la armadura (y cada tramo roto le devuelve aire a Kaito).
    ///  * Reintento: morir en la primera barra vuelve a ella (la sorpresa de la barra falsa es la primera vez; las
    ///    siguientes la cinemática va más rápida y sin el silencio largo). Morir ARMADO arranca armado (retryArmored, como
    ///    los actos de Kokuyō y las fases de Chikuō): con las barras largas de la hora de juego, volver a la primera barra
    ///    después de cada muerte en la segunda dejaba al jugador promedio 20-50 min trabado (goro_fight_sim.py).
    /// bossId 'goro', flags, SealId.Montana y musicKey 'boss_goro' no cambian. Los cuadros de los clips y de la armadura
    /// salen de GoroTimings (generado desde los sidecars).
    /// </summary>
    public class GoroBoss : Boss, ICameraProfile
    {
        public const string ArmorSeenFlag = "goro_armor_seen";

        // ------------------------------------------------------------------------------------------- balance
        /// <summary>
        /// EL BALANCE DE LA PELEA, EN UN SOLO LUGAR (EnemyArchetypes.Goro toma de acá la primera barra y
        /// Tools/Dev/goro_fight_sim.py lee estos números de este archivo). Medido en Unity con el bot (main 76be027, barras
        /// 1000 + 1600, daño x0.5 / x0.4, cura por tramo 25): 'bot on bueno' ganó en 2:24 sin morir y 'bot on promedio'
        /// en 4:04 con 2 muertes; la simulación daba 3.4 y 5.2 min, así que con Gorō el bot real va 0.71x el modelo (se le
        /// pega y le corta las vueltas a la guardia). Objetivo: el bueno ~4.5 min reales, el promedio 1-2 muertes.
        /// Con estos números (las dos barras al doble, el daño a la mitad, más cura por tramo) y los clips de C3 la
        /// simulación da: bueno 6.4 min simulados = ~4.6 reales, sin morir; promedio 9.1 simulados = ~7 reales, 1.1
        /// muertes simuladas = ~1.5 reales, 35 % gana al primer intento (dos tercios de las muertes son armado: con 0.5 en
        /// las dos barras largas el promedio moría casi siempre en la barra falsa).
        ///  * FirstBarHealth: la barra falsa (fase 1, config.maxHealth) y ArmoredHealth la de la armadura (fase 2): se
        ///    mantiene la proporción de antes (la falsa es ~40 % de la pelea), así la sorpresa llega a mitad de camino.
        ///  * FirstBarDamage / ArmoredDamage: el daño de Gorō respecto del arquetipo en cada barra (golpes, onda y
        ///    avalancha). Con más vida el daño baja: si no, la pelea larga se vuelve desgaste y el promedio muere en la
        ///    fase 1, que el daño armado no toca. Son respecto del arquetipo, no uno del otro.
        ///  * ShedHealAmount: lo que recupera Kaito con cada tramo de armadura roto (ShedAt), la única cura de la pelea
        ///    larga además de TransitionHeal.
        /// </summary>
        public const float FirstBarHealth = 2000f, ArmoredHealth = 3200f;
        public const float FirstBarDamage = 0.25f, ArmoredDamage = 0.23f;
        public const float ShedHealAmount = 40f;

        /// <summary>Vida de la barra de la fase 2 (la de la fase 1 es config.maxHealth = FirstBarHealth).</summary>
        public float armoredHealth = ArmoredHealth;
        /// <summary>Daño de Gorō armado respecto del arquetipo (ArmoredDamage).</summary>
        public float armoredDamageScale = ArmoredDamage;
        /// <summary>Daño de Gorō en la primera barra respecto del arquetipo (FirstBarDamage).</summary>
        public float firstBarDamageScale = FirstBarDamage;
        /// <summary>Vida que recupera Kaito cada vez que le rompe un tramo de la armadura (ShedHealAmount).</summary>
        public float shedHeal = ShedHealAmount;
        /// <summary>Fracciones de la segunda barra en que se le cae un tramo de la armadura y las piezas de cada uno: un
        /// cuerno y una rodilla, el brazo izquierdo con el faldón y el pecho, y al final una hombrera y una cumbre de la
        /// espalda (las grandes quedan para el último). Al morir se le cae el resto.</summary>
        static readonly float[] ShedAt = { 0.75f, 0.5f, 0.25f };
        static readonly int[][] ShedPieces = { new[] { 15, 3 }, new[] { 7, 4, 9 }, new[] { 10, 13 } };
        /// <summary>
        /// Kaito no se cura en la pelea (solo +8 por "matar" la barra falsa): sin esto llegaba a la fase 2 con lo que le
        /// quedó de la 1 y moría ahí, volviendo a empezar de cero. Como los cambios de acto de Kokuyō (KokuyoBoss.RewardKaito).
        /// </summary>
        public const float TransitionHeal = 40f, TransitionSpirit = 30f;

        const int AvalWaves = 3;
        const float AvalOpenTime = 2.4f;
        // SlamWave: el martillo cae a HeadReach y la onda se abre por el piso en un carril. El carril arranca en el borde de
        // atrás del disco del martillazo y es tan ancho como el disco: lo rojo es lo que pega, nada más y nada menos
        static float HeadReach => GoroTimings.SlamWaveAt.y;
        const float WaveSpeed = 11f, ImpactRadius = 1.8f, WaveWidth = 2f * ImpactRadius;
        // la cumbre: la pared del cráter empieza a ~17.5 m del centro (Tools/Blender/world, mont_cumbre)
        const float RimRadius = 17.5f;
        // el retumbe antes de la primera roca
        const float RumbleTime = 0.6f;
        // StoryDirector.BossReintro devuelve el control a los 1.2 s: la re-presentación llega a la guardia justo ahí
        const float ReintroTime = 1.2f;
        // el plano de costado: tirado cerca y bajo (de 7.2 a 6 m: Gorō tirado ocupa dos tercios del ancho y las rocas que se
        // tiran de costado entran por los bordes, GoroArmor.PlanAssembly); desde que se arrodilla se aleja para que entren
        // las cumbres de la espalda y el martillo del rugido, hasta 10 m, mirando a 2.9 m desde 2.6 m: entero, del piso al
        // martillo en alto (a 12.5 m y mirando a 3.4 m el rugido quedaba chico, una figura en el medio de la cumbre: la
        // armadura recién armada es lo que se tiene que ver; Tools/Blender/bosses/goro/goro_rise_review)
        const float ShotStart = 7.2f, ShotNear = 6f, ShotFar = 10f, ShotFov = 42f;
        const float ShotFarUp = 2.6f, ShotFarLook = 2.9f;

        public bool Armored => armored;
        bool armored, inCinematic, assembling, wideFrame;
        // la escala de daño ya aplicada a los pasos de config (ScaleDamage): Boss.ResetEnemy restaura la config del
        // arquetipo y la vuelve a 1
        float appliedDamageScale = 1f;
        bool started;
        float assemblyClock;
        bool holdingCutscene, holdingLetterbox;
        int shot = -1;
        GoroArmor armor;
        GoroAvalanche avalanche;
        string baseTitle, baseSubtitle;
        float baseFinisherHealth = -1f;
        int shedStage;
        bool bounceHinted, barkPending;
        // murió con la armadura puesta: el reintento arranca armado (OnPlayerDied, OnBossStarted)
        bool retryArmored;
        Vector3 riseCamDir;

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
            started = true;
            SetDamageScale(firstBarDamageScale);
            ApplyFinisherGate();
            if (Defeated) return;
            avalanche = GoroAvalanche.Create(this);
            GameEvents.PlayerDied += OnPlayerDied;
            GameEvents.BossStarted += OnBossStarted;
        }

        protected override void OnDestroy()
        {
            base.OnDestroy();
            GameEvents.PlayerDied -= OnPlayerDied;
            GameEvents.BossStarted -= OnBossStarted;
            HoldCutscene(false);
            if (avalanche != null) Destroy(avalanche.gameObject);
        }

        void OnPlayerDied()
        {
            if (Fighting && armored) retryArmored = true;
        }

        /// <summary>
        /// El reintento después de morir armado: la re-presentación ya lo mostró con la armadura (ResetEnemy) y acá entra
        /// directo a la fase 2, sin la barra falsa ni la cinemática. La música arranca en su clímax: este evento sale en el
        /// mismo frame que PlayBossMusic (Boss.BeginFight), así el tema empieza en la fase 2.
        /// </summary>
        void OnBossStarted(Boss b)
        {
            if (b != this || !retryArmored || !Game.Save.HasFlag(ArmorSeenFlag)) return;
            ResumeAtPhase(1);   // la segunda mitad de la primera barra ya pasó ('Terremoto' y su aceleración)
            BeginArmored(true);
        }

        public override void ResetEnemy()
        {
            HoldCutscene(false);
            if (shot >= 0) { Game.Camera?.CancelShot(shot); shot = -1; }
            avalanche?.Clear(false);
            base.ResetEnemy();
            // (antes de Start no hay config guardada que restaurar: la escala que había sigue puesta)
            if (started) appliedDamageScale = 1f;
            SetDamageScale(firstBarDamageScale);
            armored = inCinematic = assembling = wideFrame = false;
            held = forceAvalanche = avalOpen = avalPause = barkPending = false;
            slamLive = false;
            shedStage = 0;
            armor.HideAll();
            if (baseTitle != null) { title = baseTitle; subtitle = baseSubtitle; }
            ApplyFinisherGate();
            // murió armado: espera con la armadura puesta y el epíteto (la re-presentación lo muestra así)
            if (retryArmored && Game.Save.HasFlag(ArmorSeenFlag))
            {
                armor.ShowAll();
                title = StoryText.Goro;
                subtitle = StoryText.GoroEpithet;
            }
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
            // la avalancha terminó por otro camino (una habilidad lo sacó del paso, el reintento): la cámara vuelve
            if (wideFrame && (avalanche == null || !avalanche.Active)) wideFrame = false;
        }

        void LateUpdate()
        {
            if (assembling) armor.TickAssembly(assemblyClock);
            armor.TickFalling(Time.deltaTime);
        }

        /// <summary>Lo que pega en el piso, en el mundo: (derecha, adelante) de GoroTimings respecto de Gorō.</summary>
        Vector3 Local(Vector2 rightForward) =>
            transform.position + transform.right * rightForward.x + transform.forward * rightForward.y;

        /// <summary>
        /// La presentación (StoryDirector.BossIntroRoutine) toca 'Intro' entera: acá el martillazo al piso. La re-presentación
        /// de un reintento dura ReintroTime: Intro arranca con el martillo ya en el hombro, más rápida, y llega a la guardia
        /// justo cuando vuelve el control (antes se cortaba en plena subida al hombro).
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
                    float speed = GoroTimings.IntroLength * (1f - GoroTimings.IntroRiseNorm) / ReintroTime;
                    anim.Play(introAnim, 0.15f, GoroTimings.IntroRiseNorm, speed);
                    prevAnim = introAnim;
                    introSlam = true;
                }
            }
            introClock += dt;
            if (!introSlam && introClock >= GoroTimings.IntroSlam)
            {
                introSlam = true;
                Vector3 h = Local(GoroTimings.IntroSlamAt);
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
            bool inAvalanche = held && State == EnemyState.Attack;
            var r = base.ReceiveHit(info);
            // una habilidad lo sacó de la llamada (Enemy la deja pasar la hiperarmadura): la montaña se calla con él, así
            // nunca hay rocas y martillazos a la vez
            if (inAvalanche && State != EnemyState.Attack) EndAvalanche(true);
            return r;
        }

        /// <summary>
        /// ¿Está cargando un golpe con la armadura puesta? (GoroTimings.ArmorWindow, la 'armor_window' de cada clip). La
        /// avalancha entera: pegado a Gorō, las rocas saltan por encima de él (GoroAvalanche), y sin esto quedarse a su lado
        /// regalaba seis segundos de cortes; la ventana para pegarle es la pausa en que queda abierto después.
        /// </summary>
        bool InArmorWindow()
        {
            var a = CurrentAttack;
            if (a == null) return false;
            if (a.special == "avalanche") return held || stepClock < GoroTimings.AvalArmorEnd;
            if (!GoroTimings.ArmorWindow(a.state, out float from, out float to)) { from = 0.08f; to = a.activeStart + 0.03f; }
            return stepNorm >= from && stepNorm <= to;
        }

        protected override void OnDamaged(in DamageInfo info)
        {
            base.OnDamaged(info);
            if (!armored) return;
            // la armadura se le va rompiendo en tramos (ShedAt); un golpe grande puede romper dos
            while (shedStage < ShedAt.Length && Health01 <= ShedAt[shedStage]) ShedGroup(info.direction, ShedPieces[shedStage++]);
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
            // romperle la montaña le devuelve el aire a Kaito: sin una cura la fase larga se volvía puro desgaste
            var k = Game.Player;
            if (k != null && k.IsAlive && shedHeal > 0f)
            {
                k.Heal(shedHeal);
                BandanaGlow.Ensure(k)?.Pulse(BandanaGlow.Gold, 0.6f);
            }
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
            // "le ganaste": el golpe final del tema en el próximo tiempo y después silencio. El tema sigue cargado: la
            // fase 2 entra desde ese silencio (StopBossMusic lo descargaba y la fase 2 arrancaba recién al pelear)
            Game.Audio?.SilenceBossMusic(0.4f, true);
            Game.FX?.EnemyDeath(AimPoint, dir, true);
            float t = 0f;
            bool knee = false, drop = false, hammer = false, back = false;
            while (t < GoroTimings.FakeLength / sp)
            {
                t += Time.deltaTime;
                float c = t * sp;
                if (!knee && c >= GoroTimings.FakeKnee) { knee = true; Game.FX?.Dust(transform.position + transform.forward * 0.4f, 0.8f); }
                if (!drop && c >= GoroTimings.FakeDrop) { drop = true; Game.FX?.Dust(transform.position + transform.forward * 0.6f, 1f); }
                if (!hammer && c >= GoroTimings.FakeHammerLand)
                {
                    hammer = true;
                    Game.Audio?.Play("rock_impact", transform.position, 0.7f);
                    // el mango cae acostado a lo largo de su brazo derecho (la cabeza quedó clavada adelante a la derecha)
                    Game.FX?.Dust(transform.position + transform.right * 1.65f + transform.forward * 0.2f, 1f);
                }
                if (!back && c >= GoroTimings.FakeBackHit)
                {
                    back = true;
                    Game.FX?.Dust(transform.position - transform.forward * 1.2f, 2f);
                    Game.Audio?.Play("hit_heavy", transform.position, 0.9f);
                    Game.Camera?.Shake(0.35f);
                }
                yield return null;
            }
            // el plano de la armadura se decide ya: Kaito camina fuera del cuadro durante el silencio
            riseCamDir = SideShotDirection();
            ClearShotOfKaito(riseCamDir);
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
            Vector3 camDir = riseCamDir;
            armor.PlanAssembly(arenaCenter, RimRadius, camDir, sp, GroundMask, GoroTimings.RiseKneel);
            float lead = armor.Lead;
            // el plano arranca con el retumbe (RumbleTime antes de la primera roca) y dura hasta el rugido y un poco más
            shot = PlayRiseShot(camDir, RumbleTime + lead + (GoroTimings.RiseLength + 0.5f) / sp,
                RumbleTime + lead + GoroTimings.RiseKneel / sp, RumbleTime + lead + GoroTimings.RiseRoar / sp);
            assemblyClock = -lead;
            // el retumbe solo: el reloj del vuelo (y la primera roca) arranca después
            yield return new WaitForSeconds(RumbleTime);
            assembling = true;
            // la frase de entrada de la fase 2 arranca con las rocas y sus tambores caen cuando se pone de pie
            Game.Audio?.SetBossMusicPhase(2, lead + GoroTimings.RiseStand / sp);
            bool started = false, titled = false, roared = false, peaked = false;
            while (assemblyClock < GoroTimings.RiseLength / sp)
            {
                assemblyClock += Time.deltaTime;
                if (!started && assemblyClock >= 0f)
                {
                    started = true;
                    // FakeDefeat termina en la pose de arranque de ArmorRise salvo el brazo derecho (el solver lo resuelve
                    // por otra rama: goro_checks mide ~18°): un fundido de 0.2 s entre dos poses quietas no se ve
                    anim.Play("ArmorRise", 0.2f, 0f, sp);
                }
                float c = assemblyClock * sp;
                // el cartel apenas se para: así se apagó antes de la primera avalancha (con el rugido se encimaba con ella)
                if (!titled && c >= GoroTimings.RiseStand)
                {
                    titled = true;
                    Game.UI?.ShowBossTitle(StoryText.Goro, StoryText.GoroEpithet);
                }
                if (!roared && c >= GoroTimings.RiseRoar)
                {
                    roared = true;
                    Game.Audio?.Play("boss_roar", transform.position, 1f);
                    Game.Camera?.Shake(0.6f);
                }
                if (!peaked && c >= GoroTimings.RisePeak)
                {
                    peaked = true;
                    Game.Camera?.Punch(-4f, 0.5f);
                    Game.FX?.Shockwave(transform.position, 7f, new Color(1f, 0.55f, 0.3f));
                    Game.FX?.FlashLight(AimPoint, new Color(1f, 0.55f, 0.25f), 6f, 12f, 0.6f);
                    Game.Input?.Rumble(0.9f, 0.6f, 0.5f);
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

        /// <summary>
        /// De costado (con un poco de frente) por su IZQUIERDA: ArmorRise clava el martillo a su derecha y desde ese lado el
        /// mango le tapaba el torso justo cuando se le pegan las hombreras y las cumbres. Si de ese lado no entra la cámara
        /// (cayó cerca de la pared), se corre hacia el centro de la cumbre.
        /// </summary>
        Vector3 SideShotDirection()
        {
            Vector3 fwd = transform.forward.Flat().normalized;
            Vector3 left = -Vector3.Cross(Vector3.up, fwd);
            Vector3 dir = (left * 0.85f + fwd * 0.45f).normalized;
            Vector3 toCenter = (arenaCenter - transform.position).Flat();
            Vector3 inward = toCenter.sqrMagnitude > 0.01f ? toCenter.normalized : -fwd;
            for (int i = 0; i < 8 && ((transform.position + dir * ShotFar) - arenaCenter).Flat().magnitude > RimRadius - 1.5f; i++)
                dir = Vector3.Slerp(dir, inward, 0.3f).Flat().normalized;
            return dir;
        }

        /// <summary>Si Kaito quedó entre la cámara y Gorō, camina hasta atrás y al costado de Gorō (se lo ve mirando).</summary>
        void ClearShotOfKaito(Vector3 dir)
        {
            var p = Game.Player;
            if (p == null || !p.IsAlive) return;
            Vector3 c = transform.position;
            Vector3 to = (p.transform.position - c).Flat();
            Vector3 perp = Vector3.Cross(Vector3.up, dir);
            float along = Vector3.Dot(to, dir), lat = Vector3.Dot(to, perp);
            // el cono del plano: delante de Gorō hacia la cámara y a menos de ~3 m del eje
            if (along < 0.5f || Mathf.Abs(lat) > 3f + along * 0.35f) return;
            float s = lat >= 0f ? 1f : -1f;
            Vector3 goal = c - dir * 2.5f + perp * (s * 4f);
            Vector3 off = (goal - arenaCenter).Flat();
            if (off.magnitude > arenaRadius - 1f) goal = arenaCenter + off.normalized * (arenaRadius - 1f);
            goal.y = c.y;
            p.ScriptedMoveTo(goal, 4.5f);
        }

        int PlayRiseShot(Vector3 dir, float duration, float kneel, float roar)
        {
            if (Game.Camera == null) return -1;
            Vector3 c = transform.position;
            // tirado: cerca y bajo, se acerca mientras las rocas se le pegan; desde que se arrodilla se aleja y sube hasta el
            // rugido, para que entren las cumbres de la espalda y el martillo en alto (Tools/Blender/bosses/goro/goro_rise_review)
            return Game.Camera.PlayShot(t =>
            {
                float a = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / kneel));
                float b = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01((t - kneel) / Mathf.Max(0.1f, roar - kneel)));
                float dist = Mathf.Lerp(Mathf.Lerp(ShotStart, ShotNear, a), ShotFar, b);
                Vector3 pos = c + dir * dist + Vector3.up * Mathf.Lerp(Mathf.Lerp(1.7f, 2.1f, a), ShotFarUp, b);
                Vector3 look = c + Vector3.up * Mathf.Lerp(Mathf.Lerp(0.7f, 1.3f, a), ShotFarLook, b);
                return new Pose(pos, Quaternion.LookRotation(look - pos));
            }, () => ShotFov, 0.9f, duration, 0.8f);
        }

        /// <summary>
        /// Barra nueva entera, el epíteto, el tema en su clímax y a pelear (la avalancha primero: se la presenta). 'retry':
        /// el reintento después de morir armado (Kaito ya reapareció entero y la avalancha ya la conoce).
        /// </summary>
        void BeginArmored(bool retry = false)
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
            SetDamageScale(armoredDamageScale);
            ApplyFinisherGate();
            // la barra como la de la fase 1: el nombre y el epíteto abajo (el cartel ya salió al pararse)
            title = StoryText.Goro;
            subtitle = StoryText.GoroEpithet;
            HoldCutscene(false);
            ExitScripted(false);
            SetState(EnemyState.Chase);
            IsAggro = true;
            target = Game.Player;
            // la avalancha espera a que se vaya el cartel: el carril rojo es el único aviso justo de la primera
            nextAttackTime = Time.time + (retry ? 0.6f : 3f);
            forceAvalanche = !retry;
            // el grito sale cuando termina esa primera avalancha (encima de ella tapaba los carriles de arriba)
            barkPending = !retry;
            Game.UI?.ShowBossBar(this);
            // la fase 2 ya entró al levantarse (ArmorRise); acá solo hace falta si se llegó sin la cinemática (DebugArmor).
            // Un PlayBossMusic acá reiniciaba el tema y cortaba los tambores recién caídos
            Game.Audio?.SetBossMusicPhase(2);
            var p = Game.Player;
            if (!retry && p != null && p.IsAlive)
            {
                p.Heal(TransitionHeal);
                p.AddSpirit(TransitionSpirit);
                BandanaGlow.Ensure(p)?.Pulse(BandanaGlow.Gold, 1f);
            }
        }

        /// <summary>Deja el daño de los pasos en 'scale' veces el del arquetipo (firstBarDamageScale, armoredDamageScale):
        /// multiplica cada paso una sola vez (los combos comparten pasos) por lo que falta desde la escala ya aplicada.</summary>
        void SetDamageScale(float scale)
        {
            float k = scale / Mathf.Max(0.01f, appliedDamageScale);
            appliedDamageScale = scale;
            if (Mathf.Approximately(k, 1f) || config.patterns == null) return;
            var done = new HashSet<AttackDef>();
            foreach (var pt in config.patterns)
            {
                if (pt == null || pt.steps == null) continue;
                foreach (var s in pt.steps)
                {
                    if (s == null || !done.Add(s)) continue;
                    s.damage *= k;
                    // la avalancha no pega con el martillo: su daño por roca va en specialParam
                    if (s.special == "avalanche") s.specialParam *= k;
                }
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
            // las de las piernas y el pecho son chicas en el plano: un empujón corto del lente marca cada golpe
            if (!big) Game.Camera?.Punch(-1.5f, 0.3f);
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
                    // la fase activa (la arada) dura lo que tarda la onda en llegar al final: el aviso sigue vivo
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
                    // del borde de atrás del disco del martillazo hasta el final de la onda
                    area = new TellArea { lane = true, origin = o + d * (HeadReach - ImpactRadius), forward = d, size = ImpactRadius + a.specialParam, width = WaveWidth };
                    return true;
                }
                default: return base.HitAreaFor(a, out area);
            }
        }

        /// <summary>El golpe sísmico pega donde cae la cabeza del martillo (antes, a 0.4 del alcance: entre los pies y el martillo).</summary>
        protected override Vector3 SlamCenter(AttackDef a) =>
            a.state == "Heavy" ? Local(GoroTimings.HeavyLandAt) : base.SlamCenter(a);

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

        /// <summary>Mientras ruedan rocas no arranca otro golpe (ni rondando ni persiguiendo): nunca carriles y martillazos a la vez.</summary>
        bool AvalancheBusy => avalanche != null && avalanche.Active;

        protected override void TickStrafe(float dt)
        {
            if (AvalancheBusy) nextAttackTime = Mathf.Max(nextAttackTime, Time.time + 0.4f);
            base.TickStrafe(dt);
        }

        // ------------------------------------------------------------------ avalancha
        void TickAvalancheStep(AttackDef a)
        {
            float c = stepClock;
            if (!avalStrike1 && c >= GoroTimings.AvalStrike1) { avalStrike1 = true; HammerToGround(GoroTimings.AvalStrike1At, 0.35f); }
            if (!avalStrike2 && c >= GoroTimings.AvalStrike2) { avalStrike2 = true; HammerToGround(GoroTimings.AvalStrike2At, 0.5f); }
            if (!avalCalled && c >= GoroTimings.AvalCall)
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
            if (!avalIdle && c >= GoroTimings.AvalLength) { avalIdle = true; anim.Play(config.animGuard, 0.3f); }
            // termina cuando no queda roca: el paso sigue con su línea de tiempo (ya pasada) y cierra el patrón
            if (avalCalled && held && (avalanche == null || !avalanche.Active)) { held = false; wideFrame = false; }
        }

        /// <summary>Corta la avalancha en curso (las rocas que ruedan se rompen donde están).</summary>
        void EndAvalanche(bool breakFx)
        {
            avalanche?.Clear(breakFx);
            held = false;
            wideFrame = false;
        }

        /// <summary>
        /// Los martillazos que llaman a la montaña: no pegan, así que no llevan el anillo de onda de los que sí (Heavy, el
        /// SlamWave); polvo, la grieta y el golpe, donde cae la cabeza del martillo.
        /// </summary>
        void HammerToGround(Vector2 at, float shake)
        {
            Vector3 h = Local(at);
            Game.FX?.GroundCrack(h, 2.4f);
            Game.FX?.Dust(h, 1.5f);
            Game.Audio?.Play("slam", h, 0.9f);
            Game.Camera?.Shake(shake);
            Game.Input?.Rumble(0.6f, 0.3f, 0.2f);
        }

        /// <summary>La avalancha se fuerza apenas se arma (se la presenta con su cartel) y después sale por sorteo.</summary>
        protected override void TickChase(float dt)
        {
            if (AvalancheBusy) nextAttackTime = Mathf.Max(nextAttackTime, Time.time + 0.4f);
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
            if (barkPending)
            {
                barkPending = false;
                Game.UI?.ShowBark(StoryText.Goro, StoryText.GoroLine("fase2"), UIFactory.Crimson, 3.2f);
            }
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
