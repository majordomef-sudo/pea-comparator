#!/usr/bin/env python3
"""
alfred_self_learn.py — Auto-amélioration nocturne d'Alfred 🎩

Analyse les journaux de la journée, extrait les erreurs, décisions et leçons,
et met à jour les fichiers de mémoire pour que je m'améliore chaque nuit.
"""
import json, os, re, shutil
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
MEMORY_DIR = WORKSPACE / "memory"
STATE_DIR = WORKSPACE / "state"
REFLECTION_DIR = STATE_DIR / "auto-reflection"
LEARNINGS_FILE = MEMORY_DIR / "agent_learnings.json"
ERRORS_FILE = REFLECTION_DIR / "errors.json"
IMPROVEMENTS_FILE = REFLECTION_DIR / "improvements.log"

def ensure_dirs():
    for d in [REFLECTION_DIR]:
        d.mkdir(parents=True, exist_ok=True)

def load_learnings():
    if LEARNINGS_FILE.exists():
        try:
            with open(LEARNINGS_FILE) as f:
                return json.load(f)
        except:
            pass
    return {"alfred": []}

def save_learnings(data):
    with open(LEARNINGS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def load_errors():
    if ERRORS_FILE.exists():
        try:
            with open(ERRORS_FILE) as f:
                return json.load(f)
        except:
            pass
    return []

def save_errors(data):
    with open(ERRORS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def find_today_memory():
    """Trouve le fichier de notes du jour."""
    today = datetime.now().strftime("%Y-%m-%d")
    for f in MEMORY_DIR.glob(f"{today}*.md"):
        return f
    return None

def extract_learnings_from_text(text):
    """Extrait les patterns d'apprentissage du texte."""
    learnings = []
    
    # Patterns d'erreur
    error_patterns = [
        r"(?:erreur|bug|fail|échec|problème|cassait|corrompu|timeout):?\s*([^\n]+)",
        r"(?:fix|corrigé|réparé|solution):?\s*([^\n]+)",
    ]
    for pattern in error_patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            learnings.append({
                "learning": m.group(1).strip()[:200],
                "category": "failure",
                "source": "auto-extracted"
            })
    
    # Patterns de décision
    decision_patterns = [
        r"(?:décision|décidé|choix|option retenue):?\s*([^\n]+)",
        r"(?:Eric|on).{0,20}(?:veut|décide|choisit|préfère|dit non|dit oui):?\s*([^\n]+)",
    ]
    for pattern in decision_patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            learnings.append({
                "learning": m.group(1).strip()[:200],
                "category": "decision",
                "source": "auto-extracted"
            })
    
    return learnings

def scan_nightly_reports():
    """Analyse les rapports nocturnes du jour."""
    reports = []
    diag_file = REFLECTION_DIR / "nightly_diagnostic.json"
    if diag_file.exists():
        with open(diag_file) as f:
            try:
                reports.append(("diagnostic", json.load(f)))
            except:
                pass
    return reports

def run():
    ensure_dirs()
    print("🧠 Auto-apprentissage nocturne d'Alfred...")
    
    learnings = load_learnings()
    errors = load_errors()
    
    # 1. Analyser les notes du jour
    memory_file = find_today_memory()
    if memory_file:
        print(f"  📖 Analyse de {memory_file.name}...")
        text = memory_file.read_text()
        new_learnings = extract_learnings_from_text(text)
        
        # Ajouter les nouveaux learnings
        alfred_learnings = learnings.get("alfred", [])
        existing = {l["learning"] for l in alfred_learnings if isinstance(l, dict)}
        for nl in new_learnings:
            if nl["learning"] not in existing:
                nl["timestamp"] = datetime.now().isoformat()
                nl["confidence"] = 0.7
                alfred_learnings.insert(0, nl)
                existing.add(nl["learning"])
                print(f"    📝 Nouveau: {nl['learning'][:60]}...")
        
        learnings["alfred"] = alfred_learnings[:200]  # Garder max 200
        save_learnings(learnings)
    
    # 2. Générer le rapport de progression
    report = {
        "timestamp": datetime.now().isoformat(),
        "memory_file": memory_file.name if memory_file else None,
        "total_learnings": len(learnings.get("alfred", [])),
        "errors_count": len(errors),
        "recent_learnings": learnings.get("alfred", [])[:5],
        "summary": ""
    }
    
    # 3. Écrire le rapport dans improvements.log
    with open(IMPROVEMENTS_FILE, "a") as f:
        f.write(f"\n--- {datetime.now().isoformat()} ---\n")
        f.write(f"Fichier analysé: {memory_file.name if memory_file else 'aucun'}\n")
        f.write(f"Total learnings: {report['total_learnings']}\n")
        f.write(f"Erreurs: {report['errors_count']}\n")
    
    print(f"  ✅ {report['total_learnings']} learnings, {report['errors_count']} erreurs")
    print("🧠 Auto-apprentissage terminé")

if __name__ == "__main__":
    run()
