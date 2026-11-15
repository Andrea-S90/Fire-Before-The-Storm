// Records the 29.5 s demo video of the story site, silent, 1920x1080, 30 fps, with the cuts on fixed
// timecodes (docs/PRESENTATION_PLAN.md). Voice, title card and subtitles are added in post.
//
// Needs Playwright and a static ffmpeg, installed outside the repo:
//   mkdir rec && cd rec && npm init -y && npm i playwright@1.48.2 ffmpeg-static@5.2.0 && npx playwright install chromium
// Run (NODE_PATH points at that folder's node_modules):
//   NODE_PATH=rec/node_modules node tools/record_demo.cjs [site url] [output folder]
const fs = require('fs')
const path = require('path')
const { execFileSync } = require('child_process')
const { chromium } = require('playwright')
const ffmpeg = require('ffmpeg-static')

const URL = process.argv[2] || 'https://andrea-s90.github.io/Fire-Before-The-Storm/'
const OUT = path.resolve(process.argv[3] || 'media/demo')
const LENGTH = 29.5
const W = 1920, H = 1080            // output pixels
const CSS_W = 1600, CSS_H = 900       // page size: at 1.2x density this gives 1920x1080, and the window fits a
const DPR = W / CSS_W                 // 1080p screen (a 1920x1080 page does not, and frames came out squashed)

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function main() {
  fs.mkdirSync(OUT, { recursive: true })
  const frames = path.join(OUT, 'frames')
  fs.rmSync(frames, { recursive: true, force: true })
  fs.mkdirSync(frames)

  // headed uses the real GPU and keeps up with the map; headless falls back to software WebGL and lags
  const headed = !process.env.HEADLESS
  const browser = await chromium.launch({ channel: process.env.CHANNEL || undefined, headless: !headed,
    args: headed ? ['--hide-scrollbars', '--window-position=0,0', `--window-size=${CSS_W},${CSS_H + 140}`]
      : ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--hide-scrollbars'] })
  const page = await browser.newPage({ viewport: { width: CSS_W, height: CSS_H }, deviceScaleFactor: DPR })

  // warm the cache: step through every chapter once so tiles and layers are loaded before recording
  await page.goto(URL, { waitUntil: 'networkidle' })
  const next = page.getByRole('button', { name: 'Next section' })
  for (let i = 0; i < 9; i++) { await next.click(); await sleep(1500) }
  await page.reload({ waitUntil: 'networkidle' })
  await sleep(4000)

  const step = (i) => page.locator('section.step').nth(i)
  const jump = (i) => step(i).evaluate((el) => el.scrollIntoView({ block: 'center' }))
  const reveal = (i, sel) => step(i).locator(sel).evaluate((el) => el.scrollIntoView({ behavior: 'smooth', block: 'end' }))
  const setRain = (v) => page.locator('.dial input').evaluate((el, v) => {
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, String(v))
    el.dispatchEvent(new Event('input', { bubbles: true }))
  }, v)

  const sweepRain = (from, to, by, ms) => page.locator('.dial input').evaluate((el, [from, to, by, ms]) => {
    const set = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set
    let v = from
    const id = setInterval(() => {
      v = Math.min(v + by, to)
      set.call(el, String(v)); el.dispatchEvent(new Event('input', { bubbles: true }))
      if (v >= to) clearInterval(id)
    }, ms)
  }, [from, to, by, ms])

  // show the rain chapter once, then return to the start: the stream and town layers are built the first time
  // they are shown, which otherwise blanks the rain scene for about two seconds
  await jump(5); await sleep(5000); await jump(0); await sleep(4000)

  // capture every painted frame with its browser timestamp
  const cdp = await page.context().newCDPSession(page)
  const shots = []
  cdp.on('Page.screencastFrame', ({ data, metadata, sessionId }) => {
    cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {})   // ack first: the next frame comes sooner
    const file = path.join(frames, `f${String(shots.length).padStart(5, '0')}.jpg`)
    shots.push({ file, t: metadata.timestamp })
    fs.promises.writeFile(file, Buffer.from(data, 'base64'))
  })
  await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 85, maxWidth: W, maxHeight: H, everyNthFrame: 1 })
  await sleep(500)
  const t0 = Date.now() / 1000
  const at = async (s) => { const wait = (t0 + s) * 1000 - Date.now(); if (wait > 0) await sleep(wait) }

  // 0.0 chapter 1 (title card goes on top in post); 4.0 bring the headlines to the middle
  await at(4.0); await step(0).locator('.headlines').evaluate((el) => el.scrollIntoView({ behavior: 'smooth', block: 'center' }))
  // 9.0 the fire: burn severity, then the Sentinel-2 card
  await at(9.0); await next.click()
  await at(10.6); await reveal(1, '.explainer')
  // 14.0 what radar sees, then the NISAR card
  await at(14.0); await next.click()
  await at(15.6); await reveal(2, '.explainer')
  // 19.0 the rain dial, swept from 0 to 40 mm/h
  await at(19.0); await jump(5); await setRain(0)
  // no zoom here: at a new zoom the large GeoJSON layers are re-tiled and vanish for several seconds
  await at(19.6); await sweepRain(4, 40, 6, 280)   // runs on the page's own timer, so it never blocks the script
  // 23.0 town cards: Piedralaves, then Casavieja
  await at(23.0); await jump(6); await page.getByLabel('Town').selectOption('piedralaves')
  await at(25.4); await page.getByLabel('Town').selectOption('casavieja')
  // 27.5 zoom out to the whole region
  await at(27.2); await jump(8)
  await at(LENGTH + 0.6)
  await cdp.send('Page.stopScreencast')
  await browser.close()

  // frames -> constant 30 fps H.264, each frame held until the next one was painted
  const kept = shots.filter((s, i) => s.t >= t0 || (shots[i + 1] && shots[i + 1].t > t0))
  const list = kept.map((s, i) => {
    const start = Math.max(s.t, t0)
    const end = kept[i + 1] ? kept[i + 1].t : t0 + LENGTH + 0.5
    return `file '${s.file.replace(/\\/g, '/')}'\nduration ${Math.max(end - start, 0.001).toFixed(4)}`
  })
  list.push(`file '${kept[kept.length - 1].file.replace(/\\/g, '/')}'`)
  const listFile = path.join(OUT, 'frames.txt')
  fs.writeFileSync(listFile, list.join('\n'))
  const mp4 = path.join(OUT, 'ashwatch_demo_raw.mp4')
  execFileSync(ffmpeg, ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', listFile,
    '-vf', `fps=30,scale=${W}:${H}:flags=lanczos,format=yuv420p`, '-t', String(LENGTH),
    '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-movflags', '+faststart', mp4])

  // one frame per cue, tiled, to check the cut without an editor
  const cues = [2, 6.5, 12.5, 17.5, 21.5, 25, 28.5]
  const sel = cues.map((c) => `lt(prev_t\\,${c})*gte(t\\,${c})`).join('+')
  execFileSync(ffmpeg, ['-y', '-loglevel', 'error', '-i', mp4, '-vf',
    `select='${sel}',scale=640:-1,tile=4x2:padding=6:color=white`, '-frames:v', '1', path.join(OUT, 'contact_sheet.jpg')])
  console.log(`${kept.length} frames painted -> ${mp4}`)
}

main().catch((e) => { console.error(e); process.exit(1) })
