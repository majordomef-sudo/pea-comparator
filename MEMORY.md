# MEMORY.md — Mémoire long terme d'Alfred

Dernière mise à jour : 2026-08-19

## Qui je suis
Je suis Alfred, majordome IA d'Eric. Je parle français, je suis direct et opérationnel. Pas de blabla.

## Mission : Aider Eric à atteindre la liberté financière 🎯
- **Objectif :** 600 000 € de capital (2000€/mois ÷ 4% règle de Trinity)
- **Âge d'Eric :** 26 ans — **Horizon :** 26-30 ans
- **Stratégie :** DCA 200€/mois, PEA Trade Republic, 4 phases

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

## Les leviers de revenus

| Levier | Statut | Potentiel |
|--------|--------|-----------|
| 📺 YouTube Neuro-Finance | ✅ Pipeline actif (TOUS LES JOURS 18h Paris — 1 vidéo/jour) | Monétisation → AdSense |
| 🖥️ Comparateur PEA | ✅ Lancé + 10 calculateurs | Affiliation Trade Republic + leads |
| 🤖 Bot Telegram public | 🚧 En construction | Viralité + affiliation courtiers |
| 📝 Articles/SEO finance | 💡 À lancer | Trafic organique → affiliation |


## Projets actifs

### Pipeline vidéo Neuro-Finance
- **Pipeline :** cron TOUS LES JOURS 16h UTC (18h Paris) — 1 vidéo/jour
- **Script génération :** DeepSeek V4 Flash 0731 (fallback Gemma 4 31B), 4 segments de 38-55 mots
- **Clips :** piochés aléatoirement dans `~/output/raw_clips/`
- **Montage :** 2 passes (PASS 1 → PASS 2 +faststart)
- **TTS :** `fr-FR-RemyMultilingualNeural` (rate -5%)
- **Validations :** ffprobe 1920×1080, data check, espace /tmp > 1 Go
- **Sécurités :** flock, anti-titre-dupliqué, dead man's switch

### Comparateur PEA + Calculateurs
- **Site :** `web/pea-comparator/` — 429 ETF PEA, 10 calculateurs
- **Structure :** Header → Outils Financiers (10) → Top ETF → 429 ETF → FAQ → Footer
- **Architecture :** HTML + script.js + script.min.js + calc_functions.js + etf-data.min.js
- **Déploiement :** nginx root `/var/www/html/`
- **Cache-busting :** hash fixe `v=1784966542`
- **Objectif :** trafic SEO → affiliation Trade Republic
### Portefeuille 70/25/5 (variante diversification)
Référence : `docs/investissement/` — allocation complète 13 lignes avec SCPI, Crypto, Smart Beta.

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
- **Model router :** DeepSeek V4.1 Flash (défaut pipelines/crons depuis 24/09), DeepSeek V4 Pro (complexe), Gemma 4 31B (fallback)
- **Nocturne Memory :** port 8898 (MCP SSE, remplace Mem0)
- **Bot Telegram :** connecté

## Décisions clés
- **Chaîne YouTube :** @alfred-studio, 25+ vidéos
- **Modèle default (pipelines/crons) :** `deepseek/deepseek-v4.1-flash` (depuis 24/09) | **Pro :** `deepseek/deepseek-v4-pro` | **Fallback :** `google/gemma-4-31b-it`
- **Clause livraison obligatoire** pour sub-agents
## TikTok cross-posting (abandonné)
- API TikTok Content Posting demandée (30/04) — toujours pas approuvé (27/05)
- Abandon probable après 36 jours d'attente

## Finances & patrimoine
- **PEA :** Trade Republic (DCAM, 200€/mois)
- **Framework :** Gavekal + Taleb (4 buckets : or, cash, équités, convexité/BTC)
- **Bitcoin :** Cold storage

## Système d'auto-amélioration

| Horaire UTC | Script | Fonction |
|-------------|--------|----------|
| */30 6-22 | `scripts/end_of_session.py` | Extraction leçons + patterns d'erreurs |
| 23:00 | `scripts/daily_memory_update.py` | Met à jour métriques dans MEMORY.md |
| 08:00 | `scripts/auto_reflection.py` | Détection patterns récurrents → alertes |
| 02:00 | `scripts/stats_youtube_nightly.py` | Stats YouTube auto (token OAuth) |
| 02:30 | `scripts/veille_concurrence.py` | Veille concurrence chaînes finance/IA |
| 03:30 | `scripts/auto_diagnostic.py` | Auto-diagnostic logs pipeline, disque |
| 04:00 | `scripts/revenue_audit.py` | Audit revenus → `state/revenue_audit/latest.json` + Telegram |
| 04:30 | `scripts/seo_tracker.py` | Suivi SEO positions mots-clés |

## Leçons apprises (juillet 2026)

### PEA Comparator
- Heredoc bash corrompt le HTML > 40 KB — toujours utiliser Python
- Ne jamais `git checkout HEAD` sans backup
- Event delegation > querySelectorAll pour sites avec gros scripts
- Toujours copier TOUS les fichiers JS (pas seulement HTML)
- Design visuel à l'aveugle = catastrophe — demander screenshot
- Quand Eric approuve, s'arrêter — ne pas continuer à itérer
- Vérifier les 3 fichiers (HTML+CSS+JS) après un rollback
- `etf-data.min.js` expose `window.PEA_ETFS`

### Pipeline vidéo
- Hook analysis réparé le 30/07 : whisper import cassé → toutes les vidéos notées 6.0/10 fixe
- A/B testing initié : test chiffre choc vs question
- Pipeline path corrigé : `nightly_orchestrator` → `pipeline_orchestrator`

### Infrastructure
- 6 scripts cron nocturnes existent dans `workspace/scripts/`
- Les chemins de fichiers doivent être vérifiés systématiquement (causes de 70% des bugs)






















#### Skills (août 2026) — inspiré de NVIDIA/skills
- Chaque skill agent doit avoir un frontmatter normalisé (name/version/description/compatibility/tags/allowed-tools) — template dans `skills/_template/SKILL.md.template`
- **Gap :** nos skills n'ont pas de validation/benchmark objectif → ajouter un mini-benchmark par skill clé (pipeline vidéo, PEA Comparator) pour détecter régressions
- Le contenu NVIDIA (CUDA/robotique) est inutile pour nos projets ; ne copier que l'infrastructure skills

## Metriques (2026-08-19 23:00)
- Site: 5/5 pages OK
- Trafic 24h: 638 hits, 127 visiteurs
- Trafic 7j: 7204 hits, 628 visiteurs
- YouTube: 16 abos, 46 vues

### Watchdog (2026-08-20)
- Fix: vps_watchdog.py n'était pas exécutable (Permission denied depuis ~20j, 975 erreurs). chmod +x appliqué.
- Fix: checks Mem0 (mort) remplacés par nocturne_memory (port 8898) — plus de fausses alertes.
- Service mémoire actif = nocturne_memory (systemd alfred-memory.service désactivé, ne pas relancer).









































### Metriques (2026-09-29 23:00)
- Site: 5/5 pages OK
- Trafic 24h: 289 hits, 137 visiteurs
- Trafic 7j: 4085 hits, 685 visiteurs
- YouTube: 17 abos, 607 vues

## Projet Macro Gave (methode corrigee 2026-08-24)
- **Methode:** quadrant classe vs moyenne de CYCLE 7 ANS (croissance PIB YoY + inflation HICP Eurostat), PAS a des seuils absolus. Backtest 4/4 valide.
- **Refs reelles (API Eurostat):** croissance mean7y=1.14pct (actuel 0.9, 2026-Q2) ; inflation mean7y=3.20pct (actuel 2.0, 2025-12).
- **Verdict reel:** Q4 (croissance basse + inflation basse). Transition 0/100.
- **Acces externe:** PMI S&P, Brent ICE, TTF = cles payantes; reste seed en attendant API libre.


## Incident pipeline 2026-08-25 (YouTube OAuth)
- 2e jour consecutif d'echec du pipeline 16:00 (24 et 25/08) : token OAuth YouTube corrompu (client_secret manquant, ~/.secrets/youtube_token.json).
- Fix applique : reparation token (corrompu archive: youtube_token.json.corrompu_20260825) + patch robustesse upload.py (_inject_client_secret, 16:42).
- Valide 20:45 UTC : oauth_check OK, token renouvele.
- Upload manuel de la video du jour (PROD_20260825_1610) reussi -> https://www.youtube.com/watch?v=Y81mCpdXqX0
- Note : creds.to_json() ne stocke PAS client_secret; _inject_client_secret() le re-injecte a chaque upload. Ne pas remplacer ce patch.

## Lecon Euromillions (2026-08-28) — chantier CLOS
- Backtest evolutionnaire 935 tirages (2017-2026) refait 2x : resultats IDENTIQUES (evolue 2.0995 vs controle 2.1037, avantage -0.0043, p=0.62) -> protocole reproductible, pas d'artefact.
- Verdict def. : l'evolution ne bat PAS la population figee, et personne ne bat le hasard. Aucun signal predictif exploitable.
- Mode production = uniforme maintenu. NE PAS rouvrir ce chantier (prochain run = meme conclusion).
- Livre quand meme : evolution_backtest.py (eval historique + fitness relative + comparaison evolue/controle), antifoule.py (grilles anti-partage >31), hybride v2 par VOTE bagging dans analyze_v2.py.
- Le SEUL edge reel = anti-foule (numeros impopulaires -> gains moins partages) -> argument produit bot/SEO.
- Fichiers d'archivage : euromillions/backups/runs_20260828/

## Heartbeat 2026-08-29 — Pipeline vidéo dégradé
- Neuro-finance daily (16h UTC) : 6 échecs sur les 8 derniers runs (exit=1), dont 2 TIMEOUT 1800s (08-21, 08-28). Runs OK : 08-26, 08-27.
- 08-28 : pas de vidéo produite/publiée (orchestrateur bloqué >1800s).
- À diagnostiquer avant run 16h du 29/08 : étape de blocage orchestrateur (probable génération image / appel LLM / ffmpeg).

## Incident 2026-09-03 — Fact-check boucle + fix root cause
- 3 echecs pipeline neurofinance (04:00 idees #16, 04:28 #17, 04:50 #18 avant patch) sur le MEME blocage : "Fact-check refuse apres 3 tentatives" — memes symptomes que le 28/08.
- **Root cause trouvee :** ask_llm() dans pipeline/pipeline_orchestrator.py n'envoyait le parametre reasoning:exclude qu'au modele DeepSeek V4 Pro. Le modele principal deepseek-v4-flash-0731 est un modele reasoning -> il mettait son brouillon dans le champ reasoning et renvoyait content=None ("Reponse vide") -> fallback Gemma -> scripts qualite degradee -> fact-check bouclait 3x et plantait.
- **Fix :** ligne 221, condition etendue de m == deepseek-pro a "deepseek" in m (reasoning.exclude + response_format json s'applique a TOUS les modeles DeepSeek). Backup: pipeline_orchestrator.py.bak_factcheck_refus_20260903.
- **Resultat :** relance a 04:50 -> idee #18 "Le vrai cout de jouer en bourse" = SUCCES. Fact-check valide au 2e essai, video PROD_20260903_0504 (71.6s, 1080x1920, score 84/100), upload YouTube OK -> https://youtu.be/-HnrFydthbA , cross-post Zernio LinkedIn OK. Idee marquee done.
- **Lecon :** tout modele deepseek (flash/pro) doit recevoir reasoning.exclude sinon content=None. NE PAS reverter ce patch.

## Heartbeat 2026-09-10 — Pipeline vidéo dégradé (3 échecs, 0 vidéo)
- Aucune vidéo PROD le 10/09 : 3 echecs consecutifs (succes la veille, idee #25 exit=0).
  1. 04:00 UTC idee #26 "Ce que vous croyez risqué ne l'est pas" -> exit=1 apres 1235s.
  2. 05:15 UTC retry #26 -> exit=1 apres 885s : "Fact-check refuse apres 3 tentatives : 5 problemes persistent" MALGRE 2 corrections automatiques deepseek (DATA-VALIDATION). Les 5 points restants sont des affirmations jugees non-sources/universelles (10% du revenu, "la discipline bat l'intuition", etc.) -> probable desaccord circulaire validateur/generateur (barre trop stricte ?), PAS le bug reasoning de 09-03 (patch toujours en place).
  3. 07:22 UTC idee #27 "Votre compte-titres déteste votre perfectionnisme" -> TIMEOUT 1800s (meme symptome que le 28/08).
- A diagnostiquer avant le run 04:00 UTC du 11/09 : boucle fact-check qui ne converge pas + etape de blocage >1800s.

## Heartbeat 2026-09-11 — Pipeline récupéré, QA viralité en baisse
- **Correction note 09-10 :** la video du 10/09 a FINALEMENT ete produite a 17:23 (PROD_20260910_1723) — la journee a fini avec 1 video, pas 0. Le run 16:00 a compense les 3 echecs du matin.
- Run 04:00 du 11/09 (idee #29 "Le sentiment de controle vous rend aveugle au hasard") : SUCCESS exit=0 en 1457s. Video PROD_20260911_0413 (80.9s, 63MB→4MB compressee), QA 72/100.
- Publication OK : YouTube https://www.youtube.com/watch?v=G0oMZs-kaDo + Zernio (linkedin). OAuth OK (patch client_secret toujours en place).
- La boucle fact-check du 10/09 (non-convergence 04:00/05:15 + TIMEOUT 07:22) ne s'est PAS reproduite le 11/09 — plus besoin de diagnostic bloquant.
- **Signal QUALITE (nouveau) :** QA video du 11/09 = 72/100 vs baseline 76.5/100 (87 videos), dont Viralite 9/20 et tendance "Degradation". Faiblesse viralite recurrente.
- **1 seule amelioration prioritaire :** analyser le hook + chute (video-analysis) sur PROD_20260911_0413 pour remonter la Viralite (>12/20) avant les prochains runs.
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

## Pass 2 refonte site (2026-09-19) - 10 bugs corriges
- Icones outils : 12 SVG lucide (24px stroke 1 #0F766E) remplaces, plus AUCUN emoji dans les tool-cards.
- tool-card.open grid-column 1/-1 : simulateur ouvert = pleine rangee.
- Tableau : CSS unifie en #etfTable (hover/sticky ne s appliquaient pas avant).
- id=faq ajoute sur FAQ (lien header fonctionne).
- Header <820px : vrai hamburger au lieu de la colonne full-width ; logo sans border-radius 50.
- OG : nouveau og-image.jpg avec le A teal visible (ancien : 0 px teal).
- leadModal supprime.
- Trim des espaces de tete laisses par emoji (titres, toast, boutons, cookie).
- Anciennes vars inline -> tokens :root actuels.
- BUG STRUCTURE : carte topetf imbriquee dans plan40 (div manquant) cassee - corrige.
- Cache-bust style.css v=1789804741.
- Blog : title/meta_title/logo/icon -> Alfred, description UTF-8, nav sans /pea-comparator/, posts+footer assainis.
- Deploye /var/www/html + push git main (commit 9934b54).

## Heartbeat 2026-09-20 — Incident pipeline vidéo
- Le pipeline 20260920 a echoue a 04:00 : la restructuration du 19/09 08:38 avait supprime les sources skills/video-analysis (analyze_video.py, modules) et vide skills/alfred_video_pipeline/ (PLAYBOOK/CHARTER/LEXICON/brand_icon).
- Fix : import analyze_video rendu optionnel (fallback degrade + WARN) ; 4 fichiers bloquants restaures depuis /home/ubuntu/.openclaw/sandboxes/agent-main-f331f052/skills/alfred_video_pipeline/ (copies 2026-07-19). Backup orchestrateur : pipeline_orchestrator.py.bak_before_analyze_guard.*
- Backfill relance 12:48 UTC (idee #41).
- LECON : apres toute restructuration de skill, verifier imports de pipeline_orchestrator.py + assets alfred_video_pipeline avant le prochain run cron.
- A FAIRE (non bloquant) : reconstruire analyze_video.py (seuls des .pyc subsistent, pas de source nulle part, hors git) pour re-activer l analyse auto.

## Heartbeat 2026-09-21 — Incident pipeline vidéo (caption_burner manquant)
- Echec idee #42 (Les soldes en bourse sont un piège) a 04:01 et 04:35 UTC : ModuleNotFoundError: No module named 'caption_burner' dans scene_composer.py (stage 5 composition).
- Cause : caption_burner.py supprime du disque (restructuration du 19/09 ou cleanup pyc) ; seuls des .pyc stale (juil.) subsistaient. Non tracke dans l'index git.
- Fix : restaure depuis git b7ba27a → skills/alfred_cron/caption_burner.py (692 lignes, 26021 octets). Import verifie + smoke test burn_ass_captions sur video 2s : OK (BURN_OK 29112 bytes).
- Idee #42 remise a pending (backup output/pipeline_ideas.json.bak_20260921_pre_caption_fix) — la video du jour sera produite au prochain run cron (04:00 UTC).
- LECON : quand un import pipeline echoue, verifier git log --all même si le fichier n'est pas dans l'index (git show <commit>:<path>) ; les pyc-only sans source ne s'importent pas.
- NON BLOQUANT : MEMORY.md contient des marqueurs de conflit git non resolus en tete (<<<<<<< Updated upstream / Stashed changes) — a nettoyer lors d'une prochaine session.


## Incident cron Euromillions (2026-09-24) — RESTAURE
- Le cron ETAIT toujours present (0 12 * * 2,5 euromillions_cron.sh), mais la restructuration du 19/09 (meme incident des 20-21/09 pipeline video) avait SUPPRIME du disque : euromillions_cron.sh, pipelineeuromillion (runner), update_data.py, advanced_stats.py, evaluate_performance.py, notify_telegram.py, strategy_engine.py, evolution_manager.py. → echecs silencieux depuis le run du 18/09.
- Restaure : euromillions_cron.sh depuis git 4b65a71 ; runner depuis pipelineeuromillion.bak_before_failfast ; modules .py depuis leurs .bak_* les plus recents ; strategy_engine + evolution_manager depuis les snapshots .bak_before_improvements du 28/08 (seule paire coherente avec analyze_v2.py du 19/09 qui attend generate_uniform/generate_uniform_stars).
- Validation : pipeline complet re-teste 15:10 UTC → 5/5 etapes OK, exit=0. Prochain run auto : vendredi 25/09 12:00 UTC.
- LECON : apres toute restructuration, verifier AUSSI euromillions/ (scripts + runner + modules), pas seulement le pipeline video.


## Audit complet post-restructuration 19/09 (2026-09-24) — SUPPLEMENTS RESTAURES
En plus d'Euromillions (deja note), l'audit a revele et corrige d'autres fichiers supprimes par la restructuration du 19/09 :
- RESTAURE skills/alfred_cron/morning_report.sh (depuis git 3e048be) — le cron 06:00 rapport matinal echouait silencieusement.
- RESTAURE scripts/alfred_trader.py (git 4b65a71) + deps news_context.py, self_learning.py, paper_trading.py, scripts/__init__.py — crons 06:00 et 13:30 (logs montraient can't open file).
- RESTAURE scripts/agor/ (agents.py, __init__.py, risk_manager.py) — import alfred_trader re-valide OK.
- RESTAURE euromillions/run_benchmark.py (depuis .bak_ablation_ok 14/08) + cleanup_euromillions.py (.bak_before_audit) — crons samedi/dimanche.
- OK verifie : pipeline video (import OK, WARN non bloquants), macro_gave, ETF crons, services (nocturne 8898, ghost, alfred-pea-bot, newsletter-proxy), site HTTP 200.
- NON BLOQUANT : revenue_audit_v3.py + _original (SyntaxError, non references par cron) ; skill video-analysis partiellement degrade (connu depuis 20/09, analyze_video manquant hors git) ; .pyc orphelins (gsc_stats, plausible_stats, skill_loader, zernio_tiktok_retry, zen_quote_generator). ATTENTION : find_viral_moments avait ete classe a tort NON BLOQUANT — il est bien importe par pipeline_orchestrator.py ligne 1491 ; source restauree le 29/09/2026.
- LECON : la restructuration du 19/09 a supprime BEAUCOUP plus que le pipeline video. Audit crontab complet = seul moyen de tout rattraper.


## Bascule DeepSeek V4.1 Flash (2026-09-24)
- Eric valide : TOUS les pipelines et crons basculent sur deepseek/deepseek-v4.1-flash (14 fichiers modifies, backups dans ~/output/logs/backups_model_v41/).
- Fichiers : model_router.py, pipeline_config.yaml/yml, pipeline_orchestrator.py, pipeline_idea_refill.py, visual_fixer.py, nightly_orchestrator.py, agent_orchestrator.py, analyze_url.py, morning_report.py, llm_router.py, blog_writer.py, nocturne_nudge.py, import_knowledge_to_nocturne.py.
- Tarifs v4.1 : in 0,15$/M, out 0,60$/M (~5x in / ~1,9x out vs 0731). Surcoût mesuré : ~0,14$/mois (crons = 0,3% du budget OpenRouter).
- Test API real : content OK (pas de content=None), JSON valide -> ask_llm ne tombera pas en fallback Gemma.
- Fallbacks conservés : v4-pro (complex) + gemma-4-31b-it. Chat OpenClaw lui-même INCHANGE (gère dans config OpenClaw, pas model_router).
- Le vrai levier budget : le chat (~99% des 13,6$/mois), pas les crons.

## Fix fact-check pipeline vidéo (2026-09-26)
- Problème : 3 idées d'affilée refusées au fact-check (#50, #51) — le validateur signalait des opinions/punchlines ("le pire moment pour vendre", "le cerveau vous pousse à...") comme affirmations invérifiables. Blocage total des sujets "émotion/biais".
- Fix 1 (validate_script_data, prompt fact-check) : liste explicite "A SIGNALER" (stat chiffrée non sourcée, étude non identifiée, causalité déterministe, chiffre faux) vs "A NE JAMAIS SIGNALER" (opinion, question rhétorique, métaphore, conseil général non chiffré, tendance générale non chiffrée, biais connu sans chiffre) + règle d'arbitrage.
- Fix 2 (prompt génération) : bloc "CHIFFRES INTERDITS" (pourcentage comportemental, étude non citée, "la science montre", toujours/jamais/garanti) + "CHIFFRES AUTORISÉS" (année officielle, durée, montant d'exemple explicite, calcul exact) ; stat_value/stat_label vides si aucun chiffre autorisé. Hook MODE A limité aux chiffres autorisés.
- Fix 3 : correction_prompt ne réécrit plus les tournures catégoriques que dans les segments signalés.
- Test fonctionnel (05:20 UTC) : opinions -> valid=True/0 issue ; abus (90% investisseurs, étude bidon, loi absolue, 12%/an garanti) -> valid=False/4 issues. OK.
- Backup : pipeline/pipeline_orchestrator.py.bak_factcheck_soften_20260926
- Pipeline relancé 05:07 UTC (idée #52) avec les nouveaux prompts.
- Note : /tmp/struct.py parasite masque la stdlib Python si on exécute un script depuis /tmp — placer les scripts de test ailleurs.
## Amélioration pipeline vidéo : données réelles sourcées (2026-09-26)
- Contexte : Eric a montré une série carrousel concurrente (@altitrading, "OUTIL N°X" : ZoneBourse, Finviz, Finary) et demandé ce qu'on peut améliorer dans les pipelines avec ces outils.
- Tests de faisabilité : ZoneBourse = HTTP 403 (anti-bot) ; Finviz = scrapable HTML mais pas d'API publique (fragile, ToS) ; Stooq = challenge JavaScript. Yahoo Finance = OK ; Eurostat = OK ; ECB Data Portal = OK (nouveau).
- Décision : ne PAS scraper ZoneBourse/Finviz. Utiliser les sources libres déjà maîtrisées.
- NOUVEAU : pipeline/market_data_snapshot.py — collecteur de snapshot de données réelles (Yahoo Finance indices/matières premières, Eurostat HICP+PIB, BCE taux de dépôt, base ETF PEA 437 fonds). Cache 12h. Fallback : valeur cachée marquée stale ; si rien, bloc vide (le pipeline retombe sur les règles chiffres seules).
- Yahoo rate-limite (429) sur appels rapprochés : jeu réduit à 5 symboles, throttle 15s, 2 essais max, attente plafonnée 6s, coupe-circuit après 2 échecs consécutifs. Option SNAPSHOT_SKIP_YAHOO=1 pour tester sans Yahoo.
- Intégration pipeline_orchestrator.py : chargement avant le prompt (try/except non bloquant), injection du bloc "DONNÉES RÉELLES VÉRIFIÉES" dans le prompt de génération, priorité d'usage, stat_value/stat_label adossés au snapshot avec source nommée. Backup : pipeline_orchestrator.py.bak_market_data_20260926
- Validation hors-ligne : parsing CAC 40 OK (+277,4% depuis 1996, CAGR 10 ans 6,1%), dégradation propre si réseau mort.
- Validation end-to-end (preview 06:57 UTC, sujet "les frais invisibles") : script généré avec 0,25% (médian), 0,28% (moyen), 144 fonds sous 0,20% — valeurs EXACTES du snapshot, labels "base ETF PEA".
- Leçon : pkill -f avec un motif contenu dans sa propre commande tue son propre shell. Utiliser kill par PID.
- Leçon : dans pipeline_orchestrator.py, la concaténation implicite de chaînes ne fonctionne pas avec une expression parenthésée entre deux littéraux — il faut un + explicite.
## Correctif fact-check vs données réelles (2026-09-26, suite)
- Défaut découvert au run de validation : le fact-check rejetait NOS PROPRES données sourcées (0,25% médian, 144 fonds) comme "statistique non sourcée et invérifiable" — il ne savait pas que le snapshot est fiable.
- Fix : validate_script_data(segments, model, reference_block="") + injection du bloc "VALEURS DE RÉFÉRENCE AUTORISÉES (déjà vérifiées et sourcées)" dans le prompt du fact-check, avec consigne de ne PAS signaler un chiffre figurant dans le référentiel. Appel patché : reference_block=MARKET_DATA_BLOCK.
- Validation fonctionnelle : chiffres du référentiel -> valid=True/0 issue ; inventions (90% investisseurs, étude bidon, 12%/an garanti) -> valid=False/3 issues. OK.
- LEÇON : quand on injecte des données externes dans un prompt de génération, il faut AUSSI les injecter dans le prompt de VÉRIFICATION, sinon le validateur les rejette. Les deux prompts doivent partager le même référentiel.


## DECOUVERTE MAJEURE 2026-09-27 : axe inflation du quadrant etait FAUX (pas juste perime)
- Cause racine : le dataset Eurostat prc_hicp_manr (ECOICOP v1) est FIGE au 2025-12 depuis le changement methodologique Eurostat du 04/02/2026 (derniere maj du dataset : 2026-02-06). Il repond toujours HTTP 200 mais n est plus alimente. Collecteur + gave_ref.py + collectors/inflation.py tapaient tous dessus -> axe inflation bloque sur 2,0 pct (2025-12) alors que le mois courant est a 3,2 pct.
- Le remplacant : dataset prc_hicp_minr (ECOICOP ver.2), dimension coicop18, alimente jusqu au mois courant (derniere donnee 2026-08, maj 2026-09-17). Codes : TOTAL (ex-CP00), TOT_X_NRG_FOOD, SERV, NRG. Tables alternatives : ei_cphi_m, teicp000, prc_hicp_ctr.
- Serie reelle zone euro (RCH_A, EA20) : jan 1,7 | fev 1,9 | mars 2,6 | avr 3,0 | mai 3,2 | juin 2,7 | juil 2,9 | aout 3,2. Sous-jacente 2,4 / services 3,0 / energie 14,3. Moyenne 7 ans = 3,325 -> ecart -0,125 pp.
- Consequence quadrant : inflation 3,2 vs moyenne 3,325 -> NEUTRE (bande +-0,2). Croissance 1,2 vs 1,204 -> NEUTRE aussi. Les deux axes pile sur leur tendance de cycle -> ZONE INDECISE, quadrant precedent conserve (Q1) mais SANS signal, et c est desormais affiche comme tel au lieu d un Goldilocks affirme.
- Correction appliquee : gave_ref.py (EUROSTAT_INFLATION_V2 en primaire, v1 en repli refuse si < 2026-01) + macro_gave/collectors/inflation.py (coicop18 + garde-fou donnee >= 2026-01 sinon repli). Backups .bak_source_v2_20260927_0452.
- Fraicheur site : inflation passee de J+270 a J+27, perime: false en live (verifie sur https://alfredstudio.mooo.com/quadrant.json).
- LECON GENERALE : un dataset officiel peut etre REMPLACE (nouvelle nomenclature) sans cesser de repondre 200 avec des donnees figees. Surveiller le champ updated et OBS_PERIOD_OVERALL_LATEST du JSON-stat, pas le code retour. A ajouter dans l auto-diagnostic.
- BCE : DFR confirme en hausse reelle -> 2,00 pct jusqu au 16/06, 2,25 pct le 17/06, 2,50 pct le 16/09. MRO 2,65 pct. Les news disaient vrai, notre donnee ne l etait plus.

## Mapping ETF : resolution ISIN -> ticker Yahoo (2026-09-27)
- Probleme : mapping justETF -> suffixe Yahoo avec .DE par defaut qui fabriquait des tickers inexistants (EXH0.DE, DJAB.DE, LYY.DE) -> yfinance 404 possible delisted -> ETF sans cotation a vie. Aggravant : le filtre if perf5: return None faisait que 18 ETF avec perf5 mais AUCUN prix n etaient JAMAIS retentes.
- Fix : resolve_ticker_yahoo(isin) via l API publique query1.finance.yahoo.com/v1/finance/search (12/12 resolus sur les ISIN en echec : ESE.PA, ETZ.PA, ETZD.PA, GOLD.AS, CAC.PA, MIB.PA). Cache state/etf_ticker_cache.json (72 ISIN). Priorite des places PAR > AMS > MIL > GER. justETF ne sert plus que de complement : avant, il ECRASAIT un symbole valide.
- Selection batch elargie : reprend aussi les ETF prix manquant, plus seulement perf5 manquant.
- Resultat : 1er batch 60 -> 49/60 enrichis (avant : 5/20). Sans prix : 38 -> 34. Reste 17 ISIN sans prix ni perf5 (Expat/BG + fonds sans listing Yahoo).
- Backups : etf_scrapler.py.bak_ticker_yahoo_20260927_0453, .bak_batchsel_20260927_0453.
- etf-data.min.js redeploye sur /var/www/html (HTTP 200, 325 Ko, cache-bust v=1790484966).


## Controle dataset encore alimente (auto_diagnostic, ajoute 2026-09-27)
- check_datasets_freshness() dans scripts/auto_diagnostic.py : surveille prc_hicp_minr (inflation), namq_10_gdp (croissance), ei_bssi_m_r2 (ESI), ecb_dfr (BCE).
- 3 signaux par dataset : age du champ updated (DIFFUSION), age de la derniere periode (DONNEE), et NON-AVANCE de la derniere periode entre deux passages (> 2 x cadence => fige).
- Sortie : state/dataset_freshness.json (historique) + bloc datasets dans state/auto-reflection/nightly_diagnostic.json + recommandation Telegram prefixee du pictogramme graphique descendant.
- Test negatif valide le 27/09 : sur prc_hicp_manr (dataset mort) -> statut fige, donnee J+270, diffusion J+232, message DATASET SUSPECT. Sur endpoint inexistant -> statut indisponible (404). Sur les 4 datasets vivants -> tous ok.
- Flag --no-notify ajoute pour tester sans envoyer de Telegram. ATTENTION : auto_diagnostic importe send_telegram par from ... import, donc patcher notify_alfred.send_telegram ne suffit pas, il faut globals()['send_telegram'].


## Controle des sources du pipeline video (auto_diagnostic, ajoute 2026-09-27)
- check_pipeline_sources() dans scripts/auto_diagnostic.py : meme logique que check_datasets_freshness (une source qui repond n est pas une source VIVANTE).
- 5 sources surveillees : snapshot marche pipeline (pipeline/data/market_snapshot.json, age vs TTL 12h + champs ok/stale), market_latest.json (max 4 j), base ETF (couverture prix/perf5 + detection de REGRESSION de couverture > 3 pts + coherence min local vs /var/www/html), reserve de clips (~/output/raw_clips : alerte si 0 clip ou si une niche se vide), et l INVARIANT referentiel.
- Invariant referentiel : verifie que MARKET_DATA_BLOCK est injecte dans la GENERATION **et** dans la VERIFICATION (reference_block=MARKET_DATA_BLOCK). C est la lecon du 2026-09-26 transformee en controle automatique : si quelqu un retire l injection cote fact-check, le pipeline rejettera des chiffres pourtant sources.
- ok = absence de CRITIQUE uniquement : un INFO permanent (ex. niche vide depuis toujours) n allume pas l alarme. Historique state/pipeline_sources_history.json.
- Tests du 27/09 : etat normal ok ; base ETF tronquee -> REGRESSION 92,2 pct -> 80,3 pct ; snapshots supprimes -> ABSENT CRITIQUE ; reference_block=None -> NON PARTAGE CRITIQUE ; tout restaure ensuite.


## Incident viralite pipeline (corrige 2026-09-29)
- Symptome : rapport Telegram "🔥 Viral: analyse impossible" a chaque video (au lieu d'un score /100).
- Cause : scripts/find_viral_moments.py (source) supprime lors du nettoyage du 19-23/07 ; seul un .pyc orphelin du 20/07 subsistait. L'import en ligne ~1491 de pipeline_orchestrator.py levait ImportError, avale par un "except Exception" NU -> panne invisible ~2 mois.
- Fix : module reecrit (find_moments/scores 0-100, signaux VIRAL_SIGNALS repris de pipeline/analysis/viral_moments.py) + except desormais logge (print + traceback) dans pipeline_orchestrator.py.
- LECON : un "except Exception" sans log transforme une panne en silence. Tout except du pipeline doit tracer la cause.
- LECON BIS : un .pyc sans .py est un signal fort de module perdu mais encore importe — auditer les imports, pas seulement la presence du .pyc.

## Heartbeat 2026-09-29 — nettoyage marqueurs de conflit MEMORY.md
- Check heartbeat 07:00 UTC : pipelines video OK (PROD_20260929_0403), maintenance 03:00 OK, auto-diagnostic 03:30 (0 alerte), rapport matinal 06:00 envoye, disque 71 %, RAM OK ; swap ~60 % = pression recurrente mais stable (alerte watchdog recurrente, deja connue).
- Detecte ET corrige : MEMORY.md contenait 5 blocs de conflit git non resolus (15 marqueurs, notes le 24/09 jamais traites). Resolus en gardant la version la plus recente ("Stashed changes") + les sections uniques encore valides de "Updated upstream" (Qui je suis, Mon humain, Bibliotheque d'investissement, Ce que j'ai fait, Comportement, Documentation technique, TikTok abandonne, Rapport matinal, Portefeuille 70/25/5).
- Aucune ligne perdue hors doublons remplaces par une version plus recente (verifie par diff d'ensemble). 519 -> 448 lignes, 0 marqueur restant.
- Backup : MEMORY.md.bak_conflictclean_20260929_0700 (sha256 40300b8272acb254797082b34a5fea165cca73e6e8b6c1402accc79837d093ab).
- 1 amelioration prioritaire : ajouter a scripts/auto_diagnostic.py un controle "marqueurs de conflit git" (detecter '<<<<<<<' / '>>>>>>>' dans MEMORY.md + fichiers de memoire) pour eviter une nouvelle regression silencieuse de la memoire long terme.
## Faux positif "ETF obsoletes" (corrige 2026-09-30)

- Alerte recue : "Fichier etf-data.js (live) non modifie depuis 11j" = FAUX POSITIF.
- Cause : /var/www/html/etf-data.js etait un ORPHELIN (aucune page ne le charge : index.html charge uniquement etf-data.min.js + etf-scores.js). Les deploiements ne poussent que la version .min.js -> l'orphelin reste fige au 19/09.
- Verite : etf-data.min.js et etf-scores.js live IDENTIQUES aux sources (md5) et frais (fondamentaux quotidiens 09:30 UTC, scraper dimanche).
- 2e faux positif latent : DATA_UPDATE_DATE = 20/09 dans app.min.js -> age 10j le 30/09, 11j le 01/10 -> aurait alerte tous les jours sans qu'aucun processus ne mette cette date a jour.
- Fix scripts/check_etf_data_freshness.py : detection des fichiers REELLEMENT charges via le HTML (src="....js"), alerte uniquement sur ceux-la (presence + age + parite md5 live/source), orphelins et date declaree passes en INFO (garde-fou 60j), nouvelle option --no-notify. Backup : check_etf_data_freshness.py.bak_orphanfix_20260930_1300
- Tests valides : normal -> FRAIS/exit 0 ; derive md5 (octet ajoute a etf-scores.js live) -> [CRITIQUE] desynchronise/exit 1 ; source figee 15j -> alerte source/exit 1. Etat restaure (md5 live == source verifie).
- Orphelin archive (recoverable, pas de rm) : /home/ubuntu/output/backups/webroot_orphans/etf-data.js.orphelin_20260930. Restauration : sudo mv <ce fichier> /var/www/html/etf-data.js
- LECON : un controle de fraicheur doit porter sur ce qui est SERVI (references dans le HTML), pas sur la simple presence d'un fichier dans la webroot. Sinon faux positifs quotidiens = alerte fatigue (on finit par ignorer les vraies).
- TROUVAILLE non corrigee : /pc/ (page non linkee depuis le site) charge etf-data.min.js + script.min.js en relatif -> /pc/etf-data.min.js et /pc/script.min.js renvoient 404, page cassee. A trancher : supprimer /pc/ ou y deployer les assets.

## Decision /pc/ (corrige 2026-09-30 17:55 UTC)

- Constat : /pc/index.html = ancienne copie de la home (66 KB vs 96 KB), canonical pointant deja vers https://alfredstudio.mooo.com/, index,follow, absente du sitemap, linkee par AUCUNE page, assets en relatif -> /pc/etf-data.min.js et /pc/script.min.js en 404 (page cassee). ~5 hits seulement dans les logs.
- Decision : redirection permanente 301 /pc et /pc/ -> / (au lieu de supprimer ou de redeployer les assets). Motif : garde les liens/bookmarks entrants vivants, supprime le contenu duplique (signal SEO propre), zero maintenance, et evite exactement la classe de bug "deux copies qui divergent".
- Mise en oeuvre : /etc/nginx/sites-enabled/alfredstudio.mooo.com -> blocs "location = /pc" + "location ^~ /pc/" (return 301 /), inseres avant "location /". Backup conf : /tmp/nginx_alfredstudio.bak_pc301_20260930_1752.conf . nginx -t OK + reload OK.
- Dossier archive (recoverable, pas de rm) : /home/ubuntu/output/backups/webroot_orphans/pc_dir_20260930
- Verifs (vhost reel https, Host alfredstudio.mooo.com) : /pc, /pc/, /pc/index.html -> 301 vers / ; / , /etf-data.min.js, /etf-scores.js, /top-etf.html, /outils/, /blog/, /kakeibo/ -> 200. Aucune regression.
- LECON : pour tester nginx, utiliser le VHOST REEL (--resolve + Host), pas http://127.0.0.1 (qui tombe sur le vhost "default" et masque le comportement prod). Erreur commise puis corrigee dans le meme run.



## Audit + nettoyage VPS (2026-09-30)
- Audit complet disque : 35 300 fichiers / 17 Go scannes, 2 571 groupes de doublons stricts (~1,33 Go redondants). Rapport : rapports/nettoyage_vps_2026-09-30.md
- Lot A execute en quarantaine : /home/ubuntu/.trash_20260930 (5,5 Go). Contenu : .output_purge_20260823 (3,9 Go), medias des failures (568 Mo, JSON fact-check conserves), /tmp (900 Mo), sauvegardes recursives /var/www/html (56 Mo), dossier extrait pipeline_20260723 (30 Mo), orphelins home.
- Degats evitables : /var/www/html/_backups_theme2_* contenait 248 copies recursives d'index.html (une sauvegarde a copie une sauvegarde). Detecteur ajoute (section 7 de pipeline_cleanup.py) - le script createur est introuvable dans scripts/skills (probable commande manuelle / session).
- FIX pipeline_cleanup.py (dim 03:00) : + purge staging/trash >7j, + purge medias failures >30j, + detection sauvegardes recursives, + --dry-run. Backup .bak_nettoyage_20260930.
- La quarantaine est sur le meme filesystem -> espace libere seulement a sa purge (auto au plus tard 11/10, ou rm -rf /home/ubuntu/.trash_20260930 pour immediat).
- Lot B en attente : backups_missions (193 Mo), pea-comparator/temp (160 Mo), rapports/ juillet (286 Mo), archive/mem0 (93 Mo), whisper/base.pt (139 Mo), doublons raw_clips (~230 Mo).

- Lot B execute (30/09 20:03) : backups_missions 193 Mo, pea-comparator/temp 160 Mo, archive/mem0 93 Mo, whisper/base.pt 139 Mo, rapports >30j 173 Mo (89->31 dossiers), doublons raw_clips 417 Mo (617->200 Mo), *.bak_* euromillions + /var/www/html. Total lot B ~1,2 Go. Quarantaine totale 6,6 Go.
- VERIF whisper : aucun usage du modele "base" (usages reels = faster-whisper medium via HF cache + whisper "small" dans viral-video-analysis). base.pt etait bien orphelin. tiny.pt (73 Mo) conserve (non verifie).

## Audit .git + versionnement (2026-09-30 soir)
- Constat : .git = 2,4 Go (2 packs 1,9 Go + 518 Mo) dont 97 % de medias/archives. Top blobs : DIC_ETF.tar.gz 424 Mo, DIC_ETF_parts_*.zip ~420 Mo, failures/*/assembled.mp4 ~600 Mo, *.wav 142 Mo, ml_model.pkl 31 Mo.
- AUCUN .gitignore n'existait -> cree (75 lignes) + complete avec *.bak.*, *.bak-*, *.bak[0-9], *_bak, *.r1r5_bak.
- Le depot versionnait le site + euromillions mais PAS l automatisation : pipeline 0/134, state 1/244, macro_gave 0/100, scripts 5/130, skills 5/156, docs 0/16, memory 0/75. Fichiers racine AGENTS/CLAUDE/HEARTBEAT/IDENTITY.md non suivis.
- ETAPE 1 FAITE (commit bf2e3f0, 448 commits) : 533 ajouts, 11 retraits de l index (medes dont last_video.mp4 25 Mo + temp/*.mp4 + __pycache__), 5 modifs. Fichiers suivis 620 -> 1151. Plus aucun .py/.sh/.js non suivi dans les dossiers cles. Aucun push (6 commits d avance sur origin/main = git@github.com:majordomef-sudo/pea-comparator.git).
- ETAPE 2 EN ATTENTE (accord explicite requis) : git filter-repo --strip-blobs-bigger-than 5M + force-push -> ~2 Go recuperables (.git 2,4 Go -> ~250 Mo). gc seul ne suffit pas (blobs atteignables).
- git worktree prune fait (5 worktrees perimes supprimes).
- Reste a trancher : 491 fichiers modifies non committes (487 dans web/pea-comparator, +7045/-5095) = travail site en attente.
- Rapport : rapports/audit_git_2026-09-30.md
