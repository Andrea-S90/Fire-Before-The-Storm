// Hours of wind from each direction during the fire. Ash travels the opposite way.
export default function WindRose({ rose }) {
  const R = 70, c = 85
  const max = Math.max(...rose.sectors.map((s) => s.hours), 1)
  const half = (Math.PI / rose.sectors.length) * 0.9
  const pt = (a, r) => [c + r * Math.sin(a), c - r * Math.cos(a)]
  return (
    <figure className="card">
      <figcaption>
        <strong>Wind during the fire</strong> ({rose.window[0]} to {rose.window[1]}): hours blowing from each
        direction. Indicative only.
      </figcaption>
      <svg viewBox="0 0 170 170" role="img" aria-label="Wind rose">
        {[0.5, 1].map((f) => <circle key={f} cx={c} cy={c} r={R * f} fill="none" stroke="#ccc" strokeWidth="0.6" />)}
        {rose.sectors.map((s) => {
          const a = (s.direction_from_deg * Math.PI) / 180
          const r = (R * s.hours) / max
          const [x1, y1] = pt(a - half, r)
          const [x2, y2] = pt(a + half, r)
          return (
            <path key={s.direction_from_deg} fill="#6a51a3" opacity="0.8"
              d={`M${c},${c} L${x1},${y1} A${r},${r} 0 0 1 ${x2},${y2} Z`} />
          )
        })}
        {[['N', 0], ['E', 90], ['S', 180], ['W', 270]].map(([l, d]) => {
          const [x, y] = pt((d * Math.PI) / 180, R + 9)
          return <text key={l} x={x} y={y + 3} textAnchor="middle" fontSize="9" fill="#555">{l}</text>
        })}
      </svg>
    </figure>
  )
}
