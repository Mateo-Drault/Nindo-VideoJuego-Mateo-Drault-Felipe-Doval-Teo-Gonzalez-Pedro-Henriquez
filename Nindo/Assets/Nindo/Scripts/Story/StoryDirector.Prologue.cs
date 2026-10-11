using System.Collections;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// El prólogo, la parte de Kaito: vuelve en sí boca abajo en el piso, aturdido murmura, se arrodilla y levanta la
    /// cabeza; en ese momento ve que se llevan al abuelo (contraplano por encima de su hombro) y se levanta mientras
    /// el plano del secuestro (StoryDirector.Intro) sigue al abuelo. Antes se fundía sobre un Kaito acostado de
    /// espaldas que se enderezaba de un tirón como una tabla, con la cámara alta mirándolo a él, y el abuelo aparecía
    /// después en otro plano: no se leía que se despertaba ni que veía algo.
    /// </summary>
    public partial class StoryDirector
    {
        // contrato con kaito-anim: "WakeUp" (boca abajo, aturdido, se arrodilla, ve el secuestro, se levanta; ~3.6 s).
        // NWakeSees es el momento en que levanta la cabeza y mira adelante (fracción de anim.Length)
        public const string WakeUpState = "WakeUp";
        const float NWakeSees = 0.6f, WakeUpSeconds = 3.6f;
        // plano del piso: de costado, bajo, a 2.8 m; mientras se arrodilla sube y se aleja un poco
        const float WakeCamDistance = 2.8f, WakeCamHeight = 0.7f, WakeCamDistanceEnd = 3.4f, WakeCamHeightEnd = 1.15f, WakeFov = 36f;

        /// <summary>Kaito vuelve en sí y ve el secuestro en 'kidnap'. Termina en el contraplano hacia el abuelo.</summary>
        IEnumerator KaitoComesTo(Vector3 kidnap)
        {
            // de cara a donde se llevan al abuelo: al levantar la cabeza lo tiene adelante
            P.ScriptedFace(kidnap);
            var a = P.Anim;
            bool real = a.HasState(WakeUpState);
            float len = real ? a.Length(WakeUpState, WakeUpSeconds) : 0f;
            // dónde queda el cuerpo tirado: del primer cuadro del clip (cabeza y pies) o, sin él, el LieDown de antes
            // (de espaldas, con la cabeza hacia atrás)
            Vector3 body;
            float bodyLen;
            if (real) { LyingBody(out body, out bodyLen); a.Play(WakeUpState, 0f, 0f, 0f); }   // el primer cuadro, quieto
            else
            {
                body = P.transform.position - P.transform.forward * 0.7f;
                bodyLen = 1.5f;
                StartCoroutine(LieDown(true));
            }
            const float fadeIn = 2.2f, daze = 0.9f;
            float rise = real ? len * NWakeSees : 1.6f;
            float sideSign;
            int ground = WakeGroundShot(body, bodyLen, fadeIn + daze - 0.4f, rise + 0.4f, out sideSign);
            yield return Game.UI.Fade(0f, fadeIn);
            Game.UI.ShowBark(StoryText.Kaito, StoryText.WakeMumble, UIFactory.Gold, 2.6f);
            yield return new WaitForSecondsRealtime(daze);
            if (real)
            {
                // desde el cuadro 0 a velocidad normal, hasta que levanta la cabeza
                a.Play(WakeUpState, 0f, 0f, 1f);
                float t = 0f, n = 0f;
                while (n < NWakeSees && t < len * 1.5f)
                {
                    n = a.TryNormalizedTime(WakeUpState, out float an) ? an : t / len;
                    t += Time.deltaTime;
                    yield return null;
                }
                StartCoroutine(WakeUpToGuard(len * (1f - NWakeSees)));
            }
            else
            {
                // sin el clip: se incorpora a medias, aturdido, y termina de pararse ya en el contraplano
                yield return PivotPitch(-82f, -38f, 1.1f);
                yield return new WaitForSecondsRealtime(0.5f);
                StartCoroutine(PivotPitch(-38f, 0f, 0.9f));
            }
            // ve al abuelo: por encima de su hombro, con lente cerrado (a 17 m el abuelo tiene que leerse); el plano del
            // secuestro que sigue se mezcla encima
            WakeOverShoulderShot(kidnap, sideSign);
            Game.Camera.CancelShot(ground);
        }

        IEnumerator WakeUpToGuard(float remaining)
        {
            yield return new WaitForSecondsRealtime(Mathf.Max(0f, remaining));
            if (P != null && P.Anim.Current == WakeUpState) P.Anim.Play("Locomotion", 0.3f);
        }

        /// <summary>Respaldo sin WakeUp: inclina el pivote del modelo (como LieDown) de un ángulo a otro.</summary>
        IEnumerator PivotPitch(float from, float to, float seconds)
        {
            var motion = P.GetComponent<ProceduralMotion>();
            if (motion == null) yield break;
            float t = 0f;
            while (t < 1f)
            {
                t += Time.unscaledDeltaTime / seconds;
                motion.scriptedPose = Quaternion.Euler(Mathf.Lerp(from, to, Mathf.SmoothStep(0f, 1f, t)), 0f, 0f);
                yield return null;
            }
            motion.scriptedPose = Mathf.Approximately(to, 0f) ? Quaternion.identity : Quaternion.Euler(to, 0f, 0f);
        }

        /// <summary>Centro (en el piso) y largo del cuerpo en el primer cuadro de WakeUp: de la cabeza a los pies.</summary>
        void LyingBody(out Vector3 center, out float length)
        {
            Vector3 k = P.transform.position;
            center = k + P.transform.forward * 0.2f;
            length = 1.5f;
            Transform head = KaitoBone("cabeza"), fl = KaitoBone("Pie.L"), fr = KaitoBone("Pie.R");
            if (head == null || fl == null || fr == null || !SampleKaitoClip(WakeUpState, 0f)) return;
            Vector3 feet = (fl.position + fr.position) * 0.5f;
            center = (head.position + feet) * 0.5f;
            center.y = k.y;
            length = Mathf.Clamp(CombatMath.FlatDistance(head.position, feet) + 0.3f, 0.8f, 2f);
        }

        /// <summary>
        /// De costado y a ras del piso, apuntado al medio del cuerpo tirado ('body', 'bodyLen' de largo: entra entero), del
        /// lado libre; con el abuelo adelante, ese costado lo deja a la derecha del cuadro (el contraplano sigue la misma
        /// regla). Mientras Kaito se arrodilla la cámara sube, se aleja y mira hacia donde queda arrodillado: quieta hasta
        /// 'hold' s, el movimiento dura 'move' s.
        /// </summary>
        int WakeGroundShot(Vector3 body, float bodyLen, float hold, float move, out float sideSign)
        {
            Vector3 k = P.transform.position, f = P.transform.forward.Flat().normalized;
            Vector3 r = Vector3.Cross(Vector3.up, f);
            Vector3 look0 = body + Vector3.up * 0.3f;
            float far = Mathf.Max(WakeCamDistance, bodyLen * 1.75f);
            float right = Clearance(look0, r * far + Vector3.up * 0.4f), left = Clearance(look0, -r * far + Vector3.up * 0.4f);
            float s = right >= left - 0.05f ? 1f : -1f;
            sideSign = s;
            float free = Mathf.Max(right, left);
            float dist0 = Mathf.Max(1.6f, far * free - 0.3f), dist1 = Mathf.Max(dist0, Mathf.Min(WakeCamDistanceEnd, WakeCamDistanceEnd * free - 0.3f));
            Vector3 side = r * s;
            return Game.Camera.PlayShot(t =>
            {
                float u = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01((t - hold) / Mathf.Max(0.5f, move)));
                Vector3 look = Vector3.Lerp(look0, k + f * 0.1f + Vector3.up * 0.85f, u);
                // al arrodillarse la cámara se corre un poco hacia su frente: se le ve más la cara
                Vector3 d = Quaternion.AngleAxis(-12f * u * s, Vector3.up) * side;
                Vector3 pos = look + d * Mathf.Lerp(dist0, dist1, u);
                pos.y = k.y + Mathf.Lerp(WakeCamHeight, WakeCamHeightEnd, u);
                return new Pose(pos, Quaternion.LookRotation(look - pos));
            }, () => WakeFov, 0f, 0f, 0.6f);
        }

        /// <summary>Por encima del hombro de Kaito (del mismo lado que el plano del piso) hacia el secuestro.</summary>
        void WakeOverShoulderShot(Vector3 kidnap, float sideSign)
        {
            Vector3 k = P.transform.position;
            Vector3 f = (kidnap - k).Flat();
            float dist = f.magnitude;
            f = dist > 0.1f ? f / dist : P.transform.forward;
            Vector3 r = Vector3.Cross(Vector3.up, f) * sideSign;
            Vector3 pos = k - f * 2.3f + r * 0.85f + Vector3.up * 1.35f;
            Vector3 look = kidnap + Vector3.up * 0.9f;
            float free = Clearance(k + Vector3.up * 1.1f, pos - (k + Vector3.up * 1.1f));
            if (free < 0.98f) pos = Vector3.Lerp(k + Vector3.up * 1.1f, pos, Mathf.Max(0.45f, free - 0.05f));
            // dura lo que tarda en entrar el plano del secuestro (si no hubiera, vuelve solo al de juego)
            Game.Camera.PlayStaticShot(pos, look, dist > 12f ? 28f : 34f, 4.2f, 0.12f, 0.8f);
        }
    }
}
