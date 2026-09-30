#!/usr/bin/env python3
"""
find_viral_moments.py — Détection des moments viraux dans un transcript.

Restauré le 2026-09-29 : le fichier source avait disparu (seul un .pyc orphelin
du 20/07 subsistait), ce qui faisait échouer l'import dans pipeline_orchestrator.py
(ligne ~1491) et produisait "🔥 Viral: analyse impossible" dans le rapport Telegram.

API attendue par le pipeline :
    from find_viral_moments import find_moments
    moments = find_moments(json_path, top_n=3, min_dur=4, max_dur=20)
    # -> [{"start","end","text","score","signals","detail"}, ...] trié par score desc
    # "score" est sur une échelle 0-100

Le JSON d'entrée a le format {"segments": [{"start": float, "end": float, "text": str}, ...]}
(segments Whisper ou word_timings de Stage 4).

Usage CLI :
    python3 find_viral_moments.py --json audio.json [--top 3] [--min-dur 4] [--max-dur 20]
"""

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

# ─── Signaux de scoring viral ────────────────────────────────
# Poids inspirés du module viral_moments.py d'origine (Clipify).
VIRAL_SIGNALS = {
    "question": {
        "patterns": [
            r"(?i)savez-vous\b", r"(?i)vous\s+savez\s+(quoi|pourquoi|comment)",
            r"(?i)quel\s+est\b", r"(?i)pourquoi\b", r"(?i)comment\b",
            r"(?i)combien\b", r"(?i)est-ce\s+que\b", r"\?",
        ],
        "score": 1.5,
    },
    "data_point": {
        "patterns": [
            r"\d+[\s%,]", r"(?i)millions?\b", r"(?i)milliards?",
            r"(?i)\d+e?\s*fois\b", r"(?i)\d+\s*sur\s*\d+", r"\d+\s*%",
        ],
        "score": 1.4,
    },
    "contrast": {
        "patterns": [
            r"(?i)mais\b", r"(?i)pourtant\b", r"(?i)cependant\b",
            r"(?i)en\s+réalité\b", r"(?i)en\s+fait\b",
            r"(?i)c'est\s+l'inverse\b",
        ],
        "score": 1.3,
    },
    "fear_anger": {
        "patterns": [
            r"(?i)erreur\b", r"(?i)piège\b", r"(?i)danger\b",
            r"(?i)perte?\b", r"(?i)pire\b", r"(?i)catastroph",
            r"(?i)jamais\b", r"(?i)stop\b", r"(?i)attention\b",
        ],
        "score": 1.4,
    },
    "positive": {
        "patterns": [
            r"(?i)gratuit\b", r"(?i)libre\b", r"(?i)facile\b",
            r"(?i)simple\b", r"(?i)rapide\b", r"(?i)gagner\b",
            r"(?i)profiter\b", r"(?i)génial\b",
        ],
        "score": 1.2,
    },
    "cta": {
        "patterns": [
            r"(?i)abonne", r"(?i)like\b", r"(?i)partage",
            r"(?i)commente", r"(?i)dis-moi\b", r"(?i)clique\b",
        ],
        "score": 1.6,
    },
    "personal": {
        "patterns": [
            r"(?i)j['’](?:ai|étais|avais|suis|allais)",
            r"(?i)mon\s+(?:expérience|histoire|parcours|conseil)",
            r"(?i)je\s+me\s+souviens\b", r"(?i)quand\s+j['’]",
        ],
        "score": 1.3,
    },
    "finance_hook": {
        "patterns": [
            r"(?i)ETF\b", r"(?i)PEA\b", r"(?i)investir\b",
            r"(?i)épargne\b", r"(?i)retraite\b",
            r"(?i)indépendance\s+financière\b",
            r"(?i)liberté\s+financière\b", r"(?i)FIRE\b",
            r"(?i)bourse\b",
        ],
        "score": 1.5,
    },
    "hook": {
        "patterns": [
            r"(?i)^(?:si\s+tu|si\s+vous|voici|découvre|imagine)",
            r"(?i)^(?:tu\s+sais|vous\s+savez)\s+(?:quoi|pourquoi)",
        ],
        "score": 1.8,
    },
}

# Compléments hérités (compat : noms référencés par l'ancien module).
STRONG_WORDS = [
    "erreur", "piège", "danger", "jamais", "toujours", "secret", "gratuit",
    "choc", "catastrophe", "ruine", "faillite", "miracle",
]
REVERSAL_TRIGGERS = [
    r"(?i)mais\b", r"(?i)pourtant\b", r"(?i)en\s+réalité\b",
    r"(?i)c'est\s+l'inverse\b", r"(?i)au\s+contraire\b",
]


def _parse_srt(srt_text: str) -> list:
    """Parse un fichier SRT en segments [{start, end, text}]."""
    segments = []
    for block in re.split(r"\n\n+", srt_text.strip()):
        lines = block.strip().split("\n")
        if len(lines) < 3:
            continue
        time_match = re.match(
            r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)",
            lines[1],
        )
        if not time_match:
            continue

        def _ts(h, m, s, ms):
            return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000

        start = _ts(*[int(x) for x in time_match.groups()[:4]])
        end = _ts(*[int(x) for x in time_match.groups()[4:]])
        text = " ".join(lines[2:]).strip()
        if text:
            segments.append({"start": start, "end": end, "text": text})
    return segments


def _load_segments(path: str) -> list:
    """Charge les segments depuis un JSON (Whisper / word_timings), SRT ou texte."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"transcript introuvable: {path}")
    if p.suffix == ".srt":
        return _parse_srt(p.read_text())

    if p.suffix == ".json":
        data = json.loads(p.read_text())
        if isinstance(data, list):
            raw = data
        elif isinstance(data, dict):
            raw = data.get("segments") or [data]
        else:
            raw = []
        segs = []
        for s in raw:
            if not isinstance(s, dict):
                continue
            text = str(s.get("text", s.get("utterance", "")) or "").strip()
            if not text:
                continue
            start = float(s.get("start", 0) or 0)
            end = float(s.get("end", start) or start)
            segs.append({"start": start, "end": end, "text": text})
        return segs

    return [{"start": 0, "end": 0, "text": p.read_text().strip()}]


def score_segment(text: str, duration: float, position_ratio: float = 0.0) -> dict:
    """Score un texte sur son potentiel viral. Retourne {raw, signals, detail}."""
    if not text or not text.strip():
        return {"raw": 0.0, "signals": [], "detail": "aucun signal"}

    signals_found, raw_score = [], 0.0
    for signal_name, signal_def in VIRAL_SIGNALS.items():
        for pattern in signal_def["patterns"]:
            if re.search(pattern, text):
                raw_score += signal_def["score"]
                signals_found.append(signal_name)
                break

    # Malus durée : un moment trop long dilue l'attention.
    if duration > 20:
        raw_score *= 0.6
    elif duration > 10:
        raw_score *= 0.8
    elif duration < 1.5 and raw_score > 0:
        raw_score *= 0.75

    # Bonus position : hooks (début) et chutes (fin) performent mieux.
    if 0 < position_ratio < 0.15:
        raw_score *= 1.3
    elif position_ratio > 0.85:
        raw_score *= 1.2

    # Bonus densité de signaux.
    if len(signals_found) >= 4:
        raw_score *= 1.5
    elif len(signals_found) >= 3:
        raw_score *= 1.35
    elif len(signals_found) >= 2:
        raw_score *= 1.15

    return {
        "raw": raw_score,
        "signals": signals_found,
        "detail": ", ".join(signals_found) if signals_found else "aucun signal",
    }


def _to_100(raw: float) -> float:
    """Convertit un score brut en échelle 0-100 (saturation douce)."""
    return round(min(100.0, raw * 11.0), 1)


def _merge_segments(segments: list, min_dur: float = 4, max_dur: float = 20) -> list:
    """Regroupe des segments fins (words/phrases) en fenêtres de durée cible."""
    windows, cur = [], None
    for seg in segments:
        start, end = float(seg.get("start", 0)), float(seg.get("end", 0))
        text = seg.get("text", "").strip()
        if not text:
            continue
        if cur is None:
            cur = {"start": start, "end": end, "text": text}
            continue
        if (end - cur["start"]) <= max_dur:
            cur["end"] = end
            cur["text"] = (cur["text"] + " " + text).strip()
        else:
            windows.append(cur)
            cur = {"start": start, "end": end, "text": text}
    if cur:
        windows.append(cur)

    # Fusion des fenêtres trop courtes avec la suivante.
    merged = []
    for w in windows:
        if merged and (w["end"] - w["start"]) < min_dur:
            merged[-1]["end"] = w["end"]
            merged[-1]["text"] = (merged[-1]["text"] + " " + w["text"]).strip()
        else:
            merged.append(w)
    return merged


def find_moments(json_path: str, top_n: int = 3,
                 min_dur: float = 4, max_dur: float = 20) -> list:
    """
    Détecte les moments les plus viraux d'un transcript.

    Retourne une liste triée par score décroissant :
        [{"start", "end", "text", "score" (0-100), "signals", "detail"}, ...]
    """
    segments = _load_segments(str(json_path))
    if not segments:
        return []

    total_duration = max((float(s.get("end", 0) or 0) for s in segments), default=0.0)
    windows = _merge_segments(segments, min_dur=min_dur, max_dur=max_dur)

    results = []
    for w in windows:
        duration = max(w["end"] - w["start"], 0.1)
        position_ratio = (w["start"] / total_duration) if total_duration > 0 else 0.0
        scored = score_segment(w["text"], duration, position_ratio)
        # Densité : récompense les fenêtres riches en signaux par seconde.
        density_bonus = min(1.35, 1.0 + 0.15 * len(scored["signals"]))
        results.append({
            "start": round(w["start"], 2),
            "end": round(w["end"], 2),
            "text": w["text"],
            "score": _to_100(scored["raw"] * density_bonus),
            "signals": scored["signals"],
            "detail": scored["detail"],
            "duration": round(duration, 1),
        })

    results.sort(key=lambda x: -x["score"])
    return results[: max(top_n, 0)]


def main():
    ap = argparse.ArgumentParser(description="Détection de moments viraux")
    ap.add_argument("--json", required=True, help="transcript JSON/SRT")
    ap.add_argument("--top", type=int, default=3)
    ap.add_argument("--min-dur", type=float, default=4)
    ap.add_argument("--max-dur", type=float, default=20)
    args = ap.parse_args()

    try:
        moments = find_moments(args.json, top_n=args.top,
                               min_dur=args.min_dur, max_dur=args.max_dur)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERREUR] {exc}", file=sys.stderr)
        return 1

    if not moments:
        print("Aucun moment viral détecté.")
        return 0

    print(f"Analyse du {datetime.now().strftime('%Y-%m-%d %H:%M')} — "
          f"{len(moments)} moment(s) :\n")
    for i, m in enumerate(moments, 1):
        print(f"#{i} score={m['score']:.0f}/100  [{m['start']:.1f}s→{m['end']:.1f}s] "
              f"({m['detail']})")
        print(f"    {m['text'][:120]}...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
