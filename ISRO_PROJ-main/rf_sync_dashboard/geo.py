from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TAMIL_NADU_GEOJSON = DATA_DIR / "tamil_nadu.geojson"


def load_tamil_nadu_geojson() -> dict[str, Any]:
    with TAMIL_NADU_GEOJSON.open("r", encoding="utf-8") as geojson_file:
        return json.load(geojson_file)


def polygon_rings(geojson: dict[str, Any]) -> list[list[list[float]]]:
    rings: list[list[list[float]]] = []

    for feature in geojson.get("features", []):
        geometry = feature.get("geometry", {})
        geometry_type = geometry.get("type")
        coordinates = geometry.get("coordinates", [])

        if geometry_type == "Polygon":
            rings.extend(coordinates)
        elif geometry_type == "MultiPolygon":
            for polygon in coordinates:
                rings.extend(polygon)

    return rings
