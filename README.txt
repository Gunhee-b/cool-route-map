Digital Twin GeoJSON Exports (Team OnEvolution — Part 3: Pedestrian Cool-Route Map)

Coordinate System: WGS84 (EPSG:4326, [lon, lat]) — ready to import into QGIS, Cesium, Deck.gl, Mapbox, Blender, Unity, or Python/GeoPandas.

Files:
- seoul_walkable_streets.geojson  : All 1,424 mapped walkable street segments in Jung-gu / Myeongdong (properties: edge_id, name, highway, length_m, temp_c, humidity_pct, shade_pct, real_feel_c).
- seoul_cool_paths.geojson        : Shortest Path vs. Cool Path geometries for 3 demo pedestrian trips in Seoul.
- madrid_walkable_streets.geojson : All 1,966 mapped walkable street segments in Centro / Puerta del Sol.
- madrid_cool_paths.geojson       : Shortest Path vs. Cool Path geometries for 3 demo pedestrian trips in Madrid.

Tip: Each street segment has a unique `edge_id` matching `data/*_street_temperatures.csv` in the main routing package, so Digital Twin shade/temperature outputs can be joined directly back to the pedestrian router.
