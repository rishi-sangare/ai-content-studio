"""Screen-demo panel (Remotion "ScreenDemo"): a real page screenshot driven like a screen recording, plus its sounds.

Timeline JSON = ScreenDemo props (see studio/motion/src/ScreenDemo.tsx): scenes (img, url, typeFrom/typeTo, loadAt), cam and
cursor keyframes in screenshot pixels, clicks, marks, cards. Screenshots go in studio/motion/public/web/ (capture with
`capture(url, name)`: headless Chrome, 540 px wide at 2x = 1080 px, tall page).
sounds(props) → events (keyboard ticks while typing, Enter on load, mouse clicks, pop on cards) for the reel's audio mix.
Preview: uv run python -m studio.render.screendemo <timeline.json> <out.mp4>
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

MOTION = Path(__file__).resolve().parents[1] / "motion"
SFX = Path(__file__).resolve().parent / "assets" / "sfx"
SR = 48000


def capture(url: str, name: str, height: int = 2400) -> Path:
    chrome = next((MOTION / "node_modules/.remotion/chrome-headless-shell").rglob("chrome-headless-shell"))
    out = MOTION / "public" / "web" / f"{name}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(chrome), "--headless", "--hide-scrollbars", f"--window-size=540,{height}", "--force-device-scale-factor=2",
                    "--virtual-time-budget=8000", f"--screenshot={out}", url], check=True, capture_output=True)
    return out


def _key_tick(rng) -> np.ndarray:
    n = int(0.03 * SR)
    noise = rng.standard_normal(n) * np.exp(-np.linspace(0, 9, n))
    body = np.sin(2 * np.pi * rng.uniform(1700, 2600) * np.arange(n) / SR) * np.exp(-np.linspace(0, 14, n))
    return (0.6 * np.convolve(noise, np.ones(6) / 6, "same") + 0.4 * body) * rng.uniform(0.6, 1.0)


def _load(name):
    a, sr = sf.read(SFX / name)
    a = a.mean(1) if a.ndim > 1 else a
    if sr != SR:
        a = np.interp(np.arange(int(len(a) * SR / sr)) / SR, np.arange(len(a)) / sr, a)
    return a


def sounds(props: dict) -> np.ndarray:
    """Mono track (48 kHz) with every sound the screen makes."""
    rng = np.random.default_rng(7)
    out = np.zeros(int((props["duration"] + 1) * SR))

    def put(t, a, db):
        i = int(t * SR); a = a[: len(out) - i] * 10 ** (db / 20); out[i:i + len(a)] += a

    for s in props["scenes"]:
        if s.get("typeFrom") is not None:
            n = len(s["url"])
            for k in range(n):
                put(s["typeFrom"] + (s["typeTo"] - s["typeFrom"]) * k / n + rng.uniform(-0.015, 0.015), _key_tick(rng), -20)
        if s.get("loadAt") is not None:
            put(s["loadAt"] - 0.02, _key_tick(rng) * 1.6, -16)            # Enter
    click = _load("click.wav")
    for c in props["clicks"]:
        put(c, click, -12)
    pop = _load("pop.wav")
    for c in props.get("cards", []):
        put(c["start"], pop, -13)
    return out


def preview(timeline: Path, out: Path):
    props = json.loads(Path(timeline).read_text())
    silent = out.with_suffix(".silent.mp4")
    subprocess.run(["npx", "remotion", "render", "src/index.ts", "ScreenDemo", str(silent.resolve()), f"--props={Path(timeline).resolve()}",
                    "--codec=h264", "--crf=16", "--concurrency=8", "--log=error"], cwd=MOTION, check=True)
    wav = out.with_suffix(".wav")
    sf.write(wav, sounds(props), SR)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], check=True)
    silent.unlink(); wav.unlink()
    return out


if __name__ == "__main__":
    print(preview(Path(sys.argv[1]), Path(sys.argv[2])))
