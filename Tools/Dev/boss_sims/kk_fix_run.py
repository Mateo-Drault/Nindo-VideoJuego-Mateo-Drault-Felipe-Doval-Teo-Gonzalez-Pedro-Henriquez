"""Mediciones de la corrección (pelea entera de Kokuyō, distancia como estado):
  python kk_fix_run.py actos [nivel] [corridas]     sombra por acto (Kaito inmortal), lados, separaciones, éxito por golpe
  python kk_fix_run.py largo hp dmg heal niveles corridas    tiempo hasta ganar con reintentos
OLD=1 en el entorno = los números de antes."""
import sys, json, statistics, copy
import duet_sim as D
import fight_kokuyo as F


def cfg(hp=1800.0, dmg=1.0, heal=40.0):
    c = copy.deepcopy(F.CFG)
    c.update({"hp": float(hp), "gates": [1.0, 0.70, 0.36, 0.10], "escalate": True, "dmg_mul": dmg, "heal": heal})
    return c


def actos(level="bueno", runs=80, hp=1800.0):
    c = cfg(hp)
    acts = {a: {"seg": 0.0, "sombra": 0, "cuerpo": 0} for a in (1, 2, 3, 4)}
    zero1, first, nobi_d, sides3, gaps, overl, nobi_body, ok = 0, [], [], {}, [], 0, [], {}
    for s in range(runs):
        f = F.Fight(s + 1, level, 1, c)
        f.kaito.hp = 1e9
        log = []
        orig = f.resolve

        def res(actor, kind, move, imp, ring, vis, f=f, log=log, orig=orig):
            o = orig(actor, kind, move, imp, ring, vis)
            log.append((4 if f.last_stand else f.act, imp, actor, move, ring, getattr(f, "sside", "any"), o))
            return o
        f.resolve = res
        f.run()
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
            if x[2] != y[2] and x[0] == y[0]:
                gaps.append(y[1] - x[1])
                if y[4] < x[1] - 1e-6:
                    overl += 1
            if x[2] == "sombra" and x[3] == "nobi" and y[2] == "cuerpo" and y[1] - x[1] < 3.0:
                nobi_body.append(y[1] - x[1])
    out = {
        "bot": level, "hp": hp,
        "por_acto": {a: {"seg": round(v["seg"] / runs, 1), "golpes_sombra": round(v["sombra"] / runs, 2),
                         "golpes_cuerpo": round(v["cuerpo"] / runs, 1),
                         "parte_sombra_%": round(100 * v["sombra"] / max(1, v["sombra"] + v["cuerpo"]), 1)} for a, v in acts.items()},
        "acto1_sin_sombra_%": round(100 * zero1 / runs, 1),
        "primer_nobi_s_mediana": round(statistics.median(first), 1) if first else None,
        "nobi_distancia_m_p10_p50_p90": [round(sorted(nobi_d)[int(len(nobi_d) * q)], 2) for q in (0.1, 0.5, 0.9)] if nobi_d else None,
        "acto3_lados": sides3,
        "gap_min_entre_atacantes_s": round(min(gaps), 3) if gaps else None,
        "anillos_superpuestos": overl,
        "nobi_a_golpe_de_el_s_min": round(min(nobi_body), 3) if nobi_body else None,
        "exito_por_golpe": {k: round(v[1] / v[0], 3) for k, v in sorted(ok.items()) if v[0] >= 20},
    }
    print(json.dumps(out, ensure_ascii=False))


def largo(hp, dmg, heal, levels, runs):
    for lv in levels.split(","):
        r = F.report(lv, runs, cfg(hp, dmg, heal), "hp%d dmg%.2f heal%d" % (hp, dmg, heal))
        print(json.dumps(r, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    if sys.argv[1] == "actos":
        actos(sys.argv[2] if len(sys.argv) > 2 else "bueno", int(sys.argv[3]) if len(sys.argv) > 3 else 80,
              float(sys.argv[4]) if len(sys.argv) > 4 else 1800.0)
    else:
        largo(float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4]), sys.argv[5], int(sys.argv[6]))
