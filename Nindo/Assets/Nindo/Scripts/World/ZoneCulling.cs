using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Nindo
{
    /// <summary>
    /// Activación por zonas del mundo (pedido 17). Antes había FBX por zona, static batching, el frustum culling de Unity,
    /// la decoración fusionada por chunk de 60 m, LightPool (10 luces a menos de 45 m), far clip 400 y la cascada que se
    /// apaga a 110 m: nada se apagaba por zona. Unity no dibuja lo que queda fuera de cuadro y en el mapa de sombras ya
    /// descarta lo que no puede sombrear el cuadro (el frustum extruido hacia la luna hasta la distancia de sombras), pero
    /// probaba los ~2000 renderers del mapa en cada cull (la cámara y cada cascada), su extrusión no tiene fin (un prop
    /// cuya sombra muere en la ladera de al lado se seguía dibujando en las dos cascadas: ~20 % de los casters, simulado
    /// sobre el mapa con URP Alta) y cada enemigo del mapa seguía con su IA y su Animator aunque estuviera a 300 m.
    ///
    /// Corre en cada frame DESPUÉS de que la cámara se movió (orden 10050; CameraDirector es 500) y prueba contra el
    /// frustum de esa misma cámara, sea la de juego, un plano de presentación, la grúa de la cascada o un plano al cielo
    /// (y contra el de cualquier otra cámara prendida que dibuje el mundo):
    ///  * Renderers del mundo (props del lote estático, terreno, decoración, santuarios, portales, puertas, cuerdas, botes,
    ///    luciérnagas y humo) en celdas de 32 m. La caja de cada celda (y después la de cada renderer de una celda que
    ///    pasó) se barre a lo largo de la luz de la luna hasta el piso más bajo de su vecindario: lo que está fuera de
    ///    cuadro pero tira sombra adentro sigue prendido. Lo que no hace falta queda con forceRenderingOff: no toca
    ///    'enabled' ni el GameObject (no pisa a quien los prende o apaga), no rompe el static batching ni los colliders.
    ///    Prender es en el mismo frame en que algo entra a cuadro, así que no hay pop-in posible ni con un corte de
    ///    cámara, una cinemática o un teletransporte; apagar espera 0.35 s (sin parpadeo en el borde del cuadro).
    ///  * Enemigos y jefes del mundo: a más de 55 m de Kaito, fuera de cuadro (con su sombra) y quietos en su puesto
    ///    (Enemy.CanSleep) se duermen (Enemy.SetAsleep): sin dibujarse, Animator cortado del todo y, los comunes, sin
    ///    Update. Se despiertan a menos de 45 m, al entrar a cuadro o apenas dejan de cumplir CanSleep (un Alert del
    ///    encuentro o del guion). Mientras pelea un jefe no se duerme a nadie nuevo.
    ///  * Las luces no se tocan: URP descarta solo las que no tocan el frustum y LightPool reparte las de los faroles
    ///    (simulado sobre el mapa: con su densidad nunca deja apagada una luz que se ve). Las partículas en loop que dejan
    ///    de dibujarse se pausan solas (cullingMode Automatic de Unity).
    /// Medición y depuración en ZoneCulling.Debug.cs (Stats, ShowHud, Benchmark, CheckFrame).
    /// </summary>
    [DefaultExecutionOrder(10050)]
    public partial class ZoneCulling : MonoBehaviour
    {
        public static ZoneCulling Instance { get; private set; }
        /// <summary>Con false todo queda prendido y despierto como antes (comparar, depurar, mirar la escena del editor).</summary>
        public static bool On = true;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { Instance = null; On = true; hudWanted = false; }

        /// <summary>Lado de las celdas (m). Simulado sobre el mapa: ~220 celdas y ~390 pruebas por frame; con 24 y 16 m el
        /// resultado por renderer es el mismo pero hay más celdas que probar (420 y 560).</summary>
        const float CellSize = 32f;
        /// <summary>Lo que se agranda cada caja (m): el viento del follaje mueve vértices fuera del bounds del mesh.</summary>
        const float Margin = 1.5f;
        /// <summary>Segundos sin hacer falta antes de apagarse (prender es inmediato).</summary>
        const float Linger = 0.35f;
        /// <summary>Grilla de alturas del terreno (m) y vecindario de cada celda donde se busca el piso más bajo al que
        /// llega su sombra (m). Si con la luz de ese momento la sombra llega más lejos, se usa el piso de todo el mapa.</summary>
        const float FloorStep = 4f, FloorReach = 40f, FloorSafety = 1f;
        /// <summary>Tope del barrido de sombra (en metros a lo largo de la luz) con la luna casi al ras.</summary>
        const float MaxSweep = 400f;
        /// <summary>Enemigos: despiertan a menos de WakeRadius, se duermen recién pasado SleepRadius y después de
        /// SleepDelay s sin hacer falta (el radio de detección más grande de un común es 11 m y un encuentro se activa a
        /// 16 m como mucho con sus miembros a menos de 9 m del centro: a 45 m ningún común puede enterarse de Kaito; los
        /// jefes, que lo ven a 30 m, siguen con su Update dormidos).</summary>
        const float WakeRadius = 45f, SleepRadius = 55f, SleepDelay = 2f;

        struct Item
        {
            public Renderer r;
            public Vector3 min, max;
            public bool shadows, on;
            public float seen;
        }

        struct Cell
        {
            public Vector3 min, max;
            public float floor;
            public int start, count, lit;
            public bool shadows;
        }

        class Sleeper
        {
            public Enemy e;
            public readonly List<Renderer> rs = new List<Renderer>();
            public float pad, height, seen;
            /// <summary>Piso más bajo alrededor (hasta donde baja su sombra), medido en 'floorAt': al borde de un barranco
            /// la sombra cae más de un par de metros. Se vuelve a medir cuando se movió más de 2 m.</summary>
            public float floor;
            public Vector3 floorAt = Vector3.positiveInfinity;
        }

        struct FPlane { public float x, y, z, d, l; }

        /// <summary>
        /// Cámaras que se prueban juntas: la de juego y cualquier otra prendida que dibuje el mundo (un mapa en vivo, un
        /// retrato, la de otro frente): lo que necesite cualquiera de ellas queda prendido. Con más que esto, todo prendido.
        /// Una cámara apagada que se dibuja a mano (Camera.Render) no se ve desde acá: alrededor de ese Render, On = false.
        /// </summary>
        const int MaxCameras = 4;

        Item[] items;
        Cell[] cells;
        readonly List<Sleeper> sleepers = new List<Sleeper>();
        readonly Plane[] planes = new Plane[6];
        readonly FPlane[] fp = new FPlane[6 * MaxCameras];
        Camera[] camBuf = new Camera[8];
        int camCount, worldMask;
        float[] floorGrid;
        float floorX0, floorZ0, globalFloor;
        int floorNx, floorNz;
        float lightDown, lightFlat;
        bool allShown = true;
        int litRenderers, litCasters, totalRenderers, totalCasters, litCells, awake;
        float costMs;

        // ================================================================== armado
        /// <summary>Lo llama WorldBuilder al final de Build: el lote estático ya está combinado y los enemigos creados.</summary>
        public static ZoneCulling Create(GameObject host, Transform staticRoot, Transform dynamicRoot, IReadOnlyList<Encounter> encounters, IReadOnlyList<BossArena> arenas)
        {
            var zc = host.AddComponent<ZoneCulling>();
            zc.Collect(staticRoot, dynamicRoot, encounters, arenas);
            return zc;
        }

        void Awake() => Instance = this;

        void OnDestroy() { if (Instance == this) Instance = null; }

        /// <summary>Si alguien apaga el componente, nada queda escondido ni dormido.</summary>
        void OnDisable() => ShowAll();

        void Collect(Transform staticRoot, Transform dynamicRoot, IReadOnlyList<Encounter> encounters, IReadOnlyList<BossArena> arenas)
        {
            var found = new List<Item>(2400);
            // todo lo prendido del lote estático (los límites invisibles B__ vienen con el renderer apagado y quedan fuera)
            foreach (var r in staticRoot.GetComponentsInChildren<Renderer>(true))
                if (r.enabled && r.gameObject.activeInHierarchy) Add(found, r, 0f);
            // el vaivén de los botes (FloatingBob) sigue corriendo: apagado, el primer cuadro en que el bote vuelve a
            // entrar se lo vería en la ola de cuando salió y saltaría hasta 0.26 m al siguiente
            foreach (Transform t in dynamicRoot)
            {
                float pad = DynamicPad(t);
                if (pad < 0f) continue;
                foreach (var r in t.GetComponentsInChildren<Renderer>(true)) Add(found, r, pad);
            }
            BuildFloor(staticRoot);
            BuildCells(found);
            foreach (var enc in encounters)
                if (enc != null) foreach (var m in enc.Members) AddSleeper(m);
            foreach (var a in arenas) if (a != null) AddSleeper(a.Boss);
            Debug.Log($"[Nindo] ZoneCulling: {totalRenderers} renderers en {cells.Length} celdas, {sleepers.Count} enemigos.");
            if (huge > 0) Debug.LogWarning($"[Nindo] ZoneCulling: {huge} renderers con bounds de más de {HugeBounds} m (¿el de la malla combinada del static batching?): quedan siempre prendidos.");
        }

        /// <summary>
        /// Qué hijos de "Dynamic" se manejan y con cuánto margen (m). -1: no se tocan (el agua, los encuentros y los
        /// jefes, el abuelo, la puerta de los sellos, las zonas): se mueven, tienen lógica propia o no dibujan nada. La
        /// puerta gira sobre la bisagra: su margen es lo que mide la hoja (lo calcula Add).
        /// </summary>
        static float DynamicPad(Transform t)
        {
            if (t.GetComponent<GateDoor>() != null) return DoorPad;
            if (t.GetComponent<Checkpoint>() != null || t.GetComponent<Portal>() != null || t.GetComponent<FlagBarrier>() != null || t.GetComponent<FloatingBob>() != null) return 1f;
            if (t.name == "Fireflies") return 0f;   // M__Fireflies: solo el sistema de partículas
            return -1f;
        }

        const float DoorPad = 1000f, HugeBounds = 200f;
        int huge;

        void Add(List<Item> list, Renderer r, float pad)
        {
            // solo lo que no cambia de forma: mallas fijas y partículas (con su caja estimada). Una línea, una estela o una
            // malla con piel (el humo del incienso, por ejemplo) mueven sus vértices y su caja: esos los sigue probando Unity
            if (!(r is MeshRenderer) && !(r is ParticleSystemRenderer)) return;
            Bounds b = r is ParticleSystemRenderer ? ParticleBounds(r.GetComponent<ParticleSystem>())
                     : r.gameObject.activeInHierarchy ? r.bounds : MeshBounds(r);
            if (pad >= DoorPad) pad = Mathf.Max(b.size.x, b.size.z);
            // lo más grande del mapa son los chunks de 60 m: un bounds de cientos de metros sería el de la malla combinada
            // del lote estático y esa celda quedaría siempre prendida (no se ve mal, pero no ahorra): se avisa
            if (b.size.x > HugeBounds || b.size.z > HugeBounds) huge++;
            b.Expand(2f * (Margin + pad));
            bool shadows = r.shadowCastingMode != ShadowCastingMode.Off;
            list.Add(new Item { r = r, min = b.min, max = b.max, shadows = shadows, on = true });
            worldMask |= 1 << r.gameObject.layer;
            totalRenderers++;
            if (shadows) totalCasters++;
        }

        /// <summary>Partículas: el bounds del renderer recién creado puede estar vacío; se arma con la forma del emisor y
        /// lo que llegan a moverse (luciérnagas con ruido, humo que sube ~5 m).</summary>
        static Bounds ParticleBounds(ParticleSystem ps)
        {
            var t = ps.transform;
            var sh = ps.shape;
            Vector3 s = sh.enabled && sh.shapeType == ParticleSystemShapeType.Box ? Vector3.Scale(sh.scale, t.lossyScale) : Vector3.zero;
            float h = Mathf.Max(Mathf.Abs(s.x), Mathf.Abs(s.z)) * 0.5f + 3f, v = Mathf.Abs(s.y) * 0.5f;
            var b = new Bounds();
            b.SetMinMax(t.position - new Vector3(h, v + 1.5f, h), t.position + new Vector3(h, v + 6f, h));
            return b;
        }

        /// <summary>Bounds de un renderer apagado (la cuerda ya quitada, el portal sin desbloquear): el de Unity da vacío.</summary>
        static Bounds MeshBounds(Renderer r)
        {
            var mf = r.GetComponent<MeshFilter>();
            var t = r.transform;
            if (mf == null || mf.sharedMesh == null) return new Bounds(t.position, Vector3.one * 2f);
            var lb = mf.sharedMesh.bounds;
            var m = t.localToWorldMatrix;
            var b = new Bounds(m.MultiplyPoint3x4(lb.center), Vector3.zero);
            for (int i = 0; i < 8; i++)
                b.Encapsulate(m.MultiplyPoint3x4(lb.center + Vector3.Scale(lb.extents, new Vector3((i & 1) == 0 ? -1 : 1, (i & 2) == 0 ? -1 : 1, (i & 4) == 0 ? -1 : 1))));
            return b;
        }

        /// <summary>
        /// Alturas del terreno cada 4 m con rayos contra los colliders T__ (solo el terreno: un techo daría un piso más
        /// alto y sombras que no se tienen en cuenta). Sirve para saber hasta dónde baja la sombra de cada celda.
        /// </summary>
        void BuildFloor(Transform staticRoot)
        {
            var cols = new List<MeshCollider>();
            foreach (var c in staticRoot.GetComponentsInChildren<MeshCollider>())
                if (c.name.StartsWith("T__")) cols.Add(c);
            globalFloor = float.PositiveInfinity;
            if (cols.Count == 0) { floorGrid = null; return; }
            Bounds all = cols[0].bounds;
            foreach (var c in cols) all.Encapsulate(c.bounds);
            floorX0 = all.min.x; floorZ0 = all.min.z;
            floorNx = Mathf.CeilToInt(all.size.x / FloorStep) + 1;
            floorNz = Mathf.CeilToInt(all.size.z / FloorStep) + 1;
            floorGrid = new float[floorNx * floorNz];
            for (int i = 0; i < floorGrid.Length; i++) floorGrid[i] = float.PositiveInfinity;
            foreach (var c in cols)
            {
                var b = c.bounds;
                int i0 = Mathf.Max(0, Mathf.CeilToInt((b.min.x - floorX0) / FloorStep)), i1 = Mathf.Min(floorNx - 1, Mathf.FloorToInt((b.max.x - floorX0) / FloorStep));
                int j0 = Mathf.Max(0, Mathf.CeilToInt((b.min.z - floorZ0) / FloorStep)), j1 = Mathf.Min(floorNz - 1, Mathf.FloorToInt((b.max.z - floorZ0) / FloorStep));
                for (int j = j0; j <= j1; j++)
                    for (int i = i0; i <= i1; i++)
                    {
                        var ray = new Ray(new Vector3(floorX0 + i * FloorStep, b.max.y + 1f, floorZ0 + j * FloorStep), Vector3.down);
                        if (!c.Raycast(ray, out var hit, b.size.y + 2f)) continue;
                        int k = j * floorNx + i;
                        floorGrid[k] = Mathf.Min(floorGrid[k], hit.point.y);
                        globalFloor = Mathf.Min(globalFloor, hit.point.y);
                    }
            }
            if (float.IsInfinity(globalFloor)) { floorGrid = null; return; }
            for (int i = 0; i < floorGrid.Length; i++) if (float.IsInfinity(floorGrid[i])) floorGrid[i] = globalFloor;
            globalFloor -= FloorSafety;
        }

        /// <summary>Piso más bajo del terreno debajo de la caja y a FloorReach m alrededor (las vetas de los arroyos son
        /// más finas que la grilla: FloorSafety).</summary>
        float FloorAround(Vector3 min, Vector3 max)
        {
            float f = min.y;
            if (floorGrid == null) return f - 10f;
            int i0 = Mathf.Clamp(Mathf.FloorToInt((min.x - FloorReach - floorX0) / FloorStep), 0, floorNx - 1), i1 = Mathf.Clamp(Mathf.CeilToInt((max.x + FloorReach - floorX0) / FloorStep), 0, floorNx - 1);
            int j0 = Mathf.Clamp(Mathf.FloorToInt((min.z - FloorReach - floorZ0) / FloorStep), 0, floorNz - 1), j1 = Mathf.Clamp(Mathf.CeilToInt((max.z + FloorReach - floorZ0) / FloorStep), 0, floorNz - 1);
            for (int j = j0; j <= j1; j++)
                for (int i = i0; i <= i1; i++) f = Mathf.Min(f, floorGrid[j * floorNx + i]);
            return f - FloorSafety;
        }

        /// <summary>
        /// Agrupa por celda de CellSize (por el centro de cada caja) y deja los items ordenados por celda. Lo que mide más
        /// que una celda (los chunks de 60 m del terreno y de la decoración) va solo en la suya.
        /// </summary>
        void BuildCells(List<Item> found)
        {
            var keyOf = new Dictionary<long, int>();
            var cellOf = new int[found.Count];
            var counts = new List<int>();
            for (int i = 0; i < found.Count; i++)
            {
                var it = found[i];
                long key;
                if (it.max.x - it.min.x > CellSize || it.max.z - it.min.z > CellSize) key = long.MinValue + i;
                else
                {
                    long cx = Mathf.FloorToInt((it.min.x + it.max.x) * 0.5f / CellSize), cz = Mathf.FloorToInt((it.min.z + it.max.z) * 0.5f / CellSize);
                    key = (cx << 32) ^ (cz & 0xffffffffL);
                }
                if (!keyOf.TryGetValue(key, out int c)) { c = counts.Count; keyOf[key] = c; counts.Add(0); }
                cellOf[i] = c;
                counts[c]++;
            }
            cells = new Cell[counts.Count];
            int start = 0;
            for (int c = 0; c < cells.Length; c++)
            {
                cells[c] = new Cell { start = start, min = Vector3.positiveInfinity, max = Vector3.negativeInfinity };
                start += counts[c];
            }
            items = new Item[found.Count];
            float now = Time.unscaledTime;
            for (int i = 0; i < found.Count; i++)
            {
                ref var c = ref cells[cellOf[i]];
                var it = found[i];
                it.seen = now;
                items[c.start + c.count++] = it;
                c.min = Vector3.Min(c.min, it.min);
                c.max = Vector3.Max(c.max, it.max);
                c.shadows |= it.shadows;
                c.lit++;
            }
            float lowest = float.PositiveInfinity;
            for (int c = 0; c < cells.Length; c++)
            {
                cells[c].floor = FloorAround(cells[c].min, cells[c].max);
                lowest = Mathf.Min(lowest, cells[c].floor);
            }
            // sin terreno con collider (el piso de prueba): el piso de todo el mapa es el más bajo de las celdas
            if (float.IsInfinity(globalFloor)) globalFloor = float.IsInfinity(lowest) ? -10f : lowest - 10f;
            litRenderers = totalRenderers; litCasters = totalCasters;
        }

        void AddSleeper(Enemy e)
        {
            if (e == null) return;
            // los jefes son largos (el koi mide 7.5 m) o levantan el arma por encima de su altura
            float extra = e is Boss ? 6f : 1.5f;
            sleepers.Add(new Sleeper { e = e, pad = e.Radius + extra, height = e.config.height * Mathf.Max(0.5f, e.config.scale) + extra, seen = Time.unscaledTime });
            foreach (var r in e.GetComponentsInChildren<Renderer>(true)) worldMask |= 1 << r.gameObject.layer;
        }

        // ================================================================== cada frame
        void LateUpdate()
        {
            if (items == null) return;
            if (!On) { if (!allShown) ShowAll(); return; }
            if (Game.Player == null) return;
            long t0 = System.Diagnostics.Stopwatch.GetTimestamp();
            PrepareLight();
            if (!PrepareCameras())
            {
                // más cámaras de las que se prueban: nada escondido (es raro y así no hay forma de que falte algo)
                if (!allShown) ShowAll();
                return;
            }
            // ninguna cámara dibuja el mundo este frame (una pantalla negra, un menú): se deja todo como estaba
            if (camCount == 0) return;
            allShown = false;
            float now = Time.unscaledTime;
            litCells = 0;
            for (int c = 0; c < cells.Length; c++) TickCell(ref cells[c], now);
            TickSleepers(now);
            float ms = (System.Diagnostics.Stopwatch.GetTimestamp() - t0) * 1000f / System.Diagnostics.Stopwatch.Frequency;
            costMs = Mathf.Lerp(costMs, ms, 0.05f);
        }

        /// <summary>La dirección de la luna, que el eclipse de Kokuyō gira: se lee en vivo. Sin sombras, no hay barrido.</summary>
        void PrepareLight()
        {
            var sun = RenderSettings.sun;
            sunDir = sun != null && sun.isActiveAndEnabled && sun.shadows != LightShadows.None ? sun.transform.forward : Vector3.zero;
            lightDown = -sunDir.y;
            lightFlat = Mathf.Sqrt(sunDir.x * sunDir.x + sunDir.z * sunDir.z);
        }

        Vector3 sunDir;

        /// <summary>
        /// Los frustums de este frame: la cámara de juego (CameraDirector ya la movió: corre antes) y las otras cámaras
        /// prendidas del juego que dibujan alguna capa del mundo. false si son más de MaxCameras.
        /// </summary>
        bool PrepareCameras()
        {
            camCount = 0;
            var main = Game.Camera != null ? Game.Camera.Cam : null;
            if (main != null && main.isActiveAndEnabled) AddCamera(main);
            int n = Camera.allCamerasCount;
            if (n > camBuf.Length) camBuf = new Camera[n * 2];
            n = Camera.GetAllCameras(camBuf);
            for (int i = 0; i < n; i++)
            {
                var c = camBuf[i];
                camBuf[i] = null;   // el buffer no retiene cámaras destruidas
                if (c == main || c.cameraType != CameraType.Game || (c.cullingMask & worldMask) == 0) continue;
                if (camCount == MaxCameras) { for (int j = i + 1; j < n; j++) camBuf[j] = null; return false; }
                AddCamera(c);
            }
            return true;
        }

        /// <summary>Planos del frustum orientados hacia adentro (se verifica con un punto delante de la cámara), con su
        /// producto con la luz para el barrido de sombra.</summary>
        void AddCamera(Camera cam)
        {
            GeometryUtility.CalculateFrustumPlanes(cam, planes);
            Vector3 probe = cam.transform.position + cam.transform.forward * (cam.nearClipPlane + 1f);
            int o = camCount * 6;
            for (int i = 0; i < 6; i++)
            {
                Vector3 n = planes[i].normal;
                float d = planes[i].distance;
                if (Vector3.Dot(n, probe) + d < 0f) { n = -n; d = -d; }
                fp[o + i] = new FPlane { x = n.x, y = n.y, z = n.z, d = d, l = Vector3.Dot(n, sunDir) };
            }
            camCount++;
        }

        /// <summary>Largo del barrido de sombra (m a lo largo de la luz) de una caja con techo 'top' hasta el piso 'floor'.</summary>
        float Sweep(float top, float floor)
        {
            if (lightDown <= 0.01f) return lightDown > 0f || lightFlat > 0f ? MaxSweep : 0f;
            float s = (top - floor) / lightDown;
            // la sombra llega más lejos que el vecindario donde se midió el piso: abajo puede haber algo más bajo
            if (s * lightFlat > FloorReach) s = (top - globalFloor) / lightDown;
            return Mathf.Min(s, MaxSweep);
        }

        /// <summary>
        /// ¿La caja, o la caja estirada 's' m a lo largo de la luz (suma de Minkowski con el segmento de su sombra), puede
        /// tocar el frustum de alguna cámara? Plano por plano, como TestPlanesAABB: conservador, nunca da falso negativo.
        /// </summary>
        bool Visible(in Vector3 min, in Vector3 max, float s)
        {
            for (int c = 0; c < camCount; c++)
                if (InFrustum(c * 6, min, max, s)) return true;
            return false;
        }

        bool InFrustum(int o, in Vector3 min, in Vector3 max, float s)
        {
            for (int i = o; i < o + 6; i++)
            {
                var p = fp[i];
                float v = p.x * (p.x >= 0f ? max.x : min.x) + p.y * (p.y >= 0f ? max.y : min.y) + p.z * (p.z >= 0f ? max.z : min.z) + p.d;
                float k = s * p.l;
                if (k > 0f) v += k;
                if (v < 0f) return false;
            }
            return true;
        }

        void TickCell(ref Cell c, float now)
        {
            bool pass = Visible(c.min, c.max, c.shadows ? Sweep(c.max.y, c.floor) : 0f);
            if (pass) litCells++;
            else if (c.lit == 0) return;
            int end = c.start + c.count;
            for (int i = c.start; i < end; i++)
            {
                ref var it = ref items[i];
                bool want = pass && Visible(it.min, it.max, it.shadows ? Sweep(it.max.y, c.floor) : 0f);
                if (want) { it.seen = now; if (!it.on) Set(ref it, ref c, true); }
                else if (it.on && now - it.seen > Linger) Set(ref it, ref c, false);
            }
        }

        void Set(ref Item it, ref Cell c, bool on)
        {
            it.on = on;
            int k = on ? 1 : -1;
            c.lit += k;
            // lo que otro sistema destruyó después del armado se saltea (el == de Unity)
            if (it.r != null) it.r.forceRenderingOff = !on;
            litRenderers += k;
            if (it.shadows) litCasters += k;
        }

        void TickSleepers(float now)
        {
            Vector3 k = Game.Player.transform.position;
            bool bossFight = Game.Combat != null && Game.Combat.ActiveBoss != null;
            awake = 0;
            for (int i = 0; i < sleepers.Count; i++)
            {
                var s = sleepers[i];
                var e = s.e;
                if (e == null) continue;
                // muerto y apagado, o jefe ya vencido: no se toca (y si quedó dormido, se lo despierta)
                if (!e.gameObject.activeInHierarchy) { if (e.Asleep) Wake(s); continue; }
                Vector3 p = e.transform.position;
                float dx = p.x - k.x, dz = p.z - k.z, r = e.Asleep ? WakeRadius : SleepRadius;
                bool want = dx * dx + dz * dz < r * r;
                if (!want)
                {
                    Vector3 min = new Vector3(p.x - s.pad, p.y - 0.5f, p.z - s.pad), max = new Vector3(p.x + s.pad, p.y + s.height, p.z + s.pad);
                    if ((p - s.floorAt).sqrMagnitude > 4f) { s.floorAt = p; s.floor = FloorAround(min, max); }
                    want = Visible(min, max, Sweep(max.y, s.floor));
                }
                if (want) s.seen = now;
                if (e.Asleep) { if (want || !e.CanSleep) Wake(s); }
                else if (!bossFight && now - s.seen > SleepDelay && e.CanSleep) Sleep(s);
                if (!e.Asleep) awake++;
            }
        }

        void Sleep(Sleeper s)
        {
            // se vuelve a juntar en cada siesta: un kit, una estela o lo que agregue otro sistema después del arranque
            s.e.GetComponentsInChildren(true, s.rs);
            for (int i = 0; i < s.rs.Count; i++) s.rs[i].forceRenderingOff = true;
            s.e.SetAsleep(true);
        }

        void Wake(Sleeper s)
        {
            for (int i = 0; i < s.rs.Count; i++) if (s.rs[i] != null) s.rs[i].forceRenderingOff = false;
            s.rs.Clear();
            if (s.e != null) s.e.SetAsleep(false);
        }

        /// <summary>Todo prendido y despierto (ZoneCulling.On = false o el componente apagado).</summary>
        void ShowAll()
        {
            allShown = true;
            if (cells == null) return;
            for (int c = 0; c < cells.Length; c++)
            {
                ref var cell = ref cells[c];
                int end = cell.start + cell.count;
                for (int i = cell.start; i < end; i++)
                    if (!items[i].on) Set(ref items[i], ref cell, true);
            }
            foreach (var s in sleepers) if (s.e != null && s.e.Asleep) Wake(s);
            awake = sleepers.Count;
        }
    }
}
