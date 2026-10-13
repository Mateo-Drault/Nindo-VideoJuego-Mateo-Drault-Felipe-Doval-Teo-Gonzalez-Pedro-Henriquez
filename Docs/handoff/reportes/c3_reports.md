# Fase C3: los seis frentes y la integración

La fase C3 arrancó de main `76be027` (C2 integrada y probada por el lead en Unity) y arregló lo que la revisión de
C2 dejó abierto. Seis frentes trabajaron en paralelo, cada uno en su rama `c3/*`, y se integraron con `--no-ff` en
`c3/integration`, en este orden. **Nada de C3 se probó en Unity todavía**: todo está validado fuera de Unity
(compilación, lints de Blender, simulaciones y renders), y la lista de pruebas en Play está al final.
`c3/integration` sale de `76be027` y no tiene `e3fa891` (origin/main, la aprobación de la música en
`Audio/CREDITS.md`): se fusionan sin conflictos.

| Rama | Head | Qué trajo |
|---|---|---|
| `c3/goro-anim` | `4c83c86` | Gorō: la embestida en cuadros del clip (sin patinar), un paso largo y pesado, variantes en el lugar contra la barrera, la armadura parda que crece pareja, balance recalibrado con el bot de Unity. |
| `c3/kaito-snaps` | `efd78aa` | Kaito: tirones de un cuadro resueltos en el solver y en los clips, un lint que mira todo el cuerpo, el Corte final con las dos manos en la empuñadura y el chiburi del remate a x1. |
| `c3/chikuo-feel` | `7abb6ba` | Chikuō: el desvío con la palma que lee el corte, el paso del viento que vuela, sigue a Kaito y pasa al costado sin frenar en el aire, el saco que se desliza, el sonido del desvío. |
| `c3/kokuyo-act3` | `006ae17` | Kokuyō y Mizuchi: sustento por etapa antes que vida, el eclipse con la sombra de protagonista, dúos que salen, reintento por acto, la barra del acto, la luna y la niebla sin cortes. |
| `c3/culling-dyn` | `c9fc3f3` | `ZoneCulling.AddDynamic`: lo que se crea después del armado (incienso, braseros, rocas de Gorō, pétalos) también se apaga y pausa fuera de cuadro, con puesta al día al volver. |
| `c3/docs-saves` | `f108a8f` | `reportes/c2_reports.md` y una partida de prueba antes de cada jefe (`partidas/README.md`). |

---

## 1. La integración (`c3/integration`)

### 1.1 Merges

| Merge | Rama | Conflictos | compile_check |
|---|---|---|---|
| `48456e6` | `c3/goro-anim` | ninguno | OK, 135 .cs |
| `9b20d39` | `c3/kaito-snaps` | ninguno | OK, 135 .cs |
| `25877cd` | `c3/chikuo-feel` | ninguno | OK, 137 .cs |
| `bc8ab0e` | `c3/kokuyo-act3` | ninguno | OK, 137 .cs |
| `daad3f9` | `c3/culling-dyn` | ninguno | OK, 138 .cs |
| `e8a6362` | `c3/docs-saves` | ninguno | (sin C#) |
| `d083588` | arreglo de la integración | | OK, 138 .cs |

Ningún merge tuvo conflictos de texto. Los archivos que tocaron dos frentes se fusionaron solos y quedaron con las
dos partes:

* `Combat/CombatTypes.cs`: `AttackDef.lungeTo` (goro-anim) y `HitResult.Deflected` (chikuo-feel).
* `Resources/NindoContent.asset`: los 7 estados `*Planted` de goro, los 5 nuevos de bamboo_master
  (`DashStrike_Pass[_P3]` y los tres `GuardHitL*`) y el sonido `palm_deflect`.
* `Player/PlayerController.Combat.cs`: `EndFinisher` a x1 (kaito-snaps) y `CutEta`/`CutName` más el caso
  `Deflected` (chikuo-feel).
* `FX/MoonEclipse.cs`: `MoonReturn`/`DriveSky` (kokuyo-act3) y el `AddDynamic` de los pétalos (culling-dyn).
* `README.md`: la viñeta de Chikuō y el párrafo de `ZoneCulling`.

### 1.2 Chequeos sobre el árbol integrado

* **Binarios**: cambiaron 6, cada uno lo cambió una sola rama y el de la integración es exactamente el de su dueño:
  `kaitooo.fbx` (kaito-snaps), `BambooMaster.fbx` y `palm_deflect_1/2.wav` (chikuo-feel), `GoroAnims.fbx` y
  `Kit_goro_armor.fbx` (goro-anim).
* **Ligado de los FBX** (sin Blender, leyendo el FBX):
  * `kaitooo.fbx`: 65 nodos, las curvas solo bajo `Armature/`, el Armature sin animar, 33 clips en el .meta iguales
    al sidecar.
  * `BambooMaster.fbx`: 95 nodos, las curvas solo bajo `BambooMaster/`, la raíz sin animar, 112 clips iguales al
    sidecar (5 más que en C2); la toma llega hasta 189.07 s (los clips nuevos van al final).
  * `GoroAnims.fbx`: 66 nodos, una sola raíz con `preserveHierarchy: 1`, curvas bajo `Armature/`, 31 clips iguales
    al sidecar; la toma llega hasta 69.47 s (las 7 variantes al final).
  * `Kit_goro_armor.fbx`: sin animación.
  * Contra la base: ningún nodo menos, ningún padre cambiado, las mismas fps y unidades.
* **GUID**: 1266 `.meta`, ninguno repetido; los 5 archivos nuevos de `Assets` tienen su `.meta`.
* **Texto** (87 archivos cambiados): sin glifos japoneses, sin " - " ni " — " en strings nuevos de C#, sin marcas de
  conflicto.
* **generate_assets en seco** (intercepta las escrituras y compara): los 8 controllers, los 4 `.meta` de TeamAnims,
  `BambooMaster.fbx.meta` y sus `.mat`, `kaitooo.fbx.meta` y las filas de personajes de NindoContent salen
  idénticos. Las 92 claves de sonido coinciden (`palm_deflect`: los dos wav, volumen 1, 3D). Los 9 `.mat` de
  `Art/Materials` salen distintos, pero es la deriva vieja (Unity los reserializó en su formato) y nadie de C3 los
  tocó: **no correr generate_assets entero**, solo las funciones de lo que se cambia.
* **Tablas de tiempos**: `goro_timings`, `bamboo_master_timings`, `kokuyo_timings` y `kaito_timings` regenerados
  sobre la integración no cambian nada.
* **Contratos**: los estados del contrato están en cada controller, ningún estado con nombre literal en el código
  falta en un controller, la música y los sonidos que pide el código existen.

### 1.3 Simulaciones re-corridas sobre la integración

| Jefe | Simulación | Perillas de hoy | Bueno | Promedio |
|---|---|---|---|---|
| Gorō | `goro_fight_sim.py --runs 400` | 1900 + 3040, daño x0.30 / x0.25, 55 por tramo roto | 6.1 min simulados = ~4.3 reales, 0 muertes | 8.3 simulados = ~6.5 reales, 1.2 muertes (~1.6 reales), 38 % gana al primer intento |
| Chikuō | `sim_bamboo_master.py --runs 200 --seed 3` | 2200 | 249 s sin morir | 0.69 muertes, 40 % sin morir, 388 s en total |
| Mizuchi | `boss_sims/mz_run.py tuning bueno,promedio 200` | 3240 (x2.25), daño x0.33, 14 por postura rota | 3.49 min simulados | 5.61 min, 1.11 muertes, 31.5 % al primer intento |
| Kokuyō | `boss_sims/kk_fix_run.py largo bueno,promedio 200` | 5400 (x3), daño x0.33, tramos 35/35/25 | 3.63 min simulados | 6.11 min, 1.65 muertes, 27.5 % sin morir |

* Chikuō: experto 213 s; con `--human 0.5` los cortes rechazados son el 59 % (lo mismo que midió el frente).
* Kokuyō, `kk_fix_run.py actos bueno 60`: el eclipse dura 66 s con 11.5 cortes de la sombra (41 % de los golpes),
  dúos servidos 99-100 %, ningún anillo encimado y 0.9 s o más entre atacantes.
* `boss_sims/moon_sky_check.py`: capa máxima 6, ningún cuadro fuera de rango.
* `goro_avalanche_check.py`: ninguna ola sin salida, aviso mínimo 1.35 s.
* **El factor real/simulado no está medido para Mizuchi ni Kokuyō.** Gorō midió 0.71x con el bot de Unity sobre
  76be027 (el bueno ganó en 2:24 con 3.4 simulados). Mizuchi y Kokuyō suponen 1.4x. Si van a ~0.7x como Gorō, el
  bueno les gana en ~2.5 min reales y la hora de juego no llega. Es lo primero que hay que medir (ver 3, paso 9).
  *(Resuelto en la ronda de huecos, sección 5: el Editor.log tenía las ocho peleas del bot; los factores son Gorō
  0.71, Mizuchi 1.19, Kokuyō 0.92 y Chikuō 1.42, y la tabla de arriba quedó vieja: la de hoy está en 5.1.)*

### 1.4 Lo que encontró la integración

1. **[medio, arreglado en la sección 5: `GuardHitLow`] El desvío de Chikuō no encuentra la hoja del Corte final nuevo.** chikuo-feel ajustó
   `GuardHit` contra el Corte final de antes; kaito-snaps lo rehízo en paralelo (en el impacto la hoja va adelante y
   17° abajo, con las dos manos). Re-medido sobre la integración con el `swat2.py` del frente (scratch
   `c3/integration/swat`), cm de la palma (o del bastón) a la hoja y cuadros de 60 Hz a 15 cm o menos:

   | Corte | Fase | Kaito a | Antes (Attack3 de C2) | Ahora |
   |---|---|---|---|---|
   | Corte final | 1 | 1.40 m | 9.4 cm, 3 cuadros | 17.5 cm, 1 cuadro |
   | Corte final | 2 | 1.40 m | 9.4 cm, 4 cuadros | 17.5 cm, 1 cuadro |
   | Corte final | 3 (bastón) | 1.40 m | 6.8 cm, 4 cuadros | 15.1 cm, 0 cuadros |
   | Corte final | 1 | 1.60 m | 13.4 cm, 3 cuadros | 23.9 cm, 0 cuadros |
   | Corte final | 1 | 1.25 m | | 13.5 cm, 4 cuadros |
   | Corte 1 y Corte 2 | 1-3 | 1.40 m | sin cambio (7-15 cm, 3-6 cuadros) | igual |

   La hoja cruza 14 cm más abajo que antes (a 0.59 m del piso y no a 0.73) y la palma de `GuardHit` no baja tanto:
   ningún cambio de tiempo en el código lo arregla (con la hoja quieta en el hit-stop la palma pasa a 14 cm como
   mucho). Hay dos arreglos, los dos de un binario de otro frente, por eso no los hice acá: que el frente de Chikuō
   baje el encuentro de `GuardHit[_P2/_P3]` (o agregue una variante para el Corte final, elegida en `ReadCut` con
   `CutName == "Corte final"`), o que el de Kaito vuelva a cruzar a la altura de antes en f7. Desde la cámara del
   juego el encuentro queda detrás de Kaito, así que se nota menos que de costado (la tira de costado quedó en el
   scratch de la integración, `c3/integration/swat/rend/A3_F1_lado_1x.png`).
2. **[bajo, arreglado en `d083588`]** `BambooMasterBoss.RewardKaito` mostraba dos veces la cura del cambio de fase
   (`Heal` ya la muestra si de verdad curó). Kokuyō y Mizuchi lo arreglaron en su frente; quedaba Chikuō.
3. **[información]** Los cambios de goro-anim en `Enemy.Locomotion` (el margen del imán y el seguimiento con Kaito en
   el dash) también le llegan al sumo, que tiene `lungeShove` 0.6; son mejoras, pero el lint del sumo no las modela.
   A Chikuō no le llegan (avanza con su propio `Travel`), y Kokuyō y Mizuchi usan la embestida lineal, que no cambió.
4. **[información]** `c2_reports.md` describe C2: las vidas y daños de los cuatro jefes cambiaron en C3 (la tabla de
   1.3 es la de hoy).

---

## 2. Los frentes

### 2.1 `c3/goro-anim` (Gorō)

**Qué cambió**

* Los martillazos con paso (Combo1/2/3, Combo1B/2B/3B, SlamWave) avanzan en cuadros del clip (`AttackDef.lungeTo`,
  con `lungeFrom` = apex + 1) y terminan con el golpe: el martillo ya clavado no se arrastra. Es un paso de verdad:
  el pie de adelante sube 28 cm y apoya de talón, el de atrás queda clavado en la punta.
* Con Kaito que no se deja arrastrar (contra la barrera, una pared, otro enemigo o en el dash) el golpe sale en su
  variante en el lugar `<clip>Planted`: el mismo clip hasta el apex (0.2-0.9 cm el peor punto) y el mismo golpe sin
  recorrido. `Enemy.DecidePlant` lo decide 0.1 s antes de la suelta y lo anota en el Editor.log.
* `Goro()`: `lungeShove` 0.85 (el paso arrastra a Kaito entero) y `lungeSlack` 0.2.
* Armadura parda, sin nieve, que crece pareja de los dos lados; el mango por afuera de las piezas.
* Balance en un solo bloque de `GoroBoss` (`FirstBarHealth` 1900, `ArmoredHealth` 3040, `FirstBarDamage` 0.30,
  `ArmoredDamage` 0.25, `ShedHealAmount` 55), calibrado con el bot de Unity (0.71x). **Provisorio**: el paso de
  simulado a real salió de una pelea por bot.
* `GoroAnims.fbx` y `Kit_goro_armor.fbx` re-exportados con Blender 5.2 (24 clips bit a bit iguales a los del paso
  anterior del frente, más las 7 variantes al final). `build_team_anims goro`: 0 fallas, 39 avisos.

**Contratos**: estados `Combo1Planted` (1.8333 s), `Combo2Planted` (1.7333), `Combo3Planted` (1.7),
`Combo1BPlanted` (2.2333), `Combo2BPlanted` (1.7), `Combo3BPlanted` (2.1333), `SlamWavePlanted` (2.1333), con los
mismos tiempos que su base. `Enemy.PlantedSuffix = "Planted"`: cualquier enemigo con `<estado>Planted` en su
controller lo usa. `PlayerController.Shovable` y `PlayerController.ShoveRoom(dir, max, mover)`.

**Pruebas en Play**

1. Partida `prueba_goro.json` (ver `partidas/README.md`), `AutoPilot.Run("goto -195 118 12; talk 40; waitcontrol 30")`.
2. Kaito contra la barrera en la fase 1: con este RunCommand y después `AutoPilot.Run("tap Attack; wait 0.35; tap
   Attack; wait 0.35; tap Attack; wait 4")`:
   ```csharp
   Nindo.BossArena ar = null; foreach (var a in UnityEngine.Object.FindObjectsByType<Nindo.BossArena>(UnityEngine.FindObjectsSortMode.None)) if (a.archetype == "goro") ar = a; var g = (Nindo.GoroBoss)Nindo.Game.Combat.ActiveBoss; var c = ar.transform.position; var d = Nindo.Game.Player.transform.position - c; d.y = 0f; d = d.sqrMagnitude > 0.01f ? d.normalized : UnityEngine.Vector3.right; var k = c + d * (ar.radius - 0.55f) + UnityEngine.Vector3.up * 0.5f; var gp = k - d * 1.7f; gp.y = c.y; g.GetComponent<UnityEngine.AI.NavMeshAgent>().Warp(gp); g.transform.rotation = UnityEngine.Quaternion.LookRotation(d); Nindo.Game.Player.Teleport(k, UnityEngine.Quaternion.LookRotation(-d));
   ```
   Esperado: `[Nindo] Gorō: Combo1 en el lugar (libre 0.00 m, ...)` en el Editor.log; Gorō no avanza, pisa fuerte,
   el pie de atrás no patina, la panza no se le mete a Kaito y no hay tirón en la pausa de arriba del martillo.
3. Lo mismo en el medio del anillo (cambiar `ar.radius - 0.55f` por `4f`): sin el log; el paso arrastra a Kaito
   0.6-0.85 m. Decidir si 0.85 m se siente justo (si es mucho, bajar `lungeShove` en `Goro()`).
4. Fase 2: `((Nindo.GoroBoss)Nindo.Game.Combat.ActiveBoss).DebugArmor();` y repetir 2: Combo1B/2B/3B y SlamWave en
   el lugar, las rocas fuera de Kaito y la onda saliendo del martillo.
5. Dash de costado justo cuando baja el martillo: el pie de atrás no patina y el cuerpo no atraviesa a Kaito.
6. `bot on bueno` y `bot on promedio`: pegar las líneas `[Nindo] ... vencido en` del PlayClock (objetivo: bueno ~4.5
   min sin morir, promedio 1-2 muertes).

### 2.2 `c3/kaito-snaps` (Kaito)

**Qué cambió**

* Lint de `build_kaito`: cualquier hueso que gira más de 45° por cuadro del juego en escenas, o más de 60° en
  golpes, falla; se mide a la velocidad a la que el código toca cada clip. Exentos solo el golpe recibido, los
  tirones a propósito (`snap_ok`), los cortes de cámara y las piernas en un arranque.
* Solver: IK suave de los brazos, la katana que se suelta o se toma pareja de la mano, tramos `swing`, el codo
  izquierdo que cobra el giro de verdad (`rho_l`) y los timings `pin_l` y `settle_l`.
* Corte final: en el impacto (f7, el que congela el hit-stop) las dos manos en la empuñadura, la hoja adelante y 17°
  abajo; después la izquierda suelta y cae floja delante de la cadera.
* `EndFinisher`: el chiburi y el paso a la guardia van a x1 en los dos caminos (antes x1.7 / x2.8, 90-190° por
  cuadro). Es un gesto que el stick o un ataque cortan.
* `kaitooo.fbx` re-exportado con Blender 5.2.2: 0 FAIL en 33 clips; mismos nodos, curvas, rangos, eventos y .meta.

**Contratos**: Attack3 `pin_l` [7], `settle_l` [[8, 11]] (el resto del timing igual); Finisher `play_speed_fast`
[[0, 72, 2.8]]; Attack2 `apex` 2 (ningún código de Kaito lo lee); BandanaPower `hand_l_m.release` (-0.06, 0.72,
0.56), que usa `StoryDirector.Wall`. Campo nuevo del lint `snap_rage_max_deg` (aviso a x1.12, la furia).

**Pruebas en Play**

1. `AutoPilot.Run("pose Attack3 1; wait 1; pose Attack3 0.25")`: en f7 las dos manos en la empuñadura, ningún puño al
   lado de la cabeza; la izquierda cae floja y vuelve a la guardia sin retorcerse.
2. Delante de un ninja, `AutoPilot.Run("tap Attack x3 0.25; wait 1.5")`: dos manos en el hit-stop del tercer corte y
   los fundidos Attack2 a Attack3 y la vuelta a Idle limpios.
3. Con Filo de Ira, el mismo combo: el despegue del Corte final avisa 61-66° a x1.12; fijarse si se ve un latigazo
   del brazo derecho en f1-f4.
4. Remate corto: después de los 0.2 s en la pose, el chiburi a velocidad normal (~0.67 s) y el stick lo corta.
5. Remate cinemático y remate a un jefe: el chiburi a x1 (con jefe ~1.7 s de gesto, antes ~1.0); que no se sienta
   largo y que el stick lo corte.

### 2.3 `c3/chikuo-feel` (Chikuō)

**Qué cambió**

* Desvío (`HitResult.Deflected`): fuera de sus huecos aparta la hoja sin clang, sin empujón y sin castigo. Lee el
  corte (`ReadCut`, con `PlayerController.CutEta`): con la hoja a 0.1 s arranca el manotazo del lado por donde viene
  (`GuardHit`, o `GuardHitL` para el revés). El primer corte contesta a los 0.6 s, el segundo seguido a los 0.12 s
  (aunque esté descansando) y recién el tercero se contragolpea. Suena `palm_deflect` (sintetizado,
  `Tools/Audio/sfx_chikuo.py`).
* Paso del viento: el de frente vuela como poco la mitad del autorado; el que pasa al costado (el que sale contra el
  bot, que corre hacia él durante el salto atrás) volaba x0.3, ~2.7 m, hasta la ronda de huecos (sección 5.3); el
  carril sigue a Kaito hasta que despega y ahí se vuelve a planear el vuelo; el que pasa al costado (`DashStrike_Pass[_P3]`) nunca frena en el aire, se abre de costado
  (`PassAside`), sostiene la mano sobre Kaito de f17 a f20 y cae mirándolo. El golpe se prueba en el primer cuadro
  que pasa el contacto.
* El saco se desliza (formas `CoatSlip1..4` de `Master_Robe`, blend shapes) antes del cambio de malla.
* `poiseHits` 99: el contraataque de Kaito después de un parry mete 2 cortes (3 después de uno perfecto).
* `BambooMaster.fbx` re-exportado con Blender 5.2: 112 clips (5 más que en C2), FBX OK y ROUNDTRIP OK, los
  internalID de siempre.

**Contratos**: estados `GuardHitL`, `GuardHitL_P2`, `GuardHitL_P3` (0.5 s), evento `Deflect` en f3
(`swat_meet` 3); estados `DashStrike_Pass` y `DashStrike_Pass_P3` (1.2 s, iguales a `DashStrike` hasta f8), active
[17, 20]; `PlayerController.CutEta` y `CutName`; sonido
`palm_deflect`; `CutGoesLeft` decide por el nombre `"Corte 2"`.

**Pruebas en Play**

1. Reimportado `BambooMaster.fbx`, la consola sin errores.
2. `bot on bueno` con el PlayClock (la simulación da ~249 s) y `bot on promedio` (0.69 muertes).
3. Fase 1, un corte a la guardia: se inclina, la palma baja a la hoja a la altura del muslo y la lleva a su derecha;
   con el Corte 2 la derecha la sube a su izquierda (`GuardHitL`); un cachetazo suave, sin acero. Fase 2 (`chikuo
   fase 2`) con la mano libre, fase 3 (`chikuo fase 3`) con el bastón. **Mirar el Corte final en particular** (ver
   1.4, punto 1).
4. Dos cortes seguidos: los dos se apartan y Chikuō ataca enseguida; el contragolpe solo con el tercero.
5. `Debug.Log(Nindo.Game.Player.CutEta.ToString(System.Globalization.CultureInfo.InvariantCulture))` mientras Kaito
   corta: el manotazo arranca cuando baja de 0.1.
6. Fases 2 y 3, paso del viento con Kaito a ~2 m: el carril sigue a Kaito agachado y queda fijo al despegar; pasa al
   costado con la mano clavada ~4 cuadros y cae mirándolo. Caminando o corriendo de costado hacia el carril después
   del "¡ya!" no se queda colgado en el aire; con el dash se cruzan sin freno.
7. Kaito quieto a más de 5 m: embestida de frente que frena sobre él; contra el borde de la arena igual pega.

### 2.4 `c3/kokuyo-act3` (Kokuyō y Mizuchi)

**Qué cambió**

* Sustento antes que vida: Kokuyō cura `KokuyoMoves.StageHeal` (35 / 35 / 25) en cada corte de tramo y Mizuchi
  `MizuchiBoss.PostureHeal` (14) en cada postura rota. Vidas: Mizuchi 3240 (x2.25), Kokuyō 5400 (x3), daño x0.33.
* Eclipse: la sombra vuelve a la oscuridad y sale del otro lado (`EncoreChance` 0.6, `EncoreWindow` 3.2 s); los
  golpes de dúo que no podían salir se guardan y salen (`KageShadow.Rearming`); actos en 70 / 40 / 10.
* Reintento por acto: morir en el Acto 2 vuelve al 70 % y en el eclipse al 40 %, con arranque rápido (~2.7 s).
* Barra del acto: `Boss.BarFill01` (virtual, por defecto la vida), que usa `UIManager`.
* Luna: `MoonReturn` ya no corta la niebla de golpe (la luz entra de golpe, la niebla y el ambiente vuelven en 3 s)
  y `DriveSky` lleva el horizonte adelante de la niebla (`SkyHorizonLead` 12).
* Sims: `boss_sims/cs_knobs.py` lee las perillas del C# y falla si falta un nombre.

**Pruebas en Play**

1. Final: `AutoPilot.Run("kokuyo act 4")` y ejecutarlo en el arrodillado. A los ~4.2 s reales de la muerte vuelve la
   luna: la luz de golpe, la niebla y el cielo violetas que se aclaran en ~3 s, sin un cuadro en que el terreno lejano
   salte a la niebla del dojo ni una franja azul que lo recorte. En el sostenido,
   `Debug.Log(RenderSettings.fogColor + " " + RenderSettings.skybox.GetColor("_HorizonColor"))` tiene que dar una
   niebla todavía cerca de (0.118, 0.078, 0.188) y el horizonte casi igual.
2. Transición del eclipse desde una partida nueva (no desde un reintento): `AutoPilot.Run("kokuyo act 3")`. El
   horizonte se oscurece al violeta en ~0.3 s y el terreno lejano se funde con él; las crestas cercanas pueden
   quedar como siluetas más oscuras.
3. Si los cerros del plano de la muerte se leen como un corte plano: probar `e.fogDensity = arena.fogDensity * 1.6f`
   en `MoonEclipse.Eclipse` y ver si el Acto 3 se sigue leyendo bien.
4. Presentación con luna llena: el plano al cielo igual que antes.
5. Dúos del eclipse, segunda salida de la sombra, reintento por acto, la barra del acto que se vuelve a llenar, el
   primer arrodillado con un parry, la cura por tramo y el Último Desfile.
6. `bot on bueno` y `bot on promedio` en Mizuchi y en Kokuyō, pegando las líneas del PlayClock: es lo que calibra el
   factor real/simulado.

### 2.5 `c3/culling-dyn` (ZoneCulling)

**Qué cambió**: `ZoneCulling.AddDynamic(GameObject | Renderer | ParticleSystem)`. Quien crea algo después del armado
lo registra: el incienso de un santuario rezado en la partida, los braseros del patio, las rocas de la avalancha y
los pétalos del final. Se prueba cada cuadro con su caja de ahora; solo toma partículas en loop y mallas que tiran
sombra. Mientras maneja un loop le pone `AlwaysSimulate` y lo pausa él con una caja que no deja partículas afuera;
al volver se pone al día en pasos de 0.25 s (hasta 16). `On = false` les devuelve su modo. Contadores
`DynamicOn`/`DynamicTotal` en `Stats` y el HUD.

**Pruebas en Play** (respaldo de la partida antes):

1. `Nindo.ZoneCulling.ShowHud = true` y `Debug.Log(Nindo.ZoneCulling.Stats)`: aparecen "dinámicos" y las partículas
   simulando no cuentan lo que pausa Unity.
2. `Nindo.ZoneCulling.Benchmark(30f)` en los cuatro lugares de siempre, pegando la tabla.
3. Corte de cámara de golpe hacia los braseros del patio: sin chispas congeladas; la columna de humo de un
   santuario lejano vuelve con su forma (puesta al día).
4. Un destello (`Braziers.Flare`) con el brasero fuera de cuadro y un santuario rezado en plena partida: el incienso
   nuevo se registra.
5. `Nindo.ZoneCulling.CheckEvery(0.25f)` durante la presentación de Gorō, la avalancha y la grúa de la cascada: 0
   píxeles cambiados.
6. `Nindo.ZoneCulling.On = false` y de nuevo `true`: todo vuelve a su modo de Unity y después a la pausa de
   ZoneCulling. Con la vista Scene abierta también cuenta (`IncludeSceneView`).

### 2.6 `c3/docs-saves` (documentos y partidas)

* `reportes/c2_reports.md`: los informes de C2 por frente (contratos verificados contra el código de 76be027,
  chequeos y listas de Play), la integración, la ronda de huecos y lo que quedó abierto.
* `partidas/`: `prueba_goro.json` (cp_mountain_top), `prueba_mizuchi.json` (cp_lake_falls), `prueba_bambu.json`
  (cp_bamboo_gate), `prueba_kokuyo.json` (cp_dojo), `prueba_tarde_cp_lake_falls.json` (los tres sellos sin poner) y
  la de siempre, `prueba_juego_completo_cp_lake_falls.json`, que al cargar juega el final (ResumeEnding).
  `partidas/README.md` tiene cómo cargarlas, qué esperar y los pasos de AutoPilot. Validadas con un puerto en Python
  de la carga, no en el juego.

**Pruebas en Play**: cargar cada partida según `partidas/README.md` y ver el objetivo, que nada arranque solo y que
la presentación del jefe salga entera. Restaurar la partida del usuario (`nindo_save.json.respaldo`) al terminar.

---

## 3. Pruebas en Play para el lead, en orden

1. Respaldo de `nindo_save.json`. Abrir el proyecto: se reimportan `GoroAnims.fbx`, `Kit_goro_armor.fbx`,
   `kaitooo.fbx`, `BambooMaster.fbx` y los dos `palm_deflect`. La consola tiene que quedar sin errores ni avisos de
   clips que faltan (Goro.controller tiene 7 estados nuevos y BambooMaster.controller 5).
2. Un enemigo cualquiera: ninjas y sumos visibles a escala normal (el FBX de animación de Gorō sigue con
   `preserveHierarchy: 1`; si algo queda invisible o x100, es eso).
3. Gorō con `prueba_goro.json`: pruebas de 2.1.
4. Kaito: pruebas de 2.2 (Corte final, combo, furia, los tres remates).
5. Chikuō con `prueba_bambu.json`: pruebas de 2.3, mirando el desvío del Corte final de costado y desde la cámara
   del juego (1.4, punto 1).
6. Mizuchi con `prueba_mizuchi.json` y Kokuyō con `prueba_kokuyo.json`: pruebas de 2.4.
7. ZoneCulling: pruebas de 2.5.
8. Chikuō herido en un cambio de fase: un solo destello de cura (`d083588`).
9. **Balance**: `bot on bueno` y `bot on promedio` en los cuatro jefes (tres peleas por bot) y pegar las líneas
   `[Nindo] ... vencido en` en `Tools/Dev/boss_sims/calibration.py` (sección 5.1).
10. Las pruebas de la ronda de huecos (5.6).
11. Restaurar la partida del usuario.

---

## 4. Abierto después de C3

* *(La ronda de huecos de la sección 5 cerró el desvío del Corte final, el factor real/simulado de los cuatro jefes,
  el dash contra el cuerpo de Gorō y la hombrera del SlamWave. Lo que sigue abierto está en 5.7.)*
* **Gorō**: el balance es provisorio (una pelea por bot); el golpe en el lugar le roza la cabeza 0-3 cm con Kaito
  pegado a la cápsula; el martillo del golpe en el lugar cae 0.6-0.85 m más cerca (le pega el mango).
* **Kaito**: el brazo izquierdo del Corte final en f6-7 sigue en 83° (eximido por ir en la empuñadura); avisos a x1.12
  con furia (61-67°) en los cortes, el parry y los golpes recibidos; el remate corto a x2.8 avisa 68°.
* **Chikuō**: con Kaito pegado a 1.15 m de costado la cola del lazo y la canilla entran 2-7 cm en su cápsula (no en su
  malla); no es chibi (decisión de Felipe).
* **Kokuyō**: la silueta de los cerros cercanos en el plano de la muerte (24 niveles) es una decisión de look
  (densidad de la niebla del eclipse).
* **ZoneCulling**: la ganancia sigue sin medir en Unity.
* De antes: Amenoshita y Sakuya4 (PeriTune) se usan con la licencia general del autor, porque sus páginas no dicen
  licencia (la aprobación de Felipe para la música ya está en main, `e3fa891`); el pase de ambiente de Felipe (los
  basaltos que se leen como hielo); el kit y los clips del Ōzeki que ya no se usan.

---

## 5. La ronda de huecos de la integración (C3-A1 a C3-A5)

La auditoría de C3 dejó cinco huecos; los cerró la integración, en `c3/integration`, sin Unity (simulaciones, lints
de Blender, swat2.py y renders). Commits: `aebdb1d` (Gorō), `1ac3bef` (el factor real/simulado, Mizuchi y Kokuyō),
`74f62b1` (Chikuō: el roce, el paso del viento, las variantes de paso, la vida), `a278ead` (`GuardHitLow`).

### 5.1 El factor real/simulado de cada jefe (C3-A1)

En el Editor.log del lead (13 de octubre, main `76be027`, la fase C2) estaban las ocho peleas del bot: el PlayClock
y el resumen del driver. Corrí las simulaciones de ese mismo código (las de `76be027`) con las perillas de entonces:

| Jefe | bueno en Unity | bueno simulado (p10-p90) | F | promedio en Unity | promedio simulado | promedio calibrado |
|---|---|---|---|---|---|---|
| Gorō | 2:24, 0 muertes | 3.4 min (3.1-3.6) | **0.71** | 4:04, 2 muertes | 4.8 min, 1.45 | (goro_fight_sim: 0.78 y x1.37 en las muertes) |
| Mizuchi | 2:49, 0 | 2.37 min (2.04-2.82) | **1.19** | 3:27, 1 | 5.12 min, 2.0 | 7.1 min, 3.3 |
| Kokuyō | 1:48, 0 | 1.96 min (1.78-2.24) | **0.92** | 2:26, 0 | 6.06 min, 3.2 | 4.96 min, 2.2 (30 % sin morir) |
| Chikuō | 6:01, 0 | 254 s (235-277) | **1.42** | 15:50, 4 | 400 s, 1.0 | 758 s (p90 1107), 3.1 |

* El factor sale del bueno: su pelea casi no varía (±8 %), así que una pelea ya lo mide. No es uno solo: con Gorō el
  bot real le pega más que el modelo (se le pega a la cápsula) y con Chikuō menos (en Unity lo agarran el doble:
  24 golpes contra 12.5 simulados). El 1.4 que suponían Mizuchi y Kokuyō era el de Chikuō.
* La simulación calibrada pone el daño de Kaito en 1/F: reproduce el tiempo del bueno y predice el del promedio. Con
  Chikuō y Kokuyō lo medido cae adentro de lo calibrado; con Mizuchi el promedio de verdad anduvo mejor (lo calibrado
  es pesimista ahí). Todo en `Tools/Dev/boss_sims/calibration.py`; `--calib` en `sim_bamboo_master.py` y
  `'{"calib": true}'` en `mz_run.py` / `kk_fix_run.py`.
* Con eso, lo de hoy en minutos de juego (simulación calibrada, 200-300 peleas):

| Jefe | Perillas | bueno | promedio |
|---|---|---|---|
| Gorō | 1900 + 3040, daño x0.30 / x0.25, tramo 55 (sin cambios) | ~4.3 min | ~6.1 min, ~1.3 muertes |
| Mizuchi | vida x2.5 (3600), daño 0.33, postura que cura 18 (antes x2.25 y 14) | 4.5 min (3.9-5.0) | 7.3 min, 1.25 muertes, 32 % sin morir |
| Kokuyō | vida x4 (7200), daño 0.31, tramos 50 / 50 / 45 (antes x3, 0.33, 35 / 35 / 25) | 4.35 min (4.05-4.7) | 6.9 min (p90 10.5), 1.4 muertes, 29 % sin morir |
| Chikuō | 1900 (antes 2200) | 4.6 min (p90 5.0) | 7.3 min (p90 9.9), 1.0 muertes, 21 % sin morir |

* Kokuyō con 5400 ganaba en ~3.4 min de juego: subirle la vida sola dejaba al promedio en 4.5 muertes, por eso los
  tramos curan más. Los actos duran ~72 / 87 / 80 s con el bueno; el eclipse sigue sirviendo el 99 % de los dúos,
  ningún anillo se encima y la sombra hace el ~41 % de los golpes (`kk_fix_run.py actos`).
* Los cuatro jefes suman ~18 min para el bueno y ~28 min para el promedio. El resto de la partida no está medido.
* **Es provisorio**: una pelea por bot, y la de Chikuō con los rebotes de C2. Para medir de nuevo, con la partida del
  usuario respaldada: cargar `prueba_goro` / `prueba_mizuchi` / `prueba_bambu` / `prueba_kokuyo` (`partidas/README.md`),
  `bot on bueno` tres veces y `bot on promedio` tres veces por jefe, y pegar las líneas `[Nindo] ... vencido en` (en
  segundos) en `calibration.py`. Su docstring tiene la simulación cruda del código de hoy para sacar el factor nuevo
  (el bueno: Gorō 366 s, Mizuchi 232, Kokuyō 283, Chikuō 203) y lo que se espera ver.

### 5.2 Chikuō: el desvío del Corte final (C3-A2)

* `GuardHitLow`, `GuardHitLow_P2`, `GuardHitLow_P3` (nuevos, 0.5 s, `Deflect` en f3, `swat_meet` 3, de GUARD a GUARD):
  GuardHit con la reverencia más honda y la palma (la mano baja en la fase 2, el bastón en la 3) a la altura de la
  rodilla en f3, donde cruza la hoja del Corte final (0.59 m del piso, 0.65 m adelante).
* `BambooMasterBoss.PlaySwat(left, guarding, cut)` lo elige con `CutName == "Corte final"` (y `GuardHit` si el
  controller no lo tiene); la estela de jade y la chispa del desvío van a la altura de esa hoja (`SwatHighFinal` 0.59).
* swat2.py con el reloj del juego, palma (o bastón) a la hoja en el contacto: a 1.25 / 1.4 / 1.6 m, 2.8 / 5.8 / 12.2 cm
  (fases 1 y 2) y 4.2 / 5.7 / 11.3 cm (bastón), y 4 cuadros de 60 Hz a 15 cm o menos en los nueve casos (antes 17.5 cm
  y 1 cuadro a 1.4 m).
* `BambooMaster.fbx` re-exportado con 5.2: 115 clips, los 112 de antes con los mismos cuadros, tiempos y avance (solo
  `PoseTest` corrido), 0 avisos, FBX OK, ROUNDTRIP OK.
* Cuándo se ve: sobre todo como el tercer corte del contraataque después de un parry normal (el que ya no entra).

### 5.3 Chikuō: el paso del viento y las variantes de paso (C3-A3)

* La que pasa al costado sale casi siempre con Kaito a ~2 m (el bot corre hacia él durante el salto atrás: hacerlo
  despegar más lejos no cambia nada) y hasta el cruce vuela x0.3. Lo que estaba mal era el tramo de después: se
  escalaba con el mismo x0.3 y frenaba en seco al cortarlo (de 9.5 a 2.6 m/s). Ahora después del cruce vuela lo
  autorado (`PassTail` 1, sin salirse de la arena: `PassTailFor`) y cae ~2.4 m detrás de Kaito, mirándolo. Simulado:
  3.8 m de vuelo (antes 2.66, de 6.35 autorados), el cruce a su alcance siempre.
* Variantes de paso: contra el bot, que pelea a 1.2 m (el imán de su corte) o a 2.2 (donde para), el corto salía 9
  de cada 10 veces y por distancia era lo correcto. El golpe que abre un combo, una de cada cinco veces (`DriveChance`
  0.2), entra con el paso largo y corre a Kaito con el pecho hasta 0.45 m (`StepShove`), solo si hay lugar detrás
  (`ShoveRoom`) y si no viene con su corte ni en su dash. Bueno: 41 cortos, 8 medios y 7 enteros por pelea (2.8 a 1).

### 5.4 Chikuō: el roce del primer corte (C3-A4)

* El primero de una tanda que aparta con la palma igual lo roza: un cuarto del daño, un destello de 0.04 s y sin
  reacción (`Graze`, `GrazeShare` 0.25); nunca cruza el piso de la fase ni lo deja vencido. El segundo sigue haciéndolo
  contestar y el tercero se contragolpea.
* `sim_bamboo_master --human 0.5` (el que corta apenas lo ve): rechazados 59 % -> 36 % (bueno) y 62 % -> 37 %
  (promedio); el bot de AutoPilot, 43 % -> 23 %.
* Probé también un hueco al arrancar la respuesta (los cortes entran a x0.5 los primeros 0.35 s): 1-6 cortes por
  pelea y el rechazo casi igual. Quedó afuera.

### 5.5 Gorō (C3-A5)

* El dash contra el cuerpo: con Kaito en el dash se cruzan y el paso sale entero (`Enemy.TickLunge`, `crossing`; vale
  para todos los que avanzan en cuadros del clip). `build_team_anims` mide el caso (`dash_into_body_cm`, con Kaito
  empujado o no antes y el dash en cualquier décimo del paso): 0.0 cm en los 8 golpes con paso; 0 FAIL, 39 avisos.
* El aviso agachado del SlamWave llega a 1.55 m, pero no con el pecho (1.36 m, de f8 al apex): es la esquina de la
  hombrera izquierda, que baja con la mano que se apoya adelante, en el borde del radio de Kaito y a la altura de su
  cabeza (diagnóstico cuadro a cuadro de body_reach; el lint ahora anota el cuadro y la parte). Desde la pausa del aviso
  hasta la suelta, si Kaito está enfrente el cuerpo lo corre lo justo (`GoroBoss.ClearCrouch`, a lo sumo 1.2 m/s, con
  `Shove`), con los números del sidecar (`GoroTimings.SlamWaveCrouchFrom` / `SlamWaveCrouchReach`). GoroAnims.fbx
  no cambia.

### 5.6 Pruebas en Play de la ronda

1. Reimportar `BambooMaster.fbx` (115 clips): consola sin errores; el controller tiene `GuardHitLow`, `_P2` y `_P3`.
2. Chikuō, `prueba_bambu.json`: un parry normal a una palma y el combo entero: el tercer corte (el Corte final) se
   aparta con la palma baja, a la altura de la rodilla, y la estela de jade va sobre la hoja. Lo mismo en `chikuo fase
   2` (la mano izquierda) y `chikuo fase 3` (el bastón). Desde la cámara del juego queda detrás de Kaito: mirarlo de
   costado.
3. Un corte suelto a su guardia: la palma lo aparta, la barra baja un poco (2.5 de 1900 por corte) y destella. Tres
   seguidos: el tercero se contragolpea como antes.
4. Fases 2 y 3, el paso del viento con Kaito a ~2 m: le pasa al costado sin frenar en el cruce y cae ~2.4 m detrás de
   él, mirándolo. Cerca del borde de la arena vuela menos (no sale de la arena).
5. Palmas con Kaito pegado: una de cada cinco que abren un combo entra con el paso largo y lo corre hasta 0.45 m; contra
   la barrera nunca (el pie apoyado no patina).
6. Gorō, `prueba_goro.json`: en medio de un martillazo con paso, dash derecho contra su cuerpo: se cruzan y el pie de
   atrás no patina (mirar que el CharacterController de Kaito no salte al salir de la cápsula de Gorō). Fase 2
   (`DebugArmor()`), SlamWave con Kaito pegado enfrente: lo corre ~0.2 m mientras se agacha y la hombrera no le entra
   en la cabeza; contra la barrera no lo mueve.
7. Balance: lo de 5.1, tres peleas por bot y por jefe.

### 5.7 Lo que sigue abierto

* El balance es provisorio hasta medir con lo de C3 (5.1). El factor de Chikuō se midió con los rebotes de C2 y con
  Mizuchi el promedio calibrado es pesimista.
* La hora de juego: los jefes suman ~28 min para el promedio; el resto de la partida no está medido.
* SlamWave contra la barrera: con Kaito pegado ahí `ClearCrouch` no lo puede correr y la esquina de la hombrera le
  queda sobre la cabeza (unos centímetros adentro de su radio de 0.30 m, en el borde).
* El roce casi no se ve en la barra (2.5 de 1900): se nota por el destello.
* `GuardHitLow` a 1.6 m: 12.2 cm en el contacto (el objetivo era 12).
* El paso largo de las palmas sale al azar (una de cada cinco): el tiempo del golpe es el mismo, cambia solo cuánto
  corre a Kaito.
