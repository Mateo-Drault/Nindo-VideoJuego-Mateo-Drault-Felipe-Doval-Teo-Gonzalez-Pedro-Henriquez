"""Música de jefes por fases y tema del final de Nindō, armados a partir de temas libres (ver SOURCES y CREDITS.md).

    1. Bajar cada fuente de SOURCES a su propia carpeta y decodificarla a WAV float32 (frecuencia original) como
       <src>/<nombre>.wav:  blender -b --factory-startup --python Tools/Audio/aud_convert.py -- decode <mp3> <wav>
    2. python Tools/Audio/build_boss_music.py build --src <src> --out <out> [goro lake bamboo final ending]
    3. blender -b --factory-startup --python Tools/Audio/aud_convert.py -- encode <out>/enc 192000
    4. python Tools/Audio/build_boss_music.py trim --out <out>       (largo exacto en el último granule)
       python Tools/Audio/build_boss_music.py verify --out <out>     (largo, alineación, costuras y empalmes
       intro -> loop después del códec)
    5. python Tools/Audio/build_boss_music.py install --out <out>    (Music/<clave>.ogg + .meta, Tools/Audio/boss_music.json
       y Nindo/Assets/Nindo/Scripts/Audio/MusicPlan.cs, la tabla que lee MusicDirector)
    6. python Tools/Audio/sim_music_director.py <boss_music.json> <out>/enc/check <carpeta>   (opcional: cada pelea
       como la tocaría MusicDirector, para escucharla fuera de Unity, y la medición de cada costura)
build acepta jefes (goro lake bamboo final ending); trim, verify e install, claves o prefijos (boss_final_4) para
rehacer una toma sola sin tocar el resto. 'plan' vuelve a escribir boss_music.json y MusicPlan.cs sin tocar el audio.

Los temas no se recomponen: se cortan en tiempos de compás (grilla de tempo medida) y se reordenan por secciones
(arrange). Cada empalme salta entre compases que se parecen (croma por compás y correlación de la onda), así lo que
suena después del salto es lo que el tema tocaría ahí. Cada fase tiene su propio loop, con material distinto de las
otras, y una frase de entrada cortada del tema (los compases que en el original llevan a esa sección) que el juego
toca desde el próximo tiempo hasta el compás de la sección nueva. Una sola ganancia por jefe (BS.1770), salvo
Kokuyō, que sube por acto (ver final()).
"""
import argparse, json, math, os, shutil, sys
import numpy as np
import scipy.io.wavfile as wf
from scipy.ndimage import minimum_filter1d, uniform_filter1d
from scipy.signal import lfilter, resample_poly

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MUSIC_DIR = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Audio", "Music")
PLAN = os.path.join(HERE, "boss_music.json")

# nombre de la fuente -> (archivo, página, autor, título, licencia, url de la licencia)
SOURCES = {
    "goro_bosskoto": ("https://opengameart.org/sites/default/files/boss_koto.mp3", "https://opengameart.org/content/bosskoto",
                      "G_P", "Boss_Koto", "CC0", "https://creativecommons.org/publicdomain/zero/1.0/"),
    "lake_amenoshita": ("https://peritune.com/music/PerituneMaterial_Amenoshita.mp3", "https://peritune.com/blog/2015/07/03/amenoshita/",
                        "PeriTune", "Amenoshita", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    "bamboo_wuxia": ("https://peritune.com/music/PerituneMaterial_Wuxia.mp3", "https://peritune.com/blog/2018/06/24/wuxia/",
                     "PeriTune", "Wuxia", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    "final_tad_revenge": ("https://opengameart.org/sites/default/files/Revenge_0.mp3", "https://opengameart.org/content/revenge",
                          "TAD", "Revenge", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
    "end_sakuya4": ("https://peritune.com/music/PerituneMaterial_Sakuya4.mp3", "https://peritune.com/blog/2018/12/21/sakuya4/",
                    "PeriTune", "Sakuya4", "CC BY 4.0", "https://creativecommons.org/licenses/by/4.0/"),
}

UP, DOWN = 89, 84          # 89/84 = 1.059524 ~ un semitono (2^(1/12) = 1.059463): fase 2 de Gorō, actos 3 y 4 de Kokuyō
PAD = 2048                 # muestras de continuación que ve el codificador después del final (ver cmd_trim)
PICKUP_BARS = 2            # frase de entrada de una fase: el juego toca de 2 a 5 tiempos de ella (ver MusicDirector)
REPORT = {}
SAVED = {}
_cache = {}
SRC = OUT = None


# ============================================================================ utilidades
def src(name):
    if name not in _cache:
        sr, x = wf.read(os.path.join(SRC, name + ".wav"))
        _cache[name] = (np.ascontiguousarray(x, dtype=np.float32), sr)
    return _cache[name]


def mono(x):
    return x.mean(axis=1)


def kweight(x, sr):
    # filtros del BS.1770 (prototipos de 48 kHz llevados a sr con la transformada bilineal)
    f0, G, Q = 1681.974450955533, 3.999843853973347, 0.7071752369554196
    K = math.tan(math.pi * f0 / sr); Vh = 10 ** (G / 20); Vb = Vh ** 0.4996667741545416
    a0 = 1 + K / Q + K * K
    b = [(Vh + Vb * K / Q + K * K) / a0, 2 * (K * K - Vh) / a0, (Vh - Vb * K / Q + K * K) / a0]
    a = [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0]
    y = lfilter(b, a, x, axis=0)
    f0, Q = 38.13547087602444, 0.5003270373238773
    K = math.tan(math.pi * f0 / sr); a0 = 1 + K / Q + K * K
    return lfilter([1, -2, 1], [1, 2 * (K * K - 1) / a0, (1 - K / Q + K * K) / a0], y, axis=0)


def lufs(x, sr):
    """Sonoridad integrada BS.1770-4 (bloques de 400 ms con 75 % de solape, compuertas absoluta y relativa)."""
    y = kweight(x.astype(np.float64), sr) ** 2
    n, h = int(0.4 * sr), int(0.1 * sr)
    c = np.concatenate([np.zeros((1, y.shape[1])), np.cumsum(y, axis=0)])
    starts = np.arange(0, max(1, len(y) - n), h)
    ms = ((c[starts + n] - c[starts]) / n).sum(axis=1)
    L = -0.691 + 10 * np.log10(ms + 1e-12)
    rel = -0.691 + 10 * np.log10(ms[L > -70].mean()) - 10
    return float(-0.691 + 10 * np.log10(ms[(L > -70) & (L > rel)].mean()))


def peak_db(y):
    return float(20 * np.log10(np.abs(y).max() + 1e-12))


def band_db(y, sr, lo):
    """Energía arriba de 'lo' Hz relativa al total (dB): cuán brillante u opaco suena un clip."""
    m = mono(y).astype(np.float64)
    S = np.abs(np.fft.rfft(m)) ** 2; f = np.fft.rfftfreq(len(m), 1 / sr)
    return float(10 * np.log10(S[f >= lo].sum() / S.sum()))


def gain_for(y, sr, target, *others, ceiling=-1.0):
    """Ganancia para que y llegue a target LUFS, sin que ningún clip del mismo jefe pase de 'ceiling' dBFS de pico
    (margen para el Vorbis que Unity vuelve a codificar): un golpe de taiko a 0 dBFS no se aplasta con un limitador."""
    g = 10 ** ((target - lufs(y, sr)) / 20)
    cap = min(10 ** ((ceiling - peak_db(z)) / 20) for z in (y,) + others)
    return min(g, cap)


def high_shelf(x, sr, f0, gain_db):
    """Estante de agudos (RBJ, pendiente 1)."""
    A = 10 ** (gain_db / 40); w = 2 * math.pi * f0 / sr; cw = math.cos(w); al = math.sin(w) / 2 * math.sqrt(2)
    sA = math.sqrt(A)
    b = [A * ((A + 1) + (A - 1) * cw + 2 * sA * al), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - 2 * sA * al)]
    a = [(A + 1) - (A - 1) * cw + 2 * sA * al, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - 2 * sA * al]
    return lfilter(np.array(b) / a[0], np.array(a) / a[0], x, axis=0).astype(np.float32)


def limit(y, sr, ceiling_db=-1.3, attack=0.012, hold=0.06, smooth=0.02):
    """Limitador con anticipación sobre el tema entero (fuera de línea: no hay retardo). La ganancia necesaria en cada
    muestra se toma como el mínimo de [n - hold, n + attack] y se suaviza 'smooth' s: baja antes del golpe, queda
    abajo mientras dura y sube en 20 ms. La ventana de suavizado cabe dentro de la del mínimo, así ningún pico pasa
    del techo. Se aplica antes de cortar: cada loop sale de la misma señal limitada y sus costuras no cambian."""
    c = 10 ** (ceiling_db / 20)
    need = np.minimum(1.0, c / np.maximum(np.abs(y).max(axis=1), 1e-9))
    A, H, W = int(attack * sr), int(hold * sr), int(smooth * sr) | 1
    g = minimum_filter1d(need, size=A + H + 1, origin=(H - A) // 2, mode="nearest")
    g = uniform_filter1d(g, size=W, mode="nearest")
    return (y * g[:, None]).astype(np.float32), float(20 * np.log10(g.min()))


def grid(bpm, first_bar, pre=0.008):
    """Compás k empieza en first_bar + k * compás; 8 ms antes del tiempo fuerte medido para no comerse el ataque."""
    bar = 240.0 / bpm
    return bar, (lambda k: first_bar - pre + k * bar)


def at(t, sr):
    return int(round(t * sr))


def refine_pair(x, sr, s, e, search=0.03, win=0.6):
    """Corre e (muestras) hasta que lo que suena en e coincide con lo que suena en s (correlación normalizada)."""
    m = mono(x).astype(np.float64); w = int(win * sr); d = int(search * sr)
    a = m[s - w // 2: s + w // 2]
    seg = m[e - d - w // 2: e + d + w // 2]
    n = len(seg) + len(a)
    c = np.fft.irfft(np.fft.rfft(seg, n) * np.conj(np.fft.rfft(a, n)), n)[:len(seg) - len(a) + 1]
    e2 = np.cumsum(np.concatenate([[0], seg ** 2]))
    cn = c / np.sqrt((e2[len(a):] - e2[:-len(a)])[:len(c)] * (a ** 2).sum() + 1e-12)
    k = int(np.argmax(cn))
    return e - d + k, float(cn[k])


def first_sound(x, sr, thr_db=-50):
    a = np.abs(mono(x)); k = int(np.argmax(a > 10 ** (thr_db / 20)))
    return max(0, k - int(0.01 * sr))


def fade(n, kind):
    # suma constante (lineal en amplitud): lo que se mezcla es casi la misma señal (el mismo compás en otra vuelta) y
    # un fundido de igual potencia la subiría ~3 dB en el medio
    t = np.linspace(0, 1, n, dtype=np.float32)
    return (1 - t if kind == "out" else t)[:, None]


def end_blend(y, pre, F):
    """Los últimos F de y se funden con lo que suena justo antes del destino del salto: después del salto la onda sigue
    continua (y una intro o frase de entrada que termina donde arranca el destino empalma igual de limpio)."""
    y = y.copy(); y[-F:] = y[-F:] * fade(F, "out") + pre[-F:] * fade(F, "in")
    return y


def loop_end(x, sr, s, e, search=0.02, trust=0.9):
    """Punto de salto hacia s para un tramo que termina cerca de e: si lo que suena en e es la misma toma (el tema
    repite el pasaje), la correlación de la onda lo alinea a la muestra. Si es un empalme entre compases parecidos
    pero distintos, la correlación se engancha en cualquier periodicidad (corría el final hasta 27 ms: un tropezón
    en la costura) y manda la grilla de tempo, que los ataques siguen a ±3 ms en todo el tema."""
    e2, corr = refine_pair(x, sr, s, e, search=search)
    return (e2, corr) if corr >= trust else (e, refine_pair(x, sr, s, e, search=0.0)[1])


def arrange(x, sr, T, segs, F=0.025, multiple=1):
    """Loop hecho de tramos del tema [(ka, kb), ...] (compases [ka, kb)) tocados en ese orden y vuelta al primero.
    Cada salto (también el de la vuelta) se alinea con loop_end y se funde F s contra lo que suena antes del destino.
    'multiple': el largo total queda múltiplo de eso (89 para el re-muestreo del semitono; el último tramo se acorta
    menos de 2 ms antes del fundido, así la vuelta sigue continua). Devuelve el loop, dónde arranca cada tramo y la
    correlación de cada salto."""
    n = len(segs)
    starts = [at(T(a), sr) for a, _ in segs]
    ends, corrs = [], []
    for i, (_, b) in enumerate(segs):
        dest = starts[(i + 1) % n]
        e = at(T(b), sr)
        if e == dest:
            ends.append(e); corrs.append(1.0)
        else:
            e, c = loop_end(x, sr, dest, e)
            ends.append(e); corrs.append(round(c, 4))
    ends[-1] -= sum(e - s for s, e in zip(starts, ends)) % multiple
    Fn = int(F * sr)
    pieces = []
    for i in range(n):
        y = x[starts[i]:ends[i]]
        dest = starts[(i + 1) % n]
        if ends[i] != dest:
            y = end_blend(y, x[dest - Fn:dest], Fn)
        pieces.append(y)
    offs = [int(v) for v in np.cumsum([0] + [len(p) for p in pieces[:-1]])]
    return np.concatenate(pieces), offs, corrs


def pitch_loop(y, P=89 * 400):
    """Medio tono arriba conservando la periodicidad: relleno circular, re-muestreo 84/89 y corte del centro."""
    assert len(y) % UP == 0
    z = resample_poly(np.concatenate([y[-P:], y, y[:P]]), DOWN, UP, axis=0).astype(np.float32)
    p2 = P * DOWN // UP
    return z[p2:p2 + len(y) * DOWN // UP]


def pitch_oneshot(y, follow, P=89 * 400):
    """Ídem para una toma única que desemboca en 'follow': el final no se ensucia con el borde del filtro."""
    assert len(y) % UP == 0
    z = resample_poly(np.concatenate([y, follow[:P]]), DOWN, UP, axis=0).astype(np.float32)
    return z[:len(y) * DOWN // UP]


def onset_near(x, sr, t, radius=0.35):
    """Tiempo (s) del ataque más fuerte (flujo espectral) cerca de t: dónde entran los tambores."""
    m = mono(x).astype(np.float64); fr, hop = 1024, 128; win = np.hanning(fr)
    a = at(t - radius, sr); b = at(t + radius, sr) + fr
    seg = m[a:b]; nf = (len(seg) - fr) // hop
    S = np.log1p(100 * np.abs(np.fft.rfft(np.stack([seg[i * hop:i * hop + fr] * win for i in range(nf)]), axis=1)))
    flux = np.maximum(0, np.diff(S, axis=0)).sum(axis=1)
    return (a + (int(np.argmax(flux)) + 1) * hop + fr // 2) / sr


def seam_metrics(y, sr, seams, bar, ref_count=24):
    """Flujo espectral en cada costura contra tiempos fuertes normales del mismo archivo, nivel 50 ms antes y después,
    y el salto de muestra en la costura contra el percentil 99 de la diferencia entre muestras vecinas."""
    m = mono(y).astype(np.float64); fr, hop = 1024, 256; win = np.hanning(fr)

    def flux_peak(t):
        a = at(t - 0.06, sr); b = at(t + 0.06, sr) + fr
        seg = m[max(0, a):b]; nf = (len(seg) - fr) // hop
        if nf < 3:
            return 0.0
        S = np.log1p(100 * np.abs(np.fft.rfft(np.stack([seg[i * hop:i * hop + fr] * win for i in range(nf)]), axis=1)))
        return float(np.maximum(0, np.diff(S, axis=0)).sum(axis=1).max())
    dur = len(m) / sr
    cand = [t for t in np.arange(bar, dur - bar, bar) if all(abs(t - s) > bar / 2 for s in seams)]
    pick = np.linspace(0, len(cand) - 1, min(ref_count, len(cand))).astype(int)
    ref = np.array([flux_peak(cand[i]) for i in pick])
    out = []
    for s in seams:
        k = at(s, sr); n = int(0.05 * sr)
        d = np.abs(np.diff(y[k - n:k + n], axis=0))
        out.append({"t_s": round(s, 3), "flujo": round(flux_peak(s), 1),
                    "flujo_tiempos_fuertes_p50": round(float(np.median(ref)), 1),
                    "flujo_tiempos_fuertes_p90": round(float(np.percentile(ref, 90)), 1),
                    "nivel_antes_dB": round(20 * np.log10(np.sqrt((m[k - n:k] ** 2).mean()) + 1e-12), 1),
                    "nivel_despues_dB": round(20 * np.log10(np.sqrt((m[k:k + n] ** 2).mean()) + 1e-12), 1),
                    "salto_en_costura": round(float(np.abs(y[k] - y[k - 1]).max()), 4),
                    "p99_salto_local": round(float(np.percentile(d, 99)), 4)})
    return out


def bar_levels(y, sr, bar):
    """Nivel (dB RMS) de cada compás de un clip que arranca en un compás: la curva de intensidad de la fase."""
    B = at(bar, sr); m = mono(y).astype(np.float64)
    return [round(float(10 * np.log10((m[i:i + B] ** 2).mean() + 1e-12)), 1) for i in range(0, len(m) - B // 2, B)]


def save(key, y, sr, meta):
    y = y.astype(np.float32)
    wf.write(os.path.join(OUT, key + ".wav"), sr, y)
    meta.update({"muestras": int(len(y)), "segundos": round(len(y) / sr, 4), "sr": int(sr),
                 "LUFS": round(lufs(y, sr), 2), "pico_dBFS": round(peak_db(y), 2), "agudos_5k_dB": round(band_db(y, sr, 5000), 1)})
    assert meta["pico_dBFS"] <= -1.0, (key, meta["pico_dBFS"])
    REPORT[key] = meta
    SAVED[key] = y
    print("%-20s %8.3f s  %6.2f LUFS  pico %6.2f dBFS  >5k %5.1f dB" % (key, len(y) / sr, meta["LUFS"], meta["pico_dBFS"], meta["agudos_5k_dB"]))


def save_loop(key, y, g, sr, bar, offs, labels, corrs, extra):
    """Un loop con sus costuras medidas: la vuelta (final -> 0) y cada salto interno entre tramos."""
    meta = {"tipo": "loop", "compas_s": round(bar, 6), "tramos": labels, "correlacion_saltos": corrs,
            "nivel_por_compas_dB": bar_levels(y * g, sr, bar),
            "costuras": seam_metrics(np.concatenate([y, y]) * g, sr, [len(y) / sr] + [o / sr for o in offs[1:]], bar)}
    meta.update(extra)
    save(key, y * g, sr, meta)


def save_once(key, y, sr, bar, into, extra, hit_bars=0):
    """Intro o frase de entrada: suena una vez y desemboca en 'into' (su compás 0 cae justo al terminar). 'hit_bars':
    a cuántos compases del final cae lo que la frase anuncia (los tambores de Gorō); 0 es el final mismo."""
    meta = {"tipo": "intro (una vez)", "compas_s": round(bar, 6), "desemboca_en": into,
            "golpe_muestra": int(len(y) - at(hit_bars * bar, sr))}
    meta.update(extra)
    save(key, y, sr, meta)


def pickup(x, sr, T, k, bars=PICKUP_BARS):
    """Los compases que en el tema llevan a la sección k: la frase de entrada de la fase que arranca en k."""
    return x[at(T(k - bars), sr):at(T(k), sr)]


RAMP_IN = 0.006            # fundido de entrada de las tomas que arrancan solas (más corto que los 8 ms antes del tiempo)


def outro(x, sr, T, bar, k, g, key, name, pickup_beats=0, up=False, note=""):
    """El final escrito del tema (el último golpe y su cola) para cuando cae el jefe: arranca en un tiempo (el director
    lo pone en el próximo tiempo de lo que suena) y, si hay anacrusa, el golpe cae 'pickup_beats' tiempos después. La
    cola se corta donde baja a -60 dB del pico del tema y se funde 0.3 s. Si el golpe pasa de -1 dBFS con la ganancia
    del jefe, solo esta toma baja lo justo (el resto del jefe queda igual)."""
    s = at(T(k) - pickup_beats * bar / 4, sr)
    env = np.convolve(np.abs(mono(x)), np.ones(4096) / 4096, mode="same")
    last = len(env) - int(np.argmax(env[::-1] > env.max() * 10 ** (-60 / 20)))
    y = x[s:last].copy()
    if up:
        y = resample_poly(y, DOWN, UP, axis=0).astype(np.float32)
        bar = bar * DOWN / UP
    Fi, Fo = int(RAMP_IN * sr), int(0.3 * sr)
    y[:Fi] *= fade(Fi, "in"); y[-Fo:] *= fade(Fo, "out")
    gg = min(g, 10 ** ((-1.0 - peak_db(y)) / 20))
    save(key, y * gg, sr, {"fuente": name, "bpm": round(240.0 / bar, 3), "compas_s": round(bar, 6), "tipo": "outro (una vez)",
                           "golpe_s": round(pickup_beats * bar / 4 + 0.008, 3), "compas_fuente": k,
                           "ganancia_relativa_dB": round(20 * np.log10(gg / g), 2), "nota": note})


def stinger(x, sr, T, bar, k, g, key, name, hold=0.35, total=3.0, note=""):
    """Cierre para un tema que termina en un fundido (Wuxia): el tiempo fuerte más lleno del tema y su eco, con el
    resto apagándose en exponencial hasta -60 dB en 'total' s. El golpe cae en el tiempo en que arranca."""
    s = at(T(k), sr)
    y = x[s:s + at(total, sr)].copy()
    t = np.arange(len(y)) / sr
    y *= np.where(t < hold, 1.0, 10 ** (-3 * (t - hold) / (total - hold))).astype(np.float32)[:, None]
    Fi = int(RAMP_IN * sr); y[:Fi] *= fade(Fi, "in")
    gg = min(g, 10 ** ((-1.0 - peak_db(y)) / 20))
    save(key, y * gg, sr, {"fuente": name, "bpm": round(240.0 / bar, 3), "compas_s": round(bar, 6), "tipo": "outro (una vez)",
                           "golpe_s": 0.008, "compas_fuente": k, "ganancia_relativa_dB": round(20 * np.log10(gg / g), 2), "nota": note})


# ============================================================================ Gorō: Boss_Koto (G_P, CC0)
def goro(target=-14.0):
    """Barra falsa (fase 1): koto solo -> tambores, y un ciclo largo de 72 compases (2 min 13 s): el cuerpo, el corte
    sin tambores y su vuelta, y otra pasada del cuerpo sin corte. El cuerpo del tema se repite casi idéntico (c37 es
    c10, c39 lleva a c8), así los saltos caen donde el tema mismo se repite.
    Armadura de roca (fase 2, el clímax): todo medio tono arriba (6 % más rápido) y +1 dB, con un ciclo propio de 68
    compases (1 min 58 s) que también respira una vez. La transición es la intro medio tono arriba: koto solo y los
    tambores cuando Gorō se levanta (el juego elige cuántos tiempos de koto suenan antes: ver Phase.introHit)."""
    name = "goro_bosskoto"; x, sr = src(name); bpm = 130.0
    bar, T = grid(bpm, 1.1551)
    a = first_sound(x, sr)
    loop1, o1, c1 = arrange(x, sr, T, [(8, 48), (8, 40)], F=0.012)
    s1 = at(T(8), sr)
    g = gain_for(loop1, sr, target)
    g2 = g * 10 ** (1.0 / 20)
    drums = onset_near(x, sr, T(7) + 0.008)
    save_once("boss_goro_intro", x[a:s1] * g, sr, bar, "boss_goro", {
        "fuente": name, "bpm": bpm, "nota": "c0-c7: koto solo, percusión liviana desde c3, entran los tambores",
        "tambores_s": round(drums - a / sr, 3)})
    save_loop("boss_goro", loop1, g, sr, bar, o1, ["c8-c47", "c8-c39"], c1, {
        "fuente": name, "bpm": bpm, "secciones": "c8-c42 cuerpo (bajón c28-c30), c43-c46 corte sin tambores, c47 vuelven "
                                                 "los tambores, c8-c39 otra pasada del cuerpo y vuelta a c8"})
    outro(x, sr, T, bar, 51, g, "boss_goro_out_1", name, note="c51 en el tono de la fase 1: la barra falsa (le ganaste) o si cae en ella")
    # fase 2: arranca en c9 (la transición termina en c8); largo múltiplo de 89 para el re-muestreo exacto
    body, o2, c2 = arrange(x, sr, T, [(9, 48), (8, 37)], F=0.012, multiple=UP)
    s2 = at(T(9), sr)
    i0 = a + (s2 - a) % UP
    trans = pitch_oneshot(x[i0:s2], body)
    body2 = pitch_loop(body)
    bpm2 = bpm * UP / DOWN; bar2 = bar * DOWN / UP
    # los tambores entran en c7: dos compases antes del final de la transición
    save_once("boss_goro_2_in", trans * g2, sr, bar2, "boss_goro_2", {
        "fuente": name, "bpm": round(bpm2, 3), "nota": "la intro medio tono arriba: koto solo mientras vuelan las rocas, "
                                                         "los tambores (c7) cuando Gorō se levanta",
        "tambores_s": round((drums - i0 / sr) * DOWN / UP, 3)}, hit_bars=2)
    save_loop("boss_goro_2", body2, g2, sr, bar2, [int(o * DOWN / UP) for o in o2], ["c9-c47", "c8-c36"], c2, {
        "fuente": name, "bpm": round(bpm2, 3), "nota": "medio tono arriba, +1 dB: cuerpo, corte, vuelta de los tambores y "
                                                         "otra pasada del cuerpo hasta c36, que lleva a c9"})
    outro(x, sr, T, bar, 51, g2, "boss_goro_out", name, up=True, note="c51 medio tono arriba: el último golpe de koto y tambores, y su cola")


# ============================================================================ Mizuchi: Amenoshita (PeriTune, CC BY 4.0)
def lake(target=-14.0):
    """El tema toca dos veces un ciclo de 63 compases: apertura c0-c5, tema A c6-c21, A' c22-c36 (c36 es c20), desarrollo
    c37-c46, cumbre c47-c53, corte sin bajos c55-c60 y vuelta c61-c62. Cada fase con lo suyo:
      1 (el koi): apertura como intro y A + A' (c36 sigue en c21, que lleva otra vez a A): 32 compases, 65 s.
      2 (el dragón despierta): desarrollo, cumbre, corte y vuelta, de nuevo al desarrollo: 26 compases, 53 s.
      3 (cascada desatada): arranca en la cumbre, sin apertura ni corte (c54 salta a c7): 48 compases, 98 s.
    Las frases de entrada son los dos compases que en el tema llevan a cada sección (c35-c36, c45-c46)."""
    name = "lake_amenoshita"; x, sr = src(name); bpm = 118.0
    bar, T = grid(bpm, 1.9374)
    a = first_sound(x, sr)
    y1, o1, c1 = arrange(x, sr, T, [(6, 37), (21, 22)])
    y2, o2, c2 = arrange(x, sr, T, [(37, 63)])
    y3, o3, c3 = arrange(x, sr, T, [(47, 55), (7, 47)])
    g = gain_for(y1, sr, target, y2, y3)
    save_once("boss_lake_intro", x[a:at(T(6), sr)] * g, sr, bar, "boss_lake",
              {"fuente": name, "bpm": bpm, "nota": "anacrusa (redoble y golpe) y la apertura c0-c5"})
    save_loop("boss_lake", y1, g, sr, bar, o1, ["c6-c36", "c21"], c1, {"fuente": name, "bpm": bpm})
    save_once("boss_lake_2_in", pickup(x, sr, T, 37) * g, sr, bar, "boss_lake_2", {"fuente": name, "bpm": bpm, "nota": "c35-c36: el final de A'"})
    save_loop("boss_lake_2", y2, g, sr, bar, o2, ["c37-c62"], c2, {"fuente": name, "bpm": bpm})
    save_once("boss_lake_3_in", pickup(x, sr, T, 47) * g, sr, bar, "boss_lake_3", {"fuente": name, "bpm": bpm, "nota": "c45-c46: la subida a la cumbre"})
    save_loop("boss_lake_3", y3, g, sr, bar, o3, ["c47-c54", "c7-c46"], c3, {"fuente": name, "bpm": bpm})
    outro(x, sr, T, bar, 125, g, "boss_lake_out", name, pickup_beats=1,
          note="el último tiempo de c124 (la subida de los tambores) y el golpe final de c125 con su cola")


# ============================================================================ Maestro del bambú: Wuxia (PeriTune, CC BY 4.0)
def bamboo(target=-14.0):
    """Ciclo de 81 compases que el tema toca dos veces: tema c0-c7, A c8-c23 (lo más suave), B c24-c39 (la melodía
    arriba, lo más fuerte), C c40-c47 (taiko, cambia de color), D c48-c63, E c64-c80. Por fase:
      1: tema, A y B, y vuelta al tema (40 compases, 71 s): el maestro mide a Kaito.
      2: C, D y E, y vuelta a C (41 compases, 72 s): el taiko y otra armonía.
      3: B y D, las dos secciones más llenas (32 compases, 56 s).
    Wuxia termina en un fundido: el cierre es el primer tiempo del tema (c81, el más lleno) y su eco."""
    name = "bamboo_wuxia"; x, sr = src(name); bpm = 136.0
    bar, T = grid(bpm, 1.2864)
    a = first_sound(x, sr)
    y1, o1, c1 = arrange(x, sr, T, [(0, 40)])
    y2, o2, c2 = arrange(x, sr, T, [(40, 81)])
    y3, o3, c3 = arrange(x, sr, T, [(24, 40), (48, 64)])
    g = gain_for(y1, sr, target, y2, y3)
    save_once("boss_bamboo_intro", x[a:at(T(0), sr)] * g, sr, bar, "boss_bamboo",
              {"fuente": name, "bpm": bpm, "nota": "crescendo de entrada hasta el primer golpe"})
    save_loop("boss_bamboo", y1, g, sr, bar, o1, ["c0-c39"], c1, {"fuente": name, "bpm": bpm})
    save_once("boss_bamboo_2_in", pickup(x, sr, T, 40) * g, sr, bar, "boss_bamboo_2", {"fuente": name, "bpm": bpm, "nota": "c38-c39: el final de B"})
    save_loop("boss_bamboo_2", y2, g, sr, bar, o2, ["c40-c80"], c2, {"fuente": name, "bpm": bpm})
    save_once("boss_bamboo_3_in", pickup(x, sr, T, 24) * g, sr, bar, "boss_bamboo_3", {"fuente": name, "bpm": bpm, "nota": "c22-c23: el final de A, que lleva a B"})
    save_loop("boss_bamboo_3", y3, g, sr, bar, o3, ["c24-c39", "c48-c63"], c3, {"fuente": name, "bpm": bpm})
    stinger(x, sr, T, bar, 81, g, "boss_bamboo_out", name, note="c81: el primer tiempo del tema en la segunda vuelta, y su eco")


# ============================================================================ Kokuyō: Revenge (TAD, CC BY 4.0)
KOKUYO_SHELF = (3500.0, 6.0)        # Hz, dB: Revenge casi no tiene nada arriba de 3.4 kHz (-32 dB arriba de 5 kHz)
# dB sobre la ganancia base (acto 2 a -13.5 LUFS): el acto 1 es ralo y quedaba en -15.6, por debajo de los otros jefes;
# la ola del acto 3 y la cumbre del 4 ya suben solas (-12.5 y -12 LUFS)
KOKUYO_ACTS = {1: 1.5, 2: 0.0, 3: 0.4, 4: 0.0}


def final(target=-13.5):
    """Modo frigio sobre re, taiko y orquesta grave. El tema: latido c0-c3, tramo ralo c4-c19 (una frase de 8 compases
    dos veces), ola c20-c34 (subida a la cumbre), golpe c35, corte c36-c38 (latido otra vez), c39 sube, tramo bajo
    c40-c55 (la armonía de la ola sin los graves), segunda ola c56-c70 (casi idéntica a la primera), cierre c71-c74.
      Acto 1 (el maestro): lo ralo, c4-c19 y c40-c55, que deja oír los avisos: 32 compases, 73 s.
      Acto 2 (la sombra suelta): la ola, el golpe, el corte y medio tramo bajo, que lleva otra vez a la ola: 28, 64 s.
      Acto 3 (eclipse): la segunda ola, el golpe y el corte medio tono arriba (6 % más rápido): 20 compases, 43 s.
      Acto 4 (Último Desfile): la cumbre medio tono arriba (c61-c70 y c63-c68): 16 compases, 35 s.
    Revenge es muy opaco al lado de los otros jefes: lleva un estante de +6 dB arriba de 3.5 kHz, una ganancia
    por acto (KOKUYO_ACTS) y un limitador con anticipación que sostiene el nivel sin pasar de -1 dBFS."""
    name = "final_tad_revenge"; x0, sr = src(name); bpm = 105.0
    bar, T = grid(bpm, 1.7109)
    bar2 = bar * DOWN / UP
    xs = high_shelf(x0, sr, *KOKUYO_SHELF)
    a = first_sound(x0, sr)
    # ganancia base: el acto 2 a 'target' LUFS antes del limitador (lo que el limitador saca es solo de los golpes)
    act2, _, _ = arrange(xs, sr, T, [(20, 40), (48, 56)])
    g = 10 ** ((target - lufs(act2, sr)) / 20)
    proc, red = {}, {}
    for act, extra in KOKUYO_ACTS.items():
        proc[act], red[act] = limit(xs * (g * 10 ** (extra / 20)), sr)
    x1, x2, x3, x4 = proc[1], proc[2], proc[3], proc[4]
    lim = {"limitador_max_dB": {str(k): round(v, 2) for k, v in red.items()}, "estante": "+%.1f dB desde %d Hz" % (KOKUYO_SHELF[1], KOKUYO_SHELF[0])}
    y1, o1, c1 = arrange(x1, sr, T, [(4, 20), (40, 56)])
    y2, o2, c2 = arrange(x2, sr, T, [(20, 40), (48, 56)])
    y3, o3, c3 = arrange(x3, sr, T, [(56, 71), (35, 40)], multiple=UP)
    y4, o4, c4 = arrange(x4, sr, T, [(61, 71), (63, 69)], multiple=UP)
    save_once("boss_final_intro", x1[a:at(T(4), sr)], sr, bar, "boss_final",
              dict(lim, fuente=name, bpm=bpm, nota="c0-c3: casi silencio, el taiko como latido, y la primera subida"))
    save_loop("boss_final", y1, 1.0, sr, bar, o1, ["c4-c19", "c40-c55"], c1, dict(lim, fuente=name, bpm=bpm))
    save_once("boss_final_2_in", pickup(x2, sr, T, 20), sr, bar, "boss_final_2", dict(lim, fuente=name, bpm=bpm, nota="c18-c19: el final de lo ralo"))
    save_loop("boss_final_2", y2, 1.0, sr, bar, o2, ["c20-c39", "c48-c55"], c2, dict(lim, fuente=name, bpm=bpm))
    for key, xp, k, yy, oo, cc, lab, src_bars, note in (
            ("boss_final_3", x3, 56, y3, o3, c3, ["c56-c70", "c35-c39"], (54, 56), "c54-c55: del silencio del eclipse a la ola"),
            ("boss_final_4", x4, 61, y4, o4, c4, ["c61-c70", "c63-c68"], (59, 61), "c59-c60: la subida a la cumbre")):
        s = at(T(k), sr)
        i0 = at(T(src_bars[0]), sr); i0 += (s - i0) % UP
        save_once(key + "_in", pitch_oneshot(xp[i0:s], yy), sr, bar2, key, dict(lim, fuente=name, bpm=round(bpm * UP / DOWN, 3), nota=note + ", medio tono arriba"))
        save_loop(key, pitch_loop(yy), 1.0, sr, bar2, [int(o * DOWN / UP) for o in oo], lab, cc,
                  dict(lim, fuente=name, bpm=round(bpm * UP / DOWN, 3), nota="medio tono arriba"))
    outro(proc[3], sr, T, bar, 74, 1.0, "boss_final_out", name, up=True, note="c74 medio tono arriba: el último golpe del taiko y la cola grave")


# ============================================================================ final: Sakuya4 (PeriTune, CC BY 4.0)
def ending(target=-16.0):
    """Tema entero, una vez: koto y piano solos (sale del silencio del final), la orquesta, la cumbre y el cierre."""
    name = "end_sakuya4"; x, sr = src(name)
    a = first_sound(x, sr, -60)
    env = np.convolve(np.abs(mono(x)), np.ones(4096) / 4096, mode="same")
    last = len(env) - int(np.argmax(env[::-1] > env.max() * 10 ** (-60 / 20)))
    y = x[a:last].copy()
    Fo = int(1.0 * sr); y[-Fo:] *= fade(Fo, "out")
    g = gain_for(y, sr, target)
    save("ending", y * g, sr, {"fuente": name, "bpm": 80.0, "compas_s": 3.0, "tipo": "tema entero (una vez)",
         "nota": "0-24 s koto y piano solos; desde 24 s entra la orquesta; tema 36-63 s; cumbre 63-75 s; reprise y cierre"})


# ============================================================================ plan para AudioManager
# Por fase: loop, frase de entrada (o intro), dónde entra esa frase cuando la fase arranca desde el silencio
# (compases antes de su final; None = desde el comienzo), fundido de lo anterior (s; 0 = el de siempre: -10 dB en 30
# ms y el resto en un cuarto de compás) y el cierre si cae el jefe en esa fase (None = el del tema).
PHASES = {
    # fase 2 de Gorō desde el silencio de la barra falsa: la transición desde su c3, los tambores 6.8 s después.
    # Cambia de tono: lo anterior se corta en 40 ms para que los dos kotos no suenen juntos medio tono aparte
    "boss_goro": {1: dict(clip="boss_goro", intro="boss_goro_intro", outro="boss_goro_out_1"),
                  2: dict(clip="boss_goro_2", intro="boss_goro_2_in", entry_bars=6, cut=0.04)},
    "boss_lake": {1: dict(clip="boss_lake", intro="boss_lake_intro"), 2: dict(clip="boss_lake_2", intro="boss_lake_2_in"),
                  3: dict(clip="boss_lake_3", intro="boss_lake_3_in")},
    "boss_bamboo": {1: dict(clip="boss_bamboo", intro="boss_bamboo_intro"), 2: dict(clip="boss_bamboo_2", intro="boss_bamboo_2_in"),
                    3: dict(clip="boss_bamboo_3", intro="boss_bamboo_3_in")},
    "boss_final": {1: dict(clip="boss_final", intro="boss_final_intro"), 2: dict(clip="boss_final_2", intro="boss_final_2_in"),
                   3: dict(clip="boss_final_3", intro="boss_final_3_in", cut=0.05), 4: dict(clip="boss_final_4", intro="boss_final_4_in")},
}
# al caer el jefe: (toma final o None, fundido en s si no hay toma, vuelve la música de la zona al terminar). Kokuyō no
# devuelve la exploración: después viene la campana, la luna y el final
OUTROS = {"boss_goro": ("boss_goro_out", 0.0, True), "boss_lake": ("boss_lake_out", 0.0, True),
          "boss_bamboo": ("boss_bamboo_out", 0.0, True), "boss_final": ("boss_final_out", 0.0, False)}


def write_plan(report):
    plan = {"_nota": ("Generado por Tools/Audio/build_boss_music.py. Por fase: su loop y la frase de entrada que se toca "
                      "una vez antes (desde el próximo tiempo hasta el compás de la sección; desde el silencio, desde "
                      "'intro_muestra'); 'golpe_muestra' es donde cae lo que la frase anuncia."), "jefes": {}, "clips": {}, "finales": {}}
    for key, v in report.items():
        plan["clips"][key] = {k: v[k] for k in ("tipo", "muestras", "segundos", "sr", "bpm", "compas_s", "tambores_s", "golpe_s",
                                                "golpe_muestra", "tramos", "LUFS", "agudos_5k_dB") if k in v}
    for boss, (clip, fade_s, resume) in OUTROS.items():
        plan["finales"][boss] = {"clip": clip if clip in report else None, "fundido_s": fade_s, "vuelve_exploracion": resume}
    for boss, phases in PHASES.items():
        out = {}
        for ph, p in phases.items():
            if p["clip"] not in report:
                continue
            d = {"clip": p["clip"]}
            intro = p.get("intro")
            if intro in report:
                ri = report[intro]
                d["intro"] = intro
                d["golpe_muestra"] = ri.get("golpe_muestra", ri["muestras"])
                if p.get("entry_bars"):
                    d["intro_compases_antes_del_final"] = p["entry_bars"]
                    d["intro_muestra"] = int(round(ri["muestras"] - p["entry_bars"] * ri["compas_s"] * ri["sr"]))
            if p.get("cut"):
                d["corte_s"] = p["cut"]
            if p.get("outro") in report:
                d["cierre"] = p["outro"]
            out[str(ph)] = d
        plan["jefes"][boss] = out
    plan["jefes"]["ending"] = {"1": {"clip": "ending"}}
    plan["finales"]["ending"] = {"clip": None, "fundido_s": 2.0, "vuelve_exploracion": False}
    return plan


PLAN_CS = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Scripts", "Audio", "MusicPlan.cs")


def clip_kind(tipo):
    return "Outro" if tipo.startswith("outro") else "Once" if "una vez" in tipo else "Loop"


def write_plan_cs(plan):
    """La misma tabla para el juego (MusicDirector): sin JSON en tiempo de ejecución ni asset aparte que mantener."""
    L = ["// Generado por Tools/Audio/build_boss_music.py (install o plan) desde Tools/Audio/boss_music.json: no editar a mano.",
         "// Largos en muestras a la frecuencia del clip; compás en segundos; las entradas son muestras dentro del clip.",
         "namespace Nindo", "{", "    public static partial class MusicPlan", "    {", "        static readonly Clip[] clips =", "        {"]
    for k, c in sorted(plan["clips"].items()):
        L.append('            new Clip("%s", %d, %d, %s, ClipKind.%s),' % (k, c["muestras"], c["sr"], repr(float(c["compas_s"])), clip_kind(c["tipo"])))
    L += ["        };", "", "        static readonly Track[] tracks =", "        {"]
    q = lambda s: '"%s"' % s if s else "null"
    for boss, phases in plan["jefes"].items():
        ph = []
        for n in sorted(phases, key=int):
            p = phases[n]
            ph.append('new Phase("%s", %s, %d, %d, %sf, %s)' % (p["clip"], q(p.get("intro")), p.get("intro_muestra", 0),
                                                              p.get("golpe_muestra", 0), repr(float(p.get("corte_s", 0.0))), q(p.get("cierre"))))
        fin = plan["finales"].get(boss, {"clip": None, "fundido_s": 2.0, "vuelve_exploracion": True})
        L.append('            new Track("%s", new[] { %s }, %s, %sf, %s),' % (
            boss, ", ".join(ph), q(fin["clip"]), repr(float(fin["fundido_s"])), "true" if fin["vuelve_exploracion"] else "false"))
    L += ["        };", "    }", "}", ""]
    with open(PLAN_CS, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L))
    sys.path.insert(0, os.path.join(REPO, "Tools", "Unity"))
    from unity_yaml import write_meta, MONO_META
    write_meta(PLAN_CS, MONO_META)
    print("plan C#", PLAN_CS)


# ============================================================================ comandos
def cmd_build(names):
    path = os.path.join(OUT, "build_report.json")
    old = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    for f in names:
        # lo que ese jefe ya no genera (claves viejas) no queda en el informe
        prefix = {"goro": "boss_goro", "lake": "boss_lake", "bamboo": "boss_bamboo", "final": "boss_final", "ending": "ending"}[f]
        old = {k: v for k, v in old.items() if not k.startswith(prefix)}
        globals()[f]()
    old.update(REPORT)
    json.dump(old, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # Para el Vorbis: cada clip seguido de lo que de verdad suena después (un loop, su propio comienzo; una intro, el
    # comienzo de su loop). El codificador rellena con ceros después del final y el ruido del corte cae en las últimas
    # ~250 muestras (justo antes de la costura: la relación señal/ruido bajaba a 6 dB en el loop de Gorō). cmd_trim
    # vuelve a declarar el largo exacto en el último granule, que es lo que respeta un decodificador de Vorbis.
    enc = os.path.join(OUT, "enc"); os.makedirs(enc, exist_ok=True)
    for key, y in SAVED.items():
        meta = REPORT[key]
        nxt = key if meta["tipo"] == "loop" else meta.get("desemboca_en")
        cont = SAVED[nxt][:PAD] if nxt else np.zeros((0, 2), np.float32)
        wf.write(os.path.join(enc, key + ".wav"), meta["sr"], np.concatenate([y, cont]).astype(np.float32))


def ogg_crc(page):
    """CRC de página Ogg (polinomio 0x04C11DB7, sin reflejar, con el campo del CRC en cero)."""
    if not hasattr(ogg_crc, "table"):
        tab = []
        for i in range(256):
            r = i << 24
            for _ in range(8):
                r = ((r << 1) ^ 0x04C11DB7) if r & 0x80000000 else (r << 1)
            tab.append(r & 0xFFFFFFFF)
        ogg_crc.table = tab
    crc = 0
    for b in page:
        crc = ((crc << 8) ^ ogg_crc.table[((crc >> 24) ^ b) & 0xFF]) & 0xFFFFFFFF
    return crc


def ogg_pages(b):
    """(inicio, largo, granule) de cada página."""
    out, pos = [], 0
    while pos < len(b):
        assert b[pos:pos + 4] == b"OggS", pos
        nseg = b[pos + 26]
        size = 27 + nseg + sum(b[pos + 27:pos + 27 + nseg])
        out.append((pos, size, int.from_bytes(b[pos + 6:pos + 14], "little", signed=True)))
        pos += size
    return out


def wanted(rep, names):
    """Claves del informe que tocan: todas, o las que empiezan con alguno de los nombres (p. ej. 'boss_goro_out')."""
    return [k for k in rep if not names or any(k.startswith(n) for n in names)]


def cmd_trim(names=()):
    """enc/<clave>.ogg -> <clave>.ogg con el largo exacto en el granule de la última página. El recorte del final solo
    vale dentro de la última página: si la continuación arranca en una página anterior (el muxer corta páginas de ~1 s
    donde le toca), esas páginas se funden con la última en una sola (cabe: hasta 255 segmentos)."""
    rep = json.load(open(os.path.join(OUT, "build_report.json"), encoding="utf-8"))
    for key in wanted(rep, names):
        v = rep[key]
        b = open(os.path.join(OUT, "enc", key + ".ogg"), "rb").read()
        pages = ogg_pages(b)
        n = v["muestras"]
        k = len(pages) - 1
        while pages[k - 1][2] > n:
            k -= 1
        first = pages[k][0]
        segs, data = b"", b""
        for start, size, gran in pages[k:]:
            ns = b[start + 26]
            segs += b[start + 27:start + 27 + ns]
            data += b[start + 27 + ns:start + size]
        assert len(segs) <= 255 and pages[k - 1][2] <= n <= pages[-1][2], (key, len(segs), n)
        flags = (b[first + 5] & 0x01) | 0x04          # "sigue un paquete" de la primera fundida + fin de stream
        head = bytearray(b"OggS" + bytes([0, flags]) + n.to_bytes(8, "little", signed=True) + b[first + 14:first + 22]
                         + bytes(4) + bytes([len(segs)]) + segs)
        page = bytes(head) + data
        head[22:26] = ogg_crc(page).to_bytes(4, "little")
        open(os.path.join(OUT, key + ".ogg"), "wb").write(b[:first] + bytes(head) + data)
        print("%-20s última página (de %d del muxer): granule %d -> %d, la anterior termina en %d" % (
            key, len(pages) - k, pages[-1][2], n, pages[k - 1][2]))


def load_wav(path):
    sr, y = wf.read(path)
    return np.asarray(y, dtype=np.float32), sr


def joint_step(a, b, n=2048):
    """Salto de muestra donde 'a' desemboca en 'b' (por canal) contra el percentil 99 de los saltos de alrededor: un tic
    es un salto mucho mayor que los de la música que lo rodea."""
    z = np.concatenate([a[-n:], b[:n]])
    d = np.abs(np.diff(z, axis=0))
    return float(np.abs(b[0] - a[-1]).max()), float(np.percentile(d, 99))


def cmd_verify(names=()):
    """Después del Vorbis: el último granule de cada .ogg es el largo exacto (lo que respeta Unity al importar), la
    decodificación arranca alineada con el original (sin retardo), la costura del loop sigue limpia y cada intro o
    frase de entrada empalma con su loop sin salto (el loop la sigue sin fundido: un salto ahí es un tic)."""
    rep = json.load(open(os.path.join(OUT, "build_report.json"), encoding="utf-8"))
    ok = True
    dec = {}
    for key in wanted(rep, names):
        v = rep[key]
        ogg = os.path.join(OUT, key + ".ogg")
        b = open(ogg, "rb").read()
        i = b.rfind(b"OggS")
        gran = int.from_bytes(b[i + 6:i + 14], "little", signed=True)
        x, sr = load_wav(os.path.join(OUT, key + ".wav"))
        y = np.load(os.path.join(OUT, "enc", "check", key + ".npy"))
        dec[key] = y[:v["muestras"]]
        n = min(len(x), sr * 2)
        c = np.correlate(mono(y[:n + 400]), mono(x[200:n - 200]), mode="valid")
        lag = int(np.argmax(c)) - 200
        line = "%-20s granule %9d  muestras %9d  %s  retardo %+d" % (key, gran, v["muestras"], "OK" if gran == v["muestras"] else "DISTINTO", lag)
        if gran != v["muestras"] or lag != 0:
            ok = False
        if v["tipo"] == "loop":
            yy = y[:v["muestras"]]
            m = seam_metrics(np.concatenate([yy, yy]), sr, [len(yy) / sr], v["compas_s"])[0]
            line += "  costura: flujo %.0f (p50 %.0f, p90 %.0f)  %.1f/%.1f dB" % (
                m["flujo"], m["flujo_tiempos_fuertes_p50"], m["flujo_tiempos_fuertes_p90"], m["nivel_antes_dB"], m["nivel_despues_dB"])
        print(line)
    for key in dec:
        into = key if rep[key]["tipo"] == "loop" else rep[key].get("desemboca_en")
        if into in dec:
            step, p99 = joint_step(dec[key], dec[into])
            bad = step > 2.5 * p99 + 0.01
            ok &= not bad
            print("  empalme %-18s -> %-14s salto %.4f  (p99 local %.4f)  %s" % (key, into, step, p99, "TIC" if bad else "ok"))
    print("TODO OK" if ok else "HAY PROBLEMAS")


# Comprimido en memoria (Vorbis), precargado en segundo plano: MusicDirector encadena intro, vueltas y cambios de fase
# con PlayScheduled, que es exacto a la muestra con el clip ya cargado; con Streaming el arranque depende de que el
# stream llegue a abrirse a tiempo. Son ~27 MB comprimidos en total.
MUSIC_META = """AudioImporter:
  externalObjects: {}
  serializedVersion: 7
  defaultSettings:
    serializedVersion: 2
    loadType: 1
    sampleRateSetting: 0
    sampleRateOverride: 44100
    compressionFormat: 1
    quality: 0.7
    conversionMode: 0
    preloadAudioData: 1
  platformSettingOverrides: {}
  forceToMono: 0
  normalize: 0
  loadInBackground: 1
  ambisonic: 0
  3D: 1
  userData:
  assetBundleName:
  assetBundleVariant:
"""


def cmd_install(names=()):
    sys.path.insert(0, os.path.join(REPO, "Tools", "Unity"))
    from unity_yaml import write_meta
    rep = json.load(open(os.path.join(OUT, "build_report.json"), encoding="utf-8"))
    for key in wanted(rep, names):
        dst = os.path.join(MUSIC_DIR, key + ".ogg")
        shutil.copyfile(os.path.join(OUT, key + ".ogg"), dst)
        g = write_meta(dst, MUSIC_META, force=True)
        print("instalado", key, g, os.path.getsize(dst))
    cmd_plan()


def cmd_plan():
    """boss_music.json y MusicPlan.cs desde el informe del build (sin tocar el audio)."""
    rep = json.load(open(os.path.join(OUT, "build_report.json"), encoding="utf-8"))
    plan = write_plan(rep)
    json.dump(plan, open(PLAN, "w", encoding="utf-8", newline="\n"), ensure_ascii=False, indent=1)
    print("plan", PLAN)
    write_plan_cs(plan)


def credits_md():
    """Filas de CREDITS.md para la música de jefes y el final (las usa también build_audio.write_credits)."""
    keys = {"goro_bosskoto": "`boss_goro*`", "lake_amenoshita": "`boss_lake*`", "bamboo_wuxia": "`boss_bamboo*`",
            "final_tad_revenge": "`boss_final*`", "end_sakuya4": "`ending`"}
    change = {"goro_bosskoto": "cortado en compases y reordenado: intro, un ciclo de 72 compases con el corte una vez; "
                               "fase 2 medio tono arriba (re-muestreo 89/84) y +1 dB con su propio ciclo de 68; el golpe "
                               "final (c51) en los dos tonos como cierre",
              "lake_amenoshita": "cortado en compases y reordenado por secciones: apertura como intro, un loop por fase "
                                 "(A y A'; desarrollo, cumbre y corte; cumbre y A sin corte), dos compases de entrada "
                                 "por fase y el golpe final como cierre; sonoridad normalizada",
              "bamboo_wuxia": "cortado en compases y reordenado por secciones: crescendo como intro, un loop por fase "
                              "(tema, A y B; C, D y E; B y D), dos compases de entrada por fase y el primer tiempo del "
                              "tema con su eco como cierre; sonoridad normalizada",
              "final_tad_revenge": "cortado en compases y reordenado: intro, un loop por acto (los actos 3 y 4 medio tono "
                                   "arriba), dos compases de entrada por acto y el golpe final (c74) como cierre; estante "
                                   "de +6 dB arriba de 3.5 kHz, ganancia por acto (acto 1 +1.5 dB, acto 3 +0.4 dB), limitador a -1.3 dBFS",
              "end_sakuya4": "silencios recortados, fundido de 1 s al final, sonoridad normalizada"}
    rows = ["## Música de jefes y del final (por fases, `Tools/Audio/build_boss_music.py`)", "",
            "| Claves | Tema | Autor | Licencia | Cambios |", "|---|---|---|---|---|"]
    for k, (url, page, author, title, lic, lic_url) in SOURCES.items():
        rows.append(f"| {keys[k]} | [{title}]({page}) | {author} | [{lic}]({lic_url}) | {change[k]} |")
    rows += ["",
             "El crédito de los temas CC BY 4.0 sale en el cartel del final del juego (UIManager.Panels, BuildEnd): la",
             "licencia pide nombrar autor, licencia y que se modificaron en todo lo que se distribuye, y este archivo no",
             "viaja en la build.", "",
             "Licencias, como estaban al 12 de octubre de 2026 (páginas leídas ese día; la copia de",
             "https://peritune.com/about/ no va al repositorio porque está en japonés: archivarla en web.archive.org",
             "si hace falta una prueba fechada):", "",
             "* Wuxia: su página dice que el tema está bajo Creative Commons Attribution 4.0 International.",
             "* Amenoshita (2015) y Sakuya4 (2018): sus páginas no dicen licencia. Vale la cláusula de",
             "  https://peritune.com/about/ (sección de licencias, cambiada en marzo de 2026): a los temas publicados",
             "  hasta febrero de 2026 se les sigue aplicando CC BY 4.0; a los de marzo de 2026 en adelante, los términos",
             "  propios del sitio. Una licencia CC BY 4.0 ya otorgada no se puede revocar.",
             "* En la misma página, los términos de PeriTune (sin fecha) prohíben vender o redistribuir los archivos de",
             "  los temas solos, piden cifrar la música que va dentro de una obra paga para que no se pueda extraer y",
             "  la permiten sin cifrar en juegos gratuitos donde cifrarla no sea posible. El crédito \"PeriTune\" es",
             "  optativo para ellos. Ojo: los .ogg cortados están en un repositorio público; eso se apoya solo en la",
             "  CC BY 4.0. Para una versión paga: cifrar la música (por ejemplo AssetBundles cifrados) o escribirle a",
             "  PeriTune.",
             "* Revenge: la página de OpenGameArt pone \"CC-BY 4.0\" en el campo de licencia, sin otras instrucciones.",
             "", "### Agregar un tema por fases", "",
             "1. La fuente en `SOURCES` de `build_boss_music.py` (url, página, autor, título, licencia) y su fila en la tabla",
             "   con lo que se le cambió. Sin licencia que permita cortarla y redistribuirla, no entra. Si es CC BY, su",
             "   línea en el cartel del final.",
             "2. Medir la grilla: BPM y el primer tiempo fuerte (`grid(bpm, primer_compas)`); los ataques del tema tienen que",
             "   caer a ±3 ms de ella. Todo corte se hace en compases de esa grilla, 8 ms antes del tiempo fuerte. Las",
             "   secciones salen de la similitud entre compases (croma por compás) y del nivel de cada uno.",
             "3. Una función por tema que guarde la intro (`save_once`, termina donde arranca el loop de la fase 1), un loop",
             "   por fase (`arrange`: tramos de compases en orden; cada salto va a un compás parecido al que seguiría en el",
             "   tema), la frase de entrada de cada fase (`pickup`: los compases que llevan a esa sección en el tema) y el",
             "   cierre (`outro`, o `stinger` si el tema termina en un fundido). Una sola ganancia por jefe, picos a -1",
             "   dBFS como mucho.",
             "4. La fila en `PHASES` (loop, frase de entrada, desde dónde entra después de un silencio, corte de lo anterior",
             "   si cambia de tono, cierre propio) y en `OUTROS` (cierre, fundido si no hay, si vuelve la zona).",
             "5. Los pasos del encabezado del script: build, Vorbis con Blender, trim, verify (largo exacto, sin retardo,",
             "   costura y empalmes limpios), install (los .ogg, `Tools/Audio/boss_music.json` y",
             "   `Scripts/Audio/MusicPlan.cs`) y las claves nuevas en la lista `music` de `NindoContent` (las registra",
             "   `Tools/Unity/generate_assets.py`, que lee la carpeta `Music`). Para oírlo fuera de Unity:",
             "   `Tools/Audio/sim_music_director.py`.",
             "6. En el juego: `musicKey` del jefe y `Game.Audio.SetBossMusicPhase(n)` en cada fase. Un cambio entra en el",
             "   próximo tiempo con la frase de entrada y la sección nueva cae en un compás; antes de un silencio de la",
             "   pelea, `SilenceBossMusic` y la fase siguiente entra apenas se la pide. Al caer el jefe, `Boss.Die` llama",
             "   a `EndBossMusic` (el cierre en el próximo tiempo).", ""]
    return rows


def main():
    global SRC, OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "trim", "verify", "install", "plan", "credits"])
    ap.add_argument("names", nargs="*")
    ap.add_argument("--src")
    ap.add_argument("--out")
    a = ap.parse_args()
    SRC, OUT = a.src, a.out
    if a.cmd == "credits":
        # solo la sección de jefes de CREDITS.md (sin rehacer los efectos de build_audio.py)
        p = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Audio", "CREDITS.md")
        s = open(p, encoding="utf-8").read()
        i, j = s.index("## Música de jefes"), s.index("## Efectos")
        open(p, "w", encoding="utf-8", newline="\n").write(s[:i] + "\n".join(credits_md()) + "\n" + s[j:])
        print("créditos", p)
        return
    os.makedirs(OUT, exist_ok=True)
    if a.cmd == "build":
        cmd_build(a.names or ["goro", "lake", "bamboo", "final", "ending"])
    elif a.cmd == "trim":
        cmd_trim(a.names)
    elif a.cmd == "verify":
        cmd_verify(a.names)
    elif a.cmd == "install":
        cmd_install(a.names)
    else:
        cmd_plan()


if __name__ == "__main__":
    main()
