"""Genera Scripts/Enemies/Bosses/GoroTimings.cs desde los dos sidecars de Gorō:
  * Art/Characters/TeamAnims/GoroAnims.fbx.json (build_team_anims goro --export): duración y eventos de FakeDefeat,
    ArmorRise, AvalancheSummon e Intro, las ventanas de armadura de los golpes de la fase 2 y dónde pega la cabeza del
    martillo en cada golpe al piso (timing['impacts'], marco de autoría);
  * Art/Characters/Kits/Kit_goro_armor.fbx.json (build_goro_armor): las 16 piezas, su orden, el giro del vuelo y de
    dónde salen.
GoroBoss y GoroArmor leen solo de acá: antes los cuadros iban a mano en el código (6/54..37/54, 184f/30f...) y re-autorar
un clip los despegaba sin aviso. Si se rehace un clip o la armadura, se corre este script y se recompila.

Uso: python Tools/Unity/goro_timings.py
"""
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unity_yaml as U

ART = os.path.join(U.ASSETS, "Nindo", "Art", "Characters")
ANIMS = os.path.join(ART, "TeamAnims", "GoroAnims.fbx.json")
KIT = os.path.join(ART, "Kits", "Kit_goro_armor.fbx.json")
DST = os.path.join(U.ASSETS, "Nindo", "Scripts", "Enemies", "Bosses", "GoroTimings.cs")

# los golpes de la fase 2 con armadura que rebota los cortes (GoroBoss.InArmorWindow)
ARMOR_STATES = ("Combo1B", "Combo2B", "Combo3B", "SlamWave")
# (constante, clip, evento) de dónde cae la cabeza del martillo
IMPACTS = (("IntroSlamAt", "Intro", "slam"), ("AvalStrike1At", "AvalancheSummon", "strike1"),
           ("AvalStrike2At", "AvalancheSummon", "strike2"), ("HeavyLandAt", "Heavy", "land"), ("SlamWaveAt", "SlamWave", "wave"))


def f(x):
    s = ("%.4f" % float(x)).rstrip("0")
    if s.endswith("."):
        s += "0"
    return s + "f"


def main():
    anims = json.load(open(ANIMS, encoding="utf-8"))
    kit = json.load(open(KIT, encoding="utf-8"))
    fps = float(anims["fps"])
    clips = anims["clips"]

    def ev(clip, name):
        return clips[clip]["timing"]["events"][name] / fps

    out = []
    w = out.append
    w("// Generado por Tools/Unity/goro_timings.py desde GoroAnims.fbx.json y Kit_goro_armor.fbx.json: no editar a mano.")
    w("using UnityEngine;")
    w("")
    w("namespace Nindo")
    w("{")
    w("    /// <summary>Tiempos (s desde el arranque del clip a velocidad 1) y lugares de los clips de Gorō y de su armadura.</summary>")
    w("    public static class GoroTimings")
    w("    {")
    fd = clips["FakeDefeat"]
    w("        // FakeDefeat: de rodilla, suelta el martillo, el martillo pega el piso, la espalda pega el piso, quieto")
    w("        public const float FakeLength = %s, FakeKnee = %s, FakeDrop = %s, FakeHammerLand = %s, FakeBackHit = %s, FakeStill = %s;" % (
        f(fd["seconds"]), f(ev("FakeDefeat", "knee")), f(ev("FakeDefeat", "drop")), f(ev("FakeDefeat", "hammer_land")),
        f(ev("FakeDefeat", "back_hit")), f(ev("FakeDefeat", "still"))))
    ar = clips["ArmorRise"]
    w("        // ArmorRise: agarra el mango, se sienta, de rodilla, de pie, arranca el martillo, ruge, abre los brazos")
    w("        public const float RiseLength = %s, RiseGrab = %s, RiseSit = %s, RiseKneel = %s, RiseStand = %s, RisePull = %s," % (
        f(ar["seconds"]), f(ev("ArmorRise", "grab")), f(ev("ArmorRise", "sit")), f(ev("ArmorRise", "kneel")),
        f(ev("ArmorRise", "stand")), f(ev("ArmorRise", "pull"))))
    w("            RiseRoar = %s, RisePeak = %s;" % (f(ev("ArmorRise", "roar")), f(ev("ArmorRise", "roar_peak"))))
    av = clips["AvalancheSummon"]
    aw = av["timing"]["armor_window"]
    w("        // AvalancheSummon: los dos martillazos al piso, la llamada a la montaña, el fin del rugido y el de la armadura")
    w("        public const float AvalLength = %s, AvalStrike1 = %s, AvalStrike2 = %s, AvalCall = %s, AvalRoarEnd = %s, AvalArmorEnd = %s;" % (
        f(av["seconds"]), f(ev("AvalancheSummon", "strike1")), f(ev("AvalancheSummon", "strike2")), f(ev("AvalancheSummon", "call")),
        f(ev("AvalancheSummon", "roar_end")), f(aw[1] / fps)))
    it = clips["Intro"]
    w("        // Intro: el martillazo al piso y el cuadro en que el martillo ya está en el hombro (arranque de la re-presentación)")
    w("        public const float IntroLength = %s, IntroSlam = %s, IntroRiseNorm = %s;" % (
        f(it["seconds"]), f(ev("Intro", "slam")), f(it["timing"]["events"]["rise"] / it["frames"])))
    w("")
    w("        // dónde cae la cabeza del martillo, en el transform de Gorō: x = derecha, y = adelante (m)")
    for const, clip, name in IMPACTS:
        x, y = clips[clip]["timing"]["impacts"][name]
        # marco de autoría: +X izquierda, -Y adelante
        w("        public static readonly Vector2 %s = new Vector2(%s, %s);" % (const, f(-x), f(-y)))
    w("")
    sw, swp = clips["SlamWave"], clips["SlamWavePlanted"]
    w("        /// <summary>El aviso agachado del SlamWave: desde que se agacha (el arranque de la pausa del aviso, normalizado) el")
    w("        /// cuerpo con la armadura llega hasta acá por delante del centro (m: lo más cerca que puede estar el centro de Kaito,")
    w("        /// build_team_anims body_reach_m 'aviso' de SlamWavePlanted, que hasta el apex es el mismo clip). GoroBoss.ClearCrouch.</summary>")
    w("        public const float SlamWaveCrouchFrom = %s, SlamWaveCrouchReach = %s;" % (
        f(sw["timing"]["hold"][0] / sw["frames"]), f(swp["lint"]["body_reach_m"]["aviso"])))
    w("")
    w("        /// <summary>Ventana (normalizada) en que la armadura rebota los cortes mientras carga el golpe ('armor_window').</summary>")
    w("        public static bool ArmorWindow(string state, out float from, out float to)")
    w("        {")
    w("            switch (state)")
    w("            {")
    for st in ARMOR_STATES:
        c = clips[st]
        a, b = c["timing"]["armor_window"]
        w("                case \"%s\": from = %s; to = %s; return true;" % (st, f(a / c["frames"]), f(b / c["frames"])))
    w("                default: from = to = 0f; return false;")
    w("            }")
    w("        }")
    w("")
    w("        /// <summary>Una pieza de la armadura: cuándo se pega (s de ArmorRise), cuánto gira al volar y de qué lado sale")
    w("        /// (espacio local de Gorō, Kit_goro_armor.fbx.json 'start_unity').</summary>")
    w("        public readonly struct Piece")
    w("        {")
    w("            public readonly string name;")
    w("            public readonly float slam, spin;")
    w("            public readonly Vector3 axis, from;")
    w("            public Piece(string n, float s, float sp, Vector3 ax, Vector3 fr) { name = n; slam = s; spin = sp; axis = ax.normalized; from = fr; }")
    w("        }")
    w("")
    w("        public static readonly Piece[] Pieces =")
    w("        {")
    for p in sorted(kit["pieces"], key=lambda p: p["order"]):
        slam = clips["ArmorRise"]["timing"]["events"]["slam_" + p["name"]]
        if slam != p["slam_frame"]:
            raise SystemExit("la pieza %s se pega en f%d en el kit y en f%d en ArmorRise: re-exportar los dos" % (p["name"], p["slam_frame"], slam))
        ax, st = p["spin_axis_unity"], p["start_unity"]
        w("            new Piece(\"%s\", %s, %s, new Vector3(%s, %s, %s), new Vector3(%s, %s, %s))," % (
            p["name"], f(slam / fps), f(p["spin_deg"]), f(ax[0]), f(ax[1]), f(ax[2]), f(st[0]), f(st[1]), f(st[2])))
    w("        };")
    w("    }")
    w("}")
    U.write(DST, "\n".join(out) + "\n")
    U.write_meta(DST, U.MONO_META)
    print("escrito", os.path.relpath(DST, U.REPO))


if __name__ == "__main__":
    main()
