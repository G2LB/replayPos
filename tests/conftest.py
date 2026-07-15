from datetime import datetime, timedelta

import pytest

from replaypos.models import GPS, FixQuality, Navigation, Position, Survey, Track, TrackPoint


@pytest.fixture
def sample_position() -> Position:
    return Position(utm_easting=400020.10, utm_northing=5949091.26, utm_zone="32N")


@pytest.fixture
def sample_gps() -> GPS:
    return GPS(accuracy=0.6, satellites=11, fix_quality=FixQuality.GPS_FIX)


@pytest.fixture
def sample_navigation() -> Navigation:
    return Navigation(sog=0.0, cog=316.3, heading=23.6, speed=0.0)


@pytest.fixture
def sample_survey() -> Survey:
    return Survey(ukc_front=2.03, ukc_aft=2.03, tide=2.65, water_level=2.26)


@pytest.fixture
def sample_trackpoint(sample_position, sample_navigation, sample_gps) -> TrackPoint:
    return TrackPoint(
        index=0,
        timestamp=datetime(2026, 7, 1, 0, 0, 3),
        position=sample_position,
        navigation=sample_navigation,
        gps=sample_gps,
    )


@pytest.fixture
def sample_track(sample_trackpoint) -> Track:
    points = []
    for i in range(10):
        ts = datetime(2026, 7, 1, 0, 0, 3) + timedelta(seconds=i * 10)
        pos = Position(
            utm_easting=400020.10 + i * 0.1,
            utm_northing=5949091.26 + i * 0.05,
            utm_zone="32N",
        )
        nav = Navigation(sog=max(0.0, i * 1.5), cog=180.0 + i * 5, heading=23.5 + i * 0.1)
        pt = TrackPoint(index=i, timestamp=ts, position=pos, navigation=nav)
        points.append(pt)
    return Track(name="Test Track", points=points)
