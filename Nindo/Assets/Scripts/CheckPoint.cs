using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class CheckPoint : MonoBehaviour
{
    public Vector3 checkPoint;

    private void OnCollisionEnter(Collision collision)
    {
        if (collision.gameObject.CompareTag("PlayerBody"))
        {
            checkPoint = collision.gameObject.GetComponent<Transform>().position;
            //Debug.Log("Checkpoint guardado");
        }
    }
}
