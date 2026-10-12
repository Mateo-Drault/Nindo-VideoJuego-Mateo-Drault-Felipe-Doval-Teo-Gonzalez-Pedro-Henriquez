using System.Collections;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// La muralla del clan. Antes, al vencer a los guardias el portón se abría solo. Ahora el portón tiene un sello de
    /// sombra (WallSeal): vencidos los guardias, la cámara lo muestra y el espíritu de la bandana dice qué hacer; Kaito
    /// se acerca, aparece "Abrir con la bandana" y en la escena usa su poder: la bandana se enciende, la luz se junta a
    /// su alrededor, sale en un haz dorado que entra en el sello, las hebras de sombra se vuelven de oro y el sello
    /// estalla; las hojas se abren mientras la cámara se mete hacia el jardín. Las partidas con el portón ya abierto
    /// siguen igual (sin sello); las que tenían a los guardias vencidos y el portón cerrado ven el sello y el aviso.
    /// </summary>
    public partial class StoryDirector
    {
        // contrato con kaito-anim: "BandanaPower" (2.5 s): glow = la mano izquierda toca la bandana (f14), release = la palma
        // empuja hacia el portón con un paso (f40 de 75, la mano a (-0.10, 0.73, 0.47) m de su raíz); si el clip no los
        // trae, NGlow / NRelease (los del clip entregado)
        public const string BandanaPowerState = "BandanaPower";
        const float NGlow = 0.187f, NRelease = 0.533f, BandanaPowerSeconds = 2.5f;
        static readonly Vector3 BandanaReleaseHand = new Vector3(-0.1f, 0.73f, 0.47f);
        // sin el clip: antes el "Pray" (de rodillas con la katana en alto, el mismo gesto que rezar) y el haz le salía de
        // la frente. Ahora Kaito junta la luz quieto y estira la mano izquierda abierta hacia adelante (el arranque de
        // "Interact", a 0.55x); la mano queda ahí mientras la luz fluye y después termina el gesto
        const string PowerFallbackState = "Interact";
        const float PowerFallbackGather = 0.6f, PowerFallbackSpeed = 0.55f, NPowerHold = 0.3f, InteractSeconds = 0.667f;
        /// <summary>Lo que tarda la luz en llenar el sello antes de romperlo (s).</summary>
        const float WallPour = 1.2f;

        WallSeal wallSeal;

        /// <summary>El sello sobre el portón si sigue cerrado (lo llama Begin, con el mundo ya armado).</summary>
        void SetupWallSeal()
        {
            if (wallSeal == null && Game.World != null) wallSeal = WallSeal.Create(Game.World.WorldRoot);
        }

        /// <summary>Guardias vencidos: el portón sellado en cuadro y qué hacer. Sin sello (otro mapa) se abre como antes.</summary>
        IEnumerator WallGuardsDown()
        {
            if (wallSeal == null || !wallSeal.Sealed)
            {
                Game.Save.SetFlag(Flags.WallGateOpen);
                yield return Say("wall_open");
                yield break;
            }
            Vector3 c = wallSeal.GroundCenter;
            // el plano queda hasta terminar el diálogo (duración 0 = hasta CancelShot)
            Vector3 cam = c + wallSeal.Front * 9f + wallSeal.Along * 2.5f + Vector3.up * 3.2f;
            int shot = Game.Camera.PlayStaticShot(cam, c + Vector3.up * 1.9f, 36f, 0f, BlendOrCut(cam, 1f), 1f);
            yield return new WaitForSecondsRealtime(1.3f);
            yield return Say("wall_sealed");
            Game.Camera.CancelShot(shot);
        }

        /// <summary>Kaito usa la bandana frente al sello (WallSeal.Interact).</summary>
        public void OpenWallSeal(WallSeal seal)
        {
            if (seal == null || !seal.Sealed || Game.InCutscene || P == null) return;
            StartCoroutine(Cutscene(WallSealBreak(seal)));
        }

        IEnumerator WallSealBreak(WallSeal seal)
        {
            // 1) a su lugar, de frente al portón
            Vector3 stand = seal.StandPoint;
            yield return WalkTo(stand, 3f);
            yield return NudgeTo(stand, Quaternion.LookRotation(-seal.Front), 0.25f);
            EndKneel();
            float release = PowerRelease(out string state);
            int shot = WallShot(seal, release + WallPour + 1f);

            // 2) la bandana se enciende (cuando la mano la toca) y la luz se junta alrededor de Kaito
            var glow = BandanaGlow.Ensure(P);
            yield return PowerGesture(state, () =>
            {
                glow.Enable(0.5f);
                Game.FX?.AbilityCharge(P.transform.position, false);
                Game.Audio?.Play("bandana_charge", P.transform.position, 1f);
            });

            // 3) suelta: el haz sale de la mano que empuja y entra en el sello
            Transform src = ForwardHand();
            Vector3 off = Vector3.zero;
            if (src == null)
            {
                // sin los huesos de las manos: la bandana (sobre la frente) o, sin el hueso, a la altura de la cabeza
                src = KaitoBone("cabeza");
                off = Vector3.up * 0.12f;
                if (src == null) { src = P.transform; off = Vector3.up * 1.35f; }
            }
            var beam = BandanaStream.Play(src, off, seal.SealCenter, 0.35f);
            Game.Audio?.Play("bandana_release", P.transform.position, 1f);
            glow.Pulse(Color.white, 0.8f);
            Game.Camera.Shake(0.15f);
            float t = 0f;
            while (t < WallPour)
            {
                t += Time.deltaTime;
                // la luz llena el sello: arranca cuando llega el frente del haz
                seal.Charge(Mathf.Clamp01((t - 0.3f) / (WallPour - 0.3f)));
                yield return null;
            }

            // 4) el sello estalla
            seal.Break(0.9f);
            beam.Stop(0.3f);
            Game.FX?.PostureBreak(seal.SealCenter);
            Game.FX?.Shockwave(seal.GroundCenter + seal.Front * 0.6f, 5f, BandanaGlow.Gold);
            Game.Camera.Shake(0.55f);
            Game.Input?.Rumble(0.6f, 0.7f, 0.35f);
            Game.Audio?.Play("wall_seal_break", seal.SealCenter, 1f);
            glow.Disable(1.6f);
            EndPowerGesture(state);
            // el estallido y sus campanas de oro (hasta 0.6 s) suenan solos antes de que crujan las dos hojas
            yield return WaitScaled(0.7f);

            // 5) las hojas se abren (GateDoor gira con el flag y suena "gate_open") y la cámara entra hacia el jardín
            Game.Save.SetFlag(Flags.WallGateOpen);
            SaveSystem.Save();
            Game.FX?.Dust(seal.GroundCenter + seal.Along * 1.2f, 1.2f);
            Game.FX?.Dust(seal.GroundCenter - seal.Along * 1.2f, 1.2f);
            int shot2 = GateOpenShot(seal, 3.4f);
            Game.Camera.CancelShot(shot);
            yield return new WaitForSecondsRealtime(2.4f);
            yield return Say("wall_open");
            Game.Camera.CancelShot(shot2);
        }

        /// <summary>Lo que tarda el gesto de la bandana en soltar la luz (s, desde que arranca) y qué estado lo hace.</summary>
        float PowerRelease(out string state)
        {
            var a = P.Anim;
            if (a.HasState(BandanaPowerState))
            {
                state = BandanaPowerState;
                return KaitoTimings.Event(state, "release", NRelease) * a.Length(state, BandanaPowerSeconds);
            }
            state = PowerFallbackState;
            return PowerFallbackGather + NPowerHold * a.Length(state, InteractSeconds) / PowerFallbackSpeed;
        }

        /// <summary>
        /// El gesto hasta que suelta la luz (con BandanaPower, su release; sin él, la mano estirada que queda quieta).
        /// 'onGlow' corre cuando la bandana se enciende: con el clip, al tocarla (antes se encendía medio segundo antes de
        /// que la mano llegara); sin él, al empezar.
        /// </summary>
        IEnumerator PowerGesture(string state, System.Action onGlow)
        {
            var a = P.Anim;
            if (state == BandanaPowerState)
            {
                float max = a.Length(state, BandanaPowerSeconds) * 1.5f;
                a.Play(state, 0.2f);
                yield return WaitClip(state, KaitoTimings.Event(state, "glow", NGlow), max);
                onGlow?.Invoke();
                yield return WaitClip(state, KaitoTimings.Event(state, "release", NRelease), max);
                yield break;
            }
            onGlow?.Invoke();
            // quieto mientras la luz se junta, después la mano sale hacia adelante y se queda
            yield return WaitScaled(PowerFallbackGather);
            a.Play(state, 0.15f, 0f, PowerFallbackSpeed);
            yield return WaitClip(state, NPowerHold, 1.5f);
            a.Play(state, 0f, NPowerHold, 0f);
        }

        /// <summary>Soltada la luz: sin el clip, la mano termina el gesto y vuelve a la guardia.</summary>
        void EndPowerGesture(string state)
        {
            if (state != PowerFallbackState) return;
            P.Anim.Play(state, 0.1f, NPowerHold, 1f);
            StartCoroutine(BackToGuard(state, (1f - NPowerHold) * P.Anim.Length(state, InteractSeconds)));
        }

        /// <summary>Hasta que el estado llega a 'n' (el Animator lo dice; en el cruce, el reloj) o pasan 'max' s.</summary>
        IEnumerator WaitClip(string state, float n, float max)
        {
            var a = P.Anim;
            float t = 0f, len = Mathf.Max(0.05f, a.Length(state, 1f) / Mathf.Max(0.05f, a.StateSpeed));
            while (t < max)
            {
                float cur = a.TryNormalizedTime(state, out float an) ? an : t / len;
                if (cur >= n) yield break;
                t += Time.deltaTime;
                yield return null;
            }
        }

        IEnumerator WaitScaled(float s)
        {
            float t = 0f;
            while (t < s) { t += Time.deltaTime; yield return null; }
        }

        /// <summary>La mano más adelantada (la que empuja hacia el portón en el release), desde los nudillos.</summary>
        Transform ForwardHand()
        {
            Transform r = KaitoBone("Mando.R"), l = KaitoBone("Mando.L");
            if (r == null || l == null) return r != null ? r : l;
            float zr = P.transform.InverseTransformPoint(r.position).z, zl = P.transform.InverseTransformPoint(l.position).z;
            var h = zr >= zl ? r : l;
            var k = IncenseHold.Knuckle(h);
            return k != null ? k : h;
        }

        Vector3 wallCamEnd, wallLook;   // dónde termina el plano de la carga: el de las hojas sigue desde ahí, sin corte
        float wallCamSide = 1f;

        /// <summary>
        /// Detrás de Kaito, a 6.2 m y corrida 2.6 m a un costado (el que esté libre: banderas, braseros): Kaito entero
        /// de espaldas y el portón sellado con el dintel entre las franjas (maqueta en Blender con FOV vertical 40). Se
        /// acerca 0.8 m mientras carga.
        /// </summary>
        int WallShot(WallSeal seal, float duration)
        {
            Vector3 f = seal.Front, al = seal.Along;
            wallLook = seal.GroundCenter + Vector3.up * 2.1f + f * 0.4f;
            Vector3 eye = seal.StandPoint + Vector3.up * 1.4f;
            Vector3 best = Vector3.zero;
            float bestFree = -1f;
            for (int s = -1; s <= 1; s += 2)
            {
                Vector3 pos = seal.StandPoint + f * 6.2f + al * (2.6f * s) + Vector3.up * 1.75f;
                float free = Clearance(eye, pos - eye);
                if (free > bestFree + 0.01f) { bestFree = free; best = pos; wallCamSide = s; }
            }
            Vector3 start = Vector3.Lerp(eye, best, Mathf.Max(0.45f, bestFree - 0.05f));
            wallCamEnd = start - f * 0.8f;
            Vector3 look = wallLook;
            return Game.Camera.PlayShot(t =>
            {
                float k = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / duration));
                Vector3 pos = start - f * 0.8f * k;
                return new Pose(pos, Quaternion.LookRotation(look - pos));
            }, () => 40f, BlendOrCut(start, 0.9f), duration, 0.8f);
        }

        /// <summary>
        /// Las hojas abriéndose: sigue el travelling del plano de la carga desde donde quedó, pasa al costado de Kaito y
        /// termina con él en primer plano mirando por el vano hacia el jardín (más cerca, su cabeza llenaba el cuadro).
        /// </summary>
        int GateOpenShot(WallSeal seal, float travel)
        {
            // 'travel' es lo que tarda el travelling: el plano queda hasta que Kaito termina de hablar (CancelShot)
            Vector3 f = seal.Front, al = seal.Along;
            Vector3 a = wallCamEnd;
            Vector3 b = seal.StandPoint + f * 3.5f + al * (1.9f * wallCamSide) + Vector3.up * 1.6f;
            Vector3 la = wallLook, lb = seal.GroundCenter - f * 2.5f + Vector3.up * 1.7f;
            return Game.Camera.PlayShot(t =>
            {
                float k = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / travel));
                Vector3 pos = Vector3.Lerp(a, b, k);
                return new Pose(pos, Quaternion.LookRotation(Vector3.Lerp(la, lb, k) - pos));
            }, () => 40f, 0.3f, 0f, 0.9f);
        }
    }
}
