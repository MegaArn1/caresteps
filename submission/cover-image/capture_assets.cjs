/* Capture unmodified product UI using a fresh, nonpersistent browser context. */
const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');

async function main() {
  const origin = process.env.CARESTEPS_COVER_ORIGIN || 'http://127.0.0.1:8000';
  const assets = path.join(__dirname, 'assets');
  await fs.mkdir(assets, { recursive: true });
  const browser = await chromium.launch({
    headless: true,
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH
      ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {}),
  });
  const context = await browser.newContext({
    viewport: { width: 1120, height: 2200 },
    deviceScaleFactor: 2,
    reducedMotion: 'reduce',
    timezoneId: 'Asia/Singapore',
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const captures = [];
  async function record(name, clip, description) {
    await page.screenshot({ path: path.join(assets, name), clip, fullPage: true, animations: 'disabled' });
    captures.push({ filename: name, url: page.url(), css_clip: clip, description });
  }
  try {
    await page.goto(`${origin}/app`, { waitUntil: 'networkidle' });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path.join(assets, 'home-full.png'), fullPage: true });
    const home = await page.evaluate(() => {
      const title = document.querySelector('main h1').getBoundingClientRect();
      const tiles = document.querySelector('.tiles').getBoundingClientRect();
      return { x: Math.max(0, title.left - 12), y: title.top + scrollY - 10,
        width: Math.min(innerWidth - title.left, tiles.width + 24),
        height: tiles.bottom - title.top + 30 };
    });
    await record('home-actions.png', home, 'Greeting and three real homepage actions; banners are outside the crop.');
    const favicon = await page.locator('link[rel="icon"]').getAttribute('href');
    const logo = await context.newPage();
    await logo.setViewportSize({ width: 512, height: 512 });
    await logo.setContent(`<html><body style="margin:0;background:transparent"><img width="512" height="512" src="${favicon}"></body></html>`);
    await logo.locator('img').screenshot({ path: path.join(assets, 'caresteps-mark.png'), omitBackground: true });
    await logo.close();

    await page.goto(`${origin}/readings/new`, { waitUntil: 'networkidle' });
    await page.getByLabel('Top number (systolic)').fill('138');
    await page.getByLabel('Bottom number (diastolic)').fill('82');
    await page.locator('h1').click();
    const form = await page.evaluate(() => {
      const title = document.querySelector('main h1').getBoundingClientRect();
      const bp = document.querySelector('.bp-inputs').getBoundingClientRect();
      return { x: title.left - 12, y: title.top + scrollY - 10,
        width: Math.min(innerWidth - title.left, 1084), height: bp.bottom - title.top + 30 };
    });
    await record('reading-entry.png', form, 'Real blood-pressure form with typed but unsaved fictional example 138/82.');
    const values = await page.locator('.bp-inputs').boundingBox();
    await record('reading-values.png', {
      x: values.x - 8, y: values.y - 8,
      width: values.width + 16, height: values.height + 16,
    }, 'Actual labelled form fields with fictional unsaved values, captured without changing UI styles.');

    await page.goto(`${origin}/app/trends`, { waitUntil: 'networkidle' });
    await page.locator('svg[data-series] path').first().waitFor();
    await page.screenshot({ path: path.join(assets, 'trends-full.png'), fullPage: true });
    const chart = await page.evaluate(() => {
      const h = [...document.querySelectorAll('h2')].find(n => n.textContent.trim() === 'Day by day');
      const heading = h.getBoundingClientRect();
      const plot = document.querySelector('svg[data-series]').getBoundingClientRect();
      return { x: heading.left - 12, y: heading.top + scrollY - 12,
        width: Math.min(innerWidth - heading.left, plot.width + 24), height: plot.bottom - heading.top + 30 };
    });
    await record('trends-chart.png', chart, 'Unmodified real chart of the fictional seeded demo history.');

    const metadata = {
      date: '2026-10-16',
      origin,
      device_scale_factor: 2,
    viewport_css_pixels: { width: 1120, height: 2200 },
      data: 'Fictional seed data in an isolated temporary database; no real patient records.',
      runtime_mode: 'LLM_FORCE_DEGRADED=1; no live model requests.',
      edits: 'No HTML, CSS, labels, banner visibility or chart data were altered for capture. Crops are specified above.',
      captures,
      browser_errors: errors,
    };
    await fs.writeFile(path.join(assets, 'capture-info.json'), JSON.stringify(metadata, null, 2) + '\n');
    console.log(JSON.stringify(metadata, null, 2));
  } finally {
    await context.close();
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
