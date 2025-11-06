using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
public class PlayerLifeManager : MonoBehaviour
{
    public float currentHealth;
    public float maxHealth = 100f;
    [SerializeField] private float healthRate = 30f;
    [SerializeField] private Image healthBar;
    private void Awake()
    {
        currentHealth = maxHealth;
        healthBar.fillAmount = maxHealth;

    }

    void Update()
    {
        if (currentHealth <= 0)
        {
            restartScene();
            //Destroy(gameObject);
        }

        if (currentHealth / maxHealth != healthBar.fillAmount) //Si la vida actual no es la misma a la que se muestra en pantalla
        {
            float objectiveHealth;
            if (currentHealth / maxHealth > healthBar.fillAmount)
            {
                objectiveHealth = healthBar.fillAmount * maxHealth + (healthRate * Time.deltaTime);
                objectiveHealth = Math.Min(objectiveHealth, currentHealth);
            } else
            {
                objectiveHealth = healthBar.fillAmount * maxHealth - (healthRate * Time.deltaTime);
                objectiveHealth = Math.Max(objectiveHealth, currentHealth);
            }
            UpdatePlayerCertainHealthBar(objectiveHealth);
        }
    }
    void restartScene()
    {
        SceneManager.LoadScene(SceneManager.GetActiveScene().name);
    }

    public void DamageTaken(float damage)
    {
        currentHealth -= damage;
    }

    public void UpdatePlayerCertainHealthBar(float objective)
    {
        healthBar.fillAmount = objective / maxHealth;
    }
}
