using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerEventReciever : MonoBehaviour
{
    public PlayerCombat playerCombat;

    public void StartAttacking()
    {
        playerCombat.StartAttacking();
    }
    public void StopAttacking()
    {
        playerCombat.StopAttacking();
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
