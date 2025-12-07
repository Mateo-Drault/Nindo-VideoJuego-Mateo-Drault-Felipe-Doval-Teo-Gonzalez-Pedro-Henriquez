using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public enum SoundType
{
    ATTACK,
    PARRY,
    HURT,
    FOOTSTEPS,
    BACKGROUND,
    FINISHER,
    DASH,
    MENU
}

[RequireComponent(typeof(AudioSource))] //Siempre tiene que tener un audio

public class SoundManager : MonoBehaviour
{
    [SerializeField] private AudioClip[] soundList;
    [SerializeField, Range(0, 1f)] public float musicVolume = 0.2f;
    [SerializeField, Range(0, 1f)] public float globalVolume = 1.0f;
    [SerializeField, Range(0, 1f)] public float sfxVolume = 1.0f;
    [SerializeField] bool isInMenu;
    [SerializeField] bool isInGameplay;
    private static SoundManager instance; // Singleton instance
    private AudioSource sfxSource;
    private AudioSource musicSource;
    [SerializeField] private Slider globalSlider;
    [SerializeField] private Slider musicSlider;
    [SerializeField] private Slider sfxSlider;

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
        PlayMusic();
        musicSlider.onValueChanged.AddListener(MusicVolumeSettings);
        globalSlider.onValueChanged.AddListener(GlobalVolumeSettings);
        sfxSlider.onValueChanged.AddListener(SfxVolumeSettings);
    }

    private void Update()
    {
        musicSource.volume = musicVolume * globalVolume; //Para que sea configurable en realtime
    }
    private void PlayMusic()
    {
        musicSource.loop = true;
        musicSource.volume = musicVolume * globalVolume;
        if (isInMenu) //Si estoy en el menu, que ponga la musica del menu
        {
            musicSource.clip = soundList[(int)SoundType.MENU];
        }
        else if (isInGameplay) //Si estoy en el gameplay, que ponga la musica del gameplay
        {
            musicSource.clip = soundList[(int)SoundType.BACKGROUND];
        }
        musicSource.Play();
    }

    public static float GlobalVolume => instance.globalVolume; //La hago static para poder usarla en PlaySound
    public static float SfxVolume => instance.sfxVolume; //La hago static para poder usarla en PlaySound

    public static void PlaySound(SoundType sound, float volume = 1)
    {
        instance.sfxSource.PlayOneShot(instance.soundList[(int)sound], volume * GlobalVolume * SfxVolume); // Reproduce el sonido que le pasas que corresponda al enum y setea el volumen de ese audio
                                                                                                           // Bug con MusicSound influenciando al sfxVolume. No se que onda. Por ver.
    }

    public void MusicVolumeSettings(float volume)
    {
        musicVolume = volume;
    }
    public void GlobalVolumeSettings(float volume)
    {
        globalVolume = volume;
    }
    public void SfxVolumeSettings(float volume)
    {
        sfxVolume = volume;
    }

}
