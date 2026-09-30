#!/usr/bin/env python3
"""
📤 Alfred Multi-Platform Uploader — via Zernio SDK
Publie une vidéo sur TikTok, LinkedIn, Instagram, etc. en un seul appel.

Utilise le SDK officiel zernio-sdk (pip install zernio-sdk).

Usage:
  from zernio_uploader import upload_video
  upload_video("/path/to/video.mp4", "Titre", "Description", tags=["finance"])
"""

import os, json, logging, subprocess, tempfile
from pathlib import Path
from typing import Optional, List
from zernio import Zernio

log = logging.getLogger("zernio-uploader")

# ─── Config ───────────────────────────────────────────────────────

ZERNIO_API_KEY = os.environ.get("ZERNIO_API_KEY", "")
ZERNIO_ACCOUNTS_FILE = Path.home() / ".openclaw/workspace/state/zernio_accounts.json"
_zernio_client: Optional[Zernio] = None


def _get_key() -> str:
    """Lazy-load ZERNIO_API_KEY: env → secrets file."""
    key = os.environ.get("ZERNIO_API_KEY", "")
    if not key:
        secrets_path = Path.home() / ".secrets" / "env"
        if secrets_path.exists():
            with open(secrets_path) as f:
                for line in f:
                    if line.startswith("export ZERNIO_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        os.environ["ZERNIO_API_KEY"] = key
                        break
    return key


def _get_client():
    """Retourne le client Zernio initialisé (singleton)."""
    global _zernio_client
    if _zernio_client is not None:
        return _zernio_client
    key = _get_key()
    if not key:
        return None
    _zernio_client = Zernio(api_key=key)
    return _zernio_client


ZERNIO_API_KEY: str = ""  # obsolète — utiliser _get_key()
_zernio_client = None




def _load_accounts() -> dict:
    if ZERNIO_ACCOUNTS_FILE.exists():
        return json.loads(ZERNIO_ACCOUNTS_FILE.read_text())
    return {}


# ─── Upload ───────────────────────────────────────────────────────

def upload_video(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[List[str]] = None,
    platforms: Optional[List[str]] = None,
    thumbnail_url: Optional[str] = None,
    scheduled_at: Optional[str] = None,
) -> dict:
    """
    Upload une vidéo sur les plateformes configurées via Zernio (SDK officiel).

    Args:
        video_path: Chemin local vers la vidéo
        title: Titre de la vidéo
        description: Description
        tags: Liste de hashtags
        platforms: Plateformes cibles (ex: ["tiktok", "linkedin"])
                   None = toutes les plateformes configurées
        thumbnail_url: URL de la miniature (optionnel, non utilisé via SDK)
        scheduled_at: Date ISO pour publication différée (optionnel)

    Returns:
        dict: Résultat formaté {success, platforms, result} ou {error, platform_success}
    """
    if not _get_key():
        return {"error": "ZERNIO_API_KEY non configurée", "platform_success": []}

    accounts = _load_accounts()
    if not accounts:
        return {"error": "Aucun compte Zernio configuré. Ajoute les IDs dans state/zernio_accounts.json", "platform_success": []}

    if not platforms:
        platforms = list(accounts.keys())

    # Filtrer les plateformes avec un account ID valide
    platforms_payload = []
    for platform in platforms:
        account_id = accounts.get(platform)
        if account_id:
            platforms_payload.append({"platform": platform, "accountId": account_id})

    if not platforms_payload:
        return {"error": "Aucune plateforme valide configurée", "platform_success": []}

    client = _get_client()

    # Auto-compression si fichier > 4MB (limite Zernio upload direct)
    MAX_SIZE = 4 * 1024 * 1024  # 4MB
    file_size = os.path.getsize(video_path) if os.path.isfile(video_path) else 0
    effective_path = video_path
    temp_cleanup = None

    if file_size > MAX_SIZE:
        log.info(f"📦 Fichier {file_size // 1024 // 1024}MB > 4MB — compression auto...")
        # Calculer le bitrate pour tenir dans ~3.5MB (marge de sécurité)
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", video_path],
            capture_output=True, text=True, timeout=15
        )
        try:
            duration = float(probe.stdout.strip())
        except ValueError:
            duration = 36.0
        target_bitrate = int((2.8 * 8 * 1024 * 1024) / max(duration, 1))  # bits/sec
        target_bitrate = min(target_bitrate, 1500_000)  # max 1.5 Mbps
        target_bitrate = max(target_bitrate, 300_000)   # min 300 Kbps

        # Compression en 720p vertical
        out_fd, out_path = tempfile.mkstemp(suffix="_zernio.mp4", dir="/tmp")
        os.close(out_fd)
        temp_cleanup = out_path

        subprocess.run([
            "ffmpeg", "-i", video_path,
            "-c:v", "libx264", "-b:v", str(target_bitrate),
            "-vf", "scale=720:1280",
            "-c:a", "aac", "-b:a", "96k",
            "-preset", "fast", "-y", out_path
        ], capture_output=True, timeout=120)

        new_size = os.path.getsize(out_path)
        log.info(f"✅ Compression: {file_size//1024//1024}MB → {new_size//1024}KB (bitrate ~{target_bitrate//1000}Kbps)")
        effective_path = out_path

    try:
        # Step 1: Upload media via SDK
        media_url = effective_path
        if not effective_path.startswith("http"):
            log.info(f"📤 Upload média vers Zernio: {effective_path}")
            upload_result = client.media.upload(effective_path)
            media_url = str(upload_result.files[0].url)
            log.info(f"✅ Média uploadé: {media_url}")

        # Step 2: Créer le post
        content = f"{title}\n\n{description}" if description else title

        post_kwargs = {
            "content": content,
            "platforms": platforms_payload,
            "media_items": [{"url": media_url, "type": "video"}],
            "publish_now": True,
        }
        if any(p["platform"] == "tiktok" for p in platforms_payload):
            post_kwargs["tiktok_settings"] = {"draft": False}



        if tags:
            post_kwargs["hashtags"] = tags
        if scheduled_at:
            post_kwargs["scheduled_for"] = scheduled_at
            post_kwargs["publish_now"] = False

        log.info(f"📝 Création du post Zernio ({', '.join(p['platform'] for p in platforms_payload)})")
        post = client.posts.create(**post_kwargs)

        # Parser la réponse
        post_dict = json.loads(post.model_dump_json())
        post_data = post_dict.get("post", post_dict)
        platform_statuses = post_data.get("platforms", [])

        success = []
        for p in platform_statuses:
            plat = p.get("platform")
            status = p.get("status", "unknown")
            if status in ("published", "processing"):
                success.append(plat)

        result = {
            "success": True,
            "platforms": success,
            "result": post_dict,
        }

        if success:
            log.info(f"✅ Publié sur {', '.join(success)}")
        else:
            log.warning(f"⚠️ Aucune publication confirmée")

        return result

    except Exception as e:
        err_msg = str(e)
        log.error(f"❌ Erreur Zernio: {err_msg}")
        # Si l'upload média a réussi mais que la création du post échoue
        # (ex: validation pydantic sur platformPostUrl vide), on tente
        # quand même de retourner un succès si le média est uploadé
        if temp_cleanup:
            try: os.remove(temp_cleanup)
            except: pass
        return {"error": err_msg, "platform_success": []}
    finally:
        if temp_cleanup:
            try: os.remove(temp_cleanup)
            except: pass


def upload_to_youtube_and_tiktok(
    video_path: str,
    title: str,
    description: str = "",
    tags: Optional[List[str]] = None,
) -> dict:
    """Raccourci pour uploader sur YouTube + TikTok."""
    return upload_video(
        video_path=video_path,
        title=title,
        description=description,
        tags=tags,
        platforms=["youtube", "tiktok"],
    )


def check_status() -> dict:
    """Vérifie l'état du compte Zernio via le SDK."""
    if not _get_key():
        return {"configured": False, "message": "ZERNIO_API_KEY manquante"}
    try:
        client = _get_client()
        accounts = client.accounts.list()
        return {"configured": True, "accounts": json.loads(accounts.model_dump_json())}
    except Exception as e:
        return {"configured": False, "error": str(e)}


# ─── CLI ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 2 and sys.argv[1] == "--check":
        print(json.dumps(check_status(), indent=2, ensure_ascii=False))
        sys.exit(0)

    if len(sys.argv) < 3:
        print("Usage: zernio_uploader.py <video_path> <title> [description] [tags...]")
        print("  ou:  zernio_uploader.py --check")
        sys.exit(1)

    video_path = sys.argv[1]
    title = sys.argv[2]
    desc = sys.argv[3] if len(sys.argv) > 3 else ""
    tags = sys.argv[4:] if len(sys.argv) > 4 else None

    result = upload_video(video_path, title, desc, tags)
    print(json.dumps(result, indent=2, ensure_ascii=False))