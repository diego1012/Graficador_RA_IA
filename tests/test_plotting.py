"""Plot endpoint tests: traces, colors and range validation."""

from __future__ import annotations

import base64
from collections.abc import Callable

import numpy as np
import pytest


def _array(value: object) -> list[float]:
    """Decode a Plotly array, which may be a base64 typed array (``bdata``)."""
    if isinstance(value, dict) and "bdata" in value:
        return np.frombuffer(base64.b64decode(value["bdata"]), dtype=value["dtype"]).tolist()
    return list(value)


def _dataset(upload: Callable[[str], object], filename: str) -> dict:
    response = upload(filename)
    assert response.status_code == 201
    return response.json()


def test_plot_two_variables_with_requested_colors(
    upload: Callable[[str], object],
    client,
) -> None:
    dataset = _dataset(upload, "CCW.csv")
    first, second = dataset["variables"][:2]
    payload = {
        "variables": [
            {"id": first["id"], "color": "#112233"},
            {"id": second["id"], "color": "#aabbcc"},
        ],
        "range": {"start_index": 10, "end_index": 100},
    }

    response = client.post(
        f"/api/datasets/{dataset['dataset_id']}/plot",
        json=payload,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["rows_plotted"] == 91
    assert len(result["figure"]["data"]) == 2
    assert [trace["line"]["color"] for trace in result["figure"]["data"]] == [
        "#112233",
        "#aabbcc",
    ]
    assert len(result["figure"]["data"][0]["x"]) == 91
    assert result["figure"]["layout"]["xaxis"]["type"] == "date"
    assert result["figure"]["layout"]["xaxis"]["tickformat"] == "%M:%S"
    assert result["figure"]["data"][0]["x"][0] == "1970-01-01 00:16:43.300"
    assert result["figure"]["data"][0]["x"][-1] == "1970-01-01 00:16:52.300"
    assert result["variables"][0]["id"] == first["id"]


def test_plot_single_row_range(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "blackbox.csv")
    payload = {
        "variables": [{"id": dataset["variables"][1]["id"], "color": "#00aa88"}],
        "range": {"start_index": 0, "end_index": 0},
    }
    response = client.post(
        f"/api/datasets/{dataset['dataset_id']}/plot",
        json=payload,
    )
    assert response.status_code == 200
    result = response.json()
    assert result["rows_plotted"] == 1
    assert result["figure"]["data"][0]["x"] == [0.0]


def test_plot_datetime_uses_iso_strings(
    upload: Callable[[str], object],
    client,
) -> None:
    dataset = _dataset(upload, "test_RA_CSV.CSV")
    payload = {
        "variables": [{"id": dataset["variables"][0]["id"], "color": "#123456"}],
        "range": {"start_index": 0, "end_index": 1},
    }
    response = client.post(
        f"/api/datasets/{dataset['dataset_id']}/plot",
        json=payload,
    )
    assert response.status_code == 200
    x_values = response.json()["figure"]["data"][0]["x"]
    assert x_values == [
        "2026-07-17 17:06:14.499",
        "2026-07-17 17:06:14.509",
    ]


def test_plot_range_out_of_bounds(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    payload = {
        "variables": [{"id": dataset["variables"][0]["id"], "color": "#112233"}],
        "range": {
            "start_index": 0,
            "end_index": dataset["rows_clean"],
        },
    }
    response = client.post(
        f"/api/datasets/{dataset['dataset_id']}/plot",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_RANGE"


def test_plot_reversed_range(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    payload = {
        "variables": [{"id": dataset["variables"][0]["id"], "color": "#112233"}],
        "range": {"start_index": 100, "end_index": 10},
    }
    response = client.post(
        f"/api/datasets/{dataset['dataset_id']}/plot",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_RANGE"


def test_plot_unknown_variable(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    payload = {
        "variables": [{"id": "var_missing", "color": "#112233"}],
        "range": {"start_index": 0, "end_index": 10},
    }
    response = client.post(
        f"/api/datasets/{dataset['dataset_id']}/plot",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_VARIABLE"


def test_plot_invalid_color(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    payload = {
        "variables": [{"id": dataset["variables"][0]["id"], "color": "red"}],
        "range": {"start_index": 0, "end_index": 10},
    }
    response = client.post(
        f"/api/datasets/{dataset['dataset_id']}/plot",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_COLOR"


def test_plot_duplicate_variables(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    variable = dataset["variables"][0]
    payload = {
        "variables": [
            {"id": variable["id"], "color": "#112233"},
            {"id": variable["id"], "color": "#445566"},
        ],
        "range": {"start_index": 0, "end_index": 10},
    }
    response = client.post(
        f"/api/datasets/{dataset['dataset_id']}/plot",
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "INVALID_VARIABLE"


def test_plot_custom_name_and_unit(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    first, second = dataset["variables"][:2]
    payload = {
        "variables": [
            {"id": first["id"], "color": "#112233", "name": "  Tensión L1 ", "unit": "V"},
            {"id": second["id"], "color": "#aabbcc", "name": "", "unit": " "},
        ],
        "range": {"start_index": 0, "end_index": 10},
    }
    response = client.post(f"/api/datasets/{dataset['dataset_id']}/plot", json=payload)
    assert response.status_code == 200
    result = response.json()
    traces = result["figure"]["data"]
    assert traces[0]["name"] == "Tensión L1 [V]"
    assert traces[0]["meta"] == ["Tensión L1", "V", ""]
    assert traces[1]["meta"] == [second["name"], "", ""]
    assert "%{meta[0]}" in traces[0]["hovertemplate"]
    assert "%{meta[1]}" in traces[0]["hovertemplate"]
    assert traces[1]["name"] == second["name"]
    first_info = {
        key: value
        for key, value in result["variables"][0].items()
        if key not in ("range_min", "range_max")
    }
    assert first_info == {
        "id": first["id"],
        "name": "Tensión L1",
        "original_name": first["name"],
        "unit": "V",
        "scale": None,
        "color": "#112233",
    }
    assert result["variables"][1]["unit"] is None
    # Mixed units: the shared Y axis keeps the generic title.
    assert result["figure"]["layout"]["yaxis"]["title"]["text"] == "Valor"


def test_plot_shared_unit_in_y_axis(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    first, second = dataset["variables"][:2]
    payload = {
        "variables": [
            {"id": first["id"], "color": "#112233", "unit": "A"},
            {"id": second["id"], "color": "#aabbcc", "unit": "A"},
        ],
        "range": {"start_index": 0, "end_index": 10},
    }
    response = client.post(f"/api/datasets/{dataset['dataset_id']}/plot", json=payload)
    assert response.status_code == 200
    assert response.json()["figure"]["layout"]["yaxis"]["title"]["text"] == "Valor [A]"


def test_plot_unit_too_long(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    payload = {
        "variables": [{"id": dataset["variables"][0]["id"], "color": "#112233", "unit": "kVArh"}],
        "range": {"start_index": 0, "end_index": 10},
    }
    response = client.post(f"/api/datasets/{dataset['dataset_id']}/plot", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_plot_name_is_not_a_template(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    payload = {
        "variables": [{"id": dataset["variables"][0]["id"], "color": "#112233", "name": "x %{y}"}],
        "range": {"start_index": 0, "end_index": 10},
    }
    response = client.post(f"/api/datasets/{dataset['dataset_id']}/plot", json=payload)
    assert response.status_code == 200
    trace = response.json()["figure"]["data"][0]
    assert trace["meta"][0] == "x %{y}"
    assert "x %{y}" not in trace["hovertemplate"]


def test_plot_scaled_variable(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    variable = next(v for v in dataset["variables"] if not v["is_constant"])
    payload = {
        "variables": [
            {
                "id": variable["id"],
                "color": "#112233",
                "unit": "%",
                "scale": {"min": 0, "max": 100},
            }
        ],
        "range": {"start_index": 0, "end_index": dataset["rows_clean"] - 1},
    }
    response = client.post(f"/api/datasets/{dataset['dataset_id']}/plot", json=payload)
    assert response.status_code == 200
    result = response.json()
    trace = result["figure"]["data"][0]
    # The real min/max of the whole dataset map onto the requested bounds.
    y_values = _array(trace["y"])
    real_values = _array(trace["customdata"])
    assert min(y_values) == pytest.approx(0)
    assert max(y_values) == pytest.approx(100)
    # Real values travel in customdata so the hover can show them.
    assert min(real_values) == pytest.approx(variable["min"])
    assert max(real_values) == pytest.approx(variable["max"])
    assert "Real: %{customdata" in trace["hovertemplate"]
    assert trace["name"] == f"{variable['name']} [%] · esc. 0…100"
    assert trace["meta"][2] == "esc. 0…100"
    assert result["variables"][0]["scale"] == {"min": 0, "max": 100}


def test_plot_scale_uses_whole_dataset_range(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    variable = next(v for v in dataset["variables"] if not v["is_constant"])
    payload = {
        "variables": [
            {"id": variable["id"], "color": "#112233", "scale": {"min": -1, "max": 1}},
        ],
        "range": {"start_index": 0, "end_index": 0},
    }
    response = client.post(f"/api/datasets/{dataset['dataset_id']}/plot", json=payload)
    trace = response.json()["figure"]["data"][0]
    real = _array(trace["customdata"])[0]
    expected = -1 + (real - variable["min"]) * 2 / (variable["max"] - variable["min"])
    assert _array(trace["y"])[0] == pytest.approx(expected)


def test_plot_unscaled_has_no_customdata(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    payload = {
        "variables": [{"id": dataset["variables"][0]["id"], "color": "#112233"}],
        "range": {"start_index": 0, "end_index": 5},
    }
    trace = client.post(f"/api/datasets/{dataset['dataset_id']}/plot", json=payload).json()[
        "figure"
    ]["data"][0]
    assert "customdata" not in trace
    assert trace["meta"][2] == ""


@pytest.mark.parametrize(
    "scale",
    [{"min": 10, "max": 10}, {"min": 5, "max": 1}, {"min": 0}, {"min": "a", "max": 1}],
)
def test_plot_invalid_scale(upload: Callable[[str], object], client, scale: dict) -> None:
    dataset = _dataset(upload, "CCW.csv")
    payload = {
        "variables": [{"id": dataset["variables"][0]["id"], "color": "#112233", "scale": scale}],
        "range": {"start_index": 0, "end_index": 5},
    }
    response = client.post(f"/api/datasets/{dataset['dataset_id']}/plot", json=payload)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "VALIDATION_ERROR"


def test_rescale_constant_maps_to_min() -> None:
    from app.models.schemas import PlotScale
    from app.services.plotting import rescale

    result = rescale(np.array([3.0, 3.0]), 3.0, 3.0, PlotScale(min=2, max=8))
    assert result.tolist() == [2.0, 2.0]


def test_plot_reports_subrange_extremes(upload: Callable[[str], object], client) -> None:
    dataset = _dataset(upload, "CCW.csv")
    variable = next(v for v in dataset["variables"] if not v["is_constant"])
    payload = {
        "variables": [
            {"id": variable["id"], "color": "#112233", "scale": {"min": 0, "max": 100}},
        ],
        "range": {"start_index": 10, "end_index": 200},
    }
    response = client.post(f"/api/datasets/{dataset['dataset_id']}/plot", json=payload)
    assert response.status_code == 200
    body = response.json()
    real = _array(body["figure"]["data"][0]["customdata"])
    info = body["variables"][0]
    # Extremes are real values of the plotted subrange, not the whole dataset.
    assert info["range_min"] == pytest.approx(min(real))
    assert info["range_max"] == pytest.approx(max(real))
    assert variable["min"] <= info["range_min"] <= info["range_max"] <= variable["max"]
