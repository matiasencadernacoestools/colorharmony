from pathlib import Path
import json
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "PRESETS"
OUTPUT = ROOT / "presets.json"
EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".bmp"}

files = sorted(
    path.name
    for path in PRESETS.iterdir()
    if path.is_file() and path.suffix.lower() in EXTENSIONS
)

payload = {
    "version": 1,
    "folder": "PRESETS",
    "generatedAt": datetime.now(timezone.utc).isoformat(),
    "files": files,
}

OUTPUT.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

print(f"{len(files)} preset(s) gravado(s) em {OUTPUT}")
