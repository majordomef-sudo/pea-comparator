"""
Tests d'intÃ©gration pour le pipeline Euromillions.
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from euromillions.evolution_manager import EvolutionManager
from euromillions.strategy_engine import StrategyEngine

import unittest


class TestFullPipeline(unittest.TestCase):
    """Tests d'integration du pipeline."""

    def test_modules_import(self):
        """Verifie que tous les modules s'importent."""
        import euromillions.strategy_engine
        import euromillions.evolution_manager
        import euromillions.advanced_stats
        import euromillions.evaluate_performance
        import euromillions.notify_telegram
        import euromillions.performance_monitor
        self.assertTrue(True)

    def test_performance_monitor(self):
        """Test du PerformanceMonitor."""
        from euromillions.performance_monitor import PerformanceMonitor
        pm = PerformanceMonitor()
        pm.start_step('test')
        import time
        time.sleep(0.05)
        pm.end_step()
        report = pm.get_report()
        self.assertIn('steps', report)
        self.assertIn('test', report['steps'])
        self.assertIn('total_duration', report)

    def test_evolution_manager_backup(self):
        """Verifie que la creation de population initiale fonctionne."""
        mgr = EvolutionManager()
        pop = mgr.create_initial_population(20)
        self.assertEqual(len(pop), 20)
        ids = [g['id'] for g in pop]
        self.assertEqual(len(set(ids)), len(ids))

    def test_strategy_engine_different_seeds(self):
        """Verifie que des seeds differentes donnent de la diversite."""
        engine = StrategyEngine()
        results = []
        for seed in [1, 2, 3, 4, 5]:
            genome = {'genes': {'weight_maturity': 1.0, 'weight_poisson': 0.8,
                                'weight_mean_reversion': 0.5, 'weight_bayesian': 0.3,
                                'weight_correlation': 0.7, 'weight_random': 0.1,
                                'pool_size': 20}, 'seed': seed}
            balls = engine.generate(genome)
            results.append(tuple(balls))
        unique = len(set(results))
        self.assertGreaterEqual(unique, 2, f'5 seeds devraient produire de la diversite: {unique} uniques')

    def test_validate_grille_ranges(self):
        """Verifie validate_grille avec differentes entrees."""
        self.assertFalse(StrategyEngine.validate_grille([1, 2, 3, 4, 5]))  # sum=15 < 100
        self.assertFalse(StrategyEngine.validate_grille([46, 47, 48, 49, 50]))  # sum=240 > 175
        self.assertFalse(StrategyEngine.validate_grille([1, 2, 3, 5, 4]))  # unsorted

    def test_validate_stars_ranges(self):
        """Verifie validate_stars avec differentes entrees."""
        self.assertTrue(StrategyEngine.validate_stars([1, 2]))
        self.assertTrue(StrategyEngine.validate_stars([11, 12]))
        self.assertFalse(StrategyEngine.validate_stars([1, 13]))  # > 12

    def test_evaluate_performance_imports(self):
        """Verifie que evaluate_performance a les bonnes fonctions."""
        import euromillions.evaluate_performance as ep
        self.assertTrue(hasattr(ep, 'evaluate_and_evolve'))

    def test_parse_french_date(self):
        """Test du parsing de dates."""
        from euromillions.update_data import parse_french_date
        date = parse_french_date("31 juillet 2026")
        self.assertIsNotNone(date)
        self.assertIsInstance(date, str)
        self.assertEqual(date, "31/07/2026")

    def test_update_data_exports(self):
        """Verifie que update_data a les bonnes fonctions."""
        import euromillions.update_data as ud
        self.assertTrue(hasattr(ud, 'backup_data'))
        self.assertTrue(hasattr(ud, 'fetch_latest_draw'))
        self.assertTrue(hasattr(ud, 'parse_french_date'))

    def test_pipeline_shell_syntax(self):
        """Verifie la syntaxe du pipeline shell."""
        import subprocess, os
        r = subprocess.run(['bash', '-n', 'pipelineeuromillion'],
                          capture_output=True, text=True, timeout=10,
                          cwd=os.path.dirname(os.path.abspath(__file__)) + '/..')
        self.assertEqual(r.returncode, 0, f'Shell syntax error: {r.stderr}')


if __name__ == '__main__':
    unittest.main()
