"""Frame-by-frame continuity audit: finds the edits that feel "broken" — the things still frames can't show.

Reads every frame of a render (30 fps, small greyscale) and reports, with timestamps:
  - STUTTER: a moving shot that suddenly holds the same frame for 3+ frames (decoder ran out, a freeze where none was planned)
  - JUMP:    a sudden big picture change that is NOT one of the planned cuts (in-game camera snap, UI popping, a menu)
  - BLACK:   near-black frames that aren't part of the footage's look
  - JOLT:    a planned dissolve that arrives as a hard change (the transition is missing)
  - SHAKY:   a shot whose camera motion is jerky (frame-to-frame motion swings wildly)
Usage: uv run python -m studio.render.flow <video.mp4> <recipe.json>
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

W, H, FPS = 135, 240, 30


def frames(video):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={FPS},scale={W}:{H},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)


def audit(video, recipe):
    f = frames(video)
    n = len(f)
    diff = np.r_[0, np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))]          # picture change into each frame
    lum = f.mean(axis=(1, 2))
    # planned cuts and what kind they are
    segs, t, cuts = recipe["segments"], 0.0, []
    for i, sg in enumerate(segs):
        d = sg["out"] - sg["in"] if sg.get("freeze") is None else sg["out"]
        d = d / float(sg.get("speed", 1.0)) if sg.get("freeze") is None else d
        if i:
            cuts.append((t, float(sg.get("xfade", 0) or 0), i))
        t += d
    seg_at = lambda tt: next((i for i in range(len(cuts)) if cuts[i][0] > tt), len(cuts))
    planned = {int(round(c * FPS)) + k for c, xf, _ in cuts for k in range(-1, int(xf * FPS) + 3)}
    planned |= {int(round(c * FPS)) + k for c, xf, i in cuts if (segs[i].get("snap") or 0) > 0 for k in range(0, 10)}  # impact zooms
    flashes = {int(round(e["t"] * FPS)) + k for e in _events(recipe) if e.get("flash") or e.get("shake") for k in range(0, 9)}
    freezes = set()
    t = 0.0
    for sg in segs:
        d = sg["out"] if sg.get("freeze") is not None else (sg["out"] - sg["in"]) / float(sg.get("speed", 1.0))
        if sg.get("freeze") is not None:
            freezes |= set(range(int(t * FPS), int((t + d) * FPS) + 1))
        t += d
    med = np.median(diff[diff > 0]) if (diff > 0).any() else 1.0
    out = []
    # JUMP: spikes well above the local motion level, not at a planned cut or a flash/shake
    for k in range(2, n - 2):
        local = np.median(diff[max(1, k - 15): k + 15])
        if diff[k] > max(18, 5 * local) and k not in planned and k not in flashes:
            out.append(("JUMP", k / FPS, f"picture jumps (Δ{diff[k]:.0f} vs ~{local:.0f}) inside a shot"))
    # STUTTER: 3+ identical frames inside a moving shot
    run = 0
    for k in range(1, n):
        if diff[k] < 0.15 and k not in freezes:
            run += 1
        else:
            if run >= 3:
                moving_before = np.median(diff[max(1, k - run - 20): k - run]) > 1.0
                if moving_before:
                    out.append(("STUTTER", (k - run) / FPS, f"{run} frozen frames in a moving shot"))
            run = 0
    # BLACK
    for k in range(n):
        if lum[k] < 8 and (k == 0 or lum[k - 1] >= 8):
            out.append(("BLACK", k / FPS, "near-black frame"))
    # JOLT: a dissolve that lands as a hard change
    for c, xf, i in cuts:
        k = int(round(c * FPS))
        if xf > 0 and k + 1 < n:
            peak = diff[k: k + int(xf * FPS) + 2].max()
            if peak > max(25, 6 * med):
                out.append(("JOLT", c, f"dissolve into shot {i} arrives as a hard change (Δ{peak:.0f})"))
    # SHAKY: a shot whose motion swings wildly (jerky source camera)
    bounds = [0.0] + [c for c, _, _ in cuts] + [n / FPS]
    for i in range(len(bounds) - 1):
        a, b = int(bounds[i] * FPS) + 4, int(bounds[i + 1] * FPS) - 2
        if b - a > 8:
            seg = diff[a:b]
            if seg.std() > 6 and seg.max() > 20:
                out.append(("SHAKY", bounds[i], f"shot {i}: jerky camera (motion swings {seg.min():.0f}–{seg.max():.0f})"))
    return sorted(out, key=lambda x: x[1]), cuts


def _events(recipe):
    ev = []
    for e in recipe.get("events", []):
        if "at" in e:
            ev.append({**e, "t": e["at"]})
    return ev


if __name__ == "__main__":
    video, rp = Path(sys.argv[1]), Path(sys.argv[2])
    issues, cuts = audit(video, json.loads(rp.read_text()))
    print(f"{len(cuts)} planned cuts; {len(issues)} issues")
    for kind, t, msg in issues:
        print(f"  {kind:7s} {t:6.2f}s  {msg}")


def window_issues(src, a, b, fps=15):
    """Check a source window BEFORE using it: in-game camera snaps / cuts, freezes, black frames, jerky motion.
    Returns [(kind, clip_time, detail)]."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(0, a):.3f}", "-t", f"{b - a:.3f}", "-i", str(src),
                          "-vf", f"fps={fps},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    if not raw:
        return [("MISSING", a, "no frames (window past the end of the clip?)")]
    f = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
    d = np.r_[0, np.abs(np.diff(f, axis=0)).mean(axis=(1, 2))]
    lum = f.mean(axis=(1, 2))
    out = []
    for k in range(1, len(f)):
        local = np.median(d[max(1, k - 8): k + 8])
        if d[k] > max(16, 4.5 * local):
            out.append(("SNAP", a + k / fps, f"camera cut/snap (Δ{d[k]:.0f} vs ~{local:.0f})"))
    if (lum < 8).any():
        out.append(("BLACK", a + float(np.argmax(lum < 8)) / fps, "black frame in window"))
    run = 0
    for k in range(1, len(f)):
        run = run + 1 if d[k] < 0.1 else 0
        if run == 4:
            out.append(("FROZEN", a + (k - 3) / fps, "footage holds still (paused/loading?)"))
    if len(d) > 6 and d[2:].std() > 7 and d[2:].max() > 22:
        out.append(("JERKY", a, f"jerky camera (motion {d[2:].min():.0f}–{d[2:].max():.0f})"))
    return out


def check_windows(recipe):
    """Every non-freeze segment's source window, including the dissolve run-on into the next shot."""
    segs, rep = recipe["segments"], []
    for i, sg in enumerate(segs):
        if sg.get("freeze") is not None:
            continue
        ext = float(segs[i + 1].get("xfade", 0) or 0) if i + 1 < len(segs) else 0.0
        b = sg["out"] + ext * float(sg.get("speed", 1.0))
        for kind, t, msg in window_issues(sg["src"], sg["in"], b):
            rep.append((i, Path(sg["src"]).name, sg["in"], round(b, 2), kind, round(t, 2), msg))
    return rep
