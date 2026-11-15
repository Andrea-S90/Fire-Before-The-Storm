import { fmt } from '../data.js'

// Half-hourly satellite rain for one town against its debris-flow trigger.
export default function Hindcast({ town, record, note }) {
  if (!record) return <p className="muted">No hindcast for {town.name}.</p>
  const W = 320, H = 120, pad = 22
  const s = record.series
  const top = Math.max(record.trigger_mm_h ?? 0, record.peak_30min_mm_h ?? 0, 1) * 1.15
  const x = (i) => pad + (i / (s.length - 1)) * (W - pad - 4)
  const y = (v) => H - 16 - (v / top) * (H - 26)
  const days = s.map((p, i) => [p.t, i]).filter(([t]) => t.endsWith('T00:00:00'))
  return (
    <figure className="card">
      <figcaption>
        <strong>{town.name}</strong>: rain peaked at {fmt(record.peak_30min_mm_h, 1)} mm/h,
        trigger {fmt(record.trigger_mm_h, 1)} mm/h.{' '}
        {record.exceeded
          ? `Exceeded on ${record.first_exceedance.replace('T', ' ').slice(0, 16)}.`
          : 'Not exceeded in satellite rain.'}
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Rain at ${town.name}, 1 to 8 October`}>
        {s.map((p, i) => p.mm_h > 0 && (
          <line key={p.t} x1={x(i)} x2={x(i)} y1={y(0)} y2={y(p.mm_h)} stroke="#2b6ca3" strokeWidth="1.2" />
        ))}
        <line x1={pad} x2={W - 4} y1={y(0)} y2={y(0)} stroke="#888" strokeWidth="0.6" />
        {record.trigger_mm_h != null && (
          <>
            <line x1={pad} x2={W - 4} y1={y(record.trigger_mm_h)} y2={y(record.trigger_mm_h)}
              stroke="#b2182b" strokeDasharray="4 3" />
            <text x={W - 6} y={y(record.trigger_mm_h) - 3} textAnchor="end" fontSize="9" fill="#b2182b">trigger</text>
          </>
        )}
        {days.map(([t, i]) => (
          <text key={t} x={x(i)} y={H - 4} fontSize="8" fill="#555">{t.slice(8, 10)} Oct</text>
        ))}
        <text x={2} y={10} fontSize="8" fill="#555">mm/h</text>
      </svg>
      <p className="muted">{note}</p>
    </figure>
  )
}
