using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerSwordAnimation : MonoBehaviour
{
    public Animator animator;
    public bool isAttacking;
    public BoxCollider swordCollider;
    public bool isStunned;
    // Start is called before the first frame update
    void Start()
    {
        isAttacking = false;
    }

    // Update is called once per frame
    void Update()
    {
        if (Input.GetKeyDown(KeyCode.Space))
        {
            SwordHit();
        }
    }
    public void SwordHit()
    {
        if (!animator.GetCurrentAnimatorStateInfo(0).IsName("Cylinder_Espadazo"))//animacion de la espada
        {
            Debug.Log("hola");
            animator.SetTrigger("pHit");
        }
    }
    public void StopAttacking()
    {
        isAttacking = false;
        swordCollider.enabled = false;

    }
    public void StartAttaking()
    {
        swordCollider.enabled = true;
        isAttacking = true;

    }
    public void InterrumptAttack()
    {
        if (isAttacking)
        {
            animator.SetTrigger("stunned");
            animator.ResetTrigger("pHit");
            isAttacking = false;
            isStunned = true;
        }
    }
}
