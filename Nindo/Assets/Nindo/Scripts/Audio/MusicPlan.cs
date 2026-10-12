// Generado por Tools/Audio/build_boss_music.py (install o plan) desde Tools/Audio/boss_music.json: no editar a mano.
// Largos en muestras a la frecuencia del clip; compás en segundos; las entradas son muestras dentro del clip.
namespace Nindo
{
    public static partial class MusicPlan
    {
        static readonly Clip[] clips =
        {
            new Clip("boss_bamboo", 3112942, 44100, 1.764706, ClipKind.Loop),
            new Clip("boss_bamboo_2", 3190764, 44100, 1.764706, ClipKind.Loop),
            new Clip("boss_bamboo_2_in", 155647, 44100, 1.764706, ClipKind.Once),
            new Clip("boss_bamboo_3", 2350404, 44100, 1.665565, ClipKind.Loop),
            new Clip("boss_bamboo_3_in", 146832, 44100, 1.665565, ClipKind.Once),
            new Clip("boss_bamboo_intro", 53231, 44100, 1.764706, ClipKind.Once),
            new Clip("boss_bamboo_out", 132300, 44100, 1.764706, ClipKind.Outro),
            new Clip("boss_bamboo_out_3", 124868, 44100, 1.665565, ClipKind.Outro),
            new Clip("boss_final", 3225600, 44100, 2.285714, ClipKind.Loop),
            new Clip("boss_final_2", 2822400, 44100, 2.285714, ClipKind.Loop),
            new Clip("boss_final_2_in", 201600, 44100, 2.285714, ClipKind.Once),
            new Clip("boss_final_3", 1902684, 44100, 2.157303, ClipKind.Loop),
            new Clip("boss_final_3_in", 190260, 44100, 2.157303, ClipKind.Once),
            new Clip("boss_final_4", 1436827, 44100, 2.036364, ClipKind.Loop),
            new Clip("boss_final_4_in", 179585, 44100, 2.036364, ClipKind.Once),
            new Clip("boss_final_intro", 477666, 44100, 2.285714, ClipKind.Once),
            new Clip("boss_final_out", 216195, 44100, 2.157303, ClipKind.Outro),
            new Clip("boss_final_out_4", 204281, 44100, 2.036364, ClipKind.Outro),
            new Clip("boss_goro", 5861908, 44100, 1.846154, ClipKind.Loop),
            new Clip("boss_goro_2", 5225220, 44100, 1.742437, ClipKind.Loop),
            new Clip("boss_goro_2_in", 738360, 44100, 1.742437, ClipKind.Once),
            new Clip("boss_goro_intro", 700942, 44100, 1.846154, ClipKind.Once),
            new Clip("boss_goro_out", 156348, 44100, 1.742437, ClipKind.Outro),
            new Clip("boss_goro_out_1", 165654, 44100, 1.846154, ClipKind.Outro),
            new Clip("boss_lake", 2870237, 44100, 2.033898, ClipKind.Loop),
            new Clip("boss_lake_2", 2332068, 44100, 2.033898, ClipKind.Loop),
            new Clip("boss_lake_2_in", 179389, 44100, 2.033898, ClipKind.Once),
            new Clip("boss_lake_3", 1523760, 44100, 1.919634, ClipKind.Loop),
            new Clip("boss_lake_3_in", 169260, 44100, 1.919634, ClipKind.Once),
            new Clip("boss_lake_intro", 607652, 44100, 2.033898, ClipKind.Once),
            new Clip("boss_lake_out", 134943, 44100, 2.033898, ClipKind.Outro),
            new Clip("boss_lake_out_3", 127362, 44100, 1.919634, ClipKind.Outro),
            new Clip("ending", 6177093, 44100, 3.0, ClipKind.Once),
        };

        static readonly Track[] tracks =
        {
            new Track("boss_goro", new[] { new Phase("boss_goro", "boss_goro_intro", 0, 700942, 0.0f, "boss_goro_out_1"), new Phase("boss_goro_2", "boss_goro_2_in", 277311, 584677, 0.04f, null) }, "boss_goro_out", 0.0f, true),
            new Track("boss_lake", new[] { new Phase("boss_lake", "boss_lake_intro", 0, 607652, 0.0f, null), new Phase("boss_lake_2", "boss_lake_2_in", 0, 179389, 0.0f, null), new Phase("boss_lake_3", "boss_lake_3_in", 0, 169260, 0.04f, "boss_lake_out_3") }, "boss_lake_out", 0.0f, true),
            new Track("boss_bamboo", new[] { new Phase("boss_bamboo", "boss_bamboo_intro", 0, 53231, 0.0f, null), new Phase("boss_bamboo_2", "boss_bamboo_2_in", 0, 155647, 0.0f, null), new Phase("boss_bamboo_3", "boss_bamboo_3_in", 0, 146832, 0.04f, "boss_bamboo_out_3") }, "boss_bamboo_out", 0.0f, true),
            new Track("boss_final", new[] { new Phase("boss_final", "boss_final_intro", 0, 477666, 0.0f, null), new Phase("boss_final_2", "boss_final_2_in", 0, 201600, 0.0f, null), new Phase("boss_final_3", "boss_final_3_in", 0, 190260, 0.05f, null), new Phase("boss_final_4", "boss_final_4_in", 0, 179585, 0.05f, "boss_final_out_4") }, "boss_final_out", 0.0f, false),
            new Track("ending", new[] { new Phase("ending", null, 0, 0, 0.0f, null) }, null, 2.0f, false),
        };
    }
}
