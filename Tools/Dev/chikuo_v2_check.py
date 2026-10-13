"""Modelo de diseño de Chikuō v2 (fase C4): los números de Docs/handoff/diseno/chikuo_v2.md, chequeados sin Unity.

Es el contrato en Python, no el port del código: cuando BambooMasterBoss esté reescrito y los clips existan, la
simulación de balance de verdad es sim_bamboo_master.py portado a esta pelea (con los tiempos del sidecar). Mientras
tanto esto dice si el diseño cierra: si los avisos se leen, si el latigazo se alcanza, si la cámara encuadra y cuánto
dura la pelea contra el bot de AutoPilot.

Partes (se pueden pedir de a una):
  --layout   las cañas de la arena (centro 124, 162): distancias entre ellas, al camino de la entrada (el arco de 116,
             148), al portal que aparece al ganar (114, 158), a la barrera, el centro libre y los rayos del estampado.
  --camera   la cámara de pelea de CameraDirector (sin fijar: foco 45 % hacia la raíz del jefe + 1 m, tope 6 m, distancia
             19 + 0.35 d entre 19 y 26, FOV 30 vertical, 16:9) con el perfil de Chikuō posado (pitch 45, CameraExtraDistance
             2.4, SetFocusBias hacia arriba 0.45 x la altura del posado): qué parte de la arena lo encuadra y si el cuerpo
             posado tapa a Kaito. La raíz del jefe posado está en la base de su caña (sección 8 del doc).
  --fair     avisos de cada golpe (anillo, '¡ya!', zona fija), escapes de los rojos corriendo y con el dash, vuelo de los
             dardos, ventanas del latigazo y de la caída del cielo (desde cuántos metros llega el bot).
  (siempre)  la pelea contra el bot ('bot on experto|bueno|promedio' de Input/AutoPilot.cs, con el gancho del latigazo
             del doc): 2D a 60 Hz, tres fases, muertes y reintentos desde la fase alcanzada. Dice cuánto dura (el intento
             ganador y el total con las muertes, que es lo que mide el PlayClock), las muertes, de dónde sale el daño, la
             densidad de amenazas, el tiempo muerto, y qué tan seguido sale cada hueco.

El bot (el de AutoPilot más los ganchos de la sección 13 del doc): reacciona al '¡ya!' con N(media, desvío) (bueno
0.28 / 0.06, promedio 0.32 / 0.08), a veces no lo ve o se confunde parry y dash; va hacia la raíz del jefe (BotTarget:
la base de su caña, o la de salida mientras salta) hasta 2.2 m y corta cada 0.32 s a menos de 2.6 m si no hay un anillo
del jefe a la vista y, con Chikuō posado, solo si las campanas están blancas (BotMayCut; de apurado, a veces igual);
cuando se encienden en blanco lo nota con la probabilidad de su nivel, va a la base (con el dash si está a más de 3.7 m
y tiene Espíritu) y corta (BotCutGoal); a veces va a la caña de destino de un salto. No usa las habilidades. Lo que no
modela: el rodeo de las cañas (cápsulas de 0.16 m), el stick relativo a la cámara, los señuelos de hojas (no cambian lo
que hace el bot) y la música.

--calib F pone el daño de Kaito en 1/F (el factor real/simulado de boss_sims/calibration.py): lo que dice son segundos
de juego si la pelea nueva tiene ese factor. El de esta pelea no está medido (el Chikuō viejo dio 1.42, Mizuchi 1.19,
Kokuyō 0.92, Gorō 0.71).

Uso: python Tools/Dev/chikuo_v2_check.py [--layout] [--camera] [--fair] [--nofight] [--runs 300] [--seed 7]
     [--skill bueno|promedio|experto|all] [--calib F] [--p JSON] [--trace S] [--knobs]
  --trace S   imprime lo que pasa en los primeros S s de una pelea (del nivel --skill)
  --knobs     la tabla de las perillas del balance (--factors 1.0,1.15,1.3,1.42 por defecto; se puede correr de a uno)
"""
import argparse, heapq, json, math, os, random, sys

if hasattr(sys.stdout, "reconfigure"):   # en Windows, con la salida a un archivo, los acentos y la ō rompían cp1252
    sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "boss_sims"))
import kaito as KB   # niveles del bot y el combo de Kaito (los mismos números que las otras simulaciones)

DT = 1.0 / 60.0

# =========================================================================== arena y cañas (contrato con c4/arena)
CENTER = (124.0, 162.0)            # world_plan.BOSSES 'ozeki'; el piso de la arena está a y = 2.0
BARRIER_R, KAITO_R_MAX = 15.0, 14.6
ARCH, PORTAL, SPAWN = (116.0, 148.0), (114.0, 158.0), (126.0, 166.0)


def pol(deg, r):
    return (r * math.cos(math.radians(deg)), r * math.sin(math.radians(deg)))


# id: rumbo (grados desde el este, antihorario), radio desde el centro, altura de la caña, posado recto y cargado
# (con su peso la caña se arquea y lo baja), fases en que se puede posar (1 y 3; en la 2 están inclinadas), se arquea
STALKS = {
    "N1": dict(b=100, r=5.5, top=7.5, perch_rest=4.4, perch=4.0, phases=(0, 2), bend=True),
    "N2": dict(b=100, r=10.5, top=7.5, perch_rest=4.0, perch=3.6, phases=(0, 2), bend=True),
    "O1": dict(b=180, r=5.5, top=7.5, perch_rest=4.4, perch=4.0, phases=(0, 2), bend=True),
    "O2": dict(b=180, r=10.5, top=8.5, perch_rest=4.8, perch=4.4, phases=(0, 2), bend=True),
    "E1": dict(b=330, r=5.5, top=7.5, perch_rest=4.4, perch=4.0, phases=(0, 2), bend=True),
    "E2": dict(b=330, r=10.5, top=8.5, perch_rest=4.8, perch=4.4, phases=(0, 2), bend=True),
    # la Caña Madre: nace en el centro al empezar la fase 3, gruesa (se arquea poco), nunca se quiebra
    "M": dict(b=0, r=0.0, top=10.0, perch_rest=5.0, perch=4.8, phases=(2,), bend=False),
}
for _s in STALKS.values():
    _s["pos"] = pol(_s["b"], _s["r"])

# =========================================================================== el diseño en números
P = dict(
    health=1900.0,                      # la vida de hoy (BambooMasterMoves.Config)
    gates=[1.0, 0.65, 0.40, 0.0],       # pisos de cada fase: la 1 es el 35 %, la 2 (el piso) el 25 %, la 3 el 40 %
    trans=[4.0, 5.0], heal=30.0, spirit_gift=30.0,
    # --- arriba ---------------------------------------------------------------------------------------------------
    breath=[(0.25, 0.45), None, (0.12, 0.25)],        # respiro posado entre acciones (s); nunca quieto (PerchIdle)
    react_dist=4.5,                                   # Kaito cerca de la base y él sin cargar: contesta
    react_mix=dict(colgado=0.30, barrido=0.20, picada=0.15, baston=0.15, salto=0.20),
    camp_dist=2.5, camp_time=0.6,                     # plantado al pie de la caña: barrido de caña
    max_on_stalk=[2, None, 2],                        # acciones por caña antes de saltar sí o sí
    dart_speed=[16.0, 16.0, 18.0], dart_lead=[0.5, 0.6, 0.8], dart_hit_r=0.6,
    whistle_speed=22.0, whistle_lane=1.0,
    leap_crouch=[0.22, 0.22, 0.14], leap_base=0.30, leap_per_m=0.035, leap_k=[1.0, 1.0, 0.85], leap_grab=0.20,
    leap_dest=[(4.5, 8.0), None, (4.0, 7.0)],
    catch_window=0.45,                                # caída del cielo: el corte a la caña de destino en los últimos 0.45 s
    pingpong=0.30,
    # --- los huecos ---------------------------------------------------------------------------------------------------
    # (vuelo hasta que se lo puede cortar, cuánto dura, tope de cortes, multiplicador, daño de la caída)
    revolcon=(0.55, 1.6, 3, 1.0, 12.0),
    estampado=(1.00, 2.2, 4, 1.2, 24.0),
    caida=(0.45, 3.0, 5, 1.25, 36.0),
    resbalon=(0.30, 1.0, 2, 1.0, 6.0),
    tropiezo=(0.0, 1.0, 2, 1.0, 0.0),
    afinado=(0.30, 2.5, 4, 1.2, 0.0),
    desafinado=(0.0, 1.4, 2, 1.0, 0.0),
    pies=(0.0, 1.6, 3, 1.0, 0.0),                     # pies enterrados: esquiva perfecta de la picada
    clavado=(0.0, 1.1, 2, 1.0, 0.0),                  # bastón clavado: esquiva perfecta de la barrida
    landing=(0.0, 0.45, 1, 1.0, 0.0),                 # aterriza de la picada
    stamp_range=6.0, stamp_angle=20.0, revolcon_m=3.2,
    getup=0.40,                                       # se levanta de un salto, invulnerable
    recoil=0.40, recoil_perfect=0.60,                 # retroceso del parry a un golpe suyo de piso
    # --- el piso (fase 2) ---------------------------------------------------------------------------------------------
    gap=(0.35, 0.6), ground_speed=5.5, backflip=2.5, backflip_inv=0.35, armor_mul=0.35, neutral_mul=0.6,
    open_p3=dict(revolcon=(0.55, 1.4, 3, 1.0, 12.0), estampado=(1.00, 2.0, 3, 1.2, 24.0)),
    pertiga_every=(8.0, 11.0), pertiga_loaded=(0.45, 1.40), qa_every=(18.0, 24.0), note_gap=0.44,
    # --- daño a Kaito (de 100) -----------------------------------------------------------------------------------------
    # el más liviano por golpe del juego ("pica como un mosquito"): lo que lo hace exigente es la densidad
    dmg=dict(dart=[2.5, 2.5, 2.5], whistle=[5.0, 5.0, 5.0], dive=[5.0, 5.0, 5.0], staff=[5.0, 5.0, 4.5],
             sweep=[4.0, 4.0, 4.0], revancha=[3.5, 3.5, 4.0], ground=[3.5, 3.5, 4.0], lowsweep=[4.5, 4.5, 5.0],
             sprout=[4.0, 4.0, 4.5], catapult=[6.5, 6.5, 6.5], tala=[5.5, 5.5, 5.5]),
    dmg_scale=1.0,
    # --- el bot de AutoPilot y el gancho del latigazo (Input/AutoPilot.cs, sección 13 del doc) -------------------------
    notice={"experto": 0.95, "bueno": 0.75, "promedio": 0.55},     # ve las campanas blancas de lejos y va
    notice_near=3.0,                                               # al pie: como cualquier aviso
    catch={"experto": 0.25, "bueno": 0.06, "promedio": 0.02},      # va a la caña de destino de un salto (a <= 7 m)
    hook_dash=3.7,
)
DEATH_AND_RETRY = 3.6 + 3.0       # como sim_bamboo_master: reaparece en el santuario y camina a la arena
REINTRO = 2.0
KAITO_DMG = 1.0                   # --calib
TICK = {"gold": 0.38, "red": 0.42}
RING = {"gold": 0.85, "red": 1.0}

# --------------------------------------------------------------------------- acciones desde la caña (s desde el arranque)
# releases: soplidos; loaded: (desde, hasta) con las campanas blancas (la caña cargada: se la corta y lo despide)
PERCH_ACTS = {
    "dardo": dict(dur=0.80, releases=[0.45], loaded=None),
    "dos_dardos": dict(dur=1.13, releases=[0.45, 0.80], loaded=None),
    "tres_notas": dict(dur=1.71, releases=[0.55, 0.93, 1.31], loaded=(0.10, 1.41)),
    "cuatro_notas": dict(dur=1.60, releases=[0.45, 0.73, 1.01, 1.29], loaded=(0.10, 1.34)),
    "silbador": dict(dur=1.40, releases=[0.90], loaded=(0.10, 1.00), whistle=True),
    "silbador3": dict(dur=1.30, releases=[0.80], loaded=(0.10, 0.90), whistle=True),
    "colgado": dict(dur=1.45, releases=[0.65, 0.95], loaded=(0.00, 1.25), hang=True),
    "risa": dict(dur=1.20, releases=[], loaded=(0.00, 1.20)),
    "risa_maestro": dict(dur=2.00, releases=[], loaded=(0.00, 2.00)),
    "ermitanos": dict(dur=0.60, releases=[], loaded=None),
}


def v2(a, b):
    return (b[0] - a[0], b[1] - a[1])


def norm(v):
    m = math.hypot(v[0], v[1])
    return (v[0] / m, v[1] / m) if m > 1e-6 else (0.0, 0.0)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def clamp_r(p, r):
    m = math.hypot(p[0], p[1])
    return p if m <= r else (p[0] * r / m, p[1] * r / m)


# =========================================================================== cámara (CameraDirector, sin fijar)
TAN15 = math.tan(math.radians(15.0))
CAM = dict(pitch=45.0, extra_perch=2.4, extra_ground=1.6, bias_k=0.45, fit_max=3.0)


def screen(cam, pitch, p):
    pr = math.radians(pitch)
    fwd = (0.0, -math.sin(pr), math.cos(pr))
    up = (0.0, math.cos(pr), math.sin(pr))
    r = [p[i] - cam[i] for i in range(3)]
    z = sum(r[i] * fwd[i] for i in range(3))
    y = sum(r[i] * up[i] for i in range(3))
    return 0.5 + 0.5 * y / (z * TAN15), 0.5 + 0.5 * r[0] / (z * TAN15 * 16 / 9), z


def camera_for(kaito, root, perch_h, extra, fit=0.0):
    ppos = (kaito[0], 1.0, kaito[1])
    b = (root[0], 1.0, root[1])
    d = math.hypot(b[0] - ppos[0], b[2] - ppos[2])
    k = min(0.45, 6.0 / d) if d > 0.01 else 0.0
    f = [ppos[i] + (b[i] - ppos[i]) * k for i in range(3)]
    f[1] += CAM["bias_k"] * perch_h
    D = min(26.0, max(19.0, 19.0 + 0.35 * d)) + extra + fit
    pr = math.radians(CAM["pitch"])
    return (f[0], f[1] + D * math.sin(pr), f[2] - D * math.cos(pr))


def framed(kaito, base, perch_h, top=1.55, fit=0.0):
    """Cabeza de Chikuō posado bajo el 92 % y los pies de Kaito sobre el 8 % (como LockTopV / LockBottomV), los dos
    dentro del 4-96 % de ancho; y si su cuerpo tapa a Kaito en pantalla (estando más cerca de la cámara)."""
    cam = camera_for(kaito, base, perch_h, CAM["extra_perch"], fit)
    hv, hu, hz = screen(cam, CAM["pitch"], (base[0], perch_h + top, base[1]))
    fv, fu, fz = screen(cam, CAM["pitch"], (base[0], perch_h - 0.2, base[1]))
    kv, ku, kz = screen(cam, CAM["pitch"], (kaito[0], 0.0, kaito[1]))
    kh, _, _ = screen(cam, CAM["pitch"], (kaito[0], 1.5, kaito[1]))
    inside = hv <= 0.92 and kv >= 0.08 and 0.04 <= hu <= 0.96 and 0.04 <= ku <= 0.96
    half = lambda w, z: w / (z * TAN15 * 16 / 9) * 0.5
    over = fz < kz and abs(hu - ku) < half(0.55, fz) + half(0.35, kz) and not (fv > kh or hv < kv)
    return inside, over


# =========================================================================== --layout
def path_dist(p):
    a = (ARCH[0] - CENTER[0], ARCH[1] - CENTER[1])
    d = (-a[0], -a[1])
    L = math.hypot(*d)
    u = (d[0] / L, d[1] / L)
    q = (p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(L, q[0] * u[0] + q[1] * u[1]))
    return math.hypot(q[0] - u[0] * t, q[1] - u[1] * t)


def stamp_target(base_id, frm, alive):
    """La caña que recibe el estampado: la más cercana a <= stamp_range de la base cortada dentro de ±stamp_angle de la
    línea Kaito -> caña (el anillo de la barrera no estampa)."""
    base = STALKS[base_id]["pos"]
    d = norm(v2(frm, base))
    best, bd = None, 1e9
    for sid in alive:
        if sid == base_id:
            continue
        q = STALKS[sid]["pos"]
        w = v2(base, q)
        L = math.hypot(*w)
        if L < 0.5 or L > P["stamp_range"]:
            continue
        ang = math.degrees(math.acos(max(-1.0, min(1.0, (w[0] * d[0] + w[1] * d[1]) / L))))
        if ang <= P["stamp_angle"] and L < bd:
            best, bd = sid, L
    return best


def layout_report():
    print("== cañas (mundo x, z; el piso a y 2.0) y distancias")
    loc = lambda p: (p[0] - CENTER[0], p[1] - CENTER[1])
    for sid, s in STALKS.items():
        p = s["pos"]
        print("  %-2s (%6.2f, %6.2f)  r %4.1f  caña %.1f m  posado %.1f recto / %.1f cargado  fases %s  a la barrera %.1f  al camino "
              "de la entrada %.1f  al portal %.1f  al spawn %.1f" % (
                  sid, p[0] + CENTER[0], p[1] + CENTER[1], s["r"], s["top"], s["perch_rest"], s["perch"],
                  "/".join(str(x + 1) for x in s["phases"]), BARRIER_R - s["r"], path_dist(p), dist(p, loc(PORTAL)),
                  dist(p, loc(SPAWN))))
    ids = list(STALKS)
    pairs = sorted(((dist(STALKS[a]["pos"], STALKS[b]["pos"]), a, b) for i, a in enumerate(ids) for b in ids[i + 1:]))
    print("  más cerca entre sí: " + ", ".join("%s-%s %.1f" % (a, b, d) for d, a, b in pairs[:6]))
    six = [s for s in ids if s != "M"]
    print("  centro libre en las fases 1 y 2: r %.1f; la entrada (arco) a %.1f m del centro" % (
        min(STALKS[s]["r"] for s in six) - 0.15, dist(loc(ARCH), (0, 0))))
    # estampado desde cada lado de cada caña (Kaito a 1.6 m de la base, 24 direcciones)
    for phase, alive in ((0, six), (2, ids)):
        rows = []
        for sid in alive:
            base = STALKS[sid]["pos"]
            hits = 0
            for k in range(24):
                a = 2 * math.pi * k / 24
                frm = (base[0] + 1.6 * math.cos(a), base[1] + 1.6 * math.sin(a))
                if math.hypot(*frm) > KAITO_R_MAX:
                    continue
                hits += stamp_target(sid, frm, alive) is not None
            rows.append("%s %d/24" % (sid, hits))
        print("  estampado desde un lado al azar (fase %d): %s" % (phase + 1, ", ".join(rows)))
    for sid in ("N1", "O1", "E1"):
        c = (0.0, 0.0)
        print("  desde el centro contra %s: %s; desde afuera de la de afuera (%s): %s" % (
            sid, stamp_target(sid, c, six), sid[0] + "2",
            stamp_target(sid[0] + "2", tuple(1.3 * x for x in STALKS[sid[0] + "2"]["pos"]), ids)))


def camera_report():
    print("== cámara: Chikuō posado (pitch %.0f, extra %.1f, foco +%.2f x posado)" % (CAM["pitch"], CAM["extra_perch"], CAM["bias_k"]))
    grid = [(x, z) for x in range(-13, 14) for z in range(-13, 14) if math.hypot(x, z) <= 13.5]
    for sid, s in STALKS.items():
        base, ph = s["pos"], s["perch"]
        n_in = sum(framed(k, base, ph)[0] for k in grid)
        n_fit = sum(framed(k, base, ph, fit=CAM["fit_max"])[0] for k in grid)
        n_over = sum(framed(k, base, ph)[1] for k in grid)
        near = [k for k in grid if 4.0 <= dist(k, base) <= 8.0]
        n_near = sum(framed(k, base, ph)[0] for k in near)
        print("  %-2s en cuadro desde el %3.0f %% de la arena (%3.0f %% con el auto-encuadre), desde el %3.0f %% de los puntos a 4-8 m; "
              "su cuerpo tapa a Kaito desde el %.1f %%" % (sid, 100 * n_in / len(grid), 100 * n_fit / len(grid),
                                                            100 * n_near / max(1, len(near)), 100 * n_over / len(grid)))
    cam = camera_for((0, 0), (0, 6), 4.0, CAM["extra_perch"])
    a, _, _ = screen(cam, CAM["pitch"], (0, 0, 0)); b, _, _ = screen(cam, CAM["pitch"], (0, 1.5, 0))
    c, _, _ = screen(cam, CAM["pitch"], (0, 4.0, 6)); d, _, _ = screen(cam, CAM["pitch"], (0, 5.55, 6))
    cam2 = camera_for((0, 0), (0, 4), 0.0, CAM["extra_ground"])
    e, _, _ = screen(cam2, CAM["pitch"], (0, 0, 4)); f, _, _ = screen(cam2, CAM["pitch"], (0, 2.45, 4))
    print("  alto en pantalla (1080 px): Kaito %.0f px; Chikuō agachado posado a 6 m %.0f px; parado en el piso a 4 m %.0f px" % (
        (b - a) * 1080, (d - c) * 1080, (f - e) * 1080))


# =========================================================================== --fair
def run_dist(t):
    """Metros que corre Kaito en t s desde quieto (aceleración 40 m/s² hasta 6.2 m/s)."""
    if t <= 0:
        return 0.0
    ta = 6.2 / 40.0
    return 20.0 * t * t if t <= ta else 20.0 * ta * ta + 6.2 * (t - ta)


def fair_report():
    print("== avisos y escapes (el bot reacciona al '¡ya!'; 'corre desde el anillo' = reacción 0.30 s al verlo aparecer)")
    reds = [  # nombre, radio o medio ancho a salir (m), anillo (s antes), fija (s antes)
        ("Picada de la Grulla (disco)", 1.6, 0.95, 0.45),
        ("Silbador (carril 1.0 m)", 0.5, 1.0, 0.25),
        ("Barrido de Caña (disco en la base)", 3.6, 0.85, 0.45),
        ("Catapulta (carril 1.8 m)", 0.9, 1.0, 0.75),
        ("Tala (carril 1.6 m)", 0.8, 1.0, 0.45),
        ("Barrida del Bastón (disco 2.6 m)", 2.6, 0.80, 0.45),
        ("Brote de la respuesta (disco 1.0 m)", 1.0, 0.85, 0.45),
        ("Picada de la pértiga (disco 1.4 m)", 1.4, 0.95, 0.45),
    ]
    print("  (Barrido de Caña: Kaito a 1.5 m de la base; Barrida del Bastón: a 1.2 m de él; el resto, en el centro)")
    print("  %-38s %6s %6s %6s %8s %8s %8s" % ("rojo", "anillo", "fija", "¡ya!", "salir", "corriendo", "margen"))
    for name, rad, ring, fix in reds:
        start = 1.5 if "base" in name else (1.2 if "Bastón" in name else 0.0)
        need = rad + 0.35 - start
        ran = run_dist(ring - 0.30)
        print("  %-38s %5.2fs %5.2fs %5.2fs %7.2fm %7.2fm %+7.2fm" % (name, ring, fix, TICK["red"], need, ran, ran - need))
    print("  el dash (6.5 m en 0.26 s, i-frames 0.02-0.24) sale de cualquiera; desde quieto al '¡ya!' corriendo no se sale de"
          " ninguno de radio > 0.5 m: la regla de siempre, rojo = dash o ya venir moviéndose.")
    print("\n== dardos (desde el posado a 4.0 m; vuelo = distancia 3D / velocidad)")
    for ph, name in ((0, "fase 1"), (2, "fase 3")):
        row = []
        for d in (3, 5, 7, 9, 11):
            fl = math.hypot(d, 4.0 - 1.0) / P["dart_speed"][ph]
            row.append("%d m %.2f s" % (d, fl))
        print("  %s (%.0f m/s): %s; el anillo a los pies de Kaito desde que levanta la flauta (>= 0.45 s antes del soplido)" % (
            name, P["dart_speed"][ph], ", ".join(row)))
    gaps = lambda k: PERCH_ACTS[k]["releases"][1] - PERCH_ACTS[k]["releases"][0]
    for name, gap in (("Dos Dardos", gaps("dos_dardos")), ("Tres Notas", gaps("tres_notas")), ("Cuatro Notas", gaps("cuatro_notas")),
                      ("Colgado", gaps("colgado")), ("Respuesta", P["note_gap"])):
        print("  %s: un dardo cada %.2f s; el parry siguiente se aprieta %.2f s después del choque (el ParrySuccess deja desde"
              " 0.06 s; con el '¡ya!' a 0.38 y una reacción de 0.28 se aprieta a 0.10 del golpe)" % (name, gap, gap - 0.10))
    print("  correr de costado: en un vuelo de 0.45 s Kaito se corre 2.8 m; con la puntería adelantada %.0f %% / %.0f %% de su"
          " velocidad (fases 1 / 3) le quedan %.1f / %.1f m de margen contra el radio de %.1f m" % (
              100 * P["dart_lead"][0], 100 * P["dart_lead"][2], 2.8 * (1 - P["dart_lead"][0]), 2.8 * (1 - P["dart_lead"][2]), P["dart_hit_r"]))
    print("\n== latigazo: desde cuántos metros de la base el corte entra en la ventana blanca")
    print("  (reacción al ver las campanas; el corte pega 0.133 s después de apretar a <= 2.6 m; el dash 6.5 m en 0.26 s)")
    acts = [("Tres Notas f1", PERCH_ACTS["tres_notas"]["loaded"]), ("Cuatro Notas f3", PERCH_ACTS["cuatro_notas"]["loaded"]),
            ("Silbador f1", PERCH_ACTS["silbador"]["loaded"]), ("Colgado", PERCH_ACTS["colgado"]["loaded"]),
            ("Risa", PERCH_ACTS["risa"]["loaded"]), ("Catapulta f3", (0.0, 1.0)), ("Pértiga f2", P["pertiga_loaded"]),
            ("Trepada", (0.0, 0.80)), ("Agarre al caer de un salto", (0.0, P["leap_grab"]))]
    for name, (a, b) in acts:
        row = []
        for rt in (0.30, 0.36):
            t = (b - 0.133) - (a + rt)
            run = 2.6 + run_dist(t)
            dash = 2.6 + 6.5 + run_dist(t - 0.26) if t > 0.26 else 2.6
            row.append("reacción %.2f: corriendo %4.1f m, con el dash %4.1f m" % (rt, run, dash))
        print("  %-28s blanco %.2f-%.2f s  %s" % (name, a, b, " | ".join(row)))
    print("\n== caída del cielo: corte a la caña de destino en los últimos %.2f s del vuelo" % P["catch_window"])
    for ph in (0, 2):
        for d in (5.0, 7.0, 9.0):
            fl = (P["leap_base"] + P["leap_per_m"] * d) * P["leap_k"][ph]
            total = P["leap_crouch"][ph] + fl
            row = []
            for k_d in (4.5, 6.0, 8.0):
                t = total - 0.30 - 0.133
                run_ok = 2.6 + run_dist(t) >= k_d
                dash_ok = 2.6 + 6.5 + run_dist(t - 0.26) >= k_d if t > 0.26 else False
                row.append("Kaito a %.1f m: %s" % (k_d, "corriendo" if run_ok else "con el dash" if dash_ok else "no llega"))
            print("  fase %d, salto de %.0f m (agachado + vuelo %.2f s): %s" % (ph + 1, d, total, ", ".join(row)))


# =========================================================================== la pelea
class Kaito:
    """Kaito manejado por el bot de AutoPilot, en el plano de la arena."""

    def __init__(self, rng, skill):
        self.rng, self.skill, self.sk = rng, skill, KB.SKILL[skill]
        self.hp, self.spirit, self.rage, self.rage_until = 100.0, 40.0, 0.0, -1.0
        self.pos = [-4.0, -9.5]
        self.vel = [0.0, 0.0]
        self.state, self.s0, self.s1 = "free", 0.0, 0.0       # estado, desde, hasta
        self.invuln_until = -1.0
        self.iframe = (-1.0, -1.0)
        self.dash_from, self.dash_dir, self.dash_len, self.tired_ready = None, (0.0, 0.0), 6.5, -1.0
        self.pending = []                 # (t, acción) del '¡ya!'
        self.combo_i, self.chain_until, self.next_tap, self.cuts = 0, -1.0, 0.0, []
        self.riposte_until = -1.0
        self.cut_from = self.cut_to = -1.0
        self.goal, self.goal_until, self.goal_dashed = None, -1.0, False
        self.stats = dict(parry=0, perfect=0, dodge=0, hit=0, graze=0, dmg=0.0, dash_tired=0)

    # ------------------------------------------------------------------ defensa
    def cue(self, t, T, kind):
        """Sonó el '¡ya!' de un golpe que le llega: aprieta un tiempo de reacción después (AutoPilot.OnCue)."""
        if self.rng.random() < self.sk["miss"]:
            return
        rt = min(0.55, max(0.15, self.rng.gauss(self.sk["mean"], self.sk["sd"]))) + 1.0 / 60.0
        dash = (kind == "red") != (self.rng.random() < self.sk["wrong"])
        self.pending.append((t + rt, "dash" if dash else "parry"))

    def can_defend(self, t):
        if self.state in ("hurt", "parry_recover", "dash"):
            return False
        if self.state == "parry":
            return False
        if self.state == "parry_success":
            return t - self.s0 > 0.06
        if self.state == "attack":
            return not (self.cut_from <= t <= self.cut_to)
        return True

    def press(self, t, act, toward):
        if act == "parry":
            self.state, self.s0, self.s1 = "parry", t, t + 0.24
            self.vel = [0.0, 0.0]
            self.cuts = []
        else:
            self.dash(t, toward)

    def dash(self, t, toward):
        tired = self.spirit < 15.0
        if tired:
            self.stats["dash_tired"] += 1
            if t < self.tired_ready:
                return False
            self.tired_ready = t + 0.8
        else:
            self.spirit -= 15.0
        d = norm(v2(self.pos, toward)) if toward is not None else (0.0, 1.0)
        if d == (0.0, 0.0):
            d = (0.0, 1.0)
        self.state, self.s0, self.s1 = "dash", t, t + 0.26 + 0.08
        self.dash_from, self.dash_dir, self.dash_len = tuple(self.pos), d, 3.0 if tired else 6.5
        self.iframe = (-1.0, -1.0) if tired else (t + 0.02, t + 0.24)
        self.cuts = []
        return True

    def resolve(self, t, kind, dmg, inside):
        """Le llega un golpe en t. kind: gold/red/dart. inside: ¿está en la zona? Devuelve el resultado."""
        if self.iframe[0] <= t <= self.iframe[1]:
            perfect = t - self.iframe[0] <= 0.16
            if kind == "red" or perfect:
                self.spirit = min(100.0, self.spirit + 15.0)
                self._rage(t, 10.0)
            self.stats["dodge"] += 1
            return "perfect_dodge" if perfect else "dodge"
        if not inside:
            return "miss"
        if t < self.invuln_until:
            return "ignored"
        if kind != "red" and self.state == "parry" and t - self.s0 <= 0.24:
            perfect = t - self.s0 <= 0.11
            self._parry(t, perfect)
            return "perfect" if perfect else "parry"
        if kind != "red" and self.state == "parry_success" and t - self.s0 < 0.18:
            self._parry(t, False)
            return "parry"
        if kind != "red" and self.state == "parry_recover" and t - self.s0 < 0.15:
            self._hurt(t, dmg * 0.35, graze=True)
            return "graze"
        self._hurt(t, dmg)
        return "hit"

    def _parry(self, t, perfect):
        self.stats["perfect" if perfect else "parry"] += 1
        self.spirit = min(100.0, self.spirit + (18.0 if perfect else 12.0))
        self._rage(t, 20.0 if perfect else 14.0)
        self.riposte_until = t + 0.7
        self.state, self.s0, self.s1 = "parry_success", t, t + 0.38

    def _hurt(self, t, dmg, graze=False):
        self.hp -= dmg
        self.stats["dmg"] += dmg
        self.stats["graze" if graze else "hit"] += 1
        if t >= self.rage_until:
            self.rage = max(0.0, self.rage - 40.0 * (0.35 if graze else 1.0))
        if not graze:
            self.state, self.s0, self.s1 = "hurt", t, t + (0.38 if dmg < 25 else 0.65)
            self.invuln_until = t + 0.7
            self.cuts, self.combo_i, self.chain_until = [], 0, -1.0
            self.vel = [0.0, 0.0]

    def _rage(self, t, v):
        if t < self.rage_until:
            self.rage_until = min(t + 9.0, self.rage_until + 0.6)
            return
        self.rage = min(100.0, self.rage + v)
        if self.rage >= 99.99:
            self.rage_until, self.rage = t + 9.0, 0.0

    # ------------------------------------------------------------------ ataque
    def try_cut(self, t):
        """El bot aprieta Attack (cada 0.32 s; 0.6 después del corte final)."""
        if t < self.next_tap or self.state not in ("free", "attack", "parry_success"):
            return False
        if self.combo_i > 0 and t > self.chain_until:
            self.combo_i = 0
        dmg, delay, length, cut = KB.COMBO[self.combo_i]
        self.cuts.append((t + delay, dmg, self.combo_i))
        self.state, self.s0, self.s1 = "attack", t, t + min(KB.TAP, length) * 0.9
        self.cut_from, self.cut_to = t + delay, t + cut
        self.chain_until = t + length + 0.25
        self.combo_i = (self.combo_i + 1) % 3
        self.next_tap = t + (KB.TAP if self.combo_i != 0 else 0.6)
        return True

    def mul(self, t):
        m = (1.45 if t < self.rage_until else 1.0) * KAITO_DMG
        if t < self.riposte_until:
            m *= 1.5
            self.riposte_until = -1.0
        return m

    def on_dealt(self, t):
        self.spirit = min(100.0, self.spirit + 3.0)
        self._rage(t, 4.0)

    # ------------------------------------------------------------------ cada cuadro
    def step(self, t, target):
        # estados que terminan
        if self.state == "parry" and t > self.s1:
            self.state, self.s0, self.s1 = "parry_recover", t, t + 0.28
        elif self.state in ("parry_success", "parry_recover", "hurt", "attack") and t >= self.s1:
            self.state = "free"
        elif self.state == "dash":
            u = min(1.0, (t - self.s0) / 0.26)
            if u < 1.0:
                s = self.dash_len * (1.6 * u - 0.6 * u * u)
                p = (self.dash_from[0] + self.dash_dir[0] * s, self.dash_from[1] + self.dash_dir[1] * s)
                self.pos = list(clamp_r(p, KAITO_R_MAX))
                self.vel = [self.dash_dir[0] * 6.2, self.dash_dir[1] * 6.2]
            if t >= self.s1:
                self.state = "free"
        # defensa pendiente
        for i in range(len(self.pending) - 1, -1, -1):
            tp, act = self.pending[i]
            if t < tp:
                continue
            if self.can_defend(t):
                self.pending.pop(i)
                self.press(t, act, target)
            elif t - tp > 0.2:      # el buffer de defensa de PlayerController
                self.pending.pop(i)
        # moverse hacia el objetivo (hasta 2.2 m: AutoPilot)
        if self.state == "free" or (self.state == "attack" and t >= self.s1):
            to = v2(self.pos, target)
            d = math.hypot(*to)
            want = (0.0, 0.0) if d <= 2.2 else norm(to)
            for i in range(2):
                dv = want[i] * 6.2 - self.vel[i]
                a = max(-40.0 * DT, min(40.0 * DT, dv))
                self.vel[i] += a
            sp = math.hypot(*self.vel)
            if sp > 6.2:
                self.vel = [self.vel[0] * 6.2 / sp, self.vel[1] * 6.2 / sp]
            self.pos = list(clamp_r((self.pos[0] + self.vel[0] * DT, self.pos[1] + self.vel[1] * DT), KAITO_R_MAX))
        elif self.state != "dash":
            self.vel = [0.0, 0.0]


class Fight:
    """Una pelea (un intento) contra el bot, desde la fase 'start' (0..2)."""

    def __init__(self, skill, rng, start, stats, log=None):
        self.rng, self.skill, self.st, self.log = rng, skill, stats, log
        self.k = Kaito(rng, skill)
        self.t = 0.0
        self.ph = start
        self.hp = P["health"] * P["gates"][start]
        self.ev, self.n, self.tok = [], 0, 0
        self.alive = {s: True for s in STALKS}         # no quebrada
        self.cracked = {s: False for s in STALKS}
        self.mode, self.stalk, self.root, self.gpos = "perch", "O1", STALKS["O1"]["pos"], (0.0, 0.0)
        self.act = self.loaded = self.open = self.leap = self.qa = None
        self.on_stalk, self.uncut = 0, 0
        self.taught = 0 if start == 0 else 9
        self.first_volley = start == 0
        self.near_since, self.cd = None, {}
        self.inv_until = -1.0
        self.visit_cut_ok = True                       # la vuelta del piso se puede cortar una vez por bajada
        self.next_pertiga = self.next_qa = 0.0
        self.tells, self.rings = [], []
        self.threats, self.phase_t, self.up_t, self.acts = [0, 0, 0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0, 0, 0]
        self.open_t = [0.0, 0.0, 0.0]
        self.dead_t = self.dead_run = self.dead_max = 0.0
        self.won = False
        self.enter_phase(start, initial=True)

    # ------------------------------------------------------------------ utilidades
    def S(self, key, inc=1.0):
        self.st[key] = self.st.get(key, 0.0) + inc
        if key.startswith("acc_") or key.startswith("combo_") or key in ("saltos", "garrochas"):
            self.acts[self.ph] += 1

    def set_mode(self, m):
        """Cambia lo que hace: los pasos agendados del flujo anterior (go) ya no salen."""
        self.mode = m
        self.tok += 1

    def go(self, t, fn, *args):
        """Paso del flujo de la IA: se cancela si cambia el modo o arranca otra acción."""
        self.n += 1
        heapq.heappush(self.ev, (t, self.n, self.tok, fn, args))

    def at(self, t, fn, *args):
        """Lo que ya salió (un dardo en vuelo, una zona fija): llega aunque él haga otra cosa."""
        self.n += 1
        heapq.heappush(self.ev, (t, self.n, None, fn, args))

    def dmg(self, key):
        return P["dmg"][key][self.ph] * P["dmg_scale"]

    def perchable(self, sid):
        return self.alive[sid] and self.ph in STALKS[sid]["phases"]

    def show(self, T, kind, own=True):
        """Un aviso a la vista hasta T (para el tiempo muerto y la densidad). 'own': el anillo es del jefe (sus golpes y
        zonas: InTell, que frena el ataque del bot); el de un dardo está a los pies de Kaito y no lo frena."""
        self.tells.append((T - RING[kind], T))
        if own:
            self.rings.append((T - RING[kind], T))

    def trace(self, msg):
        if self.log is not None:
            self.log.append("%7.2f  f%d  %-8s Kaito a %4.1f m, %3.0f vida, %3.0f Esp | %s" % (
                self.t, self.ph + 1, self.mode, dist(self.k.pos, self.root), self.k.hp, self.k.spirit, msg))

    def threatened(self):
        t = self.t
        return dist(self.k.pos, self.root) < 7.0 and any(a <= t <= b for a, b in self.rings[-6:])

    # ------------------------------------------------------------------ fases
    def enter_phase(self, ph, initial=False):
        self.ph = ph
        self.act = self.loaded = self.open = self.leap = self.qa = None
        if ph in (0, 2):
            self.stalk = "O1" if ph == 0 else "M"
            self.set_mode("perch")
            self.root = STALKS[self.stalk]["pos"]
            self.on_stalk = 0
            self.go(self.t + (0.6 if initial else 0.3), self.decide)
        else:
            self.set_mode("ground")
            self.gpos = self.root = (0.0, 0.0)
            self.next_pertiga = self.t + self.rng.uniform(4.0, 6.0)
            self.next_qa = self.t + self.rng.uniform(9.0, 12.0)
            self.go(self.t + 0.6, self.gdecide)
        self.trace("empieza la fase %d" % (ph + 1))

    def damage_boss(self, amount, src):
        if self.mode == "trans" or self.won:
            return
        floor = P["health"] * P["gates"][self.ph + 1]
        dealt = max(0.0, min(amount, self.hp - floor))
        self.S("dano_" + src, dealt)
        self.S("fase%d_%s" % (self.ph + 1, src), dealt)
        self.hp -= amount
        if self.hp <= floor + 0.5:
            self.hp = floor
            if self.ph == 2:
                self.won = True
                self.trace("vencido")
                return
            self.transition()

    def transition(self):
        self.trace("cambio de fase")
        self.set_mode("trans")
        self.act = self.loaded = self.open = self.leap = self.qa = None
        self.ev = []
        self.k.hp = min(100.0, self.k.hp + P["heal"])
        self.k.spirit = min(100.0, self.k.spirit + P["spirit_gift"])
        self.k.pending.clear()
        self.k.goal = None
        self.root = (0.0, 0.0)
        self.at(self.t + P["trans"][self.ph], self.enter_phase, self.ph + 1)

    # ------------------------------------------------------------------ arriba: decidir
    def cd_ok(self, key, cd):
        return self.t - self.cd.get(key, -99.0) >= cd

    def breath(self):
        lo, hi = P["breath"][self.ph]
        return self.rng.uniform(lo, hi)

    def decide(self):
        t, ph, sid = self.t, self.ph, self.stalk
        dK = dist(self.k.pos, self.root)
        self.act = None
        if not framed(tuple(self.k.pos), STALKS[sid]["pos"], STALKS[sid]["perch"])[0] and self.pick_dest() is not None:
            return self.start_leap()
        if self.taught < 3:
            self.taught += 1
            return self.perch_act(["dardo", "dardo", "tres_notas"][self.taught - 1])
        if self.near_since is not None and t - self.near_since >= P["camp_time"] and self.cd_ok("barrido", 5.0):
            self.cd["barrido"] = t
            return self.stalk_sweep()
        if dK <= P["react_dist"]:
            # Kaito debajo y él sin cargar: se cuelga a soplarle de cerca (cargado), barre con la caña, baja a pegarle o se va
            r = self.rng.random() * sum(P["react_mix"].values())
            for name, w in P["react_mix"].items():
                r -= w
                if r <= 0:
                    break
            if name == "barrido" and dK <= 3.4 and self.cd_ok("barrido", 3.0):
                self.cd["barrido"] = t
                return self.stalk_sweep()
            if name == "picada" and self.cd_ok("picada", 3.0):
                self.cd["picada"] = t
                return self.dive()
            if name == "baston" and self.cd_ok("baston", 3.0):
                self.cd["baston"] = t
                return self.staff_drop()
            if name == "salto" and self.pick_dest() is not None:
                return self.start_leap()
            return self.perch_act("colgado")
        if self.uncut >= 3:
            self.uncut = 0
            self.S("risa_maestro")
            return self.perch_act("risa_maestro")
        if self.act_laugh:
            self.act_laugh = False
            self.S("risa")
            return self.perch_act("risa")
        cap = 1 if (ph == 2 and self.hp <= 0.12 * P["health"]) else P["max_on_stalk"][ph]
        if self.on_stalk >= cap and self.pick_dest() is not None:
            return self.start_leap()
        hp01 = self.hp / P["health"]
        opts = [("dardo", 1.0), ("dos_dardos", 0.8)]
        if dK >= 3.5:
            opts.append(("cuatro_notas" if ph == 2 else "tres_notas", 1.2))
        if hp01 <= 0.85 and dK >= 5.0:
            opts.append(("silbador3" if ph == 2 else "silbador", 0.6))
        if dK <= 7.0:
            opts.append(("colgado", 0.6))
        if self.on_stalk >= 1:
            opts.append(("leap", 0.6))
        if self.cd_ok("picada", 5.0):
            opts.append(("picada", 0.4))
        if self.cd_ok("baston", 5.0):
            opts.append(("baston", 0.3))
        if ph == 2:
            if dK >= 5.0 and self.cd_ok("catapulta", 8.0):
                opts.append(("catapulta", 0.6))
            if self.tala_target() is not None and self.cd_ok("tala", 7.0):
                opts.append(("tala", 0.9))
            if self.cd_ok("ermitanos", 22.0):
                opts.append(("ermitanos", 0.3))
        r = self.rng.random() * sum(w for _, w in opts)
        for name, w in opts:
            r -= w
            if r <= 0:
                break
        if name == "leap":
            return self.start_leap() if self.pick_dest() is not None else self.perch_act("dardo")
        if name in ("picada", "baston", "catapulta", "tala", "ermitanos"):
            self.cd[name] = t
        if name == "picada":
            return self.dive()
        if name == "baston":
            return self.staff_drop()
        if name == "catapulta":
            return self.catapult()
        if name == "tala":
            return self.tala()
        return self.perch_act(name)

    act_laugh = False
    last_open = None

    def after_perch(self):
        self.act = None
        self.go(self.t + self.breath(), self.decide)

    # ------------------------------------------------------------------ arriba: acciones
    def perch_act(self, name):
        a = dict(PERCH_ACTS[name])
        t0 = self.t
        if name == "tres_notas" and self.first_volley:
            # la primera ráfaga: una inspiración exagerada más (enseña las campanas blancas)
            self.first_volley = False
            a["loaded"] = (a["loaded"][0], a["loaded"][1] + 0.6)
            a["releases"] = [r + 0.6 for r in a["releases"]]
            a["dur"] += 0.6
        a["name"], a["t0"] = name, t0
        self.set_mode("perch")
        self.act = a
        self.on_stalk += 1
        self.S("acc_" + name)
        self.trace(name)
        if a["loaded"]:
            self.set_loaded(t0 + a["loaded"][0], t0 + a["loaded"][1], self.stalk)
        else:
            self.loaded = None
        for r in a["releases"]:
            whistle, hang = a.get("whistle", False), a.get("hang", False)
            fl = self.flight(whistle, hang)
            lead = TICK["red" if whistle else "gold"]
            self.go(max(t0, t0 + r + fl - lead), self.dart_cue, t0 + r, whistle, hang)
            self.go(t0 + r, self.release, whistle, hang, name)
        self.go(t0 + a["dur"], self.end_act, bool(a["loaded"]))

    def end_act(self, was_loaded):
        if was_loaded:
            self.uncut += 1
        self.loaded = None
        self.after_perch()

    def set_loaded(self, t0, t1, sid):
        self.loaded = (t0, t1, sid)
        self.S("cargas")
        self.tells.append((t0, t1))
        # el gancho del bot: ve las campanas blancas y va a la base. Al pie de la caña (a 3 m o menos) el brillo está ahí
        # nomás: lo ve como cualquier aviso (no lo ve el 10 / 15 %); de lejos, con la probabilidad de su nivel
        base = STALKS[sid]["pos"] if sid else self.gpos
        near = dist(self.k.pos, base) <= P["notice_near"]
        if self.rng.random() < ((1.0 - KB.SKILL[self.skill]["miss"]) if near else P["notice"][self.skill]):
            rt = max(0.15, self.rng.gauss(KB.SKILL[self.skill]["mean"] + 0.02, KB.SKILL[self.skill]["sd"]))
            self.go(t0 + rt, self.hook_on, self.loaded)

    def hook_on(self, ld):
        if self.loaded is not ld:
            return
        goal = STALKS[ld[2]]["pos"] if ld[2] else self.gpos
        self.k.goal, self.k.goal_until, self.k.goal_dashed = goal, ld[1], False

    def flight(self, whistle, hang):
        h = STALKS[self.stalk]["perch"] - (1.6 if hang else 0.0) + 0.8
        sp = P["whistle_speed"] if whistle else P["dart_speed"][self.ph]
        return math.hypot(dist(self.k.pos, self.root), h - 1.0) / sp

    def dart_cue(self, t_rel, whistle, hang):
        """El '¡ya!' del dardo por salir: la ETA cuenta lo que falta para el soplido más el vuelo (honesta)."""
        T = max(self.t, t_rel) + self.flight(whistle, hang)
        self.k.cue(self.t, T, "red" if whistle else "gold")

    def release(self, whistle, hang, name):
        """Sopla un dardo (o el silbador) hacia donde va a estar Kaito."""
        t, k, ph = self.t, self.k, self.ph
        h = STALKS[self.stalk]["perch"] - (1.6 if hang else 0.0) + 0.8
        base = self.root
        sp = P["whistle_speed"] if whistle else P["dart_speed"][ph]
        fl = math.hypot(dist(k.pos, base), h - 1.0) / sp
        lead = 0.0 if whistle else P["dart_lead"][ph]
        aim = (k.pos[0] + k.vel[0] * fl * lead, k.pos[1] + k.vel[1] * fl * lead)
        T = t + fl
        if whistle:
            # el carril siguió a Kaito hasta 0.25 s antes de soplar: 1.0 m de ancho desde la base
            zone = ("lane", (base, norm(v2(base, aim))), P["whistle_lane"] * 0.5 + 0.35)
            self.show(T, "red", own=False)
            self.at(T, self.strike_kaito, "red", self.dmg("whistle"), zone, name)
        else:
            zone = ("disc", aim, P["dart_hit_r"])
            self.show(T, "gold", own=False)
            self.at(T, self.strike_kaito, "dart", self.dmg("dart"), zone, name)

    def inside(self, zone):
        kind, a, b = zone
        p = tuple(self.k.pos)
        if kind == "disc":
            return dist(p, a) <= b
        base, d = a[0], a[1]
        length = a[2] if len(a) > 2 else 16.0
        w = v2(base, p)
        along = w[0] * d[0] + w[1] * d[1]
        return -0.5 <= along <= length and abs(w[0] * d[1] - w[1] * d[0]) <= b

    def cue_if(self, T, kind, zone):
        # AutoPilot.OnCue: 'mine' si el golpe le llega (el anillo lo alcanza, o la ETA del proyectil a Kaito)
        z = ("disc", zone[1], zone[2] + 0.5) if zone[0] == "disc" else zone
        if self.inside(z):
            self.k.cue(self.t, T, kind)

    def strike_kaito(self, kind, dmg, zone, src):
        if self.mode == "trans" or self.won:
            return None
        self.threats[self.ph] += 1
        r = self.k.resolve(self.t, kind, dmg, self.inside(zone))
        self.S("res_" + r)
        if r in ("hit", "graze"):
            self.S("golpe_" + src)
            self.S("dano_kaito_" + src, dmg if r == "hit" else dmg * 0.35)
            self.S("kfase%d_%s" % (self.ph + 1, src), dmg if r == "hit" else dmg * 0.35)
            self.trace("le pega a Kaito: %s (%.1f)" % (src, dmg))
            if self.mode == "perch" and kind == "dart" and self.rng.random() < 0.3:
                self.act_laugh = True
        return r

    # ---- saltos
    def pick_dest(self, from_ground=False):
        lo, hi = P["leap_dest"][self.ph] or (4.5, 8.0)
        k = tuple(self.k.pos)
        cands = []
        for sid in STALKS:
            if (sid == self.stalk and not from_ground) or not self.perchable(sid):
                continue
            q = STALKS[sid]["pos"]
            dk = dist(q, k)
            south = 2.5 <= dk <= 6.5 and v2(k, q)[1] / dk < -math.cos(math.radians(30))
            if dk < 2.5 or south or not framed(k, q, STALKS[sid]["perch"])[0]:
                continue
            score = 0.0 if lo <= dk <= hi else min(abs(dk - lo), abs(dk - hi))
            cands.append((score + self.rng.random() * 0.5, sid))
        if not cands:
            return None
        cands.sort()
        return cands[0][1]

    def start_leap(self, chained=False, from_ground=False, vault=False):
        dest = self.pick_dest(from_ground)
        if dest is None:
            if from_ground:
                return self.gdecide_any()
            return self.dive()
        t, ph = self.t, self.ph
        src = None if from_ground else STALKS[self.stalk]["pos"]
        start = self.gpos if from_ground else src
        c = 0.0 if chained or from_ground else P["leap_crouch"][ph]
        d = dist(start, STALKS[dest]["pos"])
        fl = (P["leap_base"] + P["leap_per_m"] * d) * P["leap_k"][ph]
        if vault:
            fl = max(fl, 0.9)
        self.set_mode("vault" if vault else "leap")
        self.act, self.loaded = None, None
        self.leap = dict(src=start, dest=dest, take=t + c, grab=t + c + fl, vault=vault)
        self.S("garrochas" if vault else "saltos")
        self.tells.append((t, t + c + fl))
        self.trace(("garrocha a " if vault else "salta a ") + dest)
        # el gancho de la caída del cielo: a veces el bot va a la caña de destino
        if not vault and dist(self.k.pos, STALKS[dest]["pos"]) <= 7.0 and self.rng.random() < P["catch"][self.skill]:
            rt = max(0.15, self.rng.gauss(KB.SKILL[self.skill]["mean"], KB.SKILL[self.skill]["sd"]))
            self.go(t + rt, self.hook_catch, self.leap)
        self.go(t + c + fl, self.grab, self.leap)

    def hook_catch(self, lp):
        if self.leap is lp:
            self.k.goal, self.k.goal_until, self.k.goal_dashed = STALKS[lp["dest"]]["pos"], lp["grab"], False

    def grab(self, lp):
        self.set_mode("perch")
        self.stalk = lp["dest"]
        self.root = STALKS[self.stalk]["pos"]
        self.leap = None
        self.on_stalk = 0
        t = self.t
        self.act = dict(name="agarre", t0=t)
        if lp.get("vault"):
            self.loaded = None
        else:
            self.set_loaded(t, t + P["leap_grab"], self.stalk)
        if self.ph == 2 and self.rng.random() < P["pingpong"] and self.pick_dest() is not None:
            self.go(t + P["leap_grab"], self.pingpong)
        else:
            self.go(t + P["leap_grab"], self.after_grab)

    def after_grab(self):
        # recién posado arranca enseguida (sin respiro): el salto ya fue la pausa
        self.loaded = None
        self.act = None
        self.decide()

    def pingpong(self):
        self.loaded = None
        self.S("ping_pong")
        self.start_leap(chained=True)

    # ---- al piso y de vuelta
    def dive(self):
        """Picada de la Grulla: la patada voladora roja sobre donde está Kaito."""
        t = self.t
        self.set_mode("dive")
        self.act, self.loaded = dict(name="picada", t0=t), None
        self.S("acc_picada")
        self.trace("picada")
        T = t + 0.95
        self.show(T, "red")
        self.go(t + 0.50, self.dive_fix, T, "picada", 1.6, "dive")

    def dive_fix(self, T, src, radius, key):
        spot = tuple(self.k.pos)
        zone = ("disc", spot, radius + 0.35)
        self.at(T - TICK["red"], self.cue_if, T, "red", zone)
        self.go(T, self.dive_land, zone, spot, src, key)

    def dive_land(self, zone, spot, src, key):
        r = self.strike_kaito("red", self.dmg(key), zone, src)
        self.gpos = self.root = spot
        self.set_mode("ground")
        self.visit_cut_ok = True
        if r == "perfect_dodge":
            return self.opening("pies", spot, self.t)
        self.opening("landing", spot, self.t, then=self.ground_after_landing)

    def staff_drop(self):
        """Bastón que Cae: cae al lado de Kaito con un bastonazo dorado."""
        t = self.t
        self.set_mode("drop")
        self.act, self.loaded = dict(name="baston", t0=t), None
        self.S("acc_baston")
        self.trace("bastón que cae")
        T = t + 0.85
        self.show(T, "gold")
        self.go(t + 0.40, self.drop_aim, T)

    def drop_aim(self, T):
        # elige dónde cae (a 1.6 m de Kaito, de su lado) 0.45 s antes del golpe; el '¡ya!' a los 0.38
        k = tuple(self.k.pos)
        d = norm(v2(k, self.root))
        spot = clamp_r((k[0] + d[0] * 1.6, k[1] + d[1] * 1.6), 13.0)
        zone = ("disc", spot, 2.4 + 0.35)
        self.at(T - TICK["gold"], self.cue_if, T, "gold", zone)
        self.go(T - 0.20, self.drop_land, T, spot, zone)

    def drop_land(self, T, spot, zone):
        self.gpos = self.root = spot
        self.visit_cut_ok = True
        self.set_mode("gstrike")
        self.act = dict(name="baston", t0=self.t, T=T)
        self.go(T, self.gstrike_hit, "gold", "staff", zone, "baston", True, self.return_up)

    def gstrike(self, key, windup, src, last, then, kind="gold", radius=2.4):
        """Un golpe en el piso (dorado salvo la barrida): armadura en la carga, el anillo, el '¡ya!'."""
        t = self.t
        T = t + windup
        self.set_mode("gstrike")
        self.act = dict(name=src, t0=t, T=T)
        self.show(T, kind)
        zone = ("disc", self.gpos, radius + 0.35)
        self.at(T - TICK[kind], self.cue_if, T, kind, zone)
        self.go(T, self.gstrike_hit, kind, key, zone, src, last, then)

    def gstrike_hit(self, kind, key, zone, src, last, then):
        r = self.strike_kaito("red" if kind == "red" else "gold", self.dmg(key), zone, src)
        if r in ("parry", "perfect") and last and src != "revancha":
            # el último golpe de una tanda, desviado: queda abierto (el contraataque de Kaito)
            self.S("contra")
            self.visit_cut_ok = False
            dur = P["recoil_perfect"] if r == "perfect" else P["recoil"]
            return self.opening("contra", self.gpos, self.t, then=then, dur=dur, cuts=3 if r == "perfect" else 2)
        if r == "perfect_dodge" and key == "lowsweep":
            return self.opening("clavado", self.gpos, self.t, then=self.gdecide if self.ph == 1 else self.return_up)
        self.set_mode("ground")
        self.go(self.t + (0.05 if not last else 0.35), then)

    def stalk_sweep(self, wobble=0.0):
        """Barrido de Caña: se cuelga del costado y la caña barre un disco rojo de 3.6 m alrededor de la base."""
        t = self.t + wobble
        self.set_mode("perch")
        self.act, self.loaded = dict(name="barrido", t0=t), None
        self.S("acc_barrido")
        self.trace("barrido de caña")
        T = t + 0.85
        self.show(T, "red")
        zone = ("disc", self.root, 3.6 + 0.35)
        self.at(T - TICK["red"], self.cue_if, T, "red", zone)
        self.at(T, self.strike_kaito, "red", self.dmg("sweep"), zone, "barrido")
        self.go(t + 1.35, self.end_act, False)

    def catapult(self):
        """Catapulta (fase 3): tensa la caña como un arco (cargada) y sale con la patada voladora por un carril rojo."""
        t = self.t
        self.set_mode("perch")
        self.act = dict(name="catapulta", t0=t)
        self.S("acc_catapulta")
        self.trace("catapulta")
        self.set_loaded(t, t + 1.0, self.stalk)
        T = t + 1.5
        self.show(T, "red")
        self.go(t + 0.75, self.catapult_fix, T)

    def catapult_fix(self, T):
        base = self.root
        dk = dist(self.k.pos, base)
        d = norm(v2(base, tuple(self.k.pos)))
        zone = ("lane", (base, d), 0.9 + 0.35)
        self.at(T - TICK["red"], self.cue_if, T, "red", zone)
        spot = clamp_r((base[0] + d[0] * (dk + 2.0), base[1] + d[1] * (dk + 2.0)), 13.0)
        self.go(self.t + 0.25, self.catapult_go, zone, spot, T)

    def catapult_go(self, zone, spot, T):
        self.loaded = None
        self.set_mode("dive")
        self.go(T, self.dive_land, zone, spot, "catapulta", "catapult")

    def tala_target(self):
        # una caña rajada (no la suya ni la Madre) que alcance a Kaito al caer: él a menos del largo de la caña
        c = [s for s in STALKS if self.cracked[s] and self.alive[s] and s not in (self.stalk, "M")
             and dist(STALKS[s]["pos"], self.k.pos) <= STALKS[s]["top"] - 1.0]
        return min(c, key=lambda s: dist(STALKS[s]["pos"], self.k.pos)) if c else None

    def tala(self):
        """Tala (fase 3): le clava el silbador en la rajadura a una caña rajada y la caña cae hacia Kaito (carril rojo
        de su largo); queda el tocón. La rajadura se la hizo Kaito: sus latigazos se vuelven las armas del viejo."""
        sid = self.tala_target()
        if sid is None:
            return self.perch_act("dardo")
        t = self.t
        self.set_mode("perch")
        self.act, self.loaded = dict(name="tala", t0=t), None
        self.S("acc_tala")
        self.trace("tala " + sid)
        T = t + 1.1
        self.show(T, "red")
        self.go(T - 0.45, self.tala_fix, sid, T)
        self.go(t + 1.6, self.end_act, False)

    def tala_fix(self, sid, T):
        base = STALKS[sid]["pos"]
        zone = ("lane", (base, norm(v2(base, tuple(self.k.pos))), STALKS[sid]["top"]), 0.8 + 0.35)
        self.at(T - TICK["red"], self.cue_if, T, "red", zone)
        self.at(T, self.strike_kaito, "red", self.dmg("tala"), zone, "tala")
        self.alive[sid] = False
        self.S("canas_taladas")

    def ground_after_landing(self):
        """Aterrizó de la picada o de la catapulta: un bastonazo rápido si Kaito está encima, y vuelve arriba."""
        if self.ph == 1:
            return self.gdecide()
        if dist(self.k.pos, self.gpos) <= 3.0 and self.rng.random() < 0.5:
            return self.gstrike("revancha", 0.55, "revancha", last=True, then=self.return_up)
        self.return_up()

    def return_up(self):
        """Vuelve a una caña: trepa si tiene una al lado (cargada: se la corta y resbala) o salta agachándose (cortarle el
        agachado lo hace tropezar); una vez por bajada. Después de un hueco vuelve con la garrocha, que no se corta."""
        if self.ph == 1:
            return self.gdecide()
        t = self.t
        if not self.visit_cut_ok:
            return self.start_leap(from_ground=True, vault=True)
        self.visit_cut_ok = False
        near = [s for s in STALKS if self.perchable(s) and dist(STALKS[s]["pos"], self.gpos) <= 1.5]
        if near:
            sid = near[0]
            self.set_mode("climb")
            self.stalk, self.root = sid, STALKS[sid]["pos"]
            self.S("trepadas")
            self.trace("trepa " + sid)
            self.set_loaded(t, t + 0.80, sid)
            return self.go(t + 0.80, self.climb_done)
        self.set_mode("crouch")
        self.trace("se agacha para saltar")
        self.go(t + 0.30, self.start_leap, False, True)

    def climb_done(self):
        self.set_mode("perch")
        self.loaded = None
        self.on_stalk = 0
        self.go(self.t + self.breath(), self.decide)

    def gdecide_any(self):
        # sin caña a la que volver (fase 3 con el bosque talado o Kaito debajo de la que queda): pelea en el piso con lo
        # de la fase 2 (tandas, la pértiga, el soplo) hasta que tenga una caña libre
        self.gdecide()

    # ------------------------------------------------------------------ los huecos
    def opening(self, kind, pos, t_cut, then="getup", dur=None, cuts=None):
        table = P["open_p3"] if self.ph == 2 and kind in P["open_p3"] else P
        fly, d0, cap, mul, fall = table[kind] if kind in table else (0.0, dur, cuts, 1.0, 0.0)
        dur = d0 if dur is None else dur
        cap = cap if cuts is None else cuts
        self.set_mode("open")
        self.loaded = self.act = None
        self.k.goal = None
        self.gpos = self.root = pos
        o = dict(kind=kind, t0=t_cut + fly, t1=t_cut + fly + dur, cuts=cap, mul=mul)
        self.open = o
        self.last_open = kind
        self.S("hueco_" + kind)
        self.trace("hueco: %s (%.1f s, %d cortes)" % (kind, dur, cap))
        self.tells.append((t_cut, o["t1"]))
        if fall > 0:
            self.go(t_cut + fly, self.damage_boss, fall * KAITO_DMG, "caida_" + kind)
        nxt = self.getup if then == "getup" else then
        self.go(o["t1"], self.close_open, nxt)

    def close_open(self, then):
        self.open = None
        self.set_mode("ground")
        then()

    def getup(self, kind=None):
        """Se levanta de un salto (invulnerable); en la fase 3, después de los huecos grandes (estampado, caída del
        cielo), contesta con un bastonazo dorado antes de volver arriba."""
        self.inv_until = self.t + P["getup"]
        self.visit_cut_ok = False
        if self.ph == 1:
            return self.go(self.t + P["getup"], self.gdecide)
        if self.ph == 2 and self.last_open in ("estampado", "caida"):
            return self.go(self.t + P["getup"], self.revancha)
        self.go(self.t + P["getup"], self.return_up)

    def revancha(self):
        if dist(self.k.pos, self.gpos) <= 3.0:
            return self.gstrike("revancha", 0.60, "revancha", last=True, then=self.return_up)
        self.return_up()

    def whip(self, frm, sid, how):
        """El corte a la caña cargada: la caña lo despide por la línea Kaito -> caña."""
        t = self.t
        base = STALKS[sid]["pos"]
        tgt = stamp_target(sid, frm, [s for s in STALKS if self.perchable(s)])
        if self.ph == 2 and sid != "M":
            if self.cracked[sid]:
                self.alive[sid] = False
                self.S("canas_quebradas")
            else:
                self.cracked[sid] = True
                self.S("canas_rajadas")
        self.leap = None
        self.uncut = 0
        self.S("latigazos_f%d" % (self.ph + 1))
        if how == "caida":
            self.S("latigazo_caida")
            return self.opening("caida", base, t)
        if how == "resbalon":
            self.S("latigazo_resbalon")
            return self.opening("resbalon", base, t)
        if tgt is not None:
            self.S("latigazo_estampado")
            q = STALKS[tgt]["pos"]
            u = norm(v2(base, q))
            return self.opening("estampado", (q[0] - u[0] * 0.6, q[1] - u[1] * 0.6), t)
        self.S("latigazo_revolcon")
        d = norm(v2(frm, base))
        return self.opening("revolcon", clamp_r((base[0] + d[0] * P["revolcon_m"], base[1] + d[1] * P["revolcon_m"]), 13.0), t)

    # ------------------------------------------------------------------ cortes de Kaito
    def kaito_cut(self, dmg_base, idx):
        t, k = self.t, self.k
        frm = tuple(k.pos)
        self.S("cortes")
        m = self.mode
        if m in ("perch", "climb"):
            base = STALKS[self.stalk]["pos"]
            if dist(frm, base) > 3.2:
                return self.S("corte_lejos")
            ld = self.loaded
            if ld is not None and ld[0] <= t <= ld[1]:
                k.on_dealt(t)
                self.k.goal = None
                return self.whip(frm, self.stalk, "resbalon" if m == "climb" else "normal")
            if m == "perch" and (self.act is None or self.act.get("name") not in ("barrido", "tala")):
                # sin campanas: '¡Cosquillas!', se agarra y le barre la caña encima (rojo); si acaba de barrer, se va
                self.S("cosquillas")
                if self.cd_ok("barrido", 2.5) and dist(frm, base) <= 3.4:
                    self.cd["barrido"] = t
                    self.trace("cosquillas: barre con la caña")
                    return self.stalk_sweep(wobble=0.25)
                self.S("la_monta")
                self.trace("la monta (cortó la caña sin campanas)")
                if self.pick_dest() is not None:
                    self.set_mode("monta")
                    self.go(t + 0.25, self.start_leap, True)
                return
            return self.S("corte_a_la_cana")
        if m == "leap" and self.leap is not None:
            dest = STALKS[self.leap["dest"]]["pos"]
            if dist(frm, dest) <= 3.2 and self.leap["grab"] - P["catch_window"] <= t < self.leap["grab"]:
                k.on_dealt(t)
                self.k.goal = None
                return self.whip(frm, self.leap["dest"], "caida")
            return self.S("corte_al_aire")
        if dist(frm, self.gpos) > 3.2:
            return self.S("corte_lejos")
        if m == "pertiga":
            ld = self.loaded
            if ld is not None and ld[0] <= t <= ld[1]:
                k.on_dealt(t)
                self.k.goal = None
                self.qa = None
                return self.whip_staff(frm)
            return self.S("corte_al_aire")
        if m in ("question", "answer"):
            k.on_dealt(t)
            self.S("desafinado_n")
            self.qa = None
            return self.opening("desafinado", self.gpos, t, then=self.gdecide)
        if m == "crouch":
            k.on_dealt(t)
            return self.opening("tropiezo", self.gpos, t)
        if m == "open" and self.open is not None and self.open["t0"] <= t <= self.open["t1"]:
            o = self.open
            if o["cuts"] <= 0:
                return self.S("corte_tope")
            o["cuts"] -= 1
            k.on_dealt(t)
            self.damage_boss(dmg_base * k.mul(t) * o["mul"], "hueco_" + o["kind"])
            if o["cuts"] <= 0 and self.mode == "open":
                # el último corte del tope lo tira lejos: se levanta enseguida
                o["t1"] = min(o["t1"], t + 0.25)
                nxt = self.getup if o["kind"] not in ("landing", "desafinado", "contra") else \
                    self.ground_after_landing if o["kind"] == "landing" else self.gdecide if self.ph == 1 else self.return_up
                self.go(o["t1"], self.close_open, nxt)
            return
        if t < self.inv_until or m in ("leap", "vault", "dive", "drop", "monta", "trans", "hop", "open"):
            return self.S("corte_al_aire")
        if m == "gstrike" and self.act is not None and t < self.act.get("T", 0.0):
            # armadura en la carga: entra a la mitad y el golpe sigue
            k.on_dealt(t)
            return self.damage_boss(dmg_base * k.mul(t) * P["armor_mul"], "carga")
        if m in ("ground", "gstrike"):
            # el Paso del Ermitaño: el corte en neutral entra y se va de una voltereta (0.35 s invulnerable)
            k.on_dealt(t)
            self.damage_boss(dmg_base * k.mul(t) * P["neutral_mul"], "neutral")
            if self.mode not in ("ground", "gstrike"):
                return
            self.S("volteretas")
            self.inv_until = t + P["backflip_inv"]
            d = norm(v2(frm, self.gpos))
            self.gpos = self.root = clamp_r((self.gpos[0] + d[0] * P["backflip"], self.gpos[1] + d[1] * P["backflip"]), 13.0)
            self.set_mode("ground")
            if self.ph == 1:
                return self.go(t + P["backflip_inv"] + 0.25, self.run_combo, list(self.rng.choice(self.COMBOS)[2]), self.gdecide)
            return self.go(t + P["backflip_inv"], self.return_up)
        return self.S("corte_sin_efecto")

    def whip_staff(self, frm):
        self.S("latigazo_pertiga")
        self.S("latigazos_f2")
        d = norm(v2(frm, self.gpos))
        return self.opening("revolcon", clamp_r((self.gpos[0] + d[0] * 2.0, self.gpos[1] + d[1] * 2.0), 13.0), self.t,
                            then=self.gdecide)

    # ------------------------------------------------------------------ el piso (fase 2)
    COMBOS = [
        # el segundo golpe de la flauta giratoria a 0.42 s del primero: un golpe encadenado no baja de ahí (el '¡ya!' va a
        # 0.38 s; StepTimeline.MinWindup)
        ("Nota y Giro", 1.0, [("gold", 0.50, "ground"), ("gold", 0.55, "ground"), ("gold", 0.42, "ground")]),
        ("Grulla que Barre", 0.9, [("gold", 0.50, "ground"), ("red", 0.80, "lowsweep")]),
        ("Tres Estocadas", 0.8, [("gold", 0.50, "ground"), ("gold", 0.42, "ground"), ("gold", 0.42, "ground")]),
        ("Golpe de Nota", 0.6, [("gold", 0.65, "ground")]),
    ]

    def gdecide(self):
        t = self.t
        self.set_mode("ground")
        self.act = None
        if self.ph == 2 and self.pick_dest(from_ground=True) is not None:
            return self.start_leap(from_ground=True, vault=True)
        if t >= self.next_pertiga:
            self.next_pertiga = t + self.rng.uniform(*P["pertiga_every"])
            return self.pertiga()
        if t >= self.next_qa:
            self.next_qa = t + self.rng.uniform(*P["qa_every"])
            return self.question()
        d = dist(self.k.pos, self.gpos)
        if d > 4.5 and self.cd_ok("soplo", 2.5):
            # de lejos no se le acerca caminando: le sopla un dardo desde el piso (y sigue)
            self.cd["soplo"] = t
            return self.ground_dart()
        if d > 3.0:
            # se acerca corriendo un tramo y vuelve a decidir
            step = min(d - 2.2, P["ground_speed"] * 0.25)
            u = norm(v2(self.gpos, self.k.pos))
            self.gpos = self.root = (self.gpos[0] + u[0] * step, self.gpos[1] + u[1] * step)
            return self.go(t + 0.25, self.gdecide)
        r = self.rng.random() * sum(w for _, w, _ in self.COMBOS)
        for name, w, steps in self.COMBOS:
            r -= w
            if r <= 0:
                break
        self.S("combo_" + name)
        self.trace("combo " + name)
        self.run_combo(list(steps), self.gap_then_decide)

    def ground_dart(self):
        """Soplo a Quemarropa: desde el piso, la flauta a la boca y un dardo dorado (0.55 s)."""
        t = self.t
        self.set_mode("ground")
        self.S("acc_soplo")
        k = self.k
        fl = math.hypot(dist(k.pos, self.gpos), 0.6) / P["dart_speed"][self.ph]
        T = t + 0.55 + fl
        self.go(max(t, T - TICK["gold"]), self.cue_only, T, "gold")
        self.go(t + 0.55, self.ground_dart_go, T)
        self.go(t + 0.85, self.gdecide)

    def ground_dart_go(self, T):
        k = self.k
        fl = T - self.t
        aim = (k.pos[0] + k.vel[0] * fl * 0.6, k.pos[1] + k.vel[1] * fl * 0.6)
        zone = ("disc", aim, P["dart_hit_r"])
        self.show(T, "gold", own=False)
        self.at(T, self.strike_kaito, "dart", self.dmg("dart"), zone, "soplo")

    def gap_then_decide(self):
        self.set_mode("ground")
        self.go(self.t + self.rng.uniform(*P["gap"]), self.gdecide)

    def run_combo(self, steps, then):
        kind, w, key = steps.pop(0)
        nxt = (lambda: self.run_combo(steps, then)) if steps else then
        self.gstrike(key, w, key, last=not steps, then=nxt, kind=kind, radius=2.6 if key == "lowsweep" else 2.4)

    def pertiga(self):
        """La Grulla en el Bastón: salta atrás, clava el bastón, se sube a la punta (2.4 m) y se para en un pie como una
        grulla; después se tira en picada (rojo). Cortar el bastón mientras las campanas brillan lo tira (revolcón)."""
        t = self.t
        u = norm(v2(self.k.pos, self.gpos))
        self.gpos = self.root = clamp_r((self.gpos[0] + u[0] * 4.0, self.gpos[1] + u[1] * 4.0), 12.5)
        self.set_mode("hop")
        self.S("acc_pertiga")
        self.trace("pértiga")
        self.go(t + 0.45, self.pertiga_up)

    def pertiga_up(self):
        t = self.t
        self.set_mode("pertiga")
        a, b = P["pertiga_loaded"]
        self.set_loaded(t + a, t + b, None)
        self.go(t + b, self.pertiga_dive)

    def cue_only(self, T, kind):
        self.k.cue(self.t, T, kind)

    def pertiga_dive(self):
        self.loaded = None
        self.set_mode("dive")
        T = self.t + 0.95
        self.show(T, "red")
        self.go(self.t + 0.50, self.dive_fix, T, "pertiga_picada", 1.4, "dive")

    def question(self):
        """Pregunta y Respuesta: toca la frase (sin daño) y en el compás siguiente la repite con golpes."""
        t = self.t
        u = norm(v2(self.k.pos, self.gpos))
        self.gpos = self.root = clamp_r((self.gpos[0] + u[0] * 3.0, self.gpos[1] + u[1] * 3.0), 12.5)
        four = self.hp / P["health"] <= 0.52
        phrase = self.rng.choice([["A", "A", "A", "G"], ["A", "G", "A", "G"], ["G", "A", "G", "A"]] if four else
                                 [["A", "A", "G"], ["A", "G", "A"], ["G", "A", "A"]])
        self.set_mode("question")
        self.S("pregunta")
        self.trace("pregunta " + "".join(phrase))
        self.qa = dict(phrase=phrase, hits=0)
        q = 0.45 + len(phrase) * P["note_gap"]
        self.tells.append((t, t + q))
        self.go(t + q, self.answer, self.qa)

    def answer(self, qa):
        self.set_mode("answer")
        t = self.t
        for i, note in enumerate(qa["phrase"]):
            T = t + 0.85 + i * P["note_gap"]
            self.go(T - 0.45, self.note_fix, qa, note, T)
        self.go(t + 0.85 + (len(qa["phrase"]) - 1) * P["note_gap"] + 0.3, self.answer_end, qa)

    def note_fix(self, qa, note, T):
        kind = "gold" if note == "A" else "red"
        zone = ("disc", tuple(self.k.pos), P["dart_hit_r"] if note == "A" else 1.0 + 0.35)
        self.show(T, kind, own=note != "A")
        self.at(T - TICK[kind], self.cue_if, T, kind, zone)
        self.at(T, self.note_hit, qa, "dart" if note == "A" else "red", zone)

    def note_hit(self, qa, kind, zone):
        r = self.strike_kaito(kind, self.dmg("dart" if kind == "dart" else "sprout"), zone, "respuesta")
        if r in ("hit", "graze"):
            qa["hits"] += 1

    def answer_end(self, qa):
        self.qa = None
        if qa["hits"] == 0:
            self.S("afinado")
            return self.opening("afinado", self.gpos, self.t, then=self.gdecide)
        self.gdecide()

    # ------------------------------------------------------------------ el bucle
    def run(self, tmax=1200.0):
        k = self.k
        while self.t < tmax:
            t = self.t
            while self.ev and self.ev[0][0] <= t:
                _, _, tok, fn, args = heapq.heappop(self.ev)
                if tok is not None and tok != self.tok:
                    continue
                fn(*args)
                if self.won or k.hp <= 0:
                    return self.won
            # el campamento al pie de la caña sin campanas
            if self.mode == "perch" and self.loaded is None and dist(k.pos, self.root) <= P["camp_dist"]:
                self.near_since = self.near_since if self.near_since is not None else t
            else:
                self.near_since = None
            if k.goal is not None and (t > k.goal_until or self.mode in ("open", "trans")):
                k.goal = None
            target = k.goal if k.goal is not None else self.root
            thr = self.threatened()
            k.step(t, target)
            if k.goal is not None and not k.goal_dashed and k.state == "free" and dist(k.pos, target) > P["hook_dash"] \
                    and k.spirit >= 15.0:
                k.goal_dashed = True
                k.dash(t, target)
                self.S("dash_al_latigazo")
            greedy = self.rng.random() < k.sk["greedy"] * DT * 4.0
            # el gancho: a Chikuō posado (o trepando, o en la pértiga) solo se le corta la caña cuando el bot vio las campanas
            # blancas (BotCutGoal, con su probabilidad y su tiempo de reacción), como no le pega a una guardia
            # (BambooMasterBoss.BotMayCut); salvo de apurado. Aunque esté al pie, no corta en el mismo cuadro en que se encienden
            up = self.mode in ("perch", "climb", "pertiga")
            if dist(k.pos, target) < 2.6 and not k.pending and (k.goal is not None or not (thr or up) or greedy):
                k.try_cut(t)
            due = [c for c in k.cuts if c[0] <= t]
            if due:
                k.cuts = [c for c in k.cuts if c[0] > t]
                for (_, dmg, idx) in due:
                    self.kaito_cut(dmg, idx)
                    if self.won:
                        return True
            # contadores
            self.phase_t[self.ph] += DT
            if self.mode in ("perch", "leap", "vault", "climb", "pertiga", "monta"):
                self.up_t[self.ph] += DT
            if self.open is not None:
                self.open_t[self.ph] += DT
            busy = self.open is not None or self.loaded is not None or self.mode in ("leap", "vault", "trans", "dive", "monta") \
                or any(a <= t <= b for a, b in self.tells[-12:])
            if busy:
                self.dead_run = 0.0
            else:
                self.dead_t += DT
                self.dead_run += DT
                if self.dead_run > self.dead_max:
                    self.dead_max = self.dead_run
                    if self.dead_run > 1.6:
                        self.trace("tramo muerto de %.2f s" % self.dead_run)
            self.t += DT
        return False


def campaign(skill, rng, stats, log=None):
    total, deaths, retry = 0.0, 0, 0
    died = []
    agg = dict(threats=[0, 0, 0], phase_t=[0.0, 0.0, 0.0], up_t=[0.0, 0.0, 0.0], acts=[0, 0, 0], open_t=[0.0, 0.0, 0.0],
               dead_t=0.0, dead_max=0.0)
    while deaths < 15:
        f = Fight(skill, rng, retry, stats, log)
        won = f.run()
        total += f.t + (REINTRO if deaths else 0.0)
        for i in range(3):
            agg["threats"][i] += f.threats[i]
            agg["phase_t"][i] += f.phase_t[i]
            agg["up_t"][i] += f.up_t[i]
            agg["acts"][i] += f.acts[i]
            agg["open_t"][i] += f.open_t[i]
        agg["dead_t"] += f.dead_t
        agg["dead_max"] = max(agg["dead_max"], f.dead_max)
        for key, v in f.k.stats.items():
            stats["k_" + key] = stats.get("k_" + key, 0.0) + v
        if won:
            return dict(win_time=f.t, total=total, deaths=deaths, died=died, phases=f.phase_t, agg=agg)
        died.append(f.ph)
        deaths += 1
        total += DEATH_AND_RETRY
        retry = max(retry, f.ph)
    return dict(win_time=None, total=total, deaths=deaths, died=died, phases=[0, 0, 0], agg=agg)


def fight_report(skills, runs, seed):
    for sk in skills:
        rng = random.Random(seed)
        stats = {}
        rs = [campaign(sk, rng, stats) for _ in range(runs)]
        wins = sorted(r["win_time"] for r in rs if r["win_time"] is not None)
        tot = sorted(r["total"] for r in rs)
        dth = [r["deaths"] for r in rs]
        q = lambda xs, f: xs[min(len(xs) - 1, int(f * len(xs)))] if xs else float("nan")
        died = [0, 0, 0]
        for r in rs:
            for ph in r["died"]:
                died[ph] += 1
        n = float(runs)
        print("\n== %s: %d peleas | total (lo que mide el PlayClock) %.0f s = %.1f min (p10 %.0f, p90 %.0f) | intento ganador %.0f s"
              " | muertes %.2f (sin morir %.0f %%; en la fase 1/2/3: %.2f/%.2f/%.2f)" % (
                  sk, runs, q(tot, 0.5), q(tot, 0.5) / 60.0, q(tot, 0.1), q(tot, 0.9), q(wins, 0.5),
                  sum(dth) / n, 100.0 * sum(1 for d in dth if d == 0) / n, died[0] / n, died[1] / n, died[2] / n))
        ph = [sorted(r["phases"][i] for r in rs if r["win_time"] is not None) for i in range(3)]
        print("   fases del intento ganador (mediana): %.0f / %.0f / %.0f s" % tuple(q(p, 0.5) for p in ph))
        agg_t = [sum(r["agg"]["phase_t"][i] for r in rs) for i in range(3)]
        agg_th = [sum(r["agg"]["threats"][i] for r in rs) for i in range(3)]
        agg_up = [sum(r["agg"]["up_t"][i] for r in rs) for i in range(3)]
        agg_op = [sum(r["agg"]["open_t"][i] for r in rs) for i in range(3)]
        agg_ac = [sum(r["agg"]["acts"][i] for r in rs) for i in range(3)]
        print("   amenazas por minuto (golpes, dardos, zonas): %.0f / %.0f / %.0f (fuera de sus huecos: %.0f / %.0f / %.0f); acciones"
              " por minuto (cada cosa que decide: ataque, salto, pértiga) %.0f / %.0f / %.0f" % (
                  *(60.0 * agg_th[i] / max(1, agg_t[i]) for i in range(3)),
                  *(60.0 * agg_th[i] / max(1, agg_t[i] - agg_op[i]) for i in range(3)),
                  *(60.0 * agg_ac[i] / max(1, agg_t[i]) for i in range(3))))
        print("   arriba (caña, salto, pértiga) %.0f / %.0f / %.0f %% del tiempo; abierto (en un hueco) %.0f / %.0f / %.0f %%" % (
            *(100.0 * agg_up[i] / max(1, agg_t[i]) for i in range(3)), *(100.0 * agg_op[i] / max(1, agg_t[i]) for i in range(3))))
        dead = sum(r["agg"]["dead_t"] for r in rs) / max(1, sum(agg_t))
        print("   tiempo muerto (ni aviso, ni campanas blancas, ni hueco, ni salto): %.0f %%; el tramo más largo %.2f s" % (
            100 * dead, max(r["agg"]["dead_max"] for r in rs)))
        dmg = {k[5:]: v / n for k, v in stats.items() if k.startswith("dano_") and not k.startswith("dano_kaito")}
        td = sum(dmg.values()) or 1.0
        print("   daño a Chikuō: " + ", ".join("%s %.0f%%" % (k, 100 * v / td) for k, v in sorted(dmg.items(), key=lambda x: -x[1])))
        whips = ["latigazo_revolcon", "latigazo_estampado", "latigazo_caida", "latigazo_resbalon", "latigazo_pertiga"]
        for f in (1, 2, 3):
            fd = {k[6:]: v / n for k, v in stats.items() if k.startswith("fase%d_" % f)}
            tf = sum(fd.values()) or 1.0
            print("   daño en la fase %d: " % f + ", ".join("%s %.0f%%" % (k, 100 * v / tf) for k, v in sorted(fd.items(), key=lambda x: -x[1])[:7]))
        ph_med = [max(1.0, q(p, 0.5)) for p in ph]
        print("   latigazos por fase: %.1f / %.1f / %.1f (uno cada %.1f / %.1f / %.1f s del intento ganador)" % (
            *(stats.get("latigazos_f%d" % f, 0) / n for f in (1, 2, 3)),
            *(ph_med[f - 1] / max(0.1, stats.get("latigazos_f%d" % f, 0) / n) for f in (1, 2, 3))))
        print("   por pelea: " + ", ".join("%s %.1f" % (k, stats.get(k, 0) / n) for k in whips + [
            "cargas", "la_monta", "saltos", "ping_pong", "trepadas", "dash_al_latigazo", "hueco_pies", "hueco_clavado",
            "pregunta", "afinado", "desafinado_n", "risa_maestro", "canas_rajadas", "canas_quebradas", "canas_taladas",
            "volteretas", "cortes", "corte_al_aire", "corte_tope", "corte_lejos"]))
        print("   acciones: " + ", ".join("%s %.1f" % (k[4:], v / n) for k, v in sorted(stats.items()) if k.startswith("acc_")))
        kd = {k[11:]: v / n for k, v in stats.items() if k.startswith("dano_kaito_")}
        tk = sum(kd.values()) or 1.0
        print("   daño a Kaito (%.0f por pelea): " % tk + ", ".join("%s %.0f%%" % (k, 100 * v / tk) for k, v in sorted(kd.items(), key=lambda x: -x[1])))
        for f in (1, 2, 3):
            fd = {k[7:]: v / n for k, v in stats.items() if k.startswith("kfase%d_" % f)}
            print("   a Kaito en la fase %d (%.0f): " % (f, sum(fd.values())) + ", ".join("%s %.1f" % (k, v) for k, v in sorted(fd.items(), key=lambda x: -x[1])[:8]))
        print("   Kaito: parries %.1f (perfectos %.1f), esquivas %.1f, golpes %.1f, roces %.1f, dash sin Espíritu %.1f" % tuple(
            stats.get("k_" + x, 0) / n for x in ("parry", "perfect", "dodge", "hit", "graze", "dash_tired")))


def knobs_report(runs, seed, factors=(1.0, 1.15, 1.3, 1.42)):
    """Las perillas del balance (sección 12.3 del doc): qué mueve cada una, con el factor real/simulado supuesto."""
    global KAITO_DMG
    import copy
    base = copy.deepcopy(P)
    cap2 = dict(revolcon=(0.55, 1.6, 2, 1.0, 12.0), open_p3=dict(revolcon=(0.55, 1.4, 2, 1.0, 12.0), estampado=(1.00, 2.0, 3, 1.2, 24.0)))
    cap4 = dict(revolcon=(0.55, 1.6, 4, 1.0, 12.0), open_p3=dict(revolcon=(0.55, 1.4, 4, 1.0, 12.0), estampado=(1.00, 2.0, 3, 1.2, 24.0)))
    half = dict(revolcon=(0.55, 1.6, 3, 1.0, 6.0), estampado=(1.00, 2.2, 4, 1.2, 12.0), caida=(0.45, 3.0, 5, 1.25, 18.0),
                open_p3=dict(revolcon=(0.55, 1.4, 3, 1.0, 6.0), estampado=(1.00, 2.0, 3, 1.2, 12.0)))
    long4 = dict(revolcon=(0.55, 2.0, 4, 1.0, 12.0), open_p3=dict(revolcon=(0.55, 1.8, 4, 1.0, 12.0), estampado=(1.00, 2.0, 3, 1.2, 24.0)))
    more = dict(revolcon=(0.55, 1.6, 3, 1.0, 18.0), estampado=(1.00, 2.2, 4, 1.2, 36.0), caida=(0.45, 3.0, 5, 1.25, 54.0),
                open_p3=dict(revolcon=(0.55, 1.4, 3, 1.0, 18.0), estampado=(1.00, 2.0, 3, 1.2, 36.0)))
    rows = [("hoy", {}), ("tope del revolcón 3 -> 2", cap2), ("tope del revolcón 3 -> 4", cap4),
            ("revolcón de 2.0 s con tope 4", long4), ("caídas a la mitad (6 / 12 / 18)", half),
            ("caídas x1.5 (18 / 36 / 54)", more), ("daño a Kaito x1.1", dict(dmg_scale=1.1)),
            ("daño a Kaito x0.9", dict(dmg_scale=0.9))]
    print("== perillas (%d peleas por nivel; minutos del PlayClock y muertes medias)" % runs)
    for F in factors:
        for label, mods in rows:
            P.clear()
            P.update(copy.deepcopy(base))
            P.update(copy.deepcopy(mods))
            KAITO_DMG = 1.0 / F
            out = []
            for sk in ("bueno", "promedio"):
                rng = random.Random(seed)
                rs = [campaign(sk, rng, {}) for _ in range(runs)]
                tot = sorted(r["total"] for r in rs)
                out.append("%s %.1f min %.2f muertes" % (sk, tot[runs // 2] / 60.0, sum(r["deaths"] for r in rs) / runs))
            print("  F %.2f  %-32s %s" % (F, label, " | ".join(out)))
    P.clear()
    P.update(base)
    KAITO_DMG = 1.0


def main():
    global KAITO_DMG
    ap = argparse.ArgumentParser()
    ap.add_argument("--layout", action="store_true")
    ap.add_argument("--camera", action="store_true")
    ap.add_argument("--fair", action="store_true")
    ap.add_argument("--runs", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--skill", default="all")
    ap.add_argument("--calib", type=float, default=None)
    ap.add_argument("--p", default=None)
    ap.add_argument("--nofight", action="store_true")
    ap.add_argument("--knobs", action="store_true", help="la tabla de las perillas del balance (tarda: 8 x 2 x --runs peleas por factor)")
    ap.add_argument("--factors", default="1.0,1.15,1.3,1.42", help="con --knobs: los factores real/simulado a probar")
    ap.add_argument("--trace", type=float, default=0.0, help="imprime los primeros N s de una pelea del nivel --skill")
    a = ap.parse_args()
    if a.p:
        for k, v in json.loads(a.p).items():
            if k not in P:
                raise SystemExit("--p: no hay perilla '%s'" % k)
            P[k] = v
    if a.calib:
        KAITO_DMG = 1.0 / a.calib
        print("daño de Kaito x%.3f (factor real/simulado supuesto %.2f)" % (KAITO_DMG, a.calib))
    if a.layout:
        layout_report()
    if a.camera:
        camera_report()
    if a.fair:
        fair_report()
    if a.knobs:
        knobs_report(a.runs, a.seed, tuple(float(x) for x in a.factors.split(",")))
        return
    if a.trace > 0:
        log = []
        campaign(a.skill if a.skill != "all" else "bueno", random.Random(a.seed), {}, log)
        for line in log:
            if float(line.split()[0]) <= a.trace:
                print(line)
        return
    if not a.nofight:
        skills = ["experto", "bueno", "promedio"] if a.skill == "all" else [a.skill]
        fight_report(skills, a.runs, a.seed)


if __name__ == "__main__":
    main()
