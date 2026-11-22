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
  // Desktop: the middle of the screen. Phone: just under the map band, where the text pane starts.
  useEffect(() => {
    if (!data) return
    const io = new IntersectionObserver(
      (entries) => entries.forEach((en) => en.isIntersecting && setActive(Number(en.target.dataset.i))),
      { rootMargin: narrow ? '-62% 0px -36% 0px' : '-45% 0px -45% 0px' })
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
    // on a phone the step's top goes just under the map (scroll-margin-top in styles.css)
    const block = narrow || i === chapters.length - 1 ? 'start' : 'center'
    stepRefs.current[i]?.scrollIntoView({ behavior: 'smooth', block })
  }

  return (
    <>
      <MapView data={data} chapter={chapter} selectedId={town.id} onSelectTown={setTownId}
        rain={chapter.panel === 'rain' ? rain : null} onMap={setMap} />
      <NewsLinks map={map} items={chapter.news} towns={data.towns} active={Boolean(chapter.news)} />
      <Timeline meta={data.meta} passDates={data.passDates} chapter={chapter} />
      {import.meta.env.DEV && data.warnings.length > 0 && (
        <div className="dev-banner">
          Data check: {data.warnings.length} problem(s). {data.warnings[0]} Run <code>npm run check:data</code>.
        </div>
      )}
      <main className="story">
        {chapters.map((c, i) => (
          <section key={c.id} data-i={i} ref={(el) => { stepRefs.current[i] = el }}
            className={`step ${i === active ? 'active' : ''} ${c.panel === 'about' ? 'wide' : ''}`}>
            <h2>{c.title}</h2>
            <p>{c.body}</p>
            {c.news && <Headlines items={c.news} />}
            {c.burnedNote && <BurnedAreaNote meta={data.meta} official={c.burnedNote} />}
            <Legend chapter={c} layers={data.layers} rain={rain} />
            {c.explainer && <Explainer kind={c.explainer} meta={data.meta} />}
            {c.panel === 'towns' && (
              <>
                <select value={town.id} onChange={(e) => setTownId(e.target.value)} aria-label="Town">
                  {data.towns.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
                <TownCard town={town} />
              </>
            )}
            {c.panel === 'hindcast' && (
              <Hindcast town={town} record={data.hindcast.byId[town.id]} note={data.hindcast.note} />
            )}
            {c.panel === 'wind' && <WindRose rose={data.windRose} />}
            {c.panel === 'rain' && (
              <label className="card dial">
                <strong>{rain} mm/h</strong> for 15 minutes
                <input type="range" min="0" max="40" step="1" value={rain}
                  onChange={(e) => setRain(Number(e.target.value))} />
                <span className="muted">Model calibrated in the western US: read it as a ranking, not a forecast.</span>
              </label>
            )}
            {c.panel === 'credits' && (
              <ul className="credits">{data.meta.sources.map((s) => <li key={s}>{s}</li>)}</ul>
            )}
            {c.panel === 'about' && <About generated={data.meta.generated} />}
          </section>
        ))}
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
