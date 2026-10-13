using System;
using UnityEngine;
using UnityEngine.EventSystems;

namespace Nindo
{
    /// <summary>
    /// La rueda sobre la lista de Opciones › Controles, en muescas (un touchpad manda fracciones). La lista la corre
    /// UIManager de parada en parada con la misma suavidad que el teclado y el mando: un ScrollRect la movía 240 px de
    /// golpe por muesca (6 de delta del Input System por su sensibilidad) y la dejaba con filas cortadas a la mitad.
    /// </summary>
    public class UIControlsScroll : MonoBehaviour, IScrollHandler
    {
        public Action<float> onScroll;

        public void OnScroll(PointerEventData e)
        {
            var es = EventSystem.current;
            // el delta del módulo depende de su configuración: lo pasa a muescas él mismo
            Vector2 ticks = es != null && es.currentInputModule != null ? es.currentInputModule.ConvertPointerEventScrollDeltaToTicks(e.scrollDelta) : e.scrollDelta;
            if (ticks.y != 0f) onScroll?.Invoke(ticks.y);
        }
    }
}
