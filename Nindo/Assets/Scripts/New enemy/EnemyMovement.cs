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
        Debug.Log(distanceToPlayer);
        //Recibiendo danio
        if (enemyBeingDamaged != null && enemyBeingDamaged.isBeingDamaged)
        {
            agent.isStopped = true;
            animator.SetBool("isChasing", false);
            return;
        }
        //Lo vio
        if (!seen && distanceToPlayer <= minDistance)
        {
            seen = true;
        }

        //Atacar
        if (distanceToPlayer <= attackRange && seen && !enemyCombat.isParrying)
        {
            Attack();
        }
        //Perseguir
        else if (distanceToPlayer > maxDistance && seen && !isAttacking && !enemyCombat.isParrying)
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

