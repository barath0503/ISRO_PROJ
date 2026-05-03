from __future__ import annotations

import json
import sys
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import dash
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, Patch, State, callback_context, dcc, html, no_update


NODES = [
    ("Chennai", 13.0827, 80.2707),
    ("Coimbatore", 11.0168, 76.9558),
    ("Madurai", 9.9252, 78.1198),
    ("Tirunelveli", 8.7139, 77.7567),
    ("Trichy", 10.7905, 78.7047),
    ("Vellore", 12.9165, 79.1325),
]

NODE_NAMES = [node[0] for node in NODES]
LATS = np.array([node[1] for node in NODES], dtype=float)
LONS = np.array([node[2] for node in NODES], dtype=float)
NODE_COUNT = len(NODES)
DISPLAY_LONS = LONS.copy()
DISPLAY_LONS[NODE_NAMES.index("Vellore")] -= 0.24

DT = 0.05
HISTORY_LIMIT = 700
CLOCK_HZ = 10_000_000.0
NS_PER_RADIAN = 1.0e9 / (2.0 * np.pi * CLOCK_HZ)
RNG = np.random.default_rng(42)
TERMINAL_PRINT_INTERVAL = 1  # print every N steps
_step_counter = 0

PAPER = "#07111f"
PLOT = "#050a12"
GRID = "rgba(117,211,255,0.15)"
TEXT = "#d8f3ff"
CYAN = "#35f6ff"
RED = "#ff5470"
GREEN = "#4dff88"
YELLOW = "#ffd166"

ERROR_SCALE = [
    [0.0, "#176bff"],
    [0.3, CYAN],
    [0.6, GREEN],
    [0.8, YELLOW],
    [1.0, RED],
]


# ─── ANSI color codes for terminal output ────────────────────────────────────
ANSI_RESET  = "\033[0m"
ANSI_BOLD   = "\033[1m"
ANSI_DIM    = "\033[2m"
ANSI_CYAN   = "\033[96m"
ANSI_GREEN  = "\033[92m"
ANSI_YELLOW = "\033[93m"
ANSI_RED    = "\033[91m"
ANSI_MAGENTA = "\033[95m"
ANSI_WHITE  = "\033[97m"
ANSI_BG_DARK = "\033[48;5;233m"

import sys

# Force UTF-8 encoding for Windows terminals so box-drawing characters don't crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def _tprint(*args: str) -> None:
    """Print directly to the terminal with an immediate flush."""
    print(" ".join(args), flush=True)


def _status_color(offset_ns: float) -> str:
    """Return ANSI color based on absolute offset magnitude."""
    absv = abs(offset_ns)
    if absv < 10.0:
        return ANSI_GREEN
    elif absv < 50.0:
        return ANSI_YELLOW
    else:
        return ANSI_RED


def _status_label(offset_ns: float) -> str:
    """Return a short sync-status label."""
    absv = abs(offset_ns)
    if absv < 10.0:
        return "SYNCED"
    elif absv < 50.0:
        return "DRIFT "
    else:
        return "DESYNC"


def _bar(offset_ns: float, max_ns: float = 120.0, width: int = 20) -> str:
    """Render a small horizontal bar for visual indication."""
    filled = int(min(abs(offset_ns) / max_ns, 1.0) * width)
    color = _status_color(offset_ns)
    return f"{color}{'#' * filled}{ANSI_DIM}{'-' * (width - filled)}{ANSI_RESET}"


import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

def print_node_timings(snapshot: "Snapshot", gnss_on: bool = False) -> None:
    """Print a static table of node timings that updates in-place."""
    global _step_counter
    _step_counter += 1
    if _step_counter % TERMINAL_PRINT_INTERVAL != 0:
        return

    w = 90  # table width
    t_str = f"{snapshot.t:,.2f}"
    gnss_str = f"{ANSI_GREEN}ON{ANSI_RESET}" if gnss_on else f"{ANSI_RED}OFF{ANSI_RESET}"

    lines = []

    lines.append(f"{ANSI_CYAN}{ANSI_BOLD}{'=' * w}{ANSI_RESET}")
    lines.append(
        f"{ANSI_BOLD}{ANSI_WHITE}  [TIME] NODE TIMING STATUS"
        f"{'':>10s}"
        f"T = {t_str} s   |   GNSS: {gnss_str}"
        f"{ANSI_RESET}"
    )
    lines.append(f"{ANSI_CYAN}{'-' * w}{ANSI_RESET}")
    lines.append(
        f"{ANSI_BOLD}{ANSI_WHITE}"
        f"  {'Node':<14s}"
        f"{'Proposed (ns)':>14s}"
        f"{'Baseline (ns)':>14s}"
        f"{'Phase (rad)':>13s}"
        f"  {'Status':<8s}"
        f"  {'Offset Bar':<22s}"
        f"{ANSI_RESET}"
    )
    lines.append(f"{ANSI_DIM}{'-' * w}{ANSI_RESET}")

    for i, name in enumerate(NODE_NAMES):
        p_ns = snapshot.proposed_ns[i]
        b_ns = snapshot.baseline_ns[i]
        phase = snapshot.theta[i]
        color = _status_color(p_ns)
        status = _status_label(p_ns)
        bar = _bar(p_ns)

        lines.append(
            f"  {color}{ANSI_BOLD}{name:<14s}{ANSI_RESET}"
            f"{color}{p_ns:>+14.3f}{ANSI_RESET}"
            f"{ANSI_DIM}{b_ns:>+14.3f}{ANSI_RESET}"
            f"{ANSI_DIM}{phase:>+13.4f}{ANSI_RESET}"
            f"  {color}{ANSI_BOLD}{status:<8s}{ANSI_RESET}"
            f"  {bar}"
        )

    lines.append(f"{ANSI_DIM}{'-' * w}{ANSI_RESET}")

    # Summary line
    p_rms = snapshot.proposed_rms
    b_rms = snapshot.baseline_rms
    gain = max(0.0, b_rms - p_rms)
    order = snapshot.order

    rms_color = ANSI_GREEN if p_rms < 10 else (ANSI_YELLOW if p_rms < 50 else ANSI_RED)
    order_color = ANSI_GREEN if order > 0.95 else (ANSI_YELLOW if order > 0.8 else ANSI_RED)

    lines.append(
        f"  {ANSI_BOLD}RMS  {rms_color}Proposed: {p_rms:>8.3f} ns{ANSI_RESET}"
        f"  {ANSI_DIM}|{ANSI_RESET}  "
        f"{ANSI_DIM}Baseline: {b_rms:>8.3f} ns{ANSI_RESET}"
        f"  {ANSI_DIM}|{ANSI_RESET}  "
        f"{order_color}Order R: {order:.4f}{ANSI_RESET}"
    )
    lines.append(f"{ANSI_CYAN}{ANSI_BOLD}{'=' * w}{ANSI_RESET}")

    # Clear the terminal and reprint the table in-place
    os.system('cls' if os.name == 'nt' else 'clear')
    print("\n".join(lines), flush=True)


@dataclass
class Snapshot:
    t: float
    theta: np.ndarray
    theta_baseline: np.ndarray
    proposed_ns: np.ndarray
    baseline_ns: np.ndarray
    proposed_rms: float
    baseline_rms: float
    order: float
    history_t: list[float]
    history_proposed: list[float]
    history_baseline: list[float]


class ClockSimulation:
    def __init__(self) -> None:
        self.distances = self._distance_matrix()
        self.delay = 2.0 * np.pi * self.distances / 299_792_458.0 / 0.020
        self.weights = np.exp(-self.distances / 450_000.0)
        np.fill_diagonal(self.weights, 0.0)
        self.weights = self.weights / self.weights.sum(axis=1, keepdims=True)

        self.natural_rate = np.array([0.018, -0.022, 0.026, -0.024, 0.016, -0.014])
        self.thermal_phase = np.linspace(0.0, 2.0 * np.pi, NODE_COUNT, endpoint=False)
        self.reset()

    def reset(self) -> None:
        initial = RNG.uniform(-0.7, 0.7, NODE_COUNT)
        self.t = 0.0
        self.theta = initial.copy()
        self.theta_baseline = initial.copy()
        self.history_t: list[float] = []
        self.history_proposed: list[float] = []
        self.history_baseline: list[float] = []
        self._record()

    def step(self, coupling: float, noise: float, drift_gain: float, gnss_on: bool) -> Snapshot:
        if gnss_on:
            self.theta[:] = 0.0
            self.theta_baseline[:] = 0.0
            self.t += DT
            self._record()
            return self.snapshot()

        self.t += DT
        drift = self._drift_rate(drift_gain)
        noise_rate = RNG.normal(0.0, noise, NODE_COUNT)

        baseline_rate = (
            self.natural_rate
            + self._kuramoto(self.theta_baseline, coupling)
            + drift
            + noise_rate
        )
        proposed_rate = (
            self.natural_rate
            + self._kuramoto(self.theta, coupling)
            + drift
            + noise_rate
            - self._pinn_correction(drift_gain)
        )

        self.theta_baseline += DT * baseline_rate
        self.theta += DT * proposed_rate
        self._record()
        return self.snapshot()

    def snapshot(self) -> Snapshot:
        proposed_ns = self.theta * NS_PER_RADIAN
        baseline_ns = self.theta_baseline * NS_PER_RADIAN
        return Snapshot(
            t=self.t,
            theta=self.theta.copy(),
            theta_baseline=self.theta_baseline.copy(),
            proposed_ns=proposed_ns.copy(),
            baseline_ns=baseline_ns.copy(),
            proposed_rms=float(np.sqrt(np.mean(proposed_ns**2))),
            baseline_rms=float(np.sqrt(np.mean(baseline_ns**2))),
            order=float(np.abs(np.mean(np.exp(1j * self.theta)))),
            history_t=self.history_t.copy(),
            history_proposed=self.history_proposed.copy(),
            history_baseline=self.history_baseline.copy(),
        )

    def _kuramoto(self, theta: np.ndarray, coupling: float) -> np.ndarray:
        delta = theta[np.newaxis, :] - theta[:, np.newaxis]
        return coupling * np.sum(self.weights * np.sin(delta - self.delay), axis=1)

    def _drift_rate(self, drift_gain: float) -> np.ndarray:
        temperature = 30.0 + 5.0 * np.sin(0.04 * self.t + self.thermal_phase)
        aging = 0.0015 * self.t
        thermal = 0.002 * (temperature - 25.0) ** 2
        return drift_gain * (thermal + aging) * np.array([1, -1, 1, -1, 1, -1])

    def _pinn_correction(self, drift_gain: float) -> np.ndarray:
        physics_drift = 0.995 * self._drift_rate(drift_gain)
        holdover_anchor = 1.2 * np.tanh(self.theta / 0.15)
        consensus_error = 0.40 * (self.theta - np.mean(self.theta))
        return physics_drift + holdover_anchor + consensus_error

    def _record(self) -> None:
        proposed = self.theta * NS_PER_RADIAN
        baseline = self.theta_baseline * NS_PER_RADIAN
        self.history_t.append(float(self.t))
        self.history_proposed.append(float(np.sqrt(np.mean(proposed**2))))
        self.history_baseline.append(float(np.sqrt(np.mean(baseline**2))))

        if len(self.history_t) > HISTORY_LIMIT:
            self.history_t = self.history_t[-HISTORY_LIMIT:]
            self.history_proposed = self.history_proposed[-HISTORY_LIMIT:]
            self.history_baseline = self.history_baseline[-HISTORY_LIMIT:]

    @staticmethod
    def _distance_matrix() -> np.ndarray:
        lat = np.radians(LATS)
        lon = np.radians(LONS)
        dlat = lat[:, None] - lat[None, :]
        dlon = lon[:, None] - lon[None, :]
        a = (
            np.sin(dlat / 2.0) ** 2
            + np.cos(lat[:, None]) * np.cos(lat[None, :]) * np.sin(dlon / 2.0) ** 2
        )
        return 6_371_000.0 * 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))


SIM = ClockSimulation()
RUNNING = False


def load_outline() -> np.ndarray:
    path = Path(__file__).parent / "data" / "tamil_nadu.geojson"
    with path.open("r", encoding="utf-8") as file:
        geojson = json.load(file)
    coordinates = geojson["features"][0]["geometry"]["coordinates"][0]
    return np.array(coordinates, dtype=float)


OUTLINE = load_outline()


def base_layout(title: str) -> dict[str, Any]:
    return {
        "title": {"text": title, "x": 0.02, "font": {"size": 15}},
        "paper_bgcolor": PAPER,
        "plot_bgcolor": PLOT,
        "font": {"color": TEXT, "family": "Segoe UI, Arial, sans-serif"},
        "margin": {"l": 48, "r": 20, "t": 42, "b": 42},
        "transition": {"duration": 0},
        "uirevision": "fixed",
    }


def make_map(snapshot: Snapshot) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=OUTLINE[:, 0],
            y=OUTLINE[:, 1],
            mode="lines",
            fill="toself",
            fillcolor="rgba(9,31,55,0.86)",
            line={"color": "rgba(53,246,255,0.75)", "width": 2},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=DISPLAY_LONS,
            y=LATS,
            mode="markers+text",
            text=NODE_NAMES,
            textposition="top center",
            marker={
                "size": 16,
                "color": np.abs(snapshot.proposed_ns),
                "cmin": 0,
                "cmax": 120,
                "colorscale": ERROR_SCALE,
                "line": {"color": "white", "width": 1},
            },
            customdata=np.column_stack([snapshot.proposed_ns, snapshot.baseline_ns]),
            hovertemplate=(
                "<b>%{text}</b><br>"
                "Proposed: %{customdata[0]:+.2f} ns<br>"
                "Baseline: %{customdata[1]:+.2f} ns<extra></extra>"
            ),
            showlegend=False,
        )
    )
    fig.update_layout(**base_layout("Tamil Nadu RF Node Error Map"))
    fig.update_xaxes(
        title="Longitude",
        range=[75.9, 80.7],
        gridcolor=GRID,
        fixedrange=True,
        zeroline=False,
    )
    fig.update_yaxes(
        title="Latitude",
        range=[7.7, 13.8],
        gridcolor=GRID,
        fixedrange=True,
        zeroline=False,
        scaleanchor="x",
        scaleratio=1,
    )
    return fig


def make_phase(snapshot: Snapshot) -> go.Figure:
    circle = np.linspace(0, 2 * np.pi, 240)
    x = np.cos(snapshot.theta)
    y = np.sin(snapshot.theta)
    spoke_x = np.ravel(np.column_stack([np.zeros(NODE_COUNT), x, np.full(NODE_COUNT, np.nan)]))
    spoke_y = np.ravel(np.column_stack([np.zeros(NODE_COUNT), y, np.full(NODE_COUNT, np.nan)]))

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
            x=spoke_x,
            y=spoke_y,
            mode="lines",
            line={"color": "rgba(117,211,255,0.22)", "width": 1},
            hoverinfo="skip",
            showlegend=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=x,
            y=y,
            mode="markers+text",
            text=NODE_NAMES,
            textposition="top center",
            marker={"size": 14, "color": CYAN, "line": {"color": "white", "width": 1}},
            showlegend=False,
        )
    )
    fig.update_layout(**base_layout("Phase Synchronization Unit Circle"))
    fig.add_annotation(
        x=-1.08,
        y=-1.08,
        text=f"Order R = {snapshot.order:.3f}",
        showarrow=False,
        font={"color": TEXT, "size": 13},
    )
    fig.update_xaxes(range=[-1.2, 1.2], gridcolor=GRID, fixedrange=True)
    fig.update_yaxes(
        range=[-1.2, 1.2],
        gridcolor=GRID,
        fixedrange=True,
        scaleanchor="x",
        scaleratio=1,
    )
    return fig


def make_error(snapshot: Snapshot) -> go.Figure:
    ymax = max(25.0, max(snapshot.history_baseline, default=25.0) * 1.12)
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=snapshot.history_t,
            y=snapshot.history_proposed,
            mode="lines",
            line={"color": CYAN, "width": 3},
            name="Kuramoto + PINN",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=snapshot.history_t,
            y=snapshot.history_baseline,
            mode="lines",
            line={"color": RED, "width": 3, "dash": "dash"},
            name="Baseline",
        )
    )
    fig.update_layout(**base_layout("Clock Error Divergence"))
    fig.update_layout(legend={"orientation": "h", "x": 0.02, "y": 1.14})
    fig.update_xaxes(title="Time (s)", gridcolor=GRID, fixedrange=True)
    fig.update_yaxes(title="RMS error (ns)", range=[0, ymax], gridcolor=GRID, fixedrange=True)
    return fig


def patch_map(snapshot: Snapshot) -> Patch:
    patched = Patch()
    patched["data"][1]["marker"]["color"] = np.abs(snapshot.proposed_ns).tolist()
    patched["data"][1]["customdata"] = np.column_stack(
        [snapshot.proposed_ns, snapshot.baseline_ns]
    ).tolist()
    return patched


def patch_phase(snapshot: Snapshot) -> Patch:
    x = np.cos(snapshot.theta)
    y = np.sin(snapshot.theta)
    spoke_x = np.ravel(np.column_stack([np.zeros(NODE_COUNT), x, np.full(NODE_COUNT, np.nan)]))
    spoke_y = np.ravel(np.column_stack([np.zeros(NODE_COUNT), y, np.full(NODE_COUNT, np.nan)]))

    patched = Patch()
    patched["data"][1]["x"] = spoke_x.tolist()
    patched["data"][1]["y"] = spoke_y.tolist()
    patched["data"][2]["x"] = x.tolist()
    patched["data"][2]["y"] = y.tolist()
    patched["layout"]["annotations"][0]["text"] = f"Order R = {snapshot.order:.3f}"
    return patched


def patch_error(snapshot: Snapshot) -> Patch:
    ymax = max(25.0, max(snapshot.history_baseline, default=25.0) * 1.12)
    patched = Patch()
    patched["data"][0]["x"] = snapshot.history_t
    patched["data"][0]["y"] = snapshot.history_proposed
    patched["data"][1]["x"] = snapshot.history_t
    patched["data"][1]["y"] = snapshot.history_baseline
    patched["layout"]["yaxis"]["range"] = [0, ymax]
    return patched


def metric_cards(snapshot: Snapshot, gnss_on: bool) -> list[html.Div]:
    values = [
        ("Time", f"{snapshot.t:,.1f} s"),
        ("GNSS", "ON" if gnss_on else "OFF"),
        ("Proposed RMS", f"{snapshot.proposed_rms:,.2f} ns"),
        ("Baseline RMS", f"{snapshot.baseline_rms:,.2f} ns"),
        ("Order R", f"{snapshot.order:.3f}"),
        ("PINN Gain", f"{max(0.0, snapshot.baseline_rms - snapshot.proposed_rms):,.2f} ns"),
    ]
    return [
        html.Div(
            [html.Div(label, className="metric-label"), html.Div(value, className="metric-value")],
            className="metric-card",
        )
        for label, value in values
    ]


def slider(label: str, slider_id: str, value: float, minimum: float, maximum: float, step: float) -> html.Div:
    return html.Div(
        [
            html.Label(label),
            dcc.Slider(
                id=slider_id,
                min=minimum,
                max=maximum,
                step=step,
                value=value,
                marks={minimum: f"{minimum:g}", maximum: f"{maximum:g}"},
                tooltip={"placement": "bottom"},
            ),
        ],
        className="control-block",
    )


initial_snapshot = SIM.snapshot()
app = dash.Dash(__name__)
server = app.server

app.layout = html.Div(
    [
        dcc.Interval(id="interval", interval=250, n_intervals=0),
        html.Header(
            [
                html.Div(
                    [
                        html.Div("Distributed RF Clock Synchronization", className="title"),
                        html.Div("Six Tamil Nadu RF nodes with GNSS denial holdover", className="subtitle"),
                    ]
                ),
                html.Div(id="status", className="status-pill", children="PAUSED"),
            ],
            className="topbar",
        ),
        html.Main(
            [
                html.Section(
                    [
                        html.Div("Controls", className="panel-heading"),
                        html.Div(
                            [
                                html.Button("Start", id="start-btn", n_clicks=0, className="primary-button"),
                                html.Button("Reset", id="reset-btn", n_clicks=0, className="secondary-button"),
                            ],
                            className="button-row",
                        ),
                        dcc.Checklist(
                            id="gnss-toggle",
                            options=[{"label": "GNSS reference ON", "value": "on"}],
                            value=["on"],
                            className="check-row",
                        ),
                        slider("Coupling K", "k-slider", 1.4, 0.1, 4.0, 0.1),
                        slider("Noise level", "noise-slider", 0.02, 0.0, 0.18, 0.005),
                        slider("Drift intensity", "drift-slider", 1.0, 0.1, 3.0, 0.1),
                        html.Div(
                            id="metrics",
                            className="metric-grid",
                            children=metric_cards(initial_snapshot, True),
                        ),
                    ],
                    className="control-panel panel",
                ),
                html.Section(
                    dcc.Graph(
                        id="map-graph",
                        figure=make_map(initial_snapshot),
                        config={"displayModeBar": False, "responsive": False},
                        className="graph",
                    ),
                    className="map-panel panel",
                ),
                html.Section(
                    dcc.Graph(
                        id="phase-graph",
                        figure=make_phase(initial_snapshot),
                        config={"displayModeBar": False, "responsive": False},
                        className="graph",
                    ),
                    className="phase-panel panel",
                ),
                html.Section(
                    dcc.Graph(
                        id="error-graph",
                        figure=make_error(initial_snapshot),
                        config={"displayModeBar": False, "responsive": False},
                        className="graph",
                    ),
                    className="error-panel panel",
                ),
            ],
            className="dashboard-grid",
        ),
    ],
    className="app-shell",
)


@app.callback(
    Output("map-graph", "figure"),
    Output("phase-graph", "figure"),
    Output("error-graph", "figure"),
    Output("metrics", "children"),
    Output("status", "children"),
    Output("start-btn", "children"),
    Input("interval", "n_intervals"),
    Input("start-btn", "n_clicks"),
    Input("reset-btn", "n_clicks"),
    Input("gnss-toggle", "value"),
    Input("k-slider", "value"),
    Input("noise-slider", "value"),
    Input("drift-slider", "value"),
    State("start-btn", "children"),
)
def update(
    n_intervals: int,
    _start_clicks: int,
    _reset_clicks: int,
    gnss_values: list[str],
    coupling: float,
    noise: float,
    drift_gain: float,
    start_label: str,
) -> tuple[Any, Any, Any, Any, str, str]:
    global RUNNING

    triggered = callback_context.triggered_id
    gnss_on = "on" in (gnss_values or [])

    if triggered == "start-btn":
        RUNNING = start_label == "Start"

    if triggered == "reset-btn":
        RUNNING = False
        SIM.reset()

    if triggered == "interval" and not RUNNING:
        return no_update, no_update, no_update, no_update, "PAUSED", "Start"

    if RUNNING or triggered in {"gnss-toggle", "k-slider", "noise-slider", "drift-slider", "reset-btn"}:
        snapshot = SIM.step(float(coupling), float(noise), float(drift_gain), gnss_on)
        # Print live node timings to terminal
        if RUNNING:
            print_node_timings(snapshot, gnss_on)
    else:
        snapshot = SIM.snapshot()

    map_output = patch_map(snapshot) if n_intervals % 4 == 0 else no_update

    return (
        map_output,
        patch_phase(snapshot),
        patch_error(snapshot),
        metric_cards(snapshot, gnss_on),
        "RUNNING" if RUNNING else "PAUSED",
        "Pause" if RUNNING else "Start",
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8050,
        debug=False,
        dev_tools_ui=False,
        use_reloader=False,
    )
