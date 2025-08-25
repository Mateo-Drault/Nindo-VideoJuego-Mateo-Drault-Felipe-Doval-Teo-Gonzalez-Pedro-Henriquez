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

    public bool seen;
    public bool isAttacking;
    // Start is called before the first frame update
    void Start()
    {

    }

    // Update is called once per frame
    void Update()
    {

        distanceToPlayer = Vector3.Distance(transform.position, player.position);

        if(distanceToPlayer < minDistance & !seen) //Idle
        {
            seen = true;
        }


        if (distanceToPlayer > maxDistance & !isAttacking && seen) //Persigue
        {
            agent.isStopped = false;
            agent.SetDestination(player.position);
            animator.SetBool("isChasing", true);
            animator.SetBool("isAttacking", false);

        }

        if (distanceToPlayer <= attackRange) //Ataca
        {
            isAttacking = true;
            agent.isStopped = true;
            animator.SetBool("isAttacking", true);
            animator.SetBool("isChasing", false);
        }
        else
        {
            isAttacking = false;
        }

    }
}

