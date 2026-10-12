using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Kaito en las escenas: los clips de historia de Tools/Blender/anim/kaito/kaito_clips.py (WakeUp, PrayIncense,
    /// PrayQuick, BandanaPower, EndingTurn) los toca StoryDirector / el santuario con ScriptedPlay. Acá va lo que esas
    /// escenas necesitan saber del clip sin tocar el Animator: si existe (con el FBX viejo no están: cada escena tiene su
    /// plan B), cuánto dura (NindoContent, kaitooo.fbx.json 'seconds') y el arranque de EndingTurn, que pide mover el
    /// transform. Los momentos con nombre de cada clip (incense_take, release, offer...) están en el .fbx.json ('events').
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
