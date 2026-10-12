using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Nindo
{
    /// <summary>
    /// Opciones › Controles: cada acción de <see cref="Act"/> (las que agreguen otros frentes aparecen solas, por
    /// BindingCatalog) y el movimiento, con su tecla principal y la alternativa como las teclas de papel de siempre.
    /// Elegís una casilla, confirmás y apretás la tecla nueva: si otra acción la usaba se intercambian y un aviso de dos
    /// renglones dice qué pasó (las reglas están en BindingTable). Arriba se elige el dispositivo (teclado y mouse, o
    /// mando); abajo, volver y restablecer. Va en el mismo panel que Opciones: la tarjeta de opciones se cambia por
    /// esta, la columna de tinta queda y la pausa sigue abierta.
    /// Mientras espera una tecla la navegación de los menús se apaga y un velo invisible se come los clics (el clic
    /// también se puede asignar); antes y después se espera a que se suelte todo, así ni el Enter que abrió la espera
    /// queda tomado ni la tecla tomada confirma algo en el menú. Esc y Start cancelan siempre.
    /// </summary>
    public partial class UIManager
    {
        // medidas a 1080p, desde la esquina de arriba a la izquierda de la tarjeta (1060 x 930, la de Opciones). Las teclas
        // van a 44 como en la tarjeta de la pausa y los nombres largos ("Stick der. →") más grandes que en el resto
        // (0.48 del alto: 21 px a 1080p, 14 a 720p), que acá es donde hay que leerlos; la fila crece a 52 para que entren
        const float CtlRowH = 52f, CtlHeadH = 50f, CtlLabelX = 130f, CtlSlot0X = 580f, CtlSlot1X = 790f;
        const float CtlKeyH = 44f, CtlKeyLong = 0.48f;
        // la lista empieza 20 px debajo de "Principal / Alternativa" y se esfuma en los bordes; se detiene siempre con el
        // borde de arriba sobre el comienzo de una fila o de un grupo (CtlStopPad más abajo, fuera de lo esfumado: nunca
        // queda una fila cortada al medio bajo los títulos de las columnas)
        const float CtlViewX = 60f, CtlViewTop = -204f, CtlViewW = 940f, CtlViewH = 546f, CtlSoft = 24f, CtlStopPad = 12f;
        // la rueda corre la lista una fila y media por muesca, con la misma suavidad que el teclado y el mando
        const float CtlWheelStops = 1.5f;
        static readonly Color CtlDim = new Color(0.62f, 0.59f, 0.53f, 1f);       // como los ítems no elegidos
        static readonly Color CtlWarn = new Color(1f, 0.46f, 0.4f, 1f);          // el carmesí claro del clan: se lee sobre la tinta

        sealed class ControlsRow
        {
            public int row;
            public float y;
            public RectTransform rt;
            public TextMeshProUGUI label, unbound;
            public Image band, cursor;
            public readonly UIControlsSlot[] slots = new UIControlsSlot[BindingTable.Slots];
            public float k;
        }

        enum CaptureState { Idle, Arming, Listening, Releasing }

        Button controlsEntry, controlsBack, controlsReset;
        RectTransform controlsCard, controlsViewport, controlsTrack, controlsThumb, controlsInfoRoot;
        Image controlsCardImg, controlsBlocker;
        CanvasGroup controlsInfoGroup;
        TextMeshProUGUI controlsInfo, controlsInfoSub, controlsResetLabel;
        NindoSelector controlsDevice;
        readonly RectTransform[] controlsContent = new RectTransform[BindingTable.Devices];
        readonly List<ControlsRow>[] controlsRows = { new List<ControlsRow>(), new List<ControlsRow>() };
        /// <summary>Dónde puede detenerse la lista (posición del contenido, de menor a mayor): ver CtlStopPad.</summary>
        readonly List<float>[] controlsStops = { new List<float>(), new List<float>() };
        int controlsDev, controlsShownVersion = -1, controlsShownFamily = -1;
        bool controlsOpen, controlsHintPad, controlsHintShown;
        float controlsOpenT, controlsScrollTarget = -1f, controlsInfoT, controlsInfoLife, controlsResetArmed, controlsWheel;
        GameObject controlsLastSel;
        CaptureState capture;
        UIControlsSlot captureSlot, captureReturn;
        bool captureByPointer;
        float captureT;

        // ================================================================== armado
        /// <summary>Renglón "Controles" de Opciones, como las demás filas: el nombre a la izquierda y "Teclado y mando ›".</summary>
        Button ControlsEntry(Transform parent, Vector2 size)
        {
            // armada como las filas de opciones (sin el halo de los botones sueltos)
            var row = UIFactory.Rect("Controls", parent, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero, size);
            var hit = row.gameObject.AddComponent<Image>();
            hit.color = new Color(0f, 0f, 0f, 0f);
            var b = row.gameObject.AddComponent<Button>();
            b.transition = Selectable.Transition.None;
            b.targetGraphic = hit;
            UIFactory.AttachFocus(row, "Controles", 30f, TextAlignmentOptions.Left, size, false);
            b.onClick.AddListener(() => Game.Audio?.Play("ui_select", null, 0.6f));
            b.onClick.AddListener(OpenControls);
            // donde las otras filas tienen "‹ valor ›": a qué se entra, con el kunai que apunta adentro
            float cx = size.x * 0.5f + 10f + size.x * 0.21f;
            var v = UIFactory.NoWrap(UIFactory.Text("Value", row, "Teclado y mando", 28, UIFactory.Paper, new Vector2(0f, 0.5f), new Vector2(cx, 0f), new Vector2(size.x * 0.32f, size.y), TextAlignmentOptions.Center, true));
            v.rectTransform.pivot = new Vector2(0.5f, 0.5f);
            UIFactory.Centered("Arrow", row, UIFactory.Gold, new Vector2(0f, 0.5f), new Vector2(cx + size.x * 0.21f - 14f, 0f), new Vector2(46f, 16f), UISprites.Kunai);
            return b;
        }

        void BuildControls()
        {
            var panel = optionsPanel.transform;
            var card = UIFactory.Sliced("ControlsCard", panel, UISprites.InkCard, Color.white, 256f);
            card.pixelsPerUnitMultiplier = 1f;
            controlsCard = card.rectTransform;
            controlsCardImg = card;
            Place(controlsCard, new Vector2(0.5f, 0.5f), new Vector2(330f, -10f), optionsCard.sizeDelta);
            controlsCard.pivot = new Vector2(0.5f, 0.5f);
            UIFactory.Legible(UIFactory.Text("Title", controlsCard, "Controles", 36, UIFactory.Gold, new Vector2(0f, 1f), new Vector2(100f, -46f), new Vector2(400, 50), TextAlignmentOptions.TopLeft, true));

            controlsDevice = UIFactory.OptionSelector("Device", controlsCard, "Dispositivo", new[] { "Teclado y mouse", "Mando" }, 0, ShowControlsDevice, new Vector2(860, 62));
            var drt = (RectTransform)controlsDevice.transform;
            drt.anchorMin = drt.anchorMax = new Vector2(0.5f, 1f); drt.pivot = new Vector2(0.5f, 0.5f);
            drt.anchoredPosition = new Vector2(20f, -118f);

            for (int s = 0; s < BindingTable.Slots; s++)
            {
                var h = UIFactory.Text("Column", controlsCard, s == 0 ? "Principal" : "Alternativa", 21, CtlDim, new Vector2(0f, 1f), new Vector2(CtlViewX + (s == 0 ? CtlSlot0X : CtlSlot1X), -170f), new Vector2(200, 28), TextAlignmentOptions.Center);
                h.rectTransform.pivot = new Vector2(0.5f, 0.5f);
            }

            // la lista se corre: con el teclado son 19 filas en cuatro grupos y no entran. Sin ScrollRect: la corre
            // UpdateControls de parada en parada (teclado, mando y rueda por igual, suavizado)
            controlsViewport = UIFactory.Rect("View", controlsCard, new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(CtlViewX, CtlViewTop), new Vector2(CtlViewW, CtlViewH));
            var hit = controlsViewport.gameObject.AddComponent<Image>();
            hit.color = new Color(0f, 0f, 0f, 0f);   // la rueda corre la lista también entre las filas
            var mask = controlsViewport.gameObject.AddComponent<RectMask2D>();
            mask.softness = new Vector2Int(0, (int)CtlSoft);    // las filas se esfuman en los bordes, como tinta
            // muescas de la rueda (hacia arriba son positivas y suben la lista); un touchpad manda fracciones y se suman
            controlsViewport.gameObject.AddComponent<UIControlsScroll>().onScroll = ticks => { if (capture == CaptureState.Idle) controlsWheel -= ticks * CtlWheelStops; };
            for (int d = 0; d < BindingTable.Devices; d++) BuildControlsList(d);

            // barra de pincel que dice dónde está la lista
            controlsTrack = UIFactory.Centered("Track", controlsCard, new Color(UIFactory.Paper.r, UIFactory.Paper.g, UIFactory.Paper.b, 0.1f), new Vector2(0f, 1f), new Vector2(CtlViewX + CtlViewW + 6f, CtlViewTop - CtlViewH * 0.5f), new Vector2(CtlViewH - 16f, 8f), UISprites.BrushLine).rectTransform;
            controlsTrack.localRotation = Quaternion.Euler(0f, 0f, 90f);
            controlsThumb = UIFactory.Centered("Thumb", controlsCard, new Color(UIFactory.Gold.r, UIFactory.Gold.g, UIFactory.Gold.b, 0.65f), new Vector2(0f, 1f), Vector2.zero, new Vector2(100f, 10f), UISprites.BrushLine).rectTransform;
            controlsThumb.localRotation = Quaternion.Euler(0f, 0f, 90f);

            // aviso de dos renglones (qué pasó con la tecla) y, cuando no hay aviso, las teclas de la página
            controlsInfoRoot = UIFactory.Rect("Info", controlsCard, new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(0.5f, 0.5f), new Vector2(530f, -794f), new Vector2(920f, 70f));
            controlsInfoGroup = controlsInfoRoot.gameObject.AddComponent<CanvasGroup>();
            controlsInfo = UIFactory.Text("Title", controlsInfoRoot, "", 27, UIFactory.Gold, new Vector2(0.5f, 0.5f), new Vector2(0f, 15f), new Vector2(920f, 38f), TextAlignmentOptions.Center);
            controlsInfo.rectTransform.pivot = new Vector2(0.5f, 0.5f);
            controlsInfoSub = UIFactory.Text("Sub", controlsInfoRoot, "", 22, UIFactory.Paper, new Vector2(0.5f, 0.5f), new Vector2(0f, -19f), new Vector2(920f, 32f), TextAlignmentOptions.Center);
            controlsInfoSub.rectTransform.pivot = new Vector2(0.5f, 0.5f);

            controlsBack = UIFactory.MenuItem("Back", controlsCard, "Volver", new Vector2(300, 66), CloseControls, 36f);
            controlsReset = UIFactory.MenuItem("Reset", controlsCard, "Restablecer", new Vector2(360, 66), ResetControls, 36f);
            controlsResetLabel = controlsReset.GetComponent<NindoMenuItem>().label;
            foreach (var (b, x) in new[] { (controlsBack, -280f), (controlsReset, 170f) })
            {
                var rt = (RectTransform)b.transform;
                rt.anchorMin = rt.anchorMax = new Vector2(0.5f, 1f); rt.pivot = new Vector2(0.5f, 0.5f);
                rt.anchoredPosition = new Vector2(x, -866f);
            }

            // velo invisible encima de todo mientras se espera una tecla: el clic se asigna, no aprieta botones
            controlsBlocker = UIFactory.Image("Blocker", panel, new Color(0f, 0f, 0f, 0f));
            controlsBlocker.rectTransform.Fill(Vector2.zero, Vector2.zero);
            controlsBlocker.raycastTarget = true;
            controlsBlocker.gameObject.SetActive(false);
            controlsCard.gameObject.SetActive(false);
        }

        /// <summary>La lista de un dispositivo: las filas que existen ahí, por grupo y en el orden del catálogo.</summary>
        void BuildControlsList(int dev)
        {
            var t = InputBindings.Table;
            var content = UIFactory.Rect(dev == BindingTable.Keys ? "Keys" : "Pad", controlsViewport, new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(0f, 1f), Vector2.zero, new Vector2(CtlViewW, 100f));
            controlsContent[dev] = content;
            var stops = controlsStops[dev];
            stops.Add(0f);
            var order = new List<int>();
            for (int r = 0; r < t.RowCount; r++) if (t.Row(r).shown[dev]) order.Add(r);
            order.Sort((a, b) => t.Row(a).group != t.Row(b).group ? t.Row(a).group.CompareTo(t.Row(b).group) : t.Row(a).order != t.Row(b).order ? t.Row(a).order.CompareTo(t.Row(b).order) : a.CompareTo(b));
            float y = 6f;
            int group = -1;
            foreach (int r in order)
            {
                var row = t.Row(r);
                if (row.group != group)
                {
                    if (group >= 0) y += 10f;
                    if (y - CtlStopPad > 0f) stops.Add(y - CtlStopPad);
                    group = row.group;
                    string name = group >= 0 && group < BindingCatalog.GroupNames.Length ? BindingCatalog.GroupNames[group] : "Otras";
                    var head = UIFactory.Text("Group", content, name, 24, UIFactory.Gold, new Vector2(0f, 1f), new Vector2(70f, -y - 6f), new Vector2(400, 32), TextAlignmentOptions.TopLeft, true);
                    head.characterSpacing = 6f;
                    // el trazo sigue al nombre del grupo a su altura (debajo se le metía entre las letras y la fila)
                    float hw = head.GetPreferredValues(name, 9999f, 32f).x;
                    var rule = UIFactory.Image("Rule", content, new Color(UIFactory.Gold.r, UIFactory.Gold.g, UIFactory.Gold.b, 0.32f), new Vector2(0f, 1f), new Vector2(70f + hw + 18f, -y - 21f), new Vector2(816f - hw - 18f, 8f), UISprites.BrushLine);
                    rule.rectTransform.pivot = new Vector2(0f, 0.5f);
                    y += CtlHeadH;
                }
                else stops.Add(y - CtlStopPad);
                controlsRows[dev].Add(BuildControlsRow(content, r, dev, y));
                y += CtlRowH;
            }
            // por qué hay teclas apagadas (en el mando la primera apagada es el movimiento, que no es por los menús)
            y += 10f;
            stops.Add(y - CtlStopPad);
            string note = dev == BindingTable.Keys ? "Las teclas apagadas son fijas: así siempre podés pausar, confirmar y volver."
                                                   : "Los botones apagados son fijos: el stick y la cruceta mueven a Kaito,\ny así siempre podés pausar, confirmar y volver.";
            UIFactory.Text("Note", content, note, 21, CtlDim, new Vector2(0f, 1f), new Vector2(70f, -y), new Vector2(820, dev == BindingTable.Keys ? 30f : 60f), TextAlignmentOptions.TopLeft);
            y += dev == BindingTable.Keys ? 44f : 74f;
            // el final también es una parada: se agrega aire abajo hasta la parada siguiente al final justo
            float end = y - CtlViewH, max = 0f;
            foreach (float s in stops) if (s >= end) { max = s; break; }
            if (max < end) max = Mathf.Max(0f, end);
            stops.RemoveAll(s => s > max);
            if (stops[stops.Count - 1] < max) stops.Add(max);
            content.sizeDelta = new Vector2(CtlViewW, Mathf.Max(y, max + CtlViewH));
            content.gameObject.SetActive(false);
        }

        ControlsRow BuildControlsRow(RectTransform content, int r, int dev, float y)
        {
            var t = InputBindings.Table;
            var ui = new ControlsRow { row = r, y = y };
            ui.rt = UIFactory.Rect("Row " + t.Row(r).id, content, new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(0f, 1f), new Vector2(0f, -y), new Vector2(CtlViewW, CtlRowH));
            // la fila elegida: un trazo apenas claro detrás y el kunai apuntando al nombre (como en los menús)
            ui.band = UIFactory.Centered("Band", ui.rt, new Color(UIFactory.Paper.r, UIFactory.Paper.g, UIFactory.Paper.b, 0f), new Vector2(0f, 0.5f), new Vector2(470f, 0f), new Vector2(900f, 58f), UISprites.BrushBanner);
            ui.cursor = UIFactory.Centered("Cursor", ui.rt, UIFactory.Gold, new Vector2(0f, 0.5f), new Vector2(CtlLabelX - 64f, 0f), new Vector2(86f, 30f), UISprites.Kunai);
            ui.cursor.enabled = false;
            ui.label = UIFactory.NoWrap(UIFactory.Text("Label", ui.rt, t.Row(r).label, 30, CtlDim, new Vector2(0f, 0.5f), new Vector2(CtlLabelX, 0f), new Vector2(420, CtlRowH), TextAlignmentOptions.Left, true));
            ui.label.rectTransform.pivot = new Vector2(0f, 0.5f);
            ui.unbound = UIFactory.NoWrap(UIFactory.Text("Unbound", ui.rt, "Sin asignar", 22, CtlWarn, new Vector2(0f, 0.5f), new Vector2(CtlSlot0X, 2f), new Vector2(188, CtlRowH), TextAlignmentOptions.Center));
            ui.unbound.rectTransform.pivot = new Vector2(0.5f, 0.5f);
            ui.unbound.enabled = false;
            for (int s = 0; s < BindingTable.Slots; s++) ui.slots[s] = BuildControlsSlot(ui.rt, r, dev, s, s == 0 ? CtlSlot0X : CtlSlot1X);
            return ui;
        }

        UIControlsSlot BuildControlsSlot(RectTransform rowRt, int r, int dev, int s, float x)
        {
            var rt = UIFactory.Rect("Slot" + s, rowRt, new Vector2(0f, 0.5f), new Vector2(0f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(x, 0f), new Vector2(188f, CtlRowH - 2f));
            var hit = rt.gameObject.AddComponent<Image>();
            hit.color = new Color(0f, 0f, 0f, 0f);
            var line = UIFactory.Centered("Line", rt, new Color(UIFactory.Paper.r, UIFactory.Paper.g, UIFactory.Paper.b, 0.16f), new Vector2(0.5f, 0.5f), new Vector2(0f, -20f), new Vector2(132f, 12f), UISprites.BrushLine);
            var key = UIFactory.KeyCap(rt, "?", CtlKeyH, new Vector2(0.5f, 0.5f), new Vector2(0f, 4f));
            var dots = new Image[3];
            for (int i = 0; i < dots.Length; i++)
            {
                dots[i] = UIFactory.Centered("Dot", rt, UIFactory.Gold, new Vector2(0.5f, 0.5f), new Vector2((i - 1) * 26f, 4f), new Vector2(15f, 15f), UISprites.Pip);
                dots[i].enabled = false;
            }
            var slot = rt.gameObject.AddComponent<UIControlsSlot>();
            slot.transition = Selectable.Transition.None;
            slot.targetGraphic = hit;
            slot.row = r; slot.dev = dev; slot.slot = s;
            slot.key = key; slot.keyGroup = key.gameObject.AddComponent<CanvasGroup>();
            slot.line = line; slot.dots = dots;
            slot.onActivate = StartCapture;
            slot.onClear = ClearControlsSlot;
            slot.interactable = !InputBindings.Table.Locked(r, dev, s);
            return slot;
        }

        // ================================================================== abrir, cambiar de dispositivo, cerrar
        /// <summary>Cambia la tarjeta de Opciones por la de controles (con Opciones abierto; si no, no hace nada).</summary>
        public void OpenControls()
        {
            if (!optionsPanel.activeSelf || controlsOpen) return;
            controlsOpen = true;
            controlsOpenT = 0f;
            controlsResetArmed = 0f;
            int dev = Game.Input != null && Game.Input.UsingGamepad ? BindingTable.Pad : BindingTable.Keys;
            controlsDevice.SetIndex(dev, false);
            optionsCard.gameObject.SetActive(false);
            controlsCard.gameObject.SetActive(true);
            RefreshControlsSlots();
            ControlsHint();
            ShowControlsDevice(dev);
            ControlsRescueNotice();
        }

        /// <summary>
        /// Una acción nueva (el mapa) llegó cuando el jugador ya usaba sus teclas para otra cosa y recibió una libre al
        /// cargar (BindingTable.Load): se avisa una vez, la primera vez que se abre la página.
        /// </summary>
        void ControlsRescueNotice()
        {
            if (!InputBindings.PendingRescue) return;
            InputBindings.PendingRescue = false;
            var t = InputBindings.Table;
            foreach (var r in t.Rescued)
            {
                string who = r.holder >= 0 ? " ya era de " + t.Row(r.holder).label : " ya se usaba para otra cosa";
                ControlsInfo(t.Row(r.row).label + " usa " + ControlsChip(r.code, r.dev), ControlsChip(r.lost, r.dev) + who, UIFactory.Gold, 6f);
                // si hay más de una (teclado y mando) se muestra la del dispositivo que se está mirando
                if (r.dev == controlsDev) break;
            }
        }

        void ShowControlsDevice(int dev)
        {
            controlsDev = dev;
            for (int d = 0; d < BindingTable.Devices; d++) controlsContent[d].gameObject.SetActive(d == dev);
            controlsContent[dev].anchoredPosition = Vector2.zero;
            controlsScrollTarget = -1f;
            controlsWheel = 0f;
            LinkControlsNavigation(dev);
            // al abrir, la primera casilla; al cambiar de dispositivo con el selector, el foco se queda en el selector
            var sel = EventSystem.current != null ? EventSystem.current.currentSelectedGameObject : null;
            if (sel != controlsDevice.gameObject) SelectControlsSlot(FirstControlsSlot(dev));
            controlsLastSel = null;
            if (controlsOpen && dev == BindingTable.Pad && !InputBindings.PadConnected)
                ControlsInfo("No hay un mando conectado", "Conectalo para cambiar sus botones", CtlWarn, 4f);
        }

        void CloseControls()
        {
            if (!controlsOpen) return;
            Settings.Save();
            ResetControlsPage();
            Select(controlsEntry);
        }

        /// <summary>Cierra la página sin más (también si la pausa se cerró de golpe con la página abierta).</summary>
        void ResetControlsPage()
        {
            if (capture != CaptureState.Idle) { capture = CaptureState.Idle; captureSlot = null; SetMenuNavigation(true); }
            captureReturn = null;
            controlsBlocker.gameObject.SetActive(false);
            controlsOpen = false;
            controlsCard.gameObject.SetActive(false);
            optionsCard.gameObject.SetActive(true);
            SetResetArmed(false);
        }

        /// <summary>
        /// Llamado desde UpdatePanels antes que la pausa: con la página abierta, Esc / B / la pausa vuelven a Opciones (no
        /// cierran todo) y, mientras se espera una tecla, no hacen nada acá (la espera las maneja: cancelan o se asignan).
        /// </summary>
        bool ControlsTakeBack(InputReader input)
        {
            if (!controlsOpen) return false;
            if (capture != CaptureState.Idle) return true;
            if (input != null && (input.Pressed(Act.Pause) || input.Pressed(Act.Cancel))) { Game.Audio?.Play("ui_close", null, 0.4f); CloseControls(); }
            return true;
        }

        // ================================================================== navegación
        UIControlsSlot FirstControlsSlot(int dev)
        {
            foreach (var row in controlsRows[dev])
                foreach (var s in row.slots)
                    if (s.interactable) return s;
            return null;
        }

        /// <summary>La casilla de la fila más cercana en esa dirección, en la misma columna o, si es fija, en la otra.</summary>
        static UIControlsSlot NextControlsSlot(List<ControlsRow> rows, int from, int dir, int col)
        {
            for (int j = from + dir; j >= 0 && j < rows.Count; j += dir)
            {
                if (rows[j].slots[col].interactable) return rows[j].slots[col];
                if (rows[j].slots[1 - col].interactable) return rows[j].slots[1 - col];
            }
            return null;
        }

        void LinkControlsNavigation(int dev)
        {
            var rows = controlsRows[dev];
            UIControlsSlot first = FirstControlsSlot(dev), last0 = null, last1 = null;
            for (int i = 0; i < rows.Count; i++)
                for (int c = 0; c < BindingTable.Slots; c++)
                {
                    var s = rows[i].slots[c];
                    if (!s.interactable) continue;
                    var other = rows[i].slots[1 - c];
                    s.navigation = new Navigation
                    {
                        mode = Navigation.Mode.Explicit,
                        selectOnLeft = other.interactable ? other : null,
                        selectOnRight = other.interactable ? other : null,
                        selectOnUp = (Selectable)NextControlsSlot(rows, i, -1, c) ?? controlsDevice,
                        selectOnDown = (Selectable)NextControlsSlot(rows, i, 1, c) ?? (c == 0 ? controlsBack : controlsReset),
                    };
                    if (c == 0) last0 = s; else last1 = s;
                }
            controlsDevice.navigation = new Navigation { mode = Navigation.Mode.Explicit, selectOnUp = controlsBack, selectOnDown = first };
            controlsBack.navigation = new Navigation { mode = Navigation.Mode.Explicit, selectOnUp = (Selectable)last0 ?? last1, selectOnDown = controlsDevice, selectOnLeft = controlsReset, selectOnRight = controlsReset };
            controlsReset.navigation = new Navigation { mode = Navigation.Mode.Explicit, selectOnUp = (Selectable)last1 ?? last0, selectOnDown = controlsDevice, selectOnLeft = controlsBack, selectOnRight = controlsBack };
        }

        static void SelectControlsSlot(UIControlsSlot s)
        {
            if (s == null || EventSystem.current == null) return;
            s.silent = true;
            s.byPointer = false;
            EventSystem.current.SetSelectedGameObject(s.gameObject);
        }

        static void SetMenuNavigation(bool on)
        {
            if (EventSystem.current != null) EventSystem.current.sendNavigationEvents = on;
        }

        // ================================================================== teclas en pantalla
        static int ControlsFamily(int dev) => dev == BindingTable.Keys ? 0 : InputBindings.PadFamily();

        void RefreshControlsSlots()
        {
            var t = InputBindings.Table;
            controlsShownVersion = InputBindings.Version;
            controlsShownFamily = InputBindings.PadFamily();
            for (int d = 0; d < BindingTable.Devices; d++)
            {
                int fam = ControlsFamily(d);
                foreach (var row in controlsRows[d])
                {
                    bool none = t.Count(row.row, d) == 0;
                    row.unbound.enabled = none;
                    foreach (var s in row.slots)
                    {
                        string name = InputBindings.Name(row.row, d, s.slot, fam);
                        s.key.gameObject.SetActive(name != null);
                        if (name != null) UIFactory.SetKeyCap(s.key, name, fam, CtlKeyLong);
                        // una casilla fija vacía (la alternativa de Confirmar) no muestra ni el trazo
                        s.line.enabled = s.interactable;
                    }
                }
            }
        }

        string ControlsChip(int code, int dev)
        {
            int fam = ControlsFamily(dev);
            return UIFactory.KeyChip(InputBindings.Display(code, fam) ?? "?", fam);
        }

        /// <summary>Las teclas de la página en el dispositivo que se está usando (Enter / A cambia, Supr o clic derecho / X quita, Esc / B vuelve).</summary>
        void ControlsHint()
        {
            var t = InputBindings.Table;
            controlsHintPad = Game.Input != null && Game.Input.UsingGamepad;
            int dev = controlsHintPad ? BindingTable.Pad : BindingTable.Keys, fam = ControlsFamily(dev);
            string change = ControlsChip(t.Get((int)Act.Submit, dev, 0), dev);
            // con el mouse se quita con el clic derecho sobre la casilla (UIControlsSlot): si no se dice, nadie lo encuentra
            string clear = controlsHintPad ? UIFactory.KeyChip(fam == 2 ? "□" : "X", fam) : UIFactory.KeyChip("Supr", 0) + " " + UIFactory.KeyChip("Clic der.", 0);
            string back = ControlsChip(t.Get((int)Act.Cancel, dev, 0), dev);
            controlsInfo.text = change + " Cambiar        " + clear + " Quitar        " + back + " Volver";
            controlsInfo.color = CtlDim;
            controlsInfo.fontSize = 24f;
            controlsInfoSub.text = "";
            controlsInfoLife = 0f;
            controlsHintShown = true;
        }

        /// <param name="life">Segundos a la vista; 0 = hasta el próximo aviso (la espera de una tecla).</param>
        void ControlsInfo(string title, string sub, Color c, float life)
        {
            controlsInfo.text = title;
            controlsInfo.color = c;
            controlsInfo.fontSize = 27f;
            controlsInfoSub.text = sub ?? "";
            controlsInfoT = 0f;
            controlsInfoLife = life;
            controlsInfoGroup.alpha = 1f;
            controlsHintShown = false;
        }

        // ================================================================== reasignar
        /// <param name="byPointer">Se abrió con un clic: el segundo clic de un doble clic no queda asignado.</param>
        void StartCapture(UIControlsSlot s, bool byPointer)
        {
            if (capture != CaptureState.Idle || !controlsOpen) return;
            var row = InputBindings.Table.Row(s.row);
            if (s.dev == BindingTable.Pad && !InputBindings.PadConnected)
            {
                Game.Audio?.Play("denied", null, 0.5f);
                ControlsInfo("No hay un mando conectado", "Conectalo para cambiar sus botones", CtlWarn, 4f);
                return;
            }
            capture = CaptureState.Arming;
            captureSlot = s;
            captureByPointer = byPointer;
            captureT = 0f;
            SetMenuNavigation(false);
            controlsBlocker.gameObject.SetActive(true);
            SetResetArmed(false);
            Game.Audio?.Play("ui_select", null, 0.6f);
            var t = InputBindings.Table;
            bool padUser = Game.Input != null && Game.Input.UsingGamepad;
            string cancel = padUser ? ControlsChip(t.Get((int)Act.Pause, BindingTable.Pad, 0), BindingTable.Pad) : ControlsChip(t.Get((int)Act.Pause, BindingTable.Keys, 0), BindingTable.Keys);
            // dos renglones: qué hacer (también un botón del mouse) y cómo salir; la rueda sirve donde se puede pero no se
            // nombra, y si no sirve (fijar, moverse) el rechazo explica por qué
            if (s.dev == BindingTable.Keys)
                ControlsInfo("Presioná la tecla o el botón del mouse para " + row.label, cancel + " cancela", UIFactory.Gold, 0f);
            else
                ControlsInfo("Presioná el botón nuevo para " + row.label, cancel + " cancela", UIFactory.Gold, 0f);
        }

        void UpdateCapture(float dt)
        {
            switch (capture)
            {
                case CaptureState.Arming:
                    // el Enter, la A o el clic que abrió la espera todavía puede estar apretado (y en el mismo cuadro
                    // contaría como apretado ahora). Tomar es por flanco, así que pasado medio segundo ya no hay riesgo
                    // aunque algo siga apretado (un gatillo que no vuelve del todo no traba la espera)
                    captureT += dt;
                    if (InputBindings.CaptureCancelPressed(captureSlot.dev)) { CancelCapture(); break; }
                    if (!InputBindings.AnyHeld() || captureT > 0.5f) { capture = CaptureState.Listening; captureT = 0f; }
                    break;
                case CaptureState.Listening:
                    captureT += dt;
                    if (InputBindings.CaptureCancelPressed(captureSlot.dev)) { CancelCapture(); break; }
                    // abierta con un clic, el mouse cuenta recién pasado el tiempo de un doble clic: si no, el segundo
                    // clic le daba el clic izquierdo a la acción (y le sacaba el ataque al mouse)
                    int code = InputBindings.Capture(captureSlot.dev, !captureByPointer || captureT >= 0.4f);
                    if (code != BindCode.None) { ApplyCapture(captureSlot, code); EndCapture(); }
                    else if (captureT > 8f)
                    {
                        ControlsInfo("Sin cambios", captureSlot.dev == BindingTable.Keys ? "No llegó ninguna tecla" : "No llegó ningún botón", UIFactory.Paper, 3f);
                        EndCapture();
                    }
                    break;
                case CaptureState.Releasing:
                    // la tecla tomada (Enter, la A) no puede confirmar nada en el menú al volver la navegación; confirmar
                    // va por flanco, así que con algo trabado alcanza con esperar un poco
                    captureT += dt;
                    RestoreCaptureSelection();
                    if (!InputBindings.AnyHeld() || captureT > 0.6f)
                    {
                        capture = CaptureState.Idle;
                        SetMenuNavigation(true);
                        controlsBlocker.gameObject.SetActive(false);
                        RestoreCaptureSelection();
                        captureReturn = null;
                    }
                    break;
            }
        }

        void EndCapture()
        {
            capture = CaptureState.Releasing;
            captureReturn = captureSlot;
            captureSlot = null;
            captureT = 0f;
        }

        /// <summary>
        /// Un clic sobre el velo (el que se asignó, o uno del doble clic) le saca la selección a la casilla: el
        /// EventSystem deselecciona al hacer clic sobre algo que no se elige. Vuelve a la casilla que esperaba la tecla,
        /// así sigue resaltada y las flechas, el stick y Supr siguen andando.
        /// </summary>
        void RestoreCaptureSelection()
        {
            var es = EventSystem.current;
            if (captureReturn != null && es != null && es.currentSelectedGameObject == null) SelectControlsSlot(captureReturn);
        }

        void CancelCapture()
        {
            Game.Audio?.Play("ui_close", null, 0.4f);
            ControlsInfo("Sin cambios", null, UIFactory.Paper, 2f);
            EndCapture();
        }

        void ApplyCapture(UIControlsSlot s, int code)
        {
            var t = InputBindings.Table;
            var res = t.Assign(s.row, s.dev, s.slot, code);
            if (res.Changed)
            {
                InputBindings.Commit();
                RefreshControlsSlots();
                s.Pop();
                if (res.others != null)
                    foreach (int q in res.others) FlashControlsRow(q, s.dev);
                if (res.outcome == BindOutcome.OwnSwap) FlashControlsRow(s.row, s.dev);
            }
            ControlsResult(res);
        }

        void FlashControlsRow(int r, int dev)
        {
            foreach (var row in controlsRows[dev])
                if (row.row == r) foreach (var slot in row.slots) if (slot.interactable) slot.Flash();
        }

        void ClearControlsSlot(UIControlsSlot s)
        {
            if (capture != CaptureState.Idle || !s.interactable) return;
            var res = InputBindings.Table.Clear(s.row, s.dev, s.slot);
            if (res.Changed) { InputBindings.Commit(); RefreshControlsSlots(); }
            ControlsResult(res);
        }

        void ResetControls()
        {
            if (capture != CaptureState.Idle) return;
            var t = InputBindings.Table;
            bool keys = controlsDev == BindingTable.Keys;
            string devName = keys ? "Teclado y mouse" : "Mando";
            if (t.IsDefault(controlsDev)) { ControlsInfo(keys ? "Ya están las teclas de fábrica" : "Ya están los botones de fábrica", devName, UIFactory.Paper, 3f); return; }
            // dos pasos: un Enter de más no borra lo que el jugador armó (el botón pasa a decir "Confirmar")
            if (controlsResetArmed <= 0f)
            {
                SetResetArmed(true);
                ControlsInfo(keys ? "¿Volver a las teclas de fábrica?" : "¿Volver a los botones de fábrica?", keys ? "Confirmá para el teclado y mouse" : "Confirmá para el mando", CtlWarn, 4f);
                return;
            }
            SetResetArmed(false);
            t.Reset(controlsDev);
            InputBindings.Commit();
            RefreshControlsSlots();
            foreach (var row in controlsRows[controlsDev]) foreach (var s in row.slots) if (s.interactable) s.Pop();
            ControlsInfo(keys ? "Teclas de fábrica" : "Botones de fábrica", devName, UIFactory.Gold, 3f);
        }

        void SetResetArmed(bool on)
        {
            controlsResetArmed = on ? 4f : 0f;
            if (controlsResetLabel != null) controlsResetLabel.text = on ? "Confirmar" : "Restablecer";
        }

        /// <summary>El aviso de lo que pasó, en dos renglones: qué tiene ahora la acción y, si tocó a otra, qué le quedó.</summary>
        void ControlsResult(BindResult res)
        {
            var t = InputBindings.Table;
            string label = t.Row(res.row).label;
            int dev = res.dev;
            bool button = !BindCode.IsKey(res.code);
            string chip = res.code != BindCode.None ? ControlsChip(res.code, dev) : null;
            if (res.Ok && res.outcome != BindOutcome.Same) Game.Audio?.Play("ui_select", null, 0.7f);
            switch (res.outcome)
            {
                case BindOutcome.Assigned:
                    ControlsInfo(label + " ahora usa " + chip, null, UIFactory.Gold, 3.5f);
                    return;
                case BindOutcome.Same:
                    if (res.code != BindCode.None) ControlsInfo(label + " ya usa " + chip, null, UIFactory.Paper, 3f);
                    return;
                case BindOutcome.OwnSwap:
                    ControlsInfo(label + " ahora usa " + chip, "Principal y alternativa intercambiadas", UIFactory.Gold, 3.5f);
                    return;
                case BindOutcome.Swapped:
                case BindOutcome.Taken:
                {
                    string others = RowNames(res.others);
                    bool many = res.others.Length > 1;
                    string sub = res.outcome == BindOutcome.Swapped
                        ? others + (many ? " pasan a " : " pasa a ") + ControlsChip(res.otherCode, dev)
                        : many ? others + (button ? " ya no lo usan" : " ya no la usan") : others + " se queda con " + ControlsChip(res.otherCode, dev);
                    ControlsInfo(label + " ahora usa " + chip, sub, UIFactory.Gold, 4.5f);
                    return;
                }
                case BindOutcome.Cleared:
                    ControlsInfo("Quitaste " + ControlsChip(res.previous, dev) + " de " + label, null, UIFactory.Paper, 3f);
                    return;
            }
            Game.Audio?.Play("denied", null, 0.5f);
            string pick = dev == BindingTable.Keys ? "Elegí otra tecla" : "Elegí otro botón";
            switch (res.refusal)
            {
                case BindRefusal.Reserved:
                    if (res.reason == "pausa") ControlsInfo(chip + (button ? " queda fijo para pausar" : " queda fija para pausar"), "Así siempre podés abrir el menú", CtlWarn, 4f);
                    else if (res.reason == "cruceta") ControlsInfo("La cruceta mueve a Kaito", pick, CtlWarn, 4f);
                    // la pausa y el mapa también se leen con un menú abierto: el clic o las flechas harían dos cosas
                    else if (res.reason == "menu") ControlsInfo(chip + " se usa en los menús", label + (dev == BindingTable.Keys ? " necesita otra tecla" : " necesita otro botón"), CtlWarn, 4f);
                    else ControlsInfo(chip + " es del sistema", pick, CtlWarn, 4f);
                    break;
                case BindRefusal.LockedElsewhere:
                    ControlsInfo(chip + (button ? " queda fijo para " : " queda fija para ") + t.Row(res.other).label, pick, CtlWarn, 4f);
                    break;
                case BindRefusal.OnlyKey:
                    // "Siguiente objetivo solo tiene Rueda ↓": sin "tecla" ni "botón" (la rueda no es ninguna de las dos)
                    ControlsInfo(t.Row(res.other).label + " solo tiene " + chip, dev == BindingTable.Keys ? "Primero dale otra tecla" : "Primero dale otro botón", CtlWarn, 4.5f);
                    break;
                case BindRefusal.NeedsHold:
                    // el movimiento del teclado solo puede recibir la rueda; fijar, también un toque del stick
                    if (t.Row(res.row).move != 0) ControlsInfo("La rueda no sirve para moverse", "Elegí una tecla", CtlWarn, 4f);
                    else if (dev == BindingTable.Keys) ControlsInfo(label + " necesita una tecla que se pueda mantener", "Mantenela apretada para soltar el objetivo", CtlWarn, 4.5f);
                    else ControlsInfo(label + " necesita un botón que se pueda mantener", "Mantenelo apretado para soltar el objetivo", CtlWarn, 4.5f);
                    break;
                case BindRefusal.LastKey:
                    ControlsInfo(label + (dev == BindingTable.Keys ? " necesita al menos una tecla" : " necesita al menos un botón"), null, CtlWarn, 3.5f);
                    break;
                default:
                    ControlsInfo("Esa casilla es fija", null, CtlWarn, 3f);
                    break;
            }
        }

        static string RowNames(int[] rows)
        {
            var t = InputBindings.Table;
            if (rows.Length == 1) return t.Row(rows[0]).label;
            var parts = new string[rows.Length];
            for (int i = 0; i < rows.Length; i++) parts[i] = t.Row(rows[i]).label;
            string last = parts[parts.Length - 1];
            // "Ejecutar e Interactuar": la y pasa a e delante de i
            bool e = last.StartsWith("I") || last.StartsWith("Hi");
            return string.Join(", ", parts, 0, parts.Length - 1) + (e ? " e " : " y ") + last;
        }

        // ================================================================== cada cuadro
        void UpdateControls(float dt)
        {
            if (!controlsOpen) return;
            // la pausa se cerró con la página abierta (morir, una cinemática): queda lista para la próxima vez
            if (!optionsPanel.activeSelf) { ResetControlsPage(); return; }
            controlsOpenT += dt;
            float ck = UIAnim.OutCubic(controlsOpenT / 0.2f);
            controlsCard.SetPos(new Vector2(330f + 90f * (1f - ck), -10f));
            controlsCardImg.color = new Color(1f, 1f, 1f, ck);

            UpdateCapture(dt);
            if (controlsShownVersion != InputBindings.Version || controlsShownFamily != InputBindings.PadFamily()) RefreshControlsSlots();

            var es = EventSystem.current;
            var sel = es != null ? es.currentSelectedGameObject : null;
            if (capture == CaptureState.Idle && sel != null && InputBindings.ClearPressed())
            {
                var s = sel.GetComponent<UIControlsSlot>();
                if (s != null) ClearControlsSlot(s);
            }
            if (controlsResetArmed > 0f)
            {
                controlsResetArmed -= dt;
                if (controlsResetArmed <= 0f || (sel != controlsReset.gameObject && capture == CaptureState.Idle)) SetResetArmed(false);
            }

            // filas: la elegida (o la que espera una tecla) se aclara, crece un poco y el kunai la señala
            foreach (var row in controlsRows[controlsDev])
            {
                bool listening = false, on = false;
                for (int i = 0; i < row.slots.Length; i++)
                {
                    var s = row.slots[i];
                    bool l = capture != CaptureState.Idle && capture != CaptureState.Releasing && s == captureSlot;
                    listening |= l;
                    on |= l || s.Selected;
                    s.Animate(dt, l, !s.interactable);
                }
                row.k = Mathf.MoveTowards(row.k, on ? 1f : 0f, dt / (on ? UIAnim.Fast : 0.1f));
                float e = UIAnim.OutCubic(row.k);
                bool none = row.unbound.enabled;
                row.label.color = Color.Lerp(none ? CtlWarn : CtlDim, none ? CtlWarn : UIFactory.Paper, e);
                row.label.rectTransform.SetScale(1f + 0.04f * e);
                var bc = row.band.color; bc.a = 0.07f * e; row.band.color = bc;
                row.cursor.enabled = e > 0.01f;
                if (row.cursor.enabled)
                {
                    var cc = row.cursor.color; cc.a = e; row.cursor.color = cc;
                    float poke = Mathf.Pow(Mathf.Max(0f, Mathf.Sin(Time.unscaledTime * Mathf.PI * 2f / 1.1f)), 6f) * 6f;
                    row.cursor.rectTransform.SetPos(new Vector2(CtlLabelX - 64f - 24f * (1f - e) + poke * e, 0f));
                }
            }

            FollowControlsSelection(sel);
            var content = controlsContent[controlsDev];
            int notches = (int)controlsWheel;
            if (notches != 0)
            {
                controlsWheel -= notches;
                controlsScrollTarget = StepControlsStops(controlsScrollTarget >= 0f ? controlsScrollTarget : content.anchoredPosition.y, notches);
            }
            if (controlsScrollTarget >= 0f)
            {
                var p = content.anchoredPosition;
                p.y = Mathf.Lerp(p.y, controlsScrollTarget, 1f - Mathf.Exp(-dt * 16f));
                if (Mathf.Abs(p.y - controlsScrollTarget) < 0.5f) { p.y = controlsScrollTarget; controlsScrollTarget = -1f; }
                content.anchoredPosition = p;
            }
            UpdateControlsThumb(content);

            // el aviso se va y vuelven las teclas de la página (cambian con el dispositivo que se usa)
            bool padUser = Game.Input != null && Game.Input.UsingGamepad;
            if (controlsInfoLife > 0f)
            {
                controlsInfoT += dt;
                if (controlsInfoT > controlsInfoLife) controlsInfoGroup.SetAlpha(Mathf.MoveTowards(controlsInfoGroup.alpha, 0f, dt / 0.25f));
                if (controlsInfoGroup.alpha <= 0f) ControlsHint();
            }
            else if (capture == CaptureState.Idle)
            {
                if (padUser != controlsHintPad && controlsHintShown) ControlsHint();
                controlsInfoGroup.SetAlpha(Mathf.MoveTowards(controlsInfoGroup.alpha, 1f, dt / 0.25f));
            }
        }

        /// <summary>
        /// Con teclado o mando, la lista se corre para que la fila elegida quede a la vista con un poco de aire (el título
        /// de su grupo arriba). Con el mouse no: lo que se ve lo maneja la rueda.
        /// </summary>
        void FollowControlsSelection(GameObject sel)
        {
            if (sel == controlsLastSel) return;
            controlsLastSel = sel;
            if (sel == null || InputBindings.PointerOver((RectTransform)sel.transform)) return;
            var content = controlsContent[controlsDev];
            float viewH = controlsViewport.rect.height, max = Mathf.Max(0f, content.sizeDelta.y - viewH);
            if (sel == controlsDevice.gameObject) { controlsScrollTarget = 0f; return; }
            if (sel == controlsBack.gameObject || sel == controlsReset.gameObject) { controlsScrollTarget = max; return; }
            var s = sel.GetComponent<UIControlsSlot>();
            if (s == null || s.dev != controlsDev || s.byPointer) return;
            var rows = controlsRows[controlsDev];
            var stops = controlsStops[controlsDev];
            for (int i = 0; i < rows.Count; i++)
            {
                if (rows[i].row != s.row) continue;
                float cur = controlsScrollTarget >= 0f ? controlsScrollTarget : content.anchoredPosition.y;
                // con aire: arriba la fila anterior o el título del grupo, abajo casi una fila más
                float top = rows[i].y - CtlHeadH - CtlStopPad, bottom = rows[i].y + CtlRowH + 40f;
                // en la primera y en la última que se pueden elegir se ve hasta el borde: arriba el título del grupo,
                // abajo las fijas (Confirmar, Volver) y la nota que explica por qué están apagadas
                if (NextControlsSlot(rows, i, -1, s.slot) == null) top = 0f;
                if (NextControlsSlot(rows, i, 1, s.slot) == null) bottom = content.sizeDelta.y;
                if (top < cur)
                {
                    // la parada más baja que deja ver ese aire
                    float t = 0f;
                    foreach (float st in stops) if (st <= top + 0.5f) t = st;
                    controlsScrollTarget = t;
                }
                else if (bottom > cur + viewH)
                {
                    float t = max;
                    for (int j = stops.Count - 1; j >= 0; j--) if (stops[j] >= bottom - viewH - 0.5f) t = stops[j];
                    controlsScrollTarget = Mathf.Min(t, max);
                }
                return;
            }
        }

        /// <summary>'n' paradas más abajo (o más arriba si es negativo) desde 'from', sin salirse de la lista.</summary>
        float StepControlsStops(float from, int n)
        {
            var stops = controlsStops[controlsDev];
            int i;
            if (n > 0)
            {
                // desde la parada en la que está o la de arriba más cercana
                i = 0;
                while (i + 1 < stops.Count && stops[i + 1] <= from + 0.5f) i++;
            }
            else
            {
                i = stops.Count - 1;
                while (i > 0 && stops[i - 1] >= from - 0.5f) i--;
            }
            return stops[Mathf.Clamp(i + n, 0, stops.Count - 1)];
        }

        void UpdateControlsThumb(RectTransform content)
        {
            float viewH = controlsViewport.rect.height, contentH = content.sizeDelta.y;
            bool show = contentH > viewH + 1f;
            if (controlsThumb.gameObject.activeSelf != show) { controlsThumb.gameObject.SetActive(show); controlsTrack.gameObject.SetActive(show); }
            if (!show) return;
            float trackH = CtlViewH - 16f, h = Mathf.Max(48f, trackH * viewH / contentH);
            float k = Mathf.Clamp01(content.anchoredPosition.y / (contentH - viewH));
            float top = CtlViewTop - 8f;
            controlsThumb.SetSize(new Vector2(h, 10f));
            controlsThumb.SetPos(new Vector2(CtlViewX + CtlViewW + 6f, top - h * 0.5f - k * (trackH - h)));
        }
    }
}
