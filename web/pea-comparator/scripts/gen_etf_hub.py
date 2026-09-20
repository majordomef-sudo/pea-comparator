# -*- coding: utf-8 -*-
import os, re
BASE = "/home/ubuntu/.openclaw/workspace/web/pea-comparator"
os.chdir(BASE)
FOOTER = open("bonus-pea.html", encoding="utf-8").read()
i = FOOTER.find("<footer")
j = FOOTER.rfind("</footer>") + len("</footer>")
FOOTER = FOOTER[i:j]
hub = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fiches ETF PEA | Alfred Invest</title>
<meta name="description" content="Consultez la fiche de chaque ETF référencé : ISIN, frais, SRI, réplication, indice suivi et Score Alfred. 437 ETF PEA référencés.">
<link rel="canonical" href="https://alfredstudio.mooo.com/etf/">
<meta property="og:type" content="website">
<meta property="og:locale" content="fr_FR">
<meta property="og:site_name" content="Alfred Invest">
<meta property="og:title" content="Fiches ETF PEA | Alfred Invest">
<meta property="og:url" content="https://alfredstudio.mooo.com/etf/">
<meta name="robots" content="index,follow">
<link rel="stylesheet" href="../style.css">
</head>
<body>
  <header class="header">
    <div class="header-inner">
      <a href="/" class="logo"><div class="logo-icon">A</div><span>Alfred Invest</span></a>
      <p class="tagline" style="font-size:.8rem;color:#94a3b8">Fiches ETF</p>
    </div>
  </header>
  <main class="container" style="padding-top:24px">
    <p style="color:#8a9bb0;font-size:.8rem;margin-bottom:4px"><a href="/">\u2190 Retour au comparateur</a></p>
    <h1 style="margin:8px 0 4px">Fiches ETF PEA</h1>
    <p style="color:#8a9bb0;font-size:.85rem;margin-bottom:16px">437 ETF r\u00e9f\u00e9renc\u00e9s : une fiche p\u00e9dagogique par ISIN (frais, SRI, r\u00e9plication, indice, Score Alfred). Recherchez par ISIN ou utilisez le comparateur pour filtrer.</p>
    <div class="card"><p><a href="/" class="btn btn-primary">Ouvrir le comparateur</a> &nbsp; <a href="/top-etf.html">Top ETF par indice</a></p>
    <p style="font-size:.72rem;color:#8a9bb0">Donn\u00e9es au 20/09/2026 \u00b7 Sources : DICI/PRIIPs, justETF. Contenu p\u00e9dagogique, pas un conseil en investissement.</p></div>
  </main>
  __FOOTER__
</body>
</html>"""
hub = hub.replace("__FOOTER__", FOOTER)
open("etf/index.html", "w", encoding="utf-8").write(hub)
print("hub /etf/ cree")