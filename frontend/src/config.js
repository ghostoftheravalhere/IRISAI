/**
 * Canonical Frontend Configuration Source
 * Defines explicit API & WebSocket endpoints for development & production desktop runtimes.
 */

export const config = {
  API_BASE_URL: "http://127.0.0.1:8000",
  WS_BASE_URL: "ws://127.0.0.1:8000/ws/events",
  DEV_SERVER_URL: "http://127.0.0.1:5173",
  APP_TITLE: "IRIS AI — Unified Desktop Assistant",
  VERSION: "4.0.0",
};

export default config;
