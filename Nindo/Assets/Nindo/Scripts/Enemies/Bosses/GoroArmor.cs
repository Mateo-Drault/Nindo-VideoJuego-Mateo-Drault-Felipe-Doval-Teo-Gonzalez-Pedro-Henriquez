using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// La armadura de roca de Gorō (kit 'goro_armor', Tools/Blender/bosses/goro/goro_armor.py): 16 rocas con skin rígido,
    /// cada una con su hueso Acc_Roca_&lt;Pieza&gt; colgado del hueso vivo. La maneja GoroBoss:
    ///  * fase 1: cada hueso de roca a escala casi cero (el renderer queda prendido: el destello de golpe y los rayos X
    ///    ya lo conocen);
    ///  * ArmorRise: cada pieza se arranca de la pared de la cumbre y vuela hasta pegarse en el cuadro 'slam_&lt;Pieza&gt;'
    ///    del clip (GoroAnims.fbx.json). El vuelo es el del contrato del kit: u = (t - salida) / vuelo, posición =
    ///    lerp(salida, pegada(t), u²) + arriba · arco · 4u(1-u), giro que se deshace con (1-u)². 'pegada(t)' es el hueso
    ///    colgado del vivo en este cuadro (el cuerpo se mueve mientras se levanta);
    ///  * fase 2: todas puestas; con la vida se le van cayendo pedazos (Shed) y al morir se le cae todo.
    /// Corre en LateUpdate (después del Animator, antes del skin). Sin asignaciones por cuadro.
    /// </summary>
    public class GoroArmor
    {
        /// <summary>Datos de cada pieza (Kit_goro_armor.fbx.json: slam_s = cuadro slam_&lt;Pieza&gt; / 30, giro y su eje en el
        /// marco de Gorō, y la dirección de 'start_unity', de donde la arrancaba la etapa de autoría).</summary>
        struct Spec
        {
            public string name;
            public float slam, spin;
            public Vector3 axis, from;
            public Spec(string n, float s, float sp, Vector3 ax, Vector3 f) { name = n; slam = s; spin = sp; axis = ax.normalized; from = f; }
        }

        static readonly Spec[] Specs =
        {
            new Spec("Greave_L", 24f / 30f, 200f, new Vector3(0.8876f, 0.4379f, -0.1429f), new Vector3(-2.6f, 0f, -1.8f)),
            new Spec("Greave_R", 30f / 30f, 220f, new Vector3(0.1171f, 0.879f, -0.4622f), new Vector3(2.8f, 0f, -1.4f)),
            new Spec("Knee_L", 38f / 30f, 260f, new Vector3(0.6669f, 0.2002f, -0.7178f), new Vector3(-3.4f, 0f, 1.0f)),
            new Spec("Knee_R", 44f / 30f, 240f, new Vector3(0.2791f, 0.5968f, -0.7523f), new Vector3(3.6f, 0f, 0.6f)),
            new Spec("Tasset_L", 52f / 30f, 180f, new Vector3(-0.1669f, 0.7071f, -0.6871f), new Vector3(-4.2f, 0f, -0.6f)),
            new Spec("Tasset_R", 56f / 30f, 200f, new Vector3(-0.6266f, 0.5556f, -0.5465f), new Vector3(4.0f, 0f, -1.2f)),
            new Spec("Bracer_R", 70f / 30f, 300f, new Vector3(0.329f, 0.6242f, 0.7086f), new Vector3(3.2f, 0f, 2.6f)),
            new Spec("Bracer_L", 76f / 30f, 280f, new Vector3(0.5998f, 0.5965f, 0.5333f), new Vector3(-3.4f, 0f, 2.4f)),
            new Spec("Chest_Low", 92f / 30f, 160f, new Vector3(0.3482f, 0.6562f, 0.6694f), new Vector3(-0.6f, 0f, 4.6f)),
            new Spec("Chest_High", 100f / 30f, 180f, new Vector3(0.6125f, 0.6774f, -0.4075f), new Vector3(0.8f, 0f, 5.0f)),
            new Spec("Pauldron_L", 118f / 30f, 220f, new Vector3(0.5757f, 0.4057f, -0.7099f), new Vector3(-5.2f, 0f, -2.2f)),
            new Spec("Pauldron_R", 128f / 30f, 240f, new Vector3(-0.6935f, 0.3359f, -0.6374f), new Vector3(5.4f, 0f, -1.6f)),
            new Spec("Ridge_L", 146f / 30f, 140f, new Vector3(0.9774f, 0.2073f, -0.0406f), new Vector3(-2.4f, 0f, -6.0f)),
            new Spec("Ridge_R", 152f / 30f, 160f, new Vector3(-0.7908f, 0.585f, -0.1799f), new Vector3(2.2f, 0f, -6.2f)),
            new Spec("Horn_L", 170f / 30f, 320f, new Vector3(-0.6987f, 0.6839f, 0.21f), new Vector3(-1.6f, 0f, -4.4f)),
            new Spec("Horn_R", 174f / 30f, 340f, new Vector3(-0.8706f, 0.1879f, 0.4547f), new Vector3(1.6f, 0f, -4.2f)),
        };

        public const int Count = 16;
        /// <summary>Cuadro (s del clip ArmorRise) en que se pega la pieza i.</summary>
        public static float SlamTime(int i) => Specs[i].slam;
        public static string PieceName(int i) => Specs[i].name;

        enum Mode { Hidden, Flying, On, Falling }

        class Piece
        {
            public Transform bone;
            public Vector3 restPos, restScale;
            public Quaternion restRot;
            public Mode mode;
            // vuelo (ArmorRise)
            public Vector3 start, axis;
            public float launch, flight, arc, spin;
            public bool launched, slammed;
            // caída (Shed): sin física, una parábola con rebote chico y se hunde en la nieve
            public Vector3 vel, angVel, euler;
            public float fallT, groundY;
        }

        readonly Piece[] pieces = new Piece[Count];
        readonly Transform root;
        public bool Valid { get; private set; }

        /// <summary>Se arrancó una pieza de la pared (índice, punto de salida) y se pegó al cuerpo (índice, punto).</summary>
        public System.Action<int, Vector3> Launched, Slammed, Landed;

        public GoroArmor(Transform root, Transform model)
        {
            this.root = root;
            int found = 0;
            var all = model.GetComponentsInChildren<Transform>(true);
            for (int i = 0; i < Count; i++)
            {
                string bn = "Acc_Roca_" + Specs[i].name;
                foreach (var t in all)
                {
                    if (t.name != bn) continue;
                    pieces[i] = new Piece { bone = t, restPos = t.localPosition, restRot = t.localRotation, restScale = t.localScale };
                    found++;
                    break;
                }
            }
            Valid = found == Count;
            if (!Valid) { if (found > 0) Debug.LogWarning($"[Nindo] La armadura de Gorō tiene {found}/{Count} huesos: no se arma."); return; }
            // las piezas que vuelan salen de los bounds de reposo del skin: sin esto se recortaban contra la cámara de costado
            foreach (var smr in model.GetComponentsInChildren<SkinnedMeshRenderer>(true))
                if (smr.name.StartsWith("Acc_Kit_goro_armor")) { var b = smr.localBounds; b.Expand(36f); smr.localBounds = b; }
            HideAll();
        }

        // escala de una pieza escondida: el skin rígido la junta en un punto (cero exacto deja las normales en NaN)
        static readonly Vector3 Gone = Vector3.one * 1e-4f;
        const float FlightScale = 0.45f;

        public void HideAll()
        {
            if (!Valid) return;
            foreach (var p in pieces) { p.mode = Mode.Hidden; p.launched = p.slammed = false; Rest(p); p.bone.localScale = Gone; }
        }

        public void ShowAll()
        {
            if (!Valid) return;
            foreach (var p in pieces) { p.mode = Mode.On; Rest(p); }
        }

        static void Rest(Piece p)
        {
            p.bone.localPosition = p.restPos;
            p.bone.localRotation = p.restRot;
            p.bone.localScale = p.restScale;
        }

        /// <summary>
        /// Prepara el vuelo: cada pieza sale de la pared de la cumbre (radio 'rimRadius' alrededor de 'rimCenter', a la
        /// altura del suelo que encuentra ahí) en la dirección de su 'start_unity', espejada hacia el lado contrario de
        /// 'camSide' (las que salían del lado de la cámara pasaban por delante del lente). 'tScale' = velocidad del clip.
        /// El reloj del vuelo es el del clip ArmorRise: t = 0 cuando arranca; las primeras piezas salen antes (t &lt; 0).
        /// </summary>
        public void PlanAssembly(Vector3 rimCenter, float rimRadius, Vector3 camSide, float tScale, int groundMask)
        {
            if (!Valid) return;
            Vector3 c = root.position;
            camSide = camSide.Flat().normalized;
            for (int i = 0; i < Count; i++)
            {
                var s = Specs[i];
                var p = pieces[i];
                Vector3 d = root.TransformDirection(s.from).Flat().normalized;
                float k = Vector3.Dot(d, camSide);
                if (k > 0.15f) d = (d - camSide * (2f * k)).normalized;
                // hasta la pared de la cumbre en esa dirección, pero a 6.5-9 m: desde la pared (13-17 m) las piezas de
                // 0.2-0.75 m eran puntos en el plano de costado; así se arrancan de la roca de la cumbre (o de la pared, si
                // Gorō cayó cerca del borde) y se ven volar enteras
                Vector3 o = (c - rimCenter).Flat();
                float b = Vector3.Dot(o, d), disc = b * b - (o.sqrMagnitude - rimRadius * rimRadius);
                float dist = Mathf.Clamp(disc > 0f ? -b + Mathf.Sqrt(disc) : 9f, 6.5f, 9f);
                Vector3 q = c + d * dist;
                q.y = c.y;
                if (Physics.Raycast(q + Vector3.up * 30f, Vector3.down, out var hit, 60f, groundMask, QueryTriggerInteraction.Ignore))
                    q.y = hit.point.y;
                q.y += 0.2f;
                p.start = q;
                p.axis = root.TransformDirection(s.axis);
                // ~10 m/s: se lee el viaje y llega en el cuadro del golpe (en reintentos el clip va más rápido)
                float realDist = Vector3.Distance(q, c + Vector3.up * 1.6f);
                p.flight = Mathf.Clamp(realDist / 10f, 0.8f, 1.2f) / Mathf.Max(0.5f, tScale);
                p.launch = s.slam / Mathf.Max(0.5f, tScale) - p.flight;
                p.arc = 2.2f + 0.3f * realDist;
                // vuela más que en la autoría (0.55-0.8 s): más vueltas para que siga leyéndose como roca suelta
                p.spin = s.spin * 1.6f;
                p.launched = p.slammed = false;
                p.mode = Mode.Hidden;
                p.bone.localScale = Gone;
            }
        }

        /// <summary>Segundos antes del arranque del clip en que sale la primera pieza (para empezar el clip a tiempo).</summary>
        public float Lead
        {
            get
            {
                float lead = 0f;
                if (Valid) foreach (var p in pieces) lead = Mathf.Max(lead, -p.launch);
                return lead;
            }
        }

        /// <summary>Vuelo de las piezas a 't' segundos (reales del clip) del arranque de ArmorRise. Llamar en LateUpdate.</summary>
        public void TickAssembly(float t)
        {
            if (!Valid) return;
            for (int i = 0; i < Count; i++)
            {
                var p = pieces[i];
                if (p.mode == Mode.On || p.mode == Mode.Falling) continue;
                if (t < p.launch) continue;
                if (!p.launched) { p.launched = true; Launched?.Invoke(i, p.start); }
                float u = Mathf.Clamp01((t - p.launch) / p.flight);
                Rest(p);
                if (u >= 1f)
                {
                    p.mode = Mode.On;
                    if (!p.slammed) { p.slammed = true; Slammed?.Invoke(i, p.bone.position); }
                    continue;
                }
                p.mode = Mode.Flying;
                Vector3 at = p.bone.position;
                Quaternion rot = p.bone.rotation;
                Vector3 pos = Vector3.Lerp(p.start, at, u * u) + Vector3.up * (p.arc * 4f * u * (1f - u));
                float w = 1f - u;
                p.bone.SetPositionAndRotation(pos, Quaternion.AngleAxis(p.spin * w * w, p.axis) * rot);
                // en el aire un poco más grande (llega a su tamaño al pegarse): las chicas se leían como piedritas
                p.bone.localScale = p.restScale * (1f + FlightScale * w);
            }
        }

        /// <summary>Termina el armado de golpe (cinemática cortada): todas puestas.</summary>
        public void FinishAssembly()
        {
            if (!Valid) return;
            foreach (var p in pieces) if (p.mode != Mode.Falling) { p.mode = Mode.On; Rest(p); }
        }

        /// <summary>
        /// Se le cae la pieza (los golpes le van rompiendo la armadura, o muere): se suelta del cuerpo con un empujón
        /// hacia afuera, cae, rebota una vez y se hunde. 'push' = de dónde vino el golpe (plano).
        /// </summary>
        public void Shed(int i, Vector3 push, float groundY)
        {
            if (!Valid || i < 0 || i >= Count) return;
            var p = pieces[i];
            if (p.mode != Mode.On) return;
            p.mode = Mode.Falling;
            Vector3 outward = (p.bone.position - root.position).Flat();
            outward = outward.sqrMagnitude > 1e-4f ? outward.normalized : push.Flat().normalized;
            p.vel = (outward * 2.2f + push.Flat().normalized * 1.2f) + Vector3.up * 2.6f;
            p.angVel = Random.onUnitSphere * Random.Range(240f, 420f);
            p.fallT = 0f;
            p.groundY = groundY;
            // desde acá la pieza ya no sigue al hueso vivo: queda donde está y se la mueve en el mundo
            p.start = p.bone.position;
            p.euler = p.bone.eulerAngles;
        }

        public bool IsOn(int i) => Valid && pieces[i].mode == Mode.On;
        public Vector3 PiecePosition(int i) => Valid ? pieces[i].bone.position : root.position;

        /// <summary>Piezas que se están cayendo (llamar en LateUpdate: el Animator ya les puso la pose del hueso vivo).</summary>
        public void TickFalling(float dt)
        {
            if (!Valid) return;
            for (int i = 0; i < Count; i++)
            {
                var p = pieces[i];
                if (p.mode != Mode.Falling) continue;
                p.fallT += dt;
                if (p.fallT < 1.4f)
                {
                    p.vel += Vector3.down * 22f * dt;
                    p.start += p.vel * dt;
                    // rebote en la nieve: pierde casi todo y se arrastra
                    if (p.start.y < p.groundY + 0.15f && p.vel.y < 0f)
                    {
                        p.start.y = p.groundY + 0.15f;
                        if (p.vel.y < -3f) Landed?.Invoke(i, p.start);
                        p.vel = new Vector3(p.vel.x * 0.4f, -p.vel.y * 0.25f, p.vel.z * 0.4f);
                        p.angVel *= 0.4f;
                    }
                    p.euler += p.angVel * dt;
                    p.bone.SetPositionAndRotation(p.start, Quaternion.Euler(p.euler));
                    p.bone.localScale = p.restScale;
                }
                else
                {
                    // se hunde y desaparece (no queda un montón de rocas que tape la pelea)
                    float k = Mathf.Clamp01((p.fallT - 1.4f) / 0.6f);
                    p.bone.SetPositionAndRotation(p.start + Vector3.down * (0.5f * k), Quaternion.Euler(p.euler));
                    p.bone.localScale = k >= 1f ? Gone : p.restScale * (1f - k);
                    if (k >= 1f) { p.mode = Mode.Hidden; p.bone.localPosition = p.restPos; p.bone.localRotation = p.restRot; }
                }
            }
        }
    }
}
