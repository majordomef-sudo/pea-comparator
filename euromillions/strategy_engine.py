"""
Moteur de Stratégie Probabiliste (v4)
Intègre : Loi des Grands Nombres, Poisson, Bayes, Corrélations, Combinatoire
"""
import numpy as np
import random
import pickle
import os
from math import exp, factorial, comb

BASE_DIR = "/home/ubuntu/.openclaw/workspace/euromillions"
STATS_FILE = os.path.join(BASE_DIR, 'advanced_stats.pkl')

class StrategyEngine:
    def __init__(self):
        self.stats = self._load_stats()
        self.gaps = self.stats.get('current_gaps', {}) if self.stats else {}
        self.avg_gaps = self.stats.get('average_gaps', {}) if self.stats else {}
        self.corr = self.stats.get('correlation_matrix', None) if self.stats else None
        # Statistiques des étoiles
        self.star_gaps = self.stats.get('star_current_gaps', {}) if self.stats else {}
        self.star_avg_gaps = self.stats.get('star_average_gaps', {}) if self.stats else {}
        self.star_corr = self.stats.get('star_correlation_matrix', None) if self.stats else None
        # Nombre total de tirages (passé dans le pickle ou fallback)
        self.total_draws = self.stats.get('total_draws', max(self.gaps.values())) if self.stats else 100

    def _load_stats(self):
        try:
            with open(STATS_FILE, 'rb') as f:
                return pickle.load(f)
        except:
            return None

    # ─── Modules Mathématiques ───

    def _poisson_probability(self, gap, avg_gap, lambda_factor=1.0):
        """
        Distribution de Poisson : Probabilité qu'un événement se produise
        après 'gap' tirages d'inactivité, sachant qu'il se produit en moyenne
        tous les 'avg_gap' tirages.
        lambda = 1/avg_gap (taux d'occurrence)
        """
        if avg_gap <= 0:
            return 0.5
        lam = lambda_factor / avg_gap
        # P(X >= gap) = 1 - sum_{k=0}^{gap-1} e^{-λ} λ^k / k!
        prob = 1.0
        cum = 0.0
        for k in range(gap):
            cum += (exp(-lam) * (lam ** k)) / factorial(k)
        prob = 1.0 - cum
        return prob

    def _mean_reversion(self, b, expected_freq, actual_freq):
        """
        Théorie du retour à la moyenne.
        Si un numéro est sorti beaucoup moins souvent que prévu, on le favorise.
        expected_freq = total_draws / 50 (fréquence théorique)
        actual_freq = total_draws / avg_gap (fréquence observée) si avg_gap > 0
        """
        if expected_freq <= 0:
            return 0.5
        deviation = (expected_freq - actual_freq) / expected_freq
        # On favorise les sous-représentés ET les sur-représentés (retour à la moyenne dans les deux sens)
        # mais avec un score absolu (les deux directions donnent une opportunité)
        return abs(deviation)

    def _bayesian_posterior(self, b, gap, avg_gap, recent_freq_window=20):
        """
        Inférence Bayésienne simple.
        Priori : P(le numéro sort) = 1/n (théorique)
        Vraisemblance : basée sur le ratio gap/avg_gap
        Le score retourné est non normalisé (utilisé comme poids dans l'ensemble final)
        """
        n = 50  # nombre de boules possibles
        prior = 1.0 / n
        # Vraisemblance : plus le gap est grand par rapport à la moyenne, plus c'est surprenant
        # On normalise entre 0 et 1 avec un plafond à 5x la moyenne
        gap_ratio = gap / max(avg_gap, 1)
        likelihood = min(gap_ratio / 5.0, 1.0)
        # Score non normalisé (la normalisation complète nécessiterait de calculer sur tous les b)
        # Utilisé comme poids dans l'ensemble, pas besoin d'une vraie probabilité
        return prior * likelihood

    def _correlation_score(self, b, already_selected):
        """
        Score basé sur les affinités : un numéro est favorisé s'il est
        historiquement sorti avec les numéros déjà sélectionnés.
        Normalisé par le max de la matrice pour être indépendant de la taille de l'historique.
        """
        if self.corr is None or not already_selected:
            return 0
        max_corr = max(self.corr[b][1:]) if self.corr[b].max() > 0 else 1.0
        total = 0
        for ref in already_selected:
            total += self.corr[b][ref]
        # Normalisation : moyenne / max possible
        return (total / len(already_selected)) / max_corr

    def score_ball(self, b, genes, already_selected):
        """
        Calcule le score final d'une boule en combinant TOUS les modules.
        """
        gap = self.gaps.get(b, 10)
        avg_gap = self.avg_gaps.get(b, 10)

        # 1. Maturité (ratio gap/avg) - pondérée par weight_maturity
        maturity_score = (gap / avg_gap) if avg_gap > 0 else 0

        # 2. Poisson - probabilité qu'il sorte "maintenant"
        poisson_score = self._poisson_probability(gap, avg_gap) if avg_gap > 0 else 0.5

        # 3. Retour à la moyenne
        expected_freq = self.total_draws / 50
        # Fréquence observée : total_draws / avg_gap
        actual_freq = self.total_draws / avg_gap if avg_gap > 0 else expected_freq
        reversion_score = self._mean_reversion(b, expected_freq, actual_freq)

        # 4. Bayésien
        bayesian_score = self._bayesian_posterior(b, gap, avg_gap)

        # 5. Corrélation
        correlation_score = self._correlation_score(b, already_selected)

        # Score final pondéré par les gènes
        w_maturity = genes.get('weight_maturity', 1.0)
        w_poisson = genes.get('weight_poisson', 1.0)
        w_reversion = genes.get('weight_mean_reversion', 0.5)
        w_bayesian = genes.get('weight_bayesian', 0.3)
        w_correlation = genes.get('weight_correlation', 0.5)
        w_random_explore = genes.get('weight_random', 0.2)

        random_bonus = self._rng.random() * w_random_explore

        total_score = (
            w_maturity * maturity_score +
            w_poisson * poisson_score +
            w_reversion * reversion_score +
            w_bayesian * bayesian_score +
            w_correlation * correlation_score +
            random_bonus
        )
        return total_score

    # ─── Méthodes pour les Étoiles ───

    def _star_poisson_probability(self, gap, avg_gap, lambda_factor=1.0):
        if avg_gap <= 0:
            return 0.5
        lam = lambda_factor / avg_gap
        prob = 1.0
        cum = 0.0
        for k in range(gap):
            cum += (exp(-lam) * (lam ** k)) / factorial(k)
        prob = 1.0 - cum
        return prob

    def _star_correlation_score(self, s, already_selected):
        if self.star_corr is None or not already_selected:
            return 0
        max_val = max(self.star_corr[s][1:]) if np.max(self.star_corr[s][1:]) > 0 else 1.0
        total = 0
        for ref in already_selected:
            total += self.star_corr[s][ref]
        return (total / len(already_selected)) / max_val if max_val > 0 else 0

    def score_star(self, s, genes, already_selected):
        gap = self.star_gaps.get(s, 5)
        avg_gap = self.star_avg_gaps.get(s, 5)

        maturity_score = (gap / avg_gap) if avg_gap > 0 else 0
        poisson_score = self._star_poisson_probability(gap, avg_gap) if avg_gap > 0 else 0.5
        correlation_score = self._star_correlation_score(s, already_selected)

        w_maturity = genes.get('weight_maturity', 1.0)
        w_poisson = genes.get('weight_poisson', 1.0)
        w_correlation = genes.get('weight_correlation', 0.5)
        w_random_explore = genes.get('weight_random', 0.2)

        total_score = (
            w_maturity * maturity_score +
            w_poisson * poisson_score +
            w_correlation * correlation_score +
            self._rng.random() * w_random_explore
        )
        return total_score

    @staticmethod
    def validate_stars(stars):
        if len(set(stars)) != 2:
            return False
        # Les étoiles sont entre 1 et 12
        if any(s < 1 or s > 12 for s in stars):
            return False
        return True

    # ─── Logique de validation (Combinatoire) ───

    @staticmethod
    def validate_grille(balls):
        """Filtres stricts basés sur les probabilités combinatories."""
        if len(set(balls)) != 5:
            return False
        
        # Parité : 2/3 pairs ou 3/2 pairs (97% des tirages)
        evens = len([b for b in balls if b % 2 == 0])
        if evens not in [2, 3]:
            return False
        
        # Somme : entre 100 et 175 (majorité des tirages)
        total = sum(balls)
        if total < 100 or total > 175:
            return False
        
        # Diversité : au moins 2 numéros > 31
        high = len([b for b in balls if b > 31])
        if high < 2:
            return False
        
        # Espacement : pas plus de 3 numéros consécutifs
        sorted_balls = sorted(balls)
        consecutives = 0
        for i in range(4):
            if sorted_balls[i+1] - sorted_balls[i] == 1:
                consecutives += 1
        if consecutives > 2:
            return False
        
        return True

    @staticmethod
    def fix_grille(balls, pool, rng):
        """Tente de corriger une grille invalide en remplaçant des éléments."""
        current = list(balls)
        attempts = 0
        while not StrategyEngine.validate_grille(current) and attempts < 100:
            attempts += 1
            idx = rng.randint(0, 4)
            alternatives = [b for b in pool if b not in current]
            if not alternatives:
                break
            current[idx] = rng.choice(alternatives)
        return sorted(current)

    @staticmethod
    def generate_uniform(seed):
        """Génère 5 boules uniformément, sans signal historique ni filtre de forme."""
        return sorted(random.Random(seed).sample(range(1, 51), 5))

    @staticmethod
    def generate_uniform_stars(seed):
        """Génère 2 étoiles uniformément et indépendamment de l historique."""
        return sorted(random.Random(seed + 999).sample(range(1, 13), 2))


    # ─── Génération ───

    def generate(self, genome, full_pool=None):
        """
        Génère une grille complète (5 boules) à partir d'un génome.
        """
        genes = genome.get('genes', {})
        pool_size = int(genes.get('pool_size', 15))
        seed = genome.get('seed', 0)
        local_rng = random.Random(seed)
        self._rng = local_rng

        # Sélection séquentielle : les corrélations sont recalculées après chaque boule
        selected = []
        available = list(range(1, 51))
        for _ in range(5):
            candidates = [(b, self.score_ball(b, genes, selected)) for b in available]
            candidates.sort(key=lambda item: item[1], reverse=True)
            top_pool = [item[0] for item in candidates[:min(pool_size, len(candidates))]]
            weights = [1.0 / (rank + 1) for rank in range(len(top_pool))]
            chosen = local_rng.choices(top_pool, weights=weights, k=1)[0]
            selected.append(chosen)
            available.remove(chosen)

        # Validation et correction
        pool = full_pool if full_pool else list(range(1, 51))
        if self.validate_grille(selected):
            return sorted(selected)
        else:
            return self.fix_grille(selected, pool, local_rng)

    def generate_stars(self, genome):
        """
        Génère les étoiles avec le même scoring probabiliste que les boules.
        Utilise : maturité, Poisson, corrélations + validation combinatoire.
        """
        genes = genome.get('genes', {})
        seed = genome.get('seed', 0)
        local_rng = random.Random(seed + 999)
        self._rng = local_rng

        selected = []
        candidates = []
        for s in range(1, 13):
            score = self.score_star(s, genes, selected)
            candidates.append((s, score))

        candidates.sort(key=lambda x: x[1], reverse=True)
        # Pool des meilleures candidates : top 8 ou toutes si moins
        pool_size = min(8, len(candidates))
        top_pool = [c[0] for c in candidates[:pool_size]]

        available = list(top_pool)
        for _ in range(2):
            if not available:
                available = list(range(1, 13))
            weights = [1.0 / (i+1) for i in range(len(available))]
            chosen = local_rng.choices(available, weights=weights, k=1)[0]
            selected.append(chosen)
            available.remove(chosen)

        # Validation
        if self.validate_stars(selected):
            return sorted(selected)
        else:
            return sorted(local_rng.sample(range(1, 13), 2))


if __name__ == "__main__":
    engine = StrategyEngine()
    test_genome = {
        "genes": {
            "weight_maturity": 1.0,
            "weight_poisson": 0.8,
            "weight_mean_reversion": 0.5,
            "weight_bayesian": 0.3,
            "weight_correlation": 0.7,
            "weight_random": 0.1,
            "pool_size": 20
        },
        "seed": 42
    }
    print(f"Grille : {engine.generate(test_genome)}")
    print(f"Stars  : {engine.generate_stars(test_genome)}")
