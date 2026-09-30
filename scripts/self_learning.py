#!/usr/bin/env python3
"""
self_learning.py — Mémoire des recommandations et feedback loop pour alfred_trader
Enregistre chaque recommandation (buy/sell/target), vérifie les outcomes à postériori,
et ajuste les poids des différents signaux pour s'améliorer dans le temps.

Principe : bête de somme qui accumule des données, pas un LLM.
On tracke : qu'est-ce qu'on a recommandé → est-ce que ça a marché → on ajuste.

Framework : Gavekal (macroscopic trends) + Taleb (apprendre des erreurs)
"""
import json
import math
from pathlib import Path
from datetime import datetime, timedelta

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
STATE_DIR = WORKSPACE / "state" / "stock_watch"
LEARN_DIR = STATE_DIR / "learning"
PREDICTIONS_FILE = LEARN_DIR / "predictions.json"
WEIGHTS_FILE = LEARN_DIR / "weights.json"
ACCURACY_FILE = LEARN_DIR / "accuracy.json"

# ─── Poids initiaux des différents signaux ─────────────────
DEFAULT_WEIGHTS = {
    "rsi_oversold": 1.0,       # RSI bas (<30) → boost acheter
    "macd_bullish": 0.8,       # MACD haussier
    "volume_spike": 0.5,       # Volume anormal
    "dip_core": 0.9,           # Baisse sur une action Core
    "pea_bonus": 0.3,          # Bonus PEA
    "price_target": 1.0,       # Précision des targets de prix
    "news_catalyst": 0.8,      # Catalyseur événementiel (news_context)
    "ma_bounce": 0.6,          # Rebond sur moyenne mobile
    "sector_trend": 0.7,       # Tendance sectorielle
    "convexity": 0.4,          # Upside asymétrique (Taleb)
}

# Seuil pour considérer une recommandation comme "correcte"
TP_HIT_MARGIN = 0.02  # 2% de marge sur le target price
SL_HIT_MARGIN = 0.02


# ═══════════════════════════════════════════════════════════
# 1. INITIALISATION
# ═══════════════════════════════════════════════════════════

def _ensure_dirs():
    LEARN_DIR.mkdir(parents=True, exist_ok=True)


def load_weights() -> dict:
    """Charge les poids actuels ou retourne les poids par défaut."""
    _ensure_dirs()
    if WEIGHTS_FILE.exists():
        try:
            return json.loads(WEIGHTS_FILE.read_text())
        except Exception:
            pass
    return dict(DEFAULT_WEIGHTS)


def save_weights(weights: dict):
    """Sauvegarde les poids."""
    _ensure_dirs()
    WEIGHTS_FILE.write_text(json.dumps(weights, indent=2))


def load_predictions() -> list:
    """Charge l'historique des prédictions."""
    _ensure_dirs()
    if PREDICTIONS_FILE.exists():
        try:
            return json.loads(PREDICTIONS_FILE.read_text())
        except Exception:
            pass
    return []


def save_predictions(predictions: list):
    """Sauvegarde les prédictions."""
    _ensure_dirs()
    PREDICTIONS_FILE.write_text(json.dumps(predictions, indent=2))


# ═══════════════════════════════════════════════════════════
# 2. ENREGISTREMENT D'UNE RECOMMANDATION
# ═══════════════════════════════════════════════════════════

def record_prediction(
    ticker: str,
    name: str,
    recommendation: str,  # "ACHETER", "VENDRE", "SURVEILLER"
    score: int,
    price_at_time: float,
    target_tp1: float = None,
    target_tp2: float = None,
    stop_loss: float = None,
    reasons: list = None,
    signals_used: dict = None,
) -> dict:
    """Enregistre une recommandation dans l'historique.

    Retourne l'ID de la prédiction pour suivi ultérieur.
    """
    pred = {
        "id": f"{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "ticker": ticker,
        "name": name,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "recommendation": recommendation,
        "score": score,
        "price_at_time": price_at_time,
        "target_tp1": target_tp1,
        "target_tp2": target_tp2,
        "stop_loss": stop_loss,
        "reasons": reasons or [],
        "signals_used": signals_used or {},
        "outcome": None,  # "HIT_TP1", "HIT_TP2", "HIT_SL", "PENDING", "EXPIRED"
        "outcome_date": None,
        "actual_price_outcome": None,
        "pnl_pct": None,
        "checked": False,
    }

    predictions = load_predictions()
    predictions.append(pred)

    # Garder max 500 prédictions
    if len(predictions) > 500:
        predictions = predictions[-500:]

    save_predictions(predictions)

    return pred["id"]


# ═══════════════════════════════════════════════════════════
# 3. VÉRIFICATION DES OUTCOMES
# ═══════════════════════════════════════════════════════════

def check_outcomes(current_prices: dict) -> dict:
    """Vérifie quelles prédictions ont atteint leurs targets.

    current_prices: {ticker: price_actuel}
    Retourne le nombre de prédictions mises à jour.
    """
    predictions = load_predictions()
    now = datetime.now()
    updated = 0
    new_accuracy_data = []

    for pred in predictions:
        if pred.get("checked") or pred.get("outcome") in ("HIT_TP1", "HIT_TP2", "HIT_SL", "EXPIRED"):
            continue

        ticker = pred["ticker"]
        current_price = current_prices.get(ticker)
        if current_price is None and pred.get("price_at_time"):
            continue

        entry = pred.get("price_at_time")
        tp1 = pred.get("target_tp1")
        tp2 = pred.get("target_tp2")
        sl = pred.get("stop_loss")

        if current_price is None:
            continue

        # Vérifier TP et SL
        # Pour un achat : le prix doit monter jusqu'au TP
        direction = 1 if pred.get("recommendation") in ("ACHETER", "SURVEILLER") else -1

        if direction == 1:
            # Recommandation d'achat
            if tp1 and current_price >= tp1 * (1 - TP_HIT_MARGIN):
                pred["outcome"] = "HIT_TP1"
                pred["outcome_date"] = now.strftime("%Y-%m-%d %H:%M")
                pred["actual_price_outcome"] = current_price
                pred["pnl_pct"] = round((current_price / entry - 1) * 100, 1) if entry else 0
                pred["checked"] = True
                updated += 1
            elif tp2 and current_price >= tp2 * (1 - TP_HIT_MARGIN):
                pred["outcome"] = "HIT_TP2"
                pred["outcome_date"] = now.strftime("%Y-%m-%d %H:%M")
                pred["actual_price_outcome"] = current_price
                pred["pnl_pct"] = round((current_price / entry - 1) * 100, 1) if entry else 0
                pred["checked"] = True
                updated += 1
            elif sl and current_price <= sl * (1 + SL_HIT_MARGIN):
                pred["outcome"] = "HIT_SL"
                pred["outcome_date"] = now.strftime("%Y-%m-%d %H:%M")
                pred["actual_price_outcome"] = current_price
                pred["pnl_pct"] = round((current_price / entry - 1) * 100, 1) if entry else 0
                pred["checked"] = True
                updated += 1
            else:
                # Expiré après 30 jours sans mouvement
                try:
                    pred_date = datetime.strptime(pred.get("date", "")[:10], "%Y-%m-%d")
                    if (now - pred_date).days > 30:
                        pred["outcome"] = "EXPIRED"
                        pred["actual_price_outcome"] = current_price
                        pred["pnl_pct"] = round((current_price / entry - 1) * 100, 1) if entry else 0
                        pred["checked"] = True
                        updated += 1
                except Exception:
                    pass
        else:
            # Recommandation de vente
            if sl and current_price <= sl * (1 + SL_HIT_MARGIN):
                pred["outcome"] = "HIT_SL"
                pred["outcome_date"] = now.strftime("%Y-%m-%d %H:%M")
                pred["actual_price_outcome"] = current_price
                pred["pnl_pct"] = round((entry / current_price - 1) * 100, 1) if entry else 0
                pred["checked"] = True
                updated += 1
            else:
                try:
                    pred_date = datetime.strptime(pred.get("date", "")[:10], "%Y-%m-%d")
                    if (now - pred_date).days > 30:
                        pred["outcome"] = "EXPIRED"
                        pred["actual_price_outcome"] = current_price
                        pred["checked"] = True
                        updated += 1
                except Exception:
                    pass

    if updated > 0:
        save_predictions(predictions)

    return {"updated": updated, "total_open": sum(1 for p in predictions if p.get("outcome") is None)}


# ═══════════════════════════════════════════════════════════
# 4. AJUSTEMENT DES POIDS (apprentissage)
# ═══════════════════════════════════════════════════════════

def update_weights() -> dict:
    """Ajuste les poids en fonction des outcomes passés.

    Principe : si un signal était présent et que la prédiction a réussi,
    son poids augmente. Si elle a échoué, son poids diminue.
    """
    predictions = load_predictions()
    weights = load_weights()

    # Ne regarder que les prédictions complétées (checked)
    completed = [p for p in predictions if p.get("checked") and p.get("signals_used")]
    if len(completed) < 3:
        return weights  # Pas assez de data pour ajuster

    # Compter les succès/échecs par type de signal
    signal_stats = {}  # {signal_name: {success: n, total: n, total_pnl: n}}

    for pred in completed:
        success = pred.get("outcome") in ("HIT_TP1", "HIT_TP2")
        pnl = pred.get("pnl_pct") or 0
        signals = pred.get("signals_used", {})

        for signal_name, was_used in signals.items():
            if not was_used:
                continue
            if signal_name not in signal_stats:
                signal_stats[signal_name] = {"success": 0, "fail": 0, "total_pnl": 0.0, "count": 0}
            if success:
                signal_stats[signal_name]["success"] += 1
            else:
                signal_stats[signal_name]["fail"] += 1
            signal_stats[signal_name]["total_pnl"] += pnl
            signal_stats[signal_name]["count"] += 1

    # Ajuster les poids
    adjustments = {}
    for signal_name, stats in signal_stats.items():
        if stats["count"] < 2:
            continue

        success_rate = stats["success"] / (stats["success"] + stats["fail"]) if (stats["success"] + stats["fail"]) > 0 else 0.5
        avg_pnl = stats["total_pnl"] / stats["count"] if stats["count"] > 0 else 0
        # Poids actuel
        current_w = weights.get(signal_name, 0.5)

        # Nouveau poids : moyenne entre le poids actuel et le succès rate
        # Plus on accumule de data, moins on bouge vite
        learning_speed = min(0.3, 1.0 / (1 + stats["count"] / 5))
        new_weight = current_w * (1 - learning_speed) + (success_rate * 2) * learning_speed

        # Bonus/malus basé sur le PnL moyen
        if avg_pnl > 3:
            new_weight *= 1.05
        elif avg_pnl < -3:
            new_weight *= 0.95

        # Saturer entre 0.1 et 2.0
        new_weight = max(0.1, min(2.0, new_weight))
        new_weight = round(new_weight, 2)

        if abs(new_weight - current_w) > 0.05:
            adjustments[signal_name] = {
                "old": current_w,
                "new": new_weight,
                "success_rate": round(success_rate, 2),
                "samples": stats["count"],
            }
            weights[signal_name] = new_weight

    save_weights(weights)

    # Sauvegarder le rapport d'accuracy
    accuracy = {
        "last_update": datetime.now().isoformat(),
        "total_predictions": len(completed),
        "success_rate": round(sum(1 for p in completed if p.get("outcome") in ("HIT_TP1", "HIT_TP2")) / len(completed) * 100, 1) if completed else 0,
        "avg_pnl": round(sum(p.get("pnl_pct") or 0 for p in completed) / len(completed), 1) if completed else 0,
        "adjustments": adjustments,
    }
    ACCURACY_FILE.parent.mkdir(parents=True, exist_ok=True)
    ACCURACY_FILE.write_text(json.dumps(accuracy, indent=2))

    return weights


# ═══════════════════════════════════════════════════════════
# 5. UTILITAIRE : filtrer les recommandations avec les poids
# ═══════════════════════════════════════════════════════════

def weighted_score(raw_score: int, signals_used: dict) -> float:
    """Applique les poids appris à un score brut de conviction."""
    weights = load_weights()
    final_score = raw_score

    for signal_name, was_used in signals_used.items():
        if was_used and signal_name in weights:
            w = weights[signal_name]
            # Les signaux avec poids > 1 amplifient l'effet
            if raw_score >= 50:
                final_score += (w - 1) * 5  # Bonus pour signaux fiables
            else:
                final_score += (w - 1) * 3  # Malus pour signaux faibles

    return min(100, max(0, round(final_score, 1)))


# ═══════════════════════════════════════════════════════════
# 6. RAPPORT
# ═══════════════════════════════════════════════════════════

def print_learning_report():
    """Affiche l'état de l'apprentissage."""
    weights = load_weights()
    predictions = load_predictions()
    completed = [p for p in predictions if p.get("checked")]
    pending = [p for p in predictions if not p.get("checked") and p.get("outcome") is None]

    hits_tp1 = sum(1 for p in completed if p.get("outcome") == "HIT_TP1")
    hits_tp2 = sum(1 for p in completed if p.get("outcome") == "HIT_TP2")
    hits_sl = sum(1 for p in completed if p.get("outcome") == "HIT_SL")
    expired = sum(1 for p in completed if p.get("outcome") == "EXPIRED")
    avg_pnl = round(sum(p.get("pnl_pct") or 0 for p in completed) / len(completed), 1) if completed else 0

    print(f"\n🧠 **ALFRED SELF-LEARNING**")
    print("=" * 50)
    print(f"Prédictions totales : {len(predictions)}")
    print(f"   Complétées : {len(completed)}")
    print(f"   En cours : {len(pending)}")
    print(f"   TP1 atteint : {hits_tp1}")
    print(f"   TP2 atteint : {hits_tp2}")
    print(f"   Stop Loss : {hits_sl}")
    print(f"   Expirées : {expired}")
    print(f"   PnL moyen : {avg_pnl:+.1f}%")
    print()

    print("📊 Poids des signaux appris :")
    for signal, weight in sorted(weights.items(), key=lambda x: -x[1]):
        bar = "█" * int(weight * 10)
        print(f"   {signal:<20} {weight:+.2f} {bar}")

    return {
        "total": len(predictions),
        "completed": len(completed),
        "pending": len(pending),
        "tp_rate": round((hits_tp1 + hits_tp2) / len(completed) * 100, 1) if completed else 0,
        "avg_pnl": avg_pnl,
    }


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if "--check" in sys.argv:
        # Tester avec des prix factices
        print("Vérification des outcomes...")
        res = check_outcomes({})
        print(json.dumps(res, indent=2))
    elif "--reset" in sys.argv:
        if input("⚠️ Réinitialiser toutes les prédictions ? (o/N) ").lower() == "o":
            save_predictions([])
            save_weights(dict(DEFAULT_WEIGHTS))
            print("✅ Réinitialisé.")
    else:
        print_learning_report()
