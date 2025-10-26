using System.Collections;
using Unity.VisualScripting;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;
using UnityEngine.UI;

public class MainMenu : MonoBehaviour
{
    [SerializeField] private Image nindoBackground;
    [SerializeField] private Sprite nindoOpenEyes;

    [SerializeField] private CanvasGroup menuButtons; 
    [SerializeField] private float fadeDuration = 1f; 

    public void PlayGame()
    {
        menuButtons.interactable = false; // desactivo los botones
        menuButtons.blocksRaycasts = false; // para que no reciban eventos
        EventSystem.current?.SetSelectedGameObject(null); // deselecciono cualquier botón seleccionado
        StartCoroutine(ChangeBackgroundSmooth());

    }

    private IEnumerator ChangeBackgroundSmooth()
    {

    Transform parent = nindoBackground.transform.parent;
    if (parent == null)
    {
        var canvas = nindoBackground.GetComponentInParent<Canvas>();
        if (canvas != null) parent = canvas.transform;
    }

    // Crear GameObject con componentes UI básicos
    Image fadeImage = new GameObject("FadeImage", typeof(RectTransform), typeof(CanvasRenderer), typeof(Image)).GetComponent<Image>();

    // Parentear (si hay parent)
    if (parent != null)
    {
        fadeImage.transform.SetParent(parent, false); // false para no alterar escala/pos
        // poner justo por encima del Nindo para que no quede por detrás
        int targetIndex = nindoBackground.transform.GetSiblingIndex() + 1;
        fadeImage.transform.SetSiblingIndex(Mathf.Clamp(targetIndex, 0, parent.childCount - 1));
    }

    // Asignar sprite y properties
    fadeImage.sprite = nindoOpenEyes;
    fadeImage.raycastTarget = false;
    fadeImage.color = new Color(1f, 1f, 1f, 0f);

    // Copiar rect transform del background (para que tenga mismo tamaño/anchos)
    fadeImage.rectTransform.sizeDelta = nindoBackground.rectTransform.sizeDelta;
    fadeImage.GetComponent<RectTransform>().anchorMin = nindoBackground.rectTransform.anchorMin;
    fadeImage.GetComponent<RectTransform>().anchorMax = nindoBackground.rectTransform.anchorMax;
        // Fade in de la nueva imagen
        float t = 0f;
        while (t < fadeDuration)
        {
            t += Time.deltaTime;
            float alpha = t / fadeDuration; // de 0 a 1
            menuButtons.alpha = Mathf.Lerp(1f, 0f, t / fadeDuration); // fade out de los botones
            fadeImage.color = new Color(1, 1, 1, alpha); // fade in de la nueva imagen
            yield return null;
        }

        // Terminar la transición
        nindoBackground.sprite = nindoOpenEyes;
        Destroy(fadeImage.gameObject);

        yield return new WaitForSeconds(1f); // esperar un poquito más antes de empezar el juego

        SceneManager.LoadScene(SceneManager.GetActiveScene().buildIndex + 1);
    }

    public void QuitGame()
    {
        Debug.Log("QUIT");
        Application.Quit();
    }
}

