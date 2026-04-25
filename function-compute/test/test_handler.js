import { test } from 'node:test';
import assert from 'node:assert/strict';
import { handler, __resetRateLimit, __setZhipuFetcher, __resetZhipuFetcher } from '../index.js';

function makeZhipuOk(text = 'Polished sentence here.') {
  return async () => ({
    ok: true,
    status: 200,
    json: async () => ({ choices: [{ message: { content: text } }] })
  });
}
function makeZhipuQuota() {
  return async () => ({
    ok: false,
    status: 429,
    json: async () => ({ error: { code: 1113, message: 'quota exhausted' } })
  });
}
function makeZhipuNetworkError() {
  return async () => { throw new Error('ECONNRESET'); };
}
function makeZhipuBadShape() {
  return async () => ({
    ok: true,
    status: 200,
    json: async () => ({ choices: [] })
  });
}

function ev(method, path = '/', body = null, headers = {}) {
  return {
    httpMethod: method,
    path,
    headers: { 'content-type': 'application/json', ...headers },
    body: body ? JSON.stringify(body) : null,
    clientIP: '203.0.113.1'
  };
}

test('OPTIONS preflight returns 204 with CORS headers', async () => {
  const res = await handler(ev('OPTIONS'));
  assert.equal(res.statusCode, 204);
  assert.equal(res.headers['Access-Control-Allow-Origin'], '*');
  assert.match(res.headers['Access-Control-Allow-Methods'], /POST/);
  assert.match(res.headers['Access-Control-Allow-Methods'], /OPTIONS/);
  assert.match(res.headers['Access-Control-Allow-Headers'], /Content-Type/i);
});

test('GET /health returns 200 ok:true with CORS', async () => {
  const res = await handler(ev('GET', '/health'));
  assert.equal(res.statusCode, 200);
  assert.equal(res.headers['Access-Control-Allow-Origin'], '*');
  const body = JSON.parse(res.body);
  assert.equal(body.ok, true);
});

test('GET / (no body, not health) returns 405', async () => {
  const res = await handler(ev('GET', '/'));
  assert.equal(res.statusCode, 405);
});

test('POST with missing body returns 400 invalid format', async () => {
  const res = await handler({ httpMethod: 'POST', path: '/', headers: {}, body: null });
  assert.equal(res.statusCode, 400);
  const body = JSON.parse(res.body);
  assert.match(body.error, /请求格式|Invalid request/);
});

test('POST with non-string draft returns 400 invalid format', async () => {
  const res = await handler(ev('POST', '/', { draft: 12345 }));
  assert.equal(res.statusCode, 400);
});

test('POST with too-short draft (5 words) returns 400 with bilingual min message', async () => {
  const res = await handler(ev('POST', '/', { draft: 'one two three four five' }));
  assert.equal(res.statusCode, 400);
  const body = JSON.parse(res.body);
  assert.match(body.error, /至少写 50/);
  assert.match(body.error, /at least 50 words/i);
  assert.match(body.error, /Currently 5/);
});

test('POST with too-long draft (200 words) returns 400 with bilingual max message', async () => {
  const longDraft = 'word '.repeat(200).trim();
  const res = await handler(ev('POST', '/', { draft: longDraft }));
  assert.equal(res.statusCode, 400);
  const body = JSON.parse(res.body);
  assert.match(body.error, /150 个词以内/);
  assert.match(body.error, /under 150 words/i);
});

test('a 49-word draft is rejected', async () => {
  const fortyNine = 'word '.repeat(49).trim();
  const res = await handler(ev('POST', '/', { draft: fortyNine }));
  assert.equal(res.statusCode, 400);
});

test('rate limit: 30 reqs from same IP all OK in window', async () => {
  __resetRateLimit();
  const draft = 'word '.repeat(50).trim();
  for (let i = 0; i < 30; i++) {
    const res = await handler(ev('POST', '/', { draft }, { 'x-forwarded-for': '198.51.100.1' }));
    assert.notEqual(res.statusCode, 429, `Request ${i+1} should not be rate-limited`);
  }
});

test('rate limit: 31st request from same IP returns 429', async () => {
  __resetRateLimit();
  const draft = 'word '.repeat(50).trim();
  for (let i = 0; i < 30; i++) {
    await handler(ev('POST', '/', { draft }, { 'x-forwarded-for': '198.51.100.2' }));
  }
  const res = await handler(ev('POST', '/', { draft }, { 'x-forwarded-for': '198.51.100.2' }));
  assert.equal(res.statusCode, 429);
  const body = JSON.parse(res.body);
  assert.match(body.error, /稍后再试/);
  assert.match(body.error, /Rate limit/i);
  assert.match(body.error, /30/);
});

test('rate limit: distinct IPs get distinct buckets', async () => {
  __resetRateLimit();
  const draft = 'word '.repeat(50).trim();
  for (let i = 0; i < 30; i++) {
    await handler(ev('POST', '/', { draft }, { 'x-forwarded-for': '198.51.100.3' }));
  }
  const res = await handler(ev('POST', '/', { draft }, { 'x-forwarded-for': '198.51.100.4' }));
  assert.notEqual(res.statusCode, 429);
});

test('happy path: Zhipu returns corrected text', async () => {
  __resetRateLimit();
  __setZhipuFetcher(makeZhipuOk('I went to the park.'));
  const res = await handler(ev('POST', '/', { draft: 'word '.repeat(50).trim() }));
  __resetZhipuFetcher();
  assert.equal(res.statusCode, 200);
  const body = JSON.parse(res.body);
  assert.equal(body.corrected, 'I went to the park.');
});

test('Zhipu quota exhausted → 503 bilingual quota message', async () => {
  __resetRateLimit();
  __setZhipuFetcher(makeZhipuQuota());
  const res = await handler(ev('POST', '/', { draft: 'word '.repeat(50).trim() }));
  __resetZhipuFetcher();
  assert.equal(res.statusCode, 503);
  const body = JSON.parse(res.body);
  assert.match(body.error, /AI 今日额度已用完/);
  assert.match(body.error, /quota exhausted today/i);
});

test('Zhipu network error → 503 service unavailable', async () => {
  __resetRateLimit();
  __setZhipuFetcher(makeZhipuNetworkError());
  const res = await handler(ev('POST', '/', { draft: 'word '.repeat(50).trim() }));
  __resetZhipuFetcher();
  assert.equal(res.statusCode, 503);
  const body = JSON.parse(res.body);
  assert.match(body.error, /AI 服务暂时不可用|service temporarily unavailable/i);
});

test('Zhipu bad shape → 500 unexpected response', async () => {
  __resetRateLimit();
  __setZhipuFetcher(makeZhipuBadShape());
  const res = await handler(ev('POST', '/', { draft: 'word '.repeat(50).trim() }));
  __resetZhipuFetcher();
  assert.equal(res.statusCode, 500);
  const body = JSON.parse(res.body);
  assert.match(body.error, /AI 返回了意外的响应|unexpected response/i);
});

test('Zhipu request shape: posts JSON with system+user messages, model, temp 0.3, max_tokens 500', async () => {
  __resetRateLimit();
  let captured = null;
  __setZhipuFetcher(async (url, opts) => {
    captured = { url, opts };
    return { ok: true, status: 200, json: async () => ({ choices: [{ message: { content: 'ok' } }] }) };
  });
  await handler(ev('POST', '/', { draft: 'word '.repeat(50).trim() }));
  __resetZhipuFetcher();

  assert.equal(captured.url, 'https://open.bigmodel.cn/api/paas/v4/chat/completions');
  assert.equal(captured.opts.method, 'POST');
  assert.match(captured.opts.headers.Authorization, /^Bearer /);
  const body = JSON.parse(captured.opts.body);
  assert.ok(body.model, 'model is set');
  assert.equal(body.temperature, 0.3);
  assert.equal(body.max_tokens, 500);
  assert.equal(body.messages.length, 2);
  assert.equal(body.messages[0].role, 'system');
  assert.match(body.messages[0].content, /minimum changes needed/i);
  assert.equal(body.messages[1].role, 'user');
});
