# -*- coding: utf-8 -*-
import os
BASE = "/home/ubuntu/.openclaw/workspace/web/pea-comparator"
os.chdir(BASE)
FOOTER = open("bonus-pea.html", encoding="utf-8").read()
i = FOOTER.find("<footer")
j = FOOTER.rfind("</footer>") + len("</footer>")
FOOTER = FOOTER[i:j]
body = """
<p style="color:#8a9bb0;font-size:.8rem;margin-bottom:4px"><a href="/">\u2190 Retour au comparateur</a></p>
<h1 style="margin:8px 0 4px">\u00c0 propos d\u2019Alfred Invest</h1>
<p style="color:#8a9bb0;font-size:.85rem;margin-bottom:16px">Site p\u00e9dagogique ind\u00e9pendant sur les ETF \u00e9ligibles au PEA.</p>
<div class="card"><h2>Notre mission</h2><p>Alfred Invest est un outil gratuit et sans compte qui aide les investisseurs particuliers fran\u00e7ais \u00e0 comprendre et comparer les ETF \u00e9ligibles au PEA : %(etf)d ETF r\u00e9f\u00e9renc\u00e9s, un Score Alfred /100 p\u00e9dagogique, 12 outils de simulation (int\u00e9r\u00eats compos\u00e9s, ind\u00e9pendance financi\u00e8re, impact des frais, PEA vs AV vs CTO\u2026).</p></div>
<div class="card"><h2>Ce que nous ne faisons pas</h2><p>Alfred Invest n\u2019est pas un conseiller en investissement (ni CIF ni CGP). Nous ne donnons aucun conseil personnalis\u00e9, n\u2019\u00e9mettons aucun ordre d\u2019achat ou de vente et ne g\u00e9rons aucun portefeuille. Tout contenu est \u00e0 vis\u00e9e p\u00e9dagogique.</p></div>
<div class="card"><h2>Identit\u00e9 de l\u2019\u00e9diteur</h2><p style="color:#8a9bb0">Raison sociale : <strong>TODO_LEGAL</strong><br>Forme juridique / capital : <strong>TODO_LEGAL</strong> <br>Si\u00e8ge social : <strong>TODO_LEGAL</strong> <br>SIRET : <strong>TODO_LEGAL</strong> <br>Directeur de la publication : <strong>TODO_LEGAL</strong> <br>Email : <strong>TODO_LEGAL</strong> <br>H\u00e9bergeur : <strong>TODO_LEGAL</strong> (voir <a href="/mentions-legales">mentions l\u00e9gales</a>)</p></div>
""" % {"etf": 437}
head = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>\u00c0 propos | Alfred Invest</title>
<meta name="description" content="Alfred Invest : comparateur p\u00e9dagogique d\u2019ETF \u00e9ligibles au PEA, outils gratuits et analyse de donn\u00e9es. Site ind\u00e9pendant et sans compte.">
<link rel="canonical" href="https://alfredstudio.mooo.com/a-propos">
<meta property="og:type" content="website">
<meta property="og:locale" content="fr_FR">
<meta property="og:site_name" content="Alfred Invest">
<meta property="og:title" content="\u00c0 propos | Alfred Invest">
<meta property="og:description" content="Comparateur p\u00e9dagogique d\u2019ETF PEA, outils gratuits et analyse de donn\u00e9es.">
<meta property="og:url" content="https://alfredstudio.mooo.com/a-propos">
<meta name="robots" content="index,follow">
<link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <a href="/" class="logo"><div class="logo-icon">A</div><span>Alfred Invest</span></a>
      <p class="tagline" style="font-size:.8rem;color:#94a3b8">\u00c0 propos</p>
    </div>
  </header>
  <main class="container" style="padding-top:24px">
__BODY__
  </main>
  __FOOTER__
</body>
</html>"""
h = head.replace("__BODY__", body).replace("__FOOTER__", FOOTER)
open("a-propos.html", "w", encoding="utf-8").write(h)
print("a-propos.html cree:", len(h), "octets")
