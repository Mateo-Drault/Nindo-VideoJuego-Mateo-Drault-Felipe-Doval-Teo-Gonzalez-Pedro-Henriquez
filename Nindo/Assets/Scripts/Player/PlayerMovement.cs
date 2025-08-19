using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PlayerMovement : MonoBehaviour
{
    [SerializeField] private float speed = 3f;
    [SerializeField] private float rotationSpeed = 1.0f;
    [SerializeField] private float maxRiseSpeed = 1;
    [SerializeField] private float maxFallSpeed = 20;
    [SerializeField] private Rigidbody playerRB;
    [SerializeField] private Animator anim;
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
        if (direction != Vector3.zero && !anim.GetCurrentAnimatorStateInfo(0).IsName("Stunned"))
        {
            transform.position += direction * speed * Time.deltaTime;
            Quaternion Target = Quaternion.LookRotation(direction);
            transform.rotation = Quaternion.Slerp(transform.rotation, Target, rotationSpeed * Time.deltaTime);
        }
    }
    void FixedUpdate()
    {
        Vector3 vel = playerRB.velocity;
        vel.y = Mathf.Clamp(vel.y, -maxFallSpeed, maxRiseSpeed);
        playerRB.velocity = vel;
    }
}
