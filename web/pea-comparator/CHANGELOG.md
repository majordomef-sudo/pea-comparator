# CHANGELOG.md — Mission « Alfred Invest » Lot A (2026-09-20)

## A1 — Marque unique
- Header : « Alfred » → « Alfred Invest » (index.html, bonus-pea.html).
- Nav : « Insights » → « Blog ».
- 404.html : refonte complète — chrome du site (light/teal), titre « 404 | Alfred Invest », liens accueil + comparateur + top-etf + blog + mentions légales. Fini le « Alfred Studio » sombre/gold.
- bonus-pea.html : « Alfred IA » → « Alfred Invest » (title, meta, OG, logo, footer).
- privacy.html / tos.html : remplacés par des redirections méta vers /politique-de-confidentialite et /cgu (plus de texte « Alfred Studio - Terms »).

## A2 — Pages légales + footer
- Nouvelles pages (avec placeholders TODO_LEGAL) : /mentions-legales, /politique-de-confidentialite, /cgu, /avertissement-investissement, /affiliation.
- /methodologie : canonical + OG + footer ajoutés (page existante enrichie).
- Footer enrichi sur toutes les pages : marque + positionnement, liens légaux, date MAJ data (20/09/2026), sources (DICI/PRIIPs, justETF), disclaimer court, disclosure affiliation.
- Newsletter : lien « politique de confidentialité » → /politique-de-confidentialite (au lieu de /privacy.html).
- Pas de bandeau cookies : documenté dans /politique-de-confidentialite (Plausible sans cookie = exempté ; localStorage appareil = non transmis).
- nginx : `try_files $uri $uri.html` pour servir les URLs propres (/mentions-legales etc.) — backup config avant, nginx -t OK, reload effectué.

## A3 — Neutraliser le conseil
- bonus-pea.html réécrit : « Sélection pédagogique · Septembre 2026 », plus de « à avoir dans son portefeuille » / « ma sélection pour démarrer solide », plus de « meilleurs ETF ».
- Performances passées approximatives (« ~85 % ») supprimées ; disclaimers AMF-like renforcés (« pas un conseil en investissement »).
- 8 liens d'affiliation TR identiques → **1 CTA primaire comparateur** + mention affiliation en bas (tertiaire, transparente).
- etf-score-integration.js (fichier annexe non chargé) : purge des labels Acheter/Conserver/Surveiller/Remplacer/Vendre.
- Vérifié : aucun libellé d'achat/vente sur les pages servies.

## A4 — Fiabilité data
- Source de vérité : dataset 437 ISIN uniques (0 doublon) ; etf-scores.js daté 20/09/2026.
- Compteur « 429 » → « 437 » (bonus), « 0 ETF trouvés » premier paint → « 437 ETF référencés » (index).
- **Fix loader** : « Chargement des ETF… » n'était jamais masqué → masqué dès le 1er rendu (app.min.js).
- Message vide précisé (« Aucun ETF ne correspond aux filtres actifs » au lieu de « Aucun ETF trouvé »).
- Page bonus : ISIN vérifiés contre dataset — CEMR (absente) retirée, PUST corrigé (FR0010892216), données frais/SRI/score réelles.
- sitemap.xml : nettoyé des posts spam (43-50 « marche-du ») → 10 URLs propres, XML validé.

## A5 — SEO head
- top-etf.html : + meta description, robots, canonical, OG, twitter:card.
- methodologie.html : + canonical, OG.
- bonus-pea.html / 404 / pages légales : title + description + canonical + OG + lang="fr" ✓.

## A6 — Blog Ghost
- Plan de purge complet : BLOG_CLEANUP.md (50 posts « marche-du » à unpublish, doublons 5-erreurs/dca/capitalisant/harry-browne/passif/inflation, bylines Rédaction Alfred Invest, thème FR, dates H1).
- L'API admin a refusé le token staff (401) : aucune action destructive faite sur Ghost — tout est documenté et prêt à exécuter.

## Fichiers touchés
index.html · top-etf.html · bonus-pea.html · methodologie.html · 404.html · app.min.js · etf-score-integration.js · privacy.html · tos.html · sitemap.xml ·
+ nouvelles : mentions-legales.html · politique-de-confidentialite.html · cgu.html · avertissement-investissement.html · affiliation.html · BLOG_CLEANUP.md

## Risques restants
- Ghost non nettoyé tant que les unpublish ne sont pas faits (dépend de clé API/UI).
- Données frais/encours de certains ETF anciens (passe fraîcheur recommandée).
- FR0010892216 à confirmer humainement (cf. DATA_ISSUES.md).
- Domaine .fr : non acheté, SEO limité tant que DynDNS persiste.

## Preview / déploiement
- Le site est déployé en direct : https://alfredstudio.mooo.com/ (nginx /var/www/html). Pas de preview séparé ; chaque changement a été vérifié via curl sur le domaine HTTPS (codes 200, contenu attendu).

## Lot B (P1) — publié le 2026-09-20

### B1 — URL architecture propre
- 437 fiches statiques /etf/{ISIN}/index.html générées depuis le dataset (nom, ISIN, frais, SRI, perf, émetteur, indice, encours, Score Alfred détaillé, disclaimer, footer légal, canonical + OG). Données jamais affichées quand N/A ou "?".
- Hub /etf/ + 12 pages /outils/{slug}/ (+ hub /outils/) avec canonical + OG + CTA "Ouvrir l'outil".
- Redirection JS des anciennes ancres #etf-ISIN vers /etf/{ISIN}/ sur index.html et top-etf.html.
- Table ETF : ISIN cliquable vers la fiche /etf/{ISIN}/ (app.min.js).
- top-etf.html : 113 liens ../index.html#etf-ISIN remplacés par /etf/{ISIN}/ ; 7 ISIN tronqués réparés via match dataset ou retirés.
- Sitemap : 462 URLs (index, top-etf, bonus, methodologie, outils x13, etf x437, a-propos, pages légales x5).

### B2 — Mobile & watchlist
- Table ETF responsive : cartes sur mobile (<700px) via data-lab sur chaque cellule + CSS, filtres sticky.
- Note watchlist : "Sauvegardé sur cet appareil (localStorage) — jamais transmis."
- Date de MAJ data unifiée 20/09/2026 (constante DATA_UPDATE_DATE dans app.min.js, était 15/09).

### B3 — Méthodologie
- Date cohérente (20/09/2026) + nouvelle section "9. Historique des changements".
- Pondérations réelles du code conservées (indice 25 / réplication 20 / coûts 15 / solidité 15 / émetteur 10 / futur 15 = 100) : la mission suggérait TER 40/encours 25/liquidité 20/tracking 15 mais cela ne correspond pas au calcul réel du Score Alfred — écart documenté dans DATA_ISSUES.md.

### B4 — À propos
- /a-propos créé : mission, "ce que nous ne faisons pas" (pas CIF), identité éditeur en TODO_LEGAL, footer légal, canonical + OG. Lien ajouté au footer index + sitemap.

### B5 — FAQ + schema
- FAQ homepage : 4 → 12 questions (réplication physique vs synthétique, éligibilité PEA, capitalisant vs distribuant, tracking difference vs TER, nombre d'ETF en PEA, Score Alfred, "Alfred Invest est-il un conseiller ?", sources).
- JSON-LD FAQPage ajouté dans le head de la homepage.

### B6 — Affiliation
- /affiliation conforme : fonctionnement, partenaire actuel (Trade Republic), "vous ne payez pas plus", indépendance éditoriale.
- Vérifié : aucune promesse de "comparateur de courtiers" dans les HTML/JS du site.

## URLs touchées (Lot B)
/etf/* (437 fiches) · /etf/ · /outils/* (13) · /a-propos · / · /top-etf.html · /methodologie · /affiliation · sitemap.xml

## Risques restants
- Données frais/encours anciennes pour certains ETF (passe de fraîcheur justETF recommandée).
- FR0010892216 (Amundi PEA Nasdaq-100) validé par match dataset justETF mais pas par émetteur : confirmation humaine souhaitée.
- Ghost non purgé tant que les unpublish ne sont pas faits (clé Admin API à régénérer).
- Les pages /outils/{slug} décrivent l'outil et renvoient vers la home : pas de duplication du code JS des calculateurs (voulu).
