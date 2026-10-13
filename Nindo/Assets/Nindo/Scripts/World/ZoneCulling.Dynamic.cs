using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Nindo
{
    /// <summary>
    /// Lo que se crea después de WorldBuilder.Build, o que Collect no junta: el incienso de un santuario rezado en la
    /// partida, los braseros del patio de Kokuyō, las rocas de la avalancha de Gorō, los pétalos del final. Quien lo arma
    /// llama ZoneCulling.AddDynamic(raíz) apenas lo configuró; si el mundo todavía no terminó de armarse (un santuario
    /// rezado en la partida guardada se enciende en su Start, antes que esto) queda anotado y se toma al final de Collect.
    /// Se toma solo lo que esconder ahorra algo:
    ///  * partículas en loop: escondidas se PAUSAN y al volver se ponen al día con un paso (Show). Lo que hace Unity solo
    ///    con las de FXFactory fuera de cuadro (cullingMode Automatic, pero en espacio de mundo y con ruido: sin modo
    ///    procedural) no está documentado ni medido; esto no depende de eso. Simulado sobre los caminos con los 14
    ///    santuarios rezados: de los 44 sistemas (16 de los braseros, 2 por santuario) queda ~1 simulando;
    ///  * renderers que tiran sombra: escondidos salen del mapa de sombras de la luna (como los del mundo).
    /// Una malla, una línea o una estela SIN sombra (el humo del incienso, los brillos de la puerta de los sellos y del
    /// sello de la muralla, las cuerdas de sombra, las llamas de los braseros, el filo de tinta de Kage) no se toma: Unity
    /// ya no la dibuja fuera de cuadro y no entra al mapa de sombras, así que esconderla no ahorra nada y probarla acá en
    /// cada frame costaría más de lo que le cuesta a Unity probarla. Tampoco lo que cuelga de Kaito (cada plano lo sigue) ni
    /// de un enemigo (lo esconde su siesta, Enemy.SetAsleep, que se saltea lo que otro ya escondió), ni las luces: URP
    /// descarta sola las que no tocan el cuadro, ninguna de estas tira sombra y sus dueños ya las apagan de lejos (incienso
    /// 32 m, sello de la muralla 40 m, braseros 45 m); apagar una cuyo alcance toca el cuadro cambiaría la imagen.
    /// Cada frame, con la misma prueba que lo del mundo (el frustum de cada cámara que dibuja el mundo más el barrido de su
    /// sombra, prender en el mismo frame en que hace falta, apagar después de Linger) pero con la caja de AHORA: se pueden
    /// mover. Lo que su dueño destruye sale solo de la lista; lo que apaga (enabled, o el GameObject: las rocas vuelven al
    /// pool así) no se decide hasta que vuelva.
    /// </summary>
    public partial class ZoneCulling
    {
        /// <summary>Todo lo que se pueda manejar debajo de 'root' (incluidos los hijos apagados), ya o al terminar el armado.</summary>
        public static void AddDynamic(GameObject root)
        {
            if (root == null) return;
            var zc = Instance;
            if (zc == null || zc.items == null) { Defer(root); return; }
            zc.TakeAll(root);
        }

        public static void AddDynamic(Renderer r)
        {
            if (r == null) return;
            var zc = Instance;
            if (zc == null || zc.items == null) { Defer(r); return; }
            zc.TakeDynamic(r);
        }

        public static void AddDynamic(ParticleSystem ps)
        {
            if (ps != null) AddDynamic(ps.GetComponent<Renderer>());
        }

        /// <summary>Registrados ahora y cuántos se están dibujando (o simulando).</summary>
        public static int DynamicOn => Instance != null ? Instance.dynLit : 0;
        public static int DynamicTotal => Instance != null ? Instance.dynCount : 0;

        struct Dyn
        {
            public Renderer r;
            public GameObject go;
            public Transform t;
            /// <summary>Partículas (null en lo demás). 'fresh': todavía no se miró si son en loop ni su cota.</summary>
            public ParticleSystem ps;
            public bool fresh, loop, paused, on;
            /// <summary>Partículas: la cota de ParticleBounds respecto del emisor (con el giro 'erot') y lo que ocupan de verdad
            /// (Update, cada 4 frames: escondidas están en pausa y lo último medido sigue siendo donde quedaron).</summary>
            public Vector3 emin, emax, mmin, mmax;
            public Quaternion erot;
            public bool measured;
            /// <summary>Partículas: desde cuándo están en pausa (en su reloj: 'unscaled' si simulan sin la escala de tiempo)
            /// y la vida más larga de una partícula (lo más que hace falta ponerse al día).</summary>
            public float pausedAt, life;
            public bool unscaled;
            public float seen;
            /// <summary>Piso más bajo alrededor (hasta donde baja su sombra), medido en 'floorAt'.</summary>
            public float floor;
            public Vector3 floorAt;
            /// <summary>La caja y el barrido del último frame (gizmos).</summary>
            public Vector3 min, max;
        }

        Dyn[] dyn = new Dyn[32];
        int dynCount, dynLit, dynLoops;
        /// <summary>Lo que ya maneja esto (lo del mundo y lo dinámico): una raíz registrada dos veces, o un santuario cuyas
        /// partículas ya juntó Collect, no se toma dos veces.</summary>
        readonly HashSet<Renderer> managed = new HashSet<Renderer>();
        static readonly List<Object> pendingDyn = new List<Object>();
        static readonly List<Renderer> dynScratch = new List<Renderer>(32);
        static readonly Vector3 Pad3 = new Vector3(Margin, Margin, Margin);
        /// <summary>Cuánto puede girar el emisor (2°, en el producto de cuaterniones) antes de rearmar la cota: el módulo
        /// Shape gira con él; con 2° la caja se corre a lo sumo un 3.5 % del emisor, dentro del margen.</summary>
        const float RotSame = 0.99985f;
        /// <summary>Lo que se mueve una caja con sombra antes de volver a medir el piso debajo (m).</summary>
        const float FloorRemeasure = 2f;
        /// <summary>Sin mundo (una escena de prueba sin WorldBuilder) nadie toma lo anotado: tope para no juntar basura.</summary>
        const int MaxPending = 512;

        static void Defer(Object o)
        {
            if (pendingDyn.Count < MaxPending) pendingDyn.Add(o);
        }

        /// <summary>Al final de Collect: lo que se registró mientras se armaba el mundo.</summary>
        void FlushPending()
        {
            for (int i = 0; i < pendingDyn.Count; i++)
            {
                var o = pendingDyn[i];
                // lo destruido mientras esperaba se saltea (el == de Unity)
                if (o is GameObject g) { if (g != null) TakeAll(g); }
                else if (o is Renderer r && r != null) TakeDynamic(r);
            }
            pendingDyn.Clear();
        }

        void TakeAll(GameObject root)
        {
            root.GetComponentsInChildren(true, dynScratch);
            for (int i = 0; i < dynScratch.Count; i++) TakeDynamic(dynScratch[i]);
            dynScratch.Clear();
        }

        void TakeDynamic(Renderer r)
        {
            if (r == null || managed.Contains(r)) return;
            bool particles = r is ParticleSystemRenderer;
            // sin sombra y sin simulación que pausar no hay nada que ahorrar (ver el resumen)
            if (!particles && (!(r is MeshRenderer || r is SkinnedMeshRenderer || r is LineRenderer || r is TrailRenderer)
                               || r.shadowCastingMode == ShadowCastingMode.Off)) return;
            var ps = particles ? r.GetComponent<ParticleSystem>() : null;
            if (particles && ps == null) return;
            if (OwnedElsewhere(r.transform)) return;
            managed.Add(r);
            // una cámara que solo dibuja esta capa también tiene que contar (PrepareCameras saltea las que no ven el mundo)
            worldMask |= 1 << r.gameObject.layer;
            if (dynCount == dyn.Length) System.Array.Resize(ref dyn, dyn.Length * 2);
            dyn[dynCount++] = new Dyn
            {
                r = r, go = r.gameObject, t = r.transform, ps = ps, fresh = ps != null, on = true,
                seen = Time.unscaledTime, floorAt = Vector3.positiveInfinity, min = Vector3.positiveInfinity, max = Vector3.negativeInfinity,
            };
            dynLit++;
        }

        /// <summary>Lo de Kaito (siempre en cuadro: cada plano lo sigue a él) y lo de un enemigo (lo esconde su siesta) no se toma.</summary>
        static bool OwnedElsewhere(Transform t)
        {
            var p = Game.Player;
            if (p != null && t.IsChildOf(p.transform)) return true;
            return t.GetComponentInParent<Enemy>(true) != null;
        }

        // ================================================================== cada frame
        void TickDynamic(float now)
        {
            // de atrás para adelante: lo que sale se reemplaza por el último, que ya se miró
            for (int i = dynCount - 1; i >= 0; i--)
            {
                ref var d = ref dyn[i];
                if (Dead(ref d)) { DropDynamic(i, true); continue; }
                if (!d.r.enabled || !d.go.activeInHierarchy) continue;
                Vector3 min, max;
                if (d.ps != null)
                {
                    if (d.fresh && !FirstLook(ref d)) { DropDynamic(i, false); continue; }
                    ParticleBox(ref d, out min, out max);
                }
                else
                {
                    // su caja de ahora: CameraDirector (500) y lo que se mueve en Update o en un LateUpdate anterior ya la movieron
                    var b = d.r.bounds;
                    min = b.min - Pad3; max = b.max + Pad3;
                }
                float s = d.r.shadowCastingMode != ShadowCastingMode.Off ? DynSweep(ref d, min, max) : 0f;
                d.min = min; d.max = max;
                if (Visible(min, max, s)) { d.seen = now; if (!d.on || d.paused) Show(ref d); }
                // ya escondida: si su dueño le volvió a dar Play (los braseros al encenderse, los pétalos), otra vez en pausa
                else if (!d.on || now - d.seen > Linger) Hide(ref d);
            }
        }

        /// <summary>Destruido por su dueño (el == de Unity): el renderer, o el sistema de partículas solo.</summary>
        static bool Dead(ref Dyn d) => d.r == null || (!ReferenceEquals(d.ps, null) && d.ps == null);

        /// <summary>
        /// Primer frame de unas partículas: su dueño ya terminó de configurarlas. Las de una sola vez se terminan solas (y
        /// Unity no dibuja fuera de cuadro las que quedan) y las que la caja no puede acotar quedan siempre prendidas: las
        /// dos salen de la lista, sin haberse escondido nunca.
        /// </summary>
        bool FirstLook(ref Dyn d)
        {
            d.fresh = false;
            var m = d.ps.main;
            if (!m.loop) return false;
            d.life = CurveMax(m.startLifetime);
            d.unscaled = m.useUnscaledTime;
            Estimate(ref d, out bool unsupported);
            if (unsupported)
            {
                Debug.LogWarning($"[Nindo] ZoneCulling: las partículas '{d.r.name}' usan luces, subemisores, fuerzas externas o un emisor de malla: quedan siempre prendidas.");
                return false;
            }
            d.loop = true;
            dynLoops++;
            return true;
        }

        /// <summary>La cota de ParticleBounds (la de lo del mundo, con el mismo margen), guardada respecto del emisor.</summary>
        void Estimate(ref Dyn d, out bool unsupported)
        {
            var b = ParticleBounds(d.ps, out unsupported);
            Vector3 c = d.t.position;
            d.emin = b.min - c - Pad3;
            d.emax = b.max - c + Pad3;
            d.erot = d.t.rotation;
        }

        /// <summary>Donde puede haber partículas: la cota alrededor del emisor de ahora (se mueve con él) más lo que ocupan
        /// de verdad (las que ya se emitieron quedan donde nacieron si simulan en espacio de mundo).</summary>
        void ParticleBox(ref Dyn d, out Vector3 min, out Vector3 max)
        {
            if (Mathf.Abs(Quaternion.Dot(d.t.rotation, d.erot)) < RotSame) Estimate(ref d, out _);
            Vector3 c = d.t.position;
            min = c + d.emin; max = c + d.emax;
            if (d.measured) { min = Vector3.Min(min, d.mmin); max = Vector3.Max(max, d.mmax); }
        }

        /// <summary>Barrido de la sombra hasta el piso más bajo alrededor; el piso se vuelve a medir cada FloorRemeasure m
        /// (y se mide con la caja agrandada eso mismo: hasta entonces el piso de abajo no puede ser más bajo que el medido).</summary>
        float DynSweep(ref Dyn d, Vector3 min, Vector3 max)
        {
            Vector3 mid = (min + max) * 0.5f;
            if ((mid - d.floorAt).sqrMagnitude > FloorRemeasure * FloorRemeasure)
            {
                var e = new Vector3(FloorRemeasure, FloorRemeasure, FloorRemeasure);
                d.floorAt = mid;
                d.floor = FloorAround(min - e, max + e);
            }
            return Sweep(max.y, d.floor);
        }

        /// <summary>
        /// Prendido y, si sus partículas las pausó esto, de nuevo simulando (si alguien las paró, quedan paradas), puestas al
        /// día con un paso grande por lo que se perdieron (como el PauseAndCatchup de Unity), hasta una vida entera: después
        /// de eso el estado es el mismo. Sin esto, un brasero que se encendió o se apagó fuera de cuadro (la ola de la
        /// presentación de Kokuyō, el eclipse) aparecía con las chispas de antes congeladas en el aire, o sin ninguna.
        /// </summary>
        void Show(ref Dyn d)
        {
            if (!d.on) { d.on = true; dynLit++; d.r.forceRenderingOff = false; }
            // con el objeto apagado no se reanuda: se reanuda cuando vuelva y haga falta
            if (!d.paused || !d.go.activeInHierarchy) return;
            d.paused = false;
            if (!d.ps.isPaused) return;
            float lost = Mathf.Min((d.unscaled ? Time.unscaledTime : Time.time) - d.pausedAt, d.life);
            if (lost > CatchUpMin) d.ps.Simulate(lost, false, false, false);
            d.ps.Play(false);
        }

        /// <summary>Menos que esto (s) de pausa no se nota: se reanuda sin ponerse al día.</summary>
        const float CatchUpMin = 0.05f;

        /// <summary>Escondido y, si simula, en pausa. Solo ese sistema: uno de adentro que se registró se maneja solo. Si su
        /// dueño le da Play estando escondido, se vuelve a pausar sin olvidar desde cuándo faltaba.</summary>
        void Hide(ref Dyn d)
        {
            if (d.on) { d.on = false; dynLit--; d.r.forceRenderingOff = true; }
            if (d.ps == null || !d.ps.isPlaying) return;
            d.ps.Pause(false);
            if (!d.paused) { d.paused = true; d.pausedAt = d.unscaled ? Time.unscaledTime : Time.time; }
        }

        /// <summary>Saca el i (lo reemplaza el último). Uno que no se destruyó (de una sola vez, sin cota) sigue en
        /// 'managed': no se vuelve a tomar.</summary>
        void DropDynamic(int i, bool destroyed)
        {
            ref var d = ref dyn[i];
            if (d.on) dynLit--;
            // se le destruyó solo el sistema de partículas: el renderer que queda no se deja escondido
            else if (d.r != null) d.r.forceRenderingOff = false;
            if (d.loop) dynLoops--;
            if (destroyed) managed.Remove(d.r);
            dyn[i] = dyn[--dynCount];
            dyn[dynCount] = default;
        }

        /// <summary>
        /// Lo que ocupan de verdad las partículas registradas que están simulando (en Update, como las del mundo: los jobs
        /// de partículas de este frame todavía no arrancaron). Se reemplaza, no se agranda: una caja que solo crece seguiría
        /// para siempre a un emisor que se mueve.
        /// </summary>
        void MeasureDynamic()
        {
            for (int i = 0; i < dynCount; i++)
            {
                ref var d = ref dyn[i];
                if (!d.loop || !d.on || d.paused || Dead(ref d)) continue;
                var b = d.r.bounds;
                d.measured = b.extents.sqrMagnitude > 1e-6f;
                if (d.measured) { d.mmin = b.min - Pad3; d.mmax = b.max + Pad3; }
            }
        }

        /// <summary>Todo lo dinámico prendido y simulando (ShowAll, y el "sin" de CheckFrame).</summary>
        void ShowDynamic()
        {
            for (int i = 0; i < dynCount; i++)
            {
                ref var d = ref dyn[i];
                if (!Dead(ref d) && (!d.on || d.paused)) Show(ref d);
            }
        }

        int CountDynamicSimulating()
        {
            int n = 0;
            for (int i = 0; i < dynCount; i++) if (dyn[i].loop && dyn[i].ps != null && dyn[i].ps.isPlaying) n++;
            return n;
        }
    }
}
