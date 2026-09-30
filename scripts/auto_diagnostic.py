#!/usr/bin/env python3
"""
auto_diagnostic.py — Auto-diagnostic nocturne
Analyse les logs pipeline, watchdog, erreurs récentes et suggestions d'amélioration.
"""
import json, os, subprocess, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from notify_alfred import send_telegram

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
STATE_DIR = WORKSPACE / "state"
OUTPUT_FILE = STATE_DIR / "auto-reflection" / "nightly_diagnostic.json"

def ensure_dir(path):
    path.parent.mkdir(parents=True, exist_ok=True)

def check_watchdog():
    """Vérifie les alertes watchdog récentes."""
    alerts = []
    wd_file = STATE_DIR / "watchdog_alerts.json"
    if wd_file.exists():
        with open(wd_file) as f:
            try:
                alerts = json.load(f)
            except:
                pass
    
    recent_alerts = [a for a in (alerts if isinstance(alerts, list) else [])
                      if isinstance(a, dict) and 'timestamp' in a]
    return len(recent_alerts)

def check_maintenance():
    """Vérifie l'historique de maintenance."""
    maint_file = STATE_DIR / "maintenance_history.json"
    if maint_file.exists():
        with open(maint_file) as f:
            try:
                return json.load(f)
            except:
                pass
    return None

def check_disk():
    """Vérifie l'espace disque."""
    try:
        result = subprocess.run(
            ["df", "-h", "/"], capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n")
        if len(lines) >= 2:
            parts = lines[1].split()
            if len(parts) >= 5:
                return {
                    "total": parts[1],
                    "used": parts[2],
                    "available": parts[3],
                    "usage_pct": parts[4]
                }
    except:
        pass
    return None

def check_pipeline_logs():
    """Vérifie les logs du pipeline vidéo."""
    issues = []
    log_dir = Path("/home/ubuntu/output/logs")
    if log_dir.exists():
        cutoff = datetime.now().timestamp() - (48 * 3600)
        logs = [f for f in log_dir.glob("*.log") if f.name != "auto_diagnostic.log" and not f.name.startswith("neuro_finance") and f.stat().st_mtime >= cutoff]
        for f in sorted(logs, key=os.path.getmtime, reverse=True):
            from collections import deque
            with open(f, encoding="utf-8", errors="replace") as fh:
                content = "".join(deque(fh, maxlen=100))
            if "ERROR" in content or "error" in content.lower():
                issues.append(str(f.name))
    return issues

# ---------- Controle dataset encore alimente (ajoute le 2026-09-27) ----------
# Pourquoi : le 27/09/2026, on a decouvert que prc_hicp_manr repondait HTTP 200
# avec des donnees FIGEES au 2025-12 (remplace par prc_hicp_minr lors du
# changement de nomenclature ECOICOP v2 du 04/02/2026). Un dataset officiel peut
# etre REMPLACE sans cesser de repondre 200 : le code retour ne suffit donc pas.
# On surveille 3 signaux par dataset :
#   1. le champ updated du JSON-stat (mise a jour de la DIFFUSION),
#   2. la derniere periode publiee (fraicheur de la DONNEE),
#   3. la NON-AVANCE : la derniere periode ne bouge plus entre deux passages
#      alors que la cadence annoncee devrait en produire une nouvelle.

DATASETS = [
    {"id": "prc_hicp_minr", "label": "HICP zone euro v2 (inflation)",
     "url": ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
             "prc_hicp_minr?geo=EA20&unit=RCH_A&coicop18=TOTAL&format=JSON&lastTimePeriod=3"),
     "cadence_days": 31, "max_updated_age_days": 45, "max_period_age_days": 90,
     "critique": True},
    {"id": "namq_10_gdp", "label": "PIB zone euro (croissance)",
     "url": ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
             "namq_10_gdp?geo=EA20&na_item=B1GQ&s_adj=SCA&unit=CLV_PCH_SM&format=JSON&lastTimePeriod=2"),
     "cadence_days": 91, "max_updated_age_days": 120, "max_period_age_days": 220,
     "critique": True},
    {"id": "ei_bssi_m_r2", "label": "ESI sentiment (croissance)",
     "url": ("https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
             "ei_bssi_m_r2?geo=EA21&s_adj=SA&format=JSON&lastTimePeriod=2"),
     "cadence_days": 31, "max_updated_age_days": 45, "max_period_age_days": 90,
     "critique": False},
    {"id": "ecb_dfr", "label": "BCE taux de depot (DFR)",
     "url": ("https://data-api.ecb.europa.eu/service/data/FM/"
             "D.U2.EUR.4F.KR.DFR.LEV?format=csvdata&lastNObservations=3"),
     "cadence_days": 3, "max_updated_age_days": 10, "max_period_age_days": 10,
     "critique": True},
]

DATASET_HIST = STATE_DIR / "dataset_freshness.json"


def _periode_fin_ds(p):
    import re, calendar
    t = str(p or "").strip()
    m = re.match(r"^(\d{4})-Q([1-4])$", t)
    if m:
        y, q = int(m.group(1)), int(m.group(2))
        return datetime(y, q * 3, calendar.monthrange(y, q * 3)[1])
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", t)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^(\d{4})-(\d{2})$", t)
    if m:
        y, mo = int(m.group(1)), int(m.group(2))
        return datetime(y, mo, calendar.monthrange(y, mo)[1])
    m = re.match(r"^(\d{4})$", t)
    if m:
        return datetime(int(m.group(1)), 12, 31)
    return None


def _parse_dt_ds(s):
    if not s:
        return None
    t = str(s).replace("Z", "+0000")
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(t, fmt)
            if dt.tzinfo:
                dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
            return dt
        except ValueError:
            continue
    return None


def _probe_jsonstat(url, timeout=30):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as fp:
        d = json.loads(fp.read())
    if isinstance(d, dict) and d.get("error"):
        raise RuntimeError(str(d["error"])[:90])
    tdim = (d.get("dimension") or {}).get("time") or {}
    periods = list(((tdim.get("category") or {}).get("index") or {}).keys())
    return (d.get("updated") or ""), (sorted(periods)[-1] if periods else None)


def _probe_csv(url, timeout=30):
    import urllib.request, csv, io
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=timeout) as fp:
        txt = fp.read().decode("utf-8", "replace")
    rows = list(csv.DictReader(io.StringIO(txt)))
    if not rows:
        raise RuntimeError("CSV vide")
    periods = [r.get("TIME_PERIOD") for r in rows if r.get("TIME_PERIOD")]
    return None, (sorted(periods)[-1] if periods else None)


def check_datasets_freshness():
    now = datetime.now()
    try:
        hist = json.load(open(DATASET_HIST)) if DATASET_HIST.exists() else {}
    except Exception:
        hist = {}
    out, issues = {}, []
    for ds in DATASETS:
        rec = {"label": ds["label"], "critique": ds["critique"]}
        try:
            if "csvdata" in ds["url"]:
                updated, last = _probe_csv(ds["url"])
            else:
                updated, last = _probe_jsonstat(ds["url"])
            rec["derniere_periode"] = last
            rec["updated"] = updated or None
            dt_up = _parse_dt_ds(updated)
            dt_last = _periode_fin_ds(last)
            rec["age_updated_jours"] = (now - dt_up).days if dt_up else None
            rec["age_periode_jours"] = (now - dt_last).days if dt_last else None
            statut = "ok"
            if (rec["age_periode_jours"] is not None
                    and rec["age_periode_jours"] > ds["max_period_age_days"]):
                statut = "retard"
            if (rec["age_updated_jours"] is not None
                    and rec["age_updated_jours"] > ds["max_updated_age_days"]):
                statut = "fige"
            h = hist.get(ds["id"]) or {}
            if h.get("derniere_periode") and last and h["derniere_periode"] == last:
                seen_since = _parse_dt_ds(h.get("depuis"))
                if seen_since:
                    stale = (now - seen_since).days
                    rec["periode_inchangee_depuis_jours"] = stale
                    if stale > 2 * ds["cadence_days"]:
                        statut = "fige"
                hist[ds["id"]] = {"derniere_periode": last,
                                  "depuis": h.get("depuis"),
                                  "derniere_verif": now.isoformat()}
            else:
                hist[ds["id"]] = {"derniere_periode": last,
                                  "depuis": now.isoformat(),
                                  "derniere_verif": now.isoformat()}
            rec["statut"] = statut
            if statut != "ok":
                sev = "CRITIQUE" if ds["critique"] else "INFO"
                msg = "[" + sev + "] " + ds["label"] + " : " + statut
                if rec["age_periode_jours"] is not None:
                    msg += " | donnee J+" + str(rec["age_periode_jours"])
                if rec["age_updated_jours"] is not None:
                    msg += " | diffusion J+" + str(rec["age_updated_jours"])
                msg += " | derniere periode " + str(last)
                if statut == "fige":
                    msg += " -> DATASET SUSPECT (verifier s il n a pas ete remplace)"
                issues.append(msg)
        except Exception as e:
            rec["statut"] = "indisponible"
            rec["erreur"] = str(e)[:120]
            sev = "CRITIQUE" if ds["critique"] else "INFO"
            issues.append("[" + sev + "] " + ds["label"]
                          + " : INJOIGNABLE (" + str(e)[:70] + ")")
        out[ds["id"]] = rec
    try:
        with open(DATASET_HIST, "w") as f:
            json.dump(hist, f, indent=1)
    except Exception:
        pass
    return {"ok": not issues, "datasets": out, "issues": issues}

# ---------- Controle des sources du pipeline video (ajoute le 2026-09-27) ----------
# Meme logique que check_datasets_freshness : une source qui repond n'est pas
# forcement une source VIVANTE. On surveille ici ce qui alimente la video du jour :
#   1. le snapshot marche (Yahoo/Eurostat/BCE/base ETF) injecte dans le prompt,
#   2. la base ETF du site (couverture prix/perf -> detection de regression),
#   3. la reserve de clips (une niche vide = video impossible),
#   4. l'INVARIANT appris le 2026-09-26 : le referentiel de donnees doit etre
#      injecte dans la GENERATION **et** dans la VERIFICATION du script.

PIPELINE_SNAPSHOT = WORKSPACE / "pipeline" / "data" / "market_snapshot.json"
MARKET_LATEST = WORKSPACE / "data" / "market" / "market_latest.json"
ETF_DATA_JS = WORKSPACE / "web" / "pea-comparator" / "etf-data.js"
ETF_DATA_MIN = WORKSPACE / "web" / "pea-comparator" / "etf-data.min.js"
ETF_DATA_LIVE = Path("/var/www/html/etf-data.min.js")
CLIPS_DIR = Path("/home/ubuntu/output/raw_clips")
ORCHESTRATOR = WORKSPACE / "pipeline" / "pipeline_orchestrator.py"
PIPELINE_HIST = STATE_DIR / "pipeline_sources_history.json"

SNAPSHOT_MAX_AGE_H = 24       # pipeline a 04h, TTL cache snapshot = 12h
MARKET_LATEST_MAX_AGE_D = 4   # quotidien en semaine -> 4 j couvre le week-end
ETF_DATA_MAX_AGE_D = 30       # rafraichi le dimanche (cron 10h) ; filet large
ETF_COVERAGE_DROP_PT = 3.0    # regression de couverture toleree, en points

VIDEO_EXT = (".mp4", ".mov", ".mkv", ".webm", ".avi")


def _age_jours(path):
    if not path.exists():
        return None
    return (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).days


def _check_snapshot_marche(issues):
    rec = {}
    if not PIPELINE_SNAPSHOT.exists():
        rec["statut"] = "absent"
        issues.append("[CRITIQUE] Snapshot marche pipeline : ABSENT ("
                      + str(PIPELINE_SNAPSHOT) + ") -> videos sans donnees reelles")
        return rec
    try:
        snap = json.loads(PIPELINE_SNAPSHOT.read_text(encoding="utf-8"))
    except Exception as e:
        rec["statut"] = "illisible"
        issues.append("[CRITIQUE] Snapshot marche pipeline : ILLISIBLE (" + str(e)[:60] + ")")
        return rec
    built = _parse_dt_ds(snap.get("built_at"))
    age_h = round((datetime.now() - built).total_seconds() / 3600, 1) if built else None
    rec["built_at"] = snap.get("built_at")
    rec["age_heures"] = age_h
    rec["ok_source"] = snap.get("ok")
    rec["stale_source"] = snap.get("stale")
    rec["sources"] = snap.get("sources")
    statut = "ok"
    if age_h is None:
        statut = "inconnu"
    elif age_h > SNAPSHOT_MAX_AGE_H:
        statut = "retard"
    if snap.get("ok") is False:
        statut = "incomplet"
    rec["statut"] = statut
    if statut != "ok":
        issues.append("[CRITIQUE] Snapshot marche pipeline : " + statut
                      + " | age " + str(age_h) + "h (max " + str(SNAPSHOT_MAX_AGE_H) + "h)"
                      + " | ok=" + str(snap.get("ok")) + " stale=" + str(snap.get("stale")))
    return rec


def _check_market_latest(issues):
    rec = {}
    age = _age_jours(MARKET_LATEST)
    rec["age_jours"] = age
    if age is None:
        rec["statut"] = "absent"
        issues.append("[INFO] market_latest.json : ABSENT (collecte marche 05h30)")
        return rec
    rec["statut"] = "ok" if age <= MARKET_LATEST_MAX_AGE_D else "retard"
    if rec["statut"] != "ok":
        issues.append("[CRITIQUE] market_latest.json : RETARD J+" + str(age)
                      + " (max " + str(MARKET_LATEST_MAX_AGE_D) + " j)")
    return rec


def _check_base_etf(issues, hist):
    rec = {}
    if not ETF_DATA_JS.exists():
        rec["statut"] = "absent"
        issues.append("[CRITIQUE] Base ETF : etf-data.js ABSENT")
        return rec
    try:
        c = ETF_DATA_JS.read_text(encoding="utf-8")
        s = c.index("[", c.index("PEA_ETFS"))
        e = c.rindex("]") + 1
        etfs = json.loads(c[s:e])
    except Exception as ex:
        rec["statut"] = "illisible"
        issues.append("[CRITIQUE] Base ETF : ILLISIBLE (" + str(ex)[:60] + ")")
        return rec
    total = len(etfs)
    avec_prix = sum(1 for x in etfs if x.get("prix"))
    avec_perf = sum(1 for x in etfs if x.get("perf5") not in (None, "", "N/A"))
    cov = round(100.0 * avec_prix / total, 1) if total else 0.0
    rec.update({"total": total, "avec_prix": avec_prix, "avec_perf5": avec_perf,
                "couverture_prix_pct": cov, "age_jours": _age_jours(ETF_DATA_JS)})
    statut = "ok"
    if rec["age_jours"] is not None and rec["age_jours"] > ETF_DATA_MAX_AGE_D:
        statut = "retard"
    h = hist.get("etf_base") or {}
    prec = h.get("couverture_prix_pct")
    if prec is not None and (prec - cov) > ETF_COVERAGE_DROP_PT:
        statut = "regression"
        issues.append("[CRITIQUE] Base ETF : REGRESSION de couverture "
                      + str(prec) + "% -> " + str(cov) + "% (" + str(avec_prix) + "/" + str(total) + ")")
    hist["etf_base"] = {"couverture_prix_pct": cov, "total": total,
                        "avec_prix": avec_prix,
                        "derniere_verif": datetime.now().isoformat()}
    try:
        taille_min = ETF_DATA_MIN.stat().st_size if ETF_DATA_MIN.exists() else None
        taille_live = ETF_DATA_LIVE.stat().st_size if ETF_DATA_LIVE.exists() else None
        rec["min_ko"] = taille_min
        rec["live_ko"] = taille_live
        if taille_live is None:
            statut = "desync"
            issues.append("[CRITIQUE] Base ETF : etf-data.min.js ABSENT du site live")
        elif taille_min and taille_live != taille_min:
            statut = "desync"
            issues.append("[INFO] Base ETF : min local (" + str(taille_min)
                          + " o) <> live (" + str(taille_live) + " o) - redeploiement a faire")
    except Exception:
        pass
    rec["statut"] = statut
    if statut == "retard":
        issues.append("[INFO] Base ETF : pas rafraichie depuis J+" + str(rec["age_jours"]))
    return rec


def _check_clips(issues, hist):
    rec = {}
    if not CLIPS_DIR.exists():
        rec["statut"] = "absent"
        issues.append("[CRITIQUE] Reserve de clips : dossier ABSENT")
        return rec
    niches = {}
    total = 0
    for d in sorted(CLIPS_DIR.iterdir()):
        if not d.is_dir():
            continue
        n = sum(1 for f in d.rglob("*") if f.is_file() and f.suffix.lower() in VIDEO_EXT)
        niches[d.name] = n
        total += n
    rec["total_clips"] = total
    rec["niches"] = niches
    vides = [k for k, v in niches.items() if v == 0]
    rec["niches_vides"] = vides
    # Regression : une niche qui AVAIT des clips et n en a plus. Une niche vide
    # depuis toujours est un etat de fait, pas un signal : on ne spamme pas.
    hist_n = (hist.get("clips") or {}).get("niches") or {}
    perdues = [k for k in vides if hist_n.get(k, 0) > 0]
    hist["clips"] = {"total": total, "niches": niches,
                    "derniere_verif": datetime.now().isoformat()}
    rec["niches_perdues"] = perdues
    rec["statut"] = "ok" if total > 0 else "vide"
    if total == 0:
        issues.append("[CRITIQUE] Reserve de clips : AUCUN clip -> pipeline video bloquee")
    elif perdues:
        issues.append("[CRITIQUE] Reserve de clips : niche(s) videe(s) " + ", ".join(perdues))
    return rec


def _check_referentiel_partage(issues):
    # Invariant : le bloc de donnees reelles doit alimenter la GENERATION du script
    # ET la VERIFICATION (fact-check). Lecon du 2026-09-26 : un chiffre du referentiel
    # etait rejete par le validateur parce que celui-ci ne recevait pas le meme
    # referentiel. Ce controle detecte la regression si l'injection cote fact-check disparait.
    rec = {}
    if not ORCHESTRATOR.exists():
        rec["statut"] = "absent"
        issues.append("[INFO] Verif referentiel : orchestrateur introuvable")
        return rec
    txt = ORCHESTRATOR.read_text(encoding="utf-8", errors="ignore")
    gen = "MARKET_DATA_BLOCK" in txt
    verif = "reference_block=MARKET_DATA_BLOCK" in txt
    rec["injecte_generation"] = gen
    rec["injecte_verification"] = verif
    rec["statut"] = "ok" if (gen and verif) else "incoherent"
    if not verif:
        issues.append("[CRITIQUE] Referentiel NON partage : le fact-check ne recoit pas "
                      "MARKET_DATA_BLOCK -> il rejettera des chiffres pourtant sources")
    elif not gen:
        issues.append("[CRITIQUE] Referentiel NON injecte dans la generation du script")
    return rec


def check_pipeline_sources():
    """Verifie que les sources du pipeline video sont fraiches ET coherentes."""
    try:
        hist = json.load(open(PIPELINE_HIST)) if PIPELINE_HIST.exists() else {}
    except Exception:
        hist = {}
    issues = []
    sources = {
        "snapshot_marche": _check_snapshot_marche(issues),
        "market_latest": _check_market_latest(issues),
        "base_etf": _check_base_etf(issues, hist),
        "reserve_clips": _check_clips(issues, hist),
        "referentiel_partage": _check_referentiel_partage(issues),
    }
    try:
        with open(PIPELINE_HIST, "w") as f:
            json.dump(hist, f, indent=1)
    except Exception:
        pass
    crit = [i for i in issues if i.startswith("[CRITIQUE]")]
    return {"ok": not crit, "critiques": len(crit), "sources": sources, "issues": issues}

def run():
    ensure_dir(OUTPUT_FILE)
    
    print("🔧 Auto-diagnostic nocturne...")
    
    diagnostic = {
        "timestamp": datetime.now().isoformat(),
        "watchdog_alerts": check_watchdog(),
        "disk": check_disk(),
        "pipeline_issues": check_pipeline_logs(),
        "datasets": check_datasets_freshness(),
        "pipeline_sources": check_pipeline_sources(),
        "maintenance": check_maintenance(),
        "recommendations": []
    }
    
    # Générer recommandations
    if diagnostic["watchdog_alerts"]:
        diagnostic["recommendations"].append("⚠️ Alertes watchdog détectées — vérifier le VPS")
    if diagnostic["disk"]:
        pct = diagnostic["disk"]["usage_pct"]
        if pct and int(pct.replace("%", "")) > 80:
            diagnostic["recommendations"].append(f"💾 Disque à {pct} — nettoyage recommandé")
    if diagnostic["pipeline_issues"]:
        diagnostic["recommendations"].append(f"🎬 {len(diagnostic['pipeline_issues'])} logs pipeline avec erreurs")
    for _msg in ((diagnostic.get("datasets") or {}).get("issues") or []):
        diagnostic["recommendations"].append("📉 " + _msg)
    for _msg in ((diagnostic.get("pipeline_sources") or {}).get("issues") or []):
        diagnostic["recommendations"].append("📉 " + _msg)
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(diagnostic, f, indent=2)
    
    n = len(diagnostic["recommendations"])
    print(f"✅ Diagnostic terminé — {n} recommandation(s)")
    if n:
        for r in diagnostic["recommendations"]:
            print(f"  {r}")

    # Notification Telegram
    try:
        n = len(diagnostic['recommendations'])
        disk = diagnostic.get('disk', {})
        msg = f"🔧 Auto-diagnostic — {n} recommandation(s)"
        if disk:
            msg += f"\n   💾 Disque: {disk.get('usage_pct', '?')} ({disk.get('used', '?')}/{disk.get('total', '?')})"
        if diagnostic['pipeline_issues']:
            msg += f"\n   🎬 {len(diagnostic['pipeline_issues'])} log(s) avec erreurs"
        if diagnostic['watchdog_alerts']:
            msg += f"\n   ⚠️ {diagnostic['watchdog_alerts']} alerte(s) watchdog"
        if n:
            for r in diagnostic['recommendations'][:3]:
                msg += f"\n   {r}"
        send_telegram(msg)
    except Exception as e:
        print(f'Notif error: {e}', file=sys.stderr)



if __name__ == "__main__":
    import sys as _sys
    if "--no-notify" in _sys.argv:
        # mode test : calcul + JSON, sans envoi Telegram
        globals()["send_telegram"] = lambda *a, **k: print("[notify desactive]")
    run()
