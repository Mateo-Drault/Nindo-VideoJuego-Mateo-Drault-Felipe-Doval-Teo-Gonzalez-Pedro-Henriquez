using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EnemyCombat : MonoBehaviour
{
    [SerializeField] private BoxCollider swordCollider;
    [SerializeField] private Animator animator;
    // Start is called before the first frame update
    void Start()
    {
        swordCollider.enabled = false;
    }

    // Update is called once per frame
    void Update()
    {
        
    }

    public void Attack()
    {
        animator.SetBool("isChasing", false);
        animator.SetTrigger("attack");
    }
    public void StartAttack()
    {
        swordCollider.enabled = true;
    }
    public void StopAttack()
    {
        swordCollider.enabled = false;
        animator.ResetTrigger("attack");
    }
}
