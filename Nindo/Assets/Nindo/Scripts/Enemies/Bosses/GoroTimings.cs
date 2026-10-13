// Generado por Tools/Unity/goro_timings.py desde GoroAnims.fbx.json y Kit_goro_armor.fbx.json: no editar a mano.
using UnityEngine;

namespace Nindo
{
    /// <summary>Tiempos (s desde el arranque del clip a velocidad 1) y lugares de los clips de Gorō y de su armadura.</summary>
    public static class GoroTimings
    {
        // FakeDefeat: de rodilla, suelta el martillo, el martillo pega el piso, la espalda pega el piso, quieto
        public const float FakeLength = 2.6f, FakeKnee = 0.5333f, FakeDrop = 1.4333f, FakeHammerLand = 1.9667f, FakeBackHit = 2.0f, FakeStill = 2.4333f;
        // ArmorRise: agarra el mango, se sienta, de rodilla, de pie, arranca el martillo, ruge, abre los brazos
        public const float RiseLength = 7.0f, RiseGrab = 2.8667f, RiseSit = 3.9667f, RiseKneel = 4.2f, RiseStand = 4.9333f, RisePull = 5.6667f,
            RiseRoar = 6.1333f, RisePeak = 6.3333f;
        // AvalancheSummon: los dos martillazos al piso, la llamada a la montaña, el fin del rugido y el de la armadura
        public const float AvalLength = 3.0f, AvalStrike1 = 0.8f, AvalStrike2 = 1.2333f, AvalCall = 2.0f, AvalRoarEnd = 2.5f, AvalArmorEnd = 2.6f;
        // Intro: el martillazo al piso y el cuadro en que el martillo ya está en el hombro (arranque de la re-presentación)
        public const float IntroLength = 2.8f, IntroSlam = 0.4333f, IntroRiseNorm = 0.3095f;

        // dónde cae la cabeza del martillo, en el transform de Gorō: x = derecha, y = adelante (m)
        public static readonly Vector2 IntroSlamAt = new Vector2(0.25f, 3.45f);
        public static readonly Vector2 AvalStrike1At = new Vector2(0.45f, 3.67f);
        public static readonly Vector2 AvalStrike2At = new Vector2(-0.25f, 3.82f);
        public static readonly Vector2 HeavyLandAt = new Vector2(-0.05f, 3.7f);
        public static readonly Vector2 SlamWaveAt = new Vector2(-0.05f, 3.9f);

        /// <summary>Ventana (normalizada) en que la armadura rebota los cortes mientras carga el golpe ('armor_window').</summary>
        public static bool ArmorWindow(string state, out float from, out float to)
        {
            switch (state)
            {
                case "Combo1B": from = 0.1017f; to = 0.6271f; return true;
                case "Combo2B": from = 0.087f; to = 0.5435f; return true;
                case "Combo3B": from = 0.0877f; to = 0.6491f; return true;
                case "SlamWave": from = 0.0781f; to = 0.5625f; return true;
                default: from = to = 0f; return false;
            }
        }

        /// <summary>Una pieza de la armadura: cuándo se pega (s de ArmorRise), cuánto gira al volar y de qué lado sale
        /// (espacio local de Gorō, Kit_goro_armor.fbx.json 'start_unity').</summary>
        public readonly struct Piece
        {
            public readonly string name;
            public readonly float slam, spin;
            public readonly Vector3 axis, from;
            public Piece(string n, float s, float sp, Vector3 ax, Vector3 fr) { name = n; slam = s; spin = sp; axis = ax.normalized; from = fr; }
        }

        public static readonly Piece[] Pieces =
        {
            new Piece("Greave_L", 0.8f, 200.0f, new Vector3(0.8876f, 0.4379f, -0.1429f), new Vector3(-2.6f, -0.3f, -1.8f)),
            new Piece("Greave_R", 1.0f, 220.0f, new Vector3(0.1171f, 0.879f, -0.4622f), new Vector3(2.8f, -0.3f, -1.4f)),
            new Piece("Knee_L", 1.2667f, 260.0f, new Vector3(0.6669f, 0.2002f, -0.7178f), new Vector3(-3.4f, -0.3f, 1.0f)),
            new Piece("Knee_R", 1.4667f, 240.0f, new Vector3(0.2791f, 0.5968f, -0.7523f), new Vector3(3.6f, -0.3f, 0.6f)),
            new Piece("Tasset_L", 1.7333f, 180.0f, new Vector3(-0.1669f, 0.7071f, -0.6871f), new Vector3(-4.2f, -0.3f, -0.6f)),
            new Piece("Tasset_R", 1.8667f, 200.0f, new Vector3(-0.6266f, 0.5556f, -0.5465f), new Vector3(4.0f, -0.3f, -1.2f)),
            new Piece("Bracer_R", 2.3333f, 300.0f, new Vector3(0.329f, 0.6242f, 0.7086f), new Vector3(3.2f, -0.3f, 2.6f)),
            new Piece("Bracer_L", 2.5333f, 280.0f, new Vector3(0.5998f, 0.5965f, 0.5333f), new Vector3(-3.4f, -0.3f, 2.4f)),
            new Piece("Chest_Low", 3.0667f, 160.0f, new Vector3(0.3482f, 0.6562f, 0.6694f), new Vector3(-0.6f, -0.3f, 4.6f)),
            new Piece("Chest_High", 3.3333f, 180.0f, new Vector3(0.6125f, 0.6774f, -0.4075f), new Vector3(0.8f, -0.3f, 5.0f)),
            new Piece("Pauldron_L", 3.9333f, 220.0f, new Vector3(0.5757f, 0.4057f, -0.7099f), new Vector3(-5.2f, -0.3f, -2.2f)),
            new Piece("Pauldron_R", 4.2667f, 240.0f, new Vector3(-0.6935f, 0.3359f, -0.6374f), new Vector3(5.4f, -0.3f, -1.6f)),
            new Piece("Ridge_L", 4.8667f, 140.0f, new Vector3(0.9774f, 0.2073f, -0.0406f), new Vector3(-2.4f, -0.3f, -6.0f)),
            new Piece("Ridge_R", 5.0667f, 160.0f, new Vector3(-0.7908f, 0.585f, -0.1799f), new Vector3(2.2f, -0.3f, -6.2f)),
            new Piece("Horn_L", 5.6667f, 320.0f, new Vector3(-0.6987f, 0.6839f, 0.21f), new Vector3(-1.6f, 5.5f, -4.4f)),
            new Piece("Horn_R", 5.8f, 340.0f, new Vector3(-0.8706f, 0.1879f, 0.4547f), new Vector3(1.6f, 5.8f, -4.2f)),
        };
    }
}
