"""El factor real/simulado de cada jefe: cuánto más (o menos) tarda en Unity el bot de AutoPilot que el mismo bot en la
simulación. Es lo que pasa la pelea simulada a minutos de juego.

Medido el 13 de octubre de 2026 en el editor, con main 76be027 (la fase C2), una pelea por bot (Core/PlayClock:
'[Nindo] <jefe> vencido en m:ss con N muertes (bot ...)', en el Editor.log), contra las simulaciones de ese mismo código
(las de 76be027, con las perillas de entonces):
  * Gorō      goro_fight_sim.py --runs 400 (barras 1000 + 1600, daño x0.5 / x0.4, tramo 25);
  * Mizuchi   mz_run.py fix bueno,promedio 300 '{"hp": 2160, "dmg": [0.35, 0.385, 0.385], "retry": true}';
  * Kokuyō    kk_fix_run.py largo 2700 0.4 40 bueno,promedio 300;
  * Chikuō    sim_bamboo_master.py --runs 200 --seed 3 (2000 de vida, los rebotes de C2).
El factor sale del bot "bueno": su pelea casi no varía (p10-p90 de ±8 % en las cuatro simulaciones), así que una pelea ya
lo mide. La del "promedio" depende de las muertes: una sola no separa la suerte del error del modelo, y queda de control.

Cómo se usa (--calib en sim_bamboo_master.py, '{"calib": true}' en mz_run.py y kk_fix_run.py): el daño de Kaito va a 1/F.
Es el error que mejor explica lo medido: con Gorō el bot real le pega más que el modelo (se le pega a la cápsula y le
corta las vueltas a la guardia: F 0.71) y con Chikuō menos (F 1.42: en Unity ronda más y lo agarran más, 24 golpes contra
12.5 simulados en la pelea del bueno). Con ese daño, la simulación de C2 reproduce el tiempo del bueno y predice al
promedio así (lo medido entre paréntesis):
  * Chikuō    758 s (p90 1107) y 3.1 muertes, 0 % sin morir    (950 s y 4 muertes)
  * Kokuyō    4.96 min (p10 2.0) y 2.2 muertes, 30 % sin morir  (2.43 min y 0 muertes)
  * Mizuchi   7.09 min (p10 4.3) y 3.3 muertes                  (3.45 min y 1 muerte: el promedio de verdad anduvo mejor
                                                                 que el modelo; con Mizuchi el promedio calibrado es pesimista)
goro_fight_sim.py usa el mismo dato a su manera (REAL_PER_SIM: el tiempo y las muertes después de simular).

Medir de nuevo: 'bot on bueno' y 'bot on promedio' tres veces por jefe con las partidas de Docs/handoff/partidas
(prueba_goro, prueba_mizuchi, prueba_bambu, prueba_kokuyo), pegar acá las líneas del PlayClock (en segundos) y las
simulaciones de ese mismo código, y el factor se actualiza solo. Con el código de c3/integration (después de la ronda
de huecos), la simulación cruda del bueno da (mediana): Gorō 366 s (goro_fight_sim --runs 400), Mizuchi 232 s (mz_run
tuning), Kokuyō 283 s (kk_fix_run largo), Chikuō 203 s (sim_bamboo_master --seed 3); y lo que se espera ver en Unity con
los factores de hoy: el bueno 4.3 / 4.5 / 4.4 / 4.6 min, el promedio 6.5 / 7.3 / 6.9 / 7.3 min con ~1.6 / 1.25 / 1.4 / 1
muertes.

Medido después en Unity (13 de octubre, la fase C3 integrada, e085ad8; una pelea por bot): Gorō bueno 259 s y promedio 311 s,
Mizuchi 209 s y 301 s, Kokuyō 281 s y 389 s, los seis sin morir. Contra esas simulaciones crudas el factor del bueno queda
Gorō 0.71 (igual), Mizuchi 0.90 y Kokuyō 0.99, y el promedio de verdad muere bastante menos que el calibrado con los cuatro
jefes (las curas por tramo y por postura lo sostienen). Con eso se subió el daño de los tres y la vida de Mizuchi y Kokuyō
(GoroBoss, MizuchiBoss.Pacing, KokuyoMoves).
"""

# jefe: el bot bueno y el promedio en Unity (segundos del PlayClock, muertes) y la simulación del mismo código (segundos:
# mediana del bueno; mediana del promedio con sus muertes medias)
MEASURED = {
    "goro": dict(real_bueno=[(144, 0)], real_promedio=[(244, 2)], sim_bueno=204.0, sim_promedio=(288.0, 1.45)),
    "mizuchi": dict(real_bueno=[(169, 0)], real_promedio=[(207, 1)], sim_bueno=142.2, sim_promedio=(307.2, 2.02)),
    "kokuyo": dict(real_bueno=[(108, 0)], real_promedio=[(146, 0)], sim_bueno=117.6, sim_promedio=(363.6, 3.23)),
    "chikuo": dict(real_bueno=[(361, 0)], real_promedio=[(950, 4)], sim_bueno=254.0, sim_promedio=(400.0, 1.00)),
}


def factor(boss):
    """Tiempo real / simulado del bot bueno (la media de lo medido)."""
    m = MEASURED[boss]
    real = sum(t for t, _ in m["real_bueno"]) / len(m["real_bueno"])
    return real / m["sim_bueno"]


def damage_mul(boss):
    """El daño de Kaito en la simulación calibrada: 1/F."""
    return 1.0 / factor(boss)


if __name__ == "__main__":
    for b in MEASURED:
        print("%-8s F = %.2f (daño de Kaito x%.2f)" % (b, factor(b), damage_mul(b)))
