using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor.Tilemaps;

[CreateAssetMenu(fileName = "MyPrefabBrush", menuName = "Brushes/MyPrefabBrush")]
[CustomGridBrush(hideAssetInstances: false, hideDefaultInstance: true, defaultBrush: false, defaultName: "PrefabBrush")]

public class PrefabBrush : GameObjectBrush
{

    // Start is called before the first frame update
    void Start()
    {
        
    }

    // Update is called once per frame
    void Update()
    {
        
    }
}
