from pydantic import BaseModel, Field


class Navigation(BaseModel):
    sog: float | None = Field(default=None, ge=0.0, description="Speed Over Ground (knots)")
    cog: float | None = Field(
        default=None, ge=0.0, lt=360.0, description="Course Over Ground (degrees)"
    )
    heading: float | None = Field(default=None, ge=0.0, lt=360.0, description="Heading (degrees)")
    speed: float | None = Field(default=None, ge=0.0, description="Speed (knots)")
    acceleration: float | None = Field(default=None, description="Acceleration (knots/s)")
