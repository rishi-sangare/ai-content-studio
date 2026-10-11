"""Word-level transcript with timings (Parakeet TDT v3 on MLX, runs locally).

Output JSON: {"text": "...", "words": [{"word": "Hello", "start": 0.32, "end": 0.61}, ...],
              "sentences": [{"text": "...", "start": .., "end": ..}]}
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

MODEL = "mlx-community/parakeet-tdt-0.6b-v3"
_model = None


def _load():
    global _model
    if _model is None:
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        from parakeet_mlx import from_pretrained
        _model = from_pretrained(MODEL)
    return _model


def transcribe(video: Path, out: Path | None = None) -> Path:
    video = Path(video)
    out = out or video.with_suffix(".words.json")
    with tempfile.TemporaryDirectory() as td:
        wav = Path(td) / "a.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-ac", "1", "-ar", "16000", str(wav)],
                       check=True)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(wav)], capture_output=True, text=True).stdout)
        # long episodes: chunk so memory stays flat
        res = _load().transcribe(wav, chunk_duration=120.0 if dur > 180 else None)
    words, cur = [], None
    for s in res.sentences:
        for t in s.tokens:
            piece = t.text
            if piece.startswith(" ") or cur is None:
                if cur:
                    words.append(cur)
                cur = {"word": piece.strip(), "start": round(t.start, 3), "end": round(t.end or t.start + t.duration, 3)}
            else:
                cur["word"] += piece
                cur["end"] = round(t.end or t.start + t.duration, 3)
    if cur:
        words.append(cur)
    words = [w for w in words if w["word"]]
    data = {"text": res.text, "words": words,
            "sentences": [{"text": s.text.strip(), "start": round(s.start, 3), "end": round(s.end, 3)} for s in res.sentences]}
    out.write_text(json.dumps(data, indent=1))
    return out


def readable(words_json: Path, every: float = 8.0) -> str:
    """Compact transcript with a timestamp every ~8s — what Claude reads to pick moments."""
    data = json.loads(Path(words_json).read_text())
    lines, cur, t0 = [], [], None
    for w in data["words"]:
        if t0 is None:
            t0 = w["start"]
        cur.append(w["word"])
        if w["end"] - t0 >= every:
            lines.append(f"[{t0:7.2f}] {' '.join(cur)}")
            cur, t0 = [], None
    if cur:
        lines.append(f"[{t0:7.2f}] {' '.join(cur)}")
    return "\n".join(lines)
