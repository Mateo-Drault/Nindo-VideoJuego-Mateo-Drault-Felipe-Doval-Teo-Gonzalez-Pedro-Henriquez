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
| `boss_goro`, `boss_goro_intro`, `boss_goro_2_in`, `boss_goro_2`, `boss_goro_out` | [Boss_Koto](https://opengameart.org/content/bosskoto) | G_P | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | cortado en compases: intro, loop largo con el corte; fase 2 medio tono arriba (re-muestreo 89/84) y +1 dB; el golpe final (c51) medio tono arriba como cierre |
| `boss_lake`, `boss_lake_intro`, `boss_lake_3`, `boss_lake_out` | [Amenoshita](https://peritune.com/blog/2015/07/03/amenoshita/) | PeriTune | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | anacrusa como intro, el ciclo de 63 compases en loop y un loop sin apertura ni corte (c7-c54) para la fase 3; el último tiempo de c124 y el golpe final como cierre; sonoridad normalizada |
| `boss_bamboo`, `boss_bamboo_intro` | [Wuxia](https://peritune.com/blog/2018/06/24/wuxia/) | PeriTune | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | crescendo inicial como intro y el ciclo de 81 compases en loop; sonoridad normalizada |
| `boss_final`, `boss_final_intro`, `boss_final_2`, `boss_final_3`, `boss_final_4`, `boss_final_out` | [Revenge](https://opengameart.org/content/revenge) | TAD | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | cortado en compases: intro, cuatro loops (c5-c20, c21-c56, c55-c70, c61-c68) y el golpe final (c74) como cierre; sonoridad normalizada |
| `ending` | [Sakuya4](https://peritune.com/blog/2018/12/21/sakuya4/) | PeriTune | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | silencios recortados, fundido de 1 s al final, sonoridad normalizada |

Los temas de PeriTune publicados hasta febrero de 2026 siguen bajo CC BY 4.0 (https://peritune.com/about/);
el crédito pedido es "PeriTune". TAD pide crédito por CC BY 4.0 en su página de OpenGameArt.

### Agregar un tema por fases

1. La fuente en `SOURCES` de `build_boss_music.py` (url, página, autor, título, licencia) y su fila en la tabla
   con lo que se le cambió. Sin licencia que permita cortarla y redistribuirla, no entra.
2. Medir la grilla: BPM y el primer tiempo fuerte (`grid(bpm, primer_compas)`); los ataques del tema tienen que
   caer a ±3 ms de ella. Todo corte se hace en compases de esa grilla, 8 ms antes del tiempo fuerte.
3. Una función por tema que guarde (`save`) la intro (una vez, termina donde arranca el loop), cada loop
   (`section_loop`: vuelve donde suena lo mismo que seguiría; `full_cycle` si el tema se repite entero), las
   secciones de entrada dentro de un loop (`entries`: muestra del compás) y el cierre (`outro`: el golpe
   final del tema y su cola). Una sola ganancia por jefe, picos a -1 dBFS como mucho.
4. La fila en `PHASES` (por fase: loop, intro o transición, sección de entrada y, si la transición entra más
   adelante, cuántos compases antes de su final) y en `OUTROS` (cierre, fundido si no hay, si vuelve la zona).
5. Los pasos del encabezado del script: build, Vorbis con Blender, trim, verify (largo exacto, sin retardo y
   costura limpia), install (los .ogg, `Tools/Audio/boss_music.json` y `Scripts/Audio/MusicPlan.cs`) y las
   claves nuevas en la lista `music` de `NindoContent`.
6. En el juego: `musicKey` del jefe y `Game.Audio.SetBossMusicPhase(n)` en cada fase. Un cambio entra en el
   próximo compás; antes de un silencio de la pelea, `SilenceBossMusic` y la fase siguiente entra apenas se
   la pide. Al caer el jefe, `Boss.Die` llama a `EndBossMusic` (el cierre en el próximo tiempo).

## Efectos

* Impactos, pasos, crujidos e interfaz: packs *Impact Sounds*, *RPG Audio* e *Interface Sounds* de Kenney (www.kenney.nl), CC0.
* Capas de acero, silbidos, campanas, magia y todos los ambientes: síntesis propia (numpy).
* Clips originales del equipo (Assets/Audios): SwordSwing, SwordClash, Hurt, Dash, Finisher, Boton, Footsteps.

> Ojo: `Assets/Audios/Satellite - John Coltrane.mp3` (y posiblemente `BackgroundMusic.mp3` /
> `Menu-TheRainInfectsAllWaters.mp3`) tienen copyright de terceros: ya no se usan en el juego;
> conviene borrarlos antes de publicar una build.
