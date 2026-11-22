// Project facts shown in the "About" section. They mirror the fields of the Space Apps project page,
// so the page and the site say the same thing. Leave a link as null until it exists: it is then not shown.
// README.md repeats them under "About": update it in the same commit.
export const project = {
  name: 'Ash Watch',
  team: 'Fire Before the Storm (Barcelona local event)',
  members: [
    ['Andrea Serio', 'https://www.linkedin.com/in/andrea--serio'],
    ['Maria Golikova', 'https://www.linkedin.com/in/maria-golikova-bi/'],
  ],
  // Checked against the 2026 Barcelona local event page:
  // https://www.spaceappschallenge.org/2026/local-events/barcelona/
  acknowledgements: [
    ['NASA International Space Apps Challenge, funded by NASA\'s Science Mission Directorate, for the challenge and the data',
      'https://www.spaceappschallenge.org/'],
    ['42 Barcelona (Fundación Telefónica), for hosting the Barcelona local event at its campus in the Parc Tecnològic',
      'https://www.42barcelona.com/'],
    ['The Barcelona local event organisers and mentors',
      'https://www.spaceappschallenge.org/2026/local-events/barcelona/'],
  ],
  challenge: 'Dancing with the SARs',
  summary:
    'Ash Watch is a post-fire warning for drinking water. It uses NASA-ISRO NISAR L-band radar to measure the forest before a fire, the burn itself and the regrowth after it, then follows the ash downhill: for every town it shows how the water supply could be polluted, by which pathway, and how confident that estimate is. The demo is the Burgohondo fire in Ávila, Spain, in July 2026.',
  links: {
    demo: null,   // 30-second video or 7 slides, public link
    site: null,   // this site, once it is deployed
    code: 'https://github.com/Andrea-S90/Fire-Before-The-Storm',
  },
  description: [
    'What it does. For each town or reservoir downstream of a fire, Ash Watch gives one card: a level for four pathways (surface runoff, debris flow, groundwater, airborne ash), the evidence behind it and the first lab tests to run.',
    'How it works. A Python pipeline cuts every NISAR GCOV acquisition to the area, compares HV and HH backscatter before and after the fire per pass, and combines the radar change with Sentinel-2 to map the burn. Pre-fire HV is fitted to ESA CCI Biomass to estimate fuel, and fuel times severity gives an ash load with a Monte Carlo range. Terrain routing sends that ash down each catchment; a published debris-flow model gives a rain trigger per stream; wind and a groundwater index give two screening layers. The pipeline exports small files that this static site reads.',
    'What it is not. One fire is a case study, not a validation. The debris-flow model was calibrated in the western United States, so read it as a ranking. Groundwater and airborne ash have no local measurements behind them and are labelled screening and indicative.',
    'Built with. Python (rasterio, pysheds, scikit-learn, h5py), Vite, React and MapLibre GL JS. Open source under Apache-2.0.',
  ],
  ai: 'The pipeline code, the site code and the documentation were written with Claude Code (Anthropic), directed and reviewed by the team; commits made that way carry a Co-Authored-By line. The idea, the choice of methods and the interpretation are ours.',
  nasaData: [
    ['NISAR L2 GCOV (NASA-ISRO), L-band HH and HV backscatter, from the ASF DAAC',
      'https://nisar-docs.asf.alaska.edu/products-overview/'],
    ['GPM IMERG Late Run V07, half-hourly rainfall, for the October hindcast', 'https://gpm.nasa.gov/data/imerg'],
    ['NASA Earthdata Login and Search, used to find and download both', 'https://www.earthdata.nasa.gov/'],
  ],
  partnerData: [
    ['ISRO: NISAR is a joint NASA-ISRO mission', 'https://www.isro.gov.in/NISARSatellite.html'],
    ['ESA / Copernicus Sentinel-2 L2A, burn severity (dNBR), via the Earth Search STAC catalogue',
      'https://earth-search.aws.element84.com/v1'],
    ['ESA CCI Biomass, above-ground biomass used to calibrate the fuel estimate',
      'https://climate.esa.int/en/projects/biomass/'],
    ['Copernicus DEM GLO-30, terrain and flow routing, and the relief of the 3D and AR model',
      'https://registry.opendata.aws/copernicus-dem/'],
    ['ERA5 hourly wind (Copernicus Climate Change Service)', 'https://cds.climate.copernicus.eu/'],
    ['ISRIC SoilGrids, soil texture and organic carbon for erodibility', 'https://soilgrids.org/'],
    ['OpenStreetMap contributors: towns, reservoirs, wells and springs', 'https://www.openstreetmap.org/copyright'],
  ],
  references: [
    ['Staley et al. (2017), the M1 post-fire debris-flow likelihood model (USGS)',
      'https://doi.org/10.1016/j.geomorph.2016.10.019'],
    ['Yu and Saatchi (2016), sensitivity of L-band radar to forest biomass', 'https://mdpi.com/2072-4292/8/6/522'],
    ['Quigley et al. (2019), ash produced per unit of fuel consumed',
      'https://link.springer.com/doi/10.1186/s42408-018-0015-7'],
    ['Reuters via KFGO (7 Oct 2026), the report of the contaminated water supply',
      'https://kfgo.com/2026/10/07/wildfire-ash-turns-spanish-mountain-river-black-contaminating-water-supply/'],
    ['El Debate (28 Jul 2026), Casavieja without power or drinking water during the fire',
      'https://www.eldebate.com/espana/castilla-y-leon/20260728/casavieja-pueblo-abulense-sobrevive-escenario-guerra-luz-agua_444145.html'],
    ['Key and Benson (2006), the Normalized Burn Ratio and its severity classes (USDA Forest Service, FIREMON)',
      'https://research.fs.usda.gov/treesearch/24066'],
    ['MapLibre GL JS', 'https://maplibre.org/'],
    ['model-viewer (Google), the 3D and AR viewer', 'https://modelviewer.dev/'],
    ['OpenFreeMap basemap (OpenMapTiles, OpenStreetMap)', 'https://openfreemap.org/'],
    ['AWS Terrain Tiles (Mapzen), the 3D terrain under the map', 'https://registry.opendata.aws/terrain-tiles/'],
  ],
}
