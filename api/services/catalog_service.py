"""
Catalog and Imagery Indexing Service for GOES ABI Products.
Provides access to channels, available timestamps, frames for animation,
and latest imagery metadata.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
import os
import re
from datetime import datetime, timezone
from api.config import OUTPUT_DIR, LATEST_DIR, get_extent_bounds

# Complete NOAA GOES-16/19 Advanced Baseline Imager (ABI) Channel Definitions
ABI_CHANNELS: Dict[str, Dict[str, Any]] = {
    "C01": {
        "channel": "C01",
        "number": 1,
        "name": "Blue (Visible)",
        "wavelength_um": 0.47,
        "resolution_km": 1.0,
        "spectrum": "Visible",
        "description": "Daytime aerosol, haze, smoke and dust detection.",
        "physical_unit": "%"
    },
    "C02": {
        "channel": "C02",
        "number": 2,
        "name": "Red (Visible)",
        "wavelength_um": 0.64,
        "resolution_km": 0.5,
        "spectrum": "Visible",
        "description": "Highest resolution band for clouds, severe weather, and daytime surface features.",
        "physical_unit": "%"
    },
    "C03": {
        "channel": "C03",
        "number": 3,
        "name": "Veggie (Near-IR)",
        "wavelength_um": 0.86,
        "resolution_km": 1.0,
        "spectrum": "Near-IR",
        "description": "Vegetation monitoring, land/water boundary contrast, and burn scar detection.",
        "physical_unit": "%"
    },
    "C04": {
        "channel": "C04",
        "number": 4,
        "name": "Cirrus (Near-IR)",
        "wavelength_um": 1.37,
        "resolution_km": 2.0,
        "spectrum": "Near-IR",
        "description": "Thin cirrus cloud detection during daytime.",
        "physical_unit": "%"
    },
    "C05": {
        "channel": "C05",
        "number": 5,
        "name": "Snow/Ice (Near-IR)",
        "wavelength_um": 1.61,
        "resolution_km": 1.0,
        "spectrum": "Near-IR",
        "description": "Cloud-top phase discrimination (water droplets vs ice crystals) and snow cover.",
        "physical_unit": "%"
    },
    "C06": {
        "channel": "C06",
        "number": 6,
        "name": "Cloud Particle Size (Near-IR)",
        "wavelength_um": 2.24,
        "resolution_km": 2.0,
        "spectrum": "Near-IR",
        "description": "Cloud microphysics, particle sizing, and hot spot/fire assessment.",
        "physical_unit": "%"
    },
    "C07": {
        "channel": "C07",
        "number": 7,
        "name": "Shortwave Window (Thermal IR)",
        "wavelength_um": 3.90,
        "resolution_km": 2.0,
        "spectrum": "Shortwave IR",
        "description": "Wildfire detection, surface hot spots, fog and nighttime low stratus.",
        "physical_unit": "°C"
    },
    "C08": {
        "channel": "C08",
        "number": 8,
        "name": "Upper-Level Water Vapor",
        "wavelength_um": 6.19,
        "resolution_km": 2.0,
        "spectrum": "Water Vapor",
        "description": "Upper tropospheric moisture (300-400 hPa), jet stream dynamics, and vorticity.",
        "physical_unit": "°C"
    },
    "C09": {
        "channel": "C09",
        "number": 9,
        "name": "Mid-Level Water Vapor",
        "wavelength_um": 6.95,
        "resolution_km": 2.0,
        "spectrum": "Water Vapor",
        "description": "Mid-tropospheric moisture (400-500 hPa), tracking synoptic troughs and ridges.",
        "physical_unit": "°C"
    },
    "C10": {
        "channel": "C10",
        "number": 10,
        "name": "Lower-Level Water Vapor",
        "wavelength_um": 7.34,
        "resolution_km": 2.0,
        "spectrum": "Water Vapor",
        "description": "Lower tropospheric moisture (600-700 hPa) and pre-convective environment evaluation.",
        "physical_unit": "°C"
    },
    "C11": {
        "channel": "C11",
        "number": 11,
        "name": "Cloud-Top Phase (Thermal IR)",
        "wavelength_um": 8.44,
        "resolution_km": 2.0,
        "spectrum": "Thermal IR",
        "description": "Cloud particle phase detection, volcanic SO2 and dust tracking.",
        "physical_unit": "°C"
    },
    "C12": {
        "channel": "C12",
        "number": 12,
        "name": "Ozone (Thermal IR)",
        "wavelength_um": 9.61,
        "resolution_km": 2.0,
        "spectrum": "Thermal IR",
        "description": "Total atmospheric ozone, stratospheric intrusions, and tropopause folds.",
        "physical_unit": "°C"
    },
    "C13": {
        "channel": "C13",
        "number": 13,
        "name": "Clean IR Longwave Window",
        "wavelength_um": 10.33,
        "resolution_km": 2.0,
        "spectrum": "Thermal IR",
        "description": "Primary window channel for cloud top temperature and severe convective storm monitoring.",
        "physical_unit": "°C"
    },
    "C14": {
        "channel": "C14",
        "number": 14,
        "name": "IR Longwave Window",
        "wavelength_um": 11.20,
        "resolution_km": 2.0,
        "spectrum": "Thermal IR",
        "description": "Traditional IR window for clouds, surface skin temperature, and convective tops.",
        "physical_unit": "°C"
    },
    "C15": {
        "channel": "C15",
        "number": 15,
        "name": "Dirty Longwave Window",
        "wavelength_um": 12.30,
        "resolution_km": 2.0,
        "spectrum": "Thermal IR",
        "description": "Low-level moisture estimation, split-window differences, and dust identification.",
        "physical_unit": "°C"
    },
    "C16": {
        "channel": "C16",
        "number": 16,
        "name": "CO2 Longwave IR",
        "wavelength_um": 13.30,
        "resolution_km": 2.0,
        "spectrum": "Thermal IR",
        "description": "Cloud top height estimation and atmospheric temperature profiling.",
        "physical_unit": "°C"
    }
}


def parse_timestamp_to_iso(ts_str: str) -> Optional[str]:
    """
    Parses timestamp in format YYYYMMDDHHMM or YYYYMMDDHHMMSS to ISO 8601 UTC string.
    Example: '202611131920' -> '2026-11-13T19:20:00Z'
    """
    if not ts_str:
        return None
    try:
        if len(ts_str) == 12:
            dt = datetime.strptime(ts_str, "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        elif len(ts_str) == 14:
            dt = datetime.strptime(ts_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        pass
    return None


def parse_pgw_bounds(pgw_path: Path, img_width: int = 2048, img_height: int = 2048) -> Optional[List[List[float]]]:
    """
    Reads an ESRI Worldfile (.pgw) to compute [[south, west], [north, east]].
    Format of worldfile:
      Line 1: dx
      Line 2: rot_y (0)
      Line 3: rot_x (0)
      Line 4: dy (negative)
      Line 5: top-left x center
      Line 6: top-left y center
    """
    if not pgw_path.is_file():
        return None
    try:
        with open(pgw_path, "r", encoding="utf-8") as f:
            lines = [float(line.strip()) for line in f if line.strip()]
        if len(lines) >= 6:
            dx = lines[0]
            dy = lines[3]
            top_left_x = lines[4]
            top_left_y = lines[5]
            
            west = top_left_x - (dx / 2.0)
            north = top_left_y - (dy / 2.0)
            east = west + (img_width * dx)
            south = north + (img_height * dy)
            return [[round(south, 4), round(west, 4)], [round(north, 4), round(east, 4)]]
    except Exception:
        pass
    return None


def get_all_channels() -> List[Dict[str, Any]]:
    """Returns list of all 16 ABI channel metadata definitions."""
    return list(ABI_CHANNELS.values())


def get_channel_by_id(channel_id: str) -> Optional[Dict[str, Any]]:
    """Normalized lookup for C01-C16."""
    norm_id = channel_id.upper()
    if not norm_id.startswith("C"):
        norm_id = f"C{norm_id.zfill(2)}"
    return ABI_CHANNELS.get(norm_id)


def get_catalog_summary() -> Dict[str, Any]:
    """
    Scans the OUTPUT_DIR directory tree:
      OUTPUT_DIR / {julian_day} / {channel} / {timestamp}.png
    Returns available Julian days, channels found, and date intervals.
    """
    if not OUTPUT_DIR.is_dir():
        return {
            "julian_days": [],
            "total_channels": 0,
            "total_frames": 0,
            "days_detail": {}
        }
    
    days_detail = {}
    total_frames = 0
    all_channels_found = set()

    # Iterate over julian day directories (e.g. '317')
    for day_dir in sorted(OUTPUT_DIR.iterdir()):
        if day_dir.is_dir() and not day_dir.name.startswith("."):
            j_day = day_dir.name
            day_channels = {}
            for ch_dir in sorted(day_dir.iterdir()):
                if ch_dir.is_dir() and ch_dir.name.startswith("C"):
                    ch_name = ch_dir.name
                    all_channels_found.add(ch_name)
                    # Count valid pngs
                    pngs = sorted([p.stem for p in ch_dir.glob("*.png")])
                    if pngs:
                        day_channels[ch_name] = {
                            "count": len(pngs),
                            "first_timestamp": pngs[0],
                            "last_timestamp": pngs[-1]
                        }
                        total_frames += len(pngs)
            if day_channels:
                days_detail[j_day] = day_channels

    return {
        "julian_days": sorted(list(days_detail.keys())),
        "total_channels": len(all_channels_found),
        "total_frames": total_frames,
        "days_detail": days_detail
    }


def get_latest_products() -> Dict[str, Any]:
    """
    Scans LATEST_DIR or latest timestamps in OUTPUT_DIR to deliver
    the newest available frame for each channel.
    """
    default_bounds = get_extent_bounds()["leaflet_bounds"]
    latest_map = {}

    # 1. Check LATEST_DIR for latestCXX.png
    if LATEST_DIR.is_dir():
        for ch_key in sorted(ABI_CHANNELS.keys()):
            png_file = LATEST_DIR / f"latest{ch_key}.png"
            pgw_file = LATEST_DIR / f"latest{ch_key}.pgw"
            if png_file.is_file():
                bounds = parse_pgw_bounds(pgw_file) or default_bounds
                stat = png_file.stat()
                mtime_iso = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                latest_map[ch_key] = {
                    "channel": ch_key,
                    "url": f"/api/v1/latest/{ch_key}.png",
                    "bounds": bounds,
                    "last_modified": mtime_iso,
                    "size_bytes": stat.st_size
                }

    # 2. If LATEST_DIR is empty, find newest frame per channel in OUTPUT_DIR
    if not latest_map and OUTPUT_DIR.is_dir():
        for ch_key in ABI_CHANNELS.keys():
            frames = get_frames_for_channel(channel=ch_key, limit=1)
            if frames.get("frames"):
                f = frames["frames"][0]
                latest_map[ch_key] = {
                    "channel": ch_key,
                    "url": f["url"],
                    "timestamp": f["timestamp"],
                    "iso_utc": f["iso_utc"],
                    "bounds": f["bounds"]
                }

    return {
        "count": len(latest_map),
        "products": latest_map
    }


def get_frames_for_channel(
    channel: str, 
    limit: int = 24, 
    date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Retrieves chronological frames for a specific channel to power fluid Web GIS animations.
    
    Args:
        channel: ABI channel ID (e.g. 'C13', 'C02')
        limit: Max frames to retrieve (e.g. 6, 12, 24, 48)
        date: Optional date filter in YYYYMMDD format
    """
    norm_ch = channel.upper()
    if not norm_ch.startswith("C"):
        norm_ch = f"C{norm_ch.zfill(2)}"

    default_bounds = get_extent_bounds()["leaflet_bounds"]
    raw_frames = []

    if OUTPUT_DIR.is_dir():
        for day_dir in sorted(OUTPUT_DIR.iterdir()):
            if not day_dir.is_dir() or day_dir.name.startswith("."):
                continue
            j_day = day_dir.name
            ch_dir = day_dir / norm_ch
            if not ch_dir.is_dir():
                continue

            for png_path in sorted(ch_dir.glob("*.png")):
                ts = png_path.stem
                # Check date filter if requested
                if date and not ts.startswith(date):
                    continue

                tif_path = ch_dir / f"{ts}.tif"
                pgw_path = ch_dir / f"{ts}.pgw"
                bounds = parse_pgw_bounds(pgw_path) or default_bounds

                iso_utc = parse_timestamp_to_iso(ts)
                raw_frames.append({
                    "timestamp": ts,
                    "iso_utc": iso_utc,
                    "channel": norm_ch,
                    "julian_day": j_day,
                    "filename": png_path.name,
                    "url": f"/api/v1/images/{j_day}/{norm_ch}/{png_path.name}",
                    "tif_url": f"/api/v1/images/{j_day}/{norm_ch}/{tif_path.name}" if tif_path.is_file() else None,
                    "bounds": bounds
                })

    # Sort frames chronologically by timestamp
    raw_frames.sort(key=lambda x: x["timestamp"])

    # If limit specified, take the last N (most recent N frames in chronological order)
    if limit > 0 and len(raw_frames) > limit:
        selected_frames = raw_frames[-limit:]
    else:
        selected_frames = raw_frames

    return {
        "channel": norm_ch,
        "channel_meta": ABI_CHANNELS.get(norm_ch, {}),
        "count": len(selected_frames),
        "total_available": len(raw_frames),
        "bounds": default_bounds,
        "frames": selected_frames
    }
