#!/usr/bin/env python3
"""
morning_report.py — Rapport matinal enrichi Alfred (V2)
Remplace morning_report.sh
Intègre : tendances J-1, analyse niche, conseil IA, projection monéto,
          santé VPS, pipeline health, format Telegram enrichi.
"""
import os, sys, json, subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
STATE_DIR = WORKSPACE / "state"
ANALYTICS_FILE = WORKSPACE / "skills/alfred_video_pipeline/ANALYTICS.json"
# [2026-09-27] upload_history.json n a JAMAIS existe : remplace par get_last_upload()
MAINT_HISTORY = STATE_DIR / "maintenance_history.json"
REPORT_STATE = STATE_DIR / "morning_report_state.json"
ENV_FILE = Path.home() / ".secrets/env"

SECRETS = {}

NICHES_FR = {
    "NEURO_FINANCE": "Neuro-Finance",
}

WEEKDAY_NAMES = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]

WEEKLY_THEMES = {
    0: "Planning",
    1: "Analyse Marché",
    2: "Stratégie",
    3: "Biais & Psychologie",
    4: "Tools & Optimisation",
    5: "Bilan semaine",
    6: "Rapport Hebdo",
}


# ─── HELPERS ────────────────────────────────────────────────────────

def load_env():
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.replace("export ", "").strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    SECRETS[k] = v.strip('"').strip("'")

def load_json(path):
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, Exception):
            return {}
    return {}

def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def run_cmd(cmd, timeout=10):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except:
        return ""

def bytes_to_gb(b_str):
    """Convert df -h output bytes to GB string"""
    try:
        # Handle french locale (virgule)
        val = b_str.replace(",", ".")
        if "G" in val:
            return float(val.replace("G", ""))
        elif "M" in val:
            return float(val.replace("M", "")) / 1024
        elif "T" in val:
            return float(val.replace("T", "")) * 1024
        return 0
    except:
        return 0


# ─── DATA COLLECTION ────────────────────────────────────────────────

def get_yt_data():
    """Construit les données YouTube depuis l historique nocturne actuel."""
    history = load_json(STATE_DIR / "yt_stats_history.json")
    if not isinstance(history, list) or not history:
        return None

    def parse_date(value):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None

    entries = [entry for entry in history if isinstance(entry, dict) and parse_date(entry.get("date", ""))]
    if not entries:
        return None
    entries.sort(key=lambda entry: parse_date(entry["date"]))
    latest = entries[-1]
    latest_date = parse_date(latest["date"])
    total_views = int(latest.get("total_views", 0))

    def views_since(days):
        """Delta de vues sur la fenetre. Tolerance ADAPTATIVE : le journal nocturne
        n'est pas toujours ecrit a la meme heure (ex. point du 20/09 a 16h43),
        donc une tolerance fixe de 6h renvoyait None sur la fenetre 7j."""
        target = latest_date - timedelta(days=days)
        candidates = [(entry, parse_date(entry.get("date", ""))) for entry in entries[:-1]]
        candidates = [(entry, entry_date) for entry, entry_date in candidates if entry_date]
        if not candidates:
            return None
        tolerance = timedelta(hours=12) if days <= 1 else timedelta(hours=24 * days / 4)
        # priorite aux points ANTERIEURS a la cible : ne pas sous-compter la fenetre
        before = [(entry, entry_date) for entry, entry_date in candidates if entry_date <= target]
        pool = before or candidates
        reference, reference_date = min(pool, key=lambda item: abs(item[1] - target))
        if abs(reference_date - target) > tolerance:
            return None
        return max(0, total_views - int(reference.get("total_views", 0)))

    def views_base(days):
        """Date du point de reference reellement utilise pour la fenetre."""
        target = latest_date - timedelta(days=days)
        candidates = [(entry, parse_date(entry.get("date", ""))) for entry in entries[:-1]]
        candidates = [(entry, entry_date) for entry, entry_date in candidates if entry_date]
        if not candidates:
            return None
        tolerance = timedelta(hours=12) if days <= 1 else timedelta(hours=24 * days / 4)
        before = [(entry, entry_date) for entry, entry_date in candidates if entry_date <= target]
        pool = before or candidates
        reference, reference_date = min(pool, key=lambda item: abs(item[1] - target))
        if abs(reference_date - target) > tolerance:
            return None
        return reference_date.strftime("%Y-%m-%d")

    videos = []
    now = datetime.now(timezone.utc)
    for source in latest.get("videos", []):
        video = dict(source)
        published = parse_date(video.get("published", ""))
        video["age_days"] = max(0, (now - published).total_seconds() / 86400) if published else 0
        videos.append(video)

    recent3 = sorted(videos, key=lambda video: parse_date(video.get("published", "")) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:3]
    top = max(videos, key=lambda video: video.get("views", 0), default={})

    return {
        "subscribers": int(latest.get("subscribers", 0)),
        "total_views": total_views,
        "video_count": int(latest.get("total_videos", 0)),
        "top_title": top.get("title", ""),
        "top_views": int(top.get("views", 0)),
        "flop_title": "",
        "flop_views": 0,
        "recent3": recent3,
        "views_24h": views_since(1),
        "views_7d": views_since(7),
        "views_24h_base": views_base(1),
        "views_7d_base": views_base(7),
        "best_niche": "NEURO_FINANCE",
        "rpm_30d": None,
        "earnings_30d": None,
    }

def get_or_data():
    """Consommation OpenRouter"""
    try:
        resp = subprocess.run(
            ["curl", "-s", "https://openrouter.ai/api/v1/auth/key",
             "-H", f"Authorization: Bearer {SECRETS.get('OPENROUTER_API_KEY', '')}"],
            capture_output=True, text=True, timeout=10
        )
        d = json.loads(resp.stdout)
        key_data = d.get("data", {})
        return {
            "daily": key_data.get("usage_daily", 0),
            "monthly": key_data.get("usage_monthly", 0),
        }
    except:
        return {"daily": 0, "monthly": 0}

def get_vps_data():
    """Métriques VPS"""
    # Disk
    df_out = run_cmd(["df", "-h", "/"])
    disk_info = {}
    if df_out:
        parts = df_out.split("\n")[1].split()
        disk_info = {
            "total": parts[1] if len(parts) > 1 else "?",
            "used": parts[2] if len(parts) > 2 else "?",
            "avail": parts[3] if len(parts) > 3 else "?",
            "pct": parts[4] if len(parts) > 4 else "?",
        }
    # RAM
    free_out = run_cmd(["free", "-h"])
    ram_info = {}
    if free_out:
        lines = free_out.split("\n")
        if len(lines) > 1:
            parts = lines[1].split()
            if len(parts) >= 3:
                used_val = parts[2].replace(",", ".")
                total_val = parts[1].replace(",", ".")
                ram_info = {"used": used_val, "total": total_val}
    # Uptime
    uptime_out = run_cmd(["uptime", "-p"]).replace("up ", "")
    load_out = run_cmd(["uptime"]).split("load average:")[-1].strip() if "load average:" in run_cmd(["uptime"]) else "?"
    
    return {"disk": disk_info, "ram": ram_info, "uptime": uptime_out, "load": load_out}

UPLOAD_WATCH_DIR = Path("/home/ubuntu/output")
UPLOAD_ALERT_HOURS = 30   # le pipeline tourne tous les jours vers 16h UTC


def get_last_upload():
    """Dernier upload REEL + detection d'un rendu non publie.

    state/upload_history.json n'a jamais existe : le rapport affichait donc N/A
    en permanence. Deux sources verifiables :
      1. la derniere video PUBLIEE vue par l'API YouTube (yt_stats_history) ;
      2. le dernier RENDU du pipeline (~/output/PROD_*.mp4).
    Un rendu plus recent que la derniere publication de plus de
    UPLOAD_ALERT_HOURS = upload en echec (cf. incident OAuth 24-25/08).
    """
    res = {"date": None, "title": "", "age_jours": None,
           "rendu": None, "en_attente": 0, "alerte": False}

    hist = load_json(STATE_DIR / "yt_stats_history.json")
    last_pub = None
    if isinstance(hist, list):
        for e in hist[-6:]:
            for v in (e.get("videos") or []):
                p = v.get("published")
                if not p:
                    continue
                try:
                    dt = datetime.fromisoformat(str(p).replace("Z", "+00:00"))
                except Exception:
                    continue
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if last_pub is None or dt > last_pub:
                    last_pub = dt
                    res["title"] = v.get("title", "")
    if last_pub:
        res["date"] = last_pub.strftime("%Y-%m-%d")
        res["age_jours"] = (datetime.now(timezone.utc) - last_pub).days

    try:
        prods = sorted(UPLOAD_WATCH_DIR.glob("PROD_*.mp4"),
                       key=lambda f: f.stat().st_mtime)
    except Exception:
        prods = []
    if prods:
        rd = datetime.fromtimestamp(prods[-1].stat().st_mtime, timezone.utc)
        res["rendu"] = rd.strftime("%Y-%m-%d %H:%M UTC")
        if last_pub:
            if (rd - last_pub).total_seconds() / 3600 > UPLOAD_ALERT_HOURS:
                res["alerte"] = True
            jours = set()
            for f in prods:
                tag = f.name[5:13]
                if len(tag) == 8 and tag.isdigit():
                    try:
                        d = datetime.strptime(tag, "%Y%m%d").replace(tzinfo=timezone.utc)
                    except Exception:
                        continue
                    if d > last_pub:
                        jours.add(tag)
            res["en_attente"] = len(jours)
        else:
            res["alerte"] = True
    return res


def get_pipeline_health():
    """Vérifie l'état des pipelines planifiés"""
    health = {}
    
    # Vérifier si les crons OpenClaw sont actifs
    cron_out = run_cmd(["crontab", "-l"])
    health["cron_output"] = "maintenance.py" in cron_out and "vps_watchdog.py" in cron_out
    
    # Dernières exécutions (via maintenance_history)
    maint = load_json(MAINT_HISTORY)
    last_maint = ""
    if maint.get("history"):
        last_maint = maint["history"][-1].get("timestamp", "")
    
    # Dernier upload reel (publication YouTube + dernier rendu pipeline)
    up = get_last_upload()
    
    health["last_maintenance"] = last_maint
    health["last_upload"] = up.get("date") or ""
    health["last_upload_title"] = up.get("title") or ""
    health["last_upload_age"] = up.get("age_jours")
    health["last_render"] = up.get("rendu") or ""
    health["videos_pending"] = up.get("en_attente", 0)
    health["upload_alarm"] = bool(up.get("alerte"))
    
    return health


# ─── TRACKING J-1 ───────────────────────────────────────────────────

def load_previous_state():
    """Charge l'état précédent pour comparaison J-1"""
    return load_json(REPORT_STATE)

def save_current_state(yt_data, or_data, vps_data):
    """Sauvegarde l'état actuel pour comparaison future"""
    state = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "subscribers": yt_data["subscribers"],
        "total_views": yt_data["total_views"],
        "video_count": yt_data["video_count"],
        "views_24h": yt_data["views_24h"],
        "youtube_source": "yt_stats_history",
        "or_daily": or_data["daily"],
        "or_monthly": or_data["monthly"],
        "disk_pct": vps_data["disk"].get("pct", "?"),
        "last_updated": datetime.now().isoformat(),
    }
    prev = load_previous_state() or {}
    hist = prev.get("history") or []
    hist.append({"date": datetime.now().strftime("%Y-%m-%d"),
                 "subscribers": yt_data["subscribers"],
                 "total_views": yt_data["total_views"]})
    seen = {}
    for _e in hist:
        if _e.get("date"):
            seen[_e["date"]] = _e
    state["history"] = [seen[_k] for _k in sorted(seen)][-REPORT_STATE_HISTORY_MAX:]
    save_json(REPORT_STATE, state)

def format_diff(current, previous, key):
    """Formate une différence entre deux valeurs numériques"""
    curr = current.get(key, 0)
    prev = previous.get(key, 0) if previous else 0
    diff = curr - prev
    if diff > 0:
        return f" (+{diff:+d})" if isinstance(diff, int) else f" (+{diff:+.0f})"
    elif diff < 0:
        return f" ({diff:-d})" if isinstance(diff, int) else f" ({diff:-.0f})"
    return ""

def format_diff_views(current, previous, key):
    """Formate la différence de vues"""
    curr = current.get(key, 0)
    prev = previous.get(key, 0) if previous else 0
    diff = curr - prev
    if diff > 0:
        return f" (🔺+{diff:+d})"
    elif diff < 0:
        return f" (🔻{diff:-d})"
    return ""


# ─── CONSEIL IA ─────────────────────────────────────────────────────

def generate_advice(yt_data, prev_state):
    """Génère un conseil actionnable basé sur les données du jour"""
    tips = []
    
    subs = yt_data["subscribers"]
    views_total = yt_data["total_views"]
    
    # Si nouvelles vidéos récentes
    recent = yt_data["recent3"]
    if recent:
        best_recent = max(recent, key=lambda v: v.get("views", 0))
        best_title = best_recent.get("title", "")
        best_views = best_recent.get("views", 0)
        if best_views >= 50:
            tips.append(f"🎯 \"{best_title[:40]}…\" cartonne ({best_views} vues) → refais un short sur le même sujet")
        elif best_views < 10:
            tips.append(f"📉 \"{best_title[:40]}…\" sous-performe ({best_views} vues) → change de hook")

    # Abonnés
    if subs <= 15:
        tips.append("📺 Priorité #1 : la barre des 50 abonnés → CTA abonnement agressif en fin de chaque short")
    elif subs <= 50:
        tips.append("📺 Bon rythme ! Continue les CTA → objectif 100 abonnés")
    
    # Vues
    if yt_data["views_24h"] is not None:
        if yt_data["views_24h"] < 20:
            tips.append("📊 Faible trafic 24h → vérifie les tags SEO et le titre (chiffres accrocheurs ?)")
        elif yt_data["views_24h"] > 100:
            tips.append("📊 Bonne dynamique vues ! Peut-être le moment de poster plus souvent ?")
    
    # RPM
    rpm = yt_data.get("rpm_30d")
    if rpm is not None:
        tips.append(f"💰 RPM estimé : {rpm:.2f}€/1k vues → {yt_data.get('earnings_30d', 0):.2f}€/30j")
    
    # Toujours un conseil générique
    tips.append("💡 Astuce : titres avec CHIFFRES et MYSTÈRE outperforment les titres descriptifs")
    
    return "\n".join(f"  {t}" for t in tips[:3])


# ─── PROJECTION MONÉTISATION ────────────────────────────────────────

def monetization_projection(yt_data):
    """Estime la monétisation seulement avec un rythme quotidien fiable."""
    subs = yt_data["subscribers"]
    videos_count = yt_data["video_count"]
    report_state = load_previous_state()
    sub_gain_per_day = None

    if report_state.get("youtube_source") == "yt_stats_history":
        try:
            previous_date = datetime.fromisoformat(report_state["last_updated"])
            elapsed_days = (datetime.now() - previous_date).total_seconds() / 86400
            if 0.5 <= elapsed_days <= 2:
                gain = max(0, subs - int(report_state.get("subscribers", subs)))
                if gain > 0:
                    sub_gain_per_day = gain / elapsed_days
        except (KeyError, TypeError, ValueError):
            pass

    if sub_gain_per_day is None and yt_data["views_24h"] is not None:
        estimated_gain = yt_data["views_24h"] / 200
        if estimated_gain > 0:
            sub_gain_per_day = estimated_gain

    remaining = max(0, 1000 - subs)
    if sub_gain_per_day:
        days_remaining = int(remaining / sub_gain_per_day)
        if days_remaining > 365:
            eta = f"+{days_remaining // 365}an {days_remaining % 365 // 30}mois"
        elif days_remaining > 60:
            eta = f"{days_remaining // 30}mois {days_remaining % 30}j"
        else:
            eta = f"{days_remaining}j"
    else:
        days_remaining = None
        eta = "N/A"

    watch_hours_est = round(yt_data["total_views"] * 15 / 3600, 1)
    return {
        "subs_current": subs,
        "subs_remaining": remaining,
        "subs_per_day": round(sub_gain_per_day, 1) if sub_gain_per_day is not None else None,
        "eta_days": days_remaining,
        "eta_str": eta,
        "watch_hours_est": watch_hours_est,
    }


# ─── RAPPORT TELEGRAM ───────────────────────────────────────────────

def format_telegram(yt_data, or_data, vps_data, prev_state, advice, monet, pipeline, weekday):
    """Construit le message Telegram structuré"""
    
    now = datetime.now()
    today_str = now.strftime("%d/%m/%Y")
    day_name = WEEKDAY_NAMES[weekday]
    
    lines = []
    
    # ── En-tête ──
    lines.append(f"☀️ Bonjour Eric — Rapport Alfred du {today_str} ({day_name})")
    lines.append("")
    
    # ── 1. 📺 Chaîne YouTube ──
    diff_subs = format_diff(yt_data, prev_state, "subscribers") if prev_state else ""
    diff_views = format_diff_views(yt_data, prev_state, "total_views") if prev_state else ""
    lines.append("📺 **Chaîne YouTube**")
    lines.append(f"  Abonnés : {yt_data['subscribers']}{diff_subs}")
    if yt_data["views_24h"] is not None:
        views_24h_label = "+" + str(yt_data["views_24h"])
    else:
        views_24h_label = "N/A (journal incomplet)"
    if yt_data["views_7d"] is not None:
        views_7d_label = "+" + str(yt_data["views_7d"])
        if yt_data.get("views_7d_base"):
            views_7d_label += " (base " + str(yt_data["views_7d_base"]) + ")"
    else:
        views_7d_label = "N/A (journal incomplet)"
    lines.append("  Vues 7j : " + views_7d_label + " | Total : " + str(yt_data["total_views"]) + diff_views)
    lines.append("  Vues 24h : " + views_24h_label)
    lines.append(f"  Vidéos : {yt_data['video_count']}")
    lines.append(f"  Top : {yt_data['top_title'][:45]} ({yt_data['top_views']} vues)")
    lines.append(f"  Niche : {NICHES_FR.get(yt_data['best_niche'], yt_data['best_niche'])}")
    lines.append("")
    
    # ── 2. 🌐 Web Analytics ──
    lines.append("🌐 " + site_analytics_report())
    lines.append("")
    
    # ── 3. 🔍 Google Search Console ──
    lines.append("")
    lines.append("")
    
    # ── 4. 3 Dernières vidéos ──
    lines.append("🎬 **3 dernières vidéos**")
    for v in yt_data["recent3"]:
        title = v.get("title", "?")[:40]
        views = v.get("views", 0)
        likes = v.get("likes", 0)
        age = v.get("age_days", 0)
        score = v.get("score")
        emoji = "🔥" if views >= 50 else ("📊" if views >= 20 else "📉")
        details = f"J+{age:.0f}" + (f", score {score:.0f}" if score is not None else "")
        lines.append(f"  {emoji} {title} — {views}👁️ {likes}👍 ({details})")
    lines.append("")
    
    # ── 5. 💰 OpenRouter ──
    diff_or = format_diff(or_data, prev_state, "or_monthly") if prev_state else ""
    lines.append("💰 **OpenRouter**")
    lines.append(f"  Aujourd'hui : ${or_data['daily']:.4f}")
    lines.append(f"  Ce mois : ${or_data['monthly']:.4f}{diff_or}")
    lines.append(f"  Modèle : deepseek/deepseek-v4.1-flash")
    lines.append("")
    
    # ── 6. 🚀 Monétisation ──
    lines.append("🚀 **Projection Monétisation**")
    eta_days = monet["eta_days"]
    eta_color = "⚪" if eta_days is None else ("🔴" if eta_days > 180 else ("🟡" if eta_days > 60 else "🟢"))
    rhythm = monet["subs_per_day"] if monet["subs_per_day"] is not None else "N/A"
    lines.append(f"  {eta_color} {monet['subs_current']}/1000 abonnés ({monet['subs_remaining']} restants)")
    lines.append(f"  Rythme : {rhythm}/jour → ETA **{monet['eta_str']}**")
    lines.append(f"  ⏱ Heures regardées estimées : {monet['watch_hours_est']}h")
    lines.append("")
    
    # ── 7. 💡 Conseil du jour ──
    lines.append("💡 **Conseil du jour**")
    lines.append(advice)
    lines.append("")
    
    # ── 8. 🖥️ VPS ──
    disk = vps_data["disk"]
    ram = vps_data["ram"]
    disk_pct = disk.get("pct", "?")
    disk_warn = "⚠️" if disk_pct.replace("%", "").replace(",", ".").replace(" ", "").isdigit() and float(disk_pct.replace("%", "").replace(",", ".")) > 80 else "✅"
    lines.append("🖥️ **VPS**")
    lines.append(f"  {disk_warn} Disque : {disk_pct} ({disk.get('used', '?')}/{disk.get('total', '?')})")
    lines.append(f"  ✅ RAM : {ram.get('used', '?')}/{ram.get('total', '?')}")
    lines.append(f"  🕐 Uptime : {vps_data['uptime']}")
    lines.append("")
    
    # ── 9. ⚙️ Pipeline ──
    lines.append("⚙️ **Pipelines**")
    if pipeline["cron_output"]:
        lines.append("  ✅ Maintenance : active")
    else:
        lines.append("  🔴 Maintenance : INACTIVE")
    if pipeline.get("last_upload"):
        up_lbl = "  📤 Dernier upload : " + pipeline["last_upload"]
        if pipeline.get("last_upload_age") is not None:
            up_lbl += " (J-" + str(pipeline["last_upload_age"]) + ")"
        if pipeline.get("last_upload_title"):
            up_lbl += " - " + pipeline["last_upload_title"][:42]
        lines.append(up_lbl)
    else:
        lines.append("  📤 Dernier upload : aucune publication detectee")
    if pipeline.get("last_render"):
        lines.append("  🎬 Dernier rendu : " + pipeline["last_render"])
    if pipeline.get("upload_alarm"):
        lines.append("  🔴 " + str(pipeline.get("videos_pending", 0)) + " video(s) rendue(s) NON publiee(s) -> upload a verifier")
    if pipeline["last_maintenance"]:
        lines.append(f"  🔧 Dernière maintenance : {pipeline['last_maintenance']}")
    lines.append("")
    
    # ── 10. 📅 Programme du jour ──
    theme = WEEKLY_THEMES.get(weekday, "Sujet libre")
    lines.append("📅 **Aujourd'hui**")
    if weekday in (1, 3, 5):  # lun, mer, ven = finance pipeline
        lines.append(f"  🎬 Pipeline Neuro-Finance : {theme}")
    else:
        lines.append(f"  📝 Jour off pipeline (repos)")
    if weekday == 6:  # Dimanche
        lines.append("  📊 Rapport hebdomadaire ci-dessous")
    lines.append("")
    
    # ── 11. 📊 Rapport hebdo (dimanche) ──
    _wd = weekly_delta(yt_data) if weekday == 6 else None
    if weekday == 6 and _wd:
        week_views = _wd["vues"]
        week_subs = _wd["abonnes"]
        lines.append("📊 **Bilan hebdomadaire**")
        lines.append(f"  📈 Vues cette semaine : {week_views:+d}")
        lines.append(f"  📈 Abonnés cette semaine : {week_subs:+d}")
        lines.append(f"  💰 Coût OpenRouter 24h : ${or_data['daily']:.4f}")
        scores = [v["score"] for v in yt_data["recent3"] if v.get("score") is not None]
        if scores:
            avg_score = sum(scores) / len(scores)
            lines.append(f"  ⭐ Score moyen dernières vidéos : {avg_score:.0f}/100")
        lines.append("")
    
    # ── Footer ──
    lines.append("🟢 Alfred opérationnel")
    
    return "\n".join(lines)


# ─── RAPPORT HEBDOMADAIRE COMPLET (script séparé, généré le dimanche) ──

def weekly_trends(yt=None):
    """Bilan des 7 derniers jours (2e message, dimanche)."""
    yt = yt or get_yt_data()
    if not yt:
        return ""
    d = weekly_delta(yt)
    lines = ["Rapport Hebdomadaire"]
    if not d:
        lines.append("  Pas de base J-7 disponible")
    else:
        lines.append("  Vues : " + str(d["vues"]) + " (base " + str(d["base"]) + ", ecart " + str(d["ecart_jours"]) + "j)")
        lines.append("  Abonnes : " + str(d["abonnes"]))
    lines.append("")
    recent = yt.get("recent3") or []
    if recent:
        best = max(recent, key=lambda v: v.get("views", 0))
        lines.append("  Top video : " + str(best.get("title", "?")))
        lines.append("     Vues : " + str(best.get("views", 0)) + " | Likes : " + str(best.get("likes", 0)))
    return "\n".join(lines)


# ─── MAIN ───────────────────────────────────────────────────────────


# ─── ENVOI TELEGRAM ROBUSTE + LOG ───────────────────────────────────
LOG_FILE = Path("/home/ubuntu/output/logs/morning_report.log")
REPORT_STATE_HISTORY_MAX = 40


def log(msg):
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("[" + datetime.now().isoformat(timespec="seconds") + "] " + msg + "\n")
    except Exception:
        pass


def send_telegram(text, label="message"):
    """Envoie PUIS verifie la reponse de l'API Telegram. Retourne True/False.
    Avant : curl -s sans controle -> on affichait 'envoye' meme si l'envoi echouait."""
    bot_token = SECRETS.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = SECRETS.get("TELEGRAM_CHAT_ID", "")
    if not (bot_token and chat_id):
        log("ECHEC " + label + " : TELEGRAM_BOT_TOKEN/CHAT_ID absent")
        print("ATTENTION " + label + " : token Telegram manquant, NON envoye")
        return False
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "20", "-X", "POST",
             "https://api.telegram.org/bot" + bot_token + "/sendMessage",
             "-d", "chat_id=" + chat_id,
             "--data-urlencode", "text=" + text,
             "--data-urlencode", "parse_mode=Markdown"],
            capture_output=True, text=True, timeout=25)
        out = (r.stdout or "").strip()
        if '"ok":true' in out:
            log("OK " + label + " (" + str(len(text)) + " car.)")
            print("OK " + label + " envoye")
            return True
        err = (out or r.stderr or "reponse vide")[:250]
        log("ECHEC " + label + " : " + err)
        print("ECHEC " + label + " NON envoye -> " + err)
        return False
    except Exception as e:
        log("ECHEC " + label + " : exception " + str(e))
        print("ECHEC " + label + " NON envoye (exception " + str(e) + ")")
        return False


# ─── BASE 7 JOURS (le state ne garde qu'un jour) ────────────────────

def weekly_baseline():
    """Reference la plus proche de J-7 : historique du state + yt_stats_history."""
    entries = []
    st = load_json(REPORT_STATE) or {}
    for e in (st.get("history") or []):
        if e.get("date"):
            entries.append({"date": str(e["date"])[:10],
                            "subscribers": e.get("subscribers"),
                            "total_views": e.get("total_views")})
    hist = load_json(STATE_DIR / "yt_stats_history.json")
    if isinstance(hist, list):
        for h in hist:
            d = str(h.get("date", ""))[:10]
            if d:
                entries.append({"date": d,
                                "subscribers": h.get("subscribers"),
                                "total_views": h.get("total_views")})
    if not entries:
        return None, None
    target = datetime.now() - timedelta(days=7)
    best, best_gap = None, None
    for e in entries:
        try:
            dd = datetime.strptime(e["date"], "%Y-%m-%d")
        except Exception:
            continue
        gap = abs((dd - target).days)
        if best_gap is None or gap < best_gap:
            best, best_gap = e, gap
    return best, best_gap


def weekly_delta(yt_data):
    """Delta 7 jours. Avant : comparaison de l'etat du jour avec lui-meme
    (save_current_state appele AVANT weekly_trends) -> toujours +0."""
    base, gap = weekly_baseline()
    if not base:
        return None
    return {"vues": yt_data["total_views"] - (base.get("total_views") or 0),
            "abonnes": yt_data["subscribers"] - (base.get("subscribers") or 0),
            "base": base["date"], "ecart_jours": gap}


def site_analytics_report():
    """Trafic du site. Remplace get_plausible_report/get_gsc_report dont les
    modules (scripts/plausible_stats.py, scripts/gsc_stats.py) n'existent pas :
    ils affichaient une erreur d'import a chaque rapport."""
    st = load_json(STATE_DIR / "analytics" / "latest.json")
    if not st:
        return "Site\n  Pas de donnees (state/analytics/latest.json)"
    lines = ["Site"]
    lines.append("  Hits : " + str(st.get("hits", "?")) + " | Visiteurs : " + str(st.get("visiteurs_uniques", "?")))
    err = (st.get("erreurs_4xx", 0) or 0) + (st.get("erreurs_5xx", 0) or 0)
    if err:
        lines.append("  Erreurs : " + str(err))
    top = st.get("top_pages") or []
    if top:
        lines.append("  Top pages : " + ", ".join(str(t.get("page")) + " (" + str(t.get("vues")) + ")" for t in top[:3]))
    return "\n".join(lines)


def main():
    load_env()
    
    prev_state = load_previous_state()
    yt_data = get_yt_data()
    or_data = get_or_data()
    vps_data = get_vps_data()
    pipeline = get_pipeline_health()
    
    if not yt_data:
        print("❌ Impossible de charger ANALYTICS.json")
        sys.exit(1)
    
    weekday = datetime.now().weekday()
    
    monet = monetization_projection(yt_data)
    advice = generate_advice(yt_data, prev_state)
    
    message = format_telegram(yt_data, or_data, vps_data, prev_state, advice, monet, pipeline, weekday)
    
    # Bilan hebdo calcule AVANT l'ecriture du state (sinon comparaison a soi-meme)
    week = weekly_delta(yt_data) if weekday == 6 else None

    # Envoi avec verification de la reponse API
    send_telegram(message, "Rapport matinal")

    # Etat + historique (base du bilan a 7 jours)
    save_current_state(yt_data, or_data, vps_data)

    # Dimanche : 2e message + state/auto-reflection/weekly-report.json
    if weekday == 6:
        weekly = weekly_trends(yt_data)
        if weekly:
            send_telegram(weekly, "Rapport hebdomadaire")
        if week:
            wr = {
                "last_report": datetime.now().isoformat(),
                "period": str(week["base"]) + "_to_" + datetime.now().strftime("%Y-%m-%d"),
                "subscribers": yt_data["subscribers"],
                "subscribers_week": week["abonnes"],
                "total_views": yt_data["total_views"],
                "views_week": week["vues"],
                "recent3": yt_data.get("recent3", []),
            }
            save_json(WORKSPACE / "state" / "auto-reflection" / "weekly-report.json", wr)
            log("weekly-report.json ecrit (vues " + str(week["vues"]) + ", abonnes " + str(week["abonnes"]) + ")")
    log("run termine (weekday=" + str(weekday) + ")")


if __name__ == "__main__":
    main()
