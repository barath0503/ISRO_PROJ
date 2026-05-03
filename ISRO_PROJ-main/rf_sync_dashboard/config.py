from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Node:
    name: str
    latitude: float
    longitude: float


NODES: tuple[Node, ...] = (
    Node("Chennai", 13.0827, 80.2707),
    Node("Coimbatore", 11.0168, 76.9558),
    Node("Madurai", 9.9252, 78.1198),
    Node("Tirunelveli", 8.7139, 77.7567),
    Node("Trichy", 10.7905, 78.7047),
    Node("Vellore", 12.9165, 79.1325),
)

NODE_NAMES = tuple(node.name for node in NODES)
LATITUDES = np.array([node.latitude for node in NODES], dtype=float)
LONGITUDES = np.array([node.longitude for node in NODES], dtype=float)
DISPLAY_LONGITUDES = LONGITUDES.copy()
DISPLAY_LONGITUDES[NODE_NAMES.index("Vellore")] -= 0.24

CLOCK_FREQUENCY_HZ = 10_000_000.0
NS_PER_RADIAN = 1.0e9 / (2.0 * np.pi * CLOCK_FREQUENCY_HZ)
SPEED_OF_LIGHT_MPS = 299_792_458.0
SYNC_WAVE_PERIOD_S = 0.020

MAX_HISTORY_POINTS = 900
SIMULATION_DT_S = 0.10
RNG_SEED = 2026

MAP_LAT_RANGE = (7.75, 13.75)
MAP_LON_RANGE = (75.95, 80.65)
