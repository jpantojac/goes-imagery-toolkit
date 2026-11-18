"""
Legend service: provides color ramps, stops, and CSS linear gradients
for ABI channels (C01 to C16) to render in Web GIS colorbars.
"""
from pathlib import Path
from typing import Dict, List, Any, Optional
import re
from api.config import COLORS_DIR, load_system_config


def parse_cpt_file(cpt_path: Path) -> List[Dict[str, Any]]:
    """
    Parses a GMT CPT file into a list of color stops.
    Line format: val1 r1 g1 b1 val2 r2 g2 b2
    """
    stops = []
    if not cpt_path.is_file():
        return stops

    try:
        with open(cpt_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or line.startswith(("B", "F", "N")):
                    continue
                parts = line.split()
                if len(parts) >= 8:
                    try:
                        v1 = float(parts[0])
                        r1, g1, b1 = int(parts[1]), int(parts[2]), int(parts[3])
                        v2 = float(parts[4])
                        r2, g2, b2 = int(parts[5]), int(parts[6]), int(parts[7])
                        if not stops:
                            stops.append({"val": v1, "r": r1, "g": g1, "b": b1})
                        stops.append({"val": v2, "r": r2, "g": g2, "b": b2})
                    except ValueError:
                        continue
    except Exception:
        pass
    return stops


def get_channel_legend(channel: str) -> Dict[str, Any]:
    """
    Returns the calibrated colorbar definition for a specific channel.
    Includes min, max, unit (°C or %), and CSS gradient string.
    """
    ch_num = channel.upper().replace("C", "").zfill(2)
    cfg = load_system_config()
    family = cfg.get("colors", {}).get("family", "default")
    
    # Visible channels (C01 - C06): Reflectance
    if ch_num in ["01", "02", "03", "04", "05", "06"]:
        unit = "%"
        min_val = 0.0
        max_val = 100.0
        # Grayscale reflectance ramp (black to white)
        stops = [
            {"val": 0.0, "hex": "#000000", "label": "0%"},
            {"val": 25.0, "hex": "#404040", "label": "25%"},
            {"val": 50.0, "hex": "#808080", "label": "50%"},
            {"val": 75.0, "hex": "#bfbfbf", "label": "75%"},
            {"val": 100.0, "hex": "#ffffff", "label": "100%"},
        ]
        gradient_css = "linear-gradient(to right, #000000 0%, #404040 25%, #808080 50%, #bfbfbf 75%, #ffffff 100%)"
        description = "Calibrated Solar Reflectance (Albedo)"
    
    # Mid/Upper Water Vapor (C08, C09, C10)
    elif ch_num in ["08", "09", "10"]:
        unit = "°C"
        min_val = -90.0
        max_val = 20.0
        # Operational WV spectrum: cyan -> green -> red -> orange -> dark
        stops = [
            {"val": -90.0, "hex": "#00ffff", "label": "-90°C"},
            {"val": -70.0, "hex": "#7db154", "label": "-70°C"},
            {"val": -50.0, "hex": "#e2e2ec", "label": "-50°C"},
            {"val": -30.0, "hex": "#000073", "label": "-30°C"},
            {"val": -10.0, "hex": "#ffb500", "label": "-10°C"},
            {"val": 20.0, "hex": "#720000", "label": "+20°C"}
        ]
        gradient_css = "linear-gradient(to right, #00ffff 0%, #7db154 20%, #e2e2ec 40%, #000073 60%, #ffb500 80%, #720000 100%)"
        description = "Tropospheric Water Vapor Brightness Temperature"
        
    # Shortwave IR / Fire (C07)
    elif ch_num == "07":
        unit = "°C"
        min_val = -90.0
        max_val = 130.0
        stops = [
            {"val": -90.0, "hex": "#7c7c7c", "label": "-90°C"},
            {"val": -40.0, "hex": "#ffaa00", "label": "-40°C"},
            {"val": 0.0, "hex": "#ccb9b9", "label": "0°C"},
            {"val": 50.0, "hex": "#ffffff", "label": "+50°C"},
            {"val": 130.0, "hex": "#3c3c3c", "label": "+130°C (Fire)"}
        ]
        gradient_css = "linear-gradient(to right, #7c7c7c 0%, #ff0000 25%, #ffaa00 35%, #00a528 45%, #ccb9b9 55%, #ffffff 70%, #3c3c3c 100%)"
        description = "Shortwave IR / Wildfire & Hotspot Detection"

    # Thermal IR Window (C11, C12, C13, C14, C15)
    elif ch_num in ["11", "12", "13", "14", "15"]:
        unit = "°C"
        min_val = -100.0
        max_val = 40.0
        # McIDAS BD convective enhancement: deep convective tops (white/cyan/violet) to warm ground (black)
        stops = [
            {"val": -100.0, "hex": "#ffffff", "label": "-100°C"},
            {"val": -80.0, "hex": "#b90000", "label": "-80°C"},
            {"val": -60.0, "hex": "#ff9800", "label": "-60°C"},
            {"val": -40.0, "hex": "#0099ff", "label": "-40°C"},
            {"val": -20.0, "hex": "#005677", "label": "-20°C"},
            {"val": 0.0, "hex": "#a0a0a0", "label": "0°C"},
            {"val": 40.0, "hex": "#1a1a1a", "label": "+40°C"}
        ]
        gradient_css = "linear-gradient(to right, #ffffff 0%, #b90000 15%, #ff9800 30%, #34ff00 45%, #0099ff 55%, #a0a0a0 75%, #1a1a1a 100%)"
        description = "Thermal IR Window / Cloud-Top Brightness Temperature"

    # Band 16 (CO2)
    else:
        unit = "°C"
        min_val = -120.0
        max_val = 40.0
        stops = [
            {"val": -120.0, "hex": "#ffffff", "label": "-120°C"},
            {"val": -80.0, "hex": "#cccccc", "label": "-80°C"},
            {"val": -40.0, "hex": "#888888", "label": "-40°C"},
            {"val": 0.0, "hex": "#444444", "label": "0°C"},
            {"val": 40.0, "hex": "#000000", "label": "+40°C"}
        ]
        gradient_css = "linear-gradient(to right, #ffffff 0%, #cccccc 25%, #888888 50%, #444444 75%, #000000 100%)"
        description = "CO2 Longwave IR / Cloud Top Height"

    return {
        "channel": f"C{ch_num}",
        "family": family,
        "unit": unit,
        "min": min_val,
        "max": max_val,
        "description": description,
        "stops": stops,
        "gradient_css": gradient_css
    }
