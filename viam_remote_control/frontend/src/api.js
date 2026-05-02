const explicitApiUrl = import.meta.env.VITE_API_BASE_URL;

export const BACKEND_URL =
  explicitApiUrl || `${window.location.protocol}//${window.location.hostname}:8000`;
