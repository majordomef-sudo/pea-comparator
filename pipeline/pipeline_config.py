#!/usr/bin/env python3
"""Config centralisee + secrets + GC temp."""
import os,glob,time,shutil
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
WORKSPACE  = Path(os.environ.get("ALFRED_WORKSPACE",str(Path.home()/".openclaw"/"workspace")))

_SECRETS=None; _CONFIG=None

def load_secrets():
    global _SECRETS
    if _SECRETS: return _SECRETS
    s={}; p=Path.home()/".secrets"/"env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line:
                line=line.replace("export ","").strip()
                k,v=line.split("=",1); s[k]=v.strip('"').strip("'")
    _SECRETS=s; return s

def load_config():
    global _CONFIG
    if _CONFIG: return _CONFIG
    _CONFIG={}; cpath=SCRIPT_DIR/"pipeline_config.yaml"
    if cpath.exists():
        import yaml; _CONFIG=yaml.safe_load(cpath.read_text()) or {}
    return _CONFIG

def cfg(*keys,default=None):
    c=load_config()
    for k in keys:
        if isinstance(c,dict): c=c.get(k,{})
        else: return default
    return c if c!={} else default

def resv(key,*sub):
    r=cfg("paths",key,*sub,default="")
    return (WORKSPACE/r).resolve() if r else WORKSPACE

def _strip_prefix(mid):
    """Enleve le prefix openrouter/ pour les appels API directs."""
    if mid.startswith("openrouter/"):
        return mid[len("openrouter/"):]
    return mid

def model_main():
    return _strip_prefix(os.environ.get("MODEL_PIPELINE",cfg("llm","script_provider",default="deepseek/deepseek-v4.1-flash")))
def model_fallback():
    return _strip_prefix(cfg("llm","script_fallback",default="google/gemma-4-26b-a4b-it"))
def forbidden_words():
    return cfg("forbidden","forbidden_words",default=[])
def guru_blacklist():
    return cfg("forbidden","guru_blacklist",default=[])
def phonetic_fixes():
    return cfg("phonetic_fixes",default={})
def default_tags():
    return cfg("youtube","default_tags",default=[])
def default_hashtags():
    return cfg("youtube","default_hashtags",default="\n#NeuroFinance #FinanceComportementale #Investissement #PEA #ETF")
def desc_template():
    return cfg("templates","rich_description",default="")
def playlist_id():
    return cfg("youtube","playlist_id",default="")
def upload_py():
    return resv("upload_script")
def sub_topics():
    return cfg("topics","rotation",default=[])

def gc_tmp(max_age=24):
    now=time.time();removed=0
    for d in glob.glob("/tmp/alfred_pipeline_*"):
        if now-os.path.getmtime(d)>max_age*3600:
            shutil.rmtree(d,ignore_errors=True);removed+=1
    if removed: print(f"[CONFIG] GC: {removed} dossiers > {max_age}h")
