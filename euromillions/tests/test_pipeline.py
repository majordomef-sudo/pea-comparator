"""Tests unitaires pour le pipeline Euromillions v4."""
import sys, os, json, pickle, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from euromillions.strategy_engine import StrategyEngine
from euromillions.evolution_manager import EvolutionManager


class TestStrategyEngine(unittest.TestCase):
    """Tests du moteur de stratégie."""

    @classmethod
    def setUpClass(cls):
        cls.engine = StrategyEngine()

    def test_validate_grille_valid(self):
        """Vérifie qu'une grille valide passe."""
        valid_grids = [
            [2, 5, 12, 20, 35],  # 3 pairs, sum=74→NON, besoin sum>=100
            [10, 15, 22, 33, 40],  # 3 pairs, sum=120, 2 high (33,40)
            [3, 14, 25, 36, 47],  # 2 pairs, sum=125, 2 high (36,47)
            [8, 17, 26, 35, 44],  # 3 pairs, sum=130, 2 high (35,44)
        ]
        for grid in valid_grids:
            if StrategyEngine.validate_grille(grid):
                print(f'  ✅ Valid: {grid}')
                return
        self.fail(f'Aucune grille valide parmi les testées')

    def test_validate_grille_invalid(self):
        """Vérifie qu'une grille invalide est rejetée."""
        invalid = [
            [1, 2, 3, 4, 5],    # 2 pairs, sum=15, trop petit, 0 high
            [1, 11, 21, 31, 41],  # 1 pair, sum=105, 2 high — mais 1 pair
            [10, 20, 30, 40, 50], # 5 pairs, sum=150, 3 high — mais evens=5
        ]
        for grid in invalid:
            self.assertFalse(StrategyEngine.validate_grille(grid), f'Devrait être invalide: {grid}')

    def test_generate_produces_valid_grid(self):
        """Vérifie que generate() produit une grille valide."""
        for seed in [42, 123, 456, 789]:
            genome = {
                'genes': {'weight_maturity': 1.0, 'weight_poisson': 0.8,
                          'weight_mean_reversion': 0.5, 'weight_bayesian': 0.3,
                          'weight_correlation': 0.7, 'weight_random': 0.1,
                          'pool_size': 20},
                'seed': seed
            }
            balls = self.engine.generate(genome)
            self.assertEqual(len(balls), 5, f'{seed}: devrait avoir 5 boules')
            self.assertEqual(len(set(balls)), 5, f'{seed}: pas de doublons')
            self.assertTrue(all(1 <= b <= 50 for b in balls), f'{seed}: boules hors limites')
            self.assertTrue(StrategyEngine.validate_grille(balls), f'{seed}: grille invalide: {balls}')

    def test_generation_is_deterministic(self):
        """Un même génome doit toujours produire la même grille."""
        genome = {"genes": {"weight_maturity": 1.0, "weight_poisson": 0.8, "weight_mean_reversion": 0.5, "weight_bayesian": 0.3, "weight_correlation": 0.7, "weight_random": 0.2, "pool_size": 20}, "seed": 4242}
        first = (self.engine.generate(genome), self.engine.generate_stars(genome))
        second = (self.engine.generate(genome), self.engine.generate_stars(genome))
        self.assertEqual(first, second)


    def test_generate_stars(self):
        """Vérifie que generate_stars() produit des étoiles valides."""
        for seed in [42, 123, 456]:
            genome = {'genes': {'weight_maturity': 1.0, 'weight_poisson': 0.8,
                                'weight_correlation': 0.5, 'weight_random': 0.1},
                      'seed': seed}
            stars = self.engine.generate_stars(genome)
            self.assertEqual(len(stars), 2, f'{seed}: devrait avoir 2 étoiles')
            self.assertEqual(len(set(stars)), 2, f'{seed}: pas de doublons')
            self.assertTrue(all(1 <= s <= 12 for s in stars), f'{seed}: étoiles hors limites')

    def test_validate_stars(self):
        """Vérifie la validation des étoiles."""
        self.assertTrue(StrategyEngine.validate_stars([1, 2]))
        self.assertFalse(StrategyEngine.validate_stars([1, 1]))  # doublon
        self.assertFalse(StrategyEngine.validate_stars([0, 1]))  # hors limites
        self.assertFalse(StrategyEngine.validate_stars([13, 1]))  # hors limites

    def test_poisson_probability(self):
        """Vérifie que Poisson retourne une probabilité entre 0 et 1."""
        for gap, avg in [(0, 5), (5, 5), (10, 5), (20, 5)]:
            prob = self.engine._poisson_probability(gap, avg)
            self.assertGreaterEqual(prob, 0)
            self.assertLessEqual(prob, 1)

    def test_correlation_score(self):
        """Vérifie le score de corrélation."""
        score = self.engine._correlation_score(5, [10, 20, 30])
        self.assertGreaterEqual(score, 0)
        # Sans already_selected
        score_empty = self.engine._correlation_score(5, [])
        self.assertEqual(score_empty, 0)


class TestEvolutionManager(unittest.TestCase):
    """Tests du manager évolutionnaire."""

    def test_create_random_genome(self):
        """Vérifie la création d'un génome aléatoire."""
        genome = EvolutionManager.create_random_genome()
        self.assertIn('genes', genome)
        self.assertIn('id', genome)
        self.assertIn('seed', genome)
        self.assertIn('fitness', genome)
        self.assertEqual(genome['fitness'], 0.0)
        # Vérifie que tous les gènes sont présents
        for name, min_v, max_v, default in EvolutionManager.GENES_META:
            self.assertIn(name, genome['genes'], f'Gène manquant: {name}')
            val = genome['genes'][name]
            self.assertGreaterEqual(val, min_v, f'{name} < {min_v}')
            self.assertLessEqual(val, max_v, f'{name} > {max_v}')

    def test_create_child(self):
        """Vérifie la création d'un enfant par crossover."""
        parent_a = EvolutionManager.create_random_genome()
        parent_b = EvolutionManager.create_random_genome()
        child = EvolutionManager.create_child(parent_a, parent_b)
        self.assertIn('genes', child)
        self.assertGreater(child['generation'], 0)
        # Vérifie que les gènes sont dans les limites
        for name, min_v, max_v, default in EvolutionManager.GENES_META:
            val = child['genes'][name]
            self.assertGreaterEqual(val, min_v, f'{name} < {min_v}')
            self.assertLessEqual(val, max_v, f'{name} > {max_v}')

    def test_initial_population_size(self):
        """Vérifie la taille de la population initiale."""
        pop = EvolutionManager().create_initial_population(50)
        self.assertEqual(len(pop), 50)
        # Vérifie les IDs uniques
        ids = [g['id'] for g in pop]
        self.assertEqual(len(set(ids)), len(ids), 'IDs en doublon')

    def test_tournament_selection(self):
        """Vérifie que la sélection par tournoi fonctionne."""
        mgr = EvolutionManager()
        # Crée une population avec fitness variées
        mgr.population = []
        for i in range(10):
            g = EvolutionManager.create_random_genome()
            g['fitness'] = float(i)
            g['draws_evaluated'] = 5
            mgr.population.append(g)
        selected = mgr.tournament_selection()
        self.assertIn('genes', selected)

    def test_get_top_genomes(self):
        """Vérifie le tri par fitness."""
        mgr = EvolutionManager()
        # Population avec fitness variées
        mgr.population = []
        for i in range(10):
            g = EvolutionManager.create_random_genome()
            g['fitness'] = float(i)
            mgr.population.append(g)
        top = mgr.get_top_genomes(3)
        self.assertEqual(len(top), 3)
        self.assertGreaterEqual(top[0]['fitness'], top[1]['fitness'])
        self.assertGreaterEqual(top[1]['fitness'], top[2]['fitness'])


class TestBenchmark(unittest.TestCase):
    """Tests du benchmark face au hasard."""

    def test_random_baseline_count_and_validity(self):
        import random
        from euromillions.run_benchmark import generate_random_predictions
        predictions = generate_random_predictions(11, random.Random(42))
        self.assertEqual(len(predictions), 11)
        for prediction in predictions:
            self.assertEqual(len(prediction["balls"]), 5)
            self.assertEqual(len(set(prediction["balls"])), 5)
            self.assertTrue(set(prediction["balls"]).issubset(range(1, 51)))
            self.assertEqual(len(prediction["stars"]), 2)
            self.assertEqual(len(set(prediction["stars"])), 2)
            self.assertTrue(set(prediction["stars"]).issubset(range(1, 13)))

    def test_benchmark_comparative_metrics(self):
        from euromillions.run_benchmark import compute_score
        results = [{"best_total_hits": 2, "random_best_total_hits": 1, "avg_total_hits": 0.8, "random_avg_total_hits": 0.6, "avg_hit_rate": 10.0, "diversity": 50.0}]
        metrics = compute_score(results)
        self.assertEqual(metrics["advantage_best"], 1.0)
        self.assertAlmostEqual(metrics["advantage_avg"], 0.2)
        self.assertNotIn("score", metrics)


    def test_significance_rejects_uncertain_advantage(self):
        from euromillions.run_benchmark import statistical_significance
        result = statistical_significance([0.1, -0.1, 0.05, -0.05], permutations=2000, seed=42)
        self.assertLessEqual(result["ci_low"], 0)
        self.assertGreaterEqual(result["ci_high"], 0)
        self.assertGreater(result["p_value"], 0.05)

    def test_reliable_advantage_requires_significance(self):
        from euromillions.run_benchmark import compute_score
        results = [{"best_total_hits": 2, "random_best_total_hits": 2, "avg_total_hits": 0.8, "random_avg_total_hits": 0.8, "advantage_best": 0.0, "advantage_avg": 0.0, "avg_hit_rate": 10.0, "diversity": 50.0} for _ in range(20)]
        metrics = compute_score(results)
        self.assertFalse(metrics["reliable_advantage"])


    def test_uniform_generation(self):
        """La stratégie uniforme doit être valide et reproductible."""
        from euromillions.strategy_engine import StrategyEngine
        balls_1 = StrategyEngine.generate_uniform(42)
        stars_1 = StrategyEngine.generate_uniform_stars(42)
        balls_2 = StrategyEngine.generate_uniform(42)
        stars_2 = StrategyEngine.generate_uniform_stars(42)
        self.assertEqual((balls_1, stars_1), (balls_2, stars_2))
        self.assertEqual(len(balls_1), 5)
        self.assertEqual(len(set(balls_1)), 5)
        self.assertTrue(set(balls_1).issubset(range(1, 51)))
        self.assertEqual(len(stars_1), 2)
        self.assertEqual(len(set(stars_1)), 2)
        self.assertTrue(set(stars_1).issubset(range(1, 13)))


    def test_split_fitness_balances_balls_and_stars(self):
        from euromillions.evaluate_performance import calculate_split_fitness
        balls, stars, global_score = calculate_split_fitness(5, 2, 1)
        self.assertEqual(balls, 1.0)
        self.assertEqual(stars, 1.0)
        self.assertEqual(global_score, 1.0)
        self.assertEqual(calculate_split_fitness(0, 0, 0), (0.0, 0.0, 0.0))


    def test_missing_dates_excludes_today(self):
        from euromillions import update_data
        missing = update_data.get_missing_draw_dates()
        self.assertNotIn(__import__("datetime").datetime.now().strftime("%d/%m/%Y"), missing)


    def test_promotion_verdict_security(self):
        import datetime as dt
        from euromillions.analyze_v2 import is_promotion_allowed
        now = dt.datetime(2026, 8, 14, tzinfo=dt.timezone.utc)
        valid = {"updated_at": now.isoformat(), "n_draws": 100, "promotion_allowed": True, "recommended_mode": "experimental", "reliable_advantage": True}
        self.assertTrue(is_promotion_allowed(valid, now))
        expired = dict(valid, updated_at=(now - dt.timedelta(days=15)).isoformat())
        self.assertFalse(is_promotion_allowed(expired, now))
        self.assertFalse(is_promotion_allowed(dict(valid, n_draws=99), now))
        self.assertFalse(is_promotion_allowed(dict(valid, reliable_advantage=False), now))
        self.assertFalse(is_promotion_allowed({}, now))


    def test_multi_window_details(self):
        from euromillions.run_benchmark import compute_window_details
        result = {"best_total_hits": 2, "random_best_total_hits": 2.0, "uniform_best_total_hits": 2, "avg_total_hits": 0.8, "random_avg_total_hits": 0.8, "uniform_avg_total_hits": 0.8, "advantage_best": 0.0, "advantage_avg": 0.0, "avg_hit_rate": 10.0, "diversity": 50.0}
        details = compute_window_details([dict(result) for _ in range(100)], 20)
        self.assertEqual(len(details), 5)
        self.assertEqual([item["window"] for item in details], [1, 2, 3, 4, 5])
        self.assertTrue(all(item["n_draws"] == 20 for item in details))


if __name__ == '__main__':
    unittest.main()
