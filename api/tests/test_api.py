"""
Unit tests for the GOES Imagery REST API.
"""
import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert "storage" in data


def test_metadata_bounds():
    response = client.get("/api/v1/metadata/bounds")
    assert response.status_code == 200
    data = response.json()
    assert data["crs"] == "EPSG:4326"
    assert "leaflet_bounds" in data
    assert len(data["leaflet_bounds"]) == 2
    # Verify [[south, west], [north, east]]
    south, west = data["leaflet_bounds"][0]
    north, east = data["leaflet_bounds"][1]
    assert south < north
    assert west < east


def test_list_channels():
    response = client.get("/api/v1/channels")
    assert response.status_code == 200
    channels = response.json()
    assert len(channels) == 16
    channel_ids = [c["channel"] for c in channels]
    assert "C01" in channel_ids
    assert "C13" in channel_ids


def test_get_single_channel():
    response = client.get("/api/v1/channels/C13")
    assert response.status_code == 200
    data = response.json()
    assert data["channel"] == "C13"
    assert data["spectrum"] == "Thermal IR"
    assert data["physical_unit"] == "°C"

    # Not found case
    err_res = client.get("/api/v1/channels/C99")
    assert err_res.status_code == 404


def test_get_legend():
    # Test thermal IR legend
    res_ir = client.get("/api/v1/legends/C13")
    assert res_ir.status_code == 200
    legend_ir = res_ir.json()
    assert legend_ir["unit"] == "°C"
    assert "gradient_css" in legend_ir
    assert len(legend_ir["stops"]) > 0

    # Test visible reflectance legend
    res_vis = client.get("/api/v1/legends/C02")
    assert res_vis.status_code == 200
    legend_vis = res_vis.json()
    assert legend_vis["unit"] == "%"


def test_catalog_inventory():
    response = client.get("/api/v1/catalog")
    assert response.status_code == 200
    data = response.json()
    assert "julian_days" in data
    assert "total_frames" in data


def test_latest_products():
    response = client.get("/api/v1/latest")
    assert response.status_code == 200
    data = response.json()
    assert "products" in data


def test_frames_for_animation():
    response = client.get("/api/v1/frames?channel=C01&limit=10")
    assert response.status_code == 200
    data = response.json()
    assert data["channel"] == "C01"
    assert "frames" in data
    assert "bounds" in data
    assert isinstance(data["frames"], list)


def test_stream_image_and_latest():
    # If there are frames, test streaming
    response = client.get("/api/v1/frames?channel=C01&limit=1")
    frames = response.json().get("frames", [])
    if frames:
        url = frames[0]["url"]
        img_res = client.get(url)
        assert img_res.status_code == 200
        assert "image/png" in img_res.headers.get("content-type", "")
        assert "Cache-Control" in img_res.headers

    # Test latest streaming
    latest_res = client.get("/api/v1/latest/latestC01.png")
    if latest_res.status_code == 200:
        assert "image/png" in latest_res.headers.get("content-type", "")


def test_root_redirect():
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (307, 302)
    assert response.headers["location"] == "/docs"
