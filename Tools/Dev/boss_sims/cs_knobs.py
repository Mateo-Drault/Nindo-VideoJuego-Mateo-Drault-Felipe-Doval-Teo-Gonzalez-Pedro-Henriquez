"""Las perillas del balance de Kokuyō y Mizuchi leídas del C# (una sola fuente por jefe: KokuyoMoves, KokuyoBoss y
MizuchiBoss.Pacing). Si el lead las cambia en Unity después de correr el bot, las simulaciones simulan lo mismo; si un
nombre desaparece o cambia de forma, falla fuerte en vez de simular números viejos."""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "Nindo", "Assets", "Nindo", "Scripts"))


def _src(rel):
    path = os.path.join(SCRIPTS, *rel.split("/"))
    with open(path, encoding="utf-8") as f:
        # sin comentarios: los números de las tablas de los <summary> no se confunden con los de verdad
        return re.sub(r"//[^\n]*", "", f.read())


def _num(src, rel, name):
    m = re.search(r"\b%s\s*=\s*(-?[0-9]+(?:\.[0-9]+)?)f?\b" % re.escape(name), src)
    if not m:
        raise SystemExit("cs_knobs: no encontré '%s' en %s" % (name, rel))
    return float(m.group(1))


def _arr(src, rel, name):
    m = re.search(r"\b%s\s*=\s*\{([^}]*)\}" % re.escape(name), src)
    if not m:
        raise SystemExit("cs_knobs: no encontré el arreglo '%s' en %s" % (name, rel))
    return [float(x.strip().rstrip("f")) for x in m.group(1).split(",") if x.strip()]


def _pat(src, rel, pattern, what):
    m = re.search(pattern, src)
    if not m:
        raise SystemExit("cs_knobs: no encontré %s en %s" % (what, rel))
    return float(m.group(1))


def kokuyo():
    moves, boss, shadow = "Enemies/Bosses/KokuyoMoves.cs", "Enemies/Bosses/KokuyoBoss.cs", "Enemies/Bosses/KokuyoBoss.Shadow.cs"
    m, b, s = _src(moves), _src(boss), _src(shadow)
    base = _pat(m, moves, r"maxHealth\s*=\s*([0-9.]+)\s*\*\s*HealthScale", "la vida base (maxHealth = N * HealthScale)")
    return {
        "hp": base * _num(m, moves, "HealthScale"),
        "dmg_mul": _num(m, moves, "DamageScale"),
        "heal": _num(m, moves, "TransitionHeal"),
        "spirit": _num(m, moves, "TransitionSpirit"),
        "stage_heal": _arr(m, moves, "StageHeal"),
        "gates": _arr(b, boss, "Gates"),
        "kneel_first": _num(b, boss, "KneelThresholdFirst"),
        "kneel_need_n": _num(b, boss, "KneelThreshold"),
        "encore": _num(s, shadow, "EncoreChance"),
        "encore_window": _num(s, shadow, "EncoreWindow"),
        "turn_chance": _arr(s, shadow, "TurnChance"),
        "turn_min_gap": _arr(s, shadow, "TurnMinGap"),
        "max_quiet": _arr(s, shadow, "MaxQuiet"),
        "first_turn": _arr(s, shadow, "FirstTurnAfter"),
    }


def mizuchi():
    pacing, arche, boss = "Enemies/Bosses/MizuchiBoss.Pacing.cs", "Enemies/EnemyArchetypes.cs", "Enemies/Bosses/MizuchiBoss.cs"
    p, a, b = _src(pacing), _src(arche), _src(boss)
    base = _pat(a, arche, r"maxHealth\s*=\s*([0-9.]+)\s*\*\s*MizuchiBoss\.HealthScale", "la vida base de Mizuchi")
    corrupt = _pat(b, boss, r"void CorruptedStats\(\)[^}]*?ScaleSteps\(\s*([0-9.]+)f", "el daño corrompido (ScaleSteps)")
    ds = _num(p, pacing, "DamageScale")
    ps = _num(p, pacing, "PhaseSpirit")
    return {
        "hp": base * _num(p, pacing, "HealthScale"),
        "dmg": [ds, ds * corrupt, ds * corrupt],
        "posture_heal": _num(p, pacing, "PostureHeal"),
        "heal": _arr(p, pacing, "PhaseHeal"),
        "heal_spirit": [0.0, ps, ps],
    }


if __name__ == "__main__":
    import json
    print(json.dumps({"kokuyo": kokuyo(), "mizuchi": mizuchi()}, ensure_ascii=False, indent=1))
