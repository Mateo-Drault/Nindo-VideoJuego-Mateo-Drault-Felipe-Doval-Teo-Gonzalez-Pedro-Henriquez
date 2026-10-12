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
        /// Dos golpes a su guardia (o en neutral) con menos de esto entre uno y otro: el segundo se contragolpea. Atrapa el
        /// combo (el 2.º corte llega 0.3 s después del 1.º, el 3.º 0.45 s después del 2.º), no al que tantea de a un corte
        /// y espera: con 1.5 s cada toque suelto terminaba en contragolpe y la pelea era una cinta de contragolpes (36 de
        /// los 50 golpes de Chikuō contra el bot "bueno"), en vez de sus combos y sus huecos.
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
        AttackPattern counterPattern, teachLeap, teachDash;
        float teachDashWeight, phaseStart;
        string baseSubtitle;

        // paso en curso
        MasterClip clip;
        float travelDone, airStretch = 1f;
        bool landed, afterRecoil, dashFx;
        string prevChainTo = "READY";
        Vector3 leapStart, leapDir;
        float leapTarget;
        bool leapFixed;
        // embestida: carril fijo desde la suelta
        bool laneFixed;
        Vector3 laneO, laneD;

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
        }

        void OnBossStarted(Boss b)
        {
            if (b != this) return;
            fightStart = Time.time;
            teachLeap = null;
            foreach (var p in config.patterns) if (p.steps[0].special == BambooMasterMoves.Leap) teachLeap = p;
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
            strafeWanted = "Locomotion";
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
            teachDash = null;
            foreach (var p in config.patterns) if (p.steps[0].special == BambooMasterMoves.Dash) { teachDash = p; teachDashWeight = p.weight; }
            // la estela del bastón: de punta a punta (Enemy la prende en la suelta y la apaga después del golpe)
            if (phaseIdx >= 2 && trail == null && look.StaffTip != null)
                trail = BladeTrail.Create(transform, look.StaffBottom, look.StaffTip, Game.Content != null ? Game.Content.trailMaterial : null, TellStyle.TrailParry);
        }

        static string PhaseSubtitle(int phase) => phase <= 0 ? null : phase == 1 ? "Las Dos Manos" : "El Bastón de Bambú";

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
            base.Update();
            float dt = Time.deltaTime;
            if (State == EnemyState.Exhausted && !anim.Frozen && anim.Current == config.animExhausted) kneelClock += dt * anim.StateSpeed;
            // el contraataque siempre es el contragolpe: sale de COIL, el final de Counter
            if (State == EnemyState.Counter && pattern != counterPattern) pattern = counterPattern;
            TickStance();
            if (State != EnemyState.Attack && clip != null) { clip = null; look.ClearTell(); }
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
            string hit = "ExhaustedHit" + suffix;
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

        /// <summary>Rodea y retrocede con sus clips: el agente se mueve de costado o hacia atrás y Run no lo dice.</summary>
        void UpdateStrafeAnim(float dt)
        {
            string loco = "Locomotion" + suffix, want = loco;
            if (State == EnemyState.Strafe && agent != null && agent.enabled)
            {
                Vector3 v = transform.InverseTransformDirection(agent.velocity);
                if (Mathf.Abs(v.x) > 0.6f && Mathf.Abs(v.x) > Mathf.Abs(v.z) * 1.2f) want = (v.x > 0f ? "StrafeR" : "StrafeL") + suffix;
                else if (v.z < -0.6f && -v.z > Mathf.Abs(v.x) * 1.2f) want = "WalkBack" + suffix;
            }
            // un poco de histéresis: el agente corrige y el costado no titila
            if (want != strafeWanted) { strafeWanted = want; strafeWantedFor = 0f; }
            else strafeWantedFor += dt;
            if (strafeWantedFor > 0.15f || want == loco) config.animLocomotion = strafeWanted;
        }

        /// <summary>La grulla voladora sale sí o sí en los primeros ~20 s (el rojo de la fase 1 se aprende temprano).</summary>
        void TeachLeap()
        {
            if (teachLeap == null) return;
            bool used = teachLeap.lastUsed >= fightStart;
            teachLeap.weight = Time.time - fightStart > 14f && !used ? 4f : 1f;
        }

        /// <summary>
        /// El paso del viento solo se elige con Kaito a 4.2 m o más (de cerca el vuelo no tiene dónde estirarse) y el que
        /// pelea pegado no lo veía nunca: hasta que sale una vez en la fase pesa cuatro veces más, así el primer respiro
        /// de Kaito a distancia lo trae.
        /// </summary>
        void TeachDash()
        {
            if (teachDash == null) return;
            teachDash.weight = teachDash.lastUsed >= phaseStart ? teachDashWeight : teachDashWeight * 4f;
        }

        // ================================================================== golpes
        protected override void OnStepStarted(AttackDef a)
        {
            base.OnStepStarted(a);
            clip = BambooMasterTimings.Get(a.state);
            travelDone = 0f;
            airStretch = 1f;
            landed = leapFixed = laneFixed = dashFx = false;
            look.ClearTell();
            if (clip != null)
            {
                // fundido según de qué pose viene: los clips encadenan pose con pose (READY, COIL...); si no coinciden,
                // o viene de un parry, el fundido corto de Enemy cruzaba la mano por el cuerpo
                bool counter = step == 0 && pattern == counterPattern;
                string from = counter ? BambooMasterTimings.Counter.ChainTo : prevChainTo;
                float fade = afterRecoil ? 0.18f : step == 0 && !counter ? 0.15f : from == clip.ChainFrom ? 0.08f : 0.2f;
                if (fade > 0.08f) anim.Play(a.state, fade);
                prevChainTo = clip.ChainTo;
            }
            afterRecoil = false;
            if (a.special == BambooMasterMoves.Qi) BeginQiStep(a);
        }

        protected override void TickSpecial(AttackDef a, float dt)
        {
            if (clip == null) { base.TickSpecial(a, dt); return; }
            if (a.special == BambooMasterMoves.Leap) TickLeap(a);
            if (a.special == BambooMasterMoves.Dash) TickDash(a);
            Travel(a);
            switch (a.special)
            {
                case BambooMasterMoves.Strike: HitArc(a); break;
                case BambooMasterMoves.Sweep: HitSweep(a); break;
                case BambooMasterMoves.Qi: TickQiStep(a); break;
            }
        }

        /// <summary>
        /// El cuerpo avanza lo que avanza el clip (travel_m) en el reloj del paso: los pies apoyados quedan clavados. La
        /// grulla voladora estira el tramo en el aire para caer en la marca. Nunca atraviesa a Kaito (salvo el salto,
        /// que cae sobre él): lo que no entra se pierde.
        /// </summary>
        void Travel(AttackDef a)
        {
            if (clip.Travel == null || anim.Frozen) return;
            float x = StretchedTravel(stepNorm, airStretch);
            float d = x - travelDone;
            travelDone = x;
            if (d <= 0f) return;
            Vector3 dir = laneFixed ? laneD : leapFixed ? leapDir : transform.forward;
            float room = d;
            if (target != null && a.special != BambooMasterMoves.Leap)
            {
                // solo frena contra lo que tiene adelante: con Kaito al costado la embestida sigue entera
                Vector3 to = (target.transform.position - transform.position).Flat();
                float along = Vector3.Dot(to, dir), lat = Mathf.Abs(Vector3.Dot(to, Vector3.Cross(Vector3.up, dir)));
                if (along > 0f && lat < Radius + target.Radius) room = along - Radius - target.Radius - 0.25f;
            }
            if (room > 0f) MoveBy(dir * Mathf.Min(d, room));
        }

        /// <summary>Lo que avanzó el cuerpo en 'n' con el tramo en el aire (los dos pies arriba) estirado por 'k'.</summary>
        float StretchedTravel(float n, float k)
        {
            float x = clip.TravelAt(n);
            if (k != 1f && clip.AirEnd > clip.AirStart) x += (k - 1f) * (clip.TravelAt(Mathf.Clamp(n, clip.AirStart, clip.AirEnd)) - clip.TravelAt(clip.AirStart));
            return x;
        }

        /// <summary>Golpe dorado: el alcance del miembro (o del bastón) desde donde está en el impacto, más el grosor.</summary>
        void HitArc(AttackDef a)
        {
            if (stepHit || target == null || stepNorm < a.activeStart || stepNorm > a.activeEnd) return;
            Vector3 tp = target.transform.position;
            if (Mathf.Abs(tp.y - transform.position.y) > 2.5f) return;
            if (!CombatMath.InArc(transform, tp, clip.Reach + 0.3f, a.arc, target.Radius)) return;
            stepHit = true;
            HitPlayer(a, transform.position);
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

        // ------------------------------------------------------------------ paso del viento
        /// <summary>
        /// Embestida: en la suelta el carril queda fijo y salen las imágenes residuales (DashStart → DashEnd del clip, en
        /// jade pálido: la estela de alguien rápido, no un aviso). Pega en el contacto si Kaito sigue en el carril y al
        /// alcance de la mano (o del bastón).
        /// </summary>
        void TickDash(AttackDef a)
        {
            if (!laneFixed && stepClock >= tl.ReleaseTime)
            {
                laneFixed = true;
                laneO = transform.position;
                laneD = transform.forward.Flat().normalized;
                airStretch = DashStretch(laneO, laneD);
            }
            float start = clip.Event("DashStart"), end = clip.Event("DashEnd");
            if (!dashFx && start >= 0f && stepNorm >= start)
            {
                dashFx = true;
                // lo que tarda la suelta en ir de DashStart a DashEnd (el clip va a releaseRate en ese tramo)
                float dur = Mathf.Max(0.15f, tl.tR * (Mathf.Max(end, start) - start) / Mathf.Max(0.01f, clip.Contact - clip.Apex));
                Game.FX?.AfterImages(model, dur, 0.04f, GhostJade);
                Game.FX?.DashBurst(transform.position, laneD);
                Game.Audio?.Play("dash", transform.position, 1f, 0.05f);
            }
            if (stepHit || target == null || stepNorm < a.activeStart || stepNorm > a.activeEnd) return;
            Vector3 tp = target.transform.position;
            if (!InLane(tp, target.Radius * 0.5f)) return;
            if (Vector3.Dot((tp - transform.position).Flat(), laneD) - target.Radius > clip.Reach + 0.3f) return;
            stepHit = true;
            HitPlayer(a, transform.position);
        }

        float LaneWidth => 2f * (Radius + 0.6f);
        /// <summary>El carril llega hasta donde de verdad termina la embestida (con su tramo en el aire ya ajustado) más
        /// el alcance de la mano o del bastón.</summary>
        float LaneLength
        {
            get
            {
                if (clip == null) return 8f;
                float k = LaneLive ? airStretch : DashStretch(transform.position, transform.forward.Flat().normalized);
                return StretchedTravel(1f, k) + clip.Reach;
            }
        }

        /// <summary>
        /// El paso del viento está autorado con 6.5 m: desde 4.2 m (lo más cerca que lo elige) pasaba 3 m de largo y
        /// Travel lo frenaba contra Kaito a mitad del vuelo, con el clip todavía corriendo en el aire. Se estira o se
        /// acorta el vuelo (timing.air, los dos pies arriba) para que llegue justo a donde Travel lo deja: el pie se clava
        /// con la mano sobre Kaito y el resto del frenado entra sin patinar.
        /// </summary>
        float DashStretch(Vector3 from, Vector3 dir)
        {
            float air = clip.TravelAt(clip.AirEnd) - clip.TravelAt(clip.AirStart);
            if (target == null || air < 0.1f) return 1f;
            float along = Vector3.Dot((target.transform.position - from).Flat(), dir);
            float stop = Radius + target.Radius + 0.25f;
            float want = along - stop - (clip.TravelAt(1f) - clip.TravelToContact);
            return Mathf.Clamp(1f + (want - clip.TravelToContact) / air, 0.15f, 1.5f);
        }

        bool InLane(Vector3 p, float pad)
        {
            var area = new TellArea { lane = true, origin = LaneLive ? laneO : transform.position, forward = LaneLive ? laneD : transform.forward.Flat().normalized, size = LaneLength, width = LaneWidth };
            return area.Contains(p, pad);
        }

        /// <summary>La embestida: hasta el contacto, salvo que Kaito haya salido del carril (se corrió a tiempo: el
        /// aviso se deshace y la carrera ya no puede pegar).</summary>
        float DashEta(AttackDef a)
        {
            if (stepHit || target == null || stepClock >= tl.T) return float.PositiveInfinity;
            if (LaneLive && !InLane(target.transform.position, target.Radius)) return float.PositiveInfinity;
            return tl.T - stepClock;
        }

        /// <summary>El carril de este paso ya quedó fijo (BeginStep pide la ETA antes de OnStepStarted: el del paso
        /// anterior todavía figura como fijo).</summary>
        bool LaneLive => laneFixed && stepClock >= tl.ReleaseTime;

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
                    area = new TellArea { lane = true, origin = LaneLive ? laneO : transform.position, forward = LaneLive ? laneD : transform.forward.Flat().normalized, size = LaneLength, width = LaneWidth };
                    return true;
            }
            return base.HitAreaFor(a, out area);
        }

        // ================================================================== recibir golpes
        /// <summary>
        /// Un maestro no se deja pegar fuera de sus huecos: lo que le entra a la guardia, en neutral, en el contragolpe o en
        /// sus golpes (los dorados enteros, los rojos hasta que pegan) rebota con un manotazo y no le suma postura (la
        /// barra se llena solo con parries: los golpes de relleno no la gastaban de a 0.25 y el que machacaba lo ponía de
        /// rodillas sin desviar nada). El segundo rebote seguido se contragolpea, y la postura del bambú desvía al primero.
        /// Los huecos: el contraataque del parry (Recoil), de rodillas, llamando a Kaito (esperó la postura) y la vuelta de
        /// un rojo que no pegó. Con la regla común (aguante 2 en neutral, cambio de golpes en el amague) el bot "bueno" lo
        /// terminaba en ~1 min (Tools/Dev/sim_bamboo_master.py).
        /// </summary>
        public override HitResult ReceiveHit(in DamageInfo info)
        {
            bool fromKaito = info.sourceFaction == Faction.Player;
            if (fromKaito && IsAlive && look != null)
            {
                // en escena (cambio de fase): rebota con clang, no hay a quién castigar
                if (transition != null) { LastHitTime = Time.time; return HitResult.Blocked; }
                bool guardable = info.kind == AttackKind.Light || info.kind == AttackKind.Heavy;
                if (stance && State == EnemyState.Guard && guardable) { LastHitTime = Time.time; return Deflect(true); }
                if (guardable && Bounces()) { LastHitTime = Time.time; return Bounce(); }
            }
            var i = info;
            // piso de vida de la fase: el que lo baja al umbral dispara el cambio; lo que sobra no se cuenta
            if (fromKaito && i.damage > 0f && IsAlive && look != null)
            {
                float floor = Gates[Mathf.Clamp(phaseIdx + 1, 1, 3)] * config.maxHealth;
                float mul = State == EnemyState.Exhausted ? config.exhaustedDamageMul : 1f;
                if (phaseIdx < 2) i.damage = Mathf.Min(i.damage, Mathf.Max(0f, Health - floor) / mul);
            }
            var r = base.ReceiveHit(i);
            if (look == null || !fromKaito) return r;
            // Enemy toca las reacciones de la fase 1 por nombre (HitHeavy, ExhaustedHit): con el saco tirado o el bastón
            // en la mano, la pose de la fase 1 no existe
            if (phaseIdx > 0)
            {
                if (anim.Current == "HitHeavy") anim.Play("HitHeavy" + suffix, 0.03f);
                else if (anim.Current == "ExhaustedHit") anim.Play("ExhaustedHit" + suffix, 0.03f);
            }
            if (anim.Current == "ExhaustedHit" + suffix && State == EnemyState.Exhausted) kneelHeld = kneelClock;
            // le entró el contraataque: se rehace antes de volver a atacar (Enemy lo largaba al combo siguiente apenas
            // se reponía, y el parry se volvía una cinta: parry, contra, golpe, parry...)
            if (r == HitResult.Hit && State == EnemyState.Stagger)
                nextAttackTime = Mathf.Max(nextAttackTime, Time.time + stateDuration + Random.Range(config.attackCooldown.x, config.attackCooldown.y));
            return r;
        }

        /// <summary>¿Este golpe de Kaito (corte o tajo final) rebota? Ver ReceiveHit.</summary>
        bool Bounces()
        {
            switch (State)
            {
                case EnemyState.Attack:
                    var a = CurrentAttack;
                    return a == null || a.kind != AttackKind.Unblockable || !float.IsInfinity(StrikeEta);
                case EnemyState.Counter:
                case EnemyState.Guard:
                case EnemyState.Chase:
                case EnemyState.Strafe:
                case EnemyState.Alert:
                case EnemyState.Stagger:
                case EnemyState.Idle:
                    return true;
                default:
                    return false;   // Recoil, Exhausted: los huecos
            }
        }

        // el último rebote y cuántos seguidos (el segundo dentro de BounceWindow se contragolpea)
        float lastBounce = -99f;
        int bounces;

        /// <summary>
        /// Rebote: clang del lado de Kaito (PlayerController con Blocked). Parado se cubre con el manotazo de GuardHit; en
        /// pleno golpe o contragolpe sigue su movimiento (la mano libre aparta la hoja). El segundo seguido en la guardia
        /// o en neutral se le devuelve con el contragolpe, como a cualquier guardia del juego.
        /// </summary>
        HitResult Bounce()
        {
            bool busy = State == EnemyState.Attack || State == EnemyState.Counter;
            if (!busy)
            {
                if (Time.time - lastBounce > BounceWindow) bounces = 0;
                if (++bounces >= 2) { bounces = 0; lastBounce = -99f; return Deflect(false); }
                if (State != EnemyState.Guard) { ReleaseToken(); EnterGuard(); }
                stateDuration = Mathf.Max(stateDuration, stateTime + 0.5f);
                if (target != null) transform.rotation = Quaternion.LookRotation((target.transform.position - transform.position).Flat().normalized + transform.forward * 0.001f);
                anim.Play("GuardHit" + suffix, 0.03f);
                Game.UI?.ShowGuardMark(this);
            }
            lastBounce = Time.time;
            if (!deflectToldOnce) { deflectToldOnce = true; Bark(StoryText.ChikuoLine("paciencia")); ShowTip(StoryText.Hint("bamboo_guard")); }
            return HitResult.Blocked;
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
                if (phaseIdx > 0 && anim.Current == "ParriedPerfect") anim.Play("ParriedPerfect" + suffix, 0.03f);
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

        void EnterStance()
        {
            EnterGuard();
            stance = true;
            float hold = Random.Range(StanceTime.x, StanceTime.y);
            stanceUntil = Time.time + hold;
            stateDuration = hold + 5f;   // la postura termina por su cuenta (TickStance), no por el tiempo de la guardia
            look.SetStance(true);
            Game.Audio?.Play("parry_ready", transform.position, 0.5f, 0.05f);
            if (!stanceTaught) { stanceTaught = true; ShowTip(StoryText.Hint("bamboo_stance")); }
        }

        /// <summary>Kaito esperó: baja la guardia y lo llama con la mano (abierto unos segundos, sin estar mareado).</summary>
        void TickStance()
        {
            if (!stance) return;
            if (State != EnemyState.Guard) { stance = false; look.SetStance(false); return; }
            if (Time.time < stanceUntil) return;
            stance = false;
            look.SetStance(false);
            taunt = true;
            savedImbalance = Imbalance;
            BecomeExhausted();
            if (!waitToldOnce) { waitToldOnce = true; Bark(StoryText.ChikuoLine("espera")); }
        }

        /// <summary>Le pegaron en la postura (o insistieron contra su guardia): desvía con un círculo de la mano y
        /// contragolpea (lo que pasa por apurarse).</summary>
        HitResult Deflect(bool fromStance)
        {
            stanceCounter = fromStance;
            stance = false;
            look.SetStance(false);
            Stop();
            ReleaseToken();
            pattern = counterPattern;
            SetState(EnemyState.Counter);
            stateDuration = Mathf.Clamp(anim.Length(config.animCounter, 0.5f), 0.2f, 0.6f);
            anim.Play(config.animCounter, 0.02f);
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
            var t = BambooMasterTimings.Get("Taunt" + suffix) ?? BambooMasterTimings.Taunt;
            stateDuration = t.Seconds;
            anim.Play(t.State, 0.2f);
        }

        protected override void OnExhaustionEnded()
        {
            if (taunt) { taunt = false; Imbalance = savedImbalance; return; }
            // si se levanta antes de terminar el clip (los golpes de la ventana) usa el clip de pararse, no el fundido
            if (Time.time - kneelStart < config.exhaustedTime - 0.3f) anim.Play("ExhaustedRise" + suffix, 0.08f);
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
            phase = Mathf.Clamp(phase, phaseIdx + 2, 3);
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
