"""
Mapa del mundo de Nindō (tecla M): una lámina de tinta sobre washi a la luz de la luna, hecha con los datos REALES
del mundo, y lo que necesita la UI para dibujar encima la niebla de lo no explorado.

No es una captura del juego: de noche, con la niebla y las luces del LightPool solo cerca de Kaito, un render cenital
sale oscuro y depende de la iluminación. Es una ilustración sumi-e que sale de lo mismo que arma el mundo:
  * alturas, agua, caminos y regiones: Tools/Blender/world/world_terrain.py + world_plan.py (Python puro);
  * cada árbol, roca, casa, farol y puente en su lugar: los props que ubica build_world.py (mismo sorteo),
    volcados por Tools/UI/world_map_data.py (corre en Blender).

Lenguaje del kit "Tinta y Bandana" bajo la luna: el papel y las aguadas se pintan de día y después pasan por la
"luz de luna" (menos saturación, tinte índigo, sombras azules, no negras); los faroles se agregan después, en oro, y
son lo único cálido: de noche el mapa se lee por sus luces, como el mundo. Sin texto horneado: los nombres de las
zonas, los santuarios y los jefes los pone la UI encima, solo lo descubierto.

Salida (Nindo/Assets/Nindo/Resources/UI):
  WorldMap.jpg       la lámina (516 x 428 m a 6 px/m = 3096 x 2568), sin borde: el borde rasgado de arriba y abajo
                     lo corta el shader Nindo/UI Map (los costados van contra las varillas del pergamino)
  WorldMapMist.png   niebla de lo no explorado, en datos (lineal), del tamaño de la lámina a 4 px/m y sin costura:
                     R fibra del papel, G nubes de tinta, B líneas de las nubes kasumi (cada banda en un solo lugar),
                     A ruido suave para deformar el borde
  WorldMap.json      geometría de la lámina y de la grilla de niebla (C# la lee: una sola fuente), dónde va el nombre
                     de cada zona, las celdas que se pueden descubrir caminando (para el %), el agua abierta, de
                     qué lado de las puertas cae cada celda y, para las partidas viejas sin niebla guardada, qué
                     revela cada flag de la historia
  MapKaito.png       Kaito: punta de flecha dorada con las dos colas de la bandana
  MapShrine.png      santuario (torii): blanco con contorno de tinta, se tiñe
  MapPortal.png      portal de vuelta al dojo (espiral), se tiñe
  MapRod.png         varilla del pergamino del mapa (9-slice vertical)
  MapShadow.png      sombra suave de la lámina (9-slice)

Uso:
  blender -b --factory-startup --python Tools/UI/world_map_data.py -- <scratch>/map_props.json   (una vez por cambio del mundo)
  python Tools/UI/build_world_map.py --props <scratch>/map_props.json [--preview CARPETA [--ppm 3]] [--no-assets] [--reuse-sheet]
Con --preview deja la lámina, la niebla en tres estados de exploración y la maqueta de la pantalla del mapa en 16:9,
21:9 y 4:3 (la niebla se compone con la MISMA cuenta que el shader: Nindo/UI Map).

Cuándo rehacerla: la lámina es una foto del mundo. Cualquier cambio de Tools/Blender/world (world_plan, build_world.py,
los props y sus manifest_*.json: un portón nuevo, un incienso, un sello en la muralla) no aparece en el mapa hasta
volver a correr los dos pasos de arriba y commitear WorldMap.jpg / WorldMap.json (los .meta y sus GUID no cambian).
Si el encuadre de la lámina (MAP_BOUNDS) o la celda cambian, las nieblas guardadas se descartan solas (prefijo de la
grilla) y esas partidas arrancan como las de antes del mapa.
"""
import argparse
import base64
import hashlib
import json
import math
import os
import random
import sys
import time
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
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

# ------------------------------------------------------------------------------------------- geometría (la lee C#)
X0, X1, Z0, Z1 = W.MAP_BOUNDS               # lo que cubre el terreno
MARGIN = 14                                 # papel alrededor (m): ahí va el borde rasgado
IX0, IX1, IZ0, IZ1 = X0 - MARGIN, X1 + MARGIN, Z0 - MARGIN, Z1 + MARGIN
SHEET_W, SHEET_H = IX1 - IX0, IZ1 - IZ0     # 516 x 428 m
CELL = 4.0                                  # celda de la niebla (m): 129 x 107 celdas, 1726 bytes en la partida
GW, GH = int(SHEET_W / CELL), int(SHEET_H / CELL)
# radio que descubre Kaito al caminar: la cámara de juego (52°, 24 m, FOV 30) ve hasta 17.8 m en las esquinas de
# lejos en 16:9 (19 m a los costados en 21:9, 15 m en 4:3). Con 16 lo que se veía en el borde de la pantalla quedaba
# en la niebla del mapa ("eso lo vi"); con 20 mostraba el doble de lo que se vio. Del otro lado de una puerta cerrada
# no se descubre nada con ningún radio (side_masks)
REVEAL_R = 18.0
# celdas "descubribles" (el 100 %): alguna parte a <= 8 m de lo transitable. Con el radio de 18 queda margen para
# no tener que pegarse a cada borde: recorriendo caminos y claros (la vista previa) se llega al 100 %
REACH_D = 8.0
# el agua abierta no la tapa nada: desde la orilla se ve el lago entero, se descubre hasta WATER_R (y cuenta para el
# 100 % la que queda a menos de WATER_REACH de lo transitable). Si no, el lago Kohan era un tubo alrededor de la pasarela
WATER_R, WATER_REACH = 34.0, 24.0
# las puertas que cierran lo que hay detrás (world_plan.DOORS): con la puerta cerrada no se descubre del otro lado.
# Tres lados: el sur de la muralla, el norte y el patio del dojo (detrás del portón, sobre la meseta)
DOJO_GATE_Z, DOJO_X = 112.6, (-80.0, 50.0)
GATE_FLAGS = ["wall_gate_open", "dojo_open"]
# la niebla (WorldMapMist) cubre la lámina entera una sola vez, a 4 texeles por metro: las bandas kasumi son únicas
# (repetida cada 262 m, cada banda salía dos veces por renglón y la niebla parecía un empapelado). Las nubes y la
# fibra se leen de la misma textura a otras escalas (MIST_K veces por lámina), que no se alinean entre sí
MIST_PPM = 4.0
MIST_K = (2.69, 1.58)
assert GW * CELL == SHEET_W and GH * CELL == SHEET_H

# ------------------------------------------------------------------------------------------- resolución
PPM = 6.0
IW = IH = 0


def configure(ppm):
    """Píxeles por metro de la lámina (la vista previa rápida usa menos; los sellos se escalan con esto)."""
    global PPM, IW, IH
    PPM = float(ppm)
    IW, IH = int(round(SHEET_W * PPM)), int(round(SHEET_H * PPM))


configure(6.0)

PAPER = np.array([0.925, 0.884, 0.790], np.float32)       # washi de día (después pasa por la luz de luna)
INK = np.array([0.105, 0.090, 0.095], np.float32)         # sumi caliente
REGIONS = ["hogar", "campos", "bosque", "jardin", "dojo", "montana", "lago", "bambu"]
# aguadas por región (multiplican el papel): suelo abierto y bosque
TINT = {
    "hogar":   ((0.955, 0.935, 0.840), (0.66, 0.72, 0.60)),
    "campos":  ((0.965, 0.935, 0.820), (0.68, 0.73, 0.60)),
    "bosque":  ((0.900, 0.915, 0.840), (0.56, 0.64, 0.56)),
    "jardin":  ((0.930, 0.950, 0.860), (0.64, 0.72, 0.62)),
    "dojo":    ((0.905, 0.890, 0.900), (0.62, 0.62, 0.68)),
    "montana": ((1.040, 1.060, 1.110), (0.84, 0.88, 0.96)),
    "lago":    ((0.925, 0.945, 0.880), (0.64, 0.72, 0.64)),
    "bambu":   ((0.900, 0.955, 0.860), (0.60, 0.74, 0.58)),
}
# luz de luna: cuánto color queda, tinte, piso índigo de las sombras y ganancia
MOON_SAT, MOON_TINT, MOON_FLOOR, MOON_GAIN = 0.62, np.array([0.80, 0.85, 0.95], np.float32), np.array([0.012, 0.020, 0.050], np.float32), 0.86
LAMP_GLOW = np.array([0.46, 0.30, 0.07], np.float32)      # resplandor (se suma después de la luna)

# dónde va el nombre de cada zona (lo escribe la UI con el título de la Zone): (x, z, alineación, chico). Un nombre
# mide ~120 m a la escala del mapa y los pasillos (el bosque, el paso de la montaña) tienen 30: van al costado, sobre
# la niebla o el bosque, sin tapar caminos, santuarios ni jefes. Alineación: -1 el texto termina en x, 0 centrado,
# 1 empieza en x. Chico: un lugar dentro de una región (la muralla, la cascada). Giro (grados, antihorario como el
# eje z de la UI): la montaña es una cresta en diagonal sin lugar para un nombre derecho (al costado quedaba en el
# renglón del jardín y se leía "Montaña Kodoyama Jardín del Clan"); va a lo largo de la cresta, del lado de la niebla,
# como se rotulan las cordilleras. La vista previa avisa si un nombre pisa a otro o a una marca (check_labels)
LABELS = {
    "hogar": (-36, -193, 0, 0), "campos": (56, -128, 1, 0), "bosque": (-14, -62, -1, 0), "muralla": (22, -39, 1, 1),
    "jardin": (-34, 41, 0, 0), "dojo": (0, 181, 0, 0), "montana": (-175, 48, 0, 0, -34.5), "lago": (128, -20, 0, 0),
    "lago_cascada": (186, 95, 0, 1), "bambu": (116, 127, 1, 0),
}


def label(v):
    """(x, z, alineación, chico, giro) de una entrada de LABELS (el giro es opcional)."""
    return tuple(v) + (0.0,) * (5 - len(v))


# el nombre va al costado de su zona, muchas veces sobre la niebla: aparece cuando ya se vio el corazón de la zona
# (un área transitable de world_plan.AREAS), no apenas se pisa su borde. Al entrar a los campos su nombre flotaba
# 42 m adentro de la niebla, sin nada debajo
LABEL_ANCHOR = {
    "hogar": "hogar", "campos": "campos_e", "bosque": "bosque_claro", "muralla": "muralla_s", "jardin": "jardin_c",
    "dojo": "dojo_patio", "montana": "mont_arena", "lago": "lago_orilla", "lago_cascada": "lago_jefe", "bambu": "bambu_claro",
}

# partidas de antes del mapa (sin niebla guardada): lo que cada flag prueba que Kaito ya recorrió. Caminos de
# world_plan.PATHS (nombre, desde, hasta: índices de sus puntos) y áreas de world_plan.AREAS; con cualquiera de los
# flags se revela todo el tramo. Así una partida a mitad del juego no abre el mapa entero en niebla
LEGACY = [
    (["intro_done"], [("camino_hogar", 0, 1)], ["hogar", "hogar_patio"]),
    (["zone_campos", "enc_fields1"], [("camino_hogar", 0, 5)], ["campos_o", "campos_e", "campos_n"]),
    (["zone_bosque", "enc_forest1", "forest_seen"], [("camino_hogar", 0, 8)], ["bosque_claro"]),
    (["zone_muralla", "enc_wall"], [("camino_hogar", 0, 9)], ["muralla_s"]),
    (["zone_jardin", "wall_gate_open"], [("camino_hogar", 0, 9), ("camino_jardin", 0, 3)], ["muralla_n", "jardin_c"]),
    (["enc_garden1"], [("rodeo_jardin_o", 0, 2)], ["jardin_o"]),
    (["enc_garden2"], [("rodeo_jardin_e", 0, 2)], ["jardin_e"]),
    (["sumo_intro", "enc_sumo"], [("camino_jardin", 0, 5)], ["jardin_n", "jardin_ne", "jardin_no"]),
    (["dojo_gate_seen", "enc_dojo_guards"], [("camino_jardin", 0, 6)], ["dojo_puerta"]),
    (["zone_montana"], [("camino_oeste", 0, 4)], ["mont_base"]),
    (["enc_mountain1"], [("camino_oeste", 0, 4), ("subida_monte", 0, 3)], ["mont_arena"]),
    (["enc_mountain2"], [("paso_monte", 0, 2)], ["mont_paso"]),
    (["boss_seen_goro", "boss_goro"], [("paso_monte", 0, 4)], ["mont_cumbre"]),
    (["zone_lago"], [("camino_este", 0, 3)], ["lago_entrada"]),
    (["enc_lake1"], [("camino_este", 0, 5)], ["lago_orilla"]),
    (["enc_lake2"], [("pasarela_lago", 0, 3)], []),
    (["boss_seen_mizuchi", "boss_mizuchi"], [("pasarela_lago", 0, 5)], ["lago_jefe"]),
    (["zone_bambu"], [("camino_ne", 0, 3)], ["bambu_entrada"]),
    (["enc_bamboo1"], [("camino_ne", 0, 5)], ["bambu_claro"]),
    (["boss_seen_ozeki", "boss_ozeki"], [("camino_ne", 0, 8)], ["bambu_arena"]),
    (["dojo_open", "zone_dojo"], [("dojo_subida", 0, 1)], ["dojo_patio", "dojo_fondo"]),
]
# hasta qué lado de las puertas llega lo que prueba cada entrada (0 el sur de la muralla, 1 el norte, 2 el patio del
# dojo; side_of): haber llegado a la muralla no es haberla cruzado. El último punto del camino_hogar (z -26) ya está
# del lado de adentro y, con el portón cerrado, revelaba el jardín. MapFog también lo mira desde el santuario
LEGACY_SIDE = {"zone_muralla": 0, "dojo_gate_seen": 1}


def to_px(x, z):
    return (x - IX0) * PPM, (IZ1 - z) * PPM


# ------------------------------------------------------------------------------------------- grilla del mundo (1 m)
GW1, GH1 = SHEET_W, SHEET_H


def _row(j):
    z = IZ1 - 0.5 - j
    h = np.zeros(GW1, np.float32); wd = np.zeros(GW1, np.float32); pd = np.zeros(GW1, np.float32)
    sd = np.zeros(GW1, np.float32); lk = np.zeros(GW1, np.float32); rg = np.zeros(GW1, np.int8)
    for i in range(GW1):
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
    with Pool(max(1, min(8, (os.cpu_count() or 4) - 2))) as pool:
        rows = pool.map(_row, range(GH1))
    g = {k: np.stack([r[i] for r in rows]) for i, k in enumerate(("h", "wd", "pd", "sd", "lake", "reg"))}
    np.savez_compressed(path, **g)
    print(f"grilla {GW1}x{GH1} en {time.time() - t:.1f} s -> {path}")
    return g


def _np_hash(ix, iz, seed):
    """world_terrain._hash con enteros de numpy (mismos bits: & 0xFFFFFFFF sobre int64 da el complemento a dos)."""
    h = (ix * 374761393 + iz * 668265263 + seed * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFFFF) / float(0xFFFFFF)


def _np_vnoise(x, z, seed):
    ix, iz = np.floor(x).astype(np.int64), np.floor(z).astype(np.int64)
    fx, fz = x - ix, z - iz
    ux, uz = fx * fx * (3 - 2 * fx), fz * fz * (3 - 2 * fz)
    a, b = _np_hash(ix, iz, seed), _np_hash(ix + 1, iz, seed)
    c, d = _np_hash(ix, iz + 1, seed), _np_hash(ix + 1, iz + 1, seed)
    return (a + (b - a) * ux) * (1 - uz) + (c + (d - c) * ux) * uz


def _np_fbm(x, z, seed, octaves=4):
    v, a, f = np.zeros_like(x), 0.5, 1.0
    for i in range(octaves):
        v += a * _np_vnoise(x * f, z * f, seed + i * 17)
        a *= 0.5; f *= 2.03
    return v


def seamless_heights(g):
    """Alturas para el relieve del mapa sin las costuras de las regiones. world_terrain.height levanta los cerros de
    afuera con un tope y una pendiente por región (26 m en la montaña, 10 u 8 en el resto): en el juego esos escalones
    quedan detrás de los árboles, pero el sombreado del mapa los dibujaba como rectas (x -80, z -78, z 95). Se rehace
    esa misma cuenta con los topes mezclados entre regiones y se cambia solo esa parte (los lagos, los arroyos y los
    arrozales quedan como estaban)."""
    zs = IZ1 - 0.5 - np.arange(GH1, dtype=np.float64)[:, None] + np.zeros((1, GW1))
    xs = IX0 + 0.5 + np.arange(GW1, dtype=np.float64)[None, :] + np.zeros((GH1, 1))
    wd, reg = g["wd"].astype(np.float64), g["reg"]
    mont, mid = reg == REGIONS.index("montana"), np.isin(reg, [REGIONS.index(r) for r in ("bosque", "bambu", "dojo")])
    rise_max_a = np.where(mont, 26.0, np.where(mid, 10.0, 8.0))
    steep_a = np.where(mont, 2.2, 1.5)
    rise_max_b = ndimage.gaussian_filter(rise_max_a, 14.0, mode="nearest")
    steep_b = ndimage.gaussian_filter(steep_a, 14.0, mode="nearest")
    n = _np_fbm(xs * 0.035, zs * 0.035, 11)
    extra = (_np_fbm(xs * 0.12, zs * 0.12, 5) - 0.5) * 2.0 * np.clip(wd / 8.0, 0, 1) ** 2 * (3 - 2 * np.clip(wd / 8.0, 0, 1))
    rise_a = np.maximum(0.0, np.minimum(wd * steep_a, rise_max_a * (0.6 + 0.8 * n)) + extra)
    rise_b = np.maximum(0.0, np.minimum(wd * steep_b, rise_max_b * (0.6 + 0.8 * n)) + extra)
    keep = (wd <= 0) | (g["lake"] > 0.5) | (g["sd"] < 2.0)
    for r in W.PADDIES:
        keep |= (xs >= r[0]) & (xs <= r[2]) & (zs >= r[1]) & (zs <= r[3])
    return np.where(keep, g["h"], g["h"] - rise_a + rise_b).astype(np.float32)


def up(a, mode=Image.BICUBIC):
    """Campo de 1 m -> píxeles de la lámina (los centros coinciden)."""
    return np.asarray(Image.fromarray(np.ascontiguousarray(a, np.float32), "F").resize((IW, IH), mode))


# ------------------------------------------------------------------------------------------- ruido
def vnoise(cell_px, seed, w=None, h=None):
    w = IW if w is None else w
    h = IH if h is None else h
    rs = np.random.RandomState(seed)
    gw, gh = int(w / cell_px) + 3, int(h / cell_px) + 3
    g = rs.rand(gh, gw).astype(np.float32)
    big = Image.fromarray(g, "F").resize((int(round(gw * cell_px)), int(round(gh * cell_px))), Image.BICUBIC)
    return np.asarray(big)[:h, :w]


def fbm(cell_px, seed, octaves=4, w=None, h=None):
    w = IW if w is None else w
    h = IH if h is None else h
    v = np.zeros((h, w), np.float32); a, tot = 1.0, 0.0
    for o in range(octaves):
        v += a * vnoise(max(1.5, cell_px / (2 ** o)), seed + 31 * o, w, h)
        tot += a; a *= 0.5
    return v / tot


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def m2px(m):
    """Metros -> píxeles de la lámina (los ruidos de arriba se dan en píxeles de la lámina de 6 px/m)."""
    return m * PPM


# ------------------------------------------------------------------------------------------- sellos (stamps)
SS = 4   # supersampling de cada sello


class Stamps:
    """Capas donde se 'estampan' árboles, casas y faroles: la tinta, su sombra (se desenfoca), el resplandor de los
    faroles y los puntos de luz (los dos últimos van después de la luna: son lo único cálido)."""

    def __init__(self):
        self.ink = Image.new("RGBA", (IW, IH), (0, 0, 0, 0))
        self.shadow = Image.new("L", (IW, IH), 0)
        self.glow = Image.new("L", (IW, IH), 0)
        self.lamps = Image.new("RGBA", (IW, IH), (0, 0, 0, 0))

    def _paste(self, layer, img, x, z):
        w, h = img.size[0] // SS, img.size[1] // SS
        if w < 1 or h < 1:
            return None
        small = img.resize((w, h), Image.LANCZOS)
        px, py = to_px(x, z)
        ox, oy = int(round(px - w / 2)), int(round(py - h / 2))
        sx0, sy0 = max(0, -ox), max(0, -oy)
        sx1, sy1 = min(w, IW - ox), min(h, IH - oy)
        if sx1 > sx0 and sy1 > sy0:
            layer.alpha_composite(small, (ox + sx0, oy + sy0), (sx0, sy0, sx1, sy1))
        return small, ox, oy, w, h

    def put(self, img, x, z, shadow=0.0, shadow_off=(0.35, 0.5)):
        """img: RGBA a SS x; (x, z) centro en metros. shadow: opacidad de la sombra (al sureste: la luna del noroeste)."""
        r = self._paste(self.ink, img, x, z)
        if r is None or shadow <= 0:
            return
        small, ox, oy, w, h = r
        a = small.getchannel("A").point(lambda v: int(v * shadow))
        rr = max(w, h) / 2
        self.shadow.paste(Image.new("L", a.size, 255), (ox + int(rr * shadow_off[0]), oy + int(rr * shadow_off[1])), a)

    def light(self, x, z, r_m, core_m):
        px, py = to_px(x, z)
        d = ImageDraw.Draw(self.glow)
        r_px = r_m * PPM
        d.ellipse((px - r_px, py - r_px, px + r_px, py + r_px), fill=255)
        self._paste(self.lamps, dot(core_m * PPM, (1.0, 0.82, 0.46), 1.0, rim=(0.32, 0.20, 0.08)), x, z)


def canvas(r_px, pad=1.6):
    s = int(math.ceil(r_px * 2 * pad)) * SS + SS * 2
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), s / 2.0


def col8(c, a=1.0):
    return (int(min(1, c[0]) * 255), int(min(1, c[1]) * 255), int(min(1, c[2]) * 255), int(a * 255))


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
    """Pino o cedro visto desde arriba: estrella de agujas de tinta, el centro más cargado, la luz del noroeste."""
    img, d, c = canvas(r)
    R = r * SS
    n = rng.randint(9, 13)
    ph = rng.random() * math.tau
    pts = []
    for i in range(n * 2):
        a = ph + i / (n * 2) * math.tau
        rr = R * (rng.uniform(0.9, 1.08) if i % 2 == 0 else rng.uniform(0.48, 0.62))
        pts.append((c + math.cos(a) * rr, c + math.sin(a) * rr))
    d.polygon(pts, fill=col8(tip, 0.94))
    pts2 = []
    for i in range(n * 2):
        a = ph + (i + 0.5) / (n * 2) * math.tau
        rr = R * (rng.uniform(0.62, 0.72) if i % 2 == 0 else rng.uniform(0.32, 0.4))
        pts2.append((c + math.cos(a) * rr, c + math.sin(a) * rr))
    d.polygon(pts2, fill=col8(body, 0.96))
    if snow:
        for i in range(n):
            a = ph + i / n * math.tau
            if math.cos(a + math.pi * 0.75) < -0.1:
                continue
            rr = R * rng.uniform(0.45, 0.75)
            x, y = c + math.cos(a) * rr, c + math.sin(a) * rr
            d.ellipse((x - R * 0.13, y - R * 0.1, x + R * 0.13, y + R * 0.1), fill=(238, 242, 248, 235))
        d.ellipse((c - R * 0.32, c - R * 0.32, c - R * 0.06, c - R * 0.06), fill=(244, 247, 252, 240))
    else:
        # brillo de luna en las agujas del noroeste y el corazón casi negro
        hl = tuple(min(1.0, v * 1.45 + 0.05) for v in tip)
        d.pieslice((c - R * 0.9, c - R * 0.9, c + R * 0.9, c + R * 0.9), 190, 260, fill=col8(hl, 0.32))
        d.ellipse((c - R * 0.12, c - R * 0.12, c + R * 0.12, c + R * 0.12), fill=col8(INK, 0.9))
    return img


def stamp_round(r, rng, fill, rim, dots=None):
    """Copa redonda en aguada: borde más oscuro abajo a la derecha, luz arriba a la izquierda (luna)."""
    img, d, c = canvas(r)
    R = r * SS
    blob(d, c + R * 0.06, c + R * 0.08, R * 1.0, rng, fill=col8(rim, 0.92))
    blob(d, c - R * 0.04, c - R * 0.04, R * 0.86, rng, fill=col8(fill, 0.96))
    blob(d, c - R * 0.28, c - R * 0.3, R * 0.38, rng, fill=col8(np.minimum(np.array(fill) * 1.14, 1), 0.7))
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
        d.line([(x, y), (x + math.cos(ang) * L, y + math.sin(ang) * L)], fill=col8((0.34 * g, 0.50 * g, 0.30 * g), 0.88), width=max(1, int(SS * 1.3 * PPM / 6)))
    for _ in range(int(4 + r * 0.6)):
        a, rr = rng.random() * math.tau, R * math.sqrt(rng.random()) * 0.55
        x, y = c + math.cos(a) * rr, c + math.sin(a) * rr
        s = R * 0.09
        d.ellipse((x - s, y - s, x + s, y + s), fill=col8((0.22, 0.30, 0.18), 0.96))
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
    for _ in range(rng.randint(3, 4)):
        branch(c, c, rng.random() * math.tau, R * 0.55, SS * 1.6 * PPM / 6, 2)
    return img


def stamp_rock(r, rng, fill=(0.58, 0.57, 0.58), snow=False, dark=False):
    img, d, c = canvas(r)
    R = r * SS
    n = rng.randint(5, 7)
    ph = rng.random() * math.tau
    pts = [(c + math.cos(ph + i / n * math.tau) * R * rng.uniform(0.75, 1.0), c + math.sin(ph + i / n * math.tau) * R * rng.uniform(0.75, 1.0)) for i in range(n)]
    d.polygon(pts, fill=col8(INK, 0.9))
    inner = [(c + (x - c) * 0.78 - R * 0.06, c + (y - c) * 0.78 - R * 0.08) for x, y in pts]
    d.polygon(inner, fill=col8((0.30, 0.30, 0.33) if dark else fill, 1.0))
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


SLATE, SLATE_RIDGE = (0.34, 0.35, 0.41), (0.62, 0.62, 0.66)


def stamp_roof(sx, sz, yaw, color=SLATE, ridge=SLATE_RIDGE, gold=False, hip=True):
    """Techo visto desde arriba (sx ancho, sz fondo, en metros): faldones de pizarra con contorno de tinta, la
    cumbrera y las limatesas claras. Antes eran cuadrados negros: se leían como agujeros en el papel."""
    w, h = sx * PPM * SS, sz * PPM * SS
    pad = SS * 4
    img = Image.new("RGBA", (int(w + pad * 2), int(h + pad * 2)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = pad, pad, pad + w, pad + h
    lw = max(1, int(SS * 1.1 * PPM / 6))
    d.rectangle((x0 - lw, y0 - lw, x1 + lw, y1 + lw), fill=col8(INK, 0.95))
    d.rectangle((x0, y0, x1, y1), fill=col8(color, 1.0))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    # el faldón del sureste en sombra (la luna está al noroeste)
    if w >= h:
        d.polygon([(x0, y1), (x1, y1), (cx + (w - h) / 2, cy), (cx - (w - h) / 2, cy)], fill=col8(np.array(color) * 0.78, 1.0))
    else:
        d.polygon([(x1, y0), (x1, y1), (cx, cy + (h - w) / 2), (cx, cy - (h - w) / 2)], fill=col8(np.array(color) * 0.78, 1.0))
    if hip:
        if w >= h:
            a, b = (cx - (w - h) / 2, cy), (cx + (w - h) / 2, cy)
            corners = (((x0, y0), a), ((x0, y1), a), ((x1, y0), b), ((x1, y1), b))
        else:
            a, b = (cx, cy - (h - w) / 2), (cx, cy + (h - w) / 2)
            corners = (((x0, y0), a), ((x1, y0), a), ((x0, y1), b), ((x1, y1), b))
        d.line([a, b], fill=col8(ridge, 0.95), width=lw * 2)
        for p, q in corners:
            d.line([p, q], fill=col8(ridge, 0.75), width=lw)
        if gold:
            d.line([a, b], fill=(232, 190, 92, 255), width=lw)
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
    d.line([(pad, cy), (pad + w, cy)], fill=col8(INK, 1.0), width=int(SS * 3.6))
    d.line([(pad, cy), (pad + w, cy)], fill=col8(color, 1.0), width=int(SS * 2.4))
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


def dot(r_px, color, a=1.0, rim=None):
    s = int(math.ceil(r_px * 2 + 4)) * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, R = s / 2, r_px * SS
    if rim is not None:
        d.ellipse((c - R - SS, c - R - SS, c + R + SS, c + R + SS), fill=col8(rim, a))
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
LAMPS = {"lantern_post": (2.4, 0.30), "lantern_stone": (2.0, 0.28), "lantern_stone_tall": (2.6, 0.32), "torch_brazier": (3.0, 0.36),
         "brazier_kage": (3.4, 0.42), "campfire": (3.8, 0.46)}
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
            st.put(stamp_round(rp * 0.78, rng, (0.92, 0.66, 0.73), (0.66, 0.40, 0.48), dots=(0.98, 0.84, 0.88)), x, z, shadow=0.45)
        elif pid == "tree_maple_a":
            st.put(stamp_round(rp * 0.78, rng, (0.80, 0.42, 0.26), (0.52, 0.22, 0.15), dots=(0.90, 0.62, 0.30)), x, z, shadow=0.45)
        elif pid == "tree_dead_a":
            st.put(stamp_dead(rp * 0.7, rng), x, z, shadow=0.2)
        elif pid.startswith("bamboo_cluster") or pid == "bamboo_young":
            st.put(stamp_bamboo(rp * (0.85 if pid != "bamboo_young" else 0.6), rng), x, z, shadow=0.35)
        elif pid in ("bush_round_a", "bush_round_b", "bush_round_c"):
            g = rng.uniform(0.92, 1.08)
            st.put(stamp_round(max(2.2 * PPM / 6, rp * 0.8), rng, (0.42 * g, 0.50 * g, 0.38 * g), (0.24, 0.31, 0.24)), x, z, shadow=0.35)
        elif pid == "bush_azalea_pink":
            st.put(stamp_round(max(2.2 * PPM / 6, rp * 0.8), rng, (0.90, 0.58, 0.70), (0.62, 0.34, 0.46), dots=(0.96, 0.78, 0.84)), x, z, shadow=0.35)
        elif pid == "bush_azalea_white":
            st.put(stamp_round(max(2.2 * PPM / 6, rp * 0.8), rng, (0.95, 0.94, 0.90), (0.62, 0.62, 0.60)), x, z, shadow=0.35)
        elif pid == "bush_snow":
            st.put(stamp_round(max(2.2 * PPM / 6, rp * 0.75), rng, (0.93, 0.95, 0.98), (0.60, 0.66, 0.76)), x, z, shadow=0.3)
        elif pid.startswith("flowers"):
            c = {"flowers_pink": (0.93, 0.56, 0.68), "flowers_yellow": (0.96, 0.80, 0.38), "flowers_blue": (0.52, 0.62, 0.86)}[pid]
            for _ in range(3):
                st.put(dot(rng.uniform(0.8, 1.3) * PPM / 6, c, 0.85), x + rng.uniform(-0.6, 0.6), z + rng.uniform(-0.6, 0.6))
        elif pid in ("tall_grass_patch", "reeds_patch"):
            img, d, cc = canvas(max(3.0 * PPM / 6, rp * 0.7))
            for _ in range(7):
                a = rng.random() * math.tau; rr = rp * 0.6 * SS * rng.random()
                xx, yy = cc + math.cos(a) * rr, cc + math.sin(a) * rr
                d.line([(xx, yy), (xx + rng.uniform(-2, 2) * SS * PPM / 6, yy - rng.uniform(2, 4) * SS * PPM / 6)], fill=col8((0.30, 0.36, 0.26), 0.8), width=SS)
            st.put(img, x, z)
        elif pid == "mushroom_cluster":
            st.put(dot(1.0 * PPM / 6, (0.55, 0.36, 0.26), 0.9), x, z)
        elif pid in ("rock_small_a", "rock_small_b", "rock_medium_a", "rock_medium_b", "rock_large_a", "rock_large_b", "stump", "log_fallen"):
            st.put(stamp_rock(max(1.6 * PPM / 6, rp * 0.85), rng), x, z, shadow=0.4)
        elif pid == "rock_snow_a":
            st.put(stamp_rock(max(1.8 * PPM / 6, rp * 0.85), rng, snow=True), x, z, shadow=0.4)
        elif pid == "rock_pillar":
            st.put(stamp_rock(rp * 0.9, rng, dark=True), x, z, shadow=0.6)
        elif pid.startswith("cliff"):
            st.put(stamp_cliff(rp * 0.75, rng, yaw, snow=pid == "cliff_c"), x, z, shadow=0.55)
        elif pid in LAMPS:
            glow_m, core_m = LAMPS[pid]
            st.light(x, z, glow_m, core_m)
        elif pid in ROOFS:
            s = size_of(pid)
            sx, sz = s[0] * sc, s[2] * sc
            if pid == "pagoda_small":
                st.put(stamp_roof(sx, sz, yaw), x, z, shadow=0.7, shadow_off=(0.6, 0.9))
                st.put(stamp_roof(sx * 0.62, sz * 0.62, yaw, color=(0.30, 0.30, 0.36)), x, z)
            elif pid == "shrine_small":
                st.put(stamp_roof(sx * 0.8, sz * 0.8, yaw, color=(0.66, 0.18, 0.13), ridge=(0.86, 0.42, 0.32)), x, z, shadow=0.6)
            elif pid == "temple_bell" or pid == "pavilion_azumaya":
                st.put(stamp_roof(min(sx, sz), min(sx, sz), yaw), x, z, shadow=0.6)
            elif pid == "wall_gate":
                st.put(stamp_roof(sx, sz * 0.8, yaw, color=(0.24, 0.22, 0.25), ridge=(0.52, 0.26, 0.20)), x, z, shadow=0.7)
            elif pid == "dojo_gate":
                st.put(stamp_roof(sx, sz, yaw, color=(0.22, 0.20, 0.24), ridge=(0.50, 0.44, 0.40), gold=True), x, z, shadow=0.7)
            else:
                # cada techo con su pizarra (iguales parecían el mismo sello repetido)
                g = rng.uniform(0.9, 1.1)
                st.put(stamp_roof(sx, sz, yaw, color=tuple(c * g for c in SLATE)), x, z, shadow=0.7, shadow_off=(0.45, 0.65))
        elif pid == "dojo_main":
            s = size_of(pid)
            st.put(stamp_roof(s[0], s[2], yaw, color=(0.22, 0.20, 0.24), ridge=(0.50, 0.44, 0.40), gold=True), x, z, shadow=0.8, shadow_off=(0.3, 0.45))
            st.put(stamp_roof(s[0] * 0.55, s[2] * 0.5, yaw, color=(0.27, 0.25, 0.29), ridge=(0.55, 0.48, 0.42), gold=True), x, z)
        elif pid == "wall_segment":
            s = size_of(pid)
            st.put(stamp_rect(s[0] * sc + 0.3, s[2] * sc, yaw, col8((0.24, 0.22, 0.23), 1.0), outline=col8(INK, 1.0), lines=2, line_col=col8((0.55, 0.50, 0.46), 1.0)), x, z, shadow=0.8, shadow_off=(0.05, 0.6))
        elif pid == "wall_post":
            s = size_of(pid)
            st.put(stamp_rect(s[0] * sc, s[2] * sc, yaw, col8((0.16, 0.14, 0.14), 1.0)), x, z, shadow=0.7)
        elif pid in ("torii_red", "torii_stone", "falls_shrine_gate", "arch_bamboo_gate"):
            s = size_of(pid)
            color = (0.80, 0.18, 0.12) if pid in ("torii_red", "falls_shrine_gate") else (0.45, 0.58, 0.36) if pid == "arch_bamboo_gate" else (0.58, 0.57, 0.58)
            st.put(stamp_torii(s[0] * sc, yaw, color), x, z, shadow=0.5)
        elif pid in ("bridge_arch", "bridge_plank", "boardwalk_segment", "dock_segment"):
            s = size_of(pid)
            sx, sz = s[0], s[2] * (sc if pid == "boardwalk_segment" else 1.0)
            if pid != "boardwalk_segment":
                sx *= sc; sz *= sc
            wood = (0.56, 0.42, 0.29)
            rail = (0.74, 0.20, 0.13) if pid == "bridge_arch" else (0.26, 0.18, 0.13)
            img = stamp_rect(sx, sz, 0, col8(wood, 1.0), outline=col8(rail, 1.0), lines=max(2, int(sz / 0.7)), line_col=col8((0.38, 0.28, 0.19), 1.0))
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
                     "shrine_checkpoint", "portal_ring", "scythe", "binding_post"):
            continue      # se dibujan aparte (arenas) o los pone la UI (santuarios, portales)
        else:
            # lo chico (pozo, carro, fardos, espantapájaros, estantes...): un punto de tinta de su tamaño
            s = size_of(pid)
            st.put(stamp_rect(max(0.5, s[0] * sc), max(0.5, s[2] * sc), yaw, col8((0.36, 0.30, 0.26), 0.95), outline=col8(INK, 0.9)), x, z, shadow=0.4)


# ------------------------------------------------------------------------------------------- arenas
def draw_arenas(st):
    """Patio del dojo (círculo de losas con su cordón) y plataforma del lago, con la herradura de la cascada."""
    K = 2
    big = Image.new("RGBA", (IW * K, IH * K), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)

    def P(x, z):
        px, py = to_px(x, z)
        return px * K, py * K

    cx, cz = W.COURTYARD_C
    r = W.COURTYARD_R * PPM * K
    x0, x1, za, zb = W.COURTYARD_APRON
    a0, a1 = P(x0, zb), P(x1, za)
    d.rectangle((a0[0], a0[1], a1[0], a1[1]), fill=(196, 192, 188, 255))
    px, py = P(cx, cz)
    d.ellipse((px - r, py - r, px + r, py + r), fill=(204, 200, 196, 255), outline=(40, 34, 36, 255), width=max(1, int(PPM * K * 0.45)))
    for rr in (0.72, 0.42):
        q = r * rr
        d.ellipse((px - q, py - q, px + q, py + q), outline=(120, 114, 114, 255), width=max(1, int(K * 2 * PPM / 6)))
    for k in range(16):
        ang = k / 16 * math.tau
        d.line([(px + math.cos(ang) * r * 0.42, py + math.sin(ang) * r * 0.42), (px + math.cos(ang) * r, py + math.sin(ang) * r)], fill=(140, 134, 132, 255), width=max(1, int(K * 1.5 * PPM / 6)))
    d.ellipse((px - r * 1.02, py - r * 1.02, px + r * 1.02, py + r * 1.02), outline=(214, 186, 120, 255), width=max(1, int(K * 2.2 * PPM / 6)))
    # plataforma del lago: octógono de tablones sobre el agua
    px, py = P(184, 72)
    R = 9.6 * PPM * K
    oct_ = [(px + math.cos(math.radians(22.5 + 45 * k)) * R, py + math.sin(math.radians(22.5 + 45 * k)) * R) for k in range(8)]
    d.polygon(oct_, fill=(146, 110, 80, 255), outline=(44, 30, 24, 255))
    for k in range(-9, 10, 1):
        y = py + k * PPM * K
        half = math.sqrt(max(0.0, R * R - (k * PPM * K) ** 2)) * 0.97
        d.line([(px - half, y), (px + half, y)], fill=(112, 82, 60, 255), width=K)
    d.line(oct_ + [oct_[0]], fill=(44, 30, 24, 255), width=max(1, int(K * 3 * PPM / 6)))
    # herradura de basalto de la cascada (falls_layout: radios y brazos) con sus cortinas de agua
    hx, hz = FALLS.HX, FALLS.HZ
    poly = []
    for b in np.linspace(-FALLS.STEP_END, FALLS.STEP_END, 80):
        e, n = FALLS.polar(FALLS.OUT_R, b)
        poly.append(P(hx + e, hz + n))
    for b in np.linspace(FALLS.STEP_END, -FALLS.STEP_END, 80):
        e, n = FALLS.polar(FALLS.LIP_R, b)
        poly.append(P(hx + e, hz + n))
    d.polygon(poly, fill=(40, 40, 48, 255))
    rng = random.Random(5)
    for _ in range(140):
        b = rng.uniform(-FALLS.STEP_END, FALLS.STEP_END); rr = rng.uniform(FALLS.LIP_R + 1, FALLS.OUT_R - 1)
        e, n = FALLS.polar(rr, b)
        a = P(hx + e, hz + n)
        e2, n2 = FALLS.polar(rr + rng.uniform(1.5, 3.5), b + rng.uniform(-6, 6))
        d.line([a, P(hx + e2, hz + n2)], fill=(84, 86, 98, 255), width=max(1, int(K * 2 * PPM / 6)))
    for name, b0, b1, layers in FALLS.SHEETS:
        for b in np.arange(b0, b1, 1.2):
            e, n = FALLS.polar(FALLS.LIP_R + 0.6, b)
            e2, n2 = FALLS.polar(FALLS.LIP_R - 2.6, b)
            d.line([P(hx + e, hz + n), P(hx + e2, hz + n2)], fill=(226, 236, 242, 255), width=max(1, int(K * 2 * PPM / 6)))
    small = big.resize((IW, IH), Image.LANCZOS)
    st.ink.alpha_composite(small)
    sh = small.getchannel("A")
    st.shadow.paste(Image.new("L", sh.size, 200), (int(PPM * 0.5), int(PPM * 0.7)), sh)


def lake_polygon_mask():
    """El lago a resolución de píxel (antes salía de la grilla de 1 m: la orilla este quedaba en escalones)."""
    K = 2
    m = Image.new("L", (IW * K, IH * K), 0)
    d = ImageDraw.Draw(m)
    d.polygon([(to_px(x, z)[0] * K, to_px(x, z)[1] * K) for x, z in W.LAKE], fill=255)
    for name, ax, az, r, h, soft in W.AREAS:
        if h is not None and T.point_in_poly(ax, az, W.LAKE):
            px, py = to_px(ax, az)
            d.ellipse(((px - r * PPM) * K, (py - r * PPM) * K, (px + r * PPM) * K, (py + r * PPM) * K), fill=0)
    return np.asarray(m.resize((IW, IH), Image.LANCZOS), np.float32) / 255


def hand_drawn(st, k6):
    """La tinta de los sellos como hecha a pincel y no a regla: (1) se deforma con un ruido suave de ±0.6 m cada ~6 m
    (la muralla deja de ser una recta, el círculo del patio del dojo y los techos dejan de ser perfectos; la sombra se
    deforma igual, así no se despega) y (2) los trazos oscuros se quiebran en pincel seco: huecos finos donde el pincel
    se quedaba sin tinta, en manchas, no en todo el trazo. Devuelve la tinta (RGBA 0..1) y la sombra (0..1)."""
    amp = m2px(0.6)
    dx = (fbm(36 * k6, 501, 3) - 0.5) * 2.0 * amp
    dy = (fbm(36 * k6, 502, 3) - 0.5) * 2.0 * amp
    yy, xx = np.mgrid[0:IH, 0:IW].astype(np.float32)
    yy += dy
    xx += dx
    del dx, dy
    src = np.asarray(st.ink, np.float32) / 255
    ink = np.empty_like(src)
    for c in range(4):
        ink[..., c] = ndimage.map_coordinates(src[..., c], (yy, xx), order=1, mode="constant", cval=0.0)
    del src
    shadow = ndimage.map_coordinates(np.asarray(st.shadow, np.float32) / 255, (yy, xx), order=1, mode="constant", cval=0.0)
    del yy, xx
    lum = (ink[..., :3] * np.array([0.299, 0.587, 0.114], np.float32)).sum(-1)
    dark = ss(0.36, 0.14, lum) * ink[..., 3]
    # las cerdas dejan rayas a lo largo de la pasada (de este a oeste, como la de las nubes), no puntos sueltos
    fine = ndimage.uniform_filter1d(vnoise(max(1.5, m2px(0.2)), 511), max(3, int(m2px(1.1))), axis=1)
    lo, hi = np.percentile(fine[::7, ::7], (2, 98))
    fine = (fine - lo) / (hi - lo + 1e-6)
    dry = ss(0.62, 0.86, fine) * ss(0.42, 0.72, vnoise(m2px(3.0), 512))
    ink[..., 3] *= 1.0 - 0.5 * dry * dark
    return ink, shadow


# ------------------------------------------------------------------------------------------- lámina
def moon_grade(col):
    """De día a luz de luna: menos color, tinte índigo, las sombras azules (no negras) y un poco más oscuro."""
    lum = (col * np.array([0.299, 0.587, 0.114], np.float32)).sum(-1, keepdims=True)
    c = lum + (col - lum) * MOON_SAT
    c = c * MOON_TINT + (1 - np.clip(lum, 0, 1)) * MOON_FLOOR
    return c * MOON_GAIN


def render(props, cache_dir):
    t0 = time.time()
    g = world_grid(cache_dir)
    hs = seamless_heights(g)
    h = up(hs); wd = up(g["wd"]); pd = up(g["pd"]); sd = up(g["sd"])
    print(f"campos {time.time() - t0:.1f} s")
    gy, gx = np.gradient(hs)           # filas = sur (z baja), columnas = este
    gx, gy = up(gx), up(-gy)                                   # dh/dx (este), dh/dz (norte), en m/m
    grad = np.sqrt(gx * gx + gy * gy)
    k6 = PPM / 6.0                                             # los ruidos se pensaron a 6 px/m

    # ---- papel
    fib = vnoise(1.2 * k6, 3) * 0.5 + vnoise(4 * k6, 4) * 0.5
    fibers = np.asarray(Image.fromarray((np.random.RandomState(9).rand(IH, max(8, int(IW / (18 * k6)))) * 255).astype(np.uint8), "L").resize((IW, IH), Image.BICUBIC), np.float32) / 255
    mottle = fbm(260 * k6, 11, 4)
    paper = PAPER[None, None, :] * (0.965 + 0.05 * mottle[..., None] + 0.018 * (fib[..., None] - 0.5) + 0.02 * (fibers[..., None] - 0.5))
    col = paper.copy()

    # ---- tierra pintada: hasta un poco más allá del bosque, con el borde de aguada irregular
    edge_n = fbm(140 * k6, 21, 4)
    lake_poly = lake_polygon_mask()
    land = ss(42.0, 26.0, wd + (edge_n - 0.5) * 18.0)
    land = np.maximum(land, ss(0.2, 0.8, lake_poly) * ss(34, 12, wd))
    open_t = np.zeros((IH, IW, 3), np.float32); forest_t = np.zeros((IH, IW, 3), np.float32)
    reg = g["reg"]
    # las regiones son rectángulos: mezcladas con un desenfoque solo, sus bordes largos se leían como rectas (la
    # nieve de la montaña cortada en x -80). Cada peso lleva su propio ruido y se renormaliza: el borde serpentea
    wts = []
    for k in range(len(REGIONS)):
        n = ndimage.gaussian_filter(np.random.RandomState(200 + k).rand(GH1, GW1).astype(np.float32), 9.0)
        n = (n - n.min()) / (n.max() - n.min() + 1e-9)
        wts.append(ndimage.gaussian_filter((reg == k).astype(np.float32), 12.0) * (0.35 + 1.3 * n))
    tot = np.maximum(sum(wts), 1e-6)
    for k, name in enumerate(REGIONS):
        m = up(wts[k] / tot)
        open_t += m[..., None] * np.array(TINT[name][0], np.float32)
        forest_t += m[..., None] * np.array(TINT[name][1], np.float32)
        del m
    del wts, tot
    wash_n = fbm(90 * k6, 31, 4)
    forest = ss(0.8, 7.0, wd) * (0.8 + 0.4 * wash_n)
    walk = ss(1.0, -1.5, wd)
    tint = open_t * (1 - forest[..., None]) + forest_t * forest[..., None]
    del open_t, forest_t
    tint = tint * (1 + 0.04 * walk[..., None])
    col = col * (1 + (tint - 1) * land[..., None])
    del tint
    # pasto en lo abierto: punteado corto de pincel (la decoración de matas son miles y no viene en los datos). Sin
    # esto los claros grandes del jardín quedaban como papel liso
    stip = ss(0.62, 0.70, vnoise(0.55 * PPM, 17)) * ss(0.3, 0.7, vnoise(6 * PPM, 18))
    open_ground = land * ss(4.0, -2.0, wd)
    col = col * (1 - 0.10 * (stip * open_ground)[..., None] * np.array([1.0, 0.8, 1.0], np.float32))
    del stip, open_ground
    mont = up(ndimage.gaussian_filter((reg == REGIONS.index("montana")).astype(np.float32), 6.0))

    # ---- relieve: luz de luna del noroeste; sombras frías
    L = np.array([-0.55, 0.55, 0.63], np.float32); L /= np.linalg.norm(L)
    nz = 1.0 / np.sqrt(gx * gx + gy * gy + 1.0)
    shade = np.clip(((-gx * L[0] - gy * L[1]) * nz + nz * L[2] - L[2]) * 1.6, -1, 1)   # 0 en lo plano
    k_relief = (0.34 + 0.4 * mont) * land
    shadow_col = np.array([0.62, 0.66, 0.78], np.float32)
    dark = np.clip(-shade, 0, 1)[..., None] * k_relief[..., None]
    col = col * (1 - dark * (1 - shadow_col))
    col = col + np.clip(shade, 0, 1)[..., None] * k_relief[..., None] * 0.08
    del dark
    # curvas de nivel finas cada 2.5 m, cortadas por el pincel seco
    c = h / 2.5
    dpx = np.abs((c - 0.5) % 1.0 - 0.5) / np.maximum(grad / 2.5 / PPM, 1e-3)
    contour = (1 - ss(0.35, 1.25, dpx)) * ss(0.6, 2.0, h) * land * ss(0.35, 0.6, vnoise(22 * k6, 41))
    col = col * (1 - 0.16 * contour[..., None] * (1 - INK))
    # trazos de textura en las laderas empinadas (los "pliegues" de las montañas sumi-e)
    steep = ss(0.45, 1.2, grad) * land * ss(-0.5, 1.0, wd)
    c2 = h / 0.9
    d2 = np.abs((c2 - 0.5) % 1.0 - 0.5) / np.maximum(grad / 0.9 / PPM, 1e-3)
    hatch = (1 - ss(0.3, 1.0, d2)) * steep * ss(0.5, 0.62, vnoise(7 * k6, 51))
    col = col * (1 - 0.3 * hatch[..., None] * (1 - INK))
    del c, dpx, contour, c2, d2, hatch, steep

    # ---- agua (lago donde la altura baja del nivel; arroyos y estanque del jardín)
    def water_mask(level, near):
        s = level - h
        dpx_ = s / np.maximum(grad, 0.05) * PPM
        return ss(-0.7, 0.7, dpx_) * near, s
    # el lago es exactamente el polígono (world_terrain: adentro, el fondo; afuera, la orilla sube): se toma su
    # distancia con signo a resolución de píxel. Con la grilla de 1 m sus lados casi verticales salían en escalones
    lake_in = lake_poly > 0.5
    lake_sd = (ndimage.distance_transform_edt(lake_in) - ndimage.distance_transform_edt(~lake_in)).astype(np.float32) / PPM
    lake_fade = ss(56.0, 30.0, wd + (edge_n - 0.5) * 16.0)       # lejos de todo, el agua se va en aguada
    wl = lake_poly * lake_fade
    depth_l = 0.4 + W.LAKE_DEPTH * ss(0.0, 14.0, lake_sd)
    stream_near = ss(3.5, 2.0, sd) * up(ndimage.gaussian_filter((reg == REGIONS.index("jardin")).astype(np.float32), 2.0))
    ws, depth_s = water_mask(W.WATER_STREAM, stream_near)
    ws = ws * (1 - lake_poly)
    water = np.maximum(wl, ws)
    lake_side = wl >= ws
    depth = np.where(lake_side, depth_l, depth_s)
    del depth_l
    wn = fbm(120 * k6, 61, 4)
    shallow = np.array([0.58, 0.68, 0.74], np.float32); deep = np.array([0.26, 0.36, 0.50], np.float32)
    wcol = shallow + (deep - shallow) * ss(0.0, 3.0, depth)[..., None]
    wcol = wcol * (0.95 + 0.1 * wn[..., None])
    col = col * (1 - water[..., None]) + (paper * wcol) * water[..., None]
    del wcol
    # líneas de agua paralelas a la orilla (como en los mapas pintados) y la orilla en tinta
    # en el lago la pendiente del fondo sale de la distancia a la orilla; en los arroyos, de la grilla
    dgrad = np.where(lake_side, W.LAKE_DEPTH * 6 * np.clip(lake_sd / 14.0, 0, 1) * (1 - np.clip(lake_sd / 14.0, 0, 1)) / 14.0 + 0.02, np.maximum(grad, 0.05))
    for lev, a in ((0.55, 0.34), (1.25, 0.24), (2.2, 0.15)):
        dd = np.abs(depth - lev) / dgrad * PPM
        ln = (1 - ss(0.4, 1.3, dd)) * water * ss(0.3, 0.55, vnoise(14 * k6, 71 + int(lev * 10)))
        col = col * (1 - a * ln[..., None] * (1 - np.array([0.2, 0.26, 0.36], np.float32)))
    shore_s = (1 - ss(0.6, 1.8, np.abs(depth_s) / np.maximum(grad, 0.05) * PPM)) * stream_near
    shore_l = (1 - ss(0.12, 0.42, np.abs(lake_sd))) * lake_fade
    shore = np.maximum(shore_s, shore_l) * land
    col = col * (1 - 0.75 * shore[..., None] * (1 - INK))
    del shore_s, shore_l, shore, depth, dgrad, lake_sd, lake_in
    # arrozales (inundados) y trigo
    for rect, base, lines in [(r, (0.66, 0.78, 0.78), (0.42, 0.56, 0.56)) for r in W.PADDIES] + [(r, (0.95, 0.84, 0.58), (0.74, 0.60, 0.36)) for r in W.WHEAT]:
        ax, ay = to_px(rect[0], rect[3]); bx, by = to_px(rect[2], rect[1])
        ax, ay, bx, by = int(ax), int(ay), int(bx), int(by)
        sub = col[ay:by, ax:bx]
        sub *= np.array(base, np.float32)
        for yy in range(0, by - ay, max(2, int(PPM * 1.5))):
            sub[yy:yy + 1] *= np.array(lines, np.float32) / np.array(base, np.float32)
        e = max(1, int(PPM / 3))
        sub[:e] *= 0.55; sub[-e:] *= 0.55; sub[:, :e] *= 0.55; sub[:, -e:] *= 0.55

    # ---- caminos: tierra clara con los bordes en tinta cortada
    pn = vnoise(30 * k6, 81)
    path = ss(0.7, -0.5, pd + (pn - 0.5) * 0.6) * land * (1 - water)
    path_col = np.array([0.985, 0.955, 0.875], np.float32)[None, None, :] * (1 - mont[..., None]) + np.array([0.84, 0.84, 0.88], np.float32)[None, None, :] * mont[..., None]
    col = col * (1 - path[..., None] * 0.85) + paper * path_col * path[..., None] * 0.85
    pedge = (1 - ss(0.1, 0.45, np.abs(pd + 0.05))) * land * (1 - water) * ss(0.35, 0.55, vnoise(9 * k6, 91))
    col = col * (1 - 0.38 * pedge[..., None] * (1 - INK))
    del pn, pedge, path_col
    print(f"suelo {time.time() - t0:.1f} s")

    # ---- props y arenas
    st = Stamps()
    draw_arenas(st)
    stamp_props(st, props)
    print(f"sellos {time.time() - t0:.1f} s")
    ink, shadow = hand_drawn(st, k6)
    print(f"pincel {time.time() - t0:.1f} s")
    shadow = ndimage.gaussian_filter(shadow, PPM * 0.5)
    col = col * (1 - 0.38 * shadow[..., None] * (1 - shadow_col * 0.6))
    del shadow
    a = ink[..., 3:4]
    # la tinta se corre en las fibras del washi (nijimi): un halo tenue y desparejo alrededor de cada trazo oscuro
    dark = ss(0.36, 0.14, (ink[..., :3] * np.array([0.299, 0.587, 0.114], np.float32)).sum(-1)) * ink[..., 3]
    halo = np.clip(ndimage.gaussian_filter(dark, PPM * 0.35) * 1.7 - dark, 0, 1) * (0.55 + 0.9 * (fib - 0.5))
    col = col * (1 - 0.2 * halo[..., None] * (1 - INK))
    del dark, halo
    # los sellos también llevan la fibra del papel (si no parecen pegados encima)
    col = col * (1 - a) + ink[..., :3] * (0.94 + 0.08 * fib[..., None]) * a
    del ink, a

    # ---- luz de luna, y después lo cálido: el resplandor de los faroles y sus puntos de luz
    col = moon_grade(col)
    glow = np.asarray(st.glow.filter(ImageFilter.GaussianBlur(PPM * 1.8)), np.float32) / 255
    col = col + glow[..., None] * LAMP_GLOW
    lamps = np.asarray(st.lamps, np.float32) / 255
    col = col * (1 - lamps[..., 3:4]) + lamps[..., :3] * lamps[..., 3:4]
    del glow, lamps

    # ---- envejecido del papel junto al borde de arriba y de abajo (el borde rasgado lo corta el shader)
    yy = np.arange(IH, dtype=np.float32)[:, None]
    ey = np.minimum(yy, IH - 1 - yy) / PPM                     # metros al borde
    xx = np.arange(IW, dtype=np.float32)[None, :]
    ex = np.minimum(xx, IW - 1 - xx) / PPM
    age = np.maximum(ss(11.0, 2.0, ey), 0.6 * ss(8.0, 0.0, ex))
    col = col * (1 - 0.16 * age[..., None] * np.array([0.55, 0.8, 1.2], np.float32))
    img = Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8), "RGB")
    print(f"lámina {IW}x{IH} en {time.time() - t0:.1f} s")
    return img, g


# ------------------------------------------------------------------------------------------- niebla (textura de datos)
def wrap_noise(shape, sigma, seed):
    """Ruido suave que se repite sin costura (filas, columnas): la textura se lee también a otras escalas, con wrap."""
    n = ndimage.gaussian_filter(np.random.RandomState(seed).rand(*shape).astype(np.float32), sigma, mode="wrap")
    return (n - n.min()) / (n.max() - n.min() + 1e-9)


def mist_size():
    """La niebla cubre la lámina una vez (MIST_PPM texeles por metro; múltiplos de 4 para la compresión por bloques)."""
    return int(round(SHEET_W * MIST_PPM / 4)) * 4, int(round(SHEET_H * MIST_PPM / 4)) * 4


def kasumi_layout(seed):
    """Bandas kasumi repartidas por la lámina (metros, x al este, y hacia abajo = al sur): una por lugar con un
    muestreo de disco de Poisson estirado a lo ancho (las bandas son horizontales), largo 0.6-1.4 veces el base, giro
    de ±6°, la punta con el rulo a uno u otro lado y, a veces, una banda de atrás corrida y más corta. Quedan huecos:
    no hay renglones."""
    rng = random.Random(seed)
    L0, H0 = 128.0, 15.0
    pts = []
    for _ in range(4000):
        x, y = rng.uniform(0, SHEET_W), rng.uniform(0, SHEET_H)
        ok = True
        for px, py in pts:
            dx = (x - px + SHEET_W / 2) % SHEET_W - SHEET_W / 2      # la textura se repite: distancias con wrap
            dy = (y - py + SHEET_H / 2) % SHEET_H - SHEET_H / 2
            if math.hypot(dx / 1.9, dy) < 64.0:
                ok = False
                break
        if ok:
            pts.append((x, y))
    rng.shuffle(pts)
    pts = pts[:max(1, int(len(pts) * 0.82))]                     # algunos lugares sin banda: aire entre las nubes
    bands = []
    for x, y in pts:
        L, H = L0 * rng.uniform(0.6, 1.4), H0 * rng.uniform(0.85, 1.15)
        tilt = rng.uniform(-6.0, 6.0)
        if rng.random() < 0.6:
            bands.append((x + rng.choice((-1, 1)) * rng.uniform(0.14, 0.24) * L, y - H * rng.uniform(0.6, 0.8), L * rng.uniform(0.5, 0.7), H * 0.82, rng.choice((-1, 1)), tilt))
        bands.append((x, y, L, H, rng.choice((-1, 1)), tilt))
    return bands


def mist(seed=7):
    """Niebla de lo no explorado (datos, lineal), del tamaño de la lámina y sin costura en los bordes: R fibra del papel
    (anisótropa), G nubes de tinta (bultos grandes y suaves), B líneas de las nubes kasumi, A ruido suave para
    deformar el borde. El shader lee R, G y A a las escalas MIST_K (nubes de ~10 y ~17 m) y B a la escala de la lámina:
    cada banda kasumi está en un solo lugar. Las kasumi son bandas largas de puntas redondeadas, en capas (la de
    adelante tapa las líneas de la de atrás) y con una segunda línea por dentro, como en los biombos."""
    MW, MH = mist_size()
    shape = (MH, MW)
    fib = ndimage.gaussian_filter(np.random.RandomState(seed + 1).rand(*shape).astype(np.float32), (0.7, 4.5), mode="wrap")
    fib = (fib - fib.min()) / (fib.max() - fib.min())
    r = np.clip(0.5 + (fib - 0.5) * 1.6, 0, 1)
    del fib
    g = wrap_noise(shape, 110, seed + 2) * 0.55 + wrap_noise(shape, 52, seed + 3) * 0.3 + wrap_noise(shape, 22, seed + 4) * 0.15
    g = ss(0.18, 0.86, (g - g.min()) / (g.max() - g.min()))
    K = 2
    sw, sh = MW * K, MH * K
    kpm = MIST_PPM * K                                           # texeles por metro del dibujo
    lw = int(round(1.15 * kpm))                                  # trazo de 1.15 m: se lee a la escala del mapa
    art = Image.new("L", (sw, sh), 0)

    def band(x, y, L, H, curl, tilt):
        """Banda de puntas redondeadas en su propia imagen (girada): borra lo de atrás, contorno, una segunda línea
        por dentro y, en una punta, el rulo. Se pega nueve veces (la textura se repite)."""
        L, H = L * kpm, H * kpm
        pad = int(H * 0.6) + lw * 2
        w, h = int(L) + 2 * pad, int(H) + 2 * pad
        shape_i, lines = Image.new("L", (w, h), 0), Image.new("L", (w, h), 0)
        ds, dl = ImageDraw.Draw(shape_i), ImageDraw.Draw(lines)
        x0, y0, x1, y1 = pad, pad, pad + L, pad + H
        ds.rounded_rectangle((x0, y0, x1, y1), radius=H / 2, fill=255)
        dl.rounded_rectangle((x0, y0, x1, y1), radius=H / 2, outline=255, width=lw)
        ix = L * 0.14
        dl.rounded_rectangle((x0 + ix * (1 if curl > 0 else 0.4), y0 + H * 0.3, x1 - ix * (0.4 if curl > 0 else 1), y1 - H * 0.3),
                             radius=H * 0.2, outline=170, width=max(2, int(lw * 0.7)))
        ex = x1 - H * 0.5 if curl > 0 else x0 + H * 0.5
        cr, cy = H * 0.27, (y0 + y1) / 2
        a0, a1 = (200, 470) if curl > 0 else (-110, 160)
        dl.arc((ex - cr, cy - cr, ex + cr, cy + cr), a0, a1, fill=220, width=max(2, int(lw * 0.7)))
        shape_i = shape_i.rotate(tilt, resample=Image.BILINEAR, expand=True)
        lines = lines.rotate(tilt, resample=Image.BICUBIC, expand=True)
        mask = ImageChops.lighter(shape_i, lines)
        cx, cy = x * kpm, y * kpm
        for ox in (-sw, 0, sw):
            for oy in (-sh, 0, sh):
                px, py = int(round(cx + ox - lines.size[0] / 2)), int(round(cy + oy - lines.size[1] / 2))
                if px < sw and py < sh and px + lines.size[0] > 0 and py + lines.size[1] > 0:
                    art.paste(lines, (px, py), mask)
    for b in kasumi_layout(seed):
        band(*b)
    # el pulso del pincel: las bandas no son rectas (el trazo sube y baja apenas) y la tinta afloja en algunos tramos
    # sin cortarse (cortadas en guiones parecían una falla de la textura)
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    wob = (wrap_noise((sh, sw), 15 * kpm, seed + 9) - 0.5) * 0.045 * 262.0 * kpm
    lines = ndimage.map_coordinates(np.asarray(art, np.float32) / 255, [(yy + wob) % sh, xx], order=1, mode="grid-wrap")
    del yy, xx, wob, art
    lines = lines * (0.65 + 0.35 * wrap_noise((sh, sw), 4 * kpm, seed + 6))
    lines = ndimage.gaussian_filter(lines, 0.8 * K, mode="wrap")
    b = np.asarray(Image.fromarray((np.clip(lines, 0, 1) * 255).astype(np.uint8), "L").resize((MW, MH), Image.LANCZOS), np.float32) / 255
    del lines
    b = np.clip(b * 1.3, 0, 1)
    a = wrap_noise(shape, 40, seed + 7) * 0.7 + wrap_noise(shape, 12, seed + 8) * 0.3
    a = (a - a.min()) / (a.max() - a.min())
    arr = np.stack([r, g, b, a], -1)
    return Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8), "RGBA")


# ------------------------------------------------------------------------------------------- datos para C#
def bits_b64(mask):
    """Máscara (GH, GW) con la fila 0 al SUR -> base64 de bits (LSB primero), índice = fila * GW + columna. El mismo
    formato que MapFog guarda en la partida."""
    by = np.packbits(mask.reshape(-1).astype(np.uint8), bitorder="little")
    return base64.b64encode(by.tobytes()).decode()


def cell_blocks(a, how):
    """Campo de 1 m (fila 0 al norte) -> una cifra por celda de niebla (fila 0 al sur): min o media de sus 4 x 4 m."""
    c = int(CELL)
    blk = a[::-1][:GH * c, :GW * c].reshape(GH, c, GW, c)
    return blk.min(axis=(1, 3)) if how == "min" else blk.mean(axis=(1, 3))


def water_mask(g):
    """Celdas de agua abierta (el lago): MapFog las descubre hasta WATER_R."""
    return cell_blocks(g["lake"], "mean") > 0.5


def reach_mask(g):
    """Celdas de niebla que se descubren caminando: alguna parte de la celda a <= REACH_D de lo transitable, o agua
    abierta a menos de WATER_REACH."""
    wd = cell_blocks(g["wd"], "min")
    return (wd <= REACH_D) | (water_mask(g) & (wd <= WATER_REACH))


def side_masks():
    """Del otro lado de una puerta cerrada no se descubre nada (MapFog: el lado de Kaito contra el de cada celda, por
    el centro de la celda): 'north' = al norte de la muralla (z > WALL_Z), 'dojo' = la meseta detrás del portón."""
    cz = IZ0 + (np.arange(GH) + 0.5)[:, None] * CELL + np.zeros((1, GW))
    cx = IX0 + (np.arange(GW) + 0.5)[None, :] * CELL + np.zeros((GH, 1))
    north = cz > W.WALL_Z
    dojo = (cz > DOJO_GATE_Z) & (cx > DOJO_X[0]) & (cx <= DOJO_X[1])
    return north & ~dojo, dojo


def side_of(x, z):
    """El lado de las puertas de un punto, como side_masks: 0 sur de la muralla, 1 norte, 2 patio del dojo."""
    if z > DOJO_GATE_Z and DOJO_X[0] < x <= DOJO_X[1]:
        return 2
    return 1 if z > W.WALL_Z else 0


def legacy_discs():
    paths = {name: pts for name, pts, width, ph in W.PATHS}
    areas = {a[0]: a for a in W.AREAS}
    out = []
    for flags, segs, ars in LEGACY:
        cap = LEGACY_SIDE.get(flags[0], 2)
        d = []

        def add(x, z, r):
            if side_of(x, z) <= cap:
                d.extend([x, z, r])
        for name, i0, i1 in segs:
            pts = paths[name][i0:i1 + 1]
            for (ax, az), (bx, bz) in zip(pts[:-1], pts[1:]):
                n = max(1, int(math.hypot(bx - ax, bz - az) / 6.0))
                for k in range(n + 1):
                    t = k / n
                    add(round(ax + (bx - ax) * t, 1), round(az + (bz - az) * t, 1), REVEAL_R)
            if len(pts) == 1:
                add(pts[0][0], pts[0][1], REVEAL_R)
        for an in ars:
            _, x, z, r, hh, soft = areas[an]
            add(x, z, round(r + REVEAL_R * 0.6, 1))
        out.append({"flags": flags, "d": d})
    return out


def label_entry(k, v):
    x, z, align, small, rot = label(v)
    e = dict(id=k, x=x, z=z, align=align, small=small, rot=rot)
    an = LABEL_ANCHOR.get(k)
    if an is not None:
        a = next(a for a in W.AREAS if a[0] == an)
        e["at"] = [a[1], a[2]]
    return e


def map_json(g):
    reach = reach_mask(g)
    north, dojo = side_masks()
    return {
        "version": 2,
        "image": [IW, IH],
        "bounds": [IX0, IX1, IZ0, IZ1],
        "cell": CELL,
        "grid": [GW, GH],
        "reveal": REVEAL_R,
        "revealWater": WATER_R,
        "mistK": list(MIST_K),
        "reachCount": int(reach.sum()),
        "reach": bits_b64(reach),
        "water": bits_b64(water_mask(g)),
        "north": bits_b64(north),
        "dojo": bits_b64(dojo),
        "gates": GATE_FLAGS,
        "labels": [label_entry(k, v) for k, v in LABELS.items()],
        "legacy": legacy_discs(),
    }


# ------------------------------------------------------------------------------------------- íconos
def icons():
    import build_ui_art as K   # mismo contorno de tinta y mismo guardado que el resto del kit

    # torii: dos postes, el travesaño de abajo (nuki) y el de arriba con las puntas levantadas (kasagi). Todo dentro
    # del margen del contorno (8 px de 128): las puntas del kasagi y el pie de los postes quedaban sin borde, cortados
    m, d, s = K.canvas(128)

    def q(x, y):
        return s * (0.5 + (x - 0.5) * 0.9), s * (0.17 + (y - 0.17) * 0.96)
    d.polygon([q(.03, .17), q(.2, .25), q(.8, .25), q(.97, .17), q(.93, .33), q(.07, .33)], fill=255)
    d.rectangle(q(.15, .43) + q(.85, .52), fill=255)
    for x in (.28, .72):
        d.polygon([q(x - .06, .3), q(x + .06, .3), q(x + .075, .95), q(x - .075, .95)], fill=255)
    d.rectangle(q(.46, .3) + q(.54, .43), fill=255)
    K.save(K.outlined(m, 128, 8), "MapShrine", usage="santuario en el mapa (torii): bermellón rezado, papel sin rezar")

    # portal: espiral de pincel que se afina hacia adentro
    m, d, s = K.canvas(128)
    prev = None
    for i in range(260):
        t = i / 259
        a = t * math.tau * 2.2
        r = s * (0.06 + 0.32 * t)          # la vuelta de afuera, su trazo y el contorno entran en el lienzo
        p = (s / 2 + math.cos(a) * r, s / 2 + math.sin(a) * r)
        if prev is not None:
            w = s * (0.035 + 0.065 * t)
            d.line([prev, p], fill=255, width=int(w))
            d.ellipse((p[0] - w / 2, p[1] - w / 2, p[0] + w / 2, p[1] + w / 2), fill=255)
        prev = p
    K.save(K.outlined(m, 128, 7), "MapPortal", usage="portal de vuelta al dojo en el mapa (teñir jade)")

    # Kaito: punta de flecha dorada (apunta al norte = hacia donde mira) con las dos colas de la bandana detrás.
    # Ya coloreada (no se tiñe): oro con el filo claro del lado de la luna y contorno de tinta
    S = 160
    k = 4
    s = S * k
    mask = Image.new("L", (s, s), 0)
    md = ImageDraw.Draw(mask)
    tip, lw_, rw_, notch = (s * .5, s * .06), (s * .2, s * .56), (s * .8, s * .56), (s * .5, s * .44)
    md.polygon([tip, rw_, notch, lw_], fill=255)

    def tail(sign):
        pts = []
        for i in range(40):
            t = i / 39
            x = s * .5 + sign * (s * .05 + s * .2 * t) + sign * math.sin(t * math.pi * 1.4) * s * .05
            y = s * .48 + s * .46 * t
            pts.append((x, y))
        for i in range(len(pts) - 1):
            w = s * (0.085 * (1 - pts[i][1] / s * 0.0) * (1 - (i / 39) * 0.72))
            md.line([pts[i], pts[i + 1]], fill=255, width=max(2, int(w)))
            md.ellipse((pts[i][0] - w / 2, pts[i][1] - w / 2, pts[i][0] + w / 2, pts[i][1] + w / 2), fill=255)
    tail(-1); tail(1)
    o = mask.filter(ImageFilter.MaxFilter(int(2 * 7 * k) | 1)).filter(ImageFilter.GaussianBlur(k * 0.5))
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    img.paste(Image.new("RGBA", (s, s), K.INK + (255,)), (0, 0), o)
    img.paste(Image.new("RGBA", (s, s), (232, 168, 52, 255)), (0, 0), mask.filter(ImageFilter.GaussianBlur(k * 0.35)))
    hd = ImageDraw.Draw(img)
    hd.polygon([tip, (s * .5, s * .44), lw_], fill=(255, 214, 112, 255))           # mitad iluminada (oeste)
    hd.line([tip, (s * .5, s * .42)], fill=(255, 236, 170, 255), width=int(2.5 * k))
    K.save(img.resize((S, S), Image.LANCZOS), "MapKaito", usage="Kaito en el mapa: apunta adonde mira (no se tiñe)")

    # varilla del pergamino del mapa: laca roja oscura con contorno de tinta y las puntas doradas (9-slice vertical)
    Wr, Hr = 56, 512
    k = 2
    w, h = Wr * k, Hr * k
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cap = 34 * k
    d.rounded_rectangle((0, 0, w - 1, h - 1), 14 * k, fill=K.INK + (255,))
    d.rounded_rectangle((9 * k, cap, w - 9 * k, h - cap), 6 * k, fill=(120, 36, 28, 255))
    d.line([(17 * k, cap + 6 * k), (17 * k, h - cap - 6 * k)], fill=(196, 92, 62, 255), width=4 * k)
    d.line([(w - 17 * k, cap + 6 * k), (w - 17 * k, h - cap - 6 * k)], fill=(78, 20, 16, 255), width=3 * k)
    for y0 in (5 * k, h - cap + 3 * k):
        d.rounded_rectangle((5 * k, y0, w - 5 * k, y0 + cap - 8 * k), 6 * k, fill=(214, 178, 104, 255))
        d.line([(12 * k, y0 + 6 * k), (12 * k, y0 + cap - 14 * k)], fill=(250, 226, 160, 255), width=3 * k)
    K.save(img.resize((Wr, Hr), Image.LANCZOS), "MapRod", border=(0, 40, 0, 40), usage="varilla del pergamino del mapa (9-slice vertical)")

    # sombra de la lámina: rectángulo blanco muy difuso (se tiñe de negro), 9-slice para cualquier tamaño
    S, b = 128, 48
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle((b * 0.55, b * 0.55, S - b * 0.55, S - b * 0.55), radius=8, fill=255)
    m = m.filter(ImageFilter.GaussianBlur(b * 0.32))
    img = Image.new("RGBA", (S, S), (255, 255, 255, 0))
    img.putalpha(m)
    K.save(img, "MapShadow", border=(b, b, b, b), usage="sombra suave debajo de la lámina del mapa (teñir negro)")
    for name in MIP_SPRITES:
        mip_sprite_meta(name)


# lo que la lámina dibuja 3 a 6 veces más chico que su textura (el torii de 128 a 27 px, el sello de 256 a 44): sin
# mips, el bilineal lee 4 de ~20 texeles por píxel y los travesaños del torii se cortan y titilan al acercar con la
# rueda (la maqueta de PIL lo esconde). Con mips trilineales (sin "conservar cobertura": eso es para el recorte por
# alfa y endurecía el borde suave del contorno). Los Hanko son del kit de la interfaz (build_ui_art.py no toca los
# mips de un .meta que ya existe)
MIP_SPRITES = ("MapShrine", "MapPortal", "MapKaito", "Hanko_IconBoss", "Hanko_ZoneMountain", "Hanko_ZoneLake", "Hanko_ZoneBamboo", "Hanko_ZoneMoon")


def mip_sprite_meta(name):
    p = os.path.join(OUT, name + ".png.meta")
    if not os.path.exists(p):
        return
    s = open(p, encoding="utf-8").read()
    t = s.replace("enableMipMap: 0", "enableMipMap: 1")
    t = t.replace("    filterMode: 1\n", "    filterMode: 2\n", 1)
    if t != s:
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(t)


# ------------------------------------------------------------------------------------------- salida
def write_assets(img, g, preview_only, reuse_sheet=False):
    data = map_json(g)
    if preview_only:
        icons()            # las marcas son chicas y siempre iguales: la maqueta las usa
        return data
    os.makedirs(OUT, exist_ok=True)
    p = os.path.join(OUT, "WorldMap.jpg")
    if not reuse_sheet:
        img.save(p, quality=92, subsampling=0, optimize=True)
    # sin redondear a potencia de 2 (3096 x 2568 ya son múltiplos de 4: compresión por bloques) y con mips: a la
    # escala de la pantalla se ve a ~0.4x. Alta calidad (BC7): con DXT1 los sellos de 2 px se ensuciaban
    # trilineal: al acercar con la rueda el mip cambia sin saltos
    write_meta(p, texture_meta(mips=True, max_size=4096, compress=True).replace("nPOTScale: 1", "nPOTScale: 0")
               .replace("textureCompression: 1", "textureCompression: 2").replace("filterMode: 1", "filterMode: 2"), force=True)
    p = os.path.join(OUT, "WorldMapMist.png")
    mist().save(p, optimize=True)
    # sin redondear a potencia de 2 (2064 x 1712, múltiplos de 4) y repetible: el shader la lee también a otras escalas
    write_meta(p, texture_meta(mips=True, srgb=False, max_size=4096, compress=True, wrap_clamp=False, alpha_transparency=False)
               .replace("nPOTScale: 1", "nPOTScale: 0").replace("textureCompression: 1", "textureCompression: 2").replace("filterMode: 1", "filterMode: 2"), force=True)
    p = os.path.join(OUT, "WorldMap.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, separators=(",", ":"))
    write_meta(p, TEXT_META, force=True)
    icons()
    print("mapa ->", os.path.relpath(OUT, ASSETS))
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--props", required=True, help="JSON de Tools/UI/world_map_data.py")
    ap.add_argument("--cache", default=None, help="carpeta para la grilla calculada (por defecto, junto al JSON)")
    ap.add_argument("--ppm", type=float, default=6.0, help="píxeles por metro (6 = la del juego; menos para probar)")
    ap.add_argument("--preview", default=None, help="carpeta para las vistas previas")
    ap.add_argument("--no-assets", action="store_true", help="no escribir en Assets (solo la vista previa)")
    ap.add_argument("--reuse-sheet", action="store_true", help="no volver a pintar la lámina: usa la WorldMap.jpg que ya está "
                    "(para rehacer los datos, la niebla y las vistas previas sin los minutos del pintado)")
    a = ap.parse_args()
    configure(a.ppm)
    data = json.load(open(a.props))
    SIZES.update(data["sizes"])
    cache = a.cache or os.path.dirname(os.path.abspath(a.props))
    if a.reuse_sheet:
        img, g = Image.open(os.path.join(OUT, "WorldMap.jpg")).convert("RGB"), world_grid(cache)
        assert img.size == (IW, IH), "la lámina guardada es de otra resolución: sin --reuse-sheet"
    else:
        img, g = render(data["placed"], cache)
    meta = write_assets(img, g, a.no_assets or a.ppm != 6.0, a.reuse_sheet)
    if a.preview:
        import world_map_preview as PV
        PV.run(img, meta, mist(), a.preview, PPM)


if __name__ == "__main__":
    main()
