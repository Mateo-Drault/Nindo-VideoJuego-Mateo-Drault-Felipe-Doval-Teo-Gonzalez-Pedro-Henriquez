"""El desvío de Chikuō (síntesis pura, con la identidad de build_audio.py): la palma que aparta la hoja de Kaito sin
parar el golpe (BambooMasterBoss.Swat, HitResult.Deflected). Escribe Nindo/Assets/Nindo/Audio/Sfx/<clave>_<n>.wav y su .meta.

    python Tools/Audio/sfx_chikuo.py

Claves (las usa el código con Game.Audio.Play):
  palm_deflect   el cachetazo de la palma contra el plano de la hoja, la hoja que sigue de largo rozando (un "tsss" de
                 acero apagado, no un choque) y la manga que acompaña el barrido. Antes sonaba "parry" (el choque de acero
                 del parry de Kaito, a media voz): se leía como que Kaito había parado algo
Después hay que registrar la clave en NindoContent.sfx (generate_assets.py audio_entries la toma del nombre).
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


def palm_deflect(i):
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


SOUNDS = {"palm_deflect": (palm_deflect, 2)}
# por debajo del parry y del choque (que son avisos): es la confirmación de que el maestro apartó el corte
PEAK_DB = {"palm_deflect": -5.0}


def main():
    for key, (fn, n) in SOUNDS.items():
        for i in range(n):
            p = os.path.join(OUT, f"{key}_{i + 1}.wav")
            x = fn(i)
            write_wav(p, x, PEAK_DB.get(key, -1.0))
            write_meta(p, audio_meta(stream=False, mono=True))
            print(f"{key}_{i + 1:<14} {os.path.getsize(p) / 1024:6.0f} KB  {len(x) / SR:.2f} s  guid {ensure_guid(p)}")


if __name__ == "__main__":
    main()
