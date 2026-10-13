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
    /// El carril del aviso sigue a Kaito hasta que de verdad sale volando y el golpe cae en tl.T, cuando lo dice el "¡ya!".
    /// </summary>
    public partial class BambooMasterBoss
    {
        // embestida: la suelta autorada eligió variante y vuelo (dashPlanned); el carril queda fijo cuando despega
        // (laneFixed, del aviso 'laneTell'; laneT0 = lo avanzado hasta ahí)
        bool dashPlanned, laneFixed;
        int laneTell;
        Vector3 laneO, laneD;
        float laneT0;
        // lo que se acortó el vuelo en el tiempo (CompressFlight): el vuelo que se vuelve a planear al despegar va a esa
        // velocidad, con margen
        float flightRate = 1f;
        // la que pasa al costado: cuánto apunta al costado antes de la suelta (0..1), si salió esa variante, cuánto corrige
        // el giro en el aire para caer mirando a Kaito (grados, una vez en el contacto) y cuánto vuela después del cruce
        // (PassTailFor: la escala del tramo del cruce al apoyo)
        Quaternion passRot;
        float passW, passDelta, passTail = 1f;
        bool passing, passDeltaSet;
        // el golpe ya se probó una vez en la ventana (el primer cuadro que llega a activeStart siempre prueba)
        bool dashTested;

        /// <summary>De centro a centro en el cruce: medido en el FBX con el reloj del juego (vuelo x0.2-1.0), el cuerpo queda
        /// a 35 cm o más del eje de Kaito y la mano que corta a 14-30 cm (con 0.85, la suma de los dos radios, el brazo y la
        /// pierna de atrás pasaban por adentro; con 1.15 rozaban la canilla y la cola del lazo). Kaito queda a la derecha
        /// del maestro (el clip corta con la derecha).</summary>
        const float PassBeside = 1.2f;
        /// <summary>
        /// Lo menos que queda al costado de Kaito en el vuelo y lo rápido que se abre en el aire para mantenerlo
        /// (PassAside), entre PassAsideAhead m antes del cruce y PassAsideBehind después (a 1.15 m la canilla y la cola del
        /// lazo pasan a 32-35 cm de su eje, a la altura de sus rodillas y de su cabeza: no lo tocan). Antes frenaba como la de
        /// frente: si Kaito se metía hacia el carril después de la suelta (corriendo, de costado o con el corte), el vuelo
        /// quedaba colgado 4-8 cuadros en la pose del aire, perdía hasta 1.7 m y el corte del cruce erraba. Kaito corre a
        /// 6.2 m/s.
        /// </summary>
        const float PassGap = 1.15f, PassAsideSpeed = 8f, PassAsideAhead = 2.5f, PassAsideBehind = 1f;
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
        /// <summary>
        /// El corte del cruce: lo más rápido que corre el clip en la ventana activa (veces su velocidad: sustain de
        /// StepTimeline) y lo más que el giro se corrige para tener la mano (o la punta) sobre Kaito. Con el vuelo comprimido
        /// el clip salía del contacto a 3-6 veces su velocidad y la mano extendida quedaba en pantalla un cuadro o ninguno.
        /// </summary>
        const float PassCutRate = 2f, PassTrackMax = 45f;

        /// <summary>Lo más largo que estira el vuelo y lo más corto que se escala el de frente (2.85 m de los 5.7 autorados:
        /// más cerca le pasa al costado) y el que pasa hasta el cruce. Con 0.1 cada embestida contra el bot "bueno" volaba
        /// x0.10. La que pasa casi siempre sale con Kaito a ~2 m (corre hacia él durante el salto atrás): hasta el cruce
        /// vuela x0.3, y después del cruce sigue lo autorado (PassTail).</summary>
        const float DashMaxStretch = 1.4f, DashMinStretch = 0.5f, PassMinStretch = 0.2f;
        /// <summary>
        /// Lo que vuela la que pasa al costado después del cruce (el tramo del contacto al apoyo, DashEnd), contra lo autorado.
        /// Antes ese tramo se escalaba con el vuelo hasta el cruce (x0.28 contra el bot): a 9.5 m/s hasta Kaito y a 2.6 m/s
        /// después, frenaba en seco justo al cortarlo y recorría 2.5-2.8 m de los 6.35 autorados. Siguiendo de largo le pasa
        /// por al lado y cae ~2.4 m detrás de él, mirándolo: 3.4-3.8 m de vuelo, más de la mitad del autorado.
        /// </summary>
        const float PassTail = 1f;
        /// <summary>El vuelo más corto en tiempo: con el borde de la arena encima el de frente puede quedar en x0.1, y con el
        /// tiempo frenado en la mitad volaba a la quinta parte de su velocidad (cámara lenta con fantasmas).</summary>
        const float DashMinFlight = 0.1f;
        /// <summary>El vuelo que se vuelve a planear al despegar, contra la velocidad que eligió la suelta (más lento o más
        /// rápido que el autorado): si Kaito frenó o se arrimó en la pausa, el cruce igual cae sobre él.</summary>
        const float ReplanSlow = 0.6f, ReplanFast = 1.8f;

        void BeginDashStep()
        {
            passRot = transform.rotation;
            passW = passDelta = 0f;
            passTail = 1f;
            passing = passDeltaSet = dashPlanned = dashTested = false;
            flightRate = 1f;
        }

        /// <summary>
        /// Embestida: en la suelta elige cómo llega (y la pausa agachado que alarga CompressFlight); el carril del aviso
        /// sigue a Kaito hasta que despega y ahí queda fijo. Salen las imágenes residuales (DashStart → DashEnd, en jade
        /// pálido: la estela de alguien rápido, no un aviso). La que pasa gira el transform en el vuelo (el giro del clip,
        /// como el avance) y lo corta en el cruce; la de frente pega con la mano sobre él. Las dos empujan a Kaito desde el
        /// maestro: la que pasa lo saca del carril hacia afuera y lo deja mirándolo (empujarlo por el carril lo daba vuelta de
        /// espaldas y lo tiraba contra el cuerpo del jefe).
        /// </summary>
        void TickDash(AttackDef a, float dt)
        {
            if (!laneFixed)
            {
                AimPass(dt);
                if (!dashPlanned && stepClock >= tl.ReleaseTime) PlanRelease();
                // despega (la suelta de verdad, que CompressFlight corrió) o entra en los últimos TrackingStopLead s: desde
                // ahí va recto y correrse sirve. Antes el carril quedaba fijo en la suelta autorada, 0.44 s antes del golpe,
                // y lo que Kaito se movía en la pausa agachado lo metía en el vuelo
                if (dashPlanned && (stepClock >= tl.ReleaseTime || tl.T - stepClock <= TrackingStopLead)) FixLane();
            }
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
            // el primer cuadro que llega al contacto prueba siempre: con el vuelo comprimido un cuadro de 60 Hz saltaba
            // la ventana entera (2 cuadros del clip) hasta 7 de cada 10 veces y el golpe no salía nunca
            if (stepHit || target == null || stepNorm < a.activeStart || dashTested && stepNorm > DashActiveEnd(a)) return;
            dashTested = true;
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

        /// <summary>La ventana del golpe: la del clip que pasa al costado (su corte dura más) o la del paso.</summary>
        float DashActiveEnd(AttackDef a) => passing ? Mathf.Max(a.activeEnd, clip.ActiveEnd) : a.activeEnd;

        /// <summary>La suelta autorada: elige la variante y cuánto vuela, y acorta el vuelo en el tiempo (CompressFlight).
        /// Pasa al costado si venía apuntándole al costado y el vuelo entero entra en la arena; si no, de frente.</summary>
        void PlanRelease()
        {
            dashPlanned = true;
            Vector3 o = transform.position, d = transform.forward.Flat().normalized;
            // en la suelta cuenta lo que Kaito sigue corriendo hasta el contacto
            float lead = Mathf.Max(0f, tl.T - stepClock);
            var pc = PassClip;
            if (pc != null && passW > 0.5f && target != null)
            {
                float k = PlanPass(pc, o, d, lead), tail = PassTailFor(pc, o, d, k);
                if (Stretched(pc, 1f, k, tail) - travelDone <= ArenaRoom(o, d) - 0.5f)
                {
                    passing = true;
                    passTail = tail;
                    clip = pc;
                    // mismos cuadros hasta la suelta: se cambia sin fundido (como las variantes de paso de PickReach)
                    anim.Play(pc.State, 0f, stepNorm);
                    airStretch = k;
                    flightRate = CompressFlight(k, PassMinStretch);
                    return;
                }
            }
            airStretch = PlanDash(o, d, lead);
            flightRate = CompressFlight(airStretch, DashMinFlight);
        }

        /// <summary>
        /// Despega: el carril queda fijo hacia donde mira (el que dibujó el aviso) y el vuelo se vuelve a planear con donde
        /// está Kaito ahora, a la velocidad que eligió la suelta (con margen). En la que pasa, el corte del cruce va con
        /// sustain: la ventana activa a lo sumo a PassCutRate veces la velocidad del clip.
        /// </summary>
        void FixLane()
        {
            laneFixed = true;
            laneTell = TellId;
            laneO = transform.position;
            laneT0 = travelDone;
            laneD = transform.forward.Flat().normalized;
            if (target == null) return;
            float lead = Mathf.Max(0f, tl.T - stepClock);
            float k = passing ? PlanPass(clip, laneO, laneD, lead) : PlanDash(laneO, laneD, lead);
            airStretch = Mathf.Clamp(k, flightRate * ReplanSlow, flightRate * ReplanFast);
            if (!passing) return;
            passTail = PassTailFor(clip, laneO, laneD, airStretch);
            float from = tl.creepIn ? tl.apex : tl.apex + tl.creep;
            float r0 = Mathf.Max(1f, 2f * (tl.activeStart - from) / Mathf.Max(1e-4f, tl.tR) * tl.stepLen);
            tl.sustain = (tl.activeEnd - tl.activeStart) * tl.stepLen / Mathf.Min(r0, PassCutRate);
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
        /// Hasta despegar apunta a Kaito (el mismo giro amortiguado que la puntería de Enemy, que este paso reemplaza, y
        /// quieto en los últimos TrackingStopLead s). Si de frente no le entraría medio vuelo (con lo que viene corriendo),
        /// apunta a su izquierda lo justo para pasarle a PassBeside: el carril del aviso ya es el que va a tomar (girarlo en
        /// la suelta lo hacía saltar). Elegida la variante en la suelta, la sigue sosteniendo en la pausa agachado.
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
                    bool pass = dashPlanned ? passing : PassClip != null && HeadOnStretch(transform.position, to / d, Mathf.Max(0f, tl.T - stepClock)) < DashMinStretch;
                    passW = Mathf.MoveTowards(passW, pass ? 1f : 0f, dt / PassBlend);
                    float ang = passW * Mathf.Asin(Mathf.Clamp(PassBeside / d, 0f, 0.87f)) * Mathf.Rad2Deg;
                    // Kaito queda a su derecha: el carril sale girado hacia su izquierda
                    passRot = CombatMath.Damp(passRot, Quaternion.LookRotation(Quaternion.Euler(0f, -ang, 0f) * to), config.turnSpeed * 1.3f, dt);
                }
            }
            transform.rotation = passRot;
        }

        /// <summary>
        /// Hacia dónde mira en el vuelo: el carril, y en la que pasa el giro del clip (+ en Blender es hacia su izquierda: en
        /// Unity, negativo) más la corrección para caer mirándolo, del cruce al apoyo. En el corte (CutTrack) lo mira de
        /// verdad: el clip extiende la mano (o el bastón) hacia adelante y el giro la lleva sobre Kaito mientras le pasa por
        /// al lado, con cualquier vuelo y aunque se haya movido.
        /// </summary>
        Quaternion DashFacing()
        {
            var q = Quaternion.LookRotation(laneD);
            if (!passing) return q;
            float yaw = -clip.TurnAt(stepNorm) + passDelta * LandingBlend(stepNorm);
            float w = CutTrack(stepNorm);
            if (w > 0f && target != null)
            {
                Vector3 to = (target.transform.position - transform.position).Flat();
                if (to.sqrMagnitude > 0.04f)
                {
                    float err = Mathf.DeltaAngle(yaw, Vector3.SignedAngle(laneD, to, Vector3.up));
                    yaw += Mathf.Clamp(err, -PassTrackMax, PassTrackMax) * w;
                }
            }
            return q * Quaternion.Euler(0f, yaw, 0f);
        }

        float LandingBlend(float n)
        {
            float a = clip.Contact, b = Mathf.Max(a + 0.01f, clip.Event("DashEnd"));
            return Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(a, b, n));
        }

        /// <summary>Cuánto mira a Kaito en el corte: entra en los dos cuadros antes del contacto, entero en la ventana activa
        /// del clip y sale en los dos de después.</summary>
        float CutTrack(float n)
        {
            float f2 = clip.FrameNorm(2f), a = clip.Contact, b = Mathf.Max(a, clip.ActiveEnd);
            if (n < a) return Mathf.SmoothStep(0f, 1f, Mathf.InverseLerp(a - f2, a, n));
            return n <= b ? 1f : Mathf.SmoothStep(1f, 0f, Mathf.InverseLerp(b, b + f2, n));
        }

        /// <summary>Por dónde avanza: el carril y, en la que pasa, desde que apoya (DashEnd) el carril girado lo que corrigió
        /// en el aire (los pies apoyados frenan hacia atrás de su espalda: con el carril sin girar patinaban de costado).</summary>
        Vector3 DashDir => passing && stepNorm > clip.Event("DashEnd") ? Quaternion.Euler(0f, passDelta, 0f) * laneD : laneD;

        /// <summary>¿La que pasa al costado está en el aire? (del pie que empuja al que apoya: ahí se puede abrir de costado)</summary>
        bool PassAirborne => passing && laneFixed && stepNorm >= clip.Event("DashStart") && stepNorm <= Mathf.Max(clip.Contact, clip.Event("DashEnd"));

        /// <summary>
        /// La que pasa al costado no frena en el aire: si Kaito se metió hacia el carril (corriendo, de costado o con el
        /// avance del corte), el vuelo se abre de costado hasta pasarle a PassGap, a lo sumo a PassAsideSpeed. En el aire no
        /// hay pie apoyado que patine y el carril dibujado se corre con él. Al que viene con el dash (i-frames) no le hace
        /// lugar: se cruzan, como con cualquier embestida.
        /// </summary>
        void PassAside(float dt)
        {
            Vector3 dir = laneD, right = Vector3.Cross(Vector3.up, dir);
            Vector3 to = (target.transform.position - transform.position).Flat();
            float along = Vector3.Dot(to, dir), lat = Vector3.Dot(to, right);
            if (along < -PassAsideBehind || along > PassAsideAhead) return;
            float need = PassGap - Mathf.Abs(lat);
            if (need <= 0f) return;
            Vector3 side = (lat >= 0f ? -right : right) * Mathf.Min(need, PassAsideSpeed * dt);
            MoveBy(side);
            laneO += side;
        }

        /// <summary>En el cruce: cuánto más tiene que girar en el aire para caer mirando a Kaito desde donde termina.</summary>
        void PlanLanding()
        {
            passDeltaSet = true;
            if (target == null) return;
            Vector3 end = laneO + laneD * (Stretched(clip, 1f, airStretch, passTail) - laneT0);
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
        static float Stretched(MasterClip c, float n, float k) => Stretched(c, n, k, k);

        /// <summary>Lo mismo, con el tramo en el aire que sigue al contacto escalado por 'tail' (la que pasa al costado vuela
        /// después del cruce: PassTail). Con tail = k es el tramo entero por k.</summary>
        static float Stretched(MasterClip c, float n, float k, float tail)
        {
            float x = c.TravelAt(n);
            StretchSpan(c, out float a0, out float a1);
            if (a1 <= a0) return x;
            float m = Mathf.Clamp(c.Contact, a0, a1);
            if (k != 1f) x += (k - 1f) * (c.TravelAt(Mathf.Clamp(n, a0, m)) - c.TravelAt(a0));
            if (tail != 1f && a1 > m) x += (tail - 1f) * (c.TravelAt(Mathf.Clamp(n, m, a1)) - c.TravelAt(m));
            return x;
        }

        /// <summary>Lo que vuela la que pasa después del cruce: PassTail sin salirse de la arena desde 'from' por 'dir' (el
        /// agente frenaría en el borde con el cuerpo en el aire), nunca menos que el vuelo hasta el cruce ('k').</summary>
        float PassTailFor(MasterClip c, Vector3 from, Vector3 dir, float k)
        {
            float room = ArenaRoom(from, dir) - 0.5f + travelDone;
            float over = Stretched(c, 1f, k, PassTail) - room;
            if (over <= 0f) return PassTail;
            StretchSpan(c, out float _, out float a1);
            float span = c.TravelAt(a1) - c.TravelAt(Mathf.Min(c.Contact, a1));
            return span > 0.05f ? Mathf.Max(k, PassTail - over / span) : k;
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
        /// Devuelve la fracción del tiempo autorado que queda.
        /// </summary>
        float CompressFlight(float k, float floor)
        {
            float c = Mathf.Clamp(k, floor, 1f);
            if (c >= 0.999f) return 1f;
            float cut = tl.tR * (1f - c);
            tl.tR -= cut;
            tl.hold += cut;
            return c;
        }

        // ------------------------------------------------------------------ el carril del aviso
        float LaneWidth => 2f * (Radius + 0.6f);

        /// <summary>
        /// El carril rojo: de frente, centrado en el camino y hasta donde de verdad termina la embestida (con su vuelo ya
        /// escalado) más el alcance de la mano o del bastón; al costado (con passW), del lado de adentro del cuerpo hasta
        /// PassLaneOut más allá de Kaito y hasta el cruce más el alcance (lo que sigue volando ya no corta: un carril hasta
        /// el final del vuelo dejaba adentro a quien ya estaba lejos del corte).
        /// </summary>
        TellArea DashArea()
        {
            Vector3 o = LaneLive ? laneO : transform.position, d = LaneDir;
            float w = dashPlanned ? (passing ? 1f : 0f) : passW;
            float lo = Mathf.Lerp(-LaneWidth * 0.5f, -(Radius + PassLaneIn), w), hi = Mathf.Lerp(LaneWidth * 0.5f, PassBeside + PassLaneOut, w);
            // la que va a salir: la que eligió la suelta o, antes, a la que viene apuntando
            var c = dashPlanned || w < 0.5f ? clip : PassClip ?? clip;
            bool pass = dashPlanned ? passing : c != clip;
            float k = dashPlanned ? airStretch : pass ? PlanPass(c, o, d, Mathf.Max(0f, tl.T - stepClock)) : PreviewStretch();
            float len = c == null ? 8f : (pass ? Stretched(c, c.Contact, k) + PassOver : Stretched(c, 1f, k)) + c.Reach;
            return new TellArea { lane = true, origin = o + Vector3.Cross(Vector3.up, d) * ((lo + hi) * 0.5f), forward = d, size = len, width = hi - lo };
        }

        /// <summary>El carril fijo o, antes de que despegue, hacia donde mira (el que va a tomar).</summary>
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
