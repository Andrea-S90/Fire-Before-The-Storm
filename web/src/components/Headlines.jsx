// News reports that anchor the story in what happened. Text only: outlet, date, headline and a link,
// never the outlets' photos or page screenshots. Items come from chapters.js (`news`).
export default function Headlines({ items }) {
  return (
    <div className="headlines">
      {items.map((n) => (
        <a key={n.url} className="card headline" href={n.url} target="_blank" rel="noreferrer">
          <span className="hl-meta">{n.outlet} · {n.date}</span>
          <q lang={n.lang}>{n.headline}</q>
          {n.english && <span className="hl-en">{n.english}</span>}
        </a>
      ))}
    </div>
  )
}
