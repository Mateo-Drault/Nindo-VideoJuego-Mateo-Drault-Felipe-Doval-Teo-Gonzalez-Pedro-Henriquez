using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EnemySwordAnimation : MonoBehaviour
{
    [SerializeField]followPlayer followPlayer;
    public Animator animator;
    public bool isAttacking;
    public BoxCollider swordCollider;


    // Start is called before the first frame update
    void Start()
    {
        isAttacking = false;
    }

    // Update is called once per frame
    void Update()
    {
        
    }
    public void SwordHit()
    {
        if (!animator.GetCurrentAnimatorStateInfo(0).IsName("Cylinder_Espadazo"))//animacion de la espada
        {
            animator.SetTrigger("hit");
        }
    }
    public void StopAttacking()
    {
        isAttacking=false;
        swordCollider.enabled = false;
    }
    public void StartAttaking()
    {
        swordCollider.enabled = true;
        isAttacking = true;
    }
}
