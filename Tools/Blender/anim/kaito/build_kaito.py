"""Kaito: esqueleto de juego + todos sus clips, chequeos, FBX y hojas de revisión. Un solo comando, determinista:

  blender -b --factory-startup --python Tools/Blender/anim/kaito/build_kaito.py -- [opciones]
    --export          re-escribe EN EL LUGAR Nindo/Assets/Animations teo/kaitooo.fbx (mismo .meta y GUID) y su
                      sidecar kaitooo.fbx.json; después correr Tools/Unity/generate_assets.py (o su parte de Kaito)
    --src FBX         modelo de partida (por defecto el del repo: el script es idempotente)
    --renders DIR     hojas de revisión por clip en DIR
    --only A,B        solo esos clips (para iterar; no exporta)
    --report PATH     las mediciones en JSON
    --blend PATH      guarda el .blend

Orden con export_kaito.py (malla, materiales y katana del pulido B2): primero export_kaito.py, después este.

Falla (código 1) si un chequeo no pasa: alcance de manos y pies, deriva de los pies apoyados (< 2 cm en el
juego), suelas que rozan el piso y se corren (< 2 cm por cuadro del juego y < 3 cm por tramo, con el avance y el
giro del modelo que pone el código, entre cuadros en los ciclos, y también con el avance del corte cortado por el
imán), pies en el aire donde el juego mueve el cuerpo ('airborne'), empalmes de los crossfades cortos
(kaito_clips.CHAINS), costura de los loops (< 1°), velocidad de los ciclos contra la autorada, el impacto dentro de
la ventana que pega, nada bajo el piso, y la re-importación del FBX igual a lo horneado.
    --detail A,B      imprime, muestra por muestra, la altura y el corrimiento de las suelas de esos clips
"""
import sys, os, json, math, time, shutil, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
for p in (HERE, os.path.join(ROOT, "Tools", "Blender", "anim"), os.path.join(ROOT, "Tools", "Blender", "characters")):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True

import bpy
import numpy as np
from mathutils import Vector, Matrix
import nindo_anim as NA
import charlib as C
import fbxcheck
import kaito_rig as KR

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


REL = "Animations teo/kaitooo.fbx"
FBX = os.path.join(ROOT, "Nindo", "Assets", REL)
SRC = opt("--src", FBX)
EXPORT = "--export" in argv
RENDERS = opt("--renders")
ONLY = opt("--only")
REPORT = opt("--report")
BLEND = opt("--blend")
DETAIL = (opt("--detail") or "").split(",")     # clips cuyos pies se imprimen muestra por muestra (para iterar)
GAP = 10
M = KR.M_PER_U
failures, warnings = [], []


def check(ok, msg, warn=False):
    print(("  ok   " if ok else ("  WARN " if warn else "  FAIL ")) + msg)
    if not ok:
        (warnings if warn else failures).append(msg)


# =============================================================================== mediciones de un clip
def sole_pivots():
    """{hueso del pie: [punta, talón, bola]} de la suela en reposo (espacio C)."""
    return {fb: list(KR.sole_points(S)) for S, fb in (("R", "Pie.R"), ("L", "Pie.L"))}


# ------------------------------------------------------------------------------- pies que rozan el piso
# plant_report solo mira apoyos que ya están casi quietos: un pie que toca el piso y SE MUEVE (la punta de atrás
# arrastrada en un tajo, la punta que roza al despegar en el trote) no lo ve. Acá cuenta cualquier punto de la
# suela a menos de CONTACT del piso en dos muestras seguidas, con el avance del juego aplicado
CONTACT_U = 0.012 * KR.U_PER_M
SKATE_STEP_CM, SKATE_RUN_CM = 2.0, 3.0      # por cuadro del juego / acumulado en un tramo
SKATE_NOISE_CM = 0.5                        # cm por cuadro del juego (15 cm/s) que no se ven: no suman


def sole_grid(S):
    """9 puntos de la suela en reposo (espacio C): punta, bola y talón por adentro, al medio y por afuera."""
    toe, heel, ball = KR.sole_points(S)
    xs = sorted({round(c.x, 4) for c in KR.sole_corners(S)} | {round(toe.x, 4)})
    return [Vector((x, y, 0.0)) for x in xs for y in (toe.y, ball.y, heel.y)]


def chain_of(rig, n):
    out = []
    while n:
        out.append(n)
        n = rig.parent[n]
    return out[::-1]


def interp_world(rig, Wa, Wb, t, chain):
    """Pose del último hueso de 'chain' entre dos cuadros horneados como la arma Unity: cada hueso interpola su
    transform local (posición lineal, giro por slerp) y la cadena se recompone. Entre claves a 30 fps un pie
    clavado en el mundo describe un arco: eso es lo que patina entre cuadros aunque cada cuadro esté quieto."""
    W = None
    for n in chain:
        p = rig.parent[n]
        la = (Wa[p].inverted() @ Wa[n]) if p else Wa[n]
        lb = (Wb[p].inverted() @ Wb[n]) if p else Wb[n]
        L = NA.compose(la.translation.lerp(lb.translation, t), la.to_quaternion().slerp(lb.to_quaternion(), t).to_matrix())
        W = L if W is None else W @ L
    return W


def spin_deg(spin, f):
    """Giro del MODELO que aplica el código (timing 'spin' = [desde, hasta, grados], con la curva EaseOut de
    PlayerController.TickWhirlwind); afuera del tramo, 0 (el código lo devuelve a la base: 720° = 0°)."""
    if not spin:
        return 0.0
    a, b, deg = spin
    if f < a or f > b:
        return 0.0
    u = (f - a) / (b - a)
    return deg * (1.0 - (1.0 - u) ** 2)


def foot_samples(rig, frames, roots, fb, S, sub, use_roots, spin=None):
    loc = [rig.rest_inv[fb] @ p for p in sole_grid(S)]
    chain = chain_of(rig, fb)
    out = []
    n = len(frames) - 1
    for f in range(n + 1):
        for k in range(sub if f < n else 1):
            t = k / sub
            W = frames[f][fb] if k == 0 else interp_world(rig, frames[f], frames[f + 1], t, chain)
            r = (roots[f].lerp(roots[f + 1], t) if k else roots[f]) if use_roots else Vector()
            Rz = Matrix.Rotation(math.radians(spin_deg(spin, f + t)), 3, 'Z')
            out.append((f + t, [Rz @ (W @ p) + r for p in loc]))
    return out


def skate_report(rig, frames, roots, sub=1, use_roots=True, skid=(), detail=False, time_scale=1.0, spin=None):
    """{pie: [[desde, hasta, cm acumulados, cm/cuadro del juego máx], ...]} de los tramos en que la suela roza el
    piso y se corre (el punto que menos se mueve: rodar sobre la punta o el talón no cuenta). 'skid' = tramos de
    cuadros donde patinar es a propósito (no cuentan). time_scale: cuadros del clip por cuadro del juego."""
    out = {}
    for S, fb in (("R", "Pie.R"), ("L", "Pie.L")):
        smp = foot_samples(rig, frames, roots, fb, S, sub, use_roots, spin)
        runs, cur = [], None
        for (ta, pa), (tb, pb) in zip(smp, smp[1:]):
            idx = [i for i in range(len(pa)) if pa[i].z < CONTACT_U and pb[i].z < CONTACT_U]
            ok = any(a <= ta and tb <= b for a, b in skid)
            if detail:
                zl = min(p.z for p in pa) * M * 100
                dd = min((Vector((pb[i].x - pa[i].x, pb[i].y - pa[i].y)).length for i in idx), default=0.0) * M * 100
                print(f"    {fb} t{ta:5.2f} z {zl:5.1f} cm  {'roza' if idx else '    '} {dd:5.2f} cm")
            if idx and not ok:
                d = min(Vector((pb[i].x - pa[i].x, pb[i].y - pa[i].y)).length for i in idx) * M * 100
                rate = d / ((tb - ta) / time_scale)
                if cur is None:
                    cur = [ta, tb, 0.0, 0.0, []]
                cur[1] = tb
                cur[2] += d if rate > SKATE_NOISE_CM else 0.0
                cur[4].append((ta / time_scale, d, (tb - ta) / time_scale))
            elif cur is not None:
                runs.append(cur)
                cur = None
        if cur is not None:
            runs.append(cur)
        # velocidad en ventanas de medio cuadro del juego (lo que se ve a 60 fps), o de una muestra si están más
        # separadas: una muestra de 1/8 de cuadro en el instante en que la punta toca no es un patinazo
        for r in runs:
            ds = r.pop()
            w = max(0.5, max(dt for _, _, dt in ds))
            r[3] = max(sum(d for t, d, _ in ds if t0 <= t < t0 + w) / w for t0, _, _ in ds)
        out[fb] = [[round(r[0], 2), round(r[1], 2), round(r[2], 2), round(r[3], 2)] for r in runs if r[2] > 0.3]
    return out


def touching(rig, frames, roots, a, b):
    """Cuadros de [a, b] en que algún pie toca el piso (para los tramos en que el juego mueve el cuerpo solo)."""
    hit = []
    for S, fb in (("R", "Pie.R"), ("L", "Pie.L")):
        loc = [rig.rest_inv[fb] @ p for p in sole_grid(S)]
        for f in range(a, b + 1):
            if min((frames[f][fb] @ p).z for p in loc) < CONTACT_U:
                hit.append((fb, f))
    return hit


def lint_clip(rig, clip, frames, ctrls, roots, misses):
    rep = {}
    t = clip.timing
    n = clip.frames
    mh = max(max(m["hand_r"], m["hand_l"]) for m in misses)
    ml = max(m["legs"] for m in misses)
    rep["reach_miss_cm"] = {"hands": round(mh * M * 100, 1), "legs": round(ml * M * 100, 1)}
    check(ml * M <= 0.015, f"{clip.name}: los pies llegan (faltó {ml * M * 100:.1f} cm en "
                           f"f{max(range(len(misses)), key=lambda i: misses[i]['legs'])})")
    fr_ = max(range(len(misses)), key=lambda i: max(misses[i]["hand_r"], misses[i]["hand_l"]))
    fl_ = max(range(len(misses)), key=lambda i: misses[i]["legs"])
    check(mh * M <= 0.02, f"{clip.name}: las manos llegan (faltó {mh * M * 100:.1f} cm en f{fr_}: der "
                          f"{misses[fr_]['hand_r'] * M * 100:.0f} / izq {misses[fr_]['hand_l'] * M * 100:.0f}; pies f{fl_})",
          warn=mh * M <= 0.05)
    # apoyos: el punto de la suela que menos se mueve (punta, talón o bola) no se corre
    piv = sole_pivots()
    gp = {fb: rig.rest_inv[fb] @ piv[fb][2] for fb in piv}
    pivl = {fb: [rig.rest_inv[fb] @ p for p in piv[fb]] for fb in piv}
    # plant_report detecta apoyos con el punto bajo (z < 0.12 u = 6 cm) y casi quieto
    plants = NA.plant_report(rig, frames, roots, list(gp), gp, thresh=0.02, pivots=pivl)
    worst = max([p["drift_cm"] for v in plants.values() for p in v] or [0.0]) * M
    rep["plants"] = plants
    rep["plant_drift_cm"] = round(worst, 2)
    wseg = [(k, p["frames"]) for k, v in plants.items() for p in v if p["drift_cm"] * M >= worst - 1e-6]
    check(worst <= 2.0 or t.get("slide_ok"), f"{clip.name}: pies apoyados quietos (deriva máx. {worst:.2f} cm en el juego {wseg[:2]})")
    # suela que roza el piso y se corre: en los ciclos también entre cuadros (4 muestras por cuadro, como interpola
    # Unity: ahí el pie clavado recorre 10-20 cm por cuadro en el espacio del cuerpo); en el resto, cuadro a cuadro.
    # 'skid' = tramos en que se corre a propósito (un corte de cámara o un teletransporte del código); 'spin' = el
    # giro del modelo que pone el código (un pie apoyado mientras el modelo gira dibuja un círculo en el piso)
    skid = [tuple(s) for s in t.get("skid", ())]
    sk = skate_report(rig, frames, roots, 4 if clip.loop else 1, True, skid, clip.name in DETAIL, t.get("time_scale", 1.0),
                      t.get("spin"))
    rep["skate"] = sk
    bad = [(fb, r) for fb, v in sk.items() for r in v if r[2] > SKATE_RUN_CM or r[3] > SKATE_STEP_CM]
    rep["skate_cm"] = round(max([r[2] for v in sk.values() for r in v] or [0.0]), 2)
    check(not bad, f"{clip.name}: ninguna suela patina rozando el piso (peor {bad[:3]})")
    # el imán del ataque corta el avance contra un enemigo pegado: un pie clavado en el mundo mientras el clip
    # descuenta el avance patina hacia atrás. Mientras el juego mueve el cuerpo, los pies van en el aire
    # (timing 'travel_fixed': el avance no lo corta nada, p. ej. el frenado de RunStop)
    if not clip.loop and not t.get("travel_fixed") and any((roots[i + 1] - roots[i]).length > 1e-6 for i in range(n)):
        sk0 = skate_report(rig, frames, roots, 1, False, skid)
        rep["skate_no_lunge"] = sk0
        bad0 = [(fb, r) for fb, v in sk0.items() for r in v if r[2] > SKATE_RUN_CM or r[3] > SKATE_STEP_CM]
        check(not bad0, f"{clip.name}: con el avance cortado por el imán tampoco patina (peor {bad0[:3]})")
    if "airborne" in t:
        a, b = t["airborne"]
        hits = touching(rig, frames, roots, a, b)
        check(not hits, f"{clip.name}: en el aire mientras el juego lo mueve (f{a}-f{b}; tocan {hits[:4]})")
    if clip.loop:
        seam, step = NA.loop_seam_deg(rig, frames)
        rep["loop_seam_deg"] = seam
        check(seam <= 1.0, f"{clip.name}: costura del loop {seam:.2f}°")
    # velocidad del suelo de los ciclos: el pie apoyado se mueve hacia atrás a la velocidad autorada
    if "stance_l" in t:
        # apoyos de los ciclos (2 cuadros en la carrera: plant_report pide 3): el borde de la suela que menos se
        # mueve en cada apoyo, medido en el mundo con el cuerpo avanzando a la velocidad autorada
        worst_g = 0.0
        for fb, key in (("Pie.L", "stance_l"), ("Pie.R", "stance_r")):
            fs = t[key]
            runs, cur = [], [fs[0]]
            for f in fs[1:]:
                if f == cur[-1] + 1:
                    cur.append(f)
                else:
                    runs.append(cur)
                    cur = [f]
            runs.append(cur)
            for run in runs:
                if len(run) < 2:
                    continue
                # el pie rueda (talón -> plano -> punta): entre cada par de cuadros tiene que haber un borde quieto;
                # se suma lo que se corrió el borde más quieto de cada par (el resbalón acumulado del apoyo)
                d = 0.0
                for f0, f1 in zip(run, run[1:]):
                    d += min((frames[f1][fb] @ pv + roots[f1] - (frames[f0][fb] @ pv + roots[f0])).length for pv in pivl[fb])
                worst_g = max(worst_g, d * M * 100)
        rep["stance_drift_cm"] = round(worst_g, 2)
        check(worst_g <= 2.0, f"{clip.name}: en el ciclo el pie apoyado no patina ({worst_g:.2f} cm en el juego)")
    if "ground_speed_mps" in t:
        # el cuerpo avanza a root_vel en el mundo: si el pie apoyado no deriva, el suelo va a esa velocidad
        rep["ground_speed_mps"] = t["ground_speed_mps"]
    # punta de la katana
    tip_local = rig.rest_inv["KatanaBone"] @ KR.TIP_C_REST
    sp, pts = NA.tip_speeds(rig, frames, roots, "KatanaBone", tip_local)
    rep["tip_speed_mps"] = [round(v * M, 1) for v in sp]
    if "contact" in t:
        a0, a1 = t["active"]
        check(a0 <= t["contact"] <= a1, f"{clip.name}: el impacto (f{t['contact']}) está dentro de la ventana {a0}-{a1}")
        # el tramo más rápido de la punta tiene que caer en la ventana que pega (el corte se VE cuando pega)
        fmax = max(range(1, n + 1), key=lambda i: sp[i])
        rep["tip_peak"] = [fmax, round(sp[fmax] * M, 1)]
        check(a0 - 1 <= fmax <= a1 + 1, f"{clip.name}: la punta va más rápido (f{fmax}, {sp[fmax] * M:.1f} m/s) dentro de la "
                                        f"ventana {a0}-{a1}")
        reach = max(Vector((pts[i].x - roots[i].x, pts[i].y - roots[i].y)).length for i in range(a0, a1 + 1)) * M
        rep["reach_m"] = round(reach, 2)
    if "strike" in t:
        s = t["strike"]
        rep["strike_n"] = round(s / n, 4)
    return rep


# =============================================================================== muñecas
BLADE_FIX_OK, BLADE_FIX_MAX = 12.0, 25.0    # grados que la hoja se puede correr de la autorada por el tope de la muñeca
# ...en los cuadros que no cortan (kaito_rig.cutting) la hoja autorada solo dice más o menos dónde va: ahí manda la
# muñeca (SOFT_LIMIT) y se tolera más. El peor es la carga del Corte final (f1: la hoja interpolada de arriba-atrás a
# afuera pide dar vuelta el codo; la muñeca la corre 50° en un cuadro de 33 ms a mitad de la carga)
BLADE_FIX_SOFT_OK, BLADE_FIX_SOFT_MAX = 20.0, 55.0
STEP_JUMP_DEG = 35.0                        # giro de la hoja o del codo entre dos cuadros del juego que ya se ve como tirón
SHOULDER_FAIL = 120.0                       # giro del húmero (respecto del brazo en cruz) que ya no pasa nunca


def wrist_report(clip, wrists, states, fixes, ease):
    """Muñecas del clip horneado: cuánto pasan de lo cómodo (WRIST_COMFORT), la hoja corrida por el tope y los
    tirones del giro de la hoja y del codo entre cuadros."""
    out = {}
    ts = clip.timing.get("time_scale", 1.0)
    for k, S in ((0, "R"), (1, "L")):
        ex = []
        for w in wrists:
            e = 0.0
            for v, key in zip(w[k], ("flex", "rad", "twist")):
                lo, hi = KR.WRIST_COMFORT[S][key]
                e = max(e, lo - v, v - hi)
            ex.append(e)
        f = max(range(len(ex)), key=lambda i: ex[i])
        out["wrist_" + S] = {"over_comfort_max": round(max(0.0, ex[f]), 1), "at": f,
                             "frames_over": sum(1 for e in ex if e > 5.0), "pose": [round(v, 1) for v in wrists[f][k]]}
        check(ex[f] <= 15.0, f"{clip.name}: muñeca {S} cómoda (pasa {max(0.0, ex[f]):.0f}° en f{f}: flex/rad/giro "
                             f"{tuple(round(v) for v in wrists[f][k])}; {out['wrist_' + S]['frames_over']} cuadros > 5°)",
              warn=ex[f] <= 25.0)
    for k, S in ((2, "R"), (3, "L")):
        sh = [abs(w[k]) for w in wrists]
        f = max(range(len(sh)), key=lambda i: sh[i])
        out["shoulder_" + S] = round(sh[f], 1)
        # (el giro se mide respecto del brazo en cruz: con el brazo atrás o adelante, 70-90° de rotación interna es
        # natural; recién pasando SHOULDER_FAIL la manga del gi se retuerce)
        check(sh[f] <= KR.SHOULDER_COMFORT[1] + 15.0, f"{clip.name}: hombro {S} sin retorcer ({sh[f]:.0f}° en f{f})",
              warn=sh[f] <= SHOULDER_FAIL)
    for cut, ok, mx, nm in ((True, BLADE_FIX_OK, BLADE_FIX_MAX, "cortando"), (False, BLADE_FIX_SOFT_OK, BLADE_FIX_SOFT_MAX, "entre cortes")):
        fs = [f for f in range(len(fixes)) if KR.cutting(clip, f) == cut]
        if not fs:
            continue
        fx = max(fs, key=lambda i: fixes[i])
        out["blade_fix_deg" + ("" if cut else "_soft")] = round(fixes[fx], 1)
        check(fixes[fx] <= ok, f"{clip.name}: la hoja autorada entra en la mano {nm} (se corrió {fixes[fx]:.0f}° en f{fx})",
              warn=fixes[fx] <= mx)
    # tirones: el cambio por cuadro del juego que el gesto autorado no tapa (KR.step_ease: en un golpe que sacude la
    # mano, un giro grande no se ve)
    for j, nm, e in ((0, "giro de la hoja", ease[0]), (2, "codo derecho", ease[0]), (3, "codo izquierdo", ease[1])):
        d = [abs(KR._wrap(b[j] - a[j])) * ts * math.sqrt(e[f + 1]) for f, (a, b) in enumerate(zip(states, states[1:]))]
        i = max(range(len(d)), key=lambda q: d[q]) if d else 0
        out["step_" + str(j)] = round(d[i], 1) if d else 0.0
        check(not d or d[i] <= STEP_JUMP_DEG, f"{clip.name}: {nm} sin tirones ({d[i] if d else 0:.0f}° por cuadro en f{i}-f{i + 1})",
              warn=True)
    out["arm_states"] = [[round(v, 1) for v in s] for s in states]
    return out


def chain_report(rig, baked):
    """Empalmes que el código hace con crossfades cortos (kaito_clips.CHAINS): el giro local más grande entre
    el cuadro que termina y el que arranca, y cuánto se corre un pie. Un empalme de combo tiene que dar 0; uno
    que vuelve a la guardia con 0.12-0.2 s de fundido aguanta poco, pero un brazo que da media vuelta salta."""
    import kaito_clips as KC
    by = {c.name: fr for c, fr in baked}
    skip = set(KR.LEGACY)
    out = {}
    for a, fa, b, fb_, lim in KC.CHAINS:
        if a not in by or b not in by:
            continue
        Wa = by[a][fa if fa >= 0 else len(by[a]) - 1]
        Wb = by[b][fb_]
        la, lb = rig.to_local(Wa), rig.to_local(Wb)
        worst = sorted(((NA.quat_angle_deg(la[n][1], lb[n][1]), n) for n in rig.names if n not in skip), reverse=True)
        ang, bone = worst[0]
        foot = max((Wa[f].translation - Wb[f].translation).length for f in ("Pie.R", "Pie.L")) * M * 100
        # lo que se ve: cuánto se corren en el mundo los codos, las rodillas, las manos y la punta de la katana
        # (con brazos de 30 cm el antebrazo gira mucho para un hombro que baja unos centímetros)
        joint = max(((Wa[n].translation - Wb[n].translation).length * M * 100, n)
                    for n in ("Antebrazo.R", "Antebrazo.L", "Mando.R", "Mando.L", "Tibia.R", "Tibia.L", "cabeza", "KatanaBone"))
        key = f"{a}{'@' + str(fa) if fa >= 0 else ''}->{b}{'@' + str(fb_) if fb_ else ''}"
        out[key] = [round(ang, 1), bone, round(foot, 1), round(joint[0], 1), joint[1]]
        check(ang <= lim and foot <= 4.0, f"empalme {key}: {ang:.1f}° en {bone} (tope {lim}°), pies {foot:.1f} cm, "
                                          f"articulaciones {joint[0]:.1f} cm ({joint[1]})"
                                          + ("" if ang <= lim else f"; siguen {[(n, round(d)) for d, n in worst[1:4]]}"))
    return out


# =============================================================================== tirones de un cuadro
# Lo que las hojas de revisión no ven porque cae entre dos cuadros dibujados: una pierna que pasa de una rodilla arriba a
# kiza de un cuadro al otro (PrayIncense f40-41: 132° y la rodilla 22 cm), la muerte que estira las dos piernas en un
# cuadro, la mano libre que da 80° al entrar al zanshin. Se mide en el mundo del clip (con el avance del juego), por
# cuadro del juego. 'snap_ok' = [[a, b], ...] tramos de cuadros (f -> f+1 con a <= f < b) donde el tirón es a propósito
# y lo tapa el gesto (el sacudón del golpe recibido, el tajo); los cortes ('cut', el teletransporte) no cuentan
SNAP_LEG_DEG = 45.0          # un hueso de la pierna que gira más que esto en un cuadro
# una articulación a menos de 20 cm del piso que se corre más de 12 cm en un cuadro (3.6 m/s: un paso rápido de Kaito
# lleva el pie a 2-3 m/s; una pierna que se reacomoda de golpe, a 6-20)
SNAP_LOW_Z_CM, SNAP_LOW_CM = 20.0, 12.0
SNAP_HAND_DEG = 45.0         # una mano (o un dedo) que gira más que esto
SNAP_HOLD_DEG = 20.0         # ...y durante la pose quieta ('hold': el zanshin con la cámara encima)
SNAP_ELBOW_DEG = 60.0        # el codo que gira alrededor de la recta hombro-muñeca (con el codo a más de 3 cm de ella)
SNAP_TWIST_DEG = 60.0        # el húmero que gira sobre su eje (la manga se retuerce de golpe)
SNAP_LEGS = ("Pierna.l", "Pierna.r", "Tibia.L", "Tibia.R", "Pie.L", "Pie.R")


def _twist_y(q):
    """Giro (grados) de un cuaternión local sobre el eje Y del hueso (su largo)."""
    return math.degrees(2.0 * math.atan2(q.y, q.w))


def snap_report(rig, clip, frames, roots):
    t = clip.timing
    ts = t.get("time_scale", 1.0)
    n = clip.frames
    if clip.loop:
        return {}            # los ciclos tienen su costura y su patinada; el pie en vuelo va rápido a propósito
    ok_rng = [tuple(r) for r in t.get("snap_ok", ())]
    cuts = list(t.get("cut", ()))
    # el cuadro en que lo golpean es un sacudón a propósito (el solver tampoco pone topes ahí)
    if "impact" in t:
        ok_rng.append((t["impact"] - 1, t["impact"]))
    ok_rng += [(b - 1, b) for b in t.get("burst", ())]
    hold = t.get("hold")
    fingers = {S: [b for b in rig.subtree("Mando." + S) if not b.endswith("_end")] for S in "LR"}
    W = frames
    loc = [rig.to_local(w) for w in W]
    hits = []

    def jp(f, b, tail):
        m = W[f][b]
        p = (m @ Vector((0.0, rig.length[b], 0.0))) if tail else m.translation
        return p + roots[f]

    def elbow(f, S):
        sh, el, wr = (W[f][b].translation for b in ("Brazo." + S, "Antebrazo." + S, "Mando." + S))
        ax = wr - sh
        if ax.length < 1e-6:
            return None
        ax.normalize()
        v = el - sh
        v = v - ax * v.dot(ax)
        return v.normalized() if v.length * M * 100 >= 3.0 else None

    for f in range(n):
        if any(f < c < f + 1 for c in cuts) or any(a <= f < b for a, b in ok_rng):
            continue
        A, B = W[f], W[f + 1]
        rot = lambda b: NA.quat_angle_deg(A[b].to_quaternion(), B[b].to_quaternion()) * ts
        in_hold = hold is not None and hold[0] <= f < hold[1]
        # en el tajo la estela tapa la mano y el codo (KR.cutting); las piernas y lo que roza el piso, siempre
        smear = KR.cutting(clip, f) or KR.cutting(clip, f + 1)
        still = (roots[f + 1] - roots[f]).length < 1e-6
        # los cuadros de una frenada que siguen la carrera ('lead') mueven las piernas como Run a 30 fps (50-60° por cuadro:
        # el ciclo dura 0.4 s); run_stop_report mide que sean los de Run
        for b in (() if "run_phase" in t and f < t.get("lead", 2) - 1 else SNAP_LEGS):
            r = rot(b)
            if r > SNAP_LEG_DEG:
                hits.append((round(r), f, b, "gira"))
            for tail in (False, True):
                pa, pb = jp(f, b, tail), jp(f + 1, b, tail)
                # (con el cuerpo quieto: en un avance del juego el pie en el aire va con el cuerpo)
                if still and min(pa.z, pb.z) * M * 100 < SNAP_LOW_Z_CM:
                    d = (pb - pa).length * M * 100 * ts
                    if d > SNAP_LOW_CM:
                        hits.append((round(d), f, b + (" punta" if tail else ""), "cm junto al piso"))
        if smear:
            continue
        for S in "LR":
            bones = fingers[S] if in_hold else ["Mando." + S]
            lim = SNAP_HOLD_DEG if in_hold else SNAP_HAND_DEG
            r, b = max((rot(b), b) for b in bones)
            if r > lim:
                hits.append((round(r), f, b, "gira" + (" en la pose quieta" if in_hold else "")))
            ea, eb = elbow(f, S), elbow(f + 1, S)
            if ea is not None and eb is not None:
                sw = math.degrees(math.acos(max(-1.0, min(1.0, ea.dot(eb))))) * ts
                if sw > SNAP_ELBOW_DEG:
                    hits.append((round(sw), f, "codo " + S, "gira"))
            tw = abs(KR._wrap(_twist_y(loc[f + 1]["Brazo." + S][1]) - _twist_y(loc[f]["Brazo." + S][1]))) * ts
            if tw > SNAP_TWIST_DEG:
                hits.append((round(tw), f, "Brazo." + S, "se retuerce"))
    hits.sort(key=lambda h: (h[1], -h[0]))
    rows = [f"f{f}-{f + 1} {b} {v}{'°' if u != 'cm junto al piso' else ' cm'}{'' if u in ('gira', 'cm junto al piso') else ' ' + u}"
            for v, f, b, u in hits]
    check(not hits, f"{clip.name}: sin tirones de un cuadro ({len(hits)}: {', '.join(rows[:10])}{' ...' if len(rows) > 10 else ''})",
          warn="--strict-snaps" not in argv)
    return {"snaps": rows}


def run_stop_report(rig, baked):
    """Las frenadas arrancan en un cuadro de Run ('run_phase') y lo siguen hasta que apoyan ('lead'): el fundido de 0.1 s
    mezcla Run, que sigue, con el clip, que también sigue. El cuadro j de la frenada contra Run 2j cuadros horneados más
    (Run va a 60 fps), todo el cuerpo (giro local del hueso que más difiere); y desde el arranque hasta un cuadro después
    de la carga, nada salta: la cadera, el tronco y la cabeza giran como mucho RUN_STOP_BODY_STEP por cuadro y los brazos
    RUN_STOP_ARM_STEP (antes la pose de frenada entraba entera en un cuadro)."""
    by = {c.name: (c, fr) for c, fr in baked}
    if "Run" not in by:
        return {}
    run_c, run_f = by["Run"]
    body = ("Root", "tronco", "cabeza")
    arms = ("Hombro.L", "Hombro.R", "Brazo.L", "Brazo.R", "Antebrazo.L", "Antebrazo.R", "Mando.L", "Mando.R")
    bones = [n for n in rig.names if n not in KR.LEGACY]
    out = {}
    for c, fr in baked:
        ph = c.timing.get("run_phase")
        if ph is None:
            continue
        k0, P = round(ph * run_c.frames), c.timing.get("lead", 2)
        lead = []
        for j in range(P):
            la, lb = rig.to_local(run_f[(k0 + 2 * j) % run_c.frames]), rig.to_local(fr[j])
            d, b = max((NA.quat_angle_deg(la[n][1], lb[n][1]), n) for n in bones)
            lead.append((j, round(d, 1), b))
        steps = []
        for f in range(P + 2):
            la, lb = rig.to_local(fr[f]), rig.to_local(fr[f + 1])
            db = max((NA.quat_angle_deg(la[n][1], lb[n][1]), n) for n in body)
            da = max((NA.quat_angle_deg(la[n][1], lb[n][1]), n) for n in arms)
            # mientras sigue la carrera, lo que el brazo de Run ya se mueve en ese cuadro (casi estirado, el izquierdo gira
            # 40-50° por cuadro en algunas fases) es el tope
            lim = RUN_STOP_ARM_STEP
            if f + 1 < P:
                ra = rig.to_local(run_f[(k0 + 2 * f) % run_c.frames])
                rb = rig.to_local(run_f[(k0 + 2 * f + 2) % run_c.frames])
                lim = max(lim, max(NA.quat_angle_deg(ra[n][1], rb[n][1]) for n in arms) + 5.0)
            steps.append((f, round(db[0], 1), db[1], round(da[0], 1), da[1], round(lim, 1)))
        out[c.name] = {"lead": lead, "steps": steps}
        wl = max(lead, key=lambda r: r[1])
        wb = max(steps, key=lambda r: r[1])
        wa = max(steps, key=lambda r: r[3] - r[5])
        check(wl[1] <= RUN_STOP_LEAD_DEG and wb[1] <= RUN_STOP_BODY_STEP and wa[3] <= wa[5],
              f"{c.name}: sigue a Run desde la fase {k0}/{run_c.frames} ({', '.join(f'f{j} {d:.0f}° {b}' for j, d, b in lead)}; "
              f"por cuadro hasta f{P + 2}: cuerpo {wb[1]:.0f}° ({wb[2]} f{wb[0]}), brazos {wa[3]:.0f}° ({wa[4]} f{wa[0]}, tope {wa[5]:.0f}°))")
    return out


# (en el cuadro del apoyo el brazo izquierdo pasa del vaivén de la carrera al del pecho: 35-40° es el sacudón del frenazo)
RUN_STOP_LEAD_DEG, RUN_STOP_BODY_STEP, RUN_STOP_ARM_STEP = 15.0, 15.0, 40.0


def mesh_floor(meshes, rng):
    """Altura mínima (m) de la malla evaluada por cuadro (espacio C: la armadura en TO_C)."""
    out = []
    for f in rng:
        bpy.context.scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        z = min(float(NA.world_verts(o, dg)[:, 2].min()) for o in meshes)
        out.append(z)
        if z < -0.04 and "--floor-debug" in argv:
            import numpy as np
            for o in meshes:
                w = NA.world_verts(o, dg)
                i = int(np.argmin(w[:, 2]))
                gs = sorted(((g.weight, o.vertex_groups[g.group].name) for g in o.data.vertices[i].groups), reverse=True)[:2] if o.vertex_groups else []
                print(f"    f{f} {o.name}: z {w[i, 2]:.3f} en {tuple(round(x, 2) for x in w[i])} {gs}")
    return out


def sheet_frames(clip):
    if isinstance(clip, NA.ProcClip):
        return list(range(0, clip.frames, max(1, clip.frames // 8)))[:10]
    fs = sorted({k.frame for k in clip.keys} | {clip.timing[k] for k in ("apex", "contact", "strike") if k in clip.timing})
    if len(fs) > 10:
        step = (len(fs) - 1) / 9.0
        fs = sorted({fs[round(i * step)] for i in range(10)})
    return fs


def frame_label(clip, f):
    t = clip.timing
    tags = []
    if t.get("apex") == f:
        tags.append("carga")
    if t.get("contact") == f:
        tags.append("impacto")
    if t.get("strike") == f:
        tags.append("tajo")
    return f"f{f}" + (" " + "/".join(tags) if tags else "")


# =============================================================================== principal
def main():
    t0 = time.time()
    print("origen:", SRC)
    before = fbxcheck.summary(SRC)
    arm = C.load(SRC)
    scn = bpy.context.scene
    scn.render.fps = NA.FPS
    body = bpy.data.objects["Cuerpo"]
    kat = bpy.data.objects["Isan"]
    meshes = [body, kat]
    for a in list(bpy.data.actions):
        bpy.data.actions.remove(a)
    C.rest(arm, True)
    print("esqueleto de juego:", KR.game_skeleton(arm, body))
    print("nudo de la bandana (caras borradas, caras del moño):", KR.bandana_knot(body))
    C.limit_weights(body)
    C.flat_normals(body)
    C.flat_normals(kat)
    C.strip_images()
    C.rest(arm, False)
    arm_world0 = arm.matrix_world.copy()
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    rig = KR.c_rig(arm)
    solver = KR.Solver(rig)
    import kaito_clips as KC
    clips = KC.CLIPS
    if ONLY:
        names = ONLY.split(",")
        clips = [c for c in clips if c.name in names]
    baked, reports, rootsd = [], {}, {}
    for clip in clips:
        states = KR.arm_path(rig, solver, clip)
        misses, wrists, fixes = [], [], []
        it = iter(states)

        fr_ = iter(range(clip.frames + 1))

        def solve(pose, c):
            misses.append(dict(solver.solve(pose, c, next(it), KR.frame_limits(clip, next(fr_)))))
            wrists.append((solver.wrist["R"], solver.wrist["L"], solver.shoulder["R"], solver.shoulder["L"]))
            fixes.append(solver.blade_fix)
        frames, ctrls, roots = NA.bake_clip(rig, clip, solve, ())
        reports[clip.name] = lint_clip(rig, clip, frames, ctrls, roots, misses)
        reports[clip.name].update(wrist_report(clip, wrists, states, fixes, solver.path_ease))
        reports[clip.name].update(snap_report(rig, clip, frames, roots))
        baked.append((clip, frames))
        rootsd[clip.name] = roots
    reports["_chains"] = chain_report(rig, baked)
    reports["_run_stop"] = run_stop_report(rig, baked)
    act, ranges = NA.write_pack(arm, rig, baked, start=1, gap=GAP, name="KaitoB3")
    last = max(b for a, b in ranges.values())
    # nada atraviesa el piso (la armadura en el espacio C para medir; el FBX se exporta con la original)
    arm.matrix_world = KR.TO_C
    for clip, frames in baked:
        a, b = ranges[clip.name]
        zs = mesh_floor(meshes, range(a, b + 1))
        lo = min(zs)
        reports[clip.name]["min_z_cm"] = round(lo * M * 100, 1)
        allow = clip.timing.get("floor_ok", -0.02)
        check(lo * M >= allow, f"{clip.name}: nada bajo el piso (mín {lo * M * 100:.1f} cm en f{zs.index(lo)})")
    arm.matrix_world = arm_world0
    if REPORT:
        with open(REPORT, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(reports, fh, indent=0)

    # ---------------------------------------------------------------- export
    tmp = None
    if not ONLY and (EXPORT or RENDERS):
        tmp = os.path.join(tempfile.gettempdir(), "nindo_kaito_b3", "kaitooo.fbx")
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        scn.frame_start, scn.frame_end = 1, last
        scn.frame_set(0)
        C.export(tmp, bake_anim_use_all_actions=False)
        after = fbxcheck.summary(tmp)
        validate_fbx(before, after)
        verify_roundtrip(tmp, rig, baked, ranges)
        if EXPORT:
            if failures:
                print("NO SE EXPORTA: fallaron chequeos")
            else:
                shutil.copyfile(tmp, FBX)
                write_sidecar(baked, ranges, reports, after)
                print("ESCRITO", FBX, f"{os.path.getsize(FBX) / 1e6:.2f} MB, cuadros 1..{last}")

    # ---------------------------------------------------------------- renders
    if RENDERS:
        import kaito_review as RV
        rv = RV.Review(arm, meshes, RENDERS)
        for clip, frames in baked:
            a, b = ranges[clip.name]
            fs = sheet_frames(clip)
            r = reports[clip.name]
            r["summary"] = summary(clip, r)
            print(rv.clip_sheet(clip, a, rootsd[clip.name], fs, [frame_label(clip, f) for f in fs], r,
                                gait=isinstance(clip, NA.ProcClip)))
    if BLEND:
        bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print(f"listo en {time.time() - t0:.1f} s; avisos {len(warnings)}")
    if failures:
        print("FALLARON", len(failures), "chequeos:")
        for f in failures:
            print("   -", f)
        sys.exit(1)


def summary(clip, r):
    out = []
    if "plant_drift_cm" in r:
        out.append(f"pies {r['plant_drift_cm']:.1f} cm")
    if "loop_seam_deg" in r:
        out.append(f"costura {r['loop_seam_deg']:.2f}°")
    if "reach_m" in r:
        out.append(f"alcance {r['reach_m']:.2f} m")
    if "ground_speed_mps" in r:
        out.append(f"{r['ground_speed_mps']:.1f} m/s")
    return ", ".join(out)


def validate_fbx(A, B):
    """El FBX nuevo tiene los mismos nodos y el mismo bind pose que el anterior (solo cambian padres)."""
    missing = [n for n in A["models"] if n not in B["models"]]
    check(not missing, f"FBX: están todos los nodos ({len(A['models'])} -> {len(B['models'])}; faltan {missing[:5]})")
    worst = (0.0, 0.0, "")
    for n, ma in A["bind"].items():
        mb = B["bind"].get(n)
        if mb is None:
            continue
        ang = fbxcheck._rot_angle(ma, mb)
        dt = math.dist(ma[12:15], mb[12:15])
        if (ang, dt) > worst[:2]:
            worst = (ang, dt, n)
    check(worst[0] <= 0.02 and worst[1] <= 0.005, f"FBX: bind pose igual (peor {worst[0]:.4f}° / {worst[1]:.5f} en {worst[2]})")
    check(B["fps"] == 30, f"FBX: 30 fps ({B['fps']})")
    check(list(B["stacks"]) == ["Scene"], f"FBX: una sola toma 'Scene' ({list(B['stacks'])})")
    check(not B["video_bytes"], "FBX: sin texturas embebidas")


def verify_roundtrip(path, rig, baked, ranges):
    """Re-importa el FBX y compara cuadros horneados con lo leído (posición de manos, pies, cabeza y katana)."""
    scn = bpy.context.scene
    keep_frame = scn.frame_current
    objs0, acts0, meshes0 = set(bpy.data.objects), set(bpy.data.actions), set(bpy.data.meshes)
    bpy.ops.import_scene.fbx(filepath=path, anim_offset=0.0)
    new = [o for o in bpy.data.objects if o not in objs0]
    arm2 = next(o for o in new if o.type == 'ARMATURE')
    acts = [a for a in bpy.data.actions if a not in acts0]
    C.bind_slots(arm2, acts)
    if acts:
        C.use_action(arm2, acts[0])
    parents_ok = all(arm2.data.bones[c].parent.name == p for c, p in (("Mando.R", "Antebrazo.R"), ("Mando.L", "Antebrazo.L"),
                                                                      ("Pie.L", "Tibia.L"), ("Pie.R", "Tibia.R")))
    check(parents_ok, "FBX: manos bajo los antebrazos y pies bajo las tibias")
    inv = KR.TO_C.inverted()
    best = None
    for off in (0, 1, -1):
        worst = (0.0, "")
        for clip, frames in baked:
            a, b = ranges[clip.name]
            for i in sorted({0, clip.frames // 2, clip.frames}):
                scn.frame_set(a + i + off)
                for n in ("Mando.R", "Mando.L", "Pie.R", "Pie.L", "cabeza", "KatanaBone", "Root"):
                    want = inv @ frames[i][n]
                    got = arm2.pose.bones[n].matrix
                    d = (want.translation - got.translation).length * M * 100
                    if d > worst[0]:
                        worst = (d, f"{clip.name}@{i}:{n}")
        if best is None or worst[0] < best[1][0]:
            best = (off, worst)
    off, worst = best
    check(worst[0] <= 0.5, f"FBX re-importado = horneado (peor {worst[0]:.2f} cm en {worst[1]}; desfase de cuadro {off})")
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    for a in [a for a in bpy.data.actions if a not in acts0]:
        bpy.data.actions.remove(a)
    for m in [m for m in bpy.data.meshes if m not in meshes0]:
        bpy.data.meshes.remove(m)
    scn.frame_set(keep_frame)


def write_sidecar(baked, ranges, reports, fbx_summary):
    clipd = {}
    for clip, frames in baked:
        a, b = ranges[clip.name]
        t = dict(clip.timing)
        n = float(clip.frames)
        norm = {}
        for k in ("apex", "contact", "combo", "strike", "cancel"):
            if k in t:
                norm[k] = round(t[k] / n, 4)
        for k in ("active", "hold", "recover"):
            if k in t:
                norm[k] = [round(t[k][0] / n, 4), round(t[k][1] / n, 4)]
        if "lunge" in t:
            norm["lunge"] = [round(t["lunge"][0] / n, 4), round(t["lunge"][1] / n, 4), t["lunge"][2]]
        rep = reports[clip.name]
        # 'seconds' es lo que dura EN EL JUEGO: los ciclos horneados densos se tocan a x time_scale (kaito_gait)
        clipd[clip.name] = {
            "first": a, "last": b, "frames": clip.frames, "loop": clip.loop,
            "seconds": round(clip.frames / NA.FPS / t.get("time_scale", 1.0), 4), "time_scale": t.get("time_scale", 1.0),
            "timing": t, "normalized": norm,
            "events": [{"frame": e["frame"], "t": round(e["frame"] / n, 4), "fn": e["fn"]} for e in clip.events],
            "notes": clip.notes,
            "lint": {k: v for k, v in rep.items() if k not in ("plants", "tip_speed_mps", "summary", "arm_states")},
        }
    info = {"fps": NA.FPS, "take": "Scene", "units_per_meter": round(KR.U_PER_M, 4),
            "facing": "frente +Y de la armadura (Blender +X): modelYaw 90 en NindoContent, como siempre",
            "skeleton": "de juego: Mando bajo Antebrazo, Pie bajo Tibia; Target*/Pole* quedan sin pesos y quietos (kits)",
            "chains": reports.get("_chains", {}), "clips": clipd}
    with open(FBX + ".json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(info, fh, indent=1, ensure_ascii=False)
    write_events_cs(clipd)


# los momentos con nombre de los clips (eventos del sidecar) también van al código: el sidecar está fuera de Resources y
# el FBX no trae AnimationEvents, así que las escenas (santuario, prólogo, final) tenían que copiar cuadros a mano y un
# clip re-tomado las dejaba esperando un número viejo. PlayerController.ClipEventTime lee esta tabla
EVENTS_CS = os.path.join(ROOT, "Nindo", "Assets", "Nindo", "Scripts", "Player", "KaitoClipEvents.cs")


def write_events_cs(clipd):
    rows = []
    for name, c in clipd.items():
        for e in c["events"]:
            fn = e["fn"]
            if fn[:1].islower():               # los de historia (los de combate, Strike / FootR..., los usa el código)
                rows.append(f'            {{ ("{name}", "{fn}"), {e["t"]:.4f}f }},')
    text = "\n".join([
        "using System.Collections.Generic;",
        "",
        "namespace Nindo",
        "{",
        "    /// <summary>",
        "    /// GENERADO por Tools/Blender/anim/kaito/build_kaito.py (no editar a mano): tiempo normalizado (0..1 del clip) de",
        "    /// cada momento con nombre de los clips de historia de Kaito (incense_take, palms, release, offer...), sacado de",
        "    /// los 'events' de kaitooo.fbx.json. Lo lee PlayerController.ClipEventTime.",
        "    /// </summary>",
        "    public static class KaitoClipEvents",
        "    {",
        "        static readonly Dictionary<(string, string), float> times = new Dictionary<(string, string), float>",
        "        {",
        *rows,
        "        };",
        "",
        "        public static bool TryGet(string state, string evt, out float normalized) => times.TryGetValue((state, evt), out normalized);",
        "    }",
        "}",
        ""])
    with open(EVENTS_CS, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    meta = EVENTS_CS + ".meta"
    if not os.path.exists(meta):
        sys.path.insert(0, os.path.join(ROOT, "Tools", "Unity"))
        import unity_yaml as UY
        UY.write_meta(EVENTS_CS, "MonoImporter:\n  externalObjects: {}\n  serializedVersion: 2\n  defaultReferences: []\n"
                                 "  executionOrder: 0\n  icon: {instanceID: 0}\n  userData: \n  assetBundleName: \n"
                                 "  assetBundleVariant: \n")
    print("ESCRITO", EVENTS_CS, len(rows), "momentos")


main()
