---
CONTEXTE MEMOIRE (injecte par le hook agent:bootstrap memory-context).
Source: state/memory_context.md — regenere par scripts/memory_context_recall.py. Ne pas editer a la main.
---

## Lecons procedurales (les plus recentes)
- Le cron dimanche 05:30 appliquera le sweep dédup des 49 fusions + TTL + reindex. Rapport toujours produit avant archivage (exigence Mem0 respectée).  [2026-09-12]
- Crontab : ligne `30 5 * * 0` ajoutée (slot libre dimanche 05:30), backup → `/tmp/crontab_backup_20260911_before_memtenance.txt`. Veille repos (lundi 06:30) intacte, 65 lignes total  [2026-09-12]
- ⚠️ INCIDENT TRANSPARENT : mon test `--help` a en fait LANCÉ le nudge pour de vrai (script sans argparse) → a créé **2 faits réels** (Lumen vaporware + stats TikTok 8.3%, ids 1119/1  [2026-09-12]
- Backup d'abord : `missions/impl-2026-09-11/backups/nocturne_nudge.py.pre_guard.20260911_2125`  [2026-09-12]
- Le contenu NVIDIA (CUDA/robotique) est inutile pour nos projets ; ne copier que l'infrastructure skills  [2026-09-12]
- **Gap :** nos skills n'ont pas de validation/benchmark objectif → ajouter un mini-benchmark par skill clé (pipeline vidéo, PEA Comparator) pour détecter régressions  [2026-09-12]

## Sessions recentes
- [SESSION 2026-09-11] 21:50 — "OK ENCHAINÉ" : garde dédup active dans le nudge + cron hebdo maintenance ✅
**Eric a dit "Ok enchaine" à 20:36** — j'ai enchaîné sur les 2 chantiers proposés en fin de rapport d'implémentation.  [2026-09-12]

