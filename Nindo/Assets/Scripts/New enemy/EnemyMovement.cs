using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

public class EnemyMovement : MonoBehaviour
{
    public Transform player;
    [SerializeField] private NavMeshAgent agent;
    private float distanceToPlayer;
    [SerializeField] private float maxDistance;
    [SerializeField] private float minDistance;
    [SerializeField] private float attackRange;
    [SerializeField] private Animator animator;

    [SerializeField] private EnemyBeingDamaged enemyBeingDamaged;


    [SerializeField] private EnemyCombat enemyCombat;

    public bool seen;
    public bool isAttacking = false;

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

        //Recibiendo danio
        if (enemyBeingDamaged != null && enemyBeingDamaged.isBeingDamaged)
        {
            agent.isStopped = true;
            animator.SetBool("isChasing", false);
            return;
        }

        // 
        if (!seen && distanceToPlayer <= minDistance)
        {
            seen = true;
        }

        if (!seen) return; // si no lo vio, no hace nada más


        //Atacar
        if (distanceToPlayer <= maxDistance)
        {
            Attack();
        }
        //Perseguir
        else if (distanceToPlayer >= maxDistance && seen)
        {
            Chase();
        }
        //Idle
        else
        {
            Idle();
        }

    }
    void Attack()
    {
        enemyCombat.Attack();
        isAttacking = true;
        agent.isStopped = true;
    }

    void Chase()
    {
        isAttacking = false;
        agent.isStopped = false;

        agent.SetDestination(player.position);
        Vector3 directionToPlayer = (player.position - transform.position).normalized;
        directionToPlayer.y = 0;
        Quaternion Target = Quaternion.LookRotation(directionToPlayer);
        transform.rotation = Quaternion.Slerp(transform.rotation, Target, rotationSpeed * Time.deltaTime);

        animator.ResetTrigger("attack");
        animator.SetBool("isChasing", true);
    }

    void Idle()
    {
        isAttacking = false;
        agent.isStopped = true;

        animator.ResetTrigger("attack");
        animator.SetBool("isChasing", false);
    }
}

