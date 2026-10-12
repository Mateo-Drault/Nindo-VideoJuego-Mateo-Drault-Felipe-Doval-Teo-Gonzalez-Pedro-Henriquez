using UnityEngine;

namespace Nindo
{
    /// <summary>Personaje no jugable simple (el abuelo): se para, mira y camina en línea recta.</summary>
    public class NPC : MonoBehaviour
    {
        // contrato con Tools/Blender/anim/team_clips_grandpa.py (TeamAnims/GrandpaAnims.fbx)
        public const string KidnapState = "Kidnap", DraggedState = "Dragged", BoundState = "Bound";
        /// <summary>DRAG_SPEED: lo que avanza el transform mientras suena Dragged (los pasos del ninja quedan clavados).</summary>
        public const float DragSpeed = 0.8f;
        /// <summary>KNEEL_FWD: Bound y Freed se autoran arrodillados con el transform adelantado esto respecto del marcador
        /// (si no, la túnica entraba en el zócalo del binding_post). Freed termina parado en el transform, en Idle.</summary>
        public const float KneelForward = 0.2f;
        /// <summary>BOUND_ROPES: alturas (m sobre los pies) de las vueltas de ShadowRopes para la pose de Bound: las muñecas
        /// cruzadas atrás (0.50), los codos (0.60) y el pecho bajo los hombros (0.69).</summary>
        public static readonly float[] BoundRopeLoops = { 0.48f, 0.58f, 0.66f };
        /// <summary>Kidnap: cae sentado en el cuadro 27 de 57 (polvo y golpe).</summary>
        const float KidnapImpact = 27f / 30f;
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

        public void Play(string state, float fade = 0.15f) { anim.Play(state, fade); then = null; dragging = false; }

        /// <summary>El primer cuadro de un estado, quieto (el NPC 'kidnap' espera en el de Kidnap: el ninja de Idle está en la
        /// pose fija del FBX, que no es la de arranque del secuestro, y el fundido de 0.1 s le movía la mano 21 cm).</summary>
        public void Hold(string state) { anim.Play(state, 0f, 0f, 0f); then = null; dragging = false; }

        /// <summary>Un clip que no es loop y, cuando termina, 'next' (los controllers no tienen transiciones: sin esto el
        /// abuelo quedaba congelado en el último cuadro de Freed como una estatua).</summary>
        public void PlayThen(string state, string next, float fade = 0.15f)
        {
            anim.Play(state, fade);
            thenFrom = state; then = next; thenDrag = false;
        }
        string then, thenFrom;
        bool thenDrag;

        /// <summary>
        /// El secuestro del prólogo (NPC 'kidnap', mirando hacia 'exit'): el ninja lo agarra de la muñeca y lo tira al
        /// piso (Kidnap); el último cuadro de Kidnap es el primero de Dragged, así que pasa en seco y el transform arranca
        /// hacia 'exit' a DragSpeed (dentro de Kidnap el grupo ya venía acelerando hasta esa velocidad).
        /// </summary>
        public void Kidnap(Vector3 exit)
        {
            dragTarget = exit;
            impactAt = Time.time + KidnapImpact;
            // sin Dragged (controller viejo): la toma del equipo y, al terminar, se desliza quieto como antes
            PlayThen(KidnapState, anim.HasState(DraggedState) ? DraggedState : KidnapState, 0.1f);
            thenDrag = true;
        }

        /// <summary>Ya lo vienen arrastrando (el bosque): Dragged desde el cuadro 0 y el transform hacia 'target'.</summary>
        public void Drag(Vector3 target)
        {
            FaceTo(target);
            if (anim.HasState(DraggedState)) Play(DraggedState, 0f);
            else { anim.Play(KidnapState, 0f, 0.98f); then = null; }
            StartDrag(target);
        }

        /// <summary>Atado al poste: de rodillas, KneelForward adelante del marcador (ver la constante). Antes de armar las cuerdas.</summary>
        public void KneelBound()
        {
            transform.position += transform.forward * KneelForward;
            Play(BoundState, 0f);
        }

        void StartDrag(Vector3 target)
        {
            SlideTo(target, DragSpeed);
            dragging = true;
            if (heels[0] == null)
            {
                // los pies del abuelo (el ninja del mismo FBX tiene los suyos con '.001')
                heels[0] = FindDeep(transform, "Pie.L");
                heels[1] = FindDeep(transform, "Pie.R");
            }
            for (int i = 0; i < 2; i++) if (heels[i] != null) heelPrev[i] = heels[i].position;
        }
        Vector3 dragTarget;
        float impactAt = -1f;
        bool dragging;
        readonly Transform[] heels = new Transform[2];
        readonly Vector3[] heelPrev = new Vector3[2];
        readonly float[] heelDust = new float[2];

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

        /// <summary>Se da vuelta hacia un punto en 'seconds' (FaceTo gira de golpe: en cámara se veía saltar 180°).</summary>
        public void TurnTo(Vector3 p, float seconds)
        {
            Vector3 d = (p - transform.position).Flat();
            if (d.sqrMagnitude < 0.01f) return;
            turnFrom = transform.rotation; turnTo = Quaternion.LookRotation(d);
            turnT = 0f; turnDur = Mathf.Max(0.01f, seconds);
        }
        Quaternion turnFrom, turnTo;
        float turnT = 1f, turnDur = 1f;

        /// <summary>Se desliza hacia un punto sin girar ni cambiar la animación (arrastre).</summary>
        public void SlideTo(Vector3 target, float speed) { walkTarget = target; walkSpeed = speed; walking = true; sliding = true; }
        bool sliding;

        public void FaceTo(Vector3 p)
        {
            Vector3 d = (p - transform.position).Flat();
            if (d.sqrMagnitude > 0.01f) transform.rotation = Quaternion.LookRotation(d);
            turnT = 1f;   // manda sobre un TurnTo a medias
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
                if (d.magnitude < 0.2f) walking = false;
                else
                {
                    Vector3 step = d.normalized * Mathf.Min(walkSpeed * dt, d.magnitude);
                    Vector3 p = transform.position + step;
                    if (Physics.Raycast(p + Vector3.up * 2f, Vector3.down, out var hit, 6f, LayerMask.GetMask("Default"), QueryTriggerInteraction.Ignore)) p.y = hit.point.y;
                    transform.position = p;
                    if (!sliding) transform.rotation = CombatMath.Damp(transform.rotation, Quaternion.LookRotation(d), 8f, dt);
                }
            }
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
                // cae sentado: el polvo bajo la cadera (el ninja tira de él hacia 'exit')
                impactAt = -1f;
                Vector3 seat = transform.position + (dragTarget - transform.position).Flat().normalized * 0.05f;
                Game.FX?.Dust(seat, 0.7f);
                Game.Audio?.Play("hit_heavy", seat, 0.7f);
            }
            if (dragging && dt > 0f) HeelDust(dt);
            if (!sliding) anim.SetLocomotion(walking ? 0.5f : 0f, dt);
            anim.Tick();
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
                v.y = 0f;
                heelDust[i] -= dt;
                if (p.y - floor < HeelHeight && v.sqrMagnitude > HeelSpeed * HeelSpeed && heelDust[i] <= 0f)
                {
                    heelDust[i] = HeelDustEvery;
                    Game.FX?.Dust(new Vector3(p.x, floor + 0.03f, p.z), HeelDustScale);
                }
            }
        }
    }
}
