#!/usr/bin/env python3
"""
oauth_check.py — Vérifie la validité du token OAuth YouTube avant upload.
Si le token est expiré et non renouvelable → alerte Telegram + sauvegarde dans failures/.
"""
import os
import json
import time
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

WORKSPACE = Path(os.environ.get("ALFRED_WORKSPACE", str(Path.home() / ".openclaw" / "workspace")))
OUTPUT_DIR = Path.home() / "output"
FAILURE_DIR = OUTPUT_DIR / "failures"
TOKEN_FILE = Path.home() / ".secrets" / "youtube_token.json"


def send_telegram(msg):
    """Envoie un message Telegram sans dépendre de l'orchestrateur."""
    try:
        secrets_env = Path.home() / ".secrets" / "env"
        secrets = {}
        if secrets_env.exists():
            for line in secrets_env.read_text().splitlines():
                if "=" in line:
                    line = line.replace("export ", "").strip()
                    k, v = line.split("=", 1)
                    secrets[k] = v.strip('"').strip("'")
        bt = secrets.get("TELEGRAM_BOT_TOKEN")
        ci = secrets.get("TELEGRAM_CHAT_ID")
        if bt and ci:
            import requests
            requests.post(
                f"https://api.telegram.org/bot{bt}/sendMessage",
                data={"chat_id": ci, "text": f"🔐 [OAUTH] {msg}"},
                timeout=10
            )
    except Exception as e:
        print(f"[OAUTH] Telegram failed: {e}")


def check_oauth_valid():
    """
    Vérifie la validité du token OAuth YouTube.
    Retourne {valid: bool, message: str, renewed: bool}
    """
    result = {"valid": False, "message": "", "renewed": False}

    if not TOKEN_FILE.exists():
        result["message"] = "Token OAuth YouTube introuvable"
        print(f"[OAUTH] {result['message']}")
        return result

    try:
        token_data = json.loads(TOKEN_FILE.read_text())
    except Exception as e:
        result["message"] = f"Token OAuth corrompu: {e}"
        print(f"[OAUTH] {result['message']}")
        return result

    # Vérifier l'expiration du access_token
    # Le token OAuth2 stocke généralement 'expiry' ou 'expires_at'
    expires_at = token_data.get("expires_at") or token_data.get("expiry")
    access_token = token_data.get("access_token") or token_data.get("token")

    if not access_token:
        result["message"] = "Token OAuth sans access_token"
        print(f"[OAUTH] {result['message']}")
        return result

    # Si on a une date d'expiration
    if expires_at:
        now_ts = time.time()
        if isinstance(expires_at, str):
            try:
                expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError) as expiry_error:
                result["message"] = f"Date d’expiration OAuth invalide: {expiry_error}"
                print(f"[OAUTH] {result['message']}")
                return result

        if now_ts > expires_at - 300:  # 5 minutes de marge
            # Token expiré, tentative de refresh
            refresh_token = token_data.get("refresh_token")
            if refresh_token:
                renewed = _try_refresh_token(refresh_token)
                if renewed:
                    result["valid"] = True
                    result["renewed"] = True
                    result["message"] = "Token renouvelé avec succès"
                    print(f"[OAUTH] {result['message']}")
                    return result

            result["message"] = f"Token expiré le {datetime.fromtimestamp(expires_at).isoformat()} — refresh impossible"
            print(f"[OAUTH] {result['message']}")
            return result

    # Test actif : appel à l'API YouTube pour vérifier que le token fonctionne
    try:
        test_result = subprocess.run([
            "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}",
            "-H", f"Authorization: Bearer {access_token}",
            "https://www.googleapis.com/youtube/v3/channels?part=id&mine=true"
        ], capture_output=True, text=True, timeout=15, check=False)
        if test_result.returncode != 0:
            result["message"] = f"Échec réseau OAuth (curl {test_result.returncode}): {test_result.stderr.strip()[-300:]}"
            print(f"[OAUTH] {result['message']}")
            return result

        if test_result.stdout.strip() == "200":
            result["valid"] = True
            result["message"] = "Token OAuth YouTube valide"
            print(f"[OAUTH] {result['message']}")
        elif test_result.stdout.strip() == "401":
            # Token invalide, tenter refresh
            refresh_token = token_data.get("refresh_token")
            if refresh_token:
                renewed = _try_refresh_token(refresh_token)
                if renewed:
                    result["valid"] = True
                    result["renewed"] = True
                    result["message"] = "Token renouvelé après 401"
                    print(f"[OAUTH] {result['message']}")
                    return result
            result["message"] = "Token OAuth invalide (401) — refresh impossible"
            print(f"[OAUTH] {result['message']}")
        else:
            result["message"] = f"API YouTube: HTTP {test_result.stdout.strip()}"
            print(f"[OAUTH] {result['message']}")
    except Exception as e:
        result["message"] = f"Erreur vérification OAuth: {e}"
        print(f"[OAUTH] {result['message']}")

    return result


def _try_refresh_token(refresh_token):
    """Tente de rafraîchir le token OAuth."""
    try:
        token_data = json.loads(TOKEN_FILE.read_text())
        secrets_env = Path.home() / ".secrets" / "env"
        secrets = {}
        if secrets_env.exists():
            for line in secrets_env.read_text().splitlines():
                if "=" in line:
                    line = line.replace("export ", "").strip()
                    k, v = line.split("=", 1)
                    secrets[k] = v.strip('"').strip("'")

        client_id = secrets.get("YOUTUBE_CLIENT_ID") or secrets.get("GOOGLE_CLIENT_ID") or token_data.get("client_id")
        client_secret = secrets.get("YOUTUBE_CLIENT_SECRET") or secrets.get("GOOGLE_CLIENT_SECRET") or token_data.get("client_secret")

        if not client_id or not client_secret:
            print("[OAUTH] Refresh impossible: client_id/client_secret manquants")
            return False

        result = subprocess.run([
            "curl", "-s", "-X", "POST",
            "https://oauth2.googleapis.com/token",
            "-d", f"client_id={client_id}",
            "-d", f"client_secret={client_secret}",
            "-d", f"refresh_token={refresh_token}",
            "-d", "grant_type=refresh_token"
        ], capture_output=True, text=True, timeout=15, check=False)

        if result.returncode == 0:
            response_data = json.loads(result.stdout)
            access_token = response_data.get("access_token")
            if not access_token:
                print(
                    f"[OAUTH] Réponse de renouvellement invalide: "
                    f"{result.stdout[:200]}"
                )
                return False

            new_token = {**token_data, **response_data}
            new_token["token"] = access_token
            new_token["refresh_token"] = refresh_token
            new_token["expires_at"] = (
                time.time() + response_data.get("expires_in", 3600)
            )
            new_token.pop("client_secret", None)

            temp_token_file = TOKEN_FILE.with_suffix(".tmp")
            temp_token_file.write_text(json.dumps(new_token, indent=2))
            os.chmod(temp_token_file, 0o600)
            os.replace(temp_token_file, TOKEN_FILE)

            print("[OAUTH] Token rafraîchi et sauvegardé")
            return True

        print(f"[OAUTH] Refresh échoué: {result.stdout[:200]}")
        return False
    except Exception as e:
        print(f"[OAUTH] Refresh exception: {e}")
        return False


def save_to_failures(video_path):
    """Sauvegarde la vidéo dans failures/ en cas d'échec OAuth."""
    FAILURE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = FAILURE_DIR / f"oauth_fail_{ts}_{Path(video_path).name}"
    try:
        shutil.copy2(video_path, dest)
        print(f"[OAUTH] Vidéo sauvegardée: {dest}")
        return str(dest)
    except Exception as e:
        print(f"[OAUTH] Échec sauvegarde: {e}")
        return None


if __name__ == "__main__":
    result = check_oauth_valid()
    print(json.dumps(result, indent=2))

