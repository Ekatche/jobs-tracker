export const getApiBaseUrl = (): string => {
  if (typeof window === "undefined") {
    return process.env.INTERNAL_API_URL || "http://backend:8000";
  }
  // En cas d'override explicite en variable d'environnement :
  if (process.env.NEXT_PUBLIC_API_URL && process.env.NEXT_PUBLIC_API_URL.trim() !== "") {
    const customUrl = process.env.NEXT_PUBLIC_API_URL.trim().replace(/\/+$/, "");
    if (!customUrl.includes(":8000") && !customUrl.endsWith("/api")) {
      return `${customUrl}/api`;
    }
    return customUrl;
  }
  // En production navigateur (derrière reverse-proxy Caddy sur VPS/domaine) :
  if (window.location.hostname !== "localhost" && window.location.hostname !== "127.0.0.1") {
    return `${window.location.origin}/api`;
  }
  return "http://localhost:8000";
};
