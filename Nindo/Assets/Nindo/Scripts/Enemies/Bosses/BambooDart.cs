using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Dardo de bambú que Chikuō sopla con la flauta-bastón (diseño: chikuo_v2.md, 5.1 y 11.2). Como las perlas de Mizuchi:
    /// la fuente del golpe es el dardo (un parry a 10 m no hace retroceder al viejo), el anillo dorado va a los pies de
    /// Kaito con la ETA honesta (BambooMasterBoss.ProjectileEta) y el "¡ya!" suena una vez por dardo. El parry lo rompe
    /// (y da el Espíritu de siempre), el dash lo atraviesa, y el que no pega queda clavado en el piso 3 s: se ve dónde cayó
    /// la ráfaga. El silbador es el pesado: rojo, por el carril, no se desvía.
    /// Sin sombra de luz (su sombra es un óvalo dibujado en el piso): ZoneCulling no lo toma (ver ZoneCulling.Dynamic).
    /// </summary>
    public class BambooDart : MonoBehaviour
    {
        public static readonly List<BambooDart> Active = new List<BambooDart>();
        static readonly Stack<BambooDart> free = new Stack<BambooDart>();
        static Material strawMat, leafMat, redMat;
        static Mesh needleMesh;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { Active.Clear(); free.Clear(); strawMat = leafMat = redMat = null; needleMesh = null; }

        // la paja de la paleta (straw #d2bd80) un poco encendida para que el dardo se lea de noche contra el bosque
        static readonly Color Straw = new Color(0.95f, 0.84f, 0.5f);
        static readonly Color Leaf = new Color(0.36f, 0.62f, 0.3f);

        public BambooMasterBoss Owner { get; private set; }
        public bool Heavy { get; private set; }
        /// <summary>Ya sonó su "¡ya!" / ya destelló (los pasa el jefe del dardo por salir al que sale).</summary>
        [System.NonSerialized] public bool cued, glinted;

        Vector3 dir;
        float speed, damage, life, floorY, hitR, stuckFor;
        bool flying;
        Transform body, shadow;
        Renderer needleR, tailR;
        TrailRenderer trail;

        public static BambooDart Spawn(BambooMasterBoss owner, Vector3 pos, Vector3 dir3, float speed, float damage, bool heavy, float floorY, bool cued)
        {
            BambooDart d = null;
            while (d == null && free.Count > 0) d = free.Pop();
            if (d == null) d = Create();
            d.transform.position = pos;
            d.gameObject.SetActive(true);
            d.Owner = owner; d.Heavy = heavy; d.cued = cued; d.glinted = false;
            d.dir = dir3.normalized; d.speed = speed; d.damage = damage; d.floorY = floorY;
            d.hitR = heavy ? BambooMasterMoves.WhistleLane * 0.5f + 0.1f : BambooMasterMoves.DartHitR;
            d.life = 2.5f; d.flying = true; d.stuckFor = 0f;
            d.body.localScale = heavy ? new Vector3(1.6f, 1.6f, 1.6f) : Vector3.one;
            d.transform.rotation = Quaternion.LookRotation(d.dir);
            d.needleR.sharedMaterial = heavy ? redMat : strawMat;
            d.trail.Clear();
            d.trail.emitting = true;
            Color c = heavy ? TellStyle.Crimson : TellStyle.Gold;
            d.trail.startColor = new Color(c.r, c.g, c.b, 0.85f);
            d.trail.endColor = new Color(c.r, c.g, c.b, 0f);
            d.trail.widthMultiplier = heavy ? 0.16f : 0.09f;
            d.shadow.gameObject.SetActive(true);
            if (!Active.Contains(d)) Active.Add(d);
            Game.Audio?.Play(heavy ? "dart_whistle" : "dart_blow", pos, heavy ? 1f : 0.7f, 0.08f);
            return d;
        }

        static BambooDart Create()
        {
            if (strawMat == null)
            {
                strawMat = FXMaterials.MakeUnlitTransparent("DardoPaja", new Color(Straw.r * 1.3f, Straw.g * 1.3f, Straw.b * 1.3f, 1f), false);
                leafMat = FXMaterials.MakeUnlitTransparent("DardoHoja", new Color(Leaf.r, Leaf.g, Leaf.b, 1f), false);
                redMat = FXMaterials.MakeUnlitTransparent("SilbadorRojo", new Color(1.2f, 0.32f, 0.22f, 1f), false);
            }
            if (needleMesh == null) needleMesh = BuildNeedle();
            var go = new GameObject("BambooDart");
            var d = go.AddComponent<BambooDart>();
            var b = new GameObject("Body").transform;
            b.SetParent(go.transform, false);
            d.body = b;
            var n = new GameObject("Aguja");
            n.transform.SetParent(b, false);
            n.AddComponent<MeshFilter>().sharedMesh = needleMesh;
            d.needleR = n.AddComponent<MeshRenderer>();
            // la cola de hoja: dos planos cruzados atrás de la aguja
            var t = new GameObject("Cola");
            t.transform.SetParent(b, false);
            t.transform.localPosition = new Vector3(0f, 0f, -0.12f);
            t.AddComponent<MeshFilter>().sharedMesh = needleMesh;
            t.transform.localScale = new Vector3(2.6f, 0.4f, 0.35f);
            d.tailR = t.AddComponent<MeshRenderer>();
            d.tailR.sharedMaterial = leafMat;
            foreach (var r in new[] { d.needleR, d.tailR })
            {
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                r.receiveShadows = false;
            }
            d.trail = go.AddComponent<TrailRenderer>();
            d.trail.time = 0.16f;
            d.trail.minVertexDistance = 0.12f;
            d.trail.sharedMaterial = FXMaterials.Additive;
            d.trail.widthCurve = new AnimationCurve(new Keyframe(0f, 1f), new Keyframe(1f, 0f));
            d.trail.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            // sombra en el piso: con la cámara alta es lo que dice dónde va a caer
            var sh = new GameObject("Sombra");
            sh.transform.SetParent(go.transform, false);
            sh.AddComponent<MeshFilter>().sharedMesh = WaterSplash.Quad;
            var smr = sh.AddComponent<MeshRenderer>();
            smr.sharedMaterial = FXMaterials.Alpha;
            smr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            var smpb = new MaterialPropertyBlock();
            smpb.SetColor("_BaseColor", new Color(0.02f, 0.03f, 0.02f, 0.5f));
            smpb.SetColor("_Color", new Color(0.02f, 0.03f, 0.02f, 0.5f));
            smr.SetPropertyBlock(smpb);
            d.shadow = sh.transform;
            return d;
        }

        /// <summary>Aguja de 0.25 m (+Z): un huso de seis caras (el estilo facetado del juego).</summary>
        static Mesh BuildNeedle()
        {
            const int S = 6;
            const float R = 0.018f, L = 0.25f;
            var v = new List<Vector3> { new Vector3(0f, 0f, L * 0.5f), new Vector3(0f, 0f, -L * 0.5f) };
            for (int i = 0; i < S; i++)
            {
                float a = i * Mathf.PI * 2f / S;
                v.Add(new Vector3(Mathf.Cos(a) * R, Mathf.Sin(a) * R, L * 0.2f));
            }
            var tri = new List<int>();
            for (int i = 0; i < S; i++)
            {
                int a = 2 + i, b = 2 + (i + 1) % S;
                tri.Add(0); tri.Add(b); tri.Add(a);
                tri.Add(1); tri.Add(a); tri.Add(b);
            }
            var m = new Mesh { name = "AgujaDeBambu" };
            m.SetVertices(v);
            m.SetTriangles(tri, 0);
            m.RecalculateNormals();
            m.RecalculateBounds();
            return m;
        }

        // ------------------------------------------------------------------ ETA (avisos honestos)
        /// <summary>Segundos hasta tocar a Kaito en 'p' (infinito si no va hacia él o ya está clavado).</summary>
        public float EtaTo(Vector3 p)
        {
            if (!flying) return float.PositiveInfinity;
            Vector3 flat = new Vector3(dir.x, 0f, dir.z);
            float fs = flat.magnitude * speed;
            if (fs < 0.5f) return float.PositiveInfinity;
            return WaterPearl.TimeToReach(transform.position, flat / flat.magnitude, fs, p, hitR, life);
        }

        public Vector3 Position => transform.position;

        // ------------------------------------------------------------------ vuelo
        void Update()
        {
            float dt = Time.deltaTime;
            if (dt <= 0f) return;
            if (!flying)
            {
                stuckFor += dt;
                if (stuckFor >= BambooMasterMoves.DartStuck) Despawn();
                return;
            }
            Vector3 pos = transform.position + dir * speed * dt;
            transform.position = pos;
            life -= dt;
            shadow.position = new Vector3(pos.x, floorY + 0.03f, pos.z);
            shadow.rotation = Quaternion.LookRotation(new Vector3(dir.x, 0f, dir.z).sqrMagnitude > 1e-4f ? new Vector3(dir.x, 0f, dir.z) : Vector3.forward);
            shadow.localScale = new Vector3(Heavy ? 0.18f : 0.12f, 1f, Heavy ? 0.6f : 0.4f);
            var p = Game.Player;
            if (p != null && p.IsAlive && Touches(p)) { TryHit(p); if (!flying) return; }
            // se clava en el piso (la punta adelante)
            if (pos.y <= floorY + 0.04f) { Stick(new Vector3(pos.x, floorY + 0.02f, pos.z)); return; }
            if (life <= 0f || Owner != null && CombatMath.FlatDistance(pos, Owner.arenaCenter) > Owner.arenaRadius + 2f) Despawn();
        }

        /// <summary>¿El dardo está a hitR del cuerpo de Kaito (de los pies a 1.7 m)?</summary>
        bool Touches(PlayerController p)
        {
            Vector3 a = p.transform.position, pos = transform.position;
            float y = Mathf.Clamp(pos.y, a.y, a.y + 1.7f);
            Vector3 c = new Vector3(a.x, y, a.z);
            return (pos - c).sqrMagnitude <= hitR * hitR;
        }

        void TryHit(PlayerController p)
        {
            var info = new DamageInfo
            {
                damage = damage, kind = Heavy ? AttackKind.Unblockable : AttackKind.Projectile, direction = new Vector3(dir.x, 0f, dir.z).normalized,
                point = transform.position, knockback = Heavy ? 1.2f : 0.35f, sourceFaction = Faction.Enemy, source = this,
                attackName = Heavy ? "Silbador" : "Dardo",
            };
            var r = p.ReceiveHit(info);
            switch (r)
            {
                case HitResult.Dodged:
                case HitResult.Ignored:
                    return;   // el dash lo atraviesa: sigue de largo y se clava atrás
                case HitResult.Hit:
                case HitResult.Killed:
                    Owner?.OnDartHit(Heavy);
                    Break(false);
                    return;
                default:
                    Break(true);
                    return;
            }
        }

        void Stick(Vector3 at)
        {
            flying = false;
            transform.position = at;
            trail.emitting = false;
            shadow.gameObject.SetActive(false);
            stuckFor = 0f;
            Game.Audio?.Play("dart_thunk", at, 0.5f, 0.1f);
            Game.FX?.Dust(at, 0.35f);
        }

        /// <summary>Se parte (lo desviaron o le pegó): astillas y afuera.</summary>
        void Break(bool parried)
        {
            BambooGrove.Splinters(transform.position, -dir);
            // su propio chasquido: "thok" (hueco) es solo el de las cosquillas, el corte a la caña sin campanas
            if (parried) Game.Audio?.Play("dart_snap", transform.position, 0.7f, 0.1f);
            Despawn();
        }

        void Despawn()
        {
            flying = false;
            Active.Remove(this);
            gameObject.SetActive(false);
            free.Push(this);
        }

        /// <summary>Saca todos los dardos (reintento, cambio de fase, derrota, "chikuo canas reset").</summary>
        public static void ClearAll()
        {
            for (int i = Active.Count - 1; i >= 0; i--)
            {
                var d = Active[i];
                if (d != null) d.Despawn(); else Active.RemoveAt(i);
            }
        }

        void OnDisable() { Active.Remove(this); }
    }
}
