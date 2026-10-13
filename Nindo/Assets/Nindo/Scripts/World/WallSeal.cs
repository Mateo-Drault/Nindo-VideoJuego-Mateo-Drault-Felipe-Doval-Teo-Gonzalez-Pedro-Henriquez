using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// El sello de sombra del portón de la muralla Kurokage: cuerdas de sombra (las mismas de Kokuyō que atan al
    /// abuelo, Nindo/ShadowRope) cruzadas en X sobre las dos hojas, una horizontal y un ensō de sombra en el centro,
    /// atadas a los pilares de piedra. Explica por qué el portón no se abre empujándolo: lo tejió el clan. Después de
    /// vencer a los guardias (enc_wall) Kaito se acerca, aparece "Abrir con la bandana" y la escena
    /// (StoryDirector.Wall) le manda la luz de la bandana: las hebras se vuelven doradas (Charge) y el sello se
    /// deshace con un borde de oro (Break). Las partidas con el portón ya abierto (wall_gate_open) no lo crean.
    /// Se ubica con las bisagras de las dos GateDoor de ese flag: sirve aunque el portón se mueva en el mapa.
    /// </summary>
    public class WallSeal : Interactable
    {
        static readonly int IdDissolve = Shader.PropertyToID("_Dissolve"), IdSeed = Shader.PropertyToID("_Seed"),
            IdColor = Shader.PropertyToID("_Color"), IdEdge = Shader.PropertyToID("_EdgeColor"), IdGlow = Shader.PropertyToID("_Glow");
        static readonly Color Violet = new Color(0.9f, 0.25f, 2.6f, 1f);           // el _Color del shader (HDR)
        static readonly Color GoldVein = new Color(2.6f, 1.7f, 0.35f, 1f);
        static readonly Color GoldEdge = new Color(4f, 2.8f, 0.8f, 1f);
        static readonly Color VioletLight = new Color(0.753f, 0.541f, 1f);          // #c08aff (glow_purple)
        /// <summary>Medidas del sello respecto del portón (wall_gate: vano de 3.4 x 3.6 m, pilares desde ±2.05).</summary>
        const float AnchorOut = 0.3f, TopY = 3.25f, BottomY = 0.4f, MidY = 1.75f, FrontOffset = 0.18f, RingR = 0.44f;
        /// <summary>Dónde se para Kaito (m delante de las hojas) y radio del aviso.</summary>
        public const float StandDistance = 2.6f;
        /// <summary>"enc_wall": se arma una vez (CanInteract corre en cada cuadro que Kaito busca qué usar).</summary>
        static readonly string GuardsDownFlag = Flags.Encounter("wall");

        Vector3 groundCenter, front, along;
        float halfWidth;
        MeshRenderer rope;
        Mesh mesh;
        Material mat;
        Light glow;
        ParticleSystem motes;
        readonly List<Vector3> path = new List<Vector3>();
        float charge, dissolve, checkTimer;
        bool near;

        public bool Sealed { get; private set; } = true;
        /// <summary>Centro del ensō (donde llega la luz de la bandana).</summary>
        public Vector3 SealCenter => groundCenter + Vector3.up * MidY + front * (FrontOffset + 0.05f);
        public Vector3 GroundCenter => groundCenter;
        /// <summary>De las hojas hacia donde viene Kaito (el sur del portón).</summary>
        public Vector3 Front => front;
        public Vector3 Along => along;
        public Vector3 StandPoint => groundCenter + front * StandDistance;

        /// <summary>Lo arma sobre el portón de la muralla si sigue cerrado. Null si el mapa no tiene ese portón.</summary>
        public static WallSeal Create(Transform parent)
        {
            if (Game.Save.HasFlag(Flags.WallGateOpen)) return null;
            var sh = Resources.Load<Shader>("Shaders/NindoShadowRope");
            if (sh == null || !sh.isSupported) { Debug.LogWarning("[Nindo] No compila Nindo/ShadowRope: el portón de la muralla queda sin su sello."); }
            Transform a = null, b = null;
            foreach (var d in FindObjectsByType<GateDoor>(FindObjectsSortMode.None))
            {
                if (d.openFlag != Flags.WallGateOpen) continue;
                if (a == null) a = d.transform; else if (b == null) b = d.transform;
            }
            if (a == null || b == null) return null;
            var go = new GameObject("SelloDeSombra");
            go.transform.SetParent(parent, false);
            var s = go.AddComponent<WallSeal>();
            s.Build(a.position, b.position, sh);
            return s;
        }

        void Awake()
        {
            prompt = "Abrir con la bandana";
            radius = 3.2f;
            promptHeight = 2.4f;
        }

        // solo del lado de afuera (del jardín no tiene sentido, y la escena lo llevaría a través de las hojas)
        public override bool CanInteract => Sealed && Game.Save.HasFlag(GuardsDownFlag) && !Game.Save.HasFlag(Flags.WallGateOpen)
                                            && (Game.Combat == null || !Game.Combat.InCombat)
                                            && Game.Player != null && Vector3.Dot(Game.Player.transform.position - groundCenter, front) > 0.3f;

        public override void Interact(PlayerController p) => Game.Story?.OpenWallSeal(this);

        // ================================================================== malla
        void Build(Vector3 hingeA, Vector3 hingeB, Shader sh)
        {
            groundCenter = (hingeA + hingeB) * 0.5f;
            along = (hingeB - hingeA); along.y = 0f;
            halfWidth = along.magnitude * 0.5f;
            along = along.sqrMagnitude > 0.0001f ? along.normalized : Vector3.right;
            front = Vector3.Cross(Vector3.up, along);
            // el frente es el lado del que vienen los guardias y Kaito (el encuentro "wall" está al sur)
            var guards = Encounter.Get("wall");
            Vector3 toward = guards != null ? guards.transform.position - groundCenter : Vector3.back;
            if (Vector3.Dot(front, toward) < 0f) front = -front;
            // el aviso de interactuar va en el suelo delante del portón (FindBest mide desde acá)
            transform.position = groundCenter + front * 1.4f;

            float x0 = halfWidth + AnchorOut;
            Vector3 P(float x, float y, float bulge = 0f) => groundCenter + along * x + Vector3.up * y + front * (FrontOffset + bulge);
            var v = new List<Vector3>(); var uv = new List<Vector2>(); var t = new List<int>();
            // la X: de las esquinas de arriba a las de abajo, abultada hacia afuera en el medio (tensa contra las hojas)
            Tube(v, uv, t, Curve(P(-x0, TopY), P(x0, BottomY), front * 0.07f, Vector3.down * 0.06f, 12), 0.05f, 6, false);
            Tube(v, uv, t, Curve(P(x0, TopY), P(-x0, BottomY), front * 0.07f, Vector3.down * 0.06f, 12), 0.05f, 6, false);
            // la horizontal, un poco caída
            Tube(v, uv, t, Curve(P(-x0, MidY + 0.1f), P(x0, MidY + 0.1f), front * 0.05f, Vector3.down * 0.16f, 12), 0.042f, 6, false);
            // vueltas en los pilares: un nudo grueso en cada punta
            foreach (var y in new[] { TopY, BottomY, MidY + 0.1f })
                for (int s = -1; s <= 1; s += 2)
                    Tube(v, uv, t, Ring(P(s * x0, y, 0.02f), 0.075f, 10, 0f, 1f), 0.035f, 5, true);
            // el ensō de sombra en el cruce: un trazo de 330° (un ensō no se cierra) y un anillo interior
            Tube(v, uv, t, Ring(P(0f, MidY, 0.12f), RingR, 26, 0.35f, 0.92f), 0.06f, 6, false);
            Tube(v, uv, t, Ring(P(0f, MidY, 0.14f), RingR * 0.62f, 18, 0f, 1f), 0.034f, 5, true);

            mesh = new Mesh { name = "SelloDeSombra" };
            mesh.SetVertices(v); mesh.SetUVs(0, uv); mesh.SetTriangles(t, 0);
            mesh.RecalculateNormals();
            mesh.RecalculateBounds();
            var ropeGo = new GameObject("Cuerdas");
            ropeGo.transform.SetParent(transform, false);
            ropeGo.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);   // malla en coordenadas de mundo
            ropeGo.AddComponent<MeshFilter>().sharedMesh = mesh;
            rope = ropeGo.AddComponent<MeshRenderer>();
            rope.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            if (sh != null && sh.isSupported)
            {
                mat = new Material(sh) { name = "Nindo_WallSeal" };
                mat.SetFloat(IdSeed, 13.7f);
                rope.sharedMaterial = mat;
            }
            else rope.sharedMaterial = FXMaterials.Flash;

            var lg = new GameObject("LuzVioleta");
            lg.transform.SetParent(transform, false);
            lg.transform.position = SealCenter + front * 0.9f;
            glow = lg.AddComponent<Light>();
            glow.type = LightType.Point; glow.color = VioletLight; glow.range = 4.5f; glow.intensity = 0f;
            glow.shadows = LightShadows.None;
            glow.enabled = false;
            motes = MakeMotes();
        }

        /// <summary>Curva de a a b (cuadrática): 'bulge' empuja el medio hacia afuera y 'sag' lo hace caer.</summary>
        static List<Vector3> Curve(Vector3 a, Vector3 b, Vector3 bulge, Vector3 sag, int n)
        {
            var l = new List<Vector3>(n + 1);
            for (int i = 0; i <= n; i++)
            {
                float s = i / (float)n, k = Mathf.Sin(s * Mathf.PI);
                l.Add(Vector3.Lerp(a, b, s) + (bulge + sag) * k);
            }
            return l;
        }

        /// <summary>Arco en el plano de las hojas, de la fracción f0 a f1 de la vuelta.</summary>
        List<Vector3> Ring(Vector3 c, float r, int segs, float f0, float f1)
        {
            var l = new List<Vector3>(segs + 1);
            int count = Mathf.Approximately(f1 - f0, 1f) ? segs : segs + 1;
            for (int i = 0; i < count; i++)
            {
                float a = Mathf.Lerp(f0, f1, i / (float)segs) * Mathf.PI * 2f + 0.6f;
                l.Add(c + (along * Mathf.Cos(a) + Vector3.up * Mathf.Sin(a)) * r);
            }
            return l;
        }

        /// <summary>Tubo facetado a lo largo de una polilínea; uv.x = metros recorridos (hebras y pulsos del shader).</summary>
        void Tube(List<Vector3> v, List<Vector2> uv, List<int> t, List<Vector3> pts, float r, int sides, bool closed)
        {
            int m = pts.Count;
            int rings = closed ? m + 1 : m;
            int start = v.Count;
            float len = 0f;
            Vector3 prevN = Vector3.zero;
            for (int k = 0; k < rings; k++)
            {
                Vector3 pt = pts[k % m];
                Vector3 tan = closed ? (pts[(k + 1) % m] - pts[(k - 1 + m) % m]) : (pts[Mathf.Min(k + 1, m - 1)] - pts[Mathf.Max(k - 1, 0)]);
                tan.Normalize();
                Vector3 nrm = k == 0 ? Vector3.Cross(tan, Mathf.Abs(tan.y) > 0.9f ? Vector3.right : Vector3.up).normalized
                                     : (prevN - tan * Vector3.Dot(prevN, tan)).normalized;
                prevN = nrm;
                Vector3 bn = Vector3.Cross(tan, nrm);
                if (k > 0) len += Vector3.Distance(pts[(k - 1) % m], pt);
                // las puntas del ensō se afinan como un trazo de pincel
                float taper = closed ? 1f : Mathf.Lerp(0.45f, 1f, Mathf.Clamp01(Mathf.Min(k, rings - 1 - k) / 3f));
                for (int i = 0; i < sides; i++)
                {
                    float a = i * Mathf.PI * 2f / sides;
                    v.Add(pt + (nrm * Mathf.Cos(a) + bn * Mathf.Sin(a)) * r * taper);
                    uv.Add(new Vector2(len, i / (float)sides));
                }
                path.Add(pt);
            }
            for (int k = 0; k < rings - 1; k++)
                for (int i = 0; i < sides; i++)
                {
                    int a0 = start + k * sides + i, a1 = start + k * sides + (i + 1) % sides;
                    int b0 = a0 + sides, b1 = a1 + sides;
                    t.Add(a0); t.Add(a1); t.Add(b0); t.Add(a1); t.Add(b1); t.Add(b0);
                }
            if (!closed)
            {
                int s0 = start, s1 = start + (rings - 1) * sides;
                for (int i = 1; i < sides - 1; i++)
                {
                    t.Add(s0); t.Add(s0 + i + 1); t.Add(s0 + i);
                    t.Add(s1); t.Add(s1 + i); t.Add(s1 + i + 1);
                }
            }
        }

        ParticleSystem MakeMotes()
        {
            var ps = FXFactory.NewSystem("MotasDelSello", transform);
            var m = ps.main;
            m.loop = false; m.playOnAwake = false;
            m.startLifetime = new ParticleSystem.MinMaxCurve(0.8f, 1.8f);
            m.startSpeed = new ParticleSystem.MinMaxCurve(0.2f, 0.9f);
            m.startSize = new ParticleSystem.MinMaxCurve(0.04f, 0.1f);
            m.startColor = new ParticleSystem.MinMaxGradient(BandanaGlow.Gold, new Color(1f, 0.95f, 0.75f));
            m.gravityModifier = -0.2f;
            m.maxParticles = 400;
            var noise = ps.noise; noise.enabled = true; noise.strength = 0.5f; noise.frequency = 1.1f;
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                      new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            return ps;
        }

        // ================================================================== escena
        /// <summary>0 = sombra violeta; 1 = la luz de la bandana la llenó: hebras doradas que brillan el doble.</summary>
        public void Charge(float k) => charge = Mathf.Clamp01(k);

        /// <summary>Se deshace en 'seconds' con un borde de oro; las motas doradas suben de todo el recorrido.</summary>
        public void Break(float seconds)
        {
            if (!Sealed) return;
            Sealed = false;
            StartCoroutine(BreakRoutine(seconds));
            if (motes != null)
            {
                var ep = new ParticleSystem.EmitParams { applyShapeToPosition = false };
                for (int i = 0; i < path.Count; i += 2) { ep.position = path[i]; motes.Emit(ep, 2); }
            }
        }

        IEnumerator BreakRoutine(float seconds)
        {
            float t = 0f;
            while (t < seconds)
            {
                t += Time.deltaTime;
                dissolve = Mathf.Clamp01(t / seconds);
                yield return null;
            }
            dissolve = 1f;
            if (rope != null) rope.enabled = false;
            yield return new WaitForSeconds(2f);   // las motas terminan de subir
            Destroy(gameObject);
        }

        void Update()
        {
            checkTimer -= Time.unscaledDeltaTime;
            if (checkTimer <= 0f)
            {
                checkTimer = 0.5f;
                var p = Game.Player;
                near = p != null && (p.transform.position - groundCenter).sqrMagnitude < 40f * 40f;
            }
            if (mat != null)
            {
                mat.SetFloat(IdDissolve, dissolve);
                mat.SetColor(IdColor, Color.Lerp(Violet, GoldVein, charge));
                mat.SetColor(IdEdge, GoldEdge);
                // la luz que entra la hace latir: más brillo y más rápido
                mat.SetFloat(IdGlow, 1f + charge * (0.8f + 0.4f * Mathf.Sin(Time.time * 14f)));
            }
            if (glow != null)
            {
                float i = (1.1f * (0.8f + 0.2f * Mathf.Sin(Time.time * 1.7f)) + charge * 1.5f) * (1f - dissolve);
                glow.color = Color.Lerp(VioletLight, BandanaGlow.Gold, charge);
                glow.intensity = i;
                bool on = near && i > 0.01f;
                if (glow.enabled != on) glow.enabled = on;
            }
        }

        void OnDestroy()
        {
            if (mat != null) Destroy(mat);
            if (mesh != null) Destroy(mesh);
        }
    }
}
