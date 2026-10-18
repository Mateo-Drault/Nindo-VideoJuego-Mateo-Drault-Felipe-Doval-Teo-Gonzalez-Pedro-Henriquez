using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Todos los textos del juego en un solo lugar (zonas, santuarios, diálogos, objetivos).
    /// Para cambiar la historia o traducir, se edita este archivo.
    /// </summary>
    public static class StoryText
    {
        public const string Kaito = "Kaito";
        public const string Abuelo = "Abuelo";
        public const string Ninja = "Ninja Kurokage";
        public const string Kage = "Kage";
        public const string Kokuyo = "Kokuyō";
        public const string Chikuo = "Chikuō";
        public const string Espiritu = "Espíritu de la Bandana";

        // Mizuchi: avisos de los cambios de fase y del final (MizuchiBoss)
        public const string MizuchiPhase2 = "¡El sello corrompe a Mizuchi!";
        public const string MizuchiPhase3 = "¡La cascada responde!";
        public const string MizuchiFreed = "Mizuchi, liberado";
        // Gorō armado (GoroBoss): el cartel de la fase 2 y la barra llevan el nombre arriba y el epíteto abajo, igual que
        // la primera barra ("Gorō" / "El Martillo de Kodoyama"). La montaña le da la armadura y le tira las rocas:
        // despertó con él
        public const string Goro = "Gorō";
        public const string GoroEpithet = "La Montaña Despierta";

        public static string CheckpointName(string id)
        {
            switch (id)
            {
                case "cp_home": return "Santuario del Hogar";
                case "cp_fields": return "Santuario de Inaba";
                case "cp_forest": return "Santuario del Bosque";
                case "cp_wall": return "Santuario de la Muralla";
                case "cp_garden": return "Santuario del Jardín";
                case "cp_dojo_gate": return "Santuario del Dojo";
                case "cp_mountain": return "Santuario de Kodoyama";
                case "cp_mountain_top": return "Santuario de la Cumbre";
                case "cp_lake": return "Santuario del Lago";
                case "cp_lake_docks": return "Santuario de los Muelles";
                case "cp_bamboo": return "Santuario del Bambú";
                case "cp_dojo": return "Santuario del Patio";
                case "cp_lake_falls": return "Santuario de la Cascada";
                case "cp_bamboo_gate": return "Santuario del Arco de Bambú";
                default: return "Santuario";
            }
        }

        public static void ConfigureZone(Zone z)
        {
            switch (z.id)
            {
                case "hogar":
                    z.title = "Hogar de Kaito"; z.subtitle = "La colina del abuelo";
                    z.music = "explore_home"; z.ambience = "night";
                    z.fogColor = new Color(0.07f, 0.1f, 0.17f); z.fogDensity = 0.010f; z.ambientSky = new Color(0.24f, 0.3f, 0.45f);
                    break;
                case "campos":
                    z.title = "Campos de Inaba"; z.subtitle = "Aldea de granjeros";
                    z.music = "explore_home"; z.ambience = "night";
                    z.fogColor = new Color(0.08f, 0.11f, 0.17f); z.fogDensity = 0.010f; z.ambientSky = new Color(0.24f, 0.3f, 0.44f);
                    break;
                case "bosque":
                    z.title = "Linde del Bosque"; z.subtitle = "Donde la luna no llega";
                    z.music = "explore_forest"; z.ambience = "forest";
                    z.fogColor = new Color(0.06f, 0.09f, 0.11f); z.fogDensity = 0.012f; z.ambientSky = new Color(0.2f, 0.27f, 0.34f);
                    break;
                case "muralla":
                    z.title = "La Muralla Kurokage"; z.subtitle = "Territorio del clan";
                    z.music = "explore_forest"; z.ambience = "forest";
                    z.fogColor = new Color(0.07f, 0.09f, 0.14f); z.fogDensity = 0.011f; z.ambientSky = new Color(0.22f, 0.27f, 0.38f);
                    break;
                case "jardin":
                    z.title = "Jardín del Clan"; z.subtitle = "La aldea de las luciérnagas";
                    z.music = "explore_garden"; z.ambience = "garden";
                    z.fogColor = new Color(0.07f, 0.09f, 0.16f); z.fogDensity = 0.008f; z.ambientSky = new Color(0.26f, 0.3f, 0.48f);
                    break;
                case "dojo":
                    z.title = "Dojo Kurokage"; z.subtitle = "El final del camino";
                    z.music = "explore_dojo"; z.ambience = "wind";
                    z.fogColor = new Color(0.1f, 0.06f, 0.1f); z.fogDensity = 0.010f; z.ambientSky = new Color(0.3f, 0.22f, 0.36f);
                    break;
                case "montana":
                    z.title = "Montaña Kodoyama"; z.subtitle = "Rocas, nieve y silencio";
                    z.music = "explore_mountain"; z.ambience = "wind"; z.snow = true;
                    z.fogColor = new Color(0.16f, 0.19f, 0.26f); z.fogDensity = 0.012f; z.ambientSky = new Color(0.32f, 0.38f, 0.52f);
                    break;
                case "lago":
                    z.title = "Aldea del Lago Kohan"; z.subtitle = "Pescadores bajo la luna";
                    z.music = "explore_lake"; z.ambience = "water";
                    z.fogColor = new Color(0.06f, 0.12f, 0.16f); z.fogDensity = 0.012f; z.ambientSky = new Color(0.22f, 0.32f, 0.45f);
                    break;
                case "lago_cascada":
                    // arena de Mizuchi: cámara más baja y algo más lejos, si no la cascada queda arriba del cuadro
                    z.title = "Cascada Kohan"; z.subtitle = "Donde los koi se vuelven dragones";
                    z.music = "explore_lake"; z.ambience = "water";
                    z.fogColor = new Color(0.06f, 0.12f, 0.16f); z.fogDensity = 0.012f; z.ambientSky = new Color(0.22f, 0.32f, 0.45f);
                    z.cameraPitchOffset = -4f; z.cameraDistanceOffset = 1f;
                    break;
                case "bambu":
                    z.title = "Bosque de Bambú"; z.subtitle = "El susurro del viento";
                    z.music = "explore_forest"; z.ambience = "bamboo";
                    z.fogColor = new Color(0.08f, 0.13f, 0.11f); z.fogDensity = 0.011f; z.ambientSky = new Color(0.23f, 0.33f, 0.31f);
                    break;
                default:
                    z.title = z.id; break;
            }
        }

        static DialogueLine L(string s, string t) => new DialogueLine(s, t);

        public static List<DialogueLine> Dialogue(string id)
        {
            switch (id)
            {
                // lo que murmura en el piso va antes, mientras se despierta (WakeMumble): esto es cuando ya lo vio
                case "intro_wake":
                    return new List<DialogueLine> {
                        L(Kaito, "¡Abuelo!"),
                        L(Abuelo, "¡KAITO! ¡Desatá la cinta de la guadaña! ¡Rápido!"),
                    };
                case "intro_bandana":
                    return new List<DialogueLine> {
                        L(Kaito, "La cinta... ¡se me ató sola! Y la guadaña... ¡es una katana!"),
                        L(Kaito, "Siento... todo lo que sabe el abuelo. Cada movimiento."),
                        L(Ninja, "¿La bandana del viejo? ...Llevátelo. Yo me encargo del mocoso."),
                    };
                case "intro_after_fight":
                    return new List<DialogueLine> {
                        L(Kaito, "Se llevaron al abuelo hacia el norte. Voy a seguir su rastro."),
                        L(Kaito, "Abuelo... aguantá. Ya voy."),
                    };
                case "fields":
                    return new List<DialogueLine> {
                        L(Kaito, "Huellas en el barro... y tiraron sus cosas por todos lados. Van hacia el bosque."),
                    };
                case "forest_reveal":
                    return new List<DialogueLine> {
                        L(Abuelo, "¡No te rindas, Kaito! ¡Recordá: el camino ninja no se recorre solo!"),
                        L(Kaito, "¡ABUELO! ...Lo arrastran hacia la muralla del clan."),
                    };
                case "wall_guards":
                    return new List<DialogueLine> {
                        L(Ninja, "¡Alto ahí! Nadie cruza la muralla Kurokage."),
                        L(Kaito, "Entonces voy a tener que abrirla yo."),
                    };
                // vencidos los guardias: el portón tiene un sello de sombra (StoryDirector.WallGuardsDown)
                case "wall_sealed":
                    return new List<DialogueLine> {
                        L(Kaito, "El portón está atado con cuerdas de sombra... Así no se abre ni a golpes."),
                        L(Espiritu, "Esa sombra la tejió el clan. Acercate al portón y soltá la luz de la bandana."),
                    };
                case "wall_open":
                    return new List<DialogueLine> {
                        L(Kaito, "¡Se abrió! Más allá está el jardín del clan. Aguantá, abuelo."),
                    };
                case "garden":
                    return new List<DialogueLine> {
                        L(Kaito, "Tantas luces... tantos guardias. Tengo que tener cuidado y pelear con la cabeza."),
                    };
                case "sumo_intro":
                    return new List<DialogueLine> {
                        L("Luchador de Sumo", "¡JA! ¿Este es el nieto del viejo? ¡Te voy a aplastar como a un grano de arroz!"),
                    };
                case "abilities":
                    return new List<DialogueLine> {
                        L(Kaito, "La bandana brilla... el espíritu del abuelo me habla."),
                        L("Espíritu de la Bandana", "Usá mi fuerza cuando el espíritu esté lleno. Corte del Viento {Ability1} y Torbellino de Hojas {Ability2}."),
                    };
                // la primera vez frente a la puerta (StoryDirector.DojoGateFirstLook: el plano termina en los tres huecos)
                case "dojo_gate":
                    return new List<DialogueLine> {
                        L(Kaito, "La puerta del dojo... tres huecos con grabados: una montaña, el agua y el bambú."),
                        L(Kaito, "Sellos. Uno en la Montaña Kodoyama, al oeste. Otro en el Lago Kohan, al este. Y el último en el Bosque de Bambú, al noreste."),
                        L(Kaito, "Cada guardián tiene el suyo. Apenas consiga uno, lo traigo y lo pongo en su lugar."),
                    };
                case "dojo_gate_incomplete":
                    return new List<DialogueLine> {
                        L(Kaito, "Todavía faltan sellos. Montaña al oeste, lago al este, bambú al noreste."),
                    };
                case "dojo_gate_open":
                    return new List<DialogueLine> {
                        L(Kaito, "Los tres sellos... ¡la puerta se abre!"),
                    };
                case "goro_intro":
                    return new List<DialogueLine> {
                        L("Gorō", "Hmmm... Un niño con una espada de juguete. Mi martillo ha roto montañas más grandes que vos."),
                    };
                case "mizuchi_intro":
                    return new List<DialogueLine> {
                        L(Espiritu, "Ese koi lleva siglos intentando remontar la cascada... y el clan le clavó el sello en el lomo."),
                        L(Kaito, "Por eso el lago está oscuro. Aguantá, gran koi: te voy a sacar esa estaca."),
                        L(Espiritu, "Mirá el agua, Kaito. El agua no miente: dorada, desviá. Roja, salí de ahí."),
                    };
                // Chikuō, el Ermitaño de las Cañas (el id del jefe sigue siendo "ozeki"): vive en las cañas del claro, fue maestro
                // de Kokuyō un invierno y Kokuyō no aprendió a doblarse
                case "ozeki_intro":
                    return new List<DialogueLine> {
                        L(Chikuo, "¡Je, je! Mirá quién vino a visitar al viejo de las cañas. ¿Te perdiste, muchacho?"),
                        L(Chikuo, "El sello que buscás me lo dejó Kokuyō. Fue mi alumno un invierno: quería ser duro como la piedra."),
                        L(Chikuo, "El bambú se dobla, por eso no se quiebra. ¿Lo querés? Bajame de acá. ¡Si podés!"),
                        L(Kaito, "Bajá vos, o te bajo yo."),
                    };
                // vencido, sentado con las piernas cruzadas, después de la reverencia
                case "bamboo_defeat":
                    return new List<DialogueLine> {
                        L(Chikuo, "Je... Hacía cien inviernos que nadie me bajaba del bambú."),
                        L(Chikuo, "Lo alto se baja desde la raíz. No te lo olvides."),
                        L(Chikuo, "Llevate el sello. Y cuando enfrentes a Kokuyō, mirá su sombra: siempre llega antes que él."),
                    };
                case "kage_intro":
                    return new List<DialogueLine> {
                        L(Kokuyo, "Así que el viejo te dio su cinta."),
                        L(Kokuyo, "Yo también llevé una. Fui su mejor alumno... hasta que eligió una granja antes que su camino."),
                        L(Kokuyo, "La corté en dos el día que se fue. Desde entonces camino solo, y nada me sigue. Ni siquiera mi sombra."),
                        L(Kaito, "No estoy solo. Nunca lo estuve."),
                    };
                case "kage_intro_abuelo":
                    return new List<DialogueLine> {
                        L(Abuelo, "¡Kaito! ¡Su sombra se mueve antes que él! ¡Mirá el suelo!"),
                    };
                // frases de Kokuyō en plena pelea (avisos arriba, sin pausar)
                case "kokuyo_bark_tear":
                    return new List<DialogueLine> {
                        L(Kokuyo, "¿Ves? Hasta mi sombra me traiciona."),
                        L(Kokuyo, "¡Que pelee por su cuenta!"),
                    };
                case "kokuyo_bark_eclipse":
                    return new List<DialogueLine> {
                        L(Kokuyo, "Sin luz no hay sombra. Sin sombra no hay aviso."),
                        L(Abuelo, "¡No estás solo, Kaito! ¡La cinta ve por vos!"),
                    };
                case "kokuyo_bark_last":
                    return new List<DialogueLine> { L(Kokuyo, "¡Todavía no!") };
                // a mitad de cada acto (KokuyoBoss.Pacing): se planta, ruge y cambia el ritmo
                case "kokuyo_bark_mitad1":
                    return new List<DialogueLine> { L(Kokuyo, "El viejo de las cañas te enseñó a doblarte. Yo no me doblo.") };
                case "kokuyo_bark_mitad2":
                    return new List<DialogueLine> { L(Kokuyo, "Mi sombra aprende rápido. Más rápido que vos.") };
                case "kokuyo_bark_mitad3":
                    return new List<DialogueLine> { L(Kokuyo, "En la oscuridad no hay maestro ni alumno.") };
                case "kokuyo_hint_suelo":
                    return new List<DialogueLine> { L(Abuelo, "El suelo, Kaito. Su sombra golpea primero.") };
                // la primera vez que la sombra ataca sola (Acto 1) y la primera vez que sale de la oscuridad (eclipse)
                case "kokuyo_hint_sombra":
                    return new List<DialogueLine> { L(Abuelo, "¡Ojo, Kaito! ¡La sombra ataca sola! ¡Desviala cuando se cierre el anillo!") };
                case "kokuyo_hint_oscuridad":
                    return new List<DialogueLine> { L(Abuelo, "¡La sombra sigue ahí, en la oscuridad! ¡Cuando aparezca, desviala!") };
                case "seal_mountain":
                    return new List<DialogueLine> { L(Kaito, "El Sello de la Montaña. Un portal apareció: me lleva de vuelta al dojo.") };
                case "seal_lake":
                    return new List<DialogueLine> {
                        L(Kaito, "El Sello del Agua... y el koi, por fin libre."),
                        L(Espiritu, "Hace mucho, tu abuelo ayudó a otro koi a subir esta cascada. Ese dragón vive en tu bandana."),
                    };
                case "seal_bamboo":
                    return new List<DialogueLine> {
                        L(Kaito, "Gracias, maestro."),
                        L(Kaito, "El Sello del Bambú. Lo que está alto se baja desde la raíz."),
                    };
                case "ending":
                    return new List<DialogueLine> {
                        L(Abuelo, "Kaito... viniste. Sabía que la cinta te elegiría."),
                    };
                // el final (StoryDirector.Ending): el reencuentro va en un plano de los dos y esto en otro de los tres
                case "ending_kokuyo":
                    return new List<DialogueLine> {
                        L(Kokuyo, "...Te eligió a vos. Como a él."),
                        L(Abuelo, "No te dejé solo, Kokuyō. Vos cortaste la cinta."),
                        L(Abuelo, "El verdadero poder nace del lazo que nos une a los nuestros."),
                    };
                case "ending_ribbon":
                    return new List<DialogueLine> {
                        L(Kaito, "Tomá. Es tuya."),
                    };
                case "ending_final":
                    return new List<DialogueLine> {
                        L(Abuelo, "Vamos a casa, nieto. Ese es tu nindō: el camino ninja."),
                    };
                case "grandpa_home":
                    return new List<DialogueLine> { L(Abuelo, "...") };
                default:
                    return new List<DialogueLine> { L("", id) };
            }
        }

        /// <summary>
        /// Frases de Chikuō en plena pelea (salen como grito, una vez cada una y no más de una cada 12 s, salvo las de los
        /// momentos que enseñan). Juguetón, excéntrico y sabio: se ríe de todo y de sí mismo, nunca cruel; cuando Kaito le
        /// pega se queja como un viejo y lo felicita.
        /// </summary>
        public static string ChikuoLine(string beat)
        {
            switch (beat)
            {
                case "cosquillas": return "¡Je! ¡Cosquillas!";
                case "latigazo": return "¡Ay, mis huesos! ¿Quién te enseñó eso?";
                case "estampado": return "¡Uf! Esa caña estaba más dura que yo.";
                case "caida": return "¡Eh! ¡Esa caña era mía!";
                case "empujon": return "¡Gracias por el empujón!";
                case "risa": return "¡Ja, ja! ¡Te di en la nariz!";
                case "maestro": return "¿Y? ¿No me vas a bajar?";
                case "fase2": return "¡Ja! Me bajaste del bambú. Bueno, bailemos en el piso.";
                case "grulla": return "¡Mirá, sin manos!";
                case "desafinado": return "¡Me hiciste desafinar!";
                case "afinado": return "¡Afinado! Me ganaste la canción.";
                case "fase3": return "¡Ahora que cante todo el bosque!";
                case "rajada": return "¡Mi bambú! Bueno... ahora es leña.";
                case "ultima": return "Última canción, muchacho. Escuchala bien.";
                default: return "";
            }
        }

        /// <summary>
        /// Gorō armado (GoroBoss): el grito al levantarse con la armadura, el aviso de la primera avalancha y el del primer
        /// corte que le rebota en la roca (título y detalle, en dos renglones).
        /// </summary>
        public static string GoroLine(string beat)
        {
            switch (beat)
            {
                case "fase2": return "¿Creíste que me habías ganado? La montaña recién despierta.";
                case "avalancha": return "¡Avalancha!";
                case "avalancha_sub": return "Las rocas no se desvían: salí del carril rojo";
                case "coraza": return "La roca rebota tus cortes";
                case "coraza_sub": return "Desviá o esquivá el golpe y pegale después";
                default: return "";
            }
        }

        /// <summary>Lo que dice Chikuō al recibir a Kaito otra vez después de vencerlo (una frase distinta por intento; si la
        /// lección sigue en la fase 2 o 3, retoma donde quedó).</summary>
        public static string ChikuoRetry(int attempt, int phase)
        {
            if (phase >= 2) return "El bosque te estaba esperando. Seguimos donde quedamos.";
            if (phase == 1) return "Las cañas siguen inclinadas. Vení a bailar.";
            switch (attempt)
            {
                // volvió otro día (el contador de intentos vive en la pelea y arranca en 0 al cargar la partida)
                case 0: return "¡Volviste! Esta vez mirá mis cascabeles.";
                case 1: return "Otra vez. Cuando brillan blancos, cortá.";
                case 2: return "El bambú se dobla y vuelve. Vos también.";
                case 3: return "No me mirés a mí: mirá la caña.";
                default: return "El que cae siete veces se levanta ocho.";
            }
        }

        /// <summary>Pistas de una línea que aparecen como tutorial en plena pelea (las teclas van entre llaves).</summary>
        public static string Hint(string id)
        {
            switch (id)
            {
                case "kage_shadow": return "La sombra no se corta con la katana: desviá sus cortes o clavala con {Ability1} o {Ability2}";
                // Chikuō, el Ermitaño de las Cañas: a él no se le pega arriba, se le corta lo que lo sostiene (dos renglones)
                case "bamboo_whip": return "Cascabeles blancos: su caña está cargada\nCortala con {Attack} y lo despide";
                case "bamboo_stamp": return "Lo despide para el lado del corte\nSi atrás hay otra caña, se estrella contra ella";
                case "bamboo_deny": return "Cuando salta, el ensō blanco marca su caña\nCortala antes de que la agarre";
                case "bamboo_tickle": return "Sin el brillo blanco, la caña te barre\nParale los dardos y entrá cuando cargue";
                case "bamboo_staff": return "Su bastón también es una caña\nCortalo con {Attack} mientras está arriba";
                case "bamboo_flute": return "Lo que toca la flauta, lo repite\nAguda: desviá con {Parry}. Grave: salí con {Dash}";
                case "bamboo_crack": return "La caña rajada se quiebra con el próximo latigazo\nY él la puede tirar encima tuyo";
                default: return "";
            }
        }

        /// <summary>
        /// Lo que Kaito reza en voz baja con las manos juntas, la primera vez en cada santuario (sale arriba sin pausar la
        /// escena). La primera de la partida es por el abuelo; después cambia con lo que avanzó, para no repetirse.
        /// </summary>
        public static string PrayerLine(bool first, SaveData s)
        {
            if (first) return "Abuelo... donde sea que te tengan, aguantá. Ya voy a buscarte.";
            int seals = s.SealCount;
            if (seals >= 3) return "Los tres sellos, abuelo. Esta noche volvés a casa.";
            if (seals == 2) return "Dos sellos, abuelo. Me falta uno solo.";
            if (seals == 1) return "Ya tengo un sello, abuelo. Esperame.";
            int n = s.shrines != null ? s.shrines.Count : 0;
            switch (n % 3)
            {
                case 0: return "Que el camino me lleve hasta vos, abuelo.";
                case 1: return "Abuelo, cuidate. Te voy a traer de vuelta a casa.";
                default: return "Cada santuario me acerca un poco más a vos.";
            }
        }

        /// <summary>Lo que murmura Kaito tirado en el piso del prólogo, mientras se despierta (StoryDirector.Prologue).</summary>
        public const string WakeMumble = "Ay... mi cabeza... ¿Qué pasó?";

        /// <summary>Kaito llama al abuelo al ir hacia él en el final, antes de que lo suelten (StoryDirector.Ending).</summary>
        public const string EndingCall = "¡Abuelo!";

        /// <summary>El consejo del primer santuario después del prólogo (StoryDirector.TickShrineTip).</summary>
        public const string ShrinePrayHint = "Rezá en los santuarios con {Interact}: te curan, guardan la partida y, si caés, volvés ahí.";

        // ------------------------------------------------------------------ puerta de los tres sellos (World/SealGate)
        static readonly string[] sealNames = { "Sello de la Montaña", "Sello del Agua", "Sello del Bambú" };
        static readonly string[] placeSealPrompts = { "Colocar el Sello de la Montaña", "Colocar el Sello del Agua", "Colocar el Sello del Bambú" };
        public const string PlaceSealsPrompt = "Colocar los sellos", OpenGatePrompt = "Abrir la puerta", ExamineGatePrompt = "Examinar la puerta";

        /// <summary>El nombre de cada sello (el HUD, los carteles y el objetivo dicen lo mismo).</summary>
        public static string SealName(SealId s) => sealNames[(int)s];

        /// <summary>El cartel de la puerta cuando Kaito trae un solo sello (cadenas fijas: se compara cada cuadro).</summary>
        public static string PlaceSealPrompt(SealId s) => placeSealPrompts[(int)s];

        /// <summary>Lo que dice Kaito (arriba, sin pausar) al quedar un sello puesto y faltar otros.</summary>
        public static string SealPlacedLine(SaveData s, SealId justPlaced)
        {
            int placed = SealGate.PlacedCount(s);
            if (placed <= 1) return SealName(justPlaced) + ", en su lugar. Faltan dos.";
            return "Dos sellos puestos. Me falta uno solo.";
        }

        /// <summary>Kaito mira la puerta sin traer ningún sello nuevo: qué falta y dónde está.</summary>
        public static List<DialogueLine> GateIncomplete(SaveData s)
        {
            var missing = new List<string>();
            if (!s.HasSeal(SealId.Montana)) missing.Add("el de la Montaña Kodoyama, al oeste");
            if (!s.HasSeal(SealId.Lago)) missing.Add("el del Lago Kohan, al este");
            if (!s.HasSeal(SealId.Bambu)) missing.Add("el del Bosque de Bambú, al noreste");
            if (missing.Count >= 3) return Dialogue("dojo_gate_incomplete");
            string line = missing.Count == 2 ? $"Faltan dos sellos: {missing[0]}, y {missing[1]}."
                : missing.Count == 1 ? $"Falta un solo sello: {missing[0]}." : "Los tres sellos ya están en su lugar.";
            return new List<DialogueLine> { L(Kaito, line) };
        }

        /// <summary>
        /// Objetivo del HUD según lo que de verdad pasó y dónde está Kaito. Antes era un camino fijo: si la muralla no
        /// quedaba marcada como abierta (guardado viejo, o se llegó por otro lado) decía "seguí el rastro hacia el
        /// norte" en todas las zonas, aunque ya tuviera sellos. Ahora lo más avanzado manda (un sello implica la
        /// muralla y la puerta del dojo) y en la zona de un guardián que falta vencer dice a quién y dónde.
        /// </summary>
        public static string Objective(SaveData s)
        {
            if (!s.HasFlag(Flags.KatanaObtained)) return "Desatá la cinta de la guadaña";
            if (!s.HasFlag(Flags.Encounter("intro"))) return "Defendete";
            if (s.HasFlag(Flags.FinalBossDone)) return "";
            if (s.HasFlag(Flags.DojoOpen)) return "Entrá al dojo y rescatá al abuelo";
            string zone = Zone.Current != null ? Zone.Current.id : "";
            // los sellos se ponen de a uno, apenas se tienen (World/SealGate): en la tierra de un guardián que falta
            // vencer manda ese guardián (no se obliga a volver), en cualquier otro lado, ir a ponerlo
            int pending = SealGate.PendingCount(s);
            if (pending > 0 && !GuardianPending(s, zone))
            {
                // frente a la puerta (el patio del dojo y el jardín) ya no es "volvé"
                bool atGate = zone == "dojo" || zone == "jardin";
                // "Llevá" y no "Volvé a la puerta del dojo a colocar el Sello de la Montaña": esa no entraba en un renglón
                // y cortaba el nombre del sello ("Montaña" sola abajo)
                if (pending > 1) return atGate ? "Colocá los sellos en la puerta del dojo" : "Llevá los sellos a la puerta del dojo";
                string seal = SealName((SealId)SealGate.FirstPending(s));
                return atGate ? "Colocá el " + seal + " en la puerta del dojo" : "Llevá el " + seal + " a la puerta del dojo";
            }
            if (s.SealCount >= 3) return "Abrí la puerta del dojo";
            bool pastWall = s.HasFlag(Flags.WallGateOpen) || s.HasFlag(Flags.DojoGateSeen) || s.SealCount > 0 || PastTheWall(zone);
            // guardias vencidos y el portón con su sello de sombra (WallSeal)
            if (!pastWall && s.HasFlag(Flags.Encounter("wall"))) return "Abrí el portón de la muralla con la bandana";
            if (!pastWall)
                return s.HasFlag(Flags.ForestSeen) ? "Cruzá la muralla del clan Kurokage" : "Seguí el rastro de los secuestradores hacia el bosque";
            // en la tierra de un guardián: qué falta ahí
            switch (zone)
            {
                case "montana": if (!s.HasSeal(SealId.Montana)) return Guardian(s, "goro", "Vencé a Gorō en la cumbre de Kodoyama", "Tomá el Sello de la Montaña"); break;
                case "lago":
                case "lago_cascada": if (!s.HasSeal(SealId.Lago)) return Guardian(s, "mizuchi", "Vencé a Mizuchi en la Cascada Kohan", "Tomá el Sello del Agua"); break;
                case "bambu": if (!s.HasSeal(SealId.Bambu)) return Guardian(s, "ozeki", "Vencé a Chikuō en el claro del bambú", "Tomá el Sello del Bambú"); break;
            }
            if (!s.HasFlag(Flags.DojoGateSeen) && s.SealCount == 0) return "Atravesá el Jardín del Clan hasta el dojo";
            var missing = new List<string>();
            if (!s.HasSeal(SealId.Montana)) missing.Add("Montaña (oeste)");
            if (!s.HasSeal(SealId.Lago)) missing.Add("Lago (este)");
            if (!s.HasSeal(SealId.Bambu)) missing.Add("Bambú (noreste)");
            return $"Conseguí los sellos ({s.SealCount}/3): " + string.Join(", ", missing);
        }

        // en la tierra de un guardián cuyo sello todavía no tiene
        static bool GuardianPending(SaveData s, string zone) =>
            (zone == "montana" && !s.HasSeal(SealId.Montana)) || ((zone == "lago" || zone == "lago_cascada") && !s.HasSeal(SealId.Lago)) ||
            (zone == "bambu" && !s.HasSeal(SealId.Bambu));

        // las zonas que quedan del otro lado de la muralla (llegar a cualquiera ya es haberla cruzado)
        static bool PastTheWall(string zone) =>
            zone == "jardin" || zone == "dojo" || zone == "montana" || zone == "lago" || zone == "lago_cascada" || zone == "bambu";

        // el guardián ya cayó pero el sello sigue en el piso (se cerró el juego antes de tomarlo): eso es lo que falta
        static string Guardian(SaveData s, string boss, string fight, string pickUp) =>
            (s.HasFlag(Flags.Boss(boss)) ? pickUp : fight) + $" ({s.SealCount}/3 sellos)";
    }
}
