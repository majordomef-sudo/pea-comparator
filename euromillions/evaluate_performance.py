"""
Phase d'Évaluation & Évolution — HYBRIDE ONLY
Compare UNIQUEMENT la grille hybride (predicted_balls/stars) avec les résultats réels.
Stocke l'historique hybride et l'utilise pour l'évolution.
"""
import json
import pandas as pd
import os

BASE_DIR = "/home/ubuntu/.openclaw/workspace/euromillions"
LOG_FILE = os.path.join(BASE_DIR, 'predictions_log.json')
CSV_FILE = os.path.join(BASE_DIR, 'history.csv')
POOL_FILE = os.path.join(BASE_DIR, 'strategy_pool.json')
HYBRID_PERF_FILE = os.path.join(BASE_DIR, 'hybrid_performance.json')


def get_actual_results():
    df = pd.read_csv(CSV_FILE, sep=';')
    df['date_de_tirage'] = pd.to_datetime(df['date_de_tirage'], dayfirst=True)
    actual = {}
    for _, row in df.iterrows():
        d = row['date_de_tirage'].strftime('%Y-%m-%d')
        balls = sorted([int(row[f'boule_{i}']) for i in range(1, 6)])
        stars = sorted([int(row[f'etoile_{i}']) for i in range(1, 3)])
        actual[d] = (balls, stars)
    return actual


def load_hybrid_perf():
    if os.path.exists(HYBRID_PERF_FILE):
        try:
            with open(HYBRID_PERF_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {"history": [], "total_draws": 0, "total_hits": 0}


def save_hybrid_perf(perf):
    with open(HYBRID_PERF_FILE, 'w') as f:
        json.dump(perf, f, indent=2)


def calculate_split_fitness(ball_hits_total, star_hits_total, draws):
    """Calcule les fitness normalisées des boules, étoiles et globale."""
    if draws <= 0:
        return 0.0, 0.0, 0.0
    fitness_balls = ball_hits_total / (5 * draws)
    fitness_stars = star_hits_total / (2 * draws)
    fitness_global = (fitness_balls + fitness_stars) / 2
    return fitness_balls, fitness_stars, fitness_global


def update_population(genome_predictions, actual_balls, actual_stars):
    """Évalue et met à jour chaque génome individuellement."""
    if not os.path.exists(POOL_FILE):
        return
    if not isinstance(genome_predictions, list):
        print("  Ancien format sans genome_id : évaluation individuelle ignorée")
        return
    with open(POOL_FILE, "r") as f:
        pop = json.load(f)
    by_id = {g["id"]: g for g in pop}
    updated = 0
    for prediction in genome_predictions:
        ind = by_id.get(prediction.get("genome_id"))
        if ind is None:
            continue
        ball_hits = len(set(prediction.get("balls", [])) & set(actual_balls))
        star_hits = len(set(prediction.get("stars", [])) & set(actual_stars))
        hits = ball_hits + star_hits
        ind["total_hits"] = ind.get("total_hits", 0) + hits
        ind["draws_evaluated"] = ind.get("draws_evaluated", 0) + 1
        ind["ball_hits_total"] = ind.get("ball_hits_total", 0) + ball_hits
        ind["star_hits_total"] = ind.get("star_hits_total", 0) + star_hits
        ind["split_draws_evaluated"] = ind.get("split_draws_evaluated", 0) + 1
        split_draws = ind["split_draws_evaluated"]
        ind["fitness_balls"], ind["fitness_stars"], ind["fitness"] = calculate_split_fitness(ind["ball_hits_total"], ind["star_hits_total"], split_draws)
        prediction["result"] = {"ball_hits": ball_hits, "star_hits": star_hits, "total": hits}
        updated += 1
    with open(POOL_FILE, "w") as f:
        json.dump(pop, f, indent=2)
    print(f"  {updated} génomes évalués individuellement")
    return pop


def evaluate_and_evolve():
    if not os.path.exists(LOG_FILE):
        print("Aucun registre de prédictions.")
        return
    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        predictions = json.load(f)

    actual = get_actual_results()
    hybrid_perf = load_hybrid_perf()
    total_eval = 0
    newly_evaluated = 0

    for date, pred in sorted(predictions.items()):
        if date not in actual:
            continue
        if pred.get('status') == 'evaluated':
            continue
        pred_balls = pred.get('predicted_balls', [])
        pred_stars = pred.get('predicted_stars', [])
        if not pred_balls or not pred_stars:
            continue
        a_balls, a_stars = actual[date]
        ball_hits = len(set(pred_balls) & set(a_balls))
        star_hits = len(set(pred_stars) & set(a_stars))
        total_hits = ball_hits + star_hits

        pred['status'] = 'evaluated'
        pred['result'] = {
            'ball_hits': ball_hits, 'star_hits': star_hits,
            'total': total_hits, 'actual_balls': a_balls, 'actual_stars': a_stars
        }
        entry = {
            'date': date,
            'predicted_balls': pred_balls, 'predicted_stars': pred_stars,
            'actual_balls': a_balls, 'actual_stars': a_stars,
            'ball_hits': ball_hits, 'star_hits': star_hits, 'total_hits': total_hits
        }
        hybrid_perf["history"].append(entry)
        hybrid_perf['total_draws'] += 1
        hybrid_perf['total_hits'] += total_hits
        update_population(pred.get("genome_predictions", []), a_balls, a_stars)
        newly_evaluated += 1
        total_eval += 1

    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(predictions, f, indent=4)
    save_hybrid_perf(hybrid_perf)

    print(f"Évaluation hybride : {total_eval} tirages ({newly_evaluated} nouveaux)")
    if hybrid_perf['total_draws'] > 0:
        avg = hybrid_perf['total_hits'] / hybrid_perf['total_draws']
        print(f"Perfo hybride : {avg:.2f} hits/tirage ({hybrid_perf['total_hits']} hits / {hybrid_perf['total_draws']} tirages)")
        if hybrid_perf['history']:
            best = max(hybrid_perf['history'], key=lambda x: x['total_hits'])
            print(f"Meilleure : {best['total_hits']} hits le {best['date']}")

    if newly_evaluated > 0:
        from evolution_manager import EvolutionManager
        mgr = EvolutionManager()
        qualified = sum(min(1, g.get("draws_evaluated", 0) // 20) for g in mgr.population)
        if qualified in range(100, len(mgr.population) + 1):
            print(f"Déclenchement de l évolution : {qualified} génomes qualifiés")
            mgr.evolve()
        else:
            mgr.save_population()
            print(f"Évolution différée : {qualified}/100 génomes avec 20 évaluations")


if __name__ == "__main__":
    evaluate_and_evolve()
