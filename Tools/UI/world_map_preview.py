"""
Vistas previas del mapa del mundo (las arma build_world_map.py --preview): sin Unity a mano, la niebla se compone con
la misma cuenta que el shader Nindo/UI Map (Resources/Shaders/NindoUIMap.shader) y la pantalla se maqueta con las
mismas medidas que UI/UIMap.cs (columna, lámina, varillas, marcas, nombres). Si se cambia una de las dos cosas, se
cambia acá también: esto es lo que se mira para juzgar el mapa.

La exploración se simula como la hace MapFog: cada 2 m de camino se descubren las celdas cuyo centro queda a menos
de REVEAL_R de Kaito, y la textura de niebla es esa grilla con un desenfoque [1 2 1] de dos pasadas.
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

import build_world_map as M
import world_plan as W

UI = M.OUT
LOGO = os.path.join(M.ASSETS, "Nindo", "Art", "UI", "Logo.png")
TITLE_TTF = os.path.join(M.FONTS, "ShipporiMinchoB1-ExtraBold.ttf")
BODY_TTF = os.path.join(M.FONTS, "ZenMaruGothic-Bold.ttf")

# ---- colores del shader (los pone UIMap.cs en el material; el proyecto está en espacio Gamma: se mezcla en sRGB)
FOG_LIGHT = np.array([0.340, 0.360, 0.430], np.float32)
FOG_DARK = np.array([0.190, 0.200, 0.260], np.float32)
KASUMI = (np.array([0.80, 0.77, 0.68], np.float32), 0.45)
TIDE = (np.array([0.045, 0.040, 0.065], np.float32), 0.62)

# ---- maqueta: mismas medidas que UIMap.cs (unidades del canvas de referencia 1920 x 1080, modo Expand)
COL_X = 660.0          # la lámina empieza a la derecha de la columna de tinta
PAD_R, PAD_V = 60.0, 70.0
ROD_W, ROD_GAP = 34.0, 30.0
PAPER = (245, 235, 209)
GOLD = (255, 209, 96)
SHRINE = (206, 58, 40)
SHRINE_BARE = (237, 230, 212)       # UIMap.MapShrineBare: todavía sin rezar
INK = (11, 10, 13)


# ------------------------------------------------------------------------------------------- niebla
def reveal_points(fog, pts):
    """fog: (GH, GW) 1 = niebla. Descubre alrededor de cada punto (x, z) como MapFog.Reveal."""
    R = M.REVEAL_R
    for x, z in pts:
        gx0, gx1 = int((x - R - M.IX0) // M.CELL), int((x + R - M.IX0) // M.CELL)
        gy0, gy1 = int((z - R - M.IZ0) // M.CELL), int((z + R - M.IZ0) // M.CELL)
        for gy in range(max(0, gy0), min(M.GH - 1, gy1) + 1):
            cz = M.IZ0 + (gy + 0.5) * M.CELL
            for gx in range(max(0, gx0), min(M.GW - 1, gx1) + 1):
                cx = M.IX0 + (gx + 0.5) * M.CELL
                if (cx - x) ** 2 + (cz - z) ** 2 <= R * R:
                    fog[gy, gx] = 0.0


def walk(pts, step=2.0):
    out = []
    for (ax, az), (bx, bz) in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.hypot(bx - ax, bz - az) / step))
        out += [(ax + (bx - ax) * k / n, az + (bz - az) * k / n) for k in range(n)]
    out.append(pts[-1])
    return out


def area_walk(name):
    a = next(a for a in W.AREAS if a[0] == name)
    _, x, z, r, h, soft = a
    pts = [(x, z)]
    for rr in np.arange(4, r, 5):
        for k in range(int(2 * math.pi * rr / 5) + 1):
            t = k / max(1, int(2 * math.pi * rr / 5)) * math.tau
            pts.append((x + math.cos(t) * rr, z + math.sin(t) * rr))
    return pts


def path(name, i0=0, i1=None):
    pts = next(p for n, p, w, h in W.PATHS if n == name)
    return pts[i0:(i1 + 1 if i1 is not None else None)]


def exploration_states():
    """Tres partidas: el comienzo (hasta el jardín), la mitad (montaña y lago) y todo recorrido."""
    early = walk(path("camino_hogar")) + walk(path("camino_jardin", 0, 3))
    for a in ("hogar", "hogar_patio", "campos_o", "campos_e", "campos_n", "bosque_claro", "muralla_s", "muralla_n", "jardin_c"):
        early += area_walk(a)
    mid = list(early) + walk(path("camino_jardin")) + walk(path("camino_oeste")) + walk(path("subida_monte")) + walk(path("paso_monte"))
    mid += walk(path("camino_este")) + walk(path("rodeo_jardin_o")) + walk(path("rodeo_jardin_e"))
    for a in ("jardin_o", "jardin_e", "jardin_n", "jardin_ne", "jardin_no", "mont_base", "mont_arena", "mont_paso", "mont_cumbre", "lago_entrada", "lago_orilla"):
        mid += area_walk(a)
    full = list(mid)
    for n, p, w, h in W.PATHS:
        full += walk(p)
    for a in W.AREAS:
        full += area_walk(a[0])
    states = []
    for pts in (early, mid, full):
        f = np.ones((M.GH, M.GW), np.float32)
        reveal_points(f, pts)
        states.append(f)
    return states


def blur121(f):
    """El desenfoque de MapFog al subir la textura: [1 2 1] / 4 en x y en y, dos pasadas, borde repetido."""
    for _ in range(2):
        p = np.pad(f, ((0, 0), (1, 1)), mode="edge")
        f = (p[:, :-2] + 2 * p[:, 1:-1] + p[:, 2:]) * 0.25
        p = np.pad(f, ((1, 1), (0, 0)), mode="edge")
        f = (p[:-2] + 2 * p[1:-1] + p[2:]) * 0.25
    return np.round(f * 255) / 255           # Alpha8


def bilinear(tex, u, v, wrap):
    """tex (H, W[, C]) con la fila 0 = v 0 (abajo, como Unity); u, v arrays. Muestreo de GPU (centros de texel)."""
    H, Wd = tex.shape[:2]
    x = u * Wd - 0.5
    y = v * H - 0.5
    x0 = np.floor(x).astype(np.int64); y0 = np.floor(y).astype(np.int64)
    fx = (x - x0)[..., None] if tex.ndim == 3 else x - x0
    fy = (y - y0)[..., None] if tex.ndim == 3 else y - y0
    if wrap:
        xa, xb, ya, yb = x0 % Wd, (x0 + 1) % Wd, y0 % H, (y0 + 1) % H
    else:
        xa, xb = np.clip(x0, 0, Wd - 1), np.clip(x0 + 1, 0, Wd - 1)
        ya, yb = np.clip(y0, 0, H - 1), np.clip(y0 + 1, 0, H - 1)
    a, b, c, d = tex[ya, xa], tex[ya, xb], tex[yb, xa], tex[yb, xb]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def ss(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def composite_uv(U, V, sheet, fog_now, mist, t=0.0, fog_prev=None, reveal=1.0, dpx_m=None):
    """frag() de NindoUIMap.shader, línea por línea. U, V: uv de la lámina de cada píxel (v 0 = sur); sheet: el color
    de la lámina en esos píxeles (sRGB 0..1). dpx_m: metros por píxel de pantalla (el fwidth del borde rasgado)."""
    sheet_m = np.array([M.SHEET_W, M.SHEET_H], np.float32)
    tile = M.MIST_TILE
    pmx, pmy = U * sheet_m[0], V * sheet_m[1]
    mist_up = mist[::-1]                                         # la textura con la fila 0 abajo, como Unity
    m1 = bilinear(mist_up, pmx / tile[0] + t * 0.006, pmy / tile[0], True)
    m1l = bilinear(mist_up, pmx / tile[0] + t * 0.006 - 0.012, pmy / tile[0] + 0.012, True)   # hacia la luna (noroeste)
    m2 = bilinear(mist_up, pmx / tile[1] - t * 0.0035, pmy / tile[1] + 0.37, True)
    m3 = bilinear(mist_up, pmx / tile[2] + t * 0.0022, pmy / tile[2] + 0.61, True)
    wu = U + (m1[..., 3] - 0.5) * (6.0 / sheet_m[0])
    wv = V + (m2[..., 3] - 0.5) * (6.0 / sheet_m[1])
    fnow = bilinear(fog_now, wu, wv, False)
    if fog_prev is not None:
        fprev = bilinear(fog_prev, wu, wv, False)
        wipe = ss(m2[..., 1] - 0.18, m2[..., 1] + 0.18, reveal * 1.36 - 0.18)
        fog = fprev + (fnow - fprev) * wipe
    else:
        fog = fnow
    F = ss(0.22, 0.78, fog + (m1[..., 0] - 0.5) * 0.12 + (m1[..., 1] - 0.5) * 0.30)
    bill = np.clip(m1[..., 1] * 0.6 + m2[..., 1] * 0.5 - 0.1, 0, 1)
    fog_col = FOG_LIGHT + (FOG_DARK - FOG_LIGHT) * bill[..., None]
    ey = np.minimum(V, 1 - V) * sheet_m[1]
    fog_col = fog_col * ((0.94 + 0.12 * m1[..., 0:1]) * (0.86 + 0.14 * ss(0.0, 36.0, ey))[..., None])
    lit = (m1[..., 1] - m1l[..., 1]) * 5.0                        # el lomo de cada nube que da a la luna, más claro
    fog_col = fog_col + (np.clip(lit, 0, 1) * 0.07 - np.clip(-lit, 0, 1) * 0.035)[..., None]
    kas = m3[..., 2] * KASUMI[1] * (0.35 + 0.65 * ss(0.2, 0.6, m2[..., 1]))
    fog_col = fog_col + (KASUMI[0] - fog_col) * kas[..., None]
    tide = ss(0.02, 0.32, F) * (1 - ss(0.32, 0.85, F))
    tide = tide * np.clip(0.35 + m1[..., 0] * 0.8 + (m2[..., 3] - 0.5) * 0.8, 0, 1)
    col = sheet + (fog_col - sheet) * F[..., None]
    col = col + (TIDE[0] - col) * (tide * TIDE[1])[..., None]
    # borde rasgado de arriba y abajo (los costados van contra las varillas)
    dk = 3.2 + (m3[..., 3] - 0.5) * 2.6 + (m1[..., 0] - 0.5) * 0.5
    aa = max(1e-4, (dpx_m if dpx_m is not None else sheet_m[1] / U.shape[0]) * 1.2)
    alpha = ss(dk - aa, dk + aa, ey) * ((U >= 0) & (U <= 1) & (V >= 0) & (V <= 1))
    return np.clip(col, 0, 1), alpha


def composite(sheet, fog_now, mist, t=0.0, fog_prev=None, reveal=1.0):
    """La lámina entera ya a la escala de la pantalla (fila 0 = norte)."""
    h, w = sheet.shape[:2]
    U, V = np.meshgrid((np.arange(w, dtype=np.float32) + 0.5) / w, 1.0 - (np.arange(h, dtype=np.float32) + 0.5) / h)
    return composite_uv(U, V, sheet, fog_now, mist, t, fog_prev, reveal)


# ------------------------------------------------------------------------------------------- maqueta de la pantalla
def font(path, size):
    return ImageFont.truetype(path, int(round(size)))


_SPRITES = {}


def sprite(name):
    if name not in _SPRITES:
        _SPRITES[name] = Image.open(os.path.join(UI, name + ".png")).convert("RGBA")
    return _SPRITES[name].copy()


def tint(img, color):
    arr = np.asarray(img, np.float32) / 255
    c = np.array(color, np.float32)[:3] / 255
    arr[..., :3] *= c
    if len(color) > 3:
        arr[..., 3] *= color[3] / 255
    return Image.fromarray((arr * 255).astype(np.uint8), "RGBA")


def paste_c(dst, img, cx, cy, size=None, rot=0.0, alpha=1.0):
    if size is not None:
        img = img.resize((max(1, int(round(size[0]))), max(1, int(round(size[1])))), Image.LANCZOS)
    if rot:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1:
        a = img.getchannel("A").point(lambda v: int(v * alpha))
        img.putalpha(a)
    x, y = int(round(cx - img.size[0] / 2)), int(round(cy - img.size[1] / 2))
    layer = Image.new("RGBA", dst.size, (0, 0, 0, 0))
    layer.paste(img, (x, y), img)
    dst.alpha_composite(layer)


def halo_text(dst, xy, text, fnt, fill, anchor="mm", halo=(9, 8, 12), halo_a=200, rad=5):
    """Texto con el halo de tinta de UIFactory.Legible (underlay de TMP dilatado y difuso)."""
    layer = Image.new("RGBA", dst.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, text, font=fnt, fill=halo + (halo_a,), anchor=anchor, stroke_width=3, stroke_fill=halo + (halo_a,))
    layer = layer.filter(ImageFilter.GaussianBlur(rad * 0.6))
    dst.alpha_composite(layer)
    ImageDraw.Draw(dst).text(xy, text, font=fnt, fill=fill + (255,), anchor=anchor)


def keycap(dst, x, y, glyph, h=40):
    """Tecla de papel (UIFactory.KeyCap) con la letra en tinta; x = borde izquierdo. Devuelve el ancho."""
    f = font(BODY_TTF, h * (0.4 if len(glyph) > 2 else 0.56))
    tw = ImageDraw.Draw(dst).textlength(glyph, font=f)
    w = max(h, tw + h * 0.56)
    cap = sprite("KeyCap").resize((int(w), int(h)), Image.LANCZOS)
    dst.alpha_composite(cap, (int(x), int(y - h / 2)))
    ImageDraw.Draw(dst).text((x + w / 2, y - h * 0.06), glyph, font=f, fill=INK + (255,), anchor="mm")
    return w


def layout(Wc, Hc):
    """Rect de la lámina en el canvas (centro y tamaño): el mismo cálculo que UIMap.LayoutMap."""
    aw = Wc - COL_X - PAD_R - 2 * ROD_GAP
    ah = Hc - 2 * PAD_V
    asp = M.SHEET_W / M.SHEET_H
    sw = min(aw, ah * asp)
    sh = sw / asp
    cx = min(max(Wc / 2, COL_X + ROD_GAP + sw / 2), Wc - PAD_R - ROD_GAP - sw / 2)
    return cx, Hc / 2, sw, sh


SOFT = 26.0     # suavizado de arriba y abajo del RectMask2D (UIMap.MapSoft)


class View:
    """El contenido de la lámina (unidades del canvas a zoom 1, centro 0, y hacia arriba) visto con zoom y paneo, como
    mapContent en UIMap.cs: pantalla = centro de la ventana + (p - pan) * zoom."""

    def __init__(self, cx, cy, sw, sh, zoom=1.0, pan=(0.0, 0.0)):
        self.cx, self.cy, self.sw, self.sh, self.zoom = cx, cy, sw, sh, zoom
        lim = np.array([sw, sh]) * 0.5 * (1 - 1 / zoom)
        self.pan = np.clip(np.array(pan, np.float64), -lim, lim)

    def content(self, x, z):
        return np.array([((x - M.IX0) / M.SHEET_W - 0.5) * self.sw, ((z - M.IZ0) / M.SHEET_H - 0.5) * self.sh])

    def screen(self, x, z):
        p = (self.content(x, z) - self.pan) * self.zoom
        return self.cx + p[0], self.cy - p[1]


def render_view(map_img, fog, mist, view, t=0.0, fog_prev=None, reveal=1.0):
    """La ventana de la lámina (sw x (sh + 2 SOFT)) como la dibuja el shader con el zoom y el paneo de la vista."""
    w, h = int(round(view.sw)), int(round(view.sh + 2 * SOFT))
    # la "mip" que corresponde: la lámina a la resolución que se ve (sin pasar la de la textura)
    tw = min(map_img.size[0], int(round(view.sw * view.zoom)))
    th = int(round(tw * map_img.size[1] / map_img.size[0]))
    mip = np.asarray(map_img.resize((tw, th), Image.LANCZOS), np.float32)[::-1] / 255   # fila 0 abajo
    xs = (np.arange(w, dtype=np.float32) + 0.5) - w / 2
    ys = h / 2 - (np.arange(h, dtype=np.float32) + 0.5)
    X, Y = np.meshgrid(xs, ys)
    U = ((X / view.zoom + view.pan[0]) / view.sw + 0.5).astype(np.float32)
    V = ((Y / view.zoom + view.pan[1]) / view.sh + 0.5).astype(np.float32)
    sheet = bilinear(mip, np.clip(U, 0, 1), np.clip(V, 0, 1), False)
    rgb, alpha = composite_uv(U, V, sheet, fog, mist, t, fog_prev, reveal, dpx_m=M.SHEET_H / (view.sh * view.zoom))
    # recorte suave de arriba y abajo (RectMask2D softness)
    edge = np.minimum(np.arange(h), h - 1 - np.arange(h)).astype(np.float32)[:, None] + 0.5
    alpha = alpha * np.clip(edge / SOFT, 0, 1)
    return Image.fromarray((np.dstack([rgb, alpha]) * 255).astype(np.uint8), "RGBA")


def column(scr, Wc, Hc, scene, gamepad=False):
    """La columna de tinta de la izquierda: logo, título, lugar, sellos, explorado, leyenda y teclas."""
    col = sprite("BrushSwash").resize((int(Hc + 240), 720), Image.LANCZOS)
    col = tint(col, (9, 8, 10))
    col = col.rotate(90, expand=True)
    col.putalpha(col.getchannel("A").point(lambda v: int(v * 0.96)))
    scr.alpha_composite(col, (int(300 - col.size[0] / 2), int(Hc / 2 - col.size[1] / 2)))
    logo = Image.open(LOGO).convert("RGBA")
    lw = 330
    logo = tint(logo.resize((lw, int(lw * logo.size[1] / logo.size[0])), Image.LANCZOS), PAPER)
    scr.alpha_composite(logo, (110, 90))
    d = ImageDraw.Draw(scr)
    halo_text(scr, (118, 290), "Mapa", font(TITLE_TTF, 44), GOLD, anchor="lt")
    paste_c(scr, sprite("Hanko_" + scene["zone_icon"]), 145, 423, (70, 70), rot=6)
    halo_text(scr, (196, 404), scene["zone"], font(TITLE_TTF, 32), PAPER, anchor="lm")
    halo_text(scr, (197, 440), scene["zone_sub"], font(BODY_TTF, 22), (199, 179, 120), anchor="lm")
    halo_text(scr, (112, 512), "Sellos", font(BODY_TTF, 24), (199, 191, 171), anchor="lm")
    for i, (ic, got) in enumerate(zip(("ZoneMountain", "ZoneLake", "ZoneBamboo"), scene["seals"])):
        s = sprite("Hanko_" + ic)
        if not got:
            s = tint(s, (77, 74, 82, 204))                       # UIMap: color (0.3, 0.29, 0.32, 0.8)
        paste_c(scr, s, 141 + i * 70, 567, (58, 58))
    halo_text(scr, (330, 567), f"{sum(scene['seals'])}/3", font(TITLE_TTF, 30), PAPER, anchor="lm")
    halo_text(scr, (112, 640), "Explorado", font(BODY_TTF, 24), (199, 191, 171), anchor="lm")
    halo_text(scr, (300, 640), f"{scene['pct']} %", font(TITLE_TTF, 32), GOLD, anchor="lm")
    rows = [("MapKaito", None, "Kaito", False), ("MapShrine", SHRINE, "Santuario", False)]
    if scene.get("prayed") is not None:
        rows.append(("MapShrine", SHRINE_BARE, "Sin rezar", False))
    rows += [("MapShrine", SHRINE, "Punto de reaparición", True), ("Hanko_IconBoss", None, "Guardián", False), ("MapPortal", (127, 224, 160), "Portal al dojo", False)]
    step = 36 if len(rows) > 5 else 40
    for i, (sp, c, label, glow) in enumerate(rows):
        y = 690 + i * step
        if glow:
            paste_c(scr, tint(sprite("SoftDot"), (255, 196, 79, 191)), 130, y, (54, 54))
        s = sprite(sp)
        if c is not None:
            s = tint(s, c)
        paste_c(scr, s, 130, y, (34, 34))
        halo_text(scr, (164, y), label, font(BODY_TTF, 24), (222, 214, 196), anchor="lm")
    hints = ([("Vista", "Cerrar"), ("RS", "Centrar")], [("RT", "Acercar"), ("LT", "Alejar")], [("Stick izq.", "Mover")]) if gamepad else \
            ([("M", "Cerrar"), ("Q", "Centrar")], [("Rueda", "Acercar"), ("WASD", "Mover")])
    f = font(BODY_TTF, 24)
    for r, row in enumerate(hints):
        y = Hc - (66 + (len(hints) - 1 - r) * 48)
        x = 110
        for glyph, label in row:
            x += keycap(scr, x, y, glyph) + 10
            halo_text(scr, (x, y), label, f, (222, 214, 196), anchor="lm")
            x += d.textlength(label, font=f) + 26


def declutter(items, view):
    """UIMap.DeclutterMarks: las marcas no se pisan (el sello del jefe queda fijo); corrimiento en unidades de la
    lámina a zoom 1, que se aplica por zoom^-0.7."""
    for it in items:
        it["at"] = view.content(it["x"], it["z"])
        it["nudge"] = np.zeros(2)
    for _ in range(24):
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                wa, wb = (0.0 if a["kind"] == "boss" else 1.0), (0.0 if b["kind"] == "boss" else 1.0)
                if wa + wb <= 0:
                    continue
                d = b["at"] + b["nudge"] - a["at"] - a["nudge"]
                need = (a["size"] + b["size"]) * 0.5 * 0.85 + 2
                dist = float(np.hypot(*d))
                if dist >= need:
                    continue
                u = d / dist if dist > 1e-3 else np.array([0.0, 1.0])
                push = (need - dist) / (wa + wb)
                a["nudge"] = a["nudge"] - u * push * wa
                b["nudge"] = b["nudge"] + u * push * wb


def mock(map_img, fog, mist, out_path, Wc, Hc, scene, zoom=1.0, pan=None, fog_prev=None, reveal=1.0, gamepad=False):
    """Pantalla del mapa (canvas Wc x Hc, 1:1) con la niebla del estado dado y las marcas que corresponden."""
    bg = np.zeros((int(Hc), int(Wc), 3), np.float32)
    yy = np.linspace(0, 1, int(Hc))[:, None, None]
    bg[:] = np.array([0.08, 0.10, 0.15]) * (0.7 + 0.5 * yy)
    scr = Image.fromarray((bg * 255).astype(np.uint8)).convert("RGBA")
    scr.alpha_composite(Image.new("RGBA", scr.size, (3, 3, 8, int(0.72 * 255))))
    column(scr, Wc, Hc, scene, gamepad)

    cx, cy, sw, sh = layout(Wc, Hc)
    kx, kz, kyaw = scene["kaito"]
    view = View(cx, cy, sw, sh, zoom, pan if pan is not None else View(cx, cy, sw, sh).content(*(scene.get("cursor") or (kx, kz))))
    shadow = Image.new("RGBA", scr.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle((cx - sw / 2 - 10, cy - sh / 2 - 11, cx + sw / 2 + 30, cy + sh / 2 + 39), fill=(0, 0, 0, 150))
    scr.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(16)))
    win = render_view(map_img, fog, mist, view, scene.get("t", 0.0), fog_prev, reveal)
    scr.alpha_composite(win, (int(round(cx - win.size[0] / 2)), int(round(cy - win.size[1] / 2))))
    rod = sprite("MapRod")
    rh = sh + 56
    k = ROD_W / rod.size[0]
    cap = int(round(40 * k))
    rimg = Image.new("RGBA", (int(ROD_W), int(rh)), (0, 0, 0, 0))
    rimg.alpha_composite(rod.crop((0, 0, rod.size[0], 40)).resize((int(ROD_W), cap), Image.LANCZOS), (0, 0))
    rimg.alpha_composite(rod.crop((0, 40, rod.size[0], rod.size[1] - 40)).resize((int(ROD_W), int(rh) - 2 * cap), Image.LANCZOS), (0, cap))
    rimg.alpha_composite(rod.crop((0, rod.size[1] - 40, rod.size[0], rod.size[1])).resize((int(ROD_W), cap), Image.LANCZOS), (0, int(rh) - cap))

    # ---- marcas (recortadas a la ventana, como el RectMask2D)
    marks = Image.new("RGBA", scr.size, (0, 0, 0, 0))
    s = zoom ** 0.3                                              # crecen un poco al acercar (zoom * zoom^-0.7)

    # lo recién descubierto entra cuando su niebla ya se abrió (UIMap.UpdateMapMarks: freshA)
    t_open = 0.45 + 0.9 * math.acos(1 - 2 * min(1.0, max(0.0, reveal))) / math.pi
    fresh_a = 1 - (1 - min(1.0, max(0.0, (t_open - 0.9) / 0.35))) ** 3

    def vis(x, z):
        gx, gy = int((x - M.IX0) // M.CELL), int((z - M.IZ0) // M.CELL)
        if not (0 <= gx < M.GW and 0 <= gy < M.GH and fog[gy, gx] < 0.5):
            return 0.0
        return fresh_a if fog_prev is not None and fog_prev[gy, gx] >= 0.5 else 1.0
    for lid, v in M.LABELS.items():
        if lid not in scene["zones"]:
            continue
        x, z, align, small, rot = M.label(v)
        px, py = view.screen(x, z)
        f = font(TITLE_TTF, (22 if small else 29) * s)
        # el nombre de una zona recién visitada entra con lo descubierto (UIMap: mapLabelFresh)
        la = fresh_a if lid in scene.get("fresh_zones", ()) else 1.0
        if la <= 0:
            continue
        lay = Image.new("RGBA", marks.size, (0, 0, 0, 0))
        if not rot:
            halo_text(lay, (px, py), scene["names"][lid], f, PAPER, anchor={-1: "rm", 0: "mm", 1: "lm"}[align], rad=6)
        else:
            tw = int(ImageDraw.Draw(marks).textlength(scene["names"][lid], font=f)) + 60
            sub = Image.new("RGBA", (tw, tw), (0, 0, 0, 0))
            halo_text(sub, (tw / 2, tw / 2), scene["names"][lid], f, PAPER, rad=6)
            paste_c(lay, sub.rotate(rot, resample=Image.BICUBIC), px, py)
        if la < 1:
            lay.putalpha(lay.getchannel("A").point(lambda q: int(q * la)))
        marks.alpha_composite(lay)
    # las marcas que se ven (en el orden en que las crea UIMap: santuarios, jefes, portales) y su despeje
    items = []
    for cid, x, z, yaw in W.CHECKPOINTS:
        if vis(x, z) > 0:
            items.append(dict(kind="cp", id=cid, x=x, z=z, size=34 if cid == scene["checkpoint"] else 27))
    for arch, ax, az, r, bx, bz, yaw in W.BOSSES:
        if vis(ax, az) > 0:
            items.append(dict(kind="boss", id=arch, x=ax, z=az, size=44))
    for pid, x, z, yaw, flag in W.PORTALS:
        if flag in scene["flags"] and vis(x, z) > 0:
            items.append(dict(kind="portal", id=pid, x=x, z=z, size=30))
    declutter(items, View(cx, cy, sw, sh))
    inv = zoom ** -0.7
    for it in items:
        cx0, cy0 = view.content(it["x"], it["z"]) + np.array(it["nudge"]) * inv
        px, py = view.cx + (cx0 - view.pan[0]) * zoom, view.cy - (cy0 - view.pan[1]) * zoom
        it["px"], it["py"] = px, py
        a = vis(it["x"], it["z"])
        if it["kind"] == "cp":
            if it["id"] == scene["checkpoint"]:
                paste_c(marks, tint(sprite("SoftDot"), (255, 196, 79, int(191 * a))), px, py, (64 * s, 64 * s))
            lit = scene.get("prayed") is None or it["id"] in scene["prayed"]
            paste_c(marks, tint(sprite("MapShrine"), SHRINE if lit else SHRINE_BARE), px, py, (it["size"] * s,) * 2, alpha=a)
        elif it["kind"] == "boss":
            name = {"goro": "ZoneMountain", "mizuchi": "ZoneLake", "ozeki": "ZoneBamboo", "kage": "ZoneMoon"}[it["id"]] if it["id"] in scene["bosses_done"] else "IconBoss"
            paste_c(marks, sprite("Hanko_" + name), px, py, (44 * s, 44 * s), rot=6, alpha=a)
        else:
            paste_c(marks, tint(sprite("MapPortal"), (127, 224, 160)), px, py, (30 * s, 30 * s), alpha=a)
    scene["_marks"] = {(it["kind"], it["id"]): (it["px"], it["py"]) for it in items}
    px, py = view.screen(kx, kz)
    ring = Image.new("RGBA", scr.size, (0, 0, 0, 0))
    rr = 30 * s
    ImageDraw.Draw(ring).ellipse((px - rr, py - rr, px + rr, py + rr), outline=(255, 209, 96, 150), width=3)
    marks.alpha_composite(ring)
    paste_c(marks, sprite("MapKaito"), px, py, (48 * s, 48 * s), rot=-kyaw)
    if scene.get("cursor"):
        qx, qz = scene["cursor"]
        px, py = view.screen(qx, qz)
        paste_c(marks, tint(sprite("Ring"), (255, 209, 96, 204)), px, py, (46 * s, 46 * s))
    clip = np.zeros((int(Hc), int(Wc)), np.float32)
    clip[int(cy - sh / 2 - SOFT):int(cy + sh / 2 + SOFT), int(cx - sw / 2):int(cx + sw / 2)] = 1
    a = np.asarray(marks.getchannel("A"), np.float32) * clip
    marks.putalpha(Image.fromarray(a.astype(np.uint8)))
    scr.alpha_composite(marks)
    for sx in (-1, 1):
        scr.alpha_composite(rimg, (int(cx + sx * (sw / 2 + 4) - ROD_W / 2), int(cy - rh / 2)))
    # ---- cartel de lo que está bajo el cursor (fuera del recorte)
    if scene.get("tooltip"):
        tx, tz, t1, t2 = scene["tooltip"]
        # sobre la marca tal como quedó dibujada (con su despeje)
        px, py = min(((x, y) for (x, y) in scene["_marks"].values()), key=lambda q: math.dist(q, view.screen(tx, tz)))
        f1, f2 = font(TITLE_TTF, 26), font(BODY_TTF, 20)
        d = ImageDraw.Draw(scr)
        w1 = max(d.textlength(t1, font=f1), d.textlength(t2, font=f2) if t2 else 0)
        bw = max(220, (w1 + 2 * 30) / (0.80 - 0.025))
        bh = ((62 if t2 else 34) + 2 * 8) / 0.73
        ban = tint(sprite("BrushBanner").resize((int(bw), int(bh)), Image.LANCZOS), (11, 10, 13, 230))
        left = (0.025 + 0.80) * 0.5                               # UIFactory.BannerLeftShare
        bxc = min(max(px, cx - sw / 2 + 6 + bw * left), cx + sw / 2 - 6 - bw * (0.80 - left))
        half = scene.get("tip_half", 13.5) * s                   # media marca en pantalla
        ink = ((62 if t2 else 34) + 16) / 2
        byc = py - (half + 4 + ink)
        if byc - ink < cy - sh / 2 + 6:                          # no entra arriba: abajo de la marca
            byc = py + half + 4 + ink
        shift = (0.5 - left) * bw
        paste_c(scr, ban, bxc + shift, byc)
        halo_text(scr, (bxc, byc - (13 if t2 else 0)), t1, f1, PAPER)
        if t2:
            halo_text(scr, (bxc, byc + 18), t2, f2, GOLD)
    scr.convert("RGB").save(out_path, quality=90)
    print("maqueta ->", out_path)


def check_labels(Wc, Hc):
    """Rectángulos de los nombres (todas las zonas a la vez, zoom 1) contra los otros nombres y las marcas: avisa lo
    que se pisa o queda a menos de 60 px en el mismo renglón (dos nombres seguidos se leen como uno)."""
    cx, cy, sw, sh = layout(Wc, Hc)
    view = View(cx, cy, sw, sh)
    d = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    boxes, obb = {}, {}
    for lid, v in M.LABELS.items():
        x, z, align, small, rot = M.label(v)
        f = font(TITLE_TTF, 22 if small else 29)
        px, py = view.screen(x, z)
        l, t, r, b = d.textbbox((px, py), NAMES[lid], font=f, anchor={-1: "rm", 0: "mm", 1: "lm"}[align])
        boxes[lid] = (l - 4, t - 4, r + 4, b + 4)
        # caja girada alrededor del ancla (en pantalla y hacia abajo: el giro antihorario es -rot)
        a = math.radians(-rot)
        ax, ay = np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])
        c = np.array([(l + r) / 2, (t + b) / 2]) - (px, py)
        c = np.array([px, py]) + ax * c[0] + ay * c[1]
        obb[lid] = (c, ax, ay, (r - l) / 2 + 4, (b - t) / 2 + 4, rot)

    def corners(o):
        c, ax, ay, hw, hh, _ = o
        return [c + ax * sx * hw + ay * sy * hh for sx in (-1, 1) for sy in (-1, 1)]

    def overlap(o1, o2):
        for axis in (o1[1], o1[2], o2[1], o2[2]):
            p1 = [float(np.dot(q, axis)) for q in corners(o1)]
            p2 = [float(np.dot(q, axis)) for q in corners(o2)]
            if max(p1) < min(p2) or max(p2) < min(p1):
                return False
        return True
    marks = [(cid, x, z, 15) for cid, x, z, yaw in W.CHECKPOINTS] + [(a, x, z, 22) for a, x, z, *_ in W.BOSSES] + \
            [(p, x + 0.0, z, 15) for p, x, z, *_ in W.PORTALS]
    bad = []
    ids = list(boxes)
    for i, a in enumerate(ids):
        A, OA = boxes[a], obb[a]
        xs, ys = [q[0] for q in corners(OA)], [q[1] for q in corners(OA)]
        if min(xs) < cx - sw / 2 + 20 or max(xs) > cx + sw / 2 - 20 or min(ys) < cy - sh / 2 + 20 or max(ys) > cy + sh / 2 - 20:
            bad.append(f"{a} queda contra el borde de la lámina")
        for bname in ids[i + 1:]:
            B, OB = boxes[bname], obb[bname]
            if overlap(OA, OB):
                bad.append(f"{a} pisa a {bname}")
            elif not OA[5] and not OB[5]:
                gap_x = max(B[0] - A[2], A[0] - B[2])
                over_y = min(A[3], B[3]) - max(A[1], B[1])
                if over_y > 0 and gap_x < 60:
                    bad.append(f"{a} / {bname}: {gap_x:.0f} px entre los dos en el mismo renglón")
        for mid, x, z, r in marks:
            q = np.array(view.screen(x, z)) - OA[0]
            if abs(float(np.dot(q, OA[1]))) < OA[3] + r and abs(float(np.dot(q, OA[2]))) < OA[4] + r:
                bad.append(f"{a} tapa {mid}")
    print(f"nombres {Wc}x{Hc}:", "bien" if not bad else "; ".join(bad))
    return bad


NAMES = {"hogar": "Hogar de Kaito", "campos": "Campos de Inaba", "bosque": "Linde del Bosque", "muralla": "La Muralla Kurokage",
         "jardin": "Jardín del Clan", "dojo": "Dojo Kurokage", "montana": "Montaña Kodoyama", "lago": "Aldea del Lago Kohan",
         "lago_cascada": "Cascada Kohan", "bambu": "Bosque de Bambú"}


def run(map_img, meta, mist_img, out_dir, ppm):
    os.makedirs(out_dir, exist_ok=True)
    for Wc, Hc in ((1920, 1080), (2560, 1080), (1920, 1440)):
        check_labels(Wc, Hc)
    map_img.save(os.path.join(out_dir, "map_sheet.jpg"), quality=88)
    mist_img.save(os.path.join(out_dir, "mist.png"))
    mist = np.asarray(mist_img, np.float32) / 255
    early, mid, full = exploration_states()
    reach = np.unpackbits(np.frombuffer(__import__("base64").b64decode(meta["reach"]), np.uint8), bitorder="little")[:M.GW * M.GH].reshape(M.GH, M.GW).astype(bool)

    def pct(st):
        return int(round(100.0 * ((st < 0.5) & reach).sum() / max(1, reach.sum())))
    base = dict(names=NAMES)
    s0 = dict(base, zone="Campos de Inaba", zone_sub="Aldea de granjeros", zone_icon="ZoneFields", seals=(False, False, False), checkpoint="cp_fields",
              zones={"hogar", "campos", "bosque", "muralla", "jardin"}, bosses_done=set(), flags=set(), kaito=(8, -100, 20), pct=pct(early))
    s1 = dict(base, zone="Montaña Kodoyama", zone_sub="Rocas, nieve y silencio", zone_icon="ZoneMountain", seals=(True, False, False), checkpoint="cp_mountain_top",
              zones={"hogar", "campos", "bosque", "muralla", "jardin", "montana", "lago"}, bosses_done={"goro"}, flags={"boss_goro"}, kaito=(-186, 108, 150),
              tooltip=(-189, 112, "Santuario de la Cumbre", "Punto de reaparición"), tip_half=17, pct=pct(mid),
              prayed={"cp_home", "cp_fields", "cp_forest", "cp_garden", "cp_mountain", "cp_mountain_top"})
    s2 = dict(base, zone="Jardín del Clan", zone_sub="La aldea de las luciérnagas", zone_icon="ZoneGarden", seals=(True, True, True), checkpoint="cp_dojo_gate",
              zones=set(NAMES), bosses_done={"goro", "mizuchi", "ozeki"}, flags={"boss_goro", "boss_mizuchi", "boss_ozeki"}, kaito=(2, 90, 0), pct=pct(full))
    mock(map_img, blur121(early), mist, os.path.join(out_dir, "mock_0_16x9.jpg"), 1920, 1080, s0)
    mock(map_img, blur121(mid), mist, os.path.join(out_dir, "mock_1_21x9.jpg"), 2560, 1080, s1)
    mock(map_img, blur121(full), mist, os.path.join(out_dir, "mock_2_4x3.jpg"), 1920, 1440, s2)
    # acercado con el mando: el cursor sobre la arena de Gorō (vencido) y su cartel
    s3 = dict(s1, cursor=(-200, 122), tooltip=(-200, 122, "Gorō", "Sello de la Montaña"), tip_half=22)
    mock(map_img, blur121(mid), mist, os.path.join(out_dir, "mock_3_16x9_zoom.jpg"), 1920, 1080, s3, zoom=2.4, gamepad=True)
    # lo nuevo se despeja al abrir: de la exploración del comienzo a la del medio
    frames = []
    for rv in (0.0, 0.35, 0.6, 1.0):
        p = os.path.join(out_dir, f"_reveal_{rv:.2f}.jpg")
        mock(map_img, blur121(mid), mist, p, 1920, 1080, dict(s1, tooltip=None, fresh_zones={"montana", "lago"}), fog_prev=blur121(early), reveal=rv)
        frames.append(Image.open(p).crop((690, 70, 1830, 1010)).resize((570, 470), Image.LANCZOS))
        os.remove(p)
    strip = Image.new("RGB", (570 * 4 + 30, 470), (10, 10, 14))
    for i, f in enumerate(frames):
        strip.paste(f, (i * 580, 0))
    strip.save(os.path.join(out_dir, "reveal_strip.jpg"), quality=88)
    print("vistas previas ->", out_dir)
