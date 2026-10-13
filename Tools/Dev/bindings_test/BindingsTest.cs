// Pruebas de la tabla de controles (Input/BindingTable.cs + BindingCatalog.cs) fuera de Unity.
// Las corre Tools/Dev/bindings_test.py (compila estos tres archivos con dotnet y el enum Key del Input System).
using System;
using System.Collections.Generic;
using System.Linq;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;

namespace Nindo.Tests
{
    static class BindingsTest
    {
        // Act de hoy (Input/InputReader.cs) y con el mapa que agrega el frente ui-map al final
        static readonly string[] Acts = { "Attack", "Parry", "Dash", "Lock", "Finisher", "Interact", "Ability1", "Ability2", "Pause", "LockNext", "LockPrev", "Submit", "Cancel" };
        static readonly string[] ActsMap = Acts.Concat(new[] { "Map" }).ToArray();

        static int fails, checks;

        static void Check(bool ok, string what)
        {
            checks++;
            if (!ok) { fails++; Console.WriteLine("FALLA: " + what); }
        }

        static BindingTable New(string[] acts) => new BindingTable(BindingCatalog.Build(acts), BindingCatalog.Reserved, BindingCatalog.MenuReserved, BindingCatalog.MapReserved, BindingCatalog.Spares);

        static int R(BindingTable t, string id) { int r = t.IndexOf(id); if (r < 0) throw new Exception("sin fila " + id); return r; }
        static int K(Key k) => (int)k;
        static int P(GamepadButton b) => BindCode.Pad((int)b);
        const int Kb = BindingTable.Keys, Pd = BindingTable.Pad;

        static int Main()
        {
            Defaults();
            SameAsOldReader();
            Swaps();
            Refusals();
            MenuInputs();
            MapInputs();
            Touchpad();
            ClearRules();
            Persistence();
            NewActionMerge();
            Fuzz(200000, 7);
            Fuzz(200000, 1234);
            Console.WriteLine($"{checks} comprobaciones, {fails} fallas");
            return fails == 0 ? 0 : 1;
        }

        static void Defaults()
        {
            foreach (var acts in new[] { Acts, ActsMap })
            {
                var t = New(acts);
                Check(t.FindProblem() == null, "las de fábrica chocan: " + t.FindProblem());
                for (int r = 0; r < t.RowCount; r++)
                    for (int d = 0; d < 2; d++)
                        if (t.Row(r).shown[d]) Check(t.Count(r, d) >= 1, $"{t.Row(r).id} sin teclas de fábrica en {d}");
                // la fila r es la acción (Act)r
                for (int i = 0; i < acts.Length; i++) Check(t.Row(i).id == acts[i] && t.Row(i).act == i, "fila de " + acts[i]);
                Check(t.Locked(R(t, "Pause"), Kb, 0) && t.Get(R(t, "Pause"), Kb, 0) == K(Key.Escape), "Esc fija en Pausa");
                Check(t.Locked(R(t, "Pause"), Pd, 0) && t.Get(R(t, "Pause"), Pd, 0) == P(GamepadButton.Start), "Start fijo en Pausa");
                Check(t.Get(R(t, "Submit"), Kb, 0) == K(Key.Enter) && t.Get(R(t, "Submit"), Pd, 0) == P(GamepadButton.South), "Confirmar");
                Check(t.Get(R(t, "Cancel"), Kb, 0) == K(Key.Escape) && t.Get(R(t, "Cancel"), Pd, 0) == P(GamepadButton.East), "Volver");
                Check(t.IsDefault(Kb) && t.IsDefault(Pd), "IsDefault");
            }
        }

        /// <summary>Lo de fábrica hace lo mismo que el InputReader de antes (salvo las terceras teclas, que no se veían: la L del dash y el clic medio de fijar).</summary>
        static void SameAsOldReader()
        {
            var old = new Dictionary<int, string>
            {
                [K(Key.J)] = "Attack", [K(Key.K)] = "Parry", [K(Key.Space)] = "Dash", [K(Key.LeftShift)] = "Dash", [K(Key.L)] = "Dash",
                [K(Key.Q)] = "Lock", [K(Key.Tab)] = "Lock", [K(Key.F)] = "Finisher,Interact", [K(Key.E)] = "Interact",
                [K(Key.Digit1)] = "Ability1", [K(Key.U)] = "Ability1", [K(Key.Digit2)] = "Ability2", [K(Key.I)] = "Ability2",
                [K(Key.Escape)] = "Cancel,Pause", [K(Key.P)] = "Pause", [K(Key.Enter)] = "Submit",
                [BindCode.MouseLeft] = "Attack", [BindCode.MouseRight] = "Parry", [BindCode.MouseMiddle] = "Lock",
                [BindCode.WheelUp] = "LockPrev", [BindCode.WheelDown] = "LockNext",
                [K(Key.W)] = "MoveUp", [K(Key.UpArrow)] = "MoveUp", [K(Key.S)] = "MoveDown", [K(Key.DownArrow)] = "MoveDown",
                [K(Key.A)] = "MoveLeft", [K(Key.LeftArrow)] = "MoveLeft", [K(Key.D)] = "MoveRight", [K(Key.RightArrow)] = "MoveRight",
                [P(GamepadButton.West)] = "Attack", [P(GamepadButton.RightShoulder)] = "Attack", [P(GamepadButton.LeftShoulder)] = "Parry",
                [P(GamepadButton.East)] = "Cancel,Dash", [P(GamepadButton.South)] = "Dash,Submit", [P(GamepadButton.RightStick)] = "Lock",
                [P(GamepadButton.North)] = "Finisher,Interact", [P(GamepadButton.RightTrigger)] = "Ability1", [P(GamepadButton.LeftTrigger)] = "Ability2",
                [P(GamepadButton.Start)] = "Pause", [BindCode.RStickRight] = "LockNext", [BindCode.RStickLeft] = "LockPrev",
            };
            var t = New(Acts);
            var now = new Dictionary<int, SortedSet<string>>();
            for (int r = 0; r < t.RowCount; r++)
                for (int d = 0; d < 2; d++)
                    for (int s = 0; s < 2; s++)
                    {
                        int c = t.Get(r, d, s);
                        if (c == 0 || BindCode.IsDisplayOnly(c)) continue;
                        if (!now.TryGetValue(c, out var set)) now[c] = set = new SortedSet<string>();
                        set.Add(t.Row(r).id);
                    }
            var diffs = new List<string>();
            foreach (var kv in old)
            {
                string got = now.TryGetValue(kv.Key, out var set) ? string.Join(",", set) : "(nada)";
                if (got != kv.Value) diffs.Add(BindingCatalog.CodeId(kv.Key) + ": antes " + kv.Value + ", ahora " + got);
            }
            foreach (var kv in now) if (!old.ContainsKey(kv.Key)) diffs.Add(BindingCatalog.CodeId(kv.Key) + ": nueva para " + string.Join(",", kv.Value));
            Console.WriteLine("Diferencias con el InputReader de antes:\n  " + string.Join("\n  ", diffs));
            Check(diffs.Count == 2 && diffs.Any(x => x.StartsWith("Key.L:")) && diffs.Any(x => x.StartsWith("Mouse.Middle:")), "solo cambian L y el clic medio");
            // las que mostraba la tarjeta de la pausa (Glyph y GlyphAlt de antes) siguen siendo la principal y la alternativa
            int dash = R(t, "Dash"), lk = R(t, "Lock");
            Check(t.Get(dash, Kb, 0) == K(Key.Space) && t.Get(dash, Kb, 1) == K(Key.LeftShift) && t.Get(lk, Kb, 0) == K(Key.Q) && t.Get(lk, Kb, 1) == K(Key.Tab), "dash Espacio / Shift, fijar Q / Tab");
        }

        static void Swaps()
        {
            var t = New(Acts);
            int atk = R(t, "Attack"), par = R(t, "Parry"), fin = R(t, "Finisher"), inter = R(t, "Interact"), dash = R(t, "Dash");
            // J (alternativa de Atacar) a la alternativa de Parry: se intercambian (las dos son teclas)
            var res = t.Assign(par, Kb, 1, K(Key.J));
            Check(res.outcome == BindOutcome.Swapped && res.other == atk && res.otherCode == K(Key.K), "J a Parry intercambia con K");
            Check(t.Get(par, Kb, 1) == K(Key.J) && t.Get(atk, Kb, 1) == K(Key.K), "J/K quedaron cambiados");
            Check(t.FindProblem() == null, "sin choques tras el intercambio");
            // J a la principal de Parry (el clic derecho): Atacar no recibe un botón del mouse a cambio de una tecla,
            // le queda el clic izquierdo
            t.Reset(-1);
            res = t.Assign(par, Kb, 0, K(Key.J));
            Check(res.outcome == BindOutcome.Taken && res.other == atk && res.otherCode == BindCode.MouseLeft && t.Get(atk, Kb, 1) == 0, "J a Parry: Atacar se queda con el clic izquierdo");
            // W a Atacar: Mover arriba no camina con el clic, se queda con la flecha
            t.Reset(-1);
            int up0 = R(t, "MoveUp");
            res = t.Assign(atk, Kb, 0, K(Key.W));
            Check(res.outcome == BindOutcome.Taken && t.Get(up0, Kb, 0) == 0 && t.Get(up0, Kb, 1) == K(Key.UpArrow), "W a Atacar: arriba se queda con la flecha");
            // el clic derecho a Mover arriba: Parry no recibe la flecha, se queda con K
            t.Reset(-1);
            res = t.Assign(up0, Kb, 1, BindCode.MouseRight);
            Check(res.outcome == BindOutcome.Taken && res.other == par && t.Get(par, Kb, 0) == 0 && t.Get(par, Kb, 1) == K(Key.K), "clic derecho para moverse: Parry se queda con K");
            // si es su única tecla sí recibe la otra clase (nunca se queda sin nada): Ejecutar con F, a Atacar
            t.Reset(-1);
            res = t.Assign(atk, Kb, 0, K(Key.F));
            Check(res.outcome == BindOutcome.Swapped && t.Get(fin, Kb, 0) == BindCode.MouseLeft && t.Get(inter, Kb, 1) == 0, "F al clic de Atacar: Ejecutar recibe el clic, Interactuar se queda con E");
            // el aviso lee lo de cada fila: antes decía "Ejecutar e Interactuar pasan a Clic izq." (solo miraba la primera)
            int fi = System.Array.IndexOf(res.others, fin), ii = System.Array.IndexOf(res.others, inter);
            Check(res.otherGot != null && fi >= 0 && ii >= 0 && res.otherGot[fi] && res.otherCodes[fi] == BindCode.MouseLeft
                  && !res.otherGot[ii] && res.otherCodes[ii] == K(Key.E), "F al clic de Atacar: lo que le quedó a cada una (clic y E)");
            Check(t.FindProblem() == null, "sin choques");
            // F (Ejecutar e Interactuar la comparten a propósito) a Atacar: las dos reciben lo que tenía Atacar
            t.Reset(-1);
            res = t.Assign(atk, Kb, 1, K(Key.F));
            Check(res.outcome == BindOutcome.Swapped && res.others.Length == 2, "F a Atacar toca a Ejecutar e Interactuar");
            Check(t.Get(fin, Kb, 0) == K(Key.J) && t.Get(inter, Kb, 1) == K(Key.J), "Ejecutar e Interactuar pasan a J");
            Check(t.FindProblem() == null, "F a Atacar sin choques");
            // E a Ejecutar: comparten contexto pero pueden compartir tecla, así que no se toca Interactuar
            t.Reset(-1);
            res = t.Assign(fin, Kb, 1, K(Key.E));
            Check(res.outcome == BindOutcome.Assigned && t.Get(inter, Kb, 0) == K(Key.E), "E a Ejecutar convive con Interactuar");
            // la principal de Atacar a su alternativa: se cambian principal y alternativa
            t.Reset(-1);
            res = t.Assign(atk, Kb, 1, BindCode.MouseLeft);
            Check(res.outcome == BindOutcome.OwnSwap && t.Get(atk, Kb, 0) == K(Key.J) && t.Get(atk, Kb, 1) == BindCode.MouseLeft, "intercambio propio");
            // la misma tecla en la otra casilla vacía de la acción: no cambia nada
            res = t.Assign(fin, Kb, 1, K(Key.F));
            Check(res.outcome == BindOutcome.Same && t.Get(fin, Kb, 1) == 0, "F en la alternativa vacía de Ejecutar no la mueve");
            // Enter (fija de Confirmar, que es de menú) para Atacar: no chocan
            t.Reset(-1);
            res = t.Assign(atk, Kb, 1, K(Key.Enter));
            Check(res.outcome == BindOutcome.Assigned, "Enter sirve para atacar (los menús usan su Enter igual)");
            // mando: A (fija de Confirmar, alternativa del dash) a Parry: el dash recibe LB
            res = t.Assign(par, Pd, 0, P(GamepadButton.South));
            Check(res.outcome == BindOutcome.Swapped && res.other == dash && t.Get(dash, Pd, 1) == P(GamepadButton.LeftShoulder), "A a Parry: el dash pasa a LB");
            Check(t.Get(R(t, "Submit"), Pd, 0) == P(GamepadButton.South), "A sigue confirmando");
            // a una casilla vacía con una tecla de otra que tiene dos: se la saca y le queda la otra
            t.Reset(-1);
            res = t.Assign(fin, Kb, 1, K(Key.LeftShift));
            Check(res.outcome == BindOutcome.Taken && res.other == dash && res.otherCode == K(Key.Space) && t.Get(dash, Kb, 1) == 0, "Shift a Ejecutar: al dash le queda Espacio");
            // la rueda que se da a cambio no le sirve al movimiento: el movimiento solo pierde la tecla si tiene otra
            t.Reset(-1);
            int up = R(t, "MoveUp"), next = R(t, "LockNext");
            t.Assign(next, Kb, 1, K(Key.R));
            res = t.Assign(next, Kb, 0, K(Key.W));   // la casilla de la rueda: W era de Mover arriba
            Check(res.outcome == BindOutcome.Taken && t.Get(up, Kb, 0) == 0 && t.Get(up, Kb, 1) == K(Key.UpArrow), "W a Siguiente objetivo: arriba se queda con la flecha");
            Check(t.FindProblem() == null, "sin choques");
            // lo mismo con fijar: Q a la casilla de la rueda de Siguiente objetivo deja a fijar con Tab
            t.Reset(-1);
            int lock_ = R(t, "Lock");
            res = t.Assign(next, Kb, 0, K(Key.Q));
            Check(res.outcome == BindOutcome.Taken && res.other == lock_ && t.Get(lock_, Kb, 0) == 0 && t.Get(lock_, Kb, 1) == K(Key.Tab), "Q a Siguiente objetivo: fijar se queda con Tab");
            Check(t.FindProblem() == null, "sin choques");
        }

        static void Refusals()
        {
            var t = New(Acts);
            int atk = R(t, "Attack"), pause = R(t, "Pause"), up = R(t, "MoveUp"), fin = R(t, "Finisher"), next = R(t, "LockNext"), par = R(t, "Parry");
            var res = t.Assign(atk, Kb, 0, K(Key.Escape));
            Check(!res.Ok && res.refusal == BindRefusal.Reserved && res.reason == "pausa", "Esc reservada");
            res = t.Assign(atk, Kb, 0, K(Key.LeftMeta));
            Check(!res.Ok && res.reason == "sistema", "Win reservada");
            res = t.Assign(atk, Pd, 0, P(GamepadButton.Start));
            Check(!res.Ok && res.reason == "pausa", "Start reservado");
            res = t.Assign(atk, Pd, 0, P(GamepadButton.DpadUp));
            Check(!res.Ok && res.reason == "cruceta", "cruceta reservada");
            res = t.Assign(pause, Kb, 0, K(Key.P));
            Check(!res.Ok && res.refusal == BindRefusal.Locked, "la Esc de Pausa no se cambia");
            res = t.Assign(pause, Kb, 1, K(Key.Enter));
            Check(!res.Ok && res.refusal == BindRefusal.LockedElsewhere && res.other == R(t, "Submit"), "Enter no pausa (confirma en los menús)");
            res = t.Assign(R(t, "Submit"), Kb, 1, K(Key.Space));
            Check(!res.Ok && res.refusal == BindRefusal.Locked, "Confirmar es fija");
            res = t.Assign(up, Kb, 0, BindCode.WheelUp);
            Check(!res.Ok && res.refusal == BindRefusal.NeedsHold, "la rueda no mueve");
            // fijar se suelta manteniéndolo: ni la rueda ni un toque del stick
            int lk = R(t, "Lock");
            Check(t.Row(lk).hold && t.Row(up).hold && !t.Row(atk).hold, "fijar y moverse se mantienen");
            res = t.Assign(lk, Kb, 1, BindCode.WheelUp);
            Check(!res.Ok && res.refusal == BindRefusal.NeedsHold, "la rueda no fija");
            res = t.Assign(lk, Pd, 1, BindCode.RStickUp);
            Check(!res.Ok && res.refusal == BindRefusal.NeedsHold, "un toque del stick no fija");
            res = t.Assign(fin, Kb, 1, BindCode.WheelDown);
            Check(!res.Ok && res.refusal == BindRefusal.OnlyKey && res.other == next, "la rueda es la única de Siguiente objetivo");
            res = t.Assign(atk, Kb, 0, P(GamepadButton.West));
            Check(!res.Ok && res.refusal == BindRefusal.WrongDevice, "un botón del mando no va en el teclado");
            res = t.Assign(R(t, "MovePad"), Pd, 0, P(GamepadButton.West));
            Check(!res.Ok && res.refusal == BindRefusal.Locked, "el movimiento del mando es fijo");
            res = t.Assign(up, Pd, 0, P(GamepadButton.West));
            Check(!res.Ok && res.refusal == BindRefusal.Locked, "las direcciones del teclado no están en el mando");
            res = t.Assign(par, Pd, 1, BindCode.RStickRight);
            Check(!res.Ok && res.refusal == BindRefusal.OnlyKey, "el toque derecho es el único de Siguiente objetivo");
            Check(t.IsDefault(Kb) && t.IsDefault(Pd), "lo rechazado no cambió nada");
        }

        /// <summary>La pausa y el mapa se leen con un menú abierto: nada de lo que usan los menús, ni directo ni por intercambio.</summary>
        static void MenuInputs()
        {
            var t = New(ActsMap);
            int atk = R(t, "Attack"), pause = R(t, "Pause"), map = R(t, "Map"), down = R(t, "MoveDown"), up = R(t, "MoveUp"), inter = R(t, "Interact");
            foreach (int c in new[] { BindCode.MouseLeft, BindCode.MouseRight, BindCode.MouseMiddle, BindCode.WheelDown, K(Key.W), K(Key.DownArrow), K(Key.Backspace), K(Key.Delete), K(Key.NumpadPlus) })
            {
                var res = t.Assign(pause, Kb, 1, c);
                Check(!res.Ok && res.refusal == BindRefusal.Reserved && res.reason == "menu", "Pausa no toma " + BindingCatalog.CodeId(c));
                res = t.Assign(map, Kb, 0, c);
                Check(!res.Ok && res.refusal == BindRefusal.Reserved && res.reason == "menu", "Mapa no toma " + BindingCatalog.CodeId(c));
            }
            foreach (int c in new[] { P(GamepadButton.West), P(GamepadButton.LeftTrigger), P(GamepadButton.RightTrigger), BindCode.RStickDown, BindCode.RStickRight })
            {
                Check(t.Assign(pause, Pd, 1, c).reason == "menu", "Pausa no toma " + BindingCatalog.CodeId(c));
                Check(t.Assign(map, Pd, 0, c).reason == "menu", "Mapa no toma " + BindingCatalog.CodeId(c));
            }
            // Enter / A / B confirman y vuelven en los menús: el mapa no los puede tener (antes era solo de juego)
            var r2 = t.Assign(map, Kb, 0, K(Key.Enter));
            Check(!r2.Ok && r2.refusal == BindRefusal.LockedElsewhere && r2.other == R(t, "Submit"), "Enter no abre el mapa");
            Check(t.Assign(map, Pd, 0, P(GamepadButton.South)).refusal == BindRefusal.LockedElsewhere, "A no abre el mapa");
            Check(t.Assign(map, Pd, 0, P(GamepadButton.East)).refusal == BindRefusal.LockedElsewhere, "B no abre el mapa");
            Check(t.IsDefault(Kb) && t.IsDefault(Pd), "lo rechazado no cambió nada");
            // por intercambio tampoco: P a Atacar le sacaría a la pausa la P a cambio del clic; se queda solo con Esc
            var res2 = t.Assign(atk, Kb, 0, K(Key.P));
            Check(res2.outcome == BindOutcome.Taken && res2.other == pause && t.Get(pause, Kb, 1) == 0 && t.Get(pause, Kb, 0) == K(Key.Escape), "P a Atacar: la pausa no recibe el clic");
            t.Reset(-1);
            res2 = t.Assign(down, Kb, 0, K(Key.P));
            Check(res2.outcome == BindOutcome.Taken && t.Get(pause, Kb, 1) == 0, "P a Mover abajo: la pausa no recibe la S");
            t.Reset(-1);
            res2 = t.Assign(up, Kb, 1, K(Key.M));
            Check(!res2.Ok && res2.refusal == BindRefusal.OnlyKey && res2.other == map, "M a la flecha de arriba: el mapa no puede recibir la flecha y la M es lo único que tiene");
            Check(t.FindProblem() == null, "sin choques: " + t.FindProblem());
            // el mando: Vista a Atacar le daría al mapa la X (quita en la página de controles): se rechaza, es su única
            t.Reset(-1);
            res2 = t.Assign(atk, Pd, 0, P(GamepadButton.Select));
            Check(!res2.Ok && res2.refusal == BindRefusal.OnlyKey && res2.other == map, "Vista a Atacar: es lo único del mapa");
            // pero el mapa sí recibe un botón que le sirve: Vista a la alternativa (RB) de Atacar
            res2 = t.Assign(atk, Pd, 1, P(GamepadButton.Select));
            Check(res2.outcome == BindOutcome.Swapped && t.Get(map, Pd, 0) == P(GamepadButton.RightShoulder), "Vista a Atacar: el mapa pasa a RB");
            Check(t.FindProblem() == null, "sin choques: " + t.FindProblem());
            // lo que no es de menú puede usar todo eso: Interactuar con el clic, Atacar con Enter
            t.Reset(-1);
            Check(t.Assign(inter, Kb, 1, BindCode.MouseMiddle).Ok && t.Assign(atk, Kb, 1, K(Key.Enter)).Ok, "las de juego toman el clic y Enter");
            // y al cargar (preferencias editadas a mano) también se ignoran
            var problems = t.Load("1|Pause.k1=Mouse.Left|Map.k0=Key.UpArrow|Map.p0=Pad.West|Pause.p1=Pad.RStickDown", BindingCatalog.ParseCode);
            Check(problems.Count == 4 && t.IsDefault(Kb) && t.IsDefault(Pd), "lo de menú cargado a mano se ignora: " + string.Join("; ", problems));
        }

        /// <summary>
        /// Fijar (centra en Kaito) y moverse (corre el cursor) también se leen con el mapa abierto: nada de lo que el mapa
        /// usa por su cuenta (el clic arrastra, la rueda, + y - y los gatillos acercan), ni directo ni por intercambio.
        /// </summary>
        static void MapInputs()
        {
            var t = New(ActsMap);
            int lk = R(t, "Lock"), up = R(t, "MoveUp"), atk = R(t, "Attack"), a1 = R(t, "Ability1"), par = R(t, "Parry");
            foreach (int c in new[] { BindCode.MouseLeft, K(Key.Equals), K(Key.Minus), K(Key.NumpadPlus), K(Key.NumpadMinus) })
            {
                var res = t.Assign(lk, Kb, 0, c);
                Check(!res.Ok && res.refusal == BindRefusal.Reserved && res.reason == "mapa", "Fijar no toma " + BindingCatalog.CodeId(c));
                res = t.Assign(up, Kb, 1, c);
                Check(!res.Ok && res.refusal == BindRefusal.Reserved && res.reason == "mapa", "Mover arriba no toma " + BindingCatalog.CodeId(c));
            }
            foreach (int c in new[] { P(GamepadButton.LeftTrigger), P(GamepadButton.RightTrigger) })
            {
                var res = t.Assign(lk, Pd, 1, c);
                Check(!res.Ok && res.reason == "mapa", "Fijar no toma " + BindingCatalog.CodeId(c));
            }
            // la B cierra el mapa (Volver): fijar no la puede tener
            var r2 = t.Assign(lk, Pd, 0, P(GamepadButton.East));
            Check(!r2.Ok && r2.refusal == BindRefusal.LockedElsewhere && r2.other == R(t, "Cancel"), "B no fija (cerraría el mapa)");
            Check(t.IsDefault(Kb) && t.IsDefault(Pd), "lo rechazado no cambió nada");
            // lo que el mapa no usa sí: el clic medio y el clic derecho para fijar, RB en el mando
            Check(t.Assign(lk, Kb, 1, BindCode.MouseMiddle).outcome == BindOutcome.Assigned, "fijar con el clic medio");
            t.Reset(-1);
            var r3 = t.Assign(lk, Kb, 1, BindCode.MouseRight);
            Check(r3.outcome == BindOutcome.Taken && r3.other == par && t.Get(par, Kb, 1) == K(Key.K), "fijar con el clic derecho: Parry se queda con K");
            Check(t.Assign(lk, Pd, 1, P(GamepadButton.RightShoulder)).Ok, "fijar con RB");
            // por intercambio tampoco: Q a Atacar le daría a fijar el clic izquierdo; se queda con su otra
            t.Reset(-1);
            var r4 = t.Assign(atk, Kb, 0, K(Key.Q));
            Check(r4.outcome == BindOutcome.Taken && t.Get(lk, Kb, 0) == 0 && t.Get(lk, Kb, 1) == K(Key.Tab), "Q a Atacar: fijar no recibe el clic");
            // RS a la habilidad del gatillo: fijar no recibe RT, y con RS como único botón se rechaza
            t.Reset(-1);
            var r5 = t.Assign(a1, Pd, 0, P(GamepadButton.RightStick));
            Check(!r5.Ok && r5.refusal == BindRefusal.OnlyKey && r5.other == lk, "RS a Corte del Viento: fijar no puede quedarse con RT");
            // las que no se leen con el mapa siguen tomando el clic
            Check(t.Assign(par, Kb, 0, BindCode.MouseLeft).outcome == BindOutcome.Swapped, "Parry toma el clic izquierdo (no se lee con el mapa)");
            Check(t.FindProblem() == null, "sin choques: " + t.FindProblem());
            // y al cargar (preferencias editadas a mano) también se ignoran
            var problems = New(ActsMap).Load("1|Lock.k1=Mouse.Left|MoveUp.k1=Key.NumpadPlus|Lock.p1=Pad.LeftTrigger", BindingCatalog.ParseCode);
            Check(problems.Count == 3, "lo del mapa cargado a mano se ignora: " + string.Join("; ", problems));
        }

        /// <summary>El panel táctil (PlayStation) abre el mapa: fijo, solo para mostrar, y no cuenta como un botón que sirve en todo mando.</summary>
        static void Touchpad()
        {
            var t = New(ActsMap);
            int map = R(t, "Map"), atk = R(t, "Attack");
            Check(t.Get(map, Pd, 1) == BindCode.PadTouchpad && t.Locked(map, Pd, 1), "el táctil es la alternativa fija del mapa");
            Check(t.Usable(map, Pd) == 1 && t.Count(map, Pd) == 2, "el táctil no cuenta como usable");
            Check(t.Clear(map, Pd, 0).refusal == BindRefusal.LastKey, "no se le puede quitar Vista al mapa (en un Xbox no tendría nada)");
            Check(t.Assign(atk, Pd, 1, BindCode.PadTouchpad).refusal == BindRefusal.WrongDevice, "el táctil no se asigna");
            Check(t.Assign(map, Pd, 1, P(GamepadButton.North)).refusal == BindRefusal.Locked, "la casilla del táctil es fija");
            // Vista a la alternativa (RB) de Atacar: el mapa pasa a RB y conserva el táctil
            var res = t.Assign(atk, Pd, 1, P(GamepadButton.Select));
            Check(res.outcome == BindOutcome.Swapped && t.Get(map, Pd, 0) == P(GamepadButton.RightShoulder) && t.Get(map, Pd, 1) == BindCode.PadTouchpad, "Vista a Atacar: el mapa pasa a RB");
            Check(t.Save(BindingCatalog.CodeId) == "1|Attack.p1=Pad.Select|Map.p0=Pad.RightShoulder", "el táctil no se guarda: " + t.Save(BindingCatalog.CodeId));
            // lo guardado le saca Vista al mapa (se la dio a la pausa antes de que existiera): recibe LS aunque tenga el táctil
            var u = New(ActsMap);
            u.Load("1|Pause.p1=Pad.Select", BindingCatalog.ParseCode);
            Check(u.Get(map, Pd, 0) == P(GamepadButton.LeftStick) && u.Rescued.Count == 1, "sin Vista, el mapa recibe LS");
            var bad = New(ActsMap).Load("1|Map.p1=Pad.North", BindingCatalog.ParseCode);
            Check(bad.Count == 1, "la casilla del táctil no se carga");
        }

        static void ClearRules()
        {
            var t = New(Acts);
            int atk = R(t, "Attack"), fin = R(t, "Finisher"), pause = R(t, "Pause");
            Check(t.Clear(fin, Kb, 0).refusal == BindRefusal.LastKey, "Ejecutar necesita una tecla");
            Check(t.Clear(atk, Kb, 1).outcome == BindOutcome.Cleared && t.Get(atk, Kb, 1) == 0, "se quita J");
            Check(t.Clear(atk, Kb, 0).refusal == BindRefusal.LastKey, "a Atacar le queda el clic");
            Check(t.Clear(pause, Kb, 1).outcome == BindOutcome.Cleared, "P se quita (queda Esc)");
            Check(t.Clear(pause, Kb, 0).refusal == BindRefusal.Locked, "Esc no se quita");
            Check(t.Clear(atk, Kb, 1).outcome == BindOutcome.Same, "quitar lo vacío no hace nada");
        }

        static void Persistence()
        {
            var t = New(Acts);
            Check(t.Save(BindingCatalog.CodeId) == "1", "de fábrica se guarda solo la versión");
            t.Assign(R(t, "Parry"), Kb, 0, K(Key.J));
            t.Assign(R(t, "Dash"), Kb, 1, K(Key.L));
            t.Assign(R(t, "Parry"), Pd, 1, P(GamepadButton.LeftTrigger));
            t.Clear(R(t, "Attack"), Pd, 1);
            t.Assign(R(t, "MoveUp"), Kb, 0, K(Key.Z));
            string saved = t.Save(BindingCatalog.CodeId);
            Console.WriteLine("guardado: " + saved);
            var u = New(Acts);
            var problems = u.Load(saved, BindingCatalog.ParseCode);
            Check(problems.Count == 0, "carga sin problemas: " + string.Join("; ", problems));
            Check(SameCodes(t, u), "guardar y cargar da lo mismo");
            // basura, acciones que no existen, teclas desconocidas, casillas fijas: se ignoran
            problems = u.Load("1|Nada.k0=Key.J|Attack.k0=Key.Inventada|Pause.k0=Key.P|Attack.x0=Key.J|Attack.k7=Key.J|Attack.k0|=|Attack.k1=Mouse.Left", BindingCatalog.ParseCode);
            // siete entradas malas y la última, válida, repite la principal de fábrica de Atacar: gana la del jugador
            Check(problems.Count == 8, "ocho problemas: " + problems.Count + " " + string.Join("; ", problems));
            Check(u.Get(R(u, "Attack"), Kb, 1) == BindCode.MouseLeft && u.Get(R(u, "Attack"), Kb, 0) == 0, "Attack.k1=Mouse.Left: queda una sola, la del jugador");
            Check(u.FindProblem() == null, "lo cargado no choca: " + u.FindProblem());
            // otra versión del formato: de fábrica
            problems = u.Load("9|Attack.k1=Key.L", BindingCatalog.ParseCode);
            Check(problems.Count == 1 && u.IsDefault(Kb), "otra versión: de fábrica");
            // datos rotos que dejan a una acción sin nada: se le devuelven las de fábrica
            problems = u.Load("1|Attack.k0=-|Attack.k1=-", BindingCatalog.ParseCode);
            Check(u.Count(R(u, "Attack"), Kb) == 2, "Atacar sin nada recupera las de fábrica");
            // reservadas y rueda para moverse (alguien editó las preferencias): se ignoran
            problems = u.Load("1|Attack.k0=Key.Escape|MoveUp.k0=Mouse.WheelUp|Attack.p0=Pad.DpadUp|Lock.k1=Mouse.WheelDown|Lock.p1=Pad.RStickUp", BindingCatalog.ParseCode);
            Check(problems.Count == 5 && u.IsDefault(Kb) && u.IsDefault(Pd), "reservadas e impulsos para fijar ignorados");
        }

        /// <summary>El mapa llega después (frente ui-map): con sus teclas de fábrica, salvo que el jugador ya las use.</summary>
        static void NewActionMerge()
        {
            var t = New(Acts);
            var u = New(ActsMap);
            Check(u.Load(t.Save(BindingCatalog.CodeId), BindingCatalog.ParseCode).Count == 0 && u.Get(R(u, "Map"), Kb, 0) == K(Key.M) && u.Get(R(u, "Map"), Pd, 0) == P(GamepadButton.Select), "Mapa con M y Vista");
            t.Assign(R(t, "Attack"), Kb, 1, K(Key.M));
            t.Assign(R(t, "Pause"), Pd, 1, P(GamepadButton.Select));
            var problems = u.Load(t.Save(BindingCatalog.CodeId), BindingCatalog.ParseCode);
            Console.WriteLine("con el mapa nuevo: " + string.Join("; ", problems));
            Check(u.Get(R(u, "Attack"), Kb, 1) == K(Key.M), "Atacar conserva la M del jugador");
            Check(u.Get(R(u, "Pause"), Pd, 1) == P(GamepadButton.Select), "Pausa conserva Vista");
            // sin su M ni su Vista el mapa recibe la primera libre de cada dispositivo: nunca queda sin forma de abrirse
            int map = R(u, "Map");
            Check(u.Get(map, Kb, 0) == K(Key.N) && u.Get(map, Pd, 0) == P(GamepadButton.LeftStick), "el mapa recibe N y LS");
            Check(u.Rescued.Count == 2 && u.Rescued.All(x => x.row == map) && u.Rescued.Any(x => x.dev == Kb && x.lost == K(Key.M) && x.holder == R(u, "Attack"))
                  && u.Rescued.Any(x => x.dev == Pd && x.lost == P(GamepadButton.Select) && x.holder == R(u, "Pause")), "y queda anotado para avisar");
            Check(u.FindProblem() == null, "sin choques con el mapa");
            // guardado así, la próxima carga ya no tiene nada que rescatar y da lo mismo
            var again = New(ActsMap);
            Check(again.Load(u.Save(BindingCatalog.CodeId), BindingCatalog.ParseCode).Count == 0 && again.Rescued.Count == 0 && SameCodes(u, again), "lo rescatado se guarda");
            // la N también estaba tomada: el mapa recibe la siguiente libre (B)
            var v = New(ActsMap);
            v.Load("1|Attack.k1=Key.M|Parry.k1=Key.N", BindingCatalog.ParseCode);
            Check(v.Get(R(v, "Map"), Kb, 0) == K(Key.B) && v.FindProblem() == null, "con la N tomada, B");
            // y al revés: una acción que ya no existe en el enum se ignora
            var back = New(Acts);
            problems = back.Load(u.Save(BindingCatalog.CodeId), BindingCatalog.ParseCode);
            Check(back.Get(R(back, "Attack"), Kb, 1) == K(Key.M), "sin el mapa también carga");
        }

        static bool SameCodes(BindingTable a, BindingTable b)
        {
            for (int r = 0; r < a.RowCount; r++)
                for (int d = 0; d < 2; d++)
                    for (int s = 0; s < 2; s++)
                        if (a.Get(r, d, s) != b.Get(r, d, s)) return false;
            return true;
        }

        /// <summary>
        /// Miles de cambios al azar (lo que puede hacer alguien en la página de controles): nunca dos acciones que
        /// chocan con la misma tecla, ninguna sin teclas, las fijas siempre en su lugar y guardar/cargar idéntico.
        /// </summary>
        static void Fuzz(int steps, int seed)
        {
            var rnd = new Random(seed);
            var t = New(ActsMap);
            var pool = new List<int>();
            foreach (Key k in Enum.GetValues(typeof(Key))) if (BindingCatalog.IsBindableKey(k)) pool.Add((int)k);
            pool.AddRange(new[] { BindCode.MouseLeft, BindCode.MouseRight, BindCode.MouseMiddle, BindCode.MouseForward, BindCode.MouseBack, BindCode.WheelUp, BindCode.WheelDown });
            foreach (GamepadButton b in Enum.GetValues(typeof(GamepadButton))) pool.Add(BindCode.Pad((int)b));
            pool.AddRange(new[] { BindCode.RStickUp, BindCode.RStickDown, BindCode.RStickLeft, BindCode.RStickRight });
            pool = pool.Distinct().ToList();
            int refused = 0, changed = 0, badAt = -1;
            for (int i = 0; i < steps && badAt < 0; i++)
            {
                int r = rnd.Next(t.RowCount), d = rnd.Next(2), s = rnd.Next(2);
                double op = rnd.NextDouble();
                BindResult res;
                if (op < 0.002) { t.Reset(d); continue; }
                if (op < 0.1) res = t.Clear(r, d, s);
                else
                {
                    // casi siempre del dispositivo correcto (como captura la página), a veces cualquiera
                    int c = pool[rnd.Next(pool.Count)];
                    if (rnd.NextDouble() < 0.97) while (BindCode.DeviceOf(c) != d) c = pool[rnd.Next(pool.Count)];
                    res = t.Assign(r, d, s, c);
                }
                if (res.Ok) changed++; else refused++;
                string p = t.FindProblem();
                if (p != null) { Check(false, $"fuzz {seed} paso {i}: {p}"); badAt = i; }
                for (int q = 0; q < t.RowCount && badAt < 0; q++)
                    for (int dd = 0; dd < 2; dd++)
                    {
                        if (!t.Row(q).shown[dd]) continue;
                        bool hasUsable = false;
                        for (int ss = 0; ss < 2; ss++) { int dc = t.Default(q, dd, ss); hasUsable |= dc != 0 && !BindCode.IsDisplayOnly(dc); }
                        if (hasUsable && t.Usable(q, dd) < 1) { Check(false, $"fuzz {seed} paso {i}: {t.Row(q).id} sin teclas que sirvan"); badAt = i; }
                        for (int ss = 0; ss < 2; ss++)
                        {
                            int c = t.Get(q, dd, ss);
                            if (t.Locked(q, dd, ss) && c != t.Default(q, dd, ss)) { Check(false, $"fuzz {seed} paso {i}: se movió una fija de {t.Row(q).id}"); badAt = i; }
                            if (c != 0 && BindCode.DeviceOf(c) != dd) { Check(false, $"fuzz {seed} paso {i}: {t.Row(q).id} tiene un control del otro dispositivo"); badAt = i; }
                            if (c != 0 && t.Row(q).hold && BindCode.IsImpulse(c)) { Check(false, $"fuzz {seed} paso {i}: {t.Row(q).id} se mantiene con un impulso"); badAt = i; }
                            if (c != 0 && !t.Locked(q, dd, ss) && BindingCatalog.Reserved(c) != null) { Check(false, $"fuzz {seed} paso {i}: {t.Row(q).id} tiene una reservada"); badAt = i; }
                            if (c != 0 && !t.Locked(q, dd, ss) && BindCode.IsDisplayOnly(c)) { Check(false, $"fuzz {seed} paso {i}: {t.Row(q).id} tiene uno que solo se muestra"); badAt = i; }
                        }
                    }
                if (i % 997 == 0)
                {
                    var u = New(ActsMap);
                    var problems = u.Load(t.Save(BindingCatalog.CodeId), BindingCatalog.ParseCode);
                    if (problems.Count > 0 || !SameCodes(t, u)) { Check(false, $"fuzz {seed} paso {i}: guardar/cargar cambió algo {string.Join("; ", problems)}"); badAt = i; }
                }
            }
            checks++;
            Console.WriteLine($"fuzz {seed}: {steps} pasos, {changed} aplicados, {refused} rechazados");
        }
    }
}
