using System.Collections.Generic;
using TMPro;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.SceneManagement;
using UnityEngine.UI;
#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace Nindo
{
    /// <summary>
    /// Mapa del mundo (Act.Map: M, o Vista / panel táctil en el mando; también desde la pausa). Un pergamino que se
    /// desenrolla entre dos varillas de laca: la lámina pintada con los datos reales del mundo (Resources/UI/WorldMap.jpg,
    /// Tools/UI/build_world_map.py) bajo la niebla de tinta de lo que Kaito todavía no vio (MapFog + el shader
    /// Nindo/UI Map). Encima: Kaito y hacia dónde mira, los santuarios descubiertos (el de reaparición con su brillo),
    /// los guardianes (el sello de su zona cuando ya cayeron), los portales abiertos y el nombre de cada zona visitada.
    /// A la izquierda, la columna de tinta de la pausa con dónde estás, los sellos, cuánto exploraste y la leyenda.
    /// Pausa el juego mientras está abierto. Se cierra con M, Esc o B (vuelve a la pausa si se abrió desde ahí).
    /// Acercar: rueda, + / -, gatillos o stick derecho; mover: WASD / flechas / stick izquierdo o arrastrando con el
    /// mouse; Q / RS lo centra en Kaito. Lo que se descubrió desde la última vez se despeja a manchas al abrirlo.
    /// Las medidas son las de la maqueta de Tools/UI/world_map_preview.py (donde se juzga sin Unity).
    /// </summary>
    public partial class UIManager
    {
        // ---- medidas (canvas de referencia 1920 x 1080 en modo Expand)
        const float MapColX = 660f, MapPadR = 60f, MapPadV = 70f, MapRodW = 34f, MapRodGap = 30f, MapSoft = 26f;
        const float MapMaxZoom = 2.6f, MapCenterZoom = 1.8f;
        const float MapUnroll = 0.42f, MapRoll = 0.24f, MapRevealAt = 0.45f, MapRevealDur = 0.9f;
        const string MapHintFlag = "tut_map";

        static readonly Color MapVeilColor = new Color(0.012f, 0.012f, 0.03f, 0.72f);
        static readonly Color MapShrineRed = new Color(0.808f, 0.227f, 0.157f);      // bermellón de los torii
        static readonly Color MapShrineBare = new Color(0.93f, 0.9f, 0.83f);         // todavía sin rezar: madera sin laca
        static readonly Color MapPortalJade = new Color(0.5f, 0.88f, 0.63f);
        static readonly Color MapDim = new Color(0.78f, 0.75f, 0.67f);
        static readonly Color MapLegendText = new Color(0.87f, 0.84f, 0.77f);
        // la niebla (los mismos valores que la vista previa: el proyecto está en Gamma, se mezcla en sRGB)
        static readonly Color MapFogLight = new Color(0.34f, 0.36f, 0.43f), MapFogDark = new Color(0.19f, 0.2f, 0.26f);
        static readonly Color MapKasumi = new Color(0.8f, 0.77f, 0.68f, 0.45f), MapTide = new Color(0.045f, 0.04f, 0.065f, 0.62f);

        class MapMark
        {
            public RectTransform rt;
            public Image img, glow;
            public Vector3 world;
            public Vector2 at, nudge;   // dónde cae en la lámina (zoom 1) y cuánto se corre para no pisar a su vecina
            public Checkpoint cp;
            public BossArena arena;
            public Portal portal;
            public bool shown, fresh;
        }

        RectTransform mapRoot, mapView, mapContent, mapMarksRt, mapRodL, mapRodR, mapShadow, mapTip, mapReticle, mapKaito, mapKaitoRing, mapSwash;
        CanvasGroup mapGroup, mapMarksGroup, mapInfoGroup, mapTipGroup;
        Image mapVeil, mapColumn, mapZoneHanko, mapKaitoImg, mapRingImg, mapReticleImg;
        readonly Image[] mapSeals = new Image[3];
        TextMeshProUGUI mapZoneTitle, mapZoneSub, mapSealCount, mapExplored, mapTipTitle, mapTipSub;
        RawImage mapImage, mapFogFallback;
        Material mapMat;
        Texture2D mapFogTex, mapFogPrevTex;
        byte[] mapFogBytes, mapFogPrevBytes;
        ResourceRequest mapTexRequest;
        readonly List<MapMark> mapMarks = new List<MapMark>();
        readonly List<(TextMeshProUGUI text, string zone)> mapLabels = new List<(TextMeshProUGUI, string)>();
        readonly List<bool> mapLabelFresh = new List<bool>();
        bool mapFirstShown = true;
        readonly RectTransform[] mapHintKeys = new RectTransform[5];
        readonly TextMeshProUGUI[] mapHintLabels = new TextMeshProUGUI[5];
        int mapHintVersion = -1, mapFogVersion = -1;
        bool mapContentBuilt, mapFromPause, mapClosing, mapMouseMode, mapMouseOver, mapCursorMoved, mapFirstOpen = true;
        float mapT, mapCloseT, mapHintPoll, mapZoom = 1f, mapZoomT = 1f, mapSheetW = 1133f, mapSheetH = 940f, mapTipInkH = 78f;
        Vector2 mapPan, mapPanT, mapCursor, mapLastMouse, mapRootSize;
        MapMark mapTipMark;
#if ENABLE_INPUT_SYSTEM
        // + y - según la distribución del teclado (en el latinoamericano y el español no están donde el "=" del inglés)
        UnityEngine.InputSystem.Controls.KeyControl mapPlusKey, mapMinusKey;
#endif

        /// <summary>Abierto (o cerrándose): mientras tanto el juego está en pausa y el resto de la UI no recibe teclas.</summary>
        public bool MapOpen => mapRoot != null && mapRoot.gameObject.activeSelf;

        // ================================================================== armado
        void BuildMap()
        {
            mapRoot = UIFactory.Stretch("Map", menus);
            UIFactory.Nest(mapRoot, true);
            mapGroup = mapRoot.gameObject.AddComponent<CanvasGroup>();
            mapVeil = UIFactory.Image("Veil", mapRoot, MapVeilColor);
            mapVeil.rectTransform.Fill(Vector2.zero, Vector2.zero);
            mapVeil.raycastTarget = true;
            mapColumn = MenuColumn(mapRoot, "Mapa", out _);

            // ---- dónde estás, sellos, explorado y leyenda (debajo del título de la columna)
            var info = UIFactory.Stretch("Info", mapRoot);
            mapInfoGroup = info.gameObject.AddComponent<CanvasGroup>();
            mapZoneHanko = UIFactory.Centered("ZoneHanko", info, Color.white, new Vector2(0f, 1f), new Vector2(145f, -423f), new Vector2(70f, 70f), null);
            mapZoneHanko.rectTransform.localRotation = Quaternion.Euler(0f, 0f, -6f);
            mapZoneTitle = MapText("Zone", info, 32f, UIFactory.Paper, new Vector2(196f, -404f), true);
            mapZoneSub = MapText("ZoneSub", info, 22f, new Color(0.78f, 0.7f, 0.47f), new Vector2(197f, -440f), false);
            MapText("SealsLabel", info, 24f, MapDim, new Vector2(112f, -512f), false).text = "Sellos";
            for (int i = 0; i < 3; i++)
                mapSeals[i] = UIFactory.Centered("Seal" + i, info, Color.white, new Vector2(0f, 1f), new Vector2(141f + i * 70f, -567f), new Vector2(58f, 58f), UISprites.Hanko(UISprites.SealIconName((SealId)i)));
            mapSealCount = MapText("SealCount", info, 30f, UIFactory.Paper, new Vector2(330f, -567f), true);
            MapText("ExploredLabel", info, 24f, MapDim, new Vector2(112f, -640f), false).text = "Explorado";
            mapExplored = MapText("Explored", info, 32f, UIFactory.Gold, new Vector2(300f, -640f), true);
            // "Sin rezar" solo si la partida guarda dónde se rezó; con esa fila de más se aprietan (en 1080 de alto no
            // tienen que tocar las teclas de abajo, que con el mando son tres renglones)
            bool bare = MapShrinesField != null;
            float step = bare ? 36f : 40f, dy = 0f;
            MapLegendRow(info, dy, "MapKaito", Color.white, "Kaito", false);
            MapLegendRow(info, dy += step, "MapShrine", MapShrineRed, "Santuario", false);
            if (bare) MapLegendRow(info, dy += step, "MapShrine", MapShrineBare, "Sin rezar", false);
            MapLegendRow(info, dy += step, "MapShrine", MapShrineRed, "Punto de reaparición", true);
            MapLegendRow(info, dy += step, "Hanko_IconBoss", Color.white, "Guardián", false);
            MapLegendRow(info, dy += step, "MapPortal", MapPortalJade, "Portal al dojo", false);
            for (int i = 0; i < mapHintKeys.Length; i++)
            {
                mapHintKeys[i] = UIFactory.KeyCap(info, "M", 40f, new Vector2(0f, 0f), new Vector2(130f, 66f));
                mapHintLabels[i] = MapText("Hint" + i, info, 24f, MapLegendText, Vector2.zero, false);
                var lrt = mapHintLabels[i].rectTransform;
                lrt.anchorMin = lrt.anchorMax = Vector2.zero;
            }

            // ---- la lámina: sombra, ventana con el recorte del RectMask2D (se desenrolla), la lámina y sus marcas
            mapShadow = UIFactory.Sliced("Shadow", mapRoot, UISprites.Get("MapShadow"), new Color(0f, 0f, 0f, 0.8f), 120f).rectTransform;
            Place(mapShadow, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(100f, 100f));
            mapShadow.pivot = new Vector2(0.5f, 0.5f);
            mapView = UIFactory.Rect("Sheet", mapRoot, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(100f, 100f));
            var mask = mapView.gameObject.AddComponent<RectMask2D>();
            mask.softness = new Vector2Int(0, (int)MapSoft);
            mapContent = UIFactory.Rect("Content", mapView, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(100f, 100f));
            var imgGo = new GameObject("Lamina", typeof(RectTransform), typeof(RawImage));
            imgGo.transform.SetParent(mapContent, false);
            mapImage = imgGo.GetComponent<RawImage>();
            mapImage.raycastTarget = false;
            mapImage.rectTransform.Fill(Vector2.zero, Vector2.zero);
            mapMarksRt = UIFactory.Stretch("Marks", mapContent);
            mapMarksGroup = mapMarksRt.gameObject.AddComponent<CanvasGroup>();
            mapReticleImg = UIFactory.Centered("Cursor", mapMarksRt, new Color(UIFactory.Gold.r, UIFactory.Gold.g, UIFactory.Gold.b, 0.8f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(46f, 46f), UISprites.Ring);
            mapReticle = mapReticleImg.rectTransform;
            mapRingImg = UIFactory.Centered("KaitoRing", mapMarksRt, UIFactory.Gold, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(60f, 60f), UISprites.Ring);
            mapKaitoRing = mapRingImg.rectTransform;
            mapKaitoImg = UIFactory.Centered("Kaito", mapMarksRt, Color.white, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(48f, 48f), UISprites.Get("MapKaito"));
            mapKaito = mapKaitoImg.rectTransform;

            var rod = UISprites.Get("MapRod");
            mapRodL = UIFactory.Sliced("RodL", mapRoot, rod, Color.white, MapRodW * 4f).rectTransform;
            mapRodR = UIFactory.Sliced("RodR", mapRoot, rod, Color.white, MapRodW * 4f).rectTransform;
            foreach (var r in new[] { mapRodL, mapRodR })
            {
                Place(r, new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(MapRodW, 100f));
                r.pivot = new Vector2(0.5f, 0.5f);
                // el 9-slice escala por el ancho (la varilla es angosta): sus puntas doradas no se estiran
                var ri = r.GetComponent<Image>();
                if (rod != null) ri.pixelsPerUnitMultiplier = rod.rect.width / MapRodW;
            }

            // ---- el nombre de lo que está bajo el cursor (fuera del recorte: no se corta contra las varillas)
            mapTip = UIFactory.Rect("Tip", mapRoot, new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f), Vector2.zero, new Vector2(300f, 90f));
            mapTipGroup = mapTip.gameObject.AddComponent<CanvasGroup>();
            mapTipGroup.alpha = 0f;
            mapTipGroup.blocksRaycasts = false;
            mapSwash = UIFactory.Banner("Swash", mapTip, new Color(0.043f, 0.039f, 0.051f, 0.9f)).rectTransform;
            mapTipTitle = UIFactory.Legible(UIFactory.NoWrap(UIFactory.Text("Title", mapTip, "", 26f, UIFactory.Paper, new Vector2(0.5f, 0.5f), new Vector2(0f, 13f), new Vector2(600f, 36f), TextAlignmentOptions.Center, true)));
            mapTipSub = UIFactory.Legible(UIFactory.NoWrap(UIFactory.Text("Sub", mapTip, "", 20f, UIFactory.Gold, new Vector2(0.5f, 0.5f), new Vector2(0f, -18f), new Vector2(600f, 28f), TextAlignmentOptions.Center)));
            foreach (var t in new[] { mapTipTitle, mapTipSub }) t.rectTransform.pivot = new Vector2(0.5f, 0.5f);

            // la lámina pesa ~10 MB (BC7 con mips): se carga de a poco desde ya (la primera M no traba el cuadro); en el menú no hace falta
            if (MapFog.Ready && SceneManager.GetActiveScene().name != "Menu") mapTexRequest = Resources.LoadAsync<Texture2D>("UI/WorldMap");
            mapRoot.gameObject.SetActive(false);
        }

        TextMeshProUGUI MapText(string name, Transform parent, float size, Color c, Vector2 pos, bool title)
        {
            var t = UIFactory.NoWrap(UIFactory.Text(name, parent, "", size, c, new Vector2(0f, 1f), pos, new Vector2(520f, size * 1.6f), TextAlignmentOptions.Left, title));
            t.rectTransform.pivot = new Vector2(0f, 0.5f);
            return UIFactory.Legible(t);
        }

        void MapLegendRow(Transform parent, float dy, string sprite, Color tint, string label, bool glow)
        {
            float y = -690f - dy;
            if (glow) UIFactory.Centered("Glow", parent, new Color(1f, 0.77f, 0.31f, 0.75f), new Vector2(0f, 1f), new Vector2(130f, y), new Vector2(54f, 54f), UISprites.SoftDot);
            UIFactory.Centered("Icon", parent, tint, new Vector2(0f, 1f), new Vector2(130f, y), new Vector2(34f, 34f), UISprites.Get(sprite));
            MapText("Legend", parent, 24f, MapLegendText, new Vector2(164f, y), false).text = label;
        }

        // SaveData.shrines (los santuarios donde Kaito ya rezó con incienso) lo agrega el frente del rezo
        // (World/ShrineIncense, StoryDirector.Shrines). Se lee por reflexión para que el mapa compile y funcione sin
        // ese cambio: sin el campo, todo santuario descubierto se ve rezado y la leyenda no tiene "Sin rezar". Con los
        // dos en main se puede cambiar por Game.Save.shrines. Solo se consulta al abrir el mapa, nunca por cuadro.
        static readonly System.Reflection.FieldInfo MapShrinesField = typeof(SaveData).GetField("shrines");

        static bool MapShrinePrayed(SaveData save, string id)
        {
            if (MapShrinesField == null) return true;
            return MapShrinesField.GetValue(save) is List<string> prayed && prayed.Contains(id);
        }

        /// <summary>Lo que depende del mundo (santuarios, jefes, portales, zonas, la lámina y su material): la primera vez
        /// que se abre, con el mundo ya armado.</summary>
        void BuildMapContent()
        {
            mapContentBuilt = true;
            var data = MapFog.Data;
            var tex = mapTexRequest != null ? mapTexRequest.asset as Texture2D : Resources.Load<Texture2D>("UI/WorldMap");
            mapImage.texture = tex;
            int fw = MapFog.TextureWidth, fh = MapFog.TextureHeight;
            mapFogTex = MapFogTexture(fw, fh);
            mapFogPrevTex = MapFogTexture(fw, fh);
            mapFogBytes = new byte[fw * fh];
            mapFogPrevBytes = new byte[fw * fh];
            var sh = Resources.Load<Shader>("Shaders/NindoUIMap");
            if (sh != null && sh.isSupported)
            {
                mapMat = new Material(sh) { name = "Mapa (niebla)" };
                mapMat.SetTexture("_FogTex", mapFogTex);
                mapMat.SetTexture("_FogPrev", mapFogPrevTex);
                mapMat.SetTexture("_MistTex", Resources.Load<Texture2D>("UI/WorldMapMist"));
                mapMat.SetVector("_SheetM", new Vector4(data.SizeX, data.SizeZ, 0f, 0f));
                if (data.mistTile != null && data.mistTile.Length >= 3) mapMat.SetVector("_MistTile", new Vector4(data.mistTile[0], data.mistTile[1], data.mistTile[2], 0f));
                mapMat.SetColor("_FogLight", MapFogLight);
                mapMat.SetColor("_FogDark", MapFogDark);
                mapMat.SetColor("_Kasumi", MapKasumi);
                mapMat.SetColor("_Tide", MapTide);
                mapImage.material = mapMat;
            }
            else
            {
                // sin el shader (no compiló): la niebla como una capa de tinta encima, sin el borde ni las nubes
                Debug.LogWarning("[Nindo] Sin el shader Nindo/UI Map: el mapa muestra la niebla lisa.");
                var go = new GameObject("FogFallback", typeof(RectTransform), typeof(RawImage));
                go.transform.SetParent(mapContent, false);
                go.transform.SetSiblingIndex(1);
                mapFogFallback = go.GetComponent<RawImage>();
                mapFogFallback.texture = mapFogTex;
                mapFogFallback.color = new Color(MapFogDark.r, MapFogDark.g, MapFogDark.b, 0.96f);
                mapFogFallback.raycastTarget = false;
                mapFogFallback.rectTransform.Fill(Vector2.zero, Vector2.zero);
            }

            // nombres de las zonas: el título de cada Zone (StoryText) donde lo ubicó la lámina
            var zones = Object.FindObjectsByType<Zone>(FindObjectsSortMode.None);
            if (data.labels != null)
                foreach (var l in data.labels)
                {
                    string title = null;
                    foreach (var z in zones) if (z.id == l.id) { title = z.title; break; }
                    if (string.IsNullOrEmpty(title)) continue;
                    var t = UIFactory.NoWrap(UIFactory.Text("Label_" + l.id, mapMarksRt, title, l.small != 0 ? 22f : 29f, UIFactory.Paper,
                        l.align < 0 ? TextAlignmentOptions.Right : l.align > 0 ? TextAlignmentOptions.Left : TextAlignmentOptions.Center, true));
                    var rt = t.rectTransform;
                    rt.anchorMin = rt.anchorMax = new Vector2(0.5f, 0.5f);
                    rt.pivot = new Vector2(l.align < 0 ? 1f : l.align > 0 ? 0f : 0.5f, 0.5f);
                    rt.sizeDelta = new Vector2(640f, 48f);
                    rt.anchoredPosition = MapPoint(new Vector3(l.x, 0f, l.z));
                    rt.localRotation = Quaternion.Euler(0f, 0f, l.rot);
                    UIFactory.Legible(t);
                    t.gameObject.SetActive(false);
                    mapLabels.Add((t, l.id));
                    mapLabelFresh.Add(false);
                }
            // santuarios, guardianes y portales (debajo de Kaito, encima de los nombres)
            foreach (var cp in Object.FindObjectsByType<Checkpoint>(FindObjectsSortMode.None))
            {
                // el brillo del de reaparición va debajo del torii (un hijo se dibujaría encima)
                var glow = UIFactory.Centered("Glow", mapMarksRt, new Color(1f, 0.77f, 0.31f, 0f), new Vector2(0.5f, 0.5f), MapPoint(cp.transform.position), new Vector2(64f, 64f), UISprites.SoftDot);
                var m = NewMark(cp.transform.position, UISprites.Get("MapShrine"), 27f, MapShrineRed);
                m.cp = cp;
                m.glow = glow;
            }
            if (Game.World != null)
                foreach (var a in Game.World.Arenas)
                    if (a != null) NewMark(a.transform.position, UISprites.Hanko("IconBoss"), 44f, Color.white).arena = a;
            foreach (var p in Object.FindObjectsByType<Portal>(FindObjectsSortMode.None))
                NewMark(p.transform.position, UISprites.Get("MapPortal"), 30f, MapPortalJade).portal = p;
            mapReticle.SetAsLastSibling();
            mapKaitoRing.SetAsLastSibling();
            mapKaito.SetAsLastSibling();
        }

        /// <summary>
        /// Las marcas que se ven no se pisan: un portal o un santuario al lado de la arena de un jefe (el portal de la
        /// cascada queda a 7 m de Mizuchi, 15 px a zoom 1) se corre lo justo para que se lean los dos. El sello del
        /// jefe no se mueve. El corrimiento está en unidades de la lámina a zoom 1 y se aplica por zoom^-0.7, como el
        /// tamaño de las marcas: al acercar se separan solas y vuelven a su lugar. Al abrir y al cambiar el tamaño.
        /// </summary>
        void DeclutterMarks()
        {
            foreach (var m in mapMarks) m.nudge = Vector2.zero;
            for (int it = 0; it < 24; it++)
                for (int i = 0; i < mapMarks.Count; i++)
                {
                    var a = mapMarks[i];
                    if (!a.shown) continue;
                    for (int j = i + 1; j < mapMarks.Count; j++)
                    {
                        var b = mapMarks[j];
                        if (!b.shown) continue;
                        float wa = a.arena != null ? 0f : 1f, wb = b.arena != null ? 0f : 1f;
                        if (wa + wb <= 0f) continue;
                        Vector2 d = b.at + b.nudge - a.at - a.nudge;
                        // el dibujo ocupa ~85 % de su cuadro (el resto es el margen del contorno)
                        float need = (a.rt.sizeDelta.x + b.rt.sizeDelta.x) * 0.5f * 0.85f + 2f, dist = d.magnitude;
                        if (dist >= need) continue;
                        Vector2 dir = dist > 1e-3f ? d / dist : Vector2.up;
                        float push = (need - dist) / (wa + wb);
                        a.nudge -= dir * (push * wa);
                        b.nudge += dir * (push * wb);
                    }
                }
        }

        static Texture2D MapFogTexture(int w, int h)
        {
            return new Texture2D(w, h, TextureFormat.Alpha8, false, true) { name = "Niebla del mapa", filterMode = FilterMode.Bilinear, wrapMode = TextureWrapMode.Clamp };
        }

        MapMark NewMark(Vector3 world, Sprite sprite, float size, Color tint)
        {
            var img = UIFactory.Centered("Mark", mapMarksRt, tint, new Vector2(0.5f, 0.5f), MapPoint(world), new Vector2(size, size), sprite);
            var m = new MapMark { rt = img.rectTransform, img = img, world = world, at = img.rectTransform.anchoredPosition };
            mapMarks.Add(m);
            return m;
        }

        /// <summary>Del mundo al contenido de la lámina (unidades del canvas a zoom 1, el centro de la lámina en 0).</summary>
        Vector2 MapPoint(Vector3 p)
        {
            var d = MapFog.Data;
            if (d == null) return Vector2.zero;
            Vector2 uv = d.ToUV(p);
            return new Vector2((uv.x - 0.5f) * mapSheetW, (uv.y - 0.5f) * mapSheetH);
        }

        /// <summary>La lámina entra a la derecha de la columna, lo más grande que dé sin deformarse (16:9, 21:9, 4:3...).</summary>
        void LayoutMap()
        {
            var d = MapFog.Data;
            float W = root.rect.width, H = root.rect.height;
            mapRootSize = new Vector2(W, H);
            float aw = W - MapColX - MapPadR - 2f * MapRodGap, ah = H - 2f * MapPadV;
            float asp = d.SizeX / d.SizeZ;
            float oldW = mapSheetW;
            mapSheetW = Mathf.Max(200f, Mathf.Min(aw, ah * asp));
            mapSheetH = mapSheetW / asp;
            // en 21:9 o más ancho, al centro de la pantalla (centrada en lo que deja la columna quedaba corrida a la
            // derecha con un hueco negro de 300 px contra la columna); si no entra, pegada a la columna
            float cx = Mathf.Clamp(W * 0.5f, MapColX + MapRodGap + mapSheetW * 0.5f, W - MapPadR - MapRodGap - mapSheetW * 0.5f) - W * 0.5f;
            mapView.anchoredPosition = new Vector2(cx, 0f);
            mapContent.sizeDelta = new Vector2(mapSheetW, mapSheetH);
            // lo que vive en el contenido se reubica con la nueva escala (los nombres y las marcas no cambian de tamaño)
            float k = mapSheetW / Mathf.Max(1f, oldW);
            foreach (var m in mapMarks) m.at = MapPoint(m.world);
            DeclutterMarks();
            if (mapContentBuilt && MapFog.Data.labels != null)
                foreach (var (text, zone) in mapLabels)
                    foreach (var l in MapFog.Data.labels)
                        if (l.id == zone) { text.rectTransform.anchoredPosition = MapPoint(new Vector3(l.x, 0f, l.z)); break; }
            mapPan *= k; mapPanT *= k; mapCursor *= k;
            SizeColumn(mapColumn);
            float hy = 66f;
            LayoutMapHints(hy);
        }

        // ================================================================== abrir y cerrar
        bool CanOpenMap()
        {
            if (!MapFog.Ready || SceneManager.GetActiveScene().name == "Menu") return false;
            // de los menús, solo desde la pausa: en Opciones (y su página de controles, que espera una tecla) la M es otra cosa
            if (PauseOpen && !pausePanel.activeSelf) return false;
            if (Game.InCutscene || DialogueOpen || deathPanel.activeSelf || endPanel.activeSelf) return false;
            return Game.Player != null && Game.Player.IsAlive && Game.World != null && Game.World.Built;
        }

        /// <param name="fromPause">Se abrió desde la pausa: al cerrarlo se vuelve a ella (el juego sigue en pausa).</param>
        public void OpenMap(bool fromPause)
        {
            if (MapOpen || !CanOpenMap()) return;
            if (!mapContentBuilt) BuildMapContent();
            mapFromPause = fromPause || pausePanel.activeSelf;
            if (pausePanel.activeSelf) pausePanel.SetActive(false);
            Game.Time?.SetPaused(true);
            if (Game.Input != null) { Game.Input.GameplayBlocked = true; Game.Input.ClearBuffer(); }
            EventSystem.current?.SetSelectedGameObject(null);
            Cursor.visible = true; Cursor.lockState = CursorLockMode.None;
            mapRoot.gameObject.SetActive(true);
            mapRoot.SetAsLastSibling();
            LayoutMap();
            mapT = 0f; mapClosing = false; mapCloseT = 0f;
            // el primer cuadro ya enrollado y transparente (si se abrió con el clic de la pausa, este cuadro ya pasó por UpdateMap)
            mapGroup.alpha = 0f; mapColumn.fillAmount = 0f; mapInfoGroup.alpha = 0f; mapMarksGroup.alpha = 0f;
            ApplyMapUnroll(0f);
            mapTipMark = null; mapTipGroup.alpha = 0f;
            mapCursorMoved = false; mapMouseMode = false;
            mapLastMouse = MapMouseScreen();
#if ENABLE_INPUT_SYSTEM
            var kb = Keyboard.current;
            if (kb != null)
            {
                mapPlusKey = kb.FindKeyOnCurrentKeyboardLayout("+") ?? kb.equalsKey;
                mapMinusKey = kb.FindKeyOnCurrentKeyboardLayout("-") ?? kb.minusKey;
            }
#endif
            // la niebla: lo de ahora y lo de la última vez que se cerró (lo nuevo se despeja al abrir)
            if (MapFog.Version != mapFogVersion)
            {
                mapFogVersion = MapFog.Version;
                MapFog.FillTexture(mapFogBytes);
                mapFogTex.LoadRawTextureData(mapFogBytes);
                mapFogTex.Apply(false, false);
            }
            if (mapFirstOpen) { System.Array.Copy(mapFogBytes, mapFogPrevBytes, mapFogBytes.Length); mapFirstOpen = false; }
            mapFogPrevTex.LoadRawTextureData(mapFogPrevBytes);
            mapFogPrevTex.Apply(false, false);
            if (mapMat != null) mapMat.SetFloat("_Reveal", 0f);
            // centrado en Kaito con el zoom de la última vez (el primero, la lámina entera)
            mapCursor = KaitoMapPoint();
            mapZoom = mapZoomT;
            mapPanT = mapPan = ClampPan(mapCursor, mapZoom);
            RefreshMap();
            ApplyMapView();
            Game.Save.SetFlag(MapHintFlag);
            Game.Audio?.Play("ui_open", null, 0.5f);
        }

        public void CloseMap()
        {
            if (!MapOpen || mapClosing) return;
            mapClosing = true; mapCloseT = 0f;
            System.Array.Copy(mapFogBytes, mapFogPrevBytes, mapFogBytes.Length);
            Game.Audio?.Play("ui_close", null, 0.5f);
        }

        void FinishCloseMap()
        {
            mapRoot.gameObject.SetActive(false);
            mapClosing = false;
            if (mapFromPause)
            {
                pausePanel.SetActive(true);
                pauseOpenT = 0.5f;
                var item = pausePanel.transform.Find("Mapa");
                Select(item != null ? item.GetComponent<Selectable>() : pauseFirst);
                return;
            }
            Game.Time?.SetPaused(false);
            if (Game.Input != null) { Game.Input.GameplayBlocked = Game.InCutscene; Game.Input.ClearBuffer(); }
            Cursor.visible = false;
        }

        /// <summary>Lo que cambia entre aperturas: qué se ve, el santuario de reaparición, los jefes, el lugar, los sellos.</summary>
        void RefreshMap()
        {
            var save = Game.Save;
            foreach (var m in mapMarks)
            {
                bool seen = MapFog.IsRevealed(m.world);
                if (m.cp != null)
                {
                    bool cur = save.checkpoint == m.cp.id;
                    m.rt.sizeDelta = Vector2.one * (cur ? 34f : 27f);
                    if (m.glow != null) m.glow.color = new Color(1f, 0.77f, 0.31f, cur ? 0.75f : 0f);
                    // bermellón donde ya rezó; el resto, la madera sin laca (UpdateMapMarks pone el alfa)
                    m.img.color = MapShrinePrayed(save, m.cp.id) ? MapShrineRed : MapShrineBare;
                    m.shown = seen;
                }
                else if (m.arena != null)
                {
                    bool done = save.HasFlag(Flags.Boss(m.arena.archetype));
                    string icon = !done ? "IconBoss" : EnemyFactory.BossSeal(m.arena.archetype, out var seal) ? UISprites.SealIconName(seal) : "ZoneMoon";
                    m.img.sprite = UISprites.Hanko(icon);
                    m.rt.localRotation = Quaternion.Euler(0f, 0f, -6f);
                    m.shown = seen;
                }
                else if (m.portal != null)
                    m.shown = seen && (string.IsNullOrEmpty(m.portal.requiredFlag) || save.HasFlag(m.portal.requiredFlag));
                m.fresh = m.shown && FoggedAtLastClose(m.world);
                if (m.rt.gameObject.activeSelf != m.shown) m.rt.gameObject.SetActive(m.shown);
                if (m.glow != null) m.glow.gameObject.SetActive(m.shown && save.checkpoint == m.cp.id);
            }
            DeclutterMarks();
            for (int i = 0; i < mapLabels.Count; i++)
            {
                var (text, zone) = mapLabels[i];
                bool on = save.HasFlag("zone_" + zone) || (zone == "hogar" && save.HasFlag(Flags.IntroDone));
                mapLabelFresh[i] = on && !text.gameObject.activeSelf && !mapFirstShown;
                if (text.gameObject.activeSelf != on) text.gameObject.SetActive(on);
            }
            mapFirstShown = false;
            var z = Zone.Current;
            mapZoneTitle.text = z != null ? z.title : "";
            mapZoneSub.text = z != null ? z.subtitle : "";
            string zi = z != null ? (UISprites.ZoneIconName(z.id) ?? (z.id.StartsWith("lago") ? "ZoneLake" : "ZoneMoon")) : null;
            mapZoneHanko.sprite = UISprites.Hanko(zi);
            mapZoneHanko.enabled = mapZoneHanko.sprite != null;
            for (int i = 0; i < 3; i++)
            {
                // el sello que falta, apagado: la tinta del hanko sin su rojo
                bool got = save.HasSeal((SealId)i);
                mapSeals[i].color = got ? Color.white : new Color(0.3f, 0.29f, 0.32f, 0.8f);
            }
            mapSealCount.text = save.SealCount + "/3";
            int pct = Mathf.FloorToInt(MapFog.ExploredFraction * 100f + 0.5f);
            mapExplored.text = pct + " %";
            RefreshMapHints();
        }

        // ================================================================== teclas de la columna
        void RefreshMapHints()
        {
            var input = Game.Input;
            if (input == null || mapHintVersion == input.GlyphVersion) return;
            mapHintVersion = input.GlyphVersion;
            bool pad = input.GlyphFamily != 0;
            SetMapHint(0, input.Glyph(Act.Map), "Cerrar");
            SetMapHint(1, input.Glyph(Act.Lock), "Centrar");
            // los gatillos se leen directo (MapControls), no por la acción que tengan asignada en el juego
            bool ps = input.GlyphFamily == 2;
            SetMapHint(2, pad ? (ps ? "R2" : "RT") : "Rueda", "Acercar");
            SetMapHint(3, pad ? (ps ? "L2" : "LT") : null, "Alejar");
            SetMapHint(4, pad ? "Stick izq." : "WASD", "Mover");
            LayoutMapHints(66f);
        }

        void SetMapHint(int i, string glyph, string label)
        {
            bool on = glyph != null;
            mapHintKeys[i].gameObject.SetActive(on);
            mapHintLabels[i].gameObject.SetActive(on);
            if (!on) return;
            UIFactory.SetKeyCap(mapHintKeys[i], glyph);
            mapHintLabels[i].text = label;
        }

        /// <summary>Renglones de teclas abajo de la columna: [tecla] acción, dos por renglón, desde abajo.</summary>
        void LayoutMapHints(float bottom)
        {
            // renglones: (0 1) (2 3) (4); el de abajo es el último que tiene algo
            int[][] rows = { new[] { 0, 1 }, new[] { 2, 3 }, new[] { 4 } };
            int visibleRows = 0;
            foreach (var r in rows) foreach (int i in r) if (mapHintKeys[i] != null && mapHintKeys[i].gameObject.activeSelf) { visibleRows++; break; }
            int row = 0;
            foreach (var r in rows)
            {
                bool any = false;
                float x = 110f, y = bottom + (visibleRows - 1 - row) * 48f;
                foreach (int i in r)
                {
                    var key = mapHintKeys[i];
                    if (key == null || !key.gameObject.activeSelf) continue;
                    any = true;
                    float w = key.sizeDelta.x;
                    key.anchoredPosition = new Vector2(x + w * 0.5f, y);
                    x += w + 10f;
                    var lab = mapHintLabels[i];
                    lab.rectTransform.anchoredPosition = new Vector2(x, y);
                    x += lab.GetPreferredValues(lab.text, 9999f, 40f).x + 26f;
                }
                if (any) row++;
            }
        }

        // ================================================================== cuadro a cuadro
        void UpdateMap(float dt)
        {
            if (!MapOpen)
            {
                // Kaito descubre lo que recorre (también con el mapa cerrado: es lo único que hace siempre)
                var p = Game.Player;
                if (p != null && Game.World != null && Game.World.Built) MapFog.Tick(p.transform.position);
                MapHint(dt);
                var input = Game.Input;
                if (input != null && input.Pressed(Act.Map) && CanOpenMap())
                {
                    OpenMap(pausePanel.activeSelf);
                    if (!MapOpen) return;
                }
                else return;
            }
            UpdateMapOpen(dt);
            // nada más lee teclas este cuadro: Esc no abre la pausa debajo, B no esquiva al volver
            Game.Input?.ClearBuffer();
        }

        /// <summary>Una vez por partida, al llegar a los campos (ya hay algo para ver): cómo se abre el mapa.</summary>
        void MapHint(float dt)
        {
            mapHintPoll -= dt;
            if (mapHintPoll > 0f) return;
            mapHintPoll = 0.5f;
            var s = Game.Save;
            if (Game.Player == null || Game.World == null || !Game.World.Built) return;   // en el menú la partida también está cargada
            if (s.HasFlag(MapHintFlag) || !s.HasFlag("zone_campos") || Game.InCutscene || PauseOpen || DialogueOpen || !MapFog.Ready) return;
            s.SetFlag(MapHintFlag);
            ShowToast("Mapa", UIFactory.RichKeys("Apretá {Map} para ver lo que recorriste"), UIFactory.Gold, 3.5f);
        }

        void UpdateMapOpen(float dt)
        {
            if (root.rect.size != mapRootSize) LayoutMap();
            var input = Game.Input;
            float open;
            if (mapClosing)
            {
                mapCloseT += dt;
                open = 1f - UIAnim.InCubic(mapCloseT / MapRoll);
                mapGroup.alpha = 1f - Mathf.Clamp01((mapCloseT - 0.12f) / 0.14f);
                mapColumn.fillAmount = 1f - UIAnim.InCubic(mapCloseT / MapRoll);
                mapMarksGroup.alpha = Mathf.MoveTowards(mapMarksGroup.alpha, 0f, dt / 0.08f);
                mapInfoGroup.alpha = Mathf.MoveTowards(mapInfoGroup.alpha, 0f, dt / 0.1f);
                mapTipGroup.alpha = 0f;
                ApplyMapUnroll(Mathf.Clamp01(open));
                if (mapCloseT >= MapRoll + 0.04f) FinishCloseMap();
                return;
            }
            mapT += dt;
            open = UIAnim.OutCubic((mapT - 0.04f) / MapUnroll);
            mapGroup.alpha = Mathf.Clamp01(mapT / 0.15f);
            mapColumn.fillAmount = UIAnim.OutCubic(mapT / 0.2f);
            mapInfoGroup.alpha = UIAnim.OutCubic((mapT - 0.12f) / 0.2f);
            mapMarksGroup.alpha = UIAnim.OutCubic((mapT - 0.32f) / 0.2f);
            ApplyMapUnroll(open);
            if (mapMat != null)
            {
                mapMat.SetFloat("_T", Time.unscaledTime);
                mapMat.SetFloat("_Reveal", UIAnim.InOutSine((mapT - MapRevealAt) / MapRevealDur));
            }
            if (input != null && mapT > 0.1f && (input.Pressed(Act.Map) || input.Pressed(Act.Cancel) || input.Pressed(Act.Pause))) { CloseMap(); return; }
            MapControls(dt, input);
            ApplyMapView();
            UpdateMapMarks(dt);
            RefreshMapHints();
        }

        void ApplyMapUnroll(float open)
        {
            float vw = Mathf.Max(0f, mapSheetW * open);
            mapView.sizeDelta = new Vector2(vw, mapSheetH + 2f * MapSoft);
            float x = mapView.anchoredPosition.x, rodX = vw * 0.5f + 4f;
            mapRodL.anchoredPosition = new Vector2(x - rodX, 0f);
            mapRodR.anchoredPosition = new Vector2(x + rodX, 0f);
            mapRodL.sizeDelta = mapRodR.sizeDelta = new Vector2(MapRodW, mapSheetH + 56f);
            mapShadow.anchoredPosition = new Vector2(x + 10f, -14f);
            mapShadow.sizeDelta = new Vector2(vw + 90f, mapSheetH + 100f);
        }

        // ---- mover, acercar, centrar
        Vector2 KaitoMapPoint() => Game.Player != null ? MapPoint(Game.Player.transform.position) : Vector2.zero;

        Vector2 ClampPan(Vector2 pan, float zoom)
        {
            Vector2 lim = new Vector2(mapSheetW, mapSheetH) * 0.5f * (1f - 1f / zoom);
            return new Vector2(Mathf.Clamp(pan.x, -lim.x, lim.x), Mathf.Clamp(pan.y, -lim.y, lim.y));
        }

        Vector2 MapMouseScreen()
        {
#if ENABLE_INPUT_SYSTEM
            return Mouse.current != null ? Mouse.current.position.ReadValue() : Vector2.zero;
#elif ENABLE_LEGACY_INPUT_MANAGER
            return Input.mousePosition;
#else
            return Vector2.zero;
#endif
        }

        void MapControls(float dt, InputReader input)
        {
            float zoomIn = 0f, zoomOut = 0f, wheel = 0f;
            bool drag = false;
            Vector2 mouse = MapMouseScreen();
#if ENABLE_INPUT_SYSTEM
            var m = Mouse.current;
            if (m != null)
            {
                wheel = m.scroll.ReadValue().y;
                drag = m.leftButton.isPressed;
            }
            var kb = Keyboard.current;
            if (kb != null)
            {
                if ((mapPlusKey != null && mapPlusKey.isPressed) || kb.numpadPlusKey.isPressed) zoomIn += 1f;
                if ((mapMinusKey != null && mapMinusKey.isPressed) || kb.numpadMinusKey.isPressed) zoomOut += 1f;
            }
            var pad = Gamepad.current;
            if (pad != null)
            {
                zoomIn += pad.rightTrigger.ReadValue();
                zoomOut += pad.leftTrigger.ReadValue();
                float ry = pad.rightStick.ReadValue().y;
                if (Mathf.Abs(ry) > 0.25f) { if (ry > 0f) zoomIn += ry; else zoomOut -= ry; }
            }
#elif ENABLE_LEGACY_INPUT_MANAGER
            wheel = Input.mouseScrollDelta.y;
            drag = Input.GetMouseButton(0);
            if (Input.GetKey(KeyCode.Equals) || Input.GetKey(KeyCode.KeypadPlus)) zoomIn += 1f;
            if (Input.GetKey(KeyCode.Minus) || Input.GetKey(KeyCode.KeypadMinus)) zoomOut += 1f;
#endif
            float scale = root.localScale.x > 0f ? root.localScale.x : 1f;   // píxeles de pantalla por unidad del canvas
            Vector2 mouseDelta = mouse - mapLastMouse;
            mapLastMouse = mouse;
            if (mouseDelta.sqrMagnitude > 1f || Mathf.Abs(wheel) > 0.01f || drag) mapMouseMode = true;
            Vector2 mouseMap = mapPan;
            mapMouseOver = false;
            if (RectTransformUtility.ScreenPointToLocalPointInRectangle(mapView, mouse, null, out var local))
            {
                mouseMap = mapPan + local / mapZoom;
                mapMouseOver = mapView.rect.Contains(local);   // sobre la columna no se nombra lo que quedó recortado
            }

            // stick, WASD y flechas: un cursor que recorre la lámina (la vista lo sigue cuando se acerca al borde)
            Vector2 move = input != null ? input.Move : Vector2.zero;
            if (move.sqrMagnitude > 0.04f)
            {
                mapMouseMode = false;
                mapCursorMoved = true;
                mapCursor += move * (mapSheetH * 0.6f * dt / mapZoom);
                Vector2 half = new Vector2(mapSheetW, mapSheetH) * 0.5f;
                mapCursor = new Vector2(Mathf.Clamp(mapCursor.x, -half.x, half.x), Mathf.Clamp(mapCursor.y, -half.y, half.y));
                Vector2 inner = half * 0.62f;
                Vector2 rel = (mapCursor - mapPanT) * mapZoom;
                rel = new Vector2(Mathf.Clamp(rel.x, -inner.x, inner.x), Mathf.Clamp(rel.y, -inner.y, inner.y));
                mapPanT = mapCursor - rel / mapZoom;
            }
            if (mapMouseMode)
            {
                mapCursor = mouseMap;
                // arrastrar con el mouse mueve la lámina con la mano (sin el suavizado: si no, se "despega")
                if (drag && mouseDelta.sqrMagnitude > 0f)
                {
                    Vector2 dm = mouseDelta / (scale * mapZoom);
                    mapPan -= dm; mapPanT -= dm;
                }
            }
            if (input != null && input.Pressed(Act.Lock))
            {
                mapCursor = KaitoMapPoint();
                mapCursorMoved = false;
                mapZoomT = Mathf.Max(mapZoomT, MapCenterZoom);
                mapPanT = mapCursor;
            }

            // acercar: alrededor del cursor (o de donde está el mouse)
            if (Mathf.Abs(wheel) > 0.01f)
            {
                float notches = Mathf.Abs(wheel) > 10f ? wheel / 120f : wheel;   // según la versión del Input System, 120 o 1 por muesca
                mapZoomT *= Mathf.Pow(1.25f, Mathf.Clamp(notches, -3f, 3f));
            }
            mapZoomT *= Mathf.Exp((zoomIn - zoomOut) * 1.6f * dt);
            mapZoomT = Mathf.Clamp(mapZoomT, 1f, MapMaxZoom);
            float z0 = mapZoom;
            float z1 = Mathf.Lerp(mapZoom, mapZoomT, 1f - Mathf.Exp(-dt * 14f));
            if (Mathf.Abs(z1 - z0) > 1e-5f)
            {
                Vector2 a = mapMouseMode ? mouseMap : mapCursor;
                mapPan = a - (a - mapPan) * (z0 / z1);
                mapPanT = a - (a - mapPanT) * (z0 / z1);
                mapZoom = z1;
            }
            mapPanT = ClampPan(mapPanT, mapZoomT);
            mapPan = ClampPan(Vector2.Lerp(mapPan, mapPanT, 1f - Mathf.Exp(-dt * 16f)), mapZoom);
        }

        void ApplyMapView()
        {
            mapContent.localScale = new Vector3(mapZoom, mapZoom, 1f);
            mapContent.anchoredPosition = -mapPan * mapZoom;
        }

        // ---- marcas: Kaito, cursor, nombres que no crecen con el zoom y el cartel de lo que está bajo el cursor
        void UpdateMapMarks(float dt)
        {
            float t = Time.unscaledTime;
            float inv = Mathf.Pow(mapZoom, -0.7f);   // al acercar crecen un poco, no al ritmo de la lámina
            var s = new Vector3(inv, inv, 1f);
            // lo nuevo entra cuando la niebla de alrededor ya se abrió
            float freshA = UIAnim.OutCubic((mapT - MapRevealAt - 0.45f) / 0.35f);
            foreach (var m in mapMarks)
                if (m.shown)
                {
                    m.rt.localScale = s;
                    m.rt.anchoredPosition = m.at + m.nudge * inv;
                    if (m.glow != null) { m.glow.rectTransform.localScale = s; m.glow.rectTransform.anchoredPosition = m.rt.anchoredPosition; }
                    var c = m.img.color;
                    float a = m.fresh ? freshA : 1f;
                    if (c.a != a) { c.a = a; m.img.color = c; }
                }
            for (int i = 0; i < mapLabels.Count; i++)
            {
                var text = mapLabels[i].text;
                text.rectTransform.localScale = s;
                float a = mapLabelFresh[i] ? freshA : 1f;
                if (text.alpha != a) text.alpha = a;
            }

            var p = Game.Player;
            if (p != null)
            {
                mapKaito.anchoredPosition = mapKaitoRing.anchoredPosition = KaitoMapPoint();
                Vector3 f = p.transform.forward;
                float yaw = Mathf.Atan2(f.x, f.z) * Mathf.Rad2Deg;
                mapKaito.localRotation = Quaternion.Euler(0f, 0f, -yaw);
                float pop = UIAnim.Pop(mapT - 0.42f, 0.32f, 0.3f, 1.3f);
                mapKaito.localScale = s * (mapT < 0.42f ? 0f : pop);
                // un ensō que late debajo: se encuentra a Kaito de un vistazo
                float ph = Mathf.Repeat(t * 0.8f, 1f);
                mapKaitoRing.localScale = s * Mathf.Lerp(0.7f, 1.35f, ph);
                mapRingImg.color = new Color(UIFactory.Gold.r, UIFactory.Gold.g, UIFactory.Gold.b, 0.7f * (1f - ph));
            }
            if (mapKaito.gameObject.activeSelf != (p != null)) { mapKaito.gameObject.SetActive(p != null); mapKaitoRing.gameObject.SetActive(p != null); }

            // el brillo del santuario de reaparición respira
            foreach (var m in mapMarks)
                if (m.shown && m.cp != null && m.glow != null && Game.Save.checkpoint == m.cp.id)
                    m.glow.color = new Color(1f, 0.77f, 0.31f, (0.55f + 0.25f * Mathf.Sin(t * 2.4f)) * (m.fresh ? freshA : 1f));

            bool reticle = !mapMouseMode && mapCursorMoved;
            if (mapReticle.gameObject.activeSelf != reticle) mapReticle.gameObject.SetActive(reticle);
            if (reticle) { mapReticle.anchoredPosition = mapCursor; mapReticle.localScale = s; }

            // el cartel: lo más cerca del cursor (a menos de ~34 px en pantalla), recién con el pergamino abierto
            MapMark best = null;
            float bestD = (mapMouseMode ? 30f : 36f) / mapZoom;
            bestD *= bestD;
            if (mapT > MapUnroll && (mapMouseMode ? mapMouseOver : mapCursorMoved))
                foreach (var m in mapMarks)
                {
                    if (!m.shown) continue;
                    float d2 = (m.rt.anchoredPosition - mapCursor).sqrMagnitude;
                    if (d2 < bestD) { bestD = d2; best = m; }
                }
            if (best != mapTipMark)
            {
                mapTipMark = best;
                if (best != null) SetMapTip(best);
            }
            mapTipGroup.alpha = Mathf.MoveTowards(mapTipGroup.alpha, best != null ? 1f : 0f, dt / 0.12f);
            if (best != null) mapTip.anchoredPosition = MapTipPosition(best);
        }

        /// <summary>
        /// Dónde va el cartel de una marca (centro del texto, en el padre de la lámina): arriba de la marca y, si ahí
        /// se saldría por arriba de la lámina, abajo (antes se pegaba al borde y tapaba lo que nombraba). De costado,
        /// adentro de la lámina: el trazo no es simétrico, 41 % de su ancho a la izquierda del texto y la cola a la
        /// derecha, que puede pasar sobre la varilla.
        /// </summary>
        Vector2 MapTipPosition(MapMark m)
        {
            Vector2 at = mapView.anchoredPosition + (m.rt.anchoredPosition - mapPan) * mapZoom;
            float half = m.rt.sizeDelta.y * 0.5f * m.rt.localScale.y * mapZoom;
            float w = mapSwash.sizeDelta.x, ink = mapTipInkH * 0.5f;
            float top = mapSheetH * 0.5f - 6f;
            float y = at.y + half + 4f + ink;
            if (y + ink > top) y = at.y - half - 4f - ink;
            float vx = mapView.anchoredPosition.x;
            float x0 = vx - mapSheetW * 0.5f + 6f + w * UIFactory.BannerLeftShare;
            float x1 = vx + mapSheetW * 0.5f - 6f - w * (UIFactory.BannerCoreEnd - UIFactory.BannerLeftShare);
            return new Vector2(Mathf.Clamp(at.x, x0, x1), y);
        }

        void SetMapTip(MapMark m)
        {
            string title = "", sub = "";
            if (m.cp != null)
            {
                title = m.cp.displayName;
                sub = Game.Save.checkpoint == m.cp.id ? "Punto de reaparición" : MapShrinePrayed(Game.Save, m.cp.id) ? "" : "Sin rezar todavía";
            }
            else if (m.arena != null)
            {
                string id = m.arena.archetype;
                bool done = Game.Save.HasFlag(Flags.Boss(id));
                bool seen = done || Game.Save.HasFlag(StoryDirector.BossSeenFlag(id));
                // vencido, su Boss no se vuelve a crear al cargar la partida: el nombre sale de su arquetipo
                title = !seen ? "Un guardián" : m.arena.Boss != null ? m.arena.Boss.title : EnemyArchetypes.Get(id).displayName;
                bool hasSeal = EnemyFactory.BossSeal(id, out var seal);
                sub = !done ? "Te espera" : !hasSeal ? "Vencido" : Game.Save.HasSeal(seal) ? UISprites.SealName(seal) : "Su sello te espera";
            }
            else if (m.portal != null) { title = "Portal al dojo"; sub = "Te lleva a la puerta del dojo"; }
            mapTipTitle.text = title;
            mapTipSub.text = sub;
            float w = Mathf.Max(mapTipTitle.GetPreferredValues(title, 9999f, 36f).x, string.IsNullOrEmpty(sub) ? 0f : mapTipSub.GetPreferredValues(sub, 9999f, 28f).x);
            bool two = !string.IsNullOrEmpty(sub);
            mapTipTitle.rectTransform.anchoredPosition = new Vector2(0f, two ? 13f : 0f);
            float contentH = two ? 62f : 34f;
            UIFactory.FitBanner(mapSwash, -w * 0.5f, w * 0.5f, 0f, contentH, 30f, 8f, false, 220f);
            mapTipInkH = contentH + 16f;   // la tinta pareja del trazo: el contenido y su margen de arriba y abajo
        }

        /// <summary>¿Esto estaba bajo la niebla la última vez que se cerró el mapa? (lo descubierto desde entonces)</summary>
        bool FoggedAtLastClose(Vector3 p)
        {
            var d = MapFog.Data;
            if (d == null || mapFogPrevBytes == null) return false;
            int gx = Mathf.FloorToInt((p.x - d.X0) / d.cell), gy = Mathf.FloorToInt((p.z - d.Z0) / d.cell);
            if (gx < 0 || gy < 0 || gx >= d.GW || gy >= d.GH) return false;
            return mapFogPrevBytes[gy * d.GW + gx] > 127;
        }
    }
}
