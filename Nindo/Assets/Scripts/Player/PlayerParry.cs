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

    public bool isParrying;

    // Start is called before the first frame update
    void Start()
    {
        anim.ResetTrigger("triggerParry");

        isParrying = false;
        parryCollider.enabled = false;
    }

    // Update is called once per frame
    void Update()
    {
        if (Input.GetKeyDown(KeyCode.O))
        {
            StartParry();
        }

        AnimatorStateInfo animatorStateInfo = anim.GetCurrentAnimatorStateInfo(0);
        if (animatorStateInfo.IsName("Parry"))
        {
            currentMode = ParryMode.Parry;
        }
        else
        {
            currentMode = ParryMode.Idle;
        }
    }

    private void OnTriggerEnter(Collider other)
    {
        if(currentMode == ParryMode.Parry && other.CompareTag("EnemySword"))
        {
            enemySwordAnimation.InterruptAttack();
            Debug.Log("Parreado paaaa");
        }
    }

    public void StartParry()
    {
        gameObject.tag = "Parry";
        anim.SetTrigger("triggerParry");
        isParrying = true;
        parryCollider.enabled = true;
    }
    public void EndParry()
    {
        gameObject.tag = "Player";
        isParrying = false;
        parryCollider.enabled = false;
        anim.ResetTrigger("triggerParry");
    }
}
