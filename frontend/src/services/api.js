/**
 * API Service — axios instance pre-configured for IRIS AI backend
 * All modules import this instead of raw axios to keep base URL in one place.
 */
import axios from "axios";

const api = axios.create({
  baseURL: "/api",
  timeout: 10000,
  headers: { "Content-Type": "application/json" },
});

export default api;
