using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

public class EnemyCombat : MonoBehaviour
{
    [Header("Referencias")]
    [SerializeField] private PlayerCombat playerCombat;
    [SerializeField] private Animator animator;
    [SerializeField] private NavMeshAgent agent;
    [SerializeField] private EnemyMovement enemyMovement;
    [SerializeField] private EnemyBeingDamaged enemyBeingDamaged;


    [Header("Rango de ataque")]
    [SerializeField] private float attackRange = 2f;   // Distancia máxima para golpear
    [SerializeField] private float attackAngle = 45f;  // Ángulo frontal de golpe
    public bool hasDealtDamage = false;

    [Header("Postura")]
    [SerializeField] private float posturaInicial = 5f;
    private float posturaActual;
    [SerializeField] private PosturaScript posturaScript; // Para UI de barra de postura

    [Header("Estados")]
    public bool isAttacking = false;

    public ParticleSystem chispas;
    [SerializeField] float chispasDuration;

    void Start()
    {
        chispas.Clear();
        posturaActual = posturaInicial;

    }

    // Update is called once per frame
    void Update()
    {
        if (!isAttacking && enemyMovement.canAttack)
        {
            StartCoroutine(AttackComboCoroutine());
        }
    }
    IEnumerator RotateTowardsPlayerBeforeAttack()
    {
        if (playerCombat == null) yield break;

        Vector3 dir = (playerCombat.transform.position - transform.position);
        dir.y = 0;
        if (dir.sqrMagnitude < 0.001f) yield break;

        Quaternion targetRotation = Quaternion.LookRotation(dir.normalized);

        // gira hasta que esté alineado
        while (Quaternion.Angle(transform.rotation, targetRotation) > 3f)
        {
            transform.rotation = Quaternion.Slerp(transform.rotation, targetRotation, 6f * Time.deltaTime);
            yield return null;
        }
    }
    IEnumerator AttackComboCoroutine()
    {
        isAttacking = true;

        for (int i = 1; i <= 3; i++) // combo de 3 ataques
        {
            yield return RotateTowardsPlayerBeforeAttack();

            // 🔹 Lanzar animación
            animator.SetTrigger("Attack" + i);

            // 🔹 Resetear flag de daño (solo puede golpear una vez por anim)
            hasDealtDamage = false;

            // 🔹 Esperar fin de animación de ataque (ajustá según duración real)
            yield return new WaitForSeconds(1f);

            // 🔹 Si el jugador se aleja demasiado, cortamos el combo
            float dist = Vector3.Distance(transform.position, playerCombat.transform.position);
            if (dist > attackRange * 1.5f)
            {
                Debug.Log("Jugador se alejó, cortando combo");
                break;
            }
        }

        isAttacking = false;
    }
    public void TryDealDamageToPlayer()
    {
        if (hasDealtDamage) return; // evita repetir el danio
        if (playerCombat == null) return;

        float dist = Vector3.Distance(playerCombat.transform.position, transform.position);
        Vector3 toPlayer = (playerCombat.transform.position - transform.position).normalized;
        float angle = Vector3.Angle(transform.forward, toPlayer);

        Debug.Log($"Distancia: {dist}, Ángulo: {angle}");

        if (dist <= attackRange && angle <= attackAngle)
        {
            Debug.Log("💥 Golpe válido, llamando a OnHitByEnemy()");
            hasDealtDamage = true; // pego
            playerCombat.OnHitByEnemy();
        }
    }
    public void InterruptAttack() //Lo llama la jugador al hacer parry
    {
        if (isAttacking)
        {
            isAttacking = false;

            // Resetea triggers de animación de ataques
            animator.ResetTrigger("Attack1");
            animator.ResetTrigger("Attack2");
            animator.ResetTrigger("Attack3");

            posturaActual -= 1f;
            posturaScript?.UpdatePosturaBar(posturaInicial, posturaActual);

            if (posturaActual <= 0f)
            {
                StunEnemy();
            }

            Debug.Log("Ataque interrumpido por parry!");
        }
    }
    void StunEnemy()
    {
        animator.SetTrigger("stunned");
        Debug.Log("Enemigo aturdido!");
        posturaActual = posturaInicial;
        posturaScript?.UpdatePosturaBar(posturaInicial, posturaActual);
    }

    public void EndChispas()
    {
        chispas.Stop();
    }
}
