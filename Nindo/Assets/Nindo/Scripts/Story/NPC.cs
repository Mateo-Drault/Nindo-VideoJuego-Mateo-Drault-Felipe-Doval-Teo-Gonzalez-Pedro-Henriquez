using UnityEngine;

namespace Nindo
{
    /// <summary>Personaje no jugable simple (el abuelo): se para, mira y camina en línea recta.</summary>
    public class NPC : MonoBehaviour
    {
        // contrato con Tools/Blender/anim/team_clips_grandpa.py (TeamAnims/GrandpaAnims.fbx)
        public const string KidnapWaitState = "KidnapWait", KidnapState = "Kidnap", DraggedState = "Dragged";
        public const string BoundState = "Bound", BoundStruggleState = "BoundStruggle", FreedState = "Freed", WalkState = "Walk";
        /// <summary>DRAG_SPEED: lo que avanza el transform mientras suena Dragged (en promedio: el grupo se atrasa cuando el
        /// abuelo resiste y se pone al día en el tirón, con los pasos del ninja clavados en el mundo).</summary>
        public const float DragSpeed = 0.8f;
        /// <summary>WALK_SPEED: lo que avanza Walk por segundo a velocidad 1 (Play(WalkState, fade, metrosPorSegundo / WalkClipSpeed)).</summary>
        public const float WalkClipSpeed = 0.8f;
        /// <summary>KNEEL_FWD: Bound y Freed se autoran arrodillados con el transform adelantado esto respecto del marcador
        /// (si no, la túnica entraba en el zócalo del binding_post). Freed termina parado en el transform, en Idle.</summary>
        public const float KneelForward = 0.2f;
        /// <summary>
        /// Alturas (m sobre los pies) de las vueltas de ShadowRopes si no encuentra los huesos del abuelo, medidas en Bound
        /// f0 (línea BOUND de build_team_anims): las muñecas cruzadas atrás (0.40), a mitad de los antebrazos (los codos,
        /// a 0.53, quedan casi a la altura del pecho) y el pecho, 5 cm bajo los hombros (0.61).
        /// </summary>
        public static readonly System.Collections.ObjectModel.ReadOnlyCollection<float> BoundRopeLoops =
            System.Array.AsReadOnly(new[] { 0.40f, 0.48f, 0.56f });
        /// <summary>Medio ancho del abuelo de rodillas a la altura de las cuerdas, con las mangas (m; los bounds de la
        /// pose de bind son de los brazos en cruz: 0.8 m).</summary>
        public const float BoundRopeHalfWidth = 0.21f;
        /// <summary>Kidnap: cae sentado en el cuadro 27 de 57 (polvo, golpe y, desde ahí, el polvo de los talones).</summary>
        const float KidnapImpact = 27f / 30f;
        /// <summary>KidnapWait -> Kidnap: los pies del ninja son los mismos y el balanceo es de 3 cm, así que se funde.</summary>
        const float KidnapFade = 0.25f;
        /// <summary>Freed: parado en el cuadro 98 de 108. Hasta ahí está de rodillas: un giro del transform le arrastraría
        /// las rodillas por el piso (a 0.2 m del pivote), así que TurnTo espera.</summary>
        const float FreedStandAt = 98f / 108f;
        // forcejeo atado: cada tanto (s) y, entre forcejeos, cada vuelta de Bound a un ritmo un poco distinto
        const float StruggleMin = 4f, StruggleMax = 9f, BoundSpeedMin = 0.85f, BoundSpeedMax = 1.1f;
        // polvo de los talones arrastrados: cerca del piso y corriendo en el mundo más que esto (m, m/s), cada tanto (s)
        const float HeelHeight = 0.15f, HeelSpeed = 0.45f, HeelDustEvery = 0.22f, HeelDustScale = 0.32f;

        public string characterId = "grandpa";
        CharacterAnimator anim = new CharacterAnimator();
        Vector3 walkTarget;
        float walkSpeed;
        bool walking;

        public static NPC Spawn(string characterId, Vector3 pos, Quaternion rot, Transform parent)
        {
            // capa Ignore Raycast: el rayo de suelo (máscara Default), el de los enemigos y el NavMesh
            // en runtime no tienen que ver la cápsula (si no, el NPC "pisa" su propia cabeza y sale volando)
            var go = new GameObject("NPC_" + characterId) { layer = 2 };
            go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation(pos, rot);
            var a = CharacterFactory.BuildModel(characterId, go.transform);
            // el FBX del abuelo trae también al ninja del secuestro ("Cube"): solo se ve en la escena del secuestro
            if (characterId == "grandpa")
                foreach (var r in go.GetComponentsInChildren<Renderer>(true)) if (r.name.StartsWith("Cube")) r.enabled = false;
            var npc = go.AddComponent<NPC>();
            npc.characterId = characterId;
            npc.anim.Init(a);
            npc.anim.Play("Locomotion", 0f);
            var col = go.AddComponent<CapsuleCollider>();
            col.radius = 0.35f; col.height = 1.5f; col.center = new Vector3(0, 0.75f, 0);
            return npc;
        }

        public void Play(string state, float fade = 0.15f) { Play(state, fade, 1f); }

        /// <summary>Un estado a 'speed' x su velocidad (Walk al ritmo de un SlideTo que no es WalkClipSpeed: sin esto los pies
        /// patinan lo que difieren las dos velocidades).</summary>
        public void Play(string state, float fade, float speed)
        {
            anim.SetSpeed(1f);
            anim.Play(state, fade, 0f, speed); then = null; dragging = dusting = false;
        }

        /// <summary>El primer cuadro de un estado, quieto.</summary>
        public void Hold(string state) { anim.SetSpeed(1f); anim.Play(state, 0f, 0f, 0f); then = null; dragging = dusting = false; }

        /// <summary>
        /// Antes del secuestro (NPC 'kidnap'): el abuelo respira y mira, el ninja agazapado se balancea delante de él
        /// (KidnapWait, que empalma con Kidnap). Sin ese estado, quietos en el cuadro 0 de Kidnap: desde Idle el ninja está
        /// en la pose fija del FBX y el fundido le movía la mano 21 cm.
        /// </summary>
        public void AwaitKidnap()
        {
            if (anim.HasState(KidnapWaitState)) Play(KidnapWaitState, 0f);
            else Hold(KidnapState);
        }

        /// <summary>Un clip que no es loop y, cuando termina, 'next' (los controllers no tienen transiciones: sin esto el
        /// abuelo quedaba congelado en el último cuadro de Freed como una estatua).</summary>
        public void PlayThen(string state, string next, float fade = 0.15f)
        {
            anim.SetSpeed(1f);
            anim.Play(state, fade);
            thenFrom = state; then = next; thenDrag = false;
        }
        string then, thenFrom;
        bool thenDrag;

        /// <summary>
        /// El secuestro del prólogo (NPC 'kidnap', mirando hacia 'exit'): el ninja lo agarra de la muñeca y lo tira al
        /// piso (Kidnap); el último cuadro de Kidnap es el primero de Dragged, así que pasa en seco y el transform arranca
        /// hacia 'exit' a DragSpeed (dentro de Kidnap el grupo ya venía acelerando hasta esa velocidad). Al llegar a 'exit'
        /// el ninja se esfuma con el abuelo en una nube de humo.
        /// </summary>
        public void Kidnap(Vector3 exit)
        {
            dragTarget = exit;
            impactAt = Time.time + KidnapImpact;
            // sin Dragged (controller viejo): la toma del equipo y, al terminar, se desliza quieto como antes
            PlayThen(KidnapState, anim.HasState(DraggedState) ? DraggedState : KidnapState,
                     anim.Current == KidnapWaitState ? KidnapFade : 0f);
            thenDrag = true;
        }

        /// <summary>Ya lo vienen arrastrando (el bosque): Dragged desde el cuadro 0 y el transform hacia 'target'; al
        /// llegar se esfuman en humo.</summary>
        public void Drag(Vector3 target)
        {
            FaceTo(target);
            if (anim.HasState(DraggedState)) Play(DraggedState, 0f);
            else { anim.Play(KidnapState, 0f, 0.98f); then = null; }
            StartDrag(target);
        }

        /// <summary>
        /// Atado al poste: de rodillas, KneelForward adelante del marcador (ver la constante). Antes de armar las cuerdas:
        /// el Animator se evalúa en el acto para que ShadowRopes lea los huesos ya en la pose de Bound. Con
        /// CullUpdateTransforms un Animator que nunca se dibujó (partida nueva: Kaito está en el prólogo, a 300 m) no
        /// escribe los huesos ni en un Update manual y quedaban en la pose de bind (brazos en cruz): las cuerdas salían
        /// sobre el sombrero. Por eso, solo para esta evaluación, AlwaysAnimate.
        /// </summary>
        public void KneelBound()
        {
            transform.position += transform.forward * KneelForward;
            Play(BoundState, 0f);
            if (anim.Valid)
            {
                var a = anim.Animator;
                var cm = a.cullingMode;
                a.cullingMode = AnimatorCullingMode.AlwaysAnimate;
                a.Update(0f);
                a.cullingMode = cm;
            }
            nextStruggle = Time.time + Random.Range(StruggleMin, StruggleMax);
        }
        float nextStruggle;

        void StartDrag(Vector3 target)
        {
            SlideTo(target, DragSpeed);
            dragging = true;
            TrackHeels();
        }
        Vector3 dragTarget;
        float impactAt = -1f;
        bool dragging, dusting, heelsPrimed;
        readonly Transform[] heels = new Transform[2];
        readonly Vector3[] heelPrev = new Vector3[2];
        readonly float[] heelDust = new float[2];

        /// <summary>Desde acá los talones que se arrastran levantan polvo. La primera muestra solo guarda dónde están: en el
        /// cuadro en que arranca (el bosque: Spawn y Drag juntos) el Animator todavía no evaluó la pose y la velocidad
        /// salía enorme (una nube por talón en el primer cuadro).</summary>
        void TrackHeels()
        {
            dusting = true;
            heelsPrimed = false;
            if (heels[0] == null)
            {
                // los pies del abuelo (el ninja del mismo FBX tiene los suyos con '.001')
                heels[0] = FindDeep(transform, "Pie.L");
                heels[1] = FindDeep(transform, "Pie.R");
            }
        }

        internal static Transform FindDeep(Transform t, string name)
        {
            if (t.name == name) return t;
            for (int i = 0; i < t.childCount; i++)
            {
                var r = FindDeep(t.GetChild(i), name);
                if (r != null) return r;
            }
            return null;
        }

        /// <summary>Se da vuelta hacia un punto en 'seconds' (FaceTo gira de golpe: en cámara se veía saltar 180°). De
        /// rodillas (Bound, el forcejeo y Freed hasta pararse) espera a que esté parado: girarlo ahí le arrastraba las
        /// rodillas 10-12 cm por el piso.</summary>
        public void TurnTo(Vector3 p, float seconds)
        {
            if (Kneeling())
            {
                pendingTurn = true; pendingTo = p; pendingDur = seconds;
                return;
            }
            pendingTurn = false;
            Vector3 d = (p - transform.position).Flat();
            if (d.sqrMagnitude < 0.01f) return;
            turnFrom = transform.rotation; turnTo = Quaternion.LookRotation(d);
            turnT = 0f; turnDur = Mathf.Max(0.01f, seconds);
        }
        Quaternion turnFrom, turnTo;
        float turnT = 1f, turnDur = 1f, pendingDur;
        bool pendingTurn;
        Vector3 pendingTo;

        bool Kneeling()
        {
            string s = anim.Current;
            if (s == BoundState || s == BoundStruggleState) return true;
            return s == FreedState && (!anim.TryNormalizedTime(FreedState, out float n) || n < FreedStandAt);
        }

        /// <summary>Se desliza hacia un punto sin girar ni cambiar la animación (arrastre) y para justo en él (el clip que
        /// suena y el transform terminan juntos). Si suena Walk, la lleva al paso del deslizamiento (el final pide Walk y
        /// SlideTo a 0.88 m/s: a velocidad 1 los pies patinaban 10 %); el próximo Play la devuelve a 1.</summary>
        public void SlideTo(Vector3 target, float speed)
        {
            walkTarget = target; walkSpeed = speed; walking = true; sliding = true;
            if (anim.Current == WalkState) anim.SetSpeed(speed / WalkClipSpeed);
        }
        bool sliding;

        public void FaceTo(Vector3 p)
        {
            Vector3 d = (p - transform.position).Flat();
            if (d.sqrMagnitude > 0.01f) transform.rotation = Quaternion.LookRotation(d);
            turnT = 1f;   // manda sobre un TurnTo a medias
            pendingTurn = false;
        }

        public void WalkTo(Vector3 target, float speed)
        {
            walkTarget = target; walkSpeed = speed; walking = true; sliding = false;
        }

        void Update()
        {
            float dt = Time.deltaTime;
            if (walking)
            {
                Vector3 d = (walkTarget - transform.position).Flat();
                // caminando (WalkTo) frena 20 cm antes, girando; deslizado (SlideTo) llega exacto: antes también paraba a
                // 20 cm y el clip seguía andando en el lugar (en el arrastre, el ninja caminaba en el aire)
                float stop = sliding ? 0.005f : 0.2f;
                if (d.magnitude < stop) Arrive();
                else
                {
                    Vector3 step = d.normalized * Mathf.Min(walkSpeed * dt, d.magnitude);
                    Vector3 p = transform.position + step;
                    if (Physics.Raycast(p + Vector3.up * 2f, Vector3.down, out var hit, 6f, LayerMask.GetMask("Default"), QueryTriggerInteraction.Ignore)) p.y = hit.point.y;
                    transform.position = p;
                    if (!sliding) transform.rotation = CombatMath.Damp(transform.rotation, Quaternion.LookRotation(d), 8f, dt);
                    if (sliding && (walkTarget - p).Flat().magnitude < stop) Arrive();
                }
            }
            if (pendingTurn && !Kneeling()) TurnTo(pendingTo, pendingDur);
            if (turnT < 1f)
            {
                turnT = Mathf.Min(1f, turnT + dt / turnDur);
                transform.rotation = Quaternion.Slerp(turnFrom, turnTo, Mathf.SmoothStep(0f, 1f, turnT));
            }
            if (then != null && anim.Current == thenFrom && anim.TryNormalizedTime(thenFrom, out float shown))
            {
                if (thenDrag && shown >= 1f)
                {
                    // Kidnap -> Dragged: el último cuadro de uno es el primero del otro; lo que se pasó del final ya es
                    // arrastre (clip y transform adelantados eso, así el grupo no frena un cuadro)
                    float over = (shown - 1f) * anim.Length(thenFrom, 1.9f);
                    if (then != thenFrom) anim.Play(then, 0f, over / anim.Length(then, 2.67f));
                    then = null;
                    StartDrag(dragTarget);
                    transform.position += (dragTarget - transform.position).Flat().normalized * Mathf.Min(over, 0.2f) * DragSpeed;
                }
                else if (!thenDrag && shown >= 0.98f)
                {
                    anim.Play(then, 0.25f);
                    then = null;
                }
            }
            if (impactAt > 0f && Time.time >= impactAt)
            {
                // cae sentado: el polvo bajo la cadera (el ninja tira de él hacia 'exit') y, desde acá, los talones
                // que clava y le arrastran también levantan polvo
                impactAt = -1f;
                Vector3 seat = transform.position + (dragTarget - transform.position).Flat().normalized * 0.05f;
                Game.FX?.Dust(seat, 0.7f);
                Game.Audio?.Play("hit_heavy", seat, 0.7f);
                TrackHeels();
            }
            if (dusting && dt > 0f) HeelDust(dt);
            if (anim.Current == BoundState) BoundRhythm();
            if (!sliding) anim.SetLocomotion(walking ? 0.5f : 0f, dt);
            anim.Tick();
        }

        /// <summary>Llegó adonde lo deslizaban. Si era el arrastre, el ninja se esfuma con el abuelo (el humo de los ninjas
        /// del juego): con Dragged sonando sobre un transform quieto el ninja caminaba en el lugar y los talones seguían
        /// levantando polvo.</summary>
        void Arrive()
        {
            walking = false;
            if (sliding) transform.position = new Vector3(walkTarget.x, transform.position.y, walkTarget.z);
            if (!dragging) return;
            dragging = dusting = false;
            Game.FX?.SmokePuff(transform.position + Vector3.up, 1.6f);
            gameObject.SetActive(false);
        }

        /// <summary>
        /// Atado: Bound es un loop tranquilo (respira y mira la arena); cada StruggleMin-StruggleMax s, en la vuelta del
        /// loop (Bound f0, donde empieza y termina el forcejeo), forcejea una vez y vuelve. Entre forcejeos cada vuelta
        /// arranca a un ritmo un poco distinto. Antes el mismo forcejeo se repetía cada 3 s durante toda la pelea.
        /// </summary>
        void BoundRhythm()
        {
            if (!anim.TryNormalizedTime(BoundState, out float n) || n < 1f) return;
            if (Time.time >= nextStruggle && anim.HasState(BoundStruggleState))
            {
                PlayThen(BoundStruggleState, BoundState, 0f);
                nextStruggle = Time.time + anim.Length(BoundStruggleState, 2.2f) + Random.Range(StruggleMin, StruggleMax);
            }
            else anim.Play(BoundState, 0f, 0f, Random.Range(BoundSpeedMin, BoundSpeedMax));
        }

        /// <summary>Los talones que se arrastran (cerca del piso y corriendo en el mundo) levantan polvo, cada uno a su ritmo.</summary>
        void HeelDust(float dt)
        {
            float floor = transform.position.y;
            for (int i = 0; i < 2; i++)
            {
                var h = heels[i];
                if (h == null) continue;
                Vector3 p = h.position;
                Vector3 v = (p - heelPrev[i]) / dt;
                heelPrev[i] = p;
                heelDust[i] -= dt;
                if (!heelsPrimed) continue;
                v.y = 0f;
                if (p.y - floor < HeelHeight && v.sqrMagnitude > HeelSpeed * HeelSpeed && heelDust[i] <= 0f)
                {
                    heelDust[i] = HeelDustEvery;
                    Game.FX?.Dust(new Vector3(p.x, floor + 0.03f, p.z), HeelDustScale);
                }
            }
            heelsPrimed = true;
        }
    }
}
