from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest

from replaypos.importers.csv_filter import FilterConfig, FilterEngine
from replaypos.importers.csv_importer import (
    CsvColumnMapper,
    CsvReader,
    TemplateManager,
    TrackPointBuilder,
    _parse_float,
    _parse_int,
    _parse_zone,
    detect_delimiter,
    parse_timestamp,
)
from replaypos.models import Navigation, Position, TrackPoint


class TestParseHelpers:
    def test_parse_float_valid(self):
        assert _parse_float("3.14") == 3.14
        assert _parse_float("0") == 0.0
        assert _parse_float("-1.5") == -1.5

    def test_parse_float_invalid(self):
        assert _parse_float("") is None
        assert _parse_float("abc") is None
        assert _parse_float(None) is None

    def test_parse_int_valid(self):
        assert _parse_int("11") == 11
        assert _parse_int("0") == 0
        assert _parse_int("3.14") == 3

    def test_parse_int_invalid(self):
        assert _parse_int("") is None
        assert _parse_int("abc") is None

    def test_parse_zone(self):
        assert _parse_zone("32N") == "32N"
        assert _parse_zone(" 32n ") == "32N"
        assert _parse_zone("") == "32N"
        assert _parse_zone(None) == "32N"


class TestDetectDelimiter:
    def test_comma(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("a,b,c\n1,2,3\n")
        assert detect_delimiter(f) == ","

    def test_semicolon(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("a;b;c\n1;2;3\n")
        assert detect_delimiter(f) == ";"

    def test_tab(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("a\tb\tc\n1\t2\t3\n")
        assert detect_delimiter(f) == "\t"

    def test_pipe(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("a|b|c\n1|2|3\n")
        assert detect_delimiter(f) == "|"

    def test_empty_fallback_comma(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text("abc\n123\n")
        assert detect_delimiter(f) == ","

    def test_real_dorsch_file(self):
        path = Path("tests/fixtures/Dorsch logs - 06-07-2026.csv")
        assert detect_delimiter(path) == ","

    def test_real_gator_file(self):
        path = Path("tests/fixtures/Gator B-KD-2492 logs - 06-07-2026 (1).csv")
        assert detect_delimiter(path) == ","


class TestParseTimestamp:
    def test_known_format(self):
        dt = parse_timestamp("00:00:03 01-07-2026", "%H:%M:%S %d-%m-%Y")
        assert dt == datetime(2026, 7, 1, 0, 0, 3)

    def test_auto_detect(self):
        dt = parse_timestamp("00:00:08 01-07-2026")
        assert dt == datetime(2026, 7, 1, 0, 0, 8)

    def test_iso_format(self):
        dt = parse_timestamp("2026-07-01T00:00:03")
        assert dt == datetime(2026, 7, 1, 0, 0, 3)

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Cannot parse timestamp"):
            parse_timestamp("not-a-timestamp")


class TestCsvColumnMapper:
    def test_valid_utm_mapping(self):
        mapping = {
            "timestamp": "Log Time", "utm_easting": "UTM Easting",
            "utm_northing": "UTM Northing", "utm_zone": "UTM Zone",
        }
        mapper = CsvColumnMapper(mapping)
        row = mapper.map_row({
            "Log Time": "00:00:03 01-07-2026",
            "UTM Easting": "400020.10",
            "UTM Northing": "5949091.26",
            "UTM Zone": "32N",
        })
        assert row["timestamp"] == "00:00:03 01-07-2026"
        assert row["utm_easting"] == "400020.10"
        assert row["utm_northing"] == "5949091.26"
        assert row["utm_zone"] == "32N"

    def test_valid_latlon_mapping(self):
        CsvColumnMapper({"timestamp": "Time", "latitude": "Lat", "longitude": "Lon"})

    def test_missing_timestamp_raises(self):
        with pytest.raises(ValueError, match="Missing required fields"):
            CsvColumnMapper({"utm_easting": "E"})

    def test_empty_mapping_raises(self):
        with pytest.raises(ValueError):
            CsvColumnMapper({})

    def test_empty_value_in_mapping_is_skipped(self):
        mapper = CsvColumnMapper({
            "timestamp": "Time",
            "utm_easting": "E",
            "utm_northing": "N",
            "utm_zone": "Z",
            "sog": "",
        })
        assert "sog" not in mapper.mapping


class TestTrackPointBuilder:
    def test_build_dorsch_point(self):
        mapping = {
            "timestamp": "Log Time",
            "utm_easting": "UTM Easting",
            "utm_northing": "UTM Northing",
            "utm_zone": "UTM Zone",
            "sog": "SOG",
            "cog": "COG",
            "heading": "Heading",
            "ukc_front": "UKC Front",
            "ukc_aft": "UKC Aft",
            "tide": "Tide",
            "water_level": "GPS WL",
            "elevation": "Z",
        }
        mapper = CsvColumnMapper(mapping)
        builder = TrackPointBuilder(timestamp_fmt="%H:%M:%S %d-%m-%Y")
        row = mapper.map_row({
            "Log Time": "00:00:03 01-07-2026",
            "UTM Zone": "32N",
            "UTM Easting": "400020.10",
            "UTM Northing": "5949091.26",
            "SOG": "0.0",
            "COG": "316.3",
            "Heading": "23.6",
            "UKC Front": "2.03",
            "UKC Aft": "2.03",
            "GPS WL": "2.26",
            "Tide": "2.65",
            "Z": "1.11",
        })
        tp = builder.build(row, 0)
        assert tp is not None
        assert tp.index == 0
        assert tp.timestamp == datetime(2026, 7, 1, 0, 0, 3)
        assert tp.position.utm_easting == 400020.10
        assert tp.position.utm_northing == 5949091.26
        assert tp.position.utm_zone == "32N"
        assert tp.navigation is not None
        assert tp.navigation.sog == 0.0
        assert tp.navigation.cog == 316.3
        assert tp.navigation.heading == 23.6
        assert tp.survey is not None
        assert tp.survey.ukc_front == 2.03
        assert tp.survey.ukc_aft == 2.03
        assert tp.survey.tide == 2.65
        assert tp.survey.water_level == 2.26
        assert tp.elevation == 1.11

    def test_build_gator_point(self):
        mapping = {
            "timestamp": "Log Time",
            "utm_easting": "UTM Easting",
            "utm_northing": "UTM Northing",
            "utm_zone": "UTM Zone",
            "speed": "GPS_SPEED",
            "gps_accuracy": "GPS_ACCURACY",
            "gps_satellites": "GPS_SATS",
            "gps_fix_quality": "GPS_FIX",
        }
        mapper = CsvColumnMapper(mapping)
        builder = TrackPointBuilder(timestamp_fmt="%H:%M:%S %d-%m-%Y")
        row = mapper.map_row({
            "Log Time": "00:00:08 01-07-2026",
            "UTM Zone": "32N",
            "UTM Easting": "400027.50",
            "UTM Northing": "5949099.86",
            "GPS_SPEED": "0.000000",
            "GPS_ACCURACY": "0.600000",
            "GPS_SATS": "11",
            "GPS_FIX": "1",
        })
        tp = builder.build(row, 0)
        assert tp is not None
        assert tp.timestamp == datetime(2026, 7, 1, 0, 0, 8)
        assert tp.position.utm_easting == 400027.50
        assert tp.position.utm_northing == 5949099.86
        assert tp.gps is not None
        assert tp.gps.accuracy == 0.6
        assert tp.gps.satellites == 11
        assert tp.gps.fix_quality is not None
        assert tp.gps.fix_quality.name == "GPS_FIX"

    def test_build_missing_position_returns_none(self):
        builder = TrackPointBuilder(timestamp_fmt="%H:%M:%S %d-%m-%Y")
        row = {"timestamp": "00:00:03 01-07-2026"}
        tp = builder.build(row, 0)
        assert tp is None

    def test_build_invalid_timestamp_returns_none(self):
        builder = TrackPointBuilder()
        row = {
            "timestamp": "invalid",
            "utm_easting": "400020.10",
            "utm_northing": "5949091.26",
            "utm_zone": "32N",
        }
        tp = builder.build(row, 0)
        assert tp is None


class TestCsvReader:
    def test_read_preview_dorsch(self):
        path = Path("tests/fixtures/Dorsch logs - 06-07-2026.csv")
        mapping = {
            "timestamp": "Log Time", "utm_easting": "UTM Easting",
            "utm_northing": "UTM Northing", "utm_zone": "UTM Zone",
        }
        mapper = CsvColumnMapper(mapping)
        reader = CsvReader(path, mapper)
        headers, rows = reader.read_preview(3)
        assert "Log Time" in headers
        assert len(rows) == 3

    def test_read_all_dorsch_first_point(self):
        path = Path("tests/fixtures/Dorsch logs - 06-07-2026.csv")
        mapping = {
            "timestamp": "Log Time",
            "utm_easting": "UTM Easting",
            "utm_northing": "UTM Northing",
            "utm_zone": "UTM Zone",
            "sog": "SOG",
            "cog": "COG",
            "heading": "Heading",
        }
        mapper = CsvColumnMapper(mapping)
        reader = CsvReader(path, mapper, timestamp_fmt="%H:%M:%S %d-%m-%Y")
        builder = TrackPointBuilder(timestamp_fmt="%H:%M:%S %d-%m-%Y")
        points = reader.read_all(builder)
        assert len(points) > 0
        assert points[0].timestamp == datetime(2026, 7, 1, 0, 0, 3)
        assert points[0].position.utm_easting == 400020.10
        assert points[0].navigation is not None

    def test_read_all_gator_first_point(self):
        path = Path("tests/fixtures/Gator B-KD-2492 logs - 06-07-2026 (1).csv")
        mapping = {
            "timestamp": "Log Time",
            "utm_easting": "UTM Easting",
            "utm_northing": "UTM Northing",
            "utm_zone": "UTM Zone",
            "speed": "GPS_SPEED",
            "gps_accuracy": "GPS_ACCURACY",
            "gps_satellites": "GPS_SATS",
            "gps_fix_quality": "GPS_FIX",
        }
        mapper = CsvColumnMapper(mapping)
        reader = CsvReader(path, mapper, timestamp_fmt="%H:%M:%S %d-%m-%Y")
        builder = TrackPointBuilder(timestamp_fmt="%H:%M:%S %d-%m-%Y")
        points = reader.read_all(builder)
        assert len(points) > 0
        assert points[0].gps is not None


class TestTemplateManager:
    def test_list_templates_includes_builtins(self):
        templates = TemplateManager.list_templates()
        names = [t["name"] for t in templates]
        assert "Dorsch Survey" in names
        assert "Gator Logger" in names

    def test_load_dorsch_template(self):
        tpl = TemplateManager.load_template("Dorsch Survey")
        assert tpl is not None
        assert tpl["mapping"]["utm_easting"] == "UTM Easting"
        assert tpl["mapping"]["sog"] == "SOG"

    def test_save_and_load_custom_template(self):
        name = "_test_custom_mapping_"
        mapping = {"timestamp": "Time", "utm_easting": "E", "utm_northing": "N", "utm_zone": "Z"}  # noqa: E501
        TemplateManager.save_template(name, mapping)
        try:
            tpl = TemplateManager.load_template(name)
            assert tpl is not None
            assert tpl["mapping"]["utm_easting"] == "E"
        finally:
            TemplateManager.delete_template(name)

    def test_delete_nonexistent_does_not_raise(self):
        TemplateManager.delete_template("_nonexistent_template_")


@pytest.fixture
def base_pos():
    return Position(utm_easting=400020.10, utm_northing=5949091.26, utm_zone="32N")


def _trackpoint_sequence(base_pos, n: int, sog_fn):
    points = []
    for i in range(n):
        ts = datetime(2026, 7, 1, 0, 0, 3) + timedelta(seconds=i * 10)
        sog = sog_fn(i)
        nav = Navigation(sog=sog, cog=180.0, heading=180.0, speed=sog)
        pos = Position(
            utm_easting=base_pos.utm_easting + i * 0.5,
            utm_northing=base_pos.utm_northing,
            utm_zone=base_pos.utm_zone,
        )
        points.append(TrackPoint(index=i, timestamp=ts, position=pos, navigation=nav))
    return points


@pytest.fixture
def moving_points(base_pos):
    return _trackpoint_sequence(base_pos, 100, lambda i: 5.0)


@pytest.fixture
def stopped_points(base_pos):
    return _trackpoint_sequence(base_pos, 100, lambda i: 0.0)


@pytest.fixture
def mixed_points(base_pos):
    return _trackpoint_sequence(base_pos, 200, lambda i: 0.0 if 50 <= i <= 80 else 4.0)


class TestFilterEngine:
    def test_detect_stops_moving_only(self, moving_points):
        engine = FilterEngine(FilterConfig(sog_threshold=1.0, min_stop_seconds=30))
        result = engine.detect_stops(moving_points)
        assert result.kept_count == len(moving_points)
        assert result.removed_count == 0

    def test_detect_stops_all_stopped(self, stopped_points):
        engine = FilterEngine(FilterConfig(sog_threshold=0.5, min_stop_seconds=10))
        result = engine.detect_stops(stopped_points)
        assert result.stop_segments == [(0, 99)]
        assert result.kept_count == len(stopped_points)

    def test_mixed_with_stop_segment(self, mixed_points):
        engine = FilterEngine(FilterConfig(sog_threshold=1.0, min_stop_seconds=30))
        result = engine.detect_stops(mixed_points)
        assert result.removed_count > 0
        assert result.kept_count > 0

    def test_estimate_reduction(self, mixed_points):
        engine = FilterEngine(FilterConfig(sog_threshold=1.0, min_stop_seconds=30))
        est = engine.estimate_reduction(mixed_points)
        assert est["total"] == len(mixed_points)
        assert est["kept"] > 0
        assert est["reduction_pct"] > 0

    def test_chapters_created(self, mixed_points):
        cfg = FilterConfig(sog_threshold=1.0, min_stop_seconds=30, create_stop_chapters=True)
        engine = FilterEngine(cfg)
        result = engine.detect_stops(mixed_points)
        assert len(result.stop_chapters) > 0
        for ch in result.stop_chapters:
            assert ch.chapter_type.value == "stop"

    def test_no_chapters_when_disabled(self, mixed_points):
        cfg = FilterConfig(sog_threshold=1.0, min_stop_seconds=30, create_stop_chapters=False)
        engine = FilterEngine(cfg)
        result = engine.detect_stops(mixed_points)
        assert len(result.stop_chapters) == 0
