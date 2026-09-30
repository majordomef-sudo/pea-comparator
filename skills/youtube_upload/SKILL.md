---
name: youtube-upload
version: "26.08.00"
description: |
  Gérer la chaîne YouTube Alfred AI (@alfred-studio) : publier des vidéos (individuelles ou batch), consulter les statistiques chaîne, renommer les titres sous-performants.
  Use when: "publie sur YouTube", "stats YouTube", "combien de vues", "renomme la vidéo", "change le titre", "performances de la chaîne".
license: internal
compatibility: |
  OpenClaw (agent main). Requiert : token OAuth YouTube (~/.secrets/youtube_token.json), scripts dans skills/youtube_upload/.
metadata:
  author: "Alfred"
  tags:
    - youtube
    - upload
    - stats
    - renommage
    - chaine
    - alfred-studio
allowed-tools: exec, python3, reseau/YouTube API (OAuth), telegram (envoi lien)
---

# Skill : YouTube Upload & Stats

Gère la chaîne Alfred AI (@alfred-studio) : upload, stats, renommage. Routé depuis `diagnosis` quand le domaine YouTube est identifié.

## Purpose

Publier des vidéos (individuelles ou batch), fournir les statistiques chaîne, renommer les titres sous-performants. Résultat : chaîne maintenue et optimisée sans intervention manuelle d'Eric.

Ce skill **possède** l'upload, les stats et le renommage. Il **ne possède pas** la génération des vidéos (pipeline vidéo) ni la stratégie éditoriale — il exécute et renvoie les données.

## Prerequisites

- Token OAuth YouTube à jour : ~/.secrets/youtube_token.json
- Scripts présents : skills/youtube_upload/ (upload.sh, stats.sh, rename.sh, upload.py, analytics.py...)
- Connexion réseau à l'API YouTube

## Workflow

### Upload d'une vidéo
```bash
~/.openclaw/workspace/skills/youtube_upload/upload.sh "<chemin>" "<titre>" "<description>"
```

### Statistiques chaîne
```bash
~/.openclaw/workspace/skills/youtube_upload/stats.sh
```

### Renommer une vidéo
```bash
~/.openclaw/workspace/skills/youtube_upload/rename.sh "<url_ou_video_id>" "<nouveau_titre>"
```

## Croyances

- **Le titre est la moitié de la performance.** Une bonne vidéo avec un titre faible ne sera pas vue. Prioriser la qualité du titre avant l'upload.
- **Les stats sont des signaux, pas des jugements.** Une baisse de vues est un diagnostic, pas un échec. Analyser, pas paniquer.
- **L'automatisation ne remplace pas la curation.** Uploader plus n'est pas mieux qu'uploader mieux.

## Output

- **Upload :** lien YouTube envoyé sur Telegram
- **Stats :** résumé texte (abonnés, vues, top vidéo)
- **Renommage :** nouveau titre proposé en preview à Eric + confirmation après action
- **Output Type(s) :** confirmation + lien + données stats
- **Exit criteria :** l'action est confirmée par l'API (upload → lien vidéo ; stats → données 2023-08 ; renommage → titre mis à jour) ; lien envoyé sur Telegram si pertinent

## Validation (mini-benchmark)

| Check | Pass criteria |
|---|---|
| Correctness | L'API retourne une réponse valide (video id / stats JSON / titre mis à jour) |
| Discoverability | Déclencheur sur "publie", "stats", "combien de vues", "renomme", "change le titre" |
| Efficiency | Un seul appel API par action ; pas d'appels redondants stats+uploads |
| Security | Aucun token leaké dans les logs ou le prompt ; token non versionné |
| Regression guard | L'upload refuse fichier inexistant/corrompu ; renommage exige titre non vide |

## Notes techniques

- Chaine : Alfred AI (@alfred-studio)
- Token OAuth : ~/.secrets/youtube_token.json
- rename.sh accepte URL complète, youtu.be ou video_id directement

## References

- scripts/ (upload.sh, stats.sh, rename.sh, analytics.py, add_to_playlist.py, auto_reply.py, generate_thumbnail.py, set_privacy.py, list_all_videos.py, manage_playlists.py)

## Maintenance
- Last reviewed : 2026-08-20
- Next review : Sep 2026 (30 jours)
- Status : actif
