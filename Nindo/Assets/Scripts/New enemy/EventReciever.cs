using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EventReciever : MonoBehaviour
{
    public EnemyCombat enemyCombat;
    [SerializeField] public Animator animator; // el Animator del Body

    public void StartAttack() => enemyCombat.StartAttack();
    public void StopAttack() => enemyCombat.StopAttack();
    public void StartParry() => enemyCombat.StartParry();
    public void EndParry() => enemyCombat.EndParry();


    // 🔹 Llamadas desde EnemyCombat hacia el EventReciever (nuevo)
    public void TriggerAttack(string animName)
    {
        animator.SetTrigger(animName);
    }
    public void ResetAttack(string animName)
    {
        animator.ResetTrigger(animName);
    }

    public void TriggerParry()
    {
        animator.SetTrigger("Parry");
    }
    public bool IsPlayingAttack()
    {
        AnimatorStateInfo state = animator.GetCurrentAnimatorStateInfo(0);

        // Devuelve true si la animación del layer 0 todavía no terminó
        return state.normalizedTime < 1f && state.tagHash == Animator.StringToHash("Attack");
    }
    public void StopAttackAnimation() // llamado desde Animation Event
    {
        enemyCombat.isAttackingAnimation = false;
    }
}
