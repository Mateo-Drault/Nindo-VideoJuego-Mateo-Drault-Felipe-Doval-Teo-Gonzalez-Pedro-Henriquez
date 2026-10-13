# Partidas de prueba

Copias de `nindo_save.json` para arrancar en un punto exacto del juego. Las de cada jefe son lo que tendría guardado un
jugador real parado en el santuario de la entrada, siguiendo el camino que marca el objetivo: prólogo, muralla, jardín,
sumo, puerta del dojo, Gorō, Mizuchi, Chikuō y Kokuyō. Cada sello queda puesto apenas se gana, porque el portal de cada
jefe lleva a `cp_dojo_gate`.

## Cómo cargar una

1. **Fuera del Play** (al salir del Play el juego guarda encima), con RunCommand. Respalda la partida del usuario una sola
   vez y copia la de prueba:

   ```csharp
   var dir = System.IO.Path.GetFullPath(System.IO.Path.Combine(UnityEngine.Application.dataPath, "../../Docs/handoff/partidas"));
   var dst = System.IO.Path.Combine(UnityEngine.Application.persistentDataPath, "nindo_save.json");
   if (System.IO.File.Exists(dst) && !System.IO.File.Exists(dst + ".respaldo")) System.IO.File.Copy(dst, dst + ".respaldo");
   System.IO.File.Copy(System.IO.Path.Combine(dir, "prueba_goro.json"), dst, true);
   ```

   Es lo mismo que copiarla a mano a `%USERPROFILE%\AppData\LocalLow\DefaultCompany\Nindo\nindo_save.json`.
2. En el `GameBootstrap` de `Nindo.unity`, `debugStartCheckpoint` tiene que estar vacío y `debugSkipIntro` y
   `debugUnlockAll` apagados: si no, pisan el santuario y los desbloqueos de la partida.
3. Play en `Menu.unity` y `Nindo.AutoPilot.Run("wait 0.5; tap Submit")` (Continuar). Play directo en `Nindo.unity` también
   continúa la partida.
4. Al terminar, salir del Play y devolver la del usuario:

   ```csharp
   var dst = System.IO.Path.Combine(UnityEngine.Application.persistentDataPath, "nindo_save.json");
   System.IO.File.Copy(dst + ".respaldo", dst, true); System.IO.File.Delete(dst + ".respaldo");
   ```

Para teletransportar a Kaito (en Play, con X, Y, Z del punto; Y es la altura del piso de la arena):

```csharp
if (UnityEngine.AI.NavMesh.SamplePosition(new UnityEngine.Vector3(X, Y, Z), out var h, 4f, UnityEngine.AI.NavMesh.AllAreas))
    Nindo.Game.Player.Teleport(h.position + UnityEngine.Vector3.up * 0.1f, Nindo.Game.Player.transform.rotation);
```

Los números de AutoPilot desde RunCommand van con `CultureInfo.InvariantCulture` (con coma decimal, `goto` manda a
Kaito a cualquier lado).

## Las partidas

| Archivo | Santuario | Para qué |
|---|---|---|
| `usuario_actual_cp_home.json` | `cp_home` | La última partida real del usuario (nueva, en la casa). No es de prueba: es su copia. |
| `prueba_juego_completo_cp_lake_falls.json` | `cp_lake_falls` | La del equipo con todo hecho. Tiene `final_boss_done` sin `ending`: al cargar corre `ResumeEnding`. |
| `prueba_tarde_cp_lake_falls.json` | `cp_lake_falls` | Fin del juego antes de Kokuyō: los tres guardianes vencidos, los tres sellos en la mano y ninguno puesto. |
| `prueba_goro.json` | `cp_mountain_top` | Antes de Gorō, el primer guardián. |
| `prueba_mizuchi.json` | `cp_lake_falls` | Antes de Mizuchi, con Gorō vencido y su sello puesto. |
| `prueba_bambu.json` | `cp_bamboo_gate` | Antes de Chikuō, con Gorō y Mizuchi vencidos y sus sellos puestos. |
| `prueba_kokuyo.json` | `cp_dojo` | Antes de Kokuyō, con los tres sellos puestos y la puerta del dojo abierta. |

Las cinco de prueba nuevas (`prueba_tarde` y las de cada jefe) traen los campos que agregó C2: `shrines` (los santuarios
donde ya rezó; `cp_fields` queda sin rezar a propósito para ver "Sin rezar" en el mapa), `sealsPlaced` y `mapFog` vacío.
Con `mapFog` vacío el mapa se arma de los flags y del santuario, como en una partida de antes del mapa. Todas traen
`pray_seen` y `tip_shrine`: rezar es el rezo corto y no sale el consejo de rezar. `playTime` y `deaths` son una estimación
para la meta de una hora, no una medición, y el cartel del final los suma.

### `prueba_juego_completo_cp_lake_falls.json`: se cerró el juego en medio del final

* Al cargar, `StoryDirector.Begin` corre `ResumeEnding`. La pantalla queda en negro y la escena del rescate arranca en el
  patio del dojo, con Kokuyō vencido y arrodillado y el abuelo atado. Después sale el cartel del final. Todo eso aunque el
  santuario sea el de la cascada: la música y el ambiente del lago se cortan dos cuadros después.
* Prueba: las cuerdas caen, el abuelo hace `Freed` y después `Walk`, suena `ending` y el cartel no reinicia el tema.
* Al irse con el abuelo guarda `ending`: para repetirla hay que volver a copiarla.
* Es de antes de C2 y se deja así a propósito. No tiene `wall_gate_open`, así que `SaveSystem.MigrateWallGate` le agrega
  `wall_gate_open` y `enc_wall` al cargar. Le faltan los disparadores del sur (`trig_fields`, `trig_forest_reveal`,
  `trig_wall_guards`, `trig_garden`), `pray_seen` y `shrines`. **No la uses para probar el lago ni la cascada.**

### `prueba_tarde_cp_lake_falls.json`: el final del juego, antes de Kokuyō

* Es la del juego completo sin `final_boss_done`, `boss_kage`, `boss_seen_kage` ni `dojo_open`.
* Para que sea una partida tardía coherente con C2 se le agregó:
  * `pray_seen` y `tip_shrine`.
  * `wall_gate_open` y `enc_wall`, lo mismo que le pone la migración.
  * `zone_hogar`, `zone_campos`, `zone_muralla` y `tut_map`: sin ellos, el mapa tardío tenía los campos en niebla.
  * `tip_parry_done`, `trig_fields`, `trig_forest_reveal`, `forest_seen`, `trig_wall_guards` y `trig_garden`: sin ellos,
    ir al bosque volvía a mostrar al abuelo arrastrado.
  * Doce santuarios rezados.
* Como en la del equipo, siguen vivos los campamentos de `fields1`, `forest1`, `garden1`, `mountain1` y `mountain2`, con
  sus idles de ambiente. Sirven para probar `EnemyAmbient`, el rodeo y `ZoneCulling`.
* Objetivo al cargar: "Llevá los sellos a la puerta del dojo". La cascada está calma.
* **Los tres sellos juntos** (el caso de una partida de antes de C2): el portal de la plataforma (179, 67) lleva a
  `cp_dojo_gate`. Desde ahí, ir a la puerta (`goto 0 107 15`) e interactuar ("Colocar los sellos"). Los tres medallones
  salen en abanico, vuelan a sus huecos, la luz corre entre los tres, la puerta se abre y aparece el diálogo
  `dojo_gate_open`. Después se entra a Kokuyō como con `prueba_kokuyo`.
* Para probar el último sello solo, poné `"sealsPlaced": [true, false, true]`: se coloca el Sello del Agua y la puerta
  abre con él.

### `prueba_goro.json`: Gorō en la cumbre de Kodoyama

* Hecho: el prólogo, la muralla, el jardín, el sumo (dash y habilidades), la puerta del dojo vista con sus guardias y la
  subida a la montaña (`enc_mountain1`, `enc_mountain2`). Sin sellos.
* Sin `boss_goro`, `boss_seen_goro`, `goro_armor_seen` ni `goro_avalanche_seen`: presentación entera, primera
  `ArmorRise` entera y primera avalancha.
* Kaito aparece a 16.6 m del centro de la arena. La presentación arranca a 10.5 m (`radius × 0.7`).
* Entrar: `Nindo.AutoPilot.Run("goto -195 118 12; talk 40; waitcontrol 30; bot on bueno")`.
* Variantes:
  * Con `goro_armor_seen` la armadura se arma rápido, como en el segundo intento.
  * Con `boss_seen_goro` la presentación es la corta del reintento.

### `prueba_mizuchi.json`: Mizuchi en la Cascada Kohan

* Gorō vencido con su sello puesto (`seals` y `sealsPlaced` = `[true, false, false]`).
* Hechos `enc_lake1`, `enc_lake2` y `falls_seen`. Sin `boss_mizuchi` ni `boss_seen_mizuchi`, y la cascada está crecida.
* Kaito aparece a 15.2 m. La presentación (sale del pozo) arranca a 6.65 m.
* Entrar como dice el traspaso: teletransportar a (184, 3, 64) y `Nindo.AutoPilot.Run("goto 184 69 10; talk 40; waitcontrol 30; bot on bueno")`.
* Variante: sin `falls_seen`, la grúa de presentación de la cascada corre apenas carga, porque Kaito aparece adentro de
  `lago_cascada`.
* Después de ganar, el portal p_lake lleva a la puerta del dojo. Ahí se coloca el Sello del Agua (uno solo, con
  "Dos sellos puestos..."), que es el camino normal de un sello.

### `prueba_bambu.json`: Chikuō, el Maestro del Bambú

* Gorō y Mizuchi vencidos, con sus sellos puestos (`[true, true, false]`). Hecho `enc_bamboo1`.
* Sin `boss_ozeki` ni `boss_seen_chikuo`: la presentación entera de Chikuō. `boss_seen_ozeki` ya no cuenta.
* Kaito aparece a 23.5 m. La presentación arranca a 10.5 m.
* Entrar: el arco de bambú traba el `goto`, así que hay que teletransportar a (122, 2, 150) y correr
  `Nindo.AutoPilot.Run("goto 124 158 10; talk 40; waitcontrol 20; bot on bueno")`. `chikuo fase 2` y `chikuo fase 3` saltan de fase.
* Variante: con `boss_seen_chikuo` aparece el saludo corto.
* Después de ganar, el portal p_bamboo y el tercer sello abren la puerta del dojo.

### `prueba_kokuyo.json`: Kokuyō en el patio del dojo

* Los tres guardianes vencidos, los tres sellos puestos y `dojo_open`. El abuelo está atado frente al poste.
* Sin `boss_kage`, `boss_seen_kage`, `final_boss_done` ni `ending`: la presentación entera.
* Kaito aparece a 20.1 m del centro (cp_dojo, mirando al este). La presentación arranca a 12.6 m.
* Entrar: `Nindo.AutoPilot.Run("goto 0 124 15; talk 40; waitcontrol 30; bot on bueno")`. `kokuyo act N`, `kokuyo mitad`,
  `kokuyo sombra MOV` y `kokuyo patron NOMBRE` sirven en plena pelea.
* Variantes:
  * Con `boss_seen_kage` sale la presentación corta.
  * Salir del Play después del último golpe y antes de irse con el abuelo deja la partida como la del juego completo
    (`ResumeEnding`).

### Si se cuelga

Si `talk` termina en la pausa entre dos diálogos, `waitcontrol` se queda esperando. Si `Game.InCutscene &&
!AutoPilot.Busy`, volvé a correr `talk 10; waitcontrol 20; bot on bueno`.

Los pasos de `goto` y del portal salen de los radios de `world_plan.py` y del código (`BossArena.triggerRadius`,
`SealGate.radius` 6.5 m). Que lleguen sin trabarse no está probado en Unity.
