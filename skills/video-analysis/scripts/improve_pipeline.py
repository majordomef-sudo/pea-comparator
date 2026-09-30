#!/usr/bin/env python3
"""
improve_pipeline.py — Applique les améliorations suggérées au pipeline

Inclut l'auto-ajustement du hook basé sur l'analyse vidéo (hook_reflection).
Détecte les hooks faibles répétés et renforce le prompt du pipeline.

Usage:
  python3 improve_pipeline.py --rapport rapport.json [--apply]
  Sans --apply : dry-run (affiche les changements sans les appliquer)
  --auto-hook : active la détection et correction automatique du hook
"""

import json, sys, argparse, shutil
from pathlib import Path
from datetime import datetime

WORKSPACE = Path.home() / ".openclaw" / "workspace"
BACKUP_DIR = WORKSPACE / "state" / "pipeline_backups"
SKILL_DIR = WORKSPACE / "skills" / "video-analysis" / "scripts" / "modules"
sys.path.insert(0, str(SKILL_DIR))

from hook_reflection import log_hook_score, get_hook_score_trend, suggest_hook_prompt_adjustment, apply_hook_adjustment_to_pipeline


def parse_args():
    parser = argparse.ArgumentParser(description="Appliquer les améliorations pipeline")
    parser.add_argument("--rapport", help="Chemin vers le rapport JSON")
    parser.add_argument("--apply", action="store_true", help="Appliquer les changements (sinon dry-run)")
    parser.add_argument("--auto-hook", action="store_true", help="Détection et correction automatique du hook dans le prompt pipeline")
    return parser.parse_args()


def backup_configs(report):
    """Crée une sauvegarde des fichiers pipeline avant modifications"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_DIR / ts
    backup.mkdir(parents=True, exist_ok=True)

    files_to_backup = set()
    for imp in report.get("improvements", []):
        patch = imp.get("patch", {})
        fpath = patch.get("file")
        if fpath:
            files_to_backup.add(Path(fpath))

    # Backup du pipeline si auto-hook
    pipeline_file = WORKSPACE / "skills" / "alfred_cron" / "pipeline_orchestrator.py"
    if pipeline_file.exists():
        shutil.copy2(pipeline_file, backup / "pipeline_orchestrator.py.bak")

    for fpath in files_to_backup:
        if fpath.exists():
            shutil.copy2(fpath, backup / f"{fpath.name}.bak")

    return backup


def handle_auto_hook(args):
    """Détection et correction automatique du hook dans le prompt pipeline."""
    print(f"\n🔬 Auto-hook analysis...")

    trend = get_hook_score_trend()
    print(f"  Tendance : {trend.get('avg', 'N/A')}/10 sur {trend.get('total', 0)} vidéos")

    suggestion = suggest_hook_prompt_adjustment()

    if suggestion is None:
        print(f"  ✅ Score hook OK — aucun ajustement nécessaire.")
        return False

    print(f"  ⚠️  Hook faible détecté — ajustement recommandé :")
    for line in suggestion.split("\n"):
        print(f"     {line}")

    if not args.apply:
        print(f"\n  ⚠️  Dry-run — ajoutez --apply pour appliquer l'ajustement au pipeline.")
        print(f"  Exemple : python3 improve_pipeline.py --auto-hook --apply")
        return False

    # Backup avant modification
    pipeline_file = WORKSPACE / "skills" / "alfred_cron" / "pipeline_orchestrator.py"
    if pipeline_file.exists():
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = BACKUP_DIR / ts
        backup.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pipeline_file, backup / "pipeline_orchestrator.py.bak")
        print(f"\n  📦 Backup : {backup / 'pipeline_orchestrator.py.bak'}")

    applied = apply_hook_adjustment_to_pipeline(suggestion)
    if applied:
        print(f"  ✅ Ajustement hook appliqué au pipeline.")
        print(f"  Prochaine vidéo utilisera le prompt renforcé.")
        return True
    else:
        print(f"  ⚠️  Ajustement déjà appliqué ou fichier non trouvé.")
        return False


def main():
    args = parse_args()

    # Mode auto-hook seulement
    if args.auto_hook and not args.rapport:
        handle_auto_hook(args)
        return

    # Mode rapport
    if not args.rapport:
        print("❌ Spécifiez --rapport ou --auto-hook")
        sys.exit(1)

    rapport_path = Path(args.rapport)
    if not rapport_path.exists():
        print(f"❌ Rapport introuvable : {rapport_path}")
        sys.exit(1)

    report = json.loads(rapport_path.read_text())
    improvements = report.get("improvements", [])

    if not improvements:
        print("✅ Aucune amélioration suggérée.")
    else:
        print(f"\n📋 Améliorations à appliquer ({len(improvements)}):")
        for i, imp in enumerate(improvements, 1):
            print(f"\n  {i}. {imp['action']}")
            print(f"     Raison : {imp['reason']}")
            print(f"     Gain estimé : +{imp['impact']} pts")
            if imp.get("patch"):
                print(f"     → {imp['patch']['description']}")
                print(f"     → Fichier : {imp['patch']['file']}")
                print(f"     → Modif : {imp['patch']['change']}")

        if not args.apply:
            print(f"\n⚠️  Dry-run — aucune modification appliquée.")
            print(f"  Pour appliquer : ajoutez --apply")
            print(f"  Exemple : python3 improve_pipeline.py --rapport {rapport_path} --apply")
            return

        # Backup
        print(f"\n📦 Sauvegarde des configs...")
        backup_dir = backup_configs(report)
        print(f"  → {backup_dir}")

        # Appliquer les patches
        applied = 0
        for imp in improvements:
            if not imp.get("patch"):
                print(f"  ⏭️  '{imp['action']}' : pas de patch automatique")
                continue

            target = Path(imp["patch"]["file"])
            if not target.exists():
                print(f"  ❌ Fichier introuvable : {target}")
                continue

            content = target.read_text()
            old = imp["patch"]["old_text"]
            new = imp["patch"]["new_text"]

            if old in content:
                content = content.replace(old, new)
                target.write_text(content)
                print(f"  ✅ {imp['action']} → patch appliqué à {target.name}")
                applied += 1
            else:
                print(f"  ⚠️  {imp['action']} → old_text introuvable dans {target.name}")

        print(f"\n📊 {applied}/{len(improvements)} patches appliqués.")
        print(f"  Sauvegarde : {backup_dir}")

    # Auto-hook en complément
    if args.auto_hook:
        print()
        handle_auto_hook(args)


if __name__ == "__main__":
    main()