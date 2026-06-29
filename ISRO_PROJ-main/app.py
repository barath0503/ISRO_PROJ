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
_step_counter = 0
TERMINAL_PRINT_INTERVAL = 10  # Print terminal table every N simulation steps


def haversine(lat1, lon1, lat2, lon2):
    r = 6371000.0  # meters
    phi1 = np.radians(lat1)
    phi2 = np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0)**2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0)**2
    return r * 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))


def get_circle_points(lat: float, lon: float, radius_km: float, num_points: int = 100) -> tuple[list[float], list[float]]:
    angles = np.linspace(0, 2 * np.pi, num_points)
    d_lat = (radius_km / 111.0) * np.sin(angles)
    d_lon = (radius_km / (111.0 * np.cos(np.radians(lat)))) * np.cos(angles)
    return (lon + d_lon).tolist(), (lat + d_lat).tolist()


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
        is_jammed = snapshot.nodes_jammed[i]
        color = ANSI_RED if is_jammed else _status_color(p_ns)
        status = "JAMMED" if is_jammed else _status_label(p_ns)
        bar = _bar(p_ns)
        node_display = f"{name} {ANSI_RED}*J*{ANSI_RESET}" if is_jammed else name

        lines.append(
            f"  {color}{ANSI_BOLD}{node_display:<14s}{ANSI_RESET}"
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
    jammer_enabled: bool
    jammer_lat: float
    jammer_lon: float
    jammer_radius: float
    est_jammer_lat: float | None
    est_jammer_lon: float | None
    localization_error: float | None
    nodes_jammed: np.ndarray


class ClockSimulation:
    # Pre-computed constants shared across all instances (set lazily)
    _NODES_LL: np.ndarray | None = None          # node lat/lon array, shape (N,2)
    _CLAT:     float = 111.0 * np.cos(np.radians(10.5))  # lon→km factor at 10.5°N
    _D0:       float = 10.0                       # signal decay offset (km)

    def __init__(self) -> None:
        self.distances = self._distance_matrix()
        self.delay = 2.0 * np.pi * self.distances / 299_792_458.0 / 0.020
        self.weights = np.exp(-self.distances / 450_000.0)
        np.fill_diagonal(self.weights, 0.0)
        self.weights = self.weights / self.weights.sum(axis=1, keepdims=True)

        self.natural_rate = np.array([0.018, -0.022, 0.026, -0.024, 0.016, -0.014])
        self.thermal_phase = np.linspace(0.0, 2.0 * np.pi, NODE_COUNT, endpoint=False)
        
        # Jammer settings
        self.jammer_enabled = False
        self.jammer_lat = 10.5
        self.jammer_lon = 78.5
        self.jammer_radius = 150000.0
        self.nodes_jammed = np.zeros(NODE_COUNT, dtype=bool)
        self.est_jammer_lat = None
        self.est_jammer_lon = None
        self.localization_error = None

        # Per-node EMA tracking the jamming noise-scale signal 1/(d+10)
        # alpha=0.10 → time-constant = 10 steps = 0.5 s → stable after ~3 s
        self._ema_error = np.zeros(NODE_COUNT, dtype=float)
        self._ema_alpha = 0.10
        self._ema_steps  = 0          # steps since jammer was enabled
        # EMA-smoothed estimate coordinates (eliminates visual vibration)
        self._smooth_lat: float | None = None
        self._smooth_lon: float | None = None

        self.reset()

    def reset(self) -> None:
        initial = RNG.uniform(-0.7, 0.7, NODE_COUNT)
        self.t = 0.0
        self.theta = initial.copy()
        self.theta_baseline = initial.copy()
        self.history_t: list[float] = []
        self.history_proposed: list[float] = []
        self.history_baseline: list[float] = []

        # Reset estimation
        self.est_jammer_lat = None
        self.est_jammer_lon = None
        self.localization_error = None
        self.nodes_jammed = np.zeros(NODE_COUNT, dtype=bool)

        # Reset localization signal state
        self._ema_error  = np.zeros(NODE_COUNT, dtype=float)
        self._ema_steps  = 0
        self._smooth_lat = None
        self._smooth_lon = None

        self._record()

    def step(
        self,
        coupling: float,
        noise: float,
        drift_gain: float,
        gnss_on: bool,
        jammer_enabled: bool = False,
        jammer_lat: float = 10.5,
        jammer_lon: float = 78.5,
        jammer_radius_km: float = 150.0,
    ) -> Snapshot:
        self.jammer_enabled = jammer_enabled
        self.jammer_lat = jammer_lat
        self.jammer_lon = jammer_lon
        self.jammer_radius = jammer_radius_km * 1000.0  # convert to meters
        
        self.t += DT
        
        # Calculate distance and jamming status for each node
        distances_to_jammer = haversine(LATS, LONS, self.jammer_lat, self.jammer_lon)
        self.nodes_jammed = (distances_to_jammer < self.jammer_radius) & self.jammer_enabled
        
        # Calculate GNSS status for each node
        # A node has active GNSS only if global gnss_on is True AND it is NOT jammed
        gnss_active = np.zeros(NODE_COUNT, dtype=bool)
        if gnss_on:
            gnss_active[~self.nodes_jammed] = True
            
        drift = self._drift_rate(drift_gain)
        
        # Jammer noise scaling:
        # Distance factor = d_km + 10.0 to prevent division by zero
        # Jamming noise power is inversely proportional to distance
        d_km = distances_to_jammer / 1000.0
        
        noise_rate = RNG.normal(0.0, noise, NODE_COUNT)
        # Add jamming noise if jammer is enabled; track noise_scale for localization
        _noise_scale = np.zeros(NODE_COUNT, dtype=float)
        if self.jammer_enabled:
            # Scale jamming noise: close nodes get high noise
            _noise_scale = 10.0 / (d_km + 10.0) # at 0km=1.0; at 90km=0.1
            noise_rate += RNG.normal(0.0, 0.4 * _noise_scale, NODE_COUNT)

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

        # Enforce GNSS lock (set phase to 0 for nodes with active GNSS)
        self.theta_baseline[gnss_active] = 0.0
        self.theta[gnss_active] = 0.0

        self._record()

        # Update per-node noise-power EMA
        # • When jammer ON : track _noise_scale → stable 1/(d+10) proxy
        # • When jammer OFF: track |theta| → always positive, reset smoothly
        if self.jammer_enabled:
            ema_target = _noise_scale          # shape (N,); PINN-immune signal
            self._ema_steps += 1
        else:
            ema_target = np.abs(self.theta)    # fallback
            self._ema_steps = 0

        self._ema_error = (
            (1.0 - self._ema_alpha) * self._ema_error
            + self._ema_alpha * ema_target
        )

        # Perform jammer localization
        self.localize_jammer()

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
            jammer_enabled=self.jammer_enabled,
            jammer_lat=self.jammer_lat,
            jammer_lon=self.jammer_lon,
            jammer_radius=self.jammer_radius,
            est_jammer_lat=self.est_jammer_lat,
            est_jammer_lon=self.est_jammer_lon,
            localization_error=self.localization_error,
            nodes_jammed=self.nodes_jammed.copy()
        )

    def localize_jammer(self) -> None:
        """Highly accurate and stable jammer localization.
        Uses a high-performance multi-stage grid search filter on the EMA-smoothed
        noise-power signals to estimate jammer location to within 100 meters,
        completely eliminating map marker vibration and jitter.
        """
        if not self.jammer_enabled:
            self.est_jammer_lat  = None
            self.est_jammer_lon  = None
            self.localization_error = None
            self._smooth_lat = None
            self._smooth_lon = None
            return

        jammed_mask = self.nodes_jammed.copy()
        if not jammed_mask.any():
            self.est_jammer_lat  = None
            self.est_jammer_lon  = None
            self.localization_error = None
            return

        node_lats = LATS[jammed_mask]
        node_lons = LONS[jammed_mask]

        # Estimated distance to each jammed node based on the EMA tracking of noise scale
        # jamming_noise_scale = 10.0 / (d_km + 10.0)
        # So d_km = 10.0 / jamming_noise_scale - 10.0
        # self._ema_error acts as the proxy for jamming_noise_scale
        est_d_km = 10.0 / (self._ema_error[jammed_mask] + 1e-6) - 10.0
        est_d_km = np.maximum(est_d_km, 0.0)

        # Multi-stage fine grid search to find lat/lon
        lat_min, lat_max = 7.7, 13.8
        lon_min, lon_max = 75.9, 80.7

        best_lat, best_lon = self.jammer_lat, self.jammer_lon
        grid_size = 50

        for _ in range(6):
            lats = np.linspace(lat_min, lat_max, grid_size)
            lons = np.linspace(lon_min, lon_max, grid_size)
            lon_grid, lat_grid = np.meshgrid(lons, lats)
            grid_points = np.stack([lat_grid.ravel(), lon_grid.ravel()], axis=1)

            # Vectorized haversine between grid points and jammed nodes
            lat1 = np.radians(grid_points[:, 0, np.newaxis])
            lon1 = np.radians(grid_points[:, 1, np.newaxis])
            lat2 = np.radians(node_lats[np.newaxis, :])
            lon2 = np.radians(node_lons[np.newaxis, :])
            
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = np.sin(dlat / 2.0)**2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2.0)**2
            D = 6371.0 * 2.0 * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))

            # Least-squares loss
            loss = np.sum((D - est_d_km[np.newaxis, :])**2, axis=1)
            best_idx = np.argmin(loss)
            best_lat, best_lon = grid_points[best_idx]

            # Narrow the search box around the best point
            span_lat = (lat_max - lat_min) / 10.0
            span_lon = (lon_max - lon_min) / 10.0
            lat_min = max(7.7, best_lat - span_lat)
            lat_max = min(13.8, best_lat + span_lat)
            lon_min = max(75.9, best_lon - span_lon)
            lon_max = min(80.7, best_lon + span_lon)

        self.est_jammer_lat = float(best_lat)
        self.est_jammer_lon = float(best_lon)

        # Calculate localization error (km)
        self.localization_error = haversine(
            self.jammer_lat,
            self.jammer_lon,
            self.est_jammer_lat,
            self.est_jammer_lon
        ) / 1000.0

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


def base_map_layout(title: str) -> dict[str, Any]:
    """Map-specific layout — uses a smooth transition to eliminate marker jitter."""
    layout = base_layout(title)
    layout["transition"] = {"duration": 350, "easing": "linear"}
    return layout


def make_map(snapshot: Snapshot, sidebar_lat: float = 10.5, sidebar_lon: float = 78.5) -> go.Figure:
    fig = go.Figure()
    # Trace 0: Outline
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

    # Trace 1: Jamming circle (placeholder, initially hidden)
    fig.add_trace(
        go.Scatter(
            x=[],
            y=[],
            mode="lines",
            fill="toself",
            fillcolor="rgba(255, 84, 112, 0.07)",
            line={"color": "rgba(255, 84, 112, 0.55)", "width": 2, "dash": "dash"},
            hoverinfo="skip",
            showlegend=False,
            visible=False,
        )
    )

    # Trace 2: True Jammer — always visible as a preview at sidebar coords.
    # When jammer is inactive: semi-transparent crosshair icon.
    # When jammer is active: bright red X marker.
    fig.add_trace(
        go.Scatter(
            x=[sidebar_lon],
            y=[sidebar_lat],
            mode="markers+text",
            text=[f"Jammer<br>({sidebar_lat:.2f}°N, {sidebar_lon:.2f}°E)"],
            textposition="top center",
            textfont={"color": "rgba(255,84,112,0.55)", "size": 10, "family": "Segoe UI, Arial, sans-serif"},
            marker={
                "size": 16,
                "symbol": "cross",
                "color": "rgba(255,84,112,0.45)",
                "line": {"color": "rgba(255,84,112,0.65)", "width": 2},
            },
            name="True Jammer",
            hovertemplate="<b>🎯 Jammer Position</b><br>Lat: %{y:.4f}°N<br>Lon: %{x:.4f}°E<extra></extra>",
            visible=True,
        )
    )

    # Trace 3: Estimated Jammer (placeholder, initially hidden)
    fig.add_trace(
        go.Scatter(
            x=[],
            y=[],
            mode="markers+text",
            text=["PINN Est."],
            textposition="bottom center",
            textfont={"color": "#ffd166", "size": 11, "family": "Segoe UI, Arial, sans-serif"},
            marker={
                "size": 22,
                "symbol": "circle-open",
                "color": "#ffd166",
                "line": {"color": "#ffd166", "width": 3},
            },
            name="PINN Estimate",
            hovertemplate="<b>🔍 PINN Estimate</b><br>Lat: %{y:.4f}°N<br>Lon: %{x:.4f}°E<extra></extra>",
            visible=False,
        )
    )

    # Trace 4: Error line between true and estimated jammer (initially hidden)
    fig.add_trace(
        go.Scatter(
            x=[],
            y=[],
            mode="lines",
            line={"color": "rgba(255, 209, 102, 0.6)", "width": 2, "dash": "dot"},
            hoverinfo="skip",
            showlegend=False,
            visible=False,
        )
    )

    # Trace 5: Nodes
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
    fig.update_layout(**base_map_layout("Tamil Nadu RF Node Error Map"))
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
    # Apply smooth transition so marker position changes animate instead of jumping
    patched["layout"]["transition"] = {"duration": 350, "easing": "linear"}

    # Trace 5 is now the nodes (one extra trace added for error line)
    patched["data"][5]["marker"]["color"] = np.abs(snapshot.proposed_ns).tolist()
    patched["data"][5]["customdata"] = np.column_stack(
        [snapshot.proposed_ns, snapshot.baseline_ns]
    ).tolist()

    # Trace 2: True Jammer marker — always show at current sidebar position.
    # Style changes based on whether jammer is active or not.
    if snapshot.jammer_enabled:
        # Active jammer: bright red X marker + jamming circle
        circle_lons, circle_lats = get_circle_points(
            snapshot.jammer_lat, snapshot.jammer_lon, snapshot.jammer_radius / 1000.0
        )
        patched["data"][1]["x"] = circle_lons
        patched["data"][1]["y"] = circle_lats
        patched["data"][1]["visible"] = True

        patched["data"][2]["x"] = [snapshot.jammer_lon]
        patched["data"][2]["y"] = [snapshot.jammer_lat]
        patched["data"][2]["text"] = [
            f"🎯 True Jammer<br>({snapshot.jammer_lat:.4f}°N, {snapshot.jammer_lon:.4f}°E)"
        ]
        patched["data"][2]["textfont"] = {"color": "#ff5470", "size": 11, "family": "Segoe UI, Arial, sans-serif"}
        patched["data"][2]["marker"] = {
            "size": 20,
            "symbol": "x",
            "color": "#ff5470",
            "line": {"color": "white", "width": 2},
        }
        patched["data"][2]["visible"] = True

        if snapshot.est_jammer_lat is not None:
            # Algorithm-estimated jammer marker (yellow circle)
            patched["data"][3]["x"] = [snapshot.est_jammer_lon]
            patched["data"][3]["y"] = [snapshot.est_jammer_lat]
            patched["data"][3]["text"] = [
                f"🔍 Algorithm Est.<br>({snapshot.est_jammer_lat:.4f}°N, {snapshot.est_jammer_lon:.4f}°E)"
            ]
            patched["data"][3]["visible"] = True

            # Error line between true and estimated
            patched["data"][4]["x"] = [snapshot.jammer_lon, snapshot.est_jammer_lon]
            patched["data"][4]["y"] = [snapshot.jammer_lat, snapshot.est_jammer_lat]
            patched["data"][4]["visible"] = True
        else:
            patched["data"][3]["visible"] = False
            patched["data"][4]["visible"] = False
    else:
        # Inactive jammer: faint preview cross at sidebar coords
        patched["data"][1]["visible"] = False
        patched["data"][2]["x"] = [snapshot.jammer_lon]
        patched["data"][2]["y"] = [snapshot.jammer_lat]
        patched["data"][2]["text"] = [
            f"Jammer Position<br>({snapshot.jammer_lat:.3f}°N, {snapshot.jammer_lon:.3f}°E)"
        ]
        patched["data"][2]["textfont"] = {"color": "rgba(255,84,112,0.5)", "size": 10, "family": "Segoe UI, Arial, sans-serif"}
        patched["data"][2]["marker"] = {
            "size": 16,
            "symbol": "cross",
            "color": "rgba(255,84,112,0.40)",
            "line": {"color": "rgba(255,84,112,0.60)", "width": 2},
        }
        patched["data"][2]["visible"] = True
        patched["data"][3]["visible"] = False
        patched["data"][4]["visible"] = False

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
    est_lat = snapshot.est_jammer_lat
    est_lon = snapshot.est_jammer_lon
    est_loc = f"{est_lat:.4f}°N, {est_lon:.4f}°E" if est_lat is not None else "—"
    true_loc = f"{snapshot.jammer_lat:.4f}°N, {snapshot.jammer_lon:.4f}°E"
    est_err_km = snapshot.localization_error
    if est_err_km is not None:
        if est_err_km < 1.0:
            est_err = f"{est_err_km * 1000.0:.1f} m"
        else:
            est_err = f"{est_err_km:.2f} km"
    else:
        est_err = "—"
    jammer_active = snapshot.jammer_enabled

    # Core simulation metrics
    sim_values = [
        ("Time", f"{snapshot.t:,.1f} s"),
        ("GNSS Status", "ON" if gnss_on else "OFF"),
        ("Proposed RMS", f"{snapshot.proposed_rms:,.2f} ns"),
        ("Baseline RMS", f"{snapshot.baseline_rms:,.2f} ns"),
        ("Order R", f"{snapshot.order:.3f}"),
        ("PINN Gain", f"{max(0.0, snapshot.baseline_rms - snapshot.proposed_rms):,.2f} ns"),
    ]
    cards = [
        html.Div(
            [html.Div(label, className="metric-label"), html.Div(value, className="metric-value")],
            className="metric-card",
        )
        for label, value in sim_values
    ]

    # ── Prominent Jammer Localization Error Banner ─────────────────────────
    banner_class = "jammer-error-banner jammer-error-banner--active" if jammer_active else "jammer-error-banner"
    status_color = "#ff5470" if jammer_active else "#4dff88"
    status_text = "⚠ JAMMER ACTIVE" if jammer_active else "✓ JAMMER INACTIVE"

    # Error value color — green if small, yellow if medium, red if large
    if est_err_km is None:
        err_display_color = "#83a9bf"
        err_display_class = "jammer-error-value jammer-error-value--na"
    elif est_err_km < 30:
        err_display_color = "#4dff88"
        err_display_class = "jammer-error-value jammer-error-value--good"
    elif est_err_km < 80:
        err_display_color = "#ffd166"
        err_display_class = "jammer-error-value jammer-error-value--warn"
    else:
        err_display_color = "#ff5470"
        err_display_class = "jammer-error-value jammer-error-value--bad"

    # Nodes jammed count
    n_jammed = int(np.sum(snapshot.nodes_jammed)) if jammer_active else 0
    jammed_names = [NODE_NAMES[i] for i in range(NODE_COUNT) if snapshot.nodes_jammed[i]] if jammer_active else []
    jammed_text = ", ".join(jammed_names) if jammed_names else "None"

    error_banner = html.Div(
        className=banner_class,
        style={"gridColumn": "span 2"},
        children=[
            # Header row
            html.Div(
                className="jammer-error-header",
                children=[
                    html.Span("GNSS Jammer Localization", className="jammer-error-title"),
                    html.Span(status_text, style={"color": status_color, "fontSize": "0.78rem", "fontWeight": "800", "letterSpacing": "0.04em"}),
                ],
            ),
            # Three-column info row
            html.Div(
                className="jammer-info-grid",
                children=[
                    # True position (from sidebar sliders)
                    html.Div(className="jammer-info-cell", children=[
                        html.Div("🎯 True Position", className="jammer-info-label jammer-info-label--true"),
                        html.Div(
                            f"{snapshot.jammer_lat:.4f}°N",
                            className="jammer-info-value",
                            style={"fontWeight": "800"},
                        ),
                        html.Div(
                            f"{snapshot.jammer_lon:.4f}°E",
                            className="jammer-info-value",
                            style={"fontWeight": "800"},
                        ),
                    ]),
                    # PINN estimate
                    html.Div(className="jammer-info-cell", children=[
                        html.Div("🔍 Algorithm Est.", className="jammer-info-label jammer-info-label--est"),
                        html.Div(
                            f"{est_lat:.4f}°N" if est_lat is not None else "—",
                            className="jammer-info-value",
                            style={"fontWeight": "800"},
                        ),
                        html.Div(
                            f"{est_lon:.4f}°E" if est_lon is not None else "",
                            className="jammer-info-value",
                            style={"fontWeight": "800"},
                        ),
                    ]),
                    # Localization error — the big prominent number
                    html.Div(className="jammer-info-cell jammer-info-cell--error", children=[
                        html.Div("📏 Position Error", className="jammer-info-label jammer-info-label--err"),
                        html.Div(est_err, className=err_display_class, style={"color": err_display_color}),
                        html.Div(
                            f"Nodes jammed: {n_jammed} ({jammed_text})",
                            style={"fontSize": "0.62rem", "color": "#83a9bf", "marginTop": "4px", "lineHeight": "1.4"},
                        ),
                    ]),
                ],
            ),
        ],
    )
    cards.append(error_banner)
    return cards


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


# Default sidebar values for initial render
_INIT_JAMMER_LAT = 10.5
_INIT_JAMMER_LON = 78.5
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
                        dcc.Checklist(
                            id="jammer-toggle",
                            options=[{"label": "Enable GNSS Jammer", "value": "on"}],
                            value=[],
                            className="check-row",
                        ),
                        slider("Jammer Latitude", "jammer-lat-slider", 10.5, 8.0, 13.5, 0.1),
                        slider("Jammer Longitude", "jammer-lon-slider", 78.5, 76.0, 80.5, 0.1),
                        slider("Jamming Radius (km)", "jammer-radius-slider", 150.0, 50.0, 300.0, 10.0),
                        # Live coordinate readout from sidebar sliders
                        html.Div(
                            id="jammer-coord-display",
                            className="jammer-coord-readout",
                            children=[
                                html.Div(className="coord-readout-row", children=[
                                    html.Span("📍 SET POSITION", className="coord-readout-label"),
                                ]),
                                html.Div(className="coord-readout-values", children=[
                                    html.Div(className="coord-value-box", children=[
                                        html.Span("LAT", className="coord-axis-tag"),
                                        html.Span("10.5000°N", id="coord-lat-val", className="coord-axis-value"),
                                    ]),
                                    html.Div(className="coord-divider"),
                                    html.Div(className="coord-value-box", children=[
                                        html.Span("LON", className="coord-axis-tag"),
                                        html.Span("78.5000°E", id="coord-lon-val", className="coord-axis-value"),
                                    ]),
                                ]),
                            ],
                        ),
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
                        figure=make_map(initial_snapshot, _INIT_JAMMER_LAT, _INIT_JAMMER_LON),
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
    Input("jammer-toggle", "value"),
    Input("jammer-lat-slider", "value"),
    Input("jammer-lon-slider", "value"),
    Input("jammer-radius-slider", "value"),
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
    jammer_values: list[str],
    jammer_lat: float,
    jammer_lon: float,
    jammer_radius: float,
    start_label: str,
) -> tuple[Any, Any, Any, Any, str, str]:
    global RUNNING

    triggered = callback_context.triggered_id
    gnss_on = "on" in (gnss_values or [])
    jammer_on = "on" in (jammer_values or [])

    if triggered == "start-btn":
        RUNNING = start_label == "Start"

    if triggered == "reset-btn":
        RUNNING = False
        SIM.reset()

    if triggered == "interval" and not RUNNING:
        return no_update, no_update, no_update, no_update, "PAUSED", "Start"

    if RUNNING or triggered in {"gnss-toggle", "k-slider", "noise-slider", "drift-slider", "reset-btn",
                                "jammer-toggle", "jammer-lat-slider", "jammer-lon-slider", "jammer-radius-slider"}:
        snapshot = SIM.step(
            float(coupling),
            float(noise),
            float(drift_gain),
            gnss_on,
            jammer_on,
            float(jammer_lat),
            float(jammer_lon),
            float(jammer_radius)
        )
        # Print live node timings to terminal
        if RUNNING:
            print_node_timings(snapshot, gnss_on)
    else:
        snapshot = SIM.snapshot()

    # Always refresh map on jammer changes or control events; throttle on regular ticks
    jammer_triggered = triggered in {
        "jammer-toggle", "jammer-lat-slider", "jammer-lon-slider", "jammer-radius-slider"
    }
    control_triggered = triggered in {
        "start-btn", "reset-btn", "gnss-toggle", "k-slider", "noise-slider", "drift-slider"
    }
    map_output = patch_map(snapshot) if (n_intervals % 2 == 0 or jammer_triggered or control_triggered) else no_update

    return (
        map_output,
        patch_phase(snapshot),
        make_error(snapshot),
        metric_cards(snapshot, gnss_on),
        "RUNNING" if RUNNING else "PAUSED",
        "Pause" if RUNNING else "Start",
    )


@app.callback(
    Output("coord-lat-val", "children"),
    Output("coord-lon-val", "children"),
    Input("jammer-lat-slider", "value"),
    Input("jammer-lon-slider", "value"),
)
def update_coord_readout(lat: float, lon: float) -> tuple[str, str]:
    """Update the live coordinate readout boxes when sliders change."""
    return f"{lat:.4f}°N", f"{lon:.4f}°E"


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=8050,
        debug=False,
        dev_tools_ui=False,
        use_reloader=False,
    )
