using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Nindo
{
    /// <summary>
    /// Activación por zonas del mundo (pedido 17). Antes había FBX por zona, static batching, el frustum culling de Unity,
    /// la decoración fusionada por chunk de 60 m, LightPool (10 luces a menos de 45 m), far clip 400 y la cascada que se
    /// apaga a 110 m. Los Animators ya usaban CullUpdateTransforms, las pieles no se actualizaban fuera de cuadro y los
    /// resortes y el poser del sumo ya se salteaban sin verse. Nada se apagaba por zona: Unity probaba los ~2000
    /// renderers del mapa en cada cull (la cámara y cada cascada) y su extrusión de sombras hacia la luna no tiene fin (un
    /// prop cuya sombra muere en la ladera de al lado se seguía dibujando en el mapa de sombras: simulado sobre el mapa,
    /// ~20 % de los casters con la calidad Alta, la de serie), y el Update de cada enemigo seguía corriendo aunque
    /// estuviera a 300 m. En la pasada principal no se ahorra ningún draw: lo que esto apaga, Unity ya no lo dibujaba.
    ///
    /// Corre en cada frame DESPUÉS de que la cámara se movió (orden 10050; CameraDirector es 500) y prueba contra el
    /// frustum de esa misma cámara, sea la de juego, un plano de presentación, la grúa de la cascada o un plano al cielo
    /// (y contra el de cualquier otra cámara prendida que dibuje el mundo y, en el editor, el de la vista Scene):
    ///  * Renderers del mundo (props del lote estático, terreno, decoración, santuarios, portales, puertas, cuerdas, botes,
    ///    luciérnagas y humo) en celdas de 32 m. La caja de cada celda (y después la de cada renderer de una celda que
    ///    pasó) se barre a lo largo de la luz de la luna hasta el piso más bajo de su vecindario: lo que está fuera de
    ///    cuadro pero tira sombra adentro sigue prendido. Lo que no hace falta queda con forceRenderingOff: no toca
    ///    'enabled' ni el GameObject (no pisa a quien los prende o apaga), no rompe el static batching ni los colliders.
    ///    Prender es en el mismo frame en que algo entra a cuadro, así que no hay pop-in posible ni con un corte de
    ///    cámara, una cinemática o un teletransporte; apagar espera 0.35 s (sin parpadeo en el borde del cuadro).
    ///  * Partículas del mundo en loop (luciérnagas, humo): al apagarse su renderer se pausan a mano (Pause) y siguen al
    ///    volver; su caja sale de lo que llegan a moverse según su propio sistema (emisor, velocidad, ruido, fuerzas,
    ///    gravedad, vida, escala) y además crece con lo que de verdad ocupan mientras simulan.
    ///  * La cascada de Kohan (fuera del lote: cuelga de [World]): dentro de su LOD de 110 m, con ninguna cámara
    ///    mirándola, KohanFalls.SetOffscreen congela sus ~1300 partículas y su emisión a mano.
    ///  * Enemigos y jefes del mundo, por encuentro: cuando todos los de un campamento están quietos en su puesto
    ///    (Enemy.CanSleep), a más de 55 m de Kaito y fuera de cuadro (con su sombra) se duermen juntos (Enemy.SetAsleep):
    ///    sin dibujarse y, los comunes, sin Update ni Animator (congelados todos en el mismo frame: los idles de a dos
    ///    no se desfasan). Se despiertan todos juntos apenas uno queda a menos de 45 m, entra a cuadro o deja de cumplir
    ///    CanSleep (un Alert del encuentro o del guion, un veto); uno que se despertó solo (SetState) despierta a los
    ///    demás. Mientras pelea un jefe no se duerme a nadie nuevo.
    ///  * Las luces no se tocan: URP descarta solo las que no tocan el frustum y LightPool reparte las de los faroles
    ///    (simulado sobre el mapa: con su densidad nunca deja apagada una luz que se ve).
    /// Medición y depuración en ZoneCulling.Debug.cs (Stats, ShowHud, Benchmark, CheckFrame).
    /// </summary>
    [DefaultExecutionOrder(10050)]
    public partial class ZoneCulling : MonoBehaviour
    {
        public static ZoneCulling Instance { get; private set; }
        /// <summary>
        /// Con false todo queda prendido y despierto como antes (comparar, depurar, mirar la escena del editor). Apagarlo
        /// prende todo en el acto, no en el próximo LateUpdate: así sirve alrededor de un Camera.Render a mano en cualquier
        /// momento del frame; al volver a true, el próximo LateUpdate apaga lo que sobra.
        /// </summary>
        public static bool On
        {
            get => on;
            set
            {
                if (on == value) return;
                on = value;
                if (!value && Instance != null) Instance.ShowAll();
            }
        }
        static bool on = true;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { Instance = null; on = true; hudWanted = false; IncludeSceneView = true; HideBatched = true; }

        /// <summary>
        /// Con false, lo que está en el lote estático no se esconde nunca (solo lo de fuera del lote). Por si esconder
        /// casters en medio de una corrida del lote la parte en más draws de sombra que los que ahorra: Benchmark avisa
        /// si con culling suben los Batches o los Draw Calls, y se compara con esto en false.
        /// </summary>
        public static bool HideBatched = true;

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
            /// <summary>'always': partículas con algo que la caja no puede acotar (luces, subemisores, emisor de malla):
            /// nunca se esconde. 'batched': parte del lote estático (HideBatched).</summary>
            public bool always, batched;
            public float seen;
            /// <summary>Partículas en loop de este renderer (null si no es eso) y si las pausó ZoneCulling.</summary>
            public ParticleSystem ps;
            public bool paused;
        }

        /// <summary>La cascada: su caja (crece con lo que ocupan sus partículas) y desde cuándo nadie la necesita.</summary>
        class Falls
        {
            public KohanFalls f;
            public readonly List<ParticleSystemRenderer> rs = new List<ParticleSystemRenderer>();
            public Vector3 min, max;
            public float seen;
            public bool off;
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
        /// <summary>Los miembros de cada encuentro (y cada jefe solo): se duermen y se despiertan juntos.</summary>
        readonly List<Sleeper[]> groups = new List<Sleeper[]>();
        readonly Plane[] planes = new Plane[6];
        readonly FPlane[] fp = new FPlane[6 * MaxCameras];
        readonly List<Falls> falls = new List<Falls>();
        Camera[] camBuf = new Camera[8];
        /// <summary>mainCam: el lugar de la cámara de juego entre los frustums de este frame (-1 si no dibuja).</summary>
        int camCount, worldMask, mainCam = -1;
        /// <summary>El último frame (y su hora) en que se decidió todo con el estado de ahora: CheckFrame espera uno.</summary>
        int lastCullFrame = -1;
        float lastCullTime;
        float[] floorGrid;
        float floorX0, floorZ0, globalFloor;
        int floorNx, floorNz;
        float lightDown, lightFlat;
        bool allShown = true;
        int litRenderers, litCasters, totalRenderers, totalCasters, totalParticles, litCells, awake;
        float costMs;

        // ================================================================== armado
        /// <summary>Lo llama WorldBuilder al final de Build: el lote estático ya está combinado y los enemigos creados.</summary>
        public static ZoneCulling Create(GameObject host, Transform staticRoot, Transform dynamicRoot, IReadOnlyList<Encounter> encounters, IReadOnlyList<BossArena> arenas)
        {
            var zc = host.AddComponent<ZoneCulling>();
            zc.Collect(staticRoot, dynamicRoot, encounters, arenas);
            return zc;
        }

        void Awake()
        {
            Instance = this;
#if UNITY_EDITOR
            UnityEditor.SceneView.duringSceneGui += OnSceneGui;
#endif
        }

        void OnDestroy()
        {
            if (Instance == this) Instance = null;
#if UNITY_EDITOR
            UnityEditor.SceneView.duringSceneGui -= OnSceneGui;
#endif
        }

        /// <summary>Si alguien apaga el componente (o se sale de Play, o se rearma el mundo), nada queda escondido ni
        /// dormido, y una medición cortada a la mitad devuelve lo que había cambiado (On, la vista Scene, fps, vsync).</summary>
        void OnDisable()
        {
            RestoreDebug();
            ShowAll();
        }

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
            var group = new List<Sleeper>();
            foreach (var enc in encounters)
            {
                if (enc == null) continue;
                group.Clear();
                foreach (var m in enc.Members) { var s = AddSleeper(m); if (s != null) group.Add(s); }
                if (group.Count > 0) groups.Add(group.ToArray());
            }
            foreach (var a in arenas)
            {
                var s = a != null ? AddSleeper(a.Boss) : null;
                if (s != null) groups.Add(new[] { s });
            }
            if (staticRoot.parent != null)
                foreach (var f in staticRoot.parent.GetComponentsInChildren<KohanFalls>(true)) AddFalls(f);
            Debug.Log($"[Nindo] ZoneCulling: {totalRenderers} renderers en {cells.Length} celdas, {sleepers.Count} enemigos, {falls.Count} cascada(s).");
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
            bool always = false;
            Bounds b = r is ParticleSystemRenderer ? ParticleBounds(r.GetComponent<ParticleSystem>(), out always)
                     : r.gameObject.activeInHierarchy ? r.bounds : MeshBounds(r);
            if (always) Debug.LogWarning($"[Nindo] ZoneCulling: las partículas '{r.name}' usan luces, subemisores, fuerzas externas o un emisor de malla: quedan siempre prendidas.");
            if (pad >= DoorPad) pad = Mathf.Max(b.size.x, b.size.z);
            // lo más grande del mapa son los chunks de 60 m: un bounds de cientos de metros sería el de la malla combinada
            // del lote estático y esa celda quedaría siempre prendida (no se ve mal, pero no ahorra): se avisa
            if (b.size.x > HugeBounds || b.size.z > HugeBounds) huge++;
            b.Expand(2f * (Margin + pad));
            bool shadows = r.shadowCastingMode != ShadowCastingMode.Off;
            var ps = r is ParticleSystemRenderer ? r.GetComponent<ParticleSystem>() : null;
            // uno de una sola vez se termina solo: solo se pausan los que siguen para siempre
            if (ps != null && !ps.main.loop) ps = null;
            if (ps != null) totalParticles++;
            list.Add(new Item { r = r, min = b.min, max = b.max, shadows = shadows, on = true, ps = ps, always = always, batched = r.isPartOfStaticBatch });
            worldMask |= 1 << r.gameObject.layer;
            totalRenderers++;
            if (shadows) totalCasters++;
        }

        /// <summary>
        /// Partículas: el bounds del renderer recién creado puede estar vacío y el que da Unity después solo abarca lo que
        /// ya se emitió. Se arma con el emisor (forma, radio, escala, giro y corrimiento del módulo Shape) más lo máximo
        /// que una partícula llega a alejarse en toda su vida según su propio sistema: velocidad inicial, velocidad y
        /// fuerza sobre la vida, ruido (actúa como velocidad: strength m/s por la parte que va a la posición; con damping,
        /// el de serie, dividido por la frecuencia: las luciérnagas a 0.35 Hz derivan a 1.7 m/s, no a 0.6), gravedad (el
        /// humo sube con gravedad negativa) y tamaño, todo escalado con la jerarquía si el sistema escala así. Es una cota
        /// por arriba (el ruido no empuja siempre para el mismo lado) y además TrackParticles la agranda con lo que el
        /// sistema ocupa de verdad. 'unsupported': algo que no se puede acotar desde acá (luces que alumbran fuera de las
        /// partículas, subemisores, fuerzas de viento, un emisor de malla): ese renderer no se esconde nunca.
        /// </summary>
        static Bounds ParticleBounds(ParticleSystem ps, out bool unsupported)
        {
            var t = ps.transform;
            var m = ps.main;
            unsupported = ps.lights.enabled || ps.subEmitters.enabled || ps.externalForces.enabled;
            Vector3 ls = t.lossyScale, center = t.position, half = Vector3.zero;
            var sh = ps.shape;
            if (sh.enabled)
            {
                Vector3 ss = Vector3.Scale(sh.scale, ls), e;
                switch (sh.shapeType)
                {
                    case ParticleSystemShapeType.Box: case ParticleSystemShapeType.BoxShell: case ParticleSystemShapeType.BoxEdge:
                    case ParticleSystemShapeType.Rectangle:
                        e = new Vector3(Mathf.Abs(ss.x), Mathf.Abs(ss.y), Mathf.Abs(ss.z)) * 0.5f;
                        break;
                    case ParticleSystemShapeType.Mesh: case ParticleSystemShapeType.MeshRenderer: case ParticleSystemShapeType.SkinnedMeshRenderer:
                    case ParticleSystemShapeType.Sprite: case ParticleSystemShapeType.SpriteRenderer:
                        unsupported = true;
                        e = Vector3.zero;
                        break;
                    default:   // esfera, semiesfera, cono, círculo, dona, borde: el radio (más el largo del cono con volumen)
                        float r = (sh.radius + (sh.shapeType == ParticleSystemShapeType.Donut ? sh.donutRadius : 0f)
                                   + (sh.shapeType == ParticleSystemShapeType.ConeVolume ? sh.length : 0f)) * MaxAbs(ss);
                        e = new Vector3(r, r, r);
                        break;
                }
                // la caja del mundo del emisor girado (|R| por los semiejes), corrido a donde lo pone el módulo
                var rot = Matrix4x4.Rotate(t.rotation * Quaternion.Euler(sh.rotation));
                for (int i = 0; i < 3; i++) half[i] = Mathf.Abs(rot[i, 0]) * e.x + Mathf.Abs(rot[i, 1]) * e.y + Mathf.Abs(rot[i, 2]) * e.z;
                center += t.TransformVector(sh.position);
            }
            float life = CurveMax(m.startLifetime);
            float reach = CurveMax(m.startSpeed) * life;
            var vol = ps.velocityOverLifetime;
            if (vol.enabled)
            {
                reach *= Mathf.Max(1f, CurveMax(vol.speedModifier));
                // por eje como mucho el máximo de los tres por raíz de 3 (en espacio local los ejes giran)
                reach += (1.7320508f * Max3(CurveMax(vol.x), CurveMax(vol.y), CurveMax(vol.z)) + CurveMax(vol.radial)) * life;
                // la órbita no aleja del eje, pero alrededor de un centro corrido puede llevarla al otro lado
                if (Max3(CurveMax(vol.orbitalX), CurveMax(vol.orbitalY), CurveMax(vol.orbitalZ)) > 0f)
                    reach += 2f * new Vector3(CurveMax(vol.orbitalOffsetX), CurveMax(vol.orbitalOffsetY), CurveMax(vol.orbitalOffsetZ)).magnitude;
            }
            var fol = ps.forceOverLifetime;
            if (fol.enabled) reach += 0.5f * 1.7320508f * Max3(CurveMax(fol.x), CurveMax(fol.y), CurveMax(fol.z)) * life * life;
            var n = ps.noise;
            if (n.enabled)
            {
                float st = n.separateAxes ? Max3(CurveMax(n.strengthX), CurveMax(n.strengthY), CurveMax(n.strengthZ)) : CurveMax(n.strength);
                // con frecuencia de más de 1 Hz el damping la achicaría: se deja la cota sin achicar
                if (n.damping) st /= Mathf.Clamp(n.frequency, 0.05f, 1f);
                reach += st * CurveMax(n.positionAmount) * life;
            }
            float size = m.startSize3D ? Max3(CurveMax(m.startSizeX), CurveMax(m.startSizeY), CurveMax(m.startSizeZ)) : CurveMax(m.startSize);
            var sol = ps.sizeOverLifetime;
            reach += size * (sol.enabled ? Mathf.Max(1f, CurveMax(sol.size)) : 1f);
            // con Hierarchy (el de FXFactory) o Local, velocidades, fuerzas y tamaño también escalan con el transform
            if (m.scalingMode != ParticleSystemScalingMode.Shape) reach *= Mathf.Max(1f, MaxAbs(ls));
            // con gravedad positiva caen (la caja baja), con negativa suben (el humo); con una curva, para los dos lados
            float g = m.gravityModifier.mode == ParticleSystemCurveMode.Constant ? m.gravityModifier.constant : CurveMax(m.gravityModifier);
            float fall = g * Physics.gravity.magnitude * 0.5f * life * life;
            float down = m.gravityModifier.mode == ParticleSystemCurveMode.Constant ? Mathf.Max(0f, fall) : fall;
            float up = m.gravityModifier.mode == ParticleSystemCurveMode.Constant ? Mathf.Max(0f, -fall) : fall;
            Vector3 ext = half + new Vector3(reach, reach, reach);
            var b = new Bounds();
            b.SetMinMax(center - ext - new Vector3(0f, down, 0f), center + ext + new Vector3(0f, up, 0f));
            return b;
        }

        static float Max3(float a, float b, float c) => Mathf.Max(a, Mathf.Max(b, c));
        static float MaxAbs(Vector3 v) => Max3(Mathf.Abs(v.x), Mathf.Abs(v.y), Mathf.Abs(v.z));

        /// <summary>
        /// La cascada: su caja arranca con lo que miden sus mallas (cortinas, nieblas, el estanque) más 8 m, y
        /// TrackParticles la agranda con lo que ocupan de verdad sus partículas mientras simulan (las columnas de niebla
        /// suben ~20 m en 9 s y la sábana de las ráfagas cruza la plataforma): antes de poder congelarse simula
        /// KohanFalls.WarmTime entero, así que para entonces la caja ya vio la columna completa.
        /// </summary>
        void AddFalls(KohanFalls f)
        {
            var fc = new Falls { f = f, seen = Time.unscaledTime };
            bool any = false;
            Bounds b = default;
            foreach (var r in f.GetComponentsInChildren<Renderer>(true))
            {
                if (r is ParticleSystemRenderer pr) { fc.rs.Add(pr); continue; }
                if (!r.gameObject.activeInHierarchy) continue;
                if (!any) { b = r.bounds; any = true; } else b.Encapsulate(r.bounds);
            }
            if (!any) b = new Bounds(f.PlungeCenter, Vector3.zero);
            b.Expand(16f);
            fc.min = b.min; fc.max = b.max;
            falls.Add(fc);
        }

        /// <summary>El valor más grande (en módulo) que puede dar una curva de partículas.</summary>
        static float CurveMax(ParticleSystem.MinMaxCurve c)
        {
            switch (c.mode)
            {
                case ParticleSystemCurveMode.Constant: return Mathf.Abs(c.constant);
                case ParticleSystemCurveMode.TwoConstants: return Mathf.Max(Mathf.Abs(c.constantMin), Mathf.Abs(c.constantMax));
                case ParticleSystemCurveMode.Curve: return Mathf.Abs(c.curveMultiplier) * KeyMax(c.curve);
                default: return Mathf.Abs(c.curveMultiplier) * Mathf.Max(KeyMax(c.curveMin), KeyMax(c.curveMax));
            }
        }

        static float KeyMax(AnimationCurve c)
        {
            float m = 0f;
            if (c != null) foreach (var k in c.keys) m = Mathf.Max(m, Mathf.Abs(k.value));
            return m;
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

        Sleeper AddSleeper(Enemy e)
        {
            if (e == null) return null;
            // los jefes son largos (el koi mide 7.5 m) o levantan el arma por encima de su altura
            float extra = e is Boss ? 6f : 1.5f;
            var s = new Sleeper { e = e, pad = e.Radius + extra, height = e.config.height * Mathf.Max(0.5f, e.config.scale) + extra, seen = Time.unscaledTime };
            sleepers.Add(s);
            foreach (var r in e.GetComponentsInChildren<Renderer>(true)) worldMask |= 1 << r.gameObject.layer;
            return s;
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
            TickFalls(now);
            TickSleepers(now);
            float ms = (System.Diagnostics.Stopwatch.GetTimestamp() - t0) * 1000f / System.Diagnostics.Stopwatch.Frequency;
            costMs = Mathf.Lerp(costMs, ms, 0.05f);
            lastCullFrame = Time.frameCount;
            lastCullTime = now;
            TickCheck(now);
        }

        /// <summary>
        /// Las cajas de las partículas crecen con lo que de verdad ocupan (si la cota de ParticleBounds se quedó corta,
        /// la próxima vez que salgan de cuadro ya no se esconden con partículas a la vista). En Update: los jobs de
        /// partículas de este frame todavía no arrancaron (lo hacen en PreLateUpdate) y leer su bounds no los espera.
        /// Cada 4 frames alcanza: lo que más rápido se mueve (la llovizna de la cascada, 7 m/s) no llega a 0.5 m.
        /// </summary>
        void Update()
        {
            PollDebugKeys();
            if (items == null || !On || (Time.frameCount & 3) != 0) return;
            for (int i = 0; i < items.Length; i++)
            {
                ref var it = ref items[i];
                if (it.ps == null || !it.on || it.paused || it.r == null) continue;
                if (Grow(ref it.min, ref it.max, it.r.bounds, Margin))
                    for (int c = 0; c < cells.Length; c++)
                        if (i >= cells[c].start && i < cells[c].start + cells[c].count) { cells[c].min = Vector3.Min(cells[c].min, it.min); cells[c].max = Vector3.Max(cells[c].max, it.max); break; }
            }
            foreach (var fc in falls)
            {
                if (fc.f == null || fc.f.Frozen || !fc.f.Active) continue;
                foreach (var r in fc.rs) if (r != null) Grow(ref fc.min, ref fc.max, r.bounds, 2f);
            }
        }

        /// <summary>Agranda la caja para que entre 'b' con 'pad' de margen; true si creció. Un bounds vacío no cuenta.</summary>
        static bool Grow(ref Vector3 min, ref Vector3 max, Bounds b, float pad)
        {
            if (b.extents.sqrMagnitude < 1e-6f) return false;
            Vector3 lo = b.min - new Vector3(pad, pad, pad), hi = b.max + new Vector3(pad, pad, pad);
            if (lo.x >= min.x && lo.y >= min.y && lo.z >= min.z && hi.x <= max.x && hi.y <= max.y && hi.z <= max.z) return false;
            min = Vector3.Min(min, lo);
            max = Vector3.Max(max, hi);
            return true;
        }

        /// <summary>La cascada se congela cuando ninguna cámara ve su caja (sus partículas no tiran sombra) desde hace
        /// Linger, y vuelve en el mismo frame en que alguna la ve.</summary>
        void TickFalls(float now)
        {
            foreach (var fc in falls)
            {
                if (fc.f == null) continue;
                bool want = Visible(fc.min, fc.max, 0f);
                if (want) fc.seen = now;
                bool off = !want && now - fc.seen > Linger;
                if (off == fc.off) continue;
                fc.off = off;
                fc.f.SetOffscreen(off);
            }
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
            mainCam = -1;
            var main = Game.Camera != null ? Game.Camera.Cam : null;
            if (main != null && main.isActiveAndEnabled) { mainCam = 0; AddCamera(main); }
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
#if UNITY_EDITOR
            // la vista Scene es una cámara apagada que el editor dibuja a mano: sin esto, en Play se vería solo lo que
            // mira la cámara de juego. Su pose es la del último repintado (si se la mueve, se pone al día al frame
            // siguiente). Solo cuentan las que se están dibujando: una pestaña Scene escondida detrás de Game (el
            // diseño de serie, o "Maximize on Play") sigue en la lista con la última pose, a veces el mapa entero
            if (IncludeSceneView)
            {
                var views = UnityEditor.SceneView.sceneViews;
                float t = Time.realtimeSinceStartup;
                for (int i = 0; i < views.Count; i++)
                {
                    var sv = views[i] as UnityEditor.SceneView;
                    var c = sv != null ? sv.camera : null;
                    if (c == null || !sceneDrawn.TryGetValue(sv, out float drawn) || t - drawn > SceneViewStale) continue;
                    if (camCount == MaxCameras) return false;
                    AddCamera(c);
                }
            }
#endif
            return true;
        }

        /// <summary>
        /// En el editor, también se deja prendido lo que mira cada vista Scene visible (Felipe revisa el mapa ahí
        /// mientras juega): con una a la vista, Stats dice "cámaras 2". Benchmark y CheckFrame la sacan mientras miden.
        /// </summary>
        public static bool IncludeSceneView = true;

#if UNITY_EDITOR
        /// <summary>Segundos sin repintarse para que una vista Scene deje de contar (en Play, una visible se repinta en
        /// cada frame; al volver a mostrarla, su primer repintado puede salir con algo apagado: es solo el editor).</summary>
        const float SceneViewStale = 1f;
        readonly Dictionary<UnityEditor.SceneView, float> sceneDrawn = new Dictionary<UnityEditor.SceneView, float>();
        void OnSceneGui(UnityEditor.SceneView sv) => sceneDrawn[sv] = Time.realtimeSinceStartup;
#endif

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
            else if (c.lit == 0 && HideBatched) return;   // sin HideBatched, lo del lote se prende aunque la celda no pase
            int end = c.start + c.count;
            for (int i = c.start; i < end; i++)
            {
                ref var it = ref items[i];
                bool want = it.always || (it.batched && !HideBatched) || (pass && Visible(it.min, it.max, it.shadows ? Sweep(it.max.y, c.floor) : 0f));
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
            // las partículas escondidas se pausan a mano (no se depende de si el culling propio de Unity cuenta un
            // forceRenderingOff como "no se ve"). Solo se reanuda lo que pausó esto: si alguien las paró, quedan paradas
            if (it.ps == null) return;
            if (!on) { if (it.ps.isPlaying) { it.ps.Pause(true); it.paused = true; } }
            else if (it.paused) { it.paused = false; if (it.ps.isPaused) it.ps.Play(true); }
        }

        void TickSleepers(float now)
        {
            Vector3 k = Game.Player.transform.position;
            bool bossFight = Game.Combat != null && Game.Combat.ActiveBoss != null;
            awake = 0;
            // por campamento: si cada uno decidiera solo, los compañeros quedarían quietos y volverían en momentos
            // distintos (sus Update, sus timers de idle). Juntos: duermen cuando todos pueden y despiertan si uno debe
            for (int g = 0; g < groups.Count; g++)
            {
                var members = groups[g];
                bool wake = false, ready = !bossFight, anyAwake = false, anyAsleep = false;
                for (int i = 0; i < members.Length; i++)
                {
                    var s = members[i];
                    var e = s.e;
                    if (e == null) continue;
                    // muerto y apagado, o jefe ya vencido: no cuenta (y si quedó dormido, se lo despierta)
                    if (!e.gameObject.activeInHierarchy) { if (e.Asleep) Wake(s); continue; }
                    bool want = Needed(s, k), can = e.CanSleep;
                    if (want) s.seen = now;
                    if (want || (e.Asleep && !can)) wake = true;
                    if (!can || now - s.seen <= SleepDelay) ready = false;
                    if (e.Asleep) anyAsleep = true; else anyAwake = true;
                }
                // uno se despertó solo (un guion le cambió el estado, un reinicio del encuentro): los demás también
                if (anyAwake && anyAsleep) wake = true;
                for (int i = 0; i < members.Length; i++)
                {
                    var s = members[i];
                    if (s.e == null || !s.e.gameObject.activeInHierarchy) continue;
                    if (wake) { if (s.e.Asleep) Wake(s); }
                    else if (ready && !s.e.Asleep) Sleep(s);
                    if (!s.e.Asleep) awake++;
                }
            }
        }

        /// <summary>¿Hace falta despierto? Cerca de Kaito (con histéresis) o su caja, con la sombra, en cuadro.</summary>
        bool Needed(Sleeper s, Vector3 kaito)
        {
            Vector3 p = s.e.transform.position;
            float dx = p.x - kaito.x, dz = p.z - kaito.z, r = s.e.Asleep ? WakeRadius : SleepRadius;
            if (dx * dx + dz * dz < r * r) return true;
            Vector3 min = new Vector3(p.x - s.pad, p.y - 0.5f, p.z - s.pad), max = new Vector3(p.x + s.pad, p.y + s.height, p.z + s.pad);
            if ((p - s.floorAt).sqrMagnitude > 4f) { s.floorAt = p; s.floor = FloorAround(min, max); }
            return Visible(min, max, Sweep(max.y, s.floor));
        }

        /// <summary>Enemy.SetAsleep esconde sus renderers (los junta en cada siesta: un kit, una estela o lo que agregue
        /// otro sistema después del arranque) y apaga lo suyo; despertarlo lo devuelve todo.</summary>
        static void Sleep(Sleeper s) => s.e.SetAsleep(true);

        static void Wake(Sleeper s) { if (s.e != null) s.e.SetAsleep(false); }

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
            foreach (var fc in falls)
                if (fc.off) { fc.off = false; if (fc.f != null) fc.f.SetOffscreen(false); }
        }
    }
}
