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
    [SerializeField] float manaRate = 75f;
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

        //Dash
        if (Input.GetKeyDown(KeyCode.P))
        {
            gastarMana(10);
        }

       
        if(currentMana / maxMana != manaBar.fillAmount)
        {
            float objectiveMana;
            if(currentMana / maxMana > manaBar.fillAmount)
            {
                objectiveMana = manaBar.fillAmount * 100 + (manaRate * Time.deltaTime);
                objectiveMana = Math.Min(objectiveMana, currentMana);
            } else
            {
                objectiveMana = manaBar.fillAmount * 100 - (manaRate * Time.deltaTime);
                objectiveMana = Math.Max(objectiveMana, currentMana);
            }

                UpdateCertainManaBar(objectiveMana);
            
        }
    }

    public void gastarMana(float manaGastada)
    {
        currentMana -= manaGastada;
    }

    public void UpdateCertainManaBar(float objective)
    {
        manaBar.fillAmount = objective / maxMana;
    }
}
