using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Lo que se ve de Chikuō y cambia con la pelea (BambooMaster.fbx, sidecar 'parts'): los cascabeles hablan (sección 3.2
    /// del diseño). Los slots de brillo nacen apagados y el jefe los enciende por nombre (CharacterGlint.SetGlow):
    ///  * Chikuo_GlintChimesHi (los cortos de los hombros): dorado = un dardo por salir;
    ///  * Chikuo_GlintChimesLo (los largos del ruedo) y los de los hombros juntos: rojo = se tira encima o barre;
    ///  * todos en blanco latiendo a 4 Hz = la caña cargada ("cortá acá");
    ///  * Chikuo_GlintStaff (la flauta-bastón) y Chikuo_GlintFootR/L (las patadas): el miembro que pega.
    /// También: la estela del bastón y de los pies, los enchufes de la flauta (de dónde salen los dardos), la cabeza (las
    /// marcas de la UI arriba de él aunque esté en la caña) y los cascabeles con la física del juego (SpringChain).
    /// </summary>
    public sealed class BambooMasterLook
    {
        public const string ChimesHi = "Chikuo_GlintChimesHi", ChimesLo = "Chikuo_GlintChimesLo", StaffGlow = "Chikuo_GlintStaff",
            FootR = "Chikuo_GlintFootR", FootL = "Chikuo_GlintFootL";
        public static readonly string[] DartSlots = { ChimesHi }, StaffSlots = { StaffGlow }, KickSlots = { FootR, ChimesLo, ChimesHi },
            RedSlots = { ChimesLo, ChimesHi, StaffGlow }, DropSlots = { StaffGlow, ChimesHi };

        readonly CharacterGlint glint;
        readonly SpringChain spring;
        readonly List<string> lit = new List<string>(6);
        bool loadLit;
        float loadClock;

        public Transform Muzzle { get; }
        public Transform Mouth { get; }
        public Transform Head { get; }
        public Transform StaffBottom { get; }
        public Transform StaffTop { get; }

        readonly Dictionary<string, BladeTrail> limbTrails = new Dictionary<string, BladeTrail>(2);
        BladeTrail limbOn;

        /// <summary>La caña está cargada: los cascabeles laten en blanco (pisa lo que pida el aviso en ellos).</summary>
        public bool Loaded { get; set; }

        public BambooMasterLook(Transform model)
        {
            glint = model.GetComponentInChildren<CharacterGlint>();
            foreach (var t in model.GetComponentsInChildren<Transform>(true))
            {
                switch (t.name)
                {
                    case "Staff_Muzzle": Muzzle = t; break;
                    case "Staff_Mouth": Mouth = t; StaffTop = t; break;
                    case "Staff": StaffBottom = t; break;
                    case "Head": Head = t; break;
                }
            }
            BuildLimbTrails(model);
            var body = model.GetComponentInChildren<SkinnedMeshRenderer>();
            spring = model.GetComponentInChildren<Animator>()?.gameObject.AddComponent<SpringChain>();
            spring?.Rebuild(body);
            ClearTell();
        }

        // ------------------------------------------------------------------ avisos
        /// <summary>
        /// El miembro del golpe (o los cascabeles) se enciende en el último tramo del aviso: de 1.5 a 5 de intensidad
        /// mientras 'k' va de 0 a 1 (el cierre del anillo). Dorado = parry, rojo = dash.
        /// </summary>
        public void Tell(string[] slots, bool danger, float k)
        {
            if (glint == null || slots == null) return;
            Color c = danger ? TellStyle.Crimson : TellStyle.Gold;
            float intensity = Mathf.Lerp(1.5f, 5f, k * k);
            for (int i = 0; i < slots.Length; i++)
            {
                if (Loaded && IsChime(slots[i])) continue;
                glint.SetGlow(slots[i], c, intensity);
                if (!lit.Contains(slots[i])) lit.Add(slots[i]);
            }
        }

        public void ClearTell()
        {
            if (glint == null) return;
            for (int i = 0; i < lit.Count; i++) if (!(Loaded && IsChime(lit[i]))) glint.SetGlow(lit[i], Color.black, 0f);
            lit.Clear();
        }

        static bool IsChime(string slot) => slot == ChimesHi || slot == ChimesLo;

        /// <summary>Cada frame: el latido blanco de la carga (4 Hz, como el nudo de la base: BambooStalk).</summary>
        public void Tick(float dt)
        {
            if (glint == null) return;
            if (Loaded)
            {
                loadClock += dt;
                float pulse = 0.5f + 0.5f * Mathf.Sin(loadClock * 4f * 2f * Mathf.PI);
                float i = Mathf.Lerp(1.8f, 4.2f, pulse);
                glint.SetGlow(ChimesHi, BambooStalk.White, i);
                glint.SetGlow(ChimesLo, BambooStalk.White, i * 0.85f);
                loadLit = true;
            }
            else if (loadLit)
            {
                loadLit = false;
                loadClock = 0f;
                glint.SetGlow(ChimesHi, Color.black, 0f);
                glint.SetGlow(ChimesLo, Color.black, 0f);
            }
        }

        /// <summary>El sacudón de los cascabeles (cayó, cada corte en un hueco): la física los revolea.</summary>
        public void Jangle(Vector3 velocity) => spring?.Kick(velocity);

        // ------------------------------------------------------------------ estelas
        void BuildLimbTrails(Transform model)
        {
            var mat = Game.Content != null ? Game.Content.trailMaterial : null;
            Transform owner = model.parent != null ? model.parent : model;
            float s = model.lossyScale.y;
            foreach (var t in model.GetComponentsInChildren<Transform>(true))
            {
                string slot = t.name == "Toe_R" ? FootR : t.name == "Toe_L" ? FootL : null;
                if (slot == null || limbTrails.ContainsKey(slot)) continue;
                var tip = new GameObject(t.name + "_Estela").transform;
                tip.SetParent(t, false);
                tip.localPosition = t.InverseTransformPoint(t.position + t.up * 0.12f * s);
                limbTrails[slot] = BladeTrail.Create(owner, t.parent, tip, mat, TellStyle.TrailParry);
            }
        }

        /// <summary>La estela del primer pie de 'slots' (dorada o roja). false si no hay pie (el bastón usa la de Enemy).</summary>
        public bool BeginLimbTrail(string[] slots, bool danger)
        {
            StopLimbTrail();
            if (slots == null) return false;
            for (int i = 0; i < slots.Length; i++)
            {
                if (!limbTrails.TryGetValue(slots[i], out var t) || t == null) continue;
                t.SetColor(danger ? TellStyle.TrailDanger : new Color(TellStyle.Gold.r, TellStyle.Gold.g, TellStyle.Gold.b, 0.75f));
                t.SetLifetime(0.2f);
                t.Begin();
                limbOn = t;
                return true;
            }
            return false;
        }

        public void StopLimbTrail()
        {
            if (limbOn != null) limbOn.Stop();
            limbOn = null;
        }

        /// <summary>Al morir o reintentar: nada encendido.</summary>
        public void Extinguish()
        {
            Loaded = false;
            Tick(0f);
            ClearTell();
            StopLimbTrail();
        }
    }
}
