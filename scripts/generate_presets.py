from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import colorsys
import json

from PIL import Image, ImageOps

try:
    import pillow_avif  # noqa: F401
except ImportError:
    pillow_avif = None

ROOT = Path(__file__).resolve().parents[1]
PRESETS = ROOT / "PRESETS"
PRESETS_OUTPUT = ROOT / "presets.json"
COLOR_INDEX_OUTPUT = ROOT / "preset-color-index.json"

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif", ".gif", ".bmp"}
MAX_SIDE = 720
QUANTIZED_COLORS = 192
DISPLAY_COLORS = 12


def rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def rgb_to_hsl(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    r, g, b = (channel / 255 for channel in rgb)
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return round(h * 360, 2), round(s * 100, 2), round(l * 100, 2)


def rgb_distance_squared(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return sum((x - y) ** 2 for x, y in zip(a, b))


def analyse_image(path: Path) -> dict:
    with Image.open(path) as source:
        source.seek(0)
        image = ImageOps.exif_transpose(source).convert("RGBA")

    # Fundo transparente não deve virar uma cor falsa.
    background = Image.new("RGBA", image.size, (255, 255, 255, 255))
    background.alpha_composite(image)
    image = background.convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)

    quantized = image.quantize(
        colors=QUANTIZED_COLORS,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    ).convert("RGB")

    counts = Counter(quantized.getdata())
    total = sum(counts.values()) or 1

    colors = []
    for rgb, count in counts.most_common():
        h, s, l = rgb_to_hsl(rgb)

        # Remove apenas extremos quase absolutos.
        if l < 1 or l > 99.5:
            continue

        colors.append(
            {
                "hex": rgb_to_hex(rgb),
                "r": rgb[0],
                "g": rgb[1],
                "b": rgb[2],
                "h": h,
                "s": s,
                "l": l,
                "count": count,
                "share": round(count / total, 8),
            }
        )

    display = []
    for color in colors:
        rgb = (color["r"], color["g"], color["b"])
        if all(
            rgb_distance_squared(
                rgb,
                (existing["r"], existing["g"], existing["b"]),
            ) > 220
            for existing in display
        ):
            display.append(color)
        if len(display) >= DISPLAY_COLORS:
            break

    return {
        "name": path.name,
        "sha256": sha256(path.read_bytes()).hexdigest(),
        "width": image.width,
        "height": image.height,
        "colors": colors,
        "displayPalette": display,
    }


def main() -> None:
    if not PRESETS.exists():
        raise FileNotFoundError(f"Pasta não encontrada: {PRESETS}")

    files = sorted(
        (
            path
            for path in PRESETS.iterdir()
            if path.is_file() and path.suffix.lower() in EXTENSIONS
        ),
        key=lambda path: path.name.casefold(),
    )

    generated_at = datetime.now(timezone.utc).isoformat()

    presets_payload = {
        "version": 2,
        "folder": "PRESETS",
        "generatedAt": generated_at,
        "files": [path.name for path in files],
    }

    entries = []
    errors = []

    for path in files:
        try:
            entries.append(analyse_image(path))
            print(f"OK: {path.name}")
        except Exception as error:
            errors.append({"name": path.name, "error": str(error)})
            print(f"ERRO: {path.name}: {error}")

    color_payload = {
        "version": 1,
        "folder": "PRESETS",
        "generatedAt": generated_at,
        "presetCount": len(files),
        "indexedCount": len(entries),
        "entries": entries,
        "errors": errors,
    }

    PRESETS_OUTPUT.write_text(
        json.dumps(presets_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    COLOR_INDEX_OUTPUT.write_text(
        json.dumps(color_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"{len(files)} preset(s) listado(s); "
        f"{len(entries)} indexado(s); "
        f"{len(errors)} erro(s)."
    )

    if errors:
        raise RuntimeError(
            "Uma ou mais imagens não puderam ser indexadas. "
            "Consulte os erros acima."
        )


if __name__ == "__main__":
    main()
