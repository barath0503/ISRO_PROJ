from __future__ import annotations

from threading import RLock
from typing import Any

from dash import (
    Dash,
    Input,
    Output,
    Patch,
    State,
    callback_context,
    dcc,
    html,
    no_update,
)

from rf_sync_dashboard.config import SIMULATION_DT_S
from rf_sync_dashboard.figures import (
    build_error_figure,
    build_map_figure,
    build_phase_figure,
    error_payload,
    map_node_payload,
    phase_payload,
)
from rf_sync_dashboard.geo import load_tamil_nadu_geojson, polygon_rings
from rf_sync_dashboard.simulation import KuramotoClockNetwork, SimulationParameters


ENGINE = KuramotoClockNetwork()
ENGINE_LOCK = RLock()
TAMIL_NADU_GEOJSON = load_tamil_nadu_geojson()
MAP_NODE_TRACE_INDEX = len(polygon_rings(TAMIL_NADU_GEOJSON))
MAP_UPDATE_EVERY_TICKS = 4
METRIC_UPDATE_EVERY_TICKS = 2
GRAPH_CONFIG = {
    "displayModeBar": False,
    "responsive": False,
    "doubleClick": False,
    "scrollZoom": False,
    "staticPlot": False,
}


def create_app() -> Dash:
    app = Dash(__name__, title="RF Clock Synchronization")
    app.layout = build_layout()
    register_callbacks(app)
    return app


def build_layout() -> html.Div:
    params = SimulationParameters(
        coupling_strength=1.15,
        noise_level=0.030,
        drift_intensity=1.0,
        gnss_enabled=True,
    )
    snapshot = ENGINE.step(0.0, params)

    return html.Div(
        className="app-shell",
        children=[
            dcc.Store(id="run-state", data={"running": False}),
            dcc.Interval(id="sim-clock", interval=500, n_intervals=0),
            html.Header(
                className="topbar",
                children=[
                    html.Div(
                        children=[
                            html.Div("Distributed RF Clock Synchronization", className="title"),
                            html.Div(
                                "Tamil Nadu six-node holdover simulation",
                                className="subtitle",
                            ),
                        ]
                    ),
                    html.Div(
                        id="status-strip",
                        className="status-strip",
                        children=status_cards(snapshot, params, False),
                    ),
                ],
            ),
            html.Main(
                className="dashboard-grid",
                children=[
                    html.Section(
                        className="control-panel panel",
                        children=[
                            html.Div(className="panel-heading", children="Controls"),
                            html.Div(
                                className="button-row",
                                children=[
                                    html.Button(
                                        "Start",
                                        id="start-pause",
                                        n_clicks=0,
                                        className="primary-button",
                                    ),
                                    html.Button(
                                        "Reset",
                                        id="reset",
                                        n_clicks=0,
                                        className="secondary-button",
                                    ),
                                ],
                            ),
                            html.Div(
                                className="toggle-row",
                                children=[
                                    html.Span("GNSS Reference"),
                                    dcc.Checklist(
                                        id="gnss-toggle",
                                        options=[{"label": "", "value": "on"}],
                                        value=["on"] if params.gnss_enabled else [],
                                        className="switch",
                                    ),
                                ],
                            ),
                            control_slider(
                                "coupling-slider",
                                "Coupling K",
                                0.10,
                                3.00,
                                0.05,
                                params.coupling_strength,
                            ),
                            control_slider(
                                "noise-slider",
                                "Noise level",
                                0.00,
                                0.18,
                                0.005,
                                params.noise_level,
                            ),
                            control_slider(
                                "drift-slider",
                                "Drift intensity",
                                0.10,
                                2.50,
                                0.05,
                                params.drift_intensity,
                            ),
                            html.Div(
                                id="metric-grid",
                                className="metric-grid",
                                children=metric_cards(snapshot, params),
                            ),
                        ],
                    ),
                    html.Section(
                        className="map-panel panel",
                        children=[
                            dcc.Graph(
                                id="map-graph",
                                figure=build_map_figure(snapshot, TAMIL_NADU_GEOJSON),
                                config=GRAPH_CONFIG,
                                className="graph",
                                style={"height": "100%", "width": "100%"},
                            )
                        ],
                    ),
                    html.Section(
                        className="phase-panel panel",
                        children=[
                            dcc.Graph(
                                id="phase-graph",
                                figure=build_phase_figure(snapshot),
                                config=GRAPH_CONFIG,
                                className="graph",
                                style={"height": "100%", "width": "100%"},
                            )
                        ],
                    ),
                    html.Section(
                        className="error-panel panel",
                        children=[
                            dcc.Graph(
                                id="error-graph",
                                figure=build_error_figure(snapshot),
                                config=GRAPH_CONFIG,
                                className="graph",
                                style={"height": "100%", "width": "100%"},
                            )
                        ],
                    ),
                ],
            ),
        ],
    )


def control_slider(
    slider_id: str,
    label: str,
    minimum: float,
    maximum: float,
    step: float,
    value: float,
) -> html.Div:
    marks = {
        minimum: f"{minimum:g}",
        maximum: f"{maximum:g}",
    }
    return html.Div(
        className="control-block",
        children=[
            html.Label(label, htmlFor=slider_id),
            dcc.Slider(
                id=slider_id,
                min=minimum,
                max=maximum,
                step=step,
                value=value,
                marks=marks,
                tooltip={"placement": "bottom", "always_visible": False},
            ),
        ],
    )


def register_callbacks(app: Dash) -> None:
    @app.callback(
        Output("run-state", "data"),
        Output("start-pause", "children"),
        Input("start-pause", "n_clicks"),
        Input("reset", "n_clicks"),
        State("run-state", "data"),
        prevent_initial_call=True,
    )
    def toggle_running(
        start_clicks: int,
        reset_clicks: int,
        run_state: dict[str, Any],
    ) -> tuple[dict[str, bool], str]:
        triggered = callback_context.triggered_id
        running = bool(run_state.get("running", False))

        if triggered == "reset":
            return {"running": False}, "Start"
        if triggered == "start-pause":
            running = not running

        return {"running": running}, "Pause" if running else "Start"

    @app.callback(
        Output("map-graph", "figure"),
        Output("phase-graph", "figure"),
        Output("error-graph", "figure"),
        Output("metric-grid", "children"),
        Output("status-strip", "children"),
        Input("sim-clock", "n_intervals"),
        Input("reset", "n_clicks"),
        Input("coupling-slider", "value"),
        Input("noise-slider", "value"),
        Input("drift-slider", "value"),
        Input("gnss-toggle", "value"),
        State("run-state", "data"),
    )
    def update_dashboard(
        n_intervals: int,
        _reset_clicks: int,
        coupling_strength: float,
        noise_level: float,
        drift_intensity: float,
        gnss_values: list[str],
        run_state: dict[str, Any],
    ) -> tuple[Any, Any, Any, list[html.Div], list[html.Div]]:
        triggered = callback_context.triggered_id
        running = bool(run_state.get("running", False))

        if triggered == "sim-clock" and not running:
            return no_update, no_update, no_update, no_update, no_update

        params = SimulationParameters(
            coupling_strength=float(coupling_strength),
            noise_level=float(noise_level),
            drift_intensity=float(drift_intensity),
            gnss_enabled="on" in (gnss_values or []),
        )

        with ENGINE_LOCK:
            if triggered == "reset":
                ENGINE.reset()

            if params.gnss_enabled and triggered in {"gnss-toggle", "reset"}:
                snapshot = ENGINE.step(0.0, params)
            elif triggered == "sim-clock" and running:
                snapshot = ENGINE.step(SIMULATION_DT_S, params)
            else:
                snapshot = ENGINE.snapshot()

        map_update_due = (
            triggered != "sim-clock"
            or n_intervals % MAP_UPDATE_EVERY_TICKS == 0
        )
        metric_update_due = (
            triggered != "sim-clock"
            or n_intervals % METRIC_UPDATE_EVERY_TICKS == 0
        )

        return (
            map_figure_patch(snapshot) if map_update_due else no_update,
            phase_figure_patch(snapshot),
            error_figure_patch(snapshot),
            metric_cards(snapshot, params) if metric_update_due else no_update,
            status_cards(snapshot, params, running) if metric_update_due else no_update,
        )


def map_figure_patch(snapshot: Any) -> Patch:
    payload = map_node_payload(snapshot)
    patched_figure = Patch()
    patched_figure["data"][MAP_NODE_TRACE_INDEX]["marker"]["color"] = payload[
        "marker_color"
    ]
    patched_figure["data"][MAP_NODE_TRACE_INDEX]["customdata"] = payload["customdata"]
    return patched_figure


def phase_figure_patch(snapshot: Any) -> Patch:
    payload = phase_payload(snapshot)
    patched_figure = Patch()
    patched_figure["data"][1]["x"] = payload["spoke_x"]
    patched_figure["data"][1]["y"] = payload["spoke_y"]
    patched_figure["data"][2]["x"] = payload["node_x"]
    patched_figure["data"][2]["y"] = payload["node_y"]
    patched_figure["data"][2]["marker"]["color"] = payload["marker_color"]
    patched_figure["layout"]["annotations"][0]["text"] = payload["order_text"]
    return patched_figure


def error_figure_patch(snapshot: Any) -> Patch:
    payload = error_payload(snapshot)
    patched_figure = Patch()
    patched_figure["data"][0]["x"] = payload["time"]
    patched_figure["data"][0]["y"] = payload["proposed"]
    patched_figure["data"][1]["x"] = payload["time"]
    patched_figure["data"][1]["y"] = payload["baseline"]
    patched_figure["layout"]["yaxis"]["range"] = [0.0, payload["y_limit"]]
    return patched_figure


def metric_cards(snapshot: Any, params: SimulationParameters) -> list[html.Div]:
    values = [
        ("Time", f"{snapshot.time_s:,.1f} s"),
        ("Proposed RMS", f"{snapshot.proposed_rms_ns:,.2f} ns"),
        ("Baseline RMS", f"{snapshot.baseline_rms_ns:,.2f} ns"),
        ("Order R", f"{snapshot.order_parameter:.3f}"),
        ("K", f"{params.coupling_strength:.2f}"),
        ("Noise", f"{params.noise_level:.3f} rad/s"),
    ]
    return [
        html.Div(
            className="metric-card",
            children=[
                html.Div(label, className="metric-label"),
                html.Div(value, className="metric-value"),
            ],
        )
        for label, value in values
    ]


def status_cards(
    snapshot: Any,
    params: SimulationParameters,
    running: bool,
) -> list[html.Div]:
    gnss_label = "GNSS ON" if params.gnss_enabled else "GNSS OFF"
    run_label = "RUNNING" if running else "PAUSED"
    delta = snapshot.baseline_rms_ns - snapshot.proposed_rms_ns
    advantage = max(0.0, delta)

    return [
        html.Div(run_label, className="status-pill"),
        html.Div(gnss_label, className="status-pill"),
        html.Div(f"PINN advantage {advantage:,.2f} ns", className="status-pill"),
    ]
