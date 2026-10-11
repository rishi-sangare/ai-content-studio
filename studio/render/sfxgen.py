"""Cinematic sound-design kit, synthesised (no samples, no licences): swells, risers, hits, shimmers, zaps, whooshes, paper.

`uv run python -m studio.render.sfxgen` writes them to assets/sfx/ as cine_*.wav (48 kHz stereo, peak -3 dBFS) so recipes
can use them like any other sound: {"at": 2.4, "sfx": "cine_swell", "db": -10}. Deterministic (fixed seeds).
"""
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
OUT = Path(__file__).resolve().parent / "assets" / "sfx"
rng = np.random.default_rng(7)


def _t(d):
    return np.arange(int(d * SR)) / SR


def _norm(x, peak_db=-3.0):
    x = np.asarray(x, dtype=np.float64)
    m = np.abs(x).max() + 1e-12
    return x / m * 10 ** (peak_db / 20)


def _st(x, width=0.0, seed=0):
    """Mono → stereo; width > 0 decorrelates the sides a little (a short, different delay per side)."""
    if width <= 0:
        return np.stack([x, x], 1)
    dl = int(SR * 0.004 * width); dr = int(SR * 0.009 * width)
    l = np.concatenate([np.zeros(dl), x])[: len(x)]; r = np.concatenate([np.zeros(dr), x])[: len(x)]
    return np.stack([0.75 * x + 0.25 * l, 0.75 * x + 0.25 * r], 1)


def _filt(x, kind, f, order=4):
    sos = butter(order, f, btype=kind, fs=SR, output="sos")
    return sosfilt(sos, x)


def _reverb(x, seconds=1.6, mix=0.35, bright=6000, seed=1):
    r = np.random.default_rng(seed)
    n = int(seconds * SR)
    ir = r.standard_normal(n) * np.exp(-np.arange(n) / SR / (seconds / 5))
    ir = _filt(ir, "low", bright, 2)
    ir /= np.sqrt((ir ** 2).sum())
    wet = fftconvolve(x, ir)
    dry = np.concatenate([x, np.zeros(len(wet) - len(x))])
    return (1 - mix) * dry + mix * wet * 3


def _sweep_noise(d, f0, f1, q=0.6):
    """Band-limited noise whose centre frequency glides from f0 to f1 (block-wise bandpass)."""
    n = int(d * SR); x = rng.standard_normal(n); out = np.zeros(n); blk = 1024
    for i in range(0, n, blk):
        u = i / n
        fc = f0 * (f1 / f0) ** u
        lo, hi = max(40, fc * (1 - q / 2)), min(SR / 2 - 100, fc * (1 + q / 2))
        seg = x[max(0, i - 2048): i + blk]
        y = sosfilt(butter(2, [lo, hi], btype="band", fs=SR, output="sos"), seg)
        out[i: i + blk] = y[-len(out[i: i + blk]):]
    return out


def swell(d=1.4):
    """Reverse-reverb swell: a bright chord's reverb tail played backwards — rises into the next moment, ends on the cut."""
    t = _t(0.25)
    chord = sum(np.sin(2 * np.pi * f * t) for f in (261.6, 329.6, 392.0, 523.3, 784.0)) * np.exp(-t * 9)
    hit = np.concatenate([chord + 0.4 * rng.standard_normal(len(t)) * np.exp(-t * 30), np.zeros(int(2.2 * SR))])
    tail = _reverb(hit, seconds=2.4, mix=0.9, bright=9000)
    rev = tail[::-1]
    rev = rev[-int(d * SR):]
    env = np.linspace(0, 1, len(rev)) ** 2.2
    return _st(_norm(rev * env), 1.0)


def riser(d=2.0):
    """Tension riser: noise sweeping up + a gliding tone, growing to the hit."""
    t = _t(d); u = t / d
    noise = _sweep_noise(d, 300, 7000, 0.5)
    f = 140 * (900 / 140) ** (u ** 1.6)
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.5) / SR)
    x = (0.8 * _norm(noise, 0) + 0.35 * tone) * u ** 2.5
    x[-int(0.02 * SR):] *= np.linspace(1, 0, int(0.02 * SR))
    return _st(_norm(x), 1.0)


def boom(d=2.2):
    """Cinematic sub hit: a falling sine, a click and a dark room tail."""
    t = _t(d)
    f = 34 + 70 * np.exp(-t * 9)
    sub = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    click = _filt(rng.standard_normal(len(t)), "band", [800, 5000]) * np.exp(-t * 60) * 0.5
    body = _filt(rng.standard_normal(len(t)), "low", 400) * np.exp(-t * 5) * 0.6
    x = _reverb(sub + click + body, seconds=1.8, mix=0.25, bright=2500)[: len(t)]
    return _st(_norm(x), 0.6)


def shimmer(d=1.8, seed=3):
    """Magic twinkle: a sparkle of high bell partials, staggered, with a big airy tail."""
    r = np.random.default_rng(seed)
    t = _t(d); x = np.zeros(len(t))
    notes = [1046.5, 1318.5, 1568.0, 2093.0, 2637.0, 3136.0, 4186.0]
    for k in range(14):
        f = notes[r.integers(len(notes))] * (2 if r.random() < 0.25 else 1)
        st = int(r.uniform(0, 0.55) * SR)
        tt = t[: len(t) - st]
        tone = (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * f * 2.76 * tt)) * np.exp(-tt * r.uniform(5, 9))
        x[st:] += tone * r.uniform(0.3, 1.0)
    x = _reverb(x, seconds=2.2, mix=0.55, bright=11000)[: len(t)]
    x *= np.minimum(1, (len(t) - np.arange(len(t))) / (0.3 * SR))
    return _st(_norm(x), 1.0)


def zap(d=0.7):
    """Spell going wrong: a fizzing, falling FM zap with a crunchy edge."""
    t = _t(d)
    f = 1800 * np.exp(-t * 5.5) + 90
    mod = np.sin(2 * np.pi * 37 * t) * 600 * np.exp(-t * 3)
    x = np.sin(2 * np.pi * np.cumsum(f + mod) / SR)
    x = np.sign(x) * np.abs(x) ** 0.5                       # soft crunch
    x += 0.4 * _filt(rng.standard_normal(len(t)), "high", 3000) * np.exp(-t * 12)
    x *= np.exp(-t * 3.2)
    x = _reverb(x, seconds=0.9, mix=0.25)[: len(t)]
    return _st(_norm(x), 0.8)


def whoosh(d=0.6, up=True):
    """Soft air whoosh: band noise sweeping past, swelling and fading (for camera moves / soft cuts)."""
    t = _t(d); u = t / d
    x = _sweep_noise(d, 400 if up else 4000, 4000 if up else 400, 0.8)
    x *= np.sin(np.pi * u) ** 2
    return _st(_norm(x), 1.5)


def fall(d=1.1):
    """Falling-away whistle + air (for "flung to another world")."""
    t = _t(d)
    f = 1400 * (180 / 1400) ** (t / d)
    x = 0.6 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 1.2)
    x += 0.5 * _norm(_sweep_noise(d, 3000, 300, 0.9), 0) * np.sin(np.pi * t / d)
    return _st(_norm(_reverb(x, 1.2, 0.3)[: len(t)]), 1.2)


def paper(d=0.8):
    """Envelope/paper handling: crisp crackly bursts of filtered noise."""
    t = _t(d); x = np.zeros(len(t))
    for _ in range(9):
        st = int(rng.uniform(0, d - 0.12) * SR); ln = int(rng.uniform(0.03, 0.11) * SR)
        b = _filt(rng.standard_normal(ln), "band", [1500, 7000]) * np.hanning(ln) * rng.uniform(0.4, 1)
        x[st: st + ln] += b[: len(x[st: st + ln])]
    x += 0.15 * _filt(rng.standard_normal(len(t)), "band", [2000, 6000]) * np.sin(np.pi * t / d)
    return _st(_norm(x, -4), 0.5)


def drone(d=6.0):
    """Low, slightly uneasy pad (for the witch part): two detuned low tones + dark air, slow fade in/out."""
    t = _t(d)
    x = (np.sin(2 * np.pi * 55 * t) + 0.7 * np.sin(2 * np.pi * 82.4 * t + 0.3 * np.sin(2 * np.pi * 0.2 * t))
         + 0.5 * np.sin(2 * np.pi * 110.6 * t))
    x += 0.4 * _filt(rng.standard_normal(len(t)), "low", 500)
    x *= np.minimum(1, t / 1.2) * np.minimum(1, (d - t) / 1.2)
    return _st(_norm(x, -6), 1.0)


KIT = {"cine_swell": swell, "cine_swell_short": lambda: swell(0.7), "cine_riser": riser, "cine_boom": boom,
       "cine_shimmer": shimmer, "cine_shimmer2": lambda: shimmer(1.4, 11), "cine_zap": zap, "cine_whoosh": whoosh,
       "cine_whoosh_down": lambda: whoosh(0.7, False), "cine_fall": fall, "cine_paper": paper, "cine_drone": drone}


def build_all():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in KIT.items():
        sf.write(OUT / f"{name}.wav", fn().astype(np.float32), SR)
        print("wrote", name)


if __name__ == "__main__":
    build_all()
