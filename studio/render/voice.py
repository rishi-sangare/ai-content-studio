"""Narration voice: design a voice once from a text description, then clone that exact voice for every script.

- design(): Qwen3-TTS VoiceDesign turns a description into speech (used once to create the channel voice).
- speak():  Qwen3-TTS Base clones the saved reference so every clip has the same narrator.
Models live in ~/.cache/rishi-reel-models (see CLAUDE.md).
"""
import json
from pathlib import Path

import numpy as np
import soundfile as sf

MODELS = Path.home() / ".cache" / "rishi-reel-models" / "mlx-community"
DESIGN = MODELS / "Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit"
BASE = MODELS / "Qwen3-TTS-12Hz-1.7B-Base-8bit"
_cache = {}


def _model(path):
    if path not in _cache:
        from mlx_audio.tts.utils import load_model
        _cache[path] = load_model(str(path))
    return _cache[path]


def _save(results, out: Path) -> Path:
    audio = np.concatenate([np.array(r.audio) for r in results])
    sr = getattr(results[0], "sample_rate", 24000)
    out.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out, audio, sr)
    return out


def design(text: str, description: str, out: Path, seed: int = 0) -> Path:
    import mlx.core as mx
    mx.random.seed(seed)
    res = list(_model(DESIGN).generate_voice_design(text=text, language="English", instruct=description))
    return _save(res, out)


def speak(text: str, voice_dir: Path, out: Path, seed: int = 0) -> Path:
    """Say `text` in the channel voice saved at voice_dir (reference.wav + reference.json)."""
    import mlx.core as mx
    mx.random.seed(seed)
    ref = json.loads((voice_dir / "reference.json").read_text())
    res = list(_model(BASE).generate(text=text, ref_audio=str(voice_dir / "reference.wav"), ref_text=ref["text"]))
    return _save(res, out)


def _trim(audio: np.ndarray, sr: int, thresh_db: float = -40, pad: float = 0.03) -> np.ndarray:
    """Cut leading/trailing silence, keeping a small pad."""
    lvl = 10 ** (thresh_db / 20) * np.abs(audio).max()
    idx = np.where(np.abs(audio) > lvl)[0]
    if not idx.size:
        return audio
    a, b = max(0, idx[0] - int(pad * sr)), min(audio.size, idx[-1] + int(pad * sr))
    return audio[a:b]


def _squeeze_pauses(audio: np.ndarray, sr: int, max_gap: float = 0.25, thresh_db: float = -38) -> np.ndarray:
    """Shorten silences inside a take to max_gap (TTS sometimes leaves long breaths between sentences)."""
    hop = int(0.01 * sr)
    n = audio.size // hop
    rms = np.sqrt(np.mean(audio[: n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)
    quiet = 20 * np.log10(rms / (np.abs(audio).max() + 1e-9)) < thresh_db
    keep, i, out = int(max_gap / 0.01), 0, []
    while i < n:
        j = i
        while j < n and quiet[j] == quiet[i]:
            j += 1
        seg = audio[i * hop: j * hop]
        if quiet[i] and (j - i) > keep:          # keep the edges of the pause, drop the middle
            half = keep * hop // 2
            seg = np.concatenate([seg[:half], seg[-half:]])
        out.append(seg)
        i = j
    return np.concatenate(out + [audio[n * hop:]])


def speak_lines(lines: list[dict], voice_dir: Path, out_dir: Path, seeds=(0, 1, 2)) -> Path:
    """Comic timing: each line is its own take, joined with a chosen gap after it.

    lines: [{"id": "l1", "text": "...", "gap": 0.4}]. For every line, the first seed whose take transcribes
    back word-for-word is kept (else the closest). Writes takes to out_dir/lines/, the joined vo.wav, and
    vo.lines.json (start/end of each line in the joined track)."""
    import hashlib
    import re
    from studio.render import transcribe
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower().replace("-", " ")).split()
    ld = out_dir / "lines"; ld.mkdir(parents=True, exist_ok=True)
    parts, spans, t, sr = [], [], 0.0, 24000
    for ln in lines:
        best = None
        key = hashlib.sha1(ln["text"].encode()).hexdigest()[:6]      # re-use takes while the text is unchanged
        for s in seeds:
            p = ld / f"{ln['id']}_{key}_s{s}.wav"
            if not p.exists():
                speak(ln["text"], voice_dir, p, seed=s)
            heard = " ".join(w["word"] for w in json.loads(transcribe.transcribe(p).read_text())["words"])
            want, got = norm(ln["text"]), norm(heard)
            score = sum(a == b for a, b in zip(want, got)) - abs(len(want) - len(got))
            if best is None or score > best[0]:
                best = (score, p, heard)
            if got == want:
                break
        audio, sr = sf.read(best[1])
        audio = _squeeze_pauses(_trim(audio, sr), sr)
        spans.append({"id": ln["id"], "text": ln["text"], "heard": best[2], "take": best[1].name,
                      "start": round(t, 3), "end": round(t + audio.size / sr, 3)})
        parts += [audio, np.zeros(int(ln.get("gap", 0.15) * sr))]
        t += audio.size / sr + ln.get("gap", 0.15)
    out = out_dir / "vo.wav"
    sf.write(out, np.concatenate(parts), sr)
    (out_dir / "vo.lines.json").write_text(json.dumps(spans, indent=1))
    return out
