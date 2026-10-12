using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// La luz de la bandana que sale de Kaito y entra en el sello del portón: un haz dorado en arco (aditivo, con
    /// cuentas de luz que corren hacia el sello: se lee hacia dónde va la energía), dos hebras que se enroscan a su
    /// alrededor y motas que se desprenden. El frente avanza desde Kaito hasta el sello en 'travel' s llevando una luz
    /// que barre el piso; Stop lo apaga desde atrás, como si terminara de entrar. Sin asignaciones por cuadro.
    /// </summary>
    [DefaultExecutionOrder(470)]
    public class BandanaStream : MonoBehaviour
    {
        const int N = 24;
        static readonly int BaseMapSt = Shader.PropertyToID("_BaseMap_ST"), BaseColorId = Shader.PropertyToID("_BaseColor"), ColorId = Shader.PropertyToID("_Color");
        static readonly Color CoreColor = new Color(1f, 0.8f, 0.4f, 0.95f), StrandColor = new Color(1f, 0.95f, 0.78f, 0.9f);
        static Material beadMat;
        static Texture2D beads;

        Transform from;
        Vector3 fromOffset, to;
        LineRenderer core, strandA, strandB;
        ParticleSystem motes;
        Light headLight;
        MaterialPropertyBlock mpb;
        readonly Vector3[] pc = new Vector3[N], pa = new Vector3[N], pb = new Vector3[N];
        float t, head, tail, travel = 0.35f, fade = 1f, fadeSpeed, emitCarry;
        bool stopping;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { beadMat = null; beads = null; }

        /// <summary>Haz de 'from' (+offset de mundo) a 'to'. 'travel' = lo que tarda el frente en llegar.</summary>
        public static BandanaStream Play(Transform from, Vector3 fromOffset, Vector3 to, float travel)
        {
            var go = new GameObject("LuzDeLaBandana_Haz");
            var s = go.AddComponent<BandanaStream>();
            s.from = from; s.fromOffset = fromOffset; s.to = to; s.travel = Mathf.Max(0.05f, travel);
            s.mpb = new MaterialPropertyBlock();
            s.core = s.Line("Nucleo", BeadMaterial, 0.15f, LineTextureMode.Tile);
            s.core.widthCurve = new AnimationCurve(new Keyframe(0f, 0.35f), new Keyframe(0.15f, 1f), new Keyframe(0.85f, 1f), new Keyframe(1f, 0.6f));
            s.strandA = s.Line("HebraA", FXMaterials.Additive, 0.045f, LineTextureMode.Stretch);
            s.strandB = s.Line("HebraB", FXMaterials.Additive, 0.035f, LineTextureMode.Stretch);
            s.motes = s.MakeMotes();
            var lg = new GameObject("Luz");
            lg.transform.SetParent(go.transform, false);
            s.headLight = lg.AddComponent<Light>();
            s.headLight.type = LightType.Point; s.headLight.color = BandanaGlow.Gold; s.headLight.range = 4.5f; s.headLight.intensity = 0f;
            s.headLight.shadows = LightShadows.None;
            s.LateUpdate();
            return s;
        }

        /// <summary>Se apaga en 'seconds': la cola corre hasta el sello y todo se desvanece.</summary>
        public void Stop(float seconds)
        {
            if (stopping) return;
            stopping = true;
            fadeSpeed = 1f / Mathf.Max(0.05f, seconds);
        }

        LineRenderer Line(string name, Material m, float width, LineTextureMode mode)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            var lr = go.AddComponent<LineRenderer>();
            lr.useWorldSpace = true;
            lr.positionCount = N;
            lr.alignment = LineAlignment.View;
            lr.textureMode = mode;
            lr.numCapVertices = 2; lr.numCornerVertices = 0;
            lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            lr.receiveShadows = false;
            lr.sharedMaterial = m;
            lr.widthMultiplier = width;
            lr.startColor = lr.endColor = Color.white;
            return lr;
        }

        static Material BeadMaterial
        {
            get
            {
                if (beadMat != null) return beadMat;
                beadMat = new Material(FXMaterials.Additive) { name = "Nindo_BandanaBeam" };
                beadMat.SetTexture("_BaseMap", Beads);
                beadMat.SetTexture("_MainTex", Beads);
                return beadMat;
            }
        }

        /// <summary>Suave a lo ancho (v) y con dos cuentas de luz por metro a lo largo (u, se repite).</summary>
        static Texture2D Beads
        {
            get
            {
                if (beads != null) return beads;
                const int W = 64, H = 16;
                beads = new Texture2D(W, H, TextureFormat.RGBA32, false) { name = "Nindo_BeamBeads", wrapModeU = TextureWrapMode.Repeat, wrapModeV = TextureWrapMode.Clamp };
                var px = new Color32[W * H];
                for (int y = 0; y < H; y++)
                {
                    float v = Mathf.Abs((y + 0.5f) / H * 2f - 1f);
                    float across = Mathf.Pow(1f - v, 1.4f);
                    for (int x = 0; x < W; x++)
                    {
                        float u = (x + 0.5f) / W;
                        float bead = Mathf.Pow(0.5f + 0.5f * Mathf.Cos(u * Mathf.PI * 4f), 3f);
                        float a = across * (0.45f + 0.55f * bead);
                        px[y * W + x] = new Color32(255, 255, 255, (byte)(Mathf.Clamp01(a) * 255f));
                    }
                }
                beads.SetPixels32(px);
                beads.Apply(false, true);
                return beads;
            }
        }

        ParticleSystem MakeMotes()
        {
            var ps = FXFactory.NewSystem("Motas", transform);
            var m = ps.main;
            m.loop = true; m.playOnAwake = true;
            m.startLifetime = new ParticleSystem.MinMaxCurve(0.3f, 0.6f);
            m.startSpeed = 0f;
            m.startSize = new ParticleSystem.MinMaxCurve(0.04f, 0.09f);
            m.startColor = new ParticleSystem.MinMaxGradient(BandanaGlow.Gold, new Color(1f, 0.97f, 0.8f));
            m.gravityModifier = -0.1f;
            m.maxParticles = 200;
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                      new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            ps.Play();
            return ps;
        }

        static Vector3 Curve(Vector3 a, Vector3 c, Vector3 b, float u)
        {
            float w = 1f - u;
            return a * (w * w) + c * (2f * w * u) + b * (u * u);
        }

        /// <summary>El arco del haz (u 0-1, de a hacia b): lo usan otros que viajan con la luz (los sellos de la puerta).</summary>
        public static Vector3 Arc(Vector3 a, Vector3 b, float u) => Curve(a, Control(a, b), b, u);

        // arco hacia arriba (un cuarto de la distancia): la luz sube de la bandana y baja sobre el sello
        static Vector3 Control(Vector3 a, Vector3 b) => (a + b) * 0.5f + Vector3.up * Vector3.Distance(a, b) * 0.22f;

        void LateUpdate()
        {
            float dt = Time.deltaTime;
            t += dt;
            head = Mathf.Clamp01(t / travel);
            if (stopping)
            {
                tail = Mathf.MoveTowards(tail, 1f, dt * fadeSpeed);
                fade = Mathf.MoveTowards(fade, 0f, dt * fadeSpeed);
                if (fade <= 0f)
                {
                    // las motas que ya salieron terminan su vuelo (0.3-0.6 s): se sueltan del haz antes de borrarlo
                    if (motes != null)
                    {
                        motes.transform.SetParent(null, true);
                        motes.Stop(true, ParticleSystemStopBehavior.StopEmitting);
                        Destroy(motes.gameObject, motes.main.startLifetime.constantMax + 0.1f);
                    }
                    Destroy(gameObject);
                    return;
                }
            }
            Vector3 a = (from != null ? from.position : transform.position) + fromOffset;
            Vector3 c = Control(a, to);
            Vector3 dir = (to - a).normalized;
            Vector3 side = Vector3.Cross(Vector3.up, dir).normalized;
            Vector3 up = Vector3.Cross(dir, side);
            float span = Mathf.Max(0.001f, head - tail);
            for (int i = 0; i < N; i++)
            {
                float u = tail + span * i / (N - 1f);
                Vector3 p = Curve(a, c, to, u);
                pc[i] = p;
                // dos hebras enroscadas que se abren en el medio del recorrido y giran hacia el sello
                float r = 0.03f + 0.11f * Mathf.Sin(u * Mathf.PI);
                float w = u * 16f - t * 11f;
                pa[i] = p + (side * Mathf.Cos(w) + up * Mathf.Sin(w)) * r;
                pb[i] = p + (side * Mathf.Cos(w + Mathf.PI) + up * Mathf.Sin(w + Mathf.PI)) * r * 0.8f;
            }
            core.SetPositions(pc); strandA.SetPositions(pa); strandB.SetPositions(pb);
            // las cuentas de luz corren hacia el sello a 3 m/s y el haz respira
            float pulse = 0.85f + 0.15f * Mathf.Sin(t * 19f);
            mpb.SetVector(BaseMapSt, new Vector4(1f, 1f, -t * 3f, 0f));
            var cc = CoreColor; cc.a *= fade * pulse;
            mpb.SetColor(BaseColorId, cc); mpb.SetColor(ColorId, cc);
            core.SetPropertyBlock(mpb);
            mpb.SetVector(BaseMapSt, new Vector4(1f, 1f, 0f, 0f));
            var sc = StrandColor; sc.a *= fade;
            mpb.SetColor(BaseColorId, sc); mpb.SetColor(ColorId, sc);
            strandA.SetPropertyBlock(mpb);
            strandB.SetPropertyBlock(mpb);
            // motas que se desprenden a lo largo de lo que ya hay de haz
            emitCarry += dt * 70f * fade;
            var ep = new ParticleSystem.EmitParams { applyShapeToPosition = false };
            while (emitCarry >= 1f)
            {
                emitCarry -= 1f;
                float u = Random.Range(tail, head);
                ep.position = Curve(a, c, to, u) + Random.insideUnitSphere * 0.08f;
                ep.velocity = Random.insideUnitSphere * 0.35f + Vector3.up * 0.2f;
                motes.Emit(ep, 1);
            }
            headLight.transform.position = Curve(a, c, to, head);
            headLight.intensity = 3.2f * fade * pulse;
        }
    }
}
