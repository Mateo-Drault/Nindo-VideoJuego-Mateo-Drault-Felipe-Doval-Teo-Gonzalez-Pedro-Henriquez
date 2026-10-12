using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using Unity.Profiling;
using Unity.Profiling.LowLevel.Unsafe;
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

        /// <summary>Partículas del mundo en loop que están simulando ahora (las pausadas por estar escondidas no).</summary>
        public static int ParticlesSimulating => Instance != null ? Instance.CountSimulating() : 0;
        public static int ParticlesTotal => Instance != null ? Instance.totalParticles : 0;

        int CountSimulating()
        {
            int n = 0;
            if (items != null) for (int i = 0; i < items.Length; i++) if (items[i].ps != null && items[i].ps.isPlaying) n++;
            return n;
        }

        /// <summary>'twoLines': el HUD lo parte en dos renglones (lo de dibujo y lo de enemigos y costo).</summary>
        internal string Describe(bool scene, bool twoLines = false)
        {
            var ic = CultureInfo.InvariantCulture;
            var sb = new StringBuilder(256);
            sb.Append(On ? "ZoneCulling ON" : "ZoneCulling OFF (todo prendido)");
            sb.Append(" | renderers ").Append(litRenderers).Append('/').Append(totalRenderers);
            sb.Append(" | casters de sombra ").Append(litCasters).Append('/').Append(totalCasters);
            sb.Append(" | celdas en cuadro ").Append(litCells).Append('/').Append(cells != null ? cells.Length : 0);
            sb.Append(twoLines ? "\n" : " | ").Append("enemigos despiertos ").Append(awake).Append('/').Append(sleepers.Count);
            sb.Append(" | partículas simulando ").Append(CountSimulating()).Append('/').Append(totalParticles);
            sb.Append(" | cámaras ").Append(camCount);
            sb.Append(" | chequeo ").Append(costMs.ToString("0.000", ic)).Append(" ms");
            if (!scene) return sb.ToString();
            // con CullUpdateTransforms, un Animator sin ningún renderer visible solo avanza su máquina de estados
            int anims = 0, culledAnims = 0;
            var rs = new List<Renderer>();
            foreach (var a in FindObjectsByType<Animator>(FindObjectsSortMode.None))
            {
                if (!a.isActiveAndEnabled) continue;
                anims++;
                if (a.cullingMode == AnimatorCullingMode.AlwaysAnimate) continue;
                a.GetComponentsInChildren(rs);
                bool seen = false;
                foreach (var r in rs) seen |= r.isVisible;
                if (!seen) culledAnims++;
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
            sb.Append(" | animators ").Append(anims).Append(" activos (").Append(culledAnims).Append(" sin pose: fuera de cuadro)");
            sb.Append(" | luces puntuales ").Append(lights).Append(" prendidas, ").Append(lightsInView).Append(" tocan el cuadro");
            return sb.ToString();
        }

        // ================================================================== banco de pruebas
        /// <summary>
        /// Alterna 6 bloques con y sin culling (3 y 3, intercalados para que la deriva del editor se cancele) en el lugar
        /// donde está Kaito, y escribe en la consola el promedio de cada contador en cada modo. Mejor con Kaito quieto,
        /// la cámara de juego (sin cinemáticas), la vista Game con foco y la calidad de serie (Alta). Mientras mide
        /// saca el tope de 120 fps y el vsync de GameBootstrap (si no, el frame da 8.3 ms en los dos modos y la ganancia
        /// no se ve) y no cuenta la vista Scene; al terminar deja todo como estaba.
        /// </summary>
        public static void Benchmark(float seconds = 12f)
        {
            if (Instance == null) { Debug.LogWarning("[Nindo] ZoneCulling.Benchmark: todavía no hay mundo armado."); return; }
            Instance.StartCoroutine(Instance.BenchmarkRoutine(Mathf.Max(3f, seconds)));
        }

        /// <summary>
        /// Contadores y marcadores del Profiler que se promedian. Se buscan por nombre entre los que esta versión de Unity
        /// publica (un nombre que no existe no se muestra): tiempos de hilo, culling, lo que se dibuja y lo que ZoneCulling
        /// ahorra fuera de cuadro (el Update de los enemigos dormidos, partículas pausadas, Animators).
        /// </summary>
        static readonly (ProfilerCategory cat, string name)[] BenchStats =
        {
            (ProfilerCategory.Internal, "Main Thread"),
            (ProfilerCategory.Internal, "Render Thread"),
            (ProfilerCategory.Render, "CullScriptable"),
            (ProfilerCategory.Render, "Batches Count"),
            (ProfilerCategory.Render, "SetPass Calls Count"),
            (ProfilerCategory.Render, "Draw Calls Count"),
            (ProfilerCategory.Render, "Shadow Casters Count"),
            (ProfilerCategory.Render, "Triangles Count"),
            (ProfilerCategory.Render, "Visible Skinned Meshes Count"),
            (ProfilerCategory.Scripts, "BehaviourUpdate"),
            (ProfilerCategory.Scripts, "LateBehaviourUpdate"),
            (ProfilerCategory.Animation, "PreLateUpdate.DirectorUpdateAnimationBegin"),
            (ProfilerCategory.Animation, "PreLateUpdate.DirectorUpdateAnimationEnd"),
            (ProfilerCategory.Particles, "PreLateUpdate.ParticleSystemBeginUpdateAll"),
            (ProfilerCategory.Particles, "ParticleSystem.Update"),
        };

        /// <summary>El contador o marcador con ese nombre (y esa categoría si hay varios), o el de StartNew si no aparece.</summary>
        static ProfilerRecorder OpenRecorder(List<ProfilerRecorderHandle> available, ProfilerCategory cat, string name, out bool time)
        {
            ProfilerRecorderHandle found = default;
            bool any = false;
            foreach (var h in available)
            {
                var d = ProfilerRecorderHandle.GetDescription(h);
                if (d.Name != name) continue;
                found = h;
                any = true;
                if (d.Category == cat) break;
            }
            if (!any) { time = false; return ProfilerRecorder.StartNew(cat, name); }
            time = ProfilerRecorderHandle.GetDescription(found).UnitType == ProfilerMarkerDataUnit.TimeNanoseconds;
            var r = new ProfilerRecorder(found, 1, ProfilerRecorderOptions.Default);
            r.Start();
            return r;
        }

        IEnumerator BenchmarkRoutine(float seconds)
        {
            bool was = On, scene = IncludeSceneView;
            int fps = Application.targetFrameRate, vsync = QualitySettings.vSyncCount;
            var available = new List<ProfilerRecorderHandle>(4096);
            ProfilerRecorderHandle.GetAvailable(available);
            int n = BenchStats.Length;
            var rec = new ProfilerRecorder[n];
            var time = new bool[n];
            // por modo: cada contador, el frame, el chequeo y los tiempos de FrameTimingManager (CPU principal, CPU de
            // render, GPU), que no cuentan la espera del vsync ni del tope de fps
            var sum = new double[2, n + 5];
            var timed = new int[2, 3];
            var frames = new int[2];
            var valid = new bool[n];
            var timing = new FrameTiming[1];
            for (int i = 0; i < n; i++) rec[i] = OpenRecorder(available, BenchStats[i].cat, BenchStats[i].name, out time[i]);
            IncludeSceneView = false;
            Application.targetFrameRate = -1;
            QualitySettings.vSyncCount = 0;
            bool focused = true;
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
                    while (Time.unscaledTime < settle) { FrameTimingManager.CaptureFrameTimings(); yield return null; }
                    float until = Time.unscaledTime + block;
                    while (Time.unscaledTime < until)
                    {
                        FrameTimingManager.CaptureFrameTimings();
                        yield return null;
                        focused &= Application.isFocused;
                        for (int i = 0; i < n; i++) if (rec[i].Valid) { valid[i] = true; sum[mode, i] += rec[i].LastValue; }
                        sum[mode, n] += Time.unscaledDeltaTime * 1000.0;
                        sum[mode, n + 1] += costMs;
                        if (FrameTimingManager.GetLatestTimings(1, timing) > 0)
                        {
                            var t = timing[0];
                            if (t.cpuMainThreadFrameTime > 0) { sum[mode, n + 2] += t.cpuMainThreadFrameTime; timed[mode, 0]++; }
                            if (t.cpuRenderThreadFrameTime > 0) { sum[mode, n + 3] += t.cpuRenderThreadFrameTime; timed[mode, 1]++; }
                            if (t.gpuFrameTime > 0) { sum[mode, n + 4] += t.gpuFrameTime; timed[mode, 2]++; }
                        }
                        frames[mode]++;
                    }
                }
            }
            finally
            {
                On = was;
                IncludeSceneView = scene;
                Application.targetFrameRate = fps;
                QualitySettings.vSyncCount = vsync;
                for (int i = 0; i < n; i++) rec[i].Dispose();
            }
            var ic = CultureInfo.InvariantCulture;
            var sb = new StringBuilder(1024);
            sb.Append("[Nindo] ZoneCulling.Benchmark en (").Append(Game.Player != null ? Game.Player.transform.position.ToString("F0", ic) : "?")
              .Append("), calidad ").Append(QualitySettings.names[QualitySettings.GetQualityLevel()])
              .Append(", ").Append(frames[0]).Append(" frames con culling y ").Append(frames[1]).Append(" sin (sin tope de fps ni vsync):\n");
            if (!focused) sb.Append("  OJO: la ventana perdió el foco durante la medición (el editor sin foco frena el juego): repetir con la vista Game activa.\n");
            void Row(string label, double on, double off, string unit)
            {
                double d = off != 0 ? (on - off) / off * 100.0 : 0.0;
                sb.Append("  ").Append(label).Append(": con ").Append(on.ToString("0.###", ic)).Append(unit)
                  .Append(" | sin ").Append(off.ToString("0.###", ic)).Append(unit)
                  .Append(" | ").Append(d.ToString("+0.0;-0.0", ic)).Append(" %\n");
            }
            for (int i = 0; i < n; i++)
            {
                // un contador que esta versión de Unity no tiene queda inválido y no se muestra
                if (frames[0] == 0 || frames[1] == 0 || !valid[i]) continue;
                double scale = time[i] ? 1e-6 : 1.0;   // ns -> ms
                Row(BenchStats[i].name, sum[0, i] / frames[0] * scale, sum[1, i] / frames[1] * scale, time[i] ? " ms" : "");
            }
            if (frames[0] > 0 && frames[1] > 0)
            {
                string[] ft = { "FrameTiming CPU hilo principal", "FrameTiming CPU hilo de render", "FrameTiming GPU" };
                for (int j = 0; j < 3; j++)
                    if (timed[0, j] > 0 && timed[1, j] > 0) Row(ft[j], sum[0, n + 2 + j] / timed[0, j], sum[1, n + 2 + j] / timed[1, j], " ms");
                Row("frame (unscaledDeltaTime)", sum[0, n] / frames[0], sum[1, n] / frames[1], " ms");
                sb.Append("  chequeo de ZoneCulling por frame: ").Append((sum[0, n + 1] / frames[0]).ToString("0.000", ic)).Append(" ms\n");
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
            bool was = On, scene = IncludeSceneView;
            On = true;
            IncludeSceneView = false;   // con lo que mira la vista Scene prendido, "con" tendría de más y la prueba sería floja
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
                IncludeSceneView = scene;
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
        float next;
        GUIStyle style;

        void Update()
        {
            if (Time.unscaledTime < next) return;
            next = Time.unscaledTime + 0.5f;
            var zc = ZoneCulling.Instance;
            content.text = zc != null ? zc.Describe(false, true) : "";
            dirty = true;
        }

        readonly GUIContent content = new GUIContent();
        Vector2 size;
        bool dirty;

        /// <summary>
        /// Abajo a la izquierda, encima del indicador de guardado (arriba está la vida del HUD), en dos renglones y
        /// escalado como si la pantalla tuviera 1080 px de alto: se lee igual en una vista Game chica del editor que en 4K.
        /// </summary>
        void OnGUI()
        {
            style ??= new GUIStyle(GUI.skin.label) { fontSize = 20, wordWrap = false, normal = { textColor = Color.white } };
            if (dirty) { size = style.CalcSize(content); dirty = false; }
            float k = Mathf.Max(0.25f, Screen.height / 1080f);
            var prev = GUI.matrix;
            GUI.matrix = Matrix4x4.Scale(new Vector3(k, k, 1f));
            float y = Screen.height / k - size.y - 170f;
            GUI.color = new Color(0f, 0f, 0f, 0.6f);
            GUI.DrawTexture(new Rect(12f, y - 6f, size.x + 20f, size.y + 12f), Texture2D.whiteTexture);
            GUI.color = Color.white;
            GUI.Label(new Rect(22f, y, size.x + 4f, size.y), content, style);
            GUI.matrix = prev;
        }
    }
}
