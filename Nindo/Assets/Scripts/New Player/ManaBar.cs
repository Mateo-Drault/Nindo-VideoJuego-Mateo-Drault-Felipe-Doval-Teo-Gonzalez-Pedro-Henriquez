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

       
        if(currentMana / maxMana != manaBar.fillAmount) //Si el mana actual no es la misma a la que se muestra en pantalla
        {
            float objectiveMana;
            if(currentMana / maxMana > manaBar.fillAmount)
            {
                objectiveMana = manaBar.fillAmount * maxMana + (manaRate * Time.deltaTime);
                objectiveMana = Math.Min(objectiveMana, currentMana);
            } else
            {
                objectiveMana = manaBar.fillAmount * maxMana - (manaRate * Time.deltaTime);
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
