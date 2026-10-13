using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Guion del juego (según el documento de diseño): prólogo con la guadaña y la bandana,
    /// tutorial de parry en cámara lenta, el rastro hasta la muralla, el jardín del clan, el
    /// luchador de sumo (tutorial del dash mágico), los tres guardianes de los sellos, la
    /// puerta del dojo y el combate final contra Kokuyō para rescatar al abuelo (StoryDirector.Kokuyo.cs).
    /// </summary>
    public partial class StoryDirector : MonoBehaviour
    {
        PlayerController P => Game.Player;
        bool parryTutorial, finisherTip;
        GameObject scytheProp;
        Coroutine deathRoutine;

        void Awake()
        {
            Game.Story = this;
        }

        void OnEnable()
        {
            GameEvents.PlayerDied += OnPlayerDied;
            GameEvents.BossDefeated += OnBossDefeated;
            GameEvents.FlagSet += OnFlag;
            GameEvents.Parry += OnParry;
            GameEvents.ZoneEntered += OnZoneEntered;
        }

        void OnDisable()
        {
            GameEvents.PlayerDied -= OnPlayerDied;
            GameEvents.BossDefeated -= OnBossDefeated;
            GameEvents.FlagSet -= OnFlag;
            GameEvents.Parry -= OnParry;
            GameEvents.ZoneEntered -= OnZoneEntered;
        }

        void OnDestroy() { if (Game.Story == this) Game.Story = null; }

        // ================================================================== inicio
        public void Begin(bool newGame)
        {
            SetupWallSeal();   // el sello de sombra del portón de la muralla, si sigue cerrado (StoryDirector.Wall)
            var s = Game.Save;
            P.SetKatanaVisible(s.HasFlag(Flags.KatanaObtained));
            UpdateObjective();
            if (!s.HasFlag(Flags.IntroDone)) StartCoroutine(Intro());
            // se salió entre el último golpe a Kokuyō y la salida con el abuelo (FinalBossDone se guarda al caer él y
            // Ending recién al irse): sin esto esa partida nunca volvía a ver el reencuentro ni el cartel del final
            else if (s.HasFlag(Flags.FinalBossDone) && !s.HasFlag(Flags.Ending)) StartCoroutine(ResumeEnding());
            else
            {
                StartCoroutine(Game.UI.Fade(0f, 1.2f));
                Zone.ForceRefresh();
            }
        }

        public void UpdateObjective() => Game.UI?.SetObjective(StoryText.Objective(Game.Save));

        // ================================================================== cinemáticas
        // cinemáticas abiertas y cuántas pidieron franjas: dos que se pisan (el diálogo de una derrota mientras corre otra)
        // no se devuelven el control una a la otra. Antes la primera en terminar sacaba las franjas, soltaba a Kaito y
        // apagaba InCutscene con la otra todavía en el medio
        int cutsceneDepth, letterboxDepth;

        IEnumerator Cutscene(IEnumerator body, bool letterbox = true)
        {
            // si justo estaba en pausa (p. ej. Esc durante la cámara lenta de la muerte de un jefe) la
            // cinemática espera: si no, corría detrás del panel y el diálogo avanzaba con los clics del menú.
            // El rezo corto no es una cinemática: una que arrancaba en el medio (el diálogo de la derrota de Chikuō, la
            // cascada) pasaba a Kaito de rodillas a la guardia con la katana del piso a la mano y, al terminar, lo
            // dejaba congelado con el controlador apagado hasta que el rezo terminaba. Espera a que se levante (≤ 2.3 s);
            // el rezo entero corre adentro de su propia cinemática, así que no se espera a sí mismo
            while (Game.IsPaused || praying) yield return null;
            bool first = cutsceneDepth++ == 0;
            Game.InCutscene = true;
            if (Game.Input != null) Game.Input.GameplayBlocked = true;
            if (letterbox && letterboxDepth++ == 0) Game.UI?.Letterbox(true);
            // la de adentro no vuelve a tomar a Kaito: EnterScripted lo pasa a la guardia y le cortaba la pose a la de afuera
            if (first) P?.EnterScripted();
            yield return body;
            if (letterbox && --letterboxDepth == 0) Game.UI?.Letterbox(false);
            if (--cutsceneDepth > 0) yield break;
            Game.Camera?.CancelAllShots();
            P?.ExitScripted();
            Game.InCutscene = false;
            if (Game.Input != null) { Game.Input.GameplayBlocked = Game.IsPaused; Game.Input.ClearBuffer(); }
            UpdateObjective();
        }

        IEnumerator Say(string id) => Game.UI.Dialogue(StoryText.Dialogue(id));

        public void PlayDialogueById(string id) => StartCoroutine(Cutscene(Say(id), false));

        Vector3 PointPos(string id, Vector3 fallback)
        {
            var t = Game.World != null ? Game.World.Point(id) : null;
            return t != null ? t.position : fallback;
        }

        // ================================================================== PRÓLOGO
        IEnumerator Intro()
        {
            while (Game.IsPaused) yield return null;   // pausa abierta durante la carga
            Game.InCutscene = true;
            if (Game.Input != null) Game.Input.GameplayBlocked = true;
            Game.UI.SetFade(1f);
            Game.UI.Letterbox(true);
            P.EnterScripted();
            P.SetKatanaVisible(false);

            // el ninja que se queda espera quieto
            var introEnc = Encounter.Get("intro");
            if (introEnc != null)
            {
                introEnc.manualActivation = true;
                foreach (var m in introEnc.Members) if (m != null) m.EnterScripted();
            }

            // la guadaña tirada en el piso
            Vector3 scythePos = PointPos("scythe", P.transform.position + P.transform.forward * 1.6f);
            scytheProp = new GameObject("Guadaña");
            scytheProp.transform.position = scythePos;
            var model = Game.Content.Prop("scythe");
            if (model != null) Instantiate(model, scytheProp.transform);
            var bandana = scytheProp.AddComponent<BandanaScythe>();
            bandana.prompt = "Desatar la cinta";
            bandana.promptHeight = 1f;
            bandana.radius = 2.5f;
            bandana.enabled = false;

            // abuelo y su secuestrador (GrandpaAnims Kidnap/Dragged). El NPC 'kidnap' mira hacia donde se lo llevan: el
            // abuelo, de cara a Kaito, y el ninja entre los dos, de espaldas a Kaito
            Vector3 kidPos = PointPos("kidnap_a", P.transform.position + new Vector3(6, 0, 8));
            Vector3 exit = PointPos("kidnap_exit", kidPos + new Vector3(0, 0, 25));
            var grandpa = NPC.Spawn("kidnap", kidPos, Quaternion.LookRotation((exit - kidPos).Flat().normalized + Vector3.forward * 0.001f), null);
            grandpa.AwaitKidnap();
            Enemy kidnapper = null;

            // texto de apertura sobre negro
            yield return new WaitForSecondsRealtime(0.6f);
            Game.UI.ShowAreaTitle("Una noche de luna llena", "Kaito y su abuelo escucharon un ruido en los cultivos...");
            yield return new WaitForSecondsRealtime(4.4f);
            Game.UI.ShowAreaTitle("...", "Kaito salió con la guadaña. De un arbusto salió un golpe.");
            Game.Audio?.Play("hit_heavy", null, 1f);
            Game.Camera?.Shake(0.6f);
            yield return new WaitForSecondsRealtime(4.2f);

            // Kaito vuelve en sí en el piso; vuelve al cortar por encima de su hombro hacia el abuelo (StoryDirector.Prologue)
            yield return KaitoComesTo(kidPos);

            // ve al abuelo siendo llevado
            // de costado al arrastre y del lado del ninja (offset local: el transform mira a 'exit'): se ven los dos brazos
            // tirantes y las muñecas agarradas. Desde atrás, el abuelo sentado tapaba al ninja y no se leía el tirón
            int shot2 = Game.Camera.PlayFollowShot(grandpa.transform, new Vector3(4.6f, 2.4f, -3.4f), 0.7f, 32f, 0f, 0.9f, 0.9f, true);
            // el ninja le agarra la muñeca, lo tira al piso (el golpe y el polvo, de NPC) y se lo lleva hacia el bosque. Arranca
            // kidnapLead después del corte: el contraplano de Kaito (StoryDirector.Prologue) se sostiene 0.8 s encima de
            // este plano y se mezcla en 0.5 s, así el agarre (0.57 s después de arrancar: a los 1.97 s) y la caída (0.9 s:
            // a los 2.3 s) caen con este plano ya quieto. Con 1.2 s y el contraplano de 1.4 + 0.8 s pasaban a mitad de la
            // mezcla; arrancando en el corte, el secuestro entero pasaba en el contraplano a 17 m. Mientras, se miran
            // (KidnapWait: el ninja agazapado, el abuelo respira). Lo que falta hasta el diálogo no cambia (3.2 s)
            const float kidnapLead = 1.4f;
            yield return new WaitForSecondsRealtime(kidnapLead);
            grandpa.Kidnap(exit);
            yield return new WaitForSecondsRealtime(2.4f - kidnapLead + 0.8f);
            yield return Say("intro_wake");
            Game.Camera.CancelShot(shot2);

            // control al jugador: tiene que desatar la cinta
            Game.UI.Letterbox(false);
            P.ExitScripted();
            Game.InCutscene = false;
            if (Game.Input != null) Game.Input.GameplayBlocked = false;
            bandana.enabled = true;
            UpdateObjective();
            Game.UI.ShowTutorial($"Acercate a la guadaña y presioná {{Interact}}");
            while (!Game.Save.HasFlag(Flags.KatanaObtained)) yield return null;
            Game.UI.HideTutorial();

            // ¡la bandana se ata sola y la guadaña se vuelve katana!
            yield return Cutscene(BandanaAwakening(grandpa, kidnapper));

            // pelea del prólogo con tutorial de parry. Si el guardado ya tiene el encuentro ganado
            // pero no "intro_done" (se salió durante el diálogo final), Activate() no haría nada y
            // FinishIntro no se llamaría nunca: el prólogo se repetiría en cada "Continuar".
            if (introEnc != null && !introEnc.Completed)
            {
                // el ninja de la práctica no muere ni se quiebra hasta que se practique a velocidad real
                foreach (var m in introEnc.Members) if (m != null) { m.ExitScripted(true); m.SetParryPractice(true); }
                introEnc.Activate();
                parryTutorial = true;
                parryGuided = parryRealtime = parryMisses = parryAttempts = 0;
            }
            else FinishIntro();
        }

        IEnumerator LieDown(bool down)
        {
            // el pivote del modelo (LeanPivot) lo reescribe ProceduralMotion en cada LateUpdate:
            // la pose se le pasa a él en vez de rotar el pivote directo (si no, Kaito nunca se acuesta)
            var motion = P.GetComponent<ProceduralMotion>();
            if (motion == null) yield break;
            Quaternion lying = Quaternion.Euler(-82f, 0f, 0f);
            if (down) { motion.scriptedPose = lying; yield break; }
            float t = 0f;
            while (t < 1f)
            {
                t += Time.unscaledDeltaTime * 1.4f;
                motion.scriptedPose = Quaternion.Slerp(lying, Quaternion.identity, Mathf.SmoothStep(0f, 1f, t));
                yield return null;
            }
            motion.scriptedPose = Quaternion.identity;
        }

        IEnumerator BandanaAwakening(NPC grandpa, Enemy kidnapper)
        {
            P.ScriptedFace(scytheProp.transform.position);
            int shot = Game.Camera.PlayAbilityShot(P.transform, CameraDirector.AbilityShot.LowOrbit, 3.2f);
            Game.Time.SlowMotion(0.4f, 1.6f, 0.1f, 0.5f);
            Game.FX.SealGlow(P.transform.position + Vector3.up);
            Game.FX.Petals(P.transform.position + Vector3.up, 1.5f);
            Game.Audio?.Play("rage_on", P.transform.position, 1f);
            Destroy(scytheProp);
            yield return new WaitForSecondsRealtime(0.9f);
            P.SetKatanaVisible(true);
            CharacterFactory.SetBandana(P.model, true, true);   // la cinta se le ata sola: vuelve su amarillo con un destello
            P.ScriptedPlay("Attack3");
            Game.FX.Screen.WhiteFlash(0.7f);
            Game.Camera.Shake(0.5f);
            Game.UI.ShowToast("Espíritu de la Bandana", UIFactory.Gold, 2.2f);
            yield return new WaitForSecondsRealtime(1.6f);
            Game.Camera.CancelShot(shot);
            yield return Say("intro_bandana");
            // el secuestrador se lleva al abuelo entre el humo
            // (si ya llegó a kidnap_exit, NPC.Arrive lo esfumó: no hay una segunda nube ni otro sonido)
            bool vanish = grandpa != null && grandpa.gameObject.activeSelf;
            if (vanish) Game.FX.SmokePuff(grandpa.transform.position + Vector3.up, 1.6f);
            if (grandpa != null) Destroy(grandpa.gameObject);
            if (kidnapper != null) Destroy(kidnapper.gameObject);
            if (vanish) Game.Audio?.Play("teleport", P.transform.position, 0.8f);
            P.AddSpirit(60f);
        }

        void FinishIntro()
        {
            StartCoroutine(Cutscene(IntroOutro()));
        }

        IEnumerator IntroOutro()
        {
            parryTutorial = false;
            EndParryWatch();
            Game.UI.HideTutorial();   // el texto de la práctica no puede quedar encima del diálogo
            P.RestoreAll();
            yield return Say("intro_after_fight");
            Game.Save.SetFlag(Flags.IntroDone);
            var cp = Checkpoint.Get("cp_home");
            if (cp != null) cp.Activate(P, false);
            SaveSystem.Save();
            Game.UI.ShowTutorial($"Tip: {{Lock}} fija a un enemigo. Mantenelo apretado para soltarlo.");
            StartCoroutine(HideTutorialLater(5f));
        }

        IEnumerator HideTutorialLater(float s) { yield return new WaitForSecondsRealtime(s); Game.UI.HideTutorial(); }

        // ================================================================== tutoriales
        // Enseñan la pista que se ve a velocidad normal: el anillo (ensō) que se cierra alrededor del atacante.
        // Parry: primero guiado en cámara lenta (el anillo dorado se cierra despacio y se aprieta al cerrarse),
        // después a velocidad real; si falla dos seguidas, una ayuda a 0.6x. Mientras dura, el ninja está en modo
        // práctica (Enemy.SetParryPractice); si falla muchas seguidas igual se termina, para no trabar el prólogo.
        // Dash: con el sumo (un común), nunca congelando una pelea de jefe.
        const int GuidedParries = 2, RealtimeParries = 2, MaxGuidedAttempts = 4, MaxPracticeMisses = 8;
        int tutorialSlow = -1;
        int parryGuided, parryRealtime, parryMisses, parryAttempts;
        Enemy parryWatch, dashWatch;
        int parryWatchTell, dashWatchTell;
        bool parryWatching, parryLanded, waitingDash;

        bool ParryGuidedPhase => parryGuided < GuidedParries && parryAttempts < MaxGuidedAttempts;

        void Update()
        {
            if (P == null || Game.IsPaused) return;
            if (parryTutorial || parryWatching) TickParryTutorial();
            TickDashTutorial();

            // primer enemigo desequilibrado: explicar la ejecución
            if (!finisherTip && P.FinisherCandidate() != null && !Game.Save.HasFlag("tip_finisher"))
            {
                finisherTip = true;
                Game.Save.SetFlag("tip_finisher");
                Game.Time.SlowMotion(0.25f, 1.2f, 0.05f, 0.4f);
                Game.UI.ShowTutorial($"¡Está desequilibrado! Pegale {{Attack}} o EJECUTALO con {{Finisher}} (cuesta Espíritu, te cura)");
                StartCoroutine(HideTutorialLater(4.5f));
            }
        }

        void TickParryTutorial()
        {
            if (parryWatching)
            {
                // el golpe salió (lo desvió o no) o se cortó: fuera la cámara lenta y se cuenta
                bool over = !parryTutorial || Game.InCutscene || parryWatch == null || !parryWatch.InTell || parryWatch.TellId != parryWatchTell;
                if (!over) return;
                bool guided = ParryGuidedPhase;
                EndParryWatch();
                if (!parryTutorial) return;
                if (parryLanded) { if (guided) parryGuided++; else parryRealtime++; parryMisses = 0; }
                else parryMisses++;
                if (guided) parryAttempts++;
                if (parryRealtime >= RealtimeParries || parryMisses >= MaxPracticeMisses) { FinishParryTutorial(); return; }
                // el primer parry: qué se ganó (queda hasta el próximo golpe, mientras el ninja está abierto)
                if (parryLanded && guided && parryGuided == 1)
                {
                    Game.UI.ShowTutorial("Cada parry DESEQUILIBRA al enemigo: cuando termina su ataque queda abierto. ¡Castigalo!");
                    return;
                }
                ShowParryText(false);
                return;
            }
            if (Game.InCutscene) return;
            var enc = Encounter.Get("intro");
            if (enc == null) return;
            foreach (var e in enc.Members)
                // solo con un golpe desviable que de verdad llega (zona/alcance real): si no, se enseña mal
                if (e != null && e.IsAlive && e.InTell && e.StepKind != AttackKind.Unblockable && e.StrikeCanReach(P.transform.position, P.Radius + 0.3f))
                {
                    parryWatching = true;
                    parryLanded = false;
                    parryWatch = e;
                    parryWatchTell = e.TellId;
                    bool assist = !ParryGuidedPhase && parryMisses >= 2;
                    if (ParryGuidedPhase)
                    {
                        // se congela un segundo al aparecer el anillo (para leer) y sigue en cámara lenta: el anillo
                        // se ve cerrarse despacio y se aprieta en el cierre, igual que después a velocidad real
                        Game.Time.SlowMotion(0.03f, 1f, 0.05f, 0.3f);
                        tutorialSlow = Game.Time.SlowMotion(0.2f, 30f, 0.05f, 0.1f);
                    }
                    else if (assist) tutorialSlow = Game.Time.SlowMotion(0.6f, 30f, 0.05f, 0.1f);
                    ShowParryText(true);
                    break;
                }
        }

        void ShowParryText(bool attacking)
        {
            const string k = "{Parry}";   // la UI la dibuja con la tecla del dispositivo de ese momento
            if (ParryGuidedPhase)
            {
                if (attacking)
                    Game.UI.ShowTutorial(parryMisses > 0
                        ? $"Esperá a que el anillo dorado se cierre del todo y recién ahí presioná {k}"
                        : $"Mirá el anillo dorado: cuando se cierre, presioná {k} (Parry)");
                else Game.UI.HideTutorial();
                return;
            }
            // práctica a velocidad real: el texto queda hasta lograrlo
            Game.UI.ShowTutorial($"Ahora a velocidad real: {k} justo cuando se cierra el anillo dorado  ({parryRealtime}/{RealtimeParries})");
        }

        void EndParryWatch()
        {
            parryWatching = false;
            parryWatch = null;
            if (tutorialSlow >= 0) { Game.Time.CancelSlowMotion(tutorialSlow); tutorialSlow = -1; }
        }

        void FinishParryTutorial()
        {
            parryTutorial = false;
            Game.Save.SetFlag("tip_parry_done");
            var enc = Encounter.Get("intro");
            if (enc != null) foreach (var m in enc.Members) if (m != null) m.SetParryPractice(false);
            Game.UI.ShowTutorial("Parry cuando se cierra el anillo dorado y, cuando quede abierto, castigalo. ¡Terminá la pelea!");
            StartCoroutine(HideTutorialLater(4.5f));
        }

        void TickDashTutorial()
        {
            if (waitingDash)
            {
                // la cámara lenta sigue hasta que sale el golpe (no se corta al apretar: el dash también se ve lento)
                bool over = Game.InCutscene || dashWatch == null || !dashWatch.InTell || dashWatch.TellId != dashWatchTell;
                if (!over) return;
                waitingDash = false;
                dashWatch = null;
                if (tutorialSlow >= 0) { Game.Time.CancelSlowMotion(tutorialSlow); tutorialSlow = -1; }
                Game.UI.HideTutorial();
                return;
            }
            if (Game.Save.HasFlag(Flags.DashUnlocked) || Game.InCutscene || Game.Combat == null) return;
            foreach (var e in Game.Combat.Engaged)
            {
                // solo imparables que pueden conectar (carril hacia Kaito, Kaito dentro del pisotón)
                if (e == null || !e.InTell || e.StepKind != AttackKind.Unblockable || !e.StrikeCanReach(P.transform.position, P.Radius)) continue;
                const string k = "{Dash}";
                if (e is Boss)
                {
                    // pelea de jefe sin el dash todavía: se habilita sin congelar la pelea
                    Game.Save.SetFlag(Flags.DashUnlocked);
                    P.AddSpirit(40f);
                    Game.UI.ShowTutorial($"Anillo ROJO: no se puede desviar. Esquivá con {k} cuando se cierre (DASH MÁGICO)");
                    StartCoroutine(HideTutorialLater(4f));
                    return;
                }
                // con el sumo, igual que el parry guiado: se congela un segundo al aparecer el anillo rojo (para leer) y
                // sigue en cámara lenta hasta el golpe. Antes arrancaba con el anillo casi cerrado y se cortaba al
                // apretar: el que apretaba al terminar de leer esquivaba antes de tiempo y comía la embestida
                Game.Save.SetFlag(Flags.DashUnlocked);
                P.AddSpirit(40f);
                waitingDash = true;
                dashWatch = e;
                dashWatchTell = e.TellId;
                Game.Time.SlowMotion(0.03f, 1f, 0.05f, 0.3f);
                tutorialSlow = Game.Time.SlowMotion(0.2f, 30f, 0.05f, 0.1f);
                Game.UI.ShowTutorial($"¡Anillo ROJO: no se puede desviar! Esquivá hacia un costado con {k} cuando se cierre (DASH MÁGICO, usa Espíritu)");
                return;
            }
        }

        void OnParry(bool perfect)
        {
            if (!parryWatching) return;
            parryLanded = true;
            Game.UI.ShowCallout(perfect ? "¡Parry perfecto!" : "¡Parry!", UIFactory.Gold);
        }

        // ================================================================== triggers del mapa
        /// <summary>
        /// Encuentros que la historia necesita ganados para seguir: la muralla (WallSeal pide enc_wall para abrir el sello)
        /// y el sumo (enc_done_sumo da el dash y las habilidades). Encounter los arranca con su radio entero aunque
        /// estén en su idle ambiental: el resto de los campamentos son de paso y esperan a que uno note a Kaito.
        /// </summary>
        public static bool GatesProgress(string encounterId) => encounterId == "wall" || encounterId == "sumo";

        public void OnTrigger(string id, StoryTrigger t)
        {
            if (!id.StartsWith("enc_done_")) Game.Save.SetFlag("trig_" + id);
            switch (id)
            {
                case "enc_done_intro": FinishIntro(); break;
                case "fields": StartCoroutine(Cutscene(Say("fields"), false)); break;
                case "forest_reveal": StartCoroutine(Cutscene(ForestReveal())); break;
                case "wall_guards":
                    StartCoroutine(Cutscene(Say("wall_guards"), false));
                    break;
                // el portón ya no se abre solo: tiene un sello de sombra que Kaito abre con la bandana (StoryDirector.Wall)
                case "enc_done_wall": StartCoroutine(Cutscene(WallGuardsDown())); break;
                case "garden": StartCoroutine(Cutscene(Say("garden"), false)); break;
                case "sumo_intro":
                {
                    // si el sumo ya cayó (se entró por el costado y se peleó antes del disparador) no hay
                    // provocación que mostrar: solo se asegura que el encuentro esté activo
                    var enc = Encounter.Get("sumo");
                    bool liveSumo = false;
                    if (enc != null) foreach (var m in enc.Members) if (m != null && m.IsAlive && m.config.id.StartsWith("sumo")) liveSumo = true;
                    if (liveSumo) StartCoroutine(Cutscene(SumoIntro()));
                    else enc?.Activate();
                    break;
                }
                case "enc_done_sumo": StartCoroutine(Cutscene(AbilitiesUnlock())); break;
                case "dojo_gate":
                    Game.Save.SetFlag(Flags.DojoGateSeen);
                    StartCoroutine(Cutscene(DojoGateFirstLook()));
                    break;
            }
            UpdateObjective();
        }

        IEnumerator ForestReveal()
        {
            Vector3 a = PointPos("forest_kidnap_a", P.transform.position + new Vector3(0, 0, 18));
            Vector3 b = PointPos("forest_kidnap_b", a + new Vector3(0, 0, 14));
            // el ninja sigue arrastrando al abuelo (Dragged), de costado y del lado del ninja como en el prólogo
            var grandpa = NPC.Spawn("kidnap", a, Quaternion.LookRotation((b - a).Flat().normalized + Vector3.forward * 0.001f), null);
            grandpa.Drag(b);
            int shot = Game.Camera.PlayFollowShot(grandpa.transform, new Vector3(5.5f, 3.6f, -5f), 0.7f, 34f, 0f, 1.2f, 1.2f, true);
            yield return new WaitForSecondsRealtime(1.5f);
            yield return Say("forest_reveal");
            yield return new WaitForSecondsRealtime(1.2f);
            // (si llegó a 'b' antes, NPC.Arrive ya lo esfumó)
            if (grandpa.gameObject.activeSelf) Game.FX.SmokePuff(grandpa.transform.position + Vector3.up, 1.5f);
            Destroy(grandpa.gameObject);
            Game.Camera.CancelShot(shot);
            Game.Save.SetFlag(Flags.ForestSeen);
        }

        IEnumerator SumoIntro()
        {
            var enc = Encounter.Get("sumo");
            Enemy sumo = null;
            if (enc != null) foreach (var m in enc.Members) if (m != null && m.IsAlive && m.config.id.StartsWith("sumo")) sumo = m;
            int shot = -1;
            if (sumo != null)
            {
                sumo.EnterScripted();
                sumo.ScriptedFace(P.transform.position);
                sumo.ScriptedPlay("Spotted");
                shot = Game.Camera.PlayBossIntroShot(sumo.transform, 2.6f, 3.5f);
            }
            yield return new WaitForSecondsRealtime(1.2f);
            yield return Say("sumo_intro");
            if (shot >= 0) Game.Camera.CancelShot(shot);
            if (sumo != null) sumo.ExitScripted(true);
            enc?.Activate();
        }

        IEnumerator AbilitiesUnlock()
        {
            Game.Save.SetFlag(Flags.AbilitiesUnlocked);
            Game.Save.SetFlag(Flags.DashUnlocked);
            P.AddSpirit(100f);
            Game.FX.SealGlow(P.transform.position + Vector3.up);
            int shot = Game.Camera.PlayAbilityShot(P.transform, CameraDirector.AbilityShot.LowOrbit, 2.5f);
            yield return new WaitForSecondsRealtime(0.8f);
            yield return Say("abilities");
            Game.Camera.CancelShot(shot);
            Game.UI.ShowTutorial($"{{Ability1}} Corte del Viento (35)   ·   {{Ability2}} Torbellino de Hojas (30)");
            StartCoroutine(HideTutorialLater(6f));
        }

        // ================================================================== presentación de la cascada
        public const string FallsSeenFlag = "falls_seen";

        void OnZoneEntered(Zone z)
        {
            UpdateObjective();   // el objetivo depende de la zona (en la tierra de un guardián dice a quién vencer)
            if (z.id != "lago_cascada" || Game.InCutscene || Game.Save.HasFlag(FallsSeenFlag)) return;
            var f = KohanFalls.Instance;
            if (f == null || P == null || (Game.Combat != null && Game.Combat.InCombat)) return;
            Game.Save.SetFlag(FallsSeenFlag);
            StartCoroutine(Cutscene(FallsReveal(f), false));
        }

        /// <summary>
        /// La primera vez que se llega a la Cascada Kohan. Con la cámara de juego (40-48° de inclinación, FOV 30) solo
        /// entra el pie de las cortinas: 42 m de caída quedan siempre arriba del cuadro. Una grúa corta, mientras sale
        /// el título de la zona, arranca baja sobre la plataforma mirando el hervor del pozo y sube la mirada hasta el
        /// labio de la cortina central. Sin franjas negras: el título de la zona va arriba y lo tapaban.
        /// </summary>
        IEnumerator FallsReveal(KohanFalls f)
        {
            Vector3 arena = f.ArenaCenter, plunge = f.PlungeCenter, lip = f.LipCenter;
            Vector3 toFalls = (plunge - arena).Flat().normalized;
            Vector3 side = Vector3.Cross(Vector3.up, toFalls);
            float deck = f.DeckY;
            const float D = 4.8f;
            int shot = Game.Camera.PlayShot(t =>
            {
                float k = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(t / D));
                // la mirada espera medio segundo en el pozo y recién ahí sube
                float tilt = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01((t - 0.5f) / (D - 1.2f)));
                Vector3 pos = arena - toFalls * Mathf.Lerp(3f, 8.5f, k) + side * Mathf.Lerp(-3.5f, 1.5f, k);
                pos.y = deck + Mathf.Lerp(1.6f, 4.2f, k);
                // termina con el labio a un cuarto del borde de arriba: mirándolo de frente, medio cuadro era cielo negro
                Vector3 look = Vector3.Lerp(plunge + Vector3.up * 3f, lip + Vector3.down * 13f, tilt);
                return new Pose(pos, Quaternion.LookRotation(look - pos));
            }, () => 50f, 1.1f, D, 1.1f);
            yield return new WaitForSecondsRealtime(D);
            Game.Camera.CancelShot(shot);
        }

        // ================================================================== jefes
        public void BossIntro(BossArena arena)
        {
            StartCoroutine(Cutscene(BossIntroRoutine(arena)));
        }

        IEnumerator BossIntroRoutine(BossArena arena)
        {
            var b = arena.Boss;
            if (b == null) yield break;
            b.EnterScripted();
            b.ScriptedFace(P.transform.position);
            // Kokuyō tiene su propia presentación (y su versión corta para los reintentos)
            if (b is KokuyoBoss k) { yield return KokuyoIntro(k); yield break; }
            // Chikuō también (espera con las manos en la espalda; en los reintentos, el saludo corto con una frase)
            if (b is BambooMasterBoss master)
            {
                // bandera propia: el bossId sigue siendo "ozeki" (partidas, sello) y una partida que vio al sumo de antes
                // tenía boss_seen_ozeki, así que nunca veía la presentación ni la historia de Chikuō
                bool first = !Game.Save.HasFlag(BossSeenFlag("chikuo"));
                yield return master.Presentation(P, first);
                if (first) { Game.Save.SetFlag(BossSeenFlag("chikuo")); SaveSystem.Save(); }
                yield return new WaitForSecondsRealtime(0.3f);
                b.ExitScripted(false);
                b.BeginFight();
                yield break;
            }
            // reintento: la presentación entera (~6 s más el diálogo) solo la primera vez
            if (Game.Save.HasFlag(BossSeenFlag(b.bossId))) { yield return BossReintro(b); yield break; }
            // Mizuchi tiene su propia presentación (sale del pozo de la cascada): la toma, el título y el diálogo son suyos
            if (b is MizuchiBoss koi)
            {
                Game.Audio?.StopMusic(1.5f);
                yield return koi.Presentation(P);
                Game.Save.SetFlag(BossSeenFlag(b.bossId));
                SaveSystem.Save();
                yield return new WaitForSecondsRealtime(0.3f);
                b.ExitScripted(false);
                b.BeginFight();
                yield break;
            }
            Game.Audio?.StopMusic(1.5f);
            int shot = Game.Camera.PlayBossIntroShot(b.transform, b.config.height * b.config.scale, 4f);
            yield return new WaitForSecondsRealtime(0.8f);
            b.ScriptedPlay(b.introAnim, 0.2f);
            Game.Audio?.Play("boss_roar", b.transform.position, 1f);
            Game.Camera.Shake(0.35f);
            Game.UI.ShowBossTitle(b.title, b.subtitle);
            yield return new WaitForSecondsRealtime(2.6f);
            yield return Say(b.bossId + "_intro");
            Game.Camera.CancelShot(shot);
            Game.Save.SetFlag(BossSeenFlag(b.bossId));
            // se guarda ya: entre la presentación y una muerte nada más guarda (reaparecer no guarda y el santuario de la
            // entrada ya era el punto de reaparición), y al salir y Continuar se repetía la presentación entera
            SaveSystem.Save();
            yield return new WaitForSecondsRealtime(0.3f);
            b.ExitScripted(false);
            b.BeginFight();
        }

        /// <summary>
        /// Ya vio la presentación de este jefe (se reintenta después de morir): las presentaciones propias de un jefe
        /// también lo pueden usar para su versión corta.
        /// </summary>
        public static string BossSeenFlag(string bossId) => "boss_seen_" + bossId;

        /// <summary>
        /// Re-presentación de 1.2 s: corte directo al jefe, rugido y a pelear (sin título ni diálogo). Corte y no fundido:
        /// fundir 20 m en 0.35 s y volver en 0.5 s eran dos latigazos de cámara en cada reintento; la vuelta (0.7 s) es la
        /// de cualquier plano que devuelve el control.
        /// </summary>
        IEnumerator BossReintro(Boss b)
        {
            Game.Audio?.StopMusic(0.6f);
            int shot = Game.Camera.PlayBossIntroShot(b.transform, b.config.height * b.config.scale, 1.2f, 0f, 0.7f);
            b.ScriptedPlay(b.introAnim, 0.2f);
            Game.Audio?.Play("boss_roar", b.transform.position, 0.8f);
            Game.Camera.Shake(0.25f);
            yield return new WaitForSecondsRealtime(1.2f);
            Game.Camera.CancelShot(shot);
            b.ExitScripted(false);
            b.BeginFight();
        }

        void OnBossDefeated(Boss b)
        {
            foreach (var a in Game.World.Arenas) if (a.Boss == b) a.OnBossDefeated();
            if (b.bossId == "kage") StartCoroutine(Ending());
            else if (b.bossId != "mizuchi") Game.UI?.ShowToast($"{b.title} derrotado", UIFactory.Gold, 2.5f);   // Mizuchi: "liberado", en su final
            UpdateObjective();
        }

        public void OnSealObtained(SealId seal)
        {
            StartCoroutine(Cutscene(SealRoutine(seal), false));
        }

        IEnumerator SealRoutine(SealId seal)
        {
            string id = seal == SealId.Montana ? "seal_mountain" : seal == SealId.Lago ? "seal_lake" : "seal_bamboo";
            Game.UI.ShowSealObtained(seal);
            P.RestoreAll();
            yield return new WaitForSecondsRealtime(0.6f);
            yield return Say(id);
            if (Game.Save.SealCount >= 3) Game.UI.ShowToast("¡Los tres sellos! Volvé a la puerta del dojo", UIFactory.Gold, 3f);
            SaveSystem.Save();
        }

        // ================================================================== muerte / viaje
        void OnPlayerDied()
        {
            if (deathRoutine != null) StopCoroutine(deathRoutine);
            deathRoutine = StartCoroutine(DeathRoutine());
        }

        // Muerte -> de vuelta a jugar en ~3.6 s (antes ~6.4): 0.8 s de caída en cámara lenta, el panel de muerte con su
        // entrada entera pero sin la espera larga, el fundido a negro y la reaparición en 0.8 s. Morir contra un jefe es
        // parte de aprenderlo: lo caro tiene que ser la pelea, no la espera.
        const float DeathFall = 0.8f, DeathHold = 0.2f, RespawnFadeIn = 0.8f;

        IEnumerator DeathRoutine()
        {
            EndParryWatch();
            waitingDash = false; dashWatch = null;
            Game.UI.HideTutorial();
            Game.Audio?.PlayMusic("gameover", 1f, loop: false);
            yield return new WaitForSecondsRealtime(DeathFall);
            yield return ShortDeathScreen();
            Game.Time.ClearSlowMotion();
            Game.World.ResetAfterDeath();
            P.RespawnAt(Game.World.RespawnPoint(), Game.World.RespawnRotation());
            Zone.ForceRefresh();
            Game.Audio?.ResumeExplore(1.5f);
            yield return Game.UI.Fade(0f, RespawnFadeIn);
            deathRoutine = null;
        }

        /// <summary>
        /// El panel de muerte de la UI (entrada 1.2 s + espera 1.6 s + fundido 0.6 s) recorrido acá con la espera
        /// acortada a DeathHold: el panel y su animación quedan como los diseñó la UI.
        /// </summary>
        IEnumerator ShortDeathScreen()
        {
            var it = Game.UI.DeathScreen();
            while (it.MoveNext())
            {
                if (it.Current is WaitForSecondsRealtime w) w.waitTime = Mathf.Min(w.waitTime, DeathHold);
                yield return it.Current;
            }
        }

        public void TravelTo(string checkpointId, bool fx)
        {
            StartCoroutine(Cutscene(TravelRoutine(checkpointId, fx), false));
        }

        IEnumerator TravelRoutine(string id, bool fx)
        {
            if (fx) { Game.FX.PortalBurst(P.transform.position + Vector3.up); Game.Audio?.Play("portal", P.transform.position, 1f); }
            yield return Game.UI.Fade(1f, 0.7f);
            var cp = Checkpoint.Get(id);
            if (cp != null)
            {
                P.Teleport(cp.spawnPoint.position, cp.spawnPoint.rotation);
                cp.Activate(P, false);
            }
            Zone.ForceRefresh();
            yield return new WaitForSecondsRealtime(0.5f);
            yield return Game.UI.Fade(0f, 0.9f);
        }

        // cualquier flag puede cambiar el objetivo (antes solo los de jefes y el dojo: "Desatá la cinta de la
        // guadaña" quedaba trabado después de desatarla hasta que otro evento lo pisaba). SetObjective ignora
        // el texto repetido, así que refrescar de más no anima nada
        void OnFlag(string f) => UpdateObjective();
    }

    /// <summary>La guadaña del abuelo: al desatar la cinta, Kaito obtiene la bandana y la katana.</summary>
    public class BandanaScythe : Interactable
    {
        public override void Interact(PlayerController p)
        {
            Game.Save.SetFlag(Flags.KatanaObtained);
            enabled = false;
        }
    }
}
