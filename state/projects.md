# Projets — État Vivant

Dernière mise à jour : 2026-08-19 (à réaligner sur current_state.md)

## Projets actifs

### 1. YouTube Alfred AI (@alfred-studio)
- **Phase** : Pivot Qualité > Quantité (appliqué 2026-07-01)
- **Niche** : Neuro-Finance — format choc
- **Métriques** : 11 abonnés, 1 758 vues totales, 44 vidéos
- **Fréquence** : Mercredi 18h Paris (1×/sem au lieu de 3×)
- **Top vidéo** : "L'Erreur qui coûte le plus cher : L'Inaction" (207 vues)
- **Pipeline** : nightly_orchestrator.py — stable
- **Dernière action** : Audit v4 Pro + redesign graphique stat cards dark/gold (2026-06-27)

### 2. Infra VPS
- **Phase** : Maintenance + Sécurité
- **État** : Sain (disque 72%, RAM OK, CPU OK)
- **Watchdog** : ✅ Actif, alertes Telegram toutes les 30 min
- **Sécurité** : Secrets déplacés hors workspace, .gitignore renforcé, 16 pycache nettoyés
- **Reste** : Rotation tokens Telegram + gateway (nécessite Eric)

### 3. Euromillions
- **Phase** : Scale (v4 Évolutionnaire)
- **État** : Pipeline actif, cron mar/ven 12:00 UTC
- **Dernier tirage** : Pipeline en attente

### 4. PEA Comparator + Blog Ghost
- **Phase** : Live — besoin de trafic
- **État** : Site statique opérationnel (429 ETF, 6 calculateurs, landing page)
- **Blog** : 3 articles SEO publiés (frais cachés, PEA vs AV, DCA ETF)
- **SEO** : Sitemap à jour, description YouTube → redirige vers site

### 5. Bot Telegram (@AlfredETFBot)
- **Phase** : Lancé — viralité nécessaire
- **État** : Commandes /fire, /compound, /pea, recherche ISIN
- **Objectif** : Leads → affiliation courtiers

### 6. Alfred Trader (scripts/alfred_trader.py)
- **Phase** : Actif — 2 crons quotidiens
- **État** : alfred-trader-morning (8h Paris) + alfred-trader-us-pulse (15h30 Paris, lun-ven)
- **Objectif** : Signaux achat/vente pour investissement PEA Eric

## Projets en veille
- TikTok cross-posting (attente approbation API — abandon probable)
- paper_trading.py / self_learning.py (0€ généré — à supprimer ?)