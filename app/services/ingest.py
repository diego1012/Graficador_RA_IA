"""CSV decoding, delimiter/header detection and format adapters."""

from __future__ import annotations

import csv
import io
import math
import re
from collections import Counter
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from app.config import MAX_ROWS
from app.services.errors import AppError

NULL_TOKENS = {"", "na", "n/a", "nan", "null", "-", "--"}
TIME_HEADERS = {"time", "timestamp", "hora", "tiempo", "t"}
DATE_HEADERS = {"date", "fecha"}
TIME_VALUE_RE = re.compile(r"^\d{1,3}:\d{1,2}(?::\d{1,2})?(?:[.,]\d+)?$")
HEX_VALUE_RE = re.compile(r"^0x[0-9a-fA-F]+$")
DATETIME_FORMATS = (
    "%d/%m/%Y %H:%M:%S.%f",
    "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%d/%m/%Y %H:%M",
    "%Y-%m-%d %H:%M",
    "%d/%m/%Y",
    "%Y-%m-%d",
)


@dataclass
class ParsedDataset:
    format_name: str
    time_index: pd.Index
    data: pd.DataFrame
    time_kind: Literal["datetime", "elapsed", "clock"]
    time_origin: Literal["csv_datetime", "csv_time", "csv_clock", "fixed_1ms", "row_index"]
    time_label: str
    sample_interval_s: float | None
    time_column_names: list[str]


def _is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip() == ""


def _looks_numeric(value: str) -> bool:
    text = value.strip()
    if not text or text.lower() in NULL_TOKENS:
        return False
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        float(text)
    except ValueError:
        return False
    return True


def _is_time_value(value: str) -> bool:
    text = value.strip().replace(";", ".")
    return bool(TIME_VALUE_RE.match(text))


def decode_bytes(raw: bytes) -> str:
    if not raw or not raw.strip():
        raise AppError("EMPTY_FILE", "El archivo está vacío.", 400)

    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        encodings = ("utf-16",)
    else:
        encodings = ("utf-8-sig", "cp1252", "latin-1")

    for encoding in encodings:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise AppError(
        "UNSUPPORTED_FORMAT",
        "No se pudo decodificar el archivo. Se probaron UTF-8, UTF-16 y Latin-1.",
        400,
    )


def _read_rows(text: str, delimiter: str) -> list[list[str]]:
    rows: list[list[str]] = []
    try:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        for row in reader:
            cleaned = [cell.strip() for cell in row]
            if cleaned:
                cleaned[0] = cleaned[0].lstrip("\ufeff")
            rows.append(cleaned)
    except csv.Error as exc:
        raise AppError(
            "UNSUPPORTED_FORMAT",
            "El CSV no tiene una estructura válida.",
            400,
            {"reason": str(exc)},
        ) from exc
    return rows


def detect_delimiter(text: str) -> str:
    candidates = [",", ";", "\t", "|"]
    best_delimiter = ","
    best_score: tuple[bool, int, float] = (False, 0, 0.0)

    for delimiter in candidates:
        rows = _read_rows(text, delimiter)
        widths = [len(row) for row in rows[:25] if any(cell for cell in row)]
        if not widths:
            continue
        modal_width, modal_count = Counter(widths).most_common(1)[0]
        consistency = modal_count / len(widths)
        score = (consistency >= 0.8, modal_width, consistency)
        if score > best_score:
            best_score = score
            best_delimiter = delimiter

    return best_delimiter


def detect_header(rows: list[list[str]]) -> int:
    best_score = float("-inf")
    best_index = 0

    for index, row in enumerate(rows[:25]):
        non_empty = [cell for cell in row if cell]
        if len(non_empty) < 2:
            continue

        width = len(row)
        following = rows[index + 1 : index + 6]
        consistent = sum(
            1
            for next_row in following
            if len(next_row) >= max(2, width - 1) and sum(1 for cell in next_row if cell) >= 2
        )
        has_time_header = any(cell.lower() in TIME_HEADERS | DATE_HEADERS for cell in row)
        numeric_below = sum(
            1
            for next_row in following[:3]
            for cell in next_row
            if cell and (_looks_numeric(cell) or _is_time_value(cell))
        )

        score = (
            len(non_empty) * 2
            + consistent * 3
            + (6 if has_time_header else 0)
            + (2 if numeric_below else 0)
            - index * 0.01
        )
        if score > best_score:
            best_score = score
            best_index = index

    return best_index


def _dedupe_headers(headers: list[str]) -> list[str]:
    result: list[str] = []
    seen: Counter[str] = Counter()
    for index, header in enumerate(headers):
        name = header.strip() or f"column_{index + 1}"
        seen[name] += 1
        if seen[name] > 1:
            name = f"{name} ({seen[name]})"
        result.append(name)
    return result


def _parse_clock_seconds(values: list[object]) -> np.ndarray:
    parsed = np.full(len(values), np.nan, dtype=float)
    for index, value in enumerate(values):
        if _is_blank(value):
            continue
        text = str(value).strip().replace(",", ".")
        if text.lower().endswith("s"):
            text = text[:-1].strip()
        parts = text.split(":")
        try:
            if len(parts) == 1:
                parsed[index] = float(parts[0])
            elif len(parts) == 2:
                parsed[index] = float(parts[0]) * 60 + float(parts[1])
            elif len(parts) == 3:
                parsed[index] = float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        except ValueError:
            continue
    return parsed


def _parse_datetime(
    values: list[object], time_values: list[object] | None = None
) -> pd.DatetimeIndex:
    base = pd.Series(values, dtype="object").astype(str).str.strip()
    if time_values is not None:
        clock = (
            pd.Series(time_values, dtype="object")
            .astype(str)
            .str.strip()
            .str.replace(";", ".", regex=False)
        )
        combined = base + " " + clock
    else:
        combined = base.str.replace(";", ".", regex=False)

    best = pd.Series(pd.NaT, index=combined.index)
    best_count = 0
    for fmt in DATETIME_FORMATS:
        parsed = pd.to_datetime(combined, format=fmt, errors="coerce", dayfirst=True)
        count = int(parsed.notna().sum())
        if count > best_count:
            best = parsed
            best_count = count

    if best_count < len(combined):
        mixed = pd.to_datetime(combined, errors="coerce", dayfirst=True, format="mixed")
        if int(mixed.notna().sum()) > best_count:
            best = mixed

    return pd.DatetimeIndex(best)


def _median_interval(values: np.ndarray) -> float | None:
    diffs = np.diff(np.sort(values[np.isfinite(values)]))
    diffs = diffs[diffs > 0]
    if not len(diffs):
        return None
    return round(float(np.median(diffs)), 9)


def _parse_time_column(
    frame: pd.DataFrame,
    column_index: int,
    format_name: str,
) -> ParsedDataset:
    column_name = str(frame.columns[column_index])
    raw_values = frame.iloc[:, column_index].tolist()
    seconds = _parse_clock_seconds(raw_values)
    valid_seconds = int(np.isfinite(seconds).sum())

    if valid_seconds >= max(1, int(len(seconds) * 0.5)):
        valid = seconds[np.isfinite(seconds)]
        if format_name == "ccw":
            return ParsedDataset(
                format_name=format_name,
                time_index=pd.Index(np.round(seconds, 9), dtype="float64"),
                data=frame.drop(columns=[column_name]),
                time_kind="clock",
                time_origin="csv_clock",
                time_label="Tiempo (mm:ss.s)",
                sample_interval_s=_median_interval(valid),
                time_column_names=[column_name],
            )

        elapsed = seconds - float(valid.min())
        elapsed = np.round(elapsed, 9)
        return ParsedDataset(
            format_name=format_name,
            time_index=pd.Index(elapsed, dtype="float64"),
            data=frame.drop(columns=[column_name]),
            time_kind="elapsed",
            time_origin="csv_time",
            time_label="Tiempo (s)",
            sample_interval_s=_median_interval(valid),
            time_column_names=[column_name],
        )

    datetimes = _parse_datetime(raw_values)
    if int(datetimes.notna().sum()) >= max(1, int(len(datetimes) * 0.5)):
        return ParsedDataset(
            format_name=format_name,
            time_index=datetimes,
            data=frame.drop(columns=[column_name]),
            time_kind="datetime",
            time_origin="csv_datetime",
            time_label="Fecha y hora",
            sample_interval_s=None,
            time_column_names=[column_name],
        )

    return _parse_row_index(frame, format_name)


def _parse_row_index(frame: pd.DataFrame, format_name: str) -> ParsedDataset:
    time_index = pd.Index(np.arange(len(frame), dtype=float), dtype="float64")
    return ParsedDataset(
        format_name=format_name,
        time_index=time_index,
        data=frame.copy(),
        time_kind="elapsed",
        time_origin="row_index",
        time_label="Tiempo (s)",
        sample_interval_s=1.0,
        time_column_names=[],
    )


def parse_csv(raw: bytes, filename: str = "dataset.csv") -> ParsedDataset:
    """Decode and parse a CSV payload into a time-indexed raw dataset."""
    del filename  # Reserved for future filename-based format hints.
    text = decode_bytes(raw)
    delimiter = detect_delimiter(text)
    rows = _read_rows(text, delimiter)

    if not rows:
        raise AppError("EMPTY_FILE", "El archivo no contiene filas.", 400)

    header_index = detect_header(rows)
    headers = rows[header_index]
    data_rows = rows[header_index + 1 :]

    if not data_rows:
        raise AppError("EMPTY_FILE", "El archivo no contiene filas de datos.", 400)
    if len(data_rows) > MAX_ROWS:
        raise AppError(
            "FILE_TOO_LARGE",
            f"El archivo supera el máximo de {MAX_ROWS} filas.",
            413,
            {"rows": len(data_rows), "max_rows": MAX_ROWS},
        )

    width = max([len(headers), *[len(row) for row in data_rows]])
    headers = _dedupe_headers(headers + [f"column_{i + 1}" for i in range(len(headers), width)])
    padded_rows = [(row + [""] * width)[:width] for row in data_rows]
    frame = pd.DataFrame(padded_rows, columns=headers, dtype="object")

    normalized = [header.lower() for header in headers]
    date_index = next(
        (index for index, header in enumerate(normalized) if header in DATE_HEADERS),
        None,
    )
    time_index = next(
        (index for index, header in enumerate(normalized) if header in TIME_HEADERS),
        None,
    )

    if date_index is not None and time_index is not None and date_index != time_index:
        date_column = str(frame.columns[date_index])
        time_column = str(frame.columns[time_index])
        datetimes = _parse_datetime(
            frame.iloc[:, date_index].tolist(),
            frame.iloc[:, time_index].tolist(),
        )
        return ParsedDataset(
            format_name="ra",
            time_index=datetimes,
            data=frame.drop(columns=[date_column, time_column]),
            time_kind="datetime",
            time_origin="csv_datetime",
            time_label="Fecha y hora",
            sample_interval_s=None,
            time_column_names=[date_column, time_column],
        )

    if time_index is not None:
        format_name = "ccw" if header_index > 0 else "generic"
        return _parse_time_column(frame, time_index, format_name)

    has_hex_values = any(
        HEX_VALUE_RE.match(cell) for row in padded_rows[:50] for cell in row if cell
    )
    if has_hex_values:
        return ParsedDataset(
            format_name="blackbox",
            time_index=pd.Index(np.arange(len(frame), dtype=float) * 0.001, dtype="float64"),
            data=frame.copy(),
            time_kind="elapsed",
            time_origin="fixed_1ms",
            time_label="Tiempo (s)",
            sample_interval_s=0.001,
            time_column_names=[],
        )

    for index in range(min(3, len(headers))):
        sample = [row[index] for row in padded_rows[:20] if row[index]]
        if sample and sum(_is_time_value(value) for value in sample) >= max(
            1, int(len(sample) * 0.8)
        ):
            return _parse_time_column(frame, index, "generic")

    return _parse_row_index(frame, "generic")
