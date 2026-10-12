using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// El frente de una onda roja por el piso (la onda de qi de Chikuō): un aro de ancho fijo (0.6 m) que se abre al ritmo
    /// del golpe (el RingWave del juego se abre frenando y se afina con el radio: no decía dónde estaba el frente). Hold
    /// lo deja quieto de otro color (el aro de jade de la postura del bambú).
    /// </summary>
    public class ShockRing : MonoBehaviour
    {
        const int N = 64;
        float width = 0.6f;
        Mesh mesh;
        MeshRenderer mr;
        MaterialPropertyBlock mpb;
        readonly Vector3[] verts = new Vector3[N * 2];
        float lastR = -1f;

        public static ShockRing Create(float width = 0.6f)
        {
            var go = new GameObject("OndaRoja");
            var r = go.AddComponent<ShockRing>();
            r.width = width;
            r.mesh = new Mesh { name = "OndaRoja" };
            r.mesh.MarkDynamic();
            var tri = new int[N * 6];
            var uv = new Vector2[N * 2];
            for (int i = 0; i < N; i++)
            {
                int j = (i + 1) % N;
                tri[i * 6] = i * 2; tri[i * 6 + 1] = j * 2; tri[i * 6 + 2] = i * 2 + 1;
                tri[i * 6 + 3] = i * 2 + 1; tri[i * 6 + 4] = j * 2; tri[i * 6 + 5] = j * 2 + 1;
                uv[i * 2] = new Vector2(0.5f, 0.5f); uv[i * 2 + 1] = new Vector2(0.5f, 0.5f);
            }
            r.Fill(1f);
            r.mesh.uv = uv;
            r.mesh.triangles = tri;
            r.mesh.bounds = new Bounds(Vector3.zero, new Vector3(40f, 2f, 40f));
            go.AddComponent<MeshFilter>().sharedMesh = r.mesh;
            r.mr = go.AddComponent<MeshRenderer>();
            r.mr.sharedMaterial = FXMaterials.Additive;
            r.mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.mr.receiveShadows = false;
            r.mpb = new MaterialPropertyBlock();
            go.SetActive(false);
            return r;
        }

        void Fill(float radius)
        {
            float rin = Mathf.Max(0f, radius - width);
            for (int i = 0; i < N; i++)
            {
                float a = i / (float)N * Mathf.PI * 2f;
                Vector3 d = new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a));
                verts[i * 2] = d * rin; verts[i * 2 + 1] = d * radius;
            }
            mesh.vertices = verts;
        }

        public void Show(Vector3 center)
        {
            transform.position = center + Vector3.up * 0.08f;
            lastR = -1f;
            gameObject.SetActive(true);
        }

        public void Tick(float radius, float max)
        {
            if (Mathf.Abs(radius - lastR) > 0.01f) { Fill(radius); lastR = radius; }
            // rojo del imparable, aclarándose en el frente; se apaga en el último metro
            float fade = Mathf.Clamp01((max - radius) / 1f);
            Color c = Color.Lerp(TellStyle.Crimson, new Color(1f, 0.75f, 0.45f), 0.35f) * 1.6f;
            c.a = 0.85f * fade;
            mpb.SetColor("_BaseColor", c); mpb.SetColor("_Color", c);
            mr.SetPropertyBlock(mpb);
            if (Time.frameCount % 3 == 0)
            {
                // polvo levantado por el frente (de a pocos puntos por frame: no un estallido)
                float a = Random.value * Mathf.PI * 2f;
                Game.FX?.Dust(transform.position + new Vector3(Mathf.Cos(a), 0f, Mathf.Sin(a)) * radius, 0.7f);
            }
        }

        /// <summary>Aro quieto de un color, sin polvo.</summary>
        public void Hold(float radius, Color c)
        {
            if (Mathf.Abs(radius - lastR) > 0.01f) { Fill(radius); lastR = radius; }
            mpb.SetColor("_BaseColor", c); mpb.SetColor("_Color", c);
            mr.SetPropertyBlock(mpb);
        }

        public void Hide() => gameObject.SetActive(false);

        void OnDestroy() { if (mesh != null) Destroy(mesh); }
    }
}
