"""Sound effects. Synthesised ones (no licensing issues) are generated once into studio/render/assets/sfx/*.wav.

Meme sounds: a real file dropped into assets/sfx/memes/<name>.(wav|mp3|m4a|ogg) always wins over the
synthesised or AI-voiced stand-in of the same name (boom, scratch, wahwah, chaching, gulp, choir, boing,
ding, airhorn, bruh, faaah).
"""
import wave
from pathlib import Path

import numpy as np

SR = 44100
ASSETS = Path(__file__).resolve().parent / "assets" / "sfx"


def _write(name, x):
    ASSETS.mkdir(parents=True, exist_ok=True)
    x = np.clip(x / (np.abs(x).max() + 1e-9) * 0.9, -1, 1)
    pcm = (x * 32767).astype(np.int16)
    with wave.open(str(ASSETS / f"{name}.wav"), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def _t(sec):
    return np.arange(int(SR * sec)) / SR


def build_all():
    rng = np.random.default_rng(7)
    # camera shutter: two short filtered noise clicks
    t = _t(0.16)
    n = rng.standard_normal(t.size)
    env = np.exp(-t * 90) + 0.7 * np.exp(-np.clip(t - 0.07, 0, None) * 120) * (t > 0.07)
    shutter = np.convolve(n, np.ones(6) / 6, "same") * env
    _write("shutter", shutter)
    # whoosh: band-swept noise with a swell
    t = _t(0.45)
    n = rng.standard_normal(t.size)
    swell = np.sin(np.pi * t / t[-1]) ** 2
    k = np.linspace(40, 4, t.size).astype(int)
    sm = np.array([n[max(0, i - k[i]):i + 1].mean() for i in range(t.size)])
    _write("whoosh", sm * swell)
    # click: tiny transient
    t = _t(0.05)
    _write("click", np.sin(2 * np.pi * 2200 * t) * np.exp(-t * 180))
    # pop: pitched blip for caption emphasis
    t = _t(0.12)
    f = np.linspace(900, 300, t.size)
    _write("pop", np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 35))


def _reverb(x, sec=0.8, mix=0.35, seed=3):
    t = _t(sec)
    ir = np.random.default_rng(seed).standard_normal(t.size) * np.exp(-t * 6)
    wet = np.convolve(x, ir)[: x.size + t.size]
    wet = np.pad(wet, (0, x.size + t.size - wet.size))
    dry = np.concatenate([x, np.zeros(t.size)])
    return dry + mix * wet / (np.abs(wet).max() + 1e-9) * np.abs(x).max()


def _saw(freq, t, n=12):
    ph = 2 * np.pi * np.cumsum(np.broadcast_to(freq, t.shape)) / SR
    return sum(np.sin(k * ph) / k for k in range(1, n + 1))


def build_memes():
    rng = np.random.default_rng(11)
    # boom: deep dropping thud with a room tail (vine-boom style)
    t = _t(0.9)
    f = 45 + 75 * np.exp(-t * 9)
    x = np.tanh(2.5 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 4.0))
    x[:300] += rng.standard_normal(300) * np.linspace(1, 0, 300) * 0.6
    _write("boom", _reverb(x, 1.0, 0.5))
    # record scratch: fast back-and-forth pitch sweep of a buzzy tone + vinyl noise
    t = _t(0.38)
    f = 250 + 900 * np.abs(np.sin(2 * np.pi * 2.6 * t)) ** 1.5
    x = _saw(f, t, 8) * 0.6 + np.convolve(rng.standard_normal(t.size), np.ones(4) / 4, "same") * 0.5
    _write("scratch", x * np.minimum(1, (0.38 - t) * 12))
    # sad trombone "wah wah wah waaah": four falling notes, the last with vibrato
    notes = [(233.1, 0.2), (220.0, 0.2), (207.7, 0.2), (196.0, 0.7)]
    out = []
    for i, (hz, d) in enumerate(notes):
        t = _t(d)
        vib = 1 + (0.02 * np.sin(2 * np.pi * 6 * t) * (t > 0.15) if i == 3 else 0)
        wah = np.clip(t / 0.12, 0, 1) * (np.exp(-np.clip(t - d + 0.25, 0, None) * 8))
        out.append(_saw(hz * vib, t, 10) * wah)
    _write("wahwah", _reverb(np.concatenate(out), 0.5, 0.25))
    # cha-ching: drawer rattle then a bright bell
    t = _t(0.1)
    cha = rng.standard_normal(t.size) * np.exp(-t * 40)
    t = _t(0.9)
    bell = (np.sin(2 * np.pi * 2093 * t) + 0.6 * np.sin(2 * np.pi * 3136 * t) + 0.3 * np.sin(2 * np.pi * 4186 * t)) * np.exp(-t * 5)
    _write("chaching", np.concatenate([cha * 0.5, np.zeros(int(0.04 * SR)), bell]))
    # gulp: two pitched bubbles
    g = []
    for _ in range(2):
        t = _t(0.16)
        f = 520 * np.exp(-t * 9) + 140
        g += [np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 18), np.zeros(int(0.07 * SR))]
    _write("gulp", np.concatenate(g))
    # angelic choir "aaah": major chord, vowel-ish harmonics, vibrato, slow swell
    t = _t(1.6)
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.2 * t)
    x = 0
    for hz in (261.6, 329.6, 392.0, 523.3, 659.3):
        ph = 2 * np.pi * np.cumsum(hz * vib) / SR
        for k in range(1, 9):
            w = np.exp(-((k * hz - 750) / 350) ** 2) + 0.5 * np.exp(-((k * hz - 1150) / 300) ** 2) + 0.2 / k
            x = x + w * np.sin(k * ph + k)
    env = np.clip(t / 0.25, 0, 1) * np.clip((1.6 - t) / 0.5, 0, 1)
    _write("choir", _reverb(x * env, 1.2, 0.6))
    # boing: wobbling spring
    t = _t(0.55)
    f = 180 * (1 + 0.5 * np.sin(2 * np.pi * 14 * t) * np.exp(-t * 5)) * (1 + t)
    _write("boing", np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5))
    # ding: clean bell
    t = _t(0.8)
    _write("ding", (np.sin(2 * np.pi * 1568 * t) + 0.4 * np.sin(2 * np.pi * 3920 * t)) * np.exp(-t * 6))
    # airhorn: three detuned-saw blasts
    blasts = []
    for d in (0.18, 0.18, 0.6):
        t = _t(d)
        x = sum(_saw(440 * m, t, 14) for m in (1.0, 1.006, 0.994, 1.498))
        blasts += [np.tanh(1.5 * x) * np.minimum(1, t / 0.01) * np.minimum(1, (d - t) / 0.03), np.zeros(int(0.05 * SR))]
    _write("airhorn", np.concatenate(blasts))


MEMES = ASSETS / "memes"


def path(name: str) -> Path:
    for ext in ("wav", "mp3", "m4a", "ogg", "aac"):
        real = MEMES / f"{name}.{ext}"
        if real.exists():
            return real
    p = ASSETS / f"{name}.wav"
    if not p.exists() and not (ASSETS / "boom.wav").exists():
        build_all()
        build_memes()
    return p


def pick(spec: str) -> Path | None:
    """"faaah|wahwah" -> the first sound that exists (a real meme file, or a built stand-in)."""
    for name in spec.split("|"):
        p = path(name)
        if p.exists():
            return p
    return None


# myinstants file name -> Studio name (see streams/clipping/research/meme-sounds.md)
MYINSTANTS = {
    "faaah.mp3": "faaah", "fahhhhhhhhhhhhhh.mp3": "fahhh_long", "vine-boom.mp3": "vine_boom", "movie_1.mp3": "bruh",
    "anime-wow-sound-effect.mp3": "anime_wow", "rizz-sound-effect.mp3": "rizz", "metal-pipe-clang.mp3": "metal_pipe",
    "sadtrombone.swf.mp3": "sad_trombone", "record-scratch.mp3": "record_scratch", "ka-ching.mp3": "kaching",
    "huh-cat.mp3": "huh_cat", "yippee-tbh.mp3": "yippee", "mlg-airhorn.mp3": "airhorn", "ding-sound-effect_2.mp3": "ding",
    "wrong-answer-sound-effect.mp3": "buzzer", "dun-dun-dun-sound-effect-brass_8nFBccR.mp3": "dun_dun_dun",
    "original-sheesh.mp3": "sheesh", "gulp-gulp-sfx.mp3": "gulp", "angel-choirrr.mp3": "angel_choir",
    "hallelujahshort.swf.mp3": "hallelujah", "cartoon-boing_7vRWDlc.mp3": "boing", "cartoon-bonk.mp3": "bonk",
    "shocked-sound-effect.mp3": "shocked", "wait-what.mp3": "wait_what", "applepay.mp3": "apple_pay",
}


def import_memes(src: Path = Path.home() / "Downloads") -> list[str]:
    """Copy downloaded meme sounds into assets/sfx/memes/<name>.wav, trimmed of silence and levelled
    (peak -1 dB) so every sound sits at a predictable volume. The originals are left where they are."""
    import subprocess
    MEMES.mkdir(parents=True, exist_ok=True)
    done = []
    for fname, name in MYINSTANTS.items():
        hits = sorted(src.glob(fname.replace(".mp3", "*.mp3")), key=lambda p: p.stat().st_mtime)
        if not hits:
            continue
        tmp = MEMES / f"{name}.tmp.wav"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(hits[-1]), "-ac", "2", "-ar", "48000",
                        "-af", "silenceremove=start_periods=1:start_threshold=-45dB", str(tmp)], check=True)
        peak = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(tmp), "-af", "volumedetect", "-f", "null", "-"],
                              capture_output=True, text=True).stderr
        mx = float(peak.split("max_volume:")[1].split("dB")[0]) if "max_volume:" in peak else 0.0
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(tmp), "-af", f"volume={-1 - mx:.1f}dB",
                        str(MEMES / f"{name}.wav")], check=True)
        tmp.unlink()
        done.append(name)
    return done
