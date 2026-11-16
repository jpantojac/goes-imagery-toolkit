"""
Metadata router: Geographical extents, projection, channel registry, and colorbar legends.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
from api.config import get_extent_bounds
from api.services.catalog_service import get_all_channels, get_channel_by_id
from api.services.legend_service import get_channel_legend

router = APIRouter(prefix="/api/v1", tags=["Metadata & Georeferencing"])


@router.get("/metadata/bounds", summary="Geographical Bounding Box & Map Extent")
def get_bounds():
    """
    Returns the official projection extent and bounding boxes in both
    Leaflet LatLngBounds (`[[south, west], [north, east]]`) and GeoJSON BBox format.
    """
    return get_extent_bounds()


@router.get("/channels", summary="List All 16 ABI Channels")
def list_channels():
    """
    Returns complete scientific catalog of GOES-16/GOES-19 ABI channels (C01 to C16),
    including central wavelengths, spatial resolution, and meteorological use.
    """
    return get_all_channels()


@router.get("/channels/{channel}", summary="Get Channel Details")
def get_channel(channel: str):
    """
    Returns metadata for a specific ABI channel (e.g. C01, C13).
    """
    ch_info = get_channel_by_id(channel)
    if not ch_info:
        raise HTTPException(status_code=404, detail=f"Channel '{channel}' not found.")
    return ch_info


@router.get("/legends/{channel}", summary="Calibrated Colorbar Legend & Stops")
def get_legend(channel: str):
    """
    Returns the calibrated colorbar scale, stop values, physical unit (°C or %),
    and CSS gradient string for dynamic rendering in Web GIS viewers.
    """
    return get_channel_legend(channel)
