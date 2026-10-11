"""
Mapa del mundo de Nindō (tecla M): una lámina de tinta sobre papel de arroz hecha con los datos REALES del mundo.

No es una captura del juego (de noche, con niebla y las luces del LightPool solo cerca de Kaito, un render cenital
sale oscuro y depende de la iluminación); es una ilustración sumi-e que sale de lo mismo que arma el mundo:
  * alturas, agua, caminos y regiones: Tools/Blender/world/world_terrain.py + world_plan.py (Python puro);
  * cada árbol, roca, casa, farol y puente en su lugar: los props que ubica build_world.py (mismo sorteo),
    volcados por Tools/UI/world_map_data.py (corre en Blender).

Lenguaje del kit "Tinta y Bandana": tinta caliente sobre papel, aguadas de poco color (índigo en el agua, verde
apagado en el bosque, blanco azulado en la nieve), rosa del sakura, laca roja de los torii y puntos de oro donde hay
faroles encendidos (de noche el mapa se lee por sus luces). Sin texto horneado: los nombres de las zonas, los
santuarios y los jefes los pone la UI encima (se ocultan hasta descubrirlos).

Salida (Nindo/Assets/Nindo/Resources/UI):
  WorldMap.jpg       la lámina (3096 x 2568, 6 px por metro; incluye el margen de papel y el borde)
  WorldMapMist.png   niebla de lo no explorado (1024 repetible, datos: R fibra del papel, G relleno de las nubes
                     kasumi, B su contorno, A jirones chicos): la compone el shader Nindo/UI Map
  WorldMap.json      límites de la lámina en metros, color del papel y dónde va el nombre de cada zona
  MapShrine.png      pictograma del santuario (torii, el símbolo de los mapas japoneses), blanco con contorno
  MapPortal.png      portal de vuelta al dojo (espiral)

Uso:
  blender -b --factory-startup --python Tools/UI/world_map_data.py -- <scratch>/map_props.json   (una vez por cambio del mundo)
  python Tools/UI/build_world_map.py --props <scratch>/map_props.json [--preview CARPETA] [--labels]
"""
import argparse
import hashlib
import json
import math
import os
import random
import sys
import time
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
WORLD = os.path.join(REPO, "Tools", "Blender", "world")
sys.path[:0] = [WORLD, os.path.join(REPO, "Tools", "Unity"), HERE]
import world_plan as W  # noqa: E402
import world_terrain as T  # noqa: E402
import falls_layout as FALLS  # noqa: E402
from unity_yaml import ASSETS, TEXT_META, texture_meta, write_meta  # noqa: E402

OUT = os.path.join(ASSETS, "Nindo", "Resources", "UI")
FONTS = os.path.join(ASSETS, "Nindo", "Art", "Fonts")

# ------------------------------------------------------------------------------------------- lámina
PPM = 6.0                                   # píxeles por metro
X0, X1, Z0, Z1 = W.MAP_BOUNDS               # lo que cubre el terreno (también la grilla de la niebla en C#)
MARGIN = 14                                 # papel alrededor (m): ahí va el borde rasgado
IX0, IX1, IZ0, IZ1 = X0 - MARGIN, X1 + MARGIN, Z0 - MARGIN, Z1 + MARGIN
IW, IH = int((IX1 - IX0) * PPM), int((IZ1 - IZ0) * PPM)   # 3096 x 2568 (múltiplos de 4: compresión por bloques)
GW, GH = IX1 - IX0, IZ1 - IZ0               # grilla de muestras de 1 m (centros de celda)

PAPER = np.array([0.925, 0.884, 0.790], np.float32)       # washi (más apagado que el papel de los textos)
INK = np.array([0.105, 0.090, 0.095], np.float32)         # sumi caliente
BACK = (11, 10, 13)                                         # fondo del panel del mapa (UIFactory.Ink)
REGIONS = ["hogar", "campos", "bosque", "jardin", "dojo", "montana", "lago", "bambu"]
# aguadas por región (multiplican el papel): suelo abierto y bosque
TINT = {
    "hogar":   ((0.955, 0.935, 0.840), (0.70, 0.75, 0.62)),
    "campos":  ((0.965, 0.935, 0.820), (0.72, 0.76, 0.62)),
    "bosque":  ((0.900, 0.915, 0.840), (0.62, 0.69, 0.60)),
    "jardin":  ((0.930, 0.950, 0.860), (0.68, 0.75, 0.64)),
    "dojo":    ((0.905, 0.890, 0.900), (0.66, 0.66, 0.70)),
    "montana": ((1.040, 1.060, 1.110), (0.86, 0.89, 0.97)),
    "lago":    ((0.925, 0.945, 0.880), (0.68, 0.75, 0.66)),
    "bambu":   ((0.900, 0.955, 0.860), (0.66, 0.78, 0.62)),
}
# dónde va el nombre de cada zona (la UI lo escribe; acá solo se elige un lugar que no tape caminos ni jefes)
LABELS = {
    "hogar": (-16, -186), "campos": (30, -138), "bosque": (-26, -62), "muralla": (32, -40), "jardin": (-30, 34),
    "dojo": (0, 182), "montana": (-150, 34), "lago": (150, -24), "lago_cascada": (184, 104), "bambu": (128, 116),
}


def wx(px):
    return IX0 + (px + 0.5) / PPM


def to_px(x, z):
    return (x - IX0) * PPM, (IZ1 - z) * PPM


# ------------------------------------------------------------------------------------------- grilla del mundo
def _row(j):
    z = IZ1 - 0.5 - j
    h = np.zeros(GW, np.float32); wd = np.zeros(GW, np.float32); pd = np.zeros(GW, np.float32)
    sd = np.zeros(GW, np.float32); lk = np.zeros(GW, np.float32); rg = np.zeros(GW, np.int8)
    for i in range(GW):
        x = IX0 + 0.5 + i
        h[i] = T.height(x, z)
        wd[i] = T.walk_dist(x, z)
        pd[i] = T.path_info(x, z)[0]
        sd[i] = T.stream_dist(x, z)
        lk[i] = 1.0 if T.in_lake(x, z) else 0.0
        rg[i] = REGIONS.index(T.region(x, z))
    return h, wd, pd, sd, lk, rg


def world_grid(cache_dir):
    src = b"".join(open(os.path.join(WORLD, f), "rb").read() for f in ("world_plan.py", "world_terrain.py", "falls_layout.py"))
    key = hashlib.md5(src + repr((IX0, IX1, IZ0, IZ1)).encode()).hexdigest()[:12]
    path = os.path.join(cache_dir, f"map_grid_{key}.npz")
    if os.path.exists(path):
        d = np.load(path)
        return {k: d[k] for k in d.files}
    t = time.time()
    with Pool(max(1, (os.cpu_count() or 4) - 2)) as pool:
        rows = pool.map(_row, range(GH))
    g = {k: np.stack([r[i] for r in rows]) for i, k in enumerate(("h", "wd", "pd", "sd", "lake", "reg"))}
    np.savez_compressed(path, **g)
    print(f"grilla {GW}x{GH} en {time.time() - t:.1f} s -> {path}")
    return g


def up(a, mode=Image.BICUBIC):
    """Campo de 1 m -> píxeles de la lámina (los centros coinciden: 1 m = 6 px exactos)."""
    return np.asarray(Image.fromarray(np.ascontiguousarray(a, np.float32), "F").resize((IW, IH), mode))


# ------------------------------------------------------------------------------------------- ruido
def vnoise(cell_px, seed, w=IW, h=IH):
    rs = np.random.RandomState(seed)
    gw, gh = int(w / cell_px) + 3, int(h / cell_px) + 3
    g = rs.rand(gh, gw).astype(np.float32)
    big = Image.fromarray(g, "F").resize((int(round(gw * cell_px)), int(round(gh * cell_px))), Image.BICUBIC)
    return np.asarray(big)[:h, :w]


def fbm(cell_px, seed, octaves=4, w=IW, h=IH):
    v = np.zeros((h, w), np.float32); a, tot = 1.0, 0.0
    for o in range(octaves):
        v += a * vnoise(max(1.5, cell_px / (2 ** o)), seed + 31 * o, w, h)
        tot += a; a *= 0.5
    return v / tot


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------------------------------- sellos (stamps)
SS = 4   # supersampling de cada sello


class Stamps:
    """Capa RGBA donde se 'estampan' árboles, casas y faroles, y una capa de sombra aparte (se desenfoca)."""

    def __init__(self):
        self.ink = Image.new("RGBA", (IW, IH), (0, 0, 0, 0))
        self.shadow = Image.new("L", (IW, IH), 0)
        self.glow = Image.new("L", (IW, IH), 0)

    def put(self, img, x, z, shadow=0.0, shadow_off=(0.35, 0.5)):
        """img: RGBA a SS x; (x, z) centro en metros. shadow: opacidad de la sombra (hacia el sureste)."""
        w, h = img.size[0] // SS, img.size[1] // SS
        if w < 1 or h < 1:
            return
        small = img.resize((w, h), Image.LANCZOS)
        px, py = to_px(x, z)
        ox, oy = int(round(px - w / 2)), int(round(py - h / 2))
        if shadow > 0:
            a = small.getchannel("A").point(lambda v: int(v * shadow))
            r = max(w, h) / 2
            self.shadow.paste(Image.new("L", a.size, 255), (ox + int(r * shadow_off[0]), oy + int(r * shadow_off[1])), a)
        # recorte a la lámina (alpha_composite no acepta destinos fuera de la imagen)
        sx0, sy0 = max(0, -ox), max(0, -oy)
        sx1, sy1 = min(w, IW - ox), min(h, IH - oy)
        if sx1 > sx0 and sy1 > sy0:
            self.ink.alpha_composite(small, (ox + sx0, oy + sy0), (sx0, sy0, sx1, sy1))

    def light(self, x, z, r_px, strength=255):
        px, py = to_px(x, z)
        d = ImageDraw.Draw(self.glow)
        d.ellipse((px - r_px, py - r_px, px + r_px, py + r_px), fill=strength)


def canvas(r_px, pad=1.6):
    s = int(math.ceil(r_px * 2 * pad)) * SS + SS * 2
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), s / 2.0


def col8(c, a=1.0):
    return (int(c[0] * 255), int(c[1] * 255), int(c[2] * 255), int(a * 255))


def blob(d, cx, cy, r, rng, n=18, wob=0.18, fill=None, outline=None, width=1):
    pts = []
    ph = rng.random() * math.tau
    k = rng.randint(3, 5)
    for i in range(n):
        a = i / n * math.tau
        rr = r * (1 + wob * (math.sin(a * k + ph) * 0.5 + (rng.random() - 0.5)))
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    d.polygon(pts, fill=fill, outline=outline, width=width)
    return pts


def stamp_conifer(r, rng, body, tip, snow=False):
    """Pino o cedro visto desde arriba: estrella de agujas de tinta, el centro más cargado."""
    img, d, c = canvas(r)
    R = r * SS
    n = rng.randint(9, 13)
    pts = []
    ph = rng.random() * math.tau
    for i in range(n * 2):
        a = ph + i / (n * 2) * math.tau
        rr = R * (rng.uniform(0.9, 1.08) if i % 2 == 0 else rng.uniform(0.48, 0.62))
        pts.append((c + math.cos(a) * rr, c + math.sin(a) * rr))
    d.polygon(pts, fill=col8(tip, 0.92))
    # segunda capa más chica girada (copa en pisos) y el corazón casi negro
    pts2 = []
    for i in range(n * 2):
        a = ph + (i + 0.5) / (n * 2) * math.tau
        rr = R * (rng.uniform(0.62, 0.72) if i % 2 == 0 else rng.uniform(0.32, 0.4))
        pts2.append((c + math.cos(a) * rr, c + math.sin(a) * rr))
    d.polygon(pts2, fill=col8(body, 0.95))
    if snow:
        # nieve sobre las ramas del lado de la luna (noroeste)
        for i in range(n):
            a = ph + i / n * math.tau
            if math.cos(a + math.pi * 0.75) < -0.1:
                continue
            rr = R * rng.uniform(0.45, 0.75)
            x, y = c + math.cos(a) * rr, c + math.sin(a) * rr
            d.ellipse((x - R * 0.13, y - R * 0.1, x + R * 0.13, y + R * 0.1), fill=(238, 242, 248, 235))
        d.ellipse((c - R * 0.2 - R * 0.12, c - R * 0.2 - R * 0.12, c - R * 0.2 + R * 0.14, c - R * 0.2 + R * 0.14), fill=(244, 247, 252, 240))
    else:
        d.ellipse((c - R * 0.12, c - R * 0.12, c + R * 0.12, c + R * 0.12), fill=col8(INK, 0.9))
    return img


def stamp_round(r, rng, fill, rim, light=(1.0, 1.0, 1.0), dots=None):
    """Copa redonda en aguada: borde más oscuro abajo a la derecha, luz arriba a la izquierda (luna)."""
    img, d, c = canvas(r)
    R = r * SS
    blob(d, c + R * 0.06, c + R * 0.08, R * 1.0, rng, fill=col8(rim, 0.9))
    blob(d, c - R * 0.04, c - R * 0.04, R * 0.86, rng, fill=col8(fill, 0.95))
    blob(d, c - R * 0.28, c - R * 0.3, R * 0.38, rng, fill=col8(np.minimum(np.array(fill) * np.array(light) * 1.12, 1), 0.7))
    if dots is not None:
        for _ in range(int(14 * r / 6) + 6):
            a, rr = rng.random() * math.tau, R * math.sqrt(rng.random()) * 0.85
            x, y = c + math.cos(a) * rr, c + math.sin(a) * rr
            s = R * rng.uniform(0.07, 0.13)
            d.ellipse((x - s, y - s, x + s, y + s), fill=col8(dots, 0.9))
    return img


def stamp_bamboo(r, rng):
    """Mata de bambú: cañas (circulitos) y hojas en trazos cortos verde jade."""
    img, d, c = canvas(r)
    R = r * SS
    for _ in range(int(10 + r * 1.5)):
        a, rr = rng.random() * math.tau, R * math.sqrt(rng.random()) * 1.0
        x, y = c + math.cos(a) * rr, c + math.sin(a) * rr
        ang = rng.random() * math.tau
        L = R * rng.uniform(0.35, 0.6)
        g = rng.uniform(0.85, 1.1)
        d.line([(x, y), (x + math.cos(ang) * L, y + math.sin(ang) * L)], fill=col8((0.36 * g, 0.50 * g, 0.30 * g), 0.85), width=max(1, int(SS * 1.3)))
    for _ in range(int(4 + r * 0.6)):
        a, rr = rng.random() * math.tau, R * math.sqrt(rng.random()) * 0.55
        x, y = c + math.cos(a) * rr, c + math.sin(a) * rr
        s = R * 0.09
        d.ellipse((x - s, y - s, x + s, y + s), fill=col8((0.25, 0.33, 0.20), 0.95))
    return img


def stamp_dead(r, rng):
    img, d, c = canvas(r)
    R = r * SS
    def branch(x, y, ang, L, w, depth):
        x2, y2 = x + math.cos(ang) * L, y + math.sin(ang) * L
        d.line([(x, y), (x2, y2)], fill=col8(INK, 0.9), width=max(1, int(w)))
        if depth > 0:
            for s in (-1, 1):
                branch(x2, y2, ang + s * rng.uniform(0.35, 0.8), L * 0.6, w * 0.65, depth - 1)
    for k in range(rng.randint(3, 4)):
        branch(c, c, rng.random() * math.tau, R * 0.55, SS * 1.6, 2)
    return img


def stamp_rock(r, rng, fill=(0.58, 0.57, 0.58), snow=False, dark=False):
    img, d, c = canvas(r)
    R = r * SS
    n = rng.randint(5, 7)
    ph = rng.random() * math.tau
    pts = [(c + math.cos(ph + i / n * math.tau) * R * rng.uniform(0.75, 1.0), c + math.sin(ph + i / n * math.tau) * R * rng.uniform(0.75, 1.0)) for i in range(n)]
    d.polygon(pts, fill=col8(INK, 0.9))
    inner = [(c + (x - c) * 0.78 - R * 0.06, c + (y - c) * 0.78 - R * 0.08) for x, y in pts]
    base = (0.30, 0.30, 0.33) if dark else fill
    d.polygon(inner, fill=col8(base, 1.0))
    if snow:
        cap = [(c + (x - c) * 0.6 - R * 0.14, c + (y - c) * 0.55 - R * 0.18) for x, y in pts]
        d.polygon(cap, fill=(240, 244, 250, 240))
    return img


def stamp_cliff(r, rng, yaw, snow=False):
    """Peñasco: bloque anguloso de tinta con facetas, como los acantilados del juego."""
    img, d, c = canvas(r, 1.4)
    R = r * SS
    n = rng.randint(6, 8)
    ph = math.radians(yaw)
    pts = [(c + math.cos(ph + i / n * math.tau) * R * rng.uniform(0.6, 1.0), c + math.sin(ph + i / n * math.tau) * R * rng.uniform(0.55, 0.95)) for i in range(n)]
    d.polygon(pts, fill=col8((0.17, 0.17, 0.19), 0.93))
    for _ in range(3):
        a = rng.random() * math.tau
        x, y = c + math.cos(a) * R * 0.3, c + math.sin(a) * R * 0.3
        d.line([(x, y), (x + math.cos(a + 1.2) * R * 0.5, y + math.sin(a + 1.2) * R * 0.5)], fill=col8((0.42, 0.42, 0.46), 0.8), width=max(1, SS))
    if snow:
        cap = [(c + (x - c) * 0.55 - R * 0.15, c + (y - c) * 0.5 - R * 0.2) for x, y in pts]
        d.polygon(cap, fill=(236, 241, 248, 220))
    return img


def rotated(img, yaw):
    """yaw del juego (grados desde el norte, a favor del reloj visto desde arriba) -> PIL gira en contra."""
    return img.rotate(-yaw, resample=Image.BICUBIC, expand=True)


def stamp_roof(sx, sz, yaw, color=(0.16, 0.14, 0.15), ridge=(0.36, 0.33, 0.31), gold=False, hip=True):
    """Techo visto desde arriba (sx ancho, sz fondo, en metros): faldones de tinta con la cumbrera más clara."""
    w, h = sx * PPM * SS, sz * PPM * SS
    pad = SS * 4
    img = Image.new("RGBA", (int(w + pad * 2), int(h + pad * 2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = pad, pad, pad + w, pad + h
    d.rectangle((x0, y0, x1, y1), fill=col8(color, 0.96))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    lw = max(1, int(SS * 1.1))
    if hip:
        # cumbrera a lo largo del lado mayor y las limatesas desde cada esquina a su punta
        if w >= h:
            a, b = (cx - (w - h) / 2, cy), (cx + (w - h) / 2, cy)
            corners = (((x0, y0), a), ((x0, y1), a), ((x1, y0), b), ((x1, y1), b))
        else:
            a, b = (cx, cy - (h - w) / 2), (cx, cy + (h - w) / 2)
            corners = (((x0, y0), a), ((x1, y0), a), ((x0, y1), b), ((x1, y1), b))
        d.line([a, b], fill=col8(ridge, 0.95), width=lw * 2)
        for p, q in corners:
            d.line([p, q], fill=col8(ridge, 0.8), width=lw)
        if gold:
            d.line([a, b], fill=(232, 190, 92, 255), width=lw)
    # alero: la luna lo marca arriba a la izquierda
    d.line([(x0, y1), (x0, y0), (x1, y0)], fill=col8(np.minimum(np.array(ridge) * 1.35, 1), 0.7), width=lw)
    return rotated(img, yaw)


def stamp_rect(sx, sz, yaw, fill, outline=None, lines=0, line_col=None, along=True):
    w, h = max(SS, sx * PPM * SS), max(SS, sz * PPM * SS)
    pad = SS * 3
    img = Image.new("RGBA", (int(w + pad * 2), int(h + pad * 2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = pad, pad, pad + w, pad + h
    d.rectangle((x0, y0, x1, y1), fill=fill, outline=outline, width=max(1, SS))
    if lines:
        for k in range(1, lines):
            if along:
                y = y0 + (y1 - y0) * k / lines
                d.line([(x0, y), (x1, y)], fill=line_col, width=max(1, SS // 2))
            else:
                x = x0 + (x1 - x0) * k / lines
                d.line([(x, y0), (x, y1)], fill=line_col, width=max(1, SS // 2))
    return rotated(img, yaw)


def stamp_torii(sx, yaw, color):
    w = sx * PPM * SS
    pad = SS * 4
    img = Image.new("RGBA", (int(w + pad * 2), int(pad * 2 + SS * 8)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cy = img.size[1] / 2
    d.line([(pad, cy), (pad + w, cy)], fill=col8(color, 1.0), width=int(SS * 2.6))
    for x in (pad + w * 0.2, pad + w * 0.8):
        d.ellipse((x - SS * 2.2, cy - SS * 2.2, x + SS * 2.2, cy + SS * 2.2), fill=col8(INK, 1.0))
    return rotated(img, yaw)


def stamp_boat(sx, sz, yaw):
    w, h = sx * PPM * SS, sz * PPM * SS
    pad = SS * 3
    img = Image.new("RGBA", (int(w + pad * 2), int(h + pad * 2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = pad, pad, pad + w, pad + h
    cx = (x0 + x1) / 2
    d.polygon([(cx, y0), (x1, y0 + h * 0.3), (x1, y1 - h * 0.12), (cx, y1), (x0, y1 - h * 0.12), (x0, y0 + h * 0.3)], fill=col8((0.30, 0.22, 0.17), 1.0))
    d.line([(cx, y0 + h * 0.2), (cx, y1 - h * 0.15)], fill=col8((0.55, 0.42, 0.30), 1.0), width=SS)
    return rotated(img, yaw)


def dot(r_px, color, a=1.0):
    s = int(math.ceil(r_px * 2 + 2)) * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, R = s / 2, r_px * SS
    d.ellipse((c - R, c - R, c + R, c + R), fill=col8(color, a))
    return img


SIZES = {}


def size_of(pid):
    return SIZES.get(pid, [2, 2, 2])


def radius_of(pid, sc):
    s = size_of(pid)
    return max(s[0], s[2]) * 0.5 * sc


GREENS = {
    "tree_cedar_a": ((0.13, 0.17, 0.15), (0.24, 0.31, 0.26)),
    "tree_cedar_b": ((0.12, 0.16, 0.15), (0.22, 0.30, 0.27)),
    "tree_pine_a": ((0.12, 0.15, 0.13), (0.26, 0.31, 0.24)),
    "tree_pine_b": ((0.13, 0.16, 0.13), (0.28, 0.33, 0.25)),
    "tree_pine_c": ((0.12, 0.15, 0.14), (0.25, 0.30, 0.26)),
    "tree_pine_snow_a": ((0.14, 0.17, 0.20), (0.27, 0.32, 0.36)),
    "tree_pine_snow_b": ((0.15, 0.18, 0.21), (0.29, 0.34, 0.38)),
    "pine_falls_lip": ((0.12, 0.16, 0.16), (0.24, 0.30, 0.30)),
}
LAMPS = {"lantern_post": 1.4, "lantern_stone": 1.2, "lantern_stone_tall": 1.6, "torch_brazier": 1.8, "brazier_kage": 2.2, "campfire": 2.4}
ROOFS = {"house_kaito", "storehouse_kura", "house_farmer_a", "house_farmer_b", "house_village_a", "house_village_b",
         "house_fisher", "mountain_cabin", "temple_bell", "dojo_gate", "wall_gate", "pavilion_azumaya", "pagoda_small", "shrine_small"}


def stamp_props(st, props):
    rng = random.Random(77)
    order = sorted(props, key=lambda p: (0 if p[0].startswith(("flowers", "tall_grass", "mushroom", "reeds")) else
                                        1 if p[0].startswith(("bush", "rock_small")) else 2, p[2], p[1]))
    for pid, x, z, yaw, sc, y in order:
        r = radius_of(pid, sc)
        rp = r * PPM
        if pid in GREENS:
            body, tip = GREENS[pid]
            st.put(stamp_conifer(rp * 0.85, rng, body, tip, snow="snow" in pid), x, z, shadow=0.55)
        elif pid in ("tree_round_a", "tree_round_b"):
            g = rng.uniform(0.92, 1.06)
            st.put(stamp_round(rp * 0.8, rng, (0.38 * g, 0.47 * g, 0.36 * g), (0.20, 0.27, 0.21)), x, z, shadow=0.5)
        elif pid.startswith("tree_sakura"):
            st.put(stamp_round(rp * 0.78, rng, (0.90, 0.68, 0.73), (0.66, 0.40, 0.48), dots=(0.97, 0.84, 0.87)), x, z, shadow=0.45)
        elif pid == "tree_maple_a":
            st.put(stamp_round(rp * 0.78, rng, (0.80, 0.42, 0.26), (0.52, 0.22, 0.15), dots=(0.90, 0.62, 0.30)), x, z, shadow=0.45)
        elif pid == "tree_dead_a":
            st.put(stamp_dead(rp * 0.7, rng), x, z, shadow=0.2)
        elif pid.startswith("bamboo_cluster") or pid == "bamboo_young":
            st.put(stamp_bamboo(rp * (0.85 if pid != "bamboo_young" else 0.6), rng), x, z, shadow=0.35)
        elif pid in ("bush_round_a", "bush_round_b", "bush_round_c"):
            g = rng.uniform(0.92, 1.08)
            st.put(stamp_round(max(2.2, rp * 0.8), rng, (0.42 * g, 0.50 * g, 0.38 * g), (0.24, 0.31, 0.24)), x, z, shadow=0.35)
        elif pid == "bush_azalea_pink":
            st.put(stamp_round(max(2.2, rp * 0.8), rng, (0.90, 0.58, 0.70), (0.62, 0.34, 0.46), dots=(0.96, 0.78, 0.84)), x, z, shadow=0.35)
        elif pid == "bush_azalea_white":
            st.put(stamp_round(max(2.2, rp * 0.8), rng, (0.95, 0.94, 0.90), (0.62, 0.62, 0.60)), x, z, shadow=0.35)
        elif pid == "bush_snow":
            st.put(stamp_round(max(2.2, rp * 0.75), rng, (0.93, 0.95, 0.98), (0.60, 0.66, 0.76)), x, z, shadow=0.3)
        elif pid.startswith("flowers"):
            c = {"flowers_pink": (0.93, 0.56, 0.68), "flowers_yellow": (0.96, 0.80, 0.38), "flowers_blue": (0.52, 0.62, 0.86)}[pid]
            for _ in range(3):
                st.put(dot(rng.uniform(0.8, 1.3), c, 0.85), x + rng.uniform(-0.6, 0.6), z + rng.uniform(-0.6, 0.6))
        elif pid in ("tall_grass_patch", "reeds_patch"):
            img, d, cc = canvas(max(3.0, rp * 0.7))
            for _ in range(7):
                a = rng.random() * math.tau; rr = rp * 0.6 * SS * rng.random()
                xx, yy = cc + math.cos(a) * rr, cc + math.sin(a) * rr
                d.line([(xx, yy), (xx + rng.uniform(-2, 2) * SS, yy - rng.uniform(2, 4) * SS)], fill=col8((0.30, 0.36, 0.26), 0.8), width=SS)
            st.put(img, x, z)
        elif pid == "mushroom_cluster":
            st.put(dot(1.0, (0.55, 0.36, 0.26), 0.9), x, z)
        elif pid in ("rock_small_a", "rock_small_b", "rock_medium_a", "rock_medium_b", "rock_large_a", "rock_large_b", "stump", "log_fallen"):
            st.put(stamp_rock(max(1.6, rp * 0.85), rng), x, z, shadow=0.4)
        elif pid == "rock_snow_a":
            st.put(stamp_rock(max(1.8, rp * 0.85), rng, snow=True), x, z, shadow=0.4)
        elif pid == "rock_pillar":
            st.put(stamp_rock(rp * 0.9, rng, dark=True), x, z, shadow=0.6)
        elif pid.startswith("cliff"):
            st.put(stamp_cliff(rp * 0.75, rng, yaw, snow=pid == "cliff_c"), x, z, shadow=0.55)
        elif pid in LAMPS:
            st.light(x, z, LAMPS[pid] * PPM * 1.3, 255)
            st.put(dot(1.6 if pid not in ("brazier_kage", "campfire") else 2.2, (1.0, 0.80, 0.42), 1.0), x, z)
        elif pid in ROOFS:
            s = size_of(pid)
            sx, sz = s[0] * sc, s[2] * sc
            if pid == "pagoda_small":
                st.put(stamp_roof(sx, sz, yaw), x, z, shadow=0.7, shadow_off=(0.6, 0.9))
                st.put(stamp_roof(sx * 0.62, sz * 0.62, yaw, color=(0.22, 0.19, 0.2)), x, z)
            elif pid == "shrine_small":
                st.put(stamp_roof(sx * 0.8, sz * 0.8, yaw, color=(0.62, 0.16, 0.12), ridge=(0.82, 0.36, 0.28)), x, z, shadow=0.6)
            elif pid == "temple_bell" or pid == "pavilion_azumaya":
                st.put(stamp_roof(min(sx, sz), min(sx, sz), yaw), x, z, shadow=0.6)
            elif pid == "wall_gate":
                st.put(stamp_roof(sx, sz * 0.8, yaw, color=(0.13, 0.11, 0.12), ridge=(0.42, 0.20, 0.16)), x, z, shadow=0.7)
            elif pid == "dojo_gate":
                st.put(stamp_roof(sx, sz, yaw, color=(0.12, 0.10, 0.11), ridge=(0.40, 0.34, 0.30), gold=True), x, z, shadow=0.7)
            else:
                st.put(stamp_roof(sx, sz, yaw), x, z, shadow=0.7, shadow_off=(0.45, 0.65))
        elif pid == "dojo_main":
            s = size_of(pid)
            st.put(stamp_roof(s[0], s[2], yaw, color=(0.11, 0.09, 0.10), ridge=(0.40, 0.34, 0.30), gold=True), x, z, shadow=0.8, shadow_off=(0.3, 0.45))
            st.put(stamp_roof(s[0] * 0.55, s[2] * 0.5, yaw, color=(0.15, 0.13, 0.14), ridge=(0.45, 0.38, 0.32), gold=True), x, z)
        elif pid == "wall_segment":
            s = size_of(pid)
            st.put(stamp_rect(s[0] * sc + 0.3, s[2] * sc, yaw, col8((0.20, 0.18, 0.18), 1.0), outline=col8(INK, 1.0), lines=2, line_col=col8((0.5, 0.46, 0.42), 1.0)), x, z, shadow=0.8, shadow_off=(0.05, 0.6))
        elif pid == "wall_post":
            s = size_of(pid)
            st.put(stamp_rect(s[0] * sc, s[2] * sc, yaw, col8((0.16, 0.14, 0.14), 1.0)), x, z, shadow=0.7)
        elif pid in ("torii_red", "torii_stone", "falls_shrine_gate", "arch_bamboo_gate"):
            s = size_of(pid)
            color = (0.74, 0.16, 0.11) if pid in ("torii_red", "falls_shrine_gate") else (0.45, 0.58, 0.36) if pid == "arch_bamboo_gate" else (0.50, 0.49, 0.50)
            st.put(stamp_torii(s[0] * sc, yaw, color), x, z, shadow=0.5)
        elif pid in ("bridge_arch", "bridge_plank", "boardwalk_segment", "dock_segment"):
            s = size_of(pid)
            sx, sz = s[0], s[2] * (sc if pid == "boardwalk_segment" else 1.0)
            if pid != "boardwalk_segment":
                sx *= sc; sz *= sc
            wood = (0.52, 0.38, 0.26)
            rail = (0.70, 0.18, 0.12) if pid == "bridge_arch" else (0.26, 0.18, 0.13)
            img = stamp_rect(sx, sz, 0, col8(wood, 1.0), outline=col8(rail, 1.0), lines=max(2, int(sz / 0.7)), line_col=col8((0.36, 0.26, 0.18), 1.0))
            st.put(rotated(img, yaw), x, z, shadow=0.5)
        elif pid == "stairs_stone_large":
            s = size_of(pid)
            st.put(stamp_rect(s[0], s[2], yaw, col8((0.66, 0.65, 0.66), 1.0), outline=col8(INK, 0.9), lines=12, line_col=col8((0.32, 0.31, 0.33), 1.0)), x, z, shadow=0.5)
        elif pid == "boat_small":
            s = size_of(pid)
            st.put(stamp_boat(s[0] * sc, s[2] * sc, yaw), x, z, shadow=0.4)
        elif pid in ("banner_nobori", "banner_kurokage"):
            st.put(stamp_rect(0.9, 0.35, yaw, col8((0.72, 0.14, 0.12), 1.0)), x, z)
        elif pid in ("dojo_courtyard_floor", "lake_arena_platform", "kohan_falls_cliff", "key_seal_mountain", "seal_pedestal",
                     "shrine_checkpoint", "portal_ring", "scythe"):
            continue      # se dibujan aparte (arenas) o los pone la UI (santuarios, portales)
        else:
            # lo chico (pozo, carro, fardos, espantapájaros, estantes...): un punto de tinta de su tamaño
            s = size_of(pid)
            st.put(stamp_rect(max(0.5, s[0] * sc), max(0.5, s[2] * sc), yaw, col8((0.30, 0.25, 0.22), 0.95), outline=col8(INK, 0.9)), x, z, shadow=0.4)


# ------------------------------------------------------------------------------------------- arenas
def draw_arenas(st):
    """Patio del dojo (círculo de losas con su cordón) y plataforma del lago, con la herradura de la cascada."""
    big = Image.new("RGBA", (IW * 2, IH * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    K = 2

    def P(x, z):
        px, py = to_px(x, z)
        return px * K, py * K

    # patio de Kokuyō
    cx, cz = W.COURTYARD_C
    r = W.COURTYARD_R * PPM * K
    x0, x1, za, zb = W.COURTYARD_APRON
    a0, a1 = P(x0, zb), P(x1, za)
    d.rectangle((a0[0], a0[1], a1[0], a1[1]), fill=(196, 192, 188, 255))
    px, py = P(cx, cz)
    d.ellipse((px - r, py - r, px + r, py + r), fill=(204, 200, 196, 255), outline=(40, 34, 36, 255), width=int(PPM * K * 0.45))
    for rr in (0.72, 0.42):
        q = r * rr
        d.ellipse((px - q, py - q, px + q, py + q), outline=(120, 114, 114, 255), width=int(K * 2))
    for k in range(16):
        ang = k / 16 * math.tau
        d.line([(px + math.cos(ang) * r * 0.42, py + math.sin(ang) * r * 0.42), (px + math.cos(ang) * r, py + math.sin(ang) * r)], fill=(140, 134, 132, 255), width=int(K * 1.5))
    # cordón sagrado (shimenawa) con sus tiras de papel
    d.ellipse((px - r * 1.02, py - r * 1.02, px + r * 1.02, py + r * 1.02), outline=(214, 186, 120, 255), width=int(K * 2.2))
    # plataforma del lago: octógono de tablones sobre el agua
    lx, lz = 184, 72
    px, py = P(lx, lz)
    R = 9.6 * PPM * K
    oct_ = [(px + math.cos(math.radians(22.5 + 45 * k)) * R, py + math.sin(math.radians(22.5 + 45 * k)) * R) for k in range(8)]
    d.polygon(oct_, fill=(140, 104, 76, 255), outline=(44, 30, 24, 255))
    for k in range(-9, 10, 1):
        y = py + k * PPM * K
        half = math.sqrt(max(0.0, R * R - (k * PPM * K) ** 2)) * 0.97
        d.line([(px - half, y), (px + half, y)], fill=(110, 80, 58, 255), width=K)
    d.line(oct_ + [oct_[0]], fill=(44, 30, 24, 255), width=int(K * 3))
    # herradura de basalto de la cascada (falls_layout: radios y brazos) con sus cortinas de agua
    hx, hz = FALLS.HX, FALLS.HZ
    poly = []
    for b in np.linspace(-FALLS.STEP_END, FALLS.STEP_END, 80):
        e, n = FALLS.polar(FALLS.OUT_R, b)
        poly.append(P(hx + e, hz + n))
    for b in np.linspace(FALLS.STEP_END, -FALLS.STEP_END, 80):
        e, n = FALLS.polar(FALLS.LIP_R, b)
        poly.append(P(hx + e, hz + n))
    d.polygon(poly, fill=(36, 36, 42, 255))
    rng = random.Random(5)
    for _ in range(140):
        b = rng.uniform(-FALLS.STEP_END, FALLS.STEP_END); rr = rng.uniform(FALLS.LIP_R + 1, FALLS.OUT_R - 1)
        e, n = FALLS.polar(rr, b)
        a = P(hx + e, hz + n)
        e2, n2 = FALLS.polar(rr + rng.uniform(1.5, 3.5), b + rng.uniform(-6, 6))
        d.line([a, P(hx + e2, hz + n2)], fill=(78, 80, 90, 255), width=K * 2)
    for name, b0, b1, layers in FALLS.SHEETS:
        for b in np.arange(b0, b1, 1.2):
            e, n = FALLS.polar(FALLS.LIP_R + 0.6, b)
            e2, n2 = FALLS.polar(FALLS.LIP_R - 2.6, b)
            d.line([P(hx + e, hz + n), P(hx + e2, hz + n2)], fill=(226, 236, 242, 255), width=K * 2)
    small = big.resize((IW, IH), Image.LANCZOS)
    st.ink.alpha_composite(small)
    sh = small.getchannel("A")
    st.shadow.paste(Image.new("L", sh.size, 200), (int(PPM * 0.5), int(PPM * 0.7)), sh)


# ------------------------------------------------------------------------------------------- rosa de los vientos
def compass(img, x, z):
    d = ImageDraw.Draw(img, "RGBA")
    px, py = to_px(x, z)
    R = 70
    ink = (40, 34, 36, 230)
    d.ellipse((px - R, py - R, px + R, py + R), outline=ink, width=3)
    d.ellipse((px - R * 0.82, py - R * 0.82, px + R * 0.82, py + R * 0.82), outline=(40, 34, 36, 120), width=2)
    for k in range(4):
        a = k * math.pi / 2
        tip = (px + math.sin(a) * R * 1.25, py - math.cos(a) * R * 1.25)
        l = (px + math.sin(a - 0.5) * R * 0.22, py - math.cos(a - 0.5) * R * 0.22)
        rr = (px + math.sin(a + 0.5) * R * 0.22, py - math.cos(a + 0.5) * R * 0.22)
        d.polygon([tip, l, (px, py)], fill=(40, 34, 36, 235))
        d.polygon([tip, rr, (px, py)], fill=(150, 40, 34, 235) if k == 0 else (120, 112, 106, 220))
    font = ImageFont.truetype(os.path.join(FONTS, "ShipporiMinchoB1-ExtraBold.ttf"), 44)
    d.text((px, py - R * 1.25 - 30), "N", font=font, fill=(40, 34, 36, 240), anchor="mm")


# ------------------------------------------------------------------------------------------- lámina
def render(props, cache_dir, preview=None, labels=False):
    t0 = time.time()
    g = world_grid(cache_dir)
    h = up(g["h"]); wd = up(g["wd"]); pd = up(g["pd"]); sd = up(g["sd"]); lake = up(g["lake"], Image.BILINEAR)
    print(f"campos {time.time() - t0:.1f} s")
    # gradiente de la altura en metros por metro (para el relieve y el antialias de las curvas)
    gy, gx = np.gradient(g["h"].astype(np.float32))           # filas = sur (z baja), columnas = este
    gx, gy = up(gx), up(-gy)                                   # dh/dx (este), dh/dz (norte)
    grad = np.sqrt(gx * gx + gy * gy)

    # ---- papel
    fib = vnoise(1.2, 3) * 0.5 + vnoise(4, 4) * 0.5
    fibers = np.asarray(Image.fromarray((np.random.RandomState(9).rand(IH, IW // 18) * 255).astype(np.uint8), "L").resize((IW, IH), Image.BICUBIC), np.float32) / 255
    mottle = fbm(260, 11, 4)
    paper = PAPER[None, None, :] * (0.965 + 0.05 * mottle[..., None] + 0.018 * (fib[..., None] - 0.5) + 0.02 * (fibers[..., None] - 0.5))
    col = paper.copy()

    # ---- tierra: hasta donde llega lo pintado (un poco más allá del bosque, con borde de aguada irregular)
    edge_n = fbm(140, 21, 4)
    land = ss(42.0, 26.0, wd + (edge_n - 0.5) * 18.0)
    land = np.maximum(land, ss(0.2, 0.8, lake) * ss(30, 10, wd))
    # aguadas por región, mezcladas (las regiones son rectángulos: sin desenfoque se verían las costuras)
    open_t = np.zeros((IH, IW, 3), np.float32); forest_t = np.zeros((IH, IW, 3), np.float32)
    reg = g["reg"]
    for k, name in enumerate(REGIONS):
        m = ndimage.gaussian_filter((reg == k).astype(np.float32), 9.0)
        m = up(m)
        open_t += m[..., None] * np.array(TINT[name][0], np.float32)
        forest_t += m[..., None] * np.array(TINT[name][1], np.float32)
    wash_n = fbm(90, 31, 4)
    forest = ss(0.8, 7.0, wd) * (0.8 + 0.4 * wash_n)
    walk = ss(1.0, -1.5, wd)
    tint = open_t * (1 - forest[..., None]) + forest_t * forest[..., None]
    tint = tint * (1 + 0.035 * walk[..., None])               # lo transitable, un poco más claro
    col = col * (1 + (tint - 1) * land[..., None])
    mont = up(ndimage.gaussian_filter((reg == REGIONS.index("montana")).astype(np.float32), 6.0))

    # ---- relieve: luz de luna del noroeste; sombras frías
    L = np.array([-0.55, 0.55, 0.63], np.float32); L /= np.linalg.norm(L)
    n = np.stack([-gx, -gy, np.ones_like(gx)], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    shade = np.clip((n @ L - L[2]) * 1.6, -1, 1)              # 0 en lo plano
    k_relief = (0.34 + 0.4 * mont) * land
    shadow_col = np.array([0.62, 0.66, 0.78], np.float32)
    dark = np.clip(-shade, 0, 1)[..., None] * k_relief[..., None]
    col = col * (1 - dark * (1 - shadow_col))
    col = col + np.clip(shade, 0, 1)[..., None] * k_relief[..., None] * 0.08
    # curvas de nivel finas cada 2.5 m, cortadas por el pincel seco
    c = h / 2.5
    dpx = np.abs((c - 0.5) % 1.0 - 0.5) / np.maximum(grad / 2.5 / PPM, 1e-3)
    contour = (1 - ss(0.35, 1.25, dpx)) * ss(0.6, 2.0, h) * land * ss(0.35, 0.6, vnoise(22, 41))
    col = col * (1 - 0.16 * contour[..., None] * (1 - INK))
    # trazos de textura en las laderas empinadas (los "pliegues" de las montañas sumi-e): curvas muy juntas, cortas
    steep = ss(0.45, 1.2, grad) * land * ss(-0.5, 1.0, wd)
    c2 = h / 0.9
    d2 = np.abs((c2 - 0.5) % 1.0 - 0.5) / np.maximum(grad / 0.9 / PPM, 1e-3)
    hatch = (1 - ss(0.3, 1.0, d2)) * steep * ss(0.5, 0.62, vnoise(7, 51))
    col = col * (1 - 0.3 * hatch[..., None] * (1 - INK))

    # ---- agua (lago donde la altura baja del nivel; arroyos y estanque del jardín)
    def water_mask(level, near):
        s = level - h
        dpx_ = s / np.maximum(grad, 0.05) * PPM
        return ss(-0.7, 0.7, dpx_) * near, s
    lake_near = ss(16, 6, up(ndimage.distance_transform_edt(g["lake"] < 0.5).astype(np.float32)))
    wl, depth_l = water_mask(W.WATER_LAKE, lake_near)
    stream_near = ss(3.5, 2.0, sd) * up(ndimage.gaussian_filter((reg == REGIONS.index("jardin")).astype(np.float32), 2.0))
    ws, depth_s = water_mask(W.WATER_STREAM, stream_near)
    water = np.maximum(wl, ws)
    depth = np.where(wl >= ws, depth_l, depth_s)
    wn = fbm(120, 61, 4)
    shallow = np.array([0.60, 0.70, 0.74], np.float32); deep = np.array([0.30, 0.40, 0.52], np.float32)
    wcol = shallow + (deep - shallow) * ss(0.0, 3.0, depth)[..., None]
    wcol = wcol * (0.95 + 0.1 * wn[..., None])
    col = col * (1 - water[..., None]) + (paper * wcol) * water[..., None]
    # líneas de agua paralelas a la orilla (como en los mapas pintados) y la orilla en tinta
    for lev, a in ((0.55, 0.32), (1.25, 0.22), (2.2, 0.13)):
        dd = np.abs(depth - lev) / np.maximum(grad, 0.05) * PPM
        ln = (1 - ss(0.4, 1.3, dd)) * water * ss(0.3, 0.55, vnoise(14, 71 + int(lev * 10)))
        col = col * (1 - a * ln[..., None] * (1 - np.array([0.2, 0.26, 0.36], np.float32)))
    shore_d = np.abs(depth) / np.maximum(grad, 0.05) * PPM
    shore = (1 - ss(0.6, 1.8, shore_d)) * np.maximum(lake_near, stream_near) * land
    col = col * (1 - 0.75 * shore[..., None] * (1 - INK))
    # arrozales (inundados) y trigo
    for rect, base, lines in [(r, (0.66, 0.78, 0.78), (0.42, 0.56, 0.56)) for r in W.PADDIES] + [(r, (0.95, 0.84, 0.58), (0.74, 0.60, 0.36)) for r in W.WHEAT]:
        ax, ay = to_px(rect[0], rect[3]); bx, by = to_px(rect[2], rect[1])
        ax, ay, bx, by = int(ax), int(ay), int(bx), int(by)
        sub = col[ay:by, ax:bx]
        sub *= np.array(base, np.float32)
        for yy in range(0, by - ay, int(PPM * 1.5)):
            sub[yy:yy + 1] *= np.array(lines, np.float32) / np.array(base, np.float32)
        sub[:2] *= 0.55; sub[-2:] *= 0.55; sub[:, :2] *= 0.55; sub[:, -2:] *= 0.55

    # ---- caminos: tierra clara con los bordes en tinta cortada
    pn = vnoise(30, 81)
    path = ss(0.7, -0.5, pd + (pn - 0.5) * 0.6) * land * (1 - water)
    path_col = np.array([0.985, 0.955, 0.875], np.float32)[None, None, :] * (1 - mont[..., None]) + np.array([0.80, 0.80, 0.84], np.float32)[None, None, :] * mont[..., None]
    col = col * (1 - path[..., None] * 0.85) + paper * path_col * path[..., None] * 0.85
    pedge = (1 - ss(0.1, 0.45, np.abs(pd + 0.05))) * land * (1 - water) * ss(0.35, 0.55, vnoise(9, 91))
    col = col * (1 - 0.38 * pedge[..., None] * (1 - INK))
    print(f"suelo {time.time() - t0:.1f} s")

    # ---- props y arenas
    st = Stamps()
    draw_arenas(st)
    stamp_props(st, props)
    print(f"sellos {time.time() - t0:.1f} s")
    shadow = np.asarray(st.shadow.filter(ImageFilter.GaussianBlur(PPM * 0.5)), np.float32) / 255
    col = col * (1 - 0.38 * shadow[..., None] * (1 - shadow_col * 0.6))
    ink = np.asarray(st.ink, np.float32) / 255
    a = ink[..., 3:4]
    # los sellos también llevan la fibra del papel (si no parecen pegados encima)
    col = col * (1 - a) + ink[..., :3] * (0.94 + 0.08 * fib[..., None]) * a
    # resplandor de los faroles: oro tenue alrededor de cada luz
    glow = np.asarray(st.glow.filter(ImageFilter.GaussianBlur(PPM * 1.6)), np.float32) / 255
    col = col + glow[..., None] * np.array([0.30, 0.20, 0.04], np.float32) * 0.9

    # ---- envejecido, borde rasgado y fondo
    yy, xx = np.mgrid[0:IH, 0:IW].astype(np.float32)
    dx = np.minimum(xx, IW - 1 - xx); dy = np.minimum(yy, IH - 1 - yy)
    border = np.minimum(dx, dy)
    deckle = 18 + (fbm(26, 101, 3) - 0.5) * 22 + (vnoise(3, 102) - 0.5) * 6
    sheet = ss(deckle - 1.2, deckle + 1.2, border)
    age = ss(deckle + 70, deckle, border)
    col = col * (1 - 0.12 * age[..., None] * np.array([0.6, 0.85, 1.25], np.float32))
    img = Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8), "RGB")
    compass(img, -216, -176)
    arr = np.asarray(img, np.float32) / 255
    arr = arr * sheet[..., None] + (np.array(BACK, np.float32) / 255)[None, None, :] * (1 - sheet[..., None])
    img = Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "RGB")
    print(f"lámina {time.time() - t0:.1f} s")
    if labels:
        draw_labels(img)
    return img


def draw_labels(img):
    """Solo para la vista previa: dónde va a escribir la UI los nombres de las zonas."""
    d = ImageDraw.Draw(img, "RGBA")
    font = ImageFont.truetype(os.path.join(FONTS, "ShipporiMinchoB1-ExtraBold.ttf"), 64)
    names = {"hogar": "Hogar de Kaito", "campos": "Campos de Inaba", "bosque": "Linde del Bosque", "muralla": "La Muralla Kurokage",
             "jardin": "Jardín del Clan", "dojo": "Dojo Kurokage", "montana": "Montaña Kodoyama", "lago": "Aldea del Lago Kohan",
             "lago_cascada": "Cascada Kohan", "bambu": "Bosque de Bambú"}
    for zid, (x, z) in LABELS.items():
        px, py = to_px(x, z)
        d.text((px, py), names[zid], font=font, fill=(28, 22, 24, 235), anchor="mm")
    for cid, x, z, yaw in W.CHECKPOINTS:
        px, py = to_px(x, z)
        d.polygon([(px, py - 16), (px + 16, py), (px, py + 16), (px - 16, py)], fill=(230, 180, 60, 255), outline=(20, 16, 18, 255))


# ------------------------------------------------------------------------------------------- niebla
def mist(S=1024, seed=7):
    """Niebla de lo no explorado, repetible: R fibra del papel, G relleno de las nubes kasumi, B su contorno de
    tinta, A jirones chicos (segunda capa, más lenta). Son datos: se importa lineal."""
    rng = random.Random(seed)
    K = 2
    s = S * K
    fill = Image.new("L", (s, s), 0)
    d = ImageDraw.Draw(fill)

    def cloud(cx, cy, L, H):
        # banda larga de puntas redondeadas con el lomo festoneado (suyari-gasumi)
        bumps = max(3, int(L / (H * 0.9)))
        for ox in (-s, 0, s):
            for oy in (-s, 0, s):
                x0, y0 = cx - L / 2 + ox, cy + oy
                d.rounded_rectangle((x0, y0 - H * 0.35, x0 + L, y0 + H * 0.5), radius=H * 0.42, fill=255)
                for b in range(bumps):
                    bx = x0 + H * 0.5 + (L - H) * (b + 0.5) / bumps
                    br = H * rng.uniform(0.38, 0.55)
                    d.ellipse((bx - br * 1.3, y0 - H * 0.25 - br, bx + br * 1.3, y0 - H * 0.25 + br), fill=255)

    for i in range(7):
        cloud(rng.uniform(0, s), (i + rng.uniform(0.1, 0.9)) * s / 7, rng.uniform(0.35, 0.62) * s, rng.uniform(0.07, 0.1) * s)
    m = np.asarray(fill, np.float32) / 255 > 0.5
    er = ndimage.binary_erosion(m, iterations=int(3 * K), border_value=0)
    outline = (m & ~er).astype(np.float32)
    # el contorno cortado por el pincel y una segunda línea interior más tenue (la nube "en capas")
    er2 = ndimage.binary_erosion(m, iterations=int(16 * K))
    er3 = ndimage.binary_erosion(er2, iterations=int(2 * K))
    inner = (er2 & ~er3).astype(np.float32)
    brk = ndimage.gaussian_filter(np.random.RandomState(seed).rand(s, s).astype(np.float32), 9 * K, mode="wrap")
    brk = (brk - brk.min()) / (brk.max() - brk.min())
    outline = outline * ss(0.25, 0.45, brk) + inner * 0.45 * ss(0.4, 0.6, brk)
    fillv = ndimage.gaussian_filter(m.astype(np.float32), 2 * K, mode="wrap")
    wisps = np.zeros((s, s), np.float32)
    wd_ = Image.new("L", (s, s), 0)
    dw = ImageDraw.Draw(wd_)
    for _ in range(26):
        cx, cy, L = rng.uniform(0, s), rng.uniform(0, s), rng.uniform(0.08, 0.2) * s
        for ox in (-s, 0, s):
            for oy in (-s, 0, s):
                dw.rounded_rectangle((cx - L / 2 + ox, cy + oy, cx + L / 2 + ox, cy + oy + L * 0.08), radius=L * 0.04, fill=255)
    wisps = ndimage.gaussian_filter(np.asarray(wd_, np.float32) / 255, 3 * K, mode="wrap")
    fib = ndimage.gaussian_filter(np.random.RandomState(seed + 1).rand(s, s).astype(np.float32), (0.6 * K, 5 * K), mode="wrap")
    fib = (fib - fib.min()) / (fib.max() - fib.min())
    mott = ndimage.gaussian_filter(np.random.RandomState(seed + 2).rand(s, s).astype(np.float32), 60 * K, mode="wrap")
    mott = (mott - mott.min()) / (mott.max() - mott.min())
    r = np.clip(0.5 + (fib - 0.5) * 0.7 + (mott - 0.5) * 0.5, 0, 1)
    arr = np.stack([r, fillv, np.clip(outline, 0, 1), wisps], -1)
    img = Image.fromarray((arr * 255).astype(np.uint8), "RGBA").resize((S, S), Image.LANCZOS)
    return img


# ------------------------------------------------------------------------------------------- íconos
def icons():
    import build_ui_art as K   # mismo contorno de tinta y mismo guardado que el resto del kit

    m, d, s = K.canvas(128)
    # torii: dos postes, el travesaño de abajo (nuki) y el de arriba con las puntas levantadas (kasagi)
    d.polygon([(s * .04, s * .2), (s * .2, s * .26), (s * .8, s * .26), (s * .96, s * .2), (s * .93, s * .33), (s * .07, s * .33)], fill=255)
    d.rectangle((s * .16, s * .42, s * .84, s * .51), fill=255)
    for x in (.27, .73):
        d.polygon([(s * (x - .055), s * .3), (s * (x + .055), s * .3), (s * (x + .07), s * .95), (s * (x - .07), s * .95)], fill=255)
    d.rectangle((s * .46, s * .3, s * .54, s * .42), fill=255)
    K.save(K.outlined(m, 128, 7), "MapShrine", usage="santuario en el mapa (torii): oro rezado, papel visto, gris sin ver")
    m, d, s = K.canvas(128)
    # portal: espiral de pincel
    pts = []
    for i in range(220):
        t = i / 219
        a = t * math.tau * 2.3
        r = s * (0.06 + 0.38 * t)
        pts.append((s / 2 + math.cos(a) * r, s / 2 + math.sin(a) * r))
    d.line(pts, fill=255, width=int(s * 0.085), joint="curve")
    K.save(K.outlined(m, 128, 6), "MapPortal", usage="portal de vuelta al dojo en el mapa (teñir jade)")


# ------------------------------------------------------------------------------------------- salida
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--props", required=True, help="JSON de Tools/UI/world_map_data.py")
    ap.add_argument("--cache", default=None, help="carpeta para la grilla calculada (por defecto, junto al JSON)")
    ap.add_argument("--preview", default=None, help="carpeta para vistas previas (no escribe en Assets)")
    ap.add_argument("--labels", action="store_true", help="en la vista previa, dónde van los nombres")
    a = ap.parse_args()
    data = json.load(open(a.props))
    SIZES.update(data["sizes"])
    cache = a.cache or os.path.dirname(os.path.abspath(a.props))
    img = render(data["placed"], cache, a.preview, a.labels)
    if a.preview:
        os.makedirs(a.preview, exist_ok=True)
        img.save(os.path.join(a.preview, "map_full.jpg"), quality=90)
        img.resize((IW // 3, IH // 3), Image.LANCZOS).save(os.path.join(a.preview, "map_small.jpg"), quality=90)
        mist().save(os.path.join(a.preview, "mist.png"))
        print("vista previa ->", a.preview)
        return
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "WorldMap.jpg")
    img.save(p, quality=92, subsampling=0, optimize=True)
    # sin redondear a potencia de 2 (3096 x 2568 ya son múltiplos de 4) y con mips: a zoom 1 se ve a ~0.4x
    write_meta(p, texture_meta(mips=True, max_size=4096, compress=True).replace("nPOTScale: 1", "nPOTScale: 0")
               .replace("textureCompression: 1", "textureCompression: 2"), force=True)
    p = os.path.join(OUT, "WorldMapMist.png")
    mist().save(p, optimize=True)
    write_meta(p, texture_meta(mips=True, srgb=False, max_size=1024, compress=False, wrap_clamp=False, alpha_transparency=False), force=True)
    p = os.path.join(OUT, "WorldMap.json")
    json.dump({"version": 1, "image": [IW, IH], "bounds": [IX0, IX1, IZ0, IZ1], "world": [X0, X1, Z0, Z1],
               "paper": [round(float(v), 4) for v in PAPER],
               "labels": [{"id": k, "x": v[0], "z": v[1]} for k, v in LABELS.items()]}, open(p, "w"), indent=1)
    write_meta(p, TEXT_META, force=True)
    icons()
    print("mapa ->", os.path.relpath(OUT, ASSETS))


if __name__ == "__main__":
    main()
