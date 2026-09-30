---
name: video-analysis
version: "26.08.00"
description: |
  Analyse complète des vidéos du pipeline Neuro-Finance : technique, scènes, motion, audio, contenu, viralité, hook microscope, hero frames et vision LLM. Génère un rapport qualité (0-100) et des correctifs actionnables.
  Use when: Eric demande d'analyser/évaluer une vidéo Shorts du pipeline, de noter une vidéo, ou de proposer des améliorations concrètes.
license: internal
compatibility: |
  OpenClaw (agent main). Requiert : ffmpeg/ffprobe, whisper, accès OpenRouter, scripts dans skills/video-analysis/scripts/.
metadata:
  author: "Alfred (pipeline Neuro-Finance)"
  tags:
    - video
    - pipeline
    - analyse
    - qualite
    - viralite
    - vision-llm
    - hook
allowed-tools: exec, python3, ffprobe, ffmpeg, whisper, reseau/OpenRouter
---

# Skill : Video Analysis Pipeline

Analyse structurée de toute vidéo produite par le pipeline Neuro-Finance (ou autre). Génère un rapport qualité (0-100) et des suggestions d'amélioration actionnables.

## Purpose

Analyser toute vidéo Shorts du pipeline Neuro-Finance sur **9 dimensions** (dont 3 issues de claude-watch), produire un score global, identifier les axes d'amélioration, et proposer des correctifs concrets pour le pipeline.

Ce skill **possède** l'analyse et le scoring. Il **ne possède pas** la génération du rendu vidéo — il propose des correctifs de paramètres au pipeline.

## Prerequisites

- ffmpeg + ffprobe installés
- whisper (hook microscopy word-level sur [0,10s])
- Accès OpenRouter (analyse contenu LLM + vision LLM)
- Scripts présents : skills/video-analysis/scripts/

## Workflow

### Étape 1 : Analyser une vidéo
python3 ~/.openclaw/workspace/skills/video-analysis/scripts/analyze_video.py --video <chemin-v> [--script <s>] [--output <d>] [--vision]

Analyse réalisée (9 modules) :

| Module | Métriques | Technologie |
|--------|-----------|-------------|
| Technique | Résolution, bitrate, codec, durée, black/freeze frames | ffprobe + ffmpeg |
| Scènes | Nb transitions, durée moyenne plan, cuts vs fades | ffmpeg scene filter |
| Motion | Score de mouvement par scène, segments statiques | ffmpeg scene change |
| Audio | Niveau voix-off, silence, SNR | ffprobe + silencedetect |
| Contenu | Hook strength, emotional triggers, CTA, words interdits | LLM via OpenRouter |
| Viralité | Score prédictif basé sur métriques combinées | Heuristique 7 facteurs |
| Hook microscope | Pattern, score/10, nb frames 0-10s, texte word-level | 2 fps + Whisper [0,10s] |
| Hero frames | 3-5 frames clés (hook, plan dynamique, plan long) | Heuristique déterministe |
| Vision LLM | Texte à l'écran, graphiques, score cohérence | Vision LLM via OpenRouter |

### Étape 2 : Générer le rapport
- **Score global** /100 (technique 30% + contenu 30% + audio 20% + viralité 20%)
- **Hook microscope** : pattern détecté, score /10
- **Hero frames** : chemins et timestamps des frames clés
- **Top 3 améliorations** prioritaires (dont hook si score <6/10)
- **Correctifs automatiques** pour le pipeline (patch config)

### Étape 3 : Appliquer les améliorations
python3 ~/.openclaw/workspace/skills/video-analysis/scripts/improve_pipeline.py --rapport <rapport.json> [--apply]

## Scoring Criteria (détail)

**Technique (/30)** — Résolution 1080p : +10 | Durée 40-60s : +5 | Codec H.264 : +5 | Pas de black >0.5s : +5 | Pas de freeze >0.3s : +5

**Contenu LLM (/30)** — Hook 5 premières secondes : +8 | ≥2 données chiffrées : +6 | Aucun mot interdit : +6 | CTA présent : +5 | Émotion ciblée : +5

**Audio (/20)** — Voix-off >80% : +8 | Pas de silence >1s : +5 | Volume -3dB à -16dB LUFS : +4 | Pas de clipping : +3

**Viralité (/20)** — Ratio motion/statique [0.3-0.7] : +5 | Plan moyen 3-7s : +5 | Transitions>/min >8 : +5 | Hook early + CTA late : +5

**Seuils** : <50 → à améliorer | 50-70 → correct | 70-85 → bon | >85 → excellent

## Modules (scripts/modules/)

| Fichier | Origine | Description |
|---------|---------|-------------|
| technical.py | Existant | Analyse technique ffprobe |
| scenes.py | Amélioré | Détection transitions + scene change |
| motion.py | Existant | Motion analysis |
| audio_analysis.py | Existant | Audio/voix-off |
| content.py | Existant | Analyse LLM contenu |
| virality.py | Existant | Score viralité heuristique |
| report.py | Amélioré | Rapport + hook + hero frames |
| hook_analysis.py | claude-watch | Hook microscope 0-10s |
| hero_frames.py | claude-watch | Sélection 3-5 frames clés |
| vision_analysis.py | isoreal/video-analyzer | Vision LLM : frame extraction, texte |

## Garde-fous

- **Ne JAMAIS modifier le pipeline sans dry-run d'abord.** --apply requis.
- **Ne JAMAIS analyser une vidéo qui n'est pas en 1080p.**
- **L'analyse LLM coûte ~$0.0005/appel.** Limiter à 1 appel/analyse, max 50/jour.
- **Les correctifs ne changent que des paramètres**, pas le code pipeline.
- **Toujours créer une sauvegarde avant apply.**
- **Le hook microscope skip les vidéos <30s.**

## Output

- **Output Type(s) :** rapport JSON + score 0-100 + listes de correctifs
- **Output Format :** Markdown (rapport) + JSON (machine-readable)
- **Exit criteria :** le rapport JSON existe, score global calculé, listes de correctifs prêtes pour validation

## Validation (mini-benchmark)

| Check | Pass criteria |
|---|---|
| Correctness | Le rapport est un JSON valide : modules remplis, score /100 cohérent avec Scoring Criteria |
| Discoverability | Se déclenche quand Eric demande "analyse", "note la vidéo" |
| Efficiency | Moins d'appels LLM inutiles ; pas d'appels en cascade |
| Security | Aucun secret leaké dans le rapport |
| Regression guard | Le score n'est pas fixe/plat ; varie selon vidéo ; détecte réellement les patterns de hook |

## References

- scripts/ (analyze_video.py, improve_pipeline.py, scripts/modules/)
- references/ (exemples de rapport)

## Maintenance
- Last reviewed : 2026-08-20
- Next review : Sep 2026 (30 jours)
- Status : actif
