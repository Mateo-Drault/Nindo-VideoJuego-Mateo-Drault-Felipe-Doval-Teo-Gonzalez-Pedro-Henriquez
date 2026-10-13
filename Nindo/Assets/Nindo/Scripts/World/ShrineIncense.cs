using System.Collections;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// El incensario (kōro) de un santuario. Apagado no brilla nada: el santuario se ilumina como el resto del mundo
    /// (antes una luz propia de 1.2-2.4, la luz cálida del manifest, la ceniza y el frente emisivos y el humo de
    /// FXFactory lo volvían una mancha encendida que no dejaba leer el modelo). Cuando Kaito reza ahí por primera vez
    /// queda su incienso clavado en la ceniza con la brasa, dos hilos de humo y una luz cálida muy leve, y así queda en
    /// la partida (SaveData.shrines). La secuencia del rezo (StoryDirector.Shrines) usa MakeStick, Light y Place.
    /// </summary>
    public class ShrineIncense : MonoBehaviour
    {
        /// <summary>Centro de la ceniza en coordenadas del prop (props_misc.py: KORO_Y -0.69, KORO_ASH_Z 0.305).</summary>
        public static readonly Vector3 AshLocal = new Vector3(0f, 0.305f, 0.69f);
        /// <summary>Largo del manojo (prop incense_stick, origen abajo) y cuánto se hunde en la ceniza.</summary>
        public const float StickLength = 0.25f, StickSink = 0.045f;
        /// <summary>Alto de las dos columnas de humo ya en el incensario (m sobre la brasa).</summary>
        const float SmokeHeight = 1.35f, SmokeHeight2 = 0.95f;
        /// <summary>La luz cálida solo se prende con Kaito a menos de esto: casi todos los santuarios quedan lejos.</summary>
        const float LightRadius = 32f;
        static readonly Color GlowColor = new Color(1f, 0.64f, 0.32f);
        const float GlowIntensity = 0.9f, GlowRange = 2.6f;

        Checkpoint cp;
        Transform socket, tip;
        IncenseSmoke smoke, smoke2;
        Light glow;
        ParticleSystem motes, ashGlow;
        float glowK, glowTarget, checkTimer;
        bool near;

        public Transform Socket => socket;
        public bool Lit { get; private set; }

        public static bool IsLit(string id) => Game.Save.shrines != null && Game.Save.shrines.Contains(id);

        public static ShrineIncense Attach(Checkpoint cp)
        {
            var s = cp.gameObject.AddComponent<ShrineIncense>();
            s.cp = cp;
            s.socket = new GameObject("Ceniza").transform;
            s.socket.SetParent(cp.transform, false);
            s.socket.localPosition = AshLocal;
            return s;
        }

        void Start()
        {
            // al cargar la partida: los santuarios donde ya rezó, con su incienso (sin destello ni sonido)
            if (cp != null && IsLit(cp.id)) ShowLit();
        }

        // ================================================================== el manojo
        /// <summary>Un manojo nuevo, sin padre, con un hijo "Punta" en el extremo de arriba (brasa y humo).</summary>
        public static Transform MakeStick()
        {
            var model = Game.Content != null ? Game.Content.Prop("incense_stick") : null;
            GameObject go;
            if (model != null) go = Instantiate(model);
            else
            {
                // sin el prop: tres varitas verdes igual que las del modelo
                go = new GameObject("incense_stick");
                var mpb = new MaterialPropertyBlock();
                mpb.SetColor("_BaseColor", new Color(0.35f, 0.48f, 0.23f));
                for (int i = -1; i <= 1; i++)
                {
                    var v = GameObject.CreatePrimitive(PrimitiveType.Cube);
                    Destroy(v.GetComponent<Collider>());
                    v.transform.SetParent(go.transform, false);
                    v.transform.localScale = new Vector3(0.012f, StickLength, 0.012f);
                    v.transform.localPosition = new Vector3(i * 0.009f, StickLength * 0.5f, 0f);
                    v.transform.localRotation = Quaternion.Euler(0f, 0f, -i * 3.5f);
                    v.GetComponent<MeshRenderer>().SetPropertyBlock(mpb);
                }
            }
            go.name = "Incienso";
            foreach (var r in go.GetComponentsInChildren<Renderer>()) r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            var t = new GameObject("Punta").transform;
            t.SetParent(go.transform, false);
            t.localPosition = new Vector3(0f, StickLength, 0f);
            return go.transform;
        }

        static Transform Tip(Transform stick) => stick != null ? stick.Find("Punta") : null;

        /// <summary>
        /// Lo prende el espíritu de la bandana: un chispazo dorado en la punta, la brasa y un hilo de humo corto que la
        /// sigue mientras está en la mano. 'flame': con una llamita que después apaga Douse (PrayIncense la apaga con
        /// dos abanicos de la mano; si nadie la apaga, Place).
        /// </summary>
        public void Light(Transform stick, bool flame = false, int sparks = 9)
        {
            var t = Tip(stick);
            if (t == null) return;
            IncenseEmber.Create(t, Vector3.zero);
            if (flame) IncenseFlame.Create(t);
            Spark(t.position, sparks);
            smoke = IncenseSmoke.Create(transform, t, Vector3.zero, 0.3f, 0.07f, 1f, Random.Range(0f, 10f));
            smoke.moving = true;
            smoke.Fade(true, 0.6f);
            // un fósforo, no un golpe: el sello que estalla en la muralla tiene que seguir siendo lo más fuerte
            Game.Audio?.Play("incense_light", t.position, 0.6f);
        }

        /// <summary>Apaga la llamita de la punta (queda la brasa).</summary>
        public void Douse(Transform stick) => IncenseFlame.Douse(Tip(stick));

        void Spark(Vector3 p, int count)
        {
            Game.FX?.FlashLight(p, new Color(1f, 0.82f, 0.45f), 2.2f, 2.2f, 0.3f);
            if (motes == null) motes = MakeMotes();
            motes.transform.position = p;
            motes.Emit(count);
        }

        /// <summary>Lo clava en la ceniza en 'seconds' (desde donde lo tenga la mano) y arranca el humo del santuario.</summary>
        public void Place(Transform stick, float seconds)
        {
            if (stick == null) return;
            // apagado ya: Destroy espera al final del cuadro y su LateUpdate lo volvería a la mano
            var hold = stick.GetComponent<IncenseHold>();
            if (hold != null) { hold.enabled = false; Destroy(hold); }
            Douse(stick);
            stick.SetParent(socket, true);
            StartCoroutine(PlaceRoutine(stick, seconds));
        }

        IEnumerator PlaceRoutine(Transform stick, float seconds)
        {
            Vector3 p0 = stick.localPosition;
            Quaternion r0 = stick.localRotation;
            Vector3 p1 = Vector3.down * StickSink;
            Quaternion r1 = Quaternion.Euler(-3f, 0f, 2f);   // apenas torcido: clavado a mano
            float t = 0f;
            while (t < seconds && stick != null)
            {
                t += Time.deltaTime;
                float k = Mathf.SmoothStep(0f, 1f, t / seconds);
                stick.localPosition = Vector3.Lerp(p0, p1, k);
                stick.localRotation = Quaternion.Slerp(r0, r1, k);
                yield return null;
            }
            if (stick == null) yield break;
            stick.localPosition = p1; stick.localRotation = r1;
            Settle(stick, false);
            // un soplo de ceniza y la luz cálida se enciende despacio
            Game.FX?.Dust(socket.position + Vector3.up * 0.02f, 0.25f);
        }

        /// <summary>Estado final: el manojo en la ceniza, brasa, humo (cinta alta y una más tenue) y la luz cálida.</summary>
        void Settle(Transform stick, bool instant)
        {
            Lit = true;
            tip = Tip(stick);
            if (tip != null && tip.Find("Brasa") == null) IncenseEmber.Create(tip, Vector3.zero);
            if (smoke == null) smoke = IncenseSmoke.Create(transform, tip, Vector3.zero, instant ? SmokeHeight : 0.3f, 0.11f, 1f, Random.Range(0f, 10f));
            smoke.moving = false;
            smoke.SetSource(tip, Vector3.zero);
            smoke.SetHeight(SmokeHeight, instant ? 0f : 2.2f);
            smoke.Fade(true, instant ? 0f : 0.5f);
            if (smoke2 == null) smoke2 = IncenseSmoke.Create(transform, tip, new Vector3(0.012f, 0f, 0f), instant ? SmokeHeight2 : 0.1f, 0.08f, 0.5f, Random.Range(10f, 20f));
            smoke2.SetHeight(SmokeHeight2, instant ? 0f : 3f);
            smoke2.Fade(true, instant ? 0f : 2.5f);
            EnsureGlow();
            glowTarget = 1f;
            if (instant) glowK = 1f;
            if (ashGlow == null) ashGlow = MakeAshGlow();
        }

        /// <summary>
        /// La ceniza encendida: un halo cálido de 0.45 m que respira despacio sobre el incensario. Desde la cámara de juego
        /// el humo es un hilo de 2 px sobre la piedra clara y la luz no llega al cuerpo del santuario: sin esto no se
        /// distinguía uno rezado de uno apagado. Tenue (alfa 0.4, lejos del umbral del bloom), como pide el santuario que
        /// no brille; con 0.3 m y alfa 0.3 la maqueta desde la cámara de juego no se distinguía del apagado.
        /// </summary>
        ParticleSystem MakeAshGlow()
        {
            var ps = FXFactory.NewSystem("BrilloDeLaCeniza", socket);
            ps.transform.localPosition = Vector3.up * AshGlowHeight;
            var m = ps.main;
            m.loop = true; m.duration = 1f; m.playOnAwake = true;
            m.simulationSpace = ParticleSystemSimulationSpace.Local;
            m.startLifetime = AshGlowCycle;
            m.startSpeed = 0f;
            m.startSize = new ParticleSystem.MinMaxCurve(AshGlowSize * 0.9f, AshGlowSize * 1.1f);
            m.startColor = AshGlowColor;
            m.maxParticles = 4;
            // dos a la vez, a destiempo: el brillo sube y baja sin código por cuadro
            var em = ps.emission; em.rateOverTime = 2f / AshGlowCycle;
            var sh = ps.shape; sh.enabled = false;
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                      new[] { new GradientAlphaKey(0f, 0f), new GradientAlphaKey(1f, 0.5f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            // ya respirando al cargar la partida o al terminar de clavarlo
            ps.Simulate(AshGlowCycle, true, true);
            ps.Play();
            return ps;
        }

        const float AshGlowHeight = 0.05f, AshGlowCycle = 2.6f, AshGlowSize = 0.45f;
        static readonly Color AshGlowColor = new Color(1f, 0.56f, 0.24f, 0.4f);

        /// <summary>Al cargar la partida: directo al estado final.</summary>
        public void ShowLit()
        {
            if (Lit) return;
            var stick = MakeStick();
            stick.SetParent(socket, false);
            stick.localPosition = Vector3.down * StickSink;
            stick.localRotation = Quaternion.Euler(-3f, 0f, 2f);
            Settle(stick, true);
        }

        /// <summary>
        /// Sin tomar el incienso con la mano (el rezo corto en un santuario nuevo, o sin el clip PrayIncense): el manojo
        /// aparece clavado en la ceniza entre un soplo de humo y lo prende el chispazo de la bandana.
        /// </summary>
        public void KindleInPlace()
        {
            if (Lit) return;
            var stick = MakeStick();
            stick.SetParent(socket, false);
            stick.localPosition = Vector3.down * StickSink;
            stick.localRotation = Quaternion.Euler(-3f, 0f, 2f);
            Game.FX?.SmokePuff(socket.position + Vector3.up * 0.12f, 0.22f);
            // desde la cámara de juego (Kaito de 100 px) el chispazo tiene que leerse: el doble de chispas
            Light(stick, false, 20);
            Settle(stick, false);
        }

        /// <summary>Kaito pasó cerca y el santuario quedó como punto de reaparición: unas motas doradas suben del incensario.</summary>
        public void Awaken()
        {
            Vector3 p = socket.position + Vector3.up * 0.15f;
            Game.FX?.FlashLight(p, new Color(1f, 0.85f, 0.5f), 1.6f, 3f, 0.6f);
            if (motes == null) motes = MakeMotes();
            motes.transform.position = p;
            motes.Emit(14);
        }

        ParticleSystem MakeMotes()
        {
            var ps = FXFactory.NewSystem("MotasDelSantuario", transform);
            var m = ps.main;
            m.loop = false; m.playOnAwake = false;
            m.startLifetime = new ParticleSystem.MinMaxCurve(0.7f, 1.4f);
            m.startSpeed = new ParticleSystem.MinMaxCurve(0.1f, 0.45f);
            m.startSize = new ParticleSystem.MinMaxCurve(0.025f, 0.06f);
            m.startColor = new ParticleSystem.MinMaxGradient(BandanaGlow.Gold, new Color(1f, 0.95f, 0.75f));
            m.gravityModifier = -0.18f;
            m.maxParticles = 40;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Sphere; sh.radius = 0.08f;
            var noise = ps.noise; noise.enabled = true; noise.strength = 0.25f; noise.frequency = 1.3f;
            var col = ps.colorOverLifetime; col.enabled = true;
            var g = new Gradient();
            g.SetKeys(new[] { new GradientColorKey(Color.white, 0f), new GradientColorKey(Color.white, 1f) },
                      new[] { new GradientAlphaKey(1f, 0f), new GradientAlphaKey(0f, 1f) });
            col.color = g;
            return ps;
        }

        // ================================================================== luz cálida
        void EnsureGlow()
        {
            if (glow != null) return;
            var lg = new GameObject("LuzDelIncienso");
            lg.transform.SetParent(transform, false);
            // delante del incensario y un poco arriba: baña la ceniza, el escalón y el frente del santuario
            lg.transform.localPosition = AshLocal + new Vector3(0f, 0.32f, 0.22f);
            glow = lg.AddComponent<Light>();
            glow.type = LightType.Point; glow.color = GlowColor; glow.range = GlowRange; glow.intensity = 0f;
            glow.shadows = LightShadows.None;
            glow.enabled = false;
        }

        void Update()
        {
            if (glow == null) return;
            checkTimer -= Time.unscaledDeltaTime;
            if (checkTimer <= 0f)
            {
                checkTimer = 0.5f;
                var p = Game.Player;
                near = p != null && (p.transform.position - transform.position).sqrMagnitude < LightRadius * LightRadius;
            }
            glowK = Mathf.MoveTowards(glowK, glowTarget, Time.deltaTime / 1.6f);
            bool on = near && glowK > 0.01f;
            if (glow.enabled != on) glow.enabled = on;
            // late con la brasa, muy poco
            if (on) glow.intensity = GlowIntensity * glowK * (0.9f + 0.1f * Mathf.PerlinNoise(Time.time * 2.3f, transform.position.x));
        }
    }
}
