#!/usr/bin/env python3
"""
Euromillions Benchmark Harness
Evaluates the prediction system against historical draws.
B_dev: last 67 draws (for development iteration)
B_test: last 20 draws (final holdout, separated from B_dev)

Scoring (0-100):
  Score = (total_best_hits / (n_draws * 7)) * 307
  This normalizes so baseline ~87.8/100 with ~2.0 avg best hits.
  At ~2.1 avg best hits → ~92/100.

  Also tracks: hit_rate, diversity, avg_best_hits for diagnostics.

Usage:
    python3 euromillions/run_benchmark.py --mode dev [--run-name NAME]
    python3 euromillions/run_benchmark.py --mode test [--run-name NAME]
"""

import argparse, json, os, sys, copy, random, math, pickle
import numpy as np
import pandas as pd
from collections import Counter

BASE_DIR = "/home/ubuntu/.openclaw/workspace/euromillions"
HISTORY_FILE = os.path.join(BASE_DIR, 'history.csv')
VERDICT_FILE = os.path.join(BASE_DIR, "benchmark_verdict.json")

sys.path.insert(0, os.path.join(BASE_DIR, '..'))
from euromillions.strategy_engine import StrategyEngine
from euromillions.evolution_manager import EvolutionManager

COMBINATION_PROFILES = {"poisson_reversion": {"weight_poisson": 1.0, "weight_mean_reversion": 1.0}}

ABLATION_PROFILES = {
    "maturity": "weight_maturity",
    "poisson": "weight_poisson",
    "mean_reversion": "weight_mean_reversion",
    "bayesian": "weight_bayesian",
    "correlation": "weight_correlation",
    "random": "weight_random"
}

random.seed(42)
np.random.seed(42)


def load_draws():
    df = pd.read_csv(HISTORY_FILE, sep=';')
    df['date_de_tirage'] = pd.to_datetime(df['date_de_tirage'], dayfirst=True)
    df = df.sort_values('date_de_tirage')
    draws = []
    for _, row in df.iterrows():
        balls = sorted([int(row[f'boule_{i}']) for i in range(1, 6)])
        stars = sorted([int(row[f'etoile_{i}']) for i in range(1, 3)])
        date_str = row['date_de_tirage'].strftime('%Y-%m-%d')
        draws.append({'date': date_str, 'balls': balls, 'stars': stars, 'ball_set': set(balls), 'star_set': set(stars)})
    return draws


def compute_stats_from_draws(train_draws):
    all_balls = [d['balls'] for d in train_draws]
    all_stars = [d['stars'] for d in train_draws]
    history_matrix = np.array(all_balls)
    gaps, avg_gaps = {}, {}
    for b in range(1, 51):
        last_seen, current_gap, all_gaps = -1, 0, []
        for row in history_matrix:
            if b in row:
                if last_seen != -1: all_gaps.append(current_gap)
                last_seen, current_gap = 1, 0
            else: current_gap += 1
        gaps[b] = current_gap
        avg_gaps[b] = np.mean(all_gaps) if all_gaps else 50

    # Star gaps and averages
    star_gaps, star_avg_gaps = {}, {}
    for s in range(1, 13):
        last_seen, current_gap, all_gaps = -1, 0, []
        for row in all_stars:
            if s in row:
                if last_seen != -1: all_gaps.append(current_gap)
                last_seen, current_gap = 1, 0
            else: current_gap += 1
        star_gaps[s] = current_gap
        star_avg_gaps[s] = np.mean(all_gaps) if all_gaps else 12

    # Ball-ball correlation
    matrix = np.zeros((51, 51))
    for row in history_matrix:
        for i in range(5):
            for j in range(i + 1, 5):
                b1, b2 = row[i], row[j]
                matrix[b1][b2] += 1; matrix[b2][b1] += 1

    # Star-ball correlation: star_ball_corr[s][b] = co-occurrence count
    star_ball_corr = np.zeros((13, 51), dtype=np.float64)
    for draw_idx in range(len(all_balls)):
        balls = all_balls[draw_idx]
        stars = all_stars[draw_idx]
        for s in stars:
            for b in balls:
                star_ball_corr[s][b] += 1.0

    return {
        "current_gaps": gaps,
        "average_gaps": avg_gaps,
        "correlation_matrix": matrix,
        "star_current_gaps": star_gaps,
        "star_average_gaps": star_avg_gaps,
        "star_ball_correlation": star_ball_corr,
    }


def compute_prediction_diversity(grids):
    if not grids: return 0
    all_balls = []
    for g in grids: all_balls.extend(g['balls'])
    unique_balls = len(set(all_balls))
    total_slots = len(grids) * 5
    return unique_balls / min(50, total_slots) * 100


def generate_random_predictions(count, rng):
    """Génère une référence aléatoire équitable."""
    return [{"balls": sorted(rng.sample(range(1, 51), 5)), "stars": sorted(rng.sample(range(1, 13), 2))} for _ in range(count)]

def evaluate_random_baseline(actual_draw, grid_count, runs=1000, seed=42):
    """Évalue plusieurs portefeuilles aléatoires équivalents."""
    rng = random.Random(seed)
    best_hits = []
    average_hits = []
    for _ in range(runs):
        predictions = generate_random_predictions(grid_count, rng)
        result = evaluate_predictions(predictions, actual_draw)
        best_hits.append(result["best_total_hits"])
        average_hits.append(result["avg_total_hits"])
    return {
        "best_mean": float(np.mean(best_hits)),
        "best_std": float(np.std(best_hits, ddof=1)),
        "average_mean": float(np.mean(average_hits)),
        "average_std": float(np.std(average_hits, ddof=1)),
        "runs": runs
    }



def evaluate_predictions(predictions, actual_draw):
    actual_balls, actual_stars = set(actual_draw['balls']), set(actual_draw['stars'])
    results = []
    for pred in predictions:
        ball_hits = len(set(pred['balls']) & actual_balls)
        star_hits = len(set(pred['stars']) & actual_stars)
        results.append({'ball_hits': ball_hits, 'star_hits': star_hits, 'total_hits': ball_hits + star_hits})
    best = max(results, key=lambda r: r['total_hits'])
    hit_rate_avg = np.mean([r['total_hits'] / 7 * 100 for r in results])
    diversity = compute_prediction_diversity(predictions)
    return {'best_ball_hits': best['ball_hits'], 'best_star_hits': best['star_hits'],
            'best_total_hits': best['total_hits'],
            'avg_total_hits': np.mean([r['total_hits'] for r in results]),
            'avg_hit_rate': hit_rate_avg, 'diversity': diversity}


def run_draw_evaluation(train_draws, eval_draw, genome_population):
    stats = compute_stats_from_draws(train_draws)
    engine = StrategyEngine()
    engine.stats = stats
    engine.gaps = stats["current_gaps"]
    engine.avg_gaps = stats["average_gaps"]
    engine.corr = stats["correlation_matrix"]
    engine.star_gaps = stats["star_current_gaps"]
    engine.star_avg_gaps = stats["star_average_gaps"]
    engine.total_draws = len(train_draws)
    evaluated = [ind for ind in genome_population if ind.get('draws_evaluated', 0) > 0]
    sorted_genomes = sorted(evaluated, key=lambda x: x.get('fitness', 0), reverse=True) if evaluated else genome_population
    top_genomes = sorted_genomes[:10]
    
    predictions = []
    for genome in top_genomes:
        balls = engine.generate(genome)
        stars = engine.generate_stars(genome)
        predictions.append({'balls': balls, 'stars': stars})
    
    hybrid_genes = {}
    for name, _, _, default in EvolutionManager.GENES_META:
        vals = [g['genes'].get(name, default) for g in top_genomes[:5]]
        hybrid_genes[name] = np.mean(vals)
    hybrid_genome = {"genes": hybrid_genes, "seed": random.randint(0, 1000)}
    predictions.append({'balls': engine.generate(hybrid_genome), 'stars': engine.generate_stars(hybrid_genome)})
    
    uniform_predictions = [{"balls": engine.generate_uniform(int(eval_draw["date"].replace("-", "")) + i), "stars": engine.generate_uniform_stars(int(eval_draw["date"].replace("-", "")) + i)} for i in range(len(predictions))]
    uniform_result = evaluate_predictions(uniform_predictions, eval_draw)
    eval_result = evaluate_predictions(predictions, eval_draw)
    baseline = evaluate_random_baseline(eval_draw, len(predictions), runs=1000, seed=int(eval_draw["date"].replace("-", "")))
    eval_result["random_best_total_hits"] = baseline["best_mean"]
    eval_result["random_avg_total_hits"] = baseline["average_mean"]
    eval_result["uniform_best_total_hits"] = uniform_result["best_total_hits"]
    eval_result["uniform_avg_total_hits"] = uniform_result["avg_total_hits"]
    eval_result["random_best_std"] = baseline["best_std"]
    eval_result["random_avg_std"] = baseline["average_std"]
    eval_result["advantage_best"] = eval_result["best_total_hits"] - baseline["best_mean"]
    eval_result["advantage_avg"] = eval_result["avg_total_hits"] - baseline["average_mean"]
    
    return eval_result


def statistical_significance(differences, permutations=20000, seed=42):
    """Calcule IC95 bootstrap et p-value de permutation appariée."""
    values = np.asarray(differences, dtype=float)
    if values.size < 2:
        return {"ci_low": 0.0, "ci_high": 0.0, "p_value": 1.0}
    rng = np.random.default_rng(seed)
    samples = rng.choice(values, size=(permutations, values.size), replace=True).mean(axis=1)
    ci_low, ci_high = np.percentile(samples, [2.5, 97.5])
    signs = rng.choice([-1.0, 1.0], size=(permutations, values.size))
    null_means = (signs * values).mean(axis=1)
    observed = abs(values.mean())
    p_value = (np.count_nonzero(np.abs(null_means) >= observed) + 1) / (permutations + 1)
    return {"ci_low": float(ci_low), "ci_high": float(ci_high), "p_value": float(p_value)}


def compute_score(all_results):
    """Compare le pipeline à une référence aléatoire équitable."""
    if not all_results:
        return {}
    n = len(all_results)
    total_best_hits = sum(r["best_total_hits"] for r in all_results)
    random_total_best_hits = sum(r["random_best_total_hits"] for r in all_results)
    avg_best_hits = total_best_hits / n
    random_avg_best_hits = random_total_best_hits / n
    avg_prediction_hits = float(np.mean([r["avg_total_hits"] for r in all_results]))
    random_avg_prediction_hits = float(np.mean([r["random_avg_total_hits"] for r in all_results]))
    uniform_avg_best_hits = float(np.mean([r.get("uniform_best_total_hits", r["random_best_total_hits"]) for r in all_results]))
    uniform_avg_prediction_hits = float(np.mean([r.get("uniform_avg_total_hits", r["random_avg_total_hits"]) for r in all_results]))
    best_differences = [r.get("advantage_best", r["best_total_hits"] - r["random_best_total_hits"]) for r in all_results]
    avg_differences = [r.get("advantage_avg", r["avg_total_hits"] - r["random_avg_total_hits"]) for r in all_results]
    uniform_best_differences = [r["best_total_hits"] - r.get("uniform_best_total_hits", r["random_best_total_hits"]) for r in all_results]
    uniform_avg_differences = [r["avg_total_hits"] - r.get("uniform_avg_total_hits", r["random_avg_total_hits"]) for r in all_results]
    uniform_best_significance = statistical_significance(uniform_best_differences)
    uniform_avg_significance = statistical_significance(uniform_avg_differences)
    best_significance = statistical_significance(best_differences)
    avg_significance = statistical_significance(avg_differences)
    reliable = best_significance["ci_low"] > 0 and avg_significance["ci_low"] > 0 and uniform_best_significance["ci_low"] > 0 and uniform_avg_significance["ci_low"] > 0 and best_significance["p_value"] < 0.05 and avg_significance["p_value"] < 0.05 and uniform_best_significance["p_value"] < 0.05 and uniform_avg_significance["p_value"] < 0.05
    return {
        "avg_best_hits": avg_best_hits,
        "random_avg_best_hits": random_avg_best_hits,
        "advantage_best": avg_best_hits - random_avg_best_hits,
        "uniform_avg_best_hits": uniform_avg_best_hits,
        "uniform_avg_prediction_hits": uniform_avg_prediction_hits,
        "advantage_vs_uniform_best": avg_best_hits - uniform_avg_best_hits,
        "advantage_vs_uniform_avg": avg_prediction_hits - uniform_avg_prediction_hits,
        "avg_prediction_hits": avg_prediction_hits,
        "random_avg_prediction_hits": random_avg_prediction_hits,
        "advantage_avg": avg_prediction_hits - random_avg_prediction_hits,
        "avg_hit_rate": float(np.mean([r["avg_hit_rate"] for r in all_results])),
        "best_ci_low": best_significance["ci_low"],
        "best_ci_high": best_significance["ci_high"],
        "uniform_best_ci_low": uniform_best_significance["ci_low"],
        "uniform_best_ci_high": uniform_best_significance["ci_high"],
        "uniform_best_p_value": uniform_best_significance["p_value"],
        "uniform_avg_ci_low": uniform_avg_significance["ci_low"],
        "uniform_avg_ci_high": uniform_avg_significance["ci_high"],
        "uniform_avg_p_value": uniform_avg_significance["p_value"],
        "best_p_value": best_significance["p_value"],
        "avg_ci_low": avg_significance["ci_low"],
        "avg_ci_high": avg_significance["ci_high"],
        "avg_p_value": avg_significance["p_value"],
        "reliable_advantage": reliable,
        "avg_diversity": float(np.mean([r["diversity"] for r in all_results])),
        "n_draws": n,
        "total_best_hits": total_best_hits,
        "random_total_best_hits": random_total_best_hits
    }


def create_combination_population(profile, size=10):
    """Crée une population déterministe utilisant une combinaison de signaux."""
    weights = COMBINATION_PROFILES[profile]
    population = create_ablation_population("random", size)
    for index, genome in enumerate(population):
        for gene in ABLATION_PROFILES.values():
            genome["genes"][gene] = 0.0
        genome["genes"].update(weights)
        genome["genes"]["pool_size"] = 50
        genome["id"] = f"combination_{profile}_{index}"
    return population


def create_ablation_population(profile, size=10):
    """Crée une population déterministe avec un seul signal actif."""
    active_gene = ABLATION_PROFILES[profile]
    population = []
    for index in range(size):
        genes = {
            "weight_maturity": 0.0,
            "weight_poisson": 0.0,
            "weight_mean_reversion": 0.0,
            "weight_bayesian": 0.0,
            "weight_correlation": 0.0,
            "weight_random": 0.0,
            "pool_size": 50
        }
        genes[active_gene] = 1.0
        population.append({
            "id": f"ablation_{profile}_{index}",
            "genes": genes,
            "seed": 10000 + index,
            "fitness": 0.0,
            "total_hits": 0,
            "draws_evaluated": 0,
            "generation": 0,
            "age": 0
        })
    return population


def compute_window_details(all_results, window_size):
    """Calcule les métriques séparées de chaque fenêtre chronologique."""
    details = []
    for start in range(0, len(all_results), window_size):
        window = all_results[start:start + window_size]
        if len(window) != window_size:
            continue
        metrics = compute_score(window)
        details.append({
            "window": len(details) + 1,
            "start_offset": start,
            "end_offset": start + window_size - 1,
            "n_draws": metrics["n_draws"],
            "advantage_best": metrics["advantage_best"],
            "advantage_avg": metrics["advantage_avg"],
            "advantage_vs_uniform_best": metrics["advantage_vs_uniform_best"],
            "advantage_vs_uniform_avg": metrics["advantage_vs_uniform_avg"],
            "reliable_advantage": metrics["reliable_advantage"]
        })
    return details


def main():
    parser = argparse.ArgumentParser(description='Euromillions benchmark')
    parser.add_argument('--mode', choices=['dev', 'test'], default='dev')
    parser.add_argument('--run-name', default='benchmark')
    parser.add_argument("--ablation", action="store_true", help="Teste chaque signal statistique séparément")
    parser.add_argument("--multi-window", action="store_true", help="Évalue plusieurs fenêtres chronologiques indépendantes")
    parser.add_argument("--window-size", type=int, default=20, help="Nombre de tirages par fenêtre")
    parser.add_argument("--window-count", type=int, default=5, help="Nombre de fenêtres chronologiques")
    args = parser.parse_args()
    
    print(f"{'='*60}")
    print(f"  Euromillions Benchmark — {args.mode.upper()}")
    print(f"  Run: {args.run_name}")
    print(f"{'='*60}")
    
    all_draws = load_draws()
    print(f"  Total draws: {len(all_draws)}")
    
    if args.multi_window:
        total_window_draws = args.window_size * args.window_count
        eval_start = len(all_draws) - total_window_draws
        eval_end = len(all_draws)
        desc = f"Multi-window ({args.window_count} x {args.window_size} = {total_window_draws} tirages)"
    elif args.mode == "dev":
        eval_start = len(all_draws) - 20 - 67
        eval_end = len(all_draws) - 20
        desc = "B_dev (67 draws)"
    else:
        eval_start = len(all_draws) - 20
        eval_end = len(all_draws)
        desc = "B_test (20 draws)"
    
    if eval_start < 100:
        print(f"ERROR: Not enough historical data")
        sys.exit(1)
    
    print(f"  Evaluation: {desc}")
    print(f"  Training up to: {all_draws[eval_start-1]['date']}")
    print(f"  Eval: {all_draws[eval_start]['date']} to {all_draws[eval_end-1]['date']}")
    
    mgr = EvolutionManager()
    random.seed(42)
    benchmark_population = mgr.create_initial_population(200)
    for genome in benchmark_population:
        genome["fitness"] = 0.0
        genome["total_hits"] = 0
        genome["draws_evaluated"] = 0
    if args.ablation:
        ablation_results = {}
        for profile in list(ABLATION_PROFILES) + list(COMBINATION_PROFILES):
            print(f"\n--- ABLATION : {profile} ---")
            profile_population = create_combination_population(profile) if profile in COMBINATION_PROFILES else create_ablation_population(profile)
            profile_results = []
            for idx in range(eval_start, eval_end):
                result = run_draw_evaluation(all_draws[:idx], all_draws[idx], profile_population)
                profile_results.append(result)
            metrics = compute_score(profile_results)
            ablation_results[profile] = {
                "avg_best_hits": round(metrics["avg_best_hits"], 4),
                "avg_prediction_hits": round(metrics["avg_prediction_hits"], 4),
                "advantage_vs_uniform_best": round(metrics["advantage_vs_uniform_best"], 4),
                "advantage_vs_uniform_avg": round(metrics["advantage_vs_uniform_avg"], 4),
                "advantage_vs_random_best": round(metrics["advantage_best"], 4),
                "advantage_vs_random_avg": round(metrics["advantage_avg"], 4),
                "best_p_value": round(metrics["best_p_value"], 4),
                "avg_p_value": round(metrics["avg_p_value"], 4)
            }
            print(profile, ablation_results[profile])
        ranking = sorted(ablation_results.items(), key=lambda item: item[1]["advantage_vs_uniform_avg"], reverse=True)
        print("\n=== CLASSEMENT ABLATION ===")
        for rank, (profile, metrics) in enumerate(ranking, 1):
            print(rank, profile, metrics)
        print(f"\nJSON_ABLATION:{json.dumps(ablation_results)}")
        return ablation_results
    all_results = []
    
    for idx in range(eval_start, eval_end):
        eval_draw = all_draws[idx]
        train_draws = all_draws[:idx]
        result = run_draw_evaluation(train_draws, eval_draw, benchmark_population)
        all_results.append(result)
        bh, sh = result['best_ball_hits'], result['best_star_hits']
        print(f"  [{idx - eval_start + 1}/{eval_end - eval_start}] {eval_draw['date']}: best={bh}b+{sh}s={bh+sh}/7 rate={result['avg_hit_rate']:.1f}% div={result['diversity']:.0f}%")
    
    window_details = compute_window_details(all_results, args.window_size) if args.multi_window else []
    if window_details:
        print("\n=== DETAILS DES FENETRES CHRONOLOGIQUES ===")
        for detail in window_details:
            print(f"Fenetre {detail['window']}: hasard_best={detail['advantage_best']:+.4f}, hasard_avg={detail['advantage_avg']:+.4f}, uniforme_best={detail['advantage_vs_uniform_best']:+.4f}, uniforme_avg={detail['advantage_vs_uniform_avg']:+.4f}, fiable={detail['reliable_advantage']}")
    score_data = compute_score(all_results)
    
    print(f"\n{'='*60}")
    print(f"  FINAL RESULTS — {desc}")
    print(f"{'='*60}")
    print(f"  Pipeline - moyenne meilleure grille : {score_data['avg_best_hits']:.4f}")
    print(f"  Hasard   - moyenne meilleure grille : {score_data['random_avg_best_hits']:.4f}")
    print(f"  Uniforme - meilleure grille moyenne : {score_data['uniform_avg_best_hits']:.4f}")
    print(f"  Avantage modèle contre uniforme     : {score_data['advantage_vs_uniform_best']:+.4f}")
    print(f"  Avantage meilleure grille           : {score_data['advantage_best']:+.4f}")
    print(f"  Pipeline - moyenne par grille        : {score_data['avg_prediction_hits']:.4f}")
    print(f"  Hasard   - moyenne par grille        : {score_data['random_avg_prediction_hits']:.4f}")
    print(f"  Uniforme - moyenne par grille        : {score_data['uniform_avg_prediction_hits']:.4f}")
    print(f"  Avantage moyen contre uniforme      : {score_data['advantage_vs_uniform_avg']:+.4f}")
    print(f"  Avantage moyen par grille            : {score_data['advantage_avg']:+.4f}")
    print(f"  IC95 meilleure grille                : [{score_data['best_ci_low']:+.4f}, {score_data['best_ci_high']:+.4f}]  p={score_data['best_p_value']:.4f}")
    print(f"  IC95 moyenne par grille              : [{score_data['avg_ci_low']:+.4f}, {score_data['avg_ci_high']:+.4f}]  p={score_data['avg_p_value']:.4f}")
    print(f"  Avantage statistiquement fiable      : {score_data['reliable_advantage']}")
    print(f"  Diversité moyenne                    : {score_data['avg_diversity']:.1f}%")
    print(f"  Tirages évalués                      : {score_data['n_draws']}")
    print(f"{'='*60}")

    output = {
        "mode": args.mode, "run_name": args.run_name,
        "avg_best_hits": round(score_data["avg_best_hits"], 4),
        "random_avg_best_hits": round(score_data["random_avg_best_hits"], 4),
        "uniform_avg_best_hits": round(score_data["uniform_avg_best_hits"], 4),
        "uniform_avg_prediction_hits": round(score_data["uniform_avg_prediction_hits"], 4),
        "advantage_vs_uniform_best": round(score_data["advantage_vs_uniform_best"], 4),
        "advantage_vs_uniform_avg": round(score_data["advantage_vs_uniform_avg"], 4),
        "advantage_best": round(score_data["advantage_best"], 4),
        "best_ci_low": round(score_data["best_ci_low"], 4),
        "best_ci_high": round(score_data["best_ci_high"], 4),
        "best_p_value": round(score_data["best_p_value"], 4),
        "avg_ci_low": round(score_data["avg_ci_low"], 4),
        "avg_ci_high": round(score_data["avg_ci_high"], 4),
        "avg_p_value": round(score_data["avg_p_value"], 4),
        "reliable_advantage": score_data["reliable_advantage"],
        "avg_prediction_hits": round(score_data["avg_prediction_hits"], 4),
        "random_avg_prediction_hits": round(score_data["random_avg_prediction_hits"], 4),
        "advantage_avg": round(score_data["advantage_avg"], 4),
        "avg_diversity": round(score_data["avg_diversity"], 1),
        "n_draws": score_data["n_draws"]
    }
    if args.mode == "test":
        promotion_allowed = bool(score_data["reliable_advantage"] and score_data["n_draws"] >= 100 and score_data["advantage_vs_uniform_best"] > 0 and score_data["advantage_vs_uniform_avg"] > 0)
        verdict = dict(output)
        verdict["promotion_allowed"] = promotion_allowed
        verdict["recommended_mode"] = "experimental" if promotion_allowed else "uniform"
        verdict["updated_at"] = pd.Timestamp.now(tz="UTC").isoformat()
        tmp_verdict = VERDICT_FILE + ".tmp"
        with open(tmp_verdict, "w", encoding="utf-8") as f:
            json.dump(verdict, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_verdict, VERDICT_FILE)
    print(f"\nJSON_OUTPUT:{json.dumps(output)}")
    return score_data["advantage_avg"]

if __name__ == "__main__":
    main()
