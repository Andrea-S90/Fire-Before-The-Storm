import { useEffect, useState } from 'react'

// Leader lines from a news card (Headlines.jsx, matched by data-news) to the towns it names on the map,
// shown while that card is hovered or focused.
// Drawn in screen space and re-measured every frame while the chapter is active, so they follow scroll,
// camera moves and resizes.
export default function NewsLinks({ map, items, towns, active }) {
  const [lines, setLines] = useState([])

  useEffect(() => {
    if (!map || !active || !items?.length) { setLines([]); return }
    let raf
    const measure = () => {
      const next = []
      const box = map.getContainer().getBoundingClientRect()   // the map may not start at the top left
      for (const n of items) {
        const card = document.querySelector(`[data-news="${CSS.escape(n.url)}"]`)
        // only for the card under the pointer (or focused with the keyboard)
        if (!card || !card.matches(':hover, :focus-visible')) continue
        const r = card.getBoundingClientRect()
        for (const id of n.towns ?? []) {
          const t = towns.find((x) => x.id === id)
          if (!t) continue
          const q = map.project([t.lon, t.lat])
          const p = { x: q.x + box.left, y: q.y + box.top }
          // leave from the card edge that faces the town
          const x1 = p.x >= r.right ? r.right : p.x <= r.left ? r.left : r.left + r.width / 2
          const y1 = x1 === r.left + r.width / 2 ? (p.y < r.top ? r.top : r.bottom) : r.top + r.height / 2
          next.push({ key: `${n.url}|${id}`, x1, y1, x2: p.x, y2: p.y, name: t.name })
        }
      }
      setLines((prev) => (JSON.stringify(prev) === JSON.stringify(next) ? prev : next))
      raf = requestAnimationFrame(measure)
    }
    measure()
    return () => cancelAnimationFrame(raf)
  }, [map, items, towns, active])

  if (!lines.length) return null
  return (
    <svg className="news-links" aria-hidden="true">
      {lines.map((l) => {
        const mx = (l.x1 + l.x2) / 2
        return (
          <g key={l.key}>
            <path d={`M${l.x1},${l.y1} C${mx},${l.y1} ${mx},${l.y2} ${l.x2},${l.y2}`} />
            <circle cx={l.x1} cy={l.y1} r="3.5" className="nl-start" />
            <circle cx={l.x2} cy={l.y2} r="11" className="nl-ring" />
          </g>
        )
      })}
    </svg>
  )
}
