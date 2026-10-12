using UnityEngine;

namespace Nindo
{
    /// <summary>De qué lado de Kaito ataca la sombra (siempre adentro del cuadro: nunca del lado de la cámara).</summary>
    public enum ShadowSide
    {
        /// <summary>Por donde ya está (sin cruzar el patio).</summary>
        Any,
        /// <summary>Por un costado de Kaito en pantalla (izquierda o derecha), el más cercano a la sombra.</summary>
        Flank,
        /// <summary>Lo más lejos posible del cuerpo: la pinza (el cuerpo de un lado, la sombra del otro).</summary>
        Opposite,
    }

    /// <summary>
    /// Un golpe de la sombra dentro de un patrón del cuerpo. 'before' = la sombra pega primero mientras el cuerpo
    /// carga (el amago: el cuerpo levanta la nodachi despacio y el que corta es la sombra); si no, pega entre este
    /// paso del cuerpo y el siguiente (la pinza: cuerpo, sombra, cuerpo).
    /// </summary>
    public sealed class ShadowCue
    {
        public int step;
        public string move;
        public ShadowSide side;
        public bool before;
    }

    /// <summary>Patrón del cuerpo con golpes de su sombra (lo elige PickPattern como cualquier otro).</summary>
    public sealed class DuetPattern : AttackPattern
    {
        public ShadowCue[] cues;
    }

    /// <summary>
    /// El contrato de lectura del dúo cuerpo + sombra, en un solo lugar (lo usan KokuyoBoss y KageShadow):
    ///  * nunca dos golpes pegados: entre el golpe de uno y el del otro hay al menos Gap(primero, segundo);
    ///  * en el eclipse la salida de la sombra tampoco cae pegada a un golpe del cuerpo (GapBeforeDark);
    ///  * el que arranca después pega después (cada uno estira su windup, no se adelanta al otro);
    ///  * la sombra no ataca mientras él está de rodillas, en una escena, hundido o en la última resistencia, y si
    ///    él cae de rodillas en plena carga de la sombra, la sombra la suelta (si todavía no dio el "¡ahora!").
    /// </summary>
    public static class KokuyoDuet
    {
        /// <summary>Entre dos desviables: el anillo del segundo (0.85 s) arranca justo después del golpe del primero.</summary>
        public const float GapParry = 0.9f;
        /// <summary>Después de un imparable: el dash (0.26 s), su recuperación y un tiempo de reacción.</summary>
        public const float GapAfterDodge = 1.1f;

        /// <summary>
        /// Separación mínima (s) entre el golpe 'first' de uno y el golpe 'second' del otro. Antes de un imparable el
        /// anillo rojo arranca 1 s antes del golpe: con 1.05 s nunca se dibuja encima del aviso anterior.
        /// </summary>
        public static float Gap(AttackKind first, AttackKind second) =>
            Mathf.Max(first == AttackKind.Unblockable ? GapAfterDodge : GapParry, TellStyle.MaxLead(second) + 0.05f);

        /// <summary>
        /// A oscuras la sombra sale de la oscuridad EmergeLead antes de cortar (humo, destello violeta, la bandana que
        /// late). Esa salida nunca cae a menos de esto de un golpe del cuerpo: con 0.9 s caía justo en el parry que
        /// Kaito le estaba haciendo a él, y los dos latidos de la bandana se pisaban.
        /// </summary>
        public const float EmergeClear = 0.25f;

        /// <summary>Separación entre un golpe del cuerpo y el golpe siguiente de la sombra que sale de la oscuridad
        /// 'emergeLead' antes de cortar (la primera vez sale antes: KageShadow.EmergeLeadNow).</summary>
        public static float GapBeforeDark(AttackKind body, AttackKind shadow, float emergeLead) =>
            Mathf.Max(Gap(body, shadow), emergeLead + EmergeClear);
    }
}
