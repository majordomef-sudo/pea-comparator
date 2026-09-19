# -*- coding: utf-8 -*-
import importlib.util, time, random

spec = importlib.util.spec_from_file_location("es", "/home/ubuntu/.openclaw/workspace/scripts/etf_scrapler.py")
es = importlib.util.module_from_spec(spec)
spec.loader.exec_module(es)

etfs = es.load()
missing = [e for e in etfs if e.get("isin", "")[:2] != "BG" and not e.get("peap")]
print(f"TOTAL {len(etfs)} | sans peap: {len(missing)}", flush=True)

done = 0
fail = 0
ok_403_pause = 0
i = 0
while i < len(missing):
    e = missing[i]
    isin = e["isin"]
    d = es.fetch_fundamentals(isin)
    if not d or "error" in d:
        err = d.get("error") if isinstance(d, dict) else str(d)
        fail += 1
        if "403" in str(err):
            ok_403_pause += 1
            print(f"403 aigu (cumule={ok_403_pause}) -> pause 30 min", flush=True)
            time.sleep(1800)
            ok_403_pause = 0
            continue  # retenter CE meme ISIN
        print(f"[{i+1}/{len(missing)}] {isin} -> {err}", flush=True)
        i += 1
        time.sleep(random.uniform(4, 8))
        continue
    retry = 0
    upd = False
    for k in ("encours_mio","encours_devise","devise","distribution","date_creation",
              "indice","volatilite","replication","repl_method","emetteur_full","domicile","hedge","peap"):
        if d.get(k) not in (None, "", "N/A", "?"):
            if e.get(k) in (None, "", "N/A", "?"):
                e[k] = d[k]
                upd = True
    done += 1
    print(f"[{i+1}/{len(missing)}] {isin} -> peap={d.get('peap')} upd={upd}", flush=True)
    i += 1
    time.sleep(random.uniform(3, 6))
    # Vague : tous les 100 OK, pause 10 min pour rester sous le quota
    if done > 0 and done % 100 == 0:
        print(f"Vague {done} terminee -> pause 10 min", flush=True)
        time.sleep(600)

es.save(etfs)
print(f"SAVED done={done} fail={fail} (sauvegarde source + live)", flush=True)
try:
    es.build_min()
    print("build_min OK (min + cache-bust + live)", flush=True)
except Exception as ex:
    print("build_min ERR:", str(ex)[:120], flush=True)
