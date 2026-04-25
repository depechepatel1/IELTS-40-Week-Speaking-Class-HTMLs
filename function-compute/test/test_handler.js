import { test } from 'node:test';
import assert from 'node:assert/strict';
import { handler, __resetRateLimit } from '../index.js';

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
