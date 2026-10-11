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


def composite(sheet, fog_now, mist, t=0.0, fog_prev=None, reveal=1.0):
    """sheet: (h, w, 3) sRGB 0..1 de la lámina ya a la escala de la pantalla (fila 0 = norte). Devuelve (rgb, alfa).
    Es frag() de NindoUIMap.shader, línea por línea."""
    h, w = sheet.shape[:2]
    sheet_m = np.array([M.SHEET_W, M.SHEET_H], np.float32)
    tile = M.MIST_TILE
    u = (np.arange(w, dtype=np.float32) + 0.5) / w
    v = 1.0 - (np.arange(h, dtype=np.float32) + 0.5) / h        # v 0 = sur (abajo)
    U, V = np.meshgrid(u, v)
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
    aa = sheet_m[1] / h * 1.2
    alpha = ss(dk - aa, dk + aa, ey)
    return np.clip(col, 0, 1), alpha


# ------------------------------------------------------------------------------------------- maqueta de la pantalla
def font(path, size):
    return ImageFont.truetype(path, int(round(size)))


def sprite(name):
    return Image.open(os.path.join(UI, name + ".png")).convert("RGBA")


def tint(img, color):
    arr = np.asarray(img, np.float32) / 255
    c = np.array(color, np.float32)[:3] / 255
    arr[..., :3] *= c
    return Image.fromarray((arr * 255).astype(np.uint8), "RGBA")


def paste_c(dst, img, cx, cy, size=None, rot=0.0, alpha=1.0):
    if size is not None:
        img = img.resize((max(1, int(size[0])), max(1, int(size[1]))), Image.LANCZOS)
    if rot:
        img = img.rotate(rot, resample=Image.BICUBIC, expand=True)
    if alpha < 1:
        a = img.getchannel("A").point(lambda v: int(v * alpha))
        img.putalpha(a)
    dst.alpha_composite(img, (int(round(cx - img.size[0] / 2)), int(round(cy - img.size[1] / 2))))


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
    cx = COL_X + ROD_GAP + aw / 2 + 0.0
    cy = Hc / 2
    return cx, cy, sw, sh


def world_to_sheet(x, z, cx, cy, sw, sh):
    return cx + ((x - M.IX0) / M.SHEET_W - 0.5) * sw, cy - ((z - M.IZ0) / M.SHEET_H - 0.5) * sh


def mock(sheet_img, fog, mist, out_path, Wc, Hc, scene):
    """Pantalla del mapa (canvas Wc x Hc, ya en píxeles 1:1) con la niebla del estado dado y las marcas que corresponden."""
    scr = Image.new("RGBA", (int(Wc), int(Hc)), (0, 0, 0, 255))
    # el juego en pausa detrás (aproximado: un plano nocturno) y el velo de tinta
    bg = np.zeros((int(Hc), int(Wc), 3), np.float32)
    yy = np.linspace(0, 1, int(Hc))[:, None, None]
    bg[:] = np.array([0.08, 0.10, 0.15]) * (0.7 + 0.5 * yy)
    scr = Image.fromarray((bg * 255).astype(np.uint8)).convert("RGBA")
    veil = Image.new("RGBA", scr.size, (3, 3, 8, int(0.72 * 255)))
    scr.alpha_composite(veil)
    # columna de tinta (MenuColumn: BrushSwash girado -90, 720 de grueso, centro en x 300)
    col = sprite("BrushSwash").resize((int(Hc + 240), 720), Image.LANCZOS)
    col = tint(col, (9, 8, 10))
    col = col.rotate(90, expand=True)
    a = col.getchannel("A").point(lambda v: int(v * 0.96))
    col.putalpha(a)
    scr.alpha_composite(col, (int(300 - col.size[0] / 2), int(Hc / 2 - col.size[1] / 2)))
    logo = Image.open(LOGO).convert("RGBA")
    lw = 330
    logo = tint(logo.resize((lw, int(lw * logo.size[1] / logo.size[0])), Image.LANCZOS), PAPER)
    scr.alpha_composite(logo, (110, 90))
    d = ImageDraw.Draw(scr)
    halo_text(scr, (118, 290), "Mapa", font(TITLE_TTF, 44), GOLD, anchor="lt")
    # lugar
    hk = sprite("Hanko_" + scene["zone_icon"]).resize((70, 70), Image.LANCZOS).rotate(6, resample=Image.BICUBIC, expand=True)
    scr.alpha_composite(hk, (110 - 3, 388 - 3))
    halo_text(scr, (196, 404), scene["zone"], font(TITLE_TTF, 32), PAPER, anchor="lm")
    d.text((197, 440), scene["zone_sub"], font=font(BODY_TTF, 22), fill=(200, 178, 120, 255), anchor="lm")
    # sellos
    d.text((112, 512), "Sellos", font=font(BODY_TTF, 24), fill=(198, 190, 172, 255), anchor="lm")
    for i, (ic, got) in enumerate(zip(("ZoneMountain", "ZoneLake", "ZoneBamboo"), scene["seals"])):
        s = sprite("Hanko_" + ic).resize((58, 58), Image.LANCZOS)
        if not got:
            arr = np.asarray(s, np.float32)
            lum = arr[..., :3].mean(-1, keepdims=True)
            arr[..., :3] = lum * 0.35 + 18
            arr[..., 3] *= 0.75
            s = Image.fromarray(arr.clip(0, 255).astype(np.uint8), "RGBA")
        scr.alpha_composite(s, (112 + i * 70, 538))
    d.text((112 + 3 * 70 + 8, 567), f"{sum(scene['seals'])}/3", font=font(TITLE_TTF, 30), fill=PAPER + (255,), anchor="lm")
    # explorado
    d.text((112, 640), "Explorado", font=font(BODY_TTF, 24), fill=(198, 190, 172, 255), anchor="lm")
    halo_text(scr, (300, 640), f"{scene['pct']} %", font(TITLE_TTF, 32), GOLD, anchor="lm")
    # leyenda
    ly = 700
    rows = [("MapKaito", None, "Kaito"), ("MapShrine", SHRINE, "Santuario"), ("MapShrine", SHRINE, "Punto de reaparición"),
            ("Hanko_IconBoss", None, "Guardián"), ("MapPortal", (127, 224, 160), "Portal al dojo")]
    for i, (sp, c, label) in enumerate(rows):
        y = ly + i * 44
        s = sprite(sp)
        if c is not None:
            s = tint(s, c)
        paste_c(scr, s, 130, y, (34, 34))
        d.text((164, y), label, font=font(BODY_TTF, 24), fill=(222, 214, 196, 255), anchor="lm")
    # teclas (abajo)
    by = Hc - 118
    x = 110
    for glyph, label in (("M", "Cerrar"), ("Q", "Centrar")):
        x += keycap(scr, x, by, glyph) + 10
        d.text((x, by), label, font=font(BODY_TTF, 24), fill=(222, 214, 196, 255), anchor="lm")
        x += d.textlength(label, font=font(BODY_TTF, 24)) + 26
    x = 110
    by2 = Hc - 66
    for glyph, label in (("Rueda", "Acercar"), ("WASD", "Mover")):
        x += keycap(scr, x, by2, glyph) + 10
        d.text((x, by2), label, font=font(BODY_TTF, 24), fill=(222, 214, 196, 255), anchor="lm")
        x += d.textlength(label, font=font(BODY_TTF, 24)) + 26

    # ---- lámina
    cx, cy, sw, sh = layout(Wc, Hc)
    sheet = np.asarray(sheet_img.resize((int(round(sw)), int(round(sh))), Image.LANCZOS), np.float32) / 255
    rgb, alpha = composite(sheet, fog, mist, t=scene.get("t", 0.0))
    # sombra suave debajo de la lámina
    shadow = Image.new("RGBA", scr.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle((cx - sw / 2 + 10, cy - sh / 2 + 18, cx + sw / 2 + 10, cy + sh / 2 + 22), fill=(0, 0, 0, 170))
    scr.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(18)))
    sheet_rgba = Image.fromarray((np.dstack([rgb, alpha]) * 255).astype(np.uint8), "RGBA")
    scr.alpha_composite(sheet_rgba, (int(round(cx - sw / 2)), int(round(cy - sh / 2))))
    # varillas
    rod = sprite("MapRod")
    rh = sh + 56
    top, mid, bot = rod.crop((0, 0, rod.size[0], 40)), rod.crop((0, 40, rod.size[0], rod.size[1] - 40)), rod.crop((0, rod.size[1] - 40, rod.size[0], rod.size[1]))
    k = ROD_W / rod.size[0]
    rimg = Image.new("RGBA", (int(ROD_W), int(rh)), (0, 0, 0, 0))
    tt = top.resize((int(ROD_W), int(40 * k)), Image.LANCZOS)
    bb = bot.resize((int(ROD_W), int(40 * k)), Image.LANCZOS)
    mm = mid.resize((int(ROD_W), int(rh - 2 * tt.size[1])), Image.LANCZOS)
    rimg.alpha_composite(tt, (0, 0)); rimg.alpha_composite(mm, (0, tt.size[1])); rimg.alpha_composite(bb, (0, tt.size[1] + mm.size[1]))
    for sx in (-1, 1):
        scr.alpha_composite(rimg, (int(cx + sx * (sw / 2 + 4) - ROD_W / 2), int(cy - rh / 2)))

    # ---- marcas
    def vis(x, z):
        gx, gy = int((x - M.IX0) // M.CELL), int((z - M.IZ0) // M.CELL)
        return 0 <= gx < M.GW and 0 <= gy < M.GH and fog[gy, gx] < 0.5
    ls = sw / 1133.0                                             # las marcas y los nombres no escalan con la lámina
    for lid, (x, z, align, small) in M.LABELS.items():
        if lid not in scene["zones"]:
            continue
        px, py = world_to_sheet(x, z, cx, cy, sw, sh)
        halo_text(scr, (px, py), scene["names"][lid], font(TITLE_TTF, (22 if small else 29) * max(0.85, ls)), PAPER, anchor={-1: "rm", 0: "mm", 1: "lm"}[align], rad=6)
    for cid, x, z, yaw in W.CHECKPOINTS:
        if not vis(x, z):
            continue
        px, py = world_to_sheet(x, z, cx, cy, sw, sh)
        cur = cid == scene["checkpoint"]
        if cur:
            glow = Image.new("RGBA", scr.size, (0, 0, 0, 0))
            ImageDraw.Draw(glow).ellipse((px - 24, py - 24, px + 24, py + 24), fill=(255, 196, 80, 170))
            scr.alpha_composite(glow.filter(ImageFilter.GaussianBlur(8)))
        paste_c(scr, tint(sprite("MapShrine"), SHRINE), px, py, (34, 34) if cur else (27, 27))
    for arch, ax, az, r, bx, bz, yaw in W.BOSSES:
        if not vis(ax, az):
            continue
        px, py = world_to_sheet(ax, az, cx, cy, sw, sh)
        done = arch in scene["bosses_done"]
        name = {"goro": "ZoneMountain", "mizuchi": "ZoneLake", "ozeki": "ZoneBamboo", "kage": "ZoneMoon"}[arch] if done else "IconBoss"
        paste_c(scr, sprite("Hanko_" + name), px, py, (44, 44), rot=-6)
    for pid, x, z, yaw, flag in W.PORTALS:
        if flag in scene["flags"] and vis(x, z):
            px, py = world_to_sheet(x, z, cx, cy, sw, sh)
            paste_c(scr, tint(sprite("MapPortal"), (127, 224, 160)), px + 14, py - 12, (30, 30))
    kx, kz, kyaw = scene["kaito"]
    px, py = world_to_sheet(kx, kz, cx, cy, sw, sh)
    ring = Image.new("RGBA", scr.size, (0, 0, 0, 0))
    ImageDraw.Draw(ring).ellipse((px - 30, py - 30, px + 30, py + 30), outline=(255, 209, 96, 150), width=3)
    scr.alpha_composite(ring)
    paste_c(scr, sprite("MapKaito"), px, py, (48, 48), rot=-kyaw)
    if scene.get("tooltip"):
        tx, tz, t1, t2 = scene["tooltip"]
        px, py = world_to_sheet(tx, tz, cx, cy, sw, sh)
        f1, f2 = font(TITLE_TTF, 26), font(BODY_TTF, 20)
        w1 = max(d.textlength(t1, font=f1), d.textlength(t2, font=f2))
        ban = sprite("BrushBanner")
        bw = (w1 + 2 * 30) / (0.80 - 0.025)
        bh = (64 + 2 * 8) / 0.73
        ban = tint(ban.resize((int(bw), int(bh)), Image.LANCZOS), (11, 10, 13))
        bxc = px + 0.0
        byc = py - 62
        shift = (0.5 - (0.025 + 0.80) * 0.5) * bw
        paste_c(scr, ban, bxc + shift, byc, alpha=0.9)
        dd = ImageDraw.Draw(scr)
        dd.text((bxc, byc - 13), t1, font=f1, fill=PAPER + (255,), anchor="mm")
        dd.text((bxc, byc + 18), t2, font=f2, fill=GOLD + (255,), anchor="mm")
    scr.convert("RGB").save(out_path, quality=90)
    print("maqueta ->", out_path)


def run(map_img, meta, mist_img, out_dir, ppm):
    os.makedirs(out_dir, exist_ok=True)
    map_img.save(os.path.join(out_dir, "map_sheet.jpg"), quality=88)
    map_img.resize((map_img.size[0] // 3, map_img.size[1] // 3), Image.LANCZOS).save(os.path.join(out_dir, "map_sheet_small.jpg"), quality=88)
    mist_img.save(os.path.join(out_dir, "mist.png"))
    mist = np.asarray(mist_img, np.float32) / 255
    states = exploration_states()
    names = {"hogar": "Hogar de Kaito", "campos": "Campos de Inaba", "bosque": "Linde del Bosque", "muralla": "La Muralla Kurokage",
             "jardin": "Jardín del Clan", "dojo": "Dojo Kurokage", "montana": "Montaña Kodoyama", "lago": "Aldea del Lago Kohan",
             "lago_cascada": "Cascada Kohan", "bambu": "Bosque de Bambú"}
    reach = np.unpackbits(np.frombuffer(__import__("base64").b64decode(meta["reach"]), np.uint8), bitorder="little")[:M.GW * M.GH].reshape(M.GH, M.GW).astype(bool)
    scenes = [
        dict(zone="Campos de Inaba", zone_sub="Aldea de granjeros", zone_icon="ZoneFields", seals=(False, False, False), checkpoint="cp_fields",
             zones={"hogar", "campos", "bosque", "muralla", "jardin"}, bosses_done=set(), flags=set(), kaito=(8, -100, 20)),
        dict(zone="Montaña Kodoyama", zone_sub="Rocas, nieve y silencio", zone_icon="ZoneMountain", seals=(True, False, False), checkpoint="cp_mountain_top",
             zones={"hogar", "campos", "bosque", "muralla", "jardin", "montana", "lago"}, bosses_done={"goro"}, flags={"boss_goro"}, kaito=(-186, 108, 150),
             tooltip=(-189, 112, "Santuario de la Cumbre", "Punto de reaparición")),
        dict(zone="Jardín del Clan", zone_sub="La aldea de las luciérnagas", zone_icon="ZoneGarden", seals=(True, True, True), checkpoint="cp_dojo_gate",
             zones=set(names), bosses_done={"goro", "mizuchi", "ozeki"}, flags={"boss_goro", "boss_mizuchi", "boss_ozeki"}, kaito=(2, 90, 0)),
    ]
    sizes = [("16x9", 1920, 1080), ("21x9", 2560, 1080), ("4x3", 1920, 1440)]
    for i, (st, sc) in enumerate(zip(states, scenes)):
        fog = blur121(st)
        sc["names"] = names
        sc["pct"] = int(round(100.0 * ((st < 0.5) & reach).sum() / max(1, reach.sum())))
        tag, Wc, Hc = sizes[i]
        mock(map_img, fog, mist, os.path.join(out_dir, f"mock_{i}_{tag}.jpg"), Wc, Hc, sc)
    # la lámina entera con la niebla del medio, a la resolución de la textura / 2 (para mirar el borde de cerca)
    half = np.asarray(map_img.resize((map_img.size[0] // 2, map_img.size[1] // 2), Image.LANCZOS), np.float32) / 255
    rgb, alpha = composite(half, blur121(states[1]), mist)
    bgc = np.array([0.05, 0.05, 0.08], np.float32)
    img = rgb * alpha[..., None] + bgc * (1 - alpha[..., None])
    Image.fromarray((img * 255).astype(np.uint8)).save(os.path.join(out_dir, "fog_mid_half.jpg"), quality=90)
    print("vistas previas ->", out_dir)
