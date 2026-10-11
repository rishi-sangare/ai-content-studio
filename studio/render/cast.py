"""Multi-voice voiceover (VoxCPM2 via mlx-audio): a narrator plus character voices, line by line.

script.json: {"voices": {"narrator": {"clone_of": "ref.wav", "ref_text": "..."}, "grandpa": {"instruct": "elderly man…"}},
              "lines": [{"id": "n1", "v": "narrator", "text": "…", "gap": 0.25}, …]}
A voice with clone_of copies that recording (same voice every line); a voice with instruct is designed from the
description (used for one-off characters). For every line the first seed whose take transcribes back word for word
is kept. Writes lines/, vo.wav, vo.lines.json (start/end per line) and vo.words.json (word timings for captions).
"""
import hashlib
import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf

from studio.render.voice import _squeeze_pauses, _trim

MODEL = Path.home() / ".cache" / "rishi-reel-models" / "mlx-community" / "VoxCPM2-8bit"
_m = None


def _model():
    global _m
    if _m is None:
        from mlx_audio.tts.utils import load_model
        _m = load_model(str(MODEL))
    return _m


def _take(text, voice, out, seed):
    import mlx.core as mx
    mx.random.seed(seed)
    kw = {}
    if voice.get("clone_of"):
        kw = dict(prompt_audio=voice["clone_of"], prompt_text=voice["ref_text"])
    elif voice.get("instruct"):
        kw = dict(instruct=voice["instruct"])
    res = list(_model().generate(text=text, **kw))
    a = np.concatenate([np.array(r.audio).reshape(-1) for r in res])
    sf.write(out, a, res[0].sample_rate)
    return out


def speak_cast(script: dict, out_dir: Path, seeds=(1, 2, 3, 4), tempo: float = 1.0) -> Path:
    from studio.render import transcribe
    norm = lambda s: re.sub(r"[^a-z0-9 ]", "", s.lower().replace("-", " ")).split()
    ld = out_dir / "lines"; ld.mkdir(parents=True, exist_ok=True)
    parts, spans, t, sr = [], [], 0.0, None
    for ln in script["lines"]:
        voice = script["voices"][ln["v"]]
        key = hashlib.sha1((ln["text"] + json.dumps(voice, sort_keys=True)).encode()).hexdigest()[:6]
        best = None
        for s in seeds:
            p = ld / f"{ln['id']}_{key}_s{s}.wav"
            if not p.exists():
                _take(ln["text"], voice, p, s)
            heard = " ".join(w["word"] for w in json.loads(transcribe.transcribe(p).read_text())["words"])
            want, got = norm(ln["text"]), norm(heard)
            score = sum(a == b for a, b in zip(want, got)) - abs(len(want) - len(got))
            if best is None or score > best[0]:
                best = (score, p, heard)
            if got == want:
                break
        audio, sr = sf.read(best[1])
        audio = audio.mean(1) if audio.ndim > 1 else audio
        audio = _squeeze_pauses(_trim(audio, sr), sr, max_gap=ln.get("max_pause", 0.3))
        if voice.get("fx"):                         # per-character treatment, e.g. grandpa = warm, distant memory
            import subprocess, tempfile
            with tempfile.TemporaryDirectory() as td:
                a_in, a_out = Path(td) / "in.wav", Path(td) / "out.wav"
                sf.write(a_in, audio, sr)
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(a_in), "-af", voice["fx"] + ",apad=pad_dur=0.6",
                                "-ar", str(sr), "-ac", "1", str(a_out)], check=True)
                audio, _ = sf.read(a_out)
                audio = _trim(audio, sr, thresh_db=-50, pad=0.05) if ln.get("trim_tail", False) else audio
        spans.append({"id": ln["id"], "v": ln["v"], "text": ln["text"], "heard": best[2], "take": best[1].name,
                      "exact": best[2] is not None and norm(best[2]) == norm(ln["text"]),
                      "start": round(t, 3), "end": round(t + audio.size / sr, 3)})
        parts += [audio, np.zeros(int(ln.get("gap", 0.15) * sr))]
        t += audio.size / sr + ln.get("gap", 0.15)
    out = out_dir / "vo_raw.wav"
    sf.write(out, np.concatenate(parts), sr)
    final = out_dir / "vo.wav"
    import subprocess
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-af",
                    (f"atempo={tempo}," if abs(tempo - 1) > 1e-3 else "") + "highpass=f=70,acompressor=threshold=-20dB:ratio=3:attack=5:release=80,"
                    "loudnorm=I=-16:TP=-1.5:LRA=9", "-ar", "48000", str(final)], check=True)
    for sp in spans:                                        # line times on the final (tempo-changed) track
        sp["start"] = round(sp["start"] / tempo, 3); sp["end"] = round(sp["end"] / tempo, 3)
    (out_dir / "vo.lines.json").write_text(json.dumps(spans, indent=1))
    transcribe.transcribe(final, out_dir / "vo.words.json")
    return final
