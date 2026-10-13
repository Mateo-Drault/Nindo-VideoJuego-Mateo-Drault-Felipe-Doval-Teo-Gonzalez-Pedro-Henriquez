"""Kaito y el bot de AutoPilot para las simulaciones de pelea entera (a 60 Hz).

Bot (AutoPilot.cs): reacciona al hyōshigi (que se OYE a TickLead del golpe: 0.38 desviable, 0.42 imparable) con
N(rtMean, rtSd) recortado a [0.15, 0.55] + 1 cuadro. La latencia de salida se cancela: el evento sale con el Play()
LAT antes de oírse y el bot suma LAT. (El duet_sim de la etapa 1 la sumaba de más: 0.02 s más tarde.)
  experto  0.25±0.04, nunca falla             bueno  0.28±0.06, no ve 10 %, se confunde 5 %, apurado 10 %
  promedio 0.32±0.08, no ve 15 %, se confunde 7 %, apurado 15 %
Parry (PlayerConfig): ventana 0.24 s, perfecta los primeros 0.11; temprano por poco = guardia imperfecta (35 % del
daño, 0.15 s después de cerrada); tarde = golpe entero. Dash: i-frames 0.02-0.24 del apretón, cuesta 15 de Espíritu;
sin Espíritu es un paso sin i-frames (golpe).
Ataque del bot: aprieta cada 0.32 s si está a menos de 2.6 m, nadie amenaza (anillo a la vista) y no está en guardia.
Combo: Corte 1 (10, pega a 0.133 s), Corte 2 (11, +0.10 s del apretón), Corte final (18, +0.246 s); el reinicio sale a
0.85 del último. Contraataque: el primer golpe que conecta dentro de 0.7 s del parry hace x1.5. Furia al 100: 9 s, x1.45.
"""
import random

DT = 1 / 60.0
SKILL = {
    "experto": dict(mean=0.25, sd=0.04, miss=0.0, wrong=0.0, greedy=0.0),
    "bueno": dict(mean=0.28, sd=0.06, miss=0.10, wrong=0.05, greedy=0.10),
    # el de Input/AutoPilot.cs (Skill.Average), recalibrado: con miss 0.25 / wrong 0.10 / greedy 0.25 perdía contra todos
    # los jefes un orden de magnitud más que el bueno (Tools/Dev/goro_fight_sim.py, sim_bamboo_master.py usan los mismos)
    "promedio": dict(mean=0.32, sd=0.08, miss=0.15, wrong=0.07, greedy=0.15),
    # una persona que juega bien: ve el aviso (no solo lo oye), con más errores si viene de atrás o de la oscuridad
    "humano": dict(mean=0.30, sd=0.07, miss=0.08, wrong=0.07, greedy=0.15, visual=True),
}
TICK = {"H": 0.38, "L": 0.38, "P": 0.38, "U": 0.42}
# combo: (daño, retraso del golpe desde el apretón, duración del corte, fin del tramo cortante)
COMBO = [(10, 0.133, 0.433, 0.233), (11, 0.100, 0.367, 0.200), (18, 0.246, 0.702, 0.351)]
TAP = 0.32


class Kaito:
    def __init__(self, rng, skill, hp=100.0, spirit=40.0):
        self.rng = rng
        self.sk = SKILL[skill]
        self.hp, self.max_hp = hp, 100.0
        self.spirit, self.rage = spirit, 0.0
        self.rage_until = -1.0
        self.busy_until = 0.0          # golpeado / dash / parry
        self.invuln_until = -1.0
        self.next_tap = 0.0
        self.combo_i = 0
        self.chain_until = -1.0        # mientras corta, el combo sigue
        self.pending_hits = []         # (t, daño base)
        self.cut_until = -1.0
        self.riposte_until = -1.0
        self.dist_ok_at = 0.0          # cuándo vuelve a estar a menos de 2.6 m
        self.dealt = 0.0
        self.taken = 0.0
        self.stats = {"perfect": 0, "parry": 0, "dodge": 0, "hit": 0, "graze": 0}

    # ---------------------------------------------------------------- defensa
    def defend(self, t, kind, dmg, notice_from=None, hard=False):
        """Resuelve un golpe que pega en 't' (el bot oyó el aviso). Devuelve (resultado, daño recibido).
        Perfil visual: nota el aviso 0.35-0.5 s después de que se ve ('notice_from'), +0.15 s si viene de atrás o de la
        oscuridad ('hard'); si lo notó con 0.3 s o más de margen aprieta con el cierre del anillo (0.10 s antes, error
        N(0, 0.06)), si no reacciona tarde (lo que pase último entre el toc y lo que notó)."""
        sk, r = self.sk, self.rng
        if t < self.invuln_until:
            return "dodge", 0.0
        miss = sk["miss"] + (0.10 if hard and sk.get("visual") else 0.0)
        if r.random() < miss:
            return self._hit(t, dmg)
        rt = min(0.55, max(0.15, r.gauss(sk["mean"], sk["sd"]))) + 1 / 60
        press = -TICK[kind] + rt
        if sk.get("visual") and notice_from is not None:
            notice = (notice_from - t) + r.uniform(0.35, 0.5) + (0.15 if hard else 0.0)
            close = -(0.10 if kind != "U" else 0.16)
            press = close + r.gauss(0.0, 0.06) if notice <= -0.30 else max(press, notice + 0.12)
        # si justo está cortando, el apretón sale cuando termina el tramo cortante (buffer de defensa)
        if self.cut_until > t + press:
            press = self.cut_until - t
        dash = (kind == "U") != (r.random() < sk["wrong"])
        if dash:
            if self.spirit < 15:
                return self._hit(t, dmg)
            self.spirit -= 15
            self.busy_until = max(self.busy_until, t + press + 0.34)
            self.dist_ok_at = max(self.dist_ok_at, t + press + 0.34 + r.uniform(0.0, 0.8))
            if press + 0.02 <= 0 <= press + 0.24:
                self.stats["dodge"] += 1
                return "dodge", 0.0
            return self._hit(t, dmg)
        if kind == "U":
            return self._hit(t, dmg)
        if -0.24 <= press <= 0:
            perfect = press >= -0.11
            self.stats["perfect" if perfect else "parry"] += 1
            self.spirit = min(100, self.spirit + (18 if perfect else 12))
            self._rage(t, 20 if perfect else 14)
            self.riposte_until = t + 0.7
            self.busy_until = max(self.busy_until, t + 0.06)
            # empujones: él 0.4-0.8 + 0.6, Kaito 0.25-0.55: un paso para volver a estar a tiro
            self.dist_ok_at = max(self.dist_ok_at, t + 0.12)
            return ("perfect" if perfect else "parry"), 0.0
        if press < -0.24 and press + 0.24 >= -0.15:
            self.stats["graze"] += 1
            return self._hit(t, dmg * 0.35, graze=True)
        return self._hit(t, dmg)

    def _hit(self, t, dmg, graze=False):
        if not graze:
            self.stats["hit"] += 1
        self.hp -= dmg
        self.taken += dmg
        if t >= self.rage_until:
            self.rage = max(0.0, self.rage - 40 * (0.35 if graze else 1.0))
        hurt = 0.38 if dmg < 25 else 0.65
        if not graze:
            self.busy_until = max(self.busy_until, t + hurt)
            self.invuln_until = t + 0.7
            self.pending_hits.clear()
            self.chain_until = -1
            self.combo_i = 0
            self.dist_ok_at = max(self.dist_ok_at, t + hurt + self.rng.uniform(0.0, 0.4))
        return ("graze" if graze else "hit"), dmg

    def _rage(self, t, v):
        if t < self.rage_until:
            self.rage_until = min(t + 9.0, self.rage_until + 0.6)
            return
        self.rage = min(100.0, self.rage + v)
        if self.rage >= 99.99:
            self.rage_until = t + 9.0
            self.rage = 0.0

    def heal(self, v):
        self.hp = min(self.max_hp, self.hp + v)

    # ---------------------------------------------------------------- ataque
    def free(self, t):
        return t >= self.busy_until and t >= self.dist_ok_at

    def try_attack(self, t, allowed):
        """Llamado cada cuadro: si toca apretar y se puede, arranca el próximo corte (los golpes caen después)."""
        if t < self.next_tap:
            return
        if not allowed or not self.free(t):
            if t > self.chain_until:
                self.combo_i = 0
            return
        if self.combo_i > 0 and t > self.chain_until:
            self.combo_i = 0
        dmg, delay, length, cut = COMBO[self.combo_i]
        self.pending_hits.append((t + delay, dmg))
        self.cut_until = t + cut
        self.chain_until = t + length + 0.25
        self.combo_i = (self.combo_i + 1) % 3
        self.next_tap = t + (TAP if self.combo_i != 0 else 0.6)
        self.busy_until = max(self.busy_until, t + min(TAP, length) * 0.9)

    def due_hits(self, t):
        out = []
        keep = []
        for (ht, d) in self.pending_hits:
            (out if ht <= t else keep).append((ht, d))
        self.pending_hits = keep
        return out

    def damage_mul(self, t):
        m = 1.45 if t < self.rage_until else 1.0
        if t < self.riposte_until:
            m *= 1.5
            self.riposte_until = -1
        return m

    def on_connect(self, freeze):
        """anim.Freeze de Kaito al conectar (0.06 / 0.11 s): su combo se corre, el jefe no se frena."""
        self.next_tap += freeze
        self.pending_hits = [(ht + freeze, d) for (ht, d) in self.pending_hits]
        self.cut_until += freeze
        self.chain_until += freeze

    def on_dealt(self, t, d):
        self.dealt += d
        self.spirit = min(100, self.spirit + 3)
        self._rage(t, 4)
