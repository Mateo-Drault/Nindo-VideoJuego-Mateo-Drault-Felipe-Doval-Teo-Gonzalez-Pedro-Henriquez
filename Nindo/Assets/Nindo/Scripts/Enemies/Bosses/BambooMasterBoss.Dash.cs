using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// El paso del viento (embestida roja con imágenes residuales). Dos maneras de llegar, elegidas en la suelta:
    ///  * de frente (DashStrike): con Kaito lejos (desde LeapFrom), el vuelo se escala para que la mano frene sobre él;
    ///  * al costado (DashStrike_Pass, la variante que pasa): con Kaito demasiado cerca para frenar con medio vuelo (lo
    ///    normal: viene corriendo durante el salto atrás), apunta a su izquierda, vuela por al lado girando en el aire, lo
    ///    corta DE FRENTE en el cruce y cae mirándolo. Antes atravesaba a Kaito con la estocada de frente: en el impacto la
    ///    mano apuntaba lejos de él, los cuerpos se metían uno en el otro y terminaba de espaldas, con el golpe siguiente
    ///    girando 150° sobre los pies.
    /// El carril del aviso es el que toma (no gira en la suelta) y el golpe cae en tl.T, cuando lo dice el "¡ya!".
    /// </summary>
    public partial class BambooMasterBoss
    {
        // embestida: carril fijo desde la suelta (del aviso 'laneTell'; laneT0 = lo avanzado hasta ahí)
        bool laneFixed;
        int laneTell;
        Vector3 laneO, laneD;
        float laneT0;
        // la que pasa al costado: cuánto apunta al costado antes de la suelta (0..1), si salió esa variante, y cuánto corrige
        // el giro en el aire para caer mirando a Kaito (grados, una vez en el contacto)
        Quaternion passRot;
        float passW, passDelta;
        bool passing, passDeltaSet;

        /// <summary>De centro a centro en el cruce: medido en la pose de vuelo, el cuerpo queda a más de ~0.3 m del eje de
        /// Kaito (con 0.85, la suma de los dos radios, el brazo y la pierna de atrás pasaban por adentro). Kaito queda a la
        /// derecha del maestro (el clip corta con la derecha).</summary>
        const float PassBeside = 1.15f;
        /// <summary>Lo que tiene que estar Kaito al costado del carril en la suelta para que vaya la variante que pasa (si se
        /// metió en el carril, de frente frena contra él: la red de seguridad de Travel).</summary>
        const float PassMinLat = 0.6f;
        /// <summary>La cadera apenas pasada de Kaito en el contacto (m por el carril).</summary>
        const float PassOver = 0.1f;
        /// <summary>Cuánto tarda en pasar de apuntarle de frente a apuntarle al costado (s).</summary>
        const float PassBlend = 0.15f;
        /// <summary>El arco del corte en el cruce (ya lo mira) y el margen de alcance de la mano o del bastón.</summary>
        const float PassArc = 100f, PassReachPad = 0.2f;
        /// <summary>Lo más que corrige el giro en el aire para caer mirándolo (grados).</summary>
        const float PassDeltaMax = 50f;
        /// <summary>Lo que el carril de la que pasa cubre afuera de Kaito (m más allá de él) y del lado del cuerpo.</summary>
        const float PassLaneOut = 0.45f, PassLaneIn = 0.2f;

        /// <summary>Lo más largo que estira el vuelo y lo más corto que se escala el de frente (2.85 m de los 5.7 autorados:
        /// más cerca le pasa al costado) y el que pasa. Con 0.1 cada embestida contra el bot "bueno" volaba x0.10.</summary>
        const float DashMaxStretch = 1.4f, DashMinStretch = 0.5f, PassMinStretch = 0.2f;
        /// <summary>El vuelo más corto en tiempo: con el borde de la arena encima el de frente puede quedar en x0.1, y con el
        /// tiempo frenado en la mitad volaba a la quinta parte de su velocidad (cámara lenta con fantasmas).</summary>
        const float DashMinFlight = 0.1f;

        void BeginDashStep()
        {
            passRot = transform.rotation;
            passW = passDelta = 0f;
            passing = passDeltaSet = false;
        }

        /// <summary>
        /// Embestida: en la suelta el carril queda fijo hacia donde mira (el que dibujó el aviso) y se elige cómo llega;
        /// salen las imágenes residuales (DashStart → DashEnd, en jade pálido: la estela de alguien rápido, no un aviso).
        /// La que pasa gira el transform en el vuelo (el giro del clip, como el avance) y lo corta en el cruce; la de frente
        /// pega con la mano sobre él. Las dos empujan a Kaito desde el maestro: la que pasa lo saca del carril hacia afuera y
        /// lo deja mirándolo (empujarlo por el carril lo daba vuelta de espaldas y lo tiraba contra el cuerpo del jefe).
        /// </summary>
        void TickDash(AttackDef a, float dt)
        {
            if (!laneFixed) AimPass(dt);
            if (!laneFixed && stepClock >= tl.ReleaseTime) ReleaseDash();
            // el vuelo corto espera agachado un poco más (CompressFlight): Enemy lo seguiría girando hacia Kaito hasta la
            // suelta nueva, y el carril ya está dibujado
            if (LaneLive) transform.rotation = DashFacing();
            float start = clip.Event("DashStart"), end = clip.Event("DashEnd");
            if (!dashFx && start >= 0f && stepNorm >= start)
            {
                dashFx = true;
                // lo que tarda la suelta en ir de DashStart a DashEnd (el clip va a releaseRate en ese tramo)
                float dur = Mathf.Max(0.08f, tl.tR * (Mathf.Max(end, start) - start) / Mathf.Max(0.01f, clip.Contact - clip.Apex));
                Game.FX?.AfterImages(model, dur, Mathf.Min(0.04f, dur / 3f), GhostJade);
                Game.FX?.DashBurst(transform.position, laneD);
                Game.Audio?.Play("dash", transform.position, 1f, 0.05f);
            }
            if (passing && !passDeltaSet && stepNorm >= clip.Contact) PlanLanding();
            if (stepHit || target == null || stepNorm < a.activeStart || stepNorm > a.activeEnd) return;
            Vector3 tp = target.transform.position;
            if (passing)
            {
                // el cruce: lo mira y lo tiene al alcance de la mano (o del bastón); el que se corrió hacia afuera no
                if (!CombatMath.InArc(transform, tp, clip.Reach + PassReachPad, PassArc, target.Radius)) return;
            }
            else
            {
                if (!InLane(tp, target.Radius * 0.5f)) return;
                // sobre el carril desde la salida hasta la mano (el que se metió por detrás de la salida no)
                float s = Vector3.Dot((tp - laneO).Flat(), laneD), flown = travelDone - laneT0;
                if (s < -target.Radius || s - target.Radius > flown + clip.Reach + 0.3f) return;
            }
            stepHit = true;
            var r = HitPlayer(a, transform.position);
            if (passing && (r == HitResult.Hit || r == HitResult.Killed)) WindCut(tp);
        }

        /// <summary>La suelta: el carril queda fijo y se elige la variante. Pasa al costado si venía apuntándole al costado,
        /// Kaito sigue a un lado del carril y el vuelo entero entra en la arena; si no, de frente.</summary>
        void ReleaseDash()
        {
            laneFixed = true;
            laneTell = TellId;
            laneO = transform.position;
            laneT0 = travelDone;
            laneD = transform.forward.Flat().normalized;
            // en la suelta cuenta lo que Kaito sigue corriendo hasta el contacto
            float lead = Mathf.Max(0f, tl.T - stepClock);
            var pc = PassClip;
            if (pc != null && passW > 0.5f && target != null)
            {
                float lat = Vector3.Dot((target.transform.position - laneO).Flat(), Vector3.Cross(Vector3.up, laneD));
                float k = PlanPass(pc, laneO, laneD, lead);
                if (lat > PassMinLat && Stretched(pc, 1f, k) - laneT0 <= ArenaRoom(laneO, laneD) - 0.5f)
                {
                    passing = true;
                    clip = pc;
                    // mismos cuadros hasta la suelta: se cambia sin fundido (como las variantes de paso de PickReach)
                    anim.Play(pc.State, 0f, stepNorm);
                    airStretch = k;
                    CompressFlight(k, PassMinStretch);
                    return;
                }
            }
            airStretch = PlanDash(laneO, laneD, lead);
            CompressFlight(airStretch, DashMinFlight);
        }

        /// <summary>La variante que pasa al costado del clip de este paso (null si el FBX no la tiene: sale de frente).</summary>
        MasterClip PassClip
        {
            get
            {
                if (clip == null || string.IsNullOrEmpty(clip.Pass) || !anim.HasState(clip.Pass)) return null;
                return BambooMasterTimings.Get(clip.Pass);
            }
        }

        /// <summary>
        /// Hasta la suelta apunta a Kaito (el mismo giro amortiguado que la puntería de Enemy, que este paso reemplaza, y
        /// quieto en los últimos TrackingStopLead s). Si de frente no le entraría medio vuelo (con lo que viene corriendo),
        /// apunta a su izquierda lo justo para pasarle a PassBeside: el carril del aviso ya es el que va a tomar (girarlo en
        /// la suelta lo hacía saltar). Antes decidía por la distancia de ese cuadro: al que entraba corriendo desde 5-6 m le
        /// apuntaba de frente y el vuelo de la mitad lo atravesaba antes de pegar.
        /// </summary>
        void AimPass(float dt)
        {
            if (target == null) return;
            if (StrikeEta > TrackingStopLead)
            {
                Vector3 to = (target.transform.position - transform.position).Flat();
                float d = to.magnitude;
                if (d > 0.3f)
                {
                    bool pass = PassClip != null && HeadOnStretch(transform.position, to / d, Mathf.Max(0f, tl.T - stepClock)) < DashMinStretch;
                    passW = Mathf.MoveTowards(passW, pass ? 1f : 0f, dt / PassBlend);
                    float ang = passW * Mathf.Asin(Mathf.Clamp(PassBeside / d, 0f, 0.87f)) * Mathf.Rad2Deg;
                    // Kaito queda a su derecha: el carril sale girado hacia su izquierda
                    passRot = CombatMath.Damp(passRot, Quaternion.LookRotation(Quaternion.Euler(0f, -ang, 0f) * to), config.turnSpeed * 1.3f, dt);
                }
            }
            transform.rotation = passRot;
        }

        /// <summary>Hacia dónde mira en el vuelo: el carril, y en la que pasa el giro del clip (+ en Blender es hacia su
        /// izquierda: en Unity, negativo) más la corrección para caer mirándolo, del cruce al apoyo.</summary>
        Quaternion DashFacing()
        {
            var q = Quaternion.LookRotation(laneD);
            if (!passing) return q;
            return q * Quaternion.Euler(0f, -clip.TurnAt(stepNorm) + passDelta * LandingBlend(stepNorm), 0f);
        }

        float LandingBlend(float n)
        {
            float a = clip.Contact, b = Mathf.Max(a + 0.01f, clip.Event("DashEnd"));
            return Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(a, b, n));
        }

        /// <summary>Por dónde avanza: el carril y, en la que pasa, desde que apoya (DashEnd) el carril girado lo que corrigió
        /// en el aire (los pies apoyados frenan hacia atrás de su espalda: con el carril sin girar patinaban de costado).</summary>
        Vector3 DashDir => passing && stepNorm > clip.Event("DashEnd") ? Quaternion.Euler(0f, passDelta, 0f) * laneD : laneD;

        /// <summary>En el cruce: cuánto más tiene que girar en el aire para caer mirando a Kaito desde donde termina.</summary>
        void PlanLanding()
        {
            passDeltaSet = true;
            if (target == null) return;
            Vector3 end = laneO + laneD * (Stretched(clip, 1f, airStretch) - laneT0);
            Vector3 face = Quaternion.LookRotation(laneD) * Quaternion.Euler(0f, -clip.TurnAt(1f), 0f) * Vector3.forward;
            Vector3 to = (target.transform.position - end).Flat();
            if (to.sqrMagnitude < 0.01f) return;
            passDelta = Mathf.Clamp(Vector3.SignedAngle(face, to, Vector3.up), -PassDeltaMax, PassDeltaMax);
        }

        /// <summary>El corte que llega en el cruce: un tajo de jade por el carril a la altura del pecho de Kaito (sin él, el
        /// golpe del que vuela por al lado se leía como un roce).</summary>
        void WindCut(Vector3 at)
        {
            Vector3 c = at + Vector3.up * 1.0f, side = Vector3.Cross(Vector3.up, laneD) * 0.25f;
            SlashLineFX.Spawn(c - laneD * 1.1f - side, c + laneD * 1.1f + side, WindCutJade, 0.42f, 0.32f);
            SlashLineFX.Spawn(c - laneD * 0.8f - side, c + laneD * 0.8f + side, WindCutCore, 0.14f, 0.22f);
            Game.Audio?.Play("ability_wind", at, 0.8f, 0.08f);
        }

        static readonly Color WindCutJade = new Color(0.55f, 1f, 0.85f, 0.9f), WindCutCore = new Color(1f, 1f, 0.95f, 1f);

        /// <summary>El avance en 'n' de un clip con su tramo en el aire escalado por 'k' (StretchedTravel de otro clip).</summary>
        static float Stretched(MasterClip c, float n, float k)
        {
            float x = c.TravelAt(n);
            StretchSpan(c, out float a0, out float a1);
            if (k != 1f && a1 > a0) x += (k - 1f) * (c.TravelAt(Mathf.Clamp(n, a0, a1)) - c.TravelAt(a0));
            return x;
        }

        /// <summary>
        /// De frente: el vuelo entero escalado (StretchSpan) para que la mano frene sobre donde va a estar Kaito en el
        /// contacto ('lead' s después: si viene corriendo sigue durante el vuelo), entre la mitad y DashMaxStretch; sin
        /// salirse de la arena (el agente frenaría en el borde con el cuerpo en el aire).
        /// </summary>
        float PlanDash(Vector3 from, Vector3 dir, float lead)
        {
            StretchSpan(clip, out float a0, out float a1);
            float span = clip.TravelAt(a1) - clip.TravelAt(a0);
            if (target == null || span < 0.1f) return 1f;
            float before = clip.TravelAt(a0), after = clip.TravelAt(1f) - clip.TravelAt(a1);
            float k = Mathf.Clamp(HeadOnStretch(from, dir, lead), DashMinStretch, DashMaxStretch);
            return Mathf.Min(k, Mathf.Max(DashMinFlight, (ArenaRoom(from, dir) - 0.5f - before - after) / span));
        }

        /// <summary>El vuelo de frente que frenaría con la mano sobre Kaito, sin límites (abajo de DashMinStretch le pasa al
        /// costado).</summary>
        float HeadOnStretch(Vector3 from, Vector3 dir, float lead)
        {
            StretchSpan(clip, out float a0, out float a1);
            float span = clip.TravelAt(a1) - clip.TravelAt(a0);
            if (target == null || span < 0.1f) return 1f;
            float before = clip.TravelAt(a0), after = clip.TravelAt(1f) - clip.TravelAt(a1);
            float along = Mathf.Max(KaitoAlong(from, dir, lead), StopShort);
            return (along - StopShort - before - after) / span;
        }

        /// <summary>Al costado: el vuelo escalado para que el cruce (el contacto) caiga donde va a estar Kaito por el carril,
        /// con la cadera apenas pasada (PassOver).</summary>
        float PlanPass(MasterClip c, Vector3 from, Vector3 dir, float lead)
        {
            StretchSpan(c, out float a0, out float _);
            float before = c.TravelAt(a0), span = c.TravelAt(c.Contact) - before;
            if (span < 0.1f) return 1f;
            return Mathf.Clamp((KaitoAlong(from, dir, lead) + PassOver - before) / span, PassMinStretch, DashMaxStretch);
        }

        /// <summary>Dónde va a estar Kaito por el carril 'lead' s después: lo que se acerca corriendo, a lo sumo a la carrera
        /// (en su dash va a 25 m/s y la cuenta se iría lejos).</summary>
        float KaitoAlong(Vector3 from, Vector3 dir, float lead)
        {
            float along = Vector3.Dot((target.transform.position - from).Flat(), dir);
            float closing = Mathf.Clamp(-Vector3.Dot(target.Velocity.Flat(), dir), 0f, target.config.runSpeed);
            return along - closing * lead;
        }

        /// <summary>
        /// Un vuelo más corto que el autorado se hace a la misma velocidad, en menos tiempo: la suelta se acorta y lo que
        /// sobra se suma a la pausa agachado antes de salir, así el golpe sigue cayendo en tl.T (el aviso, el "¡ya!" y la
        /// agenda de golpes no cambian). Escalar solo la distancia lo volvía un vuelo en cámara lenta con fantasmas.
        /// </summary>
        void CompressFlight(float k, float floor)
        {
            float c = Mathf.Clamp(k, floor, 1f);
            if (c >= 0.999f) return;
            float cut = tl.tR * (1f - c);
            tl.tR -= cut;
            tl.hold += cut;
        }

        // ------------------------------------------------------------------ el carril del aviso
        float LaneWidth => 2f * (Radius + 0.6f);

        /// <summary>
        /// El carril rojo: de frente, centrado en el camino; al costado (con passW), del lado de adentro del cuerpo hasta
        /// PassLaneOut más allá de Kaito. Llega hasta donde de verdad termina la embestida (con su vuelo ya escalado) más el
        /// alcance de la mano o del bastón.
        /// </summary>
        TellArea DashArea()
        {
            Vector3 o = LaneLive ? laneO : transform.position, d = LaneDir;
            float w = LaneLive ? (passing ? 1f : 0f) : passW;
            float lo = Mathf.Lerp(-LaneWidth * 0.5f, -(Radius + PassLaneIn), w), hi = Mathf.Lerp(LaneWidth * 0.5f, PassBeside + PassLaneOut, w);
            var c = LaneLive || w < 0.5f ? clip : PassClip ?? clip;
            float k = LaneLive ? airStretch : w >= 0.5f && c != clip ? PlanPass(c, o, d, Mathf.Max(0f, tl.T - stepClock)) : PreviewStretch();
            float len = c != null ? Stretched(c, 1f, k) + c.Reach : 8f;
            return new TellArea { lane = true, origin = o + Vector3.Cross(Vector3.up, d) * ((lo + hi) * 0.5f), forward = d, size = len, width = hi - lo };
        }

        /// <summary>El carril fijo o, antes de la suelta, hacia donde mira (el que va a tomar).</summary>
        Vector3 LaneDir => LaneLive ? laneD : transform.forward.Flat().normalized;

        /// <summary>El vuelo de frente que va a tomar si se suelta ahora (antes de la suelta el aviso ya lo dibuja).</summary>
        float PreviewStretch() => clip != null ? PlanDash(transform.position, LaneDir, Mathf.Max(0f, tl.T - stepClock)) : 1f;

        bool InLane(Vector3 p, float pad) => DashArea().Contains(p, pad);

        /// <summary>La embestida: hasta el contacto, salvo que Kaito haya salido del carril (se corrió a tiempo: el
        /// aviso se deshace y la carrera ya no puede pegar).</summary>
        float DashEta(AttackDef a)
        {
            if (stepHit || target == null || stepClock >= tl.T) return float.PositiveInfinity;
            if (LaneLive && !InLane(target.transform.position, target.Radius)) return float.PositiveInfinity;
            return tl.T - stepClock;
        }

        /// <summary>El carril de este paso ya quedó fijo (BeginStep pide la ETA antes de OnStepStarted: el del paso
        /// anterior todavía figura como fijo; y después de la suelta CompressFlight corre ReleaseTime).</summary>
        bool LaneLive => laneFixed && laneTell == TellId;
    }
}
