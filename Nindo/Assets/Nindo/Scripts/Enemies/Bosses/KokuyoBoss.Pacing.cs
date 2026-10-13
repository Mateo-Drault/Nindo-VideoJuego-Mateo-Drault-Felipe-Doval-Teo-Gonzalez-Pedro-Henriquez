using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// El ritmo de la pelea larga: cada acto se parte en tramos. Con menos de ThirdsFrom de vida son dos mitades; con la
    /// de hoy (KokuyoMoves.HealthScale) son tres tercios, para que cada tramo no se vuelva la misma pelea dos veces. El
    /// golpe que cruza cada corte le saca un humo de tinta y le devuelve aire a Kaito (KokuyoMoves.StageHeal: como los
    /// tramos de la armadura de Gorō, la pelea larga no es puro desgaste). Al terminar su combo él se planta y ruge (un
    /// respiro de 1.3 s para los dos: los golpes rebotan, la sombra espera) y desde ahí:
    ///  * suma el patrón de ese tramo (KokuyoMoves.Escalation), que la primera vez pesa el triple para que se vea;
    ///  * sus especiales vuelven antes (x0.75 en cada corte) y el Paso de Sombra hierve menos bajo el piso (sale antes);
    ///  * su sombra toma turnos más seguido (esperas x0.8, después x0.65).
    /// Los avisos no cambian nunca: cambia cuántas veces, con qué mezcla y cuánto tiempo muerto hay entre ellos.
    /// </summary>
    public partial class KokuyoBoss
    {
        /// <summary>Vida desde la que cada acto se parte en tercios (dos cortes) en vez de mitades.</summary>
        const float ThirdsFrom = 2200f;
        /// <summary>Esperas de la sombra entre turnos en cada tramo (0 = el primero).</summary>
        static readonly float[] StageShadowMul = { 1f, 0.8f, 0.65f };
        /// <summary>Paso de Sombra: lo que hierve hundido antes de salir, por tramo (lo que se ve es el charco; el corte
        /// tiene su anillo dorado entero igual). Más corto = el especial llega antes, sin tocar su aviso.</summary>
        static readonly float[] StageSinkBoil = { 0.45f, 0.32f, 0.25f };
        /// <summary>El patrón nuevo pesa esto la primera vez (como los imparables que se enseñan en el Acto 1).</summary>
        const float StageTeachBoost = 3f;
        /// <summary>El grito de cada acto al primer corte (el segundo corte, si lo hay, es solo el rugido).</summary>
        static readonly string[] StageBarks = { "", "kokuyo_bark_mitad1", "kokuyo_bark_mitad2", "kokuyo_bark_mitad3" };

        int stage;
        bool breatherPending;
        float breatherUntil = -1f, stageBaseWeight;
        AttackPattern stagePattern;

        /// <summary>Cuántos cortes tiene cada acto con la vida de esta pelea.</summary>
        int StageCount => config.maxHealth >= ThirdsFrom ? 2 : 1;

        /// <summary>La sombra en los tramos siguientes del acto: sus esperas entre turnos se acortan.</summary>
        float ShadowPace => StageShadowMul[Mathf.Clamp(stage, 0, StageShadowMul.Length - 1)];

        /// <summary>Lo que hierve el Paso de Sombra antes de salir en este tramo.</summary>
        float SinkBoil => StageSinkBoil[Mathf.Clamp(stage, 0, StageSinkBoil.Length - 1)];

        /// <summary>Rugiendo en el respiro del corte: los golpes de Kaito rebotan (como en el rugido de fase).</summary>
        bool Breathing => Time.time < breatherUntil;

        /// <summary>Cada acto (y el reintento) empieza en su primer tramo.</summary>
        void ResetPacing()
        {
            stage = 0;
            breatherPending = false;
            breatherUntil = -1f;
            stagePattern = null;
        }

        /// <summary>Vida a la que arranca el tramo 'next' (1..StageCount) del acto en curso.</summary>
        float StageAt(int next)
        {
            int a = Mathf.Clamp(Act, 1, 3);
            float from = Gates[a - 1], to = Gates[a];
            return (from - (from - to) * next / (StageCount + 1f)) * config.maxHealth;
        }

        /// <summary>Lo llama OnDamaged: cruzó el próximo corte del acto (nunca en escena ni en la última resistencia).
        /// Un golpe grande que cruza dos cortes cuenta uno: el otro entra con el golpe siguiente (de a un rugido).</summary>
        void CheckStage()
        {
            if (stage >= StageCount || LastStand || transition != null || !IsAlive || Health > StageAt(stage + 1)) return;
            stage++;
            breatherPending = true;
            RewardStage();
            // el anterior, si todavía no salió, deja de pesar el triple: el nuevo es el que se enseña ahora
            if (stagePattern != null) stagePattern.weight = stageBaseWeight;
            var extra = KokuyoMoves.Escalation(Mathf.Clamp(Act, 1, 3), stage);
            stageBaseWeight = extra.weight;
            extra.weight *= StageTeachBoost;
            var old = config.patterns;
            foreach (var p in old) if (KokuyoMoves.OpensWithSpecial(p)) p.cooldown *= KokuyoMoves.StageCooldownMul;
            // una vez por corte: el arreglo nuevo es la única asignación
            var list = new AttackPattern[old.Length + 1];
            old.CopyTo(list, 0);
            list[old.Length] = extra;
            config.patterns = list;
            stagePattern = extra;
        }

        /// <summary>
        /// Cruzó un corte: se le escapa un humo de tinta del pecho (el tramo se rompió) y Kaito recupera la cura del tramo
        /// en el mismo golpe, aunque él esté de rodillas (el rugido llega después, al terminar su combo). Heal ya muestra
        /// la cura (solo si de verdad curó). Nada que se lea como otra cosa: todas las grietas encendidas son su postura
        /// rota (de rodillas) y en el eclipse la bandana dorada es la sombra saliendo de la oscuridad; la bandana late
        /// solo en los Actos 1 y 2, y solo si curó.
        /// </summary>
        void RewardStage()
        {
            Game.FX?.SmokePuff(AimPoint, 1.4f);
            Game.Camera?.Shake(0.2f);
            var p = Game.Player;
            float heal = KokuyoMoves.StageHealOf(Act);
            if (p == null || !p.IsAlive || heal <= 0f) return;
            bool hurt = p.Health < p.config.maxHealth - 0.5f;
            p.Heal(heal);
            if (hurt && Act < 3) BandanaGlow.Ensure(p)?.Pulse(BandanaGlow.Gold, 0.8f);
        }

        /// <summary>
        /// Al terminar un combo en pie, si cruzó un corte: en vez de cubrirse se planta y ruge. Devuelve false si no tocaba.
        /// La sombra no arranca turnos mientras tanto (BodyFree es falso fuera de Chase/Strafe/Guard).
        /// </summary>
        bool TryBreather()
        {
            if (!breatherPending || !Fighting || LastStand) return false;
            breatherPending = false;
            var c = KokuyoTimings.Roar;
            SetState(EnemyState.Alert);
            stateDuration = c.Seconds;
            breatherUntil = Time.time + c.Seconds;
            anim.Play(c.State, 0.15f);
            nextAttackTime = Mathf.Max(nextAttackTime, breatherUntil + 0.4f);
            Game.Audio?.Play("boss_roar", transform.position, 0.7f);
            Game.Camera?.Shake(0.3f);
            if (stage == 1) Bark(StageBarks[Mathf.Clamp(Act, 1, 3)]);
            return true;
        }

        /// <summary>El patrón del tramo ya se vio: vuelve a su peso.</summary>
        void OnPacingPatternStarted()
        {
            if (step == 0 && stagePattern != null && pattern == stagePattern) stagePattern.weight = stageBaseWeight;
        }

#if UNITY_EDITOR || DEVELOPMENT_BUILD
        /// <summary>Pruebas (AutoPilot "kokuyo mitad"): la vida justo debajo del próximo corte del acto en curso.</summary>
        public void DebugSecondHalf()
        {
            if (!Fighting || !IsAlive || LastStand || transition != null || stage >= StageCount) return;
            Health = Mathf.Min(Health, StageAt(stage + 1) - 1f);
            CheckStage();
        }
#endif
    }
}
