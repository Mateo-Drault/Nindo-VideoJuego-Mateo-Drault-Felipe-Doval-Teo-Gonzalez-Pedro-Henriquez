"""Réplica fuera de Unity de los planos de la pelea de Kokuyō que ven el cielo, para buscar rectángulos y bordes de capa:
el cielo (Nindo/Night Sky con la luna apagada de HideSky y, si se pide, llevado hacia el eclipse como MoonEclipse.DriveSky),
el quad de la luna (Nindo/Moon, a 340 m, de frente a la cámara: la versión de hoy y la de antes de la fase C2), el terreno
(world_terrain.height con la niebla exp2 del dojo o la del eclipse) y el post de URP en espacio de color Gamma (el del
proyecto: el uber pasa a lineal, exposición 0.4, bloom, ACES y vuelve a sRGB).
Mide:
  1) en cada estado de la luna (llena, eclipse 0..1, destellos, nubes, aparición) cuánto suma la luna en la franja del borde
     del quad y el salto en 8 bits al cruzarlo (el rectángulo de C2);
  2) en las mezclas de la cámara al cielo con terreno (la transición al eclipse con sus tiempos reales, el plano de la muerte
     y de la ejecución, que miran casi horizontal en plena oscuridad, y el final con la luna que vuelve) el salto en 8 bits
     entre el borde de arriba del terreno y el cielo justo encima, con el cielo de siempre y con el que sigue a la niebla.
Uso: python moon_sky_check.py CARPETA_DE_SALIDA     (escribe .png y un resumen .json; necesita numpy y PIL)
"""
import os, sys, json, math, re
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
W, H = 640, 360
ARENA = np.array([0.0, 8.0, 132.0])
SKY_DIR = np.array([0.16, 0.5, 0.85]); SKY_DIR /= np.linalg.norm(SKY_DIR)
MOON_DIST = 340.0
HALF = MOON_DIST * math.tan(math.radians(3.4)) / 0.3


def _gamma_project():
    """ProjectSettings: m_ActiveColorSpace 0 = Gamma (el de Nindo), 1 = Linear."""
    try:
        txt = open(os.path.join(REPO, "Nindo", "ProjectSettings", "ProjectSettings.asset"), encoding="utf-8").read()
        m = re.search(r"m_ActiveColorSpace:\s*(\d)", txt)
        return m is None or m.group(1) == "0"
    except OSError:
        return True


GAMMA = _gamma_project()


# ---------------------------------------------------------------------------------------------- utilidades de shader
def frac(x):
    return x - np.floor(x)


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ss(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


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
    return pos, d, 30.0


def game_pose():
    """Cámara de combate de Kokuyō (pitch 54, ~21 m) con Kaito en el centro del patio mirando al norte."""
    kaito = ARENA + np.array([0.0, 0.0, -4.0])
    pitch, dist = math.radians(54.0), 21.0
    fwd = np.array([0.0, -math.sin(pitch), math.cos(pitch)])
    return kaito + np.array([0.0, 1.2, 0.0]) - fwd * dist, fwd, 30.0


def death_pose():
    """Boss.Die de Kokuyō al final del plano (3.6 s): 8.5 m al sur de él, 3.6 m arriba, mirando a 2 m (FOV 34). La
    ejecución (UpdateExecution) es parecida: ~9.4 m, 3 m arriba, mirando a 2.3 m (FOV 36). Las dos casi horizontales,
    en pleno eclipse: ven el horizonte a los costados del dojo."""
    boss = ARENA + np.array([0.0, 0.0, 2.0])
    pos = boss + np.array([0.0, 3.6, -8.5])
    return pos, (boss + np.array([0.0, 2.0, 0.0])) - pos, 34.0


def slerp_dir(a, b, w):
    a = a / np.linalg.norm(a); b = b / np.linalg.norm(b)
    om = math.acos(float(np.clip(np.dot(a, b), -1, 1)))
    if om < 1e-5:
        return a
    return (math.sin((1 - w) * om) * a + math.sin(w * om) * b) / math.sin(om)


def blend_pose(p0, p1, w):
    """CameraDirector: smoothstep del peso, Lerp de la posición, Slerp de la rotación y Lerp del FOV."""
    k = ss(w)
    return p0[0] + (p1[0] - p0[0]) * k, slerp_dir(p0[1], p1[1], k), p0[2] + (p1[2] - p0[2]) * k


def rays(pos, fwd, fov):
    f, r, u = look_basis(fwd)
    th = math.tan(math.radians(fov) / 2)
    xs = (np.arange(W) + 0.5) / W * 2 - 1
    ys = 1 - (np.arange(H) + 0.5) / H * 2
    X, Y = np.meshgrid(xs * th * W / H, ys * th)
    d = f[None, None] + X[..., None] * r[None, None] + Y[..., None] * u[None, None]
    return d / np.linalg.norm(d, axis=-1, keepdims=True), f


# ---------------------------------------------------------------------------------------------- cielo
SKY = dict(zen=np.array([0.015, 0.028, 0.08]), mid=np.array([0.045, 0.08, 0.16]), hor=np.array([0.13, 0.19, 0.27]),
           gnd=np.array([0.04, 0.055, 0.09]), cloud=np.array([0.1, 0.13, 0.2]), amount=0.35, density=0.9965, stars=1.6)
DOJO_FOG = np.array([0.1, 0.06, 0.1])            # StoryText: la zona del dojo (densidad 0.010, exp2)
ECLIPSE_FOG = np.array([0.118, 0.078, 0.188])    # MoonEclipse.EclipseFog (#1e1430), densidad x1.15
# El terreno iluminado, ESTIMADO (no hay render de Unity): albedo ~0.25 por (luz de la luna 1.05, azulada, a ~0.45 de
# coseno + el ambiente trilight del dojo); en el eclipse la luz a 0.35 y violeta y el ambiente apagado (MoonEclipse.Eclipse).
# El salto del borde del terreno depende de esto: los números sirven para comparar cielos, no como valor absoluto
TERRAIN_LIT = np.array([0.14, 0.137, 0.18])
TERRAIN_ECLIPSE = np.array([0.062, 0.053, 0.089])


def _knobs():
    """Las perillas de MoonEclipse.DriveSky leídas del C# (si se cambian allá, la réplica las sigue)."""
    src = open(os.path.join(REPO, "Nindo", "Assets", "Nindo", "Scripts", "FX", "MoonEclipse.cs"), encoding="utf-8").read()
    out = {}
    for name in ("SkyHorizonToFog", "SkyMidToFog", "SkyZenithDark", "SkyCloudDark", "SkyStarsBoost"):
        m = re.search(r"\b%s\s*=\s*(-?[0-9.]+)f?" % name, src)
        if not m:
            raise SystemExit("moon_sky_check: falta %s en MoonEclipse.cs" % name)
        out[name] = float(m.group(1))
    return out


DRIVE = _knobs()


def sky_colors(k, fog):
    """MoonEclipse.DriveSky: k = cuánto eclipse tiene la niebla (0..1), fog = el color de la niebla ahora."""
    lerp = lambda a, b, t: a + (b - a) * t
    return dict(hor=lerp(SKY["hor"], fog, k * DRIVE["SkyHorizonToFog"]), gnd=lerp(SKY["gnd"], fog, k * DRIVE["SkyHorizonToFog"]),
                mid=lerp(SKY["mid"], fog, k * DRIVE["SkyMidToFog"]), zen=SKY["zen"] * lerp(1, DRIVE["SkyZenithDark"], k),
                cloud=SKY["cloud"] * lerp(1, DRIVE["SkyCloudDark"], k), stars=SKY["stars"] * lerp(1, DRIVE["SkyStarsBoost"], k))


def sky(dirs, t, sc=None):
    sc = sc or dict(hor=SKY["hor"], gnd=SKY["gnd"], mid=SKY["mid"], zen=SKY["zen"], cloud=SKY["cloud"], stars=SKY["stars"])
    h = dirs[..., 1]
    t1 = np.clip(h * 3, 0, 1)[..., None]; t2 = np.clip((h - 0.25) * 1.6, 0, 1)[..., None]
    up = sc["hor"] + (sc["mid"] - sc["hor"]) * t1
    up = up + (sc["zen"] - up) * t2
    dn = sc["hor"] + (sc["gnd"] - sc["hor"]) * np.clip(-h * 6, 0, 1)[..., None]
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
    col = col + (mask * star * star * sc["stars"] * tw * np.clip(h * 4, 0, 1))[..., None] * tint
    hp = np.maximum(h, 1e-3)
    uv = np.stack([dirs[..., 0], dirs[..., 2]], -1) / (hp + 0.25)[..., None] * 1.6 + [t * 0.004, t * 0.002]
    cl = smoothstep(0.55 - SKY["amount"] * 0.3, 0.95, fbm_sky(uv)) * np.clip(h * 5, 0, 1)
    cl = np.where(h > 0, cl, 0.0)
    col = col + (sc["cloud"] - col) * (cl * 0.75)[..., None]
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


def to_linear(c):
    c = np.maximum(c, 0.0)
    return np.where(c <= 0.04045, c / 12.92, np.power((c + 0.055) / 1.055, 2.4))


def post(scene, bloom=True):
    """URP en Gamma: lo que dibujaron los shaders (valores gamma) pasa a lineal en el uber; ahí exposición (ScreenFX 0.4),
    bloom (umbral 0.95 en gamma), ACES y de vuelta a sRGB."""
    lin = to_linear(scene) if GAMMA else scene
    lin = lin * 2 ** 0.4
    if bloom:
        br = np.maximum(lin - (to_linear(np.array(0.95)) if GAMMA else 0.95), 0.0)
        bl = sum(blur(br, s) * wgt for s, wgt in ((2, 0.45), (6, 0.3), (16, 0.25)))
        lin = lin + bl * 0.9 * np.array([1.0, 0.92, 0.8])
    c = aces(lin)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def render(pose, st, grid=None, old=False):
    """st: t, eclipse (tinta de la luna), veil, flash, alpha, fog (0..1: de la niebla del dojo a la del eclipse) y
    drive (el cielo sigue a la niebla como MoonEclipse.DriveSky)."""
    pos, fwd, fov = pose
    dirs, f = rays(pos, fwd, fov)
    e = st.get("fog", 0.0)
    fogc = DOJO_FOG * (1 - e) + ECLIPSE_FOG * e
    col = sky(dirs, st["t"], sky_colors(e, fogc) if st.get("drive") else None)
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
        dens = 0.010 * (1 + 0.15 * e)
        vd = terr * (dirs @ f)
        ground = TERRAIN_LIT * (1 - e) + TERRAIN_ECLIPSE * e
        fogf = np.exp(-(dens * vd) ** 2)[..., None]
        tc = fogc + (ground - fogc) * fogf
        col = np.where(np.isfinite(terr)[..., None], tc, col)
    return col, col_sky, inside, p, occl, terr


def edge_metrics(col, col_sky, inside, p, occl):
    """Lo que suma la luna en la franja del borde del quad (|p| > 0.97 de su lado) y el salto en 8 bits al cruzarlo."""
    band = inside & (np.maximum(np.abs(p[..., 0]), np.abs(p[..., 1])) > 0.97) & ~occl
    diff = np.abs(col - col_sky).max(-1)
    out8 = (post(col, bloom=False) * 255).round()
    ref8 = (post(col_sky, bloom=False) * 255).round()
    step = np.abs(out8 - ref8).max(-1)
    return float(diff[band].max()) if band.any() else 0.0, float(step[band].max()) if band.any() else 0.0


def skyline_step(col, terr):
    """El borde de arriba del terreno contra el cielo: en cada columna, el salto en 8 bits (canal que más cambia) entre
    el terreno dos píxeles abajo del borde y el cielo dos arriba. Devuelve (mediana, p90, columnas) o None."""
    img = (post(col, bloom=False) * 255).round()
    hit = np.isfinite(terr)
    steps = []
    for x in range(hit.shape[1]):
        rows = np.nonzero(hit[:, x])[0]
        if len(rows) == 0:
            continue
        r = rows[0]
        if r < 3 or r > hit.shape[0] - 4:
            continue
        steps.append(float(np.abs(img[r + 2, x] - img[r - 2, x]).max()))
    if not steps:
        return None
    steps.sort()
    return round(steps[len(steps) // 2], 1), round(steps[9 * len(steps) // 10], 1), len(steps)


def save(img, path):
    Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(path)


def label(img, text):
    from PIL import ImageDraw
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    ImageDraw.Draw(im).text((6, 4), text, fill=(255, 240, 200))
    return np.asarray(im).astype(float) / 255


def timeline_frames(grid, summary, out):
    """Las mezclas con terreno, con sus tiempos reales, con el cielo de siempre (antes) y el que sigue a la niebla (hoy)."""
    sp, gp, dp = sky_pose(), game_pose(), death_pose()
    seqs = []
    # (a) KokuyoBoss.Eclipse: fx.Eclipse() (niebla, luz y tinta de la luna en 2 s, smoothstep) y PlaySkyShot(0.9, 0.5,
    #     0.6) en el mismo instante: entra en 0.5 s, queda 0.9 y vuelve en 0.6 a la cámara de juego (que no ve el cielo)
    ecl = []
    for t in (0.15, 0.3, 0.45, 0.9, 1.4, 1.6, 1.75):
        w = min(1.0, t / 0.5) if t <= 1.4 else max(0.0, 1 - (t - 1.4) / 0.6)
        k = ss(t / 2.0)
        ecl.append(("eclipse t=%.2f s" % t, blend_pose(gp, sp, w), dict(t=3 + t, eclipse=k, veil=0.0, flash=0.0, alpha=1.0, fog=k)))
    seqs.append(("transicion_eclipse", ecl))
    # (b) el plano de la muerte (y el de la ejecución, parecido) en pleno eclipse: casi horizontal, ve el horizonte
    seqs.append(("muerte_ejecucion", [("muerte, eclipse", dp, dict(t=5.0, eclipse=1.0, veil=0.0, flash=0.0, alpha=1.0, fog=1.0))]))
    # (c) el final: desde el plano de la muerte, PlaySkyShot(1.0, 0.6, 0.8); a los 0.6 s MoonReturn (la tinta se va en
    #     0.35 s, destello 1.5 que baja 4/s, niebla de vuelta en 3 s)
    fin = []
    for t in (0.2, 0.4, 0.6, 0.8, 1.2, 1.6, 2.0):
        w = min(1.0, t / 0.6) if t <= 1.6 else max(0.0, 1 - (t - 1.6) / 0.8)
        r = max(0.0, t - 0.6)
        ink = 1.0 - ss(r / 0.35) if t >= 0.6 else 1.0
        flash = max(0.0, 1.5 - 4 * r) if t >= 0.6 else 0.0
        fog = 1.0 - ss(r / 3.0) if t >= 0.6 else 1.0
        fin.append(("final t=%.1f s" % t, blend_pose(dp, sp, w), dict(t=8 + t, eclipse=ink, veil=0.0, flash=flash, alpha=1.0, fog=fog)))
    seqs.append(("final_luna_vuelve", fin))
    summary["borde_terreno_cielo_8bit"] = {}
    for name, frames in seqs:
        rows, res = [], {}
        for lab, pose, st in frames:
            pair = []
            for tag, drive in (("antes", False), ("hoy", True)):
                col, cs, ins, p, oc, terr = render(pose, dict(st, drive=drive), grid)
                m = skyline_step(col, terr)
                res.setdefault(lab, {})[tag] = m
                pair.append(label(post(col), "%s  %s  borde %s" % (tag, lab, "-" if m is None else "%.0f/%.0f" % m[:2])))
            rows.append(np.concatenate(pair, 1))
        summary["borde_terreno_cielo_8bit"][name] = res
        save(np.concatenate(rows, 0), os.path.join(out, "cielo_%s.png" % name))


def main(out):
    os.makedirs(out, exist_ok=True)
    sp = sky_pose()
    summary = {"espacio_de_color": "Gamma" if GAMMA else "Linear", "perillas_DriveSky": DRIVE, "estados": []}
    # 1) barrido de estados con el plano al cielo final (sin terreno: solo los planos del cielo)
    states = []
    for e in np.linspace(0, 1, 11):
        states.append(dict(name="eclipse %.1f" % e, eclipse=float(e), veil=0.0, flash=0.0, alpha=1.0, t=3.0, fog=float(e), drive=True))
    for fl in (0.6, 1.0, 1.5, 2.0):
        states.append(dict(name="destello %.1f" % fl, eclipse=1.0, veil=0.0, flash=fl, alpha=1.0, t=5.0, fog=1.0, drive=True))
        states.append(dict(name="vuelve la luna %.1f" % fl, eclipse=0.0, veil=0.0, flash=fl, alpha=1.0, t=5.0, fog=1.0, drive=True))
    for v in (1.0, 0.5):
        states.append(dict(name="nubes %.1f" % v, eclipse=0.0, veil=v, flash=0.0, alpha=1.0, t=1.0))
    for al in (0.3, 0.7):
        states.append(dict(name="aparece %.1f" % al, eclipse=0.0, veil=0.0, flash=0.0, alpha=al, t=1.0))
    worst = {"hoy": [0, 0], "antes": [0, 0]}
    for st in states:
        row = {"estado": st["name"]}
        for tag, old in (("hoy", False), ("antes", True)):
            col, cs, ins, p, oc, _ = render(sp, st, None, old)
            m, s8 = edge_metrics(col, cs, ins, p, oc)
            row[tag] = {"luz_en_el_borde": round(m, 5), "salto_8bit": s8}
            worst[tag][0] = max(worst[tag][0], m); worst[tag][1] = max(worst[tag][1], s8)
        summary["estados"].append(row)
    summary["peor_borde_del_quad"] = worst
    # 2) tiras: el cambio de luna en el plano al cielo (quad de antes de C2 con el cielo de siempre / hoy con el cielo que
    #    sigue a la niebla) y la luz de la luna sola x40 (un rectángulo se vería ahí)
    seq = [0.0, 0.25, 0.5, 0.75, 1.0]
    for tag, old in (("hoy", False), ("antes", True)):
        tiles, diffs = [], []
        for e in seq:
            st = dict(eclipse=e, veil=0.0, flash=0.0, alpha=1.0, t=3.0, fog=e, drive=not old)
            col, cs, ins, p, oc, _ = render(sp, st, None, old)
            tiles.append(label(post(col), "%s  eclipse %.2f" % (tag, e)))
            diffs.append(label(np.clip(np.abs(col - cs).max(-1, keepdims=True) * 40, 0, 1).repeat(3, -1),
                               "luz de la luna x40 (borde del quad = rectangulo)"))
        save(np.concatenate([np.concatenate(tiles, 1), np.concatenate(diffs, 1)], 0), os.path.join(out, "cielo_eclipse_%s.png" % tag))
    # 3) la luna que vuelve (destello 1.5 que baja a 4/s) y un parry en el eclipse
    tiles = []
    for tag, old in (("antes", True), ("hoy", False)):
        for st in (dict(eclipse=0.0, veil=0.0, flash=1.5, alpha=1.0, t=5.0, fog=1.0, drive=not old),
                   dict(eclipse=1.0, veil=0.0, flash=1.0, alpha=1.0, t=5.0, fog=1.0, drive=not old)):
            col, cs, ins, p, oc, _ = render(sp, st, None, old)
            tiles.append(label(post(col), "%s  %s" % (tag, "vuelve la luna" if st["eclipse"] == 0 else "parry en el eclipse")))
    save(np.concatenate([np.concatenate(tiles[:2], 1), np.concatenate(tiles[2:], 1)], 0), os.path.join(out, "cielo_destellos.png"))
    # 4) los planos con terreno (horizonte y borde del mapa) con sus tiempos reales
    timeline_frames(height_grid(), summary, out)
    json.dump(summary, open(os.path.join(out, "moon_sky_check.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "estados"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "out_moon"))
