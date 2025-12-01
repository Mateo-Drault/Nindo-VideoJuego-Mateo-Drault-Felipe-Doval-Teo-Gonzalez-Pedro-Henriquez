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
    private bool musicPlaying = false;

    private void Awake()
    {
        instance = this;
    }

    private void Start()
    {
        audioSource = GetComponent<AudioSource>();
    }

    private void Update()
    {
        StartCoroutine(Music());
    }

    public static void PlaySound(SoundType sound, float volume = 1)
    {
        instance.audioSource.PlayOneShot(instance.soundList[(int)sound], volume); // Reproduce el sonido que le pasas que corresponda al enum y setea el volumen de ese audio
    }

    IEnumerator Music()
    {
        if (musicPlaying) yield break;
        musicPlaying = true;
        PlaySound(SoundType.MUSIC, 0.1f);
        yield return new WaitForSeconds(246);
        musicPlaying = false;
    }
}
