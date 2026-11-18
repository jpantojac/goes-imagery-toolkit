/**
 * API client for interacting with the GOES REST API.
 */
const API_BASE = '/api/v1';

export const DEFAULT_CHANNELS = [
  { channel: "C01", number: 1, name: "Blue (Visible)", wavelength_um: 0.47, spectrum: "Visible", physical_unit: "%", description: "Daytime aerosol, haze, smoke and dust detection." },
  { channel: "C02", number: 2, name: "Red (Visible)", wavelength_um: 0.64, spectrum: "Visible", physical_unit: "%", description: "Highest resolution band for clouds and daytime features." },
  { channel: "C03", number: 3, name: "Veggie (Near-IR)", wavelength_um: 0.86, spectrum: "Near-IR", physical_unit: "%", description: "Vegetation monitoring, land/water boundary contrast." },
  { channel: "C04", number: 4, name: "Cirrus (Near-IR)", wavelength_um: 1.37, spectrum: "Near-IR", physical_unit: "%", description: "Thin cirrus cloud detection during daytime." },
  { channel: "C05", number: 5, name: "Snow/Ice (Near-IR)", wavelength_um: 1.61, spectrum: "Near-IR", physical_unit: "%", description: "Cloud-top phase (water vs ice) and snow cover." },
  { channel: "C06", number: 6, name: "Cloud Particle (Near-IR)", wavelength_um: 2.24, spectrum: "Near-IR", physical_unit: "%", description: "Cloud microphysics and hot spot assessment." },
  { channel: "C07", number: 7, name: "Shortwave Window (IR)", wavelength_um: 3.90, spectrum: "Shortwave IR", physical_unit: "°C", description: "Wildfires, hot spots, fog and nighttime stratus." },
  { channel: "C08", number: 8, name: "Upper-Level Water Vapor", wavelength_um: 6.19, spectrum: "Water Vapor", physical_unit: "°C", description: "Upper tropospheric moisture (300-400 hPa) and jet streams." },
  { channel: "C09", number: 9, name: "Mid-Level Water Vapor", wavelength_um: 6.95, spectrum: "Water Vapor", physical_unit: "°C", description: "Mid-tropospheric moisture (400-500 hPa) and synoptic flow." },
  { channel: "C10", number: 10, name: "Lower-Level Water Vapor", wavelength_um: 7.34, spectrum: "Water Vapor", physical_unit: "°C", description: "Lower tropospheric moisture (600-700 hPa)." },
  { channel: "C11", number: 11, name: "Cloud-Top Phase (IR)", wavelength_um: 8.44, spectrum: "Thermal IR", physical_unit: "°C", description: "Cloud particle phase and volcanic SO2 tracking." },
  { channel: "C12", number: 12, name: "Ozone (IR)", wavelength_um: 9.61, spectrum: "Thermal IR", physical_unit: "°C", description: "Total column ozone and tropopause folds." },
  { channel: "C13", number: 13, name: "Clean IR Longwave Window", wavelength_um: 10.33, spectrum: "Thermal IR", physical_unit: "°C", description: "Primary window for cloud-top temperature and convective storms." },
  { channel: "C14", number: 14, name: "IR Longwave Window", wavelength_um: 11.20, spectrum: "Thermal IR", physical_unit: "°C", description: "Traditional IR window for clouds and surface skin temp." },
  { channel: "C15", number: 15, name: "Dirty Longwave Window", wavelength_um: 12.30, spectrum: "Thermal IR", physical_unit: "°C", description: "Low-level moisture estimation and airborne dust." },
  { channel: "C16", number: 16, name: "CO2 Longwave IR", wavelength_um: 13.30, spectrum: "Thermal IR", physical_unit: "°C", description: "Cloud top height estimation and atmospheric temperature." }
];

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error('API offline');
  return res.json();
}

export async function fetchBounds() {
  const res = await fetch(`${API_BASE}/metadata/bounds`);
  if (!res.ok) throw new Error('Failed to load map bounds');
  return res.json();
}

export async function fetchChannels() {
  const res = await fetch(`${API_BASE}/channels`);
  if (!res.ok) throw new Error('Failed to load channels');
  return res.json();
}

export async function fetchFrames(channel, limit = 24) {
  const res = await fetch(`${API_BASE}/frames?channel=${channel}&limit=${limit}`);
  if (!res.ok) throw new Error(`Failed to load frames for ${channel}`);
  return res.json();
}

export async function fetchLatest() {
  const res = await fetch(`${API_BASE}/latest`);
  if (!res.ok) throw new Error('Failed to load latest imagery');
  return res.json();
}

export async function fetchLegend(channel) {
  const res = await fetch(`${API_BASE}/legends/${channel}`);
  if (!res.ok) throw new Error(`Failed to load legend for ${channel}`);
  return res.json();
}
