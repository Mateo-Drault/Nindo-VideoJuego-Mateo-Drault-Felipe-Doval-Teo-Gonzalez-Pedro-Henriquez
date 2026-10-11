using System.Collections;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Puerta del dojo con los tres huecos de los sellos. Cada hueco tiene grabado en oro (en el prop dojo_gate) el
    /// mismo pictograma que su sello en el HUD; mirando el portón, montaña a la izquierda, lago al centro y bambú a la
    /// derecha, como en el HUD. Los sellos se ponen de a uno, apenas se tienen (SaveData.sealsPlaced): el grabado de un
    /// sello que Kaito ya tiene y todavía no puso late dorado y llama desde lejos; puesto, el medallón queda en su hueco
    /// con un aro de luz tenue. Con los tres, la luz corre de un sello al otro (como la raya del HUD) y la puerta se abre
    /// (StoryDirector.SealGate). Antes los huecos eran troncos de piedra macizos y el medallón colocado quedaba enterrado
    /// adentro: se veían tres discos lisos.
    /// El marcador está en el centro del portón, al pie, con el mismo frame que el prop (forward hacia afuera).
    /// </summary>
    public class SealGate : Interactable
    {
        // medidas del prop en coordenadas del portón (build_dojo_gate / seal_socket en props_structures.py): frente del
        // tablero en z 1.59, centro de los huecos a 5.07 de alto, grabado hasta z 1.624, aro de piedra hasta z 1.67
        const float BoardZ = 1.59f, SocketY = 5.07f, IconZ = BoardZ + 0.037f, RingZ = BoardZ + 0.083f;
        /// <summary>Centro del medallón (0.15 de espesor) apoyado delante del fondo del hueco; su origen está en la base.</summary>
        const float MedallionZ = BoardZ + 0.099f, MedallionBase = 0.25f;
        /// <summary>Lado del pictograma grabado (SEAL_ICON_SIDE) y del aro de luz (el aro del sprite Ring está al 86 %).</summary>
        const float IconSide = 0.40f, RingSide = 0.744f;
        /// <summary>Mirando el portón la izquierda es +X del portón: montaña, lago, bambú (el orden de SealId y del HUD).</summary>
        static readonly float[] SocketX = { 1.15f, 0f, -1.15f };
        static readonly string[] SealProps = { "key_seal_mountain", "key_seal_lake", "key_seal_bamboo" };
        /// <summary>
        /// Kaito se para entre 3.6 y 4.6 m del tablero (donde esté, si ya está en ese rango: no camina para atrás), corrido
        /// hacia el hueco que va a llenar. Más cerca, el medallón sube casi vertical y el plano no entra.
        /// </summary>
        const float StandNear = 3.6f, StandOut = 4.6f, StandShift = 0.45f;
        /// <summary>Más lejos que esto (m a la cámara) los brillos no se actualizan ni se dibujan.</summary>
        const float DrawDistance = 80f;

        static readonly int BaseColorId = Shader.PropertyToID("_BaseColor"), ColorId = Shader.PropertyToID("_Color"),
            HoleFadeId = Shader.PropertyToID("_NindoHoleFade");
        static readonly Color Gold = new Color(1f, 0.74f, 0.3f, 1f);
        static Mesh quad;
        static Material ringMat, linkMat;
        static readonly Material[] iconMats = new Material[3];

        readonly GameObject[] medallions = new GameObject[3];
        readonly MeshRenderer[] decals = new MeshRenderer[3], rings = new MeshRenderer[3];
        readonly float[] flash = new float[3];
        readonly bool[] flying = new bool[3];
        MeshRenderer link;
        float linkFill, front = 1f;
        MaterialPropertyBlock mpb;
        bool drawn = true;
        string lastPrompt;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { quad = null; ringMat = null; linkMat = null; for (int i = 0; i < 3; i++) iconMats[i] = null; }

        // ================================================================== partida
        /// <summary>¿Está puesto? Una partida con la puerta ya abierta (de antes de poner de a uno) los tiene todos.</summary>
        public static bool IsPlaced(SaveData s, SealId id) => s.HasFlag(Flags.DojoOpen) || s.SealPlaced(id);

        /// <summary>Sellos que Kaito tiene y todavía no puso.</summary>
        public static int PendingCount(SaveData s)
        {
            int n = 0;
            for (int i = 0; i < 3; i++) if (s.HasSeal((SealId)i) && !IsPlaced(s, (SealId)i)) n++;
            return n;
        }

        public static int PlacedCount(SaveData s)
        {
            int n = 0;
            for (int i = 0; i < 3; i++) if (IsPlaced(s, (SealId)i)) n++;
            return n;
        }

        /// <summary>El primer sello que tiene y no puso (para el cartel y el objetivo); -1 si ninguno.</summary>
        public static int FirstPending(SaveData s)
        {
            for (int i = 0; i < 3; i++) if (s.HasSeal((SealId)i) && !IsPlaced(s, (SealId)i)) return i;
            return -1;
        }

        // ================================================================== ciclo de vida
        void Awake()
        {
            prompt = "Examinar la puerta";
            // el cartel sale a 6.5 m del centro (4.9 m del tablero): llegando por la rampa se aprieta antes de quedar abajo
            radius = 6.5f;
            promptHeight = 2.2f;
            mpb = new MaterialPropertyBlock();
        }

        void Start()
        {
            for (int i = 0; i < 3; i++)
            {
                decals[i] = Quad("Grabado_" + (SealId)i, IconMaterial(i), new Vector3(SocketX[i], SocketY, IconZ), IconSide);
                rings[i] = Quad("Aro_" + (SealId)i, RingMaterial, new Vector3(SocketX[i], SocketY, RingZ), RingSide);
                if (IsPlaced(Game.Save, (SealId)i)) Seat((SealId)i);
            }
            link = Quad("Lazo", LinkMaterial, new Vector3(0f, SocketY, RingZ + 0.004f), 1f);
            if (Game.Save.HasFlag(Flags.DojoOpen)) linkFill = 1f;
            ApplyLink();
            RefreshPrompt();
        }

        public override bool CanInteract
        {
            get
            {
                // ni en plena pelea (los guardias del dojo están al pie de la rampa)
                if (Game.Save.HasFlag(Flags.DojoOpen) || Game.InCutscene || (Game.Combat != null && Game.Combat.InCombat)) return false;
                // solo desde afuera (del lado de los huecos)
                var p = Game.Player;
                return p == null || transform.InverseTransformPoint(p.transform.position).z > 0.5f;
            }
        }

        public override void Interact(PlayerController p) => Game.Story?.OpenSealGate(this);

        /// <summary>El cartel dice qué va a pasar: el sello que va a poner, los sellos, abrir, o mirar qué falta.</summary>
        void RefreshPrompt()
        {
            var s = Game.Save;
            int pending = PendingCount(s);
            string want = pending == 1 ? StoryText.PlaceSealPrompt((SealId)FirstPending(s))
                : pending > 1 ? StoryText.PlaceSealsPrompt
                : PlacedCount(s) >= 3 ? StoryText.OpenGatePrompt : StoryText.ExamineGatePrompt;
            if (!ReferenceEquals(want, lastPrompt)) { prompt = want; lastPrompt = want; }
        }

        void Update()
        {
            // el cartel solo importa cerca (FindBest no mira más allá del radio)
            var pl = Game.Player;
            if (pl != null && (pl.transform.position - transform.position).sqrMagnitude < (radius + 3f) * (radius + 3f)) RefreshPrompt();
            var cam = Game.Camera != null ? Game.Camera.transform : null;
            bool near = cam == null || (cam.position - transform.position).sqrMagnitude < DrawDistance * DrawDistance;
            if (near != drawn)
            {
                drawn = near;
                for (int i = 0; i < 3; i++) { decals[i].enabled = near; rings[i].enabled = near; }
                link.enabled = near && linkFill > 0f;
            }
            if (!near) return;
            var s = Game.Save;
            bool open = s.HasFlag(Flags.DojoOpen);
            float t = Time.time;
            // con Kaito del lado del patio la cámara de juego ve el portón por delante y lo abre en trama alrededor de él:
            // los medallones se disuelven con el tablero (MakeMedallion), los brillos aditivos no, así que se apagan
            bool inFront = pl == null || transform.InverseTransformPoint(pl.transform.position).z > 0.3f;
            front = Mathf.MoveTowards(front, inFront ? 1f : 0f, Time.deltaTime / 0.4f);
            for (int i = 0; i < 3; i++)
            {
                var id = (SealId)i;
                flash[i] = Mathf.MoveTowards(flash[i], 0f, Time.deltaTime / 0.9f);
                bool placed = medallions[i] != null && !flying[i];
                float icon = 0f, ring;
                if (placed) ring = (open ? 0.5f : 0.32f) + flash[i] * 1.4f;
                else if (s.HasSeal(id))
                {
                    // late despacio y cada hueco a su ritmo: llama desde lejos sin parecer una alarma; mientras su
                    // medallón vuela se enciende entero
                    float pulse = 0.5f + 0.5f * Mathf.Sin(t * 3.4f + i * 1.9f);
                    icon = flying[i] ? 1f : 0.32f + 0.4f * pulse;
                    ring = flying[i] ? 0.5f : 0.08f + 0.12f * pulse;
                }
                else ring = 0f;
                SetGlow(decals[i], icon * front);
                SetGlow(rings[i], ring * front);
            }
            if (linkFill > 0f && Mathf.Abs(front - linkFront) > 0.01f) { linkFront = front; ApplyLink(); }
        }
        float linkFront = 1f;

        void SetGlow(MeshRenderer r, float k)
        {
            bool on = k > 0.005f;
            if (r.enabled != on) r.enabled = on;
            if (!on) return;
            var c = Gold * Mathf.Min(k, 2f);
            c.a = 1f;
            mpb.SetColor(BaseColorId, c);
            mpb.SetColor(ColorId, c);
            r.SetPropertyBlock(mpb);
        }

        // ================================================================== dónde
        /// <summary>Centro del medallón del sello en su hueco (mundo).</summary>
        public Vector3 SocketPosition(SealId s) => transform.TransformPoint(new Vector3(SocketX[(int)s], SocketY, MedallionZ));

        /// <summary>Hacia afuera del portón (hacia el que llega).</summary>
        public Vector3 Front => transform.forward;

        /// <summary>La izquierda de Kaito cuando mira el portón (+X del portón).</summary>
        public Vector3 Left => transform.right;

        /// <summary>Dónde se para Kaito para poner el sello, desde donde está 'from' (al pie: la altura la pone el terreno).</summary>
        public Vector3 StandPoint(SealId s, Vector3 from)
        {
            float z = Mathf.Clamp(transform.InverseTransformPoint(from).z, BoardZ + StandNear, BoardZ + StandOut);
            return transform.TransformPoint(new Vector3(SocketX[(int)s] * StandShift, 0f, z));
        }

        /// <summary>Punto en el medio del tablero (altura de los huecos).</summary>
        public Vector3 BoardCenter => transform.TransformPoint(new Vector3(0f, SocketY, BoardZ));

        /// <summary>X del hueco en el portón (+ = izquierda mirando el portón).</summary>
        public static float SocketSide(SealId s) => SocketX[(int)s];

        // ================================================================== medallones
        /// <summary>
        /// El medallón aparece flotando en 'at' (crece desde nada con un destello) mirando hacia afuera del portón, como
        /// va a quedar; se mece de lado a lado hasta que Fly lo manda a su hueco.
        /// </summary>
        public void Summon(SealId s, Vector3 at)
        {
            int i = (int)s;
            if (medallions[i] == null) medallions[i] = MakeMedallion(i);
            flying[i] = true;
            if (hover[i] != null) StopCoroutine(hover[i]);
            hover[i] = StartCoroutine(Hover(medallions[i].transform, at));
            Game.FX?.FlashLight(at, Gold, 3f, 3f, 0.4f);
            Game.Audio?.Play("seal", at, 0.45f);
        }

        readonly Coroutine[] hover = new Coroutine[3];

        IEnumerator Hover(Transform t, Vector3 center)
        {
            Vector3 down = transform.up * MedallionBase;   // el origen del medallón está en su base
            float k = 0f;
            while (t != null)
            {
                k += Time.deltaTime;
                t.localScale = Vector3.one * Mathf.Lerp(0.2f, 1f, UIAnim.OutCubic(Mathf.Clamp01(k / 0.35f)));
                t.SetPositionAndRotation(center - down + transform.up * (Mathf.Sin(k * 2.6f) * 0.04f),
                                         transform.rotation * Quaternion.Euler(0f, Mathf.Sin(k * 1.7f) * 22f, 0f));
                yield return null;
            }
        }

        /// <summary>
        /// Vuela a su hueco en 'seconds' por el mismo arco que la luz de la bandana (BandanaStream.Arc), girando hasta
        /// quedar de frente, y se encastra con un golpe de luz. 'onSeat' corre en el cuadro en que entra.
        /// </summary>
        public IEnumerator Fly(SealId s, float seconds, System.Action onSeat)
        {
            int i = (int)s;
            var t = medallions[i] != null ? medallions[i].transform : null;
            if (hover[i] != null) { StopCoroutine(hover[i]); hover[i] = null; }
            if (t == null) { Seat(s); onSeat?.Invoke(); yield break; }
            Vector3 up = transform.up * MedallionBase;
            Vector3 a = t.position + up, b = SocketPosition(s);
            Quaternion r0 = t.rotation, r1 = transform.rotation;
            var trail = Trail(t);
            float k = 0f;
            while (k < 1f)
            {
                k = Mathf.Min(1f, k + Time.deltaTime / seconds);
                // sale despacio de la mano, acelera y frena al llegar (la última décima casi quieta: se lee que encastra)
                float u = Mathf.SmoothStep(0f, 1f, k);
                Vector3 p = BandanaStream.Arc(a, b, u);
                // una vuelta entera sobre su eje mientras vuela (el oro del canto destella); entera: con una vuelta y
                // media arrancaba dado vuelta 180° de golpe
                Quaternion spin = Quaternion.Euler(0f, (1f - u) * 360f, 0f);
                t.SetPositionAndRotation(p - up, Quaternion.Slerp(r0, r1, u) * spin);
                t.localScale = Vector3.one;
                yield return null;
            }
            trail.emitting = false;
            Seat(s);
            flash[i] = 1f;
            Game.FX?.SealGlow(b + Front * 0.25f);
            Game.Audio?.Play("seal", b, 1f);
            Game.Camera?.Shake(0.22f);
            onSeat?.Invoke();
            StartCoroutine(Clunk(t));
        }

        /// <summary>Al encastrar entra un centímetro y vuelve (se siente el peso).</summary>
        IEnumerator Clunk(Transform t)
        {
            Vector3 p = t.localPosition, inward = Vector3.back * 0.012f;
            float k = 0f;
            while (k < 1f && t != null)
            {
                k += Time.deltaTime / 0.22f;
                t.localPosition = p + inward * Mathf.Sin(Mathf.Clamp01(k) * Mathf.PI);
                yield return null;
            }
            if (t != null) t.localPosition = p;
        }

        /// <summary>El medallón en su hueco, ya (al cargar la partida o si la escena se corta).</summary>
        public void Seat(SealId s)
        {
            int i = (int)s;
            if (medallions[i] == null) medallions[i] = MakeMedallion(i);
            if (hover[i] != null) { StopCoroutine(hover[i]); hover[i] = null; }
            flying[i] = false;
            var t = medallions[i].transform;
            t.localPosition = new Vector3(SocketX[i], SocketY - MedallionBase, MedallionZ);
            t.localRotation = Quaternion.identity;
            t.localScale = Vector3.one;
        }

        GameObject MakeMedallion(int i)
        {
            var model = Game.Content != null ? Game.Content.Prop(SealProps[i]) : null;
            GameObject go;
            if (model != null) go = Instantiate(model, transform);
            else
            {
                go = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                Destroy(go.GetComponent<Collider>());
                go.transform.SetParent(transform, false);
                var c = GameObject.CreatePrimitive(PrimitiveType.Cylinder).transform;
                Destroy(c.GetComponent<Collider>());
                go.GetComponent<MeshRenderer>().enabled = false;
                c.SetParent(go.transform, false);
                c.localPosition = Vector3.up * MedallionBase;
                c.localRotation = Quaternion.Euler(90f, 0f, 0f);
                c.localScale = new Vector3(0.5f, 0.07f, 0.5f);
                c.GetComponent<MeshRenderer>().sharedMaterial = FXMaterials.Flash;
            }
            go.name = SealProps[i];
            foreach (var c in go.GetComponentsInChildren<Collider>()) Destroy(c);
            // con los materiales "disolvibles" del mundo y la disolución del hueco siempre puesta: cuando el portón
            // tapa a Kaito (pasando por el vano) el tablero se abre en trama alrededor de él y los medallones con él;
            // si no, quedaban flotando enteros en medio del agujero. Fuera del cono no cambia nada (lo dice el shader)
            foreach (var r in go.GetComponentsInChildren<MeshRenderer>())
            {
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                var mats = r.sharedMaterials;
                bool any = false;
                for (int k = 0; k < mats.Length; k++)
                {
                    var f = CameraOcclusion.FadeVariant(mats[k]);
                    if (f != null) { mats[k] = f; any = true; }
                }
                if (!any) continue;
                r.sharedMaterials = mats;
                var b = new MaterialPropertyBlock();
                b.SetFloat(HoleFadeId, 0.82f);
                r.SetPropertyBlock(b);
            }
            return go;
        }

        /// <summary>La estela dorada sale del centro del medallón (su origen está en la base).</summary>
        static TrailRenderer Trail(Transform medallion)
        {
            var tr = medallion.GetComponentInChildren<TrailRenderer>();
            if (tr == null)
            {
                var go = new GameObject("Estela");
                go.transform.SetParent(medallion, false);
                go.transform.localPosition = Vector3.up * MedallionBase;
                tr = go.AddComponent<TrailRenderer>();
            }
            tr.time = 0.35f;
            tr.minVertexDistance = 0.05f;
            tr.widthCurve = new AnimationCurve(new Keyframe(0f, 0.22f), new Keyframe(1f, 0f));
            tr.colorGradient = TrailGradient;
            tr.sharedMaterial = FXMaterials.Additive;
            tr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            tr.receiveShadows = false;
            tr.emitting = true;
            tr.Clear();
            return tr;
        }

        static Gradient trailGradient;
        static Gradient TrailGradient
        {
            get
            {
                if (trailGradient != null) return trailGradient;
                trailGradient = new Gradient();
                trailGradient.SetKeys(new[] { new GradientColorKey(new Color(1f, 0.9f, 0.6f), 0f), new GradientColorKey(Gold, 1f) },
                                      new[] { new GradientAlphaKey(0.9f, 0f), new GradientAlphaKey(0f, 1f) });
                return trailGradient;
            }
        }

        // ================================================================== los tres
        /// <summary>
        /// La luz corre de izquierda a derecha por el tablero uniendo los tres sellos (la raya dorada del HUD); cada hueco
        /// destella cuando la luz lo alcanza.
        /// </summary>
        public IEnumerator LinkUp(float seconds)
        {
            float t = 0f;
            bool[] hit = new bool[3];
            while (t < seconds)
            {
                t += Time.deltaTime;
                linkFill = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / seconds));
                ApplyLink();
                // el frente de la luz va de +X (izquierda) a -X; los huecos están en 1.15, 0, -1.15 sobre 2.6 m de raya
                float head = 1.3f - linkFill * 2.6f;
                for (int i = 0; i < 3; i++)
                    if (!hit[i] && head <= SocketX[i] + 0.05f)
                    {
                        hit[i] = true;
                        flash[i] = 1f;
                        Vector3 p = SocketPosition((SealId)i) + Front * 0.25f;
                        Game.FX?.FlashLight(p, Gold, 6f, 6f, 0.6f);
                        Game.Audio?.Play("seal", p, 0.55f);
                    }
                yield return null;
            }
            linkFill = 1f;
            ApplyLink();
        }

        void ApplyLink()
        {
            if (link == null) return;
            if (linkFill <= 0.001f) { link.enabled = false; return; }
            // anclada a la izquierda (+X): crece hacia la derecha descubriendo el trazo (la u se recorta, no se aplasta);
            // 7 cm de alto, a la altura de los aros
            const float full = 2.6f;
            var t = link.transform;
            t.localScale = new Vector3(full * linkFill, 0.07f, 1f);
            t.localPosition = new Vector3(full * 0.5f - full * linkFill * 0.5f, SocketY, RingZ + 0.004f);
            linkBlock ??= new MaterialPropertyBlock();
            var c = Gold * (0.9f * front);
            c.a = 1f;
            link.enabled = drawn && front > 0.01f;
            linkBlock.SetColor(BaseColorId, c);
            linkBlock.SetColor(ColorId, c);
            linkBlock.SetVector(BaseMapStId, new Vector4(linkFill, 1f, 0f, 0f));
            link.SetPropertyBlock(linkBlock);
        }

        static readonly int BaseMapStId = Shader.PropertyToID("_BaseMap_ST");
        MaterialPropertyBlock linkBlock;

        // ================================================================== piezas
        MeshRenderer Quad(string name, Material m, Vector3 local, float side)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            go.transform.localPosition = local;
            go.transform.localScale = Vector3.one * side;
            go.AddComponent<MeshFilter>().sharedMesh = QuadMesh;
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = m;
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            r.receiveShadows = false;
            r.enabled = false;
            return r;
        }

        /// <summary>Cuadrado de 1 m que mira a +Z (hacia afuera del portón), con la u hacia la derecha de quien lo mira.</summary>
        static Mesh QuadMesh
        {
            get
            {
                if (quad != null) return quad;
                quad = new Mesh { name = "Nindo_SealQuad" };
                quad.vertices = new[] { new Vector3(0.5f, -0.5f, 0f), new Vector3(-0.5f, -0.5f, 0f), new Vector3(-0.5f, 0.5f, 0f), new Vector3(0.5f, 0.5f, 0f) };
                quad.uv = new[] { new Vector2(0f, 0f), new Vector2(1f, 0f), new Vector2(1f, 1f), new Vector2(0f, 1f) };
                quad.colors = new[] { Color.white, Color.white, Color.white, Color.white };
                quad.triangles = new[] { 3, 2, 1, 3, 1, 0 };
                quad.RecalculateNormals();
                quad.RecalculateBounds();
                return quad;
            }
        }

        /// <summary>Aditivo con el pictograma del HUD: el contorno de tinta del sprite es negro y no suma; brilla el relleno.</summary>
        static Material IconMaterial(int i)
        {
            if (iconMats[i] != null) return iconMats[i];
            return iconMats[i] = SpriteMaterial("Nindo_SealIcon_" + (SealId)i, UISprites.Get(UISprites.SealIconName((SealId)i)));
        }

        static Material RingMaterial => ringMat != null ? ringMat : (ringMat = SpriteMaterial("Nindo_SealRing", UISprites.Ring));
        static Material LinkMaterial => linkMat != null ? linkMat : (linkMat = SpriteMaterial("Nindo_SealLink", UISprites.BrushLine));

        static Material SpriteMaterial(string name, Sprite s)
        {
            var m = new Material(FXMaterials.Additive) { name = name };
            if (s == null) return m;   // sin el sprite queda el punto suave del material de efectos
            var tex = s.texture;
            var r = s.textureRect;
            var scale = new Vector2(r.width / tex.width, r.height / tex.height);
            var off = new Vector2(r.x / tex.width, r.y / tex.height);
            foreach (var p in new[] { "_BaseMap", "_MainTex" })
                if (m.HasProperty(p)) { m.SetTexture(p, tex); m.SetTextureScale(p, scale); m.SetTextureOffset(p, off); }
            return m;
        }
    }
}
