"""Collector Energie - Brent (chaines de sources, best-effort, sans cle API).

Ordre de tentative :
  1. Yahoo Finance (chart API, BZ=F)   -> valeur + close mois precedent + MoM
  2. CNBC quick quote (@LCO.1, ICE Brent front month) -> dernier prix + close J-1
  3. Echec -> le collector remonte l'erreur, le seed prend le relais (collector.py)

Ajout 2026-09-26 : CNBC decouvert comme source de repli fiable alors que Yahoo
throttlait l'IP du VPS (HTTP 429). CNBC ne demande ni cle ni header special et
renvoie aussi le plus haut/bas 52 semaines.
"""
import json, urllib.request
from datetime import datetime, timezone
from ..models import DataPoint, CollectorResult

YAHOO = ("https://query1.finance.yahoo.com/v8/finance/chart/BZ=F"
         "?range=3mo&interval=1d")
CNBC = ("https://quote.cnbc.com/quote-html-webservice/quote.htm"
        "?symbols=@LCO.1&requestMethod=quick&noform=1&partnerId=2"
        "&fund=1&exthrs=1&output=json")

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def _get(url, timeout=12):
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Accept": "application/json,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as fp:
        return json.loads(fp.read())


def _num(v):
    try:
        f = float(v)
        return f if f > 0 else None
    except (TypeError, ValueError):
        return None


def _yahoo_chart(url):
    """Lecture generique d une reponse chart Yahoo -> (dernier, mois prec., date, meta)."""
    raw = _get(url)
    res = (raw.get("chart") or {}).get("result") or []
    if not res:
        raise ValueError("aucune serie")
    r0 = res[0]
    ts = r0.get("timestamp") or []
    closes = ((r0.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    pairs = [(t, c) for t, c in zip(ts, closes) if c is not None]
    if not pairs:
        raise ValueError("aucune valeur close")
    last_t, last_v = pairs[-1]
    last_dt = datetime.fromtimestamp(last_t, tz=timezone.utc)
    prev_v = None
    for t, c in reversed(pairs[:-1]):
        d = datetime.fromtimestamp(t, tz=timezone.utc)
        if (d.year, d.month) != (last_dt.year, last_dt.month):
            prev_v = c
            break
    return float(last_v), prev_v, last_dt, (r0.get("meta") or {})


def _from_yahoo():
    raw = _get(YAHOO)
    res = (raw.get("chart") or {}).get("result") or []
    if not res:
        raise ValueError("aucune serie")
    r0 = res[0]
    ts = r0.get("timestamp") or []
    closes = ((r0.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    pairs = [(t, c) for t, c in zip(ts, closes) if c is not None]
    if not pairs:
        raise ValueError("aucune valeur close")

    last_t, last_v = pairs[-1]
    last_dt = datetime.fromtimestamp(last_t, tz=timezone.utc)
    prev_v = None
    for t, c in reversed(pairs[:-1]):
        d = datetime.fromtimestamp(t, tz=timezone.utc)
        if (d.year, d.month) != (last_dt.year, last_dt.month):
            prev_v = c
            break
    mom = round((last_v - prev_v) / prev_v * 100.0, 2) if prev_v else None
    return DataPoint("energie", "brent", float(last_v), prev_v, "USD/baril",
                     "Yahoo Finance (BZ=F)", last_dt.date().isoformat(),
                     {"mom_pct": mom, "prev_month_close": prev_v,
                      "source_tier": "market", "latest_available": True,
                      "source_note": "Yahoo Finance chart API (BZ=F)"})


def _from_cnbc():
    raw = _get(CNBC, timeout=15)
    qs = ((raw.get("QuickQuoteResult") or {}).get("QuickQuote") or [])
    if not qs:
        raise ValueError("aucune cotation")
    q = qs[0]
    last = _num(q.get("last")) or _num(q.get("settlePrice"))
    if last is None:
        raise ValueError("dernier prix illisible")
    prev = _num(q.get("previous_day_closing"))
    fund = q.get("FundamentalData") or {}
    pub = (q.get("settleDate") or "").strip()
    if not pub:
        lt = (q.get("last_time") or "")[:10]
        pub = lt
    extra = {"prev_close": prev,
             "contract": q.get("name") or "",
             "exchange": q.get("exchange") or "",
             "expiration": q.get("expiration_date") or "",
             "w52_high": _num(fund.get("yrhiprice")),
             "w52_low": _num(fund.get("yrloprice")),
             "source_tier": "market", "latest_available": True,
             "source_note": "CNBC quick quote (@LCO.1)"}
    if prev:
        extra["mom_pct"] = round((last - prev) / prev * 100.0, 2)
    return DataPoint("energie", "brent", float(last), prev, "USD/baril",
                     "CNBC (ICE Brent front month)", pub, extra)


def collect_brent():
    """Brent : Yahoo puis CNBC. Remonte l'erreur si les deux echouent."""
    errs = []
    for name, fn in (("Yahoo", _from_yahoo), ("CNBC", _from_cnbc)):
        try:
            p = fn()
            if errs:
                p.extra["fallback_note"] = "repli apres echec: " + " | ".join(errs)
            return CollectorResult([p], errs, "Brent/" + name)
        except Exception as e:
            errs.append(name + ": " + type(e).__name__ + " " + str(e)[:80])
    return CollectorResult([], errs, "Brent")


# ---------------------------------------------------------------------------
# TTF (gaz naturel europeen, Dutch TTF) - ajoute le 2026-09-26.
#
# Pourquoi : le TTF est le deuxieme signal energetique du module et il etait
# reste en SEED (42 EUR/MWh, source "marches gaz europeens", 2026-08-20). Or le
# TTF est LE prix qui compte pour l industrie et le consommateur europeens -
# plus que le Brent. Le laisser figé alors que le Brent est live etait incoherent.
#
# Source trouvee : Yahoo Finance, symbole TTF=F ("Dutch TTF Natural Gas Calendar",
# EUR, place NYM, type FUTURE). Aucune cle. Le TTF est un contrat calendaire
# (pas de mois unique), d ou le name Yahoo generique.
#
# Pistes ecartees : CNBC (@TTF.1 -> reponse vide, 68 octets). ICE/EEX -> pas d API
# libre. Investing -> bloque.
#
# NUANCE DE FIABILITE : TTF=F chez Yahoo est un future "calendar" dont le
# mecanisme de roulement n est pas documente par Yahoo. On l accepte comme
# indicateur de TENDANCE (et pour le MoM), pas comme une cotation officielle
# au centime. Le badge reste "market" et la source est nommee dans le rapport.
# ---------------------------------------------------------------------------
YAHOO_TTF = ("https://query1.finance.yahoo.com/v8/finance/chart/TTF=F"
             "?range=3mo&interval=1d")


def _ttf_from_yahoo():
    last, prev, last_dt, meta = _yahoo_chart(YAHOO_TTF)
    mom = round((last - prev) / prev * 100.0, 2) if prev else None
    return DataPoint("energie", "ttf", last, prev, "EUR/MWh",
                     "Yahoo Finance (TTF=F)", last_dt.date().isoformat(),
                     {"mom_pct": mom, "prev_month_close": prev,
                      "w52_high": _num(meta.get("fiftyTwoWeekHigh")),
                      "w52_low": _num(meta.get("fiftyTwoWeekLow")),
                      "contract": meta.get("shortName") or "",
                      "exchange": meta.get("exchangeName") or "",
                      "source_tier": "market", "latest_available": True,
                      "source_note": "Yahoo Finance chart API (TTF=F, Dutch TTF calendar future)",
                      "fiabilite": "future calendaire Yahoo, fiable en tendance"})


def collect_ttf():
    """TTF gaz : Yahoo (TTF=F). Le seed prend le relais si echec."""
    errs = []
    try:
        return CollectorResult([_ttf_from_yahoo()], errs, "TTF/Yahoo")
    except Exception as e:
        errs.append("Yahoo TTF: " + type(e).__name__ + " " + str(e)[:80])
    return CollectorResult([], errs, "TTF")
