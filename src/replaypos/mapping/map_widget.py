from __future__ import annotations

import json
from typing import Any

from PyQt6.QtCore import QUrl, pyqtSlot
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from replaypos.models import Track, TrackPoint

_MAPLIBRE_CDN = "https://unpkg.com/maplibre-gl@4/dist/maplibre-gl"
_MAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="{lib_css}" rel="stylesheet" />
<script src="{lib_js}"></script>
<style>
  body {{ margin: 0; padding: 0; }}
  #map {{ width: 100vw; height: 100vh; }}
  .north-arrow {{
    position: absolute; bottom: 24px; right: 24px;
    width: 36px; height: 36px; background: rgba(255,255,255,0.9);
    border-radius: 4px; display: flex; align-items: center;
    justify-content: center; font-size: 20px; pointer-events: none;
    box-shadow: 0 1px 4px rgba(0,0,0,0.3); z-index: 10;
  }}
</style>
</head>
<body>
<div id="map"></div>
<div class="north-arrow">&#x2B06;</div>
<script src="https://cdn.jsdelivr.net/npm/qwebchannel@1/dist/qwebchannel.js"></script>
<script>
const map = new maplibregl.Map({{
  container: 'map',
  style: '{map_style}',
  center: [3.5, 51.0],
  zoom: 10,
  attributionControl: false
}});
map.addControl(new maplibregl.NavigationControl(), 'top-left');
map.addControl(new maplibregl.ScaleControl({{
  maxWidth: 120, unit: 'metric'
}}), 'bottom-left');

let currentSourceId = null;

new QWebChannel(qt.webChannelTransport, function(channel) {{
  window.backend = channel.objects.backend;
}});

function loadTrack(geojson) {{
  if (currentSourceId) {{
    try {{ map.removeLayer(currentSourceId + '-line'); }} catch(e) {{}}
    try {{ map.removeLayer(currentSourceId + '-start'); }} catch(e) {{}}
    try {{ map.removeLayer(currentSourceId + '-end'); }} catch(e) {{}}
    try {{ map.removeSource(currentSourceId); }} catch(e) {{}}
  }}
  const sid = 'track-' + Date.now();
  currentSourceId = sid;

  map.addSource(sid, {{ type: 'geojson', data: geojson }});

  map.addLayer({{
    id: sid + '-line',
    type: 'line',
    source: sid,
    filter: ['==', '$type', 'LineString'],
    paint: {{
      'line-color': '#3b82f6',
      'line-width': 3,
      'line-opacity': 0.9
    }}
  }});

  map.addLayer({{
    id: sid + '-start',
    type: 'symbol',
    source: sid,
    filter: ['==', ['get', 'marker'], 'start'],
    layout: {{
      'icon-image': 'marker-start',
      'icon-size': 1.2,
      'icon-allow-overlap': true
    }}
  }});

  map.addLayer({{
    id: sid + '-end',
    type: 'symbol',
    source: sid,
    filter: ['==', ['get', 'marker'], 'end'],
    layout: {{
      'icon-image': 'marker-end',
      'icon-size': 1.2,
      'icon-allow-overlap': true
    }}
  }});

  const bounds = new maplibregl.LngLatBounds();
  if (geojson.features) {{
    geojson.features.forEach(function(f) {{
      if (f.geometry.type === 'Point') {{
        bounds.extend(f.geometry.coordinates);
      }} else if (f.geometry.type === 'LineString') {{
        f.geometry.coordinates.forEach(function(c) {{ bounds.extend(c); }});
      }}
    }});
  }}
  if (!bounds.isEmpty()) {{
    map.fitBounds(bounds, {{ padding: 60, maxZoom: 16 }});
  }}
}}

function highlightPoint(coords) {{
  if (currentSourceId) {{
    try {{
      map.getSource('highlight-point').setData({{
        type: 'Point', coordinates: coords
      }});
    }} catch(e) {{
      var hsrc = {{ type: 'geojson', data: {{ type: 'Point', coordinates: coords }} }};
      map.addSource('highlight-point', hsrc);
      map.addLayer({{
        id: 'highlight-point-layer',
        type: 'circle',
        source: 'highlight-point',
        paint: {{ 'circle-radius': 8, 'circle-color': '#ef4444', 'circle-opacity': 0.9 }}
      }});
    }}
  }}
}}

function clearMap() {{
  if (currentSourceId) {{
    try {{ map.removeLayer(currentSourceId + '-line'); }} catch(e) {{}}
    try {{ map.removeLayer(currentSourceId + '-start'); }} catch(e) {{}}
    try {{ map.removeLayer(currentSourceId + '-end'); }} catch(e) {{}}
    try {{ map.removeSource(currentSourceId); }} catch(e) {{}}
    currentSourceId = null;
  }}
  try {{ map.removeLayer('highlight-point-layer'); }} catch(e) {{}}
  try {{ map.removeSource('highlight-point'); }} catch(e) {{}}
}}

map.on('load', function() {{
  const size = 36;
  const startEl = document.createElement('div');
  var startSvg = '<svg width="' + size + '" height="' + size + '"';
  startSvg += ' viewBox="0 0 24 24" fill="#22c55e">';
  startSvg += '<circle cx="12" cy="12" r="9"/>';
  startSvg += '<path d="M12 7l4 8H8z" fill="#fff"/></svg>';
  startEl.innerHTML = startSvg;
  map.addImage('marker-start', startEl, {{ sdf: false, pixelRatio: 2 }});

  const endEl = document.createElement('div');
  var endSvg = '<svg width="' + size + '" height="' + size + '" viewBox="0 0 24 24"';
  endSvg += ' fill="#ef4444">';
  endSvg += '<circle cx="12" cy="12" r="9"/>';
  endSvg += '<rect x="9" y="9" width="6" height="6" fill="white" rx="1"/></svg>';
  endEl.innerHTML = endSvg;
  map.addImage('marker-end', endEl, {{ sdf: false, pixelRatio: 2 }});
}});
</script>
</body>
</html>
"""


def _track_to_geojson(track: Track) -> dict[str, Any]:
    """Convert a Track into a GeoJSON FeatureCollection.

    Returns a FeatureCollection with:
      - One LineString feature for the full track path
      - One Point feature for the start (with property marker='start')
      - One Point feature for the end   (with property marker='end')
    """
    if not track.points:
        return {"type": "FeatureCollection", "features": []}

    coords: list[list[float]] = []
    for tp in track.points:
        lon, lat = tp.position.longitude, tp.position.latitude
        coords.append([lon, lat])

    features: list[dict[str, Any]] = [
        {
            "type": "Feature",
            "geometry": {"type": "LineString", "coordinates": coords},
            "properties": {
                "name": track.name or "Track",
                "point_count": len(track.points),
            },
        }
    ]

    # Start marker
    first = track.points[0]
    features.append(
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [first.position.longitude, first.position.latitude],
            },
            "properties": {"marker": "start", "label": "Start"},
        }
    )

    # End marker
    last = track.points[-1]
    features.append(
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [last.position.longitude, last.position.latitude],
            },
            "properties": {"marker": "end", "label": "End"},
        }
    )

    return {"type": "FeatureCollection", "features": features}


class MapWidget(QWidget):
    """Map widget that renders tracks on a MapLibre GL map via QWebEngineView."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._track: Track | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Deferred import: QWebEngineView must be imported after QApplication exists
        from PyQt6.QtWebEngineWidgets import QWebEngineView

        self._web_view = QWebEngineView()
        self._channel = QWebChannel()
        self._channel.registerObject("backend", self)
        self._web_view.page().setWebChannel(self._channel)

        html = _HTML_TEMPLATE.format(
            lib_css=f"{_MAPLIBRE_CDN}.css",
            lib_js=f"{_MAPLIBRE_CDN}.js",
            map_style=_MAP_STYLE,
        )
        self._web_view.setHtml(html, QUrl("https://localhost/"))

        layout.addWidget(self._web_view)

    # ── public API ────────────────────────────────────────────────

    def load_track(self, track: Track) -> None:
        """Load a track onto the map, replacing any previous track."""
        self._track = track
        geojson = _track_to_geojson(track)
        js = f"loadTrack({json.dumps(geojson)})"
        self._web_view.page().runJavaScript(js)

    def fit_bounds(self) -> None:
        """Fit the map view to the currently loaded track bounds."""
        if self._track and self._track.points:
            lons = [p.position.longitude for p in self._track.points]
            lats = [p.position.latitude for p in self._track.points]
            bounds = [[min(lons), min(lats)], [max(lons), max(lats)]]
            js = f"map.fitBounds({json.dumps(bounds)}, {{padding: 60, maxZoom: 16}})"
            self._web_view.page().runJavaScript(js)

    def highlight_point(self, point: TrackPoint) -> None:
        """Highlight a specific track point on the map."""
        coords = [point.position.longitude, point.position.latitude]
        js = f"highlightPoint({json.dumps(coords)})"
        self._web_view.page().runJavaScript(js)

    def clear(self) -> None:
        """Remove all track layers from the map."""
        self._track = None
        self._web_view.page().runJavaScript("clearMap()")

    @pyqtSlot(float, float)
    def on_map_click(self, lat: float, lon: float) -> None:
        """Called from JavaScript when the map is clicked.

        Can be connected to a signal for external handlers.
        """
        pass
