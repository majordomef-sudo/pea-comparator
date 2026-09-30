#!/usr/bin/env python3
"""Revenue Audit V3 — métriques réelles, format Telegram direct, zéro fuite LaTeX."""
import json, os, subprocess, sys, time, gzip, glob, fcntl
from datetime import date, datetime, timedelta

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from notify_alfred import send_telegram

LOCKFILE = "/tmp/revenue_audit.lock"
try:
    lock_fd = open(LOCKFILE, "w")
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except (IOError, BlockingIOError) as e:
    print(f"skip revenue_audit ({e})")
    sys.exit(0)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

def run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip() or r.stderr.strip()
    except subprocess.TimeoutExpired:
        return "TIMEOUT"
    except Exception as e:
        return str(e)

def curl_status(url):
    r = run(f'curl -sL -o /dev/null -w "%{{http_code}}" "{url}" --max-time 8', timeout=10)
    return r if r.isdigit() else "ERR"

# ─── TRAFIC (nginx logs) ─────────────────────────────────

def get_traffic_stats():
    """Parse nginx access logs pour visites 24h et 7j."""
    now = datetime.now()
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)

    hits_24h = 0
    ips_24h = set()
    hits_7d = 0
    ips_7d = set()
    pages_24h = {}

    log_files = ["/var/log/nginx/access.log", "/var/log/nginx/access.log.1"]
    # Ajouter les logs gzippés pour le 7j
    for f in sorted(glob.glob("/var/log/nginx/access.log.*.gz")):
        log_files.append(f)

    for lf in log_files:
        try:
            if lf.endswith(".gz"):
                with gzip.open(lf, "rt", errors="ignore") as fh:
                    lines = fh.readlines()
            else:
                with open(lf, "r", errors="ignore") as fh:
                    lines = fh.readlines()
        except:
            continue

        for line in lines:
            parts = line.split()
            if len(parts) < 4:
                continue
            ip = parts[0]
            # Parse date
            try:
                ts_str = line.split("[")[1].split("]")[0] if "[" in line else ""
                ts = datetime.strptime(ts_str, "%d/%b/%Y:%H:%M:%S %z")
                ts = ts.replace(tzinfo=None)
            except:
                continue

            path = parts[6] if len(parts) > 6 else "-"
            code = parts[8] if len(parts) > 8 else "0"

            if ts >= cutoff_7d:
                hits_7d += 1
                ips_7d.add(ip)

            if ts >= cutoff_24h:
                hits_24h += 1
                ips_24h.add(ip)
                if code == "200" and not any(x in path for x in [".css", ".js", ".ico", ".png", ".jpg", ".woff", ".xml"]):
                    pages_24h[path] = pages_24h.get(path, 0) + 1

    top_pages = sorted(pages_24h.items(), key=lambda x: -x[1])[:5]
    top_str = " | ".join(f"{p} ({c})" for p, c in top_pages) if top_pages else "N/A"

    return {
        "hits_24h": hits_24h,
        "ips_24h": len(ips_24h),
        "hits_7d": hits_7d,
        "ips_7d": len(ips_7d),
        "top_pages": top_str,
    }

# ─── SITE ────────────────────────────────────────────────

def check_site():
    urls = [
        ("Accueil", "https://alfredstudio.mooo.com/"),
        ("Comparateur", "https://alfredstudio.mooo.com/pea-comparator/"),
        ("Blog", "https://alfredstudio.mooo.com/blog/"),
        ("A propos", "https://alfredstudio.mooo.com/blog/a-propos/"),
        ("Guide", "https://alfredstudio.mooo.com/guide/"),
    ]
    ok = 0
    failures = []
    for name, url in urls:
        code = curl_status(url)
        if code == "200":
            ok += 1
        else:
            failures.append(f"{name} ({code})")

    sitemap = curl_status("https://alfredstudio.mooo.com/sitemap.xml")
    sitemap_ok = sitemap == "200"

    status = "✅" if ok == len(urls) else ("⚠️" if ok >= 3 else "🔴")
    return {
        "status": status, "ok": ok, "total": len(urls),
        "failures": failures, "sitemap_ok": sitemap_ok
    }

# ─── YOUTUBE ─────────────────────────────────────────────

def check_youtube():
    result = run(
        "cd /home/ubuntu/.openclaw/workspace/skills/youtube_upload && source ~/.secrets/env 2>/dev/null; python3 stats.py 2>/dev/null",
        timeout=30
    )
    subs = "N/A"
    views = "N/A"
    vids = "N/A"
    last_title = "N/A"
    last_views = "N/A"
    last_likes = "N/A"

    lines = result.split("\n")
    for i, line in enumerate(lines):
        line = line.strip()
        if "Abonnés" in line:
            subs = line.split(":")[-1].strip()
        elif "Vues total" in line:
            views = line.split(":")[-1].strip()
        elif "Vidéos" in line:
            vids = line.split(":")[-1].strip()
        elif line.startswith("•") and last_title == "N/A":
            last_title = line.replace("•", "").strip()
            # Lire la ligne suivante: format "    �️ 3 vues | 👍 1 likes | ..."
            if i+1 < len(lines):
                detail = lines[i+1].strip()
                import re
                vue_match = re.search(r'([\d]+)\s*vue', detail)
                like_match = re.search(r'([\d]+)\s*like', detail)
                if vue_match:
                    last_views = vue_match.group(1)
                if like_match:
                    last_likes = like_match.group(1)

    # Vérifier dernier run pipeline
    orch = os.path.join(WORKSPACE, "skills/alfred_cron/nightly_orchestrator.py")
    pipeline_ok = os.path.exists(orch)
    last_orch = "N/A"
    if pipeline_ok:
        mtime = os.path.getmtime(orch)
        last_orch = datetime.fromtimestamp(mtime).strftime("%d/%m")

    # Vérifier cron pipeline YouTube
    cron_list = run("openclaw cron list 2>/dev/null", timeout=10)
    pipeline_cron = "veille-youtube" in cron_list or "youtube" in cron_list.lower()

    return {
        "subs": subs, "views": views, "vids": vids,
        "last_title": last_title, "last_views": last_views, "last_likes": last_likes,
        "pipeline_ok": pipeline_ok, "last_orch": last_orch, "pipeline_cron": pipeline_cron,
    }

# ─── BLOG GHOST ──────────────────────────────────────────

def check_ghost():
    """Vérifie le nombre d'articles publiés via scrape HTML + statut Docker."""
    # Scraper la page blog pour compter les articles
    posts_count = "N/A"
    try:
        html = run("curl -s 'https://alfredstudio.mooo.com/blog/' --max-time 8", timeout=10)
        # Compter les balises <article
        count = html.count("<article")
        posts_count = count if count > 0 else "?"
    except:
        pass

    ghost_status = run("docker ps --filter name=ghost-blog --format '{{.Status}}' 2>/dev/null", timeout=5)
    ghost_up = "Up" in ghost_status

    return {
        "posts_published": posts_count,
        "ghost_up": ghost_up,
    }

# ─── ALFRED TRADER ────────────────────────────────────────

def check_alfred_trader():
    """Vérifie les crons système pour Alfred Trader."""
    cron_list = run("crontab -l 2>/dev/null", timeout=10)
    morning = "alfred_trader.py" in cron_list and "0 6" in cron_list
    us_pulse = "alfred_trader.py" in cron_list and "--us-pulse" in cron_list
    crons_ok = morning and us_pulse

    # Dernier signal : chercher dans le fichier le plus récent
    last_signal = "N/A"
    watch_dir = os.path.join(WORKSPACE, "state/stock_watch/daily_scans")
    if os.path.isdir(watch_dir):
        files = sorted(os.listdir(watch_dir))
        if files:
            latest = files[-1]
            mtime = datetime.fromtimestamp(os.path.getmtime(os.path.join(watch_dir, latest)))
            last_signal = mtime.strftime("%d/%m %H:%M")

    return {
        "crons_ok": crons_ok,
        "morning": morning,
        "us_pulse": us_pulse,
        "last_signal": last_signal,
    }

# ─── INFRA ────────────────────────────────────────────────

def check_infra():
    disk = run("df -h / | tail -1")
    ram = run("free -h | grep Mem")
    nginx = run("systemctl is-active nginx")
    ghost = run("docker ps --filter name=ghost-blog --format '{{.Status}}' 2>/dev/null")

    disk_pct = 0
    disk_total = "?"
    disk_used = "?"
    if disk:
        parts = disk.split()
        if len(parts) >= 5:
            try:
                disk_pct = int(parts[4].rstrip("%"))
                disk_total = parts[1]  # ex: 72G
                disk_used = parts[2]   # ex: 52G
            except:
                pass

    ram_used_pct = 0
    if ram:
        parts = ram.split()
        if len(parts) >= 3:
            try:
                total_str = parts[1].replace(",", ".").rstrip("Gi")
                used_str = parts[2].replace(",", ".").rstrip("Gi")
                ram_used_pct = round(float(used_str) / float(total_str) * 100)
            except:
                pass

    return {
        "disk_pct": disk_pct, "disk_total": disk_total, "disk_used": disk_used,
        "ram_used_pct": ram_used_pct,
        "nginx": nginx, "ghost_docker": ghost or "down",
    }

# ─── EUROMILLIONS ─────────────────────────────────────────

def check_euromillions():
    # Vérifier cron Euromillions (crontab système + OpenClaw)
    cron_list = run("openclaw cron list 2>/dev/null", timeout=10)
    crontab_list = run("crontab -l 2>/dev/null", timeout=5)
    cron_ok = ("euromillion" in cron_list.lower() or "euromillion" in crontab_list.lower())

    # Vérifier le fichier de prédictions (dans euromillions/, pas state/)
    pred_file = os.path.join(WORKSPACE, "euromillions/predictions_log.json")
    last_pred = "N/A"
    if os.path.exists(pred_file):
        try:
            with open(pred_file) as f:
                data = json.load(f)
            if isinstance(data, list) and data:
                last_entry = data[-1]
                last_pred = last_entry.get("date", "N/A")
            elif isinstance(data, dict):
                last_pred = data.get("last_run", json.dumps(list(data.keys())[-1:]))
        except:
            pass

    # Fallback: telegram_msg.txt
    if last_pred == "N/A":
        msg_file = os.path.join(WORKSPACE, "euromillions/telegram_msg.txt")
        if os.path.exists(msg_file):
            mtime = datetime.fromtimestamp(os.path.getmtime(msg_file))
            last_pred = mtime.strftime("%d/%m %H:%M")

    # Nettoie le format si c'est une liste JSON mal parsée
    if isinstance(last_pred, str) and last_pred.startswith("["):
        try:
            arr = json.loads(last_pred)
            last_pred = arr[0] if arr else "N/A"
        except:
            pass
    return {"cron_ok": cron_ok, "last_prediction": str(last_pred)}

# ─── GENERATE REPORT (Telegram format, no markdown) ──────

def generate_report(results, traffic):
    s = results["site"]
    yt = results["youtube"]
    tr = results["alfred_trader"]
    inf = results["infra"]
    eu = results["euromillions"]
    ghost = results["ghost"]

    # Scoreboard
    checks = [
        ("Site", s["status"] == "✅"),
        ("YouTube", yt["pipeline_ok"]),
        ("Trader", tr["crons_ok"]),
        ("Infra", inf["nginx"] == "active" and inf["disk_pct"] < 88),
        ("Euromillions", eu["cron_ok"]),
        ("Blog", ghost["ghost_up"]),
    ]
    green = sum(1 for _, ok in checks if ok)
    total = len(checks)

    # Build report
    lines = []
    lines.append(f"📋 Audit Revenu — {date.today().strftime('%d/%m')}  [ {green}/{total} ]")
    lines.append("")

    # Site
    site_line = f"🌐 Site PEA: {s['status']} {s['ok']}/{s['total']} pages OK"
    if s["failures"]:
        site_line += "  | DOWN: " + ", ".join(s["failures"])
    if not s["sitemap_ok"]:
        site_line += "  | Sitemap DOWN"
    lines.append(site_line)

    # Traffic
    t = traffic
    lines.append(f"📊 Trafic 24h: {t['hits_24h']} hits · {t['ips_24h']} visiteurs uniques")
    lines.append(f"📊 Trafic 7j:  {t['hits_7d']} hits · {t['ips_7d']} visiteurs uniques")

    # YouTube
    cron_icon = "✅" if yt["pipeline_cron"] else "❌"
    lines.append(f"📺 YouTube: {yt['subs']} abonnés · {yt['views']} vues · {yt['vids']} vidéos")
    lines.append(f"   Dernière: \"{yt['last_title']}\" — {yt['last_views']} vues · {yt['last_likes']} likes")
    lines.append(f"   Pipeline: {'✅' if yt['pipeline_ok'] else '❌'} orch {yt['last_orch']} · Cron: {cron_icon}")

    # Blog Ghost
    lines.append(f"📝 Blog Ghost: {ghost['posts_published']} articles publiés · Docker: {'✅' if ghost['ghost_up'] else '❌'}")

    # Alfred Trader
    trader_icon = "✅" if tr["crons_ok"] else "⚠️"
    lines.append(f"📈 Alfred Trader: {trader_icon}")
    lines.append(f"   Crons: morning {'✅' if tr['morning'] else '❌'} · US pulse {'✅' if tr['us_pulse'] else '❌'}")
    lines.append(f"   Dernier scan: {tr['last_signal']}")

    # Euromillions
    eu_icon = "✅" if eu["cron_ok"] else "❌"
    lines.append(f"🎰 Euromillions: {eu_icon} · Dernier run: {eu['last_prediction']}")

    # Infra
    infra_ok = inf["nginx"] == "active" and inf["disk_pct"] < 88
    infra_icon = "✅" if infra_ok else "⚠️"
    lines.append(f"🏗️ Infra: {infra_icon}  Disk {inf['disk_pct']}% ({inf['disk_used']}/{inf['disk_total']}) · RAM {inf['ram_used_pct']}% · Nginx {inf['nginx']}")

    # Scorecard vs cibles
    lines.append("")
    lines.append("🎯 Scorecard vs Cibles :")

    # YouTube cibles
    try:
        subs_i = int(yt['subs'])
        views_i = int(yt['views'])
        last_v = int(yt['last_views']) if yt['last_views'].isdigit() else 0
    except:
        subs_i = views_i = last_v = 0

    lines.append(f"   YouTube: {subs_i} abonnés (cible 100) · {views_i} vues (cible 1000)")
    if last_v > 0:
        lines.append(f"   Dernière vidéo: {last_v} vues — cible >50 vues en 48h")

    # Site cible
    # Site cible — filter bot traffic estimate (real visitors ~30% of unique IPs)
    real_visitors = int(t['ips_24h'] * 0.3)
    lines.append(f"   Site: ~{real_visitors} visiteurs/jour est. — cible 15/jour (100/sem)")

    # Actions
    lines.append("")
    actions = []
    if s["failures"]:
        actions.append(f"🔧 {len(s['failures'])} page(s) down — vérifier nginx")
    if not s["sitemap_ok"]:
        actions.append("🗺️ Sitemap inaccessible")
    if inf["disk_pct"] > 85:
        actions.append(f"💾 Disque {inf['disk_pct']}% — nettoyage urgent")
    if not yt["pipeline_cron"]:
        actions.append("🎬 Cron pipeline YouTube manquant")
    if not tr["crons_ok"]:
        actions.append("📈 Crons Alfred Trader incomplets")
    if not eu["cron_ok"]:
        actions.append("🎰 Cron Euromillions inactif")
    if not ghost["ghost_up"]:
        actions.append("📝 Ghost Docker down")

    if not actions:
        actions.append("✅ Tous les leviers sont verts")
    actions.append("💡 Priorité #1 : attirer du trafic vers le comparateur PEA -> affiliation Trade Republic")

    lines.append("⚡ Actions :")
    for a in actions:
        lines.append(f"   {a}")

    return "\n".join(lines), actions

# ─── AUTO-FIX ─────────────────────────────────────────────

def auto_fix(results):
    fixes = []
    inf = results.get("infra", {})

    if inf.get("nginx", "inactive") != "active":
        r = run("sudo systemctl restart nginx && systemctl is-active nginx")
        fixes.append(f"🔧 nginx redémarré ({r})" if r == "active" else f"⚠️ nginx HS: {r}")

    if inf.get("disk_pct", 0) > 88:
        fixes.append("🔴 Disque critique >88% — nettoyage auto")
        run("docker system prune -f 2>/dev/null")
        run("sudo journalctl --vacuum-time=3d 2>/dev/null")

    return fixes

# ─── SAVE ─────────────────────────────────────────────────

def save_report(results, traffic, fixes, report, actions):
    audit_dir = os.path.join(WORKSPACE, "state/revenue_audit")
    os.makedirs(audit_dir, exist_ok=True)
    data = {
        "date": date.today().isoformat(),
        "timestamp": datetime.now().isoformat(),
        "results": results,
        "traffic": {k: v for k, v in traffic.items() if k != "top_pages"},
        "fixes": fixes,
        "actions": actions,
    }
    today_file = os.path.join(audit_dir, f"{date.today().isoformat()}.json")
    latest_file = os.path.join(audit_dir, "latest.json")
    for f in [today_file, latest_file]:
        with open(f, "w") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    return today_file

# ─── MAIN ─────────────────────────────────────────────────

def main():
    print("🧪 Audit Revenu V3...", file=sys.stderr)
    results = {}
    results["site"] = check_site()
    results["youtube"] = check_youtube()
    results["alfred_trader"] = check_alfred_trader()
    results["infra"] = check_infra()
    results["euromillions"] = check_euromillions()
    results["ghost"] = check_ghost()
    traffic = get_traffic_stats()

    fixes = auto_fix(results)
    if fixes:
        results["infra"] = check_infra()

    report, actions = generate_report(results, traffic)
    saved = save_report(results, traffic, fixes, report, actions)
    print(f"📁 Saved: {saved}", file=sys.stderr)
    print(report)

    # Notification Telegram
    try:
        send_telegram(report, parse_mode='HTML')
    except Exception as e:
        print(f'Notif error: {e}', file=sys.stderr)



if __name__ == "__main__":
    main()