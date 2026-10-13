using System;
using System.Collections.Generic;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace Nindo
{
    /// <summary>
    /// Las acciones que se pueden reasignar, con su nombre en pantalla, su grupo, dónde se usan y sus teclas de
    /// fábrica. Va por NOMBRE de acción, no por el enum: una acción nueva de <see cref="Act"/> (el mapa) toma acá sus
    /// teclas en cuanto existe, y una que no figura aparece igual en la página de controles, sin teclas.
    /// Solo usa los enums Key y GamepadButton del Input System (se prueba fuera de Unity).
    /// </summary>
    public static class BindingCatalog
    {
        /// <summary>Contextos: en juego (explorar, pelear), en menús y diálogos y con el mapa abierto (UI/UIMap.cs).</summary>
        public const int Play = 1, Menu = BindingTable.MenuContext, MapView = BindingTable.MapContext;
        public const int GroupMove = 0, GroupCombat = 1, GroupExplore = 2, GroupMenu = 3;
        public static readonly string[] GroupNames = { "Movimiento", "Combate", "Exploración", "Menú" };

        /// <summary>Filas que comparten tecla a propósito: el juego decide cuál va (PlayerController.TryInteract).</summary>
        const int ShareFinish = 1, ShareBack = 2;
        const int L = 1 << 30;   // marca de casilla fija (se le saca al código)

        struct Spec
        {
            public string id, label;
            public int group, ctx, share, k0, k1, p0, p1;
            public bool hold;   // BindRow.hold
            public Spec(string id, string label, int group, int ctx, int share, int k0, int k1, int p0, int p1)
            { this.id = id; this.label = label; this.group = group; this.ctx = ctx; this.share = share; this.k0 = k0; this.k1 = k1; this.p0 = p0; this.p1 = p1; hold = false; }
        }

        static int K(Key k) => (int)k;
        static int P(GamepadButton b) => BindCode.Pad((int)b);

        // Las de fábrica son las de siempre, con dos por dispositivo: quedan las dos que mostraba la tarjeta de la pausa
        // (dash: Espacio y Shift; fijar: Q y Tab). Las terceras, que no se veían en ningún lado (la L del dash y el clic
        // de la rueda para fijar), se asignan a mano.
        static readonly Spec[] Specs =
        {
            new Spec("Attack", "Atacar", GroupCombat, Play, 0, BindCode.MouseLeft, K(Key.J), P(GamepadButton.West), P(GamepadButton.RightShoulder)),
            new Spec("Parry", "Parry", GroupCombat, Play, 0, BindCode.MouseRight, K(Key.K), P(GamepadButton.LeftShoulder), 0),
            new Spec("Dash", "Esquivar (dash)", GroupCombat, Play, 0, K(Key.Space), K(Key.LeftShift), P(GamepadButton.East), P(GamepadButton.South)),
            // fijar se suelta manteniéndolo (PlayerController.UpdateTargeting): la rueda o un toque del stick no sirven. Con
            // el mapa abierto centra en Kaito: no puede ser nada de lo que usa el mapa
            new Spec("Lock", "Fijar objetivo", GroupCombat, Play | MapView, 0, K(Key.Q), K(Key.Tab), P(GamepadButton.RightStick), 0) { hold = true },
            new Spec("LockNext", "Siguiente objetivo", GroupCombat, Play, 0, BindCode.WheelDown, 0, BindCode.RStickRight, 0),
            new Spec("LockPrev", "Objetivo anterior", GroupCombat, Play, 0, BindCode.WheelUp, 0, BindCode.RStickLeft, 0),
            new Spec("Finisher", "Ejecutar", GroupCombat, Play, ShareFinish, K(Key.F), 0, P(GamepadButton.North), 0),
            new Spec("Ability1", "Corte del Viento", GroupCombat, Play, 0, K(Key.Digit1), K(Key.U), P(GamepadButton.RightTrigger), 0),
            new Spec("Ability2", "Torbellino de Hojas", GroupCombat, Play, 0, K(Key.Digit2), K(Key.I), P(GamepadButton.LeftTrigger), 0),
            new Spec("Interact", "Interactuar", GroupExplore, Play, ShareFinish, K(Key.E), K(Key.F), P(GamepadButton.North), 0),
            // el mapa se abre desde la pausa y se cierra con su misma tecla (UI/UIMap.cs): también es de menú, así que ni
            // Enter / A / B ni nada de lo que usan los menús y el mapa abierto (el clic arrastra, la rueda acerca). En los
            // de PlayStation el panel táctil también lo abre, como en sus juegos: fijo y solo para mostrar (en un Xbox no
            // hay, y esa casilla queda vacía)
            new Spec("Map", "Mapa", GroupExplore, Play | Menu | MapView, 0, K(Key.M), 0, P(GamepadButton.Select), BindCode.PadTouchpad | L),
            // Esc y Start pausan siempre: así nunca se puede quedar sin forma de abrir el menú
            new Spec("Pause", "Pausa", GroupMenu, Play | Menu | MapView, ShareBack, K(Key.Escape) | L, K(Key.P), P(GamepadButton.Start) | L, 0),
            // confirmar y volver son los de la navegación de los menús (el EventSystem usa Enter / A y Esc / B)
            new Spec("Submit", "Confirmar", GroupMenu, Menu, 0, K(Key.Enter) | L, L, P(GamepadButton.South) | L, L),
            // también cierra el mapa: fijar no puede tener la B (cerraría el mapa y centraría a la vez)
            new Spec("Cancel", "Volver", GroupMenu, Menu | MapView, ShareBack, K(Key.Escape) | L, L, P(GamepadButton.East) | L, L),
        };

        // con el mapa abierto el movimiento corre el cursor de la lámina
        static readonly Spec[] MoveSpecs =
        {
            new Spec("MoveUp", "Mover arriba", GroupMove, Play | MapView, 0, K(Key.W), K(Key.UpArrow), 0, 0),
            new Spec("MoveDown", "Mover abajo", GroupMove, Play | MapView, 0, K(Key.S), K(Key.DownArrow), 0, 0),
            new Spec("MoveLeft", "Mover a la izquierda", GroupMove, Play | MapView, 0, K(Key.A), K(Key.LeftArrow), 0, 0),
            new Spec("MoveRight", "Mover a la derecha", GroupMove, Play | MapView, 0, K(Key.D), K(Key.RightArrow), 0, 0),
        };

        /// <summary>
        /// Una fila por acción en el orden de 'actNames' (la fila r es la acción (Act)r: Enum.GetNames va por valor) y
        /// después las del movimiento: cuatro direcciones en el teclado y una fila fija en el mando (stick y cruceta).
        /// </summary>
        public static BindRow[] Build(IList<string> actNames)
        {
            var rows = new List<BindRow>(actNames.Count + 5);
            for (int i = 0; i < actNames.Count; i++)
            {
                int si = Array.FindIndex(Specs, s => s.id == actNames[i]);
                var row = si >= 0 ? FromSpec(Specs[si], si) : new BindRow { id = actNames[i], label = actNames[i], group = GroupExplore, order = 100 + i, context = Play };
                if (si < 0) { row.shown[BindingTable.Keys] = true; row.shown[BindingTable.Pad] = true; }
                row.act = i;
                rows.Add(row);
            }
            for (int i = 0; i < MoveSpecs.Length; i++)
            {
                var row = FromSpec(MoveSpecs[i], i);
                row.move = i + 1;
                row.hold = true;
                row.shown[BindingTable.Pad] = false;
                rows.Add(row);
            }
            var pad = new BindRow { id = "MovePad", label = "Moverse", group = GroupMove, order = 0, context = Play | MapView };
            pad.shown[BindingTable.Pad] = true;
            pad.defaults[2] = BindCode.PadMoveStick; pad.defaults[3] = BindCode.PadMoveDpad;
            for (int s = 0; s < 4; s++) pad.locked[s] = true;
            rows.Add(pad);
            return rows.ToArray();
        }

        static BindRow FromSpec(Spec s, int order)
        {
            var row = new BindRow { id = s.id, label = s.label, group = s.group, order = order, context = s.ctx, share = s.share, hold = s.hold };
            row.shown[BindingTable.Keys] = true; row.shown[BindingTable.Pad] = true;
            int[] c = { s.k0, s.k1, s.p0, s.p1 };
            for (int i = 0; i < 4; i++) { row.locked[i] = (c[i] & L) != 0; row.defaults[i] = c[i] & ~L; }
            return row;
        }

        /// <summary>
        /// Lo que no se le asigna a nada, con el motivo (la página de controles arma el aviso): Esc y Start (pausan y
        /// vuelven: nunca se pierde la forma de abrir el menú), las teclas del sistema y la cruceta, que mueve a Kaito.
        /// </summary>
        public static string Reserved(int code)
        {
            switch (code)
            {
                case (int)Key.Escape: case BindCode.PadBase + (int)GamepadButton.Start: return "pausa";
                case (int)Key.LeftMeta: case (int)Key.RightMeta: case (int)Key.PrintScreen: return "sistema";
                case BindCode.PadBase + (int)GamepadButton.DpadUp: case BindCode.PadBase + (int)GamepadButton.DpadDown:
                case BindCode.PadBase + (int)GamepadButton.DpadLeft: case BindCode.PadBase + (int)GamepadButton.DpadRight:
                    return "cruceta";
            }
            return null;
        }

        /// <summary>
        /// Lo que usan los menús y el mapa abierto por su cuenta, sin pasar por la tabla: el puntero y sus botones, la
        /// rueda (corre las listas, acerca el mapa), la navegación del EventSystem (WASD, flechas, los dos sticks), Supr,
        /// Retroceso y X / □ (quitan una tecla en Opciones › Controles) y el zoom del mapa (gatillos, + y -). Una acción
        /// que se lee con un menú abierto (pausa, mapa) no lo puede tener: un clic en "Opciones" también cerraría la
        /// pausa. El + y el - de la distribución del teclado los suma InputBindings.
        /// </summary>
        public static string MenuReserved(int code)
        {
            switch (code)
            {
                case BindCode.MouseLeft: case BindCode.MouseRight: case BindCode.MouseMiddle:
                case BindCode.WheelUp: case BindCode.WheelDown:
                case (int)Key.W: case (int)Key.A: case (int)Key.S: case (int)Key.D:
                case (int)Key.UpArrow: case (int)Key.DownArrow: case (int)Key.LeftArrow: case (int)Key.RightArrow:
                case (int)Key.Delete: case (int)Key.Backspace:
                case (int)Key.Equals: case (int)Key.Minus: case (int)Key.NumpadPlus: case (int)Key.NumpadMinus:
                case BindCode.PadBase + (int)GamepadButton.West:
                case BindCode.PadBase + (int)GamepadButton.LeftTrigger: case BindCode.PadBase + (int)GamepadButton.RightTrigger:
                case BindCode.RStickUp: case BindCode.RStickDown: case BindCode.RStickLeft: case BindCode.RStickRight:
                    return "menu";
            }
            return null;
        }

        /// <summary>
        /// Lo que el mapa abierto lee por su cuenta (UI/UIMap.cs MapControls): el clic izquierdo arrastra la lámina, la
        /// rueda, + y - (también los del teclado numérico) y los gatillos acercan y alejan, y el stick derecho hacia arriba
        /// o abajo también. Lo que se lee con el mapa abierto (fijar, moverse) no lo puede tener: un clic para arrastrar
        /// también centraría en Kaito. El + y el - de la distribución del teclado los suma InputBindings.
        /// </summary>
        public static string MapReserved(int code)
        {
            switch (code)
            {
                case BindCode.MouseLeft: case BindCode.WheelUp: case BindCode.WheelDown:
                case (int)Key.Equals: case (int)Key.Minus: case (int)Key.NumpadPlus: case (int)Key.NumpadMinus:
                case BindCode.PadBase + (int)GamepadButton.LeftTrigger: case BindCode.PadBase + (int)GamepadButton.RightTrigger:
                case BindCode.RStickUp: case BindCode.RStickDown:
                    return "mapa";
            }
            return null;
        }

        // teclas que nadie usa de fábrica, de las más a mano a las menos (BindingTable.Load las da en este orden)
        static readonly int[] SpareKeys =
        {
            K(Key.N), K(Key.B), K(Key.G), K(Key.H), K(Key.T), K(Key.R), K(Key.Z), K(Key.X), K(Key.C), K(Key.V),
            K(Key.CapsLock), K(Key.Digit3), K(Key.Digit4), K(Key.Digit5), K(Key.L), K(Key.O), K(Key.Y),
        };
        static readonly int[] SparePad =
        {
            P(GamepadButton.Select), P(GamepadButton.LeftStick), P(GamepadButton.RightShoulder), P(GamepadButton.LeftShoulder),
            P(GamepadButton.North), P(GamepadButton.RightStick),
        };

        /// <summary>Para la acción que al cargar queda sin nada en un dispositivo (sus teclas de fábrica ya eran de otra).</summary>
        public static int[] Spares(int dev) => dev == BindingTable.Keys ? SpareKeys : SparePad;

        // ================================================================== nombres para guardar
        // GamepadButton tiene alias (A = South, Cross = South...) y Enum.GetName elegiría cualquiera: van fijos
        static readonly (int code, string id)[] OtherIds =
        {
            (BindCode.MouseLeft, "Mouse.Left"), (BindCode.MouseRight, "Mouse.Right"), (BindCode.MouseMiddle, "Mouse.Middle"),
            (BindCode.MouseForward, "Mouse.Forward"), (BindCode.MouseBack, "Mouse.Back"),
            (BindCode.WheelUp, "Mouse.WheelUp"), (BindCode.WheelDown, "Mouse.WheelDown"),
            (P(GamepadButton.North), "Pad.North"), (P(GamepadButton.East), "Pad.East"), (P(GamepadButton.South), "Pad.South"),
            (P(GamepadButton.West), "Pad.West"), (P(GamepadButton.LeftShoulder), "Pad.LeftShoulder"),
            (P(GamepadButton.RightShoulder), "Pad.RightShoulder"), (P(GamepadButton.LeftTrigger), "Pad.LeftTrigger"),
            (P(GamepadButton.RightTrigger), "Pad.RightTrigger"), (P(GamepadButton.LeftStick), "Pad.LeftStick"),
            (P(GamepadButton.RightStick), "Pad.RightStick"), (P(GamepadButton.Start), "Pad.Start"), (P(GamepadButton.Select), "Pad.Select"),
            (P(GamepadButton.DpadUp), "Pad.DpadUp"), (P(GamepadButton.DpadDown), "Pad.DpadDown"),
            (P(GamepadButton.DpadLeft), "Pad.DpadLeft"), (P(GamepadButton.DpadRight), "Pad.DpadRight"),
            (BindCode.RStickUp, "Pad.RStickUp"), (BindCode.RStickDown, "Pad.RStickDown"),
            (BindCode.RStickLeft, "Pad.RStickLeft"), (BindCode.RStickRight, "Pad.RStickRight"),
        };

        /// <summary>Nombre estable para guardar ("Key.J", "Mouse.Left", "Pad.West"); null si no es un control conocido.</summary>
        public static string CodeId(int code)
        {
            if (BindCode.IsKey(code)) return Enum.IsDefined(typeof(Key), code) ? "Key." + Enum.GetName(typeof(Key), code) : null;
            foreach (var o in OtherIds) if (o.code == code) return o.id;
            return null;
        }

        public static int ParseCode(string id)
        {
            if (string.IsNullOrEmpty(id)) return BindCode.None;
            if (id.StartsWith("Key.", StringComparison.Ordinal))
                return Enum.TryParse(id.Substring(4), false, out Key k) && k != Key.None && Enum.IsDefined(typeof(Key), k) && IsBindableKey(k) ? (int)k : BindCode.None;
            foreach (var o in OtherIds) if (o.id == id) return o.code;
            return BindCode.None;
        }

        /// <summary>Las teclas que se pueden tomar al reasignar (afuera: la de relleno del IME y las de medios).</summary>
        public static bool IsBindableKey(Key k) => (k > Key.None && k <= Key.OEM5) || (k >= Key.F13 && k <= Key.F24);
    }
}
