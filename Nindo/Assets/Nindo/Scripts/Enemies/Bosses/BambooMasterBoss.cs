using System.Collections;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Chikuō, el Maestro del Bambú (arquetipo y bossId "ozeki": las partidas, las banderas y el Sello del Bambú siguen
    /// igual). Un anciano de kung fu de 2.67 m que guarda el sello que le dejó Kokuyō, su alumno de un invierno, y solo se
    /// lo da a quien muestre paciencia. La pelea enseña eso:
    ///  * Fase 1, "una mano" (100-66 %): pelea con la izquierda en la espalda. Palma, mano de sable y pico de grulla
    ///    (dorados) de a uno y en pares; la grulla voladora (roja) cae sobre una marca en el piso.
    ///  * Fase 2, "las dos manos" (66-33 %): se saca el saco y se le encienden los ojos de jade. Palmas gemelas, patada
    ///    giratoria, la barrida a ras del piso, la onda de qi y el paso del viento (embestida con imágenes residuales).
    ///  * Fase 3, "el bastón" (33-0 %): llama a un bastón de bambú. Todo llega más lejos y las cadenas terminan en rojo.
    ///  * La postura del bambú: después de algunos combos se cubre con las palmas en jade. Pegarle ahí es lo que él
    ///    espera: te desvía y contragolpea (dorado; una parada perfecta del contragolpe le quiebra la postura). Esperar
    ///    sin pegar lo deja abierto: baja la guardia y te llama (Taunt).
    /// Los cambios de fase son escenas cortas (los golpes rebotan) con la música en su fase y un poco de vida y Espíritu
    /// para Kaito. Vencido no muere: se sienta a meditar, saluda y deja el sello delante (BambooMasterBoss.Story.cs).
    /// Cada golpe sale de los tiempos del clip (BambooMasterTimings) y el cuerpo avanza lo que avanza el clip.
    /// </summary>
    public partial class BambooMasterBoss : Boss, ICameraProfile
    {
        /// <summary>Vida (fracción) donde termina cada fase: 1 → 66 %, 2 → 33 %, 3 → 0. Son pisos: el golpe que lo baja al
        /// umbral dispara el cambio y lo que sobra no se cuenta (cada fase dura lo que tiene que durar).</summary>
        public static readonly float[] Gates = { 1f, 0.66f, 0.33f, 0f };
        /// <summary>Chance de tomar la postura del bambú al terminar un combo, por fase (si no, guardia común; nunca dos
        /// seguidas). Es la pausa que enseña a esperar: con 0.35 casi no aparecía.</summary>
        static readonly float[] StanceChance = { 0.45f, 0.4f, 0.35f };
        /// <summary>Cuánto sostiene la postura antes de bajar la guardia (s, al azar entre los dos).</summary>
        static readonly Vector2 StanceTime = new Vector2(1.8f, 2.6f);
        /// <summary>Golpes que aguanta abierto: de rodillas (postura quebrada) y llamando a Kaito (esperó la postura). Con
        /// 4 y 3 el bot "bueno" lo terminaba en ~2 min: cada hueco pesaba demasiado (Tools/Dev/sim_bamboo_master.py).</summary>
        const int KneelHitCap = 3, TauntHitCap = 2;
        /// <summary>
        /// Cortes a su guardia (o en neutral) con menos de esto entre uno y otro cuentan seguidos: el segundo lo hace
        /// contestar enseguida y el tercero se contragolpea (Bounce). Atrapa el combo (el 2.º corte llega 0.3 s después del
        /// 1.º, el 3.º 0.45 s después del 2.º), no al que tantea de a un corte y espera: con 1.5 s cada toque suelto
        /// terminaba en contragolpe y la pelea era una cinta de contragolpes (36 de los 50 golpes de Chikuō contra el bot
        /// "bueno"), en vez de sus combos y sus huecos.
        /// </summary>
        const float BounceWindow = 0.55f;
        /// <summary>Segundos que queda la pista de la postura en pantalla.</summary>
        const float TipSeconds = 5f;
        static readonly Color GhostJade = new Color(0.62f, 1f, 0.86f, 0.42f);
        static readonly Color BarkColor = new Color(0.62f, 0.95f, 0.8f);

        // cámara: un poco más lejos que la de combate (la embestida y la grulla voladora cruzan medio claro)
        public float CameraPitch => 0f;
        public float CameraExtraDistance => 1.6f;

        public override int CurrentPhase => phaseIdx;
        public bool Transitioning => transition != null;

        BambooMasterLook look;
        int phaseIdx;
        string suffix = "";
        Coroutine transition;
        // el paso del viento y la grulla voladora son dos patrones cada uno (desde lejos y con el salto atrás antes):
        // TeachDash y TeachLeap pesan los dos
        AttackPattern counterPattern, teachLeapA, teachLeapB, teachDashA, teachDashB;
        float teachDashWeight, teachLeapWeightA, teachLeapWeightB, phaseStart;
        string baseSubtitle;

        // paso en curso
        MasterClip clip;
        float travelDone, airStretch = 1f;
        bool landed, afterRecoil, dashFx;
        // el golpe con paso adelante elige en la suelta la variante de paso que entra hasta Kaito (PickReach); cargándolo
        // desvía el primer corte de Kaito (Bounce)
        bool reachPicked, stepYielded;
        // la estela del miembro que pega (mano o pie; el bastón usa la de Enemy)
        bool limbTrailOn;
        string prevChainTo = "READY";
        Vector3 leapStart, leapDir;
        float leapTarget;
        bool leapFixed;

        // postura del bambú y la pausa en que llama a Kaito
        bool stance, taunt, stanceTaught, deflectToldOnce, waitToldOnce;
        float stanceUntil, savedImbalance, tipHideAt = -1f;
        bool forceStanceOnce = true;
        // de rodillas: reloj del clip (se frena con el hit-stop)
        float kneelClock, kneelStart = -99f;
        float fightStart;

        // locomoción lateral y hacia atrás (los blend trees solo tienen quieto, camina y corre)
        string strafeWanted = "Locomotion";
        float strafeWantedFor;
        bool sideSpeedSet;

        // nombres de los estados de la fase (se arman en SetPhase: concatenarlos en cada frame asignaba strings)
        string locoName = "Locomotion", strafeLName = "StrafeL", strafeRName = "StrafeR", walkBackName = "WalkBack",
               exhaustedHitName = "ExhaustedHit", hitHeavyName = "HitHeavy", parriedPerfectName = "ParriedPerfect",
               riseName = "ExhaustedRise", tauntName = "Taunt", stanceName = "Stance", guardHitName = "GuardHit",
               guardHitLName = "GuardHitL";

        // contraataque de Kaito después de un parry: cuántos cortes más le entran y hasta cuándo (Bounces)
        float riposteUntil = -1f;
        int riposteLeft;
        bool lastParryPerfect;
        // el golpe que lo agarró arrodillado (el cambio de fase primero lo para: TransitionRoutine)
        bool kneelAtHit;

        // ================================================================== setup
        protected override void Start()
        {
            base.Start();
            if (Defeated) return;
            baseSubtitle = subtitle;
            look = new BambooMasterLook(model);
            counterPattern = BambooMasterMoves.Counter(0);
            GameEvents.BossStarted += OnBossStarted;
            GameEvents.PlayerDied += OnPlayerDied;
            WaitPose();
        }

        protected override void OnDestroy()
        {
            base.OnDestroy();
            GameEvents.BossStarted -= OnBossStarted;
            GameEvents.PlayerDied -= OnPlayerDied;
            ClearQiWave(true);
            look?.Dispose();
        }

        void OnBossStarted(Boss b)
        {
            if (b != this) return;
            fightStart = Time.time;
            teachLeapA = teachLeapB = null;
            foreach (var p in config.patterns)
            {
                if (!Has(p, BambooMasterMoves.Leap)) continue;
                if (teachLeapA == null) { teachLeapA = p; teachLeapWeightA = p.weight; }
                else { teachLeapB = p; teachLeapWeightB = p.weight; }
            }
            // el maestro retoma la lección donde quedó: el reintento arranca en la fase más alta a la que llegó Kaito, con
            // su vida al umbral (ver OnPlayerDied)
            if (retryPhase >= 1)
            {
                SetPhase(retryPhase);
                Health = Mathf.Min(Health, Gates[retryPhase] * config.maxHealth);
                look.SetPhaseLook(retryPhase);
                // misma frame que PlayBossMusic (Boss.BeginFight): el tema arranca directo en su fase
                Game.Audio?.SetBossMusicPhase(retryPhase + 1);
                subtitle = PhaseSubtitle(retryPhase);
                Game.UI?.BossRetitled(this);
            }
        }

        void OnPlayerDied()
        {
            if (!Fighting) return;
            attempts++;
            // con la pelea entera de ~4-5 min el bot "promedio" (falla ~45 % de los golpes) tenía que hacer las fases 2 y 3
            // sin morir y casi nunca ganaba (Tools/Dev/sim_bamboo_master.py): cada fase es una lección ya aprendida
            retryPhase = Mathf.Max(retryPhase, phaseIdx);
        }

        public override void ResetEnemy()
        {
            transition = null;
            base.ResetEnemy();   // config de fábrica (fase 1), vida, lugar
            if (look == null) return;
            phaseIdx = 0;
            suffix = "";
            stance = taunt = false;
            ClearQiWave(true);
            look.ResetAll(retryPhase >= 1);
            if (trail != null) { Destroy(trail.gameObject); trail = null; }
            counterPattern = BambooMasterMoves.Counter(0);
            subtitle = baseSubtitle;
            prevChainTo = "READY";
            CacheNames();
            strafeWanted = locoName;
            riposteUntil = -1f;
            look.ShowStanceRing(false);
            look.StopLimbTrail();
            limbTrailOn = false;
            if (tipHideAt > 0f) { Game.UI?.HideTutorial(); tipHideAt = -1f; }
            WaitPose();
        }

        /// <summary>
        /// Espera la llegada de Kaito: las manos en la espalda y la cabeza gacha (el primer cuadro del Intro), o sin el
        /// saco (y con el bastón) y en guardia si el reintento arranca en la fase 2 o 3.
        /// </summary>
        void WaitPose()
        {
            EnterScripted();
            if (retryPhase >= 1)
            {
                look.SetPhaseLook(retryPhase);
                anim.Play("Locomotion" + BambooMasterMoves.Suffix(retryPhase), 0f);
            }
            else anim.Play(BambooMasterTimings.Intro.State, 0f, 0f, 0f);
        }

        // ================================================================== fases
        /// <summary>Patrones, clips y ritmo de una fase (0..2). Los estados de las reacciones de Enemy salen de config.</summary>
        void SetPhase(int phase)
        {
            phaseIdx = Mathf.Clamp(phase, 0, 2);
            suffix = BambooMasterMoves.Suffix(phaseIdx);
            CacheNames();
            config.patterns = BambooMasterMoves.Phase(phaseIdx);
            counterPattern = BambooMasterMoves.Counter(phaseIdx);
            config.attackCooldown = BambooMasterMoves.Cooldown[phaseIdx];
            config.animLocomotion = "Locomotion" + suffix;
            config.animGuard = "Guard" + suffix;
            config.animCounter = "Counter" + suffix;
            config.animExhausted = "Exhausted" + suffix;
            config.animHit = "Hit" + suffix;
            config.animParried = "Parried" + suffix;
            strafeWanted = config.animLocomotion;
            phaseStart = Time.time;
            teachDashA = teachDashB = null;
            foreach (var p in config.patterns)
            {
                if (!Has(p, BambooMasterMoves.Dash)) continue;
                if (teachDashA == null) teachDashA = p; else teachDashB = p;
                teachDashWeight = p.weight;
            }
            // la estela del bastón: de punta a punta (Enemy la prende en la suelta y la apaga después del golpe)
            if (phaseIdx >= 2 && trail == null && look.StaffTip != null)
                trail = BladeTrail.Create(transform, look.StaffBottom, look.StaffTip, Game.Content != null ? Game.Content.trailMaterial : null, TellStyle.TrailParry);
        }

        static string PhaseSubtitle(int phase) => phase <= 0 ? null : phase == 1 ? "Las Dos Manos" : "El Bastón de Bambú";

        void CacheNames()
        {
            locoName = "Locomotion" + suffix;
            strafeLName = "StrafeL" + suffix;
            strafeRName = "StrafeR" + suffix;
            walkBackName = "WalkBack" + suffix;
            exhaustedHitName = "ExhaustedHit" + suffix;
            hitHeavyName = "HitHeavy" + suffix;
            parriedPerfectName = "ParriedPerfect" + suffix;
            riseName = "ExhaustedRise" + suffix;
            tauntName = "Taunt" + suffix;
            stanceName = "Stance" + suffix;
            guardHitName = "GuardHit" + suffix;
            guardHitLName = "GuardHitL" + suffix;
        }

        static bool Has(AttackPattern p, string special)
        {
            foreach (var s in p.steps) if (s.special == special) return true;
            return false;
        }

        protected override void OnDamaged(in DamageInfo info)
        {
            // sin la fase genérica de Boss: los umbrales son pisos y cada uno abre su escena
            if (transition != null || !IsAlive || phaseIdx >= 2) return;
            if (Health <= Gates[phaseIdx + 1] * config.maxHealth + 0.5f) StartTransition(phaseIdx + 1);
        }

        // ================================================================== por frame
        protected override void Update()
        {
            if (look == null) { base.Update(); return; }
            ResumeKneel();
            ResolveQiHit();
            // antes que Enemy: la guardia que termina sale con el golpe, no con un cuadro rondando (BambooMasterBoss.Guard.cs)
            RestGuard();
            AnswerFromGuard();
            base.Update();
            float dt = Time.deltaTime;
            if (State == EnemyState.Exhausted && !anim.Frozen && anim.Current == config.animExhausted) kneelClock += dt * anim.StateSpeed;
            // el contraataque siempre es el contragolpe: sale de COIL, el final de Counter
            if (State == EnemyState.Counter && pattern != counterPattern) pattern = counterPattern;
            TickStance();
            if (State != EnemyState.Attack && clip != null) { clip = null; look.ClearTell(); }
            if (limbTrailOn && (clip == null || stepNorm > CurrentAttack.activeEnd + 0.05f)) { limbTrailOn = false; look.StopLimbTrail(); }
            TickTellGlow();
            TickQiWave(dt);
            UpdateStrafeAnim(dt);
            if (Fighting) { if (phaseIdx == 0) TeachLeap(); else TeachDash(); }
            if (tipHideAt > 0f && Time.unscaledTime > tipHideAt) { tipHideAt = -1f; Game.UI?.HideTutorial(); }
        }

        /// <summary>
        /// Después del sacudón de rodillas vuelve al Exhausted en el tramo de rodillas (Enemy lo reiniciaba de cero: se
        /// paraba y volvía a caer en cada golpe). Corre antes que Enemy.Update para ganarle a su chequeo.
        /// </summary>
        void ResumeKneel()
        {
            if (State != EnemyState.Exhausted || taunt) return;
            string hit = exhaustedHitName;
            if (anim.Current != hit || !anim.TryNormalizedTime(hit, out float n) || n < 0.97f) return;
            float len = anim.Length(config.animExhausted, 4f);
            float k = Mathf.Clamp(kneelHeld / len, KneelResumeMin, KneelResumeMax);
            kneelClock = k * len;
            anim.Play(config.animExhausted, 0.06f, k);
        }

        // el reloj del Exhausted cuando empezó el sacudón (mientras dura, el clip de rodillas no avanza)
        float kneelHeld;

        /// <summary>Tramo del Exhausted con la rodilla en el piso (Kneel f15 → antes del Rise f100) al que vuelve.</summary>
        const float KneelResumeMin = 0.2f, KneelResumeMax = 0.72f;

        /// <summary>El miembro que pega se enciende en el último tramo del aviso (dorado: parry; rojo: dash).</summary>
        void TickTellGlow()
        {
            var a = CurrentAttack;
            if (a == null || clip == null || a.damage <= 0f) return;
            float eta = StrikeEta;
            if (stepNorm > a.activeEnd || float.IsInfinity(eta) && stepClock > tl.T) { look.ClearTell(); return; }
            if (eta > GlintLead) return;
            look.Tell(clip.Glow, a.kind == AttackKind.Unblockable, Mathf.InverseLerp(GlintLead, a.TellBias, eta));
        }

        /// <summary>
        /// Rodea y retrocede con sus clips: el agente se mueve de costado o hacia atrás y Run no lo dice. Los clips van a
        /// walkSpeed (el controller los acelera) y el agente frena al llegar a su lugar: el clip se toca a la velocidad
        /// real del costado (o del retroceso), si no los pies patinaban hasta 1 m/s.
        /// </summary>
        void UpdateStrafeAnim(float dt)
        {
            string want = locoName;
            float side = 0f;
            if (State == EnemyState.Strafe && agent != null && agent.enabled)
            {
                Vector3 v = transform.InverseTransformDirection(agent.velocity);
                if (Mathf.Abs(v.x) > 0.6f && Mathf.Abs(v.x) > Mathf.Abs(v.z) * 1.2f) { want = v.x > 0f ? strafeRName : strafeLName; side = Mathf.Abs(v.x); }
                else if (v.z < -0.6f && -v.z > Mathf.Abs(v.x) * 1.2f) { want = walkBackName; side = -v.z; }
            }
            // un poco de histéresis: el agente corrige y el costado no titila
            if (want != strafeWanted) { strafeWanted = want; strafeWantedFor = 0f; }
            else strafeWantedFor += dt;
            if (strafeWantedFor > 0.15f || want == locoName) config.animLocomotion = strafeWanted;
            bool sideClip = State == EnemyState.Strafe && (anim.Current == strafeLName || anim.Current == strafeRName || anim.Current == walkBackName);
            if (sideClip)
            {
                // con 'want' de vuelta en la locomoción (histéresis) el clip de costado sigue a la velocidad del agente
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

        /// <summary>La grulla voladora sale sí o sí en los primeros ~20 s (el rojo de la fase 1 se aprende temprano): desde
        /// los 14 s, hasta que sale, las dos (la directa y la del salto atrás) pesan veinte veces más. Con cuatro, en ~1 de
        /// cada 100 peleas del bot "bueno" la fase 1 terminaba sin ninguna (Tools/Dev/sim_bamboo_master.py).</summary>
        void TeachLeap()
        {
            if (teachLeapA == null) return;
            bool used = teachLeapA.lastUsed >= fightStart || teachLeapB != null && teachLeapB.lastUsed >= fightStart;
            float mul = Time.time - fightStart > 14f && !used ? 20f : 1f;
            teachLeapA.weight = teachLeapWeightA * mul;
            if (teachLeapB != null) teachLeapB.weight = teachLeapWeightB * mul;
        }

        /// <summary>
        /// El paso del viento es la especial de la fase: hasta que sale una vez en la fase pesa cuatro veces más. Desde
        /// lejos sale directo y de cerca primero salta hacia atrás (BambooMasterMoves.DashPatterns): antes solo se elegía
        /// con Kaito a 4.2 m o más y el que peleaba pegado no lo veía nunca.
        /// </summary>
        void TeachDash()
        {
            if (teachDashA == null) return;
            bool used = teachDashA.lastUsed >= phaseStart || teachDashB != null && teachDashB.lastUsed >= phaseStart;
            float w = used ? teachDashWeight : teachDashWeight * 4f;
            teachDashA.weight = w;
            if (teachDashB != null) teachDashB.weight = w;
        }

        /// <summary>Los dos patrones de un especial (el directo y el del salto atrás: BambooMasterMoves.Twins) comparten la
        /// pausa entre usos: si no, uno podía salir apenas terminado el otro.</summary>
        void ShareCooldown(AttackPattern used)
        {
            foreach (var p in config.patterns)
                if (p != used && p.name == used.name) p.lastUsed = used.lastUsed;
        }

        // ================================================================== golpes
        protected override void OnStepStarted(AttackDef a)
        {
            base.OnStepStarted(a);
            if (step == 0 && pattern != null && pattern != counterPattern) ShareCooldown(pattern);
            clip = BambooMasterTimings.Get(a.state);
            travelDone = 0f;
            airStretch = 1f;
            landed = leapFixed = laneFixed = dashFx = false;
            look.ClearTell();
            reachPicked = stepYielded = false;
            if (clip != null)
            {
                // un primer cuadro que se aparta más de 2° de la pose con la que encadena salta con el fundido de 0.08 s
                bool counter = step == 0 && pattern == counterPattern;
                string from = counter ? BambooMasterTimings.Counter.ChainTo : prevChainTo;
                bool chains = from == clip.ChainFrom && clip.ChainFromDeg <= 2f;
                // fundido según de qué pose viene: los clips encadenan pose con pose (READY, COIL...); si no coinciden,
                // o viene de un parry, el fundido corto de Enemy cruzaba la mano por el cuerpo
                float fade = afterRecoil ? 0.18f : step == 0 && !counter ? 0.15f : chains ? 0.08f : from == clip.ChainFrom ? 0.15f : 0.2f;
                if (fade > 0.08f) anim.Play(a.state, fade);
                prevChainTo = clip.ChainTo;
                if (a.special == BambooMasterMoves.Hop) airStretch = HopScale();
            }
            afterRecoil = false;
            limbTrailOn = false;
            look.StopLimbTrail();
            if (a.special == BambooMasterMoves.Qi) BeginQiStep(a);
            if (a.special == BambooMasterMoves.Dash) BeginDashStep();
        }

        protected override void TickSpecial(AttackDef a, float dt)
        {
            if (clip == null) { base.TickSpecial(a, dt); return; }
            if (a.special == BambooMasterMoves.Leap) TickLeap(a);
            if (a.special == BambooMasterMoves.Dash) TickDash(a, dt);
            if (!reachPicked && stepClock >= tl.ReleaseTime) PickReach();
            Travel(a);
            TickLimbTrail(a);
            switch (a.special)
            {
                case BambooMasterMoves.Strike: HitArc(a); break;
                case BambooMasterMoves.Sweep: HitSweep(a); break;
                case BambooMasterMoves.Qi: TickQiStep(a); break;
            }
        }

        /// <summary>
        /// El cuerpo avanza lo que avanza el clip (travel_m) en el reloj del paso: los pies apoyados quedan clavados. La
        /// grulla voladora y el paso del viento escalan el tramo entre el despegue y la caída para caer donde está Kaito;
        /// el salto atrás, para no salirse de la arena; los golpes con paso adelante eligen en la suelta la variante cuyo
        /// paso entra (PickReach). Si Kaito se le mete encima del paso (su corte avanza un metro), el cuerpo del maestro lo
        /// corre con el pecho lo que no entra (PlayerController.Shove, como la panza del sumo): frenar el paso dejaba el
        /// pie apoyado patinando hasta 0.94 m. El salto cae sobre él y el paso del viento vuela lo que planeó al despegar: el
        /// de frente, si igual lo tiene enfrente, frena contra él; el que pasa al costado se abre en el aire (PassAside).
        /// </summary>
        void Travel(AttackDef a)
        {
            if (clip.Travel == null || anim.Frozen) return;
            float x = StretchedTravel(stepNorm, airStretch);
            float d = x - travelDone;
            travelDone = x;
            if (Mathf.Abs(d) < 1e-5f) return;
            Vector3 dir = laneFixed ? DashDir : leapFixed ? leapDir : transform.forward;
            // hacia atrás (el salto que toma distancia): el lugar ya lo midió HopScale
            if (d < 0f) { MoveBy(dir * d); return; }
            float move = d;
            // el que se le mete con el dash (con i-frames) se cruza con él: frenar el paso le patinaba el pie apoyado ~1 m
            // (Shove no lo mueve en el dash) y frenar la embestida la dejaba colgada en la pose del vuelo
            bool dashing = target != null && target.State == PlayerState.Dash;
            if (target != null && a.special != BambooMasterMoves.Leap && !PassAirborne && !dashing)
            {
                // solo contra lo que tiene adelante
                Vector3 to = (target.transform.position - transform.position).Flat();
                float along = Vector3.Dot(to, dir), lat = Mathf.Abs(Vector3.Dot(to, Vector3.Cross(Vector3.up, dir)));
                float room = Mathf.Max(0f, along - StopShort);
                if (along > 0f && lat < Radius + target.Radius && d > room)
                {
                    // la de frente no empuja, frena (la red de seguridad si Kaito se le mete en el carril)
                    float pushed = a.special == BambooMasterMoves.Dash ? 0f : target.Shove(dir * (d - room));
                    move = room + pushed;
                }
            }
            if (move > 0f) MoveBy(dir * move);
            // la que pasa al costado se abre en el aire en vez de frenar (BambooMasterBoss.Dash.cs)
            if (PassAirborne && target != null && !dashing) PassAside(Time.deltaTime);
        }

        /// <summary>Dónde frena delante de Kaito (de centro a centro).</summary>
        float StopShort => Radius + (target != null ? target.Radius : 0.35f) + 0.25f;

        /// <summary>Lo que avanzó el cuerpo en 'n' con el tramo del despegue a la caída escalado por 'k' (el clip lleva ese
        /// tramo en el espacio del personaje: escalarlo no mueve un pie apoyado).</summary>
        float StretchedTravel(float n, float k) => Stretched(clip, n, k);

        /// <summary>
        /// El tramo del avance que se puede escalar (normalizado), con los dos pies en el aire: el vuelo del salto y del
        /// salto atrás (timing.air) y, en la embestida, del pie que empuja (DashStart) al que se clava (el contacto, o el
        /// apoyo DashEnd en la que pasa al costado: sigue volando después del cruce). En la embestida timing.air deja afuera
        /// el empuje (1.18 m en un cuadro) y la llegada (0.49 m): escalado solo el medio era un tirón, un vuelo en cámara
        /// lenta y otro tirón.
        /// </summary>
        static void StretchSpan(MasterClip c, out float a0, out float a1)
        {
            float ds = c.Event("DashStart");
            if (ds >= 0f && c.Contact > ds) { a0 = ds; a1 = Mathf.Max(c.Contact, c.Event("DashEnd")); }
            else { a0 = c.AirStart; a1 = c.AirEnd; }
        }

        /// <summary>
        /// El largo del paso de un golpe que avanza (palmas, tajo, contragolpe, sus variantes _Mid y _Close): son el mismo
        /// clip hasta la suelta, así que al soltarse pasa sin fundido a la más larga cuyo paso entra hasta Kaito (con 5 cm
        /// de gracia). Antes el paso entero (~0.95 m) chocaba contra Kaito pegado, se perdía el 60-80 % del avance y el
        /// pie apoyado patinaba lo mismo. Mezclarlas en un blend tree no sirve: la mezcla de giros hundía el pie de atrás.
        /// Si la que entra no llega a Kaito en el contacto (entre ~1.9 y 2 m la del medio frenaba corta y pegaba al aire),
        /// va la de paso más largo si se pasa a lo sumo ReachOverrun. Cuenta dónde va a estar Kaito en el contacto (lo que
        /// se viene acercando): sin eso elegía el paso entero contra el que entraba con su corte y lo frenaba encima.
        /// </summary>
        void PickReach()
        {
            reachPicked = true;
            var vs = clip.Variants;
            if (vs == null || vs.Length == 0 || target == null) return;
            Vector3 dir = transform.forward.Flat().normalized;
            Vector3 to = (target.transform.position - transform.position).Flat();
            float along = Vector3.Dot(to, dir), lat = Mathf.Abs(Vector3.Dot(to, Vector3.Cross(Vector3.up, dir)));
            // Kaito al costado o detrás: no hay contra qué frenar, va el paso entero
            if (along <= 0f || lat >= Radius + target.Radius) return;
            // donde va a estar en el contacto: lo que se viene acercando (su corte avanza ~1 m) hasta tocarlo, como poco
            float closing = Mathf.Clamp(-Vector3.Dot(target.Velocity.Flat(), dir), 0f, target.config.runSpeed);
            along -= Mathf.Min(closing * Mathf.Max(0f, tl.T - stepClock), Mathf.Max(0f, along - Radius - target.Radius));
            float room = along - StopShort + travelDone + 0.05f;
            if (clip.TravelAt(1f) <= room) return;
            MasterClip longer = clip, pick = null;
            for (int i = 0; i < vs.Length; i++)
            {
                var v = BambooMasterTimings.Get(vs[i]);
                if (v == null) continue;
                pick = v;
                if (v.TravelAt(1f) <= room) break;
                longer = v;
            }
            if (pick == null) return;
            if (pick != longer && !ReachesAtContact(pick, along) && longer.TravelAt(1f) - room <= ReachOverrun) pick = longer;
            if (pick == clip || !anim.HasState(pick.State)) return;
            clip = pick;
            anim.Play(pick.State, 0f, stepNorm);
        }

        /// <summary>Lo más que una variante de paso puede pasarse de Kaito (lo corre con el cuerpo: Travel). Con 0.15 el pie
        /// apoyado patinaba eso cada vez que el paso entero no entraba.</summary>
        const float ReachOverrun = 0.03f;

        /// <summary>¿Con lo que le falta avanzar hasta el contacto, la mano de esta variante llega a Kaito? (HitArc, con 2 cm de
        /// margen)</summary>
        bool ReachesAtContact(MasterClip c, float along) =>
            along - Mathf.Max(0f, c.TravelToContact - travelDone) - target.Radius <= c.Reach + 0.08f;

        /// <summary>Golpe dorado: el alcance del miembro (o del bastón) desde donde está en el impacto, más el grosor (con
        /// +0.3 un dorado que se paraba pegaba 30-40 cm antes de que llegara la palma).</summary>
        void HitArc(AttackDef a)
        {
            if (stepHit || target == null || stepNorm < a.activeStart || stepNorm > a.activeEnd) return;
            Vector3 tp = target.transform.position;
            if (Mathf.Abs(tp.y - transform.position.y) > 2.5f) return;
            if (!CombatMath.InArc(transform, tp, clip.Reach + 0.1f, a.arc, target.Radius)) return;
            stepHit = true;
            HitPlayer(a, transform.position);
        }

        /// <summary>La estela dorada o roja de la mano o el pie que pega, de la suelta al final del golpe: el brillo solo de
        /// la venda eran 5 px desde la cámara del juego.</summary>
        void TickLimbTrail(AttackDef a)
        {
            if (limbTrailOn || a.damage <= 0f || stepClock < tl.ReleaseTime || stepNorm > a.activeEnd) return;
            limbTrailOn = look.BeginLimbTrail(clip.Glow, a.kind == AttackKind.Unblockable);
        }

        // ------------------------------------------------------------------ salto atrás
        /// <summary>
        /// Cuánto del salto atrás autorado hace (todo el avance va en el aire: escalarlo no patina): hasta quedar a
        /// DashFrom de Kaito (LeapFrom si lo que sigue es la grulla voladora), sin salirse de la arena; como poco un cuarto
        /// (un saltito que igual arma el especial).
        /// </summary>
        float HopScale()
        {
            float full = -clip.TravelAt(1f);
            if (full < 0.1f) return 1f;
            bool leapNext = pattern != null && step + 1 < pattern.steps.Length && pattern.steps[step + 1].special == BambooMasterMoves.Leap;
            float want = (leapNext ? BambooMasterMoves.LeapFrom : BambooMasterMoves.DashFrom) - DistToTarget;
            float room = ArenaRoom(transform.position, -transform.forward.Flat().normalized) - 1f;
            return Mathf.Clamp(Mathf.Min(want, room) / full, 0.25f, 1f);
        }

        // ------------------------------------------------------------------ barrida
        /// <summary>La pierna (o el bastón) da la vuelta a ras del piso: pega en el cierre del anillo a todo el disco.</summary>
        void HitSweep(AttackDef a)
        {
            if (landed || stepNorm < a.activeStart) return;
            landed = true;
            Game.FX?.Dust(transform.position, 1.4f);
            Game.FX?.Shockwave(transform.position, a.specialParam, new Color(0.85f, 0.8f, 0.6f));
            Game.Audio?.Play("ability_wind", transform.position, 0.7f, 0.1f);
            if (stepHit || target == null) return;
            Vector3 tp = target.transform.position;
            if (Mathf.Abs(tp.y - transform.position.y) > 1.5f) return;
            if (CombatMath.FlatDistance(tp, transform.position) - target.Radius > a.specialParam) return;
            stepHit = true;
            HitPlayer(a, transform.position);
        }

        // ------------------------------------------------------------------ grulla voladora
        /// <summary>
        /// Apunta la caída a Kaito hasta despegar (la marca roja lo sigue) y en la suelta la deja fija: el tramo en el aire
        /// se estira o se acorta para que el pie caiga ahí (entre LeapMin y LeapMax del despegue).
        /// </summary>
        void TickLeap(AttackDef a)
        {
            if (!leapFixed && stepClock >= tl.ReleaseTime)
            {
                leapFixed = true;
                leapStart = transform.position;
                leapDir = transform.forward.Flat().normalized;
                leapTarget = LeapReach(leapStart, leapDir);
                float air = clip.TravelAt(clip.AirEnd) - clip.TravelAt(clip.AirStart);
                airStretch = air > 0.1f ? 1f + (leapTarget - clip.MarkerM) / air : 1f;
                Game.Audio?.Play("dash", transform.position, 0.8f, 0.05f);
            }
            if (landed || stepNorm < a.activeStart) return;
            landed = true;
            Vector3 c = LeapLanding;
            Game.FX?.Shockwave(c, a.specialParam, new Color(1f, 0.55f, 0.4f));
            Game.FX?.GroundCrack(c, a.specialParam * 0.8f);
            Game.FX?.Dust(c, 1.4f);
            Game.Camera?.Shake(0.55f);
            Game.Audio?.Play("slam", c, 0.9f);
            Game.Input?.Rumble(0.7f, 0.5f, 0.25f);
            if (stepHit || target == null) return;
            Vector3 tp = target.transform.position;
            if (Mathf.Abs(tp.y - c.y) > 2f || CombatMath.FlatDistance(tp, c) - target.Radius > a.specialParam) return;
            stepHit = true;
            HitPlayer(a, c);
        }

        /// <summary>Dónde cae el pie: hasta Kaito por la línea en la que mira, sin pasarse de la arena.</summary>
        float LeapReach(Vector3 from, Vector3 dir)
        {
            float d = target != null ? Vector3.Dot((target.transform.position - from).Flat(), dir) : clip.MarkerM;
            float max = Mathf.Min(BambooMasterMoves.LeapMax, Mathf.Max(BambooMasterMoves.LeapMin, ArenaRoom(from, dir) - 1f));
            return Mathf.Clamp(d, BambooMasterMoves.LeapMin, max);
        }

        Vector3 LeapLanding
        {
            get
            {
                if (leapFixed && stepClock >= tl.ReleaseTime) return leapStart + leapDir * leapTarget;
                Vector3 dir = transform.forward.Flat().normalized;
                return transform.position + dir * LeapReach(transform.position, dir);
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

        // ------------------------------------------------------------------ aviso
        protected override float ComputeStrikeEta(AttackDef a)
        {
            switch (a.special)
            {
                case BambooMasterMoves.Qi: return QiEta(a);
                case BambooMasterMoves.Dash:
                {
                    float eta = DashEta(a);
                    // salió del carril a tiempo: el aviso se deshace (cortado, no "pegó") y la carrera sigue de largo sin
                    // poder pegar aunque vuelva a meterse (sin aviso no hay golpe)
                    if (float.IsInfinity(eta) && LaneLive && !stepHit && stepClock < tl.T) { stepHit = true; EndTell(TellOutcome.Cancelled); }
                    return eta;
                }
                default: return base.ComputeStrikeEta(a);
            }
        }

        protected override float TellTravel(AttackDef a) => a.special == BambooMasterMoves.Qi ? QiTravel(a) : base.TellTravel(a);

        protected override bool HitAreaFor(AttackDef a, out TellArea area)
        {
            switch (a.special)
            {
                case BambooMasterMoves.Leap:
                    area = new TellArea { origin = LeapLanding, size = a.specialParam };
                    return true;
                case BambooMasterMoves.Sweep:
                    area = new TellArea { origin = transform.position, size = a.specialParam };
                    return true;
                case BambooMasterMoves.Qi:
                    area = new TellArea { origin = qiLive && qiOwnedByStep ? qiCenter : transform.position, size = a.specialParam };
                    return true;
                case BambooMasterMoves.Dash:
                    area = DashArea();
                    return true;
            }
            return base.HitAreaFor(a, out area);
        }

        // ================================================================== recibir golpes
        /// <summary>
        /// Un maestro no se deja pegar fuera de sus huecos: lo que le entra a la guardia, en neutral, en el contragolpe o en
        /// sus golpes (los dorados enteros, los rojos hasta que pegan) lo desvía o rebota (Bounce) y no le suma postura (la
        /// barra se llena solo con parries: los golpes de relleno no la gastaban de a 0.25 y el que machacaba lo ponía de
        /// rodillas sin desviar nada). El segundo seguido se contragolpea, y la postura del bambú contragolpea al primero.
        /// Los huecos: el contraataque del parry (Recoil), de rodillas, llamando a Kaito (esperó la postura) y la vuelta de
        /// un rojo que no pegó. Con la regla común (aguante 2 en neutral, cambio de golpes en el amague) el bot "bueno" lo
        /// terminaba en ~1 min (Tools/Dev/sim_bamboo_master.py).
        /// </summary>
        public override HitResult ReceiveHit(in DamageInfo info)
        {
            bool fromKaito = info.sourceFaction == Faction.Player;
            var i = info;
            if (fromKaito && IsAlive && look != null)
            {
                // en escena (cambio de fase): rebota con clang, no hay a quién castigar
                if (transition != null) { LastHitTime = Time.time; return HitResult.Blocked; }
                // las habilidades (Corte del Viento, Torbellino) siguen las reglas de un tajo fuerte: antes no eran
                // "rebotables", le cortaban los dorados, le pegaban en neutral y atravesaban la postura (~45 % de su vida
                // sin esperar nada). Fuera de sus huecos el bambú se dobla pero le cuesta: suman postura
                if (i.kind == AttackKind.Ability)
                {
                    i.kind = AttackKind.Heavy;
                    if (Bounces()) { LastHitTime = Time.time; return AbilityAgainstGuard(info); }
                }
                bool guardable = i.kind == AttackKind.Light || i.kind == AttackKind.Heavy;
                if (stance && State == EnemyState.Guard && guardable) { LastHitTime = Time.time; return Deflect(true); }
                if (guardable && Bounces()) { LastHitTime = Time.time; return Bounce(info.attackName); }
            }
            // piso de vida de la fase: el que lo baja al umbral dispara el cambio; lo que sobra no se cuenta
            if (fromKaito && i.damage > 0f && IsAlive && look != null)
            {
                float floor = Gates[Mathf.Clamp(phaseIdx + 1, 1, 3)] * config.maxHealth;
                float mul = State == EnemyState.Exhausted ? config.exhaustedDamageMul : 1f;
                if (phaseIdx < 2) i.damage = Mathf.Min(i.damage, Mathf.Max(0f, Health - floor) / mul);
            }
            bool inRecoil = State == EnemyState.Recoil;
            bool inRiposte = RiposteOpen;
            kneelAtHit = State == EnemyState.Exhausted && !taunt;
            var r = base.ReceiveHit(i);
            kneelAtHit = false;
            if (look == null || !fromKaito) return r;
            // Enemy toca las reacciones de la fase 1 por nombre (HitHeavy, ExhaustedHit): con el saco tirado o el bastón
            // en la mano, la pose de la fase 1 no existe
            if (phaseIdx > 0)
            {
                if (anim.Current == "HitHeavy") anim.Play(hitHeavyName, 0.03f);
                else if (anim.Current == "ExhaustedHit") anim.Play(exhaustedHitName, 0.03f);
            }
            if (anim.Current == exhaustedHitName && State == EnemyState.Exhausted) kneelHeld = kneelClock;
            if (r == HitResult.Hit)
            {
                // el contraataque de Kaito: dos cortes después de un parry, tres después de uno perfecto (el combo entero).
                // Antes el primero lo pasaba a Stagger y el segundo rebotaba: la parada perfecta pagaba lo mismo
                if (inRecoil) { riposteUntil = Time.time + (lastParryPerfect ? RipostePerfectSpan : RiposteSpan); riposteLeft = lastParryPerfect ? 2 : 1; }
                else if (inRiposte) riposteLeft--;
            }
            // le entró el contraataque: se rehace antes de volver a atacar (Enemy lo largaba al combo siguiente apenas
            // se reponía, y el parry se volvía una cinta: parry, contra, golpe, parry...)
            if (r == HitResult.Hit && State == EnemyState.Stagger)
            {
                nextAttackTime = Mathf.Max(nextAttackTime, Time.time + stateDuration + Random.Range(config.attackCooldown.x, config.attackCooldown.y));
                // el descanso queda anotado: el desvío que contesta (Bounce) no lo acorta y lo pasa cubierto (RestGuard)
                restUntil = nextAttackTime;
            }
            return r;
        }

        bool RiposteOpen => riposteLeft > 0 && Time.time < riposteUntil &&
                            (State == EnemyState.Stagger || State == EnemyState.Chase || State == EnemyState.Strafe || State == EnemyState.Idle);

        /// <summary>Hasta cuándo le entran los cortes del contraataque después del primero (el 2.º corte de Kaito llega 0.3 s
        /// después del 1.º y el 3.º 0.45 s después del 2.º).</summary>
        const float RiposteSpan = 0.55f, RipostePerfectSpan = 0.95f;
        /// <summary>Postura que suma una habilidad que le entra a la guardia (el Torbellino pega dos veces).</summary>
        const float AbilityPosture = 2f, WhirlPosture = 1f;
        /// <summary>El final de la vuelta del último golpe de un combo es un hueco (s después de la ventana activa).</summary>
        const float RecoveryHoleDelay = 0.1f;

        /// <summary>
        /// Una habilidad contra su guardia: no le hace daño pero le dobla la postura (la bandana empuja más que la hoja);
        /// en la postura del bambú la desvía igual y contragolpea, como a cualquier golpe apurado.
        /// </summary>
        HitResult AbilityAgainstGuard(in DamageInfo info)
        {
            float posture = info.attackName == "Torbellino" ? WhirlPosture : AbilityPosture;
            if (stance && State == EnemyState.Guard)
            {
                var r = Deflect(false);
                AddImbalance(posture);
                return r;
            }
            Game.UI?.ShowGuardMark(this);
            Game.FX?.Shockwave(transform.position, 1.6f, BambooMasterLook.Jade);
            AddImbalance(posture);
            return HitResult.Blocked;
        }

        /// <summary>
        /// ¿Este golpe de Kaito (corte o tajo final) rebota? Ver ReceiveHit. Los huecos: el retroceso del parry y los
        /// cortes del contraataque que siguen, de rodillas, llamando a Kaito, la vuelta de un rojo que no pegó y el final
        /// de la vuelta del último golpe de un combo (el que espera que termine, pega).
        /// </summary>
        bool Bounces()
        {
            switch (State)
            {
                case EnemyState.Attack:
                    var a = CurrentAttack;
                    if (a == null) return true;
                    if (a.kind == AttackKind.Unblockable && float.IsInfinity(StrikeEta)) return false;
                    return !(pattern != null && step == pattern.steps.Length - 1 && a.damage > 0f && stepNorm > a.activeEnd + RecoveryHoleDelay / Mathf.Max(0.1f, tl.stepLen));
                case EnemyState.Stagger:
                case EnemyState.Chase:
                case EnemyState.Strafe:
                case EnemyState.Idle:
                    // los cortes que quedan del contraataque (el Stagger del 2.º termina antes de que llegue el 3.º)
                    return !RiposteOpen;
                case EnemyState.Counter:
                case EnemyState.Guard:
                case EnemyState.Alert:
                    return true;
                default:
                    return false;   // Recoil, Exhausted: los huecos
            }
        }

        /// <summary>
        /// El empuje de un golpe que entró, el que autoró su reacción: de rodillas no se desliza (ExhaustedHit es un
        /// sacudón en el lugar), llamando a Kaito retrocede lo que retrocede Hit, y en pleno golpe (la vuelta de un rojo,
        /// el contragolpe) sigue su movimiento con los pies clavados. Antes el tajo final lo corría 0.5 m por el piso
        /// arrodillado.
        /// </summary>
        protected override float KnockMeters(in DamageInfo info, float kb)
        {
            if (look == null) return kb;
            switch (State)
            {
                case EnemyState.Exhausted:
                    return taunt ? HitKnock(config.animHit, kb) : 0f;
                case EnemyState.Attack:
                case EnemyState.Counter:
                    return 0f;
                default:
                    // Stagger: la reacción que va a tocar Enemy (HitHeavy desde 1 m de empuje antes de la resistencia)
                    return HitKnock(info.knockback > 1f ? hitHeavyName : config.animHit, kb);
            }
        }

        static float HitKnock(string state, float fallback)
        {
            var c = BambooMasterTimings.Get(state);
            return c != null && c.KnockM > 0f ? c.KnockM : fallback;
        }

        // el último rebote y cuántos seguidos (el segundo dentro de BounceWindow se contragolpea)
        float lastBounce = -99f;
        int bounces;

        /// <summary>
        /// Un corte fuera de sus huecos. Parado (en neutral o en la guardia) no rebota: lo aparta con el manotazo de
        /// GuardHit (Swat), queda cubierto y le contesta con su combo saliendo de la guardia (AnswerFromGuard): al primero,
        /// pasada la ventana del segundo; al segundo dentro de BounceWindow (el combo que insiste), enseguida. Recién el
        /// tercero se le devuelve con el contragolpe. Cargando un dorado, la mano libre aparta el primer corte y el golpe
        /// sigue; en lo demás de sus golpes (la suelta, los rojos, el contragolpe) rebota: clang del lado de Kaito
        /// (PlayerController con Blocked). Con el clang en todo, contra el bot "bueno" eran ~220 rebotes por pelea: una pared.
        /// </summary>
        HitResult Bounce(string attackName)
        {
            bool left = CutGoesLeft(attackName);
            bool busy = State == EnemyState.Attack || State == EnemyState.Counter;
            if (!busy)
            {
                if (Time.time - lastBounce > BounceWindow) bounces = 0;
                if (++bounces >= 3) { bounces = 0; lastBounce = -99f; return Deflect(false); }
                bool guarding = State == EnemyState.Guard;
                if (!guarding) { ReleaseToken(); EnterGuard(); }
                if (bounces == 2)
                {
                    // el segundo seguido: lo aparta y toma la palabra, aunque estuviera descansando de un contraataque de
                    // Kaito (el que insiste no descansa). Antes se lo devolvía con el contragolpe y contra el que no para de
                    // cortar la pelea era una cinta de contragolpes: el 78-95 % de lo que elegía (sim --masher) y su
                    // repertorio no se veía. Sale cuando la palma ya apartó la hoja (GuardHit f3)
                    restUntil = Mathf.Min(restUntil, Time.time);
                    nextAttackTime = Time.time + SwatAnswer;
                    stateDuration = stateTime + SwatAnswer;
                }
                else
                {
                    // el maestro toma la palabra: pasada la ventana del segundo corte sale con su combo (antes rondaba la
                    // pausa entera y cada toque suelto era otro clang), salvo que esté descansando de un contraataque de
                    // Kaito (el desvío que contestaba acortaba ese descanso y el parry volvía a ser una cinta)
                    nextAttackTime = Mathf.Min(nextAttackTime, Mathf.Max(Time.time + AnswerDelay, restUntil));
                    // cubierto hasta que contesta: rondando entre el desvío y el golpe, el corte siguiente le caía en el aviso
                    stateDuration = Mathf.Max(stateDuration, stateTime + Mathf.Max(GuardHitHold, nextAttackTime - Time.time));
                }
                if (target != null) transform.rotation = Quaternion.LookRotation((target.transform.position - transform.position).Flat().normalized + transform.forward * 0.001f);
                // GuardHit arranca en la guardia: desde la pose de la locomoción el fundido de 0.03 s cruzaba el brazo en un cuadro.
                // La palma va con la hoja: hacia su izquierda y arriba para el revés, hacia su derecha y abajo para los otros
                anim.Play(left && anim.HasState(guardHitLName) ? guardHitLName : guardHitName, guarding ? 0.03f : 0.08f);
                Game.UI?.ShowGuardMark(this);
                lastBounce = Time.time;
                TellPatience();
                return Swat(left);
            }
            lastBounce = Time.time;
            TellPatience();
            var a = CurrentAttack;
            if (State == EnemyState.Attack && !stepYielded && a != null && a.damage > 0f && a.kind != AttackKind.Unblockable && stepClock < tl.ReleaseTime)
            {
                stepYielded = true;
                return Swat(left);
            }
            return HitResult.Blocked;
        }

        /// <summary>
        /// Para dónde va la hoja de Kaito cuando le llega (kaitooo.fbx, en el contacto y los cuadros que siguen): el revés
        /// ascendente (Corte 2) le entra por su derecha a la altura de la cadera y sube hacia su izquierda; el primer corte y
        /// el final cruzan bajando de su izquierda a su derecha, a la altura del muslo. Antes el manotazo de la palma alzada
        /// iba siempre hacia su derecha a la altura de la cabeza, lejos de la hoja: se leía como un tic más el trazo de jade.
        /// </summary>
        static bool CutGoesLeft(string attackName) => attackName == KaitoBackhand;

        const string KaitoBackhand = "Corte 2";

        /// <summary>Cuánto espera para contestar un desvío (pasada la ventana del segundo corte), lo menos que queda
        /// cubierto después del manotazo (el segundo corte del combo tiene que poder llegar a su guardia) y lo que tarda en
        /// contestar el segundo (la palma termina de apartar la hoja).</summary>
        const float AnswerDelay = 0.6f, GuardHitHold = 0.5f, SwatAnswer = 0.12f;
        static readonly Color SwatJade = new Color(0.62f, 1f, 0.86f, 0.85f);

        /// <summary>
        /// El desvío: la palma (o la mano libre) acompaña la hoja hacia afuera, sin clang ni castigo (HitResult.Deflected:
        /// PlayerController frena el corte en el roce, con un hit-stop corto, y Kaito queda donde está). Antes lo empujaba
        /// hasta 2.4 m con el corte todavía en curso: los pies de Kaito patinaban 40-70 cm y su corte siguiente volvía a
        /// meterse encima del paso del maestro. Lo que se ve es el barrido de jade donde se cruzan y el GuardHit; el aviso
        /// de que el segundo se paga es la marca de guardia.
        /// </summary>
        HitResult Swat(bool left)
        {
            var p = target;
            if (p == null) return HitResult.Deflected;
            Vector3 d = (p.transform.position - transform.position).Flat();
            Vector3 dir = d.sqrMagnitude > 1e-4f ? d.normalized : transform.forward;
            // donde la palma encuentra la hoja (GuardHit f2) y hacia dónde la lleva: el trazo sigue a la mano. El sonido es
            // la palma contra el plano de la hoja y lo pone Kaito (PlayerController con Deflected)
            Vector3 right = Vector3.Cross(Vector3.up, dir);
            Vector3 c = transform.position + dir * SwatReach + Vector3.up * (left ? SwatHighL : SwatHigh);
            if (left) SlashLineFX.Spawn(c + right * 0.35f - Vector3.up * 0.12f, c - right * 0.55f + Vector3.up * 0.3f, SwatJade, 0.24f, 0.24f);
            else SlashLineFX.Spawn(c - right * 0.35f + Vector3.up * 0.12f, c + right * 0.55f - Vector3.up * 0.22f, SwatJade, 0.24f, 0.24f);
            Game.FX?.DodgeSpark(c);
            return HitResult.Deflected;
        }

        /// <summary>Dónde la palma encuentra la hoja, delante de él (m) y a qué altura (el revés le llega más arriba).</summary>
        const float SwatReach = 0.65f, SwatHigh = 0.85f, SwatHighL = 1.05f;

        void TellPatience()
        {
            if (deflectToldOnce) return;
            deflectToldOnce = true;
            Bark(StoryText.ChikuoLine("paciencia"));
            ShowTip(StoryText.Hint("bamboo_guard"));
        }

        protected override int ExhaustedHitCap => taunt ? TauntHitCap : KneelHitCap;

        public override void OnParried(bool perfect)
        {
            bool wasAttack = State == EnemyState.Attack;
            bool counter = wasAttack && pattern == counterPattern && stanceCounter;
            base.OnParried(perfect);
            if (look == null || !IsAlive) return;
            if (wasAttack && State == EnemyState.Recoil)
            {
                afterRecoil = true;
                lastParryPerfect = perfect;
                if (phaseIdx > 0 && anim.Current == "ParriedPerfect") anim.Play(parriedPerfectName, 0.03f);
            }
            look.ClearTell();
            // la parada perfecta del contragolpe de la postura es la respuesta del maestro: le quiebra la postura entera.
            // El del rebote en neutral no: si no, provocarlo era el camino más corto a ponerlo de rodillas
            if (counter && perfect && State != EnemyState.Exhausted) AddImbalance(config.maxImbalance);
        }

        // ------------------------------------------------------------------ postura del bambú
        protected override void ComboEnd()
        {
            ReleaseToken();
            bool forced = pattern != null && pattern.exhaustAfter;
            if (forced) Imbalance = config.maxImbalance;
            pattern = null;
            nextAttackTime = Time.time + Random.Range(config.attackCooldown.x, config.attackCooldown.y);
            // de rodillas solo con la postura llena (BreakPosture, en el parry mismo): la regla común ("un parry en el combo
            // = agotado") lo arrodillaba en cada combo y la barra de 5 no decía nada
            if (forced) { BecomeExhausted(); return; }
            // la primera vez la enseña sí o sí; después, a veces (nunca dos seguidas)
            bool want = forceStanceOnce || !stanceLast && Random.value < StanceChance[phaseIdx];
            forceStanceOnce = false;
            stanceLast = want;
            if (want) EnterStance(); else EnterGuard();
        }

        bool stanceLast;
        // el contragolpe en curso salió de la postura del bambú (su parada perfecta lo pone de rodillas)
        bool stanceCounter;

        /// <summary>
        /// La postura del bambú: su propio clip (agachado en el gato, las dos palmas cruzadas delante del pecho, el saco
        /// abierto: otra silueta que la guardia común) y un aro de jade en el piso que no depende de ver las palmas.
        /// Antes era la guardia de siempre con las vendas en jade (~5 px desde la cámara del juego).
        /// </summary>
        void EnterStance()
        {
            EnterGuard();
            stance = true;
            float hold = Random.Range(StanceTime.x, StanceTime.y);
            stanceUntil = Time.time + hold;
            stateDuration = hold + 5f;   // la postura termina por su cuenta (TickStance), no por el tiempo de la guardia
            if (anim.HasState(stanceName)) anim.Play(stanceName, 0.15f);
            look.SetStance(true);
            look.ShowStanceRing(true, transform);
            Game.Audio?.Play("parry_ready", transform.position, 0.5f, 0.05f);
            if (!stanceTaught) { stanceTaught = true; ShowTip(StoryText.Hint("bamboo_stance")); }
        }

        /// <summary>Kaito esperó: baja la guardia y lo llama (abierto unos segundos, sin estar mareado).</summary>
        void TickStance()
        {
            if (!stance) { if (look.StanceRingShown) look.ShowStanceRing(false); return; }
            if (State != EnemyState.Guard) { stance = false; look.SetStance(false); look.ShowStanceRing(false); return; }
            look.TickStanceRing(stanceUntil - Time.time);
            if (Time.time < stanceUntil) return;
            stance = false;
            look.SetStance(false);
            look.ShowStanceRing(false);
            taunt = true;
            savedImbalance = Imbalance;
            BecomeExhausted();
            // en la fase 1 lo dice cada vez (es la lección); después, la primera
            if (phaseIdx == 0 || !waitToldOnce) { waitToldOnce = true; Bark(StoryText.ChikuoLine("espera")); }
        }

        /// <summary>Le pegaron en la postura (o insistieron contra su guardia): desvía con un círculo de la mano y
        /// contragolpea (lo que pasa por apurarse).</summary>
        HitResult Deflect(bool fromStance)
        {
            stanceCounter = fromStance;
            stance = false;
            look.SetStance(false);
            look.ShowStanceRing(false);
            Stop();
            ReleaseToken();
            pattern = counterPattern;
            SetState(EnemyState.Counter);
            stateDuration = Mathf.Clamp(anim.Length(config.animCounter, 0.5f), 0.2f, 0.6f);
            // Counter arranca en la guardia: desde las palmas cruzadas de la postura se funde un poco más
            anim.Play(config.animCounter, fromStance ? 0.1f : 0.02f);
            if (target != null) transform.rotation = Quaternion.LookRotation((target.transform.position - transform.position).Flat().normalized + transform.forward * 0.001f);
            Game.UI?.ShowGuardMark(this);
            Game.FX?.Shockwave(transform.position, 2f, BambooMasterLook.Jade);
            nextAttackTime = Time.time;
            if (!deflectToldOnce) { deflectToldOnce = true; Bark(StoryText.ChikuoLine("paciencia")); }
            return HitResult.Guarded;
        }

        // ------------------------------------------------------------------ abierto
        protected override bool ExhaustedFeedback => !taunt;

        protected override void BecomeExhausted()
        {
            if (stance) { stance = false; look?.SetStance(false); }
            base.BecomeExhausted();
            kneelStart = Time.time;
            kneelClock = 0f;
            look?.ClearTell();
            if (!taunt) return;
            // llamando a Kaito: abierto lo que dura el gesto, parado y con la guardia baja
            var t = BambooMasterTimings.Get(tauntName) ?? BambooMasterTimings.Taunt;
            stateDuration = t.Seconds;
            anim.Play(t.State, 0.2f);
        }

        protected override void OnExhaustionEnded()
        {
            if (taunt) { taunt = false; Imbalance = savedImbalance; return; }
            // si se levanta antes de terminar el clip (los golpes de la ventana) usa el clip de pararse, no el fundido
            if (Time.time - kneelStart < config.exhaustedTime - 0.3f) anim.Play(riseName, 0.08f);
        }

        // ================================================================== ayudas
        void Bark(string line)
        {
            if (string.IsNullOrEmpty(line)) return;
            Game.UI?.ShowBark(StoryText.Chikuo, line, BarkColor, 3.2f);
        }

        void ShowTip(string text)
        {
            if (string.IsNullOrEmpty(text)) return;
            Game.UI?.ShowTutorial(text);
            tipHideAt = Time.unscaledTime + TipSeconds;
        }

        void PushKaito(float radius, float meters)
        {
            var p = Game.Player;
            if (p != null && CombatMath.FlatDistance(p.transform.position, transform.position) < radius)
                p.Push(p.transform.position - transform.position, meters);
        }

#if UNITY_EDITOR || DEVELOPMENT_BUILD
        /// <summary>Pruebas (AutoPilot "chikuo fase N"): salta a la fase 2 o 3 en plena pelea, con su escena.</summary>
        public void DebugJump(int phase)
        {
            if (!Fighting || !IsAlive || transition != null) return;
            // solo hacia adelante: pedir la fase en la que ya está (o una anterior) volvía a tocar la escena con 1 de vida
            if (phaseIdx >= 2 || phase <= phaseIdx + 1) return;
            phase = Mathf.Min(phase, 3);
            if (phase == 3 && phaseIdx == 0)
            {
                // se saltea la escena del saco: queda sin él y en la fase 2, y abre la del bastón
                look.SetPhaseLook(1);
                SetPhase(1);
            }
            Health = Gates[phase - 1] * config.maxHealth + 1f;
            StartTransition(phase - 1);
        }
#endif
    }
}
