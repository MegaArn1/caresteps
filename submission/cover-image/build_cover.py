"""Compose the submission cover from the existing brand mark and real UI crops.

Requires Pillow. No application server or network is needed after assets exist.
The 380x216 version has its own layout; screenshots always keep their aspect ratio.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, PngImagePlugin


HERE = Path(__file__).resolve().parent
ASSETS = HERE / "assets"
P = {
    "white": "#FFFFFF", "paper": "#F8FAFC", "ink": "#192F35",
    "muted": "#50626B", "blue": "#0052CC", "teal": "#008678",
    "aqua": "#00B4A6", "blue_light": "#EAF1FD", "teal_light": "#E6F4F0",
    "line": "#CFDDE3",
}
FONT_DIR = Path("/usr/share/fonts/truetype/croscore")
FALLBACK_DIR = Path("/usr/share/fonts/truetype/dejavu")


def font(size, bold=False):
    name = "Arimo-Bold.ttf" if bold else "Arimo-Regular.ttf"
    path = FONT_DIR / name
    if not path.exists():
        path = FALLBACK_DIR / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    return ImageFont.truetype(str(path), round(size))


class Canvas:
    def __init__(self, width, height):
        self.image = Image.new("RGB", (width, height), P["white"])
        self.draw = ImageDraw.Draw(self.image)
        self.text_bounds = []
        self.asset_bounds = []

    def text(self, x, y, text, size, color="ink", bold=False, max_width=None):
        f = font(size, bold)
        b = self.draw.textbbox((x, y), text, font=f, anchor="lt")
        if max_width is not None and b[2] - b[0] > max_width:
            raise ValueError(f"Text too wide: {text}")
        if min(b[:2]) < 0 or b[2] > self.image.width or b[3] > self.image.height:
            raise ValueError(f"Text outside canvas: {text}")
        self.draw.text((x, y), text, font=f, fill=P.get(color, color), anchor="lt")
        self.text_bounds.append({"text": text, "bbox": list(b), "size": size})

    def asset(self, name, x, y, width):
        source = Image.open(ASSETS / name).convert("RGBA")
        height = round(source.height * width / source.width)
        resized = source.resize((round(width), height), Image.Resampling.LANCZOS)
        self.image.paste(resized, (round(x), round(y)), resized)
        self.asset_bounds.append({"asset": name, "bbox": [x, y, x + width, y + height]})
        return height

    def line(self, points, color="line", width=2):
        self.draw.line(points, fill=P[color], width=width)

    def shadow(self, box, radius=10, opacity=22):
        overlay = Image.new("RGBA", self.image.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        x0, y0, x1, y1 = box
        d.rounded_rectangle((x0, y0 + 7, x1, y1 + 7), radius=8,
                            fill=(25, 47, 53, opacity))
        overlay = overlay.filter(ImageFilter.GaussianBlur(radius))
        self.image = Image.alpha_composite(self.image.convert("RGBA"), overlay).convert("RGB")
        self.draw = ImageDraw.Draw(self.image)

    def check(self, x, y, label):
        self.draw.ellipse((x, y, x + 27, y + 27), fill=P["teal_light"])
        self.draw.line([(x + 7, y + 14), (x + 12, y + 19), (x + 21, y + 9)],
                       fill=P["teal"], width=3, joint="curve")
        self.text(x + 43, y + 1, label, 26, color="muted")


def large(design_height=1080):
    c = Canvas(1920, design_height)
    sy = design_height / 1080
    y = lambda v: round(v * sy)
    c.draw.rectangle((0, 0, 1919, 9), fill=P["blue"])
    c.draw.rectangle((866, y(190), 1919, y(948)), fill=P["blue_light"])
    c.draw.rectangle((866, y(190), 879, y(948)), fill=P["aqua"])

    c.asset("caresteps-mark.png", 94, y(70), 82)
    c.text(198, y(67), "CareSteps", 108, bold=True, max_width=640)
    c.text(1270, y(91), "HEALTHCARE  /  CHALLENGE 2", 25, color="blue", bold=True, max_width=560)
    c.text(1270, y(130), "AI HEALTHIER EVERY DAY", 21, color="muted", max_width=560)

    c.text(98, y(278), "AI FOR EVERYDAY SELF-CARE", 26, color="blue", bold=True, max_width=730)
    for text, top, color in [
        ("Blood pressure", 349, "ink"),
        ("support for", 436, "ink"),
        ("older adults.", 523, "teal"),
    ]:
        c.text(94, y(top), text, 78, color=color, bold=True, max_width=730)
    c.text(98, y(666), "Record. Understand. Prepare.", 34, color="muted", max_width=715)
    c.check(98, y(756), "Safety gates before AI")
    c.check(98, y(811), "Confirm before saving")
    c.text(98, y(909), "Prototype / Simulated data", 22, color="muted", max_width=710)

    sx, sw = 928, 884
    home = Image.open(ASSETS / "home-actions.png")
    home_h = round(home.height * sw / home.width)
    top = y(235)
    c.shadow((sx - 14, top - 14, sx + sw + 14, top + home_h + 14))
    c.draw.rounded_rectangle((sx - 14, top - 14, sx + sw + 14, top + home_h + 14),
                            radius=8, fill=P["white"], outline=P["line"], width=2)
    c.asset("home-actions.png", sx, top, sw)
    c.text(sx, y(706), "TWO NUMBERS. YOU CHECK BEFORE SAVING.", 21,
           color="blue", bold=True, max_width=884)
    top2 = y(759)
    reading = Image.open(ASSETS / "reading-values.png")
    reading_h = round(reading.height * sw / reading.width)
    c.draw.rounded_rectangle((sx - 14, top2 - 14, sx + sw + 14, top2 + reading_h + 14),
                            radius=8, fill=P["white"], outline=P["line"], width=2)
    c.asset("reading-values.png", sx, top2, sw)
    c.line([(96, y(986)), (1824, y(986))])
    c.text(98, y(1020), "TENCENT CLOUD AI SINGAPORE HACKATHON 2026", 24,
           color="blue", bold=True, max_width=1100)
    c.text(1343, y(1020), "Designed for daily self-care.", 25, color="teal", max_width=481)
    return c


def thumbnail(width=380, height=216):
    scale = 6
    c = Canvas(width * scale, height * scale)
    q = lambda value: round(value * scale)
    c.draw.rectangle((0, 0, c.image.width, q(3)), fill=P["blue"])
    c.draw.rectangle((q(216), q(122), c.image.width, q(183)), fill=P["blue_light"])
    c.asset("caresteps-mark.png", q(18), q(17), q(31))
    c.text(q(60), q(17), "CareSteps", q(34), bold=True, max_width=q(297))
    c.text(q(18), q(72), "Blood pressure support", q(24), bold=True, max_width=q(345))
    c.text(q(18), q(103), "for older adults.", q(24), color="teal", bold=True, max_width=q(345))
    c.text(q(18), q(148), "Record. Understand. Prepare.", q(11), color="muted", max_width=q(200))
    c.text(q(18), q(169), "Prototype / Simulated data", q(9), color="muted", max_width=q(190))
    c.asset("reading-values.png", q(221), q(134), q(146))
    c.draw.rectangle((0, q(189), c.image.width, c.image.height), fill=P["blue"])
    c.text(q(18), q(198), "Tencent Cloud AI Singapore Hackathon 2026", q(11), color="white",
           bold=True, max_width=q(345))
    return c


def save(c, filename, size, purpose):
    image = c.image.resize(size, Image.Resampling.LANCZOS)
    meta = PngImagePlugin.PngInfo()
    meta.add_text("Title", "CareSteps - Blood pressure support for older adults")
    meta.add_text("Description", "Competition prototype. Product screenshots use fictional demo data.")
    meta.add_text("Software", "CareSteps cover composer / Pillow")
    image.save(HERE / filename, optimize=True, pnginfo=meta, dpi=(96, 96))
    target = HERE / filename
    if target.stat().st_size >= 2 * 1024 * 1024:
        raise ValueError(f"Cover exceeds 2 MiB: {filename}")
    factor = size[0] / c.image.width
    return {
        "filename": filename, "dimensions": list(size), "purpose": purpose,
        "bytes": target.stat().st_size,
        "sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "text": [
            {"text": t["text"], "size_px": round(t["size"] * factor, 2),
             "bbox": [round(v * factor, 2) for v in t["bbox"]]}
            for t in c.text_bounds
        ],
        "placed_assets": c.asset_bounds,
    }


def main():
    required = ["caresteps-mark.png", "home-actions.png", "reading-values.png"]
    for filename in required:
        if not (ASSETS / filename).exists():
            raise SystemExit(f"Missing asset {filename}; run capture_assets.cjs first")
    main_cover = large()
    outputs = [
        save(main_cover, "CareSteps_Cover.png", (1920, 1080), "Primary submission cover, exact 16:9"),
        save(main_cover, "CareSteps_Cover_1280x720.png", (1280, 720), "Smaller exact 16:9 cover"),
        save(thumbnail(), "CareSteps_Cover_380x216.png", (380, 216), "Handbook's recommended pixel size; separate layout"),
        save(large(1008), "CareSteps_Cover_1200x630.png", (1200, 630), "Social/Open Graph version; not the handbook aspect ratio"),
    ]
    # Actual-size thumbnail beside a scaled primary cover for visual inspection.
    preview = Image.new("RGB", (1280, 1055), "#EDF2F5")
    d = ImageDraw.Draw(preview)
    with Image.open(HERE / "CareSteps_Cover.png") as image:
        preview.paste(image.resize((1248, 702), Image.Resampling.LANCZOS), (16, 16))
    d.text((24, 742), "380 x 216 / actual size", font=font(24, True), fill=P["ink"])
    with Image.open(HERE / "CareSteps_Cover_380x216.png") as image:
        preview.paste(image, (24, 792))
    d.text((450, 802), "Primary: 1920 x 1080 (16:9)", font=font(25, True), fill=P["blue"])
    d.text((450, 846), "Thumbnail: 380 x 216 (handbook size)", font=font(22), fill=P["muted"])
    d.text((450, 888), "Social: 1200 x 630 (alternate layout)", font=font(22), fill=P["muted"])
    d.text((450, 957), "Real UI crops / Existing brand / Simulated data", font=font(21), fill=P["teal"])
    preview.save(HERE / "CareSteps_Cover_Preview.png", optimize=True)
    manifest = {
        "date": "2026-10-16", "handbook_pdf_page": 37,
        "palette": P,
        "font": "Arimo Bold / Regular",
        "source_assets": {
            name: hashlib.sha256((ASSETS / name).read_bytes()).hexdigest() for name in required
        },
        "outputs": outputs,
    }
    (HERE / "cover-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    for item in outputs:
        print(f"{item['filename']}: {item['dimensions']}, {item['bytes'] // 1024} KiB")


if __name__ == "__main__":
    main()
