# Fase C4: Chikuō nuevo, el Ermitaño de las Cañas

Rama `c4/chikuo` (con `c4/arena` fusionada). Diseño completo: `Docs/handoff/diseno/chikuo_v2.md` (las secciones 23 y 23.1
dicen qué quedó en el código y qué cambió después de la revisión). Nada de esto se probó en Unity: lo validado es offline
(compile_check, los chequeos de Blender del modelo y de los clips, el chequeo del FBX y la simulación de la pelea).

## 1. Qué es el Chikuō nuevo

El usuario pidió cambiarlo entero: el viejo era aburrido (la guardia, esperar, atacaba cada tanto). Ahora es un viejo
ermitaño excéntrico (la opción 6 del concepto: moño blanco con cordón verde, cejas en punta, barba anudada, capa de hojas
de bambú con cascabeles de caña, gi salvia con ribete de paja, la flauta-bastón) que **vive arriba de las cañas**:

* **Arriba** (fases 1 y 3): sopla dardos desde la punta de una caña o colgado cabeza abajo, salta de caña en caña en
  menos de un segundo, cae a golpear al piso (la Picada de la Grulla, roja; el Bastón que Cae, dorado) y vuelve a subir
  (trepando, de un salto o con la garrocha).
* **La mecánica de Kaito desde el piso: el latigazo.** A él no se le pega arriba: se le corta lo que lo sostiene. Cuando
  carga su caña (la ráfaga, el silbador, colgado, la risa, trepando, al agarrarse de un salto) los cascabeles laten en
  blanco y aparece un círculo blanco en la base: un corte ahí suelta el resorte y lo despide para el lado del corte. Si
  atrás hay otra caña a 6 m o menos (±26°), se estrella contra ella (el estampado, el hueco grande); si no, el revolcón.
  Cortarle la caña adonde salta, en los últimos 0.45 s del vuelo (0.60 en la fase 3), es la caída del cielo (el hueco más
  grande). Sin campanas, la caña barre ("¡Cosquillas!"). Nunca espera ni se cubre.
* **Tres fases que cambian la forma**: Las Cañas (100-65 %); El Piso (65-40 %: las seis cañas se inclinan 70° y tiemblan
  con la música, tandas de bastón sin guardia con el Paso del Ermitaño, la Grulla en el Bastón y Pregunta y Respuesta); El
  Bosque Entero (40-0 %: nace la Caña Madre, cada 9-12 s una firma: la tala de una caña rajada, la catapulta o la ráfaga de
  cuatro; dos latigazos a una caña la rajan y la quiebran; la Última Canción desde el 20 %).
* Se mantienen: 1900 de vida, id `bamboo_master`, arquetipo y bossId `ozeki`, `SealId.Bambu`, `boss_bamboo` en tres fases.

## 2. Lo que hizo esta ronda (los cuatro revisores)

Verifiqué cada hallazgo contra el código, el sidecar y la simulación. Arreglados:

**La pelea (código)**
* C4R-1: un corte en un hueco que cruzaba el piso de la fase pisaba PhaseBow/PhaseForest con el sacudón (las notas, la
  inclinación y el salto a la Madre pasaban en 0.3 s). `HoleHit` corta si la fase cambia.
* F1 / C4R-2: la Grulla y Pregunta y Respuesta se reagendaban solo al terminar normal; la contra de Kaito (Run) las
  cortaba y volvían apenas se levantaba. Se agendan antes de arrancar, como en la simulación.
* C4R-8: `ResetEnemy` limpia colgado, la revancha, las cosquillas, los relojes de la fase 2 y la 3, el foco de la cámara.
* C4R-3: el bot nunca paraba el Bastón que Cae (sin zona, `StrikeReach` viejo): ahora tiene el disco de su alcance donde
  cae. Además cada golpe nuevo borra la zona del anterior.
* F8: el anillo de los golpes desde la caña se cerraba en la base (donde está el círculo blanco de "cortá acá"): nuevo
  `Enemy.TellCenter` (hunk de 2 líneas) que usa `CombatTelegraphs`; Chikuō lo pone en el disco o a 3 m del carril.
* C4R-4: los cascabeles dorados quedaban prendidos 1-3 s después del último dardo: se apagan.
* C4R-5: la catapulta podía caer afuera de la barrera (y Boss.Update lo traía de un tirón): usa `FlingLanding`.
* C4R-7: el `AfterFlip` (0.25 s) se pisaba con 0.35: `GroundBrain` respeta el que ya puso la voltereta.
* C4R-9: con el hit-stop local la carga se apagaba antes que el clip (latigazo que salía "Cosquillas"): la carga espera.
* C4R-10: `chikuo mov soplo` ahora fuerza el Soplo (en la pelea del piso).
* C4R-11 y D14: los cortes que no valen (levantándose, en la garrocha, en el aire) suenan a cascabel suelto y sueltan
  hojas; los cortes en la armadura (x0.35) se notan (cascabeles, hit-stop de 0.04 s).
* T1: Climb estaba autorado para la caña de adentro (4.4 m): en N2, O2, E2 y la Madre los pies y las manos quedaban
  0.4-0.6 m corridos. `PlaceModel` corre el clip la diferencia y se la come hasta f24.
* D3 (la parte de código): colgado, el cuerpo cuelga a plomo alrededor de las rodillas (la caña arqueada 30° lo torcía).
* F9: la cámara ya no bombea con cada hueco en las fases de arriba (queda con el 60 % del foco del posado).
* F10: el latigazo tiene hit-stop (0.08 s) y vibración siempre; el estampado, 0.1 s al chocar. El dardo desviado suena
  `dart_snap` (nuevo, `Tools/Audio/sfx_chikuo.py dart_snap`); "thok" queda solo para las cosquillas. Sin cámara lenta en
  combate (la política de `TimeController`).
* T6: los cuadros de aterrizaje salen del sidecar (`ChikuoClip.LandN`, MissGrab con su `land`); los tiempos de la tala y
  de la pértiga viven en `BambooMasterMoves`.

**La forma de la pelea (código y simulación, los dos lados iguales)**
* F2: la fase 3 tiene su firma cada 9-12 s (la primera a los 5-7 s); la catapulta por pesos 1.0, cada 6 s, desde 4 m; la
  Última Canción desde el 20 %; respiro posado de la fase 3 0.10-0.20 s.
* F3: la vuelta de un hueco ya no es siempre la garrocha invulnerable de 1.3 s: kip-up de 0.25 s y, lejos (>= 6 m), un
  salto común atajable; cerca, 45 % garrocha, 30 % el agachado cortable (Tropiezo), el resto (Kaito a 4 m o menos) dos
  bastonazos con la Contra y trepa sin carga. Estampado a ±26°.
* F4: colgado con Kaito al pie, la carga prende 0.35 s antes del primer dardo (era un latigazo gratis antes de que
  existiera un dardo). Probé 0.15 s: el bueno tardaba 5.6 min y el promedio moría 3.3 veces.
* F5: caída del cielo 0.60 s en la fase 3 y el viejo mira la caña de destino 0.25 s antes de agacharse; `--fair` dice que
  los saltos de 5-9 m de la fase 3 se atajan desde 4.5-8 m. La pista dice "el círculo blanco" (no "ensō").
* F7: una voltereta cada 1.5 s como mucho; dentro de esa ventana aguanta el corte y contesta con una tanda. La voltereta es
  invulnerable entera.
* F6: el revolcón queda abierto 2.2 s con tope de 5 cortes (fase 3: 2.0 s), el daño a Kaito x0.9.

**Los clips y el modelo (reexportado `BambooMaster.fbx`, el mismo GUID, 32.3 MB, cuadros 1..2628)**
* D2: HangDart2 (la pose de la hoja del concepto) se hamaca de costado ±13 cm / ±14° como un péndulo de 0.6 s, toma aire
  con la cabeza atrás en cada punta, sopla al pasar por abajo y la punta patea (retroceso). Antes: 2 cm de recorrido.
* D3: la capa colgado cuelga hacia el piso (`cloak_max` 150° en HangDrop, HangDart2 y HangClimb: con el tope de 65° quedaba
  en horizontal, una bandeja alrededor de la cabeza). Mirar en Play: de frente todavía se abre bastante.
* D9: la guardia (Idle) rebota 8 cm con el peso de un pie al otro y la punta de la flauta dibuja ~30 cm; sentado mareado
  (DazedSit) la cabeza gira 20°, cabecea dormido y se despierta de un respingo.
* D10: las dos risas tiran la cabeza atrás (GroundLaugh -30°, PerchLaugh -26/-28°) y el doblez para adelante es corto.
* D1 (parte): la cáscara de la capa y su cara de adentro en verde hoja (`bamboo_dark`), no gris-teja ni gi oscuro.
* D15 (parte): el gi en el grass_teal del diseño (0.243, 0.42, 0.333): el salvia gris salía gris azulado de noche.
* D13: los signos de `bend` del sidecar ahora siguen la convención del código (positivo = lejos de Kaito): PerchIdle,
  dardos, tala, colgado, risa, barrido, catapulta. Solo cambia lo que mide el lint.
* T4 / C4R-6: Tres Ermitaños queda recortado del todo: sin `DecoySpin` (74 clips), sin `Chikuo_Decoy.mat`, sin
  `extra_materials`. Registrado en el diseño 23.1.
* T3: README, HANDOFF, `generate_assets.py`, `calibration.py` ya no hablan de la pelea vieja; `Tools/Blender/bosses/
  bamboo_master/` (el Chikuō viejo, que nadie importaba) se borró.

**Falsos o descartados**
* T5 (la compresión de animación): el .meta ya usa errores de 0.05° / 0.05 % (diez veces más finos que el 0.5 de Unity
  que supuso el revisor): 0.05 % de 3.6 m son 1.8 mm, no 1.8 cm. Queda como está.

## 3. Números

`python Tools/Dev/chikuo_v2_check.py --runs 400 --seed 7 --calib F` (lo que mide el PlayClock):

| F | bueno | promedio | experto |
|---|---|---|---|
| 1.41 (el Chikuō viejo, el único medido) | 4.9 min (p10 4.3, p90 5.5), 0.01 muertes | 7.3 min (p10 5.3, p90 10.0), 1.20 muertes, 15 % sin morir | 4.5 min |
| 1.30 | 4.6 min | 6.7 min, 0.94 muertes | 4.3 min |
| 1.0 (cruda: `calibration.py` MEASURED['chikuo_v2']) | 3.6 min | 4.3 min, 0.33 | |

Con F 1.41: fases del bueno 119 / 43 / 128 s; un latigazo cada 13 / 15 / 12 s (revolcón 12.7, estampado 5.0, caída del
cielo 0.5 por pelea); 38 / 48 / 37 amenazas por minuto fuera de los huecos; 18 % de tiempo muerto, el tramo más largo 1.65 s.
Las muertes del promedio caen casi todas en la fase 3 (0.94 de 1.20). El objetivo del lead (bueno 4.5-5, promedio 1-2
muertes en 7-9 min) se cumple con F 1.41; con 1.3 el promedio queda corto (0.94 muertes, 6.7 min).

## 4. Contratos

* **Las cañas** (rama c4/arena): `ArenaStalk.All` / `ArenaStalk.Get("N1"|"N2"|"O1"|"O2"|"E1"|"E2"|"M")`, con `PerchNode`,
  `GripHigh`, `ClimbGrip`, `BaseCut`, `SetBend`, `SetGlint`, `SetCracked`, `SetBroken`, `SetRise`. La pelea las maneja con
  `BambooStalk` (el resorte de 1.4 Hz) y `BambooGrove`.
* **Los clips**: 74 más BindPose, nombres, cuadros y eventos en el sidecar `BambooMaster.fbx.json` y `ChikuoTimings.cs`
  (generado por `Tools/Unity/chikuo_timings.py`; nuevo campo `LandN`). El núcleo: PerchIdle 48f; PerchDart 24f DartSpawn@14;
  PerchVolley 51f Load@3 DartSpawn@17,28,39 Unload@42; HangDrop 11f Hang@10; HangDart2 18f DartSpawn@9,18; HangClimb 15f
  Unload@8 Perch@15; LeapCrouch 7f; LeapAir 12f loop; LeapGrab 6f; Climb 24f GrabStalk@4 Perch@24; Dive 29f LeaveStalk@10
  Contact@28; StaffDrop 27f LeaveStalk@6 Land@19 Contact@26; Vault 27f Plant@6 LeaveStalk@9 GrabStalk@27.
* **Perillas**: todas en `BambooMasterMoves` con el mismo nombre que en el `P` de `chikuo_v2_check.py`. Nuevas:
  `SignatureFirst/Every`, `CatapultMinDist/Every/Weight`, `HangNearLoadLead`, `CatchWindow[]`, `LeapLook[]`, `GetUpTime`,
  `RecoverLeapDist/Vault/Crouch/TandaDist`, `RecoveryTanda()`, `FlipEvery`, `RevolconOpen[]`, `RevolconCap`, `PoleLoadFrom`,
  `PoleLeaveAt`, `TalaFix`, `TalaImpact`. `DamageScale` 0.9, `LastSong` 0.20, `StampAngle` 26.
* **Enemy**: `public virtual Vector3 TellCenter` (nuevo) y `HeadPoint` (de la ronda anterior).
* **AutoPilot**: `chikuo fase N | cana ID | salto ID | mov dardo|dos|notas|silbador|colgado|risa|picada|baston|barrido|
  catapulta|tala|pertiga|pregunta|soplo | abrir revolcon|estampado|caida|resbalon|afinado|pies | canas [reset]`.
* **Sonido**: `dart_snap` (2 variantes) se suma a las 35 claves de `sfx_chikuo.py`.

## 5. Lo que sigue débil (dicho de frente)

* **Nada se corrió en Unity.** El factor real/simulado de esta pelea no se conoce: el balance vale lo que valga suponer
  el 1.41 del Chikuō viejo.
* **Más largo que Kokuyō**: con F 1.41 el bueno tarda 4.9 min y `calibration.py` espera ~4.4 para Kokuyō, que tiene que ser
  el más largo. Si manda eso y no el objetivo de 4.5-5 min: el revolcón 2.4 s o las caídas x1.5 (tabla `--knobs`).
* **141 chequeos de clips siguen fallando** (eran 144; el sidecar los lista en `lint_failures`). Los que más se van a ver:
  PoleDive (la flauta pasa del pie a la mano con un giro de 154° en f13: `chikuo mov pertiga`), los tirones de 90-127° del
  puño en FeetStuck f40, Vault f11, LowSweep f31, Detuned f8, HangDrop f9, Slip f10; la flauta 14 cm adentro del cuerpo en
  Vault f5 y PhaseForest f119; las canillas adentro del culmo colgado (hasta 9 cm). No los toqué: cada uno pide rehacer el
  manejo de la flauta del clip (D4 / T2).
* **Sin rehacer** (los hallazgos de modelo y de clips que piden un paso de animación propio): la cáscara de la capa sigue
  siendo una sola pieza (D1: partirla por paneles y limitar el ángulo entre paneles), las poses de aviso que no muestran el
  arma desde la cámara (D5: el Bastón que Cae levanta el bastón recién en f24; la cerbatana se proyecta sobre el culmo), los
  cascabeles en filas (D6), la cabeza de perfil (D7), el ribete en "A" y el pantalón en cuadrícula (D8), LeapAir y la
  patada de la catapulta (D11), los dedos en la flauta (D12), los zapatos chicos (D15). Hit y HitHeavy siguen sin usarse
  (la armadura no tiene capa de torso en el controller).
* Colgado: de frente la capa todavía se abre como un disco; de perfil ya cae. Y el aplomado alrededor de las rodillas
  está calculado sin verlo: mirar que no salte al entrar o salir del colgado.
* El gi teal y la cáscara verde se eligieron por el diseño (sección 14) y no se compararon con el arena de noche en una
  imagen del juego.
* La simulación nunca vio la vuelta con dos bastonazos terminar en la Contra con garrocha (el código hace eso; la
  simulación trepa): diferencia chica.

## 6. Plan de prueba en Play (para el lead)

Antes: copiar `%USERPROFILE%/AppData/LocalLow/DefaultCompany/Nindo/nindo_save.json` aparte, reimportar
`BambooMaster.fbx` y el controller (cambió: 81 estados, sin DecoySpin), cargar `Docs/handoff/partidas/prueba_bambu.json`,
Play, `Nindo.AutoPilot.Run("wait 0.5; tap Submit")`, Kaito a (122, 2, 150) y
`Nindo.AutoPilot.Run("goto 124 156 20; talk 40; waitcontrol 30")`. Consola sin errores ni "falta Seg_".

1. **Tamaño y colores**: Chikuō a escala normal, sin x100. El gi tiene que leerse verde (no gris azulado) contra el piso
   del claro; la capa abierta (golpes, saltos) no puede verse como una lona oscura.
2. **Colgado**: `Nindo.AutoPilot.Run("chikuo mov colgado")` en O1 y en O2. Cuelga a plomo (no torcido 30°), se hamaca de
   costado, la cabeza va y viene con cada soplido, la capa cae. Al entrar y salir del colgado el cuerpo no salta. Con Kaito
   a 2 m de la base: el círculo blanco prende recién justo antes del primer dardo (cortar antes da "¡Cosquillas!").
3. **Trepar en todas las cañas**: `chikuo cana N2`, después un hueco (`chikuo abrir revolcon`) cerca de O2/E2: si trepa, los
   pies arrancan en el piso y las manos en el culmo (no 40 cm arriba).
4. **La vuelta de un hueco**: varias veces `chikuo abrir revolcon` con Kaito cerca y lejos: se levanta rápido y vuelve de
   formas distintas (garrocha, agachado que se puede cortar, dos bastonazos dorados; lejos, un salto con su círculo blanco).
5. **La Grulla y la Pregunta no se repiten**: `chikuo fase 2`, cortar el bastón de la Grulla con las campanas blancas: el
   revolcón, y la próxima Grulla recién 8-11 s después. Lo mismo con `chikuo mov pregunta` y un corte (Desafinado).
6. **El cambio de fase desde un hueco**: con vida apenas arriba del 65 %, dejarlo sentado y cortarlo: la escena PhaseBow
   entera (tres notas, las cañas que se inclinan), sin el sacudón del corte encima.
7. **El anillo**: `chikuo mov silbador` y `chikuo mov picada`: el anillo rojo se cierra en el carril o en el disco, no
   adentro del círculo blanco de la base. Los cascabeles dorados se apagan cuando el dardo ya pegó o se clavó.
8. **Bastón que Cae con el bot**: `bot on bueno` y `chikuo mov baston` varias veces: el bot lo para (antes nunca).
9. **Fase 3**: `chikuo fase 3`: una firma cada 9-12 s (catapulta, tala con una caña rajada, ráfaga de cuatro); la catapulta
   con Kaito contra la barrera cae adentro, sin tirón. `chikuo salto N1` con Kaito al pie de N1: el viejo mira la caña antes
   de agacharse y cortar en los últimos 0.6 s lo tira (caída del cielo).
10. **El piso**: en la fase 2, perseguirlo con dash después de cada corte: una sola voltereta cada 1.5 s, después aguanta y
    contesta. Los cortes que no valen (levantándose) suenan a cascabel; los de la armadura se notan.
11. **Balance**: `bot on bueno` y `bot on promedio`, tres peleas cada uno; pegar las líneas `[Nindo] Chikuō vencido en` en
    `Tools/Dev/boss_sims/calibration.py` MEASURED['chikuo_v2'] (la simulación cruda ya está: 214 s y 255 s con 0.33) y
    correr `python Tools/Dev/chikuo_v2_check.py --runs 400 --calib F`. Objetivo: bueno 4.5-5 min, promedio 1-2 muertes en
    7-9 min; si hay que tocar, la tabla `--knobs`. Restaurar el save del usuario al final.

## 7. Hunks en archivos compartidos (esta ronda)

* `Enemies/Enemy.cs`: `public virtual Vector3 TellCenter => transform.position;` (2 líneas, debajo de `HeadPoint`).
* `FX/CombatTelegraphs.cs`: `t.center = e.TellCenter;` (1 línea).
* `Story/StoryText.cs`: la pista `bamboo_deny` dice "el círculo blanco" en vez de "el ensō blanco".
* `Resources/NindoContent.asset`: la clave `dart_snap` en la lista de efectos y la fila de `bamboo_master` sin `DecoySpin`
  (los dos los escribe `Tools/Unity/chikuo_assets.py --sfx`).
* `Tools/Unity/generate_assets.py`: dos docstrings (el sidecar lo escribe `build_chikuo.py`; los `extra_materials`).
* `Tools/Dev/boss_sims/calibration.py`: las referencias a `sim_bamboo_master.py` y los números crudos de `chikuo_v2`.
* `README.md` y `Docs/HANDOFF_PROXIMA_SESION.md`: el párrafo de Chikuō y la lista de archivos.
