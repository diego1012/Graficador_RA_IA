"""Cleaning rules tests with small synthetic CSV payloads."""

from __future__ import annotations

import pytest

from app.services.cleaning import clean_parsed
from app.services.errors import AppError
from app.services.ingest import detect_delimiter, parse_csv


def clean_text(text: str):
    return clean_parsed(parse_csv(text.encode("utf-8"), "synthetic.csv"))


def test_null_rows_are_dropped() -> None:
    cleaned = clean_text("Time,A,B\n00:00.0,1,2\n00:00.1,,3\n00:00.2,4,5\n")
    assert cleaned.rows_raw == 3
    assert cleaned.rows_clean == 2
    assert cleaned.dropped_rows_null == 1


def test_string_columns_are_dropped() -> None:
    cleaned = clean_text(
        "Time,A,Status\n00:00.0,1,OK\n00:00.1,2,OK\n",
    )
    assert cleaned.dropped_columns_string == ["Time", "Status"]
    assert cleaned.columns == ["A"]
    assert cleaned.frame["A"].tolist() == [1.0, 2.0]


def test_decimal_comma_is_accepted() -> None:
    cleaned = clean_text('Time,A\n00:00.0,"1,5"\n00:00.1,"2,5"\n')
    assert cleaned.frame["A"].tolist() == [1.5, 2.5]


def test_no_numeric_columns_raises() -> None:
    with pytest.raises(AppError) as error:
        clean_text("Time,A,B\n00:00.0,x,y\n00:00.1,z,w\n")
    assert error.value.code == "NO_NUMERIC_COLUMNS"


def test_no_rows_after_cleaning_raises() -> None:
    with pytest.raises(AppError) as error:
        clean_text("Time,A,B\n00:00.0,1,\n00:00.1,,2\n")
    assert error.value.code == "NO_ROWS_AFTER_CLEANING"


def test_ra_delimiter_is_comma_despite_semicolon_milliseconds() -> None:
    raw = "Date,Time,A\n17/07/2026,17:06:14;499,1\n17/07/2026,17:06:14;509,2\n"
    assert detect_delimiter(raw) == ","


def test_semicolon_delimited_csv_is_detected() -> None:
    raw = "Time;A;B\n00:00.0;1;2\n00:00.1;3;4\n"
    assert detect_delimiter(raw) == ";"


def test_cleaning_does_not_modify_source_bytes() -> None:
    raw = b"Time,A\n00:00.0,1\n00:00.1,2\n"
    original = bytes(raw)
    clean_parsed(parse_csv(raw, "synthetic.csv"))
    assert raw == original
