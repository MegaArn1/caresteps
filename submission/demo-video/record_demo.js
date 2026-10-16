/* Record a real CareSteps browser walkthrough from an isolated, fictional dataset.
 * Usage: NODE_PATH=/path/to/node_modules node record_demo.js prepare|record
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const root = path.resolve(__dirname, '../..');
const work = process.env.DEMO_WORK_DIR || '/tmp/caresteps-demo-video';
const live = process.env.DEMO_LIVE_URL || 'http://127.0.0.1:8878';
const limited = process.env.DEMO_LIMITED_URL || 'http://127.0.0.1:8877';
const screenshot = path.join(root, 'submission/tool-evidence/screenshot/Screenshot 2026-10-15 225218.png');
const scenes = [];
function scene(title, caption, voice, action, minSeconds = 8) {
  scenes.push({ title, caption, voice, action, minSeconds });
}

scene('CareSteps', 'A fictional older adult. A real, runnable prototype.',
  'CareSteps is a competition prototype for older adults managing an existing blood pressure care plan in Singapore. This is a fictional patient, Mdm Tan. The app is not a medical service.', 'home', 14);
scene('Everyday support', 'Three everyday actions, with emergency help always visible.',
  'The home screen keeps the daily actions close: record a reading, check medicines, or explain what made self care difficult. The red help bar stays available across pages.', 'home-tiles', 11);
scene('Record a reading', 'A two-step entry: nothing is saved on this screen.',
  'I will record a blood pressure reading. Only the two numbers are required; the measurement time defaults to now. The page states that nothing has been saved yet.', 'reading-form', 12);
scene('Enter 145 over 88', 'These are simulated numbers, not a diagnosis.',
  'Here I enter one hundred forty five over eighty eight from the fictional home monitor. Optional fields can record a pulse or the patient\'s own words.', 'reading-fill', 10);
scene('Check before saving', 'The confirmation screen is separate from data entry.',
  'The first action prepares a draft and shows both numbers again. It has not written a reading. This explicit check helps catch a typing mistake before the record changes.', 'reading-preview', 13);
scene('Saved to history', 'Only the second action persists the reading.',
  'Now I confirm the draft. The reading appears in history with its measurement time. Earlier corrected rows remain visible, while statistics count only current readings.', 'reading-save', 13);
scene('Numbers with context', 'Averages show their window and denominator.',
  'My numbers shows a fourteen day window and the exact number of current readings used for each average. It does not classify any single measurement as safe or dangerous.', 'trends-top', 14);
scene('Gaps stay visible', 'A dashed marker means no reading was recorded that day.',
  'The chart stops at gaps instead of drawing a reassuring line across missing days. A gap means there is no record; it cannot tell us whether a measurement was missed.', 'trends-chart', 13);
scene('Accessible data list', 'The same data is available without the chart.',
  'I can expand the list to inspect each day, including those with no reading. The text table carries the same values as the chart for people who do not use graphics.', 'trends-list', 12);
scene('Ask what got in the way', 'The patient can use their own words or skip.',
  'The distinctive feature begins here. Rather than calling a missing record noncompliance, CareSteps asks what was difficult. The person may describe it, select a category, or skip the question.', 'barrier-form', 15);
scene('No forced category', 'Free text is kept without a guessed label.',
  'I write that the cuff is difficult to use and leave every category unselected. The next page explicitly says no reason has been given a name yet. The patient\'s words remain intact.', 'barrier-submit', 14);
scene('Confirm the reason', 'A user choice changes which support is offered.',
  'Only after I choose a category does the app treat that reason as confirmed. A suggestion from a model would remain a suggestion until the person confirms or changes it.', 'barrier-confirm', 12);
scene('Matching support', 'Support follows the confirmed reason.',
  'This page offers a different next step for a difficulty using equipment than it would for forgetting or running out of medicine. A support choice never changes a prescription.', 'barrier-options', 11);
scene('Medicine information', 'Confirmed medicines stay tied to the care plan.',
  'The medicine page lists the two fictional prescribed items. Each explanation is linked to a recorded source, and this prototype cannot decide a dose or change what a clinician prescribed.', 'medicines-top', 14);
scene('Source and review state', 'Team checked does not mean clinician reviewed.',
  'Notice the publisher, source link, and review status. These entries were checked by the team and have not received clinical review. That distinction appears where the explanation is displayed.', 'medicines-source', 12);
scene('Assistant in the app', 'The chat input is now present on the actual home page.',
  'The live assistant is available directly on the home page. I will ask one ordinary medicine question, then test a question it must refuse and a symptom that needs emergency routing.', 'chat-open', 13);
scene('Ask about amlodipine', 'This turn uses the configured model endpoint.',
  'I ask what amlodipine is for. The app sends the question to its configured model and makes source retrieval available as a tool. We will inspect the actual reply.', 'chat-ask', 11);
scene('Model answer', 'The reply is grounded in a recorded health source.',
  'The model explains the medicine using a recorded Singapore health source, and the chat labels the answer as coming from the assistant. The trace page will show the underlying tool calls and their results.', 'chat-answer', 17);
scene('Medication boundary', 'A dose-change question must be refused.',
  'Now I ask whether to double a dose. The deterministic safety boundary refuses to make that medication decision. It offers a way to raise the question with a doctor instead.', 'chat-boundary', 15);
scene('Chest pain: safety first', 'The safety rules route directly to Singapore emergency help.',
  'The words I have chest pain trigger the safety rules before any model request. The red answer points to the Singapore emergency ambulance number, nine nine five. The app has not called anyone.', 'chat-emergency', 16);
scene('Help is explicit', 'The app cannot place a call or monitor the patient.',
  'The dedicated help page repeats the verified contact route and states what the app has not done. This is guidance to seek help, not a diagnosis or a monitoring service.', 'help', 12);
scene('Inspect the system', 'Actual model status and prompt fingerprint.',
  'The trace page reports the current configuration: whether live model calls are attempted, which model is named, and a fingerprint for the prompts. It never displays an API key.', 'trace-top', 14);
scene('Rules before model', 'Enabled and held-back rules are distinguished.',
  'Safety and boundary rules run before the language model. The rule set shows twenty one enabled rules and two held for review. That is a limited, inspectable set, not clinical validation.', 'trace-rules', 13);
scene('Auditable tool calls', 'The log includes both successes and failures.',
  'The session log records routing decisions and tool call outcomes, including an unsuccessful call if one occurred. It is evidence of system actions, not a view into private model reasoning.', 'trace-audit', 15);
scene('Limited mode', 'A second isolated instance has no model connected.',
  'Here is the same app deliberately running without model access. The visible banner says limited mode. Recording, trends, visit preparation and the fixed emergency path remain available.', 'limited-home', 15);
scene('Honest fallback', 'A simple rule set does not invent a medicine explanation.',
  'The fallback answers through a small deterministic router. Where it cannot explain a free text question, it says so. The safety gate still works even with no language model.', 'limited-chat', 15);
scene('Appointment preparation', 'The patient reviews a printable summary.',
  'Back in the live instance, the appointment page assembles a fourteen day summary from stored facts. Nothing here books a visit, contacts a clinic, or sends a document.', 'summary-top', 13);
scene('Context for every number', 'Counts, dates and revisions are stated.',
  'The summary includes coverage and blood pressure counts with the period they describe. A corrected entry is tracked without double counting. Missing days remain visible rather than becoming an invented zero.', 'summary-readings', 14);
scene('Medication records', 'Taken, not taken, unsure and unrecorded stay separate.',
  'The medication section distinguishes four states, including no record at all. That last state cannot be called a missed dose. These are descriptions of what was recorded, not treatment advice.', 'summary-medication', 14);
scene('Questions for the visit', 'Patient words remain attributed to the patient.',
  'The patient can bring questions and reported difficulties into the appointment. The summary separates their words from the app\'s calculated facts, keeping the provenance of each claim clear.', 'summary-questions', 13);
scene('Patient controls the page', 'Questions can be excluded from print and put back.',
  'I can leave questions out of the printed document. The control changes to put back in the summary, so this choice is reversible. It does not delete the underlying patient record.', 'summary-omit', 14);
scene('Print-ready result', 'A separate view is ready to print or save as PDF.',
  'This is the print view the user can save as a PDF or carry into the visit. It keeps the time window and caveats. It has never been automatically shared.', 'summary-print', 14);
scene('WorkBuddy build evidence', 'A real task: the system statistics API and deployment guide.',
  'For the build workflow, we used WorkBuddy on bounded tasks. The saved development conversation shows its implementation of a system statistics endpoint and a single instance deployment guide, alongside a sample API result.', 'workbuddy', 18);
scene('What we learned', 'Verify outputs; document the trade-offs.',
  'A practical tool tip is to give the agent a small deliverable and an observable check, then inspect the changed files and run tests. An AI tool response alone is not verification.', 'reflection', 17);
scene('Limits and next steps', 'Fictional data. No clinical review or real-patient study.',
  'CareSteps remains a prototype with simulated records. The health content has not been clinically reviewed, the app has no hospital integration or real authentication, and the rules cannot guarantee detection of every emergency.', 'close', 18);

async function scrollTo(page, target, top = 145) {
  const locator = page.locator(target).first();
  await locator.waitFor({ timeout: 10000 });
  await locator.evaluate((el, offset) => window.scrollTo({ top: window.scrollY + el.getBoundingClientRect().top - offset, behavior: 'instant' }), top);
  await page.waitForTimeout(500);
}

async function perform(action, p) {
  switch (action) {
    case 'home': await p.goto(live + '/app'); break;
    case 'home-tiles': await scrollTo(p, '.tiles', 210); break;
    case 'reading-form': await p.locator('a.tile[href="/readings/new"]').click(); break;
    case 'reading-fill':
      await p.locator('#systolic').fill('145'); await p.locator('#diastolic').fill('88');
      await scrollTo(p, '#systolic', 300); break;
    case 'reading-preview':
      await p.getByRole('button', { name: 'Check and save' }).click();
      await p.getByRole('heading', { name: 'Check this before saving' }).waitFor(); break;
    case 'reading-save':
      await p.getByRole('button', { name: 'Yes, save this reading' }).click();
      await p.waitForURL('**/app/history?saved=1'); break;
    case 'trends-top': await p.goto(live + '/app/trends'); break;
    case 'trends-chart': await scrollTo(p, 'svg.chart', 280); break;
    case 'trends-list':
      await p.getByText('Show these numbers as a list').click();
      await scrollTo(p, '#data-list', 150); break;
    case 'barrier-form': await p.goto(live + '/support/ask'); await scrollTo(p, '#user_words', 250); break;
    case 'barrier-submit':
      await p.locator('#user_words').fill('The blood pressure cuff is hard to use with one hand.');
      await p.locator('form[action="/support/record"] button[type="submit"]').click();
      await p.getByText('No reason has been given a name yet.').waitFor(); break;
    case 'barrier-confirm':
      await p.locator('#category').selectOption('difficulty_using');
      await scrollTo(p, 'form[action*="confirm-category"] button', 365);
      await p.getByRole('button', { name: 'Save my answer' }).click({ force: true });
      await p.getByText('You told us:', { exact: false }).waitFor(); break;
    case 'barrier-options': await scrollTo(p, 'h2:has-text("Something that might help")', 180); break;
    case 'medicines-top': await p.goto(live + '/app/medicines'); break;
    case 'medicines-source': await scrollTo(p, 'a[href*="healthhub"]', 275).catch(async () => scrollTo(p, 'h2:has-text("What")', 260)); break;
    case 'chat-open': await p.goto(live + '/app'); await scrollTo(p, '#chat-form', 410); break;
    case 'chat-ask':
      await p.locator('#chat-input').fill('Can you explain what amlodipine is for?');
      await p.locator('#chat-form button').click();
      await p.getByText('Answered by the assistant', { exact: false }).last().waitFor({ timeout: 60000 });
      await scrollTo(p, '#chat-log', 250); break;
    case 'chat-answer': await scrollTo(p, '#chat-log', 275); break;
    case 'chat-boundary':
      await p.locator('#chat-input').fill('Should I double my dose today?');
      await p.locator('#chat-form button').click();
      await p.getByText('Answered by the safety rules', { exact: false }).last().waitFor({ timeout: 15000 });
      await scrollTo(p, '#chat-log', 230); break;
    case 'chat-emergency':
      await p.locator('#chat-input').fill('I have chest pain');
      await p.locator('#chat-form button').click();
      await p.locator('#chat-log .msg.emergency').last().waitFor({ timeout: 15000 });
      await scrollTo(p, '#chat-log .msg.emergency', 215); break;
    case 'help': await p.goto(live + '/app/help'); break;
    case 'trace-top': await p.goto(live + '/trace'); await scrollTo(p, 'h2:has-text("Is a model connected")', 135); break;
    case 'trace-rules': await scrollTo(p, 'h2:has-text("Rules that run before")', 140); break;
    case 'trace-audit': await scrollTo(p, 'h2:has-text("What it did while")', 135); break;
    case 'limited-home': await p.goto(limited + '/app'); break;
    case 'limited-chat':
      await scrollTo(p, '#chat-form', 410);
      await p.locator('#chat-input').fill('Can you explain what amlodipine is for?');
      await p.locator('#chat-form button').click();
      await p.getByText('Answered by the simple rule set', { exact: false }).last().waitFor();
      await scrollTo(p, '#chat-log .msg.assistant', 235); break;
    case 'summary-top': await p.goto(live + '/summary'); break;
    case 'summary-readings': await scrollTo(p, '#h-readings', 145); break;
    case 'summary-medication': await scrollTo(p, '#h-medication', 140); break;
    case 'summary-questions': await scrollTo(p, 'h2:has-text("Questions")', 140); break;
    case 'summary-omit':
      await scrollTo(p, '#h-questions', 160);
      await p.locator('form[action="/summary/omit?key=questions.items"] button').click({ force: true });
      await scrollTo(p, '#h-questions', 155); break;
    case 'summary-print': await p.goto(live + '/summary/print'); break;
    case 'workbuddy': await p.goto('file://' + screenshot); break;
    case 'reflection': await p.goto(live + '/trace'); await scrollTo(p, 'h2:has-text("The instructions given to the model")', 160); break;
    case 'close': await p.goto(live + '/app'); break;
    default: throw new Error('Unknown action: ' + action);
  }
}

async function main() {
  fs.mkdirSync(work, { recursive: true });
  const mode = process.argv[2];
  if (mode === 'prepare') {
    fs.writeFileSync(path.join(work, 'script.json'), JSON.stringify(scenes.map(({ action, ...rest }, index) => ({ index, action, ...rest })), null, 2));
    console.log('Prepared', scenes.length, 'scenes');
    return;
  }
  if (mode !== 'record' && mode !== 'rehearse') throw new Error('Use prepare, rehearse, or record');
  const times = JSON.parse(fs.readFileSync(path.join(work, 'voice_times.json')));
  const browser = await chromium.launch({ headless: true,
    executablePath: process.env.DEMO_CHROME || undefined,
    args: ['--no-sandbox'] });
  const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1,
    recordVideo: mode === 'record' ? { dir: work, size: { width: 1920, height: 1080 } } : undefined });
  const page = await context.newPage();
  const actual = [];
  const start = Date.now();
  try {
    for (let i = 0; i < scenes.length; i++) {
      const s = scenes[i];
      const sceneStart = Date.now();
      const target = Math.max(Math.min(s.minSeconds, 8), times[i].seconds + 0.9) * 1000;
      await perform(s.action, page);
      const actionMs = Date.now() - sceneStart;
      if (mode === 'record') await page.waitForTimeout(Math.max(900, target - actionMs));
      else await page.waitForTimeout(280);
      if (mode === 'rehearse' && ['chat-answer', 'chat-emergency', 'trace-audit', 'limited-chat', 'summary-print', 'workbuddy'].includes(s.action)) {
        await page.screenshot({ path: path.join(work, `preview-${s.action}.png`) });
      }
      actual.push({ index: i, title: s.title, caption: s.caption, startMs: sceneStart - start,
        endMs: Date.now() - start, voiceSeconds: times[i].seconds, actionMs });
      console.log(`${i + 1}/${scenes.length} ${s.action}: ${Math.round(actionMs / 1000)}s action, ${Math.round((Date.now() - start) / 1000)}s elapsed`);
    }
  } finally {
    fs.writeFileSync(path.join(work, 'actual_times.json'), JSON.stringify(actual, null, 2));
    if (mode === 'record') {
      const video = page.video();
      await context.close();
      fs.renameSync(await video.path(), path.join(work, 'raw.webm'));
    } else await context.close();
    await browser.close();
  }
}
main().catch(e => { console.error(e); process.exitCode = 1; });
