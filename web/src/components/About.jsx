import { project } from '../project.js'

const LinkList = ({ items }) => (
  <ul>
    {items.map(([label, url]) => (
      <li key={url}><a href={url} target="_blank" rel="noreferrer">{label}</a></li>
    ))}
  </ul>
)

// Same headings as the Space Apps project page, so nothing has to be written twice.
export default function About({ generated }) {
  const { links } = project
  const main = [['Project demo', links.demo], ['Live site', links.site], ['Source code', links.code]].filter(([, u]) => u)
  return (
    <article className="card about">
      <h3>{project.name}</h3>
      <p className="muted">{project.team}: {project.members.map(([n]) => n).join(' and ')} · Challenge: {project.challenge}</p>

      <h4>Summary</h4>
      <p>{project.summary}</p>

      <h4>Links</h4>
      <LinkList items={main} />

      <h4>Project description</h4>
      {project.description.map((p) => <p key={p.slice(0, 24)}>{p}</p>)}

      <h4>NASA data</h4>
      <LinkList items={project.nasaData} />

      <h4>Space agency partner data and other sources</h4>
      <LinkList items={project.partnerData} />

      <h4>References and tools</h4>
      <LinkList items={project.references} />

      <h4>Use of AI</h4>
      <p>{project.ai}</p>

      <h4>Team</h4>
      <p>
        {project.members.map(([name, url], i) => (
          <span key={url}>
            {i > 0 && ' · '}
            <a href={url} target="_blank" rel="noreferrer">{name}</a> (LinkedIn)
          </span>
        ))}
      </p>

      <h4>Acknowledgements</h4>
      <LinkList items={project.acknowledgements} />

      <p className="muted">Data export of {generated.slice(0, 16).replace('T', ' ')} UTC. Apache-2.0.</p>
    </article>
  )
}
