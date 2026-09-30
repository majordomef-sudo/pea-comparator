#!/usr/bin/env python3
"""
paper_trading.py — Portefeuille papier automatique pour alfred_trader
Exécute virtuellement les recommandations d'achat et suit la performance.

Principe :
- Cash virtuel initial : 10 000€
- Quand une recommandation "ACHETER" (score ≥ 70) sort, on "achète" virtuellement
- Chaque action : prix d'entrée, quantité, date
- Quand une recommandation "VENDRE" ou qu'un SL/TP est atteint → on "vend"
- On tracke : PnL total, win rate, positions ouvertes, historique des trades

Framework : Taleb (apprendre des erreurs sans risquer)
"""
import json
from pathlib import Path
from datetime import datetime, timedelta

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
STATE_DIR = WORKSPACE / "state" / "stock_watch"
PAPER_FILE = STATE_DIR / "paper_trading.json"
HISTORY_FILE = STATE_DIR / "paper_trades_history.json"

# Configuration
INITIAL_CASH = 10000.0         # Cash de départ
MAX_POSITIONS = 5               # Max positions ouvertes en même temps
ALLOCATION_PER_TRADE = 0.20     # 20% du cash par trade (2000€ sur 10k)
MIN_SCORE_TO_BUY = 70            # Score minimum pour acheter
FORCE_SELL_AFTER_DAYS = 60      # Vendre automatiquement après X jours


def _ensure_files():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# 1. CHARGEMENT / SAUVEGARDE
# ═══════════════════════════════════════════════════════════

def load_paper() -> dict:
    """Charge l'état du portefeuille papier."""
    _ensure_files()
    if PAPER_FILE.exists():
        try:
            return json.loads(PAPER_FILE.read_text())
        except Exception:
            pass
    return _default_state()


def _default_state() -> dict:
    return {
        "cash": INITIAL_CASH,
        "total_invested": 0.0,
        "total_withdrawn": 0.0,
        "positions": [],
        "created_at": datetime.now().isoformat(),
        "last_updated": datetime.now().isoformat(),
    }


def save_paper(state: dict):
    """Sauvegarde l'état."""
    _ensure_files()
    state["last_updated"] = datetime.now().isoformat()
    PAPER_FILE.write_text(json.dumps(state, indent=2))


def load_history() -> list:
    """Charge l'historique des trades fermés."""
    if HISTORY_FILE.exists():
        try:
            return json.loads(HISTORY_FILE.read_text())
        except Exception:
            pass
    return []


def save_history(history: list):
    _ensure_files()
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


# ═══════════════════════════════════════════════════════════
# 2. EXÉCUTION VIRTUELLE
# ═══════════════════════════════════════════════════════════

def execute_buy(ticker: str, name: str, price: float, score: int, reasons: list = None, catalyst: float = 0) -> dict:
    """Exécute un achat virtuel.

    Retourne le trade exécuté ou None si pas possible (pas de cash, trop de positions).
    """
    state = load_paper()
    now = datetime.now().isoformat()

    # Vérifier qu'on n'a pas déjà ce ticker
    existing = [p for p in state["positions"] if p["ticker"] == ticker]
    if existing:
        return {"executed": False, "reason": "already_held", "position": existing[0]}

    # Vérifier le nombre max de positions
    if len(state["positions"]) >= MAX_POSITIONS:
        return {"executed": False, "reason": "max_positions"}

    # Calculer la quantité
    allocation = state["cash"] * ALLOCATION_PER_TRADE
    if allocation <= 0:
        return {"executed": False, "reason": "no_cash"}

    quantity = round(allocation / price, 4)
    if quantity <= 0:
        return {"executed": False, "reason": "price_too_high"}

    cost = round(quantity * price, 2)

    # Déduire le cash
    state["cash"] = round(state["cash"] - cost, 2)
    state["total_invested"] = round(state["total_invested"] + cost, 2)

    tp1 = round(price * 1.08, 2)
    tp2 = round(price * 1.25, 2)
    sl = round(price * 0.92, 2)

    position = {
        "ticker": ticker,
        "name": name,
        "entry_price": round(price, 2),
        "quantity": quantity,
        "cost": cost,
        "entry_date": now[:10],
        "entry_score": score,
        "reasons": reasons or [],
        "catalyst": round(catalyst, 1),
        "target_tp1": tp1,
        "target_tp2": tp2,
        "stop_loss": sl,
        "status": "open",
    }

    state["positions"].append(position)
    save_paper(state)

    return {
        "executed": True,
        "reason": "bought",
        "position": position,
        "cash_remaining": state["cash"],
    }


def execute_sell(ticker: str, current_price: float, sell_reason: str = "manual") -> dict:
    """Ferme une position virtuelle.

    sell_reason: "take_profit", "stop_loss", "auto_sell", "manual"
    """
    state = load_paper()
    history = load_history()

    position = None
    for i, p in enumerate(state["positions"]):
        if p["ticker"] == ticker and p["status"] == "open":
            position = state["positions"].pop(i)
            break

    if not position:
        return {"executed": False, "reason": "not_found"}

    entry_price = position["entry_price"]
    quantity = position["quantity"]
    sale_value = round(quantity * current_price, 2)
    cost = position["cost"]
    pnl = round(sale_value - cost, 2)
    pnl_pct = round((current_price / entry_price - 1) * 100, 1)

    # Remettre le cash
    state["cash"] = round(state["cash"] + sale_value, 2)

    # Tracker le trade fermé
    closed_trade = {
        **position,
        "exit_price": round(current_price, 2),
        "exit_date": datetime.now().strftime("%Y-%m-%d"),
        "sell_reason": sell_reason,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "days_held": (datetime.now() - datetime.strptime(position["entry_date"], "%Y-%m-%d")).days,
    }
    history.append(closed_trade)
    if len(history) > 200:
        history = history[-200:]

    save_paper(state)
    save_history(history)

    return {
        "executed": True,
        "reason": sell_reason,
        "trade": closed_trade,
        "cash_remaining": state["cash"],
    }


# ═══════════════════════════════════════════════════════════
# 3. VÉRIFICATION AUTO DES POSITIONS
# ═══════════════════════════════════════════════════════════

def check_positions(current_prices: dict) -> list:
    """Vérifie les positions ouvertes contre les prix actuels.

    Ferme automatiquement si TP, SL ou durée max atteints.
    Retourne la liste des trades fermés aujourd'hui.
    """
    state = load_paper()
    history = load_history()
    closed_today = []

    still_open = []
    for pos in state["positions"]:
        ticker = pos["ticker"]
        current_price = current_prices.get(ticker)
        entry_price = pos["entry_price"]
        quantity = pos["quantity"]

        if current_price is None or current_price <= 0:
            still_open.append(pos)
            continue

        tp1 = pos.get("target_tp1")
        tp2 = pos.get("target_tp2")
        sl = pos.get("stop_loss")

        sell_reason = None

        # TP1 / TP2
        if tp2 and current_price >= tp2:
            sell_reason = "take_profit_2"
        elif tp1 and current_price >= tp1:
            sell_reason = "take_profit_1"

        # Stop loss
        if sl and current_price <= sl and not sell_reason:
            sell_reason = "stop_loss"

        # Durée max sans mouvement suffisant
        if not sell_reason:
            try:
                entry_date = datetime.strptime(pos["entry_date"], "%Y-%m-%d")
                days_held = (datetime.now() - entry_date).days
                pnl_pct = (current_price / entry_price - 1) * 100
                if days_held >= FORCE_SELL_AFTER_DAYS or (days_held >= 45 and abs(pnl_pct) < 2):
                    sell_reason = "expired"
                # Auto-stop loss large si -18%
                if pnl_pct <= -18 and days_held >= 7:
                    sell_reason = "stop_loss"
            except Exception:
                pass

        if sell_reason:
            # Fermer la position
            sale_value = round(quantity * current_price, 2)
            cost = pos["cost"]
            pnl = round(sale_value - cost, 2)
            pnl_pct = round((current_price / entry_price - 1) * 100, 1)

            closed_trade = {
                **pos,
                "exit_price": round(current_price, 2),
                "exit_date": datetime.now().strftime("%Y-%m-%d"),
                "sell_reason": sell_reason,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "days_held": (datetime.now() - datetime.strptime(pos["entry_date"], "%Y-%m-%d")).days,
            }
            history.append(closed_trade)
            state["cash"] = round(state["cash"] + sale_value, 2)
            closed_today.append(closed_trade)

            if len(history) > 200:
                history = history[-200:]
        else:
            still_open.append(pos)

    state["positions"] = still_open
    save_paper(state)
    save_history(history)

    return closed_today


# ═══════════════════════════════════════════════════════════
# 4. STATS DE PERFORMANCE
# ═══════════════════════════════════════════════════════════

def compute_stats(current_prices: dict = None) -> dict:
    """Calcule les statistiques complètes du portefeuille papier."""
    state = load_paper()
    history = load_history()
    now = datetime.now()

    # Positions ouvertes
    open_positions = []
    open_value = 0.0
    for pos in state["positions"]:
        ticker = pos["ticker"]
        current_price = current_prices.get(ticker) if current_prices else None
        if current_price:
            current_value = round(pos["quantity"] * current_price, 2)
            pnl_pct = round((current_price / pos["entry_price"] - 1) * 100, 1)
        else:
            current_value = pos["cost"]
            pnl_pct = 0
        open_value += current_value
        open_positions.append({
            "ticker": ticker,
            "name": pos["name"],
            "entry_price": pos["entry_price"],
            "current_value": current_value,
            "pnl_pct": pnl_pct,
            "days_held": (now - datetime.strptime(pos["entry_date"], "%Y-%m-%d")).days,
        })

    # Trades fermés
    total_trades = len(history)
    winning_trades = [t for t in history if t.get("pnl", 0) > 0]
    losing_trades = [t for t in history if t.get("pnl", 0) <= 0]
    win_rate = round(len(winning_trades) / total_trades * 100, 1) if total_trades > 0 else 0

    total_pnl = sum(t.get("pnl", 0) for t in history)
    avg_pnl_per_trade = round(total_pnl / total_trades, 2) if total_trades > 0 else 0
    best_trade = max(history, key=lambda t: t.get("pnl_pct", 0)) if history else None
    worst_trade = min(history, key=lambda t: t.get("pnl_pct", 0)) if history else None

    cash = state["cash"]
    total_portfolio_value = round(cash + open_value, 2)
    total_gain = round(total_portfolio_value - INITIAL_CASH, 2)
    total_gain_pct = round((total_portfolio_value / INITIAL_CASH - 1) * 100, 2) if INITIAL_CASH else 0

    return {
        "initial_capital": INITIAL_CASH,
        "cash": round(cash, 2),
        "open_value": round(open_value, 2),
        "total_value": total_portfolio_value,
        "total_gain": total_gain,
        "total_gain_pct": total_gain_pct,
        "open_positions": open_positions,
        "open_count": len(open_positions),
        "total_trades": total_trades,
        "winning_trades": len(winning_trades),
        "losing_trades": len(losing_trades),
        "win_rate": win_rate,
        "avg_pnl_per_trade": avg_pnl_per_trade,
        "best_trade": best_trade,
        "worst_trade": worst_trade,
    }


# ═══════════════════════════════════════════════════════════
# 5. INTÉGRATION AVEC LE SCAN
# ═══════════════════════════════════════════════════════════

def auto_trade_from_scan(conviction: dict, prices: dict) -> dict:
    """Appelé après chaque scan pour exécuter les trades virtuels.

    Achat automatique pour chaque ticker avec score ≥ 70.
    Vérifie les positions ouvertes contre les prix courants.
    """
    results = {"buys": [], "sells": [], "errors": []}

    # 1. Check positions existantes (convert prices dict to flat prices)
    flat_prices = {t: d.get("price") for t, d in prices.items() if isinstance(d, dict) and "error" not in d and d.get("price")}
    closed = check_positions(flat_prices)
    for trade in closed:
        results["sells"].append(trade)

    # 2. Check nouvelles opportunités d'achat
    state = load_paper()
    # Ne pas acheter si déjà max positions
    if len(state["positions"]) >= MAX_POSITIONS:
        return results

    existing_tickers = {p["ticker"] for p in state["positions"]}

    # Trier par score décroissant
    sorted_candidates = sorted(
        [(t, cv) for t, cv in conviction.items() if isinstance(cv, dict)],
        key=lambda x: -x[1].get("score", 0),
    )

    for ticker, cv in sorted_candidates:
        if len(state["positions"]) >= MAX_POSITIONS:
            break

        score = cv.get("score", 0)
        if score < MIN_SCORE_TO_BUY:
            continue

        if ticker in existing_tickers:
            continue

        price_data = prices.get(ticker, {})
        price = price_data.get("price") if isinstance(price_data, dict) else price_data
        if not price or (isinstance(price_data, dict) and "error" in price_data):
            continue

        # Acheter
        buy_result = execute_buy(
            ticker=ticker,
            name=cv.get("name", ticker),
            price=price,
            score=score,
            reasons=cv.get("reasons", []),
            catalyst=cv.get("catalyst", 0),
        )
        results["buys"].append(buy_result)
        state = load_paper()  # Recharge pour le prochain achat

    return results


def paper_status_summary(current_prices: dict = None) -> str:
    """Génère un résumé lisible du portefeuille papier."""
    stats = compute_stats(current_prices)
    parts = []

    gain_emoji = "🟢" if stats["total_gain_pct"] >= 0 else "🔴"
    parts.append(f"📋 **Paper Trading Alfred**")
    parts.append(f"   Capital: {stats['initial_capital']:.0f}€ | Valeur: {stats['total_value']:.0f}€")
    parts.append(f"   {gain_emoji} PnL: {stats['total_gain']:+.0f}€ ({stats['total_gain_pct']:+.1f}%)")
    parts.append(f"   Cash: {stats['cash']:.0f}€ | Positions: {stats['open_count']}")
    parts.append(f"   Trades fermés: {stats['total_trades']} (Win rate: {stats['win_rate']}%)")
    parts.append(f"   Meilleur: {stats['best_trade']['pnl_pct']:+.1f}%" if stats.get('best_trade') else "")
    parts.append(f"   Pire: {stats['worst_trade']['pnl_pct']:+.1f}%" if stats.get('worst_trade') else "")

    if stats["open_positions"]:
        parts.append(f"\n   **Positions ouvertes :**")
        for pos in stats["open_positions"]:
            emoji = "🟢" if pos["pnl_pct"] >= 0 else "🔴"
            parts.append(f"   {emoji} {pos['ticker']} ({pos['name']}) — {pos['pnl_pct']:+.1f}% (J+{pos['days_held']})")

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "--reset":
        if total_trades := len(load_history()):
            print(f"⚠️ {total_trades} trades dans l'historique seront perdus.")
        save_paper(_default_state())
        print("✅ Portefeuille papier réinitialisé.")
    elif cmd == "--stats":
        stats = compute_stats()
        print(json.dumps(stats, indent=2))
    elif cmd == "--status":
        print(paper_status_summary())
    else:
        stats = compute_stats()
        print(f"💰 Paper Trading : {stats['total_value']:.0f}€ ({stats['total_gain_pct']:+.1f}%)")
        print(f"Positions: {stats['open_count']} | Trades: {stats['total_trades']} | Win rate: {stats['win_rate']}%")