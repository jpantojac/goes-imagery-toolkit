/**
 * API client for interacting with the GOES REST API.
 */
const API_BASE = '/api/v1';

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
