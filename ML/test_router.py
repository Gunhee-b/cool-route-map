"""Automated tests for the pedestrian cool-route path finder (Real-Feel Heat Index + Shade)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import networkx as nx

from config import CITIES, DATA_DIR, RESULTS_DIR
from cool_router import (
    attach_temperatures,
    compute_shortest_and_cool_routes,
    find_nearest_node,
    load_routable_graph,
)
from fetch_network import compute_real_feel_c


def test_humidity_real_feel_seoul_vs_madrid() -> None:
    """Humid Seoul (34°C, 70% RH) must feel hotter than dry Madrid (37°C, 25% RH)."""
    seoul_rf = compute_real_feel_c(temp_c=34.0, humidity_pct=70.0, shade_pct=50.0)
    madrid_rf = compute_real_feel_c(temp_c=37.0, humidity_pct=25.0, shade_pct=50.0)
    assert seoul_rf > madrid_rf + 5.0

    # Shaded street must feel cooler than sunlit street at identical air temp & humidity
    shaded = compute_real_feel_c(temp_c=34.0, humidity_pct=70.0, shade_pct=90.0)
    sunlit = compute_real_feel_c(temp_c=34.0, humidity_pct=70.0, shade_pct=10.0)
    assert shaded < sunlit - 2.0


def test_seoul_and_madrid_graphs_routable() -> None:
    for city_key, cfg in CITIES.items():
        net_path = DATA_DIR / f"{city_key}_network.json"
        temp_path = DATA_DIR / f"{city_key}_street_temperatures.csv"
        assert net_path.exists(), f"Missing cached network for {city_key}"
        assert temp_path.exists(), f"Missing temperature CSV for {city_key}"

        G = load_routable_graph(net_path, temp_path, default_humidity_pct=cfg["base_humidity_pct"])
        assert nx.is_connected(G)
        assert G.number_of_edges() > 100

        for trip in cfg["demo_trips"]:
            s_node = find_nearest_node(G, *trip["start"])
            e_node = find_nearest_node(G, *trip["end"])
            res = compute_shortest_and_cool_routes(G, s_node, e_node)
            assert res["cool"].avg_real_feel_c <= res["shortest"].avg_real_feel_c + 1e-6
            assert res["shortest"].distance_m <= res["cool"].distance_m + 1e-6
            assert len(res["cool"].coords) >= 2


def test_custom_temperature_csv_changes_cool_route(tmp_path: Path) -> None:
    """Verify that replacing street temperatures/humidity dynamically reroutes the cool path."""
    G = nx.Graph()
    G.add_node(1, lat=37.5600, lon=126.9800)
    G.add_node(2, lat=37.5610, lon=126.9800)
    G.add_node(3, lat=37.5620, lon=126.9800)
    G.add_node(4, lat=37.5610, lon=126.9815)

    G.add_edge(1, 2, edge_id="E1", length_m=100.0, highway="primary", name="Hot Ave", coords=[[37.56, 126.98], [37.561, 126.98]])
    G.add_edge(2, 3, edge_id="E2", length_m=100.0, highway="primary", name="Hot Ave", coords=[[37.561, 126.98], [37.562, 126.98]])
    G.add_edge(1, 4, edge_id="E3", length_m=120.0, highway="path", name="Park Path", coords=[[37.56, 126.98], [37.561, 126.9815]])
    G.add_edge(4, 3, edge_id="E4", length_m=120.0, highway="path", name="Park Path", coords=[[37.561, 126.9815], [37.562, 126.98]])

    csv_path = tmp_path / "temps.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["edge_id", "temp_c", "humidity_pct", "shade_pct"])
        w.writerow(["E1", 36.0, 70.0, 10.0])
        w.writerow(["E2", 36.0, 70.0, 10.0])
        w.writerow(["E3", 31.0, 70.0, 85.0])
        w.writerow(["E4", 31.0, 70.0, 85.0])

    attach_temperatures(G, csv_path)
    res = compute_shortest_and_cool_routes(G, 1, 3, alpha=0.65)
    assert res["shortest"].nodes == [1, 2, 3]
    assert res["cool"].nodes == [1, 4, 3]
    assert res["real_feel_reduction_c"] > 10.0


def test_geojson_exports_valid() -> None:
    """Verify GeoJSON street and cool-path exports include real_feel_c & humidity_pct."""
    for city_key in CITIES:
        streets = json.loads((RESULTS_DIR / f"{city_key}_walkable_streets.geojson").read_text(encoding="utf-8"))
        assert streets["type"] == "FeatureCollection"
        assert len(streets["features"]) > 0
        props = streets["features"][0]["properties"]
        assert "real_feel_c" in props and "humidity_pct" in props

        routes = json.loads((RESULTS_DIR / f"{city_key}_cool_paths.geojson").read_text(encoding="utf-8"))
        assert routes["type"] == "FeatureCollection"
        assert len(routes["features"]) > 0
        assert "avg_real_feel_c" in routes["features"][0]["properties"]
