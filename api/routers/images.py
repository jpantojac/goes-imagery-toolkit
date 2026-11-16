"""
Images router: High-performance cached serving of satellite PNGs, GeoTIFFs, and PGWs.
"""
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse
from pathlib import Path
import os
import hashlib
from api.config import OUTPUT_DIR, LATEST_DIR

router = APIRouter(prefix="/api/v1", tags=["Image & GeoTIFF Streaming"])


@router.get("/images/{julian_day}/{channel}/{filename}", summary="Stream Processed Image Frame")
def stream_output_image(julian_day: str, channel: str, filename: str):
    """
    Streams a georeferenced satellite PNG, GeoTIFF, or Worldfile (.pgw).
    Past frames are immutable and served with aggressive HTTP caching (ETag & Cache-Control).
    """
    file_path = OUTPUT_DIR / julian_day / channel.upper() / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Requested satellite file does not exist.")

    # Media type detection
    suffix = file_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".pgw": "text/plain"
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    stat = file_path.stat()
    etag = hashlib.md5(f"{file_path.name}-{stat.st_mtime}-{stat.st_size}".encode()).hexdigest()

    headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "ETag": f'"{etag}"'
    }

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers=headers,
        filename=filename
    )


@router.get("/latest/{filename}", summary="Stream Latest Snapshot")
def stream_latest_image(filename: str):
    """
    Streams the latest image from latestCXX.png or latestCXX.pgw.
    Uses short cache duration to ensure real-time updates.
    """
    file_path = LATEST_DIR / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Latest snapshot '{filename}' not found.")

    suffix = file_path.suffix.lower()
    media_types = {
        ".png": "image/png",
        ".tif": "image/tiff",
        ".pgw": "text/plain"
    }
    media_type = media_types.get(suffix, "application/octet-stream")

    stat = file_path.stat()
    etag = hashlib.md5(f"{file_path.name}-{stat.st_mtime}-{stat.st_size}".encode()).hexdigest()

    headers = {
        "Cache-Control": "public, max-age=30, must-revalidate",
        "ETag": f'"{etag}"'
    }

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers=headers,
        filename=filename
    )
