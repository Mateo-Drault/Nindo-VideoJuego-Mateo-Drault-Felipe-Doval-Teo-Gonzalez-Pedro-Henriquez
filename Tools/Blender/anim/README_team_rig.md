# Rig de los personajes del equipo (ninja, sumo, Gorō, abuelo y el ninja del secuestro)

Cómo se autora un clip nuevo sobre los modelos del equipo y qué garantiza el pipeline. Código:
`team_rig.py` (marco de autoría, solver, horneado), `team_limbs.py` (brazos y muñecas), `team_clips_<personaje>.py`
(los clips), `build_team_anims.py` (chequeos, FBX de animación y sidecar), `team_review.py` (hojas de revisión).

## Comandos

```
blender -b --factory-startup --python Tools/Blender/anim/build_team_anims.py -- <ninja|sumo|goro|grandpa> [--export] [--only A,B] [--renders DIR]
```

* sin `--export` solo resuelve y chequea (sale con código 1 si algo falla); con `--export` escribe
  `Nindo/Assets/Nindo/Art/Characters/TeamAnims/<Personaje>Anims.fbx` y su `.json` (cuadros, timing, lint).
* `--only` itera sobre algunos clips (no exporta). `--renders` hace una hoja por clip con la cámara del juego.
* `--export --fbx RUTA` escribe el FBX y su `.json` en otra parte (el scratch), también con `--only`: para medir una
  variante (píxeles de la hoja, giros) sin tocar el de `TeamAnims`.
* Después, en Unity: `generate_assets.py` (solo las funciones de los controllers/metas que tocás) liga cada clip del
  sidecar al estado del mismo nombre del controller (`team_states`) y escribe el importador (`team_anim_metas`:
  Generic, sin compresión, `preserveHierarchy: 1`).
* Los modelos (`export_<personaje>.py`) solo se re-exportan si cambia la malla, los pesos o el esqueleto.

## Esqueleto de juego (fase C)

Las manos y los pies del sumo, Gorō, el abuelo y el ninja del secuestro colgaban de huesos de IK en la raíz
(`TargetBrazo`, `TargetPie`, `AntebrazoTarget`, `TibiaTarget`): Unity mezcla cada hueso por separado y en cada cruce de
clips (y en todo el blend de locomoción) la muñeca y el tobillo se despegaban. Ahora (`charlib.game_limbs`, llamado
desde cada `export_<personaje>.py`) son hijos del antebrazo y la tibia, con los mismos nombres, cabezas, colas, rolls y
pose de bind; el martillo de Gorō (`BaseM`) es hijo de `Mano.R`. Los controles siguen en el FBX (sin pesos, quietos)
porque los kits de zona traen el esqueleto completo y `CharacterKits.Attach` los busca por nombre.

| personaje | mano (der / izq) | pie | cambió de padre |
|---|---|---|---|
| ninja | `Mano.L` / `Mano.R` | `Pie.*` | nada (ya era FK) |
| sumo | `Palma.L` / `Palma.R` | `pie.*` | `Palma.*` -> `Antebrazo.*`, `pie.*` -> `Tibia.*` (pesos de `TargetBrazo/TargetPie` a la mano/el pie, de `PolePie` a la tibia) |
| Gorō | `Mano.R` / `Mano.L` | `Pie.*` | `Mano.*` -> `Antebrazo.*`, `Pie.*` -> `Tibia.*`, `BaseM` -> `Mano.R` |
| abuelo | `Mano.L` / `Mano.R` | `Pie.*` | `Mano.*` -> `Antebrazo.*`, `Pie.*` -> `Tibia.*` |
| ninja del secuestro | `Mano.L.001` / `Mano.R.001` | `Pie.*.001` | igual que el abuelo |

Ojo con los lados: en el ninja, el sumo y el abuelo el `.L` del FBX es la mano DERECHA del personaje (el mapeo por
geometría vive en `CHARS[...]["right_tag"]`). En los clips siempre se escribe `_r` / `_l` del personaje.

El FBX de animación lleva solo la armadura, con los mismos padres que el modelo; `verify_fbx` falla si un nodo cuelga
de otro padre, si una ruta no empieza en `Armature/` o si el nodo `Armature` se anima (el bug de los enemigos
invisibles: un FBX con un solo nodo raíz que Unity aplana).

`SumoPoser` (Unity) sirve para los dos esqueletos: con FK la mano sigue al antebrazo y el pie conserva el giro que le
dio el clip.

## Marco de autoría

Metros del juego. Origen en el piso bajo el transform del juego, frente = -Y, izquierda del personaje = +X, arriba = +Z.
Giros en grados XYZ de ese marco: x+ = inclinarse hacia adelante, y+ = hacia su izquierda, z+ = girar hacia su
izquierda. `TeamChar` convierte al eje y las unidades de cada FBX; los clips no se enteran.

Medidas de reposo en `ch.land` (`pelvis`, `head`, `shoulder_k`, `elbow_k`, `wrist_k`, `hip_k`, `knee_k`, `ankle_k`,
`sole_z`), largos en `ch.leg_len` / `ch.arm_len`, arma en `ch.weapon_info` (`build_team_anims` las imprime en la línea
`PERSONAJE`).

## Un clip

```python
import nindo_anim as NA, team_rig as T
Key = NA.Key
POSE = dict(hips=(0, 0.02, -0.05), hips_rot=(8, 0, 0), spine=(10, 0, 0), head=(-8, 0, 0),
            hand_r=(-0.30, -0.20, 0.90), hand_r_dir=(0, -1, -0.3), hand_r_palm=(1, 0, 0), elbow_r=(-1, 0.4, -0.3),
            fist_r=1.0, knee_r=(-0.2, -1, 0))
clip = T.TeamClip("Nombre", n, [Key(0, A), Key(12, B, "inout"), Key(n, A, "sine")], loop=False,
                  timing=dict(kind="heavy", apex=14, contact=18, active=[18, 22], hold=[8, 14], lunge=0.6, windup=0.65),
                  travel=T.lunge_travel(n, 14, 18, 0.6, windup_min=0.65)[0],
                  feet={"r": [T.FootKey(0, x, y), T.FootKey(10, x, y + 0.3, pitch=20.0)], "l": [...]})
```

`team_clips_<personaje>.clips(ch)` devuelve la lista; cada clip con el nombre del estado del Animator que reemplaza.

### Canales (claves de cada pose; lo que falta en una clave sale de la vecina)

Ojo con "sale de la vecina": un canal que solo pide una clave vale eso en todo el tramo que llega a ella. Una mano que
suelta (`drop_r`) o que afloja (`grip_r`) desde una clave tiene que pedir el valor de antes (0 o 1) también en la clave
anterior; si no, suelta de golpe desde el principio del tramo. Los dedos y la palma de cada mano se interpolan como un
marco (slerp del giro, `TeamClip.FRAME_PAIRS`); la hoja y el filo, cada uno por su arco (es el tajo autorado).

| canal | qué es |
|---|---|
| `hips`, `hips_rot` | cadera: desplazamiento (m) y giro (°) respecto del reposo |
| `spine`, `chest`, `head`, `clav_r`/`clav_l` | giros (°) de columna, pecho, cabeza y clavículas; `breath` 0..1 respira |
| `hand_k` | dónde va la muñeca (m). Sin él, la muñeca de reposo |
| `hand_k_dir`, `hand_k_palm` | hacia dónde apuntan los dedos y hacia dónde mira la palma. Con los dos, ese marco; solo `dir`, el giro mínimo desde la mano neutra; ninguno, la mano neutra (sigue al antebrazo, muñeca derecha). Una palma casi paralela a los dedos se mezcla sola con el giro mínimo |
| `elbow_k` | hacia dónde va el codo (polo; por omisión atrás, afuera y abajo). `team_limbs` lo puede girar alrededor del eje hombro-muñeca para que la muñeca entre (hasta 120°, con costo) |
| `fist_k` | 0 mano abierta, 1 puño cerrado (falanges a 62/78°, pulgar 26/34°) |
| `knee_k` | hacia dónde va la rodilla (por omisión adelante) |
| `foot_k`, `foot_k_rot` | tobillo y giro del pie; mejor con `feet=` (`FootKey`, `gait2`): apoyos en el MUNDO, ruedan sobre punta o talón con el punto de apoyo clavado |
| `auto_drop` | 1 (por omisión): la cadera baja sola lo que haga falta para que los pies lleguen (el chequeo avisa desde 4 cm) |
| `travel` | lo que avanzó el transform del juego (lo arman `lunge_travel` / `knock_travel` desde `TeamClip(travel=...)`) |
| `look` | 0..1: cuadros que se leen del golpe; ahí correr el arma cuesta 4 veces más. Por omisión, de `hold[0]` a `contact + 1` |
| `extra` | `{hueso: giro}` suelto encima de todo (orejas, cintas) |

Katana (ninja, mano `weapon_info["hand"]`): `grip` (dónde va el puño), `blade` (hacia dónde va la hoja), `edge`
(hacia dónde mira el filo), `grip_l` 0..1 (la otra mano va al mango, espejo del agarre, más cerca del pomo).
La hoja va donde la pide el clip: el hueso `Katana` se anima aparte y el puño rueda sobre el mango. El mango cruza la
palma en diagonal (`KATANA_DIAG0` = -40°, la izquierda +40°, ±`KATANA_DIAG`): con esa diagonal la guardia queda con la
muñeca a 16° de recta y el antebrazo neutro. Para que la hoja se lea desde la cámara del juego, en los loops y en los
avisos el filo va inclinado (`LOOP_EDGE` en team_clips_ninja: 60° de la vertical, la cara clara hacia arriba); un filo
abajo derecho deja solo el lomo a la vista. En los golpes, el filo va adelante del tajo pero con la hoja acostada
(Attack2 sube con el filo adelante y la punta hacia Kaito, todo pronado; Attack3 baja en diagonal con el filo 35° a la
izquierda; la estocada es de plano, filo afuera; el desvío barre con el filo adelante, como la guardia). Para elegir un
filo nuevo conviene recorrer el giro del filo alrededor de la hoja (un cuadro suelto, `limbs.begin("free")`) y mirar
costo, pronación, columpio y cuánto mira la cara a la cámara; en un golpe, que el antebrazo haga todo el tajo en la misma
rama (pronado o supinado): cambiar de rama en dos cuadros es media vuelta del antebrazo.

Martillo (Gorō): `grip` (la derecha), `haft` (eje del mango hacia la cabeza), `face` (hacia dónde mira la cara de
golpe), `grip_l` 0..1 y `slide_l`/`slide_r` (corren las manos por el mango, m), `grip_r` < 1 (la derecha afloja para
cambiar de agarre: se endereza sin llevarse el martillo; el límite de la muñeca pasa de `CLUB_BEND` a 0.99 en
proporción), `grip_flip` / `grip_flip_l` (meñique hacia la cabeza, como un bastón), `drop_r` 0..1 (la derecha SUELTA el
mango y va a `hand_r`/`_dir`/`_palm` como mano libre; el martillo queda donde lo ponen `grip`/`haft`/`face`).

Tomas del equipo: `T.TakeClip(ch, "Intro", "Firstinteraction", 0, 77)` re-resuelve una acción del FBX del modelo (el
cuerpo, los pies y el arma de la toma; los brazos otra vez por team_limbs, `TeamSolver.solve_take`). Es lo que usa la
presentación de Gorō; sirve para cualquier toma que el juego siga usando tal cual. Lo que en la toma atravesaba el piso
se corrige (`take_floor_fix`): el pie gira sobre el tobillo hasta apoyar la planta (en la presentación, el pie derecho en
punta de pie estaba 8.2 cm abajo; ahora 16° menos de punta) y el martillo gira alrededor del puño de la derecha hasta
quedar a 0.5 cm del piso, con una rampa de 4 cuadros (en los dos golpes al piso se hundía 22.4 cm; ahora 5-7° más
arriba). La mano del martillo gira con él y la otra vuelve a agarrarlo. Las tomas pasan los mismos chequeos de piso que
los clips nuevos.

### Lo que hace el solver con las manos (team_limbs.ArmSolver)

* Mide la muñeca contra el reposo del modelo (neutra): flexión 75°, extensión 65°, desvío radial 25°, cubital 38°;
  `exceso` 1 = en el borde de esa elipse.
* El giro de la mano sobre el eje del brazo lo toma el antebrazo (85 %, pronación -85° a supinación 90°, 0 = pulgar
  arriba); en la muñeca quedan hasta 30°.
* Elige el codo (giro alrededor del eje hombro-muñeca), el giro del puño sobre el mango y su diagonal con la muñeca más
  cómoda, sin meter el codo en el tronco. Hornea en dos pasadas: junta las soluciones de cada cuadro y elige el camino
  más barato del clip entero (Viterbi; en un loop cierra sobre sí mismo), repartiendo en rampas de 2 a 6 cuadros los
  cambios de solución que no se pueden evitar.
* La mano en un mango prefiere el antebrazo cerca de neutro (`HOLD_PRON_C` -15°, `HOLD_PRON_W`) y el codo que gira
  prefiere bajar a subir (`ELBOW_UP_W`).
* La mano LIBRE pedida fuera de lo posible se endereza hasta el 85 % del borde (los dedos apuntan un poco distinto de
  lo pedido) y su brazo no se estira más del 95 % (`FREE_REACH`: con el codo recto el giro del antebrazo no está
  definido). La del arma se endereza desde 3/4 del borde (`KATANA_BEND` 0.75, `CLUB_BEND` 0.8: 56° de flexión como
  mucho) llevándose el arma, y eso cuesta por centímetro que se corre la punta o la cabeza (`hold.reach`). La que agarra
  un mango sin arma propia nunca se endereza: si no entra, falla.
* Cruces del Animator: `team_clips_<personaje>.BLENDS = [(clip, cuadro, otro, cuadro)]` (-1 = el último). El clip que
  se hornea después ancla ahí sus brazos a la rama del otro (`ANCHOR_W`): sin eso Guard y Counter quedaban en ramas
  opuestas de la pronación y la mezcla de Unity daba un sacacorchos de 138°. Un clip nuevo que arranca o termina en la
  guardia va en BLENDS.
* Pedir la mano: la palma (`hand_k_palm`) y los dedos (`hand_k_dir`) en el marco de autoría, como se ven en el
  personaje. Si un pedido no entra, el log dice `muñeca ... libre en su límite (xN)` con el exceso ANTES de enderezar.

### Chequeos (build_team_anims.lint / wrist_checks / mesh_pass)

Manos y pies que llegan; pies apoyados quietos (< 2 cm, `slide_ok` en el timing para un patinazo a propósito);
patinar tocando el piso medido en la malla deformada; cuerpo y arma que no se meten en el piso; costura de loop
(< 1°, el último cuadro resuelto contra el primero); contacto y apex contra `EnemyArchetypes.cs` (Hit(...)); la punta
quieta en la pausa del aviso (< 2.5 m/s) y más rápida en el golpe; embestida que arranca en la suelta; empalmes de
`chain` (Parried -> Attack1...); el arma en el blend de locomoción. Muñecas: sin matrices espejadas, exceso <= 1 (en el
mango: aviso hasta 1.35), giro en la muñeca, pronación dentro de lo humano, el arma corrida <= 12° en el aviso y el
golpe, y saltos del codo / antebrazo de un cuadro al otro (<= 35° más de lo que giró la mano pedida; aviso hasta 55°).
Además: la mano en el mango sin quebrarse (columpio <= 55°, falla desde 70°); el antebrazo en su tope más del 25 % de
los cuadros (aviso); la mano libre pedida con un giro que no entra (aviso, con el cuadro); tics en lo EXPORTADO (el giro
local del antebrazo o la mano > 45° en un cuadro con la mano viajando < 20 cm respecto de su hombro y 20° más que el cuadro vecino más rápido:
falla; lo mismo en el brazo, aviso; quedan libres la mano del arma en el golpe y los 2 primeros cuadros, que Unity cruza
en 0.08 s); el puño alrededor del mango (la palma a la distancia del agarre ideal ± 2 cm, `grip_gap_cm`); los cruces de
`BLENDS` (el antebrazo gira <= 30° más que la mano pedida, y aparte el giro crudo, aviso arriba de 45°: los golpes del
ninja salvo el Attack1 arrancan con el filo de los loops, `edge_start`, pero las vueltas a Idle todavía ruedan ~57°); el arma no se mete en el piso más de 1 cm fuera del golpe;
la cara de la katana hacia la cámara del juego (media de |normal . cámara| desde 6 lados a 52°, >= 0.5, aviso) en el
inicio del aviso, el apex y el golpe, en los loops y en los cuadros `timing["read"]` de un clip sin golpe (`blade_face`
en el sidecar). Ese número no ve lo que tapa el cuerpo: para comparar de verdad, contar píxeles con máscaras planas
(Metal / Lomo / Glint) desde la cámara del juego, como hizo la revisión.

## Dos personajes en el mismo FBX (el abuelo y el ninja del secuestro)

```python
ch = T.TeamChar("grandpa", T.CHARS["grandpa"])
kid = ch.partner                     # TeamChar del esqueleto '.001' (partner_spec): mismas unidades, su propio marco
clip = T.TeamClip("Kidnap", n, keys_del_abuelo, ...)
clip.partner = T.TeamClip("Kidnap/ninja", n, keys_del_ninja, feet={...})   # mismo largo
```

* El ninja se autora en SU marco: origen en el piso bajo su cadera de reposo (1.3 m adelante del abuelo) y frente hacia
  donde mira en el reposo (hacia el abuelo). En el marco del abuelo, un punto (x, y) del ninja es (-x, -1.3 - y).
* `bake` resuelve los dos en la misma pose (el abuelo primero; antes de resolver al ninja se le borra la pose fija que
  dejó el primero, `drop_kid`: si no, la IK de sus brazos y piernas arrancaba de los hombros y las caderas de `kid_pose`
  aunque su cadera se moviera); `build_team_anims` corre los mismos chequeos sobre el
  ninja (`reports[clip]["partner"]`) y las hojas de `--renders` lo muestran. `travel` es del transform del NPC: en el
  marco del ninja el piso corre para el otro lado (`ch.partner.travel_axis`), los pies de los dos quedan clavados.
* Sin `clip.partner`, el ninja queda en la pose fija del cuadro 2 de la toma `Kidnap` del equipo (`kid_pose`, con las
  muñecas enderezadas). Está PARADO, con las manos a los costados (no agazapado).
* `Kidnap` y `Dragged` (team_clips_grandpa) ya reemplazan la toma del equipo. Los contactos entre los dos (las manos de
  cada uno sobre la muñeca del otro) salen de resolver cuadros sueltos de los dos esqueletos (`Probe`/`Duo.resolve`:
  el puño medido contra el antebrazo del otro y corregido); `grandpa_fbx_check.py` los vuelve a medir en el FBX
  exportado, junto con los empalmes en seco del NPC. El NPC 'kidnap' espera en `KidnapWait` (`NPC.AwaitKidnap`, que
  empalma con `Kidnap` f0), no en Idle: la pose fija no es la de arranque (en el fundido de 0.1 s la mano del ninja
  saltaba 21 cm).
* La clavícula de estos rigs (20 cm en el abuelo) gira hacia la mano pedida y corre el hombro: una mano puesta "a tal
  distancia del hombro" hay que recolocarla desde el hombro ya resuelto, varias pasadas (`Duo.resolve`). Y con los
  brazos tirantes, todo lo que inclina a uno corre al otro: las piernas del ninja (0.33 m) no cubren más de ~1 m/s con
  los pies clavados, así que los compases que cambian la distancia entre hombros tienen que ser lentos o hacerse con
  los brazos (`drag_taut`).
* `grandpa_shots.py` hace las hojas con las cámaras de las escenas (prólogo, ojos de Kaito, bosque, final) y mide
  cuánto se acercan los cuerpos y si el abuelo entra en el poste o su zócalo.
* Las mallas: `Cuerpo` (abuelo) y `Cube` (ninja); el NPC `grandpa` oculta la del ninja.

## Lo que hay que mirar al autorar

* Las poses de aviso desde la cámara del juego (pitch 52°, distancia 24, FOV 30; un personaje de 1.5 m mide ~100 px).
* Un `WARN ... muñeca` o `codo y antebrazo sin saltos` dice el cuadro: casi siempre es un pedido de mano que la muñeca
  no puede cumplir (la palma al revés, la hoja paralela al antebrazo). Mover `grip`/`hand_k` o la palma unos
  centímetros suele resolverlo sin cambiar la silueta.
* Un tic que el chequeo marca casi siempre es de autoría: un polo de codo casi paralelo al brazo (el codo cambia de
  lado cuando la mano lo cruza), una mano libre pedida más allá del alcance (el brazo recto y, al doblarse, el antebrazo
  gira de golpe) o una palma que en la clave siguiente queda del otro lado (media vuelta en pocos cuadros). La mano libre
  que sigue al hombro que gira (en vez de quedarse quieta en el espacio) casi siempre lo arregla.
* Lo que el log no ve: el pulgar del puño sobre el mango no se cierra sobre él (la malla low poly lo deja arriba) y la
  diagonal del puño elegida por el solver puede leerse como "mano de costado" en primeros planos.
