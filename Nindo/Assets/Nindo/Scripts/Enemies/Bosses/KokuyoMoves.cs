using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Golpes y patrones de Kokuyō (jefe final, arquetipo "kage") y de su sombra arrancada, Kage. Los tiempos de cada
    /// golpe salen de KokuyoTimings (lo que mide el build de Blender), así el aviso, la sombra y el tajo no se despegan
    /// del clip. Contrato de lectura (judge_final):
    ///  * DÓNDE: el aviso en el suelo desde que arranca el paso (dorado = parry, rojo con zona = dash).
    ///  * CUÁNDO: un único "¡ahora!" a 0.36 s del golpe (GoLead): el filo destella, suena el hyōshigi y, en el Acto 1,
    ///    la sombra golpea. Desde ahí deja de apuntar: correrse sirve.
    ///  * cada imparable deja una ventana de castigo; nunca pegan el cuerpo y la sombra a menos de 0.9 s.
    /// La pausa en el apex (la pose del aviso) se acorta por acto: 0.42 s, 0.30 s, 0.22 s.
    /// </summary>
    public static class KokuyoMoves
    {
        /// <summary>El "¡ahora!": el filo destella, la sombra golpea y la puntería se traba (s antes del impacto).</summary>
        public const float GoLead = 0.36f;
        /// <summary>Pausa en el apex de los desviables por acto (1..3).</summary>
        static readonly float[] ParryHold = { 0f, 0.42f, 0.30f, 0.22f };
        /// <summary>Los imparables ya tienen una anticipación larga (0.9-1 s): solo un respiro en el apex.</summary>
        static readonly float[] DodgeHold = { 0f, 0.15f, 0.08f, 0.08f };
        /// <summary>StepTimeline.MinWindup multiplica por 0.9 desde la fase 1 (Actos 2 y 3): se compensa para que las
        /// pausas de arriba sean las que se ven.</summary>
        const float PhaseWindupMul = 0.9f;

        public const string Cut = "k_cut", Thrust = "k_thrust", Sweep = "k_sweep", Rift = "k_rift", Sink = "k_sink", NoHit = "k_none";
        /// <summary>
        /// Los golpes de la sombra (KageShadow). Nobi (Acto 1): pegada a sus pies, se estira por el piso hasta Kaito y
        /// corta. Giri (Actos 2 y 3): la figura de tinta corta como él (en el eclipse sale de la oscuridad). Nui y
        /// Watari (Acto 2): se desliza bajo Kaito y estalla / cruza el patio. Nobi y Giri se desvían (dorado).
        /// </summary>
        public const string Nobi = "kage_nobi", Giri = "kage_giri", Nui = "kage_nui", Watari = "kage_watari";

        /// <summary>Grieta de obsidiana del Rompecascos: carril de 14 x 2 m que avanza a 28 m/s desde el golpe.</summary>
        public const float RiftLength = 14f, RiftHalfWidth = 1.0f, RiftSpeed = 28f;
        public const float RiftDamage = 26f * DamageScale, RiftKnockback = 2.5f;

        /// <summary>
        /// Las perillas del balance final, todas juntas: HealthScale multiplica la vida pedida (1800, el doble de antes; los
        /// actos y sus tramos se reparten solos con cualquier vida), DamageScale el daño de diseño de todo lo que pega (él,
        /// la sombra, la grieta) y el sustento de Kaito: StageHeal en cada corte de tramo de un acto (KokuyoBoss.Pacing,
        /// como los tramos de la armadura de Gorō; con la vida de hoy son seis, dos por acto) y TransitionHeal /
        /// TransitionSpirit en cada cambio de acto (también al levantarse para la última resistencia). Las simulaciones
        /// leen estos números de acá (Tools/Dev/boss_sims/cs_knobs.py). Simulado con los bots de AutoPilot (kk_fix_run.py
        /// largo bueno,promedio,humano 200 ['{"stage_heal": [0, 35, 35, 35]}']; minutos simulados hasta ganar con los
        /// reintentos; "humano" = ve el anillo, se equivoca más de atrás y en la oscuridad):
        ///   vida 2700, daño 0.4, sin cura de tramo (lo de C2): bueno 2.0 min; promedio 5.6 min, 2.9 muertes y 20 % gana
        ///                          sin morir (corto para el bueno y el promedio se desgasta);
        ///   vida 5400, daño 0.33, sin cura de tramo: bueno 3.4 min; promedio 25 min y 11.5 muertes (no termina);
        ///   vida 5400, daño 0.33, tramos 35 / 35 / 35, el reintento por acto, el eclipse con sus dúos enteros y la
        ///                          primera rodilla con un parry: promedio 1.73 muertes y 29 % sin morir, 0.3 de ellas en
        ///                          el Último Desfile (llegaba sin vida; con la cura al levantarse, 1.23 y 39 %: el jefe final
        ///                          era el más fácil de ganar de una);
        ///   vida 5400, daño 0.33, tramos 35 / 35 / 20 (y 30 en el 2): promedio 2.16 muertes y 21 % (de más);
        ///   vida 5400, daño 0.33, tramos 35 / 35 / 25: bueno 3.6 min (casi nunca muere); promedio 6.1 min (p90 9.8), 1.65
        ///                          muertes y 28 % sin morir, 1.2 de ellas en el eclipse; humano 3.7 min.
        /// En Unity el bot tarda 0.92 veces lo simulado con Kokuyō (medido con el PlayClock en main 76be027: 'bot on bueno'
        /// 1:48 contra 1.96 min simulados; Tools/Dev/boss_sims/calibration.py): con 5400 el bueno ganaba en ~3.4 min de
        /// juego, corto. En minutos de juego (kk_fix_run.py largo bueno,promedio 200 '{"calib": true}', el daño de Kaito a
        /// 1/0.92):
        ///   vida 7200, daño 0.33, tramos 35 / 35 / 25: bueno 4.35 min; promedio 10.2 min y 4.5 muertes (no alcanza el sustento);
        ///   vida 7200, daño 0.33, tramos 60 / 60 / 50: promedio 6.9 min, 1.5 muertes (cura casi toda la vida en cada tramo);
        ///   vida 6600, daño 0.30, tramos 40 / 40 / 30: bueno 4.1 min; promedio 6.4 min, 1.4 muertes;
        ///   vida 7200, daño 0.31, tramos 50 / 50 / 45: bueno 4.35 min (p10-p90 4.05-4.7) sin morir; promedio 6.9 min (p90
        ///                          10.5), 1.4 muertes y 29 % sin morir, 1.0 de ellas en el eclipse (lo de hoy). Los actos duran
        ///                          ~72 / 87 / 80 s con el bueno; el eclipse sigue sirviendo el 99 % de los dúos. El promedio de verdad anduvo mejor que el calibrado (2:26 sin
        ///                          morir con lo de C2, contra 5 min y 2.2 muertes): puede que muera menos.
        /// Medido en Unity con eso (13 de octubre): bueno 4:41 y promedio 6:29, los dos sin morir (el promedio recibió 352
        /// de daño). La vida sube a 7560 (x4.2: el jefe final queda el más largo), el daño a x0.37 y los tramos a 40 / 40 /
        /// 35. Más vida alarga la
        /// pelea del bueno casi en proporción; más StageHeal le baja las muertes al promedio sin acortarla (la del eclipse es
        /// la que más pesa).
        /// </summary>
        public const float HealthScale = 4.2f, DamageScale = 0.37f;
        public const float TransitionHeal = 40f, TransitionSpirit = 30f;
        /// <summary>La cura de cada corte de tramo, por acto (1..3): un poco menos en el eclipse, que es el final (con la
        /// misma en los tres el bot promedio ganaba de una más seguido que contra los otros jefes).</summary>
        static readonly float[] StageHeal = { 0f, 40f, 40f, 35f };

        public static float StageHealOf(int act) => StageHeal[Mathf.Clamp(act, 1, 3)];
        /// <summary>Ichimonji: dentro de este radio la hoja pasa por encima de la cabeza de Kaito (la empuñadura va a
        /// 1.9 m y la punta baja a 0.97 m: a menos de ~2 m del centro la hoja corta arriba de 1.5 m). Sale del sidecar
        /// (safe_core_m), que es la única fuente: el disco pálido y el golpe usan el mismo número.</summary>
        public const float SweepCore = KokuyoTimings.IchimonjiSafeCore;

        static readonly Dictionary<string, KokuyoClip> clips = new Dictionary<string, KokuyoClip>
        {
            { "Kesagiri", KokuyoTimings.Kesagiri }, { "Gyakugiri", KokuyoTimings.Gyakugiri }, { "Tsuki", KokuyoTimings.Tsuki },
            { "TsukiRecover", KokuyoTimings.TsukiRecover }, { "Ichimonji", KokuyoTimings.Ichimonji }, { "KabutoWari", KokuyoTimings.KabutoWari },
            { "ShadowSink", KokuyoTimings.ShadowSink }, { "ShadowEmerge", KokuyoTimings.ShadowEmerge }, { "RecoverL", KokuyoTimings.RecoverL },
            { "RecoverHR", KokuyoTimings.RecoverHR },
        };

        /// <summary>Tiempos del clip de un paso (null si no es de Kokuyō).</summary>
        public static KokuyoClip ClipOf(AttackDef a) => a != null && clips.TryGetValue(a.state, out var c) ? c : null;

        // ------------------------------------------------------------------ golpes
        /// <summary>
        /// Golpe con sus propios tiempos (sin la curva genérica de los comunes). El avance del cuerpo lo hace el
        /// jefe con travel_m del clip (lunge = 0: con la embestida lineal los pies patinan). 'range' es lo más lejos que
        /// puede llegar (hoja + avance entero): lo usan el aviso de los bots y el tutorial; el golpe real se mide con
        /// el alcance de la hoja desde donde está en el impacto.
        /// </summary>
        static AttackDef K(KokuyoClip c, string name, float dmg, AttackKind kind, float arc, float kb, float hold, int act, string special)
        {
            float natural = c.Apex * c.Seconds / 0.85f + (c.Contact - c.Apex) * c.Seconds / c.ReleaseRate;
            float windup = natural + hold;
            if (act >= 2) windup /= PhaseWindupMul;
            float travel = c.Travel != null ? c.Travel[c.Travel.Length - 1] : 0f;
            return new AttackDef
            {
                name = name, state = c.State, damage = dmg * DamageScale, kind = kind, arc = arc, knockback = kb,
                range = c.Reach + travel, activeStart = c.Contact, activeEnd = c.ActiveEnd, apex = c.Apex, releaseRate = c.ReleaseRate,
                windup = windup, lunge = 0f, tracking = false, hitStop = 0.12f, shake = 0.4f, imbalance = 1f,
                sfx = "enemy_swing_heavy", special = special,
            };
        }

        /// <summary>Paso sin golpe (recuperación, hundirse en la sombra): el clip a su velocidad.</summary>
        static AttackDef R(KokuyoClip c, string special = NoHit) => new AttackDef
        {
            name = c.State, state = c.State, damage = 0f, activeStart = 0.02f, activeEnd = 0.02f, apex = 0f, lunge = 0f,
            tracking = false, special = special,
        };

        /// <summary>Los golpes de un acto (1..3): cada acto tiene sus propias pausas en el apex.</summary>
        sealed class Set
        {
            public AttackDef kesa, gyaku, tsuki, ichi, kabuto, emerge;
            public Set(int act)
            {
                float ph = ParryHold[act], dh = DodgeHold[act];
                kesa = K(KokuyoTimings.Kesagiri, "Corte del Monje", 24, AttackKind.Heavy, 120f, 1.6f, ph, act, Cut);
                gyaku = K(KokuyoTimings.Gyakugiri, "Luna Ascendente", 22, AttackKind.Heavy, 120f, 1.4f, ph, act, Cut);
                // la estocada ya tiene la anticipación más larga del juego (0.86 s de recogida + 0.42 de salto): media pausa
                tsuki = K(KokuyoTimings.Tsuki, "Colmillo", 28, AttackKind.Heavy, 40f, 2.4f, ph * 0.5f, act, Thrust);
                ichi = K(KokuyoTimings.Ichimonji, "Horizonte", 34, AttackKind.Unblockable, 240f, 3.0f, dh, act, Sweep);
                kabuto = K(KokuyoTimings.KabutoWari, "Rompecascos", 38, AttackKind.Unblockable, 50f, 2.5f, dh, act, Rift);
                emerge = K(KokuyoTimings.ShadowEmerge, "Paso de Sombra", 24, AttackKind.Heavy, 140f, 1.6f, ph, act, Cut);
            }
        }

        static readonly AttackDef recoverL = R(KokuyoTimings.RecoverL), recoverHR = R(KokuyoTimings.RecoverHR),
            tsukiRecover = R(KokuyoTimings.TsukiRecover), sink = R(KokuyoTimings.ShadowSink, Sink);

        static AttackPattern P(string name, float weight, float maxRange, float cooldown, params AttackDef[] steps) =>
            new AttackPattern { name = name, steps = steps, weight = weight, maxRange = maxRange, cooldown = cooldown };

        static ShadowCue Cue(int step, string move, ShadowSide side, bool before) => new ShadowCue { step = step, move = move, side = side, before = before };

        static DuetPattern D(string name, float weight, float maxRange, float cooldown, ShadowCue cue, params AttackDef[] steps) =>
            new DuetPattern { name = name, steps = steps, weight = weight, maxRange = maxRange, cooldown = cooldown, cues = new[] { cue } };

        /// <summary>Nombre del dúo del Acto 1 (KokuyoBoss lo deja en peso 0 hasta que la sombra atacó sola una vez).</summary>
        public const string DuetTeachName = "Sombra y Acero";

        /// <summary>
        /// Patrones de cada acto. Acto 1 enseña de a una cosa; el 2 suma la Escuela del Abuelo (corte, corte, estocada:
        /// el mismo ritmo del combo de Kaito, más lento) y el Paso de Sombra; el 3 encadena el Desfile (cuatro parries y
        /// un dash) y la Media Luna. Mezcla: ~70 % desviables, ~30 % imparables.
        /// Los dúos (DuetPattern) meten a la sombra en el combo del cuerpo, uno por acto como mínimo:
        ///  * Acto 1 "Sombra y Acero": la sombra se estira y corta mientras él levanta la nodachi despacio; después él.
        ///  * Acto 2 "Pinza": él corta, la sombra corta del otro lado de Kaito, él vuelve a cortar. "Amago": él carga y
        ///    corta la sombra primero. "Clavo y Colmillo": la sombra estalla bajo Kaito y él cruza con la estocada.
        ///  * Acto 3 "Media Luna Negra": él corta, la sombra sale de la oscuridad del otro lado, él barre (rojo).
        ///    "Eclipse Doble": sale de la oscuridad de costado y corta mientras él carga (los turnos de la sombra sola
        ///    alternan de lado: KokuyoBoss.Shadow).
        /// </summary>
        public static AttackPattern[] Act(int act)
        {
            var s = new Set(Mathf.Clamp(act, 1, 3));
            var monje = P("Corte del Monje", 1.6f, 5.0f, 0f, s.kesa, recoverL);
            var doble = P("Luna Doble", 1.8f, 5.0f, 0f, s.kesa, s.gyaku, recoverHR);
            var colmillo = P("Colmillo", 1.2f, 8.5f, 4f, s.tsuki, tsukiRecover); colmillo.minRange = 4f;
            var horizonte = P("Horizonte", 1.0f, 5.5f, 7f, s.ichi);
            var rompe = P("Rompecascos", 0.9f, 10f, 9f, s.kabuto); rompe.minRange = 2.5f;
            if (act <= 1)
            {
                var acero = D(DuetTeachName, 0.9f, 5.0f, 12f, Cue(0, Nobi, ShadowSide.Any, true), s.kesa, recoverL);
                return new AttackPattern[] { monje, doble, colmillo, horizonte, rompe, acero };
            }
            var escuela = P("Escuela del Abuelo", 1.6f, 5.0f, 0f, s.kesa, s.gyaku, s.tsuki, tsukiRecover);
            var paso = P("Paso de Sombra", 1.2f, 16f, 8f, sink, s.emerge, recoverHR);
            if (act == 2)
            {
                doble.weight = 1.2f; colmillo.weight = 0.9f; horizonte.weight = 0.7f; rompe.weight = 0.7f; escuela.weight = 1.3f; paso.weight = 1.0f;
                var pinza = D("Pinza", 1.2f, 5.0f, 8f, Cue(0, Giri, ShadowSide.Opposite, false), s.kesa, s.gyaku, recoverHR);
                var amago = D("Amago", 1.0f, 5.0f, 9f, Cue(0, Giri, ShadowSide.Flank, true), s.kesa, recoverL);
                var clavo = D("Clavo y Colmillo", 0.8f, 8.5f, 10f, Cue(0, Nui, ShadowSide.Any, true), s.tsuki, tsukiRecover); clavo.minRange = 4f;
                return new AttackPattern[] { doble, colmillo, horizonte, rompe, escuela, paso, pinza, amago, clavo };
            }
            doble.weight = 0.9f; colmillo.weight = 0.7f; horizonte.weight = 0.5f; rompe.weight = 0.5f; escuela.weight = 1.0f; paso.weight = 0.9f;
            var desfile = P("Desfile de los Cien Demonios", 1.3f, 5.0f, 10f, s.kesa, s.gyaku, s.kesa, s.tsuki, s.kabuto);
            var media = P("Media Luna", 1.0f, 5.0f, 6f, s.gyaku, s.ichi);
            var negra = D("Media Luna Negra", 1.1f, 5.0f, 9f, Cue(0, Giri, ShadowSide.Opposite, false), s.gyaku, s.ichi);
            var doble3 = D("Eclipse Doble", 1.0f, 5.0f, 9f, Cue(0, Giri, ShadowSide.Flank, true), s.kesa, recoverL);
            return new AttackPattern[] { doble, colmillo, horizonte, rompe, escuela, paso, desfile, media, negra, doble3 };
        }

        /// <summary>
        /// Lo que se suma en cada tramo de un acto (KokuyoBoss.Pacing): con la vida doble cada acto dura el doble y repetía
        /// lo mismo. En cada corte entra un patrón que mezcla lo que el acto ya enseñó, encadenando poses que coinciden.
        /// Tramo 1 (la mitad; con la vida de hoy, el único):
        ///  * Acto 1 "Luna y Horizonte": dos cortes dorados y el barrido rojo (READY, LOW_L, READY, READY): cambiar de parry
        ///    a dash en el ritmo.
        ///  * Acto 2 "Escuela de la Sombra": la Escuela del Abuelo con la sombra cortando del otro lado entre el gyakugiri y
        ///    la estocada.
        ///  * Acto 3 "Luna Nueva": el barrido rojo, el corte, y la sombra sale de la oscuridad de costado (una dirección
        ///    que el acto todavía no usaba en sus dúos) antes del gyakugiri.
        /// Tramo 2 (solo si la vida llega a KokuyoBoss.ThirdsFrom):
        ///  * Acto 1 "Sombra Larga": su corte y, mientras levanta el segundo, la sombra se estira y corta primero.
        ///  * Acto 2 "Clavo y Horizonte": la sombra estalla bajo Kaito y él barre: dos rojos seguidos (dash, dash).
        ///  * Acto 3 "Eclipse Cruzado": corte, la sombra de costado, corte, la sombra del lado opuesto, corte.
        /// La regla del dúo (KokuyoDuet) estira los windups igual que en los otros dúos.
        /// </summary>
        public static AttackPattern Escalation(int act, int stage)
        {
            var s = new Set(Mathf.Clamp(act, 1, 3));
            if (stage >= 2)
            {
                if (act <= 1) return D("Sombra Larga", 1.1f, 5.0f, 11f, Cue(1, Nobi, ShadowSide.Any, true), s.kesa, s.gyaku, recoverHR);
                if (act == 2) return D("Clavo y Horizonte", 1.0f, 5.5f, 11f, Cue(0, Nui, ShadowSide.Any, true), s.ichi);
                // la segunda salida va dos pasos después: antes la sombra todavía está volviendo a la oscuridad de la
                // primera (CanStrike) y el dúo quedaba en un combo del cuerpo solo
                var cruz = D("Eclipse Cruzado", 1.1f, 5.0f, 12f, Cue(0, Giri, ShadowSide.Flank, false), s.kesa, s.gyaku, s.kesa, s.gyaku, recoverHR);
                cruz.cues = new[] { cruz.cues[0], Cue(2, Giri, ShadowSide.Opposite, false) };
                return cruz;
            }
            if (act <= 1) return P("Luna y Horizonte", 1.1f, 5.0f, 9f, s.kesa, s.gyaku, s.ichi);
            if (act == 2) return D("Escuela de la Sombra", 1.2f, 5.0f, 10f, Cue(1, Giri, ShadowSide.Opposite, false), s.kesa, s.gyaku, s.tsuki, tsukiRecover);
            return D("Luna Nueva", 1.2f, 5.0f, 10f, Cue(2, Giri, ShadowSide.Flank, true), s.ichi, s.kesa, s.gyaku, recoverHR);
        }

        /// <summary>En cada tramo los especiales (estocada, barrido, Rompecascos, Paso de Sombra) vuelven antes: la espera
        /// se multiplica por esto. Lo que cambia es cuántas veces salen, nunca su aviso.</summary>
        public const float StageCooldownMul = 0.75f;

        /// <summary>¿El patrón abre con un especial? (los que la segunda mitad trae más seguido)</summary>
        public static bool OpensWithSpecial(AttackPattern p)
        {
            if (p == null || p.steps == null || p.steps.Length == 0) return false;
            string sp = p.steps[0].special;
            return sp == Thrust || sp == Sweep || sp == Rift || sp == Sink;
        }

        /// <summary>Contraataque (Kaito le pegó dos veces a la guardia): el Counter termina en LOW_L y sigue un gyakugiri.</summary>
        public static AttackPattern Counter(int act)
        {
            var s = new Set(Mathf.Clamp(act, 1, 3));
            return P("Contra", 1f, 99f, 0f, s.gyaku, recoverHR);
        }

        /// <summary>El Último Desfile (10 %): cinco golpes con la pausa más corta y, al terminar, de rodillas sí o sí.</summary>
        public static AttackPattern LastParade()
        {
            var s = new Set(3);
            var p = P("Último Desfile", 1f, 5.0f, 0f, s.kesa, s.gyaku, s.kesa, s.gyaku, s.tsuki);
            p.exhaustAfter = true;
            return p;
        }

        // ------------------------------------------------------------------ configs
        /// <summary>Kokuyō, Señor del Clan Kurokage. Patrones del Acto 1 (los otros los pone KokuyoBoss al cambiar de acto).</summary>
        public static EnemyConfig Kokuyo()
        {
            return new EnemyConfig
            {
                // 1800 (antes 900, el pedido de vida doble) por HealthScale (arriba, el balance): con la vida de hoy el bot
                // "bueno" pelea ~3.4 min simulados y cada acto cambia de ritmo en tercios (KokuyoBoss.Pacing)
                id = "kage", displayName = "Kokuyō", maxHealth = 1800 * HealthScale, runSpeed = 3.0f, walkSpeed = 1.8f, turnSpeed = 4.5f,
                radius = 1.1f, height = 4.2f, scale = 1f, tintStrength = 0f,
                maxImbalance = 5, exhaustedTime = KokuyoTimings.Kneel.Seconds, exhaustedDamageMul = 1.3f, guardTime = 0.8f,
                poiseHits = 4, hyperArmor = true, knockbackResist = 0.95f, staggerTime = 0.3f, parriedRecoil = 0.55f,
                preferredDistance = 4.6f, detectRadius = 30f, loseRadius = 80f,
                // la ejecución solo se habilita de rodillas en la última resistencia (KokuyoBoss la abre y la cierra)
                finisherHealth = 0f, attackCooldown = new Vector2(0.7f, 1.4f), cinematicFinisher = true,
                animGuard = "Guard", animCounter = "Counter", animExhausted = "Kneel", animHit = "Flinch",
                animSpotted = "Roar", animDeath = "Defeat", animParried = "Parried",
                patterns = Act(1),
            };
        }

        // ------------------------------------------------------------------ la sombra
        /// <summary>Nobi: la sombra pegada a sus pies se estira hasta Kaito (cargando su corte) y pega en 1.2 s.</summary>
        public const float NobiWindup = 1.2f;
        /// <summary>Nobi: el corte de la sombra cae sobre el punto trabado en el "¡ahora!" (disco de este radio).</summary>
        public const float NobiRadius = 1.7f;
        /// <summary>Nobi: hasta dónde lo alcanza la sombra (su largo con la luna a 35°, ~6.4 m, más la hoja). Más cerca no
        /// hay mínimo: la sombra se acorta (KageShadow.UpdateNobiInk) y su hoja le barre por encima.</summary>
        public const float NobiMaxRange = 8.5f;
        /// <summary>Giri: la figura de tinta corta desde acá (el alcance de la hoja de Kesagiri es 3.88 m).</summary>
        public const float GiriDistance = 3.2f;
        /// <summary>En el eclipse la sombra se ve al menos esto antes de su golpe (sale de la oscuridad).</summary>
        public const float EmergeLead = 1.05f;
        /// <summary>Daño de los cortes de la sombra (Nobi; Giri en los Actos 2 y 3).</summary>
        static readonly float[] ShadowCutDamage = { 0f, 16f, 18f, 20f };

        /// <summary>Los golpes de la sombra en un acto (1..3): las pausas en el apex son las del cuerpo en ese acto.</summary>
        public sealed class ShadowSet
        {
            public readonly AttackDef nobi, giri;
            public readonly AttackPattern nobiP, giriP;
            public ShadowSet(int act)
            {
                act = Mathf.Clamp(act, 1, 3);
                var c = KokuyoTimings.Kesagiri;
                // el Nobi es el mismo kesagiri de la sombra con la carga larga: la luz gira hacia Kaito mientras sube la hoja
                nobi = K(c, "Sombra que se Estira", ShadowCutDamage[1], AttackKind.Heavy, 360f, 1.4f, ParryHold[1], 1, Nobi);
                nobi.windup = NobiWindup;
                nobi.range = NobiMaxRange;
                giri = K(c, "Corte de Sombra", ShadowCutDamage[Mathf.Max(2, act)], AttackKind.Heavy, 120f, 1.5f, ParryHold[act], act, Giri);
                nobiP = new AttackPattern { name = nobi.name, steps = new[] { nobi }, maxRange = 99f };
                giriP = new AttackPattern { name = giri.name, steps = new[] { giri }, maxRange = 99f };
            }
        }

        /// <summary>Kage, la sombra (desde el Acto 1): no se puede fijar ni cortar; solo las habilidades la clavan.</summary>
        public static EnemyConfig Shadow()
        {
            var nui = new AttackDef
            {
                name = "Kage-nui", state = "", damage = 18 * DamageScale, kind = AttackKind.Unblockable, knockback = 2.2f, lunge = 0f, tracking = false,
                activeStart = 0.5f, activeEnd = 0.6f, apex = 0.35f, hitStop = 0.1f, sfx = "kokuyo_whisper", special = Nui,
            };
            var watari = new AttackDef
            {
                name = "Kage-watari", state = "", damage = 20 * DamageScale, kind = AttackKind.Unblockable, knockback = 2.4f, lunge = 0f, tracking = false,
                activeStart = 0.5f, activeEnd = 0.6f, apex = 0.35f, hitStop = 0.1f, sfx = "kokuyo_whisper", special = Watari,
                windup = 0.6f,
            };
            return new EnemyConfig
            {
                id = "kage_shadow", displayName = "Kage", maxHealth = 1, runSpeed = 7f, walkSpeed = 7f, turnSpeed = 8f,
                radius = 0.8f, height = 4.2f, scale = 1f, maxImbalance = 99, detectRadius = 0f, finisherHealth = 0f,
                // desviada retrocede lo del cuerpo (el clip Parried entero se comprime en esto)
                parriedRecoil = 0.55f,
                attackCooldown = new Vector2(2.5f, 4f),
                patterns = new[]
                {
                    new AttackPattern { name = "Kage-nui", steps = new[] { nui }, weight = 2f, maxRange = 99f },
                    new AttackPattern { name = "Kage-watari", steps = new[] { watari }, weight = 1f, maxRange = 99f },
                },
            };
        }
    }
}
