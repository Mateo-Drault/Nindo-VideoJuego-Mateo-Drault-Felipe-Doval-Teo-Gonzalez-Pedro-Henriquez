using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class ManaBar : MonoBehaviour
{

    [SerializeField] Image manaBar;
    public const float maxMana = 100f;
    public float currentMana;
    [SerializeField] float regeneracionMana = 5f;
    [SerializeField] float delayRegeneracion = 2f;
    [SerializeField] float realTime;
    private void Awake()
    {
        manaBar.fillAmount = maxMana;
    }

    public ManaBar()
    {
        currentMana = 100f;
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
        //if(currentMana <= maxMana)
        //{
        //    currentMana += regeneracionMana * Time.deltaTime;
        //    currentMana = Math.Min(currentMana, maxMana);
        //    UpdateManaBar();
        //    realTime = 0;
        //}
    }

    public void gastarMana(float manaGastada)
    {
        currentMana -= manaGastada;
        UpdateManaBar();
    }

    public void UpdateManaBar()
    {
        manaBar.fillAmount = currentMana / maxMana;
    }
}
