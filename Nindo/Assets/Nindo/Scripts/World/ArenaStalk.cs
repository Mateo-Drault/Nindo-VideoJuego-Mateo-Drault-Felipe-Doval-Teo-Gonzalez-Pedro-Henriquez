using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

namespace Nindo
{
    /// <summary>
    /// Una caña del claro de Chikuō (Docs/handoff/diseno/chikuo_v2.md, sección 8): la arma WorldBuilder con el marcador
    /// M__Stalk__ID__tipo de World_bambu.fbx (posiciones en Tools/Blender/world/world_plan.py, BOSS_STALKS) sobre el FBX
    /// arena_stalk_&lt;tipo&gt; (Tools/Blender/world/arena_stalks.py). Es lo que la caña ES (anclas, arco, rajadura, tocón, brillo,
    /// la Madre que nace); lo que HACE en la pelea (el resorte del arco, el latigazo, qué la carga) es del jefe.
    ///
    /// Contrato para el código de la pelea:
    ///  * Encontrarlas: ArenaStalk.All / ArenaStalk.Get("N1"), o el GameObject "ArenaStalk_N1" (N1 N2 O1 O2 E1 E2 y M, la
    ///    Caña Madre). Están en [World]/Dynamic, fuera del lote estático, registradas en ZoneCulling.AddDynamic.
    ///  * Anclas (transforms, siguen al arco): PerchNode (arriba del nudo del posado: los pies), GripHigh (0.9 m más arriba:
    ///    la mano), ClimbGrip (2.2 m: la mano al trepar), BaseCut (0.9 m: el corte, el impacto y el sonido), Tip (la punta).
    ///    Todas sobre el eje del culmo, +Y a lo largo del culmo y +Z hacia el centro del claro (la Madre: hacia el sur, la
    ///    cámara). Para apoyar una mano o un pie en la superficie: CulmRadius(altura). Los ejes locales de los Seg_k son los
    ///    de Blender (Z a lo largo del culmo, debajo del giro de -90° de Stalk): no se los gira a mano, se usa SetBend.
    ///  * El arco lo pone SetBend(grados, dirección en el mundo, parejo): cada Seg_k gira grados * w_k alrededor del eje
    ///    horizontal perpendicular a la dirección, con w_k ∝ (k + 1) (dobla más arriba, como una caña de pescar) o parejo
    ///    (parejo = 1: la inclinación de 70° de la fase 2). No tiene dinámica propia: el resorte es del jefe.
    ///  * SetGlint (el nudo de la base, material Stalk_GlintBase: el blanco de "cortá acá"), SetCracked (la rajadura de la
    ///    fase 3), SetBroken (el tocón; BreakPiece es lo que se cae, para que el jefe lo anime), SetRise (la Madre nace del
    ///    piso), Occupied (la caña donde está posado no se disuelve con CameraOcclusion), KickChimes (los dos cascabeles del
    ///    posado son péndulos: ya se sacuden solos con el arco), ResetState (todo como al armarse, para los reintentos).
    /// La cápsula del pie va en la capa TransparentFX (no la usa nada más): Kaito y los enemigos chocan con ella (la matriz
    /// de capas choca con todo), pero los rayos al piso, que miran Default (el ensō de la base en CombatTelegraphs, el apoyo
    /// del jefe en Enemy), no la toman por suelo, el NavMesh no le hace un hueco y los barridos de CameraOcclusion (Ignore
    /// Raycast) no la confunden con el volumen que se disuelve (si no, la caña de Occupied se disolvía igual).
    /// </summary>
    [DefaultExecutionOrder(520)]   // después de CameraOcclusion (510): su Restore no le borra el brillo a la base
    public class ArenaStalk : MonoBehaviour
    {
        public const int SegmentCount = 8;
        public const string NamePrefix = "ArenaStalk_";

        /// <summary>Medidas por tipo (las mismas que KINDS de arena_stalks.py; su --check las compara con estas).</summary>
        struct KindData
        {
            public string kind;
            public float length, perch, grip, climb, r0, r1;
        }

        static readonly KindData[] Kinds =
        {
            new KindData { kind = "inner", length = 7.5f, perch = 4.4f, grip = 5.3f, climb = 2.2f, r0 = 0.15f, r1 = 0.07f },
            new KindData { kind = "north", length = 7.5f, perch = 4.0f, grip = 4.9f, climb = 2.2f, r0 = 0.15f, r1 = 0.07f },
            new KindData { kind = "outer", length = 8.5f, perch = 4.8f, grip = 5.7f, climb = 2.2f, r0 = 0.15f, r1 = 0.07f },
            new KindData { kind = "mother", length = 10f, perch = 5.0f, grip = 5.9f, climb = 2.2f, r0 = 0.21f, r1 = 0.10f },
        };

        /// <summary>Altura del nudo de la base (BaseCut) y alto de la cápsula del pie: con la caña inclinada 70° en la fase 2,
        /// el culmo se aparta menos de 0.2 m de ella a esa altura (más alta, Kaito chocaría con aire).</summary>
        public const float CutHeight = 0.9f, ColliderHeight = 1.4f;
        /// <summary>TransparentFX: la capa de la cápsula del pie (ver el resumen).</summary>
        public const int BaseLayer = 1;

        static readonly List<ArenaStalk> all = new List<ArenaStalk>(8);
        public static IReadOnlyList<ArenaStalk> All => all;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() => all.Clear();

        public static ArenaStalk Get(string id)
        {
            for (int i = 0; i < all.Count; i++) if (all[i].Id == id) return all[i];
            return null;
        }

        public string Id { get; private set; }
        public string Kind { get; private set; }
        public bool IsMother => Kind == "mother";
        public float Length { get; private set; }
        /// <summary>Alturas desde el pie con la caña recta (las anclas las siguen con el arco).</summary>
        public float PerchHeight { get; private set; }
        public float GripHeight { get; private set; }
        public float ClimbHeight { get; private set; }
        /// <summary>El pie de la caña en el mundo (el centro de la base, sobre el piso).</summary>
        public Vector3 Base => basePos;
        /// <summary>Horizontal, del centro del claro hacia el pie: la fase 2 inclina hacia acá. La Madre, en el centro, lo
        /// tiene al norte: así sus anclas miran al sur (a la cámara, del lado por el que se entra al claro).</summary>
        public Vector3 Outward { get; private set; }

        public Transform Stalk { get; private set; }
        public Transform PerchNode { get; private set; }
        public Transform GripHigh { get; private set; }
        public Transform ClimbGrip { get; private set; }
        public Transform BaseCut { get; private set; }
        public Transform Tip { get; private set; }
        public Transform Crown { get; private set; }
        public Transform Segment(int k) => segs[k];
        /// <summary>Lo que se cae cuando la caña se quiebra (Seg_01 y todo lo de arriba): el jefe lo anima entre
        /// SetBroken(true, true) y SetBroken(true, false).</summary>
        public Transform BreakPiece => segs[1];
        public Renderer GlintRenderer { get; private set; }
        public CapsuleCollider BaseCollider { get; private set; }

        public float BendDegrees { get; private set; }
        public Vector3 BendDirection { get; private set; }
        public bool Cracked { get; private set; }
        public bool Broken { get; private set; }
        public float Rise { get; private set; } = 1f;

        readonly Transform[] segs = new Transform[SegmentCount];
        /// <summary>Giro de reposo de cada tramo y el de su padre respecto de Stalk. El FBX trae el giro de ejes en las raíces
        /// (Stalk: -90° en X) y cada tramo con su transform local de Blender (Z a lo largo del culmo, giro identidad); con
        /// esto el arco no depende de cómo los deje el importador.</summary>
        readonly Quaternion[] rest = new Quaternion[SegmentCount], parentInv = new Quaternion[SegmentCount];
        float r0, r1;
        Vector3 basePos;
        Renderer seg0Renderer, stumpRenderer;
        readonly List<Renderer> crack = new List<Renderer>(2);
        readonly List<Renderer> renderers = new List<Renderer>(24);
        NavMeshObstacle obstacle;

        // ------------------------------------------------------------------ armado
        /// <summary>Lo llama WorldBuilder con el prop recién instanciado (yaw 0: los ejes del FBX son los del mundo).</summary>
        public static ArenaStalk Setup(GameObject go, string id, string kind, Vector3 arenaCenter)
        {
            go.name = NamePrefix + id;
            var s = go.AddComponent<ArenaStalk>();
            s.Init(id, kind, arenaCenter);
            all.Add(s);
            ZoneCulling.AddDynamic(go);
            return s;
        }

        void Init(string id, string kind, Vector3 arenaCenter)
        {
            Id = id;
            Kind = kind;
            var d = Kinds[0];
            bool known = false;
            foreach (var k in Kinds) if (k.kind == kind) { d = k; known = true; }
            if (!known) Debug.LogWarning($"[Nindo] {name}: tipo de caña '{kind}' desconocido, uso las medidas de 'inner'.");
            Length = d.length; PerchHeight = d.perch; GripHeight = d.grip; ClimbHeight = d.climb; r0 = d.r0; r1 = d.r1;
            basePos = transform.position;
            Vector3 o = (basePos - arenaCenter).Flat();
            Outward = o.sqrMagnitude > 0.01f ? o.normalized : Vector3.forward;

            Stalk = Find("Stalk");
            for (int k = 0; k < SegmentCount; k++) segs[k] = Find("Seg_" + k.ToString("00"));
            PerchNode = Find("PerchNode"); GripHigh = Find("GripHigh"); ClimbGrip = Find("ClimbGrip");
            BaseCut = Find("BaseCut"); Tip = Find("Tip"); Crown = Find("Crown");
            var glint = Find("GlintBase");
            GlintRenderer = glint != null ? glint.GetComponent<Renderer>() : null;
            seg0Renderer = segs[0] != null ? segs[0].GetComponent<Renderer>() : null;
            var stump = Find("Stump");
            stumpRenderer = stump != null ? stump.GetComponent<Renderer>() : null;
            foreach (var n in CrackNames)
            {
                var t = Find(n);
                var r = t != null ? t.GetComponent<Renderer>() : null;
                if (r != null) crack.Add(r);
            }
            GetComponentsInChildren(true, renderers);
            Quaternion acc = Quaternion.identity;
            for (int k = 0; k < SegmentCount; k++)
            {
                if (segs[k] == null) { Debug.LogWarning($"[Nindo] {name}: falta Seg_{k:00} (¿el FBX arena_stalk_{kind} está viejo?)"); continue; }
                rest[k] = segs[k].localRotation;
                parentInv[k] = Quaternion.Inverse(acc);
                acc *= rest[k];
            }
            // +Z de las anclas hacia el centro (el FBX es uno por tipo y cada caña lo usa con yaw 0)
            Vector3 inward = transform.InverseTransformDirection(-Outward);
            foreach (var a in new[] { PerchNode, GripHigh, ClimbGrip, BaseCut, Tip })
                if (a != null) a.rotation = transform.rotation * Quaternion.LookRotation(inward, Vector3.up);

            // la cápsula del pie (ver el resumen: TransparentFX; el manifest no le pone otra) y un obstáculo sin tallar
            // para que los agentes la rodeen
            var col = new GameObject("BaseCollider") { layer = BaseLayer };
            col.transform.SetParent(transform, false);
            BaseCollider = col.AddComponent<CapsuleCollider>();
            BaseCollider.radius = r0 + 0.04f;
            BaseCollider.height = ColliderHeight;
            BaseCollider.center = Vector3.up * (ColliderHeight * 0.5f);
            obstacle = gameObject.AddComponent<NavMeshObstacle>();
            obstacle.shape = NavMeshObstacleShape.Capsule;
            obstacle.radius = r0 + 0.1f;
            obstacle.height = ColliderHeight;
            obstacle.center = Vector3.up * (ColliderHeight * 0.5f);
            obstacle.carving = false;

            occluder = GetComponent<Occluder>();
            var vol = transform.Find("OccluderVolume");
            occVolume = vol != null ? vol.GetComponent<BoxCollider>() : null;
            SetupChimes();
            ResetState();
        }

        static readonly string[] CrackNames = { "Crack", "CrackUp" };

        Transform Find(string n) => FindDeep(transform, n);

        static Transform FindDeep(Transform t, string n)
        {
            if (t.name == n) return t;
            for (int i = 0; i < t.childCount; i++)
            {
                var r = FindDeep(t.GetChild(i), n);
                if (r != null) return r;
            }
            return null;
        }

        void OnDestroy() => all.Remove(this);

        /// <summary>Como al armarse: recta, entera, sin brillo, sin rajar; la Madre escondida bajo el piso.</summary>
        public void ResetState()
        {
            SetBroken(false);
            SetCracked(false);
            SetGlint(Color.black);
            SetBend(0f, Vector3.forward);
            Occupied = false;
            SetRise(IsMother ? 0f : 1f);
            ResetChimes();
        }

        /// <summary>Radio del culmo a esa altura desde el pie (afinado lineal; los nudos sobresalen ~15 %).</summary>
        public float CulmRadius(float height) => Mathf.Lerp(r0, r1, Mathf.Clamp01(height / Length));

        // ------------------------------------------------------------------ arco
        /// <summary>
        /// Dobla la caña 'degrees' hacia 'worldDirection' (se usa su parte horizontal; negativo = para el otro lado).
        /// evenness 0: w_k ∝ (k + 1) (la carga, el latigazo); 1: parejo (la inclinación de la fase 2, la copa sobre el borde).
        /// Con la carga de 30° el posado se corre 0.46 m y baja 4 cm (lo midió arena_stalks.py --check).
        /// </summary>
        public void SetBend(float degrees, Vector3 worldDirection, float evenness = 0f)
        {
            Vector3 dir = worldDirection.Flat();
            if (dir.sqrMagnitude < 1e-6f) { dir = Vector3.forward; degrees = 0f; }
            dir.Normalize();
            BendDegrees = degrees;
            BendDirection = dir;
            Vector3 axis = (Stalk != null ? Stalk : transform).InverseTransformDirection(Vector3.Cross(Vector3.up, dir));
            float e = Mathf.Clamp01(evenness);
            const float Sum = SegmentCount * (SegmentCount + 1) * 0.5f;
            for (int k = 0; k < SegmentCount; k++)
            {
                if (segs[k] == null) continue;
                float w = (1f - e) * (k + 1) / Sum + e / SegmentCount;
                // el mismo eje (de la raíz) en el espacio del padre en reposo: todos los tramos giran alrededor de él
                segs[k].localRotation = Quaternion.AngleAxis(degrees * w, parentInv[k] * axis) * rest[k];
            }
        }

        // ------------------------------------------------------------------ estados
        static readonly int EmissionId = Shader.PropertyToID("_EmissionColor");
        MaterialPropertyBlock mpb;
        Color glint;

        /// <summary>Brillo del nudo de la base (color HDR; negro lo apaga). Se vuelve a poner cada frame mientras brilla:
        /// Occluder.Restore limpia el bloque del renderer al terminar de disolverse.</summary>
        public void SetGlint(Color hdr)
        {
            glint = hdr;
            ApplyGlint();
        }

        void ApplyGlint()
        {
            if (GlintRenderer == null) return;
            mpb ??= new MaterialPropertyBlock();
            GlintRenderer.GetPropertyBlock(mpb);
            mpb.SetColor(EmissionId, glint);
            GlintRenderer.SetPropertyBlock(mpb);
        }

        bool Glowing => glint.r + glint.g + glint.b > 0.001f;

        /// <summary>La rajadura de la fase 3 (el tramo de abajo amarillea y se parte en zigzag). La Madre no tiene.</summary>
        public void SetCracked(bool on)
        {
            Cracked = on && crack.Count > 0;
            foreach (var r in crack) r.enabled = Cracked && !Broken;
        }

        /// <summary>
        /// Quebrada: queda el tocón (el tramo de abajo y la rajadura se apagan). pieceVisible: BreakPiece (Seg_01 y lo de
        /// arriba) sigue a la vista para que el jefe la tire (la quebradura cae hacia afuera, la tala hacia Kaito); con false
        /// se apaga. Sin tocón (la Madre) no hace nada: nunca se quiebra.
        /// </summary>
        public void SetBroken(bool broken, bool pieceVisible = false)
        {
            if (stumpRenderer == null) { Broken = false; return; }
            Broken = broken;
            stumpRenderer.enabled = broken && Rise > 0f;
            if (seg0Renderer != null) seg0Renderer.enabled = !broken && Rise > 0f;
            foreach (var r in crack) r.enabled = Cracked && !broken;
            if (segs[1] != null) segs[1].gameObject.SetActive(!broken || pieceVisible);
            volumeDirty = true;
        }

        /// <summary>
        /// La Madre que nace (0 = enterrada y apagada, 1 = de pie): el pie baja su largo y medio metro. Sin colisión hasta que
        /// está casi entera (si Kaito está encima, correrlo es del jefe). Las demás quedan en 1.
        /// </summary>
        public void SetRise(float t)
        {
            Rise = Mathf.Clamp01(t);
            transform.position = basePos + Vector3.down * ((1f - Rise) * (Length + 0.5f));
            bool on = Rise > 0f;
            foreach (var r in renderers)
            {
                if (r == null || r == stumpRenderer || crack.Contains(r)) continue;
                r.enabled = on && !(r == seg0Renderer && Broken);
            }
            if (stumpRenderer != null) stumpRenderer.enabled = on && Broken;
            foreach (var r in crack) r.enabled = on && Cracked && !Broken;
            bool solid = Rise >= 0.95f;
            if (BaseCollider != null) BaseCollider.enabled = solid;
            if (obstacle != null) obstacle.enabled = solid;
            volumeDirty = true;
        }

        // ------------------------------------------------------------------ cámara
        Occluder occluder;
        BoxCollider occVolume;
        bool occupied, volumeDirty;
        float volumeBend;
        Vector3 volumeDir;

        /// <summary>
        /// La caña donde está Chikuō no se disuelve (el diseño: "salvo la caña donde está posado"): con el culmo y la copa
        /// disueltos alrededor de él, el viejo quedaría flotando. Las demás sí, como el resto del bosque.
        /// </summary>
        public bool Occupied
        {
            get => occupied;
            set
            {
                occupied = value;
                if (occVolume != null) occVolume.enabled = !value && Rise > 0f;
                if (value && occluder != null) occluder.Restore();
            }
        }

        /// <summary>El volumen de Occluder se mide una sola vez (en su Awake): doblada 70° la copa queda 5 m afuera de él.
        /// Se vuelve a medir cuando el arco cambió más de 4° o 10° de dirección (el resorte del jefe llama SetBend en cada
        /// frame: medir siempre serían ~20 bounds por caña por frame para nada), o al nacer y al quebrarse.</summary>
        void RefreshVolume()
        {
            volumeDirty = false;
            volumeBend = BendDegrees;
            volumeDir = BendDirection;
            if (occVolume == null) return;
            occVolume.enabled = !occupied && Rise > 0f;
            bool any = false;
            Bounds b = default;
            foreach (var r in renderers)
            {
                if (r == null || !r.enabled || !r.gameObject.activeInHierarchy || !(r is MeshRenderer)) continue;
                if (!any) { b = r.bounds; any = true; } else b.Encapsulate(r.bounds);
            }
            if (!any) return;
            var vt = occVolume.transform;
            vt.SetPositionAndRotation(b.center, Quaternion.identity);
            Vector3 s = vt.lossyScale;
            // lo mismo que Occluder.Awake: un poco más chico que la caja, para no disolverse por rozarla
            occVolume.size = new Vector3(b.size.x / Mathf.Max(0.01f, s.x), b.size.y / Mathf.Max(0.01f, s.y), b.size.z / Mathf.Max(0.01f, s.z)) * 0.85f;
        }

        // ------------------------------------------------------------------ cascabeles
        /// <summary>Los cascabeles del posado: péndulos de verdad (cuelgan a plomo con la caña doblada y se sacuden con el
        /// latigazo). Largo del péndulo, pérdida por paso y tope de apertura respecto de la plomada. Pasos fijos de 1/60 s
        /// (como SpringChain) con el pivote interpolado: simulado con el latigazo del diseño (el posado se corre 0.46 m y
        /// oscila a 1.4 Hz), a 30, 60 o 144 fps llegan al tope y a los 2 s siguen a 24-25° (con el paso del frame, de 19 a 37°).</summary>
        const float ChimeLength = 0.2f, ChimeDamping = 0.035f, ChimeMaxAngle = 70f, ChimeStep = 1f / 60f;

        struct Chime
        {
            public Transform pivot;
            /// <summary>El tramo del nudo del posado (la junta) y el de abajo: el culmo por el que cuelga.</summary>
            public Transform joint, below;
            public Renderer r;
            public Vector3 pos, prev, anchor;
            /// <summary>El giro del pivote colgando a plomo (el del FBX con la caña recta): el péndulo gira desde ahí.</summary>
            public Quaternion hang;
        }

        Chime[] chimes = new Chime[0];
        Vector3 kick;
        float chimeAcc;

        void SetupChimes()
        {
            var list = new List<Chime>(5);
            foreach (var t in GetComponentsInChildren<Transform>(true))
            {
                if (!t.name.StartsWith("Chime") || t.name.EndsWith("_Mesh")) continue;
                var mesh = t.Find(t.name + "_Mesh");
                var joint = t.parent;
                list.Add(new Chime
                {
                    pivot = t, joint = joint, below = joint != null ? joint.parent : null,
                    r = mesh != null ? mesh.GetComponent<Renderer>() : null, hang = t.rotation,
                });
            }
            chimes = list.ToArray();
            chimeClear = CulmRadius(PerchHeight) + 0.05f;
        }

        /// <summary>Lo más cerca que un cascabel pasa del eje del culmo de abajo (su radio en el posado más el del tubo):
        /// con la caña inclinada 70° en la fase 2, el culmo de debajo del nudo se corre hacia el cascabel del lado de
        /// adentro y lo atravesaba.</summary>
        float chimeClear;

        void ResetChimes()
        {
            for (int i = 0; i < chimes.Length; i++)
            {
                chimes[i].anchor = chimes[i].pivot.position;
                chimes[i].pos = chimes[i].prev = chimes[i].anchor + Vector3.down * ChimeLength;
                chimes[i].pivot.rotation = chimes[i].hang;
            }
            kick = Vector3.zero;
            chimeAcc = 0f;
        }

        /// <summary>Un sacudón a los cascabeles (m/s, en el mundo): el estampado, el golpe al piso. El arco ya los mueve solo.</summary>
        public void KickChimes(Vector3 velocity) => kick += velocity;

        void TickChimes(float dt)
        {
            chimeAcc = Mathf.Min(chimeAcc + dt, ChimeStep * 4f);
            int n = Mathf.FloorToInt(chimeAcc / ChimeStep);
            if (n == 0) return;
            chimeAcc -= n * ChimeStep;
            Vector3 g = Physics.gravity * (ChimeStep * ChimeStep), push = kick * ChimeStep;
            for (int i = 0; i < chimes.Length; i++)
            {
                ref var c = ref chimes[i];
                Vector3 to = c.pivot.position, from = c.anchor;
                c.anchor = to;
                // un salto del pivote (reintento, la Madre que nace de golpe) no es un latigazo
                if ((c.pos - to).sqrMagnitude > 1f) { c.pos = c.prev = to + Vector3.down * ChimeLength; continue; }
                for (int k = 1; k <= n; k++)
                {
                    Vector3 a = Vector3.Lerp(from, to, k / (float)n);
                    Vector3 v = (c.pos - c.prev) * (1f - ChimeDamping) + (k == 1 ? push : Vector3.zero);
                    c.prev = c.pos;
                    Vector3 d = c.pos + v + g - a;
                    if (d.sqrMagnitude < 1e-8f) d = Vector3.down;
                    // tope respecto de la plomada (si no, un latigazo los daba vuelta por encima del nudo)
                    float ang = Vector3.Angle(Vector3.down, d);
                    if (ang > ChimeMaxAngle) d = Vector3.Slerp(Vector3.down, d.normalized, ChimeMaxAngle / ang);
                    c.pos = a + d.normalized * ChimeLength;
                    if (c.below != null) KeepOffCulm(ref c, a);
                }
                c.pivot.rotation = Quaternion.FromToRotation(Vector3.down, c.pos - to) * c.hang;
            }
            kick = Vector3.zero;
        }

        /// <summary>El cascabel no entra en el culmo de debajo del nudo (la recta de la junta al tramo de abajo).</summary>
        void KeepOffCulm(ref Chime c, Vector3 anchor)
        {
            Vector3 j = c.joint.position, down = c.below.position - j;
            float len = down.magnitude;
            if (len < 1e-4f) return;
            down /= len;
            Vector3 rel = c.pos - j;
            float along = Vector3.Dot(rel, down);
            if (along < -0.05f) return;              // por encima del nudo: ahí no hay culmo de este lado
            Vector3 radial = rel - down * along;
            if (radial.sqrMagnitude >= chimeClear * chimeClear) return;
            Vector3 side = anchor - j - down * Vector3.Dot(anchor - j, down);
            Vector3 dir = radial.sqrMagnitude > 1e-8f ? radial.normalized : side.normalized;
            c.pos = j + down * along + dir * chimeClear;
            c.pos = anchor + (c.pos - anchor).normalized * ChimeLength;
        }

        // ------------------------------------------------------------------ cada frame
        void LateUpdate()
        {
            if (Glowing) ApplyGlint();
            if (volumeDirty || Mathf.Abs(BendDegrees - volumeBend) > 4f || Vector3.Dot(BendDirection, volumeDir) < 0.985f)
                RefreshVolume();
            if (Rise <= 0f || chimes.Length == 0) return;
            bool seen = false;
            for (int i = 0; i < chimes.Length && !seen; i++) seen = chimes[i].r != null && chimes[i].r.isVisible;
            if (seen) TickChimes(Time.deltaTime);
            else ResetChimes();
        }
    }
}
