"""Every tunable for the profile card. No logic, no imports from the rest of the package."""

USERNAME = "ikenxuan"

# --- avatar source ---
# Fetched on every build rather than committed. A committed copy would freeze
# the portrait: changing the avatar would need a manual re-fetch and a commit
# before the card caught up. github.com/{user}.png redirects to the avatar CDN,
# and requests follows that. The last fetch is cached locally as a fallback for
# a CDN hiccup or an --offline run; that cache is not committed, so a fresh
# checkout has no portrait until its first successful fetch.
AVATAR_URL = "https://github.com/{user}.png?size={size}"
AVATAR_FETCH_SIZE = 460     # 460 is the largest size the endpoint serves
AVATAR_CACHE_PATH = "cache/avatar.png"

# --- portrait: glyph matching ---
# Characters are picked by matching each cell against pre-rendered glyph coverage
# bitmaps, not by indexing a brightness ramp. A ramp only knows how dark a cell is;
# glyph matching also knows what SHAPE the ink in that cell makes, so an eyebrow
# picks a horizontal stroke and a jawline picks a diagonal one.
#
# The ramp order below doubles as the canonical character order in glyph_bitmaps.json.
GLYPH_CHARS = " .`'\"^,:;Il!i><~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$"
GLYPH_BITMAP_FILE = "glyph_bitmaps.json"
GLYPH_FONT_CANDIDATES = (
    "C:/Windows/Fonts/consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
)
GLYPH_CELL = (8, 16)            # sub-sampling resolution per character cell
GLYPH_FONT_SIZE = 14.5          # matches FONT_SIZE so bitmaps describe the real cell
# 0 = pure tone (a ramp), 1 = pure shape (fits noise). Pure structure discards
# brightness and renders confetti; tone leads, structure refines.
GLYPH_STRUCTURE_WEIGHT = 0.45
GLYPH_WORST_TONE_ERROR = 1.0    # a full-black cell against a full-white glyph
# Left off. Inverting suits a line-art avatar where only the strokes carry ink;
# this one is drawn with flat colour fills, so inverting turns the face into a
# void and the backdrop into a wall of characters.
INVERT_TONE = False

AVATAR_COLS = 56
CHAR_ASPECT = 0.5               # monospace cells are ~2x taller than wide

# --- portrait: colour ---
# The avatar's background is a flat bright yellow. Left alone it floods the card
# with ~40% solid yellow characters and the terminal framing is lost, so cells
# close to the detected background colour are dropped to spaces instead.
BG_SUPPRESS = False
BG_SUPPRESS_DISTANCE = 72       # euclidean RGB distance from the background colour
# Suppression is off by default. On this avatar the yellow field is part of the
# art -- dropping it leaves a ragged hole where the hair and shoulders should be,
# and the portrait reads as debris rather than a character. Keeping every cell
# gives the dense, continuous block that a neofetch portrait is supposed to be.
# The knobs below are still wired up for avatars with a genuinely flat backdrop.
# The background is read from a ring around the image border, not the whole frame:
# sampling everything picks whatever flat region is largest, which on this avatar
# is the cream face.
BG_DETECT_BORDER = 0.10         # fraction of width/height used as the border ring
BG_DETECT_SAMPLE = 160          # resolution the border ring is sampled at
BG_DETECT_QUANT = 16            # colour bucket size; too fine and gradients never agree
# Contrast is stretched across the subject only. The face and the background sit
# within ~20 luminance levels of each other, so a global stretch spends most of its
# range on the flat yellow field and leaves the face with almost no separation.
# With suppression off the mask is all-ones and this becomes a plain global stretch.
SUBJECT_CONTRAST_CUTOFF = 1.0   # percentile clipped at each end of the subject
# Portrait colours are blended toward the card background. Full-strength pixels read
# as an image pasted onto a terminal; dimming them keeps it reading as text.
COLOR_MIX_BG = 0.30             # 0 = raw pixels, 1 = invisible

# --- geometry ---
CARD_WIDTH = 1000
CELL_W = 8.6                    # per-character grid pitch, see render.py
CELL_H = 18.0
FONT_SIZE = 14.5
FONT_STACK = "ui-monospace,SFMono-Regular,Consolas,Menlo,monospace"
PAD = 18
TITLEBAR_H = 34
BODY_TOP = 52
COLUMN_GAP = 34

# --- palette ---
BG = "#0d1117"
FG = "#c9d1d9"
DIM = "#4d5866"
ACCENT = "#7ee787"
KEY_COLOR = "#79c0ff"
BAR_FILLED = "\u2588"           # full block
BAR_EMPTY = "\u2591"            # light shade, reads as an empty track
SEPARATOR_CHAR = "\u2500"       # box drawing, exactly one cell in any monospace face
SWATCH = ["#ff5f57", "#febc2e", "#28c840", "#59a7ff", "#bd93f9", "#8be9fd", "#c9d1d9"]

# --- window chrome ---
CARD_RADIUS = 12
TITLEBAR_OVERLAY = "#00000033"
TITLEBAR_DOT_COLORS = ("#ff5f57", "#febc2e", "#28c840")
TITLEBAR_DOT_X = (22, 42, 62)
TITLEBAR_DOT_Y = 17
TITLEBAR_DOT_RADIUS = 6
TITLEBAR_CAPTION_Y = 22
TITLEBAR_FONT_SIZE = 12
TITLEBAR_CAPTION_SUFFIX = " \u2014 neofetch"

# --- info panel layout ---
INFO_SEPARATOR_WIDTH = 46
INFO_KEY_WIDTH = 13             # left column width for key labels
LANG_NAME_WIDTH = 13            # "WebAssembly" is 11 chars; 10 was cutting it to "WebAssembl"
LANG_BAR_CELLS = 10
TOP_LANGUAGES = 6
# Minimum WCAG contrast a language colour must reach against BG before it is
# lightened. GitHub's own WebAssembly colour (#04133b) scores 1.05 on this
# background -- invisible. CSS (#663399) scores 2.48, also under the bar.
LANG_MIN_CONTRAST = 4.5
LANG_LIGHTEN_STEP = 0.08        # fraction blended toward white per attempt

# --- content ---
# Kept ASCII-only on purpose. Non-ASCII glyphs (this account's bio contains
# several) fall out of the monospace face into a proportional fallback, which
# breaks column alignment.
OS_LINE = "Windows 11 \u00b7 Linux"
SHELL_LINE = "PowerShell \u00b7 zsh"
# `contributionsCollection` with no from/to covers the TRAILING TWELVE MONTHS,
# not the calendar year -- the label has to say so.
COMMITS_LABEL = "last 12 months"

# --- data ---
STATS_CACHE_PATH = "cache/stats.json"
GITHUB_API = "https://api.github.com/graphql"
GITHUB_TIMEOUT_SECONDS = 30
# Guard against a silently under-scoped token. An Actions GITHUB_TOKEN is an
# installation token for one repository: querying repositories through it
# returns only the repos that token can see, with HTTP 200 and no error, which
# would overwrite good cached numbers with wrong ones. A drop this large is a
# permission problem rather than a real change, so the cache wins.
STATS_MIN_REPO_RATIO = 0.5

OUTPUT_PATH = "profile.svg"
