using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerCombat : MonoBehaviour
{
    [SerializeField] MeshCollider katanaCollider;
    [SerializeField] PlayerDamaged playerDamaged;

    public GameObject Katana;
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

    [Header("Attack Movement")]
    public float attackDashSpeed = 5f;//velocidad del dash
    public float attackDashTime = 0.15f;//duración del dash en segundos
    private bool isDashing = false;

    [SerializeField] private PlayerMovement playerMovement; //ARREGLAR



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

        if (Input.GetKeyDown(KeyCode.LeftShift))
        {
            anim.SetTrigger("parry");
            StartParry();
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
    public void DoAttackDash()
    {
        StartCoroutine(AttackDash());
    }
    public void StartAttacking()
    {
        Katana.tag = "PlayerSwordAttacking";
        katanaCollider.enabled = true;
        isAttacking = true;

    }

    public void StopAttacking()
    {
        Katana.tag = "PlayerSword";
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
            Katana.tag = "PlayerSword";

        }
    }

    private IEnumerator AttackDash()
    {
        if (isDashing) yield break;//evita que se solapen dashes

        isDashing = true;
        float timer = 0f;

        while (timer < attackDashTime)
        {
            transform.position += transform.forward * attackDashSpeed * Time.deltaTime; //ARREGLARRR
            timer += Time.deltaTime;
            yield return null;
        }

        isDashing = false;
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
        }
    }

    public void StartParry()
    {
        Katana.tag = "PlayerSwordParry";
        isParrying = true;
        katanaCollider.enabled = true;
    }
    public void EndParry()
    {
        Katana.tag = "PlayerSword";
        isParrying = false;
        katanaCollider.enabled = false;
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
