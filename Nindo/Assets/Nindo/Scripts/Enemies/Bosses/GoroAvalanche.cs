using System.Collections.Generic;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// La avalancha de Gorō (fase 2): la cumbre de Kodoyama es un cráter, así que la montaña rodea la arena y las rocas
    /// bajan por la pared de arriba de la pantalla y cruzan hacia la cámara. Cada OLA son 2-3 carriles paralelos:
    ///  * el carril rojo se pinta (shader Nindo/Telegraph, modo carril) y se llena hasta que la roca cae en su punto de
    ///    arranque; desde ahí rueda y el carril se achica detrás de ella: lo rojo es siempre lo que todavía puede pegar;
    ///  * un carril pasa por donde está Kaito (obliga a moverse) y los otros dejan pasillos de 2.8-3.6 m al costado;
    ///  * el arranque está SIEMPRE adentro de la cámara de juego (y de la arena): si la pantalla corta antes que la pared,
    ///    la roca entra de un rebote desde arriba y cae a la vista;
    ///  * entre el aviso y el golpe hay al menos MinWarning s (se alarga el aviso si el arranque queda cerca de Kaito):
    ///    alcanza con reaccionar y correr 1.5 m de costado (o un dash, que la atraviesa);
    ///  * una ola nueva se arma recién cuando todas las rocas de la anterior pasaron a Kaito: nunca hay dos olas
    ///    encimadas sobre él (Tools/Dev/goro_avalanche_check.py lo verifica con la cámara y la arena reales);
    ///  * las rocas se rompen contra la barrera del borde o contra el propio Gorō (la armadura de su montaña no le hace
    ///    nada): detrás de él no llegan.
    /// Las rocas no tienen física: rodar, rebotar y romperse es cuenta propia (barato y determinista). Sin asignaciones
    /// por cuadro: rocas, carriles y pedazos salen de listas reutilizadas.
    /// </summary>
    public class GoroAvalanche : MonoBehaviour
    {
        // tiempos (s) y distancias (m). Kaito corre a 6.2 m/s (PlayerConfig.runSpeed)
        public const float MinWarning = 1.35f, MinTell = 0.8f, DropTime = 0.5f, WaveGapMin = 1.1f;
        public const float GapMin = 2.8f, GapMax = 3.6f, KaitoPad = 0.35f;
        const float StartMinAhead = 0.5f, ViewTop = 0.86f, ViewBottom = 0.08f, ViewSide = 0.12f;
        // el arranque se corre este tanto hacia adentro del cuadro: Kaito se mueve y la cámara lo sigue mientras la roca
        // cae (sin esto ~1 de cada 5 arranques quedaba en el borde y salía de cuadro al correrse 1.5 m)
        const float StartBackoff = 1.8f;
        const int MaxEmptyWaves = 4;

        class Boulder
        {
            public Transform t, mesh, lane, mark;
            public MeshRenderer laneR, markR;
            public float r, speed, len, s, tTell, tLand, outT, seed, roll, nextDust;
            public Vector3 S, E, D, from, axis, prev;
            public Quaternion spin;
            public int stage;          // 0 avisando (y cayendo), 1 rodando, 2 roto (se apaga el carril), 3 libre
            public bool resolved, cued, onBoss;
        }

        class Shard
        {
            public Transform t;
            public Vector3 v, w;
            public float life, groundY, size;
        }

        readonly List<Boulder> boulders = new List<Boulder>();
        readonly List<Shard> shards = new List<Shard>();
        GoroBoss owner;
        Mesh[] boulderMeshes, shardMeshes;
        Material[][] boulderMats, shardMats;
        Mesh quad;
        Material laneMat;
        MaterialPropertyBlock mpb;
        float clock, nextWaveAt;
        int wave, waves, emptyWaves;
        float damage, knockback;
        int groundMask;

        static readonly int IdColor = Shader.PropertyToID("_Color"), IdHotColor = Shader.PropertyToID("_HotColor"), IdInk = Shader.PropertyToID("_Ink"),
            IdMode = Shader.PropertyToID("_Mode"), IdProgress = Shader.PropertyToID("_Progress"), IdHot = Shader.PropertyToID("_Hot"),
            IdFlash = Shader.PropertyToID("_Flash"), IdDanger = Shader.PropertyToID("_Danger"), IdAlpha = Shader.PropertyToID("_Alpha"),
            IdRadius = Shader.PropertyToID("_Radius"), IdWidth = Shader.PropertyToID("_Width"), IdDot = Shader.PropertyToID("_Dot"),
            IdMinPx = Shader.PropertyToID("_MinPx"), IdOutcome = Shader.PropertyToID("_Outcome"), IdOutT = Shader.PropertyToID("_OutT"),
            IdSeed = Shader.PropertyToID("_Seed");
        static readonly Color DangerHot = new Color(1f, 0.62f, 0.5f);
        static readonly Color SnowDust = new Color(0.92f, 0.95f, 1f);

        /// <summary>Quedan rocas por caer o rodando (el paso de Gorō espera a que termine).</summary>
        public bool Active => waves > 0 && wave < waves || AnyLive;
        bool AnyLive { get { foreach (var b in boulders) if (b.stage == 0 || b.stage == 1) return true; return false; } }

        public static GoroAvalanche Create(GoroBoss owner)
        {
            var go = new GameObject("AvalanchaGoro");
            go.transform.SetParent(owner.transform.parent, false);
            var av = go.AddComponent<GoroAvalanche>();
            av.owner = owner;
            return av;
        }

        void Awake()
        {
            groundMask = LayerMask.GetMask("Default");
            mpb = new MaterialPropertyBlock();
            var sh = Resources.Load<Shader>("Shaders/NindoTelegraph");
            if (sh != null && sh.isSupported) laneMat = new Material(sh) { name = "AvalanchaCarril" };
            quad = new Mesh { name = "AvalanchaQuad" };
            quad.vertices = new[] { new Vector3(-0.5f, 0, -0.5f), new Vector3(0.5f, 0, -0.5f), new Vector3(-0.5f, 0, 0.5f), new Vector3(0.5f, 0, 0.5f) };
            quad.uv = new[] { new Vector2(0, 0), new Vector2(1, 0), new Vector2(0, 1), new Vector2(1, 1) };
            quad.triangles = new[] { 0, 2, 1, 2, 3, 1 };
            quad.RecalculateBounds();
            LoadMeshes();
        }

        void OnDestroy()
        {
            if (laneMat != null) Destroy(laneMat);
            if (quad != null) Destroy(quad);
        }

        /// <summary>
        /// Las rocas del prop 'goro_boulders' (Tools/Blender/bosses/goro/build_goro_boulders.py: Boulder_* redondeadas para
        /// rodar, Shard_* para cuando se rompen). Sin el prop usa las rocas del mundo (más chatas, pero se leen).
        /// </summary>
        void LoadMeshes()
        {
            var c = Game.Content;
            var bm = new List<Mesh>(); var bmat = new List<Material[]>();
            var sm = new List<Mesh>(); var smat = new List<Material[]>();
            var prefab = c != null ? c.Prop("goro_boulders") : null;
            if (prefab != null)
                foreach (var mf in prefab.GetComponentsInChildren<MeshFilter>(true))
                {
                    var mr = mf.GetComponent<MeshRenderer>();
                    if (mf.sharedMesh == null || mr == null) continue;
                    if (mf.name.StartsWith("Boulder")) { bm.Add(mf.sharedMesh); bmat.Add(mr.sharedMaterials); }
                    else if (mf.name.StartsWith("Shard")) { sm.Add(mf.sharedMesh); smat.Add(mr.sharedMaterials); }
                }
            if (bm.Count == 0) AddPropMeshes(c, "rock_snow_a", bm, bmat);
            if (bm.Count == 0) AddPropMeshes(c, "rock_medium_b", bm, bmat);
            if (sm.Count == 0) { AddPropMeshes(c, "rock_small_a", sm, smat); AddPropMeshes(c, "rock_small_b", sm, smat); }
            boulderMeshes = bm.ToArray(); boulderMats = bmat.ToArray();
            shardMeshes = sm.ToArray(); shardMats = smat.ToArray();
        }

        static void AddPropMeshes(NindoContent c, string id, List<Mesh> meshes, List<Material[]> mats)
        {
            var p = c != null ? c.Prop(id) : null;
            if (p == null) return;
            foreach (var mf in p.GetComponentsInChildren<MeshFilter>(true))
            {
                var mr = mf.GetComponent<MeshRenderer>();
                if (mf.sharedMesh != null && mr != null && !mf.name.StartsWith("COL")) { meshes.Add(mf.sharedMesh); mats.Add(mr.sharedMaterials); return; }
            }
        }

        // ================================================================== API (GoroBoss)
        /// <summary>Arranca la avalancha: 'count' olas, la primera ya. Daño y empuje de cada roca.</summary>
        public void Begin(int count, float dmg, float kb)
        {
            waves = count; wave = 0; emptyWaves = 0;
            damage = dmg; knockback = kb;
            nextWaveAt = clock;
        }

        /// <summary>Corta todo (reintento, muerte de Gorō): las rocas que quedan se rompen donde están.</summary>
        public void Clear(bool breakFx)
        {
            waves = wave = 0;
            foreach (var f in flung) if (f.live) { f.live = false; f.t.gameObject.SetActive(false); }
            foreach (var b in boulders)
            {
                if (b.stage == 1 && breakFx) Break(b);
                else if (b.stage <= 1) Free(b);
            }
        }

        /// <summary>
        /// Segundos hasta que la próxima roca le pegue a 'p' (infinito si ninguna viene hacia ahí) y el carril de esa roca
        /// (Gorō lo devuelve como su zona de golpe: el bot y StrikeCanReach la miran).
        /// </summary>
        public float NextEta(Vector3 p, out TellArea area)
        {
            area = default;
            float best = float.PositiveInfinity;
            foreach (var b in boulders)
            {
                float eta = Eta(b, p);
                if (eta < best) { best = eta; area = LaneArea(b); }
            }
            return best;
        }

        TellArea LaneArea(Boulder b)
        {
            Vector3 o = b.stage == 0 ? b.S : b.S + b.D * b.s;
            return new TellArea { lane = true, origin = o, forward = b.D, size = Mathf.Max(0.1f, b.len - (b.stage == 0 ? 0f : b.s)), width = 2f * (b.r + KaitoPad) };
        }

        /// <summary>Lo que falta para que la roca 'b' alcance a 'p' (rodando por su carril).</summary>
        float Eta(Boulder b, Vector3 p)
        {
            if (b.resolved || b.stage > 1) return float.PositiveInfinity;
            Vector3 d = (p - b.S).Flat();
            float along = Vector3.Dot(d, b.D);
            float lat = Mathf.Abs(Vector3.Dot(d, Vector3.Cross(Vector3.up, b.D)));
            float reach = b.r + KaitoPad;
            if (lat > reach || along > b.len + reach) return float.PositiveInfinity;
            float front = b.stage == 0 ? 0f : b.s;
            float gap = along - reach - front;
            if (gap < -2f * reach) return float.PositiveInfinity;   // ya pasó
            float pre = b.stage == 0 ? Mathf.Max(0f, b.tLand - clock) : 0f;
            return pre + Mathf.Max(0f, gap) / b.speed;
        }

        // ================================================================== por cuadro
        void Update()
        {
            float dt = Time.deltaTime;
            if (dt <= 0f) return;
            clock += dt;
            var p = Game.Player;
            if (waves > 0 && wave < waves && clock >= nextWaveAt && p != null && p.IsAlive && owner != null && owner.IsAlive && NonePending(p.transform.position))
                PlanWave(p);
            for (int i = 0; i < boulders.Count; i++) TickBoulder(boulders[i], p, dt);
            TickFlung();
            TickShards(dt);
        }

        /// <summary>¿Todas las rocas vivas ya pasaron la línea de Kaito (o no le apuntan y están lejos)?</summary>
        bool NonePending(Vector3 k)
        {
            foreach (var b in boulders)
            {
                if (b.stage == 0) return false;
                if (b.stage != 1) continue;
                float along = Vector3.Dot((k - b.S).Flat(), b.D);
                if (b.s - b.r < along + KaitoPad + 0.5f) return false;
            }
            return true;
        }

        // ------------------------------------------------------------------ armar una ola
        void PlanWave(PlayerController p)
        {
            var cam = Game.Camera != null ? Game.Camera.Cam : Camera.main;
            if (cam == null) { waves = 0; return; }
            Vector3 k = p.transform.position;
            // bajan hacia la cámara (de arriba de la pantalla): es el lado de la arena que más se ve
            Vector3 down = -cam.transform.forward.Flat().normalized;
            if (down.sqrMagnitude < 0.01f) down = Vector3.back;
            Vector3 dir = Quaternion.Euler(0f, Random.Range(-14f, 14f), 0f) * down;
            Vector3 side = Vector3.Cross(Vector3.up, dir);
            float speed = 8.5f + 0.5f * wave;
            float r = Random.Range(0.75f, 0.9f);
            float w = 2f * (r + KaitoPad);
            // carriles: uno por Kaito y pasillos de GapMin-GapMax a los costados (la primera ola, uno solo al lado)
            int n = wave == 0 ? 2 : 3;
            float sgn = Random.value < 0.5f ? -1f : 1f;
            float a = w + Random.Range(GapMin, GapMax), b2 = w + Random.Range(GapMin, GapMax);
            int planned = 0;
            float tLand = 0f;
            for (int i = 0; i < n; i++)
            {
                float x = i == 0 ? 0f : i == 1 ? sgn * a : -sgn * b2;
                Vector3 bas = k + side * x;
                if (!LaneFor(bas, dir, r, cam, out Vector3 S, out Vector3 E, out bool onBoss)) continue;
                float ahead = Vector3.Dot((k - S).Flat(), dir);
                // aviso: lo que haga falta para que entre el aviso y el golpe haya MinWarning s (nunca menos de MinTell)
                float tell = Mathf.Max(MinTell, MinWarning - Mathf.Max(0f, ahead - r - KaitoPad) / speed);
                if (planned == 0) tLand = clock + tell;
                var bo = Acquire(r);
                bo.S = S; bo.E = E; bo.D = dir; bo.speed = speed * Random.Range(0.96f, 1.04f);
                bo.len = Vector3.Dot((E - S).Flat(), dir);
                bo.tTell = clock;
                // las de los costados caen un poco después: se lee como un derrumbe, no como una fila
                bo.tLand = Mathf.Max(tLand, clock + tell) + 0.12f * planned;
                bo.onBoss = onBoss;
                bo.from = S - dir * 5f + Vector3.up * 6.5f;
                bo.axis = side;
                bo.s = 0f; bo.roll = 0f; bo.nextDust = 0f;
                bo.prev = S;
                bo.stage = 0; bo.resolved = bo.cued = false; bo.outT = 0f;
                bo.seed = Random.value * 10f;
                bo.spin = Random.rotation;
                bo.t.SetPositionAndRotation(bo.from, bo.spin);
                bo.t.gameObject.SetActive(false);
                planned++;
            }
            // sin carril posible (Kaito pegado a la pared de arriba): se reintenta enseguida, unas pocas veces
            if (planned == 0 && ++emptyWaves <= MaxEmptyWaves) { nextWaveAt = clock + 0.3f; return; }
            wave++;
            if (planned == 0) { nextWaveAt = clock + 0.3f; return; }
            nextWaveAt = clock + WaveGapMin;
            // el taiko del imparable y el retumbe que baja de la pared
            Game.Audio?.Play("tell_danger", null, 0.9f, 0.03f);
            Game.Audio?.Play("avalanche_rumble", k - dir * 12f, 0.9f);
            Game.Camera?.Shake(0.2f);
            Game.Input?.Rumble(0.35f, 0.15f, 0.5f);
        }

        /// <summary>
        /// Carril que pasa por 'bas' en la dirección 'dir': arranca donde se ve (adentro de la cámara y de la arena, lo más
        /// arriba posible) y termina contra la barrera o contra Gorō. false si no queda carril (muy corto o tapado).
        /// </summary>
        bool LaneFor(Vector3 bas, Vector3 dir, float r, Camera cam, out Vector3 S, out Vector3 E, out bool onBoss)
        {
            S = E = bas; onBoss = false;
            Vector3 c = owner.arenaCenter;
            float rim = owner.arenaRadius + 1f - r - 0.15f;     // la barrera está a arenaRadius + 1 (BossArena)
            if ((bas - c).Flat().magnitude > rim) return false;
            // hacia arriba (contra 'dir') hasta salir de la arena o de la pantalla
            float up = 0f;
            const float Step = 0.25f;
            for (float s = Step; s < 40f; s += Step)
            {
                Vector3 q = bas - dir * s;
                if ((q - c).Flat().magnitude > rim || !InView(cam, q, r)) break;
                up = s;
            }
            up = Mathf.Min(up, Mathf.Max(StartMinAhead, up - StartBackoff));
            if (up < StartMinAhead) return false;
            float down = 0f;
            for (float s = Step; s < 40f; s += Step)
            {
                if (((bas + dir * s) - c).Flat().magnitude > rim) break;
                down = s;
            }
            S = Ground(bas - dir * up);
            E = Ground(bas + dir * down);
            // Gorō en el carril: la roca se rompe contra él
            Vector3 g = owner.transform.position;
            Vector3 dg = (g - S).Flat();
            float ga = Vector3.Dot(dg, dir), gl = Mathf.Abs(Vector3.Dot(dg, Vector3.Cross(Vector3.up, dir)));
            float hit = owner.Radius + r;
            float len = up + down;
            if (ga > 0f && ga < len && gl < hit)
            {
                float stop = ga - Mathf.Sqrt(hit * hit - gl * gl);
                if (stop < 2f) return false;
                E = Ground(S + dir * stop);
                onBoss = true;
                len = stop;
            }
            return len >= 3f;
        }

        static bool InView(Camera cam, Vector3 q, float r)
        {
            Vector3 v = cam.WorldToViewportPoint(q + Vector3.up * r);
            return v.z > 0f && v.x > ViewSide && v.x < 1f - ViewSide && v.y > ViewBottom && v.y < ViewTop;
        }

        Vector3 Ground(Vector3 q)
        {
            if (Physics.Raycast(q + Vector3.up * 6f, Vector3.down, out var hit, 14f, groundMask, QueryTriggerInteraction.Ignore)) q.y = hit.point.y;
            return q;
        }

        // ------------------------------------------------------------------ una roca
        void TickBoulder(Boulder b, PlayerController p, float dt)
        {
            if (b.stage == 3) return;
            if (b.stage == 2)
            {
                b.outT += dt / 0.2f;
                if (b.outT >= 1f) Free(b);
                else DrawLane(b);
                return;
            }
            if (b.stage == 0)
            {
                // cae del rebote en la pared los últimos DropTime s del aviso
                float k = 1f - (b.tLand - clock) / DropTime;
                if (k >= 0f && !b.t.gameObject.activeSelf) b.t.gameObject.SetActive(true);
                if (k >= 0f)
                {
                    k = Mathf.Min(1f, k);
                    Vector3 q = Vector3.Lerp(b.from, b.S, k);
                    q.y = Mathf.Lerp(b.from.y, b.S.y + b.r, k * k) + 1.2f * Mathf.Sin(k * Mathf.PI) * (1f - k);
                    b.t.SetPositionAndRotation(q, Quaternion.AngleAxis(420f * k, b.axis) * b.spin);
                }
                if (clock >= b.tLand) Land(b);
            }
            else
            {
                b.prev = b.t.position;
                float step = b.speed * dt;
                b.s = Mathf.Min(b.len, b.s + step);
                b.roll += step / b.r * Mathf.Rad2Deg;
                Vector3 q = Ground(b.S + b.D * b.s);
                // tumbos chicos: no es una bola perfecta
                q.y += b.r + 0.1f * Mathf.Abs(Mathf.Sin(b.roll * Mathf.Deg2Rad * 0.5f + b.seed));
                // eje = arriba x dirección (el costado): con ángulo positivo el frente de la roca baja, rueda hacia adelante
                b.t.SetPositionAndRotation(q, Quaternion.AngleAxis(b.roll, b.axis) * b.spin);
                if (clock >= b.nextDust)
                {
                    b.nextDust = clock + 0.09f;
                    Game.FX?.DustTrail(q - Vector3.up * b.r);
                }
                if (!b.resolved && p != null && p.IsAlive) TryHit(b, p);
                if (b.s >= b.len - 1e-3f) { Break(b); return; }
            }
            // el aviso a tiempo de reacción (el toc de madera y el evento que escucha el bot), una vez por roca
            if (!b.cued && p != null && p.IsAlive && AudioManager.CueDue(Eta(b, p.transform.position), TellStyle.TickUnblockable))
            {
                b.cued = true;
                Game.Audio?.Play("tell_tick", null, 0.8f, 0.03f);
                GameEvents.RaiseStrikeCue(owner, true);
            }
            DrawLane(b);
        }

        void Land(Boulder b)
        {
            b.stage = 1;
            b.t.gameObject.SetActive(true);
            Vector3 g = b.S;
            Game.FX?.Dust(g, 1.6f);
            Game.FX?.GroundCrack(g, b.r * 1.6f);
            Game.Audio?.Play("rock_impact", g, 0.9f);
            Game.Audio?.Play("boulder_roll", g, 0.8f);
            Game.Camera?.Shake(0.15f);
        }

        void TryHit(Boulder b, PlayerController p)
        {
            Vector3 k = p.transform.position;
            Vector3 a = b.prev, c = b.t.position;
            // contra el tramo que recorrió en este cuadro: a 20 fps avanza ~0.45 m
            Vector3 ab = (c - a).Flat();
            float u = ab.sqrMagnitude > 1e-6f ? Mathf.Clamp01(Vector3.Dot((k - a).Flat(), ab) / ab.sqrMagnitude) : 0f;
            Vector3 q = a + ab * u;
            if (CombatMath.FlatDistance(q, k) > b.r + KaitoPad || Mathf.Abs(k.y - (q.y - b.r)) > 2f) return;
            Vector3 lat = Vector3.Project((k - q).Flat(), b.axis);
            Vector3 dir = (b.D + (lat.sqrMagnitude > 1e-4f ? lat.normalized * 0.8f : Vector3.zero)).normalized;
            var info = new DamageInfo
            {
                damage = damage, kind = AttackKind.Unblockable, direction = dir, point = p.AimPoint, knockback = knockback,
                sourceFaction = Faction.Enemy, source = owner, attackName = "Avalancha", imbalance = 0f,
            };
            var r = p.ReceiveHit(info);
            // la esquivó con el dash (o le pegó): esta roca ya no vuelve a pegar
            if (r != HitResult.Ignored) b.resolved = true;
            if (r == HitResult.Hit || r == HitResult.Killed)
            {
                Game.FX?.Dust(k, 1.2f);
                Game.Audio?.Play("rock_impact", k, 1f);
            }
        }

        /// <summary>Se rompe contra la barrera o contra Gorō: pedazos, polvo de nieve, crujido.</summary>
        void Break(Boulder b)
        {
            Vector3 c = b.t.position;
            b.stage = 2; b.outT = 0f; b.resolved = true;
            b.t.gameObject.SetActive(false);
            Game.FX?.Dust(c, 1.8f);
            Game.FX?.SmokePuff(c, 1.1f);
            Game.Audio?.Play("boulder_break", c, 0.9f);
            Game.Camera?.Shake(0.12f);
            EmitShards(c, b.r, b.onBoss ? -b.D : b.D, 6);
        }

        /// <summary>Pedazos que saltan de una roca rota (radio r, con un empuje hacia 'bias').</summary>
        void EmitShards(Vector3 c, float r, Vector3 bias, int n)
        {
            if (shardMeshes == null || shardMeshes.Length == 0) return;
            float gy = c.y - r;
            for (int i = 0; i < n; i++)
            {
                var s = AcquireShard(i);
                if (s == null) break;
                Vector3 outward = (Random.onUnitSphere.Flat() * 0.8f + bias.Flat() * 0.6f).normalized;
                s.t.SetPositionAndRotation(c + Random.insideUnitSphere * r * 0.5f, Random.rotation);
                s.v = outward * Random.Range(2.5f, 5f) + Vector3.up * Random.Range(3f, 6f);
                s.w = Random.onUnitSphere * Random.Range(300f, 700f);
                s.size = r * Random.Range(0.35f, 0.6f);
                s.t.localScale = Vector3.one * s.size;
                s.life = 0f;
                s.groundY = gy;
            }
        }

        // ------------------------------------------------------------------ rocas sueltas (cinemática de la armadura)
        class Flung
        {
            public Transform t, mesh;
            public Vector3 a, b, axis;
            public float t0, dur, arc, spin, r;
            public bool live;
        }

        readonly List<Flung> flung = new List<Flung>();

        /// <summary>
        /// Una roca que se desprende de la pared y cae cerca de Gorō mientras se arma (no se le pega: se rompe en el piso).
        /// Junto con las 16 piezas de la armadura hacen la lluvia de rocas de la montaña. Sin daño.
        /// </summary>
        public void Fling(Vector3 from, Vector3 to, float delay, float dur, float r)
        {
            if (boulderMeshes == null || boulderMeshes.Length == 0) return;
            Flung f = null;
            foreach (var x in flung) if (!x.live) { f = x; break; }
            if (f == null)
            {
                if (flung.Count >= 24) return;
                f = new Flung();
                var go = new GameObject("RocaSuelta");
                go.transform.SetParent(transform, false);
                f.t = go.transform;
                var mg = new GameObject("Malla");
                mg.transform.SetParent(f.t, false);
                f.mesh = mg.transform;
                mg.AddComponent<MeshFilter>();
                mg.AddComponent<MeshRenderer>();
                flung.Add(f);
            }
            int i = Random.Range(0, boulderMeshes.Length);
            f.mesh.GetComponent<MeshFilter>().sharedMesh = boulderMeshes[i];
            f.mesh.GetComponent<MeshRenderer>().sharedMaterials = boulderMats[i];
            var bounds = boulderMeshes[i].bounds;
            float k = 2f * r / Mathf.Max(0.1f, Mathf.Max(bounds.size.x, Mathf.Max(bounds.size.y, bounds.size.z)));
            f.mesh.localScale = Vector3.one * k;
            f.mesh.localPosition = -bounds.center * k;
            f.a = from; f.b = Ground(to) + Vector3.up * r;
            f.t0 = clock + delay; f.dur = Mathf.Max(0.2f, dur); f.r = r;
            f.arc = 1.5f + 0.15f * Vector3.Distance(from, to);
            f.axis = Vector3.Cross(Vector3.up, (to - from).Flat().normalized);
            f.spin = Random.Range(360f, 720f);
            f.live = true;
            f.t.gameObject.SetActive(false);
        }

        void TickFlung()
        {
            foreach (var f in flung)
            {
                if (!f.live || clock < f.t0) continue;
                float u = (clock - f.t0) / f.dur;
                if (u >= 1f)
                {
                    f.live = false;
                    f.t.gameObject.SetActive(false);
                    Game.FX?.Dust(f.b, 1.3f);
                    Game.FX?.GroundCrack(f.b - Vector3.up * f.r, f.r * 1.4f);
                    Game.Audio?.Play("rock_impact", f.b, 0.6f);
                    EmitShards(f.b, f.r, (f.b - f.a).Flat().normalized, 3);
                    continue;
                }
                if (!f.t.gameObject.activeSelf) { f.t.gameObject.SetActive(true); Game.FX?.Dust(f.a, 1.1f); }
                Vector3 q = Vector3.Lerp(f.a, f.b, u) + Vector3.up * (f.arc * 4f * u * (1f - u));
                f.t.SetPositionAndRotation(q, Quaternion.AngleAxis(f.spin * u, f.axis));
            }
        }

        void Free(Boulder b)
        {
            b.stage = 3;
            if (b.t != null) b.t.gameObject.SetActive(false);
            if (b.laneR != null) b.laneR.enabled = false;
            if (b.markR != null) b.markR.enabled = false;
        }

        // ------------------------------------------------------------------ dibujo del carril
        void DrawLane(Boulder b)
        {
            if (laneMat == null || !Settings.ShowUnblockableAids) { b.laneR.enabled = false; b.markR.enabled = false; return; }
            float startS = b.stage == 1 ? b.s : 0f;
            float size = Mathf.Max(0.05f, b.len - startS);
            Vector3 o = b.S + b.D * startS;
            Vector3 mid = o + b.D * (size * 0.5f);
            mid.y = Mathf.Lerp(b.S.y, b.E.y, (startS + size * 0.5f) / Mathf.Max(0.1f, b.len)) + 0.06f;
            float width = 2f * (b.r + KaitoPad);
            b.lane.SetPositionAndRotation(mid, Quaternion.LookRotation(b.D, Vector3.up));
            b.lane.localScale = new Vector3(width * 1.1f, 1f, size * 1.04f);
            float prog = b.stage == 0 ? Mathf.Clamp01((clock - b.tTell) / Mathf.Max(0.05f, b.tLand - b.tTell)) : 1f;
            float fadeIn = Mathf.Clamp01((clock - b.tTell) / 0.15f);
            mpb.Clear();
            mpb.SetColor(IdColor, TellStyle.Crimson);
            mpb.SetColor(IdHotColor, DangerHot);
            mpb.SetColor(IdInk, TellStyle.Ink);
            mpb.SetFloat(IdMode, 2f);
            mpb.SetFloat(IdProgress, prog);
            mpb.SetFloat(IdHot, 0f);
            mpb.SetFloat(IdFlash, 0f);
            mpb.SetFloat(IdDanger, 1f);
            mpb.SetFloat(IdAlpha, fadeIn);
            mpb.SetFloat(IdRadius, 1f / 1.1f);
            mpb.SetFloat(IdWidth, 1f / 1.04f);
            mpb.SetFloat(IdDot, 0.02f);
            mpb.SetFloat(IdMinPx, 16f);
            mpb.SetFloat(IdOutcome, b.stage == 2 ? 3f : 0f);
            mpb.SetFloat(IdOutT, b.stage == 2 ? b.outT : 0f);
            mpb.SetFloat(IdSeed, b.seed);
            b.laneR.enabled = true;
            b.laneR.SetPropertyBlock(mpb);
            // marca de dónde cae: se llena con el aviso (mientras la roca todavía está en el aire)
            bool mark = b.stage == 0;
            b.markR.enabled = mark;
            if (!mark) return;
            Vector3 m = b.S; m.y += 0.07f;
            float rad = b.r + 0.35f;
            b.mark.SetPositionAndRotation(m, Quaternion.identity);
            b.mark.localScale = new Vector3(rad * 2.12f, 1f, rad * 2.12f);
            mpb.SetFloat(IdMode, 1f);
            mpb.SetFloat(IdRadius, 1f / 1.06f);
            mpb.SetFloat(IdAlpha, fadeIn);
            b.markR.SetPropertyBlock(mpb);
        }

        // ------------------------------------------------------------------ pedazos
        void TickShards(float dt)
        {
            foreach (var s in shards)
            {
                if (!s.t.gameObject.activeSelf) continue;
                s.life += dt;
                if (s.life > 1.6f) { s.t.gameObject.SetActive(false); continue; }
                s.v += Vector3.down * 20f * dt;
                Vector3 q = s.t.position + s.v * dt;
                if (q.y < s.groundY + s.size * 0.3f && s.v.y < 0f) { q.y = s.groundY + s.size * 0.3f; s.v = new Vector3(s.v.x * 0.45f, -s.v.y * 0.3f, s.v.z * 0.45f); s.w *= 0.5f; }
                float shrink = s.life > 1.1f ? 1f - (s.life - 1.1f) / 0.5f : 1f;
                s.t.SetPositionAndRotation(q, Quaternion.Euler(s.w * dt) * s.t.rotation);
                s.t.localScale = Vector3.one * (s.size * Mathf.Max(0.01f, shrink));
            }
        }

        // ------------------------------------------------------------------ listas reutilizadas
        Boulder Acquire(float r)
        {
            Boulder b = null;
            foreach (var x in boulders) if (x.stage == 3) { b = x; break; }
            if (b == null)
            {
                b = new Boulder();
                var go = new GameObject("Roca");
                go.transform.SetParent(transform, false);
                b.t = go.transform;
                var mg = new GameObject("Malla");
                mg.transform.SetParent(b.t, false);
                b.mesh = mg.transform;
                mg.AddComponent<MeshFilter>();
                mg.AddComponent<MeshRenderer>();
                b.lane = NewQuad("Carril", out b.laneR);
                b.mark = NewQuad("Caida", out b.markR);
                boulders.Add(b);
            }
            b.r = r;
            // una de las rocas, centrada (rueda sobre su centro) y escalada a 2r de diámetro
            if (boulderMeshes != null && boulderMeshes.Length > 0)
            {
                int i = Random.Range(0, boulderMeshes.Length);
                var mf = b.mesh.GetComponent<MeshFilter>();
                mf.sharedMesh = boulderMeshes[i];
                b.mesh.GetComponent<MeshRenderer>().sharedMaterials = boulderMats[i];
                var bounds = boulderMeshes[i].bounds;
                float k = 2f * r / Mathf.Max(0.1f, Mathf.Max(bounds.size.x, Mathf.Max(bounds.size.y, bounds.size.z)));
                b.mesh.localScale = Vector3.one * k;
                b.mesh.localPosition = -bounds.center * k;
            }
            return b;
        }

        Shard AcquireShard(int salt)
        {
            Shard s = null;
            foreach (var x in shards) if (!x.t.gameObject.activeSelf) { s = x; break; }
            if (s == null)
            {
                if (shards.Count >= 30) return null;
                s = new Shard();
                var go = new GameObject("Pedazo");
                go.transform.SetParent(transform, false);
                s.t = go.transform;
                go.AddComponent<MeshFilter>();
                go.AddComponent<MeshRenderer>();
                shards.Add(s);
            }
            int i = (salt + Random.Range(0, shardMeshes.Length)) % shardMeshes.Length;
            s.t.GetComponent<MeshFilter>().sharedMesh = shardMeshes[i];
            s.t.GetComponent<MeshRenderer>().sharedMaterials = shardMats[i];
            s.t.gameObject.SetActive(true);
            return s;
        }

        Transform NewQuad(string name, out MeshRenderer mr)
        {
            var go = new GameObject(name);
            go.transform.SetParent(transform, false);
            go.AddComponent<MeshFilter>().sharedMesh = quad;
            mr = go.AddComponent<MeshRenderer>();
            mr.sharedMaterial = laneMat;
            mr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            mr.receiveShadows = false;
            mr.enabled = false;
            return go.transform;
        }
    }
}
