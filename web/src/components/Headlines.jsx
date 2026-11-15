// News reports that anchor the story in what happened: outlet, date, headline, a link, and a small screenshot of
// the article's first page (src/assets/news, captured once, cropped). Items come from chapters.js (`news`).
// NewsLinks.jsx draws a line from each card to the towns it names.
const SHOTS = import.meta.glob('../assets/news/*.jpg', { eager: true, import: 'default' })
const shotUrl = (name) => SHOTS[`../assets/news/${name}.jpg`]

export default function Headlines({ items }) {
  return (
    <div className="headlines">
      {items.map((n) => (
        <a key={n.url} className={`card headline ${n.shot ? 'has-shot' : ''}`} href={n.url} target="_blank"
          rel="noreferrer" data-news={n.url}>
          {n.shot && (
            <img className="hl-shot" src={shotUrl(n.shot)} loading="lazy"
              alt={`First page of the ${n.outlet} article, as published`} />
          )}
          <span className="hl-text">
            <span className="hl-meta">{n.outlet} · {n.date}</span>
            <q lang={n.lang}>{n.headline}</q>
            {n.english && <span className="hl-en">{n.english}</span>}
          </span>
        </a>
      ))}
    </div>
  )
}
