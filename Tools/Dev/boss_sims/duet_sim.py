"""Simulación del dúo Kokuyō + sombra (a 60 Hz), con la misma lógica que el C#:
 - KokuyoMoves.Act(n): patrones, pesos, cooldowns, rangos y dúos (cues before/after);
 - StepTimeline (T = natural + pausa del acto; MinWindup x0.9 compensado), largo de cada paso;
 - KokuyoBoss.Shadow: turnos (probabilidad al terminar un combo, tope de silencio, separación mínima, primer turno),
   la regla Fit/Gap (0.9 / 1.05 / 1.1; 1.2 después del Nobi) en PlanWindup del cuerpo y de la sombra;
 - KageShadow: Nobi (1.2 s, el cuerpo quieto hasta que la tinta vuelve), Giri (acercamiento / salida de la oscuridad
   1.05 s antes), Nui (deslizamiento + 0.8 s), Watari (alineación + 0.6 s + cruce);
 - el bot "bueno" de AutoPilot (reacciona al hyōshigi: N(0.28, 0.06) s + latencia + 1 cuadro, 10 % no lo ve, 5 % se
   confunde) decide parry/golpe; los parries suman postura y abren rodillas (3.6 s) como en el juego.
Mide por acto: golpes por minuto de él y de la sombra, separación mínima entre golpes de distinto atacante,
anillos superpuestos, tiempo visible de la sombra antes de su golpe en el eclipse y el éxito del bot por golpe.
"""
import random, math, statistics, json, os, sys

DT = 1 / 60.0
LAT = 0.02  # latencia de salida de audio típica (AudioManager.OutputLatency, buffer 1024 a 48 kHz)

# ---------------------------------------------------------------- clips (KokuyoTimings)
CLIPS = {
    "Kesagiri": (1.2, 0.3889, 0.5, 0.5833, 1.6), "Gyakugiri": (1.0, 0.3333, 0.4667, 0.5667, 1.6),
    "Tsuki": (1.5333, 0.4783, 0.587, 0.6522, 0.4), "Ichimonji": (1.6, 0.4375, 0.5833, 0.6667, 1.6),
    "KabutoWari": (2.0, 0.3333, 0.45, 0.4833, 1.6), "ShadowEmerge": (1.1, 0.2727, 0.4242, 0.5152, 1.6),
}
REC = {"RecoverL": 0.5, "RecoverHR": 0.4, "TsukiRecover": 0.6, "ShadowSink": 1.4}
PARRY_HOLD = [0, 0.42, 0.30, 0.22]
DODGE_HOLD = [0, 0.15, 0.08, 0.08]
GO_LEAD = 0.36
MAXLEAD = {"H": 0.85, "U": 1.0}
TICK = {"H": 0.38, "U": 0.42}


def natural(c):
    s, ap, co, ae, rr = CLIPS[c]
    return ap * s / 0.85 + (co - ap) * s / rr


def step_T(c, kind, act, special=""):
    hold = (PARRY_HOLD[act] * (0.5 if c == "Tsuki" else 1)) if kind == "H" else DODGE_HOLD[act]
    T = natural(c) + hold
    return max(T, 0.70 if kind == "U" else 0.38)


def tail(c):
    s, ap, co, ae, rr = CLIPS[c]
    return (1 - co) * s * 0.95


# pasos: (clip, kind) o ("R:<clip>", None)
def S(c, k):
    return (c, k)


def R(c):
    return ("R:" + c, None)


def patterns(act):
    kesa, gyaku, tsuki, ichi, kabuto, emerge = S("Kesagiri", "H"), S("Gyakugiri", "H"), S("Tsuki", "H"), S("Ichimonji", "U"), S("KabutoWari", "U"), S("ShadowEmerge", "H")
    P = []
    def add(name, w, steps, cd=0, minr=0, maxr=5.0, cues=None):
        P.append({"name": name, "w": w, "steps": steps, "cd": cd, "minr": minr, "maxr": maxr, "cues": cues or [], "last": -99})
    if act == 1:
        add("Corte del Monje", 1.6, [kesa, R("RecoverL")])
        add("Luna Doble", 1.8, [kesa, gyaku, R("RecoverHR")])
        add("Colmillo", 1.2, [tsuki, R("TsukiRecover")], 4, 4, 8.5)
        add("Horizonte", 1.0, [ichi], 7, 0, 5.5)
        add("Rompecascos", 0.9, [kabuto], 9, 2.5, 10)
        add("Sombra y Acero", 0.9, [kesa, R("RecoverL")], 12, cues=[(0, "nobi", True, "any")])
        return P
    if act == 2:
        add("Luna Doble", 1.2, [kesa, gyaku, R("RecoverHR")])
        add("Colmillo", 0.9, [tsuki, R("TsukiRecover")], 4, 4, 8.5)
        add("Horizonte", 0.7, [ichi], 7, 0, 5.5)
        add("Rompecascos", 0.7, [kabuto], 9, 2.5, 10)
        add("Escuela", 1.3, [kesa, gyaku, tsuki, R("TsukiRecover")])
        add("Paso de Sombra", 1.0, [R("ShadowSink"), emerge, R("RecoverHR")], 8, 0, 16)
        add("Pinza", 1.2, [kesa, gyaku, R("RecoverHR")], 8, cues=[(0, "giri", False, "opp")])
        add("Amago", 1.0, [kesa, R("RecoverL")], 9, cues=[(0, "giri", True, "flank")])
        add("Clavo y Colmillo", 0.8, [tsuki, R("TsukiRecover")], 10, 4, 8.5, cues=[(0, "nui", True, "any")])
        return P
    add("Luna Doble", 0.9, [kesa, gyaku, R("RecoverHR")])
    add("Colmillo", 0.7, [tsuki, R("TsukiRecover")], 4, 4, 8.5)
    add("Horizonte", 0.5, [ichi], 7, 0, 5.5)
    add("Rompecascos", 0.5, [kabuto], 9, 2.5, 10)
    add("Escuela", 1.0, [kesa, gyaku, tsuki, R("TsukiRecover")])
    add("Paso de Sombra", 0.9, [R("ShadowSink"), emerge, R("RecoverHR")], 8, 0, 16)
    add("Desfile", 1.3, [kesa, gyaku, kesa, tsuki, kabuto], 10)
    add("Media Luna", 1.0, [gyaku, ichi], 6)
    add("Media Luna Negra", 1.1, [gyaku, ichi], 9, cues=[(0, "giri", False, "opp")])
    add("Eclipse Doble", 1.0, [kesa, R("RecoverL")], 9, cues=[(0, "giri", True, "opp" if OLD else "flank")])
    return P


def patterns_old(act):
    keep = {1: {"Corte del Monje": 1.6, "Luna Doble": 1.8, "Colmillo": 1.2, "Horizonte": 1.0, "Rompecascos": 0.9},
            2: {"Luna Doble": 1.4, "Colmillo": 1.0, "Horizonte": 0.8, "Rompecascos": 0.8, "Escuela": 1.6, "Paso de Sombra": 1.2},
            3: {"Luna Doble": 1.0, "Colmillo": 0.8, "Horizonte": 0.6, "Rompecascos": 0.6, "Escuela": 1.2, "Paso de Sombra": 1.0,
                "Desfile": 1.5, "Media Luna": 1.2}}[act]
    out = []
    for p in patterns(act):
        if p["name"] in keep:
            p["w"] = keep[p["name"]]
            out.append(p)
    if act == 1:   # el Acto 1 viejo no tenía dúo
        return out
    return out


DMG = {"Kesagiri": 24, "Gyakugiri": 22, "Tsuki": 28, "Ichimonji": 34, "KabutoWari": 38, "ShadowEmerge": 24,
       "nobi": 16, "giri2": 18, "giri3": 20, "nui": 18, "watari": 20}


def gap(first, second):
    return max(1.1 if first == "U" else 0.9, MAXLEAD[second] + 0.05)


OLD = os.environ.get("OLD") == "1"
# los turnos de hoy salen de KokuyoBoss.Shadow (cs_knobs: una sola fuente); OLD=1 = los de antes de la fase C2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cs_knobs
_KK = cs_knobs.kokuyo()
TURN_CHANCE = [0, 0.4, 0.6, 0.5] if OLD else list(_KK["turn_chance"])
TURN_MIN_GAP = [0, 5.5, 2.6, 3.2] if OLD else list(_KK["turn_min_gap"])
MAX_QUIET = [0, 11, 5.5, 6.5] if OLD else list(_KK["max_quiet"])
FIRST_TURN = [0, 15, 1.6, 2.5] if OLD else list(_KK["first_turn"])
GAP_AFTER_NOBI = 1.2 if OLD else 1.7
NOBI_MIN = 2.5 if OLD else 0.0
TEACH_NOBI = 1.0 if OLD else 1.5
TEACH_DARK = 1.0 if OLD else 1.4
BODY_AFTER = float(os.environ.get("BODY_AFTER", "0.6"))
DEFER = os.environ.get("DEFER", "1") == "1" and not OLD
TURN_CHANCE[1] = float(os.environ.get("TC1", TURN_CHANCE[1]))
TURN_MIN_GAP[1] = float(os.environ.get("TG1", TURN_MIN_GAP[1]))
MAX_QUIET[1] = float(os.environ.get("MQ1", MAX_QUIET[1]))
for _i in (1, 2, 3):
    TURN_CHANCE[_i] = float(os.environ.get("TC%d" % _i, TURN_CHANCE[_i]))
    TURN_MIN_GAP[_i] = float(os.environ.get("TG%d" % _i, TURN_MIN_GAP[_i]))
    MAX_QUIET[_i] = float(os.environ.get("MQ%d" % _i, MAX_QUIET[_i]))
    FIRST_TURN[_i] = float(os.environ.get("FT%d" % _i, FIRST_TURN[_i]))
EMERGE_LEAD = 1.05
EMERGE_CLEAR = float(os.environ.get("EMERGE_CLEAR", "0.25"))
GIRI_NAT = [0, 0, natural("Kesagiri") + 0.30, natural("Kesagiri") + 0.22]


class Bot:
    """AutoPilot 'bueno': aprieta al oír el hyōshigi + tiempo de reacción; resuelve el golpe."""
    def __init__(self, rng, mean=0.28, sd=0.06, miss=0.1, wrong=0.05):
        self.rng, self.mean, self.sd, self.miss, self.wrong = rng, mean, sd, miss, wrong

    def outcome(self, kind):
        r = self.rng
        if r.random() < self.miss:
            return "hit"
        rt = min(0.55, max(0.15, r.gauss(self.mean, self.sd))) + LAT + 1 / 60
        press = -TICK[kind] + rt          # respecto del golpe
        dash = (kind == "U") != (r.random() < self.wrong)
        if dash:
            ok = press + 0.02 <= 0 <= press + 0.24
            return "dodge" if ok else "hit"
        if kind == "U":
            return "hit"
        if -0.24 <= press <= 0:
            return "perfect" if press >= -0.11 else "parry"
        return "hit"


class Sim:
    def __init__(self, act, seed, seconds=70.0, dist_mean=4.6, level="bueno", old=False):
        self.rng = random.Random(seed)
        self.old = old
        self.act = act
        self.t = 0.0
        self.end = seconds
        self.P = patterns_old(act) if old else patterns(act)
        self.dmg = 0.0
        self.old_next = 0.0
        self.bot = Bot(self.rng) if level == "bueno" else Bot(self.rng, 0.32, 0.08, 0.25, 0.1)
        self.dist_mean = dist_mean
        # cuerpo
        self.bstate = "chase"; self.bnext = 0.6; self.bsteps = None; self.bi = 0; self.bimpact = -1; self.bkind = None
        self.bstep_end = 0; self.bguard_until = 0; self.posture = 0.0; self.kneel_until = -1
        self.bpat = None; self.brecoil_until = -1
        # sombra
        self.sstate = "hunt"; self.simpact = -1; self.skind = None; self.smove = ""; self.sbusy_until = 0
        self.sready_at = 0; self.svisible_at = -1; self.shold_body_until = -1
        # libro
        self.blast = -99; self.blastk = "H"; self.slast = -99; self.slastk = "H"; self.slastm = ""
        self.last_turn = -99; self.turn_asked = False; self.act_start = 0.0; self.nobi_taught = act > 1
        self.events = []   # (t_impacto, actor, kind, move, ring_start, visible_from)
        self.outcomes = []
        # golpes de dúo (KokuyoBoss.Shadow.RunCues): el que la sombra no pudo dar porque se estaba apagando queda guardado
        # y sale apenas puede dentro de ese paso (DEFER=0 en el entorno = como antes, se perdía)
        self.deferred = None   # (patrón, paso, golpe, lado)
        self.cues = {}         # acto -> [pedidos, al toque, guardados que salieron, perdidos]

    # -------------------------------------------------------- reglas
    def fit(self, t, pending, gap_before, gap_after):
        if pending <= self.t or t + gap_before <= pending:
            return t
        return max(t, pending + gap_after)

    def dark(self):
        return self.act == 3 and not self.old

    def gbd(self, body, shadow):
        # KokuyoDuet.GapBeforeDark: la salida de la oscuridad (EmergeLead antes) a EmergeClear de un golpe de él
        lead = getattr(self, "slead", EMERGE_LEAD)
        return max(gap(body, shadow), lead + EMERGE_CLEAR) if self.dark() else gap(body, shadow)

    def earliest_body(self, t, kind):
        if self.simpact > self.t:
            ga = max(gap(self.skind, kind), GAP_AFTER_NOBI if self.smove == "nobi" else 0)
            t = self.fit(t, self.simpact, self.gbd(kind, self.skind), ga)
        ga = max(gap(self.slastk, kind), GAP_AFTER_NOBI if self.slastm == "nobi" else 0)
        return max(t, self.slast + ga)

    def earliest_shadow(self, t, kind):
        if self.bimpact > self.t:
            t = self.fit(t, self.bimpact, gap(kind, self.bkind), self.gbd(self.bkind, kind))
        return max(t, self.blast + self.gbd(self.blastk, kind))

    # -------------------------------------------------------- sombra
    def shadow_can(self):
        return self.sstate == "hunt" and self.t >= self.sready_at

    def shadow_rearming(self):
        """KageShadow.Rearming: suelta o a oscuras, terminando el golpe anterior (pegada a sus pies no cuenta)."""
        return self.act >= 2 and self.sstate == "hunt" and self.t < self.sready_at

    def cue_stat(self, i):
        c = self.cues.setdefault(self.act, [0, 0, 0, 0])
        c[i] += 1

    def run_cue(self, mv, sd):
        """Un golpe de dúo del paso que arranca: sale, queda guardado (la sombra se apaga) o se pierde."""
        self.cue_stat(0)
        if self.shadow_try(mv, False, sd):
            self.cue_stat(1)
            self.on_duet_cue()
        elif DEFER and self.shadow_rearming():
            self.deferred = (self.bpat, self.bi, mv, sd)
        else:
            self.cue_stat(3)

    def on_duet_cue(self):
        pass

    def run_deferred(self):
        """El golpe de dúo guardado: solo mientras él siga en ese paso de ese patrón; sale apenas la sombra puede (la
        regla lo acomoda contra el golpe de él en camino). Devuelve True si hay algo guardado (no se piden turnos)."""
        if self.deferred is None:
            return False
        pat, bi, mv, sd = self.deferred
        if self.bstate != "attack" or self.bpat is not pat or self.bi != bi:
            self.deferred = None
            self.cue_stat(3)
            return False
        if not self.shadow_can():
            return True
        self.deferred = None
        if self.shadow_try(mv, False, sd):
            self.cue_stat(2)
            self.on_duet_cue()
        else:
            self.cue_stat(3)
        return True

    def shadow_try(self, move, before_body=False, side="any"):
        if not self.shadow_can():
            return False
        d = self.dist()
        a = self.act
        self.sside = side
        if move == "nobi":
            if a != 1 or not (NOBI_MIN <= d <= 8.5):
                return False
            T = 1.2 * (TEACH_NOBI if not self.nobi_taught else 1.0)
            imp = self.earliest_shadow(self.t + T, "H")
            self.start_shadow("nobi", "H", imp, ring=imp - min(0.85, imp - self.t), vis=self.t)
            # cuerpo quieto hasta que la tinta vuelve: fin del clip (T + 0.57) + fundido 0.3
            self.shold_body_until = imp + 0.57 + 0.3
            self.sready_at = imp + 0.57 + 0.3
            return True
        if move == "giri":
            if a == 1:
                return False
            nat = GIRI_NAT[a]
            self.slead = EMERGE_LEAD * (TEACH_DARK if a == 3 and not getattr(self, "dark_taught", False) else 1.0)
            if a == 3:
                pre = max(0, self.slead - nat)
            else:
                travel = self.rng.uniform(2.0, 9.5)
                pre = max(0, travel / 9 + 0.25 - nat)
            imp = self.earliest_shadow(self.t + pre + nat, "H")
            vis = imp - max(self.slead, nat) if a == 3 else self.t
            self.start_shadow("giri", "H", imp, ring=imp - 0.85, vis=vis)
            if a == 3:
                self.dark_taught = True
            self.slead = EMERGE_LEAD
            self.sready_at = imp + (1 - 0.5) * 1.2 * 0.95 + (0.5 + 0.3 if a == 3 else 0.5)
            return True
        if move == "nui":
            if a != 2:
                return False
            slide = min(1.0, max(0, self.rng.uniform(2, 9) - 0.5) / 9)
            nat = slide + 0.8
            imp = self.earliest_shadow(self.t + nat, "U")
            self.start_shadow("nui", "U", imp, ring=imp - 1.0, vis=self.t)
            self.sready_at = imp + 0.4
            return True
        if move == "watari":
            if a != 2:
                return False
            lineup = self.rng.uniform(0.5, 1.2)
            nat = lineup + 0.6
            imp = self.earliest_shadow(self.t + nat, "U") + 8 / 24
            self.start_shadow("watari", "U", imp, ring=imp - 1.0, vis=self.t)
            self.sready_at = imp + 0.5
            return True
        return False

    def start_shadow(self, move, kind, imp, ring, vis):
        self.sstate = "strike"; self.smove = move; self.skind = kind; self.simpact = imp
        self.sring = max(self.t, ring); self.svis = vis
        self.last_turn = self.t
        if move == "nobi":
            self.nobi_taught = True

    # -------------------------------------------------------- cuerpo
    def dist(self):
        return max(1.5, self.rng.gauss(self.dist_mean, 1.4))

    def body_free(self):
        return self.bstate in ("chase", "guard") and self.t >= self.kneel_until

    def pick(self):
        d = self.dist()
        cand = [p for p in self.P if p["minr"] <= d <= p["maxr"] and self.t - p["last"] >= p["cd"]
                and not (p["name"] == "Sombra y Acero" and not self.nobi_taught)]
        if not cand:
            return None
        tot = sum(p["w"] for p in cand)
        r = self.rng.random() * tot
        for p in cand:
            r -= p["w"]
            if r <= 0:
                return p
        return cand[-1]

    def begin_body_step(self):
        c, k = self.bsteps[self.bi]
        a = self.act
        if c.startswith("R:"):
            dur = REC[c[2:]] if c != "R:ShadowSink" else self.rng.uniform(1.0, 2.2)
            self.bimpact = -1; self.bkind = None
            self.bstep_end = self.t + dur
            return
        # cues 'before' en PlanWindup
        for (si, mv, before, sd) in self.bpat["cues"]:
            if si == self.bi and before:
                self.run_cue(mv, sd)
        T = step_T(c, k, a)
        imp = self.earliest_body(self.t + T, k)
        self.bimpact = imp; self.bkind = k; self.bring = imp - MAXLEAD[k]
        self.bstep_end = imp + tail(c)
        for (si, mv, before, sd) in self.bpat["cues"]:
            if si == self.bi and not before:
                self.run_cue(mv, sd)

    def resolve(self, actor, kind, move, imp, ring, vis):
        out = self.bot.outcome(kind)
        if out == "hit":
            self.dmg += DMG.get(move if move != "giri" else "giri%d" % self.act, 20)
        self.events.append((imp, actor, kind, move, ring, vis))
        self.outcomes.append((actor, move, kind, out))
        return out

    # -------------------------------------------------------- bucle
    def run(self):
        need = 1.0 if self.act == 1 else 2.0
        while self.t < self.end:
            t = self.t
            # ---- golpes que llegan
            if self.bimpact > 0 and t >= self.bimpact:
                out = self.resolve("cuerpo", self.bkind, self.bsteps[self.bi][0], self.bimpact, self.bring, self.bring)
                self.blast = self.bimpact; self.blastk = self.bkind; self.bimpact = -1
                if out in ("parry", "perfect"):
                    self.posture += 1.5 if out == "perfect" else 1.0
                    self.brecoil_until = t + (0.825 if out == "perfect" else 0.55)
                    self.bstep_end = self.brecoil_until
            if self.simpact > 0 and t >= self.simpact:
                out = self.resolve("sombra", self.skind, self.smove, self.simpact, self.sring, self.svis)
                self.slast = self.simpact; self.slastk = self.skind; self.slastm = self.smove; self.simpact = -1
                self.sstate = "hunt"
                if out in ("parry", "perfect"):
                    self.posture += 1.5 if out == "perfect" else 1.0
                    if self.body_free() and self.posture >= need - 0.01:
                        self.kneel(t)
            if self.posture >= 5 - 0.01 and self.t >= self.kneel_until:
                self.kneel(t)
            # ---- cuerpo
            if self.t < self.kneel_until:
                pass
            elif self.bstate == "attack":
                if t >= self.bstep_end:
                    self.bi += 1
                    if self.bi < len(self.bsteps):
                        self.begin_body_step()
                    else:
                        self.bstate = "guard"; self.bguard_until = t + self.rng.uniform(0.56, 0.96)
                        self.bnext = t + self.rng.uniform(0.7, 1.4)
                        if self.posture >= need - 0.01:
                            self.kneel(t)
                        elif self.rng.random() < TURN_CHANCE[self.act]:
                            self.turn_asked = True
            else:
                if self.bstate == "guard" and t >= self.bguard_until:
                    self.bstate = "chase"
                hold = t < self.shold_body_until
                if self.bstate == "chase" and not hold and t >= self.bnext:
                    p = self.pick()
                    if p:
                        p["last"] = t
                        self.bpat = p; self.bsteps = p["steps"]; self.bi = 0; self.bstate = "attack"
                        self.begin_body_step()
            # ---- director de la sombra
            if self.t >= self.kneel_until and self.run_deferred():
                pass
            elif self.old:
                if (self.act == 2 and self.sstate == "hunt" and self.body_free() and self.bstate != "attack"
                        and t >= self.old_next and t >= self.act_start + 1.6):
                    mv = "nui" if self.rng.random() < 2 / 3 else "watari"
                    if self.shadow_try(mv):
                        self.old_next = self.simpact + self.rng.uniform(2.5, 4.0)
                        self.bnext = max(self.bnext, self.simpact + 0.35)
            elif self.sstate == "hunt" and self.body_free() and self.bstate != "attack" and self.shadow_can():
                if t >= self.act_start + FIRST_TURN[self.act] and t >= self.last_turn + TURN_MIN_GAP[self.act]:
                    quiet = t >= max(self.last_turn, self.act_start) + MAX_QUIET[self.act]
                    if self.turn_asked or quiet or (self.act == 1 and not self.nobi_taught):
                        if self.act == 1:
                            mv = "nobi"
                        elif self.act == 2:
                            r = self.rng.random(); mv = "giri" if r < 0.5 else "nui" if r < 0.8 else "watari"
                        else:
                            mv = "giri"
                        ok = self.shadow_try(mv) or (self.act >= 2 and self.shadow_try("giri"))
                        if ok:
                            self.turn_asked = False
                            self.bnext = max(self.bnext, self.simpact + (0.4 if self.act == 1 else BODY_AFTER))
            self.t += DT
        return self

    def kneel(self, t):
        self.kneel_until = t + 3.0     # 3.6 s menos lo que la cortan los 8 golpes del bot, en promedio
        self.posture = 0.0
        self.bstate = "chase"; self.bimpact = -1; self.bnext = self.kneel_until + 0.3
        if self.deferred is not None:
            self.deferred = None
            self.cue_stat(3)
        # la sombra suelta lo que no llegó al "¡ahora!"
        if self.simpact > 0 and self.simpact - t > GO_LEAD:
            self.simpact = -1; self.sstate = "hunt"


def analyse(act, runs=200, seconds=70, level="bueno", old=False):
    gaps_diff, gaps_any, ring_over, vis_lead, emerge_clear = [], [], 0, [], []
    counts = {"cuerpo": 0, "sombra": 0}
    moves = {}
    total_time = 0.0
    outs = {}
    for s in range(runs):
        sim = Sim(act, 1000 * act + s, seconds, level=level, old=old).run()
        dmg_total = getattr(analyse, "_d", 0.0) + sim.dmg
        analyse._d = dmg_total
        total_time += seconds
        ev = sorted(sim.events)
        body_imps = [e[0] for e in ev if e[1] == "cuerpo"]
        for e in ev:
            counts[e[1]] += 1
            moves[e[3]] = moves.get(e[3], 0) + 1
            if e[1] == "sombra" and act == 3:
                vis_lead.append(e[0] - e[5])
                if body_imps:
                    emerge_clear.append(min(abs(b - e[5]) for b in body_imps))
        for a, b in zip(ev, ev[1:]):
            gaps_any.append(b[0] - a[0])
            if a[1] != b[1]:
                gaps_diff.append(b[0] - a[0])
                # el anillo del segundo arranca antes del golpe del primero
                if b[4] < a[0] - 1e-6:
                    ring_over += 1
        for (actor, mv, k, o) in sim.outcomes:
            key = (actor, mv)
            d = outs.setdefault(key, {"n": 0, "ok": 0})
            d["n"] += 1
            d["ok"] += 1 if o in ("parry", "perfect", "dodge") else 0
    mins = total_time / 60
    d = getattr(analyse, "_d", 0.0); analyse._d = 0.0
    res = {
        "act": act, "modo": "antes" if old else "ahora", "bot": level,
        "dano_recibido_por_min": round(d / mins, 1),
        "golpes_por_min_cuerpo": round(counts["cuerpo"] / mins, 1),
        "golpes_por_min_sombra": round(counts["sombra"] / mins, 1),
        "parte_de_la_sombra_%": round(100 * counts["sombra"] / max(1, counts["cuerpo"] + counts["sombra"]), 1),
        "sombra_por_golpe": {k: v for k, v in sorted(moves.items()) if k in ("nobi", "giri", "nui", "watari")},
        "gap_min_entre_atacantes_s": round(min(gaps_diff), 3) if gaps_diff else None,
        "gap_p5_entre_atacantes_s": round(sorted(gaps_diff)[len(gaps_diff) // 20], 3) if gaps_diff else None,
        "gap_min_cualquiera_s": round(min(gaps_any), 3),
        "anillos_superpuestos": ring_over,
        "pares_entre_atacantes": len(gaps_diff),
        "sombra_visible_antes_del_golpe_min_s": round(min(vis_lead), 3) if vis_lead else None,
        "salida_a_un_golpe_de_el_min_s": round(min(emerge_clear), 3) if emerge_clear else None,
        "salidas_a_menos_de_0.24_s_de_un_golpe_de_el_%": round(100 * sum(1 for x in emerge_clear if x < 0.24) / len(emerge_clear), 1) if emerge_clear else None,
        "exito_bot_bueno": {f"{a}:{m}": round(d["ok"] / d["n"], 3) for (a, m), d in sorted(outs.items()) if d["n"] > 20},
    }
    return res


if __name__ == "__main__":
    out = [analyse(a) for a in (1, 2, 3)]
    for r in out:
        print(json.dumps(r, ensure_ascii=False, indent=1))
    print("--- comparación de presión (golpes/min y daño recibido/min) ---")
    for lv in ("bueno", "promedio"):
        for a in (1, 2, 3):
            for old in (True, False):
                r = analyse(a, runs=120, level=lv, old=old)
                out.append(r)
                print(lv, "acto", a, r["modo"], "cuerpo", r["golpes_por_min_cuerpo"], "sombra", r["golpes_por_min_sombra"],
                      "daño/min", r["dano_recibido_por_min"])
    json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "duet_sim.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
