"""Generate the submission cover image.

Handbook requires a 16:9 cover image, recommended 380x216 px. Note that 380x216 is
NOT exactly 16:9 (it is 1.759 vs 1.778), so this script produces a true 16:9 image at
1280x720 and also the exact 380x216 size the handbook names, since the submission form
may enforce the stated pixel dimensions rather than the aspect ratio.

Everything is drawn offline with Pillow - no network, no design tool, no external asset.
The palette matches the app's stylesheet so the cover and the product look like one thing.
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parents[1] / "submission"

# Colours taken from app/static/css/app.css so the cover matches the product.
INK = (26, 26, 26)
INK_SOFT = (74, 74, 74)
INK_FAINT = (107, 107, 107)
PAPER = (255, 255, 255)
PAPER_ALT = (244, 242, 238)
CALM = (31, 111, 92)
CALM_LIGHT = (230, 242, 238)
LINE = (216, 212, 204)
ALERT = (163, 35, 28)
INFO = (35, 74, 122)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Find a usable font, preferring a bold face when asked.

    Falls back to Pillow's built-in bitmap font rather than failing: a cover image with
    slightly plainer type is far better than no cover image.
    """
    ordered = FONT_CANDIDATES if bold else list(reversed(FONT_CANDIDATES))
    # Prefer an exact bold/regular match when one exists.
    wants_bold = "Bold" if bold else "Regular"
    for path in ordered:
        if wants_bold in path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    for path in ordered:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


def draw_heartbeat(d: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int, width: int, colour):
    """The app's mark: a pulse trace. Drawn as line segments, no asset required."""
    pts = [
        (x, y + h // 2),
        (x + int(w * 0.22), y + h // 2),
        (x + int(w * 0.32), y + h),
        (x + int(w * 0.45), y),
        (x + int(w * 0.55), y + h // 2),
        (x + int(w * 0.75), y + h // 2),
        (x + int(w * 0.82), y + int(h * 0.28)),
        (x + int(w * 0.90), y + h // 2),
        (x + w, y + h // 2),
    ]
    d.line(pts, fill=colour, width=width, joint="curve")


def build(width: int, height: int, scale: float) -> Image.Image:
    img = Image.new("RGB", (width, height), PAPER)
    d = ImageDraw.Draw(img)

    # ---- background blocks -------------------------------------------------
    d.rectangle([0, 0, width, int(height * 0.52)], fill=PAPER)
    d.rectangle([0, int(height * 0.52), width, height], fill=PAPER_ALT)
    d.line([(0, int(height * 0.52)), (width, int(height * 0.52))], fill=LINE, width=max(1, int(scale)))

    # A calm green bar down the left edge, echoing the app's primary colour.
    d.rectangle([0, 0, max(2, int(9 * scale)), height], fill=CALM)

    pad = int(46 * scale)

    # ---- brand + pulse mark -------------------------------------------------
    draw_heartbeat(
        d, pad, int(34 * scale), int(96 * scale), int(26 * scale),
        max(2, int(4 * scale)), CALM,
    )

    f_brand = load_font(int(30 * scale), bold=True)
    d.text((pad + int(112 * scale), int(30 * scale)), "CareSteps", font=f_brand, fill=INK)

    # ---- headline ----------------------------------------------------------
    f_h1 = load_font(int(52 * scale), bold=True)
    d.text((pad, int(84 * scale)), "Everyday support for", font=f_h1, fill=INK)
    d.text((pad, int(142 * scale)), "seniors managing", font=f_h1, fill=INK)
    d.text((pad, int(200 * scale)), "blood pressure", font=f_h1, fill=CALM)

    # ---- subtitle ----------------------------------------------------------
    f_sub = load_font(int(23 * scale))
    d.text(
        (pad, int(276 * scale)),
        "A missing record is a question, not a conclusion.",
        font=f_sub, fill=INK_SOFT,
    )

    # ---- the three-step mechanic, as three chips ---------------------------
    chips = [
        ("Notice the gap", CALM_LIGHT, CALM),
        ("Ask what got in the way", (253, 243, 224), (138, 90, 0)),
        ("Route to real support", (233, 239, 247), INFO),
    ]
    cy = int(320 * scale)
    cx = pad
    f_chip = load_font(int(21 * scale), bold=True)
    for label, bg, fg in chips:
        bbox = d.textbbox((0, 0), label, font=f_chip)
        tw = bbox[2] - bbox[0]
        pw = int(24 * scale)
        cw = tw + pw * 2
        ch = int(46 * scale)
        d.rounded_rectangle([cx, cy, cx + cw, cy + ch], radius=int(23 * scale), fill=bg)
        d.text((cx + pw, cy + int(11 * scale)), label, font=f_chip, fill=fg)
        cx += cw + int(14 * scale)

    # ---- footer strip ------------------------------------------------------
    d.rectangle([0, int(height * 0.78), width, height], fill=CALM)

    # The footer lines must FIT. Rather than guessing a size, measure the rendered
    # width and shrink until it fits the available space - a clipped footer on a
    # competition cover looks careless.
    def fitted(lines: list[str], start_size: int, colour, bold: bool) -> None:
        avail = width - pad * 2
        size = start_size
        while size > 8:
            font = load_font(size, bold=bold)
            if all(d.textlength(t, font=font) <= avail for t, _ in lines):
                break
            size -= 1
        font = load_font(size, bold=bold)
        for text, y in lines:
            d.text((pad, y), text, font=font, fill=colour)

    fitted(
        [
            ("Tencent Cloud AI Singapore Hackathon 2026  |  Healthcare Track  |  Challenge 2",
             int(height * 0.78) + int(22 * scale)),
        ],
        int(21 * scale), (255, 255, 255), True,
    )
    fitted(
        [
            ("Scenario 3 - Hypertension Management for Older Adults (65+)  |  Prototype. All data simulated.",
             int(height * 0.78) + int(58 * scale)),
        ],
        int(19 * scale), (214, 235, 228), False,
    )

    return img


def build_small(width: int, height: int) -> Image.Image:
    """A layout designed FOR 380x216, not a downscale of the large one.

    Downscaling the big design to this size produces unreadable type, which is a real
    problem because this is the size the handbook names. So the small cover is a
    genuinely different composition: fewer words, larger relative type, and the same
    palette so the two read as one family.

    Rendered at 6x and downsampled, which is what keeps 11px text legible.
    """
    S = 6
    W, H = width * S, height * S
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)

    # Background split and the brand bar.
    d.rectangle([0, 0, W, int(H * 0.62)], fill=PAPER)
    d.rectangle([0, int(H * 0.62), W, H], fill=PAPER_ALT)
    d.rectangle([0, 0, 5 * S, H], fill=CALM)

    pad = 15 * S

    # Brand row: pulse mark, then the name.
    draw_heartbeat(d, pad, 15 * S, 40 * S, 14 * S, 3 * S, CALM)
    d.text((pad + 48 * S, 12 * S), "CareSteps", font=load_font(17 * S, bold=True), fill=INK)

    # Headline: three short lines, sized to fit the width.
    lines = [("Everyday support", INK), ("for seniors", INK), ("managing BP", CALM)]
    size = 26
    while size > 10:
        f = load_font(size * S, bold=True)
        if all(d.textlength(t, font=f) <= W - pad * 2 for t, _ in lines):
            break
        size -= 1
    f = load_font(size * S, bold=True)
    y = 40 * S
    for text, colour in lines:
        d.text((pad, y), text, font=f, fill=colour)
        y += int(size * S * 1.18)

    # One line of the mechanic, not three chips: there is no room at this size.
    d.text(
        (pad, int(H * 0.70)),
        "Finds why a record is missing",
        font=load_font(13 * S, bold=True), fill=CALM,
    )
    d.text(
        (pad, int(H * 0.78)),
        "Healthcare Track  |  Challenge 2",
        font=load_font(11 * S), fill=INK_SOFT,
    )
    d.text(
        (pad, int(H * 0.87)),
        "Prototype. Data simulated.",
        font=load_font(10 * S), fill=INK_FAINT,
    )

    return img.resize((width, height), Image.LANCZOS)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # True 16:9, for any display that cares about aspect ratio.
    big = build(1920, 1080, 2.0)
    p1 = OUT_DIR / "cover_16x9_1920x1080.png"
    big.save(p1)

    # The exact pixel size the handbook names, with its own composition.
    small = build_small(380, 216)
    p2 = OUT_DIR / "cover_380x216.png"
    small.save(p2)

    # A mid-size that is still exactly 16:9, useful for the submission form thumbnail.
    mid = build(1280, 720, 1.333)
    p3 = OUT_DIR / "cover_16x9_1280x720.png"
    mid.save(p3)

    for path in (p1, p2, p3):
        with Image.open(path) as im:
            print(f"{path.name}: {im.size[0]}x{im.size[1]} "
                  f"(ratio {im.size[0] / im.size[1]:.3f}) {path.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
