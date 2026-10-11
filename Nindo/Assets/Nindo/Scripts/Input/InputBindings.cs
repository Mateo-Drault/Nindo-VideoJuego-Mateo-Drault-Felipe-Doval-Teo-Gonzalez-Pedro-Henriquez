using System;
using UnityEngine;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.Controls;
using UnityEngine.InputSystem.LowLevel;
#endif

namespace Nindo
{
    /// <summary>
    /// Los controles del jugador en el juego: la tabla de <see cref="BindingTable"/> con lo elegido en
    /// Opciones › Controles (guardada en las preferencias, Settings.ControlBindings) y lo que necesita quien la usa:
    /// leer cada control (InputReader), el nombre de cada tecla en pantalla (en castellano; las letras y signos como
    /// los dice la distribución del teclado: la Ñ del teclado español) y tomar la próxima tecla al reasignar.
    /// Es estática: la tabla es la misma en el menú y en el juego, y un cambio llega a todos con <see cref="Version"/>.
    /// </summary>
    public static class InputBindings
    {
        static BindingTable table;
        static string[] names;          // [((fila * 2 + dispositivo) * 2 + casilla) * 3 + familia]
        static string moveGlyph;
        static int rowUp = -1, rowDown, rowLeft, rowRight;
#if ENABLE_INPUT_SYSTEM
        static Keyboard namesKeyboard;  // los nombres se armaron con la distribución de este teclado
#endif

        /// <summary>Cambia con cada reasignación (y si cambia la distribución del teclado): InputReader sube su GlyphVersion.</summary>
        public static int Version { get; private set; }

        public static BindingTable Table
        {
            get { if (table == null) Init(); return table; }
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics()
        {
            // el aviso de cambio de distribución no se toca acá (el Input System puede no estar listo todavía): Init lo
            // saca y lo vuelve a poner, así nunca queda dos veces
            table = null; names = null; moveGlyph = null; rowUp = -1; Version = 0;
#if ENABLE_INPUT_SYSTEM
            namesKeyboard = null;
#endif
        }

        static void Init()
        {
            // Enum.GetNames va por valor: la fila r es (Act)r (InputReader y los textos "{Attack}" cuentan con eso)
            table = new BindingTable(BindingCatalog.Build(Enum.GetNames(typeof(Act))), BindingCatalog.Reserved);
            var problems = table.Load(Settings.ControlBindings, BindingCatalog.ParseCode);
            if (problems.Count > 0) Debug.Log("[Nindo] Controles guardados: " + string.Join("; ", problems));
            rowUp = table.IndexOf("MoveUp"); rowDown = table.IndexOf("MoveDown");
            rowLeft = table.IndexOf("MoveLeft"); rowRight = table.IndexOf("MoveRight");
            names = null;
#if ENABLE_INPUT_SYSTEM
            InputSystem.onDeviceChange -= OnDeviceChange;
            InputSystem.onDeviceChange += OnDeviceChange;
#endif
        }

        /// <summary>Después de cambiar la tabla: se guarda en las preferencias y los textos con teclas se rehacen.</summary>
        public static void Commit()
        {
            Settings.ControlBindings = Table.Save(BindingCatalog.CodeId);
            names = null;
            Version++;
        }

#if ENABLE_INPUT_SYSTEM
        // cambiar la distribución del teclado (español, inglés...) cambia lo que dicen las letras y los signos
        static void OnDeviceChange(InputDevice d, InputDeviceChange c)
        {
            if (d is Keyboard && c == InputDeviceChange.ConfigurationChanged) { names = null; Version++; }
        }
#endif

        // ================================================================== nombres en pantalla
        /// <summary>Nombre de lo que tiene la casilla, o null si está vacía. 'family': 1 Xbox, 2 PlayStation (el teclado no la usa).</summary>
        public static string Name(int row, int dev, int slot, int family)
        {
            EnsureNames();
            int f = dev == BindingTable.Keys ? 0 : family == 2 ? 2 : 1;
            return names[((row * 2 + dev) * 2 + slot) * 3 + f];
        }

        /// <summary>La tecla de la acción en el dispositivo de esa familia (0 teclado): la principal o, si no hay, la otra.</summary>
        public static string Glyph(int row, int family)
        {
            int dev = family == 0 ? BindingTable.Keys : BindingTable.Pad;
            return Name(row, dev, 0, family) ?? Name(row, dev, 1, family) ?? "?";
        }

        /// <summary>La segunda tecla de la acción (null si tiene una sola).</summary>
        public static string GlyphAlt(int row, int family)
        {
            int dev = family == 0 ? BindingTable.Keys : BindingTable.Pad;
            return Name(row, dev, 0, family) != null ? Name(row, dev, 1, family) : null;
        }

        /// <summary>"WASD" (o "ZQSD", "↑←↓→"... lo que haya elegido) en el teclado; el stick en el mando.</summary>
        public static string MoveGlyph(int family)
        {
            if (family != 0) return "Stick izq.";
            EnsureNames();
            return moveGlyph;
        }

        static void EnsureNames()
        {
            var t = Table;
#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            if (names != null && kb == namesKeyboard) return;
            namesKeyboard = kb;
#else
            if (names != null) return;
#endif
            names = new string[t.RowCount * 12];
            for (int r = 0; r < t.RowCount; r++)
                for (int d = 0; d < BindingTable.Devices; d++)
                    for (int s = 0; s < BindingTable.Slots; s++)
                    {
                        int c = t.Get(r, d, s), i = ((r * 2 + d) * 2 + s) * 3;
                        if (c == BindCode.None) continue;
                        if (d == BindingTable.Keys) names[i] = Display(c, 0);
                        else { names[i + 1] = Display(c, 1); names[i + 2] = Display(c, 2); }
                    }
            // en el orden de la cruz de siempre: arriba, izquierda, abajo, derecha (W A S D)
            string u = Glyph(rowUp, 0), l = Glyph(rowLeft, 0), dn = Glyph(rowDown, 0), rt = Glyph(rowRight, 0);
            moveGlyph = u.Length == 1 && l.Length == 1 && dn.Length == 1 && rt.Length == 1 ? u + l + dn + rt : u + " " + l + " " + dn + " " + rt;
        }

        /// <summary>Nombre de un control en pantalla. 'family' elige los del mando: 2 PlayStation, si no Xbox.</summary>
        public static string Display(int code, int family)
        {
            switch (code)
            {
                case BindCode.None: return null;
                case BindCode.MouseLeft: return "Clic izq.";
                case BindCode.MouseRight: return "Clic der.";
                case BindCode.MouseMiddle: return "Clic medio";
                case BindCode.MouseBack: return "Mouse 4";
                case BindCode.MouseForward: return "Mouse 5";
                case BindCode.WheelUp: return "Rueda ↑";
                case BindCode.WheelDown: return "Rueda ↓";
                case BindCode.RStickUp: return "Stick der. ↑";
                case BindCode.RStickDown: return "Stick der. ↓";
                case BindCode.RStickLeft: return "Stick der. ←";
                case BindCode.RStickRight: return "Stick der. →";
                case BindCode.PadMoveStick: return "Stick izq.";
                case BindCode.PadMoveDpad: return "Cruceta";
            }
#if ENABLE_INPUT_SYSTEM
            if (BindCode.IsKey(code)) return KeyName((Key)code, Keyboard.current);
            if (BindCode.IsPad(code)) return PadName((GamepadButton)(code - BindCode.PadBase), family == 2);
#endif
            return "?";
        }

#if ENABLE_INPUT_SYSTEM
        static string KeyName(Key k, Keyboard kb)
        {
            switch (k)
            {
                case Key.Space: return "Espacio";
                case Key.Enter: return "Enter";
                case Key.Tab: return "Tab";
                case Key.Escape: return "Esc";
                case Key.Backspace: return "Retroceso";
                case Key.LeftShift: return "Shift";
                case Key.RightShift: return "Shift der.";
                case Key.LeftCtrl: return "Ctrl";
                case Key.RightCtrl: return "Ctrl der.";
                case Key.LeftAlt: return "Alt";
                case Key.RightAlt: return "Alt Gr";
                case Key.LeftMeta: case Key.RightMeta: return "Win";
                case Key.ContextMenu: return "Menú";
                case Key.UpArrow: return "↑";
                case Key.DownArrow: return "↓";
                case Key.LeftArrow: return "←";
                case Key.RightArrow: return "→";
                case Key.PageUp: return "RePág";
                case Key.PageDown: return "AvPág";
                case Key.Home: return "Inicio";
                case Key.End: return "Fin";
                case Key.Insert: return "Insert";
                case Key.Delete: return "Supr";
                case Key.CapsLock: return "Bloq Mayús";
                case Key.NumLock: return "Bloq Num";
                case Key.ScrollLock: return "Bloq Despl";
                case Key.PrintScreen: return "Impr Pant";
                case Key.Pause: return "Pausa";
                case Key.NumpadEnter: return "Num Enter";
                case Key.NumpadDivide: return "Num /";
                case Key.NumpadMultiply: return "Num *";
                case Key.NumpadPlus: return "Num +";
                case Key.NumpadMinus: return "Num -";
                case Key.NumpadPeriod: return "Num .";
                case Key.NumpadEquals: return "Num =";
            }
            // los números como están impresos (en un AZERTY la tecla del 1 escribe "&")
            if (k >= Key.Digit1 && k <= Key.Digit0) return k == Key.Digit0 ? "0" : ((int)(k - Key.Digit1) + 1).ToString();
            if (k >= Key.Numpad0 && k <= Key.Numpad9) return "Num " + (int)(k - Key.Numpad0);
            if (k >= Key.F1 && k <= Key.F12) return "F" + ((int)(k - Key.F1) + 1);
            if (k >= Key.F13 && k <= Key.F24) return "F" + ((int)(k - Key.F13) + 13);
            // letras y signos: lo que dice la tecla en la distribución del teclado (Key va por posición física: la
            // tecla de la W en un AZERTY es la Z)
            if (kb != null && (int)k - 1 < kb.allKeys.Count)
            {
                string dn = kb[k].displayName;
                if (!string.IsNullOrEmpty(dn) && dn.Length <= 2) return dn.ToUpperInvariant();
            }
            switch (k)
            {
                case Key.Backquote: return "`";
                case Key.Quote: return "'";
                case Key.Semicolon: return ";";
                case Key.Comma: return ",";
                case Key.Period: return ".";
                case Key.Slash: return "/";
                case Key.Backslash: return "\\";
                case Key.LeftBracket: return "[";
                case Key.RightBracket: return "]";
                case Key.Minus: return "-";
                case Key.Equals: return "=";
            }
            return k.ToString();
        }

        static string PadName(GamepadButton b, bool ps)
        {
            switch (b)
            {
                case GamepadButton.North: return ps ? "△" : "Y";
                case GamepadButton.East: return ps ? "○" : "B";
                case GamepadButton.South: return ps ? "×" : "A";
                case GamepadButton.West: return ps ? "□" : "X";
                case GamepadButton.LeftShoulder: return ps ? "L1" : "LB";
                case GamepadButton.RightShoulder: return ps ? "R1" : "RB";
                case GamepadButton.LeftTrigger: return ps ? "L2" : "LT";
                case GamepadButton.RightTrigger: return ps ? "R2" : "RT";
                case GamepadButton.LeftStick: return ps ? "L3" : "LS";
                case GamepadButton.RightStick: return ps ? "R3" : "RS";
                case GamepadButton.Start: return ps ? "Options" : "Menu";
                case GamepadButton.Select: return ps ? "Share" : "View";
                case GamepadButton.DpadUp: return "Cruceta ↑";
                case GamepadButton.DpadDown: return "Cruceta ↓";
                case GamepadButton.DpadLeft: return "Cruceta ←";
                case GamepadButton.DpadRight: return "Cruceta →";
            }
            return b.ToString();
        }
#endif

        // ================================================================== leer los controles
        /// <summary>1 Xbox o genérico, 2 PlayStation (por el layout: DualShock4GamepadHID, DualSenseGamepadHID...).</summary>
        public static int PadFamily()
        {
#if ENABLE_INPUT_SYSTEM
            string layout = Gamepad.current != null ? Gamepad.current.layout : "";
            return layout.Contains("DualShock") || layout.Contains("DualSense") ? 2 : 1;
#else
            return 1;
#endif
        }

        public static bool PadConnected
        {
#if ENABLE_INPUT_SYSTEM
            get => Gamepad.current != null;
#else
            get => false;
#endif
        }

#if ENABLE_INPUT_SYSTEM
        /// <summary>Todos los botones del mando, para tomar uno al reasignar (la cruceta también: se rechaza con su aviso).</summary>
        static readonly GamepadButton[] PadButtons =
        {
            GamepadButton.South, GamepadButton.East, GamepadButton.West, GamepadButton.North,
            GamepadButton.LeftShoulder, GamepadButton.RightShoulder, GamepadButton.LeftTrigger, GamepadButton.RightTrigger,
            GamepadButton.LeftStick, GamepadButton.RightStick, GamepadButton.Start, GamepadButton.Select,
            GamepadButton.DpadUp, GamepadButton.DpadDown, GamepadButton.DpadLeft, GamepadButton.DpadRight,
        };

        /// <summary>¿Se apretó este cuadro la tecla o botón del mouse? 'held' se prende si está apretada; 'wheel' es el giro de la rueda.</summary>
        public static bool PollKeys(int code, Keyboard kb, Mouse mouse, float wheel, ref bool held)
        {
            if (BindCode.IsKey(code))
            {
                if (kb == null || code - 1 >= kb.allKeys.Count) return false;
                var k = kb[(Key)code];
                held |= k.isPressed;
                return k.wasPressedThisFrame;
            }
            if (mouse == null) return false;
            ButtonControl b;
            switch (code)
            {
                case BindCode.MouseLeft: b = mouse.leftButton; break;
                case BindCode.MouseRight: b = mouse.rightButton; break;
                case BindCode.MouseMiddle: b = mouse.middleButton; break;
                case BindCode.MouseForward: b = mouse.forwardButton; break;
                case BindCode.MouseBack: b = mouse.backButton; break;
                case BindCode.WheelUp: return wheel > 0.1f;
                case BindCode.WheelDown: return wheel < -0.1f;
                default: return false;
            }
            held |= b.isPressed;
            return b.wasPressedThisFrame;
        }

        /// <summary>Lo mismo para el mando; 'flick' es el toque del stick derecho de este cuadro (BindCode.RStick*, 0 si no hubo).</summary>
        public static bool PollPad(int code, Gamepad pad, int flick, ref bool held)
        {
            if (pad == null) return false;
            if (code >= BindCode.RStickUp && code <= BindCode.RStickRight) return code == flick;
            if (code < BindCode.PadBase || code >= BindCode.RStickUp) return false;
            var b = pad[(GamepadButton)(code - BindCode.PadBase)];
            held |= b.isPressed;
            return b.wasPressedThisFrame;
        }
#endif

        /// <summary>
        /// Lo primero que se apretó este cuadro en ese dispositivo, para reasignar (0 si nada). Toma cualquier tecla
        /// (las reservadas también: la tabla las rechaza con su motivo), los botones y la rueda del mouse, y en el mando
        /// todos los botones y los toques del stick derecho. El stick izquierdo nunca: mueve a Kaito.
        /// </summary>
        public static int Capture(int dev)
        {
#if ENABLE_INPUT_SYSTEM
            if (dev == BindingTable.Keys)
            {
                var kb = Keyboard.current;
                if (kb != null)
                {
                    var keys = kb.allKeys;
                    for (int i = 0; i < keys.Count; i++)
                        if (keys[i].wasPressedThisFrame && BindingCatalog.IsBindableKey(keys[i].keyCode)) return (int)keys[i].keyCode;
                }
                var m = Mouse.current;
                if (m == null) return BindCode.None;
                if (m.leftButton.wasPressedThisFrame) return BindCode.MouseLeft;
                if (m.rightButton.wasPressedThisFrame) return BindCode.MouseRight;
                if (m.middleButton.wasPressedThisFrame) return BindCode.MouseMiddle;
                if (m.forwardButton.wasPressedThisFrame) return BindCode.MouseForward;
                if (m.backButton.wasPressedThisFrame) return BindCode.MouseBack;
                float w = m.scroll.ReadValue().y;
                return w > 0.1f ? BindCode.WheelUp : w < -0.1f ? BindCode.WheelDown : BindCode.None;
            }
            var pad = Gamepad.current;
            if (pad == null) return BindCode.None;
            foreach (var b in PadButtons) if (pad[b].wasPressedThisFrame) return BindCode.Pad((int)b);
            // el toque del stick derecho: antes de tomar se esperó a que todo estuviera suelto (AnyHeld), así que
            // pasar de 0.7 es un toque nuevo
            Vector2 rs = pad.rightStick.ReadValue();
            if (Mathf.Abs(rs.x) >= Mathf.Abs(rs.y)) return rs.x > 0.7f ? BindCode.RStickRight : rs.x < -0.7f ? BindCode.RStickLeft : BindCode.None;
            return rs.y > 0.7f ? BindCode.RStickUp : rs.y < -0.7f ? BindCode.RStickDown : BindCode.None;
#else
            return BindCode.None;
#endif
        }

        /// <summary>¿Hay algo apretado? Al reasignar se espera a que se suelte todo: el Enter o la A que abrió la
        /// espera (o el clic) no puede quedar tomado como la tecla nueva, ni la tecla tomada confirmar en el menú.</summary>
        public static bool AnyHeld()
        {
#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            if (kb != null && kb.anyKey.isPressed) return true;
            var m = Mouse.current;
            if (m != null && (m.leftButton.isPressed || m.rightButton.isPressed || m.middleButton.isPressed || m.forwardButton.isPressed || m.backButton.isPressed)) return true;
            var pad = Gamepad.current;
            if (pad != null)
            {
                foreach (var b in PadButtons) if (pad[b].isPressed) return true;
                if (pad.rightStick.ReadValue().sqrMagnitude > 0.09f) return true;
            }
#endif
            return false;
        }

        /// <summary>¿El puntero del mouse está sobre ese rect de la UI? (lo elegido al pasar el mouse no corre la lista)</summary>
        public static bool PointerOver(RectTransform rt)
        {
#if ENABLE_INPUT_SYSTEM
            var m = Mouse.current;
            return m != null && Cursor.visible && RectTransformUtility.RectangleContainsScreenPoint(rt, m.position.ReadValue(), null);
#else
            return false;
#endif
        }

        /// <summary>Cancelar la espera de una tecla nueva: Esc o Start siempre; si se espera una del teclado, también la
        /// B del mando (no hay nada del mando para tomar ahí). En el mando la B no cancela: es una tecla que se puede asignar.</summary>
        public static bool CaptureCancelPressed(int dev)
        {
#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            if (kb != null && kb.escapeKey.wasPressedThisFrame) return true;
            var pad = Gamepad.current;
            return pad != null && (pad.startButton.wasPressedThisFrame || (dev == BindingTable.Keys && pad.buttonEast.wasPressedThisFrame));
#else
            return false;
#endif
        }

        /// <summary>Quitar la tecla elegida en la página de controles: Supr o Retroceso, o X / □ del mando (la navegación no lo usa).</summary>
        public static bool ClearPressed()
        {
#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            if (kb != null && (kb.deleteKey.wasPressedThisFrame || kb.backspaceKey.wasPressedThisFrame)) return true;
            var pad = Gamepad.current;
            return pad != null && pad.buttonWest.wasPressedThisFrame;
#else
            return false;
#endif
        }
    }
}
