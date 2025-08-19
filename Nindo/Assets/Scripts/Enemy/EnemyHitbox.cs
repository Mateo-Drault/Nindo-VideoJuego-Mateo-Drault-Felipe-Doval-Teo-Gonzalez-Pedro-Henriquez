using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EnemyHitbox : MonoBehaviour
{

    public enum HitboxMode { Idle, Attack, Parry }
    public HitboxMode currentMode = HitboxMode.Idle;
    [SerializeField] Animator anim;
    [SerializeField] PlayerSwordAnimation PlayerSwordAnimation;
    [SerializeField] BoxCollider swordCollider;
    public bool isParying;



    // Start is called before the first frame update
    void Start()
    {
        isParying = false;
    }

    // Update is called once per frame
    void Update()
    {
        AnimatorStateInfo animatorStateInfo = anim.GetCurrentAnimatorStateInfo(0);
        if (animatorStateInfo.IsName("EnemyParry"))
        {
            currentMode = HitboxMode.Parry;

        }
        else if (animatorStateInfo.IsName("EnemyAttack"))
        {
            currentMode = HitboxMode.Attack;
        }
        else
        {
            currentMode = HitboxMode.Idle;
        }
    }
    private void OnTriggerEnter(Collider other)
    {
        if(currentMode==HitboxMode.Parry & other.CompareTag("Player"))
        {
            PlayerSwordAnimation.InterrumptAttack();
        }
    }
    public void StartParry()
    {
        isParying = true;
        swordCollider.enabled = true;
    }
    public void EndParry()
    {
        isParying = false;
        swordCollider.enabled = false;
    }
}
