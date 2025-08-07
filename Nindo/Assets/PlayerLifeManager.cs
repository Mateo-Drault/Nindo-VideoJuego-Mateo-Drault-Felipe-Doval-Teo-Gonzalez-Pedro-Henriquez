using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;
public class PlayerLifeManager : MonoBehaviour
{
    public float actualHealth;
    public float maxHealth;

    // Start is called before the first frame update
    void Start()
    {
        maxHealth = actualHealth;
    }

    // Update is called once per frame
    void Update()
    {
        if(actualHealth <= 0)
        {
            Destroy(gameObject);

        }
    }
    void restartScene()
    {
        SceneManager.LoadScene(SceneManager.GetActiveScene().name);
    }
}
