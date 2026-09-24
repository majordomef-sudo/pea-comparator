"""
Manager Évolutionnaire (v4)
Gère la population de génomes stratégiques.
Cycle de vie : Génération → Évaluation → Sélection → Croisement → Mutation
"""
import json
import random
import copy
import os
import uuid

BASE_DIR = "/home/ubuntu/.openclaw/workspace/euromillions"
POOL_FILE = os.path.join(BASE_DIR, 'strategy_pool.json')

# ─── Paramètres Génétiques ───
POPULATION_SIZE = 200
ELITE_RATIO = 0.20         # Top 20% survivent
TOURNAMENT_SIZE = 5
MUTATION_RATE = 0.15       # 15% de mutation par gène
CROSSOVER_RATE = 0.70      # 70% des enfants sont des crossovers
FRESH_BLOOD = 0.10         # 10% de nouveaux génomes aléatoires à chaque génération

# Définition des gènes : nom, min, max, default
GENES_META = [
    ("weight_maturity", 0.0, 3.0, 1.0),
    ("weight_poisson", 0.0, 3.0, 0.8),
    ("weight_mean_reversion", 0.0, 3.0, 0.5),
    ("weight_bayesian", 0.0, 3.0, 0.3),
    ("weight_correlation", 0.0, 3.0, 0.5),
    ("weight_random", 0.0, 1.0, 0.2),
    ("pool_size", 5, 30, 15)
]

class EvolutionManager:
    GENES_META = GENES_META

    def __init__(self):
        self.population = self.load_population()
        self.generation = max(ind.get('generation', 0) for ind in self.population) if self.population else 0

    # ─── Génome Helpers ───

    _id_counter = 0

    @classmethod
    def _next_id(cls):
        cls._id_counter += 1
        return f"g_{uuid.uuid4().hex}"

    @staticmethod
    def create_random_genome():
        """Crée un génome avec des gènes aléatoires dans leur plage définie."""
        genes = {}
        for name, min_v, max_v, default in GENES_META:
            genes[name] = random.uniform(min_v, max_v) if isinstance(default, float) else random.randint(min_v, max_v)
        return {
            "id": EvolutionManager._next_id(),
            "genes": genes,
            "seed": random.randint(0, 100000),
            "fitness": 0.0,
            "total_hits": 0,
            "draws_evaluated": 0,
            "generation": 0,
            "age": 0
        }

    @staticmethod
    def create_child(genome_a, genome_b, mutation_rate=MUTATION_RATE):
        """
        Crée un enfant à partir de deux parents par crossover + mutation.
        """
        child_genes = {}
        for name, min_v, max_v, default in GENES_META:
            if random.random() < CROSSOVER_RATE:
                # Crossover uniforme : on prend un gène aléatoire d'un parent
                parent = random.choice([genome_a, genome_b])
                child_genes[name] = parent['genes'].get(name, default)
            else:
                child_genes[name] = genome_a['genes'].get(name, default)
            
            # Mutation
            if random.random() < mutation_rate:
                if isinstance(default, float):
                    child_genes[name] = random.uniform(min_v, max_v)
                else:
                    child_genes[name] = random.randint(min_v, max_v)
        
        return {
            "id": EvolutionManager._next_id(),
            "genes": child_genes,
            "seed": random.randint(0, 100000),
            "fitness": 0.0,
            "total_hits": 0,
            "draws_evaluated": 0,
            "generation": max(genome_a.get('generation', 0), genome_b.get('generation', 0)) + 1,
            "age": 0
        }

    def mutate_genome(self, genome, mutation_rate=MUTATION_RATE):
        """Applique des mutations à un génome existant."""
        for name, min_v, max_v, default in GENES_META:
            if random.random() < mutation_rate:
                if isinstance(default, float):
                    genome['genes'][name] = random.uniform(min_v, max_v)
                else:
                    genome['genes'][name] = random.randint(min_v, max_v)
        genome['seed'] = random.randint(0, 100000)
        return genome

    # ─── Population Management ───

    def load_population(self):
        """Charge la population depuis le fichier JSON, ou en crée une nouvelle."""
        if os.path.exists(POOL_FILE):
            try:
                with open(POOL_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list) and len(data) >= 20:
                    print(f"📂 Population chargée : {len(data)} génomes (génération {data[0].get('generation', 0)})")
                    return data
            except Exception as e:
                print(f"⚠️ Erreur chargement pool : {e}")
        
        print("🌱 Création d'une nouvelle population initiale...")
        return self.create_initial_population()

    def create_initial_population(self, size=POPULATION_SIZE):
        """Crée une population diversifiée pour démarrer l'évolution."""
        population = []
        
        # Quelques archétypes de départ (stratégies connues)
        archetypes = [
            {"weight_maturity": 1.5, "weight_poisson": 0.8, "weight_mean_reversion": 0.3, "weight_bayesian": 0.2, "weight_correlation": 0.4, "weight_random": 0.1, "pool_size": 15},
            {"weight_maturity": 0.3, "weight_poisson": 1.5, "weight_mean_reversion": 0.5, "weight_bayesian": 1.0, "weight_correlation": 0.3, "weight_random": 0.2, "pool_size": 20},
            {"weight_maturity": 0.5, "weight_poisson": 0.5, "weight_mean_reversion": 1.5, "weight_bayesian": 0.5, "weight_correlation": 0.5, "weight_random": 0.1, "pool_size": 12},
            {"weight_maturity": 0.8, "weight_poisson": 0.8, "weight_mean_reversion": 0.8, "weight_bayesian": 0.8, "weight_correlation": 0.8, "weight_random": 0.0, "pool_size": 25},
            {"weight_maturity": 0.0, "weight_poisson": 0.0, "weight_mean_reversion": 0.0, "weight_bayesian": 0.0, "weight_correlation": 0.0, "weight_random": 1.0, "pool_size": 10},
        ]
        
        for arch in archetypes:
            genome = {
                "id": EvolutionManager._next_id(),
                "genes": arch,
                "seed": random.randint(0, 100000),
                "fitness": 0.0,
                "total_hits": 0,
                "draws_evaluated": 0,
                "generation": 0,
                "age": 0
            }
            population.append(genome)
        
        # On complète avec des génomes aléatoires
        while len(population) < size:
            population.append(self.create_random_genome())
        
        return population

    def save_population(self):
        """Sauvegarde la population dans le fichier JSON."""
        tmp_file = POOL_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(self.population, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, POOL_FILE)
        print(f"💾 Population sauvegardée : {len(self.population)} génomes")

    # ─── Sélection ───

    def get_top_genomes(self, n=4):
        """Classe les génomes en privilégiant un historique fiable."""
        sorted_pop = sorted(
            self.population,
            key=lambda x: (
                min(x.get("draws_evaluated", 0), 5),
                x.get("fitness", 0),
                x.get("draws_evaluated", 0)
            ),
            reverse=True
        )
        return sorted_pop[:n]

    def tournament_selection(self):
        """Sélection par tournoi : on prend le meilleur d'un sous-ensemble aléatoire."""
        # On filtre les génomes avec au moins 1 évaluation
        candidates = [ind for ind in self.population if ind.get('draws_evaluated', 0) > 0]
        if len(candidates) < TOURNAMENT_SIZE:
            candidates = self.population
        
        tournament = random.sample(candidates, min(TOURNAMENT_SIZE, len(candidates)))
        tournament.sort(key=lambda x: x.get('fitness', 0), reverse=True)
        return copy.deepcopy(tournament[0])

    # ─── Évolution (une génération) ───

    def evolve(self):
        """
        Exécute UN cycle complet d'évolution :
        1. Tri par fitness
        2. Élite : les meilleurs survivent
        3. Croisement des élites pour créer des enfants
        4. Mutation de certains enfants
        5. Injection de sang neuf
        6. Réinitialisation des fitness pour le prochain cycle
        """
        if len([ind for ind in self.population if ind.get('draws_evaluated', 0) > 0]) < 10:
            print("⏳ Pas assez de données pour évoluer. Besoin de plus de tirages évalués.")
            return False
        
        self.generation += 1
        print(f"\n🧬 Génération {self.generation} — Évolution en cours...")
        
        # Trier par fitness (descendant)
        self.population.sort(key=lambda x: x.get('fitness', 0), reverse=True)
        
        # Afficher le top 5
        print("  Top 5 avant évolution :")
        for i, ind in enumerate(self.population[:5]):
            print(f"    #{i+1} Fitness={ind.get('fitness', 0):.4f} "
                  f"(hits={ind.get('total_hits', 0)}/{ind.get('draws_evaluated', 0)}) "
                  f"age={ind.get('age', 0)}")
        
        # 1. Élite
        elite_count = max(5, int(len(self.population) * ELITE_RATIO))
        elite = [copy.deepcopy(ind) for ind in self.population[:elite_count]]
        
        # 2. Créer des enfants
        children = []
        needed = len(self.population) - len(elite) - int(len(self.population) * FRESH_BLOOD)
        
        for _ in range(needed):
            parent_a = self.tournament_selection()
            parent_b = self.tournament_selection()
            child = self.create_child(parent_a, parent_b)
            children.append(child)
        
        # 3. Sang neuf (exploration)
        new_blood_count = int(len(self.population) * FRESH_BLOOD)
        new_blood = [self.create_random_genome() for _ in range(new_blood_count)]
        
        # 4. Nouvelle population
        self.population = elite + children + new_blood
        
        # 5. Préserver la fitness des élites, reset pour les nouveaux
        for ind in elite:
            ind['age'] = ind.get('age', 0) + 1
        for ind in children + new_blood:
            ind['fitness'] = 0.0
            ind['total_hits'] = 0
            ind['draws_evaluated'] = 0
            ind['age'] = 0
        
        # 6. Sauvegarder
        self.save_population()
        print(f"✅ Évolution terminée. Nouvelle population : {len(self.population)} génomes")
        return True

    # ─── Interface Pipeline ───

    def evaluate(self, genome_index, ball_hits):
        """
        Enregistre le résultat d'un tirage pour un génome donné.
        """
        if 0 <= genome_index < len(self.population):
            ind = self.population[genome_index]
            ind['total_hits'] = ind.get('total_hits', 0) + ball_hits
            ind['draws_evaluated'] = ind.get('draws_evaluated', 0) + 1
            # Fitness = hits moyens par tirage
            ind['fitness'] = ind['total_hits'] / max(1, ind['draws_evaluated'])

    def get_population_stats(self):
        """Retourne des stats sur la population actuelle."""
        if not self.population:
            return {}
        evaluated = [ind for ind in self.population if ind.get('draws_evaluated', 0) > 0]
        return {
            "total": len(self.population),
            "evaluated": len(evaluated),
            "generation": self.generation,
            "top_fitness": max(ind.get('fitness', 0) for ind in evaluated) if evaluated else 0,
            "avg_fitness": sum(ind.get('fitness', 0) for ind in evaluated) / len(evaluated) if evaluated else 0
        }


if __name__ == "__main__":
    mgr = EvolutionManager()
    stats = mgr.get_population_stats()
    print(f"Stats population : {stats}")
    print("Top 5 génomes :")
    for i, g in enumerate(mgr.get_top_genomes(5)):
        print(f"  #{i+1} fitness={g.get('fitness', 0):.4f} genes={g['genes']}")
