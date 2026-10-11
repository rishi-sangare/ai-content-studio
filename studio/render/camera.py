"""Virtual camera over a wide clip, for footage-only brand campaigns.

A recipe gives keyframes (time, x, y, zoom) and the renderer moves a 9:16 window over the source frame by frame:
eased moves, real motion blur on fast moves (several sub-frame crops averaged, like a 180° shutter), an optional
camera shake and flash on a beat. The clip's ORIGINAL audio plays once, in sync — nothing is repeated or added.

Recipe (mode "camera"):
  {"source": "clip.mp4", "keys": [{"t": 0, "x": 0.36, "y": 0.40, "z": 1.6}, ...],
   "shake": [{"t": 1.95, "dur": 0.3, "amp": 10}], "flash": [{"t": 1.95, "dur": 0.15, "strength": 0.35}],
   "hook": {"text": "...", "max_lines": 3, "size": 64, "top_pct": 0.04}}
x, y = centre of the window as a fraction of the source; z = zoom (1 = full source height).
"""
import math
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from studio.render import text

W, H, FPS = 1080, 1920, 30


def _probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "csv=p=0:s=,", str(path)],
                         capture_output=True, text=True, check=True).stdout.split()
    w, h = map(int, out[0].split(",")[:2])
    return w, h, float(out[-1].strip(","))


def _ease(u):                                   # smooth start and stop
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def _cam(keys, t):
    """Camera (x, y, z) at time t, eased between keyframes; zoom moves in log space so it feels even."""
    if t <= keys[0]["t"]:
        k = keys[0]
        return k["x"], k.get("y", 0.5), k.get("z", 1.0)
    for a, b in zip(keys, keys[1:]):
        if a["t"] <= t <= b["t"]:
            u = _ease((t - a["t"]) / max(1e-6, b["t"] - a["t"]))
            lerp = lambda p, q: p + (q - p) * u
            za, zb = a.get("z", 1.0), b.get("z", 1.0)
            return lerp(a["x"], b["x"]), lerp(a.get("y", 0.5), b.get("y", 0.5)), math.exp(lerp(math.log(za), math.log(zb)))
    k = keys[-1]
    return k["x"], k.get("y", 0.5), k.get("z", 1.0)


def _window(sw, sh, x, y, z):
    h = sh / z
    w = h * 9 / 16
    if w > sw:
        w, h = sw, sw * 16 / 9
    left = min(max(x * sw - w / 2, 0), sw - w)
    top = min(max(y * sh - h / 2, 0), sh - h)
    return left, top, w, h


def _shake(shakes, t):
    dx = dy = 0.0
    for s in shakes or []:
        u = (t - s["t"]) / s.get("dur", 0.3)
        if 0 <= u <= 1:
            a = s.get("amp", 8) * (1 - u) ** 2                     # hard hit, quick settle
            dx += a * math.sin(t * 91.0)
            dy += a * math.cos(t * 73.0)
    return dx, dy


def _ring_out(src: Path, dur: float, tail: float, tmp: Path, sr: int = 48000) -> Path:
    """Source audio + a reverb tail made from its own last second (convolved with a smooth, decaying room response)."""
    import soundfile as sf
    wav = tmp / "src.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-vn", "-ac", "2", "-ar", str(sr), str(wav)], check=True)
    a, _ = sf.read(wav, dtype="float32")
    n_total = int(round((dur + tail) * sr))
    out = np.zeros((n_total, 2), dtype=np.float32)
    n = min(len(a), n_total)
    hand = int(0.45 * sr)                                   # crossfade length at the handover
    main = a[:n].copy()
    main[-hand:] *= np.linspace(1, 0, hand)[:, None] ** 1.5
    out[:n] += main
    # room response: decaying noise, a little brighter at first (like a hall), one per channel for width
    rng = np.random.default_rng(3)
    ir_len = int((tail + 0.6) * sr)
    t = np.arange(ir_len) / sr
    env = np.exp(-t / (tail / 4.2))
    ir = rng.standard_normal((ir_len, 2)).astype(np.float32) * env[:, None]
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    L = min(n, int(1.0 * sr))
    seg = a[n - L:n] * np.hanning(L * 2)[:L, None]          # rising window: the most recent sound feeds the room most
    nfft = 1 << int(np.ceil(np.log2(L + ir_len - 1)))
    wet = np.stack([np.fft.irfft(np.fft.rfft(seg[:, c], nfft) * np.fft.rfft(ir[:, c], nfft), nfft)[: L + ir_len - 1]
                    for c in range(2)], axis=1).astype(np.float32)
    start = n - len(seg)
    wet = wet[: n_total - start]
    # match the tail's level to the source's last half second, then fade it to exactly zero at the end
    ref = np.sqrt(np.mean(a[n - hand:n] ** 2)) + 1e-9
    look = wet[len(seg) - hand: len(seg)]
    wet *= 0.85 * ref / (np.sqrt(np.mean(look ** 2)) + 1e-9)
    fade = np.ones(len(wet), dtype=np.float32)
    fade[: len(seg) - hand] = 0.0                            # the tail only takes over from the handover onwards
    ramp = np.linspace(0, 1, hand)
    fade[len(seg) - hand: len(seg)] = ramp
    rest = len(wet) - len(seg)
    if rest > 0:
        fade[len(seg):] = np.linspace(1, 0, rest) ** 1.6
    out[start:start + len(wet)] += wet * fade[:, None]
    res = tmp / "ringout.wav"
    sf.write(res, np.clip(out, -1, 1), sr)
    return res


def render(recipe: dict, out_path: Path) -> Path:
    src = Path(recipe["source"])
    sw, sh, dur = _probe(src)
    keys = sorted(recipe["keys"], key=lambda k: k["t"])
    frame_bytes = sw * sh * 3
    src_frames = int(round(dur * FPS))
    tail = float(recipe.get("tail", 0.0))              # extra seconds: camera keeps moving over the last frame
    n_frames = src_frames + int(round(tail * FPS))
    total = dur + tail
    tmp = Path(tempfile.mkdtemp(prefix="studio_cam_"))
    hook = recipe.get("hook") or {}
    hook_png = None
    if hook.get("text"):
        hook_png = tmp / "hook.png"
        text.hook_banner(hook["text"], hook_png, hook.get("max_lines", 2), hook.get("size", 76), hook.get("top_pct", 0.14))

    dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", str(src), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc_in = ["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", "AUDIO_IN"]
    audio_in = str(src)
    if tail > 0:
        # the source audio ends at full volume: let its own last moment ring out as a smooth reverb tail under the
        # extra seconds (nothing repeated, nothing new added), level-matched at the handover, silent at the last frame
        audio_in = str(_ring_out(src, dur, tail, tmp))
    fc = "[1:a]aresample=48000,aformat=channel_layouts=stereo,loudnorm=I=-14:TP=-1.5:LRA=11[a]"
    vmap = "0:v"
    if hook_png:
        enc_in += ["-loop", "1", "-i", str(hook_png)]
        fc = f"[0:v][2:v]overlay=0:0:shortest=1,format=yuv420p[v];" + fc
        vmap = "[v]"
    enc_in[enc_in.index("AUDIO_IN")] = audio_in
    out_path.parent.mkdir(parents=True, exist_ok=True)
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", *enc_in, "-filter_complex", fc,
                            "-map", vmap, "-map", "[a]", "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium",
                            "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                            "-ar", "48000", "-movflags", "+faststart", str(out_path)], stdin=subprocess.PIPE)
    shutter = 0.5 / FPS                                            # 180° shutter
    try:
        img = None
        for i in range(n_frames):
            if i < src_frames:
                raw = dec.stdout.read(frame_bytes)
                if len(raw) == frame_bytes:
                    img = Image.frombuffer("RGB", (sw, sh), raw, "raw", "RGB", 0, 1).copy()
            if img is None:
                break                                    # (after the source ends, the last frame is held)
            t = i / FPS
            # how far the window moves during the shutter decides how many sub-frames to blend (motion blur)
            a = _window(sw, sh, *_cam(keys, t - shutter / 2))
            b = _window(sw, sh, *_cam(keys, t + shutter / 2))
            travel = abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])
            samples = 1 if travel < 1.5 else min(9, 2 + int(travel / 2))
            acc = None
            for s in range(samples):
                ts = t if samples == 1 else t - shutter / 2 + shutter * s / (samples - 1)
                left, top, w, h = _window(sw, sh, *_cam(keys, ts))
                dx, dy = _shake(recipe.get("shake"), ts)
                left = min(max(left + dx, 0), sw - w)
                top = min(max(top + dy, 0), sh - h)
                crop = img.resize((W, H), Image.LANCZOS if samples == 1 else Image.BILINEAR,
                                  box=(left, top, left + w, top + h))
                arr = np.asarray(crop, dtype=np.float32)
                acc = arr if acc is None else acc + arr
            frame = acc / samples
            for f in recipe.get("flash") or []:                     # a short bright hit on the beat
                u = (t - f["t"]) / f.get("dur", 0.15)
                if 0 <= u <= 1:
                    frame = frame + (255 - frame) * f.get("strength", 0.3) * (1 - u)
            enc.stdin.write(np.clip(frame, 0, 255).astype(np.uint8).tobytes())
    finally:
        enc.stdin.close()
        enc.wait()
        dec.stdout.close()
        dec.wait()
    if enc.returncode != 0:
        raise RuntimeError("encoding failed")
    return out_path
