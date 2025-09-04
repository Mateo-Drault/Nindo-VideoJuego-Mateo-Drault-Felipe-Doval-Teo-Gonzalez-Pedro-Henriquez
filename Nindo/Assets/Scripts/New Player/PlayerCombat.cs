using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerCombat : MonoBehaviour
{
    //PlayerSwordAnimation cositas

    public Animator animator;
    public bool isAttacking;
    public BoxCollider swordCollider;
    public bool isStunned;

    [Header("Attack Movement")]
    public float attackDashSpeed = 5f;//velocidad del dash
    public float attackDashTime = 0.15f;//duración del dash en segundos
    private bool isDashing = false;

    [SerializeField] private PlayerMovement playerMovement; //ARREGLAR

    //PlayerBeingDamaged cositas

    public bool hasRecievedDamage = false;
    [SerializeField] private Renderer playerRenderer;
    public Material originalMaterial;
    public Material newMaterial;
    [SerializeField] private PlayerLifeManager playerLifeManager;
    [SerializeField] private PlayerHealthBar PlayerHealthBar;
    [SerializeField] private float enemyDamage; //conectarlo con el enemigo de mate
    [SerializeField] private float invincibilityDuration;

    void Start()
    {
        isAttacking = false;
        PlayerHealthBar.UpdatePlayerHealthBar(playerLifeManager.actualHealth, playerLifeManager.maxHealth);
    }

    void Update()
    {
        if (Input.GetKeyDown(KeyCode.Space))
        {
            SwordHit();
        }
    }

    public void SwordHit()
    {
        if (!animator.GetCurrentAnimatorStateInfo(0).IsName("Attacking"))//animación de ataque
        {
            animator.SetTrigger("attack");
        }
    }
    public void DoAttackDash()
    {
        StartCoroutine(AttackDash());
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
            animator.ResetTrigger("attack");
            isAttacking = false;
            swordCollider.enabled = false;
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
            Debug.Log("Daleeee");
            timer += Time.deltaTime;
            yield return null;
        }

        isDashing = false;
    }
    private void OnTriggerEnter(Collider other)
    {
        if (other.CompareTag("EnemySword") && !hasRecievedDamage)
        {
            Debug.Log("daño");
            playerRenderer.material = newMaterial;
            hasRecievedDamage = true;
            playerLifeManager.actualHealth -= enemyDamage;
            PlayerHealthBar.UpdatePlayerHealthBar(playerLifeManager.actualHealth, playerLifeManager.maxHealth);
            Invoke("RestartInvincibility", invincibilityDuration);
        }
    }
}
