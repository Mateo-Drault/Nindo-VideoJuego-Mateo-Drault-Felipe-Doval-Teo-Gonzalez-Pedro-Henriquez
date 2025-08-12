using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerBeingDamaged : MonoBehaviour
{
    [SerializeField] private float enemySwordDamage; //esto va a la espada del enemigo mas adelante
    [SerializeField] private PlayerLifeManager playerLifeManager;
    [SerializeField] private PlayerHealthBar PlayerHealthBar;


    // Start is called before the first frame update
    void Start()
    {
        PlayerHealthBar.UpdatePlayerHealthBar(playerLifeManager.actualHealth, playerLifeManager.maxHealth);
    }

    // Update is called once per frame
    void Update()
    {
        
    }
    private void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("EnemySword"))
        {
            playerLifeManager.actualHealth -= enemySwordDamage;
            PlayerHealthBar.UpdatePlayerHealthBar(playerLifeManager.actualHealth, playerLifeManager.maxHealth);
        }
    }
}
