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
| `boss_goro`, `boss_goro_intro`, `boss_goro_2_in`, `boss_goro_2` | [Boss_Koto](https://opengameart.org/content/bosskoto) | G_P | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | cortado en compases: intro, loop largo con el corte; fase 2 medio tono arriba (re-muestreo 89/84) y +1 dB |
| `boss_lake`, `boss_lake_intro`, `boss_lake_3` | [Amenoshita](https://peritune.com/blog/2015/07/03/amenoshita/) | PeriTune | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | anacrusa como intro, el ciclo de 63 compases en loop y un loop sin apertura ni corte (c7-c54) para la fase 3; sonoridad normalizada |
| `boss_bamboo`, `boss_bamboo_intro` | [Wuxia](https://peritune.com/blog/2018/06/24/wuxia/) | PeriTune | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | crescendo inicial como intro y el ciclo de 81 compases en loop; sonoridad normalizada |
| `boss_final`, `boss_final_intro`, `boss_final_2`, `boss_final_3` | [Revenge](https://opengameart.org/content/revenge) | TAD | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | cortado en compases: intro y tres loops (c5-c20, c21-c56, c55-c70); sonoridad normalizada |
| `ending` | [Sakuya4](https://peritune.com/blog/2018/12/21/sakuya4/) | PeriTune | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | silencios recortados, fundido de 1 s al final, sonoridad normalizada |

Los temas de PeriTune publicados hasta febrero de 2026 siguen bajo CC BY 4.0 (https://peritune.com/about/);
el crédito pedido es "PeriTune". TAD pide crédito por CC BY 4.0 en su página de OpenGameArt.

## Efectos

* Impactos, pasos, crujidos e interfaz: packs *Impact Sounds*, *RPG Audio* e *Interface Sounds* de Kenney (www.kenney.nl), CC0.
* Capas de acero, silbidos, campanas, magia y todos los ambientes: síntesis propia (numpy).
* Clips originales del equipo (Assets/Audios): SwordSwing, SwordClash, Hurt, Dash, Finisher, Boton, Footsteps.

> Ojo: `Assets/Audios/Satellite - John Coltrane.mp3` (y posiblemente `BackgroundMusic.mp3` /
> `Menu-TheRainInfectsAllWaters.mp3`) tienen copyright de terceros: ya no se usan en el juego;
> conviene borrarlos antes de publicar una build.
