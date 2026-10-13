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
    /// Se toma:
    ///  * partículas en loop. Unity ya las pausa solo fuera de cuadro (cullingMode Automatic, el de serie: "Pause" en un
    ///    loop), pero decide con la caja de las partículas que ya hay y no se pone al día: con el humo o las chispas
    ///    fuera de cuadro y el lugar adonde suben todavía a la vista, quedaban congeladas (nada entraba al cuadro) y al
    ///    volver seguían de donde quedaron, aunque el brasero se hubiera encendido o apagado mientras tanto (la ola de
    ///    la presentación de Kokuyō, el eclipse). Acá la pausa pasa a ser de esto (AlwaysSimulate mientras lo maneja; con
    ///    On = false vuelve el modo de Unity, así Benchmark compara contra el juego de antes): se decide con la cota de
    ///    ParticleBounds más lo que ocupan de verdad, como lo del mundo, y al volver se ponen al día (Show). No ahorra
    ///    simulación (simulado sobre los caminos con los 14 santuarios rezados: de 44 sistemas quedan ~0.9 simulando
    ///    explorando, contra ~0.6 con la pausa de Unity sola, porque esta caja es más grande): lo que se gana es que no
    ///    se ven ni la pausa ni la vuelta;
    ///  * mallas fijas que tiran sombra (las rocas de Gorō): escondidas salen del mapa de sombras de la luna.
    /// Una malla, una línea o una estela SIN sombra (el humo del incienso, los brillos de la puerta de los sellos y del
    /// sello de la muralla, las cuerdas de sombra, las llamas de los braseros, el filo de tinta de Kage) no se toma: Unity
    /// ya no la dibuja fuera de cuadro y no entra al mapa de sombras, así que esconderla no ahorra nada y probarla acá en
    /// cada frame costaría más de lo que le cuesta a Unity probarla. Una malla con piel tampoco: escondida, su Animator
    /// (CullUpdateTransforms) deja de escribir los huesos y el primer cuadro en que vuelve saldría con la pose de antes.
    /// Tampoco lo que cuelga de Kaito (cada plano lo sigue) ni de un enemigo (lo esconde su siesta, Enemy.SetAsleep, que
    /// se saltea lo que otro ya escondió), ni las luces: URP descarta sola las que no tocan el cuadro, ninguna de estas
    /// tira sombra y sus dueños ya las apagan de lejos (incienso 32 m, sello de la muralla 40 m, braseros 45 m); apagar
    /// una cuyo alcance toca el cuadro cambiaría la imagen.
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

        /// <summary>Cuántos de los registrados se están dibujando ahora (prendidos, con su objeto activo) y cuántos hay.
        /// Se cuenta al leer: una roca que vuelve al pool apagada no cuenta como dibujada.</summary>
        public static int DynamicOn => Instance != null ? Instance.CountDynamicOn() : 0;
        public static int DynamicTotal => Instance != null ? Instance.dynCount : 0;

        struct Dyn
        {
            public Renderer r;
            public GameObject go;
            public Transform t;
            /// <summary>Partículas (null en lo demás). 'fresh': todavía no se miró si son en loop ni su cota. 'owned': con
            /// AlwaysSimulate puesto por esto ('cull': el modo que tenían, el que les devuelve ShowAll).</summary>
            public ParticleSystem ps;
            public bool fresh, loop, owned, paused, on;
            public ParticleSystemCullingMode cull;
            /// <summary>Partículas: la parte de la cota que no depende del giro, la cota de ahora respecto del emisor (con el
            /// giro 'erot') y lo que ocupan de verdad mientras simulan (Update, cada 4 frames: en pausa, lo último medido
            /// sigue siendo donde quedaron).</summary>
            public ParticleReach reach;
            public Vector3 emin, emax, mmin, mmax;
            public Quaternion erot;
            public bool measured;
            /// <summary>Partículas, en su reloj ('unscaled' si simulan sin la escala de tiempo): desde cuándo están en pausa
            /// y cuántas había al pausarlas, hasta cuándo simulan escondidas sin pausarse (su dueño las tocó estando en
            /// pausa) y la vida más larga de una partícula (lo más que hace falta ponerse al día).</summary>
            public float pausedAt, runUntil, life;
            public int pausedCount;
            public bool unscaled;
            public float seen;
            /// <summary>Piso más bajo alrededor (hasta donde baja su sombra), medido en 'floorAt'.</summary>
            public float floor;
            public Vector3 floorAt;
            /// <summary>La caja y el barrido del último frame (gizmos).</summary>
            public Vector3 min, max;
        }

        Dyn[] dyn = new Dyn[32];
        int dynCount, dynLoops;
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
            // solo lo que esconder ahorra o mejora (ver el resumen): partículas, o una malla fija que tira sombra
            var ps = r is ParticleSystemRenderer ? r.GetComponent<ParticleSystem>() : null;
            if (ps == null && !(r is MeshRenderer && r.shadowCastingMode != ShadowCastingMode.Off)) return;
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
                    // también al volver de On = false (ShowAll les devolvió su modo)
                    if (!d.owned) Own(ref d);
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
                // ya escondida se sigue mirando: su dueño puede haberle dado Play o emitido a mano (Hide)
                else if (!d.on || now - d.seen > Linger) Hide(ref d);
            }
        }

        /// <summary>Destruido por su dueño (el == de Unity): el renderer, o el sistema de partículas solo.</summary>
        static bool Dead(ref Dyn d) => d.r == null || (!ReferenceEquals(d.ps, null) && d.ps == null);

        /// <summary>El reloj en que simulan esas partículas.</summary>
        static float Clock(ref Dyn d) => d.unscaled ? Time.unscaledTime : Time.time;

        /// <summary>
        /// Primer frame de unas partículas: su dueño ya terminó de configurarlas. Las de una sola vez se terminan solas (y
        /// Unity no dibuja fuera de cuadro las que quedan) y las que la caja no puede acotar quedan siempre prendidas: las
        /// dos salen de la lista, sin haberse escondido nunca y con su modo de Unity.
        /// </summary>
        bool FirstLook(ref Dyn d)
        {
            d.fresh = false;
            var m = d.ps.main;
            if (!m.loop) return false;
            d.reach = MeasureReach(d.ps, out bool unsupported);
            if (unsupported)
            {
                Debug.LogWarning($"[Nindo] ZoneCulling: las partículas '{d.r.name}' usan luces, subemisores, fuerzas externas o un emisor de malla: quedan siempre prendidas.");
                return false;
            }
            d.life = d.reach.life;
            d.unscaled = m.useUnscaledTime;
            d.cull = m.cullingMode;
            Place(ref d);
            d.loop = true;
            dynLoops++;
            return true;
        }

        /// <summary>La pausa de fuera de cuadro pasa a ser de esto: con la de Unity debajo (la caja justa, sin ponerse al
        /// día) quedarían congeladas cada vez que sus partículas salen de cuadro y la caja de acá todavía no.</summary>
        static void Own(ref Dyn d)
        {
            var m = d.ps.main;
            m.cullingMode = ParticleSystemCullingMode.AlwaysSimulate;
            d.owned = true;
        }

        static void Release(ref Dyn d)
        {
            var m = d.ps.main;
            m.cullingMode = d.cull;
            d.owned = false;
        }

        /// <summary>La cota de ParticleBounds (la de lo del mundo, con el mismo margen) donde está el emisor, guardada respecto de él.</summary>
        static void Place(ref Dyn d)
        {
            var b = PlaceReach(d.t, d.reach);
            Vector3 c = d.t.position;
            d.emin = b.min - c - Pad3;
            d.emax = b.max - c + Pad3;
            d.erot = d.t.rotation;
        }

        /// <summary>Donde puede haber partículas: la cota alrededor del emisor de ahora (se mueve con él; si giró, se rearma
        /// sin leer los módulos) más lo que ocupan de verdad (las que ya se emitieron quedan donde nacieron si simulan en
        /// espacio de mundo).</summary>
        static void ParticleBox(ref Dyn d, out Vector3 min, out Vector3 max)
        {
            if (Mathf.Abs(Quaternion.Dot(d.t.rotation, d.erot)) < RotSame) Place(ref d);
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
        /// día por lo que se perdieron, hasta una vida entera (después de eso el estado es el mismo). En pasos de a lo sumo
        /// CatchStep: en uno solo la gravedad y el ruido se aplicarían una vez a toda la vida y, si Unity no reparte lo que
        /// emite dentro del paso, las partículas nacerían juntas (en un modelo de Euler con el ruido muestreado una vez
        /// por paso: con un paso de 4 s la columna de humo del brasero sale 1.8-2.3 m más baja, y las dos del brillo de la
        /// ceniza en fase, que se apaga una vez por ciclo; con pasos de 0.25 s queda a menos de 0.2 m de la de 1/60 s).
        /// Si su dueño emitió en este mismo frame
        /// estando en pausa (Braziers.Flare), no se pone al día: envejecería lo recién nacido.
        /// </summary>
        static void Show(ref Dyn d)
        {
            if (!d.on) { d.on = true; d.r.forceRenderingOff = false; }
            // con el objeto apagado no se reanuda: se reanuda cuando vuelva y haga falta
            if (!d.paused || !d.go.activeInHierarchy) return;
            d.paused = false;
            if (!d.ps.isPaused) return;
            if (d.ps.particleCount <= d.pausedCount)
            {
                float lost = Mathf.Min(Clock(ref d) - d.pausedAt, d.life);
                if (lost > CatchUpMin)
                {
                    int k = Mathf.Min(MaxCatchSteps, Mathf.CeilToInt(lost / CatchStep));
                    for (int j = 0; j < k; j++) d.ps.Simulate(lost / k, false, false, false);
                }
            }
            d.ps.Play(false);
        }

        /// <summary>Menos que esto (s) de pausa no se nota: se reanuda sin ponerse al día. El paso más largo al ponerse al
        /// día y cuántos como mucho (la vida más larga, la del humo del brasero, es 4 s: 16 pasos de 0.25 s).</summary>
        const float CatchUpMin = 0.05f, CatchStep = 0.25f;
        const int MaxCatchSteps = 16;

        /// <summary>
        /// Escondido y, si simula, en pausa (solo ese sistema: uno de adentro que se registró se maneja solo). Si su dueño
        /// lo toca estando en pausa (le da Play: la lluvia de pétalos; o emite a mano: Braziers.Flare), sigue escondido pero
        /// simulando una vida antes de volver a pausarse: lo nuevo no queda quieto en el emisor, al volver no se envejece
        /// de más y lo que emitió (las chispas del destello suben casi 9 m, la cota llega a 6.6) lo sigue la caja medida. Uno
        /// parado con StopEmitting (la llamita del incienso que apaga Douse) no se pausa: se consume solo en menos de una
        /// vida, y el Play de Show lo volvería a hacer emitir.
        /// </summary>
        static void Hide(ref Dyn d)
        {
            if (d.on) { d.on = false; d.r.forceRenderingOff = true; }
            if (d.ps == null) return;
            float clock = Clock(ref d);
            if (d.paused)
            {
                if (d.ps.isPaused)
                {
                    int n = d.ps.particleCount;
                    // igual que al pausarlo (o menos: su dueño las borró)
                    if (n <= d.pausedCount) { d.pausedCount = n; return; }
                    d.ps.Play(false);
                }
                // lo paró su dueño: queda parado
                else if (!d.ps.isPlaying) { d.paused = false; return; }
                d.paused = false;
                d.runUntil = clock + d.life;
                return;
            }
            if (clock < d.runUntil || !d.ps.isPlaying || !d.ps.isEmitting) return;
            d.ps.Pause(false);
            d.paused = true;
            d.pausedAt = clock;
            d.pausedCount = d.ps.particleCount;
        }

        /// <summary>Saca el i (lo reemplaza el último). Uno que no se destruyó (de una sola vez, sin cota) sigue en
        /// 'managed': no se vuelve a tomar.</summary>
        void DropDynamic(int i, bool destroyed)
        {
            ref var d = ref dyn[i];
            // se le destruyó solo el sistema de partículas: el renderer que queda no se deja escondido
            if (!d.on && d.r != null) d.r.forceRenderingOff = false;
            if (d.loop) dynLoops--;
            if (destroyed) managed.Remove(d.r);
            dyn[i] = dyn[--dynCount];
            dyn[dynCount] = default;
        }

        /// <summary>
        /// Lo que ocupan de verdad las partículas registradas que están simulando, escondidas o no (en Update, como las del
        /// mundo: los jobs de partículas de este frame todavía no arrancaron). Escondidas también: lo que su dueño emitió
        /// con velocidad propia (Braziers.Flare) va más allá de la cota. Simulado: con el margen de 1.5 m, una chispa del
        /// destello nunca sale de la caja medida 4 frames antes, ni a 30 fps. Se reemplaza, no se agranda: una caja que solo
        /// crece seguiría para siempre a un emisor que se mueve.
        /// </summary>
        void MeasureDynamic()
        {
            for (int i = 0; i < dynCount; i++)
            {
                ref var d = ref dyn[i];
                if (!d.loop || d.paused || Dead(ref d) || !d.go.activeInHierarchy) continue;
                var b = d.r.bounds;
                d.measured = b.extents.sqrMagnitude > 1e-6f;
                if (d.measured) { d.mmin = b.min - Pad3; d.mmax = b.max + Pad3; }
            }
        }

        /// <summary>Todo lo dinámico prendido, simulando y con su modo de Unity (ShowAll: On = false, el componente apagado).</summary>
        void ShowDynamic()
        {
            for (int i = 0; i < dynCount; i++)
            {
                ref var d = ref dyn[i];
                if (Dead(ref d)) continue;
                if (!d.on || d.paused) Show(ref d);
                if (d.owned) Release(ref d);
            }
        }

        /// <summary>El "sin" de CheckFrame: lo escondido se dibuja (a 'shown', que RunCheck vuelve a esconder) sin reanudar
        /// ni ponerse al día: las pausadas se dibujan quietas, y lo que se está midiendo no cambia por medirlo.</summary>
        void ShowDynamicForCheck(List<Renderer> shown)
        {
            for (int i = 0; i < dynCount; i++)
            {
                ref var d = ref dyn[i];
                if (d.on || Dead(ref d)) continue;
                d.r.forceRenderingOff = false;
                shown.Add(d.r);
            }
        }

        int CountDynamicOn()
        {
            int n = 0;
            for (int i = 0; i < dynCount; i++)
            {
                ref var d = ref dyn[i];
                if (d.on && !Dead(ref d) && d.r.enabled && d.go.activeInHierarchy) n++;
            }
            return n;
        }

        int CountDynamicSimulating()
        {
            int n = 0;
            for (int i = 0; i < dynCount; i++)
            {
                ref var d = ref dyn[i];
                if (d.loop && !Dead(ref d) && Simulating(d.ps, d.r)) n++;
            }
            return n;
        }
    }
}
