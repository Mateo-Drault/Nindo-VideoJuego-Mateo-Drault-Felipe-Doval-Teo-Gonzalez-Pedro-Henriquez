using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerDamaged : MonoBehaviour
{
    [SerializeField] PlayerLifeManager playerLifeManager;
    [SerializeField] PlayerHealthBar playerHealthBar;
    public float enemyDamage;
    public bool hasRecievedDamage = false;
    public float invincibilityDuration;

    // Start is called before the first frame update
    void Start()
    {
        playerHealthBar.UpdatePlayerHealthBar(playerLifeManager.actualHealth, playerLifeManager.maxHealth);
    }

    // Update is called once per frame
    void Update()
    {
        
    }

    private void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("EnemySword") && !hasRecievedDamage)
        {
            playerLifeManager.actualHealth -= enemyDamage;
            playerHealthBar.UpdatePlayerHealthBar(playerLifeManager.actualHealth, playerLifeManager.maxHealth);
            Invoke("RestartInvincibility", invincibilityDuration);
            hasRecievedDamage = true;
        }
    }

    void RestartInvincibility()
    {
        hasRecievedDamage = false;
    }
}
