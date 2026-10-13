using TMPro;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// "[Enter] Saltar" abajo a la derecha (donde cae la franja negra de abajo cuando la hay) mientras algo que ya se vio
    /// se puede saltar (el rezo corto en los santuarios, una vez visto el entero). Entra un segundo después de empezar,
    /// para no sumarle un cartel al primer instante; la tecla sigue al dispositivo (Enter, A, ×). Canvas propio: no toca
    /// la UI del juego.
    /// </summary>
    public class SkipHint : MonoBehaviour
    {
        static SkipHint instance;
        RectTransform key;
        CanvasGroup group;
        float shownFor, alpha;
        bool visible;
        int glyphs = -1;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatic() => instance = null;

        public static void Show()
        {
            if (instance == null) instance = Build();
            if (instance == null) return;
            instance.visible = true;
            instance.shownFor = 0f;
        }

        public static void Hide() { if (instance != null) instance.visible = false; }

        static SkipHint Build()
        {
            if (Game.UI == null) return null;
            var canvas = UIFactory.CreateCanvas("Nindo Saltar", 12);
            canvas.GetComponent<UnityEngine.UI.CanvasScaler>().screenMatchMode = UnityEngine.UI.CanvasScaler.ScreenMatchMode.Expand;
            canvas.transform.SetParent(Game.UI.transform, false);
            var root = UIFactory.At("Saltar", canvas.transform, new Vector2(1f, 0f), new Vector2(-56f, 38f), new Vector2(260f, 48f));
            var h = root.gameObject.AddComponent<SkipHint>();
            h.group = root.gameObject.AddComponent<CanvasGroup>();
            h.group.alpha = 0f;
            h.group.blocksRaycasts = false;
            // la palabra a la derecha y la tecla a su izquierda: el borde derecho queda fijo aunque la tecla cambie de ancho
            var label = UIFactory.NoWrap(UIFactory.Text("Texto", root, "Saltar", 30, UIFactory.Paper, new Vector2(1f, 0.5f), Vector2.zero, new Vector2(120f, 44f), TextAlignmentOptions.Right));
            UIFactory.Legible(label);
            h.key = UIFactory.KeyCap(root, "Enter", 40f, new Vector2(1f, 0.5f), new Vector2(-150f, 0f));
            return h;
        }

        void Update()
        {
            float dt = Time.unscaledDeltaTime;
            shownFor += dt;
            alpha = Mathf.MoveTowards(alpha, visible && shownFor > 1f && !Game.IsPaused ? 1f : 0f, dt * 4f);
            group.alpha = alpha * (0.75f + 0.25f * Mathf.Sin(Time.unscaledTime * 2.4f));
            var input = Game.Input;
            if (input != null && input.GlyphVersion != glyphs)
            {
                glyphs = input.GlyphVersion;
                UIFactory.SetKeyCap(key, input.Glyph(Act.Submit));
                // la tecla termina 12 px antes de "Saltar"
                key.anchoredPosition = new Vector2(-120f - 12f - key.sizeDelta.x * 0.5f, 0f);
            }
        }
    }
}
