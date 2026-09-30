# Current State

Dernière mise à jour : 2026-08-19

## Source de vérité opérationnelle

### Priorité #1
Faire croître les revenus et les actifs d'Eric.

### Pipeline vidéo
- Pipeline actif : pipeline/pipeline_orchestrator.py
- Format : Shorts 1080x1920
- 4 segments de 38-55 mots
- Durée cible : 60-85 secondes
- Modèle principal : DeepSeek V4 Flash 0731
- Fallback : Gemma 4 31B

### Projets actifs
- YouTube @alfred-studio
- PEA Comparator
- AlfredETFBot
- OpenClaw / Alfred
- Pipeline Euromillions

### Bottleneck actuel
- Croissance audience
- Conversion trafic → revenus
- Automatisation fiable des pipelines

### Consignes
- Ce fichier remplace diagnosis.md et actions.md pour l'état opérationnel.
- Toute information périmée doit être supprimée ou archivée.

<br>
### Configuration validée (2026-08-19)

- Résolution : 1080x1920
- FPS : 30
- Transition : 0.3 s
- Segments : 4
- Longueur segment : 38-55 mots
- Durée finale cible : 60-85 s
- QA bloquante : activée
- OAuth YouTube : obligatoire avant upload

<br>
### Dernier état validé

- Audit OpenClaw : validé
- Compilation pipeline : OK
- Fact-check : DeepSeek V4 Pro + fallback Flash
- Auto-fix actif : stronger_hook
- Upload YouTube : opérationnel
- QA référence : 100/100

<br>
### Prochaine action prioritaire

- Exécuter un test complet preview :
  python3 pipeline/pipeline_orchestrator.py --preview --skip-image-gen

