using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;

namespace Nindo
{
    [Serializable]
    public class SaveData
    {
        public int version = 1;
        public string checkpoint = "";            // id del último santuario
        public List<string> flags = new List<string>();
        public bool[] seals = new bool[3];
        public float playTime;
        public int deaths;
        /// <summary>Santuarios donde Kaito ya rezó con incienso: quedan con el humo y la brasa (World/ShrineIncense).</summary>
        public List<string> shrines = new List<string>();
        /// <summary>Sellos ya puestos en la puerta del dojo (World/SealGate): se ponen de a uno, apenas se tienen.</summary>
        public bool[] sealsPlaced = new bool[3];

        public bool HasFlag(string f) => flags.Contains(f);
        public void SetFlag(string f)
        {
            if (string.IsNullOrEmpty(f) || flags.Contains(f)) return;
            flags.Add(f);
            GameEvents.RaiseFlag(f);
        }
        public bool HasSeal(SealId s) => seals != null && seals.Length > (int)s && seals[(int)s];
        public bool SealPlaced(SealId s) => sealsPlaced != null && sealsPlaced.Length > (int)s && sealsPlaced[(int)s];
        public int SealCount
        {
            get { int n = 0; if (seals != null) foreach (var s in seals) if (s) n++; return n; }
        }
        /// <summary>Niebla del mapa: lo que Kaito ya vio, en bits (MapFog). Vacío en las partidas de antes del mapa.
        /// Al final: es el renglón largo del JSON.</summary>
        public string mapFog = "";
    }

    /// <summary>Guardado en JSON (Application.persistentDataPath/nindo_save.json).</summary>
    public static class SaveSystem
    {
        static SaveData data;
        static string PathFile => System.IO.Path.Combine(Application.persistentDataPath, "nindo_save.json");

        public static SaveData Data
        {
            get { if (data == null) data = new SaveData(); return data; }
        }

        public static bool HasSave => File.Exists(PathFile);

        public static void NewGame()
        {
            data = new SaveData();
        }

        public static bool Load()
        {
            try
            {
                if (!File.Exists(PathFile)) { data = new SaveData(); return false; }
                data = JsonUtility.FromJson<SaveData>(File.ReadAllText(PathFile)) ?? new SaveData();
                if (data.seals == null || data.seals.Length != 3) data.seals = new bool[3];
                if (data.shrines == null) data.shrines = new List<string>();
                if (data.sealsPlaced == null || data.sealsPlaced.Length != 3) data.sealsPlaced = new bool[3];
                MigrateWallGate(data);
                return true;
            }
            catch (Exception e)
            {
                Debug.LogWarning("[Nindo] No se pudo leer la partida: " + e.Message);
                data = new SaveData();
                return false;
            }
        }

        /// <summary>
        /// El portón de la muralla ya no se abre solo: lo abre Kaito con la bandana desde el sur (WallSeal), después de la
        /// pelea de la muralla. Una partida de antes que ya pasó al otro lado sin 'wall_gate_open' (la del juego completo
        /// del equipo no lo tiene) cargaba con el sello puesto detrás de Kaito, un santuario al norte desde el que no se
        /// puede volver y medio mapa en niebla para siempre (MapFog la ve cerrada). Si la partida prueba que cruzó, el
        /// portón queda abierto y la pelea ganada. Directo en la lista: al cargar no hay nadie escuchando GameEvents.
        /// </summary>
        static void MigrateWallGate(SaveData d)
        {
            if (d.HasFlag(Flags.WallGateOpen)) return;
            bool crossed = d.SealCount > 0 || d.HasFlag(Flags.DojoGateSeen);
            foreach (var f in d.flags)
            {
                if (crossed) break;
                if (f == null) continue;
                crossed = f.StartsWith("boss_", StringComparison.Ordinal) || Array.IndexOf(NorthOfWall, f) >= 0;
            }
            if (!crossed) return;
            d.flags.Add(Flags.WallGateOpen);
            if (!d.HasFlag(Flags.Encounter("wall"))) d.flags.Add(Flags.Encounter("wall"));
        }

        /// <summary>Zonas que solo se pisan del otro lado de la muralla.</summary>
        static readonly string[] NorthOfWall = { "zone_jardin", "zone_montana", "zone_lago", "zone_lago_cascada", "zone_bambu", "zone_dojo" };

        public static void Save()
        {
            MapFog.Store(Data);
            try { File.WriteAllText(PathFile, JsonUtility.ToJson(Data, true)); }
            catch (Exception e) { Debug.LogWarning("[Nindo] No se pudo guardar: " + e.Message); return; }
            GameEvents.RaiseSaved();
        }

        public static void Delete()
        {
            try { if (File.Exists(PathFile)) File.Delete(PathFile); } catch { }
            data = new SaveData();
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { data = null; }
    }

    /// <summary>Opciones del jugador (PlayerPrefs).</summary>
    public static class Settings
    {
        public static float MasterVolume { get => PlayerPrefs.GetFloat("nindo.master", 0.9f); set => PlayerPrefs.SetFloat("nindo.master", value); }
        public static float MusicVolume { get => PlayerPrefs.GetFloat("nindo.music", 0.6f); set => PlayerPrefs.SetFloat("nindo.music", value); }
        public static float SfxVolume { get => PlayerPrefs.GetFloat("nindo.sfx", 0.9f); set => PlayerPrefs.SetFloat("nindo.sfx", value); }
        public static float ScreenShake { get => PlayerPrefs.GetFloat("nindo.shake", 1f); set => PlayerPrefs.SetFloat("nindo.shake", value); }
        public static bool SlowMotionEnabled { get => PlayerPrefs.GetInt("nindo.slowmo", 1) == 1; set => PlayerPrefs.SetInt("nindo.slowmo", value ? 1 : 0); }
        public static bool Rumble { get => PlayerPrefs.GetInt("nindo.rumble", 1) == 1; set => PlayerPrefs.SetInt("nindo.rumble", value ? 1 : 0); }
        public static int Quality { get => PlayerPrefs.GetInt("nindo.quality", -1); set => PlayerPrefs.SetInt("nindo.quality", value); }
        /// <summary>
        /// Avisos de combate (Opciones): 2 = todos, 1 = solo los del imparable, 0 = ninguno. Para quien ya lee
        /// los golpes y quiere la pantalla limpia. Lo consultan con <see cref="ShowParryAids"/> /
        /// <see cref="ShowUnblockableAids"/> las marcas de la UI ("!", escudo, rombo rojo) y los anillos ensō con sus
        /// zonas del piso (FX/CombatTelegraphs). El filo encendido, las poses y los sonidos del aviso quedan siempre.
        /// </summary>
        public static int CombatAids { get => Mathf.Clamp(PlayerPrefs.GetInt("nindo.aids", 2), 0, 2); set => PlayerPrefs.SetInt("nindo.aids", Mathf.Clamp(value, 0, 2)); }
        public static bool ShowParryAids => CombatAids >= 2;
        public static bool ShowUnblockableAids => CombatAids >= 1;
        public static bool Fullscreen { get => Screen.fullScreen; set => Screen.fullScreen = value; }
        /// <summary>Teclas y botones elegidos en Opciones › Controles: versión del formato y solo lo que no es de
        /// fábrica (BindingTable.Save), así una acción nueva llega con sus teclas y no hay que migrar nada.</summary>
        public static string ControlBindings { get => PlayerPrefs.GetString("nindo.controls", ""); set => PlayerPrefs.SetString("nindo.controls", value); }
        public static void Save() => PlayerPrefs.Save();
    }
}
