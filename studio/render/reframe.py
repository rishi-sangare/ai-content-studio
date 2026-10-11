"""Find where the subject is, so the 9:16 crop keeps them centred.

Samples frames at ~4 fps, detects faces with OpenCV's YuNet (CPU, on-device), and returns the
horizontal centre (0-1 of source width) over time, smoothed so the crop doesn't jitter.
With several faces it follows the largest (usually the active speaker in a podcast frame).
"""
import json
from pathlib import Path

import cv2
import numpy as np

MODEL = Path(__file__).resolve().parent / "assets" / "models" / "face_detection_yunet_2023mar.onnx"
DETECT_W = 640          # detect on a downscaled frame: fast, plenty for face boxes


def track(video: Path, out: Path | None = None, sample_fps: float = 4.0) -> Path:
    cap = cv2.VideoCapture(str(video))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    scale = DETECT_W / width
    dw, dh = DETECT_W, int(height * scale)
    det = cv2.FaceDetectorYN.create(str(MODEL), "", (dw, dh), score_threshold=0.6)
    step = max(1, int(round(fps / sample_fps)))
    samples, i = [], 0
    while True:
        if not cap.grab():
            break
        if i % step == 0:
            ok, frame = cap.retrieve()
            if ok:
                small = cv2.resize(frame, (dw, dh))
                _, faces = det.detect(small)
                if faces is not None and len(faces):
                    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])[:4]
                    samples.append((i / fps, float((x + w / 2) / dw)))
                else:
                    samples.append((i / fps, None))
        i += 1
    cap.release()

    # fill gaps with last known position (else centre), then smooth with an exponential filter
    xs, last = [], 0.5
    for _, x in samples:
        last = x if x is not None else last
        xs.append(last)
    sm, v = [], xs[0] if xs else 0.5
    for x in xs:
        v = v + 0.35 * (x - v)
        sm.append(round(v, 4))
    data = {"sample_fps": sample_fps, "track": [[round(t, 2), x] for (t, _), x in zip(samples, sm)],
            "faces_found": sum(1 for _, x in samples if x is not None), "samples": len(samples)}
    out = out or Path(video).with_suffix(".faces.json")
    out.write_text(json.dumps(data))
    return out


def centre_for(faces_json: Path, t_in: float, t_out: float) -> float:
    """Median face centre inside a segment — one steady crop per segment (cuts hide the jumps)."""
    tr = json.loads(Path(faces_json).read_text())["track"]
    xs = [x for t, x in tr if t_in <= t <= t_out]
    return float(np.median(xs)) if xs else 0.5
