import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The backend runs on 127.0.0.1:8000 with CORS allow_origins=["*"],
// so the frontend calls it directly — no proxy needed.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
  },
})
