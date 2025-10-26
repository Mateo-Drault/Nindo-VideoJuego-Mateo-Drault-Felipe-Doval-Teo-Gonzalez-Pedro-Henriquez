using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

public class EnemyCombat : MonoBehaviour
{
    //scripts y objetos seteados por el inspector
    [SerializeField] private EnemyMovement enemyMovement;
    [SerializeField] private EnemyBeingDamaged enemyBeingDamaged;
    [SerializeField] private PlayerCombat playerCombat;
    [SerializeField] private CapsuleCollider parryCollider;
    [SerializeField] private MeshCollider swordCollider;
    [SerializeField] private Animator animator;
    [SerializeField] public Transform player;
    [SerializeField] private EventReciever eventReciever;
    [SerializeField] private NavMeshAgent agent;
    public bool isAttackingAnimation = false;
    

    //Parry
    [SerializeField] private float maxHitsBeforeParry;
    [SerializeField] private float actualHitsBeforeParry;
    [SerializeField] private float posturaInicial;
    [SerializeField] private float posturaActual;
    [SerializeField] private PosturaScript posturaScript;

    public enum HitboxMode { Idle, Attack, Parry }
    public HitboxMode currentMode = HitboxMode.Idle;
    [SerializeField] public bool isParrying;
    [SerializeField] private GameObject Katana;

    public ParticleSystem chispas;
    [SerializeField] float chispasDuration;

    void Start()
    {
        chispas.Clear();
        posturaActual = posturaInicial;
        actualHitsBeforeParry = maxHitsBeforeParry;
        swordCollider.enabled = false;
        currentMode = HitboxMode.Idle;
    }

    // Update is called once per frame
    void Update()
    {
        if (enemyBeingDamaged.parryHit) //menos golpes para hacer parry
        {
            HitsToParry();
        }
        if (actualHitsBeforeParry <= 0) //si llega a 0, hacer parry
        {
            TriggerParry();
        }
        else
        {
            animator.ResetTrigger("Parry");
        }
        AnimatorStateInfo animatorStateInfo = animator.GetCurrentAnimatorStateInfo(0);
        if (animatorStateInfo.IsName("Parrying")) //saber si esta parreando
        {
            currentMode = HitboxMode.Parry;

        }
        else
        {
            isParrying = false;
            gameObject.tag = "EnemySword";
            currentMode = HitboxMode.Idle;
        }
    }
    public void Attac()
    {
        if (!enemyMovement.isAttacking)
            StartCoroutine(AttackCombo());
    }

    private IEnumerator AttackCombo()
    {
        enemyMovement.isAttacking = true;

        for (int i = 1; i <= 3; i++)
        {
            // Girar hacia el jugador antes de atacar
            yield return RotateTowardsPlayer();

            //  Activar animación de golpe
            string animName = "Attack" + i;

            eventReciever.TriggerAttack(animName);

            //  Esperar a que termine la animación del ataque actual
            yield return WaitForAnimation(animName);
            isAttackingAnimation = true;

            eventReciever.ResetAttack(animName);

            //  Después de terminar el ataque, recién ahí chequea si sigue en rango
            float dist = Vector3.Distance(transform.position, player.position);
            Vector3 toPlayer = (player.position - transform.position).normalized;
            float angle = Vector3.Angle(transform.forward, toPlayer);

            if (dist > enemyMovement.attackRange)
                break;
            else if (angle > 8f)
                yield return RotateTowardsPlayer();
        }


    }

    private IEnumerator RotateTowardsPlayer()
    {
        Vector3 dir = (player.position - transform.position);
        dir.y = 0;
        if (dir.sqrMagnitude < 0.001f) yield break;

        Quaternion targetRotation = Quaternion.LookRotation(dir.normalized);

        // Activar animación intermedia solo si hace falta
        float angle = Quaternion.Angle(transform.rotation, targetRotation);
        if (angle > 8f)
        {
            animator.SetTrigger("Turning"); // trigger de giro
        }

        // Girar hasta quedar orientado
        while (Quaternion.Angle(transform.rotation, targetRotation) > 3f)
        {
            // Chequeo de distancia mientras gira
            float dist = Vector3.Distance(transform.position, player.position);
            if (dist > enemyMovement.attackRange)
            {
                // Interrumpe giro si el jugador se aleja
                animator.ResetTrigger("Turning");
                yield break;
            }

            transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, 6f * Time.deltaTime);
            yield return null;
        }

        // Giro terminado
        animator.ResetTrigger("Turning");
    }

    private IEnumerator WaitForAnimation(string animName)
    {
        // Espera a que la animación que disparaste realmente comience
        AnimatorStateInfo state = eventReciever.animator.GetCurrentAnimatorStateInfo(0);
        while (!state.IsName(animName))
        {
            yield return null;
            state = eventReciever.animator.GetCurrentAnimatorStateInfo(0);
        }

        // Ahora la animación empezó, esperamos a que termine
        while (state.normalizedTime < 1f)
        {
            yield return null;
            state = eventReciever.animator.GetCurrentAnimatorStateInfo(0);
        }
    }









public void StartAttack() //llamado desde la animacion (en el EventReciever)
    {
        agent.updateRotation = false;
        swordCollider.enabled = true;
    }
    public void StopAttack() //llamado desde la animacion (en el EventReciever)
    {
        agent.updateRotation = true;
        swordCollider.enabled = false;
        animator.ResetTrigger("Attack1");
        enemyMovement.isAttacking = false;
    }

    public void MidAttack()
    {
        swordCollider.enabled = false;
        animator.SetTrigger("Turning");
    }

    void TriggerParry()
    {
        animator.SetBool("isStunned", false);
        animator.SetTrigger("Parry");
        actualHitsBeforeParry = maxHitsBeforeParry;
        currentMode = HitboxMode.Parry;
    }
    void HitsToParry()
    {
        actualHitsBeforeParry -= 1;
        enemyBeingDamaged.parryHit = false;
    }
    public void StartParry() //llamado desde la animacion (en el EventReciever)
    {
        gameObject.tag = "Parry";
        isParrying = true;
        parryCollider.enabled = true;
    }
    public void EndParry() //llamado desde la animacion (en el EventReciever)
    {
        gameObject.tag = "Enemy";
        isParrying = false;
        parryCollider.enabled = false;
        animator.ResetTrigger("Parry");
    }

    private void OnTriggerEnter(Collider other)
    {
        if (currentMode == HitboxMode.Parry & other.CompareTag("PlayerSwordAttacking")) //si el arma del jugador impacta con la espada al hacer parry:
        {
            playerCombat.InterrumptAttack();
            chispas.Play();
            Invoke("EndChispas", chispasDuration);
            animator.SetTrigger("HasParry"); //hacer el parry por el golpe
            animator.SetBool("isStunned", false);
        }
    }

    public void InterruptAttack() //Lo llama la jugador al hacer parry
    {
        if (enemyMovement.isAttacking && !playerCombat.hasParried)
        {
            playerCombat.hasParried = true;
            if (posturaActual > 0)
            {
                swordCollider.enabled = false;
                posturaActual -= 1;
                posturaScript.UpdatePosturaBar(posturaInicial, posturaActual);
            }
            if (posturaActual <= 0)
            {
                animator.SetBool("isStunned", true);
                animator.ResetTrigger("attack");
                enemyMovement.isAttacking = false;
                enemyBeingDamaged.isStunned = true;
                enemyBeingDamaged.stunTimer = enemyBeingDamaged.stunDuration;
                //se resetea solo


            }
           

        }
    }
    public void EndChispas()
    {
        chispas.Stop();
    }
}
