using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// La media cinta de Kokuyō, la que colgaba del pomo de su espada (la otra mitad la sigue llevando en la hombrera):
    /// la misma tela que la bandana de Kaito. Un nudo y dos colas de ~0.45 m, cada una una cadena de puntos (verlet:
    /// gravedad, una brisa leve y el piso) dibujada como cinta de dos caras. Está tirada en el piso, en la mano de Kaito
    /// (el nudo en el puño, las colas cuelgan y se mecen) o bajando hasta el piso cuando Kaito se la devuelve
    /// (StoryDirector.Ending). Sin asignaciones por cuadro: una malla de 72 vértices que se rehace en el lugar.
    /// </summary>
    [DefaultExecutionOrder(450)]
    public class HalfRibbon : MonoBehaviour
    {
        const int N = 8;                         // puntos por cola
        const float Seg = 0.065f, Width = 0.085f, Lift = 0.004f;
        static readonly float[] TailScale = { 1f, 0.84f };
        static readonly Color Fallback = new Color(0.88f, 0.62f, 0.2f);

        enum Mode { Lying, Held, Falling }
        Mode mode;
        readonly Vector3[] p = new Vector3[2 * N], q = new Vector3[2 * N];
        Vector3[] verts, normals;
        Mesh mesh;
        Transform hand, knuckle, body;
        Vector3 anchor, fallFrom, fallTo, sideRef, holdFrom;
        float floorY, fallT, fallDur = 1f, holdT;

        /// <summary>El nudo (donde la agarra el puño).</summary>
        public Vector3 Knot => p[0];

        /// <summary>
        /// Tirada en el piso en 'floor' con las colas hacia 'lay' (abiertas en V). 'cloth' = el material de la tela
        /// (ClothFrom): la cinta es de dos caras en la malla, así sirve aunque el material descarte la cara de atrás.
        /// </summary>
        public static HalfRibbon Create(Vector3 floor, Vector3 lay, Material cloth)
        {
            var go = new GameObject("MediaCinta");
            var r = go.AddComponent<HalfRibbon>();
            r.Build(floor, lay.Flat().sqrMagnitude > 1e-4f ? lay.Flat().normalized : Vector3.forward, cloth);
            return r;
        }

        /// <summary>La tela de la cinta: la de la media cinta de Kokuyō o, si no, la de la bandana de Kaito.</summary>
        public static Material ClothFrom(Transform kokuyo, Transform kaito)
        {
            var m = FindMaterial(kokuyo, "Kokuyo_Ribbon");
            if (m == null) m = FindMaterial(kaito, CharacterFactory.BandanaSlot);
            if (m != null) return m;
            var lit = new Material(FXMaterials.FindShader("Universal Render Pipeline/Lit", "Standard")) { name = "Nindo_HalfRibbon" };
            FXMaterials.SetColor(lit, Fallback);
            return lit;
        }

        static Material FindMaterial(Transform root, string slot)
        {
            if (root == null) return null;
            foreach (var r in root.GetComponentsInChildren<Renderer>(true))
                foreach (var m in r.sharedMaterials)
                    if (m != null && m.name.StartsWith(slot)) return m;
            return null;
        }

        /// <summary>
        /// La media cinta del pomo de Kokuyō deja de verse (los huesos Tassel_1/2 de su espada se encogen a cero después
        /// del Animator): cayó al piso y es esta.
        /// </summary>
        public static void HideTassel(Transform kokuyo)
        {
            if (kokuyo == null) return;
            foreach (var t in kokuyo.GetComponentsInChildren<Transform>(true))
                if (t.name == "Tassel_1" && t.GetComponent<HiddenBone>() == null) t.gameObject.AddComponent<HiddenBone>();
        }

        void Build(Vector3 floor, Vector3 lay, Material cloth)
        {
            anchor = floor;
            floorY = floor.y;
            mode = Mode.Lying;
            sideRef = Vector3.up;
            for (int j = 0; j < 2; j++)
            {
                Vector3 d = Quaternion.AngleAxis(j == 0 ? -14f : 16f, Vector3.up) * lay;
                for (int i = 0; i < N; i++)
                {
                    // en el piso, con una ondulación apenas (tela tirada, no una regla)
                    Vector3 w = Vector3.Cross(Vector3.up, d) * (Mathf.Sin(i * 1.3f + j) * 0.012f * i / N);
                    p[j * N + i] = q[j * N + i] = floor + d * (Seg * TailScale[j] * i) + w + Vector3.up * Lift;
                }
            }
            mesh = new Mesh { name = "Nindo_HalfRibbon" };
            mesh.MarkDynamic();
            // por cola: borde izquierdo y derecho, cara de adelante y de atrás (4 x N); + el nudo (8)
            verts = new Vector3[2 * 4 * N + 8];
            normals = new Vector3[verts.Length];
            var uv = new Vector2[verts.Length];
            for (int i = 0; i < uv.Length; i++) uv[i] = new Vector2(0.5f, 0.5f);
            var tris = new int[2 * 2 * (N - 1) * 6 + 36];
            int t = 0;
            for (int j = 0; j < 2; j++)
            {
                int b = j * 4 * N;
                for (int i = 0; i < N - 1; i++)
                {
                    int l0 = b + i, r0 = b + N + i, l1 = l0 + 1, r1 = r0 + 1;
                    tris[t++] = l0; tris[t++] = l1; tris[t++] = r1; tris[t++] = l0; tris[t++] = r1; tris[t++] = r0;
                    int bl0 = b + 2 * N + i, br0 = b + 3 * N + i, bl1 = bl0 + 1, br1 = br0 + 1;
                    tris[t++] = bl0; tris[t++] = br1; tris[t++] = bl1; tris[t++] = bl0; tris[t++] = br0; tris[t++] = br1;
                }
            }
            // el nudo: un cubito de 3 cm
            int k0 = 2 * 4 * N;
            int[] box = { 0, 1, 2, 0, 2, 3, 4, 6, 5, 4, 7, 6, 0, 4, 5, 0, 5, 1, 1, 5, 6, 1, 6, 2, 2, 6, 7, 2, 7, 3, 3, 7, 4, 3, 4, 0 };
            for (int i = 0; i < box.Length; i++) tris[t++] = k0 + box[i];
            mesh.vertices = verts;
            mesh.uv = uv;
            mesh.triangles = tris;
            gameObject.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mr = gameObject.AddComponent<MeshRenderer>();
            mr.sharedMaterial = cloth;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            Rebuild();
        }

        /// <summary>El nudo pasa al puño de 'hand' (IncenseHold.Grip): las colas cuelgan.</summary>
        public void Hold(Transform hand, Transform body)
        {
            if (hand == null) return;
            this.hand = hand; this.body = body;
            knuckle = IncenseHold.Knuckle(hand);
            holdFrom = p[0];
            holdT = 0f;
            mode = Mode.Held;
        }

        /// <summary>Deja la mano y baja en 'seconds' hasta 'floor' (un arco suave, la tela se mece) y queda tendida.</summary>
        public void Release(Vector3 floor, float seconds)
        {
            fallFrom = p[0];
            fallTo = floor;
            floorY = Mathf.Min(floorY, floor.y);
            fallT = 0f;
            fallDur = Mathf.Max(0.2f, seconds);
            hand = null;
            mode = Mode.Falling;
        }

        void LateUpdate()
        {
            float dt = Mathf.Min(Time.deltaTime, 1f / 30f);
            if (dt <= 0f) return;
            Vector3 root;
            Vector3 wind = Vector3.zero;
            float t = Time.time;
            switch (mode)
            {
                case Mode.Held:
                {
                    root = hand != null ? IncenseHold.Grip(hand, knuckle, body) : p[0];
                    // del piso al puño en 0.15 s: la mano casi la toca en el cuadro en que la agarra, pero no exacto
                    holdT = Mathf.Min(1f, holdT + dt / 0.15f);
                    root = Vector3.Lerp(holdFrom, root, Mathf.SmoothStep(0f, 1f, holdT));
                    // la tela gira de a poco hasta mostrarle el ancho a la cámara (de canto, una cinta de 8 cm no se lee)
                    Vector3 toCam = Game.Camera != null ? (Game.Camera.transform.position - root).Flat() : Vector3.zero;
                    if (toCam.sqrMagnitude < 1e-4f) toCam = body != null ? body.forward : Vector3.forward;
                    sideRef = Vector3.Slerp(sideRef, toCam.normalized, dt * 4f);
                    wind = (body != null ? body.right : Vector3.right) * (Mathf.Sin(t * 2.3f) * 0.5f + Mathf.Sin(t * 5.1f) * 0.25f);
                    break;
                }
                case Mode.Falling:
                {
                    fallT += dt / fallDur;
                    float u = Mathf.Clamp01(fallT);
                    // baja como una hoja: avanza parejo y cae despacio al principio, más al final; se mece de lado
                    Vector3 side = Vector3.Cross(Vector3.up, (fallTo - fallFrom).Flat().normalized);
                    root = Vector3.Lerp(fallFrom, fallTo, u) + side * (Mathf.Sin(u * Mathf.PI * 2f) * 0.08f * (1f - u));
                    root.y = Mathf.Lerp(fallFrom.y, fallTo.y + Lift, u * u);
                    wind = side * Mathf.Sin(t * 3f) * 0.6f;
                    if (u >= 1f) { mode = Mode.Lying; anchor = fallTo + Vector3.up * Lift; }
                    sideRef = Vector3.Slerp(sideRef, Vector3.up, dt * 2f);
                    break;
                }
                default:
                    root = anchor;
                    sideRef = Vector3.Slerp(sideRef, Vector3.up, dt * 2f);
                    break;
            }
            Step(root, wind, dt);
            Rebuild();
        }

        void Step(Vector3 root, Vector3 wind, float dt)
        {
            Vector3 g = (Physics.gravity + wind) * (dt * dt);
            Vector3 split = Vector3.Cross(sideRef, Vector3.up);
            if (split.sqrMagnitude < 1e-4f) split = Vector3.right;
            split = split.normalized * 0.012f;
            // tela: el aire la frena mucho (0.9 por cuadro a 60 fps, igual a cualquier cuadro: si no, se mecía el triple a 30)
            float damp = Mathf.Pow(0.9f, dt * 60f);
            for (int j = 0; j < 2; j++)
            {
                int b = j * N;
                p[b] = q[b] = root + (j == 0 ? split : -split);
                for (int i = 1; i < N; i++)
                {
                    Vector3 v = (p[b + i] - q[b + i]) * damp;
                    q[b + i] = p[b + i];
                    p[b + i] += v + g;
                }
                float seg = Seg * TailScale[j];
                for (int it = 0; it < 3; it++)
                    for (int i = 1; i < N; i++)
                    {
                        Vector3 d = p[b + i] - p[b + i - 1];
                        float len = d.magnitude;
                        if (len < 1e-5f) continue;
                        // el primero queda clavado al nudo: el resto se acomoda
                        p[b + i] = p[b + i - 1] + d * (seg / len);
                        if (p[b + i].y < floorY + Lift)
                        {
                            p[b + i].y = floorY + Lift;
                            q[b + i] = Vector3.Lerp(q[b + i], p[b + i], 0.6f);   // roce con el piso
                        }
                    }
            }
        }

        void Rebuild()
        {
            Vector3 min = p[0], max = p[0];
            for (int j = 0; j < 2; j++)
            {
                int b = j * N, v = j * 4 * N;
                for (int i = 0; i < N; i++)
                {
                    Vector3 c = p[b + i];
                    Vector3 tan = (p[b + Mathf.Min(i + 1, N - 1)] - p[b + Mathf.Max(i - 1, 0)]);
                    if (tan.sqrMagnitude < 1e-8f) tan = Vector3.down;
                    tan.Normalize();
                    // el ancho de la cinta: perpendicular a su largo y a hacia dónde mira (de pie o tendida en el piso)
                    Vector3 s = Vector3.Cross(tan, sideRef);
                    if (s.sqrMagnitude < 1e-4f) s = Vector3.Cross(tan, Vector3.right);
                    s.Normalize();
                    Vector3 n = Vector3.Cross(s, tan).normalized;
                    // la punta cortada se abre un poco, como tela cortada
                    float w = Width * (0.5f + 0.06f * i / (N - 1f)) * (i == 0 ? 0.6f : 1f);
                    verts[v + i] = c + s * w; verts[v + N + i] = c - s * w;
                    verts[v + 2 * N + i] = verts[v + i]; verts[v + 3 * N + i] = verts[v + N + i];
                    normals[v + i] = normals[v + N + i] = n;
                    normals[v + 2 * N + i] = normals[v + 3 * N + i] = -n;
                    min = Vector3.Min(min, c); max = Vector3.Max(max, c);
                }
            }
            // el nudo
            Vector3 k = p[0];
            const float h = 0.016f;
            int k0 = 2 * 4 * N;
            for (int i = 0; i < 8; i++)
            {
                // anillo de abajo (0-3) y de arriba (4-7): -x-z, +x-z, +x+z, -x+z
                int c = i & 3;
                Vector3 o = new Vector3(c == 0 || c == 3 ? -h : h, i < 4 ? -h : h, c < 2 ? -h : h);
                verts[k0 + i] = k + o;
                normals[k0 + i] = o.normalized;
            }
            mesh.vertices = verts;
            mesh.normals = normals;
            mesh.bounds = new Bounds((min + max) * 0.5f, max - min + Vector3.one * 0.3f);
        }

        void OnDestroy() { if (mesh != null) Destroy(mesh); }

        /// <summary>Hueso encogido a cero después de que el Animator lo posa (la media cinta del pomo de Kokuyō).</summary>
        sealed class HiddenBone : MonoBehaviour
        {
            void LateUpdate() => transform.localScale = Vector3.zero;
        }
    }
}
