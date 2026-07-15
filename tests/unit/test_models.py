from datetime import datetime

from replaypos.models import (
    GPS,
    Chapter,
    ChapterType,
    Event,
    EventSeverity,
    EventType,
    FixQuality,
    Navigation,
    Position,
    Project,
    ProjectObject,
    ProjectObjectType,
    SafetyZone,
    Survey,
    Track,
)


class TestPosition:
    def test_utm_to_wgs84(self):
        pos = Position(utm_easting=400020.10, utm_northing=5949091.26, utm_zone="32N")
        lat, lon = pos.lat_lon
        assert 53.5 < lat < 53.8
        assert 7.3 < lon < 7.6

    def test_epsg_code_north(self):
        pos = Position(utm_easting=0, utm_northing=0, utm_zone="32N")
        assert pos.epsg_code == 32632

    def test_epsg_code_south(self):
        pos = Position(utm_easting=0, utm_northing=0, utm_zone="19S")
        assert pos.epsg_code == 32719

    def test_invalid_zone(self):
        try:
            Position(utm_easting=0, utm_northing=0, utm_zone="invalid")
            assert False, "Should have raised"
        except ValueError:
            pass

    def test_immutable(self):
        pos = Position(utm_easting=100.0, utm_northing=200.0, utm_zone="32N")
        try:
            pos.utm_easting = 999.0
            assert False, "Should be frozen"
        except (ValueError, AttributeError, TypeError):
            pass


class TestNavigation:
    def test_navigation_validation(self):
        nav = Navigation(sog=12.5, cog=180.0, heading=175.0)
        assert nav.sog == 12.5
        assert nav.cog == 180.0

    def test_invalid_cog(self):
        try:
            Navigation(cog=400.0)
            assert False, "COG must be < 360"
        except ValueError:
            pass


class TestGPS:
    def test_gps_default(self):
        gps = GPS(accuracy=2.5, satellites=8)
        assert gps.accuracy == 2.5
        assert gps.satellites == 8
        assert gps.fix_quality is None

    def test_gps_fix_quality(self):
        gps = GPS(accuracy=0.5, satellites=12, fix_quality=FixQuality.RTK_FIX)
        assert gps.fix_quality == FixQuality.RTK_FIX


class TestSurvey:
    def test_survey_fields(self):
        s = Survey(ukc_front=2.5, ukc_aft=2.3, tide=1.2, water_level=3.4)
        assert s.ukc_front == 2.5
        assert s.ukc_aft == 2.3

    def test_survey_partial(self):
        s = Survey(tide=1.5)
        assert s.tide == 1.5
        assert s.ukc_front is None


class TestTrack:
    def test_track_creation(self, sample_track):
        assert sample_track.name == "Test Track"
        assert sample_track.point_count == 10
        assert sample_track.duration_seconds == 90.0

    def test_track_time_range(self, sample_track):
        assert sample_track.start_time == datetime(2026, 7, 1, 0, 0, 3)
        assert sample_track.end_time == datetime(2026, 7, 1, 0, 1, 33)

    def test_get_point_at(self, sample_track):
        mid = datetime(2026, 7, 1, 0, 0, 33)
        pt = sample_track.get_point_at(mid)
        assert pt is not None
        assert pt.index == 3

    def test_empty_track(self):
        t = Track()
        assert t.point_count == 0
        assert t.duration_seconds == 0.0
        assert t.start_time is None
        assert t.end_time is None


class TestTrackPoint:
    def test_trackpoint_full(self, sample_trackpoint):
        tp = sample_trackpoint
        assert tp.index == 0
        assert tp.position.utm_easting == 400020.10
        assert tp.navigation.sog == 0.0
        assert tp.gps.satellites == 11


class TestEvent:
    def test_event_defaults(self):
        ev = Event(timestamp=datetime.now())
        assert ev.event_type == EventType.MANUAL
        assert ev.severity == EventSeverity.INFO

    def test_event_alert(self):
        ev = Event(
            timestamp=datetime.now(),
            event_type=EventType.ALARM,
            severity=EventSeverity.CRITICAL,
            message="UKC below threshold",
        )
        assert ev.event_type == EventType.ALARM
        assert ev.severity == EventSeverity.CRITICAL


class TestChapter:
    def test_chapter_duration(self):
        ch = Chapter(
            name="Transit",
            start_time=datetime(2026, 7, 1, 10, 0, 0),
            end_time=datetime(2026, 7, 1, 11, 30, 0),
            chapter_type=ChapterType.TRANSIT,
        )
        assert ch.duration_seconds == 5400.0
        assert ch.duration_formatted == "1h 30m 00s"

    def test_chapter_short_duration(self):
        ch = Chapter(
            name="Stop",
            start_time=datetime(2026, 7, 1, 10, 0, 0),
            end_time=datetime(2026, 7, 1, 10, 1, 5),
            chapter_type=ChapterType.STOP,
            color="#FF4444",
        )
        assert ch.duration_formatted == "1m 05s"


class TestProject:
    def test_project_creation(self):
        p = Project(name="Test Project", client="ACME Corp")
        assert p.name == "Test Project"
        assert p.client == "ACME Corp"

    def test_project_with_objects(self):
        obj = ProjectObject(
            name="Bridge A",
            object_type=ProjectObjectType.BRIDGE,
            geometry={"type": "point", "utm_zone": "32N", "point": (400000.0, 5949000.0)},
        )
        p = Project(name="Project X", objects=[obj])
        assert len(p.objects) == 1
        assert p.objects[0].object_type == ProjectObjectType.BRIDGE


class TestSafetyZone:
    def test_zone_defaults(self):
        zone = SafetyZone(
            name="Danger",
            geometry={"type": "point", "utm_zone": "32N", "point": (400000.0, 5949000.0)},
        )
        assert zone.warning_distance == 250.0
        assert zone.alarm_distance == 100.0
        assert zone.enabled is True
