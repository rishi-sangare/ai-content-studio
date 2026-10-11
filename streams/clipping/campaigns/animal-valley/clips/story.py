"""Voice-led Animal Valley story builder (av-006 onward; generalised from av-004's build.py).

A spec = Day One Drops voice lines → speak_cast; one shot per cue (a line id, or (word, line id) for a mid-line cut), each cut snapped
to the music's beat grid (brief: beat sync required); stamps/labels on cues; one fitting sound per beat; logo sticker from the line that
says "Animal Valley" to the end; word captions with highlights. Run: uv run python streams/clipping/campaigns/animal-valley/clips/story.py <spec.py> [version]
"""
import importlib.util, json, subprocess, sys
from pathlib import Path
import librosa, numpy as np, soundfile as sf

CL = Path(__file__).resolve().parent; AV = CL.parent; ROOT = AV.parents[3]
G = AV / "footage" / "Gameplay + Meta Gameplay"
SRC = {f.name.split("_")[0].split("-")[1]: f for f in sorted(G.glob("AVAPPQ-*.mp4"))}    # "171" → AVAPPQ-171_v1_59s_…mp4
LOGO = AV / "footage" / "Logo" / "logo.png"
VOICE = ROOT / "streams/clipping/brand/day-one-drops/voice-guy"
MUSIC = ROOT / "studio/render/assets/music"
TRACKS = {"monkeys_spinning_monkeys": "Monkeys Spinning Monkeys", "fluffing_a_duck": "Fluffing a Duck", "sneaky_snitch": "Sneaky Snitch"}


def build(spec, version="1"):
    cid = spec["id"]; C = CL / cid; C.mkdir(exist_ok=True)
    from studio.render.cast import speak_cast
    V = VOICE.parent / spec.get("voice", "voice-guy")              # voice-guy (Day One Drops) or voice-doc (documentary)
    ref = json.loads((V / "reference.json").read_text())["text"]
    script = {"concept": spec["concept"], "voices": {"guy": {"clone_of": str(V / "reference.wav"), "ref_text": ref}},
              "lines": [{"id": i, "v": "guy", "text": tx, "gap": gap} for i, tx, gap in spec["lines"]]}
    (C / "script.json").write_text(json.dumps(script, indent=1))
    speak_cast(script, C, seeds=(1, 2, 3, 4))
    words = json.loads((C / "vo.words.json").read_text())["words"]
    for w in words:                                    # transcriber homophones the captions must not show ("than" for "then")
        core = w["word"].strip(" ,.?!'\"")
        if core.lower() in spec.get("fix_words", {}):
            w["word"] = w["word"].replace(core, spec["fix_words"][core.lower()])
    (C / "vo.words.json").write_text(json.dumps({"words": words, "text": " ".join(w["word"] for w in words)}))
    lines = {l["id"]: l for l in json.loads((C / "vo.lines.json").read_text())}
    def cue(c, after=False):
        if isinstance(c, (int, float)): return float(c)
        if isinstance(c, str): return lines[c]["start"]
        w, ln = c
        hit = next(x for x in words if x["word"].lower().strip(" ,.?!'\"") == w and lines[ln]["start"] - 0.3 <= x["start"] <= lines[ln]["end"] + 0.1)
        return hit["end"] if after else hit["start"]
    last = spec["lines"][-1][0]
    TOTAL = round(lines[last]["end"] + spec.get("tail", 0.6), 3)
    track = spec["music"]
    y, sr = librosa.load(str(MUSIC / f"{track}.mp3"), sr=22050, duration=90)
    beats = librosa.frames_to_time(librosa.beat.beat_track(y=y, sr=sr)[1], sr=sr)
    first = cue(spec["shots"][1][0])
    mstart = round(float(min((b for b in beats if b >= first), key=lambda b: b - first)) - first, 3)
    grid = [b - mstart for b in beats if b - mstart >= 0]
    beat = lambda t, tol=0.22: round(min(grid, key=lambda g: abs(g - t)), 3) if min(abs(g - t) for g in grid) <= tol else round(t, 3)
    shots = []
    for k, (c, src, a, kw) in enumerate(spec["shots"]):
        t = 0.0 if k == 0 else beat(cue(c))
        sg = {"src": str(SRC[src]), "in": a, "zoom": kw.get("z", 1.0), "crop_x": kw.get("x", 0.5), "crop_y": kw.get("y", 0.5),
              "layout": "crop", "push": kw.get("push", 0.05), "snap": kw.get("snap", 0.0), "xfade": kw.get("xf", 0.0)}
        if kw.get("freeze") is not None: sg["freeze"] = kw["freeze"]
        shots.append((t, sg))
    segs = []
    for i, (t, sg) in enumerate(shots):
        nxt = shots[i + 1][0] if i + 1 < len(shots) else TOTAL
        sg = dict(sg)
        if sg.get("freeze") is not None: sg["in"], sg["out"] = 0.0, round(nxt - t, 3)
        else: sg["out"] = round(sg["in"] + (nxt - t), 3)
        segs.append(sg)
    starts = [t for t, _ in shots] + [TOTAL]
    fx = lambda t, name, db, mx=None: {"at": round(max(0.0, t), 3), "sfx": name, "db": db, **({"sfx_max": mx} if mx else {})}
    events = [fx(cue(c, after) + off, n, db, mx) for c, n, db, mx, off, after in
              [(s[0], s[1], s[2], s[3] if len(s) > 3 else None, s[4] if len(s) > 4 else 0.0, s[5] if len(s) > 5 else False) for s in spec["sfx"]]]
    lf = cue(spec["logo_on"])
    events.append({"at": round(lf, 3), "sticker": str(LOGO), "pos": [0.5, 0.2], "size": 700, "sticker_s": round(TOTAL - lf, 3)})
    titles = [{"text": spec["hook"], "start": 0.0, "end": round(starts[1] - 0.05, 2), "kind": "hook", "y": 0.08, "size": 96}]
    for tx, c, shot_i, kind in spec.get("stamps", []):          # a stamp lasts until the next shot after it
        a = cue(c) if c is not None else starts[shot_i]
        b = next(s for s in starts if s > a + 0.05) - 0.05
        titles.append({"text": tx, "start": round(a, 2), "end": round(b, 2), "kind": kind, "y": 0.36 if kind == "stamp" else 0.58})
    a, msr = sf.read(MUSIC / f"{track}.mp3"); a = a if a.ndim > 1 else np.stack([a, a], 1)
    a = a[int(mstart * msr):]; n = int(TOTAL * msr); a = np.concatenate([a, a, a])[:n]; tt = np.arange(n) / msr
    lv = spec.get("music_db", -7.5)
    g = np.interp(tt, [0, 0.3, TOTAL - 0.5, TOTAL], [10 ** ((lv - 4.5) / 20), 10 ** (lv / 20), 10 ** (lv / 20), 10 ** (-20 / 20)])
    sf.write(C / "music_bed.wav", (a * g[:, None]).astype("float32"), msr)
    recipe = {
        "clip_id": cid, "campaign_id": "animal-valley", "mode": "montage",
        "voiceover": str(C / "vo.wav"), "voiceover_words": str(C / "vo.words.json"), "voiceover_lines": str(C / "vo.lines.json"),
        "motion": {"captions": True, "highlight": spec["highlight"],
                   "style": {"y": 0.72, "size": 92, "maxWords": 3, "accent": "#FFD23F", "accent2": "#7CFF6B"}, "titles": titles},
        "game_audio_db": -30, "sharpen": 0.7, "crf": 16,
        "music": {"path": str(C / "music_bed.wav"), "db": 0, "start": 0.0, "duck_threshold": 0.08, "duck_ratio": 2,
                  "credit": f'Music: "{TRACKS[track]}" by Kevin MacLeod (incompetech.com), licensed under Creative Commons: By Attribution 4.0'},
        "events": events, "segments": segs, "must_say": ["animal valley"], "max_shot_s": 6.0, "min_s": 10, "dead_air_db": -45,
        "version_note": spec["concept"],
    }
    from studio.render.flow import check_windows
    for r in check_windows(recipe):
        if r[4] != "JERKY":
            print("  WINDOW PROBLEM shot %d %s %.2f–%.2f: %s at %.2f (%s)" % r)
    (C / f"v{version}.json").write_text(json.dumps(recipe, indent=1, ensure_ascii=False))
    print(f"{cid} v{version}: {TOTAL}s, {len(segs)} shots; cuts {[s for s in starts[:-1]]}")
    r = subprocess.run(["uv", "run", "studio", "clip", "render", str(C / f"v{version}.json"), "-o", str(C / f"{cid}_v{version}.mp4")],
                       cwd=ROOT, capture_output=True, text=True)
    print("\n".join(l for l in (r.stdout + r.stderr).splitlines() if "❌" in l or "rendered" in l or "Error" in l))


if __name__ == "__main__":
    p = Path(sys.argv[1]).resolve()
    s = importlib.util.spec_from_file_location(p.stem, p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    build(m.SPEC, sys.argv[2] if len(sys.argv) > 2 else "1")
