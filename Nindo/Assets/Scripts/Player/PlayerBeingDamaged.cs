using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerBeingDamaged : MonoBehaviour
{
    [SerializeField] private float enemySwordDamage; //esto va a la espada del enemigo mas adelante
    [SerializeField] private PlayerLifeManager playerLifeManager;
    [SerializeField] private PlayerHealthBar PlayerHealthBar;
    private bool hasRecivedDamage = false;
    public Material originalMaterial;
    public Material newMaterial;

    [SerializeField] private float invincibilityDuration;
    [SerializeField] private Renderer playerRenderer;

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
        if (other.CompareTag("EnemySword")& !hasRecivedDamage)
        {
            playerRenderer.material = newMaterial;
            hasRecivedDamage = true;
            playerLifeManager.actualHealth -= enemySwordDamage;
            PlayerHealthBar.UpdatePlayerHealthBar(playerLifeManager.actualHealth, playerLifeManager.maxHealth);
            Invoke("RestartInvincibility", invincibilityDuration);
        }
    }
    public void RestartInvincibility()
    {
        hasRecivedDamage = false;
        playerRenderer.material = originalMaterial;
    }
}
