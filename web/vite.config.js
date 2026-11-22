import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The dev and preview servers send .usdz with no Content-Type, and iPhone AR Quick Look then refuses the model.
// GitHub Pages already serves the right type; this only fixes local testing from a phone (npm run dev -- --host).
const usdzType = (server) => {
  server.middlewares.use((req, res, next) => {
    if (req.url?.split('?')[0].endsWith('.usdz')) res.setHeader('Content-Type', 'model/vnd.usdz+zip')
    next()
  })
}

// Relative base: the same build works on GitHub Pages (/Fire-Before-The-Storm/), Vercel (/) and `vite preview`.
export default defineConfig({
  base: './',
  plugins: [react(), { name: 'usdz-content-type', configureServer: usdzType, configurePreviewServer: usdzType }],
  server: { port: 5173 },
})
