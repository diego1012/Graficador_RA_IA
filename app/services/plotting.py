"""Plotly figure construction for a selected dataset range."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from app.models.schemas import (
    PlotRequest,
    PlotResponse,
    PlotScale,
    PlotTraceInfo,
)
from app.services.errors import AppError
from app.services.store import StoredDataset

MAX_GL_POINTS = 5000
CLOCK_EPOCH = pd.Timestamp("1970-01-01")


def _format_clock(seconds: float) -> str:
    total = abs(float(seconds))
    minutes = int(total // 60)
    rest = total - minutes * 60
    return f"{minutes:02d}:{rest:04.1f}"


def _x_values(index: pd.Index, time_kind: str) -> list[str | float]:
    if time_kind == "datetime":
        return [timestamp.isoformat(sep=" ", timespec="milliseconds") for timestamp in index]
    if time_kind == "clock":
        return [
            (CLOCK_EPOCH + pd.to_timedelta(float(value), unit="s")).isoformat(
                sep=" ",
                timespec="milliseconds",
            )
            for value in index
        ]
    return [round(float(value), 9) for value in index]


def _axis_config(stored: StoredDataset) -> dict:
    index = stored.cleaned.frame.index
    if stored.cleaned.time_kind == "clock":
        return {
            "title": {"text": stored.cleaned.time_label},
            "type": "date",
            "tickformat": "%M:%S",
            "hoverformat": "%M:%S.%L",
            "showgrid": True,
            "zeroline": False,
        }
    if stored.cleaned.time_kind == "datetime":
        span_seconds = (index[-1] - index[0]).total_seconds()
        if span_seconds < 3600:
            tickformat = "%H:%M:%S.%L"
        elif span_seconds < 86400:
            tickformat = "%H:%M:%S"
        else:
            tickformat = "%d/%m\n%H:%M"
        return {
            "title": {"text": stored.cleaned.time_label},
            "type": "date",
            "tickformat": tickformat,
            "hoverformat": "%d/%m/%Y %H:%M:%S.%L",
            "showgrid": True,
            "zeroline": False,
        }
    return {
        "title": {"text": stored.cleaned.time_label},
        "showgrid": True,
        "zeroline": False,
    }


def _format_bound(value: float) -> str:
    return f"{value:g}"


def scale_label(scale: PlotScale | None) -> str:
    """Legend suffix that flags a rescaled trace, e.g. "esc. 0…100"."""
    if scale is None:
        return ""
    return f"esc. {_format_bound(scale.min)}…{_format_bound(scale.max)}"


def legend_name(name: str, unit: str | None, scale: PlotScale | None) -> str:
    text = f"{name} [{unit}]" if unit else name
    suffix = scale_label(scale)
    return f"{text} · {suffix}" if suffix else text


def rescale(
    values: np.ndarray,
    real_min: float,
    real_max: float,
    scale: PlotScale,
) -> np.ndarray:
    """Map [real_min, real_max] linearly onto [scale.min, scale.max].

    A constant variable (real_min == real_max) has no span to map, so every
    value is placed at ``scale.min``.
    """
    span = real_max - real_min
    if span == 0:
        return np.full_like(values, scale.min, dtype=float)
    return scale.min + (values - real_min) * (scale.max - scale.min) / span


def _y_axis_title(units: set[str | None]) -> str:
    """Shared Y axis: show the unit only when every trace uses the same one."""
    if len(units) == 1:
        (unit,) = units
        if unit:
            return f"Valor [{unit}]"
    return "Valor"


def build_figure(stored: StoredDataset, request: PlotRequest) -> PlotResponse:
    cleaned = stored.cleaned
    total_rows = cleaned.rows_clean
    start = request.range.start_index
    end = request.range.end_index

    if start >= total_rows or end >= total_rows:
        raise AppError(
            "INVALID_RANGE",
            "El rango seleccionado está fuera de los límites del dataset.",
            422,
            {
                "start_index": start,
                "end_index": end,
                "rows_clean": total_rows,
            },
        )

    subset = cleaned.frame.iloc[start : end + 1]
    x_values = _x_values(subset.index, cleaned.time_kind)
    use_gl = len(subset) > MAX_GL_POINTS
    trace_class = go.Scattergl if use_gl else go.Scatter
    traces: list[PlotTraceInfo] = []
    units: set[str | None] = set()
    figure = go.Figure()

    for requested in request.variables:
        column = cleaned.variable_ids.get(requested.id)
        if column is None:
            raise AppError(
                "INVALID_VARIABLE",
                "La variable solicitada no existe en el dataset.",
                422,
                {"variable_id": requested.id},
            )

        display_name = requested.name or column
        unit = requested.unit
        scale = requested.scale
        x_hover = "%{x|%M:%S.%L}" if cleaned.time_kind == "clock" else "%{x}"
        real_values = subset[column].to_numpy(dtype=float)
        hover = f"<b>%{{meta[0]}}</b><br>{x_hover}<br>%{{y:.6g}} %{{meta[1]}}"
        extra: dict = {}
        if scale is not None:
            # Scale against the whole cleaned dataset so the mapping does not
            # change when the user moves the range slider.
            full = cleaned.frame[column]
            y_values = rescale(real_values, float(full.min()), float(full.max()), scale)
            extra["customdata"] = real_values
            hover += "<br>Real: %{customdata:.6g}"
        else:
            y_values = real_values
        figure.add_trace(
            trace_class(
                x=x_values,
                y=y_values,
                mode="lines",
                name=legend_name(display_name, unit, scale),
                line={"color": requested.color, "width": 1.5},
                # Labels live in `meta` (not in the template text) so the client
                # can rename a trace with Plotly.restyle, and user text is never
                # parsed as a template placeholder. meta[2] is the scale suffix.
                meta=[display_name, unit or "", scale_label(scale)],
                hovertemplate=f"{hover}<extra></extra>",
                **extra,
            )
        )
        traces.append(
            PlotTraceInfo(
                id=requested.id,
                name=display_name,
                original_name=column,
                unit=unit,
                scale=scale,
                color=requested.color,
                range_min=float(real_values.min()),
                range_max=float(real_values.max()),
            )
        )
        units.add(unit)

    if cleaned.time_kind == "datetime":
        range_label = f"{x_values[0]} a {x_values[-1]}"
    elif cleaned.time_kind == "clock":
        range_label = f"{_format_clock(subset.index[0])} a {_format_clock(subset.index[-1])}"
    else:
        range_label = f"{x_values[0]:.3f} s a {x_values[-1]:.3f} s"

    figure.update_layout(
        title={
            "text": f"{stored.filename} — {range_label}",
            "x": 0.01,
            "xanchor": "left",
            "font": {"size": 17},
        },
        xaxis=_axis_config(stored),
        yaxis={
            "title": {"text": _y_axis_title(units)},
            "showgrid": True,
            "zeroline": False,
        },
        hovermode="x unified",
        template="plotly_white",
        legend={
            "orientation": "v",
            "x": 1.01,
            "y": 1,
            "xanchor": "left",
            "yanchor": "top",
            "font": {"size": 10},
            "groupclick": "toggleitem",
        },
        margin={"l": 64, "r": 190, "t": 64, "b": 64},
        autosize=True,
        uirevision=stored.dataset_id,
    )

    return PlotResponse(
        figure=json.loads(figure.to_json()),
        rows_plotted=len(subset),
        variables=traces,
    )
