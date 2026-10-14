// Generado por Tools/Unity/chikuo_timings.py desde BambooMaster.fbx.json: no editar a mano.
using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>Tiempos de un clip del Chikuō ermitaño tal como los mide el build de Blender (normalizados 0..1 salvo
    /// que el nombre diga otra cosa).</summary>
    public sealed class ChikuoClip
    {
        public readonly string State;
        public readonly int Frames;
        public readonly float Seconds;
        public readonly bool Loop;
        /// <summary>0 = piso (la raíz en el transform), 1 = posado (la raíz en el PerchNode de la caña), 2 = vuelo (la
        /// raíz la lleva el código por el arco, los pies a su altura), 3 = en el piso con el bastón clavado.</summary>
        public readonly int Space;
        /// <summary>0 = no pega, 1 = dorado (parry), 2 = rojo (dash), 3 = dardo (el golpe lo hace el proyectil).</summary>
        public readonly int Kind;
        public readonly float Apex, Contact, ActiveStart, ActiveEnd, TellStart, TellEnd, LoadStart, LoadEnd, AirStart,
            AirEnd, OpenStart, OpenEnd;
        /// <summary>Radio del disco rojo (barrida, picadas: 0 = sin disco), dónde cae la marca del salto y el alcance
        /// del golpe medidos en metros.</summary>
        public readonly float RingM, MarkerM, ReachM;
        /// <summary>Metros por segundo a los que la locomoción no patina (0 = no es locomoción).</summary>
        public readonly float GroundSpeed;
        /// <summary>Slots de CharacterGlint que se encienden con el aviso.</summary>
        public readonly string[] Glow;
        /// <summary>Metros que avanzó el transform hacia su frente en cada cuadro (null = no se mueve).</summary>
        public readonly float[] Travel;
        /// <summary>Pose con la que empieza y con la que termina (PERCH, READY, HANG, AIR...) y los segundos del
        /// fundido que necesita el empalme (0 = empalma exacto).</summary>
        public readonly string ChainFrom, ChainTo;
        public readonly float FadeFrom, FadeTo;
        /// <summary>Dónde va la raíz del clip de vuelo que sigue respecto de la de este (espacio del modelo de Unity;
        /// Vector3.zero = no cambia de espacio).</summary>
        public readonly Vector3 RootOffset;
        readonly string[] eventNames;
        readonly float[] eventTimes;

        public ChikuoClip(string state, int frames, float seconds, bool loop, int space, int kind, float apex, float contact,
            float activeStart, float activeEnd, float tellStart, float tellEnd, float loadStart, float loadEnd, float airStart,
            float airEnd, float openStart, float openEnd, float ringM, float markerM, float reachM, float groundSpeed,
            string[] glow, float[] travel, string chainFrom, string chainTo, float fadeFrom, float fadeTo, Vector3 rootOffset,
            string[] eventNames, float[] eventTimes)
        {
            State = state; Frames = frames; Seconds = seconds; Loop = loop; Space = space; Kind = kind; Apex = apex;
            Contact = contact; ActiveStart = activeStart; ActiveEnd = activeEnd; TellStart = tellStart; TellEnd = tellEnd;
            LoadStart = loadStart; LoadEnd = loadEnd; AirStart = airStart; AirEnd = airEnd; OpenStart = openStart;
            OpenEnd = openEnd; RingM = ringM; MarkerM = markerM; ReachM = reachM; GroundSpeed = groundSpeed; Glow = glow;
            Travel = travel; ChainFrom = chainFrom; ChainTo = chainTo; FadeFrom = fadeFrom; FadeTo = fadeTo;
            RootOffset = rootOffset; this.eventNames = eventNames; this.eventTimes = eventTimes;
        }

        /// <summary>Tiempo normalizado del primer evento con ese nombre (-1 si el clip no lo tiene).</summary>
        public float Event(string name) => EventAt(name, 0);

        /// <summary>Tiempo normalizado del evento número 'index' con ese nombre (los dardos de una ráfaga: -1 si no hay).</summary>
        public float EventAt(string name, int index)
        {
            for (int i = 0; i < eventNames.Length; i++)
            {
                if (eventNames[i] != name) continue;
                if (index == 0) return eventTimes[i];
                index--;
            }
            return -1f;
        }

        /// <summary>Cuántos eventos con ese nombre trae el clip.</summary>
        public int EventCount(string name)
        {
            int n = 0;
            for (int i = 0; i < eventNames.Length; i++) if (eventNames[i] == name) n++;
            return n;
        }

        /// <summary>Normalizado de un cuadro del clip.</summary>
        public float FrameNorm(float frame) => Frames > 0 ? frame / Frames : 0f;

        /// <summary>Metros avanzados en el tiempo normalizado 'n' (interpolado entre cuadros).</summary>
        public float TravelAt(float n)
        {
            if (Travel == null) return 0f;
            float x = Mathf.Clamp(n, 0f, 1f) * Frames;
            int i = Mathf.Min((int)x, Travel.Length - 1);
            int j = Mathf.Min(i + 1, Travel.Length - 1);
            return Travel[i] + (Travel[j] - Travel[i]) * (x - i);
        }
    }

    public static class ChikuoTimings
    {
        public const float BindHeight = 2.453f;
        /// <summary>Largo de la flauta-bastón (m): el hueso Staff va de la punta de abajo a la de arriba.</summary>
        public const float StaffLength = 2.1f;
        public static readonly ChikuoClip PerchIdle = new ChikuoClip("PerchIdle", 48, 1.6f, true, 1, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "PERCH", "PERCH", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip PerchDart = new ChikuoClip("PerchDart", 24, 0.8f, false, 1, 3,
            0.3333f, 0.0f, 0.0f, 0.0f, 0.0833f, 0.3333f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintChimesHi" },
            null,
            "PERCH", "PERCH", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "DartSpawn" }, new[] { 0.5833f });
        public static readonly ChikuoClip PerchDart2 = new ChikuoClip("PerchDart2", 34, 1.1333f, false, 1, 3,
            0.2353f, 0.0f, 0.0f, 0.0f, 0.0588f, 0.2353f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintChimesHi" },
            null,
            "PERCH", "PERCH", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "DartSpawn", "DartSpawn" }, new[] { 0.4118f, 0.7059f });
        public static readonly ChikuoClip PerchVolley = new ChikuoClip("PerchVolley", 51, 1.7f, false, 1, 3,
            0.2353f, 0.0f, 0.0f, 0.0f, 0.0588f, 0.2353f, 0.0588f, 0.8235f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintChimesHi" },
            null,
            "PERCH", "PERCH", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Load", "DartSpawn", "DartSpawn", "DartSpawn", "Unload" }, new[] { 0.0588f, 0.3333f, 0.549f, 0.7647f, 0.8235f });
        public static readonly ChikuoClip PerchVolley4 = new ChikuoClip("PerchVolley4", 48, 1.6f, false, 1, 3,
            0.2083f, 0.0f, 0.0f, 0.0f, 0.0625f, 0.2083f, 0.0625f, 0.8333f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintChimesHi" },
            null,
            "PERCH", "PERCH", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Load", "DartSpawn", "DartSpawn", "DartSpawn", "DartSpawn", "Unload" }, new[] { 0.0625f, 0.2917f, 0.4583f, 0.625f, 0.8125f, 0.8333f });
        public static readonly ChikuoClip PerchWhistle = new ChikuoClip("PerchWhistle", 42, 1.4f, false, 1, 2,
            0.5714f, 0.0f, 0.0f, 0.0f, 0.0714f, 0.5714f, 0.0714f, 0.7143f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintChimesHi", "Chikuo_GlintStaff" },
            null,
            "PERCH", "PERCH", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Load", "DartSpawn", "Unload" }, new[] { 0.0714f, 0.6429f, 0.7143f });
        public static readonly ChikuoClip TalaShot = new ChikuoClip("TalaShot", 30, 1.0f, false, 1, 2,
            0.4333f, 0.0f, 0.0f, 0.0f, 0.0667f, 0.4333f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintChimesHi", "Chikuo_GlintStaff" },
            null,
            "PERCH", "PERCH", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "DartSpawn" }, new[] { 0.4667f });
        public static readonly ChikuoClip HangDrop = new ChikuoClip("HangDrop", 11, 0.3667f, false, 1, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "PERCH", "HANG", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Hang" }, new[] { 0.9091f });
        public static readonly ChikuoClip HangDart2 = new ChikuoClip("HangDart2", 18, 0.6f, false, 1, 3,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintChimesHi" },
            null,
            "HANG", "", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "DartSpawn", "DartSpawn" }, new[] { 0.5f, 1.0f });
        public static readonly ChikuoClip HangClimb = new ChikuoClip("HangClimb", 15, 0.5f, false, 1, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.5333f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "HANG_END", "PERCH", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Unload", "Perch" }, new[] { 0.5333f, 1.0f });
        public static readonly ChikuoClip PerchLaugh = new ChikuoClip("PerchLaugh", 36, 1.2f, true, 1, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "PERCH", "PERCH", 0.15f, 0.15f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip PerchWobble = new ChikuoClip("PerchWobble", 8, 0.2667f, false, 1, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "PERCH", "PERCH", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip StalkSweep = new ChikuoClip("StalkSweep", 41, 1.3667f, false, 1, 2,
            0.4878f, 0.6341f, 0.5854f, 0.6829f, 0.1951f, 0.4878f, 0.1951f, 0.6341f, 0.0f, 0.0f, 0.0f, 0.0f,
            3.6f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintChimesHi", "Chikuo_GlintChimesLo", "Chikuo_GlintStaff" },
            null,
            "PERCH", "PERCH", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Load", "Contact" }, new[] { 0.1951f, 0.6341f });
        public static readonly ChikuoClip CatapultDraw = new ChikuoClip("CatapultDraw", 30, 1.0f, false, 1, 2,
            0.7333f, 0.0f, 0.0f, 0.0f, 0.0f, 0.7333f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintChimesHi", "Chikuo_GlintChimesLo", "Chikuo_GlintFootR" },
            null,
            "PERCH", "", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Load", "AimFix", "LeaveStalk" }, new[] { 0.0f, 0.7333f, 1.0f });
        public static readonly ChikuoClip CatapultKick = new ChikuoClip("CatapultKick", 15, 0.5f, false, 2, 2,
            0.0f, 1.0f, 1.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintFootR" },
            null,
            "", "DIVE_LAND", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Contact" }, new[] { 1.0f });
        public static readonly ChikuoClip LeapCrouch = new ChikuoClip("LeapCrouch", 7, 0.2333f, false, 1, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "PERCH", "AIR", 0.0f, 0.08f, new Vector3(-0.0f, -0.02f, 0.15f), new[] { "LeaveStalk" }, new[] { 1.0f });
        public static readonly ChikuoClip LeapAir = new ChikuoClip("LeapAir", 12, 0.4f, true, 2, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "AIR", "AIR", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip LeapGrab = new ChikuoClip("LeapGrab", 6, 0.2f, false, 1, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "AIR", "PERCH", 0.08f, 0.0f, new Vector3(-0.45f, -0.02f, -0.35f), new[] { "GrabStalk", "Perch" }, new[] { 0.0f, 1.0f });
        public static readonly ChikuoClip Climb = new ChikuoClip("Climb", 24, 0.8f, false, 1, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.1667f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "", "PERCH", 0.1f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "GrabStalk", "Perch" }, new[] { 0.1667f, 1.0f });
        public static readonly ChikuoClip DecoySpin = new ChikuoClip("DecoySpin", 18, 0.6f, false, 1, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "PERCH", "PERCH", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Dive = new ChikuoClip("Dive", 29, 0.9667f, false, 2, 2,
            0.2759f, 0.9655f, 0.9655f, 0.9655f, 0.069f, 0.3448f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            1.6f, 1.6f, 0.0f, 0.0f, new[] { "Chikuo_GlintFootR", "Chikuo_GlintChimesLo" },
            null,
            "PERCH", "DIVE_LAND", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "LeaveStalk", "Contact" }, new[] { 0.3448f, 0.9655f });
        public static readonly ChikuoClip DiveLand = new ChikuoClip("DiveLand", 14, 0.4667f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, -0.03f, -0.07f, -0.12f, -0.17f, -0.22f, -0.27f, -0.3f, -0.3f },
            "DIVE_LAND", "READY", 0.05f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Land" }, new[] { 0.0f });
        public static readonly ChikuoClip FeetStuck = new ChikuoClip("FeetStuck", 48, 1.6f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.9167f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "DIVE_LAND", "READY", 0.0f, 0.1f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip StaffDrop = new ChikuoClip("StaffDrop", 27, 0.9f, false, 2, 1,
            0.7407f, 0.963f, 0.9259f, 1.0f, 0.0741f, 0.7407f, 0.0f, 0.0f, 0.2222f, 0.7037f, 0.0f, 0.0f,
            0.0f, 0.0f, 2.4f, 0.0f, new[] { "Chikuo_GlintStaff", "Chikuo_GlintChimesHi" },
            null,
            "PERCH", "STAFF_DOWN", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "LeaveStalk", "Land", "Contact" }, new[] { 0.2222f, 0.7037f, 0.963f });
        public static readonly ChikuoClip StaffDropRecover = new ChikuoClip("StaffDropRecover", 12, 0.4f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "STAFF_DOWN", "READY", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Vault = new ChikuoClip("Vault", 27, 0.9f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.3333f, 1.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            new[] { 0.0f, 0.0389f, 0.1111f, 0.15f, 0.2556f, 0.2944f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f, 0.3f },
            "READY", "AIR", 0.0f, 0.0f, new Vector3(-0.0f, 0.4f, 0.35f), new[] { "Plant", "LeaveStalk", "GrabStalk" }, new[] { 0.2222f, 0.3333f, 1.0f });
        public static readonly ChikuoClip JumpCrouch = new ChikuoClip("JumpCrouch", 9, 0.3f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "READY", "AIR", 0.0f, 0.08f, new Vector3(-0.0f, 0.12f, 0.1f), new[] { "LeaveStalk" }, new[] { 1.0f });
        public static readonly ChikuoClip FlungAir = new ChikuoClip("FlungAir", 12, 0.4f, true, 2, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "FLUNG", "FLUNG", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip FlungLand = new ChikuoClip("FlungLand", 11, 0.3667f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "FLUNG", "DAZED_SIT", 0.06f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip DazedSit = new ChikuoClip("DazedSit", 30, 1.0f, true, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "DAZED_SIT", "DAZED_SIT", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip DazedSitHit = new ChikuoClip("DazedSitHit", 10, 0.3333f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "DAZED_SIT", "DAZED_SIT", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Splat = new ChikuoClip("Splat", 9, 0.3f, false, 2, 0,
            0.0f, 0.2222f, 0.2222f, 0.2222f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "FLUNG", "SPLAT", 0.06f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Contact" }, new[] { 0.2222f });
        public static readonly ChikuoClip SlideDown = new ChikuoClip("SlideDown", 18, 0.6f, false, 2, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "SPLAT", "DAZED_SIT", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip MissGrab = new ChikuoClip("MissGrab", 14, 0.4667f, false, 2, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "AIR", "DAZED_LIE", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip DazedLie = new ChikuoClip("DazedLie", 30, 1.0f, true, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "DAZED_LIE", "DAZED_LIE", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip DazedLieHit = new ChikuoClip("DazedLieHit", 10, 0.3333f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "DAZED_LIE", "DAZED_LIE", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Slip = new ChikuoClip("Slip", 15, 0.5f, false, 2, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "", "DAZED_SIT", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Stumble = new ChikuoClip("Stumble", 30, 1.0f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "READY", "READY", 0.08f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip PoleFall = new ChikuoClip("PoleFall", 14, 0.4667f, false, 3, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "BALANCE", "FLUNG", 0.0f, 0.1f, new Vector3(-0.0f, 0.84f, 2.2f), new string[0], new float[0]);
        public static readonly ChikuoClip GetUp = new ChikuoClip("GetUp", 12, 0.4f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.5f, 0.75f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "DAZED_LIE", "READY", 0.1f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Detuned = new ChikuoClip("Detuned", 42, 1.4f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "FLUTE", "READY", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Tuned = new ChikuoClip("Tuned", 36, 1.2f, true, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "DAZED_SIT", "DAZED_SIT", 0.2f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip StaffStuck = new ChikuoClip("StaffStuck", 33, 1.1f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, -0.2111f, -0.2889f, -0.3f, -0.3259f, -0.3741f, -0.4f, -0.4f, -0.4f, -0.4f },
            "READY", "READY", 0.1f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Hit = new ChikuoClip("Hit", 10, 0.3333f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            new[] { 0.0f, -0.1056f, -0.1444f, -0.15f, -0.2f, -0.25f, -0.25f, -0.25f, -0.25f, -0.25f, -0.25f },
            "READY", "READY", 0.06f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip HitHeavy = new ChikuoClip("HitHeavy", 16, 0.5333f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            new[] { 0.0f, -0.2533f, -0.3467f, -0.36f, -0.3975f, -0.48f, -0.5625f, -0.6f, -0.6f, -0.6f, -0.6f, -0.6f, -0.6f, -0.6f, -0.6f, -0.6f, -0.6f },
            "READY", "READY", 0.06f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Parried = new ChikuoClip("Parried", 12, 0.4f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            new[] { 0.0f, -0.0919f, -0.105f, -0.175f, -0.245f, -0.2975f, -0.35f, -0.35f, -0.35f, -0.35f, -0.35f, -0.35f, -0.35f },
            "READY", "READY", 0.06f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip ParriedPerfect = new ChikuoClip("ParriedPerfect", 18, 0.6f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            new[] { 0.0f, -0.1444f, -0.165f, -0.275f, -0.385f, -0.4022f, -0.4431f, -0.4919f, -0.5328f, -0.55f, -0.55f, -0.55f, -0.55f, -0.55f, -0.55f, -0.55f, -0.55f, -0.55f, -0.55f },
            "READY", "READY", 0.06f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Idle = new ChikuoClip("Idle", 48, 1.6f, true, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "READY", "READY", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Walk = new ChikuoClip("Walk", 30, 1.0f, true, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 1.6f, new string[0],
            null,
            "READY", "READY", 0.25f, 0.25f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Step", "Step" }, new[] { 0.2f, 0.7f });
        public static readonly ChikuoClip Run = new ChikuoClip("Run", 20, 0.6667f, true, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 5.5f, new string[0],
            null,
            "READY", "READY", 0.25f, 0.25f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Step", "Step" }, new[] { 0.35f, 0.85f });
        public static readonly ChikuoClip StrafeL = new ChikuoClip("StrafeL", 24, 0.8f, true, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 1.3f, new string[0],
            null,
            "READY", "READY", 0.25f, 0.25f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Step", "Step" }, new[] { 0.2083f, 0.7083f });
        public static readonly ChikuoClip StrafeR = new ChikuoClip("StrafeR", 24, 0.8f, true, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 1.3f, new string[0],
            null,
            "READY", "READY", 0.25f, 0.25f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Step", "Step" }, new[] { 0.2083f, 0.7083f });
        public static readonly ChikuoClip WalkBack = new ChikuoClip("WalkBack", 30, 1.0f, true, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 1.2f, new string[0],
            null,
            "READY", "READY", 0.25f, 0.25f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Step", "Step" }, new[] { 0.2f, 0.7f });
        public static readonly ChikuoClip BackFlip = new ChikuoClip("BackFlip", 12, 0.4f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.1667f, 0.8333f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            new[] { 0.0f, 0.0f, 0.0f, -0.225f, -0.45f, -0.775f, -1.1f, -1.7f, -2.3f, -2.4f, -2.5f, -2.5f, -2.5f },
            "READY", "READY", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip HopBack = new ChikuoClip("HopBack", 14, 0.4667f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.2143f, 0.8571f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            new[] { 0.0f, 0.0f, 0.0f, -0.1f, -0.2f, -0.7f, -1.25f, -1.8f, -2.3f, -2.8f, -3.8063f, -3.95f, -4.0f, -4.0f, -4.0f },
            "READY", "READY", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Thrust = new ChikuoClip("Thrust", 27, 0.9f, false, 0, 1,
            0.3333f, 0.5556f, 0.5185f, 0.6296f, 0.0741f, 0.3333f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 2.4f, 0.0f, new[] { "Chikuo_GlintStaff", "Chikuo_GlintChimesHi" },
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0036f, 0.0288f, 0.0972f, 0.2304f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f, 0.45f },
            "READY", "READY", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Contact" }, new[] { 0.5556f });
        public static readonly ChikuoClip StaffSpin2 = new ChikuoClip("StaffSpin2", 30, 1.0f, false, 0, 1,
            0.3f, 0.5667f, 0.5333f, 0.6f, 0.0667f, 0.3f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 2.3f, 0.0f, new[] { "Chikuo_GlintStaff", "Chikuo_GlintChimesHi" },
            null,
            "READY", "", 0.0f, 0.15f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Contact", "Contact" }, new[] { 0.5667f, 0.9667f });
        public static readonly ChikuoClip CraneKick = new ChikuoClip("CraneKick", 28, 0.9333f, false, 0, 1,
            0.2857f, 0.5357f, 0.5f, 0.5714f, 0.0714f, 0.2857f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 1.2f, 0.0f, new[] { "Chikuo_GlintFootR", "Chikuo_GlintChimesHi" },
            null,
            "READY", "READY", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Contact" }, new[] { 0.5357f });
        public static readonly ChikuoClip NoteSmash = new ChikuoClip("NoteSmash", 36, 1.2f, false, 0, 1,
            0.3889f, 0.5556f, 0.5278f, 0.5833f, 0.0556f, 0.3889f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 2.2f, 0.0f, new[] { "Chikuo_GlintStaff", "Chikuo_GlintChimesHi" },
            new[] { 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.025f, 0.05f, 0.25f, 0.2833f, 0.3167f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f, 0.35f },
            "READY", "READY", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Contact" }, new[] { 0.5556f });
        public static readonly ChikuoClip LowSweep = new ChikuoClip("LowSweep", 39, 1.3f, false, 0, 2,
            0.4103f, 0.6154f, 0.5385f, 0.6923f, 0.1026f, 0.4103f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            2.6f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintStaff", "Chikuo_GlintChimesLo" },
            null,
            "READY", "READY", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Contact" }, new[] { 0.6154f });
        public static readonly ChikuoClip GroundDart = new ChikuoClip("GroundDart", 25, 0.8333f, false, 0, 3,
            0.36f, 0.0f, 0.0f, 0.0f, 0.08f, 0.36f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintChimesHi", "Chikuo_GlintStaff" },
            null,
            "READY", "READY", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "DartSpawn" }, new[] { 0.68f });
        public static readonly ChikuoClip PolePlant = new ChikuoClip("PolePlant", 14, 0.4667f, false, 3, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "READY", "POLE", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Plant" }, new[] { 0.5714f });
        public static readonly ChikuoClip PoleClimb = new ChikuoClip("PoleClimb", 14, 0.4667f, false, 3, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "POLE", "BALANCE", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Load" }, new[] { 0.0f });
        public static readonly ChikuoClip PoleBalance = new ChikuoClip("PoleBalance", 30, 1.0f, true, 3, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "BALANCE", "BALANCE", 0.0f, 0.0f, new Vector3(-0.0f, 1.98f, -0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip PoleDive = new ChikuoClip("PoleDive", 29, 0.9667f, false, 2, 2,
            0.4828f, 0.9655f, 0.9655f, 0.9655f, 0.0f, 0.4828f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            1.4f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintFootR", "Chikuo_GlintChimesLo" },
            null,
            "DIVE_TOP", "DIVE_LAND", 0.0f, 0.06f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "LeaveStalk", "Contact" }, new[] { 0.0f, 0.9655f });
        public static readonly ChikuoClip FluteRaise = new ChikuoClip("FluteRaise", 14, 0.4667f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "READY", "FLUTE", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip FluteNote = new ChikuoClip("FluteNote", 13, 0.4333f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "FLUTE", "FLUTE", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Note" }, new[] { 0.0f });
        public static readonly ChikuoClip AnswerBlow = new ChikuoClip("AnswerBlow", 13, 0.4333f, false, 0, 3,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintChimesHi" },
            null,
            "FLUTE", "FLUTE", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "DartSpawn" }, new[] { 0.3077f });
        public static readonly ChikuoClip AnswerStamp = new ChikuoClip("AnswerStamp", 13, 0.4333f, false, 0, 2,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new[] { "Chikuo_GlintChimesLo" },
            null,
            "FLUTE", "FLUTE", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Stamp" }, new[] { 0.3077f });
        public static readonly ChikuoClip GroundLaugh = new ChikuoClip("GroundLaugh", 36, 1.2f, true, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "READY", "READY", 0.2f, 0.2f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip Intro = new ChikuoClip("Intro", 195, 6.5f, false, 1, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "", "PERCH", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "DartSpawn", "LeaveStalk", "Perch" }, new[] { 0.6923f, 0.759f, 0.8974f });
        public static readonly ChikuoClip PhaseBow = new ChikuoClip("PhaseBow", 120, 4.0f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "DAZED_SIT", "READY", 0.1f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new[] { "Note", "Note", "Note" }, new[] { 0.5833f, 0.7083f, 0.8333f });
        public static readonly ChikuoClip PhaseForest = new ChikuoClip("PhaseForest", 150, 5.0f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.8f, 1.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "READY", "AIR", 0.0f, 0.0f, new Vector3(-0.0f, 0.4f, 0.35f), new[] { "Note", "Note", "LeaveStalk", "GrabStalk" }, new[] { 0.4f, 0.6f, 0.8f, 1.0f });
        public static readonly ChikuoClip Defeat = new ChikuoClip("Defeat", 165, 5.5f, false, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "READY", "CROSS", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);
        public static readonly ChikuoClip DefeatIdle = new ChikuoClip("DefeatIdle", 60, 2.0f, true, 0, 0,
            0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f, 0.0f,
            0.0f, 0.0f, 0.0f, 0.0f, new string[0],
            null,
            "CROSS", "CROSS", 0.0f, 0.0f, new Vector3(0.0f, 0.0f, 0.0f), new string[0], new float[0]);

        /// <summary>Los nombres que Enemy toca por config y no son clips propios (el controller los tiene como estados
        /// con el clip de otro).</summary>
        static readonly Dictionary<string, string> aliases = new Dictionary<string, string>
        {
            { "Guard", "Idle" },
            { "Counter", "Idle" },
            { "Spotted", "Idle" },
            { "Exhausted", "DazedSit" },
            { "ExhaustedHit", "DazedSitHit" },
            { "ExhaustedRise", "GetUp" },
        };

        static Dictionary<string, ChikuoClip> all;
        /// <summary>El clip de un estado o de un alias (null si el FBX no lo tiene).</summary>
        public static ChikuoClip Get(string state)
        {
            if (all == null)
            {
                all = new Dictionary<string, ChikuoClip>();
                foreach (var c in new[] { PerchIdle, PerchDart, PerchDart2, PerchVolley, PerchVolley4, PerchWhistle, TalaShot, HangDrop, HangDart2, HangClimb, PerchLaugh, PerchWobble, StalkSweep, CatapultDraw, CatapultKick, LeapCrouch, LeapAir, LeapGrab, Climb, DecoySpin, Dive, DiveLand, FeetStuck, StaffDrop, StaffDropRecover, Vault, JumpCrouch, FlungAir, FlungLand, DazedSit, DazedSitHit, Splat, SlideDown, MissGrab, DazedLie, DazedLieHit, Slip, Stumble, PoleFall, GetUp, Detuned, Tuned, StaffStuck, Hit, HitHeavy, Parried, ParriedPerfect, Idle, Walk, Run, StrafeL, StrafeR, WalkBack, BackFlip, HopBack, Thrust, StaffSpin2, CraneKick, NoteSmash, LowSweep, GroundDart, PolePlant, PoleClimb, PoleBalance, PoleDive, FluteRaise, FluteNote, AnswerBlow, AnswerStamp, GroundLaugh, Intro, PhaseBow, PhaseForest, Defeat, DefeatIdle })
                    all[c.State] = c;
            }
            if (state == null) return null;
            if (aliases.TryGetValue(state, out var real)) state = real;
            return all.TryGetValue(state, out var r) ? r : null;
        }
    }
}
