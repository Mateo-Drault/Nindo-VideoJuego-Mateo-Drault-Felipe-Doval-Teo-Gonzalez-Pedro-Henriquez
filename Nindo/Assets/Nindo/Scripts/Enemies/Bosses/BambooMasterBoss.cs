using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

namespace Nindo
{
    /// <summary>
    /// Lo que un jefe le dice al bot de pruebas (Input/AutoPilot.cs, "bot on") cuando no se pelea yendo derecho a su raíz.
    /// Chikuō vive arriba de las cañas: a él no se le pega arriba, se le corta lo que lo sostiene.
    /// </summary>
    public interface IBotHints
    {
        /// <summary>Adónde ir: la base de su caña; mientras salta, la de salida hasta que agarra (una persona no corre debajo
        /// de un salto de 0.6 s); en el piso, la raíz.</summary>
        Vector3 BotTarget { get; }
        /// <summary>¿Cortar sirve? Posado, trepando o en la pértiga, solo con las campanas blancas (sin ellas, la caña barre).</summary>
        bool BotMayCut { get; }
        /// <summary>Un latigazo posible: la base cargada (o la caña de destino de un salto, 'fall'), abierto hasta 'until'
        /// (Time.time). Cada ventana nueva tiene un 'until' nuevo.</summary>
        bool BotCutGoal(out Vector3 goal, out float until, out bool fall);
    }

    /// <summary>
    /// Chikuō, el Ermitaño de las Cañas (arquetipo y bossId "ozeki", SealId.Bambu, música "boss_bamboo" en tres fases).
    /// Un viejo ermitaño excéntrico que vive en las seis cañas del claro (siete en la fase 3): sopla dardos con su
    /// flauta-bastón, salta de caña en caña en menos de un segundo, cae al piso a golpear y vuelve arriba. Diseño completo en
    /// Docs/handoff/diseno/chikuo_v2.md. La regla de la pelea: a él no se le pega arriba; SE LE CORTA LO QUE LO SOSTIENE.
    ///  * El latigazo (BambooMasterBoss.Canopy): cuando carga su caña (la ráfaga, el silbador, colgado, la risa, trepando, al
    ///    agarrarse de un salto) los cascabeles laten en blanco y aparece un ensō blanco en la base. Un corte ahí suelta el
    ///    resorte y lo despide para el lado del corte: revolcón, estampado contra otra caña (el billar), o la caída del cielo
    ///    si se le corta la caña adonde salta. Sin campanas, la caña barre ("¡Cosquillas!").
    ///  * Tres fases que cambian la forma: Las Cañas (100-65 %), El Piso (65-40 %: las cañas inclinadas, tandas de bastón sin
    ///    guardia, la Grulla en el Bastón y Pregunta y Respuesta: .Ground) y El Bosque Entero (40-0 %: el bucle al doble con
    ///    la Caña Madre, la catapulta, la rajadura y la tala).
    ///  * Nunca espera ni se cubre: los huecos salen de reglas que se ven (sección 6), no de una barra de postura.
    /// La raíz del jefe (cápsula, NavMeshAgent, fijado, el imán del corte de Kaito, el anillo de sus golpes) queda en la BASE
    /// de su caña mientras está arriba; el modelo se dibuja en el PerchNode de la caña (se inclina con el arco). En el aire
    /// la raíz viaja con él por el piso. Así Kaito y su bot no cambian: el corte a la base es el corte a Chikuō.
    /// Cada acción es una corrutina que toca los clips del sidecar (ChikuoTimings) en su tiempo natural; lo que pega con
    /// anillo pasa por la maquinaria de Enemy (un paso "held": Enemy dibuja el aviso con la ETA que da el jefe).
    /// </summary>
    public partial class BambooMasterBoss : Boss, ICameraProfile, IBotHints
    {
        static readonly float[] Gates = BambooMasterMoves.Gates;

        /// <summary>Dónde está el cuerpo: en el piso (el modelo sobre la raíz, como cualquier enemigo), posado (el modelo en
        /// el PerchNode de su caña) o llevado por el código (saltos, picadas, revolcones).</summary>
        enum Body { Ground, Perch, Carried }

        /// <summary>Qué le pasa a un corte de Kaito ahora (ReceiveHit; tabla de la sección 9 del diseño).</summary>
        enum Vuln { None, Scene, Tickle, Loaded, Climb, Air, Crouch, Open, Neutral, Armor, Flute }

        // ------------------------------------------------------------------ cámara
        /// <summary>Los 45° de pelea de siempre: subir o bajar el ángulo casi no cambia el encuadre (sección 10).</summary>
        public float CameraPitch => 0f;
        /// <summary>Más lejos con él arriba o en el aire (posado a 4-5 m), un poco menos en el piso.</summary>
        public float CameraExtraDistance => body != Body.Ground || HeightAboveFloor > 1f || !groundAI && phaseIdx != 1 ? 2.4f : 1.6f;

        public override int CurrentPhase => phaseIdx;
        public bool Transitioning => vuln == Vuln.Scene && Fighting;

        BambooMasterLook look;
        BambooGrove grove;
        MizuchiMarks marks;
        HitFlash flash;
        CapsuleCollider capsule;
        int phaseIdx;
        bool begun;
        Coroutine act;
        string baseSubtitle;

        // ------------------------------------------------------------------ cuerpo
        Body body = Body.Ground;
        BambooStalk perch;
        Vector3 carryPos;
        Quaternion carryRot = Quaternion.identity;
        Quaternion perchYaw = Quaternion.identity;
        bool perchFaceLock;
        Vector3 perchFaceDir = Vector3.forward;
        float modelLift;
        Vector3 modelLocalScale = Vector3.one;
        /// <summary>Trepando: lo que falta del arrimo al culmo (1 → 0 entre f0 y GrabStalk: Climb del sidecar).</summary>
        float climbBlend;
        Vector3 climbFrom;

        // ------------------------------------------------------------------ el clip que toca la acción
        ChikuoClip clip;
        float clipT, clipRate = 1f;
        // un tramo del clip a otra velocidad (la inspiración exagerada de las primeras Tres Notas)
        float slowFrom = -1f, slowTo = -1f, slowRate = 1f;

        // ------------------------------------------------------------------ vulnerabilidad y huecos
        Vuln vuln = Vuln.None;
        BambooMasterMoves.Hole hole;
        int holeLeft;
        float holeUntil;
        string holeLoop, holeHit;
        // la carga
        BambooStalk loadedStalk;
        float loadUntil;
        int loadsUncut;
        bool loadCut;
        // el salto en curso (para la caída del cielo y el bot)
        BambooStalk leapFrom, leapDest;
        float leapGrabAt = -1f;
        bool leapCatchable;
        // cortes que ya le abrieron la vuelta arriba en esta bajada (uno solo por bajada)
        bool returnCutUsed;
        // la fase cambia: lo que la corrutina en curso haga después de esto ya no vale
        bool phaseChanging;
        int attempts, retryPhase;

        // ------------------------------------------------------------------ dardos por salir (ETA honesta)
        struct PendingDart { public float at; public bool cued, glinted; }
        readonly List<PendingDart> pending = new List<PendingDart>(4);
        float projEta = float.PositiveInfinity;
        Vector3 projFrom;
        bool dartHitPending, dartGlow;

        // ------------------------------------------------------------------ paso "held" (lo coreografía el jefe)
        bool heldStep;
        float heldStrikeAt = -1f, heldTravel;
        bool heldStruck;
        Vector3 heldAreaOrigin, heldAreaDir;
        float heldAreaSize, heldAreaWidth;
        bool heldAreaLane;

        // ------------------------------------------------------------------ Kaito
        float kaitoDashAt = -9f;
        bool kaitoWasDashing;
        float campFor;

        // ------------------------------------------------------------------ texto
        float tipHideAt = -1f, lastBark = -99f;
        readonly HashSet<string> said = new HashSet<string>();
        static readonly Color BarkColor = new Color(0.78f, 0.92f, 0.62f);
        const float TipSeconds = 5f, BarkGap = 12f;

        // ================================================================== setup
        protected override void Start()
        {
            base.Start();
            if (Defeated) return;
            baseSubtitle = subtitle;
            look = new BambooMasterLook(model);
            flash = model.GetComponent<HitFlash>();
            capsule = GetComponent<CapsuleCollider>();
            modelLift = model.localPosition.y;
            modelLocalScale = model.localScale;
            // el "¡ahora!" del aviso destella en la punta de la flauta (Enemy lo busca en katanaTip)
            if (look.Muzzle != null) katanaTip = look.Muzzle;
            if (look.StaffBottom != null && look.StaffTop != null && trail == null)
                trail = BladeTrail.Create(transform, look.StaffBottom, look.StaffTop, Game.Content != null ? Game.Content.trailMaterial : null, TellStyle.TrailParry);
            marks = MizuchiMarks.Create();
            marks.transform.SetParent(transform.parent, false);
            GameEvents.PlayerDied += OnPlayerDied;
            EnsureGrove();
            WaitPose();
        }

        protected override void OnDestroy()
        {
            base.OnDestroy();
            GameEvents.PlayerDied -= OnPlayerDied;
            if (marks != null) Destroy(marks.gameObject);
            grove?.Dispose();
            ClearCameraBias();
        }

        /// <summary>Las cañas las arma WorldBuilder con el mundo; si el jefe nace antes, se juntan en la presentación.</summary>
        bool EnsureGrove()
        {
            if (grove != null) return true;
            grove = BambooGrove.Build(transform.parent, arenaCenter);
            if (grove == null)
            {
                if (!warnedGrove) Debug.LogWarning("[Nindo] Chikuō: el claro no tiene las cañas de la arena (ArenaStalk_*): ¿World_bambu.fbx viejo?");
                warnedGrove = true;
                return false;
            }
            arenaCenter = new Vector3(grove.Center.x, arenaCenter.y, grove.Center.z);
            var o1 = grove.Get("O1");
            if (o1 != null) spawnPos = o1.Base;
            grove.Reset(0);
            return true;
        }

        bool warnedGrove;

        void OnPlayerDied()
        {
            if (!Fighting) return;
            attempts++;
            // el viejo retoma la lección donde quedó: el reintento arranca en la fase más alta a la que llegó Kaito
            retryPhase = Mathf.Max(retryPhase, phaseIdx);
        }

        public override void ResetEnemy()
        {
            base.ResetEnemy();   // config de fábrica, vida, lugar, StopAllCoroutines
            act = null;
            if (look == null) return;
            begun = false;
            phaseChanging = false;
            phaseIdx = 0;
            subtitle = baseSubtitle;
            config.patterns = BambooMasterMoves.GroundPatterns(1);
            ClearActionState();
            BambooDart.ClearAll();
            marks?.Clear();
            look.Extinguish();
            loadsUncut = 0;
            // lo que el intento anterior dejó a medias (colgado, la revancha, los relojes de la fase 2 y la 3 en Time.time
            // viejos: el reintento abriría con la Grulla al instante en vez de a los 4-6 s)
            hanging = leaving = justLanded = revanchaPending = dartHitPending = firstVolleyDone = dartGlow = false;
            tickles = actionsOnStalk = 0;
            nextPoleAt = nextQaAt = nextSignatureAt = -1f;
            lastFlip = -9f;
            campFor = 0f;
            hangBlend = lastPerchBias = 0f;
            said.Clear();
            lastBark = -99f;
            if (tipHideAt > 0f) { Game.UI?.HideTutorial(); tipHideAt = -1f; }
            ClearCameraBias();
            if (EnsureGrove()) grove.Reset(retryPhase);
            WaitPose();
        }

        /// <summary>
        /// Espera la llegada de Kaito: colgado cabeza abajo de la punta de O1 tocando la flauta (el primer cuadro del Intro);
        /// en un reintento de la fase 2, parado en el centro del claro; de la fase 3, posado en la Madre.
        /// </summary>
        void WaitPose()
        {
            EnterScripted();
            vuln = Vuln.None;
            if (grove == null) { SetBody(Body.Ground); return; }
            if (retryPhase == 1)
            {
                Warp(grove.Center + (grove.Get("O1") != null ? (grove.Get("O1").Base - grove.Center).normalized * 2f : Vector3.left * 2f));
                SetBody(Body.Ground);
                anim.Play("Idle", 0f);
                return;
            }
            var s = retryPhase >= 2 && grove.Mother != null ? grove.Mother : grove.Get("O1");
            PerchOn(s);
            // colgado de O1 quieto en el primer cuadro del Intro hasta que lo arranque la presentación
            if (retryPhase >= 2) Play(ChikuoTimings.PerchIdle, 0f);
            else Play(ChikuoTimings.Intro, 0f, 0f, 0f);
        }

        // ================================================================== por frame
        protected override void Update()
        {
            if (look == null) { base.Update(); return; }
            // la pelea arrancó (BossIntroRoutine llamó BeginFight): antes que Enemy, que en Chase ya buscaría un patrón del piso
            if (Fighting && !begun && IsAlive) BeginMine();
            // Kaito cayó: deja lo que hacía y se ríe hasta que la arena lo reinicia (Enemy, con su blanco muerto, lo pasaba a
            // Idle y le tocaba la locomoción arriba de la caña)
            if (Fighting && begun && !kaitoDown && target != null && !target.IsAlive) { kaitoDown = true; Run(KaitoDown()); }
            TrackKaito();
            base.Update();
            float dt = Time.deltaTime;
            if (dt <= 0f) return;
            if (!anim.Frozen) AdvanceClip(dt);
            grove?.Tick(dt);
            UpdateProjectiles(dt);
            UpdateLoad(dt);
            UpdateVulnFromState();
            TickHeldGlow();
            look.Tick(dt);
            if (tipHideAt > 0f && Time.unscaledTime > tipHideAt) { tipHideAt = -1f; Game.UI?.HideTutorial(); }
            anim.Tick();
        }

        void LateUpdate()
        {
            if (look == null) return;
            PlaceModel(Time.deltaTime);
            UpdateCamera();
        }

        bool kaitoDown;

        IEnumerator KaitoDown()
        {
            vuln = Vuln.None;
            if (body == Body.Carried) Landed(transform.position, transform.forward);
            Play(body == Body.Perch ? ChikuoTimings.PerchLaugh : ChikuoTimings.GroundLaugh, 0.2f);
            while (true) yield return null;
        }

        void BeginMine()
        {
            begun = true;
            kaitoDown = false;
            if (!EnsureGrove()) return;
            phaseIdx = Mathf.Clamp(retryPhase, 0, 2);
            if (phaseIdx >= 1)
            {
                // misma frame que PlayBossMusic (Boss.BeginFight): el tema arranca directo en su fase
                Health = Mathf.Min(Health, Gates[phaseIdx] * config.maxHealth);
                Game.Audio?.SetBossMusicPhase(phaseIdx + 1);
                subtitle = PhaseSubtitle(phaseIdx);
                Game.UI?.BossRetitled(this);
            }
            config.patterns = BambooMasterMoves.GroundPatterns(Mathf.Max(1, phaseIdx));
            SetState(EnemyState.Scripted);
            firstActions = phaseIdx == 0 && retryPhase == 0 ? 0 : 3;
            Run(Brain());
        }

        /// <summary>Kaito: cuándo arrancó su dash (la esquiva perfecta de la picada abre los Pies Enterrados) y si acampa
        /// al pie de la caña.</summary>
        void TrackKaito()
        {
            var p = target != null ? target : Game.Player;
            if (p == null) return;
            bool dashing = p.State == PlayerState.Dash;
            if (dashing && !kaitoWasDashing) kaitoDashAt = Time.time;
            kaitoWasDashing = dashing;
            bool camping = body == Body.Perch && perch != null && (p.transform.position - perch.Base).Flat().magnitude <= BambooMasterMoves.CampDist && loadedStalk == null;
            campFor = camping ? campFor + Time.deltaTime : 0f;
        }

        /// <summary>¿El dash de Kaito que esquivó este golpe fue perfecto? (los i-frames del principio: PlayerConfig).</summary>
        bool PerfectDodge => Time.time - kaitoDashAt <= 0.02f + 0.16f + 0.02f;

        // ================================================================== el clip de la acción
        /// <summary>Toca 'c' desde 'from' (normalizado) a 'rate' con un fundido. El reloj (clipT) se frena con el hit-stop
        /// local igual que el Animator: los eventos del sidecar caen en el cuadro que se ve.</summary>
        void Play(ChikuoClip c, float fade, float from = 0f, float rate = 1f)
        {
            clip = c;
            clipT = from * c.Seconds;
            clipRate = rate;
            slowFrom = slowTo = -1f;
            travelDone = c.TravelAt(from);
            anim.Play(c.State, fade, from, rate);
            anim.SetSpeed(1f);
        }

        void AdvanceClip(float dt)
        {
            if (clip == null) return;
            float r = clipRate;
            if (slowFrom >= 0f && clipT >= slowFrom && clipT < slowTo) r *= slowRate;
            clipT += dt * r;
            // (los golpes del piso los toca Enemy con su línea de tiempo: no se les pisa la velocidad)
            if (anim.Current == clip.State) anim.SetStateSpeed(r);
            if (clip.Loop) return;
            // un clip que terminó queda en su último cuadro (el controller no tiene transiciones)
            if (clipT > clip.Seconds) clipT = clip.Seconds;
        }

        float ClipNorm => clip == null ? 1f : clip.Loop ? Mathf.Repeat(clipT / clip.Seconds, 1f) : Mathf.Clamp01(clipT / clip.Seconds);
        bool ClipDone => clip == null || !clip.Loop && clipT >= clip.Seconds - 1e-4f;

        /// <summary>Segundos reales hasta que el clip llegue a 'norm' (con el tramo lento, si hay).</summary>
        float RealUntil(float norm)
        {
            if (clip == null) return 0f;
            float t = norm * clip.Seconds;
            if (t <= clipT) return 0f;
            float rate = Mathf.Max(0.01f, clipRate);
            if (slowFrom < 0f) return (t - clipT) / rate;
            float s = 0f, x = clipT;
            if (x < slowFrom) { float e = Mathf.Min(t, slowFrom); s += (e - x) / rate; x = e; }
            if (x < t && x < slowTo) { float e = Mathf.Min(t, slowTo); s += (e - x) / (rate * slowRate); x = e; }
            if (x < t) s += (t - x) / rate;
            return s;
        }

        /// <summary>Espera a que el clip llegue a 'norm' (el hit-stop lo frena).</summary>
        IEnumerator Until(float norm)
        {
            while (clip != null && clipT < norm * clip.Seconds - 1e-4f) yield return null;
        }

        /// <summary>Espera 'seconds' de juego (se frena con el hit-stop local como el clip).</summary>
        IEnumerator Wait(float seconds)
        {
            float t = 0f;
            while (t < seconds) { if (!anim.Frozen) t += Time.deltaTime; yield return null; }
        }

        // ================================================================== el cuerpo
        void SetBody(Body b)
        {
            body = b;
            bool ground = b == Body.Ground;
            if (agent != null)
            {
                if (ground && !agent.enabled)
                {
                    agent.enabled = true;
                    if (NavMesh.SamplePosition(transform.position, out var hit, 2f, NavMesh.AllAreas)) agent.Warp(hit.position);
                }
                else if (!ground && agent.enabled) agent.enabled = false;
            }
            // en el aire la cápsula se apaga (no empuja a Kaito a 12 m/s); posado queda en la base (no se metan en la caña)
            if (capsule != null) capsule.enabled = b != Body.Carried && IsAlive;
            if (ground)
            {
                model.localPosition = new Vector3(0f, modelLift, 0f);
                model.localRotation = modelBaseRot;
                model.localScale = modelLocalScale;
                if (perch != null) { perch.S.Occupied = false; perch = null; }
            }
        }

        /// <summary>Posado en 's': la raíz en su base, el modelo en su PerchNode.</summary>
        void PerchOn(BambooStalk s)
        {
            if (perch != null && perch != s) perch.S.Occupied = false;
            perch = s;
            s.S.Occupied = true;
            SetBody(Body.Perch);
            Warp(s.Base);
            perchFaceDir = FaceDirFrom(s.Base);
            perchYaw = Quaternion.LookRotation(perchFaceDir);
        }

        /// <summary>La raíz en un punto del piso (sin agente: arriba la mueve el código).</summary>
        void Warp(Vector3 p)
        {
            p.y = grove != null ? grove.FloorY : p.y;
            if (agent != null && agent.enabled && agent.isOnNavMesh) agent.Warp(p);
            else transform.position = p;
        }

        Vector3 FaceDirFrom(Vector3 from)
        {
            var p = target != null ? target : Game.Player;
            Vector3 d = p != null ? (p.transform.position - from).Flat() : transform.forward.Flat();
            return d.sqrMagnitude > 1e-4f ? d.normalized : Vector3.forward;
        }

        /// <summary>Lleva el cuerpo por el código: la raíz viaja por el piso debajo de él (la cámara lo sigue).</summary>
        void Carry(Vector3 pos, Quaternion rot)
        {
            if (body != Body.Carried) SetBody(Body.Carried);
            carryPos = pos;
            carryRot = rot;
            if (perch != null) { perch.S.Occupied = false; perch = null; }
            transform.position = new Vector3(pos.x, grove != null ? grove.FloorY : transform.position.y, pos.z);
            Vector3 f = (rot * Vector3.forward).Flat();
            if (f.sqrMagnitude > 1e-4f) transform.rotation = Quaternion.LookRotation(f);
        }

        /// <summary>
        /// Dónde se dibuja el modelo (LateUpdate: después del Animator y del arco de este frame, antes de SpringChain, la
        /// cámara y los cascabeles de la caña). Posado: en el PerchNode, con el giro del tramo (se inclina con el arco) y
        /// mirando a Kaito alrededor del culmo; en la Madre (culmo más grueso) 5 cm hacia su frente.
        /// </summary>
        void PlaceModel(float dt)
        {
            if (body == Body.Ground) return;
            if (body == Body.Carried) { model.SetPositionAndRotation(carryPos, carryRot); return; }
            if (perch == null || perch.S.PerchNode == null) return;
            var node = perch.S.PerchNode;
            Vector3 up = node.up;
            if (!perchFaceLock) perchFaceDir = FaceDirFrom(perch.Base);
            Vector3 fwd = Vector3.ProjectOnPlane(perchFaceDir, up);
            if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.ProjectOnPlane(node.forward, up);
            Quaternion want = Quaternion.LookRotation(fwd.normalized, up);
            perchYaw = Quaternion.Slerp(perchYaw, want, 1f - Mathf.Exp(-8f * dt));
            Vector3 pos = node.position + perchYaw * Vector3.forward * (perch.IsMother ? 0.05f : 0f);
            if (clip == ChikuoTimings.Climb)
            {
                // Climb está autorado sobre la caña de adentro (posado a 4.4 m): en las otras (4.0 / 4.8 / Madre 5.0) los
                // pies y las manos quedaban 0.4-0.6 m corridos del piso y del ClimbGrip. Se corre el clip entero esa
                // diferencia y se la come a lo largo de los tirones: exacto en el PerchNode al llegar (f24)
                float grab = clip.AirEnd > 0f ? clip.AirEnd : Mathf.Max(0f, clip.Event("GrabStalk"));
                pos += up * ((ClimbAuthorPerch - perch.S.PerchHeight) * (1f - Mathf.InverseLerp(grab, 1f, ClipNorm)));
            }
            if (climbBlend > 0f)
            {
                // trepando desde el piso: del lugar donde está parado al eje del culmo, con la altura corregida (Climb está
                // autorado sobre la caña de adentro: los pies arrancan 4.4 m abajo del PerchNode)
                Vector3 start = new Vector3(climbFrom.x, (grove != null ? grove.FloorY : transform.position.y) + ClimbAuthorPerch, climbFrom.z);
                pos = Vector3.Lerp(pos, start, climbBlend);
            }
            Quaternion rot = perchYaw * Quaternion.AngleAxis(AimLean(node.position, dt), Vector3.right);
            // colgado de las corvas el cuerpo cuelga a plomo: con la caña arqueada 30° hacia Kaito el giro del tramo lo
            // dejaba torcido 30° de la vertical. Se lo endereza alrededor de las rodillas (siguen en el culmo)
            hangBlend = Mathf.MoveTowards(hangBlend, hanging ? 1f : 0f, dt / 0.2f);
            if (hangBlend > 0f && look.ShinL != null && look.ShinR != null)
            {
                Vector3 kneeLocal = model.InverseTransformPoint((look.ShinL.position + look.ShinR.position) * 0.5f);
                Vector3 kneeWorld = pos + rot * Vector3.Scale(kneeLocal, model.lossyScale);
                Vector3 f = (rot * Vector3.forward).Flat();
                Quaternion plumb = Quaternion.Slerp(rot, Quaternion.LookRotation(f.sqrMagnitude > 1e-4f ? f.normalized : Vector3.forward), hangBlend);
                pos = kneeWorld - plumb * Vector3.Scale(kneeLocal, model.lossyScale);
                rot = plumb;
            }
            model.SetPositionAndRotation(pos, rot);
        }

        float hangBlend;

        /// <summary>
        /// Los clips de cerbatana apuntan la flauta 35° hacia abajo al frente; el dardo va al pecho de Kaito (de lejos más
        /// tendido, de cerca más empinado). Mientras sopla, el cuerpo entero se inclina sobre los pies (gira alrededor del
        /// PerchNode, así las suelas no se despegan del nudo) lo que falta para que la flauta coincida con el tiro: hasta 20°
        /// hacia adelante y 12° hacia atrás. Fuera de los soplidos vuelve suave.
        /// </summary>
        float AimLean(Vector3 node, float dt)
        {
            float want = 0f;
            if (clip != null && aimClips.Contains(clip) && ClipNorm >= clip.TellStart)
            {
                Vector3 to = TargetPos + Vector3.up * 0.9f - (node + Vector3.up * 1.3f);
                float down = Mathf.Atan2(-to.y, Mathf.Max(0.5f, to.Flat().magnitude)) * Mathf.Rad2Deg;
                want = Mathf.Clamp(down - 35f, -12f, 20f);
            }
            aimLean = Mathf.MoveTowards(aimLean, want, 60f * dt);
            return aimLean;
        }

        float aimLean;
        static readonly HashSet<ChikuoClip> aimClips = new HashSet<ChikuoClip>
        {
            ChikuoTimings.PerchDart, ChikuoTimings.PerchDart2, ChikuoTimings.PerchVolley, ChikuoTimings.PerchVolley4, ChikuoTimings.PerchWhistle,
        };

        float HeightAboveFloor => grove != null ? model.position.y - grove.FloorY : 0f;

        // ================================================================== cámara
        void UpdateCamera()
        {
            if (Game.Camera == null) return;
            if (!Fighting || !IsAlive) return;
            // arriba (posado, salto, pértiga): el foco sube con él (0.45 x la altura del posado), CameraDirector lo
            // amortigua. Sin esto, posado a 4 m solo entraba en cuadro con Kaito a 3 m al norte de su caña
            float h = Mathf.Clamp(HeightAboveFloor, 0f, 5.5f);
            if (h > 0.6f) lastPerchBias = 0.45f * h;
            // en las fases de arriba una bajada (un hueco, la picada) dura 1-3 s y vuelve a subir: la cámara se queda con el
            // 60 % del foco del posado en vez de bombear cada 5 s; recién la pelea del piso (GroundBrain) la baja del todo
            float bias = h > 0.6f ? 0.45f * h : !groundAI && phaseIdx != 1 ? 0.6f * lastPerchBias : 0f;
            Game.Camera.SetFocusBias(Vector3.up * bias);
        }

        float lastPerchBias;

        void ClearCameraBias() => Game.Camera?.SetFocusBias(Vector3.zero);

        /// <summary>El anillo de sus golpes con aviso se cierra donde está el peligro (el disco de la picada, el carril a 3 m de
        /// su origen), no en la base de la caña: ahí está el ensō blanco que dice "cortá acá", y un anillo rojo encima decía lo
        /// contrario.</summary>
        public override Vector3 TellCenter
        {
            get
            {
                if (!heldStep || body == Body.Ground || heldAreaSize <= 0f) return base.TellCenter;
                return heldAreaLane ? heldAreaOrigin + heldAreaDir * Mathf.Min(3f, heldAreaSize * 0.5f) : heldAreaOrigin;
            }
        }

        /// <summary>Las marcas de la UI (fijado, peligro) arriba de su cabeza, esté donde esté (no a 2.7 m de la base).</summary>
        public override Vector3 HeadPoint => look != null && look.Head != null && body != Body.Ground ? look.Head.position + Vector3.up * 0.45f : base.HeadPoint;

        /// <summary>En plena pelea se lo puede fijar siempre: casi todo lo hace en el estado Scripted de Enemy (lo coreografía el
        /// jefe), que para un enemigo común es "en una escena, no fijable".</summary>
        public override bool Targetable => IsAlive && gameObject.activeInHierarchy && (Fighting || State != EnemyState.Scripted);

        /// <summary>El imán y el fijado de Kaito apuntan a la base de su caña (la raíz); en el salto, a la caña de destino
        /// (el imán gira hacia ella: la caída del cielo se apunta sola).</summary>
        public override Vector3 HurtCenter(Vector3 from) => vuln == Vuln.Air && leapDest != null ? leapDest.Base : transform.position;

        /// <summary>Donde suena su voz y lo que hace con el cuerpo (la raíz está en el piso).</summary>
        Vector3 Voice => model != null ? model.position + Vector3.up * 1.2f : transform.position;

        // ================================================================== golpes de Kaito
        public override HitResult ReceiveHit(in DamageInfo info)
        {
            if (info.sourceFaction != Faction.Player || !IsAlive) return HitResult.Ignored;
            if (look == null || grove == null) return base.ReceiveHit(info);
            if (!Fighting) return HitResult.Ignored;
            LastHitTime = Time.time;
            Vector3 dir = CutDirection(info);
            switch (vuln)
            {
                case Vuln.Scene: return HitResult.Blocked;
                case Vuln.Loaded: return onPole ? PoleWhip(dir) : Whip(dir, info);
                case Vuln.Flute: return Detune(info);
                case Vuln.Climb: return Slip(info);
                case Vuln.Tickle: return Tickle(dir, info);
                case Vuln.Air: return SkyCatch(info);
                case Vuln.Crouch: return Trip(info);
                case Vuln.Open: return HoleHit(info);
                case Vuln.Neutral: return NeutralHit(info);
                case Vuln.Armor: return ArmorHit(info, dir);
                default: return Whiff(dir);
            }
        }

        /// <summary>El corte en la carga de su golpe: entra a x0.35 y el golpe sigue, pero se tiene que notar que entró (sin
        /// esto el filo lo atravesaba como un corte errado): un sacudón de cascabeles y un hit-stop chico.</summary>
        HitResult ArmorHit(in DamageInfo info, Vector3 dir)
        {
            var r = ApplyDamage(info, BambooMasterMoves.ArmorMul);
            if (r != HitResult.Hit) return r;
            Sfx("chime_jangle", "step_wood", Voice, 0.55f);
            look.Jangle(dir * 4f + Vector3.up);
            Game.Time?.HitStop(0.04f);
            return r;
        }

        /// <summary>
        /// Un corte que no vale ahora (levantándose, en la garrocha, en el aire): el filo pasa por las hojas de la capa y los
        /// cascabeles suenan sueltos, para que se lea "ahora no" y no un error del juego. Una vez cada 0.3 s.
        /// </summary>
        HitResult Whiff(Vector3 dir)
        {
            if (body != Body.Perch && Time.time - lastWhiff >= 0.3f)
            {
                lastWhiff = Time.time;
                Sfx("chime_jangle", "parry_whiff", Voice, 0.3f);
                look.Jangle(dir * 3f);
                BambooGrove.Leaves(Voice, 0.4f);
            }
            return HitResult.Ignored;
        }

        float lastWhiff = -9f;

        /// <summary>
        /// Para dónde lo despide el corte: la línea Kaito → base, en el plano. El Corte del Viento se resuelve cuando Kaito
        /// ya pasó (iaido): ahí vale para dónde corrió, no dónde quedó.
        /// </summary>
        Vector3 CutDirection(in DamageInfo info)
        {
            var src = info.source as Component;
            Vector3 d = info.direction;
            if (info.attackName == "Corte del Viento" && src != null) d = src.transform.forward;
            else if (src != null) d = (HurtCenter(src.transform.position) - src.transform.position);
            d = d.Flat();
            return d.sqrMagnitude > 1e-4f ? d.normalized : transform.forward.Flat().normalized;
        }

        /// <summary>
        /// Le entra daño ('mul' por el corte): nunca cruza el piso de la fase (el golpe que llega dispara la escena y lo que
        /// sobra no cuenta). Los huecos, la caída de un latigazo, el piso neutral y la armadura pasan por acá.
        /// </summary>
        HitResult ApplyDamage(in DamageInfo info, float mul) => ApplyDamage(info.damage * mul, info);

        HitResult ApplyDamage(float dmg, in DamageInfo info)
        {
            if (!IsAlive) return HitResult.Ignored;
            float floor = phaseIdx < 2 ? Gates[phaseIdx + 1] * config.maxHealth : 0f;
            dmg = Mathf.Min(Mathf.Max(0f, dmg), Mathf.Max(0f, Health - floor));
            Health -= dmg;
            LastHitTime = Time.time;
            flash?.Flash();
            look.Jangle(info.direction * 2f + Vector3.up);
            if (Health <= 0.001f)
            {
                Health = 0f;
                Die(info);
                return HitResult.Killed;
            }
            if (phaseIdx < 2 && Health <= floor + 0.5f) StartTransition(phaseIdx + 1);
            return HitResult.Hit;
        }

        /// <summary>El daño de la caída de un latigazo (al tocar el piso; se multiplica como un corte).</summary>
        void FallDamage(float amount)
        {
            if (amount <= 0f) return;
            var info = new DamageInfo { damage = amount, kind = AttackKind.Heavy, direction = transform.forward, sourceFaction = Faction.Player, source = Game.Player, attackName = "Caída" };
            ApplyDamage(amount, info);
        }

        protected override void OnDamaged(in DamageInfo info) { }   // sin la fase genérica de Boss: los pisos son de Gates

        // ================================================================== maquinaria de Enemy para los golpes con aviso
        protected override bool StepHeld => heldStep;

        static bool IsHeld(string special) =>
            special == BambooMasterMoves.Sweep || special == BambooMasterMoves.Whistle || special == BambooMasterMoves.Dive ||
            special == BambooMasterMoves.StaffDrop || special == BambooMasterMoves.Catapult || special == BambooMasterMoves.Tala ||
            special == BambooMasterMoves.PoleDive || special == BambooMasterMoves.Answer || special == BambooMasterMoves.Spin;

        /// <summary>Arranca un golpe con aviso de un solo paso (lo lleva la corrutina de la acción).</summary>
        bool StartMove(AttackDef a)
        {
            pattern = new AttackPattern { name = a.name, steps = new[] { a }, maxRange = 99f };
            StartAttack(false);
            return State == EnemyState.Attack;
        }

        protected override void OnStepStarted(AttackDef a)
        {
            base.OnStepStarted(a);
            heldStep = IsHeld(a.special);
            heldStruck = false;
            heldStrikeAt = -1f;
            heldTravel = 0f;
            heldAreaSize = 0f;   // cada golpe pone su zona (si no, quedaba la del anterior)
            travelDone = 0f;
            stepClip = ChikuoTimings.Get(a.state);
            if (heldStep) anim.SetSpeed(1f);   // BeginStep lo dejó en 0 (el reloj de Enemy arranca el frame que viene)
            if (a.special == BambooMasterMoves.Spin) BeginSpin(a);
            // el Soplo: su dardo ya cuenta para el anillo de los pies desde que arranca
            if (a.special == BambooMasterMoves.Soplo && stepClip != null)
                pending.Add(new PendingDart { at = Time.time + tl.TimeAt(Mathf.Max(0f, stepClip.EventAt("DartSpawn", 0))) });
        }

        ChikuoClip stepClip;
        float travelDone;

        protected override float PlanWindup(AttackDef a, float windup) => IsHeld(a.special) ? a.windup : windup;

        protected override bool StepHasTell(AttackDef a) =>
            a.special != BambooMasterMoves.Answer && a.special != BambooMasterMoves.Soplo && base.StepHasTell(a);

        protected override float ComputeStrikeEta(AttackDef a)
        {
            if (!heldStep) return base.ComputeStrikeEta(a);
            if (heldStruck) return float.PositiveInfinity;
            if (a.special == BambooMasterMoves.Spin) return SpinEta();
            if (a.special == BambooMasterMoves.Whistle && whistleDart != null) return whistleDart.EtaTo(TargetPos);
            if (heldStrikeAt < 0f) return float.PositiveInfinity;
            return RealUntil(heldStrikeAt) + heldTravel;
        }

        protected override bool HitAreaFor(AttackDef a, out TellArea area)
        {
            switch (a.special)
            {
                case BambooMasterMoves.Sweep:
                case BambooMasterMoves.Dive:
                case BambooMasterMoves.PoleDive:
                case BambooMasterMoves.Whistle:
                case BambooMasterMoves.Catapult:
                case BambooMasterMoves.Tala:
                // el bastón que cae: el disco de donde cae (la raíz sigue en la base de la caña hasta que toca el piso, y
                // el bot medía el alcance desde ahí: nunca lo paraba)
                case BambooMasterMoves.StaffDrop:
                    area = new TellArea { lane = heldAreaLane, origin = heldAreaOrigin, forward = heldAreaDir, size = heldAreaSize, width = heldAreaWidth };
                    return heldAreaSize > 0f;
                case BambooMasterMoves.LowSweep:
                    area = new TellArea { origin = transform.position, size = a.specialParam };
                    return true;
                case BambooMasterMoves.Answer:
                    return NextSproutArea(out area);
            }
            return base.HitAreaFor(a, out area);
        }

        protected override void TickSpecial(AttackDef a, float dt)
        {
            if (a.special == BambooMasterMoves.Spin) { TickSpin(a, dt); return; }
            if (heldStep) return;   // lo coreografía la corrutina de la acción
            switch (a.special)
            {
                case BambooMasterMoves.Strike: GroundTravel(a); base.TickSpecial(a, dt); break;
                case BambooMasterMoves.LowSweep: TickLowSweep(a); break;
                case BambooMasterMoves.Soplo: TickSoplo(a); break;
                default: base.TickSpecial(a, dt); break;
            }
        }

        /// <summary>Termina el golpe de la acción (sin pasar por la guardia de Enemy): queda en manos de la corrutina.</summary>
        void EndMove(TellOutcome outcome)
        {
            if (State != EnemyState.Attack) { heldStep = false; return; }
            EndTell(outcome);
            ReleaseToken();
            pattern = null;
            heldStep = false;
            look.ClearTell();
            look.StopLimbTrail();
            SetState(groundAI ? EnemyState.Chase : EnemyState.Scripted);
            if (groundAI) nextAttackTime = Time.time + Random.Range(BambooMasterMoves.Breath[1].x, BambooMasterMoves.Breath[1].y);
        }

        protected override void ComboEnd()
        {
            ReleaseToken();
            pattern = null;
            heldStep = false;
            look.ClearTell();
            look.StopLimbTrail();
            if (groundAI)
            {
                // sin guardia: entre tandas respira 0.35-0.6 s y vuelve (Enemy.ComboEnd lo metía en la guardia)
                nextAttackTime = Time.time + Random.Range(BambooMasterMoves.Breath[1].x, BambooMasterMoves.Breath[1].y);
                SetState(EnemyState.Chase);
            }
            else SetState(EnemyState.Scripted);
        }

        /// <summary>
        /// Kaito desvió un golpe del viejo. El último de una tanda (o el bastón que cae) lo deja abierto: la Contra (0.40 s y
        /// dos cortes; 0.60 s y tres después de uno perfecto). Los del medio y la Revancha no (noRecoil: la tanda sigue).
        /// </summary>
        public override void OnParried(bool perfect)
        {
            if (!IsAlive || look == null) { base.OnParried(perfect); return; }
            var a = CurrentAttack;
            // la Flauta Giratoria: el primero de sus dos golpes no abre (sigue el segundo, con su anillo)
            if (a != null && a.special == BambooMasterMoves.Spin && spinHit < 2) return;
            bool opens = State == EnemyState.Attack && a != null && !a.noRecoil;
            if (!opens) { base.OnParried(perfect); return; }
            EndTell(TellOutcome.Parried);
            trail?.Stop();
            Run(ContraRoutine(perfect));
        }

        // ================================================================== dardos: la ETA honesta y el "¡ya!"
        public override float ProjectileEta => projEta;
        public override Vector3 ProjectileFrom => projFrom;

        Vector3 TargetPos => target != null ? target.transform.position : (Game.Player != null ? Game.Player.transform.position : transform.position);

        /// <summary>Un dardo por salir del clip en curso (normalizado del sidecar): su ETA cuenta el soplido que falta más el
        /// vuelo. 'at' queda en Time.time (los de un clip que todavía no suena, colgado o la respuesta, se anotan igual).</summary>
        void QueueDart(float norm) => pending.Add(new PendingDart { at = Time.time + RealUntil(norm) });

        void UpdateProjectiles(float dt)
        {
            projEta = float.PositiveInfinity;
            if (!Fighting) return;   // el dardo del saludo de la presentación no avisa
            // el hit-stop local frena el soplido: los dardos por salir esperan lo mismo
            if (anim.Frozen) for (int i = 0; i < pending.Count; i++) { var x = pending[i]; x.at += dt; pending[i] = x; }
            var p = target;
            if (p == null || !p.IsAlive) return;
            Vector3 pp = p.transform.position;
            BambooDart next = null;
            int nextPending = -1;
            var list = BambooDart.Active;
            for (int i = 0; i < list.Count; i++)
            {
                var d = list[i];
                if (d == null || d.Owner != this || d.Heavy) continue;
                float eta = d.EtaTo(pp);
                if (eta < projEta) { projEta = eta; projFrom = d.Position; next = d; }
            }
            Vector3 muzzle = MuzzlePos;
            float speed = BambooMasterMoves.DartSpeed[phaseIdx];
            for (int i = 0; i < pending.Count; i++)
            {
                float eta = Mathf.Max(0f, pending[i].at - Time.time) + Mathf.Max(0f, Vector3.Distance(muzzle, pp + Vector3.up * 0.9f) - BambooMasterMoves.DartHitR) / speed;
                if (eta < projEta) { projEta = eta; projFrom = muzzle; next = null; nextPending = i; }
            }
            if (float.IsInfinity(projEta))
            {
                // el último dardo ya pegó o se clavó: los hombros se apagan (dorado = "viene un dardo"; PerchDart no tiene
                // Unload que lo apague, y quedaban encendidos 1-3 s mintiendo)
                if (dartGlow) { dartGlow = false; look.ClearTell(); }
                return;
            }
            bool cued = next != null ? next.cued : pending[nextPending].cued;
            if (!cued && AudioManager.CueDue(projEta, TellStyle.TickParryable))
            {
                if (next != null) next.cued = true; else { var x = pending[nextPending]; x.cued = true; pending[nextPending] = x; }
                Game.Audio?.Play("tell_tick", null, 0.8f, 0.03f);
                GameEvents.RaiseStrikeCue(this, false);
            }
            // los cascabeles de los hombros en dorado en el último tramo (el filo de los otros), y el destello del cierre
            if (projEta <= GlintLead) { look.Tell(BambooMasterLook.DartSlots, false, Mathf.InverseLerp(GlintLead, TellStyle.BiasParryable, projEta)); dartGlow = true; }
            bool glinted = next != null ? next.glinted : pending[nextPending].glinted;
            if (!glinted && projEta <= TellStyle.BiasParryable)
            {
                if (next != null) next.glinted = true; else { var x = pending[nextPending]; x.glinted = true; pending[nextPending] = x; }
                Game.FX?.BladeGlint(next != null ? next.Position : muzzle, false);
            }
        }

        Vector3 MuzzlePos => look != null && look.Muzzle != null ? look.Muzzle.position : Voice;

        /// <summary>Sopla el próximo dardo de la cola (el más viejo): desde la boca de la flauta hacia donde va a estar Kaito.</summary>
        void FireDart()
        {
            bool cued = false;
            if (pending.Count > 0) { cued = pending[0].cued; pending.RemoveAt(0); }
            var p = target;
            if (p == null || grove == null) return;
            Vector3 from = MuzzlePos;
            float speed = BambooMasterMoves.DartSpeed[phaseIdx];
            Vector3 aim = p.transform.position + Vector3.up * 0.9f;
            float t = Vector3.Distance(from, aim) / speed;
            aim += p.Velocity.Flat() * (BambooMasterMoves.DartLead[phaseIdx] * t);
            var d = BambooDart.Spawn(this, from, aim - from, speed, BambooMasterMoves.Dmg(BambooMasterMoves.Move.Dart, phaseIdx), false, grove.FloorY, cued);
            d.cued = cued;
            Game.FX?.Dust(from, 0.25f);
        }

        /// <summary>Un dardo suyo le pegó a Kaito: a veces se ríe (y la risa es cargada: la revancha de Kaito).</summary>
        public void OnDartHit(bool heavy)
        {
            dartHitPending = true;
            if (fluting) qaFailed = true;
        }

        // ================================================================== la carga (campanas blancas)
        /// <summary>Carga 'stalk' hasta 'seconds' desde ahora (las campanas no mienten: no se cancela salvo por el latigazo,
        /// la muerte de Kaito o el cambio de fase).</summary>
        void Load(BambooStalk stalk, float seconds)
        {
            if (stalk == null) return;
            if (loadedStalk != null && loadedStalk != stalk) loadedStalk.SetLoaded(false);
            loadedStalk = stalk;
            loadUntil = Time.time + seconds;
            loadCut = false;
            stalk.SetLoaded(true, seconds);
            look.Loaded = true;
            Sfx("tell_chime_shimmer", "parry_ready", Voice, 0.5f);
            if (Teach("whip")) ShowTip(StoryText.Hint("bamboo_whip"));
            if (vuln != Vuln.Climb) vuln = Vuln.Loaded;
        }

        /// <summary>La carga se apaga sin corte (o con él): cuenta para la Risa del Maestro.</summary>
        void Unload()
        {
            if (loadedStalk == null) return;
            loadedStalk.SetLoaded(false);
            loadedStalk = null;
            look.Loaded = false;
            if (!loadCut) loadsUncut++;
            if (vuln == Vuln.Loaded || vuln == Vuln.Climb) vuln = body == Body.Perch ? Vuln.Tickle : Vuln.None;
        }

        void UpdateLoad(float dt)
        {
            // el hit-stop local frena el clip (y su Unload): la carga espera lo mismo, si no el corte que el clip dice
            // latigazo salía "¡Cosquillas!" después de un parry a un dardo de la ráfaga
            if (anim.Frozen && (loadedStalk != null || onPole)) loadUntil += dt;
            if (loadedStalk != null && Time.time > loadUntil + 0.05f) Unload();
            grove?.TickAim(loadedStalk, TargetPos, phaseIdx, dt);
        }

        /// <summary>El miembro (o los cascabeles) del golpe con aviso en curso se enciende en su último tramo: dorado = parry,
        /// rojo = dash (el filo de Enemy, que Chikuō no tiene: la flauta, los pies y los cascabeles hacen de filo).</summary>
        void TickHeldGlow()
        {
            if (!heldStep || State != EnemyState.Attack || heldSlots == null) return;
            var a = CurrentAttack;
            if (a == null) return;
            float eta = StrikeEta;
            if (float.IsInfinity(eta) || eta > GlintLead) return;
            look.Tell(heldSlots, a.kind == AttackKind.Unblockable, Mathf.InverseLerp(GlintLead, a.TellBias, eta));
        }

        /// <summary>Lo que Enemy no sabe: en el piso de la fase 2 el corte en neutral le entra a x0.6 y en la carga de su
        /// golpe, x0.35 (la armadura).</summary>
        void UpdateVulnFromState()
        {
            if (!groundAI) return;
            if (State == EnemyState.Attack) vuln = Vuln.Armor;
            else if (State == EnemyState.Chase || State == EnemyState.Strafe) vuln = Vuln.Neutral;
        }

        // ================================================================== el bot (Input/AutoPilot.cs)
        public Vector3 BotTarget
        {
            get
            {
                if (vuln == Vuln.Air && leapFrom != null) return leapFrom.Base;
                return transform.position;
            }
        }

        public bool BotMayCut => vuln == Vuln.Open || vuln == Vuln.Neutral || vuln == Vuln.Armor || vuln == Vuln.Crouch ||
                                 vuln == Vuln.Loaded || vuln == Vuln.Climb || (vuln == Vuln.Air && leapCatchable);

        public bool BotCutGoal(out Vector3 goal, out float until, out bool fall)
        {
            fall = false;
            if (loadedStalk != null && (vuln == Vuln.Loaded || vuln == Vuln.Climb))
            {
                goal = loadedStalk.Base;
                until = loadUntil;
                return true;
            }
            // la Grulla en el Bastón: su bastón también es una caña
            if (onPole && vuln == Vuln.Loaded)
            {
                goal = transform.position;
                until = loadUntil;
                return true;
            }
            if (vuln == Vuln.Air && leapDest != null && leapGrabAt > Time.time && (leapDest.Base - TargetPos).Flat().magnitude <= BambooMasterMoves.BotCatchDist)
            {
                goal = leapDest.Base;
                until = leapGrabAt;
                fall = true;
                return true;
            }
            goal = transform.position;
            until = 0f;
            return false;
        }

        // ================================================================== ayudas
        void Run(IEnumerator routine)
        {
            if (act != null) StopCoroutine(act);
            act = null;
            ClearActionState();
            if (IsAlive) act = StartCoroutine(routine);
        }

        /// <summary>Lo que una acción cortada deja colgado: la carga, el golpe con aviso, los dardos por salir, la marca del
        /// destino, el tramo lento del clip.</summary>
        void ClearActionState()
        {
            if (State == EnemyState.Attack) EndMove(TellOutcome.Cancelled);
            // la acción nueva arranca en manos del jefe (el piso de la fase 2 vuelve a Enemy en EnterGroundAI)
            if (IsAlive && State != EnemyState.Scripted) SetState(EnemyState.Scripted);
            heldStep = false;
            Unload();
            pending.Clear();
            if (leapDest != null) leapDest.Mark(false);
            leapDest = leapFrom = null;
            leapGrabAt = -1f;
            leapCatchable = false;
            perchFaceLock = false;
            climbBlend = 0f;
            slowFrom = slowTo = -1f;
            groundAI = false;
            whistleDart = null;
            onPole = false;
            grove?.SetPoleEnso(false, transform.position);
            look?.ClearTell();
            look?.StopLimbTrail();
            trail?.Stop();
            ClearSprouts();
        }

        bool groundAI;

        void Bark(string beat, bool always = false)
        {
            if (!always && (said.Contains(beat) || Time.time - lastBark < BarkGap)) return;
            string line = StoryText.ChikuoLine(beat);
            if (string.IsNullOrEmpty(line)) return;
            said.Add(beat);
            lastBark = Time.time;
            Game.UI?.ShowBark(StoryText.Chikuo, line, BarkColor, 3.2f);
        }

        /// <summary>¿Es la primera vez de esta lección en la pelea? (las pistas salen una vez cada una)</summary>
        bool Teach(string key) => said.Add("tip_" + key);

        void ShowTip(string text)
        {
            if (string.IsNullOrEmpty(text)) return;
            Game.UI?.ShowTutorial(text);
            tipHideAt = Time.unscaledTime + TipSeconds;
        }

        /// <summary>
        /// Un sonido de la pelea (Tools/Audio/sfx_chikuo.py); si la clave no está en NindoContent, la de respaldo. Los
        /// cascabeles y la flauta están afinados a la pentatónica del tema: sin variación de altura, y en la fase 3 (el
        /// tema sube medio tono) su versión '_p3'.
        /// </summary>
        void Sfx(string key, string fallback, Vector3 pos, float volume = 1f)
        {
            var content = Game.LoadContent();
            bool tonal = key.StartsWith("tell_chime") || key.StartsWith("chime") || key.StartsWith("flute_n");
            if (tonal && phaseIdx >= 2 && content != null && content.Sfx(key + "_p3") != null) key += "_p3";
            else if (content != null && content.Sfx(key) == null) key = fallback;
            if (!string.IsNullOrEmpty(key)) Game.Audio?.Play(key, pos, volume, tonal ? 0f : 0.06f);
        }

        static string PhaseSubtitle(int phase) => phase <= 0 ? null : phase == 1 ? "El Baile de la Flauta" : "Todo el Bosque Canta";

        static readonly System.Globalization.CultureInfo Inv = System.Globalization.CultureInfo.InvariantCulture;

        void Log(string what) => Debug.Log("[Nindo] Chikuō: " + what);
    }
}
