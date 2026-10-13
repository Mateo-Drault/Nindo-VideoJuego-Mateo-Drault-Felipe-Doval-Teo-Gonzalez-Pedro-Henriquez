using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Cómo se mueve el cuerpo del enemigo, aparte de la IA de Enemy.cs:
    ///  * locomoción direccional: rodeando a Kaito (TickStrafe) el enemigo lo mira y se mueve de costado o para atrás. Con
    ///    un controller que trae el blend tree 2D (VelX/VelZ: Walk, WalkBack, StrafeL y StrafeR alrededor de un LocoIdle
    ///    quieto, todos del largo de Walk, y Run en el 1D de afuera) se le pasa la velocidad en su marco y Unity mezcla el
    ///    paso con la dirección y el largo reales: los pies no patinan a ninguna velocidad ni en diagonal (ver
    ///    DriveDirectional). Quieto un rato pasa al Idle que respira. Sin esos parámetros queda el blend tree 1D de siempre;
    ///  * de vuelta a su lugar sin pelea (perdió a Kaito): mira adonde camina, al llegar gira a como estaba y retoma lo que
    ///    hacía antes (EnemyAmbient: meditar, practicar, dormir...);
    ///  * los clips de variante: un golpe de zona con clip propio (Whirl, Leap, Morote, HopBack...) vuelve al de siempre con
    ///    sus tiempos si el controller no lo tiene (AttackClipFallback);
    ///  * la embestida en cuadros del clip (AttackDef.lungeFrom): el transform recorre en cada cuadro entero del clip lo que
    ///    el clip se autoró (team_moves.clip_lunge_travel) y entre cuadros interpola como el clip. Con el avance lineal en el
    ///    tiempo y la suelta del clip acelerando (u², StepTimeline) el transform se iba hasta 0.6 m por delante en el primer
    ///    cuadro de la suelta: los pies apoyados patinaban 35-45 cm en la estocada y 8-13 cm en los cortes;
    ///  * el imán del golpe: si Kaito está pegado, la embestida del transform se corta (no lo atraviesa). En el aire (saltos)
    ///    el recorrido se decide al despegar y cae más corto; en el piso el sumo arrastra a Kaito con la panza (lungeShove) y
    ///    lo que igual no entra lo sigue el MODELO hasta 'lungeSlack' metros (el cuerpo visible está más adentro que la
    ///    cápsula), que se le devuelve al transform en cuanto hay lugar, sin que nada se mueva en pantalla;
    ///  * el golpe en el lugar: si Kaito no se deja arrastrar (contra la barrera, una pared u otro enemigo, en el dash) y
    ///    el paso no entra, un golpe con variante '<estado>Planted' sale en ella, sin avanzar (DecidePlant).
    /// </summary>
    public partial class Enemy
    {
        public const string StrafeLState = "StrafeL", StrafeRState = "StrafeR", WalkBackState = "WalkBack";
        const string IdleState = "Idle";

        // quieto (m/s) este tiempo (s) en el blend tree: al Idle que respira; sale apenas se mueve
        const float IdleEnter = 0.12f, IdleExit = 0.3f, IdleAfter = 0.3f;
        // los cuadros por segundo de los clips del equipo (Tools/Blender/anim: team_rig.FPS)
        const float ClipFps = 30f;
        // la embestida en cuadros del clip termina un poco después del golpe y no pasa de esto (m/s, en lo más rápido)
        const float MaxClipLunge = 16f;
        // arranca acelerando y, en el piso, termina frenando en estas partes del recorrido (team_moves.LUNGE_EASE): con un
        // arranque seco el clip (que Unity interpola con curvas suaves entre cuadros) y el transform se separaban justo
        // donde el pie despega o queda clavado
        const float LungeAccel = 0.2f, LungeBrake = 0.2f;
        // un salto con Kaito cerca cae donde lo frenaría el imán, nunca más corto que esta parte de su embestida
        const float AirMinShare = 0.35f;
        // la variante en el lugar de un golpe con paso (TeamAnims/GoroAnims: '<estado>Planted', el mismo clip hasta la
        // suelta): se elige este tiempo (s) antes de la suelta y se cruza en ese tiempo, con los dos clips todavía iguales.
        // Un paso que no entra por menos de PlantSlack (m) sigue con el paso: el imán corta ese resto
        public const string PlantedSuffix = "Planted";
        const float PlantLead = 0.1f, PlantSlack = 0.03f;
        // el imán frena el transform a esta distancia (m) de la cápsula de Kaito
        const float MagnetGap = 0.3f;

        float stillFor;
        int idleMode = -1;          // 1 = el blend tree es direccional y existe el estado Idle (se mira una vez)
        float clipScale = -1f;      // m/s del mundo por m/s del clip (la variante y la escala del modelo)

        // embestida que el imán cortó y el modelo siguió adelante (m, en el frente del transform)
        float lungeWarp;
        // embestida en cuadros del clip: recorrido total (m), lo que ya pidió el clip, lo que arrastró a Kaito
        bool clipLunge, lungeDecided;
        float lungeLen, lungeTravel, shoved, lungeBrake;
        // el margen del imán en esta embestida: MagnetGap o, si Kaito ya estaba más cerca (se le metió encima atacando), el
        // que había. Con los 0.3 m de siempre el empujón primero lo corría hasta recuperarlos con el transform quieto, y eso
        // que no avanzaba lo patinaba el pie de atrás (30 cm con Kaito pegado a la cápsula de Gorō)
        float lungeGap = MagnetGap;
        int lungeFrames;
        // el recorrido con el que se autoró el clip (m) y lo que lleva hecho en el primer cuadro en el aire (lungeKeep): un
        // salto decidido más corto recorre igual hasta ahí (ver Knot)
        float lungeFull, lungeKeepAt;
        int lungeKeep;
        // el estado del Animator del paso: el de AttackDef, o su espejo si el salto de costado va para el otro lado, o su
        // variante en el lugar (planted)
        string stepState;
        bool plantDecided, planted;

        /// <summary>Corrimiento local del modelo respecto de su pose base (la embestida cortada por el imán): VariantMotion
        /// lo suma cuando escribe la posición del modelo (los saltos de zona).</summary>
        public Vector3 ModelNudge { get; private set; }

        /// <summary>Está en su locomoción (el blend tree o el Idle que respira): ahí VariantMotion pone su sabor.</summary>
        public bool InLocomotionPose => anim.Current == config.animLocomotion || (UsesIdleState && anim.Current == IdleState);

        bool UsesIdleState
        {
            get
            {
                if (idleMode < 0) idleMode = anim.HasDirectional && anim.HasState(IdleState) ? 1 : 0;
                return idleMode == 1;
            }
        }

        float ClipScale
        {
            get
            {
                if (clipScale < 0f)
                {
                    // los clips pisan a la velocidad de caminar del arquetipo: la variante la multiplica (y su Animator va a ese
                    // ritmo, VariantMotion.moveSpeed) y el modelo escalado da pasos más largos
                    var vm = model != null ? model.GetComponent<VariantMotion>() : null;
                    clipScale = Mathf.Max(0.1f, vm != null ? vm.moveSpeed : 1f) * Mathf.Max(0.3f, config.scale);
                }
                return clipScale;
            }
        }

        /// <summary>
        /// Locomoción del cuerpo en Chase / Strafe / Idle (llamado desde Enemy.Update). Los controllers no tienen
        /// transiciones: al volver a moverse hay que reentrar a la locomoción, si no se desliza congelado en la última pose
        /// (fin de Spotted, Guard, Hit, Counter, intro de jefe...).
        /// </summary>
        void TickLocomotionAnim(float dt)
        {
            bool moving = State == EnemyState.Chase || State == EnemyState.Strafe || State == EnemyState.Idle;
            if (!moving || (Ambient != null && Ambient.HoldsPose)) { stillFor = 0f; return; }
            // Chase y Strafe se alternan seguido rodeando (se compromete, se aleja): la locomoción sigue entre los dos
            if (stateTime <= 0.02f) return;
            Vector3 vel = useAgent ? agent.velocity.Flat() : Vector3.zero;
            float speed = vel.magnitude;
            if (State == EnemyState.Idle && !IsAggro) TickHome(vel, speed, dt);

            bool idle = UsesIdleState && anim.Current == IdleState;
            // fuera de la locomoción (otro estado, o el jefe que cambió animLocomotion): de vuelta a ella
            if (anim.Current != config.animLocomotion && !idle)
            {
                anim.Play(config.animLocomotion, 0.15f);
                return;
            }
            if (!anim.HasDirectional) return;
            stillFor = speed < IdleEnter ? stillFor + dt : 0f;
            if (idle)
            {
                if (speed > IdleExit) anim.Play(config.animLocomotion, 0.2f);
                return;
            }
            if (UsesIdleState && stillFor >= IdleAfter)
            {
                anim.Play(IdleState, 0.35f);
                return;
            }
            DriveDirectional(vel, dt);
        }

        /// <summary>
        /// La velocidad en el marco del enemigo, en m/s del clip, para el blend tree 2D Simple Directional: Unity mezcla en el
        /// triángulo de dos ciclos vecinos del anillo y el centro quieto con pesos baricéntricos, así que el paso mezclado camina
        /// justo la velocidad que se le pasa (a cualquier velocidad y en diagonal) mientras caiga dentro del triángulo. Más allá
        /// de la cuerda entre los dos vecinos (en diagonal a velocidad de caminar: hasta 0.71 del anillo) se le pasa el punto
        /// de la cuerda y el ritmo sube lo que falta (hasta 1.41). Corriendo (más que caminar, siempre hacia adelante) el 2D
        /// queda en el anillo y el 1D de afuera (Speed) mezcla con Run como siempre.
        /// </summary>
        void DriveDirectional(Vector3 vel, float dt)
        {
            Vector3 l = transform.InverseTransformDirection(vel) / ClipScale;
            var p = new Vector2(l.x, l.z);
            float r = p.magnitude, rate = 1f, walk = config.walkSpeed / ClipScale;
            if (r > 1e-3f)
            {
                // la cuerda entre los dos vecinos en esta dirección está a walk / (|cos| + |sin|) del centro
                float chord = walk * r / (Mathf.Abs(p.x) + Mathf.Abs(p.y));
                if (r > walk) p *= walk / r;
                else if (r > chord) { rate = r / chord; p *= chord / r; }
            }
            anim.SetDirectional(p, dt);
            anim.SetStateSpeed(rate);
        }

        /// <summary>De vuelta a su lugar sin pelea (LoseAggro): camina mirando adonde va y, ya en su lugar y quieto, gira a
        /// como estaba y retoma lo que hacía (si no, quedaba parado de espaldas a la roca: la espera que se quería evitar).</summary>
        void TickHome(Vector3 vel, float speed, float dt)
        {
            if (speed > IdleExit) { Face(transform.position + vel, 1f, dt); return; }
            if (Ambient == null || speed > 0.1f || (transform.position - spawnPos).Flat().sqrMagnitude > 0.09f) return;
            transform.rotation = CombatMath.Damp(transform.rotation, spawnRot, config.turnSpeed * 0.6f, dt);
            if (Quaternion.Angle(transform.rotation, spawnRot) > 4f) return;
            Warp(spawnPos, spawnRot);
            Ambient.Resume();
        }

        // ---------------------------------------------------------------- clips de variante
        /// <summary>Un golpe de zona con clip propio vuelve al estado y los tiempos de siempre si el controller no lo tiene
        /// (otra rama sin el FBX nuevo, un personaje que reusa el arquetipo). Una vez, antes de la primera pelea.</summary>
        void ResolveClipVariants()
        {
            if (config.patterns == null || !anim.Valid) return;
            foreach (var p in config.patterns)
            {
                if (p == null || p.steps == null) continue;
                foreach (var s in p.steps)
                    if (s != null && s.fallback != null && !anim.HasState(s.state)) s.fallback.ApplyTo(s);
            }
        }

        // ---------------------------------------------------------------- embestida
        static bool IsHop(AttackDef a) => a.special == "hop_back" || a.special == "hop_side";

        /// <summary>
        /// Enemy.BeginStep, con la línea de tiempo del paso ya armada: un golpe con lungeFrom (y los saltos sin daño) avanza en
        /// cuadros del clip desde ese cuadro; el golpe hasta un poco después del impacto (sin pasar de MaxClipLunge), el salto
        /// hasta que cae (activeEnd). Sin lungeFrom queda la embestida lineal de lungeStartT a lungeEndT.
        /// </summary>
        void SetupLunge(AttackDef a)
        {
            bool hop = IsHop(a);
            // la finta salta a su derecha o a su izquierda al azar (hopSide): HopSideR tiene su espejo HopSideL
            stepState = a.state;
            if (a.special == "hop_side" && hopSide < 0f && a.state.EndsWith("R"))
            {
                string mirror = a.state.Substring(0, a.state.Length - 1) + "L";
                if (anim.HasState(mirror)) stepState = mirror;
            }
            lungeLen = hop ? a.specialParam : a.lunge;
            clipLunge = a.lungeFrom >= 0f && lungeLen > 0f;
            lungeTravel = shoved = 0f;
            lungeDecided = plantDecided = planted = false;
            if (!clipLunge) return;
            lungeFrames = Mathf.Max(1, Mathf.RoundToInt(clipLen * ClipFps));
            // en el aire no frena (cae cuando ya terminó de avanzar); en el piso y al caer de un salto sin daño, sí
            lungeBrake = a.lungeAir ? 0f : LungeBrake;
            lungeStartT = tl.TimeAt(a.lungeFrom);
            // lungeTo: la embestida termina en ese cuadro (el martillo de Gorō pega el piso con el cuerpo ya llegado; si
            // seguía avanzando después del golpe, la cabeza clavada se arrastraba por el piso con él)
            lungeEndT = hop ? tl.TimeAt(a.activeEnd)
                : Mathf.Max(a.lungeTo > 0f ? tl.TimeAt(a.lungeTo) : tl.T + 0.05f * tl.stepLen,
                    lungeStartT + lungeLen * LungePeak(lungeBrake) / MaxClipLunge);
            lungeFull = lungeLen;
            lungeKeep = Mathf.Min(lungeFrames, Mathf.RoundToInt(a.lungeFrom * lungeFrames) + 1);
            lungeKeepAt = ProfileLunge(tl.TimeAt(lungeKeep / (float)lungeFrames));
        }

        /// <summary>Velocidad máxima de la embestida respecto de la media (el trapecio de aceleración y frenada).</summary>
        static float LungePeak(float brake) => 1f / (1f - 0.5f * LungeAccel - 0.5f * brake);

        /// <summary>Recorrido (m) a 't' s del paso con el largo autorado (lungeFull): acelera parejo hasta LungeAccel, sigue a
        /// velocidad fija y frena parejo el último 'lungeBrake' del tiempo.</summary>
        float ProfileLunge(float t)
        {
            float u = Mathf.Clamp01((t - lungeStartT) / Mathf.Max(0.01f, lungeEndT - lungeStartT));
            float g = u < LungeAccel ? u * u / (2f * LungeAccel)
                : u <= 1f - lungeBrake ? u - 0.5f * LungeAccel
                : 1f - 0.5f * LungeAccel - 0.5f * lungeBrake - (1f - u) * (1f - u) / (2f * Mathf.Max(1e-4f, lungeBrake));
            return lungeFull * g * LungePeak(lungeBrake);
        }

        /// <summary>Recorrido en el cuadro entero 'k' del clip. Un salto decidido más corto (lungeLen menor que lungeFull) hace
        /// lo autorado hasta el primer cuadro en el aire (lungeKeep) y achica solo lo que sigue: escalado parejo desde el
        /// despegue, la punta que todavía empujaba en el piso medio cuadro se corría lo que faltaba (2.5 cm en el Attack2 y 3.6
        /// en la estocada con el salto al 35%, medido con fbx_skate.py).</summary>
        float Knot(int k)
        {
            float full = ProfileLunge(tl.TimeAt(Mathf.Clamp(k, 0, lungeFrames) / (float)lungeFrames));
            if (lungeLen >= lungeFull) return full;
            // tan corto que ni llega a lo del despegue: parejo (el imán de todos modos ya lo frena contra Kaito)
            if (lungeKeepAt >= lungeLen) return full * lungeLen / lungeFull;
            if (k <= lungeKeep) return full;
            return lungeKeepAt + (full - lungeKeepAt) * (lungeLen - lungeKeepAt) / Mathf.Max(1e-4f, lungeFull - lungeKeepAt);
        }

        /// <summary>Recorrido del transform a 'clock' s del paso: ProfileLunge tomado en cada cuadro entero del clip (como lo
        /// hornea clip_lunge_travel) e interpolado entre cuadros con una curva como la que Unity le pone al clip (cúbica con
        /// tangentes automáticas que no se pasan: Tangent): un pie clavado en el mundo no se corre ni entre cuadros.</summary>
        float LungeAt(float clock)
        {
            float f = Mathf.Clamp01(tl.NormAt(clock)) * lungeFrames;
            int k = Mathf.Min((int)f, lungeFrames - 1);
            float p0 = Knot(k - 1), a = Knot(k), b = Knot(k + 1), p3 = Knot(k + 2);
            float ma = Tangent(p0, a, b), mb = Tangent(a, b, p3);
            float s = f - k, s2 = s * s, s3 = s2 * s;
            return (2f * s3 - 3f * s2 + 1f) * a + (s3 - 2f * s2 + s) * ma + (-2f * s3 + 3f * s2) * b + (s3 - s2) * mb;
        }

        /// <summary>Tangente en 'b' entre sus vecinos: la media de los dos tramos, cero en un extremo o un tramo quieto y
        /// nunca más de 3 veces el tramo más corto (así la cúbica no se pasa: Fritsch-Carlson). team_moves.knot_curve.</summary>
        static float Tangent(float a, float b, float c)
        {
            float d0 = b - a, d1 = c - b;
            if (d0 * d1 <= 0f) return 0f;
            float m = 0.5f * (d0 + d1), lim = 3f * Mathf.Min(Mathf.Abs(d0), Mathf.Abs(d1));
            return Mathf.Clamp(m, -lim, lim);
        }

        /// <summary>Avance del golpe (o del salto sin daño) este frame; devuelve lo que le queda de embestida (StrikeReach).
        /// Llamado desde Enemy.TickAttack.</summary>
        float TickLunge(AttackDef a, float dt)
        {
            if (!clipLunge) return a.lunge > 0f ? TickLinearLunge(a, dt) : 0f;
            if (anim.Frozen || target == null) return lungeLen - lungeTravel;
            bool hop = IsHop(a);
            // (nunca después de que arrancó la embestida: desde ahí los dos clips ya son distintos)
            if (!plantDecided && !hop && !a.lungeAir && stepClock >= Mathf.Min(lungeStartT, Mathf.Max(0.1f, tl.ReleaseTime - PlantLead)))
                DecidePlant(a);
            if (planted) return 0f;
            if (!lungeDecided && stepClock >= lungeStartT)
            {
                lungeDecided = true;
                lungeGap = Mathf.Clamp(DistToTarget - Radius - target.Radius, 0f, MagnetGap);
                // en el aire: cae más corto si Kaito está cerca (cortado a mitad, el salto chocaba contra una pared invisible
                // y caía derecho); el clip es el mismo, lo que se achica es el recorrido después del despegue (Knot)
                if (a.lungeAir && !hop)
                    lungeLen = Mathf.Clamp(DistToTarget - Radius - target.Radius - 0.3f, a.lunge * AirMinShare, a.lunge);
            }
            float want = LungeAt(stepClock) - lungeTravel;
            if (want <= 0f) return lungeLen - lungeTravel;
            lungeTravel += want;
            if (hop)
            {
                // el repliegue y la finta se alejan de Kaito o lo rodean: el imán no tiene nada que cortar
                MoveBy((a.special == "hop_back" ? -transform.forward : transform.right * hopSide).Flat().normalized * want);
                return 0f;
            }
            float room = DistToTarget - Radius - target.Radius - lungeGap;
            // Kaito en el dash se cruza con el cuerpo, como con el Travel de Chikuō: el paso sigue entero. Frenarlo contra el
            // que se metía derecho al cuerpo después de DecidePlant dejaba al modelo seguir solo hasta 'near' y el pie de
            // atrás, clavado en la punta, patinaba lo cortado (33-65 cm contra Gorō; build_team_anims 'dash_into_body_cm')
            bool crossing = target.State == PlayerState.Dash;
            if (!crossing && room < want && config.lungeShove > shoved && !a.lungeAir)
            {
                float push = Mathf.Min(want - Mathf.Max(0f, room), config.lungeShove - shoved);
                float moved = target.Shove((target.transform.position - transform.position).Flat().normalized * push);
                shoved += moved;
                room += moved;
            }
            float go = crossing ? want : Mathf.Clamp(room, 0f, want), cut = want - go;
            if (go > 0f) MoveBy(transform.forward * go);
            if (cut > 0f && config.lungeShove > 0f && !a.lungeAir && !target.Shovable)
            {
                // Kaito que no se deja empujar (rematando, en una escena; el del dash ya se cruzó arriba). Lo cortado lo sigue
                // el modelo mientras no quede más cerca de Kaito que donde lo deja el imán con lungeSlack: de costado se abre
                // lugar enseguida y el paso sale entero; contra el cuerpo del enemigo es como una pared
                float near = Radius + target.Radius + MagnetGap - config.lungeSlack * Mathf.Max(0.5f, config.scale);
                lungeWarp += Mathf.Clamp(DistToTarget - lungeWarp - near, 0f, cut);
            }
            else WarpLunge(cut, lungeLen - lungeTravel);   // lo que cortó el imán: el modelo sigue el final
            return lungeLen - lungeTravel;
        }

        /// <summary>
        /// Un poco antes de la suelta de un golpe con paso: ¿entra el paso? Con Kaito pegado el imán corta la embestida y
        /// el cuerpo lo arrastra (lungeShove); si Kaito no se deja (pegado a la barrera de la arena, a una pared o a otro
        /// enemigo, en el dash) el pie de atrás, clavado en la punta mientras el cuerpo le pasa por encima, se corría lo
        /// cortado (25-50 cm en los martillazos de Gorō), y que el modelo siguiera de largo le metía la panza y la armadura
        /// en Kaito (hasta 18 cm; en una cadena, encima). Si lo libre, más lo que se lo puede correr, más lo que el modelo
        /// todavía puede seguir (lungeSlack menos lo que ya va adelantado) no llega a la embestida, el golpe sale en su
        /// variante en el lugar: el mismo clip hasta la suelta y el mismo golpe sin avanzar, pisando fuerte. El cruce dura
        /// lo que falta para la suelta, con los dos clips todavía iguales: no se ve.
        /// </summary>
        void DecidePlant(AttackDef a)
        {
            plantDecided = true;
            // (con Kaito más cerca que el margen, el transform lo acompaña empujándolo: lungeGap)
            float room = Mathf.Max(0f, DistToTarget - Radius - target.Radius - MagnetGap);
            float follow = Mathf.Max(0f, config.lungeSlack * Mathf.Max(0.5f, config.scale) - lungeWarp);
            if (room + follow >= lungeLen - PlantSlack) return;
            string st = stepState + PlantedSuffix;
            if (!anim.HasState(st)) return;
            Vector3 dir = (target.transform.position - transform.position).Flat().normalized;
            float push = config.lungeShove > 0f ? target.ShoveRoom(dir, config.lungeShove, transform) : 0f;
            if (room + push + follow >= lungeLen - PlantSlack) return;
            planted = true;
            stepState = st;
            anim.Play(st, Mathf.Clamp(tl.ReleaseTime - stepClock, 0.03f, PlantLead), tl.NormAt(stepClock));
            // (pasa pocas veces por pelea: el Editor.log dice cuándo y por qué, para probarlo contra la barrera)
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            Debug.Log($"[Nindo] {config.displayName}: {a.state} en el lugar (libre {room.ToString("0.00", inv)} m, " +
                      $"se lo puede correr {push.ToString("0.00", inv)} m, embestida {lungeLen.ToString("0.00", inv)} m)");
        }

        /// <summary>La embestida de siempre (golpes sin lungeFrom: los jefes): lineal en el tiempo de lungeStartT a lungeEndT.</summary>
        float TickLinearLunge(AttackDef a, float dt)
        {
            if (stepClock >= lungeEndT) return 0f;
            float span = Mathf.Max(0.01f, lungeEndT - lungeStartT);
            float left = a.lunge * Mathf.Clamp01((lungeEndT - Mathf.Max(stepClock, lungeStartT)) / span);
            if (stepClock >= lungeStartT && !anim.Frozen && target != null)
            {
                float room = DistToTarget - Radius - target.Radius - 0.3f;
                float want = a.lunge / span * dt, go = Mathf.Clamp(room, 0f, want);
                if (go > 0f) MoveBy(transform.forward * go);
                WarpLunge(want - go, left);
            }
            return left;
        }

        // ---------------------------------------------------------------- imán del golpe
        /// <summary>
        /// El imán cortó 'meters' de la embestida este frame y quedan 'left' por recorrer: el modelo hace solo los últimos
        /// lungeSlack metros. Ahí es donde el clip apoya el pie (el ninja cae del salto corto; el sumo arrima el de atrás)
        /// y donde se veía patinar: medido en build_team_anims (magnet_curve_cm).
        /// </summary>
        void WarpLunge(float meters, float left)
        {
            float cap = config.lungeSlack * Mathf.Max(0.5f, config.scale);
            if (meters <= 0f || cap <= 0f) return;
            float within = Mathf.Clamp(cap - left, 0f, meters);
            // (sin achicar lo que ya sigue de más: el dash de Kaito, TickLunge)
            lungeWarp = Mathf.Max(lungeWarp, Mathf.Min(cap, lungeWarp + within));
        }

        /// <summary>Devuelve el adelanto del modelo al transform apenas hay lugar (nada se mueve en pantalla); caminando lo
        /// suelta de a poco (los pies ya se mueven y no se nota). Llamado desde Enemy.Update.</summary>
        void TickLungeWarp(float dt)
        {
            if (lungeWarp <= 0f)
            {
                if (ModelNudge != Vector3.zero) ApplyNudge(0f);
                return;
            }
            if (!IsAlive) { lungeWarp = 0f; ApplyNudge(0f); return; }
            if (target != null && !anim.Frozen)
            {
                float room = DistToTarget - Radius - target.Radius - 0.3f;
                if (room > 0.01f)
                {
                    float m = Mathf.Min(lungeWarp, room);
                    MoveBy(transform.forward * m);
                    lungeWarp -= m;
                }
            }
            if (State == EnemyState.Chase || State == EnemyState.Strafe) lungeWarp = Mathf.MoveTowards(lungeWarp, 0f, 1.2f * dt);
            ApplyNudge(lungeWarp);
        }

        void ApplyNudge(float forward)
        {
            if (model == null || model == transform) return;
            Vector3 w = transform.forward * forward;
            ModelNudge = model.parent != null ? model.parent.InverseTransformVector(w) : w;
            model.localPosition = modelBasePos + ModelNudge;
        }

        /// <summary>Vuelve a la pose base (ResetEnemy, la muerte): sin adelanto del modelo.</summary>
        void ResetLocomotionAnim()
        {
            lungeWarp = 0f;
            ModelNudge = Vector3.zero;
            stillFor = 0f;
        }
    }

    /// <summary>El estado y los tiempos del clip de siempre para un golpe de zona con clip propio (EnemyArchetypes): si
    /// el controller no tiene el estado nuevo, el golpe vuelve a ese clip con sus números (los del clip, no los del golpe:
    /// el daño, el alcance y la embestida quedan).</summary>
    public class AttackClipFallback
    {
        public string state;
        // lungeTo es de cada clip como lungeFrom: una variante con 'to:' que cae al clip de siempre se quedaba con el cuadro
        // del suyo y terminaba la embestida en cualquier lado
        public float activeStart, activeEnd, apex, lungeFrom = -1f, lungeTo = -1f;
        public bool lungeAir;

        public void ApplyTo(AttackDef a)
        {
            a.state = state;
            a.activeStart = activeStart;
            a.activeEnd = activeEnd;
            a.apex = apex;
            a.lungeFrom = lungeFrom;
            a.lungeTo = lungeTo;
            a.lungeAir = lungeAir;
            a.fallback = null;
        }
    }
}
