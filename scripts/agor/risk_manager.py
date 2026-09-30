#!/usr/bin/env python3
"""
risk_manager.py — Gestion des risques Alfred AGOR
Inspiré de NoFx (safety mode) + ai-hedge-fund (risk_manager)

Fonctions :
1. Volatility-adjusted position sizing
2. Portfolio correlation check
3. Max drawdown monitoring
4. 🌟 SAFETY MODE : after 3 consecutive wrong calls, freeze trades
5. Sector concentration limits
"""
import json
import math
from pathlib import Path
from datetime import datetime, timedelta

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
STATE_DIR = WORKSPACE / "state" / "stock_watch"
SAFETY_FILE = STATE_DIR / "risk_safety.json"

# Configuration
MAX_CONSECUTIVE_ERRORS = 3      # Combien d'erreurs avant safety mode
SAFETY_COOLDOWN_DAYS = 3        # Combien de jours en observation
MAX_SECTOR_EXPOSURE = 0.30      # Max 30% dans un même secteur
MAX_DRAWDOWN_TRIGGER = -0.15    # -15% de drawdown → alerte
VOLATILITY_POSITION_CAP = 0.25  # Max 25% du portefeuille par position


def _ensure():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# 1. SAFETY MODE (NoFx pattern)
# ═══════════════════════════════════════════════════════════

def get_safety_state() -> dict:
    """Charge l'état du safety mode."""
    _ensure()
    if SAFETY_FILE.exists():
        try:
            return json.loads(SAFETY_FILE.read_text())
        except Exception:
            pass
    return {
        "mode": "normal",  # "normal" | "observation" | "frozen"
        "consecutive_errors": 0,
        "last_error_date": None,
        "frozen_since": None,
        "auto_unfreeze_at": None,
        "total_frozen_trades": 0,
        "history": [],
    }


def save_safety_state(state: dict):
    _ensure()
    SAFETY_FILE.write_text(json.dumps(state, indent=2))


def record_outcome(success: bool, ticker: str = "", pnl: float = 0.0):
    """Enregistre le résultat d'un trade et ajuste le safety mode.

    Appelé après chaque fermeture de position (réelle ou papier).
    """
    state = get_safety_state()

    entry = {
        "date": datetime.now().isoformat(),
        "success": success,
        "ticker": ticker,
        "pnl": round(pnl, 2),
    }
    state["history"].append(entry)
    if len(state["history"]) > 50:
        state["history"] = state["history"][-50:]

    if not success:
        state["consecutive_errors"] += 1
        state["last_error_date"] = datetime.now().isoformat()

        # Safety mode déclenché ?
        if state["consecutive_errors"] >= MAX_CONSECUTIVE_ERRORS:
            state["mode"] = "observation"
            state["frozen_since"] = datetime.now().isoformat()
            state["auto_unfreeze_at"] = (datetime.now() + timedelta(days=SAFETY_COOLDOWN_DAYS)).isoformat()
            state["consecutive_errors"] = 0
            state["total_frozen_trades"] += 1
    else:
        # Un succès réinitialise le compteur
        state["consecutive_errors"] = 0

    save_safety_state(state)

    return state


def check_safety() -> dict:
    """Vérifie l'état du safety mode. Retourne les restrictions en cours."""
    state = get_safety_state()

    now = datetime.now()

    if state["mode"] == "observation":
        unfreeze_at = state.get("auto_unfreeze_at")
        if unfreeze_at:
            try:
                unfreeze_dt = datetime.fromisoformat(unfreeze_at)
                if now >= unfreeze_dt:
                    state["mode"] = "normal"
                    state["frozen_since"] = None
                    state["auto_unfreeze_at"] = None
                    state["consecutive_errors"] = 0
                    save_safety_state(state)
                    return {
                        "restricted": False,
                        "mode": "normal",
                        "message": "Safety mode auto-désactivé (cooldown terminé)",
                    }
            except Exception:
                pass

        return {
            "restricted": True,
            "mode": "observation",
            "message": f"🔒 Safety mode : observation uniquement jusqu'à {state.get('auto_unfreeze_at', '?')[:10]} ({SAFETY_COOLDOWN_DAYS}j)",
            "frozen_since": state.get("frozen_since"),
            "auto_unfreeze_at": state.get("auto_unfreeze_at"),
            "last_error": state.get("last_error_date"),
        }

    return {
        "restricted": False,
        "mode": "normal",
        "message": "Safety mode désactivé — trading normal",
    }


# ═══════════════════════════════════════════════════════════
# 2. RISK ASSESSMENT
# ═══════════════════════════════════════════════════════════

def assess_portfolio_risk(positions: list, current_prices: dict) -> dict:
    """Évalue le risque du portefeuille actuel.

    Retourne un dict avec les métriques de risque.
    """
    if not positions:
        return {
            "risk_level": "low",
            "max_drawdown": 0,
            "sector_exposure": {},
            "warnings": [],
        }

    warnings = []

    # Sector exposure
    sector_counts = {}
    for pos in positions:
        sector = pos.get("sector", "unknown")
        sector_counts[sector] = sector_counts.get(sector, 0) + 1

    for sector, count in sector_counts.items():
        exposure = count / len(positions)
        if exposure > MAX_SECTOR_EXPOSURE:
            warnings.append(f"⚠️ Sur-exposition au secteur {sector} ({exposure:.0%})")

    # PnL des positions
    total_pnl_pct = sum(pos.get("pnl_pct", 0) for pos in positions) / max(len(positions), 1)
    max_drawdown = min(pos.get("pnl_pct", 0) for pos in positions) if positions else 0

    risk_level = "low"
    if total_pnl_pct < -10 or max_drawdown < MAX_DRAWDOWN_TRIGGER:
        risk_level = "high"
        warnings.append(f"🔴 Drawdown élevé : {max_drawdown:.0f}% sur une position")
    elif total_pnl_pct < -5:
        risk_level = "medium"
        warnings.append(f"🟡 Perte moyenne : {total_pnl_pct:.1f}%")

    return {
        "risk_level": risk_level,
        "max_drawdown": round(max_drawdown, 1),
        "sector_exposure": sector_counts,
        "warnings": warnings,
        "position_count": len(positions),
    }


def assess_ticker_risk(ticker: str, price_data: dict, stock: dict, portfolio_prices: dict = None) -> dict:
    """Évalue le risque d'un ticker individuel.

    Donne un score de risque (0-100) et une taille max recommandée.
    """
    rsi = price_data.get("rsi_14", 50)
    change_7d = price_data.get("change_7d_pct", 0)
    volatility = price_data.get("daily_volatility", 2.0)
    price = price_data.get("price")

    risk_score = 30  # Baseline
    reasons = []

    # RSI extrême
    if rsi > 80 or rsi < 20:
        risk_score += 20
        reasons.append(f"RSI extrême ({rsi:.0f})")
    elif rsi > 70 or rsi < 30:
        risk_score += 10
        reasons.append(f"RSI élevé/bas ({rsi:.0f})")

    # Volatilité
    if volatility and volatility > 4:
        risk_score += 15
        reasons.append(f"Volatilité élevée ({volatility:.1f}%)")
    elif volatility and volatility > 3:
        risk_score += 5
        reasons.append(f"Volatilité modérée ({volatility:.1f}%)")

    # Baisse violente
    if change_7d and change_7d < -10:
        risk_score += 15
        reasons.append(f"Baisse violente {change_7d:.0f}%")
    elif change_7d and change_7d < -5:
        risk_score += 5
        reasons.append(f"Baisse modérée {change_7d:.0f}%")

    # Core = moins risqué
    is_core = stock.get("risk_profile") in ("Defensive", "Defensive Growth")
    if is_core:
        risk_score -= 10
        reasons.append("Core stock (défensif)")

    # Position sizing
    if price and price > 0:
        max_allocation_ratio = max(0.05, VOLATILITY_POSITION_CAP * (30 / max(risk_score, 15)))
    else:
        max_allocation_ratio = 0.1

    risk_score = max(0, min(100, risk_score))

    risk_level = "low"
    if risk_score >= 60:
        risk_level = "high"
    elif risk_score >= 35:
        risk_level = "medium"

    return {
        "ticker": ticker,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "max_allocation_ratio": round(max_allocation_ratio, 3),
        "reasons": "; ".join(reasons) if reasons else "Risque standard",
        "stop_loss_suggested": max(-0.18, min(-0.05, -(risk_score / 100) * 0.25)),
    }


def is_sector_overexposed(ticker: str, sector: str, positions: list) -> bool:
    """Vérifie si le secteur est sur-exposé."""
    if not positions:
        return False
    sector_count = sum(1 for p in positions if p.get("sector") == sector)
    return (sector_count + 1) / (len(positions) + 1) > MAX_SECTOR_EXPOSURE


# ═══════════════════════════════════════════════════════════
# 3. RAPPORT DE RISQUE
# ═══════════════════════════════════════════════════════════

def risk_summary(positions: list, current_prices: dict) -> str:
    """Génère un résumé lisible des risques."""
    safety = check_safety()
    portfolio_risk = assess_portfolio_risk(positions, current_prices)

    parts = []
    parts.append(f"**🛡️ Risk Manager**")

    # Safety mode
    if safety["restricted"]:
        parts.append(f"   🔒 {safety['message']}")
    else:
        parts.append(f"   ✅ {safety['message']}")

    # Portfolio risk
    parts.append(f"   Niveau de risque: {portfolio_risk['risk_level'].upper()}")
    if portfolio_risk["warnings"]:
        for w in portfolio_risk["warnings"][:3]:
            parts.append(f"   {w}")

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if "--status" in sys.argv:
        safety = check_safety()
        print(json.dumps(safety, indent=2))
    elif "--reset" in sys.argv:
        save_safety_state({
            "mode": "normal",
            "consecutive_errors": 0,
            "last_error_date": None,
            "frozen_since": None,
            "auto_unfreeze_at": None,
            "total_frozen_trades": 0,
            "history": [],
        })
        print("✅ Safety mode réinitialisé")
    elif "--fail" in sys.argv:
        for _ in range(3):
            record_outcome(success=False, ticker="TEST")
        print(f"🔒 Safety mode activé : {check_safety()['message']}")
    elif "--success" in sys.argv:
        record_outcome(success=True, ticker="TEST")
        print("✅ Succès enregistré")
    else:
        print(risk_summary([], {}))