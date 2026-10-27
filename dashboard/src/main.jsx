import React from 'react'
import ReactDOM from 'react-dom/client'
// Self-hosted fonts (bundled) replace the render-blocking Google Fonts @import —
// no external request, so the offline single-file export stays self-contained.
import '@fontsource-variable/inter'
import '@fontsource/jetbrains-mono'
import App from '@/App.jsx'
import { initTheme } from '@/lib/theme'
import '@/index.css'
import '@pr-federation/react/styles.css'
import 'maplibre-gl/dist/maplibre-gl.css'

// Stamp the shared federation.css signals. The per-repo accent is fixed; the
// theme (dark by default, light or system by preference) is applied before the
// first render so there is no flash of the wrong palette.
document.documentElement.dataset.repo = 'ovnis-pr'
initTheme()

ReactDOM.createRoot(document.getElementById('root')).render(
  <App />
)
