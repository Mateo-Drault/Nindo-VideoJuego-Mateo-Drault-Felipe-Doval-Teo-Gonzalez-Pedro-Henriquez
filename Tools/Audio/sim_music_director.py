"""MusicDirector fuera de Unity: la misma máquina de estados (Scripts/Audio/MusicDirector.cs), frame a frame, con el
reloj del DSP en bloques de 1024 muestras, sobre la decodificación de los .ogg (lo que sale de aud_convert.py encode).
Renderiza cada pelea con sus cambios de fase para escucharla (preview_<escena>.wav) y mide cada toma y cada cambio:
tic (energía de agudos en 3 ms contra el entorno), salto de nivel y cuánto suena lo anterior debajo de lo nuevo.

  python Tools/Audio/sim_music_director.py Tools/Audio/boss_music.json <out>/enc/check <carpeta> [escenas...]

Si se cambia MusicDirector.cs, se cambia acá igual: es lo que permite oír las peleas sin abrir Unity.
"""
import sys, os, json, math
import numpy as np
import scipy.io.wavfile as wf
from scipy.signal import butter, sosfilt

SR = 44100
LEAD, COMMIT, LONG_INTRO = 0.25, 0.5, 4.0
RAMP = 265
VOICES = 6
BLOCK = 1024
DIP_GAIN, DIP_TIME = 0.316, 0.03


def kind(tipo):
    return "Outro" if tipo.startswith("outro") else "Once" if "una vez" in tipo else "Loop"


def load_plan(path):
    plan = json.load(open(path, encoding="utf-8"))
    clips = {k: dict(samples=v["muestras"], rate=v["sr"], bar=v["compas_s"], kind=kind(v["tipo"])) for k, v in plan["clips"].items()}
    tracks = {}
    for key, ph in plan["jefes"].items():
        phases = [ph[n] for n in sorted(ph, key=int)]
        fin = plan["finales"].get(key, {"clip": None, "fundido_s": 2.0, "vuelve_exploracion": True})
        tracks[key] = dict(phases=[dict(clip=p["clip"], intro=p.get("intro"), entry=p.get("intro_muestra", 0), hit=p.get("golpe_muestra", 0),
                                        cut=p.get("corte_s", 0.0), outro=p.get("cierre")) for p in phases],
                           outro=fin["clip"], outroFade=fin["fundido_s"], resume=fin["vuelve_exploracion"])
    return clips, tracks


def gain(t, start, ln, dip):
    """VoiceRamp.Gain (acepta arrays)."""
    t = np.asarray(t, dtype=np.float64)
    e = t - start
    u = e / max(1e-3, ln)
    k = np.clip(1 - u, 0, 1) ** 2
    if dip:
        k = k * np.where(e >= DIP_TIME, DIP_GAIN, 1 - (1 - DIP_GAIN) * np.clip(e / DIP_TIME, 0, 1))
    return np.where(t <= start, 1.0, np.where(u >= 1, 0.0, k))


class V:
    def __init__(s):
        s.layer = -1; s.clip = None; s.start = s.end = 0.0; s.offset = 0; s.fadeStart = math.inf; s.fadeLen = 1.0; s.dip = False
        s.cold = False


class Director:
    def __init__(s, clips, tracks, log):
        s.C, s.T = clips, tracks
        s.v = [V() for _ in range(VOICES)]
        s.track = None; s.key = None; s.layer = 0; s.head = s.next = -1; s.playing = s.target = 0
        s.lead = -1.0; s.reqPhase = 0; s.reqFrame = -1; s.frame = 0
        s.pending = s.silent = s.outro = False; s.startAt = s.outroEnd = 0.0
        s.heard = set(); s.log = log; s.done = []; s.now = 0.0; s.finished = []; s.commits = []

    # --- API
    def requested(s, fb):
        return max(fb, s.reqPhase) if s.reqFrame == s.frame else fb

    def Play(s, key, delay=0.0):
        t = s.T[key]
        if t is s.track and not s.silent and not s.outro and (s.playing > 0 or s.pending):
            return
        s.FadeAll(s.now, 0.3, False)
        s.track = t; s.key = key; s.target = max(1, min(s.requested(1), len(t["phases"]))); s.playing = 0
        s.silent = s.outro = False; s.pending = True; s.startAt = s.now + max(0.0, delay); s.head = s.next = -1

    def SetPhase(s, n, lead=-1.0):
        s.reqPhase = n; s.reqFrame = s.frame
        if s.track is None or s.outro:
            return
        n = max(1, min(n, len(s.track["phases"])))
        if s.silent:
            s.target = max(s.target, n); s.lead = lead
            s.FadeAll(s.now + LEAD, 0.4, False)
            s.silent = False; s.pending = True; s.startAt = s.now
            return
        if n <= s.target:
            return
        s.target = n; s.lead = lead

    def Silence(s, fade, with_outro=False):
        if s.track is None or s.outro:
            return False
        if s.silent:
            return True
        if not (with_outro and not s.pending and s.head >= 0 and s.PlayOutro(s.now)):
            s.FadeAll(s.now, max(0.05, fade), False)
        s.head = s.next = -1; s.silent = True; s.pending = False; s.playing = 0
        return True

    def Stop(s, fade):
        s.FadeAll(s.now, max(0.05, fade), False); s.track = None; s.head = s.next = -1
        s.pending = s.silent = s.outro = False; s.playing = s.target = 0

    def End(s):
        if s.track is None:
            return False
        if s.outro:
            return True
        if s.silent or s.pending or s.head < 0:
            s.FadeAll(s.now, 1.0, False); s.Finish(); return True
        if not s.PlayOutro(s.now):
            b = s.NextBoundary(s.now + LEAD, 0.25); f = max(0.5, s.track["outroFade"])
            s.FadeLayer(s.layer, b, f, False); s.outroEnd = b + f
        s.head = s.next = -1; s.outro = True
        return True

    def outro_for(s, n):
        p = s.track["phases"][max(1, min(n, len(s.track["phases"]))) - 1]
        return p["outro"] or s.track["outro"]

    def PlayOutro(s, now):
        o = s.outro_for(s.playing)
        if not o or s.head < 0:
            return False
        b = s.NextBoundary(now + LEAD, 0.25)
        s.FadeLayer(s.layer, b, s.C[s.v[s.head].clip]["bar"] / 4, True)
        s.layer += 1
        v = s.Schedule(o, 0, b, True)
        s.outroEnd = s.v[v].end if v >= 0 else b
        s.commits.append((b, s.layer, "cierre " + o))
        s.log.append((round(b, 3), "cierre", o))
        return v >= 0

    # --- motor
    def LateUpdate(s):
        now = s.now
        if s.track is not None:
            if s.pending:
                s.pending = False
                s.StartLayer(s.target, max(s.startAt, now + LEAD), True)
            if s.head >= 0 and s.next >= 0 and now >= s.v[s.next].end:
                s.log.append((round(now, 3), "se perdieron vueltas: vuelve a entrar"))
                s.CancelLayer(s.layer); s.StartLayer(max(1, s.playing), now + LEAD, False)
            if s.head >= 0 and now >= s.v[s.head].end:
                s.head, s.next = s.next, -1
                if s.head >= 0 and s.C[s.v[s.head].clip]["kind"] == "Loop":
                    h = s.v[s.head]; s.next = s.Schedule(h.clip, 0, h.end, False)
            if s.outro:
                if now >= s.outroEnd:
                    s.Finish()
            elif not s.silent and not s.pending and s.head < 0:
                s.Finish()
            elif not s.silent and s.head >= 0 and s.target != s.playing:
                s.TryCommit(now)
        for i, v in enumerate(s.v):
            if v.layer < 0:
                continue
            ended = now > v.end + 0.1 and i != s.head and i != s.next
            if gain(now, v.fadeStart, v.fadeLen, v.dip) <= 0 or ended:
                s.Release(v)

    def beats_for(s, intro, lead):
        bs = s.C[intro]["bar"] / 4 * s.C[intro]["rate"]
        return max(1, int(round(lead * s.C[intro]["rate"] / bs))), bs

    def TryCommit(s, now):
        h = s.v[s.head]
        if h.start > now + 0.05:
            at = h.start; s.CancelLayer(s.layer); s.StartLayer(s.target, at, True)
            s.log.append((round(at, 3), "reemplazo antes de sonar", s.target)); return
        beat = s.C[h.clip]["bar"] / 4
        b = s.NextBoundary(now + LEAD, 0.25)
        if b - now > COMMIT:
            return
        p = s.track["phases"][s.target - 1]
        intro = p["intro"]; entry = 0
        if intro:
            if s.lead >= 0:
                beats, bs = s.beats_for(intro, s.lead)
            else:
                arrive = s.NextBoundary(b + 2 * beat - 1e-4, 1.0)
                beats = max(1, int(round((arrive - b) / beat))); bs = s.C[intro]["bar"] / 4 * s.C[intro]["rate"]
            entry = max(0, p["hit"] - int(round(beats * bs)))
        s.FadeLayer(s.layer, b, p["cut"] if p["cut"] > 0 else beat, p["cut"] <= 0)
        s.layer += 1; s.head = s.next = -1
        if intro:
            s.head = s.Schedule(intro, entry, b, True)
        s.StartLoop(p["clip"], b)
        s.playing = s.target; s.lead = -1.0
        s.commits.append((b, s.layer, "fase %d" % s.target))
        s.log.append((round(b, 3), "fase", s.target, intro or "", entry))

    def StartLayer(s, phase, at, allow):
        s.layer += 1
        p = s.track["phases"][phase - 1]
        intro = p["intro"] if allow else None
        if intro and phase == 1 and s.key in s.heard and s.C[intro]["samples"] / SR > LONG_INTRO:
            intro = None
        s.head = s.next = -1
        if intro:
            entry = p["entry"]
            if s.lead >= 0:
                beats, bs = s.beats_for(intro, s.lead); entry = max(0, p["hit"] - int(round(beats * bs)))
            s.head = s.Schedule(intro, entry, at, True)
        s.StartLoop(p["clip"], at)
        s.playing = phase; s.lead = -1.0
        if phase == 1:
            s.heard.add(s.key)
        s.commits.append((at, s.layer, "capa %d" % phase))
        s.log.append((round(at, 3), "capa", phase, intro or "", p["clip"]))

    def StartLoop(s, clip, at):
        if s.head >= 0:
            s.next = s.Schedule(clip, 0, s.v[s.head].end, False); return
        s.head = s.Schedule(clip, 0, at, True)
        if s.head >= 0 and s.C[clip]["kind"] == "Loop":
            s.next = s.Schedule(clip, 0, s.v[s.head].end, False)

    def NextBoundary(s, tmin, frac):
        b = s.Boundary(s.v[s.head], tmin, frac) if s.head >= 0 else -1
        if b < 0 and s.next >= 0:
            b = s.Boundary(s.v[s.next], tmin, frac)
        return tmin if b < 0 else b

    def Boundary(s, v, tmin, frac):
        if tmin >= v.end:
            return -1
        c = s.C[v.clip]; unit = c["bar"] * frac * c["rate"]
        pos = v.offset + max(0.0, tmin - v.start) * c["rate"]
        if c["kind"] == "Once":
            b = c["samples"] - math.floor((c["samples"] - pos) / unit) * unit
        else:
            b = math.ceil(pos / unit - 1e-6) * unit
            if b > c["samples"] - unit * 0.05:
                b = c["samples"]
        return v.start + (b - v.offset) / c["rate"]

    def Schedule(s, clip, offset, at, cold):
        i = next((k for k, v in enumerate(s.v) if v.layer < 0), -1)
        if i < 0:
            cand = [k for k, v in enumerate(s.v) if k != s.head and k != s.next and v.fadeStart < math.inf]
            if not cand:
                raise RuntimeError("sin voces")
            i = min(cand, key=lambda k: s.v[k].fadeStart); s.Release(s.v[i])
        v = s.v[i]; c = s.C[clip]
        v.cold = cold; v.clip = clip; v.layer = s.layer; v.offset = offset; v.start = at
        v.end = at + (c["samples"] - offset) / c["rate"]; v.fadeStart = math.inf; v.fadeLen = 1.0; v.dip = False
        return i

    def FadeVoice(s, v, at, ln, dip):
        if v.start >= at + ln:
            s.Release(v, cancelled=True); return
        if at >= v.fadeStart:
            return
        v.fadeStart = at; v.fadeLen = ln; v.dip = dip

    def FadeLayer(s, l, at, ln, dip):
        for v in s.v:
            if v.layer == l:
                s.FadeVoice(v, at, ln, dip)

    def FadeAll(s, at, ln, dip):
        for v in s.v:
            if v.layer >= 0:
                s.FadeVoice(v, at, ln, dip)

    def CancelLayer(s, l):
        for v in s.v:
            if v.layer == l:
                s.Release(v, cancelled=True)

    def Release(s, v, cancelled=False):
        if not cancelled or v.start < s.now:
            s.done.append(dict(clip=v.clip, offset=v.offset, start=v.start, end=min(v.end, s.now + 0.05), cold=v.cold,
                               fade=(v.fadeStart, v.fadeLen, v.dip), layer=v.layer))
        v.layer = -1; v.clip = None; v.fadeStart = math.inf

    def Finish(s):
        s.finished.append(round(s.now, 3)); s.log.append((round(s.now, 3), "fin del tema"))
        s.track = None; s.outro = s.silent = s.pending = False; s.head = s.next = -1; s.playing = s.target = 0


def run(clips, tracks, events, dur, fps=60.0, jitter=0.0, seed=1):
    """events: (t, método, args...). ('pausa', s): el juego deja de correr LateUpdate s segundos (el DSP sigue)."""
    rng = np.random.default_rng(seed)
    log = []
    d = Director(clips, tracks, log)
    t = 0.0; ev = sorted(events, key=lambda e: e[0]); k = 0; paused_until = -1.0
    while t < dur:
        d.now = math.floor(t * SR / BLOCK) * BLOCK / SR
        d.frame += 1
        while k < len(ev) and ev[k][0] <= t:
            _, name, *args = ev[k]
            if name == "pausa":
                paused_until = t + args[0]
            else:
                getattr(d, name)(*args)
            log.append((round(d.now, 3), "evento " + name, *args)); k += 1
        if t >= paused_until:
            d.LateUpdate()
        t += (1.0 / fps) * (1 + jitter * rng.uniform(-1, 1))
    d.now = dur
    for v in d.v:
        if v.layer >= 0:
            d.Release(v)
    return d, log


class Audio:
    def __init__(s, check):
        s.dir = check; s.cache = {}

    def __call__(s, k):
        if k not in s.cache:
            s.cache[k] = np.load(os.path.join(s.dir, k + ".npy")).astype(np.float32)
        return s.cache[k]


def render(d, dur, audio, layer_filter=None, t0=0.0):
    """Las voces que sonaron entre t0 y dur (s), con su fundido de entrada y el de salida de VoiceRamp."""
    out = np.zeros((int((dur - t0) * SR) + SR, 2), np.float32)
    for r in d.done:
        if layer_filter is not None and not layer_filter(r["layer"]):
            continue
        a = max(r["start"], t0); e = min(r["end"], dur)
        n = int(round((e - a) * SR))
        if n <= 0:
            continue
        k0 = int(round((a - r["start"]) * SR))
        seg = audio(r["clip"])[r["offset"] + k0:r["offset"] + k0 + n].copy()
        n = len(seg)
        if r["cold"] and k0 < RAMP:
            ramp = np.minimum(1.0, (k0 + np.arange(n)) / RAMP).astype(np.float32)
            seg *= ramp[:, None]
        fs, fl, dip = r["fade"]
        if fs < math.inf:
            seg *= gain(a + np.arange(n) / SR, fs, fl, dip).astype(np.float32)[:, None]
        s0 = int(round((a - t0) * SR))
        m = min(n, len(out) - s0)
        out[s0:s0 + m] += seg[:m]
    return out[:int((dur - t0) * SR)]


SOS = butter(4, 7000, "highpass", fs=SR, output="sos")


def click_metric(y, t, win=0.003):
    """Energía de agudos (>7 kHz) en 3 ms alrededor de t contra el percentil 95 de las ventanas de ±0.6 s."""
    a = int((t - 0.6) * SR); b = int((t + 0.6) * SR)
    if a < 0 or b > len(y):
        return None
    h = sosfilt(SOS, y[a:b].mean(axis=1).astype(np.float64))
    w = int(win * SR); nw = len(h) // w
    e = (h[:nw * w].reshape(nw, w) ** 2).mean(axis=1)
    mid = int(0.6 * SR) // w
    loc = e[max(0, mid - 1):mid + 2].max()
    ref = np.percentile(np.concatenate([e[:mid - 3], e[mid + 3:]]), 95)
    return float(10 * np.log10((loc + 1e-15) / (ref + 1e-15)))


def rms_db(z):
    return float(20 * np.log10(np.sqrt((z.astype(np.float64).mean(axis=1) ** 2).mean()) + 1e-9))


SCEN = {
    "goro": ([(0.5, "Play", "boss_goro"), (95.0, "SetPhase", 2), (230.0, "End")], 240),
    "goro_barra_falsa": ([(0.5, "Play", "boss_goro"), (88.0, "Silence", 0.5, True), (91.0, "SetPhase", 2), (150.0, "End")], 160),
    "goro_barra_falsa_3s": ([(0.5, "Play", "boss_goro"), (88.0, "Silence", 0.5, True), (91.0, "SetPhase", 2, 3.0), (130.0, "End")], 140),
    "goro_reintento": ([(0.5, "Play", "boss_goro"), (30.0, "Stop", 1.0), (34.0, "Play", "boss_goro"), (60.0, "End")], 70),
    "lake": ([(0.5, "Play", "boss_lake"), (100.0, "SetPhase", 2), (170.0, "SetPhase", 3), (280.0, "End")], 290),
    "bamboo": ([(0.5, "Play", "boss_bamboo"), (95.0, "SetPhase", 2), (180.0, "SetPhase", 3), (250.0, "End")], 260),
    "final": ([(0.5, "Play", "boss_final"), (105.0, "SetPhase", 2), (205.0, "Silence", 0.4), (206.6, "SetPhase", 3),
               (262.0, "SetPhase", 4), (300.0, "End")], 310),
    "final_reintento_acto2": ([(0.5, "Play", "boss_final"), (0.5, "SetPhase", 2), (60.0, "End")], 70),
    "final_fase_antes_que_play": ([(0.5, "SetPhase", 2), (0.5, "Play", "boss_final"), (40.0, "End")], 50),
    "final_reintento_frame_siguiente": ([(0.5, "Play", "boss_final"), (0.52, "SetPhase", 2), (40.0, "End")], 50),
    "lake_pausa_editor": ([(0.5, "Play", "boss_lake"), (40.0, "pausa", 140.0), (200.0, "End")], 210),
    "ending": ([(0.5, "Play", "ending", 1.0)], 160),
}
LISTEN = ("goro", "goro_barra_falsa", "lake", "bamboo", "final", "final_reintento_acto2", "ending")


def main():
    plan, check, out = sys.argv[1:4]
    only = sys.argv[4:]
    clips, tracks = load_plan(plan)
    audio = Audio(check)
    os.makedirs(out, exist_ok=True)
    report, worst = {}, []
    for name, (events, dur) in SCEN.items():
        if only and name not in only:
            continue
        for fps, jit in ((60.0, 0.0), (24.0, 0.6)):
            d, log = run(clips, tracks, events, dur, fps, jit)
            y = render(d, dur, audio)
            if fps == 60.0 and name in LISTEN:
                wf.write(os.path.join(out, "preview_%s.wav" % name), SR, y)
            takes = []
            for r in d.done:
                st = r["start"]
                if st < 0.3 or st > dur - 0.7:
                    continue
                c = click_metric(y, st)
                a = int(st * SR); n = int(0.05 * SR)
                takes.append({"t": round(st, 3), "clip": r["clip"], "desde": r["offset"], "sola": r["cold"],
                              "tic_dB": None if c is None else round(c, 1),
                              "nivel": [round(rms_db(y[a - n:a]), 1), round(rms_db(y[a:a + n]), 1)]})
                if c is not None:
                    worst.append((round(c, 1), name, fps, round(st, 3), r["clip"], "sola" if r["cold"] else "sigue"))
            # cuánto suena lo anterior debajo de lo nuevo en el primer tiempo después de cada cambio
            under = []
            for b, L, what in d.commits:
                if b < 1 or b > dur - 1:
                    continue
                old = render(d, b + 0.25, audio, lambda l, L=L: l < L, b); new = render(d, b + 0.25, audio, lambda l, L=L: l >= L, b)
                under.append({"t": round(b, 3), "que": what, "anterior_dB": round(rms_db(old), 1), "nuevo_dB": round(rms_db(new), 1)})
            report["%s@%d" % (name, fps)] = {"log": log, "tomas": takes, "cambios": under,
                                             "pico_dBFS": round(float(20 * np.log10(np.abs(y).max() + 1e-9)), 2), "fin": d.finished}
    json.dump(report, open(os.path.join(out, "sim_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    worst.sort(reverse=True)
    print("peores 'tic' (dB sobre el p95 local de agudos):")
    for w in worst[:10]:
        print("  ", w)
    for k, v in report.items():
        if k.endswith("@60"):
            print("==", k, "pico", v["pico_dBFS"], "fin", v["fin"])
            for c in v["cambios"]:
                print("    cambio %8.3f %-26s anterior %6.1f dB  nuevo %6.1f dB" % (c["t"], c["que"], c["anterior_dB"], c["nuevo_dB"]))
            for l in v["log"]:
                if l[1] not in ("capa",) or True:
                    print("    ", l)


if __name__ == "__main__":
    main()
