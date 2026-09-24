"""
Analyse & Prédictions Évolutionnaires
1. Utilise les meilleurs génomes de la population
2. Génère des prédictions pour TOUS les génomes (pour l'évaluation future)
3. Sélectionne les meilleures grilles pour le rapport utilisateur
"""
import csv
import pickle
import numpy as np
import pandas as pd
from collections import Counter
import random
import json
import os
import datetime as dt

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from euromillions.strategy_engine import StrategyEngine
from euromillions.evolution_manager import EvolutionManager
from euromillions.antifoule import generate_antifoule_grid, describe as antifoule_describe

BASE_DIR = "/home/ubuntu/.openclaw/workspace/euromillions"
HISTORY_FILE = os.path.join(BASE_DIR, 'history.csv')
RESULTS_FILE = os.path.join(BASE_DIR, 'analysis_results.json')
LOG_FILE = os.path.join(BASE_DIR, 'predictions_log.json')
LAST_ANALYSIS_TXT = os.path.join(BASE_DIR, 'last_analysis.txt')
VERDICT_FILE = os.path.join(BASE_DIR, "benchmark_verdict.json")

def is_promotion_allowed(verdict, now=None):
    """Valide un verdict récent, suffisant et statistiquement fiable."""
    try:
        now = now or dt.datetime.now(dt.timezone.utc)
        updated_at = dt.datetime.fromisoformat(verdict["updated_at"].replace("Z", "+00:00")).astimezone(dt.timezone.utc)
        age = now - updated_at
        return bool(age >= dt.timedelta(0) and age <= dt.timedelta(days=14) and verdict.get("n_draws", 0) >= 100 and verdict.get("promotion_allowed") is True and verdict.get("recommended_mode") == "experimental" and verdict.get("reliable_advantage") is True)
    except (KeyError, TypeError, ValueError):
        return False


def analyze():
    # 1. Initialisation
    engine = StrategyEngine()
    evo_mgr = EvolutionManager()

    # 2. Collecte des données de base
    main_nums = []
    stars = []
    try:
        with open(HISTORY_FILE, mode='r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=';')
            for row in reader:
                for i in range(1, 6):
                    val = row.get(f'boule_{i}')
                    if val: main_nums.append(int(val))
                for i in range(1, 3):
                    val = row.get(f'etoile_{i}')
                    if val: stars.append(int(val))
    except Exception as e:
        print(f"Error reading history: {e}")
        return

    # 3. Préparation du pool de numéros (pour la correction combinatoire)
    main_counts = Counter(main_nums)
    top_20_main = [num for num, freq in main_counts.most_common(20)]
    full_pool = list(range(1, 51))

    # 4. Génération des prédictions pour TOUTE la population
    # On enregistre tout dans le log pour pouvoir évaluer la fitness plus tard
    population = evo_mgr.population

    # 5. Sélection des meilleures grilles pour l'utilisateur (TOP GENOMES)
    top_genomes = evo_mgr.get_top_genomes(10) # On regarde les 10 meilleurs

    # On crée 4 stratégies basées sur les top génomes
    # Stratégie 1: CHAMPION (best fitness — favorise maturité/gaps)
    champion = top_genomes[0]
    best_balls = engine.generate(champion, full_pool=full_pool)
    best_stars = engine.generate_stars(champion)

    # Stratégie 2: CHALLENGER (2ème meilleure fitness, angle différent)
    challenger = top_genomes[1] if len(top_genomes) > 1 else champion
    chall_balls = engine.generate(challenger, full_pool=full_pool)
    chall_stars = engine.generate_stars(challenger)

    # Stratégie 3: EXPLORATION (génome aléatoire pour diversification)
    explorer = random.choice(population)
    exp_balls = engine.generate(explorer, full_pool=full_pool)
    exp_stars = engine.generate_stars(explorer)

    # Stratégie 4: HYBRIDE v2 (VOTE bagging top 5 - robuste au bruit)
    vote_counter = Counter()
    star_vote_counter = Counter()
    for g in top_genomes[:5]:
        vote_counter.update(engine.generate(g, full_pool=full_pool))
        star_vote_counter.update(engine.generate_stars(g))
    hyb_balls = sorted([n for n, _ in vote_counter.most_common(5)])
    hyb_stars = sorted([n for n, _ in star_vote_counter.most_common(2)])
    if len(set(hyb_balls)) < 5 or len(set(hyb_stars)) < 2:
        hyb_balls = sorted(random.Random(42).sample(range(1, 51), 5))
        hyb_stars = sorted(random.Random(42).sample(range(1, 13), 2))

    # 6.5 Grille anti-foule v2 (anti-partage) - DETERMINISTE par date de tirage
    today = dt.date.today()
    weekday = today.weekday()
    if weekday < 1: days_until = 1 - weekday
    elif weekday < 4: days_until = 4 - weekday
    else: days_until = (7 - weekday) + 1
    next_draw_date = (today + dt.timedelta(days=days_until)).isoformat()
    production_seed = int(next_draw_date.replace("-", ""))
    history_last = None
    try:
        with open(HISTORY_FILE, encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh, delimiter=";"))
        if rows:
            def _row_date(r):
                try:
                    return dt.datetime.strptime(r.get("date_de_tirage", ""), "%d/%m/%Y")
                except Exception:
                    return dt.datetime.min
            last_row = max(rows, key=_row_date)
            history_last = [int(last_row["boule_" + str(i)]) for i in range(1, 6)]
    except Exception as e:
        print("Anti-foule : historique indisponible (" + str(e) + ")")
    af_balls, af_stars = generate_antifoule_grid(seed=production_seed, history_last=history_last)
    af_meta = antifoule_describe(af_balls, af_stars, history_last)

    # 6. Génération de la couverture (basez sur le top 3)
    coverage_pool = list(set(best_balls + chall_balls + exp_balls))
    coverage_grilles = []
    for i in range(3):
        # On utilise un génome aléatoire pour chaque grille de couverture
        cov_genome = random.choice(population)
        g = engine.generate(cov_genome, full_pool=full_pool)
        s = engine.generate_stars(cov_genome)
        coverage_grilles.append({"balls": g, "stars": s})

    # 7. Enregistrement dans le log (pour l'évolution)
    uniform_balls = engine.generate_uniform(production_seed)
    uniform_stars = engine.generate_uniform_stars(production_seed)
    production_mode = "uniform"
    production_balls = uniform_balls
    production_stars = uniform_stars
    if os.path.exists(VERDICT_FILE):
        try:
            with open(VERDICT_FILE, "r", encoding="utf-8") as f:
                verdict = json.load(f)
            if is_promotion_allowed(verdict):
                production_mode = "experimental"
                production_balls = hyb_balls
                production_stars = hyb_stars
            else:
                print("Promotion non autorisée : maintien du mode uniforme")
        except Exception as e:
            print(f"Verdict invalide, maintien du mode uniforme : {e}")

    log_data = {}
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r') as f:
            try: log_data = json.load(f)
            except: log_data = {}

    existing = log_data.get(next_draw_date, {})
    if existing.get("status") == "pending":
        print(f"Prédiction déjà enregistrée pour {next_draw_date} : conservation sans écrasement")
        return
    genome_predictions = [{"genome_id": g["id"], "balls": engine.generate(g, full_pool=full_pool), "stars": engine.generate_stars(g)} for g in population]
    log_data[next_draw_date] = {
        "predicted_balls": production_balls,
        "predicted_stars": production_stars,
        "production_mode": production_mode,
        "experimental_hybrid": {"balls": hyb_balls, "stars": hyb_stars},
        "antifoule": {"balls": af_balls, "stars": af_stars, **af_meta},
        "genome_predictions": genome_predictions,

        "timestamp": dt.datetime.now().isoformat(),
        "status": "pending"
    }
    with open(LOG_FILE, 'w') as f:
        json.dump(log_data, f, indent=4)

    # 8. Sauvegarde des résultats pour le rapport utilisateur
    results = {
        "champion": {"balls": best_balls, "stars": best_stars},
        "challenger": {"balls": chall_balls, "stars": chall_stars},
        "exploration": {"balls": exp_balls, "stars": exp_stars},
        "hybrid": {"balls": hyb_balls, "stars": hyb_stars},
        "production": {"mode": production_mode, "balls": production_balls, "stars": production_stars},
        "coverage": coverage_grilles,
        "antifoule": {"balls": af_balls, "stars": af_stars, **af_meta},
        "production_antifoule": {"mode": "antifoule", "balls": af_balls, "stars": af_stars, **af_meta}
    }
    with open(RESULTS_FILE, 'w') as f:
        json.dump(results, f, indent=4)

    # 9. Sauvegarde de la population pour l'évolution continue
    evo_mgr.save_population()

    # 10. Affichage console
    print("\n--- Prédictions Évolutionnaires (Génération {}) ---".format(evo_mgr.generation))
    print(f"Champion : {best_balls} | {best_stars}")
    print(f"Challenger : {chall_balls} | {chall_stars}")
    print(f"Exploration : {exp_balls} | {exp_stars}")
    print(f"Hybride : {hyb_balls} | {hyb_stars}")

    # Ecriture du rapport texte pour Telegram (si on n'utilise pas directement le JSON)
    report_lines = [
        f"\n--- Prédictions Évolutionnaires (Gén {evo_mgr.generation}) ---",
        f"Champion : {best_balls} | {best_stars}",
        f"Challenger : {chall_balls} | {chall_stars}",
        f"Exploration : {exp_balls} | {exp_stars}",
        f"Hybride : {hyb_balls} | {hyb_stars}",
        "\n--- 🌟 Couverture ---"
    ]
    for i, g in enumerate(coverage_grilles, 1):
        report_lines.append(f"Grille {i} : {g['balls']} | {g['stars']}")
    report_lines.append("\n---  Anti-Foule (anti-partage) ---")
    report_lines.append(f"Grille Anti-Foule : {af_balls} | {af_stars}")

    with open(LAST_ANALYSIS_TXT, 'w', encoding='utf-8') as f:
        f.write("\n".join(report_lines))

if __name__ == "__main__":
    analyze()
