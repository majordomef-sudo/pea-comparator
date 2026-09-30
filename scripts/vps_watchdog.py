#!/usr/bin/env python3
"""
🐶 VPS Watchdog — Alerte proactive inspirée de Netdata
Tourne toutes les 15-30 min. Alerte Telegram si seuil critique.

Seuils déclenchant une alerte :
  🔴 CPU > 80% (load / n_cpus)
  🔴 RAM < 500 MB libre
  🔴 Disk > 88% utilisé
  🔴 Service critique down (Memory backend, OpenClaw)
  ⚠️  Processus anormal (ffmpeg zombie, OOM imminent)
"""

import os, sys, subprocess, json, time, sqlite3
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw/workspace"
STATE_DIR = WORKSPACE / "state"
ALERT_LOG = STATE_DIR / "watchdog_alerts.json"

# ── SEUILS ────────────────────────────────────────────────────────
THRESHOLDS = {
    "cpu_pct": 80,        # % CPU utilisé (load / n_cores)
    "ram_free_mb": 500,   # RAM libre minimale (MB)
    "disk_pct": 88,       # % disque utilisé max
    "swap_pct": 50,       # % swap utilisé max
}

ALERT_COOLDOWN_SEC = 3600  # Pas de doublon avant 1h

# ── SERVICES À MONITORER ──────────────────────────────────────────
SERVICES = {
    "nocturne_memory": {"cmd": ["curl", "-sf", "-o", "/dev/null", "http://127.0.0.1:8898/health"], "label": "🧠 Nocturne Memory"},
}

# ── PROCESSUS CRITIQUES ───────────────────────────────────────────
CRITICAL_PROCS = {
    "openclaw": {"alert": "🔴 OpenClaw down !"},
    "python3": {"min": 1, "alert": "⚠️ Aucun process Python actif (anormal)"},
    "ffmpeg": {"alert": None},  # Info seulement
}


def _run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except:
        return -1, "", "timeout/error"


def get_system_metrics() -> dict:
    """Snapshot complet du système."""
    metrics = {}
    
    # CPU load (normalisé par nombre de cores)
    rc, out, _ = _run(["nproc"])
    n_cores = int(out.strip() or 1)
    rc, out, _ = _run(["cat", "/proc/loadavg"])
    load_parts = out.split()
    load_1m = float(load_parts[0]) if load_parts else 0
    cpu_pct = round((load_1m / n_cores) * 100, 1)
    
    # RAM
    rc, out, _ = _run(["free", "-m"])
    lines = out.split("\n")
    if len(lines) > 1:
        parts = lines[1].split()
        ram_total = int(parts[1])
        ram_used = int(parts[2])
        ram_free = int(parts[3])
        ram_avail = int(parts[6]) if len(parts) > 6 else ram_free
    else:
        ram_total = ram_used = ram_avail = 0
    
    # Swap
    if len(lines) > 2:
        swap_parts = lines[2].split()
        swap_total = int(swap_parts[1])
        swap_used = int(swap_parts[2])
        swap_pct = round((swap_used / swap_total) * 100, 1) if swap_total else 0
    else:
        swap_total = swap_used = swap_pct = 0
    
    # Disk
    rc, out, _ = _run(["df", "-h", "/"])
    df_lines = out.split("\n")
    if len(df_lines) > 1:
        cols = df_lines[1].split()
        disk_pct = int(cols[4].rstrip("%"))
        disk_used = cols[2]
        disk_total = cols[3]
    else:
        disk_pct = disk_used = disk_total = 0
    
    # Uptime
    rc, out, _ = _run(["uptime", "-p"])
    uptime = out or "?"
    
    # Top CPU consumers
    rc, out, _ = _run(["ps", "aux", "--sort=-%cpu", "--no-headers"], 10)
    top_cpu_procs = []
    for line in out.split("\n")[:5]:
        parts = line.split()
        if len(parts) >= 11:
            top_cpu_procs.append({
                "user": parts[0],
                "cpu": parts[2],
                "mem": parts[3],
                "cmd": " ".join(parts[10:])[:60],
            })
    
    # Top RAM consumers
    rc, out, _ = _run(["ps", "aux", "--sort=-%mem", "--no-headers"], 10)
    top_mem_procs = []
    for line in out.split("\n")[:5]:
        parts = line.split()
        if len(parts) >= 11:
            top_mem_procs.append({
                "user": parts[0],
                "cpu": parts[2],
                "mem": parts[3],
                "cmd": " ".join(parts[10:])[:60],
            })
    
    metrics.update({
        "ts": datetime.now().isoformat(),
        "cpu_pct": cpu_pct,
        "load_1m": load_1m,
        "n_cores": n_cores,
        "ram_total_mb": ram_total,
        "ram_used_mb": ram_used,
        "ram_free_mb": ram_free,
        "ram_avail_mb": ram_avail,
        "ram_pct": round((ram_used / ram_total) * 100, 1) if ram_total else 0,
        "swap_pct": swap_pct,
        "disk_pct": disk_pct,
        "disk_used": disk_used,
        "disk_total": disk_total,
        "uptime": uptime,
        "top_cpu": top_cpu_procs,
        "top_mem": top_mem_procs,
    })
    
    return metrics


def check_services() -> list:
    """Vérifie les services critiques et retourne les alertes."""
    alerts = []
    for name, svc in SERVICES.items():
        rc, _, _ = _run(svc["cmd"])
        if rc != 0:
            alerts.append(f"{svc['label']} — DOWN")
    return alerts


def check_processes(metrics: dict) -> list:
    """Analyse les processus et retourne les anomalies."""
    alerts = []
    ps_list = metrics.get("top_cpu", [])
    all_cmds = [p["cmd"] for p in ps_list]
    
    # Vérifier les processus critiques
    rc, _, _ = _run(["pgrep", "-f", "openclaw.*gateway"], 5)
    openclaw_running = rc == 0
    python_running = any("python3" in c.lower() or "python" in c.lower() for c in all_cmds)
    
    if not openclaw_running:
        alerts.append("🔴 OpenClaw — aucun process trouvé")
    if not python_running:
        alerts.append("⚠️ Aucun process Python — normal si idle, sinon suspect")
    
    # Alerte si ffmpeg consomme trop (encodage qui dérape)
    for p in ps_list:
        if "ffmpeg" in p["cmd"].lower() and float(p["cpu"]) > 200:
            alerts.append(f"⚠️ ffmpeg consomme {p['cpu']}% CPU — encodage lourd en cours")
    
    return list(set(alerts))


def check_auth() -> list:
    """Vérifie que les clés API OpenRouter sont présentes dans le SQLite store.
    Évite les blocages auth comme celui du 01/07/2026."""
    alerts = []
    sqlite_path = Path.home() / ".openclaw/agents/main/agent/openclaw-agent.sqlite"
    if not sqlite_path.exists():
        return ["⚠️ Store SQLite auth introuvable"]
    try:
        conn = sqlite3.connect(f"file:{sqlite_path}?mode=ro", uri=True)
        c = conn.cursor()
        rows = c.execute("SELECT store_json FROM auth_profile_store").fetchall()
        conn.close()
        found = False
        for (store_json,) in rows:
            d = json.loads(store_json)
            for name, profile in d.get("profiles", {}).items():
                if profile.get("provider") == "openrouter" and profile.get("key"):
                    found = True
        if not found:
            alerts.append("🔴 Clé API OpenRouter absente du SQLite store !")
            alerts.append("   ➡ Exécuter: python3 scripts/ensure_auth.py --fix")
    except Exception as e:
        alerts.append(f"⚠️ Impossible de vérifier l'auth SQLite: {e}")
    return alerts


def check_thresholds(metrics: dict) -> list:
    """Vérifie les seuils critiques et retourne les alertes."""
    alerts = []
    
    if metrics["cpu_pct"] > THRESHOLDS["cpu_pct"]:
        alerts.append(f"🔴 CPU à {metrics['cpu_pct']}% (seuil: {THRESHOLDS['cpu_pct']}%)")
        # Ajouter les top consommateurs
        top = metrics.get("top_cpu", [])
        if top:
            procs = ", ".join(f"{p['cmd']} ({p['cpu']}%)" for p in top[:3])
            alerts.append(f"   Top CPU: {procs}")
    
    if metrics["ram_avail_mb"] < THRESHOLDS["ram_free_mb"]:
        alerts.append(f"🔴 RAM disponible: {metrics['ram_avail_mb']} MB (seuil: {THRESHOLDS['ram_free_mb']} MB)")
        top = metrics.get("top_mem", [])
        if top:
            procs = ", ".join(f"{p['cmd']} ({p['mem']}%)" for p in top[:3])
            alerts.append(f"   Top RAM: {procs}")
    
    if metrics["disk_pct"] > THRESHOLDS["disk_pct"]:
        alerts.append(f"🔴 Disque à {metrics['disk_pct']}% (seuil: {THRESHOLDS['disk_pct']}%)")
    
    if metrics.get("swap_pct", 0) > THRESHOLDS["swap_pct"] and metrics.get("ram_avail_mb", 0) < 1000:
        alerts.append(f"⚠️ Swap à {metrics['swap_pct']}% — RAM sous pression")
    
    return alerts


def alert_cooldown_key(alert: str) -> str:
    """Retourne une clé stable indépendante des valeurs mesurées."""
    categories = {"🔴 CPU à": "cpu_high", "   Top CPU:": "cpu_top", "🔴 RAM disponible:": "ram_low", "   Top RAM:": "ram_top", "🔴 Disque à": "disk_high", "⚠️ Swap à": "swap_high", "🔴 OpenClaw": "openclaw_down", "⚠️ Aucun process Python": "python_missing", "⚠️ ffmpeg consomme": "ffmpeg_high"}
    for prefix, key in categories.items():
        if alert.startswith(prefix):
            return key
    return alert[:60]


def was_alerted_recently(alert_key: str) -> bool:
    """Vérifie le cooldown pour éviter les doublons."""
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if ALERT_LOG.exists():
        try:
            log = json.loads(ALERT_LOG.read_text())
            last_ts = log.get("last_alerts", {}).get(alert_key)
            if last_ts:
                elapsed = time.time() - last_ts
                if elapsed < ALERT_COOLDOWN_SEC:
                    return True
        except:
            pass
    return False


def mark_alerted(alert_key: str):
    """Enregistre le timestamp d'une alerte."""
    ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    log = {"last_alerts": {}}
    if ALERT_LOG.exists():
        try:
            log = json.loads(ALERT_LOG.read_text())
        except:
            pass
    log["last_alerts"][alert_key] = time.time()
    log["last_run"] = time.time()
    log["last_metrics"] = {
        "cpu_pct": "?",
        "ram_avail_mb": "?",
        "disk_pct": "?",
    }
    ALERT_LOG.write_text(json.dumps(log, indent=2))


def save_snapshot(metrics: dict):
    """Sauvegarde le snapshot dans l'historique."""
    # Ajouter à maintenance_history.json
    hist_file = STATE_DIR / "maintenance_history.json"
    hist = {"dates": [], "cpu_pct": [], "ram_pct": [], "disk_pct": [], "load": []}
    if hist_file.exists():
        try:
            hist = json.loads(hist_file.read_text())
        except:
            pass
    
    today = datetime.now().strftime("%Y-%m-%d")
    # Snapshots par heure dans le même jour
    hour_key = f"{today}T{datetime.now().hour:02d}"
    
    if hist["dates"] and hist["dates"][-1] == hour_key:
        hist["cpu_pct"][-1] = metrics["cpu_pct"]
        hist["ram_pct"][-1] = metrics["ram_pct"]
        hist["disk_pct"][-1] = metrics["disk_pct"]
        hist["load"][-1] = metrics["load_1m"]
    else:
        hist["dates"].append(hour_key)
        hist.setdefault("cpu_pct", []).append(metrics["cpu_pct"])
        hist.setdefault("ram_pct", []).append(metrics["ram_pct"])
        hist.setdefault("disk_pct", []).append(metrics["disk_pct"])
        hist.setdefault("load", []).append(metrics["load_1m"])
    
    # Garder 7 jours de données
    max_entries = 7 * 24  # 1 snapshot/h → 168 max
    for key in ("dates", "cpu_pct", "ram_pct", "disk_pct", "load"):
        hist[key] = hist[key][-max_entries:]
    
    hist_file.write_text(json.dumps(hist, indent=2))


def format_alert_message(alerts: list, metrics: dict) -> str:
    """Formate un message Telegram pour les alertes."""
    lines = ["🚨 *Watchdog — Alerte VPS*", ""]
    lines.append(f"📊 {datetime.now().strftime('%d/%m %H:%M')} UTC")
    lines.append("")
    
    for a in alerts:
        lines.append(a)
    
    lines.append("")
    lines.append(f"CPU: {metrics['cpu_pct']}% | RAM: {metrics['ram_avail_mb']}MB libre | Disk: {metrics['disk_pct']}%")
    
    if metrics.get("top_cpu"):
        lines.append("")
        lines.append("🔥 Top CPU:")
        for p in metrics["top_cpu"][:3]:
            lines.append(f"  • {p['cmd']} — {p['cpu']}% CPU, {p['mem']}% RAM")
    
    return "\n".join(lines)


def run_watchdog(send_telegram: bool = False) -> dict:
    """Tour complet du watchdog. Retourne le statut."""
    metrics = get_system_metrics()
    
    # Toutes les alertes potentielles
    threshold_alerts = check_thresholds(metrics)
    auth_alerts = check_auth()
    service_alerts = check_services()
    process_alerts = check_processes(metrics)
    
    all_alerts = threshold_alerts + auth_alerts + service_alerts + process_alerts
    
    # Sauvegarder le snapshot
    save_snapshot(metrics)
    
    # Filtrer par cooldown et envoyer
    new_alerts = []
    for alert in all_alerts:
        key = alert_cooldown_key(alert)
        if not was_alerted_recently(key):
            new_alerts.append(alert)

    if new_alerts and send_telegram:
        from notify_alfred import send_telegram as notify_telegram
        msg = format_alert_message(new_alerts, metrics)
        if notify_telegram(msg):
            for alert in new_alerts:
                mark_alerted(alert_cooldown_key(alert))
        else:
            alert_file = STATE_DIR / "watchdog_pending_alert.txt"
            alert_file.write_text(msg)

    return {
        "status": "alert" if new_alerts else "ok",
        "alerts": new_alerts,
        "metrics": {
            "cpu_pct": metrics["cpu_pct"],
            "ram_avail_mb": metrics["ram_avail_mb"],
            "ram_pct": metrics["ram_pct"],
            "disk_pct": metrics["disk_pct"],
            "load": metrics["load_1m"],
        },
        "top_cpu": [p["cmd"] for p in metrics.get("top_cpu", [])[:3]],
        "ts": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    send = "--no-send" not in sys.argv
    result = run_watchdog(send_telegram=send)
    print(json.dumps(result, indent=2, ensure_ascii=False))