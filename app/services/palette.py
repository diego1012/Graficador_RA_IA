"""Deterministic color assignment for dataset variables."""

from __future__ import annotations

import colorsys

BASE_PALETTE = [
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#d62728",
    "#9467bd",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
    "#bcbd22",
    "#17becf",
]


def _golden_angle_color(index: int) -> str:
    hue = ((index - len(BASE_PALETTE)) * 137.508) % 360
    red, green, blue = colorsys.hls_to_rgb(hue / 360.0, 0.52, 0.62)
    return f"#{round(red * 255):02x}{round(green * 255):02x}{round(blue * 255):02x}"


def assign_colors(names: list[str]) -> dict[str, str]:
    """Return a deterministic color for each column name."""
    colors: dict[str, str] = {}
    for index, name in enumerate(names):
        if index < len(BASE_PALETTE):
            colors[name] = BASE_PALETTE[index]
        else:
            colors[name] = _golden_angle_color(index)
    return colors
