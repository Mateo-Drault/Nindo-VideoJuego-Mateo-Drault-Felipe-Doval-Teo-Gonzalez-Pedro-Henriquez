# Conversión de audio con el módulo 'aud' de Blender (no hay ffmpeg en las máquinas del equipo).
#   decode: mp3/ogg/wav -> WAV float32 estéreo a la frecuencia original (sin re-muestrear: los cortes de la música
#           de jefes se hacen sobre la señal tal cual vino)
#   encode: cada <out>/*.wav -> <out>/<clave>.ogg (Vorbis) y su decodificación de control en <out>/check/<clave>.npy
#           (float32; escribirla como WAV con aud falla en algunos largos: "filling the audio frame failed")
# Uso:
#   blender -b --factory-startup --python Tools/Audio/aud_convert.py -- decode <archivo_fuente> <salida.wav>
#   blender -b --factory-startup --python Tools/Audio/aud_convert.py -- encode <carpeta> <bitrate_bps>
import aud, sys, os, glob
import numpy as np

args = sys.argv[sys.argv.index("--") + 1:]


def write(sound, path, rate, ogg=False, bitrate=0):
    if ogg:
        sound.write(path, rate=rate, channels=aud.CHANNELS_STEREO, format=aud.FORMAT_FLOAT32,
                    container=aud.CONTAINER_OGG, codec=aud.CODEC_VORBIS, bitrate=bitrate)
    else:
        sound.write(path, rate=rate, channels=aud.CHANNELS_STEREO, format=aud.FORMAT_FLOAT32,
                    container=aud.CONTAINER_WAV, codec=aud.CODEC_PCM)


if args[0] == "decode":
    s = aud.Sound(args[1])
    rate = int(s.specs[0])
    write(s, args[2], rate)
    print("OK decode", os.path.basename(args[1]), rate)
elif args[0] == "encode":
    out, br = args[1], int(args[2])
    chk = os.path.join(out, "check")
    os.makedirs(chk, exist_ok=True)
    for w in sorted(glob.glob(os.path.join(out, "*.wav"))):
        key = os.path.splitext(os.path.basename(w))[0]
        s = aud.Sound(w)
        rate = int(s.specs[0])
        o = os.path.join(out, key + ".ogg")
        write(s, o, rate, ogg=True, bitrate=br)
        np.save(os.path.join(chk, key + ".npy"), np.asarray(aud.Sound(o).data(), dtype=np.float32))
        print("OK encode", key, rate, os.path.getsize(o))
