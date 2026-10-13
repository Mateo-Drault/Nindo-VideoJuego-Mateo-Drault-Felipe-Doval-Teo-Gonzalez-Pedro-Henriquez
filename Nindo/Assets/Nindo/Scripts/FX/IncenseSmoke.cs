using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Humo de incienso estilizado: una cinta fina (LineRenderer que mira a la cámara) que sube desde la brasa y se
    /// ondula con ondas que viajan hacia arriba y se abren con la altura; abajo es un hilo opaco y arriba se ensancha
    /// y se pierde. Es el trazo de pincel de una lámina, no una nube de partículas: con FXFactory.Smoke (manchas de
    /// 0.25-1.2 m) el santuario parecía en llamas. 16 puntos y una draw call por cinta; solo se mueve si se ve.
    /// </summary>
    [DefaultExecutionOrder(460)]   // después de IncenseHold (450): sale de la punta ya acomodada en la mano
    public class IncenseSmoke : MonoBehaviour
    {
        const int N = 16;
        /// <summary>Más allá de esto (m a la cámara) la cinta queda quieta: es un hilo de 1-3 px.</summary>
        const float AnimateDistance = 55f;
        /// <summary>
        /// Desde la cámara de juego (a ~24 m) el santuario rezado se distinguía del que no por un hilo gris de 1-2 px: de
        /// FarFrom a FarTo m de la cámara la cinta se ensancha hasta x(1 + FarWidth) y su alfa sube hasta x(1 + FarAlpha).
        /// En los planos cerca del rezo (2-6 m) queda como está, fina.
        /// </summary>
        const float FarFrom = 12f, FarTo = 22f, FarWidth = 0.8f, FarAlpha = 0.6f;
        static readonly int BaseColorId = Shader.PropertyToID("_BaseColor"), ColorId = Shader.PropertyToID("_Color");
        static readonly Color Tint = new Color(0.86f, 0.88f, 0.94f, 1f);
        static Material mat;
        static Texture2D strip;

        Transform source;
        Vector3 sourceOffset;
        LineRenderer lr;
        MaterialPropertyBlock mpb;
        readonly Vector3[] pts = new Vector3[N];
        float height, targetHeight, growSpeed = 1f;
        float alpha, targetAlpha = 1f, fadeSpeed = 1f, alphaMul;
        float seed, sway, baseWidth;
        bool posed;
        /// <summary>La fuente se mueve (el incienso en la mano): se rearma aunque no se vea.</summary>
        public bool moving;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { mat = null; strip = null; }

        /// <summary>
        /// Cinta que sale de 'source' (+ offset en espacio de mundo). 'width' = ancho arriba (m); 'opacity' multiplica el
        /// alfa (la segunda cinta, más tenue, da cuerpo sin ensuciar).
        /// </summary>
        public static IncenseSmoke Create(Transform parent, Transform source, Vector3 offset, float height, float width, float opacity, float seed)
        {
            var go = new GameObject("HumoDeIncienso");
            go.transform.SetParent(parent, false);
            var s = go.AddComponent<IncenseSmoke>();
            s.source = source; s.sourceOffset = offset;
            s.height = s.targetHeight = height;
            s.alphaMul = opacity;
            s.seed = seed;
            s.sway = 0.6f + 0.4f * Mathf.Repeat(seed * 0.37f, 1f);
            s.lr = go.AddComponent<LineRenderer>();
            s.lr.useWorldSpace = true;
            s.lr.positionCount = N;
            s.lr.alignment = LineAlignment.View;
            s.lr.textureMode = LineTextureMode.Stretch;
            s.lr.numCapVertices = 0; s.lr.numCornerVertices = 0;
            s.lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            s.lr.receiveShadows = false;
            s.lr.sharedMaterial = Material;
            // hilo de 1.5 cm en la brasa que se abre a 'width' arriba
            s.lr.widthMultiplier = s.baseWidth = width;
            s.lr.widthCurve = new AnimationCurve(new Keyframe(0f, 0.14f), new Keyframe(0.25f, 0.32f), new Keyframe(0.7f, 0.7f), new Keyframe(1f, 1f));
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                      new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(0.6f, 0.05f), new GradientAlphaKey(0.45f, 0.3f), new GradientAlphaKey(0.2f, 0.72f), new GradientAlphaKey(0f, 1f) });
            s.lr.colorGradient = g;
            s.mpb = new MaterialPropertyBlock();
            s.alpha = 0f;
            s.Pose(0f);
            return s;
        }

        static Material Material
        {
            get
            {
                if (mat != null) return mat;
                // el de las partículas (alfa, color por vértice) con una franja suave a lo ancho en vez del punto
                mat = new Material(FXMaterials.Alpha) { name = "Nindo_IncenseSmoke" };
                mat.SetTexture("_BaseMap", Strip);
                mat.SetTexture("_MainTex", Strip);
                return mat;
            }
        }

        /// <summary>Alfa 1 en el centro de la cinta y 0 en los bordes (u a lo largo, v a lo ancho).</summary>
        static Texture2D Strip
        {
            get
            {
                if (strip != null) return strip;
                const int H = 32;
                strip = new Texture2D(2, H, TextureFormat.RGBA32, false) { name = "Nindo_SmokeStrip", wrapMode = TextureWrapMode.Clamp };
                var px = new Color32[2 * H];
                for (int y = 0; y < H; y++)
                {
                    float v = Mathf.Abs((y + 0.5f) / H * 2f - 1f);
                    float a = Mathf.Pow(1f - v, 1.6f);
                    var c = new Color32(255, 255, 255, (byte)(a * 255f));
                    px[y * 2] = c; px[y * 2 + 1] = c;
                }
                strip.SetPixels32(px);
                strip.Apply(false, true);
                return strip;
            }
        }

        /// <summary>Lleva la columna a 'h' metros en 'seconds' (al dejar el incienso en el incensario crece hasta arriba).</summary>
        public void SetHeight(float h, float seconds)
        {
            targetHeight = h;
            growSpeed = seconds > 0f ? Mathf.Abs(h - height) / seconds : 1000f;
        }

        /// <summary>Aparece o se apaga con fundido.</summary>
        public void Fade(bool on, float seconds)
        {
            targetAlpha = on ? 1f : 0f;
            fadeSpeed = seconds > 0f ? 1f / seconds : 1000f;
            if (seconds <= 0f) alpha = targetAlpha;
        }

        public void SetSource(Transform t, Vector3 offset) { source = t; sourceOffset = offset; }

        void LateUpdate()
        {
            float dt = Time.deltaTime;
            height = Mathf.MoveTowards(height, targetHeight, growSpeed * dt);
            alpha = Mathf.MoveTowards(alpha, targetAlpha, fadeSpeed * dt);
            var cam = Game.Camera != null ? Game.Camera.Cam : null;
            float d2 = cam != null ? (cam.transform.position - transform.position).sqrMagnitude : 0f;
            bool near = cam == null || d2 < AnimateDistance * AnimateDistance;
            // quieta si no se ve y ya está armada (los bounds siguen siendo los de la última pose)
            if (!posed || (lr.isVisible && near) || moving) Pose(Time.time);
            float far = cam != null ? Mathf.InverseLerp(FarFrom, FarTo, Mathf.Sqrt(d2)) : 0f;
            lr.widthMultiplier = baseWidth * (1f + FarWidth * far);
            var c = Tint; c.a = Mathf.Min(1f, alpha * alphaMul * (1f + FarAlpha * far));
            mpb.SetColor(BaseColorId, c); mpb.SetColor(ColorId, c);
            lr.SetPropertyBlock(mpb);
            lr.enabled = alpha > 0.002f;
        }

        void Pose(float t)
        {
            posed = true;
            Vector3 b = (source != null ? source.position : transform.position) + sourceOffset;
            // el viento la inclina un poco hacia un lado que cambia despacio
            float wind = Mathf.Sin(t * 0.21f + seed) * 0.5f + Mathf.Sin(t * 0.13f + seed * 2.1f) * 0.5f;
            for (int i = 0; i < N; i++)
            {
                float s = i / (N - 1f);
                float h = s * height;
                // ondas que suben a ~0.3 m/s y se abren con la altura (abajo el hilo sale casi recto de la brasa)
                float amp = (0.012f + 0.12f * Mathf.Pow(s, 1.6f)) * sway;
                float x = amp * (Mathf.Sin(6.5f * h - 2.1f * t + seed) + 0.45f * Mathf.Sin(13.1f * h - 3.7f * t + seed * 1.7f));
                float z = amp * 0.7f * Mathf.Cos(5.2f * h - 1.6f * t + seed * 2.3f);
                x += wind * 0.14f * s * s;
                pts[i] = new Vector3(b.x + x, b.y + h, b.z + z);
            }
            lr.SetPositions(pts);
        }
    }

    /// <summary>
    /// Brasa en la punta del incienso: chispitas naranjas aditivas que nacen y se apagan en 0.1-0.3 s en una cajita
    /// de 4 cm (las tres varitas), así titila sola sin código por cuadro. Con el bloom es un punto cálido de 2-3 px
    /// desde la cámara de juego y una brasa viva en el plano cercano del rezo.
    /// </summary>
    public static class IncenseEmber
    {
        public static ParticleSystem Create(Transform parent, Vector3 localPos)
        {
            var ps = FXFactory.NewSystem("Brasa", parent);
            ps.transform.localPosition = localPos;
            var m = ps.main;
            m.loop = true; m.duration = 1f; m.playOnAwake = true;
            m.simulationSpace = ParticleSystemSimulationSpace.Local;
            m.startLifetime = new ParticleSystem.MinMaxCurve(0.1f, 0.3f);
            m.startSpeed = 0f;
            m.startSize = new ParticleSystem.MinMaxCurve(0.03f, 0.06f);
            m.startColor = new ParticleSystem.MinMaxGradient(new Color(1f, 0.42f, 0.12f, 1f), new Color(1f, 0.7f, 0.3f, 1f));
            m.maxParticles = 16;
            var em = ps.emission; em.rateOverTime = 26f;
            var sh = ps.shape; sh.enabled = true; sh.shapeType = ParticleSystemShapeType.Box; sh.scale = new Vector3(0.04f, 0.012f, 0.012f);
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(new Color(1f, 0.5f, 0.3f), 1f) },
                      new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 0.25f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            ps.Play();
            return ps;
        }
    }

    /// <summary>
    /// La llamita del incienso recién prendido (2-3 cm, amarilla con el pie naranja) que Kaito apaga abanicando con la
    /// mano en PrayIncense; sin ella los dos abanicos del clip apagaban nada. Lenguas que suben y se achican en 0.15-0.25 s
    /// (titila sola); Douse corta la emisión y las que quedan se consumen.
    /// </summary>
    public static class IncenseFlame
    {
        const string Name = "Llama";

        public static ParticleSystem Create(Transform tip)
        {
            var ps = FXFactory.NewSystem(Name, tip);
            ps.transform.localPosition = Vector3.up * 0.008f;
            var m = ps.main;
            m.loop = true; m.duration = 1f; m.playOnAwake = true;
            m.simulationSpace = ParticleSystemSimulationSpace.World;   // se inclina sola si la mano se mueve
            m.startLifetime = new ParticleSystem.MinMaxCurve(0.15f, 0.25f);
            m.startSpeed = new ParticleSystem.MinMaxCurve(0.08f, 0.14f);
            m.startSize = new ParticleSystem.MinMaxCurve(0.018f, 0.03f);
            m.startColor = new ParticleSystem.MinMaxGradient(new Color(1f, 0.86f, 0.42f, 1f), new Color(1f, 0.62f, 0.2f, 1f));
            m.gravityModifier = -0.05f;
            m.maxParticles = 14;
            var em = ps.emission; em.rateOverTime = 40f;
            var sh = ps.shape; sh.enabled = true; sh.shapeType = ParticleSystemShapeType.Cone; sh.angle = 6f; sh.radius = 0.004f;
            sh.rotation = new Vector3(-90f, 0f, 0f);   // el cono hacia arriba del manojo
            var size = ps.sizeOverLifetime; size.enabled = true;
            size.size = new ParticleSystem.MinMaxCurve(1f, new AnimationCurve(new Keyframe(0f, 0.7f), new Keyframe(0.3f, 1f), new Keyframe(1f, 0.1f)));
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(new Color(1f, 0.95f, 0.7f), 0f), new GradientColorKey(new Color(1f, 0.45f, 0.15f), 1f) },
                      new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 0.2f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            ps.Play();
            return ps;
        }

        /// <summary>Apaga la llama de esa punta (si tiene): deja de salir y se borra cuando se consumen las últimas lenguas.</summary>
        public static void Douse(Transform tip)
        {
            var f = tip != null ? tip.Find(Name) : null;
            if (f == null) return;
            var ps = f.GetComponent<ParticleSystem>();
            if (ps != null) ps.Stop(true, ParticleSystemStopBehavior.StopEmitting);
            // otro nombre: un segundo Douse no la encuentra
            f.name = Name + "Apagada";
            Object.Destroy(f.gameObject, 0.4f);
        }
    }
}
