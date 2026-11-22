import { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'
import { dataUrl, LEVEL_COLOR, fmt } from '../data.js'
import { isNarrow } from '../useNarrow.js'
// Reference outlines, not pipeline data: the municipalities the news reports name (OpenStreetMap, ODbL).
import municipalitiesUrl from '../assets/municipalities.geojson?url'

const STREAM_WIDTH = ['interpolate', ['linear'], ['coalesce', ['get', 'area_km2'], 0], 0, 0.4, 5, 1.2, 100, 3]
// Streams have two looks. Normally: debris-flow likelihood at 24 mm/h (segments outside the model's size range
// have no value). With the rain dial: red where the trigger is at or below the chosen intensity, grey otherwise;
// those red segments are small headwater channels, so they are drawn thicker and on top (line-sort-key).
// The switch is a feature state per segment, never a new expression: changing a data-driven expression makes
// MapLibre re-tile the whole source, which takes seconds and made the dial lag.
const PASSED = ['boolean', ['feature-state', 'passed'], false]
const STREAM_COLOR = ['case', PASSED, '#b2182b',
  ['boolean', ['feature-state', 'dial'], false], '#9fb8c8',
  ['interpolate', ['linear'], ['coalesce', ['get', 'p24'], 0], 0, '#4d9ac4', 0.4, '#fdae61', 0.7, '#b2182b']]

const BASEMAP = 'https://tiles.openfreemap.org/styles/positron'
const levelColor = ['match', ['get', 'overall'], 'high', LEVEL_COLOR.high, 'medium', LEVEL_COLOR.medium,
  'low', LEVEL_COLOR.low, LEVEL_COLOR.unknown]

// vector group (used in chapters.js) -> the map layers it owns
const VECTORS = {
  burned: ['burned-line'],
  streams: ['streams-line'],
  catchments: ['catchment-fill', 'catchment-line'],
  water: ['water-circle'],
  towns: ['towns-circle', 'towns-label'],
  reported: ['reported-fill', 'reported-line'],
}

export const REPORTED = '#f2b705'

function addLayers(map, layers) {
  for (const l of layers) {
    map.addSource(`ov-${l.id}`, { type: 'image', url: dataUrl(l.url), coordinates: l.coordinates })
    map.addLayer({ id: `ov-${l.id}`, type: 'raster', source: `ov-${l.id}`,
      paint: { 'raster-opacity': 0, 'raster-opacity-transition': { duration: 600 }, 'raster-fade-duration': 0 } })
  }
  const src = (id, file, extra) => map.addSource(id, { type: 'geojson', data: dataUrl(file), ...extra })
  src('burned', 'burned_area.geojson')
  src('streams', 'streams.geojson', { promoteId: 'id' })   // ids for the rain dial's feature state
  src('catchments', 'catchments.geojson')
  src('water', 'water_points.geojson')
  src('towns', 'towns.geojson')
  map.addSource('reported', { type: 'geojson', data: municipalitiesUrl })
  map.addLayer({ id: 'reported-fill', type: 'fill', source: 'reported',
    paint: { 'fill-color': REPORTED, 'fill-opacity': 0.3 } })
  map.addLayer({ id: 'reported-line', type: 'line', source: 'reported',
    paint: { 'line-color': '#1c1917', 'line-width': 1.6 } })
  map.addLayer({ id: 'catchment-fill', type: 'fill', source: 'catchments',
    paint: { 'fill-color': '#1d4e89', 'fill-opacity': 0.18 } })
  map.addLayer({ id: 'catchment-line', type: 'line', source: 'catchments',
    paint: { 'line-color': '#1d4e89', 'line-width': 1.5 } })
  map.addLayer({ id: 'streams-line', type: 'line', source: 'streams',
    // lowest trigger drawn last, so the segments the rain dial turns red are always on top
    layout: { 'line-sort-key': ['-', 1000, ['coalesce', ['get', 'trigger_mmh'], 1000]] },
    paint: {
      'line-color': STREAM_COLOR,
      'line-width': ['case', PASSED, 2.6, STREAM_WIDTH],
    } })
  map.addLayer({ id: 'burned-line', type: 'line', source: 'burned',
    paint: { 'line-color': '#3b2a20', 'line-width': 1.2, 'line-dasharray': [2, 1.5] } })
  map.addLayer({ id: 'water-circle', type: 'circle', source: 'water',
    paint: { 'circle-radius': 3.5, 'circle-stroke-width': 0.8, 'circle-stroke-color': '#fff',
      'circle-color': ['interpolate', ['linear'], ['coalesce', ['get', 'score'], 0],
        0, '#9ecae1', 0.25, '#fdae61', 0.5, '#b2182b'] } })
  map.addLayer({ id: 'towns-circle', type: 'circle', source: 'towns',
    paint: { 'circle-radius': 6, 'circle-color': levelColor, 'circle-stroke-width': 1.5, 'circle-stroke-color': '#fff' } })
  // every dot gets its name; where names collide, the riskier town keeps its label
  map.addLayer({ id: 'towns-label', type: 'symbol', source: 'towns',
    layout: { 'text-field': ['get', 'name'], 'text-size': 11, 'text-offset': [0, 0.9], 'text-anchor': 'top',
      'text-font': ['Noto Sans Regular'], 'text-padding': 1,
      'symbol-sort-key': ['match', ['get', 'overall'], 'high', 0, 'medium', 1, 2] },
    paint: { 'text-halo-color': '#fff', 'text-halo-width': 1.4, 'text-color': '#222' } })
}

function applyRain(map, streams, rain) {
  for (const [id, trigger] of streams) {
    map.setFeatureState({ source: 'streams', id }, { dial: rain != null, passed: rain != null && trigger <= rain })
  }
}

function applyChapter(map, layers, chapter, selectedId) {
  for (const l of layers) {
    map.setPaintProperty(`ov-${l.id}`, 'raster-opacity', chapter.overlays.includes(l.id) ? 0.85 : 0)
  }
  for (const [group, ids] of Object.entries(VECTORS)) {
    for (const id of ids) {
      map.setLayoutProperty(id, 'visibility', chapter.vectors.includes(group) ? 'visible' : 'none')
    }
  }
  // only the selected town's catchment, so the map stays readable
  map.setFilter('catchment-fill', ['==', ['get', 'id'], selectedId])
  map.setFilter('catchment-line', ['==', ['get', 'id'], selectedId])
  const sel = ['==', ['get', 'id'], selectedId]
  map.setPaintProperty('towns-circle', 'circle-radius', ['case', sel, 10, 6])
  map.setPaintProperty('towns-circle', 'circle-stroke-color', ['case', sel, '#1c1917', '#fff'])
  map.setPaintProperty('towns-circle', 'circle-stroke-width', ['case', sel, 2.5, 1.5])
  map.setLayoutProperty('towns-label', 'text-size', ['case', sel, 13, 11])
}

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])
const PATH_LABEL = { runoff: 'Surface runoff', debris_flow: 'Debris flow', groundwater: 'Groundwater', airborne: 'Airborne ash' }
// The data behind a dot's colour: overall level, the four pathways (overall = worse of runoff and debris flow), ash
function popupHtml(t) {
  const dot = (level) => `<i class="pp-dot" style="background:${LEVEL_COLOR[level] ?? LEVEL_COLOR.unknown}"></i>`
  const rows = Object.entries(PATH_LABEL).map(([k, label]) => {
    const p = t.pathways[k]
    const drives = (k === 'runoff' || k === 'debris_flow') && p.level === t.overall ? 'pp-drives' : ''
    return `<li class="${drives}">${dot(p.level)}<span>${label}</span><b>${esc(p.level)}</b><small>${esc(p.confidence)}</small></li>`
  }).join('')
  return `<div class="pp">
    <header><strong>${esc(t.name)}</strong><span class="pill" style="background:${LEVEL_COLOR[t.overall]}">${esc(t.overall)}</span></header>
    <p class="muted">${t.kind === 'reservoir' ? 'Reservoir' : `Population ${fmt(t.population)}`} · ${fmt(t.upstream_burned_pct, 1)}% burned upstream</p>
    <ul>${rows}</ul>
    <p class="pp-ash">Ash upstream <b>${fmt(t.ash_t.p50)} t</b> <small>(range ${fmt(t.ash_t.p10)} to ${fmt(t.ash_t.p90)})</small></p>
    <p class="muted pp-note">Bold: the pathway that sets the dot's colour (the worse of surface runoff and debris flow).</p>
  </div>`
}

// chapter cameras are framed for a full-screen desktop map; the phone map band is far smaller,
// so pull back one zoom level there to keep the same area in view
const fit = (view) => (isNarrow() ? { ...view, zoom: view.zoom - 1 } : view)

export default function MapView({ data, chapter, selectedId, onSelectTown, rain, onMap }) {
  const el = useRef(null)
  const mapRef = useRef(null)
  const ready = useRef(false)
  const popupRef = useRef(null)
  const streams = useRef([])   // [stream id, trigger mm/h or Infinity] for every segment
  const latest = useRef({ chapter, selectedId, rain })
  latest.current = { chapter, selectedId, rain }

  useEffect(() => {
    const map = new maplibregl.Map({
      container: el.current, style: BASEMAP, ...fit(chapter.view), attributionControl: { compact: true },
      // the wheel (and one finger on a phone) scrolls the story; Ctrl + wheel or two fingers zoom the map
      cooperativeGestures: true,
    })
    mapRef.current = map
    onMap?.(map)
    const popup = new maplibregl.Popup({ maxWidth: '280px', offset: 12, className: 'town-popup' })
    popupRef.current = popup
    if (import.meta.env.DEV) window.__map = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right')
    map.on('load', () => {
      addLayers(map, data.layers)
      ready.current = true
      applyChapter(map, data.layers, latest.current.chapter, latest.current.selectedId)
      map.getSource('streams').getData().then((fc) => {
        streams.current = fc.features.map((f) => [f.properties.id, f.properties.trigger_mmh ?? Infinity])
        applyRain(map, streams.current, latest.current.rain)
      })
    })
    map.on('click', 'towns-circle', (e) => {
      const f = e.features[0]
      const t = data.towns.find((x) => x.id === f.properties.id)
      onSelectTown(f.properties.id)
      if (t) popup.setLngLat(f.geometry.coordinates).setHTML(popupHtml(t)).addTo(map)
    })
    map.on('mouseenter', 'towns-circle', () => { map.getCanvas().style.cursor = 'pointer' })
    map.on('mouseleave', 'towns-circle', () => { map.getCanvas().style.cursor = '' })
    return () => { ready.current = false; map.remove() }
    // the map is created once; chapter changes are applied by the effects below
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map || !ready.current) return
    applyChapter(map, data.layers, chapter, selectedId)
  }, [chapter, selectedId, data.layers])

  useEffect(() => {
    const map = mapRef.current
    if (map && ready.current) applyRain(map, streams.current, rain)
  }, [rain])

  useEffect(() => {
    mapRef.current?.flyTo({ ...fit(chapter.view), duration: 1200 })
    if (!chapter.vectors.includes('towns')) popupRef.current?.remove()
  }, [chapter])

  // the town picker (towns chapter) moves an open popup to the newly selected town
  useEffect(() => {
    const popup = popupRef.current
    const t = data.towns.find((x) => x.id === selectedId)
    if (popup?.isOpen() && t) popup.setLngLat([t.lon, t.lat]).setHTML(popupHtml(t))
  }, [selectedId, data.towns])

  return <div ref={el} className="map" />
}
