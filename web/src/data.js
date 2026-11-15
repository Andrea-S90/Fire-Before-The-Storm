// Single entry point to the data contract (docs/DATA_CONTRACT.md). Components never fetch on their own.
export const dataUrl = (name) => `${import.meta.env.BASE_URL}data/${name}`

const getJson = async (name) => {
  const r = await fetch(dataUrl(name))
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`)
  return r.json()
}

// TEMPORARY, remove once a fresh export is committed. Exports made before pipeline commit 794f4f2 passed the
// Web Mercator bounds to the lon/lat conversion with x and y swapped. The swap is exact, so it can be undone:
// the stored "lon" is really a Mercator y read as an angle, and the stored "lat" is a Mercator x.
const D = 180 / Math.PI
function unswapCorners(corners) {
  const pts = corners.map(([a, b]) => [Math.asinh(Math.tan(b / D)) * D, Math.atan(Math.sinh(a / D)) * D])
  const lons = pts.map((p) => p[0]), lats = pts.map((p) => p[1])
  const [w, e, s, n] = [Math.min(...lons), Math.max(...lons), Math.min(...lats), Math.max(...lats)]
  return [[w, n], [e, n], [e, s], [w, s]]
}

// Small files only. The big vectors (streams, catchments...) are loaded by the map straight from their URL.
export async function loadData() {
  const [meta, layers, towns, hindcast, windRose] = await Promise.all(
    ['meta.json', 'layers.json', 'towns.json', 'hindcast.json', 'wind_rose.json'].map(getJson))
  const [w, s, e, n] = meta.aoi_bbox
  const inAoi = ([lon, lat]) => lon > w - 0.25 && lon < e + 0.25 && lat > s - 0.25 && lat < n + 0.25
  const warnings = []
  const goodLayers = layers.flatMap((l) => {
    if (l.coordinates.every(inAoi)) return [l]
    const fixed = unswapCorners(l.coordinates)
    if (fixed.every(inAoi)) {
      warnings.push(`overlay "${l.id}": corners repaired in the browser (export predates the step 12 fix)`)
      return [{ ...l, coordinates: fixed }]
    }
    warnings.push(`overlay "${l.id}" has corners outside the AOI and is hidden`)
    return []
  })
  return {
    meta, layers: goodLayers, towns, windRose, warnings,
    hindcast: { ...hindcast, byId: Object.fromEntries(hindcast.towns.map((t) => [t.id, t])) },
  }
}

export const LEVEL_COLOR = { high: '#b2182b', medium: '#ef8a62', low: '#4d9ac4', unknown: '#9a9a9a', none: '#9a9a9a' }
export const fmt = (v, digits = 0) =>
  v == null || !Number.isFinite(v) ? 'n/a' : v.toLocaleString('en-GB', { maximumFractionDigits: digits })
