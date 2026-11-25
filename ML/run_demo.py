"""One-command runner for Team OnEvolution's pedestrian cool-route prototype."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from build_map import build_city_map, build_kpi_chart
from config import CITIES, RESULTS_DIR
from cool_router import load_routable_graph, run_benchmark
from export_geojson import export_city_geojson
from fetch_network import ensure_city_data


def write_report_summary(summaries: dict[str, dict[str, Any]], street_counts: dict[str, int]) -> Path:
    """Write a copy-pasteable summary of Part 3 (Cool-Route Map) for the Final Report & Slides."""
    out_md = RESULTS_DIR / "REPORT_SUMMARY.md"
    seoul = summaries["seoul"]
    madrid = summaries["madrid"]

    content = f"""# Part 3: Pedestrian Cool-Route Map — Summary for Final Report & Slides

## Method Overview
To guide pedestrians away from urban heat hotspots, we built a city-agnostic **heat-weighted pedestrian routing engine** tested on ~1.1 km × 1.1 km urban cores in **Seoul (Jung-gu / Myeongdong)** and **Madrid (Centro / Puerta del Sol)**:

1. **Walkable Street Network**: Extracted every walkable street segment (sidewalks, pedestrian zones, alleys, crosswalks, park paths; excluding car-only roads) from OpenStreetMap.
2. **Ground-Level Real-Feel Heat Model (Humidity + Shade)**: Because **Seoul's summer heat is humid (~70% RH)** while **Madrid's is dry (~25% RH)**, dry air temperature alone understates pedestrian heat stress in Korea. Each street segment's **Real-Feel temperature (°C)** combines the **NOAA Heat Index** (air temperature + relative humidity) with a **pedestrian radiant sun/shade adjustment** (`±1.8 °C` from full sun to full shade). Teammates' ML / Digital Twin predictions plug directly into `data/{{city}}_street_temperatures.csv` (`temp_c`, `humidity_pct`, `shade_pct`).
3. **Cool-Path Algorithm**: Using Dijkstra's shortest-path algorithm, we compare:
   - **Shortest Path**: minimizes walking distance `L(e)`.
   - **Cool Path**: minimizes real-feel heat-penalized walking cost `L(e) * (1 + alpha * max(0, T_real_feel(e) - 30°C))`, steering pedestrians along cooler, shaded streets while keeping detours short.

## KPI Results (60 Random Pedestrian Trips per City)

| Test City | Climate Baseline | Walkable Streets | Avg Real-Feel Saved | Max Real-Feel Saved | Excess Heat Reduced | Shade Gained | Extra Distance / Time |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Seoul (Jung-gu / Myeongdong)** | 34.0 °C air, **70% RH** (humid) | {street_counts['seoul']:,} | **-{seoul['avg_real_feel_reduction_c']:.2f} °C** | **-{seoul['max_real_feel_reduction_c']:.2f} °C** | **{seoul['avg_heat_exposure_reduction_pct']:.1f}%** | **+{seoul['avg_shade_gain_pct']:.1f}%** | +{seoul['avg_extra_dist_m']:.0f} m (+{seoul['avg_extra_dist_pct']:.1f}% / +{seoul['avg_extra_time_min']:.2f} min) |
| **Madrid (Centro / Puerta del Sol)** | 37.5 °C air, **25% RH** (dry) | {street_counts['madrid']:,} | **-{madrid['avg_real_feel_reduction_c']:.2f} °C** | **-{madrid['max_real_feel_reduction_c']:.2f} °C** | **{madrid['avg_heat_exposure_reduction_pct']:.1f}%** | **+{madrid['avg_shade_gain_pct']:.1f}%** | +{madrid['avg_extra_dist_m']:.0f} m (+{madrid['avg_extra_dist_pct']:.1f}% / +{madrid['avg_extra_time_min']:.2f} min) |

## Included Visuals & Data Files
- **Interactive Maps (open in any browser)**: `seoul_cool_routes.html`, `madrid_cool_routes.html`
- **KPI Chart (for report & slides)**: `kpi_summary.png`
- **GeoJSON Exports (for QGIS / Cesium / Web / Digital Twin)**: `seoul_walkable_streets.geojson`, `seoul_cool_paths.geojson`, `madrid_walkable_streets.geojson`, `madrid_cool_paths.geojson`
- **Benchmark CSVs**: `seoul_benchmark.csv`, `madrid_benchmark.csv`
"""
    out_md.write_text(content, encoding="utf-8")
    return out_md


def main() -> None:
    summaries: dict[str, dict[str, Any]] = {}
    street_counts: dict[str, int] = {}

    for city_key, cfg in CITIES.items():
        print("=" * 72)
        print(f"Processing {cfg['display_name']}...")
        net_path, temp_path = ensure_city_data(city_key)
        G = load_routable_graph(
            net_path, temp_path, default_humidity_pct=cfg["base_humidity_pct"]
        )
        street_counts[city_key] = G.number_of_edges()

        bench_csv = RESULTS_DIR / f"{city_key}_benchmark.csv"
        summary = run_benchmark(G, n_pairs=60, out_csv=bench_csv)
        summaries[city_key] = summary

        map_html = build_city_map(city_key, G, summary)
        streets_gj, routes_gj = export_city_geojson(city_key, G)

        print(
            f"[{city_key}] Benchmark ({summary['n_trips']} trips, {summary['avg_humidity_pct']:.0f}% RH): "
            f"avg -{summary['avg_real_feel_reduction_c']:.2f} °C Real-Feel "
            f"(max -{summary['max_real_feel_reduction_c']:.2f} °C), "
            f"{summary['avg_heat_exposure_reduction_pct']:.1f}% excess heat reduced, "
            f"+{summary['avg_shade_gain_pct']:.1f}% shade, "
            f"+{summary['avg_extra_dist_m']:.0f} m (+{summary['avg_extra_dist_pct']:.1f}% / +{summary['avg_extra_time_min']:.2f} min)"
        )
        print(f"[{city_key}] Interactive map saved -> {map_html}")
        print(f"[{city_key}] GeoJSON saved -> {streets_gj.name}, {routes_gj.name}")

    chart_png = build_kpi_chart(summaries)
    summary_md = write_report_summary(summaries, street_counts)
    print("=" * 72)
    print(f"KPI summary chart saved -> {chart_png}")
    print(f"Report summary saved    -> {summary_md}")
    print("Done! Open results/*.html in any browser to view the interactive maps.")


if __name__ == "__main__":
    main()
