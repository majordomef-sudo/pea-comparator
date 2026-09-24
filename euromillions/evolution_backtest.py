#!/usr/bin/env python3
"""
Backtest evolutionnaire corrige (v2)
=====================================
Corrige 3 bugs methodologiques du pipeline :

Bug 1 : l'evolution ne se declenche presque jamais (attend 100 genomes x 20 tirages
        = ~19 ans a 2 tirages/semaine). Ici : evaluation sur l'historique complet
        en walk-forward, evolution cyclique tous les N tirages.

Bug 2 : la fitness recompense le hasard (hits bruts). Ici : fitness = avantage
        relatif vs esperance aleatoire, avec shrinkage James-Stein.

Bug 3 : le benchmark testait une population figee non evoluee. Ici : comparaison
        population EVOLUEE vs population CONTROLE (figee).

Usage:
    python3 euromillions/evolution_backtest.py --quick 150     # test rapide
    python3 euromillions/evolution_backtest.py                  # complet
"""
import argparse
import copy
import json
import os
import random
import sys
from collections import Counter

import numpy as np

BASE_DIR = "/home/ubuntu/.openclaw/workspace/euromillions"
sys.path.insert(0, os.path.join(BASE_DIR, ".."))

import euromillions.run_benchmark as rb
from euromillions.evolution_manager import EvolutionManager
from euromillions.strategy_engine import StrategyEngine

TRAIN_MIN = 100
DEFAULT_EVOLVE_EVERY = 100
DEFAULT_EVAL_WINDOW = 20
SHRINK_K = 20.0
EXPECTED_HITS = 5 * (5 / 50.0) + 2 * (2 / 12.0)  # ~0.8333 hits/tirage pour le hasard


class SilentEvolutionManager(EvolutionManager):
    """Evolution en memoire, sans sauvegarde disque (dry-run)."""

    def __init__(self, population=None):
        self.population = population if population is not None else []
        self.generation = max((g.get("generation", 0) for g in self.population), default=0)

    def save_population(self):
        pass


def relative_fitness(hits, n, baseline_per_draw=EXPECTED_HITS):
    """Avantage par tirage vs hasard, avec shrinkage."""
    if n <= 0:
        return 0.0
    excess = (hits / n) - baseline_per_draw
    shrink = n / (n + SHRINK_K)
    return excess * shrink


def build_engine(train_draws):
    stats = rb.compute_stats_from_draws(train_draws)
    engine = StrategyEngine()
    engine.stats = stats
    engine.gaps = stats["current_gaps"]
    engine.avg_gaps = stats["average_gaps"]
    engine.corr = stats["correlation_matrix"]
    engine.star_gaps = stats["star_current_gaps"]
    engine.star_avg_gaps = stats["star_average_gaps"]
    engine.star_corr = stats.get("star_correlation_matrix")
    engine.total_draws = len(train_draws)
    return engine


def evaluate_population_on_window(population, train_draws, eval_draw):
    """Evalue chaque genome sur UN tirage (entrainement = avant, sans fuite)."""
    engine = build_engine(train_draws)
    actual_balls, actual_stars = set(eval_draw["balls"]), set(eval_draw["stars"])
    for g in population:
        balls = engine.generate(g)
        stars = engine.generate_stars(g)
        hits = len(set(balls) & actual_balls) + len(set(stars) & actual_stars)
        g["_hits"] = g.get("_hits", 0) + hits
        g["_n"] = g.get("_n", 0) + 1


def refresh_fitness(population):
    """Convertit les compteurs de fenetre en fitness relative, puis reset."""
    for g in population:
        n = g.get("_n", 0)
        g["fitness"] = relative_fitness(g.get("_hits", 0), n)
        g["total_hits"] = g.get("_hits", 0)
        g["draws_evaluated"] = n if n > 0 else g.get("draws_evaluated", 0)
        g["_hits"] = 0
        g["_n"] = 0


def best_predictions(population, train_draws, eval_draw):
    """Top-10 genomes par fitness + hybride par VOTE (bagging top 5)."""
    engine = build_engine(train_draws)
    pool = sorted(population, key=lambda g: g.get("fitness", 0), reverse=True)
    top10 = pool[:10]
    preds = []
    for g in top10:
        preds.append({"balls": engine.generate(g), "stars": engine.generate_stars(g)})
    votes = Counter()
    star_votes = Counter()
    for g in top10[:5]:
        votes.update(engine.generate(g))
        star_votes.update(engine.generate_stars(g))
    hyb_balls = sorted([n for n, _ in votes.most_common(5)])
    hyb_stars = sorted([n for n, _ in star_votes.most_common(2)])
    preds.append({"balls": hyb_balls, "stars": hyb_stars})
    return preds


def hits_for(preds, draw):
    best = 0
    for p in preds:
        h = len(set(p["balls"]) & set(draw["balls"])) + len(set(p["stars"]) & set(draw["stars"]))
        best = max(best, h)
    return best


def main():
    parser = argparse.ArgumentParser(description="Backtest evolutionnaire corrige")
    parser.add_argument("--quick", type=int, default=0, help="Nb de tirages a evaluer (test)")
    parser.add_argument("--evolve-every", type=int, default=DEFAULT_EVOLVE_EVERY)
    parser.add_argument("--eval-window", type=int, default=DEFAULT_EVAL_WINDOW)
    parser.add_argument("--out", default=os.path.join(BASE_DIR, "backtest_evolution_20260828.json"))
    args = parser.parse_args()

    all_draws = rb.load_draws()
    n = len(all_draws)
    eval_start = TRAIN_MIN
    eval_end = n if not args.quick else min(n, TRAIN_MIN + args.quick)
    print(f"Tirages: {n} | Evaluation: {eval_start}->{eval_end - 1} ({eval_end - eval_start} tirages)", flush=True)

    random.seed(42)
    base_pop = EvolutionManager().create_initial_population(200)
    for g in base_pop:
        g.update(fitness=0.0, total_hits=0, draws_evaluated=0, _hits=0, _n=0)
    pop_evolved = copy.deepcopy(base_pop)
    pop_control = copy.deepcopy(base_pop)
    mgr_evolved = SilentEvolutionManager(pop_evolved)
    mgr_control = SilentEvolutionManager(pop_control)

    res_evolved, res_control = [], []
    last_gen = 0
    for idx in range(eval_start, eval_end):
        draw = all_draws[idx]
        train = all_draws[:idx]
        res_evolved.append(hits_for(best_predictions(pop_evolved, train, draw), draw))
        res_control.append(hits_for(best_predictions(pop_control, train, draw), draw))

        steps = idx - eval_start + 1
        if steps % args.evolve_every == 0:
            # Re-evaluer la population sur la fenetre passee (sans fuite)
            wstart = max(eval_start, idx - args.eval_window)
            for j in range(wstart, idx):
                evaluate_population_on_window(pop_evolved, all_draws[:j], all_draws[j])
                evaluate_population_on_window(pop_control, all_draws[:j], all_draws[j])
            refresh_fitness(pop_evolved)
            refresh_fitness(pop_control)
            mgr_evolved.evolve()
            last_gen = mgr_evolved.generation
            print(f"  [evolution #{steps // args.evolve_every}] gen={last_gen} "
                  f"eval={steps}/{eval_end - eval_start}", flush=True)

    # Rapport
    diffs = [a - b for a, b in zip(res_evolved, res_control)]
    sig = rb.statistical_significance(diffs)
    out = {
        "n_draws": len(res_evolved),
        "first_date": all_draws[eval_start]["date"],
        "last_date": all_draws[eval_end - 1]["date"],
        "evolve_every": args.evolve_every,
        "eval_window": args.eval_window,
        "generation_atteinte": last_gen,
        "avg_best_hits_evolved": round(float(np.mean(res_evolved)), 4),
        "avg_best_hits_control": round(float(np.mean(res_control)), 4),
        "advantage_evolved_vs_control": round(float(np.mean(diffs)), 4),
        "ci_low": round(float(sig["ci_low"]), 4),
        "ci_high": round(float(sig["ci_high"]), 4),
        "p_value": round(float(sig["p_value"]), 4),
        "expected_random_best_hits": round(EXPECTED_HITS, 4),
    }
    with open(args.out, "w") as f:
        json.dump(out, f, indent=2)

    print("=" * 60)
    print(f"  Backtest evolutionnaire ({len(res_evolved)} tirages)")
    print(f"  Generation atteinte par l'evolution : {last_gen}")
    print(f"  Moyenne meilleure grille EVOLUE      : {out['avg_best_hits_evolved']}")
    print(f"  Moyenne meilleure grille CONTROLE    : {out['avg_best_hits_control']}")
    print(f"  Avantage (evolue - controle)         : {out['advantage_evolved_vs_control']}")
    print(f"  IC95 : [{out['ci_low']}, {out['ci_high']}]  p={out['p_value']}")
    print("=" * 60)
    print("JSON_OUTPUT:" + json.dumps(out))
    return out


if __name__ == "__main__":
    main()
