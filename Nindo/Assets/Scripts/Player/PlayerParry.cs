using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerParry : MonoBehaviour
{
    public enum ParryMode { Idle, Parry }
    public ParryMode currentMode = ParryMode.Idle;

    [SerializeField] Animator anim;
    [SerializeField] BoxCollider parryCollider;
    [SerializeField] EnemySwordAnimation enemySwordAnimation;
    [SerializeField] private ParticleSystem chispas;
    [SerializeField] private float chispasDuration = 0.05f;
    [SerializeField] private BoxCollider playerBodyCollider;
    [SerializeField] EnemySwordAnimation swordAnim;

    [SerializeField] private PlayerBeingDamaged playerBeingDamaged;
    [SerializeField] private float inmunityTime;
    public bool hasParried;
    public bool isParrying;

    // Start is called before the first frame update
    void Start()
    {
        anim.ResetTrigger("triggerParry");
        chispas.Stop();

        isParrying = false;
        parryCollider.enabled = false;
    }

    // Update is called once per frame
    void Update()
    {
        if (Input.GetKeyDown(KeyCode.LeftShift))
        {
            StartParry();
        }

        AnimatorStateInfo animatorStateInfo = anim.GetCurrentAnimatorStateInfo(0);
        if (animatorStateInfo.IsName("Parry"))
        {
            Debug.Log("parr");

            currentMode = ParryMode.Parry;

        }
        else
        {
            currentMode = ParryMode.Idle;
        }
    }

    private void OnTriggerEnter(Collider other)
    {
        if (currentMode == ParryMode.Parry && other.CompareTag("EnemySword") && !playerBeingDamaged.hasRecivedDamage)
        {
            Debug.Log("parry");
            hasParried = true;
            Invoke("EndInmunity", inmunityTime);
            chispas.Play();
            Invoke("EndChispas", chispasDuration);
            enemySwordAnimation.InterruptAttack();
        }
    }

    public void StartParry()
    {
        Physics.IgnoreCollision(enemySwordAnimation.swordCollider, playerBodyCollider, true);

        gameObject.tag = "Parry";
        anim.SetTrigger("triggerParry");
        isParrying = true;
        parryCollider.enabled = true;
    }
    public void EndParry()
    {
        Physics.IgnoreCollision(enemySwordAnimation.swordCollider, playerBodyCollider, false);
        gameObject.tag = "Player";
        isParrying = false;
        parryCollider.enabled = false;
        anim.ResetTrigger("triggerParry");
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
