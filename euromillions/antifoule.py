#!/usr/bin/env python3
"""
Anti-foule v2 (anti-partage) pour Euromillions
==============================================
PRINCIPE : la probabilite de gagner est IDENTIQUE pour toutes les grilles.
Le seul levier d'esperance de gain reel au loto = le PARTAGE : si plusieurs
joueurs jouent la meme combinaison, le lot est divise. Jouer des combinaisons
IMPOPULAIRES augmente donc l'esperance de gain (pas la chance de gagner).

Modele de popularite (biais documentes des joueurs) :
  - numeros <= 31 (dates) surjoues, d'autant plus que le numero est petit (1-12)
  - chiffres "porte-bonheur" (7, 3, 9, 11) surjoues
  - motifs visibles : clusters serres, suites, lignes/diagonales de la grille,
    dizaines completes, multiples de 5
  - grilles deja sorties recemment : moins jouees (biais "froid") -> leger bonus
Score : popularite relative de la grille (1.0 = grille moyenne).
esperance_relative = 1 / score  (approximation 1er ordre du non-partage)

Usage:
    python3 antifoule.py                      # 1 grille anti-foule
    python3 antifoule.py --count 5 --seed 42  # deterministe
    python3 antifoule.py --score "3 7 12 25 31 / 3 7"   # note une grille
    python3 antifoule.py --stars
"""
import argparse
import random
import statistics

BALLS_MAX = 50
STARS_MAX = 12
GRID_WIDTH = 7  # grille visuelle 1-50 sur 7 colonnes


# ---------------------------------------------------------------- popularite
_LUCKY = {7: 2.10, 1: 1.90, 3: 1.80, 9: 1.75, 11: 1.70, 2: 1.70,
          5: 1.65, 6: 1.60, 8: 1.60, 10: 1.55, 12: 1.55, 4: 1.50}


def ball_popularity(b):
    """Popularite relative d'une boule (1.0 = neutre, >1 = surjouee)."""
    if b <= 12:
        return _LUCKY[b]
    if b <= 31:
        return round(1.45 - (b - 13) * 0.0135, 4)   # 1.45 -> 1.21
    return round(1.02 - (b - 32) * 0.002, 4)        # 1.02 -> 0.98


def star_popularity(s):
    return {1: 1.90, 2: 1.80, 3: 1.80, 4: 1.70, 5: 1.60, 6: 1.60,
            7: 1.80, 8: 1.30, 9: 1.25, 10: 1.20, 11: 1.05, 12: 1.00}[s]


_MEAN_BALL_POP = statistics.mean(ball_popularity(b) for b in range(1, BALLS_MAX + 1))
_MEAN_STAR_POP = statistics.mean(star_popularity(s) for s in range(1, STARS_MAX + 1))


# ------------------------------------------------------------ motifs visibles
def _longest_run(sorted_balls):
    best = cur = 1
    for i in range(1, len(sorted_balls)):
        cur = cur + 1 if sorted_balls[i] - sorted_balls[i - 1] == 1 else 1
        best = max(best, cur)
    return best


def _arith_run(sorted_balls):
    """Plus longue suite arithmetique (pas constant >= 1)."""
    best = 2
    for i in range(len(sorted_balls) - 2):
        d = sorted_balls[i + 1] - sorted_balls[i]
        run = 2
        j = i + 1
        while j + 1 < len(sorted_balls) and sorted_balls[j + 1] - sorted_balls[j] == d:
            run += 1
            j += 1
        best = max(best, run)
    return best


def pattern_multiplier(balls, history_last=None):
    """Multiplicateur de popularite lie aux motifs visibles (>1 = attire l'oeil)."""
    m = 1.0
    sb = sorted(balls)
    span = sb[-1] - sb[0]
    if span < 15:
        m *= 1.25                      # cluster serre
    if _longest_run(sb) >= 3:
        m *= 1.20                      # 3+ consecutifs
    if _arith_run(sb) >= 3:
        m *= 1.15                      # suite arithmetique (ex 5-10-15)
    if sum(b % 5 == 0 for b in sb) >= 2:
        m *= 1.08                      # multiples de 5
    if sum(b % 10 == 0 for b in sb) >= 2:
        m *= 1.08                      # multiples de 10
    decades = {}
    for b in sb:
        decades[(b - 1) // 10] = decades.get((b - 1) // 10, 0) + 1
    if max(decades.values()) >= 3:
        m *= 1.15                      # meme dizaine
    rows = {}
    for b in sb:
        rows[(b - 1) // GRID_WIDTH] = rows.get((b - 1) // GRID_WIDTH, 0) + 1
    if max(rows.values()) >= 3:
        m *= 1.15                      # meme ligne de la grille visuelle
    if all(b <= 31 for b in sb):
        m *= 1.50                      # grille "anniversaires"
    if history_last:
        repeats = len(set(sb) & set(history_last))
        if repeats >= 2:
            m *= 0.93                  # biais "froid" : les sortants sont avoid
    return round(m, 4)


# ------------------------------------------------------------------ scoring
def grid_popularity(balls, stars, history_last=None):
    """Popularite relative de la grille (1.0 = grille moyenne)."""
    ball_part = 1.0
    for b in balls:
        ball_part *= ball_popularity(b) / _MEAN_BALL_POP
    star_part = 1.0
    for s in stars:
        star_part *= star_popularity(s) / _MEAN_STAR_POP
    return round(ball_part * (star_part ** 0.5) * pattern_multiplier(balls, history_last), 4)


def expected_share(balls, stars, history_last=None):
    """Part de lot attendue (1.0 = grille moyenne). Esperance relative = 1/score."""
    return grid_popularity(balls, stars, history_last)


def describe(balls, stars, history_last=None):
    score = grid_popularity(balls, stars, history_last)
    return {
        "popularity_score": score,
        "expected_share_vs_average": score,
        "unpopularity_gain_pct": round((1.0 / score - 1.0) * 100, 1) if score > 0 else 0.0,
        "labels": _labels(balls, stars),
    }


def _labels(balls, stars):
    out = []
    high = sum(b > 31 for b in balls)
    out.append(f"{high}/5 numeros > 31")
    if len(set(balls) & set(range(1, 13))) == 0:
        out.append("aucun mois/jour bas")
    if not any(b in (7, 1, 3, 9, 11) for b in balls):
        out.append("aucun chiffre porte-bonheur surjoue")
    if _arith_run(sorted(balls)) < 3 and _longest_run(sorted(balls)) < 3:
        out.append("aucun motif visible")
    if stars and max(stars) >= 10:
        out.append("etoiles hautes (peu jouees)")
    return out


# --------------------------------------------------------------- validation
def _validate(balls):
    """Contraintes de lisibilite (grille plausible, non degeneree)."""
    if len(set(balls)) != 5:
        return False
    evens = len([b for b in balls if b % 2 == 0])
    if evens not in (2, 3):
        return False
    total = sum(balls)
    if total < 100 or total > 175:
        return False
    if len([b for b in balls if b > 31]) < 2:
        return False
    sb = sorted(balls)
    consecutives = sum(1 for i in range(4) if sb[i + 1] - sb[i] == 1)
    if consecutives > 2:
        return False
    return True


def _weighted_pick(pool, weights, rng):
    return rng.choices(pool, weights=weights, k=1)[0]


def _sample_balls(rng, history_last=None):
    pool = list(range(1, BALLS_MAX + 1))
    weights = [1.0 / ball_popularity(b) for b in pool]
    if history_last:
        for i, b in enumerate(pool):
            if b in history_last:
                weights[i] *= 0.85
    chosen = set()
    guard = 0
    while len(chosen) < 5 and guard < 500:
        guard += 1
        chosen.add(_weighted_pick(pool, weights, rng))
    return sorted(chosen)


def _sample_stars(rng):
    pool = list(range(1, STARS_MAX + 1))
    weights = [1.0 / star_popularity(s) for s in pool]
    stars = set()
    guard = 0
    while len(stars) < 2 and guard < 200:
        guard += 1
        stars.add(_weighted_pick(pool, weights, rng))
    return sorted(stars)


def _feed_fallback(rng, history_last=None):
    """Grille de secours : moitie haute, sans motif."""
    while True:
        balls = sorted(rng.sample(range(20, 51), 5))
        if _validate(balls):
            return balls


def generate_antifoule_grid(rng=None, n_balls=5, n_stars=2, seed=None,
                            history_last=None, iterations=400):
    """Grille anti-partage. Deterministe si seed est fourni.

    Retourne (balls, stars) pour rester compatible avec l'API historique.
    """
    if seed is not None:
        rng = random.Random(seed)
    elif rng is None:
        rng = random.Random()
    assert n_balls == 5 and n_stars == 2, "seules les grilles 5/2 sont supportees"

    best, best_score = None, float("inf")
    for _ in range(6):                       # 6 departs aleatoires
        balls = _sample_balls(rng, history_last)
        if not _validate(balls):
            cand = _feed_fallback(rng, history_last)
            if cand:
                balls = cand
        score = grid_popularity(balls, stars=_sample_stars(rng), history_last=history_last)
        # recherche locale : echanger une boule contre une meilleure
        for _ in range(iterations):
            i = rng.randrange(5)
            remaining = [x for x in balls if x != balls[i]]
            replacement = rng.choice([b for b in range(1, BALLS_MAX + 1) if b not in remaining])
            trial = sorted(remaining + [replacement])
            if len(set(trial)) != 5 or not _validate(trial):
                continue
            t_score = grid_popularity(trial, stars=_sample_stars(rng), history_last=history_last)
            if t_score < score:
                balls, score = trial, t_score
        if score < best_score:
            best, best_score = balls, score

    stars = _sample_stars(rng)
    best_stars, best_star_score = stars, float("inf")
    for _ in range(60):
        s_try = _sample_stars(rng)
        s_score = grid_popularity(best, s_try, history_last)
        if s_score < best_star_score:
            best_stars, best_star_score = s_try, s_score
    return sorted(best), sorted(best_stars)


def main():
    parser = argparse.ArgumentParser(description="Grille anti-foule Euromillions v2")
    parser.add_argument("--stars", action="store_true", help="Affiche seulement les etoiles")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--seed", type=int, default=None, help="Deterministe")
    parser.add_argument("--score", type=str, default=None,
                        help='Note une grille, format "1 2 3 4 5 / 3 7"')
    args = parser.parse_args()

    if args.score:
        raw = args.score.replace("/", " ").replace(",", " ").split()
        nums = [int(x) for x in raw]
        balls, stars = sorted(nums[:5]), sorted(nums[5:7])
        info = describe(balls, stars)
        print(f"Grille {balls} | Etoiles {stars}")
        print(f"  popularite relative : {info['popularity_score']} (1.0 = moyenne)")
        print(f"  partage attendu     : {info['expected_share_vs_average']:.2f}x la normale")
        print(f"  gain d'esperance    : {info['unpopularity_gain_pct']:+.1f}%")
        print(f"  {' | '.join(info['labels'])}")
        return

    for i in range(args.count):
        seed = args.seed + i if args.seed is not None else None
        balls, stars = generate_antifoule_grid(seed=seed)
        info = describe(balls, stars)
        if args.stars:
            print(f"Etoiles anti-foule : {stars}  (pop {info['popularity_score']})")
        else:
            print(f"Grille {i + 1} : {balls} | Etoiles {stars}")
            print(f"  popularite {info['popularity_score']} | gain d'esperance "
                  f"{info['unpopularity_gain_pct']:+.1f}% | {' | '.join(info['labels'])}")


if __name__ == "__main__":
    main()

