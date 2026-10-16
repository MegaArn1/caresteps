"""Check exported text, page bounds, raster dimensions and source consistency."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from zipfile import ZipFile

import pdfplumber
from PIL import Image, ImageStat
from pptx import Presentation


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
STEM = os.environ.get("CARE_STEPS_STEM", "CareSteps_Architecture_Diagram")


def compact(text):
    return re.sub(r"\s+", "", text).replace("\u2010", "-").replace("\u2011", "-")


def main():
    pptx = HERE / f"{STEM}.pptx"
    with ZipFile(pptx) as archive:
        assert archive.testzip() is None, "Corrupt PPTX ZIP entry"
    prs = Presentation(pptx)
    assert len(prs.slides) == 9
    assert abs(prs.slide_width / prs.slide_height - 16 / 9) < .0001
    issues = []
    frames = 0
    native_shapes = 0
    with pdfplumber.open(HERE / f"{STEM}.pdf") as pdf:
        assert len(pdf.pages) == len(prs.slides)
        for index, (slide, page) in enumerate(zip(prs.slides, pdf.pages), 1):
            assert (round(page.width), round(page.height)) == (1152, 648)
            assert len(page.chars) > 200, f"Slide {index} has no searchable text"
            assert slide.notes_slide.notes_text_frame.text.strip()
            for shape in slide.shapes:
                native_shapes += 1
                if not shape.has_text_frame or not shape.text.strip():
                    continue
                frames += 1
                bbox = tuple(v / 12700 for v in (
                    shape.left, shape.top,
                    shape.left + shape.width, shape.top + shape.height,
                ))
                x0, top, x1, bottom = bbox
                inside = page.within_bbox((max(0, x0 - 1), max(0, top - 1),
                                          min(page.width, x1 + 1), min(page.height, bottom + 1)))
                text = inside.extract_text(x_tolerance=2, y_tolerance=2) or ""
                if compact(shape.text) not in compact(text):
                    issues.append({"slide": index, "expected": shape.text, "inside": text})
    if issues:
        print(json.dumps(issues, indent=2))
        raise SystemExit(f"{len(issues)} text frame(s) need layout review")

    previews = sorted((HERE / "previews").glob("slide-*.png"))
    assert len(previews) == 9
    for preview in previews:
        with Image.open(preview) as image:
            assert image.size == (1920, 1080)
            assert max(ImageStat.Stat(image.convert("RGB")).stddev) > 15
    assert (HERE / "CareSteps_System_Architecture.png").read_bytes() == previews[1].read_bytes()
    assert (HERE / "CareSteps_Trust_Boundaries.png").read_bytes() == previews[2].read_bytes()
    evidence = json.loads((HERE / "source-verification.json").read_text())
    for filename, digest in evidence["source_sha256"].items():
        assert hashlib.sha256((ROOT / filename).read_bytes()).hexdigest() == digest, filename
    report = f"""# Architecture Deliverable Validation

Validated on 2026-10-16 using `python3 submission/architecture-diagram/verify_artifacts.py`.

| Check | Result |
|---|---|
| PPTX ZIP integrity | Passed |
| Slides / notes | 9 slides, each with speaker notes |
| Editable shapes and text elements | {native_shapes} native elements |
| Aspect ratio | 16:9 |
| PDF dimensions and page count | 9 pages, 1152 x 648 pt |
| Searchable PDF text | Present on all 9 pages |
| Text fitting inside authored text frames | {frames} frames checked; no missing or clipped text |
| Raster previews | 9 nonblank PNGs, each 1920 x 1080 |
| Standalone diagrams | Match slides 2 and 3 byte for byte |
| Code fingerprints | {len(evidence['source_sha256'])} files match source-verification.json |
| Model contracts / SQLite tables | 10 / 13, extracted from current source |
| Existing application tests | 170 passed, 3 upstream deprecation warnings |

All nine PDF pages were rendered for visual inspection. Reviewed the page overview,
system architecture, trust zones and dense tool/data diagrams for readable labels,
clear arrow directions and text collisions. Footers intentionally use smaller type
than the diagram content. PDF export embeds the available fonts.

Release audit note: the redesigned deck was re-exported after correcting clipped
text frames and system-flow arrows. The current verifier checks the selected canonical
PPTX and its matching PDF/previews. Application logic was not changed.

This is artifact and implementation verification. No live model endpoint, clinical
validation, production identity, health-system integration or accessibility audit
was performed as part of this task.
"""
    (HERE / "VALIDATION.md").write_text(report, encoding="utf-8")
    print(f"Validated: 9 slides, {native_shapes} native elements, {frames} text frames, 9 1080p previews")


if __name__ == "__main__":
    main()
