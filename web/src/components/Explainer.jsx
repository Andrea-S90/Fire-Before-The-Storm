// Plain-language cards on how each satellite sees the fire. Schematic drawings, not agency images.
// kind: 'sentinel2' (optical burn ratio) | 'nisar' (L-band radar polarizations)
const H = '#2b6ca3'   // horizontal polarization
const V = '#6a51a3'   // vertical polarization
const NIR = '#1a9850'
const SWIR = '#d94801'

function Arrowheads({ id }) {
  return (
    <defs>
      {[['h', H], ['v', V], ['k', '#5b544c']].map(([k, c]) => (
        <marker key={k} id={`${id}-${k}`} viewBox="0 0 10 10" refX="8" refY="5" markerWidth="5" markerHeight="5" markerUnits="userSpaceOnUse"
          orient="auto-start-reverse">
          <path d="M0,0 L10,5 L0,10 z" fill={c} />
        </marker>
      ))}
    </defs>
  )
}

// a small double arrow: the direction the wave's electric field swings
function Pol({ x, y, dir, id, size = 7, opacity = 1 }) {
  const c = dir === 'h' ? H : V
  const [dx, dy] = dir === 'h' ? [size, 0] : [0, size]
  return (
    <line x1={x - dx} y1={y - dy} x2={x + dx} y2={y + dy} stroke={c} strokeWidth="2" opacity={opacity}
      markerStart={`url(#${id}-${dir})`} markerEnd={`url(#${id}-${dir})`} />
  )
}

function Satellite({ x, y, kind }) {
  if (kind === 'nisar') {
    // body, solar wing, and the 12 m mesh reflector on its boom
    return (
      <g transform={`translate(${x},${y})`}>
        <rect x="-38" y="-4" width="26" height="8" fill="#cfc8be" stroke="#5b544c" strokeWidth="0.8" />
        <rect x="-10" y="-6" width="14" height="12" fill="#e6c36a" stroke="#5b544c" strokeWidth="0.8" />
        <line x1="4" y1="0" x2="22" y2="-6" stroke="#5b544c" strokeWidth="1.2" />
        <ellipse cx="30" cy="-8" rx="14" ry="5" fill="#f2efe9" stroke="#5b544c" strokeWidth="0.8" />
      </g>
    )
  }
  return (
    <g transform={`translate(${x},${y})`}>
      <rect x="-8" y="-8" width="16" height="16" fill="#e6c36a" stroke="#5b544c" strokeWidth="0.8" />
      <rect x="10" y="-5" width="40" height="10" fill="#3d5a80" stroke="#5b544c" strokeWidth="0.8" />
      {[20, 30, 40].map((v) => <line key={v} x1={v} y1="-5" x2={v} y2="5" stroke="#a9bcd0" strokeWidth="0.6" />)}
    </g>
  )
}

function Sentinel2() {
  // typical reflectances, for illustration only
  const groups = [
    { label: 'Before', nir: 0.30, swir: 0.10, x: 112 },
    { label: 'After', nir: 0.12, swir: 0.20, x: 192 },
  ]
  const k = 220   // px per unit reflectance
  const base = 128
  const nbr = (g) => (g.nir - g.swir) / (g.nir + g.swir)
  const sign = (v) => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(2)
  return (
    <svg viewBox="0 0 360 160" role="img"
      aria-label="Before the fire, near-infrared is high and shortwave infrared low; after, the opposite.">
      <Satellite x={30} y={26} kind="sentinel2" />
      <text x="10" y="54" fontSize="9" fill="#5b544c">Sentinel-2 (ESA)</text>
      <text x="10" y="66" fontSize="8" fill="#6b645c">sunlight reflected</text>
      <text x="10" y="76" fontSize="8" fill="#6b645c">by the ground</text>
      <line x1="100" y1={base} x2="262" y2={base} stroke="#5b544c" strokeWidth="0.8" />
      {groups.map((g) => (
        <g key={g.label}>
          <rect x={g.x} y={base - g.nir * k} width="22" height={g.nir * k} fill={NIR} />
          <rect x={g.x + 26} y={base - g.swir * k} width="22" height={g.swir * k} fill={SWIR} />
          <text x={g.x + 24} y={base + 12} fontSize="9" textAnchor="middle" fill="#1c1917">{g.label}</text>
          <text x={g.x + 24} y={base + 24} fontSize="9" textAnchor="middle" fill="#6b645c">NBR {sign(nbr(g))}</text>
        </g>
      ))}
      <rect x="10" y="98" width="9" height="9" fill={NIR} />
      <text x="23" y="106" fontSize="8.5" fill="#1c1917">NIR (B8A)</text>
      <rect x="10" y="112" width="9" height="9" fill={SWIR} />
      <text x="23" y="120" fontSize="8.5" fill="#1c1917">SWIR (B12)</text>
      <text x="272" y="62" fontSize="9" fill="#1c1917">dNBR =</text>
      <text x="272" y="76" fontSize="9" fill="#1c1917">{sign(nbr(groups[0]))} − ({sign(nbr(groups[1]))})</text>
      <text x="272" y="92" fontSize="11" fontWeight="600" fill="#b2182b">= {(nbr(groups[0]) - nbr(groups[1])).toFixed(2)}</text>
      <text x="272" y="106" fontSize="9" fill="#b2182b">high severity</text>
    </svg>
  )
}

function Nisar() {
  const id = 'nx'
  const ground = 150
  const panel = (x0, burned) => (
    <g>
      <text x={x0 + 85} y="16" fontSize="10" fontWeight="600" textAnchor="middle" fill="#1c1917">
        {burned ? 'After the fire' : 'Forest'}
      </text>
      {/* pulse going down, horizontally polarized */}
      <line x1={x0 + 12} y1="34" x2={x0 + 62} y2="98" stroke="#5b544c" strokeWidth="1.2" strokeDasharray="4 3"
        markerEnd={`url(#${id}-k)`} />
      <Pol x={x0 + 22} y={56} dir="h" id={id} />
      <text x={x0 + 4} y="74" fontSize="9" fill={H} fontWeight="600">H sent</text>
      {/* ground */}
      <rect x={x0} y={ground} width="170" height="10" fill={burned ? '#8a8580' : '#8c6d46'} />
      {burned
        ? [40, 70, 104, 132].map((dx, i) => (
          <line key={dx} x1={x0 + dx} y1={ground} x2={x0 + dx + (i % 2 ? 2 : -2)} y2={ground - 30 - (i % 2) * 12}
            stroke="#2b2b2b" strokeWidth="2.5" strokeLinecap="round" />
        ))
        : [44, 84, 124].map((dx) => (
          <g key={dx}>
            <line x1={x0 + dx} y1={ground} x2={x0 + dx} y2={ground - 30} stroke="#5d4430" strokeWidth="3" />
            <ellipse cx={x0 + dx} cy={ground - 44} rx="19" ry="23" fill="#4d9221" opacity="0.9" />
            <path d={`M${x0 + dx},${ground - 28} l-10,-14 M${x0 + dx},${ground - 36} l9,-12`}
              stroke="#5d4430" strokeWidth="1.5" />
          </g>
        ))}
      {/* echoes going back up */}
      {burned ? (
        <>
          <line x1={x0 + 96} y1="104" x2={x0 + 146} y2="40" stroke={H} strokeWidth="1.6" markerEnd={`url(#${id}-h)`} />
          <Pol x={x0 + 150} y={62} dir="h" id={id} />
          <Pol x={x0 + 150} y={84} dir="v" id={id} size={4} opacity={0.45} />
          <text x={x0 + 142} y="102" fontSize="9" fill={H} fontWeight="600">HH</text>
        </>
      ) : (
        <>
          <line x1={x0 + 86} y1="96" x2={x0 + 140} y2="40" stroke={V} strokeWidth="1.6" markerEnd={`url(#${id}-v)`} />
          <line x1={x0 + 104} y1="104" x2={x0 + 156} y2="52" stroke={V} strokeWidth="1.6" markerEnd={`url(#${id}-v)`} />
          <Pol x={x0 + 160} y={78} dir="v" id={id} size={8} />
          <text x={x0 + 150} y="104" fontSize="9" fill={V} fontWeight="600">HV</text>
          <Pol x={x0 + 140} y={90} dir="h" id={id} size={5} opacity={0.6} />
        </>
      )}
      <text x={x0 + 85} y={ground + 24} fontSize="9.5" textAnchor="middle" fill="#1c1917">
        {burned ? 'HV drops; bare ground echoes H (HH)' : 'Wood scatters it many times: strong HV'}
      </text>
    </g>
  )
  return (
    <svg viewBox="0 0 360 180" role="img"
      aria-label="In a forest the radar echo comes back partly vertical (strong HV); after the fire HV drops.">
      <Arrowheads id={id} />
      {panel(0, false)}
      {panel(190, true)}
      <line x1="180" y1="30" x2="180" y2="150" stroke="#e4ddd3" />
      <Satellite x={180} y={14} kind="nisar" />
    </svg>
  )
}

export default function Explainer({ kind }) {
  if (kind === 'sentinel2') {
    return (
      <figure className="card explainer">
        <figcaption><strong>How Sentinel-2 grades the burn</strong></figcaption>
        <Sentinel2 />
        <p className="formula">NBR = (NIR − SWIR) / (NIR + SWIR)<br />dNBR = NBR<sub>before</sub> − NBR<sub>after</sub></p>
        <p className="muted">
          Healthy leaves reflect near-infrared; burned ground reflects more shortwave infrared. The bigger the
          drop, the harder it burned: low from 0.10, moderate from 0.27, high from 0.66 (Key and Benson, 2006).
          A pixel counts as burned only where NISAR also saw the canopy go. Bars show typical values.
        </p>
        <p className="credit">Schematic drawing, made with AI assistance.</p>
      </figure>
    )
  }
  return (
    <figure className="card explainer">
      <figcaption><strong>How NISAR sees a forest</strong></figcaption>
      <Nisar />
      <p className="muted">
        NISAR (NASA-ISRO) sends 24 cm microwaves, polarized horizontally (H), through smoke and cloud. Branches
        and trunks bounce them around and turn part of the echo vertical: a strong{' '}
        <b style={{ color: V }}>HV</b> signal. When the canopy burns, HV drops. Bare ground echoes mostly{' '}
        <b style={{ color: H }}>H</b> (HH), which rises on wet soil: HV down means burned, HH up alone means rain.
      </p>
      <p className="credit">Schematic drawing, made with AI assistance.</p>
    </figure>
  )
}
