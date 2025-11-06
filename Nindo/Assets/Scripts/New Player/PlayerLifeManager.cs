using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
public class PlayerLifeManager : MonoBehaviour
{
    public float actualHealth;
    public float maxHealth;
    [SerializeField] private Image redBar;

    void Start()
    {
        maxHealth = actualHealth;
    }

    void Update()
    {
        if (actualHealth <= 0)
        {
            SceneManager.LoadScene(SceneManager.GetActiveScene().name);
            //Destroy(gameObject);
        }
    }
    void restartScene()
    {
        SceneManager.LoadScene(SceneManager.GetActiveScene().name);
    }
    public void UpdatePlayerHealthBar(float health, float maxHeatlh)
    {
        redBar.fillAmount = health / maxHeatlh;
    }
}
