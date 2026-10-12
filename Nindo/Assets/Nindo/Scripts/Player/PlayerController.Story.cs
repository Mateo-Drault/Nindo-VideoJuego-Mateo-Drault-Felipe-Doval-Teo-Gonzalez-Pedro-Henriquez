using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Kaito en las escenas: los clips de historia de Tools/Blender/anim/kaito/kaito_clips.py (WakeUp, PrayIncense,
    /// PrayQuick, BandanaPower, EndingTurn) los toca StoryDirector / el santuario con ScriptedPlay. Acá va lo que esas
    /// escenas necesitan saber del clip sin tocar el Animator: si existe (con el FBX viejo no están: cada escena tiene su
    /// plan B), cuánto dura (NindoContent, kaitooo.fbx.json 'seconds'), cuándo pasa cada momento con nombre del clip
    /// (incense_take, release, offer...: ClipEventTime, de la tabla que build_kaito genera desde los 'events' del
    /// .fbx.json; así un clip re-tomado no deja a la escena esperando un número viejo) y el arranque de EndingTurn, que
    /// pide mover el transform.
    /// WakeUp arranca boca abajo: se sostiene su primer cuadro con ScriptedPlay("WakeUp", 0, 0, 0) mientras entra la
    /// imagen y se suelta con ScriptedPlay("WakeUp", 0, 0, 1); el clip ya está acostado, así que ProceduralMotion.scriptedPose
    /// va en identidad (si no, gira dos veces).
    /// </summary>
    public partial class PlayerController
    {
        // EndingTurn arranca con el cuerpo como estaba (de espaldas a Kokuyō) pero 0.55 m detrás del transform: el
        // transform tiene que ir primero ahí, mirando a Kokuyō (kaito_clips ET_SHIFT). Así el clip termina parado en el
        // transform, sin saltos al volver al Idle
        const float EndingTurnShift = 0.55f;

        /// <summary>¿El Animator de Kaito tiene este estado?</summary>
        public bool HasClip(string state) => anim.HasState(state);

        /// <summary>Duración del clip del estado (s a velocidad 1), o 'fallback' si no se conoce.</summary>
        public float ClipLength(string state, float fallback = 0f) => anim.Length(state, fallback);

        /// <summary>Segundos (a velocidad 1, desde el principio del clip) del momento 'evt' del clip 'state' (p. ej.
        /// "PrayIncense", "incense_place"), o 'fallback' si el clip o el momento no existen.</summary>
        public float ClipEventTime(string state, string evt, float fallback = -1f)
        {
            if (!anim.HasState(state) || !KaitoClipEvents.TryGet(state, evt, out float n)) return fallback;
            return n * anim.Length(state, 0f);
        }

        /// <summary>Toca 'state' desde 'normalizedOffset' a 'speed' (0 lo sostiene en ese cuadro) en modo guionado: la
        /// velocidad del Animator que pone el modo guionado no la pisa.</summary>
        public void ScriptedPlay(string state, float fade, float normalizedOffset, float speed) => anim.Play(state, fade, normalizedOffset, speed);

        /// <summary>
        /// Se da vuelta hacia 'kokuyo' y le ofrece la media cinta (EndingTurn): corre el transform 0.55 m hacia él, lo
        /// pone mirándolo y toca el clip sin fundido (su primer cuadro es la pose en la que estaba, de espaldas). Kaito
        /// tiene que estar en modo guionado. Devuelve lo que dura el clip (el último cuadro, la cinta ofrecida, queda
        /// hasta el próximo Play); sin el clip, solo lo da vuelta y devuelve 0.
        /// </summary>
        public float PlayEndingTurn(Vector3 kokuyo)
        {
            Vector3 dir = (kokuyo - transform.position).Flat();
            if (dir.sqrMagnitude < 0.01f) dir = -transform.forward;
            dir.Normalize();
            if (!anim.HasState("EndingTurn")) { FaceInstant(dir); return 0f; }
            Teleport(transform.position + dir * EndingTurnShift, Quaternion.LookRotation(dir));
            anim.Play("EndingTurn", 0f);
            return anim.Length("EndingTurn", 2.8f);
        }
    }
}
