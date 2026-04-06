import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

import { chromium } from 'playwright';

const repoRoot = resolve(fileURLToPath(new URL('../..', import.meta.url)));

const mimeTypes = {
  '.css': 'text/css; charset=utf-8',
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
};

function contentType(path) {
  return mimeTypes[extname(path)] ?? 'text/plain; charset=utf-8';
}

function resolveRequestPath(pathname) {
  const relativePath = pathname === '/' ? '/tests/fixtures/youtube-feed.html' : pathname;
  const candidate = resolve(repoRoot, `.${relativePath}`);
  if (!candidate.startsWith(repoRoot)) {
    throw new Error(`Blocked path outside repo root: ${pathname}`);
  }
  return candidate;
}

function mockScore(item) {
  if (item.title.includes('Breaking aliens')) {
    return {
      risk_score: 0.74,
      confidence: 0.88,
      uncertainty: 0.12,
      recommended_action: 'blur',
      reasons: ['Title contains strong sensational framing patterns.'],
      explanation_id: 'exp-card-1',
      explanation_summary: 'Flagged because the title framing is sensational.',
      evidence: [
        {
          kind: 'title',
          label: 'Sensational title framing',
          score: 0.88,
          details: 'Multiple high-intensity claim tokens were detected in the title.',
        },
      ],
    };
  }
  if (item.title.includes('Weekly launch schedule')) {
    return {
      risk_score: 0.18,
      confidence: 0.81,
      uncertainty: 0.19,
      recommended_action: 'none',
      reasons: [],
      explanation_id: null,
      explanation_summary: null,
      evidence: [],
    };
  }
  if (item.title.includes('Secret lab leak')) {
    return {
      risk_score: 0.83,
      confidence: 0.91,
      uncertainty: 0.09,
      recommended_action: 'ask-report',
      reasons: ['Risk score crossed the report-prompt threshold.'],
      explanation_id: 'exp-card-3',
      explanation_summary: 'Flagged because risk crossed the report prompt threshold.',
      evidence: [
        {
          kind: 'policy',
          label: 'Policy crossed the report threshold',
          score: 0.83,
          details: 'Risk score crossed the report-prompt threshold.',
        },
      ],
    };
  }
  return {
    risk_score: 0.44,
    confidence: 0.79,
    uncertainty: 0.21,
    recommended_action: 'badge',
    reasons: ['Dynamic card entered the moderate-risk review band.'],
    explanation_id: 'exp-card-dynamic',
    explanation_summary: 'Flagged because the dynamic card entered the moderate-risk review band.',
    evidence: [
      {
        kind: 'policy',
        label: 'Moderate-risk review band',
        score: 0.44,
        details: 'Dynamic card entered the moderate-risk review band.',
      },
    ],
  };
}

async function main() {
  const server = createServer(async (request, response) => {
    try {
      const url = new URL(request.url ?? '/', 'http://127.0.0.1');
      const path = resolveRequestPath(url.pathname);
      const source = await readFile(path);
      response.statusCode = 200;
      response.setHeader('Content-Type', contentType(path));
      response.end(source);
    } catch {
      response.statusCode = 404;
      response.end('not found');
    }
  });

  await new Promise((resolveListen) => server.listen(0, '127.0.0.1', resolveListen));
  const address = server.address();
  assert(address && typeof address === 'object' && 'port' in address);
  const baseUrl = `http://127.0.0.1:${address.port}`;

  const feedbackEvents = [];
  const optimizationRequests = [];
  const suggestionRequests = [];
  const youtubeReports = [];
  let batchRequests = 0;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
    await page.addInitScript(() => {
      const listeners = [];
      const sentMessages = [];

      window.chrome = {
        runtime: {
          onMessage: {
            addListener(listener) {
              listeners.push(listener);
            },
          },
          async sendMessage(message) {
            sentMessages.push(message);
            return { ok: true };
          },
        },
      };

      Object.defineProperty(window, '__truthlensSentMessages', {
        value: sentMessages,
        configurable: true,
      });

      Object.defineProperty(window, '__dispatchTruthlensRuntimeMessage', {
        value: async (message) => {
          for (const listener of listeners) {
            await new Promise((resolve) => {
              listener(message, {}, () => resolve());
              setTimeout(resolve, 0);
            });
          }
        },
        configurable: true,
      });

      Object.defineProperty(navigator, 'clipboard', {
        value: {
          writeText: async (text) => {
            window.__truthlensClipboardText = text;
          },
        },
        configurable: true,
      });
    });

    await page.route('http://127.0.0.1:8000/batch-score', async (route) => {
      batchRequests += 1;
      const body = JSON.parse(route.request().postData() ?? '{}');
      const results = Object.fromEntries(
        (body.items ?? []).map((item) => [item.item_id, mockScore(item)]),
      );
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ results }),
      });
    });

    await page.route('http://127.0.0.1:8000/feedback', async (route) => {
      feedbackEvents.push(JSON.parse(route.request().postData() ?? '{}'));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'accepted' }),
      });
    });

    await page.route('http://127.0.0.1:8000/manual-report/optimize', async (route) => {
      optimizationRequests.push(JSON.parse(route.request().postData() ?? '{}'));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          issues: [
            {
              issue_type: 'title',
              comment: 'The title frames an unverified allegation as established fact.',
            },
          ],
          optimization_model: 'gemini-2.5-flash',
          report_text:
            'The video title presents an unverified allegation as established fact and should be reviewed for misleading framing.',
        }),
      });
    });

    await page.route('http://127.0.0.1:8000/manual-report/suggest', async (route) => {
      if (route.request().method() !== 'POST') {
        await route.fulfill({
          status: 204,
          headers: {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST, OPTIONS',
          },
          body: '',
        });
        return;
      }
      suggestionRequests.push(JSON.parse(route.request().postData() ?? '{}'));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          issues: [
            {
              issue_type: 'thumbnail',
              suggested: true,
              comment: 'The thumbnail framing appears disconnected from the stated topic.',
            },
            {
              issue_type: 'title',
              suggested: true,
              comment: 'The title overstates certainty relative to the available context.',
            },
            {
              issue_type: 'description',
              suggested: true,
              comment: 'The description snippet does not clearly reinforce the same understanding created by the title and thumbnail.',
            },
            {
              issue_type: 'transcript',
              suggested: true,
              comment: 'The transcript context does not clearly support the impression created by the thumbnail and title.',
            },
            {
              issue_type: 'channel',
              suggested: true,
              comment: 'The channel context should be reviewed alongside the packaging signals on this video.',
            },
            {
              issue_type: 'other',
              suggested: true,
              comment: 'The packaging resembles clickbait.',
            },
          ],
          suggested_outcome: 'moderate',
          suggestion_model: 'gemini-2.5-flash',
        }),
      });
    });

    await page.route('http://127.0.0.1:8000/feedback-summary', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_events: 6,
          correction_rate: 0.33,
          channel_profiles: {
            'opensky alerts': {
              channel_name: 'OpenSky Alerts',
              event_count: 4,
              bias: -0.08,
              report_count: 3,
              dismiss_count: 0,
              mute_count: 0,
              moderate_request_count: 2,
              remove_request_count: 1,
              scored_item_count: 6,
              reported_item_count: 3,
              trust_score: 3.4,
            },
            'context first media': {
              channel_name: 'Context First Media',
              event_count: 5,
              bias: 0.04,
              report_count: 0,
              dismiss_count: 0,
              mute_count: 0,
              transparent_count: 5,
              moderate_request_count: 0,
              remove_request_count: 0,
              scored_item_count: 9,
              reported_item_count: 0,
              trust_score: 8.6,
            },
            'signal watch europe': {
              channel_name: 'Signal Watch Europe',
              event_count: 3,
              bias: -0.04,
              report_count: 2,
              dismiss_count: 1,
              mute_count: 0,
              moderate_request_count: 2,
              remove_request_count: 0,
              scored_item_count: 8,
              reported_item_count: 2,
              trust_score: 6.0,
            },
            'dynamic signal desk': {
              channel_name: 'Dynamic Signal Desk',
              event_count: 1,
              bias: 0.0,
              report_count: 0,
              dismiss_count: 0,
              mute_count: 0,
              moderate_request_count: 0,
              remove_request_count: 0,
              scored_item_count: 2,
              reported_item_count: 0,
              trust_score: 5.2,
            },
          },
          top_channels: [
            {
              channel_name: 'OpenSky Alerts',
              event_count: 4,
              bias: -0.08,
              report_count: 3,
              dismiss_count: 0,
              mute_count: 0,
              moderate_request_count: 2,
              remove_request_count: 1,
              scored_item_count: 6,
              reported_item_count: 3,
              trust_score: 3.4,
            },
          ],
        }),
      });
    });

    await page.route('http://127.0.0.1:8000/youtube/auth/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          configured: true,
          connected: true,
          auth_url: null,
          channel_name: 'TruthLens Test Channel',
        }),
      });
    });

    await page.route('http://127.0.0.1:8000/youtube/report', async (route) => {
      youtubeReports.push(JSON.parse(route.request().postData() ?? '{}'));
      await route.fulfill({
        status: 400,
        contentType: 'application/json',
        body: JSON.stringify({
          detail:
            "YouTube did not return a suitable 'Spam or misleading' report category for this account. Available categories: Sex or nudity.",
        }),
      });
    });

    await page.goto(`${baseUrl}/tests/fixtures/youtube-feed.html`);
    await page.addScriptTag({
      type: 'module',
      url: `${baseUrl}/apps/extension/dist/content.js`,
    });

    await page.waitForFunction(
      () => document.querySelectorAll('[data-truthlens-processed="true"]').length === 3,
    );

    assert.equal(batchRequests, 1);
    assert.equal(await page.locator('#truthlens-overlay-root').count(), 1);
    assert.equal(await page.locator('.truthlens-action-row').count(), 0);

    const cards = page.locator('[data-truthlens-card]');
    await page.waitForFunction(
      () => document.querySelector('[data-truthlens-card]')?.classList.contains('truthlens-card-blur') ?? false,
    );
    assert.equal(
      await cards.nth(0).evaluate((element) => element.classList.contains('truthlens-card-blur')),
      true,
    );
    assert.equal(
      await cards.nth(1).evaluate((element) => element.classList.contains('truthlens-card-hidden')),
      false,
    );
    assert.match(
      (await cards.nth(2).locator('.truthlens-card-flag').textContent()) ?? '',
      /^\d{1,2}\.\d$/,
    );
    assert.equal(await cards.nth(0).getAttribute('data-truthlens-personalization'), 'downranked');
    assert.equal(await cards.nth(0).evaluate((element) => element.style.order), '');
    assert.equal(await cards.nth(1).getAttribute('data-truthlens-personalization'), 'boosted');
    assert.equal(await cards.nth(1).evaluate((element) => element.style.order), '');
    assert.equal(await cards.nth(1).locator('.truthlens-card-flag').textContent(), '10.0');
    assert.equal(await cards.nth(2).evaluate((element) => element.style.order), '');
    assert.equal(await cards.nth(2).locator('.truthlens-review-prompt').textContent(), 'Review report');
    if ((await page.locator('.truthlens-report-card').count()) === 0) {
      await cards.nth(2).locator('.truthlens-review-prompt').click();
    }
    await expectText(
      page,
      '.truthlens-report-card h2',
      'Secret lab leak exposed in new footage',
    );
    await expectText(page, '.truthlens-live-status', 'Preparing TruthLens report analysis');
    await expectText(page, '.truthlens-live-status', 'Checking YouTube reporting connection');
    await expectText(page, '.truthlens-live-status', 'Loading watch metadata and transcript context');
    await expectText(page, '.truthlens-live-status', 'Drafting initial comments with Gemini');
    await expectText(page, '.truthlens-live-status', 'Initial draft suggestions are ready for review');
    await page.waitForFunction(() => {
      const titleCard = Array.from(document.querySelectorAll('.truthlens-issue-card')).find((node) =>
        node.textContent?.includes('Title'),
      );
      const checkbox = titleCard?.querySelector('input[type="checkbox"]');
      const textarea = titleCard?.querySelector('textarea');
      return (
        checkbox instanceof HTMLInputElement &&
        checkbox.checked &&
        textarea instanceof HTMLTextAreaElement &&
        textarea.value.includes('overstates certainty')
      );
    });
    await page.waitForFunction(() => {
      const sections = Array.from(document.querySelectorAll('.truthlens-preview-section'));
      return sections.some((section) => {
        const title = section.querySelector('.truthlens-preview-section-title');
        return title?.textContent?.includes('Requested outcome');
      });
    });
    await page.getByRole('radio', { name: 'Yes' }).check();
    await page.getByRole('button', { name: 'Optimize comments' }).click();
    await expectText(
      page,
      '.truthlens-report-preview',
      'The video title presents an unverified allegation as established fact',
    );
    await expectText(
      page,
      '.truthlens-live-status',
      'Comment optimization completed and the preview was refreshed',
    );
    await page
      .locator('.truthlens-report-sheet')
      .getByRole('button', { name: 'Report' })
      .click();
    await expectText(
      page,
      '.truthlens-status-success',
      'Rapporten blev sendt via YouTubes indbyggede report-flow',
    );
    await expectText(page, '.truthlens-live-status', 'TruthLens feedback was stored locally');
    await page.waitForFunction(
      () => document.querySelector('.truthlens-report-sheet') === null,
      null,
      { timeout: 4000 },
    );
    assert.equal(suggestionRequests.length, 1);
    assert.equal(optimizationRequests.length, 1);
    assert.equal(youtubeReports.length, 1);
    assert.equal(feedbackEvents.length, 1);
    assert.equal(feedbackEvents[0].user_action, 'confirm-report');
    assert.equal(feedbackEvents[0].manual_report.optimize_applied, true);
    assert.deepEqual(youtubeReports[0].issue_types, [
      'thumbnail',
      'title',
      'description',
      'transcript',
      'channel',
      'other',
    ]);
    assert.equal(
      feedbackEvents[0].manual_report.issues.some((issue) => issue.issue_type === 'title'),
      true,
    );
    assert.match(
      feedbackEvents[0].manual_report.report_text,
      /unverified allegation as established fact/i,
    );
    assert.equal(
      await cards.nth(2).getAttribute('data-youtube-report-submitted'),
      'true',
    );
    const sentMessages = await page.evaluate(() => window.__truthlensSentMessages);
    assert.equal(sentMessages.length, 0);

    await page.evaluate(() => {
      const firstCard = document.querySelector('[data-truthlens-card]');
      if (!(firstCard instanceof HTMLElement)) {
        throw new Error('fixture first card missing');
      }
      const title = firstCard.querySelector('#video-title');
      const snippet = firstCard.querySelector('.metadata-snippet');
      if (!(title instanceof HTMLElement) || !(snippet instanceof HTMLElement)) {
        throw new Error('fixture first card content missing');
      }
      title.textContent = 'Weekly launch schedule and mission update';
      snippet.textContent = 'Routine mission planning and launch cadence update.';
    });

    await page.waitForFunction(() => {
      const firstCard = document.querySelector('[data-truthlens-card]');
      return (
        firstCard instanceof HTMLElement &&
        firstCard.getAttribute('data-truthlens-signature')?.includes('Weekly launch schedule') &&
        !firstCard.classList.contains('truthlens-card-blur') &&
        firstCard.getAttribute('data-truthlens-personalization') === 'steady' &&
        !firstCard.querySelector('.truthlens-card-flag')
      );
    });
    assert.equal(batchRequests, 2);
    assert.equal(await page.locator('.truthlens-action-row').count(), 0);
    assert.equal(
      await cards.nth(0).evaluate((element) => element.classList.contains('truthlens-card-blur')),
      false,
    );
    assert.equal(await cards.nth(0).getAttribute('data-truthlens-personalization'), 'steady');
    assert.equal(await cards.nth(0).evaluate((element) => element.style.order), '');
    assert.equal(await cards.nth(0).locator('.truthlens-card-flag').count(), 0);

    await page.evaluate(() => {
      const feed = document.querySelector('.feed');
      if (!(feed instanceof HTMLElement)) {
        throw new Error('fixture feed missing');
      }
      const article = document.createElement('article');
      article.setAttribute('data-truthlens-card', '');
      article.innerHTML = `
        <a id="thumbnail" href="/watch?v=fixture-item-4">
          <img alt="thumbnail four" src="https://example.com/thumb-4.jpg" />
        </a>
        <h3 id="video-title">Dynamic emergency update from orbit</h3>
        <div id="channel-name">Dynamic Signal Desk</div>
        <div class="metadata-snippet">Dynamic transcript with moderate mismatch for observer testing.</div>
      `;
      feed.appendChild(article);
    });

    await page.waitForFunction(
      () => document.querySelectorAll('[data-truthlens-processed="true"]').length === 4,
    );
    assert.equal(batchRequests, 3);
    assert.equal(await page.locator('#truthlens-overlay-root').count(), 1);
    assert.equal(await cards.nth(3).locator('.truthlens-card-flag').count(), 1);
    assert.equal(await cards.nth(3).getAttribute('data-truthlens-personalization'), 'steady');
    assert.equal(await cards.nth(3).evaluate((element) => element.style.order), '');
    assert.equal(await page.locator('.truthlens-action-row').count(), 0);

    console.log(
      JSON.stringify(
        {
          batchRequests,
          feedbackEvents: feedbackEvents.length,
          optimizationRequests: optimizationRequests.length,
          overlayRoots: await page.locator('#truthlens-overlay-root').count(),
          processedCards: await page.locator('[data-truthlens-processed="true"]').count(),
        },
        null,
        2,
      ),
    );
  } finally {
    await page.close();
    await browser.close();
    await new Promise((resolveClose) => server.close(resolveClose));
  }
}

async function expectText(page, selector, text) {
  await page.waitForFunction(
    ({ selector: nextSelector, text: nextText }) => {
      const node = document.querySelector(nextSelector);
      return node instanceof HTMLElement && node.textContent?.includes(nextText);
    },
    { selector, text },
  );
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
