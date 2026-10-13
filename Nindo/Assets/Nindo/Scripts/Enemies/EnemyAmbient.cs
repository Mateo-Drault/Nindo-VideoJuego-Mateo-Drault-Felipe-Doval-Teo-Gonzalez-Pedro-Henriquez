using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

namespace Nindo
{
    /// <summary>
    /// Lo que hacen los enemigos ANTES de que empiece la pelea, para que no estén parados esperando (ítem 5): los
    /// ninjas meditan sentados en una roca, practican de a dos, miran el filo o se estiran; el sumo duerme sentado o hace
    /// el shiko. Lo notan a Kaito recién de cerca (NoticeRadius: el encuentro no arranca por el radio de su centro, que caía
    /// fuera de la pantalla) y se sobresaltan con su clip (AmbientAlert desde los sentados, el Spotted de siempre desde los
    /// parados) antes de perseguir: nunca atacan desde la pose ambiental. El sumo dormido tarda un poco más en despertarse;
    /// un golpe lo despierta en el acto y apura el sobresalto (así los golpes gratis son los de un combo). Si Kaito muere,
    /// ResetEncounter los devuelve a lo que estaban haciendo; si se escapa, al volver a su lugar lo retoman (Resume).
    /// Se reparte por encuentro (Setup, desde Encounter.SpawnAll) según quiénes son, distinto en cada encuentro pero
    /// siempre igual en el mismo (sale del id). Los clips y sus números vienen de Tools/Blender/anim/team_ambient.py;
    /// si un controller no trae el estado, ese enemigo se queda con el Idle de siempre.
    /// </summary>
    public class EnemyAmbient : MonoBehaviour
    {
        public enum Activity { Meditate, Spar, Inspect, Sleep, Shiko, Stretch }

        // ---- números de team_ambient.py (marco de autoría: frente -Y, izquierda +X -> Unity: x = -x, y = z, z = -y)
        const string RockId = "rock_small_a";
        /// <summary>rock_small_a (0.70 x 0.30 x 0.64 m) escalada a 0.91 x 0.40 x 0.72: la cara de arriba a ROCK_TOP.</summary>
        static readonly Vector3 RockScale = new Vector3(1.3f, 1.32f, 1.12f);
        /// <summary>El collider de rock_small_a en el PropsManifest (antes de escalar).</summary>
        static readonly Vector3 RockBoxCenter = new Vector3(-0.008f, 0.145f, -0.004f), RockBoxSize = new Vector3(0.594f, 0.289f, 0.545f);
        /// <summary>Centro de la roca detrás del transform (SEAT_BACK): el salto del despertar cae en su lugar.</summary>
        const float SeatBack = 0.72f;
        /// <summary>Dónde está el cuerpo sentado detrás del transform (m): ahí van la cápsula y el punto donde le entran los
        /// golpes hasta que se para (con la cápsula en el transform Kaito chocaba con el aire delante del que medita).</summary>
        const float MeditateBody = 0.6f, SleepBody = 0.3f;
        /// <summary>Distancia entre los dos que practican (SPAR_GAP): a esa distancia se tocan las hojas.</summary>
        const float SparGap = 1.70f;
        /// <summary>Dónde se tocan las hojas, en el espacio del que corta (spar_geometry).</summary>
        static readonly Vector3 ClashLocal = new Vector3(-0.35f, 1.435f, 1.325f);
        const float ClashA = 15f / 96f, ClashB = 63f / 96f;          // SPAR_CLASH: corta A, corta B
        const float Snore = 52f / 120f;                              // SLEEP_SNORE
        const float StompR = 47f / 150f, StompL = 122f / 150f;       // SHIKO_STOMPS
        /// <summary>Cuadro (s) del despertar en que ya está parado en su lugar y puede girar hacia Kaito ('land').</summary>
        const float MeditateLand = 20f / 30f, SleepLand = 55f / 30f;
        const string AlertState = "AmbientAlert";
        /// <summary>Cruce de entrada al despertar y el que Enemy usa al salir del Alert a la locomoción.</summary>
        const float WakeFade = 0.12f, StandFade = 0.2f;
        /// <summary>Hasta dónde se reparte la reacción de los del mismo encuentro (no se sobresaltan todos en el mismo
        /// cuadro) y cuánto más tarda el sumo dormido.</summary>
        const float WakeSpread = 0.3f, SleepExtra = 0.35f;
        /// <summary>Un golpe en pleno sobresalto lo apura a este ritmo: el sumo dormido queda en guardia a los 0.9 s (le entra
        /// el combo de Kaito, 3 cortes), el ninja a los 0.5 (2 cortes). Con el ritmo normal le entraban 5-6 sin respuesta.</summary>
        const float HurrySpeed = 2.2f;
        /// <summary>Lo nota a Kaito a esta distancia (m): lo bastante adentro de la pantalla (el piso visible delante de Kaito
        /// llega a ~10 m con la cámara del juego) para que lo que hace se vea un rato; dormido, más cerca.</summary>
        const float NoticeAwake = 7f, NoticeAsleep = 5f;
        /// <summary>Cruce al retomar lo que hacía (volvió a su lugar sin pelea): parado y sentado.</summary>
        const float ResumeFade = 0.5f, ResumeSeatFade = 0.8f;
        const float PairMaxDistance = 14f, SoundRange = 20f;
        /// <summary>Encuentros que maneja la historia: el ninja del prólogo es parte del secuestro (StoryDirector.Intro).</summary>
        static readonly string[] ScriptedEncounters = { "intro" };

        Enemy enemy;
        Activity activity;
        EnemyAmbient partner;
        bool leader, pending, holding, waking, wakePlayed, resuming;
        string loopState, playing;
        float phase, wakeDelay, wakeAt, wakeStart, turnAt, hurry = 1f, lastNorm = -1f;
        Transform head;
        CapsuleCollider capsule;
        Vector3 capsuleCenter;
        bool seatShift;

        /// <summary>Hay una pose ambiental (el loop o su despertar): Enemy no vuelve a la locomoción.</summary>
        public bool HoldsPose => holding;
        /// <summary>Se está sobresaltando: el sobresalto es la reacción, un golpe no lo corta con el Hit.</summary>
        public bool Waking => holding && waking;
        /// <summary>Puede girar hacia Kaito (sentado en la roca o en el piso, el giro lo sacaría de su lugar).</summary>
        public bool CanTurn => !Waking || Time.time >= turnAt;
        /// <summary>Sentado todavía (meditando, dormido, o despertándose antes de pararse en su lugar).</summary>
        public bool SeatedNow => holding && Seated && (!waking || Time.time < turnAt);
        /// <summary>Dónde le entran los golpes (Enemy.HurtCenter): el cuerpo sentado está detrás del transform.</summary>
        public Vector3 HurtPoint => SeatedNow ? transform.position - transform.forward * (BodyBack * enemy.config.scale) : transform.position;
        /// <summary>Distancia a la que nota a Kaito mientras está en lo suyo (Enemy.TickIdle).</summary>
        public float NoticeRadius => activity == Activity.Sleep ? NoticeAsleep : NoticeAwake;
        public Activity Current => activity;

        float BodyBack => activity == Activity.Meditate ? MeditateBody : activity == Activity.Sleep ? SleepBody : 0f;

        /// <summary>Alguno del encuentro sigue en su idle ambiental sin haber notado a Kaito: el encuentro espera a que lo note
        /// (Encounter.Update no lo activa por la distancia a su centro).</summary>
        public static bool AnyHolding(IReadOnlyList<Enemy> members)
        {
            for (int i = 0; i < members.Count; i++)
            {
                var m = members[i];
                if (m != null && m.IsAlive && m.Ambient != null && m.Ambient.holding && !m.Ambient.waking) return true;
            }
            return false;
        }

        // ================================================================== reparto
        struct Plan { public Activity act; public bool on; public int mate; public Vector3 pos; public Quaternion rot; }

        /// <summary>Lo que hacen los ninjas sueltos, en el orden en que se reparten (empieza en uno distinto por encuentro).</summary>
        static readonly Activity[] Singles = { Activity.Meditate, Activity.Inspect, Activity.Stretch };

        /// <summary>
        /// Elige qué hace cada uno (de los datos de los spawns, así sale igual aunque el encuentro ya esté ganado: la roca
        /// del que meditaba sigue ahí) y, si los enemigos existen, se lo asigna y acomoda a las parejas.
        /// </summary>
        public static void Setup(Encounter enc, IReadOnlyList<(string archetype, Vector3 pos, Quaternion rot)> spawns, IReadOnlyList<Enemy> members)
        {
            if (enc == null || spawns == null || spawns.Count == 0 || System.Array.IndexOf(ScriptedEncounters, enc.id) >= 0) return;
            int n = spawns.Count;
            var plan = new Plan[n];
            var ninjas = new List<int>();
            for (int i = 0; i < n; i++)
            {
                plan[i] = new Plan { mate = -1, pos = Ground(spawns[i].pos), rot = spawns[i].rot };
                string a = spawns[i].archetype;
                if (EnemyFactory.IsBoss(a)) continue;
                string c = EnemyFactory.CharacterFor(a);
                if (c == "ninja") ninjas.Add(i);
                else if (c == "sumo")
                {
                    // el sumo del jardín provoca a Kaito en una cinemática (StoryDirector.SumoIntro): parado, haciendo el
                    // shiko, la provocación entra sin levantarlo del piso
                    plan[i].act = enc.id == "sumo" || Hash01(enc.id, i, 1) >= 0.6f ? Activity.Shiko : Activity.Sleep;
                    plan[i].on = true;
                }
            }
            PairUp(enc.id, ninjas, plan);
            int singles = 0, start = (int)(Hash01(enc.id, 0, 2) * Singles.Length);
            foreach (int i in ninjas)
            {
                if (plan[i].mate >= 0) continue;
                // uno distinto por encuentro y después rotando: ni todos meditando ni todos mirando el filo
                var act = Singles[(start + singles) % Singles.Length];
                singles++;
                if (act == Activity.Meditate && !RockRoom(plan[i].pos, plan[i].rot)) act = Activity.Inspect;
                plan[i].act = act;
                plan[i].on = true;
            }
            for (int i = 0; i < n; i++)
                if (plan[i].on && plan[i].act == Activity.Meditate) SpawnRock(enc.transform, plan[i].pos, plan[i].rot, enc.id, i);
            if (members == null || members.Count != n) return;
            var made = new EnemyAmbient[n];
            for (int i = 0; i < n; i++)
            {
                var e = members[i];
                if (!plan[i].on || e == null) continue;
                if (plan[i].act == Activity.Spar) Move(e, plan[i].pos, plan[i].rot);
                var amb = e.gameObject.AddComponent<EnemyAmbient>();
                amb.Init(e, plan[i].act, Hash01(enc.id, i, 3), Hash01(enc.id, i, 4) * WakeSpread);
                made[i] = amb;
            }
            for (int i = 0; i < n; i++)
            {
                int j = plan[i].mate;
                if (made[i] == null || j < 0 || made[j] == null) { if (made[i] != null && plan[i].act == Activity.Spar) made[i].Unpair(); continue; }
                made[i].partner = made[j];
                made[i].leader = i < j;
                made[i].loopState = i < j ? "IdleSparA" : "IdleSparB";
                // la pareja practica a compás y se sobresalta junta
                if (i > j) { made[i].phase = made[j].phase; made[i].wakeDelay = made[j].wakeDelay; }
            }
        }

        /// <summary>Junta de a dos a los ninjas más cercanos (según el encuentro: practicar era lo de casi todos) y les busca
        /// lugar enfrentados de perfil para la cámara; si no entran, quedan sueltos.</summary>
        static void PairUp(string id, List<int> ninjas, Plan[] plan)
        {
            int pairs = 0;
            while (true)
            {
                int bi = -1, bj = -1;
                float best = PairMaxDistance * PairMaxDistance;
                for (int a = 0; a < ninjas.Count; a++)
                    for (int b = a + 1; b < ninjas.Count; b++)
                    {
                        int i = ninjas[a], j = ninjas[b];
                        if (plan[i].mate != -1 || plan[j].mate != -1) continue;
                        float d = (plan[i].pos - plan[j].pos).Flat().sqrMagnitude;
                        if (d < best) { best = d; bi = i; bj = j; }
                    }
                if (bi < 0 || Hash01(id, bi, 5) >= (pairs == 0 ? 0.5f : 0.35f)) return;
                if (!PairSpot(plan[bi].pos, plan[bj].pos, out var pa, out var pb))
                {
                    // sin lugar: los dos quedan sueltos (mate -2: no se los vuelve a probar)
                    plan[bi].mate = plan[bj].mate = -2;
                    continue;
                }
                plan[bi].mate = bj; plan[bj].mate = bi;
                plan[bi].act = plan[bj].act = Activity.Spar;
                plan[bi].on = plan[bj].on = true;
                plan[bi].pos = pa; plan[bj].pos = pb;
                plan[bi].rot = Quaternion.LookRotation((pb - pa).Flat());
                plan[bj].rot = Quaternion.LookRotation((pa - pb).Flat());
                pairs++;
            }
        }

        /// <summary>
        /// Lugar para la pareja: a SparGap uno del otro alrededor del punto medio de sus spawns, sobre la línea
        /// horizontal de la pantalla (la cámara del juego no gira: de perfil se lee el intercambio) o, si no entra, girada
        /// de a poco. Los dos sobre el NavMesh, al mismo alto (las hojas tienen que encontrarse) y con camino libre entre ellos.
        /// </summary>
        static bool PairSpot(Vector3 a, Vector3 b, out Vector3 pa, out Vector3 pb)
        {
            pa = pb = default;
            Vector3 mid = Ground((a + b) * 0.5f);
            for (int k = 0; k < SparAngles.Length; k++)
            {
                Vector3 axis = Quaternion.Euler(0f, SparAngles[k], 0f) * Vector3.right * (SparGap * 0.5f);
                if (!OnFlat(mid - axis, mid.y, out pa) || !OnFlat(mid + axis, mid.y, out pb)) continue;
                if (NavMesh.Raycast(pa, pb, out _, NavMesh.AllAreas)) continue;
                return true;
            }
            return false;
        }

        static readonly float[] SparAngles = { 0f, 25f, -25f, 50f, -50f, 90f };

        static bool OnFlat(Vector3 p, float y, out Vector3 at)
        {
            at = p;
            if (!NavMesh.SamplePosition(p, out var hit, 0.3f, NavMesh.AllAreas) || Mathf.Abs(hit.position.y - y) > 0.15f) return false;
            at = hit.position;
            return NavMesh.FindClosestEdge(at, out var edge, NavMesh.AllAreas) && edge.distance > 0.6f;
        }

        /// <summary>
        /// Hay lugar para la roca detrás del que medita: piso parejo con el suyo, sobre el NavMesh y lejos de un borde (no
        /// en un pasillo angosto: una roca nueva no puede tapar un camino), y nada ahí (otra roca, una pared, un prop).
        /// </summary>
        static bool RockRoom(Vector3 pos, Quaternion rot)
        {
            Vector3 c = RockCenter(pos, rot);
            if (!Physics.Raycast(c + Vector3.up * 2f, Vector3.down, out var hit, 4f, GroundMask, QueryTriggerInteraction.Ignore)) return false;
            if (Mathf.Abs(hit.point.y - pos.y) > 0.12f) return false;
            if (!NavMesh.SamplePosition(hit.point, out var nh, 0.3f, NavMesh.AllAreas)) return false;
            if (!NavMesh.FindClosestEdge(nh.position, out var edge, NavMesh.AllAreas) || edge.distance < 0.9f) return false;
            Vector3 half = Vector3.Scale(RockBoxSize, RockScale) * 0.5f;
            return !Physics.CheckBox(hit.point + Vector3.up * (0.08f + half.y), half, rot, GroundMask, QueryTriggerInteraction.Ignore);
        }

        static Vector3 RockCenter(Vector3 pos, Quaternion rot) => pos - rot * Vector3.forward * SeatBack;

        static void SpawnRock(Transform parent, Vector3 pos, Quaternion rot, string id, int i)
        {
            var model = Game.Content != null ? Game.Content.Prop(RockId) : null;
            if (model == null) return;
            Vector3 c = RockCenter(pos, rot);
            if (Physics.Raycast(c + Vector3.up * 2f, Vector3.down, out var hit, 4f, GroundMask, QueryTriggerInteraction.Ignore)) c.y = hit.point.y;
            // apenas girada (±6°): más, la esquina de adelante se mete bajo el talón de la guardia del despertar
            var r = Instantiate(model, c, rot * Quaternion.Euler(0f, (Hash01(id, i, 6) - 0.5f) * 12f, 0f), parent);
            r.name = RockId + "_seat";
            r.transform.localScale = Vector3.Scale(r.transform.localScale, RockScale);
            var box = r.AddComponent<BoxCollider>();
            box.center = RockBoxCenter;
            box.size = RockBoxSize;
            // aparece después de hornear el NavMesh (WorldBuilder): sin obstáculo los enemigos la atravesaban persiguiendo a
            // Kaito o volviendo a su lugar. Sin tallar: el lugar del que medita, 0.36 m adelante, sigue en el NavMesh
            var obs = r.AddComponent<NavMeshObstacle>();
            obs.shape = NavMeshObstacleShape.Box;
            obs.center = RockBoxCenter;
            obs.size = RockBoxSize;
            obs.carving = false;
        }

        static void Move(Enemy e, Vector3 p, Quaternion r)
        {
            var agent = e.GetComponent<NavMeshAgent>();
            if (agent != null && agent.isOnNavMesh) agent.Warp(p);
            else e.transform.position = p;
            e.transform.rotation = r;
        }

        static Vector3 Ground(Vector3 p) => NavMesh.SamplePosition(p, out var hit, 4f, NavMesh.AllAreas) ? hit.position : p;

        static int groundMask = -1;
        static int GroundMask { get { if (groundMask == -1) groundMask = LayerMask.GetMask("Default"); return groundMask; } }

        /// <summary>0..1 fijo por encuentro, enemigo y uso (FNV-1a: string.GetHashCode cambia entre ejecuciones).</summary>
        static float Hash01(string id, int i, int salt)
        {
            uint h = 2166136261u;
            for (int k = 0; k < id.Length; k++) { h ^= id[k]; h *= 16777619u; }
            h ^= (uint)(i * 92821 + salt * 68917); h *= 16777619u;
            h ^= h >> 15; h *= 2246822519u; h ^= h >> 13;
            return (h & 0xFFFFFF) / 16777216f;
        }

        // ================================================================== instancia
        void Init(Enemy e, Activity a, float ph, float delay)
        {
            enemy = e;
            activity = a;
            phase = ph;
            wakeDelay = delay + (a == Activity.Sleep ? SleepExtra : 0f);
            loopState = a switch
            {
                Activity.Meditate => "IdleMeditate",
                Activity.Spar => "IdleSparA",
                Activity.Inspect => "IdleInspect",
                Activity.Sleep => "IdleSleep",
                Activity.Stretch => "IdleStretch",
                _ => "IdleShiko",
            };
            e.Ambient = this;
            pending = true;
            holding = true;     // desde ya: Enemy.Update no lo devuelve a la locomoción antes del primer cuadro
            if (a == Activity.Sleep) head = FindDeep(e.transform, "Cabeza");
            capsule = e.GetComponent<CapsuleCollider>();
            if (capsule != null) capsuleCenter = capsule.center;
        }

        /// <summary>La pareja no consiguió compañero (encuentro a medias): mira el filo solo.</summary>
        void Unpair() { activity = Activity.Inspect; loopState = "IdleInspect"; }

        static Transform FindDeep(Transform t, string name)
        {
            if (t.name == name) return t;
            for (int i = 0; i < t.childCount; i++)
            {
                var r = FindDeep(t.GetChild(i), name);
                if (r != null) return r;
            }
            return null;
        }

        bool Seated => activity == Activity.Meditate || activity == Activity.Sleep;

        /// <summary>El loop de ahora: el que practicaba solo (el compañero murió y Kaito se escapó) mira el filo.</summary>
        string LoopNow => activity == Activity.Spar && (partner == null || partner.enemy == null || !partner.enemy.IsAlive) ? "IdleInspect" : loopState;

        /// <summary>El estado existe en el controller (y el despertar, si es sentado): si no, Idle de siempre.</summary>
        bool Usable => enemy != null && enemy.Anim.HasState(LoopNow) && (!Seated || enemy.Anim.HasState(AlertState));

        void Begin(float fade)
        {
            holding = Usable && enemy.IsAlive && !enemy.IsAggro && enemy.State == EnemyState.Idle
                      && (enemy.encounter == null || !enemy.encounter.manualActivation);
            if (holding) PlayPose(fade);
            else Seat(false);
        }

        void PlayPose(float fade)
        {
            waking = false;
            lastNorm = -1f;
            hurry = 1f;
            playing = LoopNow;
            enemy.Anim.Play(playing, fade, phase);
            Seat(true);
        }

        /// <summary>La cápsula sobre el cuerpo sentado (o de vuelta en el transform al pararse).</summary>
        void Seat(bool on)
        {
            on &= Seated;
            if (capsule == null || on == seatShift) return;
            seatShift = on;
            capsule.center = on ? capsuleCenter + Vector3.back * (BodyBack * enemy.config.scale / Mathf.Max(0.01f, transform.lossyScale.z)) : capsuleCenter;
        }

        /// <summary>
        /// Enemy.Alert: arranca el sobresalto (después de su demora: los del encuentro no reaccionan en el mismo cuadro; un
        /// golpe, 'now', en el acto) y devuelve cuánto dura el Alert, o -1 si no estaba en una pose ambiental (el Spotted de
        /// siempre).
        /// </summary>
        public float Wake(bool now = false)
        {
            if (!holding || waking || pending) return -1f;
            waking = true;
            wakePlayed = false;
            hurry = 1f;
            float delay = now ? 0f : wakeDelay;
            wakeAt = Time.time + delay;
            turnAt = wakeAt + (activity == Activity.Meditate ? MeditateLand : activity == Activity.Sleep ? SleepLand : 0f);
            return delay + WakeLength - (Seated ? StandFade : 0f);
        }

        /// <summary>Segundos del sobresalto a velocidad 1: el despertar entero, o el Spotted desde donde arranca.</summary>
        float WakeLength => Seated ? enemy.Anim.Length(AlertState, 1.5f)
            : Mathf.Clamp(enemy.Anim.Length(enemy.config.animSpotted, 0.6f) * (1f - SpottedOffset), 0.4f, 0.9f);

        /// <summary>
        /// Un golpe en pleno sobresalto (Enemy.ReceiveHit): arranca ya si todavía esperaba su turno y sigue a HurrySpeed. Una
        /// vez por despertar; devuelve lo que le falta al Alert (s) o -1 si ya estaba apurado.
        /// </summary>
        public float Hurry()
        {
            if (!Waking || hurry > 1f) return -1f;
            float land = turnAt - wakeAt;
            if (!wakePlayed) { wakeAt = Time.time; hurry = HurrySpeed; PlayWake(); }
            else
            {
                hurry = HurrySpeed;
                if (enemy.Anim.Current == WakeState) enemy.Anim.SetStateSpeed(hurry);
            }
            float done = Time.time - wakeStart;
            turnAt = Time.time + Mathf.Max(0f, land - done) / hurry;
            return Mathf.Max(0f, WakeLength - done) / hurry - (Seated ? StandFade : 0f);
        }

        /// <summary>De dónde arranca el Spotted desde un idle parado: el que mira el filo entra con la hoja ya levantada
        /// (el Spotted la sube delante de la cara) y el resto en el saltito (el cruce de los pies queda en el aire).</summary>
        float SpottedOffset => activity == Activity.Inspect ? 0.25f : 0.1f;

        string WakeState => Seated ? AlertState : enemy.config.animSpotted;

        void PlayWake()
        {
            wakePlayed = true;
            wakeStart = Time.time;
            if (Seated) enemy.Anim.Play(AlertState, WakeFade, 0f, hurry);
            else enemy.Anim.Play(enemy.config.animSpotted, StandFade, SpottedOffset, hurry);
        }

        /// <summary>Enemy.ResetEnemy (Kaito murió): vuelve a lo que estaba haciendo en su lugar.</summary>
        public void Restart()
        {
            pending = resuming = false;
            Begin(0f);
        }

        /// <summary>Enemy.TickHome: volvió a su lugar sin pelea y ya mira como estaba. Retoma lo que hacía (la pareja, cuando
        /// llegaron los dos: si no, el primero practicaba contra el aire).</summary>
        public void Resume()
        {
            if (!holding && !pending) resuming = true;
        }

        void TryResume()
        {
            if (enemy.State != EnemyState.Idle || enemy.IsAggro || !enemy.IsAlive) { resuming = false; return; }
            bool mateAway = activity == Activity.Spar && partner != null && partner.enemy != null && partner.enemy.IsAlive
                            && !partner.holding && !partner.resuming;
            if (mateAway) return;
            resuming = false;
            Begin(Seated ? ResumeSeatFade : ResumeFade);
        }

        /// <summary>La historia lo toma (EnterScripted): deja la pose ambiental.</summary>
        public void Release() { holding = waking = resuming = false; Seat(false); }

        void OnEnable()
        {
            // reactivado (lejos de la cámara, una cinemática): el Animator vuelve a su estado por defecto; la pose se
            // retoma en el próximo Update, cuando el Animator ya se reinició
            if (holding && !waking && enemy != null) pending = true;
        }

        void Update()
        {
            if (enemy == null) return;
            if (pending) { pending = false; Begin(0f); }
            if (!holding)
            {
                if (resuming) TryResume();
                return;
            }
            if (waking)
            {
                if (!wakePlayed && Time.time >= wakeAt) PlayWake();
                if (seatShift && Time.time >= turnAt) Seat(false);
                // terminó el Alert (persigue) o lo sacó otra cosa (la muerte, la historia): se acabó lo ambiental
                if (enemy.State != EnemyState.Alert) { holding = waking = false; Seat(false); }
                return;
            }
            if (enemy.State != EnemyState.Idle || enemy.IsAggro || !enemy.IsAlive) { holding = false; Seat(false); return; }
            if (partner != null && !leader && playing == loopState) Follow();
            Events();
        }

        /// <summary>El segundo de la pareja sigue el reloj del primero: si se corren (un cuadro largo, reactivado), el
        /// choque de las hojas deja de coincidir.</summary>
        void Follow()
        {
            if (!partner.holding || partner.waking || partner.playing != partner.loopState) return;
            if (!partner.enemy.Anim.TryNormalizedTime(partner.loopState, out float ln) || !enemy.Anim.TryNormalizedTime(loopState, out float mn)) return;
            float d = Mathf.Repeat(ln, 1f) - Mathf.Repeat(mn, 1f);
            if (d > 0.5f) d -= 1f; else if (d < -0.5f) d += 1f;
            if (Mathf.Abs(d) > 0.01f) { enemy.Anim.Play(loopState, 0f, Mathf.Repeat(ln, 1f)); lastNorm = -1f; }
        }

        /// <summary>Lo que acompaña a los loops en sus cuadros: el choque de las hojas, el ronquido, los pisotones.</summary>
        void Events()
        {
            if (!enemy.Anim.TryNormalizedTime(playing, out float n)) return;
            n = Mathf.Repeat(n, 1f);
            float prev = lastNorm;
            lastNorm = n;
            if (prev < 0f) return;
            switch (activity)
            {
                case Activity.Spar:
                    if (!leader || partner == null || playing != loopState || partner.playing != partner.loopState) break;
                    if (Crossed(prev, n, ClashA)) Clash(transform);
                    if (Crossed(prev, n, ClashB)) Clash(partner.transform);
                    break;
                case Activity.Sleep:
                    if (Crossed(prev, n, Snore) && Near(out _) && head != null)
                        Game.FX?.SmokePuff(head.position + transform.forward * (0.35f * enemy.config.scale) - Vector3.up * 0.1f, 0.3f);
                    break;
                case Activity.Shiko:
                    if (Crossed(prev, n, StompR)) Stomp(new Vector3(0.42f, 0f, -0.02f));
                    if (Crossed(prev, n, StompL)) Stomp(new Vector3(-0.42f, 0f, -0.02f));
                    break;
            }
        }

        static bool Crossed(float prev, float now, float at) => prev <= now ? prev < at && at <= now : at > prev || at <= now;

        /// <summary>Kaito cerca (los efectos se ven y se oyen); 'k' baja el volumen con la distancia.</summary>
        bool Near(out float k)
        {
            k = 0f;
            if (Game.Player == null) return false;
            float d = CombatMath.FlatDistance(Game.Player.transform.position, transform.position);
            k = 1f - d / SoundRange;
            return k > 0f;
        }

        void Clash(Transform striker)
        {
            if (!Near(out float k)) return;
            Vector3 p = striker.TransformPoint(ClashLocal * enemy.config.scale);
            Game.FX?.DodgeSpark(p);
            Game.Audio?.Play("clang", p, 0.25f * k);
        }

        void Stomp(Vector3 footLocal)
        {
            if (!Near(out float k)) return;
            Vector3 p = transform.TransformPoint(footLocal * enemy.config.scale);
            Game.FX?.Dust(p, 0.5f);
            Game.Audio?.Play("step", p, 0.6f * k);
        }
    }
}
