
#!/usr/bin/env python3
"""word_timings.py - Robust word timings using cached openai-whisper."""
import time as _time

def get_word_timings(audio_paths, segment_texts, timeout_per_file=120):
    """Get word-level timings from audio files using openai-whisper."""
    import whisper
    try:
        print("[WT] Loading cached whisper base...")
        t0 = _time.time()
        model = whisper.load_model("base")
        print(f"[WT] Loaded in {_time.time()-t0:.1f}s")
        all_words = []
        cum = 0.0
        for i, (ap, txt) in enumerate(zip(audio_paths, segment_texts)):
            try:
                result = model.transcribe(
                    str(ap), word_timestamps=True,
                    language="fr", fp16=False
                )
                seg_words = []
                for seg in result.get("segments", []):
                    for w in seg.get("words", []):
                        wt = w.get("word", "").strip()
                        if wt:
                            seg_words.append({
                                "word": wt,
                                "segment_index": i,
                                "local_start": w.get("start", 0),
                                "local_end": w.get("end", 0),
                                "start": w.get("start", 0) + cum,
                                "end": w.get("end", 0) + cum
                            })
                all_words.extend(seg_words)
                if seg_words:
                    cum = seg_words[-1]["end"]
            except Exception as e:
                print(f"[WT] Segment {i}: {e}")
                wds = txt.split()
                wd = 0.35
                for j, w in enumerate(wds):
                    all_words.append({
                        "word": w,
                        "start": cum + j * wd,
                        "end": cum + (j + 1) * wd
                    })
                cum += len(wds) * wd
        print(f"[WT] Done: {len(all_words)} words")
        return all_words
    except Exception as e:
        print(f"[WT] FAIL: {e}")
        return None


def make_ass_captions(segments, seg_times, word_timings=None,
                       font_name="Montserrat", font_size=84, margin_v=50):
    """Generate ASS subtitle file content."""

    def s2a(sec):
        h = int(sec // 3600)
        m = int((sec % 3600) // 60)
        s = sec % 60
        return f"{h}:{m:02d}:{s:05.2f}"

    lines = []
    lines.append("[Script Info]")
    lines.append("Title: Alfred AI")
    lines.append("ScriptType: v4.00+")
    lines.append("Collisions: Normal")
    lines.append("PlayDepth: 0")
    lines.append("")
    lines.append("[V4+ Styles]")
    lines.append("Format: Name, Fontname, Fontsize, PrimaryColour, "
                 "SecondaryColour, OutlineColour, BackColour, Bold, "
                 "Italic, Underline, StrikeOut, ScaleX, ScaleY, "
                 "Spacing, Angle, BorderStyle, Outline, Shadow, "
                 "Alignment, MarginL, MarginR, MarginV, Encoding")
    afs = int(font_size * 1.08)
    lines.append(f"Style: Default,{font_name},{font_size},&H00FFFFFF,"
                 f"&H000000FF,&H00000000,&H80000000,1,0,0,0,"
                 f"100,100,0,0,1,4,0,2,50,50,{margin_v},1")
    lines.append(f"Style: Active,{font_name},{afs},&H00F5A623,"
                 f"&H000000FF,&H00000000,&H80000000,1,0,0,0,"
                 f"100,100,0,0,1,4,0,2,50,50,{margin_v},1")
    lines.append("")
    lines.append("[Events]")
    lines.append("Format: Layer, Start, End, Style, Name, "
                 "MarginL, MarginR, MarginV, Effect, Text")

    for si, (ss, se) in enumerate(seg_times):
        if isinstance(segments[si], dict):
            txt = segments[si].get("text", "")
        else:
            txt = str(segments[si])
        words_in_seg = txt.split()

        seg_words = []
        if word_timings:
            # Format segmente: liste par segment de tuples (word, local_start, local_end)
            if isinstance(word_timings[0], (list, tuple)) and si < len(word_timings):
                try:
                    seg_words = [
                        {"start": ss + w[1], "end": ss + w[2], "word": w[0]}
                        for w in word_timings[si]
                        if isinstance(w, (list, tuple)) and len(w) >= 3
                    ]
                except Exception:
                    seg_words = []
            else:
                # Format plat: liste de dicts (start/end/word globaux)
                seg_words = [
                    w for w in word_timings
                    if w["start"] >= ss - 0.05 and w["end"] <= se + 0.1
                ]

        if seg_words:
            for w in seg_words:
                lines.append(
                    f"Dialogue: 0,{s2a(w['start'])},{s2a(w['end'])},"
                    f"Active,,0,0,0,,{w['word']}"
                )
        else:
            dur = se - ss
            wd = dur / max(len(words_in_seg), 1)
            for j, word in enumerate(words_in_seg):
                ws = ss + j * wd
                we = ws + wd
                lines.append(
                    f"Dialogue: 0,{s2a(ws)},{s2a(we)},"
                    f"Active,,0,0,0,,{word}"
                )

    return "\n".join(lines)


def burn_ass_captions(video_path, ass_path, output_path):
    """Burn ASS subtitles into video using ffmpeg."""
    import subprocess
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-vf", f"ass={ass_path}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k",
        str(output_path)
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    return output_path
