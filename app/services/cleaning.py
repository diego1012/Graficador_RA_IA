"""DataFrame cleaning rules and cleaning metrics."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from app.services.errors import AppError
from app.services.ingest import NULL_TOKENS, ParsedDataset


@dataclass
class CleanedDataset:
    frame: pd.DataFrame
    format_name: str
    time_kind: Literal["datetime", "elapsed", "clock"]
    time_origin: Literal["csv_datetime", "csv_time", "csv_clock", "fixed_1ms", "row_index"]
    time_label: str
    sample_interval_s: float | None
    rows_raw: int
    dropped_rows_empty: int
    dropped_rows_invalid_time: int
    dropped_rows_null: int
    dropped_columns_empty: int
    dropped_columns_string: list[str]
    variable_ids: dict[str, str]

    @property
    def rows_clean(self) -> int:
        return len(self.frame)

    @property
    def columns(self) -> list[str]:
        return list(self.variable_ids.values())


def _is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip() == ""


def _normalize_number(value: object) -> object:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return np.nan
    text = str(value).strip()
    if text.lower() in NULL_TOKENS:
        return np.nan
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    return text


def _numeric_ratio(series: pd.Series, numeric: pd.Series) -> float:
    non_blank = int((~series.map(_is_blank)).sum())
    if non_blank == 0:
        return 0.0
    return int(numeric.notna().sum()) / non_blank


def _median_interval(index: pd.Index) -> float | None:
    values = np.asarray(index, dtype=float)
    diffs = np.diff(np.sort(values))
    diffs = diffs[diffs > 0]
    if not len(diffs):
        return None
    return round(float(np.median(diffs)), 9)


def clean_parsed(parsed: ParsedDataset) -> CleanedDataset:
    """Apply the project cleaning rules without mutating the source CSV."""
    frame = parsed.data.copy()
    frame.insert(0, "__time__", list(parsed.time_index))

    if parsed.time_kind == "datetime":
        time_series = pd.to_datetime(pd.Series(frame["__time__"]), errors="coerce")
    else:
        time_series = pd.to_numeric(pd.Series(frame["__time__"]), errors="coerce")

    invalid_time = time_series.isna()
    dropped_rows_invalid_time = int(invalid_time.sum())
    frame = frame.loc[~invalid_time].copy()
    frame["__time__"] = time_series.loc[~invalid_time].to_numpy()

    data_columns = [column for column in frame.columns if column != "__time__"]
    if data_columns:
        empty_rows = frame[data_columns].apply(
            lambda row: all(_is_blank(value) for value in row),
            axis=1,
        )
    else:
        empty_rows = pd.Series(True, index=frame.index)
    dropped_rows_empty = int(empty_rows.sum())
    frame = frame.loc[~empty_rows].copy()

    empty_columns = [column for column in data_columns if frame[column].map(_is_blank).all()]
    dropped_columns_empty = len(empty_columns)
    frame = frame.drop(columns=empty_columns)

    numeric_columns: list[str] = []
    string_columns: list[str] = []
    for column in [name for name in frame.columns if name != "__time__"]:
        series = frame[column]
        if pd.api.types.is_numeric_dtype(series):
            numeric_columns.append(column)
            continue

        numeric = pd.to_numeric(series.map(_normalize_number), errors="coerce")
        if _numeric_ratio(series, numeric) >= 0.9:
            frame[column] = numeric.astype(float)
            numeric_columns.append(column)
        else:
            string_columns.append(column)

    if not numeric_columns:
        raise AppError(
            "NO_NUMERIC_COLUMNS",
            "Después de limpiar el archivo no quedaron variables numéricas.",
            422,
        )

    frame = frame[["__time__", *numeric_columns]]
    before_null_drop = len(frame)
    frame = frame.dropna(subset=numeric_columns)
    dropped_rows_null = before_null_drop - len(frame)

    if frame.empty:
        raise AppError(
            "NO_ROWS_AFTER_CLEANING",
            "Todas las filas fueron descartadas durante la limpieza.",
            422,
        )

    frame = frame.set_index("__time__")
    if parsed.time_kind == "elapsed":
        elapsed = frame.index.astype(float)
        frame.index = pd.Index(np.round(elapsed - float(elapsed.min()), 9), dtype="float64")
    frame.index.name = None
    frame = frame.sort_index(kind="stable")

    sample_interval = parsed.sample_interval_s
    if sample_interval is None and parsed.time_kind == "elapsed":
        sample_interval = _median_interval(frame.index)

    variable_ids = {f"var_{index}": column for index, column in enumerate(numeric_columns, start=1)}

    return CleanedDataset(
        frame=frame,
        format_name=parsed.format_name,
        time_kind=parsed.time_kind,
        time_origin=parsed.time_origin,
        time_label=parsed.time_label,
        sample_interval_s=sample_interval,
        rows_raw=len(parsed.data),
        dropped_rows_empty=dropped_rows_empty,
        dropped_rows_invalid_time=dropped_rows_invalid_time,
        dropped_rows_null=dropped_rows_null,
        dropped_columns_empty=dropped_columns_empty,
        dropped_columns_string=[*parsed.time_column_names, *string_columns],
        variable_ids=variable_ids,
    )
