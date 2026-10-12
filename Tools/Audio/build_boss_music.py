"""Música de jefes por fases y tema del final de Nindō, armados a partir de temas libres (ver SOURCES y CREDITS.md).

    1. Bajar cada fuente de SOURCES a su propia carpeta y decodificarla a WAV float32 (frecuencia original) como
       <src>/<nombre>.wav:  blender -b --factory-startup --python Tools/Audio/aud_convert.py -- decode <mp3> <wav>
    2. python Tools/Audio/build_boss_music.py build --src <src> --out <out> [goro lake bamboo final ending]
    3. blender -b --factory-startup --python Tools/Audio/aud_convert.py -- encode <out>/enc 192000
    4. python Tools/Audio/build_boss_music.py trim --out <out>       (largo exacto en el último granule)
       python Tools/Audio/build_boss_music.py verify --out <out>     (largo, alineación y costuras después del códec)
    5. python Tools/Audio/build_boss_music.py install --out <out>    (Music/<clave>.ogg + .meta, Tools/Audio/boss_music.json
       y Nindo/Assets/Nindo/Scripts/Audio/MusicPlan.cs, la tabla que lee MusicDirector)
    6. python Tools/Audio/build_boss_music.py preview --out <out>    (opcional: cómo suena cada pelea con sus fases)
build acepta jefes (goro lake bamboo final ending); trim, verify e install, claves o prefijos (boss_final_4) para
rehacer una toma sola sin tocar el resto. 'plan' vuelve a escribir boss_music.json y MusicPlan.cs sin tocar el audio.

Los temas no se recomponen: se cortan en tiempos de compás (grilla de tempo medida), los loops se cierran donde lo que
suena después del salto es lo mismo que sonaría en el tema (auto-similitud por compás y correlación de la onda), y cada
fase es otro tramo del tema o el mismo tema medio tono arriba (Gorō). Una sola ganancia por jefe (BS.1770): la fase
tranquila queda más suave que la fuerte, como la escribió el compositor.
"""
import argparse, json, math, os, shutil, sys
import numpy as np
import scipy.io.wavfile as wf
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

UP, DOWN = 89, 84          # 89/84 = 1.059524 ~ un semitono (2^(1/12) = 1.059463): fase 2 de Gorō
PAD = 2048                 # muestras de continuación que ve el codificador después del final (ver cmd_trim)
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


def gain_for(y, sr, target, *others, ceiling=-1.0):
    """Ganancia para que y llegue a target LUFS, sin que ningún clip del mismo jefe pase de 'ceiling' dBFS de pico
    (margen para el Vorbis que Unity vuelve a codificar): un golpe de taiko a 0 dBFS no se aplasta con un limitador."""
    g = 10 ** ((target - lufs(y, sr)) / 20)
    cap = min(10 ** ((ceiling - peak_db(z)) / 20) for z in (y,) + others)
    return min(g, cap)


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
    """Los últimos F de y se funden con lo que suena justo antes del punto de vuelta: al volver al comienzo la onda
    sigue continua, y la primera vez (intro -> loop) también, porque y arranca donde terminaba la intro."""
    y = y.copy(); y[-F:] = y[-F:] * fade(F, "out") + pre[-F:] * fade(F, "in")
    return y


def head_blend(y, cont, T):
    """Ciclo entero que empieza en su compás 0: los primeros T vienen del ciclo 2 (traen la cola de reverb del final del
    ciclo, que es lo que de verdad sigue al último compás) y se funden con el ciclo 1. La vuelta queda como en el tema."""
    y = y.copy(); y[:T] = cont[:T] * fade(T, "out") + y[:T] * fade(T, "in")
    return y


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


def save(key, y, sr, meta):
    y = y.astype(np.float32)
    wf.write(os.path.join(OUT, key + ".wav"), sr, y)
    meta.update({"muestras": int(len(y)), "segundos": round(len(y) / sr, 4), "sr": int(sr),
                 "LUFS": round(lufs(y, sr), 2), "pico_dBFS": round(peak_db(y), 2)})
    assert meta["pico_dBFS"] <= -1.0, (key, meta["pico_dBFS"])
    REPORT[key] = meta
    SAVED[key] = y
    print("%-18s %8.3f s  %6.2f LUFS  pico %6.2f dBFS" % (key, len(y) / sr, meta["LUFS"], meta["pico_dBFS"]))


def loop_meta(y, g, sr, bar, extra):
    meta = {"tipo": "loop", "compas_s": round(bar, 6), "costuras": seam_metrics(np.concatenate([y, y]) * g, sr, [len(y) / sr], bar)}
    meta.update(extra)
    return meta


def cycle_len(x, sr, T, bars):
    # medido en el compás 10: los primeros del ciclo 1 no traen la cola de reverb del final y correlacionan peor
    s = at(T(10), sr)
    e, corr = refine_pair(x, sr, s, s + at(bars * (T(1) - T(0)), sr), search=0.05)
    return e - s, corr


def full_cycle(x, sr, T, bar, bars):
    """Ciclo entero desde el compás 0 (el tema lo toca dos veces): loop exacto, la vuelta es la del propio tema."""
    L, corr = cycle_len(x, sr, T, bars)
    s0 = at(T(0), sr); B2 = at(2 * bar, sr)
    # dos compases: cubre la cola de reverb (~3 s) que el ciclo 1 no tiene en su comienzo
    y = head_blend(x[s0:s0 + L], x[s0 + L:s0 + L + B2], B2)
    return y, s0, corr


def loop_end(x, sr, s, e, search=0.02, trust=0.9):
    """Punto de vuelta para un loop que arranca en s: si lo que suena en e es la misma toma (el tema repite el pasaje),
    la correlación de la onda lo alinea a la muestra. Si es un empalme entre compases parecidos pero distintos, la
    correlación se engancha en cualquier periodicidad (corría el final hasta 27 ms: un tropezón en la costura) y manda
    la grilla de tempo, que los ataques siguen a ±3 ms en todo el tema."""
    e2, corr = refine_pair(x, sr, s, e, search=search)
    return (e2, corr) if corr >= trust else (e, refine_pair(x, sr, s, e, search=0.0)[1])


def section_loop(x, sr, T, ka, kb, F=0.025, search=0.02):
    """Loop [ka, kb): al terminar el compás kb-1 vuelve a ka, donde suena lo mismo que seguiría en el tema."""
    s = at(T(ka), sr)
    e, corr = loop_end(x, sr, s, at(T(kb), sr), search=search)
    Fn = int(F * sr)
    return end_blend(x[s:e], x[s - Fn:s], Fn), s, corr


def entries(T, sr, s0, bars, names):
    """Muestra (dentro del clip que arranca en s0) donde empieza cada compás de entrada de fase."""
    return {names[k]: {"compas": k, "muestra": at(T(k), sr) - s0, "s": round(at(T(k), sr) / sr - s0 / sr, 4)} for k in bars}


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


# ============================================================================ Gorō: Boss_Koto (G_P, CC0)
def goro(target=-14.0):
    """Fase 1 (barra falsa): koto solo -> tambores, y un loop largo con el respiro del tema (cuerpo, corte y vuelta de
    los tambores). Fase 2 (armadura de roca): la misma intro medio tono arriba como transición (los tambores caen
    cuando se levanta) y el cuerpo sin respiro, medio tono arriba (6 % más rápido) y +1 dB: el clímax."""
    name = "goro_bosskoto"; x, sr = src(name); bpm = 130.0
    bar, T = grid(bpm, 1.1551)
    a = first_sound(x, sr)
    loop1, s1, c1 = section_loop(x, sr, T, 8, 48, F=0.012)
    g = gain_for(loop1, sr, target)
    g2 = g * 10 ** (1.0 / 20)
    drums = onset_near(x, sr, T(7) + 0.008)
    save("boss_goro_intro", x[a:s1] * g, sr, {
        "fuente": name, "bpm": bpm, "compas_s": round(bar, 6), "tipo": "intro (una vez)", "desemboca_en": "boss_goro",
        "nota": "c0-c7: koto solo, percusión liviana desde c3, entran los tambores", "tambores_s": round(drums - a / sr, 3)})
    save("boss_goro", loop1 * g, sr, loop_meta(loop1, g, sr, bar, {
        "fuente": name, "bpm": bpm, "compases": "c8-c47 (40)", "correlacion_vuelta": round(c1, 4),
        "secciones": "c8-c42 cuerpo (bajón c28-c30), c43-c46 corte sin tambores, c47 vuelven los tambores y salta a c8"}))
    # fase 2: el cuerpo [c9, c37) sin el corte; largo múltiplo de 89 para el re-muestreo exacto (corre el final < 2 ms)
    s2 = at(T(9), sr)
    e2, c2 = loop_end(x, sr, s2, at(T(37), sr), search=0.03)
    e2 -= (e2 - s2) % UP
    F = int(0.012 * sr)
    body = end_blend(x[s2:e2], x[s2 - F:s2], F)
    i0 = a + (s2 - a) % UP
    trans = pitch_oneshot(x[i0:s2], body)
    body2 = pitch_loop(body)
    bpm2 = bpm * UP / DOWN; bar2 = bar * DOWN / UP
    save("boss_goro_2_in", trans * g2, sr, {
        "fuente": name, "bpm": round(bpm2, 3), "compas_s": round(bar2, 6), "tipo": "transición (una vez)", "desemboca_en": "boss_goro_2",
        "nota": "la intro medio tono arriba: koto solo mientras vuelan las rocas, los tambores cuando Gorō se levanta",
        "tambores_s": round((drums - i0 / sr) * DOWN / UP, 3)})
    save("boss_goro_2", body2 * g2, sr, loop_meta(body2, g2, sr, bar2, {
        "fuente": name, "bpm": round(bpm2, 3), "compases": "c9-c36 (28) medio tono arriba, +1 dB", "correlacion_vuelta": round(c2, 4)}))
    # medio tono arriba, como la fase 2: Gorō solo cae en la 2 (la barra falsa termina en ella) y un cierre medio tono
    # abajo de lo que venía sonando suena a que se desinfla
    outro(x, sr, T, bar, 51, g2, "boss_goro_out", name, up=True, note="c51 medio tono arriba: el último golpe de koto y tambores, y su cola")


# ============================================================================ Mizuchi: Amenoshita (PeriTune, CC BY 4.0)
def lake(target=-14.0):
    """Ciclo de 63 compases (el tema lo toca dos veces): apertura, tema A dos veces, desarrollo y un corte sin bajos.
    Fase 1: el ciclo entero. Fase 2: el mismo ciclo desde el desarrollo (c36). Fase 3: un loop sin apertura ni corte
    (c7-c54: el koi ya no da respiro) que arranca en la cumbre del desarrollo (c47)."""
    name = "lake_amenoshita"; x, sr = src(name); bpm = 118.0
    bar, T = grid(bpm, 1.9374)
    y, s0, corr = full_cycle(x, sr, T, bar, 63)
    y3, c3 = rotated_section(x, sr, T, 7, 55, 47)
    g = gain_for(y, sr, target, y3)
    a = first_sound(x, sr)
    save("boss_lake_intro", x[a:s0] * g, sr, {"fuente": name, "bpm": bpm, "compas_s": round(bar, 6), "tipo": "intro (una vez)",
         "desemboca_en": "boss_lake", "nota": "anacrusa (redoble y golpe) que cae en el primer compás"})
    save("boss_lake", y * g, sr, loop_meta(y, g, sr, bar, {
        "fuente": name, "bpm": bpm, "ciclo_compases": 63, "correlacion_ciclo": round(corr, 4),
        "secciones": "c0-c5 apertura, c6-c21 tema A, c22-c35 tema A', c36-c54 desarrollo (cumbre c44-c53), c55-c60 corte sin bajos, c61-c62 vuelta",
        "entradas": entries(T, sr, s0, (0, 6, 22, 36, 47, 55), {0: "apertura", 6: "tema_a", 22: "tema_a2", 36: "desarrollo", 47: "cumbre", 55: "corte"})}))
    j = at(T(55), sr) - at(T(47), sr)
    save("boss_lake_3", y3 * g, sr, loop_meta(y3, g, sr, bar, {
        "fuente": name, "bpm": bpm, "compases": "c47-c54 y c7-c46 (48)", "correlacion_empalme": round(c3, 4),
        "nota": "fase 3: arranca en la cumbre (c47); al terminar c54 salta a c7 (el tema A) sin apertura ni corte",
        "empalme": seam_metrics(np.concatenate([y3, y3]) * g, sr, [j / sr], bar)}))
    outro(x, sr, T, bar, 125, g, "boss_lake_out", name, pickup_beats=1,
          note="el último tiempo de c124 (la subida de los tambores) y el golpe final de c125 con su cola")


def rotated_section(x, sr, T, ka, kb, kstart, F=0.025):
    """Loop [ka, kb) que arranca en kstart: x[kstart:kb] + x[ka:kstart]. El empalme kb-1 -> ka queda adentro del clip
    (fundido corto contra lo que suena antes de ka, como en section_loop) y la vuelta del clip (kstart-1 -> kstart) es
    la del propio tema, continua."""
    sa, ss = at(T(ka), sr), at(T(kstart), sr)
    e, corr = loop_end(x, sr, sa, at(T(kb), sr))
    Fn = int(F * sr)
    head = end_blend(x[ss:e], x[sa - Fn:sa], Fn)
    return np.concatenate([head, x[sa:ss]]), corr


# ============================================================================ Maestro del bambú: Wuxia (PeriTune, CC BY 4.0)
def bamboo(target=-14.0):
    """Ciclo de 81 compases (el tema lo toca dos veces): erhu, dizi, guzheng, coro y orquesta. Fase 2 entra en la
    sección C (c40: taiko y cambio de color armónico); si hay una tercera, en la B (c24: la melodía arriba, lo más fuerte)."""
    name = "bamboo_wuxia"; x, sr = src(name); bpm = 136.0
    bar, T = grid(bpm, 1.2864)
    y, s0, corr = full_cycle(x, sr, T, bar, 81)
    g = gain_for(y, sr, target)
    a = first_sound(x, sr)
    save("boss_bamboo_intro", x[a:s0] * g, sr, {"fuente": name, "bpm": bpm, "compas_s": round(bar, 6), "tipo": "intro (una vez)",
         "desemboca_en": "boss_bamboo", "nota": "crescendo de entrada hasta el primer golpe"})
    save("boss_bamboo", y * g, sr, loop_meta(y, g, sr, bar, {
        "fuente": name, "bpm": bpm, "ciclo_compases": 81, "correlacion_ciclo": round(corr, 4),
        "secciones": "c0-c7 tema, c8-c23 A, c24-c39 B (melodía arriba), c40-c47 C (taiko, modula), c48-c63 D, c64-c80 E",
        "entradas": entries(T, sr, s0, (0, 8, 24, 40, 48, 64), {0: "tema", 8: "a", 24: "b", 40: "c_taiko", 48: "d", 64: "e"})}))


# ============================================================================ Kokuyō: Revenge (TAD, CC BY 4.0)
def final(target=-14.0):
    """Modo frigio sobre re (re, mi bemol, fa, sol, la, do), taiko y orquesta grave, en dos olas de 36 compases.
    Acto 1 (el maestro): el tramo ralo que deja oír los avisos. Acto 2 (la sombra suelta): la ola entera, cumbre,
    golpe, corte y vuelta. Acto 3 (eclipse, después del silencio): la segunda subida entera hasta la cumbre, en loop.
    Las costuras son empalmes entre compases parecidos (no repeticiones exactas): se eligieron por auto-similitud,
    poco salto de nivel y un ataque en la costura como el de cualquier tiempo fuerte del tema."""
    name = "final_tad_revenge"; x, sr = src(name); bpm = 105.0
    bar, T = grid(bpm, 1.7109)
    a = first_sound(x, sr)
    act1, s1, c1 = section_loop(x, sr, T, 5, 21)
    act2, s2, c2 = section_loop(x, sr, T, 21, 57)
    act3, s3, c3 = section_loop(x, sr, T, 55, 71)
    g = gain_for(act2, sr, target, act1, act3, x[a:s1])
    save("boss_final_intro", x[a:s1] * g, sr, {"fuente": name, "bpm": bpm, "compas_s": round(bar, 6), "tipo": "intro (una vez)",
         "desemboca_en": "boss_final", "nota": "c0-c4: casi silencio, el taiko como latido, y la primera subida"})
    save("boss_final", act1 * g, sr, loop_meta(act1, g, sr, bar, {
        "fuente": name, "bpm": bpm, "compases": "c5-c20 (16)", "correlacion_vuelta": round(c1, 4),
        "nota": "acto 1: al terminar c20 vuelve a c5; en el tema c20 sigue en c21, que es donde arranca el acto 2"}))
    save("boss_final_2", act2 * g, sr, loop_meta(act2, g, sr, bar, {
        "fuente": name, "bpm": bpm, "compases": "c21-c56 (36)", "correlacion_vuelta": round(c2, 4),
        "secciones": "c21-c34 primera cumbre, c35 golpe, c36-c38 corte, c39-c54 vuelta con menos graves, c55-c56 sube",
        "entradas": entries(T, sr, s2, (21, 27, 35, 39, 55), {21: "comienzo", 27: "cumbre", 35: "golpe", 39: "vuelta", 55: "subida"})}))
    save("boss_final_3", act3 * g, sr, loop_meta(act3, g, sr, bar, {
        "fuente": name, "bpm": bpm, "compases": "c55-c70 (16)", "correlacion_vuelta": round(c3, 4),
        "nota": "acto 3: la segunda subida (c55) hasta la cumbre (c63-c70); al terminar c70 vuelve a c55",
        "entradas": entries(T, sr, s3, (55, 63), {55: "subida", 63: "cumbre"})}))
    # la última resistencia (10 %): la meseta de la cumbre. El acto 3 vuelve de la cumbre a la subida en cada vuelta
    # (-14 -> -18 dB por compás) y en el Último Desfile eso se oía como un bajón. c69 sigue en c61 casi igual (correlación
    # 0.52, el flujo de la costura en la mediana de los tiempos fuertes, sin salto de nivel)
    act4, s4, c4 = section_loop(x, sr, T, 61, 69)
    assert peak_db(act4 * g) <= -1.0
    save("boss_final_4", act4 * g, sr, loop_meta(act4, g, sr, bar, {
        "fuente": name, "bpm": bpm, "compases": "c61-c68 (8)", "correlacion_vuelta": round(c4, 4),
        "nota": "última resistencia: la cumbre de la segunda subida en loop"}))
    outro(x, sr, T, bar, 74, g, "boss_final_out", name, note="c74: el último golpe del taiko y la cola grave")


# ============================================================================ final: Sakuya4 (PeriTune, CC BY 4.0)
def ending(target=-16.0):
    """Tema entero: koto y piano solos (sale del silencio del final), después la orquesta, la cumbre y el cierre."""
    name = "end_sakuya4"; x, sr = src(name)
    a = first_sound(x, sr, -60)
    env = np.convolve(np.abs(mono(x)), np.ones(4096) / 4096, mode="same")
    last = len(env) - int(np.argmax(env[::-1] > env.max() * 10 ** (-60 / 20)))
    y = x[a:last].copy()
    Fo = int(1.0 * sr); y[-Fo:] *= fade(Fo, "out")
    g = gain_for(y, sr, target)
    save("ending", y * g, sr, {"fuente": name, "bpm": 80.0, "compas_s": 3.0, "tipo": "tema entero (vuelve a empezar si sigue sonando)",
         "nota": "0-24 s koto y piano solos; desde 24 s entra la orquesta; tema 36-63 s; cumbre 63-75 s; reprise y cierre"})


# ============================================================================ plan para AudioManager
PHASES = {
    # fase 2 de Gorō: la transición desde su c3 (koto y percusión liviana, 6 compases antes del final): los tambores caen
    # 6.8 s después del cambio. Entera eran 13 s de koto solo con el jefe ya enfurecido
    "boss_goro": {1: ("boss_goro", "boss_goro_intro", None), 2: ("boss_goro_2", "boss_goro_2_in", None, 6)},
    "boss_lake": {1: ("boss_lake", "boss_lake_intro", None), 2: ("boss_lake", None, "desarrollo"), 3: ("boss_lake_3", None, None)},
    "boss_bamboo": {1: ("boss_bamboo", "boss_bamboo_intro", None), 2: ("boss_bamboo", None, "c_taiko"), 3: ("boss_bamboo", None, "b")},
    # 4: la última resistencia (10 %), la meseta de la cumbre
    "boss_final": {1: ("boss_final", "boss_final_intro", None), 2: ("boss_final_2", None, None), 3: ("boss_final_3", None, None),
                   4: ("boss_final_4", None, None)},
}
# al caer el jefe: (toma final o None, fundido en s si no hay toma, vuelve la música de la zona al terminar). Wuxia
# termina en un fundido largo, no en un golpe: el bambú se funde. Kokuyō no devuelve la exploración: después viene
# la campana, la luna y el final
OUTROS = {"boss_goro": ("boss_goro_out", 0.0, True), "boss_lake": ("boss_lake_out", 0.0, True),
          "boss_bamboo": (None, 3.5, True), "boss_final": ("boss_final_out", 0.0, False)}


def write_plan(report):
    plan = {"_nota": ("Generado por Tools/Audio/build_boss_music.py. Por fase: clip en loop, intro o transición que se toca "
                      "una vez antes (PlayScheduled del loop a las 'muestras' de la intro) y, si la fase es otro punto del "
                      "mismo clip, la muestra de entrada. Los cambios de fase conviene hacerlos en el próximo límite de "
                      "compás del clip que suena (compas_s desde el comienzo del clip)."), "jefes": {}, "clips": {}, "finales": {}}
    for key, v in report.items():
        plan["clips"][key] = {k: v[k] for k in ("tipo", "muestras", "segundos", "sr", "bpm", "compas_s", "tambores_s", "golpe_s", "entradas", "LUFS")
                              if k in v}
    for boss, (clip, fade_s, resume) in OUTROS.items():
        plan["finales"][boss] = {"clip": clip if clip in report else None, "fundido_s": fade_s, "vuelve_exploracion": resume}
    for boss, phases in PHASES.items():
        out = {}
        for ph, (clip, intro, entry, *rest) in phases.items():
            if clip not in report:
                continue
            d = {"clip": clip}
            if intro:
                d["intro"] = intro
            if rest and intro in report:
                # la intro entra 'rest[0]' compases antes de su final (su grilla se cuenta desde el final)
                ri = report[intro]
                d["intro_compases_antes_del_final"] = rest[0]
                d["intro_muestra"] = int(round(ri["muestras"] - rest[0] * ri["compas_s"] * ri["sr"]))
            if entry:
                d["entrada"] = entry
                d["entrada_muestra"] = report[clip]["entradas"][entry]["muestra"]
            out[str(ph)] = d
        plan["jefes"][boss] = out
    plan["jefes"]["ending"] = {"1": {"clip": "ending"}}
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
    for boss, phases in plan["jefes"].items():
        ph = []
        for n in sorted(phases, key=int):
            p = phases[n]
            intro = '"%s"' % p["intro"] if p.get("intro") else "null"
            ph.append('new Phase("%s", %s, %d, %d)' % (p["clip"], intro, p.get("entrada_muestra", 0), p.get("intro_muestra", 0)))
        fin = plan["finales"].get(boss, {"clip": None, "fundido_s": 2.0, "vuelve_exploracion": True})
        outro = '"%s"' % fin["clip"] if fin["clip"] else "null"
        L.append('            new Track("%s", new[] { %s }, %s, %sf, %s),' % (
            boss, ", ".join(ph), outro, repr(float(fin["fundido_s"])), "true" if fin["vuelve_exploracion"] else "false"))
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
        nxt = key if "loop" in meta["tipo"] else meta.get("desemboca_en")
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
        print("%-18s última página (de %d del muxer): granule %d -> %d, la anterior termina en %d" % (
            key, len(pages) - k, pages[-1][2], n, pages[k - 1][2]))


def load_wav(path):
    sr, y = wf.read(path)
    return np.asarray(y, dtype=np.float32), sr


def cmd_verify(names=()):
    """Después del Vorbis: el último granule de cada .ogg es el largo exacto (lo que respeta Unity al importar), la
    decodificación arranca alineada con el original (sin retardo) y la costura del loop sigue limpia."""
    rep = json.load(open(os.path.join(OUT, "build_report.json"), encoding="utf-8"))
    ok = True
    for key in wanted(rep, names):
        v = rep[key]
        ogg = os.path.join(OUT, key + ".ogg")
        b = open(ogg, "rb").read()
        i = b.rfind(b"OggS")
        gran = int.from_bytes(b[i + 6:i + 14], "little", signed=True)
        x, sr = load_wav(os.path.join(OUT, key + ".wav"))
        y = np.load(os.path.join(OUT, "enc", "check", key + ".npy"))
        n = min(len(x), sr * 2)
        c = np.correlate(mono(y[:n + 400]), mono(x[200:n - 200]), mode="valid")
        lag = int(np.argmax(c)) - 200
        line = "%-18s granule %9d  muestras %9d  %s  retardo %+d" % (key, gran, v["muestras"], "OK" if gran == v["muestras"] else "DISTINTO", lag)
        if gran != v["muestras"] or lag != 0:
            ok = False
        if "loop" in v["tipo"]:
            yy = y[:v["muestras"]]
            m = seam_metrics(np.concatenate([yy, yy]), sr, [len(yy) / sr], v["compas_s"])[0]
            line += "  costura: flujo %.0f (p50 %.0f, p90 %.0f)  %.1f/%.1f dB" % (
                m["flujo"], m["flujo_tiempos_fuertes_p50"], m["flujo_tiempos_fuertes_p90"], m["nivel_antes_dB"], m["nivel_despues_dB"])
        print(line)
    print("TODO OK" if ok else "HAY PROBLEMAS")


# Comprimido en memoria (Vorbis), precargado en segundo plano: MusicDirector encadena intro, vueltas y cambios de fase
# con PlayScheduled, que es exacto a la muestra con el clip ya cargado; con Streaming el arranque depende de que el
# stream llegue a abrirse a tiempo. Son ~20 MB comprimidos en total.
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


def cmd_preview():
    """Cómo suena cada pelea, para escucharla fuera de Unity (<out>/preview/preview_<jefe>.wav): intro, fase 1 un rato y
    los cambios de fase como los haría AudioManager. Un cambio dentro del mismo clip espera el próximo límite de compás y
    funde un pulso; un clip nuevo después de un loop entero arranca justo al terminar la vuelta; antes de un silencio
    (barra falsa de Gorō, eclipse de Kokuyō) el loop se apaga en 0.5 s."""
    rep = json.load(open(os.path.join(OUT, "build_report.json"), encoding="utf-8"))
    pv = os.path.join(OUT, "preview"); os.makedirs(pv, exist_ok=True)
    sr = 44100
    clips = {k: load_wav(os.path.join(OUT, k + ".wav"))[0] for k in rep}

    def looped(k, start, n):
        y = clips[k]
        return y[(start + np.arange(n)) % len(y)]

    loops = lambda k, n: ("loop", k, n * rep[k]["segundos"])
    plans = {
        "goro": [("intro", "boss_goro_intro"), loops("boss_goro", 1.6), ("silencio", 2.0), ("intro", "boss_goro_2_in"), loops("boss_goro_2", 1.5)],
        "lake": [("intro", "boss_lake_intro"), ("fase", "boss_lake", None, 80), ("fase", "boss_lake", "desarrollo", 60), ("fase", "boss_lake_3", None, 110)],
        "bamboo": [("intro", "boss_bamboo_intro"), ("fase", "boss_bamboo", None, 90), ("fase", "boss_bamboo", "c_taiko", 80)],
        "final": [("intro", "boss_final_intro"), loops("boss_final", 2), loops("boss_final_2", 0.85), ("silencio", 1.6), loops("boss_final_3", 2)],
    }
    events = {}
    for name, steps in plans.items():
        out = []; pending = None; ev = []
        pos = lambda: sum(len(o) for o in out) / sr
        for i, st in enumerate(steps):
            ev.append((round(pos(), 3), st[0] + " " + str(st[1]) + ("" if len(st) < 4 or not st[2] else " @" + st[2])))
            if st[0] == "intro":
                out.append(clips[st[1]])
            elif st[0] == "silencio":
                out.append(np.zeros((at(st[1], sr), 2), np.float32))
            elif st[0] == "loop":
                y = looped(st[1], 0, at(st[2], sr))
                L = len(clips[st[1]])
                ev += [(round(pos() + j * L / sr, 3), "vuelta") for j in range(1, int(len(y) // L) + 1)]
                if i + 1 < len(steps) and steps[i + 1][0] == "silencio":
                    F = at(0.5, sr); y[-F:] *= fade(F, "out")
                out.append(y)
            else:
                k, entry, dur = st[1:]
                e = rep[k]["entradas"][entry]["muestra"] if entry else 0
                b = rep[k]["compas_s"] * sr
                n = int(math.ceil((e + at(dur, sr)) / b) * b) - e      # el cambio cae en un límite de compás del clip
                L = len(clips[k])
                ev += [(round(pos() + (j * L - e) / sr, 3), "vuelta") for j in range(1, (e + n) // L + 1)]
                y = looped(k, e, n)
                if pending is not None:
                    F = len(pending); y[:F] = y[:F] * fade(F, "in") + pending
                F = at(rep[k]["compas_s"] / 4, sr)
                pending = looped(k, e + n, F) * fade(F, "out")
                out.append(y)
        y = np.concatenate(out)
        wf.write(os.path.join(pv, "preview_" + name + ".wav"), sr, y.astype(np.float32))
        events[name] = ev
        print("preview", name, round(len(y) / sr, 1), "s")
    json.dump(events, open(os.path.join(pv, "events.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def credits_md():
    """Filas de CREDITS.md para la música de jefes y el final (las usa también build_audio.write_credits)."""
    keys = {"goro_bosskoto": "`boss_goro`, `boss_goro_intro`, `boss_goro_2_in`, `boss_goro_2`, `boss_goro_out`",
            "lake_amenoshita": "`boss_lake`, `boss_lake_intro`, `boss_lake_3`, `boss_lake_out`",
            "bamboo_wuxia": "`boss_bamboo`, `boss_bamboo_intro`",
            "final_tad_revenge": "`boss_final`, `boss_final_intro`, `boss_final_2`, `boss_final_3`, `boss_final_4`, `boss_final_out`",
            "end_sakuya4": "`ending`"}
    rows = ["## Música de jefes y del final (por fases, `Tools/Audio/build_boss_music.py`)", "",
            "| Claves | Tema | Autor | Licencia | Cambios |", "|---|---|---|---|---|"]
    change = {"goro_bosskoto": "cortado en compases: intro, loop largo con el corte; fase 2 medio tono arriba (re-muestreo 89/84) y +1 dB; el golpe final (c51) medio tono arriba como cierre",
              "lake_amenoshita": "anacrusa como intro, el ciclo de 63 compases en loop y un loop sin apertura ni corte (c7-c54) para la fase 3; el último tiempo de c124 y el golpe final como cierre; sonoridad normalizada",
              "bamboo_wuxia": "crescendo inicial como intro y el ciclo de 81 compases en loop; sonoridad normalizada",
              "final_tad_revenge": "cortado en compases: intro, cuatro loops (c5-c20, c21-c56, c55-c70, c61-c68) y el golpe final (c74) como cierre; sonoridad normalizada",
              "end_sakuya4": "silencios recortados, fundido de 1 s al final, sonoridad normalizada"}
    for k, (url, page, author, title, lic, lic_url) in SOURCES.items():
        rows.append(f"| {keys[k]} | [{title}]({page}) | {author} | [{lic}]({lic_url}) | {change[k]} |")
    rows += ["", "Los temas de PeriTune publicados hasta febrero de 2026 siguen bajo CC BY 4.0 (https://peritune.com/about/);",
             "el crédito pedido es \"PeriTune\". TAD pide crédito por CC BY 4.0 en su página de OpenGameArt.", "",
             "### Agregar un tema por fases", "",
             "1. La fuente en `SOURCES` de `build_boss_music.py` (url, página, autor, título, licencia) y su fila en la tabla",
             "   con lo que se le cambió. Sin licencia que permita cortarla y redistribuirla, no entra.",
             "2. Medir la grilla: BPM y el primer tiempo fuerte (`grid(bpm, primer_compas)`); los ataques del tema tienen que",
             "   caer a ±3 ms de ella. Todo corte se hace en compases de esa grilla, 8 ms antes del tiempo fuerte.",
             "3. Una función por tema que guarde (`save`) la intro (una vez, termina donde arranca el loop), cada loop",
             "   (`section_loop`: vuelve donde suena lo mismo que seguiría; `full_cycle` si el tema se repite entero), las",
             "   secciones de entrada dentro de un loop (`entries`: muestra del compás) y el cierre (`outro`: el golpe",
             "   final del tema y su cola). Una sola ganancia por jefe, picos a -1 dBFS como mucho.",
             "4. La fila en `PHASES` (por fase: loop, intro o transición, sección de entrada y, si la transición entra más",
             "   adelante, cuántos compases antes de su final) y en `OUTROS` (cierre, fundido si no hay, si vuelve la zona).",
             "5. Los pasos del encabezado del script: build, Vorbis con Blender, trim, verify (largo exacto, sin retardo y",
             "   costura limpia), install (los .ogg, `Tools/Audio/boss_music.json` y `Scripts/Audio/MusicPlan.cs`) y las",
             "   claves nuevas en la lista `music` de `NindoContent`.",
             "6. En el juego: `musicKey` del jefe y `Game.Audio.SetBossMusicPhase(n)` en cada fase. Un cambio entra en el",
             "   próximo compás; antes de un silencio de la pelea, `SilenceBossMusic` y la fase siguiente entra apenas se",
             "   la pide. Al caer el jefe, `Boss.Die` llama a `EndBossMusic` (el cierre en el próximo tiempo).", ""]
    return rows


def main():
    global SRC, OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "trim", "verify", "install", "plan", "preview"])
    ap.add_argument("names", nargs="*")
    ap.add_argument("--src")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    SRC, OUT = a.src, a.out
    os.makedirs(OUT, exist_ok=True)
    if a.cmd == "build":
        cmd_build(a.names or ["goro", "lake", "bamboo", "final", "ending"])
    elif a.cmd == "trim":
        cmd_trim(a.names)
    elif a.cmd == "verify":
        cmd_verify(a.names)
    elif a.cmd == "install":
        cmd_install(a.names)
    elif a.cmd == "plan":
        cmd_plan()
    else:
        cmd_preview()


if __name__ == "__main__":
    main()
