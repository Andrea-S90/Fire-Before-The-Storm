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
// 3D terrain: AWS Terrain Tiles (Terrarium encoding, built from SRTM and other open DEMs), free and keyless.
// A display aid only; the pipeline's own flow routing uses Copernicus GLO-30.
const DEM = {
  type: 'raster-dem', encoding: 'terrarium', tileSize: 256, maxzoom: 14,
  tiles: ['https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'],
  attribution: '<a href="https://registry.opendata.aws/terrain-tiles/">Terrain Tiles</a> (Mapzen, AWS)',
}
// Vertical exaggeration, not to scale: 2.5x makes the valleys and burned slopes stand out at the story's zoom.
const EXAGGERATION = 2.5
// Elevation tiles are only fetched this many degrees around the study area (the overlays' extent): enough for a
// tilted, rotating camera, without loading the whole horizon.
const DEM_PAD = 0.6
// Satellite basemap: EOX Sentinel-2 cloudless, the 2016 mosaic (CC BY 4.0; later years are CC BY-NC-SA). It is
// years older than the fire, so the map says so whenever it is on. 10 m pixels: no sharper tiles past zoom 14,
// and like the DEM it is only fetched around the study area, wider so the tilted views rarely reach its edge.
const SATELLITE = {
  type: 'raster', tileSize: 256, maxzoom: 14,
  tiles: ['https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg'],
  attribution: '<a href="https://s2maps.eu">Sentinel-2 cloudless</a> by EOX (modified Copernicus Sentinel data 2016, ' +
    '<a href="https://creativecommons.org/licenses/by/4.0/">CC BY 4.0</a>)',
}
const SAT_PAD = 2.5
const SAT_NOTE = 'Satellite basemap, before the fire (Sentinel-2, 2016)'
const SAT_KEY = 'ashwatch-basemap'
function savedSatellite() {
  try { return sessionStorage.getItem(SAT_KEY) === 'satellite' } catch { return false }
}
function saveSatellite(on) {
  try { sessionStorage.setItem(SAT_KEY, on ? 'satellite' : 'map') } catch { /* private mode: not remembered */ }
}
// Auto-rotation while the story scrolls, until the visitor touches the map: one full turn in about 3 minutes.
const SPIN_DEG_PER_S = 2
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

function demBounds(layers, pad = DEM_PAD) {
  const pts = layers.flatMap((l) => l.coordinates)
  if (!pts.length) return undefined
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1])
  return [Math.min(...xs) - pad, Math.min(...ys) - pad, Math.max(...xs) + pad, Math.max(...ys) + pad]
}

function addLayers(map, layers) {
  // two sources from the same tiles: MapLibre recommends not sharing one between terrain and hillshade.
  // The hillshade reads them as 512 px tiles, i.e. one zoom level coarser: a quarter of the downloads (it was
  // most of the 3D weight), and still sharp enough at the story's zoom levels.
  const bounds = demBounds(layers)
  map.addSource('dem', { ...DEM, bounds })
  map.addSource('dem-shade', { ...DEM, tileSize: 512, bounds })
  // the imagery sits above Positron's land and roads but below its place names, the hillshade and our layers
  map.addSource('satellite', { ...SATELLITE, bounds: demBounds(layers, SAT_PAD) })
  map.addLayer({ id: 'satellite', type: 'raster', source: 'satellite', layout: { visibility: 'none' },
    // a little paler, so the red and orange of our layers stand out from the brown hills
    paint: { 'raster-fade-duration': 150, 'raster-saturation': -0.35 } }, map.getStyle().layers.find((l) => l.type === 'symbol')?.id)
  map.addLayer({ id: 'hillshade', type: 'hillshade', source: 'dem-shade',
    layout: { visibility: 'none' },
    paint: { 'hillshade-exaggeration': 0.35, 'hillshade-shadow-color': '#5b5048' } })
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

// Phone: the section card is parked at the top of the screen (App.jsx, goTo), so centre the map in the
// open part below it: pad the camera by the timeline plus the card, capped so a card with 'More' open
// still leaves the map some room, and by the pager at the bottom.
function phonePadding() {
  const step = document.querySelector('.step.active')
  const title = step?.querySelector('h2')
  const timeline = document.querySelector('.timeline')?.offsetHeight ?? 0
  const card = step && title ? step.getBoundingClientRect().bottom - title.getBoundingClientRect().top : 0
  return { top: Math.round(Math.min(timeline + 12 + card, window.innerHeight * 0.6)), bottom: 60, left: 0, right: 0 }
}

// Laptop: the story column covers the left of the map, so centre the map in the open part to its right
// (the active card's right edge, wide cards included, capped at half the screen) and below the timeline.
function desktopPadding() {
  const step = document.querySelector('.step.active')
  const right = step ? step.getBoundingClientRect().right : document.querySelector('.story')?.getBoundingClientRect().right ?? 0
  const timeline = document.querySelector('.timeline')?.offsetHeight ?? 0
  return { top: timeline, bottom: 0, left: Math.round(Math.min(Math.max(right, 0), window.innerWidth * 0.5)), right: 0 }
}

// the chapter cameras were framed for the full width, so zoom out by the share the story column covers
// (about half a level on a laptop) to keep the same area in view
function desktopFit(v) {
  const padding = desktopPadding()
  const open = Math.max(window.innerWidth - padding.left, 1) / window.innerWidth
  return { ...v, zoom: v.zoom + Math.log2(open), padding }
}

// chapter cameras are framed for a full-screen desktop map; the open map area on a phone is far smaller,
// so pull back one zoom level there to keep the same area in view
const fit = (view, is3d, spinning) => {
  const v = { pitch: 0, bearing: 0, ...view }
  if (!is3d) { v.pitch = 0; v.bearing = 0 }
  if (spinning) delete v.bearing   // keep turning from where the camera is, no snap back to north
  return isNarrow()
    ? { ...v, zoom: v.zoom - 1, padding: phonePadding() }
    : desktopFit(v)
}

function applyTerrain(map, is3d) {
  map.setTerrain(is3d ? { source: 'dem', exaggeration: EXAGGERATION } : null)
  map.setLayoutProperty('hillshade', 'visibility', is3d ? 'visible' : 'none')
}

function applyBasemap(map, sat) {
  map.setLayoutProperty('satellite', 'visibility', sat ? 'visible' : 'none')
  // the dark dashed burn outline vanishes on the imagery: white there
  map.setPaintProperty('burned-line', 'line-color', sat ? '#fff' : '#3b2a20')
  map.setPaintProperty('burned-line', 'line-width', sat ? 1.1 : 1.2)
  map.setPaintProperty('burned-line', 'line-opacity', sat ? 0.8 : 1)
  // the rain dial's red segments are thin headwater channels that sink into the brown hills: thicker there
  map.setPaintProperty('streams-line', 'line-width', ['case', PASSED, sat ? 3.6 : 2.6, STREAM_WIDTH])
}

// The note next to the buttons while the satellite basemap is on, so nobody reads the imagery as the burn scar
class NoteControl {
  onAdd() {
    this.el = document.createElement('div')
    this.el.className = 'maplibregl-ctrl map-note'
    this.el.textContent = SAT_NOTE
    return this.el
  }
  show(on) { this.el.hidden = !on }
  onRemove() { this.el.remove() }
}

// A one-button control in the map's stack (bottom right): the 2D / 3D switch and the rotation on/off.
// look(on) gives the button's text, tooltip and whether it is usable.
class ButtonControl {
  constructor(className, look, get, set) { Object.assign(this, { className, look, get, set }) }
  onAdd() {
    this.el = document.createElement('div')
    this.el.className = 'maplibregl-ctrl maplibregl-ctrl-group'
    this.btn = document.createElement('button')
    this.btn.type = 'button'
    this.btn.className = this.className
    this.btn.addEventListener('click', () => this.set(!this.get()))
    this.el.appendChild(this.btn)
    this.update()
    return this.el
  }
  update() {
    const on = this.get()
    const { text, title, disabled = false, pressed } = this.look(on)
    this.btn.textContent = text
    this.btn.title = title
    this.btn.disabled = disabled
    this.btn.setAttribute('aria-label', title)
    if (pressed != null) this.btn.setAttribute('aria-pressed', String(pressed))
  }
  onRemove() { this.el.remove() }
}

export default function MapView({ data, chapter, selectedId, onSelectTown, rain, onMap }) {
  const el = useRef(null)
  const mapRef = useRef(null)
  const ready = useRef(false)
  const popupRef = useRef(null)
  const streams = useRef([])   // [stream id, trigger mm/h or Infinity] for every segment
  const is3d = useRef(true)
  // turns the camera slowly from the start, on every device, until the visitor drags, zooms, rotates, tilts or
  // clicks the map; the rotate button (bottom right) stops and restarts it
  const spin = useRef(true)
  const sat = useRef(savedSatellite())   // satellite basemap on, remembered for the visit
  const latest = useRef({ chapter, selectedId, rain })
  latest.current = { chapter, selectedId, rain }

  useEffect(() => {
    const map = new maplibregl.Map({
      container: el.current, style: BASEMAP, ...fit(chapter.view, is3d.current, false), attributionControl: { compact: true },
      // the wheel (and one finger on a phone) scrolls the story; Ctrl + wheel or two fingers zoom the map
      cooperativeGestures: true,
    })
    mapRef.current = map
    onMap?.(map)
    const popup = new maplibregl.Popup({ maxWidth: '280px', offset: 12, className: 'town-popup' })
    popupRef.current = popup
    if (import.meta.env.DEV) window.__map = map
    map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), 'bottom-right')
    // rotation on/off; any other touch of the map turns it off too, and this button turns it back on
    const spinCtrl = new ButtonControl('map-toggle spin-toggle',
      (on) => (is3d.current
        ? { text: '⟳', title: on ? 'Stop rotating the map' : 'Rotate the map', pressed: on }
        : { text: '⟳', title: 'Rotation needs the 3D view', pressed: false, disabled: true }),
      () => spin.current, (on) => setSpin(on))
    const setSpin = (on) => {
      if (spin.current === on) return
      spin.current = on
      spinCtrl.update()
    }
    const terrainCtrl = new ButtonControl('map-toggle',
      (on) => ({ text: on ? '2D' : '3D', title: on ? 'Flat map' : 'Show terrain in 3D' }),
      () => is3d.current, (on) => {
        is3d.current = on
        terrainCtrl.update()
        setSpin(false)   // the 2D/3D button counts as touching the map
        spinCtrl.update()
        if (!ready.current) return
        applyTerrain(map, on)
        map.easeTo({ ...fit(latest.current.chapter.view, on, false), duration: 800 })
      })
    const satNote = new NoteControl()
    const satCtrl = new ButtonControl('map-toggle',
      (on) => ({ text: on ? 'Map' : 'Sat', title: on ? 'Back to the plain map' : 'Show satellite imagery (Sentinel-2, 2016: before the fire)', pressed: on }),
      () => sat.current, (on) => {
        sat.current = on
        saveSatellite(on)
        satCtrl.update()
        satNote.show(on)
        if (ready.current) applyBasemap(map, on)
      })
    map.addControl(terrainCtrl, 'bottom-right')
    map.addControl(spinCtrl, 'bottom-right')
    map.addControl(satCtrl, 'bottom-right')
    map.addControl(satNote, 'bottom-right')
    satNote.show(sat.current)
    map.on('load', () => {
      // on a phone start with the map credits folded into the (i) button: open, they cover the cards
      if (isNarrow()) el.current.querySelector('.maplibregl-ctrl-attrib')?.classList.remove('maplibregl-compact-show')
      addLayers(map, data.layers)
      applyTerrain(map, is3d.current)
      applyBasemap(map, sat.current)
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
    // only gestures and buttons carry an originalEvent; the story's own flyTo does not
    const stopSpin = (e) => { if (e.originalEvent) setSpin(false) }
    for (const ev of ['dragstart', 'zoomstart', 'rotatestart', 'pitchstart']) map.on(ev, stopSpin)
    map.on('click', () => setSpin(false))
    let last = null, raf = 0
    const tick = (t) => {
      raf = requestAnimationFrame(tick)
      const dt = last == null ? 0 : Math.min(t - last, 100) / 1000
      last = t
      if (!spin.current || !is3d.current || !ready.current || map.isMoving()) return
      map.setBearing(map.getBearing() + SPIN_DEG_PER_S * dt)
    }
    raf = requestAnimationFrame(tick)
    map.on('mouseenter', 'towns-circle', () => { map.getCanvas().style.cursor = 'pointer' })
    map.on('mouseleave', 'towns-circle', () => { map.getCanvas().style.cursor = '' })
    return () => { ready.current = false; cancelAnimationFrame(raf); map.remove() }
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
    mapRef.current?.flyTo({ ...fit(chapter.view, is3d.current, spin.current), duration: 1200 })
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
