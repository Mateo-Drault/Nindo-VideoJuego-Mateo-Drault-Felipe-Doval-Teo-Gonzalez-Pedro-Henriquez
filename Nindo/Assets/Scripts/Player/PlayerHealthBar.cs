using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
public class PlayerHealthBar : MonoBehaviour
{
    [SerializeField] private Image redBar;
    // Start is called before the first frame update
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        
    }

    public void UpdatePlayerHealthBar(float health, float maxHeatlh)
    {
        redBar.fillAmount = health / maxHeatlh;
    }
}
