using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Destello del desvío (shader Nindo/ParrySteel, modo 1): una aguja de acero HORIZONTAL EN PANTALLA en el choque,
    /// con orla dorada y líneas de impacto rectas que salen; el perfecto suma la estrella de cuatro puntas, destellos
    /// diagonales y un abanico de púas de tinta hacia el atacante. Reemplaza al anillo dorado del piso y al destello
    /// redondo, que tenían la forma del aviso ensō (pedido 27). Horizontal en pantalla y no a lo largo de la guardia:
    /// en los prototipos la versión "en el mundo" se leía como un tajo vertical cuando Kaito mira al costado.
    /// Un quad que mira a la cámara, reciclado; corre en tiempo real (el perfecto trae hit-stop global y el destello
    /// aguanta su pico mientras dura).
    /// </summary>
    public class ParrySteel : MonoBehaviour
    {
        // las vidas salen del shader (normal 0.17 s, perfecto 0.30 s); se apaga un poco después
        const float LifeNormal = 0.2f, LifePerfect = 0.34f;
        static readonly Vector2 ExtentNormal = new Vector2(1.4f, 1.2f), ExtentPerfect = new Vector2(1.8f, 1.4f);

        static readonly Stack<ParrySteel> free = new Stack<ParrySteel>();
        static Material mat;
        static Mesh quad;
        static readonly int IdT = Shader.PropertyToID("_T"), IdPerfect = Shader.PropertyToID("_Perfect"),
            IdSeed = Shader.PropertyToID("_Seed"), IdAim = Shader.PropertyToID("_Aim"), IdExtent = Shader.PropertyToID("_Extent");

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetPool() => free.Clear();

        MeshRenderer mr;
        MaterialPropertyBlock mpb;
        Vector3 at, toAttacker;
        float t, life;
        bool perfect;

        /// <summary>Destello en 'contact' (la hoja de Kaito). 'toAttacker' = de Kaito hacia el que pegó.</summary>
        public static void Spawn(Vector3 contact, Vector3 toAttacker, bool perfect)
        {
            if (mat == null && !Build()) return;
            ParrySteel s = null;
            while (s == null && free.Count > 0) s = free.Pop();
            if (s == null)
            {
                var go = new GameObject("ParrySteel");
                s = go.AddComponent<ParrySteel>();
                go.AddComponent<MeshFilter>().sharedMesh = quad;
                s.mr = go.AddComponent<MeshRenderer>();
                s.mr.sharedMaterial = mat;
                s.mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                s.mr.receiveShadows = false;
                s.mpb = new MaterialPropertyBlock();
            }
            s.at = contact;
            s.toAttacker = toAttacker;
            s.perfect = perfect;
            s.t = 0f;
            s.life = perfect ? LifePerfect : LifeNormal;
            Vector2 ext = perfect ? ExtentPerfect : ExtentNormal;
            s.transform.localScale = new Vector3(ext.x * 2f, ext.y * 2f, 1f);
            s.mpb.Clear();
            s.mpb.SetVector(IdExtent, ext);
            s.mpb.SetFloat(IdPerfect, perfect ? 1f : 0f);
            s.mpb.SetFloat(IdSeed, Random.value * 10f);
            s.gameObject.SetActive(true);
            s.UpdateShape();
        }

        static bool Build()
        {
            var sh = Resources.Load<Shader>("Shaders/NindoParrySteel");
            if (sh == null || !sh.isSupported) return false;
            mat = new Material(sh) { name = "ParrySteel" };
            mat.SetFloat("_Mode", 1f);
            mat.SetFloat("_ZTest", (float)UnityEngine.Rendering.CompareFunction.Always);   // la luz va encima de los cuerpos
            ApplyPalette(mat);
            quad = new Mesh { name = "ParrySteelQuad" };
            quad.vertices = new[] { new Vector3(-0.5f, -0.5f, 0), new Vector3(0.5f, -0.5f, 0), new Vector3(-0.5f, 0.5f, 0), new Vector3(0.5f, 0.5f, 0) };
            quad.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(0, 1), new Vector2(1, 1) };
            quad.triangles = new[] { 0, 2, 1, 2, 3, 1 };
            // los límites se agrandan: el quad gira con la cámara y no tiene que desaparecer por culling
            quad.bounds = new Bounds(Vector3.zero, Vector3.one * 2f);
            return true;
        }

        /// <summary>Los mismos dorados y tinta que el aviso (TellStyle): el parry cambia de forma, no de color.</summary>
        public static void ApplyPalette(Material m)
        {
            m.SetColor("_Gold", TellStyle.Gold);
            m.SetColor("_GoldHot", TellStyle.GoldHot);
            m.SetColor("_Ink", TellStyle.Ink);
        }

        void LateUpdate()
        {
            t += Time.unscaledDeltaTime;
            if (t >= life) { gameObject.SetActive(false); free.Push(this); return; }
            UpdateShape();
        }

        void UpdateShape()
        {
            var cam = Game.Camera != null ? Game.Camera.Cam : Camera.main;
            if (cam == null) return;
            // en el plano de la cámara: x = su derecha (la aguja queda horizontal en pantalla aunque la cámara tiemble)
            var ct = cam.transform;
            transform.SetPositionAndRotation(at, ct.rotation);
            // hacia el atacante visto en pantalla (las púas de tinta del perfecto van para ese lado; Kaito queda limpio)
            Vector2 aim = new Vector2(Vector3.Dot(toAttacker, ct.right), Vector3.Dot(toAttacker, ct.up));
            aim = aim.sqrMagnitude > 1e-4f ? aim.normalized : Vector2.right;
            mpb.SetVector(IdAim, aim);
            mpb.SetFloat(IdT, t);
            mr.SetPropertyBlock(mpb);
        }
    }
}
