"""Réplica fuera de Unity del plano al cielo de la pelea de Kokuyō (MoonEclipse.PlaySkyShot) para buscar rectángulos:
el cielo (Nindo/Night Sky con la luna apagada de HideSky), el quad de la luna (Nindo/Moon, a 340 m, de frente a la
cámara: la versión de hoy y la de antes de la fase C2), el terreno (world_terrain.height con la niebla de la zona del
dojo o la del eclipse) y un tonemap ACES con bloom aproximado. Mide, en cada estado (luna llena, eclipse 0..1, destello
de parry y de la luna que vuelve, nubes, aparición), cuánto suma la luna en la franja del borde del quad y el salto en
8 bits al cruzarlo; y renderiza tiras de cuadros del cambio de luna con el mismo plano y la mezcla desde la cámara de
juego (donde se ve el horizonte: el borde del mapa).
Uso: python moon_sky_check.py CARPETA_DE_SALIDA     (escribe .png y un resumen .json; necesita numpy y PIL)
"""
import os, sys, json, math
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
W, H = 640, 360
FOV = 30.0
ARENA = np.array([0.0, 8.0, 132.0])
SKY_DIR = np.array([0.16, 0.5, 0.85]); SKY_DIR /= np.linalg.norm(SKY_DIR)
MOON_DIST = 340.0
HALF = MOON_DIST * math.tan(math.radians(3.4)) / 0.3


# ---------------------------------------------------------------------------------------------- utilidades de shader
def frac(x):
    return x - np.floor(x)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def hash21(p):   # NindoMoon.hash21
    q = frac(np.stack([p[..., 0], p[..., 1], p[..., 0]], -1) * 0.1031)
    q = q + (q * (q[..., [1, 2, 0]] + 33.33)).sum(-1, keepdims=True)
    return frac((q[..., 0] + q[..., 1]) * q[..., 2])


def vnoise2(p):
    i = np.floor(p); f = p - i
    u = f * f * (3 - 2 * f)
    a = hash21(i); b = hash21(i + [1, 0]); c = hash21(i + [0, 1]); d = hash21(i + [1, 1])
    return (a + (b - a) * u[..., 0]) * (1 - u[..., 1]) + (c + (d - c) * u[..., 0]) * u[..., 1]


def fbm_moon(p):
    return vnoise2(p) * 0.55 + vnoise2(p * 2.07 + 3.1) * 0.28 + vnoise2(p * 4.13 + 7.7) * 0.17


def hash13(p):   # NindoSky.hash13
    p = frac(p * 0.1031)
    p = p + (p * (p[..., [2, 1, 0]] + 31.32)).sum(-1, keepdims=True)
    return frac((p[..., 0] + p[..., 1]) * p[..., 2])


def noise2_sky(p):
    i = np.floor(p); f = p - i
    def h(o):
        q = i + o
        return hash13(np.stack([q[..., 0], q[..., 1], np.full(q.shape[:-1], 1.7)], -1))
    a, b, c, d = h([0, 0]), h([1, 0]), h([0, 1]), h([1, 1])
    u = f * f * (3 - 2 * f)
    return (a + (b - a) * u[..., 0]) * (1 - u[..., 1]) + (c + (d - c) * u[..., 0]) * u[..., 1]


def fbm_sky(p):
    v, a = 0.0, 0.5
    for _ in range(4):
        v = v + a * noise2_sky(p); p = p * 2.03; a *= 0.5
    return v


# ---------------------------------------------------------------------------------------------- cámara (Unity)
def look_basis(fwd, up=np.array([0.0, 1.0, 0.0])):
    f = fwd / np.linalg.norm(fwd)
    r = np.cross(up, f); r /= np.linalg.norm(r)
    u = np.cross(f, r)
    return f, r, u


def sky_pose():
    """MoonEclipse.PlaySkyShot: desde el sur del patio, bajo, 8° por debajo de la luna y un poco hacia el dojo."""
    pos = ARENA + np.array([0.0, 2.5, -12.0])
    flat = np.array([SKY_DIR[0], 0.0, SKY_DIR[2]]); flat /= np.linalg.norm(flat)
    flat = flat + (np.array([0.0, 0.0, 1.0]) - flat) * 0.4; flat /= np.linalg.norm(flat)
    pitch = math.asin(SKY_DIR[1]) - math.radians(8.0)
    d = flat * math.cos(pitch) + np.array([0.0, 1.0, 0.0]) * math.sin(pitch)
    return pos, d


def game_pose():
    """Cámara de combate de Kokuyō (pitch 54, ~21 m) con Kaito en el centro del patio mirando al norte."""
    kaito = ARENA + np.array([0.0, 0.0, -4.0])
    pitch, dist = math.radians(54.0), 21.0
    fwd = np.array([0.0, -math.sin(pitch), math.cos(pitch)])
    return kaito + np.array([0.0, 1.2, 0.0]) - fwd * dist, fwd


def slerp_dir(a, b, w):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    om = math.acos(float(np.clip(np.dot(a, b), -1, 1)))
    if om < 1e-5:
        return a
    return (math.sin((1 - w) * om) * a + math.sin(w * om) * b) / math.sin(om)


def rays(pos, fwd):
    f, r, u = look_basis(fwd)
    th = math.tan(math.radians(FOV) / 2)
    xs = (np.arange(W) + 0.5) / W * 2 - 1
    ys = 1 - (np.arange(H) + 0.5) / H * 2
    X, Y = np.meshgrid(xs * th * W / H, ys * th)
    d = f[None, None] + X[..., None] * r[None, None] + Y[..., None] * u[None, None]
    return d / np.linalg.norm(d, axis=-1, keepdims=True), f


# ---------------------------------------------------------------------------------------------- cielo
SKY = dict(zen=np.array([0.015, 0.028, 0.08]), mid=np.array([0.045, 0.08, 0.16]), hor=np.array([0.13, 0.19, 0.27]),
           gnd=np.array([0.04, 0.055, 0.09]), cloud=np.array([0.1, 0.13, 0.2]), amount=0.35, density=0.9965, stars=1.6)


def sky(dirs, t):
    h = dirs[..., 1]
    t1 = np.clip(h * 3, 0, 1)[..., None]; t2 = np.clip((h - 0.25) * 1.6, 0, 1)[..., None]
    up = SKY["hor"] + (SKY["mid"] - SKY["hor"]) * t1
    up = up + (SKY["zen"] - up) * t2
    dn = SKY["hor"] + (SKY["gnd"] - SKY["hor"]) * np.clip(-h * 6, 0, 1)[..., None]
    col = np.where((h > 0)[..., None], up, dn)
    p = dirs * 260.0
    cell = np.floor(p)
    rnd = hash13(cell)
    c = cell + 0.5 + (np.stack([hash13(cell + 1.3), hash13(cell + 2.7), hash13(cell + 4.1)], -1) - 0.5) * 0.6
    dist = np.linalg.norm(p - c, axis=-1)
    star = np.clip(1 - dist * 2.2, 0, 1)
    tw = 0.65 + 0.35 * np.sin(t * (1.5 + rnd * 4.0) + rnd * 60.0)
    mask = (rnd > SKY["density"]) & (h > 0.02)
    tint = np.where((frac(rnd * 37.0) > 0.5)[..., None], [1.0, 0.92, 0.8], [0.8, 0.88, 1.0])
    col = col + (mask * star * star * SKY["stars"] * tw * np.clip(h * 4, 0, 1))[..., None] * tint
    hp = np.maximum(h, 1e-3)
    uv = np.stack([dirs[..., 0], dirs[..., 2]], -1) / (hp + 0.25)[..., None] * 1.6 + [t * 0.004, t * 0.002]
    cl = smoothstep(0.55 - SKY["amount"] * 0.3, 0.95, fbm_sky(uv)) * np.clip(h * 5, 0, 1)
    cl = np.where(h > 0, cl, 0.0)
    col = col + (SKY["cloud"] - col) * (cl * 0.75)[..., None]
    # HideSky: la luna del cielo con _MoonGlow 0 y _MoonSize 0.0001 (no aporta nada)
    return col


# ---------------------------------------------------------------------------------------------- la luna (Nindo/Moon)
MOON = dict(moon=np.array([1.9, 1.86, 1.72]), halo=np.array([0.55, 0.7, 1.0]), corona=np.array([1.2, 0.4, 3.2]),
            ink=np.array([0.07, 0.04, 0.1]), r=0.3, edir=np.array([-0.8, 0.6]))


def glow(x, k, r):
    return np.maximum(np.exp(-k * x) - math.exp(-k * (1 - r)), 0.0)


def moon_frag(p, aa, t, eclipse, veil, flash, alpha, old=False):
    """La función frag del shader sobre las coordenadas p del quad (-1..1). Devuelve (rgb premultiplicado, alfa)."""
    r = MOON["r"]
    d = np.linalg.norm(p, axis=-1)
    disc = 1 - smoothstep(r - aa, r + aa, d)
    mp = p / r
    maria = smoothstep(0.45, 0.75, fbm_moon(mp * 1.6 + 2.3))
    face = MOON["moon"] * ((1 - 0.28 * maria) * (0.92 + 0.08 * (1 - (mp * mp).sum(-1))))[..., None]
    dr = MOON["edir"] / np.linalg.norm(MOON["edir"])
    c = dr * (1 - eclipse) * r * 2.3
    inkD = np.linalg.norm(p - c, axis=-1)
    ang = np.arctan2(p[..., 1] - c[1], p[..., 0] - c[0])
    rough = r * (1 + 0.035 * (vnoise2(np.stack([ang * 3.0, np.full_like(ang, t * 0.4)], -1)) - 0.5))
    covered = (1 - smoothstep(rough - aa, rough + aa, inkD)) * (1.0 if eclipse >= 0.001 else 0.0)
    col = (face + (MOON["ink"] - face) * covered[..., None]) * disc[..., None]
    a = disc.copy()
    x = np.maximum(d - r, 0.0)
    lit = 1 - eclipse * 0.92
    full = smoothstep(0.75, 1.0, eclipse)
    pa = np.arctan2(p[..., 1], p[..., 0])
    rays_ = 0.55 + 0.45 * vnoise2(np.stack([pa * 5.0 + t * 0.15, np.full_like(pa, t * 0.3)], -1))
    if old:
        halo = np.exp(-x * 9) * 0.55 + np.exp(-x * 3) * 0.18
        corona = np.exp(-np.abs(d - r * 1.02) * 40) + np.exp(-x * 7) * 0.5 * rays_ * (1 - disc)
    else:
        edge = 1 - smoothstep(0.62, 0.98, d)
        halo = (glow(x, 9, r) * 0.55 + glow(x, 3, r) * 0.18) * edge
        corona = (np.exp(-np.abs(d - r * 1.02) * 40) + glow(x, 7, r) * 0.5 * rays_ * (1 - disc)) * edge
    col = col + MOON["halo"] * (halo * lit * (1 - disc))[..., None]
    col = col + MOON["corona"] * (corona * full * (1 - disc * 0.85))[..., None]
    cl = smoothstep(0.42, 0.7, fbm_moon(p * 1.4 + [t * 0.03, 0.0]))
    col = col * (1 - veil * (0.35 + 0.6 * cl))[..., None]
    a = a * (1 - veil * 0.5 * cl)
    if old:
        col = col * (1 + flash * 2.5)
        col = col + MOON["halo"] * (flash * np.exp(-x * 2) * (1 - disc))[..., None]
    else:
        col = col * (1 + flash * 2.5 * disc)[..., None]
        fe = 1 - smoothstep(0.45, 0.98, d)
        col = col + MOON["halo"] * (0.35 * (1 - np.exp(-flash * glow(x, 6, r) * 1.5)) * fe * (1 - disc))[..., None]
    return col * alpha, np.clip(a, 0, 1) * alpha


def moon_hit(pos, dirs):
    """Intersección con el quad de la luna (MoonEclipse.LateUpdate: sigue a la cámara, de frente). p del shader, profundidad."""
    C = pos + SKY_DIR * MOON_DIST
    f, r, u = look_basis(C - pos)
    den = dirs @ f
    tt = ((C - pos) @ f) / np.maximum(den, 1e-6)
    P = pos + dirs * tt[..., None]
    lx = ((P - C) @ r) / HALF
    ly = ((P - C) @ u) / HALF
    inside = (np.abs(lx) <= 1) & (np.abs(ly) <= 1) & (den > 0)
    return np.stack([lx, ly], -1), tt, inside


# ---------------------------------------------------------------------------------------------- terreno
def height_grid():
    sys.path.insert(0, os.path.join(REPO, "Tools", "Blender", "world"))
    import world_terrain as T
    import world_plan as WP
    x0, x1, z0, z1 = WP.MAP_BOUNDS
    step = 2.0
    xs = np.arange(-140, 141, step); zs = np.arange(96, z1 + 0.1, step)
    g = np.array([[T.height(float(x), float(z)) for x in xs] for z in zs])
    return xs, zs, g, (x0, x1, z0, z1)


def terrain(pos, dirs, grid, far=400.0):
    xs, zs, g, (x0, x1, z0, z1) = grid
    n = dirs.reshape(-1, 3)
    hit_t = np.full(n.shape[0], np.inf)
    t = 1.0
    alive = np.ones(n.shape[0], bool)
    while t < far:
        P = pos + n * t
        ix = (P[:, 0] - xs[0]) / (xs[1] - xs[0]); iz = (P[:, 2] - zs[0]) / (zs[1] - zs[0])
        inb = (ix >= 0) & (ix < len(xs) - 1) & (iz >= 0) & (iz < len(zs) - 1) & (P[:, 0] <= x1) & (P[:, 2] <= z1)
        i0 = np.clip(ix.astype(int), 0, len(xs) - 2); j0 = np.clip(iz.astype(int), 0, len(zs) - 2)
        fx = np.clip(ix - i0, 0, 1); fz = np.clip(iz - j0, 0, 1)
        hh = (g[j0, i0] * (1 - fx) + g[j0, i0 + 1] * fx) * (1 - fz) + (g[j0 + 1, i0] * (1 - fx) + g[j0 + 1, i0 + 1] * fx) * fz
        hit = alive & inb & (P[:, 1] <= hh)
        hit_t[hit] = t
        alive &= ~hit
        if not alive.any():
            break
        t += 0.5 if t < 60 else 1.0
    return hit_t.reshape(dirs.shape[:2])


# ---------------------------------------------------------------------------------------------- imagen final
def aces(x):
    a, b, c, d, e = 2.51, 0.03, 2.43, 0.59, 0.14
    return np.clip((x * (a * x + b)) / (x * (c * x + d) + e), 0, 1)


def blur(img, s):
    k = int(3 * s) | 1
    xs = np.arange(-k, k + 1)
    w = np.exp(-xs ** 2 / (2 * s * s)); w /= w.sum()
    out = img.copy()
    for axis in (0, 1):
        pad = [(0, 0)] * 3; pad[axis] = (k, k)
        p = np.pad(out, pad, mode="edge")
        acc = np.zeros_like(out)
        for i, wi in enumerate(w):
            sl = [slice(None)] * 3; sl[axis] = slice(i, i + out.shape[axis])
            acc += wi * p[tuple(sl)]
        out = acc
    return out


def post(lin, bloom=True):
    lin = lin * 2 ** 0.4   # postExposure 0.4 (ScreenFX)
    if bloom:
        br = np.maximum(lin - 0.95, 0.0)
        bl = sum(blur(br, s) * wgt for s, wgt in ((2, 0.45), (6, 0.3), (16, 0.25)))
        lin = lin + bl * 0.9 * np.array([1.0, 0.92, 0.8])
    c = aces(lin)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def render(pos, fwd, st, grid=None, old=False, fog=("dojo", 1.0)):
    dirs, f = rays(pos, fwd)
    col = sky(dirs, st["t"])
    p, tt, inside = moon_hit(pos, dirs)
    d = np.linalg.norm(p, axis=-1)
    aa = np.maximum(np.maximum(np.abs(np.gradient(d, axis=0)), np.abs(np.gradient(d, axis=1))), 1e-4)
    mc, ma = moon_frag(p, aa, st["t"], st["eclipse"], st["veil"], st["flash"], st["alpha"], old)
    moon_add = np.where(inside[..., None], mc, 0.0)
    moon_a = np.where(inside, ma, 0.0)
    terr = np.full(dirs.shape[:2], np.inf) if grid is None else terrain(pos, dirs, grid)
    occl = terr < tt
    col_sky = col.copy()
    col = np.where(occl[..., None], col, moon_add + col * (1 - moon_a)[..., None])
    if grid is not None:
        e = st.get("fog", 0.0)
        fogc = np.array([0.1, 0.06, 0.1]) * (1 - e) + np.array([0.118, 0.078, 0.188]) * e
        dens = 0.010 * (1 + 0.15 * e)
        vd = terr * (dirs @ f)
        ground = np.array([0.045, 0.05, 0.055]) * (0.6 + 0.4 * (1 - e))
        fogf = np.exp(-(dens * vd) ** 2)[..., None]
        tc = fogc + (ground - fogc) * fogf
        col = np.where(np.isfinite(terr)[..., None], tc, col)
    return col, col_sky, inside, p, occl


def edge_metrics(col, col_sky, inside, p, occl):
    """Lo que suma la luna en la franja del borde del quad (|p| > 0.97 de su lado) y el salto en 8 bits al cruzarlo."""
    band = inside & (np.maximum(np.abs(p[..., 0]), np.abs(p[..., 1])) > 0.97) & ~occl
    diff = np.abs(col - col_sky).max(-1)
    out8 = (post(col, bloom=False) * 255).round()
    ref8 = (post(col_sky, bloom=False) * 255).round()
    step = np.abs(out8 - ref8).max(-1)
    return float(diff[band].max()) if band.any() else 0.0, float(step[band].max()) if band.any() else 0.0


def save(img, path):
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(path)


def label(img, text):
    from PIL import ImageDraw
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    ImageDraw.Draw(im).text((6, 4), text, fill=(255, 240, 200))
    return np.asarray(im).astype(float) / 255


def main(out):
    os.makedirs(out, exist_ok=True)
    sp, sd = sky_pose()
    summary = {"estados": []}
    # 1) barrido de estados con el plano al cielo final (sin terreno: solo los planos del cielo)
    states = []
    for e in np.linspace(0, 1, 11):
        states.append(dict(name="eclipse %.1f" % e, eclipse=float(e), veil=0.0, flash=0.0, alpha=1.0, t=3.0))
    for fl in (0.6, 1.0, 1.5, 2.0):
        states.append(dict(name="destello %.1f" % fl, eclipse=1.0, veil=0.0, flash=fl, alpha=1.0, t=5.0))
        states.append(dict(name="vuelve la luna %.1f" % fl, eclipse=0.0, veil=0.0, flash=fl, alpha=1.0, t=5.0))
    for v in (1.0, 0.5):
        states.append(dict(name="nubes %.1f" % v, eclipse=0.0, veil=v, flash=0.0, alpha=1.0, t=1.0))
    for al in (0.3, 0.7):
        states.append(dict(name="aparece %.1f" % al, eclipse=0.0, veil=0.0, flash=0.0, alpha=al, t=1.0))
    worst = {"hoy": [0, 0], "antes": [0, 0]}
    for st in states:
        row = {"estado": st["name"]}
        for tag, old in (("hoy", False), ("antes", True)):
            col, cs, ins, p, oc = render(sp, sd, st, None, old)
            m, s8 = edge_metrics(col, cs, ins, p, oc)
            row[tag] = {"luz_en_el_borde": round(m, 5), "salto_8bit": s8}
            worst[tag][0] = max(worst[tag][0], m); worst[tag][1] = max(worst[tag][1], s8)
        summary["estados"].append(row)
    summary["peor"] = worst
    # 2) tiras: el cambio de luna en el plano al cielo (antes / hoy) y la diferencia con el cielo solo x40
    seq = [0.0, 0.25, 0.5, 0.75, 1.0]
    for tag, old in (("hoy", False), ("antes", True)):
        tiles, diffs = [], []
        for e in seq:
            st = dict(eclipse=e, veil=0.0, flash=0.0, alpha=1.0, t=3.0)
            col, cs, ins, p, oc = render(sp, sd, st, None, old)
            tiles.append(label(post(col), "%s  eclipse %.2f" % (tag, e)))
            diffs.append(label(np.clip(np.abs(col - cs).max(-1, keepdims=True) * 40, 0, 1).repeat(3, -1),
                               "luz de la luna x40 (borde del quad = rectangulo)"))
        save(np.concatenate([np.concatenate(tiles, 1), np.concatenate(diffs, 1)], 0), os.path.join(out, "cielo_eclipse_%s.png" % tag))
    # 3) la luna que vuelve (destello 1.5 que baja a 4/s) y un parry en el eclipse
    tiles = []
    for tag, old in (("antes", True), ("hoy", False)):
        for st in (dict(eclipse=0.0, veil=0.0, flash=1.5, alpha=1.0, t=5.0), dict(eclipse=1.0, veil=0.0, flash=1.0, alpha=1.0, t=5.0)):
            col, cs, ins, p, oc = render(sp, sd, st, None, old)
            tiles.append(label(post(col), "%s  %s" % (tag, "vuelve la luna" if st["eclipse"] == 0 else "parry en el eclipse")))
    save(np.concatenate([np.concatenate(tiles[:2], 1), np.concatenate(tiles[2:], 1)], 0), os.path.join(out, "cielo_destellos.png"))
    # 4) la mezcla desde la cámara de juego hasta el cielo, con terreno y la niebla del eclipse (el horizonte y el borde
    #    del mapa solo se ven acá)
    grid = height_grid()
    gp, gd = game_pose()
    tiles = []
    for w in (0.0, 0.25, 0.5, 0.75, 1.0):
        k = w * w * (3 - 2 * w)
        pos = gp + (sp - gp) * k
        fwd = slerp_dir(gd, sd, k)
        st = dict(eclipse=min(1.0, w), veil=0.0, flash=0.0, alpha=1.0, t=3.0, fog=min(1.0, w))
        col, cs, ins, p, oc = render(pos, fwd, st, grid, False)
        tiles.append(label(post(col), "mezcla %.2f (cámara de juego -> cielo)" % w))
    save(np.concatenate(tiles, 0), os.path.join(out, "cielo_mezcla_terreno.png"))
    json.dump(summary, open(os.path.join(out, "moon_sky_check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary["peor"], ensure_ascii=False))
    for r in summary["estados"]:
        print(r["estado"], r["hoy"], r["antes"])


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out_moon"))
