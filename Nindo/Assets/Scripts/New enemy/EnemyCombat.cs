using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EnemyCombat : MonoBehaviour
{
    //scripts y objetos seteados por el inspector
    [SerializeField] private EnemyMovement enemyMovement;
    [SerializeField] private EnemyBeingDamaged enemyBeingDamaged;
    [SerializeField] private PlayerCombat playerCombat;
    [SerializeField] private CapsuleCollider parryCollider;
    [SerializeField] private MeshCollider swordCollider;
    [SerializeField] private Animator animator;


    //Parry
    [SerializeField] private float maxHitsBeforeParry;
    [SerializeField] private float actualHitsBeforeParry;
    public enum HitboxMode { Idle, Attack, Parry }
    public HitboxMode currentMode = HitboxMode.Idle;
    [SerializeField] public bool isParrying;
    [SerializeField] private GameObject Katana;

    public ParticleSystem chispas;
    [SerializeField] float chispasDuration;

    void Start()
    {
        actualHitsBeforeParry = maxHitsBeforeParry;
        swordCollider.enabled = false;
        currentMode = HitboxMode.Idle;
    }

    // Update is called once per frame
    void Update()
    {
        if (enemyBeingDamaged.parryHit) //menos golpes para hacer parry
        {
            HitsToParry();
        }
        if (actualHitsBeforeParry <= 0) //si llega a 0, hacer parry
        {
            TriggerParry();
        }
        else
        {
            animator.ResetTrigger("Parry");
        }
        AnimatorStateInfo animatorStateInfo = animator.GetCurrentAnimatorStateInfo(0);
        if (animatorStateInfo.IsName("Parrying")) //saber si esta parreando
        {
            currentMode = HitboxMode.Parry;

        }
        else
        {
            isParrying = false;
            gameObject.tag = "EnemySword";
            currentMode = HitboxMode.Idle;
        }
    }

    public void Attack() //atacar (llamado desde EnemyMovement)
    {
        animator.SetBool("isChasing", false);
        animator.SetTrigger("attack");
    }
    public void StartAttack() //llamado desde la animacion (en el EventReciever)
    {
        swordCollider.enabled = true;
    }
    public void StopAttack() //llamado desde la animacion (en el EventReciever)
    {
        swordCollider.enabled = false;
        animator.ResetTrigger("attack");
        enemyMovement.isAttacking = false;
    }



    void TriggerParry()
    {
        animator.SetBool("isStunned", false);
        animator.SetTrigger("Parry");
        actualHitsBeforeParry = maxHitsBeforeParry;
        currentMode = HitboxMode.Parry;
    }
    void HitsToParry()
    {
        actualHitsBeforeParry -= 1;
        enemyBeingDamaged.parryHit = false;
    }
    public void StartParry() //llamado desde la animacion (en el EventReciever)
    {
        Katana.tag = "Parry";
        isParrying = true;
        parryCollider.enabled = true;
    }
    public void EndParry() //llamado desde la animacion (en el EventReciever)
    {
        Katana.tag = "EnemySword";
        isParrying = false;
        parryCollider.enabled = false;
        animator.ResetTrigger("Parry");
    }

    private void OnTriggerEnter(Collider other)
    {
        if (currentMode == HitboxMode.Parry & other.CompareTag("Player")) //si el arma del jugador impacta con la espada al hacer parry:
        {
            playerCombat.InterrumptAttack();
            chispas.Play();
            Invoke("EndChispas", chispasDuration);
            animator.SetTrigger("HasParry"); //hacer el parry por el golpe

        }
    }

    public void InterruptAttack() //Lo llama la jugador al hacer parry
    {
        if (enemyMovement.isAttacking)
        {
            animator.SetBool("isStunned", true);
            animator.ResetTrigger("attack");
            enemyMovement.isAttacking = false;
            swordCollider.enabled = false;
            //se resetea solo
            enemyBeingDamaged.isStunned = true;
            enemyBeingDamaged.stunTimer = enemyBeingDamaged.stunDuration;
        }
    }
    public void EndChispas()
    {
        chispas.Stop();
    }
}
