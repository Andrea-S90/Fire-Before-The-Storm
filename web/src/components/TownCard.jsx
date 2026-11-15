import { LEVEL_COLOR, fmt } from '../data.js'

const PATHWAYS = [
  ['runoff', 'Surface runoff', () => null],
  ['debris_flow', 'Debris flow',
    (p) => p.trigger_mm_h_15min != null && `trigger ${fmt(p.trigger_mm_h_15min)} mm/h (15 min)`],
  ['groundwater', 'Groundwater',
    (p) => (p.points?.length ? `${p.points.length} wells or springs nearby` : 'no mapped wells or springs')],
  ['airborne', 'Airborne ash', () => null],
]

export default function TownCard({ town }) {
  return (
    <article className="card">
      <header>
        <h3>{town.name}</h3>
        <span className="pill" style={{ background: LEVEL_COLOR[town.overall] }}>{town.overall}</span>
      </header>
      <p className="muted">
        {town.kind === 'reservoir' ? 'Reservoir' : `Population ${fmt(town.population)}`}
        {' · '}catchment {fmt(town.catchment_km2, 1)} km²
        {' · '}{fmt(town.upstream_burned_pct, 1)}% burned upstream
      </p>
      <ul className="pathways">
        {PATHWAYS.map(([key, label, detail]) => {
          const p = town.pathways[key]
          return (
            <li key={key}>
              <span className="dot" style={{ background: LEVEL_COLOR[p.level] }} />
              <strong>{label}</strong> <span>{p.level}</span>
              <small>{[detail(p), `confidence: ${p.confidence}`].filter(Boolean).join(' · ')}</small>
            </li>
          )
        })}
      </ul>
      <p className="muted">
        Ash upstream: {fmt(town.ash_t.p50)} t (range {fmt(town.ash_t.p10)} to {fmt(town.ash_t.p90)})
      </p>
      <p className="muted">First lab checks: {town.tests.join(', ')}</p>
    </article>
  )
}
