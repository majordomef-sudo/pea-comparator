# Infrastructure Alfred
Dernière mise à jour : 2026-04-21

## Serveur Principal (VPS OVH)
- **OS :** Ubuntu
- **IP :** 57.129.120.7
- **Rôle :** Hébergement de l'infrastructure Alfred (OpenClaw + OpenRouter)
- **Localisation :** France

## Services Installés
- **OpenClaw :** Core runtime de l'agent.
- **OpenRouter :** Gateway pour les LLMs.
- **Bot Telegram :** Interface de communication principale.
- **Crontab :** Gestion des pipelines nocturnes, rapports matinaux et synthèses de mémoire.

## Configuration LLM (Routage Dynamique)
- **Routine :** `google/gemma-4-26b-a4b-it`
- **Standard :** `deepseek/deepseek-v4-flash-0731`
- **Expert :** `qwen/qwen3.6-plus`
