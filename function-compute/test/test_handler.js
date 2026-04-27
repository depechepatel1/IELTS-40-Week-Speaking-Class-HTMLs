import { test } from 'node:test';
import assert from 'node:assert/strict';
import { handler, fc, __resetRateLimit, __setZhipuFetcher, __resetZhipuFetcher } from '../index.js';

// Build a mock FC v3 HTTP-trigger event (AWS-Lambda-HTTPv2-shaped).
function fcEvent(method, path = '/', body = null, extraHeaders = {}) {
  return {
    version: 'v1',
    rawPath: path,
    body: body == null ? null : (typeof body === 'string' ? body : JSON.stringify(body)),
    isBase64Encoded: false,
    headers: { 'content-type': 'application/json', ...extraHeaders },
    queryParameters: {},
    requestContext: {
      http: {
        method,
        path,
        protocol: 'HTTP/1.1',
        sourceIp: '203.0.113.1',
        userAgent: 'test'
      }
    }
  };
}

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

test('OPTIONS preflight returns 204 with empty body (CORS added by FC gateway)', async () => {
  const res = await handler(ev('OPTIONS'));
  assert.equal(res.statusCode, 204);
  assert.equal(res.body, '');
  // We deliberately do NOT set Access-Control-Allow-Origin — Aliyun FC's
  // HTTP-trigger gateway adds it automatically by echoing the request
  // Origin header. Setting it ourselves caused a duplicate-header error
  // in browsers ("only one is allowed").
  assert.equal(res.headers['Access-Control-Allow-Origin'], undefined);
});

test('GET /health returns 200 ok:true', async () => {
  const res = await handler(ev('GET', '/health'));
  assert.equal(res.statusCode, 200);
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

test('POST with too-long draft (350 words) returns 400 with bilingual max message', async () => {
  const longDraft = 'word '.repeat(350).trim();
  const res = await handler(ev('POST', '/', { draft: longDraft }));
  assert.equal(res.statusCode, 400);
  const body = JSON.parse(res.body);
  assert.match(body.error, /300 个词以内/);
  assert.match(body.error, /under 300 words/i);
});

test('a 49-word draft is rejected', async () => {
  const fortyNine = 'word '.repeat(49).trim();
  const res = await handler(ev('POST', '/', { draft: fortyNine }));
  assert.equal(res.statusCode, 400);
});

test('a 300-word draft is accepted (boundary, passes validation)', async () => {
  __resetRateLimit();
  __setZhipuFetcher(async () => ({ ok: true, status: 200, json: async () => ({ choices: [{ message: { content: 'ok' } }] }) }));
  const exactly300 = 'word '.repeat(300).trim();
  const res = await handler(ev('POST', '/', { draft: exactly300 }));
  __resetZhipuFetcher();
  assert.equal(res.statusCode, 200);
});

test('a 301-word draft is rejected (boundary)', async () => {
  __resetRateLimit();
  const res = await handler(ev('POST', '/', { draft: 'word '.repeat(301).trim() }));
  assert.equal(res.statusCode, 400);
  assert.match(JSON.parse(res.body).error, /Currently 301/);
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

test('Zhipu network error → 503 service unavailable (after retry)', async () => {
  __resetRateLimit();
  __setZhipuFetcher(makeZhipuNetworkError());
  const res = await handler(ev('POST', '/', { draft: 'word '.repeat(50).trim() }));
  __resetZhipuFetcher();
  assert.equal(res.statusCode, 503);
  const body = JSON.parse(res.body);
  assert.match(body.error, /AI 服务暂时不可用|service temporarily unavailable/i);
});

test('FC v3 adapter: OPTIONS returns 204 with empty body (CORS added by gateway)', async () => {
  const r = await fc(fcEvent('OPTIONS'));
  assert.equal(r.statusCode, 204);
  assert.equal(r.body, '');
  assert.equal(r.headers['Access-Control-Allow-Origin'], undefined);
});

test('FC v3 adapter: GET /health returns 200 ok:true', async () => {
  const r = await fc(fcEvent('GET', '/health'));
  assert.equal(r.statusCode, 200);
  assert.equal(JSON.parse(r.body).ok, true);
});

test('FC v3 adapter: POST too-short returns 400 bilingual', async () => {
  __resetRateLimit();
  const r = await fc(fcEvent('POST', '/', { draft: 'one two three four five' }));
  assert.equal(r.statusCode, 400);
  assert.match(JSON.parse(r.body).error, /至少写 50/);
});

test('FC v3 adapter: base64-encoded body is decoded', async () => {
  __resetRateLimit();
  const e = fcEvent('POST', '/', null);
  e.body = Buffer.from(JSON.stringify({ draft: 'too short' }), 'utf8').toString('base64');
  e.isBase64Encoded = true;
  const r = await fc(e);
  assert.equal(r.statusCode, 400);
  assert.match(JSON.parse(r.body).error, /至少写 50/);
});

test('FC v3 adapter: clientIP comes from requestContext.http.sourceIp', async () => {
  __resetRateLimit();
  const e = fcEvent('POST', '/', { draft: 'word '.repeat(50).trim() });
  e.requestContext.http.sourceIp = '198.51.100.99';
  __setZhipuFetcher(async () => ({ ok: true, status: 200, json: async () => ({ choices: [{ message: { content: 'ok' } }] }) }));
  const r = await fc(e);
  __resetZhipuFetcher();
  assert.equal(r.statusCode, 200);
});

test('FC v3 adapter: parses Buffer-of-JSON event (real runtime shape)', async () => {
  __resetRateLimit();
  const eventObj = fcEvent('POST', '/', { draft: 'one two three four five' });
  const eventBuffer = Buffer.from(JSON.stringify(eventObj), 'utf8');
  const r = await fc(eventBuffer);
  assert.equal(r.statusCode, 400);
  assert.match(JSON.parse(r.body).error, /至少写 50/);
});

test('FC v3 adapter: parses string event', async () => {
  __resetRateLimit();
  const eventObj = fcEvent('GET', '/health');
  const r = await fc(JSON.stringify(eventObj));
  assert.equal(r.statusCode, 200);
  assert.equal(JSON.parse(r.body).ok, true);
});

test('FC v3 adapter: Title-Cased headers normalize to lowercase', async () => {
  __resetRateLimit();
  const e = fcEvent('POST', '/', { draft: 'word '.repeat(50).trim() });
  // FC actually sends Title-Cased headers; simulate
  e.headers = { 'Content-Type': 'application/json', 'X-Forwarded-For': '198.51.100.50, 10.0.0.1' };
  e.requestContext.http.sourceIp = ''; // force the X-Forwarded-For path
  __setZhipuFetcher(async () => ({ ok: true, status: 200, json: async () => ({ choices: [{ message: { content: 'ok' } }] }) }));
  const r = await fc(e);
  __resetZhipuFetcher();
  assert.equal(r.statusCode, 200, 'X-Forwarded-For should still be readable after lowercase normalization');
});

test('Zhipu transient network error: succeeds on retry (spec §5.7)', async () => {
  __resetRateLimit();
  let calls = 0;
  __setZhipuFetcher(async () => {
    calls += 1;
    if (calls === 1) throw new Error('ECONNRESET');
    return { ok: true, status: 200, json: async () => ({ choices: [{ message: { content: 'retried ok' } }] }) };
  });
  const res = await handler(ev('POST', '/', { draft: 'word '.repeat(50).trim() }));
  __resetZhipuFetcher();
  assert.equal(res.statusCode, 200);
  assert.equal(calls, 2, 'must retry exactly once');
  assert.equal(JSON.parse(res.body).corrected, 'retried ok');
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
