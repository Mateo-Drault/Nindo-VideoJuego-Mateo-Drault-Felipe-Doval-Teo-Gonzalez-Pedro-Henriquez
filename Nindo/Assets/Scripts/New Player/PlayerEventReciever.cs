using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerEventReciever : MonoBehaviour
{
    public PlayerCombat playerCombat;
    public PlayerFinisher playerFinisher;


    //HACER QUE CAMBIE EL TAG
    public void StartAttacking()
    {
        playerCombat.StartAttacking();
        gameObject.tag = "PlayerSword";
    }
    public void StopAttacking()
    {
        playerCombat.StopAttacking();
    }
    public void EndFinisher()
    {
        playerFinisher.DeactivateSlowMotion();
    }
    public void Fbx1()
    {
        playerFinisher.SpawnDashVFX();
    }
    public void EnableComboWindow()
    {
        playerCombat.EnableComboWindow();
    }
    public void DisableComboWindow()
    {
        playerCombat.DisableComboWindow();
    }
}
