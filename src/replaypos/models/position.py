from __future__ import annotations

import re
from functools import cached_property

import pyproj
from pydantic import BaseModel, ConfigDict, model_validator

_UTM_ZONE_RE = re.compile(r"^(\d{1,2})([NS])$")


class Position(BaseModel):
    utm_easting: float
    utm_northing: float
    utm_zone: str = "32N"
    elevation: float | None = None

    @model_validator(mode="after")
    def _validate_zone(self) -> Position:
        if not _UTM_ZONE_RE.match(self.utm_zone.upper()):
            msg = f"Invalid UTM zone: {self.utm_zone!r} (expected e.g. '32N')"
            raise ValueError(msg)
        return self

    @cached_property
    def epsg_code(self) -> int:
        match = _UTM_ZONE_RE.match(self.utm_zone.upper())
        zone_num = int(match.group(1))
        hemisphere = match.group(2)
        return 32600 + zone_num if hemisphere == "N" else 32700 + zone_num

    @cached_property
    def latitude(self) -> float:
        transformer = pyproj.Transformer.from_crs(self.epsg_code, 4326, always_xy=True)
        lon, lat = transformer.transform(self.utm_easting, self.utm_northing)
        return lat

    @cached_property
    def longitude(self) -> float:
        transformer = pyproj.Transformer.from_crs(self.epsg_code, 4326, always_xy=True)
        lon, lat = transformer.transform(self.utm_easting, self.utm_northing)
        return lon

    @cached_property
    def lat_lon(self) -> tuple[float, float]:
        transformer = pyproj.Transformer.from_crs(self.epsg_code, 4326, always_xy=True)
        lon, lat = transformer.transform(self.utm_easting, self.utm_northing)
        return lat, lon

    model_config = ConfigDict(frozen=True)
