using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class ManaBar : MonoBehaviour
{

    [SerializeField] Image manaBar;
    public const int maxMana = 100;
    public float currentMana;
    private float regeneracionMana;

    private void Awake()
    {
        manaBar.fillAmount = maxMana;
    }

    public ManaBar()
    {
        currentMana = 100;
    }

    private void Update()
    {
        if (Input.GetKeyDown(KeyCode.P))
        {
            gastarMana(10);
        }
    }

    public void gastarMana(int manaGastada)
    {
        if (currentMana >= manaGastada)
        {
            currentMana -= manaGastada;
            UpdateManaBar(currentMana, maxMana);
        }
    }

    public void UpdateManaBar(float currentMana, float maxMana)
    {
        manaBar.fillAmount = currentMana / maxMana;
    }
}
