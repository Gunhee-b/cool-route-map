"""Configuration for Team OnEvolution's pedestrian cool-route prototype."""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"

# Default routing parameters
WALK_SPEED_MPS = 1.3          # Average pedestrian walking speed (~4.7 km/h)
TEMP_BASELINE_C = 30.0        # Reference real-feel comfort threshold (°C)
DEFAULT_HEAT_ALPHA = 0.65     # Trade-off weight: higher = stronger preference for cooler streets

CITIES = {
    "seoul": {
        "display_name": "Seoul (Jung-gu / Myeongdong)",
        "center_lat": 37.5636,
        "center_lon": 126.9826,
        "radius_m": 550,         # ~1.1 km x 1.1 km walkable urban core
        "base_temp_c": 34.0,     # Typical peak summer afternoon air temperature (°C)
        "base_humidity_pct": 70.0,  # Humid East Asian monsoon summer relative humidity (%)
        "demo_trips": [
            {
                "name": "City Hall → Myeongdong Cathedral",
                "start": (37.5658, 126.9779),
                "end": (37.5632, 126.9873),
            },
            {
                "name": "Euljiro 1-ga → Namsan Cable Car Footpath",
                "start": (37.5660, 126.9822),
                "end": (37.5594, 126.9845),
            },
            {
                "name": "Hoehyeon Station → Euljiro 3-ga",
                "start": (37.5596, 126.9786),
                "end": (37.5663, 126.9876),
            },
        ],
    },
    "madrid": {
        "display_name": "Madrid (Centro / Puerta del Sol)",
        "center_lat": 40.4168,
        "center_lon": -3.7038,
        "radius_m": 550,         # ~1.1 km x 1.1 km walkable urban core
        "base_temp_c": 37.5,     # Typical peak summer afternoon air temperature (°C)
        "base_humidity_pct": 25.0,  # Dry Iberian continental summer relative humidity (%)
        "demo_trips": [
            {
                "name": "Plaza Mayor → Banco de España Direction",
                "start": (40.4154, -3.7074),
                "end": (40.4184, -3.6986),
            },
            {
                "name": "Callao → Barrio de las Letras",
                "start": (40.4200, -3.7058),
                "end": (40.4139, -3.6994),
            },
            {
                "name": "Ópera → Tirso de Molina",
                "start": (40.4181, -3.7090),
                "end": (40.4126, -3.7042),
            },
        ],
    },
}
