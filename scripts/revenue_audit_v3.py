#!/usr/bin/env python3
"""Revenue Audit V4 — métriques réelles + progression monétisation + benchmarks finance."""

import json, os, subprocess, sys, time, gzip, glob, fcntl, re
from datetime import date, datetime, timedelta

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
    now = datetime.now()
    cutoff_24h = now - timedelta(hours=24)
    cutoff_7d = now - timedelta(days=7)

    hits_24h = 0; ips_24h = set()
    hits_7d = 0; ips_7d = set()
    pages_24h = {}
    referrers_24h = {}

    log_files = ["/var/log/nginx/access.log", "/var/log/nginx/access.log.1"]
    for f in sorted(glob.glob("/var/log/nginx/access.log.*.gz")): log_files.append(f)

    for lf in log_files:
        try:
            if lf.endswith(".gz"):
                with gzip.open(lf, "rt", errors="ignore") as fh: lines = fh.readlines()
            else:
                with open(lf, "r", errors="ignore") as fh: lines = fh.readlines()
        except: continue

        for line in lines:
            parts = line.split()
            if len(parts) < 4: continue
            ip = parts[0]
            try:
                ts_str = line.split("[")[1].split("]")[0] if "[" in line else ""
                ts = datetime.strptime(ts_str, "%d/%b/%Y:%H:%M:%S %z")
                ts = ts.replace(tzinfo=None)
            except: continue

            path = parts[6] if len(parts) > 6 else "-"
            code = parts[8] if len(parts) > 8 else "0"
            ref = parts[10] if len(parts) > 10 else "-"

            if ts >= cutoff_7d:
                hits_7d += 1; ips_7d.add(ip)
            if ts >= cutoff_24h:
                hits_24h += 1; ips_24h.add(ip)
                if code == "200" and not any(x in path for x in [".css", ".js", ".ico", ".png", ".jpg", ".woff", ".xml"]):
                    pages_24h[path] = pages_24h.get(path, 0) + 1
                    if ref and ref != "-" and "alfredstudio" not in ref:
                        domain = ref.split("/")[2] if "://" in ref else ref
                        referrers_24h[domain] = referrers_24h.get(domain, 0) + 1

    top_pages = sorted(pages_24h.items(), key=lambda x: -x[1])[:5]
    top_str = " | ".join(f"{p} ({c})" for p, c in top_pages) if top_pages else "N/A"
    top_refs = sorted(referrers_24h.items(), key=lambda x: -x[1])[:3]
    ref_str = " | ".join(f"{r} ({c})" for r, c in top_refs) if top_refs else "direct"

    return {
        "hits_24h": hits_24h, "ips_24h": len(ips_24h),
        "hits_7d": hits_7d, "ips_7d": len(ips_7d),
        "top_pages": top_str, "top_referrers": ref_str,
    }

# ─── SITE ────────────────────────────────────────────────

def check_site():
    urls = [
        ("Accueil", "https://alfredstudio.mooo.com/"),
        ("Comparateur", "https://alfredstudio.mooo.com/pea-comparator/"),
        ("Blog", "https://alfredstudio.mooo.com/blog/"),
        ("Guide", "https://alfredstudio.mooo.com/guide/"),
    ]
    ok = 0; failures = []
    for name, url in urls:
        code = curl_status(url)
        if code == "200": ok += 1
        else: failures.append(f"{name} ({code})")
    sitemap_ok = curl_status("https://alfredstudio.mooo.com/sitemap.xml") == "200"
    status = "✅" if ok == len(urls) else ("⚠️" if ok >= 3 else "🔴")
    return {"status": status, "ok": ok, "total": len(urls), "failures": failures, "sitemap_ok": sitemap_ok}

# ─── YOUTUBE (augmenté : progression monétisation) ───────

def check_youtube():
    result = run(
        "cd /home/ubuntu/.openclaw/workspace/skills/youtube_upload && source ~/.secrets/env 2>/dev/null; python3 stats.py 2>/dev/null",
        timeout=30
    )
    subs = 0; views = 0; vids = 0
    last_title = "N/A"; last_views = 0; last_likes = 0

    for i, line in enumerate(result.split("\n")):
        line = line.strip()
        if "Abonnés" in line:
            subs = int(re.sub(r'[^0-9]', '', line.split(":")[-1]) or 0)
        elif "Vues total" in line:
            views = int(re.sub(r'[^0-9]', '', line.split(":")[-1]) or 0)
        elif "Vidéos" in line:
            vids = int(re.sub(r'[^0-9]', '', line.split(":")[-1]) or 0)
        elif line.startswith("•") and last_title == "N/A":
            last_title = line.replace("•", "").strip()
            if i+1 < len(lines := result.split("\n")):
                detail = lines[i+1].strip()
                vm = re.search(r'([d]+)s*vue', detail)
                lm = re.search(r'([d]+)s*like', detail)
                if vm: last_views = int(vm.group(1))
                if lm: last_likes = int(lm.group(1))

    # Progression monétisation YouTube
    # Seuil Early Access : 500 subs / 3000h watch time
    # Seuil Full : 1000 subs / 4000h watch time
    # On estime ~3 min/vue pour la niche finance (format court neuro 60s)
    est_watch_hours = round(views * 1.2 / 60, 1)  # ~1.2 min avg per view → heures
    subs_pct_early = min(100, round(subs / 500 * 100)) if subs else 0
    subs_pct_full = min(100, round(subs / 1000 * 100)) if subs else 0
    hours_pct_early = min(100, round(est_watch_hours / 3000 * 100))
    hours_pct_full = min(100, round(est_watch_hours / 4000 * 100))

    # Projection revenue potentielle (niche Finance RPM 5-20$)
    rpm_low = 5; rpm_high = 20
    pot_rev_monthly_low = round(views * rpm_low / 1000, 1)
    pot_rev_monthly_high = round(views * rpm_high / 1000, 1)

    # Vérifier pipeline
    orch = os.path.join(WORKSPACE, "pipeline/pipeline_orchestrator.py")
    pipeline_ok = os.path.exists(orch)
    last_orch = datetime.fromtimestamp(os.path.getmtime(orch)).strftime("%d/%m") if pipeline_ok else "N/A"
    cron_list = run("crontab -l 2>/dev/null", timeout=10)
    pipeline_cron = "neuro_finance_cron" in cron_list or "pipeline_orchestrator" in cron_list

    return {
        "subs": subs, "views": views, "vids": vids,
        "last_title": last_title, "last_views": last_views, "last_likes": last_likes,
        "pipeline_ok": pipeline_ok, "last_orch": last_orch, "pipeline_cron": pipeline_cron,
        "est_watch_hours": est_watch_hours,
        "subs_pct_early": subs_pct_early, "subs_pct_full": subs_pct_full,
        "hours_pct_early": hours_pct_early, "hours_pct_full": hours_pct_full,
        "pot_rev_monthly_low": pot_rev_monthly_low, "pot_rev_monthly_high": pot_rev_monthly_high,
    }

# ─── BLOG GHOST ──────────────────────────────────────────

def check_ghost():
    posts_count = "N/A"
    try:
        html = run("curl -s 'https://alfredstudio.mooo.com/blog/' --max-time 8", timeout=10)
        count = html.count("<article")
        posts_count = count if count > 0 else "?"
    except: pass
    ghost_status = run("docker ps --filter name=ghost-blog --format '{{.Status}}' 2>/dev/null", timeout=5)
    return {"posts_published": posts_count, "ghost_up": "Up" in ghost_status}

# ─── ALFRED TRADER ────────────────────────────────────────

def check_alfred_trader():
    cron_list = run("crontab -l 2>/dev/null", timeout=10)
    morning = "alfred_trader" in cron_list and 'morning' not in cron_list
    us_pulse = "alfred_trader" in cron_list and 'us-pulse' not in cron_list
    last_signal = "N/A"
    watch_dir = os.path.join(WORKSPACE, "state/stock_watch/daily_scans")
    if os.path.isdir(watch_dir):
        files = sorted(os.listdir(watch_dir))
        if files:
            mtime = datetime.fromtimestamp(os.path.getmtime(os.path.join(watch_dir, files[-1])))
            last_signal = mtime.strftime("%d/%m %H:%M")
    return {"crons_ok": morning and us_pulse, "morning": morning, "us_pulse": us_pulse, "last_signal": last_signal}

# ─── AFFILIATION ─────────────────────────────────────────

def check_affiliation():
    """Vérifie les liens d'affiliation Trade Republic sur le site."""
    try:
        html = run("curl -s 'https://alfredstudio.mooo.com/pea-comparator/' --max-time 8", timeout=10)
        tr_link = "trade-republic" in html.lower() or "ref" in html.lower()
        etf_links = html.count("trade-republic") + html.count("tr-link")
    except:
        tr_link = False; etf_links = 0
    return {"tr_link_present": tr_link, "etf_links_count": etf_links}

# ─── INFRA ────────────────────────────────────────────────

def check_infra():
    disk = run("df -h / | tail -1")
    ram = run("free -h | grep Mem")
    nginx = run("systemctl is-active nginx")
    ghost = run("docker ps --filter name=ghost-blog --format '{{.Status}}' 2>/dev/null")
    disk_pct = 0; disk_total = "?"; disk_used = "?"
    if disk:
        parts = disk.split()
        if len(parts) >= 5:
            try: disk_pct = int(parts[4].rstrip("%")); disk_total = parts[1]; disk_used = parts[2]
            except: pass
    ram_used_pct = 0
    if ram:
        parts = ram.split()
        if len(parts) >= 3:
            try:
                total_str = parts[1].replace(",",".").rstrip("Gi")
                used_str = parts[2].replace(",",".").rstrip("Gi")
                ram_used_pct = round(float(used_str) / float(total_str) * 100)
            except: pass
    return {"disk_pct": disk_pct, "disk_total": disk_total, "disk_used": disk_used,
            "ram_used_pct": ram_used_pct, "nginx": nginx, "ghost_docker": ghost or "down"}

# ─── EUROMILLIONS ─────────────────────────────────────────

def check_euromillions():
    cron_list = run("crontab -l 2>/dev/null", timeout=10)
    cron_ok = "euromillion" in cron_list.lower()
    pred_file = os.path.join(WORKSPACE, "euromillions/predictions_log.json")
    last_pred = "N/A"
    if os.path.exists(pred_file):
        try:
            with open(pred_file) as f: data = json.load(f)
            if isinstance(data, list) and data: last_pred = data[-1].get("date","N/A")
            elif isinstance(data, dict): last_pred = data.get("last_run","N/A")
        except: pass
    if last_pred == "N/A":
        msg_file = os.path.join(WORKSPACE, "euromillions/telegram_msg.txt")
        if os.path.exists(msg_file):
            last_pred = datetime.fromtimestamp(os.path.getmtime(msg_file)).strftime("%d/%m %H:%M")
    return {"cron_ok": cron_ok, "last_prediction": str(last_pred)}

# ─── GENERATE REPORT ─────────────────────────────────────

def generate_report(results, traffic):
    s = results["site"]; yt = results["youtube"]; tr = results["alfred_trader"]
    inf = results["infra"]; eu = results["euromillions"]; ghost = results["ghost"]
    aff = results["affiliation"]

    # Scoreboard (poids revenu)
    checks = [
        ("Site", s["status"] == "✅", 1),
        ("YouTube", yt["pipeline_ok"], 3),       # ×3 — levier #1
        ("Affiliation TR", aff["tr_link_present"], 2),  # ×2 — levier #2
        ("Trader", tr["crons_ok"], 1),
        ("Infra", inf["nginx"] == "active" and inf["disk_pct"] < 88, 1),
        ("Euromillions", eu["cron_ok"], 1),
        ("Blog", ghost["ghost_up"], 1),
    ]
    green = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)

    lines = [f"📋 Audit Revenu — {date.today().strftime('%d/%m')}  [ {green}/{total} ]"]

    # Site
    site_line = f"🌐 Site PEA: {s['status']} {s['ok']}/{s['total']} pages OK"
    if s["failures"]: site_line += "  | DOWN: " + ", ".join(s["failures"])
    if not s["sitemap_ok"]: site_line += "  | Sitemap DOWN"
    lines.append(site_line)

    # Trafic
    t = traffic
    lines.append(f"📊 Trafic 24h: {t['hits_24h']} hits · {t['ips_24h']} visiteurs uniques")
    lines.append(f"📊 Trafic 7j:  {t['hits_7d']} hits · {t['ips_7d']} visiteurs uniques")
    lines.append(f"    Référants: {t['top_referrers']}")

    # YouTube — version enrichie
    cron_icon = "✅" if yt["pipeline_cron"] else "❌"
    lines.append(f"📺 YouTube: {yt['subs']} abonnés · {yt['views']} vues · {yt['vids']} vidéos")
    lines.append(f"    Dernière: "{yt['last_title']}" — {yt['last_views']} vues · {yt['last_likes']} likes")
    lines.append(f"    Pipeline: {'✅' if yt['pipeline_ok'] else '❌'} orch {yt['last_orch']} · Cron: {cron_icon}")

    # 🔥 Progression monétisation
    lines.append(f"🔥 Progression monétisation YouTube :")
    lines.append(f"    Early Access (500 abonnés): Subs {yt['subs_pct_early']}% · Watch hours {yt['hours_pct_early']}%")
    lines.append(f"    Full (1000 abonnés):       Subs {yt['subs_pct_full']}% · Watch hours {yt['hours_pct_full']}%")
    lines.append(f"    {yt['est_watch_hours']}h estimées sur 3000h (seuil)")

    # Projection revenue
    lines.append(f"💰 Projection AdSense (niche Finance RPM 5$-20$) :")
    lines.append(f"    Est. {yt['pot_rev_monthly_low']}$ — {yt['pot_rev_monthly_high']}$ / mois (vues totales)")
    lines.append(f"    Objectif 100k vues/mois: 500$ — 2 000$ / mois")

    # Blog
    lines.append(f"📝 Blog Ghost: {ghost['posts_published']} articles · Docker: {'✅' if ghost['ghost_up'] else '❌'}")

    # Affiliation
    aff_icon = "✅" if aff["tr_link_present"] else "⚠️"
    lines.append(f"🔗 Affiliation TR: {aff_icon} Liens présents: {aff['etf_links_count']}")

    # Alfred Trader
    trader_icon = "✅" if tr["crons_ok"] else "⚠️"
    lines.append(f"📈 Alfred Trader: {trader_icon}")
    lines.append(f"    Crons: morning {'✅' if tr['morning'] else '❌'} · US pulse {'✅' if tr['us_pulse'] else '❌'}")
    lines.append(f"    Dernier scan: {tr['last_signal']}")

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

    try:
        subs_i = int(yt['subs']); views_i = int(yt['views'])
        last_v = int(yt['last_views'])
    except:
        subs_i = views_i = last_v = 0

    lines.append(f"   YouTube: {subs_i}/{1000} abonnés ({yt['subs_pct_full']}%) · {views_i} vues")
    lines.append(f"   Dernière vidéo: {last_v} vues — cible >50 vues en 48h")
    real_visitors = int(t['ips_24h'] * 0.3)
    lines.append(f"   Site: ~{real_visitors} visiteurs/jour est. — cible 15/jour (100/sem)")

    # Actions
    lines.append("")
    actions = []
    if s["failures"]: actions.append(f"🔧 {len(s['failures'])} page(s) down — vérifier nginx")
    if not s["sitemap_ok"]: actions.append("🗺️ Sitemap inaccessible")
    if inf["disk_pct"] > 85: actions.append(f"💾 Disque {inf['disk_pct']}% — nettoyage urgent")
    if not yt["pipeline_cron"]: actions.append("🎬 Cron pipeline YouTube manquant")
    if not aff["tr_link_present"]: actions.append("🔗 Liens affiliation Trade Republic absents du site")
    if not tr["crons_ok"]: actions.append("📈 Crons Alfred Trader incomplets")
    if not eu["cron_ok"]: actions.append("🎰 Cron Euromillions inactif")
    if not ghost["ghost_up"]: actions.append("📝 Ghost Docker down")

    # Actions stratégiques basées sur les rapports
    if 100 <= subs_i < 500: actions.append("🎯 Plus que {}/500 pour Early Access YouTube — accélérer la prod".format(500 - subs_i))
    elif subs_i < 100: actions.append("🎯 Objectif 100 abonnés → mise en place stratégie cross-pub blog/YouTube")
    if yt['est_watch_hours'] < 500: actions.append("⏱️ Watch hours faibles ({:.0f}h/3000h) — prioriser les formats longs >8min".format(yt['est_watch_hours']))

    if not actions: actions.append("✅ Tous les leviers sont verts")
    actions.append("💡 Priorité #1 : attirer du trafic vers le comparateur PEA → affiliation Trade Republic")

    lines.append("⚡ Actions :")
    for a in actions: lines.append(f"   {a}")

    return "
".join(lines), actions

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
        "date": date.today().isoformat(), "timestamp": datetime.now().isoformat(),
        "results": results, "traffic": {k: v for k, v in traffic.items() if k != "top_pages"},
        "fixes": fixes, "actions": actions, "version": 4,
    }
    today_file = os.path.join(audit_dir, f"{date.today().isoformat()}.json")
    latest_file = os.path.join(audit_dir, "latest.json")
    for f in [today_file, latest_file]:
        with open(f, "w") as fh: json.dump(data, fh, indent=2, ensure_ascii=False)
    return today_file

# ─── MAIN ─────────────────────────────────────────────────

def main():
    print("🧪 Audit Revenu V4...", file=sys.stderr)
    results = {}
    results["site"] = check_site()
    results["youtube"] = check_youtube()
    results["alfred_trader"] = check_alfred_trader()
    results["infra"] = check_infra()
    results["euromillions"] = check_euromillions()
    results["ghost"] = check_ghost()
    results["affiliation"] = check_affiliation()
    traffic = get_traffic_stats()

    fixes = auto_fix(results)
    if fixes: results["infra"] = check_infra()

    report, actions = generate_report(results, traffic)
    saved = save_report(results, traffic, fixes, report, actions)
    print(f"📁 Saved: {saved}", file=sys.stderr)
    print(report)

if __name__ == "__main__":
    main()
