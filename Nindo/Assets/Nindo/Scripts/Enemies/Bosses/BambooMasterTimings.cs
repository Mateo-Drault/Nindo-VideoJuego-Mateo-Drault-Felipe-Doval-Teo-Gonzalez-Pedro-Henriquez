// Generado por Tools/Unity/bamboo_master_timings.py desde BambooMaster.fbx.json: no editar a mano.
using System.Collections.Generic;

namespace Nindo
{
    /// <summary>Tiempos de un clip de Chikuō tal como los mide el build de Blender (normalizados 0..1).</summary>
    public sealed class MasterClip
    {
        public readonly string State;
        public readonly int Frames;
        public readonly float Seconds, Apex, Contact, ActiveEnd, ReleaseRate, Reach;
        /// <summary>0 = no pega, 1 = dorado (parry), 2 = rojo (dash).</summary>
        public readonly int Kind;
        /// <summary>Slots de CharacterGlint que se encienden con el aviso (la mano, el pie o el bastón que pega).</summary>
        public readonly string[] Glow;
        /// <summary>Radio del anillo rojo (barrida, caída del salto; 0 = sin anillo), dónde cae el pie del salto
        /// medido desde el transform inicial (0 = no salta) y metros que retrocede una reacción (knock_m).</summary>
        public readonly float RingM, MarkerM, KnockM;
        /// <summary>Tramo con los dos pies en el aire (normalizado; AirEnd 0 = no tiene): ahí se puede estirar el avance.</summary>
        public readonly float AirStart, AirEnd;
        /// <summary>Metros que avanzó el transform en cada cuadro del clip (null = no se mueve).</summary>
        public readonly float[] Travel;
        /// <summary>Pose con la que empieza y con la que termina (READY, GUARD, COIL...).</summary>
        public readonly string ChainFrom, ChainTo;
        readonly string[] eventNames;
        readonly float[] eventTimes;

        public MasterClip(string state, int frames, float seconds, float apex, float contact, float activeEnd, float releaseRate,
            float reach, int kind, string[] glow, float ringM, float markerM, float knockM, float airStart, float airEnd,
            float[] travel, string chainFrom, string chainTo, string[] eventNames, float[] eventTimes)
        {
            State = state; Frames = frames; Seconds = seconds; Apex = apex; Contact = contact; ActiveEnd = activeEnd;
            ReleaseRate = releaseRate; Reach = reach; Kind = kind; Glow = glow; RingM = ringM; MarkerM = markerM; KnockM = knockM;
            AirStart = airStart; AirEnd = airEnd; Travel = travel; ChainFrom = chainFrom; ChainTo = chainTo;
            this.eventNames = eventNames; this.eventTimes = eventTimes;
        }

        /// <summary>Tiempo normalizado del primer evento con ese nombre (-1 si el clip no lo tiene).</summary>
        public float Event(string name)
        {
            for (int i = 0; i < eventNames.Length; i++) if (eventNames[i] == name) return eventTimes[i];
            return -1f;
        }

        /// <summary>Normalizado de un cuadro del clip.</summary>
        public float FrameNorm(float frame) => Frames > 0 ? frame / Frames : 0f;

        /// <summary>Metros avanzados en el tiempo normalizado 'n' (interpolado entre cuadros).</summary>
        public float TravelAt(float n)
        {
            if (Travel == null) return 0f;
            float x = UnityEngine.Mathf.Clamp(n, 0f, 1f) * Frames;
            int i = UnityEngine.Mathf.Min((int)x, Travel.Length - 1);
            int j = UnityEngine.Mathf.Min(i + 1, Travel.Length - 1);
            return Travel[i] + (Travel[j] - Travel[i]) * (x - i);
        }

        /// <summary>Lo que avanza el cuerpo hasta el golpe (para saber desde qué distancia llega).</summary>
        public float TravelToContact => TravelAt(Contact);
    }

    public static class BambooMasterTimings
    {
        public const float BindHeight = 2.672f;
        /// <summary>Largo del bastón (m): el hueso Staff va de la punta de abajo a la de arriba.</summary>
        public const float StaffLength = 2.3f;
        public static readonly MasterClip Idle = new MasterClip("Idle", 96, 3.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new string[0], new float[0]);
        public static readonly MasterClip Walk = new MasterClip("Walk", 36, 1.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip Run = new MasterClip("Run", 22, 0.7333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip StrafeL = new MasterClip("StrafeL", 24, 0.8f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip StrafeR = new MasterClip("StrafeR", 24, 0.8f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip WalkBack = new MasterClip("WalkBack", 36, 1.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip Idle_P2 = new MasterClip("Idle_P2", 96, 3.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new string[0], new float[0]);
        public static readonly MasterClip Walk_P2 = new MasterClip("Walk_P2", 36, 1.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip Run_P2 = new MasterClip("Run_P2", 22, 0.7333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip StrafeL_P2 = new MasterClip("StrafeL_P2", 24, 0.8f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip StrafeR_P2 = new MasterClip("StrafeR_P2", 24, 0.8f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip WalkBack_P2 = new MasterClip("WalkBack_P2", 36, 1.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip Idle_P3 = new MasterClip("Idle_P3", 96, 3.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new string[0], new float[0]);
        public static readonly MasterClip Walk_P3 = new MasterClip("Walk_P3", 36, 1.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip Run_P3 = new MasterClip("Run_P3", 22, 0.7333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip StrafeL_P3 = new MasterClip("StrafeL_P3", 24, 0.8f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip StrafeR_P3 = new MasterClip("StrafeR_P3", 24, 0.8f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip WalkBack_P3 = new MasterClip("WalkBack_P3", 36, 1.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new[] { "Step", "Step" }, new[] { 0.0f, 0.5f });
        public static readonly MasterClip Palm = new MasterClip("Palm", 34, 1.1333f, 0.2941f, 0.4412f, 0.5f, 1.6f, 1.32f, 1, new[] { "Master_GlintHandR" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.25f, 0.425f, 0.6f, 0.765f, 0.82f, 0.8638f, 0.895f, 0.9138f, 0.92f, 0.9231f, 0.9306f, 0.9394f, 0.9469f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f },
            "READY", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.2941f, 0.4412f, 0.4412f, 0.7353f });
        public static readonly MasterClip ChopPalm = new MasterClip("ChopPalm", 36, 1.2f, 0.3056f, 0.4722f, 0.5278f, 1.6f, 1.27f, 1, new[] { "Master_GlintHandR" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.126f, 0.252f, 0.405f, 0.558f, 0.72f, 0.774f, 0.8134f, 0.8415f, 0.8584f, 0.864f, 0.8677f, 0.8767f, 0.8873f, 0.8963f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f },
            "READY", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.3056f, 0.4722f, 0.4722f, 0.75f });
        public static readonly MasterClip CraneKick = new MasterClip("CraneKick", 42, 1.4f, 0.3095f, 0.4286f, 0.4762f, 1.6f, 1.32f, 1, new[] { "Master_GlintFootR" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0075f, 0.03f, 0.0675f, 0.12f, 0.1407f, 0.1926f, 0.26f, 0.3274f, 0.3793f, 0.4f, 0.413f, 0.437f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f },
            "READY", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.3095f, 0.4286f, 0.6667f, 0.8571f });
        public static readonly MasterClip LeapKick = new MasterClip("LeapKick", 56, 1.8667f, 0.3393f, 0.5893f, 0.6429f, 0.6f, 0.31f, 2, new[] { "Master_GlintFootR" },
            1.8f, 4.79f, 0.0f, 0.3929f, 0.5714f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.075f, 0.15f, 0.7037f, 1.2574f, 1.6823f, 2.1072f, 2.4654f, 2.8236f, 3.1391f, 3.4547f, 3.74f, 4.0253f, 4.2876f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f },
            "READY", "READY", new[] { "Apex", "TakeOff", "Strike", "Land", "Step" }, new[] { 0.3393f, 0.375f, 0.5893f, 0.5893f, 0.625f });
        public static readonly MasterClip Palm_P2 = new MasterClip("Palm_P2", 34, 1.1333f, 0.2941f, 0.4412f, 0.5f, 1.6f, 1.32f, 1, new[] { "Master_GlintHandR" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.25f, 0.425f, 0.6f, 0.765f, 0.82f, 0.8638f, 0.895f, 0.9138f, 0.92f, 0.9231f, 0.9306f, 0.9394f, 0.9469f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f },
            "READY", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.2941f, 0.4412f, 0.4412f, 0.7353f });
        public static readonly MasterClip ChopPalm_P2 = new MasterClip("ChopPalm_P2", 36, 1.2f, 0.3056f, 0.4722f, 0.5278f, 1.6f, 1.27f, 1, new[] { "Master_GlintHandR" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.126f, 0.252f, 0.405f, 0.558f, 0.72f, 0.774f, 0.8134f, 0.8415f, 0.8584f, 0.864f, 0.8677f, 0.8767f, 0.8873f, 0.8963f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f },
            "READY", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.3056f, 0.4722f, 0.4722f, 0.75f });
        public static readonly MasterClip CraneKick_P2 = new MasterClip("CraneKick_P2", 42, 1.4f, 0.3095f, 0.4286f, 0.4762f, 1.6f, 1.32f, 1, new[] { "Master_GlintFootR" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0075f, 0.03f, 0.0675f, 0.12f, 0.1407f, 0.1926f, 0.26f, 0.3274f, 0.3793f, 0.4f, 0.413f, 0.437f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f },
            "READY", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.3095f, 0.4286f, 0.6667f, 0.8571f });
        public static readonly MasterClip LeapKick_P2 = new MasterClip("LeapKick_P2", 56, 1.8667f, 0.3393f, 0.5893f, 0.6429f, 0.6f, 0.31f, 2, new[] { "Master_GlintFootR" },
            1.8f, 4.79f, 0.0f, 0.3929f, 0.5714f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.075f, 0.15f, 0.7037f, 1.2574f, 1.6823f, 2.1072f, 2.4654f, 2.8236f, 3.1391f, 3.4547f, 3.74f, 4.0253f, 4.2876f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f },
            "READY", "READY", new[] { "Apex", "TakeOff", "Strike", "Land", "Step" }, new[] { 0.3393f, 0.375f, 0.5893f, 0.5893f, 0.625f });
        public static readonly MasterClip Guard = new MasterClip("Guard", 20, 0.6667f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "GUARD", new string[0], new float[0]);
        public static readonly MasterClip GuardHit = new MasterClip("GuardHit", 15, 0.5f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "GUARD", "GUARD", new[] { "Deflect" }, new[] { 0.0667f });
        public static readonly MasterClip Counter = new MasterClip("Counter", 16, 0.5333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "GUARD", "COIL", new[] { "Deflect" }, new[] { 0.125f });
        public static readonly MasterClip CounterStrike = new MasterClip("CounterStrike", 26, 0.8667f, 0.1154f, 0.2692f, 0.3462f, 1.6f, 1.3f, 1, new[] { "Master_GlintHandR" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.075f, 0.15f, 0.255f, 0.36f, 0.4725f, 0.51f, 0.5359f, 0.5561f, 0.5705f, 0.5791f, 0.582f, 0.5839f, 0.5883f, 0.5937f, 0.5981f, 0.6f, 0.6f, 0.6f, 0.6f, 0.6f, 0.6f, 0.6f, 0.6f },
            "COIL", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.1154f, 0.2692f, 0.2692f, 0.6923f });
        public static readonly MasterClip Taunt = new MasterClip("Taunt", 54, 1.8f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new[] { "Beckon", "Beckon" }, new[] { 0.2778f, 0.4444f });
        public static readonly MasterClip Hit = new MasterClip("Hit", 18, 0.6f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.12f, 0.0f, 0.0f,
            new[] { 0.0f, -0.0292f, -0.0584f, -0.0697f, -0.0811f, -0.0924f, -0.1038f, -0.1067f, -0.1097f, -0.1127f, -0.1157f, -0.1167f, -0.1176f, -0.1183f, -0.1189f, -0.1194f, -0.1197f, -0.1199f, -0.12f },
            "READY", "READY", new string[0], new float[0]);
        public static readonly MasterClip HitHeavy = new MasterClip("HitHeavy", 27, 0.9f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.42f, 0.0f, 0.0f,
            new[] { 0.0f, -0.0885f, -0.177f, -0.2655f, -0.2906f, -0.3156f, -0.3407f, -0.3658f, -0.3908f, -0.395f, -0.3992f, -0.4034f, -0.4076f, -0.4118f, -0.4161f, -0.4166f, -0.4172f, -0.4177f, -0.4181f, -0.4185f, -0.4189f, -0.4192f, -0.4194f, -0.4196f, -0.4198f, -0.4199f, -0.42f, -0.42f },
            "READY", "READY", new string[0], new float[0]);
        public static readonly MasterClip Parried = new MasterClip("Parried", 30, 1.0f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.4f, 0.0f, 0.0f,
            new[] { 0.0f, -0.0973f, -0.1946f, -0.2379f, -0.2812f, -0.3244f, -0.3342f, -0.3439f, -0.3537f, -0.3634f, -0.3732f, -0.3829f, -0.3927f, -0.3935f, -0.3942f, -0.3949f, -0.3956f, -0.3962f, -0.3967f, -0.3973f, -0.3977f, -0.3982f, -0.3986f, -0.3989f, -0.3992f, -0.3994f, -0.3996f, -0.3998f, -0.3999f, -0.4f, -0.4f },
            "", "READY", new[] { "Parried", "Step" }, new[] { 0.0f, 0.1667f });
        public static readonly MasterClip ParriedPerfect = new MasterClip("ParriedPerfect", 36, 1.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.8f, 0.0f, 0.0f,
            new[] { 0.0f, -0.1946f, -0.3893f, -0.4559f, -0.5225f, -0.5892f, -0.6558f, -0.7224f, -0.7293f, -0.7362f, -0.743f, -0.7499f, -0.7568f, -0.7637f, -0.7705f, -0.7774f, -0.7843f, -0.7911f, -0.798f, -0.7982f, -0.7984f, -0.7986f, -0.7988f, -0.799f, -0.7991f, -0.7993f, -0.7994f, -0.7995f, -0.7996f, -0.7997f, -0.7998f, -0.7998f, -0.7999f, -0.7999f, -0.8f, -0.8f, -0.8f },
            "", "READY", new[] { "Parried", "Step" }, new[] { 0.0f, 0.1667f });
        public static readonly MasterClip Exhausted = new MasterClip("Exhausted", 120, 4.0f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new[] { "Kneel", "Breath", "Breath", "Breath" }, new[] { 0.125f, 0.2167f, 0.4333f, 0.65f });
        public static readonly MasterClip ExhaustedHit = new MasterClip("ExhaustedHit", 16, 0.5333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "KNEEL", "KNEEL", new string[0], new float[0]);
        public static readonly MasterClip ExhaustedRise = new MasterClip("ExhaustedRise", 22, 0.7333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "KNEEL", "READY", new string[0], new float[0]);
        public static readonly MasterClip Guard_P2 = new MasterClip("Guard_P2", 20, 0.6667f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "GUARD", new string[0], new float[0]);
        public static readonly MasterClip GuardHit_P2 = new MasterClip("GuardHit_P2", 15, 0.5f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "GUARD", "GUARD", new[] { "Deflect" }, new[] { 0.0667f });
        public static readonly MasterClip Counter_P2 = new MasterClip("Counter_P2", 16, 0.5333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "GUARD", "COIL", new[] { "Deflect" }, new[] { 0.125f });
        public static readonly MasterClip CounterStrike_P2 = new MasterClip("CounterStrike_P2", 26, 0.8667f, 0.1154f, 0.2692f, 0.3462f, 1.6f, 1.3f, 1, new[] { "Master_GlintHandR" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.075f, 0.15f, 0.255f, 0.36f, 0.4725f, 0.51f, 0.5359f, 0.5561f, 0.5705f, 0.5791f, 0.582f, 0.5839f, 0.5883f, 0.5937f, 0.5981f, 0.6f, 0.6f, 0.6f, 0.6f, 0.6f, 0.6f, 0.6f, 0.6f },
            "COIL", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.1154f, 0.2692f, 0.2692f, 0.6923f });
        public static readonly MasterClip Taunt_P2 = new MasterClip("Taunt_P2", 54, 1.8f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new[] { "Beckon", "Beckon" }, new[] { 0.2778f, 0.4444f });
        public static readonly MasterClip Hit_P2 = new MasterClip("Hit_P2", 18, 0.6f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.12f, 0.0f, 0.0f,
            new[] { 0.0f, -0.0292f, -0.0584f, -0.0697f, -0.0811f, -0.0924f, -0.1038f, -0.1067f, -0.1097f, -0.1127f, -0.1157f, -0.1167f, -0.1176f, -0.1183f, -0.1189f, -0.1194f, -0.1197f, -0.1199f, -0.12f },
            "READY", "READY", new string[0], new float[0]);
        public static readonly MasterClip HitHeavy_P2 = new MasterClip("HitHeavy_P2", 27, 0.9f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.42f, 0.0f, 0.0f,
            new[] { 0.0f, -0.0885f, -0.177f, -0.2655f, -0.2906f, -0.3156f, -0.3407f, -0.3658f, -0.3908f, -0.395f, -0.3992f, -0.4034f, -0.4076f, -0.4118f, -0.4161f, -0.4166f, -0.4172f, -0.4177f, -0.4181f, -0.4185f, -0.4189f, -0.4192f, -0.4194f, -0.4196f, -0.4198f, -0.4199f, -0.42f, -0.42f },
            "READY", "READY", new string[0], new float[0]);
        public static readonly MasterClip Parried_P2 = new MasterClip("Parried_P2", 30, 1.0f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.4f, 0.0f, 0.0f,
            new[] { 0.0f, -0.0973f, -0.1946f, -0.2379f, -0.2812f, -0.3244f, -0.3342f, -0.3439f, -0.3537f, -0.3634f, -0.3732f, -0.3829f, -0.3927f, -0.3935f, -0.3942f, -0.3949f, -0.3956f, -0.3962f, -0.3967f, -0.3973f, -0.3977f, -0.3982f, -0.3986f, -0.3989f, -0.3992f, -0.3994f, -0.3996f, -0.3998f, -0.3999f, -0.4f, -0.4f },
            "", "READY", new[] { "Parried", "Step" }, new[] { 0.0f, 0.1667f });
        public static readonly MasterClip ParriedPerfect_P2 = new MasterClip("ParriedPerfect_P2", 36, 1.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.8f, 0.0f, 0.0f,
            new[] { 0.0f, -0.1946f, -0.3893f, -0.4559f, -0.5225f, -0.5892f, -0.6558f, -0.7224f, -0.7293f, -0.7362f, -0.743f, -0.7499f, -0.7568f, -0.7637f, -0.7705f, -0.7774f, -0.7843f, -0.7911f, -0.798f, -0.7982f, -0.7984f, -0.7986f, -0.7988f, -0.799f, -0.7991f, -0.7993f, -0.7994f, -0.7995f, -0.7996f, -0.7997f, -0.7998f, -0.7998f, -0.7999f, -0.7999f, -0.8f, -0.8f, -0.8f },
            "", "READY", new[] { "Parried", "Step" }, new[] { 0.0f, 0.1667f });
        public static readonly MasterClip Exhausted_P2 = new MasterClip("Exhausted_P2", 120, 4.0f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new[] { "Kneel", "Breath", "Breath", "Breath" }, new[] { 0.125f, 0.2167f, 0.4333f, 0.65f });
        public static readonly MasterClip ExhaustedHit_P2 = new MasterClip("ExhaustedHit_P2", 16, 0.5333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "KNEEL", "KNEEL", new string[0], new float[0]);
        public static readonly MasterClip ExhaustedRise_P2 = new MasterClip("ExhaustedRise_P2", 22, 0.7333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "KNEEL", "READY", new string[0], new float[0]);
        public static readonly MasterClip Guard_P3 = new MasterClip("Guard_P3", 20, 0.6667f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "GUARD", new string[0], new float[0]);
        public static readonly MasterClip GuardHit_P3 = new MasterClip("GuardHit_P3", 15, 0.5f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "GUARD", "GUARD", new[] { "Deflect" }, new[] { 0.0667f });
        public static readonly MasterClip Counter_P3 = new MasterClip("Counter_P3", 16, 0.5333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "GUARD", "COIL", new[] { "Deflect" }, new[] { 0.125f });
        public static readonly MasterClip CounterStrike_P3 = new MasterClip("CounterStrike_P3", 26, 0.8667f, 0.1154f, 0.2692f, 0.3462f, 1.6f, 2.5f, 1, new[] { "Master_GlintStaff" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.075f, 0.15f, 0.255f, 0.36f, 0.4725f, 0.51f, 0.5359f, 0.5561f, 0.5705f, 0.5791f, 0.582f, 0.5839f, 0.5883f, 0.5937f, 0.5981f, 0.6f, 0.6f, 0.6f, 0.6f, 0.6f, 0.6f, 0.6f, 0.6f },
            "COIL", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.1154f, 0.2692f, 0.2692f, 0.6923f });
        public static readonly MasterClip Taunt_P3 = new MasterClip("Taunt_P3", 54, 1.8f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new[] { "Beckon", "Beckon" }, new[] { 0.2778f, 0.4444f });
        public static readonly MasterClip Hit_P3 = new MasterClip("Hit_P3", 18, 0.6f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.12f, 0.0f, 0.0f,
            new[] { 0.0f, -0.0292f, -0.0584f, -0.0697f, -0.0811f, -0.0924f, -0.1038f, -0.1067f, -0.1097f, -0.1127f, -0.1157f, -0.1167f, -0.1176f, -0.1183f, -0.1189f, -0.1194f, -0.1197f, -0.1199f, -0.12f },
            "READY", "READY", new string[0], new float[0]);
        public static readonly MasterClip HitHeavy_P3 = new MasterClip("HitHeavy_P3", 27, 0.9f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.42f, 0.0f, 0.0f,
            new[] { 0.0f, -0.0885f, -0.177f, -0.2655f, -0.2906f, -0.3156f, -0.3407f, -0.3658f, -0.3908f, -0.395f, -0.3992f, -0.4034f, -0.4076f, -0.4118f, -0.4161f, -0.4166f, -0.4172f, -0.4177f, -0.4181f, -0.4185f, -0.4189f, -0.4192f, -0.4194f, -0.4196f, -0.4198f, -0.4199f, -0.42f, -0.42f },
            "READY", "READY", new string[0], new float[0]);
        public static readonly MasterClip Parried_P3 = new MasterClip("Parried_P3", 30, 1.0f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.4f, 0.0f, 0.0f,
            new[] { 0.0f, -0.0973f, -0.1946f, -0.2379f, -0.2812f, -0.3244f, -0.3342f, -0.3439f, -0.3537f, -0.3634f, -0.3732f, -0.3829f, -0.3927f, -0.3935f, -0.3942f, -0.3949f, -0.3956f, -0.3962f, -0.3967f, -0.3973f, -0.3977f, -0.3982f, -0.3986f, -0.3989f, -0.3992f, -0.3994f, -0.3996f, -0.3998f, -0.3999f, -0.4f, -0.4f },
            "", "READY", new[] { "Parried", "Step" }, new[] { 0.0f, 0.1667f });
        public static readonly MasterClip ParriedPerfect_P3 = new MasterClip("ParriedPerfect_P3", 36, 1.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.8f, 0.0f, 0.0f,
            new[] { 0.0f, -0.1946f, -0.3893f, -0.4559f, -0.5225f, -0.5892f, -0.6558f, -0.7224f, -0.7293f, -0.7362f, -0.743f, -0.7499f, -0.7568f, -0.7637f, -0.7705f, -0.7774f, -0.7843f, -0.7911f, -0.798f, -0.7982f, -0.7984f, -0.7986f, -0.7988f, -0.799f, -0.7991f, -0.7993f, -0.7994f, -0.7995f, -0.7996f, -0.7997f, -0.7998f, -0.7998f, -0.7999f, -0.7999f, -0.8f, -0.8f, -0.8f },
            "", "READY", new[] { "Parried", "Step" }, new[] { 0.0f, 0.1667f });
        public static readonly MasterClip Exhausted_P3 = new MasterClip("Exhausted_P3", 120, 4.0f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new[] { "Kneel", "Breath", "Breath", "Breath" }, new[] { 0.125f, 0.2167f, 0.4333f, 0.65f });
        public static readonly MasterClip ExhaustedHit_P3 = new MasterClip("ExhaustedHit_P3", 16, 0.5333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "KNEEL", "KNEEL", new string[0], new float[0]);
        public static readonly MasterClip ExhaustedRise_P3 = new MasterClip("ExhaustedRise_P3", 22, 0.7333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "KNEEL", "READY", new string[0], new float[0]);
        public static readonly MasterClip Intro = new MasterClip("Intro", 120, 4.0f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "WAIT", "READY", new[] { "HeadRise", "Salute", "Bow", "Step", "Guard" }, new[] { 0.2167f, 0.4333f, 0.5833f, 0.8f, 0.8667f });
        public static readonly MasterClip PhaseCoat = new MasterClip("PhaseCoat", 110, 3.6667f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY2", new[] { "EyesIgnite", "CoatGrab", "CoatOff", "CoatLand", "CoatRest", "Guard" }, new[] { 0.1636f, 0.2727f, 0.3455f, 0.5545f, 0.6182f, 0.8182f });
        public static readonly MasterClip TwinPalm = new MasterClip("TwinPalm", 38, 1.2667f, 0.3158f, 0.4474f, 0.5f, 1.6f, 1.23f, 1, new[] { "Master_GlintHandR", "Master_GlintHandL" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.266f, 0.4275f, 0.589f, 0.76f, 0.817f, 0.8586f, 0.8882f, 0.9061f, 0.912f, 0.916f, 0.9254f, 0.9366f, 0.946f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f },
            "READY", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.3158f, 0.4474f, 0.4474f, 0.7105f });
        public static readonly MasterClip SpinKick = new MasterClip("SpinKick", 44, 1.4667f, 0.3182f, 0.4318f, 0.4773f, 1.6f, 1.89f, 1, new[] { "Master_GlintFootL" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new[] { "Apex", "Strike", "Step" }, new[] { 0.3182f, 0.4318f, 0.75f });
        public static readonly MasterClip Sweep = new MasterClip("Sweep", 48, 1.6f, 0.25f, 0.3333f, 0.625f, 1.6f, 1.69f, 2, new[] { "Master_GlintFootR" },
            1.9f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new[] { "Apex", "Strike", "SweepEnd", "Step" }, new[] { 0.25f, 0.3333f, 0.625f, 0.7917f });
        public static readonly MasterClip QiWave = new MasterClip("QiWave", 56, 1.8667f, 0.5357f, 0.6429f, 0.6964f, 1.6f, 1.12f, 2, new[] { "Master_GlintHandR", "Master_GlintHandL" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new[] { "Gather", "Apex", "Stomp", "QiRelease", "Strike" }, new[] { 0.375f, 0.5357f, 0.6429f, 0.6429f, 0.6429f });
        public static readonly MasterClip DashStrike = new MasterClip("DashStrike", 36, 1.2f, 0.2222f, 0.4722f, 0.5278f, 0.68f, 1.52f, 2, new[] { "Master_GlintHandR" },
            0.0f, 0.0f, 0.0f, 0.2778f, 0.4444f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.3f, 1.4805f, 2.3863f, 3.15f, 3.8228f, 4.431f, 4.9904f, 5.511f, 6.0f, 6.1312f, 6.225f, 6.2812f, 6.3f, 6.3111f, 6.3397f, 6.3787f, 6.4213f, 6.4603f, 6.4889f, 6.5f, 6.5f, 6.5f, 6.5f, 6.5f, 6.5f, 6.5f, 6.5f, 6.5f },
            "READY", "READY", new[] { "Apex", "DashStart", "DashEnd", "Strike", "Step" }, new[] { 0.2222f, 0.25f, 0.4722f, 0.4722f, 0.6667f });
        public static readonly MasterClip Palm_P3 = new MasterClip("Palm_P3", 34, 1.1333f, 0.2941f, 0.4412f, 0.5f, 1.6f, 2.4f, 1, new[] { "Master_GlintStaff" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.25f, 0.425f, 0.6f, 0.765f, 0.82f, 0.8638f, 0.895f, 0.9138f, 0.92f, 0.9231f, 0.9306f, 0.9394f, 0.9469f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f, 0.95f },
            "READY", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.2941f, 0.4412f, 0.4412f, 0.7353f });
        public static readonly MasterClip ChopPalm_P3 = new MasterClip("ChopPalm_P3", 36, 1.2f, 0.3056f, 0.4722f, 0.5278f, 1.6f, 2.79f, 1, new[] { "Master_GlintStaff" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.126f, 0.252f, 0.405f, 0.558f, 0.72f, 0.774f, 0.8134f, 0.8415f, 0.8584f, 0.864f, 0.8677f, 0.8767f, 0.8873f, 0.8963f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f, 0.9f },
            "READY", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.3056f, 0.4722f, 0.4722f, 0.75f });
        public static readonly MasterClip CraneKick_P3 = new MasterClip("CraneKick_P3", 42, 1.4f, 0.3095f, 0.4286f, 0.4762f, 1.6f, 1.32f, 1, new[] { "Master_GlintFootR" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0075f, 0.03f, 0.0675f, 0.12f, 0.1407f, 0.1926f, 0.26f, 0.3274f, 0.3793f, 0.4f, 0.413f, 0.437f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f },
            "READY", "READY", new[] { "Apex", "Strike", "Step", "Step" }, new[] { 0.3095f, 0.4286f, 0.6667f, 0.8571f });
        public static readonly MasterClip LeapKick_P3 = new MasterClip("LeapKick_P3", 56, 1.8667f, 0.3393f, 0.5893f, 0.6429f, 0.6f, 0.31f, 2, new[] { "Master_GlintFootR" },
            1.8f, 4.79f, 0.0f, 0.3929f, 0.5714f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.075f, 0.15f, 0.7037f, 1.2574f, 1.6823f, 2.1072f, 2.4654f, 2.8236f, 3.1391f, 3.4547f, 3.74f, 4.0253f, 4.2876f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f, 4.55f },
            "READY", "READY", new[] { "Apex", "TakeOff", "Strike", "Land", "Step" }, new[] { 0.3393f, 0.375f, 0.5893f, 0.5893f, 0.625f });
        public static readonly MasterClip Sweep_P3 = new MasterClip("Sweep_P3", 48, 1.6f, 0.25f, 0.3333f, 0.625f, 1.6f, 2.46f, 2, new[] { "Master_GlintStaff" },
            2.3f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new[] { "Apex", "Strike", "SweepEnd", "Step" }, new[] { 0.25f, 0.3333f, 0.625f, 0.7917f });
        public static readonly MasterClip QiWave_P3 = new MasterClip("QiWave_P3", 56, 1.8667f, 0.5357f, 0.6429f, 0.6964f, 1.6f, 0.95f, 2, new[] { "Master_GlintStaff" },
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY", new[] { "Gather", "Apex", "Stomp", "QiRelease", "Strike" }, new[] { 0.375f, 0.5357f, 0.6429f, 0.6429f, 0.6429f });
        public static readonly MasterClip DashStrike_P3 = new MasterClip("DashStrike_P3", 36, 1.2f, 0.2222f, 0.4722f, 0.5278f, 0.68f, 2.43f, 2, new[] { "Master_GlintStaff" },
            0.0f, 0.0f, 0.0f, 0.2778f, 0.4444f,
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.3f, 1.4805f, 2.3863f, 3.15f, 3.8228f, 4.431f, 4.9904f, 5.511f, 6.0f, 6.1312f, 6.225f, 6.2812f, 6.3f, 6.3111f, 6.3397f, 6.3787f, 6.4213f, 6.4603f, 6.4889f, 6.5f, 6.5f, 6.5f, 6.5f, 6.5f, 6.5f, 6.5f, 6.5f, 6.5f },
            "READY", "READY", new[] { "Apex", "DashStart", "DashEnd", "Strike", "Step" }, new[] { 0.2222f, 0.25f, 0.4722f, 0.4722f, 0.6667f });
        public static readonly MasterClip PhaseStaff = new MasterClip("PhaseStaff", 90, 3.0f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "READY3", new[] { "StaffCall", "StaffAppear", "StaffCatch", "StaffPresent", "Guard" }, new[] { 0.0667f, 0.1333f, 0.2778f, 0.5111f, 0.8889f });
        public static readonly MasterClip Defeat = new MasterClip("Defeat", 150, 5.0f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "READY", "MEDITATE", new[] { "Exhale", "StaffDrop", "StaffLand", "Step", "Step", "SitDown", "Meditate" }, new[] { 0.1333f, 0.2f, 0.2667f, 0.4f, 0.48f, 0.6533f, 0.7467f });
        public static readonly MasterClip Meditate = new MasterClip("Meditate", 96, 3.2f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "MEDITATE", "MEDITATE", new string[0], new float[0]);
        public static readonly MasterClip SeatedBow = new MasterClip("SeatedBow", 70, 2.3333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "MEDITATE", "MEDITATE", new[] { "Salute", "Bow", "BowEnd" }, new[] { 0.1714f, 0.4286f, 0.7714f });
        public static readonly MasterClip PoseTest = new MasterClip("PoseTest", 232, 7.7333f, 0.0f, 0.0f, 0.0f, 1.6f, 0.0f, 0, new string[0],
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            null,
            "", "", new string[0], new float[0]);

        static Dictionary<string, MasterClip> all;
        /// <summary>El clip de un estado (null si el FBX no lo tiene).</summary>
        public static MasterClip Get(string state)
        {
            if (all == null)
            {
                all = new Dictionary<string, MasterClip>();
                foreach (var c in new[] { Idle, Walk, Run, StrafeL, StrafeR, WalkBack, Idle_P2, Walk_P2, Run_P2, StrafeL_P2, StrafeR_P2, WalkBack_P2, Idle_P3, Walk_P3, Run_P3, StrafeL_P3, StrafeR_P3, WalkBack_P3, Palm, ChopPalm, CraneKick, LeapKick, Palm_P2, ChopPalm_P2, CraneKick_P2, LeapKick_P2, Guard, GuardHit, Counter, CounterStrike, Taunt, Hit, HitHeavy, Parried, ParriedPerfect, Exhausted, ExhaustedHit, ExhaustedRise, Guard_P2, GuardHit_P2, Counter_P2, CounterStrike_P2, Taunt_P2, Hit_P2, HitHeavy_P2, Parried_P2, ParriedPerfect_P2, Exhausted_P2, ExhaustedHit_P2, ExhaustedRise_P2, Guard_P3, GuardHit_P3, Counter_P3, CounterStrike_P3, Taunt_P3, Hit_P3, HitHeavy_P3, Parried_P3, ParriedPerfect_P3, Exhausted_P3, ExhaustedHit_P3, ExhaustedRise_P3, Intro, PhaseCoat, TwinPalm, SpinKick, Sweep, QiWave, DashStrike, Palm_P3, ChopPalm_P3, CraneKick_P3, LeapKick_P3, Sweep_P3, QiWave_P3, DashStrike_P3, PhaseStaff, Defeat, Meditate, SeatedBow, PoseTest })
                    all[c.State] = c;
            }
            return state != null && all.TryGetValue(state, out var r) ? r : null;
        }
    }
}
