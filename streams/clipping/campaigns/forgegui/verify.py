"""Verify finished renders: transcript of what's actually heard + integrated loudness + length.
uv run python streams/clipping/campaigns/forgegui/verify.py clips/fg-004/fg-004_v2.mp4 ..."""
import json, re, subprocess, sys, tempfile
from pathlib import Path
from studio.render.transcribe import transcribe
FG = Path(__file__).resolve().parent
for p in sys.argv[1:]:
    v = FG / p if not Path(p).is_absolute() else Path(p)
    with tempfile.TemporaryDirectory() as td:
        w = json.loads(transcribe(v, Path(td) / "w.json").read_text())
    r = subprocess.run(["ffmpeg", "-nostats", "-i", str(v), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    lufs = re.findall(r"I:\s+(-?[\d.]+) LUFS", r)[-1]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(v)], capture_output=True, text=True).stdout)
    print(f"== {v.name}  {dur:.1f}s  {lufs} LUFS\n   " + " ".join(f'{x["word"]}' for x in w["words"]))
