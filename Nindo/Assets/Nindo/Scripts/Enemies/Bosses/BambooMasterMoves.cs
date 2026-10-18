using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Perillas, golpes y config de Chikuō, el Ermitaño de las Cañas (Docs/handoff/diseno/chikuo_v2.md, secciones 5, 6, 12
    /// y 17). Todo número de la pelea vive acá, con el mismo nombre que en el modelo de Python (Tools/Dev/chikuo_v2_check.py,
    /// diccionario P): el día que se calibre con el PlayClock se cambia en los dos lados. Los tiempos de cada movimiento
    /// salen de los clips (ChikuoTimings, el sidecar de Blender): el aviso, el dardo y el golpe caen en el cuadro que se ve.
    /// </summary>
    public static class BambooMasterMoves
    {
        // ================================================================== perillas (sección 12.3 del diseño)
        /// <summary>Pisos de vida de cada fase: 65 % (baja al piso) y 40 % (el bosque entero). El golpe que cruza el piso
        /// dispara la escena y lo que sobra no cuenta.</summary>
        public static readonly float[] Gates = { 1f, 0.65f, 0.40f, 0f };
        public const float TransitionHeal = 30f, TransitionSpirit = 30f;
        /// <summary>Respiro posado entre acciones por fase (s): nunca quieto, se hamaca con la caña. En la fase 2 es la
        /// pausa entre tandas del piso.</summary>
        public static readonly Vector2[] Breath = { new Vector2(0.25f, 0.45f), new Vector2(0.35f, 0.6f), new Vector2(0.10f, 0.20f) };
        /// <summary>Kaito a esta distancia de la base y él sin cargar: le contesta (7.1, regla 4).</summary>
        public const float ReactDist = 4.5f;
        /// <summary>Plantado al pie de la caña tanto tiempo: barrido de caña (cada CampEvery s como mucho).</summary>
        public const float CampDist = 2.5f, CampTime = 0.6f, CampEvery = 5f;
        /// <summary>Acciones por caña antes de saltar sí o sí (1 en la Última Canción).</summary>
        public const int MaxOnStalk = 2;
        /// <summary>La Última Canción (fase 3): salta después de cada acción.</summary>
        public const float LastSong = 0.20f;
        /// <summary>Fase 3: la firma (tala, catapulta o la ráfaga de cuatro) a los SignatureFirst s y después cada SignatureEvery.</summary>
        public static readonly Vector2 SignatureFirst = new Vector2(5f, 7f), SignatureEvery = new Vector2(9f, 12f);
        /// <summary>Con Kaito a esta distancia o menos de la base, la firma de la ráfaga de cuatro sigue sin respiro con la
        /// Picada (m).</summary>
        public const float SignatureChain = 7f;
        /// <summary>Los dardos posados (Dardo, Dos Dardos, Tres y Cuatro Notas) por fase: en la fase 3 a x1.2 y un soplido de
        /// cada dos en abanico (dos dardos más a FanM del de Kaito, de costado): la fase 3 tenía la misma densidad de
        /// amenazas que la 1 y menos que la 2 (37 / 48 / 37 por minuto fuera de los huecos; ahora 37 / 48 / 53).</summary>
        public static readonly float[] PerchRate = { 1f, 1f, 1.2f };
        public static readonly bool[] Fan = { false, false, true };
        public const float FanM = 1.6f;
        /// <summary>La catapulta por pesos (fase 3): Kaito a esta distancia o más, cada tanto como mucho, con este peso.</summary>
        public const float CatapultMinDist = 4f, CatapultEvery = 6f, CatapultWeight = 1.0f;
        /// <summary>Colgado con Kaito al pie: la carga prende recién esto antes del primer dardo.</summary>
        public const float HangNearLoadLead = 0.35f;
        /// <summary>El Silbador sale recién desde este tramo de vida (la fase 1 enseña primero el dardo y la ráfaga).</summary>
        public const float WhistleFrom = 0.85f;

        // ---- dardos
        public static readonly float[] DartSpeed = { 16f, 16f, 18f };
        /// <summary>Cuánto adelanta la puntería con la velocidad de Kaito (de costado, corriendo, se esquiva en las fases 1-2).</summary>
        public static readonly float[] DartLead = { 0.5f, 0.6f, 0.8f };
        public const float DartHitR = 0.6f, WhistleSpeed = 22f, WhistleLane = 1.0f;
        /// <summary>El carril del silbador deja de seguir a Kaito este tiempo antes de soplar.</summary>
        public const float WhistleFix = 0.25f;
        /// <summary>Lo que queda clavado en el piso un dardo que no pegó (se ve dónde cayó la ráfaga).</summary>
        public const float DartStuck = 3f;

        // ---- saltos entre cañas
        /// <summary>Vuelo: LeapBase + LeapPerM por metro, por LeapK de la fase; comba del arco.</summary>
        public const float LeapBase = 0.30f, LeapPerM = 0.035f, LeapArc = 1.8f;
        public static readonly float[] LeapK = { 1f, 1f, 0.85f };
        /// <summary>El agachado del salto a x1.57 en la fase 3 (0.23 → 0.15 s).</summary>
        public static readonly float[] LeapCrouchRate = { 1f, 1f, 1.57f };
        /// <summary>A qué distancia de Kaito busca posarse (la franja), por fase.</summary>
        public static readonly Vector2[] LeapDest = { new Vector2(4.5f, 8f), new Vector2(4.5f, 8f), new Vector2(4f, 7f) };
        /// <summary>Nunca se posa más cerca de Kaito que esto; el cono del sur de Kaito (donde su cuerpo posado lo tapa).</summary>
        public const float PerchMinDist = 2.5f, SouthConeDeg = 30f, SouthConeNear = 2.5f, SouthConeFar = 6.5f;
        /// <summary>Caída del cielo: cortar la caña de destino en los últimos CatchWindow s del vuelo (por fase: en la 3 los
        /// saltos son más cortos y rápidos, y con 0.45 no se llegaba de reacción).</summary>
        public static readonly float[] CatchWindow = { 0.45f, 0.45f, 0.60f };
        /// <summary>Lo que mira la caña de destino antes de agacharse (fase 3: el agachado va a x1.57).</summary>
        public static readonly float[] LeapLook = { 0f, 0f, 0.25f };
        /// <summary>Fase 3: al caer de un salto, la chance de encadenar otro (ping-pong).</summary>
        public const float PingPong = 0.30f;
        /// <summary>El bot (y la pista bamboo_deny): un salto a una caña a esta distancia de Kaito o menos se puede atajar.</summary>
        public const float CatchHint = 5f, BotCatchDist = 7f;

        // ---- el latigazo y los huecos (sección 6)
        public const float StampRange = 6f, StampAngle = 26f, RevolconM = 3.2f, PoleFlingM = 2f;
        /// <summary>El revolcón nunca deja al viejo a más de esto del centro (adentro de la barrera de 15 m).</summary>
        public const float ArenaKeep = 13f;
        /// <summary>A qué altura de la otra caña se estrella el estampado.</summary>
        public const float SplatHeight = 3.5f;

        /// <summary>Un hueco: lo que vuela hasta que se lo puede cortar, cuánto queda abierto, el tope de cortes, el
        /// multiplicador de daño y el daño de la caída (entra al tocar el piso, como un corte).</summary>
        public struct Hole
        {
            public float fly, open, mul, fall;
            public int cap;
            public Hole(float fly, float open, int cap, float mul, float fall) { this.fly = fly; this.open = open; this.cap = cap; this.mul = mul; this.fall = fall; }
        }

        public static Hole Revolcon(int phase) => phase >= 2 ? new Hole(0.55f, RevolconOpen[2], RevolconCap, 1f, 12f) : new Hole(0.55f, RevolconOpen[0], RevolconCap, 1f, 12f);
        /// <summary>El revolcón, el resultado más común del latigazo: abierto y tope de cortes (la perilla de la duración). Medido en
        /// Unity el 18 de octubre con tope 5 y daño x0.9: bueno 3:50 y promedio 4:44, los dos sin morir (factor real/simulado
        /// ~1.1); con tope 2 y daño x1.0 la simulación da 4.6 min y 6.6 min con 1.5 muertes.</summary>
        public static readonly float[] RevolconOpen = { 2.2f, 2.2f, 2.0f };
        public const int RevolconCap = 2;
        public static Hole Estampado(int phase) => phase >= 2 ? new Hole(1.0f, 2.0f, 3, 1.2f, 24f) : new Hole(1.0f, 2.2f, 4, 1.2f, 24f);
        /// <summary>La caída del cielo: el premio grande. La simulación la da 0.2 veces por pelea, pero en Unity el bot la saca
        /// 2 a 4 veces (18 de octubre) y con 3 s, 5 cortes y 36 de caída decidía el largo de la pelea (2:43 a 3:50 con el
        /// mismo bot): sigue siendo el mejor hueco, pero ya no termina la fase sola.</summary>
        public static readonly Hole Caida = new Hole(0.45f, 2.6f, 3, 1.25f, 24f);
        public static readonly Hole Resbalon = new Hole(0.30f, 1.0f, 2, 1f, 6f);
        public static readonly Hole Tropiezo = new Hole(0f, 1.0f, 2, 1f, 0f);
        public static readonly Hole Pies = new Hole(0f, 1.6f, 3, 1f, 0f);
        public static readonly Hole Clavado = new Hole(0f, 1.1f, 2, 1f, 0f);
        public static readonly Hole Aterrizaje = new Hole(0f, 0.45f, 1, 1f, 0f);
        public static readonly Hole Afinado = new Hole(0.30f, 2.5f, 4, 1.2f, 0f);
        public static readonly Hole Desafinado = new Hole(0f, 1.4f, 2, 1f, 0f);
        public static readonly Hole PoleRevolcon = new Hole(0.55f, 1.6f, 3, 1f, 12f);
        /// <summary>Contra: el parry al último golpe de una tanda (o al bastón que cae). El primer corte va x1.5 (el
        /// contraataque de siempre de PlayerController).</summary>
        public static Hole Contra(bool perfect) => new Hole(0f, perfect ? 0.60f : 0.40f, perfect ? 3 : 2, 1f, 0f);
        /// <summary>Lo que sigue abierto después del último corte del tope (lo despide un poco y se levanta).</summary>
        public const float CapRise = 0.25f;

        // ---- el piso (fase 2 y la coda de la 3)
        /// <summary>El corte en neutral le entra a x0.6 y se va de una voltereta; en la carga de su golpe, x0.35 y el golpe sigue.</summary>
        public const float NeutralMul = 0.6f, ArmorMul = 0.35f;
        /// <summary>Después de la voltereta arranca una tanda a este tiempo; una voltereta cada FlipEvery s como mucho.</summary>
        public const float AfterFlip = 0.25f, FlipEvery = 1.5f;
        public static readonly Vector2 PoleFirst = new Vector2(4f, 6f), PoleEvery = new Vector2(8f, 11f);
        public static readonly Vector2 QaFirst = new Vector2(9f, 12f), QaEvery = new Vector2(18f, 24f);
        /// <summary>Pregunta y Respuesta: entre notas, de la última de la pregunta a la primera de la respuesta, radio del brote
        /// y cuándo queda fijo antes de brotar.</summary>
        public const float NoteGap = 0.44f, AnswerLead = 0.85f, SproutRadius = 1.0f, SproutFix = 0.45f;
        /// <summary>Desde esta vida (fracción) la pregunta es de cuatro notas.</summary>
        public const float QaFourFrom = 0.52f;
        /// <summary>El Soplo: con Kaito más lejos que esto, un dardo desde el piso cada tanto.</summary>
        public const float SoploDist = 4.5f, SoploEvery = 2.5f;
        /// <summary>La Grulla en el Bastón: el salto atrás antes de clavarlo; cargada de PoleLoadFrom a PoleLeaveAt s desde
        /// que clava, y ahí sale en picada.</summary>
        public const float PoleHop = 4f, PoleLoadFrom = 0.45f, PoleLeaveAt = 1.40f;
        /// <summary>La Tala: el carril queda fijo y la caña pega a estos s desde que arranca.</summary>
        public const float TalaFix = 0.65f, TalaImpact = 1.10f;

        // ---- vuelta arriba
        /// <summary>Trepa si cayó a esta distancia de una caña; si no, se agacha y salta.</summary>
        public const float ClimbReach = 1.5f;
        /// <summary>El kip-up de después de un hueco (GetUp a esta duración; el clip es de 0.40 s).</summary>
        public const float GetUpTime = 0.25f;
        /// <summary>Cómo vuelve arriba después de un hueco: con Kaito a RecoverLeapDist o más, un salto común; si no, la
        /// garrocha (RecoverVault), el agachado cortable (RecoverCrouch) o, con Kaito a RecoverTandaDist o menos, dos
        /// bastonazos y trepa (el resto).</summary>
        public const float RecoverLeapDist = 6f, RecoverVault = 0.45f, RecoverCrouch = 0.30f, RecoverTandaDist = 4f;
        /// <summary>Garrocha después de un hueco: a una caña a esta distancia de Kaito.</summary>
        public static readonly Vector2 VaultDest = new Vector2(4.5f, 8f);
        /// <summary>Bastonazo de la vuelta: la mitad de las veces con Kaito a 3 m o menos; la Revancha de la fase 3 igual.</summary>
        public const float AfterLandStrikeChance = 0.5f, AfterLandStrikeDist = 3f;
        /// <summary>Cuánto le escupe al revolcón la Picada: el disco queda fijo a 0.50 s del golpe.</summary>
        public const float DiveFix = 0.50f;
        /// <summary>El Bastón que Cae elige dónde cae (de Kaito, de su lado) a este tiempo desde que arranca.</summary>
        public const float StaffDropPick = 0.40f, StaffDropNear = 1.6f;
        /// <summary>Lo más que gira el cuerpo sobre los pies soplando para que la cerbatana no caiga sobre el culmo en pantalla
        /// (grados).</summary>
        public const float AimYaw = 20f;

        /// <summary>Todo lo que pega a Kaito se multiplica por esto (la perilla de las muertes: 0.9 o 1.1, sección 12.3).</summary>
        public const float DamageScale = 1.0f;

        /// <summary>Daño a Kaito (de 100) por fase (0..2). Pica como un mosquito: lo que exige es la densidad.</summary>
        public static float Dmg(Move m, int phase)
        {
            int p = Mathf.Clamp(phase, 0, 2);
            float d;
            switch (m)
            {
                case Move.Dart: d = 2.5f; break;
                case Move.Whistle: d = 5f; break;
                case Move.Dive: d = 5f; break;
                case Move.StaffDrop: d = p >= 2 ? 4.5f : 5f; break;
                case Move.Sweep: d = 4f; break;
                case Move.Strike: d = p >= 2 ? 4f : 3.5f; break;
                case Move.LowSweep: d = p >= 2 ? 5f : 4.5f; break;
                case Move.Sprout: d = p >= 2 ? 4.5f : 4f; break;
                case Move.Catapult: d = 6.5f; break;
                case Move.Tala: d = 5.5f; break;
                case Move.PoleDive: d = 5f; break;
                default: d = 3.5f; break;
            }
            return d * DamageScale;
        }

        public enum Move { Dart, Whistle, Dive, StaffDrop, Sweep, Strike, LowSweep, Sprout, Catapult, Tala, PoleDive }

        // ================================================================== golpes
        /// <summary>Especiales de Chikuō que maneja el jefe (los 'held' llevan su propio reloj: BambooMasterBoss.StepHeld).</summary>
        public const string Sweep = "c_sweep", Whistle = "c_whistle", Dive = "c_dive", StaffDrop = "c_staffdrop", Catapult = "c_catapult",
            Tala = "c_tala", PoleDive = "c_polecrane", Answer = "c_answer", Spin = "c_spin", Soplo = "c_soplo", LowSweep = "c_lowsweep",
            Strike = "c_strike";

        /// <summary>
        /// Un golpe que el jefe coreografía con sus clips (desde la caña, la picada, la pértiga): Enemy pone el anillo, el
        /// "¡ya!", el destello y la zona con la ETA que da el jefe, y el reloj del paso lo lleva el jefe. La línea de tiempo
        /// de Enemy queda con el golpe en 'strike' segundos (apex 0, la suelta lineal hasta ahí): de eso sale cuándo arranca
        /// el anillo.
        /// </summary>
        public static AttackDef Held(string name, ChikuoClip c, AttackKind kind, float strike, float dmg, string special, float param = 0f)
        {
            float start = Mathf.Clamp(strike / Mathf.Max(0.05f, c.Seconds), 0.02f, 1f);
            return new AttackDef
            {
                name = name, state = c.State, damage = dmg, kind = kind, range = Mathf.Max(0.5f, c.ReachM), arc = 360f, knockback = kind == AttackKind.Unblockable ? 2f : 1.4f,
                apex = 0f, activeStart = start, activeEnd = start, releaseRate = 1f, windup = strike,
                lunge = 0f, tracking = false, hitStop = kind == AttackKind.Unblockable ? 0.12f : 0.1f, shake = kind == AttackKind.Unblockable ? 0.45f : 0.35f,
                sfx = kind == AttackKind.Unblockable ? "enemy_swing_heavy" : "enemy_swing", special = special, specialParam = param,
            };
        }

        /// <summary>
        /// Un golpe de piso con los tiempos de su clip (las tandas de la fase 2): el anillo se cierra en el contacto y 'charge'
        /// es la carga (s desde que arranca hasta que pega). StepTimeline.MinWindup lo multiplica por 0.9 desde la fase 2: se
        /// compensa acá para que la carga sea la que pide el diseño.
        /// </summary>
        static AttackDef Ground(string name, ChikuoClip c, AttackKind kind, float charge, float dmg, string special, bool noRecoil, float param = 0f)
        {
            float rate = 1f;
            float apexS = c.Apex * c.Seconds, contactS = c.Contact * c.Seconds;
            // la suelta del clip a la velocidad que deja la carga pedida (anticipación al 0.85 de StepTimeline)
            float release = contactS - apexS;
            float left = charge - apexS / 0.85f;
            if (left > 0.04f && release > 0.01f) rate = Mathf.Clamp(release / left, 0.8f, 2.2f);
            return new AttackDef
            {
                name = name, state = c.State, damage = dmg, kind = kind, range = Mathf.Max(1.2f, c.ReachM), arc = kind == AttackKind.Unblockable ? 360f : 110f,
                knockback = kind == AttackKind.Unblockable ? 2f : 1.4f, apex = c.Apex, activeStart = c.Contact, activeEnd = Mathf.Max(c.Contact, c.ActiveEnd),
                releaseRate = rate, windup = charge / 0.9f, lunge = 0f, tracking = true, hitStop = kind == AttackKind.Unblockable ? 0.12f : 0.1f,
                shake = kind == AttackKind.Unblockable ? 0.45f : 0.35f, sfx = kind == AttackKind.Unblockable ? "enemy_swing_heavy" : "enemy_swing",
                special = special, specialParam = param, noRecoil = noRecoil, imbalance = 0f,
            };
        }

        static AttackPattern P(string name, float weight, float minRange, float maxRange, float cooldown, params AttackDef[] steps) =>
            new AttackPattern { name = name, steps = steps, weight = weight, minRange = minRange, maxRange = maxRange, cooldown = cooldown };

        /// <summary>
        /// Las tandas del piso (fase 2 y la coda de la 3), sin guardia: cargas de 0.42-0.65 s y el último golpe, desviado,
        /// lo deja abierto (la Contra); los del medio no (noRecoil: la tanda sigue). La Flauta Giratoria pega dos veces en
        /// el mismo clip (la lleva el jefe: 'c_spin'). El Soplo es el dardo desde el piso con Kaito lejos.
        /// </summary>
        public static AttackPattern[] GroundPatterns(int phase)
        {
            var T = ChikuoTimings.Thrust;
            float strike = Dmg(Move.Strike, phase);
            var thrust = Ground("Estocada", T, AttackKind.Heavy, 0.50f, strike, Strike, true);
            var thrust2 = Ground("Estocada", T, AttackKind.Heavy, 0.42f, strike, Strike, true);
            var thrustLast = Ground("Estocada", T, AttackKind.Heavy, 0.42f, strike, Strike, false);
            var spin = Held("Flauta Giratoria", ChikuoTimings.StaffSpin2, AttackKind.Heavy, 0.55f, strike, Spin, 0.42f);
            var crane = Ground("Patada de Grulla", ChikuoTimings.CraneKick, AttackKind.Heavy, 0.50f, strike, Strike, true);
            var low = Ground("Barrida del Bastón", ChikuoTimings.LowSweep, AttackKind.Unblockable, 0.80f, Dmg(Move.LowSweep, phase), LowSweep, false, ChikuoTimings.LowSweep.RingM);
            var note = Ground("Golpe de Nota", ChikuoTimings.NoteSmash, AttackKind.Heavy, 0.65f, strike, Strike, false);
            var soplo = Ground("Soplo", ChikuoTimings.GroundDart, AttackKind.Projectile, 0.55f, Dmg(Move.Dart, phase), Soplo, false);
            float reach = T.ReachM + 0.3f;
            return new[]
            {
                P("Nota y Giro", 1.0f, 0f, reach, 0f, thrust, spin),
                P("Grulla que Barre", 0.9f, 0f, ChikuoTimings.CraneKick.ReachM + 0.6f, 0f, crane, low),
                P("Tres Estocadas", 0.8f, 0f, reach, 0f, thrust, thrust2, thrustLast),
                P("Golpe de Nota", 0.6f, 0f, ChikuoTimings.NoteSmash.ReachM + 0.3f, 0f, note),
                P("Soplo", 1.2f, SoploDist, 99f, SoploEvery, soplo),
            };
        }

        /// <summary>Los dos bastonazos de la vuelta de un hueco: el segundo, desviado, abre la Contra.</summary>
        public static AttackPattern RecoveryTanda(int phase)
        {
            var T = ChikuoTimings.Thrust;
            float strike = Dmg(Move.Strike, phase);
            return P("Vuelta con Bastón", 1f, 0f, 99f, 0f, Ground("Estocada", T, AttackKind.Heavy, 0.50f, strike, Strike, true), Ground("Estocada", T, AttackKind.Heavy, 0.42f, strike, Strike, false));
        }

        /// <summary>El bastonazo dorado (después de aterrizar con Kaito cerca, y la Revancha de la fase 3: pararla no lo abre).</summary>
        public static AttackDef Bastonazo(int phase, bool revancha) =>
            Ground(revancha ? "Revancha" : "Bastonazo", ChikuoTimings.Thrust, AttackKind.Heavy, revancha ? 0.60f : 0.55f, Dmg(Move.Strike, phase) + (revancha ? 0.5f : 0f), Strike, revancha);

        // ================================================================== config
        /// <summary>
        /// Chikuō, el Ermitaño de las Cañas. 2200 de vida, la que tenía cuando el usuario dijo que estaba bien (C3 la había bajado a
        /// 1900; con 1900 el bot bueno ganaba en 3:46 en Unity, con el bot sacando la caída del cielo hasta 6 veces). No se lo ejecuta
        /// (termina sentado con las piernas cruzadas, BambooMasterBoss.Story). Sin postura: ningún hueco sale de llenar una
        /// barra, salen de las reglas que se ven (maxImbalance y poiseHits altos apagan las reglas comunes del agotado y del
        /// neutral). Locomoción a 1.6 / 5.5 m/s, las de Walk y Run (los pies no patinan). Arriba decide el jefe; los
        /// patrones de config son las tandas del piso.
        /// </summary>
        public static EnemyConfig Config()
        {
            return new EnemyConfig
            {
                id = "ozeki", displayName = "Chikuō", maxHealth = 2200, runSpeed = 5.5f, walkSpeed = 1.6f, turnSpeed = 9f,
                radius = 0.5f, height = 2.4f, scale = 1f, tintStrength = 0f,
                maxImbalance = 99, exhaustedTime = 1f, exhaustedDamageMul = 1f, guardTime = 0.3f,
                poiseHits = 99, hyperArmor = true, knockbackResist = 1f, staggerTime = 0.3f,
                parriedRecoil = ChikuoTimings.Parried.Seconds,
                preferredDistance = 2.4f, detectRadius = 30f, loseRadius = 80f,
                finisherHealth = 0f, attackCooldown = Breath[1], cinematicFinisher = false,
                animLocomotion = "Locomotion", animGuard = "Idle", animCounter = "Idle", animExhausted = "DazedSit", animHit = "Hit",
                animSpotted = "Idle", animDeath = "Defeat", animParried = "Parried", deathClipFalls = true,
                patterns = GroundPatterns(1),
            };
        }
    }
}
