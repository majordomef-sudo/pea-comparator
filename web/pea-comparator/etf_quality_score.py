"""
ETF Quality Score v1.0 — Modèle de scoring avec données réelles.

Utilise dic_etf_data_v2.json pour les frais, performances, PEA.
Scoring sur 100 points selon le modèle d'Eric.

Usage:
    python3 etf_quality_score.py --report   # Rapport complet
    python3 etf_quality_score.py --etf ISIN # ETF spécifique
"""

import json, os, re, argparse, sys
from datetime import datetime

# === Constantes ===
BONUS_PEA = 2
BONUS_TER_BAS = 1
MALUS_ENCOURS_FAIBLE = -5

DECISIONS = [(74, "Achat"), (64, "Conserver"), (54, "Surveiller"), (44, "Remplacer"), (0, "Vendre")]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "etf-data.js")
RICH_DATA_PATH = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "output", "dic_etf_data_v2.json")

# Émetteurs
TOP_ISSUERS = ["amundi", "blackrock", "ishares", "hsbc", "bnp"]
GOOD_ISSUERS = ["lyxor", "xtrackers", "vanguard", "spdr"]
FAIR_ISSUERS = ["pictet", "ossiam", "jp morgan"]

# Chargement des données riches
_rich_cache = None

def get_rich_data():
    global _rich_cache
    if _rich_cache is None:
        if os.path.isfile(RICH_DATA_PATH):
            with open(RICH_DATA_PATH) as f:
                data = json.load(f)
            _rich_cache = {e["isin"]: e for e in data if e.get("isin")}
        else:
            _rich_cache = {}
    return _rich_cache


def get_decision(score):
    for threshold, label in DECISIONS:
        if score >= threshold:
            return label
    return "Vendre"


def load_etfs(path=None):
    if path is None:
        path = DATA_PATH
    if not os.path.isfile(path):
        print(f"Fichier non trouvé: {path}")
        return []
    with open(path) as f:
        content = f.read()
    match = re.search(r"window\.PEA_ETFS\s*=\s*(\[.*?\])\s*;", content, re.DOTALL)
    if not match:
        print("Impossible de parser les ETFs")
        return []
    return json.loads(match.group(1))


def parse_frais(val):
    """Parse un string de frais en float."""
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        val = val.strip().replace("%", "").replace(",", ".")
        try:
            return float(val)
        except:
            pass
    return None


def compute_score(etf):
    rich = get_rich_data()
    rich_info = rich.get(etf.get("isin", ""), {})
    
    name = (etf.get("name", "") + " " + etf.get("nom", "")).lower()
    
    result = {
        "isin": etf.get("isin", ""),
        "name": etf.get("name", etf.get("nom", etf.get("isin", ""))),
        "categories": {},
        "bonus": [],
        "malus": [],
        "total": 0,
        "decision": "",
    }
    
    # --- A: Qualite de l'indice (0-25) ---
    idx = 0
    if "world" in name or "global" in name or "msci world" in name or "monde" in name:
        idx += 12
    if "cap" in name and "small" not in name and "mid" not in name:
        idx += 6
    if any(k in name for k in ["ai", "artificial", "ia", "machine", "deep"]):
        idx += 6
    if any(k in name for k in ["semicon", "chip", "semi"]):
        idx += 4
    if "robot" in name:
        idx += 5
    if any(k in name for k in ["energy", "energie", "renew", "solar", "wind"]):
        idx += 3
    # Bonus pour ETF larges
    if any(k in name for k in ["core", "esg", "sri", "climate", "swap"]):
        idx += 2
    if any(k in name for k in ["msci", "stoxx", "euro stoxx", "s&p", "nasdaq"]):
        idx += 6
    result["categories"]["indice"] = min(25, idx)
    
    # --- B: Qualite de replication (0-20) ---
    # Par defaut 12/20, difficile sans tracking difference reelle
    result["categories"]["replication"] = 12
    
    # --- C: Couts (0-15) ---
    ter = None
    # Essayer d'abord ongoing_costs_pct des donnees riches
    raw_ter = rich_info.get("ongoing_costs_pct", "")
    if raw_ter:
        ter = parse_frais(raw_ter)
    # Fallback vers le champ frais des ETFs
    if ter is None:
        ter = parse_frais(etf.get("frais", ""))
    # Fallback 0.30% par defaut
    if ter is None:
        ter = 0.30
    
    if ter < 0.10:
        cost_score = 15
    elif ter < 0.20:
        cost_score = 14
    elif ter < 0.30:
        cost_score = 12
    elif ter < 0.40:
        cost_score = 10
    elif ter < 0.60:
        cost_score = 6
    else:
        cost_score = 3
    result["categories"]["couts"] = cost_score
    
    # --- D: Solidite du fonds (0-15) ---
    enc = etf.get("encours_mio") or 0
    if enc > 0:
        if enc >= 5000:  solid = 14
        elif enc >= 1000: solid = 12
        elif enc >= 300:  solid = 10
        elif enc >= 100:  solid = 8
        else:             solid = 6
        result["categories"]["solidite"] = min(15, solid)
        if enc < 100:
            result["malus"].append(f"AUM faible {int(enc)}M")
    else:
        result["categories"]["solidite"] = 12
    
    # --- E: Emetteur (0-10) ---
    issuer = (etf.get("emetteur", "") + " " + rich_info.get("emetteur", "")).lower()
    if any(i in issuer for i in TOP_ISSUERS):
        issuer_score = 10
    elif any(i in issuer for i in GOOD_ISSUERS):
        issuer_score = 8
    elif any(i in issuer for i in FAIR_ISSUERS):
        issuer_score = 6
    else:
        issuer_score = 5
    result["categories"]["emetteur"] = issuer_score
    
    # --- F: Potentiel Futur (0-15) ---
    future = 0
    if any(k in name for k in ["ai", "artificial", "ia", "machine", "deep", "data"]):
        future += 3
    if any(k in name for k in ["robot", "automation"]):
        future += 3
    if any(k in name for k in ["energy", "energie", "renew", "solar", "wind", "clean"]):
        future += 3
    if any(k in name for k in ["cyber", "security", "safe"]):
        future += 2
    if any(k in name for k in ["space", "spatial", "aerospace", "aero"]):
        future += 2
    if any(k in name for k in ["metal", "mining", "materiaux", "raw", "commodity"]):
        future += 2
    # Les ETF larges ont un potentiel futur intrinsèque
    future = max(8, future + (5 if "world" in name or "global" in name or "monde" in name or "core" in name else 0))
    result["categories"]["futur"] = min(15, future)
    
    # --- Total ---
    base = sum(result["categories"].values())
    total = base
    
    # Bonus PEA
    pea = rich_info.get("eligibilite_pea", "")
    if pea is True or pea == "Oui" or etf.get("pea", "") == "Oui" or etf.get("eligibilite_pea", "") == "Oui":
        total += BONUS_PEA
        result["bonus"].append("PEA")
    
    # Bonus TER < 0.20%
    if ter is not None and ter < 0.20:
        total += BONUS_TER_BAS
        result["bonus"].append("TER<0.20")
    
    result["total"] = max(0, min(100, total))
    result["decision"] = get_decision(result["total"])
    return result


def generate_report(scores):
    sorted_scores = sorted(scores, key=lambda x: x["total"], reverse=True)
    lines = []
    lines.append("=" * 65)
    lines.append(f"ETF QUALITY SCORE v1.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 65)
    lines.append("")
    lines.append(f"{'Score':>5} {'Decision':18s} {'ISIN':13s} {'ETF'}")
    lines.append("-" * 65)
    for s in sorted_scores[:30]:
        isin = s["isin"][:12]
        name = s["name"][:55]
        dec = s["decision"][:16]
        lines.append(f"{s['total']:3d}/100 {dec:16s} {isin:12s} | {name}")
    lines.append("")
    lines.append("-" * 65)
    lines.append(f"Total: {len(scores)} ETFs")
    
    # Stats par decision
    decisions = {}
    for s in scores:
        d = s["decision"]
        decisions[d] = decisions.get(d, 0) + 1
    lines.append("")
    for d, c in sorted(decisions.items(), key=lambda x: -x[1]):
        lines.append(f"  {d}: {c}")
    
    # Stats categories
    lines.append("")
    lines.append("Moyennes par categorie:")
    cat_max = {"indice": 25, "replication": 20, "couts": 15, "solidite": 15, "emetteur": 10, "futur": 15}
    for cat, maximum in cat_max.items():
        vals = [s["categories"].get(cat, 0) for s in scores]
        avg = sum(vals) / len(vals) if vals else 0
        lines.append(f"  {cat}: {avg:.1f}/{maximum}")
    
    return chr(10).join(lines)


def main():
    parser = argparse.ArgumentParser(description="ETF Quality Score v1.0")
    parser.add_argument("--etf", "-e", help="ISIN specifique")
    parser.add_argument("--report", "-r", action="store_true", help="Rapport complet")
    parser.add_argument("--output", "-o", default="", help="Fichier JSON sortie")
    parser.add_argument("--emit-scores", "--emit", action="store_true", help="Ecrit etf-scores.js deployable")
    args = parser.parse_args()
    
    etfs = load_etfs()
    if not etfs:
        print("Aucun ETF charge")
        return
    
    print(f"{len(etfs)} ETFs charges")
    
    if args.etf:
        etfs = [e for e in etfs if e.get("isin", "") == args.etf]
        if not etfs:
            print(f"ETF {args.etf} non trouve")
            return
    
    scores = [compute_score(e) for e in etfs]
    
    if args.report:
        report = generate_report(scores)
        print(report)
        rpath = os.path.expanduser("~/output/logs/etf_quality_score_report.txt")
        with open(rpath, "w") as f:
            f.write(report)
        print(f"\nRapport sauvegarde: {rpath}")
    
    if args.output:
        with open(args.output, "w") as f:
            json.dump(scores, f, indent=2, ensure_ascii=False)
        print(f"Scores sauvegardes: {args.output}")

    if args.emit_scores:
        # Ecrit etf-scores.js (source) puis deploie sur /var/www/html + bump cache-bust dans index.html
        src_path = os.path.join(BASE_DIR, "etf-scores.js")
        emit_scores_js(scores, src_path)
        os.system("sudo cp " + src_path + " /var/www/html/etf-scores.js")
        from datetime import datetime as _dt
        import re as _re
        newhash = str(int(_dt.now().timestamp()))
        for ip in (os.path.join(BASE_DIR, "index.html"), "/var/www/html/index.html"):
            try:
                h = open(ip, encoding="utf-8").read()
            except PermissionError:
                import subprocess as _sp
                h = _sp.run(["sudo", "cat", ip], capture_output=True, text=True).stdout
            m = _re.search(r"etf-scores\.js\?v=[0-9]+", h)
            if m:
                h2 = h.replace(m.group(0), "etf-scores.js?v=" + newhash)
                if h2 != h:
                    src_tmp = os.path.join("/tmp", ".scores.tmp")
                    open(src_tmp, "w", encoding="utf-8").write(h2)
                    os.system("sudo cp " + src_tmp + " " + ip)
                    os.remove(src_tmp)
                    print("  cache-bust: etf-scores.js?v=" + newhash + " (" + ip.split("/")[-1] + ")")
        print(f"etf-scores.js deploye ({len(scores)} scores)")
    
    if not args.report and not args.etf:
        sorted_scores = sorted(scores, key=lambda x: x["total"], reverse=True)
        print(f"\n{'Score':>5} {'Decision':18s} {'ETF'}")
        print("-" * 70)
        for s in sorted_scores[:10]:
            print(f"{s['total']:3d}/100 {s['decision']:16s} {s['name'][:45]}")


def emit_scores_js(scores, path):
    from datetime import datetime
    lines = ["// ETF Quality Scores - Auto-generated by Alfred",
             "// Updated: " + datetime.now().strftime("%Y-%m-%d"),
             "window.ETF_SCORES = " + json.dumps(scores, ensure_ascii=False) + ";"]
    content = chr(10).join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return content


if __name__ == "__main__":
    main()
