"""Pelea ENTERA contra Kokuyō a 60 Hz: la lógica del cuerpo y la sombra del duet_sim de la etapa 1 (patrones, tiempos,
turnos y dúos de KokuyoBoss.Shadow, la regla del Gap) más lo que faltaba para medir el largo:
  * la vida (1800 o la que se pase), los pisos de cada acto (Gates), las escenas de cambio de acto (invulnerables, curan
    30 y dan 30 de Espíritu), la última resistencia (Último Desfile -> de rodillas -> ejecución);
  * el ataque del bot (kaito.py): solo pega si nadie amenaza (anillo a la vista) y él no está en guardia; en neutral
    aguanta 4 golpes (poiseHits) y el quinto rebota; de rodillas x1.3 y 8 golpes como mucho;
  * la defensa del bot con su vida: si muere, la pelea vuelve a empezar (desde el 70 % si ya vio el eclipse) y se cobra
    lo que tarda en volver (RESPAWN s);
  * el sustento y la segunda salida de la fase C3 (claves de cfg): 'stage_heal' (KokuyoMoves.StageHeal, por acto, en el
    golpe que cruza cada corte de tramo), 'kneel_heal' (probado y descartado: premia al que ya no muere), 'encore' y
    'encore_window' (KokuyoBoss.Shadow.EncoreChance / EncoreWindow: en el eclipse la sombra vuelve a salir del otro lado
    apenas se apagó, metida entre los golpes de él, que no la espera);
  * 'kneel_first_once': solo la primera rodilla del Acto 1 sale con un parry (después dos); 'retry_by_act': morir en el
    Acto 2 o 3 reintenta desde ese acto (el 3 con el arranque rápido de la sombra arrancada y la luna tapada).
  * los golpes de dúo que la sombra no puede dar porque se está apagando quedan guardados (duet_sim.run_deferred).
Uso: python fight_kokuyo.py [nivel] [corridas] con la config vieja (CFG); con la de hoy, kk_fix_run.py (TUNING, leída del
C# por cs_knobs).
"""
import os, sys, json, random, statistics
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# las simulaciones de Kokuyō y Mizuchi de la fase C2 (combat-kokuyo), traídas al repo con el reintento por fase de
# Mizuchi y el bot promedio recalibrado. Uso: python Tools/Dev/boss_sims/kk_fix_run.py largo VIDA DAÑO 40 bueno,promedio 60
# y python Tools/Dev/boss_sims/mz_run.py fix bueno,promedio 60 '{"hp": 2160, "dmg": [0.35, 0.385, 0.385], "retry": true}'
import duet_sim as D
from kaito import Kaito, DT

RESPAWN = 22.0          # pantalla "Caíste" + santuario del dojo + subir la escalera + el arranque rápido

CFG = {
    "hp": 900.0, "gates": [1.0, 0.65, 0.30, 0.10], "heal": 30.0, "spirit": 30.0,
    "kneel": 3.6, "kneel_cap": 8, "kneel_need": [0, 1.0, 2.0, 2.0], "poise": 4,
    "cool": (0.7, 1.4), "guard": (0.56, 0.96), "dmg_mul": 1.0,
    "t_tear": 2.6, "t_eclipse": 3.7, "t_last": 1.5,
}


def body_damage(move, act):
    return D.DMG.get(move, 20) * CFG["dmg_mul"]


class Fight(D.Sim):
    def __init__(self, seed, level, start_act=1, cfg=None, kneel_taught=False):
        super().__init__(start_act, seed, 1e9, level=level)
        self.cfg = cfg or CFG
        self.kaito = Kaito(self.rng, level)
        self.maxhp = self.cfg["hp"]
        self.hp = self.maxhp * (self.cfg["gates"][min(3, start_act) - 1] if start_act >= 2 else 1.0)
        # lo que KokuyoBoss recuerda entre reintentos: ya cayó de rodillas una vez, ya enseñó la salida de la oscuridad
        self.kneel_taught = kneel_taught or start_act >= 2
        self.dark_taught = start_act >= 3
        self.encore_until = -1.0
        self.trans_until = -1.0
        self.pending_act = None
        self.last_stand = False
        self.kneel_hits = 0
        self.neutral_hits, self.last_neutral = 0, -9.0
        self.won = False
        self.reached = start_act
        self.act_time = {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0}
        self.hits_landed = 0
        self.desfile = None
        self.kneel_start = -1.0
        self.tg = list(D.TURN_MIN_GAP); self.mq = list(D.MAX_QUIET)
        self.escalated = False; self.roar_pending = False; self.roar_until = -1.0
        self.stage = 0
        self.d = 4.6
        self.last_dark_side = "flank"
        self.nobi_log = []
        self.encores = 0
        if start_act >= 2:
            # arranque rápido del reintento: la sombra ya arrancada (y para el 3, la luna tapada)
            self.begin_transition(min(3, start_act), quick=True)

    # ---------------------------------------------------------------- reglas nuevas
    def need_now(self):
        """Postura para caer de rodillas: KokuyoBoss.KneelNeed (o la tabla vieja por acto)."""
        a = min(3, self.act)
        if self.cfg.get("kneel_first_once"):
            return self.cfg["kneel_first"] if a == 1 and not self.kneel_taught else self.cfg["kneel_need_n"]
        return self.cfg["kneel_need"][a]

    def on_duet_cue(self):
        # la sombra ya salió otra vez, en el dúo: la segunda salida pendiente sobra
        self.encore_until = -1.0

    def run_queued(self, t):
        """KokuyoBoss.RunQueuedShadow: el golpe de dúo guardado y la segunda salida del eclipse salen apenas la sombra
        puede, esté él atacando o no. True mientras haya algo guardado (ese cuadro no se piden turnos)."""
        waiting = self.deferred is not None or self.encore_until > 0
        sinking = self.bstate == "attack" and self.bsteps is not None and self.bi < len(self.bsteps) and self.bsteps[self.bi][0] == "R:ShadowSink"
        if t < self.roar_until or sinking:
            return waiting
        if self.run_deferred():
            return True
        if self.encore_until > 0 and t > self.encore_until:
            self.encore_until = -1.0
        if self.encore_until < 0:
            return False
        if not self.shadow_can():
            return True
        self.encore_until = -1.0
        sd = "opp" if self.last_dark_side == "flank" else "flank"
        if self.shadow_try("giri", False, sd):
            self.last_dark_side = sd
            self.encores += 1
            if self.bstate != "attack":
                self.bnext = max(self.bnext, self.simpact + D.BODY_AFTER)
        return True

    def kneel(self, t):
        super().kneel(t)
        self.encore_until = -1.0
        self.kneel_taught = True
        # cfg 'kneel_heal': cada vez que cae de rodillas (postura rota) Kaito se cura
        if self.cfg.get("kneel_heal") and not self.last_stand:
            self.kaito.heal(self.cfg["kneel_heal"])
        self.kneel_until = t + self.cfg["kneel"]
        self.bnext = self.kneel_until + 0.3
        self.kneel_hits = 0

    def dist(self):
        return self.d

    def stage_count(self):
        if not self.cfg.get("escalate"):
            return 0
        if D.OLD:
            return 1
        return 2 if self.maxhp >= 2200 else 1

    def check_escalation(self):
        n = self.stage_count()
        if self.stage >= n or self.last_stand or self.pending_act is not None:
            return
        g = self.cfg["gates"]
        a = min(3, self.act)
        cut = (g[a - 1] - (g[a - 1] - g[a]) * (self.stage + 1) / (n + 1.0)) * self.maxhp
        if self.hp > cut:
            return
        self.stage += 1
        self.escalated = True
        self.roar_pending = True
        # cfg 'stage_heal': cada corte del acto cura a Kaito en el golpe que lo cruza (KokuyoBoss.Pacing, como los
        # tramos de la armadura de Gorō); un número o uno por acto (KokuyoMoves.StageHeal)
        sh = self.cfg.get("stage_heal", 0.0)
        self.kaito.heal(sh[a] if isinstance(sh, (list, tuple)) else sh)
        if self.stage >= 2:
            self.add_stage2(a)
            return
        S, R = D.S, D.R
        kesa, gyaku, tsuki, ichi = S("Kesagiri", "H"), S("Gyakugiri", "H"), S("Tsuki", "H"), S("Ichimonji", "U")

        def add(name, w, steps, cd=0, minr=0, maxr=5.0, cues=None):
            self.P.append({"name": name, "w": w * 3, "w0": w, "steps": steps, "cd": cd, "minr": minr, "maxr": maxr, "cues": cues or [], "last": -99})
        if a == 1:
            add("Luna y Horizonte", 1.1, [kesa, gyaku, ichi], 9)
        elif a == 2:
            add("Escuela de la Sombra", 1.2, [kesa, gyaku, tsuki, R("TsukiRecover")], 10, cues=[(1, "giri", False, "opp")])
        else:
            add("Luna Nueva", 1.2, [ichi, kesa, gyaku, R("RecoverHR")], 10, cues=[(2, "giri", True, "opp" if D.OLD else "flank")])
        m = self.cfg.get("esc_cd", 0.75)
        for p in self.P:
            if p["name"] in ("Colmillo", "Horizonte", "Rompecascos", "Paso de Sombra", "Clavo y Colmillo"):
                p["cd"] *= m
        f = self.cfg.get("esc_shadow", 0.8)
        self.tg[a] = D.TURN_MIN_GAP[a] * f; self.mq[a] = D.MAX_QUIET[a] * f

    def add_stage2(self, a):
        S, R = D.S, D.R
        kesa, gyaku, ichi = S("Kesagiri", "H"), S("Gyakugiri", "H"), S("Ichimonji", "U")
        for p in self.P:
            if "w0" in p:
                p["w"] = p["w0"]

        def add(name, w, steps, cd=0, minr=0, maxr=5.0, cues=None):
            self.P.append({"name": name, "w": w * 3, "w0": w, "steps": steps, "cd": cd, "minr": minr, "maxr": maxr, "cues": cues or [], "last": -99})
        if a == 1:
            add("Sombra Larga", 1.1, [kesa, gyaku, R("RecoverHR")], 11, cues=[(1, "nobi", True, "any")])
        elif a == 2:
            add("Clavo y Horizonte", 1.0, [ichi], 11, maxr=5.5, cues=[(0, "nui", True, "any")])
        else:
            add("Eclipse Cruzado", 1.1, [kesa, gyaku, kesa, gyaku, R("RecoverHR")], 12, cues=[(0, "giri", False, "flank"), (2, "giri", False, "opp")])
        for p in self.P:
            if p["name"] in ("Colmillo", "Horizonte", "Rompecascos", "Paso de Sombra", "Clavo y Colmillo"):
                p["cd"] *= 0.75
        self.tg[a] = D.TURN_MIN_GAP[a] * 0.65; self.mq[a] = D.MAX_QUIET[a] * 0.65

    def gate_floor(self):
        g = self.cfg["gates"]
        return g[3 if self.last_stand else min(3, self.act)] * self.maxhp

    def begin_transition(self, nxt, quick=False):
        t = self.t
        from_kneel = t < self.kneel_until
        dur = {2: self.cfg["t_tear"], 3: self.cfg["t_eclipse"], 4: self.cfg["t_last"]}[nxt]
        if quick:
            # KokuyoBoss: la sombra arrancada rápida ~1.3 s; para el 3, más la luna tapada rápida ~1.4 s
            dur = 1.3 if nxt == 2 else 2.7
        dur += 0.45 if from_kneel else 0.0
        self.trans_until = t + dur
        self.pending_act = nxt
        self.kneel_until = -1
        self.posture = 0.0
        self.bstate = "trans"; self.bimpact = -1
        self.simpact = -1; self.sstate = "hunt"
        self.deferred = None
        self.encore_until = -1.0
        self.d = max(self.d, 5.0)          # PushKaito(5, 3) de cada escena
        # RewardKaito: en la sombra arrancada (también la rápida), en el eclipse y, con 'heal_last', al levantarse para la
        # última resistencia (sin ella solo le asegura el Espíritu de la ejecución: end_transition)
        if nxt in (2, 3) or self.cfg.get("heal_last"):
            self.kaito.heal(self.cfg["heal"])
            self.kaito.spirit = min(100, self.kaito.spirit + self.cfg["spirit"])

    def end_transition(self):
        nxt = self.pending_act
        self.pending_act = None
        if nxt == 4:
            self.last_stand = True
            # el Último Desfile: cinco golpes con la pausa del Acto 3 y de rodillas sí o sí
            self.P = [{"name": "Último Desfile", "w": 1, "steps": [D.S("Kesagiri", "H"), D.S("Gyakugiri", "H"), D.S("Kesagiri", "H"),
                       D.S("Gyakugiri", "H"), D.S("Tsuki", "H")], "cd": 0, "minr": 0, "maxr": 99, "cues": [], "last": -99, "exhaust": True}]
            self.kaito.spirit = max(self.kaito.spirit, 30.5)
        else:
            self.act = nxt
            self.reached = max(self.reached, nxt)
            self.P = D.patterns(nxt)
            self.escalated = False; self.roar_pending = False; self.stage = 0
            self.last_dark_side = "flank"
            self.tg = list(D.TURN_MIN_GAP); self.mq = list(D.MAX_QUIET)
            self.act_start = self.t
            self.last_turn = -99
            self.nobi_taught = nxt > 1
        self.bstate = "chase"; self.bnext = self.t + 0.5

    def shadow_allowed(self):
        return not self.last_stand and self.pending_act is None

    # ---------------------------------------------------------------- golpes de Kaito
    def body_hittable(self, t):
        if self.pending_act is not None or t < self.trans_until or t < self.roar_until:
            return False, False
        if t < self.kneel_until:
            return True, True
        if self.bstate == "guard":
            return False, False
        if self.bstate == "attack" and self.bsteps is not None and self.bi < len(self.bsteps):
            c, k = self.bsteps[self.bi]
            if c == "R:ShadowSink":
                return False, False
        return True, False

    def threatened(self, t):
        if self.bimpact > t and t >= self.bimpact - D.MAXLEAD[self.bkind]:
            return True
        if self.simpact > t and t >= getattr(self, "sring", t):
            return True
        return False

    def kaito_tick(self, t):
        k = self.kaito
        # AutoPilot: camina hacia el jefe mientras esté a más de 2.2 m (6.2 m/s); él ronda a 4.6 y se acerca a 3 m/s
        if t >= k.busy_until and self.d > 2.2 and self.pending_act is None:
            self.d = max(2.2, self.d - 6.2 * DT)
        hittable, kneeling = self.body_hittable(t)
        hittable = hittable and self.d < 2.6
        # el bot no arranca un corte con un anillo a la vista ni contra la guardia (rara vez, apurado)
        greedy = self.rng.random() < k.sk["greedy"] * DT * 4
        k.try_attack(t, hittable and (not self.threatened(t) or greedy))
        for (ht, base) in k.due_hits(t):
            hittable, kneeling = self.body_hittable(ht)
            if not hittable or self.d > 2.9:
                continue
            if self.bstate == "chase" and not kneeling:
                if ht - self.last_neutral > 2.2:
                    self.neutral_hits = 0
                self.last_neutral = ht
                self.neutral_hits += 1
                if self.neutral_hits > self.cfg["poise"]:
                    # rebota en la guardia: clang, +0.25 de postura, y queda cubierto
                    self.neutral_hits = 0
                    self.bstate = "guard"; self.bguard_until = ht + self.rng.uniform(*self.cfg["guard"])
                    self.posture += 0.25
                    k.on_connect(0.06)
                    continue
            d = base * k.damage_mul(ht) * (1.3 if kneeling else 1.0)
            floor = self.gate_floor()
            d = min(d, max(0.0, self.hp - floor))
            self.hp -= d
            self.hits_landed += 1
            k.on_dealt(ht, d)
            k.on_connect(0.11 if base >= 18 else 0.06)
            self.check_escalation()
            if kneeling:
                self.kneel_hits += 1
                self.kneel_until = max(self.kneel_until, ht + 0.6)
                if self.kneel_hits >= self.cfg["kneel_cap"] and not self.last_stand:
                    self.kneel_until = ht
                    self.bstate = "guard"; self.bguard_until = ht + self.rng.uniform(*self.cfg["guard"])
                    self.bnext = ht + self.rng.uniform(*self.cfg["cool"])
            if self.hp <= floor + 0.5 and self.pending_act is None:
                if self.last_stand:
                    continue
                self.begin_transition(self.act + 1 if self.act < 3 else 4)
                return

    # ---------------------------------------------------------------- golpes que llegan
    def resolve(self, actor, kind, move, imp, ring, vis):
        dmg = D.DMG.get(move if move != "giri" else "giri%d" % self.act, 20) * self.cfg["dmg_mul"]
        side = getattr(self, "sside", "any") if actor == "sombra" else "front"
        hard = side == "opp" or (actor == "sombra" and self.act == 3)
        out, _ = self.kaito.defend(imp, "U" if kind == "U" else "H", dmg, notice_from=min(ring, vis), hard=hard)
        # avance del cuerpo (travel_m del clip) y empujones
        if actor == "cuerpo":
            if move == "Tsuki":
                self.d = max(1.6, self.d - 3.0)
            elif move in ("Kesagiri", "Gyakugiri", "ShadowEmerge"):
                self.d = max(1.6, self.d - 0.5) if move != "ShadowEmerge" else 3.0
        self.d += {"hit": 2.2, "graze": 0.6, "parry": 0.6, "perfect": 1.0, "dodge": 1.4}.get(out, 0.0)
        self.d = min(self.d, 9.0)
        if actor == "sombra" and move == "nobi":
            self.nobi_log.append(self.d)
        self.events_side = getattr(self, "events_side", [])
        self.events_side.append((actor, move, side, out, self.act))
        if out == "graze":
            self.posture += 0.34
        self.events.append((imp, actor, kind, move, ring, vis))
        self.outcomes.append((actor, move, kind, out))
        return "parry" if out == "parry" else "perfect" if out == "perfect" else "dodge" if out == "dodge" else "hit"

    # ---------------------------------------------------------------- bucle
    def run(self, limit=900.0):
        while self.t < limit:
            t = self.t
            if self.kaito.hp <= 0:
                return self
            if self.won:
                return self
            seg = 4 if self.last_stand else self.act
            self.act_time[seg] += DT
            # ---- escena de cambio de acto
            if self.pending_act is not None:
                if t >= self.trans_until:
                    self.end_transition()
                self.t += DT
                continue
            need = self.need_now()
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
                if self.last_stand:
                    # de rodillas en la última resistencia: el bot ejecuta (tiene Espíritu: TopUpSpirit)
                    if t >= self.kneel_start + 0.4:
                        self.won = True
                        continue
            elif self.bstate == "attack":
                if t >= self.bstep_end:
                    self.bi += 1
                    if self.bi < len(self.bsteps):
                        self.begin_body_step()
                    else:
                        self.bstate = "guard"; self.bguard_until = t + self.rng.uniform(*self.cfg["guard"])
                        self.bnext = t + self.rng.uniform(*self.cfg["cool"])
                        if self.roar_pending and self.posture < need - 0.01 and not self.bpat.get("exhaust"):
                            # el rugido de la escalada: 1.3 s quieto (se le puede pegar), ni él ni la sombra atacan
                            self.roar_pending = False
                            self.bstate = "chase"; self.bguard_until = t
                            self.roar_until = t + 1.3
                            self.bnext = max(self.bnext, t + 1.3 + 0.4)
                            self.shold_body_until = max(self.shold_body_until, t + 1.3)
                        elif self.bpat.get("exhaust"):
                            self.kneel(t); self.kneel_start = t
                        elif self.posture >= need - 0.01:
                            self.kneel(t)
                        elif not self.last_stand and self.rng.random() < D.TURN_CHANCE[self.act]:
                            self.turn_asked = True
            else:
                if self.bstate == "guard" and t >= self.bguard_until:
                    self.bstate = "chase"
                hold = t < self.shold_body_until
                if self.bstate == "chase" and not hold and t >= self.bnext:
                    p = self.pick()
                    if p:
                        p["last"] = t
                        if "w0" in p:
                            p["w"] = p["w0"]
                        self.bpat = p; self.bsteps = p["steps"]; self.bi = 0; self.bstate = "attack"
                        self.begin_body_step()
            # ---- director de la sombra (el del duet_sim): primero lo guardado, después los turnos
            if self.shadow_allowed() and t >= self.kneel_until and self.run_queued(t):
                pass
            elif self.shadow_allowed() and self.sstate == "hunt" and self.body_free() and self.bstate != "attack" and self.shadow_can():
                a = self.act
                if t >= self.act_start + D.FIRST_TURN[a] and t >= self.last_turn + self.tg[a] and t >= self.roar_until:
                    quiet = t >= max(self.last_turn, self.act_start) + self.mq[a]
                    if self.turn_asked or quiet or (a == 1 and not self.nobi_taught):
                        sd = "any"
                        if a == 1:
                            mv = "nobi"
                        elif a == 2:
                            r = self.rng.random(); mv = "giri" if r < 0.5 else "nui" if r < 0.8 else "watari"
                        else:
                            mv = "giri"
                            sd = "opp" if D.OLD or self.last_dark_side == "flank" else "flank"
                        # el corte que enseña la salida de la oscuridad no tiene segunda salida
                        teaching = a == 3 and not self.dark_taught
                        ok = self.shadow_try(mv, False, sd) or (a >= 2 and self.shadow_try("giri", False, sd))
                        if ok and a == 3:
                            self.last_dark_side = sd
                            if not teaching and self.rng.random() < self.cfg.get("encore", 0.0):
                                # la sombra sale otra vez del otro lado apenas se apagó; él no la espera
                                self.encore_until = self.simpact + self.cfg.get("encore_window", 3.2)
                        if ok:
                            self.turn_asked = False
                            self.bnext = max(self.bnext, self.simpact + (0.4 if a == 1 else D.BODY_AFTER))
            # ---- Kaito
            self.kaito_tick(t)
            self.t += DT
        return self


def attempt_series(seed, level, cfg=None, max_deaths=12, log=None):
    """Intentos hasta ganar: devuelve (tiempo total con los reintentos, muertes, tiempos por acto del intento ganador).
    'log' (lista) recibe (acto en que murió, segundos del intento) de cada muerte."""
    cfg = cfg or CFG
    total, deaths, start, taught = 0.0, 0, 1, False
    hits = 0
    while True:
        f = Fight(seed * 31 + deaths, level, start, cfg, taught).run()
        total += f.t + f.hits_landed * 0.04       # hit-stop global (tiempo real)
        hits += f.hits_landed
        taught = f.kneel_taught
        if f.won:
            return total, deaths, f.act_time, f.kaito
        deaths += 1
        total += RESPAWN
        if log is not None:
            log.append((4 if f.last_stand else f.act, f.t))
        if cfg.get("retry_by_act"):
            # KokuyoBoss.OnPlayerDied: el reintento arranca en el acto en que murió (2 o 3)
            if f.reached >= 2:
                start = max(start, min(3, f.reached))
        elif f.reached >= 3:
            start = 2
        if deaths >= max_deaths:
            return total, deaths, f.act_time, f.kaito


def report(level, runs=120, cfg=None, label=""):
    T, Dn, A, W1 = [], [], {1: [], 2: [], 3: [], 4: []}, 0
    first_try = 0
    log = []
    for s in range(runs):
        tot, deaths, at, k = attempt_series(s + 1, level, cfg, log=log)
        T.append(tot); Dn.append(deaths)
        if deaths == 0:
            first_try += 1
            for a in A:
                A[a].append(at[a])
    T.sort()
    by_act = {}
    for a, _ in log:
        by_act[a] = by_act.get(a, 0) + 1
    res = {
        "bot": level, "config": label,
        "min_total_mediana": round(statistics.median(T) / 60, 2),
        "min_total_media": round(statistics.mean(T) / 60, 2),
        "min_total_p10_p90": [round(T[len(T) // 10] / 60, 2), round(T[9 * len(T) // 10] / 60, 2)],
        "muertes_media": round(statistics.mean(Dn), 2),
        "gana_sin_morir_%": round(100 * first_try / runs, 1),
        "muertes_por_acto": {a: round(n / runs, 2) for a, n in sorted(by_act.items())},
        "seg_por_acto_sin_morir": {a: round(statistics.median(v), 1) if v else None for a, v in A.items()},
    }
    return res


if __name__ == "__main__":
    lv = sys.argv[1] if len(sys.argv) > 1 else "bueno"
    runs = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    print(json.dumps(report(lv, runs, CFG, "actual"), ensure_ascii=False))
