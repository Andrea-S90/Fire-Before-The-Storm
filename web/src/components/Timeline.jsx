const DAY = 86400000
const short = (iso) => new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' })

// Top bar: what happened when, when NISAR looked, and which period the map is showing now.
// Dates come from meta.json (the pipeline config); only the report date is fixed here.
export default function Timeline({ meta, passDates = [], chapter }) {
  const d = meta.dates
  const t0 = Date.parse(d.pre_start), t1 = Date.parse(d.series_end)
  const pct = (iso) => Math.min(100, Math.max(0, ((Date.parse(iso) - t0) / (t1 - t0)) * 100))
  const span = (a, b) => ({ left: `${pct(a)}%`, width: `${Math.max(pct(b) - pct(a), 0.6)}%` })

  const months = []
  const m = new Date(t0)
  m.setUTCDate(1)
  for (m.setUTCMonth(m.getUTCMonth() + 1); m.getTime() < t1; m.setUTCMonth(m.getUTCMonth() + 1)) {
    months.push([m.toISOString().slice(0, 10), m.toLocaleDateString('en-GB', { month: 'short', timeZone: 'UTC' })])
  }
  const firstRain = meta.wind?.first_rain_day
  const reported = '2026-10-07'   // date of the Reuters report on the contaminated water supply
  const periods = (chapter.time ?? []).map(([a, b]) => [d[a], d[b]]).filter(([a, b]) => a && b)

  return (
    <header className="timeline">
      <p className="tl-now">
        <strong>On the map:</strong> {chapter.timeLabel ?? 'all dates'}
        {periods.length > 0 && <> ({periods.map(([a, b]) => `${short(a)} to ${short(b)}`).join(' and ')})</>}
      </p>
      <div className="tl-track" role="img"
        aria-label={`Timeline from ${short(d.pre_start)} to ${short(d.series_end)} 2026`}>
        <span className="tl-axis" />
        {periods.map(([a, b]) => <span key={a} className="tl-period" style={span(a, b)} />)}
        <span className="tl-fire" style={span(d.fire_start, d.fire_end)} />
        <span className="tl-label tl-fire-label" style={{ left: `${pct(d.fire_start)}%` }}>
          Fire, {short(d.fire_start)} to {short(d.fire_end)}
        </span>
        {firstRain && (
          <>
            <span className="tl-mark tl-rain" style={{ left: `${pct(firstRain)}%` }} />
            <span className="tl-label tl-end" style={{ left: `${pct(firstRain)}%` }}>First rain, {short(firstRain)}</span>
          </>
        )}
        <span className="tl-mark tl-report" style={{ left: `${pct(reported)}%` }} />
        <span className="tl-label tl-report-label" style={{ left: `${pct(reported)}%` }}>Tap water unfit, reported {short(reported)}</span>
        {passDates.map((p) => (
          <span key={p} className="tl-pass" style={{ left: `${pct(p)}%` }} title={`NISAR pass, ${short(p)}`} />
        ))}
        {months.map(([iso, label]) => <span key={iso} className="tl-month" style={{ left: `${pct(iso)}%` }}>{label}</span>)}
      </div>
      <p className="tl-key">
        <i className="tl-k-pass" /> NISAR pass <i className="tl-k-period" /> period shown on the map
        {(t1 - t0) / DAY > 0 && <> · {short(d.pre_start)} to {short(d.series_end)} 2026</>}
      </p>
    </header>
  )
}
