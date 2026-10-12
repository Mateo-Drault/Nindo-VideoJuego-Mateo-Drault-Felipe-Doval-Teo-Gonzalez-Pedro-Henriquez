using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Las "cuerdas de sombra" con que Kokuyō ata al abuelo al poste (prop binding_post). Tres vueltas tirantes que
    /// abrazan el poste y al abuelo arrodillado (a la altura de las muñecas cruzadas, de los codos y del pecho), dos
    /// vueltas chicas que le atan las muñecas, una cruz sobre el pecho y dos cabos colgando del nudo, en tubos facetados
    /// con Nindo/ShadowRope: violeta oscuro con hebras que brillan y pulsos que corren. Una luz violeta tenue lo baña (se
    /// lee desde la arena: "ahí está el abuelo"). Dissolve las deshace con un borde encendido y motas que suben cuando
    /// Kokuyō cae; Restore las vuelve a atar (reintentos).
    /// Las medidas salen de los huesos del abuelo en la pose de Bound (NPC.KneelBound la evalúa antes): cada vuelta es la
    /// envolvente del poste y del cuerpo a esa altura, así va pegada al pecho y a los brazos y de ahí tirante al poste.
    /// Antes salían de los bounds de la pose de bind (los brazos en cruz) y las vueltas flotaban 15-27 cm afuera.
    /// </summary>
    public class ShadowRopes : MonoBehaviour
    {
        static readonly int IdDissolve = Shader.PropertyToID("_Dissolve"), IdSeed = Shader.PropertyToID("_Seed");
        static readonly Color GlowColor = new Color(0.753f, 0.541f, 1f);     // #c08aff (glow_purple)

        public bool Bound { get; private set; }

        MeshRenderer rope;
        Mesh ropeMesh;
        Material mat;
        Light glow;
        ParticleSystem motes;
        readonly List<Vector3> path = new List<Vector3>();   // puntos de las cuerdas (para las motas al deshacerse)
        float dissolve, glowBase = 1.2f;
        Coroutine routine;

        /// <summary>Ata a 'captive' (el NPC del abuelo) contra 'post' (el binding_post). Devuelve null si falta algo.</summary>
        public static ShadowRopes Bind(Transform post, Transform captive, Transform parent)
        {
            if (post == null || captive == null) return null;
            var sh = Resources.Load<Shader>("Shaders/NindoShadowRope");
            if (sh == null || !sh.isSupported)
            {
                Debug.LogWarning("[Nindo] No compila Nindo/ShadowRope: el abuelo queda sin las cuerdas de sombra.");
                return null;
            }
            var go = new GameObject("CuerdasDeSombra");
            go.transform.SetParent(parent, false);
            var r = go.AddComponent<ShadowRopes>();
            r.Build(post, captive, sh);
            return r;
        }

        void Build(Transform post, Transform captive, Shader sh)
        {
            // alto del abuelo, para la luz (los renderers apagados, como el ninja del FBX, no cuentan)
            Bounds b = new Bounds(captive.position + Vector3.up * 0.7f, new Vector3(0.5f, 1.4f, 0.4f));
            bool any = false;
            foreach (var r in captive.GetComponentsInChildren<Renderer>())
            {
                if (!r.enabled || !(r is SkinnedMeshRenderer || r is MeshRenderer)) continue;
                if (!any) { b = r.bounds; any = true; } else b.Encapsulate(r.bounds);
            }
            float height = Mathf.Clamp(b.max.y - captive.position.y, 0.9f, 2.2f);
            Vector3 p = post.position, c = captive.position;
            Vector3 axis = (c - p); axis.y = 0f;
            float dist = axis.magnitude;
            axis = dist > 0.01f ? axis / dist : Vector3.back;
            Vector3 side = Vector3.Cross(Vector3.up, axis);
            var v = new List<Vector3>(); var uv = new List<Vector2>(); var t = new List<int>();
            BuildWraps(p, captive, axis, side, v, uv, t);

            ropeMesh = new Mesh { name = "CuerdasDeSombra" };
            ropeMesh.SetVertices(v); ropeMesh.SetUVs(0, uv); ropeMesh.SetTriangles(t, 0);
            ropeMesh.RecalculateNormals();
            ropeMesh.RecalculateBounds();
            var go = new GameObject("Cuerdas");
            go.transform.SetParent(transform, false);
            go.transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);   // la malla ya está en coordenadas de mundo
            go.AddComponent<MeshFilter>().sharedMesh = ropeMesh;
            rope = go.AddComponent<MeshRenderer>();
            mat = new Material(sh) { name = "Nindo_ShadowRope" };
            mat.SetFloat(IdSeed, Random.Range(0f, 50f));
            rope.sharedMaterial = mat;
            rope.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;

            var lg = new GameObject("LuzVioleta");
            lg.transform.SetParent(transform, false);
            lg.transform.position = c + Vector3.up * height * 0.65f + axis * 0.7f;
            glow = lg.AddComponent<Light>();
            glow.type = LightType.Point; glow.color = GlowColor; glow.range = 3.6f; glow.intensity = glowBase;
            glow.shadows = LightShadows.None;
            motes = MakeMotes();
            Bound = true;
        }

        // radio de la cuerda y lo que se separa de lo que envuelve; sección del poste (octógono de 0.3 m)
        const float RopeR = 0.027f, RopeGap = 0.03f, PostR = 0.16f;
        // medio fondo del tronco (del eje del cuerpo a la panza o al pecho) y grosor de un brazo
        const float WaistHalfD = 0.12f, ChestHalfD = 0.12f, LimbR = 0.05f;
        readonly List<Vector2> pts2 = new List<Vector2>(), hull = new List<Vector2>();

        /// <summary>
        /// Las vueltas, las ataduras de las muñecas, la cruz y los cabos. Los huesos del abuelo (Mano, Antebrazo, Brazo,
        /// Root) dicen dónde va cada cosa; sin ellos (otro modelo), las medidas de Bound en NPC.
        /// </summary>
        void BuildWraps(Vector3 p, Transform captive, Vector3 axis, Vector3 side, List<Vector3> v, List<Vector2> uv, List<int> t)
        {
            Vector3 c = captive.position;
            Transform hl = NPC.FindDeep(captive, "Mano.L"), hr = NPC.FindDeep(captive, "Mano.R");
            Transform el = NPC.FindDeep(captive, "Antebrazo.L"), er = NPC.FindDeep(captive, "Antebrazo.R");
            Transform sl = NPC.FindDeep(captive, "Brazo.L"), sr = NPC.FindDeep(captive, "Brazo.R");
            Transform root = NPC.FindDeep(captive, "Root");
            Vector3 up = Vector3.up, back = -axis;
            var loops = NPC.BoundRopeLoops;
            float hw = NPC.BoundRopeHalfWidth;
            Vector3 handL = hl != null ? hl.position : c + up * loops[0] + back * 0.13f + side * 0.02f;
            Vector3 handR = hr != null ? hr.position : c + up * loops[0] + back * 0.13f - side * 0.02f;
            Vector3 elbL = el != null ? el.position : c + up * loops[1] + back * 0.10f + side * (hw - LimbR);
            Vector3 elbR = er != null ? er.position : c + up * loops[1] + back * 0.10f - side * (hw - LimbR);
            Vector3 shL = sl != null ? sl.position : c + up * (loops[2] + 0.07f) + side * (hw - 0.04f);
            Vector3 shR = sr != null ? sr.position : c + up * (loops[2] + 0.07f) - side * (hw - 0.04f);
            Vector3 hip = root != null ? root.position : c + up * 0.16f + axis * 0.05f;
            Vector3 wrist = (handL + handR) * 0.5f, shoulders = (shL + shR) * 0.5f;
            float yW = wrist.y, yE = (elbL.y + elbR.y) * 0.5f, yC = shoulders.y - 0.07f;
            float shoulderHalf = Mathf.Abs(Vector3.Dot(shL - shR, side)) * 0.5f;

            // cada vuelta: la envolvente (vista desde arriba) del poste, del tronco a esa altura y de lo que sobresale (los
            // codos atrás, las manos cruzadas) con la holgura de la cuerda: pegada al cuerpo y tirante hasta el poste
            for (int k = 0; k < 3; k++)
            {
                float y = k == 0 ? yW : k == 1 ? yE : yC;
                Vector3 trunk = AxisAt(hip, shoulders, y);
                pts2.Clear();
                Circle(pts2, p, PostR + RopeGap, 12);
                float halfW = k == 2 ? shoulderHalf + LimbR + 0.02f : Mathf.Min(hw, shoulderHalf);
                Ellipse(pts2, trunk, side, axis, halfW + RopeGap, (k == 0 ? WaistHalfD : ChestHalfD) + RopeGap, 16);
                if (k == 0) Circle(pts2, wrist, LimbR + RopeGap, 8);
                if (k == 1) { Circle(pts2, elbL, LimbR + RopeGap, 8); Circle(pts2, elbR, LimbR + RopeGap, 8); }
                Hull(pts2, hull);
                var ring = Resample(hull, 44);
                var loop = new List<Vector3>(ring.Count);
                for (int i = 0; i < ring.Count; i++)
                    loop.Add(new Vector3(ring[i].x, y + 0.008f * Mathf.Sin(i * 0.9f + k), ring[i].y));
                Tube(v, uv, t, loop, RopeR, 6, true);
            }
            // las muñecas cruzadas atadas entre sí: dos vueltas chicas alrededor del cruce, de canto a los antebrazos
            Vector3 across = (handL - handR).sqrMagnitude > 1e-4f ? (handL - handR).normalized : side;
            Vector3 a1 = Vector3.Cross(across, up).normalized, a2 = Vector3.Cross(across, a1);
            for (int w = 0; w < 2; w++)
            {
                var ring = new List<Vector3>();
                Vector3 o = wrist + across * (w == 0 ? 0.02f : -0.02f);
                for (int i = 0; i < 10; i++)
                {
                    float a = i * Mathf.PI * 2f / 10f;
                    ring.Add(o + (a1 * Mathf.Cos(a) + a2 * Mathf.Sin(a)) * (LimbR + 0.005f));
                }
                Tube(v, uv, t, ring, 0.02f, 5, true);
            }
            // cruz sobre el pecho (de la vuelta de arriba a la del medio, por delante) y dos cabos colgando del nudo hasta
            // arriba de los muslos
            Vector3 chest = AxisAt(hip, shoulders, yC), mid = AxisAt(hip, shoulders, yE);
            float fC = ChestHalfD + RopeGap, w2 = shoulderHalf * 0.75f;
            Vector3 cl = chest + axis * fC + side * w2, cr = chest + axis * fC - side * w2;
            Vector3 ml = mid + axis * fC + side * w2, mr = mid + axis * fC - side * w2;
            Tube(v, uv, t, Line(cl, mr, axis * 0.03f), 0.024f, 5, false);
            Tube(v, uv, t, Line(cr, ml, axis * 0.035f), 0.024f, 5, false);
            Vector3 knot = (chest + mid) * 0.5f + axis * (fC + 0.02f) + side * 0.03f;
            float hang = Mathf.Max(0.05f, knot.y - (c.y + 0.26f));
            Tube(v, uv, t, new List<Vector3> { knot, knot + axis * 0.04f + side * 0.03f + Vector3.down * (0.4f * hang), knot + axis * 0.05f + side * 0.07f + Vector3.down * hang }, 0.022f, 5, false);
            Tube(v, uv, t, new List<Vector3> { knot, knot + axis * 0.05f - side * 0.02f + Vector3.down * (0.45f * hang), knot + axis * 0.03f + side * 0.01f + Vector3.down * (0.9f * hang) }, 0.022f, 5, false);
        }

        /// <summary>El eje del tronco (de la cadera al medio de los hombros) a la altura y.</summary>
        static Vector3 AxisAt(Vector3 hip, Vector3 shoulders, float y)
        {
            float k = Mathf.Abs(shoulders.y - hip.y) > 1e-3f ? (y - hip.y) / (shoulders.y - hip.y) : 0f;
            return Vector3.LerpUnclamped(hip, shoulders, k);
        }

        static void Circle(List<Vector2> o, Vector3 c, float r, int n)
        {
            for (int i = 0; i < n; i++)
            {
                float a = i * Mathf.PI * 2f / n;
                o.Add(new Vector2(c.x + Mathf.Cos(a) * r, c.z + Mathf.Sin(a) * r));
            }
        }

        static void Ellipse(List<Vector2> o, Vector3 c, Vector3 side, Vector3 fwd, float hw, float hd, int n)
        {
            for (int i = 0; i < n; i++)
            {
                float a = i * Mathf.PI * 2f / n;
                Vector3 q = c + side * (Mathf.Cos(a) * hw) + fwd * (Mathf.Sin(a) * hd);
                o.Add(new Vector2(q.x, q.z));
            }
        }

        /// <summary>Envolvente convexa de 'pts' (cadena monótona) en 'h', en sentido antihorario.</summary>
        static void Hull(List<Vector2> pts, List<Vector2> h)
        {
            pts.Sort((a, b) => a.x != b.x ? a.x.CompareTo(b.x) : a.y.CompareTo(b.y));
            h.Clear();
            for (int pass = 0; pass < 2; pass++)
            {
                int start = h.Count;
                for (int i = 0; i < pts.Count; i++)
                {
                    var q = pts[pass == 0 ? i : pts.Count - 1 - i];
                    while (h.Count >= start + 2 && Cross(h[h.Count - 2], h[h.Count - 1], q) <= 0f) h.RemoveAt(h.Count - 1);
                    h.Add(q);
                }
                h.RemoveAt(h.Count - 1);
            }
        }

        static float Cross(Vector2 o, Vector2 a, Vector2 b) => (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);

        /// <summary>n puntos parejos sobre el perímetro de un polígono cerrado (las facetas del tubo quedan del mismo largo).</summary>
        static List<Vector2> Resample(List<Vector2> poly, int n)
        {
            float per = 0f;
            for (int i = 0; i < poly.Count; i++) per += Vector2.Distance(poly[i], poly[(i + 1) % poly.Count]);
            var o = new List<Vector2>(n);
            int seg = 0;
            float acc = 0f;
            for (int k = 0; k < n; k++)
            {
                float d = per * k / n;
                while (seg < poly.Count - 1 && acc + Vector2.Distance(poly[seg], poly[seg + 1]) < d)
                {
                    acc += Vector2.Distance(poly[seg], poly[seg + 1]);
                    seg++;
                }
                Vector2 a = poly[seg], b = poly[(seg + 1) % poly.Count];
                float l = Vector2.Distance(a, b);
                o.Add(l > 1e-6f ? Vector2.Lerp(a, b, (d - acc) / l) : a);
            }
            return o;
        }

        static List<Vector3> Line(Vector3 a, Vector3 b, Vector3 bulge)
        {
            var l = new List<Vector3>();
            for (int i = 0; i <= 6; i++) { float s = i / 6f; l.Add(Vector3.Lerp(a, b, s) + bulge * Mathf.Sin(s * Mathf.PI)); }
            return l;
        }

        /// <summary>Tubo facetado a lo largo de una polilínea; uv.x = metros recorridos (las hebras y los pulsos).</summary>
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
                Vector3 n = k == 0 ? Vector3.Cross(tan, Mathf.Abs(tan.y) > 0.9f ? Vector3.right : Vector3.up).normalized
                                   : (prevN - tan * Vector3.Dot(prevN, tan)).normalized;
                prevN = n;
                Vector3 bn = Vector3.Cross(tan, n);
                if (k > 0) len += Vector3.Distance(pts[(k - 1) % m], pt);
                for (int i = 0; i < sides; i++)
                {
                    float a = i * Mathf.PI * 2f / sides;
                    v.Add(pt + (n * Mathf.Cos(a) + bn * Mathf.Sin(a)) * r);
                    uv.Add(new Vector2(len, i / (float)sides));
                }
                path.Add(pt);
            }
            for (int k = 0; k < rings - 1; k++)
                for (int i = 0; i < sides; i++)
                {
                    int a0 = start + k * sides + i, a1 = start + k * sides + (i + 1) % sides;
                    int b0 = a0 + sides, b1 = a1 + sides;
                    t.AddRange(new[] { a0, a1, b0, a1, b1, b0 });
                }
            if (!closed)
            {
                // tapas: un abanico en cada punta
                int s0 = start, s1 = start + (rings - 1) * sides;
                for (int i = 1; i < sides - 1; i++)
                {
                    t.AddRange(new[] { s0, s0 + i + 1, s0 + i });
                    t.AddRange(new[] { s1, s1 + i, s1 + i + 1 });
                }
            }
        }

        ParticleSystem MakeMotes()
        {
            var ps = FXFactory.NewSystem("MotasVioletas", transform);
            var m = ps.main;
            m.loop = false; m.playOnAwake = false;
            m.startLifetime = new ParticleSystem.MinMaxCurve(0.8f, 1.6f);
            m.startSpeed = new ParticleSystem.MinMaxCurve(0.1f, 0.4f);
            m.startSize = new ParticleSystem.MinMaxCurve(0.04f, 0.09f);
            m.startColor = new ParticleSystem.MinMaxGradient(GlowColor, new Color(0.95f, 0.85f, 1f));
            m.gravityModifier = -0.25f;
            m.maxParticles = 300;
            var noise = ps.noise; noise.enabled = true; noise.strength = 0.4f; noise.frequency = 1.1f;
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                      new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            return ps;
        }

        // ================================================================== API
        /// <summary>Las cuerdas se deshacen (borde encendido, motas que suben, la luz violeta se apaga): el abuelo está libre.</summary>
        public void Dissolve(float seconds = 1.6f)
        {
            if (!Bound) return;
            Bound = false;
            if (routine != null) StopCoroutine(routine);
            routine = StartCoroutine(DissolveRoutine(seconds));
            if (motes != null)
            {
                var ep = new ParticleSystem.EmitParams();
                for (int i = 0; i < path.Count; i += 2)
                {
                    ep.position = path[i];
                    ep.applyShapeToPosition = false;
                    motes.Emit(ep, 2);
                }
            }
            // en el abuelo (la raíz de las cuerdas es el centro de la arena, a 18 m)
            Game.Audio?.Play("shadow_rope_free", glow != null ? glow.transform.position : transform.position, 0.9f);
        }

        IEnumerator DissolveRoutine(float seconds)
        {
            float t = 0f;
            while (t < seconds)
            {
                t += Time.unscaledDeltaTime;
                dissolve = Mathf.Clamp01(t / seconds);
                yield return null;
            }
            dissolve = 1f;
            if (rope != null) rope.enabled = false;
            routine = null;
        }

        /// <summary>Atado de nuevo, ya (reintento antes de vencer a Kokuyō).</summary>
        public void Restore()
        {
            if (routine != null) { StopCoroutine(routine); routine = null; }
            dissolve = 0f;
            Bound = true;
            if (rope != null) rope.enabled = true;
            if (motes != null) motes.Clear();
        }

        void Update()
        {
            if (mat != null) mat.SetFloat(IdDissolve, dissolve);
            if (glow != null)
            {
                // late despacio, como algo que respira; se apaga con la disolución
                glow.intensity = glowBase * (0.8f + 0.2f * Mathf.Sin(Time.time * 1.7f)) * (1f - dissolve);
                glow.enabled = glow.intensity > 0.01f;
            }
        }

        void OnDestroy()
        {
            if (mat != null) Destroy(mat);
            if (ropeMesh != null) Destroy(ropeMesh);
        }
    }
}
