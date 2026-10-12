using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// La katana de Kaito apoyada en el piso mientras reza: con la espada en una mano no puede juntar las palmas, y en
    /// el plano de costado la hoja le cruzaba la cara a 10 cm del ojo. Se copia la malla del arma en la pose de ese
    /// momento (la hoja es rígida: alcanza con una), se acuesta de plano a la derecha de su rodilla derecha y la de la
    /// mano se esconde; al levantarse vuelve a la mano y la del piso desaparece. No hay clip de envainar: el cambio
    /// pasa cuando Kaito ya está arrodillado (se arrodilla con ella) y cuando se para.
    /// </summary>
    public static class KatanaRest
    {
        /// <summary>A la derecha de la rodilla derecha (m del costado y hacia adelante de la raíz de Kaito).</summary>
        const float Side = 0.42f, Ahead = 0.12f;
        const string BakedName = "Nindo_KatanaEnElPiso";

        /// <summary>Acuesta la katana y la saca de la mano; null si Kaito no tiene katana (prólogo) o no se encontró.</summary>
        public static GameObject Lay(PlayerController p)
        {
            if (p == null || !p.HasKatana) return null;
            var weapon = FindWeapon(p);
            if (weapon == null) return null;
            Mesh mesh;
            Vector3 scale;
            bool baked = false;
            if (weapon is SkinnedMeshRenderer smr)
            {
                mesh = new Mesh { name = BakedName };
                smr.BakeMesh(mesh, true);
                scale = Vector3.one;
                baked = true;
            }
            else
            {
                var mf = weapon.GetComponent<MeshFilter>();
                mesh = mf != null ? mf.sharedMesh : null;
                scale = weapon.transform.lossyScale;
            }
            if (mesh == null) return null;

            // el eje de la hoja: el vértice más lejos del centro y el más lejos de ese (en una espada, punta y pomo);
            // de plano: el canto (lo más lejos del eje) queda horizontal
            var v = mesh.vertices;
            if (v.Length < 2) { if (baked) Object.Destroy(mesh); return null; }
            Vector3 c = Vector3.zero;
            for (int i = 0; i < v.Length; i++) { v[i] = Vector3.Scale(v[i], scale); c += v[i]; }
            c /= v.Length;
            Vector3 a = Farthest(v, c), b = Farthest(v, a);
            Vector3 axis = (b - a).normalized;
            Vector3 wide = Vector3.zero;
            float best = 0f;
            for (int i = 0; i < v.Length; i++)
            {
                Vector3 d = v[i] - c;
                d -= axis * Vector3.Dot(d, axis);
                if (d.sqrMagnitude > best) { best = d.sqrMagnitude; wide = d; }
            }
            Vector3 normal = Vector3.Cross(axis, wide.sqrMagnitude > 1e-8f ? wide.normalized : Vector3.Cross(axis, Vector3.up));
            if (normal.sqrMagnitude < 1e-8f) normal = Vector3.Cross(axis, Vector3.right);
            normal.Normalize();
            float half = 0f;
            for (int i = 0; i < v.Length; i++) half = Mathf.Max(half, Mathf.Abs(Vector3.Dot(v[i] - c, normal)));

            // a lo largo del cuerpo de Kaito (la punta hacia adelante) y de plano sobre el piso
            Transform k = p.transform;
            Quaternion local = Quaternion.LookRotation(axis, normal);
            Quaternion world = Quaternion.LookRotation(k.forward.Flat().normalized, Vector3.up);
            Quaternion rot = world * Quaternion.Inverse(local);
            Vector3 spot = k.position + k.right * Side + k.forward * Ahead + Vector3.up * (half + 0.005f);

            var go = new GameObject("KatanaEnElPiso");
            go.transform.SetPositionAndRotation(spot - rot * c, rot);
            if (!baked) go.transform.localScale = scale;
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterials = weapon.sharedMaterials;
            p.SetKatanaVisible(false);
            return go;
        }

        /// <summary>La katana vuelve a la mano y la del piso desaparece.</summary>
        public static void Restore(PlayerController p, GameObject resting)
        {
            if (resting == null) return;
            // la malla horneada es solo de esta copia
            var mf = resting.GetComponent<MeshFilter>();
            if (mf != null && mf.sharedMesh != null && mf.sharedMesh.name == BakedName) Object.Destroy(mf.sharedMesh);
            Object.Destroy(resting);
            if (p != null) p.SetKatanaVisible(true);
        }

        static Renderer FindWeapon(PlayerController p)
        {
            var root = p.model != null ? p.model : p.transform;
            foreach (var r in root.GetComponentsInChildren<Renderer>())
            {
                string n = r.gameObject.name;
                if (r.enabled && (n.Contains("Isan") || n.Contains("Katana") || n.Contains("katana"))) return r;
            }
            return null;
        }

        static Vector3 Farthest(Vector3[] v, Vector3 from)
        {
            Vector3 best = from;
            float d = -1f;
            for (int i = 0; i < v.Length; i++)
            {
                float s = (v[i] - from).sqrMagnitude;
                if (s > d) { d = s; best = v[i]; }
            }
            return best;
        }
    }
}
