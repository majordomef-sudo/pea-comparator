#!/usr/bin/env python3
"""
news_context.py — Moteur de veille événementielle pour alfred_trader
Scanne les news en temps réel, classifie les événements par secteur,
et génère des modificateurs de score (catalyseurs/risques).

Architecture :
1. Sources multiples : Google News RSS, Yahoo Finance Top Stories, Web search
2. Classification NLP simple : patterns de mots-clés → catégories d'événements
3. Mapping événement → secteur → tickers individuels
4. Output : dict {ticker: {impact: -3..+3, reason: str, event_type: str}}

Framework : Gavekal (macro) + Taleb (convexité)
"""
import json
import hashlib
import re
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import xml.etree.ElementTree as ET

import requests

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
STATE_DIR = WORKSPACE / "state" / "stock_watch"
NEWSCACHE_FILE = STATE_DIR / "news_context_cache.json"
NEWS_EVENTS_FILE = STATE_DIR / "news_events.json"

# ─── Durée de vie du cache ────────────────────────────────
CACHE_TTL = timedelta(hours=2)  # On re-scrape toutes les 2h max

# ─── Sources news ─────────────────────────────────────────
NEWS_SOURCES = [
    {
        "name": "google_top",
        "url": "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
        "type": "rss",
    },
    {
        "name": "google_finance",
        "url": "https://news.google.com/rss/search?q=stock+market&hl=en-US&gl=US&ceid=US:en",
        "type": "rss",
    },
    {
        "name": "reuters_investing",
        "url": "https://news.google.com/rss/search?q=investing+market+economy&hl=en-US&gl=US&ceid=US:en",
        "type": "rss",
    },
]

# ─── Classification des événements ────────────────────────
# Pattern matching de titres → catégorie d'événement
EVENT_PATTERNS = [
    # ── Géopolitique / Défense ──
    (r"(war|conflict|invasion|military|troops|attack|missile|drone|sanction|escalation|nato)", "GEOPOLITICS", "defense_aero"),
    (r"(defense|defence|military spending|rearmament|arms|ammunition)", "GEOPOLITICS", "defense_aero"),

    # ── Taux / Fed / BCE ──
    (r"(fed|federal reserve|interest rate|rate cut|rate hike|ecb|central bank|monetary policy)", "MONETARY_POLICY", "finance_assurance"),
    (r"(inflation|cpi|pce|consumer price)", "INFLATION", "finance_assurance"),

    # ── Pétrole / Énergie ──
    (r"(oil price|cude|wti|brent|opec|energy crisis|gas price|natural gas)", "COMMODITY_OIL", "energie_transition"),
    (r"(renewable|wind|solar|green energy|hydrogen|energy transition)", "ENERGY_TRANSITION", "energie_transition"),

    # ── Semi-conducteurs / Tech ──
    (r"(semiconductor|chip|nvda|ai chip|hbm|tsmc|wafer|euv|machine learning)", "TECH_SEMI", "semiconducteurs_AI"),
    (r"(artificial intelligence|ai|llm|large language model|data center|cloud)", "TECH_AI", "software_AI"),
    (r"(quantum|cyber|cybersecurity|hack|data breach)", "TECH_CYBER", "software_AI"),

    # ── Luxe / Consommation ──
    (r"(luxury|china demand|spending|consumer|retail sales)", "CONSUMPTION", "luxe_consommation"),

    # ── Pharma / Santé ──
    (r"(drug approval|fda|pharma|biotech|obesity|wegovy|ozempic|cancer)", "HEALTHCARE", "pharma_sante"),
    (r"(pandemic|virus|outbreak|vaccine|covid)", "HEALTH_CRISIS", "pharma_sante"),

    # ── Industrie ──
    (r"(manufacturing|industrial|factory|supply chain|infrastructure)", "INDUSTRY", "industrie_equipement"),

    # ── Finance ──
    (r"(bank|banking|financial|crisis|credit|loan|default|bailout)", "FINANCE", "finance_assurance"),

    # ── Macro général ──
    (r"(recession|gdp|economic growth|slowdown|employment|jobs report|unemployment)", "MACRO", None),
    (r"(trade war|tariff|import|export|china tariff)", "TRADE", None),

    # ── Or / Devises ──
    (r"(gold price|gold record|safe haven|precious metal)", "COMMODITY_GOLD", None),
    (r"(dollar|eurusd|currency|fx)", "FX", None),
]

# ─── Impact mapping : type d'événement → secteur → direction ──
# Chaque événement a : {sector: impact_score} où impact_score = -3..+3
EVENT_IMPACT_MAP = {
    "GEOPOLITICS": {
        "defense_aero": 3,      # guerre → défense 🚀
        "energie_transition": 1, # pétrole/gaz monte
        "luxe_consommation": -1, # incertitude → baisse conso
        "semiconducteurs_AI": -1,
        "industrie_equipement": -1,
    },
    "MONETARY_POLICY": {
        "finance_assurance": 1,  # taux hauts → banques gagnent
        "pharma_sante": -1,      # coût du capital
    },
    "INFLATION": {
        "energie_transition": 1,  # hedge inflation
        "luxe_consommation": -1,  # consommation freinée
    },
    "COMMODITY_OIL": {
        "energie_transition": 2,  # pétrole monte = Total/Shell/BP 🚀
        "industrie_equipement": -1, # coût énergie pour industrie
        "luxe_consommation": -1,
    },
    "ENERGY_TRANSITION": {
        "energie_transition": 2,  # ENR, NEX, VWS bénéficient
        "industrie_equipement": 1, # électrification
    },
    "TECH_SEMI": {
        "semiconducteurs_AI": 2,  # ASML, NVDA, etc.
        "midcaps_croissance": 1,
    },
    "TECH_AI": {
        "software_AI": 2,         # SAP, DSY, CAP, etc.
        "semiconducteurs_AI": 1,  # toutes les puces bénéficient
        "midcaps_croissance": 1,
    },
    "HEALTHCARE": {
        "pharma_sante": 2,
    },
    "HEALTH_CRISIS": {
        "pharma_sante": 2,
        "luxe_consommation": -2,
        "industrie_equipement": -1,
    },
    "FINANCE": {
        "finance_assurance": -2,  # crise bancaire → banques baissent
    },
    "CONSUMPTION": {
        "luxe_consommation": 1,   # bonne consommation → luxe monte
    },
    "INDUSTRY": {
        "industrie_equipement": 1,
    },
    "RECESSION": {
        "luxe_consommation": -2,
        "industrie_equipement": -2,
        "pharma_sante": -1,
    },
    "TRADE": {
        "semiconducteurs_AI": -1,
        "energie_transition": -1,
    },
    "MACRO": {},  # Neutre par défaut
    "FX": {},
    "COMMODITY_GOLD": {},  # Neutre, or = refug
}

# ─── Ticker → secteur mapping (importé depuis watchlist) ──
# Construit automatiquement au load

_TICKER_SECTOR_MAP = None


def _build_ticker_map():
    """Construit le mapping ticker → secteur depuis la watchlist."""
    global _TICKER_SECTOR_MAP
    wl_path = STATE_DIR / "watchlist.json"
    if wl_path.exists():
        try:
            wl = json.loads(wl_path.read_text())
            mapping = {}
            for sector_key, sector_data in wl.get("sectors", {}).items():
                for stock in sector_data.get("stocks", []):
                    mapping[stock["ticker"]] = sector_key
            _TICKER_SECTOR_MAP = mapping
            return mapping
        except Exception:
            pass
    _TICKER_SECTOR_MAP = {}
    return {}


def get_ticker_sector(ticker: str) -> Optional[str]:
    """Retourne le secteur d'un ticker."""
    if _TICKER_SECTOR_MAP is None:
        _build_ticker_map()
    return _TICKER_SECTOR_MAP.get(ticker)


# ═══════════════════════════════════════════════════════════
# 1. SCRAPER NEWS
# ═══════════════════════════════════════════════════════════

def fetch_raw_news(force: bool = False) -> list:
    """Récupère les news depuis les sources RSS.

    Respecte le cache : si le cache est récent (< CACHE_TTL), on
    évite de rescrapper pour pas se faire ban.
    """
    now = datetime.now()

    # Vérifier le cache
    if not force and NEWSCACHE_FILE.exists():
        try:
            cached = json.loads(NEWSCACHE_FILE.read_text())
            cached_time = datetime.fromisoformat(cached.get("timestamp", "2000-01-01"))
            if now - cached_time < CACHE_TTL:
                return cached.get("articles", [])
        except Exception:
            pass

    articles = []
    seen = set()

    for source in NEWS_SOURCES:
        try:
            resp = requests.get(source["url"], timeout=10, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            if resp.status_code != 200:
                continue

            if source["type"] == "rss":
                root = ET.fromstring(resp.content)
                # Gérer le namespace RSS
                for item in root.iter("item"):
                    title = item.findtext("title", "").strip()
                    link = item.findtext("link", "").strip()
                    pub_date = item.findtext("pubDate", "")[:25]

                    if not title or len(title) < 15:
                        continue

                    # Déduplication par hash du titre normalisé
                    key = re.sub(r'[^a-z0-9]', '', title.lower())[:40]
                    if key in seen:
                        continue
                    seen.add(key)

                    articles.append({
                        "title": title,
                        "link": link,
                        "source": source["name"],
                        "date": pub_date,
                        "fetched_at": now.isoformat(),
                    })

        except Exception as e:
            pass  # Une source qui plante ne doit pas bloquer le reste

        time.sleep(0.3)  # Politeness delay

    # Sauvegarder le cache
    NEWSCACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    NEWSCACHE_FILE.write_text(json.dumps({
        "timestamp": now.isoformat(),
        "articles": articles[:60],  # On garde max 60 articles
    }, indent=2))

    return articles[:60]


# ═══════════════════════════════════════════════════════════
# 2. CLASSIFICATION DES ÉVÉNEMENTS
# ═══════════════════════════════════════════════════════════

def classify_article(title: str) -> list:
    """Classifie un titre d'article en (catégorie, secteur_cible).

    Retourne une liste de tuples (event_type, sector_key).
    Un article peut correspondre à plusieurs catégories.
    """
    title_lower = title.lower()
    results = []

    for pattern, event_type, default_sector in EVENT_PATTERNS:
        if re.search(pattern, title_lower, re.IGNORECASE):
            results.append((event_type, default_sector))

    return results


def aggregate_events(articles: list) -> dict:
    """Agrège les classifications pour détecter des tendances.

    Retourne :
    {
        "GEOPOLITICS": {
            "count": 5,
            "sectors_hit": {"defense_aero": 5},
            "recent_titles": [...]
        },
        ...
    }
    """
    events = {}
    for article in articles:
        classifications = classify_article(article["title"])
        for event_type, sector in classifications:
            if event_type not in events:
                events[event_type] = {
                    "count": 0,
                    "sectors_hit": {},
                    "recent_titles": [],
                }
            events[event_type]["count"] += 1
            if sector:
                events[event_type]["sectors_hit"][sector] = \
                    events[event_type]["sectors_hit"].get(sector, 0) + 1
            if len(events[event_type]["recent_titles"]) < 3:
                events[event_type]["recent_titles"].append(article["title"][:120])

    # Sauvegarder les événements détectés
    NEWS_EVENTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    NEWS_EVENTS_FILE.write_text(json.dumps({
        "timestamp": datetime.now().isoformat(),
        "events": events,
    }, indent=2))

    return events


# ═══════════════════════════════════════════════════════════
# 3. GÉNÉRATION DES MODIFICATEURS DE SCORE
# ═══════════════════════════════════════════════════════════

def compute_catalyst_modifiers(events: dict, tickers: list = None) -> dict:
    """Calcule les modificateurs de score par ticker basés sur les événements.

    Retourne : {ticker: {catalyst: -3..+3, reason: str, event_type: str}}

    - catalyst = impact cumulé de tous les événements affectant ce ticker
    - Compris entre -5 et +5 (saturé)
    """
    sector_impacts = {}  # {sector: total_impact}

    for event_type, event_data in events.items():
        impact_map = EVENT_IMPACT_MAP.get(event_type, {})
        count = event_data["count"]

        if count == 0:
            continue

        # L'impact augmente avec le nombre d'articles sur le même sujet
        # mais sature à partir de 5 articles
        strength = min(count / 3, 2.0)  # 3 articles = 1.0, 6+ = 2.0

        for sector, base_impact in impact_map.items():
            if sector not in sector_impacts:
                sector_impacts[sector] = 0.0
            sector_impacts[sector] += base_impact * strength

    # Maintenant mapper secteur → tickers
    if _TICKER_SECTOR_MAP is None:
        _build_ticker_map()

    # Si tickers fourni, ne traiter que ceux-là (optimisation)
    target_tickers = tickers if tickers else list(_TICKER_SECTOR_MAP.keys())

    modifiers = {}
    for ticker in target_tickers:
        sector = _TICKER_SECTOR_MAP.get(ticker)
        if not sector or sector not in sector_impacts:
            continue

        raw_impact = sector_impacts[sector]
        # Saturer entre -5 et +5
        impact = max(-5, min(5, round(raw_impact, 1)))

        if abs(impact) < 0.5:
            continue  # Trop faible pour être significatif

        # Générer une raison lisible
        reason = _generate_reason(events, sector, impact)

        modifiers[ticker] = {
            "catalyst": impact,
            "reason": reason,
            "sector": sector,
        }

    return modifiers


def _generate_reason(events: dict, sector: str, impact: float) -> str:
    """Génère une raison lisible pour un modificateur."""
    direction = "catalyseur haussier" if impact > 0 else "risque baissier"
    parts = []
    for event_type, data in events.items():
        if sector in EVENT_IMPACT_MAP.get(event_type, {}):
            n = data["count"]
            parts.append(f"{event_type} ({n}x)")
            if len(parts) >= 2:
                break

    if parts:
        return f"{direction} : {', '.join(parts)}"
    return f"{direction} : événement sectoriel détecté"


# ═══════════════════════════════════════════════════════════
# 4. INTÉGRATION (appelée depuis alfred_trader.py)
# ═══════════════════════════════════════════════════════════

def get_catalyst_modifiers(tickers: list = None, force_refresh: bool = False) -> dict:
    """Point d'entrée principal.

    1. Récupère les news (cache ou fresh)
    2. Classifie les événements
    3. Calcule les modificateurs

    Utilisation :
        from news_context import get_catalyst_modifiers
        mods = get_catalyst_modifiers()
        # mods["DSY"] = {"catalyst": 1.5, "reason": "catalyseur haussier : TECH_AI (3x)", ...}
    """
    articles = fetch_raw_news(force=force_refresh)
    events = aggregate_events(articles)
    modifiers = compute_catalyst_modifiers(events, tickers=tickers)

    return modifiers


def print_event_summary():
    """Affiche un résumé lisible des événements détectés."""
    articles = fetch_raw_news()
    events = aggregate_events(articles)
    modifiers = compute_catalyst_modifiers(events)

    print("\n🌍 **VEILLE ÉVÉNEMENTIELLE**")
    print("=" * 50)

    if not events:
        print("   Aucun événement majeur détecté.")
        return

    # Afficher les événements
    for event_type, data in sorted(events.items(), key=lambda x: -x[1]["count"]):
        impact_map = EVENT_IMPACT_MAP.get(event_type, {})
        sectors = ", ".join(impact_map.keys()) if impact_map else "général"
        print(f"\n🔸 **{event_type}** ({data['count']} articles)")
        print(f"   Secteurs impactés : {sectors}")
        for t in data["recent_titles"]:
            print(f"   📰 {t}")

    # Afficher les modificateurs les plus forts
    print(f"\n{'='*50}")
    print("📈 **CATALYSEURS PAR ACTION**")
    print("=" * 50)
    sorted_mods = sorted(modifiers.items(), key=lambda x: -abs(x[1]["catalyst"]))
    for ticker, mod in sorted_mods[:10]:
        icon = "🟢" if mod["catalyst"] > 0 else "🔴"
        print(f"  {icon} {ticker} : {mod['catalyst']:+.1f} — {mod['reason']}")


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    if "--refresh" in sys.argv:
        get_catalyst_modifiers(force_refresh=True)
    print_event_summary()
