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

## 2. Segunda ronda de arreglos (lo que quedaba abierto)

Commits db6443d, d30e737, eb9c75a, 15a2038 y 952ec8a. Nada se probó en Unity: compile_check, el lint de
los clips, check_chikuo_fbx, la ida y vuelta del FBX y la simulación.

**La capa (D1, D3)**
* La cáscara era una sola pieza de 20x7: cuando los paños se separaban (golpes, saltos, colgado) se estiraba en una lona
  plana más ancha que el cuerpo. Ahora son doce paños sueltos (uno por hueso de la capa, con una ranura de 1.6° y pesados
  enteros a su hueso), dos hojas largas tapan cada ranura y la cara de adentro va en el verde medio (`moss`).
* En el horneado (chikuo_anim): el levante de un paño llega a 35° (era 65°) y dos paños vecinos no se apartan más de 25°
  entre sí (`clamp_cloak`). Donde la capa toca el piso (sentado, tirado, caído) se hornea de nuevo con el tope de 65° y
  sin el tope entre vecinos: si no, el piso y el tope se peleaban y la capa se metía en el piso o saltaba.
* Colgado (HangDrop, HangDart2, HangClimb, la clave nueva `cloak_free`): cada paño cuelga solo hacia el piso. Con el giro
  común de la capa los tramos del yugo, que salen de costado, giraban sobre su eje y quedaban en horizontal: el disco
  de la crítica. Ahora la capa cae (clip_HangDart2.png); la barba blanca se ve al costado de la cerbatana.

**Los cascabeles y la espalda (D6)**: la tabla `CHIMES` va en racimos de dos y tres, los agudos en dos racimos por hombro
(1.64-1.86 m) y los graves por toda la espalda (0.98-1.85 m), con huecos de 9 a 22° y tubos de 0.16 a 0.30 m. La espalda
se abre hacia abajo como una parva (el perfil de 135° llega a r 0.44 y el de atrás a 0.37 en z 0.45) y las hojas van por
pisos, de claro arriba a oscuro abajo, menos y más grandes. La capa quedó en 2478 triángulos (el presupuesto es 2500).

**El salto y la catapulta (D11)**
* `AIR` (la pose del salto entre cañas) va abierta de piernas: la rodilla izquierda alta adelante, la derecha estirada atrás
  con la rodilla abajo. LeapAir pedalea 10 cm y la capa flamea hacia atrás (horneada a 0.25 m por cuadro y con la tela
  arrastrada al 55 %: antes colgaba a plomo).
* CatapultKick: de f5 a f11 la patada voladora del concepto (`dive_kick`): echado atrás 56° en línea con la pierna derecha,
  que va por el carril con la punta a ~1.05 m delante de la cadera, los brazos atrás y el cuerpo girado 25° para la cámara.
  En f13 recoge y en f15 toca de talón como pide DiveLand (en el Contact la punta queda a 0.9 m, no a 1.0: la pose la
  comparte el aterrizaje).

**Colgado que sopla (D2)**: el vaivén es de ±16 cm y ±16°; antes de cada dardo toma aire (f7-f8 y f16-f17: la cabeza a
-32/-34°, el pecho atrás, los cachetes inflados, la punta sube 6-7°), sopla de golpe (f9 y f18) y la punta patea 11° (f10).
En las puntas del vaivén la cerbatana va con el cuerpo (-16° y +20°: quieta en el mundo doblaba la muñeca). No se tocó el
plan del giro de la izquierda.

**Los avisos (D5)**
* El Bastón que Cae tiene la flauta parada sobre la cabeza desde f14 hasta f20 (el aviso: una línea vertical contra el
  piso, desde la cámara alta); la echa atrás en f21, pasa por adelante en f23 y pega en f26. Antes la tenía tendida detrás
  de la cabeza hasta f24 y del aviso al golpe giraba 84° en un cuadro.
* La cerbatana posada: mientras sopla (desde TellStart de PerchDart, Dart2, Volley, Volley4 y Whistle) el cuerpo gira sobre
  los pies hasta 20° hacia el lado de la pantalla al que ya apunta, según cuánto mira hacia la cámara
  (`BambooMasterBoss.AimYaw`, `BambooMasterMoves.AimYaw`); el dardo igual sale a Kaito. La hoja de avisos lo copia: la punta
  queda a 60-75 px del culmo (tells_blowpipe.png).

**Los clips (D4 / T2)**
* La flauta que pasa de un agarre a otro girando sobre el puño era la causa de casi todos los tirones grandes. Ahora la
  tira y la ataja (`tossed` en chikuo_clips, con `arc` para que pase por afuera del cuerpo): la picada desde la pértiga
  (la patea con los dedos del pie y la ataja en los hombros), la garrocha (clavada 1.2 m adelante y menos tendida; suelta
  primero la derecha, la izquierda la arranca del piso), los Pies Enterrados al salir, el aterrizaje de la picada, colgarse
  y descolgarse, el agarre del salto, el agachado de la vuelta arriba y el resbalón. El mortal cruza la flauta delante del
  pecho (la de la guardia se clavaba 17 cm en el piso). La barrida de bastón gira pareja (~33° por cuadro) y la pierna
  vuelve a la guardia rodeando el pie de apoyo. El kip-up cae con la flauta ya en el ángulo de la guardia.
* El IK del brazo no confía en el lado del codo con el brazo casi estirado (daba vuelta el brazo 126° en un cuadro), y
  `Kit` mide cada pose sin lo que el solver recordaba de la medida anterior (las flautas tiradas apuntaban a medio camino).
* El lint mide la flauta también contra el pecho (en un mortal gira con él: no es un tirón).
* Resultado: 141 fallas -> 115 (tirones 34 -> 29, sin clases nuevas). De la lista de la crítica quedaron arreglados PoleDive
  (154°, la mano a 24 cm), FeetStuck (127°), Vault (121°, la flauta 14 cm en el pecho), LowSweep (103°, 12 cm), StaffDrop
  (84°), HangDrop (92°), JumpCrouch (90°), LeapGrab (87° -> 62°), GetUp (84° -> 57°), Slip (90° -> 46°), BackFlip, HopBack
  y DiveLand.

**La fase 3 (F2)**: los dardos posados van a x1.2 (`PerchRate`), un soplido de cada dos sale en abanico (dos dardos más a
1.6 m del de Kaito, de costado: `Fan`, `FanM`, `FireDart(fan)`) y la firma de la ráfaga de cuatro con Kaito a 7 m o menos
sigue sin respiro con la Picada (`SignatureChain`). La simulación copia las tres cosas.

**F6 (Kokuyō el más largo)**: sigue siendo decisión del lead. Medido: el revolcón a 2.4 s solo baja el bueno 4 s (4.8 min),
no es la perilla; las otras de la tabla `--knobs` siguen valiendo.

## 3. Primera ronda de arreglos (los cuatro revisores)

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

## 4. Números

`python Tools/Dev/chikuo_v2_check.py --runs 400 --seed 7 --calib F` (lo que mide el PlayClock), después de la segunda ronda:

| F | bueno | promedio | experto |
|---|---|---|---|
| 1.41 (el Chikuō viejo, el único medido) | 4.9 min (p10 4.3, p90 5.5), 0.00 muertes | 7.3 min (p10 5.5, p90 10.3), 1.23 muertes, 12 % sin morir | 4.6 min |
| 1.0 (cruda: `calibration.py` MEASURED['chikuo_v2']) | 3.6 min (213 s) | 4.3 min (255 s), 0.32 | |

Con F 1.41: fases del bueno 119 / 44 / 131 s; amenazas por minuto fuera de los huecos 37 / 48 / 54 (promedio 37 / 50 / 52,
experto 40 / 48 / 58): la fase 3 ya es la más densa (era 37 / 48 / 37). Ojo: los dos dardos de costado del abanico cuentan
como amenazas aunque casi nunca pegan (el bot está donde apunta el del medio): lo que hacen es no dejar esquivar corto
hacia el costado; por eso el tiempo y las muertes casi no cambiaron. 18 % de tiempo muerto, el tramo más largo 1.67 s. Las
muertes del promedio caen casi todas en la fase 3 (0.91 de 1.23). El objetivo del lead (bueno 4.5-5, promedio 1-2 muertes
en 7-9 min) se cumple con F 1.41.

Lint de los clips (el sidecar los lista en `lint_failures`): 141 -> 115 (muñecas 44, tirones 29, cuerpo contra sí mismo 23,
culmo 8, piso 4, alcance 3, otros 4).

## 5. Contratos

* **Las cañas** (rama c4/arena): `ArenaStalk.All` / `ArenaStalk.Get("N1"|"N2"|"O1"|"O2"|"E1"|"E2"|"M")`, con `PerchNode`,
  `GripHigh`, `ClimbGrip`, `BaseCut`, `SetBend`, `SetGlint`, `SetCracked`, `SetBroken`, `SetRise`. La pelea las maneja con
  `BambooStalk` (el resorte de 1.4 Hz) y `BambooGrove`.
* **Los clips**: 74 más BindPose; nombres, cuadros y eventos sin cambios en esta ronda (sidecar `BambooMaster.fbx.json` y
  `ChikuoTimings.cs`, generado por `Tools/Unity/chikuo_timings.py`; cambiaron los `RootOffset` de LeapCrouch, LeapGrab, Vault,
  JumpCrouch y PhaseForest y el avance de Vault). El núcleo: PerchIdle 48f; PerchDart 24f DartSpawn@14; PerchVolley 51f
  Load@3 DartSpawn@17,28,39 Unload@42; HangDrop 11f Hang@10; HangDart2 18f DartSpawn@9,18; HangClimb 15f Unload@8 Perch@15;
  LeapCrouch 7f; LeapAir 12f loop; LeapGrab 6f; Climb 24f GrabStalk@4 Perch@24; Dive 29f LeaveStalk@10 Contact@28;
  StaffDrop 27f LeaveStalk@6 Land@19 Contact@26 (apex f20); Vault 27f Plant@6 LeaveStalk@9 GrabStalk@27; CatapultKick 15f
  Contact@15.
* **Perillas** (`BambooMasterMoves`, el mismo nombre en el `P` de `chikuo_v2_check.py`). De esta ronda: `AimYaw` 20 (no está
  en la simulación: no cambia tiempos), `SignatureChain` 7 m (`signature_chain`), `PerchRate` {1, 1, 1.2} (`perch_rate`),
  `Fan` {no, no, sí} y `FanM` 1.6 m (`fan`, `fan_m`). De la primera: `SignatureFirst/Every`, `CatapultMinDist/Every/Weight`,
  `HangNearLoadLead`, `CatchWindow[]`, `LeapLook[]`, `GetUpTime`, `RecoverLeapDist/Vault/Crouch/TandaDist`,
  `RecoveryTanda()`, `FlipEvery`, `RevolconOpen[]`, `RevolconCap`, `PoleLoadFrom`, `PoleLeaveAt`, `TalaFix`, `TalaImpact`,
  `DamageScale` 0.9, `LastSong` 0.20, `StampAngle` 26.
* **El código**: `FireDart(bool fan = false)` (el abanico: dos dardos más sin aviso propio), `FirePerchDart()` (DartAct:
  alterna el abanico en la fase 3), `AimYaw()` en `PlaceModel`, `chainDive` (la firma encadenada, después de `DoPerch` en
  `PerchTurn`; se limpia en `ResetEnemy` junto con `fanFlip`).
* **Enemy**: `public virtual Vector3 TellCenter` y `HeadPoint` (rondas anteriores).
* **La tubería de Blender**: la clave de clip `cloak_free` (cada paño de la capa cuelga solo); `CLOAK_LIFT` 35°,
  `CLOAK_PAIR` 25°, `CLOAK_FLOOR_LIFT` 65° y `clamp_cloak` en chikuo_anim; `tossed(kit, A, B, t, lift, side_of_b, arc)` y
  `spine_mix(a, b, t)` en chikuo_clips; el ruedo de la capa se le pide al piso 0.33 m debajo de la cola del último tramo; el
  lint mide la flauta contra la raíz y contra el pecho; las hojas de avisos giran la cerbatana posada como el código.
* **AutoPilot**: `chikuo fase N | cana ID | salto ID | mov dardo|dos|notas|silbador|colgado|risa|picada|baston|barrido|
  catapulta|tala|pertiga|pregunta|soplo | abrir revolcon|estampado|caida|resbalon|afinado|pies | canas [reset]`.
* **Sonido**: `dart_snap` (2 variantes) se suma a las 35 claves de `sfx_chikuo.py`.

## 6. Lo que sigue débil (dicho de frente)

* **Nada se corrió en Unity.** El factor real/simulado de esta pelea no se conoce: el balance vale lo que valga suponer
  el 1.41 del Chikuō viejo. El giro de la cerbatana (`AimYaw`), el abanico y la firma encadenada están compilados y
  simulados, no vistos; el aplomado del colgado alrededor de las rodillas tampoco se vio en movimiento.
* **Más largo que Kokuyō**: con F 1.41 el bueno tarda 4.9 min y `calibration.py` espera ~4.4 para Kokuyō, que tiene que ser
  el más largo. Es decisión del lead; el revolcón a 2.4 s no alcanza (4.8 min), quedan las caídas x1.5 o el daño de
  Kaito (tabla `--knobs`).
* **115 chequeos de clips siguen fallando.** Los tirones más grandes que quedan: Intro (la capa 177° en f157, una vez por
  pelea), PhaseForest (la mano 121° en f122) y PhaseBow (el antebrazo 105° en f57), que son escenas de cambio de fase;
  Detuned (un cascabel 98° en f32), MissGrab (la mano 90° en f11), PoleFall (la tibia 85° en f8), HangClimb (la capa 83° en
  f9), StaffSpin2 (el brazo 81° en f15 y la muñeca izquierda en 2.1 todo el giro). Las 44 muñecas son en general agarres
  forzados de 1.4-2.4 (el tope es 1.35). Colgarse y descolgarse siguen con los pies girando 66° en un cuadro (HangDrop f8:
  la vuelta de 180° sobre el culmo en cuatro cuadros) y las canillas 9 cm adentro del culmo en HangClimb f9.
* **Colgado desde la cámara del juego**: la capa ya cae, pero la cara todavía queda en parte tapada desde arriba (la
  cabeza está adentro del cono de hojas). La crítica proponía girar la cabeza 15-20° hacia la cámara: no lo hice.
* **Sin rehacer** (hallazgos del modelo que no estaban en esta ronda): la cabeza de perfil (D7), el ribete en "A" y el
  pantalón en cuadrícula (D8), los dedos en la flauta (D12), los zapatos chicos (D15). Hit y HitHeavy siguen sin usarse.
* El gi teal y la cáscara verde no se compararon con el arena de noche en una imagen del juego (las hojas de avisos usan
  un fondo gris).
* La simulación nunca vio la vuelta con dos bastonazos terminar en la Contra con garrocha (el código hace eso; la
  simulación trepa): diferencia chica.

## 7. Plan de prueba en Play (para el lead)

Antes: copiar `%USERPROFILE%/AppData/LocalLow/DefaultCompany/Nindo/nindo_save.json` aparte, reimportar
`BambooMaster.fbx` y el controller (81 estados), cargar `Docs/handoff/partidas/prueba_bambu.json`, Play,
`Nindo.AutoPilot.Run("wait 0.5; tap Submit")`, Kaito a (122, 2, 150) y
`Nindo.AutoPilot.Run("goto 124 156 20; talk 40; waitcontrol 30")`. Consola sin errores ni "falta Seg_".

Lo nuevo de la segunda ronda (A-G), después lo de la primera (1-11):

* A. **La capa**: escala normal, sin x100. En los golpes y los saltos la capa se abre en paños con hojas en las ranuras,
  sin una lona plana más ancha que el cuerpo; quieto, de espaldas, no se ven agujeros entre paños; los cascabeles de la
  espalda cuelgan en racimos a distintas alturas.
* B. **Colgado**: `chikuo mov colgado` en O1 y O2: la capa cae hacia el piso paño por paño (no un disco); antes de cada
  dardo echa la cabeza atrás e infla los cachetes, sopla de golpe y la punta patea.
* C. **La cerbatana posada**: `chikuo mov dardo`, `dos` y `notas` con Kaito al sur de la caña (hacia la cámara): el cuerpo
  gira ~17° y la cerbatana se despega del culmo en pantalla; el dardo igual va a Kaito. Con Kaito al este u oeste no gira.
* D. **El Bastón que Cae**: `chikuo mov baston`: la flauta parada sobre la cabeza desde el aire hasta que pisa, la echa
  atrás y baja en cinco cuadros.
* E. **La picada desde la pértiga**: `chikuo fase 2` y `chikuo mov pertiga`: patea la flauta con el pie, da vuelta en el
  aire y la ataja en los hombros; la mano no gira sobre el caño.
* F. **Las vueltas de un hueco**: `chikuo abrir revolcon` varias veces, cerca y lejos: la garrocha (clava 1.2 m adelante,
  suelta primero la derecha, arranca la flauta con la izquierda, la revolea y la ataja alzada), el agachado (revolea la
  flauta por arriba del hombro derecho), el kip-up. `chikuo abrir pies` y `chikuo abrir resbalon`: sale de los pies
  enterrados tirando la flauta por arriba del hombro; en el resbalón la flauta salta de la espalda y cae en la derecha.
* G. **Fase 3**: `chikuo fase 3`: la catapulta se ve como una patada voladora de perfil; los saltos entre cañas van
  abiertos de piernas con la capa hacia atrás; un soplido de cada dos sale en abanico (tres dardos; los de costado sin
  anillo propio); con Kaito a 7 m o menos, la ráfaga de cuatro de la firma sigue sin respiro con la Picada; los dardos
  posados van más rápido que en la fase 1. Con `bot on promedio`, mirar que las muertes en la fase 3 no suban.

1. **Tamaño y colores**: Chikuō a escala normal, sin x100. El gi tiene que leerse verde (no gris azulado) contra el piso
   del claro.
2. **Colgado**: `Nindo.AutoPilot.Run("chikuo mov colgado")` en O1 y en O2. Cuelga a plomo (no torcido 30°), se hamaca de
   costado. Al entrar y salir del colgado el cuerpo no salta. Con Kaito a 2 m de la base: el círculo blanco prende recién
   justo antes del primer dardo (cortar antes da "¡Cosquillas!").
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
    `Tools/Dev/boss_sims/calibration.py` MEASURED['chikuo_v2'] (la simulación cruda ya está: 213 s y 255 s con 0.32) y
    correr `python Tools/Dev/chikuo_v2_check.py --runs 400 --calib F`. Objetivo: bueno 4.5-5 min, promedio 1-2 muertes en
    7-9 min; si hay que tocar, la tabla `--knobs`. Restaurar el save del usuario al final.

## 8. Hunks en archivos compartidos

Segunda ronda:
* `Tools/Dev/boss_sims/calibration.py`: los números crudos de `chikuo_v2` (213 s, 255 s con 0.32 muertes).

Primera ronda:
* `Enemies/Enemy.cs`: `public virtual Vector3 TellCenter => transform.position;` (2 líneas, debajo de `HeadPoint`).
* `FX/CombatTelegraphs.cs`: `t.center = e.TellCenter;` (1 línea).
* `Story/StoryText.cs`: la pista `bamboo_deny` dice "el círculo blanco" en vez de "el ensō blanco".
* `Resources/NindoContent.asset`: la clave `dart_snap` en la lista de efectos y la fila de `bamboo_master` sin `DecoySpin`
  (los dos los escribe `Tools/Unity/chikuo_assets.py --sfx`).
* `Tools/Unity/generate_assets.py`: dos docstrings (el sidecar lo escribe `build_chikuo.py`; los `extra_materials`).
* `Tools/Dev/boss_sims/calibration.py`: las referencias a `sim_bamboo_master.py` y los números crudos de `chikuo_v2`.
* `README.md` y `Docs/HANDOFF_PROXIMA_SESION.md`: el párrafo de Chikuō y la lista de archivos.
