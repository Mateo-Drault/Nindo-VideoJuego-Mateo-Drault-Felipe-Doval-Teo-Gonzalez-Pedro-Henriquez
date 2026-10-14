using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Lo que se ve de Chikuō y cambia con la pelea (BambooMaster.fbx, sidecar 'parts'):
    ///  * el saco de la fase 1 (Master_Robe), la copia que vuela al sacárselo (Master_RobeThrown, en los huesos RobeT_*)
    ///    y que queda horneada en el piso, y el bastón de la fase 3 (Master_Staff, rígido en el hueso Staff);
    ///  * el brillo del miembro que pega (slots Master_Glint*: dorado = parry, rojo = dash), el jade de la postura del
    ///    bambú y los ojos de jade desde la fase 2 (Master_Eyes);
    ///  * la punta de arriba del bastón para su estela.
    /// Ningún material se llama 'Glint': Enemy no prende nada solo y el jefe elige qué se enciende.
    /// </summary>
    public sealed class BambooMasterLook
    {
        public const string Robe = "Master_Robe", RobeThrown = "Master_RobeThrown", Staff = "Chikuo_Staff";
        public const string HandR = "Master_GlintHandR", HandL = "Master_GlintHandL", StaffGlow = "Chikuo_GlintStaff", Eyes = "Master_Eyes";
        /// <summary>Jade de los ojos (el sidecar: 0.45, 1, 0.8) y de la postura del bambú: no es dorado ni rojo, no pide nada.</summary>
        public static readonly Color Jade = new Color(0.45f, 1f, 0.8f);

        readonly Transform model;
        readonly CharacterGlint glint;
        Renderer robe, robeThrown, staff;
        Transform staffBone, staffTip;
        GameObject bakedCoat;
        Mesh bakedMesh;
        // slots encendidos por el aviso (para apagarlos sin recorrer todos)
        readonly List<string> lit = new List<string>(4);
        bool stanceGlow;
        float eyes;

        public Transform StaffBottom => staffBone;
        public Transform StaffTip => staffTip;
        public bool StaffShown => staff != null && staff.enabled;

        // estelas de las manos y los pies (de la muñeca a la punta de los dedos, del tobillo a la punta del pie)
        readonly Dictionary<string, BladeTrail> limbTrails = new Dictionary<string, BladeTrail>(4);
        BladeTrail limbOn;
        // el aro de jade de la postura del bambú
        ShockRing stanceRing;
        Transform ringOwner;
        /// <summary>Radio del aro de la postura (m): fuera del cuerpo y del alcance de la palma de guardia, dentro de la
        /// pantalla de pelea.</summary>
        const float StanceRingRadius = 1.35f;

        public BambooMasterLook(Transform model)
        {
            this.model = model;
            glint = model.GetComponentInChildren<CharacterGlint>();
            foreach (var r in model.GetComponentsInChildren<Renderer>(true))
            {
                if (r.name == Robe) robe = r;
                else if (r.name == RobeThrown) robeThrown = r;
                else if (r.name == Staff) staff = r;
            }
            // el hueso de la flauta-bastón va de la punta de abajo a la de arriba; la de arriba es el enchufe Staff_Mouth
            // del ermitaño (BambooMaster.fbx de la fase C4): de ahí sale la estela
            foreach (var t in model.GetComponentsInChildren<Transform>(true))
            {
                if (t.name == "Staff") staffBone = t;
                else if (t.name == "Staff_Mouth") staffTip = t;
            }
            BuildLimbTrails(model);
            // la barba, la ramita del moño, las colas de la faja y los cascabeles con la física del juego (SpringChain)
            var body = model.GetComponentInChildren<SkinnedMeshRenderer>();
            var spring = model.GetComponentInChildren<Animator>()?.gameObject.AddComponent<SpringChain>();
            spring?.Rebuild(body);
            ResetAll();
        }

        /// <summary>Como al aparecer: con el saco, sin bastón, nada encendido. El saco horneado del intento anterior se va,
        /// salvo que el reintento arranque sin él ('keepCoat'): sigue tirado en el claro donde cayó.</summary>
        public void ResetAll(bool keepCoat = false)
        {
            SetPhaseLook(0);
            if (!keepCoat && bakedCoat != null) { Object.Destroy(bakedCoat); bakedCoat = null; }
            if (!keepCoat && bakedMesh != null) { Object.Destroy(bakedMesh); bakedMesh = null; }
            ClearTell();
            SetStance(false);
            eyes = 0f;
            glint?.SetGlow(Eyes, Jade, 0f);
        }

        /// <summary>Lo que lleva puesto en cada fase (0..2): para los reintentos que arrancan en la fase 2.</summary>
        public void SetPhaseLook(int phase)
        {
            if (robe != null) robe.enabled = phase == 0;
            if (robeThrown != null) robeThrown.enabled = false;
            // el ermitaño lleva la flauta-bastón siempre (el modelo viejo la sacaba en la fase 3)
            if (staff != null) staff.enabled = true;
            if (phase >= 1) IgniteEyes(1f);
        }

        // ------------------------------------------------------------------ cambio a la fase 2
        /// <summary>CoatOff: el saco puesto se apaga y la copia que vuela se prende (la mueve el clip).</summary>
        public void ThrowCoat()
        {
            if (robe != null) robe.enabled = false;
            if (robeThrown != null) robeThrown.enabled = true;
        }

        /// <summary>
        /// CoatRest: el saco quedó en el piso. Se hornea en una malla quieta del claro (los demás clips vuelven a guardar
        /// la copia en la espalda) y la copia animada se apaga.
        /// </summary>
        public void RestCoat(Transform keepIn)
        {
            if (!(robeThrown is SkinnedMeshRenderer smr) || !smr.enabled) return;
            bakedMesh = new Mesh { name = "SacoDeChikuo" };
            smr.BakeMesh(bakedMesh, true);
            bakedCoat = new GameObject("SacoDeChikuo");
            bakedCoat.transform.SetPositionAndRotation(smr.transform.position, smr.transform.rotation);
            bakedCoat.transform.SetParent(keepIn, true);
            bakedCoat.AddComponent<MeshFilter>().sharedMesh = bakedMesh;
            var mr = bakedCoat.AddComponent<MeshRenderer>();
            mr.sharedMaterials = smr.sharedMaterials;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.On;
            smr.enabled = false;
        }

        /// <summary>Los ojos de jade (EyesIgnite de PhaseCoat): suben en un instante y quedan encendidos.</summary>
        public void IgniteEyes(float k)
        {
            eyes = Mathf.Max(eyes, k);
            glint?.SetGlow(Eyes, Jade, 2.2f * eyes);
        }

        // ------------------------------------------------------------------ cambio a la fase 3
        public void ShowStaff(bool on) { if (staff != null) staff.enabled = on; }

        // ------------------------------------------------------------------ avisos
        /// <summary>
        /// El miembro del golpe se enciende en el último tramo (como el filo de Enemy): de 1.5 a 5 de intensidad entre
        /// GlintLead y el cierre del anillo. Dorado = parry, rojo = dash. Pisa el jade de la postura en esa mano.
        /// </summary>
        public void Tell(string[] slots, bool danger, float k)
        {
            if (glint == null || slots == null) return;
            Color c = danger ? TellStyle.Crimson : TellStyle.Gold;
            float intensity = Mathf.Lerp(1.5f, 5f, k * k);
            for (int i = 0; i < slots.Length; i++)
            {
                glint.SetGlow(slots[i], c, intensity);
                if (!lit.Contains(slots[i])) lit.Add(slots[i]);
            }
        }

        public void ClearTell()
        {
            if (glint == null) return;
            for (int i = 0; i < lit.Count; i++) glint.SetGlow(lit[i], Color.black, 0f);
            lit.Clear();
            if (stanceGlow) ApplyStance();
        }

        /// <summary>Postura del bambú: las palmas (o el bastón) en jade suave. "No le pegues: esperá."</summary>
        public void SetStance(bool on)
        {
            if (stanceGlow == on) return;
            stanceGlow = on;
            ApplyStance();
        }

        void ApplyStance()
        {
            if (glint == null) return;
            float i = stanceGlow ? 1.6f : 0f;
            bool withStaff = StaffShown;
            glint.SetGlow(HandR, Jade, withStaff ? 0f : i);
            glint.SetGlow(HandL, Jade, withStaff ? 0f : i);
            glint.SetGlow(StaffGlow, Jade, withStaff ? i : 0f);
        }

        // ------------------------------------------------------------------ estelas del miembro que pega
        void BuildLimbTrails(Transform model)
        {
            var mat = Game.Content != null ? Game.Content.trailMaterial : null;
            Transform owner = model.parent != null ? model.parent : model;
            float s = model.lossyScale.y;
            foreach (var t in model.GetComponentsInChildren<Transform>(true))
            {
                // el slot del brillo, el hueso de la base y cuánto se estira la punta por su eje (m del modelo)
                string slot = t.name == "Hand_R" ? HandR : t.name == "Hand_L" ? HandL : t.name == "Toe_R" ? "Chikuo_GlintFootR"
                            : t.name == "Toe_L" ? "Chikuo_GlintFootL" : null;
                if (slot == null || limbTrails.ContainsKey(slot)) continue;
                bool foot = t.name.StartsWith("Toe");
                Transform basePt = foot ? t.parent : t;
                var tip = new GameObject(t.name + "_Estela").transform;
                tip.SetParent(t, false);
                tip.localPosition = t.InverseTransformPoint(t.position + t.up * (foot ? 0.12f : 0.21f) * s);
                limbTrails[slot] = BladeTrail.Create(owner, basePt, tip, mat, TellStyle.TrailParry);
            }
        }

        /// <summary>La estela del primer slot de 'slots' que es mano o pie (dorada o roja). false si no hay (el bastón usa la
        /// estela de Enemy).</summary>
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

        // ------------------------------------------------------------------ aro de la postura del bambú
        public bool StanceRingShown => stanceRing != null && stanceRing.gameObject.activeSelf;

        /// <summary>El aro de jade en el piso mientras dura la postura ("no le pegues"): se ve aunque las palmas queden
        /// tapadas o de espaldas a la cámara.</summary>
        public void ShowStanceRing(bool on, Transform owner = null)
        {
            if (!on) { if (stanceRing != null) stanceRing.Hide(); return; }
            if (stanceRing == null) stanceRing = ShockRing.Create(0.22f);
            ringOwner = owner;
            if (owner != null) stanceRing.Show(owner.position);
            TickStanceRing(9f);
        }

        /// <summary>Respira despacio y se apaga en el último medio segundo (va a bajar la guardia).</summary>
        public void TickStanceRing(float timeLeft)
        {
            if (!StanceRingShown) return;
            if (ringOwner != null) stanceRing.Show(ringOwner.position);
            float pulse = 0.5f + 0.5f * Mathf.Sin(Time.time * 4.2f);
            Color c = Jade * (1.2f + 0.5f * pulse);
            c.a = Mathf.Lerp(0.4f, 0.7f, pulse) * Mathf.Clamp01(timeLeft / 0.5f);
            stanceRing.Hold(StanceRingRadius, c);
        }

        /// <summary>Al morir: nada brilla salvo los ojos, que se apagan despacio (los apaga el jefe).</summary>
        public void Extinguish()
        {
            ClearTell();
            SetStance(false);
        }

        /// <summary>El aro de la postura no cuelga del jefe (va en el piso): se va con él.</summary>
        public void Dispose()
        {
            if (stanceRing != null) Object.Destroy(stanceRing.gameObject);
            stanceRing = null;
        }

        public void DimEyes(float k)
        {
            eyes = Mathf.Clamp01(k);
            glint?.SetGlow(Eyes, Jade, 2.2f * eyes);
        }
    }
}
