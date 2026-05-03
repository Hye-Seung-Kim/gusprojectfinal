const explicitApiUrl = import.meta.env.VITE_API_BASE_URL;

export const BACKEND_URL =
  explicitApiUrl || `${window.location.protocol}//${window.location.hostname}:8000`;

export const storedToken = () => localStorage.getItem("gus-control-token") || "";

export const authHeaders = (token) => {
  if (!token) {
    return {};
  }

  return { "X-Control-Token": token };
};

export const withToken = (url, token) => {
  if (!token) {
    return url;
  }

  const separator = url.includes("?") ? "&" : "?";
  return `${url}${separator}token=${encodeURIComponent(token)}`;
};
