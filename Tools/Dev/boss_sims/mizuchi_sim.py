"""Pelea ENTERA contra Mizuchi a 60 Hz, con la lógica de MizuchiBoss / EnemyArchetypes.Mizuchi / Enemy / StepTimeline:
  * elección de patrón (pesos, rangos, cooldowns, fase mínima/máxima, el coletazo solo con Kaito detrás);
  * cada paso: T = max(natural, MinWindup) (Light 0.55/0.42, Heavy 0.65/0.50, rojo 0.80; x0.9 desde la fase 1;
    + telegraph); el resto del clip a su velocidad; la velocidad de los pasos sube con cada fase (ScaleSteps);
  * los especiales con sus propios relojes (zambullida, ola, pilares, chorro, barrido, perlas, tormenta, peloteo);
  * postura 4 (parry 1, perfecto 1.5, perla devuelta 1) -> varado (3.4 s; 2.8 corrompido), hasta 4 golpes x1.3;
    varado 1.6 s después de la zambullida y de los pilares (sin gastar la postura);
  * fin de combo -> guardia (guardTime 1.2 x U(0.7,1.2)), cooldown U(attackCooldown) que baja x0.75 por fase;
  * fases por vida (umbrales), corrupción de 5.5 s (no se le pega, Kaito guionado) y rugido de 1.1 s en la 3;
  * el remate: con <= 12 % de vida y 30 de Espíritu, el bot lo ejecuta (gana);
  * Kaito y el bot: kaito.py (el mismo de fight_kokuyo). Distancia: el bot vuelve a 2.2 m a 6.2 m/s; el koi ronda a 4.5.
Uso: python mizuchi_sim.py [nivel] [corridas] [clave=valor ...]  (hp, th="[0.55,0.33]", ...)
"""
import os, sys, json, random, statistics, copy, math
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from kaito import Kaito, DT, SKILL

RESPAWN = 25.0      # "Caíste" + santuario + volver a la plataforma + la presentación corta (Roar)
LAT = 0.0

# clip: (largo s, apex, activeStart, activeEnd)
CLIP = {"Bite": (1.1, 0.4545, 0.5758, 0.697), "FinL": (0.9, 0.4074, 0.5556, 0.6667), "FinR": (0.8, 0.25, 0.4167, 0.5417),
        "TailWhip": (1.4, 0.4524, 0.5476, 0.7143), "Spit": (1.2, 0.4444, 0.5556, 0.5833), "Jet": (2.2, 0.4848, 0.5455, 0.7576)}


def step(name, clip, dmg, kind, tel=0.0, special="", kb=1.0, noRecoil=False, param=0):
    return dict(name=name, clip=clip, dmg=dmg, kind=kind, tel=tel, special=special, kb=kb, noRecoil=noRecoil, param=param)


def base_cfg():
    return {
        "hp": 720.0, "th": [0.55, 0.33], "cool": [0.8, 1.6], "guard": 1.2, "exh": 3.4, "exh2": 2.8, "poise": 3,
        "finisher": 0.12, "speed": [1.0, 1.12, 1.12 * 1.08], "dmg": [1.0, 1.1, 1.1],
        "corruption": 5.5, "roar": 1.4,
        # patrones: nombre -> (pasos, peso, minR, maxR, cooldown, minFase, maxFase, behind)
        "patterns": None,
        "rally_returns": [[2, 4], [2, 4], [3, 5]],
        "dive_cd_p3": None, "beach_dive": 1.6,
    }


def patterns(cfg):
    if cfg.get("patterns"):
        return copy.deepcopy(cfg["patterns"])
    bite = step("Bite", "Bite", 16, "L", 0.22, kb=1.0)
    finL = step("FinL", "FinL", 14, "L", 0.15, kb=0.6)
    finR = step("FinR", "FinR", 14, "L", 0.0, kb=0.6)
    tail = step("TailWhip", "TailWhip", 22, "HV", 0.28, kb=2.4)
    pearls = step("Perlas", "Spit", 10, "L", 0.25, "pearls", 0.8, param=3)
    dive = step("Dive", None, 30, "U", 0, "dive", 3.2)
    jet = step("Jet", "Jet", 26, "U", 0.3, "jet", 2.6)
    tB, tFL, tFR, tT = [dict(s, noRecoil=True) for s in (bite, finL, finR, dict(tail, tel=0.45))]
    rally = step("Tama-asobi", "Spit", 18, "L", 0.25, "rally", 2.0)
    sweep = dict(jet, name="Chorro barrido", special="jetsweep", tel=0.7)
    wave = step("GreatWave", None, 24, "U", 0, "greatwave", 3.0)
    pillars = step("Roar", None, 20, "U", 0, "pillars", 2.5, param=4)
    storm = dict(pearls, name="Perlas de tormenta", special="storm", param=5, dmg=8)
    P = []

    def add(name, steps, w, minR=0, maxR=99, cd=0, minP=0, maxP=9, behind=False):
        P.append(dict(name=name, steps=steps, w=w, minR=minR, maxR=maxR, cd=cd, minP=minP, maxP=maxP, behind=behind, last=-99))
    add("Mordida", [bite], 1.6, maxR=3.6)
    add("Aletazo", [finL, finR], 1.5, maxR=3.4)
    add("Mordida y aletazo", [bite, finL, finR], 1.1, maxR=3.6, maxP=0)
    add("Coletazo", [tail], 2.5, maxR=4.8, cd=4, behind=True)
    add("Perlas del Lago", [pearls], 1.2, 6, 14, 5, maxP=0)
    add("Salto del Dragón", [dive], 1.0, 2, 30, 12)
    add("Chorro", [jet], 0.9, 4, 11, 9, maxP=0)
    add("Torrente", [tB, tFL, tFR, tT], 1.6, maxR=3.6, minP=1)
    add("Tama-asobi", [rally], 1.0, 6, 14, 14, minP=1)
    add("Chorro barrido", [sweep], 1.0, 4, 9, 8, minP=1)
    add("Ola de la Cascada", [wave], 0.9, 2, 30, 15, minP=1)
    add("Pilares", [pillars], 0.8, 2, 30, 20, minP=1)
    add("Perlas de tormenta", [storm], 1.0, 6, 14, 6, minP=2)
    if cfg.get("new"):
        add("Aletas y mordida", [finL, finR, bite], 1.0, maxR=3.4)
        add("Torrente largo", [tB, tFL, tFR, tB, tT], 1.2, maxR=3.6, minP=2)
    if cfg.get("retreat"):
        rt = step("Retirada", None, 0, "N", 0, "retreat")
        R = cfg["retreat"]
        add("Perlas desde lejos", [rt, pearls], R[0], maxR=4.0, cd=11, maxP=0)
        add("Chorro desde lejos", [rt, jet], R[1], maxR=4.0, cd=13, maxP=0)
        add("Peloteo desde lejos", [rt, rally], R[2], maxR=4.0, cd=16, minP=1)
        add("Barrido desde lejos", [rt, sweep], R[3], maxR=4.0, cd=12, minP=1)
        add("Tormenta desde lejos", [rt, storm], R[4], maxR=4.0, cd=10, minP=2)
    return P


def min_windup(s, chained, phase):
    k = s["kind"]
    if k == "U":
        b = 0.80
    elif k == "HV":
        b = 0.50 if chained else 0.65
    else:
        b = 0.42 if chained else 0.55
    if phase >= 1:
        b *= 0.9
    b = max(b, 0.70 if k == "U" else 0.38)
    return b + max(0.0, s["tel"])


def timeline(s, chained, phase, speed):
    L, ap, a0, a1 = CLIP[s["clip"]]
    L /= speed
    nat = ap * L / 0.85 + (a0 - ap) * L / 1.6
    T = max(nat, min_windup(s, chained, phase))
    rest = (1 - a0) * L
    return T, rest


class Fight:
    def __init__(self, seed, level, cfg):
        self.rng = random.Random(seed)
        self.cfg = cfg
        self.k = Kaito(self.rng, level)
        self.lv = level
        self.maxhp = cfg["hp"]
        self.hp = self.maxhp
        self.phase = 0
        self.P = patterns(cfg)
        for p in self.P:
            if p["minP"] == 0 and p["cd"] >= 8:
                p["last"] = -p["cd"] * 0.5       # StaggerCooldowns(0, 0.5) al empezar
        self.t = 0.0
        self.d = 4.5
        self.state = "chase"; self.until = 0.6; self.next_attack = 0.6
        self.posture = 0.0
        self.exh_hits = 0; self.free_beach = False; self.saved_posture = 0.0
        self.neutral_hits = 0; self.last_neutral = -9
        self.guard_hits = 0
        self.ring = None          # (desde, impacto) del aviso dibujado alrededor del koi
        self.events = []          # golpes por resolver: (t, kind, dmg, kb, tag)
        self.untouchable_until = -1
        self.scripted_until = -1
        self.won = False
        self.phase_time = [0.0, 0.0, 0.0]
        self.cool = list(cfg["cool"])
        self.counts = {}
        self.pending_phase = 0
        self.dmg_log = {"normal": 0.0, "exhausted": 0.0}

    # ------------------------------------------------------------ utilidades
    def speed(self):
        return self.cfg["speed"][self.phase]

    def dmg(self, s):
        return s["dmg"] * self.cfg["dmg"][self.phase]

    def pick(self):
        cand, tot = [], 0.0
        for p in self.P:
            if self.d < p["minR"] or self.d > p["maxR"] or self.phase < p["minP"] or self.phase > p["maxP"]:
                continue
            if self.t - p["last"] < p["cd"]:
                continue
            if p["behind"] and self.rng.random() > 0.12:
                continue
            cand.append(p); tot += p["w"]
        if not cand:
            return None
        r = self.rng.random() * tot
        for p in cand:
            r -= p["w"]
            if r <= 0:
                return p
        return cand[-1]

    def add_posture(self, v):
        if self.state == "exhausted":
            return
        self.posture = min(4.0, self.posture + v)
        if self.posture >= 3.99:
            self.exhaust(self.cfg["exh"] if self.phase == 0 else self.cfg["exh2"])

    def exhaust(self, secs, free=False):
        if free:
            self.saved_posture = self.posture
        self.free_beach = free
        self.state = "exhausted"; self.until = self.t + secs; self.exh_hits = 0
        self.events = [e for e in self.events if e[4] == "kaito"]
        self.ring = None
        self.seq = None
        self.next_attack = self.t + secs + self.rng.uniform(*self.cool)

    def end_exhaust(self):
        self.posture = self.saved_posture if self.free_beach else 0.0
        self.free_beach = False
        self.guard()
        if self.pending_phase > self.phase:
            self.phase_change(self.pending_phase)
        self.pending_phase = 0

    def guard(self):
        self.state = "guard"; self.guard_hits = 0
        self.until = self.t + self.cfg["guard"] * self.rng.uniform(0.7, 1.2)

    def phase_change(self, n):
        n = min(n, self.phase + 1)
        self.phase = n
        self.k.heal(self.cfg.get("heal", [0, 0, 0])[n])
        self.k.spirit = min(100, self.k.spirit + self.cfg.get("heal_spirit", [0, 0, 0])[n])
        for p in self.P:
            cd = self.cfg.get("cds", {}).get(p["name"])
            if cd:
                p["cd"] = cd[n]
        self.cool = [c * 0.75 for c in self.cool]
        self.events = [e for e in self.events if e[4] == "kaito"]
        self.ring = None; self.seq = None
        if n == 1:
            self.posture = 0.0
            dur = self.cfg["corruption"]
            self.state = "cine"; self.until = self.t + dur
            self.scripted_until = self.t + dur
            self.d = 4.5
            self.k.pending_hits.clear()
            for p in self.P:
                if p["minP"] == 1 and p["cd"] >= 8:
                    p["last"] = self.t + dur - p["cd"] * 0.4
            if self.cfg.get("fix"):
                self.signatures([("Ola de la Cascada", self.t + dur + 2.5), ("Pilares", self.t + dur + 10.0)])
        else:
            self.state = "cine"; self.until = self.t + self.cfg["roar"]
            for p in self.P:
                if p["name"] == "Pilares":
                    p["cd"] = 12
                if p["minP"] == 2 and p["cd"] >= 8:
                    p["last"] = self.t - p["cd"] * 0.4
            if self.cfg.get("p3_cd"):
                for p in self.P:
                    if p["name"] in self.cfg["p3_cd"]:
                        p["cd"] = self.cfg["p3_cd"][p["name"]]
            if self.cfg.get("fix"):
                self.signatures([("Tormenta desde lejos", self.t + self.cfg["roar"] + 2.5)])
        if self.cfg.get("fix"):
            for p in self.P:
                if p["name"] == "Mordida":
                    p["w"] = 1.2
                elif p["name"] == "Aletazo":
                    p["w"] = 1.1

    def signatures(self, items):
        for p in self.P:
            if "w0" in p:
                p["w"] = p.pop("w0")
        for name, ready in items:
            for p in self.P:
                if p["name"] == name:
                    p["last"] = ready - p["cd"]
                    p["w0"] = p["w"]
                    p["w"] *= 50

    # ------------------------------------------------------------ ataque del koi: secuencias como listas de eventos
    def start_pattern(self, p):
        p["last"] = self.t
        if "w0" in p:
            p["w"] = p.pop("w0")
        self.counts[p["name"]] = self.counts.get(p["name"], 0) + 1
        self.pat = p; self.si = 0
        self.state = "attack"
        self.begin_step()

    def begin_step(self):
        s = self.pat["steps"][self.si]
        self.cur = s
        chained = self.si > 0
        sp = s["special"]
        t = self.t
        if self.cfg.get("fix"):
            if sp == "retreat":
                for q in self.P:
                    if q is not self.pat and q["minR"] >= 4:
                        q["last"] = max(q["last"], t - q["cd"] + 3.0)
            elif sp in ("pearls", "jet", "rally", "jetsweep", "storm"):
                for q in self.P:
                    if q is not self.pat and any(st is s for st in q["steps"]):
                        q["last"] = t
        self.step_hit_done = False
        self.ring = None
        if sp == "dive":
            # Leap 0.27 + arco ~0.65 + nado ~1.0 + hervor 0.35 + vuelo 1.1 (disco rojo desde que despega)
            hide = 0.27
            swim = self.rng.uniform(0.6, 1.4) * (self.cfg.get("swim_mul", [1, 1, 1])[self.phase])
            imp = t + 0.27 + 0.65 + swim + 0.35 + 1.1
            self.untouchable_until = imp
            self.untouch_from = t + hide
            self.events.append((imp, "U", self.dmg(s), s["kb"], "koi"))
            self.ring = (imp - 1.1, imp)
            self.step_end = imp
            self.after = ("beach", self.cfg["beach_dive"])
            return
        if sp == "retreat":
            # se enrosca 0.27 s (se le puede pegar), salta 0.8 s lejos de Kaito (rebota) y gira 0.45 s hacia él
            self.untouch_from = t + 0.27
            self.untouchable_until = t + 0.27 + 0.8
            self.step_end = t + 0.27 + 0.8 + 0.45
            self.after = ("land", self.rng.uniform(7.5, 9.0))
            self.ring = None
            return
        if sp == "greatwave":
            launch = t + 0.27 + 0.7 + 0.2 + 17 / 30 + 1.2
            ws = self.cfg.get("wave_speed", [8, 8, 8])[self.phase]
            imp = launch + (11.0 - self.rng.uniform(-3, 5)) / ws
            self.untouch_from = t + 0.27
            self.untouchable_until = launch + 20 / ws + 0.5 + 1.0
            self.events.append((imp, "U", self.dmg(s), s["kb"], "koi"))
            self.ring = (launch - 1.2, imp)
            self.step_end = self.untouchable_until
            self.after = ("land", 3.5)
            return
        if sp == "pillars":
            t0 = t + 0.35
            pg = self.cfg.get("pillar_gap", [0.45, 0.45, 0.45])[self.phase]
            for i in range(4):
                self.events.append((t0 + i * pg + 1.1, "U", self.dmg(s), s["kb"], "koi"))
            last = t0 + 3 * pg + 1.1
            imp = last + 0.2 + 0.27 + 1.1
            self.events.append((imp, "U", self.dmg(s) * 1.5, 3.2, "koi"))
            self.untouch_from = last + 0.2 + 0.27
            self.untouchable_until = imp
            self.ring = (t0 + 1.1 - 1.1, imp)     # los discos no son InTell (no frenan el ataque del bot) -> ver abajo
            self.ring_blocks = False
            self.step_end = imp
            self.after = ("beach", 1.6)
            return
        T, rest = timeline(s, chained, self.phase, self.speed())
        imp = t + T
        self.ring_blocks = True
        if sp in ("pearls", "storm", "rally"):
            fly = max(0.0, self.d - 1.0) / (10.0 if sp != "pearls" else 9.0)
            if sp == "pearls":
                self.events.append((imp + fly, "H", self.dmg(s), s["kb"], "pearl"))
            elif sp == "storm":
                for i in range(int(s["param"])):
                    self.events.append((imp + i * 0.15 + fly, "H", self.dmg(s), s["kb"], "pearl"))
            else:
                lo, hi = self.cfg["rally_returns"][self.phase]
                self.rally_left = self.rng.randint(lo, hi)
                self.events.append((imp + fly, "H", self.dmg(s), s["kb"], "rally"))
                self.rally_fly = fly
            self.ring = None          # avisan a los pies de Kaito (el bot no ataca: está lejos)
            self.step_end = imp + rest if sp != "rally" else 9e9
            self.after = None
            return
        self.events.append((imp, "U" if s["kind"] == "U" else "H", self.dmg(s), s["kb"], "koi"))
        lead = 1.0 if s["kind"] == "U" else 0.85
        if sp == "jetsweep":
            lead = 1.0
        self.ring = (imp - lead, imp)
        self.step_end = imp + rest
        self.after = None

    def threatened(self, t):
        if self.ring and self.ring[0] <= t < self.ring[1] and getattr(self, "ring_blocks", True):
            return True
        return False

    def hittable(self, t):
        if self.state in ("cine",):
            return False
        if self.state == "attack" and getattr(self, "untouch_from", 9e9) <= t < self.untouchable_until:
            return False
        if self.state == "guard":
            return False
        return True

    def step_done(self):
        if self.after:
            kind, v = self.after
            self.after = None
            if kind == "beach":
                self.d = self.rng.uniform(1.6, 3.2)
                self.exhaust(v, free=True)
                return
            if kind == "land":
                self.d = v
        self.si += 1
        if self.si < len(self.pat["steps"]):
            self.begin_step()
            return
        self.combo_end()

    def combo_end(self):
        self.ring = None
        self.next_attack = self.t + self.rng.uniform(*self.cool)
        if self.posture >= 3.99:
            self.exhaust(self.cfg["exh"] if self.phase == 0 else self.cfg["exh2"])
        else:
            self.guard()

    # ------------------------------------------------------------ golpes que llegan a Kaito
    def resolve(self, ev):
        t, kind, dmg, kb, tag = ev
        k = self.k
        if t < self.scripted_until:
            return
        out, taken = k.defend(t, "U" if kind == "U" else "H", dmg)
        if out in ("parry", "perfect"):
            perfect = out == "perfect"
            if tag == "rally":
                self.rally_left -= 1 + (1 if perfect else 0)
                if self.rally_left <= 0:
                    # se le escapa: postura llena, 30 de daño y varado
                    nxt = t + self.rally_fly + 0.4
                    self.events.append((nxt, "MISS", 0, 0, "rallymiss"))
                else:
                    self.events.append((t + 2 * self.rally_fly + 0.17, "H", dmg, kb, "rally"))
                return
            if tag == "pearl":
                if perfect:
                    self.add_posture(1.0)
                    self.deal(t + 0.5, 8.0, ability=True)
                return
            self.add_posture(1.5 if perfect else 1.0)
            self.d += 0.4 + (0.8 if perfect else 0.4)
            if self.state == "attack" and not self.cur["noRecoil"]:
                rec = 0.4 * (1.5 if perfect else 1.0)
                # Recoil -> el paso siguiente arranca al terminar el retroceso
                self.step_end = t + rec
            return
        if out == "graze":
            self.add_posture(0.34)
        if tag == "rally":
            self.state_after_rally()
        if out == "hit":
            self.d += kb + (1.2 if kind == "U" or dmg >= 20 else 0.5)

    def state_after_rally(self):
        if self.state == "attack" and self.cur["special"] == "rally":
            self.step_end = self.t + 0.3

    def deal(self, t, d, ability=False):
        if self.state == "cine":
            return
        mul = 1.3 if self.state == "exhausted" else 1.0
        self.hp -= d * mul
        self.k.on_dealt(t, d * mul)
        self.check_phase()

    def check_phase(self):
        n = 0
        for i, th in enumerate(self.cfg["th"]):
            if self.hp / self.maxhp <= th:
                n = i + 1
        if n > self.phase:
            if self.state == "exhausted":
                self.pending_phase = n
            else:
                self.phase_change(n)

    # ------------------------------------------------------------ Kaito pega
    def kaito_tick(self, t):
        k = self.k
        # moverse: vuelve a 2.2 m si está libre (el koi ronda a 4.5 a 2.4 m/s: el bot lo alcanza)
        if t >= k.busy_until and self.d > 2.2 and self.state != "cine":
            self.d = max(2.2, self.d - (6.2 - (2.4 if self.state in ("chase",) else 0.0)) * DT)
        allowed = self.d < 2.6 and self.hittable(t)
        greedy = self.rng.random() < k.sk["greedy"] * DT * 4
        k.try_attack(t, allowed and (not self.threatened(t) or greedy))
        for (ht, base) in k.due_hits(t):
            if not self.hittable(ht) or self.d > 2.9:
                if self.state == "guard":
                    self.guard_hit(ht)
                continue
            if self.state in ("chase",):
                if ht - self.last_neutral > 2.2:
                    self.neutral_hits = 0
                self.last_neutral = ht
                self.neutral_hits += 1
                if self.neutral_hits > self.cfg["poise"]:
                    self.neutral_hits = 0
                    self.guard()
                    self.guard_hit(ht)
                    continue
            d = base * k.damage_mul(ht)
            mul = 1.3 if self.state == "exhausted" else 1.0
            self.hp -= d * mul
            self.dmg_log["exhausted" if self.state == "exhausted" else "normal"] += d * mul
            k.on_dealt(ht, d * mul)
            k.on_connect(0.11 if base >= 18 else 0.06)
            if self.state == "exhausted":
                self.exh_hits += 1
                self.until = max(self.until, ht + 0.6)
                if self.exh_hits >= 4:
                    self.end_exhaust()
            self.check_phase()
            if self.hp <= 0:
                self.won = True
                return

    def guard_hit(self, t):
        self.guard_hits += 1
        if self.guard_hits >= 2:
            # contraataque: un golpe corto (mordida) que sale enseguida
            self.pat = dict(name="Contra", steps=[dict(step("Bite", "Bite", 16, "L", 0.22), name="Contra")], last=t)
            self.si = 0; self.state = "attack"
            self.begin_step()
            return
        self.until = max(self.until, t + 0.5)
        self.add_posture(0.25)

    # ------------------------------------------------------------ bucle
    def run(self, limit=1500.0):
        cfg = self.cfg
        while self.t < limit:
            t = self.t
            k = self.k
            if k.hp <= 0 or self.won:
                return self
            self.phase_time[self.phase] += DT
            # remate
            if self.hp / self.maxhp <= cfg["finisher"] and k.spirit >= 30 and self.state != "cine" and self.d < 3.5 \
                    and not (self.state == "attack" and getattr(self, "untouch_from", 9e9) <= t < self.untouchable_until) \
                    and t >= k.busy_until:
                self.won = True
                return self
            # golpes que llegan
            due = [e for e in self.events if e[0] <= t]
            if due:
                self.events = [e for e in self.events if e[0] > t]
                for ev in due:
                    if ev[1] == "MISS":
                        self.posture = 0
                        self.deal(t, 30.0, ability=True)
                        self.exhaust(cfg["exh"] if self.phase == 0 else cfg["exh2"])
                        continue
                    self.resolve(ev)
            # koi
            st = self.state
            if st == "cine":
                if t >= self.until:
                    self.state = "chase"; self.next_attack = t + 0.8
            elif st == "exhausted":
                if t >= self.until:
                    self.end_exhaust()
            elif st == "guard":
                if t >= self.until:
                    self.state = "chase"
            elif st == "attack":
                if t >= self.step_end and not [e for e in self.events if e[4] in ("koi", "rally", "rallymiss")]:
                    self.step_done()
            if self.state == "chase" and t >= self.next_attack:
                p = self.pick()
                if p:
                    self.start_pattern(p)
            self.kaito_tick(t)
            self.t += DT
        return self


def resume_at(f, n):
    """El reintento arranca en la fase n (MizuchiBoss.retryPhase, como Chikuō): las esperas, la cadencia y las firmas
    de cada fase saltada, sin la transición ni la cura (Kaito reapareció entero), y la vida en el umbral de esa fase."""
    hp0, sp0 = f.k.hp, f.k.spirit
    for i in range(1, n + 1):
        f.phase_change(i)
    f.k.hp, f.k.spirit = hp0, sp0
    f.state = "chase"; f.until = 0.6; f.next_attack = 0.6; f.scripted_until = -1
    f.hp = f.maxhp * f.cfg["th"][n - 1]
    return f


def attempt_series(seed, level, cfg, max_deaths=12):
    total, deaths, start = 0.0, 0, 0
    while True:
        f = Fight(seed * 31 + deaths, level, cfg)
        if start > 0:
            resume_at(f, start)
        f.run()
        total += f.t
        if f.won:
            return total, deaths, f
        deaths += 1
        total += RESPAWN
        # cfg 'retry': el reintento retoma la fase más alta a la que llegó (sin: vuelve a la 1, como antes)
        if cfg.get("retry"):
            start = max(start, f.phase)
        if deaths >= max_deaths:
            return total, deaths, f


def report(level, runs, cfg, label=""):
    T, Dn, ph, fw = [], [], [[], [], []], 0
    counts = {}
    reached = [0, 0, 0]
    for s in range(runs):
        tot, deaths, f = attempt_series(s + 1, level, cfg)
        T.append(tot); Dn.append(deaths)
        if deaths == 0:
            fw += 1
            for i in range(3):
                ph[i].append(f.phase_time[i])
            for kname, v in f.counts.items():
                counts[kname] = counts.get(kname, 0) + v
    T.sort()
    return {"bot": level, "cfg": label, "min_mediana": round(statistics.median(T) / 60, 2),
            "p10_p90": [round(T[len(T) // 10] / 60, 2), round(T[9 * len(T) // 10] / 60, 2)],
            "muertes": round(statistics.mean(Dn), 2), "gana_1ra_%": round(100 * fw / runs, 1),
            "seg_fase_1ra": [round(statistics.median(v), 1) if v else None for v in ph]}


if __name__ == "__main__":
    lv = sys.argv[1] if len(sys.argv) > 1 else "bueno"
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    cfg = base_cfg()
    for kv in sys.argv[3:]:
        kk, v = kv.split("=", 1)
        cfg[kk] = json.loads(v)
    for l in lv.split(","):
        print(json.dumps(report(l, runs, cfg, " ".join(sys.argv[3:])), ensure_ascii=False))
