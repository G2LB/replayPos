# Project Rules

- Use Python 3.13 features only. No compatibility shims for older versions.
- Always use uv for package management, not pip or pipenv.
- All data models use Pydantic v2 with typed fields.
- Database layer uses SQLAlchemy 2.0 mapped_column style.
- Internal datamodel uses UTM (Easting/Northing/Zone). Convert to WGS84 only for map rendering via pyproj.
