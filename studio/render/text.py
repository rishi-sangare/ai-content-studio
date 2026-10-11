"""Draw text overlays (hook text, word-by-word captions) as transparent images.

Homebrew ffmpeg here has no libass/freetype, so text is rendered with Pillow and
composited by ffmpeg. That also gives exact control over the look.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FONT = "/System/Library/Fonts/Avenir Next.ttc"
HEAVY = 8        # Avenir Next Heavy
DEMI = 2         # Avenir Next Demi Bold
W, H = 1080, 1920
BRAND_GREEN = (124, 255, 58, 255)


def font(size: int, index: int = HEAVY) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT, size, index=index)


def _stroke_text(draw, xy, text, fnt, fill, stroke=10, anchor="mm"):
    draw.text(xy, text, font=fnt, fill=fill, anchor=anchor,
              stroke_width=stroke, stroke_fill=(0, 0, 0, 255))


def caption_word(word: str, out: Path, highlight: bool = False, scale: float = 1.0, y_pct: float = 0.62):
    """One caption frame: a single bold word, centered, for the lower-middle band.

    Returned image is full-frame (1080x1920) so ffmpeg can overlay at 0,0.
    Placement: ~62% down the frame — above the Shorts UI (title/buttons live in the
    bottom ~20% and right edge), below faces.
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    size = int(118 * scale)
    fnt = font(size)
    txt = word.upper()
    # shrink long words to stay inside the safe width (80px side margins + right UI rail)
    while d.textlength(txt, font=fnt) > W - 260 and size > 60:
        size -= 6
        fnt = font(size)
    # soft shadow for legibility on bright footage
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).text((W // 2, int(H * y_pct) + 8), txt, font=fnt, fill=(0, 0, 0, 170), anchor="mm",
                            stroke_width=14, stroke_fill=(0, 0, 0, 170))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(10)))
    d = ImageDraw.Draw(img)
    _stroke_text(d, (W // 2, int(H * y_pct)), txt, fnt, BRAND_GREEN if highlight else (255, 255, 255, 255))
    img.save(out)


def hook_banner(text: str, out: Path, max_lines: int = 2, size: int = 76, top_pct: float = 0.14):
    """Hook text across the top third: up to `max_lines` lines, heavy, white on a dark pill."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    words = text.split()

    def wrap(fnt):
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if d.textlength(trial, font=fnt) > W - 200 and cur:
                lines.append(cur); cur = w
            else:
                cur = trial
        return lines + [cur]

    # never drop words: shrink until the hook fits in max_lines lines
    lines = wrap(font(size))
    while len(lines) > max_lines and size > 44:
        size -= 4
        lines = wrap(font(size))
    fnt = font(size)
    lh = int(size * 1.26)
    top = int(H * top_pct)
    pad = 34
    width = max(d.textlength(l, font=fnt) for l in lines) + pad * 2
    box = [(W - width) / 2, top - pad, (W + width) / 2, top + lh * len(lines) + pad - 20]
    d.rounded_rectangle(box, radius=28, fill=(0, 0, 0, 185))
    for i, l in enumerate(lines):
        d.text((W // 2, top + i * lh + int(size / 2)), l, font=fnt, fill=(255, 255, 255, 255), anchor="mm")
    img.save(out)


def endcard(icon_path: Path, out: Path, title: str | None = None):
    """Closing card: the game icon big and centred with a rounded frame, title underneath.

    Sits in the middle band (above the Shorts UI, below the hook area)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    shade = Image.new("RGBA", (W, H), (0, 0, 0, 150))
    img = Image.alpha_composite(img, shade)
    icon = Image.open(icon_path).convert("RGBA")
    if abs(icon.width / icon.height - 1) < 0.1:          # square game icon
        iw = ih = 560
    else:                                                 # wide store art: keep its shape
        iw = 940; ih = int(iw * icon.height / icon.width)
    side = ih
    icon = icon.resize((iw, ih), Image.LANCZOS)
    mask = Image.new("L", (iw, ih), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, iw, ih], radius=64, fill=255)
    x, y = (W - iw) // 2, int(H * 0.30)
    frame = Image.new("RGBA", (iw + 24, ih + 24), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle([0, 0, iw + 23, ih + 23], radius=76, fill=(255, 255, 255, 255))
    img.alpha_composite(frame, (x - 12, y - 12))
    img.paste(icon, (x, y), mask)
    if title:
        d = ImageDraw.Draw(img)
        _stroke_text(d, (W // 2, y + side + 110), title.upper(), font(84), (255, 255, 255, 255), stroke=9)
        _stroke_text(d, (W // 2, y + side + 200), "ON ROBLOX", font(56, DEMI), BRAND_GREEN, stroke=7)
    img.save(out)


def logo_overlay(logo_path: Path, out: Path, width_pct: float = 0.34, y_pct: float = 0.80):
    """Place a campaign/brand logo centered at y_pct (default just above the bottom UI band)."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    logo = Image.open(logo_path).convert("RGBA")
    lw = int(W * width_pct)
    lh = int(logo.height * lw / logo.width)
    logo = logo.resize((lw, lh), Image.LANCZOS)
    img.alpha_composite(logo, ((W - lw) // 2, int(H * y_pct - lh / 2)))
    img.save(out)


def sticker(png: Path, out: Path, pos=(0.5, 0.4), size: int = 300, rot: float = 0.0):
    """An emoji/meme image placed at pos (centre, as fractions of the frame), with a soft shadow."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    em = Image.open(png).convert("RGBA")
    em = em.resize((int(size), int(size * em.height / em.width)), Image.LANCZOS)   # size = width; keeps aspect
    if rot:
        em = em.rotate(rot, resample=Image.BICUBIC, expand=True)
    x, y = int(W * pos[0] - em.width / 2), int(H * pos[1] - em.height / 2)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sh.alpha_composite(Image.merge("RGBA", (*[Image.new("L", em.size, 0)] * 3, em.getchannel("A").point(lambda a: a * 0.55))),
                       (x + 10, y + 14))
    img = Image.alpha_composite(img, sh.filter(ImageFilter.GaussianBlur(12)))
    img.alpha_composite(em, (x, y))
    img.save(out)


def tier_card(title: str, sub: str | None, color, out: Path, y_pct: float = 0.20, scale: float = 1.0):
    """A clean rarity badge: big tier name in its colour, the odds underneath, on a dark rounded card."""
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    tf, sf = font(int(104 * scale)), font(int(52 * scale), DEMI)
    tw = d.textlength(title, font=tf)
    while tw > W - 140 and tf.size > 40:                   # long title (e.g. a code): shrink the title, not the line under it
        tf = font(tf.size - 2)
        tw = d.textlength(title, font=tf)
    sw = d.textlength(sub, font=sf) if sub else 0
    while sw > W - 140 and sf.size > 30:                   # very long odds: shrink the line, never cut it
        sf = font(sf.size - 2, DEMI)
        sw = d.textlength(sub, font=sf)
    width = max(tw, sw) + 90 * scale
    height = (tf.size + (sf.size + 26 if sub else 0) + 60) * 1.0
    cx, top = W / 2, H * y_pct - height / 2
    col = tuple(color[:3]) + (255,)
    d.rounded_rectangle([cx - width / 2, top, cx + width / 2, top + height], radius=int(34 * scale),
                        fill=(10, 10, 12, 205), outline=col, width=int(7 * scale))
    _stroke_text(d, (cx, top + 30 + tf.size / 2), title, tf, col, stroke=int(8 * scale))
    if sub:
        _stroke_text(d, (cx, top + 30 + tf.size + 22 + sf.size / 2), sub, sf, (255, 255, 255, 255), stroke=int(6 * scale))
    img.save(out)
