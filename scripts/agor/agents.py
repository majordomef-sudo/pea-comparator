#!/usr/bin/env python3
"""
agents.py — Alfred Trading Agent System (AGOR)
Multi-agent architecture inspirée de ai-hedge-fund (virattt) et TradingAgents (TauricResearch)

Chaque agent a une personnalité d'investissement différente et produit un signal.
Le Portfolio Manager agrège les signaux avec des poids basés sur le track record.

Agents :
- TechnicalAgent : RSI, MACD, volume, tendances (exists déjà dans alfred_trader.py)
- BullAgent : optimiste, voit les catalyseurs et l'upside
- BearAgent : sceptique, chasse les red flags et le downside
- ValueAgent : valorisation, P/E, FCF, multiples
- SentimentAgent : news, secteur, événements macro
- MomentumAgent : tendances court/moyen terme
"""
import json
import math
from pathlib import Path
from datetime import datetime

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
STATE_DIR = WORKSPACE / "state" / "stock_watch"
AGENTS_TRACK_FILE = STATE_DIR / "agor_track_record.json"
AGENTS_SIGNALS_FILE = STATE_DIR / "agor_signals.json"


def _ensure():
    STATE_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════
# CHARGEMENT DU TRACK RECORD DES AGENTS
# ═══════════════════════════════════════════════════════════

def load_track_record() -> dict:
    _ensure()
    if AGENTS_TRACK_FILE.exists():
        try:
            return json.loads(AGENTS_TRACK_FILE.read_text())
        except Exception:
            pass
    return {
        "technical_agent": {"calls": 0, "correct": 0, "avg_pnl": 0.0, "weight": 1.0},
        "bull_agent": {"calls": 0, "correct": 0, "avg_pnl": 0.0, "weight": 1.0},
        "bear_agent": {"calls": 0, "correct": 0, "avg_pnl": 0.0, "weight": 1.0},
        "value_agent": {"calls": 0, "correct": 0, "avg_pnl": 0.0, "weight": 1.0},
        "sentiment_agent": {"calls": 0, "correct": 0, "avg_pnl": 0.0, "weight": 1.0},
        "momentum_agent": {"calls": 0, "correct": 0, "avg_pnl": 0.0, "weight": 1.0},
        "created": datetime.now().isoformat(),
        "updated": datetime.now().isoformat(),
    }


def save_track_record(record: dict):
    _ensure()
    record["updated"] = datetime.now().isoformat()
    AGENTS_TRACK_FILE.write_text(json.dumps(record, indent=2))


# ═══════════════════════════════════════════════════════════
# 1. TECHNICAL AGENT — RSI, MACD, Volume, Tendances
# ═══════════════════════════════════════════════════════════

def technical_agent(ticker: str, name: str, price_data: dict, stock: dict) -> dict:
    """Analyse technique pure : RSI, MACD, SMA, volume.

    Inspiré de ai-hedge-fund src/agents/technicals.py
    mais adapté à notre data déjà calculée (yfinance).
    """
    rsi = price_data.get("rsi_14", 50)
    ma20 = price_data.get("ma_20")
    ma50 = price_data.get("ma_50")
    price = price_data.get("price")

    change = price_data.get("change_pct", 0)
    change_7d = price_data.get("change_7d_pct", 0)
    volume_ratio = price_data.get("volume_ratio", 1)
    macd_bullish = price_data.get("macd", {}).get("bullish", False)
    bb_upper = price_data.get("bb_upper")
    bb_lower = price_data.get("bb_lower")

    score = 0
    signals = []

    # RSI
    if rsi < 30:
        score += 4
        signals.append(f"RSI {rsi:.0f} — oversold profond")
    elif rsi < 35:
        score += 2
        signals.append(f"RSI {rsi:.0f} — proche oversold")
    elif rsi > 70:
        score -= 3
        signals.append(f"RSI {rsi:.0f} — surachat")
    elif rsi > 60:
        score -= 1
        signals.append(f"RSI {rsi:.0f} — tendance surachat")

    # MACD
    if macd_bullish:
        score += 3
        signals.append("MACD haussier")

    # MA bounce
    if price and ma20 and price < ma20 and change_7d and change_7d < -5:
        score += 2  # Possible rebond
        signals.append("Sous MA20 + baisse — possible rebond")

    if price and ma20 and price > ma20 and change_7d and change_7d > 5:
        score -= 2  # Possible résistance
        signals.append("Au-dessus MA20 + hausse — résistance proche")

    if ma50 and price and price < ma50 * 0.9:
        score += 2
        signals.append("Sous MA50 (-10%) — value zone")

    # Volume spike
    if volume_ratio > 2:
        if change > 0:
            score += 1
            signals.append("Volume élevé + hausse")
        else:
            score -= 1
            signals.append("Volume élevé + baisse")

    # Bollinger bands
    if bb_lower and price and price <= bb_lower * 1.02:
        score += 2
        signals.append("Bollinger bas — zone de rebond")

    if bb_upper and price and price >= bb_upper * 0.98:
        score -= 2
        signals.append("Bollinger haut — zone de résistance")

    # Clamp score -10..+10
    score = max(-10, min(10, score))

    # Convert to signal
    if score >= 4:
        signal = "bullish"
        confidence = min(100, 50 + score * 5)
    elif score <= -4:
        signal = "bearish"
        confidence = min(100, 50 + abs(score) * 5)
    elif score >= 1:
        signal = "bullish"
        confidence = 55
    elif score <= -1:
        signal = "bearish"
        confidence = 55
    else:
        signal = "neutral"
        confidence = 50

    return {
        "agent": "technical_agent",
        "ticker": ticker,
        "name": name,
        "signal": signal,
        "score": score,
        "confidence": confidence,
        "reasoning": "; ".join(signals) if signals else "Aucun signal technique fort",
        "data_points": {
            "rsi": round(rsi, 1),
            "macd_bullish": macd_bullish,
            "volume_ratio": round(volume_ratio, 2),
        },
    }


# ═══════════════════════════════════════════════════════════
# 2. BULL AGENT — Catalyseurs, momentum, upside potentiel
# ═══════════════════════════════════════════════════════════

def bull_agent(ticker: str, name: str, price_data: dict, stock: dict) -> dict:
    """Agent optimiste : cherche les catalyseurs haussiers.

    Patterns :
    - Dip dans une action Core / Defensive → opportunité d'achat
    - RSI bas sur valeur de qualité → rebond probable
    - Forte baisse technique + catalyseur secteur → retournement
    - Volume croissant pendant la baisse → accumulation
    """
    rsi = price_data.get("rsi_14", 50)
    change = price_data.get("change_pct", 0)
    change_7d = price_data.get("change_7d_pct", 0)
    volume_ratio = price_data.get("volume_ratio", 1)
    is_core = stock.get("risk_profile") in ("Defensive", "Defensive Growth")
    sector_label = stock.get("sector", "")

    catalyst_modifier = price_data.get("catalyst", 0) if isinstance(price_data.get("catalyst"), (int, float)) else 0
    cat_reason = price_data.get("news_reason", "")

    score = 5  # Bull démarre optimiste
    signals = []

    # Dip d'une action core
    if is_core and change_7d and change_7d < -5:
        score += 3
        signals.append(f"Core stock en baisse de {change_7d:.0f}% — opportunité d'achat")

    # RSI bas + core
    if is_core and rsi < 35:
        score += 2
        signals.append(f"Core stock RSI {rsi:.0f} — probablement sur-vendu")

    # Catalyseur événementiel
    if catalyst_modifier > 0:
        score += min(5, int(catalyst_modifier * 2))
        signals.append(f"Catalyseur haussier : {cat_reason.split(':')[-1].strip() if ':' in cat_reason else cat_reason[:60]}")

    # Volume durant la baisse
    if volume_ratio > 1.5 and change_7d and change_7d < -3:
        score += 1
        signals.append("Volume élevé pendant la baisse — possible accumulation")

    # Baisse + secteur porteur
    if change_7d and change_7d < -3 and "technologie" in sector_label.lower():
        score += 1
        signals.append("Baisse technique dans secteur porteur")

    # Clamp -10..+10
    score = max(-10, min(10, score))

    if score >= 3:
        signal = "bullish"
        confidence = min(90, 55 + score * 3)
    elif score <= 0:
        signal = "neutral"
        confidence = 40
    else:
        signal = "bullish"
        confidence = 50

    return {
        "agent": "bull_agent",
        "ticker": ticker,
        "name": name,
        "signal": signal,
        "score": score,
        "confidence": confidence,
        "reasoning": "; ".join(signals) if signals else "Pas de catalyseur haussier clair",
    }


# ═══════════════════════════════════════════════════════════
# 3. BEAR AGENT — Red flags, downside, risques
# ═══════════════════════════════════════════════════════════

def bear_agent(ticker: str, name: str, price_data: dict, stock: dict) -> dict:
    """Agent pessimiste : cherche les risques baissiers.

    Patterns :
    - RSI surachat sur action non-core → vente
    - Forte hausse + volume décroissant → épuisement
    - Catalyseur baissier (news négatives)
    - Baisse 7j prolongée avec RSI moyen → downtrend confirmé
    - Action volatile sans raison fondamentale
    """
    rsi = price_data.get("rsi_14", 50)
    change = price_data.get("change_pct", 0)
    change_7d = price_data.get("change_7d_pct", 0)
    is_core = stock.get("risk_profile") in ("Defensive", "Defensive Growth")
    ma20 = price_data.get("ma_20")
    ma50 = price_data.get("ma_50")
    price = price_data.get("price")
    catalyst_modifier = price_data.get("catalyst", 0) if isinstance(price_data.get("catalyst"), (int, float)) else 0

    score = -3  # Bear démarre pessimiste
    signals = []

    # RSI surachat sur non-core
    if not is_core and rsi > 65:
        score -= 3
        signals.append(f"RSI {rsi:.0f} — surachat sur non-core")
    elif rsi > 75:
        score -= 2
        signals.append(f"RSI {rsi:.0f} — surachat extrême")

    # Downtrend confirmé (RSI moyen + baisse prolongée)
    if rsi < 40 and change_7d and change_7d < -5:
        score -= 3
        signals.append(f"Downtrend confirmé : RSI {rsi:.0f} + baisse {change_7d:.0f}%")

    # Sous les MA
    if price and ma20 and ma50 and price < ma20 and price < ma50:
        score -= 2
        signals.append("Sous MA20 et MA50 — tendance baissière")

    # Catalyseur baissier
    if catalyst_modifier < 0:
        score -= min(3, int(abs(catalyst_modifier)))
        signals.append("Catalyseur baissier détecté")

    # Baisse forte sur 7j
    if change_7d and change_7d < -8:
        score -= 2
        signals.append(f"Baisse violente : {change_7d:.0f}% en 7j")

    # Hausse forte sans raison
    if change_7d and change_7d > 10 and rsi > 60:
        score -= 2
        signals.append(f"Hausse rapide de {change_7d:.0f}% — possible épuisement")

    # Clamp -10..+10
    score = max(-10, min(10, score))

    if score <= -4:
        signal = "bearish"
        confidence = min(90, 50 + abs(score) * 4)
    elif score <= -1:
        signal = "bearish"
        confidence = 55
    else:
        signal = "neutral"
        confidence = 50

    return {
        "agent": "bear_agent",
        "ticker": ticker,
        "name": name,
        "signal": signal,
        "score": score,
        "confidence": confidence,
        "reasoning": "; ".join(signals) if signals else "Pas de risque baissier immédiat",
    }


# ═══════════════════════════════════════════════════════════
# 4. VALUE AGENT — Valorisation, P/E, rendement, qualité
# ═══════════════════════════════════════════════════════════

def value_agent(ticker: str, name: str, price_data: dict, stock: dict) -> dict:
    """Agent value : cherche les décotes et la qualité financière.

    Utilise les infos yfinance disponibles : P/E, market cap, secteur,
    comportement du prix pour estimer la valorisation relative.
    """
    pe = price_data.get("trailing_pe")
    change_7d = price_data.get("change_7d_pct", 0)
    is_core = stock.get("risk_profile") in ("Defensive", "Defensive Growth")
    sector_label = stock.get("sector", "")

    score = 0
    signals = []

    # P/E ratio (value check)
    if pe is not None:
        if 0 < pe < 12:
            score += 3
            signals.append(f"P/E bas ({pe:.1f}) — possible sous-valorisation")
        elif 12 <= pe < 18:
            score += 1
            signals.append(f"P/E raisonnable ({pe:.1f})")
        elif pe > 30:
            score -= 2
            signals.append(f"P/E élevé ({pe:.1f}) — premium de valorisation")
        elif pe < 0:
            score -= 1
            signals.append(f"P/E négatif ({pe:.1f}) — pertes")
    else:
        score -= 1  # Pas de data PE disponible

    # Core stock en baisse = value opportunity
    if is_core and change_7d and change_7d < -5:
        score += 2
        signals.append(f"Core stock en baisse de {change_7d:.0f}% — zone value")

    # Baisse sévère mais core
    if is_core and change_7d and change_7d < -10:
        score += 2
        signals.append("Baisse sévère sur core — potentiel de rebond")

    # Clamp -10..+10
    score = max(-10, min(10, score))

    if score >= 4:
        signal = "bullish"
        confidence = min(85, 50 + score * 3)
    elif score >= 1:
        signal = "bullish"
        confidence = 55
    elif score <= -2:
        signal = "bearish"
        confidence = 55
    else:
        signal = "neutral"
        confidence = 50

    return {
        "agent": "value_agent",
        "ticker": ticker,
        "name": name,
        "signal": signal,
        "score": score,
        "confidence": confidence,
        "reasoning": "; ".join(signals) if signals else "Valorisation neutre",
    }


# ═══════════════════════════════════════════════════════════
# 5. SENTIMENT AGENT — News, secteur, événements
# ═══════════════════════════════════════════════════════════

def sentiment_agent(ticker: str, name: str, price_data: dict, stock: dict) -> dict:
    """Agent sentiment : news, catalyseurs secteur, humeur de marché.

    Utilise les données de news_context (catalyst_mods) et les tendances
    sectorielles pour évaluer le sentiment.
    """
    catalyst = price_data.get("catalyst", 0) if isinstance(price_data.get("catalyst"), (int, float)) else 0
    cat_reason = price_data.get("news_reason", "")
    sector_label = stock.get("sector", "")

    score = 0
    signals = []

    # Catalyseur news
    if catalyst >= 3:
        score += 3
        signals.append("Sentiment secteur fortement positif")
    elif catalyst >= 1:
        score += 1
        signals.append("Sentiment secteur positif")
    elif catalyst <= -3:
        score -= 3
        signals.append("Sentiment secteur négatif")
    elif catalyst <= -1:
        score -= 1
        signals.append("Sentiment secteur mitigé/négatif")

    if cat_reason:
        short_reason = cat_reason.split(':')[-1].strip() if ':' in cat_reason else cat_reason[:80]
        signals.append(short_reason)

    # Clamp -10..+10
    score = max(-5, min(5, score))

    if score >= 2:
        signal = "bullish"
        confidence = min(80, 50 + score * 6)
    elif score <= -2:
        signal = "bearish"
        confidence = min(80, 50 + abs(score) * 6)
    else:
        signal = "neutral"
        confidence = 50

    return {
        "agent": "sentiment_agent",
        "ticker": ticker,
        "name": name,
        "signal": signal,
        "score": score,
        "confidence": confidence,
        "reasoning": "; ".join(signals) if signals else "Pas de signal sentiment fort",
    }


# ═══════════════════════════════════════════════════════════
# 6. MOMENTUM AGENT — Tendance court/moyen terme
# ═══════════════════════════════════════════════════════════

def momentum_agent(ticker: str, name: str, price_data: dict, stock: dict) -> dict:
    """Agent momentum : force de la tendance.

    Analyse le mouvement relatif vs le marché et la force
    de la tendance actuelle.
    """
    change = price_data.get("change_pct", 0)
    change_7d = price_data.get("change_7d_pct", 0)
    ma20 = price_data.get("ma_20")
    ma50 = price_data.get("ma_50")
    price = price_data.get("price")
    volume_ratio = price_data.get("volume_ratio", 1)

    score = 0
    signals = []

    # Tendance 7j
    if change_7d and change_7d > 8:
        score += 3
        signals.append(f"Momentum fort : +{change_7d:.0f}% en 7j")
    elif change_7d and change_7d > 3:
        score += 1
        signals.append(f"Momentum modéré : +{change_7d:.0f}% en 7j")
    elif change_7d and change_7d < -8:
        score -= 3
        signals.append(f"Momentum négatif : {change_7d:.0f}% en 7j")
    elif change_7d and change_7d < -3:
        score -= 1
        signals.append(f"Momentum faible : {change_7d:.0f}% en 7j")

    # Prix au-dessus des MA
    if price and ma20 and price > ma20:
        score += 1
        signals.append("Au-dessus MA20")
    if price and ma50 and price > ma50:
        score += 1
        signals.append("Au-dessus MA50")

    # Prix sous les MA = momentum négatif
    if price and ma20 and price < ma20:
        score -= 1
    if price and ma50 and price < ma50:
        score -= 1

    # Volume + prix = confirmation
    if volume_ratio > 1.5 and change > 0:
        score += 1
        signals.append("Volume + hausse = confirmation")
    if volume_ratio > 1.5 and change < 0:
        score -= 1
        signals.append("Volume + baisse = distribution")

    score = max(-10, min(10, score))

    if score >= 4:
        signal = "bullish"
        confidence = min(85, 50 + score * 3)
    elif score <= -4:
        signal = "bearish"
        confidence = min(85, 50 + abs(score) * 3)
    elif score >= 1:
        signal = "bullish"
        confidence = 55
    elif score <= -1:
        signal = "bearish"
        confidence = 55
    else:
        signal = "neutral"
        confidence = 50

    return {
        "agent": "momentum_agent",
        "ticker": ticker,
        "name": name,
        "signal": signal,
        "score": score,
        "confidence": confidence,
        "reasoning": "; ".join(signals) if signals else "Momentum neutre",
    }


# ═══════════════════════════════════════════════════════════
# ORCHESTRATEUR — Lance tous les agents pour un ticker
# ═══════════════════════════════════════════════════════════

ALL_AGENTS = [
    technical_agent,
    bull_agent,
    bear_agent,
    value_agent,
    sentiment_agent,
    momentum_agent,
]

AGENT_NAMES = {
    "technical_agent": "Technical",
    "bull_agent": "Bull",
    "bear_agent": "Bear",
    "value_agent": "Value",
    "sentiment_agent": "Sentiment",
    "momentum_agent": "Momentum",
}


def run_agents(ticker: str, name: str, price_data: dict, stock: dict) -> list:
    """Exécute tous les agents pour un ticker et retourne leurs signaux."""
    signals = []
    for agent_fn in ALL_AGENTS:
        try:
            sig = agent_fn(ticker, name, price_data, stock)
            signals.append(sig)
        except Exception as e:
            signals.append({
                "agent": agent_fn.__name__,
                "ticker": ticker,
                "name": name,
                "signal": "neutral",
                "score": 0,
                "confidence": 0,
                "reasoning": f"Erreur : {e}",
            })
    return signals


def get_weighted_score(signals: list, track_record: dict = None) -> dict:
    """Agrège les signaux des agents avec leurs poids de track record.

    Retourne un score final de conviction.
    """
    if track_record is None:
        track_record = load_track_record()

    total_weighted_score = 0.0
    total_weight = 0.0
    contributions = []

    # Bear agent a un poids inversé (ses bears sont des signaux d'achat)
    for sig in signals:
        agent_name = sig["agent"]
        agent_score = sig["score"]
        confidence = sig["confidence"] / 100.0

        # Poids de base depuis le track record
        base_weight = track_record.get(agent_name, {}).get("weight", 1.0)

        # Le poids effectif tient compte de la confiance
        effective_weight = base_weight * confidence

        # Bear agent : score inversé (il marque -10 quand c'est baissier,
        # donc -10 devient un signal de ne PAS acheter)
        if agent_name == "bear_agent":
            bear_multiplier = 0.7
            effective_score = agent_score * bear_multiplier
        else:
            effective_score = agent_score

        weighted = effective_score * effective_weight
        total_weighted_score += weighted
        total_weight += effective_weight

        contributions.append({
            "agent": AGENT_NAMES.get(agent_name, agent_name),
            "agent_key": agent_name,
            "score": agent_score,
            "weight": round(base_weight, 2),
            "confidence": round(confidence * 100),
            "effective": round(weighted, 1),
        })

    # Score final = moyenne pondérée, normalisée à 0-100
    if total_weight > 0:
        avg_score = total_weighted_score / total_weight
    else:
        avg_score = 0

    # Un score d'agent va de -10 à +10 → on convertit en 0-100
    # -10 → 0, 0 → 50, +10 → 100
    final_score = 50 + (avg_score / 10) * 50
    final_score = max(0, min(100, round(final_score, 1)))

    # Verdict
    if final_score >= 70:
        verdict = "🟢 Achat conseillé"
        decision = "buy"
    elif final_score >= 55:
        verdict = "🟡 Surveiller"
        decision = "hold"
    elif final_score <= 30:
        verdict = "🔴 Vente conseillée"
        decision = "sell"
    else:
        verdict = "⚪ Neutre"
        decision = "hold"

    # Consensus des agents
    bullish_count = sum(1 for s in signals if s["signal"] == "bullish")
    bearish_count = sum(1 for s in signals if s["signal"] == "bearish")
    neutral_count = sum(1 for s in signals if s["signal"] == "neutral")

    return {
        "final_score": final_score,
        "verdict": verdict,
        "decision": decision,
        "bullish_count": bullish_count,
        "bearish_count": bearish_count,
        "neutral_count": neutral_count,
        "total_agents": len(signals),
        "avg_score": round(avg_score, 1),
        "contributions": contributions,
    }


# ═══════════════════════════════════════════════════════════
# MISE À JOUR DU TRACK RECORD
# ═══════════════════════════════════════════════════════════

def update_agent_track_record(outcomes: dict):
    """Met à jour le track record de chaque agent.

    outcomes: {agent_name: {"correct": bool, "pnl": float}}
    """
    record = load_track_record()

    for agent_name, outcome in outcomes.items():
        if agent_name not in record:
            record[agent_name] = {"calls": 0, "correct": 0, "avg_pnl": 0.0, "weight": 1.0}

        agent_rec = record[agent_name]
        agent_rec["calls"] += 1
        if outcome.get("correct"):
            agent_rec["correct"] += 1

        # Mettre à jour le PnL moyen
        pnl = outcome.get("pnl", 0)
        old_pnl = agent_rec["avg_pnl"]
        n = agent_rec["calls"]
        agent_rec["avg_pnl"] = round(old_pnl + (pnl - old_pnl) / n, 2) if n > 0 else pnl

        # Ajuster le poids : entre 0.5 et 2.0 basé sur le win rate
        win_rate = agent_rec["correct"] / agent_rec["calls"] if agent_rec["calls"] > 0 else 0.5
        weight = 1.0 + (win_rate - 0.5) * 1.5
        agent_rec["weight"] = round(max(0.3, min(2.5, weight)), 2)

    save_track_record(record)


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if "--track" in sys.argv:
        record = load_track_record()
        for agent, data in sorted(record.items()):
            if agent in ("created", "updated"):
                continue
            bar = "█" * int(data["weight"] * 10)
            print(f"{agent:<20} poids:{data['weight']:.2f} {bar}")
            print(f"   Appels:{data['calls']} Correct:{data['correct']} WinRate:{data['correct']/data['calls']*100:.0f}%" if data['calls'] > 0 else "   (pas de données)")
    else:
        print("Usage: python3 scripts/agor/agents.py --track")