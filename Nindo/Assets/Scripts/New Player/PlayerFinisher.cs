using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.VFX;
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
    public Transform KaitoTr;

    public VisualEffect hit;
    public VisualEffect slash;


    public VisualEffect vfx1;

    // Start is called before the first frame update
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        if(enemyBeingDamaged.isFinishable && Input.GetKeyDown(KeyCode.F) && !slowMotionActive) 
        {
            
            animator.SetTrigger("Finish");
        }
//        if (animator.GetCurrentAnimatorStateInfo(0).IsName("Finishing") && !slowMotionActive)
//        {
//           ActivateSlowMotion();
//        }
        if (Input.GetKeyDown(KeyCode.P))
        {
            SpawnDashVFX();
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

        hit.Play();
        slash.Play();
    Time.timeScale = 1f;
        Time.fixedDeltaTime = 0.02f;
        slowMotionActive = false;
        enemyBeingDamaged.Death();
        

    }

    private IEnumerator DashCoroutine(Transform enemy)
    {
        BoxCollider playerCollider = GetComponent<BoxCollider>();
        if (playerCollider != null) playerCollider.enabled = false;
        isDashing = true;

        Vector3 startPos = transform.position;

        // Dirección hacia atrás del enemigo
        Vector3 direction = (enemy.position - transform.position).normalized;

        // Posición objetivo justo detrás del enemigo
        Vector3 targetPos = enemy.position + direction * dashDistanceBehindEnemy;
        targetPos.y = startPos.y;
        float elapsed = 0f;
        while (elapsed < dashDuration)
        {
            transform.position = Vector3.Lerp(startPos, targetPos, elapsed / dashDuration);
            elapsed += Time.deltaTime / Time.timeScale;
            yield return null;
        }

        transform.position = targetPos;
        isDashing = false;
        if (playerCollider != null) playerCollider.enabled = true;
    }
    public void SpawnDashVFX()
    {
       // Instanciar con la rotación del jugador + un offset fijo
    Quaternion rotationOffset = Quaternion.Euler(0f, -180f, 0f); // ejemplo: rotar 90° en Y
    VisualEffect vfxInstance = Instantiate(vfx1, KaitoTr.position, KaitoTr.rotation * rotationOffset);

    // Offset local (atrás del jugador)
    Vector3 localOffset = new Vector3(-5.6400f, 0.6799f, -1.388f);
    vfxInstance.transform.position += KaitoTr.TransformDirection(localOffset);

    // Reproducir el efecto
    vfxInstance.Play();
    Destroy(vfxInstance.gameObject, 2f);
    }

}
