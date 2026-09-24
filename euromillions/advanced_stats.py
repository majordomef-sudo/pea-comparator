import pandas as pd
import numpy as np
import pickle
import os
from collections import Counter

BASE_DIR = "/home/ubuntu/.openclaw/workspace/euromillions"
HISTORY_FILE = os.path.join(BASE_DIR, 'history.csv')
STATS_FILE = os.path.join(BASE_DIR, 'advanced_stats.pkl')

def calculate_gap_analysis(history_matrix=None):
    """Analyse des ecarts (Gap Analysis) optimisee avec numpy."""
    print("Calcul de l'analyse des ecarts (Gap Analysis)...")
    if history_matrix is None:
        df = pd.read_csv(HISTORY_FILE, sep=";")
        df["date_de_tirage"] = pd.to_datetime(df["date_de_tirage"], dayfirst=True)
        df = df.sort_values("date_de_tirage")
        history_matrix = df[[f"boule_{i}" for i in range(1, 6)]].values
    
    n_rows = history_matrix.shape[0]
    gaps = {}
    avg_gaps = {}
    
    # Precompute: for each number, create a boolean mask of presence
    for b in range(1, 51):
        # Find rows where number b appears
        presence = np.any(history_matrix == b, axis=1)
        indices = np.where(presence)[0]
        
        if len(indices) == 0:
            gaps[b] = n_rows
            avg_gaps[b] = 50
        else:
            # Current gap = rows since last appearance
            current_gap = n_rows - 1 - indices[-1]
            gaps[b] = current_gap
            
            # Gaps between appearances
            if len(indices) > 1:
                all_gaps = np.diff(indices) - 1
                avg_gaps[b] = np.mean(all_gaps) if len(all_gaps) > 0 else 50
            else:
                avg_gaps[b] = indices[0] + 1  # gap before first appearance
    return gaps, avg_gaps


def calculate_correlations(history_matrix=None):
    """Calcule la matrice de co-occurrence des boules (1-50).
    
    Version vectorisée numpy : 10 opérations au lieu de (n_draws × 10).
    """
    print("🚀 Calcul de la matrice de corrélation (Affinités)...")
    if history_matrix is None:
        df = pd.read_csv(HISTORY_FILE, sep=';')
        history_matrix = df[[f'boule_{i}' for i in range(1, 6)]].values
    
    # Matrice 51x51 pour inclure l'index 1-50
    matrix = np.zeros((51, 51), dtype=np.int32)
    
    # Vectorisation : toutes les paires de colonnes (5 choose 2 = 10 paires)
    pairs = np.triu_indices(5, k=1)  # [(0,0,0,0,1,1,1,2,2,3), (1,2,3,4,2,3,4,3,4,4)]
    
    for c1, c2 in zip(pairs[0], pairs[1]):
        b1 = history_matrix[:, c1]
        b2 = history_matrix[:, c2]
        np.add.at(matrix, (b1, b2), 1)
        np.add.at(matrix, (b2, b1), 1)
    
    return matrix, len(history_matrix)

def calculate_star_gaps(stars_matrix=None):
    """Calcule les écarts des étoiles sur une matrice chronologique."""
    if stars_matrix is None:
        df = pd.read_csv(HISTORY_FILE, sep=";")
        df["date_de_tirage"] = pd.to_datetime(df["date_de_tirage"], dayfirst=True, errors="raise")
        df = df.sort_values("date_de_tirage")
        stars_matrix = df[[f"etoile_{i}" for i in range(1, 3)]].values
    star_gaps = {}
    star_avg_gaps = {}
    for s in range(1, 13):
        presence = np.any(stars_matrix == s, axis=1)
        indices = np.where(presence)[0]
        if len(indices) == 0:
            star_gaps[s] = len(stars_matrix)
            star_avg_gaps[s] = 12.0
        else:
            star_gaps[s] = len(stars_matrix) - 1 - indices[-1]
            intervals = np.diff(indices) - 1
            star_avg_gaps[s] = float(np.mean(intervals)) if len(intervals) else float(indices[0])
    return star_gaps, star_avg_gaps


def calculate_star_correlation(stars_matrix=None):
    """Calcule la matrice de cooccurrence entre étoiles."""
    if stars_matrix is None:
        df = pd.read_csv(HISTORY_FILE, sep=";")
        stars_matrix = df[[f"etoile_{i}" for i in range(1, 3)]].values
    matrix = np.zeros((13, 13), dtype=np.int32)
    for s1, s2 in stars_matrix:
        matrix[int(s1), int(s2)] += 1
        matrix[int(s2), int(s1)] += 1
    return matrix

def main():
    try:
        # Read CSV once for all functions
        df = pd.read_csv(HISTORY_FILE, sep=";")
        df["date_de_tirage"] = pd.to_datetime(df["date_de_tirage"], dayfirst=True)
        df = df.sort_values("date_de_tirage")
        history_matrix = df[[f"boule_{i}" for i in range(1, 6)]].values
        stars_matrix = df[[f"etoile_{i}" for i in range(1, 3)]].values

        gaps, avg_gaps = calculate_gap_analysis(history_matrix)
        correlations, total_draws = calculate_correlations(history_matrix)
        star_gaps, star_avg_gaps = calculate_star_gaps(stars_matrix)
        star_corr = calculate_star_correlation(stars_matrix)
        
        stats = {
            "current_gaps": gaps,
            "average_gaps": avg_gaps,
            "correlation_matrix": correlations,
            "star_current_gaps": star_gaps,
            "star_average_gaps": star_avg_gaps,
            "star_correlation_matrix": star_corr,
            "total_draws": total_draws
        }
        
        with open(STATS_FILE, 'wb') as f:
            pickle.dump(stats, f)
            
        print(f"✅ Statistiques avancées sauvegardées dans {STATS_FILE}")
        print(f"   {total_draws} tirages analysés")
        
        # Debug: Afficher les 5 numéros les plus "mûrs"
        maturity_scores = []
        for b in range(1, 51):
            score = gaps[b] / avg_gaps[b] if avg_gaps[b] > 0 else 0
            maturity_scores.append((b, score))
        
        maturity_scores.sort(key=lambda x: x[1], reverse=True)
        print("\n--- Top 5 Numéros les plus 'Mûrs' (Écart > Moyenne) ---")
        for b, s in maturity_scores[:5]:
            print(f"Numéro {b} : Score {s:.2f} (Écart actuel: {gaps[b]}, Moyenne: {avg_gaps[b]:.1f})")
        
        # Debug: Afficher les 3 étoiles les plus "mûres"
        star_scores = []
        for s in range(1, 13):
            score = star_gaps[s] / star_avg_gaps[s] if star_avg_gaps[s] > 0 else 0
            star_scores.append((s, score))
        star_scores.sort(key=lambda x: x[1], reverse=True)
        print("\n--- Top 3 Étoiles les plus 'Mûres' ---")
        for s, sc in star_scores[:3]:
            print(f"Étoile {s} : Score {sc:.2f} (Écart: {star_gaps[s]}, Moyenne: {star_avg_gaps[s]:.1f})")

    except Exception as e:
        print(f"❌ Erreur : {e}")

if __name__ == "__main__":
    main()
