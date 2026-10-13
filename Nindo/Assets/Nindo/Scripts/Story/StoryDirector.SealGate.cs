using System.Collections;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// La puerta de los tres sellos (World/SealGate). Antes había que juntar los tres y recién ahí la puerta hacía algo;
    /// ahora cada sello se pone apenas se tiene: Kaito se para frente a la puerta, el medallón aparece delante de su
    /// pecho, la bandana lo manda con un gesto (BandanaPower o su respaldo, el mismo de la muralla) y vuela a su hueco,
    /// donde encastra con un golpe de luz y queda guardado. Con el tercero la luz corre de un sello al otro, como la raya
    /// del HUD, y la puerta se abre. La primera vez que Kaito llega, una grúa termina en los tres grabados.
    /// </summary>
    public partial class StoryDirector
    {
        /// <summary>Lo que tarda un medallón en volar a su hueco y cada cuánto sale el siguiente (s).</summary>
        const float SealFlight = 0.85f, SealFlightGap = 0.32f;
        // plano de la colocación (maquetas en Blender con FOV vertical 40 y las franjas): detrás de Kaito, corrido al
        // costado contrario del hueco, bajo, mirando entre su pecho y el tablero; se acerca y sube la mirada al hueco
        const float PlaceBack = 7.5f, PlaceSide = 2.4f, PlaceHeight = 1.4f, PlaceLook = 2.9f;
        const float PlaceBackEnd = 6.6f, PlaceSideEnd = 2.1f, PlaceHeightEnd = 1.55f, PlaceLookEnd = 3.35f, PlaceFov = 40f;

        readonly SealId[] pendingSeals = new SealId[3];

        // ================================================================== la primera vez
        /// <summary>
        /// Kaito llega a la puerta: grúa desde detrás de él que sube por encima de su cabeza y termina de frente a los tres
        /// huecos grabados (el diálogo habla de ellos). Antes la cámara quedaba del lado del patio, mirando la espalda
        /// del portón: los huecos no se veían.
        /// </summary>
        IEnumerator DojoGateFirstLook()
        {
            var t = Game.World.Point("seal_gate");
            var gate = t != null ? t.GetComponent<SealGate>() : null;
            int shot = -1;
            if (gate != null) shot = GateRevealShot(gate, 4.2f);
            yield return new WaitForSecondsRealtime(gate != null ? 3.4f : 0.5f);
            yield return Say("dojo_gate");
            if (shot >= 0) Game.Camera.CancelShot(shot);
        }

        int GateRevealShot(SealGate gate, float travel)
        {
            Vector3 board = gate.BoardCenter, f = gate.Front;
            Vector3 k = P.transform.position;
            Vector3 toGate = (board - k).Flat();
            if (toGate.sqrMagnitude < 1f) toGate = -f;
            toGate.Normalize();
            Vector3 side = Vector3.Cross(Vector3.up, toGate);
            Vector3 a = k - toGate * 3.2f + side * 1.1f + Vector3.up * 1.9f;
            Vector3 la = board - Vector3.up * 2.2f;
            // de frente a 5.5 m del tablero y a su altura: los tres huecos con su grabado entran enteros (FOV 30)
            Vector3 b = board + f * 5.5f + Vector3.up * 0.3f;
            // el lente se cierra con el viaje (el reloj de los planos es el real)
            float start = Time.unscaledTime;
            return Game.Camera.PlayShot(t =>
            {
                float u = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / travel));
                // sube antes de avanzar: pasa por encima de la cabeza de Kaito
                float h = 1f - (1f - u) * (1f - u);
                Vector3 pos = Vector3.Lerp(a, b, u);
                pos.y = Mathf.Lerp(a.y, b.y, h);
                return new Pose(pos, Quaternion.LookRotation(Vector3.Lerp(la, board, u) - pos));
            }, () => Mathf.Lerp(40f, 30f, Mathf.SmoothStep(0f, 1f, Mathf.Clamp01((Time.unscaledTime - start) / travel))), BlendOrCut(a, 1.1f), 0f, 1f);
        }

        // ================================================================== poner los sellos
        /// <summary>Kaito usa la puerta (SealGate.Interact).</summary>
        public void OpenSealGate(SealGate gate)
        {
            var s = Game.Save;
            if (gate == null || P == null || Game.InCutscene || s.HasFlag(Flags.DojoOpen)) return;
            if (SealGate.PendingCount(s) == 0 && SealGate.PlacedCount(s) < 3)
            {
                StartCoroutine(Cutscene(Game.UI.Dialogue(StoryText.GateIncomplete(s)), false));
                return;
            }
            StartCoroutine(Cutscene(PlaceSeals(gate)));
        }

        IEnumerator PlaceSeals(SealGate gate)
        {
            var s = Game.Save;
            // los que tiene y no puso, en el orden del HUD (de izquierda a derecha mirando la puerta)
            int n = 0;
            for (int i = 0; i < 3; i++) if (s.HasSeal((SealId)i) && !SealGate.IsPlaced(s, (SealId)i)) pendingSeals[n++] = (SealId)i;
            // los tres puestos y la puerta cerrada (se cortó antes de abrirse): directo a abrir
            if (n == 0) { yield return GateOpens(gate, -1); yield break; }
            SealId lead = n == 1 ? pendingSeals[0] : SealId.Lago;

            // 1) a su lugar frente a la puerta, mirándola
            Vector3 stand = gate.StandPoint(lead, P.transform.position);
            yield return WalkTo(stand, 3.5f);
            yield return NudgeTo(stand, Quaternion.LookRotation(-gate.Front.Flat().normalized), 0.3f);
            EndKneel();
            float release = PowerRelease(out string state);
            float beat = release + SealFlight + (n - 1) * SealFlightGap + 1.6f;
            int shot = PlaceShot(gate, lead, beat);

            // 2) los medallones aparecen delante de él, donde la palma va a empujar en el release (varios: en abanico, el
            // de la montaña a su izquierda). Antes flotaban a la altura del pecho y la palma, que empuja a 0.73 m de alto,
            // empujaba el aire medio metro abajo; con el paso del clip la cabeza quedaba casi contra el medallón
            Vector3 front = P.transform.TransformPoint(ReleaseHandLocal(state) + new Vector3(0f, SealAboveHand, SealAheadOfHand));
            for (int k = 0; k < n; k++)
            {
                gate.Summon(pendingSeals[k], front + gate.Left * (((n - 1) * 0.5f - k) * 0.42f));
                yield return WaitScaled(0.12f);
            }
            yield return PowerGesture(state, () => Game.Audio?.Play("bandana_charge", P.transform.position, 0.55f));

            // 3) suelta: la bandana destella y cada medallón vuela a su hueco
            BandanaGlow.Ensure(P).Pulse(BandanaGlow.Gold, 0.8f);
            Game.Audio?.Play("bandana_release", P.transform.position, 0.7f);
            int seated = 0;
            for (int k = 0; k < n; k++)
            {
                var id = pendingSeals[k];
                StartCoroutine(gate.Fly(id, SealFlight, () => { s.sealsPlaced[(int)id] = true; seated++; }));
                if (k < n - 1) yield return WaitScaled(SealFlightGap);
            }
            float guard = 0f;
            while (seated < n && guard < 3f) { guard += Time.deltaTime; yield return null; }
            for (int k = 0; k < n; k++) s.sealsPlaced[(int)pendingSeals[k]] = true;
            SaveSystem.Save();   // sale el pergamino: quedó puesto
            if (state == BandanaPowerState) StartCoroutine(BackToGuard(state, P.Anim.Length(state, BandanaPowerSeconds) - release - SealFlight));
            else EndPowerGesture(state);
            UpdateObjective();

            // 4) con los tres, se abre; si no, Kaito lo dice en voz baja y vuelve el control
            if (SealGate.PlacedCount(s) >= 3) { yield return GateOpens(gate, shot); yield break; }
            Game.UI.ShowBark(StoryText.Kaito, StoryText.SealPlacedLine(s, pendingSeals[n - 1]), UIFactory.Gold, 2.6f);
            yield return WaitScaled(1.4f);
            Game.Camera.CancelShot(shot);
        }

        /// <summary>
        /// Dónde empuja la palma en el release, respecto de Kaito (x a su derecha, y arriba, z adelante): con BandanaPower
        /// la mano más adelantada muestreada en ese momento; sin él (la mano estirada de Interact), al frente y abajo.
        /// </summary>
        Vector3 ReleaseHandLocal(string state)
        {
            if (state == BandanaPowerState && SampleKaitoClip(state, KaitoTimings.Event(state, "release", NRelease)))
            {
                var h = ForwardHand();
                if (h != null)
                {
                    Vector3 l = P.transform.InverseTransformPoint(h.position);
                    if (l.z > 0.2f && l.z < 1f && l.y > 0.4f && l.y < 1.5f) return l;
                }
            }
            return state == BandanaPowerState ? BandanaReleaseHand : new Vector3(0f, 0.8f, 0.4f);
        }

        /// <summary>El medallón delante de la palma (m): un poco arriba y adelante, para que el empujón le llegue sin tocarlo.</summary>
        const float SealAboveHand = 0.1f, SealAheadOfHand = 0.45f;

        /// <summary>Termina el gesto y vuelve a la guardia (el clip queda en su pose final si nadie lo cambia).</summary>
        IEnumerator BackToGuard(string state, float remaining)
        {
            yield return WaitScaled(Mathf.Max(0f, remaining));
            if (P != null && P.Anim.Current == state) P.Anim.Play("Locomotion", 0.3f);
        }

        /// <summary>
        /// Detrás de Kaito, del lado contrario al hueco (el medallón cruza el cuadro en diagonal hacia arriba), bajo: Kaito
        /// entero abajo, el portón y el tablero arriba. Se acerca casi un metro y sube la mirada hacia el hueco mientras vuela
        /// (termina con Kaito de los hombros para arriba abajo a la izquierda).
        /// Las alturas de la cámara van desde los pies de Kaito (la subida al portón es una rampa).
        /// </summary>
        int PlaceShot(SealGate gate, SealId lead, float duration)
        {
            Vector3 f = gate.Front, left = gate.Left;
            float sx = SealGate.SocketSide(lead);
            Vector3 k = P.transform.position;
            float baseY = gate.transform.position.y;
            Vector3 chest = k + Vector3.up * 1.1f;
            Vector3 board = gate.transform.TransformPoint(new Vector3(sx * 0.5f, 0f, 1.59f));
            Vector3 look0 = Vector3.Lerp(chest, board, 0.45f), look1 = Vector3.Lerp(chest, board, 0.55f);
            look0.y = baseY + PlaceLook;
            look1.y = baseY + PlaceLookEnd;
            // del lado contrario al hueco; con el del medio (o varios), el lado más libre
            float side = sx > 0.1f ? -1f : sx < -0.1f ? 1f : 0f;
            Vector3 eye = k + Vector3.up * PlaceHeight;
            if (side == 0f)
                side = Clearance(eye, f * PlaceBack - left * PlaceSide) >= Clearance(eye, f * PlaceBack + left * PlaceSide) ? -1f : 1f;
            Vector3 c0 = k + f * PlaceBack + left * (side * PlaceSide) + Vector3.up * PlaceHeight;
            Vector3 c1 = k + f * PlaceBackEnd + left * (side * PlaceSideEnd) + Vector3.up * PlaceHeightEnd;
            // si algo tapa (estandartes, guardias de piedra) se acerca hasta lo libre
            float free = Clearance(look0, c0 - look0);
            if (free < 0.98f) { c0 = Vector3.Lerp(look0, c0, Mathf.Max(0.5f, free - 0.05f)); c1 = Vector3.Lerp(look1, c1, Mathf.Max(0.5f, free - 0.05f)); }
            return Game.Camera.PlayShot(t =>
            {
                float u = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / duration));
                Vector3 pos = Vector3.Lerp(c0, c1, u);
                return new Pose(pos, Quaternion.LookRotation(Vector3.Lerp(look0, look1, u) - pos));
            }, () => PlaceFov, BlendOrCut(c0, 0.9f), 0f, 0.9f);
        }

        // ================================================================== la puerta se abre
        /// <summary>
        /// Los tres sellos: de frente al tablero la luz corre de un sello al otro (la raya del HUD), tiembla todo, la
        /// puerta se abre (GateDoor gira con el flag y suena) y la cámara se aleja para ver las hojas abrirse.
        /// </summary>
        IEnumerator GateOpens(SealGate gate, int shot)
        {
            Vector3 board = gate.BoardCenter, f = gate.Front;
            int close = Game.Camera.PlayStaticShot(board + f * 6.5f + Vector3.up * 0.15f, board, 32f, 0f, shot >= 0 ? 1.0f : 1.2f, 1f);
            if (shot >= 0) Game.Camera.CancelShot(shot);
            yield return WaitScaled(1.1f);
            yield return gate.LinkUp(1.1f);
            Game.Camera.Shake(0.5f);
            Game.Input?.Rumble(0.5f, 0.6f, 0.4f);
            Game.FX?.SealGlow(board + f * 0.3f);
            yield return WaitScaled(0.35f);
            Game.Save.SetFlag(Flags.DojoOpen);
            SaveSystem.Save();
            Vector3 sill = gate.transform.position + f * 0.4f;
            Game.FX?.Dust(sill + gate.Left * 1.2f, 1.2f);
            Game.FX?.Dust(sill - gate.Left * 1.2f, 1.2f);
            // de frente y más atrás: el tablero con los tres sellos arriba y las hojas abriéndose abajo
            int open = Game.Camera.PlayStaticShot(gate.transform.position + f * 13.6f + gate.Left * 2f + Vector3.up * 2.1f,
                                                   gate.transform.position + f * 1.6f + Vector3.up * 3.6f, 42f, 0f, 1.6f, 1f);
            Game.Camera.CancelShot(close);
            yield return new WaitForSecondsRealtime(2.6f);
            yield return Say("dojo_gate_open");
            Game.Camera.CancelShot(open);
        }
    }
}
