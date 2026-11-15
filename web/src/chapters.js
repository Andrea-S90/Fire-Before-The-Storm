// The story, as data. Edit text and map state here; no component changes needed.
//   overlays:  ids from layers.json shown as rasters (their colour scale appears in the legend)
//   vectors:   burned | streams | catchments | water | towns | reported (each has a legend entry);
//              reported = outlines of the municipalities the news items name
//   panel:     towns | hindcast | wind | rain | credits | about
//   view:      MapLibre camera
//   time:      periods highlighted on the timeline, as pairs of keys of meta.json "dates"
//   timeLabel: what the map shows, in words, next to the timeline
//   news:      news reports as text cards (outlet, date, headline, link; never their photos or screenshots)
//              and the towns each names (towns: ids; a line is drawn from the card to each)
//   explainer: 'sentinel2' | 'nisar' | 'ash', a plain-language card on a satellite or on the ash formula
//   burnedNote: an official burned-area figure (with its source) to compare with ours in a 'How we compute this' box
const AVILA = { center: [-4.66, 40.38], zoom: 9.6 }
const PRE = ['pre_start', 'fire_start']
const POST = ['post_start', 'post_end']
const FIRE = ['fire_start', 'fire_end']
const STORM = ['hindcast_start', 'hindcast_end']

export const chapters = [
  { id: 'intro', title: 'The fire is out. The danger isn’t.',
    body: 'In early October 2026, the first autumn rain washed ash from the Burgohondo fire into the rivers of Ávila. Tap water in Casavieja and Piedralaves was declared unfit to drink.',
    burnedNote: { official_ha: 33943, source: 'Reuters via Devdiscourse, 7 October 2026',
      url: 'https://www.devdiscourse.com/article/international/3988408-wildfire-ash-turns-spanish-mountain-river-black-contaminating-water-supply' },
    view: { center: [-4.66, 40.38], zoom: 8.6 }, overlays: [], vectors: ['reported', 'towns'],
    time: [STORM], timeLabel: 'towns rated after the fire; the rain came in early October',
    news: [
      { outlet: 'El Debate', date: '28 July 2026', lang: 'es',
        headline: 'Casavieja, el pueblo abulense que sobrevive a un escenario de guerra sin luz ni agua',
        english: 'During the fire: Casavieja without power or drinking water',
        towns: ['casavieja'],
        url: 'https://www.eldebate.com/espana/castilla-y-leon/20260728/casavieja-pueblo-abulense-sobrevive-escenario-guerra-luz-agua_444145.html' },
      { outlet: 'Reuters via Devdiscourse', date: '7 October 2026', lang: 'en',
        headline: 'Wildfire ash turns Spanish mountain river black, contaminating water supply',
        english: 'After the first rain: tap water in Piedralaves declared unfit for consumption',
        towns: ['casavieja', 'piedralaves'],
        url: 'https://www.devdiscourse.com/article/international/3988408-wildfire-ash-turns-spanish-mountain-river-black-contaminating-water-supply' },
    ] },
  { id: 'fire', title: 'The fire',
    body: 'Between 22 July and 6 August the fire burned across the Alberche and Tiétar valleys.',
    view: AVILA, overlays: ['severity'], vectors: ['burned'],
    time: [PRE, POST], timeLabel: 'burn severity, from the change between before and after the fire',
    explainer: 'sentinel2' },
  { id: 'radar', title: 'What radar sees',
    body: 'NISAR’s L-band radar passes every 12 days and sees through smoke and cloud. HV backscatter comes from branches and trunks: when the canopy burns, it drops.',
    view: AVILA, overlays: ['dhv'], vectors: ['burned'],
    time: [PRE, POST], timeLabel: 'radar change, after the fire minus before',
    explainer: 'nisar' },
  { id: 'ash', title: 'From forest to ash',
    body: 'Fuel before the fire, times how much burned, times how much of that turns to ash. Every factor is a range, so the result is a range too.',
    view: AVILA, overlays: ['ash'], vectors: ['burned'],
    time: [PRE, POST], timeLabel: 'ash load, from pre-fire fuel and post-fire severity',
    explainer: 'ash' },
  { id: 'pathways', title: 'Four ways ash reaches your tap',
    body: 'Runoff into streams and reservoirs, debris flows from steep burned slopes, seepage to wells and springs, and ash carried by the wind.',
    view: AVILA, overlays: [], vectors: ['burned', 'streams', 'water'], panel: 'wind',
    time: [FIRE, POST], timeLabel: 'wind during the fire; streams and wells as the fire left them' },
  { id: 'rain', title: 'How much rain is too much?',
    body: 'Move the dial. A stream turns red when that rain intensity, held for 15 minutes, passes its debris-flow trigger.',
    view: AVILA, overlays: [], vectors: ['burned', 'streams', 'towns'], panel: 'rain',
    time: [POST], timeLabel: 'the ground as the fire left it, before the autumn rain' },
  { id: 'towns', title: 'One card per town',
    body: 'Click a town. Each pathway gets a level and an honest confidence label.',
    view: AVILA, overlays: [], vectors: ['burned', 'catchments', 'towns'], panel: 'towns',
    time: [POST], timeLabel: 'risk per town, as the fire left it' },
  { id: 'hindcast', title: 'Could we have known?',
    body: 'Satellite rain for 1 to 8 October against each town’s trigger. One fire is a case study, not proof.',
    view: AVILA, overlays: [], vectors: ['burned', 'streams', 'towns'], panel: 'hindcast',
    time: [STORM], timeLabel: 'the first autumn rain' },
  { id: 'credits', title: 'Any fire, anywhere',
    body: 'Every input is a global open dataset. A new fire needs a new bounding box and a re-run.',
    view: { center: [-4.66, 40.38], zoom: 7.5 }, overlays: [], vectors: ['burned'], panel: 'credits' },
  { id: 'about', title: 'About this project',
    body: 'What we built, the data behind it and how it was made.',
    view: { center: [-4.66, 40.38], zoom: 7.5 }, overlays: [], vectors: ['burned'], panel: 'about' },
]
