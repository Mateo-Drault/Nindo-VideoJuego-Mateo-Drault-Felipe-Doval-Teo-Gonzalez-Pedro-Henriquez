using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Kage, la sombra viva de Kokuyō: un segundo atacante hecho de tinta en los tres actos. Es un Enemy sin modelo
    /// propio (lo que se ve es el doble de PlanarShadow) para que sus golpes hablen el idioma de todos: anillo en el
    /// suelo (dorado = parry, rojo con zona = dash), hyōshigi a 0.38 / 0.42 s y el "¡ahora!" a 0.36 s, que en la sombra
    /// es un destello dorado de la tinta. CUÁNDO ataca lo decide Kokuyō (KokuyoBoss.Shadow: turnos, dúos y la regla de
    /// KokuyoDuet); acá está el CÓMO:
    ///  * Acto 1, pegada a sus pies (Bound): Kage-nobi. Él se queda quieto y su sombra gira por el piso hacia Kaito, se
    ///    estira, levanta la hoja y corta. El anillo dorado se cierra a los pies de Kaito y se traba en el "¡ahora!".
    ///  * Acto 2, suelta (Loose): una figura de humo de tinta que ronda a Kaito. Kage-giri (corta como él, dorado),
    ///    Kage-nui (se acuesta, se desliza bajo Kaito y estalla en agujas, rojo) y Kage-watari (cruza el patio, rojo).
    ///  * Acto 3, a oscuras (Hidden): sin luna no se ve. Para atacar sale de la oscuridad 1.05 s antes del golpe
    ///    (destello violeta, susurro, la bandana late) y corta: Kage-giri, dorado. Después vuelve a la oscuridad.
    /// La katana la atraviesa. Una habilidad (Corte del Viento, Torbellino) la CLAVA 6 s y le suma 2 de postura al
    /// cuerpo; desviarla le suma la postura de un parry (y puede tirarlo de rodillas).
    /// </summary>
    public class KageShadow : Enemy
    {
        public enum Shape { Bound, Loose, Hidden }

        KokuyoBoss owner;
        PlanarShadow ink;
        KokuyoHazards hazards;
        KokuyoMoves.ShadowSet moves;
        int act = 1;

        enum Mode { Hunt, Stalk, LineUp, Pinned, Recall }
        Mode mode = Mode.Hunt;
        float pinnedUntil, lastGhostHit = -9f, recallT;
        Vector3 lineUp, laneOrigin, laneDir, lockPos, recallFrom;
        Quaternion recallRot;
        bool locked, erupted, crossing, crossHit;
        float lockTime, slideTime;
        // Nui: cuánto se desliza como mucho y cuándo estalla (fijo desde que arranca: la regla del dúo se midió contra eso)
        float nuiSlide, nuiEruptAt, eruptedAt;
        int sideSign = 1;
        AttackPattern nui, watari;
        // golpe planeado (Stalk): cuándo pega, cuándo arranca su paso y desde qué lado de Kaito
        string stalkMove;
        float plannedImpactAt = -1f, stepAt, emergeAt;
        Vector3 attackDir;
        // golpe en curso
        bool goFired, parried;
        float travelDone;
        // Nobi: el punto trabado, y cuánto está girada / estirada la sombra hacia él (0 = su sombra de siempre)
        Vector3 nobiPoint, nobiDir;
        float nobiW, nobiWTarget, retractTime = NobiRetractTime;
        // la tinta vuelve a copiar al cuerpo: pendiente (cuando termine de volver a sus pies) y fundiéndose
        bool mirrorPending, handingBack;
        // pose al terminar un golpe (la figura vuelve a la guardia antes de rondar)
        string settleState;
        float settleLeft, settleDur;
        // a oscuras: si está afuera, cuándo vuelve a apagarse y cuánto antes del golpe sale (más la primera vez)
        bool emerged;
        float vanishAt = -1f, emergeLead = KokuyoMoves.EmergeLead;
        Light glow;
        Transform tipMark;
        LineRenderer edge;
        float edgeAt = -99f;

        public const float SlideSpeed = 9f, NuiHold = 0.8f, NuiRadius = 2.2f, SlideMax = 1.0f;
        public const float CrossSpeed = 24f, CrossLength = 16f, CrossHalfWidth = 1.2f, LineUpDistance = 8f;
        const float GlideSpeed = 7f, StalkSpeed = 9f, HuntDistance = 6.5f, PinTime = 6f;
        /// <summary>El hueco de la bandana alrededor de Kaito (PlanarShadow.HoleRadius) y el que deja el Nobi: chico,
        /// para que la hoja de tinta se vea llegar a sus pies.</summary>
        const float HoleDefault = 1.1f, HoleNobi = 0.45f;
        /// <summary>
        /// Nobi: la sombra se estira hasta que su cabeza cae esto antes de Kaito. Así la silueta llega hasta él y, con la
        /// hoja de Kesagiri en el impacto (cuadro 18: 3.5 m adelante, 3.8 m arriba), la sombra de la hoja le pasa a 0.1 m
        /// (medido proyectando Kokuyo.fbx con la cuenta de Nindo/ShadowInk, a 6.4 y 6.9 m de él).
        /// </summary>
        const float NobiHeadShort = 1f, NobiMinStretch = 0.3f;
        const float NobiAimTime = 0.35f, NobiRetractTime = 0.45f, NobiSnapTime = 0.22f;
        /// <summary>Color del pulso del "¡ahora!" de la sombra (el shader lo multiplica por 2.6: dorado vivo).</summary>
        static readonly Color GoldFlash = new Color(0.42f, 0.31f, 0.1f);
        static readonly Color GlowColor = new Color(0.62f, 0.4f, 1f);
        /// <summary>
        /// A oscuras el filo violeta de la figura brilla más (pasa el umbral del bloom) y la ilumina su luz propia. Con
        /// 1.4 y 1.6 la figura era violeta oscuro sobre piso violeta oscuro: en el render del eclipse desde la cámara del
        /// juego solo se leía el anillo dorado, no la figura con la hoja levantada (la pose del aviso). Con 2.5 y 3 el
        /// contorno entero se recorta contra el piso; la hoja, que es fina, se lee por su filo y por el destello de la
        /// punta en el "¡ahora!".
        /// </summary>
        const float DarkRim = 2.5f, DarkGlow = 3f;
        /// <summary>
        /// Al salir de la oscuridad la hoja levantada es lo que hay que leer (la pose del aviso del corte), y con el filo de
        /// 2.5 seguía siendo una raya fina hasta el destello de la punta: un trazo violeta claro a lo largo de la hoja, de
        /// 0.12 m (~10 px con la cámara de juego), los primeros EdgeHold s del adelanto, y se apaga en EdgeFade s.
        /// </summary>
        const float EdgeWidth = 0.12f, EdgeHold = 0.4f, EdgeFade = 0.2f;
        static readonly Color EdgeColor = new Color(0.82f, 0.68f, 1f);

        public Shape Form { get; private set; } = Shape.Bound;
        public bool Pinned => mode == Mode.Pinned;
        /// <summary>Atacando, con un golpe planeado o alineándose para cruzar: el cuerpo no le pisa el turno.</summary>
        public bool Busy => State == EnemyState.Attack || State == EnemyState.Recoil || mode == Mode.LineUp || mode == Mode.Stalk;
        /// <summary>Lista para recibir un golpe nuevo de Kokuyō. A oscuras, recién cuando terminó de apagarse: si salía
        /// otra vez a medio fundir (dos cortes seguidos, la segunda salida del eclipse) la figura todavía visible saltaba
        /// de un lado de Kaito al otro.</summary>
        public bool CanStrike => IsAlive && owner != null && ink != null && mode == Mode.Hunt && !Busy && !mirrorPending
                                 && nobiW <= 0f && settleLeft <= 0f
                                 && !(Form == Shape.Hidden && (!ink.Detached || emerged || vanishAt > 0f || ink.Visibility > 0.02f));
        /// <summary>Pegada a sus pies y con la tinta ocupada en un golpe propio: el adelanto del Acto 1 espera.</summary>
        public bool DrivesInk => Form == Shape.Bound && ink != null
                                 && (State == EnemyState.Attack || State == EnemyState.Recoil || nobiW > 0f || mirrorPending || handingBack);
        /// <summary>El cuerpo de Kokuyō no se mueve ni arranca un golpe mientras su sombra pegada ataca y vuelve a sus
        /// pies (se ve que la que pelea es ella, y el adelanto del Acto 1 vuelve entero para el golpe siguiente).</summary>
        public bool HoldsBody => DrivesInk;
        /// <summary>Cuándo pega el golpe en camino o planeado (Time.time; -1 = ninguno).</summary>
        public float PendingImpactAt
        {
            get
            {
                if (State == EnemyState.Attack) { float e = StrikeEta; return float.IsInfinity(e) ? -1f : Time.time + e; }
                return mode == Mode.Stalk || mode == Mode.LineUp ? plannedImpactAt : -1f;
            }
        }
        public AttackKind PendingKind => State == EnemyState.Attack ? StepKind
                                         : stalkMove == KokuyoMoves.Nui || stalkMove == KokuyoMoves.Watari ? AttackKind.Unblockable : AttackKind.Heavy;
        /// <summary>Qué golpe es (KokuyoMoves.Nobi, Giri...): después del Nobi el cuerpo espera más (el adelanto vuelve).</summary>
        public string PendingMove => State == EnemyState.Attack && CurrentAttack != null ? CurrentAttack.special
                                     : mode == Mode.Stalk || mode == Mode.LineUp ? stalkMove : "";
        /// <summary>Sus cortes salen de la oscuridad (eclipse): se ven EmergeLeadNow antes del golpe.</summary>
        public bool FromDark => Form == Shape.Hidden;
        /// <summary>Cuánto antes de su corte sale de la oscuridad el golpe planeado (EmergeLead, más la primera vez).</summary>
        public float EmergeLeadNow => emergeLead;
        public override bool Targetable => false;
        public override int CurrentPhase => owner != null ? owner.CurrentPhase : 0;

        public static KageShadow Spawn(KokuyoBoss owner, PlanarShadow ink, KokuyoHazards hazards)
        {
            var go = new GameObject("Kage");
            int layer = LayerMask.NameToLayer("Enemy");
            if (layer >= 0) go.layer = layer;
            go.transform.SetPositionAndRotation(owner.transform.position, owner.transform.rotation);
            var k = go.AddComponent<KageShadow>();
            k.config = KokuyoMoves.Shadow();
            k.owner = owner;
            k.ink = ink;
            k.hazards = hazards;
            k.nui = k.config.patterns[0];
            k.watari = k.config.patterns[1];
            k.SetAct(1);
            return k;
        }

        protected override void Start()
        {
            base.Start();
            target = Game.Player;
            // el brillo del "¡ahora!" (Enemy.TickTell) va en la punta de la hoja de tinta: la del aire si está parada,
            // la del piso si está acostada (sin esto salía a 2.3 m de altura sobre Kaito)
            tipMark = new GameObject("PuntaDeSombra").transform;
            tipMark.SetParent(transform, false);
            katanaTip = tipMark;
            var lg = new GameObject("BrilloDeSombra");
            lg.transform.SetParent(transform, false);
            lg.transform.localPosition = new Vector3(0f, 1.6f, 0f);
            glow = lg.AddComponent<Light>();
            glow.type = LightType.Point; glow.color = GlowColor; glow.range = 4.5f; glow.intensity = 0f;
            glow.shadows = LightShadows.None; glow.enabled = false;
            var eg = new GameObject("FiloDeTinta");
            eg.transform.SetParent(transform, false);
            edge = eg.AddComponent<LineRenderer>();
            edge.useWorldSpace = true;
            edge.positionCount = 2;
            edge.alignment = LineAlignment.View;
            edge.numCapVertices = 2;
            edge.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            edge.receiveShadows = false;
            edge.sharedMaterial = FXMaterials.Additive;
            edge.widthMultiplier = EdgeWidth;
            edge.enabled = false;
        }

        /// <summary>Los golpes del acto (las pausas en el apex son las del cuerpo).</summary>
        public void SetAct(int a)
        {
            act = Mathf.Clamp(a, 1, 3);
            moves = new KokuyoMoves.ShadowSet(act);
        }

        // ================================================================== API de Kokuyō
        /// <summary>
        /// Arranca un golpe de la sombra (Nobi, Giri, Nui o Watari) desde 'side'. Devuelve false si en esta forma o a
        /// esta distancia no puede. El momento del golpe lo ajusta Kokuyō (nunca pegado al suyo). 'leadMul' estira la
        /// carga del Nobi y la salida de la oscuridad (la primera vez que se enseñan).
        /// </summary>
        public bool TryStrike(string move, ShadowSide side, float leadMul)
        {
            if (!CanStrike || target == null || !target.IsAlive) return false;
            Vector3 kp = target.transform.position;
            switch (move)
            {
                case KokuyoMoves.Nobi:
                {
                    // desde cualquier distancia a tiro: pegado a él (donde pelean el bot y casi todos) la sombra se
                    // estira poco y la hoja de tinta le barre por encima (UpdateNobiInk)
                    if (Form != Shape.Bound) return false;
                    if (CombatMath.FlatDistance(owner.transform.position, kp) > KokuyoMoves.NobiMaxRange) return false;
                    BeginNobi(leadMul);
                    return State == EnemyState.Attack;
                }
                case KokuyoMoves.Giri:
                {
                    if (Form == Shape.Bound) return false;
                    attackDir = PickDir(side);
                    float natural = StepTimeline.MinWindup(moves.giri, false, false, CurrentPhase, 1f);
                    // suelta: el tiempo de llegar a su lugar; a oscuras: se ve al menos emergeLead antes del golpe (la
                    // regla del dúo se mide con este mismo número: se fija antes de planear)
                    emergeLead = KokuyoMoves.EmergeLead * Mathf.Max(1f, leadMul);
                    float pre = Form == Shape.Hidden
                        ? Mathf.Max(0f, emergeLead - natural)
                        : Mathf.Max(0f, CombatMath.FlatDistance(transform.position, StalkSpot()) / StalkSpeed + 0.25f - natural);
                    Plan(KokuyoMoves.Giri, natural, pre, moves.giri.kind);
                    emergeAt = plannedImpactAt - Mathf.Max(emergeLead, natural);
                    return true;
                }
                case KokuyoMoves.Nui:
                {
                    if (Form != Shape.Loose || CombatMath.FlatDistance(transform.position, kp) > SlideSpeed * SlideMax + 2f) return false;
                    Plan(KokuyoMoves.Nui, NuiSlide() + NuiHold, 0f, AttackKind.Unblockable);
                    if (stepAt <= Time.time + 0.02f) BeginNui();
                    return true;
                }
                case KokuyoMoves.Watari:
                    if (Form != Shape.Loose || !TryLineUp(kp, out lineUp)) return false;
                    // lo que tarda en alinearse, apuntar y cruzar hasta Kaito: él lo respeta como un golpe planeado
                    stalkMove = KokuyoMoves.Watari;
                    plannedImpactAt = owner.EarliestShadowImpact(Time.time + CombatMath.FlatDistance(transform.position, lineUp) / (GlideSpeed * 1.4f)
                                                                 + watari.steps[0].windup + LineUpDistance / CrossSpeed, AttackKind.Unblockable);
                    mode = Mode.LineUp;
                    return true;
            }
            return false;
        }

        /// <summary>Golpe planeado: pega en lo antes posible que le deje Kokuyō y su paso arranca 'natural' antes.</summary>
        void Plan(string move, float natural, float pre, AttackKind kind)
        {
            stalkMove = move;
            plannedImpactAt = owner.EarliestShadowImpact(Time.time + pre + natural, kind);
            stepAt = plannedImpactAt - natural;
            emerged = Form != Shape.Hidden;
            mode = Mode.Stalk;
        }

        /// <summary>
        /// Kokuyō cayó de rodillas o entra en una escena: suelta el golpe que estaba cargando (con 'force', aunque ya
        /// haya dado el "¡ahora!"). Lo planeado se cancela siempre.
        /// </summary>
        public void Abort(bool force)
        {
            if (mode == Mode.Stalk || mode == Mode.LineUp)
            {
                mode = Mode.Hunt;
                plannedImpactAt = -1f;
                hazards?.Puddle(Vector3.zero, 0f);
                if (Form == Shape.Hidden && emerged) Vanish(0.3f);
            }
            if (State != EnemyState.Attack || !force && StrikeEta <= KokuyoMoves.GoLead) return;
            SetState(EnemyState.Idle);   // el aviso se borra como cortado
            ReleaseStrikeReservation();
            hazards?.Puddle(Vector3.zero, 0f);
            crossing = false;
            AfterStrike(false);   // cortado a mitad de la carga: sin pose de cierre
        }

        /// <summary>1 → 2: Kokuyō la arrancó del piso (KageArenaFX ya la despegó y la paró): ahora caza suelta.</summary>
        public void Tear()
        {
            Abort(true);
            ResetInkAim();
            Form = Shape.Loose;
            SetAct(2);
            mode = Mode.Hunt;
            if (ink != null && ink.Root != null) transform.position = ink.Root.position.Flat() + Vector3.up * owner.transform.position.y;
        }

        /// <summary>2 → 3: sin luna no hay sombra que ver (KageArenaFX la apaga). Queda en la oscuridad y sale a atacar.</summary>
        public void Hide()
        {
            Abort(true);
            ResetInkAim();
            Form = Shape.Hidden;
            SetAct(3);
            mode = Mode.Hunt;
            emerged = false;
            vanishAt = -1f;
            if (ink != null && !ink.Detached && ink.Visibility < 0.01f) LieInTheDark();
        }

        // ------------------------------------------------------------------ recibir golpes
        /// <summary>Hay una figura que tocar: suelta, afuera de la oscuridad, o pegada pero cargando su corte.</summary>
        bool Exposed => Form == Shape.Loose || Form == Shape.Hidden && emerged
                        || Form == Shape.Bound && State == EnemyState.Attack && StrikeEta > KokuyoMoves.GoLead;

        public override HitResult ReceiveHit(in DamageInfo info)
        {
            if (!IsAlive || info.sourceFaction != Faction.Player || mode == Mode.Recall) return HitResult.Ignored;
            if (info.kind == AttackKind.Ability)
            {
                if (!Exposed || mode == Mode.Pinned) return HitResult.Ignored;
                Pin();
                return HitResult.Hit;
            }
            // pegada a sus pies o a oscuras no hay figura que atravesar: los cortes cerca de él no hacen ruido
            if (Form == Shape.Bound || Form == Shape.Hidden && !emerged) return HitResult.Ignored;
            // la katana pasa a través: un susurro y un salpicón de tinta (y la primera vez, la pista)
            if (Time.time - lastGhostHit > 0.35f)
            {
                lastGhostHit = Time.time;
                ink?.Strike(0.06f);
                owner?.OnShadowSlashed();
            }
            return HitResult.Ignored;
        }

        public override void OnParried(bool perfect)
        {
            bool striking = State == EnemyState.Attack;
            base.OnParried(perfect);   // retrocede (Recoil) y el anillo se rompe
            if (!striking) return;
            parried = true;
            Imbalance = 0f;   // la postura es de él (OnShadowParried): la de la sombra no se llena nunca
            ink?.Strike(0.3f);
            if (Form == Shape.Bound) Retract(NobiSnapTime);   // la tinta vuelve de golpe a sus pies
            owner?.OnShadowParried(perfect, transform.position);
        }

        void Pin()
        {
            if (State == EnemyState.Attack) SetState(EnemyState.Idle);   // corta el golpe (el aviso se borra como cortado)
            ReleaseStrikeReservation();
            mode = Mode.Pinned;
            pinnedUntil = Time.time + PinTime;
            plannedImpactAt = -1f;
            hazards?.Puddle(Vector3.zero, 0f);
            if (ink != null)
            {
                ink.Strike(0.3f);
                // pegada vuelve a sus pies (en el Acto 1 su sombra sigue siendo el aviso); suelta queda tenue; a oscuras se va
                if (Form == Shape.Bound) { Retract(NobiSnapTime); mirrorPending = true; }
                else
                {
                    ink.RiseTo(1f, 0.15f);
                    ink.FadeTo(Form == Shape.Hidden ? 0f : 0.45f, Form == Shape.Hidden ? 0.5f : 0.2f);
                }
            }
            if (Form == Shape.Hidden) { emerged = false; vanishAt = -1f; }
            Game.FX?.Shockwave(transform.position, 2.4f, new Color(1f, 0.8f, 0.35f));
            Game.FX?.FlashLight(transform.position + Vector3.up * 2f, new Color(1f, 0.85f, 0.45f), 5f, 9f, 0.3f);
            Game.Audio?.Play("seal", transform.position, 0.9f);
            owner?.OnShadowPinned();
        }

        void ReleaseStrikeReservation() => Game.Combat?.ReleaseStrike(this);

        // ------------------------------------------------------------------ ronda (estado Idle: el cerebro es propio)
        // si la agenda de golpes no le hace lugar, Enemy lo manda a perseguir como a un ninja: vuelve a su ronda
        protected override void TickChase(float dt) => SetState(EnemyState.Idle);
        protected override void TickStrafe(float dt) => SetState(EnemyState.Idle);

        protected override void TickIdle(float dt)
        {
            if (target == null || !target.IsAlive || owner == null) return;
            switch (mode)
            {
                case Mode.Pinned:
                    // clavada se queda donde la clavaron (pegada, con él)
                    if (Form == Shape.Bound) transform.position = owner.transform.position;
                    if (Time.time >= pinnedUntil)
                    {
                        mode = Mode.Hunt;
                        if (Form == Shape.Loose && ink != null) ink.FadeTo(1f, 0.4f);
                    }
                    break;
                case Mode.Recall:
                    TickRecall(dt);
                    break;
                case Mode.LineUp:
                    Glide(lineUp, GlideSpeed * 1.4f, dt);
                    FaceFlat(target.transform.position, dt);
                    if (CombatMath.FlatDistance(transform.position, lineUp) < 0.6f) BeginWatari();
                    break;
                case Mode.Stalk:
                    TickStalk(dt);
                    break;
                default:
                    Hunt(dt);
                    break;
            }
        }

        void Hunt(float dt)
        {
            Vector3 kp = target.transform.position;
            if (Form == Shape.Bound)
            {
                transform.position = owner.transform.position;
                return;
            }
            // ronda a un costado de Kaito en pantalla (un poco hacia arriba): el cuerpo suele estar arriba y la cámara
            // mira hacia allá; del lado opuesto al cuerpo quedaba debajo del cuadro y el segundo cazador no se veía
            Vector3 right = CameraRight();
            Vector3 up = Vector3.Cross(right, Vector3.up);
            Vector3 dest = ClampToArena(kp + (right * sideSign * 0.92f + up * 0.38f) * HuntDistance);
            // a oscuras no se ve: espera en su lugar (sale de ahí cuando ataca). Mientras se apaga después de un corte
            // sigue deslizándose: saltaba a su lugar de espera con la figura todavía visible
            if (Form == Shape.Hidden && !emerged && (ink == null || ink.Visibility <= 0.02f)) transform.position = dest;
            else Glide(dest, GlideSpeed, dt);
            FaceFlat(kp, dt);
        }

        void TickStalk(float dt)
        {
            Vector3 kp = target.transform.position;
            if (stalkMove == KokuyoMoves.Nui)
            {
                // hierve en su lugar hasta que le toca deslizarse
                hazards?.Boil(25f);
                FaceFlat(kp, dt);
                if (Time.time >= stepAt) BeginNui();
                return;
            }
            Vector3 spot = StalkSpot();
            if (Form == Shape.Hidden)
            {
                if (!emerged)
                {
                    transform.position = spot;
                    FaceFlat(kp, 100f);
                    if (Time.time >= emergeAt) Emerge();
                }
                else FaceFlat(kp, dt, 6f);
            }
            else
            {
                Glide(spot, StalkSpeed, dt);
                FaceFlat(kp, dt, 6f);
            }
            if (Time.time >= stepAt && (Form != Shape.Hidden || emerged)) StartGiri();
        }

        /// <summary>Dónde se para para cortar: a GiriDistance de Kaito, del lado elegido (adentro del patio).</summary>
        Vector3 StalkSpot() => target != null ? ClampToArena(target.transform.position + attackDir * KokuyoMoves.GiriDistance) : transform.position;

        /// <summary>
        /// El lado del ataque: derecha, izquierda o arriba de Kaito en pantalla (nunca del lado de la cámara: una figura de
        /// 4.5 m entre la cámara y Kaito lo taparía). Any/Flank: el más cercano a donde ya está; Opposite: el más lejos
        /// del cuerpo.
        /// </summary>
        Vector3 PickDir(ShadowSide side)
        {
            Vector3 kp = target.transform.position;
            Vector3 right = CameraRight();
            Vector3 up = Vector3.Cross(right, Vector3.up);
            Vector3 me = (transform.position - kp).Flat();
            Vector3 body = (owner.transform.position - kp).Flat();
            me = me.sqrMagnitude > 0.01f ? me.normalized : right;
            body = body.sqrMagnitude > 0.01f ? body.normalized : up;
            Vector3 best = Vector3.zero;
            float bestScore = float.NegativeInfinity;
            for (int i = 0; i < 3; i++)
            {
                if (i == 2 && side == ShadowSide.Flank) break;
                Vector3 c = i == 0 ? right : i == 1 ? -right : up;
                if (!owner.InArena(kp + c * KokuyoMoves.GiriDistance, 1.5f)) continue;
                float score = side == ShadowSide.Opposite ? -Vector3.Dot(c, body) : Vector3.Dot(c, me);
                if (score > bestScore) { bestScore = score; best = c; }
            }
            if (best.sqrMagnitude > 0.01f) return best;
            // contra el borde del patio en los tres lados: hacia el centro
            Vector3 toCenter = (owner.arenaCenter - kp).Flat();
            return toCenter.sqrMagnitude > 0.01f ? toCenter.normalized : up;
        }

        static Vector3 CameraRight()
        {
            Vector3 r = Game.Camera != null ? Game.Camera.transform.right.Flat().normalized : Vector3.right;
            return r.sqrMagnitude < 0.01f ? Vector3.right : r;
        }

        bool TryLineUp(Vector3 kp, out Vector3 p)
        {
            // al este o al oeste de Kaito (de costado en pantalla: nunca entra por arriba o por abajo del cuadro)
            Vector3 side = CameraRight();
            float pick = Vector3.Dot(transform.position - kp, side) >= 0f ? 1f : -1f;
            for (int i = 0; i < 2; i++, pick = -pick)
            {
                p = kp + side * pick * LineUpDistance;
                if (owner.InArena(p, 1f)) return true;
            }
            p = kp;
            return false;
        }

        // ------------------------------------------------------------------ salir de la oscuridad (Acto 3)
        void Emerge()
        {
            emerged = true;
            vanishAt = -1f;
            if (ink != null)
            {
                ink.Root.SetPositionAndRotation(transform.position, transform.rotation);
                ink.RiseTo(1f, 0f);
                ink.FadeTo(1f, 0.25f);
                ink.Strike(0.25f);   // salpicón y susurro: se oye de dónde sale
            }
            Game.FX?.FlashLight(transform.position + Vector3.up * 2f, GlowColor, 3.5f, 7f, 0.35f);
            Game.FX?.SmokePuff(transform.position + Vector3.up * 0.6f, 1.6f);
            edgeAt = Time.time;
            // "la cinta ve por vos": la bandana late cuando la sombra sale de la oscuridad
            if (Game.Player != null) BandanaGlow.Ensure(Game.Player)?.Pulse(BandanaGlow.Gold, 0.6f);
            owner?.OnShadowEmerged();
        }

        void Vanish(float seconds)
        {
            emerged = false;
            edgeAt = -99f;
            vanishAt = -1f;
            ink?.FadeTo(0f, seconds);
        }

        /// <summary>A oscuras la tinta queda parada y suelta, invisible, lista para salir donde haga falta.</summary>
        void LieInTheDark()
        {
            ink.Detach();
            ink.RiseTo(1f, 0f);
        }

        // ------------------------------------------------------------------ golpes
        void StartGiri()
        {
            mode = Mode.Hunt;
            plannedImpactAt = -1f;
            pattern = moves.giriP;
            StartAttack(false);
            emergeLead = KokuyoMoves.EmergeLead;   // ya salió: lo que sigue se mide con la salida de siempre
            // la agenda de golpes no le hizo lugar (Enemy lo mandó a rondar): afuera de la oscuridad no puede quedar la
            // figura parada y con su brillo, y el próximo plan la movería de golpe a otro lado
            if (State != EnemyState.Attack && Form == Shape.Hidden && emerged) Vanish(0.3f);
        }

        void BeginNobi(float leadMul)
        {
            mode = Mode.Hunt;
            nobiPoint = target.transform.position;
            nobiDir = (nobiPoint - owner.transform.position).Flat().normalized;
            pattern = moves.nobiP;
            // la primera vez carga más: el windup se lee al armar el paso (BeginStep) y vuelve enseguida al de siempre
            moves.nobi.windup = KokuyoMoves.NobiWindup * Mathf.Max(1f, leadMul);
            StartAttack(false);
            moves.nobi.windup = KokuyoMoves.NobiWindup;
            if (State != EnemyState.Attack) return;
            nobiWTarget = 1f;
            retractTime = NobiRetractTime;
            // la sombra despierta: se oye antes de que se mueva
            Game.Audio?.Play("kokuyo_whisper", owner.transform.position, 0.8f);
        }

        float NuiSlide() => Mathf.Min(SlideMax, Mathf.Max(0f, CombatMath.FlatDistance(transform.position, target.transform.position) - 0.5f) / SlideSpeed);

        /// <summary>
        /// Kage-nui: el estallido cae cuando se planeó (Kokuyō acomodó sus golpes contra esa hora). Si Kaito se alejó
        /// mientras la tinta hervía, se traba antes de llegar (correrse es una buena respuesta a un rojo); si se acercó,
        /// hierve más. Antes la hora dependía de lo que tardara en llegar y podía correrse hasta 0.7 s sobre el golpe
        /// siguiente de él (Clavo y Colmillo).
        /// </summary>
        void BeginNui()
        {
            float planned = plannedImpactAt;
            mode = Mode.Hunt;
            plannedImpactAt = -1f;
            pattern = nui;
            var a = nui.steps[0];
            nuiSlide = NuiSlide();
            if (planned > 0f) nuiSlide = Mathf.Clamp(planned - Time.time - NuiHold, 0f, nuiSlide);
            nuiEruptAt = Mathf.Max(Time.time + nuiSlide + NuiHold, planned);
            a.windup = nuiEruptAt - Time.time;
            locked = erupted = false;
            slideTime = 0f;
            StartAttack(false);
            // sin lugar en la agenda: el charco que hervía esperando se apaga (si no, quedaba un hervor sin golpe)
            if (State != EnemyState.Attack) { hazards?.Puddle(Vector3.zero, 0f); return; }
            if (ink != null) ink.RiseTo(0f, 0.25f);   // se acuesta: es tinta en el piso que corre hacia Kaito
            hazards?.Boil(25f);
            Game.Audio?.Play("kokuyo_whisper", transform.position, 1f);
        }

        void BeginWatari()
        {
            mode = Mode.Hunt;
            plannedImpactAt = -1f;
            pattern = watari;
            crossing = crossHit = false;
            StartAttack(false);
        }

        protected override float StepClipLength(AttackDef a)
        {
            var c = KokuyoMoves.ClipOf(a);
            return c != null ? c.Seconds : base.StepClipLength(a);
        }

        /// <summary>El windup lo acomoda Kokuyō (la regla del dúo). El del Nui es su hora de estallido entera: el 0.9 de
        /// MinWindup en los Actos 2 y 3 adelantaba el anillo rojo respecto del estallido real.</summary>
        protected override float PlanWindup(AttackDef a, float windup)
        {
            if (a.special == KokuyoMoves.Nui) windup = Mathf.Max(windup, nuiEruptAt - Time.time);
            return owner != null ? owner.ShadowWindup(a, windup) : windup;
        }

        protected override void OnStepStarted(AttackDef a)
        {
            base.OnStepStarted(a);
            // después de cada golpe ronda del otro costado (o del mismo): no se lo ve venir siempre igual
            sideSign = Random.value < 0.5f ? -1 : 1;
            goFired = parried = false;
            travelDone = 0f;
            settleLeft = 0f;
        }

        protected override float ComputeStrikeEta(AttackDef a)
        {
            if (target == null) return float.PositiveInfinity;
            switch (a.special)
            {
                case KokuyoMoves.Nui:
                    // a su hora (BeginNui), o más tarde si la agenda de golpes le estiró el paso
                    if (erupted) return float.PositiveInfinity;
                    return Mathf.Max(0f, Mathf.Max(nuiEruptAt - Time.time, tl.T - stepClock));
                case KokuyoMoves.Watari:
                {
                    if (crossHit) return float.PositiveInfinity;
                    Vector3 o = crossing ? laneOrigin : transform.position;
                    Vector3 dir = crossing ? laneDir : transform.forward.Flat().normalized;
                    Vector3 to = (target.transform.position - o).Flat();
                    float along = Vector3.Dot(to, dir);
                    float lateral = Mathf.Abs(Vector3.Dot(to, Vector3.Cross(Vector3.up, dir)));
                    float pre = Mathf.Max(0f, tl.T - stepClock);
                    if (crossing)
                    {
                        float done = (stepClock - tl.T) * CrossSpeed;
                        if (along < done - 0.5f || along > CrossLength || lateral > CrossHalfWidth + target.Radius) return float.PositiveInfinity;
                        return Mathf.Max(0f, along - done) / CrossSpeed;
                    }
                    return pre + Mathf.Max(0f, along) / CrossSpeed;
                }
            }
            return base.ComputeStrikeEta(a);
        }

        protected override bool HitAreaFor(AttackDef a, out TellArea area)
        {
            switch (a.special)
            {
                case KokuyoMoves.Nobi:
                    area = new TellArea { origin = nobiPoint, size = KokuyoMoves.NobiRadius };
                    return true;
                case KokuyoMoves.Nui:
                    area = new TellArea { origin = locked ? lockPos : transform.position, size = NuiRadius };
                    return true;
                case KokuyoMoves.Watari:
                    area = new TellArea
                    {
                        lane = true, origin = crossing ? laneOrigin : transform.position,
                        forward = crossing ? laneDir : transform.forward.Flat().normalized, size = CrossLength, width = CrossHalfWidth * 2f,
                    };
                    return true;
            }
            return base.HitAreaFor(a, out area);
        }

        protected override void TickSpecial(AttackDef a, float dt)
        {
            switch (a.special)
            {
                case KokuyoMoves.Nui: TickNui(a, dt); return;
                case KokuyoMoves.Watari: TickWatari(a, dt); return;
                case KokuyoMoves.Nobi: TickNobi(a, dt); return;
                case KokuyoMoves.Giri: TickGiri(a, dt); return;
            }
            base.TickSpecial(a, dt);
        }

        /// <summary>El "¡ahora!" de los cortes de la sombra (los dos se desvían): la tinta destella dorada y en el eclipse
        /// la bandana late en blanco.</summary>
        void Go(AttackDef a)
        {
            if (goFired || StrikeEta > KokuyoMoves.GoLead) return;
            goFired = true;
            ink?.Flash(GoldFlash, 0.16f);
            if (act >= 3 && Game.Player != null) Game.Player.GetComponent<BandanaGlow>()?.Pulse(Color.white, 0.8f);
        }

        /// <summary>
        /// Kage-nobi: el punto sigue a Kaito hasta el "¡ahora!" y ahí se traba. La luz de la sombra gira hacia él, la raíz
        /// se da vuelta y la silueta se estira hasta sus pies (UpdateNobiInk): en el impacto la sombra de la hoja le
        /// pasa por encima y después barre hacia el costado del cuerpo.
        /// </summary>
        void TickNobi(AttackDef a, float dt)
        {
            if (target != null && StrikeEta > KokuyoMoves.GoLead) nobiPoint = target.transform.position;
            transform.position = nobiPoint;
            Vector3 to = (nobiPoint - owner.transform.position).Flat();
            if (to.sqrMagnitude > 0.04f && StrikeEta > KokuyoMoves.GoLead) nobiDir = to.normalized;
            if (stepNorm > a.activeEnd && nobiWTarget > 0f) Retract(NobiRetractTime);
            Go(a);
            if (!specialFired && stepNorm >= a.activeStart)
            {
                specialFired = true;
                ink?.Strike(0.22f);
                Game.Camera?.Shake(0.25f);
            }
            if (stepHit || target == null || stepNorm < a.activeStart || stepNorm > a.activeEnd) return;
            if (CombatMath.FlatDistance(target.transform.position, nobiPoint) > KokuyoMoves.NobiRadius + target.Radius) return;
            stepHit = true;
            HitPlayer(a, owner.transform.position);   // viene de él: el parry lo enfrenta
        }

        void TickGiri(AttackDef a, float dt)
        {
            var c = KokuyoTimings.Kesagiri;
            bool beforeGo = StrikeEta > KokuyoMoves.GoLead;
            if (target != null && beforeGo) FaceFlat(target.transform.position, dt, 6f);
            // suelta: termina de llegar a su lugar mientras sube la hoja; desde la suelta, el avance del clip
            if (Form == Shape.Loose && stepClock < tl.ReleaseTime) Glide(StalkSpot(), StalkSpeed, dt);
            else Travel(c);
            Go(a);
            if (!specialFired && stepNorm >= a.activeStart)
            {
                specialFired = true;
                ink?.Strike(0.18f);
            }
            if (stepHit || target == null || stepNorm < a.activeStart || stepNorm > a.activeEnd) return;
            Vector3 tp = target.transform.position;
            if (Mathf.Abs(tp.y - transform.position.y) > 2.5f) return;
            if (!CombatMath.InArc(transform, tp, c.Reach + 0.3f, a.arc, target.Radius)) return;
            stepHit = true;
            HitPlayer(a, transform.position);
        }

        /// <summary>El avance del clip (travel_m) en el reloj del paso, sin atravesar a Kaito (como el cuerpo).</summary>
        void Travel(KokuyoClip c)
        {
            if (c.Travel == null || anim.Frozen) return;
            float x = c.TravelAt(stepNorm);
            float d = x - travelDone;
            travelDone = x;
            if (d <= 0f) return;
            float room = d;
            if (target != null)
            {
                Vector3 to = (target.transform.position - transform.position).Flat();
                float along = Vector3.Dot(to, transform.forward), lat = Mathf.Abs(Vector3.Dot(to, transform.right));
                if (along > 0f && lat < Radius + target.Radius) room = along - Radius - target.Radius - 0.25f;
            }
            if (room > 0f) MoveBy(transform.forward * Mathf.Min(d, room));
        }

        void TickNui(AttackDef a, float dt)
        {
            if (!erupted)
            {
                // el reloj del paso espera en el golpe hasta que estalla (con el hit-stop el estallido también espera)
                if (stepClock > tl.T) { stepClock = tl.T; stepNorm = tl.NormAt(stepClock); }
                if (!locked)
                {
                    slideTime += dt;
                    Vector3 kp = target.transform.position;
                    Glide(kp, SlideSpeed, dt);
                    hazards?.Puddle(transform.position, 1.6f);
                    // la zona se traba al llegar (o si Kaito corre más que la tinta): desde acá al menos 0.8 s para salir
                    if (CombatMath.FlatDistance(transform.position, kp) <= 0.5f || slideTime >= nuiSlide)
                    {
                        locked = true;
                        lockTime = Time.time;
                        lockPos = transform.position;
                        hazards?.Boil(60f);
                        Game.Audio?.Play("tell_danger", lockPos, 0.8f, 0.03f);
                    }
                }
                else
                {
                    float eta = ComputeStrikeEta(a);
                    hazards?.Puddle(lockPos, 1.6f + 0.6f * (1f - Mathf.Clamp01(eta / NuiHold)));
                    if (eta <= 0f) Erupt(a);
                }
            }
            if (ink != null) ink.SampleAhead(KokuyoTimings.ShadowEmerge.State, erupted ? Mathf.Min(KokuyoTimings.ShadowEmerge.Contact + (Time.time - eruptedAt) * 0.9f, 1f) : 0.15f);
        }

        void Erupt(AttackDef a)
        {
            erupted = true;
            eruptedAt = Time.time;
            stepClock = tl.T;
            stepNorm = tl.NormAt(stepClock);
            hazards?.Puddle(Vector3.zero, 0f);
            // anillo de agujas alrededor del punto trabado y la tinta se para de golpe
            if (hazards != null)
                for (int i = 0; i < 9; i++)
                {
                    float ang = i * 40f + Random.Range(-12f, 12f);
                    float r = i == 0 ? 0f : Random.Range(0.6f, NuiRadius - 0.2f);
                    hazards.Shard(lockPos + Quaternion.Euler(0f, ang, 0f) * Vector3.forward * r, i == 0 ? 2 : Random.Range(0, 2), 0.9f);
                }
            if (ink != null) ink.RiseTo(1f, 0.2f);
            Game.FX?.Shockwave(lockPos, NuiRadius, new Color(0.75f, 0.54f, 1f));
            Game.FX?.Dust(lockPos, 1.4f);
            Game.Camera?.Shake(0.45f);
            Game.Audio?.Play("slam", lockPos, 0.9f);
            if (target != null && CombatMath.FlatDistance(target.transform.position, lockPos) <= NuiRadius + target.Radius)
            {
                stepHit = true;
                // lo despide hacia afuera del estallido (parado justo en el centro, hacia donde mira)
                Vector3 from = (target.transform.position - lockPos).Flat().sqrMagnitude > 0.09f ? lockPos : target.transform.position - target.transform.forward;
                HitPlayer(a, from);
            }
        }

        void TickWatari(AttackDef a, float dt)
        {
            if (!crossing)
            {
                // apunta hasta el "¡ahora!" y desde ahí el carril queda fijo
                if (StrikeEta > KokuyoMoves.GoLead) FaceFlat(target.transform.position, dt, 10f);
                if (ink != null) ink.SampleAhead(KokuyoTimings.Tsuki.State, KokuyoTimings.Tsuki.Apex);
                if (stepClock >= tl.T)
                {
                    crossing = true;
                    laneOrigin = transform.position;
                    laneDir = transform.forward.Flat().normalized;
                    tl.sustain = CrossLength / CrossSpeed;
                    Game.Audio?.Play("ability_wind", transform.position, 0.8f);
                }
                return;
            }
            if (ink != null) ink.SampleAhead(KokuyoTimings.Tsuki.State, KokuyoTimings.Tsuki.ActiveEnd);
            float travelled = (stepClock - tl.T) * CrossSpeed;
            if (travelled <= CrossLength && !anim.Frozen)
            {
                Vector3 p = laneOrigin + laneDir * Mathf.Min(travelled, CrossLength);
                p.y = transform.position.y;
                transform.position = p;
                Game.FX?.DustTrail(p);
                if (!crossHit && target != null)
                {
                    Vector3 to = (target.transform.position - p).Flat();
                    float along = Vector3.Dot(to, laneDir);
                    float lateral = Mathf.Abs(Vector3.Dot(to, Vector3.Cross(Vector3.up, laneDir)));
                    if (along <= 0.3f && along > -1.5f && lateral <= CrossHalfWidth + target.Radius)
                    {
                        crossHit = true;
                        stepHit = true;
                        HitPlayer(a, p - laneDir);
                    }
                }
            }
        }

        protected override void ComboEnd()
        {
            ReleaseToken();
            bool wasParried = parried;
            pattern = null;
            crossing = false;
            hazards?.Puddle(Vector3.zero, 0f);
            SetState(EnemyState.Idle);
            AfterStrike(!wasParried);
        }

        /// <summary>Terminó (o se cortó) un golpe: la pose vuelve a la guardia, la tinta a sus pies o a la oscuridad.</summary>
        void AfterStrike(bool settle)
        {
            if (mode != Mode.Pinned) mode = Mode.Hunt;
            if (Form == Shape.Bound)
            {
                // pegada no hay guardia propia: la tinta vuelve a sus pies y el doble se funde en la pose del cuerpo
                if (nobiWTarget > 0f) Retract(NobiRetractTime);
                mirrorPending = true;
                return;
            }
            // el desvío ya termina en la guardia (Parried llega a READY); un corte normal termina abajo a la izquierda
            if (settle) Settle(KokuyoTimings.RecoverL.State, KokuyoTimings.RecoverL.Seconds);
            if (Form == Shape.Hidden && mode != Mode.Pinned) vanishAt = Time.time + (settle ? 0.3f : 0.05f);
        }

        void Retract(float seconds)
        {
            nobiWTarget = 0f;
            retractTime = Mathf.Max(0.05f, seconds);
        }

        void Settle(string state, float seconds)
        {
            settleState = state;
            settleDur = Mathf.Max(0.05f, seconds);
            settleLeft = settleDur;
        }

        // ------------------------------------------------------------------ vuelta al cuerpo (eclipse)
        /// <summary>La sombra vuelve volando a los pies de Kokuyō y se acuesta (el eclipse la borra después).</summary>
        public void Recall()
        {
            if (State == EnemyState.Attack) SetState(EnemyState.Idle);
            ReleaseStrikeReservation();
            hazards?.Puddle(Vector3.zero, 0f);
            plannedImpactAt = -1f;
            settleLeft = 0f;
            mode = Mode.Recall;
            recallT = 0f;
            recallFrom = transform.position;
            recallRot = transform.rotation;
            if (ink != null) { ink.FadeTo(1f, 0.2f); ink.RiseTo(0f, 0.45f); }
        }

        void TickRecall(float dt)
        {
            recallT += dt / 0.5f;
            float k = 1f - (1f - Mathf.Clamp01(recallT)) * (1f - Mathf.Clamp01(recallT));
            Vector3 p = Vector3.Lerp(recallFrom, owner.transform.position, k);
            p.y = owner.transform.position.y;
            transform.position = p;
            // llega girada como él: al volver a sus pies la raíz no salta
            transform.rotation = Quaternion.Slerp(recallRot, owner.Body.rotation, k);
            if (recallT >= 1f && ink != null && ink.Detached)
            {
                ink.Reattach();
                ink.ReturnToBody(0.25f);   // vuelve a ser su sombra: copia la pose del cuerpo (con un fundido)
            }
        }

        /// <summary>Se va del todo (reintento, final). La sombra dibujada la maneja KageArenaFX.</summary>
        public void Dismiss()
        {
            if (State == EnemyState.Attack) SetState(EnemyState.Idle);
            ReleaseStrikeReservation();
            hazards?.Puddle(Vector3.zero, 0f);
            ResetInkAim();
            Destroy(gameObject);
        }

        /// <summary>La luz, la raíz, el largo y el hueco de la sombra como los dejó PlanarShadow (sin el Nobi).</summary>
        void ResetInkAim()
        {
            nobiW = nobiWTarget = 0f;
            mirrorPending = handingBack = false;
            if (ink == null) return;
            ink.ResetLight();
            ink.AimRoot(null);
            ink.Stretch = 1f;
            ink.HoleRadius = HoleDefault;
        }

        // ------------------------------------------------------------------ movimiento
        void Glide(Vector3 dest, float speed, float dt)
        {
            Vector3 d = (dest - transform.position).Flat();
            float m = d.magnitude;
            if (m < 0.05f) return;
            MoveBy(d / m * Mathf.Min(m, speed * dt));
        }

        void FaceFlat(Vector3 p, float dt, float rate = 8f)
        {
            Vector3 d = (p - transform.position).Flat();
            if (d.sqrMagnitude > 0.01f) transform.rotation = CombatMath.Damp(transform.rotation, Quaternion.LookRotation(d), rate, dt);
        }

        Vector3 ClampToArena(Vector3 p) => owner != null ? owner.ClampToArena(p, 1.5f) : p;

        protected override void Update()
        {
            base.Update();
            float dt = Time.deltaTime;
            if (ink == null) return;
            if (Form == Shape.Hidden)
            {
                if (!ink.Detached && ink.Visibility < 0.01f && mode != Mode.Recall) LieInTheDark();
                if (vanishAt > 0f && Time.time >= vanishAt) Vanish(0.45f);
                // el brillo violeta (luz en el piso y un filo más fuerte) la hace legible en la oscuridad mientras está
                // afuera, y se apaga con ella
                float want = emerged ? DarkGlow * ink.Visibility : 0f;
                glow.intensity = Mathf.MoveTowards(glow.intensity, want, dt * 8f);
                glow.enabled = glow.intensity > 0.01f;
                ink.RimGain = emerged ? DarkRim : 1f;
            }
            else if (glow != null && glow.enabled) { glow.intensity = 0f; glow.enabled = false; }
            // la figura de tinta va donde está este cazador (suelta: PlanarShadow ya no la pega al cuerpo). Pegada no:
            // en el arranque del Acto 2 la tinta ya está suelta y la lleva KageArenaFX (se despega hacia la cámara)
            if (Form != Shape.Bound && ink.Detached && ink.Root != null) ink.Root.SetPositionAndRotation(transform.position, transform.rotation);
            UpdateNobiInk(dt);
            UpdatePose(dt);
            UpdateTipMark();
            UpdateEdge();
        }

        /// <summary>El trazo de la hoja recién salida de la oscuridad (EdgeHold + EdgeFade), sobre la pose ya evaluada.</summary>
        void UpdateEdge()
        {
            if (edge == null) return;
            float k = Time.time - edgeAt;
            var tip = ink.BladeTip;
            var bas = ink.BladeBase;
            bool on = emerged && tip != null && bas != null && k < EdgeHold + EdgeFade;
            if (edge.enabled != on) edge.enabled = on;
            if (!on) return;
            float a = (k < EdgeHold ? 1f : 1f - (k - EdgeHold) / EdgeFade) * ink.Visibility;
            var c = new Color(EdgeColor.r, EdgeColor.g, EdgeColor.b, a);
            edge.startColor = edge.endColor = c;
            edge.SetPosition(0, bas.position);
            edge.SetPosition(1, tip.position);
        }

        /// <summary>
        /// Cuánto apunta la sombra pegada hacia el punto del Nobi (0 = su sombra de siempre, desde la luna del norte).
        /// Entra en NobiAimTime y vuelve en NobiRetractTime; al volver del todo (y con la pose en la guardia) el doble
        /// pasa a copiar al cuerpo con un fundido.
        /// </summary>
        void UpdateNobiInk(float dt)
        {
            if (Form != Shape.Bound) return;
            bool aiming = nobiW > 0f || nobiWTarget > 0f;
            float rate = nobiWTarget > nobiW ? 1f / NobiAimTime : 1f / retractTime;
            nobiW = Mathf.MoveTowards(nobiW, nobiWTarget, rate * dt);
            if (aiming)
            {
                float k = Mathf.SmoothStep(0f, 1f, nobiW);
                // gira en el plano del piso por el lado corto (un Slerp entre direcciones opuestas da vueltas raras)
                Vector3 from = new Vector3(PlanarShadow.DefaultLight.x, 0f, PlanarShadow.DefaultLight.z).normalized;
                Vector3 to = nobiDir.sqrMagnitude > 0.01f ? nobiDir : from;
                Vector3 h = Quaternion.AngleAxis(Vector3.SignedAngle(from, to, Vector3.up) * k, Vector3.up) * from;
                float cosE = new Vector2(PlanarShadow.DefaultLight.x, PlanarShadow.DefaultLight.z).magnitude, sinE = -PlanarShadow.DefaultLight.y;
                ink.SetLightDirection(h * cosE + Vector3.down * sinE);
                // la raíz gira con la luz: corta HACIA Kaito aunque el cuerpo mire a otro lado
                var body = owner.Body;
                float yaw = Vector3.SignedAngle(owner.transform.forward.Flat(), nobiDir.sqrMagnitude > 0.01f ? nobiDir : owner.transform.forward.Flat(), Vector3.up);
                ink.AimRoot(Quaternion.AngleAxis(yaw * k, Vector3.up) * body.rotation);
                float d = CombatMath.FlatDistance(owner.transform.position, nobiPoint);
                float unit = ink.Stretch > 0.01f ? ink.Length / ink.Stretch : 6.4f;   // su largo sin estirar (~6.4 m)
                // pegado a él la sombra se acorta (la luna "sube") hasta NobiMinStretch: con el piso de 0.8 de antes, a
                // 2 m la silueta le pasaba 3 m de largo a Kaito y el Nobi solo salía a 2.5 m o más
                float stretch = Mathf.Clamp((d - NobiHeadShort) / unit, NobiMinStretch, 2f);
                ink.Stretch = Mathf.Lerp(1f, stretch, k);
                ink.HoleRadius = Mathf.Lerp(HoleDefault, HoleNobi, k);
                if (nobiW <= 0f && nobiWTarget <= 0f) { ink.ResetLight(); ink.AimRoot(null); ink.Stretch = 1f; ink.HoleRadius = HoleDefault; }
            }
            // vuelve a copiar al cuerpo cuando la tinta ya está en sus pies y la pose en la guardia (el fundido es de
            // ella; el que hace el cuerpo después de cada golpe suyo no frena al cuerpo)
            if (mirrorPending && nobiW <= 0f && settleLeft <= 0f && State != EnemyState.Attack && State != EnemyState.Recoil)
            {
                mirrorPending = false;
                ink.ReturnToBody(0.3f);
                handingBack = ink.Returning;
            }
            else if (handingBack && !ink.Returning) handingBack = false;
        }

        /// <summary>La pose del doble: el clip del golpe en su reloj, el desvío, la vuelta a la guardia y la ronda.</summary>
        void UpdatePose(float dt)
        {
            var a = CurrentAttack;
            var c = KokuyoMoves.ClipOf(a);
            if (State == EnemyState.Attack)
            {
                if (c != null) ink.SampleAhead(c.State, stepNorm);   // Nui y Watari arman su pose en su Tick
                return;
            }
            if (State == EnemyState.Recoil)
            {
                ink.SampleAhead(KokuyoTimings.Parried.State, Mathf.Clamp01(stateTime / Mathf.Max(0.05f, stateDuration)));
                return;
            }
            if (settleLeft > 0f)
            {
                settleLeft = Mathf.Max(0f, settleLeft - dt);
                ink.SampleAhead(settleState, 1f - settleLeft / settleDur);
                return;
            }
            // pegada, fuera de sus golpes, la pose es la del cuerpo (espejo o el adelanto del Acto 1); también a oscuras
            // mientras todavía está en sus pies apagándose con el eclipse (si no, saltaba a la guardia en pleno gesto)
            if (Form == Shape.Bound || mode == Mode.Recall || !ink.Detached) return;
            ink.SampleAhead(KokuyoTimings.Idle.State, Mathf.Repeat(Time.time / KokuyoTimings.Idle.Seconds, 1f));
        }

        void UpdateTipMark()
        {
            if (tipMark == null) return;
            var tip = ink.BladeTip;
            Vector3 p = tip != null ? tip.position : transform.position + Vector3.up * 2f;
            // acostada, el brillo va donde cae la punta en el piso
            if (ink.Rise < 0.5f) p = ink.ProjectToGround(p);
            tipMark.position = p;
        }

        protected override void OnDestroy()
        {
            base.OnDestroy();
            if (Game.Combat != null) Game.Combat.ReleaseStrike(this);
        }
    }
}
