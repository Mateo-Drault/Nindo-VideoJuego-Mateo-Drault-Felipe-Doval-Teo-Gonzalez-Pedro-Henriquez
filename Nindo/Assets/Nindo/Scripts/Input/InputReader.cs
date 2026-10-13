using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace Nindo
{
    public enum Act
    {
        Attack, Parry, Dash, Lock, Finisher, Interact, Ability1, Ability2, Pause, LockNext, LockPrev, Submit, Cancel,
        Map   // mapa del mundo (UI/UIMap.cs)
    }

    /// <summary>
    /// Lectura de input unificada: teclado+mouse y gamepad (Input System), con fallback al
    /// Input Manager clásico. Incluye buffer de acciones para que los combos/parrys se sientan
    /// precisos (si apretás un poco antes de que termine el golpe, igual entra).
    /// Las teclas de cada acción son las que eligió el jugador en Opciones › Controles (InputBindings).
    /// </summary>
    [DefaultExecutionOrder(-800)]
    public class InputReader : MonoBehaviour
    {
        // sale del enum: una acción nueva (Map) no deja los arreglos cortos
        static readonly int ActCount = System.Enum.GetValues(typeof(Act)).Length;
        readonly float[] pressedAt = new float[ActCount];
        readonly bool[] pressedNow = new bool[ActCount];
        readonly bool[] consumed = new bool[ActCount];
        readonly bool[] actHeld = new bool[ActCount];

        public Vector2 Move { get; private set; }
        public bool ParryHeld { get; private set; }
        public bool AttackHeld { get; private set; }
        public bool LockHeld { get; private set; }
        public bool UsingGamepad { get; private set; }
        /// <summary>Bloquea el input de gameplay (UI abierta, cinemáticas).</summary>
        public bool GameplayBlocked { get; set; }

        float rumbleUntil;

        void Awake()
        {
            Game.Input = this;
            for (int i = 0; i < ActCount; i++) pressedAt[i] = -999f;
        }

        void OnDestroy()
        {
            if (Game.Input == this) Game.Input = null;
            StopRumble();
        }

        void OnDisable() => StopRumble();

        void Update()
        {
            for (int i = 0; i < ActCount; i++) pressedNow[i] = false;
            Vector2 move = Vector2.zero;
            bool parryHeld = false, attackHeld = false, lockHeld = false;

#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            var mouse = Mouse.current;
            var pad = Gamepad.current;
            if (kb != null && kb.anyKey.wasPressedThisFrame) UsingGamepad = false;
            if (mouse != null && (mouse.leftButton.wasPressedThisFrame || mouse.rightButton.wasPressedThisFrame)) UsingGamepad = false;
            // cada acción (y cada dirección del teclado) con sus dos teclas y sus dos botones del mando (el panel táctil
            // de los de PlayStation, que abre el mapa, es la segunda casilla fija del mapa)
            var table = InputBindings.Table;
            float wheel = mouse != null ? mouse.scroll.ReadValue().y : 0f;
            int flick = pad != null ? StickFlick(pad.rightStick.ReadValue()) : 0;
            for (int r = 0; r < table.RowCount; r++)
            {
                bool held = false, keyPress = false, padPress = false;
                for (int s = 0; s < BindingTable.Slots; s++)
                {
                    int k = table.Get(r, BindingTable.Keys, s);
                    if (k != BindCode.None && InputBindings.PollKeys(k, kb, mouse, wheel, ref held)) keyPress = true;
                    int p = table.Get(r, BindingTable.Pad, s);
                    if (p != BindCode.None && InputBindings.PollPad(p, pad, flick, ref held)) padPress = true;
                }
                var row = table.Row(r);
                if (row.act >= 0)
                {
                    if (keyPress) Press((Act)row.act, false);
                    if (padPress) Press((Act)row.act, true);
                    actHeld[row.act] = held;
                }
                else if (held)
                {
                    if (row.move == 1) move.y += 1;
                    else if (row.move == 2) move.y -= 1;
                    else if (row.move == 3) move.x -= 1;
                    else if (row.move == 4) move.x += 1;
                }
            }
            parryHeld = actHeld[(int)Act.Parry];
            attackHeld = actHeld[(int)Act.Attack];
            lockHeld = actHeld[(int)Act.Lock];
            if (pad != null)
            {
                // el movimiento del mando es fijo: stick izquierdo y cruceta (la cruceta no se puede asignar)
                Vector2 ls = pad.leftStick.ReadValue();
                if (ls.sqrMagnitude < 0.04f) ls = Vector2.zero;
                ls += pad.dpad.ReadValue();
                if (ls.sqrMagnitude > 0.01f) { move += ls; UsingGamepad = true; }
            }
#elif ENABLE_LEGACY_INPUT_MANAGER
            move.x = Input.GetAxisRaw("Horizontal");
            move.y = Input.GetAxisRaw("Vertical");
            if (Input.GetKeyDown(KeyCode.J) || Input.GetMouseButtonDown(0)) Press(Act.Attack, false);
            if (Input.GetKeyDown(KeyCode.K) || Input.GetMouseButtonDown(1)) Press(Act.Parry, false);
            if (Input.GetKeyDown(KeyCode.Space) || Input.GetKeyDown(KeyCode.LeftShift)) Press(Act.Dash, false);
            if (Input.GetKeyDown(KeyCode.Q) || Input.GetKeyDown(KeyCode.Tab) || Input.GetMouseButtonDown(2)) Press(Act.Lock, false);
            if (Input.GetKeyDown(KeyCode.F)) { Press(Act.Finisher, false); Press(Act.Interact, false); }
            if (Input.GetKeyDown(KeyCode.E)) Press(Act.Interact, false);
            if (Input.GetKeyDown(KeyCode.Alpha1)) Press(Act.Ability1, false);
            if (Input.GetKeyDown(KeyCode.Alpha2)) Press(Act.Ability2, false);
            if (Input.GetKeyDown(KeyCode.Escape)) { Press(Act.Pause, false); Press(Act.Cancel, false); }
            if (Input.GetKeyDown(KeyCode.Return)) Press(Act.Submit, false);
            if (Input.GetKeyDown(KeyCode.M)) Press(Act.Map, false);
            float wheel = Input.mouseScrollDelta.y;
            if (wheel > 0.1f) Press(Act.LockPrev, false);
            if (wheel < -0.1f) Press(Act.LockNext, false);
            parryHeld = Input.GetKey(KeyCode.K) || Input.GetMouseButton(1);
            attackHeld = Input.GetKey(KeyCode.J) || Input.GetMouseButton(0);
            lockHeld = Input.GetKey(KeyCode.Q) || Input.GetKey(KeyCode.Tab) || Input.GetMouseButton(2);
#endif
#if UNITY_EDITOR || DEVELOPMENT_BUILD
            // entrada virtual del AutoPilot (pruebas automáticas): se suma a la real
            for (int i = 0; i < ActCount; i++)
            {
                if (virtualTaps[i] > 0) { virtualTaps[i]--; Press((Act)i, false); }
                else if (virtualHeld[i] && !virtualPrev[i]) Press((Act)i, false);
                virtualPrev[i] = virtualHeld[i];
            }
            move += VirtualMove;
            parryHeld |= virtualHeld[(int)Act.Parry];
            attackHeld |= virtualHeld[(int)Act.Attack];
            lockHeld |= virtualHeld[(int)Act.Lock];
#endif
            Move = Vector2.ClampMagnitude(move, 1f);
            ParryHeld = parryHeld;
            AttackHeld = attackHeld;
            LockHeld = lockHeld;

            if (rumbleUntil > 0f && Time.unscaledTime > rumbleUntil) StopRumble();
        }

#if ENABLE_INPUT_SYSTEM
        bool stickFlicked;

        /// <summary>Toque del stick derecho (cambiar de objetivo): cuenta una vez por eje dominante y se rearma al volver al centro.</summary>
        int StickFlick(Vector2 rs)
        {
            if (rs.sqrMagnitude < 0.09f) { stickFlicked = false; return 0; }
            if (stickFlicked) return 0;
            bool horizontal = Mathf.Abs(rs.x) >= Mathf.Abs(rs.y);
            float v = horizontal ? rs.x : rs.y;
            if (Mathf.Abs(v) < 0.7f) return 0;
            stickFlicked = true;
            return horizontal ? (v > 0f ? BindCode.RStickRight : BindCode.RStickLeft) : (v > 0f ? BindCode.RStickUp : BindCode.RStickDown);
        }
#endif

#if UNITY_EDITOR || DEVELOPMENT_BUILD
        // ---------------------------------------------------------------- entrada virtual (AutoPilot)
        static readonly int[] virtualTaps = new int[ActCount];
        static readonly bool[] virtualHeld = new bool[ActCount];
        static readonly bool[] virtualPrev = new bool[ActCount];
        /// <summary>Movimiento virtual (mismo espacio que el stick: x derecha, y adelante).</summary>
        public static Vector2 VirtualMove;
        /// <summary>Una pulsación que se registra en el próximo Update, sin importar el framerate.</summary>
        public static void VirtualTap(Act a) => virtualTaps[(int)a]++;
        public static void VirtualHold(Act a, bool held) => virtualHeld[(int)a] = held;
        public static void ClearVirtual()
        {
            for (int i = 0; i < ActCount; i++) { virtualTaps[i] = 0; virtualHeld[i] = false; virtualPrev[i] = false; }
            VirtualMove = Vector2.zero;
        }
#endif

        void Press(Act a, bool gamepad)
        {
            int i = (int)a;
            pressedNow[i] = true;
            pressedAt[i] = Time.unscaledTime;
            // si el buffer se limpió en este mismo frame (p. ej. la UI procesó el botón que cerró la
            // pausa antes que este Update) la pulsación no llega al gameplay
            consumed[i] = Time.frameCount == clearedFrame;
            if (gamepad) UsingGamepad = true;
        }

        /// <summary>¿Se apretó este frame? (ignora el bloqueo de gameplay para UI). Si en este frame
        /// ya se llamó a ClearBuffer (p. ej. la A del mando cerró la pausa) la pulsación se descarta
        /// también acá, para que los que leen después (tutoriales de StoryDirector) no la tomen.</summary>
        public bool Pressed(Act a) => pressedNow[(int)a] && Time.frameCount != clearedFrame;

        /// <summary>¿Se apretó dentro de los últimos 'window' segundos y nadie lo consumió?</summary>
        public bool Buffered(Act a, float window = 0.18f)
        {
            if (GameplayBlocked) return false;
            int i = (int)a;
            return !consumed[i] && Time.unscaledTime - pressedAt[i] <= window;
        }

        public void Consume(Act a) => consumed[(int)a] = true;

        /// <summary>Descarta las acciones en buffer (también las que se registren en este mismo frame).</summary>
        public void ClearBuffer()
        {
            for (int i = 0; i < ActCount; i++) consumed[i] = true;
            clearedFrame = Time.frameCount;
        }

        int clearedFrame = -1;

        public Vector2 GameplayMove => GameplayBlocked ? Vector2.zero : Move;

        // ---------------------------------------------------------------- rumble
        public void Rumble(float low, float high, float seconds)
        {
#if ENABLE_INPUT_SYSTEM
            if (!Settings.Rumble || !UsingGamepad) return;
            var pad = Gamepad.current;
            if (pad == null) return;
            pad.SetMotorSpeeds(Mathf.Clamp01(low), Mathf.Clamp01(high));
            rumbleUntil = Time.unscaledTime + seconds;
#endif
        }

        void StopRumble()
        {
            rumbleUntil = 0f;
#if ENABLE_INPUT_SYSTEM
            Gamepad.current?.SetMotorSpeeds(0f, 0f);
#endif
        }

        // ---------------------------------------------------------------- glyphs
        /// <summary>Familia de botones que se muestra: 0 teclado y mouse, 1 mando Xbox / genérico, 2 PlayStation.</summary>
        public int GlyphFamily { get; private set; }
        /// <summary>Cambia cada vez que cambia la familia o el jugador reasigna una tecla (los textos con teclas se
        /// rehacen al verlo distinto: consejos, diálogos, la tarjeta de controles, los carteles sobre el mundo).</summary>
        public int GlyphVersion { get; private set; }
        int bindingsVersion = -1;

        void LateUpdate()
        {
            // por el layout (DualShock4GamepadHID, DualSenseGamepadHID...): sin depender del plugin de Sony
            int fam = UsingGamepad ? InputBindings.PadFamily() : 0;
            if (fam != GlyphFamily || bindingsVersion != InputBindings.Version)
            {
                GlyphFamily = fam;
                bindingsVersion = InputBindings.Version;
                GlyphVersion++;
            }
        }

        /// <summary>
        /// Símbolo de la acción en el dispositivo que se está usando: la tecla que eligió el jugador (la principal o,
        /// si no tiene, la otra; "?" si quedó sin ninguna). La UI lo dibuja como tecla (UIFactory.KeyCap / RichKeys):
        /// □ ○ △ × en los de PlayStation, A B X Y en los demás.
        /// </summary>
        public string Glyph(Act a) => InputBindings.Glyph((int)a, GlyphFamily);

        /// <summary>Segunda tecla de la misma acción, si hay (la tarjeta de controles de la pausa muestra las dos).</summary>
        public string GlyphAlt(Act a) => InputBindings.GlyphAlt((int)a, GlyphFamily);

        /// <summary>Las teclas de moverse ("WASD", o las que eligió) o el stick.</summary>
        public string MoveGlyph => InputBindings.MoveGlyph(GlyphFamily);
    }
}
