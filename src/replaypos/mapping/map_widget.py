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
let dayLayerIds = [];
let openseamapVisible = true;
let progressCoords = [];
let intervalData = [];

function initQWebChannel() {{
  if (typeof QWebChannel === 'undefined') {{
    setTimeout(initQWebChannel, 50);
    return;
  }}
  new QWebChannel(qt.webChannelTransport, function(channel) {{
    window.backend = channel.objects.backend;
  }});
}}
initQWebChannel();

function toggleOpenSeaMap(visible) {{
  openseamapVisible = visible;
  if (map.getLayer('openseamap-layer')) {{
    map.setLayoutProperty('openseamap-layer', 'visibility', visible ? 'visible' : 'none');
  }}
}}

function loadTrack(data) {{
  clearMap();
  const sid = 'track-' + Date.now();
  currentSourceId = sid;
  dayLayerIds = [];

  // ── one source + layer per day ──────────────────────────────────
  for (const [dateStr, geojson] of Object.entries(data.days)) {{
    const srcId = sid + '-src-' + dateStr;
    const layId = sid + '-lay-' + dateStr;
    dayLayerIds.push(layId);

    map.addSource(srcId, {{ type: 'geojson', data: geojson }});
    map.addLayer({{
      id: layId,
      type: 'line',
      source: srcId,
      paint: {{
        'line-color': ['get', 'stroke'],
        'line-width': 3,
        'line-opacity': 0.9
      }}
    }});
  }}

  // ── progress line (cumulative trail, grows during playback) ─────
  map.addSource('progress-line', {{
    type: 'geojson',
    data: {{ type: 'FeatureCollection', features: [] }}
  }});
  map.addLayer({{
    id: 'progress-line-layer',
    type: 'line',
    source: 'progress-line',
    paint: {{
      'line-color': '#fbbf24',
      'line-width': 5,
      'line-opacity': 0.9
    }}
  }});

  // ── start / end markers ─────────────────────────────────────────
  function addMarker(coords, imgId, layerId) {{
    const srcId = sid + '-' + layerId;
    map.addSource(srcId, {{
      type: 'geojson',
      data: {{ type: 'FeatureCollection', features: [{{
        type: 'Feature',
        geometry: {{ type: 'Point', coordinates: coords }},
        properties: {{}}
      }}] }}
    }});
    map.addLayer({{
      id: layerId,
      type: 'symbol',
      source: srcId,
      layout: {{
        'icon-image': imgId,
        'icon-size': 1.2,
        'icon-allow-overlap': true
      }}
    }});
  }}
  if (data.markers && data.markers.start) {{
    addMarker(data.markers.start, 'marker-start', 'marker-start-' + sid);
  }}
  if (data.markers && data.markers.end) {{
    addMarker(data.markers.end, 'marker-end', 'marker-end-' + sid);
  }}

  // ── fit bounds over ALL days ────────────────────────────────────
  const bounds = new maplibregl.LngLatBounds();
  for (const geojson of Object.values(data.days)) {{
    if (geojson.features) {{
      geojson.features.forEach(function(f) {{
        if (f.geometry && f.geometry.coordinates) {{
          if (f.geometry.type === 'Point') {{
            bounds.extend(f.geometry.coordinates);
          }} else if (f.geometry.type === 'LineString') {{
            f.geometry.coordinates.forEach(function(c) {{ bounds.extend(c); }});
          }}
        }}
      }});
    }}
  }}
  if (!bounds.isEmpty()) {{
    map.fitBounds(bounds, {{ padding: 60, maxZoom: 16 }});
  }}
}}

function toggleDay(dateStr, visible) {{
  const sid = currentSourceId;
  if (!sid) return;
  const layId = sid + '-lay-' + dateStr;
  if (map.getLayer(layId)) {{
    map.setLayoutProperty(layId, 'visibility', visible ? 'visible' : 'none');
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

function resetProgress() {{
  progressCoords = [];
  intervalData = [];
  ['progress-line', 'interval-markers', 'current-interval'].forEach(function(id) {{
    try {{ map.getSource(id).setData({{ type: 'FeatureCollection', features: [] }}); }}
    catch(e) {{}}
  }});
}}

function appendProgressPoint(coord) {{
  progressCoords.push(coord);
  if (map.getSource('progress-line')) {{
    map.getSource('progress-line').setData({{
      type: 'FeatureCollection',
      features: [{{
        type: 'Feature',
        geometry: {{ type: 'LineString', coordinates: progressCoords }},
        properties: {{}}
      }}]
    }});
  }}
}}

function loadIntervals(intervals) {{
  intervalData = intervals || [];
  // remove old layers
  ['interval-markers-layer', 'current-interval-layer'].forEach(function(id) {{
    try {{ map.removeLayer(id); }} catch(e) {{}}
  }});
  ['interval-markers', 'current-interval'].forEach(function(id) {{
    try {{ map.removeSource(id); }} catch(e) {{}}
  }});
  if (!intervalData.length) return;

  // interval dots
  var features = intervalData.map(function(iv) {{
    return {{
      type: 'Feature',
      geometry: {{ type: 'Point', coordinates: iv.coords }},
      properties: {{ time: iv.time || '' }}
    }};
  }});
  map.addSource('interval-markers', {{
    type: 'geojson',
    data: {{ type: 'FeatureCollection', features: features }}
  }});
  map.addLayer({{
    id: 'interval-markers-layer',
    type: 'circle',
    source: 'interval-markers',
    paint: {{
      'circle-radius': 5,
      'circle-color': '#fbbf24',
      'circle-opacity': 0.7,
      'circle-stroke-width': 1,
      'circle-stroke-color': '#fff'
    }}
  }});

  // highlighted (current) interval — starts empty
  map.addSource('current-interval', {{
    type: 'geojson',
    data: {{ type: 'FeatureCollection', features: [] }}
  }});
  map.addLayer({{
    id: 'current-interval-layer',
    type: 'circle',
    source: 'current-interval',
    paint: {{
      'circle-radius': 10,
      'circle-color': '#fbbf24',
      'circle-opacity': 1.0,
      'circle-stroke-width': 3,
      'circle-stroke-color': '#fff'
    }}
  }});
}}

function highlightInterval(coords) {{
  if (map.getSource('current-interval')) {{
    map.getSource('current-interval').setData({{
      type: 'FeatureCollection',
      features: [{{
        type: 'Feature',
        geometry: {{ type: 'Point', coordinates: coords }},
        properties: {{}}
      }}]
    }});
  }}
}}

function clearMap() {{
  if (currentSourceId) {{
    const sid = currentSourceId;
    // remove per-day layers + sources
    for (const layId of dayLayerIds) {{
      try {{
        const srcId = sid + '-src-' + layId.replace(sid + '-lay-', '');
        map.removeLayer(layId);
        try {{ map.removeSource(srcId); }} catch(e) {{}}
      }} catch(e) {{}}
    }}
    // remove markers
    try {{ map.removeLayer('marker-start-' + sid); }} catch(e) {{}}
    try {{ map.removeLayer('marker-end-' + sid); }} catch(e) {{}}
    currentSourceId = null;
    dayLayerIds = [];
  }}
  // progress + intervals
  try {{ map.removeLayer('progress-line-layer'); }} catch(e) {{}}
  try {{ map.removeSource('progress-line'); }} catch(e) {{}}
  try {{ map.removeLayer('interval-markers-layer'); }} catch(e) {{}}
  try {{ map.removeSource('interval-markers'); }} catch(e) {{}}
  try {{ map.removeLayer('current-interval-layer'); }} catch(e) {{}}
  try {{ map.removeSource('current-interval'); }} catch(e) {{}}
  try {{ map.removeLayer('highlight-point-layer'); }} catch(e) {{}}
  try {{ map.removeSource('highlight-point'); }} catch(e) {{}}
  resetProgress();
}}

map.on('load', function() {{
  const S = 36;

  function makeMarkerIcon(fillColor, symbol) {{
    const c = document.createElement('canvas');
    c.width = S;
    c.height = S;
    const ctx = c.getContext('2d');

    // translucent halo
    ctx.beginPath();
    ctx.arc(S/2, S/2, S/2 - 1, 0, 2 * Math.PI);
    ctx.fillStyle = fillColor;
    ctx.fill();

    // white symbol
    ctx.fillStyle = '#fff';
    ctx.beginPath();
    if (symbol === 'start') {{
      // play triangle
      ctx.moveTo(13, 9);
      ctx.lineTo(25, 18);
      ctx.lineTo(13, 27);
    }} else {{
      // stop square
      ctx.rect(11, 11, 14, 14);
    }}
    ctx.closePath();
    ctx.fill();

    return ctx.getImageData(0, 0, S, S);
  }}

  map.addImage('marker-start', makeMarkerIcon('#22c55e', 'start'), {{ sdf: false, pixelRatio: 2 }});
  map.addImage('marker-end',   makeMarkerIcon('#ef4444', 'end'),   {{ sdf: false, pixelRatio: 2 }});

  // ── OpenSeaMap raster overlay ──────────────────────────────────
  map.addSource('openseamap', {{
    type: 'raster',
    tiles: ['https://tiles.openseamap.org/seamark/{{z}}/{{x}}/{{y}}.png'],
    tileSize: 256,
    attribution: '&copy; <a href="https://www.openseamap.org">OpenSeaMap</a>'
  }});
  map.addLayer({{
    id: 'openseamap-layer',
    type: 'raster',
    source: 'openseamap',
    paint: {{ 'raster-opacity': 0.7 }}
  }});
}});
</script>
</body>
</html>
"""


_DAY_COLORS = ("#3b82f6", "#93c5fd")  # blue / lighter-blue alternating palette


def _track_to_geojson_by_day(track: Track) -> dict[str, Any]:
    """Convert a Track into per-day GeoJSON bundles for the JS map.

    Returns
    -------
    dict
        ``{"days": {date_str: FeatureCollection, …},
          "markers": {"start": [lon, lat], "end": [lon, lat]}}``
    """
    result: dict[str, Any] = {"days": {}, "markers": {}}
    if not track.points:
        return result

    from collections import defaultdict

    by_date: dict[str, list] = defaultdict(list)
    for tp in track.points:
        by_date[tp.timestamp.strftime("%Y-%m-%d")].append(tp)

    for i, (date_str, pts) in enumerate(sorted(by_date.items())):
        coords = [[p.position.longitude, p.position.latitude] for p in pts]
        result["days"][date_str] = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {
                        "name": date_str,
                        "stroke": _DAY_COLORS[i % len(_DAY_COLORS)],
                        "point_count": len(pts),
                    },
                }
            ],
        }

    first = track.points[0]
    last = track.points[-1]
    result["markers"]["start"] = [first.position.longitude, first.position.latitude]
    result["markers"]["end"] = [last.position.longitude, last.position.latitude]
    return result


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
        """Load a track onto the map, replacing any previous track.

        Creates one MapLibre source+layer per day in JS so that
        individual days can be toggled on/off without re-sending data.
        """
        self._track = track
        data = _track_to_geojson_by_day(track)
        js = f"loadTrack({json.dumps(data)})"
        self._web_view.page().runJavaScript(js)

    def set_day_visible(self, date_str: str, visible: bool) -> None:
        """Show or hide a single day's layer without reloading the full track."""
        js = f"toggleDay({json.dumps(date_str)}, {'true' if visible else 'false'})"
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

    def load_intervals(self, intervals: list[dict]) -> None:
        """Set 6-minute interval markers on the map."""
        js = f"loadIntervals({json.dumps(intervals)})"
        self._web_view.page().runJavaScript(js)

    def append_progress_point(self, coord: list[float]) -> None:
        """Append one coordinate to the cumulative trail."""
        js = f"appendProgressPoint({json.dumps(coord)})"
        self._web_view.page().runJavaScript(js)

    def highlight_interval(self, coords: list[float]) -> None:
        """Highlight the current 6-minute interval marker."""
        js = f"highlightInterval({json.dumps(coords)})"
        self._web_view.page().runJavaScript(js)

    def reset_progress(self) -> None:
        """Clear the cumulative trail and interval highlights."""
        self._web_view.page().runJavaScript("resetProgress()")

    def clear(self) -> None:
        """Remove all track layers from the map."""
        self._track = None
        self._web_view.page().runJavaScript("clearMap()")

    def set_openseamap_visible(self, visible: bool) -> None:
        """Show or hide the OpenSeaMap raster overlay."""
        js = f"toggleOpenSeaMap({'true' if visible else 'false'})"
        self._web_view.page().runJavaScript(js)

    @pyqtSlot(float, float)
    def on_map_click(self, lat: float, lon: float) -> None:
        """Called from JavaScript when the map is clicked.

        Can be connected to a signal for external handlers.
        """
        pass
