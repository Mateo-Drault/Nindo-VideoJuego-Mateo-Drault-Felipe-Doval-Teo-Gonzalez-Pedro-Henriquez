using System.Collections;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// El rezo en los santuarios y el consejo de rezar.
    /// La primera vez en la partida: escena de costado (con franjas) mientras Kaito, arrodillado frente al incensario
    /// con la katana en el piso, toma el incienso, lo prende con el espíritu de la bandana, lo clava en la ceniza y
    /// junta las manos rezando por el abuelo; con las manos juntas se cura y se guarda. Ese santuario queda humeando para
    /// siempre (ShrineIncense). Después, en cualquier santuario, un rezo corto sin cortes de cámara (un leve
    /// acercamiento) y con el HUD a la vista para ver la vida llenarse; en uno nuevo el incienso aparece clavado, lo
    /// prende la chispa de la bandana y Kaito dice algo en voz baja. Antes la escena entera se repetía en cada santuario
    /// nuevo (unos 7 s por 13 santuarios, y saltarla costaba una tecla y un fundido). Nunca en pelea
    /// (Checkpoint.CanInteract) y si un enemigo lo encuentra en el rezo corto, se levanta.
    /// </summary>
    public partial class StoryDirector
    {
        // ---- contrato con kaito-anim (Kaito.controller). Los momentos son fracciones de la duración del clip, la que
        // da anim.Length: los eventos del sidecar (KaitoTimings, lo genera Tools/Unity/kaito_timings.py) y, si el clip
        // todavía no los trae, estas
        public const string PrayIncenseState = "PrayIncense", PrayQuickState = "PrayQuick", PrayOldState = "Pray";
        const float NTake = 0.16f, NLight = 0.3f, NPlace = 0.52f, NPalms = 0.64f, NRise = 0.84f, NQuickPalms = 0.42f;
        /// <summary>Duraciones si Length no las conoce (contrato: ~5.6 s el entero, ~2 s el corto; el "Pray" de antes, 1.33 s).</summary>
        const float PrayIncenseSeconds = 5.6f, PrayQuickSeconds = 2f, OldPraySeconds = 1.333f;
        /// <summary>En el rezo corto de un santuario nuevo el incienso aparece clavado y se prende acá (ya arrodillado).</summary>
        const float NQuickKindle = 0.2f;
        // sin los clips nuevos, el "Pray" de antes (rodilla al piso en f10, se para en f30 de 40). En el rezo con incienso
        // iba de corrido a 0.6x: 2.2 s, con el chispazo en medio del travelling y la cámara quieta 0.7 s. Ahora baja a
        // 0.6x, se sostiene arrodillado a 0.2x (respira y baja la cabeza: f10-f30 en 3.3 s), con la cámara ya quieta se
        // prende el incienso y reza, y se para a 0.6x: 4.5 s con 3 s de plano quieto
        const float OldPraySpeedFull = 0.6f, OldPraySpeedHold = 0.2f, NOldKneel = 0.25f, NOldRise = 0.75f, NOldPalms = 0.45f;
        const float OldKindleAt = 1.3f, OldRestAt = 2f, OldFullMax = 7f;
        /// <summary>Lo que dura arriba lo que reza (el cartel del santuario entra después: los avisos van en fila).</summary>
        const float PrayerBarkSeconds = 2.4f;

        public const string PraySeenFlag = "pray_seen", ShrineTipFlag = "tip_shrine";

        /// <summary>
        /// Raíz de Kaito a la ceniza (m), si el clip no dice dónde suelta el incienso. Desde 0.40 sus 0.35 m de radio no
        /// tocan la caja del santuario (que llega a 0.03 m delante de la ceniza); en el corto queda más atrás.
        /// </summary>
        const float DefaultReach = 0.42f, MinReach = 0.4f, MaxReach = 0.75f, MaxSideReach = 0.25f, QuickReach = 0.55f;
        // plano de costado (maquetas en Blender con FOV vertical 34 y las franjas de cine): mira a 0.88 m del piso, a
        // mitad de camino entre Kaito y el santuario, desde 4.5 m y 1.2 m de alto; entran el santuario entero, el
        // incensario con el humo, el piso y Kaito con aire delante de la cara
        const float PrayLookHeight = 0.88f, PrayCamHeight = 1.2f, PrayCamDistance = 4.5f, PrayCamMinDistance = 2.4f, PrayFov = 34f;
        /// <summary>
        /// Consejo de rezar: a cuántos metros de un santuario sale (en pantalla con la cámara de juego). cp_home queda a
        /// 11-15 m de donde termina la pelea del prólogo y Kaito sale para el norte: con 8 m el consejo recién salía en
        /// cp_fields, 70 m después y pasada la pelea de los campos.
        /// </summary>
        const float ShrineTipRadius = 8f, HomeTipRadius = 18f;

        bool praying, shrineTipDone;
        Checkpoint tipShrine;
        float introSeenAt = -1f;

        /// <summary>Rezo en curso (el entero o el corto): mientras tanto el santuario no ofrece rezar.</summary>
        public bool Praying => praying;

        /// <summary>Kaito reza en el santuario (lo llama Checkpoint.Interact).</summary>
        public void PrayAt(Checkpoint cp)
        {
            if (praying || cp == null || P == null || Game.InCutscene) return;
            bool lit = ShrineIncense.IsLit(cp.id) || (cp.Incense != null && cp.Incense.Lit);
            bool kindle = !lit && cp.Incense != null;
            if (kindle && !Game.Save.HasFlag(PraySeenFlag)) StartCoroutine(Cutscene(PrayFull(cp)));
            else StartCoroutine(PrayQuick(cp, kindle));
        }

        // ================================================================== rezo con incienso (una vez por partida)
        IEnumerator PrayFull(Checkpoint cp)
        {
            praying = true;
            bool real = P.Anim.HasState(PrayIncenseState);
            Vector2 reach = new Vector2(0f, DefaultReach);
            Transform hand = real ? PickIncenseHand(ref reach) : null;
            yield return KneelAt(cp, reach);
            // con la espada en una mano no se juntan las palmas (y de costado la hoja le cruzaba la cara)
            var katana = KatanaRest.Lay(P);
            if (real) yield return PrayIncenseClip(cp, hand);
            else yield return PrayOldClip(cp);
            EndKneel();
            KatanaRest.Restore(P, katana);
            cp.FinishRest();
            praying = false;
        }

        IEnumerator PrayIncenseClip(Checkpoint cp, Transform hand)
        {
            var a = P.Anim;
            var inc = cp.Incense;
            const string state = PrayIncenseState;
            float len = a.Length(state, PrayIncenseSeconds);
            float nTake = KaitoTimings.Event(state, "incense_take", NTake), nLight = KaitoTimings.Event(state, "incense_light", NLight);
            float nPlace = KaitoTimings.Event(state, "incense_place", NPlace), nPalms = KaitoTimings.Event(state, "palms", NPalms);
            float nRise = KaitoTimings.Event(state, "rise", NRise);
            int shot = PrayShot(cp, len);
            a.Play(state, 0.25f);
            Transform stick = null;
            bool took = false, lit = false, placed = false, rested = false, rising = false;
            float t = 0f, n = 0f;
            // el avance real del clip cuando el Animator lo dice (con Filo de Ira Kaito anima más rápido); si no, el reloj
            while (n < 1f && t < len * 1.5f)
            {
                n = a.TryNormalizedTime(state, out float an) ? an : t / len;
                if (!took && n >= nTake)
                {
                    took = true;
                    if (hand == null) hand = ChooseIncenseHand();
                    stick = ShrineIncense.MakeStick();
                    if (hand != null) IncenseHold.Attach(stick, hand, P.transform);
                    else stick.SetPositionAndRotation(P.transform.position + P.transform.forward * 0.3f + Vector3.up * 0.5f, P.transform.rotation);
                    StartCoroutine(PopIn(stick, 0.14f));
                }
                if (!lit && n >= nLight)
                {
                    lit = true;
                    inc.Light(stick);
                    // la chispa sale de la bandana: la cinta destella un instante
                    BandanaGlow.Ensure(P).Pulse(BandanaGlow.Gold, 0.7f);
                }
                if (!placed && n >= nPlace) { placed = true; inc.Place(stick, 0.2f); MarkShrineLit(cp.id); }
                if (!rested && n >= nPalms) { rested = true; PrayRest(cp, true, true); }
                // se levanta: la cámara empieza a volver mientras termina el clip
                if (!rising && n >= nRise) { rising = true; Game.Camera.CancelShot(shot); }
                t += Time.deltaTime;
                yield return null;
            }
            Game.Camera.CancelShot(shot);
        }

        /// <summary>Sin PrayIncense: el "Pray" de antes estirado (ver OldPraySpeedHold); el incienso aparece clavado.</summary>
        IEnumerator PrayOldClip(Checkpoint cp)
        {
            var a = P.Anim;
            const string state = PrayOldState;
            float clip = a.Length(state, OldPraySeconds);
            // cuándo vuelve a la velocidad de pararse (el travelling del plano dura hasta ahí)
            float rise = NOldKneel * clip / OldPraySpeedFull + (NOldRise - NOldKneel) * clip / OldPraySpeedHold;
            int shot = PrayShot(cp, rise);
            a.Play(state, 0.25f, 0f, OldPraySpeedFull);
            bool held = false, kindled = false, rested = false, risen = false, rising = false;
            float t = 0f;
            while (t < OldFullMax)
            {
                // en el cruce el Animator no da el tiempo del estado: se sigue el reloj
                float n = a.TryNormalizedTime(state, out float an) ? an
                    : t < rise ? Mathf.Min(NOldKneel, t * OldPraySpeedFull / clip) : NOldRise + (t - rise) * OldPraySpeedFull / clip;
                if (!held && n >= NOldKneel) { held = true; a.Play(state, 0f, n, OldPraySpeedHold); }
                if (!kindled && t >= OldKindleAt)
                {
                    kindled = true;
                    cp.Incense.KindleInPlace();
                    BandanaGlow.Ensure(P).Pulse(BandanaGlow.Gold, 0.7f);
                    MarkShrineLit(cp.id);
                }
                if (!rested && t >= OldRestAt) { rested = true; PrayRest(cp, true, true); }
                if (!risen && held && n >= NOldRise) { risen = true; a.Play(state, 0f, n, OldPraySpeedFull); }
                if (!rising && risen && n >= NOldRise + 0.05f) { rising = true; Game.Camera.CancelShot(shot); }
                if (risen && n >= 0.99f) break;
                t += Time.deltaTime;
                yield return null;
            }
            Game.Camera.CancelShot(shot);
            if (a.Current == state) a.Play("Locomotion", 0.2f);
        }

        /// <summary>Con las manos juntas: cura, guarda, la campanita del santuario y, si corresponde, lo que reza.</summary>
        void PrayRest(Checkpoint cp, bool first, bool speak)
        {
            Game.Save.SetFlag(PraySeenFlag);
            cp.Rest(P);
            Game.FX?.HealBurst(P.transform.position);
            Game.Audio?.Play("checkpoint", cp.Incense != null ? cp.Incense.Socket.position : cp.transform.position, 0.9f);
            if (speak) Game.UI?.ShowBark(StoryText.Kaito, StoryText.PrayerLine(first, Game.Save), UIFactory.Gold, PrayerBarkSeconds);
        }

        static void MarkShrineLit(string id)
        {
            if (Game.Save.shrines == null) Game.Save.shrines = new System.Collections.Generic.List<string>();
            if (!Game.Save.shrines.Contains(id)) Game.Save.shrines.Add(id);
        }

        /// <summary>El manojo aparece en la mano creciendo un instante (sobre su escala de importación).</summary>
        IEnumerator PopIn(Transform t, float seconds)
        {
            Vector3 s0 = t.localScale;
            float k = 0f;
            while (k < 1f && t != null)
            {
                k += Time.deltaTime / seconds;
                t.localScale = s0 * Mathf.Lerp(0.3f, 1f, UIAnim.OutCubic(Mathf.Clamp01(k)));
                yield return null;
            }
        }

        // ================================================================== rezo corto
        /// <summary>'kindle': santuario nuevo (sin incienso), se prende ya arrodillado y Kaito reza en voz baja.</summary>
        IEnumerator PrayQuick(Checkpoint cp, bool kindle)
        {
            praying = true;
            P.EnterScripted();
            var a = P.Anim;
            bool real = a.HasState(PrayQuickState);
            string state = real ? PrayQuickState : PrayOldState;
            float len = real ? a.Length(state, PrayQuickSeconds) : a.Length(state, OldPraySeconds);
            float palms = real ? KaitoTimings.Event(PrayQuickState, "palms", NQuickPalms) : NOldPalms;
            float kindleAt = real ? Mathf.Min(NQuickKindle, palms - 0.1f) : NOldKneel;
            yield return KneelAt(cp, new Vector2(0f, QuickReach));
            bool rested = false, kindled = !kindle;
            GameObject katana = null;
            // si lo encontraron mientras rodeaba el santuario, ni se arrodilla
            if (!PrayInterrupted)
            {
                // PrayQuick junta las palmas: la katana al piso (el "Pray" de antes la ofrece con las dos manos)
                if (real) katana = KatanaRest.Lay(P);
                int shot = PushInShot();
                a.Play(state, 0.2f);
                float t = 0f, n = 0f;
                while (n < 1f && t < len * 1.5f && !PrayInterrupted)
                {
                    n = a.TryNormalizedTime(state, out float an) ? an : t / len;
                    if (!kindled && n >= kindleAt)
                    {
                        kindled = true;
                        cp.Incense.KindleInPlace();
                        BandanaGlow.Ensure(P).Pulse(BandanaGlow.Gold, 0.7f);
                        MarkShrineLit(cp.id);
                    }
                    if (!rested && n >= palms) { rested = true; PrayRest(cp, false, kindle); }
                    t += Time.deltaTime;
                    yield return null;
                }
                Game.Camera.CancelShot(shot);
            }
            EndKneel();
            KatanaRest.Restore(P, katana);
            // cortado por una pelea: lo que ya curó queda, pero los encuentros no se reinician (lo estaban atacando)
            if (rested && !PrayInterrupted) cp.FinishRest();
            P.ExitScripted();
            Game.Input?.ClearBuffer();
            praying = false;
        }

        // ================================================================== Kaito frente al incensario
        /// <summary>
        /// Lleva a Kaito caminando hasta su lugar frente al incensario (rodeando el santuario si estaba al costado o
        /// detrás) y lo acomoda al centímetro mirando al santuario. 'reach' = dónde queda la ceniza respecto de su raíz
        /// (x a su derecha, y adelante). El CharacterController queda apagado hasta EndKneel: arrodillado no tiene que
        /// deslizarse por rozar la caja del santuario.
        /// </summary>
        IEnumerator KneelAt(Checkpoint cp, Vector2 reach)
        {
            var tr = cp.transform;
            Vector3 socket = cp.Incense != null ? cp.Incense.Socket.position : tr.TransformPoint(ShrineIncense.AshLocal);
            Vector3 fwd = tr.forward.Flat().normalized;            // el frente del santuario (de él hacia Kaito)
            Vector3 right = Vector3.Cross(Vector3.up, fwd);         // la izquierda de Kaito, que lo mira de frente
            Vector3 kneel = socket + fwd * reach.y + right * reach.x;
            Vector3 lp = tr.InverseTransformPoint(P.transform.position);
            float sx = lp.x >= 0f ? 1f : -1f;
            // caja del santuario en coordenadas del prop: x ±0.6, z de -0.5 a 0.72; las esquinas con 0.45 de margen
            if (lp.z < -0.5f) yield return WalkTo(tr.TransformPoint(new Vector3(sx * 1.05f, 0f, -0.95f)));
            if (lp.z < 1.05f && (Mathf.Abs(lp.x) > 0.55f || lp.z < -0.5f) && !PrayInterrupted) yield return WalkTo(tr.TransformPoint(new Vector3(sx * 1.05f, 0f, 1.2f)));
            if (PrayInterrupted) yield break;
            yield return WalkTo(kneel);
            if (PrayInterrupted) yield break;
            yield return NudgeTo(kneel, Quaternion.LookRotation(-fwd), 0.3f);
        }

        /// <summary>
        /// El rezo corto no es una cinemática y los enemigos siguen: si uno lo encuentra (mientras rodea el santuario o
        /// arrodillado) se corta y Kaito vuelve a sus manos. En el entero (cinemática) los enemigos esperan.
        /// </summary>
        static bool PrayInterrupted => !Game.InCutscene && Game.Combat != null && Game.Combat.InCombat;

        IEnumerator WalkTo(Vector3 target, float maxTime = 2.5f)
        {
            target.y = P.transform.position.y;
            if (CombatMath.FlatDistance(target, P.transform.position) < 0.25f) yield break;
            P.ScriptedMoveTo(target, 2.1f);
            float t = 0f;
            while (!P.ScriptedArrived && t < maxTime && !PrayInterrupted) { t += Time.deltaTime; yield return null; }
        }

        IEnumerator NudgeTo(Vector3 pos, Quaternion rot, float seconds)
        {
            var cc = P.GetComponent<CharacterController>();
            if (cc != null) cc.enabled = false;
            Vector3 p0 = P.transform.position;
            Quaternion r0 = P.transform.rotation;
            pos.y = p0.y;
            float t = 0f;
            while (t < seconds)
            {
                t += Time.deltaTime;
                float k = Mathf.SmoothStep(0f, 1f, t / seconds);
                P.transform.SetPositionAndRotation(Vector3.Lerp(p0, pos, k), Quaternion.Slerp(r0, rot, k));
                yield return null;
            }
            P.transform.SetPositionAndRotation(pos, rot);
        }

        void EndKneel()
        {
            var cc = P != null ? P.GetComponent<CharacterController>() : null;
            if (cc != null) cc.enabled = true;
        }

        // ================================================================== la mano del incienso
        /// <summary>
        /// La mano que toma el incienso y dónde lo suelta: se muestrea el clip en los momentos de tomarlo y clavarlo
        /// (el Animator lo vuelve a posar antes de dibujar). Así Kaito se arrodilla a la distancia justa para que la
        /// mano llegue a la ceniza con el clip que haya (sin el clip, DefaultReach y la mano libre de la katana).
        /// </summary>
        Transform PickIncenseHand(ref Vector2 reach)
        {
            if (!SampleKaitoClip(PrayIncenseState, KaitoTimings.Event(PrayIncenseState, "incense_take", NTake))) return null;
            var hand = ChooseIncenseHand();
            if (hand != null && SampleKaitoClip(PrayIncenseState, KaitoTimings.Event(PrayIncenseState, "incense_place", NPlace)))
            {
                Vector3 g = P.transform.InverseTransformPoint(IncenseHold.Grip(hand, IncenseHold.Knuckle(hand), P.transform));
                reach = new Vector2(Mathf.Clamp(g.x, -MaxSideReach, MaxSideReach), Mathf.Clamp(g.z, MinReach, MaxReach));
            }
            return hand;
        }

        /// <summary>La mano que no sostiene la katana; si la katana no está en ninguna (la dejó en el piso), la derecha.</summary>
        Transform ChooseIncenseHand()
        {
            Transform r = KaitoBone("Mando.R"), l = KaitoBone("Mando.L");
            if (r == null) return l;
            if (l == null) return r;
            var kb = P.katanaBase;
            if (kb == null || !P.HasKatana) return r;
            float dr = (kb.position - r.position).sqrMagnitude, dl = (kb.position - l.position).sqrMagnitude;
            if (Mathf.Min(dr, dl) > 0.15f * 0.15f) return r;
            return dr < dl ? l : r;
        }

        Transform KaitoBone(string name)
        {
            var root = P.model != null ? P.model : P.transform;
            foreach (var t in root.GetComponentsInChildren<Transform>()) if (t.name == name) return t;
            return null;
        }

        bool SampleKaitoClip(string state, float n)
        {
            var an = P.Anim.Animator;
            if (an == null || an.runtimeAnimatorController == null) return false;
            foreach (var c in an.runtimeAnimatorController.animationClips)
                if (c != null && (c.name == state || c.name.EndsWith("|" + state)))
                {
                    c.SampleAnimation(an.gameObject, Mathf.Clamp01(n) * c.length);
                    return true;
                }
            return false;
        }

        // ================================================================== cámaras
        /// <summary>
        /// De costado, corrida 14° hacia donde mira Kaito (se le ve la cara además del perfil), con Kaito, el incensario
        /// y el humo en cuadro entre las franjas. Elige el lado libre (esfera de 0.25 m contra lo que haya: pared, árbol,
        /// ladera) y, si los dos están libres, el más cercano a la cámara de juego (el corte gira menos). Si el lado
        /// elegido está tapado se acerca hasta lo libre y abre el lente para que siga entrando todo.
        /// </summary>
        int PrayShot(Checkpoint cp, float duration)
        {
            // 'duration' es el recorrido del travelling: el plano dura hasta que se corta (CancelShot al levantarse),
            // porque el reloj de la cámara es real y seguiría corriendo si algo pausara el juego
            var cam = Game.Camera;
            Vector3 socket = cp.Incense != null ? cp.Incense.Socket.position : cp.transform.position;
            Vector3 kaito = P.transform.position;
            Vector3 axis = (socket - kaito).Flat().normalized;
            Vector3 look = Vector3.Lerp(kaito, cp.transform.position, 0.45f);
            look.y = kaito.y + PrayLookHeight;
            Vector3 lift = Vector3.up * (PrayCamHeight - PrayLookHeight);
            Vector3 toCam = (cam.transform.position - look).Flat().normalized;
            float ang = 14f * Mathf.Deg2Rad, bestScore = float.NegativeInfinity, bestFree = 1f;
            Vector3 bestDir = Vector3.right;
            float sign = 1f;
            for (int s = -1; s <= 1; s += 2)
            {
                Vector3 side = Vector3.Cross(Vector3.up, axis) * s;
                Vector3 dir = (side * Mathf.Cos(ang) + axis * Mathf.Sin(ang)).normalized;
                float free = Clearance(look, dir * PrayCamDistance + lift);
                float score = free * 2f + Vector3.Dot(dir, toCam) * 0.3f;
                if (score > bestScore) { bestScore = score; bestDir = dir; bestFree = free; sign = s; }
            }
            float dist = Mathf.Max(PrayCamMinDistance, PrayCamDistance * bestFree - 0.3f);
            dist = Mathf.Min(dist, PrayCamDistance);
            // más cerca, lente más abierto para el mismo cuadro (tan(fov/2) proporcional a 1/distancia)
            float fov = 2f * Mathf.Atan(Mathf.Tan(PrayFov * 0.5f * Mathf.Deg2Rad) * PrayCamDistance / dist) * Mathf.Rad2Deg;
            fov = Mathf.Min(fov, 50f);
            // de la cámara de juego (19 m arriba) a 1.2 m del piso: si el viaje cruza un techo o un árbol, corte seco
            float blend = BlendOrCut(look + bestDir * dist + lift * (dist / PrayCamDistance), 0.9f);
            return cam.PlayShot(t =>
            {
                float k = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / duration));
                // se acerca un 8 % y gira 6° alrededor de Kaito en toda la escena: quieta pero viva
                Vector3 d = Quaternion.AngleAxis(Mathf.Lerp(-3f, 3f, k) * sign, Vector3.up) * bestDir;
                float r = dist * Mathf.Lerp(1f, 0.92f, k);
                Vector3 pos = look + d * r + lift * (r / PrayCamDistance);
                return new Pose(pos, Quaternion.LookRotation(look - pos));
            }, () => fov, blend, 0f, 0.9f);
        }

        /// <summary>Fracción libre (0-1) del segmento look -> look + to, con una esfera de 0.25 m. Arranca a 1 m del punto de
        /// mira: ya fuera de la caja del santuario (el punto de mira cae adentro) y de Kaito.</summary>
        static float Clearance(Vector3 look, Vector3 to)
        {
            float len = to.magnitude;
            Vector3 dir = to / len;
            const float start = 1f, radius = 0.25f;
            if (Physics.SphereCast(look + dir * start, radius, dir, out var hit, len - start, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                return Mathf.Clamp01((hit.distance + start) / len);
            return 1f;
        }

        /// <summary>
        /// La mezcla de la cámara va en línea recta de donde está a 'to'. Desde la cámara de juego (19 m arriba y 15 m
        /// atrás) hasta un plano a ras del piso, el último tramo baja en diagonal y puede atravesar un techo o una copa:
        /// se miran tres puntos del final del viaje y, si alguno está adentro de algo, 'blend' pasa a 0 (corte seco).
        /// </summary>
        static float BlendOrCut(Vector3 to, float blend)
        {
            var cam = Game.Camera;
            if (cam == null || blend <= 0f) return blend;
            Vector3 from = cam.transform.position;
            for (int i = 0; i < BlendProbes.Length; i++)
                if (Physics.CheckSphere(Vector3.Lerp(from, to, BlendProbes[i]), 0.3f, Physics.DefaultRaycastLayers, QueryTriggerInteraction.Ignore))
                    return 0f;
            return blend;
        }

        static readonly float[] BlendProbes = { 0.6f, 0.8f, 0.9f };

        /// <summary>Rezo corto: la cámara de juego se acerca un 22 % a Kaito y vuelve; sin corte. Dura hasta CancelShot
        /// (este rezo no es una cinemática: se puede pausar en el medio y el reloj de la cámara es real).</summary>
        int PushInShot()
        {
            var cam = Game.Camera;
            Vector3 p0 = cam.transform.position;
            Quaternion r0 = cam.transform.rotation;
            Transform k = P.transform;
            return cam.PlayShot(t =>
            {
                float s = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / 1.1f));
                Vector3 focus = k.position + Vector3.up * 0.7f;
                Vector3 pos = Vector3.Lerp(p0, focus, 0.22f * s);
                return new Pose(pos, Quaternion.Slerp(r0, Quaternion.LookRotation(focus - pos), 0.5f * s));
            }, () => cam.fov, 0.5f, 0f, 0.7f);
        }

        // ================================================================== consejo de rezar
        /// <summary>
        /// La primera vez que Kaito está cerca de un santuario después del prólogo (cp_home, al terminar la pelea, o el
        /// primero que encuentre): un consejo de que se puede rezar y para qué. Una vez por partida, y nunca si ya rezó.
        /// Lo llama cada Checkpoint en su Update (es barato: se corta en el flag).
        /// </summary>
        public void TickShrineTip(Checkpoint cp)
        {
            if (shrineTipDone || tipShrine != null || P == null) return;
            var s = Game.Save;
            if (s.HasFlag(ShrineTipFlag)) { shrineTipDone = true; return; }
            // ya sabe rezar: el consejo sobra
            if (s.HasFlag(PraySeenFlag)) { s.SetFlag(ShrineTipFlag); shrineTipDone = true; return; }
            if (!s.HasFlag(Flags.IntroDone)) return;
            // el consejo del fijado sale 5 s al terminar el prólogo: este espera a que se vaya
            if (introSeenAt < 0f) introSeenAt = Time.unscaledTime;
            if (Time.unscaledTime - introSeenAt < 6f || Game.InCutscene || praying || (Game.Combat != null && Game.Combat.InCombat)) return;
            float radius = cp.id == "cp_home" ? HomeTipRadius : ShrineTipRadius;
            Vector3 d = P.transform.position - cp.transform.position;
            if (d.y * d.y > 9f || d.x * d.x + d.z * d.z > radius * radius) return;
            s.SetFlag(ShrineTipFlag);
            tipShrine = cp;
            StartCoroutine(ShrineTipRoutine(cp, radius));
        }

        IEnumerator ShrineTipRoutine(Checkpoint cp, float radius)
        {
            Game.UI.ShowTutorial(StoryText.ShrinePrayHint);
            float t = 0f;
            // queda hasta que rece, empiece una pelea o una escena, o pasen 14 s (o 6 s y ya se alejó)
            while (t < 14f && !praying && !Game.InCutscene && (Game.Combat == null || !Game.Combat.InCombat))
            {
                if (t > 6f && CombatMath.FlatDistance(P.transform.position, cp.transform.position) > radius + 4f) break;
                t += Time.unscaledDeltaTime;
                yield return null;
            }
            // solo si sigue siendo el suyo: otro consejo (la ejecución, la pelea) pudo reemplazarlo en el medio
            if (Game.UI.TutorialShowing(StoryText.ShrinePrayHint)) Game.UI.HideTutorial();
            tipShrine = null;
        }
    }
}
