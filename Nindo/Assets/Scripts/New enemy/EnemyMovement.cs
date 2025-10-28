using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

public class EnemyMovement : MonoBehaviour
{
    //scripts
    [SerializeField] private EnemyBeingDamaged enemyBeingDamaged;
    [SerializeField] private EnemyCombat enemyCombat;
    [SerializeField] private Animator animator;
    [SerializeField] private NavMeshAgent agent;

    //etc
    public Transform player;
    public float distanceToPlayer;
    [SerializeField] private float maxDistance;
    [SerializeField] private float minDistance;
    [SerializeField] public float attackRange;




    public bool seen;
    public bool isAttacking = false;
    [SerializeField] private bool isAttackingGeneral;

    [SerializeField] private float rotationSpeed = 10f;

    // Start is called before the first frame update
    void Start()
    {
        agent.updateRotation = false;
    }

    // Update is called once per frame
    void Update()
    {

        distanceToPlayer = Vector3.Distance(transform.position, player.position);
        //Chequear que no este golpeando asi se mueve
        AnimatorStateInfo animatorStateInfo = animator.GetCurrentAnimatorStateInfo(0);
        //if (animatorStateInfo.IsName("Attack1") | animatorStateInfo.IsName("Attack2") | animatorStateInfo.IsName("Attack3"))
        //{
        //    isAttackingGeneral = true;
        //} 
        //else
        //{
        //    isAttackingGeneral = false;
        //}
        //Recibiendo danio
        if (enemyBeingDamaged != null && enemyBeingDamaged.isStunned)
        {
            agent.isStopped = true;
            animator.SetBool("isChasing", false);
            return;
        }
        //Lo vio
        if (!seen && distanceToPlayer <= minDistance)
        {
            animator.SetTrigger("Spotted");
            Invoke("Seen", 0.1f);
        }
        if (!isAttacking)
        {
            //Atacar
            if (distanceToPlayer <= attackRange && seen && !enemyCombat.isParrying)
            {
                Attack();
            }
            //Perseguir
            else if (distanceToPlayer > maxDistance && seen && !enemyCombat.isParrying)
            {
                Chase();
            }
            //Idle

            else
            {
                Idle();
            }
        }
    }
    void Seen()
    {
        seen = true;
    }
    void Attack()
    {
        agent.isStopped = true;
        animator.SetBool("isChasing", false);
        enemyCombat.Attac();

    }

    void Chase()
    {
        if (!animator.GetCurrentAnimatorStateInfo(0).IsName("EnemySpotted"))
        {
            agent.isStopped = false;
            agent.SetDestination(player.position);
        }

        // Girar suavemente hacia el jugador
        Vector3 directionToPlayer = (player.position - transform.position).normalized;
        directionToPlayer.y = 0;
        Quaternion targetRotation = Quaternion.LookRotation(directionToPlayer);
        transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, rotationSpeed * Time.deltaTime);

        // Animaciones de movimiento
        animator.SetBool("isChasing", true);
    }

    void Idle()
    {
        isAttacking = false;
        agent.isStopped = true;
        animator.SetBool("isChasing", false);
    }
}

