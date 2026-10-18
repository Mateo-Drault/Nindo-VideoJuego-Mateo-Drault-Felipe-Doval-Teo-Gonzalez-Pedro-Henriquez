using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Las cañas del claro de Chikuō en la pelea (World/ArenaStalk + BambooStalk): cuáles están en cada fase, contra cuál
    /// lo estampa un latigazo (los rayos desde el centro: el billar con el viejo), adónde puede saltar (en cuadro, lejos
    /// del cono del sur de Kaito, en la franja de distancia), la mira de tinta y las hojas y astillas que sueltan. Diseño:
    /// chikuo_v2.md, secciones 2.1, 2.6, 7.3 y 8.
    /// </summary>
    public sealed class BambooGrove
    {
        readonly List<BambooStalk> stalks = new List<BambooStalk>(8);
        /// <summary>Las cañas (la lista misma: recorrerla con foreach no asigna memoria, como sí la interfaz).</summary>
        public List<BambooStalk> All => stalks;
        public BambooStalk Mother { get; private set; }
        public Vector3 Center { get; private set; }
        public float FloorY { get; private set; }
        readonly Transform root;
        Mesh quad;
        Material ensoMat;

        // la mira de tinta (2.6): un trazo tenue de la base hacia donde lo despediría el corte
        readonly LineRenderer aim;
        float aimAlpha;
        static readonly Color AimInk = new Color(0.92f, 0.97f, 1f, 0.35f);

        BambooGrove(Transform parent)
        {
            root = new GameObject("[CañasDeChikuō]").transform;
            root.SetParent(parent, false);
            var sh = Resources.Load<Shader>("Shaders/NindoTelegraph");
            if (sh != null && sh.isSupported)
            {
                ensoMat = new Material(sh) { name = "EnsoBlanco" };
                quad = new Mesh { name = "EnsoQuad" };
                quad.vertices = new[] { new Vector3(-0.5f, 0, -0.5f), new Vector3(0.5f, 0, -0.5f), new Vector3(-0.5f, 0, 0.5f), new Vector3(0.5f, 0, 0.5f) };
                quad.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(0, 1), new Vector2(1, 1) };
                quad.triangles = new[] { 0, 2, 1, 2, 3, 1 };
                quad.RecalculateBounds();
            }
            var ag = new GameObject("MiraDeTinta");
            ag.transform.SetParent(root, false);
            aim = ag.AddComponent<LineRenderer>();
            aim.positionCount = 2;
            aim.useWorldSpace = true;
            aim.widthMultiplier = 0.09f;
            aim.numCapVertices = 3;
            aim.alignment = LineAlignment.TransformZ;
            ag.transform.rotation = Quaternion.Euler(90f, 0f, 0f);   // acostada en el piso
            aim.sharedMaterial = FXMaterials.Additive;
            aim.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            aim.receiveShadows = false;
            aim.enabled = false;
        }

        /// <summary>Junta las siete cañas de la arena (WorldBuilder ya las armó). null si el mundo no las tiene: la pelea
        /// no se puede jugar sin ellas (se avisa una vez).</summary>
        public static BambooGrove Build(Transform parent, Vector3 fallbackCenter)
        {
            if (ArenaStalk.All.Count == 0) return null;
            var g = new BambooGrove(parent);
            foreach (var s in ArenaStalk.All)
            {
                if (s == null) continue;
                var b = new BambooStalk(s, g.quad, g.ensoMat, g.root);
                g.stalks.Add(b);
                if (s.IsMother) g.Mother = b;
            }
            g.poleEnso = InkEnso.Create("Enso_Baston", g.quad, g.ensoMat, g.root);
            g.Center = g.Mother != null ? g.Mother.Base : fallbackCenter;
            g.FloorY = g.Center.y;
            return g;
        }

        public void Dispose()
        {
            if (root != null) Object.Destroy(root.gameObject);
            if (ensoMat != null) Object.Destroy(ensoMat);
            if (quad != null) Object.Destroy(quad);
        }

        public BambooStalk Get(string id)
        {
            for (int i = 0; i < stalks.Count; i++) if (stalks[i].Id == id) return stalks[i];
            return null;
        }

        /// <summary>Todas como empieza esa fase (0..2): reintento, "chikuo canas reset".</summary>
        public void Reset(int phase)
        {
            for (int i = 0; i < stalks.Count; i++) stalks[i].ResetFor(phase);
            aim.enabled = false;
            aimAlpha = 0f;
            aimStamp = null;
            poleOn = false;
            poleEnso?.Hide();
        }

        public void Tick(float dt)
        {
            for (int i = 0; i < stalks.Count; i++) stalks[i].Tick(dt);
            poleEnso?.Tick(poleAt, poleOn, false, 0f, dt);
        }

        // el ensō del bastón clavado de la Grulla en el Bastón (su bastón también es una caña)
        InkEnso poleEnso;
        Vector3 poleAt;
        bool poleOn;

        public void SetPoleEnso(bool on, Vector3 at)
        {
            poleOn = on;
            poleAt = at;
        }

        /// <summary>Se puede posar (en pie y recta; la Madre solo en la fase 3).</summary>
        public static bool Perchable(BambooStalk s, int phase) => s != null && s.Standing && (!s.IsMother || phase >= 2);

        // ------------------------------------------------------------------ el estampado
        /// <summary>
        /// Contra qué caña lo estampa un latigazo desde 'from' hacia 'dir' (plano): la más cercana en pie a StampRange m o
        /// menos dentro de ±StampAngle° de la línea. null = revolcón. La barrera nunca estampa.
        /// </summary>
        public BambooStalk StampTarget(BambooStalk from, Vector3 dir, int phase)
        {
            Vector3 d = dir.Flat().normalized;
            BambooStalk best = null;
            float bestD = BambooMasterMoves.StampRange;
            for (int i = 0; i < stalks.Count; i++)
            {
                var s = stalks[i];
                if (s == from || !s.Standing || (s.IsMother && phase < 2)) continue;
                Vector3 to = (s.Base - from.Base).Flat();
                float dist = to.magnitude;
                if (dist > bestD || dist < 0.5f) continue;
                if (Vector3.Angle(d, to) > BambooMasterMoves.StampAngle) continue;
                best = s;
                bestD = dist;
            }
            return best;
        }

        /// <summary>Dónde cae el revolcón: 'meters' más allá de 'from' por 'dir', adentro de la arena.</summary>
        public Vector3 FlingLanding(Vector3 from, Vector3 dir, float meters)
        {
            Vector3 p = from + dir.Flat().normalized * meters;
            Vector3 off = (p - Center).Flat();
            if (off.magnitude > BambooMasterMoves.ArenaKeep) p = Center + off.normalized * BambooMasterMoves.ArenaKeep;
            p.y = FloorY;
            if (UnityEngine.AI.NavMesh.SamplePosition(p, out var hit, 1.5f, UnityEngine.AI.NavMesh.AllAreas)) p = hit.position;
            return p;
        }

        // ------------------------------------------------------------------ adónde salta (7.3)
        /// <summary>
        /// La caña adonde salta: en pie, distinta de 'except', con su posado en cuadro, a PerchMinDist o más de Kaito, fuera
        /// del cono de ±30° al sur de Kaito entre 2.5 y 6.5 m (ahí su cuerpo posado tapa a Kaito en pantalla), y la más
        /// cercana a la franja de distancia de la fase, con un poco de azar. null si no hay ninguna.
        /// </summary>
        public BambooStalk PickDestination(BambooStalk except, Vector3 kaito, int phase, Vector2 band)
        {
            BambooStalk best = null;
            float bestScore = float.PositiveInfinity;
            for (int i = 0; i < stalks.Count; i++)
            {
                var s = stalks[i];
                if (s == except || !Perchable(s, phase)) continue;
                Vector3 to = (s.Base - kaito).Flat();
                float d = to.magnitude;
                if (d < BambooMasterMoves.PerchMinDist) continue;
                // el sur es -Z (la cámara de la zona mira al norte): el cuerpo posado ahí tapa a Kaito
                if (d > BambooMasterMoves.SouthConeNear && d < BambooMasterMoves.SouthConeFar && Vector3.Angle(to, Vector3.back) < BambooMasterMoves.SouthConeDeg) continue;
                if (!Framed(PerchHead(s), kaito)) continue;
                float off = d < band.x ? band.x - d : d > band.y ? d - band.y : 0f;
                float score = off + Random.value * 1.2f;
                if (score < bestScore) { bestScore = score; best = s; }
            }
            return best;
        }

        /// <summary>Lo más alto del viejo agachado en el posado de 's' (para el encuadre).</summary>
        public static Vector3 PerchHead(BambooStalk s) => s.S.PerchNode != null ? s.S.PerchNode.position + Vector3.up * 1.6f : s.Base + Vector3.up * 6f;

        /// <summary>
        /// Con la cámara de este frame: la cabeza del viejo bajo el 92 % de la pantalla y los pies de Kaito sobre el 8 %
        /// (los márgenes del encuadre del fijado de CameraDirector), y los dos adentro de los costados.
        /// </summary>
        public static bool Framed(Vector3 head, Vector3 kaitoFeet)
        {
            var cam = Camera.main;
            if (cam == null) return true;
            Vector3 h = cam.WorldToViewportPoint(head), f = cam.WorldToViewportPoint(kaitoFeet);
            return h.z > 0f && f.z > 0f && h.y < 0.92f && f.y > 0.08f && h.x > 0.04f && h.x < 0.96f;
        }

        // ------------------------------------------------------------------ la mira de tinta
        /// <summary>
        /// Con la caña 'loaded' cargada y Kaito a 4 m o menos de su base: un trazo blanco tenue de la base hacia donde lo
        /// despediría un corte desde donde está Kaito (hasta la caña del estampado si la hay). Un LineRenderer de 2 puntos,
        /// sin asignar memoria. Se apaga con los avisos de combate.
        /// </summary>
        public void TickAim(BambooStalk loaded, Vector3 kaito, int phase, float dt)
        {
            bool show = loaded != null && Settings.ShowParryAids && (loaded.Base - kaito).Flat().magnitude <= 4f;
            aimAlpha = Mathf.MoveTowards(aimAlpha, show ? 1f : 0f, dt / 0.15f);
            if (!show) SetAimStamp(null);
            if (aimAlpha <= 0f) { if (aim.enabled) aim.enabled = false; return; }
            aim.enabled = true;
            if (loaded == null) return;
            Vector3 b = loaded.Base;
            Vector3 dir = (b - kaito).Flat();
            if (dir.sqrMagnitude < 0.01f) dir = Vector3.forward;
            dir.Normalize();
            var stamp = StampTarget(loaded, dir, phase);
            Vector3 end = stamp != null ? stamp.Base : b + dir * BambooMasterMoves.RevolconM;
            float y = FloorY + 0.07f;
            aim.SetPosition(0, new Vector3(b.x, y, b.z) + dir * 0.45f);
            aim.SetPosition(1, new Vector3(end.x, y, end.z) - (stamp != null ? dir * 0.3f : Vector3.zero));
            Color c = AimInk;
            c.a *= aimAlpha * (stamp != null ? 1.6f : 1f);
            aim.startColor = c;
            c.a *= 0.4f;
            aim.endColor = c;
            SetAimStamp(stamp);
        }

        // la caña que la mira marca como blanco del estampado (su nudo destella)
        BambooStalk aimStamp;

        void SetAimStamp(BambooStalk s)
        {
            if (s == aimStamp) return;
            aimStamp?.Mark(false);
            s?.Mark(true);
            aimStamp = s;
        }

        // ------------------------------------------------------------------ hojas y astillas
        static GameObject splinterTpl, leafTpl;

        public static void Splinters(Vector3 pos, Vector3 dir)
        {
            if (splinterTpl == null)
            {
                splinterTpl = FXFactory.Sparks(new Color(0.84f, 0.76f, 0.42f), 14, 22, 7f, "BambooSplinters");
                splinterTpl.GetComponent<ParticleSystemRenderer>().sharedMaterial = FXMaterials.Alpha;
                var m = splinterTpl.GetComponent<ParticleSystem>().main;
                m.startSize = new ParticleSystem.MinMaxCurve(0.05f, 0.12f);
                m.startLifetime = new ParticleSystem.MinMaxCurve(0.3f, 0.6f);
            }
            Emit(splinterTpl, pos, Quaternion.LookRotation(dir.sqrMagnitude > 1e-4f ? dir : Vector3.forward), 1.2f);
        }

        public static void Leaves(Vector3 pos, float life = 1.6f)
        {
            if (leafTpl == null) leafTpl = FXFactory.Leaves(new Color(0.42f, 0.66f, 0.3f), new Color(0.68f, 0.82f, 0.38f), 26, 1.2f, 1.5f, "BambooLeaves");
            Emit(leafTpl, pos, Quaternion.identity, life);
        }

        static void Emit(GameObject tpl, Vector3 pos, Quaternion rot, float life)
        {
            var go = Pool.Spawn(tpl, pos, rot);
            var ps = go.GetComponent<ParticleSystem>();
            if (ps != null) { ps.Clear(true); ps.Play(true); }
            Pool.Despawn(go, life);
        }
    }
}
