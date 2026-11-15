import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Relative base: the same build works on GitHub Pages (/Fire-Before-The-Storm/), Vercel (/) and `vite preview`.
export default defineConfig({
  base: './',
  plugins: [react()],
  server: { port: 5173 },
})
