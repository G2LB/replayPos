from __future__ import annotations

import logging
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QFont, QIcon, QPainter, QPixmap

logger = logging.getLogger(__name__)

# ── Nerd Font codepoints used in the app ───────────────────────────
# Map from CSS class name → hex codepoint (without \\u prefix)
NERD_CODEPOINTS: dict[str, str] = {
    "nf-fae-file_import": "e27d",
    "nf-fae-file_export": "e27c",
    "nf-md-database_import_outline": "f162d",
    "nf-md-database_export": "f058b",
    "nf-md-file_import_outline": "f102f",
    "nf-md-map_marker": "f034e",
    "nf-md-map": "f034d",
    "nf-md-play": "f040a",
    "nf-md-stop": "f04db",
    "nf-md-pause": "f03e4",
    "nf-md-skip_next": "f04d0",
    "nf-md-skip_previous": "f04cf",
    "nf-md-speedometer": "f0506",
    "nf-md-timer": "f04e2",
    "nf-md-layers": "f0e4a",
    "nf-md-eye": "f01ed",
    "nf-md-eye_off": "f01ee",
    "nf-md-filter": "f0233",
    "nf-md-filter_variant": "f0234",
    "nf-md-import": "f0bd7",
    "nf-md-export": "f0bd8",
    "nf-md-close": "f0156",
    "nf-md-check": "f012c",
    "nf-md-menu": "f035c",
    "nf-md-settings": "f0493",
}

_FONT_CACHE_DIR = Path(tempfile.gettempdir()) / "replaypos-nerdfonts"
_DEFAULT_FAMILY = "NerdFontsSymbolsOnly"

# Fallback family names to check on the system (some users install Nerd Fonts
# under different names via font managers).
_SYSTEM_FAMILIES = (
    _DEFAULT_FAMILY,
    "NerdFontsSymbols Nerd Font",
    "Symbols Nerd Font",
    "NerdFontsSymbolsOnly",
    "Nerd Fonts",
)

# The release zip containing the symbol-only TTF.
_ZIP_URL = (
    "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.3.0/NerdFontsSymbolsOnly.zip"
)

# Alternative direct TTF download candidates (tried in order).
_TTF_CANDIDATES = (
    # jsDelivr CDN (faster, cached)
    "https://cdn.jsdelivr.net/gh/ryanoasis/nerd-fonts@v3.3.0/"
    "patched-fonts/NerdFontsSymbolsOnly/Regular/"
    "NerdFontsSymbolsOnly-Regular.ttf",
    # Raw GitHub (no caching, but always works)
    "https://raw.githubusercontent.com/ryanoasis/nerd-fonts/v3.3.0/"
    "patched-fonts/NerdFontsSymbolsOnly/Regular/"
    "NerdFontsSymbolsOnly-Regular.ttf",
)

# Module-level state -------------------------------------------------
_font_id: int | None = None  # QFontDatabase font ID (≥0 when loaded)
_font_family: str = _DEFAULT_FAMILY  # resolved family name


# ── public API ─────────────────────────────────────────────────────


def init_nerd_fonts() -> bool:
    """Load a Nerd Font into Qt's font database.

    Checks in order:
      1. Already loaded successfully → return True.
      2. System-installed Nerd Font (common family names).
      3. Previously cached TTF in tempdir.
      4. Download a TTF (direct candidates first, then zip).
      5. Fall back gracefully (empty icons, no crash).

    Returns True if the font is available and ready for ``nerd_icon()``.
    """
    global _font_id, _font_family

    from PyQt6.QtGui import QFontDatabase

    if _font_id is not None and _font_id >= 0:
        return True

    # ── system check ─────────────────────────────────────────────
    families: list[str] = QFontDatabase.families()
    for family in _SYSTEM_FAMILIES:
        if family in families:
            _font_family = family
            logger.info("Using system-installed Nerd Font: %s", family)
            return True

    # ── cache or download ────────────────────────────────────────
    _FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    ttf_path = _find_cached_ttf()
    if ttf_path is None:
        ttf_path = _download_font()
    if ttf_path is None:
        logger.warning("Nerd Font not available — UI icons disabled")
        return False

    fid = QFontDatabase.addApplicationFont(str(ttf_path))
    if fid < 0:
        logger.error("QFontDatabase rejected font file: %s", ttf_path)
        return False

    _font_id = fid
    families = QFontDatabase.applicationFontFamilies(fid)
    _font_family = families[0] if families else _DEFAULT_FAMILY
    logger.info("Nerd Font loaded: %s (family=%s)", ttf_path.name, _font_family)
    return True


def nerd_icon(css_class: str, size: int = 16, color: str | None = None) -> QIcon:
    """Create a ``QIcon`` from a Nerd Font glyph.

    Parameters
    ----------
    css_class :
        CSS class name, e.g. ``"nf-fae-file_import"``.
    size :
        Pixel size for the icon (square).
    color :
        Hex string like ``"#fff"``. Defaults to white.

    Returns
    -------
    QIcon
        Rendered glyph, or an empty icon if the font or codepoint is
        unavailable.
    """
    codepoint = _resolve_codepoint(css_class)
    if codepoint is None:
        return QIcon()

    if _font_id is None or _font_id < 0:
        return QIcon()

    pm = QPixmap(QSize(size, size))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

    font = QFont(_font_family, int(size * 0.80))
    painter.setFont(font)

    from PyQt6.QtGui import QColor

    painter.setPen(QColor(color) if color else Qt.GlobalColor.white)

    char = chr(int(codepoint, 16))
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, char)
    painter.end()
    return QIcon(pm)


def nerd_font(size: int = 14) -> QFont:
    """Return a ``QFont`` for the loaded Nerd Font at *size*."""
    return QFont(_font_family, size)


# ── helpers ────────────────────────────────────────────────────────


def _resolve_codepoint(css_class: str) -> str | None:
    """Look up the hex codepoint for a CSS class name."""
    cp = NERD_CODEPOINTS.get(css_class)
    if cp is not None:
        return cp
    prefixed = f"nf-{css_class}" if not css_class.startswith("nf-") else css_class
    return NERD_CODEPOINTS.get(prefixed)


def _find_cached_ttf() -> Path | None:
    """Return the path to a cached TTF/OTF, or None."""
    for f in _FONT_CACHE_DIR.iterdir():
        if f.suffix.lower() in (".ttf", ".otf"):
            return f
    return None


def _download_font() -> Path | None:
    """Try direct TTF URLs first, then the release zip.

    Returns the path to the downloaded font file, or None on failure.
    """
    # 1. Try direct TTF candidates (CDN first)
    for url in _TTF_CANDIDATES:
        try:
            logger.info("Downloading TTF from %s …", url)
            return _download_ttf(url)
        except Exception as exc:
            logger.debug("Direct TTF failed (%s): %s", url, exc)

    # 2. Try the release zip (contains TTF inside)
    try:
        logger.info("Downloading zip from %s …", _ZIP_URL)
        return _download_and_extract_zip()
    except Exception as exc:
        logger.debug("Zip download failed: %s", exc)

    return None


def _download_ttf(url: str) -> Path:
    """Download a TTF file and cache it locally.

    Raises on network / I / O errors.
    """
    dst = _FONT_CACHE_DIR / Path(url).name
    if dst.exists():
        return dst

    _urlopen_to_file(url, dst)

    # Sanity check: first 4 bytes should be "OTTO" (CFF OTF),
    # "\x00\x01\x00\x00" (TTF), or "\x00\x01\x00\x01" (variable).
    if not _looks_like_font(dst):
        dst.unlink(missing_ok=True)
        raise ValueError(f"Downloaded file is not a valid font: {url}")

    return dst


def _download_and_extract_zip() -> Path:
    """Download the NerdFontsSymbolsOnly.zip and extract the TTF inside.

    Returns the path to the extracted font file.
    """
    zip_dst = _FONT_CACHE_DIR / "NerdFontsSymbolsOnly.zip"

    if not zip_dst.exists():
        _urlopen_to_file(_ZIP_URL, zip_dst)

    with zipfile.ZipFile(zip_dst) as zf:
        for name in zf.namelist():
            # Skip directories and macOS metadata
            if name.endswith("/") or "__MACOSX" in name:
                continue
            if name.lower().endswith((".ttf", ".otf")):
                extract_path = _FONT_CACHE_DIR / Path(name).name
                if not extract_path.exists():
                    with zf.open(name) as src, open(extract_path, "wb") as dst:
                        dst.write(src.read())
                return extract_path

    raise ValueError("No TTF/OTF found in the zip archive")


def _urlopen_to_file(url: str, dst: Path) -> None:
    """Download *url* to *dst* (overwrite if exists)."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "ReplayPos/0.1",
            "Accept": "application/octet-stream",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as src, open(dst, "wb") as f:
        f.write(src.read())


def _looks_like_font(path: Path) -> bool:
    """Check that the first 4 bytes look like a real OpenType/TrueType font."""
    try:
        magic = path.read_bytes()[:4]
    except OSError:
        return False
    return magic in (
        b"\x00\x01\x00\x00",  # TTF
        b"OTTO",  # CFF OTF
        b"\x00\x01\x00\x01",  # variable TTF
        b"true",  # old TrueType
        b"ttcf",  # TTC (font collection)
    )
