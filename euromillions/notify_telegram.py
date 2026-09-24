"""Notifications Telegram pour le pipeline Euromillions.
Utilise le module partage scripts.notify_alfred pour envoyer les
predictions et resultats sur Telegram.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from scripts.notify_alfred import send_telegram
import json
import pickle
import pandas as pd
import numpy as np
from datetime import datetime

BASE_DIR = "/home/ubuntu/.openclaw/workspace/euromillions"
HISTORY_FILE = os.path.join(BASE_DIR, 'history.csv')
STATS_FILE = os.path.join(BASE_DIR, 'advanced_stats.pkl')
RESULTS_FILE = os.path.join(BASE_DIR, 'analysis_results.json')
LOG_FILE = os.path.join(BASE_DIR, 'predictions_log.json')
SECRETS_PATH = '/home/ubuntu/.secrets/env'

def load_secrets():
    secrets = {}
    if os.path.exists(SECRETS_PATH):
        with open(SECRETS_PATH, 'r') as f:
            for line in f:
                if '=' in line:
                    k, v = line.strip().split('=', 1)
                    if k.startswith('export '):
                        k = k[7:]
                    secrets[k] = v.strip('"').strip("'")
    return secrets

def get_last_draw():
    try:
        df = pd.read_csv(HISTORY_FILE, sep=';')
        df['date_de_tirage'] = pd.to_datetime(df['date_de_tirage'], dayfirst=True)
        df = df.sort_values('date_de_tirage')
        last = df.iloc[-1]
        date = pd.to_datetime(last['date_de_tirage']).strftime('%d/%m/%Y')
        balls = [int(last[f'boule_{i}']) for i in range(1, 6)]
        stars = [int(last[f'etoile_{i}']) for i in range(1, 3)]
        return date, balls, stars
    except:
        return None, None, None

def get_mature_numbers(n=5):
    try:
        with open(STATS_FILE, 'rb') as f:
            stats = pickle.load(f)
        gaps = stats['current_gaps']
        avg_gaps = stats['average_gaps']
        
        scores = []
        for b in range(1, 51):
            score = gaps[b] / avg_gaps[b] if avg_gaps[b] > 0 else 0
            scores.append((b, score, gaps[b], avg_gaps[b]))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:n]
    except:
        return []

def get_mature_stars(n=3):
    """Retourne le top N étoiles les plus 'mûres' via le pickle centralisé."""
    try:
        with open(STATS_FILE, 'rb') as f:
            stats = pickle.load(f)
        star_gaps = stats.get('star_current_gaps', {})
        star_avg_gaps = stats.get('star_average_gaps', {})
        scores = []
        for s in range(1, 13):
            gap = star_gaps.get(s, 5)
            avg = star_avg_gaps.get(s, 5)
            score = gap / avg if avg > 0 else 0
            scores.append((s, score, gap, avg))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:n]
    except:
        return []

def pick_best_grid(results):
    """Sélectionne la meilleure grille unique parmi les stratégies disponibles."""
    # Priorité : hybrid > champion > challenger > exploration (qualité décroissante)
    order = ["hybrid", "champion", "challenger", "exploration"]
    for key in order:
        entry = results.get(key, {})
        balls = entry.get('balls', [])
        stars = entry.get('stars', [])
        if balls and stars:
            return key, balls, stars
    return None, [], []

def get_performance():
    """Lit uniquement les performances déjà évaluées, sans modifier le journal."""
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            log = json.load(f)
    except Exception as e:
        print(f"Erreur lecture performances : {e}")
        return 0, 0, 0, []

    total_found = 0
    total_draws = 0
    best_hit = 0
    recent_hits = []

    for date, pred in sorted(log.items(), reverse=True):
        if pred.get("status") != "evaluated":
            continue
        result = pred.get("result", {})
        ball_hits = int(result.get("ball_hits", 0))
        star_hits = int(result.get("star_hits", 0))
        total = int(result.get("total", ball_hits + star_hits))
        total_found += total
        total_draws += 1
        best_hit = max(best_hit, total)
        if len(recent_hits) != 5:
            recent_hits.append((date, ball_hits, star_hits, total))

    return total_draws, total_found, best_hit, recent_hits

def pick_production_grid(results):
    """Grille de PRODUCTION = celle validee par le benchmark (mode uniform).
    Les grilles evolutionnaires ne sont PAS recommandees (aucun avantage demontre)."""
    prod = results.get("production", {})
    if prod.get("balls") and prod.get("stars"):
        return prod.get("mode", "uniform"), prod["balls"], prod["stars"]
    af = results.get("antifoule", {})
    if af.get("balls") and af.get("stars"):
        return "antifoule", af["balls"], af["stars"]
    return None, [], []


def get_verdict_summary():
    try:
        with open(os.path.join(BASE_DIR, "benchmark_verdict.json"), encoding="utf-8") as f:
            v = json.load(f)
        return {
            "reliable": bool(v.get("reliable_advantage")),
            "avg_p": v.get("avg_p_value"),
            "n_draws": v.get("n_draws"),
            "mode": v.get("recommended_mode"),
            "date": str(v.get("updated_at", ""))[:10],
        }
    except Exception:
        return None


MODE_LABELS = {
    "uniform": "aleatoire equilibre (seul mode valide par le benchmark)",
    "antifoule": "anti-partage (optimisation de l'esperance)",
}

BT = chr(96)


def code(vals):
    return BT + " \u2022 ".join(map(str, vals)) + BT


def build_report():
    results = None
    try:
        with open(RESULTS_FILE, "r") as f:
            results = json.load(f)
    except Exception:
        pass

    last_date, last_balls, last_stars = get_last_draw()
    mature = get_mature_numbers(5)
    total_draws, total_found, best_hit, recent_hits = get_performance() if results else (0, 0, 0, [])
    verdict = get_verdict_summary()

    pool_file = os.path.join(BASE_DIR, "strategy_pool.json")
    pop_fitness = None
    if os.path.exists(pool_file):
        try:
            with open(pool_file, "r") as f:
                pool = json.load(f)
            fitnesses = [g.get("fitness", 0) for g in pool if g.get("fitness", 0) > 0]
            if fitnesses:
                pop_fitness = {
                    "size": len(pool),
                    "avg": sum(fitnesses) / len(fitnesses),
                    "max": max(fitnesses),
                }
        except Exception:
            pass

    lines = ["\U0001F3A9 *Rapport Euromillions*\n"]

    if last_date:
        lines.append("\U0001F4C5 *Dernier tirage* (" + str(last_date) + ")")
        lines.append("   Boules : " + code(last_balls) + "  \u2b50 " + code(last_stars) + "\n")

    if results:
        mode, prod_balls, prod_stars = pick_production_grid(results)
        if prod_balls:
            lines.append("\U0001F3AF *Grille recommandee* — " + MODE_LABELS.get(mode, mode))
            lines.append("  " + code(prod_balls) + "  \u2b50 " + code(prod_stars) + "\n")

        af = results.get("antifoule", {})
        af_balls, af_stars = af.get("balls", []), af.get("stars", [])
        if af_balls:
            lines.append("\U0001F525 *Grille anti-partage* (meme chance de gagner, partage reduit)")
            lines.append("  " + code(af_balls) + "  \u2b50 " + code(af_stars))
            if af.get("popularity_score"):
                lines.append("  popularite " + str(af["popularity_score"]) + " (1.0 = grille moyenne) → esperance estimee "
                             + str(af.get("unpopularity_gain_pct", 0)) + "%")
            lines.append("")

        if verdict and not verdict["reliable"]:
            p = verdict.get("avg_p")
            p_txt = ("p=" + format(p, ".2f")) if isinstance(p, (int, float)) else "p non concluant"
            lines.append("\u26a0\ufe0f *Evolution : aucun avantage demontre* (" + p_txt + ", verdict du " + str(verdict["date"]) + ")")
            lines.append("  Grilles de recherche ci-dessous — suivi experimental uniquement.\n")

        lines.append("\U0001F52C *Grilles de recherche*")
        for key, label in [("champion", "\U0001F3C6 CHAMPION"), ("challenger", "\u2694\ufe0f CHALLENGER"),
                           ("exploration", "\U0001F9ED EXPLORATION"), ("hybrid", "\U0001F9EC HYBRIDE")]:
            entry = results.get(key, {})
            balls, stars = entry.get("balls", []), entry.get("stars", [])
            if balls:
                lines.append("  " + label + " — " + code(balls) + " \u2b50 " + code(stars))

    if mature:
        lines.append("\n\u23f3 *Top 5 numeros murs*  _(indicatif, aucun pouvoir predictif demontre)_")
        for num, score, gap, avg in mature:
            lines.append("  #" + str(num) + "  —  ecart " + str(int(gap)) + " tirages (moy. " + format(avg, ".0f") + ")")

    mature_stars = get_mature_stars(3)
    if mature_stars:
        lines.append("\n\u23f3 *Top 3 etoiles mures*")
        for num, score, gap, avg in mature_stars:
            lines.append("  \u2b50" + str(num) + "  —  ecart " + str(int(gap)) + " tirages (moy. " + format(avg, ".0f") + ")")

    if total_draws > 0:
        avg_hit = total_found / total_draws
        lines.append("\n\U0001F4C8 *Performance historique (mode production)*")
        lines.append("  " + str(total_draws) + " tirages evalues  —  " + str(total_found) + " numeros trouves")
        lines.append("  Moy. " + format(avg_hit, ".1f") + "/tirage  —  Meilleur " + str(best_hit) + " bons")

    if pop_fitness:
        lines.append("\n\U0001F9EC *Population (recherche)*")
        lines.append("  " + str(pop_fitness["size"]) + " genomes  —  fitness moy. "
                     + format(pop_fitness["avg"], ".2f") + " (max " + format(pop_fitness["max"], ".2f") + ")")

    lines.append("\n---\n_\U0001F9EC Pipeline v4 Evolutionnaire \u2022 " + datetime.now().strftime("%d/%m/%Y %H:%M") + "_")
    return "\n".join(lines)


if __name__ == "__main__":
    report = build_report()
    print(report)
    send_telegram(report)
