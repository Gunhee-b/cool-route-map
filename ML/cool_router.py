"""Heat-weighted pedestrian routing engine (Shortest Path vs. Cool Path) using ground-level Real-Feel temperature."""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx

from config import DEFAULT_HEAT_ALPHA, TEMP_BASELINE_C, WALK_SPEED_MPS
from fetch_network import compute_real_feel_c, haversine_m, load_network_json


@dataclass
class RouteMetrics:
    mode: str
    nodes: list[int]
    coords: list[list[float]]
    distance_m: float
    walk_time_min: float
    avg_temp_c: float
    max_temp_c: float
    avg_humidity_pct: float
    avg_real_feel_c: float
    max_real_feel_c: float
    avg_shade_pct: float
    heat_exposure_deg_m: float


def attach_temperatures(
    G: nx.Graph,
    temp_csv_path: Path,
    default_humidity_pct: float = 50.0,
) -> nx.Graph:
    """Attach air temp, humidity, shade, and ground-level Real-Feel (°C) onto each street edge."""
    temp_map: dict[str, tuple[float, float, float, float]] = {}
    with temp_csv_path.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            temp_c = float(row["temp_c"])
            shade_pct = float(row.get("shade_pct") or 50.0)
            humidity_pct = float(row.get("humidity_pct") or default_humidity_pct)
            # Always compute Real-Feel from (temp_c, humidity_pct, shade_pct) so teammate edits auto-update
            real_feel_c = compute_real_feel_c(temp_c, humidity_pct, shade_pct)
            temp_map[row["edge_id"]] = (temp_c, humidity_pct, shade_pct, real_feel_c)

    fallback_temp = sum(v[0] for v in temp_map.values()) / max(1, len(temp_map))
    fallback_rf = compute_real_feel_c(fallback_temp, default_humidity_pct, 50.0)
    for _, _, data in G.edges(data=True):
        temp_c, humidity_pct, shade_pct, real_feel_c = temp_map.get(
            data["edge_id"], (fallback_temp, default_humidity_pct, 50.0, fallback_rf)
        )
        data["temp_c"] = temp_c
        data["humidity_pct"] = humidity_pct
        data["shade_pct"] = shade_pct
        data["real_feel_c"] = real_feel_c
    return G


def load_routable_graph(
    net_path: Path,
    temp_csv_path: Path,
    default_humidity_pct: float = 50.0,
) -> nx.Graph:
    """Load pedestrian graph and join street thermal attributes."""
    G = load_network_json(net_path)
    return attach_temperatures(G, temp_csv_path, default_humidity_pct=default_humidity_pct)


def find_nearest_node(G: nx.Graph, lat: float, lon: float) -> int:
    """Return the graph intersection node closest to (lat, lon)."""
    return min(
        G.nodes,
        key=lambda nid: haversine_m(lat, lon, G.nodes[nid]["lat"], G.nodes[nid]["lon"]),
    )


def _cool_edge_weight(
    u: int,
    v: int,
    data: dict[str, Any],
    alpha: float = DEFAULT_HEAT_ALPHA,
    temp_baseline: float = TEMP_BASELINE_C,
) -> float:
    """Heat-penalized walking cost based on ground-level Real-Feel temperature."""
    excess_heat = max(0.0, data["real_feel_c"] - temp_baseline)
    return data["length_m"] * (1.0 + alpha * excess_heat)


def evaluate_path(
    G: nx.Graph,
    node_path: list[int],
    mode: str,
    temp_baseline: float = TEMP_BASELINE_C,
) -> RouteMetrics:
    """Compute distance, walking time, air temp, humidity, real-feel temp, shade, and polyline."""
    total_dist = 0.0
    weighted_temp = 0.0
    weighted_rh = 0.0
    weighted_rf = 0.0
    weighted_shade = 0.0
    heat_exposure = 0.0
    max_temp = -999.0
    max_rf = -999.0
    coords: list[list[float]] = []

    for i in range(len(node_path) - 1):
        u, v = node_path[i], node_path[i + 1]
        data = G[u][v]
        length_m = data["length_m"]
        temp_c = data["temp_c"]
        rh = data["humidity_pct"]
        rf_c = data["real_feel_c"]
        shade_pct = data["shade_pct"]

        total_dist += length_m
        weighted_temp += temp_c * length_m
        weighted_rh += rh * length_m
        weighted_rf += rf_c * length_m
        weighted_shade += shade_pct * length_m
        heat_exposure += max(0.0, rf_c - temp_baseline) * length_m
        max_temp = max(max_temp, temp_c)
        max_rf = max(max_rf, rf_c)

        edge_coords = data["coords"]
        u_lat, u_lon = G.nodes[u]["lat"], G.nodes[u]["lon"]
        d_start = haversine_m(u_lat, u_lon, edge_coords[0][0], edge_coords[0][1])
        d_end = haversine_m(u_lat, u_lon, edge_coords[-1][0], edge_coords[-1][1])
        oriented = edge_coords if d_start <= d_end else list(reversed(edge_coords))
        if coords:
            coords.extend(oriented[1:])
        else:
            coords.extend(oriented)

    avg_temp = weighted_temp / total_dist if total_dist > 0 else 0.0
    avg_rh = weighted_rh / total_dist if total_dist > 0 else 0.0
    avg_rf = weighted_rf / total_dist if total_dist > 0 else 0.0
    avg_shade = weighted_shade / total_dist if total_dist > 0 else 0.0
    walk_time_min = (total_dist / WALK_SPEED_MPS) / 60.0

    return RouteMetrics(
        mode=mode,
        nodes=node_path,
        coords=coords,
        distance_m=round(total_dist, 1),
        walk_time_min=round(walk_time_min, 2),
        avg_temp_c=round(avg_temp, 2),
        max_temp_c=round(max_temp, 2),
        avg_humidity_pct=round(avg_rh, 1),
        avg_real_feel_c=round(avg_rf, 2),
        max_real_feel_c=round(max_rf, 2),
        avg_shade_pct=round(avg_shade, 1),
        heat_exposure_deg_m=round(heat_exposure, 1),
    )


def compute_shortest_and_cool_routes(
    G: nx.Graph,
    start_node: int,
    end_node: int,
    alpha: float = DEFAULT_HEAT_ALPHA,
    temp_baseline: float = TEMP_BASELINE_C,
) -> dict[str, Any]:
    """Compute and compare Shortest Path vs. Cool Path (Real-Feel weighted)."""
    shortest_nodes = nx.shortest_path(G, start_node, end_node, weight="length_m")
    cool_nodes = nx.shortest_path(
        G,
        start_node,
        end_node,
        weight=lambda u, v, d: _cool_edge_weight(u, v, d, alpha=alpha, temp_baseline=temp_baseline),
    )

    short_m = evaluate_path(G, shortest_nodes, mode="shortest", temp_baseline=temp_baseline)
    cool_m = evaluate_path(G, cool_nodes, mode="cool", temp_baseline=temp_baseline)

    temp_reduction_c = round(short_m.avg_temp_c - cool_m.avg_temp_c, 2)
    real_feel_reduction_c = round(short_m.avg_real_feel_c - cool_m.avg_real_feel_c, 2)
    extra_dist_m = round(cool_m.distance_m - short_m.distance_m, 1)
    extra_dist_pct = round((extra_dist_m / short_m.distance_m) * 100.0, 1) if short_m.distance_m > 0 else 0.0
    extra_time_min = round(cool_m.walk_time_min - short_m.walk_time_min, 2)
    shade_gain_pct = round(cool_m.avg_shade_pct - short_m.avg_shade_pct, 1)
    heat_exp_red_pct = (
        round(((short_m.heat_exposure_deg_m - cool_m.heat_exposure_deg_m) / short_m.heat_exposure_deg_m) * 100.0, 1)
        if short_m.heat_exposure_deg_m > 0
        else 0.0
    )

    return {
        "shortest": short_m,
        "cool": cool_m,
        "temp_reduction_c": temp_reduction_c,
        "real_feel_reduction_c": real_feel_reduction_c,
        "heat_exposure_reduction_pct": heat_exp_red_pct,
        "shade_gain_pct": shade_gain_pct,
        "extra_distance_m": extra_dist_m,
        "extra_distance_pct": extra_dist_pct,
        "extra_time_min": extra_time_min,
    }


def run_benchmark(
    G: nx.Graph,
    n_pairs: int = 60,
    min_straight_dist_m: float = 350.0,
    seed: int = 42,
    alpha: float = DEFAULT_HEAT_ALPHA,
    out_csv: Path | None = None,
) -> dict[str, Any]:
    """Evaluate Cool Route vs. Shortest Route across random pedestrian trips."""
    rng = random.Random(seed)
    nodes = list(G.nodes)
    rows: list[dict[str, Any]] = []
    attempts = 0

    while len(rows) < n_pairs and attempts < n_pairs * 25:
        attempts += 1
        u, v = rng.sample(nodes, 2)
        straight_d = haversine_m(
            G.nodes[u]["lat"], G.nodes[u]["lon"], G.nodes[v]["lat"], G.nodes[v]["lon"]
        )
        if straight_d < min_straight_dist_m:
            continue

        comp = compute_shortest_and_cool_routes(G, u, v, alpha=alpha)
        rows.append(
            {
                "trip_id": len(rows) + 1,
                "shortest_dist_m": comp["shortest"].distance_m,
                "cool_dist_m": comp["cool"].distance_m,
                "extra_dist_m": comp["extra_distance_m"],
                "extra_dist_pct": comp["extra_distance_pct"],
                "extra_time_min": comp["extra_time_min"],
                "shortest_avg_temp_c": comp["shortest"].avg_temp_c,
                "cool_avg_temp_c": comp["cool"].avg_temp_c,
                "temp_reduction_c": comp["temp_reduction_c"],
                "shortest_real_feel_c": comp["shortest"].avg_real_feel_c,
                "cool_real_feel_c": comp["cool"].avg_real_feel_c,
                "real_feel_reduction_c": comp["real_feel_reduction_c"],
                "avg_humidity_pct": comp["shortest"].avg_humidity_pct,
                "shortest_shade_pct": comp["shortest"].avg_shade_pct,
                "cool_shade_pct": comp["cool"].avg_shade_pct,
                "shade_gain_pct": comp["shade_gain_pct"],
                "heat_exposure_reduction_pct": comp["heat_exposure_reduction_pct"],
            }
        )

    if out_csv is not None and rows:
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)

    def avg(key: str) -> float:
        return round(sum(r[key] for r in rows) / max(1, len(rows)), 2)

    return {
        "n_trips": len(rows),
        "avg_temp_reduction_c": avg("temp_reduction_c"),
        "avg_real_feel_reduction_c": avg("real_feel_reduction_c"),
        "max_real_feel_reduction_c": round(max((r["real_feel_reduction_c"] for r in rows), default=0.0), 2),
        "avg_shortest_real_feel_c": avg("shortest_real_feel_c"),
        "avg_cool_real_feel_c": avg("cool_real_feel_c"),
        "avg_humidity_pct": avg("avg_humidity_pct"),
        "avg_heat_exposure_reduction_pct": avg("heat_exposure_reduction_pct"),
        "avg_shade_gain_pct": avg("shade_gain_pct"),
        "avg_extra_dist_m": avg("extra_dist_m"),
        "avg_extra_dist_pct": avg("extra_dist_pct"),
        "avg_extra_time_min": avg("extra_time_min"),
        "rows": rows,
    }
