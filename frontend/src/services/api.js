/**
 * Axios instance for IRIS AI backend.
 * VITE_API_URL can be set in .env.local to override the default.
 * Falls back to the direct backend address — required for Electron renderer
 * which does not go through Vite's dev proxy.
 */
import axios from "axios";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000",
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

export default api;
