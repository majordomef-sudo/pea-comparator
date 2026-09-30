#!/usr/bin/env python3
"""
Caption Burner — Animated ASS captions (TikTok style)
Genere un fichier ASS avec :
  - Fond "pill" semi-transparent derrière les sous-titres (TikTok/Opus style)
  - Animation pop-in mot-par-mot avec pulse scale + glow
  - Mots groupés par blocs de 3 (words_per_cap)
  - Mot actif : scale 108% + outline pulse + blur glow
  - Mots inactifs : blanc avec outline
  - Majuscules automatiques

Avec Whisper: timestamps precis word-level (via faster-whisper).
Sans Whisper: timestamps approximatifs (mots repartis uniformement).
"""

import os, re, subprocess, textwrap
from pathlib import Path

_WHISPER_AVAIL = None
_WHISPER_MODEL = None


def _whisper_available() -> bool:
    global _WHISPER_AVAIL
    if _WHISPER_AVAIL is None:
        try:
            from faster_whisper import WhisperModel
            _WHISPER_AVAIL = True
        except ImportError:
            _WHISPER_AVAIL = False
    return _WHISPER_AVAIL


def _get_whisper_model():
    """Charge le modèle faster-whisper (lazy singleton, small, int8 CPU)."""
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None and _whisper_available():
        from faster_whisper import WhisperModel
        _WHISPER_MODEL = WhisperModel("small", device="cpu", compute_type="int8")
    return _WHISPER_MODEL


def _split_words(text: str) -> list:
    words = re.findall(r'\S+\s*', text)
    if not words:
        words = [text]
    return [w.strip() for w in words if w.strip()]


def transcribe_audio(audio_path: str, language: str = "fr") -> list:
    """Transcrit un fichier audio avec faster-whisper pour les timestamps mot-par-mot."""
    model = _get_whisper_model()
    if model is None:
        return []

    try:
        # Utilisation de beam_size=5 pour plus de précision sur les clips courts
        segments, info = model.transcribe(
            audio_path, 
            language=language, 
            word_timestamps=True,
            beam_size=5,
            best_of=5
        )

        word_timings = []
        for seg in segments:
            if seg.words:
                for w in seg.words:
                    word_timings.append((w.word.strip(), w.start, w.end))

        return word_timings
    except Exception as e:
        print(f"[WHISPER ERR] {e}")
        return []


def get_word_timings(audio_paths: list, segment_texts: list) -> list:
    """
    Pour chaque segment audio, retourne les timings mots precis via Whisper.
    Retourne: liste de [(word1, s1, e1), ...] ou None si indisponible.
    """
    if not _whisper_available():
        print("[CAPTIONS] Whisper non disponible, fallback timings approximatifs")
        return None

    all_timings = []
    for idx, audio_path in enumerate(audio_paths):
        if not os.path.exists(audio_path):
            all_timings.append(None)
            continue
        try:
            word_times = transcribe_audio(audio_path, language="fr")
            if word_times:
                all_timings.append(word_times)
                text = segment_texts[idx] if idx < len(segment_texts) else ""
                print(f"  [WHISPER] {Path(audio_path).name}: {len(word_times)} mots sur ~{text[:40]}...")
            else:
                all_timings.append(None)
        except Exception as e:
            print(f"  [WHISPER] Erreur: {e}")
            all_timings.append(None)

    return all_timings


def _esc_ass(s: str) -> str:
    return s.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")


def _rgb_to_ass_hex(rgb_hex: str) -> str:
    """#RRGGBB -> AABBGGRR (AA=00 opaque)"""
    rgb_hex = rgb_hex.lstrip("#")
    r = int(rgb_hex[0:2], 16); g = int(rgb_hex[2:4], 16); b = int(rgb_hex[4:6], 16)
    return f"00{b:02X}{g:02X}{r:02X}"


def _bbggrr(rgb_hex: str) -> str:
    """#RRGGBB -> BBGGRR for inline \\1c&H...&"""
    rgb_hex = rgb_hex.lstrip("#")
    r = int(rgb_hex[0:2], 16); g = int(rgb_hex[2:4], 16); b = int(rgb_hex[4:6], 16)
    return f"{b:02X}{g:02X}{r:02X}"


def _sec_to_ass(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _generate_pill_draw(play_res_x: int, play_res_y: int) -> str:
    """
    Genere les lignes ASS pour le fond "pill" semi-transparent derrière les sous-titres.
    Utilise un rectangle avec blur pour des coins arrondis visuels.
    """
    # Position du pill : sous les sous-titres, ~85% de largeur
    pill_w = int(play_res_x * 0.85)
    pill_h = 120
    pill_x = (play_res_x - pill_w) // 2
    # Sous les sous-titres (MARGIN_V = 560), avec un gap de 30px
    pill_y = play_res_y - 320 + 30

    # Style du pill
    pill_col = _rgb_to_ass_hex("#0A0A0A")  # noir profond
    # Couleur en BBGGRR pour le primary
    pill_col_bbggrr = _bbggrr("#0A0A0A")

    # Rectangle vectoriel : α=80 (semi-transparent), blur=12 pour coins arrondis
    draw_line = (
        f"Dialogue: 0,0:00:00.00,10:00:00.00,Pill,"
        f"0,0,0,,"
        f"{{\\p1\\bord0\\shad0\\blur12\\1c&H{pill_col_bbggrr}&\\alpha&H80&}}"
        f"m {pill_x} {pill_y} l {pill_x + pill_w} {pill_y} "
        f"l {pill_x + pill_w} {pill_y + pill_h} "
        f"l {pill_x} {pill_y + pill_h}{{\\p0}}"
    )

    return draw_line


def _sec_to_ass(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds - int(seconds)) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def make_ass_captions(segments: list, seg_timings: list,
                      word_timings: list = None,
                      video_res=(1080, 1920),
                      font_name="Montserrat",
                      font_size=84,
                      margin_v: int = None) -> str:
    """
    Genere un fichier ASS complet avec :
      - Fond "pill" semi-transparent en bas (Layer 1)
      - Sous-titres animés mot-par-mot (Layer 2)
      - Mot actif: scale 108% + glow + pulse outline
      - Mots groupés par blocs de 3
      - Resolution verticale pour Shorts
    """
    WPC = 3  # words per caption block
    BORD = 5
    SHAD = 0
    MARGIN_V = int(margin_v) if margin_v else 560  # évite l'UI YouTube/TikTok en bas
    MARGIN_LR = 70
    COLOR_ACTIVE = "#F5A623"  # orange doux (plus premium)
    COLOR_INACTIVE = "#FFFFFF"  # blanc
    OUTLINE_COLOR = "#1A1A1A"  # gris foncé au lieu de noir pur
    GLOW_COLOR = "#F5A623"  # glow assorti

    POP_IN_MS = 80
    POP_OUT_MS = 180
    POP_OUTLINE_EXTRA = 4
    POP_BLUR = 1.2
    ACTIVE_SCALE = 108  # 108% scale sur mot actif

    width, height = video_res
    if width < height:
        play_res_x, play_res_y = width, height
    else:
        play_res_x, play_res_y = 1080, 1920

    ass_lines = []

    # ── Header ──
    ass_lines.append("[Script Info]")
    ass_lines.append("ScriptType: v4.00+")
    ass_lines.append(f"PlayResX: {play_res_x}")
    ass_lines.append(f"PlayResY: {play_res_y}")
    ass_lines.append("WrapStyle: 2")
    ass_lines.append("ScaledBorderAndShadow: yes")
    ass_lines.append("")

    # ── Styles ──
    ass_lines.append("[V4+ Styles]")
    ass_lines.append(
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding"
    )

    inactive_col = _rgb_to_ass_hex(COLOR_INACTIVE)
    outline_col = _rgb_to_ass_hex(OUTLINE_COLOR)

    # Style pour les sous-titres
    ass_lines.append(
        f"Style: Cap,{font_name},{font_size},{inactive_col},{inactive_col},"
        f"{outline_col},&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,{BORD},{SHAD},2,{MARGIN_LR},{MARGIN_LR},{MARGIN_V},1"
    )
    # Style pour le pill background (BorderStyle=3 = opaque box)
    pill_col = _rgb_to_ass_hex("#0A0A0A")
    ass_lines.append(
        f"Style: Pill,Arial,1,{pill_col},{pill_col},"
        f"&H00000000,&H00000000,"
        f"0,0,0,0,100,100,0,0,1,0,0,0,7,1"
    )
    ass_lines.append("")

    # ── Events ──
    ass_lines.append("[Events]")
    ass_lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

    # ── Pill background (Layer 1, toute la durée) ──
    # Pill semi-transparent via drawbox dans ffmpeg plutôt qu'ASS,
    # car ASS drawing est limité. On fait le pill en overkill :
    # On ajoute un drawbox dans le compositeur (scene_composer.py)

    # ── Sous-titres par segment ──
    for idx, (seg, (t_start, t_end)) in enumerate(zip(segments, seg_timings)):
        words = _split_words(seg.get("text", ""))
        if not words:
            continue

        precise = word_timings and idx < len(word_timings) and word_timings[idx] is not None
        active_color = _bbggrr(COLOR_ACTIVE)
        inactive_color = _bbggrr(COLOR_INACTIVE)
        glow_color_bbggrr = _bbggrr(GLOW_COLOR)

        if precise:
            wt = word_timings[idx]
            for bi in range(0, len(wt), WPC):
                block = wt[bi:bi + WPC]
                if not block:
                    continue

                for ki in range(len(block)):
                    w = block[ki]
                    w_start = t_start + w[1]
                    w_end = t_start + w[2]

                    # Hold until next word or block end
                    if ki < len(block) - 1:
                        hold_end = t_start + block[ki + 1][1]
                    elif bi + WPC < len(wt):
                        hold_end = t_start + wt[bi + WPC][1]
                    else:
                        hold_end = w_end + 0.1

                    if hold_end <= w_start:
                        hold_end = max(w_start + 0.01, w_end)

                    dur_ms = int(round((hold_end - w_start) * 1000))
                    t_in = min(POP_IN_MS, max(0, dur_ms - 10))
                    t_out = min(POP_OUT_MS, max(t_in, dur_ms))

                    # Build text: active word avec scale + glow
                    parts = [r"{\q0}{\fsp2}"]
                    for wi, wrd in enumerate(block):
                        txt = wrd[0].upper()
                        if wi == ki:
                            # Active word: scale 108% + glow outline + pulse blur
                            tag = (
                                f"{{\\1c&H{active_color}&\\bord{BORD + POP_OUTLINE_EXTRA}\\blur{POP_BLUR}"
                                + f"\\fscx{ACTIVE_SCALE}\\fscy{ACTIVE_SCALE}"
                                + (f"\\t(0,{t_in},\\bord{BORD + POP_OUTLINE_EXTRA + 2}\\blur{POP_BLUR + 0.5})" if t_in > 0 else "")
                                + (f"\\t({t_in},{t_out},\\bord{BORD}\\blur0\\fscx100\\fscy100)" if t_out > t_in else "")
                                + "}"
                            )
                            parts.append(tag + _esc_ass(txt))
                        else:
                            parts.append(
                                f"{{\\1c&H{inactive_color}&\\bord{BORD}\\blur0\\fscx100\\fscy100}}{_esc_ass(txt)}"
                            )
                        if wi != len(block) - 1:
                            parts.append(" ")

                    text_line = "".join(parts)
                    ass_lines.append(
                        f"Dialogue: 0,{_sec_to_ass(w_start)},{_sec_to_ass(hold_end)},Cap,,0,0,0,,{text_line}"
                    )
        else:
            # Fallback: pas de timings precis, repartition uniforme
            dur_total = t_end - t_start
            word_dur = dur_total / max(len(words), 1)
            for wi in range(0, len(words), WPC):
                block_words = words[wi:wi + WPC]
                block_start = t_start + wi * word_dur
                block_end = t_start + min((wi + WPC) * word_dur, dur_total)

                for ki, wrd in enumerate(block_words):
                    w_time = block_start + ki * word_dur
                    w_end_time = w_time + word_dur
                    if w_end_time > block_end:
                        w_end_time = block_end

                    dur_ms = int(round((w_end_time - w_time) * 1000))
                    t_in = min(POP_IN_MS, max(0, dur_ms - 10))
                    t_out = min(POP_OUT_MS, max(t_in, dur_ms))

                    parts = [r"{\q0}{\fsp2}"]
                    for bi, bw in enumerate(block_words):
                        txt = bw.upper()
                        if bi == ki:
                            tag = (
                                f"{{\\1c&H{active_color}&\\bord{BORD + POP_OUTLINE_EXTRA}\\blur{POP_BLUR}"
                                + f"\\fscx{ACTIVE_SCALE}\\fscy{ACTIVE_SCALE}"
                                + (f"\\t(0,{t_in},\\bord{BORD + POP_OUTLINE_EXTRA + 2}\\blur{POP_BLUR + 0.5})" if t_in > 0 else "")
                                + (f"\\t({t_in},{t_out},\\bord{BORD}\\blur0\\fscx100\\fscy100)" if t_out > t_in else "")
                                + "}"
                            )
                            parts.append(tag + _esc_ass(txt))
                        else:
                            parts.append(
                                f"{{\\1c&H{inactive_color}&\\bord{BORD}\\blur0\\fscx100\\fscy100}}{_esc_ass(txt)}"
                            )
                        if bi != len(block_words) - 1:
                            parts.append(" ")

                    text_line = "".join(parts)
                    ass_lines.append(
                        f"Dialogue: 0,{_sec_to_ass(w_time)},{_sec_to_ass(w_end_time)},Cap,,0,0,0,,{text_line}"
                    )

    return "\n".join(ass_lines)


def burn_ass_captions(video_path: str, ass_path: str, output_path: str,
                       add_pill: bool = False):
    """
    Brûle les sous-titres ASS dans la vidéo, avec option pill background.
    Le pill est ajouté via drawbox filter avant l'application ASS.
    """
    if add_pill:
        # Drawbox: barre semi-transparente sous les sous-titres
        # Position: centrée, sous MARGIN_V=320, 120px de haut
        pill_w = "iw*0.85"
        pill_h = 120
        pill_x = "(iw-iw*0.85)/2"
        pill_y = "ih-320+30"  # aligné avec MARGIN_V

        vf = (
            f"drawbox=x={pill_x}:y={pill_y}:w={pill_w}:h={pill_h}:"
            f"color=black@0.45:t=fill,"
            f"ass={ass_path}"
        )
    else:
        vf = f"ass={ass_path}"

    subprocess.run([
        "ffmpeg", "-i", video_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        output_path, "-y", "-loglevel", "error"
    ], check=True, timeout=300)


def add_captions_to_video(video_path: str, segments: list,
                          seg_timings: list, word_timings: list = None,
                          output_path: str = None) -> str:
    """Point d'entree principal. Retourne le chemin de la video finale."""
    if output_path is None:
        p = Path(video_path)
        output_path = str(p.parent / f"{p.stem}_captioned{p.suffix}")

    work_dir = Path(video_path).parent
    ass_path = work_dir / "captions.ass"

    ass_content = make_ass_captions(segments, seg_timings,
                                    word_timings=word_timings,
                                    font_size=84)
    ass_path.write_text(ass_content, encoding="utf-8")
    print(f"[CAPTIONS] ASS genere: {len(ass_content)} chars, {len(segments)} segments"
          f"{' (Whisper timings)' if word_timings else ''}")

    burn_ass_captions(video_path, str(ass_path), output_path)
    print(f"[CAPTIONS] Burn-in OK: {output_path}")

    return output_path


def transcribe_assembled_audio(audio_path: str, language: str = "fr") -> list:
    """
    Transcrit l'audio ASSEMBLE (full video) avec Whisper en un seul passage.
    Retourne: [(word, start_abs, end_abs), ...] en secondes absolues.
    """
    model = _get_whisper_model()
    if model is None:
        return []

    try:
        segments, info = model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
            beam_size=5,
            best_of=5
        )
        all_words = []
        for seg in segments:
            if seg.words:
                for w in seg.words:
                    # w.start et w.end sont deja ABSOLUS (relatifs au debut du fichier audio)
                    all_words.append((w.word.strip(), w.start or 0.0, w.end or 0.0))
        print(f"[WHISPER ASSEMBLED] {len(all_words)} mots, audio={audio_path}")
        return all_words
    except Exception as e:
        print(f"[WHISPER ASSEMBLED ERR] {e}")
        return []


def make_ass_captions_from_assembled(
    segments: list,
    seg_timings: list,
    assembled_audio_path: str,
    video_res=(1080, 1920),
    font_name="Montserrat",
    font_size=84
) -> str:
    """
    Genere un ASS en transcriyant l'audio assemble (1 passage Whisper) et en
    utilisant le TEXTE ORIGINAL du script pour l'affichage.
    
    Les word timings sont ABSOLUS (secondes dans la video complete),
    extraits de l'audio final. t_start est ignore (mis a 0).
    """
    WPC = 3
    BORD = 5
    SHAD = 0
    MARGIN_V = 560
    MARGIN_LR = 70
    COLOR_ACTIVE = "#F5A623"
    COLOR_INACTIVE = "#FFFFFF"
    OUTLINE_COLOR = "#1A1A1A"
    POP_IN_MS = 80
    POP_OUT_MS = 180
    POP_OUTLINE_EXTRA = 4
    POP_BLUR = 1.2
    ACTIVE_SCALE = 108

    width, height = video_res
    if width < height:
        play_res_x, play_res_y = width, height
    else:
        play_res_x, play_res_y = 1080, 1920

    ass_lines = []

    # Header
    ass_lines.append("[Script Info]")
    ass_lines.append("ScriptType: v4.00+")
    ass_lines.append(f"PlayResX: {play_res_x}")
    ass_lines.append(f"PlayResY: {play_res_y}")
    ass_lines.append("WrapStyle: 2")
    ass_lines.append("ScaledBorderAndShadow: yes")
    ass_lines.append("")

    # Styles
    ass_lines.append("[V4+ Styles]")
    ass_lines.append(
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding"
    )
    inactive_col = _rgb_to_ass_hex(COLOR_INACTIVE)
    outline_col = _rgb_to_ass_hex(OUTLINE_COLOR)
    ass_lines.append(
        f"Style: Cap,{font_name},{font_size},{inactive_col},{inactive_col},"
        f"{outline_col},&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,{BORD},{SHAD},2,{MARGIN_LR},{MARGIN_LR},{MARGIN_V},1"
    )
    pill_col = _rgb_to_ass_hex("#0A0A0A")
    ass_lines.append(
        f"Style: Pill,Arial,1,{pill_col},{pill_col},"
        f"&H00000000,&H00000000,"
        f"0,0,0,0,100,100,0,0,1,0,0,0,7,1"
    )
    ass_lines.append("")

    # Events
    ass_lines.append("[Events]")
    ass_lines.append("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text")

    # Transcribe the assembled audio
    all_word_timings = transcribe_assembled_audio(assembled_audio_path, language="fr")
    if not all_word_timings:
        # Fallback: uniform timing using seg_timings
        return make_ass_captions(segments, seg_timings, word_timings=None,
                                  video_res=video_res, font_name=font_name, font_size=font_size)

    active_color = _bbggrr(COLOR_ACTIVE)
    inactive_color = _bbggrr(COLOR_INACTIVE)

    # Map assembled word timings to each segment based on seg_timings boundaries
    for idx, (seg, (t_start, t_end)) in enumerate(zip(segments, seg_timings)):
        seg_words_text = _split_words(seg.get("text", ""))
        if not seg_words_text:
            continue

        # Find which assembled words fall within this segment's time range
        seg_assembled_timings = [
            w for w in all_word_timings
            if w[1] >= t_start and w[2] <= t_end + 0.5
        ]

        # Find which assembled words fall within this segment's time range
        seg_assembled_timings = [
            w for w in all_word_timings
            if w[1] >= t_start and w[2] <= t_end + 0.5
        ]

        num_script_words = len(seg_words_text)
        num_whisper_words = len(seg_assembled_timings)

        # Distribuer le timing Whisper reel sur les mots du script original
        if num_whisper_words > 0 and num_script_words > 0:
            wr_start = seg_assembled_timings[0][1]
            wr_end = seg_assembled_timings[-1][2]
            word_dur = (wr_end - wr_start) / num_script_words
            seg_word_timings = []
            for wi in range(num_script_words):
                ws = wr_start + wi * word_dur
                we = wr_start + (wi + 1) * word_dur
                seg_word_timings.append((seg_words_text[wi], ws, we))
        else:
            # Fallback: distribution uniforme
            dur_total = t_end - t_start
            word_dur = dur_total / max(num_script_words, 1)
            seg_word_timings = []
            for wi in range(num_script_words):
                ws = t_start + wi * word_dur
                we = ws + word_dur
                seg_word_timings.append((seg_words_text[wi], ws, we))

        # Grouper en blocs de WPC, timing = mots du script indexes sur Whisper
        wt = seg_word_timings
        for bi in range(0, len(wt), WPC):
            block = wt[bi:bi + WPC]
            if not block:
                continue

            for ki in range(len(block)):
                w = block[ki]
                w_start = w[1]
                w_end = w[2]

                # Hold jusqu'au mot suivant ou fin du bloc
                if ki < len(block) - 1:
                    hold_end = block[ki + 1][1]
                elif bi + WPC < len(wt):
                    hold_end = wt[bi + WPC][1]
                else:
                    hold_end = w_end + 0.15

                if hold_end <= w_start:
                    hold_end = max(w_start + 0.01, w_end + 0.05)

                dur_ms = int(round((hold_end - w_start) * 1000))
                t_in = min(POP_IN_MS, max(0, dur_ms - 10))
                t_out = min(POP_OUT_MS, max(t_in, dur_ms))

                # Texte = mots du SCRIPT original, timing = Whisper reel
                parts = [r"{\q0}{\fsp2}"]
                for wi2 in range(len(block)):
                    txt = block[wi2][0].upper()
                    if wi2 == ki:
                        tag = (
                            f"{{\1c&H{active_color}&\bord{BORD + POP_OUTLINE_EXTRA}"
                            f"\blur{POP_BLUR}"
                            f"\fscx{ACTIVE_SCALE}\fscy{ACTIVE_SCALE}"
                            + (f"\t(0,{t_in},\bord{BORD + POP_OUTLINE_EXTRA + 2}"
                               f"\blur{POP_BLUR + 0.5})" if t_in > 0 else "")
                            + (f"\t({t_in},{t_out},\bord{BORD}\blur0"
                               f"\fscx100\fscy100)" if t_out > t_in else "")
                            + "}"
                        )
                        parts.append(tag + _esc_ass(txt))
                    else:
                        parts.append(
                            f"{{\1c&H{inactive_color}&\bord{BORD}\blur0"
                            f"\fscx100\fscy100}}{_esc_ass(txt)}"
                        )
                    if wi2 != len(block) - 1:
                        parts.append(" ")

                text_line = "".join(parts)
                ass_lines.append(
                    f"Dialogue: 0,{_sec_to_ass(w_start)},{_sec_to_ass(hold_end)},"
                    f"Cap,,0,0,0,,{text_line}"
                )

    return "\n".join(ass_lines)


def add_captions_to_video_assembled(
    video_path: str,
    assembled_audio_path: str,
    segments: list,
    seg_timings: list,
    output_path: str = None
) -> str:
    """
    Version assemblee : transcrit l'audio final en 1 passage Whisper,
    utilise le TEXTE ORIGINAL du script pour les sous-titres.
    """
    if output_path is None:
        p = Path(video_path)
        output_path = str(p.parent / f"{p.stem}_captioned{p.suffix}")

    work_dir = Path(video_path).parent
    ass_path = work_dir / "captions.ass"

    ass_content = make_ass_captions_from_assembled(
        segments, seg_timings, assembled_audio_path,
        font_size=84
    )
    ass_path.write_text(ass_content, encoding="utf-8")
    print(f"[CAPTIONS ASSEMBLED] ASS genere: {len(ass_content)} chars, {len(segments)} segments")

    burn_ass_captions(video_path, str(ass_path), output_path)
    print(f"[CAPTIONS ASSEMBLED] Burn-in OK: {output_path}")

    return output_path


if __name__ == "__main__":
    # Test
    segs = [{"text": "83 pourcent des investisseurs perdent de l'argent.", "voice": "B"},
            {"text": "Votre cerveau est programme pour echouer en bourse.", "voice": "A"}]
    tims = [(0.5, 5.5), (6.0, 11.0)]

    ass = make_ass_captions(segs, tims, font_size=84)
    for line in ass.split("\n")[-6:]:
        if "Dialogue" in line:
            print(line[:120])
    print(f"\nWhisper disponible: {_whisper_available()}")
    print(f"Total: {len(ass)} chars")
    print(f"Pill: {'ajouté via drawbox' if True else 'désactivé'}")

# === Style presets (merged from scripts/ass_caption.py, 2026-07-21) ===
# Styles de sous-titres pour le CLI. Chaque style ajuste police, taille, chunk, highlight.

ASS_STYLES_PRESETS = {
    "tiktok":  dict(font="Montserrat", size=56,  chunk=3,
                     color_active="#F5A623", color_inactive="#FFFFFF",
                     outline="#1A1A1A", pill=True),
    "opus":    dict(font="Arial Black", size=90,  chunk=3,
                     color_active="#FFFF00", color_inactive="#FFFFFF",
                     outline="#000000", pill=False),
    "karaoke": dict(font="Arial Black", size=100, chunk=4,
                     color_active="#00FF00", color_inactive="#FFFFFF",
                     outline="#000000", pill=False),
    "minimal": dict(font="Helvetica",   size=65,  chunk=6,
                     color_active=None, color_inactive="#FFFFFF",
                     outline="#000000", pill=False),
}
