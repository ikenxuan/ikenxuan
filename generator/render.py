"""Grid + stats -> profile.svg. Knows nothing about images or the GitHub API."""
from generator import config
from generator.models import ProfileStats

_MONTH_NAMES = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")


def esc(text: str) -> str:
    """XML-escape text content. Quotes are escaped too: safe in attributes as well."""
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                .replace('"', "&quot;").replace("'", "&#39;"))


# --- colour ---

def _channels(hex_colour: str) -> tuple[int, int, int]:
    red, green, blue = (int(hex_colour[index:index + 2], 16) for index in (1, 3, 5))
    return red, green, blue


def _relative_luminance(hex_colour: str) -> float:
    def linearise(value: int) -> float:
        channel = value / 255.0
        return channel / 12.92 if channel <= 0.03928 else ((channel + 0.055) / 1.055) ** 2.4

    red, green, blue = (linearise(value) for value in _channels(hex_colour))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(foreground: str, background: str) -> float:
    first, second = _relative_luminance(foreground), _relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def readable_colour(hex_colour: str | None, background: str = config.BG) -> str:
    """Lighten a language colour until it clears config.LANG_MIN_CONTRAST on the card.

    GitHub's language palette was chosen for a white page. On #0d1117 several of
    them are effectively invisible -- WebAssembly's #04133b scores 1.05, CSS's
    #663399 scores 2.48. Blend toward white in fixed steps until it clears the bar.
    """
    if not hex_colour:
        return config.FG
    colour = hex_colour
    for _ in range(24):
        if contrast(colour, background) >= config.LANG_MIN_CONTRAST:
            return colour
        red, green, blue = _channels(colour)
        step = config.LANG_LIGHTEN_STEP
        colour = "#{:02x}{:02x}{:02x}".format(
            *(round(value + (255 - value) * step) for value in (red, green, blue)))
    return colour


# --- text layout ---

def _advance(columns: int) -> float:
    return columns * config.CELL_W


def _run(text: str, x: float, y: float, fill: str) -> str:
    return (f'<tspan x="{x:.1f}" y="{y:.1f}" fill="{fill}">{esc(text)}</tspan>')


# --- blocks ---

def _window_chrome(width: int, height: int) -> str:
    radius = config.CARD_RADIUS
    bar = config.TITLEBAR_H
    # Top-rounded, bottom-square: a plain rect with rx would round the titlebar's
    # bottom corners too and leave a visible notch where it meets the body.
    title_path = (f"M0,{bar} L0,{radius} Q0,0 {radius},0 L{width - radius},0 "
                  f"Q{width},0 {width},{radius} L{width},{bar} Z")
    dots = "".join(
        f'<circle cx="{cx}" cy="{config.TITLEBAR_DOT_Y}" r="{config.TITLEBAR_DOT_RADIUS}" fill="{colour}"/>'
        for cx, colour in zip(config.TITLEBAR_DOT_X, config.TITLEBAR_DOT_COLORS))

    return (
        f'<rect width="{width}" height="{height}" fill="{config.BG}" rx="{radius}"/>'
        f'<path d="{title_path}" fill="{config.TITLEBAR_OVERLAY}"/>'
        f'{dots}'
        f'<text x="{width / 2:.1f}" y="{config.TITLEBAR_CAPTION_Y}" fill="{config.DIM}" '
        f'text-anchor="middle" font-size="{config.TITLEBAR_FONT_SIZE}px">'
        f'{esc(config.USERNAME + config.TITLEBAR_CAPTION_SUFFIX)}</text>'
    )


def _portrait(grid: list[list[tuple[str, str]]]) -> str:
    """One tspan per visible character, each pinned to its own x.

    Pinning every character is what makes the layout font-independent. Relying on
    the natural advance would let the portrait's true width drift with whichever
    monospace face the viewer resolves (8.73px for Menlo, 7.98px for Consolas),
    shifting the info column by up to 42px. Spaces are skipped rather than drawn:
    with explicit x they cost nothing to omit.
    """
    rows: list[str] = []
    for row_index, cells in enumerate(grid):
        y = config.BODY_TOP + row_index * config.CELL_H
        spans = "".join(
            f'<tspan x="{config.PAD + col * config.CELL_W:.1f}" fill="{colour}">{esc(char)}</tspan>'
            for col, (char, colour) in enumerate(cells) if char != " ")
        if spans:
            rows.append(f'<tspan x="{config.PAD}" y="{y:.1f}">{spans}</tspan>')
    return f'<text font-size="{config.FONT_SIZE}px">{"".join(rows)}</text>'


def _info_panel(stats: ProfileStats, x: float) -> str:
    key_x = x
    value_x = x + _advance(config.INFO_KEY_WIDTH)
    y = float(config.BODY_TOP)
    out: list[str] = []

    def line(offset: float = config.CELL_H) -> None:
        nonlocal y
        y += offset

    def emit(text: str, fill: str, at: float) -> None:
        out.append(_run(text, at, y, fill))

    def rule() -> None:
        emit(config.SEPARATOR_CHAR * config.INFO_SEPARATOR_WIDTH, config.DIM, key_x)
        line()

    def row(key: str, value: str, value_fill: str = config.FG) -> None:
        emit(key, config.KEY_COLOR, key_x)
        emit(value, value_fill, value_x)
        line()

    # header block
    emit(f"{stats['login']}@{stats['login']}", config.ACCENT, key_x)
    line()
    rule()

    row("OS", config.OS_LINE)
    row("Shell", config.SHELL_LINE)
    row("Repos", f"{stats['repos']} sources")
    row("Stars", f"{stats['stars']:,}")
    row("Commits", f"{stats['commits_12mo']:,} ({config.COMMITS_LABEL})")
    row("Followers", f"{stats['followers']} · following {stats['following']}")
    row("Uptime", f"since {_pretty_date(stats['created_at'])}")
    rule()

    # languages block
    emit("Languages", config.ACCENT, key_x)
    line()

    total = sum(entry["size"] for entry in stats["languages"]) or 1
    for entry in stats["languages"][:config.TOP_LANGUAGES]:
        share = entry["size"] / total * 100.0
        filled = round(share / 100.0 * config.LANG_BAR_CELLS)
        bar = config.BAR_FILLED * filled + config.BAR_EMPTY * (config.LANG_BAR_CELLS - filled)
        colour = readable_colour(entry["color"])

        emit(entry["name"][:config.LANG_NAME_WIDTH], colour, key_x)
        emit(bar, colour, value_x)
        emit(f"{share:5.1f}%", config.FG,
             value_x + _advance(config.LANG_BAR_CELLS) + config.CELL_W)
        line()

    line()
    # Appended as markup, not through emit(): emit() escapes its text, which would
    # print the tspans literally across the card.
    swatch = "".join(f'<tspan fill="{colour}">{config.BAR_FILLED * 3}</tspan>'
                     for colour in config.SWATCH)
    out.append(f'<tspan x="{key_x:.1f}" y="{y:.1f}">{swatch}</tspan>')
    return f'<text font-size="{config.FONT_SIZE}px">{"".join(out)}</text>'


def _pretty_date(iso_date: str) -> str:
    year, month, day = (int(part) for part in iso_date.split("-"))
    return f"{_MONTH_NAMES[month - 1]} {day}, {year}"


# --- entry point ---

def render(grid: list[list[tuple[str, str]]], stats: ProfileStats) -> str:
    rows = len(grid)
    height = round(config.BODY_TOP + rows * config.CELL_H + config.PAD)
    width = config.CARD_WIDTH
    info_x = config.PAD + _advance(config.AVATAR_COLS) + config.COLUMN_GAP

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="{config.FONT_STACK}" '
        f'font-size="{config.FONT_SIZE}px">'
        f'<style>text,tspan{{white-space:pre}}</style>'
        f'{_window_chrome(width, height)}'
        f'{_portrait(grid)}'
        f'{_info_panel(stats, info_x)}'
        f'</svg>'
    )
