"""Comparación a escala del Chikuō ermitaño con el concepto (Python del sistema + Pillow; Blender no trae PIL).

  python chikuo_overlay.py layout.json

Cada vista es un recorte del concepto y un render ortográfico del modelo que cubre exactamente el mismo rectángulo del
mundo (chikuo_review.Review.metric_sheet calcula la cámara): los dos llevan la misma grilla en metros (alturas cada
10 cm, columnas cada 10 cm desde el eje) y al lado va la superposición al 50 %, donde cualquier diferencia de proporción
se ve como un doble contorno. Es la herramienta para modelar "al pie de la letra": la hoja se mide, no se mira a ojo.

layout = {"out": png, "title": str, "views": [{"label": str, "concept": jpg, "crop": [x0, y0, x1, y1], "model": png,
          "sole_y": px, "center_x": px, "mm_px": float, "zoom": float}]}
"""
import json, sys
from PIL import Image, ImageDraw, ImageFont


def font(size):
    for f in ("arial.ttf", "DejaVuSans.ttf", "segoeui.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def grid(im, v, step_m=0.10):
    """Líneas de altura (rojas, con la cota) y de distancia al eje (azules) sobre una imagen del tamaño del recorte."""
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = v["crop"]
    k = im.width / (x1 - x0)
    px_m = 1000.0 / v["mm_px"]
    f = font(12)
    z = 0.0
    while True:
        y = (v["sole_y"] - z * px_m - y0) * k
        if y < 0:
            break
        if y <= im.height:
            d.line([(0, y), (im.width, y)], fill=(230, 60, 60), width=1)
            d.text((3, y + 1), f"{z:.1f}", fill=(255, 230, 90), font=f)
        z = round(z + step_m, 3)
    for i in range(-30, 31):
        x = (v["center_x"] + i * step_m * px_m - x0) * k
        if 0 <= x <= im.width:
            d.line([(x, 0), (x, im.height)], fill=(70, 150, 255) if i else (120, 255, 160), width=1)
    return im


def main(path):
    lay = json.load(open(path, encoding="utf-8"))
    tiles = []
    for v in lay["views"]:
        x0, y0, x1, y1 = v["crop"]
        z = v.get("zoom", 1.0)
        size = (int((x1 - x0) * z), int((y1 - y0) * z))
        c = Image.open(v["concept"]).convert("RGB").crop((x0, y0, x1, y1)).resize(size, Image.LANCZOS)
        m = Image.open(v["model"]).convert("RGB").resize(size, Image.LANCZOS)
        mix = Image.blend(c, m, 0.5)
        tiles.append((v["label"], [grid(c, v), grid(m, v), grid(mix, v)]))
    f_t, f_c = font(20), font(14)
    W = max(sum(t.width for t in ims) + 4 * len(ims) for _, ims in tiles)
    H = 34 + sum(ims[0].height + 26 for _, ims in tiles)
    sheet = Image.new("RGB", (W, H), (14, 14, 18))
    d = ImageDraw.Draw(sheet)
    d.text((8, 6), lay.get("title", ""), fill=(255, 255, 255), font=f_t)
    y = 34
    for label, ims in tiles:
        x = 0
        for im, sub in zip(ims, ("concepto", "modelo", "superpuestos")):
            sheet.paste(im, (x, y + 22))
            d.text((x + 4, y + 3), f"{label}: {sub}", fill=(255, 230, 160), font=f_c)
            x += im.width + 4
        y += ims[0].height + 26
    # las hojas de revisión no pasan de 1280 px de ancho
    if sheet.width > 1280:
        sheet = sheet.resize((1280, int(sheet.height * 1280 / sheet.width)), Image.LANCZOS)
    sheet.save(lay["out"], optimize=True)
    print("SHEET", lay["out"], sheet.size)


if __name__ == "__main__":
    main(sys.argv[1])
