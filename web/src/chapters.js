// The story, as data. Edit text and map state here; no component changes needed.
//   overlays: ids from layers.json shown as rasters
//   vectors:  burned | streams | catchments | water | towns
//   panel:    towns | hindcast | wind | rain | credits
//   view:     MapLibre camera
const AVILA = { center: [-4.66, 40.38], zoom: 9.6 }

export const chapters = [
  { id: 'intro', title: 'The fire is out. The danger isn’t.',
    body: 'In early October 2026, the first autumn rain washed ash from the Burgohondo fire into the rivers of Ávila. Tap water in Casavieja and Piedralaves was declared unfit to drink.',
    view: { center: [-4.66, 40.38], zoom: 8.6 }, overlays: [], vectors: ['towns'] },
  { id: 'fire', title: 'The fire',
    body: 'Between 22 July and 6 August the fire burned across the Alberche and Tiétar valleys.',
    view: AVILA, overlays: ['severity'], vectors: ['burned'] },
  { id: 'radar', title: 'What radar sees',
    body: 'NISAR’s L-band radar passes every 12 days and sees through smoke and cloud. HV backscatter comes from branches and trunks: when the canopy burns, it drops.',
    view: AVILA, overlays: ['dhv'], vectors: ['burned'] },
  { id: 'ash', title: 'From forest to ash',
    body: 'Fuel before the fire, times how much burned, times how much of that turns to ash. Every factor is a range, so the result is a range too.',
    view: AVILA, overlays: ['ash'], vectors: ['burned'] },
  { id: 'pathways', title: 'Four ways ash reaches your tap',
    body: 'Runoff into streams and reservoirs, debris flows from steep burned slopes, seepage to wells and springs, and ash carried by the wind.',
    view: AVILA, overlays: [], vectors: ['burned', 'streams', 'water'], panel: 'wind' },
  { id: 'rain', title: 'How much rain is too much?',
    body: 'Move the dial. A stream turns red when that rain intensity, held for 15 minutes, passes its debris-flow trigger.',
    view: AVILA, overlays: [], vectors: ['burned', 'streams', 'towns'], panel: 'rain' },
  { id: 'towns', title: 'One card per town',
    body: 'Click a town. Each pathway gets a level and an honest confidence label.',
    view: AVILA, overlays: [], vectors: ['burned', 'catchments', 'towns'], panel: 'towns' },
  { id: 'hindcast', title: 'Could we have known?',
    body: 'Satellite rain for 1 to 8 October against each town’s trigger. One fire is a case study, not proof.',
    view: AVILA, overlays: [], vectors: ['burned', 'streams', 'towns'], panel: 'hindcast' },
  { id: 'credits', title: 'Any fire, anywhere',
    body: 'Every input is a global open dataset. A new fire needs a new bounding box and a re-run.',
    view: { center: [-4.66, 40.38], zoom: 7.5 }, overlays: [], vectors: ['burned'], panel: 'credits' },
]
