#!/usr/bin/env python3
"""
preflight.py — Vérification des capacités avant production
Inspiré d'OpenMontage : audite l'environnement et présente un rapport.
"""

import os, sys, json, shutil, subprocess
from pathlib import Path
WORKSPACE = Path(os.environ.get("ALFRED_WORKSPACE", str(Path(__file__).resolve().parent.parent)))


def check_tool(name: str, cmd: list) -> dict:
    """Vérifie qu'un outil CLI est dispo et retourne sa version."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5, check=False)
        version = r.stdout.strip().split("\n")[0][:80] if r.stdout else r.stderr.strip()[:80]
        return {"available": r.returncode == 0, "version": version or None}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"available": False, "version": None}


def check_python_module(module: str) -> dict:
    """Vérifie qu'un module Python est installé."""
    try:
        import importlib
        m = importlib.import_module(module)
        v = getattr(m, "__version__", None)
        return {"available": True, "version": v}
    except ImportError:
        return {"available": False, "version": None}


def check_api_key(key_name: str, secrets: dict) -> dict:
    """Vérifie qu'une clé API est configurée."""
    val = secrets.get(key_name, os.environ.get(key_name, ""))
    return {"available": bool(val) and len(val) > 10, "prefix": val[:8] + "..." if val else None}


def load_secrets():
    """Charge le fichier .secrets/env."""
    secrets_path = Path.home() / ".secrets" / "env"
    s = {}
    if secrets_path.exists():
        with open(secrets_path) as f:
            for line in f:
                if "=" in line:
                    line = line.replace("export ", "").strip()
                    k, v = line.split("=", 1)
                    s[k] = v.strip('"').strip("'")
    return s


def run_preflight() -> dict:
    """Exécute la vérification complète et retourne un rapport structuré."""
    secrets = load_secrets()

    report = {
        "system": {
            "python": sys.version.split()[0],
            "platform": sys.platform,
        },
        "tools": {
            "ffmpeg": check_tool("ffmpeg", ["ffmpeg", "-version"]),
            "ffprobe": check_tool("ffprobe", ["ffprobe", "-version"]),
            "whisper": check_python_module("whisper"),
        },
        "python_modules": {
            "PIL (Pillow)": check_python_module("PIL"),
            "edge_tts": check_python_module("edge_tts"),
            "requests": check_python_module("requests"),
            "numpy": check_python_module("numpy"),
            "PyYAML": check_python_module("yaml"),
            "json_repair": check_python_module("json_repair"),
            "Google OAuth": check_python_module("google.oauth2.credentials"),
        },
        "apis": {
            "openrouter": check_api_key("OPENROUTER_API_KEY", secrets),
            "elevenlabs": check_api_key("ELEVENLABS_API_KEY", secrets),
            "leonardo": check_api_key("LEONARDO_API_KEY", secrets),
            "piapi": check_api_key("PIAPI_API_KEY", secrets),
            "zernio": check_api_key("ZERNIO_API_KEY", secrets),
        },
        "disk": {},
        "status": "unknown",
        "blockers": [],
        "warnings": [],
        "degradations": [],
    }

    required_files = [WORKSPACE / "pipeline/background_music.mp3", WORKSPACE / "skills/alfred_video_pipeline/alfred_brand_icon.png", WORKSPACE / "skills/youtube_upload/upload.py", WORKSPACE / "skills/alfred_video_pipeline/PLAYBOOK_NEURO_FINANCE.md", WORKSPACE / "skills/alfred_video_pipeline/EDITORIAL_CHARTER_NEURO_FINANCE.md", WORKSPACE / "skills/alfred_video_pipeline/SEMANTIC_LEXICON_NEURO_FINANCE.md"]
    for required_file in required_files:
        if not required_file.exists():
            report["blockers"].append(f"Fichier indispensable manquant: {required_file}")

    clip_count = len(list((Path.home() / "output/raw_clips").rglob("*.mp4")))
    if clip_count < 4:
        report["blockers"].append(f"Réserve de clips insuffisante: {clip_count}/4")
    # Disk space check
    stat = shutil.disk_usage("/")
    report["disk"] = {
        "total_gb": round(stat.total / (1024**3), 1),
        "free_gb": round(stat.free / (1024**3), 1),
        "free_percent": round(stat.free / stat.total * 100, 1),
    }
    if stat.free < 1024**3:  # < 1 Go
        report["blockers"].append("Disk space < 1 Go — peut bloquer l'encodage")
    elif stat.free < 3 * 1024**3:
        report["warnings"].append(f"Disk space limité ({report['disk']['free_gb']} Go)")

    # Blockers — éléments critiques qui bloquent la prod
    if not report["apis"]["openrouter"]["available"]:
        report["blockers"].append("Clé OPENROUTER_API_KEY indispensable pour générer et valider le script")
    if not report["tools"]["ffmpeg"]["available"]:
        report["blockers"].append("ffmpeg est requis pour la composition vidéo")
    if not report["tools"]["ffprobe"]["available"]:
        report["blockers"].append("ffprobe est requis pour la validation")

    for name, info in report["python_modules"].items():
        if not info["available"]:
            report["blockers"].append(f"Module Python requis manquant: {name}")

    # Warnings — fonctionnalités réduites
    if not report["tools"]["whisper"]["available"]:
        report["warnings"].append("Whisper non installé — sous-titres approximatifs seulement")

    # Dégradations — fonctionnalités optionnelles manquantes
    if not report["apis"]["piapi"]["available"]:
        report["degradations"].append("Pas de clé PiAPI — images générées désactivées, fallback clips")
    if not report["apis"]["elevenlabs"]["available"]:
        report["degradations"].append("Pas de clé ElevenLabs — TTS Azure edge-tts seulement")

    # Statut global
    if report["blockers"]:
        report["status"] = "blocked"
    elif report["warnings"]:
        report["status"] = "degraded"
    else:
        report["status"] = "ready"

    return report


def print_report(report: dict):
    """Affiche le rapport de preflight formaté."""
    status_icon = {"ready": "✅", "degraded": "⚠️", "blocked": "❌"}
    print(f"\n{'='*50}")
    print(f"  PREFLIGHT — {status_icon.get(report['status'], '❓')} {report['status'].upper()}")
    print(f"{'='*50}")

    print(f"\n📦 Système : Python {report['system']['python']} / {report['system']['platform']}")
    print(f"💾 Disque : {report['disk']['free_gb']} Go libres / {report['disk']['total_gb']} Go")

    print(f"\n🔧 Outils :")
    for name, info in report["tools"].items():
        icon = "✅" if info["available"] else "❌"
        ver = f" ({info['version']})" if info.get("version") else ""
        print(f"  {icon} {name}{ver}")

    print(f"\n📦 Modules Python :")
    for name, info in report["python_modules"].items():
        icon = "✅" if info["available"] else "❌"
        ver = f" ({info['version']})" if info.get("version") else ""
        print(f"  {icon} {name}{ver}")

    print(f"\n🔑 APIs :")
    for name, info in report["apis"].items():
        icon = "✅" if info["available"] else "❌"
        print(f"  {icon} {name}")

    if report["blockers"]:
        print(f"\n❌ BLOCKERS :")
        for b in report["blockers"]:
            print(f"  • {b}")

    if report["warnings"]:
        print(f"\n⚠️  WARNINGS :")
        for w in report["warnings"]:
            print(f"  • {w}")

    if report["degradations"]:
        print(f"\n🔶 DÉGRADATIONS :")
        for d in report["degradations"]:
            print(f"  • {d}")

    print()


def check_can_produce(report: dict) -> bool:
    """Retourne True si la production peut commencer."""
    return report["status"] != "blocked"


if __name__ == "__main__":
    r = run_preflight()
    print_report(r)
    sys.exit(0 if check_can_produce(r) else 1)
