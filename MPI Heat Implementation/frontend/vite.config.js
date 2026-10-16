import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api goes to scripts/demo_server.py, which runs the real programs for the Live demo tab
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
