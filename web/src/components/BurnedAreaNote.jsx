import { fmt } from '../data.js'

// "How we compute this": why our burned area is smaller than the official figure. Our numbers come from
// meta.json (pipeline step outputs); the official figure and its source come from chapters.js (burnedNote).
export default function BurnedAreaNote({ meta, official }) {
  const sev = meta.severity?.severity ?? {}
  const byClass = meta.severity?.burned_ha ?? {}
  const ours = Object.values(byClass).reduce((a, b) => a + b, 0)
  const rvo = sev.radar_vs_optical ?? {}
  const max = Math.max(ours, official.official_ha)
  return (
    <details className="card how">
      <summary>How we compute the burned area</summary>
      <div className="ha-bars" aria-hidden="true">
        <span>Our map: {fmt(ours)} ha</span>
        <span className="ha-bar" style={{ width: `${(100 * ours) / max}%`, background: '#b2182b' }} />
        <span>Official figure: {fmt(official.official_ha)} ha</span>
        <span className="ha-bar" style={{ width: `${(100 * official.official_ha) / max}%`, background: '#9a9a9a' }} />
      </div>
      <p>
        We map {fmt(ours)} ha burned; the official figure is {fmt(official.official_ha)} ha (
        <a href={official.url} target="_blank" rel="noreferrer">{official.source}</a>). The gap is expected,
        because we measure something narrower:
      </p>
      <ul>
        <li>
          <b>Both satellites must agree.</b> A pixel counts as burned only where NISAR’s radar sees the canopy go
          and Sentinel-2 sees burned ground. Ground fires under trees that survived barely change the radar echo,
          so they are left out.
        </li>
        <li>
          <b>The official figure is the area inside the fire outline,</b> unburned patches included. We
          {sev.perimeter_used ? ' use' : ' do not use'} that outline, and we drop isolated patches smaller
          than {fmt(sev.min_burn_patch_ha)} ha as noise.
        </li>
        <li>
          <b>The study area is a fixed box.</b> Where the fire runs past its edge, we do not count it.
        </li>
      </ul>
      {rvo.optical_only_ha != null && (
        <p className="muted">
          The two satellites agree only partly (kappa {fmt(rvo.kappa, 2)}). Sentinel-2 alone flags another{' '}
          {fmt(rvo.optical_only_ha)} ha, mostly summer drying and harvest, though some of it is probably fire the
          radar could not see.
        </p>
      )}
      <p className="muted">
        So read our area, and the ash estimate built on it, as a conservative lower bound: where we are sure it
        burned, not everywhere it did.
      </p>
    </details>
  )
}
