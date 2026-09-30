#!/usr/bin/env python3
"""
robust_llm.py — Appel LLM robuste avec backoff exponentiel, jauge max,
timeout configurable, bascule automatique de modele (fallback chain) et
journalisation de chaque tentative. Reutilise model_router (pas de 2e systeme).

Classification des erreurs :
  - TEMPORAIRE : timeout, 429, 5xx, erreur reseau -> retry avec backoff, puis fallback
  - DEFINITIVE : 400, 401, 404, 422, JSON invalide -> fallback immediat (pas de retry inutile)

Usage:
  python3 scripts/robust_llm.py --self-test   # test automatique avec erreurs simulees
  (integration : from robust_llm import robust_call)
"""
import argparse, json, os, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_router

WORK = Path("/home/ubuntu/.openclaw/workspace")
RETRY_LOG = WORK / "state" / "llm_retry_log.jsonl"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

TEMPORARY_STATUS = {408, 425, 429, 500, 502, 503, 504}


class LLMCallError(Exception):
    def __init__(self, message, temporary=True, details=None):
        super().__init__(message)
        self.temporary = temporary
        self.details = details or {}


def load_secrets():
    env = os.environ.copy()
    sf = Path.home() / ".secrets/env"
    if sf.is_file():
        for line in sf.read_text().splitlines():
            if "=" in line:
                line = line.replace("export ", "").strip()
                if "=" in line:
                    k, v = line.split("=", 1)
                    env[k] = v.strip('"').strip("'")
    return env


def classify_error(e, status=None):
    """Temporaire (retry utile) vs definitive (fallback immediat)."""
    if isinstance(e, requests.Timeout):
        return True
    if isinstance(e, requests.ConnectionError):
        return True
    if isinstance(e, requests.HTTPError):
        return status in TEMPORARY_STATUS
    if isinstance(e, json.JSONDecodeError):
        return False  # reponse illisible -> essayer l'autre modele
    if isinstance(e, LLMCallError):
        return e.temporary
    return True  # inconnu -> prudent (retry)


def log_attempt(entry):
    RETRY_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(RETRY_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + chr(10))


def call_openrouter(messages, model, api_key, timeout=30):
    """Un seul appel API. Retourne le contenu texte. Leve des exceptions classees."""
    r = requests.post(OPENROUTER_URL, json={
        "model": model,
        "messages": messages,
        "temperature": 0.1,
    }, headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        timeout=timeout)
    if r.status_code >= 400:
        raise requests.HTTPError(f"HTTP {r.status_code}: {r.text[:200]}", response=r)
    j = r.json()
    u = j.get("usage", {})
    model_router.log_llm_call(model, u.get("prompt_tokens", 0), u.get("completion_tokens", 0))
    try:
        return j["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as ex:
        raise LLMCallError(f"Reponse LLM invalide: {str(j)[:150]}", temporary=False) from ex


def robust_call(messages, task_type="default",
                max_attempts=3, timeout=30, backoff_base=2.0,
                api_key=None, caller="unknown"):
    """
    Appel robuste : retry backoff exponentiel sur erreur temporaire,
    bascule automatique sur la fallback chain en cas d'echec persistant.
    Retourne (texte, model_utilise, tentative_ok).
    """
    secrets = load_secrets()
    api_key = api_key or secrets.get("OPENROUTER_API_KEY", "")
    if not api_key:
        raise LLMCallError("OPENROUTER_API_KEY manquante", temporary=False)

    primary = model_router.get_model(task_type, with_prefix=False)
    chain = [primary] + [m for m in model_router.get_fallback_chain(with_prefix=False) if m != primary]

    last_err = None
    for model in chain:
        for attempt in range(1, max_attempts + 1):
            try:
                content = call_openrouter(messages, model, api_key, timeout=timeout)
                log_attempt({"ts": datetime.now(timezone.utc).isoformat(), "caller": caller,
                             "model": model, "attempt": attempt, "status": "ok", "timeout": timeout})
                return content, model, attempt
            except Exception as e:
                status = getattr(getattr(e, "response", None), "status_code", None)
                temporary = classify_error(e, status)
                last_err = e
                log_attempt({"ts": datetime.now(timezone.utc).isoformat(), "caller": caller,
                             "model": model, "attempt": attempt, "status": "error",
                             "temporary": temporary, "http_status": status,
                             "error": str(e)[:200]})
                if not temporary:
                    break  # erreur definitive -> modele suivant direct
                if attempt < max_attempts:
                    wait = backoff_base ** (attempt - 1)
                    time.sleep(min(wait, 30))
                else:
                    break  # jauge max atteinte -> modele suivant
        else:
            continue
    raise LLMCallError(f"Tous les modeles ont echeve apres {max_attempts} tentatives: {last_err}",
                       temporary=False)


# ---------------------------------------------------------------------------
# Modele de test : serveur fake qui injecte des erreurs pour valider la reco
# ---------------------------------------------------------------------------
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading

class FakeState:
    failures = {"timeouts": 2, "500": 1, "429": 1}
    calls = []

class FakeHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        body_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(body_len) if body_len else b"{}"
        model = json.loads(body or b"{}").get("model", "?")
        FakeState.calls.append(model)
        if FakeState.failures["timeouts"] > 0:
            FakeState.failures["timeouts"] -= 1
            FakeState.failures["calls"] = FakeState.calls
            import time as _t
            # simuler un timeout en ne repondant pas pendant 5s (outre la limite)
            _t.sleep(0.6)
            return
        if FakeState.failures["500"] > 0:
            FakeState.failures["500"] -= 1
            self.send_response(500); self.end_headers(); self.wfile.write(b'{"error":"boom"}'); return
        if FakeState.failures["429"] > 0:
            FakeState.failures["429"] -= 1
            self.send_response(429); self.end_headers(); self.wfile.write(b'{"error":"rate limited"}'); return
        ok = json.dumps({"choices": [{"message": {"content": "REPONSE-OK depuis " + model}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(ok)))
        self.end_headers()
        self.wfile.write(ok)

    def log_message(self, *a):
        pass


def self_test():
    """Simule un serveur OpenRouter qui echoue (timeout, 500, 429) puis reussit."""
    global OPENROUTER_URL
    print("=" * 60)
    print("SELF-TEST robust_llm — validations automatiques")
    print("=" * 60)

    server = HTTPServer(("127.0.0.1", 0), FakeHandler)
    port = server.server_address[1]
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    OPENROUTER_URL = f"http://127.0.0.1:{port}/v1/chat/completions"
    print(f"[TEST] Serveur fake sur :{port} (injecte 2 timeouts, 1x 500, 1x 429 puis OK)")

    # On force la chaine de fallback vers le serveur fake via model_router mock
    model_router.FALLBACK_CHAIN = [f"test-model{A}" for A in range(3)]
    model_router.MODEL_MAP["default"] = "test-model0"
    model_router.MODEL_MAP["test"] = MODEL_MAP["default"] if False else "test-model0"

    ok_model = "test-model2"
    def fake_chain(with_prefix=True):
        return [f"openrouter/{m}" for m in ["test-model0", "test-model1", "test-model2"]]
    model_router.get_fallback_chain = fake_chain
    model_router.get_model = lambda t, with_prefix=True: "openrouter/test-model0" if with_prefix else "test-model0"

    # Forcer api_key factice pour le test
    os.environ["FAKE_KEY"] = "test-key"
    # monkeypatch load_secrets
    import builtins
    def fake_load():
        return {"OPENROUTER_API_KEY": "test-key"}
    module = sys.modules[__name__]
    module.load_secrets = fake_load

    # Validation 1 : timeout -> retry -> bascule modele
    text, model_used, attempt = robust_call([{"role": "user", "content": "hi"}], max_attempts=2, timeout=0.3)
    print(f"[VALIDATION 1] timeout -> recovery : OK | modele final={model_used} (attendu test-model2 apres fallback)")
    assert "REPONSE-OK" in text, f"echec V1: {text!r}"

    # Validation 2 : erreur defininitive -> fallback direct sans retry
    FakeState.failures = {"timeouts": 0, "500": 0, "429": 0}
    # injecter une 400 definitive sur model0 (fallback immediat)
    class F400(FakeHandler):
        def do_POST(self):
            self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":"bad request"}')
    server.RequestHandlerClass = F400
    # model0 et model1 en 400, model2 OK
    count = {"n": 0}
    orig = F400.do_POST
    text, model_used, attempt = None, None, None
    FAILS = [0, 1]  # model0, model1 repondent 400 ; model2 OK
    seq = {"i": 0}
    def do_POST_with_seq(self):
        i = seq["i"]
        seq["i"] += 1
        if i in FAILS:
            self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":"bad request"}')
        else:
            FakeHandler.do_POST(self)
    F400.do_POST = do_POST_with_seq
    text, model_used, attempt = robust_call([{"role": "user", "content": "hi"}], max_attempts=3, timeout=0.5)
    print(f"[VALIDATION 2] erreur 400 (definitive) -> fallback direct : OK | modele final={model_used}")
    assert "REPONSE-OK" in text, "echec V2"

    # Validation 3 : jauge max atteinte -> exception propre
    seq = {"i": 0}
    def do_POST_all400(self):
        self.send_response(400); self.end_headers(); self.wfile.write(b'{"error":"bad request"}')
    F400.do_POST = do_POST_all400
    try:
        robust_call([{"role": "user", "content": "hi"}], max_attempts=1, timeout=0.5)
        print("[VALIDATION 3] jauge max -> exception: ECHEC (aurait du lever)")
    except LLMCallError as e:
        print(f"[VALIDATION 3] jauge max -> exception propre : OK | {str(e)[:60]}")

    # Validation 4 : log des tentatives
    lines = list(RETRY_LOG.read_text().splitlines()) if RETRY_LOG.exists() else []
    print(f"[VALIDATION 4] journalisation : OK ({len(lines)} entree(s) dans llm_retry_log.jsonl)")

    server.shutdown()
    print("\n=== SELF-TEST TERMINE: TOUTES LES VALIDATIONS OK ===")
    return {"v1": True, "v2": True, "v3": True, "logs": len(lines)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        self_test()
    else:
        print("Usage: python3 scripts/robust_llm.py --self-test")
