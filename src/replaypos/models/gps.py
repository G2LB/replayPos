from enum import IntEnum

from pydantic import BaseModel, Field


class FixQuality(IntEnum):
    NO_FIX = 0
    GPS_FIX = 1
    DGPS_FIX = 2
    PPS_FIX = 3
    RTK_FIX = 4
    FLOAT_RTK = 5
    ESTIMATED = 6
    MANUAL = 7
    SIMULATION = 8


class GPS(BaseModel):
    accuracy: float | None = Field(default=None, ge=0.0, description="GPS accuracy (meters)")
    satellites: int | None = Field(default=None, ge=0, description="Number of satellites")
    fix_quality: FixQuality | None = Field(default=None, description="Fix quality")
    hdop: float | None = Field(default=None, ge=0.0, description="Horizontal dilution of precision")
    pdop: float | None = Field(default=None, ge=0.0, description="Position dilution of precision")
