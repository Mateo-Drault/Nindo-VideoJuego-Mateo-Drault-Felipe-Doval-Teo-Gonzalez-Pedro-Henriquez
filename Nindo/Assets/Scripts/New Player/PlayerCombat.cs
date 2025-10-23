using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerCombat : MonoBehaviour
{
    [SerializeField] MeshCollider katanaCollider;
    [SerializeField] PlayerDamaged playerDamaged;
    [SerializeField] BoxCollider parryCollider;
    [SerializeField] private GameObject sword;
    //PlayerParry cositas

    public enum ParryMode { Idle, Parry }
    public ParryMode currentMode = ParryMode.Idle;

    [Header("PlayerParry")]

    [SerializeField] Animator anim;
    [SerializeField] private ParticleSystem chispas;
    [SerializeField] private float chispasDuration = 0.05f;
    [SerializeField] private BoxCollider playerBodyCollider;
    [SerializeField] EnemyCombat enemyCombat;

    [SerializeField] private float inmunityTime;
    public bool hasParried;
    public bool isParrying;

    
    [Header("PlayerSwordAnimation")]

    public bool isAttacking;
    public bool isStunned;




    void Awake()
    {

    }

    void Start()
    {
        isAttacking = false;
       
        anim.ResetTrigger("parry");
        isParrying = false;
        katanaCollider.enabled = false;
    }

    void Update()
    {
        if (Input.GetKeyDown(KeyCode.Space))
        {
            SwordHit();
        }

        if (Input.GetKeyDown(KeyCode.E))
        {
            ParryHit();
        }

        AnimatorStateInfo animatorStateInfo = anim.GetCurrentAnimatorStateInfo(0);
        if (animatorStateInfo.IsName("Parrying"))
        {

            currentMode = ParryMode.Parry;

        }
        else
        {
            currentMode = ParryMode.Idle;
        }
    }

    public void SwordHit()
    {
        if (!anim.GetCurrentAnimatorStateInfo(0).IsName("Attacking"))//animación de ataque
        {
            anim.SetTrigger("attack");
        }
    }
    public void ParryHit()
    {
        if (!anim.GetCurrentAnimatorStateInfo(0).IsName("Parrying"))//animación de ataque
        {
            anim.SetTrigger("parry");
        }
    }

    public void StartAttacking()
    {
        katanaCollider.enabled = true;
        isAttacking = true;
    }

    public void StopAttacking()
    {
        katanaCollider.enabled = false;
        isAttacking = false;
    }


    public void InterrumptAttack()
    {
        if (isAttacking)
        {
            anim.ResetTrigger("attack");
            anim.SetTrigger("stunned");
            isAttacking = false;
            katanaCollider.enabled = false;
        }
    }


    private void OnTriggerEnter(Collider other)
    {

        if (currentMode == ParryMode.Parry && other.CompareTag("EnemySword") && !playerDamaged.hasRecievedDamage)
        {
            hasParried = true;
            Invoke("EndInmunity", inmunityTime);
            chispas.Play();
            Invoke("EndChispas", chispasDuration);
            enemyCombat.InterruptAttack();
            Debug.Log("PARRRRRRRY");
        }
    }

    public void StartParry()
    {
        sword.tag = "PlayerParry";
        isParrying = true;
        parryCollider.enabled = true;
        currentMode = ParryMode.Parry;
        Debug.Log("gola");
    }
    public void EndParry()
    {
        isParrying = false;
        parryCollider.enabled = false;
        currentMode = ParryMode.Idle;

    }
    public void EndChispas()
    {
        chispas.Stop();
    }
    private void EndInmunity()
    {
        Debug.Log("parry ended");
        hasParried = false;
    }
}
