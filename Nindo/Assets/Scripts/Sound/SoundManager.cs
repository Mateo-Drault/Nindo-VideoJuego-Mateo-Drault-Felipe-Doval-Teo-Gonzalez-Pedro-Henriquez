using System.Collections;
using System.Collections.Generic;
using Unity.VisualScripting;
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

public class SoundManager : MonoBehaviour
{
    [SerializeField] private AudioClip[] soundList;
    [SerializeField, Range(0, 1f)] public float musicVolume = 0.2f;
    [SerializeField, Range(0, 1f)] public float masterVolume = 1.0f;
    [SerializeField, Range(0, 1f)] public float sfxVolume = 1.0f;
    [SerializeField] private float fadeDuration = 3f;
    [SerializeField] bool isInMenu;
    [SerializeField] bool isInGameplay;
    private bool isFading = false;
    private static SoundManager instance; // Singleton instance
    private AudioSource sfxSource;
    private AudioSource musicSource;
    [SerializeField] private Slider masterSlider;
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
    }

    private void Start()
    {
        sfxSource = gameObject.AddComponent<AudioSource>();
        musicSource = gameObject.AddComponent<AudioSource>();

        SetMasterVolume(masterVolume);
        SetMusicVolume(musicVolume);
        SetSfxVolume(sfxVolume);

        //Seteo los sliders al valor de los volumenes
        SlidersUpdate();

        PlayMusic();

        musicSlider.onValueChanged.AddListener(MusicVolumeSettings);
        masterSlider.onValueChanged.AddListener(MasterVolumeSettings);
        sfxSlider.onValueChanged.AddListener(SfxVolumeSettings);
    }

    public void SlidersUpdate()
    {
        musicSlider.value = PlayerPrefs.GetFloat("MusicVolume");
        masterSlider.value = PlayerPrefs.GetFloat("MasterVolume");
        sfxSlider.value = PlayerPrefs.GetFloat("SfxVolume");
    }

    private void Update()
    {
        if (!isFading)
            musicSource.volume = musicVolume * masterVolume; //Para que sea configurable en realtime

    }
    private void PlayMusic()
    {
        musicSource.loop = true;
        musicSource.volume = musicVolume * masterVolume;
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

    //static volumes for PlaySound()
    public static float SavedMasterVolume => instance.masterVolume;
    public static float SavedSfxVolume => instance.sfxVolume;


    public static void PlaySound(SoundType sound, float volume = 1)
    {
        instance.sfxSource.PlayOneShot(instance.soundList[(int)sound], volume * SavedMasterVolume * SavedSfxVolume); // Reproduce el sonido que le pasas que corresponda al enum y setea el volumen de ese audio
    }

    public void MusicVolumeSettings(float volume)
    {
        musicVolume = volume;
        SetMusicVolume(musicVolume);
    }
    public void MasterVolumeSettings(float volume)
    {
        masterVolume = volume;
        SetMasterVolume(masterVolume);
    }
    public void SfxVolumeSettings(float volume)
    {
        sfxVolume = volume;
        SetSfxVolume(sfxVolume);

    }

    public void SetMusicVolume(float music_Volume)
    {
        PlayerPrefs.SetFloat("MusicVolume", music_Volume);
    }
    public void SetMasterVolume(float master_Volume)
    {
        PlayerPrefs.SetFloat("MasterVolume", master_Volume);
    }
    public void SetSfxVolume(float sfx_Volume)
    {
        PlayerPrefs.SetFloat("SfxVolume", sfx_Volume);
    }

    public void FadeOut()
    {
        if (!isFading)
            StartCoroutine(FadeOutCoroutine());
    }

    private IEnumerator FadeOutCoroutine()
    {
        isFading = true;

        float startVolume = musicSource.volume;
        float t = 0;

        while (t < fadeDuration)
        {
            t += Time.deltaTime;
            musicSource.volume = Mathf.Lerp(startVolume, 0, t / fadeDuration);
            yield return null;
        }

        musicSource.Stop();
        isFading = false;
    }

}
