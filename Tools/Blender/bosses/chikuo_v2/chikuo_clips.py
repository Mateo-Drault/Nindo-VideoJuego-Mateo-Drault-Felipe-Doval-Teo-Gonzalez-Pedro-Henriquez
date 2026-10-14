"""Clips de pelea del Chikuō ermitaño (fase C4): la tabla del contrato (Docs/handoff/diseno/chikuo_v2.md, sección 16) y
las poses compartidas. Cada familia vive en su módulo (chikuo_clips_perch, _ground, _react, _story) y esta lista los junta
en el orden de la toma del FBX.

Gramática del personaje (la hoja de acciones y la de expresiones del concepto): un viejo de miembros largos, liviano y
saltarín, que se mueve como un mono en las cañas y como un maestro de bastón en el piso. Todo lo grande arranca de la
cadera (el pie que empuja, la cadera que gira, el hombro y la mano llegan después), cada aviso es una pose que rompe la
silueta desde arriba y se sostiene moviéndose, y cada golpe se pasa y se asienta. La cara acompaña: la sonrisa pícara de
siempre, los cachetes inflados al soplar, la carcajada con los ojos cerrados.

'timing' (cuadros a 30 fps; va al sidecar BambooMaster.fbx.json y de ahí a ChikuoTimings.cs):
  space                 ground | perch | air | pole (chikuo_anim)
  tell [a, b]           la anticipación hasta la pose de aviso (b = apex)       apex   la pose de aviso
  contact / active      el primer cuadro que pega / la ventana que pega            kind   parry | dodge | none
  load [a, b]           la caña cargada (Load ... Unload: las campanas blancas)    air    [a, b] los pies en el aire
  release_rate          AttackDef.releaseRate del golpe (StepTimeline)             glow   los slots que se encienden
  chain_from / chain_to la pose con la que empieza / termina (PERCH, READY, HANG, AIR, DAZED_SIT, DAZED_LIE...)
  bend                  grados del arco con el que se miden manos y pies en el culmo
  travel                el avance que el JUEGO aplica al transform (canal 'travel' de las claves, metros hacia adelante)
"""
import math
from mathutils import Vector
from nindo_anim import Key
import chikuo_rig as CR
from chikuo_anim import CClip, merge, free, grip, legs, staff_world, staff_spine, staff_lips

# ============================================================================ el posado (la pose madre de arriba)
# Agachado sobre el anillo del nudo (z = 0) como en la hoja de acciones: las rodillas bien abiertas y altas, los pies
# juntos a los dos lados del culmo (los talones en el anillo), el tronco casi derecho delante del culmo (del lado de Kaito:
# la caña no le parte la barba en pantalla), la flauta cruzada detrás del cuello como un yugo con los dos puños por afuera
# de los hombros y los codos abajo (la hoja: el puño adelante, el antebrazo parado). El diseño pedía la izquierda en el
# culmo (GripHigh): desde la cámara la tapaba la capa y cada clip tenía que soltarla y volver a agarrarla; se mantiene en
# equilibrio con los pies, como en el concepto.
PERCH_FEET = legs((-0.155, -0.115, 0.115), (0.155, -0.115, 0.115), rr=(0, 0, -32), rl=(0, 0, 32),
                  kr=(-1.0, -0.7, 0.35), kl=(1.0, -0.7, 0.35))
STAFF_SHOULDERS = staff_spine((-1.00, 0.11, 1.95), (1, 0, 0.03), (0, -0.3, 1))
PERCH = merge(dict(hips=(0, -0.34, -0.58), hips_rot=(10, 0, 0), spine=(-6, 0, 0), spine1=(0, 0, 0), spine2=(8, 0, 0),
                   neck=(8, 0, 0), head=(8, 0, 0), face="grin"),
              PERCH_FEET, STAFF_SHOULDERS,
              grip("r", 0.38, elbow=(-0.6, -0.2, -1)),
              grip("l", 1.66, elbow=(0.6, -0.2, -1)))
# de cerbatana desde el posado: el tronco se inclina hacia Kaito, la flauta de punta 35° hacia abajo con la boquilla en
# los labios y las dos manos juntas cerca de la boquilla (16.6 del diseño); los cachetes inflados
AIM = (0.0, -0.819, -0.574)                  # 35° hacia abajo, al frente del modelo (el código lo gira hacia Kaito)
BLOW_STAFF = staff_lips(CR.STAFF_LEN, tuple(-x for x in AIM), (0, 0, 1))
PERCH_BLOW = merge(PERCH, dict(hips=(0, -0.36, -0.60), hips_rot=(16, 0, 0), spine=(4, 0, 0), spine1=(6, 0, 0), spine2=(8, 0, 0),
                               neck=(6, 0, 0), head=(14, 0, 0), face="blow"),
                   BLOW_STAFF, grip("l", CR.STAFF_LEN - 0.17, elbow=(1, 0.2, -0.6)),
                   grip("r", CR.STAFF_LEN - 0.36, elbow=(-1, 0.2, -0.6)))
# colgado cabeza abajo DELANTE del culmo, mirando a Kaito (la hoja original): las piernas abrazan el culmo arriba del nudo
# (los muslos a los dos lados, las pantorrillas cruzadas detrás), la espalda hacia la caña, la capa y los cascabeles caen
# hacia el piso alrededor de la cabeza; sopla de cerbatana con las dos manos en la boquilla
HANG = merge(dict(hips=(0, -0.27, -1.56), hips_rot=(12, 180, 0), spine=(4, 0, 0), spine1=(4, 0, 0), spine2=(2, 0, 0),
                  neck=(-8, 0, 0), head=(-20, 0, 0), face="blow"),
             legs((0.10, 0.21, 0.30), (-0.10, 0.23, 0.38), rr=(-40, 180, 0), rl=(-40, 180, 0), kr=(1.0, -0.35, 0.3), kl=(-1.0, -0.35, 0.3)),
             staff_lips(CR.STAFF_LEN, (0.0, 0.819, 0.574), (0, 0, -1)),
             grip("l", CR.STAFF_LEN - 0.17, elbow=(1, -0.2, 0.6)),
             grip("r", CR.STAFF_LEN - 0.36, elbow=(-1, -0.2, 0.6)))
HANG_X = dict(cloak_hang=0.97)

# ============================================================================ en el piso (fase 2 y la coda)
# En guardia de bastón (16.6: la derecha en el vendado, la izquierda 0.6 m más arriba): la izquierda adelante, las
# piernas abiertas y dobladas (el kung fu de viejo), la flauta-bastón en diagonal hacia Kaito.
READY_FEET = legs((-0.30, 0.20, 0.115), (0.24, -0.30, 0.115), rr=(0, 0, -40), rl=(0, 0, 8), kr=(-0.7, -1, 0), kl=(0.3, -1, 0))
STAFF_GUARD = staff_world((-0.40, 0.21, 0.97), (0.40, -0.83, 0.39), (0, -0.3, 1))
READY = merge(dict(hips=(0, -0.02, -0.17), hips_rot=(6, 0, -22), spine=(2, 0, 8), spine1=(2, 0, 6), spine2=(4, 0, 4),
                   neck=(-4, 0, 2), head=(-4, 0, 4), face="grin"),
              READY_FEET, STAFF_GUARD,
              grip("r", 0.23, elbow=(-1, 0.4, -0.6)),
              grip("l", 0.83, elbow=(1, 0.2, -0.8)))
# la flauta alzada en diagonal detrás del hombro derecho (el salto del concepto), pegada al pecho
AIR_STAFF = staff_spine((-0.22, 0.90, 2.75), (0.04, -0.92, -0.38), (-0.9, 0.2, -0.1))
# en el aire (el salto del concepto): la rodilla izquierda arriba, la derecha estirada atrás y abajo, la flauta alzada en
# la derecha, la izquierda abierta al costado como una garra; los pies a la altura de la raíz (el arco lo lleva el código)
AIR = merge(dict(hips=(0, 0.05, -0.30), hips_rot=(-10, 0, 0), spine=(4, 0, 0), spine1=(4, 0, 4), spine2=(4, 0, 6),
                 neck=(-4, 0, -4), head=(-8, 0, -4), face="grin"),
            legs((-0.16, 0.42, 0.10), (0.18, -0.30, 0.42), rr=(-30, 0, -10), rl=(-50, 0, 10), kr=(-0.2, -1, 0), kl=(0.2, -1, 0.3)),
            AIR_STAFF, grip("r", 0.95, elbow=(-1, 0.4, -0.3)),
            free("l", (0.70, -0.14, 1.50), elbow=(0.4, 0.6, -0.6), fing="claw"))

LAB = {"PERCH": (PERCH, "perch"), "PERCH_BLOW": (PERCH_BLOW, "perch"), "HANG": (HANG, "perch", HANG_X), "READY": (READY, "ground"),
       "AIR": (AIR, "air")}


def K(f, *ds, ease="inout", ease_ch=None, stops=(), **kw):
    return Key(f, merge(*ds, **kw), ease, ease_ch, stops)


# ============================================================================ los pies en el piso
# Puntos de la suela respecto del tobillo en reposo (pie derecho; el izquierdo espejado en X): el talón y la bola. Un pie
# que rueda gira sobre uno de ellos, que queda quieto en el piso (rodar no es patinar).
HEEL_REL = Vector((0.0, CR.SOLE_HEEL_Y - CR.ANKLE.y, -CR.ANKLE.z))
BALL_REL = Vector((CR.BALL.x - CR.ANKLE.x, CR.BALL.y - CR.ANKLE.y, -CR.ANKLE.z))
ANKLE_Z = CR.ANKLE.z


def foot_rot(yaw, pitch):
    """El giro del pie como lo arma el Solver (foot_s_rot = (pitch, roll, yaw)): Z(yaw) @ X(pitch). pitch > 0 baja la
    punta (el talón se levanta)."""
    from mathutils import Matrix
    return Matrix.Rotation(math.radians(yaw), 3, 'Z') @ Matrix.Rotation(math.radians(pitch), 3, 'X')


def rolled(s, x, y, yaw, pitch, pivot):
    """El tobillo del pie s apoyado en (x, y) (donde estaría el tobillo con el pie plano) rodando 'pitch' grados sobre el
    talón (pitch < 0, la punta arriba) o la bola (pitch > 0): el punto de apoyo no se mueve. Devuelve (tobillo, giro, dedos)."""
    mx = 1.0 if s == "r" else -1.0
    P = (HEEL_REL if pivot == "heel" else BALL_REL).copy()
    P.x *= mx
    flat = Vector((x, y, ANKLE_Z))
    contact = flat + foot_rot(yaw, 0.0) @ P
    ankle = contact - foot_rot(yaw, pitch) @ P
    toe = max(0.0, pitch) if pivot == "ball" else 0.0
    return tuple(ankle), (pitch, 0.0, yaw), toe


def travel_of(keys, frames):
    """El canal 'travel' de las claves del cuerpo, cuadro a cuadro (lo que el código le hace avanzar al transform)."""
    tmp = CClip("_travel", frames, [Key(k.frame, dict(k.ctrl), k.ease, k.ease_ch, k.stops) for k in keys])
    return [tmp.controls(f).get("travel") or 0.0 for f in range(frames + 1)], tmp


SOLE_CLEAR = 0.03                  # lo que la suela se despega del piso en el vuelo de un paso (con el pie inclinado)


def sole_low(s, yaw, pitch):
    """Cuánto queda la suela más baja debajo del tobillo con el pie girado (m, positivo hacia abajo)."""
    mx = 1.0 if s == "r" else -1.0
    toe = Vector(((CR.TOE_TIP.x - CR.ANKLE.x) * mx, CR.SOLE_TOE_Y - CR.ANKLE.y, -CR.ANKLE.z))
    R = foot_rot(yaw, pitch)
    return max(-(R @ Vector((P.x * mx, P.y, P.z))).z for P in (HEEL_REL, BALL_REL, toe))


def feet_track(keys, frames, plan, lift=0.12, swing_pitch=-12.0):
    """Pista de los pies para un clip de piso: cada pie con sus apoyos EN EL MUNDO (el transform del primer cuadro), que no
    patinan aunque el código lo haga avanzar (travel); entre dos apoyos el pie vuela en arco y fuera de ellos manda lo que
    traen las claves del cuerpo (los saltos, en el marco de la cadera).
    plan = {"r": [apoyo, ...], "l": [...]}, apoyo = (f0, f1, x, y, yaw[, rolls]) con rolls = [(cuadro, grados, 'heel'|
    'ball'), ...] (el pie que rueda dentro del apoyo, interpolado) o un dict {"free": (f0, f1)} para un tramo de las claves."""
    tr, body = travel_of(keys, frames)
    out = [dict() for _ in range(frames + 1)]
    for s, segs in plan.items():
        plants = [p for p in segs if not isinstance(p, dict)]
        frees = [p["free"] for p in segs if isinstance(p, dict)]
        for f in range(frames + 1):
            k = out[f]
            in_free = any(a <= f <= b for a, b in frees)
            here = next((p for p in plants if p[0] <= f <= p[1]), None)
            if here is None and not in_free:
                prev = max((p for p in plants if p[1] < f), key=lambda p: p[1], default=None)
                nxt = min((p for p in plants if p[0] > f), key=lambda p: p[0], default=None)
                if prev is not None and nxt is not None and not any(prev[1] <= a and b <= nxt[0] for a, b in frees):
                    u = (f - prev[1]) / float(nxt[0] - prev[1])
                    e = u * u * (3.0 - 2.0 * u)
                    x = prev[2] + (nxt[2] - prev[2]) * e
                    y = prev[3] + (nxt[3] - prev[3]) * e
                    yaw = prev[4] + (nxt[4] - prev[4]) * e
                    hgt = (lift if len(nxt) < 7 else nxt[6]) * math.sin(math.pi * u)
                    # la punta sube en el vuelo (no raspa) y el pie nunca baja a menos de SOLE_CLEAR del piso
                    p = swing_pitch * math.sin(math.pi * u)
                    z = max(ANKLE_Z + hgt, sole_low(s, yaw, p) + SOLE_CLEAR)
                    k.update({"foot_" + s: (x, y + tr[f], z), "foot_%s_rot" % s: (p, 0.0, yaw), "toe_" + s: 0.0,
                              "fsp_" + s: 0.0})
                    continue
                in_free = True
            if in_free or here is None:
                c = body.controls(f)
                for ch in ("foot_" + s, "foot_%s_rot" % s, "toe_" + s, "fsp_" + s):
                    if c.get(ch) is not None:
                        k[ch] = c[ch]
                continue
            f0, f1, x, y, yaw = here[:5]
            rolls = here[5] if len(here) > 5 and here[5] else []
            pitch, pivot = 0.0, "ball"
            if rolls:
                pts = sorted(rolls)
                if f <= pts[0][0]:
                    pitch, pivot = pts[0][1], pts[0][2]
                elif f >= pts[-1][0]:
                    pitch, pivot = pts[-1][1], pts[-1][2]
                else:
                    for (fa, pa, va), (fb, pb, vb) in zip(pts, pts[1:]):
                        if fa <= f <= fb:
                            u = (f - fa) / float(max(1, fb - fa))
                            u = u * u * (3.0 - 2.0 * u)
                            pitch = pa + (pb - pa) * u
                            pivot = vb if abs(pb) >= abs(pa) else va
                            break
            ank, rot, toe = rolled(s, x, y + tr[f], yaw, pitch, pivot)
            k.update({"foot_" + s: ank, "foot_%s_rot" % s: rot, "toe_" + s: toe, "fsp_" + s: 0.0})
    return [Key(f, k, "lin") for f, k in enumerate(out)]


# los pies de la guardia (READY_FEET) como apoyos: (x, y, yaw)
READY_R, READY_L = (-0.30, 0.20, -40.0), (0.24, -0.30, 8.0)


# ============================================================================ los clips
def clips(rig):
    """Todos los clips en el orden de la toma (arriba, al piso y de vuelta, huecos, piso, historia)."""
    import chikuo_anim as CA
    import chikuo_clips_perch as CPe
    import chikuo_clips_ground as CG
    import chikuo_clips_drop as CD
    import chikuo_clips_react as CRe
    import chikuo_clips_story as CS
    kit = CA.Kit(rig)
    out = []
    for mod in (CPe, CD, CRe, CG, CS):
        out += mod.clips(kit)
    return out


# poses de referencia para el encadenado (lint): el primer cuadro de su clip
CHAIN_REF = {"PERCH": "PerchIdle", "READY": "Idle", "HANG": "HangDart2", "AIR": "LeapAir", "POLE": "PoleClimb",
             "BALANCE": "PoleBalance", "FLUTE": "FluteNote", "DIVE_LAND": "DiveLand", "DAZED_SIT": "DazedSit",
             "DAZED_LIE": "DazedLie", "FLUNG": "FlungAir", "SPLAT": "SlideDown", "STAFF_DOWN": "StaffDropRecover",
             "CROSS": "DefeatIdle", "DIVE_TOP": "PoleDive"}


# ============================================================================ el contrato (diseño, sección 16)
# cuadros y eventos de cada estado: build_chikuo falla si un clip se aparta (el código lee los tiempos del sidecar, pero
# la pelea del diseño se simuló con estos)
CONTRACT_FRAMES = {
    "PerchIdle": 48, "PerchDart": 24, "PerchDart2": 34, "PerchVolley": 51, "PerchVolley4": 48, "PerchWhistle": 42,
    "TalaShot": 30, "HangDrop": 11, "HangDart2": 18, "HangClimb": 15, "PerchLaugh": 36, "PerchWobble": 8, "StalkSweep": 41,
    "CatapultDraw": 30, "CatapultKick": 15, "LeapCrouch": 7, "LeapAir": 12, "LeapGrab": 6, "Climb": 24, "DecoySpin": 18,
    "Dive": 29, "DiveLand": 14, "FeetStuck": 48, "StaffDrop": 27, "StaffDropRecover": 12, "Vault": 27, "JumpCrouch": 9,
    "FlungAir": 12, "FlungLand": 11, "DazedSit": 30, "DazedSitHit": 10, "Splat": 9, "SlideDown": 18, "MissGrab": 14,
    "DazedLie": 30, "DazedLieHit": 10, "Slip": 15, "Stumble": 30, "PoleFall": 14, "GetUp": 12, "Detuned": 42, "Tuned": 36,
    "StaffStuck": 33, "BackFlip": 12, "HopBack": 14, "Thrust": 27, "StaffSpin2": 30, "CraneKick": 28, "NoteSmash": 36,
    "LowSweep": 39, "GroundDart": 25, "PolePlant": 14, "PoleClimb": 14, "PoleBalance": 30, "PoleDive": 29, "FluteRaise": 14,
    "FluteNote": 13, "AnswerBlow": 13, "AnswerStamp": 13, "GroundLaugh": 36, "PhaseBow": 120, "PhaseForest": 150,
    "Defeat": 165, "DefeatIdle": 60, "Hit": 10, "HitHeavy": 16, "Parried": 12, "ParriedPerfect": 18,
}
CONTRACT_EVENTS = {
    "PerchIdle": [], "PerchDart": [(14, "DartSpawn")], "PerchDart2": [(14, "DartSpawn"), (24, "DartSpawn")],
    "PerchVolley": [(3, "Load"), (17, "DartSpawn"), (28, "DartSpawn"), (39, "DartSpawn"), (42, "Unload")],
    "PerchVolley4": [(3, "Load"), (14, "DartSpawn"), (22, "DartSpawn"), (30, "DartSpawn"), (39, "DartSpawn"), (40, "Unload")],
    "PerchWhistle": [(3, "Load"), (27, "DartSpawn"), (30, "Unload")], "TalaShot": [(14, "DartSpawn")],
    "HangDrop": [(10, "Hang")], "HangDart2": [(9, "DartSpawn"), (18, "DartSpawn")], "HangClimb": [(8, "Unload"), (15, "Perch")],
    "PerchLaugh": [], "PerchWobble": [], "StalkSweep": [(8, "Load"), (26, "Contact")],
    "CatapultDraw": [(0, "Load"), (22, "AimFix"), (30, "LeaveStalk")], "CatapultKick": [(15, "Contact")],
    "LeapCrouch": [(7, "LeaveStalk")], "LeapAir": [], "LeapGrab": [(0, "GrabStalk"), (6, "Perch")],
    "Climb": [(4, "GrabStalk"), (24, "Perch")], "DecoySpin": [],
    "Dive": [(10, "LeaveStalk"), (28, "Contact")], "DiveLand": [(0, "Land")], "FeetStuck": [],
    "StaffDrop": [(6, "LeaveStalk"), (19, "Land"), (26, "Contact")], "StaffDropRecover": [],
    "Vault": [(6, "Plant"), (9, "LeaveStalk"), (27, "GrabStalk")], "JumpCrouch": [(9, "LeaveStalk")],
    "Splat": [(2, "Contact")],
    "Thrust": [(15, "Contact")], "StaffSpin2": [(17, "Contact"), (29, "Contact")], "CraneKick": [(15, "Contact")],
    "NoteSmash": [(20, "Contact")], "LowSweep": [(24, "Contact")], "GroundDart": [(17, "DartSpawn")],
    "PolePlant": [(8, "Plant")], "PoleClimb": [(0, "Load")], "PoleDive": [(0, "LeaveStalk"), (28, "Contact")],
    "FluteNote": [(0, "Note")], "AnswerBlow": [(4, "DartSpawn")], "AnswerStamp": [(4, "Stamp")],
    "PhaseBow": [(70, "Note"), (85, "Note"), (100, "Note")],
    "PhaseForest": [(60, "Note"), (90, "Note"), (120, "LeaveStalk"), (150, "GrabStalk")],
}
# los nombres que Enemy toca por config y no son clips propios (generate_assets los agrega al controller como estados con
# el mismo clip)
ALIASES = {"Guard": "Idle", "Counter": "Idle", "Spotted": "Idle", "Exhausted": "DazedSit", "ExhaustedHit": "DazedSitHit",
           "ExhaustedRise": "GetUp"}
GOLD, RED, WHITE = "gold", "red", "white"
CHIMES_ALL = ("Chikuo_GlintChimesHi", "Chikuo_GlintChimesLo")


def tell_shots(clip):
    """Los cuadros que se miran con la cámara del juego: [(cuadro, etiqueta, slots que brillan, color)]."""
    t = clip.timing
    if "shots" in t:
        return [tuple(s) for s in t["shots"]]
    out = []
    if "apex" in t:
        out.append((t["apex"], "aviso", tuple(t.get("glow", ())), RED if t.get("kind") == "dodge" else GOLD))
    if "load" in t:
        a, b = t["load"]
        out.append(((a + b) // 2, "cargada", CHIMES_ALL, WHITE))
    return out
