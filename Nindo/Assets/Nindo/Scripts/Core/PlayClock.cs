using UnityEngine;

namespace Nindo
{
    /// <summary>
    /// El reloj de la partida, para medir la hora de juego que pide el diseño (hoy ~30 min). Suma a SaveData.playTime el
    /// tiempo real que no está en pausa ni en el mapa (antes sumaba todo, también la pausa abierta, y nadie lo mostraba).
    /// Deja en la consola cuánto se estuvo en cada zona al cambiar (Zone.Current) y cuánto llevó ganarle a cada jefe desde
    /// su primera pelea en esta sesión, con las muertes del medio: lo que hace falta para balancear con "bot on bueno" /
    /// "bot on promedio" sin cronómetro. El cartel del final muestra el total (UIManager.ShowEnding).
    /// </summary>
    public static class PlayClock
    {
        static Zone zone;
        static float zoneSince;
        static Boss boss;
        static float bossSince;
        static int bossDeaths;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]
        static void ResetStatics() { zone = null; boss = null; bossDeaths = 0; }

        /// <summary>Lo llama GameBootstrap cada cuadro.</summary>
        public static void Tick(float unscaledDt)
        {
            if (Game.Save == null || Game.IsPaused) return;
            Game.Save.playTime += unscaledDt;
        }

        public static void Attach()
        {
            GameEvents.ZoneEntered += OnZone;
            GameEvents.BossStarted += OnBossStarted;
            GameEvents.BossDefeated += OnBossDefeated;
            GameEvents.PlayerDied += OnPlayerDied;
        }

        public static void Detach()
        {
            GameEvents.ZoneEntered -= OnZone;
            GameEvents.BossStarted -= OnBossStarted;
            GameEvents.BossDefeated -= OnBossDefeated;
            GameEvents.PlayerDied -= OnPlayerDied;
            zone = null;
            boss = null;
        }

        static float Now => Game.Save != null ? Game.Save.playTime : 0f;

        static void OnZone(Zone z)
        {
            if (z == zone) return;
            if (zone != null) Debug.Log($"[Nindo] Tiempo de juego {Clock(Now)}: {Clock(Now - zoneSince)} en {zone.id}, entra a {z.id}");
            zone = z;
            zoneSince = Now;
        }

        // la pelea cuenta desde la primera presentación hasta la derrota, con los reintentos (lo que el diseño mide)
        static void OnBossStarted(Boss b)
        {
            if (b == boss) return;
            boss = b;
            bossSince = Now;
            bossDeaths = 0;
        }

        static void OnPlayerDied()
        {
            if (boss != null && boss.Fighting) bossDeaths++;
        }

        static void OnBossDefeated(Boss b)
        {
            if (b != boss) return;
#if UNITY_EDITOR || DEVELOPMENT_BUILD
            string bot = AutoPilot.Bot ? $" (bot {AutoPilot.SkillName})" : "";
#else
            const string bot = "";
#endif
            Debug.Log($"[Nindo] {b.title} vencido en {Clock(Now - bossSince)} con {bossDeaths} muertes{bot}; tiempo de juego {Clock(Now)}");
            boss = null;
        }

        /// <summary>h:mm:ss (o m:ss) para la consola.</summary>
        public static string Clock(float seconds)
        {
            int s = Mathf.Max(0, Mathf.FloorToInt(seconds));
            return s >= 3600 ? $"{s / 3600}:{s / 60 % 60:00}:{s % 60:00}" : $"{s / 60}:{s % 60:00}";
        }

        /// <summary>Para el cartel del final: "58 min" o "1 h 04 min".</summary>
        public static string Spoken(float seconds)
        {
            int m = Mathf.Max(1, Mathf.RoundToInt(seconds / 60f));
            return m >= 60 ? $"{m / 60} h {m % 60:00} min" : $"{m} min";
        }
    }
}
