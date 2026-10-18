using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Lo que una caña del claro HACE en la pelea de Chikuō (lo que ES vive en World/ArenaStalk): el resorte del arco con
    /// el viejo encima, la carga (el ensō blanco de tinta en la base y el nudo que brilla: "cortá acá"), el latigazo, la
    /// inclinación de la fase 2, la rajadura y la quebradura de la fase 3 y la tala. Diseño: chikuo_v2.md, secciones 2 y 8.3.
    /// El arco es un vector en el plano (grados por eje del mundo): cambiar de dirección no le pega un tirón a la caña.
    /// </summary>
    public sealed class BambooStalk
    {
        public readonly ArenaStalk S;
        public string Id => S.Id;
        public Vector3 Base => S.Base;
        public bool IsMother => S.IsMother;

        /// <summary>Resorte del arco (sección 8.3): 1.4 Hz, amortiguado 0.15. Pasos fijos: igual a cualquier framerate.</summary>
        const float Omega = 2f * Mathf.PI * 1.4f, Zeta = 0.15f, Step = 1f / 120f;
        /// <summary>La Madre (Ø 0.40) se arquea a esta parte de lo que pide la carga y nunca se quiebra.</summary>
        const float MotherBend = 0.3f;

        Vector2 bend, vel, target;
        float acc, wobbleAmp, wobbleHz, wobbleUntil;
        // inclinación (fase 2) y vuelta (cambio 2): una interpolación propia, no el resorte (con 0.15 se pasaba a 110°)
        Vector2 tweenFrom, tweenTo;
        float tweenT = -1f, tweenLen, even, evenFrom, evenTo;
        bool leaning;

        /// <summary>Fase 3: 1 = rajada, 2 = quebrada (cae hacia afuera; queda el tocón).</summary>
        public int Cracks { get; private set; }
        /// <summary>Quebrada o talada: no se posa ni estampa.</summary>
        public bool Fallen { get; private set; }
        public bool Leaning => leaning;
        /// <summary>En pie y recta: se puede posar en ella, estampar contra ella y latigarla.</summary>
        public bool Standing => !Fallen && !leaning && S.Rise >= 0.999f && S.gameObject.activeInHierarchy;

        // la carga: el ensō de la base y el nudo blanco
        bool loaded;
        float loadedFor, loadLen;
        public bool Loaded => loaded;

        // la pieza que cae (quebradura hacia afuera, tala hacia Kaito)
        readonly Transform piece;
        Quaternion pieceFrom;
        Vector3 pieceAxis;
        float pieceT;
        /// <summary>La tala: la pieza toca el piso a este tiempo (Time.time); -1 si no hay tala en curso.</summary>
        public float FellImpactAt { get; private set; } = -1f;

        // ensō: un quad con el pincel de los avisos (shader Nindo/Telegraph, modo anillo)
        readonly Transform enso;
        readonly MeshRenderer ensoR;
        readonly MaterialPropertyBlock mpb = new MaterialPropertyBlock();
        float ensoAlpha, ensoSeed;

        /// <summary>Radio del ensō blanco (m): fuera del cuerpo del viejo sentado al pie y de la cápsula de la raíz.</summary>
        public const float EnsoRadius = 1.2f;
        public static readonly Color White = new Color(0.92f, 0.97f, 1f);
        static readonly int IdColor = Shader.PropertyToID("_Color"), IdHotColor = Shader.PropertyToID("_HotColor"), IdInk = Shader.PropertyToID("_Ink"),
            IdMode = Shader.PropertyToID("_Mode"), IdProgress = Shader.PropertyToID("_Progress"), IdHot = Shader.PropertyToID("_Hot"),
            IdFlash = Shader.PropertyToID("_Flash"), IdDanger = Shader.PropertyToID("_Danger"), IdAlpha = Shader.PropertyToID("_Alpha"),
            IdRadius = Shader.PropertyToID("_Radius"), IdWidth = Shader.PropertyToID("_Width"), IdDot = Shader.PropertyToID("_Dot"),
            IdMinPx = Shader.PropertyToID("_MinPx"), IdOutcome = Shader.PropertyToID("_Outcome"), IdOutT = Shader.PropertyToID("_OutT"),
            IdSeed = Shader.PropertyToID("_Seed");

        public BambooStalk(ArenaStalk s, Mesh quad, Material ensoMat, Transform parent)
        {
            S = s;
            piece = s.BreakPiece;
            if (quad != null && ensoMat != null)
            {
                var go = new GameObject("Enso_" + s.Id);
                go.transform.SetParent(parent, false);
                go.AddComponent<MeshFilter>().sharedMesh = quad;
                ensoR = go.AddComponent<MeshRenderer>();
                ensoR.sharedMaterial = ensoMat;
                ensoR.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                ensoR.receiveShadows = false;
                ensoR.enabled = false;
                enso = go.transform;
            }
            ensoSeed = Random.value * 10f;
        }

        // ------------------------------------------------------------------ estado por fase (reintentos)
        /// <summary>Como empieza la fase (0..2): en la 2 las seis inclinadas hacia afuera; en la 3 rectas y la Madre de pie;
        /// sin rajaduras ni piezas caídas.</summary>
        public void ResetFor(int phase)
        {
            S.ResetState();
            bend = vel = target = Vector2.zero;
            wobbleUntil = 0f;
            tweenT = -1f;
            even = 0f;
            leaning = false;
            Cracks = 0;
            Fallen = false;
            loaded = markOn = false;
            ensoAlpha = 0f;
            if (ensoR != null) ensoR.enabled = false;
            pieceActive = false;
            FellImpactAt = -1f;
            if (IsMother) S.SetRise(phase >= 2 ? 1f : 0f);
            else if (phase == 1)
            {
                Lean(true, 0f);
                Wobble(2f, 136f / 60f, 9999f);
            }
        }

        // ------------------------------------------------------------------ el arco
        /// <summary>La carga de la acción: 'degrees' hacia 'dir' (plano). El resorte la persigue.</summary>
        public void SetLoad(float degrees, Vector3 dir)
        {
            Vector3 d = dir.Flat();
            if (d.sqrMagnitude < 1e-6f) { target = Vector2.zero; return; }
            d.Normalize();
            float k = IsMother ? MotherBend : 1f;
            target = new Vector2(d.x, d.z) * degrees * k;
        }

        /// <summary>Tiembla alrededor de la carga (la risa ±10°, la inclinación de la fase 2 con la música ±2°).</summary>
        public void Wobble(float degrees, float hz, float seconds)
        {
            wobbleAmp = degrees * (IsMother ? MotherBend : 1f);
            wobbleHz = hz;
            wobbleUntil = Time.time + seconds;
        }

        /// <summary>El latigazo: el resorte se suelta para el otro lado (se ve el chicotazo) y oscila.</summary>
        public void Whip()
        {
            vel += -bend * Omega * 1.6f;
            target = Vector2.zero;
            S.KickChimes(new Vector3(-bend.x, 0f, -bend.y).normalized * 6f);
        }

        /// <summary>Un sacudón corto (el corte sin campanas, el estampado contra ella): 'degrees/s' hacia 'dir'.</summary>
        public void Shake(Vector3 dir, float degPerSec)
        {
            Vector3 d = dir.Flat().normalized;
            vel += new Vector2(d.x, d.z) * degPerSec * (IsMother ? MotherBend : 1f);
            S.KickChimes(d * 3f);
        }

        /// <summary>Inclinada 70° hacia afuera (fase 2) en 'seconds', o de vuelta a la vertical (el "fuush" del cambio 2).</summary>
        public void Lean(bool on, float seconds)
        {
            if (IsMother) return;
            leaning = on;
            Vector3 o = S.Outward;
            tweenFrom = bend;
            tweenTo = on ? new Vector2(o.x, o.z) * 70f : Vector2.zero;
            evenFrom = even;
            evenTo = on ? 1f : 0f;
            tweenLen = Mathf.Max(0.001f, seconds);
            tweenT = 0f;
            vel = Vector2.zero;
            target = Vector2.zero;
            if (seconds <= 0f) { bend = tweenTo; even = evenTo; tweenT = -1f; Apply(); }
        }

        /// <summary>Cada frame (desde el Update del jefe, antes del LateUpdate de ArenaStalk: los cascabeles del posado
        /// se mueven con el arco de este frame).</summary>
        public void Tick(float dt)
        {
            if (pieceActive) TickPiece(dt);
            // quebrada no se arquea (el tocón)
            if (Fallen) { TickEnso(dt); return; }
            if (tweenT >= 0f)
            {
                tweenT += dt;
                float u = Mathf.Clamp01(tweenT / tweenLen);
                // la vuelta a la vertical es un latigazo (sale rápido y frena); la inclinación, pareja
                float e = leaning ? Mathf.SmoothStep(0f, 1f, u) : 1f - (1f - u) * (1f - u) * (1f - u);
                bend = Vector2.Lerp(tweenFrom, tweenTo, e);
                even = Mathf.Lerp(evenFrom, evenTo, e);
                if (u >= 1f)
                {
                    tweenT = -1f;
                    // al enderezarse sigue de largo un poco: el resorte se lleva la velocidad del final
                    if (!leaning) vel = (tweenTo - tweenFrom).normalized * -Omega * 4f;
                }
            }
            else if (!leaning)
            {
                acc = Mathf.Min(acc + dt, Step * 6f);
                Vector2 goal = target;
                if (Time.time < wobbleUntil)
                {
                    Vector2 dir = target.sqrMagnitude > 0.01f ? target.normalized : Vector2.right;
                    goal += dir * (wobbleAmp * Mathf.Sin(Time.time * wobbleHz * 2f * Mathf.PI));
                }
                while (acc >= Step)
                {
                    acc -= Step;
                    vel += (-(Omega * Omega) * (bend - goal) - 2f * Zeta * Omega * vel) * Step;
                    bend += vel * Step;
                }
            }
            else if (Time.time < wobbleUntil)
            {
                // inclinada: tiembla con la música sin el resorte
                Vector3 o = S.Outward;
                bend = new Vector2(o.x, o.z) * (70f + wobbleAmp * Mathf.Sin(Time.time * wobbleHz * 2f * Mathf.PI));
            }
            Apply();
            TickEnso(dt);
        }

        void Apply()
        {
            float deg = bend.magnitude;
            Vector3 dir = deg > 1e-3f ? new Vector3(bend.x, 0f, bend.y) / deg : Vector3.forward;
            S.SetBend(deg, dir, even);
        }

        /// <summary>Velocidad del arco (grados/s): el latigazo que despide al viejo.</summary>
        public float BendSpeed => vel.magnitude;

        // ------------------------------------------------------------------ la carga
        /// <summary>Prende (o apaga) la carga: el ensō blanco en la base y el nudo de la base en blanco. 'seconds' es lo
        /// que va a durar (en el último cuarto el trazo se afina: no es un reloj, es un "acá" que avisa que se va).</summary>
        public void SetLoaded(bool on, float seconds = 1f)
        {
            if (on == loaded && !on) return;
            loaded = on;
            loadedFor = 0f;
            loadLen = Mathf.Max(0.1f, seconds);
            if (!on) S.SetGlint(Color.black);
        }

        /// <summary>Un destello blanco en el nudo de la base sin carga: "acá cae" (la caña de destino de un salto).</summary>
        public void Mark(bool on)
        {
            markOn = on;
            if (!on && !loaded) S.SetGlint(Color.black);
        }

        bool markOn;

        void TickEnso(float dt)
        {
            bool show = (loaded || markOn) && !Fallen;
            ensoAlpha = Mathf.MoveTowards(ensoAlpha, show ? 1f : 0f, dt / (show ? 0.08f : 0.18f));
            if (loaded)
            {
                loadedFor += dt;
                // pulso de 4 Hz en el nudo de la base (las campanas del viejo laten igual: BambooMasterLook)
                float pulse = 0.5f + 0.5f * Mathf.Sin(loadedFor * 4f * 2f * Mathf.PI);
                S.SetGlint(White * Mathf.Lerp(2.2f, 4.5f, pulse));
            }
            else if (markOn) S.SetGlint(White * 2.4f);
            if (ensoR == null) return;
            if (ensoAlpha <= 0f) { if (ensoR.enabled) ensoR.enabled = false; return; }
            ensoR.enabled = Settings.CombatAids >= 1;
            Vector3 p = Base;
            const float half = EnsoRadius * 1.7f + 0.3f;
            enso.SetPositionAndRotation(p + Vector3.up * 0.06f, Quaternion.Euler(0f, ensoSeed * 36f, 0f));
            enso.localScale = new Vector3(half * 2f, 1f, half * 2f);
            // en el último cuarto de la carga el trazo se afina
            float thin = loaded ? Mathf.InverseLerp(0.75f, 1f, loadedFor / loadLen) : 0f;
            float width = 0.14f * 0.5f * 1.25f * Mathf.Lerp(1f, 0.45f, thin);
            mpb.Clear();
            mpb.SetColor(IdColor, White);
            mpb.SetColor(IdHotColor, White);
            mpb.SetColor(IdInk, TellStyle.Ink);
            mpb.SetFloat(IdMode, 0f);
            // abierto (0.86): no se cierra nunca, no es un reloj
            mpb.SetFloat(IdProgress, 0.86f);
            mpb.SetFloat(IdHot, 0.6f);
            mpb.SetFloat(IdFlash, 0f);
            mpb.SetFloat(IdDanger, 0f);
            mpb.SetFloat(IdAlpha, ensoAlpha * (markOn && !loaded ? 0.7f : 1f));
            mpb.SetFloat(IdRadius, EnsoRadius / half);
            mpb.SetFloat(IdWidth, width / half);
            mpb.SetFloat(IdDot, 0.125f / half);
            mpb.SetFloat(IdMinPx, 14f);
            mpb.SetFloat(IdOutcome, 0f);
            mpb.SetFloat(IdOutT, 0f);
            mpb.SetFloat(IdSeed, ensoSeed);
            ensoR.SetPropertyBlock(mpb);
        }

        // ------------------------------------------------------------------ rajadura, quebradura, tala (fase 3)
        /// <summary>Un latigazo de la fase 3 la raja; el segundo la quiebra (cae hacia afuera del claro). La Madre no.
        /// Devuelve true si se quebró.</summary>
        public bool Crack()
        {
            if (IsMother || Fallen) return false;
            Cracks++;
            if (Cracks == 1) { S.SetCracked(true); return false; }
            BeginFall(S.Outward, false, FallTime);
            return true;
        }

        /// <summary>La tala: la caña rajada cae hacia 'dir' (carril rojo del largo de la caña), queda tumbada 5 s y se
        /// deshace en hojas. Devuelve cuándo toca el piso (s desde ahora).</summary>
        public void Fell(Vector3 dir, float seconds)
        {
            BeginFall(dir, true, seconds);
        }

        /// <summary>Tiempo que tarda la pieza en caer (la tala lo usa para su golpe).</summary>
        public const float FallTime = 0.62f;
        const float FellLie = 5f;

        void BeginFall(Vector3 dir, bool felled, float seconds)
        {
            fallTime = Mathf.Max(0.2f, seconds);
            Fallen = true;
            loaded = markOn = false;
            S.SetGlint(Color.black);
            S.Occupied = false;
            bend = vel = target = Vector2.zero;
            S.SetBend(0f, Vector3.forward);
            if (piece == null) { S.SetBroken(true, false); return; }
            S.SetBroken(true, true);
            fallDir = dir.Flat().normalized;
            pieceAxis = Vector3.Cross(Vector3.up, fallDir);
            pieceFrom = piece.rotation;
            // hasta que la punta toca el piso: pasa la horizontal lo que el tocón la levanta
            float len = Mathf.Max(1f, S.Length - ArenaStalk.CutHeight);
            fallDeg = 90f + Mathf.Asin(Mathf.Clamp01(ArenaStalk.CutHeight / len)) * Mathf.Rad2Deg;
            pieceActive = true;
            pieceT = 0f;
            FellImpactAt = felled ? Time.time + fallTime : -1f;
            lieFor = fallTime + (felled ? FellLie : 0.5f);
            Game.Audio?.Play(felled ? "bamboo_fall" : "bamboo_break", Base + Vector3.up, 1f, 0.05f);
            BambooGrove.Splinters(Base + Vector3.up * ArenaStalk.CutHeight, fallDir);
        }

        float fallDeg, lieFor, fallTime = FallTime;
        Vector3 fallDir;
        bool pieceActive;

        void TickPiece(float dt)
        {
            pieceT += dt;
            // cae como una vara: acelera (u²) hasta tocar el piso y rebota apenas
            float u = Mathf.Clamp01(pieceT / fallTime);
            float a = pieceT <= fallTime ? fallDeg * u * u : fallDeg - 3f * Mathf.Sin(Mathf.Clamp01((pieceT - fallTime) / 0.25f) * Mathf.PI);
            piece.rotation = Quaternion.AngleAxis(a, pieceAxis) * pieceFrom;
            if (pieceT >= fallTime && pieceT - dt < fallTime)
            {
                Vector3 tip = Base + fallDir * (S.Length * 0.6f);
                Game.FX?.Dust(tip, 1.6f);
                Game.Camera?.Shake(0.25f);
                Game.Audio?.Play("rock_impact", tip, 0.6f, 0.1f);
                FellImpactAt = -1f;
            }
            if (pieceT < lieFor) return;
            // se deshace en hojas y queda el tocón (ResetFor la vuelve a parar: SetBend escribe el giro de cada tramo)
            BambooGrove.Leaves(Base + fallDir * (S.Length * 0.4f) + Vector3.up * 0.6f, 1.6f);
            S.SetBroken(true, false);
            pieceActive = false;
        }
    }
}
