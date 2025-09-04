using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EventReciever : MonoBehaviour
{
    public EnemyCombat enemyCombat;
    // Start is called before the first frame update
    void Start()
    {

    }

    // Update is called once per frame
    void Update()
    {
    }

    public void StartAttack()
    {
        enemyCombat.StartAttack();
    }
    public void StopAttack()
    {
        enemyCombat.StopAttack();
    }
    public void StartParry() //llamado desde la animacion (en el EventReciever)
    {
        enemyCombat.StartParry();
    }
    public void EndParry() //llamado desde la animacion (en el EventReciever)
    {
        enemyCombat.EndParry();
    }
}
