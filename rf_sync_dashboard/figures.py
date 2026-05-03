from __future__ import annotations

from typing import Any

import numpy as np
import plotly.graph_objects as go

from rf_sync_dashboard.config import (
    DISPLAY_LONGITUDES,
    MAP_LAT_RANGE,
    MAP_LON_RANGE,
)
from rf_sync_dashboard.geo import polygon_rings
from rf_sync_dashboard.simulation import SimulationSnapshot


PLOT_BG = "#050a12"
PANEL_BG = "#07111f"
GRID = "rgba(117, 211, 255, 0.14)"
TEXT = "#d8f3ff"
MUTED = "#83a9bf"
CYAN = "#35f6ff"
RED = "#ff5470"
YELLOW = "#ffd166"
BLUE = "#176bff"

ERROR_COLORSCALE = [
    [0.00, "#1f6fff"],
    [0.25, "#35f6ff"],
    [0.50, "#4dff88"],
    [0.75, "#ffd166"],
    [1.00, "#ff5470"],
]


def map_node_payload(snapshot: SimulationSnapshot) -> dict[str, list[Any]]:
    return {
        "marker_color": np.abs(snapshot.proposed_error_ns).tolist(),
        "customdata": np.column_stack(
            [
                snapshot.proposed_error_ns,
                snapshot.baseline_error_ns,
                snapshot.temperatures_c,
            ]
        ).tolist(),
    }


def phase_payload(snapshot: SimulationSnapshot) -> dict[str, Any]:
    wrapped_theta = np.mod(snapshot.proposed_theta, 2.0 * np.pi)
    x = np.cos(wrapped_theta)
    y = np.sin(wrapped_theta)
    spoke_x = np.ravel(np.column_stack([np.zeros_like(x), x, np.full_like(x, np.nan)]))
    spoke_y = np.ravel(np.column_stack([np.zeros_like(y), y, np.full_like(y, np.nan)]))

    return {
        "spoke_x": spoke_x.tolist(),
        "spoke_y": spoke_y.tolist(),
        "node_x": x.tolist(),
        "node_y": y.tolist(),
        "marker_color": np.abs(snapshot.proposed_error_ns).tolist(),
        "order_text": f"R = {snapshot.order_parameter:.3f}",
    }


def error_axis_limit(snapshot: SimulationSnapshot) -> float:
    max_error = max(
        20.0,
        float(np.max(snapshot.history_baseline_rms_ns))
        if snapshot.history_baseline_rms_ns.size
        else 20.0,
        float(np.max(snapshot.history_proposed_rms_ns))
        if snapshot.history_proposed_rms_ns.size
        else 20.0,
    )
    return float(np.ceil((max_error * 1.18) / 100.0) * 100.0)


def error_payload(snapshot: SimulationSnapshot) -> dict[str, list[float] | float]:
    return {
        "time": snapshot.history_time_s.tolist(),
        "proposed": snapshot.history_proposed_rms_ns.tolist(),
        "baseline": snapshot.history_baseline_rms_ns.tolist(),
        "y_limit": error_axis_limit(snapshot),
    }


def build_map_figure(
    snapshot: SimulationSnapshot,
    tamil_nadu_geojson: dict[str, Any],
) -> go.Figure:
    fig = go.Figure()

    for ring in polygon_rings(tamil_nadu_geojson):
        ring_array = np.asarray(ring, dtype=float)
        fig.add_trace(
            go.Scatter(
                x=ring_array[:, 0],
                y=ring_array[:, 1],
                mode="lines",
                fill="toself",
                fillcolor="rgba(9, 31, 55, 0.82)",
                line={"color": "rgba(62, 217, 255, 0.72)", "width": 1.8},
                hoverinfo="skip",
                showlegend=False,
            )
        )

    payload = map_node_payload(snapshot)
    fig.add_trace(
        go.Scatter(
            x=DISPLAY_LONGITUDES,
            y=snapshot.latitudes,
            mode="markers+text",
            text=snapshot.node_names,
            textposition="top center",
            textfont={"color": TEXT, "size": 12},
            marker={
                "size": 16,
                "color": payload["marker_color"],
                "cmin": 0.0,
                "cmax": 180.0,
                "colorscale": ERROR_COLORSCALE,
                "line": {"color": "white", "width": 1.2},
                "colorbar": {
                    "title": {"text": "|Error| ns", "font": {"color": TEXT}},
                    "tickfont": {"color": TEXT},
                    "outlinecolor": "rgba(255,255,255,0.24)",
                },
            },
            customdata=payload["customdata"],
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Proposed: %{customdata[0]:+.2f} ns<br>"
                "Baseline: %{customdata[1]:+.2f} ns<br>"
                "Temperature: %{customdata[2]:.1f} C"
                "<extra></extra>"
            ),
            name="RF nodes",
        )
    )

    fig.update_layout(
        title={"text": "Tamil Nadu RF Nodes", "x": 0.02, "font": {"size": 16}},
        margin={"l": 8, "r": 8, "t": 42, "b": 8},
        paper_bgcolor=PANEL_BG,
        plot_bgcolor=PLOT_BG,
        font={"color": TEXT, "family": "Inter, Segoe UI, Arial"},
        xaxis={
            "title": "Longitude",
            "range": MAP_LON_RANGE,
            "gridcolor": GRID,
            "zeroline": False,
            "fixedrange": True,
        },
        yaxis={
            "title": "Latitude",
            "range": MAP_LAT_RANGE,
            "gridcolor": GRID,
            "zeroline": False,
            "scaleanchor": "x",
            "scaleratio": 1,
            "fixedrange": True,
        },
        legend={"font": {"color": TEXT}},
        transition={"duration": 0},
        uirevision="rf-sync-map",
    )
    return fig


def build_phase_figure(snapshot: SimulationSnapshot) -> go.Figure:
    payload = phase_payload(snapshot)
    circle = np.linspace(0.0, 2.0 * np.pi, 241)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=np.cos(circle),
            y=np.sin(circle),
            mode="lines",
            line={"color": "rgba(117,211,255,0.35)", "width": 2},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=payload["spoke_x"],
            y=payload["spoke_y"],
            mode="lines",
            line={"color": "rgba(117,211,255,0.18)", "width": 1},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=payload["node_x"],
            y=payload["node_y"],
            mode="markers+text",
            text=snapshot.node_names,
            textposition="top center",
            marker={
                "size": 15,
                "color": payload["marker_color"],
                "cmin": 0.0,
                "cmax": 180.0,
                "colorscale": ERROR_COLORSCALE,
                "line": {"color": "#ffffff", "width": 1.0},
            },
            hovertemplate=(
                "<b>%{text}</b><br>"
                "cos(theta): %{x:.3f}<br>"
                "sin(theta): %{y:.3f}"
                "<extra></extra>"
            ),
            name="Proposed phase",
        )
    )
    fig.add_annotation(
        x=-1.08,
        y=-1.08,
        text=payload["order_text"],
        showarrow=False,
        font={"color": MUTED, "size": 13},
    )
    fig.update_layout(
        title={"text": "Phase Synchronization", "x": 0.02, "font": {"size": 16}},
        margin={"l": 24, "r": 18, "t": 42, "b": 24},
        paper_bgcolor=PANEL_BG,
        plot_bgcolor=PLOT_BG,
        font={"color": TEXT, "family": "Inter, Segoe UI, Arial"},
        xaxis={
            "range": [-1.18, 1.18],
            "zeroline": True,
            "zerolinecolor": "rgba(117,211,255,0.24)",
            "gridcolor": GRID,
            "title": "cos(theta)",
            "scaleanchor": "y",
            "scaleratio": 1,
        },
        yaxis={
            "range": [-1.18, 1.18],
            "zeroline": True,
            "zerolinecolor": "rgba(117,211,255,0.24)",
            "gridcolor": GRID,
            "title": "sin(theta)",
        },
        showlegend=False,
        transition={"duration": 0},
        uirevision="rf-sync-phase",
    )
    return fig


def build_error_figure(snapshot: SimulationSnapshot) -> go.Figure:
    payload = error_payload(snapshot)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=payload["time"],
            y=payload["proposed"],
            mode="lines",
            line={"color": CYAN, "width": 3},
            name="Proposed: Kuramoto + PINN",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=payload["time"],
            y=payload["baseline"],
            mode="lines",
            line={"color": RED, "width": 3},
            name="Baseline: no PINN",
        )
    )

    fig.update_layout(
        title={"text": "Clock Error", "x": 0.02, "font": {"size": 16}},
        margin={"l": 62, "r": 24, "t": 42, "b": 48},
        paper_bgcolor=PANEL_BG,
        plot_bgcolor=PLOT_BG,
        font={"color": TEXT, "family": "Inter, Segoe UI, Arial"},
        xaxis={
            "title": "Time (s)",
            "gridcolor": GRID,
            "zerolinecolor": GRID,
        },
        yaxis={
            "title": "RMS clock error (ns)",
            "gridcolor": GRID,
            "zerolinecolor": GRID,
            "range": [0.0, payload["y_limit"]],
        },
        legend={
            "orientation": "h",
            "x": 0.01,
            "y": 1.12,
            "font": {"color": TEXT},
        },
        transition={"duration": 0},
        uirevision="rf-sync-error",
    )
    return fig
