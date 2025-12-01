using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public enum SoundType
{
    ATTACK,
    PARRY,
    HURT,
    FOOTSTEPS,
    MUSIC,
    FINISHER
}

[RequireComponent(typeof(AudioSource))] //Siempre tiene que tener un audio

public class SoundManager : MonoBehaviour
{
    [SerializeField] private AudioClip[] soundList;
    private static SoundManager instance; // Singleton instance
    private AudioSource audioSource;

    private void Awake()
    {
        instance = this;
    }

    private void Start()
    {
        audioSource = GetComponent<AudioSource>();
    }

    public static void PlaySound(SoundType sound, float volume = 1)
    {
        instance.audioSource.PlayOneShot(instance.soundList[(int)sound], volume); // Reproduce el sonido que le pasas que corresponda al enum y setea el volumen de ese audio
    }
}
