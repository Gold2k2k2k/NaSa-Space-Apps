"""Shared strict analysis-option contracts for engine, CLI, and HTTP callers."""
from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, StrictBool, model_validator


class AnalysisOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, allow_inf_nan=False)

    year_start: int = Field(default=2000, ge=2000, le=2026)
    year_end: int = Field(default=2026, ge=2000, le=2026)
    focus_year: int = Field(default=2026, ge=2000, le=2026)
    focus_month: int = Field(default=9, ge=1, le=12)
    mode: Literal["harmonized", "raw"] = "harmonized"
    flare_guard: StrictBool = True
    confidence_min: Literal["low", "nominal", "high"] = "low"
    persona: Literal["responder", "scientist", "land_manager", "firefighter"] = "responder"

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.year_start > self.year_end:
            raise ValueError("year_start must not exceed year_end")
        if not self.year_start <= self.focus_year <= self.year_end:
            raise ValueError("focus_year must be inside the requested year window")
        return self


class AnalysisRequest(AnalysisOptions):
    aoi_id: str | None = Field(default=None, max_length=80)
    name: str | None = Field(default=None, max_length=255)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    custom_lat: float | None = Field(default=None, ge=-90, le=90)
    custom_lon: float | None = Field(default=None, ge=-180, le=180)
    radius_km: float = Field(default=60, gt=0, le=2000)
    geojson: dict[str, Any] | None = None
    geometry: dict[str, Any] | None = None
    polygon: list[Any] | None = None
    reference_time: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.year_start > self.year_end:
            raise ValueError("year_start must not exceed year_end")
        if "focus_year" in self.model_fields_set and not self.year_start <= self.focus_year <= self.year_end:
            raise ValueError("focus_year must be inside the requested year window")
        return self


class WhatIfBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    field: Literal["mode", "flare_guard", "focus_year", "focus_month", "focus_period",
                   "confidence_min", "persona", "focus_to_median", "options"]
    value: Any


def validate_options(request: dict[str, Any], aoi: dict[str, Any]) -> dict[str, Any]:
    options = {key: request[key] for key in AnalysisOptions.model_fields if key in request}
    if "focus_year" not in options:
        # A default follows the requested window; an explicit invalid focus is
        # rejected by the model instead of silently analyzing a different year.
        start = options.get("year_start", 2000)
        end = options.get("year_end", 2026)
        if type(start) is int and type(end) is int:
            options["focus_year"] = min(end, max(start, aoi.get("default_focus_year", 2026)))
    options.setdefault("focus_month", aoi.get("default_focus_month", 9))
    return AnalysisOptions.model_validate(options).model_dump()


def counterfactual_options(options, field, value):
    """Validate actual values rather than coercing typos and strings to choices."""
    updated = dict(options)
    if field == "options":
        if not isinstance(value, dict) or not value or set(value) - set(AnalysisOptions.model_fields):
            raise ValueError("options must be a nonempty object of supported analysis options")
        updated.update(value)
    elif field == "focus_period":
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            raise ValueError("focus_period must contain [year, month]")
        updated["focus_year"], updated["focus_month"] = value
    elif field in ("mode", "flare_guard", "focus_year", "focus_month", "confidence_min", "persona"):
        updated[field] = value
    elif field == "focus_to_median":
        if type(value) is not bool:
            raise ValueError("focus_to_median requires a boolean")
    else:
        raise ValueError(f"Unsupported what_if field: {field!r}")
    return AnalysisOptions.model_validate(updated).model_dump()
