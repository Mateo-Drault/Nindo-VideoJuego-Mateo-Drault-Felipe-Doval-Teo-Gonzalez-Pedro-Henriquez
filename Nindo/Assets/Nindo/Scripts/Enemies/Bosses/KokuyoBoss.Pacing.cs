using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// El ritmo de la pelea larga (vida 1800): cada acto tiene dos mitades. Al cruzar la mitad de la vida del acto, al
    /// terminar su combo él se planta y ruge (un respiro de 1.3 s para los dos: los golpes rebotan, la sombra espera) y
    /// desde ahí:
    ///  * suma el patrón de la segunda mitad (KokuyoMoves.SecondHalf), que la primera vez pesa el triple para que se vea;
    ///  * sus especiales vuelven antes (KokuyoMoves.SecondHalfCooldownMul);
    ///  * su sombra toma turnos más seguido (TurnMinGap y MaxQuiet x0.8).
    /// Con la vida doble cada acto duraba el doble con lo mismo; así la mitad de cada acto cambia algo y se anuncia.
    /// Los avisos no cambian: cambia cuántas veces y con qué mezcla.
    /// </summary>
    public partial class KokuyoBoss
    {
        const float SecondHalfShadowMul = 0.8f;
        /// <summary>El patrón nuevo pesa esto la primera vez (como los imparables que se enseñan en el Acto 1).</summary>
        const float SecondHalfTeachBoost = 3f;
        static readonly string[] SecondHalfBarks = { "", "kokuyo_bark_mitad1", "kokuyo_bark_mitad2", "kokuyo_bark_mitad3" };

        bool secondHalf, breatherPending;
        float breatherUntil = -1f, secondHalfBaseWeight;
        AttackPattern secondHalfPattern;

        /// <summary>La sombra en la segunda mitad del acto: sus esperas entre turnos se acortan.</summary>
        float ShadowPace => secondHalf ? SecondHalfShadowMul : 1f;

        /// <summary>Rugiendo en el respiro de mitad de acto: los golpes de Kaito rebotan (como en el rugido de fase).</summary>
        bool Breathing => Time.time < breatherUntil;

        /// <summary>Cada acto (y el reintento) empieza en su primera mitad.</summary>
        void ResetPacing()
        {
            secondHalf = breatherPending = false;
            breatherUntil = -1f;
            secondHalfPattern = null;
        }

        /// <summary>Vida a la que arranca la segunda mitad del acto en curso.</summary>
        float SecondHalfAt
        {
            get
            {
                int a = Mathf.Clamp(Act, 1, 3);
                return (Gates[a - 1] + Gates[a]) * 0.5f * config.maxHealth;
            }
        }

        /// <summary>Lo llama OnDamaged: cruzó la mitad del acto (una vez por acto; nunca en escena ni en la última resistencia).</summary>
        void CheckSecondHalf()
        {
            if (secondHalf || LastStand || transition != null || !IsAlive || Health > SecondHalfAt) return;
            secondHalf = true;
            breatherPending = true;
            int act = Mathf.Clamp(Act, 1, 3);
            var extra = KokuyoMoves.SecondHalf(act);
            secondHalfBaseWeight = extra.weight;
            extra.weight *= SecondHalfTeachBoost;
            var old = config.patterns;
            foreach (var p in old) if (KokuyoMoves.OpensWithSpecial(p)) p.cooldown *= KokuyoMoves.SecondHalfCooldownMul;
            // una vez por acto: el arreglo nuevo es la única asignación
            var list = new AttackPattern[old.Length + 1];
            old.CopyTo(list, 0);
            list[old.Length] = extra;
            config.patterns = list;
            secondHalfPattern = extra;
        }

        /// <summary>
        /// Al terminar un combo en pie, si cruzó la mitad: en vez de cubrirse se planta y ruge. Devuelve false si no tocaba.
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
            Bark(SecondHalfBarks[Mathf.Clamp(Act, 1, 3)]);
            return true;
        }

        /// <summary>El patrón de la segunda mitad ya se vio: vuelve a su peso.</summary>
        void OnPacingPatternStarted()
        {
            if (step == 0 && secondHalfPattern != null && pattern == secondHalfPattern) secondHalfPattern.weight = secondHalfBaseWeight;
        }

#if UNITY_EDITOR || DEVELOPMENT_BUILD
        /// <summary>Pruebas (AutoPilot "kokuyo mitad"): la vida justo debajo de la mitad del acto en curso.</summary>
        public void DebugSecondHalf()
        {
            if (!Fighting || !IsAlive || LastStand || transition != null) return;
            Health = Mathf.Min(Health, SecondHalfAt - 1f);
            CheckSecondHalf();
        }
#endif
    }
}
