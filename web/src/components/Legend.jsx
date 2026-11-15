import { LEVEL_COLOR, fmt } from '../data.js'

// CSS gradients for the matplotlib colour maps that pipeline step 12 uses (low value first).
const CMAPS = {
  gray: ['#000000', '#ffffff'],
  RdBu: ['#67001f', '#b2182b', '#d6604d', '#f4a582', '#fddbc7', '#f7f7f7', '#d1e5f0', '#92c5de', '#4393c3', '#2166ac', '#053061'],
  Greens: ['#f7fcf5', '#c7e9c0', '#74c476', '#238b45', '#00441b'],
  YlOrBr: ['#ffffe5', '#fee391', '#fe9929', '#cc4c02', '#662506'],
  Oranges: ['#fff5eb', '#fdd0a2', '#fd8d3c', '#d94801', '#7f2704'],
  Blues: ['#f7fbff', '#c6dbef', '#6baed6', '#2171b5', '#08306b'],
  Purples: ['#fcfbfd', '#dadaeb', '#9e9ac8', '#6a51a3', '#3f007d'],
}
const gradient = (stops) => `linear-gradient(to right, ${stops.join(', ')})`
// step 12 writes class colours as "rgba(r, g, b, a)" with a from 0 to 255; keep the rgb part
const rgb = (s) => `rgb(${s.match(/\d+/g).slice(0, 3).join(', ')})`

// What each raster means in plain words (the title comes from layers.json).
const RASTER_NOTE = {
  dhv: 'Red: the radar echo from branches and trunks fell (canopy lost). Blue: it rose.',
  hv_pre: 'Brighter means more woody vegetation.',
  hv_post: 'Brighter means more woody vegetation.',
  ash: 'Estimated ash left on the ground.',
  biomass: 'Wood above ground before the fire, estimated from radar.',
  erosion: 'Where rain is most likely to move soil. Relative scale.',
  gw_vuln: 'How easily surface water reaches groundwater. Screening only.',
  wind_exposure: 'Downwind of the fire while it burned. Indicative only.',
}

const Ramp = ({ title, stops, min, max, units, note }) => (
  <li>
    <span className="lg-title">{title}</span>
    <span className="lg-ramp" style={{ background: gradient(stops) }} />
    <span className="lg-ends"><span>{min}</span><span>{units}</span><span>{max}</span></span>
    {note && <small>{note}</small>}
  </li>
)

const Swatches = ({ title, items, shape = 'box', note }) => (
  <li>
    <span className="lg-title">{title}</span>
    <span className="lg-swatches">
      {items.map(([label, color]) => (
        <span key={label}><i className={`lg-${shape}`} style={{ '--c': color }} />{label}</span>
      ))}
    </span>
    {note && <small>{note}</small>}
  </li>
)

// Colours below must match the paint rules in MapView.jsx.
function vectorLegend(group, chapter, rain) {
  switch (group) {
    case 'towns':
      return <Swatches key={group} title="Dots: towns and reservoirs, by overall risk" shape="dot"
        items={['high', 'medium', 'low'].map((l) => [l, LEVEL_COLOR[l]])}
        note="The overall level is the worse of surface runoff and debris flow." />
    case 'burned':
      return <Swatches key={group} title="Dashed line: edge of the burned area" shape="dash" items={[['burn outline', '#3b2a20']]} />
    case 'streams':
      return chapter.panel === 'rain'
        ? <Swatches key={group} title={`Lines: streams at ${rain} mm/h`} shape="line"
          items={[['trigger passed', '#b2182b'], ['below trigger, or outside the model', '#9fb8c8']]} />
        : <Ramp key={group} title="Lines: streams, by debris-flow likelihood in a 24 mm/h storm"
          stops={['#4d9ac4', '#fdae61', '#b2182b']} min="0%" max="70% or more" units=""
          note="Thicker lines drain more land. Large rivers are outside the model and stay blue." />
    case 'water':
      return <Ramp key={group} title="Small dots: wells, springs and water works"
        stops={['#9ecae1', '#fdae61', '#b2182b']} min="test later" max="test first" units=""
        note="Groundwater screening score: how exposed the point is and how much burned upslope." />
    case 'catchments':
      return <Swatches key={group} title="Blue area: land that drains through the selected town" shape="box"
        items={[['catchment', 'rgba(29, 78, 137, 0.35)']]} />
    default:
      return null
  }
}

export default function Legend({ chapter, layers, rain }) {
  const rasters = chapter.overlays.map((id) => layers.find((l) => l.id === id)).filter(Boolean)
  if (rasters.length === 0 && chapter.vectors.length === 0) return null
  return (
    <ul className="card legend" aria-label="Map legend">
      {rasters.map((l) => (l.legend.classes
        ? <Swatches key={l.id} title={`Colours: ${l.title.toLowerCase()}`}
          items={l.legend.classes.map((c, i) => [c, rgb(l.legend.colors[i])]).filter(([c]) => c !== 'unburned')} />
        : <Ramp key={l.id} title={`Colours: ${l.title}`} stops={CMAPS[l.legend.cmap] ?? CMAPS.gray}
          min={fmt(l.legend.min, 1)} max={fmt(l.legend.max, 1)} units={l.units} note={RASTER_NOTE[l.id]} />))}
      {chapter.vectors.map((g) => vectorLegend(g, chapter, rain))}
    </ul>
  )
}
