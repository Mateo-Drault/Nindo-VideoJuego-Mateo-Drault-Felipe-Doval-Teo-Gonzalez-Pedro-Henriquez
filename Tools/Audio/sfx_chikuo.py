"""Los sonidos de Chikuō (síntesis pura, con la identidad de build_audio.py). Escribe Nindo/Assets/Nindo/Audio/Sfx/<clave>_<n>.wav
(o <clave>.wav si hay una sola) y su .meta. Diseño: Docs/handoff/diseno/chikuo_v2.md, sección 18.

    python Tools/Audio/sfx_chikuo.py

Afinación (18.2): el tema boss_bamboo, medido con un cromagrama sobre lo que decodifica el Audio de Blender (las fases 1-2:
F# 1.00, B 0.68, A 0.57, E 0.57, D 0.37, C# 0.20), es F# menor pentatónica (F# A B C# E); la fase 3 (boss_bamboo_3:
G 1.00, F 0.48, A# 0.36, C 0.35, D 0.24) va medio tono arriba, G menor pentatónica. Los cascabeles y la flauta suenan
dentro de la música: cada sonido tonal tiene su versión '_p3' medio tono arriba (BambooMasterBoss.Sfx la elige).

Claves (las usa el código con Game.Audio.Play):
  palm_deflect          el cachetazo de la palma contra la hoja (el Chikuō viejo; lo usa PlayerController con Deflected)
  tell_chime_hi         los cascabeles cortos de los hombros: dos golpecitos agudos al levantar la flauta (un dardo)
  tell_chime_lo         los largos del ruedo: "tok-tok" al agacharse (salta a otra caña)
  tell_chime_cascade    todos, de agudo a grave (se tira encima o barre: rojo)
  tell_chime_shimmer    el tintineo blanco: la caña está cargada (seguido y agudo, late a 4 Hz)
  chime_jangle          el sacudón de los cascabeles (cayó, cada corte en un hueco: "lo agarraste")
  flute_n1..flute_n5    la flauta de bambú, la pentatónica de abajo hacia arriba (Pregunta y Respuesta, los cambios)
  flute_phrase_intro    la frase de la presentación (colgado de la caña); flute_phrase_forest, la del cambio 2
  flute_squeak          la flauta que chilla (Desafinado)
  dart_blow, dart_whistle, dart_thunk    el soplido, el silbador (el pesado, rojo) y el dardo que se clava en el piso
  bamboo_thok           corte a la caña sin campanas (hueco, opaco)
  bamboo_whip           el latigazo: el chasquido y el "zuing" de la caña tensa que se suelta
  bamboo_slam           el estampado contra la otra caña (grave, con las hojas)
  bamboo_crack, bamboo_break, bamboo_fall    rajada, quebrada, talada (la caña que cae)
  stalk_bow, stalk_whoosh, stalk_grow        las seis cañas que se inclinan, que se enderezan y la Madre que nace
Después hay que registrar las claves en NindoContent.sfx: Tools/Unity/chikuo_assets.py --sfx (solo la lista de efectos).
"""
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "Unity"))
from dsp import *  # noqa
from unity_yaml import write_meta, audio_meta, ensure_guid

REPO = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(REPO, "Nindo", "Assets", "Nindo", "Audio", "Sfx")

# F# menor pentatónica (A4 = 440): F# A B C# E en tres octavas
PENTA = [369.99, 440.0, 493.88, 554.37, 659.26, 739.99, 880.0, 987.77, 1108.73, 1318.51, 1479.98, 1760.0, 1975.53]
SEMITONE = 2 ** (1 / 12)


def palm_deflect(i, k=1.0):
    # la palma: piel contra metal plano, seca y corta (sin el "pac" agudo de un aplauso), con el cuerpo del golpe abajo
    slap = filt(noise(0.06, 1300 + i), 350, 3200) * env_exp(0.06, 0.007, attack=0.0015)
    body = thump(190 - 25 * i, 115, 0.14, 0.032, seed=1302 + i)
    # la hoja que sigue de largo rozando la palma: acero apagado y bajo (el choque de verdad es "clang", que es un aviso)
    graze = filt(sweep(noise(0.16, 1304 + i), 5200, 2600, q=3.0), 1500, 7000) * env_points(0.16, [(0, 0), (0.012, 1), (0.16, 0)]) ** 2
    ring = partials(1180 + 110 * i, [1.0, 2.62, 4.9], [1.0, 0.35, 0.12], [0.09, 0.05, 0.03], 0.22, seed=1306 + i)
    ring = filt(ring, None, 4500)
    # la manga que acompaña el barrido de la mano
    sleeve = whoosh(0.24, 420, 2300, peak_t=0.3, q=1.2, seed=1308 + i, rough=0.25)
    x = mix((sleeve, 0.0, 0.55), (slap, 0.012, 1.0), (body, 0.012, 0.8), (graze, 0.02, 0.28), (ring, 0.014, 0.1))
    return reverb(x, 0.14, 0.9, 0.3)


# ---------------------------------------------------------------- los cascabeles (tubos de bambú huecos)
def tube(freq, dur=0.5, seed=0, wood=1.0, decay=1.0):
    """Un cascabel de bambú: los modos de un tubo libre (1 : 2.76 : 5.40 : 8.93) que se apagan rápido (el bambú es
    madera, no metal), el golpe seco de caña contra caña y el hueco del tubo (una resonancia en la fundamental)."""
    x = partials(freq, [1.0, 2.76, 5.40, 8.93], [1.0, 0.42, 0.18, 0.07],
                 [0.22 * decay, 0.09 * decay, 0.045 * decay, 0.025 * decay], dur, seed=seed, detune=0.003)
    knock = filt(noise(0.03, seed + 1), freq * 0.8, freq * 4.0) * env_exp(0.03, 0.006, attack=0.0008)
    x = mix((x, 0.0, 1.0), (knock, 0.0, 0.35 * wood))
    return peak(x, freq, freq * 0.08, 0.8)


def chime_hi(i, k=1.0):
    # dos golpecitos agudos al levantar la flauta (el dardo): dos tubos cortos de los hombros
    a, b = PENTA[10 + i % 3] * k, PENTA[9 + (i + 1) % 3] * k
    x = mix((tube(a, 0.45, 2100 + i, 0.7), 0.0, 1.0), (tube(b, 0.45, 2110 + i, 0.7), 0.075, 0.8))
    return reverb(x, 0.22, 1.1, 0.35)


def chime_lo(i, k=1.0):
    # "tok-tok": los tubos largos del ruedo, más madera que tono (el agachado del salto)
    a, b = PENTA[0 + i] * k, PENTA[3 + i] * k
    x = mix((tube(a, 0.5, 2200 + i, 1.6, 0.8), 0.0, 1.0), (tube(b, 0.5, 2210 + i, 1.6, 0.8), 0.11, 0.85))
    return reverb(x, 0.18, 1.0, 0.3)


def chime_cascade(i, k=1.0):
    # todos de agudo a grave en 0.35 s (rojo: se tira encima o barre)
    notes = [PENTA[j] * k for j in (12, 11, 10, 9, 8, 7, 6, 5, 3, 1, 0)]
    parts = [(tube(f, 0.55, 2300 + n, 0.9), n * 0.034, 0.9 - 0.03 * n) for n, f in enumerate(notes)]
    return reverb(mix(*parts), 0.25, 1.4, 0.45)


def chime_shimmer(i, k=1.0):
    # el tintineo blanco: tubos agudos seguidos, sin ritmo fijo, latiendo a 4 Hz (como el brillo); 1.3 s
    r = rng(2400 + i)
    parts = []
    t = 0.0
    while t < 1.25:
        f = PENTA[r.integers(8, 13)] * k
        g = 0.55 + 0.45 * (0.5 + 0.5 * np.sin(2 * np.pi * 4.0 * t))
        parts.append((tube(f, 0.3, 2410 + len(parts), 0.4, 0.6), t, g * (1.0 - 0.35 * t / 1.25)))
        t += r.uniform(0.035, 0.07)
    return reverb(mix(*parts), 0.3, 1.2, 0.4)


def chime_jangle(i, k=1.0):
    # el sacudón: un racimo de tubos que se chocan entre sí (cayó, le entró un corte)
    r = rng(2500 + i)
    parts = [(tube(PENTA[r.integers(0, 13)] * k, 0.35, 2510 + n, 1.2, 0.5), r.uniform(0, 0.28), r.uniform(0.4, 1.0)) for n in range(11)]
    return reverb(mix(*parts), 0.2, 0.9, 0.3)


# ---------------------------------------------------------------- la flauta de bambú
def flute(freq, dur, seed=0, vib=1.0, breath=1.0):
    """Shakuhachi chico: fundamental fuerte, armónicos impares suaves, el aire de la boquilla y un vibrato que llega tarde."""
    t = t_axis(dur)
    vibrato = 1.0 + 0.006 * vib * np.sin(2 * np.pi * 5.2 * t) * np.clip((t - 0.12) / 0.2, 0, 1)
    f = freq * vibrato
    tone = osc(f, dur) + 0.22 * osc(f * 2, dur) + 0.12 * osc(f * 3, dur) + 0.04 * osc(f * 4, dur)
    air = band(noise(dur, seed), freq * 1.6, q=1.1) * 0.5 * breath
    env = env_points(dur, [(0, 0), (0.045, 1.0), (max(0.05, dur - 0.12), 0.85), (dur, 0)])
    chiff = filt(noise(0.05, seed + 1), 2500, 9000) * env_exp(0.05, 0.012) * 0.4 * breath
    return mix((tone * env, 0.0, 1.0), (air * env, 0.0, 0.35), (chiff, 0.0, 1.0))


FLUTE_NOTES = [739.99, 880.0, 987.77, 1108.73, 1318.51]   # F#5 A5 B5 C#6 E6


def flute_note(n):
    return lambda i, k=1.0: reverb(flute(FLUTE_NOTES[n] * k, 0.42, 2600 + 10 * n), 0.3, 1.6, 0.6)


def flute_phrase(notes, durs, seed):
    def make(i, k=1.0):
        parts, t = [], 0.0
        for n, d in zip(notes, durs):
            parts.append((flute(FLUTE_NOTES[n] * k, d + 0.05, seed + int(t * 100)), t, 1.0))
            t += d
        return reverb(mix(*parts), 0.35, 2.2, 0.8)
    return make


def flute_squeak(i, k=1.0):
    # la flauta que chilla: se le va el aire, sube desafinada y se corta tosiendo
    f = glide(1318.51 * k, 1318.51 * k * 1.38, 0.5, 0.6)
    t = t_axis(0.5)
    tone = (osc(f, 0.5) + 0.5 * osc(f * 2.01, 0.5)) * env_points(0.5, [(0, 0), (0.03, 1), (0.36, 0.8), (0.5, 0)])
    tone *= 1 + 0.5 * np.sin(2 * np.pi * 19 * t)
    air = filt(noise(0.5, 2700 + i), 1500, 8000) * env_points(0.5, [(0, 0), (0.05, 0.7), (0.5, 0)])
    cough = filt(noise(0.12, 2710 + i), 300, 2500) * env_exp(0.12, 0.03)
    return reverb(mix((tone, 0.0, 0.7), (air, 0.0, 0.45), (cough, 0.38, 0.6)), 0.2, 1.0, 0.4)


# ---------------------------------------------------------------- dardos
def dart_blow(i, k=1.0):
    # el soplido corto de la cerbatana: "fft" con el silbido del dardo que sale
    puff = band(noise(0.14, 2800 + i), 1700 + 300 * i, q=0.9) * env_points(0.14, [(0, 0), (0.01, 1), (0.14, 0)]) ** 1.5
    zip_ = whoosh(0.18, 2600, 6500, peak_t=0.25, q=2.0, seed=2810 + i)
    pop = thump(240, 160, 0.06, 0.012, seed=2820 + i)
    return mix((puff, 0.0, 1.0), (zip_, 0.02, 0.55), (pop, 0.0, 0.35))


def dart_whistle(i, k=1.0):
    # el silbador: la gran soplada y el dardo pesado que silba bajando (se oye venir)
    f = glide(2300, 1250, 0.6, 0.8)
    whistle = (osc(f, 0.6) + 0.3 * osc(f * 2, 0.6)) * env_points(0.6, [(0, 0), (0.04, 1), (0.45, 0.7), (0.6, 0)])
    blow = band(noise(0.25, 2900 + i), 900, q=0.8) * env_points(0.25, [(0, 0), (0.02, 1), (0.25, 0)])
    air = whoosh(0.6, 1800, 4200, peak_t=0.4, q=1.4, seed=2910 + i)
    return reverb(mix((blow, 0.0, 0.9), (whistle, 0.03, 0.55), (air, 0.03, 0.5)), 0.15, 0.9, 0.3)


def dart_thunk(i, k=1.0):
    # se clava en la tierra: un "tuc" de madera y el temblor de la aguja
    x = thump(320 + 40 * i, 170, 0.09, 0.018, seed=3000 + i)
    quiver = partials(560 + 60 * i, [1.0, 2.7], [1.0, 0.3], [0.05, 0.02], 0.12, seed=3010 + i) * (1 + 0.6 * osc(38, 0.12, "tri"))
    dirt = filt(noise(0.05, 3020 + i), 300, 2200) * env_exp(0.05, 0.01)
    return mix((x, 0.0, 1.0), (quiver, 0.004, 0.25), (dirt, 0.0, 0.4))


# ---------------------------------------------------------------- las cañas
def bamboo_thok(i, k=1.0):
    # corte a la caña sin campanas: hueco y opaco, el culmo grueso resuena bajo (no es un aviso: es "no así")
    x = tube(210 + 25 * i, 0.4, 3100 + i, 2.2, 1.3)
    hit = filt(noise(0.04, 3110 + i), 600, 4000) * env_exp(0.04, 0.008)
    return reverb(mix((x, 0.0, 1.0), (hit, 0.0, 0.7)), 0.16, 0.9, 0.3)


def bamboo_whip(i, k=1.0):
    # el latigazo: el chasquido seco y el "zuing" de la caña tensa que se suelta (cae de agudo a grave y oscila)
    crack = filt(noise(0.03, 3200 + i), 1800, 11000) * env_exp(0.03, 0.004, attack=0.0005)
    f = glide(820 + 60 * i, 210, 0.55, 0.5)
    t = t_axis(0.55)
    zing = osc(f * (1 + 0.04 * np.sin(2 * np.pi * 11 * t)), 0.55) * env_points(0.55, [(0, 0), (0.01, 1), (0.55, 0)]) ** 1.3
    body = thump(170, 90, 0.3, 0.07, seed=3210 + i)
    rush = whoosh(0.45, 600, 3800, peak_t=0.2, q=1.2, seed=3220 + i)
    return reverb(mix((crack, 0.0, 1.0), (zing, 0.01, 0.55), (body, 0.0, 0.6), (rush, 0.0, 0.5)), 0.2, 1.2, 0.4)


def bamboo_slam(i, k=1.0):
    # el estampado: el viejo de espaldas contra la otra caña (grave, el culmo que vibra y las hojas de arriba)
    body = thump(120, 62, 0.45, 0.12, seed=3300)
    culm = tube(185, 0.8, 3310, 2.0, 2.2)
    leaves = whoosh(0.9, 2500, 7000, peak_t=0.25, q=0.9, seed=3320, rough=0.5)
    return reverb(mix((body, 0.0, 1.0), (culm, 0.0, 0.6), (leaves, 0.04, 0.45)), 0.22, 1.3, 0.5)


def bamboo_crack(i, k=1.0):
    # la rajadura: un crujido de fibras que se abren (chasquidos chicos en racimo)
    r = rng(3400)
    parts = [(filt(noise(0.012, 3410 + n), 1500, 9000) * env_exp(0.012, 0.002), r.uniform(0, 0.22), r.uniform(0.4, 1.0)) for n in range(14)]
    groan = band(noise(0.35, 3430), 380, q=3.0) * env_points(0.35, [(0, 0), (0.05, 1), (0.35, 0)])
    return reverb(mix(*(parts + [(groan, 0.0, 0.6)])), 0.15, 0.8, 0.3)


def bamboo_break(i, k=1.0):
    # la quebradura: el crujido que no para, el chasquido grande y la caña que se va
    x = bamboo_crack(0)
    snap = filt(noise(0.05, 3500), 900, 10000) * env_exp(0.05, 0.008, attack=0.0005)
    body = thump(150, 70, 0.4, 0.1, seed=3510)
    return reverb(mix((x, 0.0, 0.8), (snap, 0.2, 1.0), (body, 0.2, 0.7)), 0.2, 1.2, 0.4)


def bamboo_fall(i, k=1.0):
    # la tala: la caña rajada que se viene abajo (el aire de la copa y el golpe contra el piso)
    creak = band(noise(0.5, 3600), 300, q=2.5) * env_points(0.5, [(0, 0), (0.1, 1), (0.5, 0.3)])
    fall = whoosh(0.7, 500, 2500, peak_t=0.7, q=1.0, seed=3610, rough=0.4)
    impact = thump(95, 50, 0.6, 0.18, seed=3620)
    leaves = whoosh(0.8, 2400, 6500, peak_t=0.1, q=0.9, seed=3630, rough=0.5)
    return reverb(mix((creak, 0.0, 0.6), (fall, 0.1, 0.7), (impact, 0.78, 1.0), (leaves, 0.8, 0.5)), 0.22, 1.6, 0.6)


def stalk_bow(i, k=1.0):
    # las seis cañas que se inclinan a la vez: un gemido largo de madera y el rumor de las copas
    t = t_axis(1.3)
    groan = sum(band(noise(1.3, 3700 + j), f, q=4.0) for j, f in enumerate((180, 240, 310)))
    groan *= env_points(1.3, [(0, 0), (0.25, 1), (1.0, 0.7), (1.3, 0)]) * (1 + 0.3 * np.sin(2 * np.pi * 3 * t))
    rustle = whoosh(1.3, 2000, 6000, peak_t=0.5, q=0.8, seed=3720, rough=0.6)
    return reverb(mix((groan, 0.0, 1.0), (rustle, 0.0, 0.55)), 0.3, 1.8, 0.7)


def stalk_whoosh(i, k=1.0):
    # se enderezan de golpe: un "fuush" de hojas y el chicotazo de seis culmos
    rush = whoosh(0.7, 4000, 900, peak_t=0.3, q=0.9, seed=3800, rough=0.5)
    snaps = [(bamboo_whip(n)[:secs(0.25)] * 0.4, 0.05 + 0.03 * n, 1.0) for n in range(3)]
    return reverb(mix(*([(rush, 0.0, 1.0)] + snaps)), 0.3, 1.6, 0.6)


def stalk_grow(i, k=1.0):
    # la Madre que nace: la tierra que se abre (un rumor grave) y la caña que sube crujiendo
    rumble = filt(noise(1.7, 3900), 30, 160) * env_points(1.7, [(0, 0), (0.15, 1), (1.4, 0.8), (1.7, 0)])
    burst = filt(noise(0.3, 3910), 200, 3000) * env_exp(0.3, 0.06)
    f = glide(140, 420, 1.5, 1.0)
    rise = osc(f, 1.5, "saw") * env_points(1.5, [(0, 0), (0.2, 0.4), (1.3, 0.6), (1.5, 0)])
    rise = band(rise, 600, q=0.7)
    return reverb(mix((rumble, 0.0, 1.0), (burst, 0.0, 0.7), (rise, 0.1, 0.25)), 0.3, 2.0, 0.7)


# clave: (función, variantes, versión de la fase 3 medio tono arriba)
SOUNDS = {
    "palm_deflect": (palm_deflect, 2, False),
    "tell_chime_hi": (chime_hi, 3, True), "tell_chime_lo": (chime_lo, 2, True), "tell_chime_cascade": (chime_cascade, 1, True),
    "tell_chime_shimmer": (chime_shimmer, 1, True), "chime_jangle": (chime_jangle, 2, True),
    "flute_n1": (flute_note(0), 1, True), "flute_n2": (flute_note(1), 1, True), "flute_n3": (flute_note(2), 1, True),
    "flute_n4": (flute_note(3), 1, True), "flute_n5": (flute_note(4), 1, True),
    "flute_phrase_intro": (flute_phrase([0, 2, 1, 3, 2, 4, 3], [0.32, 0.22, 0.42, 0.22, 0.22, 0.5, 0.7], 2650), 1, False),
    "flute_phrase_forest": (flute_phrase([0, 1, 2, 3, 4, 3, 4], [0.24, 0.24, 0.24, 0.24, 0.36, 0.2, 0.9], 2680), 1, False),
    "flute_squeak": (flute_squeak, 1, False),
    "dart_blow": (dart_blow, 2, False), "dart_whistle": (dart_whistle, 1, False), "dart_thunk": (dart_thunk, 2, False),
    "bamboo_thok": (bamboo_thok, 2, False), "bamboo_whip": (bamboo_whip, 2, False), "bamboo_slam": (bamboo_slam, 1, False),
    "bamboo_crack": (bamboo_crack, 1, False), "bamboo_break": (bamboo_break, 1, False), "bamboo_fall": (bamboo_fall, 1, False),
    "stalk_bow": (stalk_bow, 1, False), "stalk_whoosh": (stalk_whoosh, 1, False), "stalk_grow": (stalk_grow, 1, False),
}
# los avisos (cascabeles) arriba, como el resto de los avisos; la confirmación y el ambiente de las cañas por debajo
PEAK_DB = {"palm_deflect": -5.0, "tell_chime_shimmer": -4.0, "chime_jangle": -6.0, "dart_thunk": -8.0, "bamboo_thok": -4.0,
           "stalk_bow": -4.0, "stalk_grow": -3.0, "flute_phrase_intro": -3.0, "flute_phrase_forest": -3.0}


def main():
    for key, (fn, n, p3) in SOUNDS.items():
        for name, k in [(key, 1.0)] + ([(key + "_p3", SEMITONE)] if p3 else []):
            for i in range(n):
                p = os.path.join(OUT, f"{name}_{i + 1}.wav" if n > 1 or key == "palm_deflect" else f"{name}.wav")
                x = fn(i, k)
                write_wav(p, x, PEAK_DB.get(key, -1.0))
                write_meta(p, audio_meta(stream=False, mono=True))
                print(f"{os.path.basename(p):<28} {os.path.getsize(p) / 1024:6.0f} KB  {len(x) / SR:.2f} s  guid {ensure_guid(p)}")


if __name__ == "__main__":
    main()
