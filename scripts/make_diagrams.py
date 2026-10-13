"""Render the architecture diagrams from the Mermaid blocks in docs/architecture.md.

The handbook's Healthcare track asks for an "Architecture Diagram - architecture,
trust-boundary diagram, key design trade-offs". Those two diagrams already exist as
Mermaid source inside ``docs/architecture.md``, so this script does not draw anything:
it extracts the blocks and renders them, which keeps the picture and the prose from
drifting apart. Edit the diagram in the document, re-run this, and both stay honest.

Requires ``mmdc`` (Mermaid CLI) and a Chrome/Chromium it can drive. Unlike
``make_cover.py`` - which is pure Pillow and needs nothing - this one has a real
external dependency, so it degrades to a clear message rather than a stack trace.

  npm install -g @mermaid-js/mermaid-cli
  # or, without installing:  npx --yes @mermaid-js/mermaid-cli@11 ...

If Chromium is missing or will not start, point PUPPETEER_EXECUTABLE_PATH at a
chrome-headless-shell binary and this script will pass it through.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "architecture.md"
OUT_DIR = ROOT / "submission" / "diagrams"

# Block index -> output name. Order matters: it is the order they appear in the doc.
NAMES = ["architecture-system", "architecture-trust-boundaries"]

# Chromium in a container or under WSL usually needs these. Harmless elsewhere.
PUPPETEER_ARGS = {
    "args": ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
}


def extract_blocks() -> list[str]:
    text = SOURCE.read_text(encoding="utf-8")
    return re.findall(r"```mermaid\n(.*?)```", text, re.S)


def find_mmdc() -> list[str] | None:
    if shutil.which("mmdc"):
        return ["mmdc"]
    if shutil.which("npx"):
        return ["npx", "--yes", "@mermaid-js/mermaid-cli@11"]
    return None


def _explain_failure(name: str, proc: subprocess.CompletedProcess) -> int:
    """Turn a renderer crash into an instruction, not a stack trace.

    The Mermaid CLI's most common failure by far is that it cannot start a browser,
    and its default output for that is twenty lines of Puppeteer internals ending in
    a ChromeLauncher frame. A stack trace tells the reader nothing they can act on,
    so the known cases are recognised and named, and the raw output is kept behind
    an environment variable for the case where it is genuinely needed.
    """
    raw = ((proc.stderr or "") + (proc.stdout or "")).strip()

    print(f"  failed to render {name}.")

    if "Could not find chrome" in raw or "chrome-headless-shell" in raw:
        print("\n  Mermaid CLI could not find a browser to drive.")
        print("  Either install one:   npx puppeteer browsers install chrome-headless-shell")
        print("  or point at an existing one:")
        print("      export PUPPETEER_EXECUTABLE_PATH=/path/to/chrome-headless-shell")
        print("  (extract the chrome-for-testing zip if the installer needs an archiver")
        print("   this machine does not have).")
    elif "no zip archiver" in raw or "Extraction failed" in raw:
        print("\n  The browser download could not be unpacked: no archiver is available.")
        print("  Install 'unzip', or download and extract the chrome-for-testing zip")
        print("  yourself and set PUPPETEER_EXECUTABLE_PATH to the binary.")
    elif "Failed to launch" in raw or "ChromeLauncher" in raw or "BrowserLauncher" in raw:
        print("\n  A browser was found but would not start.")
        print("  In a container or under WSL this is usually the sandbox. Try:")
        print("      export PUPPETEER_EXECUTABLE_PATH=/path/to/chrome-headless-shell")
        print("  and re-run; this script already passes --no-sandbox to the renderer.")
    else:
        print("\n  The renderer failed for a reason this script does not recognise.")
        print("  Re-run with MERMAID_DEBUG=1 to see its raw output.")

    if os.environ.get("MERMAID_DEBUG"):
        print("\n  --- renderer output ---")
        for line in raw.splitlines()[-30:]:
            print(f"  {line}")

    return 1


def main() -> int:
    blocks = extract_blocks()
    if len(blocks) != len(NAMES):
        print(
            f"expected {len(NAMES)} mermaid blocks in {SOURCE.name}, found {len(blocks)}.\n"
            "If a diagram was added or removed, update NAMES in this script to match."
        )
        return 1

    mmdc = find_mmdc()
    if mmdc is None:
        print("Neither 'mmdc' nor 'npx' is available, so the diagrams cannot be rendered.")
        print("Install one:  npm install -g @mermaid-js/mermaid-cli")
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        config = tmpdir / "puppeteer.json"
        config.write_text(json.dumps(PUPPETEER_ARGS), encoding="utf-8")

        env = dict(os.environ)
        note = ""
        if not env.get("PUPPETEER_EXECUTABLE_PATH") and shutil.which("chrome-headless-shell"):
            env["PUPPETEER_EXECUTABLE_PATH"] = shutil.which("chrome-headless-shell")
            note = f" (using {env['PUPPETEER_EXECUTABLE_PATH']})"

        for name, block in zip(NAMES, blocks):
            src = tmpdir / f"{name}.mmd"
            dst = OUT_DIR / f"{name}.png"
            src.write_text(block, encoding="utf-8")

            print(f"rendering {name}{note} ...")
            proc = subprocess.run(
                [*mmdc, "-i", str(src), "-o", str(dst), "-p", str(config),
                 "-b", "white", "-s", "3"],
                capture_output=True, text=True, env=env,
            )
            if proc.returncode != 0 or not dst.exists():
                return _explain_failure(name, proc)

            from PIL import Image

            with Image.open(dst) as im:
                print(f"  {dst.relative_to(ROOT)}  {im.size[0]}x{im.size[1]}  "
                      f"{dst.stat().st_size // 1024} KB")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
