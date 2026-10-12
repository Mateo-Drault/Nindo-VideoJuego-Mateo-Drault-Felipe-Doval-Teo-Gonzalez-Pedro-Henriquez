using System;
using System.Globalization;
using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// Geometría y datos del mapa del mundo (Resources/UI/WorldMap.json, lo escribe Tools/UI/build_world_map.py junto
    /// con la lámina): dónde cae la lámina en el mundo, la grilla de la niebla, dónde van los nombres de las zonas, qué
    /// celdas se pueden descubrir caminando, cuáles son agua abierta, de qué lado de las puertas cae cada una y qué
    /// revela cada flag en una partida de antes del mapa. Una sola fuente: si se rehace la lámina con otro tamaño o
    /// celda, el juego lo toma de acá.
    /// </summary>
    [Serializable]
    public class WorldMapData
    {
        public int version;
        public int[] image;
        public float[] bounds;          // x0, x1, z0, z1 (m) de la lámina
        public float cell;              // lado de la celda de niebla (m)
        public int[] grid;              // columnas, filas
        public float reveal;            // radio que descubre Kaito (m)
        public float revealWater;       // hasta dónde se ve el agua abierta (m): nada la tapa
        public float[] mistK;           // cuántas veces por lámina se leen las nubes finas y las gruesas
        public int reachCount;
        public string reach;            // bits de las celdas descubribles (mismo formato que la niebla)
        public string water, north, dojo;   // bits: agua abierta; al norte de la muralla; detrás del portón del dojo
        public string[] gates;          // los flags que abren la muralla y el portón del dojo
        public Label[] labels;
        public Legacy[] legacy;

        /// <summary>Nombre de zona: dónde, alineación (-1 termina en x, 0 centrado, 1 empieza), chico, giro (grados,
        /// antihorario: la cresta de la montaña se rotula a lo largo) y el corazón de la zona (x, z): el nombre sale
        /// cuando eso ya se vio.</summary>
        [Serializable] public class Label { public string id; public float x, z, rot; public int align, small; public float[] at; }
        [Serializable] public class Legacy { public string[] flags; public float[] d; }

        public float X0 => bounds[0];
        public float Z0 => bounds[2];
        public float SizeX => bounds[1] - bounds[0];
        public float SizeZ => bounds[3] - bounds[2];
        public int GW => grid[0];
        public int GH => grid[1];

        /// <summary>Del mundo a la lámina: (0,0) la esquina suroeste, (1,1) la noreste (las uv del shader).</summary>
        public Vector2 ToUV(Vector3 p) => new Vector2((p.x - X0) / SizeX, (p.z - Z0) / SizeZ);
    }

    /// <summary>
    /// Niebla del mapa: qué celdas (de 4 m) ya vio Kaito. Caminando descubre un radio de 18 m a su alrededor (hasta la
    /// esquina de la pantalla de juego en 16:9; el radio lo dice WorldMap.json) y el agua abierta hasta 34 m, cada 2 m de recorrido; con una puerta cerrada no
    /// descubre lo que hay del otro lado (la muralla, el portón del dojo). Se guarda en la partida como bits en base64
    /// (1726 bytes: ~2.3 KB de texto en el JSON) con un prefijo que dice de qué grilla son ("2:129x107@-258,-218:"):
    /// si se rehace la lámina con otro encuadre, esos bits ya no caen en su lugar y se toman como una partida de antes
    /// del mapa. Esa no trae niebla: arranca descubierta alrededor de su santuario y de lo que sus flags prueban que
    /// ya recorrió (WorldMap.json "legacy"), así continuar a mitad del juego no abre un mapa entero en blanco.
    /// La lee la UI del mapa (UIMap.cs); SaveSystem.Save llama a Store antes de escribir.
    /// </summary>
    public static class MapFog
    {
        const float Step = 2f;          // cada cuánto recorrido se vuelve a descubrir (m)

        static WorldMapData data;
        static bool dataLoaded;
        static string prefix;           // versión y grilla de los bits guardados
        static byte[] bits, reach, water, north, dojo;
        static SaveData owner;          // la partida de la que son estos bits (cambia con Nueva partida / Continuar)
        static bool dirty, hasLast;
        static Vector3 last;
        static int[] blurA, blurB;

        /// <summary>Sube cada vez que se descubre algo (la UI vuelve a armar la textura solo entonces).</summary>
        public static int Version { get; private set; }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics()
        {
            data = null; dataLoaded = false; prefix = null; bits = reach = water = north = dojo = null; owner = null; dirty = hasLast = false;
            blurA = blurB = null; Version = 0;
        }

        public static WorldMapData Data
        {
            get
            {
                if (!dataLoaded)
                {
                    dataLoaded = true;
                    var t = Resources.Load<TextAsset>("UI/WorldMap");
                    try { data = t != null ? JsonUtility.FromJson<WorldMapData>(t.text) : null; }
                    catch (Exception e) { Debug.LogWarning("[Nindo] WorldMap.json inválido: " + e.Message); data = null; }
                    if (data != null && (data.bounds == null || data.bounds.Length < 4 || data.grid == null || data.grid.Length < 2 || data.cell <= 0f)) data = null;
                    if (data == null) Debug.LogWarning("[Nindo] Sin Resources/UI/WorldMap.json: el mapa no se puede abrir (Tools/UI/build_world_map.py).");
                    else
                    {
                        reach = Decode(data.reach, ByteCount);
                        water = Decode(data.water, ByteCount);
                        north = Decode(data.north, ByteCount);
                        dojo = Decode(data.dojo, ByteCount);
                        var inv = CultureInfo.InvariantCulture;
                        prefix = "2:" + data.GW + "x" + data.GH + "@" + data.X0.ToString(inv) + "," + data.Z0.ToString(inv) + ":";
                    }
                }
                return data;
            }
        }

        public static bool Ready => Data != null;
        static int CellCount => data.GW * data.GH;
        static int ByteCount => (data.GW * data.GH + 7) >> 3;

        /// <summary>Kaito recorre el mundo: descubre a su alrededor cada 2 m (lo llama la UI todos los cuadros).</summary>
        public static void Tick(Vector3 pos)
        {
            if (!Ensure()) return;
            if (hasLast && (pos - last).sqrMagnitude < Step * Step) return;
            hasLast = true; last = pos;
            Reveal(pos, data.reveal);
        }

        /// <summary>Descubre las celdas cuyo centro queda a menos de 'radius' de 'pos' (el agua abierta, hasta
        /// revealWater) del mismo lado de las puertas cerradas.</summary>
        public static void Reveal(Vector3 pos, float radius)
        {
            if (!Ensure()) return;
            if (RevealDisc(pos.x, pos.z, radius, -1)) { dirty = true; Version++; }
        }

        /// <param name="from">De qué lado de las puertas se mira (-1: el del centro del disco, donde está Kaito).</param>
        static bool RevealDisc(float x, float z, float r, int from)
        {
            float c = data.cell;
            float rw = water != null ? Mathf.Max(r, data.revealWater) : r;
            int gx0 = Mathf.Max(0, Mathf.FloorToInt((x - rw - data.X0) / c)), gx1 = Mathf.Min(data.GW - 1, Mathf.FloorToInt((x + rw - data.X0) / c));
            int gy0 = Mathf.Max(0, Mathf.FloorToInt((z - rw - data.Z0) / c)), gy1 = Mathf.Min(data.GH - 1, Mathf.FloorToInt((z + rw - data.Z0) / c));
            // de qué lado está Kaito y qué puertas están abiertas (una vez por llamada: cada 2 m de recorrido)
            int side = from >= 0 ? from : SideAt(x, z);
            bool wallOpen = GateOpen(0), dojoOpen = GateOpen(1);
            bool any = false;
            float r2 = r * r, rw2 = rw * rw;
            for (int gy = gy0; gy <= gy1; gy++)
            {
                float dz = data.Z0 + (gy + 0.5f) * c - z;
                for (int gx = gx0; gx <= gx1; gx++)
                {
                    float dx = data.X0 + (gx + 0.5f) * c - x;
                    float d2 = dx * dx + dz * dz;
                    if (d2 > rw2) continue;
                    int i = gy * data.GW + gx;
                    int b = 1 << (i & 7);
                    if ((bits[i >> 3] & b) != 0) continue;
                    if (d2 > r2 && (water == null || (water[i >> 3] & b) == 0)) continue;
                    int s = Side(i);
                    if (s != side && !Passable(side, s, wallOpen, dojoOpen)) continue;
                    bits[i >> 3] |= (byte)b;
                    any = true;
                }
            }
            return any;
        }

        /// <summary>0 al sur de la muralla, 1 al norte, 2 detrás del portón del dojo (sin los datos, todo es un lado).</summary>
        static int Side(int i)
        {
            int b = 1 << (i & 7);
            if (dojo != null && (dojo[i >> 3] & b) != 0) return 2;
            return north != null && (north[i >> 3] & b) != 0 ? 1 : 0;
        }

        static int SideAt(float x, float z)
        {
            int gx = Mathf.Clamp(Mathf.FloorToInt((x - data.X0) / data.cell), 0, data.GW - 1);
            int gy = Mathf.Clamp(Mathf.FloorToInt((z - data.Z0) / data.cell), 0, data.GH - 1);
            return Side(gy * data.GW + gx);
        }

        static bool GateOpen(int g) => data.gates == null || data.gates.Length <= g || owner.HasFlag(data.gates[g]);

        /// <summary>¿Se ve de un lado al otro? Sur y norte, por la muralla; norte y dojo, por su portón.</summary>
        static bool Passable(int a, int b, bool wallOpen, bool dojoOpen)
        {
            if (a > b) { int t = a; a = b; b = t; }
            return a == 0 ? wallOpen && (b == 1 || dojoOpen) : dojoOpen;
        }

        /// <summary>¿Ya vio Kaito este lugar?</summary>
        public static bool IsRevealed(Vector3 p)
        {
            if (!Ensure()) return false;
            int gx = Mathf.FloorToInt((p.x - data.X0) / data.cell), gy = Mathf.FloorToInt((p.z - data.Z0) / data.cell);
            if (gx < 0 || gy < 0 || gx >= data.GW || gy >= data.GH) return false;
            int i = gy * data.GW + gx;
            return (bits[i >> 3] & (1 << (i & 7))) != 0;
        }

        /// <summary>Cuánto de lo que se puede descubrir caminando ya se vio (0..1).</summary>
        public static float ExploredFraction
        {
            get
            {
                if (!Ensure() || reach == null || data.reachCount <= 0) return 0f;
                int n = 0;
                for (int i = 0; i < bits.Length && i < reach.Length; i++)
                {
                    int v = bits[i] & reach[i];
                    while (v != 0) { v &= v - 1; n++; }
                }
                return Mathf.Clamp01(n / (float)data.reachCount);
            }
        }

        /// <summary>
        /// El rectángulo del mundo (x, z) que ya se descubrió: el mapa se abre encuadrándolo mientras el jugador no
        /// eligió su propio zoom (al principio, una mancha sola en la lámina entera parecía un mapa vacío). Recorre
        /// los bits: solo al abrir el mapa.
        /// </summary>
        public static bool ExploredBounds(out Rect world)
        {
            world = default;
            if (!Ensure()) return false;
            int x0 = int.MaxValue, x1 = -1, y0 = int.MaxValue, y1 = -1;
            for (int i = 0, n = CellCount; i < n; i++)
            {
                if ((bits[i >> 3] & (1 << (i & 7))) == 0) continue;
                int gx = i % data.GW, gy = i / data.GW;
                if (gx < x0) x0 = gx;
                if (gx > x1) x1 = gx;
                if (gy < y0) y0 = gy;
                if (gy > y1) y1 = gy;
            }
            if (x1 < 0) return false;
            float c = data.cell;
            world = new Rect(data.X0 + x0 * c, data.Z0 + y0 * c, (x1 - x0 + 1) * c, (y1 - y0 + 1) * c);
            return true;
        }

        /// <summary>Antes de escribir la partida: los bits van a SaveData.mapFog (solo si cambiaron o si la partida
        /// todavía no los tenía). Si estos bits son de otra partida, no se toca.</summary>
        public static void Store(SaveData d)
        {
            if (d == null || d != owner || bits == null) return;
            if (!dirty && !string.IsNullOrEmpty(d.mapFog)) return;
            d.mapFog = prefix + Convert.ToBase64String(bits);
            dirty = false;
        }

        /// <summary>
        /// La textura de la niebla (Alpha8, GW x GH, la fila 0 al sur): 255 donde no se vio. Con un desenfoque [1 2 1]
        /// de dos pasadas: el borde llega al shader como una rampa de ~2 celdas y no como escalones.
        /// </summary>
        public static void FillTexture(byte[] dst)
        {
            if (!Ensure() || dst == null || dst.Length < CellCount) return;
            int w = data.GW, h = data.GH, n = w * h;
            if (blurA == null || blurA.Length != n) { blurA = new int[n]; blurB = new int[n]; }
            for (int i = 0; i < n; i++) blurA[i] = (bits[i >> 3] & (1 << (i & 7))) != 0 ? 0 : 255;
            for (int pass = 0; pass < 2; pass++)
            {
                for (int y = 0; y < h; y++)
                    for (int x = 0; x < w; x++)
                    {
                        int r = y * w;
                        int a = blurA[r + Mathf.Max(0, x - 1)], b = blurA[r + x], c = blurA[r + Mathf.Min(w - 1, x + 1)];
                        blurB[r + x] = a + 2 * b + c;          // x4
                    }
                for (int y = 0; y < h; y++)
                    for (int x = 0; x < w; x++)
                    {
                        int a = blurB[Mathf.Max(0, y - 1) * w + x], b = blurB[y * w + x], c = blurB[Mathf.Min(h - 1, y + 1) * w + x];
                        blurA[y * w + x] = (a + 2 * b + c + 8) >> 4;   // /16
                    }
            }
            for (int i = 0; i < n; i++) dst[i] = (byte)blurA[i];
        }

        public static int TextureWidth => Ready ? data.GW : 1;
        public static int TextureHeight => Ready ? data.GH : 1;

        // ---------------------------------------------------------------- partida
        static bool Ensure()
        {
            if (Data == null) return false;
            var d = SaveSystem.Data;
            if (d != owner) Load(d);
            return true;
        }

        static void Load(SaveData d)
        {
            owner = d;
            hasLast = false;
            Version++;
            int nb = ByteCount;
            string s = d.mapFog;
            if (!string.IsNullOrEmpty(s) && s.StartsWith(prefix, StringComparison.Ordinal))
            {
                bits = Decode(s.Substring(prefix.Length), nb);
                if (bits != null) { dirty = false; return; }
            }
            // partida de antes del mapa (o una niebla de otra grilla): lo que prueban sus flags y su santuario. Todo se
            // mira desde el lado del santuario: un disco del camino de la muralla con el centro ya del otro lado
            // (z -26 contra la muralla en -30) revelaba, con el portón cerrado, el jardín de adentro
            bits = new byte[nb];
            var cp = Checkpoint.Get(d.checkpoint);
            int from = cp != null ? SideAt(cp.transform.position.x, cp.transform.position.z) : 0;
            if (data.legacy != null)
                foreach (var l in data.legacy)
                {
                    if (l == null || l.flags == null || l.d == null || !AnyFlag(d, l.flags)) continue;
                    for (int i = 0; i + 2 < l.d.Length; i += 3) RevealDisc(l.d[i], l.d[i + 1], l.d[i + 2], from);
                }
            if (cp != null) RevealDisc(cp.transform.position.x, cp.transform.position.z, data.reveal * 1.5f, from);
            dirty = true;
        }

        static bool AnyFlag(SaveData d, string[] flags)
        {
            foreach (var f in flags) if (d.HasFlag(f)) return true;
            return false;
        }

        static byte[] Decode(string b64, int expected)
        {
            if (string.IsNullOrEmpty(b64)) return null;
            try
            {
                var b = Convert.FromBase64String(b64);
                return b.Length == expected ? b : null;
            }
            catch (FormatException) { return null; }
        }

#if UNITY_EDITOR || DEVELOPMENT_BUILD
        /// <summary>Pruebas: descubre todo lo que se puede descubrir caminando (RunCommand: Nindo.MapFog.DebugRevealAll()).</summary>
        public static void DebugRevealAll()
        {
            if (!Ensure() || reach == null) return;
            for (int i = 0; i < bits.Length && i < reach.Length; i++) bits[i] |= reach[i];
            dirty = true; Version++;
        }

        /// <summary>Pruebas: vuelve a cubrir todo (la próxima pasada de Kaito descubre de nuevo a su alrededor).</summary>
        public static void DebugClear()
        {
            if (!Ensure()) return;
            Array.Clear(bits, 0, bits.Length);
            hasLast = false; dirty = true; Version++;
        }
#endif
    }
}
