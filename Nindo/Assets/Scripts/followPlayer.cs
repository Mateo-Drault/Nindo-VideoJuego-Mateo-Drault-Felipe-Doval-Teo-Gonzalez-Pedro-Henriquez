using System.Collections;
using System.Collections.Generic;
using Unity.VisualScripting;
using UnityEngine;

public class followPlayer : MonoBehaviour
{
    [SerializeField] private float rotationSpeed;
    [SerializeField] private float speed;
    [SerializeField] private float minDistance;
    public float maxDistance;
    [SerializeField] Transform playerTransform;
    [SerializeField] private BeingDamaged BeingDamaged;
    [SerializeField] private bool Seen= false;


    // Start is called before the first frame update
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        Vector3 directionToPlayer = playerTransform.position - transform.position;
        if (!Seen && Vector3.Distance(transform.position, playerTransform.position) < maxDistance)
        {
            Seen = true;
        }
        if (Vector3.Distance(transform.position, playerTransform.position) > minDistance & !BeingDamaged.isBeingDamaged & Seen)
        {
            transform.position = Vector3.MoveTowards(transform.position, playerTransform.position, speed* Time.deltaTime);

            if (transform.position != Vector3.zero)
            {
                Quaternion Target = Quaternion.LookRotation(directionToPlayer);
                transform.rotation = Quaternion.Slerp(transform.rotation, Target, rotationSpeed * Time.deltaTime);
            }
        }

    }
}
