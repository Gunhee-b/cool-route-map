# Part 3: Pedestrian Cool-Route Map — Summary for Final Report & Slides

## Method Overview
To guide pedestrians away from urban heat hotspots, we built a city-agnostic **heat-weighted pedestrian routing engine** tested on ~1.1 km × 1.1 km urban cores in **Seoul (Jung-gu / Myeongdong)** and **Madrid (Centro / Puerta del Sol)**:

1. **Walkable Street Network**: Extracted every walkable street segment (sidewalks, pedestrian zones, alleys, crosswalks, park paths; excluding car-only roads) from OpenStreetMap.
2. **Ground-Level Real-Feel Heat Model (Humidity + Shade)**: Because **Seoul's summer heat is humid (~70% RH)** while **Madrid's is dry (~25% RH)**, dry air temperature alone understates pedestrian heat stress in Korea. Each street segment's **Real-Feel temperature (°C)** combines the **NOAA Heat Index** (air temperature + relative humidity) with a **pedestrian radiant sun/shade adjustment** (`±1.8 °C` from full sun to full shade). Teammates' ML / Digital Twin predictions plug directly into `data/{city}_street_temperatures.csv` (`temp_c`, `humidity_pct`, `shade_pct`).
3. **Cool-Path Algorithm**: Using Dijkstra's shortest-path algorithm, we compare:
   - **Shortest Path**: minimizes walking distance `L(e)`.
   - **Cool Path**: minimizes real-feel heat-penalized walking cost `L(e) * (1 + alpha * max(0, T_real_feel(e) - 30°C))`, steering pedestrians along cooler, shaded streets while keeping detours short.

## KPI Results (60 Random Pedestrian Trips per City)

| Test City | Climate Baseline | Walkable Streets | Avg Real-Feel Saved | Max Real-Feel Saved | Excess Heat Reduced | Shade Gained | Extra Distance / Time |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Seoul (Jung-gu / Myeongdong)** | 34.0 °C air, **70% RH** (humid) | 1,424 | **-4.68 °C** | **-11.12 °C** | **15.9%** | **+15.0%** | +101 m (+11.1% / +1.30 min) |
| **Madrid (Centro / Puerta del Sol)** | 37.5 °C air, **25% RH** (dry) | 1,966 | **-0.97 °C** | **-2.91 °C** | **13.7%** | **+6.4%** | +47 m (+5.5% / +0.61 min) |

## Included Visuals & Data Files
- **Interactive Maps (open in any browser)**: `seoul_cool_routes.html`, `madrid_cool_routes.html`
- **KPI Chart (for report & slides)**: `kpi_summary.png`
- **GeoJSON Exports (for QGIS / Cesium / Web / Digital Twin)**: `seoul_walkable_streets.geojson`, `seoul_cool_paths.geojson`, `madrid_walkable_streets.geojson`, `madrid_cool_paths.geojson`
- **Benchmark CSVs**: `seoul_benchmark.csv`, `madrid_benchmark.csv`
