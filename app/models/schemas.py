"""Pydantic request/response models for the public API."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

COLOR_PATTERN = r"^#[0-9A-Fa-f]{6}$"
MAX_NAME_LENGTH = 80
MAX_UNIT_LENGTH = 4


class VariableInfo(BaseModel):
    id: str
    name: str
    color: str
    min: float
    max: float
    is_constant: bool


class TimeInfo(BaseModel):
    kind: Literal["datetime", "elapsed", "clock"]
    origin: Literal["csv_datetime", "csv_time", "csv_clock", "fixed_1ms", "row_index"]
    start: float | str
    end: float | str
    label: str
    sample_interval_s: float | None = None
    values: list[str | float] = Field(default_factory=list)


class DatasetMetadata(BaseModel):
    dataset_id: str
    filename: str
    format: str
    rows_raw: int
    rows_clean: int
    dropped_rows_empty: int
    dropped_rows_invalid_time: int
    dropped_rows_null: int
    dropped_columns_empty: int
    dropped_columns_string: list[str]
    time: TimeInfo
    variables: list[VariableInfo]


class PlotScale(BaseModel):
    """Linear rescale target: the variable's real [min, max] maps to [min, max]."""

    min: float = Field(allow_inf_nan=False)
    max: float = Field(allow_inf_nan=False)

    @model_validator(mode="after")
    def _check_order(self) -> PlotScale:
        if self.min >= self.max:
            raise ValueError("scale min must be lower than scale max")
        return self


class PlotVariable(BaseModel):
    id: str
    color: str = Field(pattern=COLOR_PATTERN)
    name: str | None = Field(default=None, max_length=MAX_NAME_LENGTH)
    unit: str | None = Field(default=None, max_length=MAX_UNIT_LENGTH)
    scale: PlotScale | None = None

    @field_validator("name", "unit", mode="after")
    @classmethod
    def _blank_to_none(cls, value: str | None) -> str | None:
        """Strip whitespace; an empty label means "use the default"."""
        if value is None:
            return None
        value = value.strip()
        return value or None


class PlotRange(BaseModel):
    start_index: int = Field(ge=0)
    end_index: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_order(self) -> PlotRange:
        if self.end_index < self.start_index:
            raise ValueError("end_index must be greater than or equal to start_index")
        return self


class PlotRequest(BaseModel):
    variables: list[PlotVariable] = Field(min_length=1, max_length=50)
    range: PlotRange

    @model_validator(mode="after")
    def _check_unique_variables(self) -> PlotRequest:
        ids = [variable.id for variable in self.variables]
        if len(ids) != len(set(ids)):
            raise ValueError("variables must be unique")
        return self


class PlotTraceInfo(BaseModel):
    id: str
    name: str
    original_name: str
    unit: str | None = None
    scale: PlotScale | None = None
    color: str
    # Real (unscaled) extremes of the plotted subrange, for the min/max box.
    range_min: float
    range_max: float


class PlotResponse(BaseModel):
    figure: dict[str, Any]
    rows_plotted: int
    variables: list[PlotTraceInfo]
