# Traspaso a la próxima sesión de Claude Code (Nindō), octubre 2026

> Primer mensaje sugerido para la sesión nueva: **"Leé `Docs/HANDOFF_PROXIMA_SESION.md` entero y seguí desde ahí."**
> Lo escribió la sesión anterior (fases A, B1, B2 y B3 más arreglos) cuando se agotó el límite semanal de uso.
> El traspaso viejo (`Docs/HANDOFF_SESION_LOCAL.md`) quedó desactualizado: usá este.

---

## 0. En 30 segundos

* **Nindō**: juego de acción ninja low-poly isométrico, al estilo Tunic, en **Unity 6.3 LTS (6000.3.25f1) con URP 17**.
  Es un proyecto de cuatro amigos:
  * **Felipe Doval** (el usuario): arte 3D de ambiente, HUD y texturas.
  * **Teo González**: modelos y animaciones.
  * **Mateo Drault**: enemigos y mapa.
  * **Pedro Henríquez**: el jugador.
* Kaito, con la bandana mágica del abuelo, rescata al abuelo secuestrado por el clan Kurokage. Hay tres jefes de zona (montaña: Gorō; lago: Mizuchi; bambú: Chikuō, el Maestro del Bambú) y un jefe final (Kokuyō).
* **Estado del juego**:
  * Se juega de punta a punta.
  * Están Mizuchi (el koi), Kokuyō (el jefe final), Gorō con barra falsa y armadura de roca, y **Chikuō**, que reemplazó a Ōzeki (el arquetipo y el bossId siguen siendo `ozeki`: partidas, flags y sello del bambú no cambian).
  * Las variantes por zona tienen ataques propios; ninjas y sumos tienen idles de ambiente.
  * Kaito y los personajes del equipo tienen animaciones nuevas, con las muñecas medidas en el lint de cada pipeline.
* **Lo pendiente**: la fase C2 hizo casi toda la lista de la sección 4 en la rama `c2/integration` (13 frentes `c2/*`, sección 5). Cada pedido dice ahí su estado; lo que quedó abierto está juntado en la sección 4b. C2 ya está en main (`76be027`) y la probó el lead. La fase C3 (seis frentes `c3/*`, sección 5a) arregló lo abierto de C2 y está integrada en `c3/integration`, con una ronda de huecos de la integración encima (`reportes/c3_reports.md`, sección 5). El lead la probó en Unity el 13 de octubre (Gorō, Mizuchi y Kokuyō con los dos bots), rebalanceó con esas peleas y está en main (`a080043`).
* **En curso, fase C4: Chikuō nuevo.** El usuario lo encontró aburrido (la guardia, esperar, ataques muy espaciados) y eligió un concepto nuevo, el ermitaño excéntrico (`handoff/conceptos/chikuo_v2/elegido_*.jpg`): trepa las cañas, tira dardos, se cambia de caña rápido, baja a pegar y vuelve a subir (no toda la pelea), y Kaito lo baja desde el piso con una mecánica nueva. Ramas `c4/chikuo` (diseño, modelo, animaciones, pelea) y `c4/arena` (las cañas trepables); el diseño queda en `handoff/diseno/chikuo_v2.md`.
* **El usuario pide**: calidad de juego publicado, autocrítica, respetar el estilo de arte, y que la partida dure cerca de **una hora**. `Core/PlayClock` la mide de verdad en la consola (por zona y por jefe) y el cartel del final la muestra. Con el factor real/simulado medido para cada jefe (`Tools/Dev/boss_sims/calibration.py`) los cuatro jefes suman ~18 min para el bot "bueno" (~4.5 cada uno) y ~28 min para el "promedio"; el resto de la partida no está medido.

---

## 1. Reglas de trabajo con este usuario (importantes)

* Hablale en **español rioplatense**, corto y honesto. Decí qué verificaste y qué no.
* **Commits** en español, explicando el porqué y terminando con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
* **Pusheá vos cada commit**: a la rama `claude/serene-edison-xd7v94` y, una vez probado en Unity, también a **main**.
  * A main solo fast-forward: `git merge-base --is-ancestor origin/main HEAD` y después `git push origin HEAD:main`. Nunca force.
  * **No abras PRs.**
  * El remoto se mudó a `github.com/Felgimon/Nindo-VideoJuego-Mateo-Drault-Felipe-Doval-Teo-Gonzalez-Pedro-Henriquez` (la URL vieja redirige).
* **No commitees** los cambios locales que Unity genera en el checkout principal: `Nindo/ProjectSettings/ProjectSettings.asset` (define del AI Assistant), `Nindo/UserSettings/*`, `Assembly-CSharp.csproj`, `Nindo.sln`, `Nindo/Logs/*`, `Nindo/Assets/_Recovery*`.
* **Dónde editar**:
  * Checkout principal (donde Unity tiene abierto el proyecto): `C:\Users\Felipe Doval\Documents\Github-local-repostory\Nindo`, rama `claude/serene-edison-xd7v94`.
  * Worktree de trabajo: `.claude/worktrees/handoff-sesion-local-7ceffb`, rama `claude/handoff-sesion-local-7ceffb`.
  * Un hook bloquea editar el checkout principal: se edita y commitea en el worktree, después `git merge --ff-only claude/handoff-sesion-local-7ceffb` en el checkout principal, después `AssetDatabase.Refresh()` en Unity.
* **Unity**: solo por el **MCP de Unity** (`Unity_RunCommand`, `Unity_ManageEditor`, `Unity_GetConsoleLogs`). **Computer-use para Unity fue rechazado**: no lo uses.
  * **El usuario a veces está jugando en el editor.** Antes de cortar el Play fijate en `%LOCALAPPDATA%\Unity\Editor\Editor.log` si hay peleas recientes (`[Nindo] Pelea de`) y si Kaito se mueve.
  * Si cambiás scripts durante el Play, Unity queda "compilando" hasta que salís del Play, y RunCommand se niega a correr.
* **La partida del usuario**: `%USERPROFILE%\AppData\LocalLow\DefaultCompany\Nindo\nindo_save.json`. **Respaldala antes de cada prueba y restaurala después**: al salir del Play el juego guarda.
  * La última del usuario está copiada en `Docs/handoff/partidas/usuario_actual_cp_home.json`: es una partida nueva, en la casa.
  * Partidas de prueba en `Docs/handoff/partidas/` (qué es cada una y cómo cargarla: su `README.md`): una antes de cada jefe (`prueba_goro`, `prueba_mizuchi`, `prueba_bambu`, `prueba_kokuyo`) y `prueba_tarde_cp_lake_falls` (el final del juego antes de Kokuyō).
  * `prueba_juego_completo_cp_lake_falls.json` tiene `final_boss_done` sin `ending`: al cargarla corre el final entero (`ResumeEnding`). Sirve para probar eso, no el lago.
* **Descargas**: el usuario tiene que aprobar cada archivo que se baje de internet. Mostrale nombre, fuente, licencia y tamaño.
* **Higgsfield** (MCP `4e3e7df2…`): sirve para hojas de concepto (`generate_image_batch`, `gpt_image_2_5`, ~0.25 créditos por imagen), con aprobación del usuario. **No sirve para música**: su modelo de música está reservado para otro uso.
* **Herramientas disponibles**:
  * Blender 5.2 por CLI (`"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe" -b --factory-startup --python script.py -- args`); el 4.4 ya no está. Las diferencias de API de 5.2 están juntas en `Tools/Blender/bl_compat.py`: todos los pipelines pasan por ahí. Hay un MCP de Blender, pero **el usuario prefiere la línea de comandos** (no quiere tener Blender abierto todo el tiempo).
  * Blender en Windows no abre un script de más de 260 caracteres de ruta: con el scratchpad largo, copiá a una carpeta corta o corré desde el repo.
  * MCP de Unity, Higgsfield, Python con PIL y numpy.
  * `python Tools/Dev/compile_check.py --project "<checkout principal>/Nindo"`: compila todo el C# sin Unity, en unos 30 s. Corrélo antes de cada commit de C#.

### Trampas conocidas (cada una ya costó tiempo)

* **Animaciones en un FBX aparte**: si el archivo tiene un solo nodo raíz (Armature), Unity lo aplana y los clips terminan animando la raíz del modelo.
  * En octubre pasó: escala ×100, los enemigos quedaron invisibles y solo se veía la barra de vida.
  * Los `.meta` de `Art/Characters/TeamAnims/*Anims.fbx` llevan `preserveHierarchy: 1`, y `generate_assets.py team_anim_metas()` lo escribe.
  * Verificá siempre que las rutas de las curvas empiecen con `Armature/…` y que **cada enemigo tenga el cuerpo visible junto a su barra**.
* **Ver todo celeste** justo después de importar o de entrar en Play es el shader provisorio del editor mientras compila (compilación asíncrona). No es un error.
* **Reimportar las TTF con Unity abierto lo crasheó** (FontEngine). Para tocar fuentes: cerrá Unity (`EditorApplication.Exit(0)`), mergeá y volvé a abrirlo.
* **El resume de un Workflow** vuelve a correr agentes que ya habían terminado cuando cambia el orden de las llamadas. Para relanzar solo lo que falló, escribí un script nuevo filtrando los frentes (como `Docs/handoff/fase_c_frentes_workflow.js` con `args.only`).
* **`scriptPath` en Workflow** a veces lo rechaza el control de permisos ("control characters"). Pasar el script en línea funcionó.
* **Agentes y worktrees**:
  * Los agentes no pueden usar el MCP de Unity: solo compilan, simulan en Python y renderizan en Blender. **Probar en Unity es trabajo tuyo.**
  * Para editar en otro worktree tienen que llamar `EnterWorktree(path)`.
  * Worktrees ralos (≈0.5 GB):
    ```
    git worktree add --no-checkout -b <rama> <ruta> <base> && cd <ruta> && MSYS_NO_PATHCONV=1 git sparse-checkout set --no-cone '/*' '!/Nindo/Assets/Textures/' '!/Nindo/Assets/_Legacy/' '!/Nindo/Assets/Characters/Sumo/2.fbx' && git read-tree -mu HEAD
    ```
* **Bash**: los `sleep` largos y encadenados están bloqueados; usá `Monitor` con un bucle `until`. En los heredocs de bash con barras invertidas, escribí los .py con la herramienta Write.

---

## 2. El proyecto por dentro (mapa rápido)

* **Código**: `Nindo/Assets/Nindo/Scripts/`
  * `Core/`: Game, GameBootstrap, SaveSystem/Settings, NindoContent, CharacterFactory, CharacterKits, TimeController.
  * `Player/`: PlayerController(.Combat), PlayerConfig.
  * `Enemies/`: Enemy, Boss, EnemyArchetypes (los AttackDef de todos), EnemyVariants, VariantMotion, SumoPoser, StepTimeline (tiempos de aviso y embestidas en cuadros del clip), EnemyAmbient (idles de ambiente).
    * `Enemies/Bosses/`: MizuchiBoss(+Moves, Pacing), KoiBody, WaterPearl, MizuchiMarks, KokuyoBoss, KokuyoMoves/Timings/Hazards/Look, KageShadow, GoroBoss(+GoroArmor, GoroAvalanche), BambooMasterBoss(+Moves, Look, Qi, Story, BambooMasterTimings).
  * `Combat/`: CombatDirector (tokens), CharacterAnimator, CombatTypes.
  * `Camera/`: CameraDirector (planos, perfil de jefe ICameraProfile, SetFocusBias, auto-encuadre), CameraOcclusion.
  * `FX/`: FXManager, CombatTelegraphs (anillos ensō), ParryCrescent, ScreenFX, CharacterGlint, KohanFalls (la cascada), FloodSheet, WaterSplash, Braziers, MoonEclipse, PlanarShadow, ShadowRopes, KageArenaFX, FinisherStreak, XRaySilhouette, SpringChain, BandanaGlow.
  * `UI/`: UIManager(.HUD/.Panels/.World), UIFactory, UISprites, ThreatIndicators.
  * `Story/`: StoryDirector(.Kokuyo, .Ending, .Shrines, .Prologue), StoryText (todo el texto del juego), KaitoTimings (los momentos de los clips de historia, generado por `Tools/Unity/kaito_timings.py`), NPC.
  * `World/`: WorldBuilder, Areas (Zone, Encounter, BossArena, ArenaBarrier, BarrierFade, LightPool), Interactables (Checkpoint/santuario, KeyPickup, SealGate), ZoneCulling (activación por zonas; el banco de pruebas es Ctrl+Shift+F9).
  * `Input/`: InputReader, BindingTable (controles reasignables), AutoPilot.
  * `Audio/`: AudioManager, MusicDirector (un tema por jefe con fases, en el reloj DSP).
  * `Core/PlayClock`: la hora de juego.
* **Shaders**: `Nindo/Assets/Nindo/Resources/Shaders/` (CharacterLit, Telegraph, Waterfall, FoamWater, Spray, Mist, InkStreak, CharacterXRay, Moon, ShadowInk…).
* **Pipelines** (ver README):
  * `Tools/Unity/generate_assets.py`: personajes, controllers, metas, `NindoContent.asset`. Correrlo entero reescribe cosas ajenas: tocá sus entradas a mano o revertí lo que no corresponde.
  * `Tools/Blender/world/` (`world_plan.py`, `validate_plan.py`, `build_world.py -- --export`): el mapa, los checkpoints y las arenas. Las coordenadas están en `world_plan.py`.
  * `Tools/Blender/props/`: props y manifest.
  * `Tools/Blender/characters/`: export de los modelos del equipo.
  * `Tools/Blender/anim/`: `nindo_anim.py`, `kaito/*` y `team_*.py` (clips del equipo: build_team_anims.py y apply_team_anims.py).
  * `Tools/Blender/bosses/{mizuchi,kokuyo}/`.
  * `Tools/Audio/build_audio.py`: efectos sintetizados.
  * `Tools/UI/`: el kit de sprites de la interfaz.
* **Música**: `Nindo/Assets/Nindo/Audio/Music/*.ogg`, todo CC0 de OpenGameArt; los créditos están en `Audio/CREDITS.md`.
  * Cada jefe tiene su tema con fases (`boss_goro`, `boss_lake`, `boss_bamboo`, `boss_final`) y el final el suyo (`ending`), por `Audio/MusicDirector`. *bosskoto* (G_P, **al usuario le encanta**) quedó para Gorō, con el clímax en su fase 2.
  * Dos pistas de PeriTune (Amenoshita y Sakuya4) se usan como CC BY 4.0 por la cláusula general del autor: sus páginas no dicen licencia. **Falta que el usuario lo apruebe** (sección 4b).
* **Coordenadas útiles** (de `world_plan.py`):

  | Jefe | Arena (centro, radio) | Checkpoint cercano |
  |---|---|---|
  | Gorō | (-200, 122), r15 | `cp_mountain_top` (-189, 112) |
  | Mizuchi | (184, 72) | `cp_lake_falls` (177, 58); para entrar, teletransportar a (184, 3, 64) y hacer `goto 184 69` |
  | Chikuō / bambú | (124, 162) | `cp_bamboo_gate` (111.5, 144.2); el arco de bambú traba el `goto`, mejor teletransportar a (122, 150) |
  | Kokuyō | (0, 132) | `cp_dojo` (8, 114.5); `goto 0 124 15` funciona |

* **AutoPilot** (`Nindo.AutoPilot.Run("…")`, pasos separados por `;`):
  * Generales: `tap Submit` (Continuar en el menú), `goto X Z [max]`, `talk [max]`, `waitcontrol [max]`, `pose ESTADO [vel]`, `kokuyo act N`.
  * `bot on [experto|bueno|promedio]` / `bot off`:
    * **experto**: 0.25 s de reacción y nunca falla. Sirve para saber si un aviso se puede leer. **No sirve para balancear**: con él los jefes caían en 20 a 40 s.
    * **bueno** y **promedio**: más lentos, a veces no ven el aviso, a veces confunden parry y dash, a veces atacan apurados. Usalos para balancear.
  * Ojo: `talk` se termina en la pausa entre dos diálogos y después `waitcontrol` queda esperando. Si `Game.InCutscene && !AutoPilot.Busy`, volvé a correr `talk 10; waitcontrol 20; bot on bueno`.
* **Para probar**:
  * Partida con el checkpoint deseado y los flags del jefe sacados (`boss_<id>`, `boss_seen_<id>`; para Kokuyō también `final_boss_done`). Para cada jefe ya están hechas en `Docs/handoff/partidas/` (`prueba_goro.json`, etc.).
  * Play, después `AutoPilot.Run("wait 0.5; tap Submit")`, después teletransportar a Kaito (desactivar el CharacterController, mover, reactivar).
  * Capturas con `ScreenCapture.CaptureScreenshot(path, 3)` desde una clase estática colgada de `EditorApplication.update`, con un `Debug.Log` por captura. La carpeta de capturas va en el scratchpad.
  * `Game.Save.flags` se puede editar en vivo (por ejemplo `.Remove("falls_seen")`).

---

## 3. Qué está hecho (resumen)

* **A + B1**: combate legible.
  * Avisos con anillo ensō dorado (golpe que se puede parar) o rojo (imparable: se esquiva con dash), un "¡ya!" con sonido (hyōshigi/taiko) a 0.33 s del golpe.
  * Media luna de parry, postura de los jefes, tokens de ataque, TimingCoach ("temprano / tarde").
* **B2**:
  * UI "Nindō": la bandana roja es la vida y el dragón amarillo el espíritu; menú con kunai; trazos de tinta.
  * CharacterLit y los personajes del equipo pulidos; kits por zona con SpringChain.
  * Modelos y clips de Mizuchi y Kokuyō.
  * Cascada Kohan, patio de Kokuyō (braseros, eclipse, sombra plana), checkpoints nuevos.
* **B3**:
  * Peleas completas de Mizuchi (3 fases, perlas, crecida, ascenso final) y de Kokuyō (actos, sombra adelantada 0.36 s, Kage, eclipse, final).
  * Ōzeki yokozuna; variantes con ataques propios; brillo en los avisos; ajustes de "Avisos de combate"; objetivo según el progreso.
  * Clips nuevos de Kaito (21) y del ninja, el sumo, Gorō y el abuelo.
* **Después de B3**:
  * Espuma y grúa de presentación de la cascada.
  * Silueta de Kaito tapado (**el usuario no la quiere así**, ver la tarea 20).
  * Barrera de arena con degradé que se apaga en las cinemáticas; avisos que no tapan al jefe.
  * Vida: Mizuchi 720, Ōzeki 760; fase 3 de Mizuchi al 33 %.
  * Enemigos invisibles arreglados (`preserveHierarchy`).
  * Bot con niveles.
* **Todo eso está en main**: `origin/main` = `70351e4`.

---

## 3b. Hecho el 11 de octubre (probado en Unity y en main, `3ad9195`)

* **18** objetivo y cartel trabados: cualquier flag refresca el objetivo; el cartel de interactuar se esconde si su objetivo se destruyó, quedó lejos o no se puede usar.
* **19** sin "Victoria" en las peleas comunes.
* **20** silueta: stencil (bit 32) que marcan jefes y sumos con `Nindo/OccluderMark` (`XRayOccluder`, copias fuera de la jerarquía del jefe). Ya no se marca sobre el propio Kaito. Falta que el usuario la vea y diga si la quiere así o sacarla.
* **21, 22, 23, 24** (del WIP `c/ui-hud`, mergeado y terminado): avisos medidos y en dos renglones con `BrushBanner`, sin " — " (santuario: nombre + "Vida restaurada"/"Punto de reaparición"; gritos con `ShowBark`), halo de tinta en vez de contorno (`UIFactory.Legible`, `Resources/UI/TextHalo.mat` para el build), relleno de vida nuevo, ojo del dragón nuevo. **Indicador de guardado** (`UIManager.Save.cs`, `GameEvents.Saved`): pergamino, pincel que escribe "Guardado" y sello del nudo.
* **28** sin Espíritu no hay dash: aviso (dragón + sonido) y un paso de 3 m sin i-frames (0.8 s de espera). El bot ahora recibe golpes si dashea sin Espíritu: tenerlo en cuenta al balancear.
* **29** el anillo de combate crece hasta 10 m para encerrar a Kaito y a los enemigos, y si Kaito sigue lejos espera a que entre.
* La rama `c/ui-hud` ya está integrada: se puede borrar su worktree.
* Ojo en AutoPilot desde RunCommand: formateá los números con `CultureInfo.InvariantCulture` (con la coma decimal, `goto -25,0 …` manda a Kaito a cualquier lado). `Unity_ReadConsole` lo bloquea el clasificador de permisos: usá `Unity_GetConsoleLogs`.

## 4. Los pedidos del usuario (los de 3b ya están)

Están casi en sus palabras, con notas. Al final de cada uno, entre corchetes, **su estado después de la fase C2** (todo en `c2/integration`, sin probar en Unity todavía). Lo que quedó abierto está juntado en la sección 4b. `Docs/handoff/fase_c_frentes_workflow.js` tiene los frentes de la fase C especificados en detalle (contratos entre frentes, alcance, validación) y se puede reusar pasándole `args: { only: [...] }`.

### 4.1 Animación y modelos
1. **El abuelo arrastrado** (prólogo y bosque): mejorar la animación. Contacto creíble con el ninja que lo lleva (manos en el cuello o el brazo), talones que se arrastran con polvo, forcejeo. Clips `Kidnap`/`Dragged`. **[C2 hecho, c2/grandpa: agarre de las muñecas, arrastre sin patinar, polvo de los talones.]**
2. **Kaito despertándose en el suelo** al ver que secuestran al abuelo: clip `WakeUp` bien hecho y una cámara que lo muestre (`StoryDirector.Intro` / `LieDown`). **[C2 hecho, c2/kaito-anim y c2/world-story.]**
3. **Muñecas y brazos doblados** en varios ninjas, Kaito y el abuelo: corregir el modelo. Averiguar si viene del bind pose, de los pesos o de las rotaciones de las manos en los clips. **[C2 hecho: los lints de Kaito, del equipo y de Chikuō miden las muñecas con los límites de team_limbs. Quedan tirones de un cuadro de Kaito como avisos (4b).]**
4. **La cola de la bandana amarilla está duplicada.** La malla de `kaitooo.fbx` tiene sus propias colas animadas y además están las del kit (`Kit_kaito_bandana.fbx` + SpringChain) con física. Tiene que quedar **un solo juego de colas, con física**. **[C2 hecho: solo las del kit; el nudo del cuerpo es un moño y pesa entero a la cabeza.]**
5. **Idles nuevos y realistas**: ninjas meditando sobre una roca, entrenando entre ellos en pareja, el sumo durmiendo con las manos en la panza; un sobresalto antes de pelear. Contrato: `IdleMeditate`, `IdleSparA/B`, `IdleSleep`, `AmbientAlert`, más un `Enemies/EnemyAmbient.cs` nuevo. **[C2 hecho, c2/ninja-sumo.]**
6. **Lo pendiente del pase de animación anterior (B4)**:
   * **Ninja y sumo**:
     * Strafe izquierda/derecha y retroceso: hoy caminan hacia adelante mientras rodean a Kaito.
     * Cachetazos del sumo con el brazo bien extendido y carrera erguida.
     * Pies que patinan cuando la embestida del código no coincide con la del clip (Morote 1.6 contra 0.6, remolino 1.1 contra 0.8, arpón 2.4 contra 3.2, salto 4.4 contra 1.4) o cuando el imán del ataque la acorta.
     * Saltos que se lean desde arriba.
     * **La hoja del ninja apenas se ve** desde la cámara: hacerla de acero claro con lomo oscuro.
   * **Gorō**:
     * El arma atraviesa el torso (Combo2, caída del Heavy).
     * En Parried el arma salta por encima en 1 o 2 cuadros.
     * Rehacer su Intro e Idle, que todavía son los del equipo.
   * **Abuelo**: `Bound` (atado, arrodillado) y `Freed` para el final de Kokuyō, y `Walk`.
   * **Kaito**:
     * El rezo (lo reemplaza `PrayIncense`, ver 4.3).
     * Una muerte con más peso: arreglar la mano que no llega en Death (3.6 cm) y en Attack3 (2.6 cm).
     * Reacciones al golpe según de dónde viene: `HitBack`/`HitLeft`/`HitRight`.
     * Transiciones que saltan (Dash → Attack1, la réplica temprana después de un parry).
     * Frenada (RunStop).
   * **Limpieza del esqueleto** donde las manos o los pies cuelgan de controles de IK (sumo, Gorō, abuelo): se hace como se hizo con Kaito, sin cambiar nombres ni GUIDs.
   * **[C2 hecho casi todo, c2/ninja-sumo, c2/team-rig, c2/goro, c2/grandpa, c2/kaito-anim: rodeo de costado, bofetadas largas, embestidas en cuadros del clip con su lint, saltos, Gorō sin el martillo en el cuerpo ni saltos en Parried, Intro e Idle propios, Bound/Freed/Walk del abuelo, muerte con peso, HitBack/Left/Right, RunStop. Abierto: Gorō no pasa el lint nuevo de la embestida y sus manos se despegan del mango (4b).]**
7. **"Ult" cortada**: el remate y las habilidades (Corte del Viento, Torbellino de Hojas) vuelven a la cámara de juego demasiado pronto. El usuario quiere **un segundo** de Kaito en la pose final, tanto en el clip como en la duración del plano (`CameraDirector.PlayFinisherShot` / `PlayAbilityShot`, `Player/*`). **[C2 hecho: un segundo de zanshin en el clip y en el plano.]**

### 4.2 Jefes y balance
8. **Reemplazar por completo al jefe del bambú.** Un **anciano maestro de kung fu**, sabio, que **no se parezca al abuelo de Kaito**, con ropa de kung fu y habilidades de kung fu. Animaciones profesionales de ataques, **bloqueos** y especiales. Pensar estilo de arte, diseño y sensación de juego.
   * Pasos: concepto con Higgsfield, modelo y rig en Blender (`Tools/Blender/bosses/bamboo_master/`), clips, y `Enemies/Bosses/BambooMasterBoss.cs`.
   * **Mantener** el arquetipo `ozeki` y bossId `ozeki` (partidas, flags y sello del bambú). El personaje nuevo se llama `bamboo_master`.
   * Ideas que estaban en el plan:
     * Palmas y combos dorados, patada de grulla, patada voladora roja con marca en el piso, barrida.
     * Postura de bloqueo que contraataca si lo atacás: enseña paciencia.
     * Onda de qi como anillo rojo, embestida rápida con imágenes residuales.
     * Cambio de fase con bastón de bambú o sacándose la túnica.
     * Derrota: se sienta a meditar y le hace una reverencia.
   * **[C2 hecho, c2/bamboo-master: Chikuō, con palmas, grulla, patada voladora, barrida, postura del bambú que contraataca, onda de qi, embestida con imágenes residuales, el saco que se saca, el bastón en la fase 3 y la derrota meditando. Vida ~2000. Abierto: no es chibi como el resto (4b).]**
9. **Gorō: barra de vida falsa y fase 2.**
   * Vida total el doble.
   * Cuando la primera barra se vacía, "le ganaste": cae, hay un silencio, y de golpe muchas rocas vuelan y se le pegan al cuerpo.
   * Se levanta épicamente con una armadura de roca exagerada. El título pasa a ser "Gorō, <nombre de fase 2>", con un epíteto a inventar y sin kanji.
   * Fase 2: los mismos ataques pero más difíciles y con variaciones, y uno nuevo: una **avalancha** que baja por la ladera en carriles rojos con aviso, que se esquiva corriendo y que nunca arranca fuera de pantalla.
   * La música tiene que llegar a su clímax en la fase 2.
   * Código nuevo: `Enemies/Bosses/GoroBoss.cs`.
   * **[C2 hecho, c2/goro: barras de 1000 + 1600, avalancha, armadura en tres tramos que curan, el reintento arranca armado, la música por fases. Abierto: la armadura podría ser más grande (4b).]**
10. **Vida doble en todos los jefes** (Mizuchi 1440, Kokuyō 1800, bambú ~1400, Gorō ~1040 entre las dos barras) y algunos especiales más rápidos, para peleas más dinámicas.
    * **Objetivo: que la partida dure ~1 hora** (hoy ~30 min).
    * Después balancear en Unity con `bot on bueno` / `bot on promedio`: el bueno gana en unos 4-6 min por jefe, el promedio muere alguna vez.
    * **[C2 hecho en simulación (`Tools/Dev/goro_fight_sim.py`, `sim_bamboo_master.py`, `boss_sims/`): Gorō 1000 + 1600, Mizuchi y Kokuyō x1.5 (2160 y 2700, con el daño que aguanta el promedio), Chikuō ~2000; el bot promedio se recalibró (falla 15 %, se confunde 7 %, ataca apurado 15 %). Falta medir en Unity con PlayClock.]**
    * **[C3: con las ocho peleas del bot que el lead corrió sobre C2 el factor real/simulado es Gorō 0.71, Mizuchi 1.19, Kokuyō 0.92 y Chikuō 1.42 (`boss_sims/calibration.py`); con eso Gorō 1900 + 3040, Mizuchi x2.5, Kokuyō x4 y Chikuō 1900 dan ~4.5 min de juego para el bueno y 1-1.6 muertes para el promedio en cada jefe. Provisorio: medir tres peleas por bot con lo de C3 (`reportes/c3_reports.md` 5.1).]**
    * **[Medido en Unity el 13 de octubre (C3 integrada, PlayClock).** Con lo de C3 el bot promedio no moría con ningún jefe
      (Gorō 5:11, Mizuchi 5:01, Kokuyō 6:29, los tres sin morir) y Mizuchi duraba poco para el bueno (3:29). Rebalanceado
      con más peleas, en minutos de juego:
      * Gorō (daño x0.35 / x0.30): bueno 4:19 sin morir (antes del cambio de daño; la vida no cambió), promedio 6:36 con 1 muerte.
      * Mizuchi (vida x2.9, daño x0.37, postura 17): bueno 4:31 sin morir, promedio 7:17 con 1 muerte. El promedio salta mucho
        con el daño: con x0.39 y postura 15 fueron 14:59 y 5 muertes; con x0.35, 4:53 sin morir.
      * Kokuyō (vida x4.2, tramos 40 / 40 / 35): bueno 5:04 sin morir con daño x0.37; promedio 11:33 con 3 muertes con x0.37, y
        el daño quedó en x0.35 (sin medir todavía con ese número).
      * Chikuō: se rehace en C4; el viejo no se re-midió.
      Una pelea por bot y por número: el promedio varía mucho, conviene medir dos o tres más antes de darlo por cerrado.]**
11. **Kokuyō**:
    * **La sombra viva casi nunca ataca.** El usuario la considera la mejor mecánica: tiene que estar en todos los actos.
    * En la fase de luna llena, donde la sombra no se ve, cuando ataca **tiene que hacerse visible un segundo antes y poder pararse** (difícil pero justo).
    * En el cambio de luna **se nota un rectángulo**, como el borde de una capa (`MoonEclipse` / shader de la luna / planos del cielo).
   * **[C2 hecho, c2/combat-kokuyo: la sombra pelea en los tres actos, en la luna llena se ve antes de pegar (con un filo de tinta en la hoja) y la luna ya no tiene rectángulo.]**
12. **Final**:
    * La música no va con el rescate.
    * Mejorar la animación de Kaito cuando se da vuelta y le da la cinta a Kokuyō (`EndingTurn`, `StoryDirector.Kokuyo.EndingScene`).
   * **[C2 hecho: el final suena con su tema, EndingTurn saca la media cinta del cinturón y se retoma si la partida se cerró en medio.]**

### 4.3 Mundo e historia
13. **Santuario**:
    * Hoy **brilla demasiado** cuando se activa y no se entiende el modelo. Por defecto no tiene que brillar nada; después de rezar, un brillo muy leve y **humo de incienso**.
    * **Escena de rezo** con cámara de costado: Kaito se arrodilla, prende el incienso, lo apoya en el santuario y reza por el abuelo (clip `PrayIncense` con eventos).
    * La primera vez se ve completa; después, una versión corta.
   * **[C2 hecho, c2/world-story.]**
14. **Tutorial temprano** que avise que se puede **rezar** en los santuarios (cura, guarda y marca el punto de reaparición). **[C2 hecho.]**
15. **Muralla del Jardín del Clan**: después de ganarles a los ninjas, Kaito se acerca a la muralla y la abre con el poder de la bandana (clip `BandanaPower`, VFX, sonido, cámara). Hoy el portón se abre solo. **[C2 hecho.]**
16. **Puerta de los tres sellos**:
    * Cada círculo muestra el ícono de su jefe.
    * Los sellos se ponen **de a uno**, apenas los tenés (ganás a Mizuchi, vas y ponés el suyo). La puerta abre con los tres.
    * Hay que guardar cuáles están puestos.
   * **[C2 hecho.]**
17. **Optimización**: hoy **no hay sistema por chunks**. Existe: FBX por zona, static batching, frustum culling de Unity, decoración del piso fusionada por chunk, LightPool, far clip 400 y la cascada que se apaga a 110 m. Falta: activar y desactivar zonas, props, luces, partículas y la IA de enemigos según la distancia, con histéresis y sin pop-in a la vista. Hay que medir la ganancia. **[C2 hecho, c2/culling: `World/ZoneCulling`. Falta medir la ganancia en un build con el banco de pruebas (Ctrl+Shift+F9).]**

### 4.4 Interfaz
18. **El cartel "Desatá la bandana" queda trabado** hasta que aparece otro (rezar, portal). Hay que esconder los carteles cuando su objetivo ya no está, se usó o quedó fuera de rango (`UIManager.World`, `Interactables`, `StoryDirector` del prólogo).
19. **Sacar el cartel "Victoria"** después de las peleas comunes; dejarlo solo en los jefes.
20. **La silueta amarilla a través de Kaito no le gusta.**
    * Hoy es `XRaySilhouette` + `NindoCharacterXRay.shader`, con ZTest Greater y la malla adelantada 0.5 m. Las partes de Kaito se marcan sobre él mismo.
    * Solución pensada: stencil. El pase de CharacterLit de los personajes grandes (jefes, sumo) escribe un valor; la silueta solo se dibuja donde está ese valor y con ZTest Greater, así los píxeles del propio Kaito nunca califican.
    * Si no queda limpio, sacarla.
21. **El trazo negro de los mensajes queda corto** para el texto (`ShowToast`, banner; en pelea se achica, ver `UpdateBanner` y `fight`). Hay que medirlo bien, con relleno, mínimo y máximo, y pasar a dos renglones si hace falta.
22. **Sacar los guiones " - "** de todos los textos (por ejemplo "Santuario de Kodoyama - Partida guardada"): ir a dos renglones.
    * Agregar un **indicador de guardado** abajo a la izquierda, ~3 s, tipo loader, estilo Nindō, innovador y divertido. Ideas: un pincel que cierra un ensō, el nudo de la bandana atándose, un farol que se prende.
23. **El contorno negro** de los títulos de zona y los textos sobra: comparar sin contorno, fino y con sombra suave, y elegir.
24. **HUD**:
    * El relleno de vida dentro de la bandana está corrido a la izquierda y no se ve el diseño entero.
    * **El ojo del dragón no le gusta**: probar otras opciones en su estilo.
25. **Mapa con M**: dónde estás, niebla sobre las zonas no exploradas (se guarda en la partida), santuarios, estilo Nindō. Pausa el juego. **[C2 hecho, c2/ui-map.]**
26. **Controles reasignables**: cada acción, sin conflictos (intercambiar o rechazar con un mensaje), resetear, guardar, y mostrar las teclas con los key-caps actuales. **[C2 hecho, c2/ui-controls: Opciones › Controles.]**

### 4.5 Combate
27. **Efecto de parry de Kaito**: hoy es la misma forma que el segmento de ensō bajo el enemigo. Tiene que ser **distinto, pero con el color relacionado**: por ejemplo un destello de acero horizontal, chispas y una onda corta, con una variante para el perfecto. **[C2 hecho: parry con lenguaje de acero.]**
28. **Dash sin espíritu**: es un bug. El documento de diseño dice que el dash mágico gasta Espíritu y que sin barra no hay dash. Arreglarlo con aviso (el dragón parpadea y suena). Evaluar si conviene un pasito sin invulnerabilidad.
29. **Kaito queda afuera del anillo amarillo de combate** (`ArenaBarrier`, `Encounter.lockArea`): el anillo tiene que encerrar a Kaito y a todos los enemigos, o arrimarlo suavemente.

### 4.6 Música (después de que el usuario apruebe las descargas)
30. **Un tema propio, icónico y que represente a cada jefe**, que cambie un poco en cada fase. Nada de temas compartidos.
    * Decidir quién se queda con *bosskoto* (le encanta; la idea natural es Gorō, alargado y con clímax en su fase 2).
    * Buscar temas nuevos para Mizuchi, el maestro del bambú y Kokuyō (si *great-boss* no alcanza), y uno para el final.
    * Fuentes: CC0 preferido (OpenGameArt) o CC-BY con crédito (incompetech, freepd, FMA según la pista).
    * Arreglar que Mizuchi no tenga música (`boss_lake`).
    * Sistema de música por fases: claves `boss_goro`, `boss_lake`, `boss_bamboo`, `boss_final`, `ending`. Intro, loop A y loop B o salto de sección con fundido; frase de transición; sin cortes audibles.
    * Armá una lista corta (página, URL del archivo, licencia citada, autor, duración, tamaño, por qué encaja, qué parte sirve para cada fase) y **pedile aprobación** antes de bajar.
    * **[C2 hecho, c2/music: los temas por fases y los créditos en el juego. Abierto: la aprobación de las dos pistas de PeriTune (4b).]**

## 4b. Abierto después de la fase C2

* **Música**: Amenoshita y Sakuya4 (PeriTune, `boss_lake` y `ending`) se usan como CC BY 4.0 por la cláusula general del autor; sus páginas no dicen licencia. Que el usuario lo apruebe (y quede anotado en `Audio/CREDITS.md`) o cambiarlas por pistas con CC BY o CC0 en su página.
* **Kaito** (`Tools/Blender/anim/kaito`): `build_kaito.py` avisa tirones de un cuadro (manos, codos, piernas) en casi todos los golpes y en las escenas: BandanaPower f36-38 (la mano izquierda 117°, el húmero 94°), Death f32-35 (la pierna derecha 71°, el brazo izquierdo 112°), PrayQuick f45-46 (75°), EndingTurn f27-29 (el pie izquierdo 56°), WakeUp, Pray y PrayIncense (45-55°). El pedido era que en las escenas fallen arriba de 45° por cuadro: falta un tope de giro por cuadro en el camino de los brazos (`kaito_rig.arm_path`) y repartir la suelta de BandanaPower y el estirón de piernas de Death en 3-5 cuadros. **[C3, c3/kaito-snaps: el lint falla arriba de 45° en escenas y 60° en golpes en cualquier hueso, a la velocidad del código; 0 FAIL. El Corte final pega con las dos manos y el chiburi del remate va a x1. Quedan avisos a x1.12 con la furia.]**
* **Gorō** (`Tools/Blender/anim/build_team_anims.py -- goro`): no pasa el lint de la embestida que agregó c2/ninja-sumo (con el reloj del juego los pies apoyados patinan 6-16 cm en Combo1/2/3, Combo1B/2B/3B y SlamWave), así que GoroAnims.fbx no se puede re-exportar hasta arreglarlo. Pendientes del mismo pase: las manos se despegan del mango 2.9-5.2 cm (Combo1, Combo3, Heavy, Combo3B, AvalancheSummon), la cadera de FakeDefeat y ArmorRise 3 cm bajo el piso, el martillo 2.7 cm en el piso en Heavy. La armadura es parda con brasa más ancha; **más grande** (x1.3) choca con el mango y con el piso en 13 chequeos: hay que agrandarla junto con los caminos del martillo. **[C3, c3/goro-anim: la embestida va en cuadros del clip y es un paso de verdad (0 cm de patinaje en el lint), variantes en el lugar con Kaito contra la barrera, el agarre y el martillo arreglados, la armadura crece pareja y sin nieve; GoroAnims.fbx re-exportado con 5.2. Balance provisorio 1900 + 3040.]**
* **Chikuō**: no es chibi como el resto (2.6 m, cabeza chica, manos de mitón): es decisión de Felipe. La pelea es mayormente rebotes (~0.9 por segundo con el bot bueno) y el Paso del Viento vuela poco; el saco sale en un cuadro (se podría deslizar en 6-8). **[C3, c3/chikuo-feel: desvía con la palma leyendo el corte, el paso del viento vuela, sigue a Kaito y pasa al costado, el saco se desliza. Sigue sin ser chibi. El desvío del Corte final nuevo de Kaito tiene su clip (`GuardHitLow`), el primer corte apartado lo roza y el paso del viento sigue volando después del cruce: `reportes/c3_reports.md` sección 5.]**
* **Ambiente**: el pase de Felipe sobre el mundo (lo que quedó del ítem de basaltos que se leen como hielo).

Lo que quedó abierto después de C3 está en [`handoff/reportes/c3_reports.md`](handoff/reportes/c3_reports.md), sección 4.

---

## 5. Ramas de la fase C2

Las ramas `c2/*` son locales (no están en origin) y están integradas en `c2/integration`, que ya está en main (`76be027`) y la probó el lead en Unity.

**Los informes de cada frente** (contratos y APIs, chequeos y simulaciones, y la lista de pruebas en Play de cada uno, de la integración y de los arreglos de huecos) están en [`handoff/reportes/c2_reports.md`](handoff/reportes/c2_reports.md).

| Rama | Qué trajo |
|---|---|
| `c2/team-rig` | Rig del equipo con muñecas validadas, el segundo esqueleto (el ninja del secuestro) y el pipeline de Blender 5.2 (`bl_compat`). |
| `c2/kaito-anim` | Clips de historia de Kaito (WakeUp, PrayIncense, PrayQuick, BandanaPower, EndingTurn), golpes según el lado, frenada, muerte con peso, una sola bandana. |
| `c2/ninja-sumo` | Idles de ambiente (`EnemyAmbient`), rodeo de costado, bofetadas, saltos, embestidas en cuadros del clip y su lint de patinaje. |
| `c2/goro` | Barra falsa, armadura de roca que se le arma encima, fase 2 con la avalancha, manos sin teletransporte. |
| `c2/grandpa` | Secuestro con agarre de muñecas, arrastre sin patinar, atado de rodillas con cuerdas y liberación. |
| `c2/bamboo-master` | Chikuō, el Maestro del Bambú, en lugar del Ōzeki (modelo, 107 clips, pelea, balance). |
| `c2/combat-kokuyo` | La sombra viva de Kokuyō en los tres actos, la luna sin rectángulo, el parry de acero, la vida de Mizuchi y Kokuyō. |
| `c2/music` | Un tema por jefe con fases y el del final (`MusicDirector`), créditos en el juego. |
| `c2/world-story` | Santuarios con incienso y rezo, el consejo de rezar, la muralla que abre la bandana, la puerta de los sellos de a uno, el despertar y el final. |
| `c2/culling` | `ZoneCulling`: apaga lo que ninguna cámara ve, congela la cascada fuera de cuadro y duerme por campamento a los enemigos lejanos. |
| `c2/ui-map` | El mapa con la M. |
| `c2/ui-controls` | Controles reasignables. |
| `c2/integration` | Las doce integradas más los arreglos de la revisión final (reintentos de Gorō y Mizuchi, títulos de jefe en el tercio de abajo, PlayClock, partidas viejas, muñecas de Chikuō, nudo de la bandana, rugido de Gorō más cerca...). |

Las listas de pruebas en Play de cada frente y de la revisión final están juntas en `handoff/reportes/c2_reports.md`. Los worktrees viejos de la fase C (`c-*`, `b4-*`) ya no hacen falta.

**Memoria**: cuatro frentes con Blender a la vez más Unity ya es el límite de los 16 GB.

---

## 5a. Ramas de la fase C3

Seis frentes `c3/*` (locales) sobre `76be027`, integrados con `--no-ff` y sin conflictos en `c3/integration`. Qué trajo cada uno, sus contratos, lo que re-midió la integración (FBX, GUID, generate_assets en seco, simulaciones) y la lista de pruebas en Play para el lead están en [`handoff/reportes/c3_reports.md`](handoff/reportes/c3_reports.md).

| Rama | Qué trajo |
|---|---|
| `c3/goro-anim` | Gorō: embestida en cuadros del clip sin patinar, variantes en el lugar contra la barrera, armadura parda, balance recalibrado con el bot de Unity. |
| `c3/kaito-snaps` | Kaito: sin tirones de un cuadro (lint de todo el cuerpo), el Corte final con las dos manos, el chiburi del remate a x1. |
| `c3/chikuo-feel` | Chikuō: el desvío con la palma, el paso del viento que sigue a Kaito y pasa al costado, el saco que se desliza. |
| `c3/kokuyo-act3` | Kokuyō y Mizuchi: sustento por etapa, el eclipse de la sombra, reintento por acto, la barra del acto, la luna sin cortes. |
| `c3/culling-dyn` | `ZoneCulling.AddDynamic`: lo creado después del armado también se apaga y se pausa fuera de cuadro. |
| `c3/docs-saves` | `reportes/c2_reports.md` y una partida de prueba antes de cada jefe. |

---

## 5b. La fase C (vieja, ya integrada en C2)

Lo que sigue es cómo había quedado la fase C antes de C2; su trabajo ya lo retomaron los frentes `c2/*`. Queda por referencia.

| Worktree (`.claude/worktrees/…`) | Rama | Qué hay |
|---|---|---|
| `c-ui-hud` | `c/ui-hud` | Lo más avanzado (27 archivos): relleno de vida nuevo (`Health_Fill.png`), ojo del dragón nuevo (`DragonEye.png`), sprites `BrushBanner`, `Fude` (pincel), `IconKnot`/`Hanko_IconKnot` (¿indicador de guardado?), `ScrollPaper`/`ScrollRod`, `Tools/UI/hud_bandana.py`, cambios en UIManager*, UIFactory, UISprites, Areas.cs, TimingCoach y `build_ui_art.py`. **Revisar, compilar y probar antes de usar.** |
| `c-bamboo-master` | `c/bamboo-master` | `Tools/Blender/bosses/bamboo_master/` (inicio del modelo). Puede haber conceptos de Higgsfield en el scratchpad viejo (`…/scratchpad/c/bamboo-master/`). |
| `c-kaito-anim` | `c/kaito-anim` | Cambios chicos en `kaito_rig.py` y `build_kaito.py` (¿muñecas?). |
| `c-team-a` | `c/team-a` | `team_rig.py` + `team_limbs.py` nuevo (¿muñecas o esqueleto?). |
| `c-team-b` | `c/team-b` | `team_hands.py` nuevo. |
| `c-ui-map-controls` | `c/ui-map-controls` | `Tools/UI/build_world_map.py`, `world_map_data.py` (inicio del mapa). |
| `c-music` | `c/music` | Nada commiteado. |
| `b4-*` | `b4/*` | Vacíos: se pueden borrar. |

Para seguir un frente: entrá a su worktree, mirá `git show --stat HEAD`, decidí qué sirve y seguí.

Si relanzás agentes: usá el script `Docs/handoff/fase_c_frentes_workflow.js` (pasá el script **en línea** con `args: { only: ["..."], limit: 4 }`). Ya contempla que el worktree exista y que tenga que retomar.

---

## 6. Plan sugerido (orden)

1. **Unity sano**: abrir y verificar que no haya errores ni enemigos invisibles. La partida del usuario está en `Docs/handoff/partidas`.
2. **Arreglos chicos de alto impacto** (de a uno, probando en Unity y pusheando a main):
   * Cartel trabado (18), "Victoria" (19), dash sin espíritu (28), anillo de combate (29).
   * Silueta amarilla (20), trazo corto (21), guiones e indicador de guardado (22).
   * HUD de la bandana y ojo del dragón (24): partir del WIP `c/ui-hud`.
3. **En paralelo, los frentes grandes con agentes** (de a cuatro):
   * Jefe del bambú (8).
   * Gorō con fase 2 (9).
   * Animación de Kaito (2, 3, 4, 7, 13, 15 y 12 parte animación).
   * Ninjas y sumo (3, 5, 6).
   * Abuelo (1, 6).
   * Kokuyō (11).
   * Mundo e historia (13 a 17).
   * Mapa y controles (25, 26).
   * Música: investigación y sistema (30).
4. Lista de música para el usuario y aprobación; después integrar.
5. **Balance final** con el bot "bueno" y "promedio" (vida, ritmo) hasta que la partida dure ~1 h. Para cada jefe, medí la duración, las muertes y la fase a la que se llega.
6. Siempre probar en Unity con capturas, mirarlas críticamente (¿se ve el cuerpo de cada enemigo? ¿tapa algo la interfaz?), restaurar la partida y pushear.

---

## 7. Críticas abiertas que vale tener presentes

* La hoja del ninja negro apenas se ve desde arriba: hoy el aviso depende del brillo del arma.
* Los números de vida se ajustaron contra el bot experto, que es sobrehumano; con una persona las peleas duran más.
* Las presentaciones de los jefes ponían el título encima de la cabeza del jefe en algunas tomas (C2: ahora va en el tercio de abajo, `ShowBossTitle`; verificarlo en Play).
* El pozo de la cascada quedó bien, pero los basaltos claros todavía se pueden leer como hielo.
* Otros detalles:
  * Los cuatro de esta lista (el abuelo atado, el rezo que no se leía, el arma de Gorō en el cuerpo y el rodeo hacia adelante) se hicieron en C2; falta verlos en Play.

---

## 8. Material de referencia copiado al repo (`Docs/handoff/`)

* `diseno/`:
  * `design_doc_nindo.md`: resumen del documento de diseño del equipo, del Drive.
  * `judge_water.json`: diseño final de Mizuchi. `judge_final.json`: diseño final de Kokuyō (en los dos, la clave `final` tiene el moveset, las fases y la implementación).
  * `audit_*.json`: auditorías de animación (gramática de avisos ANIM-02 y plan), combate, gamefeel, modelos y UI.
  * `concept_*.json`: conceptos alternativos.
* `reportes/b2_final_reports.md`, `reportes/b3_reports.md`, `reportes/c2_reports.md` y `reportes/c3_reports.md`: qué construyó cada frente, sus APIs, los pendientes y las pruebas en Play que proponían.
* `conceptos/*.jpg`: arte conceptual (cascada, Mizuchi fase 1 y 2, Kokuyō, variantes).
* `fase_c_frentes_workflow.js`: los nueve frentes de la fase C con todos los detalles; reusable.
* `partidas/`: la partida actual del usuario y las de prueba (una antes de cada jefe, la tarde antes de Kokuyō y la del final a medias), con su `README.md`.
