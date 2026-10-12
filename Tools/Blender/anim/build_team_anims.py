"""Clips nuevos de los personajes del equipo: autoría, chequeos, FBX de animación y hojas de revisión.

  blender -b --factory-startup --python Tools/Blender/anim/build_team_anims.py -- <ninja|sumo|goro|grandpa> [opciones]
    --export        escribe Nindo/Assets/Nindo/Art/Characters/TeamAnims/<Personaje>Anims.fbx (+ .json)
    --renders DIR   una hoja por clip (cámara del juego de frente y de perfil, perfil ortográfico)
    --only A,B      solo esos clips (para iterar; no exporta)
    --frames F      con --renders: cuadros de la hoja (si no, los del timing del clip)
    --fbx PATH      con --export: escribe el FBX (y su .json) ahí en vez de TeamAnims (para medir sin tocar el repo;
                    con --only exporta solo esos clips)

El FBX de animación lleva SOLO la armadura (mismos nombres, padres y reposo que el modelo, exportada con los
mismos ajustes del equipo que usan los export_<personaje>.py): Unity liga sus clips por ruta de transform al
modelo de siempre, que no se toca (malla, pesos, kits de zona, .meta y GUID quedan como estaban).

Falla (código 1) si un chequeo no pasa: manos y pies que no llegan, pies apoyados que patinan, costuras de
loop, golpes cuyo contacto no cae en la ventana activa de EnemyArchetypes.cs, punta del arma rápida en la
pausa del aviso, avisos que no cambian la silueta vista desde la cámara del juego.
"""
import sys, os, json, math, re, time, importlib
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
for p in (HERE, os.path.join(ROOT, "Tools", "Blender"), os.path.join(ROOT, "Tools", "Blender", "characters")):
    if p not in sys.path:
        sys.path.insert(0, p)
sys.dont_write_bytecode = True

import bpy
from mathutils import Vector, Matrix
import nindo_anim as NA
import team_rig as T

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
CHAR = argv[0] if argv and not argv[0].startswith("--") else "ninja"


def opt(name, default=None):
    return argv[argv.index(name) + 1] if name in argv else default


EXPORT = "--export" in argv
RENDERS = opt("--renders")
ONLY = opt("--only")
FRAMES = opt("--frames")
OUT_DIR = os.path.join(ROOT, "Nindo", "Assets", "Nindo", "Art", "Characters", "TeamAnims")
FBX = opt("--fbx") or os.path.join(OUT_DIR, CHAR.capitalize() + "Anims.fbx")
ARCHETYPES = os.path.join(ROOT, "Nindo", "Assets", "Nindo", "Scripts", "Enemies", "EnemyArchetypes.cs")
GAP = 10
failures, warnings = [], []


def check(ok, msg, warn=False):
    print(("  ok   " if ok else ("  WARN " if warn else "  FAIL ")) + msg)
    if not ok:
        (warnings if warn else failures).append(msg)


# ------------------------------------------------------------------------------- golpes del juego
def archetype_hits(func_names):
    """Hit("Estado", ...) de las funciones dadas de EnemyArchetypes.cs:
    {estado: [(activeStart, activeEnd, apex, función, embestida, velocidad, lungeFrom), ...]}.
    Los apex y lungeFrom con nombre (NinjaApex1 = 0.50f) se resuelven con las constantes del archivo; embestida y
    velocidad, con los valores por omisión de Hit() (0.8 m, 1); lungeFrom None = sin 'from:' (embestida lineal)."""
    src = open(ARCHETYPES, encoding="utf-8").read()
    consts = {m.group(1): float(m.group(2)) for m in re.finditer(r"(\w+)\s*=\s*([\d.]+)f", src)}
    out = {}
    for fn in func_names:
        m = re.search(r"public static \w+ " + fn + r"\([^)]*\)\s*\{(.*?)\n        \}", src, re.S)
        if not m:
            continue
        for h in re.finditer(r'Hit\("(\w+)",\s*[\d.]+,\s*([\d.]+)f,\s*([\d.]+)f(.*?)\);', m.group(1)):
            st, a0, a1, rest = h.group(1), float(h.group(2)), float(h.group(3)), h.group(4)
            am = re.search(r"apex:\s*([\w.]+)", rest)
            apex = None
            if am:
                v = am.group(1).rstrip("f")
                apex = consts.get(v, None) if not re.match(r"[\d.]+$", v) else float(v)
            lm = re.search(r"lunge:\s*([\d.]+)f", rest)
            sm = re.search(r"speed:\s*([\d.]+)f", rest)
            fm = re.search(r"from:\s*([\w.]+)", rest)
            air = bool(re.search(r"air:\s*true", rest))
            frm = None
            if fm:
                v = fm.group(1).rstrip("f")
                frm = consts.get(v, None) if not re.match(r"[\d.]+$", v) else float(v)
            out.setdefault(st, []).append((a0, a1, apex, fn, float(lm.group(1)) if lm else 0.8, float(sm.group(1)) if sm else 1.0, frm, air))
    return out


# las variantes de zona reusan los clips con sus propios números: también tienen que coincidir
ARCH_FUNCS = {"ninja": ["Ninja", "NinjaElite", "NinjaMountainMoves", "NinjaLakeMoves", "NinjaBambooMoves"],
              "sumo": ["Sumo", "Ozeki", "SumoMountainMoves", "SumoLakeMoves", "SumoBambooMoves"], "goro": ["Goro"], "grandpa": []}


# ------------------------------------------------------------------------------- mediciones
def canon_track(ch, frames, roots, bone, local):
    """Recorrido de un punto de un hueso en el marco de autoría (m), con el avance del transform incluido."""
    return [ch.Pc(W[bone] @ local + r) for W, r in zip(frames, roots)]


def plants(ch, frames, roots, ctrls):
    """Apoyos de cada pie (el tobillo casi quieto y a la altura de apoyo) y cuánto se corre dentro de cada uno el
    punto de la suela que menos se movió (punta, talón o planta: un pie que rueda sobre la punta no patina)."""
    R = ch.rig
    out = {}
    for k in "rl":
        fb = ch.side[k]["foot"]
        # puntos de la suela en el espacio del hueso del pie: bajo el tobillo, punta y talón (medidos en la malla)
        a0 = ch.land["ankle_" + k]
        so = ch.sole[k]
        loc = [R.rest_inv[fb] @ ch.P(a0 + v) for v in (Vector((0.0, 0.0, so["toe"].z)), so["toe"], so["heel"])]
        tracks = [canon_track(ch, frames, roots, fb, l) for l in loc]
        ankle = canon_track(ch, frames, roots, fb, Vector())
        segs, cur = [], None
        sz = ch.land["sole_z"][k]
        for i in range(1, len(ankle)):
            sp = (ankle[i] - ankle[i - 1]).length * T.FPS
            low = ankle[i].z < sz + 0.035
            if sp < 0.5 and low:
                cur = [i - 1, i] if cur is None else [cur[0], i]
            else:
                if cur and cur[1] - cur[0] >= 3:
                    segs.append(cur)
                cur = None
        if cur and cur[1] - cur[0] >= 3:
            segs.append(cur)
        rep = []
        for a, b in segs:
            drift = min(max(Vector((p.x - tr[a].x, p.y - tr[a].y)).length for p in tr[a:b + 1]) for tr in tracks)
            rep.append({"frames": [a, b], "drift_cm": round(drift * 100.0, 2)})
        out[k] = rep
    return out


def lint(ch, clip, frames, ctrls, roots, drops, misses, hits):
    rep = {}
    t = clip.timing
    n = clip.frames
    hm = [max(m["hand_r"], m["hand_l"]) / ch.u for m in misses]
    lm = [m["legs"] / ch.u for m in misses]
    mh, ml = max(hm), max(lm)
    fh, fl, fd = hm.index(mh), lm.index(ml), drops.index(max(drops))
    rep["reach_miss_cm"] = {"hands": round(mh * 100, 1), "legs": round(ml * 100, 1)}
    check(ml <= 0.02, f"{clip.name}: los pies llegan (faltó {ml * 100:.1f} cm en f{fl})")
    side = "derecha" if misses[fh]["hand_r"] >= misses[fh]["hand_l"] else "izquierda"
    check(mh <= 0.03, f"{clip.name}: las manos llegan (faltó {mh * 100:.1f} cm en f{fh}, {side})", warn=mh <= 0.06)
    rep["hip_drop_cm"] = round(max(drops) * 100, 1)
    check(max(drops) <= 0.04, f"{clip.name}: la cadera no se cae para alcanzar los pies ({max(drops) * 100:.1f} cm en f{fd})", warn=True)
    pl = plants(ch, frames, roots, ctrls)
    touch = touch_segments(ch, frames)
    rep["plants"] = pl
    worst = max([p["drift_cm"] for v in pl.values() for p in v] or [0.0])
    allow = t.get("slide_ok", 2.0)
    where = "; ".join(f"{k} f{p['frames'][0]}-f{p['frames'][1]} {p['drift_cm']}" for k, v in pl.items() for p in v if p["drift_cm"] > 1.0)
    check(worst <= max(2.0, allow), f"{clip.name}: pies apoyados quietos (deriva máx. {worst:.1f} cm{'; ' + where if where else ''})")
    if clip.loop:
        # la costura real (el último cuadro resuelto contra el primero, team_rig.bake): la de loop_seam_deg mira el cuadro
        # ya copiado y daba 0 siempre
        seam = getattr(clip, "seam_deg", 0.0)
        rep["loop_seam_deg"] = round(seam, 3)
        check(seam <= 1.0, f"{clip.name}: costura del loop {seam:.2f}°")
    wrist_checks(ch, clip, frames, rep)
    pop_checks(ch, clip, frames, ctrls, rep)
    grip_checks(ch, clip, frames, ctrls, rep)
    blade_checks(ch, clip, frames, rep)
    w = ch.weapon_info
    if "contact" in t:
        a = t["contact"]
        if w and w["kind"] == "katana":
            bone, local = ch.spec["weapon"]["bone"], w["tip_local"]
        elif w and w["kind"] == "club":
            bone = ch.spec["weapon"]["bone"]
            local = Vector((0.0, w["head_center"] * ch.u, 0.0))
        else:
            hk = t.get("striker", "r")
            if hk.startswith("foot_"):
                bone, local = ch.side[hk[5:]]["foot"], Vector()
            else:
                bone, local = ch.side[hk]["hand"], Vector((0.0, ch.hand_info[hk]["len"], 0.0))
        tip = canon_track(ch, frames, roots, bone, local)
        # pausa y pico se miden respecto del cuerpo (sin el avance del transform: en una embestida el cuerpo entero
        # vuela, lo que importa es que el arma quede quieta en la pausa y que el golpe sea lo más rápido del clip)
        rel = canon_track(ch, frames, [Vector()] * len(frames), bone, local)
        sp = [0.0] + [(rel[i] - rel[i - 1]).length * T.FPS for i in range(1, len(rel))]
        rep["tip_speed_mps"] = [round(v, 1) for v in sp]
        ap = t["apex"]
        h0, h1 = t.get("hold", [ap, ap])
        qmax = max(sp[h0 + 1:h1 + 1] or [0.0])
        rep["hold_tip_mps"] = round(qmax, 2)
        check(qmax <= 2.5, f"{clip.name}: la punta casi quieta en la pausa del aviso f{h0}-f{h1} ({qmax:.1f} m/s)")
        act = t.get("active", [a, a + 2])
        peak = max(range(ap, min(n, act[1] + 2) + 1), key=lambda i: sp[i])
        rep["peak_frame"] = peak
        check(ap < peak <= act[1] + 1, f"{clip.name}: la punta va más rápido en el golpe (pico f{peak}, golpe f{ap}-f{act[1]})")
        # el golpe del juego: activeStart = contacto / largo (±1 cuadro), apex = fin de la pausa
        st = t.get("state", clip.name)
        lf = t.get("lunge_from")
        for a0, a1, apex, fn, hl, hs, frm, air in hits.get(st, []):
            ok = abs(a0 - a / n) <= 1.0 / n + 1e-3 and (apex is None or abs(apex - ap / n) <= 1.0 / n + 1e-3)
            check(ok, f"{clip.name}: {fn}() Hit(\"{st}\") activo {a0:.2f}-{a1:.2f} apex {apex} vs clip contacto "
                      f"{a / n:.3f} apex {ap / n:.3f}")
            # la embestida en cuadros del clip arranca donde el clip la autoró (sin 'from:' es la lineal de siempre: se
            # mide abajo como variante, el Ōzeki que se reemplaza)
            if lf is not None and hl > 0.0:
                check(frm is None or abs(frm - lf / n) <= 0.5 / n, f"{clip.name}: {fn}() Hit(\"{st}\") from {frm} vs clip "
                      f"lunge_from {lf / n:.4f} (f{lf})", warn=frm is None)
            # las variantes que reusan el clip con otra embestida (o con otra velocidad): lo que se corre un pie apoyado
            # con el avance que aplica el juego, medido sobre los apoyos del clip (aviso, no falla: es su número). Un clip
            # cuyos pies vuelan durante la embestida aguanta cualquier largo; uno con un pie clavado patina la diferencia
            if t.get("lunge") is not None and hl > 0.0 and clip.travel_table is not None:
                trv = game_travel(n, ap, a, hl, t.get("windup", 0.55), hs, frm, air=air)
                sk = variant_skate(touch, clip.travel_table, trv)
                rep.setdefault("variant_skate_cm", {})[fn] = round(sk * 100.0, 1)
                check(sk <= 0.02, f"{clip.name}: {fn}() embestida {hl:.2f} m (clip {t['lunge']:.2f}): los pies apoyados "
                                  f"se corren {sk * 100:.1f} cm", warn=True)
        # Kaito pegado (el imán del golpe corta la embestida en Enemy.TickAttack): lo que patina un pie apoyado si el
        # transform no avanza nada. Con los pies en el aire durante la embestida es 0
        if t.get("lunge") and clip.travel_table is not None:
            rep["magnet_skate_cm"] = round(variant_skate(touch, clip.travel_table, [0.0] * len(clip.travel_table)) * 100.0, 1)
            # y si el transform alcanza a avanzar una parte (Kaito un poco más lejos): el corte cae al final de la embestida
            # con lungeSlack (Enemy.Locomotion.cs) el modelo hace los últimos 'slack' m de lo que el imán cortó
            L = t["lunge"]
            rep["magnet_curve_cm"] = {str(sl): [round(variant_skate(touch, clip.travel_table, [
                min(x, L * q / 10.0) + max(0.0, x - max(L * q / 10.0, L - sl)) for x in clip.travel_table]) * 100.0, 1) for q in range(11)]
                for sl in (0.0, 0.15, 0.35)}
        # la embestida del clip tiene que arrancar en la suelta: si arranca antes, con cualquier pausa del juego en el
        # apex (CombatDirector la estira hasta 0.6 s) el ninja se desliza con la pose quieta y los pies clavados. En
        # cuadros del clip (lunge_from) arranca después del apex por construcción
        if t.get("lunge"):
            if lf is None:
                g = prerelease_glide(n, ap, a, t["lunge"], 1.0)
                rep["prerelease_glide_cm"] = round(g * 100.0, 1)
                check(g <= 0.02, f"{clip.name}: la embestida de {t['lunge']:.1f} m arranca en la suelta ({g * 100:.0f} cm antes)")
            else:
                check(lf > ap, f"{clip.name}: la embestida arranca después del apex (f{lf}, apex f{ap})")
            # lo mismo medido con el reloj: con 0.45 s más de pausa, lo que avanzó hasta el apex (la pose congelada)
            held = game_travel(n, ap, a, t["lunge"], t.get("windup", 0.55) + 0.45, 1.0, None if lf is None else lf / n, air=t.get("lunge_air", False))
            dh = max(held[:ap + 1])
            check(dh <= 0.02, f"{clip.name}: con 0.45 s de pausa no avanza con la pose del apex quieta ({dh * 100:.1f} cm)")
        # con el reloj del juego: segundos desde que arranca el paso hasta el golpe
        tl = NA.StepTimeline(n, ap, a, windup_min=t.get("windup", 0.55))
        rep["game_T_s"] = round(tl.T, 3)
        rep["game_hold_s"] = round(tl.hold, 3)
        rep["contact_tip_m"] = [round(x, 2) for x in tip[a]]
    if "hop" in t:
        # saltos sin daño (HopBack, HopSide): el Hit del juego despega y cae en los cuadros del clip
        hp = t["hop"]
        for a0, a1, apex, fn, hl, hs, frm, air in hits.get(t.get("state", clip.name), []):
            ok = (abs(a0 - hp["takeoff"] / n) <= 0.5 / n and abs(a1 - hp["land"] / n) <= 0.5 / n
                  and apex is not None and abs(apex - hp["apex"] / n) <= 0.5 / n and frm is not None and abs(frm - hp["takeoff"] / n) <= 0.5 / n)
            check(ok, f"{clip.name}: {fn}() Hit despega {a0:.3f} cae {a1:.3f} apex {apex} from {frm} vs clip "
                      f"{hp['takeoff'] / n:.4f} / {hp['land'] / n:.4f} / {hp['apex'] / n:.4f}")
    return rep


def game_travel(n, apex, contact, lunge, windup, speed, frm, end_frame=None, air=False):
    """Lo que avanza el transform del juego en cada cuadro del clip: en cuadros del clip desde 'frm' (normalizado,
    AttackDef.lungeFrom: team_moves.clip_lunge_travel) o la lineal de siempre si no tiene."""
    import team_moves as TM
    if frm is None:
        return T.lunge_travel(n, apex, contact, lunge, windup_min=windup, speed=speed)[0]
    return TM.clip_lunge_travel(n, apex, contact, lunge, windup, round(frm * n), speed=speed, end_frame=end_frame, air=air)[0]


def _hermite(P, i, s):
    """Curva cúbica por los cuadros enteros con tangentes automáticas que no se pasan (como las del FBX que exporta Blender y
    vuelve a muestrear Unity: sin pasarse en los quiebres). P: arrays (cuadro, vértice, xyz)."""
    import numpy as np
    n = len(P) - 1
    a, b = P[i], P[min(n, i + 1)]
    pa, nb = P[max(0, i - 1)], P[min(n, i + 2)]
    def tang(p, q, r):
        d0, d1 = q - p, r - q
        lim = 3.0 * np.minimum(np.abs(d0), np.abs(d1))
        return np.where(d0 * d1 <= 0.0, 0.0, np.clip(0.5 * (d0 + d1), -lim, lim))
    ma, mb = tang(pa, a, b), tang(a, b, nb)
    s2, s3 = s * s, s * s * s
    return (2 * s3 - 3 * s2 + 1) * a + (s3 - 2 * s2 + s) * ma + (-2 * s3 + 3 * s2) * b + (s3 - s2) * mb


def replay_skate(clip, pts, roots_auth, tdir, n, apex, contact, windup, lunge, frm, speed=1.0, end_frame=None, air=False, floor_tol=0.01, hz=240.0):
    """El golpe con el reloj del juego (StepTimeline a 240 Hz, cuadros fraccionarios) y la embestida del juego (en cuadros
    del clip o lineal): lo que se corre en el mundo la suela que toca el piso, con el clip interpolado entre cuadros como
    en Unity (cúbica) y el transform como lo mueve Enemy (lineal entre cuadros en LungeAt). Medido así, la estocada
    patinaba 34-45 cm aunque los cuadros enteros dieran 0. Devuelve (peor total cm, peor por muestra cm, dónde)."""
    import numpy as np
    tl = NA.StepTimeline(n, apex, contact, windup_min=windup, speed=speed)
    import team_moves as TM
    knots = game_travel(n, apex, contact, lunge, windup, speed, frm, end_frame, air=air)
    lin = None
    if frm is None:
        tr0 = T.lunge_travel(n, apex, contact, lunge, windup_min=windup, speed=speed)[1]
        end = tr0.T + 0.05 * tr0.step_len
        start = max(0.0, end - max(end - (tr0.tA + tr0.hold), lunge / 12.0))
        lin = (start, end)
    d = np.array((tdir[0], tdir[1], 0.0), dtype=np.float64)
    worst, per, at = 0.0, 0.0, ""
    for k in pts[0]:
        P = np.array([pts[f][k] - np.array(roots_auth[f]) for f in range(n + 1)])
        prev, run, f0 = None, 0.0, 0.0
        t = 0.0
        while True:
            nt = min(1.0, tl.norm_at(t))
            f = nt * n
            i = min(int(f), n - 1)
            s = f - i
            if lin is None:
                trv = TM.knot_curve(knots, f)
            else:
                trv = lunge * min(1.0, max(0.0, (t - lin[0]) / max(1e-4, lin[1] - lin[0])))
            Wp = _hermite(P, i, s) + d * trv
            if prev is not None:
                on = (prev[:, 2] < floor_tol) & (Wp[:, 2] < floor_tol)
                if on.any():
                    m = float(np.min(np.hypot(Wp[on, 0] - prev[on, 0], Wp[on, 1] - prev[on, 1]))) * 100.0
                    if run == 0.0:
                        f0 = f
                    run += m
                    if m > per:
                        per = m
                    if run > worst:
                        worst, at = run, f"pie {k} f{f0:.1f}-f{f:.1f} t {t:.2f} s"
                else:
                    run = 0.0
            prev = Wp
            if nt >= 1.0:
                break
            t += 1.0 / hz
    return worst, per, at


def wrist_checks(ch, clip, frames, rep):
    """Muñecas (ítem 3 de la revisión de Felipe), medidas sobre lo que se exporta y sobre lo que eligió team_limbs:
      * ninguna matriz espejada (determinante < 0: pasada a cuaternión, la mano salía doblada 180°);
      * la muñeca de cada mano dentro de su límite (exceso <= 1; la que sostiene un mango fijo, la menos mala: aviso
        hasta 1.35, falla después) y el giro que queda en ella hasta team_limbs.WRIST_TWIST;
      * lo que se enderezó la mano del arma (y el arma con ella) en los cuadros que se leen (aviso, apex, golpe): <= 12°;
      * saltos: el codo y la pronación que elige team_limbs no cambian de golpe más de lo que gira la mano pedida en ese
        cuadro (un antebrazo que da media vuelta solo se ve como un tic)."""
    import team_limbs as TL
    R = ch.rig
    neg = sum(1 for W in frames for M in W.values() if M.to_3x3().determinant() < 0.0)
    check(neg == 0, f"{clip.name}: sin matrices espejadas ({neg})")
    sv = getattr(clip, "limb_rows", None) or {}
    out = {}
    t = clip.timing
    look = set()
    if "contact" in t:
        look = {t["apex"], t["contact"]} | set(range(t.get("hold", [t["apex"]] * 2)[0], t["apex"] + 1))
    for k, rows in sv.items():
        if not rows:
            continue
        side = "derecha" if k == "r" else "izquierda"
        held = [r for r in rows if r["held"]]
        free = [r for r in rows if not r["held"]]
        ex = max(r["excess"] for r in rows)
        tw = max(abs(r["twist"]) for r in rows)
        out[k] = dict(excess=round(ex, 2), twist=round(tw, 1), fore=round(max(abs(r["fore"]) for r in rows), 1),
                      swivel=round(max(abs(r["swivel"]) for r in rows), 1), clamp=round(max(r["clamp"] for r in rows), 1))
        if free:
            e1 = max(r["excess"] for r in free)
            check(e1 <= 1.0, f"{clip.name}: muñeca {side} libre en su límite (x{e1:.2f})")
            fo = max(range(len(rows)), key=lambda i: rows[i].get("tw_over", 0.0))
            ov = rows[fo].get("tw_over", 0.0)
            out[k]["asked_over"] = round(ov, 1)
            check(ov <= 45.0, f"{clip.name}: mano {side} libre pedida posible (el pedido gira {ov:.0f}° de más en f{fo})", warn=True)
        if held:
            e2 = max(r["excess"] for r in held)
            f2 = max(range(len(rows)), key=lambda i: rows[i]["excess"] if rows[i]["held"] else -1)
            check(e2 <= 1.05, f"{clip.name}: muñeca {side} en el mango (x{e2:.2f} en f{f2})", warn=e2 <= 1.35)
            # el columpio de la mano sobre el antebrazo (lo que se ve: 75° alrededor de un mango es una muñeca quebrada aunque
            # esté dentro de lo anatómico); la del arma se endereza desde team_limbs.KATANA_BEND/CLUB_BEND
            sw = max(range(len(rows)), key=lambda i: rows[i]["swing"] if rows[i]["held"] else -1)
            out[k]["swing"] = round(rows[sw]["swing"], 1)
            check(rows[sw]["swing"] <= 55.0, f"{clip.name}: mano {side} en el mango sin quebrarse ({rows[sw]['swing']:.0f}° en f{sw})",
                  warn=rows[sw]["swing"] <= 70.0)
            # el antebrazo o la muñeca clavados en su tope casi todo el clip: el pedido no entra y lo que sobra se vuelve
            # el puño rodado en el mango (TR-4)
            pin = [r for r in held if r["pron_w"] > 0.5]
            if pin:
                at = sum(1 for r in pin if r["pron"] >= TL.PRON_MAX - 2.0 or r["pron"] <= TL.PRON_MIN + 2.0
                         or abs(r["twist"]) >= TL.WRIST_TWIST * 0.97) / len(pin)
                out[k]["pinned"] = round(at, 2)
                check(at <= 0.25, f"{clip.name}: antebrazo {side} lejos de sus topes ({at * 100:.0f} % de los cuadros en el tope)", warn=True)
        # pronación y supinación de una persona (con el codo doblado: con el brazo derecho el hombro hace lo mismo)
        pr = [r["pron"] for r in rows if r["pron_w"] > 0.5]
        if pr:
            lo, hi = min(pr), max(pr)
            out[k]["pron"] = [round(lo, 1), round(hi, 1)]
            check(TL.PRON_MIN - 3.0 <= lo and hi <= TL.PRON_MAX + 3.0,
                  f"{clip.name}: antebrazo {side} dentro de la pronación y la supinación ({lo:.0f}° a {hi:.0f}°)")
        tl = TL.WRIST_TWIST * 1.3 + 1.0
        check(tw <= tl, f"{clip.name}: giro que queda en la muñeca {side} ({tw:.0f}°)", warn=tw <= tl + 15.0)
        if look and held:
            dv = max((rows[f]["clamp"] for f in look if f < len(rows) and rows[f]["held"]), default=0.0)
            out[k]["clamp_tell"] = round(dv, 1)
            check(dv <= 12.0, f"{clip.name}: el arma de la mano {side} donde la pidió el clip en el aviso y el golpe "
                              f"(se corrió {dv:.0f}°)", warn=dv <= 25.0)
    rep["wrists"] = out
    # saltos que pone el solver (no el clip): el codo, la pronación o el agarre que cambian de golpe de un cuadro al otro
    # mientras la mano pedida casi no se mueve (fuera de la ventana del golpe, donde un tajo de 2 cuadros es legítimo)
    act = set(range(t["apex"], t.get("active", [t["contact"], t["contact"] + 2])[1] + 2)) if "contact" in t else set()
    worst, where = 0.0, ""
    for k, rows in sv.items():
        for i in range(1, len(rows)):
            if i in act:
                continue
            a, b = rows[i - 1], rows[i]
            asked = math.degrees(a["req"].rotation_difference(b["req"]).angle)
            asked = min(asked, 360.0 - asked)
            jump = TL.change_deg((0.0, a["roll"], a["diag"], a["swivel"], a["fore"]), (0.0, b["roll"], b["diag"], b["swivel"], b["fore"]),
                                 a["hand"], b["hand"])
            j = max(0.0, jump - asked)
            if j > worst:
                worst, where = j, f"{'derecha' if k == 'r' else 'izquierda'} f{i}"
    rep["solver_jump_deg"] = round(worst, 1)
    check(worst <= 35.0, f"{clip.name}: codo y antebrazo sin saltos de un cuadro al otro ({worst:.0f}° más que la mano, {where})",
          warn=worst <= 55.0)


# cámara del juego (pitch 52°) desde 6 lados alrededor del personaje: el enemigo puede mirar para cualquier lado
BLADE_CAMS = [Vector((math.sin(math.radians(a)) * math.cos(math.radians(52.0)), -math.cos(math.radians(a)) * math.cos(math.radians(52.0)),
                      math.sin(math.radians(52.0)))) for a in (0, 35, 90, 145, 180, 270)]


def blade_checks(ch, clip, frames, rep):
    """La cara plana de la katana vista desde la cámara del juego (V-TR-1 de la verificación): la media de |normal . cámara|
    en los cuadros que se leen (inicio del aviso, apex y golpe; timing 'read' en un clip sin golpe; en los loops, el primero
    y el del medio). Con el filo
    abajo derecho la cámara de arriba ve la hoja de canto: solo el lomo oscuro y una raya de 1 px (el Attack2 perdió así
    el 43 % de los píxeles claros). 1 = la cara entera mirando a la cámara desde los 6 lados; un filo inclinado 60° de la
    vertical (LOOP_EDGE) da ~0.6; uno abajo derecho con la hoja horizontal, ~0.33."""
    w = ch.weapon_info
    if not w or w["kind"] != "katana":
        return
    t = clip.timing
    if "contact" in t:
        look = sorted({t.get("hold", [t["apex"]])[0], t["apex"], t["contact"]})
    elif "read" in t:
        look = list(t["read"])
    elif clip.loop:
        look = [0, clip.frames // 2]
    else:
        return
    B = ch.spec["weapon"]["bone"]
    face = {}
    for f in look:
        Fk = frames[f][B].to_3x3().normalized() @ w["KB"].transposed()
        nrm = ch.Dc(Fk.col[0])
        face[f] = round(sum(abs(nrm.dot(d)) for d in BLADE_CAMS) / len(BLADE_CAMS), 2)
    rep["blade_face"] = face
    lo = min(face, key=face.get)
    check(face[lo] >= 0.5, f"{clip.name}: la cara de la hoja mira a la cámara del juego en el aviso y el golpe "
                           f"({face[lo]:.2f} en f{lo}; {', '.join(f'f{f} {v:.2f}' for f, v in face.items())})", warn=True)


def pop_checks(ch, clip, frames, ctrls, rep):
    """Tics medidos en lo que se exporta (TR-5 de la revisión): el giro LOCAL del brazo, el antebrazo y la mano de un cuadro
    al otro, como lo interpola Unity. Falla (la regla de la revisión) con más de 45° del antebrazo o la mano en un cuadro
    mientras la mano viaja menos de 20 cm, si ese cuadro gira 20° más que el más rápido de sus vecinos (un tic: 5°, 90°, 5°;
    no un barrido ni un arranque rápido que el clip pidió: 1°, 50°, 33°). Avisa con lo mismo en el brazo, o con la mano viajando
    más. El chequeo de saltos de team_limbs no veía la mano libre dentro de la ventana del golpe, los cambios que pedía el
    clip ni el codo que se mueve con el polo pedido. Quedan libres la mano del arma (y la otra si también agarra el mango)
    en la ventana del golpe, donde un tajo de dos cuadros es legítimo, y los dos primeros cuadros de un clip que no es
    loop: Unity entra con un cruce de 0.08 s (CharacterAnimator.Play), así que el sacudón del primer cuadro de un golpe
    recibido nunca se ve solo."""
    R = ch.rig
    w = ch.weapon_info
    wk = (w["hand"] if w["kind"] == "katana" else "r") if w else None
    t = clip.timing
    act = set(range(t["apex"], t.get("active", [t["contact"], t["contact"] + 2])[1] + 2)) if "contact" in t else set()
    loc = [R.to_local(W) for W in frames]
    n = len(frames)
    bad, soft, top = (0.0, ""), (0.0, ""), 0.0
    for k in "rl":
        d = ch.side[k]
        # lo que viajó la mano respecto de su hombro (V-TR-6 de la verificación): medido en la armadura, el cuerpo que gira o
        # se lanza en el golpe hacía "viajar" a una mano quieta en el brazo y eximía giros de 100° del brazo
        rel = [frames[i][d["hand"]].translation - frames[i][d["upper"]].translation for i in range(n)]
        move = [0.0] + [(rel[i] - rel[i - 1]).length / ch.u for i in range(1, n)]
        for b in (d["upper"], d["fore"], d["hand"]):
            dl = [0.0] + [NA.quat_angle_deg(loc[i - 1][b][1], loc[i][b][1]) for i in range(1, n)]
            for i in range(1, n):
                on = k == wk or (w is not None and (w["kind"] == "club" or (ctrls[i].get("grip_l") or 0.0) >= 0.5))
                if (on and i in act) or (not clip.loop and i <= 2):
                    continue
                top = max(top, dl[i])
                if dl[i] <= 45.0:
                    continue
                nb = [dl[j] for j in (i - 1, i + 1) if 1 <= j < n]
                spike = dl[i] - max(nb, default=0.0)
                txt = f"{b} f{i - 1}-f{i}: {dl[i]:.0f}°, vecinos {', '.join(f'{x:.0f}' for x in nb)}°, la mano viajó {move[i] * 100:.0f} cm"
                if spike > 20.0 and b != d["upper"] and move[i] < 0.20:
                    if spike > bad[0]:
                        bad = (spike, txt)
                elif spike > soft[0]:
                    soft = (spike, txt)
    rep["local_pop_deg"] = round(bad[0], 1)
    rep["local_max_deg"] = round(top, 1)
    check(bad[0] == 0.0, f"{clip.name}: antebrazo y mano sin tics en lo exportado ({bad[1] or f'el cuadro más rápido gira {top:.0f}°'})")
    check(soft[0] <= 30.0, f"{clip.name}: brazo sin tics en lo exportado ({soft[1] or 'ok'})",
          warn=not (clip.loop and "ambient" in clip.timing))


_PALM = {}


def palm_centroid(ch, k):
    """Centro de los vértices que pesan > 0.6 en la mano (espacio local del hueso de la mano, reposo)."""
    key = (ch.name, k)
    if key not in _PALM:
        h = ch.side[k]["hand"]
        pts = []
        for o in ch.meshes:
            if h not in o.vertex_groups:
                continue
            gi = o.vertex_groups[h].index
            pts += [ch.Ai @ (o.matrix_world @ v.co) for v in o.data.vertices if any(g.group == gi and g.weight > 0.6 for g in v.groups)]
        _PALM[key] = (ch.rig.rest_inv[h] @ (sum(pts, Vector()) / len(pts))) if pts else None
    return _PALM[key]


def weapon_axis(ch, W):
    """(punto, dirección) del eje del mango en la pose W (espacio de la armadura)."""
    w = ch.weapon_info
    B = W[ch.spec["weapon"]["bone"]]
    if w["kind"] == "club":
        return B.translation.copy(), B.to_3x3().normalized().col[1]
    Fk = B.to_3x3().normalized() @ w["KB"].transposed()
    return B.translation - Fk @ w["hb"], Fk.col[1]


def grip_checks(ch, clip, frames, ctrls, rep):
    """El puño alrededor del mango (TR-1 de la revisión: el de Gorō flotaba 12-20 cm al costado del palo y ningún chequeo
    lo veía). Se mide como la revisión, sobre la malla: la distancia del centro de la palma al eje del mango en cada cuadro
    en que la mano agarra del todo, contra la del agarre ideal (el mango por el hueco del puño, team_rig.grip_frame /
    measure_katana). Falla si se aparta más de 2 cm, o si el hueco del puño mismo queda fuera de la mano (más lejos de la
    palma que el 75 % del largo de la mano: con el 60 % fallaba la izquierda del ninja, que agarra bien). La diagonal del
    agarre (la mano girada sobre la normal de su palma por el hueco, team_limbs CLUB_DIAG/KATANA_DIAG alrededor de
    KATANA_DIAG0) cambia esa distancia: el agarre ideal da el rango que se acepta (más 2 cm)."""
    import team_limbs as TL
    w = ch.weapon_info
    if not w:
        return
    out = {}
    for k in "rl":
        c = palm_centroid(ch, k)
        if c is None:
            continue
        hi = ch.hand_info[k]
        h = ch.side[k]["hand"]
        # el eje del mango en el espacio de la mano con el agarre ideal: pasa por el hueco del puño, en la dirección del
        # índice al meñique (el martillo) o la de la hoja del modelo (la katana: la mano no es la del arma -> su espejo)
        if w["kind"] == "club":
            a = (hi["Rh0"].transposed() @ hi["M0"].col[1]).normalized()
        else:
            a = (w["K"].transposed() @ Vector((0.0, 1.0, 0.0))).normalized()
        d = c - hi["fist"]
        n = (hi["Rh0"].transposed() @ hi["M0"].col[2]).normalized()
        diag = TL.CLUB_DIAG if w["kind"] == "club" else TL.KATANA_DIAG
        # la katana va en diagonal sobre la palma (team_limbs.KATANA_DIAG0): el rango del agarre, alrededor de esa diagonal
        d0 = TL.KATANA_DIAG0 if w["kind"] == "katana" and k == w["hand"] else 0.0
        refs = []
        for i in range(-4, 5):
            # la mano girada +g sobre su palma ve el mango girado -g en su espacio
            ag = Matrix.Rotation(-math.radians(d0 + diag * i / 4.0), 3, n) @ a
            refs.append((d - ag * d.dot(ag)).length / ch.u * 100.0)
        ref = refs[4]
        rows = (getattr(clip, "limb_rows", None) or {}).get(k) or []
        if w["kind"] == "katana" and k != w["hand"]:
            # la otra mano en el mango es el espejo del agarre de la del arma: su eje en el espacio de la mano sale del
            # primer cuadro en que agarra del todo, sin la diagonal que eligió el solver, y la diagonal de referencia es la
            # espejada (KATANA_LDIAG0)
            ref = None
            f0 = next((f for f, cc in enumerate(ctrls) if (cc.get("grip_l") or 0.0) >= 0.999 and f < len(rows)), None)
            if f0 is not None:
                _, ax = weapon_axis(ch, frames[f0])
                a = (frames[f0][h].to_3x3().normalized().transposed() @ ax).normalized()
                a = Matrix.Rotation(math.radians(rows[f0]["diag"]), 3, n) @ a
                refs = []
                for i in range(-4, 5):
                    ag = Matrix.Rotation(-math.radians(TL.KATANA_LDIAG0 + diag * i / 4.0), 3, n) @ a
                    refs.append((d - ag * d.dot(ag)).length / ch.u * 100.0)
                ref = refs[4]
        held = []
        for f, (W, cc) in enumerate(zip(frames, ctrls)):
            if w["kind"] == "club":
                g = cc.get("grip_r") if k == "r" else cc.get("grip_l")
                full = (1.0 if g is None else g) >= 0.999 and not (k == "r" and (cc.get("drop_r") or 0.0) > 1e-3)
            else:
                full = k == w["hand"] or (cc.get("grip_l") or 0.0) >= 0.999
            if not full:
                continue
            p, ax = weapon_axis(ch, W)
            q = W[h] @ c - p
            held.append((f, (q - ax * q.dot(ax)).length / ch.u * 100.0))
        if not held:
            continue
        lo, hi_ = min(g for _, g in held), max(g for _, g in held)
        side = "derecha" if k == "r" else "izquierda"
        out[k] = dict(ref=None if ref is None else round(ref, 1), min=round(lo, 1), max=round(hi_, 1))
        r0, r1 = (min(refs), max(refs)) if ref is not None else (lo, lo)
        fw = max(held, key=lambda x: max(r0 - x[1], x[1] - r1))
        check(r0 - 2.0 <= fw[1] <= r1 + 2.0, f"{clip.name}: el puño {side} alrededor del mango (palma a {fw[1]:.1f} cm del eje en "
                                              f"f{fw[0]}, agarre {r0:.1f}-{r1:.1f} cm)")
        if ref is not None:
            check(ref <= 75.0 * hi["len"] / ch.u, f"{clip.name}: el hueco del puño {side} dentro de la mano ({ref:.1f} cm de la palma, "
                                                  f"tope {75.0 * hi['len'] / ch.u:.1f})")
    rep["grip_gap_cm"] = out


def prerelease_glide(frames, apex, contact, lunge, speed):
    """Metros que el transform avanza ANTES de la suelta (Enemy.BeginStep: la embestida termina en T + 0.05 * largo
    del paso y no va a más de 12 m/s; si la suelta no alcanza, arranca antes). No depende de la pausa."""
    tl = NA.StepTimeline(frames, apex, contact, windup_min=0.0, speed=speed)
    room = tl.tR + 0.05 * tl.step_len
    span = max(room, lunge / 12.0)
    return lunge * (span - room) / span


def touch_segments(ch, frames, tol=0.02):
    """Tramos de cuadros en que cada pie toca el piso (el punto más bajo de la suela, la punta o el talón, a menos de
    'tol' del piso), apoyado o rodando sobre la punta: ahí un cambio del avance del transform es un patinazo. Los apoyos
    de plants() no ven el pie que rueda (el tobillo sube y se mueve) y es justo el que empuja en una embestida."""
    R = ch.rig
    out = {}
    for k in "rl":
        fb = ch.side[k]["foot"]
        a0 = ch.land["ankle_" + k]
        so = ch.sole[k]
        loc = [R.rest_inv[fb] @ ch.P(a0 + v) for v in (Vector((0.0, 0.0, so["toe"].z)), so["toe"], so["heel"])]
        zero = [Vector()] * len(frames)
        low = [min(p.z for p in pts) for pts in zip(*[canon_track(ch, frames, zero, fb, l) for l in loc])]
        floor = min(low)
        segs, cur = [], None
        for f, z in enumerate(low):
            if z < floor + tol:
                cur = [f, f] if cur is None else [cur[0], f]
            else:
                if cur:
                    segs.append({"frames": cur})
                cur = None
        if cur:
            segs.append({"frames": cur})
        out[k] = segs
    return out


def variant_skate(segs, tr, trv):
    """Lo que se corre en el mundo un pie que toca el piso (tramos de touch_segments) si el juego avanza el transform
    'trv' en vez del 'tr' con que se autoró: dentro de un tramo el pie se mueve lo que cambia la diferencia de los avances."""
    worst = 0.0
    for ss in segs.values():
        for sgm in ss:
            a, b = sgm["frames"]
            d0 = trv[min(a, len(trv) - 1)] - tr[min(a, len(tr) - 1)]
            for f in range(a, b + 1):
                worst = max(worst, abs((trv[min(f, len(trv) - 1)] - tr[min(f, len(tr) - 1)]) - d0))
    return worst


def body_points(ch, W):
    """Todos los huesos y la punta del arma (m, marco de autoría, sin el avance del transform): para comparar poses."""
    pts = [ch.Pc(W[n].translation) for n in ch.rig.names]
    w = ch.weapon_info
    if w and w["kind"] == "katana":
        pts.append(ch.Pc(W[ch.spec["weapon"]["bone"]] @ w["tip_local"]))
    elif w and w["kind"] == "club":
        pts.append(ch.Pc(W[ch.spec["weapon"]["bone"]] @ Vector((0.0, w["head_center"] * ch.u, 0.0))))
    return pts


def pose_at(ch, frames, f):
    """Puntos de body_points en un cuadro fraccionario (interpolados entre los dos enteros)."""
    i = max(0, min(len(frames) - 1, int(math.floor(f))))
    j = min(len(frames) - 1, i + 1)
    a, b = body_points(ch, frames[i]), body_points(ch, frames[j])
    s = f - i
    return [p + (q - p) * s for p, q in zip(a, b)]


def chain_checks(ch, baked_by_name):
    """Cortes del juego que encadenan con otro clip (timing['chain'] = [(cuadro, clip, cuadro del otro, tolerancia m)]):
    el retroceso del parry que corta Parried y arranca el paso siguiente, el sacudón que vuelve al loop de agotado,
    el final del abuelo que vuelve al Idle. La pose en el corte tiene que ser la del otro clip (peor punto)."""
    for name, (clip, frames) in baked_by_name.items():
        for f, other, fo, tol in clip.timing.get("chain", []):
            if other not in baked_by_name:
                continue
            a = pose_at(ch, frames, f)
            b = pose_at(ch, baked_by_name[other][1], fo)
            d = max((p - q).length for p, q in zip(a, b))
            check(d <= tol, f"{name}: en f{f:g} empalma con {other} f{fo:g} (peor punto {d * 100:.1f} cm, tope {tol * 100:.0f})")


def blend_index(n, loop, f):
    """Cuadro f de un clip de n cuadros (negativo: desde el final; en un loop el último es el primero)."""
    last = n - 1 if loop else n
    return f if f >= 0 else last + 1 + f


def blend_anchors(clip, blends, rows_by):
    """{lado: {cuadro: (estado, mano en el mango, mano pedida)}} de los cruces de 'clip' con clips ya resueltos
    (team_clips_<personaje>.BLENDS = [(clip, cuadro, otro clip, cuadro del otro)]; -1 es el último cuadro)."""
    out = {"r": {}, "l": {}}
    for a, fa, b, fb in blends:
        for x, fx, y, fy in ((a, fa, b, fb), (b, fb, a, fa)):
            if x != clip.name or y not in rows_by:
                continue
            for k in "rl":
                rr = rows_by[y].get(k) or []
                if not rr:
                    continue
                r = rr[min(len(rr) - 1, blend_index(len(rr) - 1, False, fy))]
                out[k][blend_index(clip.frames, clip.loop, fx)] = (r["state"], r["hc"], r["req"])
    return out


def blend_checks(ch, baked_by_name, blends):
    """Los cruces de Unity (BLENDS): Unity interpola cada hueso por separado, y un antebrazo en otra rama de la pronación da
    un sacacorchos a media mezcla aunque la mano y la hoja terminen en el mismo lugar (Guard -> Counter giraba 138°). Se mide
    el giro del antebrazo sobre su eje entre los dos clips menos lo que cambió la mano pedida (lo que el clip pidió cambiar
    no es un salto). Aparte, el giro crudo (V-TR-5 de la verificación: restar lo pedido escondía que cada golpe arrancaba
    rodando el antebrazo 60° en los 0.08 s del cruce): más de 45° es un aviso, aunque lo haya pedido el clip."""
    import team_limbs as TL
    R = ch.rig
    for a, fa, b, fb in blends:
        if a not in baked_by_name or b not in baked_by_name:
            continue
        (ca, Fa), (cb, Fb) = baked_by_name[a], baked_by_name[b]
        ia, ib = blend_index(ca.frames, False, fa), blend_index(cb.frames, False, fb)
        la, lb = R.to_local(Fa[ia]), R.to_local(Fb[ib])
        worst, where, raw, raw_at = 0.0, "", 0.0, ""
        for k in "rl":
            fo = ch.side[k]["fore"]
            tw = abs(TL.twist_deg(la[fo][1].inverted() @ lb[fo][1]))
            ra, rb = (getattr(ca, "limb_rows", {}) or {}).get(k), (getattr(cb, "limb_rows", {}) or {}).get(k)
            asked = 0.0
            if ra and rb:
                asked = math.degrees(ra[min(ia, len(ra) - 1)]["req"].rotation_difference(rb[min(ib, len(rb) - 1)]["req"]).angle)
                asked = min(asked, 360.0 - asked)
            if tw - asked > worst:
                worst, where = tw - asked, f"{fo} gira {tw:.0f}°, la mano pedida {asked:.0f}°"
            if tw > raw:
                raw, raw_at = tw, fo
        check(worst <= 30.0, f"cruce {a} f{fa} -> {b} f{fb}: antebrazos en la misma rama ({where or 'sin saltos'})",
              warn=worst <= 50.0)
        check(raw <= 45.0, f"cruce {a} f{fa} -> {b} f{fb}: el antebrazo rueda poco en el cruce de 0.08 s "
                           f"({raw_at + ' ' if raw_at else ''}{raw:.0f}° crudo)", warn=True)


def locomotion_weapon(ch, baked_by_name, states, ths=None):
    """El blend de locomoción mezcla cada hueso por separado: si el arma apunta para lados opuestos en dos hijos
    vecinos, a mitad de mezcla se mete en el cuerpo o en el piso. Punta del arma a la misma fase, < 60 cm. En el blend
    tree 2D (umbrales (x, y)) se mezclan el centro con cada uno y los vecinos del anillo (no los opuestos)."""
    w = ch.weapon_info
    if not w:
        return
    bone = ch.spec["weapon"]["bone"]
    local = w["tip_local"] if w["kind"] == "katana" else Vector((0.0, w["head_center"] * ch.u, 0.0))
    pairs = list(zip(states, states[1:]))
    if ths and isinstance(ths[0], (tuple, list)):
        pairs = []
        for i in range(len(states)):
            for j in range(i + 1, len(states)):
                a, b = Vector(ths[i]), Vector(ths[j])
                if a.length < 1e-6 or b.length < 1e-6 or a.angle(b) < math.radians(100.0):
                    pairs.append((states[i], states[j]))
    for s0, s1 in pairs:
        if s0 not in baked_by_name or s1 not in baked_by_name:
            continue
        fa, fb = baked_by_name[s0][1], baked_by_name[s1][1]
        worst = 0.0
        for ph in (0.0, 0.25, 0.5, 0.75):
            pa = ch.Pc(fa[int(round(ph * (len(fa) - 1)))][bone] @ local)
            pb = ch.Pc(fb[int(round(ph * (len(fb) - 1)))][bone] @ local)
            worst = max(worst, (pa - pb).length)
        check(worst <= 0.6, f"locomoción: el arma de {s0} a {s1} a la misma fase ({worst * 100:.0f} cm)")
        # la mezcla como la hace Unity (posición y giro LOCALES de cada hueso, interpolados): la punta a media mezcla
        # no puede irse lejos del promedio de las dos (se metía en las piernas) ni bajar del piso
        R = ch.rig
        dev, low = 0.0, 9.0
        for ph in (0.0, 0.25, 0.5, 0.75):
            Wa, Wb = fa[int(round(ph * (len(fa) - 1)))], fb[int(round(ph * (len(fb) - 1)))]
            la, lb = R.to_local(Wa), R.to_local(Wb)
            for wgt in (0.25, 0.5, 0.75):
                W = {}
                for nm in R.names:
                    (pa, qa), (pb, qb) = la[nm], lb[nm]
                    if qa.dot(qb) < 0.0:
                        qb = -qb
                    L = Matrix.Translation(pa.lerp(pb, wgt)) @ qa.slerp(qb, wgt).to_matrix().to_4x4()
                    par = R.parent[nm]
                    W[nm] = (W[par] @ R.rel[nm] if par else R.rest[nm]) @ L
                tip = ch.Pc(W[bone] @ local)
                ref = ch.Pc(Wa[bone] @ local).lerp(ch.Pc(Wb[bone] @ local), wgt)
                dev = max(dev, (tip - ref).length)
                low = min(low, tip.z)
        check(dev <= 0.3 and low >= 0.25, f"locomoción: a media mezcla {s0}-{s1} el arma sigue su camino (se aparta {dev * 100:.0f} cm, "
                                          f"punta/cabeza a {low * 100:.0f} cm del piso)")


def foot_vertices(ch):
    """Vértices de la suela de cada pie (malla con skin): los que pesan más de la mitad en el pie o en su control.
    {k: [(objeto, [índices])]}"""
    out = {}
    for k in "rl":
        names = {ch.side[k]["foot"]} | ({ch.side[k]["foot_ctrl"]} if ch.side[k]["foot_ctrl"] else set())
        lst = []
        for o in ch.meshes:
            gi = {g.index for g in o.vertex_groups if g.name in names}
            if not gi:
                continue
            idx = [v.index for v in o.data.vertices if sum(g.weight for g in v.groups if g.group in gi) > 0.5]
            if idx:
                lst.append((o, idx))
        out[k] = lst
    return out


def mesh_pass(ch, clip, first, roots, feet_v, floor_tol=0.01):
    """Una pasada por la malla deformada de cada cuadro (la acción ya escrita) con dos medidas:
      * patinada CON el pie tocando el piso (revisión AK-03): en cada par de cuadros, de los vértices de la suela que
        están a menos de 1 cm del piso en los dos, el que menos se corrió en el plano del piso (con el avance del
        transform del juego sumado). Un pie que rueda sobre la punta o el talón tiene un vértice quieto: no cuenta; uno
        que se arrastra entero sí. {k: [(cuadro inicial, final, total cm, peor cm por cuadro)]} de las tiradas > 0.5 cm;
      * lo más hondo que se mete en el piso el cuerpo (mallas con skin) y el arma (piezas rígidas), en cm por cuadro."""
    import numpy as np
    scn = bpy.context.scene
    n = clip.frames
    Rw = np.array(ch.Rcw, dtype=np.float64)
    O = np.array(ch.O, dtype=np.float64)
    A3 = ch.A.to_3x3()
    feet_idx = {o.name: {k: np.array(idx) for k, lst in feet_v.items() for oo, idx in lst if oo is o} for o in ch.meshes}
    pts, low_body, low_weapon, low_where = [], [], [], []
    for f in range(n + 1):
        scn.frame_set(first + f)
        dg = bpy.context.evaluated_depsgraph_get()
        shift = np.array(A3 @ roots[f], dtype=np.float64)
        row = {k: [] for k in feet_v}
        lb = lw = 9.0
        where = ""
        for o in ch.meshes:
            oe = o.evaluated_get(dg)
            me = oe.to_mesh()
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            oe.to_mesh_clear()
            M = np.array(oe.matrix_world, dtype=np.float64)
            w = co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3] + shift
            c = (w - O) @ Rw / ch.u                         # marco de autoría (m)
            z = float(c[:, 2].min())
            if o.vertex_groups:
                if z < lb:
                    lb, where = z, dominant_group(o, int(c[:, 2].argmin()))
            else:
                lw = min(lw, z)
            for k, idx in feet_idx[o.name].items():
                row[k].append(c[idx])
        pts.append({k: np.concatenate(v) for k, v in row.items() if v})
        low_body.append(lb)
        low_weapon.append(lw)
        low_where.append(where)
    out = {}
    for k in feet_v:
        runs, run = [], None
        for a in range(n):
            pa, pb = pts[a][k], pts[a + 1][k]
            on = (pa[:, 2] < floor_tol) & (pb[:, 2] < floor_tol)
            if on.any():
                m = float(np.min(np.hypot(pb[on, 0] - pa[on, 0], pb[on, 1] - pa[on, 1]))) * 100.0
                if run is None:
                    run = [a, a + 1, 0.0, 0.0]
                run[1] = a + 1
                run[2] += m
                run[3] = max(run[3], m)
            elif run:
                runs.append(run)
                run = None
        if run:
            runs.append(run)
        out[k] = [(r0, r1, round(t, 2), round(w, 2)) for r0, r1, t, w in runs if t > 0.5]
    return out, [round(v * 100.0, 1) for v in low_body], [round(v * 100.0, 1) for v in low_weapon], low_where, pts


def dominant_group(o, vi):
    """Hueso que más pesa en un vértice (para decir QUÉ se mete en el piso)."""
    gs = o.data.vertices[vi].groups
    return o.vertex_groups[max(gs, key=lambda g: g.weight).group].name if len(gs) else o.name


def floor_checks(clip, low_body, low_weapon, low_where):
    """Nada atraviesa el piso: el cuerpo nunca más de 3 cm (las suelas que ruedan rozan); el arma no más de 1 cm (la que se
    apoya en el piso, la katana del agotado o el martillo de Gorō: con los 3 cm de antes la hoja del Attack2 y el martillo
    de la muerte de Gorō pasaban justo y en una pendiente se meten), salvo el mordisco del golpe (hasta 6 cm, del
    contacto a 3 cuadros después: el martillo que pega en el piso)."""
    t = clip.timing
    bite = range(t["contact"], t["contact"] + 4) if "contact" in t else range(0)
    wb = min(range(len(low_body)), key=lambda i: low_body[i])
    # una toma del equipo re-resuelta (TakeClip) se corrige igual que un clip nuevo (team_rig.take_floor_fix: el pie
    # gira sobre el tobillo, el martillo alrededor del puño), así que también falla; 'take_raw' en solve_take la deja tal
    # cual para comparar (la presentación de Gorō: el pie derecho -8.2 cm y el martillo -22.4 cm)
    check(low_body[wb] >= -3.0, f"{clip.name}: el cuerpo no se mete en el piso (f{wb} {low_body[wb]:.1f} cm)")
    if low_body[wb] < -3.0:
        print("       cuadro a cuadro (cm):", " ".join(f"{i}:{v:.0f}({low_where[i]})" for i, v in enumerate(low_body) if v < -3.0))
    if min(low_weapon) < 800.0:          # sin arma queda en 900 (centinela)
        bad = [(i, v) for i, v in enumerate(low_weapon) if v < (-6.0 if i in bite else -1.0)]
        ww = min(range(len(low_weapon)), key=lambda i: low_weapon[i])
        check(not bad, f"{clip.name}: el arma no se mete en el piso (f{ww} {low_weapon[ww]:.1f} cm"
                       f"{'; ' + str(len(bad)) + ' cuadros de más' if bad else ''})")


def replay_checks(ch, clip, soles, hits):
    """replay_skate de cada golpe con embestida (y de cada salto sin daño) con los números del clip (falla > 2 cm) y con
    los de cada variante de EnemyArchetypes que lo usa (aviso)."""
    t = clip.timing
    n = clip.frames
    td = getattr(clip, "travel_dir", (0.0, -1.0))
    if "hop" in t:
        hp = t["hop"]
        roots = [Vector((td[0], td[1], 0.0)) * x for x in clip.travel_table]
        w, p, at = replay_skate(clip, soles, roots, td, n, hp["apex"], hp["takeoff"], t.get("windup", 0.1), t["lunge"],
                                hp["takeoff"] / n, end_frame=hp["land"])
        # como el chequeo de los cuadros enteros: 3 cm en total (una suela que rueda corre apenas su punto de apoyo)
        check(w <= 3.0 and p <= 2.0, f"{clip.name}: con el reloj del juego los pies no patinan en el salto ({w:.1f} cm, peor muestra "
                                     f"{p:.1f} cm, {at})")
        clip.timing = dict(t, replay_skate_cm=round(w, 1))
        return
    if not t.get("lunge") or "contact" not in t or clip.travel_table is None:
        return
    ap, a = t["apex"], t["contact"]
    roots = [Vector((td[0], td[1], 0.0)) * x for x in clip.travel_table]
    lf = t.get("lunge_from")
    w, p, at = replay_skate(clip, soles, roots, td, n, ap, a, t.get("windup", 0.55), t["lunge"], None if lf is None else lf / n,
                            air=t.get("lunge_air", False))
    check(w <= 3.0 and p <= 2.0, f"{clip.name}: con el reloj del juego los pies apoyados no patinan en la embestida ({w:.1f} cm, peor "
                                 f"muestra {p:.1f} cm, {at})")
    out = {"clip": round(w, 1)}
    for a0, a1, apex, fn, hl, hs, frm, air in hits.get(t.get("state", clip.name), []):
        if hl <= 0.0:
            continue
        wv, pv, atv = replay_skate(clip, soles, roots, td, n, ap, a, t.get("windup", 0.55), hl, frm, speed=hs, air=air)
        out[fn] = round(wv, 1)
        check(wv <= 2.0, f"{clip.name}: {fn}() ({hl:.2f} m, velocidad {hs:g}{', lineal' if frm is None else ''}) con el reloj del "
                         f"juego: {wv:.1f} cm ({atv})", warn=True)
    clip.timing = dict(t, replay_skate_cm=out)


# ------------------------------------------------------------------------------- export
def export_fbx(ch, path, frame_start, frame_end):
    """Solo la armadura, con los ajustes del equipo (charlib.TEAM): el nodo 'Armature' y el reposo de cada hueso
    salen idénticos a los del modelo, así las curvas se ligan a la misma ruta y no mueven nada que no animen."""
    import charlib as C
    scn = bpy.context.scene
    scn.frame_start, scn.frame_end = frame_start, frame_end
    scn.frame_set(frame_start - 1)
    bpy.ops.object.select_all(action='DESELECT')
    ch.arm.select_set(True)
    bpy.context.view_layer.objects.active = ch.arm
    kw = dict(C.TEAM)
    kw.update(object_types={'ARMATURE'}, bake_anim_use_all_actions=False, bake_anim_step=1.0)
    # el abuelo se exportó en centímetros (FBX_SCALE_UNITS): el nodo de la armadura tiene que salir igual al del modelo
    kw.update(ch.spec.get("export_kw", {}))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, **kw)


def verify_fbx(ch, path, last):
    """El FBX de animación contra el modelo: mismos nodos (nombres), el nodo de la armadura con el mismo transform
    (si no, cada clip lo movería), las mismas unidades y una sola toma que cubre todos los clips."""
    import fbxcheck as FC
    a, m = FC.summary(path), FC.summary(ch.src)
    extra = [n for n in a["models"] if n not in m["models"]]
    check(not extra, f"FBX: todos los nodos existen en el modelo ({extra[:4]})")
    arm = ch.arm.name
    ra, ta, sa = a["local"][arm]
    rm, tm, sm = m["local"][arm]
    d_rot = FC._rot3_angle(ra, rm)
    d_pos = max(abs(x - y) for x, y in zip(ta, tm))
    d_scl = max(abs(x - y) for x, y in zip(sa, sm))
    check(d_rot < 0.01 and d_pos < 1e-4 and d_scl < 1e-5, f"FBX: nodo '{arm}' igual al del modelo (giro {d_rot:.4f}°, "
                                                          f"posición {d_pos:.2e}, escala {d_scl:.2e})")
    check(abs(a.get("unit", 1) - m.get("unit", 1)) < 1e-6, f"FBX: unidades {a.get('unit')} = {m.get('unit')}")
    check(list(a["stacks"]) == ["Scene"], f"FBX: una toma 'Scene' ({list(a['stacks'])})")
    # Unity liga cada curva por ruta: cada nodo tiene que colgar del mismo padre que en el modelo (el esqueleto de juego
    # cambió padres de manos y pies) y la ruta empezar en 'Armature/...'; el nodo raíz no se anima (si no, con un solo
    # nodo raíz Unity lo aplana y el clip escala el modelo entero: el bug de los enemigos invisibles)
    bad = [n for n in a["models"] if a["parents"].get(n) != m["parents"].get(n)]
    check(not bad, f"FBX: mismos padres que el modelo ({bad[:4]})")
    paths = [FC.path_of(a["parents"], n) for n in a["models"]]
    check(all(p == arm or p.startswith(arm + "/") for p in paths), f"FBX: rutas bajo '{arm}/' ({[p for p in paths if not p.startswith(arm)][:3]})")
    root_moves = sorted({prop for n, prop, ax in a["motion"].get("Scene", set()) if n == arm})
    check(not root_moves, f"FBX: el nodo '{arm}' no se anima ({root_moves})")
    lo, hi = a["stacks"].get("Scene", (0, 0))
    check(abs(hi * T.FPS - last) < 0.51, f"FBX: la toma llega al cuadro {last} ({hi * T.FPS:.1f})")
    return a


def sheet_frames(clip):
    t = clip.timing
    if FRAMES:
        return [int(x) for x in FRAMES.split(",")]
    if "contact" in t:
        fs = {0, t["hold"][0], t["apex"], t["contact"] - 1, t["contact"], t["active"][1], clip.frames}
        fs |= set(t.get("sheet", []))
        return sorted(f for f in fs if 0 <= f <= clip.frames)
    k = max(1, clip.frames // 7)
    return sorted(set(list(range(0, clip.frames + 1, k)) + list(t.get("sheet", []))))


def frame_label(clip, f):
    t = clip.timing
    tags = []
    if "contact" in t:
        if f == t["hold"][0]:
            tags.append("aviso")
        if f == t["apex"]:
            tags.append("apex")
        if f == t["contact"]:
            tags.append("GOLPE")
    return f"f{f}" + (" " + "/".join(tags) if tags else "")


# ------------------------------------------------------------------------------- main
def main():
    global mod
    t0 = time.time()
    ch = T.TeamChar(CHAR, T.CHARS[CHAR])
    print("PERSONAJE", CHAR, json.dumps(ch.report()))
    mod = importlib.import_module("team_clips_" + CHAR)
    clips = mod.clips(ch)
    if ONLY:
        keep = ONLY.split(",")
        clips = [c for c in clips if c.name in keep]
    solver = T.TeamSolver(ch)
    hits = archetype_hits(ARCH_FUNCS.get(CHAR, []))
    baked, reports, rootsd, rootsa = [], {}, {}, {}
    blends = getattr(mod, "BLENDS", ())
    rows_by = {}
    for clip in clips:
        # los cruces de Unity con clips ya resueltos anclan el camino del brazo a la rama de ellos (team_limbs.ANCHOR_W)
        solver.limbs.anchors = blend_anchors(clip, blends, rows_by)
        frames, ctrls, roots, drops, misses = T.bake(ch, clip, solver)
        solver.limbs.anchors = {}
        clip.limb_rows = {k: list(v) for k, v in solver.limbs.rows.items()}
        rows_by[clip.name] = clip.limb_rows
        print(f"[{clip.name}] {clip.frames} cuadros ({clip.frames / T.FPS:.2f} s){' loop' if clip.loop else ''}")
        reports[clip.name] = lint(ch, clip, frames, ctrls, roots, drops, misses, hits)
        duo = getattr(clip, "partner", None)
        if duo is not None:
            # el segundo esqueleto del FBX (el ninja del secuestro): los mismos chequeos sobre lo suyo
            duo.limb_rows = {k: list(v) for k, v in solver.partner_solver().limbs.rows.items()}
            reports[clip.name]["partner"] = lint(ch.partner, duo, frames, duo.ctrls, roots, duo.drops, duo.misses, {})
        # avance del transform en el marco de autoría (frente -Y): el rodeo va de costado y el retroceso para atrás
        td = getattr(clip, "travel_dir", (0.0, -1.0))
        rootsd[clip.name] = [Vector((td[0], td[1], 0.0)) * (c.get("travel") or 0.0) + clip.root_vel * (f / T.FPS) for f, c in enumerate(ctrls)]
        rootsa[clip.name] = roots
        baked.append((clip, frames))
    act, ranges = NA.write_pack(ch.arm, ch.rig, baked, start=1, gap=GAP)
    # pies que patinan tocando el piso: se mide sobre la malla deformada por la acción ya escrita
    feet_v = foot_vertices(ch)
    for clip, _ in baked:
        sk, lb, lw, lwh, soles = mesh_pass(ch, clip, ranges[clip.name][0], rootsa[clip.name], feet_v)
        reports[clip.name]["floor_skate_cm"] = sk
        reports[clip.name]["lowest_body_cm"] = min(lb)
        reports[clip.name]["lowest_weapon_cm"] = min(lw) if min(lw) < 800 else None
        floor_checks(clip, lb, lw, lwh)
        allow = clip.timing.get("slide_ok", 0.0)
        runs = [r for v in sk.values() for r in v]
        tot = max([r[2] for r in runs] or [0.0])
        per = max([r[3] for r in runs] or [0.0])
        where = "; ".join(f"{k} f{r[0]}-f{r[1]} {r[2]} cm" for k, v in sk.items() for r in v if r[2] > 1.0)
        check(tot <= max(3.0, allow) and per <= max(2.0, allow),
              f"{clip.name}: sin patinar con el pie en el piso (total {tot:.1f} cm, peor cuadro {per:.1f} cm{'; ' + where if where else ''})")
        replay_checks(ch, clip, soles, hits)
    by_name = {c.name: (c, fr) for c, fr in baked}
    chain_checks(ch, by_name)
    blend_checks(ch, by_name, blends)
    lo = getattr(mod, "LOCOMOTION", None)
    if lo:
        locomotion_weapon(ch, by_name, [nm for nm, _ in lo], [th for _, th in lo])
    last = max(b for a, b in ranges.values())
    if EXPORT and (not ONLY or opt("--fbx")):
        if failures:
            print("NO SE EXPORTA: fallaron chequeos")
        else:
            export_fbx(ch, FBX, 1, last)
            nfail = len(failures)
            verify_fbx(ch, FBX, last)
            if len(failures) > nfail:
                os.remove(FBX)
                print("FBX BORRADO: no coincide con el modelo")
                sys.exit(1)
            info = {"fps": T.FPS, "take": "Scene", "character": CHAR, "model": ch.spec["fbx"], "units_per_meter": round(ch.u, 5),
                    "clips": {}}
            lo = getattr(mod, "LOCOMOTION", None)
            if lo and all(n in ranges for n, _ in lo):
                # estados y umbrales de Speed (velocidad / runSpeed) del blend tree de locomoción
                info["locomotion"] = {"states": [n for n, _ in lo], "thresholds": [th for _, th in lo]}
            for clip, frames in baked:
                a, b = ranges[clip.name]
                t = dict(clip.timing)
                nn = float(clip.frames)
                norm = {k: round(t[k] / nn, 4) for k in ("apex", "contact") if k in t}
                for k in ("hold", "active"):
                    if k in t:
                        norm[k] = [round(t[k][0] / nn, 4), round(t[k][1] / nn, 4)]
                rec = {"first": a, "last": b, "frames": clip.frames, "seconds": round(clip.frames / T.FPS, 4), "loop": clip.loop,
                       "timing": t, "normalized": norm, "notes": clip.notes,
                       "lint": {k: v for k, v in reports[clip.name].items() if k not in ("tip_speed_mps", "plants")}}
                if clip.root_vel.length > 0:
                    rec["root_velocity_mps"] = round(clip.root_vel.length, 3)
                info["clips"][clip.name] = rec
            with open(FBX + ".json", "w", encoding="utf-8", newline="\n") as fh:
                json.dump(info, fh, indent=1, ensure_ascii=False)
            print("EXPORTADO", FBX, "cuadros 1 ..", last, f"{os.path.getsize(FBX) / 1e6:.2f} MB")
    if RENDERS:
        import team_review as TR
        rv = TR.Review(ch, RENDERS, partner=any(getattr(c, "partner", None) is not None for c, _ in baked))
        for clip, frames in baked:
            fs = sheet_frames(clip)
            # Kaito donde lo alcanza el golpe: a la embestida más el alcance (los demás clips, a 2.4 m)
            t = clip.timing
            kd = max(2.4, t.get("lunge", 0.0) + t.get("reach", 1.6)) if "contact" in t else 2.4
            print(rv.clip_sheet(clip, ranges[clip.name][0], rootsd[clip.name], fs, [frame_label(clip, f) for f in fs], kaito_dist=kd))
        with open(os.path.join(RENDERS, CHAR + "_lint.json"), "w", encoding="utf-8") as fh:
            json.dump(reports, fh, indent=0)
    print(f"listo en {time.time() - t0:.1f} s; avisos {len(warnings)}")
    if failures:
        print("FALLARON", len(failures), "chequeos:")
        for f in failures:
            print("   -", f)
        sys.exit(1)


main()
