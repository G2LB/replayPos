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
    # File / data
    "nf-fae-file_import": "e27d",
    "nf-fae-file_export": "e27c",
    "nf-md-database_import_outline": "f162d",
    "nf-md-database_export": "f058b",
    "nf-md-file_import_outline": "f102f",
    # Map / navigation
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
    # Toggle
    "nf-md-eye": "f01ed",
    "nf-md-eye_off": "f01ee",
    "nf-md-filter": "f0233",
    "nf-md-filter_variant": "f0234",
    # Action
    "nf-md-import": "f0bd7",
    "nf-md-export": "f0bd8",
    "nf-md-close": "f0156",
    "nf-md-check": "f012c",
    "nf-md-menu": "f035c",
    "nf-md-settings": "f0493",
}

_FONT_CACHE_DIR = Path(tempfile.gettempdir()) / "replaypos-nerdfonts"
_FONT_FAMILY = "NerdFontsSymbolsOnly"
_GITHUB_RELEASE = (
    "https://github.com/ryanoasis/nerd-fonts/releases/download/v3.3.0/NerdFontsSymbolsOnly.zip"
)

_font_id: int | None = None  # QFontDatabase ID for the loaded font
_font_family: str = _FONT_FAMILY  # resolved family name (may differ from default)


def init_nerd_fonts() -> bool:
    """Load a Nerd Font into Qt's font database.

    Returns True if the font was successfully loaded (or was already loaded).
    """
    global _font_id, _font_family

    from PyQt6.QtGui import QFontDatabase

    # 1. Already loaded?
    if _font_id is not None and _font_id >= 0:
        return True

    # 2. Check if a Nerd Font family is already available on the system
    for family in (
        _FONT_FAMILY,
        "NerdFontsSymbols Nerd Font",
        "Symbols Nerd Font",
        "Nerd Fonts",
        "NerdFontsSymbolsOnly",
    ):
        if family in QFontDatabase().families():
            _font_family = family
            logger.info("Nerd Font found on system: %s", family)
            return True

    # 3. Try to load from a local cache
    cached = _find_cached_font()
    if cached:
        fid = QFontDatabase.addApplicationFont(str(cached))
        if fid >= 0:
            _font_id = fid
            _font_family = QFontDatabase.applicationFontFamilies(fid)[0]
            logger.info("Nerd Font loaded from cache: %s", cached)
            return True

    # 4. Download the font from GitHub
    logger.info("Downloading Nerd Font from GitHub …")
    try:
        fid = _download_and_load()
        if fid >= 0:
            _font_id = fid
            _font_family = QFontDatabase.applicationFontFamilies(fid)[0]
            return True
    except Exception as exc:
        logger.warning("Failed to download Nerd Font: %s", exc)

    logger.warning("Nerd Font is not available — UI icons will not render")
    return False


def nerd_font(size: int = 14) -> QFont:
    """Return a QFont for the loaded Nerd Font at *size*."""
    return QFont(_font_family, size)


def nerd_icon(css_class: str, size: int = 16, color: str | None = None) -> QIcon:
    """Create a QIcon from a Nerd Font glyph.

    Parameters
    ----------
    css_class :
        CSS class name like ``"nf-fae-file_import"`` (with or without ``nf-`` prefix).
    size :
        Pixel size for the icon (square).
    color :
        Hex color string (e.g. ``"#fff"``). Defaults to the application palette text color.

    Returns
    -------
    QIcon
        A square icon with the glyph rendered, or an empty icon if the font
        is not loaded or the codepoint is unknown.
    """
    codepoint = NERD_CODEPOINTS.get(css_class)
    if codepoint is None:
        # try without nf- prefix
        prefixed = f"nf-{css_class}" if not css_class.startswith("nf-") else css_class
        codepoint = NERD_CODEPOINTS.get(prefixed)
    if codepoint is None:
        logger.warning("Unknown Nerd Font icon: %s", css_class)
        return QIcon()

    if _font_id is None or _font_id < 0:
        return QIcon()

    # Render the glyph onto a pixmap
    pm = QPixmap(QSize(size, size))
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    font = nerd_font(int(size * 0.85))
    painter.setFont(font)
    if color:
        from PyQt6.QtGui import QColor

        painter.setPen(QColor(color))
    else:
        painter.setPen(Qt.GlobalColor.white)

    char = chr(int(codepoint, 16))
    painter.drawText(pm.rect(), Qt.AlignmentFlag.AlignCenter, char)
    painter.end()
    return QIcon(pm)


# ── private helpers ────────────────────────────────────────────────


def _find_cached_font() -> Path | None:
    """Return the path to a cached Nerd Font TTF if one exists."""
    _FONT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for f in _FONT_CACHE_DIR.iterdir():
        if f.suffix.lower() in (".ttf", ".otf"):
            return f
    return None


def _download_and_load() -> int:
    """Download the NerdFontsSymbolsOnly zip, extract a TTF, cache and load it.

    Returns the QFontDatabase font ID, or -1 on failure.
    """
    from PyQt6.QtGui import QFontDatabase

    zip_path = _FONT_CACHE_DIR / "NerdFontsSymbolsOnly.zip"

    # Download if not already cached
    if not zip_path.exists():
        urllib.request.urlretrieve(_GITHUB_RELEASE, zip_path)

    # Extract the first TTF/OTF
    ttf_path: Path | None = None
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            if name.lower().endswith((".ttf", ".otf")) and "__MACOSX" not in name:
                extract_path = _FONT_CACHE_DIR / Path(name).name
                if not extract_path.exists():
                    with zf.open(name) as src, open(extract_path, "wb") as dst:
                        dst.write(src.read())
                ttf_path = extract_path
                break

    if ttf_path is None:
        logger.error("No TTF/OTF found in Nerd Fonts zip")
        return -1

    fid = QFontDatabase.addApplicationFont(str(ttf_path))
    if fid < 0:
        logger.error("QFontDatabase rejected the Nerd Font TTF: %s", ttf_path)
        return -1

    return fid
