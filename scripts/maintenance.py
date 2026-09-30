"""
Maintenance V2 — Automatisation complète du VPS
Inclut : nettoyage, updates, monitoring, tendances
"""
import os
import shutil
import time
import json
import subprocess
import fnmatch
from pathlib import Path
from datetime import datetime, timedelta

# ── CONFIGURATION ────────────────────────────────────────────────
WORKSPACE_ROOT = Path("/home/ubuntu/.openclaw/workspace")
ARCHIVE_DIR = WORKSPACE_ROOT / "archive"
LOGS_DIR = WORKSPACE_ROOT / "logs"
FAILURES_DIR = WORKSPACE_ROOT / "failures"
HISTORY_FILE = WORKSPACE_ROOT / "state" / "maintenance_history.json"
STATE_DIR = WORKSPACE_ROOT / "state"

LOG_RETENTION_DAYS = 7
FAILURE_RETENTION_DAYS = 14
DISK_WARN_PCT = 20
TREND_HISTORY_DAYS = 7
CRITICAL_PIP_PACKAGES = [
    "beautifulsoup4", "requests", "pandas", "numpy",
    "scikit-learn", "scipy", "lxml", "matplotlib", "pillow"
]

# SECURITY: HUMAN-IN-THE-LOOP
# Commandes destructrices apt upgrade autoremove pip --upgrade 
SAFE_MODE = os.environ.get("MAINTENANCE_SAFE_MODE", "1") == "1"
JUNK_PATTERNS = [
    "rescue_*.py", "final_test_*.mp4", "rescue_test_*.mp4",
    "assembled_*.mp4", "test_*.mp4", "*.mp4",
]

CRITICAL_FILES = {"IDENTITY.md", "USER.md", "SOUL.md", "MEMORY.md",
                  "AGENTS.md", "TOOLS.md", "HEARTBEAT.md"}

# ── OUTPUT COLLECTOR ─────────────────────────────────────────────
_report_sections = []

def section(title):
    _report_sections.append(("section", title))

def ok(msg):
    _report_sections.append(("ok", msg))

def warn(msg):
    _report_sections.append(("warn", msg))

def err(msg):
    _report_sections.append(("err", msg))

def info(msg):
    _report_sections.append(("info", msg))

def _run(cmd, timeout=120):
    """Run a command, return (returncode, stdout, stderr)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except FileNotFoundError:
        return -1, "", "command not found"
    except subprocess.TimeoutExpired:
        return -2, "", "timeout"
    except PermissionError:
        return -3, "", "permission denied"

# ── CORE FUNCTIONS ───────────────────────────────────────────────

def is_junk(file_path):
    for pattern in JUNK_PATTERNS:
        if fnmatch.fnmatch(file_path.name, pattern):
            return True
    return False


def archive_file(file_path):
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    month_folder = ARCHIVE_DIR / datetime.now().strftime("%Y-%m")
    month_folder.mkdir(exist_ok=True)
    dest = month_folder / file_path.name
    if dest.exists():
        dest = month_folder / f"{int(time.time())}_{file_path.name}"
    shutil.move(str(file_path), str(dest))
    return dest


def load_history():
    """Charge l'historique des mesures VPS."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"disk_pct": [], "ram_pct": [], "load": [], "dates": []}


def save_history(disk_pct, ram_pct, load1):
    h = load_history()
    today = datetime.now().strftime("%Y-%m-%d")
    # Éviter les doublons du même jour
    if h["dates"] and h["dates"][-1] == today:
        h["disk_pct"][-1] = disk_pct
        h["ram_pct"][-1] = ram_pct
        h["load"][-1] = load1
    else:
        h["dates"].append(today)
        h["disk_pct"].append(disk_pct)
        h["ram_pct"].append(ram_pct)
        h["load"].append(load1)
    # Garder seulement TREND_HISTORY_DAYS
    for key in ("dates", "disk_pct", "ram_pct", "load"):
        h[key] = h[key][-TREND_HISTORY_DAYS:]
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w") as f:
        json.dump(h, f, indent=2)
    return h


def trend_icon(values):
    """↑ stable ↗ ↓ ou → selon tendance."""
    if len(values) < 2:
        return "→"
    diff = values[-1] - values[0]
    if diff > 5:
        return "⬆️"
    elif diff > 1:
        return "↗️"
    elif diff < -5:
        return "⬇️"
    elif diff < -1:
        return "↘️"
    else:
        return "➡️"


# ── CHECKS ────────────────────────────────────────────────────────

def check_system():
    section("🖥️ Système")
    # CPU / RAM / Disk
    rc, load_str, _ = _run(["cat", "/proc/loadavg"])
    load1 = float(load_str.split()[0]) if load_str else 0

    rc, mem_str, _ = _run(["free", "-m"])
    mem_lines = mem_str.split("\n")
    if len(mem_lines) > 1:
        parts = mem_lines[1].split()
        ram_total = int(parts[1])
        ram_used = int(parts[2])
        ram_pct = round(ram_used / ram_total * 100, 1) if ram_total else 0
    else:
        ram_total, ram_used, ram_pct = 0, 0, 0

    rc, df_str, _ = _run(["df", "-h", "/"])
    df_parts = df_str.split("\n")
    if len(df_parts) > 1:
        df_cols = df_parts[1].split()
        disk_pct = int(df_cols[4].rstrip("%"))
        disk_used = df_cols[2]
        disk_total = df_cols[3]
    else:
        disk_pct, disk_used, disk_total = 0, "?", "?"

    info(f"Load: {load1}  |  RAM: {ram_used}/{ram_total} MB ({ram_pct}%)  |  Disk: {disk_used}/{disk_total} ({disk_pct}%)")

    # Alerte disque (seuil sur espace libre)
    free_pct = 100 - disk_pct
    if free_pct > DISK_WARN_PCT:
        ok(f"Disque {disk_pct}% utilisé — {free_pct}% libre")
    else:
        err(f"⚠️ Disque à {disk_pct}% — seulement {free_pct}% libre (seuil {DISK_WARN_PCT}%)!")

    # Tendances
    h = save_history(disk_pct, ram_pct, load1)
    if len(h["dates"]) >= 2:
        info(f"Tendance disque {trend_icon(h['disk_pct'])}  RAM {trend_icon(h['ram_pct'])}  Load {trend_icon(h['load'])} (sur {len(h['dates'])} jours)")
    
    return {"disk_pct": disk_pct, "ram_pct": ram_pct, "load1": load1}


def check_disk():
    section("🧹 Nettoyage")
    # Junk
    junk_count = 0
    for item in WORKSPACE_ROOT.iterdir():
        if item.is_file() and is_junk(item) and item.name not in CRITICAL_FILES:
            archive_file(item)
            junk_count += 1
    if junk_count:
        ok(f"{junk_count} fichier(s) indésirable(s) archivé(s)")
    else:
        ok("Aucun fichier indésirable")

    # Logs
    removed_logs = 0
    if LOGS_DIR.exists():
        now = time.time()
        for log_file in LOGS_DIR.iterdir():
            if log_file.is_file() and (now - log_file.stat().st_mtime) > (LOG_RETENTION_DAYS * 86400):
                log_file.unlink()
                removed_logs += 1
    if removed_logs:
        ok(f"{removed_logs} vieux log(s) supprimé(s)")
    else:
        ok("Logs OK")

    # Failures
    removed_fails = 0
    if FAILURES_DIR.exists():
        now = time.time()
        for fail_dir in FAILURES_DIR.iterdir():
            if fail_dir.is_dir() and (now - fail_dir.stat().st_mtime) > (FAILURE_RETENTION_DAYS * 86400):
                shutil.rmtree(fail_dir)
                removed_fails += 1
    if removed_fails:
        ok(f"{removed_fails} vieux rapport(s) d'échec supprimé(s)")


def check_updates():
    """Verifie les mises a jour. SAFE_MODE=True=desactive les mises a jour automatiques."""
    section("📦 Mises à jour")

    if SAFE_MODE:
        info("SAFE_MODE actif — mises à jour automatiques désactivées")
        return

    # apt
    rc, _, _ = _run(["sudo", "apt", "update"], 120)
    if rc == 0:
        ok("apt update OK")
    else:
        warn("apt update a échoué")

    rc, out, _ = _run(["sudo", "apt", "upgrade", "-y"], 300)
    if rc == 0:
        # Compter les upgrades
        upgrades = [l for l in out.split("\n") if l.strip().startswith("Mise à niveau") or "upgraded" in l.lower()]
        ok(f"apt upgrade OK ({len(upgrades)} paquets)" if upgrades else "apt — déjà à jour")
    else:
        warn("apt upgrade a échoué")

    # autoremove
    rc, out, _ = _run(["sudo", "apt", "autoremove", "-y"], 60)
    removed = 0
    for line in out.split("\n"):
        if "Suppression de" in line or "Removing" in line:
            removed += 1
    if removed:
        ok(f"{removed} paquet(s) orphelin(s) supprimé(s)")
    else:
        ok("Aucun paquet orphelin")

    # pip
    rc, out, _ = _run(["pip3", "list", "--outdated", "--format=columns", "--break-system-packages"], 30)
    outdated_lines = [l for l in out.split("\n") if l.strip()][2:]  # skip header
    outdated_packages = [l.split()[0] for l in outdated_lines if l.split()]

    if not outdated_packages:
        ok("pip — tous à jour")
    else:
        # Mettre à jour les packages critiques
        to_upgrade = [p for p in CRITICAL_PIP_PACKAGES if p in outdated_packages]
        if to_upgrade:
            pip_cmd = ["pip3", "install", "--upgrade", "--break-system-packages"] + to_upgrade
            rc, pip_out, _ = _run(pip_cmd, 180)
            upgraded = [l.split()[-1] for l in pip_out.split("\n") if "Successfully installed" in l]
            ok(f"pip — {len(to_upgrade)} critique(s) mis à jour")
            outdated_packages = [p for p in outdated_packages if p not in to_upgrade]
        
        if outdated_packages:
            warn(f"{len(outdated_packages)} package(s) pip obsolète(s) restant(s)")

    # npm
    rc, _, _ = _run(["npm", "--version"], 10)
    if rc == 0:
        rc, out, _ = _run(["npm", "update", "-g"], 120)
        if rc == 0:
            ok("npm — à jour")
        else:
            warn("npm update a planté")
    else:
        info("npm — non installé, ignoré")

    # OpenClaw version
    rc, ver, _ = _run(["openclaw", "--version"], 10)
    if rc == 0:
        info(f"OpenClaw {ver}")


def check_certificates():
    section("🔒 Certificats SSL")
    rc, out, _ = _run(["which", "certbot"], 5)
    if rc != 0:
        info("certbot non installé — ignoré")
        return

    rc, out, _ = _run(["sudo", "certbot", "certificates"], 15)
    if rc != 0:
        warn("Impossible de lister les certificats")
        return

    # Extraire les dates d'expiration
    certs = []
    for line in out.split("\n"):
        if "Expiry Date:" in line or "Date d'expiration" in line:
            date_part = line.split(":", 1)[-1].strip()
            certs.append(date_part)
    
    if not certs:
        info("Aucun certificat actif")
    else:
        for c in certs:
            # Extraire la date avant " (VALID" ou " ("
            try:
                date_str = c.split(" (VALID")[0].split(" (")[0].split("+")[0].strip()
                matched = False
                for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                    try:
                        expiry = datetime.strptime(date_str, fmt)
                        matched = True
                        break
                    except:
                        continue
                if not matched:
                    info(f"Certificat: {c[:50]}...")
                    continue
                days_left = (expiry - datetime.now()).days
                if days_left < 0:
                    err(f"⚠️ Certificat expiré depuis {-days_left} jours!")
                elif days_left < 15:
                    err(f"⚠️ Certificat expire dans {days_left} jours!")
                elif days_left < 30:
                    warn(f"Certificat expire dans {days_left} jours")
                else:
                    ok(f"Certificat OK — expire dans {days_left} jours")
            except Exception as e:
                info(f"Certificat: {c[:60]}...")


def check_pipelines():
    section("⚙️ Pipelines")

    # Vérifier via les jobs cron OpenClaw
    pipelines = {
        "🎬 Pipeline vidéo": "nightly_orchestrator",
        "🧬 Euromillions": "euromillions",
        "📊 Rapport matinal": "matinal",
    }

    rc, out, _ = _run(["crontab", "-l"], 10)
    if rc != 0:
        warn("Impossible de lire crontab")
        return

    crontab = out

    for label, keyword in pipelines.items():
        if keyword.lower() in crontab.lower():
            ok(f"{label} — cron présent")
        elif keyword == "nightly_orchestrator":
            info(f"{label} — géré par OpenClaw Cron")  # Pas dans crontab système
        else:
            warn(f"{label} — cron introuvable!")

    # Vérifier les jobs OpenClaw internes
    # On liste les derniers enregistrements de prédictions
    predictions_log = WORKSPACE_ROOT / "euromillions" / "predictions_log.json"
    if predictions_log.exists():
        try:
            with open(predictions_log) as f:
                log = json.load(f)
            last_pred = max(log.keys()) if isinstance(log, dict) else "?"
            info(f"Dernière prédiction Euromillions : {last_pred}")
        except:
            pass


def full_report():
    """Génère un rapport structuré pour Telegram/Markdown."""
    lines = []
    current_section = ""
    emoji_map = {"ok": "✅", "warn": "⚠️", "err": "🔴", "info": "ℹ️"}

    for kind, msg in _report_sections:
        if kind == "section":
            current_section = msg
            lines.append(f"\n{msg}")
        elif kind in emoji_map:
            lines.append(f"  {emoji_map[kind]} {msg}")
        else:
            lines.append(f"  {msg}")

    errors = [m for k, m in _report_sections if k == "err"]
    warns = [m for k, m in _report_sections if k == "warn"]

    header = "📋 *Rapport de maintenance* — " + datetime.now().strftime("%d/%m/%Y %H:%M UTC")
    
    if errors:
        header += f"\n🔴 {len(errors)} alerte(s)"
    if warns:
        header += f"\n⚠️ {len(warns)} avertissement(s)"

    lines.insert(0, header)
    lines.append("")
    lines.append("───")
    lines.append(f"_Maintenance V2 • {datetime.now().strftime('%d/%m/%Y %H:%M')}_")

    return "\n".join(lines)


# ── MAIN ──────────────────────────────────────────────────────────

def run_maintenance():
    print(f"--- Maintenance V2 — {datetime.now()} ---\n")

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    check_system()
    check_disk()
    check_updates()
    check_certificates()
    check_pipelines()

    report = full_report()
    print(report)

    # Sauvegarde du rapport
    report_path = WORKSPACE_ROOT / "logs" / f"maintenance_{datetime.now().strftime('%Y%m%d_%H%M')}.log"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        f.write(report)

    return report


if __name__ == "__main__":
    run_maintenance()