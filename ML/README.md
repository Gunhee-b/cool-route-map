# Pedestrian Cool-Route Path Finder (Team OnEvolution — Part 3)

This package contains Stefan's **Pedestrian Cool-Route Map** work for **Seoul (Jung-gu / Myeongdong)** and **Madrid (Centro / Puerta del Sol)**.

---

## 1. For Report, Slides & Poster (No Coding Needed)
Open the `results/` folder directly:
- `results/seoul_cool_routes.html` — Double-click to open the interactive Seoul map in Chrome/Edge (toggle the 3 demo trips in the top-right corner).
- `results/madrid_cool_routes.html` — Double-click to open the interactive Madrid map.
- `results/kpi_summary.png` — Ready-to-paste KPI chart comparing Cool Path vs. Shortest Path.
- `results/REPORT_SUMMARY.md` — Copy-pasteable text & KPI table for the Nov 29 Final Report and Dec 5 Presentation.

---

## 2. For Technical Teammates (ML / Digital Twin Integration)

### Run Locally
```bash
pip install -r requirements.txt
python run_demo.py
pytest test_router.py -v
```

### Plug In Real ML / Digital Twin Temperatures
Replace the `temp_c`, `humidity_pct`, and `shade_pct` columns (keeping the same `edge_id` values) in:
- `data/seoul_street_temperatures.csv`
- `data/madrid_street_temperatures.csv`

Then re-run `python run_demo.py`. Ground-level Real-Feel (`real_feel_c` via NOAA Heat Index + shade radiant load) recalculates automatically, and all interactive maps, GeoJSONs, KPI benchmarks, and charts will regenerate.

### Import Into GIS / 3D Tools (QGIS, Cesium, Blender, Deck.gl, GeoPandas)
Standard WGS84 GeoJSON files are already exported in `results/`:
- `results/seoul_walkable_streets.geojson` & `results/madrid_walkable_streets.geojson`
- `results/seoul_cool_paths.geojson` & `results/madrid_cool_paths.geojson`
