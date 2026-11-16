"""
Configuration settings for the GOES Satellite Imagery REST API.
Loads environment variables or defaults to project directories.
"""
import os
from pathlib import Path
from typing import List
import yaml

# Base directory for api
API_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = API_DIR.parent

# Read environment variables with sensible local development defaults
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", str(PROJECT_ROOT / "app" / "output")))
LATEST_DIR = Path(os.getenv("LATEST_DIR", str(PROJECT_ROOT / "app" / "latest")))
CONFIG_FILE = Path(os.getenv("CONFIG_FILE", str(PROJECT_ROOT / "app" / "config.yaml")))
COLORS_DIR = Path(os.getenv("COLORS_DIR", str(PROJECT_ROOT / "app" / "colors")))

cors_env = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS: List[str] = [
    origin.strip() 
    for origin in cors_env.split(",") 
    if origin.strip()
]

def load_system_config() -> dict:
    """Loads configuration from app/config.yaml if present."""
    if CONFIG_FILE.is_file():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}

def get_extent_bounds() -> dict:
    """
    Returns geographical bounds in GeoJSON / Leaflet order.
    extent_default in config.yaml is [West, South, East, North]
    """
    cfg = load_system_config()
    plotting_cfg = cfg.get("plotting", {})
    extent = plotting_cfg.get("extent_default", [-100.0, -14.0, -50.0, 30.0])
    
    west = float(extent[0])
    south = float(extent[1])
    east = float(extent[2])
    north = float(extent[3])
    center_lat = (south + north) / 2.0
    center_lon = (west + east) / 2.0
    
    return {
        "crs": "EPSG:4326",
        "west": west,
        "south": south,
        "east": east,
        "north": north,
        # Leaflet LatLngBounds: [[south, west], [north, east]]
        "leaflet_bounds": [[south, west], [north, east]],
        # GeoJSON Bounding Box: [min_lon, min_lat, max_lon, max_lat]
        "bbox": [west, south, east, north],
        "center": [center_lat, center_lon],
        "zoom_default": 4
    }

