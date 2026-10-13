using System;
using System.Collections.Generic;
using System.Text;

namespace Nindo
{
    /// <summary>
    /// Códigos de los controles que se le pueden asignar a una acción. Un entero por control (sin tipos de
    /// Unity: la tabla se prueba fuera del editor): las teclas son el valor de UnityEngine.InputSystem.Key, el
    /// mouse y el mando van en sus propios rangos. Se guardan por nombre (BindingCatalog.CodeId), no por número.
    /// </summary>
    public static class BindCode
    {
        public const int None = 0;
        // teclado: 1..999 = (int)Key
        public const int MouseLeft = 1001, MouseRight = 1002, MouseMiddle = 1003, MouseForward = 1004, MouseBack = 1005;
        public const int WheelUp = 1006, WheelDown = 1007;
        /// <summary>Botones del mando: PadBase + (int)GamepadButton.</summary>
        public const int PadBase = 2000;
        /// <summary>Toques del stick derecho (cuentan una vez y se rearman al volver al centro).</summary>
        public const int RStickUp = 2100, RStickDown = 2101, RStickLeft = 2102, RStickRight = 2103;
        /// <summary>Solo para mostrar: el movimiento del mando es fijo (stick izquierdo y cruceta).</summary>
        public const int PadMoveStick = 2200, PadMoveDpad = 2201;

        public static int Pad(int gamepadButton) => PadBase + gamepadButton;
        public static bool IsKey(int c) => c > 0 && c < 1000;
        public static bool IsMouse(int c) => c > 1000 && c < PadBase;
        public static bool IsPad(int c) => c >= PadBase;
        public static int DeviceOf(int c) => c >= PadBase ? BindingTable.Pad : BindingTable.Keys;
        /// <summary>La rueda y los toques del stick son un impulso: no se pueden mantener (no sirven para moverse).</summary>
        public static bool IsImpulse(int c) => c == WheelUp || c == WheelDown || (c >= RStickUp && c <= RStickRight);
        public static bool IsDisplayOnly(int c) => c == PadMoveStick || c == PadMoveDpad;
    }

    /// <summary>Una fila de la tabla: una acción de <see cref="Act"/> o una dirección del movimiento.</summary>
    public sealed class BindRow
    {
        public string id;              // nombre de la acción ("Attack") o del movimiento ("MoveUp"): así se guarda
        public string label;           // "Atacar"
        public int group;              // BindingCatalog.GroupMove...
        public int order;              // orden dentro del grupo en la página de controles
        public int act = -1;           // valor de Act (-1 = movimiento)
        public int move;               // 0 no mueve; 1 arriba, 2 abajo, 3 izquierda, 4 derecha
        public bool hold;              // se usa manteniendo (moverse; fijar se suelta así): nada de rueda ni toques del stick
        public int context;            // máscara: dónde se usa (BindingCatalog.Play / Menu)
        public int share;              // != 0: puede compartir tecla con las filas del mismo número
        public readonly bool[] shown = new bool[BindingTable.Devices];
        public readonly int[] defaults = new int[BindingTable.Devices * BindingTable.Slots];
        /// <summary>Casillas fijas: ni se cambian ni se quitan (Esc pausa, Enter confirma...).</summary>
        public readonly bool[] locked = new bool[BindingTable.Devices * BindingTable.Slots];
    }

    public enum BindOutcome { Assigned, Same, Swapped, Taken, OwnSwap, Cleared, Refused }

    public enum BindRefusal
    {
        None,
        Locked,             // la casilla es fija
        Reserved,           // el control no se asigna a nada (Esc, Win, la cruceta...) o a nada de los menús: ver 'reason'
        LockedElsewhere,    // es la tecla fija de otra acción que choca con esta (Enter para pausar)
        OnlyKey,            // es la única tecla de la otra acción y no hay nada para darle a cambio
        NeedsHold,          // la acción se mantiene apretada (moverse, fijar): no sirven la rueda ni los toques del stick
        WrongDevice,
        LastKey,            // quitar dejaría a la acción sin teclas en ese dispositivo
    }

    /// <summary>Una acción que al cargar quedó sin nada en un dispositivo y recibió una tecla libre (ver BindingTable.Load).</summary>
    public struct BindRescue
    {
        public int row, dev, code;
        /// <summary>Su tecla de fábrica y quién la tiene (el jugador se la dio a otra acción antes de que esta existiera).</summary>
        public int lost, holder;
    }

    public struct BindResult
    {
        public BindOutcome outcome;
        public BindRefusal refusal;
        public int row, dev, slot, code, previous;
        /// <summary>Filas a las que les cambió algo (intercambio o quita); la primera también en 'other'.</summary>
        public int[] others;
        public int other;
        /// <summary>Lo que le quedó a 'other': la tecla que recibió (Swapped) o la que conserva (Taken).</summary>
        public int otherCode;
        public string reason;
        public bool Ok => outcome != BindOutcome.Refused;
        public bool Changed => outcome != BindOutcome.Refused && outcome != BindOutcome.Same;
    }

    /// <summary>
    /// Qué teclas y botones tiene cada acción, con las reglas para cambiarlas. Dos casillas por dispositivo
    /// (principal y alternativa; teclado y mouse por un lado, mando por el otro).
    /// Reglas (las prueba Tools/Dev/bindings_test):
    ///   - Dos acciones que se usan en el mismo momento (mismo contexto) no comparten tecla, salvo las que el juego
    ///     ya resuelve juntas (Ejecutar e Interactuar: gana el remate si hay alguien para rematar; Pausa y Volver).
    ///   - Si la tecla nueva ya era de otra acción, se INTERCAMBIAN: la otra recibe la que tenía esta casilla. Se
    ///     eligió sobre rechazar porque respeta lo que el jugador quiso (esa tecla para esta acción), nunca deja a la
    ///     otra sin tecla ni pierde nada, y un aviso de dos renglones dice qué pasó. No se le da a cambio lo que no
    ///     le serviría: si le queda otra tecla y lo que recibiría es de otra clase (un botón del mouse para moverse,
    ///     una tecla para el parry que estaba en el mouse), solo pierde la suya. Se rechaza solo lo que rompería algo:
    ///     las teclas reservadas, las fijas de otra acción, la rueda o un toque del stick para lo que se mantiene
    ///     apretado (moverse, fijar: se suelta manteniéndolo) y sacarle a otra acción su única tecla sin nada para
    ///     darle a cambio.
    ///   - Una acción que también se lee con un menú abierto (la pausa, el mapa) no puede tener nada de lo que usan los
    ///     menús (el clic, la rueda, WASD y las flechas, Supr...): la misma tecla movería el menú y lo cerraría.
    ///   - Quitar una tecla no puede dejar a una acción sin ninguna en ese dispositivo.
    /// Se guardan solo las casillas que difieren de las de fábrica, por nombre de acción: una acción nueva (p. ej. el
    /// mapa) llega con sus teclas de fábrica y, si alguna ya la usa el jugador para otra cosa, gana la del jugador.
    /// </summary>
    public sealed class BindingTable
    {
        public const int Keys = 0, Pad = 1, Devices = 2, Slots = 2;
        /// <summary>Bit de BindRow.context de lo que se lee con un menú abierto (BindingCatalog.Menu).</summary>
        public const int MenuContext = 2;
        /// <summary>Formato de lo guardado. Si cambia de forma incompatible se vuelve a las de fábrica.</summary>
        public const int FormatVersion = 1;

        readonly BindRow[] rows;
        readonly int[] codes;
        readonly Func<int, string> reserved, menuReserved;
        readonly Func<int, int[]> spares;

        /// <summary>Lo que hizo la última carga para que ninguna acción quede sin teclas (para avisarle al jugador).</summary>
        public readonly List<BindRescue> Rescued = new List<BindRescue>();

        /// <param name="reserved">Motivo por el que un control no se puede asignar a nada (null = libre).</param>
        /// <param name="menuReserved">Motivo por el que un control no sirve para lo que se lee con un menú abierto.</param>
        /// <param name="spares">Teclas libres por dispositivo, en orden, para la acción que al cargar quede sin nada.</param>
        public BindingTable(BindRow[] rows, Func<int, string> reserved, Func<int, string> menuReserved = null, Func<int, int[]> spares = null)
        {
            this.rows = rows;
            this.reserved = reserved;
            this.menuReserved = menuReserved;
            this.spares = spares;
            codes = new int[rows.Length * Devices * Slots];
            Reset(-1);
        }

        public int RowCount => rows.Length;
        public BindRow Row(int r) => rows[r];

        static int Ix(int r, int dev, int slot) => (r * Devices + dev) * Slots + slot;

        public int Get(int r, int dev, int slot) => codes[Ix(r, dev, slot)];
        public bool Locked(int r, int dev, int slot) => rows[r].locked[dev * Slots + slot];
        public int Default(int r, int dev, int slot) => rows[r].defaults[dev * Slots + slot];

        /// <summary>Cuántas casillas con algo tiene la fila en ese dispositivo.</summary>
        public int Count(int r, int dev) => (Get(r, dev, 0) != 0 ? 1 : 0) + (Get(r, dev, 1) != 0 ? 1 : 0);

        public int IndexOf(string id)
        {
            for (int i = 0; i < rows.Length; i++) if (rows[i].id == id) return i;
            return -1;
        }

        /// <summary>¿Pueden apretarse a la vez sin que una tecla haga dos cosas que no van juntas?</summary>
        public bool Conflicts(int a, int b)
        {
            if (a == b) return false;
            var ra = rows[a]; var rb = rows[b];
            if ((ra.context & rb.context) == 0) return false;
            return ra.share == 0 || ra.share != rb.share;
        }

        public void Reset(int dev)
        {
            for (int r = 0; r < rows.Length; r++)
                for (int d = 0; d < Devices; d++)
                {
                    if (dev >= 0 && d != dev) continue;
                    for (int s = 0; s < Slots; s++) codes[Ix(r, d, s)] = rows[r].defaults[d * Slots + s];
                }
        }

        /// <summary>¿El dispositivo está como de fábrica?</summary>
        public bool IsDefault(int dev)
        {
            for (int r = 0; r < rows.Length; r++)
                for (int s = 0; s < Slots; s++)
                    if (Get(r, dev, s) != Default(r, dev, s)) return false;
            return true;
        }

        /// <summary>Por qué 'code' no le sirve a la fila r por leerse con un menú abierto (null si le sirve).</summary>
        string MenuBlock(int r, int code) => (rows[r].context & MenuContext) != 0 ? menuReserved?.Invoke(code) : null;

        /// <summary>¿La fila r puede tener 'code' en ese dispositivo? (sin mirar a las demás filas)</summary>
        bool Fits(int r, int dev, int code) =>
            code != BindCode.None && BindCode.DeviceOf(code) == dev && !BindCode.IsDisplayOnly(code) && reserved?.Invoke(code) == null &&
            MenuBlock(r, code) == null && !(rows[r].hold && BindCode.IsImpulse(code));

        BindResult Refuse(BindResult res, BindRefusal why)
        {
            res.outcome = BindOutcome.Refused;
            res.refusal = why;
            return res;
        }

        /// <summary>Le da 'code' a la casilla (fila, dispositivo, casilla) con las reglas de arriba.</summary>
        public BindResult Assign(int r, int dev, int slot, int code)
        {
            var res = new BindResult { row = r, dev = dev, slot = slot, code = code, other = -1, previous = Get(r, dev, slot) };
            var row = rows[r];
            if (code == BindCode.None) return Clear(r, dev, slot);
            if (!row.shown[dev] || Locked(r, dev, slot)) return Refuse(res, BindRefusal.Locked);
            if (BindCode.DeviceOf(code) != dev || BindCode.IsDisplayOnly(code)) return Refuse(res, BindRefusal.WrongDevice);
            string why = reserved?.Invoke(code);
            if (why != null) { res.reason = why; return Refuse(res, BindRefusal.Reserved); }
            why = MenuBlock(r, code);
            if (why != null) { res.reason = why; return Refuse(res, BindRefusal.Reserved); }
            if (row.hold && BindCode.IsImpulse(code)) return Refuse(res, BindRefusal.NeedsHold);
            int old = res.previous;
            if (old == code) { res.outcome = BindOutcome.Same; return res; }

            int o = 1 - slot;
            if (Get(r, dev, o) == code)
            {
                // ya era la otra casilla de esta acción: se cambian principal y alternativa (si la de acá estaba
                // vacía no hay nada que cambiar: la acción ya usa esa tecla)
                if (old == BindCode.None) { res.outcome = BindOutcome.Same; return res; }
                if (Locked(r, dev, o)) return Refuse(res, BindRefusal.Locked);
                codes[Ix(r, dev, o)] = old;
                codes[Ix(r, dev, slot)] = code;
                res.outcome = BindOutcome.OwnSwap;
                return res;
            }

            // quién más la tiene y choca con esta acción
            var holders = new List<int>(2);   // fila * Slots + casilla
            for (int q = 0; q < rows.Length; q++)
            {
                if (q == r || !rows[q].shown[dev] || !Conflicts(r, q)) continue;
                for (int t = 0; t < Slots; t++)
                    if (Get(q, dev, t) == code)
                    {
                        if (Locked(q, dev, t)) { res.other = q; return Refuse(res, BindRefusal.LockedElsewhere); }
                        holders.Add(q * Slots + t);
                    }
            }

            // qué recibe cada una: la tecla vieja de esta casilla, salvo que no le sirva (la rueda para moverse o fijar, el
            // clic para la pausa), ya la tenga en su otra casilla, choque con otra acción que también la usa o, si le queda
            // otra tecla, sea de otra clase que la que pierde (teclado contra mouse: el jugador nunca pidió ese cambio)
            var gives = new int[holders.Count];
            for (int h = 0; h < holders.Count; h++)
            {
                int q = holders[h] / Slots, t = holders[h] % Slots;
                int give = old;
                if (give != BindCode.None)
                {
                    if (rows[q].hold && BindCode.IsImpulse(give)) give = BindCode.None;
                    else if (MenuBlock(q, give) != null) give = BindCode.None;
                    else if (Get(q, dev, 1 - t) == give) give = BindCode.None;
                    else if (HeldByConflicting(give, dev, q, r)) give = BindCode.None;
                    else if (Count(q, dev) >= 2 && BindCode.IsKey(give) != BindCode.IsKey(code)) give = BindCode.None;
                }
                if (give == BindCode.None && Count(q, dev) <= 1) { res.other = q; return Refuse(res, BindRefusal.OnlyKey); }
                gives[h] = give;
            }

            codes[Ix(r, dev, slot)] = code;
            res.others = new int[holders.Count];
            for (int h = 0; h < holders.Count; h++)
            {
                int q = holders[h] / Slots, t = holders[h] % Slots;
                codes[Ix(q, dev, t)] = gives[h];
                res.others[h] = q;
            }
            if (holders.Count == 0) { res.outcome = BindOutcome.Assigned; return res; }
            int q0 = holders[0] / Slots, t0 = holders[0] % Slots;
            res.other = q0;
            res.outcome = gives[0] != BindCode.None ? BindOutcome.Swapped : BindOutcome.Taken;
            res.otherCode = gives[0] != BindCode.None ? gives[0] : Get(q0, dev, 1 - t0);
            return res;
        }

        /// <summary>¿Alguna fila, fuera de 'q' y de 'skip', usa 'code' y choca con 'q'?</summary>
        bool HeldByConflicting(int code, int dev, int q, int skip)
        {
            for (int p = 0; p < rows.Length; p++)
            {
                if (p == q || p == skip || !rows[p].shown[dev] || !Conflicts(p, q)) continue;
                if (Get(p, dev, 0) == code || Get(p, dev, 1) == code) return true;
            }
            return false;
        }

        public BindResult Clear(int r, int dev, int slot)
        {
            var res = new BindResult { row = r, dev = dev, slot = slot, other = -1, previous = Get(r, dev, slot) };
            if (!rows[r].shown[dev] || Locked(r, dev, slot)) return Refuse(res, BindRefusal.Locked);
            if (res.previous == BindCode.None) { res.outcome = BindOutcome.Same; return res; }
            if (Count(r, dev) <= 1) return Refuse(res, BindRefusal.LastKey);
            codes[Ix(r, dev, slot)] = BindCode.None;
            res.outcome = BindOutcome.Cleared;
            return res;
        }

        // ================================================================== guardar y cargar
        static char DevChar(int dev) => dev == Keys ? 'k' : 'p';

        /// <summary>"1|Attack.k1=Key.L|Dash.p0=-": versión y las casillas que no son las de fábrica.</summary>
        public string Save(Func<int, string> codeId)
        {
            var sb = new StringBuilder(64);
            sb.Append(FormatVersion);
            for (int r = 0; r < rows.Length; r++)
                for (int d = 0; d < Devices; d++)
                    for (int s = 0; s < Slots; s++)
                    {
                        int c = Get(r, d, s);
                        if (Locked(r, d, s) || c == Default(r, d, s)) continue;
                        string name = c == BindCode.None ? "-" : codeId(c);
                        if (name == null) continue;
                        sb.Append('|').Append(rows[r].id).Append('.').Append(DevChar(d)).Append(s).Append('=').Append(name);
                    }
            return sb.ToString();
        }

        /// <summary>
        /// Vuelve a las de fábrica y aplica lo guardado. Lo que no se entiende (una acción que ya no existe, una
        /// tecla desconocida, una casilla fija) se ignora. Si lo guardado choca con una tecla de fábrica (una acción
        /// nueva que trae la tecla que el jugador ya usa), gana lo del jugador; si una acción queda sin teclas se le
        /// devuelven las de fábrica que no choquen y, si no queda ninguna, la primera libre de 'spares' (queda en
        /// <see cref="Rescued"/>). Devuelve lo que no se pudo aplicar (para el log).
        /// </summary>
        public List<string> Load(string data, Func<string, int> parseCode)
        {
            var problems = new List<string>();
            Rescued.Clear();
            Reset(-1);
            if (string.IsNullOrEmpty(data)) return problems;
            var parts = data.Split('|');
            if (!int.TryParse(parts[0], out int ver) || ver != FormatVersion)
            {
                problems.Add("formato " + parts[0] + ": se usan las de fábrica");
                return problems;
            }
            var user = new bool[codes.Length];
            for (int i = 1; i < parts.Length; i++)
            {
                // "Attack.k1=Key.L": el nombre de la tecla también lleva punto, por eso se corta primero en el '='
                string p = parts[i];
                int eq = p.IndexOf('=');
                int dot = eq > 0 ? p.LastIndexOf('.', eq - 1) : -1;
                if (dot <= 0 || eq != dot + 3) { problems.Add(p); continue; }
                int r = IndexOf(p.Substring(0, dot));
                int d = p[dot + 1] == 'k' ? Keys : p[dot + 1] == 'p' ? Pad : -1;
                int s = p[dot + 2] == '0' ? 0 : p[dot + 2] == '1' ? 1 : -1;
                if (r < 0 || d < 0 || s < 0 || Locked(r, d, s) || !rows[r].shown[d]) { problems.Add(p); continue; }
                string name = p.Substring(eq + 1);
                int c = name == "-" ? BindCode.None : parseCode(name);
                if (name != "-" && !Fits(r, d, c)) { problems.Add(p); continue; }
                codes[Ix(r, d, s)] = c;
                user[Ix(r, d, s)] = true;
            }
            for (int d = 0; d < Devices; d++) Resolve(d, user, problems);
            return problems;
        }

        /// <summary>
        /// Deja el dispositivo sin choques: entre lo del jugador y lo de fábrica gana lo del jugador (entre dos del
        /// jugador, solo posible con datos rotos, la primera); una casilla fija nunca pierde. A la acción que quedó
        /// sin nada se le devuelven sus teclas de fábrica que no choquen con nadie y, si todas están tomadas (llega el
        /// mapa y el jugador ya atacaba con la M), la primera libre de 'spares': ninguna acción que tenga teclas de
        /// fábrica queda sin forma de usarse. Una que nunca tuvo (una acción nueva sin catálogo) sigue sin nada.
        /// </summary>
        void Resolve(int d, bool[] user, List<string> problems)
        {
            for (int r = 0; r < rows.Length; r++)
            {
                if (!rows[r].shown[d]) continue;
                for (int s = 0; s < Slots; s++)
                {
                    int a = Ix(r, d, s);
                    for (int q = r; q < rows.Length && codes[a] != BindCode.None; q++)
                    {
                        if (!rows[q].shown[d] || (q != r && !Conflicts(r, q))) continue;
                        for (int t = q == r ? s + 1 : 0; t < Slots && codes[a] != BindCode.None; t++)
                        {
                            int b = Ix(q, d, t);
                            if (codes[b] != codes[a]) continue;
                            bool la = Locked(r, d, s), lb = Locked(q, d, t);
                            if (la && lb) continue;
                            bool loseA = !la && (lb || (!user[a] && user[b]));
                            problems.Add((loseA ? rows[r].id : rows[q].id) + " pierde " + codes[a] + ": ya la usa " + (loseA ? rows[q].id : rows[r].id));
                            codes[loseA ? a : b] = BindCode.None;
                        }
                    }
                }
            }
            for (int r = 0; r < rows.Length; r++)
            {
                if (!rows[r].shown[d] || Count(r, d) > 0) continue;
                int lost = BindCode.None;
                for (int s = 0; s < Slots; s++)
                {
                    int c = Default(r, d, s);
                    if (c == BindCode.None) continue;
                    if (lost == BindCode.None) lost = c;
                    if (!HeldByConflicting(c, d, r, r)) codes[Ix(r, d, s)] = c;
                }
                if (Count(r, d) > 0 || lost == BindCode.None || spares == null) continue;
                int slot = Locked(r, d, 0) ? 1 : 0;
                if (Locked(r, d, slot)) continue;
                foreach (int c in spares(d))
                {
                    if (!Fits(r, d, c) || HeldByConflicting(c, d, r, r)) continue;
                    codes[Ix(r, d, slot)] = c;
                    Rescued.Add(new BindRescue { row = r, dev = d, code = c, lost = lost, holder = HolderOf(lost, d, r) });
                    problems.Add(rows[r].id + " recibe " + c + ": sus teclas de fábrica ya estaban tomadas");
                    break;
                }
            }
        }

        /// <summary>La primera fila que choca con 'r' y tiene 'code' (-1 si ninguna).</summary>
        int HolderOf(int code, int dev, int r)
        {
            for (int p = 0; p < rows.Length; p++)
                if (p != r && rows[p].shown[dev] && Conflicts(p, r) && (Get(p, dev, 0) == code || Get(p, dev, 1) == code)) return p;
            return -1;
        }

        /// <summary>Para las pruebas: ¿dos casillas que chocan, una acción con la misma tecla dos veces o una de menú con algo de los menús?</summary>
        public string FindProblem()
        {
            for (int d = 0; d < Devices; d++)
                for (int r = 0; r < rows.Length; r++)
                {
                    if (!rows[r].shown[d]) continue;
                    for (int s = 0; s < Slots; s++)
                    {
                        int c = Get(r, d, s);
                        if (c == BindCode.None) continue;
                        if (s == 0 && Get(r, d, 1) == c) return rows[r].id + " repite " + c;
                        if (!Locked(r, d, s) && MenuBlock(r, c) != null) return rows[r].id + " tiene " + c + ", que usan los menús";
                        for (int q = r + 1; q < rows.Length; q++)
                            if (rows[q].shown[d] && Conflicts(r, q) && (Get(q, d, 0) == c || Get(q, d, 1) == c))
                                return rows[r].id + " y " + rows[q].id + " comparten " + c + " (dispositivo " + d + ")";
                    }
                }
            return null;
        }
    }
}
