using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerEventReciever : MonoBehaviour
{
    public PlayerCombat playerCombat;

    //HACER QUE CAMBIE EL TAG
    public void StartAttacking()
    {
        playerCombat.StartAttacking();
        gameObject.tag = "PlayerSword";
    }
    public void StopAttacking()
    {
        playerCombat.StopAttacking();
        gameObject.tag = "IdlePlayerSword";
    }
    public void StartParry()
    {
        playerCombat.StartParry();
    }
    public void EndParry()
    {
        playerCombat.EndParry();
    }

}
