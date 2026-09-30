"Validateur: fraicheur des donnees + DATA UNAVAILABLE si trop ancien."
from datetime import datetime, timezone, timedelta
from .config import load_config

def _parse_period(published_date):
    """Accepte YYYY-MM-DD, YYYY-MM et YYYY (formats Eurostat).
    Retourne la date de FIN de periode, ou None si illisible.
    BUG CORRIGE (2026-09-26) : datetime.fromisoformat() rejette '2025-12',
    ce qui renvoyait age=9999 et marquait TOUTE donnee Eurostat
    (periodes mensuelles) comme DATA UNAVAILABLE."""
    s = (published_date or "").strip()
    if not s:
        return None
    try:
        if len(s) == 4 and s.isdigit():            # YYYY
            return datetime(int(s), 12, 31, tzinfo=timezone.utc)
        if len(s) == 7 and s[4] == "-":            # YYYY-MM
            y, m = int(s[:4]), int(s[5:7])
            nxt = (datetime(y + 1, 1, 1, tzinfo=timezone.utc) if m == 12
                   else datetime(y, m + 1, 1, tzinfo=timezone.utc))
            return nxt - timedelta(days=1)
        dt = datetime.fromisoformat(s)             # YYYY-MM-DD
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _age_days(published_date):
    dt = _parse_period(published_date)
    if dt is None:
        return 9999
    return (datetime.now(timezone.utc) - dt).days

def validate(points):
    """Verifie la fraicheur.

    Option A (2026-09-26) : les points marques extra["reference"]=True (seed /
    baseline de reference) ne sont plus declares DATA UNAVAILABLE. Ils restent
    utilisables et portent un badge de fraicheur explicite dans extra.
    Seuls les points live trop vieux sont invalides.
    """
    cfg = load_config()
    fresh = cfg["freshness"]
    out = []
    for p in points:
        maxage = fresh.get(p.category, 60)
        days = _age_days(p.published_date)
        is_ref = bool(p.extra.get("reference"))
        p.extra["age_days"] = days
        p.extra["max_age_days"] = maxage

        if is_ref:
            # Baseline de reference : jamais invalidee, mais signalee si perimee.
            p.available = True
            if days > maxage:
                p.extra["freshness"] = "reference_perimee"
                p.extra["freshness_note"] = ("REFERENCE PERIMEE (age " + str(days)
                                             + "j > max " + str(maxage) + "j)")
            else:
                p.extra["freshness"] = "reference"
                p.extra["freshness_note"] = "REFERENCE (age " + str(days) + "j)"
        elif (p.extra.get("source_tier") in ("official", "market")
              and p.extra.get("latest_available")):
            # Sources officielles (Eurostat / BCE) : un point qui est LA DERNIERE
            # PERIODE PUBLIEE n'est pas "perime", il est simplement le plus recent
            # qui existe. La periode est toujours affichee dans le rapport.
            # Plafond dur conserve pour empecher toute derive silencieuse.
            ceiling = fresh.get("official_max_age_days", 550)
            tier = p.extra.get("source_tier")
            tlabel = {"official": "OFFICIEL", "market": "MARCHE"}.get(tier, "SOURCE")
            if days <= ceiling:
                p.available = True
                p.extra["freshness"] = str(tier) + "_latest"
                p.extra["freshness_note"] = (tlabel + ", DERNIERE DONNEE PUBLIEE (age "
                                             + str(days) + "j, plafond " + str(ceiling) + "j)")
            else:
                p.available = False
                p.raw = ("DATA UNAVAILABLE (officiel trop ancien: age " + str(days)
                         + "j > plafond " + str(ceiling) + "j)")
                p.value = None
                p.extra["freshness"] = "unavailable"
                p.extra["freshness_note"] = "OFFICIEL AU-DELA DU PLAFOND DUR"
        else:
            if days > maxage:
                p.available = False
                p.raw = "DATA UNAVAILABLE (age "+str(days)+"j > max "+str(maxage)+"j)"
                p.value = None
                p.extra["freshness"] = "unavailable"
                p.extra["freshness_note"] = "LIVE PERIME (age " + str(days) + "j)"
            else:
                p.extra["freshness"] = "live"
                p.extra["freshness_note"] = "LIVE (age " + str(days) + "j)"
        out.append(p)
    return out