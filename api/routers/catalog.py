"""
Catalog router: Temporal inventory, latest frames, and animation frame sequences.
"""
from fastapi import APIRouter, Query
from typing import Optional
from api.services.catalog_service import (
    get_catalog_summary,
    get_latest_products,
    get_frames_for_channel
)

router = APIRouter(prefix="/api/v1", tags=["Catalog & Imagery Inventory"])


@router.get("/catalog", summary="Get Inventory of Available Imagery")
def get_catalog():
    """
    Returns an index of all processed Julian days, channels present, and frame counts.
    """
    return get_catalog_summary()


@router.get("/latest", summary="Get Latest Frame for All Channels")
def get_latest():
    """
    Returns the newest processed satellite image for every available channel,
    with direct URLs and georeferenced bounding boxes.
    """
    return get_latest_products()


@router.get("/frames", summary="Get Chronological Frames for Animation")
def get_frames(
    channel: str = Query(..., description="ABI Channel ID (e.g. C01, C09, C13)"),
    limit: int = Query(24, ge=1, le=120, description="Number of most recent frames to retrieve"),
    date: Optional[str] = Query(None, description="Optional date filter YYYYMMDD")
):
    """
    Retrieves an ordered array of imagery frames for fluid Web GIS animations.
    Frames are sorted chronologically from oldest to newest.
    """
    return get_frames_for_channel(channel=channel, limit=limit, date=date)
