# Fase C2: lo que dejó cada frente

Resumen de los informes de los doce frentes de la fase C2 (`c2/*`), de la integración (`c2/integration`) y de la ronda
de arreglos de huecos que vino después. Todo eso está en main desde `76be027`. El lead lo probó en Unity: los jefes y
los sistemas andan. Arregló que Kaito se caía al agua en la plataforma de Mizuchi (rescate en `BossArena`) y está
arreglando el grito del rezo que quedaba en pantalla después de la cinemática.

Cada frente tiene tres partes:

* **Contratos y API**: los nombres en los que se apoya el resto del código. Es lo que hay en `76be027`; si la
  integración lo cambió, está marcado.
* **Chequeos**: los lints y simulaciones que lo validaron fuera de Unity.
* **En Play**: la lista para probar en Unity.

Ninguno de los frentes pudo abrir Unity: todo lo de "En Play" lo tiene que mirar el lead. Para llegar rápido a cada
jefe están las partidas de [`../partidas/README.md`](../partidas/README.md).

Fuentes, en el scratchpad de la sesión del lead (no están en el repo y se pueden perder):
`C:/Users/FELIPE~1/AppData/Local/Temp/claude/C--Users-Felipe-Doval-Documents-Github-local-repostory-Nindo--claude-worktrees-handoff-proxima-sesion-77ccb6/273c68c4-a0ed-48e1-a37c-cccb9fba0d67/scratchpad/`.

* `c2/state/<frente>.json`: los informes de cada etapa, las revisiones y los arreglos.
* `c3/c2_open_findings.md`: la integración, los huecos y lo que siguió abierto.

Los frentes goro, grandpa y ninja-sumo tuvieron rondas más que no quedaron en esos `.json`. Lo de esas rondas sale de
sus commits: `b0ce603` y `d34c813` (goro), `f693e15` y `d205895` (grandpa), `d0dbac3`, `bd07668` y `8a3ac2f`
(ninja-sumo).

---

## team-rig: el rig del equipo y Blender 5.2

**Contratos y API**
* Rig para autores de clips: `Tools/Blender/anim/README_team_rig.md`. Build:
  `blender -b --factory-startup --python Tools/Blender/anim/build_team_anims.py -- <ninja|sumo|goro|grandpa> [--export] [--only A,B] [--renders DIR]`.
  Los clips van en `team_clips_<personaje>.py`, con `T.TeamClip(name, frames, keys, loop, timing=..., travel=..., feet=...)`.
* Marco de autoría:
  * Metros de juego, con el origen en el piso bajo el transform.
  * Adelante = -Y, la izquierda del personaje = +X, arriba = +Z.
  * `_r`/`_l` son siempre del lado del personaje. En el ninja, el sumo y el abuelo `.L` es la mano **derecha**.
* Esqueleto de juego FK: en el sumo, Gorō, el abuelo y el ninja del secuestro, manos y pies cuelgan del antebrazo y de la
  canilla. `BaseM` (el martillo) es hijo de `Mano.R`. Nombres, poses de bind y GUIDs no cambiaron.
* Segundo esqueleto: `clip.partner` anima al ninja del secuestro (huesos `.001`, malla `Cube`) junto al abuelo (`Cuerpo`).
  `team_rig.drop_kid` limpia sus huesos antes de resolverlo.
* `team_limbs.ArmSolver`, en todos los brazos de los cuatro personajes:
  * El codo gira y el puño rueda en el mango.
  * El antebrazo se lleva el 85 % de la torsión (pronación de -85 a 90°).
  * Una mano libre que no entra se endereza al 85 % del límite (flexión 75, extensión 65, radial 25, cubital 38).
* `take_floor_fix`: pies y martillo sobre el piso en las tomas re-resueltas. `team_clips_ninja.EDGE_START`: los golpes
  arrancan con el filo del loop.
* Hoja del ninja: acero claro `#d3dae3`, 30 % más ancha, lomo oscuro con el material `Lomo` (`#3b3f47`). El slot `Glint`
  sigue en el filo (CharacterGlint).
* `Tools/Blender/bl_compat.py`: las diferencias de la API de Blender 5.2. Todos los pipelines pasan por ahí.

**Chequeos**
* `build_team_anims` falla si pasa alguna de estas:
  * Una mano o un pie no llega.
  * Un pie apoyado se mueve más de 2 cm (salvo `slide_ok`) o patina sobre la malla.
  * El cuerpo o el arma entran al piso.
  * La costura de un loop pasa de 1°.
  * El contacto o el apex no coinciden con el `Hit()` de `EnemyArchetypes`.
  * Cadenas que no empalman, matrices espejadas.
  * La muñeca pasa de 1 (en el mango, aviso hasta 1.35).
  * El arma gira más de 12° en el aviso.
  * El solver salta más de 35° (aviso hasta 55).
* `verify_fbx`: mismos padres que el modelo, rutas bajo `Armature/`, el nodo Armature sin animar y `preserveHierarchy 1`.
  `blade_checks` avisa si la cara de la hoja no mira a la cámara del juego.
* Muñecas, del peor cuadro de cada clip: de 2 a 7.7 de exceso a 1.0 o menos. Al cerrar, los cuatro builds salen sin
  fallas (avisos: ninja 23, Gorō 15, sumo 9, abuelo 0).

**En Play**
1. Después de reimportar, mirar un enemigo de cada tipo: ninja, élite y variantes de zona, sumo, Gorō, el abuelo y el
   ninja del secuestro. Ninguno invisible, agrandado ni en el origen. Las manos no se doblan sobre el antebrazo en Idle,
   Walk ni Run.
2. Ninja de noche, desde la cámara de juego: la hoja clara con lomo oscuro, y el filo destella antes de cada golpe y en
   el parry. En Attack2 la cara clara se lee en el aviso (f5-7) y en el contacto (f10).
3. Ninja, de Idle a Attack2, Attack3, Thrust y las reacciones: el filo rueda dentro del clip, sin torcer la muñeca al
   arrancar. Juzgar Idle → Attack1 y la vuelta de cada golpe a Idle, que todavía giran el antebrazo ~57° en el fundido
   de 0.08 s (V-TR-5, abierto).
4. Ninja persiguiendo (Run): la mano libre bombea sin aletear.
5. Sumo y variantes:
   * Muñecas y tobillos no se sueltan en los fundidos ni en la mezcla Walk/Run.
   * En los movimientos de `SumoPoser` los pies quedan planos al bajar la cadera.
6. Gorō:
   * El martillo no se escapa de la mano en los fundidos.
   * Heavy sube sin saltos de brazo (f0-12) y cae derecho adelante, con el puño cerrado en el mango.
   * En la presentación la cabeza del martillo apoya en el piso en los dos golpes (antes se hundía 22 cm) y el pie de
     atrás no entra al piso.
7. Abuelo (Idle, Walk, Bound, Freed) y el ninja del secuestro agachado, sin muñecas rotas.
8. Bot por el dojo, Gorō y las zonas del sumo: nada en la consola de `SumoPoser: el esqueleto ... no es el del sumo` ni
   de kits faltantes.

---

## kaito-anim: Kaito

**Contratos y API** (30 fps, segundos a velocidad 1)
* `WakeUp` 3.6 s: stir f28, see f80, stand f93.
* `PrayIncense` 6.27 s: katana_down f28, incense_take 70, incense_light 88, incense_place 116, palms 128, katana_up 159,
  rise 166. La katana queda en el piso a su derecha: empuñadura a 0.35 m a la derecha y 0.16 adelante, punta a 0.79 y
  0.92 (`timing.katana_floor_m`).
* `PrayQuick` 2.33 s: kneel 11, katana_down 21, palms 28, katana_up 49, rise 57. También deja la katana en el piso.
* `BandanaPower` 2.5 s: glow f14, release f40. La palma izquierda en la suelta está en (-0.10, 0.73, 0.47) m.
* `EndingTurn` 2.8 s: turned f39, ribbon f50, offer f61. Arranca de espaldas a Kokuyō y 0.55 m detrás del transform
  (`KaitoTimings.EndingTurnShift`).
* `HitBack`, `HitLeft`, `HitRight` 0.3667 s; `RunStop` y `RunStopL` 0.5333 s; `RunStopReach` y `RunStopLReach`
  0.5667 s; `Death` 1.6 s.
* Zanshin: alrededor de 1 s de pose final.
  * Remate cinemático: f55-86 con `CameraDirector.PlayZanshinShot`.
  * Corte del Viento: de 0.54 a 1.5 s. Torbellino: de 0.8 a 1.8 s.
  * Los últimos 0.25 s se cortan con el stick, un ataque, el dash o el parry. Después, el resto del clip es un gesto
    (`StartGesture`).
* Momentos de los clips: una sola tabla, `Story/KaitoTimings.cs`, con `KaitoTimings.Event(state, name, fallback)`.
  * La genera `Tools/Unity/kaito_timings.py` desde `Animations teo/kaitooo.fbx.json`, y la corre también
    `generate_assets.kaito_assets()`.
  * La integración (CODE-1) borró `KaitoClipEvents.cs` y los helpers duplicados: las escenas usan `anim.HasState` y
    `anim.Length`.
* `PlayerController.Anim`:
  * `HitFrom`: hasta 50° es Hit (gira), desde 130° HitBack y, entre medio, Left o Right. Sin el estado, cae en `Hit`.
  * `TryRunStop`: elige una de las cuatro frenadas por la fase de la carrera (8/24, 20/24, 2/24, 14/24). Debounce
    0.04 s, `RunStopMaxWait` 0.16 s, `RunStopLead`.
  * `LocomotionCadence` y `GaitSpeed`, con histéresis 2.1/1.9 y 4.4/4.2 m/s.
  * `CharacterAnimator.LocomotionParam`. Umbrales del blend: 0 / 1.2 / 3.4 / 6.2 m/s ÷ runSpeed.
* `kaito_rig`: `knee_guide_r/l` con `knee_at_r/l`, `hand_l_relax`, `arm_space_l`, el timing `burst` y el helper `swung()`.
* Bandana: quedan solo las colas del kit (`Kit_kaito_bandana.fbx` con SpringChain). El nudo del cuerpo es un moño, con
  todos sus vértices en la cabeza (`kaito_rig.bandana_weights`, del arreglo de huecos A5).

**Chequeos**
* `Tools/Blender/anim/kaito/build_kaito.py` revisa el export:
  * 65 de 65 nodos, la pose de bind idéntica (0.0019°), una sola toma `Scene` y el FBX re-importado igual al horneado
    (0.00 cm).
  * Pies apoyados por debajo de 2 cm (`SKATE_RUN_CM`) y muñecas con los límites de `team_limbs`.
  * Los tirones de un cuadro salen como aviso: 0 FAIL y 64 WARN al cerrar.
* `runstop_sim.py`, sobre 48 fases: en el cambio, las piernas difieren 10.5° como mucho y el freno llega 68 ms después
  de soltar el stick, en promedio.
* Simulación de la cadencia: la patinada del pie apoyado bajó de 36 cm a 0.6-2 cm por ciclo.

**En Play**
1. Idle, caminar, trotar y correr subiendo el stick despacio: el pie apoyado no patina, tampoco entre zonas (2 y
   4.3 m/s). Las muñecas se ven derechas en idle, en la carrera y en Attack1 y Attack2.
2. Frenada:
   * Correr a fondo y soltar unas 20 veces en momentos al azar: frena ~0.07 s después, sin tirón de piernas ni talón que
     patine.
   * Repetir al 75 % del stick y con un cambio de dirección del teclado: el debounce evita una frenada falsa.
   * Contra una pared, frena antes de 0.16 s.
   * Con un objetivo fijado no hay RunStop.
3. Golpes de frente, costados y espalda: Hit (gira), HitLeft y HitRight y HitBack (no gira). El pesado sigue en HitHeavy.
4. Morir: cae de rodillas y boca abajo con peso, en 1.6 s, y suelta la katana. Las piernas se estiran cuando apoya el
   pecho, sin pie que patine, y el nudo no muestra el cuerno amarillo.
5. Dash y ataque: Attack1 sale con un fundido de 0.1 s. Parry y ataque temprano: la réplica espera la pose de carga, con
   el parry normal y con el perfecto.
6. Remates y habilidades:
   * Remate cinemático (élite, sumo, jefe o el último enemigo de la pelea): corte al plano frontal y ~1 s de pose quieta.
     Kaito no recibe daño y los enemigos esperan. Mover el stick corta el chiburi.
   * Corte del Viento y Torbellino: ~1 s de pose, cancelable al final.
   * El puño izquierdo queda quieto en la cadera.
7. Bandana: un solo par de colas, con física, que nacen del nudo. En el prólogo está oculta hasta que Kaito la tiene.
   Probar también `BandanaGlow` y `SetBandana` (tapada o con pelo).
8. Rezos: la katana rueda plana en el aire y queda quieta en el piso. En el rezo largo la rodilla derecha baja y sube con
   el pie hacia el costado. El incienso y las palmas siguen alineados.
9. WakeUp: el paso de cuatro patas a una rodilla sin tirón del pie.
10. Furia: la cadencia de la carrera no acelera los pasos (es a propósito); los golpes sí se aceleran.

Abierto:
* En Attack3 la mano derecha gira 178° en f2-3 (V-KA-4). Necesita una decisión: mover el contacto, terminar Attack2 en
  pronación o un remate de revés.
* Los tirones de un cuadro (§4b).
* El Finisher f55 queda en el tope radial.
* La frenada agrega ~0.4 m de deslizamiento: se afina con `RunStopMaxWait` y `RunStopLead`.

---

## ninja-sumo: idles de ambiente, rodeo, golpes y embestidas

**Contratos y API**
* Ninja:
  * `IdleMeditate`, loop de 4 s: sentado en `rock_small_a` a escala (1.3, 1.32, 1.12), 0.72 m detrás, con la cara de
    arriba a 0.40 m.
  * `AmbientAlert` 1.4667 s: cae y puede girar a los 0.667 s.
  * `IdleSparA` e `IdleSparB`, loops de 3.2 s en sincronía: chocan en 15/96 y 63/96, a 1.70 m uno del otro.
  * `IdleInspect`, loop de 4 s con el chiburi en f77. `IdleStretch` es nuevo.
  * `StrafeL` y `StrafeR`: 0.3333 s a 2 m/s. `WalkBack` 0.4667 s.
  * `Attack3` 1.2 s: salto de 0.45 m, apex 0.3056, contacto 0.5833.
  * `Whirl` 1.2 s: 470° y un salto de 0.30 m. `Leap` 1.6 s: arco de 1.0 m. `HopBack`: el repliegue.
* Sumo:
  * `IdleSleep`, loop de 4 s, con el ronquido en 52/120.
  * `AmbientAlert` 2.4 s: gira a los 1.833 s.
  * `IdleShiko`, loop de 5 s, con los pisotones en 47 y 122/150.
  * `StrafeL` y `StrafeR` 0.4 s a 1.6 m/s, `WalkBack` 0.6667 s, `Morote` 1.2 s.
  * `Run` 0.4667 s a 3.4 m/s, erguida. `HopSideR` y `HopSideL`: la finta.
* `EnemyArchetypes`:
  * Constantes `NinjaApex3` 0.3056, `NinjaApexWhirl` 0.2778, `NinjaApexLeap` 0.2917, `SumoApexMorote` 0.3333.
  * `AttackDef.fallback`: si el controller no tiene el clip nuevo, vuelve al viejo con sus tiempos.
  * `lungeFrom`: la embestida en cuadros del clip (`team_moves.clip_lunge_travel`).
  * `EnemyConfig.lungeSlack`: ninja 0.15 m, sumo 0.35 m. El modelo cubre lo que corta el imán y se lo devuelve al
    transform.
  * `StepTimeline.creepIn`.
* `EnemyAmbient`:
  * `Setup(enc, spawns, members)`, llamado desde `Encounter.SpawnAll`. La actividad sale de un hash FNV del id del
    encuentro: siempre la misma.
  * `enemy.Ambient`: `HoldsPose`, `Waking`, `CanTurn`, `Current` (Meditate, Spar, Inspect, Sleep, Shiko, Stretch),
    `Wake()`, `Hurry()`, `Restart()`, `Resume()` y `Release()`.
  * Notan a Kaito de cerca: 7 m, o 5 m dormidos. Un golpe los despierta en el acto y apura el sobresalto ×2.2.
  * `intro` no tiene ambiente y el sumo del encuentro `sumo` hace siempre el shiko.
  * Corren en `Idle`: por eso ZoneCulling los duerme con su campamento.
* `Enemy.Locomotion.cs`: `InLocomotionPose`, `ModelNudge` y el rodeo en un blend 2D Simple Directional, dentro del 1D
  de Speed (`CharacterAnimator.HasDirectional` / `SetDirectional`). Los jefes quedan afuera.

**Chequeos**
* `build_team_anims` mide `variant_skate_cm`, `magnet_skate_cm`, `magnet_curve_cm`, `replay_skate` (con el reloj del
  juego) y `hop_arc`.
* `fbx_skate.py` re-importa el FBX y repasa cada embestida y cada salto con el reloj del C#. Peor suela apoyada: ninja
  1.8 cm (HopBack), sumo 2.0 cm.
* **Ese lint de embestida es el que hoy hace fallar a GoroAnims** (§4b).
* Simulaciones en el scratch:
  * `sim_assign`: qué hace cada campamento.
  * `sim_gait`: el rodeo.
  * `sim_magnet`, Monte Carlo del imán: la bofetada patina 1.5 cm en promedio (era 5.1).
* `ambient_review.py` y `ambient_kits.py`: hojas con la cámara del juego, con la roca y la pareja medidas.

**En Play**
1. Ningún ninja ni sumo invisible: el cuerpo junto a su barra.
2. Ambiente, con `prueba_tarde_cp_lake_falls.json` (que tiene campamentos vivos) o sacando flags `enc_*`. Listar:
   `foreach (var a in Object.FindObjectsByType<Nindo.EnemyAmbient>(FindObjectsSortMode.None)) Debug.Log($"[Nindo] amb {a.transform.parent.name} {a.Current} hold={a.HoldsPose}")`.
   * El que medita está sobre una roca, sin atravesarla.
   * La pareja que practica queda horizontal en pantalla y las hojas chocan en sincronía, con chispa y un clang suave.
   * El que mira el filo lo sacude cada 4 s.
3. Acercarse a un campamento:
   * Las reacciones salen escalonadas (~0.3 s).
   * El que medita se sobresalta, se apoya en la roca, salta adelante y recién parado gira.
   * Nadie ataca antes de estar en guardia (~1.5 s).
   * Pegarle de atrás a uno sentado: recibe daño y se apura, sin Hit ni retroceso.
4. Morir (o `Encounter.Get("lake1").ResetEncounter()`): todos vuelven a su pose y la pareja queda sincronizada.
5. mountain1:
   * El sumo duerme, con el ronquido cada ~4 s, y despierta lento.
   * No gira hasta estar parado.
   * El kit de piel no atraviesa el piso.
6. Encuentro `sumo`: el shiko tira polvo y la provocación (Spotted) no da un salto grande.
7. Rodeo, con fields1 vivo:
   * Los ninjas rodean de costado, con los pies cruzados y el derecho adelante.
   * Cambian de ciclo ~1 vez por segundo sin saltos.
   * Retroceden caminando si Kaito se les acerca.
   * Log por cuadro con `e.Anim.Current` y la velocidad del agente: StrafeL, StrafeR, WalkBack o Locomotion.
8. Sumo:
   * La bofetada avisa con la mano arriba de la cabeza.
   * Pega con el brazo estirado a la altura del hombro ~0.13 s, con el brillo en esa mano.
   * La carrera va erguida.
9. Imán: dejar que el sumo pegue con Kaito pegado a él.
   * `ModelNudge` llega hasta 0.35 m (ninja 0.15) y vuelve a 0.
   * El pie de atrás no patina y la panza no atraviesa a Kaito.
10. lake1 con `bot on bueno`:
    * El remolino gira en el aire, con los pies fuera del piso, y pega cuando la hoja vuelve por delante.
    * El arpón no patina al caer.
    * El Attack3 es un salto visible.
11. bamboo1: desde 4-6.6 m el ninja salta en un arco alto (~1 m) y corta al bajar, sin deslizarse antes ni levantarse
    dos veces.
12. mountain1: el Rompeguardia de los élite se sigue leyendo con el salto nuevo.
13. Morote: no hay sumo del lago en el mapa. Probarlo con `EnemyFactory.Spawn("sumo", ...)` cerca de (112, 0) y mirar
    el patrón 'Oleaje'.
14. Kokuyō sigue cambiando su propio StrafeL/R.

Abierto:
* Los movimientos del sumo del lago y del bambú no se usan (Morote): §4b.
* Morote con Kaito pegado patina 42 cm.
* Balance: el T del Attack3 pasó de 0.59 a 0.64 s y el del salto del bambú de 0.8 a 0.97 s.

---

## goro: barra falsa, armadura de roca y fase 2

**Contratos y API**
* `Enemies/Bosses/GoroBoss.cs`:
  * Fases 0 y 1 son la primera barra: 1000 de vida (`EnemyArchetypes.Goro`), con el daño de Gorō
    ×`firstBarDamageScale` 0.5.
  * La fase 2 es la armada: `armoredHealth` 1600, con el daño ×`armoredDamageScale` 0.4.
  * No tiene el enfurecido genérico del 50 %.
* La secuencia: `FakeDefeat`, silencio, `ArmorRise` (cada roca se clava en el cuadro de su golpe), el cartel "Gorō / La
  Montaña Despierta" y la fase 2, con +40 de vida y +30 de Espíritu para Kaito.
* La armadura:
  * Rebota los cortes en las ventanas `armor` del sidecar.
  * Se le cae en tres tramos, que curan a Kaito.
* Reintento: arranca armado si ya vio la armadura (`goro_armor_seen`), y desde la segunda vez la cinemática va rápida.
  Debug: `DebugSetHealth01(f)` y `DebugArmor()`.
* `GoroAvalanche.cs` (`goro_avalanche_seen`):
  * Olas de 2 o 3 carriles, con pasillos de 2.8-3.6 m.
  * Siempre arranca dentro de la cámara y de la barrera, con al menos 1.35 s entre el carril y el golpe.
* `GoroArmor.cs` mueve los huesos `Acc_Roca_<Pieza>` del kit `goro_armor` (`CharacterKits.Attach(model, "goro_armor")`).
  El vuelo de cada pieza está en `Kit_goro_armor.fbx.json`.
* Estados (`GoroAnims.fbx.json`; los cuadros en `GoroTimings.cs`, generado):
  * Idle 3.2, Intro 2.8, FakeDefeat 2.6, ArmorRise 7.0.
  * Combo1 1.6, Combo3 1.5667, Heavy 2.1333.
  * Combo1B 1.9667, Combo2B, Combo3B 1.9, SlamWave 2.1333, AvalancheSummon 3.0.
  * Parried y ParriedPerfect, con `parriedRecoil` 0.5 s.
  * FakeDefeat termina justo en la pose de arranque de ArmorRise: van con fundido 0.
* Música: `FakeDefeat` llama `SilenceBossMusic(0.4f, true)` y `ArmorRise` llama `SetBossMusicPhase(2, lead + RiseStand/sp)`,
  para que los tambores caigan cuando se para.

**Chequeos**
* `Tools/Blender/bosses/goro/goro_checks.py`:
  * El martillo contra cascos del cuerpo y contra cada roca, y las rocas contra el piso.
  * El giro del martillo por cuadro.
  * El recorrido de cada mano por cuadro del juego: como mucho 0.5 m fuera del golpe.
* `goro_review.py` y `goro_rise_review.py`: hojas con la cámara del juego.
* `Tools/Dev/goro_avalanche_check.py`: 0 olas sin escape, aviso mínimo 1.35 s.
* `Tools/Dev/goro_fight_sim.py`, 400 corridas: bueno 3.4 min simulados, promedio 4.8 con 1.45 muertes.
* **Hoy `build_team_anims.py -- goro` falla 7 chequeos**: la embestida patina 6-16 cm con el reloj del juego y el
  martillo entra al piso en SlamWave y Combo2. GoroAnims.fbx no se puede re-exportar hasta arreglarlo (§4b).

**En Play** (`prueba_goro.json`)
1. Reimportar. Gorō tiene el cuerpo visible junto a su barra, con la escala de la raíz entre 0.5 y 1. En Idle apoya la
   cabeza del martillo en el piso.
2. En el Animator:
   * Combo1 1.6, Combo3 1.57, Heavy 2.13, Combo1B 1.97, Combo3B 1.9 y AvalancheSummon 3.0.
   * `anim.Length("Combo1")` da 1.6, no 1.4: la fila de NindoContent la arregló la integración (`8d7cac0`).
3. Barra falsa y música: `var g = Object.FindFirstObjectByType<Nindo.GoroBoss>(); g.DebugSetHealth01(0.02f);` y un golpe.
   * Suena el cierre del tema en el próximo tiempo.
   * Silencio con viento, sin la música de exploración.
   * Las rocas vuelan con la frase del koto y los tambores caen cuando se para, junto con el cartel.
   * `Debug.Log(Nindo.Game.Audio.MusicState)` muestra boss_goro 1/2 y después 2/2, sin 'silencio'.
   * En el reintento (rápido), el mismo orden. `g.DebugArmor()`, sin la cinemática, también pasa a la fase 2.
4. ArmorRise: en el plano del rugido entra la figura entera con el martillo arriba. La armadura se lee como roca parda
   oscura con brasa, no como hielo.
5. Combos (Combo1, 2 y 3, las variantes B y SlamWave): mirar si los pies apoyados patinan en la embestida. El lint dice
   6-16 cm.
6. Parried: el martillo rebota y cae, sin dar la vuelta por arriba. En Combo2 y Heavy el mango no atraviesa el torso, y
   los golpes pegan a ~3.7 m.
7. Avalancha:
   * Carriles rojos que bajan desde arriba de la pantalla, siempre con un pasillo libre.
   * Pegado a Gorō no se es inmune.
8. Morir armado: el reintento arranca armado.
9. `bot on bueno` y `bot on promedio`: leer la línea de PlayClock.

---

## grandpa: el abuelo

**Contratos y API**
* Estados de `Grandpa.controller`, que usan los NPC `grandpa` y `kidnap`:
  * `Idle` 2.5 s (loop) y `Walk` 0.8 s (loop, a 0.8 m/s). `KidnapWait`.
  * `Kidnap` 1.9 s: agarra en f17, se sienta en f27 y el arrastre arranca en f47. Su último cuadro es Dragged f0.
  * `Dragged` 2.6667 s, loop a 0.8 m/s: el tirón en f20-40, la mano hacia Kaito en f40-60 y se rinde en f60-80.
  * `Bound` 6 s, en seiza y tranquilo. `BoundStruggle` lo dispara el NPC cada 4-9 s.
  * `Freed` 3.6 s: parado en f98, y f108 es Idle f0.
* `Story/NPC.cs`:
  * `Kidnap(exit)`, `Drag(target)`, `Hold(state)` y `AwaitKidnap()`.
  * `KneelBound()`: lo pone 0.2 m adelante del marcador y evalúa el Animator con `AlwaysAnimate`.
  * Constantes de estado (`KidnapState`, `DraggedState`, `BoundState`, `BoundStruggleState`, `FreedState`, `WalkState`),
    `DragSpeed` 0.8 y `KneelForward` 0.2.
* `ShadowRopes.Bind(post, captive, parent)` arma tres vueltas con los huesos de Bound. `Drop(0.55 s)` las hace caer.

**Chequeos**
* `build_team_anims grandpa`: sin fallas ni avisos. Tiene el chequeo nuevo de la cadera sin tirones: aviso desde 6 cm y
  `hip_acc_cm` en el timing.
* `grandpa_fbx_check.py` mide el FBX como lo lee Unity: los brazos, el agarre a dos manos y los dedos.
* `grandpa_shots.py` usa las cámaras de las escenas: los cuerpos nunca quedan a menos de 10.4 cm.
* Los empalmes dan 0.00 cm: Kidnap a Dragged, los loops, Bound a Freed y Freed a Idle.

**En Play**
1. Después del refresh, el controller tiene Idle, KidnapWait, Kidnap, Walk, Dragged, Bound, BoundStruggle y Freed.
   Ningún NPC avisa que "no tiene el estado".
2. Prólogo de una partida nueva:
   * El ninja corre, agarra la muñeca y el abuelo cae sentado, con polvo y golpe. Después viene el plano de costado.
   * Los brazos van tirantes, las muñecas trabadas y los talones levantan polvo.
   * Los pies del ninja no patinan a 0.8 m/s.
   * Siguen hacia `kidnap_exit` hasta el humo.
3. Prueba rápida:
   `var p = Nindo.Game.Player.transform; var f = p.forward; var n = Nindo.NPC.Spawn("kidnap", p.position + f * 4f, UnityEngine.Quaternion.LookRotation(f), null); n.Hold(Nindo.NPC.KidnapState);`
   y un momento después `n.Kidnap(p.position + f * 30f);`.
4. Bosque: sacar `forest_seen` **y** `trig_forest_reveal`, y pasar por el disparador. Los árboles no tapan la cámara de
   costado (local 5.5, 3.6, -5). Si la tapan, volver al offset de mundo (-5, 4.5, -7).
5. Arena de Kokuyō (`prueba_kokuyo.json`):
   * El abuelo está en seiza 0.2 m delante del poste, nunca dentro de la base.
   * Las cuerdas pasan por las muñecas, los codos y el pecho, sin cruzarle la cara ni el sombrero, y las puntas no
     entran al piso.
   * Morir y reintentar: sigue atado.
6. Final:
   * Caen las cuerdas y viene Freed: los brazos, el frotado de las muñecas, la mirada y se para con las manos en las
     rodillas.
   * Después Walk, sin patinar en el cambio.

Abierto:
* Atado se lee como una figura más baja: la túnica tapa las rodillas.
* Desde arriba, el sombrero tapa el frotado de las muñecas.
* Mientras Kaito despierta, el abuelo queda quieto en Kidnap f0.

---

## bamboo-master: Chikuō, el Maestro del Bambú

**Contratos y API**
* El personaje:
  * Es `bamboo_master`: `BambooMaster.fbx` (GUID `191c5633648e5611746e668f0421a7c7`, controller
    `00038a893675a4c699be298472f4a7fd`), de 2.672 m.
  * El arquetipo y el bossId siguen siendo `ozeki` (partidas, flags, `SealId.Bambu`). `CharacterFactory` crea
    `BambooMasterBoss`.
  * Título 'Chikuō' / 'El Maestro del Bambú'. Después 'Las Dos Manos' y 'El Bastón de Bambú' (`UIManager.BossRetitled`).
  * maxHealth 2000 (el contrato decía ~1400), con pisos de fase al 66 % y al 33 %.
  * Presentación propia, con su bandera `boss_seen_chikuo`.
* 107 clips. Los de locomoción y los golpes tienen variantes `_P2` y `_P3` con los mismos cuadros: Palm, ChopPalm,
  CraneKick, LeapKick, Guard (la grulla blanca), GuardHit, Counter, CounterStrike, Taunt, Stance, TwinPalm, SpinKick,
  Sweep, QiWave, DashStrike, BackHop, BackHop_P2, BackHop_P3, PhaseCoat, PhaseStaff, Defeat, Meditate y SeatedBow.
  * Los tiempos están en `BambooMasterTimings.cs`, generado del sidecar.
  * Mallas: `Master_Body`, `Master_Robe`, `Master_RobeThrown` y `Master_Staff`.
  * Brillos por material: `Master_GlintHandR/L`, `FootR/L`, `Staff` y `Eyes`. Dorado se para, rojo se esquiva.
* La pelea:
  * Los cortes sueltos rebotan (`BounceWindow` 0.55 s).
  * La postura del bambú (manos de jade) contraataca, y parar ese contraataque en perfecto lo arrodilla.
  * Paso del Viento: carril fijo, estiramiento de 0.1 a 1.4, y si Kaito dashea lo atraviesa.
  * Grulla Voladora: directa desde 2.5 m o después de un BackHop.
  * La réplica de Kaito: 2 cortes después de un parry normal, 3 después de uno perfecto. Las habilidades cuentan como
    golpes pesados contra su guardia.
* Música: `musicKey 'boss_bamboo'`.
  * La fase 2 entra en el `CoatOff` de PhaseCoat y la 3 en el `StaffCatch` de PhaseStaff.
  * Un reintento en la fase 2 o 3 llama `SetBossMusicPhase(n)` en el mismo cuadro.
* Hooks en `Enemy`: `KnockMeters(in DamageInfo, float)` y `DeathBurst`. AutoPilot: `chikuo fase N`.
* Textos: 'ozeki_intro', 'bamboo_defeat', `ChikuoLine(fase2|fase3|paciencia|espera)`, `ChikuoRetry(intento, fase)`,
  `Hint('bamboo_stance')` y `Hint('bamboo_guard')`.

**Chequeos**
* `Tools/Blender/bosses/bamboo_master/build_bamboo_master.py` corre 688 chequeos:
  * Pies hasta 1.87 cm y costuras hasta 0.06°.
  * Piso y cuerpo, cadenas y suela hasta 2 cm.
  * Las siluetas de los avisos cambian al menos un 15 %.
* `master_lint` mide las muñecas con los límites de `team_limbs` (`WristMeter`, del arreglo de huecos A3): las manos fuera
  de límite pasaron de 149 de 214 a 0.
* `check_master_fbx.py` y `check_master_roundtrip.py` (error de 0.04 cm).
* `Tools/Dev/sim_bamboo_master.py`, un port cuadro a cuadro de la pelea y del bot, con `--fair` y `--abilities`. Con el
  bot recalibrado: bueno 255 s sin muertes, promedio 0.99 muertes (29 % de las veces sin morir).

**En Play** (`prueba_bambu.json`)
1. Importación: 107 clips y la vista previa de tamaño normal (no ×100 ni invisible).
2. Presentación: las manos en la espalda, levanta la cabeza, el título, el saludo de puño en la palma, la reverencia y el
   diálogo. Después, la pelea.
3. Duración: leer '[Nindo] Pelea de X s' y la línea de PlayClock. Bueno ~256 s sin muertes; promedio, 1 a 3 muertes.
4. Guardia:
   * La grulla blanca, con la palma derecha junto a la cabeza, se distingue del Idle a 24 m.
   * Guard_P2 tiene la palma izquierda baja y Guard_P3 el bastón cruzado.
   * Golpearlo en guardia da GuardHit; el segundo golpe, Counter y CounterStrike, sin saltos.
5. Rebote:
   * Un corte suelto rebota con un clang, el grito 'Paciencia...' y la primera vez el consejo `bamboo_guard`.
   * En el combo de tres, el segundo corte se desvía a un contraataque dorado.
6. Postura del bambú:
   * Esperar ~2 s: baja la guardia y llama con la mano (Taunt, abierto por dos golpes, 'Eso. Supiste esperar.').
   * Pegarle en la postura da un contraataque, y el parry perfecto a ese contraataque lo arrodilla.
   * La barra de postura tiene 8 marcas.
7. Fases:
   * `chikuo fase 2`: PhaseCoat, con los ojos de jade y el saco que queda en el piso. La música pasa a la fase 2 y Kaito
     recibe +30.
   * `chikuo fase 3`: el bastón sale del bambú, él lo ataja y entra la música de la fase 3.
8. Grulla en la fase 1 (antes de los ~20 s): salta atrás con la mano izquierda en la espalda y cae sobre la marca roja,
   sin saltos de brazo.
9. Paso del Viento:
   * Cerca (`chikuo fase 2`, `bot on bueno`): el carril no rota en la suelta. Se agacha un poco más, sale 1-1.5 m y la
     palma pega justo en el '¡ya!'.
   * Lejos (`bot off`, `move 0 -1 1.0` hasta los 6 m): un vuelo largo que frena con la mano en Kaito.
   * Dashear contra él: lo atraviesa sin quedar flotando.
10. Réplica: después de un parry perfecto entran los 3 cortes; después de uno normal, el tercero choca.
11. Golpes con Kaito pegado: Palm, ChopPalm y TwinPalm toman el paso corto (`_Close`) sin que el pie de adelante patine.
12. Rematarlo arrodillado:
    * Defeat sigue desde el cuadro sentado y se sienta a meditar.
    * El sello sale delante de él con una onda de jade, aparece 'Chikuō derrotado' y se disuelve la barrera.
    * Al tomar el sello: 'Gracias, maestro.'
13. Reintento en la fase 2 o 3:
    * Arranca en esa fase: sin saco, y con el bastón en la 3. El saco sigue en el piso.
    * La re-presentación es corta, la música arranca en esa fase y la vida en su umbral.
14. Pies con la compresión de claves 0.05 (Walk, Run, Palm): si derivan, poner `animationCompression` en 0 en
    `bamboo_master_assets()`.

Abierto (§4b):
* No es chibi: lo decide Felipe.
* La pelea son mayormente rebotes (~0.9 por segundo).
* El Paso del Viento vuela poco contra el bot.
* El saco cambia en un cuadro.

---

## music: un tema por jefe, con fases

**Contratos y API**
* Claves:
  * `boss_goro` (2 fases), `boss_lake` (3) y `boss_bamboo` (3).
  * `boss_final` (4: los tres actos y el Último Desfile).
  * `ending`, que suena una vez. `boss` (bosskoto) queda de respaldo.
* `Game.Audio`:
  * `PlayBossMusic(key, fade = 1.2)`.
  * `SetBossMusicPhase(n, leadIn = -1)`, con las fases desde 1.
    * Entra en el próximo tiempo con su frase de transición; la sección cae en un compás, 2-5 tiempos después.
    * En el mismo cuadro que `PlayBossMusic`, arranca directo en esa fase.
    * Con `leadIn ≥ 0`, se fija cuándo cae el golpe.
  * `SilenceBossMusic(fade = 0.5, withOutro = false)`.
  * `EndBossMusic()`: el cierre escrito, en el próximo tiempo, y después vuelve la zona (salvo con `boss_final`).
  * `StopBossMusic(fade)` y `PlayEnding(delay)`, agendado en el reloj DSP.
  * `BossMusicPhase`, `MusicState` y `ForgetHeardIntros()`: en una partida nueva, las intros largas vuelven a sonar.
* `Scripts/Audio/MusicPlan.cs` se genera con `Tools/Audio/build_boss_music.py install|plan` desde
  `Tools/Audio/boss_music.json`: no se edita a mano. La receta para un tema nuevo está en `Audio/CREDITS.md`.
* Fases:
  * Mizuchi: 1 = A/A' (65.1 s), 2 = desarrollo y cumbre (52.9 s), 3 = un semitono arriba (34.6 s).
  * Bambú: 70.6, 72.4 y 53.3 s (+1).
  * Kokuyō: 73.1, 64, 43.1 (+1) y 32.6 s (+2).
  * Cierres: `boss_goro_out_1`, `boss_lake_out_3`, `boss_bamboo_out_3` y `boss_final_out_4`.

**Chequeos**
* `build_boss_music.py verify`, después del Vorbis: largos de gránulo exactos, retardo 0 y todas las costuras (intro a
  loop y loop a loop) 'ok'.
* `Tools/Audio/sim_music_director.py`, espejo de MusicDirector: sin clics, y en cada cambio la capa vieja queda al menos
  16 dB debajo.
* `stress2.py`: 500 secuencias al azar a 30, 60 y 144 fps, 0 fallas.
* `dup2`: ninguna fase repite compases de otra a r > 0.7.

**En Play**
1. Antes de Unity, escuchar las pruebas (`scratch c2/music/sim4/preview_*.ogg`) y confirmar el carácter de cada tema.
   * Revenge (Kokuyō) puede sonar turbio; el respaldo es EpicBattle_J.
   * El Último Desfile, a +2 semitonos, puede sonar acelerado.
2. Importación:
   * Los `Music/*.ogg` nuevos están en Vorbis 0.7, Compressed In Memory y Preload, y figuran en NindoContent.
   * Largos: boss_lake_3 34.6 s, boss_bamboo_3 53.3 s, boss_final_4 32.6 s.
   * Ningún aviso de clip sin cargar.
3. Gorō: ver su sección. Al matarlo, suena el golpe final y vuelve la montaña, sin un blip de la música de combate.
4. Mizuchi:
   * En cada cambio de fase (68 % y 38 %) suena distinto, y nunca vuelve al tema de apertura.
   * La fase 3 sube de tono sin que suenen dos tonos juntos (MusicState muestra boss_lake_3).
   * Al morir, el cierre suena en el mismo tono.
5. Chikuō:
   * La fase 3 es B medio tono arriba.
   * Un reintento en la fase 3 entra con la entrada transpuesta de 3.3 s.
   * Al morir, un golpe corto con eco.
6. Kokuyō:
   * El acto 2 entra con el tirón de la sombra, ~1 s después del rugido.
   * En el eclipse hay silencio, y el acto 3 entra ~1.6 s después. El Último Desfile entra con el rugido final.
   * Al morir suena el último taiko y no vuelve la música de la zona.
   * Un reintento en el acto 2 arranca sin la intro de 11 s.
7. Prueba rápida sin pelear: `Nindo.Game.Audio.PlayBossMusic("boss_lake"); Nindo.Game.Audio.SetBossMusicPhase(3);` y a
   los ~10 s `Nindo.Game.Audio.EndBossMusic();`. Lo mismo con boss_bamboo en la fase 3 y boss_final en la 4.
8. Pausa y muerte:
   * Pausar en una pelea de jefe: la música baja al 45 % sin cortarse.
   * Pausar el Editor más de un minuto y seguir: el loop vuelve limpio.
   * Morir: suena 'gameover' y, al reaparecer, la música de la zona.
9. Escuchar cada vuelta de loop, por si el re-encode de Unity dejó un clic: boss_lake_3, boss_final_4 y boss_bamboo_3.
10. Cartel del final: la línea de créditos de la música entra debajo de la de las fuentes, sin tapar 'Volver al menú',
    a 1920×1080 y a 1280×720.

Abierto: nadie escuchó los temas todavía, y falta que el usuario apruebe Amenoshita y Sakuya4, de PeriTune (§4b).

---

## ui-map: el mapa con la M

**Contratos y API**
* `Act.Map`, al final del enum.
  * Teclas de fábrica: M en el teclado, Select/Vista en el mando y el panel táctil en DualShock y DualSense (bloqueado en
    la tabla de controles).
  * `UIManager.MapOpen` y `OpenMap(bool fromPause)`. `PauseOpen` también da true con el mapa abierto, y el juego se pausa.
* `SaveData.mapFog`: string y último campo, en base64 con el prefijo de grilla `2:129x107@-258,-218:` (~1.7 KB).
  * `SaveSystem.Save` llama `MapFog.Store`.
  * Una partida sin niebla se revela alrededor del santuario y de lo que prueban sus flags (`WorldMap.json`, "legacy").
* `MapFog`:
  * `Ready`, `Tick`, `Reveal`, `IsRevealed`, `ExploredFraction`, `ExploredBounds`, `Store`, `DebugRevealAll()` y
    `DebugClear()`.
  * Celdas de 4 m. Kaito revela 16 m alrededor (34 m sobre el agua).
  * Con la puerta cerrada, no revela nada del otro lado.
* Lee:
  * `SaveData.shrines` (los santuarios sin rezar) y `zone_<id>`.
  * `IntroDone`, `boss_<id>`, `boss_seen_<id>` y el `requiredFlag` de los portales.
  * Su bandera propia es `tut_map`.
* La lámina:
  * `Tools/UI/build_world_map.py` (con `--reuse-sheet` no repinta), `world_map_preview.py` y `check_labels`.
  * El shader es `Nindo/UI Map`.

**Chequeos**
* Copia en Python del shader (`check_drift`): el papel y el borde rasgado quedan quietos mientras la niebla se corre.
* Maquetas a 16:9, 21:9 y 4:3, más `check_labels`.
* `fxc` en D3D11, en las tres variantes del shader.

**En Play**
1. Partida nueva hasta los Campos: el aviso 'Mapa / Apretá M para ver lo que recorriste' sale una vez. La M desenrolla el
   pergamino, pausa (timeScale 0), encuadra lo explorado y muestra la flecha dorada de Kaito.
2. Con el mapa abierto:
   * Esc lo cierra sin abrir la pausa. B lo cierra y Kaito no dashea después.
   * La rueda, +/− y los gatillos hacen zoom. WASD o el stick mueven el cursor, y Q (Fijar) centra en Kaito.
   * Pasar el cursor por un santuario muestra su nombre y 'Punto de reaparición' o 'Sin rezar todavía'.
3. Pausa:
   * La entrada 'Mapa' aparece debajo de 'Continuar'.
   * La tarjeta de controles tiene la fila 'Mapa': son 10 renglones, y la nota entra en la tarjeta.
   * Mientras se reasigna en Opciones › Controles, la M no abre el mapa.
4. Niebla:
   * Al caminar el borde del campo, el tramo nuevo se aclara en manchas.
   * Con la puerta del dojo cerrada, el patio sigue en niebla aunque Kaito esté pegado al muro.
5. Guardar, salir y continuar: la niebla queda igual (mapFog es la última línea del JSON).
6. Partida vieja: borrar la línea mapFog, o usar cualquiera de las partidas de prueba. El mapa se abre revelado alrededor
   del santuario y de las zonas con flag.
7. Sin rezar:
   * Los santuarios sin rezar se dibujan pelados y la leyenda siempre tiene 'Sin rezar'.
   * Al rezar, ese santuario se pone rojo.
8. `Nindo.MapFog.DebugRevealAll();` y revisar los nombres, los sellos y los portales. `Nindo.MapFog.DebugClear();`
   vuelve atrás, y
   `Debug.Log(Nindo.MapFog.ExploredFraction.ToString(System.Globalization.CultureInfo.InvariantCulture));` da lo explorado.
9. A 2560×1080 y a 1600×1200 la lámina entra sin recortes. En 4:3 la columna baja.
10. Quieto 20 s sobre lo explorado, a zoom 1 y a 2.6: el papel y el borde rasgado no se mueven y la niebla se corre al
    este.
11. El brillo de la leyenda y el torii (del arreglo de huecos).

---

## ui-controls: controles reasignables

**Contratos y API**
* `InputBindings.Table` (BindingTable):
  * La fila r es `(Act)r`, seguida de MoveUp, MoveDown, MoveLeft, MoveRight y MovePad.
  * Keys = 0, Pad = 1, con 2 casillas por dispositivo.
* `InputBindings.Commit()`:
  * Guarda en `Settings.ControlBindings` (PlayerPrefs `nindo.controls`), solo lo que no es de fábrica.
  * El formato es `1|<Acción>.<k|p><casilla>=<código>`.
* `Glyph(row, family)`, `GlyphAlt`, `MoveGlyph`, `Display`, `Name` y `BeginCapture()`. Familia: 0 teclado, 1 Xbox,
  2 PlayStation.
* Opciones › Controles lista las acciones con `Enum.GetNames(typeof(Act))`: una acción nueva aparece sola, y sus teclas
  de fábrica van en `BindingCatalog.Specs`.
* Reglas:
  * Si la tecla ya es de otra acción, se intercambian, con un aviso de dos renglones.
  * Rechaza las teclas de los menús ('se usa en los menús') y las del mapa (`BindingTable.MapContext`,
    `BindingCatalog.MapReserved`).
  * Esc queda fija para pausar y Enter para Confirmar. La cruceta y el stick no se reasignan.
  * `BindCode.PadTouchpad` (2202) es solo para mostrar.
  * De fábrica: Dash Espacio/Shift y Fijar Q/Tab.
* `UIFactory.KeyChip` y `SetKeyCap(key, glyph, family, longScale)`. `UIManager.OpenControls()` y `FitCard(card, pos)`.

**Chequeos**
* `Tools/Dev/bindings_test.py` compila BindingTable y BindingCatalog con dotnet, contra `Unity.InputSystem.dll`: 242
  chequeos con 0 fallas, más dos fuzz de 200k reasignaciones.
* `capture_sim.py` y `scroll_sim.py`, en el scratch.

**En Play**
1. `UnityEngine.PlayerPrefs.DeleteKey("nindo.controls");` y reiniciar el Play. La tarjeta de pausa muestra Fijar objetivo
   Q / Tab, 'Cambiar objetivo' con Rueda ↑ / Rueda ↓, y Mapa M al final.
2. Pausa › Opciones › 'Controles: Teclado y mando':
   * La tarjeta entra deslizándose, y las flechas o WASD mueven la selección.
   * La lista va de parada en parada, sin dejar medio renglón bajo 'Principal / Alternativa'. La rueda mueve 1.5
     renglones.
   * Con el mouse quieto no se roba la selección: abre en Mover arriba, y 8 veces abajo mueve un renglón por vez.
3. Parry Principal ← J: 'Parry ahora usa J' / 'Atacar se queda con Clic izq.'. Al cerrar, J hace parry y todos los
   key-caps muestran J.
4. Atacar Alternativa ← E: se intercambia con Interactuar ('... pasa a ...').
5. Pausa Alternativa:
   * Clic izquierdo, W, una flecha y Supr se rechazan ('se usa en los menús').
   * Esc nunca ('queda fija para pausar'), y Enter en Pausa tampoco ('queda fija para Confirmar').
6. Fijar objetivo:
   * ← rueda: 'necesita una tecla que se pueda mantener'.
   * ← clic izquierdo, = o el + del teclado numérico: 'se usa en el mapa'.
   * En el mando, ← LT se rechaza y ← B da 'B queda fijo para Volver'.
   * Mover arriba ← rueda: 'La rueda no sirve para moverse'.
7. Clics y espera:
   * Un segundo clic dentro de los 0.4 s se ignora.
   * Esperando una tecla, Esc o Start dan 'Sin cambios' sin cerrar la pausa.
   * Sin esperar, Esc o B vuelven a Opciones.
8. Supr, Retroceso o clic derecho borran la casilla. Borrar la última tecla de una acción se rechaza ('necesita al menos
   una tecla').
9. Restablecer pregunta primero '¿Volver a las teclas de fábrica?' y solo resetea el dispositivo que se está viendo.
10. Esperando una tecla:
    * Alt+Tab cancela.
    * Shift solo se toma al soltarlo, y Ctrl+K toma K.
    * AltGr se muestra como 'Alt Gr', y con Dash en Ctrl no dashea.
    * Desenchufar el mando da 'Se desconectó el mando'.
11. Mando:
    * Sin mando: 'No hay un mando conectado'.
    * Xbox: A, B, X e Y redondos y de color, y Vista.
    * DualSense: los símbolos de PlayStation, y Mapa con 'Create' más un 'Táctil' atenuado (el panel táctil abre el mapa).
    * La cruceta se rechaza ('La cruceta mueve a Kaito').
12. A 2560×1080, 3840×1080 y 1440×1080, las tarjetas de Opciones, Controles y la pausa entran enteras en pantalla. A
    1920×1080 no se mueve nada.
13. Persistencia: reasignar Fijar a clic medio, salir del Play y volver.
    `Debug.Log(UnityEngine.PlayerPrefs.GetString("nindo.controls"))` da `1|Lock.k1=Mouse.Middle`.
14. Rescate: `UnityEngine.PlayerPrefs.SetString("nindo.controls", "1|Attack.k1=Key.M");` y reiniciar. Sale una sola vez el
    aviso 'Mapa usa N' / 'M ya era de Atacar'.
15. Con el teclado de Windows en AZERTY, los key-caps de letras se re-etiquetan (la W muestra Z) y MoveGlyph da ZQSD.

---

## combat-kokuyo: la sombra de Kokuyō, el parry de acero y la vida de Mizuchi y Kokuyō

**Contratos y API**
* La sombra viva pelea en los tres actos (`KageShadow.TryStrike(move, side, leadMul)`, `EmergeLeadNow`,
  `KokuyoDuet.GapBeforeDark`).
  * Separaciones del dúo:
    * 0.9 s entre golpes desviables y 1.05-1.1 s junto a un imparable.
    * 1.7 s después de un Nobi (`GapAfterNobi`) y 1.3 s antes de un corte desde la oscuridad.
    * La sombra nunca aparece a menos de 0.25 s de un golpe de él.
  * En el acto 3 se hace visible 1.05 s antes del corte (la primera vez 1.47 s, `TeachDarkMul` 1.4), dorada y desviable,
    con un filo de tinta en la hoja.
  * El primer Nobi tiene una carga de 1.8 s (`TeachLeadMul`).
  * Los valores por acto están en `KokuyoBoss.Shadow`: `TurnChance`, `TurnMinGap`, `MaxQuiet` y `FirstTurnAfter`.
* Escalada (`KokuyoMoves.Escalation(act, stage)`):
  * Cada acto se parte en mitades con menos de 2200 de vida, o en tercios con 2200 o más (hoy son 2700).
  * En cada corte hay un rugido, un patrón nuevo y especiales ×0.75 (`StageCooldownMul`).
* Perillas de balance (las dejó así el arreglo de huecos; el frente las había dejado en 1/1 y 1/0.7):
  * Kokuyō: `KokuyoMoves.HealthScale` 1.5 (2700) y `DamageScale` 0.4.
  * Mizuchi: `MizuchiBoss.HealthScale` 1.5 (2160) y `DamageScale` 0.35.
  * Umbrales: Mizuchi {0.68, 0.38}, Kokuyō {0.70, 0.36}, iguales a `KokuyoBoss.Gates`.
  * Mizuchi cura a Kaito 25 y 20 en los cambios de fase y retoma la fase a la que llegó.
* Mizuchi:
  * `QueueSignatures(phase)`: la ola llega 2.5 s después de la corrupción y los pilares 10 s después. La tormenta, 2.5 s
    después del rugido de la fase 3.
  * `PaceStep` y `MeleeWeights`.
  * Patrones nuevos: 'Aletas y mordida', 'Torrente largo' y los '... desde lejos'. La especial 'retreat' es la Retirada.
* Parry de acero:
  * `ParrySteel.Spawn(contact, toAttacker, perfect)`, `ApplyPalette` y `TeamParryVfx` (false).
  * Shader `Nindo/ParrySteel`: `_Mode` 0 es la línea de guardia y 1 el destello. El segundo pase, `ParrySteelOccluded`,
    la dibuja a media opacidad detrás del cuerpo.
  * El destello se calma si aparece otro aviso mientras vive (`OtherWarningDuring`).
  * `ParryCrescent` sigue con Begin, Success, Whiff y Cancel, y `FXManager.ParryFlash(p, dir, perfect)` mantiene su firma.
* Luna: los halos de `NindoMoon` llegan a cero antes del borde del quad, así que ya no se ve el rectángulo.
* Debug: `KokuyoBoss.DebugShadow(move, side)`, `DebugSecondHalf()` y `DebugPattern(name)`. En AutoPilot:
  `kokuyo sombra MOV [flanco|opuesto]`, `kokuyo mitad` y `kokuyo patron NOMBRE`.
* Textos: 'kokuyo_hint_sombra', 'kokuyo_hint_oscuridad', 'kokuyo_bark_mitad1..3' y `Hint('kage_shadow')`.

**Chequeos**
* `Tools/Dev/boss_sims/`:
  * `duet_sim.py`: la sombra pega el 28, 42 y 33 % de los golpes en los actos 1, 2 y 3. La separación mínima es 1.2,
    0.9 y 0.9 s, y ningún anillo pisa a otro.
  * `kk_fix_run.py` y `mz_fix_run.py`: la pelea entera de Kokuyō y de Mizuchi. También están `fight_kokuyo.py`,
    `mizuchi_sim.py`, `mz_run.py` y `kaito.py`.
* `moon_sim.py`: el escalón en el borde de la luna pasó de 10.6/255 a 0.1/255.
* El chequeo de la calma corre sobre el duet sim.

**En Play** (`prueba_kokuyo.json` y `prueba_mizuchi.json`)
1. Acto 1 cuerpo a cuerpo con `Nindo.AutoPilot.ResetStats(); Nindo.AutoPilot.Run("bot on bueno");`:
   * El primer Nobi llega a los 8-10 s, con la carga lenta y la frase del abuelo. Después, ~2 por acto 1.
   * La línea '[Nindo] Kokuyō acto 1 (...)' dice 'N de la sombra' con N de 2 o más.
   * `kokuyo sombra nobi` pegado a él: el anillo se cierra a los pies de Kaito, la hoja de la sombra corta de lado a lado
     y un parry la desvía.
2. 'Sombra y Acero' (acto 1): después del corte de la sombra, su kesa llega ~1.7 s más tarde, y la sombra se adelanta
   ~0.36 s.
3. Acto 2 (`kokuyo act 2`, después `kokuyo sombra giri opuesto`, `nui` y `watari`): el cuerpo nunca pega a menos de
   ~0.9 s de un golpe de la sombra y nunca se pisan dos anillos.
4. Acto 3 (`kokuyo act 3` y varias veces `kokuyo sombra giri`):
   * La primera aparición llega ~1.5 s antes del corte; las demás, ~1.05 s.
   * Alterna el lado opuesto y el flanco, y la figura violeta se lee contra el piso.
   * Parar unas 10 a mano y contar cuántas entran.
5. Parry en nieve, patio, pasto y eclipse:
   * La línea es dorada y después azul fría, de ~7-8 cm. Se ve a media opacidad con Kaito mirando al norte.
   * El fallo se parte en dos mitades grises.
   * El normal es una aguja blanca corta, con un lente oscuro en la nieve. El perfecto sostiene el pico en el hit-stop y
     se va a los 0.15 s.
   * No se parece a un aviso ensō. Opcional: comparar con `ParrySteel.TeamParryVfx = true`.
6. Calma:
   * `kokuyo act 2`, `kokuyo patron Pinza` y un parry perfecto a mano a su kesa: el destello sale al 40 %, sin la
     estrella, y el anillo de la sombra del otro lado se lee entero.
   * Control: con `kokuyo act 3` y `kokuyo patron Media Luna Negra`, la estrella sí sale. Con un ninja solo, también.
7. Luna: la transición del eclipse (PlaySkyShot) y la vuelta en el final, cuadro a cuadro y con y sin bloom. No se ve el
   rectángulo claro, y la vuelta es un brillo suave. Mirar también la luna del piso (NindoFloorMoon).
8. Mitad del acto (`kokuyo mitad`): después de su combo ruge 1.3 s, los golpes rebotan, aparece la línea y después el
   patrón nuevo.
9. Mizuchi con `bot on bueno`:
   * En la fase 2 la ola llega ~2.5 s después de la corrupción, y los pilares ~10 s después.
   * En la fase 3 la tormenta, con la Retirada, llega ~2.5 s después del rugido, y nunca dos tormentas seguidas.
   * El koi a veces salta lejos (Retirada).
   * En cada cambio de fase la bandana pulsa y Kaito se cura.
10. El balance de la sección de huecos.

---

## world-story: santuarios, muralla, puerta de los sellos, despertar y final

**Contratos y API**
* Estados de Kaito, siempre con `HasState` y un respaldo:
  * WakeUp, con LieDown de respaldo.
  * PrayIncense y PrayQuick, con Pray.
  * BandanaPower, con Interact.
  * EndingTurn, con un paso más Interact.
  * Los momentos salen de `KaitoTimings.Event`.
* Del abuelo: Bound, Freed y Walk, con `NpcHasState` y Locomotion de respaldo.
* Partida:
  * `SaveData.shrines`: los santuarios con el incienso prendido.
  * `SaveData.sealsPlaced` (bool[3]) y `SealPlaced(SealId)`. `Load` los acepta nulos.
  * Flags `pray_seen` y `tip_shrine`.
  * `SaveSystem.MigrateWallGate` abre el portón en las partidas viejas que ya cruzaron la muralla.
* API:
  * `StoryDirector.PrayAt(cp)`, `Praying`, `OpenWallSeal(WallSeal)`, `OpenSealGate(SealGate)`, `TickShrineTip(cp)` y
    `WakeRevealHold` (1.4 s).
  * `SealGate.IsPlaced`, `PendingCount`, `PlacedCount` y `FirstPending`. Con `dojo_open`, los tres cuentan como puestos.
  * En `StoryText`: `PlaceSealPrompt(id)`, `PlaceSealsPrompt`, `OpenGatePrompt`, `ExamineGatePrompt`, `SealPlacedLine`,
    `GateIncomplete`, `SealName` y `PrayerLine`.
* FX:
  * `ShadowRopes.Drop(0.55)`, `IncenseFlame.Create/Douse`, `ShrineIncense.Light/Douse/IsLit`, `BandanaStream.Play` y
    `SkipHint.Show/Hide`.
  * `HalfRibbon.Stow(belt, local, seconds)` guarda la media cinta en el cinturón. No renombrar `Root`, `Mando.L`, `Dedo2`
    ni `Dedo3`.
* Puntos del mundo: `seal_gate` y `npc_grandpa_dojo`.
* Final:
  * `Game.Audio.StopMusic` al empezar el rescate y `PlayEnding()` en el reencuentro (de la integración, `4c674d4`).
  * Si se cerró el juego en medio, se retoma con `ResumeEnding` (`06416b4`).

**Chequeos**
* Maquetas en Blender con los números de cámara del código: el rezo, la puerta y la ofrenda (`sim_offer2`).
* Caminos alrededor del santuario: 2075 arranques, ninguno cruza la caja.
* La cinta, en verlet a 30, 60 y 120 fps. `stow_probe.py` corre sobre `kaitooo.fbx`.
* `prayquick_katana.py` (de la integración): la katana del rezo corto queda al menos a 5.6 cm de la base del santuario.

**En Play**
1. Partida nueva:
   * El prólogo abre con Kaito boca abajo, que murmura.
   * Cuando levanta la cabeza (WakeUp f80), corte por encima de su hombro al secuestro, ~1.4 s, y después el seguimiento.
   * 'intro_wake' arranca a los 2.4 s.
2. Después de la pelea del prólogo:
   * Dentro de ~6 s la cámara se corre 3.5 s hacia cp_home y el incensario suelta motas doradas.
   * El consejo 'Rezá en los santuarios con {Interact}...' sale una sola vez por partida: al recargar no vuelve.
3. Un santuario sin rezar, de día y de noche: no brilla ni tiene halo, y el modelo se entiende.
4. Primer rezo, en cp_home, con el plano de costado:
   * Deja la katana con sus manos.
   * Toma el incienso (~2.3 s), aparecen la brasa y una llamita (~2.9 s), la apaga con el segundo abanico y lo clava
     (~3.9 s).
   * Cura y guarda al juntar las palmas, y dice una frase por el abuelo.
   * Retoma la katana. El humo y la brasa quedan, también al recargar.
5. Segundo santuario sin rezar:
   * Rezo corto, al costado de la línea de la cámara; el chispazo se ve.
   * 'Enter Saltar' aparece abajo a la derecha cuando ya está arrodillado.
   * Submit, después de 0.3 s, lo salta: cura, guarda y prende igual. Interact no lo salta, y pausar y apretar Submit
     tampoco.
   * Si se salta con la katana en el piso, juega la recogida.
6. Más rezos:
   * En uno que ya humea: PrayQuick, sin franjas y con el HUD.
   * Con un enemigo cerca no se puede rezar.
   * Si uno llega durante el rezo corto, Kaito se levanta sin curar y el encuentro no se reinicia.
7. Muralla:
   * Al ganar enc_wall, el plano del sello y la frase, con el portón todavía cerrado.
   * 'Abrir con la bandana': la bandana se prende al tocar (f14) y sale el rayo dorado.
   * El sello estalla (el sonido más fuerte de la escena) y las puertas crujen ~0.7 s después.
   * La cámara entra al jardín, se actualiza el objetivo y se guarda.
8. Partida vieja con wall_gate_open: el portón está abierto y sin sello. Con los guardias ganados y sin el flag: el
   sello, el aviso y el objetivo.
9. Puerta de los sellos sin ningún sello: la grúa termina de frente a los tres grabados y sale el diálogo 'dojo_gate'.
   Interact dice qué falta.
10. Un sello (`prueba_mizuchi.json`, después de ganar):
    * El grabado del agua pulsa y el cartel dice 'Colocar el Sello del Agua'.
    * El medallón aparece delante de la palma que empuja, un poco más arriba, vuela al hueco del medio y encastra con un
      destello.
    * Se guarda y Kaito dice su línea. El objetivo ('Llevá el ... a la puerta del dojo') entra en un renglón.
    * Al recargar, el medallón sigue puesto.
11. Los tres a la vez (`prueba_tarde_cp_lake_falls.json`):
    * 'Colocar los sellos': vuelan los tres juntos.
    * La luz corre entre los tres, tiembla todo, se abre la puerta, viene el plano abierto y 'dojo_gate_open'.
    * El objetivo pasa a 'Entrá al dojo y rescatá al abuelo'.
    * En una partida con dojo_open: los tres puestos, la línea prendida y ningún cartel.
12. Pasar al patio y mirar atrás: ningún anillo ni grabado aditivo flotando en el hueco.
13. Final:
    * Después del golpe no suena la música del dojo: viento y campana.
    * En negro, Kokuyō arrodillado y sin máscara. Kaito levanta la media cinta y grita '¡Abuelo!'.
    * Las cuerdas caen en ~0.55 s y se deshacen, sube 'ending', y el abuelo hace Freed y Walk.
    * Plano de dos y de tres. Al detenerse, el nudo se desliza ~17 cm al cinturón en 0.35 s.
    * En EndingTurn f50 el puño toma el nudo. En la ofrenda (~2.03 s) la cinta cuelga de la palma, con el destello.
    * La mano y la cara de Kokuyō entran en las franjas, a 16:9 y a 21:9.
    * Kokuyō se inclina, la cinta queda delante de sus rodillas, se van, sube la cámara y sale el cartel del final.
    * Mirar la cola de la cinta que roza la pierna en EndingTurn f13-18: hasta 3 cm, dos cuadros.
14. `Game.Save.sealsPlaced = new bool[]{false,true,false};`, con los tres sellos en la mano, guardar y recargar: solo
    queda puesto el del medio.

---

## culling: ZoneCulling

**Contratos y API**
* `Nindo.ZoneCulling` (`World/ZoneCulling.cs` y `ZoneCulling.Debug.cs`). Lo crea `WorldBuilder.Build`, con
  `ZoneCulling.Create(host, staticRoot, dynamicRoot, encounters, arenas)`.
* Estáticos:
  * `On`: en false prende todo en el acto.
  * `IncludeSceneView`: solo en el editor. Cuentan las vistas Scene que se dibujaron en el último segundo.
  * `HideBatched`: true por defecto.
  * Contadores: `RenderersOn/Total`, `CastersOn`, `EnemiesAwake/Total`, `ParticlesSimulating/Total`, `CostMs`, más
    `Stats` y `ShowHud`.
* Métodos: `Benchmark(30)`, `CheckFrame(carpeta)`, `CheckEvery(intervalo, carpeta)` y `StopCheck()`.
* El banco de pruebas corre con Ctrl+Shift+F9 (F9 sola no hace nada) o con `-zcbench [s]` en un Development Build. El
  informe va a Player.log.
* Constantes:
  * Celdas de 32 m, margen 1.5 m, Linger 0.35 s.
  * WakeRadius 45 m, SleepRadius 55 m, SleepDelay 2 s.
  * MaxCameras 4. El barrido de sombra llega a 400 m.
* Enemigos:
  * `Enemy.Asleep`, `SetAsleep(bool)` (solo lo llama ZoneCulling) y `virtual CanSleep`: State == Idle, sin aggro, vivo,
    sin empuje y con el agente quieto.
  * `SetState` y `ScriptedPlay` lo despiertan, y el campamento entero despierta en el mismo cuadro.
  * Los idles de ambiente corren en Idle y duermen con su campamento. La integración (`5463839`) sacó `AmbientIdle` y los
    vetos.
  * Kokuyō (WaitKneeling) y Mizuchi (Lurk) nunca duermen.
* `KohanFalls.SetOffscreen(bool)` y `Frozen`: la cascada se congela fuera de cuadro solo si está activa y pasaron 9.5 s
  del `SetActive`.
* Qué recolecta, al construir el mundo:
  * Todo lo prendido bajo Static.
  * De Dynamic: GateDoor, Checkpoint, Portal, FlagBarrier, FloatingBob y 'Fireflies'.
  * Lo que se crea después no entra: el humo del incienso, los brillos de SealGate y WallSeal, las rocas de Gorō y el
    filo de KageShadow (§4b).
  * Una cámara apagada que se dibuja a mano tiene que envolver su Render con `ZoneCulling.On = false` / `true`.

**Chequeos**
* Simulación en Python sobre un volcado del mundo real (1990 renderers):
  * Explorando quedan ~50 prendidos (p95 108).
  * 0 pop-in en 454 puntos del camino y en 1500 tomas de cinemática.
  * Los casters bajan un 20 % en High.
* `sim_sleep2`: quedan despiertos 11.6 de 35 enemigos.
* La compilación del player, sin `UNITY_EDITOR`, pasa con y sin `DEVELOPMENT_BUILD`.
* Ganancia esperada, de un modelo (no medida): de -0.1 a -0.5 ms en el hilo principal y de -0.2 a -0.4 ms en el de
  render.

**En Play**
1. Al arrancar sale '[Nindo] ZoneCulling: ~1990 renderers en ~220 celdas, 35 enemigos, 1 cascada(s).', sin avisos de
   bounds enormes ni de 'siempre prendidas'.
2. Base: `Nindo.ZoneCulling.IncludeSceneView = false; Debug.Log(Nindo.ZoneCulling.Stats);`.
   * Tiene que decir 'cámaras 1' y entre unas decenas y ~110 de ~1990 renderers prendidos.
   * Con la Scene visible al lado: 'cámaras 2' y '(cámara de juego sola N)'.
   * Con la pestaña Scene tapada detrás de Game: 'cámaras 1'.
3. Pop-in: `Nindo.ZoneCulling.CheckFrame("C:/Temp/zc");` da 0 píxeles distintos, o unos pocos en los bordes de sombra.
   * Después `CheckEvery(0.25f, "C:/Temp/zc")` y jugar: una presentación de jefe, la grúa de la cascada, una toma del
     cielo, el santuario de costado, las luciérnagas y el humo.
   * `StopCheck()` tiene que dar 0 cuadros distintos. Un parche rojo en un `dif_*.png` es una falla real.
4. `Nindo.ZoneCulling.On = false` y después `true`, mirando la pantalla: nada cambia.
5. Cascada, con `ShowHud = true`:
   * Esperar 10 s cerca de Kohan y darle la espalda: 'cascada congelada (fuera de cuadro)'.
   * Volver a mirarla: las columnas están llenas y en movimiento, sin rellenarse.
6. Campamentos:
   * Alejarse más de 60 m (del sumo, de los guardias del dojo o de una pareja que practica) y esperar 3 s: EnemiesAwake
     baja por el campamento entero.
   * Volver: despierta junto, la pareja sigue sincronizada y nadie se alerta solo.
   * Caminando el mapa quedan ~11-12 de 35 despiertos.
   * Morir lejos de un campamento dormido: fijar objetivo no lo elige, y al volver despiertan y alertan normal.
   * En una pelea de jefe nadie se duerme.
7. Ganancia, en un Development Build con Frame Timing Stats prendido, a 1920×1080 y en High:
   * `-zcbench 30`, o Ctrl+Shift+F9 con Kaito quieto, en cuatro lugares: el jardín, el camino del bambú, el patio del
     dojo y la orilla de Kohan. Pegar los cuatro informes de Player.log.
   * Pasa si la CPU principal y la de render con culling dan igual o menos que sin, y los Batches o Draw Calls no suben.
   * Si dice 'OJO: con culling hay MÁS Batches', repetir con `HideBatched = false`.
   * Al terminar, `Application.targetFrameRate` y `QualitySettings.vSyncCount` vuelven a '120 1'.
8. Vista Scene en Play: el mapa se ve entero donde mira la Scene.

---

## Integración (`c2/integration`)

**Qué se resolvió al juntar**
* `CharacterAnimator`: `LocomotionParam` (kaito-anim) quedó junto a `HasDirectional`/`SetDirectional` (ninja-sumo).
* `CharacterFactory`: 'ozeki' crea `BambooMasterBoss` y 'goro' crea `GoroBoss`. Gorō no tiene el umbral genérico del
  50 %; Chikuō tiene 0.66/0.33.
* `Enemy.TakeHit`: `kb = startled ? 0 : KnockMeters(...)`. La muerte sentada va dentro de `DeathBurst`.
* `SumoPoser` perdió el brillo especial del shiko del Ōzeki.
* `KokuyoBoss.Eclipse`: `kage?.Hide()` y `SilenceBossMusic(0.4f)`.
* NindoContent: `avalanche_rumble`, `bandana_charge` y `bandana_release` quedaron como entradas separadas.

**Arreglos de la integración**
* Música de Gorō (`90964db`).
* El abuelo espera Freed entero antes de Walk (`fed60e5`).
* `KaitoTimings` regenerado, la katana del rezo corto en el piso y `PlayEnding()` en el final (`4c674d4`).
* Culling sin `AmbientIdle`: `CanSleep` es `State == Idle` y `EnemyAmbient` no corre dormido (`5463839`).
* Fila `kage` de NindoContent (`f6c4b28`) y fila `goro`, con los largos de los clips que se habían alargado (`8d7cac0`).
* `UIMap` lee `SaveData.shrines` directo (`ba7fd68`).

**Auditoría**
* Compilación:
  * `compile_check` da OK en 136 archivos.
  * La compilación del player pasa con y sin `DEVELOPMENT_BUILD`.
  * `bindings_test`: 242 chequeos, 0 fallas.
* `generate_assets.py` en seco: los controllers, las metas de TeamAnims y las filas de NindoContent salen idénticos.
* `fbx_scan` sobre los 16 FBX cambiados:
  * Todo lo animado cuelga de `Armature/` (en Chikuō, de `BambooMaster/`) y ningún nodo raíz se anima.
  * Las listas de clips de cada `.meta` coinciden con su sidecar.
* Sin GUIDs repetidos entre 1262 metas y sin kanji ni separadores ' - ' en el texto del jugador.
* Contratos: todos los estados del contrato existen en los controllers, y todos los estados que nombra el código también.
* Simulaciones: avalancha sin olas sin escape; Gorō bueno 1.6 min. Después la recalibraron los arreglos de huecos.

**En Play**
1. Respaldar `nindo_save.json` antes y restaurarlo después.
   * Cerrar Unity antes de mergear: la reimportación es grande (FBX, OGG, controllers).
   * Abrirlo y esperar la reimportación y la compilación, sin errores en consola.
2. Gorō:
   * Todos los enemigos con el cuerpo junto a su barra, con la escala de la raíz entre 0.5 y 1.
   * Las duraciones de su sección, con `anim.Length("Combo1")` = 1.6.
3. Barra falsa y música de Gorō, como en su sección: `DebugSetHealth01(0.02f)` y `DebugArmor()`.
4. Final:
   * La música entra cuando caen las cuerdas (`PlayEnding`).
   * Freed se juega entero (parado a los 3.27 s, Idle a los 3.6 s) y después camina hacia Kaito sin saltos.
   * El cartel del final no reinicia el tema.
5. Rezo corto en un santuario nuevo:
   * Kaito deja la katana a su derecha, sin meterla en la base de piedra, tampoco cuando queda corrido al costado.
   * Cura y sale el indicador de guardado cuando se juntan las palmas (~40 % de los 2.33 s), no antes.
   * Saltar con Submit: juzgar si la recogida rápida de la katana se ve mal.
6. Campamentos con ZoneCulling: como en culling, punto 6.
7. Mapa: los santuarios sin rezar se ven pelados y la leyenda siempre tiene 'Sin rezar'. Al rezar, el santuario se pone
   rojo.
8. Pausa: la tarjeta de controles tiene 10 renglones (con 'Cambiar objetivo' y 'Mapa') y la nota entra.
9. Chikuō:
   * `musicKey` boss_bamboo. La fase 2 entra en el CoatOff y la 3 en el StaffCatch.
   * No hay cambio de fase temprano en el piso del 66 %.
   * `chikuo fase 2` y `chikuo fase 3` andan.
10. Eclipse de Kokuyō:
    * La sombra se esconde y la música se calla. El acto 3 arranca ~1.6 s después.
    * `kokuyo sombra giri`, `kokuyo mitad` y `kokuyo patron Pinza` andan.
11. Prólogo de una partida nueva:
    * KaitoComesTo (WakeUp con el corte por encima del hombro).
    * El plano de costado del abuelo con el agarre y el arrastre (Kidnap 1.2 s después del corte).
    * Sin un hit_heavy de más ni un doble puf cuando desaparecen.
12. Después, las listas de cada frente, y al final el balance: `bot on bueno` y `bot on promedio` por jefe, buscando una
    hora de partida.

---

## Arreglos de huecos (después de la integración, hasta `93ff54f`)

**Qué hizo**
* Las muñecas de Chikuō (A3), la bandana con todos sus vértices en la cabeza (A5) y la patinada de WakeUp y PrayIncense
  (de 2.89 y 2.78 cm a 1.75 y 0.0 cm).
* El zanshin del Finisher sin tics.
* El plano del rugido de Gorō más cerca y la armadura parda con brasa más ancha (A8, en parte).
* Los títulos de jefe en el tercio de abajo (`ShowBossTitle`).
* El final se retoma si se cerró el juego en medio, y las cinemáticas anidadas no sueltan el control antes de tiempo.
* El rezo corto no se salta desde la pausa.
* Las partidas viejas reciben `wall_gate_open` y el flag del mapa.
* Los tambores de Gorō caen cuando se para, y una partida nueva vuelve a oír las intros.
* Los planos de cámara no se vencen detrás de la pausa, y el banco de pruebas pasó a Ctrl+Shift+F9.
* El sonido `spar_clash`.
* Los campamentos de ambiente no se pueden pasar de largo: en el medio del campamento arrancan igual, y los de la muralla
  y el sumo (`StoryDirector.GatesProgress`) arrancan con su radio entero.
* Gorō 1000 + 1600 con tres tramos que curan y el reintento armado. El bot promedio se recalibró: falla el 15 %, se
  confunde el 7 % y ataca apurado el 15 %.
* Mizuchi retoma la fase, y Mizuchi y Kokuyō quedaron con vida ×1.5 y el daño que aguanta el promedio.
* PlayClock por zona y por jefe, en la consola y en el cartel del final.
* El filo de tinta de la hoja en el eclipse, el humo del incienso legible desde la cámara del juego y el empujón de panza
  del sumo con i-frames.

**En Play**
1. Chikuō, fase 3, con `bot on bueno`, de cerca y desde la cámara de juego:
   * Las manos en el bastón se ven naturales, sin saltos de muñeca.
   * Stance_P3: el bastón plantado en la mano derecha y la palma izquierda arriba. Mirar el fundido de 0.1 s a
     Counter_P3.
   * Taunt_P3: la izquierda sostiene el bastón con la punta arriba y la derecha lo vuelve a tomar suave.
   * ChopPalm_P3: la derecha suelta y vuelve a agarrar en la carga y en la recuperación.
   * PhaseStaff: cómo ataja el bastón que vuela.
2. Chikuō, fases 1 y 2:
   * La postura del bambú (palmas cruzadas en X delante de la cara, codos abiertos) se distingue del idle y de la guardia.
   * En la guardia de la fase 2, la mano baja va más abierta.
3. Kaito desde la cámara de juego:
   * En Attack1 a 3, el nudo amarillo ya no se dobla en un cuerno.
   * Al pararse en WakeUp y al arrodillarse en PrayIncense, el pie derecho no patina.
   * En el zanshin del Finisher, el puño izquierdo cierra suave.
4. Gorō, ArmorRise: el rugido entra entero, con el martillo arriba y más cerca que antes. La armadura se lee como roca
   parda oscura con brasa, no como hielo.
5. Gorō, combos (1, 2 y 3, las variantes B y SlamWave): ver si los pies apoyados patinan en la embestida. El lint de
   team-anims dice 6-16 cm desde el cambio de StepTimeline de ninja-sumo.
6. Por jefe, con `bot on bueno` y `bot on promedio`: leer las líneas de PlayClock (`[Nindo] ... vencido en`, con el
   tiempo, las muertes y el bot).
   * Referencias de los sims, en minutos simulados: Gorō 3.4 y 5.0; Mizuchi 2.4 y 4.8; Kokuyō 2.0, con ~3 muertes del
     promedio; Chikuō ~4.3 min con 0.99 muertes.
   * El cartel del final muestra la hora de juego.
7. Reintentos: si muere armado contra Gorō, arranca armado. Mizuchi retoma la fase a la que llegó Kaito.
8. Cerrar el juego en medio del final (con final_boss_done y sin ending) y recargar: el final se retoma con Kokuyō
   vencido y el abuelo arrodillado. Es lo que hace `prueba_juego_completo_cp_lake_falls.json`.
9. Rezo corto:
   * Pausar en medio y apretar Submit: no lo salta.
   * El aviso de saltar aparece cuando ya está arrodillado.
   * Saltarlo, o que lo interrumpan, con la katana en el piso: juega la recogida.
10. Una partida nueva vuelve a oír las intros de los jefes. Los tambores de Gorō caen cuando se para (MusicState).
11. Títulos de jefe: en las cinco presentaciones van en el tercio de abajo, no sobre la cabeza. El título bajo se apaga
    cuando se abre un diálogo o aparece la barra del jefe.
12. Una partida vieja que ya cruzó la muralla: el portón queda abierto y el mapa revela el jardín del sumo.
13. F9 sola no hace nada; Ctrl+Shift+F9 arranca el banco de pruebas. Medir la ganancia en un build.
14. Mapa: el brillo de la leyenda y el torii. Controles: el aviso de resultado mixto cuando una reasignación choca.
15. El humo del incienso se ve desde la cámara de juego. En la luna llena de Kokuyō, el filo de tinta se ve antes del
    corte. El empujón de panza del sumo funciona justo después de que golpean a Kaito.

---

## Lo que quedó abierto al cerrar C2

Es la lista "STILL OPEN" de la auditoría. Los frentes de C3 parten de ella; el detalle de cada punto está en §4b del
traspaso.

* **[alto] Balance de Mizuchi y Kokuyō.**
  * El bueno sigue lejos de los 4-6 min: Mizuchi ~2.4 min simulados (~3.3 reales) y Kokuyō ~2.0 (~2.8 reales).
  * El promedio muere ~3 veces contra Kokuyō, y la hora total no está medida.
  * Subir la vida sola no alcanza: hace falta sustento como el de Gorō, curas por postura rota o por acto.
  * Antes, medir con PlayClock para calibrar el factor 1.4 entre el sim y el juego.
* **[alto] Gorō patina 12-14 cm** en sus combos con el reloj del juego, y GoroAnims.fbx no se puede re-exportar. Falta
  darles `apex`/`from` y embestidas en cuadros del clip, como al ninja.
* **[alto] Música sin aprobación del usuario.** Las licencias de las dos pistas de PeriTune se infirieron.
* **[medio] La armadura de Gorō está a medias.** Falta agrandarla junto con los caminos del martillo, el agarre del
  mango y la cadera sentada. Nadie la vio en su color nuevo.
* **[medio] Los tirones de un cuadro de Kaito.** Falta el tope por cuadro en `kaito_rig.arm_path` y repartir la suelta de
  BandanaPower y las piernas de Death.
* **[medio] Chikuō.** Las proporciones, los rebotes, el vuelo corto del Paso del Viento y el saco que sale en un cuadro.
* **[medio] Culling.** La ganancia sin medir y los FX que nacen después de `WorldBuilder.Build`.
* **[bajo] Kokuyō, acto 3.** Pocas sombras (1.8 contra la meta de 4) en 15.5 s, y nadie revisó los planos del cielo.
* **[bajo]** Los basaltos claros que se leen como hielo (el pase de Felipe).
* **[bajo]** El kit y los clips muertos del Ōzeki, y los movimientos del sumo del lago y del bambú.
* **[bajo]** Las listas de pruebas no estaban en el repo: ahora están en este archivo.
* **[bajo]** La partida del juego completo disparaba el final al cargarla. Queda como la prueba de `ResumeEnding`, y las
  demás están en [`../partidas/README.md`](../partidas/README.md).
