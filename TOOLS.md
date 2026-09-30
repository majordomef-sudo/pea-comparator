# TOOLS.md — Notes locales & Références opérationnelles

_Skills définissent **comment** les outils marchent. Ce fichier c'est **ton** setup._

---

## Ghost CMS

- **Admin URL :** 🔐 (voir .secrets/ghost_keys.txt)
- **API Base :** 🔐 (voir .secrets/ghost_keys.txt)
- **Staff token user_id=1** (contourne limitation integration token)
- **Docker :** /opt/ghost/
  - ghost-blog (ghost:5-alpine, port 2368)
  - ghost-mysql (mysql:8.0)
  - ddns-updater (qmcgaw/ddns-updater)
- **🔴 Clés API :** `/home/ubuntu/.secrets/ghost_keys.txt`


## Pipeline Macro Gave (suivi macro)

- **Dossier :** `macro_gave/` — détection changements de régime économique (Q1-Q4)
- **But :** surveiller transition Q2 (croissance+inflation) → Q3 (stagflation)
- **Commandes :**
  - Analyse complète : `python3 -m macro_gave.run_pipeline`
  - Backtest : `python3 -m macro_gave.backtest` (4 scénarios, 4/4 OK)
  - Dashboard : `python3 -m macro_gave.dashboard.build_dashboard` → dashboard/index.html
  - Test scénario Q3 : `python3 -m macro_gave.test_q3`
- **Données :** `macro_gave/data/seed_reference.json` (références juillet 2026, à remplacer par collecte réelle Eurostat/BCE)
- **Alertes Telegram :** uniquement sur changement significatif (anti-spam), recommandations analytiques — JAMAIS d'ordre automatique
- **Cron :** collecte lundi 08:30, rapport + backtest 1er du mois 09:00/09:30 UTC

## Pipeline vidéo Neuro-Finance

- **Orchestrator prod :** `nightly_orchestrator.py`
- **Réserve clips :** `~/output/raw_clips/`
- **Filtres FFmpeg :** 2 passes (PASS 1 → PASS 2 +faststart)
- **Validation :** ffprobe vérifie 1920×1080 + codec post-render
- **Subscribe overlay :** écran 🔔 en fin de vidéo
- **TTS :** `fr-FR-RemyMultilingualNeural` (rate -5%)
- **Word count scripts :** 24-35 mots
- **Cron :** TOUS LES JOURS 16h UTC (18h Paris) — 1 vidéo/jour
- **Lock/flock, anti-dimanche, anti-titre-dupliqué, dead man's switch** — actifs

## PEA Comparator

- **Site :** `web/pea-comparator/`
- **ETF indexés :** 429
- **Calculateurs :** intérêts composés, FIRE, impact frais, PEA vs AV vs CTO, allocation
- **Affiliation :** Trade Republic

## Euromillions

- **Scripts :** pipeline v4 évolutionnaire, 100 stratégies génétiques, 7 modules de probabilité
- **Cron :** mardi et vendredi 12:00 UTC (14:00 Paris)
- **Cycle :** Scraping → Évaluation fitness → Évolution → Prédictions → Telegram

## Scripts importants

| Script | Usage |
|--------|-------|
| `scripts/maintenance.py` | Analyse système quotidienne |
| `scripts/vps_watchdog.py` | Monitoring VPS (cron */30) |
| `scripts/model_router.py` | Routage modèle par tâche |
| `scripts/revenue_audit.py` | Audit revenus quotidien |
| `scripts/alfred_trader.py` | Agent conseil action |

## Auto-Réflexion

- **State files :** `state/auto-reflection/{errors,ab-testing,improvements,weekly-report}`
- **Fréquence :** erreurs J/2, itération J/7, A/B testing à la volée
- **Garde-fous :** dry-run, max 1 amélioration/jour, pas de modif SOUL sans notif

## Infrastructure

- **OpenClaw + OpenRouter** sur VPS OVH
- **Documentation :** `docs/homelab/`
- **Nocturne Memory :** port 8898 (MCP SSE, remplace Mem0)
- **Nocturne MCP :** http://127.0.0.1:8898/sse (7 tools)
- **Nocturne code :** /tmp/nocturne_memory/
- **Github Scout :** `scripts/github_scout.py` — détection outils viraux

## Model Router

- **Default (pipelines/crons) :** `deepseek/deepseek-v4.1-flash` (depuis 24/09, tous pipelines+crons)
- **Complexe (audit, refacto) :** `deepseek/deepseek-v4-pro`
- **Fallback Flash :** `google/gemma-4-31b-it`
- **Fallback 2 :** `google/gemma-4-26b-a4b-it`

## Template Skills standardisé (inspiré NVIDIA/skills)

- **Source :** github.com/NVIDIA/skills — catalogue de skills agents vérifiés
- **Template :** `skills/_template/SKILL.md.template`
- **Références :** `skills/_template/_nvidia_ref/REF-*.md` (exemples NVIDIA copiés : aiq-deploy, benchmark-format)
- **Ce qu'on copie :** frontmatter normalisé (name/version/description/compatibilité/tags/allowed-tools), sections Purpose/Workflow/Output/Validation/Maintenance
- **Ce qu'on ignore :** contenu CUDA/robotique (inutile pour nos projets)
- **Gap identifié :** validation + benchmark objectif par skill → à intégrer dans nos prochains skills
