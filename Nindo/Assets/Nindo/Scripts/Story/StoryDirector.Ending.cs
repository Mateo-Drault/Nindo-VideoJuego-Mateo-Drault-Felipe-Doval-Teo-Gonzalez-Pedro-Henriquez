using System.Collections;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// El final, después del último golpe a Kokuyō. Antes: la música de la pelea se cortaba y a los 2.5 s volvía la del
    /// dojo, que sonaba en todo el rescate; los tres quedaban en un solo plano de perfil y Kaito giraba 180° de golpe
    /// para "darle" una cinta que no se veía.
    /// Ahora: silencio (solo el viento y la campana de la luna) hasta que el abuelo queda libre, y ahí entra el tema
    /// del final. En negro se ubica a los tres (la pelea pudo terminar en cualquier punto del patio): Kokuyō de rodillas,
    /// sin máscara, y junto a sus rodillas la media cinta que colgaba del pomo de su espada. Kaito la junta, va hasta el
    /// abuelo, las cuerdas de sombra se deshacen y el abuelo (Bound, Freed, Walk) se acerca. Habla el abuelo con Kaito en
    /// un plano de los dos; Kokuyō y el abuelo en el de los tres. Kaito se da vuelta y le ofrece la media cinta (EndingTurn,
    /// por encima de su hombro: la cinta y la cara de Kokuyō en cuadro), Kokuyō se inclina en seiza y la cinta baja hasta
    /// el piso delante de él. "Vamos a casa": Kaito y el abuelo se van juntos mientras la cámara sube.
    /// </summary>
    public partial class StoryDirector
    {
        // contrato con kaito-anim: "EndingTurn" (~2.5 s). Arranca mirando al abuelo con Kokuyō a la espalda (como lo
        // deja esta escena), se da vuelta y le ofrece la media cinta con la mano libre de la katana; desde NEndingOffer
        // el brazo ya está extendido y la pose se sostiene hasta el final del clip. El giro que trae el clip se mide al
        // empezar, así sirve con 180°, con otro ángulo o sin giro
        public const string EndingTurnState = "EndingTurn";
        const float NEndingOffer = 0.6f, EndingTurnSeconds = 2.5f;
        // contrato con el frente del abuelo: "Bound" (atado de rodillas; lo pone KageArenaFX) -> "Freed" (se frota las
        // muñecas, se para, alivio) -> "Walk"; sin ellos, Locomotion
        const string GrandpaFreedState = "Freed", GrandpaWalkState = "Walk";
        /// <summary>
        /// La línea abuelo - Kaito - Kokuyō (m desde el abuelo). Kokuyō de rodillas mide 3.4 m y ocupa de 0.7 m detrás a
        /// 2.4 m delante de su raíz (la máscara en el piso) y ±1.75 m de hombrera a hombrera: la media cinta queda a
        /// 2.2 m delante de él, al lado de la máscara (corrida hacia la cámara), y la devuelta baja delante de sus rodillas.
        /// </summary>
        const float EndMeet = 2.2f, EndKokuyo = 5.8f, EndRibbonAhead = 2.2f, EndRibbonSide = 0.55f, EndReturnAhead = 1.75f;
        const float EndPickReach = 0.42f, EndGrandpaStep = 0.8f, GrandpaWalkSpeed = 0.8f;

        bool endingMusic;
        HalfRibbon halfRibbon;
        float offerTurn;

        IEnumerator Ending()
        {
            Game.Save.SetFlag(Flags.FinalBossDone);
            SaveSystem.Save();
            StartCoroutine(HoldSilence());
            // Kokuyō suelta la espada, pierde la máscara y la luna vuelve antes del fundido (KokuyoBoss.FinaleSeconds)
            yield return new WaitForSecondsRealtime(FinalBoss() != null ? KokuyoBoss.FinaleSeconds : 3.5f);
            yield return Cutscene(EndingScene());
            // el tema del final ya suena desde el reencuentro (si no llegó a entrar, entra acá)
            Game.Audio?.PlayMusic("ending", 3f);
            Game.UI.ShowEnding();
        }

        /// <summary>
        /// Boss.Die apaga la música de la pelea, pero 2.5 s después el combate termina (CombatDirector) y AudioManager
        /// arranca la música del dojo con un fundido de 3 s: un cuadro después se apaga (no llega a oírse). El silencio
        /// dura hasta que el abuelo queda libre (endingMusic).
        /// </summary>
        IEnumerator HoldSilence()
        {
            endingMusic = false;
            while (!endingMusic && Game.Combat != null && Game.Combat.InCombat) yield return null;
            yield return null;
            if (!endingMusic) Game.Audio?.StopMusic(0.3f);
        }

        IEnumerator EndingScene()
        {
            var gp = Game.World.Point("npc_grandpa_dojo");
            NPC grandpa = gp != null ? gp.GetComponent<NPC>() : null;
            if (grandpa == null) grandpa = NPC.Spawn("grandpa", P.transform.position + P.transform.forward * 3f, Quaternion.identity, null);
            var k = FinalBoss();
            var fx = k != null ? k.ArenaFX : KageArenaFX.Current;
            // la línea abuelo - Kaito - Kokuyō va hacia el sudsudoeste, por el atrio de losas, perpendicular a la cámara que
            // mira desde el estesudeste. Antes iba al sudoeste y Kokuyō (3.5 m de hombreras) quedaba encima del brasero
            // del noroeste del anillo
            Vector3 camSide = new Vector3(0.89f, 0f, -0.45f).normalized;
            Vector3 dir = Vector3.Cross(Vector3.up, camSide);
            Vector3 g = grandpa.transform.position;
            Vector3 meet = OnNavMesh(g + dir * EndMeet), kokuyoSpot = OnNavMesh(g + dir * EndKokuyo);
            Vector3 ribbonSpot = OnNavMesh(kokuyoSpot - dir * EndRibbonAhead + camSide * EndRibbonSide);
            yield return Game.UI.Fade(1f, 0.8f);

            // en negro: Kokuyō de rodillas mirando al abuelo, sin la media cinta del pomo (cayó al piso: es la que va a
            // juntar Kaito), y Kaito al lado de ella
            if (k != null) { k.KneelAt(kokuyoSpot, Quaternion.LookRotation(-dir)); HalfRibbon.HideTassel(k.transform); }
            // donde la mano izquierda llega al piso en Interact (se muestrea el clip): ahí queda la cinta
            P.Teleport(ribbonSpot - dir * EndPickReach, Quaternion.LookRotation(dir));
            Vector3 grip = InteractGripLocal();
            P.Teleport(ribbonSpot - P.transform.rotation * new Vector3(grip.x, 0f, grip.z), Quaternion.LookRotation(dir));
            if (halfRibbon != null) Destroy(halfRibbon.gameObject);
            halfRibbon = HalfRibbon.Create(ribbonSpot, camSide, HalfRibbon.ClothFrom(k != null ? k.transform : null, P.model));
            Game.Camera?.Snap();
            Vector3 mid = (g + kokuyoSpot) * 0.5f;
            int wide = Game.Camera.PlayStaticShot(mid + camSide * 10f + Vector3.up * 2.6f, mid + Vector3.up * 1.4f, 36f, 0f, 0f, 1f);
            yield return Game.UI.Fade(0f, 1.2f);

            // 1) junta la media cinta (Interact: se agacha y la toma con la izquierda a la mitad) y la mira un momento
            var a = P.Anim;
            float pick = a.Length("Interact", 0.667f);
            a.Play("Interact", 0.15f);
            yield return Wait(pick * 0.5f);
            var hand = KaitoBone("Mando.L");
            if (hand == null) hand = ChooseIncenseHand();
            halfRibbon.Hold(hand, P.transform);
            yield return Wait(pick * 0.5f + 0.6f);

            // 2) se da vuelta y va hasta el abuelo (caminando: el giro sale del paso)
            P.ScriptedMoveTo(meet, 1.7f);
            float tw = 0f;
            while (!P.ScriptedArrived && tw < 2.5f) { tw += Time.deltaTime; yield return null; }
            yield return NudgeTo(meet, Quaternion.LookRotation(-dir), 0.25f);
            EndKneel();
            int two = ReunionShot(meet, g, camSide);
            Game.Camera.CancelShot(wide);

            // 3) las cuerdas de sombra se deshacen y el abuelo queda libre: recién ahí, el tema del final
            if (fx != null && fx.Ropes != null && fx.Ropes.Bound) { fx.Ropes.Dissolve(1.6f); yield return Wait(1.2f); }
            endingMusic = true;
            Game.Audio?.PlayMusic("ending", 6f);
            yield return FreeGrandpa(grandpa);

            // 4) el reencuentro; 5) Kokuyō y el abuelo, los tres en cuadro
            yield return Say("ending");
            int three = ThreeShot(g, kokuyoSpot, camSide, 0f);
            Game.Camera.CancelShot(two);
            yield return Wait(0.35f);
            yield return Say("ending_kokuyo");

            // 6) Kaito le ofrece la media cinta; Kokuyō se inclina y la cinta baja hasta el piso delante de sus rodillas
            int offer = -1;
            if (k != null)
            {
                offer = OfferShot(P.transform.position, kokuyoSpot, camSide);
                Game.Camera.CancelShot(three);
                yield return OfferRibbon(k);
                yield return Say("ending_ribbon");
                k.Bow();
                yield return Wait(0.35f);
                halfRibbon.Release(OnNavMesh(kokuyoSpot - dir * EndReturnAhead), 1.3f);
                yield return Wait(1.9f);
                yield return SettleOffer(0.45f);
            }
            else yield return Say("ending_ribbon");

            // 7) "vamos a casa": la grúa sube y se aleja mientras se van juntos hacia la puerta
            int last = ThreeShot(g, kokuyoSpot, camSide, 9f);
            if (offer >= 0) Game.Camera.CancelShot(offer);
            Game.Camera.CancelShot(three);
            yield return Wait(0.4f);
            yield return Say("ending_final");
            // hacia la puerta, abriéndose del lado de la cámara: derecho al sur pasaban por la hombrera de Kokuyō
            Vector3 home = (GatePoint(g) - g).Flat();
            home = home.sqrMagnitude > 1f ? Vector3.Lerp(home.normalized, camSide, 0.4f).normalized : camSide;
            P.ScriptedMoveTo(P.transform.position + home * 6f, 1.0f);
            grandpa.WalkTo(grandpa.transform.position + home * 6f + Vector3.Cross(Vector3.up, home) * 0.7f, GrandpaWalkSpeed * 1.1f);
            Game.Save.SetFlag(Flags.Ending);
            SaveSystem.Save();
            yield return Wait(1.6f);
            yield return Game.UI.Fade(1f, 2.4f);
            Game.Camera.CancelShot(last);
        }

        /// <summary>Dónde agarra la mano izquierda en Interact (cuadro 10 de 20), respecto de Kaito; si no, adelante a la izquierda.</summary>
        Vector3 InteractGripLocal()
        {
            var hand = KaitoBone("Mando.L");
            if (hand != null && SampleKaitoClip("Interact", 0.5f))
            {
                Vector3 g = P.transform.InverseTransformPoint(IncenseHold.Grip(hand, IncenseHold.Knuckle(hand), P.transform));
                if (g.z > 0.1f && g.z < 0.9f && Mathf.Abs(g.x) < 0.5f) return g;
            }
            return new Vector3(-0.15f, 0f, EndPickReach);
        }

        static Vector3 OnNavMesh(Vector3 p) =>
            UnityEngine.AI.NavMesh.SamplePosition(p, out var hit, 2f, UnityEngine.AI.NavMesh.AllAreas) ? hit.position : p;

        /// <summary>La puerta del dojo (hacia donde se van): el marcador de la puerta de los sellos o, si no está, el sur.</summary>
        Vector3 GatePoint(Vector3 from)
        {
            var t = Game.World != null ? Game.World.Point("seal_gate") : null;
            return t != null ? t.position : from + Vector3.back * 20f;
        }

        // ================================================================== el abuelo
        IEnumerator FreeGrandpa(NPC grandpa)
        {
            bool freed = NpcHasState(grandpa, GrandpaFreedState);
            grandpa.TurnTo(P.transform.position, 0.45f);
            if (freed) grandpa.PlayThen(GrandpaFreedState, "Locomotion", 0.25f);
            else grandpa.Play("Locomotion", 0.3f);
            Game.FX?.Petals(grandpa.transform.position + Vector3.up * 1.6f, 1.6f);
            yield return Wait(freed ? NpcStateLength(grandpa, GrandpaFreedState, 3f) * 0.95f : 0.6f);
            // unos pasos hacia su nieto
            Vector3 to = grandpa.transform.position + (P.transform.position - grandpa.transform.position).Flat().normalized * EndGrandpaStep;
            float walk = EndGrandpaStep / GrandpaWalkSpeed;
            if (NpcHasState(grandpa, GrandpaWalkState))
            {
                grandpa.TurnTo(to, 0.3f);
                grandpa.Play(GrandpaWalkState, 0.2f);
                grandpa.SlideTo(to, GrandpaWalkSpeed);
                yield return Wait(walk);
                grandpa.Play("Locomotion", 0.3f);
            }
            else
            {
                grandpa.WalkTo(to, GrandpaWalkSpeed);
                yield return Wait(walk + 0.2f);
            }
        }

        static Animator NpcAnimator(NPC n) => n != null ? n.GetComponentInChildren<Animator>() : null;

        static bool NpcHasState(NPC n, string state)
        {
            var an = NpcAnimator(n);
            return an != null && an.runtimeAnimatorController != null && an.HasState(0, Animator.StringToHash(state));
        }

        static float NpcStateLength(NPC n, string state, float fallback)
        {
            var an = NpcAnimator(n);
            if (an == null || an.runtimeAnimatorController == null) return fallback;
            foreach (var c in an.runtimeAnimatorController.animationClips)
                if (c != null && (c.name == state || c.name.EndsWith("|" + state))) return c.length;
            return fallback;
        }

        // ================================================================== la media cinta
        /// <summary>
        /// Kaito se da vuelta hacia Kokuyō y le ofrece la cinta. Con EndingTurn se mide cuánto gira el clip (su último
        /// cuadro) y Kaito arranca de modo que termine de frente a Kokuyō; sin el clip, gira en el lugar.
        /// </summary>
        IEnumerator OfferRibbon(KokuyoBoss k)
        {
            var a = P.Anim;
            Vector3 toK = (k.transform.position - P.transform.position).Flat().normalized;
            offerTurn = 0f;
            if (!a.HasState(EndingTurnState))
            {
                yield return TurnInPlace(toK, 0.6f);
                yield return Wait(0.3f);
                yield break;
            }
            float turn = ClipYaw(EndingTurnState);
            offerTurn = turn;
            // el clip deja el cuerpo girado 'turn' respecto del transform: el transform arranca en (hacia Kokuyō - turn)
            Vector3 start = Quaternion.AngleAxis(-turn, Vector3.up) * toK;
            if (Vector3.Angle(P.transform.forward.Flat(), start) > 15f) yield return TurnInPlace(start, 0.5f);
            float len = a.Length(EndingTurnState, EndingTurnSeconds);
            a.Play(EndingTurnState, 0.2f);
            yield return Wait(len * NEndingOffer);
            // el brazo extendido: un destello dorado tenue en la cinta (la tela es la de la bandana)
            Game.FX?.FlashLight(halfRibbon.Knot, BandanaGlow.Gold, 1.6f, 2.5f, 0.7f);
            yield return Wait(len * (1f - NEndingOffer));
        }

        /// <summary>
        /// Baja el brazo: de la pose sostenida de EndingTurn a la guardia sin que el cuerpo vuelva a girar. El transform se
        /// gira hasta donde mira el cuerpo y el pivote del modelo compensa al revés mientras dura el cruce.
        /// </summary>
        IEnumerator SettleOffer(float fade)
        {
            var a = P.Anim;
            if (a.Current != EndingTurnState) yield break;
            var motion = P.GetComponent<ProceduralMotion>();
            float turn = offerTurn;
            if (motion == null || Mathf.Abs(turn) < 1f) { a.Play("Locomotion", fade); yield break; }
            P.transform.rotation = Quaternion.AngleAxis(turn, Vector3.up) * P.transform.rotation;
            motion.scriptedPose = Quaternion.AngleAxis(-turn, Vector3.up);
            a.Play("Locomotion", fade);
            float t = 0f;
            while (t < 1f)
            {
                t = Mathf.Min(1f, t + Time.deltaTime / fade);
                motion.scriptedPose = Quaternion.AngleAxis(-turn * (1f - t), Vector3.up);
                yield return null;
            }
            motion.scriptedPose = Quaternion.identity;
        }

        /// <summary>Gira a Kaito en el lugar hacia 'dir' (sin clip de giro: corto, en la guardia).</summary>
        IEnumerator TurnInPlace(Vector3 dir, float seconds)
        {
            Quaternion r0 = P.transform.rotation, r1 = Quaternion.LookRotation(dir.Flat().normalized);
            float t = 0f;
            while (t < 1f)
            {
                t = Mathf.Min(1f, t + Time.deltaTime / seconds);
                P.transform.rotation = Quaternion.Slerp(r0, r1, Mathf.SmoothStep(0f, 1f, t));
                yield return null;
            }
        }

        /// <summary>
        /// Cuánto gira un clip de Kaito (grados alrededor de Y, desde el frente del transform) en su último cuadro: el frente
        /// del cuerpo por la línea de los hombros y la de las rodillas (el Animator lo vuelve a posar antes de dibujar).
        /// </summary>
        float ClipYaw(string state)
        {
            if (!SampleKaitoClip(state, 1f)) return 0f;
            Vector3 f = BodyForward();
            return f.sqrMagnitude < 1e-4f ? 0f : Vector3.SignedAngle(P.transform.forward.Flat(), f, Vector3.up);
        }

        Vector3 BodyForward()
        {
            Vector3 right = Vector3.zero;
            Transform sr = KaitoBone("Brazo.R"), sl = KaitoBone("Brazo.L"), kr = KaitoBone("Tibia.R"), kl = KaitoBone("Tibia.L");
            if (sr != null && sl != null) right += (sr.position - sl.position).Flat();
            if (kr != null && kl != null) right += (kr.position - kl.position).Flat();
            return right.sqrMagnitude < 1e-4f ? Vector3.zero : Vector3.Cross(right.normalized, Vector3.up);
        }

        // ================================================================== cámaras
        /// <summary>Los dos de costado (desde el patio): Kaito llega, las cuerdas se deshacen, el abuelo se acerca.</summary>
        int ReunionShot(Vector3 kaito, Vector3 grandpa, Vector3 camSide)
        {
            Vector3 mid = (kaito + grandpa) * 0.5f;
            Vector3 look = mid + Vector3.up * 0.95f;
            return Game.Camera.PlayShot(t =>
            {
                // se acerca medio metro en toda la escena: quieta pero viva
                float u = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / 8f));
                Vector3 pos = mid + camSide * Mathf.Lerp(4.4f, 3.9f, u) + Vector3.up * 1.3f;
                return new Pose(pos, Quaternion.LookRotation(look - pos));
            }, () => 36f, 0.9f, 0f, 0.9f);
        }

        /// <summary>
        /// Los tres de perfil (el abuelo, Kaito en el medio, Kokuyō de rodillas). Con 'crane' > 0 sube y se aleja en esos
        /// segundos (el cierre).
        /// </summary>
        int ThreeShot(Vector3 grandpa, Vector3 kokuyo, Vector3 camSide, float crane)
        {
            Vector3 mid = (grandpa + kokuyo) * 0.5f;
            return Game.Camera.PlayShot(t =>
            {
                float u = crane > 0f ? Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / crane)) : 0f;
                Vector3 pos = mid + camSide * (9.5f + 4f * u) + Vector3.up * (2.4f + 3.6f * u);
                Vector3 look = mid + Vector3.up * Mathf.Lerp(1.35f, 0.9f, u);
                return new Pose(pos, Quaternion.LookRotation(look - pos));
            }, () => 34f, 1.0f, 0f, 1.0f);
        }

        /// <summary>
        /// Por encima del hombro izquierdo de Kaito (el de la cinta: queda del lado de la cámara) hacia Kokuyō: la mano
        /// con la cinta cerca, grande, y la cara de Kokuyō de frente para ver que se inclina.
        /// </summary>
        int OfferShot(Vector3 kaito, Vector3 kokuyo, Vector3 camSide)
        {
            // Kokuyō de rodillas tiene la cara a 2.6 m de alto y la cresta a 3.4: desde 2.6 m detrás de Kaito y a 1.6 m de
            // alto entran la cresta arriba y la mano con la cinta abajo (maqueta en Blender, FOV vertical 38 con franjas)
            Vector3 axis = (kokuyo - kaito).Flat().normalized;
            Vector3 pos = kaito - axis * 2.6f + camSide * 1.7f + Vector3.up * 1.6f;
            Vector3 look = kaito + axis * 1.9f + Vector3.up * 1.75f;
            return Game.Camera.PlayStaticShot(pos, look, 38f, 0f, 0.9f, 1.0f);
        }
    }
}
