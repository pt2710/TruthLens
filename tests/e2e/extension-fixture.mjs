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
    };
  }
  if (item.title.includes('Weekly launch schedule')) {
    return {
      risk_score: 0.18,
      confidence: 0.81,
      uncertainty: 0.19,
      recommended_action: 'none',
      reasons: [],
    };
  }
  if (item.title.includes('Secret lab leak')) {
    return {
      risk_score: 0.83,
      confidence: 0.91,
      uncertainty: 0.09,
      recommended_action: 'ask-report',
      reasons: ['Risk score crossed the report-prompt threshold.'],
    };
  }
  return {
    risk_score: 0.44,
    confidence: 0.79,
    uncertainty: 0.21,
    recommended_action: 'badge',
    reasons: ['Dynamic card entered the moderate-risk review band.'],
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
  let batchRequests = 0;
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  try {
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
    assert.equal(await page.locator('.truthlens-action-row').count(), 3);

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
    assert.equal(
      await cards.nth(2).locator('.truthlens-card-flag').textContent(),
      'TruthLens: ask-report',
    );

    await cards.nth(0).getByRole('button', { name: 'Why' }).click();
    await page.waitForFunction(() => {
      const details = document.querySelector('.truthlens-details');
      return details instanceof HTMLElement && details.hidden === false;
    });

    await cards.nth(2).getByRole('button', { name: 'Report' }).click();
    await cards.nth(0).getByRole('button', { name: 'Hide' }).click();
    await page.waitForTimeout(50);
    assert.equal(feedbackEvents.length, 2);
    assert.equal(feedbackEvents[0].user_action, 'report');
    assert.equal(feedbackEvents[1].user_action, 'hide-locally');
    assert.equal(
      await cards.nth(0).evaluate((element) => element.classList.contains('truthlens-card-hidden')),
      true,
    );

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
    assert.equal(batchRequests, 2);
    assert.equal(await page.locator('#truthlens-overlay-root').count(), 1);
    assert.equal(await cards.nth(3).locator('.truthlens-card-flag').count(), 1);
    assert.equal(await page.locator('.truthlens-action-row').count(), 4);

    console.log(
      JSON.stringify(
        {
          batchRequests,
          feedbackEvents: feedbackEvents.length,
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

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
