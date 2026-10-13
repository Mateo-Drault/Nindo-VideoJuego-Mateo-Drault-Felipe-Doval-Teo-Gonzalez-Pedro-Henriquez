using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Presets de enemigos y jefes. Los nombres de estado coinciden con los AnimatorControllers
    /// generados en Assets/Nindo/Animation. Tiempos normalizados (0..1) respecto del clip.
    /// 'apex' = pose de máxima carga del arma en cada clip (de ahí sale la suelta del golpe, ver StepTimeline).
    /// </summary>
    public static class EnemyArchetypes
    {
        // apex = fin de la pausa del aviso y activeStart = cuadro de contacto de los clips nuevos (TeamAnims/*Anims.fbx.json,
        // 'normalized': Tools/Blender/anim/build_team_anims.py falla si estos números no coinciden con el clip)
        const float NinjaApex1 = 0.50f, NinjaApex2 = 0.318f, NinjaApex3 = 0.3056f, NinjaApexThrust = 0.275f;
        const float SumoApex1 = 0.556f, SumoApex2 = 0.407f, SumoApex3 = 0.571f, SumoApexSpecial = 0.233f;
        // golpes de zona con clip propio (Tools/Blender/anim/team_moves.py): el remolino y el salto del ninja, el morote del sumo
        const float NinjaApexWhirl = 0.2778f, NinjaApexLeap = 0.2917f, SumoApexMorote = 0.3333f;
        // cuadro del clip en que arranca la embestida (AttackDef.lungeFrom: desde ahí sigue los cuadros del clip, ver
        // Enemy.Locomotion.cs). En los cortes es el primero de la suelta; en los saltos, el último con la punta en el piso
        const float NinjaFrom1 = 0.5417f, NinjaFrom2 = 0.3636f, NinjaFrom3 = 0.3611f, NinjaFromThrust = 0.3f;
        const float NinjaFromLeap = 0.3333f, NinjaFromWhirl = 0.3056f;
        const float SumoFrom1 = 0.5926f, SumoFrom2 = 0.4444f, SumoFrom3 = 0.5952f, SumoFromMorote = 0.3611f;

        static AttackDef Hit(string state, float dmg, float aStart, float aEnd, float range = 2.3f, float arc = 110f,
            AttackKind kind = AttackKind.Light, float lunge = 0.8f, float telegraph = 0f, float speed = 1f, float kb = 0.6f, float apex = -1f,
            float from = -1f, bool air = false, float to = -1f)
        {
            return new AttackDef
            {
                name = state, state = state, damage = dmg, activeStart = aStart, activeEnd = aEnd, range = range, arc = arc,
                kind = kind, lunge = lunge, telegraph = telegraph, speed = speed, knockback = kb, apex = apex,
                lungeFrom = from, lungeAir = air, lungeTo = to,
                hitStop = kind == AttackKind.Light ? 0.07f : 0.12f, sfx = kind == AttackKind.Light ? "enemy_swing" : "enemy_swing_heavy",
            };
        }

        public static EnemyConfig Get(string id)
        {
            switch (id)
            {
                case "ninja": return Ninja();
                case "ninja_elite": return NinjaElite();
                case "sumo": return Sumo();
                case "sumo_mountain": return SumoMountain();
                case "goro": return Goro();
                case "mizuchi": return Mizuchi();
                case "ozeki": return Ozeki();
                case "kage": return Kage();
                default:
                    Debug.LogWarning($"[Nindo] Arquetipo desconocido '{id}', uso ninja.");
                    return Ninja();
            }
        }

        // ------------------------------------------------------------------ comunes
        public static EnemyConfig Ninja()
        {
            var c = new EnemyConfig
            {
                id = "ninja", displayName = "Ninja del Clan", maxHealth = 60, runSpeed = 5.0f, walkSpeed = 2.0f,
                // aguanta el combo entero de Kaito (3 cortes) antes de cubrirse; agotado 2.4 s (ya no se le gasta el
                // desequilibrio por golpe: hasta 4 golpes o ese tiempo)
                radius = 0.42f, height = 1.7f, scale = 1f, maxImbalance = 3, exhaustedTime = 2.4f, guardTime = 1.4f,
                poiseHits = 3, preferredDistance = 3.4f, detectRadius = 10f,
                // los cortes despegan los pies en la suelta, pero el de atrás todavía empuja: con Kaito pegado (el imán corta
                // la embestida) patinaba hasta 14 cm (build_team_anims, magnet_skate_cm); 0.15 m de modelo lo cubren (el
                // cuerpo llega a 0.48 m adelante del transform, a ~0.4 m del de Kaito con las cápsulas pegadas)
                lungeSlack = 0.15f,
                animGuard = "Guard", animCounter = "Counter", animExhausted = "Exhausted", animHit = "Hit",
                animSpotted = "Spotted", animDeath = "Death", animParried = "Parried", deathClipFalls = true,
            };
            // los cuatro golpes saltan (los pies dejan el piso en la embestida): con Kaito cerca caen más corto ('air')
            var a1 = Hit("Attack1", 12, 0.583f, 0.75f, telegraph: 0.12f, apex: NinjaApex1, from: NinjaFrom1, air: true);
            var a2 = Hit("Attack2", 12, 0.455f, 0.636f, apex: NinjaApex2, from: NinjaFrom2, air: true);
            var a3 = Hit("Attack3", 15, 0.583f, 0.694f, kind: AttackKind.Heavy, lunge: 1.4f, kb: 1.2f, apex: NinjaApex3, from: NinjaFrom3, air: true);
            // la estocada arranca de lejos con su propio clip (se lanza volando): el aviso dura más para que se lea
            var thrust = Hit("Thrust", 16, 0.525f, 0.625f, kind: AttackKind.Heavy, lunge: 3.2f, range: 2.6f, apex: NinjaApexThrust, from: NinjaFromThrust, air: true);
            thrust.windup = 0.7f;
            c.patterns = new[]
            {
                new AttackPattern { name = "Combo de 3", steps = new[] { a1, a2, a3 }, weight = 2f, maxRange = 2.8f },
                new AttackPattern { name = "Doble", steps = new[] { a1, a2 }, weight = 1.5f, maxRange = 2.8f },
                new AttackPattern { name = "Estocada", steps = new[] { thrust }, weight = 1f, minRange = 2.6f, maxRange = 5.5f, cooldown = 4f },
            };
            return c;
        }

        public static EnemyConfig NinjaElite()
        {
            var c = Ninja();
            c.id = "ninja_elite"; c.displayName = "Ninja de Élite";
            c.maxHealth = 90; c.runSpeed = 5.6f; c.maxImbalance = 4; c.guardTime = 1.8f; c.poiseHits = 2; c.cinematicFinisher = true;
            c.tint = new Color(0.75f, 0.18f, 0.15f); c.tintStrength = 0.55f;
            c.ScaleSteps(1.25f, 1.12f); // a1/a2 del ninja están en dos patrones: se escalan una sola vez
            var a1 = Hit("Attack1", 14, 0.583f, 0.75f, telegraph: 0.1f, speed: 1.12f, apex: NinjaApex1, from: NinjaFrom1, air: true);
            var a2 = Hit("Attack2", 14, 0.455f, 0.636f, speed: 1.12f, apex: NinjaApex2, from: NinjaFrom2, air: true);
            var a3 = Hit("Attack3", 18, 0.583f, 0.694f, kind: AttackKind.Heavy, lunge: 1.4f, speed: 1.1f, apex: NinjaApex3, from: NinjaFrom3, air: true);
            var list = new System.Collections.Generic.List<AttackPattern>(c.patterns);
            list.Add(new AttackPattern { name = "Combo largo", steps = new[] { a1, a2, a1, a3 }, weight = 1.2f, maxRange = 2.8f });
            c.patterns = list.ToArray();
            return c;
        }

        public static EnemyConfig Sumo()
        {
            var c = new EnemyConfig
            {
                id = "sumo", displayName = "Luchador de Sumo", maxHealth = 150, runSpeed = 3.4f, walkSpeed = 1.6f, turnSpeed = 6f,
                radius = 0.85f, height = 2.5f, scale = 1f, maxImbalance = 2, exhaustedTime = 3.8f, guardTime = 0.8f,
                poiseHits = 4, hyperArmor = true, knockbackResist = 0.7f, preferredDistance = 3.6f, detectRadius = 11f,
                staggerTime = 0.25f, cinematicFinisher = true,
                // con Kaito pegado el imán corta la embestida y el pie de atrás (clavado mientras avanza) patinaba hasta
                // 0.5 m (build_team_anims, magnet_skate_cm). Con las cápsulas pegadas la panza (0.58 m adelante del
                // transform, 0.78 en el golpe) queda a ~0.45 m del cuerpo de Kaito: el modelo sigue 0.35 m sin tocarlo
                lungeSlack = 0.35f,
                // y antes de eso lo arrastra con la panza (hasta 0.6 m por golpe): el pie de atrás queda clavado empujando
                lungeShove = 0.6f,
                animGuard = "Idle", animCounter = "Attack1", animExhausted = "Exhausted", animHit = "Hit",
                animSpotted = "Spotted", animDeath = "Death", animParried = "Parried", deathClipFalls = true,
            };
            var slap1 = Hit("Attack1", 18, 0.667f, 0.815f, range: 2.8f, arc: 120, kind: AttackKind.Heavy, lunge: 0.6f, kb: 1.6f, apex: SumoApex1, from: SumoFrom1);
            var slap2 = Hit("Attack2", 20, 0.593f, 0.741f, range: 2.8f, arc: 130, kind: AttackKind.Heavy, lunge: 0.6f, kb: 1.6f, apex: SumoApex2, from: SumoFrom2);
            var stomp = Hit("Attack3", 26, 0.643f, 0.738f, range: 3.4f, arc: 360, kind: AttackKind.Heavy, lunge: 0.2f, kb: 2.2f, apex: SumoApex3, from: SumoFrom3);
            // embestida: el windup mínimo de un imparable (0.8 s) ya alcanza; el resto lo da el recorrido (la fase
            // activa del clip es la carrera, que Enemy estira lo que dura el carril)
            var charge = Hit("Special", 30, 0.3f, 0.7f, range: 2.4f, arc: 90, kind: AttackKind.Unblockable, lunge: 0f, kb: 3f, apex: SumoApexSpecial);
            charge.special = "charge"; charge.specialParam = 11f; charge.tracking = true;
            c.patterns = new[]
            {
                new AttackPattern { name = "Bofetadas", steps = new[] { slap1, slap2 }, weight = 2f, maxRange = 3.2f },
                new AttackPattern { name = "Pisotón", steps = new[] { stomp }, weight = 1f, maxRange = 3.4f, cooldown = 3f },
                new AttackPattern { name = "Embestida imparable", steps = new[] { charge }, weight = 1.4f, minRange = 3.5f, maxRange = 11f, cooldown = 5f },
            };
            return c;
        }

        public static EnemyConfig SumoMountain()
        {
            var c = Sumo();
            c.id = "sumo_mountain"; c.displayName = "Sumo de la Montaña";
            c.maxHealth = 200; c.tint = new Color(0.35f, 0.45f, 0.75f); c.tintStrength = 0.45f;
            c.ScaleSteps(1.2f, 1f);
            SumoMountainMoves(c);     // es el sumo de la montaña: pelea como tal aunque aparezca en otro lado
            return c;
        }

        // ------------------------------------------------------------------ jefes
        /// <summary>Gorō, el Martillo de Kodoyama (Minijefe): lento, golpes enormes, giro imparable que lo marea.</summary>
        public static EnemyConfig Goro()
        {
            var c = new EnemyConfig
            {
                // la primera barra (la falsa); la de la armadura es GoroBoss.armoredHealth (balance en goro_fight_sim.py)
                id = "goro", displayName = "Gorō", maxHealth = 1000, runSpeed = 3.8f, walkSpeed = 2f, turnSpeed = 5f,
                radius = 1.0f, height = 3.2f, scale = 1f, maxImbalance = 4, exhaustedTime = 4f, guardTime = 0.6f,
                poiseHits = 5, hyperArmor = true, knockbackResist = 0.9f, preferredDistance = 4.2f, detectRadius = 30f, loseRadius = 80f,
                finisherHealth = 0.12f, attackCooldown = new Vector2(0.9f, 1.8f),
                // el martillo rebota, se le resbala en la mano y cae por su peso (GoroAnims Parried: 16 cuadros); con los
                // 0.32 s de siempre daba la vuelta por encima en dos cuadros
                parriedRecoil = 0.5f,
                animGuard = "Idle", animCounter = "Combo1", animExhausted = "StunSpin", animHit = "Hit",
                animSpotted = "Spotted", animDeath = "Death", animParried = "Parried", deathClipFalls = true,
            };
            // contacto = activeStart de los clips nuevos (TeamAnims/GoroAnims.fbx): la cabeza del martillo llega en ese
            // cuadro; el golpe sísmico pega al aterrizar del salto, no al despegar. Alcance = dónde cae la cabeza del
            // martillo (GoroAnims.fbx.json, 3.66-3.90 m del centro) más medio ancho de la cabeza: con 3.4 el martillo se
            // veía pasar por encima de Kaito sin pegarle
            var c1 = Hit("Combo1", 22, 0.5472f, 0.6226f, range: 3.8f, arc: 130, kind: AttackKind.Heavy, lunge: 1.2f, telegraph: 0.2f, kb: 1.8f, apex: 0.3962f, from: 0.4151f, to: 0.5472f);
            var c2 = Hit("Combo2", 24, 0.5532f, 0.617f, range: 3.9f, arc: 130, kind: AttackKind.Heavy, lunge: 1.2f, kb: 1.8f, apex: 0.383f, from: 0.4043f, to: 0.5532f);
            var c3 = Hit("Combo3", 28, 0.5686f, 0.6275f, range: 4.0f, arc: 160, kind: AttackKind.Heavy, lunge: 1.0f, kb: 2.4f, apex: 0.4314f, from: 0.451f, to: 0.5686f);
            var slam = Hit("Heavy", 38, 0.625f, 0.6563f, range: 3.4f, arc: 360, kind: AttackKind.Unblockable, lunge: 0.5f, telegraph: 0.3f, kb: 3f, apex: 0.5f, from: 0.5156f, to: 0.625f);
            slam.special = "slam"; slam.specialParam = 4.6f;
            // el giro barre con la cabeza a ~3.9 m del eje: 2.8 dejaba pasar el martillo por Kaito sin daño
            var spin = Hit("Spin", 20, 0.288f, 0.848f, range: 3.6f, arc: 360, kind: AttackKind.Unblockable, lunge: 0f, telegraph: 0.15f, kb: 2.5f, apex: 0.242f);
            spin.special = "spin"; spin.specialParam = 3.8f;
            var slam2 = slam.Clone(); slam2.specialParam = 6f; slam2.damage = 42;
            // fase 1 = la primera barra (la que se "gana"); 'Terremoto' recién en su segunda mitad (GoroBoss.CurrentPhase 1).
            // La armadura de roca (fase 2) pelea con GoroPhase2
            c.patterns = new[]
            {
                new AttackPattern { name = "Martillazo", steps = new[] { c1 }, weight = 1.2f, maxRange = 4f, maxPhase = 1 },
                new AttackPattern { name = "Doble martillazo", steps = new[] { c1, c2 }, weight = 1.5f, maxRange = 4f, maxPhase = 1 },
                new AttackPattern { name = "Combo completo", steps = new[] { c1, c2, c3 }, weight = 1.2f, maxRange = 4f, minPhase = 0, maxPhase = 1 },
                new AttackPattern { name = "Torbellino", steps = new[] { spin }, weight = 1f, maxRange = 9f, cooldown = 9f, exhaustAfter = true, maxPhase = 1 },
                new AttackPattern { name = "Terremoto", steps = new[] { c1, slam2 }, weight = 1.3f, maxRange = 5f, cooldown = 7f, minPhase = 1, maxPhase = 1 },
            };
            GoroPhase2(c, c1, c2, c3, slam, slam2, spin);
            return c;
        }

        /// <summary>
        /// Gorō armado (fase 2, GoroBoss.CurrentPhase 2): los mismos golpes más pesados y con variantes (GoroAnims.fbx.json):
        /// Combo1B amaga y pega 0.6 s tarde, Combo2B barre a ras del piso desde la izquierda, Combo3B bombea arriba antes de
        /// bajar, combos de tres y cuatro golpes, el SlamWave clava el martillo y la onda sale por el piso (imparable, carril
        /// rojo) y la AVALANCHA: dos martillazos al piso, ruge al cielo y la montaña le tira rocas por carriles rojos
        /// (GoroAvalanche). La armadura rebota los cortes mientras carga cada golpe (GoroBoss.ArmorWindow).
        /// </summary>
        public static void GoroPhase2(EnemyConfig c, AttackDef c1, AttackDef c2, AttackDef c3, AttackDef slam, AttackDef slam2, AttackDef spin)
        {
            // normalizados de los clips de la fase 2 (apex / contacto-fin): la cabeza cae a 3.66-3.90 m
            var c1b = Hit("Combo1B", 26, 0.6308f, 0.6923f, range: 3.8f, arc: 130, kind: AttackKind.Heavy, lunge: 1.4f, kb: 2f, apex: 0.4923f, from: 0.5077f, to: 0.6308f);
            c1b.windup = 1.2f;
            var c2b = Hit("Combo2B", 24, 0.5102f, 0.5918f, range: 3.8f, arc: 170, kind: AttackKind.Heavy, lunge: 1.0f, kb: 2.2f, apex: 0.3673f, from: 0.3878f, to: 0.5102f);
            c2b.windup = 0.7f;
            var c3b = Hit("Combo3B", 30, 0.6563f, 0.7031f, range: 4.0f, arc: 160, kind: AttackKind.Heavy, lunge: 1.5f, kb: 2.6f, apex: 0.5f, from: 0.5156f, to: 0.6563f);
            c3b.windup = 1.2f;
            // la onda: el martillo cae a 3.9 m y la onda sale por el piso hasta 'specialParam' m más (GoroBoss "slamwave").
            // La fase activa es la arada entera (f34-f43): GoroBoss la estira lo que tarda la onda en llegar al final. El
            // aviso es el martillo arrastrado en el piso (apex f24); la suelta es el molino por el costado (10 cuadros) a 1.2x
            var wave = Hit("SlamWave", 40, 0.5312f, 0.6719f, range: 3.9f, arc: 60, kind: AttackKind.Unblockable, lunge: 1.0f, kb: 3f, apex: 0.375f, from: 0.3906f, to: 0.5312f);
            wave.special = "slamwave"; wave.specialParam = 10f; wave.windup = 1.25f; wave.releaseRate = 1.2f;
            // la avalancha no pega con el martillo: el aviso y el golpe son de cada roca (GoroAvalanche). Contacto = "call"
            // (f60 de 90) y apex al final de la vuelta a la guardia (f56): con el apex en el segundo martillazo la vuelta
            // caía en la suelta y se tocaba acelerando hasta 1.7x
            var aval = Hit("AvalancheSummon", 0, 0.6667f, 0.8333f, range: 30f, arc: 360, kind: AttackKind.Unblockable, lunge: 0f, kb: 2.6f, apex: 0.6222f);
            aval.special = "avalanche"; aval.specialParam = 24f; aval.releaseRate = 1f; aval.tracking = false;
            var spin2 = spin.Clone(); spin2.specialParam = 4.4f; spin2.damage = 24;
            var c1f = c1.Clone(); c1f.speed = 1.1f;
            var c2f = c2.Clone(); c2f.speed = 1.1f;
            var c3f = c3.Clone(); c3f.speed = 1.05f;
            var list = new System.Collections.Generic.List<AttackPattern>(c.patterns)
            {
                new AttackPattern { name = "Amague de piedra", steps = new[] { c1b }, weight = 1.0f, maxRange = 4.2f, minPhase = 2 },
                new AttackPattern { name = "Barrido bajo", steps = new[] { c1f, c2b }, weight = 1.1f, maxRange = 4.2f, minPhase = 2 },
                new AttackPattern { name = "Derrumbe", steps = new[] { c1f, c2b, c3b }, weight = 1.3f, maxRange = 4.2f, minPhase = 2 },
                new AttackPattern { name = "Cuatro martillazos", steps = new[] { c1b, c2f, c3f, c2b }, weight = 0.9f, maxRange = 4.2f, minPhase = 2, cooldown = 6f },
                new AttackPattern { name = "Onda de Kodoyama", steps = new[] { wave }, weight = 1.0f, maxRange = 7f, minPhase = 2, cooldown = 6f },
                new AttackPattern { name = "Martillo y onda", steps = new[] { c1f, wave }, weight = 1.0f, maxRange = 4.5f, minPhase = 2, cooldown = 8f },
                new AttackPattern { name = "Terremoto de piedra", steps = new[] { c2b, slam2 }, weight = 0.9f, maxRange = 5f, minPhase = 2, cooldown = 8f },
                new AttackPattern { name = "Torbellino de piedra", steps = new[] { spin2 }, weight = 0.8f, maxRange = 9f, minPhase = 2, cooldown = 11f, exhaustAfter = true },
                new AttackPattern { name = GoroAvalanchePattern, steps = new[] { aval }, weight = 1.2f, maxRange = 40f, minPhase = 2, cooldown = 20f },
                // en las dos fases y al final: Enemy.PickPattern cae en el último patrón si el sorteo se pasa por redondeo
                new AttackPattern { name = "Golpe sísmico", steps = new[] { slam }, weight = 1f, maxRange = 5f, cooldown = 6f },
            };
            c.patterns = list.ToArray();
        }

        /// <summary>Nombre del patrón de la avalancha (GoroBoss la fuerza al empezar la fase 2 y le da su pausa al final).</summary>
        public const string GoroAvalanchePattern = "Avalancha";

        /// <summary>
        /// Mizuchi, el Gran Koi de la Cascada Kohan (jefe del lago): un koi espíritu de 7.5 m con el Sello del Agua clavado
        /// en el lomo. Golpes desviables con aviso dorado (mordida, aletazos, coletazo si Kaito se le pone detrás, perlas
        /// que el parry perfecto devuelve) e imparables rojos que siempre se pueden esquivar corriendo (salto del dragón,
        /// chorro). Fase 2 (68 %): corrompido, inunda la plataforma; combo de ritmo, peloteo de la perla, chorro barrido,
        /// la ola de la cascada y los pilares de agua. Fase 3 (38 %): perlas de tormenta y el torrente largo. Desde cerca, la
        /// retirada abre los especiales de distancia. Los especiales los maneja MizuchiBoss. Tiempos de las hojas de contacto de Art/Characters/Mizuchi/Mizuchi.fbx.json (apex = pose cargada,
        /// activeStart = contacto); la mordida ya adelanta el cuerpo 0.6 m en el clip.
        /// </summary>
        public static EnemyConfig Mizuchi()
        {
            // 1440 (antes 720): pedido de vida doble para que la partida dure ~1 h. Con 500 el bot de pruebas lo liberaba en
            // ~40 s de pelea; con 1440, la retirada y las fases nuevas el bot "bueno" pelea ~80 s por intento (simulado)
            var c = new EnemyConfig
            {
                id = "mizuchi", displayName = "Mizuchi", maxHealth = 1440 * MizuchiBoss.HealthScale, runSpeed = 5f, walkSpeed = 2.4f, turnSpeed = 4.5f,
                // radio = medio cuerpo (1.95 m de ancho) más algo de aleta; altura 3 m: AimPoint a 1.65 m, el eje del cuerpo
                radius = 1.3f, height = 3f, scale = 1f, maxImbalance = 4, exhaustedTime = 3.4f, guardTime = 1.2f,
                poiseHits = 3, hyperArmor = true, knockbackResist = 0.95f, parriedRecoil = 0.4f, staggerTime = 0.3f,
                preferredDistance = 4.5f, detectRadius = 30f, loseRadius = 80f, finisherHealth = 0.12f,
                attackCooldown = new Vector2(0.8f, 1.6f),
                // contraataque: muestra el flanco (Guard) antes del golpe; con FinR barría con la aleta sin pegar
                animGuard = "Guard", animCounter = "Guard", animExhausted = "Exhausted", animHit = "Hit",
                animSpotted = "Roar", animDeath = "Freed", animParried = "Parried",
            };
            // ---- fase 1
            // embestidas cortas: el tope de Enemy se mide con el radio del cuerpo (1.3) y la boca está 2.9 m adelante;
            // con más avance el hocico atravesaba a Kaito
            var bite = Hit("Bite", 16, 0.5758f, 0.697f, range: 3.4f, arc: 70, lunge: 0.6f, telegraph: 0.22f, kb: 1f, apex: 0.4545f);
            bite.sfx = "koi_snap";
            var finL = Hit("FinL", 14, 0.5556f, 0.6667f, range: 3.3f, arc: 150, lunge: 0.5f, telegraph: 0.15f, apex: 0.4074f);
            var finR = Hit("FinR", 14, 0.4167f, 0.5417f, range: 3.3f, arc: 150, lunge: 0.4f, apex: 0.25f);
            finL.sfx = finR.sfx = "fin_whoosh";
            // el coletazo barre el disco entero desde el centro del cuerpo y no corrige la puntería: castiga quedarse detrás
            var tail = Hit("TailWhip", 22, 0.5476f, 0.7143f, range: 4.6f, arc: 360, kind: AttackKind.Heavy, lunge: 0f, telegraph: 0.28f, kb: 2.4f, apex: 0.4524f);
            tail.tracking = false; tail.sfx = "tail_crack";
            // perlas: el paso no pega, pegan las perlas (desviables; el parry perfecto las devuelve)
            var pearls = Hit("Spit", 10, 0.5556f, 0.5833f, range: 14f, arc: 60, lunge: 0f, telegraph: 0.25f, kb: 0.8f, apex: 0.4444f);
            pearls.name = "Perlas"; pearls.special = "pearls"; pearls.specialParam = 3;
            // salto del dragón: se zambulle, nada bajo el agua y salta sobre Kaito (disco rojo de 3.6 m)
            var dive = Hit("Dive", 30, 0.9f, 0.95f, range: 3.6f, arc: 360, kind: AttackKind.Unblockable, lunge: 0f, kb: 3.2f);
            dive.special = "dive"; dive.specialParam = 3.6f; dive.tracking = false;
            // chorro: apunta, se traba 0.75 s antes de disparar y la línea queda fija (un paso al costado alcanza)
            var jet = Hit("Jet", 26, 0.5455f, 0.7576f, range: 11f, arc: 20, kind: AttackKind.Unblockable, lunge: 0f, telegraph: 0.3f, kb: 2.6f, apex: 0.4848f);
            jet.special = "jet"; jet.specialParam = 11f; jet.tracking = false; jet.sfx = "jet_fire";
            // ---- fase 2: el torrente no retrocede con el parry (la postura igual suma) y cierra con un coletazo demorado
            var tBite = Torrente(bite); var tFinL = Torrente(finL); var tFinR = Torrente(finR); var tTail = Torrente(tail);
            tTail.telegraph = 0.45f;
            var rally = Hit("Spit", 18, 0.5556f, 0.5833f, range: 14f, arc: 60, lunge: 0f, telegraph: 0.25f, kb: 2f, apex: 0.4444f);
            rally.name = "Tama-asobi"; rally.special = "rally";
            // el barrido se traba 1 s antes (abanico más ancho que la línea): con más aviso la mira vive ~0.4 s antes de
            // trabarse y se lee "apunta, se traba" como en el chorro (con 0.3 la mira duraba 0.1-0.2 s)
            var sweep = jet.Clone(); sweep.name = "Chorro barrido"; sweep.special = "jetsweep"; sweep.telegraph = 0.7f;
            var wave = Hit("GreatWave", 24, 0.354f, 0.396f, range: 0.1f, arc: 360, kind: AttackKind.Unblockable, lunge: 0f, kb: 3f, apex: 0.25f);
            wave.special = "greatwave"; wave.tracking = false;
            var pillars = Hit("Roar", 20, 0.3f, 0.35f, range: 0.1f, arc: 360, kind: AttackKind.Unblockable, lunge: 0f, kb: 2.5f);
            pillars.special = "pillars"; pillars.specialParam = 4; pillars.tracking = false;
            // ---- fase 3
            var storm = pearls.Clone(); storm.name = "Perlas de tormenta"; storm.special = "storm"; storm.specialParam = 5; storm.damage = 8;
            // retirada (MizuchiBoss.Pacing): salta lejos de Kaito y abre un especial de distancia (sin daño, sin aviso)
            var retreat = Hit("Dive", 0, 0.9f, 0.95f, lunge: 0f);
            retreat.name = "Retirada"; retreat.special = "retreat"; retreat.tracking = false;
            // los especiales grandes piden 2 m o más: el contraataque (Enemy.Counter elige con distancia 1) es siempre un golpe corto
            c.patterns = new[]
            {
                new AttackPattern { name = "Mordida", steps = new[] { bite }, weight = 1.6f, maxRange = 3.6f, maxAngle = 70f },
                new AttackPattern { name = "Aletazo", steps = new[] { finL, finR }, weight = 1.5f, maxRange = 3.4f, maxAngle = 110f },
                new AttackPattern { name = "Mordida y aletazo", steps = new[] { bite, finL, finR }, weight = 1.1f, maxRange = 3.6f, maxAngle = 70f, maxPhase = 0 },
                new AttackPattern { name = "Coletazo", steps = new[] { tail }, weight = 2.5f, maxRange = 4.8f, minAngle = 100f, cooldown = 4f },
                new AttackPattern { name = "Perlas del Lago", steps = new[] { pearls }, weight = 1.2f, minRange = 6f, maxRange = 14f, cooldown = 5f, maxPhase = 0 },
                new AttackPattern { name = "Salto del Dragón", steps = new[] { dive }, weight = 1f, minRange = 2f, maxRange = 30f, cooldown = 12f },
                new AttackPattern { name = "Chorro", steps = new[] { jet }, weight = 0.9f, minRange = 4f, maxRange = 11f, maxAngle = 35f, cooldown = 9f, maxPhase = 0 },
                new AttackPattern { name = "Torrente", steps = new[] { tBite, tFinL, tFinR, tTail }, weight = 1.6f, maxRange = 3.6f, maxAngle = 70f, minPhase = 1 },
                new AttackPattern { name = "Tama-asobi", steps = new[] { rally }, weight = 1f, minRange = 6f, maxRange = 14f, cooldown = 14f, minPhase = 1 },
                new AttackPattern { name = "Chorro barrido", steps = new[] { sweep }, weight = 1f, minRange = 4f, maxRange = 9f, maxAngle = 35f, cooldown = 8f, minPhase = 1 },
                new AttackPattern { name = "Ola de la Cascada", steps = new[] { wave }, weight = 0.9f, minRange = 2f, maxRange = 30f, cooldown = 15f, minPhase = 1 },
                new AttackPattern { name = "Pilares", steps = new[] { pillars }, weight = 0.8f, minRange = 2f, maxRange = 30f, cooldown = 20f, minPhase = 1 },
                new AttackPattern { name = "Perlas de tormenta", steps = new[] { storm }, weight = 1f, minRange = 6f, maxRange = 14f, cooldown = 6f, minPhase = 2 },
                // ---- pelea larga (vida doble): otra mezcla de cerca y la retirada que abre los especiales de distancia,
                // que contra alguien pegado al koi no salían nunca (piden 4-6 m o más)
                new AttackPattern { name = "Aletas y mordida", steps = new[] { finL, finR, bite }, weight = 1f, maxRange = 3.4f, maxAngle = 110f },
                new AttackPattern { name = "Torrente largo", steps = new[] { tBite, tFinL, tFinR, tBite, tTail }, weight = 1.2f, maxRange = 3.6f, maxAngle = 70f, minPhase = 2 },
                new AttackPattern { name = "Perlas desde lejos", steps = new[] { retreat, pearls }, weight = 0.9f, maxRange = 4f, cooldown = 11f, maxPhase = 0 },
                new AttackPattern { name = "Chorro desde lejos", steps = new[] { retreat, jet }, weight = 0.7f, maxRange = 4f, cooldown = 13f, maxPhase = 0 },
                new AttackPattern { name = "Peloteo desde lejos", steps = new[] { retreat, rally }, weight = 0.8f, maxRange = 4f, cooldown = 16f, minPhase = 1 },
                new AttackPattern { name = "Barrido desde lejos", steps = new[] { retreat, sweep }, weight = 0.8f, maxRange = 4f, cooldown = 12f, minPhase = 1 },
                new AttackPattern { name = "Tormenta desde lejos", steps = new[] { retreat, storm }, weight = 1f, maxRange = 4f, cooldown = 10f, minPhase = 2 },
            };
            // con la vida doble, el daño de todo a MizuchiBoss.DamageScale (perlas, saltos, ola y pilares incluidos)
            c.ScaleSteps(MizuchiBoss.DamageScale, 1f);
            return c;
        }

        static AttackDef Torrente(AttackDef a)
        {
            var t = a.Clone();
            t.name = "Torrente " + a.name;
            t.noRecoil = true;
            return t;
        }

        /// <summary>Chikuō, el Maestro del Bambú (Enemies/Bosses/BambooMasterBoss.cs). Sus golpes salen de los tiempos de
        /// sus clips y van en BambooMasterMoves; el id "ozeki" queda por las partidas, las banderas y el sello.</summary>
        public static EnemyConfig Ozeki() => BambooMasterMoves.Config();

        // ------------------------------------------------------------------ movimientos de las variantes de zona
        // EnemyVariants los suma según la región donde aparece el enemigo. Todo dentro de la gramática del aviso:
        // dorado = parry, rojo = dash; cada zona agrega una mezcla propia, no golpes más rápidos.

        /// <summary>Ninja de la montaña: más pesado y lento; dos cortes y un tajo de arriba IMPARABLE (rompeguardia).</summary>
        public static void NinjaMountainMoves(EnemyConfig c)
        {
            c.ScaleSteps(1.1f, 0.92f);
            var a1 = Hit("Attack1", 14, 0.583f, 0.75f, telegraph: 0.15f, speed: 0.92f, apex: NinjaApex1, from: NinjaFrom1, air: true);
            var a2 = Hit("Attack2", 14, 0.455f, 0.636f, speed: 0.92f, apex: NinjaApex2, from: NinjaFrom2, air: true);
            // el tajo de arriba con todo el peso: 0.95 s de carga (VariantMotion lo echa atrás antes de soltar)
            var breaker = Hit("Attack3", 20, 0.583f, 0.694f, range: 2.6f, arc: 120, kind: AttackKind.Unblockable, lunge: 1.3f, kb: 2.2f, apex: NinjaApex3, from: NinjaFrom3, air: true);
            breaker.windup = 0.95f; breaker.name = "Rompeguardia";
            Weight(c, "Combo de 3", 1f);
            Add(c, new AttackPattern { name = "Avalancha", steps = new[] { a1, a2, breaker }, weight = 1.6f, maxRange = 2.8f, cooldown = 5f },
                   new AttackPattern { name = "Rompeguardia", steps = new[] { breaker }, weight = 0.6f, maxRange = 2.8f, cooldown = 7f });
        }

        /// <summary>Ninja del lago: fluido; un corte y un remolino de 360° (dorado) y el arpón que llega de lejos.</summary>
        public static void NinjaLakeMoves(EnemyConfig c)
        {
            var a1 = Hit("Attack1", 12, 0.583f, 0.75f, telegraph: 0.1f, apex: NinjaApex1, from: NinjaFrom1, air: true);
            // el remolino tiene su clip (Whirl: una vuelta entera en el aire, los pies giran con el cuerpo); sin él vuelve al
            // Attack2 que VariantMotion gira entero
            var whirl = Hit("Whirl", 14, 0.556f, 0.667f, range: 2.7f, arc: 360, kind: AttackKind.Heavy, lunge: 1.1f, telegraph: 0.1f, kb: 1.4f, apex: NinjaApexWhirl, from: NinjaFromWhirl, air: true);
            whirl.name = "Remolino";
            whirl.fallback = Fallback(Hit("Attack2", 14, 0.455f, 0.636f, lunge: 1.1f, apex: NinjaApex2, from: NinjaFrom2, air: true));
            // el arpón es la estocada voladora (clip Thrust) con menos recorrido: en el vuelo los pies van con el avance y
            // caen cuando terminó, así que con 2.4 m no patinan (build_team_anims lo mide con el reloj del juego)
            var harpoon = Hit("Thrust", 16, 0.525f, 0.625f, range: 3.2f, kind: AttackKind.Heavy, lunge: 2.4f, kb: 1.2f, apex: NinjaApexThrust, from: NinjaFromThrust, air: true);
            harpoon.windup = 0.75f; harpoon.name = "Arpón";
            Remove(c, "Estocada");
            // alcance real: 3.2 + 2.4 de embestida + el radio de Kaito = 5.95 m; arranca a 5.5 como mucho (si no, el
            // anillo se cerraba sobre un golpe que no llegaba y enseñaba un parry falso)
            Add(c, new AttackPattern { name = "Marea", steps = new[] { a1, whirl }, weight = 1.6f, maxRange = 2.8f },
                   new AttackPattern { name = "Arpón", steps = new[] { harpoon }, weight = 1.2f, minRange = 2.8f, maxRange = 5.5f, cooldown = 4f });
        }

        /// <summary>Ninja del bambú: acrobático; entra de un salto desde 4-6.5 m y después de un combo se repliega.</summary>
        public static void NinjaBambooMoves(EnemyConfig c)
        {
            var a1 = Hit("Attack1", 12, 0.583f, 0.75f, telegraph: 0.12f, apex: NinjaApex1, from: NinjaFrom1, air: true);
            var a2 = Hit("Attack2", 12, 0.455f, 0.636f, apex: NinjaApex2, from: NinjaFrom2, air: true);
            // el salto: el aviso dura lo que tarda en cerrar la distancia (VariantMotion lo levanta en el aire)
            // el clip Leap salta en un arco de 1 m con la embestida entera en el aire (0.51 s desde la suelta) y el golpe
            // pega bajando; sin él vuelve al Attack3, que VariantMotion levanta (y patina en la pausa: 4.4 m no entran en su suelta)
            // con Kaito cerca (desde 3.8 m) cae más corto: cortado por el imán a mitad del vuelo chocaba con una pared invisible
            var leap = Hit("Leap", 16, 0.708f, 0.792f, range: 2.4f, kind: AttackKind.Heavy, lunge: 4.4f, kb: 1.4f, apex: NinjaApexLeap, from: NinjaFromLeap, air: true);
            leap.windup = 0.8f; leap.name = "Salto";
            leap.fallback = Fallback(Hit("Attack3", 16, 0.583f, 0.694f, lunge: 4.4f, apex: NinjaApex3, from: NinjaFrom3, air: true));
            // repliegue: salto atrás de 3 m sin daño (queda a tiro de otro salto). Su clip (HopBack) se agacha, despega en
            // 'from' y cae en activeEnd; sin él vuelve al Spotted que VariantMotion levanta
            var hop = Hit("HopBack", 0, 0.219f, 0.844f, lunge: 0f, telegraph: 0.12f, apex: 0.156f, from: 0.219f);
            hop.special = "hop_back"; hop.specialParam = 3f; hop.name = "Repliegue";
            hop.fallback = Fallback(Hit("Spotted", 0, 0.15f, 0.6f, lunge: 0f, telegraph: 0.12f));
            Remove(c, "Estocada");
            // alcance real del salto: 2.4 + 4.4 + 0.35 = 7.15 m. El patrón se elige el primer frame que entra en rango
            // (corriendo hacia Kaito arranca casi siempre en el borde): a 6.6 queda medio metro de margen
            Add(c, new AttackPattern { name = "Salto", steps = new[] { leap }, weight = 1.5f, minRange = 3.8f, maxRange = 6.6f, cooldown = 3.5f },
                   new AttackPattern { name = "Golpe y repliegue", steps = new[] { a1, a2, hop }, weight = 1.6f, maxRange = 2.8f });
        }

        /// <summary>Sumo de la montaña: más lento y pesado; el pisotón es un shiko IMPARABLE con un disco de 4.6 m.</summary>
        public static void SumoMountainMoves(EnemyConfig c)
        {
            c.ScaleSteps(1.1f, 0.9f);
            var stomp = Hit("Attack3", 26, 0.643f, 0.738f, range: 3.4f, arc: 360, kind: AttackKind.Unblockable, lunge: 0.2f, telegraph: 0.15f, kb: 2.6f, apex: SumoApex3, from: SumoFrom3);
            stomp.special = "slam"; stomp.specialParam = 4.6f; stomp.tracking = false; stomp.name = "Shiko D";
            Remove(c, "Pisotón");
            Add(c, new AttackPattern { name = "Shiko de nieve", steps = new[] { stomp }, weight = 1.2f, maxRange = 4f, cooldown = 5f });
        }

        /// <summary>Sumo del lago: una bofetada y el empujón a dos manos que te saca lejos (dorado, con salpicón).</summary>
        public static void SumoLakeMoves(EnemyConfig c)
        {
            var slap = Hit("Attack1", 18, 0.667f, 0.815f, range: 2.8f, arc: 120, kind: AttackKind.Heavy, lunge: 0.6f, kb: 1.6f, apex: SumoApex1, from: SumoFrom1);
            // el morote tiene su clip (dos pasos que empujan con los dos brazos estirados, los pies nunca clavados mientras
            // avanza); sin él vuelve al Attack2 con las manos de SumoPoser (el pie de atrás patinaba 1 m)
            var morote = Hit("Morote", 20, 0.611f, 0.75f, range: 3.0f, arc: 120, kind: AttackKind.Heavy, lunge: 1.6f, kb: 3.8f, apex: SumoApexMorote, from: SumoFromMorote);
            morote.name = "Morote";
            morote.fallback = Fallback(Hit("Attack2", 20, 0.593f, 0.741f, lunge: 1.6f, apex: SumoApex2, from: SumoFrom2));
            Weight(c, "Bofetadas", 1.2f);
            Add(c, new AttackPattern { name = "Oleaje", steps = new[] { slap, morote }, weight = 1.6f, maxRange = 3.4f });
        }

        /// <summary>Sumo del bambú: se corre de costado de un salto (la finta) y embiste desde ahí.</summary>
        public static void SumoBambooMoves(EnemyConfig c)
        {
            // su clip (HopSideR, y HopSideL cuando Enemy elige el otro lado) se hunde, despega en 'from' y cae en activeEnd;
            // sin él vuelve al Spotted que VariantMotion levanta
            var feint = Hit("HopSideR", 0, 0.306f, 0.722f, lunge: 0f, telegraph: 0.1f, apex: 0.222f, from: 0.306f);
            feint.special = "hop_side"; feint.specialParam = 2.6f; feint.name = "Finta";
            feint.fallback = Fallback(Hit("Spotted", 0, 0.15f, 0.7f, lunge: 0f, telegraph: 0.1f));
            var charge = Hit("Special", 30, 0.3f, 0.7f, range: 2.4f, arc: 90, kind: AttackKind.Unblockable, lunge: 0f, kb: 3f, apex: SumoApexSpecial);
            charge.special = "charge"; charge.specialParam = 13f; charge.tracking = true;
            Add(c, new AttackPattern { name = "Finta y embestida", steps = new[] { feint, charge }, weight = 1.5f, minRange = 3.5f, maxRange = 10f, cooldown = 5f });
        }

        /// <summary>El clip de siempre (estado y tiempos de un Hit) para un golpe con clip propio: Enemy lo usa si el
        /// controller no tiene el estado nuevo.</summary>
        static AttackClipFallback Fallback(AttackDef a) =>
            new AttackClipFallback { state = a.state, activeStart = a.activeStart, activeEnd = a.activeEnd, apex = a.apex, lungeFrom = a.lungeFrom, lungeAir = a.lungeAir };

        static void Add(EnemyConfig c, params AttackPattern[] add)
        {
            var list = new System.Collections.Generic.List<AttackPattern>(c.patterns ?? new AttackPattern[0]);
            list.AddRange(add);
            c.patterns = list.ToArray();
        }

        static void Remove(EnemyConfig c, string pattern)
        {
            if (c.patterns == null) return;
            c.patterns = System.Array.FindAll(c.patterns, p => p != null && p.name != pattern);
        }

        static void Weight(EnemyConfig c, string pattern, float w)
        {
            if (c.patterns != null) foreach (var p in c.patterns) if (p != null && p.name == pattern) p.weight = w;
        }

        /// <summary>
        /// Kokuyō, Señor del Clan Kurokage (jefe final). El arquetipo sigue llamándose "kage" (banderas del guardado, la
        /// puerta y el final); sus golpes, tiempos y actos viven en Enemies/Bosses (KokuyoMoves, KokuyoBoss). Los clones
        /// de sombra del Kage viejo se retiraron: su sombra arrancada (KageShadow) los reemplaza.
        /// </summary>
        public static EnemyConfig Kage() => KokuyoMoves.Kokuyo();
    }
}
