# Cool-Route Digital Twin — Seoul · Madrid

Team OnEvolution — Part 3: Pedestrian Cool-Route Map

거리별 체감온도·기온·그늘 비율을 색으로 보여주고, 시범 이동 3건의 **최단경로 vs 쿨루트**를 비교하는 웹 지도입니다.

## 구성

| 파일 | 내용 |
|---|---|
| `index.html` | Leaflet 기반 지도 페이지 (빌드 불필요) |
| `seoul_walkable_streets.geojson` | 서울 중구·명동 보행 구간 1,424개 |
| `seoul_cool_paths.geojson` | 서울 시범 이동 3건의 최단경로/쿨루트 |
| `madrid_walkable_streets.geojson` | 마드리드 센트로·솔 광장 보행 구간 1,966개 |
| `madrid_cool_paths.geojson` | 마드리드 시범 이동 3건의 최단경로/쿨루트 |
| `README.txt` | 데이터 설명 (좌표계 WGS84, 속성 목록) |

## 로컬에서 보기

`fetch()`로 GeoJSON을 불러오므로 파일을 더블클릭하면 열리지 않습니다. 폴더에서 간이 서버를 띄우세요.

```bash
python3 -m http.server 8000
# 브라우저에서 http://localhost:8000
```

## 배경지도 출처

© OpenStreetMap contributors (CARTO 키를 넣으면 © CARTO 추가)
