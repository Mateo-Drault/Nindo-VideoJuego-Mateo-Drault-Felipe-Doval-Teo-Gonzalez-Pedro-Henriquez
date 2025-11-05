using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class ManaBar : MonoBehaviour
{

    [SerializeField] Image manaBar;
    public const int maxMana = 100;
    public float currentMana;
    [SerializeField] int regeneracionMana = 5;
    [SerializeField] float delayRegeneracion = 2f;
    [SerializeField] float realTime;
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
        realTime += Time.deltaTime;

        //Dash
        if (Input.GetKeyDown(KeyCode.P))
        {
            gastarMana(10);
        }

        //El maná aumenta 5f por segundo, pero está en constante aumento.
        if(currentMana <= maxMana)
        {
            currentMana += regeneracionMana * Time.deltaTime;
            currentMana = Math.Min(currentMana, maxMana);
            UpdateManaBar();
            realTime = 0;
        }
    }

    public void gastarMana(int manaGastada)
    {
        if (currentMana >= manaGastada)
        {
            currentMana -= manaGastada;
            UpdateManaBar();
        }
    }

    public void UpdateManaBar()
    {
        manaBar.fillAmount = currentMana / maxMana;
    }
}
