import React, { useEffect, useRef } from 'react';
import L from 'leaflet';

const BASEMAP_TILES = {
  dark: {
    url: 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',
    attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; OpenStreetMap'
  },
  satellite: {
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, Maxar, Earthstar Geographics'
  },
  osm: {
    url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/">OpenStreetMap</a>'
  }
};

export default function MapViewer({
  boundsMeta,
  frames,
  currentIndex,
  opacity,
  basemap,
  onMouseMove,
  onPreloadProgress
}) {
  const mapContainerRef = useRef(null);
  const mapRef = useRef(null);
  const tileLayerRef = useRef(null);
  const overlaysRef = useRef([]);
  const prevIndexRef = useRef(currentIndex);

  // 1. Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapRef.current) return;

    // Default Colombia / Tropical America bounds: [[-14, -100], [30, -50]]
    const defaultBounds = boundsMeta?.leaflet_bounds || [[-14.0, -100.0], [30.0, -50.0]];
    const center = boundsMeta?.center || [8.0, -75.0];

    const map = L.map(mapContainerRef.current, {
      center: center,
      zoom: 5,
      minZoom: 3,
      maxZoom: 12,
      zoomControl: false,
      attributionControl: false
    });

    // Add zoom control in top-left
    L.control.zoom({ position: 'topleft' }).addTo(map);

    // Initial tile layer
    const initialTile = BASEMAP_TILES[basemap] || BASEMAP_TILES.dark;
    tileLayerRef.current = L.tileLayer(initialTile.url, {
      maxZoom: 19,
      attribution: initialTile.attribution
    }).addTo(map);

    // Fit to initial bounds
    map.fitBounds(defaultBounds);

    // Cursor coordinates tracking
    map.on('mousemove', (e) => {
      if (onMouseMove) {
        onMouseMove({ lat: e.latlng.lat, lon: e.latlng.lng });
      }
    });

    map.on('mouseout', () => {
      if (onMouseMove) {
        onMouseMove({ lat: null, lon: null });
      }
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // 2. Handle Basemap Tile Switch
  useEffect(() => {
    if (!mapRef.current || !tileLayerRef.current) return;
    const tile = BASEMAP_TILES[basemap] || BASEMAP_TILES.dark;
    tileLayerRef.current.setUrl(tile.url);
  }, [basemap]);

  // 3. Preload and Manage Overlays Array when frames change
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Clear existing overlays
    overlaysRef.current.forEach(overlay => map.removeLayer(overlay));
    overlaysRef.current = [];

    if (!frames || frames.length === 0) return;

    const defaultBounds = boundsMeta?.leaflet_bounds || [[-14.0, -100.0], [30.0, -50.0]];
    let loadedCount = 0;

    // Create L.imageOverlay for each frame in the buffer
    const newOverlays = frames.map((frame, index) => {
      const frameBounds = frame.bounds || defaultBounds;
      const initialOpacity = index === currentIndex ? opacity : 0;

      const overlay = L.imageOverlay(frame.url, frameBounds, {
        opacity: initialOpacity,
        interactive: false,
        crossOrigin: true
      });

      // Track image load for progress
      const img = new Image();
      img.src = frame.url;
      img.onload = () => {
        loadedCount += 1;
        if (onPreloadProgress) {
          onPreloadProgress(loadedCount);
        }
      };

      overlay.addTo(map);
      return overlay;
    });

    overlaysRef.current = newOverlays;
    prevIndexRef.current = currentIndex;
  }, [frames]);

  // 4. Ultra-smooth 60 FPS Frame & Opacity Swap
  useEffect(() => {
    const overlays = overlaysRef.current;
    if (!overlays || overlays.length === 0) return;

    const prevIndex = prevIndexRef.current;

    // Hide previous overlay
    if (prevIndex !== currentIndex && overlays[prevIndex]) {
      overlays[prevIndex].setOpacity(0);
    }

    // Show current overlay
    if (overlays[currentIndex]) {
      overlays[currentIndex].setOpacity(opacity);
    }

    prevIndexRef.current = currentIndex;
  }, [currentIndex, opacity]);

  return (
    <div className="relative w-full h-full flex-1 overflow-hidden">
      <div ref={mapContainerRef} className="w-full h-full" />
    </div>
  );
}
