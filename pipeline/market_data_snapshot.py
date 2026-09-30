#!/usr/bin/env python3
"""
market_data_snapshot.py — Snapshot de données de marché RÉELLES et sourcées.

But : fournir au pipeline vidéo des chiffres vérifiables (Yahoo Finance +
Eurostat + base ETF PEA), afin que les scripts puissent citer de vraies
statistiques au lieu d'en inventer — et que le fact-check les accepte.

Sources (toutes testées OK le 2026-09-26) :
  - Yahoo Finance chart API (indices, matières premières, crypto, FX)
  - Eurostat dissemination API (HICP inflation, PIB)
  - web/pea-comparator/etf-data.min.js (437 ETF PEA : frais, perfs)

Usage :
    python3 -m pipeline.market_data_snapshot            # utilise le cache (TTL 12h)
    python3 -m pipeline.market_data_snapshot --force     # force le rafraîchissement
    python3 -m pipeline.market_data_snapshot --block     # affiche le bloc prompt

Fallback : si une source tombe, on réutilise la valeur cachée (marquée stale).
Si aucune donnée n'est disponible, le bloc prompt est vide et le pipeline
retombe sur son comportement actuel (chiffres autorisés limités).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import requests

PIPELINE_DIR = Path(__file__).parent.resolve()
WORKSPACE_DIR = PIPELINE_DIR.parent

SNAPSHOT_FILE = PIPELINE_DIR / "data" / "market_snapshot.json"
ETF_DATA_FILE = WORKSPACE_DIR / "web" / "pea-comparator" / "etf-data.min.js"

CACHE_TTL = timedelta(hours=12)
HTTP_TIMEOUT = 25
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"

# ─── Univers suivi ────────────────────────────────────────────────
# Jeu volontairement REDUIT : Yahoo rate-limite (429) sur des appels
# rapproches. 5 symboles espaces de 15s passent sans probleme.
EQUITIES = {
    "CAC 40": "^FCHI",
    "S&P 500": "^GSPC",
    "MSCI World": "URTH",
}
COMMODITIES = {"Or": "GC=F", "Brent": "BZ=F"}

EUROSTAT_HICP = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "prc_hicp_manr?geo=EA20&unit=RCH_A&coicop=CP00&format=JSON"
)
EUROSTAT_GDP = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
    "namq_10_gdp?geo=EA19&na_item=B1GQ&s_adj=SCA&unit=CLV_PCH_SM&format=JSON"
)

# Taux de depot BCE (facilite de depot) - API Data Portal, sans cle.
ECB_DEPOSIT_RATE = (
    "https://data-api.ecb.europa.eu/service/data/"
    "FM/D.U2.EUR.4F.KR.DFR.LEV?lastNObservations=1&format=jsondata"
)


# ─── Helpers ──────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _pct(new: float, old: float) -> Optional[float]:
    if not old:
        return None
    return (new / old - 1.0) * 100.0


def _close_on_or_before(ts: list, cl: list, target_epoch: float) -> Optional[tuple]:
    """Dernier point (timestamp, close) antérieur ou égal à target_epoch."""
    best = None
    for t, c in zip(ts, cl):
        if c is None:
            continue
        if t <= target_epoch:
            best = (t, c)
        else:
            break
    return best


def _fetch_json(url: str, timeout: int = HTTP_TIMEOUT) -> Any:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout)
    r.raise_for_status()
    return r.json()


# ─── Yahoo Finance ────────────────────────────────────────────────

YAHOO_HOSTS = ("query1.finance.yahoo.com", "query2.finance.yahoo.com")
YAHOO_MIN_INTERVAL = 15.0  # secondes entre deux appels (Yahoo 429 agressif)
_last_yahoo_call = [0.0]


def _yahoo_throttle() -> None:
    elapsed = time.time() - _last_yahoo_call[0]
    if elapsed < YAHOO_MIN_INTERVAL:
        time.sleep(YAHOO_MIN_INTERVAL - elapsed)
    _last_yahoo_call[0] = time.time()


def fetch_yahoo_series(symbol: str, attempts: int = 2) -> Optional[dict]:
    """Récupère 30 ans mensuels et calcule les performances clés.

    Throttle + retry avec backoff (Yahoo renvoie 429 sur des appels rapprochés)
    et alternance query1/query2.
    """
    result = None
    for attempt in range(attempts):
        host = YAHOO_HOSTS[attempt % len(YAHOO_HOSTS)]
        url = (
            f"https://{host}/v8/finance/chart/{symbol}"
            "?range=30y&interval=1mo"
        )
        _yahoo_throttle()
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=HTTP_TIMEOUT)
            if r.status_code == 429:
                wait = float(r.headers.get("Retry-After") or (2 * (attempt + 1)))
                wait = min(wait, 6.0)
                print(f"[SNAPSHOT] Yahoo 429 {symbol}, pause {wait:.0f}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            data = r.json()
            result = data["chart"]["result"][0]
            break
        except Exception as exc:  # noqa: BLE001
            print(f"[SNAPSHOT] Yahoo KO {symbol} (essai {attempt+1}/{attempts}): {exc}")
            time.sleep(1.5 * (attempt + 1))
    if result is None:
        print(f"[SNAPSHOT] Yahoo abandon {symbol}")
        return None

    ts = result.get("timestamp") or []
    try:
        cl = result["indicators"]["quote"][0]["close"]
    except Exception:  # noqa: BLE001
        return None
    if not ts or not cl:
        return None

    pairs = [(t, c) for t, c in zip(ts, cl) if c is not None]
    if len(pairs) < 13:
        return None

    last_t, last_c = pairs[-1]
    now_epoch = last_t

    out: dict[str, Any] = {
        "last_close": round(last_c, 2),
        "last_date": datetime.fromtimestamp(last_t, timezone.utc).strftime("%Y-%m-%d"),
        "first_date": datetime.fromtimestamp(pairs[0][0], timezone.utc).strftime("%Y-%m-%d"),
        "years_of_history": round((last_t - pairs[0][0]) / (365.25 * 86400), 1),
    }

    for label, days in (("perf_1y", 365), ("perf_5y", 365 * 5), ("perf_10y", 365 * 10)):
        ref = _close_on_or_before([p[0] for p in pairs], [p[1] for p in pairs],
                                  now_epoch - days * 86400)
        if ref:
            out[label] = round(_pct(last_c, ref[1]), 1)

    # Performance sur toute l'historique disponible
    out["perf_full"] = round(_pct(last_c, pairs[0][1]), 1)
    out["perf_full_from_year"] = datetime.fromtimestamp(
        pairs[0][0], timezone.utc
    ).year

    # CAGR 10 ans
    ref10 = _close_on_or_before([p[0] for p in pairs], [p[1] for p in pairs],
                                now_epoch - 365 * 10 * 86400)
    if ref10 and ref10[1] > 0:
        yrs = (last_t - ref10[0]) / (365.25 * 86400)
        if yrs > 0:
            out["cagr_10y"] = round(((last_c / ref10[1]) ** (1 / yrs) - 1) * 100, 1)

    return out


# ─── Eurostat ─────────────────────────────────────────────────────

def fetch_eurostat_latest(url: str) -> Optional[dict]:
    """Dernière valeur d'une série Eurostat (JSON-stat simplifié)."""
    try:
        data = _fetch_json(url)
        values = data.get("value") or {}
        times = (data.get("dimension", {}).get("time", {}).get("category", {})
                 .get("index") or {})
        if not values or not times:
            return None
        inv = {idx: label for label, idx in times.items()}
        last_idx = max(int(k) for k in values.keys())
        periods = sorted(inv.keys(), reverse=True)
        period = inv.get(last_idx) or (periods[0] if periods else None)
        return {"value": round(float(values[str(last_idx)]), 2), "period": period}
    except Exception as exc:  # noqa: BLE001
        print(f"[SNAPSHOT] Eurostat KO: {exc}")
        return None


def fetch_ecb_deposit_rate() -> Optional[dict]:
    """Taux de depot BCE (SDMX-JSON). API publique, sans cle."""
    try:
        data = _fetch_json(ECB_DEPOSIT_RATE)
        series = data["dataSets"][0]["series"]
        sid = next(iter(series))
        obs = series[sid]["observations"]
        last_key = max(int(k) for k in obs.keys())
        value = round(float(obs[str(last_key)][0]), 2)
        periods = (data.get("structure", {}).get("dimensions", {})
                   .get("observation", [{}])[0].get("values") or [])
        period = periods[last_key].get("id") if last_key < len(periods) else None
        return {"value": value, "period": period}
    except Exception as exc:  # noqa: BLE001
        print(f"[SNAPSHOT] ECB KO: {exc}")
        return None

# ─── Base ETF PEA ─────────────────────────────────────────────────

def fetch_etf_stats() -> Optional[dict]:
    """Statistiques sur les frais de la base ETF PEA."""
    try:
        src = ETF_DATA_FILE.read_text(encoding="utf-8", errors="ignore")
        marker = "const ETF_DATA ="
        pos = src.index(marker) + len(marker)
        while src[pos] in " \n\r\t":
            pos += 1
        arr, _ = json.JSONDecoder().raw_decode(src[pos:])
    except Exception as exc:  # noqa: BLE001
        print(f"[SNAPSHOT] ETF base KO: {exc}")
        return None

    fees = []
    for etf in arr:
        raw = str(etf.get("frais", "")).strip()
        m = re.match(r"^([0-9]+(?:[.,][0-9]+)?)\s*%?$", raw)
        if m:
            fees.append((float(m.group(1).replace(",", ".")), etf.get("nom", "")))

    if not fees:
        return None

    fees.sort()
    vals = [f for f, _ in fees]
    n = len(vals)
    median = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
    return {
        "count_total": len(arr),
        "count_with_fees": n,
        "avg_fee": round(sum(vals) / n, 2),
        "median_fee": round(median, 2),
        "min_fee": round(vals[0], 2),
        "min_fee_name": fees[0][1].strip('“”"')[:70],
        "max_fee": round(vals[-1], 2),
        "count_under_030": sum(1 for v in vals if v <= 0.30),
        "count_under_020": sum(1 for v in vals if v <= 0.20),
    }


# ─── Construction du snapshot ─────────────────────────────────────

def build_snapshot(use_cache: bool = True) -> dict:
    cached: dict = {}
    if SNAPSHOT_FILE.exists():
        try:
            cached = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            cached = {}

    if use_cache:
        built = cached.get("built_at")
        if built:
            try:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(built)
                if age < CACHE_TTL:
                    print(f"[SNAPSHOT] Cache valide ({age.total_seconds()/3600:.1f}h)")
                    return cached
            except Exception:  # noqa: BLE001
                pass

    print("[SNAPSHOT] Collecte des données réelles...")
    prev = cached.get("data", {})
    snap: dict[str, Any] = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "as_of": _today(),
        "sources": {
            "market": "Yahoo Finance (chart API)",
            "macro": "Eurostat (HICP zone euro, PIB zone euro)",
            "etf": "Base ETF PEA Alfred (web/pea-comparator)",
        },
        "data": {},
        "stale": [],
    }

    # Marchés (avec coupe-circuit : Yahoo 429 = on n'insiste pas 5 fois)
    markets: dict[str, Any] = {}
    consecutive_failures = 0
    _skip_market = os.environ.get("SNAPSHOT_SKIP_YAHOO") == "1"
    for label, sym in {**EQUITIES, **COMMODITIES}.items():
        if _skip_market:
            if label in prev.get("markets", {}):
                markets[label] = prev["markets"][label]
            snap["stale"].append(f"market:{label}:skip")
            continue
        if consecutive_failures >= 2:
            snap["stale"].append(f"market:{label}:skip")
            print(f"[SNAPSHOT] Coupe-circuit Yahoo, {label} ignoré")
            if label in prev.get("markets", {}):
                markets[label] = prev["markets"][label]
            continue
        series = fetch_yahoo_series(sym)
        if series:
            consecutive_failures = 0
            series["symbol"] = sym
            markets[label] = series
        else:
            consecutive_failures += 1
            if label in prev.get("markets", {}):
                markets[label] = prev["markets"][label]
                snap["stale"].append(f"market:{label}")
    if markets:
        snap["data"]["markets"] = markets

    # Macro
    macro: dict[str, Any] = {}
    hicp = fetch_eurostat_latest(EUROSTAT_HICP)
    if hicp:
        macro["inflation_zone_euro"] = hicp
    elif "inflation_zone_euro" in prev.get("macro", {}):
        macro["inflation_zone_euro"] = prev["macro"]["inflation_zone_euro"]
        snap["stale"].append("macro:inflation")
    gdp = fetch_eurostat_latest(EUROSTAT_GDP)
    if gdp:
        macro["croissance_pib_zone_euro"] = gdp
    elif "croissance_pib_zone_euro" in prev.get("macro", {}):
        macro["croissance_pib_zone_euro"] = prev["macro"]["croissance_pib_zone_euro"]
        snap["stale"].append("macro:gdp")
    rate = fetch_ecb_deposit_rate()
    if rate:
        macro["taux_depot_bce"] = rate
    elif "taux_depot_bce" in prev.get("macro", {}):
        macro["taux_depot_bce"] = prev["macro"]["taux_depot_bce"]
        snap["stale"].append("macro:rate")
    if macro:
        snap["data"]["macro"] = macro

    # ETF
    etf = fetch_etf_stats()
    if etf:
        snap["data"]["etf"] = etf
    elif "etf" in prev:
        snap["data"]["etf"] = prev["etf"]
        snap["stale"].append("etf")

    snap["ok"] = bool(snap["data"])

    SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_FILE.write_text(
        json.dumps(snap, indent=1, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[SNAPSHOT] Écrit: {SNAPSHOT_FILE}")
    return snap


# ─── Bloc prompt ──────────────────────────────────────────────────

def build_prompt_block(snap: Optional[dict] = None) -> str:
    """Bloc texte compact, chaque chiffre daté et sourcé."""
    if snap is None:
        snap = build_snapshot(use_cache=True)
    data = snap.get("data") or {}
    if not data:
        return ""

    lines: list[str] = []
    lines.append("=== DONNÉES RÉELLES VÉRIFIÉES (source officielle, datées) ===")
    lines.append(
        "Ces chiffres sont RÉELS et déjà vérifiés. Ce sont les SEULS chiffres "
        "que tu peux citer comme des faits."
    )

    markets = data.get("markets") or {}
    if markets:
        lines.append("")
        lines.append("Marchés (cours au " + snap.get("as_of", "?") + ") :")
        for label, s in markets.items():
            bits = []
            if s.get("perf_full") is not None:
                bits.append(
                    f"x{s['perf_full']:+.1f}% depuis {s.get('perf_full_from_year', '?')}"
                )
            if s.get("perf_10y") is not None:
                bits.append(f"{s['perf_10y']:+.1f}% sur 10 ans")
            if s.get("cagr_10y") is not None:
                bits.append(f"soit {s['cagr_10y']:+.1f}%/an sur 10 ans")
            if s.get("perf_1y") is not None:
                bits.append(f"{s['perf_1y']:+.1f}% sur 1 an")
            if bits:
                lines.append(f"  - {label} : " + " | ".join(bits))

    macro = data.get("macro") or {}
    if macro:
        lines.append("")
        lines.append("Macro (Eurostat) :")
        infl = macro.get("inflation_zone_euro")
        if infl:
            lines.append(
                f"  - Inflation zone euro : {infl['value']}% "
                f"(glissement annuel, période {infl['period']})"
            )
        gdp = macro.get("croissance_pib_zone_euro")
        if gdp:
            lines.append(
                f"  - Croissance PIB zone euro : {gdp['value']}% "
                f"(variation trimestrielle, période {gdp['period']})"
            )
        rate = macro.get("taux_depot_bce")
        if rate:
            lines.append(
                f"  - Taux de dépôt BCE : {rate['value']}% (en vigueur {rate['period']})"
            )

    etf = data.get("etf") or {}
    if etf:
        lines.append("")
        lines.append(f"Frais des ETF PEA (base de {etf['count_total']} ETF) :")
        lines.append(
            f"  - Frais moyen : {etf['avg_fee']}% | médian : {etf['median_fee']}% "
            f"| le moins cher : {etf['min_fee']}% ({etf['min_fee_name']})"
        )
        lines.append(
            f"  - {etf['count_under_020']} ETF sous 0,20% de frais, "
            f"{etf['count_under_030']} sous 0,30%"
        )

    stale = snap.get("stale") or []
    if stale:
        lines.append("")
        lines.append(
            "ATTENTION : sources en échec ce jour (" + ", ".join(stale)
            + ") — valeurs potentiellement anciennes, ne pas citer comme du jour."
        )

    lines.append("")
    lines.append(
        "RÈGLE : si un chiffre n'apparaît PAS dans cette liste, tu ne peux pas "
        "le citer comme un fait. Tu peux toujours utiliser : une année, une durée, "
        "un montant présenté comme exemple hypothétique, ou un calcul arithmétique "
        "exact que tu poses toi-même."
    )
    return "\n".join(lines)


def main() -> int:
    force = "--force" in sys.argv
    snap = build_snapshot(use_cache=not force)
    if "--block" in sys.argv:
        print()
        print(build_prompt_block(snap))
    else:
        print(f"ok={snap.get('ok')} stale={snap.get('stale')}")
        for k, v in (snap.get("data") or {}).items():
            print(f"  {k}: {len(v)} entrées")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

