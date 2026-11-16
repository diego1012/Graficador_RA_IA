"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.store import store

FIXTURES = Path(__file__).resolve().parents[1] / "test_csv"


def fixture_path(filename: str) -> Path:
    """Path of a reference CSV; skip the test when it is not available.

    ``test_csv/`` holds real equipment data and is not published with the
    repository, so a fresh clone runs only the tests that do not need it.
    """
    path = FIXTURES / filename
    if not path.is_file():
        pytest.skip(f"Fixture no disponible: test_csv/{filename}")
    return path


@pytest.fixture(autouse=True)
def clear_dataset_store() -> Iterator[None]:
    store.clear()
    yield
    store.clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def upload(client: TestClient) -> Callable[[str], object]:
    def _upload(filename: str):
        path = fixture_path(filename)
        with path.open("rb") as handle:
            return client.post(
                "/api/datasets",
                files={"file": (filename, handle, "text/csv")},
            )

    return _upload
