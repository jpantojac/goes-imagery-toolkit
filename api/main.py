"""
GOES Imagery Toolkit - REST API Service.
Decoupled high-performance spatial API for satellite imagery distribution,
metadata cataloging, and Web GIS animation streaming.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import os
import shutil
from datetime import datetime, timezone

from api.config import (
    CORS_ORIGINS,
    OUTPUT_DIR,
    LATEST_DIR,
    CONFIG_FILE,
    load_system_config
)
from api.routers import metadata, catalog, images

app = FastAPI(
    title="GOES Satellite Imagery Toolkit API",
    description="""
# 🛰️ GOES ABI L1b/L2 Spatial & Animation API

High-performance REST API serving calibrated satellite imagery from **NOAA GOES-16 and GOES-19** Advanced Baseline Imagers (ABI).

### Key Features:
- **Spatial Extents & Bounding Boxes**: GeoJSON and Leaflet coordinate bounds.
- **Spectral Catalog**: Wavelength, resolution, and meteorological use for channels C01–C16.
- **Animation Sequence Engine**: Chronological image series optimized for 60 FPS Web GIS rendering.
- **Calibrated Colorbars**: Physical stops (°C, %) and CSS linear gradients.
- **High-Throughput Caching**: Immutable image frame delivery with ETags and HTTP Cache-Control.
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Configuration for Frontend and 3rd Party Clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Service Routers
app.include_router(metadata.router)
app.include_router(catalog.router)
app.include_router(images.router)


@app.get("/", include_in_schema=False)
def root():
    """Redirect root requests to interactive Swagger documentation."""
    return RedirectResponse(url="/docs")


@app.get("/api/v1/health", tags=["System"])
def health_check():
    """
    Returns system status, directory mounts, and storage diagnostics.
    """
    total, used, free = shutil.disk_usage(os.path.abspath("."))
    gb = 1024 ** 3
    
    return {
        "status": "online",
        "service": "goes-imagery-api",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "storage": {
            "output_dir_exists": OUTPUT_DIR.is_dir(),
            "latest_dir_exists": LATEST_DIR.is_dir(),
            "config_file_exists": CONFIG_FILE.is_file(),
            "disk_total_gb": round(total / gb, 2),
            "disk_free_gb": round(free / gb, 2)
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
