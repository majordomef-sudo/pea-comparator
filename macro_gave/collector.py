"Orchestrateur de collecte: tente le live (Eurostat, BCE), retombe sur seed, ecrit en DB."
from .models import DataPoint
from . import db
from .collectors import (seed as seed_col, inflation as inf_col, ecb as ecb_col,
                         energy as energy_col, sentiment as sent_col,
                         oecd as oecd_col)

def run_collect_all(use_seed=True, use_live=True):
    pts = []
    live_map = {}
    if use_seed:
        pts += seed_col.collect_seed().points
    if use_live:
        for res in (inf_col.collect(), ecb_col.collect_bce(),
                    energy_col.collect_brent(), energy_col.collect_ttf(),
                    sent_col.collect_esi(), oecd_col.collect_cli()):
            for p in res.points:
                live_map[(p.category, p.indicator)] = p
    # merge : live remplace seed (meme cle categorie/indicateur)
    final = []
    seen = set()
    for p in pts:
        key = (p.category, p.indicator)
        if key in live_map or key in seen:
            continue
        final.append(p); seen.add(key)
    for key, lp in live_map.items():
        if key in seen:
            continue
        final.append(lp); seen.add(key)
    # ecrire en base
    for p in final:
        db.insert_indicator(p.category, p.indicator, p.value, p.previous,
                            p.unit, p.source, p.published_date, p.extra)
    return final