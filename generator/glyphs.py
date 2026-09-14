"""Glyph coverage bitmaps: build them once, then load them forever.

The bitmaps are committed so the portrait is byte-identical on any machine.
Rendering them at build time would tie the portrait to whatever monospace font
the host happens to have, and CI would disagree with a local build.

Build with:  python -m generator.glyphs --build
"""
import base64
import json
import pathlib
import sys

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw, ImageFont

from generator import config

_cache: tuple[tuple[str, ...], npt.NDArray[np.float64]] | None = None


def _pick_font() -> str:
    for path in config.GLYPH_FONT_CANDIDATES:
        if pathlib.Path(path).exists():
            return path
    raise RuntimeError(
        "No monospace font found. Add one to config.GLYPH_FONT_CANDIDATES:\n  "
        + "\n  ".join(config.GLYPH_FONT_CANDIDATES))


def _render_glyph(font: ImageFont.FreeTypeFont, char: str,
                  cell: tuple[int, int]) -> npt.NDArray[np.uint8]:
    """Ink coverage of one character in a cell-sized box, as 0..255 bytes."""
    _, height = cell
    ascent, descent = font.getmetrics()
    # Centre the glyph's ascent+descent band inside the cell so the bitmap
    # describes where the ink actually lands relative to the character origin.
    top = (height - (ascent + descent)) / 2.0

    image = Image.new("L", cell, 0)
    ImageDraw.Draw(image).text((0, top), char, font=font, fill=255)
    return np.asarray(image, dtype=np.uint8)


def build_bitmap_file(path: pathlib.Path | None = None) -> pathlib.Path:
    font_path = _pick_font()
    font = ImageFont.truetype(font_path, config.GLYPH_FONT_SIZE)
    cell = config.GLYPH_CELL

    glyphs: dict[str, str] = {}
    for char in config.GLYPH_CHARS:
        raw = _render_glyph(font, char, cell)
        glyphs[char] = base64.b64encode(raw.tobytes()).decode("ascii")

    doc = {
        "_comment": (
            "Pre-rendered glyph coverage bitmaps, committed so the portrait is "
            "byte-identical on any machine. Regenerate with "
            "`python -m generator.glyphs --build` only when changing "
            "GLYPH_FONT_SIZE, GLYPH_CELL or GLYPH_CHARS."
        ),
        "font": pathlib.Path(font_path).name,
        "size": config.GLYPH_FONT_SIZE,
        "cell": list(cell),
        "order": config.GLYPH_CHARS,
        "glyphs": glyphs,
    }

    target = path or pathlib.Path(__file__).with_name(config.GLYPH_BITMAP_FILE)
    target.write_text(json.dumps(doc, indent=1, ensure_ascii=False), encoding="utf-8")
    return target


def _load() -> tuple[tuple[str, ...], npt.NDArray[np.float64]]:
    global _cache
    if _cache is None:
        path = pathlib.Path(__file__).with_name(config.GLYPH_BITMAP_FILE)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as error:
            raise RuntimeError(
                f"Cannot read glyph bitmaps at {path}: {error}\n"
                f"Generate them first: python -m generator.glyphs --build") from error

        width, height = doc["cell"]
        if [width, height] != list(config.GLYPH_CELL):
            raise RuntimeError(
                f"Glyph bitmap cell {width}x{height} does not match "
                f"config.GLYPH_CELL {config.GLYPH_CELL}; rebuild the bitmaps")

        order = doc["order"]
        if order != config.GLYPH_CHARS:
            raise RuntimeError(
                "glyph_bitmaps.json was built from a different GLYPH_CHARS; rebuild the bitmaps")

        chars: list[str] = []
        rows: list[npt.NDArray[np.uint8]] = []
        for char in order:
            encoded = doc["glyphs"].get(char)
            if encoded is None:
                raise RuntimeError(f"glyph_bitmaps.json is missing {char!r}")
            raw = base64.b64decode(encoded)
            if len(raw) != width * height:
                raise RuntimeError(
                    f"Glyph {char!r} has {len(raw)} bytes, expected {width * height}")
            chars.append(char)
            rows.append(np.frombuffer(raw, dtype=np.uint8))

        if not chars:
            raise RuntimeError("Glyph bitmap file contains no glyphs")
        _cache = (tuple(chars), np.stack(rows).astype(np.float64) / 255.0)
    return _cache


def load() -> tuple[tuple[str, ...], npt.NDArray[np.float64]]:
    return _load()


def main(argv: list[str]) -> int:
    if "--build" not in argv:
        print((__doc__ or "").strip())
        return 0
    target = build_bitmap_file()
    chars, bitmaps = load()
    print(f"Wrote {target} — {len(chars)} glyphs at {bitmaps.shape[1]} sub-pixels per cell")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
