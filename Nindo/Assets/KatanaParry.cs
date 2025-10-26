using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class KatanaParry : MonoBehaviour
{
    public bool katanaIsColliding { get; private set; }
    private void OnTriggerEnter(Collider other)
    {
        // Detecta si tocó la espada del enemigo o el parry
        if (other.CompareTag("EnemySword") || other.CompareTag("Parry"))
        {
            katanaIsColliding = true;
            Debug.Log("Katana comenzó a colisionar con: " + other.name);
        }
    }

    private void OnTriggerExit(Collider other)
    {
        // Cuando deja de tocarla, se apaga
        if (other.CompareTag("EnemySword") || other.CompareTag("Parry"))
        {
            katanaIsColliding = false;
            Debug.Log("Katana dejó de colisionar con: " + other.name);
        }
    }
}
