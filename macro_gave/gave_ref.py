"""tReference Gave : moyenne mobile 7 ans (cycle long).
Classe croissance/inflation haut/bas par rapport a leur tendance de cycle,
pas par des seuils absolus."""
import json, statistics, urllib.request

CYCLE_MONTHS = 84
CYCLE_QUARTERS = 28

def _fetch(url, timeout=35):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as fp:
        return json.loads(fp.read())

def _decode(raw):
    dims = raw["dimension"]; order = raw["id"]
    sizes = [len(dims[o]["category"]["index"]) for o in order]
    out = {}
    for k, v in raw.get("value", {}).items():
        pos = int(k); rem = pos; codes = []
        for o, sz in zip(order, sizes):
            idx = rem % sz; rem //= sz
            c = dims[o]["category"]["index"]
            codes.append([cd for cd, pi in c.items() if int(pi) == idx][0])
        d = dict(zip(order, codes))
        out[d.get("time")] = v
    return out

def _mean_last(vals, n):
    pts = sorted(vals.items())
    nums = [v for _, v in pts[-n:] if v is not None]
    return statistics.mean(nums) if nums else None

# --- Source inflation (corrige le 2026-09-27) -------------------------------
# prc_hicp_manr (ECOICOP v1) est FIGE au 2025-12 depuis le changement
# methodologique Eurostat du 04/02/2026 : le dataset n'est plus alimente.
# Le remplacant est prc_hicp_minr (ECOICOP v2), alimente jusqu'au mois courant
# (verifie 2026-09-27 : derniere donnee 2026-08, mise a jour 2026-09-17).
# Le poste global s'appelle desormais coicop18=TOTAL (l'ancien CP00 disparait).
EUROSTAT_INFLATION_V2 = ("https://ec.europa.eu/eurostat/api/dissemination/"
                         "statistics/1.0/data/prc_hicp_minr?geo=EA20&unit=RCH_A"
                         "&coicop18=TOTAL&format=JSON")
EUROSTAT_INFLATION_V1 = ("https://ec.europa.eu/eurostat/api/dissemination/"
                         "statistics/1.0/data/prc_hicp_manr?geo=EA20&unit=RCH_A"
                         "&coicop=CP00&format=JSON")


def inflation_history():
    """Serie inflation zone euro : ECOICOP v2 en priorite, v1 en repli.

    Le repli v1 est volontairement CONSERVE mais il ne sert que si la v2 tombe :
    si on y retombe en silence, on repart sur une serie figee 9 mois plus tot.
    On ne l'accepte donc que si elle apporte au moins une donnee 2026.
    """
    try:
        v2 = _decode(_fetch(EUROSTAT_INFLATION_V2))
        if v2 and max(v2.keys()) >= "2026-01":
            return v2
    except Exception:
        pass
    return _decode(_fetch(EUROSTAT_INFLATION_V1))

def growth_history():
    url = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/" + "namq_10_gdp?geo=EA20&na_item=B1GQ&s_adj=SCA&unit=CLV_PCH_SM&format=JSON"
    return _decode(_fetch(url))

def inflation_refs():
    v = inflation_history()
    if not v: return None
    pts = sorted(v.items())
    return {"mean_7y": _mean_last(v, CYCLE_MONTHS), "current": pts[-1][1], "date": pts[-1][0]}

def growth_refs():
    v = growth_history()
    if not v: return None
    pts = sorted(v.items())
    return {"mean_7y": _mean_last(v, CYCLE_QUARTERS), "current": pts[-1][1], "date": pts[-1][0]}

def classify(v, ref, band=0.0):
    """Classe par rapport a la reference de cycle.

    band = zone neutre (dead band) en points de pourcentage. Si |v - ref| <= band,
    on retourne "neutre" : l'ecart est du bruit, pas un signal de changement de regime.
    Sans bande (band=0), comportement historique conserve.
    """
    if v is None or ref is None: return "unknown"
    if band and abs(v - ref) <= band:
        return "neutre"
    return "haut" if v >= ref else "bas"

if __name__ == "__main__":
    i = inflation_refs(); g = growth_refs()
    print("INFLATION:", i, "->", classify(i["current"], i["mean_7y"]))
    print("CROISSANCE:", g, "->", classify(g["current"], g["mean_7y"]))
