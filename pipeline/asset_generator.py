#!/usr/bin/env python3
"""
asset_generator.py — Génération d'images thématiques et overlays graphiques
Inspiré d'OpenMontage : génère des scènes visuelles cohérentes plutôt que des clips aléatoires.

Composants :
- generate_scene_images()  → images thématiques via PiAPI (fallback: stock clips)
- create_title_card()       → titre animé via Pillow
- create_stat_card()        → carte statistique animée
- create_overlay_sequence() → séquence d'overlays pour le compositeur
"""

import os, json, shutil, subprocess, random, re, textwrap
from pathlib import Path
from datetime import datetime

try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter
except ImportError:
    Image = None

import requests


def load_secrets():
    s = {}
    secrets_path = Path.home() / ".secrets" / "env"
    if secrets_path.exists():
        with open(secrets_path) as f:
            for line in f:
                if "=" in line:
                    line = line.replace("export ", "").strip()
                    k, v = line.split("=", 1)
                    s[k] = v.strip('"').strip("'")
    return s


# ── PIAPI IMAGE GENERATION ───────────────────────────────────────

def piapi_generate_image(prompt: str, out_path: Path, cfg_scale: float = 7.0,
                          steps: int = 20, timeout: int = 60) -> bool:
    """
    Génère une image via PiAPI (flux-pro ou autre modèle dispo).
    Retourne True si succès, False sinon.
    """
    secrets = load_secrets()
    api_key = secrets.get("PIAPI_API_KEY") or os.environ.get("PIAPI_API_KEY")
    if not api_key:
        print("[PiAPI] Pas de clé API")
        return False

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    try:
        # Step 1: Create task
        payload = {
            "model": "Qubico/flux1-dev-advanced",
            "task_type": "txt2img",
            "input": {
                "prompt": prompt,
                "width": 576,
                "height": 1024,  # 9:16 pour Shorts
                "num_images": 1,
                "steps": steps,
                "cfg_scale": cfg_scale,
            }
        }
        resp = requests.post(
            "https://api.piapi.ai/api/v1/task",
            headers=headers, json=payload, timeout=15
        )
        if resp.status_code != 200:
            print(f"[PiAPI] Create task failed: {resp.status_code} {resp.text[:200]}")
            return False

        task_id = resp.json().get("data", {}).get("task_id")
        if not task_id:
            print(f"[PiAPI] No task_id in response: {resp.text[:200]}")
            return False

        # Step 2: Poll until done
        import time
        for _ in range(timeout // 3):
            time.sleep(3)
            poll = requests.get(
                f"https://api.piapi.ai/api/v1/task/{task_id}",
                headers=headers, timeout=10
            )
            if poll.status_code != 200:
                continue
            status = poll.json().get("data", {}).get("status")
            if status == "completed":
                # Get image URL
                image_url = poll.json().get("data", {}).get("output", {}).get("image_url") or \
                            poll.json().get("data", {}).get("output", {}).get("images", [None])[0]
                if not image_url:
                    print(f"[PiAPI] Completed but no image_url: {poll.text[:300]}")
                    return False
                # Download
                img_resp = requests.get(image_url, timeout=30)
                if img_resp.status_code == 200:
                    out_path.write_bytes(img_resp.content)
                    print(f"[PiAPI] Image saved: {out_path.name} ({len(img_resp.content)} bytes)")
                    return True
                return False
            elif status in ("failed", "error"):
                err = poll.json().get("data", {}).get("error", "unknown")
                print(f"[PiAPI] Task failed: {err}")
                return False

        print(f"[PiAPI] Timeout after {timeout}s")
        return False

    except Exception as e:
        print(f"[PiAPI] Exception: {e}")
        return False


# ── LEONARDO.AI IMAGE GENERATION ─────────────────────────────────

def leonardo_generate_image(prompt: str, out_path: Path, timeout: int = 45) -> bool:
    """
    Génère une image via Leonardo.ai (FLUX Schnell).
    Coût : ~$0.003/image. Retourne True si succès.
    """
    secrets = load_secrets()
    api_key = secrets.get("LEONARDO_API_KEY") or os.environ.get("LEONARDO_API_KEY")
    if not api_key:
        print("[Leonardo] Pas de clé API")
        return False

    headers = {
        "Authorization": f"Bearer {api_key}",
        "accept": "application/json",
        "content-type": "application/json",
    }

    try:
        # Step 1: Create generation
        from datetime import datetime as _dt
        payload = {
            "modelId": "1dd50843-d653-4516-a8e3-f0238ee453ff",  # FLUX Schnell
            "prompt": prompt,
            "width": 576,
            "height": 1024,
            "num_images": 1,
            "contrast": 3.5,
            "enhancePrompt": True,
        }
        resp = requests.post(
            "https://cloud.leonardo.ai/api/rest/v1/generations",
            headers=headers, json=payload, timeout=15
        )
        if resp.status_code != 200:
            print(f"[Leonardo] Create failed: {resp.status_code} {resp.text[:200]}")
            return False

        gen_id = resp.json().get("sdGenerationJob", {}).get("generationId")
        if not gen_id:
            print(f"[Leonardo] No generationId: {resp.text[:200]}")
            return False

        # Step 2: Poll until complete
        import time
        for _ in range(timeout // 3):
            time.sleep(3)
            poll = requests.get(
                f"https://cloud.leonardo.ai/api/rest/v1/generations/{gen_id}",
                headers=headers, timeout=10
            )
            if poll.status_code != 200:
                continue
            data = poll.json()
            gens = data.get("generations_by_pk", {})
            status = gens.get("status", "")

            if status == "COMPLETE":
                images = gens.get("generated_images", [])
                if images:
                    url = images[0].get("url", "")
                    if url:
                        img_resp = requests.get(url, timeout=30)
                        if img_resp.status_code == 200:
                            out_path.write_bytes(img_resp.content)
                            print(f"[Leonardo] Image saved: {out_path.name} ({len(img_resp.content)} bytes)")
                            return True
                break
            elif status == "FAILED":
                err = gens.get("failedReason", "unknown")
                print(f"[Leonardo] Generation failed: {err}")
                return False

        print(f"[Leonardo] Timeout after {timeout}s")
        return False

    except Exception as e:
        print(f"[Leonardo] Exception: {e}")
        return False


# ── ASSET GENERATION ───────────────────────────────────────

try:
    from tools.api_bridge import bridge
except ImportError:
    class _BridgeFallback:
        @staticmethod
        def generate_image(prompt, out_path): return False
    bridge = _BridgeFallback()
    print("[WARN] tools.api_bridge non trouvé — génération d'images désactivée")

def generate_scene_images(topic: str, scene_descriptions: list[str],
                           work_dir: Path, fallback_clips: list = None) -> list[Path]:
    """
    Génère des images thématiques pour chaque scène via le Bridge optimisé.
    Retourne la liste des chemins d'images/scènes.
    """
    scene_images = []
    
    # Style base commun pour les prompts
    BASE_STYLE = (
        "cinematic photography, dark elegant atmosphere, deep blue and gold tones, "
        "professional lighting, sharp focus, 9:16 aspect ratio, "
        "text overlay space at bottom, minimalist, sophisticated, "
        "financial abstract concept, data visualization background, "
        "no text, no watermark, ultra detailed"
    )

    for i, desc in enumerate(scene_descriptions):
        out_path = work_dir / f"scene_{i+1:02d}.png"
        full_prompt = f"{desc}, {BASE_STYLE}"

        # Utilisation du Bridge pour optimiser les coûts
        if bridge.generate_image(full_prompt, out_path):
            scene_images.append(out_path)
            print(f"[SCENE {i+1}] Bridge: {desc[:50]}... ✅")
        else:
            # Fallback final : frame de clip
            if fallback_clips and i < len(fallback_clips):
                clip = Path(fallback_clips[i])
                frame_path = work_dir / f"scene_{i+1:02d}.png"
                subprocess.run([
                    "ffmpeg", "-i", str(clip), "-vframes", "1",
                    "-q:v", "2", str(frame_path), "-y", "-loglevel", "error"
                ], check=True, timeout=30)
                if frame_path.exists():
                    scene_images.append(frame_path)
                    print(f"[SCENE {i+1}] Fallback: Frame extraite de {clip.name}")
            else:
                print(f"[SCENE {i+1}] Échec total de génération pour {desc[:50]}")

    return scene_images


# ── PILLOW OVERLAY GENERATION ─────────────────────────────────────

def find_font(size: int = 48, bold: bool = True) -> str:
    """Trouve une police Bold dispo, avec fallback."""
    candidates = [
        "/usr/share/fonts/truetype/montserrat/Montserrat-ExtraBold.ttf",
        "/usr/share/fonts/truetype/montserrat/Montserrat-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    # Fallback : n'importe quel .ttf dans /usr/share/fonts
    import glob
    ttf = glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
    if ttf:
        return ttf[0]
    return None


def create_title_card(text: str, out_path: Path, width: int = 1080, height: int = 1920,
                       subtitle: str = None) -> bool:
    """Crée une carte titre premium — style Alfred AI (dark/gold, incitation abonnement)."""
    if Image is None:
        return False

    font_path = find_font(90)
    font_sub_path = find_font(44)
    font_small_path = find_font(36)
    font_val = ImageFont.truetype(font_path, 90) if font_path else None
    font_sub = ImageFont.truetype(font_sub_path, 44) if font_sub_path else None
    font_small = ImageFont.truetype(font_small_path, 36) if font_small_path else None

    GOLD = (255, 200, 50, 245)
    GOLD_DIM = (200, 160, 40, 200)
    WHITE = (255, 255, 255, 245)
    WHITE_DIM = (200, 205, 220, 200)

    # ── Fond noir profond avec halo doré subtil ──
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    try:
        import numpy as np
        cx, cy = width // 2, height // 2 - 150
        Y, X = np.ogrid[:height, :width]
        dist = np.sqrt((X - cx)**2 + (Y - cy)**2)
        max_dist = np.sqrt(cx**2 + cy**2)
        alpha = np.clip(1.0 - dist / max_dist * 0.85, 0.05, 0.85)
        bg = np.zeros((height, width, 4), dtype=np.uint8)
        bg[:, :, 0] = 8
        bg[:, :, 1] = 8
        bg[:, :, 2] = 10
        bg[:, :, 3] = (alpha * 255).astype(np.uint8)
        bg_img = Image.fromarray(bg)
        img = bg_img
        draw = ImageDraw.Draw(img)
    except ImportError:
        draw.rectangle([0, 0, width, height], fill=(8, 8, 10, 230))

    # ── Bande dorée large en haut ──
    gold_band_y = int(height * 0.06)
    draw.rectangle([0, gold_band_y, width, gold_band_y + 4], fill=GOLD)

    # ── Titre principal ──
    title_area_top = int(height * 0.20)
    if font_val:
        lines = textwrap.wrap(text, width=14)
        line_height = 95
        total_text_h = len(lines) * line_height
        y_start = title_area_top
        for j, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_val)
            tw = bbox[2] - bbox[0]
            tx = (width - tw) // 2
            draw.text((tx + 2, y_start + j * line_height + 2), line, font=font_val, fill=(0, 0, 0, 100))
            draw.text((tx, y_start + j * line_height), line, font=font_val, fill=WHITE)

    # ── Séparateur doré ──
    sep_y = y_start + total_text_h + 30
    draw.rectangle([width // 2 - 120, sep_y, width // 2 + 120, sep_y + 2], fill=GOLD_DIM)

    # ── Sous-titre / catégorie ──
    sub_bottom = sep_y + 50
    if subtitle and font_sub:
        sub_y = sub_bottom
        bbox = draw.textbbox((0, 0), subtitle, font=font_sub)
        tw = bbox[2] - bbox[0]
        tx = (width - tw) // 2
        draw.text((tx, sub_y), subtitle, font=font_sub, fill=GOLD)
        sub_bottom = sub_y + (bbox[3] - bbox[1]) + 60
    else:
        sub_bottom = sep_y + 40

    # ── Zone CTA : ABONNEZ-VOUS (positionné dynamiquement) ──
    cta_bg_h = 100
    cta_bg_y = max(sub_bottom, int(height * 0.50))
    # Safety: keep at least 60px from bottom for channel name
    cta_bg_y = min(cta_bg_y, height - cta_bg_h - 120)
    btn_margin = 100
    draw.rounded_rectangle(
        [btn_margin, cta_bg_y, width - btn_margin, cta_bg_y + cta_bg_h],
        radius=16, fill=(255, 200, 50, 220)
    )
    cta_text = "ABONNEZ-VOUS"
    cta_font = font_sub or font_small
    if cta_font:
        bbox = draw.textbbox((0, 0), cta_text, font=cta_font)
        tw = bbox[2] - bbox[0]
        tx = (width - tw) // 2
        ty = cta_bg_y + (cta_bg_h - (bbox[3] - bbox[1])) // 2
        draw.text((tx, ty), cta_text, font=cta_font, fill=(0, 0, 0, 230))

    # ── Channel name (positionné dynamiquement) ──
    if font_small:
        channel_text = "@Alfred AI"
        bbox = draw.textbbox((0, 0), channel_text, font=font_small)
        tw = bbox[2] - bbox[0]
        tx = (width - tw) // 2
        ty = cta_bg_y + cta_bg_h + 50
        # Keep between 65-85% of height
        ty = min(max(ty, int(height * 0.65)), int(height * 0.82))
        draw.text((tx, ty), channel_text, font=font_small, fill=WHITE_DIM)

    # ── Bande dorée en bas (positionnée dynamiquement) ──
    if font_small:
        ch_bottom = ty + (bbox[3] - bbox[1]) + 30
    else:
        ch_bottom = cta_bg_y + cta_bg_h + 80
    bot_band_y = min(ch_bottom, int(height * 0.92))
    draw.rectangle([width // 2 - 100, bot_band_y, width // 2 + 100, bot_band_y + 2], fill=GOLD_DIM)

    img.save(str(out_path))
    return True




def _fit_label(draw, text: str, font_path: str, max_w: int,
                start_size: int = 34, min_size: int = 22):
    """Ajuste un libelle a la largeur dispo : reduit la taille, puis passe sur 2 lignes, puis tronque.
    Garantit qu'aucun texte ne deborde de la carte."""
    text = " ".join(str(text).split())
    size = start_size
    while size >= min_size:
        f = ImageFont.truetype(font_path, size)
        bb = draw.textbbox((0, 0), text, font=f)
        if bb[2] - bb[0] <= max_w:
            return f, [text], size
        size -= 2
    size = min_size
    f = ImageFont.truetype(font_path, size)
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        cand = (cur + " " + w).strip()
        bb = draw.textbbox((0, 0), cand, font=f)
        if bb[2] - bb[0] <= max_w or not cur:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    if len(lines) > 2:
        lines = lines[:2]
        last = lines[1]
        while last and draw.textbbox((0, 0), last + "\u2026", font=f)[2] > max_w:
            last = last[:-1]
        lines[1] = last + "\u2026"
    return f, lines, size


def create_stat_card(label: str, value: str, out_path: Path,
                      width: int = 680, height: int = 360,
                      accent_color: tuple = (255, 200, 50),
                      source: str = "") -> bool:
    """Crée une carte statistique overlay — style Alfred AI (dark/gold premium)."""
    if Image is None:
        return False

    font_val_path = find_font(100)
    font_lbl_path = find_font(34)
    font_val = ImageFont.truetype(font_val_path, 100) if font_val_path else None
    font_lbl = ImageFont.truetype(font_lbl_path, 34) if font_lbl_path else None

    GOLD = accent_color + (245,)
    GOLD_DIM = (accent_color[0] - 40, accent_color[1] - 40, accent_color[2] - 20, 200)
    WHITE_DIM = (210, 215, 230, 220)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    m = 18  # margin
    r = 20  # corner radius

    # ── Fond transparent (Eric veut pas de zone sombre) ──
    draw.rounded_rectangle(
        [m, m, width - m, height - m],
        radius=r, fill=(0, 0, 0, 0)
    )
    # Liseré doré subtil
    draw.rounded_rectangle(
        [m, m, width - m, height - m],
        radius=r, outline=accent_color + (140,), width=1
    )

    # Ligne d'accent dorée en haut
    draw.rounded_rectangle(
        [m + 6, m + 4, width - m - 6, m + 10],
        radius=3, fill=GOLD
    )

    # ── Valeur (grand, doré) ──
    if font_val:
        bbox = draw.textbbox((0, 0), value, font=font_val)
        tw = bbox[2] - bbox[0]
        tx = (width - tw) // 2
        # Ombre portée légère
        draw.text((tx + 2, height // 2 - 72 + 2), value, font=font_val, fill=(0, 0, 0, 80))
        draw.text((tx, height // 2 - 72), value, font=font_val, fill=GOLD)

    # ── Label (blanc, moderne) — auto-ajustement, aucun debordement garanti ──
    avail_w = width - 2 * m - 24
    label_lines = []
    line_h = 42
    if label and font_lbl_path:
        font_lbl, label_lines, _sz = _fit_label(draw, label, font_lbl_path, avail_w, 34, 22)
        line_h = _sz + 8
        y_lbl = height // 2 + 28
        for i, line in enumerate(label_lines):
            bbox = draw.textbbox((0, 0), line, font=font_lbl)
            tw = bbox[2] - bbox[0]
            draw.text(((width - tw) // 2, y_lbl + i * line_h), line,
                      font=font_lbl, fill=WHITE_DIM)
    elif font_lbl:
        bbox = draw.textbbox((0, 0), label, font=font_lbl)
        tw = bbox[2] - bbox[0]
        draw.text(((width - tw) // 2, height // 2 + 28), label, font=font_lbl, fill=WHITE_DIM)
        label_lines = [label] if label else []

    # Petite barre decorative sous le label
    n_lbl = max(1, len(label_lines))
    y_bar = (height // 2 + 28) + n_lbl * line_h + 4
    bar_w = 40
    bar_x = (width - bar_w) // 2
    draw.rounded_rectangle(
        [bar_x, y_bar, bar_x + bar_w, y_bar + 4],
        radius=2, fill=GOLD_DIM
    )

    # ── Source (attribution discrete, optionnelle) ──
    if source:
        src_path = find_font(20)
        if src_path:
            font_src = ImageFont.truetype(src_path, 20)
            src_txt = "SOURCE : " + str(source).upper()
            bbox = draw.textbbox((0, 0), src_txt, font=font_src)
            while bbox[2] - bbox[0] > avail_w and len(src_txt) > 12:
                src_txt = src_txt[:-2].rstrip(" ,-") + "\u2026"
                bbox = draw.textbbox((0, 0), src_txt, font=font_src)
            tw = bbox[2] - bbox[0]
            draw.text(((width - tw) // 2, y_bar + 14), src_txt,
                      font=font_src, fill=(185, 175, 145, 205))

    img.save(str(out_path))
    return True


def create_comparison_card(label_left: str, label_right: str, value_left: str, value_right: str,
                            out_path: Path, width: int = 900, height: int = 400) -> bool:
    """Crée une carte de comparaison bicolore — format Shorts (max 900×400)."""
    if Image is None:
        return False

    font_val = ImageFont.truetype(find_font(64), 64)
    font_lbl = ImageFont.truetype(find_font(26), 26)

    GOLD = (255, 200, 50, 245)

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    half = width // 2
    gap = 8

    # Côté gauche (rouge foncé, premium)
    draw.rounded_rectangle([10, 12, half - gap, height - 12], radius=14, fill=(120, 25, 25, 210))
    draw.rounded_rectangle([10, 12, half - gap, height - 12], radius=14, outline=GOLD, width=1)
    if font_val:
        bbox = draw.textbbox((0, 0), value_left, font=font_val)
        tw = bbox[2] - bbox[0]
        draw.text(((half - tw) // 2, height // 2 - 50), value_left, font=font_val, fill=(255, 255, 255, 245))
    if font_lbl:
        bbox = draw.textbbox((0, 0), label_left, font=font_lbl)
        tw = bbox[2] - bbox[0]
        draw.text(((half - tw) // 2, height // 2 + 30), label_left, font=font_lbl, fill=(255, 200, 200, 220))

    # Côté droit (vert foncé, premium)
    draw.rounded_rectangle([half + gap, 12, width - 10, height - 12], radius=14, fill=(20, 120, 50, 210))
    draw.rounded_rectangle([half + gap, 12, width - 10, height - 12], radius=14, outline=GOLD, width=1)
    if font_val:
        bbox = draw.textbbox((0, 0), value_right, font=font_val)
        tw = bbox[2] - bbox[0]
        draw.text((half + (half - tw) // 2, height // 2 - 50), value_right, font=font_val, fill=(255, 255, 255, 245))
    if font_lbl:
        bbox = draw.textbbox((0, 0), label_right, font=font_lbl)
        tw = bbox[2] - bbox[0]
        draw.text((half + (half - tw) // 2, height // 2 + 30), label_right, font=font_lbl, fill=(200, 255, 200, 220))

    # Séparateur doré
    draw.rectangle([half - 1, 30, half + 1, height - 30], fill=GOLD)

    img.save(str(out_path))
    return True


def create_overlay_sequence(script_data: dict, scene_images: list,
                             work_dir: Path, fps: int = 30) -> dict:
    """
    Génère les overlays pour chaque segment du script.
    Retourne un dict avec les chemins et timings :
    {
        "segments": [
            {
                "index": 0,
                "scene_image": "scene_01.png",
                "overlays": ["stat_card_01.png", ...],
                "overlay_times": [0.5, 3.0],  # secondes dans le segment
                "text": "...",
                "voice": "A",
                "duration": 10.0
            },
            ...
        ]
    }
    """
    result = {"segments": []}
    overlays_dir = work_dir / "overlays"
    overlays_dir.mkdir(parents=True, exist_ok=True)

    for idx, seg in enumerate(script_data.get("segments", [])):
        seg_info = {
            "index": idx,
            "scene_image": str(scene_images[idx]) if idx < len(scene_images) else None,
            "overlays": [],
            "overlay_times": [],
            "text": seg.get("text", ""),
            "voice": seg.get("voice", "A"),
            "duration": seg.get("duration", 10),
        }

        text = seg.get("text", "")
        stat_value = str(seg.get("stat_value", "")).strip()
        stat_label = str(seg.get("stat_label", "")).strip() or _infer_stat_context(text)["label"]
        stat_source = str(seg.get("stat_source", "")).strip()
        if not stat_source:
            stat_label, stat_source = _split_source(stat_label)
        if stat_value:
            stat_path = overlays_dir / f"stat_{idx:02d}.png"
            if create_stat_card(stat_label, stat_value, stat_path, source=stat_source):
                seg_info["overlays"].append(str(stat_path))
                seg_info["overlay_times"].append(0.0)

        # Détection de comparaison — SUPPRIMÉ (Eric veut plus les carrés rouge/vert)
        pass

        result["segments"].append(seg_info)

    return result


_SOURCE_TOKENS = ["base ETF PEA", "Eurostat", "BCE", "Yahoo Finance",
                  "MSCI", "Amundi", "iShares", "ETF PEA"]


def _split_source(label: str):
    """Separe une eventuelle mention de source du libelle (ex: 'base ETF PEA (437 fonds)')."""
    low = label.lower()
    for tok in _SOURCE_TOKENS:
        i = low.find(tok.lower())
        if i >= 0:
            src = label[i:i + len(tok)].strip()
            rest = (label[:i] + " " + label[i + len(tok):]).strip(" ,-()")
            rest = " ".join(rest.split())
            if rest:
                return rest, src
            return label, ""
    return label, ""


def _infer_stat_context(text: str) -> dict:
    """Infère le contexte d'une statistique dans le texte."""
    text_lower = text.lower()
    if "pourcent" in text_lower or "%" in text_lower:
        return {"label": "DES INVESTISSEURS"}
    if "euro" in text_lower or "€" in text_lower:
        return {"label": "PAR AN"}
    if "an" in text_lower or "année" in text_lower or "ans" in text_lower:
        return {"label": "SUR LA PÉRIODE"}
    if "million" in text_lower:
        return {"label": "CAPITAL TOTAL"}
    return {"label": "CHIFFRE CLÉ"}


def _extract_comparison(text: str) -> dict:
    """Extrait une comparaison gauche/droite du texte."""
    # Patterns: X contre Y, X vs Y
    import re as _re
    parts = _re.split(r'\s+(contre|vs|versus)\s+', text, flags=_re.IGNORECASE)
    if len(parts) >= 3:
        left = parts[0].strip()
        right = parts[2].strip().rstrip('.!,?')

        left_nums = _re.findall(r'\d+[\s.,]*(?:%|euros|€)?', left)
        right_nums = _re.findall(r'\d+[\s.,]*(?:%|euros|€)?', right)

        return {
            "left_label": left[:30].upper() if left_nums else "AVANT",
            "right_label": right[:30].upper() if right_nums else "APRÈS",
            "left_val": left_nums[0].strip() if left_nums else "—",
            "right_val": right_nums[0].strip() if right_nums else "—",
        }
    return None


# ── END CARD (SUBSCRIBE OVERLAY) ─────────────────────────────────

def create_end_card(out_path: Path, width: int = 1920, height: int = 1080,
                     channel_name: str = "Alfred AI") -> bool:
    """Utilise l'end card designée par Eric directement."""
    if Image is None:
        return False

    custom_path = Path(__file__).parent.parent / "skills" / "alfred_video_pipeline" / "alfred_brand_icon.png"

    if not custom_path.exists():
        print(f"[END CARD] Custom end card introuvable: {custom_path}")
        return False

    try:
        card = Image.open(str(custom_path)).convert("RGBA")
        # Redimensionner pour remplir les dimensions demandées (cover)
        card_ratio = card.width / card.height
        target_ratio = width / height

        if card_ratio > target_ratio:
            # Card plus large que cible → ajuster sur hauteur
            new_h = height
            new_w = int(new_h * card_ratio)
        else:
            # Card plus haute → ajuster sur largeur
            new_w = width
            new_h = int(new_w / card_ratio)

        card = card.resize((new_w, new_h), Image.LANCZOS)

        # Crop center si plus grand que la cible
        if new_w > width or new_h > height:
            left = (new_w - width) // 2
            top = (new_h - height) // 2
            card = card.crop((left, top, left + width, top + height))
        else:
            # Centrer sur fond noir si plus petit
            final = Image.new("RGBA", (width, height), (0, 0, 0, 255))
            left = (width - new_w) // 2
            top = (height - new_h) // 2
            final.paste(card, (left, top), card)
            card = final

        card.save(str(out_path))
        return True
    except Exception as e:
        print(f"[END CARD] Erreur: {e}")
        return False


# ── YOUTUBE THUMBNAIL GENERATION ────────────────────────────────

def create_youtube_thumbnail(title: str, out_path: Path,
                              width: int = 1280, height: int = 720,
                              channel_name: str = "Alfred AI") -> bool:
    """
    Crée une miniature YouTube 1280x720 (ratio 16:9) optimisée pour les clics.
    Style : dégradé sombre, texte blanc en haut, barre orange décorative,
    bandeau channel en bas.
    """
    if Image is None:
        return False

    font_title = ImageFont.truetype(find_font(80), 80)
    font_channel = ImageFont.truetype(find_font(24), 24)

    # Toile de fond dégradée verticale
    try:
        import numpy as np
        gradient = np.zeros((height, width, 4), dtype=np.uint8)
        for y in range(height):
            t = y / height
            r = int(5 + 15 * t)
            g = int(8 + 20 * t)
            b = int(20 + 15 * t)
            gradient[y, :, 0] = r
            gradient[y, :, 1] = g
            gradient[y, :, 2] = b
            gradient[y, :, 3] = 255
        img = Image.fromarray(gradient)
        draw = ImageDraw.Draw(img)
    except ImportError:
        img = Image.new("RGBA", (width, height), (10, 12, 25, 255))
        draw = ImageDraw.Draw(img)

    # Barre décorative orange en haut
    draw.rectangle([0, 0, width, 8], fill=(255, 180, 23, 255))
    # Barre décorative orange en bas
    draw.rectangle([0, height - 60, width, height], fill=(0, 0, 0, 160))

    # Titre (centré, avec word wrap)
    if font_title:
        lines = textwrap.wrap(title.upper(), width=20)
        y_start = 100
        for j, line in enumerate(lines):
            bbox = draw.textbbox((0, 0), line, font=font_title)
            tw = bbox[2] - bbox[0]
            tx = (width - tw) // 2
            # Ombre portée
            draw.text((tx + 2, y_start + j * 100 + 2), line, font=font_title, fill=(0, 0, 0, 180))
            draw.text((tx, y_start + j * 100), line, font=font_title, fill=(255, 255, 255, 245))

    # Bandeau channel en bas
    if font_channel:
        ch_text = f"  {channel_name}  "
        bbox = draw.textbbox((0, 0), ch_text, font=font_channel)
        ch_w = bbox[2] - bbox[0] + 40
        ch_h = 40
        cx = (width - ch_w) // 2
        cy = height - 50
        draw.rounded_rectangle([cx, cy, cx + ch_w, cy + ch_h], radius=20, fill=(255, 180, 23, 220))
        draw.text((cx + 20, cy + 5), ch_text, font=font_channel, fill=(0, 0, 0, 255))

    img.save(str(out_path))
    print(f"[THUMB] Miniature créée: {out_path.name} ({out_path.stat().st_size // 1024} Ko)")
    return True


if __name__ == "__main__":
    # Test
    import sys
    test_dir = Path("/tmp/alfred_asset_test")
    test_dir.mkdir(parents=True, exist_ok=True)

    print("=== Test créations graphiques ===")

    # Title card
    if create_title_card("Pourquoi 83% des épargnants perdent de l'argent", test_dir / "test_title.png",
                          subtitle="NEURO-FINANCE"):
        print("✅ Title card créée")
    else:
        print("❌ Title card échouée")

    # Stat card
    if create_stat_card("DES INVESTISSEURS", "83%", test_dir / "test_stat.png"):
        print("✅ Stat card créée")
    else:
        print("❌ Stat card échouée")

    # Comparison card
    if create_comparison_card("SANS STRATÉGIE", "AVEC STRATÉGIE", "73%", "27%", test_dir / "test_comp.png"):
        print("✅ Comparison card créée")
    else:
        print("❌ Comparison card échouée")

    # End card
    if create_end_card(test_dir / "test_end.png"):
        print("✅ End card créée")
    else:
        print("❌ End card échouée")

    # Thumbnail
    if create_youtube_thumbnail("83% perdent de l'argent", test_dir / "test_thumb.png"):
        print("✅ Thumbnail YouTube créée")
    else:
        print("❌ Thumbnail échouée")

    print(f"\nFichiers dans {test_dir}:")
    for f in test_dir.iterdir():
        print(f"  {f.name} ({f.stat().st_size // 1024} Ko)")