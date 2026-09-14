"""Dev tool: render the portrait under several parameter sets, side by side.

    python tools/variants.py

Writes cache/variants/*.svg and a contact sheet at cache/variants/sheet.html.
Screenshot the sheet to compare every variant in one image.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from generator import avatar, config, render, stats  # noqa: E402

VARIANTS: dict[str, dict[str, object]] = {
    "a_suppress":        {"BG_SUPPRESS": True,  "INVERT_TONE": False, "COLOR_MIX_BG": 0.22},
    "b_suppress_invert": {"BG_SUPPRESS": True,  "INVERT_TONE": True,  "COLOR_MIX_BG": 0.22},
    "c_full":            {"BG_SUPPRESS": False, "INVERT_TONE": False, "COLOR_MIX_BG": 0.30},
    "d_full_dim":        {"BG_SUPPRESS": False, "INVERT_TONE": False, "COLOR_MIX_BG": 0.52},
    "e_suppress_soft":   {"BG_SUPPRESS": True,  "INVERT_TONE": True,  "COLOR_MIX_BG": 0.10},
    "f_nosupp_invert":   {"BG_SUPPRESS": False, "INVERT_TONE": True,  "COLOR_MIX_BG": 0.36},
}


def main() -> int:
    snapshot = {key: getattr(config, key) for key in
                {k for overrides in VARIANTS.values() for k in overrides}}

    image = avatar.load_avatar()
    data = stats.collect(offline=True)
    out = pathlib.Path("cache/variants")
    out.mkdir(parents=True, exist_ok=True)

    cards: list[str] = []
    for name, overrides in VARIANTS.items():
        for key, value in overrides.items():
            setattr(config, key, value)
        grid = avatar.build_grid(image)
        (out / f"{name}.svg").write_text(render.render(grid, data), encoding="utf-8")
        print(f"{name:20} {overrides}")
        cards.append(f'<figure><figcaption>{name}</figcaption>'
                     f'<img src="{name}.svg" width="1000"></figure>')

    for key, value in snapshot.items():
        setattr(config, key, value)

    (out / "sheet.html").write_text(
        "<body style='margin:0;background:#222;font:13px monospace;color:#ddd'>"
        "<style>figure{margin:0;padding:6px}figcaption{padding:3px}"
        ".grid{display:grid;grid-template-columns:1fr 1fr;gap:6px}"
        "img{display:block;border:1px solid #444}</style>"
        f"<div class='grid'>{''.join(cards)}</div></body>", encoding="utf-8")
    print(f"\nContact sheet: {out / 'sheet.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
