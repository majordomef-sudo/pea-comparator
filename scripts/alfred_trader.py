#!/usr/bin/env python3
"""
alfred_trader.py — Agent conseil action Alfred v2.0
Veille quotidienne 100+ entreprises avec indicateurs techniques,
news scraping, suivi portefeuille, et scoring conviction.

Framework : Gavekal (macro) + Taleb (convexité)
Objectif : recommandations actionnables pour faire gagner de l'argent.
"""
import json
import os
import sys
import time
import math
import re
from pathlib import Path
from datetime import datetime, timedelta

import yfinance as yf
import pandas as pd
import requests

# Ajouter le workspace au path pour les imports locaux
WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

# Modules veille événementielle et apprentissage
from scripts import news_context
from scripts import self_learning
from scripts import paper_trading

STATE_DIR = WORKSPACE / "state" / "stock_watch"
WATCHLIST_FILE = STATE_DIR / "watchlist.json"
SCAN_DIR = STATE_DIR / "daily_scans"
PORTFOLIO_FILE = STATE_DIR / "portfolio.json"
MACRO_FILE = STATE_DIR / "macro_cache.json"
NEWS_CACHE = STATE_DIR / "news_cache.json"

# ─── Configuration signaux ──────────────────────────────────

SIGNAL_CONFIG = {
    "buy_good": -5.0,
    "buy_strong": -8.0,
    "buy_crash": -12.0,
    "take_profit": 25.0,
    "take_profit_rapide": 8.0,
    "sell_warning": -25.0,
    "stop_loss_spec": -18.0,
    "stop_loss_core": -25.0,
    "volume_spike": 2.0,
    "rsi_oversold": 30,
    "rsi_sell": 72,
    "rsi_overbought": 80,
}

# ─── Currency detection ────────────────────────────────────
_CURRENCY_CACHE = {}
_CURRENCY_MAP = {"USD": "$", "EUR": "€", "GBP": "£", "GBp": "£", "CHF": "CHF"}

def fetch_currency(yahoo_ticker: str) -> str:
    """Détecte la devise de trading depuis yfinance.info, avec cache."""
    if yahoo_ticker in _CURRENCY_CACHE:
        return _CURRENCY_CACHE[yahoo_ticker]
    try:
        t = yf.Ticker(yahoo_ticker)
        info = t.info if hasattr(t, "info") else {}
        currency = info.get("currency", "USD")
    except Exception:
        currency = "USD"
    _CURRENCY_CACHE[yahoo_ticker] = currency
    return currency


def currency_symbol(currency_code: str) -> str:
    """Convertit un code ISO devise en symbole monétaire."""
    return _CURRENCY_MAP.get(currency_code, currency_code)
# ─── Yahoo Finance suffix mapping ──────────────────────────
_YHOO_SUFFIX = {
    "ASML": "ASML.AS", "IFX": "IFX.DE", "STM": "STMPA.PA",
    "SOI": "SOI.PA", "BESI": "BESI.AS", "ASM": "ASM.AS",
    "SAP": "SAP.DE", "DSY": "DSY.PA", "CAP": "CAP.PA",
    "ATE": "ATE.PA",
    "RHM": "RHM.DE", "HO": "HO.PA", "SAF": "SAF.PA",
    "AIR": "AIR.PA",
    "RMS": "RMS.PA", "MC": "MC.PA", "CDI": "CDI.PA",
    "KER": "KER.PA", "CFR": "CFR.SW", "NESN": "NESN.SW",
    "DGE": "DGE.L", "MONC": "MONC.MI", "BRBY": "BRBY.L",
    "NOVO-B": "NOVO-B.CO", "EL": "EL.PA", "SAN": "SAN.PA",
    "BIM": "BIM.PA",
    "TTE": "TTE.PA", "SU": "SU.PA", "ENR": "ENR.DE",
    "NEX": "NEX.PA", "VWS": "VWS.CO", "SHEL": "SHEL.L",
    "BP": "BP.L",
    "ACA": "ACA.PA", "GLE": "GLE.PA", "BNP": "BNP.PA",
    "CS": "CS.PA", "SGO": "SGO.PA",
    "VIE": "VIE.PA", "SIE": "SIE.DE", "ABBN": "ABBN.SW",
    "UBI": "UBI.PA", "PUB": "PUB.PA",
    "LDO": "LDO.MI", "IPN": "IPN.PA",
    "GET": "GET.PA", "SPIE": "SPIE.PA",
    "MTX": "MTX.DE", "LR": "LR.PA",
}


def resolve_ticker(ticker: str) -> str:
    return _YHOO_SUFFIX.get(ticker, ticker)


# ═══════════════════════════════════════════════════════════
# 1. INDICATEURS TECHNIQUES
# ═══════════════════════════════════════════════════════════

def calc_rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta.where(delta < 0, 0.0))
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, 0.001)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not rsi.empty else 50.0


def calc_macd(series: pd.Series) -> dict:
    ema12 = series.ewm(span=12).mean()
    ema26 = series.ewm(span=26).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9).mean()
    histogram = macd_line - signal
    return {
        "macd": float(macd_line.iloc[-1]) if not macd_line.empty else 0,
        "signal": float(signal.iloc[-1]) if not signal.empty else 0,
        "histogram": float(histogram.iloc[-1]) if not histogram.empty else 0,
        "bullish": bool(macd_line.iloc[-1] > signal.iloc[-1]) if not macd_line.empty else None,
    }


def calc_ma(series: pd.Series, period: int) -> float:
    return float(series.rolling(window=period).mean().iloc[-1]) if len(series) >= period else 0


def compute_technical_indicators(hist: pd.DataFrame) -> dict:
    """Calcule tous les indicateurs techniques pour un DataFrame."""
    if hist.empty or "Close" not in hist:
        return {}
    close = hist["Close"]
    result = {
        "rsi_14": round(calc_rsi(close), 1),
        "macd": calc_macd(close),
        "ma_20": round(calc_ma(close, 20), 2) if len(close) >= 20 else None,
        "ma_50": round(calc_ma(close, 50), 2) if len(close) >= 50 else None,
        "ma_200": round(calc_ma(close, 200), 2) if len(close) >= 200 else None,
        "volatility_14d": round(float(close.pct_change().rolling(14).std().iloc[-1]) * 100, 2) if len(close) >= 14 else None,
    }

    # Signaux techniques
    signals = []
    price = float(close.iloc[-1])
    
    if result["rsi_14"] <= SIGNAL_CONFIG["rsi_oversold"]:
        signals.append(f"RSI oversold ({result['rsi_14']})")
    elif result["rsi_14"] >= SIGNAL_CONFIG["rsi_overbought"]:
        signals.append(f"RSI overbought ({result['rsi_14']})")

    if result["ma_20"] and price < result["ma_20"]:
        signals.append(f"Sous MA20 (×{round(result['ma_20']/price, 2)})")
    if result["ma_50"] and price < result["ma_50"] * 0.95:
        signals.append(f"Sous MA50 ({round((1-price/result['ma_50'])*100,1)}%)")
    if result["macd"]["bullish"]:
        signals.append("MACD+")

    result["signals"] = signals
    return result


# ═══════════════════════════════════════════════════════════
# 2. NEWS SCRAPING
# ═══════════════════════════════════════════════════════════

def fetch_stock_news(ticker: str, name: str, max_results: int = 3) -> list:
    """Scrape les news récentes pour un ticker via Google News / Yahoo Finance."""
    news = []
    try:
        # Via Yahoo Finance news
        t = yf.Ticker(ticker)
        if hasattr(t, "news") and t.news:
            for article in t.news[:max_results]:
                title = article.get("title", "") or ""
                if not title.strip():
                    continue
                news.append({
                    "title": title,
                    "publisher": article.get("publisher", ""),
                    "link": article.get("link", ""),
                    "date": datetime.fromtimestamp(article.get("providerPublishTime", 0)).strftime("%Y-%m-%d %H:%M") if article.get("providerPublishTime") else "",
                    "source": "yahoo",
                })
    except Exception:
        pass

    # Si Yahoo n'a pas donné d'articles utiles, fallback
    if not news:
        try:
            from duckduckgo_search import DDGS
            with DDGS() as ddgs:
                raw = list(ddgs.news(f"{name} {ticker} stock", max_results=3))
                for r in raw:
                    news.append({
                        "title": r.get("title", ""),
                        "publisher": r.get("source", ""),
                        "link": r.get("url", ""),
                        "date": r.get("date", ""),
                        "source": "duckduckgo",
                    })
        except Exception:
            try:
                url = f"https://news.google.com/rss/search?q={ticker}+stock&hl=en-US&gl=US&ceid=US:en"
                r = requests.get(url, timeout=5)
                if r.status_code == 200:
                    import xml.etree.ElementTree as ET
                    root = ET.fromstring(r.content)
                    for item in list(root.iter("item"))[:max_results]:
                        title = item.findtext("title", "")
                        link = item.findtext("link", "")
                        pub_date = item.findtext("pubDate", "")[:10]
                        news.append({
                            "title": title, "publisher": "Google News",
                            "link": link, "date": pub_date, "source": "google",
                        })
            except Exception:
                pass

    return news[:max_results]


def fetch_earnings_date(ticker: str) -> dict:
    """Récupère la prochaine date de résultats."""
    try:
        t = yf.Ticker(ticker)
        if hasattr(t, "calendar") and t.calendar:
            cal = t.calendar
            if "Earnings Date" in cal:
                ed = cal["Earnings Date"]
                if isinstance(ed, pd.Timestamp):
                    return {
                        "next_earnings": ed.strftime("%Y-%m-%d"),
                        "days_until": (ed - datetime.now()).days,
                    }
    except Exception:
        pass
    return {}


# ═══════════════════════════════════════════════════════════
# 3. PRICE FETCHING (amélioré)
# ═══════════════════════════════════════════════════════════

def fetch_prices_and_tech(tickers: list) -> dict:
    """Récupère prix + historique long pour indicateurs tech."""
    results = {}
    batch_size = 10  # Plus petit pour obtenir de l'historique
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        yahoo_tickers = [resolve_ticker(t) for t in batch]

        # 1. Fetch long history for technical indicators (3 mois min)
        try:
            data_3m = yf.download(yahoo_tickers, period="3mo", interval="1d", progress=False, group_by="ticker", threads=True)
            # 2. Fetch short history (5d) for latest prices
            data_5d = yf.download(yahoo_tickers, period="5d", interval="1d", progress=False, group_by="ticker", threads=True)
        except Exception:
            data_3m = pd.DataFrame()
            data_5d = pd.DataFrame()

        for idx, ticker in enumerate(batch):
            yahoo_t = yahoo_tickers[idx]
            try:
                # Extraire les dataframes pour ce ticker
                df_long = _extract_ticker_df(data_3m, yahoo_t)
                df_short = _extract_ticker_df(data_5d, yahoo_t) if not data_5d.empty else df_long

                if df_short is None or df_short.empty:
                    # Solo fallback
                    solo = yf.download(yahoo_t, period="3mo", interval="1d", progress=False)
                    if solo is None or solo.empty or len(solo) < 2:
                        results[ticker] = {"error": "No data"}
                        continue
                    df_long = df_short = solo

                close = df_short["Close"] if "Close" in df_short else df_short.iloc[:, 0]
                if len(close) < 2:
                    results[ticker] = {"error": "Insufficient data"}
                    continue

                price = float(close.iloc[-1])
                prev = float(close.iloc[-2])
                change_pct = ((price - prev) / prev) * 100 if prev else 0
                volume = int(df_short["Volume"].iloc[-1]) if "Volume" in df_short else 0
                avg_volume = int(df_short["Volume"].mean()) if "Volume" in df_short else 0

                # Technical indicators from the 3-month data
                tech = compute_technical_indicators(df_long)

                # 7-day change (for take-profit / stop-loss signals)
                close_long = df_long["Close"] if "Close" in df_long else df_long.iloc[:, 0]
                change_7d_pct = 0.0
                if len(close_long) >= 7:
                    price_7d_ago = float(close_long.iloc[-7])
                    change_7d_pct = ((price - price_7d_ago) / price_7d_ago) * 100 if price_7d_ago else 0

                result = {
                    "price": round(price, 2),
                    "change_pct": round(change_pct, 2),
                    "change_7d_pct": round(change_7d_pct, 2),
                    "volume": volume,
                    "avg_volume_5d": avg_volume,
                    "volume_ratio": round(volume / avg_volume, 2) if avg_volume > 0 else 0,
                    "date": str(close.index[-1].date()) if hasattr(close.index[-1], "date") else "",
                    **tech,
                }
                results[ticker] = result

            except Exception as e:
                if ticker not in results:
                    results[ticker] = {"error": str(e)[:80]}

        time.sleep(0.5)

    return results


def _extract_ticker_df(data: pd.DataFrame, yahoo_ticker: str) -> pd.DataFrame:
    """Extrait le DataFrame pour un ticker depuis un multi-index."""
    if data is None or data.empty:
        return None
    try:
        if isinstance(data.columns, pd.MultiIndex):
            # Try (Ticker, Price) format
            if data.columns.names[0] == "Ticker":
                if yahoo_ticker in data.columns.get_level_values(0):
                    return data.xs(yahoo_ticker, axis=1, level=0)
            # Try (Price, Ticker) format  
            elif data.columns.names[0] == "Price":
                close = data.xs("Close", axis=1, level=0)
                if yahoo_ticker in close.columns:
                    result = pd.DataFrame()
                    for col in ["Open", "High", "Low", "Close", "Volume"]:
                        if col in data.columns.get_level_values(0):
                            result[col] = data.xs(col, axis=1, level=0)[yahoo_ticker]
                    return result
        else:
            return data
    except Exception:
        pass
    return None


# ═══════════════════════════════════════════════════════════
# 4. NEWS + EARNINGS ENRICHISSEMENT
# ═══════════════════════════════════════════════════════════

def enrich_with_news(prices: dict, stocks: list) -> dict:
    """Ajoute news et dates résultats aux stocks qui bougent."""
    news_cache = {}
    if NEWS_CACHE.exists():
        try:
            news_cache = json.load(open(NEWS_CACHE))
        except Exception:
            news_cache = {}

    enriched = {}
    now = datetime.now().strftime("%Y-%m-%d")

    needs_news = []
    for stock in stocks:
        ticker = stock["ticker"]
        price_data = prices.get(ticker, {})
        if "error" in price_data:
            continue
        # News seulement si mouvement significatif ou stock Core
        change = abs(price_data.get("change_pct", 0))
        risk = stock.get("risk_profile", "")
        vol_ratio = price_data.get("volume_ratio", 0)
        is_core = risk in ("Defensive", "Defensive Growth", "Cyclical Growth")
        if change >= 3 or vol_ratio >= 1.5 or is_core:
            needs_news.append(stock)

    # Cache les news pour la journée
    for stock in needs_news[:20]:
        ticker = stock["ticker"]
        cache_key = f"{ticker}_{now}"
        if cache_key in news_cache:
            news_list = news_cache[cache_key]
        else:
            news_list = fetch_stock_news(ticker, stock.get("name", ""))
            if news_list:
                news_cache[cache_key] = news_list

        earnings = fetch_earnings_date(ticker)
        enriched[ticker] = {"news": news_list, "earnings": earnings}

    # Sauvegarde cache — nettoie entrées vides et >7 jours
    cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    news_cache = {k: v for k, v in news_cache.items()
                  if v and any(n.get("title", "").strip() for n in v)
                  and k.split("_")[-1] >= cutoff}
    if len(news_cache) > 500:
        news_cache = dict(list(news_cache.items())[-300:])
    NEWS_CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(NEWS_CACHE, "w") as f:
        json.dump(news_cache, f, indent=2)

    return enriched


# ═══════════════════════════════════════════════════════════
# 5. SCORING CONVICTION — AGOR Multi-Agent System
# ═══════════════════════════════════════════════════════════
# Remplacé par le système multi-agents AGOR (scripts/agor/agents.py)
# Analyse 6 agents (Technical, Bull, Bear, Value, Sentiment, Momentum)
# pondérés par leur track record + Risk Manager avec Safety Mode

def score_conviction(ticker_data: dict, stock: dict) -> dict:
    """Calcule un score de conviction via le système multi-agents AGOR.

    Remplace l'ancienne fonction score_conviction simple par une
    architecture multi-analystes (via scripts/agor/agents.py).
    """
    from scripts.agor import run_agents, get_weighted_score, load_track_record
    from scripts.agor import assess_ticker_risk

    ticker = stock.get("ticker", "")
    name = stock.get("name", "")

    # 1. Executer tous les agents
    agent_signals = run_agents(ticker, name, ticker_data, stock)

    # 2. Charger le track record
    track_record = load_track_record()

    # 3. Agrégation pondérée
    weighted = get_weighted_score(agent_signals, track_record)

    # 4. Évaluation du risque
    risk = assess_ticker_risk(ticker, ticker_data, stock)

    # 5. Safety check
    from scripts.agor.risk_manager import check_safety
    safety = check_safety()

    # 6. Score final = score AGOR ajusté par le risque
    final_score = weighted["final_score"]

    # Ajustement risque
    if risk["risk_level"] == "high":
        final_score -= 10
    elif risk["risk_level"] == "medium":
        final_score -= 3

    # Safety mode
    if safety["restricted"]:
        final_score = max(final_score - 15, 0)

    final_score = max(0, min(100, round(final_score, 1)))

    # Verdict enrichi
    if final_score >= 75:
        verdict = f"🟢 FORTE OPPORTUNITÉ ({weighted['bullish_count']}/{weighted['total_agents']} agents haussiers)"
    elif final_score >= 60:
        verdict = f"🟡 Opportunité modérée ({weighted['bullish_count']}/{weighted['total_agents']} haussiers)"
    elif final_score <= 25:
        verdict = "🔴 Éviter maintenant"
    elif final_score <= 40:
        verdict = "🟠 Surveiller"
    else:
        verdict = "⚪ Neutre"

    # Raisons des agents (top 3)
    reasons = []
    risks = []
    for c in weighted["contributions"]:
        if c["score"] > 0:
            agent_emoji = "🟢" if c["agent_key"] != "bear_agent" else "🔴"
            reasons.append(f"{agent_emoji} {c['agent']} +{c['score']} (pds {c['weight']})")
        elif c["score"] < 0:
            risks.append(f"🔴 {c['agent']} {c['score']} (pds {c['weight']})")

    if risk["reasons"] and risk["risk_level"] != "low":
        risks.append(f"⚠️ Risque {risk['risk_level']}: {risk['reasons'][:60]}")

    return {
        "score": final_score,
        "verdict": verdict,
        "reasons": reasons[:3],
        "risks": risks[:3],
        "agor_agents": weighted["contributions"],
        "agor_consensus": {
            "bulls": weighted["bullish_count"],
            "bears": weighted["bearish_count"],
            "neutrals": weighted["neutral_count"],
        },
    }


# ═══════════════════════════════════════════════════════════
# 6. MACRO SCAN
# ═══════════════════════════════════════════════════════════

def fetch_macro() -> dict:
    """Scanne les indicateurs macro clés."""
    macro = {}
    indicators = {
        "SPY": "S&P 500",
        "QQQ": "Nasdaq",
        "^VIX": "VIX (volatilité)",
        "DX-Y.NYB": "Dollar Index",
        "^TNX": "Taux 10 ans US",
        "CL=F": "Pétrole (WTI)",
        "GC=F": "Or",
        "BTC-USD": "Bitcoin",
        "^STOXX50E": "EURO STOXX 50",
    }
    for ticker, label in indicators.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            if hist is not None and len(hist) >= 2:
                price = float(hist["Close"].iloc[-1])
                prev = float(hist["Close"].iloc[-2])
                change = ((price - prev) / prev) * 100
                macro[ticker] = {
                    "label": label, "price": round(price, 2),
                    "change_pct": round(change, 2),
                }
        except Exception:
            continue
    return macro


# ═══════════════════════════════════════════════════════════
# 7. SUIVI PORTEFEUILLE
# ═══════════════════════════════════════════════════════════

def load_portfolio() -> dict:
    """Charge le portefeuille si défini."""
    if PORTFOLIO_FILE.exists():
        return json.load(open(PORTFOLIO_FILE))
    return {"holdings": [], "total_invested": 0, "cash": 0}


def calc_portfolio_value(prices: dict) -> dict:
    """Calcule la valeur du portefeuille aux prix actuels."""
    portfolio = load_portfolio()
    if not portfolio.get("holdings"):
        return {"has_portfolio": False}

    total_value = 0
    holdings_value = []
    for h in portfolio["holdings"]:
        ticker = h["ticker"]
        qty = h["quantity"]
        avg_price = h.get("avg_price", 0)
        price_data = prices.get(ticker, {})
        if "error" in price_data:
            continue
        current_price = price_data.get("price", 0)
        value = qty * current_price
        cost = qty * avg_price
        pnl = value - cost
        pnl_pct = ((current_price - avg_price) / avg_price) * 100 if avg_price else 0
        total_value += value
        holdings_value.append({
            "ticker": ticker,
            "name": h.get("name", ticker),
            "qty": qty,
            "avg_price": avg_price,
            "current_price": current_price,
            "value": round(value, 2),
            "pnl": round(pnl, 2),
            "pnl_pct": round(pnl_pct, 2),
        })

    total_invested = portfolio.get("total_invested", 0)
    cash = portfolio.get("cash", 0)
    total = total_value + cash
    total_pnl = total - total_invested
    total_pnl_pct = (total / total_invested - 1) * 100 if total_invested else 0

    return {
        "has_portfolio": True,
        "holdings": holdings_value,
        "total_invested": total_invested,
        "total_value": round(total_value, 2),
        "cash": cash,
        "total_portfolio": round(total, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
    }


# ═══════════════════════════════════════════════════════════
# 8. REPORT GÉNÉRATION
# ═══════════════════════════════════════════════════════════

def generate_report(prices: dict, signals: list, stocks: list, enriched: dict, macro: dict, conviction: dict, portfolio: dict, pt_stats: dict = None) -> str:
    """Génère le rapport final formaté pour Telegram."""
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    parts = [f"📊 **Alfred Stock Watch — {today}**"]
    parts.append("")

    # ── Section Portefeuille ──
    if portfolio.get("has_portfolio"):
        pnl = portfolio["total_pnl_pct"]
        pnl_emoji = "🟢" if pnl >= 0 else "🔴"
        parts.append(f"**{pnl_emoji} Portefeuille :** {portfolio['total_value']:.0f}€ ({portfolio['total_pnl_pct']:+.1f}%)")
        parts.append(f"   Cash: {portfolio['cash']:.0f}€ | Total: {portfolio['total_portfolio']:.0f}€")
        parts.append("")

    # ── Section Macro ──
    if macro:
        parts.append("**🌍 Macro :**")
        for ticker, data in list(macro.items())[:5]:
            emoji = "🟢" if data["change_pct"] >= 0 else "🔴"
            parts.append(f"   {data['label']}: {emoji} {data['price']} ({data['change_pct']:+.1f}%)")
        parts.append("")

    # ── Section Portefeuille Papier ──
    if pt_stats:
        gain_emoji = "🟢" if pt_stats["total_gain_pct"] >= 0 else "🔴"
        parts.append(f"**💰 Paper Trading :** {pt_stats['total_value']:.0f}€ ({pt_stats['total_gain_pct']:+.1f}%)")
        parts.append(f"   Cash: {pt_stats['cash']:.0f}€ | Win rate: {pt_stats['win_rate']}% | Trades: {pt_stats['total_trades']}")
        if pt_stats["open_positions"]:
            for pos in pt_stats["open_positions"][:3]:
                emoji = "🟢" if pos["pnl_pct"] >= 0 else "🔴"
                parts.append(f"   {emoji} {pos['ticker']}: {pos['pnl_pct']:+.1f}% (J+{pos['days_held']})")
        parts.append("")

    # ── Section Signaux HAUTE priorité ──
    high = [s for s in signals if s.get("priority") == "HIGH"]
    high_tickers = set()
    if high:
        parts.append(f"🔴 **{len(high)} SIGNAL{'X' if len(high)>1 else ''} HAUTE PRIORITÉ :**")
        for s in high:
            high_tickers.add(s["ticker"])
            tag = " 🇪🇺" if s.get("pea") else " 🇺🇸"
            name = s.get("name", s["ticker"])
            action = s.get("action", "Surveiller")
            parts.append(f"• **{name}** ({s['ticker']}) : {s['change']:+.1f}%")
            parts.append(f"   {s['message']}{tag}")
            parts.append(f"   → **Action :** {action}")

            # Ajouter news si disponibles
            ticker_news = enriched.get(s["ticker"], {}).get("news", [])
            for n in ticker_news[:2]:
                parts.append(f"   📰 {n['title'][:120]}")
            # Ajouter conviction
            cv = conviction.get(s["ticker"], {})
            if cv:
                parts.append(f"   **Score conviction :** {cv['score']}/100 — {cv['verdict']}")
        parts.append("")

    # ── Section Signaux VENTE (sans dupliquer ceux déjà en HAUTE) ──
    sell_signals = [s for s in signals if s.get("type") in ("SELL_RSI", "TAKE_PROFIT_RAPIDE", "STOP_LOSS", "TAKE_PROFIT") and s.get("priority") in ("HIGH", "MEDIUM") and s["ticker"] not in high_tickers]
    if sell_signals:
        parts.append("**🔴 Signaux VENTE :**")
        for s in sell_signals[:5]:
            tag = " 🇪🇺" if s.get("pea") else " 🇺🇸"
            change_str = f" | {s.get('change_7d',0):+.1f}% en 7j" if s.get('change_7d') else ""
            parts.append(f"• {s['message']}{change_str}{tag}")
            parts.append(f"   → **Action :** {s.get('action', 'Surveiller')}")
        if len(sell_signals) > 5:
            parts.append(f"  ... et {len(sell_signals)-5} autres")
        parts.append("")

    # ── Section Recommandations ──
    recos = [cv for cv in conviction.values() if isinstance(cv, dict) and cv.get("score", 0) >= 60]
    if recos:
        recos.sort(key=lambda x: -x["score"])
        parts.append(f"🟢 **Recommandations du jour :**")
        for r in recos[:5]:
            ticker = r.get("ticker", "")
            name = r.get("name", ticker)
            change = r.get("change_pct", 0)
            pea_tag = " 🇪🇺" if r.get("pea") else " 🇺🇸"
            parts.append(f"• **{name}** ({ticker}): {change:+.1f}% — Score {r['score']}/100{pea_tag}")
            # Catalyseur événementiel
            cat_reason = r.get("news_reason")
            if cat_reason:
                cat_icon = "🟢" if (r.get("catalyst") or 0) > 0 else "🔴"
                parts.append(f"   {cat_icon} {cat_reason}")
            for reason in r.get("reasons", []):
                parts.append(f"   ✅ {reason}")
            for risk in r.get("risks", []):
                parts.append(f"   ⚠️ {risk}")
            # Agent consensus
            consensus = r.get("agor_consensus")
            if consensus:
                bulls = consensus["bulls"]
                bears = consensus["bears"]
                total = bulls + bears + consensus["neutrals"]
                bar_bulls = "🟢" * bulls if bulls else ""
                bar_bears = "🔴" * bears if bears else ""
                bar_neu = "⚪" * consensus["neutrals"] if consensus["neutrals"] else ""
                parts.append(f"   Agents: {bar_bulls}{bar_bears}{bar_neu} ({bulls}B/{bears}R/{consensus['neutrals']}N)")
            # News associées
            ticker_news = enriched.get(ticker, {}).get("news", [])
            for n in ticker_news[:1]:
                parts.append(f"   📰 {n['title'][:120]}")
        parts.append("")

    # ── Section Alertes ──
    med = [s for s in signals if s.get("priority") == "MEDIUM"]
    if med:
        parts.append(f"🟡 **{len(med)} alertes :**")
        for s in med[:5]:
            tag = " 🇪🇺" if s.get("pea") else " 🇺🇸"
            parts.append(f"• {s['message']}{tag}")
        if len(med) > 5:
            parts.append(f"  ... et {len(med)-5} autres")
        parts.append("")

    # ── Top hausses/baisses du jour ──
    valid = {k: v for k, v in prices.items() if "error" not in v and "change_pct" in v}
    sorted_p = sorted(valid.items(), key=lambda x: x[1].get("change_pct", 0))

    if sorted_p:
        parts.append("**📈 Top 5 hausses :**")
        n = 0
        for ticker, data in sorted_p[-5:][::-1]:
            if data["price"]:
                sym = currency_symbol(data.get("currency", "USD"))
                parts.append(f"  {ticker} : {data['change_pct']:+.1f}% à {data['price']}{sym}")
                n += 1
        if n == 0:
            parts[-1] += " (aucune)"


        parts.append("")
        parts.append("**📉 Top 5 baisses :**")
        n = 0
        for ticker, data in sorted_p[:5]:
            if data["price"]:
                sym = currency_symbol(data.get("currency", "USD"))
                parts.append(f"  {ticker} : {data['change_pct']:+.1f}% à {data['price']}{sym}")
                n += 1
        if n == 0:
            parts[-1] += " (aucune)"

    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
# 9. SCAN PRINCIPAL
# ═══════════════════════════════════════════════════════════

def run_scan(quiet: bool = False):
    """Scan complet v2.0 : prix + tech + news + macro + conviction."""
    _log = lambda *a, **kw: None if quiet else print(*a, **kw)

    _log(f"\n{'='*50}")
    _log(f"  📊 STOCK AGENT v2.0 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    _log(f"{'='*50}")

    # 1. Load watchlist
    wl = json.load(open(WATCHLIST_FILE))
    sectors = wl["sectors"]
    stocks = []
    for key in sectors:
        for s in sectors[key]["stocks"]:
            s["sector"] = sectors[key].get("label", key)
            s["risk_profile"] = sectors[key].get("risk", "Growth")
            stocks.append(s)
    tickers = [s["ticker"] for s in stocks]

    _log(f"📡 Watchlist: {len(stocks)} entreprises")

    # 1b. News context — veille événementielle
    _log("🌐 Veille événementielle (news_context) ...")
    try:
        catalyst_mods = news_context.get_catalyst_modifiers(tickers=tickers)
        _log(f"✅ {len(catalyst_mods)} catalyseurs événementiels détectés")
        for t, m in sorted(catalyst_mods.items(), key=lambda x: -abs(x[1]["catalyst"]))[:5]:
            icon = "🟢" if m["catalyst"] > 0 else "🔴"
            _log(f"   {icon} {t} : {m['catalyst']:+.1f} — {m['reason']}")
    except Exception as e:
        _log(f"⚠️ Veille événementielle indisponible : {e}")
        catalyst_mods = {}

    # 2. Fetch prices + technical indicators
    _log("💵 Fetching prices + indicateurs techniques ...")
    prices = fetch_prices_and_tech(tickers)
    ok = sum(1 for v in prices.values() if "error" not in v)
    _log(f"✅ {ok}/{len(tickers)} tickers")

    # 3. Fetch macro
    _log("🌍 Macro scan ...")
    macro = fetch_macro()

    # 4. Fetch news + earnings
    _log("📰 News + earnings ...")
    enriched = enrich_with_news(prices, stocks)

    # 5. Generate conviction scores (with catalyst modifiers)
    _log("📊 Scoring conviction ...")
    conviction = {}
    for stock in stocks:
        ticker = stock["ticker"]
        pd_ = prices.get(ticker, {})
        if "error" in pd_:
            continue
        cv = score_conviction(pd_, stock)
        cv["ticker"] = ticker
        cv["name"] = stock.get("name", ticker)
        cv["change_pct"] = pd_.get("change_pct", 0)
        cv["pea"] = stock.get("pea", False)

        # Appliquer le modificateur événementiel
        cat_mod = catalyst_mods.get(ticker)
        if cat_mod:
            cv["catalyst"] = cat_mod["catalyst"]
            cv["news_reason"] = cat_mod["reason"]
            # Le catalyseur modifie le score : max ±15 points
            adj = cat_mod["catalyst"] * 3
            cv["score_raw"] = cv["score"]
            cv["score"] = max(0, min(100, cv["score"] + adj))
            cv["score_adjustment"] = adj

        if cv["score"] >= 60 or cv["score"] <= 25:
            conviction[ticker] = cv

    # 6. Generate signals (from price data + conviction)
    signals = []
    for stock in stocks:
        ticker = stock["ticker"]
        pd_ = prices.get(ticker, {})
        if "error" in pd_:
            continue
        change = pd_.get("change_pct", 0)
        change_7d = pd_.get("change_7d_pct", 0)
        vol_ratio = pd_.get("volume_ratio", 0)
        rsi = pd_.get("rsi_14", 50)
        is_core = stock["risk_profile"] in ("Defensive", "Defensive Growth")
        name = stock.get("name", ticker)
        pea = stock.get("pea", False)

        # ── SELL SIGNALS (checked first, no elif to allow stacking) ──

        # RSI OVERBOUGHT SELL (only if confirmed by 7-day gain or strong daily move)
        if rsi >= SIGNAL_CONFIG["rsi_overbought"]:
            has_gain = change_7d >= 3.0 or change >= 2.0
            priority = "HIGH" if (rsi >= 85 and has_gain) else "LOW"
            action = "Vendre 50-100%" if priority == "HIGH" else "Vigilance"
            if priority != "LOW" or has_gain:
                signals.append({
                    "type": "SELL_RSI", "ticker": ticker, "name": name,
                    "change": change, "change_7d": change_7d, "pea": pea, "priority": priority,
                    "action": action, "risk": stock["risk_profile"],
                    "message": f"🔴 {name} ({ticker}) : RSI {rsi} — sur-achat" + (f" +{change_7d:.0f}% en 7j" if has_gain else ""),
                })
        elif rsi >= SIGNAL_CONFIG["rsi_sell"]:
            has_gain = change_7d >= 3.0 or change >= 2.0
            if has_gain:
                signals.append({
                    "type": "SELL_RSI", "ticker": ticker, "name": name,
                    "change": change, "change_7d": change_7d, "pea": pea, "priority": "LOW",
                    "action": "Vendre 30% si grosse position", "risk": stock["risk_profile"],
                    "message": f"🟠 {name} ({ticker}) : RSI {rsi} +{change_7d:.0f}% 7j",
                })

        # TAKE PROFIT RAPIDE (+8% en 7 jours)
        if change_7d >= SIGNAL_CONFIG["take_profit_rapide"] and is_core:
            signals.append({
                "type": "TAKE_PROFIT_RAPIDE", "ticker": ticker, "name": name,
                "change": change, "change_7d": change_7d, "pea": pea, "priority": "MEDIUM",
                "action": "Vendre 30%", "risk": stock["risk_profile"],
                "message": f"💰 {name} ({ticker}) : +{change_7d:.0f}% en 7j → prendre bénéfices",
            })

        # STOP LOSS (baisse rapide en 7j + RSI confirmation)
        if change_7d <= SIGNAL_CONFIG["stop_loss_spec"] and rsi <= 40:
            sl_priority = "HIGH" if (change_7d <= SIGNAL_CONFIG["stop_loss_core"] or rsi <= 25) else "MEDIUM"
            signals.append({
                "type": "STOP_LOSS", "ticker": ticker, "name": name,
                "change": change, "change_7d": change_7d, "pea": pea, "priority": sl_priority,
                "action": "Vendre", "risk": stock["risk_profile"],
                "message": f"⚠️ {name} ({ticker}) : -{abs(change_7d):.0f}% en 7j (RSI {rsi}) → stop loss",
            })

        # ── BUY / HOLD SIGNALS (elif-chain) ──

        # SELL WARNING (long-term)
        if change <= SIGNAL_CONFIG["sell_warning"]:
            signals.append({
                "type": "SELL_WARNING", "ticker": ticker, "name": name,
                "change": change, "pea": pea, "priority": "HIGH",
                "action": "Vendre", "risk": stock["risk_profile"],
                "message": f"⚠️ {name} ({ticker}) : -{abs(change):.0f}% — vente recommandée",
            })
        # BUY CRASH
        elif change <= SIGNAL_CONFIG["buy_crash"] and is_core:
            signals.append({
                "type": "BUY_CRASH", "ticker": ticker, "name": name,
                "change": change, "pea": pea, "priority": "HIGH",
                "action": "Analyser avant achat",
                "message": f"🔥 {name} ({ticker}) : -{abs(change):.0f}% — crash Core, investiguer",
            })
        # BUY STRONG (rsi oversold + price drop)
        elif change <= SIGNAL_CONFIG["buy_strong"] and is_core and rsi <= 35:
            signals.append({
                "type": "BUY_STRONG", "ticker": ticker, "name": name,
                "change": change, "pea": pea, "priority": "HIGH",
                "action": "Acheter",
                "message": f"🟢 {name} ({ticker}) : -{abs(change):.0f}% + RSI {rsi} — ACHETER",
            })
        # BUY GOOD
        elif change <= SIGNAL_CONFIG["buy_good"] and is_core:
            signals.append({
                "type": "BUY_GOOD", "ticker": ticker, "name": name,
                "change": change, "pea": pea, "priority": "MEDIUM",
                "action": "Acheter si disponible",
                "message": f"📉 {name} ({ticker}) : -{abs(change):.0f}% — opportunité",
            })
        # BUY OVERSOLD (non-Core stocks with RSI ≤ 30)
        elif rsi <= 30 and not is_core:
            signals.append({
                "type": "BUY_OVERSOLD", "ticker": ticker, "name": name,
                "change": change, "pea": pea, "priority": "MEDIUM",
                "action": "Surveiller pour achat",
                "message": f"🟢 {name} ({ticker}) : RSI {rsi} — oversold sur non-Core",
            })
        # TAKE PROFIT (long-term 25%)
        elif change >= SIGNAL_CONFIG["take_profit"] and is_core:
            signals.append({
                "type": "TAKE_PROFIT", "ticker": ticker, "name": name,
                "change": change, "pea": pea, "priority": "MEDIUM",
                "action": "Vendre partiellement",
                "message": f"💰 {name} ({ticker}) : +{change:.0f}% — prendre bénéfices",
            })
        # VOLUME SPIKE
        if vol_ratio >= SIGNAL_CONFIG["volume_spike"]:
            signals.append({
                "type": "VOLUME_SPIKE", "ticker": ticker, "name": name,
                "change": change, "pea": pea, "priority": "MEDIUM",
                "action": "Surveiller",
                "message": f"📊 {name} ({ticker}) : volume ×{vol_ratio}",
            })

    # 7. Portfolio calculation
    portfolio = calc_portfolio_value(prices)

    # 7b. Self-learning : enregistrer les recommandations
    _log("🧠 Enregistrement des recommandations (self_learning) ...")
    for ticker, cv in conviction.items():
        if cv.get("score", 0) >= 60:
            price_data = prices.get(ticker, {})
            if "error" in price_data:
                continue
            price = price_data.get("price")
            # Calculer des targets basés sur la volatilité
            tp1 = round(price * 1.08, 2) if price else None
            tp2 = round(price * 1.25, 2) if price else None
            sl = round(price * 0.92, 2) if price else None

            signals_used = {
                "rsi_oversold": price_data.get("rsi_14", 50) <= 35,
                "macd_bullish": price_data.get("macd", {}).get("bullish", False),
                "volume_spike": price_data.get("volume_ratio", 0) >= 2,
                "dip_core": price_data.get("change_pct", 0) <= -3,
                "pea_bonus": cv.get("pea", False),
                "news_catalyst": cv.get("catalyst", 0) != 0,
                "ma_bounce": price_data.get("ma_20") and price and price < price_data["ma_20"],
            }
            try:
                self_learning.record_prediction(
                    ticker=ticker, name=cv.get("name", ticker),
                    recommendation="ACHETER" if cv.get("score", 0) >= 70 else "SURVEILLER",
                    score=cv.get("score", 0),
                    price_at_time=price,
                    target_tp1=tp1,
                    target_tp2=tp2,
                    stop_loss=sl,
                    reasons=cv.get("reasons", []),
                    signals_used=signals_used
                )
            except Exception:
                pass

    # Vérifier les outcomes des prédictions passées
    try:
        current_check = {t: d.get("price") for t, d in prices.items() if "error" not in d and d.get("price")}
        check_res = self_learning.check_outcomes(current_check)
        if check_res["updated"] > 0:
            _log(f"✅ {check_res['updated']} prédictions mises à jour")
        # Ajuster les poids si assez de data
        weights = self_learning.update_weights()
        _log(f"📊 Poids appris : {len([w for w in weights.values() if abs(w - 1) > 0.1])} ajustements actifs")
    except Exception as e:
        _log(f"⚠️ Self-learning : {e}")

    # 7c. Paper trading — exécution virtuelle des recommandations
    _log("💰 Paper trading ...")
    try:
        pt_results = paper_trading.auto_trade_from_scan(conviction, prices)
        if pt_results["buys"]:
            for b in pt_results["buys"]:
                if b.get("executed"):
                    p = b["position"]
                    _log(f"   🟢 ACHAT virtuel {p['ticker']} à {p['entry_price']}€ (score {p['entry_score']})")
        if pt_results["sells"]:
            for s in pt_results["sells"]:
                _log(f"   {'💰' if 'take_profit' in s.get('sell_reason','') else '🔴'} VENTE virtuelle {s['ticker']} — {s['pnl_pct']:+.1f}% ({s.get('sell_reason','')})")
        pt_stats = paper_trading.compute_stats({t: d.get("price") for t, d in prices.items() if "error" not in d and d.get("price")})
        _log(f"   💰 Portefeuille papier : {pt_stats['total_gain']:+.0f}€ ({pt_stats['total_gain_pct']:+.1f}%)")
        _log(f"   📈 Win rate: {pt_stats['win_rate']}% | Positions: {pt_stats['open_count']}")
    except Exception as e:
        _log(f"⚠️ Paper trading : {e}")
        pt_stats = None

    # 8. Generate report
    report = generate_report(prices, signals, stocks, enriched, macro, conviction, portfolio, pt_stats)

    # 9. Save outputs
    SCAN_DIR.mkdir(parents=True, exist_ok=True)
    scan_data = {
        "timestamp": datetime.now().isoformat(),
        "stats": {"total": len(tickers), "ok": ok, "signals": len(signals), "conviction_signals": len(conviction)},
        "signals": signals[:20],
        "conviction": conviction,
        "portfolio": portfolio,
        "paper_trading": pt_stats,
        "macro": macro,
        "report": report,
    }
    date = datetime.now().strftime("%Y-%m-%d")
    with open(SCAN_DIR / f"{date}.json", "w") as f:
        json.dump(scan_data, f, indent=2)

    if not quiet:
        print(f"\n{'='*50}")
        print(f"  ✅ Scan terminé : {ok}/{len(tickers)} tickers, {len(signals)} signaux")
        print(f"{'='*50}")
        print(report)

    return scan_data


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

def cmd_scan():
    run_scan(quiet=False)

def cmd_summary():
    date = datetime.now().strftime("%Y-%m-%d")
    f = SCAN_DIR / f"{date}.json"
    if f.exists():
        try:
            data = json.load(open(f))
            print(data.get("report", "Aucun rapport"))
        except (json.JSONDecodeError, IOError) as e:
            print(f"❌ Erreur lecture fichier scan: {e}")
    else:
        print(f"Aucun scan pour {date}. Lance avec --scan")

def cmd_init():
    SCAN_DIR.mkdir(parents=True, exist_ok=True)
    if not WATCHLIST_FILE.exists():
        print(f"❌ Watchlist introuvable: {WATCHLIST_FILE}")
        return
    try:
        wl = json.load(open(WATCHLIST_FILE))
    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ Erreur lecture watchlist: {e}")
        return
    stocks = []
    for k in wl["sectors"]:
        stocks.extend(wl["sectors"][k]["stocks"])
    print(f"✅ Watchlist: {len(stocks)} stocks")
    print(f"   🇪🇺 PEA: {sum(1 for s in stocks if s.get('pea'))}")
    print(f"   🇺🇸 US: {sum(1 for s in stocks if not s.get('pea'))}")

def cmd_test():
    if not WATCHLIST_FILE.exists():
        print(f"❌ Watchlist introuvable: {WATCHLIST_FILE}")
        return
    wl = json.load(open(WATCHLIST_FILE))
    stocks = []
    for k in wl["sectors"]:
        stocks.extend(wl["sectors"][k]["stocks"])
    test = stocks[:3]
    tickers = [s["ticker"] for s in test]
    prices = fetch_prices_and_tech(tickers)
    for t, d in prices.items():
        if "error" in d:
            print(f"❌ {t}: {d['error']}")
        else:
            rsi = d.get("rsi_14", "N/A")
            macd = d.get("macd", {}).get("bullish", "N/A")
            sym = currency_symbol(d.get("currency", "USD"))
            print(f"✅ {t}: {d['price']}{sym} ({d['change_pct']:+.1f}%) RSI={rsi} MACD+={macd}")

def cmd_portfolio():
    """Initialise le fichier portefeuille."""
    pf = PORTFOLIO_FILE
    if pf.exists():
        data = json.load(open(pf))
        print(f"Portefeuille existant: {len(data.get('holdings',[]))} lignes")
        print(f"Investi: {data.get('total_invested',0)}€, Cash: {data.get('cash',0)}€")
    else:
        print("Créer state/stock_watch/portfolio.json avec :")
        print('{"holdings": [{"ticker":"MC","name":"LVMH","quantity":5,"avg_price":750}], "total_invested":3750, "cash":5000}')


def cmd_clean_cache():
    """Nettoie le cache news des entrées vides et >7 jours."""
    if not NEWS_CACHE.exists():
        print("✅ Cache déjà propre (fichier inexistant)")
        return
    try:
        cache = json.load(open(NEWS_CACHE))
        cutoff = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        before = len(cache)
        cache = {k: v for k, v in cache.items()
                 if v and any(n.get("title", "").strip() for n in v)
                 and k.split("_")[-1] >= cutoff}
        after = len(cache)
        with open(NEWS_CACHE, "w") as f:
            json.dump(cache, f, indent=2)
        print(f"🗑️ Cache nettoyé: {before} → {after} entrées")
    except (json.JSONDecodeError, IOError) as e:
        print(f"❌ Erreur: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd in ("--scan", "--us-pulse"): cmd_scan()
        elif cmd in ("--summary", "--report"): cmd_summary()
        elif cmd == "--init": cmd_init()
        elif cmd == "--test": cmd_test()
        elif cmd == "--portfolio": cmd_portfolio()
        elif cmd == "--clean-cache": cmd_clean_cache()
        else: print(f"Usage: {sys.argv[0]} [--scan|--summary|--init|--test|--portfolio|--clean-cache]")
    else:
        cmd_scan()
