"""Build editable submission slides and, with --render, PDF/PNG exports.

Requires python-pptx and Pillow. Rendering additionally uses LibreOffice and
Poppler. All presentation elements are native PowerPoint shapes and text.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from zipfile import ZipFile

from PIL import Image, ImageDraw, ImageFilter, ImageOps

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt


OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
STEM = os.environ.get("CARE_STEPS_STEM", "CareSteps_Architecture_Diagram")
FONT = "Arimo"
MONO = "DejaVu Sans Mono"
ASSETS = OUT / "assets"
C = {
    "bg": "F7F5F1", "white": "FFFFFF", "ink": "2F2D29",
    "muted": "6B6861", "line": "CBD4D9", "blue": "0B61C9",
    "blue_bg": "EEF5FB", "blue_accent": "0752AB", "teal": "138F98",
    "teal_bg": "EAF7F5", "teal_light": "BFE8E7", "red": "C74C48",
    "red_bg": "FDF0EE", "red_accent": "A83C39", "amber": "A77722",
    "amber_bg": "FAF3E5", "amber_accent": "8B6019", "soft": "F2F0EC",
    "soft_dark": "E5E8E8", "purple": "3B2561", "cyan": "64C7D4",
}
TOTAL_SLIDES = 9


def ensure_assets():
    """Create local visual assets from the supplied template-1 device art."""
    ASSETS.mkdir(exist_ok=True)
    template = OUT / "template-1-Purple Modern Launching Digital Product Presentation.pptx"
    wanted = {"image8.png": "phone.png", "image17.png": "tablet.png",
              "image38.png": "watch.png", "image39.png": "laptop.png",
              "image1.png": "purple_blob.png"}
    if template.exists():
        with ZipFile(template) as archive:
            for source, target in wanted.items():
                out = ASSETS / target
                if not out.exists():
                    out.write_bytes(archive.read(f"ppt/media/{source}"))
    screen = ASSETS / "laptop_screen.png"
    source_screen = OUT.parent / "cover-image" / "assets" / "home-actions.png"
    if source_screen.exists():
        source = Image.open(source_screen).convert("RGB")
        fitted = ImageOps.contain(source, (1600, 900), Image.Resampling.LANCZOS)
        display = Image.new("RGB", (1600, 900), (250, 251, 255))
        display.paste(fitted, ((1600 - fitted.width) // 2, (900 - fitted.height) // 2))
        display.save(screen, quality=95)
    bg = ASSETS / "template2_background.png"
    if not bg.exists():
        base = Image.new("RGBA", (1920, 1080), (247, 245, 241, 255))
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        draw.ellipse((460, -270, 1420, 230), fill=(95, 196, 215, 58))
        draw.ellipse((-390, 700, 670, 1340), fill=(24, 104, 202, 72))
        draw.ellipse((1330, 760, 2220, 1330), fill=(95, 205, 211, 68))
        draw.ellipse((1510, -260, 2080, 300), fill=(60, 133, 212, 52))
        layer = layer.filter(ImageFilter.GaussianBlur(100))
        base.alpha_composite(layer)
        base.convert("RGB").save(bg, quality=95)


def rgb(value):
    return RGBColor.from_string(C.get(value, value))


def literal(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            names = [t.id for t in stmt.targets if isinstance(t, ast.Name)]
            if name in names:
                return ast.literal_eval(stmt.value)
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.target.id == name:
                return ast.literal_eval(stmt.value)
    raise ValueError(f"Missing constant {name} in {path}")


def inspect_sources(test_count):
    contracts = literal("app/tools/contracts.py", "TOOL_SCHEMAS")
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(literal("app/db.py", "SCHEMA"))
        tables = sorted(row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ))
    finally:
        conn.close()
    files = [
        "app/main.py", "app/config.py", "app/db.py", "app/repository.py",
        "app/routes/api.py", "app/routes/deps.py", "app/safety/__init__.py",
        "app/tools/contracts.py", "app/tools/handlers.py", "app/stats.py",
        "app/summary.py", "app/llm/orchestrator.py", "app/llm/provider.py",
        "app/llm/prompts.py", "app/content_loader.py",
    ]
    return {
        "review_date": date(2026, 10, 16).isoformat(),
        "handbook": {
            "filename": "Copy of AI CAN DO IT Tencent Cloud AI Singapore Hackathon 2026 Handbook.pdf",
            "submission_requirements_pdf_page": 37,
            "healthcare_challenge_2_diagram_guidance_pdf_page": 35,
            "diagram_scope": ["architecture", "trust boundaries", "key design trade-offs"],
        },
        "tool_names": [t["function"]["name"] for t in contracts],
        "ui_only_handler": "confirm_draft",
        "tables": tables,
        "automated_tests_passed": test_count,
        "test_command": ".venv/bin/python -m pytest -q",
        "live_endpoint_tested_for_this_deliverable": False,
        "source_sha256": {
            f: hashlib.sha256((ROOT / f).read_bytes()).hexdigest() for f in files
        },
    }


class Deck:
    def __init__(self, evidence):
        ensure_assets()
        self.prs = Presentation()
        self.prs.slide_width = Inches(16)
        self.prs.slide_height = Inches(9)
        self.evidence = evidence
        self.prs.core_properties.title = "CareSteps | Architecture & Trust Boundaries"
        self.prs.core_properties.subject = "Healthcare Challenge 2: AI Healthier Every Day"
        self.prs.core_properties.author = "CareSteps"
        self.prs.core_properties.keywords = "architecture, trust boundaries, safety, tool calling"
        self.prs.core_properties.comments = "Source-checked competition prototype architecture."

    def rect(self, s, x, y, w, h, fill="white", line="line", dashed=False, rounded=True, shadow=False):
        sh = s.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
            Inches(x), Inches(y), Inches(w), Inches(h)
        )
        style = sh._element.find(qn("p:style"))
        if style is not None:
            sh._element.remove(style)
        sh.fill.solid()
        sh.fill.fore_color.rgb = rgb(fill)
        if line:
            sh.line.color.rgb = rgb(line)
            sh.line.width = Pt(0.75)
        else:
            sh.line.fill.background()
        if dashed:
            sh.line._get_or_add_ln().append(OxmlElement("a:prstDash"))
            sh.line._get_or_add_ln()[-1].set("val", "dash")
        if shadow:
            sp_pr = sh._element.find(qn("p:spPr"))
            if sp_pr is not None:
                effect_lst = OxmlElement("a:effectLst")
                outer_shdw = OxmlElement("a:outerShdw")
                outer_shdw.set("blurRad", "30000")
                outer_shdw.set("dist", "18000")
                outer_shdw.set("dir", "2700000")
                outer_shdw.set("algn", "ctr")
                outer_shdw.set("rotWithShape", "0")
                srgb_clr = OxmlElement("a:srgbClr")
                srgb_clr.set("val", "2F2D29")
                alpha = OxmlElement("a:alpha")
                alpha.set("val", "12000")
                srgb_clr.append(alpha)
                outer_shdw.append(srgb_clr)
                effect_lst.append(outer_shdw)
                sp_pr.append(effect_lst)
        return sh

    def picture(self, s, filename, x, y, w=None, h=None):
        path = ASSETS / filename
        if not path.exists():
            return None
        kwargs = {}
        if w is not None:
            kwargs["width"] = Inches(w)
        if h is not None:
            kwargs["height"] = Inches(h)
        return s.shapes.add_picture(str(path), Inches(x), Inches(y), **kwargs)

    def text(self, s, x, y, w, h, text, size=20, color="ink", bold=False,
             align=PP_ALIGN.LEFT, font=FONT, valign=MSO_ANCHOR.TOP):
        sh = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = sh.text_frame
        tf.clear()
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE
        tf.margin_left = tf.margin_right = Inches(0.015)
        tf.margin_top = tf.margin_bottom = Inches(0.015)
        tf.vertical_anchor = valign
        for i, line in enumerate(text.split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.space_before = Pt(0)
            p.space_after = Pt(2)
            p.line_spacing = 1.08
            run = p.add_run()
            run.text = line
            run.font.name = font
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = rgb(color)
        return sh

    def bullet_row(self, s, x, y, w, text, accent="blue", fill="white", size=17, h=.48,
                   outlined=True):
        if outlined:
            self.rect(s, x, y, w, h, fill=fill, line=accent, rounded=True)
        self.rect(s, x + .12, y + (h - .10) / 2, .10, .10, fill=accent, line=None, rounded=False)
        self.text(s, x + .34, y + .07, w - .46, h - .10, text, size=size, color="ink")

    def node(self, s, x, y, w, h, title, body="", accent="blue", fill="white",
             title_size=20, body_size=16):
        self.rect(s, x, y, w, h, fill=fill, line=accent, rounded=True, shadow=True)
        self.rect(s, x, y, .055, h, fill=accent, line=None, rounded=False)
        self.text(s, x + .20, y + .10, w - .36, .36, title,
                  size=title_size, bold=True)
        if body:
            self.text(s, x + .20, y + .48, w - .34, max(h - .50, .30), body, size=body_size,
                      color="muted")

    def arrow(self, s, points, color="muted", dashed=False, both=False):
        for i, ((x1, y1), (x2, y2)) in enumerate(zip(points, points[1:])):
            sh = s.shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2)
            )
            style = sh._element.find(qn("p:style"))
            if style is not None:
                sh._element.remove(style)
            sh.line.color.rgb = rgb(color)
            sh.line.width = Pt(1.7)
            ln = sh.line._get_or_add_ln()
            if dashed:
                dash = OxmlElement("a:prstDash")
                dash.set("val", "dash")
                ln.append(dash)
            if i == len(points) - 2:
                head = OxmlElement("a:tailEnd")
                head.set("type", "triangle")
                head.set("w", "sm")
                head.set("len", "sm")
                ln.append(head)
            if both and i == 0:
                tail = OxmlElement("a:headEnd")
                tail.set("type", "triangle")
                tail.set("w", "sm")
                tail.set("len", "sm")
                ln.append(tail)

    def device_cluster(self, s, x, y, scale=1.0, phone=True, laptop=True, tablet=False):
        """Template-1 inspired device composition for the hero and process pages."""
        if laptop:
            self.picture(s, "laptop.png", x + .75 * scale, y + .70 * scale,
                         w=5.25 * scale)
        if tablet:
            self.picture(s, "tablet.png", x + .28 * scale, y + .25 * scale,
                         h=3.20 * scale)
        if phone:
            self.picture(s, "phone.png", x + .25 * scale, y + .15 * scale,
                         h=3.50 * scale)

    def new_slide(self, title, subtitle, refs, notes):
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        bg = self.picture(s, "template2_background.png", 0, 0, w=16, h=9)
        if bg is None:
            s.background.fill.solid()
            s.background.fill.fore_color.rgb = rgb("bg")
        # Template-2 style navigation line and compact metadata.
        self.text(s, .72, .27, 2.8, .22, "CARESteps  /  ARCHITECTURE", size=9,
                  color="muted", bold=True)
        self.rect(s, 2.55, .38, 10.35, .012, fill="line", line=None, rounded=False)
        self.text(s, 13.60, .27, 1.65, .22, "16 OCT 2026", size=9,
                  color="muted", align=PP_ALIGN.RIGHT)
        self.text(s, .72, .67, 14.35, .55, title, size=31, bold=True)
        self.text(s, .75, 1.27, 13.9, .42, subtitle, size=15.5, color="muted")
        self.rect(s, .75, 8.34, 14.5, .012, fill="line", line=None, rounded=False)
        self.text(s, .75, 8.48, 2.7, .20, "CareSteps  |  Healthcare Challenge 2", size=9, color="muted")
        self.text(s, 3.60, 8.48, 9.7, .20, refs, size=9, color="muted")
        self.text(s, 14.18, 8.45, 1.05, .25, f"{len(self.prs.slides):02d} / {TOTAL_SLIDES:02d}",
                  size=10, color="muted", align=PP_ALIGN.RIGHT)
        s.notes_slide.notes_text_frame.text = notes
        return s

    def banner(self, s, text, y=7.62, fill="teal_bg", color="teal", size=16):
        self.rect(s, .75, y, 14.5, .49, fill=fill, line=None, rounded=True)
        self.rect(s, .93, y + .17, .09, .15, fill=color, line=None, rounded=False)
        self.text(s, 1.16, y + .09, 13.80, .31, text, size=size, color=color)

    def cover(self):
        s = self.new_slide(
            "", "", "Handbook pp. 35, 37 | Source review: 16 October 2026",
            "CareSteps architecture submission. Healthcare Challenge Statement 2: AI Healthier Every Day. "
            "The deck is a source-checked prototype overview using simulated data."
        )
        self.text(s, .74, .78, 7.4, .30, "TENCENT CLOUD AI SINGAPORE HACKATHON 2026", size=12,
                  color="blue", bold=True)
        self.text(s, .72, 1.34, 7.5, .84, "CareSteps", size=48, bold=True)
        self.text(s, .75, 2.32, 7.3, 1.12, "Architecture &\nTrust Boundaries", size=31, bold=True,
                  color="purple")
        self.text(s, .76, 3.68, 6.65, .70,
                  "A safety-first self-care companion for older adults\nmanaging blood pressure.",
                  size=19, color="muted")
        self.text(s, .77, 4.66, 6.1, .35,
                  "Local application  •  Optional model  •  Human confirmation", size=14, color="blue", bold=True)
        metrics = [("3", "ordered safety gates"), (str(len(self.evidence["tool_names"])), "model-facing tools"),
                   (str(len(self.evidence["tables"])), "SQLite tables")]
        for i, (n, label) in enumerate(metrics):
            x = .76 + i * 2.14
            self.rect(s, x, 5.45, 1.85, 1.02, fill="white", line="line", rounded=True, shadow=True)
            self.text(s, x + .17, 5.56, 1.45, .52, n, size=28, color="blue", bold=True)
            self.text(s, x + .17, 6.07, 1.50, .22, label, size=11, color="muted")
        self.picture(s, "laptop_screen.png", 9.68, 2.47, w=3.18, h=1.80)
        self.device_cluster(s, 8.62, 1.86, scale=.78, phone=False, laptop=True)
        self.picture(s, "purple_blob.png", 12.20, .93, w=2.65)
        self.picture(s, "phone.png", 8.82, 1.95, h=2.72)
        self.node(s, 9.28, 6.00, 5.55, .84, "One local source of truth",
                  "Routes, safety, tools and SQLite stay together.", accent="teal", fill="teal_bg",
                  title_size=18, body_size=14)
        self.banner(s, "Healthcare Challenge 2  |  AI Healthier Every Day  |  Competition prototype", y=7.62,
                    fill="blue_bg", color="blue", size=15)

    def system(self):
        s = self.new_slide(
            "System Architecture",
            "A local FastAPI application owns decisions, validation and storage; the model is optional.",
            "app/main.py | app/routes/api.py | app/llm/orchestrator.py | app/repository.py",
            "Solid arrows represent local flow. Dashed arrows cross the optional model or content boundary. "
            "The three chat safety gates run before the orchestrator; SQLite is local to the application host."
        )
        # Browser and optional services frame the central application process.
        self.node(s, .72, 2.18, 2.35, 1.02, "Browser UI", "Jinja + JS + CSS", accent="blue",
                  title_size=19, body_size=14)
        self.arrow(s, [(3.10, 2.69), (3.62, 2.69)], color="blue", both=True)
        self.rect(s, 3.62, 1.82, 8.35, 5.65, fill="white", line="blue", rounded=True)
        self.text(s, 3.90, 2.02, 7.65, .25, "APPLICATION HOST  /  FastAPI + Python", size=12,
                  color="blue", bold=True)
        self.node(s, 3.92, 2.45, 2.28, .86, "Routes", "Forms + /api/chat", accent="blue",
                  title_size=18, body_size=13)
        self.node(s, 6.55, 2.45, 2.55, .86, "Safety router", "3 ordered gates",
                  accent="red", fill="red_bg", title_size=18, body_size=13)
        self.node(s, 9.47, 2.45, 2.17, .86, "Orchestrator", "Live loop / fallback", accent="teal",
                  title_size=18, body_size=13)
        self.arrow(s, [(6.23, 2.88), (6.50, 2.88)], color="blue")
        self.arrow(s, [(9.12, 2.88), (9.43, 2.88)], color="red")
        self.node(s, 3.92, 3.78, 2.28, .86, "Output check", "Live prose + numbers", accent="blue",
                  title_size=18, body_size=13)
        self.node(s, 6.55, 3.78, 2.55, .86, "Tools + statistics", "10 named contracts", accent="teal",
                  title_size=18, body_size=13)
        self.node(s, 9.47, 3.78, 2.17, .86, "Repository", "Validated SQL", accent="teal",
                  title_size=18, body_size=13)
        self.arrow(s, [(10.55, 3.34), (10.55, 3.51), (7.82, 3.51), (7.82, 3.74)], color="teal")
        self.arrow(s, [(9.14, 4.21), (9.43, 4.21)], color="teal")
        self.arrow(s, [(6.50, 4.21), (6.23, 4.21)], color="blue")
        self.node(s, 6.55, 5.25, 2.55, .86, "SQLite", "Records + audit", accent="blue",
                  fill="blue_bg", title_size=18, body_size=13)
        self.arrow(s, [(10.55, 4.67), (10.55, 4.98), (7.82, 4.98), (7.82, 5.20)], color="blue", both=True)
        self.node(s, 9.47, 5.25, 2.17, .86, "Health content", "Source-linked JSON", accent="amber",
                  fill="amber_bg", title_size=17, body_size=13)
        self.arrow(s, [(9.43, 5.68), (9.14, 5.68)], color="amber", dashed=True)
        self.node(s, 12.45, 2.46, 2.82, .86, "External model", "OpenAI-compatible endpoint", accent="amber",
                  fill="amber_bg", title_size=18, body_size=13)
        self.arrow(s, [(11.66, 2.88), (12.40, 2.88)], color="amber", dashed=True, both=True)
        self.text(s, 12.44, 3.54, 2.75, .70, "Context + tool results out\nProse + tool requests in", size=13,
                  color="amber")
        self.banner(s, "Safety can return early  •  Forms use server validation  •  Model availability never owns storage", y=7.62,
                    fill="teal_bg", color="teal", size=15)

    def trust(self):
        s = self.new_slide(
            "Trust Boundaries",
            "Every model request is re-validated; browser, model and imported content have limited authority.",
            "app/routes/deps.py | app/tools/handlers.py | app/content_loader.py | app/db.py",
            "Four zones separate user device, trusted application, local storage and external inputs. "
            "The model has no database credential, arbitrary SQL tool or confirm_draft contract. "
            "The signed cookie provides integrity, not production authentication."
        )
        zones = [
            (.72, "01  USER DEVICE", "red", "red_bg", "Browser", "Untrusted forms + chat\nReadable signed cookie"),
            (4.40, "02  TRUSTED APPLICATION", "teal", "teal_bg", "Input + safety", "Route, validate, decide\nScope user + session"),
            (8.10, "03  LOCAL STORAGE", "blue", "blue_bg", "SQLite + audit", "Records, sources\nRedacted audit trail"),
            (11.80, "04  EXTERNAL INPUTS", "amber", "amber_bg", "Model + education", "Minimal context out\nSeed-time content checks"),
        ]
        for x, label, accent, fill, title, body in zones:
            self.rect(s, x, 2.00, 3.45, 4.95, fill=fill, line=accent, dashed=True, rounded=True)
            self.text(s, x + .21, 2.20, 3.0, .33, label, size=13, color=accent, bold=True)
            self.node(s, x + .23, 3.04, 2.98, 1.10, title, body, accent=accent, fill="white",
                      title_size=20, body_size=14)
        self.arrow(s, [(3.96, 3.60), (4.34, 3.60)], color="red")
        self.arrow(s, [(7.64, 3.60), (8.04, 3.60)], color="teal")
        self.arrow(s, [(11.34, 3.60), (11.74, 3.60)], color="blue", dashed=True)
        self.bullet_row(s, 4.64, 4.70, 2.98, "Server owns user_id", accent="teal", fill="white", size=13, h=.46)
        self.bullet_row(s, 4.64, 5.30, 2.98, "Tools cannot issue SQL", accent="teal", fill="white", size=13, h=.46)
        self.bullet_row(s, 8.34, 4.70, 2.98, "No encryption at rest", accent="blue", fill="white", size=13, h=.46)
        self.bullet_row(s, 8.34, 5.30, 2.98, "Corrections preserve history", accent="blue", fill="white", size=13, h=.46)
        self.bullet_row(s, 12.04, 4.70, 2.98, "Endpoint is optional", accent="amber", fill="white", size=13, h=.46)
        self.bullet_row(s, 12.04, 5.30, 2.98, "Content has source metadata", accent="amber", fill="white", size=13, h=.46)
        self.banner(s, "Prototype boundary: shared demo profile, local HTTP and readable cookie state still need production hardening.", y=7.62,
                    fill="red_bg", color="red", size=14)

    def safety(self):
        s = self.new_slide(
            "Safety Gates Run Before the Model",
            "The first decisive verdict ends the turn; model instructions cannot bypass this ordering.",
            "app/safety/__init__.py: route | app/llm/orchestrator.py: run_turn",
            "route() evaluates red flags, boundaries and clarification in order. emergency, urgent_advice, "
            "refuse and clarify all block model access. Detection uses authored patterns and context; it is not a clinical diagnostic system."
        )
        self.text(s, .76, 1.88, 5.8, .34, "FIXED ORDER  /  ONE MATCH CAN END THE TURN", size=13,
                  color="blue", bold=True)
        items = [
            (2.35, "01  Red flags", "Symptoms + reading context", "Emergency / urgent guidance", "red", "red_bg"),
            (3.77, "02  Boundaries", "Dose changes or unclear medicine", "Refuse + redirect", "amber", "amber_bg"),
            (5.19, "03  Clarification", "Missing values or intent", "Ask for details", "blue", "blue_bg"),
        ]
        for i, (y, title, body, out, accent, fill) in enumerate(items):
            self.node(s, .76, y, 4.92, .92, title, body, accent=accent, fill=fill,
                      title_size=19, body_size=14)
            self.arrow(s, [(5.75, y + .46), (6.34, y + .46)], color=accent)
            self.text(s, 5.80, y + .12, .76, .20, "match", size=10, color=accent, bold=True)
            self.node(s, 6.55, y, 4.22, .92, out, "Fixed response; no model call", accent=accent,
                      fill="white", title_size=19, body_size=14)
            if i < 2:
                self.arrow(s, [(3.20, y + .95), (3.20, y + 1.30)], color="teal")
                self.text(s, 3.38, y + 1.02, .9, .18, "otherwise", size=11, color="teal")
        self.rect(s, 11.25, 2.35, 3.92, 3.76, fill="white", line="blue", rounded=True, shadow=True)
        self.text(s, 11.52, 2.62, 3.28, .32, "WHEN ALL THREE ALLOW", size=13, color="blue", bold=True)
        self.text(s, 11.52, 3.24, 3.24, 1.48,
                  "Continue to:\n• live model tools\n• rule-based degraded support", size=18, color="ink")
        self.text(s, 11.52, 4.94, 3.22, .72,
                  "Priority is deterministic. Detection remains limited to authored rules.", size=14, color="muted")
        self.banner(s, "Red flags  >  boundaries  >  clarification  |  Safety is evaluated before the orchestrator.", y=7.62,
                    fill="teal_bg", color="teal", size=15)

    def tools(self):
        s = self.new_slide(
            "Tool Calling & Human Confirmation",
            "The server owns identity, argument checks and database operations; the model only requests named tools.",
            "app/tools/contracts.py | app/tools/handlers.py | app/routes/api.py | app/stats.py",
            "The read example uses the real get_period_stats tool with days=7. user_id comes from ToolContext. "
            "Readings and medication reports stage a draft, then a user action confirms the write. "
            "record_barrier, add_question and set_reminder_preference are scoped direct-write exceptions."
        )
        self.text(s, .76, 1.86, 1.95, .32, "READ / COMPUTE", size=13, color="blue", bold=True)
        self.text(s, 2.86, 1.85, 8.15, .34, '"What was my average blood pressure this week?"', size=18,
                  color="blue", bold=True)
        read = [("Safety", "Gates pass"), ("Request", "get_period_stats\n{days: 7}"),
                ("Validate", "Schema + context\nuser_id server-owned"), ("Compute", "repo + stats.py\nwindow, gaps, n"),
                ("Answer", "Facts -> prose\nLive output check")]
        for i, (t, b) in enumerate(read):
            x = .76 + i * 2.96
            self.node(s, x, 2.38, 2.53, 1.15, t, b, accent="blue", title_size=17, body_size=13)
            if i < 4:
                self.arrow(s, [(x + 2.57, 2.95), (x + 2.90, 2.95)], color="blue")
        self.text(s, .76, 4.23, 14.1, .32, "PREPARE / CONFIRM", size=13, color="teal", bold=True)
        self.text(s, 2.68, 4.22, 8.8, .34, "Readings and medication reports", size=18, color="teal", bold=True)
        write = [("Prepare", "Validate + stage\nNo health record"), ("Preview", "Show draft values\nUser sees before save"),
                 ("Confirm", "POST /api/chat/confirm\nUI-only handler"), ("Persist", "Repository saves\nDuplicate protection")]
        for i, (t, b) in enumerate(write):
            x = .76 + i * 3.75
            self.node(s, x, 4.78, 3.14, 1.22, t, b, accent="teal", title_size=18, body_size=14)
            if i < 3:
                self.arrow(s, [(x + 3.18, 5.39), (x + 3.68, 5.39)], color="teal")
        self.picture(s, "phone.png", 12.83, 6.12, h=1.30)
        self.banner(s, "10 model-facing contracts  |  Human confirmation protects staged health records  |  Scoped direct writes stay explicit", y=7.62,
                    fill="amber_bg", color="amber", size=14)

    def fallback(self):
        s = self.new_slide(
            "Degraded Mode & Partial Failure",
            "Core workflows remain available when the optional model is missing, unavailable or interrupted.",
            "app/config.py | app/llm/provider.py | app/llm/orchestrator.py",
            "Missing configuration or forced degraded mode uses _degraded_turn. A provider failure before tools also degrades. "
            "If tools already ran, the fallback text can still return mode live and is checked. Completed writes are not rolled back."
        )
        paths = [
            (.76, "No live endpoint", "Unset configuration\nor forced degraded", "Rule-based reply", "mode = degraded", "amber", "amber_bg"),
            (5.78, "Call fails before tools", "Timeout or unreadable\nprovider response", "Rule-based reply", "mode = degraded", "amber", "amber_bg"),
            (10.80, "Tools already ran", "Later failure or\nround budget exhausted", "Tool-result fallback", "mode = live + check", "blue", "blue_bg"),
        ]
        for x, title, body, out, detail, accent, fill in paths:
            self.node(s, x, 2.40, 4.46, 1.25, title, body, accent=accent, title_size=19, body_size=15)
            self.arrow(s, [(x + 2.23, 3.70), (x + 2.23, 4.15)], color=accent)
            self.node(s, x, 4.22, 4.46, 1.24, out, detail, accent=accent, fill=fill,
                      title_size=20, body_size=15)
        self.text(s, .77, 6.05, 14.3, .32, "LOCAL WORKFLOWS REMAIN AVAILABLE", size=13, color="teal", bold=True)
        for i, label in enumerate(["BP entry forms", "Trends + statistics", "Medicine reports", "Visit summary"]):
            self.bullet_row(s, .76 + i * 3.72, 6.55, 3.28, label, accent="teal", fill="teal_bg", size=14, h=.50)
        self.banner(s, "A later model failure does not undo completed tool writes; the application records actual outcomes.", y=7.62,
                    fill="soft", color="ink", size=15)

    def data(self):
        s = self.new_slide(
            "Data Model & Provenance",
            "13 SQLite tables grouped by responsibility; the repository owns request-path database access.",
            "app/db.py: SCHEMA | app/repository.py: corrections, dedupe and audit",
            "The table count is checked by executing SCHEMA in memory. This is a responsibility map, not a complete ER diagram. "
            "Corrections preserve history through superseded_by; missing reports remain unknown rather than compliant/non-compliant."
        )
        self.node(s, .76, 1.98, 9.65, .88, "user_profile", "Profile, preferences and simulated-data marker",
                  accent="blue", fill="blue_bg", title_size=19, body_size=14)
        groups = [
            (.76, "HEALTH RECORDS", "teal", ["care_plan", "medication_item", "bp_reading", "medication_report"]),
            (5.77, "SUPPORT + PREPARATION", "blue", ["barrier_event", "support_action", "consultation_question", "visit_summary"]),
            (10.78, "KNOWLEDGE + TRACE", "amber", ["education_source", "education_fact", "conversation_message", "audit_event"]),
        ]
        for x, title, accent, names in groups:
            self.rect(s, x, 3.30, 4.45, 3.42, fill="white", line=accent, rounded=True, shadow=True)
            self.text(s, x + .22, 3.52, 3.96, .28, title, size=13, color=accent, bold=True)
            for i, name in enumerate(names):
                y = 4.08 + i * .62
                self.rect(s, x + .22, y, .09, .09, fill=accent, line=None, rounded=False)
                self.text(s, x + .42, y - .06, 3.55, .40, name, size=18, bold=True)
        self.arrow(s, [(3.05, 2.90), (3.05, 3.25)], color="blue")
        self.arrow(s, [(8.05, 2.90), (8.05, 3.25)], color="blue")
        self.text(s, .78, 6.96, 14.0, .28, "Preserved corrections  •  Unique dedupe keys  •  Source metadata  •  Audit events", size=14, color="muted")
        self.banner(s, "Patient data is fictional and simulated; source checks do not equal clinical review.", y=7.62,
                    fill="amber_bg", color="amber", size=15)

    def prompt(self):
        s = self.new_slide(
            "Prompting, Grounding & Traceability",
            "The prompt sets tone and limits; deterministic code controls routing, tools, calculations and checks.",
            "app/llm/prompts.py | app/llm/orchestrator.py | app/main.py: /trace",
            "The system prompt is caresteps.system.v3. Context includes profile orientation and the latest 12 messages; tool results are appended. "
            "check_output uses heuristic numeric and phrase checks. /trace exposes contracts, rule metadata, provider status, source IDs and audit events."
        )
        flow = [("System prompt", "Role, tone, limits\ncaresteps.system.v3"), ("Minimal context", "Profile + latest\n12 messages"),
                ("Bounded tool loop", "Named operations\nDefault: 4 rounds"), ("Live output check", "Known numbers + phrases\nReplace on failure")]
        for i, (t, b) in enumerate(flow):
            x = .76 + i * 3.77
            self.node(s, x, 2.12, 3.10, 1.33, t, b, accent="blue", title_size=18, body_size=14)
            if i < 3:
                self.arrow(s, [(x + 3.14, 2.78), (x + 3.70, 2.78)], color="blue")
        self.rect(s, .76, 4.16, 6.78, 2.30, fill="white", line="blue", rounded=True, shadow=True)
        self.text(s, 1.02, 4.42, 6.22, .28, "PROMPT POLICY SUMMARY", size=13, color="blue", bold=True)
        for i, t in enumerate(["Numbers: use tool results", "Education: retrieve, then cite", "Unknowns: ask or defer", "Medication changes: refuse"]):
            self.bullet_row(s, 1.02, 4.90 + i * .39, 6.18, t, accent="blue", fill="blue_bg", size=13, h=.36, outlined=False)
        self.rect(s, 8.00, 4.16, 7.24, 2.30, fill="teal_bg", line="teal", rounded=True, shadow=True)
        self.text(s, 8.26, 4.42, 6.60, .28, "INSPECTABLE AT /trace", size=13, color="teal", bold=True)
        for i, t in enumerate(["Active contracts + provider status", "Rule version + source IDs", "Prompt version + fingerprint", "Tool outcomes + response mode"]):
            self.bullet_row(s, 8.26, 4.90 + i * .39, 6.62, t, accent="teal", fill="white", size=13, h=.36, outlined=False)
        self.banner(s, "Output checks are grounding heuristics; they do not provide clinical validation.", y=7.62,
                    fill="amber_bg", color="amber", size=15)

    def tradeoffs(self):
        count = self.evidence["automated_tests_passed"]
        s = self.new_slide(
            "Key Design Trade-offs & Prototype Limits",
            "Each constraint makes the local prototype easier to inspect and leaves a clear production task.",
            "Handbook p. 35 | docs/decisions.md | Source assertions checked against current app/ code",
            f"Automated validation recorded {count} passed tests on 16 October 2026. Tests do not establish clinical safety, accessibility conformance or live model performance. "
            "Known limits include no production login, no encryption at rest, no atomic whole-turn transaction and no health-system integration."
        )
        cols = [("CHOICE", .76, 4.05, "blue"), ("WHY IT HELPS", 4.92, 4.55, "teal"), ("COST / NEXT STEP", 9.55, 5.70, "purple")]
        for title, x, w, accent in cols:
            self.rect(s, x, 1.98, w, .47, fill=accent, line=None, rounded=True)
            self.text(s, x + .18, 2.10, w - .36, .22, title, size=12, color="white", bold=True)
        rows = [
            ("Deterministic gates first", "Immediate, inspectable safety routing", "Expand clinical review + rule coverage"),
            ("SQLite + local browser assets", "One-process, reproducible demo", "Add auth, encryption and scaling"),
            ("Scoped tools + confirm flow", "Validated operations + visible drafts", "Add atomic turn boundaries"),
            ("Optional model endpoint", "Core workflows survive downtime", "Verify live provider in production")
        ]
        for i, row in enumerate(rows):
            y = 2.58 + i * .84
            fill = "white" if i % 2 == 0 else "soft"
            for (_, x, w, _), value in zip(cols, row):
                self.rect(s, x, y, w, .75, fill=fill, line=None, rounded=False)
                self.text(s, x + .18, y + .15, w - .36, .46, value, size=14,
                          bold=(x == .76), color="ink" if x != 9.55 else "muted")
        self.rect(s, .76, 6.35, 14.49, .57, fill="teal_bg", line=None, rounded=True)
        self.text(s, .98, 6.50, 14.05, .25,
                  f"{count} automated tests passed  |  10 model tools  |  13 tables  |  Source-linked rules and education",
                  size=16, color="teal", bold=True)
        self.banner(s, "Simulated data  |  No clinical validation  |  No health-system integration  |  No accessibility conformance audit", y=7.62,
                    fill="amber_bg", color="amber", size=14)

    def build(self):
        for builder in [self.cover, self.system, self.trust, self.safety, self.tools,
                        self.fallback, self.data, self.prompt, self.tradeoffs]:
            builder()
        for n, slide in enumerate(self.prs.slides, 1):
            for sh in slide.shapes:
                if sh.left < 0 or sh.top < 0:
                    raise ValueError(f"Slide {n}: negative shape origin")
                if sh.left + sh.width > self.prs.slide_width + 10:
                    raise ValueError(f"Slide {n}: shape exceeds right edge")
                if sh.top + sh.height > self.prs.slide_height + 10:
                    raise ValueError(f"Slide {n}: shape exceeds bottom edge")
        path = OUT / f"{STEM}.pptx"
        self.prs.save(path)
        notes = ["# CareSteps Architecture - Speaker Notes\n"]
        for n, slide in enumerate(self.prs.slides, 1):
            title = next((sh.text for sh in slide.shapes
                          if sh.has_text_frame and sh.text.strip()), "CareSteps")
            notes.append(f"## {n:02d}. {title}\n\n{slide.notes_slide.notes_text_frame.text}\n")
        (OUT / "SPEAKER_NOTES.md").write_text("\n".join(notes), encoding="utf-8")
        (OUT / "source-verification.json").write_text(
            json.dumps(self.evidence, indent=2) + "\n", encoding="utf-8"
        )
        return path


def render(path):
    if not shutil.which("soffice") or not shutil.which("pdftoppm"):
        raise RuntimeError("PDF/PNG export needs soffice and pdftoppm")
    with tempfile.TemporaryDirectory(prefix="caresteps-slides-") as profile:
        subprocess.run([
            "soffice", f"-env:UserInstallation={Path(profile).as_uri()}", "--headless",
            "--convert-to", "pdf:impress_pdf_Export", "--outdir", str(OUT), str(path),
        ], check=True, timeout=90)
    pdf = path.with_suffix(".pdf")
    if not pdf.exists():
        raise RuntimeError("LibreOffice did not produce the PDF")
    previews = OUT / "previews"
    previews.mkdir(exist_ok=True)
    subprocess.run([
        "pdftoppm", "-png", "-scale-to-x", "1920", "-scale-to-y", "1080",
        str(pdf), str(previews / "slide"),
    ], check=True, timeout=90)
    images = sorted(previews.glob("slide-*.png"))
    if len(images) != TOTAL_SLIDES:
        raise RuntimeError(f"Expected {TOTAL_SLIDES} rendered slides, got {len(images)}")
    shutil.copyfile(images[1], OUT / "CareSteps_System_Architecture.png")
    shutil.copyfile(images[2], OUT / "CareSteps_Trust_Boundaries.png")
    from PIL import Image, ImageDraw

    sheet = Image.new("RGB", (1440, 885), "#E4EAED")
    draw = ImageDraw.Draw(sheet)
    for i, image in enumerate(images):
        thumb = Image.open(image).convert("RGB")
        thumb.thumbnail((464, 261), Image.Resampling.LANCZOS)
        x = 8 + (i % 3) * 480
        y = 8 + (i // 3) * 295
        sheet.paste(thumb, (x, y))
        draw.text((x + 5, y + 266), f"{i + 1:02d}", fill="#192F35")
    sheet.save(OUT / "CareSteps_Architecture_Overview.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render", action="store_true", help="Also export PDF and 1080p PNGs")
    parser.add_argument("--test-count", type=int, required=True,
                        help="Count from a completed pytest run; do not infer or invent")
    args = parser.parse_args()
    evidence = inspect_sources(args.test_count)
    if len(evidence["tool_names"]) != 10 or len(evidence["tables"]) != 13:
        raise RuntimeError("Source contracts changed: review slide labels before regenerating")
    path = Deck(evidence).build()
    if args.render:
        render(path)
    print(f"Built {TOTAL_SLIDES} editable slides: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
