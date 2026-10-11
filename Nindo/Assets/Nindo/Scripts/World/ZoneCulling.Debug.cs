using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using Unity.Profiling;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Medición y depuración de ZoneCulling, para el Inspector o RunCommand:
    ///  * ZoneCulling.Stats: una línea con lo prendido ahora (renderers, casters de sombra, celdas, enemigos despiertos,
    ///    Animators y luces de la escena, y lo que cuesta el chequeo por frame).
    ///  * ZoneCulling.ShowHud = true: esa línea arriba a la izquierda y, en la vista Scene, las celdas (verde = prendida).
    ///  * ZoneCulling.Benchmark(segundos): alterna con y sin culling en el mismo lugar y escribe en la consola el promedio
    ///    de cada contador del Profiler (tiempo del hilo principal y de render, batches, SetPass, casters de sombra...).
    ///  * ZoneCulling.CheckFrame(carpeta): el mismo cuadro, congelado, con y sin culling: cuántos píxeles cambian.
    /// </summary>
    public partial class ZoneCulling
    {
        static bool hudWanted;

        public static bool ShowHud
        {
            get => hudWanted;
            set { hudWanted = value; if (Instance != null) Instance.SyncHud(); }
        }

        public static int RenderersOn => Instance != null ? Instance.litRenderers : 0;
        public static int RenderersTotal => Instance != null ? Instance.totalRenderers : 0;
        public static int CastersOn => Instance != null ? Instance.litCasters : 0;
        public static int EnemiesAwake => Instance != null ? Instance.awake : 0;
        public static int EnemiesTotal => Instance != null ? Instance.sleepers.Count : 0;
        /// <summary>Lo que cuesta el chequeo de cada frame (ms, promedio móvil).</summary>
        public static float CostMs => Instance != null ? Instance.costMs : 0f;

        /// <summary>Estado completo (cuenta también Animators y luces de toda la escena: busca, no usar por frame).</summary>
        public static string Stats => Instance != null ? Instance.Describe(true) : "ZoneCulling: todavía no hay mundo armado";

        void Start() => SyncHud();

        void SyncHud()
        {
            var hud = GetComponent<ZoneCullingHud>();
            if (hudWanted && hud == null) gameObject.AddComponent<ZoneCullingHud>();
            else if (!hudWanted && hud != null) Destroy(hud);
        }

        internal string Describe(bool scene)
        {
            var ic = CultureInfo.InvariantCulture;
            var sb = new StringBuilder(256);
            sb.Append(On ? "ZoneCulling ON" : "ZoneCulling OFF (todo prendido)");
            sb.Append(" | renderers ").Append(litRenderers).Append('/').Append(totalRenderers);
            sb.Append(" | casters de sombra ").Append(litCasters).Append('/').Append(totalCasters);
            sb.Append(" | celdas en cuadro ").Append(litCells).Append('/').Append(cells != null ? cells.Length : 0);
            sb.Append(" | enemigos despiertos ").Append(awake).Append('/').Append(sleepers.Count);
            sb.Append(" | cámaras ").Append(camCount);
            sb.Append(" | chequeo ").Append(costMs.ToString("0.000", ic)).Append(" ms");
            if (!scene) return sb.ToString();
            int anims = 0, culledAnims = 0;
            foreach (var a in FindObjectsByType<Animator>(FindObjectsSortMode.None))
            {
                if (!a.isActiveAndEnabled) continue;
                anims++;
                if (a.cullingMode == AnimatorCullingMode.CullCompletely) culledAnims++;
            }
            int lights = 0, lightsInView = 0;
            foreach (var l in FindObjectsByType<Light>(FindObjectsSortMode.None))
            {
                if (!l.isActiveAndEnabled || l.type == LightType.Directional) continue;
                lights++;
                Vector3 c = l.transform.position;
                float r = l.range;
                if (Visible(new Vector3(c.x - r, c.y - r, c.z - r), new Vector3(c.x + r, c.y + r, c.z + r), 0f)) lightsInView++;
            }
            sb.Append(" | animators ").Append(anims).Append(" activos (").Append(culledAnims).Append(" dormidos)");
            sb.Append(" | luces puntuales ").Append(lights).Append(" prendidas, ").Append(lightsInView).Append(" tocan el cuadro");
            return sb.ToString();
        }

        // ================================================================== banco de pruebas
        /// <summary>
        /// Alterna 6 bloques con y sin culling (3 y 3, intercalados para que la deriva del editor se cancele) en el lugar
        /// donde está Kaito, y escribe en la consola el promedio de cada contador en cada modo. Mejor con Kaito quieto
        /// y la cámara de juego (sin cinemáticas). Deja ZoneCulling.On como estaba.
        /// </summary>
        public static void Benchmark(float seconds = 12f)
        {
            if (Instance == null) { Debug.LogWarning("[Nindo] ZoneCulling.Benchmark: todavía no hay mundo armado."); return; }
            Instance.StartCoroutine(Instance.BenchmarkRoutine(Mathf.Max(3f, seconds)));
        }

        static readonly (ProfilerCategory cat, string name, bool time)[] BenchStats =
        {
            (ProfilerCategory.Internal, "Main Thread", true),
            (ProfilerCategory.Internal, "Render Thread", true),
            (ProfilerCategory.Render, "CullScriptable", true),
            (ProfilerCategory.Render, "Batches Count", false),
            (ProfilerCategory.Render, "SetPass Calls Count", false),
            (ProfilerCategory.Render, "Draw Calls Count", false),
            (ProfilerCategory.Render, "Shadow Casters Count", false),
            (ProfilerCategory.Render, "Triangles Count", false),
            (ProfilerCategory.Render, "Visible Skinned Meshes Count", false),
        };

        IEnumerator BenchmarkRoutine(float seconds)
        {
            bool was = On;
            var rec = new ProfilerRecorder[BenchStats.Length];
            var sum = new double[2, BenchStats.Length + 2];
            var frames = new int[2];
            var valid = new bool[BenchStats.Length];
            for (int i = 0; i < rec.Length; i++) rec[i] = ProfilerRecorder.StartNew(BenchStats[i].cat, BenchStats[i].name);
            try
            {
                float block = seconds / 6f;
                for (int b = 0; b < 6; b++)
                {
                    int mode = b % 2;   // 0 = con culling, 1 = sin
                    On = mode == 0;
                    // que se asiente: al volver a prender, lo que no hace falta se apaga y los lejanos se duermen en el
                    // primer frame (mientras estuvo apagado no se anotó cuándo hicieron falta); el resto es ruido del cambio
                    float settle = Time.unscaledTime + 0.5f;
                    while (Time.unscaledTime < settle) yield return null;
                    float until = Time.unscaledTime + block;
                    while (Time.unscaledTime < until)
                    {
                        yield return null;
                        for (int i = 0; i < rec.Length; i++) if (rec[i].Valid) { valid[i] = true; sum[mode, i] += rec[i].LastValue; }
                        sum[mode, rec.Length] += Time.unscaledDeltaTime * 1000.0;
                        sum[mode, rec.Length + 1] += costMs;
                        frames[mode]++;
                    }
                }
            }
            finally
            {
                On = was;
                for (int i = 0; i < rec.Length; i++) rec[i].Dispose();
            }
            var ic = CultureInfo.InvariantCulture;
            var sb = new StringBuilder(512);
            sb.Append("[Nindo] ZoneCulling.Benchmark en (").Append(Game.Player != null ? Game.Player.transform.position.ToString("F0", ic) : "?")
              .Append("), ").Append(frames[0]).Append(" frames con culling y ").Append(frames[1]).Append(" sin:\n");
            void Row(string label, double on, double off, string unit)
            {
                double d = off != 0 ? (on - off) / off * 100.0 : 0.0;
                sb.Append("  ").Append(label).Append(": con ").Append(on.ToString("0.###", ic)).Append(unit)
                  .Append(" | sin ").Append(off.ToString("0.###", ic)).Append(unit)
                  .Append(" | ").Append(d.ToString("+0.0;-0.0", ic)).Append(" %\n");
            }
            for (int i = 0; i < BenchStats.Length; i++)
            {
                // un contador que esta versión de Unity no tiene queda inválido y no se muestra
                if (frames[0] == 0 || frames[1] == 0 || !valid[i]) continue;
                double scale = BenchStats[i].time ? 1e-6 : 1.0;   // ns -> ms
                Row(BenchStats[i].name, sum[0, i] / frames[0] * scale, sum[1, i] / frames[1] * scale, BenchStats[i].time ? " ms" : "");
            }
            if (frames[0] > 0 && frames[1] > 0)
            {
                Row("frame (unscaledDeltaTime)", sum[0, rec.Length] / frames[0], sum[1, rec.Length] / frames[1], " ms");
                sb.Append("  chequeo de ZoneCulling por frame: ").Append((sum[0, rec.Length + 1] / frames[0]).ToString("0.000", ic)).Append(" ms\n");
            }
            sb.Append("  ").Append(Describe(true));
            Debug.Log(sb.ToString());
        }

        // ================================================================== prueba de pop-in
        /// <summary>
        /// La prueba objetiva de que el culling no se ve: dibuja la cámara dos veces en el mismo frame (nada se mueve
        /// entre una y otra: ni el viento, ni el agua, ni las partículas, ni la cámara), primero con el culling del último
        /// LateUpdate y después con todo prendido, y cuenta los píxeles distintos. Tiene que dar 0 (a lo sumo unos pocos
        /// en bordes de sombra con diferencia chica, si Unity ajusta la profundidad del mapa de sombras a los casters que
        /// quedan; un objeto que falta da manchas grandes con diferencia alta). Con 'folder' guarda
        /// con.png, sin.png y dif.png. Sirve en cualquier plano, aunque la cámara esté en movimiento: la de juego, una
        /// presentación de jefe, la grúa de la cascada, un plano al cielo. Renderiza a mano en una textura (con el editor
        /// sin foco la vista Game no siempre se repinta).
        /// </summary>
        public static void CheckFrame(string folder = null)
        {
            if (Instance == null) { Debug.LogWarning("[Nindo] ZoneCulling.CheckFrame: todavía no hay mundo armado."); return; }
            Instance.StartCoroutine(Instance.CheckFrameRoutine(folder));
        }

        IEnumerator CheckFrameRoutine(string folder)
        {
            var cam = Game.Camera != null ? Game.Camera.Cam : null;
            if (cam == null) { Debug.LogWarning("[Nindo] ZoneCulling.CheckFrame: no hay cámara de juego."); yield break; }
            bool was = On;
            On = true;
            // un LateUpdate con culling: la corrutina sigue en el frame siguiente antes de que CameraDirector mueva la
            // cámara, así que la pose es la misma con la que se decidió qué apagar
            yield return null;
            var hidden = new List<Canvas>();
            foreach (var c in FindObjectsByType<Canvas>(FindObjectsSortMode.None))
                if (c.isRootCanvas && c.enabled && c.renderMode != RenderMode.ScreenSpaceOverlay) { c.enabled = false; hidden.Add(c); }
            Texture2D a, b;
            string stats;
            try
            {
                a = RenderCamera(cam);
                stats = Describe(false);
                ShowAll();   // el próximo LateUpdate vuelve a apagar lo que sobra
                b = RenderCamera(cam);
            }
            finally
            {
                On = was;
                foreach (var c in hidden) if (c != null) c.enabled = true;
            }
            var pa = a.GetPixels32();
            var pb = b.GetPixels32();
            int diff = 0, maxD = 0, w = a.width;
            int x0 = int.MaxValue, y0 = int.MaxValue, x1 = -1, y1 = -1;
            var dif = folder != null ? new Color32[pa.Length] : null;
            for (int i = 0; i < pa.Length && i < pb.Length; i++)
            {
                int d = Mathf.Max(Mathf.Abs(pa[i].r - pb[i].r), Mathf.Max(Mathf.Abs(pa[i].g - pb[i].g), Mathf.Abs(pa[i].b - pb[i].b)));
                if (dif != null) dif[i] = d > 3 ? new Color32(255, 40, 40, 255) : new Color32((byte)(pa[i].r / 4), (byte)(pa[i].g / 4), (byte)(pa[i].b / 4), 255);
                if (d <= 3) continue;   // ruido de 8 bits
                diff++;
                maxD = Mathf.Max(maxD, d);
                int x = i % w, y = i / w;
                x0 = Mathf.Min(x0, x); x1 = Mathf.Max(x1, x); y0 = Mathf.Min(y0, y); y1 = Mathf.Max(y1, y);
            }
            if (folder != null)
            {
                System.IO.Directory.CreateDirectory(folder);
                System.IO.File.WriteAllBytes(System.IO.Path.Combine(folder, "con.png"), a.EncodeToPNG());
                System.IO.File.WriteAllBytes(System.IO.Path.Combine(folder, "sin.png"), b.EncodeToPNG());
                var t = new Texture2D(a.width, a.height, TextureFormat.RGBA32, false);
                t.SetPixels32(dif);
                System.IO.File.WriteAllBytes(System.IO.Path.Combine(folder, "dif.png"), t.EncodeToPNG());
                Destroy(t);
            }
            string box = diff > 0 ? $" en x {x0}..{x1}, y {y0}..{y1} (abajo a la izquierda = 0,0), diferencia máx {maxD}" : "";
            Debug.Log($"[Nindo] ZoneCulling.CheckFrame: {diff} de {pa.Length} píxeles distintos{box}. Con culling: {stats}");
            Destroy(a); Destroy(b);
        }

        /// <summary>La cámara con el estado de culling del último LateUpdate, en una textura del tamaño de la pantalla.</summary>
        static Texture2D RenderCamera(Camera cam)
        {
            int w = Mathf.Max(64, cam.pixelWidth), h = Mathf.Max(64, cam.pixelHeight);
            var rt = RenderTexture.GetTemporary(w, h, 24, RenderTextureFormat.ARGB32);
            var prev = cam.targetTexture;
            cam.targetTexture = rt;
            cam.Render();
            cam.targetTexture = prev;
            var active = RenderTexture.active;
            RenderTexture.active = rt;
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            tex.Apply(false);
            RenderTexture.active = active;
            RenderTexture.ReleaseTemporary(rt);
            return tex;
        }

#if UNITY_EDITOR
        /// <summary>Con el HUD prendido, las celdas en la vista Scene: verde las que tienen algo prendido.</summary>
        void OnDrawGizmos()
        {
            if (!hudWanted || cells == null) return;
            for (int c = 0; c < cells.Length; c++)
            {
                Gizmos.color = cells[c].lit > 0 ? new Color(0.3f, 1f, 0.4f, 0.8f) : new Color(0.5f, 0.5f, 0.5f, 0.15f);
                Gizmos.DrawWireCube((cells[c].min + cells[c].max) * 0.5f, cells[c].max - cells[c].min);
            }
        }
#endif
    }

    /// <summary>La línea de ZoneCulling arriba a la izquierda (solo mientras ZoneCulling.ShowHud está prendido).</summary>
    public class ZoneCullingHud : MonoBehaviour
    {
        string text = "";
        float next;
        GUIStyle style;

        void Update()
        {
            if (Time.unscaledTime < next) return;
            next = Time.unscaledTime + 0.5f;
            var zc = ZoneCulling.Instance;
            text = zc != null ? zc.Describe(false) : "";
        }

        void OnGUI()
        {
            style ??= new GUIStyle(GUI.skin.label) { fontSize = 14, normal = { textColor = Color.white } };
            GUI.color = new Color(0f, 0f, 0f, 0.6f);
            GUI.DrawTexture(new Rect(8, 8, 1100, 24), Texture2D.whiteTexture);
            GUI.color = Color.white;
            GUI.Label(new Rect(14, 10, 1090, 22), text, style);
        }
    }
}
