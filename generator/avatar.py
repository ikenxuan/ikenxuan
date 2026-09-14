"""Avatar image -> grid of (character, colour) cells. Knows nothing about SVG."""
import io
import pathlib

import numpy as np
import numpy.typing as npt
import requests
from PIL import Image

from generator import config, glyphs

Cell = tuple[str, str]


def fetch_avatar(username: str, size: int = config.AVATAR_FETCH_SIZE) -> Image.Image:
    url = config.AVATAR_URL.format(user=username, size=size)
    response = requests.get(url, timeout=config.GITHUB_TIMEOUT_SECONDS)
    if response.status_code != 200:
        raise RuntimeError(f"Avatar fetch failed for {username}: HTTP {response.status_code}")
    return Image.open(io.BytesIO(response.content)).convert("RGB")


def load_avatar(offline: bool = False) -> Image.Image:
    """Fetch the avatar, falling back to the last fetched copy.

    Fetching rather than committing the image means a changed avatar reaches the
    card on its own. The fallback covers a CDN hiccup and --offline runs; the
    cached copy is deliberately not committed.
    """
    cache = pathlib.Path(config.AVATAR_CACHE_PATH)

    if offline:
        if not cache.exists():
            raise RuntimeError(
                f"--offline given but no cached avatar at {cache}. Run once "
                f"without --offline to fetch one.")
        return Image.open(cache).convert("RGB")

    try:
        image = fetch_avatar(config.USERNAME)
    except (RuntimeError, requests.RequestException) as error:
        if not cache.exists():
            raise
        print(f"Avatar fetch failed ({error}); using the cached copy.")
        return Image.open(cache).convert("RGB")

    cache.parent.mkdir(parents=True, exist_ok=True)
    image.save(cache)
    return image


def detect_background(rgb: Image.Image) -> tuple[int, int, int]:
    """The dominant colour of the image BORDER, quantised so gradients agree.

    Only a ring around the edge is sampled. Taking the mode of the whole frame
    picks whatever flat region happens to cover the most buckets, and on this
    avatar that is the cream face -- which then gets suppressed as "background"
    while the actual yellow field survives.
    """
    small = rgb.resize((config.BG_DETECT_SAMPLE, config.BG_DETECT_SAMPLE),
                       Image.Resampling.NEAREST)
    pixels = np.asarray(small, dtype=np.int32)
    height, width = pixels.shape[:2]

    band_y = max(1, round(height * config.BG_DETECT_BORDER))
    band_x = max(1, round(width * config.BG_DETECT_BORDER))
    ring = np.concatenate([
        pixels[:band_y].reshape(-1, 3),
        pixels[-band_y:].reshape(-1, 3),
        pixels[:, :band_x].reshape(-1, 3),
        pixels[:, -band_x:].reshape(-1, 3),
    ])

    quant = config.BG_DETECT_QUANT
    buckets = ring // quant * quant
    colours, counts = np.unique(buckets, axis=0, return_counts=True)
    members = ring[(buckets == colours[counts.argmax()]).all(axis=1)]
    # Mean of the real pixels in the winning bucket, so the result is not the
    # bucket floor.
    red, green, blue = members.mean(axis=0)
    return round(red), round(green), round(blue)


def _score_cells(patches: npt.NDArray[np.float64],
                 bitmaps: npt.NDArray[np.float64]) -> npt.NDArray[np.intp]:
    """Index of the best-matching glyph for every cell, scored in one pass.

    Both terms reduce to a dot product, so the whole image is two matrix
    multiplies rather than a Python loop over cells x glyphs x pixels.

    NumPy's matmul goes through BLAS, which does not clear the FPU exception
    flags, so a flag left dirty by an earlier operation gets reported against a
    later matmul. Every input here is finite and in [0, 1], so any such warning
    is stale, not ours -- suppressed, and the result is checked for real
    numerical failure below instead.
    """
    per_cell = patches.shape[1]

    with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
        dot = patches @ bitmaps.T
        tone_error = (np.sum(bitmaps ** 2, axis=1)[None, :]
                      - 2.0 * dot
                      + np.sum(patches ** 2, axis=1)[:, None]) / per_cell
        tone = 1.0 - tone_error / config.GLYPH_WORST_TONE_ERROR

        # Structure: normalised correlation of the mean-subtracted patterns.
        centred_glyphs = bitmaps - bitmaps.mean(axis=1, keepdims=True)
        centred_cells = patches - patches.mean(axis=1, keepdims=True)
        usable = np.outer(np.linalg.norm(centred_cells, axis=1),
                          np.linalg.norm(centred_glyphs, axis=1))
        safe = np.where(usable > 1e-12, usable, 1.0)
        structure = np.where(usable > 1e-12, (centred_cells @ centred_glyphs.T) / safe, 0.0)
        structure = (structure + 1.0) / 2.0

        weight = config.GLYPH_STRUCTURE_WEIGHT
        score = (1.0 - weight) * tone + weight * structure

    # A genuine NaN here would silently pick glyph 0 for every affected cell, so
    # it must fail loudly rather than render a corrupted portrait.
    if not np.isfinite(score).all():
        raise RuntimeError("Glyph scoring produced non-finite values; refusing to render")
    return np.argmax(score, axis=1)


def _mix_toward_bg(red: int, green: int, blue: int) -> str:
    mix = config.COLOR_MIX_BG
    bg = tuple(int(config.BG[index:index + 2], 16) for index in (1, 3, 5))
    out = [round(channel * (1.0 - mix) + base * mix)
           for channel, base in zip((red, green, blue), bg)]
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, value)) for value in out))


def subject_mask(rgb: Image.Image, cols: int, rows: int) -> npt.NDArray[np.bool_]:
    """Cells far enough from the detected background colour to be the subject."""
    if not config.BG_SUPPRESS:
        return np.ones((rows, cols), dtype=bool)
    cell_rgb = np.asarray(rgb.resize((cols, rows), Image.Resampling.BOX), dtype=float)
    background = np.array(detect_background(rgb), dtype=float)
    return np.linalg.norm(cell_rgb - background, axis=2) >= config.BG_SUPPRESS_DISTANCE


def build_grid(image: Image.Image, cols: int = config.AVATAR_COLS) -> list[list[Cell]]:
    if cols <= 0:
        raise ValueError("cols must be positive")

    rgb = image.convert("RGB")
    width, height = rgb.size
    rows = max(1, round(cols * (height / width) * config.CHAR_ASPECT))

    chars, bitmaps = glyphs.load()
    cell_w, cell_h = config.GLYPH_CELL

    # BOX rather than LANCZOS: a cell's colour should be the mean of the pixels it
    # covers, not a ringing-filtered sample of one point.
    cell_rgb = np.asarray(rgb.resize((cols, rows), Image.Resampling.BOX), dtype=float)
    subject = subject_mask(rgb, cols, rows)

    # Luminance, stretched at glyph resolution. The stretch is spent on the subject
    # only: face and background sit within ~20 luminance levels of each other here,
    # so a global stretch spends its range on the flat yellow field and leaves the
    # face with no separation at all.
    grey = np.asarray(
        rgb.convert("L").resize((cols * cell_w, rows * cell_h), Image.Resampling.LANCZOS),
        dtype=float)
    subject_detail = np.repeat(np.repeat(subject, cell_h, axis=0), cell_w, axis=1)
    if subject_detail.any():
        cutoff = config.SUBJECT_CONTRAST_CUTOFF
        low, high = np.percentile(grey[subject_detail], [cutoff, 100.0 - cutoff])
    else:
        low, high = 0.0, 255.0
    pixels = np.clip((grey - low) / max(high - low, 1e-6), 0.0, 1.0)
    if config.INVERT_TONE:
        pixels = 1.0 - pixels

    # (rows, cols, cell_h * cell_w), one flattened patch per character cell.
    patches = (pixels.reshape(rows, cell_h, cols, cell_w)
                     .transpose(0, 2, 1, 3)
                     .reshape(rows * cols, cell_h * cell_w))
    best = _score_cells(patches, bitmaps)

    grid: list[list[Cell]] = []
    for row in range(rows):
        cells: list[Cell] = []
        for col in range(cols):
            if not subject[row, col]:
                cells.append((" ", ""))
                continue
            red, green, blue = (int(value) for value in cell_rgb[row, col])
            # int(): numpy integers index a tuple fine at runtime but typeshed
            # only declares int and slice, so a raw np.intp is "partially unknown".
            glyph = chars[int(best[row * cols + col])]
            cells.append((glyph, _mix_toward_bg(red, green, blue)))
        grid.append(cells)
    return grid
