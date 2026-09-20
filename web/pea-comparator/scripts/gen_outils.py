# -*- coding: utf-8 -*-
import os
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(BASE)

FOOTER = open('bonus-pea.html', encoding='utf-8').read()
i = FOOTER.find('<footer')
j = FOOTER.rfind('</footer>') + len('</footer>')
FOOTER = FOOTER[i:j]

TOOLS = [
    ("comparer-2-etf", "Comparer 2 ETF", "Comparez deux ETF côte à côte : frais, risque, performance. Entrez deux ISIN et visualisez les différences.", "tc-compare"),
    ("top-etf-par-indice", "Top ETF par indice", "Classement pédagogique des ETF par indice (MSCI World, S&P 500, Nasdaq-100, Euro Stoxx…) selon le Score Alfred.", "tc-topetf"),
    ("simulation-allocation", "Simulation d'allocation", "Simulez une allocation d'exemple selon votre profil de risque. Résultat indicatif, pas une recommandation.", "tc-alloc"),
    ("pea-vs-av-vs-cto", "PEA vs AV vs CTO", "Comparez les enveloppes fiscales sur le long terme : PEA, assurance-vie et compte-titres.", "tc-env"),
    ("interets-composes", "Intérêts composés", "Visualisez la puissance des intérêts composés sur votre épargne.", "tc-compound"),
    ("plan-40-ans", "Plan des 40 ans", "Votre plan de long terme en 2 étapes : capital cible puis chemin d'investissement.", "tc-plan40"),
    ("chemin-1-million", "Chemin vers 1 million", "Combien de temps pour atteindre 1 million d'euros selon votre épargne mensuelle et le rendement ?", "tc-million"),
    ("independance-financiere", "Indépendance financière", "Quand pourriez-vous arrêter de travailler ? Simulez votre indépendance financière.", "tc-fire"),
    ("impact-des-frais", "Impact des frais", "Visualisez ce que 1 % de frais vous coûte vraiment sur 20 ou 30 ans.", "tc-fees"),
    ("inflation", "Inflation", "Ce que votre épargne vaudra vraiment dans 20 ans après inflation.", "tc-inflation"),
    ("retraits-mensuels", "Retraits mensuels", "Combien pouvez-vous retirer chaque mois sur une durée choisie, sans épuiser le capital trop vite ?", "tc-consumption"),
    ("plan-rattrapage", "Plan de rattrapage", "Vous avez commencé tard ? Simulez le rattrapage nécessaire pour atteindre votre objectif.", "tc-catchup"),
]

HEAD = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<meta name="description" content="__DESC__">
<link rel="canonical" href="https://alfredstudio.mooo.com/outils/__SLUG__/">
<meta property="og:type" content="website">
<meta property="og:locale" content="fr_FR">
<meta property="og:site_name" content="Alfred Invest">
<meta property="og:title" content="__TITLE__">
<meta property="og:description" content="__DESC__">
<meta property="og:url" content="https://alfredstudio.mooo.com/outils/__SLUG__/">
<meta name="robots" content="index,follow">
<link rel="stylesheet" href="../../style.css">
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <a href="/" class="logo"><div class="logo-icon">A</div><span>Alfred Invest</span></a>
      <p class="tagline" style="font-size:.8rem;color:#94a3b8">Outils gratuits</p>
    </div>
  </header>
  <main class="container" style="padding-top:24px">
    <p style="color:#8a9bb0;font-size:.8rem;margin-bottom:4px"><a href="/">← Retour au comparateur</a> &middot; <a href="/outils/">Tous les outils</a></p>
    <h1 style="margin:8px 0 4px">__TITLE__</h1>
    <p style="color:#8a9bb0;font-size:.85rem;margin-bottom:16px">Outil gratuit et sans compte d'Alfred Invest</p>
    <div class="card"><p>__DESC__</p>
    <p style="margin-top:14px"><a class="btn btn-primary" href="/#__ANCHOR__">Ouvrir l'outil</a></p>
    <p style="font-size:.72rem;color:#8a9bb0;margin-top:10px">Résultats purement indicatifs, à visée pédagogique. Ne constituent pas un conseil en investissement personnalisé.</p></div>
  </main>
  __FOOTER__
</body>
</html>"""

for slug, titre, desc, anchor in TOOLS:
    h = HEAD.replace("__TITLE__", titre).replace("__DESC__", desc)
    h = h.replace("__SLUG__", slug).replace("__ANCHOR__", anchor).replace("__FOOTER__", FOOTER)
    out = os.path.join("outils", slug)
    os.makedirs(out, exist_ok=True)
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(h)

# Hub /outils/
cards = ""
for slug, titre, desc, anchor in TOOLS:
    cards += '<div class="tool-card"><div class="tool-card-header"><div class="tool-card-info"><h3><a href="/outils/%s/">%s</a></h3><p>%s</p></div></div></div>' % (slug, titre, desc[:70])
hub = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Outils financiers gratuits | Alfred Invest</title>
<meta name="description" content="12 outils gratuits pour votre épargne : comparateur d'ETF, intérêts composés, indépendance financière, impact des frais, PEA vs AV vs CTO et plus.">
<link rel="canonical" href="https://alfredstudio.mooo.com/outils/">
<meta property="og:type" content="website">
<meta property="og:locale" content="fr_FR">
<meta property="og:site_name" content="Alfred Invest">
<meta property="og:title" content="Outils financiers gratuits | Alfred Invest">
<meta property="og:url" content="https://alfredstudio.mooo.com/outils/">
<meta name="robots" content="index,follow">
<link rel="stylesheet" href="../style.css">
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <a href="/" class="logo"><div class="logo-icon">A</div><span>Alfred Invest</span></a>
      <p class="tagline" style="font-size:.8rem;color:#94a3b8">Outils gratuits</p>
    </div>
  </header>
  <main class="container" style="padding-top:24px">
    <p style="color:#8a9bb0;font-size:.8rem;margin-bottom:4px"><a href="/">← Retour au comparateur</a></p>
    <h1 style="margin:8px 0 4px">Outils financiers gratuits</h1>
    <p style="color:#8a9bb0;font-size:.85rem;margin-bottom:16px">12 outils sans compte, à visée pédagogique.</p>
    <div class="tools-grid">__CARDS__</div>
  </main>
  __FOOTER__
</body>
</html>"""
hub = hub.replace("__CARDS__", cards).replace("__FOOTER__", FOOTER)
os.makedirs("outils", exist_ok=True)
open("outils/index.html", "w", encoding="utf-8").write(hub)
print("outils generes:", len(TOOLS), "+ hub")
