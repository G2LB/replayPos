from __future__ import annotations

import csv
import json
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger

from replaypos.models import (
    GPS,
    FixQuality,
    Navigation,
    Position,
    Survey,
    TrackPoint,
)

TIMESTAMP_FORMATS = [
    ("%H:%M:%S %d-%m-%Y", "HH:MM:SS DD-MM-YYYY"),
    ("%d-%m-%Y %H:%M:%S", "DD-MM-YYYY HH:MM:SS"),
    ("%Y-%m-%dT%H:%M:%S", "ISO 8601"),
    ("%Y-%m-%d %H:%M:%S", "YYYY-MM-DD HH:MM:SS"),
    ("%d/%m/%Y %H:%M:%S", "DD/MM/YYYY HH:MM:SS"),
    ("%m/%d/%Y %H:%M:%S", "MM/DD/YYYY HH:MM:SS"),
]

TEMPLATES_DIR = Path.home() / ".replaypos" / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


BUILTIN_TEMPLATES: list[dict[str, Any]] = []


def _load_builtin_templates():
    pkg_dir = Path(__file__).parent / "templates"
    if pkg_dir.is_dir():
        for f in sorted(pkg_dir.glob("*.json")):
            try:
                with open(f) as fh:
                    BUILTIN_TEMPLATES.append(json.load(fh))
            except Exception as e:
                logger.warning("Failed to load builtin template {}: {}", f, e)


_load_builtin_templates()


class CsvColumnMapper:
    REQUIRED_FIELDS = ["timestamp"]
    POSITION_GROUPS = [
        ("utm_easting", "utm_northing", "utm_zone"),
        ("latitude", "longitude"),
    ]

    def __init__(self, mapping: dict[str, str]):
        self.mapping = {k: v for k, v in mapping.items() if v}
        self._validate()

    def _validate(self):
        missing = [f for f in self.REQUIRED_FIELDS if f not in self.mapping]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")
        has_pos = any(
            all(f in self.mapping for f in group)
            for group in self.POSITION_GROUPS
        )
        if not has_pos:
            raise ValueError(
                "Must provide either (UTM Easting + Northing + Zone) "
                "or (Latitude + Longitude)"
            )

    def map_row(self, row: dict[str, str]) -> dict[str, Any]:
        return {k: row.get(v, "").strip() for k, v in self.mapping.items()}


def _parse_float(val: str) -> float | None:
    if not val:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_int(val: str) -> int | None:
    if not val:
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _parse_zone(val: str) -> str:
    return val.strip().upper() if val else "32N"


def detect_delimiter(filepath: str | Path, num_bytes: int = 4096) -> str:
    with open(filepath) as f:
        sample = f.read(num_bytes)
    delimiters = {",": 0, ";": 0, "\t": 0, "|": 0}
    for ch in delimiters:
        delimiters[ch] = sample.count(ch)
    best = max(delimiters, key=delimiters.get)
    if delimiters[best] == 0:
        return ","
    return best


def detect_timestamp_format(samples: list[str]) -> tuple[str, str] | None:
    for val in samples:
        val = val.strip()
        for fmt, label in TIMESTAMP_FORMATS:
            try:
                datetime.strptime(val, fmt)
                return fmt, label
            except ValueError:
                continue
    return None


def parse_timestamp(val: str, fmt: str | None = None) -> datetime:
    val = val.strip()
    if fmt:
        return datetime.strptime(val, fmt)
    for fmt_candidate, _ in TIMESTAMP_FORMATS:
        try:
            return datetime.strptime(val, fmt_candidate)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: {val!r}")


class TrackPointBuilder:
    def __init__(self, timestamp_fmt: str | None = None):
        self.timestamp_fmt = timestamp_fmt

    def build(self, mapped: dict[str, Any], index: int) -> TrackPoint | None:
        try:
            ts = parse_timestamp(mapped.get("timestamp", ""), self.timestamp_fmt)
        except (ValueError, KeyError):
            return None

        utm_e = _parse_float(mapped.get("utm_easting"))
        utm_n = _parse_float(mapped.get("utm_northing"))
        utm_z = _parse_zone(mapped.get("utm_zone", "32N"))

        lat = _parse_float(mapped.get("latitude"))
        lon = _parse_float(mapped.get("longitude"))

        if utm_e is not None and utm_n is not None:
            position = Position(utm_easting=utm_e, utm_northing=utm_n, utm_zone=utm_z)
        elif lat is not None and lon is not None:
            from pyproj import Transformer
            target_crs = 32600 + int(utm_z[:-1]) if utm_z[:-1] else 32632
            transformer = Transformer.from_crs(4326, target_crs, always_xy=True)
            lon_t, lat_t = transformer.transform(lon, lat)
            position = Position(utm_easting=lon_t, utm_northing=lat_t, utm_zone=utm_z)
        else:
            return None

        sog = _parse_float(mapped.get("sog"))
        cog = _parse_float(mapped.get("cog"))
        heading = _parse_float(mapped.get("heading"))
        speed = _parse_float(mapped.get("speed"))
        navigation = Navigation(
            sog=sog, cog=cog, heading=heading, speed=speed
        ) if any(x is not None for x in [sog, cog, heading, speed]) else None

        gps_acc = _parse_float(mapped.get("gps_accuracy"))
        gps_sats = _parse_int(mapped.get("gps_satellites"))
        gps_fix = _parse_int(mapped.get("gps_fix_quality"))
        gps = GPS(
            accuracy=gps_acc,
            satellites=gps_sats,
            fix_quality=FixQuality(gps_fix) if gps_fix is not None else None,
        ) if any([gps_acc is not None, gps_sats is not None, gps_fix is not None]) else None

        ukc_f = _parse_float(mapped.get("ukc_front"))
        ukc_a = _parse_float(mapped.get("ukc_aft"))
        tide = _parse_float(mapped.get("tide"))
        wl = _parse_float(mapped.get("water_level"))
        survey = Survey(
            ukc_front=ukc_f, ukc_aft=ukc_a, tide=tide, water_level=wl
        ) if any(x is not None for x in [ukc_f, ukc_a, tide, wl]) else None

        elevation = _parse_float(mapped.get("elevation"))

        return TrackPoint(
            index=index,
            timestamp=ts,
            position=position,
            navigation=navigation,
            gps=gps,
            survey=survey,
            elevation=elevation,
        )


class CsvReader:
    def __init__(
        self,
        filepath: str | Path,
        mapper: CsvColumnMapper,
        timestamp_fmt: str | None = None,
        delimiter: str | None = None,
        has_header: bool = True,
        skip_rows: int = 0,
    ):
        self.filepath = Path(filepath)
        self.mapper = mapper
        self.timestamp_fmt = timestamp_fmt
        self.delimiter = delimiter or detect_delimiter(self.filepath)
        self.has_header = has_header
        self.skip_rows = skip_rows

    def read_preview(self, n: int = 10) -> tuple[list[str], list[list[str]]]:
        headers: list[str] = []
        rows: list[list[str]] = []
        with open(self.filepath, newline="") as f:
            reader = csv.reader(f, delimiter=self.delimiter)
            for _ in range(self.skip_rows):
                next(reader)
            if self.has_header:
                headers = next(reader)
            for i, row in enumerate(reader):
                if i >= n:
                    break
                rows.append(row)
        return headers, rows

    def read_all(
        self,
        builder: TrackPointBuilder,
        progress: Callable[[int, int], None] | None = None,
    ) -> list[TrackPoint]:
        points: list[TrackPoint] = []
        idx = 0
        with open(self.filepath, newline="") as f:
            reader = csv.reader(f, delimiter=self.delimiter)
            for _ in range(self.skip_rows):
                next(reader)
            if self.has_header:
                header_row = next(reader)
            else:
                header_row = []

            total_estimate = sum(1 for _ in open(self.filepath)) - (1 if self.has_header else 0)
            if progress:
                progress(0, total_estimate)

            for row_idx, row in enumerate(reader):
                if not row or all(c.strip() == "" for c in row):
                    continue
                if self.has_header:
                    mapped = dict(zip(header_row, row))
                else:
                    mapped = {str(i): v for i, v in enumerate(row)}

                mapped_dict = self.mapper.map_row(mapped)
                tp = builder.build(mapped_dict, idx)
                if tp is not None:
                    points.append(tp)
                    idx += 1
                if progress and row_idx % 1000 == 0:
                    progress(row_idx, total_estimate)

        if progress:
            progress(total_estimate, total_estimate)
        return points


class TemplateManager:
    @staticmethod
    def list_templates() -> list[dict[str, Any]]:
        templates = list(BUILTIN_TEMPLATES)
        for f in sorted(TEMPLATES_DIR.glob("*.json")):
            try:
                with open(f) as fh:
                    tpl = json.load(fh)
                    if not any(t.get("name") == tpl.get("name") for t in templates):
                        templates.append(tpl)
            except Exception:
                continue
        return templates

    @staticmethod
    def load_template(name: str) -> dict[str, Any] | None:
        for t in TemplateManager.list_templates():
            if t.get("name") == name:
                return dict(t)
        return None

    @staticmethod
    def save_template(name: str, mapping: dict[str, Any], description: str = ""):
        tpl = {
            "name": name,
            "description": description,
            "delimiter": ",",
            "has_header": True,
            "timestamp_format": "HH:MM:SS DD-MM-YYYY",
            "mapping": mapping,
        }
        path = TEMPLATES_DIR / f"{name.lower().replace(' ', '_')}.json"
        with open(path, "w") as f:
            json.dump(tpl, f, indent=2)
        logger.info("Saved template: {}", path)

    @staticmethod
    def delete_template(name: str):
        path = TEMPLATES_DIR / f"{name.lower().replace(' ', '_')}.json"
        if path.exists():
            path.unlink()
            logger.info("Deleted template: {}", path)
