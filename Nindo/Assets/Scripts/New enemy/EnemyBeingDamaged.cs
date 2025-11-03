    using System.Collections;
    using System.Collections.Generic;
    using UnityEngine;

    public class EnemyBeingDamaged : MonoBehaviour
    {
        //seteados desde el inspector
        [SerializeField] private healthScript healthScript;
        [SerializeField] private EnemyCombat enemyCombat;
        [SerializeField] private EnemyHitbox hitbox;
        [SerializeField] private Rigidbody rb;
        [SerializeField] private Transform playerTransform;
        [SerializeField] Animator animator;
        [SerializeField] private GameObject enemyEntity;
        [SerializeField] private bool isBeingDamaged;
        [SerializeField] private float safeTime;

        //knockback
        [SerializeField] private float knockbackForce;
        [SerializeField] private float knockbackDuration;


        //animaciones
        [SerializeField] public float stunDuration;
        [SerializeField] public float stunTimer;
        public bool isStunned = false;
        public bool superArmor = false; //no puede recibir mas stun


        //Script vida
        public float Health;
        public float maxHealthAmount;
        public float finisherThreshold = 20f;
        [SerializeField] private float damageAmount; //se va a cambiar a la espada este valor
        [SerializeField] private GameObject F;
        public bool isFinishable;


        //Parry
        public bool parryHit;

 
            void Start()
        {
            Health = maxHealthAmount;
            healthScript.UpdateHealthBar(maxHealthAmount, Health);
        }

        // Update is called once per frame
        void Update()
        {
            if (isStunned)
            {
                stunTimer -= Time.deltaTime;
                if (stunTimer <= 0)
                {
                    animator.SetBool("isStunned", false);
                    isStunned = false;

                }
            }
        if (isBeingDamaged) 
        {
            safeTime -= Time.deltaTime;
            if (safeTime <= 0)
            {
                isBeingDamaged = false;
            }
        }
        if (animator.GetCurrentAnimatorStateInfo(0).IsName("Stunned"))
        {
            safeTime -= Time.deltaTime;
            if (safeTime <= 0)
            {
                animator.SetBool("isStunned", false);
            }
        }
        if (Health<= finisherThreshold) 
        {
            F.SetActive(true);
            isFinishable = true;
        }

    }
        void OnTriggerEnter(Collider other)
        {
        if (other.CompareTag("PlayerSword") && !isBeingDamaged)
            {           
                //Animaciones
                stunTimer = stunDuration;
                animator.SetBool("isStunned", true);
                isStunned = true;
                parryHit = true;
                isBeingDamaged = true;
                Health -= damageAmount;
                    if (Health <= 0)
                    {
                        Invoke(nameof(Death), knockbackDuration);
                    }
                    healthScript.UpdateHealthBar(maxHealthAmount, Health);


            }

        }
    public void Death()
        {
            Destroy(enemyEntity);
        }
    }
