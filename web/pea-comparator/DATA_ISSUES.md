# DATA_ISSUES.md — Incohérences ETF / ISIN / compteurs (2026-09-20)

Source de vérité utilisée : `etf-data.js` / `etf-data.min.js` (dataset interne, 437 ISIN uniques, aucun doublon) + `etf-scores.js` (mis à jour le 2026-09-20).

## 1. Compteurs (CORRIGÉ)
- **bonus-pea.html affichait « 429 ETF éligibles au PEA »** → le dataset contient **437 ETF uniques** (le champ "peap" réel est renseigné par ISIN). Corrigé : la page affiche désormais « 437 ETF référencés » + les stats héro de la home restent 437.
- **home dashboard « 0 ETF trouvés » au premier paint** → remplacé par « 437 ETF référencés » statique ; le JS affiche ensuite le vrai compte filtré. Le loader « Chargement des ETF… » n'était jamais masqué : corrigé dans app.min.js (masqué dès le premier rendu).

## 2. ISIN du top 5 (CORRIGÉ — la page bonus inventait des données)
| Fiche | Avant (bonus-pea.html) | Après (source dataset) |
|---|---|---|
| DCAM | FR001400U5Q4 (déjà bon) | FR001400U5Q4 ✓ |
| PAEEM | FR0013412020 (déjà bon) | FR0013412020 ✓ |
| ESE | FR0011550185 (déjà bon) | FR0011550185 ✓ |
| CEMR | FR0013286133 — **absent du dataset** → retiré | remplacé par Amundi PEA S&P 500 FR0011871128 (présent, validé) |
| PUST | FR0010892280 — **absent du dataset, check digit suspect** | FR0010892216 (Amundi PEA Nasdaq-100 présent dans le dataset, source justETF) |

Note : la mission suggérait FR0011871110 pour Amundi PEA Nasdaq-100 ; ce code n'existe **pas** dans notre dataset (qui contient FR0010892216, validé par le pipeline justETF du 19/09 — cf. DATA pdf + validateur check digit). Vérification humaine conseillée auprès d'Amundi si besoin.

## 3. Données marketing non sourcées de la page bonus (CORRIGÉ)
- « ~85% perf 5 ans », « ~120% perf 5 ans » etc. ont été **supprimés** : valeurs approximatives sans source. La page affiche maintenant uniquement frais + SRI + Score Alfred issus du dataset.
- « SRI 5 » arrivant sur CEMR/PAEEM : remis aux valeurs dataset (SRI 4 pour PAEEM, SRI 5 pour Nasdaq-100).

## 4. Scores Alfred (VÉRIFIÉS via etf-scores.js)
- DCAM 68 · ESE 65 · PAEEM 60 · Amundi S&P500 59 · Nasdaq-100 54. Ces scores réels peuvent surprendre vs l'ancien marketing (« les 5 meilleurs ») : la page est désormais présentée comme *sélection pédagogique*, pas comme top 5.

## 5. Champ « frais » du dataset (À SURVEILLER — non corrigé, décision documentée)
- Le dataset contient quelques valeurs « frais: 0 » ou valeurs anciennes pour certains fonds récents (ex. DCAM encours_mio=1.0 dans le fichier non-minifié — vraisemblablement un champ non rafraîchi par le scraper, pas une valeur réelle affichée). L'UI (app.min.js) affiche ces valeurs telles quelles. **Recommandation** : lancer une passe de fraîcheur du scraper (fichier `scripts/veille_fraicheur.py` existant) avant toute refonte data.

## 6. Sitemap (CORRIGÉ côté statique)
- Le sitemap.xml racine référençait **43-50 posts blog « marche-du-* »** (auto-spam quotidien) → réduit à **10 URLs propres** (pages outils + légales), XML validé. Le blog Ghost dispose de son propre sitemap (/blog/sitemap.xml) qui se nettoiera avec les unpublish (cf. BLOG_CLEANUP.md).

## 7. Labels de score
- Aucun libellé Achat/Vendre/Conserver/Surveiller/Remplacer retrouvé dans les pages servies (index, top-etf, bonus, app.min.js). Un fichier annexe `etf-score-integration.js` (non chargé) contenait encore ces labels : purgé.

