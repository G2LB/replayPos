from pydantic import BaseModel, Field


class Survey(BaseModel):
    ukc_front: float | None = Field(default=None, description="Under-keel clearance front (meters)")
    ukc_aft: float | None = Field(default=None, description="Under-keel clearance aft (meters)")
    tide: float | None = Field(default=None, description="Tide level (meters)")
    water_level: float | None = Field(default=None, description="Water level (meters)")
    depth: float | None = Field(default=None, description="Water depth (meters)")
