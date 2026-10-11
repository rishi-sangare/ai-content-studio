"""Mark Manson podcast clip builder: one continuous range of an episode → a 9:16 Short with the speaker's face kept centred.

For a pick (episode, start, end, hook): sample the range at 4 fps, find camera cuts (big frame difference) and the largest face
per frame (YuNet, studio/render/reframe.py's model), so each camera shot becomes one segment with a steady crop on the face.
Original audio only (no voiceover, no music), word captions from the episode transcript (rebased to the clip), the hook as
on-screen text over the first seconds. Brief: Mark's face in the first 5 s, subtitles on the whole clip, whole thoughts only.
  uv run python streams/clipping/campaigns/mark-manson/podclip.py <pick rank> <platform> [version]   (reads picks.json)
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

MM = Path(__file__).resolve().parent
ROOT = MM.parents[3]
MODEL = ROOT / "studio" / "render" / "assets" / "models" / "face_detection_yunet_2023mar.onnx"
DW, DH, FPS_S = 640, 360, 4.0


def ts(s: str) -> float:
    m, sec = s.split(":")
    return int(m) * 60 + float(sec)


def episode(prefix: str) -> Path:
    return next((MM / "footage").glob(f"{prefix}*.mp4"))


def shots(src: Path, a: float, b: float):
    """[(t0, t1, face_x | None, face_w)] per camera shot inside [a, b] (times relative to a)."""
    p = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(src), "-vf",
                        f"fps={FPS_S},scale={DW}:{DH}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, check=True)
    fr = np.frombuffer(p.stdout, np.uint8).reshape(-1, DH, DW, 3)
    det = cv2.FaceDetectorYN.create(str(MODEL), "", (DW, DH), score_threshold=0.6)
    faces, cuts, prev = [], [0], None
    for i, f in enumerate(fr):
        _, fs = det.detect(f)
        faces.append(max(((x + w / 2) / DW, w / DW, (y + h / 2) / DH) for x, y, w, h in fs[:, :4]) if fs is not None and len(fs) else None)
        small = cv2.resize(f, (64, 36)).astype(np.int16)
        if prev is not None and np.abs(small - prev).mean() > 18:
            cuts.append(i)
        prev = small
    cuts.append(len(fr))
    out = []
    for c0, c1 in zip(cuts, cuts[1:]):
        xs = [faces[k] for k in range(c0, c1) if faces[k]]
        fx = float(np.median([x for x, _, _ in xs])) if xs else None
        fw = float(np.median([w for _, w, _ in xs])) if xs else 0.0
        fy = float(np.median([y for _, _, y in xs])) if xs else 0.4
        out.append((round(c0 / FPS_S, 3), round(min(c1 / FPS_S, b - a), 3), fx, fw, fy))
    merged = []                                      # fold shots shorter than 0.6 s into the previous one
    for s in out:
        if merged and s[1] - s[0] < 0.6:
            merged[-1] = (merged[-1][0], s[1], *merged[-1][2:])
        else:
            merged.append(s)
    return merged


def build(pick: dict, version: str = "1"):
    cid = f"mm-{pick['platform'][:2]}{pick['rank']:02d}"
    C = MM / "clips" / cid; C.mkdir(parents=True, exist_ok=True)
    src = episode(pick["episode"])
    a, b = ts(pick["start"]), ts(pick["end"])
    words = json.loads(next((MM / "transcripts").glob(f"{pick['episode']}*.words.json")).read_text())["words"]
    b = min(b, max(w["end"] for w in words if w["start"] < b) + 0.12)  # end right after the last spoken word
    a = max(0.0, min(w["start"] for w in words if w["end"] > a) - 0.05)
    import re as _re                                    # captions bleep swears (the audio stays as Mark said it)
    SWEARS = [(r"(?i)\bf(u)(ck)", "f*ck"), (r"(?i)\bbullsh(i)(t)", "bullsh*t"), (r"(?i)\bsh(i)(t)", "sh*t")]
    def soft(t):
        for pat, rep in SWEARS:
            t = _re.sub(pat, lambda m: rep if m.group(0).islower() else rep.capitalize(), t)
        return t
    cw = [{**w, "word": soft(w["word"]), "start": round(w["start"] - a, 3), "end": round(w["end"] - a, 3)}
          for w in words if a <= w["start"] < b]
    (C / "words.json").write_text(json.dumps({"words": cw, "text": " ".join(w["word"] for w in cw)}))
    sh = shots(src, a, b)
    segs, last_x = [], 0.62
    for t0, t1, fx, fw, fy in sh:
        x = fx if fx is not None else last_x
        last_x = x
        # wide shots (small face) zoom in so Mark fills the frame like the medium shot does (face ≈ 11% of source width)
        zoom = round(min(1.6, max(1.0, 0.11 / fw)), 2) if fw else 1.0
        y = round(min(0.7, fy + 0.08), 3) if zoom > 1.05 else 0.5   # keep the face in the upper third when zoomed
        segs.append({"src": str(src), "in": round(a + t0, 3), "out": round(a + t1, 3), "zoom": zoom, "crop_x": round(x, 3), "crop_y": y,
                     "layout": "crop", "push": 0.02, "snap": 0.0, "xfade": 0.0})
    if pick.get("auto_punch", True):
        gaps = [cw[i]["end"] + (cw[i + 1]["start"] - cw[i]["end"]) / 2 for i in range(len(cw) - 1)]
        out = []
        for sg in segs:
            t0, t1 = sg["in"] - a, sg["out"] - a
            pts, k = [t0], 0
            while pts[-1] + 4.6 < t1:
                tgt = pts[-1] + 3.6
                near = min((g for g in gaps if pts[-1] + 2.6 < g < min(t1 - 1.2, pts[-1] + 4.8)), key=lambda g: abs(g - tgt), default=None)
                if near is None:
                    break
                pts.append(near)
            pts.append(t1)
            for j, (u0, u1) in enumerate(zip(pts, pts[1:])):
                part = {**sg, "in": round(a + u0, 3), "out": round(a + u1, 3)}
                if j % 2 == 1:                                   # every other chunk: punch in on the face
                    part.update(zoom=round(sg["zoom"] * 1.14, 2), push=0.02,
                                crop_y=sg.get("crop_y", 0.5) if sg["zoom"] > 1.05 else 0.42)
                out.append(part)
        segs = out
    punches = [tuple(x) for x in pick.get("punches", [])]
    if punches:
        cut = sorted({round(t, 3) for p0, p1 in punches for t in (p0, p1)})
        out = []
        for sg in segs:
            t0, t1 = sg["in"] - a, sg["out"] - a
            pts = [t0] + [c for c in cut if t0 + 0.3 < c < t1 - 0.3] + [t1]
            for u0, u1 in zip(pts, pts[1:]):
                part = {**sg, "in": round(a + u0, 3), "out": round(a + u1, 3)}
                if any(p0 - 0.05 <= u0 and u1 <= p1 + 0.05 for p0, p1 in punches):
                    part.update(zoom=round(sg["zoom"] * 1.15, 2), push=0.05,
                                crop_y=sg.get("crop_y", 0.5) if sg["zoom"] > 1.05 else 0.42)
                out.append(part)
        segs = out
    first_face = sh[0][2] is not None
    recipe = {
        "clip_id": cid, "campaign_id": "mark-manson", "mode": "montage",
        "voiceover_words": str(C / "words.json"),
        "motion": {"captions": True, "highlight": pick.get("highlight", []),
                   "style": {"y": 0.66, "size": 80, "maxWords": 3, "accent": "#FFD23F", "accent2": "#7CFF6B"},
                   "titles": [{"text": pick.get("headline") or pick["hook"], "start": 0.0,
                               "end": round(b - a, 2) if pick.get("headline_all") else 3.5, "kind": "hook", "y": 0.10, "size": 74}]
                             + [{"text": t, "start": s0, "end": s1, "kind": k, "y": 0.57 if k == "stamp" else 0.58}
                                for t, s0, s1, k in pick.get("stamps", [])]
                             + ([{"text": pick["end_label"], "start": round(b - a - 2.6, 2), "end": round(b - a - 0.05, 2),
                                  "kind": "label", "y": 0.58}] if pick.get("end_label") else [])},
        "game_audio_db": 0, "sharpen": 0.5, "crf": 16,
        "events": [{"at": t, "sfx": n, "db": db} for t, n, db in pick.get("sfx", [])], "segments": segs, "must_say": [], "max_shot_s": 60.0, "min_s": 12, "dead_air_db": -45, "dead_air_s": 0.9, "no_logo": True,
        "version_note": f"{pick['episode']} {pick['start']}–{pick['end']} · {pick['type']} · {pick['hook']}",
    }
    (C / f"v{version}.json").write_text(json.dumps(recipe, indent=1, ensure_ascii=False))
    print(f"{cid} v{version}: {b - a:.1f}s, {len(segs)} shots, face in first shot: {first_face} · {pick['hook']}")
    r = subprocess.run(["uv", "run", "studio", "clip", "render", str(C / f"v{version}.json"), "-o", str(C / f"{cid}_v{version}.mp4")],
                       cwd=ROOT, capture_output=True, text=True)
    print("\n".join(l for l in (r.stdout + r.stderr).splitlines() if "❌" in l or "rendered" in l or "Error" in l))
    return C / f"{cid}_v{version}.mp4"


if __name__ == "__main__":
    picks = json.loads((MM / "picks.json").read_text())["picks"]
    rank, plat = int(sys.argv[1]), sys.argv[2]
    pick = next(p for p in picks if p["rank"] == rank and p["platform"] == plat)
    build(pick, sys.argv[3] if len(sys.argv) > 3 else "1")
