"""
Relleno de la bandana del HUD (la vida) calzado en el interior del marco.

El arte del equipo trae el marco vacío (Sprites/EmptyHealthBar.png) y el relleno (Sprites/HealthBarFull.png)
en dos lienzos de 1920x1080, pero el rojo está corrido ~50 px a la izquierda del interior de la banda: tapaba
la mitad del nudo y dejaba sin llenar la punta en diagonal de la derecha (con la vida llena seguía viéndose una
franja oscura). Acá el relleno se rehace con la forma EXACTA del interior de la banda del marco (la región roja
más grande, sin las puntas del nudo) pintada con el rojo del relleno del equipo, en un sprite del mismo tamaño
que el marco y con el mismo 9-slice: en Unity marco y relleno comparten el rect y calzan a cualquier ancho.

Lo llama Tools/Unity/generate_assets.py (ui_sprites) después de recortar el par; devuelve el área del relleno
(u0, 0, ancho, 1) que va a NindoContent.healthFillArea: dónde empieza y termina la banda en u del sprite.

Uso suelto:  python Tools/UI/hud_bandana.py   (rehace Nindo/Assets/Nindo/Art/UI/Health_Fill.png)
"""
import os
import sys
from collections import Counter

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Unity"))
from unity_yaml import ASSETS, texture_meta, write_meta  # noqa: E402

ART_UI = os.path.join(ASSETS, "Nindo", "Art", "UI")
BORDER = (252, 0, 60, 0)   # el mismo 9-slice que el marco (generate_assets.py: crop_pair de "Health")


def fill_color(fill_png):
    """El rojo del relleno del equipo (el color más repetido entre los píxeles opacos)."""
    a = np.asarray(Image.open(fill_png).convert("RGBA"))
    px = a[a[..., 3] > 250][:, :3]
    return Counter(map(tuple, px)).most_common(1)[0][0]


def band_mask(frame_png):
    """Alfa [0,1] del interior de la banda: la región roja conexa que pasa por el medio de la banda (las dos puntas
    del nudo quedan afuera: el contorno negro las separa). El borde suave sale de cuánto rojo tiene el píxel."""
    f = np.asarray(Image.open(frame_png).convert("RGBA")).astype(np.float32)
    red = (f[..., 0] > 20) & (f[..., 3] > 128)
    H, W = red.shape
    x = int(W * 0.55)                       # la banda ocupa casi todo el ancho; el nudo, el 15 % de la izquierda
    rows = np.nonzero(red[:, x])[0]
    if len(rows) == 0:
        raise RuntimeError("el marco de la bandana no tiene interior rojo")
    seed = (x, int(np.median(rows)))
    lab = Image.fromarray((red * 255).astype(np.uint8), "L").copy()   # fromarray comparte el buffer (solo lectura)
    ImageDraw.floodfill(lab, seed, 128, thresh=0)
    band = np.asarray(lab) == 128
    near = np.asarray(Image.fromarray((band * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(5))) > 0
    body = np.median(f[band][:, 0])                      # rojo del interior (~77)
    soft = np.clip(f[..., 0] / max(1.0, body), 0, 1) * (f[..., 3] / 255)
    return np.where(band, 1.0, np.where(near, soft, 0.0)), band


def bandana_fill(frame_png, fill_png):
    alpha, band = band_mask(frame_png)
    color = fill_color(fill_png)
    H, W = alpha.shape
    arr = np.zeros((H, W, 4), np.uint8)
    arr[..., :3] = color
    arr[..., 3] = np.clip(alpha * 255 + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "RGBA").save(fill_png)
    write_meta(fill_png, texture_meta(sprite=True, compress=False, max_size=2048, border=BORDER), force=True)
    cols = np.nonzero(band.any(0))[0]
    u0, u1 = cols[0] / W, (cols[-1] + 1) / W
    return [u0, 0.0, u1 - u0, 1.0]


if __name__ == "__main__":
    area = bandana_fill(os.path.join(ART_UI, "Health_Frame.png"), os.path.join(ART_UI, "Health_Fill.png"))
    print("healthFillArea x=%.6f width=%.6f" % (area[0], area[2]))
