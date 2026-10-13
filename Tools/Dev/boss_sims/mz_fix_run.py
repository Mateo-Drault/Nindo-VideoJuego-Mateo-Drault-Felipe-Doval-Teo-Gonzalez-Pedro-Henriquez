"""Mizuchi: patrones por pelea (sin morir), firmas de fase vistas y repeticiones del mismo especial, y barrido de largo.
python mz_fix_run.py uso preset [corridas]  |  python mz_fix_run.py largo [corridas]"""
import sys, json
from multiprocessing import Pool
import mizuchi_sim as M
import mz_run as R

SPECIAL_OF = {"Perlas del Lago": "pearls", "Perlas desde lejos": "pearls", "Chorro": "jet", "Chorro desde lejos": "jet",
              "Tama-asobi": "rally", "Peloteo desde lejos": "rally", "Chorro barrido": "jetsweep", "Barrido desde lejos": "jetsweep",
              "Perlas de tormenta": "storm", "Tormenta desde lejos": "storm"}


def uso(preset, runs=60):
    cfg = R.cfg_of(preset)
    cnt, n, secs = {}, 0, 0.0
    sig = {"ola": 0, "pilares": 0, "tormenta": 0}
    repeats, specials = 0, 0
    for s in range(runs):
        f = M.Fight(s + 1, "bueno", cfg)
        f.k.hp = f.k.max_hp = 1e9
        seq = []
        orig = f.start_pattern

        def sp(p, f=f, seq=seq, orig=orig):
            seq.append((f.t, p["name"]))
            orig(p)
        f.start_pattern = sp
        f.run()
        n += 1
        secs += sum(f.phase_time)
        names = [x[1] for x in seq]
        for k in names:
            cnt[k] = cnt.get(k, 0) + 1
        sig["ola"] += "Ola de la Cascada" in names
        sig["pilares"] += "Pilares" in names
        sig["tormenta"] += any(x in names for x in ("Tormenta desde lejos", "Perlas de tormenta"))
        # el mismo especial dos veces seguidas (patrón de por medio no cuenta) en menos de 6 s
        last = None
        for t, k in seq:
            sp_ = SPECIAL_OF.get(k)
            if sp_:
                specials += 1
                if last and last[1] == sp_ and t - last[0] < 6.0:
                    repeats += 1
                last = (t, sp_)
            else:
                last = None
    print(preset, "peleas", n, "seg/pelea", round(secs / n, 1), "fase3 vista %",
          {k: round(100 * v / n) for k, v in sig.items()}, "especial repetido seguido", repeats, "de", specials)
    for k, v in sorted(cnt.items(), key=lambda x: -x[1]):
        print("   ", k.encode("ascii", "replace").decode(), round(v / n, 2))


def one(a):
    hp, dm, lv, runs = a
    c = R.cfg_of("fix", {"hp": hp, "dmg": [dm, dm * 1.1, dm * 1.1]})
    r = M.report(lv, runs, c, "")
    return {"hp": hp, "dmg": dm, "bot": lv, "min": r["min_mediana"], "p10_p90": r["p10_p90"], "muertes": r["muertes"],
            "gana1_%": r["gana_1ra_%"], "seg_fase_1ra": r["seg_fase_1ra"]}


if __name__ == "__main__":
    if sys.argv[1] == "uso":
        uso(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 60)
    else:
        runs = int(sys.argv[2]) if len(sys.argv) > 2 else 40
        jobs = [(hp, dm, lv, runs) for hp in (1440, 2160, 2880) for dm in (1.0, 0.8, 0.6) for lv in ("bueno", "humano", "promedio")]
        with Pool(10) as p:
            for row in p.imap(one, jobs):
                print(json.dumps(row, ensure_ascii=False), flush=True)
