using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Ventana del parry de Kaito: una LÍNEA DE ACERO a lo largo de su guardia (shader Nindo/ParrySteel, modo 0). Antes
    /// era una media luna del mismo trazo de pincel que el aviso ensō de los enemigos y se confundía con otro aviso
    /// (pedido 27); el nombre de la clase quedó por compatibilidad (FXManager.Crescent, PlayerController). Recta,
    /// filosa y a la altura del pecho: se lee como la hoja cruzada delante de Kaito, que el clip ParryStance casi no
    /// muestra desde la cámara alta. Acá:
    ///  * dorada mientras la ventana es PERFECTA, acero después;
    ///  * se acorta hacia el centro al ritmo de la ventana: queda en un tercio justo cuando se cierra;
    ///  * si desvía, destella blanca y se apaga (el destello del choque lo pone FX/ParrySteel); si no llegó nada,
    ///    se parte al medio y se cae en gris (con el "fiu" del parry al aire); si lo cortan, se apaga.
    /// Una cinta de cuatro vértices que mira a la cámara, un MaterialPropertyBlock por frame.
    /// </summary>
    public class ParryCrescent : MonoBehaviour
    {
        enum End { None, Success, Whiff, Cancel }

        [Tooltip("Medio largo de la línea al abrir la ventana (m)")] public float halfLength = 0.62f;
        [Tooltip("Al cerrarse la ventana queda esta fracción del largo")] public float minLength = 0.35f;
        [Tooltip("Altura sobre los pies de Kaito (m): a la de la hoja en guardia")] public float height = 1.0f;
        [Tooltip("Adelante de Kaito (m)")] public float ahead = 0.45f;
        [Tooltip("Medio ancho del filo (m); nunca menos de 1.6 px")] public float width = 0.022f;

        static readonly Color Steel = new Color(0.82f, 0.9f, 1f);
        static readonly Color Broken = new Color(0.5f, 0.5f, 0.54f);
        static readonly Color Flash = new Color(1f, 0.97f, 0.92f);
        // medio ancho de la cinta: entra la tinta de abajo y las mitades que se caen al aire
        const float RibbonHalfWidth = 0.15f;

        Transform ribbon;
        MeshRenderer mr;
        Material mat;
        Mesh mesh;
        MaterialPropertyBlock mpb;
        readonly Vector3[] verts = new Vector3[4];
        Transform owner;
        float window, perfect, t, outT, len;
        End end;
        bool active;

        static readonly int IdColor = Shader.PropertyToID("_Color"), IdGlow = Shader.PropertyToID("_Glow"),
            IdLen = Shader.PropertyToID("_Len"), IdWidth = Shader.PropertyToID("_Width"), IdFade = Shader.PropertyToID("_Fade"),
            IdHot = Shader.PropertyToID("_Hot"), IdBreak = Shader.PropertyToID("_Break"), IdExtent = Shader.PropertyToID("_Extent");

        void Awake()
        {
            var sh = Resources.Load<Shader>("Shaders/NindoParrySteel");
            if (sh == null || !sh.isSupported) { enabled = false; return; }
            mat = new Material(sh) { name = "ParryGuard" };
            mat.SetFloat("_Mode", 0f);
            // la hoja está delante de Kaito: si él la tapa (mirando hacia el norte), queda detrás de su cuerpo
            mat.SetFloat("_ZTest", (float)UnityEngine.Rendering.CompareFunction.LessEqual);
            ParrySteel.ApplyPalette(mat);
            mpb = new MaterialPropertyBlock();
            mesh = new Mesh { name = "ParryGuard" };
            mesh.MarkDynamic();
            mesh.vertices = verts;
            mesh.uv = new[] { new Vector2(0, 0), new Vector2(0, 1), new Vector2(1, 0), new Vector2(1, 1) };
            mesh.triangles = new[] { 0, 1, 2, 2, 1, 3 };
            var go = new GameObject("ParryGuard");
            go.transform.SetParent(transform, false);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = mat;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            mr.receiveShadows = false;
            mr.enabled = false;
            ribbon = go.transform;
        }

        void OnDestroy()
        {
            if (mat != null) Destroy(mat);
            if (mesh != null) Destroy(mesh);
        }

        // ------------------------------------------------------------------ API (la llama Kaito)
        /// <summary>Arranca la ventana: 'window' segundos de juego, los primeros 'perfectWindow' son perfectos.</summary>
        public void Begin(Transform kaito, float window, float perfectWindow)
        {
            if (!enabled) return;
            owner = kaito;
            this.window = Mathf.Max(0.02f, window);
            perfect = Mathf.Clamp(perfectWindow, 0f, this.window);
            t = 0f; outT = 0f; len = halfLength;
            end = End.None;
            active = true;
        }

        /// <summary>Desvió un golpe: destella blanca y se apaga.</summary>
        public void Success() => Finish(End.Success);
        /// <summary>Se cerró la ventana sin nada que desviar: se parte y se cae en gris.</summary>
        public void Whiff() => Finish(End.Whiff);
        /// <summary>Kaito salió del parry por otra cosa (golpe, dash, cinemática): se apaga.</summary>
        public void Cancel() => Finish(End.Cancel);

        void Finish(End e)
        {
            if (!active || end != End.None) return;
            end = e;
            outT = 0f;
        }

        // ------------------------------------------------------------------ por frame
        void LateUpdate()
        {
            if (!active) return;
            if (owner == null) { Hide(); return; }
            // tiempo de juego: igual que la ventana de parry de Kaito (cámara lenta y hit-stop incluidos)
            float dt = Time.deltaTime;
            if (end == End.None) t += dt;
            else
            {
                outT += dt / (end == End.Whiff ? 0.22f : end == End.Success ? 0.06f : 0.1f);
                if (outT >= 1f) { Hide(); return; }
            }
            // lo que queda de ventana: se acorta hacia el centro (al terminar queda del último largo)
            if (end == End.None) len = halfLength * Mathf.Lerp(minLength, 1f, Mathf.Clamp01(1f - t / window));

            var cam = Game.Camera != null ? Game.Camera.Cam : Camera.main;
            if (cam == null) return;
            Vector3 fwd = owner.forward; fwd.y = 0f;
            if (fwd.sqrMagnitude < 1e-4f) fwd = Vector3.forward;
            fwd.Normalize();
            Vector3 center = owner.position + Vector3.up * height + fwd * ahead;
            Vector3 axis = Vector3.Cross(Vector3.up, fwd);                  // la guardia: de costado a costado
            // la cinta mira a la cámara alrededor de su eje y +v queda hacia arriba en pantalla (las mitades caen a -v)
            Vector3 side = Vector3.Cross(axis, cam.transform.position - center).normalized;
            if (Vector3.Dot(side, cam.transform.up) < 0f) side = -side;
            float ex = halfLength * 1.04f + 0.05f;
            // vértices en el espacio de la cinta (cuelga del FXManager, que puede no estar en el origen)
            verts[0] = ribbon.InverseTransformPoint(center - axis * ex - side * RibbonHalfWidth);
            verts[1] = ribbon.InverseTransformPoint(center - axis * ex + side * RibbonHalfWidth);
            verts[2] = ribbon.InverseTransformPoint(center + axis * ex - side * RibbonHalfWidth);
            verts[3] = ribbon.InverseTransformPoint(center + axis * ex + side * RibbonHalfWidth);
            mesh.vertices = verts;
            mesh.RecalculateBounds();
            mr.enabled = true;

            Color col = TellStyle.Gold;
            float glow = 2.2f, fade = 1f, hot = 1f, brk = 0f;
            if (end == End.None) col = t <= perfect ? TellStyle.Gold : Steel;
            else if (end == End.Success) { col = Flash; glow = 3.5f; fade = 1f - outT; }
            else if (end == End.Whiff) { col = Broken; glow = 1f; fade = 1f - outT; hot = 0f; brk = outT; }
            else { col = t <= perfect ? TellStyle.Gold : Steel; fade = 1f - outT; }

            mpb.Clear();
            mpb.SetVector(IdExtent, new Vector4(ex, RibbonHalfWidth, 0f, 0f));
            mpb.SetColor(IdColor, col);
            mpb.SetFloat(IdGlow, glow);
            mpb.SetFloat(IdLen, len);
            mpb.SetFloat(IdWidth, width);
            mpb.SetFloat(IdFade, fade);
            mpb.SetFloat(IdHot, hot);
            mpb.SetFloat(IdBreak, brk);
            mr.SetPropertyBlock(mpb);
        }

        void Hide()
        {
            active = false;
            owner = null;
            if (mr != null) mr.enabled = false;
        }
    }
}
