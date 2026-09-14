"""Build profile.svg.

    python -m generator.main [--refresh] [--offline]
"""
import pathlib
import sys

from generator import avatar, config, render, stats


def main(argv: list[str]) -> int:
    image = avatar.load_avatar(refresh="--refresh" in argv)
    grid = avatar.build_grid(image)
    data = stats.collect(offline="--offline" in argv)
    svg = render.render(grid, data)

    out = pathlib.Path(config.OUTPUT_PATH)
    out.write_text(svg, encoding="utf-8")
    print(f"Wrote {out} — {len(grid)}x{config.AVATAR_COLS} cells, {out.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
