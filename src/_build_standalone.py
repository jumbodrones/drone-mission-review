#!/usr/bin/env python3
"""
_build_standalone.py — Bundle drone-mission-review.html into a single offline-capable file.

Reads:
  - drone-mission-review.html                          (the source app)
  - libs/node_modules/.../*.{js,css}           (the CDN libraries to inline)
  - <sample_index.json>                        (a pre-built sample dataset)

Writes:
  - drone-mission-review-standalone.html               (one file, no external deps)

The bundle:
  1. Replaces every <link rel="stylesheet" href="https://..."> with <style>…inline…</style>.
  2. Replaces every <script src="https://..."></script> with <script>…inline…</script>.
  3. Injects window.SAMPLE_DATASET as a JS constant.
  4. Adds a "Load sample dataset" button to the toolbar that calls the
     existing index.json loader against window.SAMPLE_DATASET.

Run from the build dir (mnt/outputs) where libs/ and sample4/ live, e.g.:
  python3 _build_standalone.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent           # .../drone-mission-review/src
PROJECT_ROOT = HERE.parent                        # .../drone-mission-review

# Project-relative paths so this script keeps working if the project is moved.
SRC_HTML = HERE / "drone-mission-review.html"
OUT_HTML = PROJECT_ROOT / "dist" / "drone-mission-review-standalone.html"

# These two still live outside the project root (build-time scratch space).
# The build script falls back gracefully if either is missing.
LIBS = Path("/sessions/epic-loving-ptolemy/mnt/outputs/libs/node_modules")
# Sample dataset to embed. Built from ~/Documents/Cowork_Playground/DemoData
# via build_index.py — see README for the one-line command.
SAMPLE_JSON = Path("/sessions/epic-loving-ptolemy/mnt/outputs/demo_sample/index.json")

# Map: external URL substring  ->  local file to inline
LIB_MAP_CSS = {
    "leaflet@1.9.4/dist/leaflet.css": LIBS / "leaflet/dist/leaflet.css",
    "leaflet.markercluster@1.5.3/dist/MarkerCluster.css":
        LIBS / "leaflet.markercluster/dist/MarkerCluster.css",
    "leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css":
        LIBS / "leaflet.markercluster/dist/MarkerCluster.Default.css",
}
LIB_MAP_JS = {
    "leaflet@1.9.4/dist/leaflet.js": LIBS / "leaflet/dist/leaflet.js",
    "leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js":
        LIBS / "leaflet.markercluster/dist/leaflet.markercluster.js",
    "exifr@7.1.3/dist/full.umd.js": LIBS / "exifr/dist/full.umd.js",
}


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def inline_link(html: str) -> str:
    pattern = re.compile(r'<link\s+rel="stylesheet"\s+href="([^"]+)"\s*/?>', re.I)
    def repl(m):
        url = m.group(1)
        for sig, path in LIB_MAP_CSS.items():
            if sig in url:
                css = read(path)
                return f"<style>\n/* {sig} */\n{css}\n</style>"
        return m.group(0)
    return pattern.sub(repl, html)


def inline_script_src(html: str) -> str:
    pattern = re.compile(r'<script\s+src="([^"]+)"\s*></script>', re.I)
    def repl(m):
        url = m.group(1)
        for sig, path in LIB_MAP_JS.items():
            if sig in url:
                js = read(path)
                return f"<script>\n/* {sig} */\n{js}\n</script>"
        return m.group(0)
    return pattern.sub(repl, html)


def inject_sample_button(html: str) -> str:
    """Add a "Load sample dataset" button to the toolbar."""
    toolbar_old = '<button id="fitBtn" disabled>Fit to photos</button>'
    toolbar_new = (
        '<button id="sampleBtn">Load sample dataset</button>\n'
        '      <button id="fitBtn" disabled>Fit to photos</button>'
    )
    return html.replace(toolbar_old, toolbar_new, 1)


def inject_sample_handler(html: str, sample_data: dict) -> str:
    """Embed the sample dataset and add a click handler.

    We splice the handler in just before the closing of the main IIFE so it
    has access to the loadFromIndex() function in scope.
    """
    sample_json = json.dumps(sample_data, ensure_ascii=False, separators=(",", ":"))
    # Put the SAMPLE_DATASET in a separate <script> tag so it's a global,
    # then add another small <script> after the main IIFE that wires the button.
    inject = (
        f'\n<script id="sample-dataset" type="application/json">{sample_json}</script>\n'
        '<script>\n'
        '(() => {\n'
        '  const btn = document.getElementById("sampleBtn");\n'
        '  const dataEl = document.getElementById("sample-dataset");\n'
        '  if (!btn || !dataEl) return;\n'
        '  let data = null;\n'
        '  try { data = JSON.parse(dataEl.textContent); } catch(e) { console.error("sample-dataset JSON parse failed", e); return; }\n'
        '  btn.addEventListener("click", () => {\n'
        '    // Re-use the index.json loader path: synthesise a File and feed it to the existing input.\n'
        '    const blob = new Blob([JSON.stringify(data)], {type: "application/json"});\n'
        '    const file = new File([blob], "sample_dataset.json", {type: "application/json"});\n'
        '    const dt = new DataTransfer();\n'
        '    dt.items.add(file);\n'
        '    const input = document.getElementById("indexInput");\n'
        '    input.files = dt.files;\n'
        '    input.dispatchEvent(new Event("change", {bubbles: true}));\n'
        '  });\n'
        '})();\n'
        '</script>\n'
    )
    return html.replace("</body>", inject + "</body>", 1)


def main():
    html = read(SRC_HTML)
    html = inline_link(html)
    html = inline_script_src(html)
    html = inject_sample_button(html)
    sample = json.loads(read(SAMPLE_JSON))
    html = inject_sample_handler(html, sample)

    # Sanity: confirm no external URLs remain in <link> or <script src=>
    leftover_link = re.search(r'<link[^>]+href="https?://', html)
    leftover_script = re.search(r'<script[^>]+src="https?://', html)
    warnings = []
    if leftover_link: warnings.append(f"unresolved <link>: {leftover_link.group(0)[:80]}")
    if leftover_script: warnings.append(f"unresolved <script src>: {leftover_script.group(0)[:80]}")
    for w in warnings:
        sys.stderr.write("WARN: " + w + "\n")

    OUT_HTML.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(html, encoding="utf-8")
    kb = OUT_HTML.stat().st_size / 1024
    print(f"Wrote {OUT_HTML}  ({kb:.1f} KB)")


if __name__ == "__main__":
    main()
