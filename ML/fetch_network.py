"""Download walkable pedestrian street networks from OpenStreetMap (Overpass API)
and generate a clean street_temperatures.csv interface with ground-level Real-Feel
temperature (NOAA Heat Index + pedestrian sun/shade radiant adjustment).
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

import networkx as nx
import requests

from config import CITIES, DATA_DIR

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]

WALKABLE_HIGHWAYS = {
    "footway",
    "pedestrian",
    "path",
    "steps",
    "living_street",
    "residential",
    "service",
    "unclassified",
    "tertiary",
    "tertiary_link",
    "secondary",
    "secondary_link",
    "primary",
    "primary_link",
    "cycleway",
    "track",
}

# Approximate microclimate air-temp offset (°C) relative to city base_temp_c by street type.
HIGHWAY_TEMP_OFFSET = {
    "primary": +1.9,
    "primary_link": +1.7,
    "secondary": +1.4,
    "secondary_link": +1.2,
    "tertiary": +0.7,
    "tertiary_link": +0.6,
    "unclassified": +0.2,
    "residential": -0.5,
    "service": -0.7,
    "living_street": -1.1,
    "pedestrian": -1.2,
    "footway": -1.4,
    "cycleway": -0.6,
    "steps": -1.3,
    "path": -2.1,
    "track": -1.9,
}


def compute_heat_index_c(temp_c: float, humidity_pct: float) -> float:
    """Compute NOAA / Rothfusz Heat Index in °C from dry-bulb air temperature (°C) and RH (%)."""
    rh = max(0.0, min(100.0, float(humidity_pct)))
    t_f = temp_c * 9.0 / 5.0 + 32.0

    # Simple Steadman formula below 80°F
    simple_hi = 0.5 * (t_f + 61.0 + ((t_f - 68.0) * 1.2) + (rh * 0.094))
    if (simple_hi + t_f) / 2.0 < 80.0:
        return (simple_hi - 32.0) * 5.0 / 9.0

    # Full Rothfusz regression
    hi_f = (
        -42.379
        + 2.04901523 * t_f
        + 10.14333127 * rh
        - 0.22475541 * t_f * rh
        - 0.00683783 * (t_f ** 2)
        - 0.05481717 * (rh ** 2)
        + 0.00122874 * (t_f ** 2) * rh
        + 0.00085282 * t_f * (rh ** 2)
        - 0.00000199 * (t_f ** 2) * (rh ** 2)
    )

    # Standard NOAA low-humidity and high-humidity adjustments
    if rh < 13.0 and 80.0 <= t_f <= 112.0:
        hi_f -= ((13.0 - rh) / 4.0) * math.sqrt((17.0 - abs(t_f - 95.0)) / 17.0)
    elif rh > 85.0 and 80.0 <= t_f <= 87.0:
        hi_f += ((rh - 85.0) / 10.0) * ((87.0 - t_f) / 5.0)

    return (hi_f - 32.0) * 5.0 / 9.0


def compute_real_feel_c(temp_c: float, humidity_pct: float, shade_pct: float) -> float:
    """Compute ground-level pedestrian Real-Feel temperature (°C).

    Combines NOAA Heat Index (air temperature + relative humidity) with a
    radiant sun/shade load adjustment (+1.8 °C in full sun, -1.8 °C in full shade).
    """
    hi_c = compute_heat_index_c(temp_c, humidity_pct)
    shade_frac = max(0.0, min(1.0, float(shade_pct) / 100.0))
    radiant_offset = 1.8 * (1.0 - 2.0 * shade_frac)
    return round(hi_c + radiant_offset, 2)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two (lat, lon) points."""
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def compute_bbox(center_lat: float, center_lon: float, radius_m: float) -> tuple[float, float, float, float]:
    """Return (south, west, north, east) bounding box around center."""
    dlat = radius_m / 111320.0
    dlon = radius_m / (111320.0 * math.cos(math.radians(center_lat)))
    return (center_lat - dlat, center_lon - dlon, center_lat + dlat, center_lon + dlon)


def query_overpass(south: float, west: float, north: float, east: float) -> dict[str, Any]:
    """Query Overpass API for walkable streets and green spaces inside the bbox."""
    hw_regex = "^(" + "|".join(sorted(WALKABLE_HIGHWAYS)) + ")$"
    query = f"""
    [out:json][timeout:45];
    (
      way["highway"~"{hw_regex}"]["foot"!="no"]["access"!="private"]({south},{west},{north},{east});
      way["leisure"="park"]({south},{west},{north},{east});
      way["landuse"~"^(grass|forest|recreation_ground|village_green)$"]({south},{west},{north},{east});
      node["natural"="tree"]({south},{west},{north},{east});
    );
    out body;
    >;
    out skel qt;
    """
    last_err: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            resp = requests.post(
                endpoint,
                data={"data": query},
                headers={"User-Agent": "OnEvolution-UHI-PedestrianRouter/1.0"},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("elements"):
                return data
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(1.0)
    raise RuntimeError(f"Failed to fetch OSM data from Overpass API: {last_err}")


def build_network_from_overpass(osm_data: dict[str, Any]) -> tuple[nx.Graph, list[tuple[float, float]]]:
    """Convert raw Overpass JSON into a connected pedestrian networkx.Graph and green-point list."""
    nodes_coord: dict[int, tuple[float, float]] = {}
    green_points: list[tuple[float, float]] = []
    ways: list[dict[str, Any]] = []

    for el in osm_data.get("elements", []):
        if el["type"] == "node":
            nodes_coord[el["id"]] = (el["lat"], el["lon"])
            if el.get("tags", {}).get("natural") == "tree":
                green_points.append((el["lat"], el["lon"]))
        elif el["type"] == "way":
            ways.append(el)

    walk_ways: list[dict[str, Any]] = []
    for w in ways:
        tags = w.get("tags", {})
        if tags.get("leisure") == "park" or tags.get("landuse") in {
            "grass",
            "forest",
            "recreation_ground",
            "village_green",
        }:
            pts = [nodes_coord[nid] for nid in w.get("nodes", []) if nid in nodes_coord]
            if pts:
                green_points.append(
                    (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
                )
        elif tags.get("highway") in WALKABLE_HIGHWAYS:
            walk_ways.append(w)

    node_usage: dict[int, int] = {}
    for w in walk_ways:
        nids = w.get("nodes", [])
        for idx, nid in enumerate(nids):
            if nid not in nodes_coord:
                continue
            if idx == 0 or idx == len(nids) - 1:
                node_usage[nid] = node_usage.get(nid, 0) + 2
            else:
                node_usage[nid] = node_usage.get(nid, 0) + 1

    G = nx.Graph()
    edge_counter = 0

    for w in walk_ways:
        nids = [nid for nid in w.get("nodes", []) if nid in nodes_coord]
        if len(nids) < 2:
            continue
        tags = w.get("tags", {})
        highway = tags.get("highway", "unclassified")
        name = tags.get("name:en") or tags.get("name") or f"{highway.replace('_', ' ').title()}"
        covered = tags.get("covered") == "yes" or tags.get("tunnel") in {"yes", "passage", "building_passage"}

        seg_start = 0
        for i in range(1, len(nids)):
            is_split = (i == len(nids) - 1) or (node_usage.get(nids[i], 0) >= 2)
            if not is_split:
                continue

            sub_nids = nids[seg_start : i + 1]
            u, v = sub_nids[0], sub_nids[-1]
            seg_start = i
            if u == v:
                continue

            coords = [list(nodes_coord[nid]) for nid in sub_nids]
            length_m = sum(
                haversine_m(coords[k][0], coords[k][1], coords[k + 1][0], coords[k + 1][1])
                for k in range(len(coords) - 1)
            )
            if length_m < 1.0:
                continue

            for nid in (u, v):
                if nid not in G:
                    lat, lon = nodes_coord[nid]
                    G.add_node(nid, lat=lat, lon=lon)

            if G.has_edge(u, v) and G[u][v]["length_m"] <= length_m:
                continue

            edge_counter += 1
            edge_id = f"E{edge_counter:05d}"
            G.add_edge(
                u,
                v,
                edge_id=edge_id,
                length_m=round(length_m, 2),
                highway=highway,
                name=name,
                covered=covered,
                coords=coords,
            )

    if G.number_of_nodes() == 0:
        raise RuntimeError("No walkable streets were extracted from OSM response.")

    largest_cc = max(nx.connected_components(G), key=len)
    G = G.subgraph(largest_cc).copy()
    return G, green_points


def _deterministic_jitter(edge_id: str, scale: float = 0.8) -> float:
    """Deterministic micro-variation in [-scale, +scale] based on edge_id."""
    digest = hashlib.md5(edge_id.encode("utf-8")).hexdigest()
    val = int(digest[:8], 16) / 0xFFFFFFFF
    return (val * 2.0 - 1.0) * scale


def generate_placeholder_temperatures(
    G: nx.Graph,
    green_points: list[tuple[float, float]],
    base_temp_c: float,
    base_humidity_pct: float,
    csv_path: Path,
) -> None:
    """Generate realistic baseline street air temperatures, humidity, shade, and Real-Feel °C.

    Teammates can replace `temp_c`, `humidity_pct`, and `shade_pct` in this CSV with their
    Digital Twin + ML model predictions and re-run run_demo.py directly.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []

    for _, _, data in G.edges(data=True):
        coords = data["coords"]
        mid_lat = coords[len(coords) // 2][0]
        mid_lon = coords[len(coords) // 2][1]

        highway = data["highway"]
        offset = HIGHWAY_TEMP_OFFSET.get(highway, 0.0)

        green_bonus = 0.0
        if green_points:
            min_d = min(haversine_m(mid_lat, mid_lon, glat, glon) for glat, glon in green_points)
            if min_d < 90.0:
                green_bonus = -1.9 * (1.0 - min_d / 90.0)

        covered_bonus = -2.8 if data.get("covered") else 0.0
        jitter = _deterministic_jitter(data["edge_id"], scale=0.9)

        temp_c = round(base_temp_c + offset + green_bonus + covered_bonus + jitter, 2)
        shade_pct = round(max(5.0, min(95.0, 50.0 - (temp_c - base_temp_c) * 13.0)), 1)

        # Micro-variation in street relative humidity (slightly more humid in shaded/green areas)
        rh_jitter = _deterministic_jitter(data["edge_id"] + "_rh", scale=2.5)
        humidity_pct = round(max(15.0, min(90.0, base_humidity_pct + rh_jitter)), 1)
        real_feel_c = compute_real_feel_c(temp_c, humidity_pct, shade_pct)

        rows.append(
            {
                "edge_id": data["edge_id"],
                "street_name": data["name"],
                "highway_type": highway,
                "length_m": data["length_m"],
                "temp_c": temp_c,
                "humidity_pct": humidity_pct,
                "shade_pct": shade_pct,
                "real_feel_c": real_feel_c,
                "source": "estimated_baseline",
            }
        )

    rows.sort(key=lambda r: r["edge_id"])
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "edge_id",
                "street_name",
                "highway_type",
                "length_m",
                "temp_c",
                "humidity_pct",
                "shade_pct",
                "real_feel_c",
                "source",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def save_network_json(G: nx.Graph, json_path: Path) -> None:
    """Serialize networkx graph to a lightweight JSON file."""
    json_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "nodes": [
            {"id": nid, "lat": data["lat"], "lon": data["lon"]}
            for nid, data in G.nodes(data=True)
        ],
        "edges": [
            {
                "u": u,
                "v": v,
                "edge_id": data["edge_id"],
                "length_m": data["length_m"],
                "highway": data["highway"],
                "name": data["name"],
                "covered": data.get("covered", False),
                "coords": data["coords"],
            }
            for u, v, data in G.edges(data=True)
        ],
    }
    json_path.write_text(json.dumps(payload), encoding="utf-8")


def load_network_json(json_path: Path) -> nx.Graph:
    """Load cached pedestrian network JSON back into a networkx.Graph."""
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    G = nx.Graph()
    for n in payload["nodes"]:
        G.add_node(n["id"], lat=n["lat"], lon=n["lon"])
    for e in payload["edges"]:
        G.add_edge(
            e["u"],
            e["v"],
            edge_id=e["edge_id"],
            length_m=e["length_m"],
            highway=e["highway"],
            name=e["name"],
            covered=e.get("covered", False),
            coords=e["coords"],
        )
    return G


def _csv_has_real_feel(csv_path: Path) -> bool:
    if not csv_path.exists():
        return False
    with csv_path.open("r", encoding="utf-8") as f:
        header = next(csv.reader(f), [])
    return "humidity_pct" in header and "real_feel_c" in header


def ensure_city_data(city_key: str, force_refresh: bool = False) -> tuple[Path, Path]:
    """Download street network & create baseline temperature CSV if not already cached."""
    cfg = CITIES[city_key]
    net_path = DATA_DIR / f"{city_key}_network.json"
    temp_path = DATA_DIR / f"{city_key}_street_temperatures.csv"

    if net_path.exists() and _csv_has_real_feel(temp_path) and not force_refresh:
        return net_path, temp_path

    if net_path.exists() and not force_refresh:
        # Upgrade existing baseline CSV with humidity_pct & real_feel_c using cached network
        G = load_network_json(net_path)
        generate_placeholder_temperatures(
            G, [], cfg["base_temp_c"], cfg["base_humidity_pct"], temp_path
        )
        print(f"[{city_key}] Upgraded baseline CSV with humidity & Real-Feel: {temp_path}")
        return net_path, temp_path

    print(f"[{city_key}] Downloading walkable street network from OpenStreetMap...")
    bbox = compute_bbox(cfg["center_lat"], cfg["center_lon"], cfg["radius_m"])
    osm_data = query_overpass(*bbox)
    G, green_points = build_network_from_overpass(osm_data)
    save_network_json(G, net_path)
    print(
        f"[{city_key}] Saved {G.number_of_nodes()} intersections & "
        f"{G.number_of_edges()} walkable street segments ({len(green_points)} green POIs)."
    )

    generate_placeholder_temperatures(
        G, green_points, cfg["base_temp_c"], cfg["base_humidity_pct"], temp_path
    )
    print(f"[{city_key}] Generated baseline temperatures with Real-Feel: {temp_path}")
    return net_path, temp_path


if __name__ == "__main__":
    for city in CITIES:
        ensure_city_data(city)
