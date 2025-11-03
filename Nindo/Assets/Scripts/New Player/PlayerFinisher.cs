using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerFinisher : MonoBehaviour
{
    [SerializeField] private EnemyBeingDamaged enemyBeingDamaged;
    public float slowMotionScale = 0.3f; // Escala de tiempo para remate
    public float slowMotionDuration = 0.5f;
    private bool slowMotionActive = false;
    [SerializeField] Transform enemy; // despues lo cambio al enemigo fijado
    [SerializeField] Animator animator;
    private float targetAlpha = 0f;

    public float dashDistanceBehindEnemy = 2f; // distancia atrás del enemigo
    public float dashDuration = 0.05f; // duración muy corta para que sea casi instantáneo
    private bool isDashing = false;

    // Start is called before the first frame update
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        if(enemyBeingDamaged.isFinishable && Input.GetKeyDown(KeyCode.F) && !slowMotionActive) 
        {
            
            ActivateSlowMotion();
            animator.SetTrigger("Finish");
        }
    }
    public void ActivateSlowMotion()
    {
        Time.timeScale = slowMotionScale;
        Time.fixedDeltaTime = 0.02f * Time.timeScale;
        slowMotionActive = true;
    }
    public void DeactivateSlowMotion() //desde el animator
    {
        if (!isDashing)
            StartCoroutine(DashCoroutine(enemy));

    Time.timeScale = 1f;
        Time.fixedDeltaTime = 0.02f;
        slowMotionActive = false;
        enemyBeingDamaged.Death();
        

    }

    private IEnumerator DashCoroutine(Transform enemy)
    {
        isDashing = true;

        Vector3 startPos = transform.position;

        // Dirección hacia atrás del enemigo
        Vector3 direction = (transform.position - enemy.position).normalized;

        // Posición objetivo justo detrás del enemigo
        Vector3 targetPos = enemy.position + direction * dashDistanceBehindEnemy;

        float elapsed = 0f;
        while (elapsed < dashDuration)
        {
            transform.position = Vector3.Lerp(startPos, targetPos, elapsed / dashDuration);
            elapsed += Time.deltaTime / Time.timeScale; // importante si hay slow motion
            yield return null;
        }

        transform.position = targetPos;
        isDashing = false;
    }
}
