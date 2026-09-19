#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Controle automatique des donnees ETF (point 7) — usage: python3 validate_etf_data.py
Verifie: checksum ISIN, doublons, champs manquants, N/A sur champs critiques, format frais, coherence SRI."""
import json, re, sys

def isin_ok(isin):
    if not re.match(r'^[A-Z]{2}[A-Z0-9]{9}[0-9]$', isin or ''):
        return False
    digits = ''.join(str(ord(c)-55) if c.isalpha() else c for c in isin[:12])
    rev = digits[::-1]
    total = sum((int(d)*2 - 9) if (i % 2 == 1 and int(d)*2 > 9) else (int(d)*2 if i % 2 == 1 else int(d)) for i, d in enumerate(rev))
    return total % 10 == 0

def load(path):
    src = open(path, encoding='utf-8').read()
    m = re.search(r'\[[\s\S]*\]', src)
    return json.loads(m.group(0))

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else '/var/www/html/etf-data.min.js'
    rows = load(path)
    errs = {'isin_invalide': [], 'doublon': [], 'nom_manquant': [], 'sans_frais': [],
            'sri_incoherent': [], 'emetteur_vide': []}
    seen = {}
    for r in rows:
        i = r.get('isin', '')
        if not isin_ok(i):
            errs['isin_invalide'].append(f"{i} {r.get('nom','')[:45]}")
        if i in seen:
            errs['doublon'].append(i)
        seen[i] = 1
        if not (r.get('nom') or '').strip():
            errs['nom_manquant'].append(i)
        if (r.get('frais') or '') in ('N/A', '', None):
            errs['sans_frais'].append(f"{i} {r.get('nom','')[:45]}")
        sri = r.get('sri')
        if sri not in ('1','2','3','4','5','6','7',None,''):
            errs['sri_incoherent'].append(f"{i} sri={sri}")
        if not (r.get('emetteur') or '').strip():
            errs['emetteur_vide'].append(i)
    print(f"== Validation {path} — {len(rows)} ETF ==")
    for k, v in errs.items():
        print(f"{k}: {len(v)}")
        for x in v[:8]:
            print(f"   - {x}")
    return 0

if __name__ == '__main__':
    sys.exit(main())

