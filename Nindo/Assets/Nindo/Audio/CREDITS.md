# Créditos de audio

El audio nuevo de Nindō es CC0 (dominio público), CC BY 4.0 con su crédito (música de jefes y del final,
abajo) o sintetizado por `Tools/Audio/build_audio.py`.

## Música (OpenGameArt, CC0)

| Clave | Tema | Autor | Licencia |
|---|---|---|---|
| `menu` | [oriental-somber](https://opengameart.org/content/oriental-somber) | Tozan | CC0 |
| `explore_home` | [tyhosi-garden-3](https://opengameart.org/content/tyhosi-garden-3) | Tozan | CC0 |
| `explore_forest` | [lapsy-koto](https://opengameart.org/content/lapsy-koto) | Tozan | CC0 |
| `explore_garden` | [asianoriental1](https://opengameart.org/content/asianoriental1) | Tozan | CC0 |
| `explore` | [asianoriental1](https://opengameart.org/content/asianoriental1) | Tozan | CC0 |
| `explore_dojo` | [rpjian](https://opengameart.org/content/rpjian) | Tozan | CC0 |
| `explore_mountain` | [oriental8](https://opengameart.org/content/oriental8) | Tozan | CC0 |
| `explore_lake` | [hot-springs-town](https://opengameart.org/content/hot-springs-town) | Kistol | CC0 |
| `combat` | [looping-japanese-fight-track](https://opengameart.org/content/looping-japanese-fight-track) | Pepsidog | CC0 |
| `boss` | [bosskoto](https://opengameart.org/content/bosskoto) | G_P | CC0 |
| `gameover` | [death-of-a-ninja-game-over](https://opengameart.org/content/death-of-a-ninja-game-over) | Joth | CC0 |

## Música de jefes y del final (por fases, `Tools/Audio/build_boss_music.py`)

| Claves | Tema | Autor | Licencia | Cambios |
|---|---|---|---|---|
| `boss_goro*` | [Boss_Koto](https://opengameart.org/content/bosskoto) | G_P | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | cortado en compases y reordenado: intro, un ciclo de 72 compases con el corte una vez; fase 2 medio tono arriba (re-muestreo 89/84) y +1 dB con su propio ciclo de 68; el golpe final (c51) en los dos tonos como cierre |
| `boss_lake*` | [Amenoshita](https://peritune.com/blog/2015/07/03/amenoshita/) | PeriTune | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | cortado en compases y reordenado por secciones: apertura como intro, un loop por fase (A y A'; desarrollo, cumbre y corte; cumbre y A sin corte), dos compases de entrada por fase y el golpe final como cierre; sonoridad normalizada |
| `boss_bamboo*` | [Wuxia](https://peritune.com/blog/2018/06/24/wuxia/) | PeriTune | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | cortado en compases y reordenado por secciones: crescendo como intro, un loop por fase (tema, A y B; C, D y E; B y D), dos compases de entrada por fase y el primer tiempo del tema con su eco como cierre; sonoridad normalizada |
| `boss_final*` | [Revenge](https://opengameart.org/content/revenge) | TAD | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | cortado en compases y reordenado: intro, un loop por acto (los actos 3 y 4 medio tono arriba), dos compases de entrada por acto y el golpe final (c74) como cierre; estante de +6 dB arriba de 3.5 kHz, ganancia por acto (acto 1 +1.5 dB, acto 3 +0.4 dB), limitador a -1.3 dBFS |
| `ending` | [Sakuya4](https://peritune.com/blog/2018/12/21/sakuya4/) | PeriTune | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | silencios recortados, fundido de 1 s al final, sonoridad normalizada |

El crédito de los temas CC BY 4.0 sale en el cartel del final del juego (UIManager.Panels, BuildEnd): la
licencia pide nombrar autor, licencia y que se modificaron en todo lo que se distribuye, y este archivo no
viaja en la build.

Licencias, como estaban al 12 de octubre de 2026 (páginas leídas ese día; la copia de
https://peritune.com/about/ no va al repositorio porque está en japonés: archivarla en web.archive.org
si hace falta una prueba fechada):

* Wuxia: su página dice que el tema está bajo Creative Commons Attribution 4.0 International.
* Amenoshita (2015) y Sakuya4 (2018): sus páginas no dicen licencia. Vale la cláusula de
  https://peritune.com/about/ (sección de licencias, cambiada en marzo de 2026): a los temas publicados
  hasta febrero de 2026 se les sigue aplicando CC BY 4.0; a los de marzo de 2026 en adelante, los términos
  propios del sitio. Una licencia CC BY 4.0 ya otorgada no se puede revocar.
* En la misma página, los términos de PeriTune (sin fecha) prohíben vender o redistribuir los archivos de
  los temas solos, piden cifrar la música que va dentro de una obra paga para que no se pueda extraer y
  la permiten sin cifrar en juegos gratuitos donde cifrarla no sea posible. El crédito "PeriTune" es
  optativo para ellos. Ojo: los .ogg cortados están en un repositorio público; eso se apoya solo en la
  CC BY 4.0. Para una versión paga: cifrar la música (por ejemplo AssetBundles cifrados) o escribirle a
  PeriTune.
* Revenge: la página de OpenGameArt pone "CC-BY 4.0" en el campo de licencia, sin otras instrucciones.

### Agregar un tema por fases

1. La fuente en `SOURCES` de `build_boss_music.py` (url, página, autor, título, licencia) y su fila en la tabla
   con lo que se le cambió. Sin licencia que permita cortarla y redistribuirla, no entra. Si es CC BY, su
   línea en el cartel del final.
2. Medir la grilla: BPM y el primer tiempo fuerte (`grid(bpm, primer_compas)`); los ataques del tema tienen que
   caer a ±3 ms de ella. Todo corte se hace en compases de esa grilla, 8 ms antes del tiempo fuerte. Las
   secciones salen de la similitud entre compases (croma por compás) y del nivel de cada uno.
3. Una función por tema que guarde la intro (`save_once`, termina donde arranca el loop de la fase 1), un loop
   por fase (`arrange`: tramos de compases en orden; cada salto va a un compás parecido al que seguiría en el
   tema), la frase de entrada de cada fase (`pickup`: los compases que llevan a esa sección en el tema) y el
   cierre (`outro`, o `stinger` si el tema termina en un fundido). Una sola ganancia por jefe, picos a -1
   dBFS como mucho.
4. La fila en `PHASES` (loop, frase de entrada, desde dónde entra después de un silencio, corte de lo anterior
   si cambia de tono, cierre propio) y en `OUTROS` (cierre, fundido si no hay, si vuelve la zona).
5. Los pasos del encabezado del script: build, Vorbis con Blender, trim, verify (largo exacto, sin retardo,
   costura y empalmes limpios), install (los .ogg, `Tools/Audio/boss_music.json` y
   `Scripts/Audio/MusicPlan.cs`) y las claves nuevas en la lista `music` de `NindoContent` (las registra
   `Tools/Unity/generate_assets.py`, que lee la carpeta `Music`). Para oírlo fuera de Unity:
   `Tools/Audio/sim_music_director.py`.
6. En el juego: `musicKey` del jefe y `Game.Audio.SetBossMusicPhase(n)` en cada fase. Un cambio entra en el
   próximo tiempo con la frase de entrada y la sección nueva cae en un compás; antes de un silencio de la
   pelea, `SilenceBossMusic` y la fase siguiente entra apenas se la pide. Al caer el jefe, `Boss.Die` llama
   a `EndBossMusic` (el cierre en el próximo tiempo).

## Efectos

* Impactos, pasos, crujidos e interfaz: packs *Impact Sounds*, *RPG Audio* e *Interface Sounds* de Kenney (www.kenney.nl), CC0.
* Capas de acero, silbidos, campanas, magia y todos los ambientes: síntesis propia (numpy).
* Clips originales del equipo (Assets/Audios): SwordSwing, SwordClash, Hurt, Dash, Finisher, Boton, Footsteps.

> Ojo: `Assets/Audios/Satellite - John Coltrane.mp3` (y posiblemente `BackgroundMusic.mp3` /
> `Menu-TheRainInfectsAllWaters.mp3`) tienen copyright de terceros: ya no se usan en el juego;
> conviene borrarlos antes de publicar una build.
