"""API lifecycle and error handling tests."""

from __future__ import annotations

from collections.abc import Callable

from fastapi.testclient import TestClient


def test_index_page(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert "Graficador Rockwell" in response.text


def test_index_has_theme_toggle(client: TestClient) -> None:
    html = client.get("/").text
    assert 'id="theme-toggle"' in html
    assert "/static/js/theme.js" in html
    assert client.get("/static/js/theme.js").status_code == 200


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_unsupported_extension(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "UNSUPPORTED_FORMAT"


def test_empty_csv(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "EMPTY_FILE"


def test_dataset_not_found(client: TestClient) -> None:
    response = client.get("/api/datasets/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "DATASET_NOT_FOUND"


def test_delete_dataset(
    upload: Callable[[str], object],
    client: TestClient,
) -> None:
    dataset = upload("CCW.csv").json()
    dataset_id = dataset["dataset_id"]

    response = client.get(f"/api/datasets/{dataset_id}")
    assert response.status_code == 200
    assert response.json()["dataset_id"] == dataset_id

    response = client.delete(f"/api/datasets/{dataset_id}")
    assert response.status_code == 204

    response = client.get(f"/api/datasets/{dataset_id}")
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "DATASET_NOT_FOUND"


def test_api_cache_header(
    upload: Callable[[str], object],
    client: TestClient,
) -> None:
    dataset = upload("CCW.csv").json()
    response = client.get(f"/api/datasets/{dataset['dataset_id']}")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_page_and_static_are_revalidated(client: TestClient) -> None:
    for path in ("/", "/static/js/app.js", "/static/css/app.css"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache", path


def test_assets_are_fingerprinted(client: TestClient) -> None:
    import hashlib
    import re
    from pathlib import Path

    html = client.get("/").text
    match = re.search(r'src="/static/js/app\.js\?v=([0-9a-f]{12})"', html)
    assert match, "app.js must be referenced with a content fingerprint"
    app_js = Path(__file__).resolve().parents[1] / "app" / "static" / "js" / "app.js"
    assert match.group(1) == hashlib.sha256(app_js.read_bytes()).hexdigest()[:12]
    assert client.get(f"/static/js/app.js?v={match.group(1)}").status_code == 200
    assert "url_for('static'" not in html
