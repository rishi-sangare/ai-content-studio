"""Reusable ForgeGUI clip builder (fg-004 onward; fg-001–003 are the hand-built originals it was generalised from).

A clip spec = the raw source, the cuts kept (name, src in, src out, speed), an optional final hold (freeze), our voice lines (bigbro
clone) placed on the edit timeline at the moment each prompt is typed, keyboard ticks under the typing, one fitting sound per payoff,
hook/stamp/label titles, the logo pill from a point to the end (≥3 s), music. Times inside a cut are given in SOURCE seconds as
(cut, src_t) and mapped to the edit; plain numbers are edit seconds.
Pipeline: speak_cast (cached per line) → place lines → recipe → `studio clip render` → checks.
"""
import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[4]
FG = Path(__file__).resolve().parent
FOOT = FG / "footage"
LOGO = FOOT / "Forge Logo" / "forgegui_pill.png"
VOICE = ROOT / "streams/clipping/brand/cooked-or-cracked/voice-bigbro/reference.wav"
MUSIC = ROOT / "studio/render/assets/music"
MEMES = ROOT / "studio/render/assets/memes"
CREDIT = 'music: "{}" by Kevin MacLeod (incompetech.com), licensed under Creative Commons: By Attribution 4.0'
TRACKS = {"monkeys_spinning_monkeys": "Monkeys Spinning Monkeys", "fluffing_a_duck": "Fluffing a Duck", "sneaky_snitch": "Sneaky Snitch"}


def build(spec: dict, version: str = "1", note: str = "", render: bool = True):
    cid = spec["id"]; C = FG / "clips" / cid; C.mkdir(parents=True, exist_ok=True)
    src = FOOT / spec["src"]
    # ---- edit timeline -----------------------------------------------------------------------------------------------
    starts, t, segs = {}, 0.0, []
    for name, a, b, sp, *opt in spec["cuts"]:          # speed 0 = a freeze: hold source frame a for b seconds (a beat mid-edit)
        o = opt[0] if opt else {}
        starts[name] = round(t, 3)
        seg = {"src": str(src), "in": a, "out": b, "zoom": o.get("zoom", 1.0), "crop_x": o.get("x", 0.5), "layout": "crop",
               "push": o.get("push", 0.03), "snap": o.get("snap", 0.0), "xfade": o.get("xfade", 0.0)}
        if sp == 0:
            seg.update({"in": 0.0, "out": b, "freeze": a}); segs.append(seg); t += b; continue
        if sp != 1.0: seg["speed"] = sp
        segs.append(seg); t += (b - a) / sp
    cutmap = {c[0]: c for c in spec["cuts"]}
    def ed(x):
        if isinstance(x, (int, float)): return round(float(x), 3)
        n, s = x; c = cutmap[n]
        return round(starts[n] + (s - c[1]) / (c[3] or 1.0), 3)
    if spec.get("hold"):
        frz, dur = spec["hold"]
        segs.append({"src": str(src), "in": 0.0, "out": dur, "zoom": 1.0, "layout": "crop", "push": 0.04, "snap": 0.0, "xfade": 0.0, "freeze": frz})
        t += dur
    TOTAL = round(t, 3)
    # ---- voice ---------------------------------------------------------------------------------------------------------
    from studio.render.cast import speak_cast
    ref = json.load(open(VOICE.with_suffix(".words.json")))["text"]
    script = {"concept": spec.get("concept", cid), "voices": {"bro": {"clone_of": str(VOICE), "ref_text": ref}},
              "lines": [{"id": i, "v": "bro", "text": tx, "gap": 0.3} for i, tx, _ in spec["lines"]]}
    (C / "script.json").write_text(json.dumps(script, indent=1))
    speak_cast(script, C, seeds=(1, 2, 3, 4, 5, 6))
    vo, sr = sf.read(C / "vo.wav"); vo = vo.mean(1) if vo.ndim > 1 else vo
    lines = {l["id"]: l for l in json.loads((C / "vo.lines.json").read_text())}
    words = json.loads((C / "vo.words.json").read_text())["words"]
    out = np.zeros(int((TOTAL + 0.5) * sr)); pl, pw = [], []
    place = sorted(((i, ed(at)) for i, _, at in spec["lines"]), key=lambda x: x[1])
    for k, (i, at) in enumerate(place):
        l = lines[i]; a, b = max(0, l["start"] - 0.08), l["end"] + 0.08
        clip = vo[int(a * sr): int(b * sr)]; j = int(at * sr); out[j:j + len(clip)] += clip[: max(0, len(out) - j)]
        sh = at - a
        pl.append({**l, "start": round(l["start"] + sh, 3), "end": round(l["end"] + sh, 3)})
        pw += [{**w, "start": round(w["start"] + sh, 3), "end": round(w["end"] + sh, 3)} for w in words if a - 0.1 <= w["start"] < b]
        nxt = place[k + 1][1] if k + 1 < len(place) else TOTAL
        if at + (l["end"] - l["start"]) > nxt + 0.1:
            print(f"  VO OVERLAP {i}: {at:.2f}+{l['end'] - l['start']:.2f} > next {nxt:.2f}")
    import re as _re                                    # captions read "Forge GUI", whatever the TTS spelling was ("G-U-I")
    pw = [{**w, "word": _re.sub(r"(?i)\bg[-. ]?u[-. ]?i\b", "GUI", w["word"]).lstrip(".")} for w in pw]
    for w in pw:                                        # transcriber spellings the captions must not show
        core = w["word"].strip(" ,.?!'\"")
        if core.lower() in spec.get("fix_words", {}):
            w["word"] = w["word"].replace(core, spec["fix_words"][core.lower()])
    sf.write(C / "vo_placed.wav", out.astype("float32"), sr)
    (C / "vo_placed.lines.json").write_text(json.dumps(pl))
    (C / "vo_placed.words.json").write_text(json.dumps({"words": pw, "text": " ".join(w["word"] for w in pw)}))
    # ---- sound + titles ------------------------------------------------------------------------------------------------
    fx = lambda at, name, db, mx=None: {"at": round(max(0.0, ed(at)), 3), "sfx": name, "db": db, **({"sfx_max": mx} if mx else {})}
    events = [fx(at, "typing", -16, d) for at, d in spec.get("typing", [])]
    events += [fx(at, n, db, *(mx if mx else [])) for at, n, db, *mx in spec.get("sfx", [])]
    for e in spec.get("fx", []):                        # visual beats: impact frames, shake, flash, meme GIF cut-ins
        e = dict(e); e["at"] = round(max(0.0, ed(e["at"])), 3)
        if e.get("gif") and not str(e["gif"]).startswith("/"): e["gif"] = str(MEMES / f"{e['gif']}.mp4")
        events.append(e)
    lf = ed(spec["logo_from"])                                  # pill_until: stop where the raw's own ForgeGUI end card takes over
    lu = ed(spec["pill_until"]) if spec.get("pill_until") else TOTAL
    events.append({"at": lf, "sticker": str(LOGO), "pos": [0.5, 0.2], "size": 620, "sticker_s": round(lu - lf, 3)})
    titles = [{"text": tx, "start": ed(a), "end": round(ed(b) if b is not None else TOTAL - 0.05, 2), "kind": k, "y": y, **({"size": s} if s else {})}
              for tx, a, b, k, y, s in spec["titles"]]
    track = spec.get("music", "monkeys_spinning_monkeys")
    a, msr = sf.read(MUSIC / f"{track}.mp3"); a = a if a.ndim > 1 else np.stack([a, a], 1)
    n = int(TOTAL * msr); a = np.concatenate([a] * (n // len(a) + 2))[:n]; tt = np.arange(n) / msr
    lvl = spec.get("music_db", -7)
    g = np.interp(tt, [0, 0.2, TOTAL - 0.6, TOTAL], [10 ** ((lvl - 5) / 20), 10 ** (lvl / 20), 10 ** (lvl / 20), 10 ** (-20 / 20)])
    sf.write(C / "music_bed.wav", (a * g[:, None]).astype("float32"), msr)
    recipe = {
        "clip_id": cid, "campaign_id": "forgegui", "mode": "montage",
        "voiceover": str(C / "vo_placed.wav"), "voiceover_words": str(C / "vo_placed.words.json"), "voiceover_lines": str(C / "vo_placed.lines.json"),
        "motion": {"captions": bool(spec.get("captions")), "highlight": (spec.get("captions") or {}).get("highlight", []),
                   "style": {"accent": "#FFD23F", "accent2": "#7CFF6B", **(spec.get("captions") or {}).get("style", {})}, "titles": titles},
        "game_audio_db": spec.get("game_audio_db", -18), "sharpen": 0.4, "crf": 16,
        "music": {"path": str(C / "music_bed.wav"), "db": 0, "start": 0.0, "duck_threshold": 0.08, "duck_ratio": 2, "credit": CREDIT.format(TRACKS[track])},
        "events": events, "segments": segs, "must_say": ["forge gui"], "max_shot_s": 12.0, "min_s": 10, "dead_air_db": -45, "version_note": note,
    }
    (C / f"v{version}.json").write_text(json.dumps(recipe, indent=1, ensure_ascii=False))
    print(f"{cid} v{version}: {TOTAL}s, {len(segs)} segments, cuts {starts}")
    if render:
        r = subprocess.run(["uv", "run", "studio", "clip", "render", str(C / f"v{version}.json"), "-o", str(C / f"{cid}_v{version}.mp4")],
                           cwd=ROOT, capture_output=True, text=True)
        print("\n".join(l for l in (r.stdout + r.stderr).splitlines() if "❌" in l or "rendered" in l or "Error" in l))
    return C / f"{cid}_v{version}.mp4"
