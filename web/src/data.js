// Single entry point to the data contract (docs/DATA_CONTRACT.md). Components never fetch on their own.
export const dataUrl = (name) => `${import.meta.env.BASE_URL}data/${name}`

const getJson = async (name) => {
  const r = await fetch(dataUrl(name))
  if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`)
  return r.json()
}

// Small files only. The big vectors (streams, catchments...) are loaded by the map straight from their URL.
export async function loadData() {
  const [meta, layers, towns, hindcast, windRose] = await Promise.all(
    ['meta.json', 'layers.json', 'towns.json', 'hindcast.json', 'wind_rose.json'].map(getJson))
  const [w, s, e, n] = meta.aoi_bbox
  const inAoi = ([lon, lat]) => lon > w - 0.25 && lon < e + 0.25 && lat > s - 0.25 && lat < n + 0.25
  const warnings = []
  const goodLayers = layers.filter((l) => {
    const ok = l.coordinates.every(inAoi)
    if (!ok) warnings.push(`overlay "${l.id}" has corners outside the AOI and is hidden (stale export?)`)
    return ok
  })
  return {
    meta, layers: goodLayers, towns, windRose, warnings,
    hindcast: { ...hindcast, byId: Object.fromEntries(hindcast.towns.map((t) => [t.id, t])) },
  }
}

export const LEVEL_COLOR = { high: '#b2182b', medium: '#ef8a62', low: '#4d9ac4', unknown: '#9a9a9a', none: '#9a9a9a' }
export const fmt = (v, digits = 0) =>
  v == null || !Number.isFinite(v) ? 'n/a' : v.toLocaleString('en-GB', { maximumFractionDigits: digits })
