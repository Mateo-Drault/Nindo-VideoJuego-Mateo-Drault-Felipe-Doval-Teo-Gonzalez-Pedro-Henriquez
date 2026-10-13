using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>Sprites de UI dibujados por Tools/UI/build_ui_art.py (Resources/UI). Pueden faltar: quien
    /// los usa tiene que tolerar null.</summary>
    public static class UISprites
    {
        static readonly Dictionary<string, Sprite> cache = new Dictionary<string, Sprite>();
        static Texture2D profile;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { cache.Clear(); profile = null; }

        public static Sprite Get(string name)
        {
            if (string.IsNullOrEmpty(name)) return null;
            if (!cache.TryGetValue(name, out var s)) { s = Resources.Load<Sprite>("UI/" + name); cache[name] = s; }
            return s;
        }

        // paneles y piezas del kit "Tinta y Bandana"
        public static Sprite BrushSwash => Get("BrushSwash");
        /// <summary>Trazo para poner texto encima: núcleo parejo hasta u ~0.8 (UIFactory.FitBanner).</summary>
        public static Sprite BrushBanner => Get("BrushBanner");
        public static Sprite BrushLine => Get("BrushLine");
        public static Sprite InkPanel => Get("InkPanel");
        public static Sprite InkCard => Get("InkCard");
        public static Sprite KeyCap => Get("KeyCap");
        public static Sprite KeyRound => Get("KeyRound");
        public static Sprite Kunai => Get("Kunai");
        public static Sprite Pip => Get("Pip");
        public static Sprite SealDisc => Get("SealDisc");
        public static Sprite Ring => Get("Ring");
        public static Sprite BossBarBack => Get("BossBarBack");
        public static Sprite BossBarFill => Get("BossBarFill");
        public static Sprite DragonEye => Get("DragonEye");
        public static Sprite SoftDot => Get("SoftDot");

        // indicador de guardado (UI/SaveIndicator): pergamino, pincel y el sello del nudo
        public static Sprite ScrollPaper => Get("ScrollPaper");
        public static Sprite ScrollRod => Get("ScrollRod");
        public static Sprite Fude => Get("Fude");

        // marcadores de combate (blancos con contorno de tinta: se tiñen)
        public static Sprite Unblockable => Get("IconUnblockable");
        public static Sprite Alert => Get("IconAlert");
        public static Sprite Guard => Get("IconGuard");
        public static Sprite Finisher => Get("IconFinisher");
        public static Sprite Boss => Get("IconBoss");
        /// <summary>Nombre viejo del ícono de imparable (era un estallido con "!"): ahora el rombo con >>.</summary>
        public static Sprite Danger => Unblockable;

        /// <summary>Perfil del lomo del dragón (generate_assets.py: R cresta, G piel, B panza, en v del sprite).</summary>
        public static Texture2D SpiritProfile => profile != null ? profile : (profile = Resources.Load<Texture2D>("UI/SpiritProfile"));

        /// <summary>Pictograma de cada zona (el id de Zone; ver StoryText.ConfigureZone).</summary>
        public static string ZoneIconName(string zoneId)
        {
            switch (zoneId)
            {
                case "hogar": return "ZoneHome";
                case "campos": return "ZoneFields";
                case "bosque": return "ZoneForest";
                case "muralla": return "ZoneWall";
                case "jardin": return "ZoneGarden";
                case "dojo": return "ZoneDojo";
                case "montana": return "ZoneMountain";
                case "lago": return "ZoneLake";
                case "bambu": return "ZoneBamboo";
                default: return null;
            }
        }

        public static string SealIconName(SealId s) => s == SealId.Montana ? "ZoneMountain" : s == SealId.Lago ? "ZoneLake" : "ZoneBamboo";

        // un solo nombre por sello: el HUD decía "Sello del Lago" y Kaito, los objetivos y la puerta, "Sello del Agua"
        public static string SealName(SealId s) => StoryText.SealName(s);

        /// <summary>Sello rojo (hanko) con el pictograma calado: "Hanko_" + nombre del ícono.</summary>
        public static Sprite Hanko(string iconName) => string.IsNullOrEmpty(iconName) ? null : Get("Hanko_" + iconName);
    }
}
