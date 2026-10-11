using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Nindo
{
    /// <summary>
    /// Silueta de Kaito cuando lo tapa un personaje grande (shader Nindo/CharacterXRay): con los jefes (el koi de
    /// 7.5 m, Kokuyō de 4.5 m) y el sumo Kaito quedaba entero debajo del cuerpo y no se sabía dónde estaba justo
    /// cuando hay que esquivar. Solo se dibuja donde esos personajes marcaron el stencil (XRayOccluder). Copia cada malla suya que usa Nindo/CharacterLit (cuerpo, katana, cintas) con el material de la
    /// silueta: las copias con piel comparten los huesos, así que se mueven con él sin costo de animación propio.
    /// Las copias siguen si el original está prendido (la katana antes de tenerla, la bandana escondida).
    /// </summary>
    public class XRaySilhouette : MonoBehaviour
    {
        static Material shared;
        readonly List<(Renderer src, Renderer copy)> pairs = new List<(Renderer, Renderer)>();

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() => shared = null;

        public static XRaySilhouette Attach(Transform model)
        {
            if (model == null) return null;
            if (shared == null)
            {
                var sh = Resources.Load<Shader>("Shaders/NindoCharacterXRay");
                if (sh == null || !sh.isSupported) return null;
                shared = new Material(sh) { name = "KaitoXRay" };
            }
            var x = model.gameObject.AddComponent<XRaySilhouette>();
            x.Build(model);
            return x;
        }

        void Build(Transform model)
        {
            foreach (var r in model.GetComponentsInChildren<Renderer>(true))
            {
                var mats = r.sharedMaterials;
                if (mats.Length == 0 || mats[0] == null || mats[0].shader == null || mats[0].shader.name != "Nindo/CharacterLit") continue;
                var go = new GameObject(r.name + "_XRay");
                go.layer = r.gameObject.layer;
                Renderer copy;
                if (r is SkinnedMeshRenderer s)
                {
                    if (s.sharedMesh == null) continue;
                    go.transform.SetParent(s.transform.parent, false);
                    go.transform.SetLocalPositionAndRotation(s.transform.localPosition, s.transform.localRotation);
                    go.transform.localScale = s.transform.localScale;
                    var c = go.AddComponent<SkinnedMeshRenderer>();
                    c.sharedMesh = s.sharedMesh;
                    c.bones = s.bones;
                    c.rootBone = s.rootBone;
                    c.localBounds = s.localBounds;
                    c.updateWhenOffscreen = s.updateWhenOffscreen;
                    copy = c;
                }
                else if (r is MeshRenderer && r.TryGetComponent<MeshFilter>(out var mf) && mf.sharedMesh != null)
                {
                    go.transform.SetParent(r.transform, false);
                    go.AddComponent<MeshFilter>().sharedMesh = mf.sharedMesh;
                    copy = go.AddComponent<MeshRenderer>();
                }
                else { Destroy(go); continue; }
                var xm = new Material[mats.Length];
                for (int i = 0; i < xm.Length; i++) xm[i] = shared;
                copy.sharedMaterials = xm;
                copy.shadowCastingMode = ShadowCastingMode.Off;
                copy.receiveShadows = false;
                copy.lightProbeUsage = LightProbeUsage.Off;
                copy.reflectionProbeUsage = ReflectionProbeUsage.Off;
                copy.enabled = r.enabled && r.gameObject.activeInHierarchy;
                pairs.Add((r, copy));
            }
        }

        void LateUpdate()
        {
            // en las cinemáticas Kaito no pelea: la silueta sobre un plano de cámara armado ensucia la toma
            bool allow = !Game.InCutscene;
            for (int i = 0; i < pairs.Count; i++)
            {
                var (src, copy) = pairs[i];
                if (copy == null) continue;
                bool on = allow && src != null && src.enabled && src.gameObject.activeInHierarchy;
                if (copy.enabled != on) copy.enabled = on;
            }
        }
    }

    /// <summary>
    /// Marca en el stencil dónde se ve un personaje grande (jefe, sumo) para que la silueta de Kaito aparezca solo
    /// ahí (shader Nindo/OccluderMark, sin color). Copia sus mallas con Nindo/CharacterLit como XRaySilhouette, pero
    /// las cuelga de una raíz aparte: el destello de golpe, los cambios de fase y las cámaras recorren los renderers
    /// del modelo y no tienen que encontrar las copias. Las rígidas copian la pose del original en LateUpdate; las
    /// con piel comparten los huesos.
    /// </summary>
    [DefaultExecutionOrder(10000)]
    public class XRayOccluder : MonoBehaviour
    {
        static Material shared;
        readonly List<(Renderer src, Renderer copy)> pairs = new List<(Renderer, Renderer)>();
        GameObject root;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() => shared = null;

        public static XRayOccluder Attach(Transform model)
        {
            if (model == null) return null;
            if (shared == null)
            {
                var sh = Resources.Load<Shader>("Shaders/NindoOccluderMark");
                if (sh == null || !sh.isSupported) return null;
                shared = new Material(sh) { name = "OccluderMark" };
            }
            return model.gameObject.AddComponent<XRayOccluder>();
        }

        // en Start: el kit de la zona y los cuerpos de fase (Body_P1/P2 del koi) ya están puestos
        void Start()
        {
            root = new GameObject(name + "_OccluderMarks");
            foreach (var r in GetComponentsInChildren<Renderer>(true))
            {
                var mats = r.sharedMaterials;
                if (mats.Length == 0 || mats[0] == null || mats[0].shader == null || mats[0].shader.name != "Nindo/CharacterLit") continue;
                var go = new GameObject(r.name + "_Mark");
                go.transform.SetParent(root.transform, false);
                Renderer copy;
                if (r is SkinnedMeshRenderer s)
                {
                    if (s.sharedMesh == null) { Destroy(go); continue; }
                    var c = go.AddComponent<SkinnedMeshRenderer>();
                    c.sharedMesh = s.sharedMesh;
                    c.bones = s.bones;
                    c.rootBone = s.rootBone != null ? s.rootBone : s.transform;
                    c.localBounds = s.localBounds;
                    c.updateWhenOffscreen = s.updateWhenOffscreen;
                    copy = c;
                }
                else if (r is MeshRenderer && r.TryGetComponent<MeshFilter>(out var mf) && mf.sharedMesh != null)
                {
                    go.AddComponent<MeshFilter>().sharedMesh = mf.sharedMesh;
                    copy = go.AddComponent<MeshRenderer>();
                }
                else { Destroy(go); continue; }
                var xm = new Material[mats.Length];
                for (int i = 0; i < xm.Length; i++) xm[i] = shared;
                copy.sharedMaterials = xm;
                copy.shadowCastingMode = ShadowCastingMode.Off;
                copy.receiveShadows = false;
                copy.lightProbeUsage = LightProbeUsage.Off;
                copy.reflectionProbeUsage = ReflectionProbeUsage.Off;
                copy.enabled = false;
                pairs.Add((r, copy));
            }
        }

        void LateUpdate()
        {
            bool allow = !Game.InCutscene;
            for (int i = 0; i < pairs.Count; i++)
            {
                var (src, copy) = pairs[i];
                if (copy == null) continue;
                bool on = allow && src != null && src.enabled && src.gameObject.activeInHierarchy;
                if (copy.enabled != on) copy.enabled = on;
                if (on && copy is MeshRenderer)
                {
                    var t = src.transform;
                    copy.transform.SetPositionAndRotation(t.position, t.rotation);
                    copy.transform.localScale = t.lossyScale;
                }
            }
        }

        void OnDestroy() { if (root != null) Destroy(root); }
    }
}
