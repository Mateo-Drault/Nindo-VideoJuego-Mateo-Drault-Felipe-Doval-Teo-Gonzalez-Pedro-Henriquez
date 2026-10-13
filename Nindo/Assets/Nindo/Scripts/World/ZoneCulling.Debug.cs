using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Text;
using Unity.Collections;
using Unity.Profiling;
using Unity.Profiling.LowLevel.Unsafe;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Medición y depuración de ZoneCulling, para el Inspector o RunCommand:
    ///  * ZoneCulling.Stats: una línea con lo prendido ahora (renderers, y cuántos pide solo la cámara de juego si hay
    ///    otra cámara contando; los dinámicos de AddDynamic, casters de sombra, celdas, enemigos despiertos, partículas
    ///    simulando, la cascada, Animators y luces de la escena, y lo que cuesta el chequeo por frame).
    ///  * ZoneCulling.ShowHud = true: esa línea abajo a la izquierda y, en la vista Scene, las celdas (verde = prendida).
    ///  * ZoneCulling.Benchmark(segundos): alterna con y sin culling en el mismo lugar y escribe en la consola el promedio
    ///    de cada contador del Profiler (tiempo del hilo principal y de render, batches, SetPass, casters de sombra...).
    ///    En un Development Build: Ctrl + Shift + F9, o arrancar el juego con -zcbench (el informe va a Player.log).
    ///  * ZoneCulling.CheckFrame(carpeta): el mismo cuadro dibujado dos veces, con y sin culling: cuántos píxeles cambian.
    ///    ZoneCulling.CheckEvery(intervalo, carpeta) lo repite mientras se juega (presentaciones de jefe, planos al
    ///    cielo, la grúa de la cascada) y ZoneCulling.StopCheck() da el resumen.
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

        void Start()
        {
            SyncHud();
            // Development Build sin editor: "-zcbench [segundos]" mide solo apenas se puede jugar
            if (Application.isEditor || !Debug.isDebugBuild) return;
            var args = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length; i++)
            {
                if (args[i] != "-zcbench") continue;
                float s = 30f;
                if (i + 1 < args.Length && float.TryParse(args[i + 1], NumberStyles.Float, CultureInfo.InvariantCulture, out float v)) s = v;
                StartCoroutine(AutoBench(s));
                break;
            }
        }

        /// <summary>Espera a que se pueda jugar (Kaito armado, sin cinemática ni pausa) y 5 s más para que se asiente.</summary>
        IEnumerator AutoBench(float seconds)
        {
            while (Game.Player == null || Game.InCutscene || Game.IsPaused) yield return null;
            float t = Time.unscaledTime + 5f;
            while (Time.unscaledTime < t) yield return null;
            Benchmark(seconds);
        }

        /// <summary>
        /// Ctrl + Shift + F9 en el editor o en un Development Build: Benchmark de 30 s donde está Kaito. F9 sola se puede
        /// asignar a una acción en Opciones › Controles (BindingCatalog.IsBindableKey) y el usuario juega en el editor: cada
        /// golpe arrancaba un benchmark (sin vsync, con el culling prendiéndose y apagándose).
        /// </summary>
        void PollDebugKeys()
        {
#if DEVELOPMENT_BUILD || UNITY_EDITOR
#if ENABLE_INPUT_SYSTEM
            var kb = UnityEngine.InputSystem.Keyboard.current;
            bool f9 = kb != null && kb.f9Key.wasPressedThisFrame && kb.ctrlKey.isPressed && kb.shiftKey.isPressed;
#elif ENABLE_LEGACY_INPUT_MANAGER
            bool f9 = Input.GetKeyDown(KeyCode.F9) && (Input.GetKey(KeyCode.LeftControl) || Input.GetKey(KeyCode.RightControl))
                      && (Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift));
#else
            bool f9 = false;
#endif
            if (f9) Benchmark(30f);
#endif
        }

        void SyncHud()
        {
            var hud = GetComponent<ZoneCullingHud>();
            if (hudWanted && hud == null) gameObject.AddComponent<ZoneCullingHud>();
            else if (!hudWanted && hud != null) Destroy(hud);
        }

        /// <summary>Partículas en loop (del mundo y las de AddDynamic) que están simulando ahora (las pausadas por estar
        /// escondidas no).</summary>
        public static int ParticlesSimulating => Instance != null ? Instance.CountSimulating() : 0;
        public static int ParticlesTotal => Instance != null ? Instance.totalParticles + Instance.dynLoops : 0;

        int CountSimulating()
        {
            int n = CountDynamicSimulating();
            if (items != null) for (int i = 0; i < items.Length; i++) if (items[i].ps != null && items[i].ps.isPlaying) n++;
            return n;
        }

        /// <summary>
        /// Los renderers que pide solo la cámara de juego en el último frame (sin el Linger ni las otras cámaras): con
        /// una vista Scene a la vista, Stats compara contra esto y no contra lo que pide la vista Scene.
        /// </summary>
        int CountMainCamera()
        {
            if (mainCam < 0 || cells == null) return -1;
            int o = mainCam * 6, n = 0;
            for (int c = 0; c < cells.Length; c++)
            {
                ref var cell = ref cells[c];
                bool pass = InFrustum(o, cell.min, cell.max, cell.shadows ? Sweep(cell.max.y, cell.floor) : 0f);
                int end = cell.start + cell.count;
                for (int i = cell.start; i < end; i++)
                {
                    ref var it = ref items[i];
                    if (it.always || (it.batched && !HideBatched) || (pass && InFrustum(o, it.min, it.max, it.shadows ? Sweep(it.max.y, cell.floor) : 0f))) n++;
                }
            }
            return n;
        }

        /// <summary>'twoLines': el HUD lo parte en dos renglones (lo de dibujo y lo de enemigos y costo).</summary>
        internal string Describe(bool scene, bool twoLines = false)
        {
            var ic = CultureInfo.InvariantCulture;
            var sb = new StringBuilder(320);
            sb.Append(On ? "ZoneCulling ON" : "ZoneCulling OFF (todo prendido)");
            sb.Append(" | renderers ").Append(litRenderers).Append('/').Append(totalRenderers);
            if (On && camCount > 1 && mainCam >= 0) sb.Append(" (cámara de juego sola ").Append(CountMainCamera()).Append(')');
            if (!HideBatched) sb.Append(" (lote estático siempre prendido)");
            sb.Append(" | dinámicos ").Append(dynLit).Append('/').Append(dynCount);
            sb.Append(" | casters de sombra ").Append(litCasters).Append('/').Append(totalCasters);
            sb.Append(" | celdas en cuadro ").Append(litCells).Append('/').Append(cells != null ? cells.Length : 0);
            sb.Append(twoLines ? "\n" : " | ").Append("enemigos despiertos ").Append(awake).Append('/').Append(sleepers.Count);
            sb.Append(" | partículas simulando ").Append(CountSimulating()).Append('/').Append(totalParticles + dynLoops);
            foreach (var fc in falls)
                if (fc.f != null) sb.Append(" | cascada ").Append(!fc.f.Active ? "lejos (LOD)" : fc.f.Frozen ? "congelada (fuera de cuadro)" : "en movimiento");
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
            sb.Append(" | animators ").Append(anims).Append(" prendidos (").Append(culledAnims).Append(" sin pose: fuera de cuadro)");
            sb.Append(" | luces puntuales ").Append(lights).Append(" prendidas, ").Append(lightsInView).Append(" tocan el cuadro");
            return sb.ToString();
        }

        /// <summary>Una medición cortada a la mitad (se salió de Play, se rearmó el mundo, se apagó el componente: la
        /// corrutina muere sin su finally) devuelve todo lo que había cambiado.</summary>
        void RestoreDebug()
        {
            RestoreBench();
            EndCheck();
        }

        // ================================================================== banco de pruebas
        /// <summary>
        /// Alterna 6 bloques con y sin culling (3 y 3, intercalados para que la deriva se cancele) en el lugar donde
        /// está Kaito, y escribe en la consola (o en Player.log) el promedio de cada contador en cada modo. Mejor en un
        /// Development Build (el editor mete ruido del mismo orden que la ganancia), con Kaito quieto, la cámara de
        /// juego (sin cinemáticas) y la calidad de serie (Alta); de 30 s para arriba (bloques de 5 s). Mientras mide
        /// saca el tope de 120 fps y el vsync de GameBootstrap (si no, el frame da 8.3 ms en los dos modos y la ganancia
        /// no se ve) y no cuenta la vista Scene; al terminar, o si se corta, deja todo como estaba.
        /// </summary>
        public static void Benchmark(float seconds = 30f)
        {
            if (Instance == null) { Debug.LogWarning("[Nindo] ZoneCulling.Benchmark: todavía no hay mundo armado."); return; }
            if (Instance.benchActive || Instance.checkActive) { Debug.LogWarning("[Nindo] ZoneCulling.Benchmark: ya hay una medición o una prueba de cuadros en curso."); return; }
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

        // lo que Benchmark cambió y tiene que devolver aunque se corte
        bool benchActive, benchWasOn, benchScene;
        int benchFps, benchVsync;
        ProfilerRecorder[] benchRec;

        void RestoreBench()
        {
            if (!benchActive) return;
            benchActive = false;
            On = benchWasOn;
            IncludeSceneView = benchScene;
            Application.targetFrameRate = benchFps;
            QualitySettings.vSyncCount = benchVsync;
            if (benchRec != null) for (int i = 0; i < benchRec.Length; i++) benchRec[i].Dispose();
            benchRec = null;
        }

        IEnumerator BenchmarkRoutine(float seconds)
        {
            benchActive = true;
            benchWasOn = On; benchScene = IncludeSceneView;
            benchFps = Application.targetFrameRate; benchVsync = QualitySettings.vSyncCount;
            var available = new List<ProfilerRecorderHandle>(4096);
            ProfilerRecorderHandle.GetAvailable(available);
            int n = BenchStats.Length;
            var rec = benchRec = new ProfilerRecorder[n];
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
            Debug.Log($"[Nindo] ZoneCulling.Benchmark: midiendo {seconds.ToString("0", CultureInfo.InvariantCulture)} s, no mover a Kaito ni la cámara.");
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
                RestoreBench();
            }
            var ic = CultureInfo.InvariantCulture;
            var sb = new StringBuilder(1024);
            sb.Append("[Nindo] ZoneCulling.Benchmark en (").Append(Game.Player != null ? Game.Player.transform.position.ToString("F0", ic) : "?")
              .Append("), calidad ").Append(QualitySettings.names[QualitySettings.GetQualityLevel()])
              .Append(", ").Append(Screen.width).Append('x').Append(Screen.height)
              .Append(Application.isEditor ? ", EDITOR" : ", build").Append(HideBatched ? "" : ", HideBatched = false")
              .Append(", ").Append(frames[0]).Append(" frames con culling y ").Append(frames[1]).Append(" sin (sin tope de fps ni vsync):\n");
            if (!focused) sb.Append("  OJO: la ventana perdió el foco durante la medición (sin foco se frena el juego): repetir con la ventana activa.\n");
            void Row(string label, double on, double off, string unit)
            {
                double d = off != 0 ? (on - off) / off * 100.0 : 0.0;
                sb.Append("  ").Append(label).Append(": con ").Append(on.ToString("0.###", ic)).Append(unit)
                  .Append(" | sin ").Append(off.ToString("0.###", ic)).Append(unit)
                  .Append(" | ").Append(d.ToString("+0.0;-0.0", ic)).Append(" %\n");
            }
            bool moreDraws = false;
            for (int i = 0; i < n; i++)
            {
                // un contador que esta versión de Unity no tiene queda inválido y no se muestra
                if (frames[0] == 0 || frames[1] == 0 || !valid[i]) continue;
                double scale = time[i] ? 1e-6 : 1.0;   // ns -> ms
                double con = sum[0, i] / frames[0] * scale, sin = sum[1, i] / frames[1] * scale;
                Row(BenchStats[i].name, con, sin, time[i] ? " ms" : "");
                if ((BenchStats[i].name == "Batches Count" || BenchStats[i].name == "Draw Calls Count") && con > sin * 1.005 + 0.5) moreDraws = true;
            }
            if (frames[0] > 0 && frames[1] > 0)
            {
                string[] ft = { "FrameTiming CPU hilo principal", "FrameTiming CPU hilo de render", "FrameTiming GPU" };
                for (int j = 0; j < 3; j++)
                    if (timed[0, j] > 0 && timed[1, j] > 0) Row(ft[j], sum[0, n + 2 + j] / timed[0, j], sum[1, n + 2 + j] / timed[1, j], " ms");
                Row("frame (unscaledDeltaTime)", sum[0, n] / frames[0], sum[1, n] / frames[1], " ms");
                sb.Append("  chequeo de ZoneCulling por frame: ").Append((sum[0, n + 1] / frames[0]).ToString("0.000", ic)).Append(" ms\n");
            }
            // esconder casters en medio de una corrida del lote estático puede partirla en más draws de sombra
            if (moreDraws && HideBatched)
                sb.Append("  OJO: con culling hay MÁS Batches/Draw Calls: repetir con Nindo.ZoneCulling.HideBatched = false; si así baja el frame, dejarlo en false.\n");
            sb.Append("  ").Append(Describe(true));
            Debug.Log(sb.ToString());
        }

        // ================================================================== prueba de pop-in
        /// <summary>
        /// La prueba objetiva de que el culling no se ve: en el LateUpdate de ZoneCulling, recién decidido qué apagar y
        /// con la cámara ya movida por CameraDirector (la misma pose con la que se decidió), dibuja la cámara de juego dos
        /// veces en el mismo frame (nada se mueve entre una y otra: ni el viento, ni el agua, ni las partículas): primero
        /// con el culling y después con todo prendido (también lo de los enemigos dormidos, sin despertarlos), y cuenta los
        /// píxeles distintos. Tiene que dar 0 (a lo sumo unos pocos en bordes de sombra con diferencia chica, si Unity
        /// ajusta la profundidad del mapa de sombras a los casters que quedan; un objeto que falta da manchas grandes con
        /// diferencia alta). Saca la vista Scene y espera un LateUpdate con eso y Linger, así "con" es lo que pide la
        /// cámara de juego sola. Con 'folder' guarda con.png, sin.png y dif.png. La cascada congelada no se ve en esta
        /// prueba (sus partículas se dibujan igual, quietas): para eso, Stats dice "cascada congelada" o "en movimiento".
        /// </summary>
        public static void CheckFrame(string folder = null) => StartCheck(folder, 0f);

        /// <summary>
        /// CheckFrame cada 'interval' s mientras se juega: avisa solo de los cuadros con diferencias (y guarda hasta 10 en
        /// 'folder', con el número de cuadro) y StopCheck() da el resumen. Para pasar por las presentaciones de jefe, los
        /// planos al cielo, la grúa de la cascada y el santuario lateral sin tener que acertar el momento. Cada prueba
        /// dibuja la escena dos veces más: el juego va a tirones mientras corre.
        /// </summary>
        public static void CheckEvery(float interval = 0.25f, string folder = null) => StartCheck(folder, Mathf.Max(0.05f, interval));

        public static void StopCheck() { if (Instance != null) Instance.EndCheck(); }

        static void StartCheck(string folder, float every)
        {
            if (Instance == null) { Debug.LogWarning("[Nindo] ZoneCulling.CheckFrame: todavía no hay mundo armado."); return; }
            if (Instance.benchActive) { Debug.LogWarning("[Nindo] ZoneCulling.CheckFrame: hay un Benchmark en curso."); return; }
            Instance.BeginCheck(folder, every);
        }

        // la prueba en curso, lo que hay que devolver al terminar y lo que lleva contado CheckEvery
        bool checkActive, checkWasOn, checkScene;
        string checkFolder;
        float checkEvery, checkNext;
        int checkFrom, checkCount, checkBad, checkAllOn, checkMaxPixels, checkSaved;
        Texture2D checkA, checkB;
        readonly List<Canvas> checkCanvases = new List<Canvas>();

        void BeginCheck(string folder, float every)
        {
            if (!checkActive)
            {
                checkActive = true;
                checkWasOn = On; checkScene = IncludeSceneView;
                checkCount = checkBad = checkAllOn = checkMaxPixels = checkSaved = 0;
            }
            On = true;
            IncludeSceneView = false;
            checkFolder = folder;
            checkEvery = every;
            // antes, un LateUpdate con estos flags y que se apague por Linger lo que solo pedía la vista Scene (o lo que
            // quedó prendido si recién se volvió de On = false): si no, "con" sale con todo prendido y no prueba nada
            checkFrom = Time.frameCount;
            checkNext = Time.unscaledTime + Linger + 0.1f;
        }

        /// <summary>Al final del LateUpdate, recién decidido todo con la pose de cámara de este frame.</summary>
        void TickCheck(float now)
        {
            if (!checkActive || lastCullFrame <= checkFrom || now < checkNext) return;
            var cam = Game.Camera != null ? Game.Camera.Cam : null;
            if (mainCam < 0 || cam == null) return;
            RunCheck(cam);
            if (checkEvery <= 0f) EndCheck();
            else checkNext = now + checkEvery;
        }

        void EndCheck()
        {
            if (!checkActive) return;
            checkActive = false;
            if (checkEvery > 0f)
                Debug.Log($"[Nindo] ZoneCulling.CheckEvery: {checkCount} cuadros revisados, {checkBad} con píxeles distintos (máx {checkMaxPixels})"
                          + (checkAllOn > 0 ? $", {checkAllOn} con todo prendido (esos no prueban nada)" : "") + (checkBad > 0 && checkFolder != null ? $"; imágenes en {checkFolder}" : "") + ".");
            On = checkWasOn;
            IncludeSceneView = checkScene;
            if (checkA != null) Destroy(checkA);
            if (checkB != null) Destroy(checkB);
            checkA = checkB = null;
        }

        void RunCheck(Camera cam)
        {
            checkCanvases.Clear();
            foreach (var c in FindObjectsByType<Canvas>(FindObjectsSortMode.None))
                if (c.isRootCanvas && c.enabled && c.renderMode != RenderMode.ScreenSpaceOverlay) { c.enabled = false; checkCanvases.Add(c); }
            string stats;
            bool allOn = litRenderers == totalRenderers;
            try
            {
                RenderInto(cam, ref checkA);
                stats = Describe(false);
                // "sin": todo prendido sin despertar a nadie; el próximo LateUpdate vuelve a apagar lo que sobra
                ShowItems();
                foreach (var s in sleepers)
                    if (s.e != null && s.e.Asleep) foreach (var r in s.e.SleepHidden) if (r != null) r.forceRenderingOff = false;
                RenderInto(cam, ref checkB);
            }
            finally
            {
                foreach (var s in sleepers)
                    if (s.e != null && s.e.Asleep) foreach (var r in s.e.SleepHidden) if (r != null) r.forceRenderingOff = true;
                foreach (var c in checkCanvases) if (c != null) c.enabled = true;
            }
            var pa = checkA.GetPixelData<Color32>(0);
            var pb = checkB.GetPixelData<Color32>(0);
            int diff = 0, maxD = 0, w = checkA.width;
            int x0 = int.MaxValue, y0 = int.MaxValue, x1 = -1, y1 = -1;
            for (int i = 0; i < pa.Length && i < pb.Length; i++)
            {
                Color32 a = pa[i], b = pb[i];
                int d = Mathf.Max(Mathf.Abs(a.r - b.r), Mathf.Max(Mathf.Abs(a.g - b.g), Mathf.Abs(a.b - b.b)));
                if (d <= 3) continue;   // ruido de 8 bits
                diff++;
                maxD = Mathf.Max(maxD, d);
                int x = i % w, y = i / w;
                x0 = Mathf.Min(x0, x); x1 = Mathf.Max(x1, x); y0 = Mathf.Min(y0, y); y1 = Mathf.Max(y1, y);
            }
            checkCount++;
            if (allOn) checkAllOn++;
            if (diff > 0) { checkBad++; checkMaxPixels = Mathf.Max(checkMaxPixels, diff); }
            bool every = checkEvery > 0f;
            string tag = every ? "_" + Time.frameCount.ToString(CultureInfo.InvariantCulture) : "";
            if (checkFolder != null && (!every || (diff > 0 && checkSaved < 10)))
            {
                if (every) checkSaved++;
                SaveCheck(pa, pb, tag);
            }
            if (every && diff == 0) return;
            string box = diff > 0 ? $" en x {x0}..{x1}, y {y0}..{y1} (abajo a la izquierda = 0,0), diferencia máx {maxD}" : "";
            string warn = allOn ? " OJO: con culling estaba TODO prendido, así que este cuadro no prueba nada (¿una cámara más, una vista Scene, On recién vuelto a true?)." : "";
            string msg = $"[Nindo] ZoneCulling.CheckFrame{tag}: {diff} de {pa.Length} píxeles distintos{box}. Con culling: {stats}.{warn}";
            if (diff > 0 || allOn) Debug.LogWarning(msg); else Debug.Log(msg);
        }

        void SaveCheck(NativeArray<Color32> pa, NativeArray<Color32> pb, string tag)
        {
            System.IO.Directory.CreateDirectory(checkFolder);
            System.IO.File.WriteAllBytes(System.IO.Path.Combine(checkFolder, "con" + tag + ".png"), checkA.EncodeToPNG());
            System.IO.File.WriteAllBytes(System.IO.Path.Combine(checkFolder, "sin" + tag + ".png"), checkB.EncodeToPNG());
            var dif = new Color32[pa.Length];
            for (int i = 0; i < pa.Length && i < pb.Length; i++)
            {
                Color32 a = pa[i], b = pb[i];
                int d = Mathf.Max(Mathf.Abs(a.r - b.r), Mathf.Max(Mathf.Abs(a.g - b.g), Mathf.Abs(a.b - b.b)));
                dif[i] = d > 3 ? new Color32(255, 40, 40, 255) : new Color32((byte)(a.r / 4), (byte)(a.g / 4), (byte)(a.b / 4), 255);
            }
            var t = new Texture2D(checkA.width, checkA.height, TextureFormat.RGBA32, false);
            t.SetPixels32(dif);
            System.IO.File.WriteAllBytes(System.IO.Path.Combine(checkFolder, "dif" + tag + ".png"), t.EncodeToPNG());
            Destroy(t);
        }

        /// <summary>Los renderers del mundo y los dinámicos prendidos (sin tocar enemigos ni la cascada), para el "sin" de
        /// CheckFrame.</summary>
        void ShowItems()
        {
            for (int c = 0; c < cells.Length; c++)
            {
                ref var cell = ref cells[c];
                int end = cell.start + cell.count;
                for (int i = cell.start; i < end; i++)
                    if (!items[i].on) Set(ref items[i], ref cell, true);
            }
            ShowDynamic();
        }

        /// <summary>La cámara con el estado de culling de ahora, en una textura del tamaño de la pantalla (se reusa).</summary>
        static void RenderInto(Camera cam, ref Texture2D tex)
        {
            int w = Mathf.Max(64, cam.pixelWidth), h = Mathf.Max(64, cam.pixelHeight);
            if (tex == null || tex.width != w || tex.height != h)
            {
                if (tex != null) Destroy(tex);
                tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
            }
            var rt = RenderTexture.GetTemporary(w, h, 24, RenderTextureFormat.ARGB32);
            var prev = cam.targetTexture;
            cam.targetTexture = rt;
            cam.Render();
            cam.targetTexture = prev;
            var active = RenderTexture.active;
            RenderTexture.active = rt;
            tex.ReadPixels(new Rect(0, 0, w, h), 0, 0);
            RenderTexture.active = active;
            RenderTexture.ReleaseTemporary(rt);
        }

#if UNITY_EDITOR
        /// <summary>Con el HUD prendido, las celdas en la vista Scene (verde las que tienen algo prendido) y las cajas de lo
        /// dinámico con las que se decidió el último frame (celeste prendido, gris escondido).</summary>
        void OnDrawGizmos()
        {
            if (!hudWanted || cells == null) return;
            for (int c = 0; c < cells.Length; c++)
            {
                Gizmos.color = cells[c].lit > 0 ? new Color(0.3f, 1f, 0.4f, 0.8f) : new Color(0.5f, 0.5f, 0.5f, 0.15f);
                Gizmos.DrawWireCube((cells[c].min + cells[c].max) * 0.5f, cells[c].max - cells[c].min);
            }
            for (int i = 0; i < dynCount; i++)
            {
                ref var d = ref dyn[i];
                if (d.r == null || d.max.x < d.min.x) continue;
                Gizmos.color = d.on ? new Color(0.35f, 0.85f, 1f, 0.9f) : new Color(0.5f, 0.5f, 0.5f, 0.25f);
                Gizmos.DrawWireCube((d.min + d.max) * 0.5f, d.max - d.min);
            }
        }
#endif
    }

    /// <summary>La línea de ZoneCulling abajo a la izquierda (solo mientras ZoneCulling.ShowHud está prendido).</summary>
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
