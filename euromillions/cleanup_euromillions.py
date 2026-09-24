#!/usr/bin/env python3
"""Cleanup utility for Euromillions pipeline."""

import os
import time
import argparse
from datetime import datetime, timedelta


def get_size_str(path: str) -> str:
    size = os.path.getsize(path)
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    else:
        return f"{size / (1024 * 1024):.1f} MB"


def cleanup(dry_run: bool = True, keep_days: int = 30):
    base = os.path.dirname(os.path.abspath(__file__))
    cutoff = datetime.now() - timedelta(days=keep_days)
    
    patterns = {
        'logs': ('logs', ['.log']),
        'tmp': ('', ['.tmp', '.temp', '.swp']),
        'cache': ('', ['.pyc', '.pyo']),
    }
    
    total_size = 0
    total_files = 0
    
    mode = "DRY RUN" if dry_run else "CLEANUP"
    print(f"[{mode}] Files older than {keep_days} days")
    print("-" * 40)
    
    for pattern_name, (subdir, extensions) in patterns.items():
        directory = os.path.join(base, subdir) if subdir else base
        if not os.path.isdir(directory):
            continue
        for f in os.listdir(directory):
            fpath = os.path.join(directory, f)
            if not os.path.isfile(fpath):
                continue
            ext = os.path.splitext(f)[1].lower()
            if ext in extensions:
                mtime = datetime.fromtimestamp(os.path.getmtime(fpath))
                if mtime < cutoff:
                    age = (datetime.now() - mtime).days
                    print(f"  {pattern_name}: {f} ({get_size_str(fpath)}, {age}d)")
                    total_files += 1
                    total_size += os.path.getsize(fpath)
                    if not dry_run:
                        os.remove(fpath)
    
    print("-" * 40)
    if total_files == 0:
        print("Nothing to clean")
    else:
        print(f"{total_files} files, {get_size_str(str(total_size))} freed")
        if dry_run:
            print("Run with --apply to execute")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Euromillions cleanup')
    parser.add_argument('--apply', action='store_true', help='Execute cleanup')
    parser.add_argument('--keep', type=int, default=30, help='Days to keep')
    args = parser.parse_args()
    cleanup(dry_run=not args.apply, keep_days=args.keep)
