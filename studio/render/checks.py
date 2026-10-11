"""Automated quality checks on a rendered Short. Pass/fail with a reason for each.

Thresholds come from the research (Unreal Ishan / Hynex / Not Harshu videos, field guide).
"""
import json
import re
import subprocess
from pathlib import Path


def _ff(args):
    return subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *args, "-f", "null", "-"],
                          capture_output=True, text=True).stderr


def run(video: Path, recipe: dict | None = None, min_s=15.0, max_s=60.0) -> list[dict]:
    res = []
    if recipe:                                   # a campaign can set its own length rules (e.g. "at least 5 s")
        min_s, max_s = recipe.get("min_s", min_s), recipe.get("max_s", max_s)
    info = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height,r_frame_rate:format=duration",
         "-of", "json", str(video)], capture_output=True, text=True).stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    dur = float(info["format"]["duration"])
    fps = eval(v["r_frame_rate"])  # e.g. "30/1"

    res.append(dict(check="Format 1080x1920", ok=(v["width"], v["height"]) == (1080, 1920),
                    detail=f"{v['width']}x{v['height']} @ {fps:.0f}fps"))
    res.append(dict(check=f"Length {min_s:.0f}-{max_s:.0f}s", ok=min_s <= dur <= max_s, detail=f"{dur:.1f}s"))

    # dead air: any silence longer than 0.35s (speech clips lose viewers here)
    floor = (recipe or {}).get("dead_air_db", -38)          # music-led stories sit lower: e.g. -45 (truly silent only)
    gap_s = float((recipe or {}).get("dead_air_s", 0.35))  # podcast clips keep the speaker's natural pauses (e.g. 0.9)
    sil = _ff(["-i", str(video), "-af", f"silencedetect=noise={floor}dB:d={gap_s}"])
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", sil)]
    durs = [float(x) for x in re.findall(r"silence_duration: ([\d.]+)", sil)]
    # a deliberate hold on the end card (last ~1.2 s) isn't dead air; nor is a designed comic/dramatic beat
    beats = (recipe or {}).get("beats", [])                 # [[start, end], …] pauses the edit wants
    gaps = [d for s, d in zip(starts, durs) if s < dur - 1.2
            and not any(b0 - 0.2 <= s and s + d <= b1 + 0.2 for b0, b1 in beats)]
    res.append(dict(check=f"No dead air > {gap_s:g}s", ok=not gaps,
                    detail=f"{len(gaps)} gap(s), longest {max(gaps):.2f}s" if gaps else "none"))

    # background music must be audible: 9–15 dB under the voice (Rishi, 4 Oct: music at -19/-28 dB was inaudible on a phone)
    mus = ((recipe or {}).get("music") or {}).get("path")
    if mus and (recipe or {}).get("voiceover") and Path(mus).exists():
        import numpy as np, soundfile as sf
        m, _ = sf.read(mus); m = m.mean(1) if m.ndim > 1 else m
        vv, _ = sf.read(recipe["voiceover"]); vv = vv.mean(1) if vv.ndim > 1 else vv
        rms = lambda x: 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9)
        gap = rms(vv[vv ** 2 > 1e-5]) - rms(m[m ** 2 > 1e-7]) - float(recipe["music"].get("db", 0))
        gap = float(gap); res.append(dict(check="Music audible (9–15 dB under the voice)", ok=bool(9 <= gap <= 15), detail=f"{gap:.1f} dB under"))

    # loudness ~ -14 LUFS, true peak <= -1 dBTP
    lo = _ff(["-i", str(video), "-af", "ebur128=peak=true"])
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", lo)
    tp = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", lo)
    I = float(I[-1]) if I else None
    tp = float(tp[-1]) if tp else None
    res.append(dict(check="Loudness -14 LUFS (±1.5)", ok=I is not None and abs(I + 14) <= 1.5,
                    detail=f"{I} LUFS, true peak {tp} dBFS"))

    if recipe:
        hook = recipe.get("hook") or {}
        if not hook.get("text"):                 # motion layer (Remotion) titles count as the hook too
            mh = [t for t in (recipe.get("motion") or {}).get("titles", []) if t.get("kind", "hook") == "hook"]
            hook = {"text": mh[0]["text"], "start": mh[0]["start"]} if mh else hook
        res.append(dict(check="Hook text on screen from 0s", ok=bool(hook.get("text")) and hook.get("start", 1) <= 0.1,
                        detail=hook.get("text") or "no hook"))
        if recipe.get("allowed_text"):           # brand campaigns: on-screen text must be an approved line, word for word
            ok = hook.get("text") in recipe["allowed_text"]
            res.append(dict(check="On-screen text is an approved line (word for word)", ok=ok,
                            detail=hook.get("text") if ok else f"NOT approved: {hook.get('text')}"))
        first_in = recipe["segments"][0]["in"]
        if recipe.get("mode") == "montage" and recipe.get("voiceover_words"):
            words = json.loads(Path(recipe["voiceover_words"]).read_text())["words"]
            res.append(dict(check="Speech starts within 0.5s", ok=words[0]["start"] <= 0.5,
                            detail=f"first word at +{words[0]['start']:.2f}s"))
            names = " ".join(w["word"].lower().strip(".,!?") for w in words)
            squash = lambda x: re.sub(r"[^a-z0-9]", "", x.lower())  # "Forge G-U-I" / "Forge G. U. I." both count as "forge gui"
            for must in recipe.get("must_say", []):
                heard = must.lower() in names or squash(must) in squash(names)
                res.append(dict(check=f"Says '{must}'", ok=heard, detail="heard" if heard else "NOT heard"))
            logo = [e for e in recipe.get("events", []) if str(e.get("sticker", "")).endswith(".png")]
            if not recipe.get("no_logo"):                   # podcast clips: the speaker is the brand, no logo needed
              res.append(dict(check="End card / game logo shown", ok=bool((recipe.get("endcard") or {}).get("image")) or bool(logo),
                            detail=(recipe.get("endcard") or {}).get("text") or ("logo at %.1fs" % logo[-1]["at"] if logo else "none")))
        elif recipe.get("transcript"):
            words = json.loads(Path(recipe["transcript"]).read_text())["words"]
            first = next((w for w in words if w["end"] > first_in), None)
            lag = (first["start"] - first_in) if first else None
            res.append(dict(check="Speech starts within 0.5s", ok=lag is not None and lag <= 0.5,
                            detail=f"first word at +{lag:.2f}s" if lag is not None else "no speech"))
            # word timings stretch over pauses, so judge the ending by the audio itself:
            # a clean ending is quiet in its last ~120 ms
            tail = _ff(["-sseof", "-0.12", "-i", str(video), "-af", "astats=metadata=0:reset=0"])
            rms = re.findall(r"RMS level dB: (-?[\d.]+|-inf)", tail)
            level = float(rms[-1]) if rms and rms[-1] != "-inf" else -120.0
            res.append(dict(check="Ends on a finished word (quiet last 120ms)", ok=level < -32,
                            detail=f"tail level {level:.0f} dB"))
        segs = recipe["segments"]
        longest = max(s["out"] - s["in"] for s in segs)
        cap = recipe.get("max_shot_s", 4.0)                  # a single-shot brand clip may set its own limit
        res.append(dict(check=f"Visual change at least every {cap:g}s", ok=longest <= cap or len(segs) >= dur / cap,
                        detail=f"{len(segs)} segment(s), longest {longest:.1f}s"))
    return res


def format_results(res) -> str:
    return "\n".join(f"  {'✅' if r['ok'] else '❌'} {r['check']}: {r['detail']}" for r in res)
