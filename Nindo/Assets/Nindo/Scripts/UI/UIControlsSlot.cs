using System;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Nindo
{
    /// <summary>
    /// Una casilla de la página de controles (principal o alternativa de una acción en un dispositivo): la tecla de
    /// papel y, debajo, un trazo de pincel que se enciende en dorado cuando está elegida. Confirmar o clic espera la
    /// tecla nueva; clic derecho la quita. La dibuja UIManager (UIControls.cs) en cada cuadro con <see cref="Animate"/>.
    /// </summary>
    public class UIControlsSlot : Selectable, ISubmitHandler, IPointerClickHandler
    {
        public int row, dev, slot;
        public RectTransform key;
        public CanvasGroup keyGroup;
        public Image line;
        public Image[] dots;
        public Action<UIControlsSlot> onActivate, onClear;
        /// <summary>La última selección vino del mouse: la lista no se corre sola (si no, al pasar por la última fila
        /// visible la lista subía, el mouse caía sobre otra fila y la elegía).</summary>
        public bool byPointer;
        public bool silent;
        static bool selectingByPointer;
        public bool Selected { get; private set; }

        float k, pop, flash;

        public override void OnSelect(BaseEventData e)
        {
            base.OnSelect(e);
            if (!Selected && !silent) Game.Audio?.Play("ui_move", null, 0.35f);
            silent = false;
            Selected = true;
            byPointer = selectingByPointer;
            selectingByPointer = false;
        }

        public override void OnDeselect(BaseEventData e)
        {
            base.OnDeselect(e);
            Selected = false;
        }

        public override void OnPointerEnter(PointerEventData e)
        {
            base.OnPointerEnter(e);
            if (!IsInteractable() || EventSystem.current == null || EventSystem.current.currentSelectedGameObject == gameObject) return;
            selectingByPointer = true;
            EventSystem.current.SetSelectedGameObject(gameObject);
            selectingByPointer = false;
        }

        public void OnSubmit(BaseEventData e) { if (IsInteractable()) onActivate?.Invoke(this); }

        public void OnPointerClick(PointerEventData e)
        {
            if (!IsInteractable()) return;
            if (e.button == PointerEventData.InputButton.Left) onActivate?.Invoke(this);
            else if (e.button == PointerEventData.InputButton.Right) onClear?.Invoke(this);
        }

        /// <summary>Recién asignada: la tecla salta.</summary>
        public void Pop() => pop = 1f;
        /// <summary>Le cambió la tecla por un intercambio: el trazo destella para que se vea qué se movió.</summary>
        public void Flash() => flash = 1f;

        /// <param name="listening">Esta casilla espera la tecla nueva: la tecla se apaga y laten tres rombos.</param>
        public void Animate(float dt, bool listening, bool locked)
        {
            bool on = Selected || listening;
            k = Mathf.MoveTowards(k, on ? 1f : 0f, dt / (on ? UIAnim.Fast : 0.08f));
            pop = Mathf.MoveTowards(pop, 0f, dt / 0.28f);
            flash = Mathf.MoveTowards(flash, 0f, dt / 0.7f);
            float e = UIAnim.OutCubic(k), t = Time.unscaledTime;
            if (key != null)
            {
                key.SetScale(1f + 0.08f * e + 0.32f * pop * pop);
                keyGroup.SetAlpha(listening ? 0f : locked ? 0.45f : 1f);
            }
            if (line != null)
            {
                // en espera el trazo respira; elegido se enciende en dorado y se alarga; el destello del intercambio
                // lo prende un momento aunque no esté elegida
                float a = locked ? 0f : listening ? 0.55f + 0.4f * Mathf.Sin(t * 7f) : Mathf.Lerp(0.16f, 0.95f, Mathf.Max(e, flash));
                var c = Color.Lerp(UIFactory.Paper, UIFactory.Gold, Mathf.Max(e, flash));
                c.a = a;
                line.color = c;
                line.rectTransform.SetSize(new Vector2(Mathf.Lerp(132f, 172f, Mathf.Max(e, flash * 0.6f)), 12f));
            }
            for (int i = 0; dots != null && i < dots.Length; i++)
            {
                if (dots[i].enabled != listening) dots[i].enabled = listening;
                if (!listening) continue;
                // los rombos laten de a uno, de izquierda a derecha (la espera se entiende sin texto)
                float beat = Mathf.Repeat(t * 1.6f - i * 0.22f, 1f);
                float s = beat < 0.3f ? UIAnim.OutCubic(beat / 0.3f) : 1f - UIAnim.InCubic((beat - 0.3f) / 0.7f);
                dots[i].rectTransform.SetScale(0.7f + 0.5f * s);
                var dc = UIFactory.Gold; dc.a = 0.35f + 0.65f * s; dots[i].color = dc;
            }
        }
    }
}
