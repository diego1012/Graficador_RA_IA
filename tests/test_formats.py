"""Format detection and fixture baseline tests."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from tests.conftest import fixture_path

EXPECTED_HASHES = {
    "test_RA_CSV.CSV": "3c3080ad9a0c6a14253687e17c017ba064cd93c285e9311e717b65158f1a1aa5",
    "CCW.csv": "0564489991583736eb57d7094d346f43ae91bab03ba03f4a0adf0c702f77e34d",
    "blackbox.csv": "e046a2c8f4c8bdd375f8ee54d0d097f6b6225f7f4b873762d0eb79eb86554f9d",
}


def test_fixture_hashes_are_unchanged() -> None:
    for filename, expected in EXPECTED_HASHES.items():
        digest = hashlib.sha256(fixture_path(filename).read_bytes()).hexdigest()
        assert digest == expected


def test_ra_metadata(upload: Callable[[str], object]) -> None:
    response = upload("test_RA_CSV.CSV")
    assert response.status_code == 201
    payload = response.json()

    assert payload["format"] == "ra"
    assert payload["rows_raw"] == 8094
    assert payload["rows_clean"] == 8094
    assert payload["dropped_columns_string"] == ["Date", "Time"]
    assert len(payload["variables"]) == 5
    assert payload["time"]["kind"] == "datetime"
    assert payload["time"]["start"] == "2026-07-17 17:06:14.499"
    assert payload["time"]["end"] == "2026-07-17 17:07:35.429"
    assert payload["variables"][0]["name"] == "test_RA.ActualVelocity"
    assert re.fullmatch(r"#[0-9A-Fa-f]{6}", payload["variables"][0]["color"])


def test_ccw_metadata(upload: Callable[[str], object]) -> None:
    response = upload("CCW.csv")
    assert response.status_code == 201
    payload = response.json()

    assert payload["format"] == "ccw"
    assert payload["rows_raw"] == 3488
    assert payload["rows_clean"] == 3469
    assert payload["dropped_columns_string"] == ["Time"]
    assert len(payload["variables"]) == 7
    assert payload["time"]["kind"] == "clock"
    assert payload["time"]["origin"] == "csv_clock"
    assert payload["time"]["start"] == pytest.approx(1002.3)
    assert payload["time"]["end"] == pytest.approx(1349.1)
    assert payload["time"]["sample_interval_s"] == pytest.approx(0.1)
    assert len(payload["time"]["values"]) == 3469


def test_blackbox_metadata(upload: Callable[[str], object]) -> None:
    response = upload("blackbox.csv")
    assert response.status_code == 201
    payload = response.json()

    assert payload["format"] == "blackbox"
    assert payload["rows_raw"] == 128
    assert payload["rows_clean"] == 128
    assert len(payload["variables"]) == 49
    assert len(payload["dropped_columns_string"]) == 14
    assert all(
        name.startswith(("DrvStatus", "InvControl", "RecControl", "Contactor"))
        for name in payload["dropped_columns_string"]
    )
    assert sum(variable["is_constant"] for variable in payload["variables"]) == 19
    assert payload["time"]["kind"] == "elapsed"
    assert payload["time"]["origin"] == "fixed_1ms"
    assert payload["time"]["start"] == 0.0
    assert payload["time"]["end"] == pytest.approx(0.127)
    assert payload["time"]["sample_interval_s"] == pytest.approx(0.001)


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == "1.8.0"
    assert payload["datasets"] == 0
