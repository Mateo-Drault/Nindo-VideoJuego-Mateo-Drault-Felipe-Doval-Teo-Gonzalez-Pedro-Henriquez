using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// El manojo en la mano de Kaito durante el rezo: sigue el puño (entre la muñeca y los nudillos) después de que el
    /// Animator posó el esqueleto, y queda derecho con una leve inclinación hacia adelante. No se emparenta al hueso: la
    /// orientación de la mano cambia con cada clip y un incienso que gira con la muñeca se ve torcido.
    /// </summary>
    [DefaultExecutionOrder(450)]
    public class IncenseHold : MonoBehaviour
    {
        /// <summary>Del pie del manojo a donde lo agarra el puño.</summary>
        public const float GripHeight = 0.075f;
        Transform hand, knuckle, body;

        public static IncenseHold Attach(Transform stick, Transform hand, Transform body)
        {
            var h = stick.gameObject.AddComponent<IncenseHold>();
            h.hand = hand; h.body = body;
            h.knuckle = Knuckle(hand);
            h.LateUpdate();
            return h;
        }

        /// <summary>El nudillo del medio (Dedo2/Dedo3 del esqueleto de Kaito): da hacia dónde apunta la mano.</summary>
        public static Transform Knuckle(Transform hand)
        {
            if (hand == null) return null;
            foreach (Transform c in hand) if (c.name.StartsWith("Dedo2") || c.name.StartsWith("Dedo3")) return c;
            return null;
        }

        /// <summary>Punto del puño (en el mundo) de una mano de Kaito.</summary>
        public static Vector3 Grip(Transform hand, Transform knuckle, Transform body)
        {
            if (knuckle != null) return Vector3.Lerp(hand.position, knuckle.position, 0.7f);
            return hand.position + (body != null ? body.forward : Vector3.forward) * 0.06f;
        }

        void LateUpdate()
        {
            if (hand == null) return;
            Vector3 fwd = body != null ? body.forward : Vector3.forward;
            Quaternion rot = Quaternion.AngleAxis(12f, Vector3.Cross(Vector3.up, fwd)) * Quaternion.LookRotation(fwd);
            Vector3 up = rot * Vector3.up;
            transform.SetPositionAndRotation(Grip(hand, knuckle, body) - up * GripHeight, rot);
        }
    }
}
