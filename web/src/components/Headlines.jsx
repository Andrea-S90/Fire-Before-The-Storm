// News reports that anchor the story in what happened. Text only: outlet, date, headline and a link, never the
// outlets' photos or page screenshots (copyright). Items come from chapters.js (`news`); NewsLinks.jsx draws a
// line from each card to the towns it names.
export default function Headlines({ items }) {
  return (
    <div className="headlines">
      {items.map((n) => (
        <a key={n.url} className="card headline" href={n.url} target="_blank" rel="noreferrer" data-news={n.url}>
          <span className="hl-meta">{n.outlet} · {n.date}</span>
          <q lang={n.lang}>{n.headline}</q>
          {n.english && <span className="hl-en">{n.english}</span>}
        </a>
      ))}
    </div>
  )
}
