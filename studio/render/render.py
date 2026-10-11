"""Recipe (timeline JSON) -> finished 1080x1920 Short. Deterministic: same recipe, same video.

Recipe shape (v1):
{
  "clip_id": "...", "source": "path/to/source.mp4",
  "transcript": "path/to/source.words.json",          # from transcribe.py (optional)
  "segments": [ {"in": 12.30, "out": 15.80, "zoom": 1.0, "crop_x": 0.52}, ... ],
  "hook": {"text": "He really thought that would work", "start": 0.0, "end": 2.6},
  "captions": {"enabled": true, "highlight": ["insane", "perplexity"]},
  "logo": {"path": "...png", "width_pct": 0.34, "y_pct": 0.80},   # if the brief requires one
  "sfx": {"zoom": "shutter", "start": "whoosh", "volume_db": -16},
  "audio": {"lufs": -14}
}
crop_x = horizontal centre of the 9:16 window as a fraction of source width (from reframe.py).
zoom > 1 punches in (e.g. 1.18 on a reaction) and gets a shutter sound.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from studio.render import sfx, text

W, H, FPS = 1080, 1920, 30
EMOJI = Path(__file__).resolve().parent / "assets" / "emoji"     # Noto emoji PNGs, named by codepoint


def probe(path) -> dict:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                          "stream=width,height:format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    j = json.loads(out)
    s = j["streams"][0]
    return {"w": s["width"], "h": s["height"], "duration": float(j["format"]["duration"])}


def _crop_expr(src, seg):
    zoom = seg.get("zoom", 1.0) or 1.0
    sw, sh = src["w"], src["h"]
    if sw / sh <= 0.6:                     # already vertical: centre crop + zoom
        ch = sh / zoom; cw = ch * 9 / 16
        if cw > sw:                        # slightly narrower than 9:16 (e.g. 1078x1920): fit the width instead
            cw = sw; ch = cw * 16 / 9
    else:
        ch = sh / zoom; cw = ch * 9 / 16
        if cw > sw:
            cw = sw; ch = cw * 16 / 9
    cx = (seg.get("crop_x") if seg.get("crop_x") is not None else 0.5) * sw
    x = min(max(cx - cw / 2, 0), sw - cw)
    cy = (seg.get("crop_y") if seg.get("crop_y") is not None else 0.5) * sh
    y = min(max(cy - ch / 2, 0), sh - ch)
    cw, ch, x, y = [int(round(v / 2) * 2) for v in (cw, ch, x, y)]
    if seg.get("pan_to") is not None:      # camera move: glide the window from crop_x to pan_to (eased) over the segment
        x1 = int(round(min(max(seg["pan_to"] * sw - cw / 2, 0), sw - cw) / 2) * 2)
        dur = max(0.01, (seg["out"] - seg["in"]) / float(seg.get("speed", 1.0)))
        p = f"clip(t/{dur:.3f},0,1)"
        xe = f"{x}+({x1 - x})*{p}*{p}*(3-2*{p})"
        return f"crop={cw}:{ch}:x='{xe}':y={y},scale={W}:{H}:flags=lanczos,setsar=1"
    return f"crop={cw}:{ch}:{x}:{y},scale={W}:{H}:flags=lanczos,setsar=1"


def _fit_filter(fit_zoom: float = 1.0, fit_scale: float = 1.0, bg: str = "blur"):
    """Wide frame shown full width over a blurred, darkened copy of itself (for wide menus/popups).

    fit_zoom > 1 first crops the centre (keeping aspect) so a centred popup fills the width.
    fit_scale > 1 enlarges the frame and trims only the SIDES, so the full height (e.g. an on-screen
    toggle and legal line at the bottom) always stays visible while the subject gets bigger."""
    pre = f"crop=iw/{fit_zoom}:ih/{fit_zoom}," if fit_zoom and fit_zoom > 1.01 else ""
    fg = (f"scale={int(W * fit_scale) // 2 * 2}:-2:flags=lanczos,crop={W}:ih:(iw-{W})/2:0"
          if fit_scale and fit_scale > 1.01 else f"scale={W}:-2:flags=lanczos")
    if bg == "black":                         # plain black bars: nothing on screen that could read as "blurry"
        return f"{pre}{fg},pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    return (f"{pre}split[fg0][bg0];[bg0]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur=24:3,eq=brightness=-0.18[bgb];[fg0]{fg}[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,setsar=1")


def render_montage(recipe: dict, out_path: Path) -> Path:
    """Voiceover-driven edit from many short source clips (gameplay campaigns).

    Recipe additions:  "mode": "montage", "voiceover": "vo.wav", "voiceover_words": "vo.words.json",
      segments: [{"src": "clip4.mp4", "in": 0.2, "out": 2.1, "layout": "crop"|"fit", "zoom": 1.2, "crop_x": 0.5}]
      "game_audio_db": -20,  "endcard": {"image": "icon.png", "seconds": 2.2, "text": "ROLL ANIME GIRLS"}
    Segment durations are laid end to end; the video is trimmed to the voiceover length (+ tail).
    """
    segs = recipe["segments"]
    tmp = Path(tempfile.mkdtemp(prefix="studio_montage_"))
    try:
        srcs = []
        for sg in segs:
            if sg["src"] not in srcs:
                srcs.append(sg["src"])
        inputs = []
        for s in srcs:
            inputs += ["-i", str(s)]
        idx = len(srcs)
        still_in = {}                              # split layout needs a second read of its source for the still
        for i, sg in enumerate(segs):
            if sg.get("layout") == "split":
                inputs += ["-i", str(sg["src"])]
                still_in[i] = idx
                idx += 1
        fc, total, bases = [], 0.0, []
        for i, sg in enumerate(segs):
            ext = float(segs[i + 1].get("xfade", 0) or 0) if i + 1 < len(segs) else 0.0   # next shot dissolves in over this one
            k = srcs.index(sg["src"])
            info = probe(sg["src"])
            sp = float(sg.get("speed", 1.0))           # 0.5 = half speed (slow motion), audio stretched to match
            d = sg["out"] - sg["in"]
            if sg.get("layout") == "split":            # before/after: a held frame on top, the clip below, on black
                dd = d / sp
                top_y, gap = sg.get("split_top", 330), sg.get("split_gap", 16)
                fc.append(f"[{still_in[i]}:v]trim=start={sg['still']}:end={sg['still'] + 1 / FPS:.4f},setpts=PTS-STARTPTS,"
                          f"scale={W}:-2:flags=lanczos,tpad=stop_mode=clone:stop_duration={dd:.3f},trim=duration={dd:.3f}[st{i}]")
                fc.append(f"[{k}:v]trim=start={sg['in']}:end={sg['out']},setpts=PTS-STARTPTS,setpts=PTS/{sp},"
                          f"scale={W}:-2:flags=lanczos[mv{i}]")
                fc.append(f"color=c=black:s={W}x{H}:r={FPS}:d={dd:.3f}[bk{i}]")
                fc.append(f"[bk{i}][st{i}]overlay=0:{top_y}[t{i}];[t{i}][mv{i}]overlay=0:{top_y}+h+{gap}:shortest=1,"
                          f"setsar=1,fps={FPS},format=yuv420p[v{i}]")
                fc.append(f"[{k}:a]atrim=start={sg['in']}:end={sg['out']},asetpts=PTS-STARTPTS,"
                          f"{'atempo=' + str(sp) + ',' if abs(sp - 1) > 1e-3 else ''}aresample=48000,aformat=channel_layouts=stereo[g{i}]")
                total += dd
                continue
            lay = (_fit_filter(sg.get("fit_zoom", 1.0), sg.get("fit_scale", 1.0), sg.get("bg", "blur"))
                   if sg.get("layout") == "fit" else _crop_expr(info, sg))
            if sg.get("freeze") is not None:      # hold one frame (at "freeze" s) for the segment's length
                f0 = sg["freeze"]
                vtrim = (f"trim=start={f0}:end={f0 + 0.1:.4f},setpts=PTS-STARTPTS,trim=end_frame=1,"  # first real frame (any fps)
                         f"tpad=stop_mode=clone:stop_duration={d + ext:.3f},trim=duration={d + ext:.3f}")
            else:
                vtrim = f"trim=start={sg['in']}:end={sg['out'] + ext * sp:.4f},setpts=PTS-STARTPTS"
                if abs(sp - 1) > 1e-3:
                    vtrim += f",setpts=PTS/{sp}"
            if sg.get("push") or sg.get("snap"):   # slow push-in / impact zoom on the cut (pre-rendered:
                pre = _pushed_segment(sg["src"], vtrim, lay, (d if sg.get("freeze") is not None else d / sp) + ext,
                                      float(sg.get("push") or 0), tmp / f"push{i}.mp4", float(sg.get("snap") or 0))
                inputs += ["-i", str(pre)]         # zoompan multiplies frames on 60 fps video input)
                fc.append(f"[{idx}:v]setpts=PTS-STARTPTS,fps={FPS},format=yuv420p,settb=AVTB[v{i}]")
                idx += 1
            else:
                fc.append(f"[{k}:v]{vtrim},{lay},fps={FPS},format=yuv420p,settb=AVTB[v{i}]")
            tempo = f"atempo={sp}," if abs(sp - 1) > 1e-3 and sg.get("freeze") is None else ""
            fc.append(f"[{k}:a]atrim=start={sg['in']}:end={sg['out']},asetpts=PTS-STARTPTS,{tempo}aresample=48000,"
                      f"aformat=channel_layouts=stereo[g{i}]")
            bases.append(d if sg.get("freeze") is not None else d / sp)
            total += bases[-1]
        if any(float(sg.get("xfade", 0) or 0) > 0 for sg in segs):
            cur, acc = "v0", bases[0]                 # chain: cross-dissolve where a shot asks for it, hard cut elsewhere
            for i in range(1, len(segs)):
                xf = float(segs[i].get("xfade", 0) or 0)
                nxt = f"x{i}" if i < len(segs) - 1 else "vbase"
                if xf > 0:
                    fc.append(f"[{cur}][v{i}]xfade=transition=fade:duration={xf:.3f}:offset={acc:.3f}[{nxt}]")
                else:
                    fc.append(f"[{cur}][v{i}]concat=n=2:v=1:a=0[{nxt}]")
                cur, acc = nxt, acc + bases[i]
        else:
            fc.append("".join(f"[v{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=0[vbase]")
        fc.append("".join(f"[g{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=0:a=1,volume={recipe.get('game_audio_db', -20)}dB[game]")
        vlabel = "vbase"
        sharp = float(recipe.get("sharpen", 0.0))   # zoomed-in gameplay is upscaled: a light unsharp mask keeps it crisp
        if sharp > 0:
            fc.append(f"[vbase]unsharp=5:5:{sharp}:5:5:0[vsharp]")
            vlabel = "vsharp"
        words_all = json.loads(Path(recipe["voiceover_words"]).read_text())["words"] if recipe.get("voiceover_words") else []
        spans = json.loads(Path(recipe["voiceover_lines"]).read_text()) if recipe.get("voiceover_lines") else []
        events = _resolve_events(recipe.get("events") or [], words_all, spans)
        shakes = [(e["t"], e["t"] + e["shake"]) for e in events if e.get("shake")]
        if shakes:
            win = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in shakes)
            fc.append(f"[{vlabel}]split[shA][shB]")
            fc.append(f"[shB]scale={W * 106 // 100 // 2 * 2}:{H * 106 // 100 // 2 * 2},"
                      f"crop={W}:{H}:x='(iw-ow)/2+24*sin(t*83)':y='(ih-oh)/2+20*sin(t*71+1)'[shC]")
            fc.append(f"[shA][shC]overlay=0:0:enable='{win}'[vsh]")
            vlabel = "vsh"
        for j, fa in enumerate(e["t"] for e in events if e.get("flash")):
            fc.append(f"[{vlabel}]drawbox=x=0:y=0:w=iw:h=ih:color=white@0.85:t=fill:enable='between(t,{fa:.3f},{fa + 0.06:.3f})',"
                      f"drawbox=x=0:y=0:w=iw:h=ih:color=white@0.35:t=fill:enable='between(t,{fa + 0.06:.3f},{fa + 0.18:.3f})'[vfl{j}]")
            vlabel = f"vfl{j}"

        # anime "impact frames": a few frames flicking between inverted and hard black-and-white, like a manga hit
        for j, e in enumerate([e for e in events if e.get("impact")]):
            n, fr = int(e["impact"]), 1.0 / FPS
            t0 = round(e["t"] * FPS) / FPS                  # snap to the frame grid; each window holds exactly one frame
            win = lambda k: f"between(t,{t0 + (k - 0.5) * fr:.4f},{t0 + (k + 0.45) * fr:.4f})"
            inv = "+".join(win(k) for k in range(0, n, 2))
            bw = "+".join(win(k) for k in range(1, n, 2)) or "0"
            fc.append(f"[{vlabel}]split=3[im{j}a][im{j}b][im{j}c]")
            fc.append(f"[im{j}b]hue=s=0,eq=contrast=3.2:brightness=-0.08,negate[im{j}i]")
            fc.append(f"[im{j}c]hue=s=0,eq=contrast=3.2:brightness=-0.08[im{j}w]")
            fc.append(f"[im{j}a][im{j}i]overlay=0:0:enable='{inv}'[im{j}x];[im{j}x][im{j}w]overlay=0:0:enable='{bw}'[im{j}]")
            vlabel = f"im{j}"

        hook = recipe.get("hook")
        if hook and hook.get("text"):
            hp = tmp / "hook.png"; text.hook_banner(hook["text"], hp, hook.get("max_lines", 2), hook.get("size", 76),
                                                     hook.get("top_pct", 0.14))
            inputs += ["-loop", "1", "-i", str(hp)]
            fc.append(f"[{vlabel}][{idx}:v]overlay=0:0:enable='between(t,{hook.get('start', 0)},{hook.get('end', 2.5)})':shortest=1[vh]")
            vlabel, idx = "vh", idx + 1

        end = recipe.get("endcard")
        if end and end.get("image"):
            t0 = max(0.0, total - end.get("seconds", 2.2))
            ep = tmp / "end.png"
            text.endcard(Path(end["image"]), ep, end.get("text"))
            inputs += ["-loop", "1", "-i", str(ep)]
            fc.append(f"[{idx}:v]format=rgba,fade=t=in:st={t0}:d=0.25:alpha=1[endc]")
            fc.append(f"[{vlabel}][endc]overlay=0:0:enable='gte(t,{t0})':shortest=1[ve]")
            vlabel, idx = "ve", idx + 1

        for j, e in enumerate([e for e in events if e.get("sticker")]):
            big, norm = tmp / f"st{j}_b.png", tmp / f"st{j}_n.png"
            em = Path(e["sticker"]) if str(e["sticker"]).endswith(".png") else EMOJI / f"{e['sticker']}.png"
            pos, size, rot = e.get("pos", (0.5, 0.4)), e.get("size", 300), e.get("rot", 0)
            text.sticker(em, big, pos, size * 1.3, rot)          # 2-frame pop, then settle
            text.sticker(em, norm, pos, size, rot)
            sa, sb = e["t"], e["t"] + e.get("sticker_s", 1.0)
            inputs += ["-loop", "1", "-i", str(big), "-loop", "1", "-i", str(norm)]
            fc.append(f"[{vlabel}][{idx}:v]overlay=0:0:enable='between(t,{sa:.3f},{sa + 0.07:.3f})':shortest=1[st{j}a]")
            fc.append(f"[st{j}a][{idx + 1}:v]overlay=0:0:enable='between(t,{sa + 0.07:.3f},{sb:.3f})':shortest=1[st{j}]")
            vlabel, idx = f"st{j}", idx + 2

        for j, e in enumerate([e for e in events if e.get("card")]):
            c = e["card"]
            big, norm = tmp / f"cd{j}_b.png", tmp / f"cd{j}_n.png"
            sc = float(c.get("scale", 1.0))
            text.tier_card(c["title"], c.get("sub"), c.get("color", (255, 255, 255)), big, c.get("y", 0.20), 1.12 * sc)
            text.tier_card(c["title"], c.get("sub"), c.get("color", (255, 255, 255)), norm, c.get("y", 0.20), sc)
            ca, cb = e["t"], e["t"] + e.get("card_s", 1.5)
            inputs += ["-loop", "1", "-i", str(big), "-loop", "1", "-i", str(norm)]
            fc.append(f"[{vlabel}][{idx}:v]overlay=0:0:enable='between(t,{ca:.3f},{ca + 0.08:.3f})':shortest=1[cd{j}a]")
            fc.append(f"[cd{j}a][{idx + 1}:v]overlay=0:0:enable='between(t,{ca + 0.08:.3f},{cb:.3f})':shortest=1[cd{j}]")
            vlabel, idx = f"cd{j}", idx + 2

        # meme cut-ins: a short GIF/mp4 (no audio) popped over the edit with a white border, looped for gif_s seconds
        for j, e in enumerate([e for e in events if e.get("gif")]):
            w, (px, py), dur = int(e.get("w", 560)), e.get("pos", (0.5, 0.38)), float(e.get("gif_s", 1.2))
            inputs += ["-stream_loop", "-1", *(["-ss", f"{float(e['gif_from']):.2f}"] if e.get("gif_from") else []),
                       "-t", f"{dur:.3f}", "-i", str(e["gif"])]
            b = int(e.get("border", 10))
            fc.append(f"[{idx}:v]fps={FPS},scale={w - 2 * b}:-2,pad=iw+{2 * b}:ih+{2 * b}:{b}:{b}:white,format=rgba,"
                      f"setpts=PTS-STARTPTS+{e['t']:.3f}/TB[gf{j}]")
            fc.append(f"[{vlabel}][gf{j}]overlay=x={int(px * W)}-overlay_w/2:y={int(py * H)}-overlay_h/2:"
                      f"enable='between(t,{e['t']:.3f},{e['t'] + dur:.3f})':eof_action=pass[gv{j}]")
            vlabel, idx = f"gv{j}", idx + 1

        if recipe.get("motion"):                  # animated captions/titles from Remotion replace the PIL captions
            from studio.render import motion
            ov = motion.overlay(recipe, total)
            inputs += ["-i", str(ov)]
            fc.append(f"[{idx}:v]format=rgba,setpts=PTS-STARTPTS[mot]")
            fc.append(f"[{vlabel}][mot]overlay=0:0:eof_action=pass[vmo]")
            vlabel, idx = "vmo", idx + 1
        cap = recipe.get("captions") or {}
        if cap.get("enabled", True) and recipe.get("voiceover_words") and not recipe.get("motion"):
            words = json.loads(Path(recipe["voiceover_words"]).read_text())["words"]
            lst = _caption_track(words, [{"in": 0.0, "out": total}], tmp, cap.get("highlight"), base_y=cap.get("y", 0.62),
                                  lift_after=t0 if end and end.get("image") else None)
            if lst:
                inputs += ["-f", "concat", "-safe", "0", "-i", str(lst)]
                fc.append(f"[{idx}:v]fps={FPS},format=rgba[capt]")
                fc.append(f"[{vlabel}][capt]overlay=0:0:eof_action=pass[vc]")
                vlabel, idx = "vc", idx + 1

        if recipe.get("voiceover"):
            inputs += ["-i", str(recipe["voiceover"])]
            fc.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,apad[vo]")
            idx += 1
            alabels = ["vo", "game"]
        else:                                     # footage-only clips (e.g. brand campaigns: original audio only)
            fc.append("[game]apad[vo]")
            alabels = ["vo"]
        mus = recipe.get("music")
        if mus and mus.get("path") and recipe.get("voiceover"):
            # background bed, ducked under the voice (sidechain) so lines stay clear and gaps feel alive
            inputs += ["-stream_loop", "-1", "-i", str(mus["path"])]
            fc.append("[vo]asplit=2[vo][vokey]")
            fc.append(f"[{idx}:a]atrim=start={mus.get('start', 0)},asetpts=PTS-STARTPTS,aresample=48000,"
                      f"aformat=channel_layouts=stereo,volume={mus.get('db', -18)}dB,"
                      f"afade=t=in:d=0.4,afade=t=out:st={max(0.0, total - 1.2):.3f}:d=1.2[mraw]")
            fc.append(f"[mraw][vokey]sidechaincompress=threshold={mus.get('duck_threshold', 0.03)}:"
                      f"ratio={mus.get('duck_ratio', 6)}:attack=15:release=350[music]")
            alabels.append("music")
            idx += 1
        fx = recipe.get("sfx") or {}
        vol = fx.get("volume_db", -16)
        hits, off = ([(fx["start"], 0.0, vol)] if fx.get("start") else []), 0.0
        for sg in segs:
            if (sg.get("zoom") or 1.0) > 1.01 and fx.get("zoom"):
                hits.append((fx["zoom"], off, vol))
            off += (sg["out"] - sg["in"]) / (1 if sg.get("freeze") is not None else float(sg.get("speed", 1.0)))
        hits = [(n, a, d, None) for n, a, d in hits]
        hits += [(e["sfx"], e["t"], e.get("db", -8), e.get("sfx_max")) for e in events if e.get("sfx")]
        for j, (name, at, db, mx) in enumerate(hits):
            p = sfx.pick(name)
            if not p:
                continue
            inputs += ["-i", str(p)]
            ms = int(at * 1000)
            cut = f"atrim=end={mx},afade=t=out:st={max(0, mx - 0.25)}:d=0.25," if mx else ""   # long memes get cut short
            fc.append(f"[{idx}:a]{cut}aresample=48000,aformat=channel_layouts=stereo,volume={db}dB,adelay={ms}|{ms}[fx{j}]")
            alabels.append(f"fx{j}"); idx += 1
        fc.append("".join(f"[{l}]" for l in alabels) +
                  f"amix=inputs={len(alabels)}:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
        fc.append(f"[{vlabel}]format=yuv420p[vout]")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs, "-filter_complex", ";".join(fc),
                        "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}", "-c:v", "libx264", "-preset", "medium",
                        "-crf", str(recipe.get("crf", 18)), "-profile:v", "high", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
                        "-ar", "48000", "-movflags", "+faststart", str(out_path)], check=True)
        return out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _pushed_segment(src, vtrim: str, lay: str, dur: float, push: float, out: Path, snap: float = 0.0) -> Path:
    """Render one segment at 1080x1920 / 30 fps, then zoom in smoothly by `push` over its length, frame by frame.

    snap > 0 = impact zoom on the cut: starts `snap` zoomed in and settles to normal in ~0.22 s (ease-out)."""
    import numpy as np
    from PIL import Image
    base = out.with_suffix(".base.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-filter_complex",
                    f"[0:v]{vtrim},{lay},fps={FPS},format=rgb24[v]", "-map", "[v]", "-an", "-t", f"{dur:.3f}",
                    "-c:v", "libx264", "-crf", "12", "-preset", "veryfast", "-pix_fmt", "yuv444p", str(base)], check=True)
    n = max(1, int(round(dur * FPS)))
    dec = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", str(base), "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           stdout=subprocess.PIPE)
    enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                            "-r", str(FPS), "-i", "-", "-frames:v", str(n), "-c:v", "libx264", "-crf", "14",
                            "-preset", "veryfast", "-pix_fmt", "yuv420p", str(out)], stdin=subprocess.PIPE)
    fb, last = W * H * 3, None
    try:
        for f in range(n):
            raw = dec.stdout.read(fb)
            if len(raw) == fb:
                last = Image.frombuffer("RGB", (W, H), raw, "raw", "RGB", 0, 1).copy()
            if last is None:
                break
            u = f / max(1, n - 1)
            z = 1 + push * (u * u * (3 - 2 * u) * 0.35 + u * 0.65)   # gentle ease-in, then steady
            z += snap * max(0.0, 1 - f / (0.22 * FPS)) ** 3
            w, h = W / z, H / z
            box = ((W - w) / 2, (H - h) / 2, (W + w) / 2, (H + h) / 2)
            enc.stdin.write(np.asarray(last.resize((W, H), Image.BICUBIC, box=box)).tobytes())
    finally:
        enc.stdin.close(); enc.wait(); dec.stdout.close(); dec.wait()
    base.unlink(missing_ok=True)
    return out


def _resolve_events(events, words, spans):
    """Place each event in time: "at" seconds, "cue" = next matching spoken word (in order; "after": true uses
    the word's end), or "line_end" = end of a voiceover line id. "offset" shifts it."""
    out, pos = [], 0
    ends = {sp["id"]: sp["end"] for sp in spans}
    for e in events:
        e = dict(e)
        if "at" in e:
            t = e["at"]
        elif "line_end" in e:
            t = ends[e["line_end"]]
        else:
            cue = e["cue"].lower()
            k = next((i for i in range(pos, len(words)) if words[i]["word"].lower().strip(" ,.?!\"'") == cue), None)
            if k is None:
                raise ValueError(f"event cue '{cue}' not found in the voiceover after word {pos}")
            pos = k + 1
            t = words[k]["end"] if e.get("after") else words[k]["start"]
        e["t"] = max(0.0, t + e.get("offset", 0.0))
        out.append(e)
    return out


def _caption_track(words, segments, tmp: Path, highlight, lift_after: float | None = None,
                   base_y: float = 0.62) -> Path | None:
    """Map source-timed words onto the output timeline and build a PNG concat track."""
    placed, offset = [], 0.0
    for seg in segments:
        a, b = seg["in"], seg["out"]
        for w in words:
            if w["end"] <= a or w["start"] >= b:
                continue
            s = max(w["start"], a) - a + offset
            e = min(w["end"], b) - a + offset
            placed.append((s, e, w["word"]))
        offset += b - a
    if not placed:
        return None
    total = offset
    blank = tmp / "blank.png"
    from PIL import Image
    Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(blank)
    lines, t = [], 0.0
    hl = {h.lower() for h in (highlight or [])}
    for i, (s, e, word) in enumerate(placed):
        # hold each word until the next one starts (no flicker between words), max 0.9s
        nxt = placed[i + 1][0] if i + 1 < len(placed) else min(e + 0.4, total)
        e = min(max(e, s + 0.12), nxt, s + 0.9)
        if lift_after is not None and s < lift_after - 0.05:
            e = min(e, lift_after)   # don't hold a low caption over the end-card title
        if s > t:
            lines.append((blank, s - t))
        clean = word.strip(" ,.?!\"'")
        is_hl = clean.lower() in hl or any(ch.isdigit() for ch in clean)
        big, norm = tmp / f"w{i}_b.png", tmp / f"w{i}_n.png"
        y = 0.19 if lift_after is not None and s >= lift_after - 0.05 else base_y   # above the end-card icon
        text.caption_word(clean, big, highlight=is_hl, scale=1.12, y_pct=y)      # 2-frame "pop"
        text.caption_word(clean, norm, highlight=is_hl, scale=1.0, y_pct=y)
        pop = min(0.066, (e - s) / 2)
        lines.append((big, pop))
        lines.append((norm, e - s - pop))
        t = e
    if t < total:
        lines.append((blank, total - t))
    lst = tmp / "captions.txt"
    body = "".join(f"file '{p}'\nduration {d:.3f}\n" for p, d in lines)
    body += f"file '{lines[-1][0]}'\n"   # concat demuxer needs the last file repeated
    lst.write_text(body)
    return lst


def silences(src_path, min_gap=0.28, noise_db=-38):
    """[(start, end)] of pauses in the source audio (ASR word timings stretch over pauses)."""
    import re
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(src_path), "-af",
                          f"silencedetect=noise={noise_db}dB:d={min_gap}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    starts = [float(x) for x in re.findall(r"silence_start: (-?[\d.]+)", err)]
    ends = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    return list(zip(starts, ends))


def tighten(segments, gaps, keep=0.08):
    """Cut pauses out of segments, leaving `keep` seconds of air on each side of the cut.

    Each piece keeps the parent's zoom/crop; only the first piece of a zoomed segment keeps
    its sound effect so a split doesn't stack shutters.
    """
    out = []
    for sg in segments:
        start, first = sg["in"], True
        for gs, ge in gaps:
            if ge <= sg["in"] or gs >= sg["out"]:
                continue
            cut_out, resume = max(gs + keep, sg["in"]), min(ge - keep, sg["out"])
            if resume - cut_out < 0.1:
                continue
            if cut_out - start > 0.15:
                out.append({**sg, "in": round(start, 3), "out": round(cut_out, 3), "sfx": first})
                first = False
            start = resume
        if sg["out"] - start > 0.15:
            out.append({**sg, "in": round(start, 3), "out": round(sg["out"], 3), "sfx": first})
    return out


def render(recipe: dict, out_path: Path) -> Path:
    src_path = Path(recipe["source"])
    src = probe(src_path)
    segs = recipe["segments"]
    if recipe.get("tighten", True):
        segs = tighten(segs, silences(src_path))
        recipe["segments"] = segs   # so checks see the real cut list
    tmp = Path(tempfile.mkdtemp(prefix="studio_render_"))
    try:
        inputs = ["-i", str(src_path)]
        fc = []
        for i, sg in enumerate(segs):
            fc.append(f"[0:v]trim=start={sg['in']}:end={sg['out']},setpts=PTS-STARTPTS,{_crop_expr(src, sg)},fps={FPS}[v{i}]")
            fc.append(f"[0:a]atrim=start={sg['in']}:end={sg['out']},asetpts=PTS-STARTPTS,aresample=48000[a{i}]")
        fc.append("".join(f"[v{i}][a{i}]" for i in range(len(segs))) + f"concat=n={len(segs)}:v=1:a=1[vbase][abase]")
        vlabel, idx = "vbase", 1

        # hook text
        hook = recipe.get("hook")
        if hook and hook.get("text"):
            hp = tmp / "hook.png"
            text.hook_banner(hook["text"], hp)
            inputs += ["-loop", "1", "-i", str(hp)]
            fc.append(f"[{vlabel}][{idx}:v]overlay=0:0:enable='between(t,{hook.get('start', 0)},{hook.get('end', 2.5)})':shortest=1[vh]")
            vlabel, idx = "vh", idx + 1

        # word-by-word captions
        cap = recipe.get("captions") or {}
        if cap.get("enabled", True) and recipe.get("transcript"):
            words = json.loads(Path(recipe["transcript"]).read_text())["words"]
            lst = _caption_track(words, segs, tmp, cap.get("highlight"))
            if lst:
                inputs += ["-f", "concat", "-safe", "0", "-i", str(lst)]
                fc.append(f"[{idx}:v]fps={FPS},format=rgba[capt]")
                fc.append(f"[{vlabel}][capt]overlay=0:0:eof_action=pass[vc]")
                vlabel, idx = "vc", idx + 1

        # brand/campaign logo
        logo = recipe.get("logo")
        if logo and logo.get("path"):
            lp = tmp / "logo.png"
            text.logo_overlay(Path(logo["path"]), lp, logo.get("width_pct", 0.34), logo.get("y_pct", 0.80))
            inputs += ["-loop", "1", "-i", str(lp)]
            fc.append(f"[{vlabel}][{idx}:v]overlay=0:0:shortest=1[vl]")
            vlabel, idx = "vl", idx + 1

        # sound effects: whoosh at start, shutter on every zoom-in cut
        fx = recipe.get("sfx") or {}
        vol = fx.get("volume_db", -16)
        hits, offset = [], 0.0
        if fx.get("start"):
            hits.append((fx["start"], 0.0))
        for sg in segs:
            if (sg.get("zoom") or 1.0) > 1.01 and fx.get("zoom") and sg.get("sfx", True):
                hits.append((fx["zoom"], offset))
            offset += sg["out"] - sg["in"]
        alabels = ["abase"]
        for j, (name, at) in enumerate(hits):
            inputs += ["-i", str(sfx.path(name))]
            ms = int(at * 1000)
            fc.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,volume={vol}dB,adelay={ms}|{ms}[fx{j}]")
            alabels.append(f"fx{j}")
            idx += 1
        lufs = (recipe.get("audio") or {}).get("lufs", -14)
        mix = "".join(f"[{l}]" for l in alabels)
        fc.append(f"{mix}amix=inputs={len(alabels)}:normalize=0:duration=first,loudnorm=I={lufs}:TP=-1.5:LRA=11[aout]")
        fc.append(f"[{vlabel}]format=yuv420p[vout]")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *inputs,
               "-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]",
               "-t", f"{offset:.3f}", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
               "-profile:v", "high", "-r", str(FPS), "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
               "-movflags", "+faststart", str(out_path)]
        subprocess.run(cmd, check=True)
        return out_path
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
