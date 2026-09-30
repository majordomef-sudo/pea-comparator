#!/usr/bin/env python3
"""pipeline_cleanup.py — Cleanup temp files, old archives, stale locks.

Sections (ordre d'execution) :
  1. /tmp/alfred_pipeline_*        > 48 h
  2. ~/output/archive/PROD_*.mp4   > 30 j
  3. ~/output/logs/*.log           > 60 j
  4. stale lock /tmp/alfred_pipeline.lock
  5. dossiers de staging/quarantaine ~/.output_purge_*, ~/.trash_*, ~/.purge_*  > 7 j   [ajout 2026-09-30]
  6. medias des runs echoues ~/.openclaw/workspace/failures/*  > 30 j (JSON/txt conserves)  [ajout 2026-09-30]
  7. detection des sauvegardes recursives (dossier _backup* contenant une copie de lui-meme)  [ajout 2026-09-30]

Usage : pipeline_cleanup.py [--dry-run]
"""
import os, sys, time, shutil
from pathlib import Path
from datetime import datetime, timedelta

HOME = Path.home()
OUTPUT = HOME / "output"
TMP = Path("/tmp")
WORKSPACE = HOME / ".openclaw" / "workspace"
MAX_ARCHIVE_AGE_DAYS = 30
MAX_TEMP_AGE_HOURS = 48
STAGING_MAX_AGE_DAYS = 7      # ~/.trash_*, ~/.output_purge_*, ~/.purge_*
FAILURES_MAX_AGE_DAYS = 30    # medias des runs echoues
MEDIA_SUFFIXES = (".mp4", ".mov", ".mkv", ".wav", ".mp3", ".ass", ".png", ".jpg")

DRY_RUN = "--dry-run" in sys.argv


def _size(p: Path) -> int:
    try:
        if p.is_file():
            return p.stat().st_size
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except OSError:
        return 0


def _rm(p: Path) -> bool:
    try:
        if DRY_RUN:
            return True
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
        return True
    except Exception as e:
        print(f"[CLEAN] Failed {p}: {e}")
        return False


def cleanup():
    cleaned = 0
    freed = 0

    # 1. Clean old temp pipeline dirs
    for d in TMP.glob("alfred_pipeline_*"):
        if d.is_dir():
            age_h = (time.time() - d.stat().st_mtime) / 3600
            if age_h > MAX_TEMP_AGE_HOURS:
                size = _size(d)
                if _rm(d):
                    freed += size
                    cleaned += 1
                    print(f"[CLEAN] Removed {d.name} ({size//1024//1024}MB, {age_h:.0f}h old)")

    # 2. Clean old archived videos (>30 days)
    archive = OUTPUT / "archive"
    if archive.exists():
        cutoff = time.time() - MAX_ARCHIVE_AGE_DAYS * 86400
        for f in archive.glob("PROD_*.mp4"):
            if f.stat().st_mtime < cutoff:
                size = _size(f)
                if _rm(f):
                    freed += size
                    cleaned += 1
                    print(f"[CLEAN] Archived {f.name} ({size//1024//1024}MB)")

    # 3. Clean old logs (>60 days)
    logdir = OUTPUT / "logs"
    if logdir.exists():
        cutoff = time.time() - 60 * 86400
        for f in logdir.glob("*.log"):
            if f.stat().st_mtime < cutoff:
                if _rm(f):
                    cleaned += 1
                    print(f"[CLEAN] Old log {f.name}")

    # 4. Remove stale lockfile
    lock = TMP / "alfred_pipeline.lock"
    if lock.exists():
        try:
            pid = int(lock.read_text().strip())
            os.kill(pid, 0)
        except (OSError, ValueError, ProcessLookupError):
            if _rm(lock):
                print("[CLEAN] Stale lock removed")

    # 5. Staging / quarantaine (dossiers de purge oublies)
    staging_cutoff = time.time() - STAGING_MAX_AGE_DAYS * 86400
    for pattern in (".output_purge_*", ".trash_*", ".purge_*"):
        for d in HOME.glob(pattern):
            try:
                if not d.is_dir():
                    continue
                if d.stat().st_mtime >= staging_cutoff:
                    continue
                age_d = (time.time() - d.stat().st_mtime) / 86400
                size = _size(d)
                if _rm(d):
                    freed += size
                    cleaned += 1
                    print(f"[CLEAN] Staging supprime {d.name} ({size//1024//1024}MB, {age_d:.0f}j)")
            except OSError as e:
                print(f"[CLEAN] Failed {d}: {e}")

    # 6. Medias des runs echoues (on garde les .json / .txt de diagnostic)
    failures = WORKSPACE / "failures"
    if failures.exists():
        fail_cutoff = time.time() - FAILURES_MAX_AGE_DAYS * 86400
        for run in sorted(failures.iterdir()):
            if not run.is_dir():
                continue
            try:
                if run.stat().st_mtime >= fail_cutoff:
                    continue
            except OSError:
                continue
            for item in list(run.iterdir()):
                try:
                    if item.is_dir():
                        size = _size(item)
                        if _rm(item):
                            freed += size
                            cleaned += 1
                            print(f"[CLEAN] failures/{run.name}/{item.name} ({size//1024//1024}MB)")
                    elif item.suffix.lower() in MEDIA_SUFFIXES:
                        size = _size(item)
                        if _rm(item):
                            freed += size
                            cleaned += 1
                            print(f"[CLEAN] failures/{run.name}/{item.name} ({size//1024//1024}MB)")
                except OSError as e:
                    print(f"[CLEAN] Failed {item}: {e}")

    # 7. Detection des sauvegardes recursives (report seul, pas de suppression auto)
    webroot = Path("/var/www/html")
    if webroot.exists():
        try:
            for top in webroot.iterdir():
                if not top.is_dir() or not top.name.startswith("_backup"):
                    continue
                nested = [c for c in top.iterdir() if c.is_dir() and c.name.startswith("_backup")]
                if nested:
                    print(f"[ALERT] Sauvegarde recursive : {top} contient {len(nested)} copie(s) de sauvegarde imbriquee(s) -> a purger manuellement")
        except OSError as e:
            print(f"[ALERT] Scan sauvegardes impossible: {e}")

    tag = " (DRY-RUN)" if DRY_RUN else ""
    print(f"[CLEAN] Total{tag}: {cleaned} items, {freed//1024//1024}MB freed")
    return cleaned, freed


if __name__ == "__main__":
    cleanup()

