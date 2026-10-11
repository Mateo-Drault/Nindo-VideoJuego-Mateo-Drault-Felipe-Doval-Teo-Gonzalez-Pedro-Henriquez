using TMPro;
using UnityEngine;
using UnityEngine.UI;

namespace Nindo
{
    /// <summary>
    /// Indicador de guardado, abajo a la izquierda (~3 s): un pergamino se desenrolla, el pincel escribe "Guardado"
    /// y cae el sello rojo del nudo de la bandana con un golpe seco; después se vuelve a enrollar. Antes el único
    /// aviso era " — partida guardada" pegado al nombre del santuario en el cartel del medio. Lo dispara cualquier
    /// SaveSystem.Save (GameEvents.Saved); si se guarda de nuevo mientras se ve, vuelve a sellar sin rehacer todo.
    /// Va en la capa de la historia (no en el HUD): también se ve cuando se guarda en una cinemática.
    /// </summary>
    public partial class UIManager
    {
        const float SaveUnroll = 0.3f, SaveWrite = 0.75f, SaveStampAt = 1.2f, SaveRollAt = 2.45f, SaveEnd = 3f;
        const float SavePaperW = 236f, SavePaperH = 76f;

        RectTransform saveRoot, saveRodR, saveBrush, saveStamp;
        CanvasGroup saveGroup;
        Image savePaper, saveStampImg;
        TextMeshProUGUI saveText;
        float saveT = -1f;
        bool saveStamped;

        void BuildSaveIndicator()
        {
            saveRoot = UIFactory.Rect("SaveIndicator", story, Vector2.zero, Vector2.zero, new Vector2(0f, 0f), new Vector2(46f, 40f), new Vector2(SavePaperW + 80f, 110f));
            saveGroup = saveRoot.gameObject.AddComponent<CanvasGroup>();
            saveGroup.alpha = 0f;
            saveGroup.blocksRaycasts = false;

            savePaper = UIFactory.Image("Paper", saveRoot, Color.white, new Vector2(0f, 0.5f), new Vector2(10f, 0f), new Vector2(SavePaperW, SavePaperH), UISprites.ScrollPaper);
            savePaper.rectTransform.pivot = new Vector2(0f, 0.5f);
            savePaper.type = Image.Type.Filled; savePaper.fillMethod = Image.FillMethod.Horizontal; savePaper.fillOrigin = 0;
            if (savePaper.sprite == null) savePaper.color = UIFactory.Paper;

            saveText = UIFactory.NoWrap(UIFactory.Text("Text", saveRoot, "Guardado", 32, UIFactory.Ink, new Vector2(0f, 0.5f), new Vector2(34f, 2f), new Vector2(180f, 50f), TextAlignmentOptions.Left, true));
            saveText.rectTransform.pivot = new Vector2(0f, 0.5f);
            saveText.color = new Color(0.09f, 0.07f, 0.08f, 1f);

            UIFactory.Centered("RodL", saveRoot, Color.white, new Vector2(0f, 0.5f), new Vector2(10f, 0f), new Vector2(14f, SavePaperH + 16f), UISprites.ScrollRod);
            saveRodR = UIFactory.Centered("RodR", saveRoot, Color.white, new Vector2(0f, 0.5f), new Vector2(10f, 0f), new Vector2(14f, SavePaperH + 16f), UISprites.ScrollRod).rectTransform;

            saveStampImg = UIFactory.Centered("Stamp", saveRoot, Color.white, new Vector2(0f, 0.5f), new Vector2(10f + SavePaperW - 40f, 2f), new Vector2(54f, 54f), UISprites.Get("Hanko_IconKnot"));
            saveStamp = saveStampImg.rectTransform;

            var brush = UIFactory.Centered("Brush", saveRoot, Color.white, new Vector2(0f, 0.5f), Vector2.zero, new Vector2(58f, 58f), UISprites.Fude);
            saveBrush = brush.rectTransform;
            saveBrush.pivot = new Vector2(0.08f, 0.1f);   // la punta del pincel (abajo a la izquierda del sprite)
            saveRoot.gameObject.SetActive(false);
        }

        void OnGameSaved()
        {
            if (saveRoot == null) return;
            // ya sellado y todavía abierto: vuelve a caer el sello (otro guardado seguido) sin desenrollar de nuevo
            if (saveT >= 0f && saveT < SaveRollAt) { if (saveT > SaveStampAt) { saveT = SaveStampAt; saveStamped = false; } return; }
            saveT = 0f; saveStamped = false;
            saveRoot.gameObject.SetActive(true);
        }

        void UpdateSaveIndicator(float dt)
        {
            if (saveT < 0f) return;
            saveT += dt;
            float t = saveT;
            if (t >= SaveEnd) { saveT = -1f; saveRoot.gameObject.SetActive(false); return; }

            // desenrolla, queda abierto y se vuelve a enrollar desde la derecha
            float open = t < SaveRollAt ? UIAnim.OutCubic(t / SaveUnroll) : 1f - UIAnim.InCubic((t - SaveRollAt) / (SaveEnd - SaveRollAt - 0.1f));
            open = Mathf.Clamp01(open);
            savePaper.fillAmount = open;
            saveRodR.anchoredPosition = new Vector2(10f + SavePaperW * open, 0f);
            saveGroup.alpha = Mathf.Clamp01(t / 0.12f) * (t > SaveEnd - 0.2f ? (SaveEnd - t) / 0.2f : 1f);

            // el pincel escribe "Guardado" letra por letra y se va; el texto se enrolla con el papel
            int n = saveText.text.Length;
            float wk = Mathf.Clamp01((t - SaveUnroll) / SaveWrite);
            int shown = t < SaveRollAt ? Mathf.CeilToInt(wk * n) : n;
            if (saveText.maxVisibleCharacters != shown) saveText.maxVisibleCharacters = shown;
            float textRight = 34f + saveText.preferredWidth * wk;
            saveText.alpha = t < SaveRollAt ? 1f : open;
            bool writing = t > SaveUnroll - 0.1f && t < SaveUnroll + SaveWrite + 0.25f;
            saveBrush.gameObject.SetActive(writing);
            if (writing)
            {
                // trazos cortos: sube y baja con cada letra y se inclina hacia donde va
                float bob = Mathf.Abs(Mathf.Sin(wk * n * Mathf.PI)) * 9f;
                float leave = Mathf.Clamp01((t - SaveUnroll - SaveWrite) / 0.25f);
                saveBrush.anchoredPosition = new Vector2(textRight + 4f + leave * 30f, -6f + bob + leave * 36f);
                saveBrush.localRotation = Quaternion.Euler(0f, 0f, -8f + 10f * Mathf.Sin(wk * n * Mathf.PI * 2f));
                var bc = Color.white; bc.a = 1f - leave; saveBrush.GetComponent<Image>().color = bc;
            }

            // el sello cae grande y girado, golpea (pequeño rebote) y queda; se borra al enrollar
            if (t >= SaveStampAt && !saveStamped)
            {
                saveStamped = true;
                Game.Audio?.Play("seal", null, 0.35f);
            }
            float st = t - SaveStampAt;
            if (st < 0f || t >= SaveRollAt + 0.1f) saveStampImg.enabled = false;
            else
            {
                saveStampImg.enabled = true;
                float k = Mathf.Clamp01(st / 0.14f);
                float s = st < 0.14f ? Mathf.Lerp(1.9f, 0.92f, k * k) : 0.92f + 0.08f * UIAnim.OutCubic((st - 0.14f) / 0.12f);
                saveStamp.localScale = Vector3.one * s;
                saveStamp.localRotation = Quaternion.Euler(0f, 0f, Mathf.Lerp(-24f, -7f, k));
                saveStampImg.color = new Color(1f, 1f, 1f, Mathf.Clamp01(st / 0.06f));
            }
        }
    }
}
