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
    FINISHER,
    DASH
}

[RequireComponent(typeof(AudioSource))] //Siempre tiene que tener un audio

public class SoundManager : MonoBehaviour
{
    [SerializeField] private AudioClip[] soundList;
    [SerializeField, Range(0, 1f)] private float musicVolume = 0.2f;
    [SerializeField, Range(0, 1f)] private float globalVolume = 1.0f;
    private static SoundManager instance; // Singleton instance
    private AudioSource sfxSource;
    private AudioSource musicSource;

    private void Awake()
    {
        if (instance == null)
        {
            instance = this;
        }
        else if (instance != this)
        {
            Destroy(instance);
        }
        ;
    }

    private void Start()
    {
        sfxSource = GetComponent<AudioSource>();
        musicSource = GetComponent<AudioSource>();
        musicSource.loop = true;
        PlayMusic();
    }

    private void Update()
    {
       
    }

    public static float GlobalVolume => instance.globalVolume; //La hago static para poder usarla en PlaySound

    public static void PlaySound(SoundType sound, float volume = 1)
    {
        instance.sfxSource.PlayOneShot(instance.soundList[(int)sound], volume * GlobalVolume); // Reproduce el sonido que le pasas que corresponda al enum y setea el volumen de ese audio 
    }

    private void PlayMusic()
    {
        musicSource.clip = soundList[(int)SoundType.MUSIC];
        musicSource.volume = musicVolume * globalVolume;
        musicSource.Play();
    }
}
