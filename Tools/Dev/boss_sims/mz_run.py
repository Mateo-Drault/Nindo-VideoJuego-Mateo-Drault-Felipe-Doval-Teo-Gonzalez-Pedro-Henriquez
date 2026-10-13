"""Corre presets de mizuchi_sim: python mz_run.py preset[,preset] niveles [corridas]"""
import sys, json, copy
import mizuchi_sim as M

FAST = {"Salto del Dragón": [12, 9, 7], "Ola de la Cascada": [15, 13, 10], "Pilares": [20, 17, 12],
        "Chorro barrido": [8, 8, 6.5], "Perlas de tormenta": [6, 6, 5]}
PRESETS = {
    "hoy": {},
    "doble": {"hp": 1440},
    "nuevo": {"hp": 1440, "th": [0.66, 0.33], "new": True, "heal": [0, 25, 20], "heal_spirit": [0, 20, 20],
              "swim_mul": [1, 0.75, 0.6], "wave_speed": [8, 8, 9], "pillar_gap": [0.45, 0.45, 0.38], "cds": FAST},
    "retirada": {"hp": 1440, "th": [0.66, 0.33], "new": True, "heal": [0, 25, 20], "heal_spirit": [0, 20, 20],
                 "swim_mul": [1, 0.75, 0.6], "wave_speed": [8, 8, 9], "pillar_gap": [0.45, 0.45, 0.38], "cds": FAST,
                 "retreat": [0.9, 0.7, 0.8, 0.8, 1.0]},
}
PRESETS["final"] = dict(PRESETS["retirada"], th=[0.68, 0.38], dmg=[0.85, 0.935, 0.935])
# la corrección: una espera por especial, firmas de fase, mezcla de cerca más liviana y el daño de diseño (x1)
PRESETS["fix"] = dict(PRESETS["final"], fix=True, dmg=[1.0, 1.1, 1.1])
# lo de hoy (MizuchiBoss.Pacing: HealthScale 2.25, DamageScale 0.33 x1.1 corrompido, PostureHeal 14) con el reintento por
# fase. Uso: python mz_run.py tuning bueno,promedio,humano 200 ['{"hp": 2880, "posture_heal": 10}']
PRESETS["tuning"] = dict(PRESETS["fix"], hp=1440 * 2.25, dmg=[0.33, 0.363, 0.363], retry=True, posture_heal=14)


def cfg_of(name, extra=None):
    c = M.base_cfg()
    c.update(copy.deepcopy(PRESETS[name]))
    if extra:
        c.update(extra)
    return c


if __name__ == "__main__":
    runs = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    extra = json.loads(sys.argv[4]) if len(sys.argv) > 4 else None
    for pn in sys.argv[1].split(","):
        for lv in sys.argv[2].split(","):
            print(json.dumps(M.report(lv, runs, cfg_of(pn, extra), pn), ensure_ascii=False))
