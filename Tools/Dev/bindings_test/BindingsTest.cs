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

        static BindingTable New(string[] acts) => new BindingTable(BindingCatalog.Build(acts), BindingCatalog.Reserved);

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

        /// <summary>Lo de fábrica hace lo mismo que el InputReader de antes (salvo las terceras teclas L y Tab).</summary>
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
            Check(diffs.Count == 2 && diffs.Any(x => x.StartsWith("Key.L:")) && diffs.Any(x => x.StartsWith("Key.Tab:")), "solo cambian L y Tab");
        }

        static void Swaps()
        {
            var t = New(Acts);
            int atk = R(t, "Attack"), par = R(t, "Parry"), fin = R(t, "Finisher"), inter = R(t, "Interact"), dash = R(t, "Dash");
            // J (alternativa de Atacar) a la principal de Parry: se intercambian
            var res = t.Assign(par, Kb, 0, K(Key.J));
            Check(res.outcome == BindOutcome.Swapped && res.other == atk && res.otherCode == BindCode.MouseRight, "J a Parry intercambia");
            Check(t.Get(par, Kb, 0) == K(Key.J) && t.Get(atk, Kb, 1) == BindCode.MouseRight, "J/Clic der. quedaron cambiados");
            Check(t.FindProblem() == null, "sin choques tras el intercambio");
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
            // lo mismo con fijar: Q a la casilla de la rueda de Siguiente objetivo deja a fijar con el clic medio
            t.Reset(-1);
            int lock_ = R(t, "Lock");
            res = t.Assign(next, Kb, 0, K(Key.Q));
            Check(res.outcome == BindOutcome.Taken && res.other == lock_ && t.Get(lock_, Kb, 0) == 0 && t.Get(lock_, Kb, 1) == BindCode.MouseMiddle, "Q a Siguiente objetivo: fijar se queda con el clic medio");
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
            Check(u.Count(R(u, "Map"), Kb) == 0 && u.Count(R(u, "Map"), Pd) == 0, "el mapa queda sin tecla (la página lo muestra) en vez de chocar");
            Check(u.Get(R(u, "Pause"), Pd, 1) == P(GamepadButton.Select), "Pausa conserva Vista");
            Check(u.FindProblem() == null, "sin choques con el mapa");
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
                        if (t.Count(q, dd) < 1) { Check(false, $"fuzz {seed} paso {i}: {t.Row(q).id} sin teclas"); badAt = i; }
                        for (int ss = 0; ss < 2; ss++)
                        {
                            int c = t.Get(q, dd, ss);
                            if (t.Locked(q, dd, ss) && c != t.Default(q, dd, ss)) { Check(false, $"fuzz {seed} paso {i}: se movió una fija de {t.Row(q).id}"); badAt = i; }
                            if (c != 0 && BindCode.DeviceOf(c) != dd) { Check(false, $"fuzz {seed} paso {i}: {t.Row(q).id} tiene un control del otro dispositivo"); badAt = i; }
                            if (c != 0 && t.Row(q).hold && BindCode.IsImpulse(c)) { Check(false, $"fuzz {seed} paso {i}: {t.Row(q).id} se mantiene con un impulso"); badAt = i; }
                            if (c != 0 && !t.Locked(q, dd, ss) && BindingCatalog.Reserved(c) != null) { Check(false, $"fuzz {seed} paso {i}: {t.Row(q).id} tiene una reservada"); badAt = i; }
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
