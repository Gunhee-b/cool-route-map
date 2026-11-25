"""Export walkable street networks and Shortest vs. Cool pedestrian routes as standard GeoJSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx

from config import CITIES, DEFAULT_HEAT_ALPHA, RESULTS_DIR
from cool_router import compute_shortest_and_cool_routes, find_nearest_node


def _to_lonlat(coords_latlon: list[list[float]]) -> list[list[float]]:
    """GeoJSON RFC 7946 requires [lon, lat] coordinate order."""
    return [[round(c[1], 6), round(c[0], 6)] for c in coords_latlon]


def export_city_geojson(
    city_key: str,
    G: nx.Graph,
    alpha: float = DEFAULT_HEAT_ALPHA,
) -> tuple[Path, Path]:
    """Export all walkable streets and demo Shortest vs. Cool routes to GeoJSON."""
    cfg = CITIES[city_key]
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    street_features: list[dict[str, Any]] = []
    for _, _, data in G.edges(data=True):
        street_features.append(
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": _to_lonlat(data["coords"]),
                },
                "properties": {
                    "edge_id": data["edge_id"],
                    "name": data["name"],
                    "highway": data["highway"],
                    "length_m": data["length_m"],
                    "temp_c": data["temp_c"],
                    "humidity_pct": data["humidity_pct"],
                    "shade_pct": data["shade_pct"],
                    "real_feel_c": data["real_feel_c"],
                },
            }
        )

    streets_path = RESULTS_DIR / f"{city_key}_walkable_streets.geojson"
    streets_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": street_features}),
        encoding="utf-8",
    )

    route_features: list[dict[str, Any]] = []
    for idx, trip in enumerate(cfg["demo_trips"], start=1):
        s_node = find_nearest_node(G, *trip["start"])
        e_node = find_nearest_node(G, *trip["end"])
        comp = compute_shortest_and_cool_routes(G, s_node, e_node, alpha=alpha)

        for mode_key in ("shortest", "cool"):
            rm = comp[mode_key]
            route_features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "LineString",
                        "coordinates": _to_lonlat(rm.coords),
                    },
                    "properties": {
                        "trip_id": idx,
                        "trip_name": trip["name"],
                        "mode": mode_key,
                        "distance_m": rm.distance_m,
                        "walk_time_min": rm.walk_time_min,
                        "avg_temp_c": rm.avg_temp_c,
                        "avg_humidity_pct": rm.avg_humidity_pct,
                        "avg_real_feel_c": rm.avg_real_feel_c,
                        "avg_shade_pct": rm.avg_shade_pct,
                        "real_feel_reduction_c": comp["real_feel_reduction_c"] if mode_key == "cool" else 0.0,
                        "extra_distance_m": comp["extra_distance_m"] if mode_key == "cool" else 0.0,
                    },
                }
            )

    routes_path = RESULTS_DIR / f"{city_key}_cool_paths.geojson"
    routes_path.write_text(
        json.dumps({"type": "FeatureCollection", "features": route_features}),
        encoding="utf-8",
    )
    return streets_path, routes_path
