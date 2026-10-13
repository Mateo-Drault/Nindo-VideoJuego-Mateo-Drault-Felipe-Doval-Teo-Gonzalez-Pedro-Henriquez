"""Mediciones de la pelea entera de Kokuyō (distancia como estado), con las perillas de hoy por defecto (TUNING):
  python kk_fix_run.py actos [nivel] [corridas] ['{"hp": 2700}']      sombra por acto (Kaito inmortal), lados,
                                                                    separaciones, anillos encimados, éxito por golpe
  python kk_fix_run.py largo [niveles] [corridas] ['{"dmg_mul": 0.4}'] minutos hasta ganar con los reintentos y muertes
  python kk_fix_run.py largo VIDA DAÑO CURA niveles corridas          (la forma vieja: vida, daño y cura de acto)
Las claves que se pueden cambiar son las de TUNING y las de fight_kokuyo.CFG. OLD=1 en el entorno = los turnos de la
sombra de antes de la fase C2."""
import sys, json, statistics, copy
import duet_sim as D
import fight_kokuyo as F

# lo de hoy, copiado de KokuyoMoves (HealthScale 3 x 1800, DamageScale, StageHeal, TransitionHeal), KokuyoBoss.Gates y
# KokuyoBoss.Shadow (EncoreChance, EncoreWait): si se cambian allá, se cambian acá
TUNING = {"hp": 1800.0 * 3.0, "dmg_mul": 0.33, "heal": 40.0, "spirit": 30.0, "stage_heal": 35.0,
          "gates": [1.0, 0.70, 0.40, 0.10], "encore": 0.6, "encore_wait": 3.0, "escalate": True}


def cfg(hp=None, dmg=None, heal=None, **extra):
    c = copy.deepcopy(F.CFG)
    c.update(copy.deepcopy(TUNING))
    if hp is not None:
        c["hp"] = float(hp)
    if dmg is not None:
        c["dmg_mul"] = float(dmg)
    if heal is not None:
        c["heal"] = float(heal)
    c.update(extra)
    return c


def actos(level="bueno", runs=80, **extra):
    c = cfg(**extra)
    acts = {a: {"seg": 0.0, "sombra": 0, "cuerpo": 0} for a in (1, 2, 3, 4)}
    zero1, first, nobi_d, sides3, gaps, overl, nobi_body, ok, ss3 = 0, [], [], {}, [], 0, [], {}, []
    encores = 0
    for s in range(runs):
        f = F.Fight(s + 1, level, 1, c)
        # inmortal de verdad: la cura de cada cambio de acto recorta la vida a max_hp (con solo hp = 1e9 Kaito volvía a
        # 100 en la escena del Acto 2 y moría en el 3, que se medía cortado: ~15 s y 1.8 cortes en vez de ~32 s)
        f.kaito.hp = f.kaito.max_hp = 1e9
        log = []
        orig = f.resolve

        def res(actor, kind, move, imp, ring, vis, f=f, log=log, orig=orig):
            o = orig(actor, kind, move, imp, ring, vis)
            log.append((4 if f.last_stand else f.act, imp, actor, move, ring, getattr(f, "sside", "any"), o))
            return o
        f.resolve = res
        f.run()
        encores += f.encores
        n1 = 0
        for a, imp, actor, mv, ring, sd, o in log:
            acts[a]["sombra" if actor == "sombra" else "cuerpo"] += 1
            if actor == "sombra":
                if a == 1:
                    n1 += 1
                    if n1 == 1:
                        first.append(imp)
                if a == 3:
                    sides3[sd] = sides3.get(sd, 0) + 1
            key = "%s:%s" % (actor, mv)
            d = ok.setdefault(key, [0, 0])
            d[0] += 1
            d[1] += o in ("parry", "perfect", "dodge")
        for a in acts:
            acts[a]["seg"] += f.act_time[a]
        zero1 += n1 == 0
        nobi_d += f.nobi_log
        ev = sorted(log, key=lambda e: e[1])
        for x, y in zip(ev, ev[1:]):
            if x[0] != y[0]:
                continue
            # el anillo del segundo arranca antes de que pegue el primero (de cualquiera de los dos atacantes)
            if y[4] < x[1] - 1e-6:
                overl += 1
            if x[2] != y[2]:
                gaps.append(y[1] - x[1])
            elif x[2] == "sombra" and x[0] == 3:
                ss3.append(y[1] - x[1])
            if x[2] == "sombra" and x[3] == "nobi" and y[2] == "cuerpo" and y[1] - x[1] < 3.0:
                nobi_body.append(y[1] - x[1])
    out = {
        "bot": level, "hp": c["hp"],
        "por_acto": {a: {"seg": round(v["seg"] / runs, 1), "golpes_sombra": round(v["sombra"] / runs, 2),
                         "golpes_cuerpo": round(v["cuerpo"] / runs, 1),
                         "parte_sombra_%": round(100 * v["sombra"] / max(1, v["sombra"] + v["cuerpo"]), 1)} for a, v in acts.items()},
        "acto1_sin_sombra_%": round(100 * zero1 / runs, 1),
        "primer_nobi_s_mediana": round(statistics.median(first), 1) if first else None,
        "nobi_distancia_m_p10_p50_p90": [round(sorted(nobi_d)[int(len(nobi_d) * q)], 2) for q in (0.1, 0.5, 0.9)] if nobi_d else None,
        "acto3_lados": sides3,
        "acto3_segundas_salidas": round(encores / runs, 2),
        "acto3_sombra_tras_sombra_s_min": round(min(ss3), 3) if ss3 else None,
        "gap_min_entre_atacantes_s": round(min(gaps), 3) if gaps else None,
        "anillos_superpuestos": overl,
        "nobi_a_golpe_de_el_s_min": round(min(nobi_body), 3) if nobi_body else None,
        "exito_por_golpe": {k: round(v[1] / v[0], 3) for k, v in sorted(ok.items()) if v[0] >= 20},
    }
    print(json.dumps(out, ensure_ascii=False))


def largo(levels, runs, **extra):
    c = cfg(**extra)
    label = "hp%d dmg%.2f tramo%d acto%d" % (c["hp"], c["dmg_mul"], c["stage_heal"], c["heal"])
    for lv in levels.split(","):
        r = F.report(lv, runs, c, label)
        print(json.dumps(r, ensure_ascii=False), flush=True)


def _num(x):
    try:
        float(x)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    a = sys.argv
    over = json.loads(a[-1]) if len(a) > 2 and a[-1].startswith("{") else {}
    if a[1] == "actos":
        actos(a[2] if len(a) > 2 and not a[2].startswith("{") else "bueno",
              int(a[3]) if len(a) > 3 and _num(a[3]) else 80, **over)
    elif len(a) > 2 and _num(a[2]):
        largo(a[5], int(a[6]), hp=float(a[2]), dmg=float(a[3]), heal=float(a[4]), **over)
    else:
        largo(a[2] if len(a) > 2 and not a[2].startswith("{") else "bueno,promedio",
              int(a[3]) if len(a) > 3 and _num(a[3]) else 60, **over)
