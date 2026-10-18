# Chikuō v2, el Ermitaño de las Cañas (diseño de la pelea, fase C4)

Es el contrato para los cuatro trabajos de la fase: el **modelo** (el concepto elegido, opción 6), el **rig y los clips**,
la **arena** (las cañas, rama `c4/arena`) y el **código** (rama `c4/chikuo`). Lo escribió el líder de diseño después de
juzgar las tres propuestas (`ritmo`, `trucos`, `vertical`, sección 1). Todo número de este documento sale de
`Tools/Dev/chikuo_v2_check.py` (el modelo en Python del diseño: arena, cámara, avisos y la pelea contra el bot) y se
puede volver a correr; la sección 12 copia sus salidas. Nada se probó en Unity.

Lo que no cambia: el nombre **Chikuō**, el personaje `bamboo_master`, el arquetipo `ozeki`, el `bossId` `ozeki`,
`SealId.Bambu`, la música `boss_bamboo` con sus tres fases (`Game.Audio.SetBossMusicPhase`), la vida **1900**
(`BambooMasterMoves.Config`), el FBX `Art/Characters/BambooMaster/BambooMaster.fbx` con su GUID
(`191c5633648e5611746e668f0421a7c7`) y el controller `BambooMaster.controller` (GUID `00038a89…`, generado por
`generate_assets.py`), el reintento desde la fase alcanzada y la cura de 30 de vida y 30 de Espíritu en cada cambio.

---

## 0. En una página

* **La regla de la pelea**: a Chikuō no se le pega arriba; **se le corta lo que lo sostiene**. Vive en seis cañas que se
  doblan con su peso (siete en la fase 3), sopla dardos con su flauta-bastón y salta de caña en caña en menos de un segundo.
* **El latigazo** (la mecánica de Kaito, el corazón de la pelea): cuando Chikuō **carga** su caña (se echa atrás para
  una ráfaga, tensa el silbador, se cuelga cabeza abajo, se ríe de vos, trepa o cae de un salto), la caña se arquea, sus
  **cascabeles se encienden en blanco** con un tintineo agudo y aparece un **ensō blanco de tinta en la base**. Un corte
  normal de Kaito a esa base suelta el resorte: la caña lo **despide para el lado del corte**.
  * Nada adelante: **Revolcón** (cae a 3.2 m, mareado 1.6 s, 3 cortes, +12 de la caída).
  * Otra caña en la línea (a 6 m o menos, ±20°): **Estampado** (se estrella contra ella, se desliza, 2.2 s, 4 cortes a
    x1.2, +24). Las cañas están en rayos desde el centro: apuntar es jugar al billar con el viejo.
  * La caña adonde salta, cortada en los últimos 0.45 s del vuelo: **Caída del Cielo** (se le escapa de las manos, cae de
    espaldas, 3.0 s, 5 cortes a x1.25, +36). El ensō blanco aparece en la caña de destino apenas se agacha para saltar.
  * Sin blanco, cortar la caña lo enoja: "¡Cosquillas!", se cuelga del costado y **barre con la caña** (rojo).
* **Su ataque es tu hueco**: lo que lo carga es lo mismo que te ataca (la ráfaga, el silbador, colgarse para soplarte de
  cerca). La decisión de cada momento: ¿paro los dardos acá o me tiro con el dash a su base antes del segundo?
* **Tres fases que cambian la forma de la pelea** (pisos de vida 65 % y 40 %):
  1. **Las Cañas** (100-65 %): el bucle que pidió el usuario. Posado, dardos, saltos rápidos, picadas al piso y vuelta
     arriba con la garrocha. Se aprende el latigazo, el estampado y (en secreto) la caída del cielo.
  2. **El Piso** (65-40 %): "Bueno, bailemos en el piso". Toca tres notas y las seis cañas **se inclinan hacia afuera**:
     no hay dónde posarse. Pelea rápida con la flauta-bastón, sin guardia; su verticalidad sigue en chico (**la Grulla en
     el Bastón**: clava el bastón y se para en la punta; el bastón también se corta) y la flauta **pregunta y responde**.
  3. **El Bosque Entero** (40-0 %): las cañas se enderezan de golpe y **nace la Caña Madre** en el centro. El bucle de la
     fase 1 al doble, con la catapulta, los señuelos de hojas y el ping-pong entre cañas; **cada latigazo raja la caña y el
     segundo la quiebra**, y el viejo usa tus rajaduras: les clava el silbador y te las tira encima. El bosque se ralea.
* **Nunca espera, nunca se cubre**: entre acción y acción respira 0.25-0.45 s (0.12-0.25 en la fase 3); fuera de sus
  huecos le tira a Kaito 28 / 46 / 32 cosas por minuto (fases 1 / 2 / 3) y decide 33-36 veces por minuto arriba. El tramo
  más largo sin aviso, campanas, hueco ni salto es de ~3 s y es raro (19 % del tiempo "quieto", casi todo con Kaito
  aturdido o corriendo hacia él).
* **Duración** (el bot de AutoPilot con los ganchos de la sección 13): con el factor real/simulado de 1.3 (sin medir:
  el Chikuō viejo dio 1.42), el **bueno 4.8 min sin morir** y el **promedio 7.3 min con 1.3 muertes**. Las perillas
  de tiempo son lo que entra en cada hueco (el tope de cortes del revolcón y la caída) y la de las muertes el daño
  (sección 12.3, con la regla para calibrar).

---

## 1. El juicio de las tres propuestas

### 1.1 Contra los criterios

Puntaje de 1 a 5 (5 es lo mejor) contra lo que pidió el usuario y lo que pidió el líder:

| Criterio | Ritmo (el atajo) | Trucos (el latigazo) | Vertical (tramo a tramo) |
|---|---|---|---|
| (0) La visión del usuario: arriba con dardos, saltos rápidos, picadas y vuelta; no toda la pelea así; una mecánica innovadora desde el piso | 4. El atajo es elegante, pero para alcanzarlo los saltos necesitan 4 tiempos de llamado (1.76 s): **el salto se vuelve lento**, que es lo contrario de "moverse rápido de lugar" | **5**. Cada ataque largo desde la caña es a la vez el hueco; la caña de destino es la maestría; el estampado le da dirección; la fase 2 en el piso y la 3 con el bosque entero cambian la forma | 4. Muy fiel al "mono ermitaño" y a los saltos rápidos; "tres cortes a la caña" es el verbo más simple de los tres |
| (1) La queja: aburrido, esperar, ataca cada tanto | 4. Densidad 14-22 por minuto; el atajo se gana yendo a buscarlo | **5**. Algo cada ~1 s; las campanas no mienten (sin falsas esperas) | 4. 15-17 golpes por minuto en las fases 1-2; tramos muertos de 1.6 s |
| (2) Innovación e identidad (bambú, flauta, cascabeles, trepar, ermitaño excéntrico) | **5**. Los cascabeles como idioma y la flauta que pregunta y responde son lo más original de las tres | 4. La caña-resorte, el billar, los señuelos, la risa | 4. El daruma otoshi es lindo, pero es "pegarle a la caña" con un contador |
| (3) Lectura y justicia desde la cámara | 3. Apoya la lectura en el tiempo de la música; el "¡ya!" un tiempo antes cambia la gramática de todo el juego; el atajo dorado se confunde con el parry dorado | 4. Suma un color (blanco) que hay que enseñar, pero es "acá", no un reloj | 4. Un brillo color paja en la base; la caña que baja se puede leer como un error |
| (4) Factibilidad con este código y clips de Blender | 2. La sincronía al reloj DSP es el mayor riesgo (latencia de 21-85 ms, auriculares Bluetooth) | 3. ~50 estados y cuatro sistemas nuevos | **5**. **La raíz del jefe en la base de la caña**: el corte, el imán, el fijado y el bot de Kaito ya apuntan a la caña sin tocar a Kaito |
| (5) Variedad contra Gorō, Mizuchi y Kokuyō | 4 | **5**. Ningún otro jefe se apunta; ningún otro se baja | 3. Devolver el dardo con el parry perfecto es la regla de Mizuchi |

**Gana Trucos como base** (el latigazo es la mecánica más fuerte para el criterio 0: clara de descubrir porque la caña
reacciona a cualquier corte, satisfactoria porque un corte decide y el resultado es enorme, y la fuente principal de
huecos sin esperar a que baje). Se le injertan las mejores ideas de las otras dos.

### 1.2 Qué tomé de cada una y por qué

* **De Trucos** (la base): el latigazo y su familia (revolcón, estampado, caída del cielo), el blanco como tercer color
  de la gramática, "su ataque es tu hueco", "las campanas no mienten" (un compromiso encendido no se cancela), las cañas en
  rayos desde el centro para el billar, la mira de tinta, la fase 2 en el piso con las cañas inclinadas y la pértiga, la
  fase 3 con la Caña Madre, los señuelos y la catapulta, la risa del maestro que enseña, el texto de la presentación.
  Lo que cambié: el corte sin campanas ya no es "la monta" (gratis): es "¡Cosquillas!" y un barrido rojo, porque en la
  simulación el bot (y cualquier jugador apurado) le cortaba la caña cada vez que caía de un salto y él se pasaba la pelea
  saltando sin atacar nunca.
* **De Vertical**: **la raíz del jefe en la base de su caña** (lo hace factible: Kaito no cambia), la pértiga como "su
  última caña" (el mismo verbo en el piso), **la arena que cambia por lo que hace Kaito** (en la fase 3 sus latigazos rajan
  y quiebran las cañas), los saltos rápidos (0.5-0.8 s), el filtro de destino con el cono del sur (que el cuerpo posado no
  tape a Kaito), el Bastón que Cae y la respuesta a quien acampa debajo.
* **De Ritmo**: **el idioma de los cascabeles** (los agudos de los hombros avisan un dardo, los graves del ruedo un salto,
  la cascada una picada, el tintineo blanco la caña cargada) afinado a la escala del tema; **Pregunta y Respuesta** (la
  flauta toca la frase y la repite como golpes; contestarla limpia lo deja "afinado" y abierto), el atajo como **caída del
  cielo** (la caña de destino que se ilumina), la tala como carril rojo, las entradas de la música en los cambios de fase.
  Lo que dejé afuera: atar cada golpe al tiempo de la música. Cambia el "¡ya!" de todo el juego (0.38 → 0.44 s) y depende de
  la latencia de audio; queda como mejora posible (sección 18.3).

### 1.3 Lo que se descartó de las tres

* Devolver dardos con el parry perfecto (es el peloteo de Mizuchi). El parry a un dardo lo rompe y da Espíritu.
* Talar la caña a fuerza de cortes (estático, vacía la arena en un minuto). La caña se quiebra solo en la fase 3 y por
  latigazos, que son huecos.
* El "¡ya!" un tiempo antes y la pelea en el tiempo (riesgo técnico, regla distinta del resto del juego).
* El sacudón a tiempo de ritmo (pedía un segundo reloj con el ataque) y la resonancia de tres cortes (Kaito parado debajo).
* El daruma otoshi literal (la caña que se hunde en el piso se lee como un error).

---

## 2. El latigazo, en detalle

### 2.1 La regla

1. **Cargar** = Chikuō pone su peso en la caña para algo que lleva tiempo. Durante la carga:
   * la caña se arquea (el código la dobla: 6° quieto, 20° en la ráfaga, 25° en el silbador, 30° colgado, -35° hacia
     atrás en la catapulta, ±10° temblando en la risa);
   * sus ~24 cascabeles brillan **blanco** (pulso de 4 Hz) y suenan agudos y seguidos (`tell_chime_shimmer`);
   * en la base de la caña aparece un **ensō blanco de tinta** de 1.2 m que **no se cierra** (no es un reloj, es un
     "acá"); en el último cuarto de la ventana el trazo se afina.
2. El **primer corte de Kaito que toca la base** mientras dura la carga dispara el latigazo. Cuenta cualquier corte del
   combo, el contraataque, el Corte del Viento cuya línea pase a 1.6 m o menos de la base y el Torbellino a 4.2 m o menos.
3. La caña suelta el resorte y lo despide por la línea **Kaito → base** (horizontal, en el plano):
   * si hay otra caña en pie a 6 m o menos dentro de ±20° de esa línea: **Estampado** contra la más cercana;
   * si no: **Revolcón**, cae a 3.2 m de la base (adentro de la arena: nunca más de 13 m del centro, punto de NavMesh);
   * la barrera nunca estampa (rebota y cae adentro): el borde no es la estrategia.
4. **Las campanas no mienten**: una carga encendida dura lo que dice su tabla y no se cancela por nada salvo el
   latigazo, la muerte de Kaito o el cambio de fase. Lo que no está encendido no se puede latigar.

### 2.2 Qué la carga (tabla completa)

| Momento | Fases | Ventana blanca (s desde que arranca) | Si no se corta | Desde dónde llega Kaito (reacción 0.30 s; corriendo / con el dash) |
|---|---|---|---|---|
| Tres Notas (ráfaga de 3) | 1 | 0.10-1.41 (la primera de la pelea +0.6 s) | 3 dardos dorados | 7.6 m / 12.4 m |
| Cuatro Notas | 3 | 0.10-1.34 | 4 dardos dorados | 7.1 / 12.0 |
| Silbador | 1 (desde el 85 %), 3 | 0.10-1.00 (fase 3: 0.10-0.90) | carril rojo, 5 de daño | 5.0 / 9.9 |
| Colgado (cabeza abajo) | 1-3 | 0.00-1.25 | 2 dardos de cerca | 7.2 / 12.1 |
| Risa | 1-3 | 0.00-1.20 (la del maestro, 2.0) | nada: es la revancha de Kaito | 6.9 / 11.8 |
| Catapulta | 3 | 0.00-1.00 | la patada voladora por un carril rojo | 5.6 / 10.5 |
| Trepada | 1, 3 | 0.00-0.80 | sube | 4.4 / 9.3 (hueco: **Resbalón**) |
| Agarre al caer de un salto | 1, 3 | 0.00-0.20 | queda posado | solo si ya estabas ahí |
| La Grulla en el Bastón (pértiga) | 2 (y la coda de la 3) | 0.45-1.40 desde que clava el bastón | se tira en picada (rojo) | 5.3 / 10.2 (hueco: Revolcón desde 2.4 m) |

Lo que **no** carga (no da para llegar, por eso no brilla): el dardo suelto (0.45 s a soplar), los dos dardos, el
agachado de la picada (0.35 s), el barrido de caña, la tala, el giro de los señuelos.

### 2.3 Lo que pasa después del corte

| Resultado | Vuela | Abierto | Tope de cortes | Daño | Caída | Fase 3 |
|---|---|---|---|---|---|---|
| **Revolcón** | 0.55 s, cae 3.2 m más allá de la base, una vuelta y queda sentado mareado | 1.6 s | 3 | x1.0 | +12 | 1.4 s, 3 cortes |
| **Estampado** | se estrella a ~3.5 m de altura contra la otra caña ("¡PUM!", hojas y un cascabel que se suelta), se desliza 0.6 s y queda sentado al pie | 2.2 s desde que toca el piso (1.0 s después del corte) | 4 | x1.2 | +24 | 2.0 s, 3 cortes |
| **Caída del Cielo** | la caña de destino se le escapa: cae de espaldas desde ~4 m al pie de esa caña | 3.0 s | 5 | x1.25 | +36 | igual |
| **Resbalón** (trepando) | se resbala por la caña y cae sentado | 1.0 s | 2 | x1.0 | +6 | igual |
| **Revolcón desde la pértiga** | el bastón se dobla y lo tira 2 m | 1.6 s | 3 | x1.0 | +12 | |

* La caída (+12/+24/+36) entra cuando toca el piso, se multiplica como un corte (calibración) y nunca cruza el piso de
  la fase (como hoy: lo que sobra no cuenta).
* El último corte del tope lo despide un poco y se levanta enseguida (0.25 s); si no se usa el tope, se levanta al final.
* **Se levanta** de un salto (`GetUp`, 0.40 s, invulnerable) y vuelve arriba **con la garrocha** (salto con el bastón,
  0.9 s, invulnerable, a una caña a 4.5-8 m de Kaito; el agarre de la garrocha no carga). Así un hueco nunca encadena otro.
* En la **fase 3**, después de un estampado o de una caída del cielo, si Kaito está a 3 m o menos, primero le contesta
  con un bastonazo dorado (**Revancha**, 0.60 s de aviso, 4 de daño; pararlo no lo abre: es la prueba del maestro).

### 2.4 Cómo se descubre (los primeros 40 s)

1. **Presentación** (sección 19.1): colgado cabeza abajo de la caña O1 tocando la flauta, abre un ojo, se ríe, le clava
   un dardo a los pies a Kaito (un saludo, no pega) y se acomoda agachado.
2. **0-5 s**: dos dardos sueltos (dorados, el parry de lejos de siempre). El jugador corre a la caña y la corta por
   instinto: suena hueca, la caña se sacude, "¡Je! ¡Cosquillas!" y **barre con la caña** (rojo: la regla de siempre, dash).
   Primera lección: **la caña reacciona, pero no así**.
3. **La tercera acción es siempre Tres Notas** con 0.6 s más de carga (una inspiración exagerada, "¡Mmm!"): campanas
   blancas, ensō blanco en la base y la pista `bamboo_whip` (sección 19.4).
4. **El primer latigazo** tiene 0.25 s de cámara lenta (solo esa vez) y "¡Ay, mis huesos! ¿Quién te enseñó eso?". Al
   terminar ese hueco, la pista `bamboo_stamp`. El primer estampado: "¡Uf! Esa caña estaba más dura que yo."
5. **Si tres cargas seguidas terminan sin corte**, la acción siguiente es la **Risa del Maestro** (2.0 s, cargada): "¿Y?
   ¿No me vas a bajar?". Vuelve la pista.
6. **La caída del cielo no se enseña con texto**: la primera vez que salta a una caña a 5 m o menos de Kaito sale la pista
   `bamboo_deny` (una sola vez por partida). Es el regalo para el que mira dónde va.

### 2.5 Por qué es la mecánica que pidió el usuario

* **Se juega desde el piso con el kit de siempre**: el corte, el dash para llegar (que de paso atraviesa un dardo), el
  parry a los dardos (que da el Espíritu que paga el dash) y las dos habilidades como latigazos a distancia. **Ningún clip
  nuevo de Kaito.**
* **Es la fuente principal de huecos**: en la simulación el latigazo (con sus caídas) da el ~83 % del daño de la fase 1 y
  el ~74 % de la 3, uno cada 8.5-9.5 s (sección 12); el resto son contras, pies enterrados y, en la fase 2, la pértiga y la
  flauta.
* **Nunca hay que esperar a que baje**: hay que ir a buscarlo cuando se compromete. Lo que lo hace dinámico (moverse,
  atacar desde lejos) es lo que lo deja abierto.
* **Tiene techo**: el billar (apuntar el estampado) y la caída del cielo (leer el salto) duplican el hueco para el que
  juega mejor; la mira de tinta (2.6) ayuda sin resolverlo.

### 2.6 La mira de tinta (ayuda, se puede apagar con los "Avisos de combate")

Con la caña cargada y Kaito a 4 m o menos de la base, un trazo de tinta blanca tenue sale de la base hacia donde lo
despediría un corte desde donde está Kaito (3.2 m); si encuentra una caña en pie dentro de la regla del estampado, el
trazo termina en ella y su base destella. Se actualiza cada cuadro (un `LineRenderer` de 2 puntos, sin asignar memoria).

---

## 3. La gramática de esta pelea

### 3.1 Colores (la de todo el juego más uno)

* **Dorado** = parry (dardos, bastonazos, la estocada, la patada de grulla). Para los dardos el anillo va **a los pies de
  Kaito** con la ETA honesta del dardo por salir (como las perlas de Mizuchi: `Boss.ProjectileEta`).
* **Rojo** = dash o salir (picada, silbador, barrido de caña, barrida del bastón, catapulta, tala, brotes de la respuesta,
  picada de la pértiga). La zona queda **fija** a 0.45 s del golpe como mínimo (el silbador 0.25 s antes de soplar, la
  catapulta 0.75 s).
* **Blanco** (solo en esta pelea) = **cortá acá**. Campanas blancas en él, ensō blanco en la base. Nunca un golpe a Kaito.

Los tiempos de siempre: anillo dorado hasta 0.85 s antes, rojo hasta 1.0 s; se cierran 0.10 / 0.16 s antes; el "¡ya!" a
0.38 / 0.42 s (`TellStyle`). No se tocan.

### 3.2 Los cascabeles hablan (sonido y luz desde donde se ven)

| Grupo | Dónde | Suena | Brilla | Quiere decir |
|---|---|---|---|---|
| Agudos | ~10 tubos cortos de los hombros | `tell_chime_hi`: dos golpecitos agudos al levantar la flauta | dorado | un dardo (el "¡ya!" sigue saliendo a 0.38 s) |
| Graves | ~12 tubos largos del ruedo | `tell_chime_lo`: "tok-tok" al agacharse | no brillan (la luz está en la caña de destino: el ensō blanco) | salta a otra caña |
| Cascada | todos, de agudo a grave | `tell_chime_cascade` | rojo | se tira encima (picada, catapulta) o barre |
| Tintineo blanco | todos | `tell_chime_shimmer` (loop mientras dura) | blanco a 4 Hz | **la caña está cargada** |
| Sacudón | todos | `chime_jangle` | | cayó, está mareado (cada corte en un hueco lo hace sonar: "lo agarraste") |

Afinados a la escala del tema `boss_bamboo` (sección 18.2): suenan como parte de la música. La pelea se lee entera sin
sonido: cada palabra tiene su luz y cada golpe su anillo.

---

## 4. Las fases

| Fase | Vida | Forma | Música | Cañas | Bueno (min de juego, F 1.3) |
|---|---|---|---|---|---|
| 1, **Las Cañas** | 100-65 % | arriba: dardos, saltos, picadas y vuelta | fase 1 (136 BPM) | N1 N2 O1 O2 E1 E2 (seis, rectas) | 1.9 |
| 2, **El Piso** | 65-40 % | abajo: tandas de bastón, la Grulla en el Bastón, Pregunta y Respuesta | fase 2 | las seis inclinadas 70° hacia afuera | 0.75 |
| 3, **El Bosque Entero** | 40-0 % | arriba al doble, catapulta, señuelos, tala; el bosque se ralea | fase 3 (144 BPM) | las seis rectas otra vez + la Caña Madre (siete) | 2.2 |

`Gates = { 1, 0.65, 0.40, 0 }` (son pisos: el golpe que cruza el umbral dispara la escena y lo que sobra no cuenta, como
hoy). `CharacterFactory` pasa a `phaseThresholds = { 0.65f, 0.40f }` (hunk de una línea; `BambooMasterBoss` maneja sus
fases con sus `Gates`). Con 66 / 33 la fase 2 (el piso, el interludio) duraba más que la 3, que es el clímax.

### 4.1 Fase 1, "Las Cañas" (el bucle del usuario)

* Posado: respira 0.25-0.45 s entre acciones (`PerchIdle`, nunca quieto: se hamaca con la caña) y hace una o dos
  acciones por caña antes de saltar; recién posado arranca sin respiro.
* Con Kaito lejos (a más de 4.5 m de la base): dardos, ráfagas, silbador (desde el 85 %), colgado, saltos, picadas y
  bastonazos (pesos en la sección 7).
* Con Kaito debajo y él sin cargar: se cuelga a soplarle de cerca (cargado), barre con la caña, baja a pegarle o se va
  saltando (sección 7.2). Nadie acampa al pie de su caña.
* **Bajadas al piso** (las del usuario: "ataques rápidos al piso y vuelve al bambú"): la **Picada de la Grulla** (la
  patada voladora del concepto, roja) y el **Bastón que Cae** (dorado). Cada bajada dura 1.2-2.5 s y vuelve arriba
  trepando (si cayó al lado de una caña), saltando agachado o, después de un hueco, con la garrocha.
* Medido (bueno, F 1.3): 112 s, arriba el 55 % del tiempo, 33 decisiones por minuto, 13 latigazos en la fase (uno cada
  ~8.5 s), ~21 saltos y ~10 ping-pong por pelea.

### 4.2 Cambio 1 (65 %), "Bailemos en el piso" (4.0 s)

El golpe que lo baja al 65 % lo tira (si estaba arriba, el latigazo; si estaba en un hueco, el hueco se corta). Cae
sentado, se ríe, se saca una hoja de la barba: "¡Ja! Me bajaste del bambú. Bueno, bailemos en el piso." Toca tres notas
(la flauta de costado, la pose del concepto) y en la tercera **las seis cañas se inclinan 70° hacia afuera** en 1.2 s y
quedan así, temblando con la música. `SetBossMusicPhase(2)`, subtítulo "El Baile de la Flauta", Kaito +30 de vida y +30
de Espíritu. Los golpes rebotan mientras dura (como hoy, `Boss.Roaring`).

### 4.3 Fase 2, "El Piso"

* Pelea de piso rápida con la flauta-bastón, **sin guardia**: tandas cortas (cargas de 0.42-0.65 s), 0.35-0.6 s entre
  tandas. Se acerca corriendo (5.5 m/s); de lejos (más de 4.5 m) le sopla un dardo desde el piso (Soplo).
* **El Paso del Ermitaño** en lugar de la guardia: el corte de Kaito en neutral le entra a x0.6 (lo roza mientras se va)
  y se va de una voltereta 2.5 m (0.35 s invulnerable); 0.25 s después arranca una tanda. En la carga de sus golpes tiene
  armadura: el corte entra a x0.35 y el golpe sigue (cambiar golpes no conviene).
* **El último golpe de cada tanda, desviado, lo deja abierto** (retroceso 0.40 s, dos cortes; 0.60 s y tres después de un
  perfecto). Los del medio de la tanda no: la tanda sigue (`noRecoil`).
* **La Grulla en el Bastón** (cada 8-11 s, la primera a los 4-6 s): salta 4 m atrás, clava el bastón, se sube a la punta y
  se para en un pie como una grulla con las campanas blancas; después se tira en picada. **El bastón es su caña**:
  cortarlo con las campanas blancas lo tira (revolcón).
* **Pregunta y Respuesta** (cada 18-24 s, la primera a los 9-12 s): salta 3 m atrás y toca una frase de tres notas (cuatro
  desde el 52 %); en el compás siguiente **la repite como golpes con el mismo ritmo**: nota aguda = dardo dorado, nota
  grave = brote rojo bajo Kaito. Contestarla entera sin recibir un golpe: "¡Afinado! Me ganaste la canción" y queda
  **Afinado** (2.5 s abierto, 4 cortes a x1.2). Cortarlo mientras toca (pregunta o respuesta): "¡Me hiciste desafinar!",
  **Desafinado** (1.4 s, 2 cortes), y la frase se apaga en gris. Dos caminos, los dos valen.
* Medido (bueno, F 1.3): 45 s, 46 amenazas por minuto fuera de sus huecos (la fase más densa: es corta a propósito).

### 4.4 Cambio 2 (40 %), "Que cante todo el bosque" (5.0 s)

En el piso, toca la frase entera (2 s, todas las campanas en cascada); las seis cañas **se enderezan de golpe** (un
"fuush" de hojas) y en el centro **nace la Caña Madre** (crece de la tierra en 1.5 s; si Kaito está encima lo corre 1 m,
sin daño). Salta con la garrocha a la Madre: "¡Ahora que cante todo el bosque!". `SetBossMusicPhase(3)` (144 BPM),
subtítulo "Todo el Bosque Canta", Kaito +30 / +30.

### 4.5 Fase 3, "El Bosque Entero" (el clímax)

* El bucle de la fase 1 más rápido: respiro 0.12-0.25 s, agachado del salto 0.14 s, vuelo x0.85, **ping-pong** (el 30 %
  de las veces encadena otro salto al caer), Cuatro Notas, silbador más corto, dardos más rápidos y mejor apuntados.
* **Catapulta** (la pose del concepto "agachado sobre la caña que se dobla" llevada a golpe): tensa la caña hacia atrás
  como un arco (cargada) y sale con la patada voladora por un carril rojo. Cortarla tensa: el tiro sale errado (latigazo).
* **Cada latigazo raja la caña** (una grieta clara, paja, en el tramo de abajo) y **el segundo la quiebra** (cae hacia
  afuera, queda el tocón de 1 m). La Madre se arquea poco y nunca se quiebra.
* **La Tala**: le clava el silbador en la rajadura a una caña rajada y la tira encima de Kaito (carril rojo del largo de
  la caña). Tus latigazos se vuelven sus armas.
* **Tres Ermitaños** (cada ~22 s): gira con la capa abierta y aparecen dos señuelos de hojas en otras cañas que copian
  sus poses 0.25 s tarde; **solo el verdadero brilla y solo el verdadero tira**. Cortar la caña de un señuelo lo deshace
  en hojas ("¡Ese no era yo!"); el Torbellino los revienta. Duran 9 s o hasta que el verdadero cae.
* **La Última Canción** (12 % o menos): salta después de cada acción. Con el bosque raleado le quedan pocas cañas y la
  de destino se adivina: la caída del cielo queda al alcance de todos.
* **Si no tiene una caña libre** (todas quebradas o Kaito al pie de la única), pelea en el piso con lo de la fase 2
  (tandas, la Grulla en el Bastón, el Soplo) hasta que tenga una.
* Medido (bueno, F 1.3): 131 s, 32 amenazas por minuto fuera de sus huecos, 5 rajaduras, 3 cañas quebradas y 1 talada por
  pelea.

### 4.6 Derrota y reintento

* **Derrota**: el último golpe siempre le cae en el piso (arriba no se le pega). Cae de espaldas riéndose, se sienta con
  las piernas cruzadas, se seca una lágrima de risa y hace la reverencia con la flauta sobre las rodillas; las campanas de
  la Caña Madre suenan solas, una por una, y se callan; aparece el sello delante. No se lo ejecuta (`finisherHealth` 0).
* **Reintento**: arranca en la fase más alta a la que llegó Kaito (`retryPhase`), con la arena de esa fase entera (en la
  2, las seis inclinadas; en la 3, las seis rectas y la Madre, sin rajaduras) y su vida en el piso de la fase.

---

## 5. Los movimientos

Daño sobre los 100 de Kaito (fases 1 / 2 / 3). Tiempos en s desde que arranca la acción; T = el golpe. "Carga" = ventana
blanca. Todos los dardos: radio de golpe 0.6 m, se paran (`AttackKind.Projectile`), el parry los rompe, el dash los
atraviesa, los que fallan quedan clavados 3 s en el piso (se ve dónde cayó la ráfaga).

### 5.1 Desde la caña

| Movimiento | Fases | Color | Línea de tiempo | Daño | Cómo se lee | Respuesta |
|---|---|---|---|---|---|---|
| **Dardo** | 1-3 | dorado | flauta a la boca 0.25, sopla a 0.45; vuela a 16 m/s (18 en la 3) hacia donde va a estar Kaito (adelanta 50 / 60 / 80 % de su velocidad) | 2.5 | cascabeles agudos, la flauta apunta, anillo a los pies | parry; de costado se lo esquiva corriendo (fases 1-2) |
| **Dos Dardos** | 1-3 | dorado x2 | soplos a 0.45 y 0.80 | 2.5 c/u | dos golpecitos agudos | dos parries |
| **Tres Notas** | 1 | dorado x3 | se echa atrás (la caña se arquea) 0.10; soplos a 0.55, 0.93, 1.31; **carga 0.10-1.41**; termina a 1.71 | 2.5 c/u | campanas blancas, ensō blanco | parries **o latigazo** |
| **Cuatro Notas** | 3 | dorado x4 | soplos a 0.45, 0.73, 1.01, 1.29; **carga 0.10-1.34**; termina a 1.60 | 2.5 c/u | igual | parries **o latigazo** |
| **Silbador** | 1 (85 %), 3 | rojo | gran inspiración; el carril de 1.0 m sigue a Kaito hasta 0.25 s antes de soplar; sopla a 0.90 (0.80 en la 3) un dardo pesado a 22 m/s; **carga 0.10-1.00** (0.90) | 5 | la flauta silba, cachetes inflados, carril | salir del carril o dash, **o latigazo** |
| **Colgado** (la pose del concepto) | 1-3 | dorado x2 | se deja caer cabeza abajo colgado de las rodillas (0.35), la cabeza a ~2.4 m; soplos a 0.65 y 0.95; vuelve a 1.45; **carga 0.00-1.25** | 2.5 c/u | colgado, barba al revés | parries **o latigazo** (cae de cabeza) |
| **Risa** | 1-3 | | se ríe a carcajadas sacudiendo las campanas; 1.2 s (la del maestro 2.0 s); **cargada entera** | | la cara del concepto "riéndose" | **latigazo** |
| **Barrido de Caña** | 1, 3 | rojo | (si Kaito acampa o le corta la caña sin campanas) se cuelga del costado y la caña barre un disco de 3.6 m alrededor de la base; T = 0.85 (más 0.25 de manoteo después de un corte) | 4 / (no) / 4 | la caña se inclina sobre vos | salir del disco o dash |
| **Salto** | 1, 3 | (blanco en el destino) | agachado 0.22 (0.14) mirando la caña de destino; vuelo 0.30 s + 0.035 s por metro de salto (x0.85 en la 3), comba de 1.8 m; agarre 0.20 cargado | | cascabeles graves, ensō blanco en la caña de destino desde que se agacha | **caída del cielo**: cortar la caña de destino en los últimos 0.45 s del vuelo |
| **Catapulta** | 3 | rojo | tensa la caña hacia atrás (**carga 0.00-1.00**), el carril de 1.8 m sigue a Kaito hasta 0.75 y queda fijo; sale a 1.00, la patada pega a 1.50 al final del carril y aterriza 2 m más allá | 6.5 | la caña arqueada como un arco, cruje | salir del carril o dash; **latigazo = tiro errado** |
| **Tala** | 3 | rojo | le sopla el silbador a la rajadura de una caña rajada (sopla a 0.45); la caña cruje y cae hacia Kaito: carril de 1.6 m de ancho y su largo, fijo a 0.65; T = 1.10; queda el tocón | 5.5 | la caña rajada se ladea hacia vos | salir del carril |
| **Tres Ermitaños** | 3 | | gira con la capa abierta (0.6 s), estallido de hojas, dos señuelos en otras cañas | | | ver 4.5 |

### 5.2 Al piso y de vuelta (fases 1 y 3)

| Movimiento | Color | Línea de tiempo | Daño | Respuesta | Hueco |
|---|---|---|---|---|---|
| **Picada de la Grulla** (patada voladora del concepto) | rojo | agachado 0.35 (sale de la caña), vuelo 0.60; el disco de 1.6 m sobre Kaito queda fijo a 0.50; T = 0.95 | 5 | dash, o correr si ya venía moviéndose (margen +1.6 m desde que aparece el anillo) | aterriza 0.45 s (un corte); **dash perfecto: Pies Enterrados**, 1.6 s, 3 cortes |
| **Bastón que Cae** | dorado | sale de la caña a 0.20, elige dónde cae (1.6 m de Kaito, de su lado) a 0.40, cae a 0.65, bastonazo T = 0.85 (arco 90°, 2.4 m) | 5 / (no) / 4.5 | parry | **Contra**: 0.40 s, 2 cortes (0.60 y 3 tras un perfecto) |
| **Bastonazo después de aterrizar** | dorado | la mitad de las veces que aterriza de la picada con Kaito a 3 m o menos: T = 0.55 | 3.5 / (no) / 4 | parry | contra |
| **Vuelta arriba** | | trepa si cayó a 1.5 m o menos de una caña (0.80 s, **cargada**: Resbalón) o se agacha 0.30 (**cortarle el agachado: Tropiezo**, 1.0 s, 2 cortes) y salta (vuelo 0.30 s + 0.035 s por metro); una sola vez por bajada se lo puede cortar volviendo | | | |
| **Garrocha** | | después de cualquier hueco: clava el bastón y salta a una caña a 4.5-8 m de Kaito; 0.9 s; invulnerable; el agarre no carga | | | |
| **Revancha** (fase 3) | dorado | después de un estampado o una caída del cielo, con Kaito a 3 m o menos: T = 0.60 desde que se levanta | 4 | parry (no abre) | |

### 5.3 En el piso (fase 2, y la coda de la 3)

| Tanda | Peso | Golpes (s de carga cada uno) | Color | Daño | Nota |
|---|---|---|---|---|---|
| **Nota y Giro** | 1.0 | Estocada 0.50, Flauta Giratoria 0.55 + 0.42 | dorado x3 | 3.5 c/u (4 en la 3) | la flauta gira con hojas (la pose del concepto); parry al último: contra |
| **Grulla que Barre** | 0.9 | Patada de Grulla 0.50, **Barrida del Bastón** 0.80 (disco 2.6 m) | dorado, rojo | 3.5 / 4.5 (5) | dash perfecto a la barrida: **Bastón Clavado** 1.1 s, 2 cortes |
| **Tres Estocadas** | 0.8 | 0.50, 0.42, 0.42 | dorado x3 | 3.5 c/u | tres parries seguidos |
| **Golpe de Nota** | 0.6 | 0.65 | dorado | 3.5 | la flauta arriba suena una nota |
| **Soplo** | (Kaito a más de 4.5 m, cada 2.5 s) | sopla a 0.55 desde el piso | dorado | 2.5 | |
| **La Grulla en el Bastón** | (cada 8-11 s) | salto atrás 4 m (0.45), clava (0.45), sube (0.45) y se para en la punta (2.4 m); **carga 0.45-1.40 desde que clava**; picada desde la punta: disco 1.4 m fijo a 0.45 del golpe, T = 1.40 + 0.95 | rojo | 5 | **cortar el bastón**: Revolcón |
| **Pregunta y Respuesta** | (cada 18-24 s) | salta 3 m atrás; levanta la flauta 0.45 y toca 3 (4) notas cada 0.44 s; la primera nota de la respuesta pega 0.85 s después de la última de la pregunta, las demás cada 0.44 s; aguda = dardo (anillo a los pies), grave = brote (disco 1.0 m fijo a 0.45) | dorado / rojo | 2.5 / 4 (4.5 en la 3) | ver 4.3 |

Frases (A aguda, G grave): de tres notas `A A G`, `A G A`, `G A A`; de cuatro `A A A G`, `A G A G`, `G A G A`. Una nota
aguda brilla dorada en los hombros, una grave roja en el ruedo, y suena cada una con su altura: se escucha el ataque antes
de que pase. Nunca dos rojos de fuentes distintas a menos de 0.6 s (las de la respuesta son de la misma frase y caen donde
estaba Kaito: corriendo sin parar se esquivan todas).

### 5.4 Daño comparado (por golpe que entra)

| Jefe | Por golpe | Cómo duele |
|---|---|---|
| **Chikuō** | 2.5 los dardos, 3.5-5 el bastón y la picada, 5.5-6.5 la tala y la catapulta | el más liviano por golpe y el que más seguido ataca: "pica como un mosquito" |
| Mizuchi | 3.3 las perlas, hasta ~9.9 | |
| Gorō | 6.6-12.6 la primera barra | pocos y pesados |
| Kokuyō | 7.4-11.8 | el que más duele: sigue siendo el final |

---

## 6. Los huecos (todos)

| Hueco | Cómo se gana | Vuela (s) | Abierto (s) | Tope | x | Caída |
|---|---|---|---|---|---|---|
| Revolcón | latigazo sin caña detrás; cortar la pértiga | 0.55 | 1.6 (f3 1.4) | 3 | 1.0 | 12 |
| Estampado | latigazo con otra caña en la línea | 1.00 | 2.2 (f3 2.0) | 4 (f3 3) | 1.2 | 24 |
| Caída del Cielo | cortar la caña de destino en los últimos 0.45 s del salto | 0.45 | 3.0 | 5 | 1.25 | 36 |
| Resbalón | cortar la caña mientras trepa | 0.30 | 1.0 | 2 | 1.0 | 6 |
| Tropiezo | cortarle el agachado de la vuelta | 0 | 1.0 | 2 | 1.0 | |
| Pies Enterrados | dash perfecto a la picada (i-frames en los primeros 0.16 s) | 0 | 1.6 | 3 | 1.0 | |
| Bastón Clavado | dash perfecto a la barrida del bastón | 0 | 1.1 | 2 | 1.0 | |
| Contra | parry al último golpe de una tanda o al bastón que cae | 0 | 0.40 (0.60) | 2 (3) | el primer corte x1.5 (el contraataque de siempre) | |
| Aterrizaje | aterriza de la picada o la catapulta | 0 | 0.45 | 1 | 1.0 | |
| Afinado | contestar la Pregunta y Respuesta sin recibir un golpe | 0.30 | 2.5 | 4 | 1.2 | |
| Desafinado | cortarlo mientras toca | 0 | 1.4 | 2 | 1.0 | |

**Fuera de los huecos** no hay pared: arriba, la caña sin campanas responde con el barrido; en el piso, el corte en neutral
entra a x0.6 y él se va de una voltereta; en la carga de un golpe, x0.35 y el golpe sigue. Nunca un clang ni un rebote.

**Desequilibrio (la postura de `Enemy`)**: no se usa. Ningún hueco sale de llenar una barra: salen de las reglas de esta
tabla, que se ven. `maxImbalance` alto (99) y `poiseHits` 99 para que la regla común del agotado y del neutral no aparezca
nunca (como hoy con `poiseHits`). Los parries le siguen sumando a Kaito Espíritu y furia como siempre.

---

## 7. La IA en reglas

### 7.1 Posado: qué decide (cada vez que termina algo)

En orden; lo primero que se cumple:

1. **Fuera de cuadro** (con la cámara de este cuadro, sección 10): salta a una caña en cuadro. Nunca ataca desde fuera.
2. **Las tres primeras acciones de la pelea** (solo arrancando en la fase 1): Dardo, Dardo, Tres Notas (+0.6 s).
3. **Acampan debajo**: Kaito a 2.5 m o menos de la base durante 0.6 s sin campanas → Barrido de Caña (cada 5 s como mucho).
4. **Kaito a 4.5 m o menos de la base** y él sin cargar → una de: Colgado 0.30, Barrido de Caña 0.20 (si Kaito está a
   3.4 m o menos; cada 3 s), Picada 0.15 (cada 3 s), Bastón que Cae 0.15 (cada 3 s), se va saltando 0.20; si la elegida no
   puede, Colgado.
5. **Tres cargas seguidas sin corte** → Risa del Maestro (2.0 s, cargada).
6. **Un dardo suyo le pegó a Kaito**: el 30 % de las veces la acción siguiente es la Risa (1.2 s, cargada).
7. **Ya hizo 2 acciones en esta caña** (1 en la Última Canción) → salta.
8. **Si no, por pesos** (Kaito a más de 4.5 m): Dardo 1.0, Dos Dardos 0.8, Tres / Cuatro Notas 1.2 (Kaito a 3.5 m o más),
   Silbador 0.6 (desde el 85 % y Kaito a 5 m o más), Colgado 0.6 (Kaito a 7 m o menos), Salto 0.6 (después de la primera
   acción en la caña), Picada 0.4 (cada 5 s), Bastón que Cae 0.3 (cada 5 s). En la fase 3 además: Catapulta 0.6 (Kaito a
   5 m o más, cada 8 s), Tala 0.9 (si hay una caña rajada que alcance a Kaito al caer, cada 7 s), Tres Ermitaños 0.3
   (cada 22 s).

### 7.2 Cortes a su caña sin campanas: "¡Cosquillas!"

El corte suena hueco (`bamboo_thok`), la caña se sacude, él manotea 0.25 s y **barre con la caña** (Barrido de Caña, rojo;
cada 2.5 s como mucho). Si acaba de barrer, usa el envión para irse a otra caña ("¡Gracias por el empujón!"). Al corte
no le entra daño ni da Espíritu (`HitResult.Ignored` con la respuesta del jefe).

### 7.3 Adónde salta (cada salto)

Una caña en pie (no quebrada; en la fase 3 incluida la Madre), distinta de la suya, con su posado **en cuadro** con la
cámara de ese cuadro, a 2.5 m o más de Kaito, **fuera del cono de ±30° al sur de Kaito entre 2.5 y 6.5 m** (ahí el
cuerpo posado tapa a Kaito en pantalla), y de esas, la más cercana a la franja de 4.5-8 m de Kaito (4-7 en la fase 3),
con un poco de azar. Si no hay, una Picada (siempre en cuadro: cae sobre Kaito). Desde el piso, cualquier caña que cumpla
eso (incluida aquella de la que bajó).

### 7.4 Lo que nunca hace

Fintas con anillo; cancelar una carga encendida; atacar desde fuera de cuadro; posarse a menos de 2.5 m de Kaito; dos
zonas rojas de fuentes distintas a menos de 0.6 s; un hueco que encadena otro (después de un hueco vuelve con la garrocha);
quedarse quieto (`PerchIdle` se hamaca, en el piso amaga y rodea).

---

## 8. La arena: las cañas (contrato con `c4/arena`)

### 8.1 Dónde

Centro de la arena `(124, 162)`, barrera de r 15, el jefe hasta r 14, **piso plano a y = 2.0**. La cámara de la zona mira
al norte (`cameraYaw` 0 en "bambu"). Kaito entra por el arco del sudoeste `(116, 148)`. Tres rayos desde el centro
(rumbos desde el este, antihorario) con una caña de adentro a 5.5 m y una de afuera a 10.5 m, más la Madre en el centro:

| Caña | Rumbo, radio | Base en el mundo (x, z) | Alto | Posado recto / cargado | Fases | Se arquea |
|---|---|---|---|---|---|---|
| **N1** | 100°, 5.5 | (123.04, 167.42) | 7.5 m | 4.4 / 4.0 m | 1, 3 | sí (hasta 35°) |
| **N2** | 100°, 10.5 | (122.18, 172.34) | 7.5 m | 4.0 / 3.6 m (la del norte va más baja: es la que peor encuadra) | 1, 3 | sí |
| **O1** | 180°, 5.5 | (118.50, 162.00) | 7.5 m | 4.4 / 4.0 m (la de la presentación) | 1, 3 | sí |
| **O2** | 180°, 10.5 | (113.50, 162.00) | 8.5 m | 4.8 / 4.4 m | 1, 3 | sí |
| **E1** | 330°, 5.5 | (128.76, 159.25) | 7.5 m | 4.4 / 4.0 m | 1, 3 | sí |
| **E2** | 330°, 10.5 | (133.09, 156.75) | 8.5 m | 4.8 / 4.4 m | 1, 3 | sí |
| **M** (la Caña Madre) | centro | (124.00, 162.00) | 10.0 m | 5.0 / 4.8 m | 3 (nace en el cambio 2) | poco (hasta 10°), nunca se quiebra |

Verificado (`--layout`): entre vecinas de un rayo 5.0 m; de la Madre a las de adentro 5.5 m; centro libre de r 5.3 en las
fases 1 y 2 (el piso de la fase 2); el camino del arco al centro pasa a 4.8 m o más de toda caña (la Madre no está cuando se
entra la primera vez); el **portal** que aparece al ganar `(114, 158)` queda a 4.0 m de O2; las de afuera a 4.5 m de la
barrera. **Estampado**: desde el centro contra una de adentro siempre la tira contra la de afuera de su rayo, y desde
afuera de la de afuera contra la de adentro; desde un lado al azar, 2-3 de 24 direcciones (fase 1) y hasta 9 de 24 contra la
Madre (fase 3).

**Ninguna tapa la pelea** (`--camera`, sección 10): el cuerpo posado tapa a Kaito en pantalla desde el 0.3-1.0 % de las
posiciones de la arena, y el filtro de destino (7.3) las descarta. El culmo tapa poco (0.26 m); las copas (6-8.5 m) están
por encima de la línea de la cámara a Kaito salvo con la caña a 6-8 m al sur de Kaito: llevan la marca `occluder` y
`CameraOcclusion` las funde como al resto del bosque, salvo la caña donde está posado Chikuō.

### 8.2 Cómo es cada caña (el FBX y el comportamiento que espera el código)

* **Forma**: low-poly facetada, 6-8 lados. Culmo de Ø 0.26 m en la base a 0.18 m en el posado y 0.12 m en la punta, un
  nudo cada ~0.9 m (anillo oscuro `bamboo_dark`), el **nudo del posado** más grueso (Ø 0.30) con un cordón atado y **dos
  cascabeles de paja** colgando 0.3 m debajo (las cañas "suyas"), la copa de hojas desde 0.75 del alto. La Madre: Ø 0.40,
  diez nudos, un cordón rojo y cinco cascabeles.
* **Colores** (`nindo_palette`): culmo `bamboo_light` #a4c25a, nudos `bamboo_dry` #b8a35a, cordón `rope`, cascabeles
  `straw`, hojas `leaf` / `leaf_light`. El bosque de alrededor sigue en `bamboo` / `bamboo_dark`: las cañas de la arena son
  las más claras del claro y Chikuō (salvia y hojas oscuras) queda más oscuro que su caña, con la cabeza blanca encima.
* **Jerarquía** (una por FBX: `arena_stalk_inner` 7.5 m, `arena_stalk_outer` 8.5 m, `arena_stalk_north` 7.5 m con el
  posado a 4.0, `arena_stalk_mother` 10 m; y `arena_stalk_stump`, el tocón de 1 m con el corte en diagonal de cara clara):
  * `Stalk` (raíz, pivote en la base, sin animar) → `Seg_00` … `Seg_07` (cada tramo hijo del anterior, pivote abajo,
    ~1/8 del alto) → `Crown` (las hojas, hija del último tramo).
  * Vacíos, hijos del tramo que los lleva (así siguen al arco): `PerchNode` (sobre el nudo del posado, +Y a lo largo del
    culmo, +Z hacia el centro del claro), `GripHigh` (0.9 m arriba del posado, donde agarra la mano), `ClimbGrip` (2.2 m:
    donde agarra al trepar desde el piso), `BaseCut` (a 0.9 m: el punto del impacto y del sonido del corte), `ChimeL` y
    `ChimeR` (los dos cascabeles, para `SpringChain`).
  * Materiales: la paleta y **un slot que el código pueda hacer brillar** en el anillo del nudo de la base
    (`Stalk_GlintBase`, el destello blanco de la carga y el de "acá cae" de la caída del cielo).
  * Una **malla de grieta** oculta en `Seg_00` y `Seg_01` (`Crack`, una rajadura en diagonal de cara paja clara) que el
    código prende en la fase 3.
* **Colisión**: cápsula de r 0.16 m y 2 m de alto en la base (Kaito no la atraviesa; el bot la rodea), sin tallar el
  NavMesh más que un hueco de r 0.3. Sin colisión arriba (el arco y la inclinación no empujan a nadie).
* **No van al static batching** (se mueven); registradas en `ZoneCulling.AddDynamic` y con la marca `occluder`.
* **Marcadores en la arena**: instancias `ArenaStalk_N1` … `ArenaStalk_E2` y `ArenaStalk_M` en las posiciones de 8.1
  (o una lista `BOSS_STALKS` en `world_plan.py` que lea `WorldBuilder`), la Madre oculta hasta la fase 3.
* **El mundo**: sin decoración a menos de 1.5 m de cada base ni de la Madre; el resto de la decoración del claro (r 13)
  baja de alto (pasto, flores); la pared del bosque queda afuera de r 15. Un `LightPool` de luna sobre el claro para que el
  ensō blanco y la cabeza blanca de Chikuō se lean de noche. El piso del claro claro (`path` / `grass_dry`): el ensō blanco
  y los anillos tienen que leerse encima.

### 8.3 El comportamiento (código de `c4/chikuo`, `BambooStalk.cs`)

* **El arco**: cada `Seg_k` rota θ · w_k alrededor del eje horizontal perpendicular a la dirección del arco, con
  w_k ∝ (k + 1) normalizado (más arriba, más dobla: como una caña de pescar). θ es un resorte amortiguado (1.4 Hz, ζ 0.15)
  hacia la carga de la acción (6° quieto con él encima, 20° en la ráfaga, 25° silbador, 30° colgado, -35° catapulta, ±10°
  risa); al latigazo θ salta al opuesto y oscila (el latigazo se ve). Con su peso, el posado baja 0.4 m (recto → cargado).
* **Inclinada (fase 2)**: θ sostenido en 70° hacia afuera del claro (w_k parejo: la copa sobre el borde), temblando ±2° con
  la música; volver a la vertical en el cambio 2 es un latigazo de 0.4 s ("fuush").
* **Rajada**: `Crack` prendida, el culmo un 10 % más claro; **quebrada**: el tramo de arriba de la rajadura cae hacia
  afuera del claro (1.2 s, sin daño, polvo y hojas), se apaga y queda `arena_stalk_stump`. **Talada** (la tala): cae hacia
  Kaito por el carril rojo, queda tumbada 5 s (obstáculo) y se deshace en hojas.
* **La Madre**: crece de y = -10 a 0 en 1.5 s con tierra que estalla; la caña de más arriba de las siete.
* Todo vuelve al estado de la fase en un reintento (`ResetEnemy` → `BambooGrove.Reset(phase)`).

### 8.4 Dónde se posa, se cuelga y trepa (anclas)

* **Posado**: los dos pies sobre el nudo del posado (`PerchNode`), las suelas envolviendo el culmo, agachado; la mano
  izquierda en `GripHigh`. La raíz del modelo va en el `PerchNode` (posición y rotación: el cuerpo se inclina con el arco).
* **Colgado**: las corvas enganchadas en el culmo justo arriba del `PerchNode`, cabeza abajo (la cabeza a ~2.4 m del piso
  con el posado cargado a 4.0).
* **Trepada**: las manos en `ClimbGrip` (2.2 m) y después de dos tirones en `GripHigh`; los pies contra el culmo.
* **Agarre al caer**: las manos golpean en `GripHigh` en el primer cuadro del `LeapGrab`, las piernas se balancean y los pies
  encuentran el `PerchNode` en el sexto.
* La raíz del jefe (el GameObject: CharacterController, NavMeshAgent, fijado) **en la base de la caña** (sección 9).

---

## 9. La raíz, los golpes y la detección (código)

* **Posado, la raíz en la base de su caña** (`BaseCut` proyectado al piso). El modelo se dibuja en el `PerchNode`
  (`model.position` = el `PerchNode` del arco de este cuadro; el cuerpo sigue la rotación del tramo), como `VariantMotion`.
  Con eso, **sin tocar a Kaito**:
  * `PlayerController.DoAttackHits` le llega a la caña (la diferencia de altura de la raíz es 0) y `ReceiveHit` decide;
  * el imán del corte, el fijado (`LockFocus`) y el bot apuntan a la base: el blanco correcto;
  * el impacto sale en `AimPoint` (1.3 m sobre la base: el culmo) y el corte suena en la caña.
  * El `NavMeshAgent` queda quieto mientras está arriba (el código mueve el transform, como en sus vuelos de hoy) y la
    cápsula de la raíz se queda en la base (Kaito no se mete en la caña); en el aire la cápsula se apaga (no empuja a Kaito
    a 12 m/s) y vuelve al posarse o al tocar el piso.
* **En el aire** (salto, garrocha, picada) la raíz viaja con él por el piso (la cámara lo sigue); `HurtCenter` devuelve la
  **base de la caña de destino** en el salto (el imán de Kaito gira hacia ella: la caída del cielo se apunta sola) y la
  base de salida en la picada. `ReceiveHit` en el aire: `Ignored`, salvo el corte a la caña de destino en los últimos 0.45 s
  (caída del cielo).
* **`ReceiveHit` por estado**:

| Estado | Corte de Kaito | Devuelve |
|---|---|---|
| posado, colgado, trepando, agarrando, en la pértiga **con campanas blancas** | latigazo (dirección = `info.direction` plana) | `Hit` sin daño (hit-stop, Espíritu +3, furia +4, impacto en la caña); la caída daña al tocar el piso |
| posado sin campanas | "¡Cosquillas!" (7.2) | `Ignored` (el jefe pone el sonido y el temblor) |
| en el aire | caída del cielo o nada | `Hit` / `Ignored` |
| en un hueco | daño x(su multiplicador) hasta el tope | `Hit` / `Killed`; pasado el tope, `Ignored` |
| en el piso, neutral | x0.6 y voltereta | `Hit` |
| en el piso, cargando un golpe | x0.35, el golpe sigue | `Hit` |
| levantándose, en la garrocha, en un cambio de fase | nada | `Ignored` (el cambio de fase: `Blocked`, como hoy) |

* **Las habilidades**: el Corte del Viento (`CollectLineVictims` usa `HurtCenter`) y el Torbellino (`WhirlHit`) ya miden en
  el plano: con la caña cargada son latigazos a distancia (el Corte del Viento con ±25° de captura para el estampado); sin
  carga, "Cosquillas" (el Torbellino revienta los señuelos que toca). En el piso, daño normal.
* **Los dardos** (`BambooDart`, con pool como `WaterPearl`): la fuente del golpe es el dardo (un parry a 10 m no hace
  retroceder al jefe), `ProjectileEta` honesta contando el dardo por salir (el soplido que falta más el vuelo, como las olas
  de Mizuchi en `Boss.UpdateProjectiles`), el "¡ya!" con `GameEvents.RaiseStrikeCue(this, false)` (el jefe de fuente: el
  bot lo reconoce con `e.ProjectileEta < 0.5f`). Salen del socket `Staff_Muzzle` hacia el punto de impacto; el clip apunta
  a 35° hacia abajo y el código gira el pecho (±20° de pitch, suave) para que la flauta coincida con el tiro.
* **Los rojos** son las zonas que ya existen (`HitAreaFor`: disco o carril) y `OnUnblockableTelegraph`; los dorados en el
  piso, `AttackPattern` comunes con los tiempos del sidecar (sección 16).

---

## 10. La cámara

* **Perfil** (`ICameraProfile`): `CameraPitch` 0 (los 45° de pelea de siempre), `CameraExtraDistance` **2.4 m posado o en
  el aire** y 1.6 m en el piso (la propiedad es dinámica). Mientras está arriba (posado, salto, pértiga):
  `Game.Camera.SetFocusBias(Vector3.up * 0.45f * alturaDelPosado)` (CameraDirector ya lo amortigua a 2/s); en el piso,
  `Vector3.zero`. El auto-encuadre (hasta 3 m) queda de red.
* **Encuadre medido** (`--camera`, cámara de pelea sin fijar, cabeza de Chikuō bajo el 92 % y pies de Kaito sobre el 8 %):

| Caña | Desde dónde de la arena está en cuadro | Con el auto-encuadre | Desde 4-8 m (adonde salta) | Su cuerpo tapa a Kaito |
|---|---|---|---|---|
| N1 | 75 % | 84 % | 100 % | 0.5 % |
| N2 | 54 % | 64 % | 100 % | 0.3 % |
| O1 | 90 % | 99 % | 100 % | 1.0 % |
| O2 | 71 % | 82 % | 100 % | 1.0 % |
| E1 | 95 % | 99 % | 100 % | 1.0 % |
| E2 | 77 % | 83 % | 100 % | 0.5 % |
| M | 92 % | 99 % | 100 % | 0.5 % |

* Sin el sesgo del foco, posado a 4.0 m solo entraba hasta 3.1 m al norte de Kaito; con 0.45 x posado entra hasta 10.5 m.
  El pitch casi no cambia nada (48 o 50° dan lo mismo ±0.5 m): se queda en 45 para no cambiar el ángulo de la pelea.
* **Alto en pantalla** (1080 px): Kaito 79 px, Chikuō agachado posado a 6 m 104 px, parado en el piso 160 px.
* **Regla de cuadro**: antes de cada acción posado, si su caña no está en cuadro con la cámara de ese cuadro, salta a una
  que sí (7.1); los saltos solo van a cañas en cuadro (7.3). Nunca un ataque que arranque fuera de pantalla.
* **Fijado**: `LockFocus` encuadra la raíz (la base) con su `config.height` (2.4, tope 2.6); el sesgo del foco se suma
  después (`targetFocus += focusBias`), así que también vale fijado. No hace falta tocar `CameraDirector`.

---

## 11. Justicia (salida de `--fair`)

### 11.1 Rojos: cuánto hay que salir y cuánto se corre

Reacción de 0.30 s al **ver aparecer el anillo** (la lectura predictiva); Kaito corre con 40 m/s² hasta 6.2 m/s:

| Rojo | Anillo | Fija | "¡ya!" | Hay que salir | Corriendo | Margen |
|---|---|---|---|---|---|---|
| Picada de la Grulla (disco 1.6) | 0.95 s | 0.45 s | 0.42 s | 1.95 m | 3.55 m | +1.60 |
| Silbador (carril 1.0) | 1.00 | 0.25 | 0.42 | 0.85 | 3.86 | +3.01 |
| Barrido de Caña (disco 3.6 en la base, Kaito a 1.5 m) | 0.85 | 0.45 | 0.42 | 2.45 | 2.93 | +0.48 |
| Catapulta (carril 1.8) | 1.00 | 0.75 | 0.42 | 1.25 | 3.86 | +2.61 |
| Tala (carril 1.6) | 1.00 | 0.45 | 0.42 | 1.15 | 3.86 | +2.71 |
| Barrida del Bastón (disco 2.6, Kaito a 1.2 m) | 0.80 | 0.45 | 0.42 | 1.75 | 2.62 | +0.87 |
| Brote de la respuesta (disco 1.0) | 0.85 | 0.45 | 0.42 | 1.35 | 2.93 | +1.58 |
| Picada de la pértiga (disco 1.4) | 0.95 | 0.45 | 0.42 | 1.75 | 3.55 | +1.80 |

El dash (6.5 m en 0.26 s, i-frames 0.02-0.24) sale de cualquiera. Quieto hasta el "¡ya!" no se sale corriendo de ninguno
de más de 0.5 m: la regla de siempre (rojo = dash o venir moviéndose).

### 11.2 Dardos

* Vuelo desde el posado a 4.0 m: fase 1 (16 m/s) 0.27 s a 3 m, 0.36 a 5, 0.48 a 7, 0.59 a 9, 0.71 a 11; fase 3 (18 m/s)
  0.24 / 0.32 / 0.42 / 0.53 / 0.63. El anillo a los pies desde que levanta la flauta (0.45 s o más antes del soplido) y el
  "¡ya!" a 0.38 s del golpe aunque el vuelo sea más corto (la ETA cuenta el soplido que falta).
* Entre dardos de una tanda: Dos Dardos 0.35 s, Tres Notas 0.38, Cuatro Notas 0.28, Colgado 0.30, Respuesta 0.44. Con el
  "¡ya!" a 0.38 y una reacción de 0.28 el parry siguiente se aprieta 0.18-0.34 s después del choque; `ParrySuccess` deja
  apretar desde 0.06 s. **Nunca dos dorados a menos de 0.28 s.**
* Corriendo de costado: en un vuelo de 0.45 s Kaito se corre 2.8 m; con la puntería adelantada al 50 % (fase 1) le quedan
  1.4 m de margen contra el radio de 0.6 (se esquiva corriendo); al 80 % (fase 3) 0.6 m (hay que parar o dashear).

### 11.3 Latigazo y caída del cielo

* Ventanas: la tabla de 2.2 (desde cuántos metros se llega corriendo y con el dash, reacción 0.30 / 0.36 s).
* Caída del cielo en la fase 1 (agachado 0.22 + vuelo): salto de 5 m (0.69 s) se ataja con el dash desde 4.5-8 m; de 9 m
  (0.83 s) corriendo desde 4.5 m. En la fase 3 (0.54-0.66 s) **no se ataja reaccionando**: hay que haber leído el
  ping-pong o la Última Canción y estar ahí. Es el techo de la pelea, a propósito.

### 11.4 Reglas de cuadro y de densidad

* Nada arranca fuera de cuadro (10); nunca dos golpes ilegibles juntos: un solo anillo de Chikuō por vez salvo los dardos de
  una misma tanda (cada uno con su anillo y su "¡ya!", separados 0.28 s o más) y las notas de la respuesta; entre el último
  golpe de una acción y el primero de la siguiente, el respiro (0.25-0.45 s; 0.12-0.25 en la 3) más el arranque de la
  acción (0.45 s como mínimo hasta un soplido).

---

## 12. Balance (salida de la pelea simulada)

### 12.1 Qué es este número

`chikuo_v2_check.py` simula la pelea en 2D a 60 Hz con las reglas de este documento y el bot de AutoPilot con los ganchos
de la sección 13 (los mismos niveles y el mismo combo que `boss_sims/kaito.py`). **No es el port del código** (no tiene
los clips, el rodeo de las cañas ni el stick relativo a la cámara). El factor real/simulado de esta pelea **no está
medido**: el Chikuō viejo dio 1.42 (en Unity el bot rondaba más), Mizuchi 1.19, Kokuyō 0.92, Gorō 0.71. Para esta, con un
bot que corre entre cañas y un jefe que salta, espero **1.2-1.4**. `--calib F` pone el daño de Kaito en 1/F (la misma
calibración de `boss_sims/calibration.py`): lo que dice son segundos de juego.

### 12.2 Resultados (400 peleas por nivel, semilla 7; la 11 da lo mismo ±2 %)

Tiempo total = lo que mide el PlayClock (con las muertes, la vuelta del santuario y el reintento):

| Factor supuesto | Bueno | Promedio |
|---|---|---|
| 1.00 (la simulación cruda) | **226 s = 3.8 min**, 0.00 muertes (p10 203, p90 251) | 281 s = 4.7 min, 0.48 muertes, 56 % sin morir |
| 1.15 | 4.3 min, 0.00 | 6.5 min, 0.84 |
| **1.30** | **4.8 min, 0.01 muertes** (p10 4.4, p90 5.4), 99 % sin morir | **7.3 min, 1.27 muertes** (p90 10.4), 12 % sin morir |
| 1.42 (el del Chikuō viejo) | 5.3 min, 0.02 | 9.0 min, 1.74 |

Con F 1.3 (bueno): fases de 112 / 45 / 131 s (la 3, el clímax, la más larga; la 2, el interludio, la más corta).

Salida de `python Tools/Dev/chikuo_v2_check.py --runs 400 --calib 1.3` (bueno), recortada:

```
== bueno: 400 peleas | total (lo que mide el PlayClock) 290 s = 4.8 min (p10 262, p90 322) | intento ganador 290 s
   | muertes 0.01 (sin morir 99 %; en la fase 1/2/3: 0.00/0.00/0.01)
   fases del intento ganador (mediana): 112 / 45 / 131 s
   amenazas por minuto (golpes, dardos, zonas): 20 / 34 / 24 (fuera de sus huecos: 28 / 46 / 32); acciones por minuto
   (cada cosa que decide: ataque, salto, pértiga) 33 / 12 / 36
   arriba (caña, salto, pértiga) 55 / 7 / 57 % del tiempo; abierto (en un hueco) 29 / 26 / 27 %
   tiempo muerto (ni aviso, ni campanas blancas, ni hueco, ni salto): 19 %; el tramo más largo 3.30 s
   daño en la fase 1: hueco_revolcon 52%, caida_revolcon 15%, hueco_estampado 10%, hueco_contra 8%, hueco_pies 5%,
   caida_estampado 4%, hueco_tropiezo 3%
   daño en la fase 2: hueco_contra 27%, hueco_revolcon 23%, carga 17%, neutral 12%, hueco_desafinado 10%, ...
   daño en la fase 3: hueco_revolcon 29%, hueco_estampado 24%, caida_estampado 11%, caida_revolcon 10%, hueco_contra 8%, ...
   latigazos por fase: 13.2 / 3.0 / 13.8 (uno cada 8.5 / 14.9 / 9.5 s del intento ganador)
   por pelea: latigazo_revolcon 19.0, latigazo_estampado 6.1, latigazo_caida 0.2, latigazo_resbalon 1.7,
   latigazo_pertiga 3.0, cargas 63.9, saltos 21.0, ping_pong 10.3, dash_al_latigazo 11.6, hueco_pies 6.1, ...
   daño a Kaito (102 por pelea): ground 17%, cuatro_notas 9%, baston 9%, dos_dardos 8%, barrido 8%, colgado 8%, ...
== promedio: 400 peleas | total 437 s = 7.3 min (p10 328, p90 622) | muertes 1.27 (sin morir 12 %; en la fase 1/2/3:
   0.00/0.30/0.97)
```

Lectura:

* **El latigazo es el corazón**: ~83 % del daño de la fase 1 (revolcón, estampado, resbalón y sus caídas) y ~74 % de la 3;
  en la 2, la pértiga (28 %) y las contras (27 %). Unos 30 latigazos por pelea de 64 cargas (47 %: el bot ve las campanas
  de lejos el 75 % de las veces, reacciona y no siempre llega): 13.2 / 3.0 / 13.8 por fase, **uno cada 8.5 / 14.9 / 9.5 s**.
* **Dinámico**: fuera de sus huecos, 28 / 46 / 32 amenazas por minuto (una cada 1.3-2.1 s, más los saltos); 33-36
  decisiones por minuto arriba; arriba el 55-57 % del tiempo en las fases 1 y 3 y abierto el ~28 %: la pelea alterna
  presión y revancha sin esperas.
* **Dónde muere el promedio**: en la fase 3 (0.97 de las 1.27), que es el clímax; en la 2 (0.30), el piso. Nunca en la 1
  (es la que enseña).
* **Contra Kokuyō** (lo que predijo C3 para su retoque: bueno 4.35 min, promedio 6.9 min con 1.4 muertes): con F 1.3
  Chikuō dura un poco más para el bueno (4.8, el objetivo del líder era 4.5-5) y mata menos al promedio (1.27 contra 1.4).
  Si el lead quiere que Kokuyō sea claramente el más largo, el ajuste es de Kokuyō (como dijeron las tres propuestas).
* **Cómo se llegó acá**: el bot real reacciona (no corta en el cuadro en que se encienden las campanas: lo modela
  `BotCutGoal`, 13.1); con eso el daño de la primera versión dejaba al promedio en 2.9 muertes, y se bajó todo a x0.85
  (los dardos a 2.5) con las caídas más pesadas (12 / 24 / 36): el viejo pega poco y seguido, y lo que se gana bajándolo
  pesa más.

### 12.3 Perillas (en un solo bloque, como `GoroBoss`; el lead las mueve con el PlayClock)

`python Tools/Dev/chikuo_v2_check.py --knobs --runs 250 --factors 1.0,1.15,1.3,1.42` (minutos del PlayClock y muertes
medias; semilla 7; se puede correr un factor por proceso; con 250 peleas "hoy" en F 1.3 da 7.1 min y no los 7.3 de las
400 de 12.2). Bueno / promedio:

| Perilla | F 1.00 | F 1.15 | F 1.30 | F 1.42 |
|---|---|---|---|---|
| hoy | 3.8 / 4.8 min, 0.50 | 4.3 / 6.4, 0.82 | **4.8 / 7.1, 1.21** | 5.3 / 8.9, 1.70 |
| **tope del revolcón 3 → 2** (también en la fase 3) | **4.3 / 6.3, 0.80** | 4.9 / 7.4, 1.30 | 5.6 / 9.3, 1.94 | 6.1 / 10.9, 2.66 |
| tope del revolcón 3 → 4 | 3.6 / 4.3, 0.38 | 4.2 / 6.0, 0.68 | 4.7 / 7.1, 1.15 | 5.2 / 7.9, 1.57 |
| **revolcón de 2.0 s con tope 4** (fase 3: 1.8 s) | 3.5 / 4.1, 0.26 | 4.1 / 5.0, 0.51 | 4.5 / 6.7, 0.85 | **4.9 / 7.5, 1.17** |
| **caídas a la mitad** (6 / 12 / 18) | 4.1 / 6.1, 0.69 | **4.7 / 7.2, 1.20** | 5.3 / 8.9, 1.80 | 5.7 / 10.1, 2.30 |
| caídas x1.5 (18 / 36 / 54) | 3.5 / 4.0, 0.24 | 4.0 / 5.6, 0.55 | 4.4 / 6.6, 0.97 | 4.9 / 7.5, 1.35 |
| daño a Kaito x1.1 | 3.8 / 5.4, 0.64 | 4.3 / 6.5, 1.13 | 4.9 / 7.9, 1.76 | 5.3 / 9.4, 2.39 |
| daño a Kaito x0.9 | 3.8 / 4.3, 0.20 | 4.3 / 5.2, 0.48 | 4.8 / 7.2, 0.87 | 5.3 / 8.1, 1.24 |

Lectura: **el tiempo lo mueve lo que le entra en cada hueco** (el tope del revolcón, el hueco más común, y la caída); subir
el tope solo no alcanza porque el bot ya no llega a dar el cuarto corte en 1.6 s: hay que alargar el hueco con él. **Las
muertes las mueve `DamageScale`**, que casi no cambia el tiempo del bueno.

**Regla para calibrar** (medir con `prueba_bambu.json`, tres peleas por bot):

| El bueno real da | Factor | Qué cambiar | Queda (simulado) |
|---|---|---|---|
| ~3.8 min | ~1.0 | tope del revolcón 2 | bueno 4.3, promedio 6.3 con 0.8 muertes |
| ~4.3 min | ~1.15 | caídas a la mitad | 4.7 / 7.2 con 1.2 |
| 4.5-5.0 min | 1.25-1.35 | nada | 4.8 / 7.1 con 1.2 |
| ~5.3 min o más | ~1.42 | revolcón de 2.0 s con tope 4 | 4.9 / 7.5 con 1.2 |

Si da más de 6 min, el revolcón de 2.0 s con tope 4 y las caídas x1.5 juntos (sin probar en la simulación). Si después de
eso el promedio muere más de 2 veces, `DamageScale` 0.9; menos de una, 1.1. En `boss_sims/calibration.py`, la entrada
`MEASURED["chikuo"]` de hoy es la del Chikuō viejo (361 s reales contra 254 simulados): se reemplaza por las líneas del
PlayClock del nuevo con la simulación cruda de este archivo (`sim_bueno=226.0, sim_promedio=(281.0, 0.48)`) y el factor
sale solo.

---

## 13. AutoPilot: cómo pelea el bot y los comandos de prueba (hunk en `Input/AutoPilot.cs`)

### 13.1 El bot contra Chikuō (`bot on bueno|promedio|experto`)

El bot de hoy va hacia `nearest.transform.position`, corta a menos de 2.6 m si no hay un anillo a la vista (`InTell`) y
nunca contra una guardia. Contra Chikuō necesita tres ganchos, todos detrás de una interfaz que implementa el jefe (en
`BambooMasterBoss.cs`, archivo propio), así el hunk en AutoPilot son unas pocas líneas:

```csharp
// en BambooMasterBoss.cs
public interface IBotHints
{
    Vector3 BotTarget { get; }            // adónde ir: la base de su caña; mientras salta, la de salida hasta que agarre
    bool BotMayCut { get; }               // posado, trepando o en la pértiga: solo con las campanas blancas
    bool BotCutGoal(out Vector3 goal, out float until);   // la base cargada (o la caña de destino de un salto)
}
```

* **BotTarget**: posado, la base de su caña; **mientras salta, la base de salida hasta el agarre** (un jugador que
  reacciona no corre debajo de un salto de 0.6 s; la simulación lo modela así y el factor real/simulado depende de que el
  bot haga lo mismo); en el piso y en los huecos, la raíz.
* **BotMayCut**: el bot no le corta la caña sin campanas (como no le pega a una guardia); de apurado sí, con la misma
  probabilidad `greedy` con la que ataca un anillo (bueno 10 %, promedio 15 %), y se come el barrido.
* **BotCutGoal** (el latigazo): cuando arranca una carga, el bot **la nota** a un tiempo de reacción N(rtMean + 0.02,
  rtSd) de su nivel: **de lejos** con probabilidad experto 0.95, bueno 0.75, promedio 0.55 (ver las campanas y decidir ir);
  **al pie de la caña** (a 3 m o menos) como cualquier aviso (no lo ve el 10 / 15 %). Hasta que la nota no corta, aunque
  esté debajo (una persona tampoco corta en el mismo cuadro en que se encienden). Va a la base (con el **dash** si está a más de
  3.7 m y tiene 15 de Espíritu) y corta al llegar, aunque haya un anillo a la vista; las defensas pendientes (los "¡ya!")
  siguen teniendo prioridad. **La caída del cielo**: en un salto a una caña a 7 m o menos de Kaito, el bot va a la caña de
  destino con probabilidad experto 0.25, bueno 0.06, promedio 0.02.
* El bot no usa las habilidades (como hoy).

### 13.2 Comandos nuevos (dentro de `case "chikuo"`, además de `chikuo fase N`)

| Paso | Qué hace |
|---|---|
| `chikuo cana ID` | se posa ya en la caña ID (N1 N2 O1 O2 E1 E2 M) |
| `chikuo salto ID` | salta ya a la caña ID (con su agachado y su ensō) |
| `chikuo mov NOMBRE` | hace ya esa acción si puede: `dardo`, `dos`, `notas`, `silbador`, `colgado`, `risa`, `picada`, `baston`, `barrido`, `catapulta`, `tala`, `ermitanos`, `pertiga`, `pregunta`, `soplo` |
| `chikuo abrir TIPO` | lo pone en ese hueco para revisar los clips: `revolcon`, `estampado`, `caida`, `resbalon`, `afinado`, `pies` |
| `chikuo canas` | escribe el estado de las cañas en el Editor.log (en pie, rajada, quebrada, inclinada) |
| `chikuo canas reset` | todas en pie (las de la fase) |

Líneas del Editor.log (números con `CultureInfo.InvariantCulture`): `[Nindo] Chikuō: latigazo O1 -> estampado (O2),
Kaito a 1.62 m, 'Corte 1'`, `[Nindo] Chikuō: caída del cielo en N1 (0.31 s antes del agarre)`, `[Nindo] Chikuō:
cosquillas en E1 (barre)`, `[Nindo] Chikuō: caña E2 rajada` / `quebrada` / `talada`, `[Nindo] Chikuō: afinado` /
`desafinado`, `[Nindo] Chikuō: fase 2 (el piso)`.

---

## 14. El modelo (contrato para el paso de modelado)

* **Al pie de la letra del concepto** (`conceptos/chikuo_v2/elegido_*.jpg`) en el estilo de Nindō: low-poly facetado,
  colores planos de la paleta, siluetas gruesas, nada más fino que 4 cm (los cascabeles y la flauta, 6 cm o más).
* **Alto 2.45 m** hasta la punta del moño (la coronilla a 2.2 m; `CharacterFactory` normaliza con el `height` de
  NindoContent, que pasa a la medida nueva; `config.height` 2.4 sigue). El concepto lo dibuja 2.6 veces más alto que
  Kaito: es una exageración de hoja. A 2.45 m (1.6 veces Kaito) agachado en el posado mide ~1.5 m (104 px en pantalla) y
  su mano agarra un culmo de 0.2 m; a 4 m el viejo no cabría en las cañas. **Las proporciones sí son las del concepto**:
  flaco, de miembros largos, manos y pies grandes, la cabeza 1/7 del alto con el moño, la barba larga hasta el ombligo.
* **Cabeza**: calvo arriba, **moño blanco** atado con cordón verde (`leaf`) y una hoja; **cejas blancas en punta** salvajes
  (que se lean de arriba); orejas en punta; sonrisa con dientes en punta (`white`); **barba blanca larga anudada** al final
  (el nudo y la punta: los dos se leen desde la cámara); arrugas como facetas. Expresiones (formas o huesos de la cara):
  sonrisa pícara (la de siempre), soplando (cachetes inflados, labios a la boquilla), riéndose (boca abierta, ojos cerrados),
  tocando la flauta (ojos cerrados).
* **Ropa**: gi de karate **salvia** (`grass_teal` #3e6b55, el lado en sombra `leaf_pine` #2f5a3c) con **ribete paja**
  (`straw` #d2bd80) en el cuello, los puños y el ruedo; **faja verde anudada** (`leaf` #4c8a3e, el nudo al frente y dos
  colas); pantalón ancho salvia; **polainas vendadas oscuras** (`cloth_black` con vendas `stone_moss`); **sandalias-zapato**
  negras (`black`) con suela y tiras paja.
* **La capa de hojas**: hojas de bambú en capas que cuelgan de los hombros hasta las corvas, en tres tonos (`bamboo` arriba,
  `leaf` al medio, `leaf_dark` abajo: más oscura que sus cañas), 10-12 paneles.
* **Los cascabeles**: **~24 tubos huecos de bambú paja con agujeros** colgando de cordones de la capa: ~10 cortos en los
  hombros (los agudos) y ~12 largos en el ruedo (los graves); tubos de 6 lados abiertos, agujeros como caras oscuras
  (`gold_dark`), cordón `rope`. Son la luz de la pelea: dos materiales de brillo (abajo).
* **La flauta-bastón**: bambú **paja-amarillo** (`wheat` #d9b85a, nudos `bamboo_dry`), **2.1 m**, Ø 6 cm, 6 nudos con
  anillos de cordón verde, 6-7 agujeros en el tercio de arriba (las caras oscuras), **empuñadura vendada oscura** (`ink`) de
  0.30 m cerca de la punta de abajo. Se toca de costado (la música) y de punta como cerbatana (los dardos).
* **Los dardos**: aguja de bambú de 0.25 m (paja) con la cola de hoja verde; el silbador, uno grueso de 0.4 m con la cola
  roja (el rojo del aviso).
* **Materiales de brillo** (`CharacterGlint`): `Chikuo_GlintChimesHi` (los cascabeles de los hombros), `Chikuo_GlintChimesLo`
  (los del ruedo), `Chikuo_GlintStaff` (la flauta-bastón), `Chikuo_GlintFootR` / `Chikuo_GlintFootL` (las patadas). El
  código los enciende en dorado (dardo, bastonazo), rojo (rojos) o blanco (carga).
* **El señuelo de hojas**: la misma malla con un material de hojas (sin piel ni ropa, `leaf` / `leaf_dark` sin brillo) y
  los cascabeles de hoja (sin material de brillo): `Chikuo_Decoy`.
* **Lectura de noche**: contra las cañas `bamboo_light` y el bosque oscuro, lo que da valor es el blanco (moño, cejas, barba:
  arriba del todo de la silueta), la paja (ribete y 24 cascabeles alrededor), el rim de `CharacterLit`. Renderizarlo con la
  cámara del juego sobre los colores de la arena antes de darlo por bueno.
* **Presupuesto**: ~9000 triángulos en total (cuerpo y ropa ~5000, capa ~2400, cascabeles ~1000 a ~40 cada uno, flauta
  ~400); un solo SkinnedMesh más la flauta rígida.
* **El pipeline**: `Tools/Blender/bosses/bamboo_master/` se rehace para el ermitaño (modelo, rig, clips, sidecar, lint); se
  conservan la ruta y el GUID de `BambooMaster.fbx` y del sidecar, y los `.mat` viejos que nadie use se borran con su `.meta`.
  Varios nodos raíz en el FBX (el esqueleto, hoy `BambooMaster/…`, y las mallas) como hoy: el clip no se aplana a la raíz.

## 15. El rig (contrato)

* Esqueleto de juego limpio como el de hoy (`master_rig.py`): manos bajo antebrazos, pies bajo tibias, sin huesos de IK en
  el FBX, una sola raíz `Root` (sin animar: ninguna curva en la raíz del modelo).
* Cadena humana: `Hips`, `Spine`, `Spine1`, `Spine2`, `Neck`, `Head`, **`Jaw`** (la risa, soplar), hombros, brazos,
  antebrazos, manos, muslos, tibias, pies.
* **Dedos para agarrar** (la caña y el bastón): pulgar, índice, medio, anular y meñique de dos falanges (como hoy), con
  las poses de mano del sidecar: puño en la caña (el culmo de 0.2 m), puño en el bastón (6 cm), palma, garra.
* **`Toe_L` / `Toe_R`**: la suela se dobla para envolver el culmo en el posado y para pararse en punta.
* **`Staff`** (la flauta-bastón): hueso rígido hijo de `Root`, libre en el mundo, las manos lo agarran por IK (se puede
  girar, pasar de mano, cruzar en los hombros, clavar en el piso). Sockets (vacíos hijos de `Staff`): `Staff_Mouth` (la
  boquilla), **`Staff_Muzzle`** (la punta de donde salen los dardos), `Staff_Grip` (el vendado).
* **El bastón en los hombros** (PerchIdle, la hoja de acciones): detrás del cuello, las muñecas colgando sobre él; en el
  código es un estado de `Staff` pegado a `Spine2` con un desfase fijo (sin física).
* **Cadenas** (`Acc_Tie<Nombre>_0..2` + `_end`, la convención de los kits; horneadas en los clips y reemplazables por
  `SpringChain` con las esferas `AccCol_*` del pecho, la cadera y los muslos): barba (4 tramos con el nudo), moño (2),
  cola del cordón del moño (2), colas de la faja (2 x 2), mangas (2 x 2), 10-12 paneles de la capa (2 tramos cada uno,
  más pesados), **cascabeles: un hueso por tubo** colgando de su cordón (`Chime_Hi_00..09`, `Chime_Lo_00..11`, péndulos:
  en el juego `SpringChain` con perfil "Chime", así suenan y se mueven solos).
* **Cejas** rígidas (`Brow_L/R`, como hoy).

## 16. Los clips (contrato para el animador)

A 30 cuadros por segundo. Sidecar `BambooMaster.fbx.json` como hoy (`timing`, `normalized`, `events`, `travel_m`,
`ring_m`, `marker_m`, `chain_from` / `chain_to`, `glow`, `strike`) y `Tools/Unity/bamboo_master_timings.py` lo pasa a
`BambooMasterTimings.cs`: **el código lee los tiempos del sidecar** (lo de abajo es el objetivo; ±1 cuadro está bien si el
sidecar lo dice). Eventos nuevos: `Load` / `Unload` (empieza y termina la carga), `DartSpawn`, `LeaveStalk`, `GrabStalk`,
`Perch`, `Hang`, `Land`, `Contact`, `Plant`, `Note`, `Stamp`, `AimFix`, `Kick`.

**Posado y colgado se autoran en el espacio del `PerchNode`** (la caña recta, a 4.4 m; el código mueve el cuerpo con el
arco): manos y pies trabados en el culmo **< 2 cm**, medido en el lint con el arco del código aplicado (8.3, θ de la
acción). Ningún clip anima la raíz `Root`; las curvas van bajo el nodo del esqueleto del modelo como hoy
(`BambooMaster/…`; el FBX tiene más de un nodo raíz, así que Unity no lo aplana; verificar igual que las rutas empiecen como
en el modelo, la lección de octubre).

### 16.1 Arriba

| Estado | Cuadros | Loop | Eventos (cuadro) | Notas |
|---|---|---|---|---|
| `PerchIdle` | 48 | sí | | agachado sobre el nudo (la pose del concepto), el bastón cruzado en los hombros, la izquierda en `GripHigh`; se hamaca 2 cm con la caña; la sonrisa pícara |
| `PerchDart` | 24 | | apex 8, `DartSpawn` 14 | baja el bastón de los hombros a la boca (cerbatana, las dos manos cerca de la boquilla), apunta, sopla; vuelve |
| `PerchDart2` | 34 | | `DartSpawn` 14, 24 | |
| `PerchVolley` (Tres Notas) | 51 | | `Load` 3, `DartSpawn` 17, 28, 39, `Unload` 42 | se echa atrás (la caña se arquea), tres soplidos con un rebote de hombros cada uno |
| `PerchVolley4` (Cuatro Notas) | 48 | | `Load` 3, `DartSpawn` 14, 22, 30, 39, `Unload` 40 | fase 3 |
| `PerchWhistle` (Silbador) | 42 | | `Load` 3, apex 24, `DartSpawn` 27, `Unload` 30 | gran inspiración, cachetes inflados; en la fase 3 el código lo toca a x1.125 |
| `TalaShot` | 30 | | `DartSpawn` 14 | el silbador corto hacia una caña vecina (el código gira el cuerpo) |
| `HangDrop` | 11 | | `Hang` 10 | se deja caer de espaldas y queda colgado de las corvas |
| `HangDart2` | 18 | | `DartSpawn` 9, 18 | cabeza abajo soplando (la pose de la hoja original), la barba cuelga hacia arriba |
| `HangClimb` | 15 | | `Unload` 8, `Perch` 15 | abdominal de vuelta al posado |
| `PerchLaugh` | 36 | sí | | carcajada, se palmea la rodilla, los cascabeles se sacuden |
| `PerchWobble` | 8 | | | manotea (cortaron la caña sin campanas) |
| `StalkSweep` (Barrido de Caña) | 41 | | `Load` 8, apex 20, `Contact` 26 | se cuelga del costado y la caña (código) barre; vuelve a posarse |
| `CatapultDraw` | 30 | | `Load` 0, `AimFix` 22, `LeaveStalk` 30 | agachado tensando la caña hacia atrás como un arco, el bastón en los hombros |
| `CatapultKick` | 15 | | `Contact` 15 | la patada voladora por el carril (el código lleva el cuerpo) |
| `LeapCrouch` | 7 | | `LeaveStalk` 7 | se agacha y mira la caña de destino (la cabeza gira primero); fase 3 a x1.57 |
| `LeapAir` | 12 | sí | | el salto del concepto: una pierna estirada, el bastón en una mano, la capa y los cascabeles flameando |
| `LeapGrab` | 6 | | `GrabStalk` 0, `Perch` 6 | las manos golpean `GripHigh`, las piernas se balancean, los pies encuentran el nudo |
| `Climb` | 24 | | `GrabStalk` 4, `Perch` 24 | desde el piso, el trepar del concepto: dos tirones mano sobre mano, los pies contra el culmo |
| `DecoySpin` | 18 | | | gira con la capa abierta (los señuelos repiten este y los de arriba con 0.25 s de eco) |

### 16.2 Al piso y de vuelta

| Estado | Cuadros | Eventos | Notas |
|---|---|---|---|
| `Dive` (Picada de la Grulla) | 29 | `LeaveStalk` 10, `Contact` 28 | agachado y patada voladora en picada (la pose del concepto); `marker_m` y `ring_m` 1.6 |
| `DiveLand` | 14 | `Land` 0 | aterriza agachado, el pie de la patada clavado; queda cortable 0.45 s |
| `FeetStuck` | 48 | | los pies enterrados hasta el tobillo, tironea (Pies Enterrados) |
| `StaffDrop` (Bastón que Cae) | 27 | `LeaveStalk` 6, `Land` 19, apex 20, `Contact` 26 | cae al lado de Kaito con el bastón en alto y lo baja de golpe |
| `StaffDropRecover` | 12 | | |
| `Vault` (garrocha) | 27 | `Plant` 6, `LeaveStalk` 9, `GrabStalk` 27 | clava el bastón, salta apoyado en él y agarra la caña (el código lleva el arco: 0.9 s) |
| `JumpCrouch` | 9 | `LeaveStalk` 9 | el agachado de la vuelta (cortable: Tropiezo) |

### 16.3 Los huecos

| Estado | Cuadros | Loop | Notas |
|---|---|---|---|
| `FlungAir` | 12 | sí | dando vueltas en el aire, los cascabeles en estela |
| `FlungLand` | 11 | | toca el piso rodando |
| `DazedSit` | 30 | sí | sentado, mareado, hojas que le giran sobre la cabeza (revolcón, estampado, resbalón, tropiezo) |
| `DazedSitHit` | 10 | | el sacudón de cada corte sentado (los cascabeles suenan) |
| `Splat` | 9 | `Contact` 2 | se estrella contra la otra caña a ~3.5 m (el estampado) |
| `SlideDown` | 18 | | se desliza por esa caña hasta sentarse |
| `MissGrab` | 14 | | la caña se le escapa de las manos (caída del cielo) |
| `DazedLie` | 30 | sí | de espaldas, pataleando |
| `DazedLieHit` | 10 | | |
| `Slip` | 15 | | resbala trepando y cae sentado |
| `Stumble` | 30 | | tropieza en el agachado, rodilla al piso |
| `PoleFall` | 14 | | el bastón cortado se dobla y lo tira |
| `GetUp` | 12 | | de un salto (kip-up), invulnerable; a `READY` |
| `Detuned` | 42 | | tose hojas, la flauta chilla (Desafinado) |
| `Tuned` | 36 | sí | pierde pie, sentado aplaudiendo despacio (Afinado) |
| `StaffStuck` | 33 | | el bastón clavado, tironea (Bastón Clavado) |

### 16.4 El piso (fase 2 y la coda)

| Estado | Cuadros | Eventos | Notas |
|---|---|---|---|
| `Idle`, `Walk` (1.6 m/s), `Run` (5.5 m/s, saltarín de viejo), `StrafeL`, `StrafeR`, `WalkBack` | | | el blend tree `Locomotion` como hoy; los pies no patinan a esas velocidades |
| `BackFlip` (Paso del Ermitaño) | 12 | aire 2-10 | 2.5 m atrás (`travel_m`) |
| `HopBack` | 14 | aire 3-12 | 4 m atrás (antes de la pértiga y de la pregunta) |
| `Thrust` (Estocada; la Revancha y el bastonazo de después de aterrizar) | 27 | apex 9, `Contact` 15 | dorado, 2.4 m |
| `StaffSpin2` (Flauta Giratoria) | 30 | `Contact` 17, 29 | dos golpes con el giro del concepto (hojas en espiral) |
| `CraneKick` (Patada de Grulla) | 28 | `Contact` 15 | rodilla arriba, brazos abiertos |
| `NoteSmash` (Golpe de Nota) | 36 | apex 14, `Contact` 20 | la flauta arriba, suena una nota |
| `LowSweep` (Barrida del Bastón) | 39 | apex 16, `Contact` 24 | rojo, disco 2.6 m, a ras del piso |
| `GroundDart` (Soplo) | 25 | `DartSpawn` 17 | |
| `PolePlant` | 14 | `Plant` 8 | clava el bastón vertical |
| `PoleClimb` | 14 | `Load` 0 | sube por el bastón |
| `PoleBalance` | 30 | sí | parado en un pie sobre la punta, como una grulla, los brazos abiertos |
| `PoleDive` | 29 | `LeaveStalk` 0, `Contact` 28 | la picada desde la punta (1.4 m) |
| `FluteRaise` | 14 | | se lleva la flauta de costado a la boca (la pose del concepto) |
| `FluteNote` | 13 | `Note` 0 | una nota (la pregunta: el código la repite por nota) |
| `AnswerBlow` | 13 | `DartSpawn` 4 | la nota aguda de la respuesta: de punta, sopla un dardo |
| `AnswerStamp` | 13 | `Stamp` 4 | la nota grave: golpea el piso con el bastón y brota el retoño |
| `GroundLaugh` | 36 | sí | |

### 16.5 Historia y reacciones

| Estado | Cuadros | Notas |
|---|---|---|
| `Intro` | ~195 (6.5 s) | colgado cabeza abajo de la punta de O1 tocando la flauta de costado, abre un ojo, sonríe, se ríe, sopla un dardo a los pies de Kaito, se suelta, da una vuelta y queda agachado en el posado |
| `PhaseBow` | 120 (4.0 s) | cae sentado riéndose, se saca una hoja de la barba, tres notas (las cañas se inclinan en la tercera, `Note` 70, 85, 100) |
| `PhaseForest` | 150 (5.0 s) | toca la frase entera, las cañas se enderezan (`Note` 60), la Madre crece (`Note` 90), garrocha a la Madre (`LeaveStalk` 120, `GrabStalk` 150) |
| `Defeat` | 165 (5.5 s) | de espaldas riéndose, se sienta con las piernas cruzadas, se seca una lágrima, reverencia con la flauta sobre las rodillas |
| `DefeatIdle` | 60, loop | meditando, respira |
| `Hit`, `HitHeavy` | 10, 16 | en el piso (los que pide `EnemyConfig`) |
| `Parried`, `ParriedPerfect` | 12, 18 | el retroceso del parry (0.40 / 0.60 s) |
| alias | | `Guard`, `Counter`, `Spotted` → `Idle`; `Exhausted` → `DazedSit`; `ExhaustedHit` → `DazedSitHit`; `ExhaustedRise` → `GetUp` (los nombres que `Enemy` toca por config) |

Son **~70 estados** (el Chikuō viejo tenía 115 clips): la prioridad para recortar está en la sección 22.

### 16.6 Dónde va la flauta-bastón y qué está trabado

| Clips | El bastón | Trabado (< 2 cm) |
|---|---|---|
| `PerchIdle`, `CatapultDraw`, `LeapCrouch`, `LeapGrab` | cruzado en los hombros detrás del cuello (pegado a `Spine2`), las muñecas colgando encima | los pies en `PerchNode`; la izquierda en `GripHigh` (salvo `CatapultDraw`: las dos manos en el bastón) |
| `PerchDart*`, `PerchVolley*`, `PerchWhistle`, `TalaShot`, `GroundDart`, `AnswerBlow` | de punta, como cerbatana: `Staff_Mouth` en la boca, las dos manos juntas cerca de la boquilla; los dardos salen de `Staff_Muzzle` | los pies en `PerchNode` (los de arriba) |
| `HangDrop`, `HangDart2`, `HangClimb` | de punta, cabeza abajo | las corvas en el culmo arriba del `PerchNode` |
| `Climb` | cruzado en la espalda | las manos en `ClimbGrip` y `GripHigh`, los pies contra el culmo |
| `Dive`, `StaffDrop`, `Thrust`, `StaffSpin2`, `NoteSmash`, `LowSweep` | en las manos (la derecha en `Staff_Grip`, la izquierda a 0.6 m) | los pies apoyados (sin patinar con `travel_m`) |
| `Vault`, `PolePlant`, `PoleClimb`, `PoleBalance`, `PoleDive` | clavado en el piso (`Staff` en el mundo, vertical) | las manos en el bastón; en `PoleBalance` un pie en la punta |
| `FluteRaise`, `FluteNote`, `Intro`, `PhaseBow`, `PhaseForest` | de costado, como flauta, los dedos en los agujeros | |
| `LeapAir`, `FlungAir`, huecos | en una mano, suelto (vuela con él) | |

### 16.7 Calidad (el lint de cada clip)

Lazos sin costura (< 1°); pies apoyados que no patinan (< 2 cm con el avance del código: `travel_m` del sidecar); manos y
pies en la caña trabados (< 2 cm) con el arco aplicado; nada del cuerpo ni del bastón atraviesa el piso, la caña o el
propio cuerpo; ningún hueso gira más de 45° por cuadro fuera de un corte; las poses de empalme a menos de 5° o tapadas por
el fundido del código; las poses de aviso legibles desde la cámara del juego (renderizarlas a 52° y 24 m: ~100 px para 1.5
m); anticipación, cambio de peso, superposición (la capa, la barba y los cascabeles llegan tarde), seguimiento y asentamiento.

---

## 17. El código (contrato para `c4/chikuo`)

### 17.1 Archivos

* `Enemies/Bosses/BambooMasterBoss.cs` reescrito (mismo nombre, `Boss, ICameraProfile, IBotHints`) en partes:
  `BambooMasterBoss.Canopy.cs` (posarse, saltar, cargas, latigazos, huecos, la raíz en la base), `.Ground.cs` (fase 2 y la
  coda), `.Tricks.cs` (pértiga, pregunta y respuesta, catapulta, tala, señuelos), `.Story.cs` (presentación, cambios de fase,
  derrota, gritos y pistas).
* `BambooMasterMoves.cs` (los `AttackDef` y el bloque de perillas), `BambooMasterTimings.cs` (generado),
  `BambooMasterLook.cs` (los brillos de los cascabeles, el señuelo), `BambooStalk.cs` (la caña: arco, anclas, estados),
  `BambooGrove.cs` (las cañas de la arena por fase, el estampado `StampTarget`, la mira de tinta, el filtro de destino),
  `BambooDart.cs` (el dardo con pool), `ChikuoDecoy.cs` (los señuelos).
* **Se borran** `BambooMasterBoss.Guard.cs`, `.Qi.cs` y `.Dash.cs` con sus `.meta`.
* `Tools/Dev/sim_bamboo_master.py`: cuando existan los clips, portarlo a esta pelea (o reemplazarlo por este modelo con los
  tiempos del sidecar) para la calibración.

### 17.2 Los AttackDef (en `BambooMasterMoves`)

`special` nuevos (los maneja el jefe en `TickSpecial`, `ComputeStrikeEta`, `HitAreaFor` y `StepHasTell`):

| Nombre | Estado | `kind` | Daño f1/f2/f3 | Golpe (s) | `special` | `specialParam` | Notas |
|---|---|---|---|---|---|---|---|
| Dardo | `PerchDart` | Projectile | 2.5 / 2.5 / 2.5 | soplo 0.45 + vuelo | `dart` | velocidad 16 / 16 / 18 | `StepHasTell` false: el anillo es el de Kaito (ETA) |
| Dos Dardos | `PerchDart2` | Projectile | 2.5 | 0.45, 0.80 | `dart` | | |
| Tres Notas | `PerchVolley` | Projectile | 2.5 | 0.55, 0.93, 1.31 | `dart` | | carga 0.10-1.41 |
| Cuatro Notas | `PerchVolley4` | Projectile | 2.5 | 0.45, 0.73, 1.01, 1.29 | `dart` | | carga 0.10-1.34 |
| Silbador | `PerchWhistle` | Unblockable | 5 / (no) / 5 | 0.90 (0.80) + vuelo a 22 m/s | `whistle` | ancho 1.0 | carril fijo 0.25 s antes de soplar; carga 0.10-1.00 |
| Colgado | `HangDrop`→`HangDart2` | Projectile | 2.5 | 0.65, 0.95 | `dart` | | carga 0.00-1.25 |
| Barrido de Caña | `StalkSweep` | Unblockable | 4 / (no) / 4 | 0.85 | `stalksweep` | radio 3.6 | disco en la base |
| Picada de la Grulla | `Dive` | Unblockable | 5 | 0.95 | `dive` | radio 1.6 | disco fijo a 0.50 donde está Kaito |
| Bastón que Cae | `StaffDrop` | Heavy | 5 / (no) / 4.5 | 0.85 | `staffdrop` | arco 90°, 2.4 m | cae a 1.6 m de Kaito; contra |
| Catapulta | `CatapultDraw`→`CatapultKick` | Unblockable | 6.5 | 1.50 | `catapult` | ancho 1.8 | carga 0.00-1.00; carril fijo a 0.75 |
| Tala | `TalaShot` | Unblockable | 5.5 | 1.10 | `tala` | ancho 1.6 | carril del largo de la caña, fijo a 0.65 |
| Bastonazo / Revancha | `Thrust` | Heavy | 3.5 / 3.5 / 4 | 0.55 / 0.60 | | 2.4 m | la Revancha `noRecoil` |
| Estocada / Giratoria / Patada / Nota | `Thrust`, `StaffSpin2`, `CraneKick`, `NoteSmash` | Heavy | 3.5 / 3.5 / 4 | 0.50 (encadenados 0.42), 0.55 + 0.42, 0.50, 0.65 | | 2.4 m | los del medio de una tanda `noRecoil` |
| Barrida del Bastón | `LowSweep` | Unblockable | 4.5 / 4.5 / 5 | 0.80 | `lowsweep` | radio 2.6 | dash perfecto: Bastón Clavado |
| Soplo | `GroundDart` | Projectile | 2.5 | 0.55 + vuelo | `dart` | | |
| Picada de la pértiga | `PoleDive` | Unblockable | 5 | 0.95 desde que sale | `dive` | radio 1.4 | |
| Nota aguda / grave | `AnswerBlow` / `AnswerStamp` | Projectile / Unblockable | 2.5 / 4 (4.5) | cada 0.44 | `answer` | brote radio 1.0 | |

`windup` mínimo de cada uno: el de `StepTimeline.MinWindup` (dorado encadenado 0.38, rojo 0.70) se cumple en toda la tabla.

`EnemyConfig` (`BambooMasterMoves.Config()`): `id` "ozeki", `displayName` "Chikuō", `maxHealth` 1900, `runSpeed` 5.5,
`walkSpeed` 1.6 (las de `Run` y `Walk`), `radius` 0.5, `height` 2.4, `maxImbalance` 99, `poiseHits` 99, `hyperArmor` true
(la armadura x0.35 de la carga la aplica el jefe), `finisherHealth` 0, `cinematicFinisher` false, `attackCooldown` 0.35-0.6
(la pausa entre tandas del piso), `parriedRecoil` 0.40, `patterns` = las tandas de la fase 2 (arriba decide el jefe, no
`Enemy`), nombres de estados los de 16.5.

### 17.3 Las perillas (un bloque al principio de `BambooMasterMoves`, con los números del modelo)

Los de `P` en `chikuo_v2_check.py`, con el mismo nombre: `Gates`, `TransitionHeal`, `Breath`, `ReactDist`, `ReactMix`,
`CampDist`, `CampTime`, `MaxOnStalk`, `DartSpeed`, `DartLead`, `LeapCrouch`, `LeapBase`, `LeapPerM`, `LeapK`, `LeapGrab`,
`LeapDest`, `CatchWindow`, `PingPong`, los huecos (`Revolcon`, `Estampado`, `Caida`…, cada uno vuelo / dura / tope /
multiplicador / caída), `StampRange`, `StampAngle`, `GetUp`, `Recoil`, `ArmorMul`, `NeutralMul`, `PertigaEvery`,
`PertigaLoaded`, `QaEvery`, `NoteGap`, `DamageScale` y la tabla de daño. Una sola fuente: el día que se calibre, se
cambian acá y en el modelo.

### 17.4 Hunks en archivos compartidos (chicos, sin reordenar)

| Archivo | Qué |
|---|---|
| `Input/AutoPilot.cs` | el bot: `BotTarget` en lugar de `nearest.transform.position` si el jefe es `IBotHints`; no cortar si `!BotMayCut` (salvo `greedy`); el gancho `BotCutGoal` (va, dash si está a más de 3.7 m, corta); los subcomandos de 13.2 dentro de `case "chikuo"` |
| `Story/StoryText.cs` | `ozeki_intro`, `bamboo_defeat` y `seal_bamboo` nuevos; `ChikuoLine` y `ChikuoRetry` con las frases de 19.3; las pistas `bamboo_whip`, `bamboo_stamp`, `bamboo_deny`, `bamboo_tickle`, `bamboo_staff`, `bamboo_flute`, `bamboo_crack` (se van `bamboo_stance` y `bamboo_guard`) |
| `Core/CharacterFactory.cs` | el subtítulo "El Ermitaño de las Cañas", `phaseThresholds = { 0.65f, 0.40f }`, `phaseAnim` → `PhaseBow` |
| `Resources/NindoContent.asset`, `Tools/Unity/generate_assets.py` | la fila de `bamboo_master` (el `height` nuevo, los materiales de brillo) y las claves de sonido de 18.1; correr solo esas funciones |
| `Enemies/EnemyArchetypes.cs` | nada (`Ozeki()` ya delega en `BambooMasterMoves.Config()`) |
| `Enemy.cs`, `Boss.cs`, `PlayerController*`, `CameraDirector` | nada |

---

## 18. Sonido

### 18.1 Claves (sintetizadas en `Tools/Audio/sfx_chikuo.py`, como `palm_deflect`)

| Clave | Qué es |
|---|---|
| `tell_chime_hi` (3 variantes), `tell_chime_lo` (2), `tell_chime_cascade`, `tell_chime_shimmer` (loop) | los cascabeles: síntesis modal de tubo de bambú (parciales ~1, 2.76, 5.40, caída rápida); `tell_` para que vayan en `Tier.Cue` (`AudioManager.TierOf`: sin el pitch de la cámara lenta, nunca pierden la voz) |
| `chime_jangle` | el sacudón de los cascabeles (mareado, cada corte en un hueco) |
| `flute_note_1..5` | la flauta (pentatónica del tema), las de la pregunta y la respuesta |
| `flute_phrase_intro`, `flute_phrase_bow`, `flute_phrase_forest` | las frases de la presentación y de los cambios |
| `dart_blow`, `dart_whistle`, `dart_thunk` | el soplido, el silbador, el dardo que se clava |
| `bamboo_thok` | corte a la caña sin campanas (hueco, opaco) |
| `bamboo_creak` | la caña que se carga (debajo del tintineo) |
| `bamboo_whip` | el latigazo: chasquido y "zuing" de caña tensa |
| `bamboo_slam` | el estampado contra la otra caña (grave) |
| `bamboo_crack`, `bamboo_break`, `bamboo_fall` | rajada, quebrada, talada |
| `stalk_bow`, `stalk_whoosh`, `stalk_grow` | las cañas que se inclinan, se enderezan, la Madre que nace |
| `leaves_burst` | señuelos, hojas del estampado |

### 18.2 Afinación

Medir la tónica de `boss_bamboo` (Wuxia, PeriTune; 136 BPM en las fases 1-2 y 144.1 en la 3, medio tono arriba) con un
cromagrama sobre la fuente que decodifica `build_boss_music.py` y afinar cascabeles y flauta a su pentatónica; en la fase 3,
medio tono arriba (x1.0595).

### 18.3 Lo que queda para después

El arranque de las acciones posado cuantizado al próximo medio tiempo de la música (`MusicDirector.NextBoundary`, ≤ 0.22 s
de espera) haría que los dardos caigan en el tiempo sin tocar los avisos. Es una mejora de sensación; no está en este
contrato (agrega espera y depende de la latencia de audio).

---

## 19. Historia y texto (voseo, sin separadores con guion, sin kanji)

### 19.1 Presentación

Kaito entra por el arco; se oye una flauta. Plano hacia arriba de O1: Chikuō **cuelga cabeza abajo de la punta tocando
la flauta** (la hoja original), abre un ojo, sonríe, se ríe y le sopla un dardo que se clava a los pies de Kaito. Diálogo
(`ozeki_intro`):

* Chikuō: "¡Je, je! Mirá quién vino a visitar al viejo de las cañas. ¿Te perdiste, muchacho?"
* Chikuō: "El sello que buscás me lo dejó Kokuyō. Fue mi alumno un invierno: quería ser duro como la piedra."
* Chikuō: "El bambú se dobla, por eso no se quiebra. ¿Lo querés? Bajame de acá. ¡Si podés!"
* Kaito: "Bajá vos, o te bajo yo."

Se suelta, da una vuelta y queda agachado en el posado; título en el tercio de abajo: **Chikuō** / *El Ermitaño de las
Cañas*. Empieza la pelea.

### 19.2 Derrota y sello

`bamboo_defeat` (sentado, después de la reverencia):

* Chikuō: "Je... Hacía cien inviernos que nadie me bajaba del bambú."
* Chikuō: "Lo alto se baja desde la raíz. No te lo olvides."
* Chikuō: "Llevate el sello. Y cuando enfrentes a Kokuyō, mirá su sombra: siempre llega antes que él."

`seal_bamboo` (Kaito al tomarlo): "Gracias, maestro." / "El Sello del Bambú. Lo que está alto se baja desde la raíz."

### 19.3 Gritos en pelea (`ChikuoLine`, una vez cada uno, no más de uno cada 12 s)

| Momento | Frase |
|---|---|
| primer corte sin campanas | "¡Je! ¡Cosquillas!" |
| primer latigazo | "¡Ay, mis huesos! ¿Quién te enseñó eso?" |
| primer estampado | "¡Uf! Esa caña estaba más dura que yo." |
| primera caída del cielo | "¡Eh! ¡Esa caña era mía!" |
| la monta (se va con el envión) | "¡Gracias por el empujón!" |
| un dardo le pega a Kaito (la risa) | "¡Ja, ja! ¡Te di en la nariz!" |
| la risa del maestro | "¿Y? ¿No me vas a bajar?" |
| cambio 1 | "¡Ja! Me bajaste del bambú. Bueno, bailemos en el piso." |
| primera Grulla en el Bastón | "¡Mirá, sin manos!" |
| desafinado | "¡Me hiciste desafinar!" |
| afinado | "¡Afinado! Me ganaste la canción." |
| cambio 2 | "¡Ahora que cante todo el bosque!" |
| primera caña rajada | "¡Mi bambú! Bueno... ahora es leña." |
| Tres Ermitaños | "¿Cuál de los tres soy? ¡Ni yo sé!" |
| señuelo cortado | "¡Ese no era yo!" |
| Última Canción | "Última canción, muchacho. Escuchala bien." |

### 19.4 Pistas (`StoryText.Hint`, dos renglones, las teclas entre llaves)

| Clave | Cuándo | Texto |
|---|---|---|
| `bamboo_whip` | la primera carga (y después de la risa del maestro) | "Cascabeles blancos: su caña está cargada\nCortala con {Attack} y lo despide" |
| `bamboo_stamp` | después del primer latigazo | "Lo despide para el lado del corte\nSi atrás hay otra caña, se estrella contra ella" |
| `bamboo_deny` | la primera vez que salta a una caña a 5 m o menos de Kaito | "Cuando salta, el ensō blanco marca su caña\nCortala antes de que la agarre" |
| `bamboo_tickle` | el segundo corte sin campanas | "Sin el brillo blanco, la caña te barre\nParale los dardos y entrá cuando cargue" |
| `bamboo_staff` | la primera Grulla en el Bastón | "Su bastón también es una caña\nCortalo con {Attack} mientras está arriba" |
| `bamboo_flute` | la primera Pregunta y Respuesta | "Lo que toca la flauta, lo repite\nAguda: desviá con {Parry}. Grave: salí con {Dash}" |
| `bamboo_crack` | la primera caña rajada | "La caña rajada se quiebra con el próximo latigazo\nY él la puede tirar encima tuyo" |

### 19.5 Reintento (`ChikuoRetry(intento, fase)`)

* Fase 3: "El bosque te estaba esperando. Seguimos donde quedamos."
* Fase 2: "Las cañas siguen inclinadas. Vení a bailar."
* Fase 1, por intento: "¡Volviste! Esta vez mirá mis cascabeles." · "Otra vez. Cuando brillan blancos, cortá." · "El bambú
  se dobla y vuelve. Vos también." · "No me mirés a mí: mirá la caña." · y después "El que cae siete veces se levanta ocho."

### 19.6 La personalidad

Juguetón (se ríe de todo, se ríe de sí mismo), excéntrico (vive en las cañas, habla con el bambú, se hace el que no sabe
cuál de los tres es), sabio (cada frase tiene una enseñanza sobre doblarse y volver, sobre la raíz). Nunca cruel: cuando le
pega a Kaito se ríe, cuando Kaito le pega se queja como un viejo y lo felicita. Kokuyō fue su alumno y no aprendió a
doblarse: es la semilla de la frase de la sombra.

---

## 20. Pruebas en Play para el lead (cuando esté hecho)

Respaldar `%USERPROFILE%\AppData\LocalLow\DefaultCompany\Nindo\nindo_save.json`; cargar `Docs/handoff/partidas/prueba_bambu.json`
(su `README.md`); Play; `Nindo.AutoPilot.Run("wait 0.5; tap Submit")`; teletransportar a Kaito a (122, 150) (el arco traba
el `goto`) y `Nindo.AutoPilot.Run("goto 124 156 20; talk 40; waitcontrol 30")`.

1. **Consola**: reimportado `BambooMaster.fbx`, sin errores ni clips que falten; Chikuō visible junto a su barra (la
   lección de la escala x100).
2. **Presentación**: colgado de O1 tocando, el dardo a los pies, el título en el tercio de abajo, arranca agachado en O1.
3. **El latigazo y el estampado**: `Nindo.AutoPilot.Run("chikuo cana O1")`, Kaito del lado del centro de O1 con
   `Nindo.Game.Player.Teleport(new UnityEngine.Vector3(120.1f, 2.0f, 162.0f), UnityEngine.Quaternion.LookRotation(new UnityEngine.Vector3(-1f, 0f, 0f)))`
   y `Nindo.AutoPilot.Run("chikuo mov notas; wait 0.5; tap Attack")`. Esperado: campanas blancas y tintineo, ensō blanco
   en la base, el corte suena en la caña, vuela contra O2 y se desliza; en el Editor.log `[Nindo] Chikuō: latigazo O1 ->
   estampado (O2)`. Lo mismo desde el lado de afuera de O1 (x 116.9): revolcón hacia el centro.
4. **Cosquillas**: con Chikuō en `chikuo mov dardo`, cortar la caña: suena hueca, manotea y barre (disco rojo de 3.6 m).
5. **Caída del cielo**: Kaito en la base de N1, `Nindo.AutoPilot.Run("chikuo salto N1; wait 0.45; tap Attack")`.
6. **Cámara**: Chikuō en N2 con Kaito en el centro y en E1: la cabeza bajo el 92 % de la pantalla, Kaito sobre el 8 %; Kaito
   al pie de O1 visto desde la cámara: la copa se funde, la de Chikuō no.
7. **Colores**: capturas de las siete cañas y de Chikuō posado de noche, a la distancia de la cámara: la cabeza blanca y los
   cascabeles se leen, él más oscuro que su caña, el ensō blanco sobre el piso del claro.
8. **Fases**: `chikuo fase 2` (las seis se inclinan sin pisar a Kaito; `chikuo mov pertiga`: cortar el bastón;
   `chikuo mov pregunta`: contestar limpio y cortarlo mientras toca) y `chikuo fase 3` (la Madre nace, `chikuo mov tala`
   con una caña rajada: `chikuo abrir revolcon` dos veces sobre la misma caña para rajarla).
9. **Animación**: `chikuo abrir estampado` y `chikuo abrir caida` para mirar los clips; posado con la caña en 30° (colgado):
   las manos y los pies no se despegan del culmo.
10. **Balance**: `bot on bueno` y `bot on promedio`, tres peleas cada uno, pegando las líneas `[Nindo] Chikuō vencido en` y
    la simulación de 12.2 en `boss_sims/calibration.py`. Objetivo: bueno 4.5-5 min sin morir, promedio 1-2 muertes en 7-9
    min. Restaurar la partida del usuario.

---

## 21. Lo débil, dicho de frente

1. **El factor real/simulado no se conoce** para una pelea así: el balance es ±20 %. La simulación es 2D y optimista para
   el bot (no rodea las cañas, el stick no es relativo a la cámara). Con F 1.0 el bueno ganaría en 3.8 min: hay que medir y
   mover las perillas de 12.3.
2. **El blanco es un color nuevo** de la gramática: hay que verlo contra el destello de acero del parry de Kaito (también
   claro) y con los ajustes de "Avisos de combate". Si se confunde, el ensō de la base puede ir en paja (el color del corte
   del bambú, como proponía Vertical) y las campanas en blanco.
3. **El arco de la caña con un cuerpo encima** es lo más difícil de animar: manos y pies trabados en un culmo que se dobla
   hasta 35°. Autorar en el espacio del `PerchNode` lo vuelve un problema de siempre, pero el lint tiene que medir con el arco
   del código.
4. **La raíz en la base** resuelve el golpe, el fijado y el bot, pero todo lo que usa `boss.transform.position` como "dónde
   está" apunta al piso: la voz y los sonidos (que salgan del modelo), las flechas de `ThreatIndicators`, la silueta del
   oclusor, el foco de la cámara (lo corrige el sesgo).
5. **Muy saltarín**: ~20 saltos y ~10 ping-pong por pelea. Es lo que pidió el usuario, pero puede marear: los vuelos duran
   0.5 s o más, la cámara sigue a la raíz (que viaja por el piso debajo de él, sin la altura del salto, amortiguada) y el
   filtro de destino lo mantiene en cuadro. Mirarlo en Play.
6. **Un latigazo cada 8.5-9.5 s** es mucho del mismo verbo. Lo varían lo que carga (la ráfaga, el silbador, colgado, la risa,
   la catapulta, el agarre, la trepada), el resultado (revolcón, estampado, caída del cielo) y las bajadas al piso; si en
   Play cansa, subir el tope de cortes y bajar la frecuencia de las cargas (los pesos de 7.1) antes que agregar cosas.
7. **La fase 2 es la menos nueva** (pelea de piso, aunque sin guardia, con la pértiga y la flauta): dura 45 s a propósito.
   Si se siente como el Chikuō viejo, acortarla (piso de la fase 2 al 45 %) antes que alargarla.
8. **Pregunta y Respuesta casi nunca se contesta limpia contra el bot** (siempre lo interrumpe: está a 3 m). El camino de
   "afinado" es para el que elige escuchar; hay que verlo con una persona.
9. **El bot no apunta el estampado** (6 de 30 latigazos por azar); una persona que lo entiende saca más. La simulación no
   mide ese techo.
10. **Alcance grande**: ~70 estados, cinco sistemas nuevos (cañas, dardos, señuelos, la mira, la grieta). La sección 22 dice
    qué recortar.
11. **Kokuyō**: con el objetivo del líder Chikuō dura igual o un poco más que lo que C3 predice para Kokuyō (4.8 contra 4.35
    min el bueno); lo que lo mantiene abajo es que pega menos y mata menos (1.3 contra 1.4 muertes del promedio).

## 22. Si no alcanza el tiempo, qué se hace primero

1. **Imprescindible**: las seis cañas con el arco, la raíz en la base, posarse y saltar, Dardo, Dos Dardos, Tres / Cuatro
   Notas, Colgado, Risa, el latigazo (revolcón y estampado) con el ensō y las campanas, Cosquillas, Picada, Bastón que Cae,
   la vuelta arriba y la garrocha, la fase 2 con las tandas y la Grulla en el Bastón, los cambios de fase, el bot y los
   comandos, el texto y las pistas.
2. **Muy importante**: la caída del cielo, el Silbador, la Caña Madre, la rajadura y la quebradura, la Catapulta, Pregunta
   y Respuesta, la mira de tinta, la inclinación de la fase 2.
3. **Recortable, en este orden**: Tres Ermitaños, la Tala, los dardos que quedan clavados, `PerchVolley4` (la fase 3 usa
   Tres Notas a x1.12), la inclinación (las cañas quedan paradas y en la fase 2 tiemblan con la música), la Madre (la fase 3
   con las seis).

## 23. Lo que quedó en el código (rama `c4/chikuo`, paso de la pelea)

Todo lo de las secciones 22.1 y 22.2 está; de la 22.3 quedó afuera solo **Tres Ermitaños** (los señuelos de hojas: el primero
de la lista de recortes; la simulación ya no los tiene). Diferencias con este documento, todas a propósito:

* **Archivos**: `BambooMasterBoss.cs` (núcleo: el cuerpo, el reloj de los clips, los golpes de Kaito, la maquinaria de los
  avisos, el bot), `.Canopy.cs` (arriba: decidir, dardos, colgado, risa, barrido, picada, bastón que cae, saltos, vuelta
  arriba, el latigazo y los huecos), `.Tricks.cs` (silbador, catapulta, tala), `.Ground.cs` (el piso, la Grulla en el
  Bastón, Pregunta y Respuesta), `.Story.cs`; `BambooStalk.cs` (con `InkEnso`, el ensō blanco), `BambooGrove.cs`,
  `BambooDart.cs`. Los tiempos los da `ChikuoTimings.cs` (no `BambooMasterTimings.cs`, borrado con la pelea vieja).
* **Los golpes con anillo** desde la caña y la pértiga son pasos "held" de Enemy: el jefe toca el clip a su tiempo natural y
  le da a Enemy la ETA; Enemy dibuja el anillo, el "¡ya!", el destello y la zona. Las tandas del piso son patrones comunes.
* **El ensō blanco** tiene 1.6 m de radio (no 1.2): el anillo de los golpes del jefe va a 1.2 m alrededor de la raíz, que
  posado está en esa misma base, y el silbador es rojo y cargado a la vez. También hay uno en el bastón de la Grulla.
* **Apuntar la flauta**: en vez de girar el pecho (la flauta es un hueso de `Root` que las manos agarran por IK: girar el
  pecho despegaba las manos) se inclina el cuerpo entero sobre los pies, hasta 20° adelante y 12° atrás, solo soplando.
* **El bastonazo de la vuelta** (después de aterrizar) desviado abre la Contra, como dice la tabla 5.2 (el modelo de Python
  no la abría); la Revancha de la fase 3 no.
* **El ping-pong** de la fase 3 encadena el salto con su agachado (0.15 s).
* **La barra del jefe** no muestra rombos de postura (no tiene postura) y las marcas de la UI van arriba de su cabeza.
* **Sonido**: `Tools/Audio/sfx_chikuo.py` sintetiza la sección 18 entera; el cromagrama del tema dio F# menor pentatónica
  (la fase 3, G): los cascabeles y la flauta tienen su versión `_p3`. El tintineo blanco es de una sola vez (1.3 s), no un
  loop.
* **Balance**: `chikuo_v2_check.py` toma los tiempos del sidecar (lo que toca el código). 400 peleas por nivel con F 1.3:
  el bueno 4.9 min sin morir, el promedio 7.4 min con 1.26 muertes (fases 112 / 46 / 132 s; un latigazo cada 8.4 / 15 /
  9.7 s). Con el 1.42 del Chikuō viejo: 5.3 y 8.9 min con 1.81. La regla para calibrar de 12.3 sigue valiendo.

### 23.1 Después de la revisión de C4 (cuatro revisores; detalle en `Docs/handoff/reportes/c4_reports.md`)

* **Tres Ermitaños queda recortado del todo**: se borraron el clip `DecoySpin`, `Chikuo_Decoy.mat` y los
  `extra_materials` del sidecar (un especial que no está no deja assets en el build). Para darle forma a la fase 3 sin él:
  **la firma** cada 9-12 s (la primera a los 5-7 s): la tala si hay una caña rajada, la catapulta con Kaito a 4 m o más,
  si no la ráfaga de cuatro. La catapulta por pesos pasa a 1.0, cada 6 s, desde 4 m. La Última Canción arranca al 20 %.
* **La vuelta de un hueco varía** (antes siempre la garrocha invulnerable de 1.3 s): el kip-up a 0.25 s, y con Kaito a
  6 m o más un salto común (se le puede cortar el agachado y atajar el salto); si no, 45 % la garrocha, 30 % el agachado
  cortable, y con Kaito a 4 m o menos el resto son dos bastonazos (el segundo desviado abre la Contra) y trepa sin carga.
  El estampado se abre a ±26° (antes 20°).
* **Colgado con Kaito al pie**: la carga prende 0.35 s antes del primer dardo (antes desde el principio: un latigazo gratis
  antes de que existiera un dardo). Lejos (la regla 8), cargado de punta a punta como antes.
* **La caída del cielo** tiene 0.60 s de ventana en la fase 3 (0.45 en la 1) y el viejo mira la caña de destino 0.25 s
  antes de agacharse: los saltos de 5-9 m se atajan de reacción con el dash desde 4.5-8 m (`--fair`).
* **El Paso del Ermitaño**: una voltereta cada 1.5 s como mucho (dash-corte-voltereta lo trababa); dentro de esa ventana
  aguanta el corte (x0.6) y contesta con una tanda ya. La voltereta es invulnerable entera.
* **El revolcón** queda abierto 2.2 s con tope de 5 cortes (fase 3: 2.0 s). El daño a Kaito va x0.9.
* **Balance** (400 peleas, seed 7): con el 1.41 del Chikuō viejo, el bueno 4.9 min (p10 4.3, p90 5.5) sin morir y el
  promedio 7.3 min con 1.20 muertes (el experto 4.5 min); con F 1.3, 4.6 y 6.7 min con 0.94. Sigue siendo más largo que
  lo que se espera de Kokuyō (~4.4 min para el bueno, `calibration.py`): el lead decide si el objetivo de 4.5-5 min manda.
