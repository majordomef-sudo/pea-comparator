"""Collector BCE - API Data Portal (SDMX-JSON), sans cle.

CORRIGE le 2026-09-26 : l'ancienne URL SDMX renvoyait HTTP 400 (cle de serie
malformee) et ne produisait aucun point, donc le taux de depot dependait du seed.
URL validee : FM/D.U2.EUR.4F.KR.DFR.LEV (facilite de depot) et ...MRR_FR.LEV (refi).
"""
import json, urllib.request
from ..models import DataPoint, CollectorResult

SDMX = "https://data-api.ecb.europa.eu/service/data/FM/"
SERIES = {
    "taux_depot": "D.U2.EUR.4F.KR.DFR.LEV",
    "taux_refinancement": "D.U2.EUR.4F.KR.MRR_FR.LEV",
}
LABELS = {"taux_depot": "BCE Data Portal (DFR)",
          "taux_refinancement": "BCE Data Portal (MRO)"}


def _get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=25) as fp:
        return json.loads(fp.read())


def _parse_sdmx(raw):
    """Retourne (valeur, periode) de la derniere observation."""
    series = raw["dataSets"][0]["series"]
    sid = next(iter(series))
    obs = series[sid]["observations"]
    last = max(int(k) for k in obs.keys())
    value = round(float(obs[str(last)][0]), 2)
    periods = (raw.get("structure", {}).get("dimensions", {})
               .get("observation", [{}])[0].get("values") or [])
    period = periods[last].get("id") if last < len(periods) else None
    return value, period


def collect_bce():
    """Taux de depot + refinancement BCE (live)."""
    pts, errs = [], []
    for key, serie in SERIES.items():
        url = SDMX + serie + "?lastNObservations=2&format=jsondata"
        try:
            raw = _get(url)
            val, period = _parse_sdmx(raw)
            if val is None:
                errs.append("BCE " + key + ": aucune observation")
                continue
            pts.append(DataPoint("bce", key, val, None, "%",
                                 LABELS.get(key, "BCE"), period or "",
                                 {"source_tier": "official", "latest_available": True}))
        except Exception as e:
            errs.append("BCE " + key + ": " + str(e))
    return CollectorResult(pts, errs, "BCE")


def collect_rates_from_seed(sd):
    pts = []
    for k in ("taux_depot", "taux_refinancement"):
        it = sd.get("bce", {}).get(k)
        if it:
            pts.append(DataPoint("bce", k, it.get("value"), None, it.get("unit", ""),
                                 "ECB", it.get("published", ""),
                                 {"source_note": "manual/seed"}))
    return pts
