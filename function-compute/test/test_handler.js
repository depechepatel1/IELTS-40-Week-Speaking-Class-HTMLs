import { test } from 'node:test';
import assert from 'node:assert/strict';
import { handler } from '../index.js';

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
