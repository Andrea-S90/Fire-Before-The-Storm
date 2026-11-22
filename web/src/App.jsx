import { useEffect, useRef, useState } from 'react'
import { loadData } from './data.js'
import { chapters } from './chapters.js'
import { useNarrow } from './useNarrow.js'
import MapView from './components/MapView.jsx'
import TownCard from './components/TownCard.jsx'
import Hindcast from './components/Hindcast.jsx'
import WindRose from './components/WindRose.jsx'
import About from './components/About.jsx'
import Legend from './components/Legend.jsx'
import Timeline from './components/Timeline.jsx'
import Headlines from './components/Headlines.jsx'
import Explainer from './components/Explainer.jsx'
import BurnedAreaNote from './components/BurnedAreaNote.jsx'
import NewsLinks from './components/NewsLinks.jsx'

// what a phone reader finds behind 'More' in a section
function moreLabel(c) {
  const parts = []
  if (c.news) parts.push('news reports')
  if (c.burnedNote || c.explainer) parts.push('how it works')
  if (c.panel === 'towns') parts.push('town card')
  if (c.panel === 'hindcast') parts.push('the record')
  if (c.panel === 'wind') parts.push('wind rose')
  return parts.join(', ')
}

const hasLegend = (c) => c.overlays.length > 0 || c.vectors.length > 0

export default function App() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [active, setActive] = useState(0)
  const [townId, setTownId] = useState(null)
  const [rain, setRain] = useState(24)
  const [map, setMap] = useState(null)
  const stepRefs = useRef([])
  const narrow = useNarrow()

  useEffect(() => { loadData().then(setData, (e) => setError(String(e))) }, [])

  // scroll-driven chapters: the step crossing a line across the reading area is active.
  // Desktop: the middle of the screen. Phone: a line near the top, so a section turns active (and the map
  // flies) as the gap before it scrolls in, once the previous card has mostly left the screen.
  useEffect(() => {
    if (!data) return
    const io = new IntersectionObserver(
      (entries) => entries.forEach((en) => en.isIntersecting && setActive(Number(en.target.dataset.i))),
      { rootMargin: narrow ? '-20% 0px -79% 0px' : '-45% 0px -45% 0px' })
    stepRefs.current.forEach((el) => el && io.observe(el))
    return () => io.disconnect()
  }, [data, narrow])

  if (error) return <p className="fatal">Could not load the data files: {error}</p>
  if (!data) return <p className="fatal">Loading…</p>

  const town = data.towns.find((t) => t.id === townId)
    ?? data.towns.find((t) => t.named_in_reports && t.kind === 'town') ?? data.towns[0]
  const chapter = chapters[active]
  const goTo = (i) => {
    if (i < 0 || i >= chapters.length) return
    setActive(i)   // the map reacts at once; the scroll observer confirms when the step arrives
    const el = stepRefs.current[i]
    if (!el) return
    if (narrow) {
      // on a phone bring the card to just under mid-screen, with the map in full above it
      const card = el.querySelector('h2')
      window.scrollTo({ top: card.getBoundingClientRect().top + window.scrollY - window.innerHeight * 0.45, behavior: 'smooth' })
      return
    }
    el.scrollIntoView({ behavior: 'smooth', block: i === chapters.length - 1 ? 'start' : 'center' })
  }

  return (
    <>
      <MapView data={data} chapter={chapter} selectedId={town.id} onSelectTown={setTownId}
        rain={chapter.panel === 'rain' ? rain : null} onMap={setMap} />
      <NewsLinks map={map} items={chapter.news} towns={data.towns} active={Boolean(chapter.news)} />
      <Timeline meta={data.meta} passDates={data.passDates} chapter={chapter} />
      {narrow && hasLegend(chapter) && (
        <details className="legend-chip">
          <summary>Map key</summary>
          <Legend chapter={chapter} layers={data.layers} rain={rain} />
        </details>
      )}
      {import.meta.env.DEV && data.warnings.length > 0 && (
        <div className="dev-banner">
          Data check: {data.warnings.length} problem(s). {data.warnings[0]} Run <code>npm run check:data</code>.
        </div>
      )}
      <main className="story">
        {chapters.map((c, i) => {
          // pieces of a section; on a phone the reading extras fold into 'More' so each card stays short
          // and the map shows in full in the gap before every section (styles.css, phone block)
          const news = c.news && <Headlines items={c.news} />
          const burned = c.burnedNote && <BurnedAreaNote meta={data.meta} official={c.burnedNote} />
          const explainer = c.explainer && <Explainer kind={c.explainer} meta={data.meta} />
          const picker = c.panel === 'towns' && (
            <select value={town.id} onChange={(e) => setTownId(e.target.value)} aria-label="Town">
              {data.towns.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          )
          const townCard = c.panel === 'towns' && <TownCard town={town} />
          const hindcast = c.panel === 'hindcast' && (
            <Hindcast town={town} record={data.hindcast.byId[town.id]} note={data.hindcast.note} />
          )
          const wind = c.panel === 'wind' && <WindRose rose={data.windRose} />
          const dial = c.panel === 'rain' && (
            <label className="card dial">
              <strong>{rain} mm/h</strong> for 15 minutes
              <input type="range" min="0" max="40" step="1" value={rain}
                onChange={(e) => setRain(Number(e.target.value))} />
              <span className="muted">Model calibrated in the western US: read it as a ranking, not a forecast.</span>
            </label>
          )
          const credits = c.panel === 'credits' && (
            <ul className="credits">{data.meta.sources.map((s) => <li key={s}>{s}</li>)}</ul>
          )
          const about = c.panel === 'about' && <About generated={data.meta.generated} />
          const more = [news, burned, explainer, townCard, hindcast, wind].filter(Boolean)
          return (
            <section key={c.id} data-i={i} ref={(el) => { stepRefs.current[i] = el }}
              className={`step ${i === active ? 'active' : ''} ${c.panel === 'about' ? 'wide' : ''}`}>
              <h2>{c.title}</h2>
              <p>{c.body}</p>
              {narrow ? (
                <>
                  {picker}{dial}
                  {more.length > 0 && (
                    <details className="card more">
                      <summary>More: {moreLabel(c)}</summary>
                      {more.map((el, k) => <div key={k}>{el}</div>)}
                    </details>
                  )}
                </>
              ) : (
                <>
                  {news}{burned}
                  <Legend chapter={c} layers={data.layers} rain={rain} />
                  {explainer}{picker}{townCard}{hindcast}{wind}{dial}
                </>
              )}
              {credits}{about}
            </section>
          )
        })}
        <footer>Data export {data.meta.generated.slice(0, 16).replace('T', ' ')} UTC · {data.meta.config}</footer>
      </main>
      <nav className="pager" aria-label="Sections">
        <button type="button" onClick={() => goTo(active - 1)} disabled={active === 0}
          aria-label="Previous section">‹ Back</button>
        <span>{active + 1} / {chapters.length} · {chapter.title}</span>
        <button type="button" onClick={() => goTo(active + 1)} disabled={active === chapters.length - 1}
          aria-label="Next section">Next ›</button>
      </nav>
    </>
  )
}
