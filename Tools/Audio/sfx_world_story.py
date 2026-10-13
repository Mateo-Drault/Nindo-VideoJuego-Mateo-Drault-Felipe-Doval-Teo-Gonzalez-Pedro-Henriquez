"""Efectos del rezo en los santuarios y del sello de la muralla (síntesis pura, con la misma identidad que
build_audio.py: campanas del templo, cristal y aire). Escribe Nindo/Assets/Nindo/Audio/Sfx/<clave>_1.wav y su .meta.

    python Tools/Audio/sfx_world_story.py

Claves (las usa el código con Game.Audio.Play):
  incense_light    el espíritu de la bandana prende el incienso: chispa, una campanita y el siseo de la brasa
  bandana_charge   la bandana se enciende frente al portón: brillo que sube y un zumbido que crece (1.6 s)
  bandana_release  la luz sale de la palma: soplo que baja, campana clara y un golpe de taiko
  wall_seal_break  el sello de sombra estalla: crujido, esquirlas de cristal, estruendo grave y campanas de oro
Después hay que registrar las claves en NindoContent.sfx (generate_assets.py audio_entries las toma del nombre).
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


def crackles(dur, seed, density, lo=2500, hi=8000):
    """chasquidos sueltos (la brasa del incienso, más finos que los de la leña)."""
    r = rng(seed)
    n = secs(dur)
    x = (r.random(n) < density / SR) * r.standard_normal(n) * r.uniform(0.3, 1.0, n)
    x = np.convolve(x, np.exp(-np.arange(secs(0.003)) / secs(0.0008)), "same")
    return filt(x, lo, hi)


def incense_light():
    # un fósforo que prende, no un golpe: el chasquido entra en 30 ms (antes en 2 ms, y con -8 dB de RMS pegaba como el
    # sello de la muralla que estalla); el nivel lo baja PEAK_DB
    d = 1.0
    spark = filt(noise(0.06, 1201), 2500, 9000) * env_exp(0.06, 0.012, attack=0.03)
    chime = partials(1318.5, [1, 2.01, 3.02], [1, 0.25, 0.08], [0.7, 0.3, 0.18], 0.9, seed=1202)
    fizz = band(noise(d, 1203), 3000, 1.5) * env_points(d, [(0, 0), (0.04, 0.6), (0.3, 0.25), (d, 0)])
    pops = crackles(d, 1204, 14, 1800, 6000) * env_points(d, [(0, 0), (0.05, 1), (d, 0.2)])
    warm = partials(880, [1, 2.0], [1, 0.25], [0.5, 0.25], 0.8, seed=1205)
    x = mix((spark, 0, 0.45), (chime, 0.02, 0.4), (warm, 0.02, 0.25), (fizz, 0.0, 0.1), (pops, 0.03, 0.22))
    return reverb(x, 0.25, 1.2, 0.4)


def bandana_charge():
    d = 1.6
    t = t_axis(d)
    trem = 1 + (0.15 + 0.35 * t / d) * np.sin(2 * np.pi * (4 + 8 * t / d) * t)
    tones = sum(osc(glide(f, f * 2, d, 1.6), d) / (k + 1) for k, f in enumerate((330, 495, 660)))
    tones = tones * trem * env_points(d, [(0, 0), (d * 0.85, 1), (d, 0.6)])
    air = sweep(noise(d, 1211), 600, 4200, q=2.5) * env_points(d, [(0, 0), (d * 0.9, 0.9), (d, 0.5)])
    hum = osc(110, d) * 0.6 + osc(165, d) * 0.3
    hum = hum * env_points(d, [(0, 0), (d, 1)]) ** 1.5
    return reverb(mix((tones, 0, 0.45), (air, 0, 0.22), (hum, 0, 0.5)), 0.3, 1.6, 0.5)


def bandana_release():
    d = 1.4
    w = whoosh(0.6, 4500, 500, 0.15, 1.6, seed=1221)
    b1 = bell(880, 1.4, 0.9, 1.0, seed=1222)
    b2 = bell(1318.5, 1.2, 0.7, 0.8, seed=1223)
    taiko = thump(150, 55, 0.6, 0.18, seed=1224)
    x = mix((w, 0, 0.5), (b1, 0.02, 0.55), (b2, 0.05, 0.3), (taiko, 0.0, 1.0))
    return reverb(x, 0.35, 2.0, 0.7)


def wall_seal_break():
    crack = filt(noise(0.16, 1231), 900, 6500) * env_exp(0.16, 0.03)
    shards = sum(partials(f, [1, 2.7, 5.2], [1, 0.5, 0.3], [0.25, 0.12, 0.07], 0.6, 1232 + k)
                 for k, f in enumerate([1700, 2300, 2900, 3500]))
    boom = thump(75, 28, 1.4, 0.5, seed=1237)
    rumble = filt(noise(1.6, 1238), 30, 180) * env_exp(1.6, 0.5, 0.01)
    # la luz de oro que queda: campanitas que suben (la escala in del sello del juego) y una campana grave
    gold = [partials(f, [1, 2.0, 3.01], [1, 0.35, 0.15], [1.2, 0.5, 0.3], 1.8, seed=1240 + k)
            for k, f in enumerate((1174.7, 1318.5, 1760, 2349.3))]
    tail = bell(392, 3.2, 2.2, 0.8, seed=1245)
    x = mix((crack, 0, 0.7), (shards, 0.01, 0.22), (boom, 0, 1.0), (rumble, 0, 0.7),
            (gold[0], 0.25, 0.25), (gold[1], 0.37, 0.22), (gold[2], 0.49, 0.2), (gold[3], 0.61, 0.18), (tail, 0.15, 0.45))
    # saturado suave al final: más cuerpo con el mismo pico (RMS de -9.9 a -6.4 dB en 50 ms), así es lo más fuerte de su
    # escena aunque las dos hojas del portón suenen (gate_open) después
    x = reverb(x, 0.4, 2.8, 1.0)
    return distort(x / np.abs(x).max(), 1.8)


# pico de cada uno (dBFS): todos se normalizan al pico; el del incienso queda abajo para que la brasa sea chiquita
PEAK_DB = {"incense_light": -9.0}

SOUNDS = {
    "incense_light": incense_light,
    "bandana_charge": bandana_charge,
    "bandana_release": bandana_release,
    "wall_seal_break": wall_seal_break,
}


def main():
    for key, fn in SOUNDS.items():
        p = os.path.join(OUT, f"{key}_1.wav")
        write_wav(p, fn(), PEAK_DB.get(key, -1.0))
        write_meta(p, audio_meta(stream=False, mono=True))
        print(f"{key:18} {os.path.getsize(p) / 1024:6.0f} KB  guid {ensure_guid(p)}")


if __name__ == "__main__":
    main()
