using System.Collections;
using System.Collections.Generic;
using System.Linq;
using UnityEngine;

public class LockOnTarget : MonoBehaviour
{
    //Mover camara en un punto medio
    [SerializeField] private Camera mainCamera;
    [SerializeField] private float normalFOV;
    [SerializeField] private float adjustedFOV;
    [SerializeField] private float lerpSpeed;

    //Rotar al objetivo
    public float lockRange = 10f;
    [SerializeField] private Transform target;
    [SerializeField] private LayerMask enemyLayer;
    public bool isLocked;
    // Start is called before the first frame update
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        if (Input.GetKeyDown(KeyCode.Q))
        {
            if (target == null)
            {
                isLocked = true;
                LockOnClosestEnemies();
            }
            else
            {
                isLocked = false ;
                target = null;
            }
        }

        if (target != null)
        {
            if (target.Equals(null))
            {
                target = null;
                return;
            }
            LookAt();
            AdjustCamera();
        }
        else
        {
            StopAdjustment();
        }
    }
    void LockOnClosestEnemies()
    {
        Collider[] enemies = Physics.OverlapSphere(transform.position,lockRange, enemyLayer);

        if (enemies.Length > 0)
        {
            var closest = enemies.OrderBy(e => Vector3.Distance(transform.position, e.transform.position)).FirstOrDefault();
            target = closest.transform;
        }
    }
    void LookAt()
    {
        Vector3 direction = target.position - transform.position;
        direction.y = 0;
        Quaternion TargetRotation = Quaternion.LookRotation(direction);
        transform.rotation = Quaternion.Slerp(transform.rotation, TargetRotation, 10f * Time.deltaTime);
    }
    void AdjustCamera()
    {
        mainCamera.orthographicSize = Mathf.Lerp(mainCamera.orthographicSize, adjustedFOV, Time.deltaTime * lerpSpeed);
    }
    void StopAdjustment()
    {
        mainCamera.orthographicSize = Mathf.Lerp(mainCamera.orthographicSize, normalFOV, Time.deltaTime *lerpSpeed);
    }
}

