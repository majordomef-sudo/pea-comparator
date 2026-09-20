# -*- coding: utf-8 -*-
import re, json, os, html as H

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

def load_js_array(path, marker):
    d = open(path, encoding='utf-8').read()
    s = d.find('[', d.find(marker))
    return json.loads(d[s:d.rfind(']')+1])

DATA = load_js_array('etf-data.min.js', 'const ETF_DATA')
SCORES = {}
for x in load_js_array('etf-scores.js', 'window.ETF_SCORES'):
    SCORES[x['isin']] = x
print('ETF:', len(DATA), '| scores:', len(SCORES))

def esc(x):
    return H.escape(str(x), quote=True)

def clean_name(n):
    n = n.replace('“', '').replace('”', '').replace('"', '').strip()
    return n

def val(e, k, fmt=None, deny=('N/A', '?', '')):
    v = e.get(k)
    if v is None:
        return None
    s = str(v).strip()
    if s.lower() in ('n/a', 'nan', 'null', 'none', '?', ''):
        return None
    if fmt and isinstance(v, (int, float)):
        return fmt(v)
    return s

DICO_LAB = {'indice': 'Qualité de l’indice', 'replication': 'Réplication', 'couts': 'Coûts (TER)', 'solidite': 'Solidité du fonds', 'emetteur': 'Émetteur', 'futur': 'Potentiel futur'}

def score_block(sc):
    if not sc:
        return '<p class="disc">Score non disponible pour cet ETF.</p>'
    total = sc.get('total', 0)
    dec = esc(sc.get('decision', '—'))
    rows = ''
    for k, lab in DICO_LAB.items():
        rows += '<tr><td>%s</td><td style="text-align:right">%d/20</td></tr>' % (lab, sc.get('categories', {}).get(k, 0))
    bonus = ''.join('<span class="tag-ok">+ %s</span>' % esc(b) for b in sc.get('bonus', []))
    malus = ''.join('<span class="tag-warn">− %s</span>' % esc(m) for m in sc.get('malus', []))
    return ('<div class="card"><h2>Score Alfred : %d/100 — %s</h2>'
            '<p style="color:#8a9bb0;font-size:.82rem">Score pédagogique indicatif, calculé selon la <a href="/methodologie">méthodologie du Score Alfred</a>. Ni conseil, ni ordre d’achat ou de vente.</p>'
            '<table style="max-width:420px"><tr><th>Critère</th><th>Points</th></tr>%s</table>'
            '<p style="margin-top:10px">%s%s</p></div>') % (total, dec, rows, bonus, malus)

FOOTER = open('bonus-pea.html', encoding='utf-8').read()
i = FOOTER.find('<footer')
j = FOOTER.rfind('</footer>') + len('</footer>')
FOOTER = FOOTER[i:j]

def pct(x):
    if x is None: return None
    return str(x).strip().replace('%', '') + ' %'

TPL_HEAD = '''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="__CANON__">
<meta property="og:type" content="website">
<meta property="og:locale" content="fr_FR">
<meta property="og:site_name" content="Alfred Invest">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:url" content="__CANON__">
<meta name="robots" content="index,follow">
<link rel="stylesheet" href="../../style.css">
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <a href="/" class="logo"><div class="logo-icon">A</div><span>Alfred Invest</span></a>
      <p class="tagline" style="font-size:.8rem;color:#94a3b8">Fiche ETF · Données au 20/09/2026</p>
    </div>
  </header>
  <main class="container" style="padding-top:24px">
    <p style="color:#8a9bb0;font-size:.8rem;margin-bottom:4px"><a href="/">← Retour au comparateur</a> &middot; <a href="/top-etf.html">Top ETF par indice</a></p>
    <h1 style="margin:8px 0 4px">__NAME__ __PEA__</h1>
    <p style="color:#8a9bb0;font-size:.85rem;margin-bottom:16px">Fiche pédagogique · Données au 20/09/2026 · Sources : DICI/PRIIPs, justETF</p>
    <div class="card"><table>__ROWS__</table></div>
    __SCORE__
    <div class="card"><p style="font-size:.8rem;color:#8a9bb0"><strong>Document légal :</strong> consultez le DIC/PRIIPs officiel du fonds avant toute décision. <a href="https://www.justetf.com/fr/etf-profile.html?isin=__ISIN__" target="_blank" rel="noopener">Voir sur justETF ↗</a></p></div>
    <p style="font-size:.75rem;color:#8a9bb0">La performance passée ne préjuge pas des performances futures. Alfred Invest est un site pédagogique : les informations affichées ne constituent pas un conseil en investissement personnalisé.</p>
  </main>
  __FOOTER__
</body>
</html>'''

def gen_etf(e):
    isin = e['isin']
    sc = SCORES.get(isin)
    name = esc(clean_name(e.get('nom', isin)))
    rows = []
    def row(l, v):
        if v is not None:
            rows.append('<tr><th style="width:40%">' + l + '</th><td>' + v + '</td></tr>')
    row('ISIN', esc(isin))
    row('Frais (TER)', esc(pct(val(e, 'frais'))))
    row('SRI (risque)', esc(val(e, 'sri')))
    row('Performance 5 ans', esc(pct(val(e, 'perf5'))))
    row('Volatilite', esc(val(e, 'volatilite')))
    row('Emetteur', esc(val(e, 'emetteur_full') or val(e, 'emetteur')))
    row('Domicile', esc(val(e, 'domicile')))
    row('Indice suivi', esc(val(e, 'indice')))
    enc = val(e, 'encours_mio')
    if enc is not None:
        row('Encours', esc(str(enc) + ' M' + (val(e, 'encours_devise') or 'EUR')))
    row('Devise', esc(val(e, 'devise')))
    row('Distribution', esc(val(e, 'distribution')))
    row('Replication', esc(val(e, 'replication') or val(e, 'repl_method')))
    row('Date de creation', esc(val(e, 'date_creation')))
    pea = '<span class="badge-pea">PEA</span>' if str(val(e, 'peap', '')).lower() in ('oui', 'yes', 'true', '1') else ''
    title = name + ' (' + isin + ') - Fiche ETF | Alfred Invest'
    desc = 'Fiche ETF ' + isin + ' : frais ' + (val(e, 'frais') or 'non communique') + ', SRI ' + (val(e, 'sri') or 'non communique') + ', score Alfred ' + (str(sc.get('total', 'NA')) if sc else 'NA') + '/100.'
    canon = 'https://alfredstudio.mooo.com/etf/' + isin + '/'
    h = TPL_HEAD.replace('__TITLE__', title).replace('__DESC__', desc)
    h = h.replace('__CANON__', canon).replace('__NAME__', name).replace('__PEA__', pea)
    h = h.replace('__ROWS__', chr(10).join(rows)).replace('__SCORE__', score_block(sc))
    h = h.replace('__ISIN__', esc(isin)).replace('__FOOTER__', FOOTER)
    out = os.path.join('etf', isin)
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, 'index.html'), 'w', encoding='utf-8').write(h)

for e in DATA:
    gen_etf(e)
print("OK fiches:", len(DATA))
