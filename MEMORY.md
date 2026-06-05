# MEMORY.md — Mémoire long terme d'Alfred

Dernière mise à jour : 2026-06-05 (révision roadmap complète)

## Qui je suis
Je suis Alfred, majordome IA d'Eric. Je parle français, je suis direct et opérationnel. Pas de blabla.

## Mission : Aider Eric à atteindre la liberté financière 🎯
**Objectif ultime : 600 000 € de capital** (2000€/mois ÷ 4% règle de Trinity)
**Âge actuel : 26 ans**
**Horizon : 26-30 ans**
**Stratégie :** DCA 200€/mois, PEA Trade Republic, 4 phases

## Roadmap investissement (définie le 05/06/2026)

### Phase 0 — Fondation 🔵 (EN COURS)
- **Enveloppe :** PEA Trade Republic
- **Core :** **DCAM** — Amundi PEA Monde MSCI World (FR001400U5Q4, 0,20%)
- **Action :** 200€/mois DCA
- **Seuil Phase 1 :** PEA ≥ 10-15k€

### Phase 1 — Diversification EM 🟡 (à venir)
- **Ajout :** PAEEM — Amundi PEA Emergent MSCI EM ESG (FR0013412020, 0,30%)
- **Allocation cible :** ~87% DCAM / ~13% PAEEM
- **DCA ajusté :** 174€ DCAM + 26€ PAEEM

### Phase 2 — Or & EM ex-Chine 🟠 (à venir)
- **Déclencheur :** PEA ≥ 20k€ → ouverture CTO Trade Republic
- **Ajouts CTO :** PPFB (iShares Physical Gold, IE00B4ND3602, 0,12%) + LU2009202107 (Amundi MSCI EM Ex-China, 0,15%)
- **Optionnel PEA :** PTPXE (Amundi PEA Japan TOPIX)

### Phase 3 — Obligations & AV 🔴 (à venir)
- **Déclencheur :** Total portefeuille ≥ 30k€ → ouverture AV Linxea
- **Ajout AV :** IE00BDBRDM35 (iShares Core Global Agg Bond EUR Hdg, 0,10%)

### Allocation finale cible
- 65% MSCI World / 10% EM ESG / 10% EM ex-Chine / 10% Or / 5% Obligations
- **TER moyen pondéré :** ~0,20%

### Projection
- 200€/mois × 30 ans = 72 000€ investis
- À 7%/an → 245 417€ | À 10%/an → 417 557€
- **Besoins pour 600k€ :** ~350€/mois à 7% sur 30 ans, ou 200€/mois à 10%/an sur 30 ans + apports ponctuels

### Portefeuille 70/25/5 (variante diversification)
Référence : `docs/investissement/` — allocation complète 13 lignes avec SCPI, Crypto, Smart Beta.

## Les leviers de revenus que je construis et optimise

| Levier | Statut | Potentiel |
|--------|--------|-----------|
| 📺 YouTube Neuro-Finance | ✅ Pipeline actif (lun-sam 18h) | Monétisation → AdSense (1000 abonnés min.) |
| 🖥️ Comparateur PEA + calculateurs | ✅ Lancé + 🚧 V2 | Affiliation Trade Republic + leads |
| 🤖 Bot Telegram public | 🚧 En construction | Viralité + affiliation courtiers |
| 📝 Articles/SEO finance | 💡 À lancer | Trafic organique → affiliation |

## Ma bibliothèque d'investissement (14 fichiers reçus le 05/06/2026)

```
📂 docs/investissement/
   roadmap_eric.md              → Synthèse complète de la roadmap
   
Les 14 documents source sont dans media/inbound/ :
   BONUSE_* + roadmap_investissement_eric.pdf
   
Couvre : ETF PEA/non-PEA, SCPI, Private Equity, Or, Crypto, Obligataires,
         Fonds datés, Calculateurs (frais, FIRE, 1M, enveloppes fiscales),
         Stratégie multi-actifs (16 classes), Allocation 70/25/5
```

## Ce que j'ai fait (05/06/2026)
- ✅ Reçu et analysé 14 fichiers d'investissement d'Eric
- ✅ Sauvé la roadmap complète dans `docs/investissement/roadmap_eric.md`
- ✅ Mis à jour MEMORY.md avec la vraie stratégie (Trade Republic, DCAM, 4 phases)
- ✅ Priorités définies : portefeuille perso → simulateurs site → YouTube → bot Telegram
- ✅ Prochaine action : ajouter les calculateurs interactifs au comparateur PEA

## Mon humain
- **Nom :** Eric (majordomef@gmail.com)
- **Localisation :** France (UTC+2)
- **Profil :** Développeur/homelab avancé, VPS OVH Ubuntu (57.129.120.7)
- **Style :** Direct, va droit au but, n'aime pas répéter le contexte
- **Âge :** 26 ans
- **Objectif :** Liberté financière (600k€)

## Projets actifs

### Pipeline vidéo Neuro-Finance (mise à jour 2026-05-27)
- **Pipeline unique :** `nightly_orchestrator.py` (prod) — pipeline test obsolète
- **Plus de LTX :** clips piochés aléatoirement dans la réserve `~/output/raw_clips/`
- **Montage 2 passes :** PASS 1 → PASS 2 avec `-movflags +faststart` (optimisé streaming)
- **Modèle script :** **Gemma-4** (fallback DeepSeek-chat), word count 24-35 mots
- **TTS rate : -5%** (Remy ralenti, ton posé — audit 08/05 confirmé)
- **Validation post-encodage :** ffprobe vérifie 1920×1080 + codec après chaque rendu
- **Data check renforcé :** cherche `%`, euros, millions, milliards (plus de simple regex `\d+`)
- **Check /tmp :** bloque si espace < 1 Go avant encodage
- **Code mort retiré :** `DEFAULT_DESC_TEMPLATE` supprimé
- **Audit expert** (v4-pro, 08/05) : score **44/60** (+6 pts)
- **Validation bloquante :** langue interdite, guru-score, data chiffrée
- **Prompt renforcé** + **PHONETIC_FIXES** (comportemental, algorithme, etc.)
- **Upload non-fatale :** si YouTube refuse, warning Telegram + sauvegarde
- **Lock file (flock)**, **Protection dimanche**, **Anti-titre-dupliqué automatisé**, **Token check**, **Dead man's switch** — tous actifs
- **Cron :** lun-sam 18h Paris

### Comparateur PEA + Calculateurs (nouveau — 02/06, V2 en cours)
- Site statique dans `web/pea-comparator/`
- 429 ETF PEA indexés, filtrables par frais, SRI, émetteur
- Lien affiliation Trade Republic intégré
- 🚧 V2 : ajout des calculateurs (intérêts composés, FIRE, impact frais, enveloppes)
- Objectif : trafic SEO → leads → commission

### Contenu YouTube en réserve (idées tirées des docs investissement)
- "J'ai 26 ans, 200€/mois, voici mon plan pour être libre" → Storytime viral
- "PEA vs AV vs CTO : le match fiscal" → Comparatif
- "L'impact CACHÉ des frais (exemple 156 855€)" → Choc
- "La règle de la moitié du chemin vers 1M€" → Éducatif
- "4 phases pour l'indépendance financière" → Série

### Rapport matinal (8h Telegram)
- Stats YouTube (abonnés, vues, top vidéo, niche leader)
- Solde LTX : tracking manuel via state/ltx_balance.json
- Consommation OpenRouter (daily + monthly)
- Prochaine niche planifiée

### Pipeline Test (obsolète — archive)
- `nightly_test_orchestrator.py` en archive, plus utilisé
- Voix Remy : `fr-FR-RemyMultilingualNeural` — stable et validée

### Projet Euromillions
- **Pipeline v4 Évolutionnaire :** 100 stratégies génétiques, 7 modules de probabilité
- **Audit & Nettoyage :** Pipeline audité, ML RandomForest supprimé (530 MB), 6 scripts nettoyés
- **Cron :** Mardi et vendredi à 12:00 UTC (14:00 Paris)
- **Cycle :** Scraping → Évaluation fitness → Évolution → Prédictions → Rapport Telegram

### Infrastructure Alfred
- OpenClaw + OpenRouter sur VPS OVH
- **Documentation technique :** `/home/ubuntu/.openclaw/workspace/docs/homelab/`
- Model-router : Routage dynamique (Routine/Standard/Expert) cf. `TOOLS.md`
- Bot Telegram connecté

## Décisions importantes
- **Chaîne YouTube :** 11 abonnés, 1 571 vues totales, 25 vidéos (au 03/06)
- **Top vidéo :** "L'Erreur qui coûte le plus cher : L'Inaction" (207 vues)
- **🔴 Audit YouTube 27/05 :** Score **48/100** — bugs thumbnail, ConvertKit, PERFORMANCE.md — CORRIGÉS
- **Modèle default :** `openrouter/deepseek/deepseek-v4-flash`
  - Fallback 1 : `openrouter/google/gemma-4-31b-it`
  - Fallback 2 (expert) : `openrouter/deepseek/deepseek-v4-pro`
  - `deepseek/deepseek-v4-flash` sans prefix pour appels API directs dans scripts
- Clause de livraison obligatoire pour sub-agents
- Base stratégique 2026 intégrée (`STRATEGY_2026.md`)

## TikTok cross-posting (abandonné)
- API TikTok Content Posting demandée (30/04) — toujours pas approuvé (27/05)
- Abandon probable après 36 jours d'attente

## Finances & patrimoine
- **PEA :** Trade Republic (DCAM, 200€/mois)
- **Framework :** Gavekal + Taleb (4 buckets : or, cash, équités, convexité/BTC)
- **Bitcoin :** Cold storage
- **Objectif :** 600 000 € (2000€/mois à 4%)
- **Suivi :** Manuel via la roadmap 4 phases

## Vacances
- Lac de Serre-Ponçon, semaine du 14 juillet

## Comportement
- **Mission #1 :** Tout ce que je fais est orienté vers un seul objectif — générer le max de revenus pour Eric afin d'atteindre les 600 000 €.
- **Style :** Réponses rapides et directes, sans blabla
- **Autonomie :** Ne pas attendre qu'Eric relance. Agir, corriger, envoyer le résultat directement. Anticiper les étapes suivantes. L'informer, pas lui demander la permission.
- **Priorisation :** Tout projet qui rapporte de l'argent (ou qui y contribue indirectement) passe avant le reste.
- **Proactivité :** Après chaque session, vérifier les prochaines actions programmées et avancer sans attendre.