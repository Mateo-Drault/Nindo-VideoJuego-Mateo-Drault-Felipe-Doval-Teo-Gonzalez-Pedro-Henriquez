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
    public bool isAttacking = false;
    // Start is called before the first frame update
    void Start()
    {

    }

    // Update is called once per frame
    void Update()
    {

        distanceToPlayer = Vector3.Distance(transform.position, player.position);
        Debug.Log(distanceToPlayer);
        if(distanceToPlayer < minDistance & !seen) //Idle
        {
            seen = true;
        }


        if (distanceToPlayer > maxDistance && !isAttacking && seen) //Persigue
        {
            Debug.Log("persigue");
            agent.isStopped = false;
            agent.SetDestination(player.position);
            //animator.SetBool("isChasing", true); Falta animator
            //animator.SetBool("isAttacking", false); Falta animator

        }
        else
        {
            agent.isStopped = true;
        }
        if (distanceToPlayer <= attackRange) //Ataca
        {
            isAttacking = true;
            agent.isStopped = true;
            //animator.SetBool("isAttacking", true); Falta animator
            //animator.SetBool("isChasing", false); Falta animator
        }
        else
        {
            isAttacking = false;
        }

    }
}

