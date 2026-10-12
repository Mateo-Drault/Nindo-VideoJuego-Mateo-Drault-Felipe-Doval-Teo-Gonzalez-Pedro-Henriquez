using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Golpes, patrones y config de Chikuō, el Maestro del Bambú (arquetipo y bossId "ozeki": las partidas, las banderas
    /// y el Sello del Bambú siguen igual). Los tiempos salen de BambooMasterTimings (lo que mide el build de Blender):
    /// el aviso, el brillo del miembro que pega y el golpe no se despegan del clip. Gramática de siempre:
    ///  * dorado = parry (palmas, tajo de mano, patada de grulla, patada giratoria, las estocadas del bastón);
    ///  * rojo = dash o salir de la zona (grulla voladora con la marca donde cae, barrida a ras del piso, onda de qi,
    ///    embestida con imágenes residuales).
    /// Las tres fases: una mano a la espalda (enseña de a una cosa), las dos manos (combos y los rojos nuevos) y el
    /// bastón (más alcance, cadenas largas). Cada fase acorta la pausa en el apex: la velocidad sube sin tocar los clips.
    /// </summary>
    public static class BambooMasterMoves
    {
        /// <summary>Especiales de Chikuō: golpe con el alcance real del miembro, salto que cae en la marca, barrida en
        /// disco, onda de qi que se abre por el piso, embestida por un carril fijo y paso sin golpe.</summary>
        public const string Strike = "m_strike", Leap = "m_leap", Sweep = "m_sweep", Qi = "m_qi", Dash = "m_dash";

        /// <summary>Pausa en el apex de los dorados por fase (0..2) y la de los rojos, que ya tienen anticipación larga.</summary>
        static readonly float[] ParryHold = { 0.30f, 0.22f, 0.16f };
        static readonly float[] DodgeHold = { 0.14f, 0.10f, 0.08f };
        /// <summary>Los pasos encadenados de un combo (el jugador ya está en ritmo) pausan menos.</summary>
        const float ChainedHold = 0.6f;
        /// <summary>StepTimeline.MinWindup multiplica por 0.9 desde la fase 1: se compensa para que las pausas de arriba
        /// sean las que se ven.</summary>
        const float PhaseWindupMul = 0.9f;

        /// <summary>Onda de qi por fase: velocidad del frente (m/s) y radio final (m). Más rápida que Kaito corriendo
        /// (6.2): de lejos se la ve venir, de cerca se la cruza con el dash cuando llega.</summary>
        public static readonly float[] QiSpeed = { 9f, 9f, 10f }, QiRadius = { 9f, 9f, 10.5f };
        /// <summary>El salto cae entre estos metros del lugar donde despega (estira o acorta el tramo en el aire). Cae sobre
        /// Kaito: de cerca es un salto casi en el lugar que pisa desde arriba (el que se le pega al cuerpo igual lo ve).</summary>
        public const float LeapMin = 2.0f, LeapMax = 7.4f;
        /// <summary>Desde esta distancia elige el salto: el que se le pega no puede quedar sin ver nunca el rojo de la fase 1.</summary>
        const float LeapMinRange = 1.0f;

        /// <summary>Sufijo de los clips de cada fase (los _P2 y _P3 tienen los mismos cuadros que el de la fase 1).</summary>
        public static string Suffix(int phase) => phase <= 0 ? "" : phase == 1 ? "_P2" : "_P3";

        public static MasterClip Clip(string baseState, int phase) =>
            BambooMasterTimings.Get(baseState + Suffix(phase)) ?? BambooMasterTimings.Get(baseState);

        // ------------------------------------------------------------------ golpes
        /// <summary>
        /// Un golpe con los tiempos de su clip. El avance lo hace el jefe con travel_m (lunge = 0: con la embestida lineal
        /// los pies patinan). 'range' es lo más lejos que llega (alcance + avance hasta el contacto): lo usan el bot y
        /// StrikeCanReach; el golpe real se mide con el alcance del miembro desde donde está en el impacto.
        /// </summary>
        static AttackDef M(string baseState, int phase, string name, float dmg, float arc, float kb, bool chained, string special = Strike)
        {
            var c = Clip(baseState, phase);
            bool red = c.Kind == 2;
            float hold = (red ? DodgeHold : ParryHold)[Mathf.Clamp(phase, 0, 2)] * (chained ? ChainedHold : 1f);
            float natural = c.Apex * c.Seconds / 0.85f + (c.Contact - c.Apex) * c.Seconds / c.ReleaseRate;
            float windup = natural + hold;
            if (phase >= 1) windup /= PhaseWindupMul;
            return new AttackDef
            {
                name = name, state = c.State, damage = dmg, kind = red ? AttackKind.Unblockable : AttackKind.Heavy, arc = arc, knockback = kb,
                range = c.Reach + c.TravelToContact, activeStart = c.Contact, activeEnd = c.ActiveEnd, apex = c.Apex, releaseRate = c.ReleaseRate,
                windup = windup, lunge = 0f, tracking = special == Strike || special == Leap || special == Dash, hitStop = red ? 0.12f : 0.1f,
                shake = red ? 0.45f : 0.35f, imbalance = 1f, sfx = phase >= 2 || red ? "enemy_swing_heavy" : "enemy_swing", special = special,
                // radio de la zona roja: el anillo de la barrida y de la caída del salto (del clip), el final de la onda
                specialParam = special == Qi ? QiRadius[Mathf.Clamp(phase, 0, 2)] : c.RingM,
            };
        }

        static AttackPattern P(string name, float weight, float minRange, float cooldown, params AttackDef[] steps) =>
            new AttackPattern
            {
                // se acerca hasta tener a Kaito al alcance del primer golpe (más el avance del clip hasta el contacto)
                name = name, steps = steps, weight = weight, minRange = minRange, cooldown = cooldown,
                maxRange = steps[0].special == Strike ? steps[0].range + 0.1f : steps[0].special == Sweep ? steps[0].specialParam + 0.2f : steps[0].range,
            };

        /// <summary>
        /// Patrones de cada fase (0..2). Fase 1, una mano: palma, tajo y grulla de a uno y en pares, y la grulla voladora
        /// (el único rojo: se aprende a mirar la marca). Fase 2, las dos manos: palmas dobles, patada giratoria, mezclas
        /// dorado-rojo, la barrida, la onda de qi y la embestida. Fase 3, el bastón: todo llega más lejos y las cadenas
        /// terminan en rojo ("el bambú que vuelve"). Mezcla: ~70 % dorados, ~30 % rojos, como el resto de los jefes.
        /// Daño: el jefe de 1400 de vida se pelea ~4-5 min y el bot "bueno" no resuelve ~17 % de los golpes (el
        /// "promedio", ~45 %; Tools/Dev/sim_bamboo_master.py): con golpes de 10-20 llegaba a la fase 3 sin vida. Pega poco
        /// y seguido, como un maestro que prueba: con una mano casi no lastima (5-7, es la lección), con las dos 7-11 y
        /// con el bastón 9-13. Lo que más sube con las fases es el ritmo y el alcance.
        /// </summary>
        public static AttackPattern[] Phase(int phase)
        {
            switch (Mathf.Clamp(phase, 0, 2))
            {
                case 0:
                {
                    var palm = M("Palm", 0, "Palma", 5, 70f, 1.4f, false);
                    var chop = M("ChopPalm", 0, "Mano de Sable", 5, 90f, 1.6f, false);
                    var chopC = M("ChopPalm", 0, "Mano de Sable", 5, 90f, 1.6f, true);
                    var crane = M("CraneKick", 0, "Pico de Grulla", 5, 80f, 1.8f, false);
                    var craneC = M("CraneKick", 0, "Pico de Grulla", 5, 80f, 1.8f, true);
                    var leap = M("LeapKick", 0, "Grulla Voladora", 7, 360f, 2.6f, false, Leap);
                    var leapP = P("Grulla Voladora", 1.0f, LeapMinRange, 6f, leap);
                    leapP.maxRange = LeapMax - 0.4f;
                    return new[]
                    {
                        P("Palma", 1.3f, 0f, 0f, palm),
                        P("Palma y Sable", 1.6f, 0f, 0f, palm, chopC),
                        P("Pico de Grulla", 1.0f, 0f, 2f, crane),
                        P("Sable y Grulla", 1.2f, 0f, 4f, chop, craneC),
                        P("Tres de una Mano", 0.8f, 0f, 8f, palm, chopC, craneC),
                        leapP,
                    };
                }
                case 1:
                {
                    var palm = M("Palm", 1, "Palma", 7, 70f, 1.4f, false);
                    var chopC = M("ChopPalm", 1, "Mano de Sable", 8, 90f, 1.6f, true);
                    var chop = M("ChopPalm", 1, "Mano de Sable", 8, 90f, 1.6f, false);
                    var crane = M("CraneKick", 1, "Pico de Grulla", 8, 80f, 1.8f, false);
                    var twin = M("TwinPalm", 1, "Palmas Gemelas", 8, 90f, 2.2f, false);
                    var twinC = M("TwinPalm", 1, "Palmas Gemelas", 8, 90f, 2.2f, true);
                    var spinC = M("SpinKick", 1, "Viento que Gira", 8, 200f, 2.0f, true);
                    var sweep = M("Sweep", 1, "Barrida del Bambú", 9, 360f, 2.0f, false, Sweep);
                    var sweepC = M("Sweep", 1, "Barrida del Bambú", 9, 360f, 2.0f, true, Sweep);
                    var qi = M("QiWave", 1, "Onda de Qi", 9, 360f, 2.8f, false, Qi);
                    var dash = M("DashStrike", 1, "Paso del Viento", 11, 60f, 2.4f, false, Dash);
                    var leap = M("LeapKick", 1, "Grulla Voladora", 11, 360f, 2.6f, false, Leap);
                    var leapP = P("Grulla Voladora", 0.8f, LeapMinRange, 7f, leap);
                    leapP.maxRange = LeapMax - 0.4f;
                    var dashP = P("Paso del Viento", 1.1f, 4.2f, 6f, dash);
                    dashP.maxRange = 7.6f;
                    var qiP = P("Onda de Qi", 0.9f, 0f, 9f, qi);
                    qiP.maxRange = 7f;
                    return new[]
                    {
                        P("Palmas Gemelas", 1.2f, 0f, 0f, twin),
                        P("Palma y Viento", 1.4f, 0f, 3f, palm, spinC),
                        P("Sable y Gemelas", 1.2f, 0f, 3f, chop, twinC),
                        P("Grulla y Barrida", 1.0f, 0f, 6f, crane, sweepC),
                        P("Barrida", 0.6f, 0f, 6f, sweep),
                        P("Cuatro Vientos", 0.7f, 0f, 9f, palm, chopC, twinC, spinC),
                        qiP, dashP, leapP,
                    };
                }
                default:
                {
                    var thrust = M("Palm", 2, "Estocada del Bastón", 9, 50f, 1.6f, false);
                    var thrustC = M("Palm", 2, "Estocada del Bastón", 9, 50f, 1.6f, true);
                    var smashC = M("ChopPalm", 2, "Bambú que Cae", 10, 70f, 2.0f, true);
                    var crane = M("CraneKick", 2, "Pico de Grulla", 10, 80f, 1.8f, false);
                    var sweep = M("Sweep", 2, "Barrida del Bastón", 12, 360f, 2.2f, false, Sweep);
                    var sweepC = M("Sweep", 2, "Barrida del Bastón", 12, 360f, 2.2f, true, Sweep);
                    var qi = M("QiWave", 2, "Raíz del Bambú", 12, 360f, 3.0f, false, Qi);
                    var qiC = M("QiWave", 2, "Raíz del Bambú", 12, 360f, 3.0f, true, Qi);
                    var dash = M("DashStrike", 2, "Paso del Viento", 13, 50f, 2.4f, false, Dash);
                    var leap = M("LeapKick", 2, "Grulla Voladora", 13, 360f, 2.6f, false, Leap);
                    var leapP = P("Grulla y Estocada", 0.8f, LeapMinRange, 7f, leap, thrustC);
                    leapP.maxRange = LeapMax - 0.4f;
                    var dashP = P("Viento y Bambú", 1.0f, 4.2f, 6f, dash, smashC);
                    dashP.maxRange = 7.6f;
                    var qiP = P("Raíz del Bambú", 0.8f, 0f, 8f, qi);
                    qiP.maxRange = 7f;
                    return new[]
                    {
                        P("Estocada", 1.2f, 0f, 0f, thrust),
                        P("Estocada y Bambú", 1.4f, 0f, 0f, thrust, smashC),
                        P("El Bambú Vuelve", 1.1f, 0f, 6f, thrust, smashC, sweepC),
                        P("Grulla y Estocada", 1.0f, 0f, 3f, crane, thrustC),
                        P("Barrida del Bastón", 0.6f, 0f, 6f, sweep),
                        P("La Última Lección", 0.6f, 0f, 12f, thrust, smashC, thrustC, qiC),
                        qiP, dashP, leapP,
                    };
                }
            }
        }

        /// <summary>El contragolpe de la postura del bambú (y de la guardia común): sale de COIL, el final de Counter.</summary>
        public static AttackPattern Counter(int phase)
        {
            int ph = Mathf.Clamp(phase, 0, 2);
            var c = M("CounterStrike", ph, ph >= 2 ? "Contragolpe del Bastón" : "Contragolpe", ph == 0 ? 5 : ph == 1 ? 7 : 9,
                      ph >= 2 ? 60f : 80f, 1.4f, false);
            return new AttackPattern { name = "Contragolpe", steps = new[] { c }, weight = 1f, maxRange = 99f };
        }

        // ------------------------------------------------------------------ config
        /// <summary>Pausa entre combos por fase (s): rodea y mira antes de volver a atacar; se acorta con cada fase.</summary>
        public static readonly Vector2[] Cooldown = { new Vector2(2.6f, 3.6f), new Vector2(2.0f, 3.0f), new Vector2(1.6f, 2.4f) };

        /// <summary>
        /// Chikuō, el Maestro del Bambú. 1400 de vida (el doble del jefe de antes, como el resto de los jefes). No se lo
        /// ejecuta: termina sentado a meditar (BambooMasterBoss). Postura de 8 (parry 1, perfecto 1.5, unos seis parries):
        /// solo de rodillas con la barra llena, y de rodillas aguanta tres cortes a x1.15. Con 5 y x1.3 se arrodillaba
        /// cada 15 s y la pelea duraba la mitad. Los golpes fuera de sus huecos rebotan (BambooMasterBoss.ReceiveHit), así que poiseHits
        /// no se usa. Locomoción a 1.6 / 4.0 m/s, las velocidades a las que están autorados Walk y Run (los pies no
        /// patinan).
        /// </summary>
        public static EnemyConfig Config()
        {
            return new EnemyConfig
            {
                id = "ozeki", displayName = "Chikuō", maxHealth = 1400, runSpeed = 4.0f, walkSpeed = 1.6f, turnSpeed = 7f,
                radius = 0.5f, height = 2.4f, scale = 1f, tintStrength = 0f,
                maxImbalance = 8, exhaustedTime = BambooMasterTimings.Exhausted.Seconds, exhaustedDamageMul = 1.15f, guardTime = 0.7f,
                poiseHits = 0, hyperArmor = true, knockbackResist = 0.7f, staggerTime = 0.35f,
                // el retroceso del parry dura lo que tarda el clip en volver a la guardia (resume de Parried, 0.4 s; el
                // perfecto, x1.5 = 0.6 s = resume de ParriedPerfect)
                parriedRecoil = BambooMasterTimings.Parried.Seconds * 0.4f,
                preferredDistance = 3.6f, detectRadius = 30f, loseRadius = 80f,
                finisherHealth = 0f, attackCooldown = Cooldown[0], cinematicFinisher = false,
                animLocomotion = "Locomotion", animGuard = "Guard", animCounter = "Counter", animExhausted = "Exhausted", animHit = "Hit",
                animSpotted = "Guard", animDeath = "Defeat", animParried = "Parried", deathClipFalls = true,
                patterns = Phase(0),
            };
        }
    }
}
