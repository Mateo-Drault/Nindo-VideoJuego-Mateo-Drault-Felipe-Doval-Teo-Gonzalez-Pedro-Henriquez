// Generado por Tools/Audio/build_boss_music.py (install o plan) desde Tools/Audio/boss_music.json: no editar a mano.
// Largos en muestras a la frecuencia del clip; compás en segundos; las entradas son muestras dentro del clip.
namespace Nindo
{
    public static partial class MusicPlan
    {
        static readonly Clip[] clips =
        {
            new Clip("boss_bamboo", 6303706, 44100, 1.764706, ClipKind.Loop),
            new Clip("boss_bamboo_intro", 53231, 44100, 1.764706, ClipKind.Once),
            new Clip("boss_final", 1612800, 44100, 2.285714, ClipKind.Loop),
            new Clip("boss_final_2", 3628800, 44100, 2.285714, ClipKind.Loop),
            new Clip("boss_final_3", 1612800, 44100, 2.285714, ClipKind.Loop),
            new Clip("boss_final_4", 806400, 44100, 2.285714, ClipKind.Loop),
            new Clip("boss_final_intro", 578466, 44100, 2.285714, ClipKind.Once),
            new Clip("boss_final_out", 228360, 44100, 2.285714, ClipKind.Outro),
            new Clip("boss_goro", 3256616, 44100, 1.846154, ClipKind.Loop),
            new Clip("boss_goro_2", 2151492, 44100, 1.742437, ClipKind.Loop),
            new Clip("boss_goro_2_in", 738360, 44100, 1.742437, ClipKind.Once),
            new Clip("boss_goro_intro", 700942, 44100, 1.846154, ClipKind.Once),
            new Clip("boss_goro_out", 156348, 44100, 1.742437, ClipKind.Outro),
            new Clip("boss_lake", 5650780, 44100, 2.033898, ClipKind.Loop),
            new Clip("boss_lake_3", 4305356, 44100, 2.033898, ClipKind.Loop),
            new Clip("boss_lake_intro", 69483, 44100, 2.033898, ClipKind.Once),
            new Clip("boss_lake_out", 134943, 44100, 2.033898, ClipKind.Outro),
            new Clip("ending", 6177093, 44100, 3.0, ClipKind.Loop),
        };

        static readonly Track[] tracks =
        {
            new Track("boss_goro", new[] { new Phase("boss_goro", "boss_goro_intro", 0, 0), new Phase("boss_goro_2", "boss_goro_2_in", 0, 277311) }, "boss_goro_out", 0.0f, true),
            new Track("boss_lake", new[] { new Phase("boss_lake", "boss_lake_intro", 0, 0), new Phase("boss_lake", null, 3229016, 0), new Phase("boss_lake_3", null, 0, 0) }, "boss_lake_out", 0.0f, true),
            new Track("boss_bamboo", new[] { new Phase("boss_bamboo", "boss_bamboo_intro", 0, 0), new Phase("boss_bamboo", null, 3112942, 0), new Phase("boss_bamboo", null, 1867765, 0) }, null, 3.5f, true),
            new Track("boss_final", new[] { new Phase("boss_final", "boss_final_intro", 0, 0), new Phase("boss_final_2", null, 0, 0), new Phase("boss_final_3", null, 0, 0), new Phase("boss_final_4", null, 0, 0) }, "boss_final_out", 0.0f, false),
            new Track("ending", new[] { new Phase("ending", null, 0, 0) }, null, 2.0f, true),
        };
    }
}
