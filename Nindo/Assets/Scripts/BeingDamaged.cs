using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class BeingDamaged : MonoBehaviour
{
    [SerializeField] private Rigidbody rb;
    [SerializeField] private Transform playerTransform;
    [SerializeField] private float knockbackForce;
    [SerializeField] private float knockbackDuration;

    public float Health;
    public float maxHealthAmount;
    [SerializeField] private float damageAmount; //se va a cambiar a la espada este valor
    [SerializeField] private GameObject enemyEntity;
    [SerializeField] private healthScript healthScript;

   

    public bool isBeingDamaged = false;
    // Start is called before the first frame update
    void Start()
    {
        Health = maxHealthAmount;
        healthScript.UpdateHealthBar(maxHealthAmount, Health);
    }

    // Update is called once per frame
    void Update()
    {
    }
    void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("Player"))
        {
            isBeingDamaged = true;
            rb.velocity = Vector3.zero;
            Vector3 knockback = (transform.position - playerTransform.position).normalized;
            knockback.y = 0f;
            rb.AddForce(knockback * knockbackForce, ForceMode.Impulse);
            Invoke(nameof(StopKnockback), knockbackDuration);
             
            Health -= damageAmount;
            if (Health <= 0)
            {
                Invoke(nameof(Death), knockbackDuration);
            }
            healthScript.UpdateHealthBar(maxHealthAmount, Health);

        }

    }
    void StopKnockback()
    {
        isBeingDamaged= false;
    }
    void Death()
    {
        Destroy(enemyEntity);
    }
}
