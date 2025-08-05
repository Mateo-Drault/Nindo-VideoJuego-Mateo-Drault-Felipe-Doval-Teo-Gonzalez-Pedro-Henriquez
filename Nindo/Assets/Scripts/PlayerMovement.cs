using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerMovement : MonoBehaviour
{
    [SerializeField] private float speed = 3f;
    [SerializeField] private float rotationSpeed = 1.0f;
    private Rigidbody playerRB;
    private Vector3 forward, right;
    void Start()
    {
        forward = Camera.main.transform.forward;
        forward.y = 0;
        forward = Vector3.Normalize(forward);

        right = Camera.main.transform.right;
        right.y = 0;
        right = Vector3.Normalize(right);

    }

    // Update is called once per frame
    void Update()
    {
        float horizontalInput = Input.GetAxis("Horizontal");
        float verticalInput = Input.GetAxis("Vertical");
        Vector3 direction = horizontalInput * right + verticalInput * forward;
        if (direction != Vector3.zero)
        {
            transform.position += direction * speed * Time.deltaTime;
            Quaternion Target = Quaternion.LookRotation(direction);
            transform.rotation = Quaternion.Slerp(transform.rotation, Target, rotationSpeed * Time.deltaTime);
        }
    }
    private void FixedUpdate()
    {

    }
}
