"""Verificación offline de la avalancha de Gorō (Enemies/Bosses/GoroAvalanche.cs): justa y siempre a la vista.

    python Tools/Dev/goro_avalanche_check.py [--trials 20000] [--seed 1]

Reproduce la planificación de cada ola (PlanWave / LaneFor) con la arena real de la cumbre (BossArena r 15: arenaRadius
14, barrera a 15) y la cámara del juego en tres modos:
  * 'jefe'   : pelea sin fijar (CameraDirector.UpdateBaseParams): pitch 45, distancia 19 + 0.35 d (19-26) + 3.4 de
               GoroBoss.CameraExtraDistance durante la avalancha, foco 45 % hacia Gorō (Kaito a menos de 6 m del centro);
  * 'fijado' : distancia 18 + 0.5 separación (19-25) + 3.4, foco en Kaito con un 12 % hacia Gorō;
  * '52/24'  : la cámara de exploración (pitch 52, distancia 24) que pide el traspaso.
FOV 30 vertical, 16:9. Mide, para cada ola:
  1. que el arranque de cada roca esté adentro de la pantalla (con los márgenes del código) al armar la ola y también
     cuando cae (Kaito ya se corrió 1.5 m hacia un pasillo: la cámara lo sigue);
  2. el aviso: segundos entre que aparece el carril y el golpe a Kaito (>= MinWarning);
  3. que siempre exista un lugar a salvo alcanzable a la carrera (6.2 m/s, PlayerConfig.runSpeed) dentro del aviso con
     una reacción de 0.45 s (0.35 de una persona + latencia), adentro de la barrera y sin atravesar a Gorō;
  4. con el bot 'bueno' (AutoPilot: reacción N(0.28, 0.06), no ve el 10 %, se confunde el 5 %), cuántas rocas le pegan.
Sale con código 1 si algo falla.
"""
import argparse, math, random, sys

# --- números del código (GoroAvalanche.cs, GoroBoss.cs, PlayerConfig.cs, CameraDirector.cs, TellStyle)
MIN_WARNING, MIN_TELL, DROP = 1.35, 0.8, 0.5
GAP_MIN, GAP_MAX, PAD = 2.8, 3.6, 0.35
VIEW_TOP, VIEW_BOTTOM, VIEW_SIDE = 0.86, 0.08, 0.12
ARENA_R = 14.0                  # Boss.arenaRadius = BossArena.radius - 1
BARRIER = ARENA_R + 1.0
GORO_R = 1.0
RUN = 6.2
FOV, ASPECT = 30.0, 16 / 9
TICK_UNBLOCKABLE, LATENCY = 0.42, 0.05
DASH_I0, DASH_I1 = 0.02, 0.24


def rot(v, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return (v[0] * c + v[1] * s, -v[0] * s + v[1] * c)   # giro en Y de Unity (x, z)


def dot(a, b): return a[0] * b[0] + a[1] * b[1]
def add(a, b, k=1.0): return (a[0] + b[0] * k, a[1] + b[1] * k)
def norm(a): return math.hypot(a[0], a[1])


class Cam:
    """Cámara de Unity: Quaternion.Euler(pitch, 0, 0); pos = foco - forward * distancia."""

    def __init__(self, focus, pitch, dist):
        p = math.radians(pitch)
        self.f = (0.0, -math.sin(p), math.cos(p))       # forward (x, y, z)
        self.u = (0.0, math.cos(p), math.sin(p))
        self.r = (1.0, 0.0, 0.0)
        self.pos = (focus[0] - self.f[0] * dist, focus[1] - self.f[1] * dist, focus[2] - self.f[2] * dist)
        self.t = math.tan(math.radians(FOV) / 2)

    def viewport(self, x, y, z):
        d = (x - self.pos[0], y - self.pos[1], z - self.pos[2])
        cz = d[0] * self.f[0] + d[1] * self.f[1] + d[2] * self.f[2]
        cx = d[0] * self.r[0] + d[1] * self.r[1] + d[2] * self.r[2]
        cy = d[0] * self.u[0] + d[1] * self.u[1] + d[2] * self.u[2]
        if cz <= 0:
            return None
        return (0.5 + 0.5 * cx / (cz * self.t * ASPECT), 0.5 + 0.5 * cy / (cz * self.t))

    def in_view(self, q, r):
        v = self.viewport(q[0], r, q[1])
        return v is not None and VIEW_SIDE < v[0] < 1 - VIEW_SIDE and VIEW_BOTTOM < v[1] < VIEW_TOP

    def on_screen(self, q, r, m=0.03):
        """Adentro de la pantalla de verdad (el margen de planificación es solo un colchón)."""
        v = self.viewport(q[0], r, q[1])
        return v is not None and m < v[0] < 1 - m and m < v[1] < 1 - m

    @property
    def forward_flat(self):
        return (0.0, 1.0)


def camera(mode, k, g):
    d = norm(add(g, k, -1))
    if mode == "jefe":
        lean = min(0.45, 6 / d) if d > 0.01 else 0
        f = add(k, add(g, k, -1), lean)
        return Cam((f[0], 1.0, f[1]), 45, min(26, max(19, 19 + 0.35 * d)) + 3.4)
    if mode == "fijado":
        f = add(k, add(g, k, -1), 0.12)
        return Cam((f[0], 1.0, f[1]), 45, min(25, max(19, 18 + 0.5 * d)) + 3.4)
    return Cam((k[0], 1.0, k[1]), 52, 24)


def lane_for(bas, d, r, cam, g):
    """LaneFor: arranque lo más arriba posible adentro de la arena y de la pantalla; fin en la barrera o en Gorō."""
    rim = ARENA_R + 1 - r - 0.15
    if norm(bas) > rim:
        return None
    up = 0.0
    s = 0.25
    while s < 40:
        q = add(bas, d, -s)
        if norm(q) > rim or not cam.in_view(q, r):
            break
        up = s
        s += 0.25
    up = min(up, max(0.5, up - 1.8))       # StartBackoff
    if up < 0.5:
        return None
    down = 0.0
    s = 0.25
    while s < 40 and norm(add(bas, d, s)) <= rim:
        down = s
        s += 0.25
    S = add(bas, d, -up)
    length = up + down
    dg = add(g, S, -1)
    ga = dot(dg, d)
    side = (d[1], -d[0])
    gl = abs(dot(dg, side))
    hit = GORO_R + r
    on_boss = False
    if 0 < ga < length and gl < hit:
        stop = ga - math.sqrt(hit * hit - gl * gl)
        if stop < 2:
            return None
        length = stop
        on_boss = True
    if length < 3:
        return None
    return S, length, on_boss


def plan_wave(wave, k, g, cam, rng):
    down = (0.0, -1.0)                       # -cam.forward plano: hacia la cámara
    d = rot(down, rng.uniform(-14, 14))
    side = (d[1], -d[0])
    speed = 8.5 + 0.5 * wave
    r = rng.uniform(0.75, 0.9)
    w = 2 * (r + PAD)
    n = 2 if wave == 0 else 3
    sgn = -1 if rng.random() < 0.5 else 1
    a, b2 = w + rng.uniform(GAP_MIN, GAP_MAX), w + rng.uniform(GAP_MIN, GAP_MAX)
    lanes = []
    t_land = None
    for i in range(n):
        x = 0 if i == 0 else (sgn * a if i == 1 else -sgn * b2)
        L = lane_for(add(k, side, x), d, r, cam, g)
        if L is None:
            continue
        S, length, on_boss = L
        ahead = dot(add(k, S, -1), d)
        tell = max(MIN_TELL, MIN_WARNING - max(0.0, ahead - r - PAD) / speed)
        if t_land is None:
            t_land = tell
        land = max(t_land, tell) + 0.12 * len(lanes)
        lanes.append(dict(S=S, d=d, side=side, len=length, r=r, speed=speed, land=land, on_boss=on_boss, x=x))
    return lanes


def impact_time(L, p):
    """Cuándo pasa la roca por p (infinito si p no está en su carril): la misma cuenta que GoroAvalanche.Eta."""
    dd = add(p, L["S"], -1)
    along = dot(dd, L["d"])
    lat = abs(dot(dd, L["side"]))
    reach = L["r"] + PAD
    if lat > reach or along > L["len"] + reach or along < -reach:
        return None
    return L["land"] + max(0.0, along - reach) / L["speed"]


def threatened(lanes, p, t0, t1):
    """¿Alguna roca pasa por p entre t0 y t1 (con el ancho del cuerpo de la roca)?"""
    for L in lanes:
        t = impact_time(L, p)
        if t is None:
            continue
        span = 2 * (L["r"] + PAD) / L["speed"]
        if t <= t1 and t + span >= t0:
            return True
    return False


def safe_reachable(lanes, k, g, reaction):
    """¿Hay un punto a salvo que se alcanza corriendo antes del golpe? Busca en todas direcciones (8 rumbos, 0.25 m)."""
    first = min((impact_time(L, k) for L in lanes if impact_time(L, k) is not None), default=None)
    if first is None:
        return True, 9.0
    best = -9.0
    for h in range(16):
        dirv = rot((1.0, 0.0), h * 22.5)
        for step in range(1, 33):
            dist = step * 0.25
            q = add(k, dirv, dist)
            if norm(q) > BARRIER - PAD:
                break
            if norm(add(q, g, -1)) < GORO_R + PAD:
                break
            t_arrive = reaction + dist / RUN
            # el camino hasta q no puede cruzar un carril antes de que pase su roca (se mira cada 0.25 m)
            ok = True
            for s2 in range(1, step + 1):
                qq = add(k, dirv, s2 * 0.25)
                tq = reaction + s2 * 0.25 / RUN
                if threatened(lanes, qq, tq - 0.05, tq + 0.05):
                    ok = False
                    break
            if not ok:
                break
            if not threatened(lanes, q, t_arrive, 99):
                best = max(best, first - t_arrive)
                break
    return best >= 0, best


def bot_hits(lanes, k, rng):
    """El bot 'bueno' contra las rocas que le apuntan (no se mueve: AutoPilot camina hacia Gorō). Dash con i-frames."""
    hits = 0
    for L in lanes:
        t = impact_time(L, k)
        if t is None:
            continue
        if rng.random() < 0.10:          # no lo vio
            hits += 1
            continue
        if rng.random() < 0.05:          # se confundió: parry contra un imparable
            hits += 1
            continue
        rt = min(0.55, max(0.15, rng.gauss(0.28, 0.06)))
        press = t - TICK_UNBLOCKABLE - LATENCY + rt + LATENCY + 1 / 60
        if not (press + DASH_I0 <= t <= press + DASH_I1):
            hits += 1
    return hits


def run(trials, seed):
    rng = random.Random(seed)
    fails = []
    stats = {m: dict(waves=0, lanes=0, warn_min=9.0, see_min=9.0, margin_min=9.0, view_fail=0, view_land_fail=0, empty=0) for m in ("jefe", "fijado", "52/24")}
    bot_total, bot_waves, aimed = 0, 0, 0
    for _ in range(trials):
        mode = rng.choice(("jefe", "fijado", "52/24"))
        st = stats[mode]
        a = rng.uniform(0, 2 * math.pi)
        g = (math.cos(a) * rng.uniform(0, 11), math.sin(a) * rng.uniform(0, 11))
        for _try in range(20):
            b = rng.uniform(0, 2 * math.pi)
            k = (math.cos(b) * math.sqrt(rng.random()) * (BARRIER - PAD), math.sin(b) * math.sqrt(rng.random()) * (BARRIER - PAD))
            if norm(add(k, g, -1)) > GORO_R + PAD + 0.5:
                break
        for wave in range(3):
            cam = camera(mode, k, g)
            lanes = plan_wave(wave, k, g, cam, rng)
            st["waves"] += 1
            # MaxEmptyWaves: sin carril se reintenta 0.3 s después (Kaito se movió algo hacia el centro)
            retry = 0
            while not lanes and retry < 4:
                retry += 1
                k = add(k, k, -0.15)
                cam = camera(mode, k, g)
                lanes = plan_wave(wave, k, g, cam, rng)
            if not lanes:
                st["empty"] += 1
                continue
            st["lanes"] += len(lanes)
            for L in lanes:
                if not cam.in_view(L["S"], L["r"]):
                    st["view_fail"] += 1
                # cuando cae, Kaito ya se corrió 1.5 m de costado y la cámara lo siguió (sin el amortiguado: peor caso)
                k2 = add(k, L["side"], 1.5 if L["x"] <= 0 else -1.5)
                cam2 = camera(mode, k2, g)
                if not cam2.on_screen(L["S"], L["r"]):
                    st["view_land_fail"] += 1
                    if st["view_land_fail"] <= 3:
                        v = cam2.viewport(L["S"][0], L["r"], L["S"][1])
                        print(f"   al caer fuera de cuadro ({mode}): viewport {v[0]:.3f}, {v[1]:.3f}  Kaito {k}  Gorō {g}  carril x {L['x']:.1f}")
                t = impact_time(L, k)
                if t is not None:
                    aimed += 1
                    st["warn_min"] = min(st["warn_min"], t)
                    st["see_min"] = min(st["see_min"], t - (L["land"] - DROP))
            ok, margin = safe_reachable(lanes, k, g, 0.45)
            st["margin_min"] = min(st["margin_min"], margin)
            if not ok:
                fails.append((mode, wave, k, g, margin))
            bot_total += bot_hits(lanes, k, rng)
            bot_waves += 1
            # la ola siguiente se arma con Kaito donde quedó: el oráculo se mudó al pasillo más cercano
            k = add(k, lanes[0]["side"], rng.choice((-1, 1)) * (lanes[0]["r"] + PAD + 0.6))
            if norm(k) > BARRIER - PAD:
                k = add((0, 0), k, (BARRIER - PAD - 0.2) / norm(k))
            # Kaito no puede quedar adentro de Gorō (la cápsula lo empuja)
            off = add(k, g, -1)
            if norm(off) < GORO_R + PAD + 0.05:
                k = add(g, off if norm(off) > 1e-3 else (1.0, 0.0), (GORO_R + PAD + 0.1) / max(1e-3, norm(off)))
    ok = True
    for m, st in stats.items():
        print(f"[{m:6s}] olas {st['waves']}, carriles {st['lanes']} ({st['lanes'] / max(1, st['waves']):.2f}/ola), sin carril {st['empty']}, "
              f"arranque fuera de cuadro al planear {st['view_fail']} / al caer {st['view_land_fail']}, "
              f"aviso mínimo {st['warn_min']:.2f} s, roca a la vista antes del golpe >= {st['see_min']:.2f} s, "
              f"margen mínimo para ponerse a salvo {st['margin_min']:.2f} s")
        if st["view_fail"] or st["warn_min"] < MIN_WARNING - 1e-6:
            ok = False
    print(f"olas sin salida (el oráculo no llega a ningún lado a salvo): {len(fails)}")
    for f in fails[:5]:
        print("   ", f)
    print(f"bot 'bueno': {bot_total} rocas recibidas en {bot_waves} olas ({bot_total / max(1, bot_waves):.3f} por ola, "
          f"{bot_total / max(1, aimed) * 100:.1f} % de las que le apuntaban) -> ~{3 * bot_total / max(1, bot_waves):.2f} por avalancha")
    if fails:
        ok = False
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    sys.exit(0 if run(a.trials, a.seed) else 1)
