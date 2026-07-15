from __future__ import annotations

from replaypos.models.project import ProjectObjectType


class NerdIcon:
    def __init__(self, css_class: str, codepoint: str, color: str = "#4A90D9"):
        self.css_class = css_class
        self.codepoint = codepoint
        self.color = color

    @property
    def html_entity(self) -> str:
        return f"&#x{self.codepoint};"

    def marker_html(self, size: int = 24, color: str | None = None) -> str:
        c = color or self.color
        return f'<span class="nf {self.css_class}" style="font-size:{size}px;color:{c}"></span>'


ICON_MAP: dict[ProjectObjectType, NerdIcon] = {
    ProjectObjectType.BRIDGE: NerdIcon("nf-md-bridge", "f061b", "#8B4513"),
    ProjectObjectType.JETTY: NerdIcon("nf-md-dock", "f0b90", "#8B4513"),
    ProjectObjectType.BUOY: NerdIcon("nf-md-buoy", "f0da0", "#FF4444"),
    ProjectObjectType.PIPELINE: NerdIcon("nf-md-pipe", "f07e5", "#FF8C00"),
    ProjectObjectType.CABLE: NerdIcon("nf-md-cable_data", "f1394", "#FF8C00"),
    ProjectObjectType.WINDMILL: NerdIcon("nf-md-wind_turbine", "f0da5", "#4CAF50"),
    ProjectObjectType.WORK_AREA: NerdIcon("nf-md-vector_square", "f0001", "#FFC107"),
    ProjectObjectType.ANCHORAGE: NerdIcon("nf-md-anchor", "f0d50", "#2196F3"),
    ProjectObjectType.CRANE: NerdIcon("nf-md-crane", "f0d51", "#FF5722"),
    ProjectObjectType.PONTOON: NerdIcon("nf-md-ferry", "f0d52", "#9E9E9E"),
    ProjectObjectType.EQUIPMENT: NerdIcon("nf-md-tractor", "f0d53", "#FF9800"),
    ProjectObjectType.FREE_MARKER: NerdIcon("nf-md-map_marker_circle", "f034f", "#4A90D9"),
    ProjectObjectType.POLYGON: NerdIcon("nf-md-shape_polygon_plus", "f65e", "#9C27B0"),
    ProjectObjectType.LINE: NerdIcon("nf-md-vector_line", "f0d54", "#9C27B0"),
    ProjectObjectType.CIRCLE: NerdIcon("nf-md-circle_outline", "f0d55", "#9C27B0"),
}


def get_icon(obj_type: ProjectObjectType) -> NerdIcon:
    return ICON_MAP.get(obj_type, ICON_MAP[ProjectObjectType.FREE_MARKER])


def get_marker_html(obj_type: ProjectObjectType, size: int = 24, color: str | None = None) -> str:
    return get_icon(obj_type).marker_html(size, color)


NERD_FONTS_CSS = """
@import url('https://cdn.jsdelivr.net/gh/ryanoasis/nerd-fonts@v3.3.0/css/nerd-fonts-generated.css');

.map-marker {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: rgba(255,255,255,0.9);
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    border: 2px solid #4A90D9;
    font-size: 18px;
    cursor: pointer;
    transition: transform 0.2s;
}
.map-marker:hover {
    transform: scale(1.2);
    z-index: 10;
}
.map-marker.danger { border-color: #FF4444; }
.map-marker.warning { border-color: #FFC107; }
.map-marker.info { border-color: #4A90D9; }

.marker-popup {
    font-family: -apple-system, BlinkMacSystemFont, sans-serif;
    font-size: 12px;
    padding: 4px 8px;
}
.marker-popup strong { display: block; font-size: 14px; }
"""


def generate_marker_style(icon: NerdIcon) -> str:
    return f"""
    .marker-{icon.css_class.replace('nf-', '')} {{
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
        height: 32px;
        border-radius: 50%;
        background: white;
        border: 2px solid {icon.color};
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        font-size: 16px;
        cursor: pointer;
    }}
    """
