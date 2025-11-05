using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
public class PlayerLifeManager : MonoBehaviour
{
    public float actualHealth;
    public float maxHealth;

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
}
