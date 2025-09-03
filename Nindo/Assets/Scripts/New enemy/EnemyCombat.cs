using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EnemyCombat : MonoBehaviour
{
    [SerializeField] private BoxCollider swordCollider;
    [SerializeField] private Animator animator;
    [SerializeField] private EnemyMovement enemyMovement;


    //Parry
    [SerializeField] private EnemyBeingDamaged EnemyBeingDamaged;
    [SerializeField] private float maxHitsBeforeParry;
    private float actualHitsBeforeParry;
    public enum HitboxMode { Idle, Attack, Parry }
    public HitboxMode currentMode = HitboxMode.Idle;
    [SerializeField] public bool isParrying;
    [SerializeField] private PlayerSwordAnimation PlayerSwordAnimation;
    [SerializeField] private CapsuleCollider parryCollider;

    // Start is called before the first frame update
    void Start()
    {
        actualHitsBeforeParry = maxHitsBeforeParry;
        swordCollider.enabled = false;
    }

    // Update is called once per frame
    void Update()
    {
        if (EnemyBeingDamaged.isBeingDamaged) //menos golpes para hacer parry
        {
            actualHitsBeforeParry -= 1;
        }
        if (actualHitsBeforeParry <= 0) //si llega a 0, hacer parry
        {
            TriggerParry();
        }
        AnimatorStateInfo animatorStateInfo = animator.GetCurrentAnimatorStateInfo(0);
        if (animatorStateInfo.IsName("Parrying")) //saber si esta parreando
        {
            currentMode = HitboxMode.Parry;

        }
        else
        {
            isParrying = false;
            swordCollider.enabled = false;
            gameObject.tag = "EnemySword";
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
        //Arreglar!!!!
        animator.SetTrigger("Parry");
        actualHitsBeforeParry = maxHitsBeforeParry;
        currentMode = HitboxMode.Parry;
    }
    public void StartParry() //llamado desde la animacion (en el EventReciever)
    {
        gameObject.tag = "Parry";
        animator.SetTrigger("Parry");
        isParrying = true;
        parryCollider.enabled = true;
    }
    public void EndParry() //llamado desde la animacion (en el EventReciever)
    {
        gameObject.tag = "Player";
        isParrying = false;
        parryCollider.enabled = false;
        animator.ResetTrigger("Parry");
    }

    private void OnTriggerEnter(Collider other)
    {
        if (currentMode == HitboxMode.Parry & other.CompareTag("Player")) //si el arma del jugador impacta con la espada al hacer parry:
        {
            PlayerSwordAnimation.InterrumptAttack();
            //chispas.Play(); Falta agregar chispas
            //Invoke("EndChispas", chispasDuration);
            animator.SetTrigger("HasParry"); //hacer el parry por el golpe

        }
    }
}
