"""Render the checked-in Mermaid sources with the pinned Mermaid CLI.

Uses an existing Chrome/Chromium when available; otherwise Puppeteer may install
its bundled browser. This optional documentation tool is not a runtime dependency.
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--png", action="store_true", help="Also save PNG previews for visual inspection")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    npx = shutil.which("npx.cmd" if os.name == "nt" else "npx")
    if not npx:
        raise SystemExit("Install Node.js (including npx) to render the Mermaid diagrams")
    configured = os.environ.get("CHROME_PATH")
    candidates = [configured] if configured else []
    candidates.extend([
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        shutil.which("chromium"), shutil.which("chromium-browser"), shutil.which("google-chrome"),
    ])
    browser = next((path for path in candidates if path and Path(path).is_file()), None)
    environment = os.environ.copy()
    with tempfile.TemporaryDirectory(prefix="context-memory-diagrams-") as temporary:
        config = Path(temporary) / "puppeteer.json"
        config.write_text(json.dumps({"executablePath": browser} if browser else {}), encoding="utf-8")
        if browser:
            environment["PUPPETEER_SKIP_DOWNLOAD"] = "true"
        for name in ("architecture", "comparison"):
            for extension in (["svg", "png"] if args.png else ["svg"]):
                subprocess.run([
                    npx, "--yes", "--package", "@mermaid-js/mermaid-cli@12.0.0", "mmdc",
                    "-i", str(root / "docs" / f"{name}.mmd"),
                    "-o", str(root / "docs" / f"{name}.{extension}"),
                    "-c", str(root / "docs" / "mermaid-config.json"),
                    "-p", str(config), "-b", "white", "--size", "1600",
                ], check=True, cwd=root, env=environment)


if __name__ == "__main__":
    main()
