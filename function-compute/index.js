const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS, GET',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json'
};

// In-memory rate limiter — Map<ip, { count, windowStart }>.
// Resets when the FC instance recycles, which is acceptable per spec §5.4.
const RATE_LIMIT = new Map();
const RATE_LIMIT_MAX = 30;
const RATE_LIMIT_WINDOW_MS = 60 * 60 * 1000;

export function __resetRateLimit() {
  RATE_LIMIT.clear();
}

function getClientIP(event) {
  const xff = event.headers?.['x-forwarded-for'] || event.headers?.['X-Forwarded-For'];
  if (xff) return xff.split(',')[0].trim();
  return event.clientIP || event.requestContext?.identity?.sourceIp || 'unknown';
}

function checkRateLimit(ip) {
  const now = Date.now();
  const entry = RATE_LIMIT.get(ip);
  if (!entry || now - entry.windowStart > RATE_LIMIT_WINDOW_MS) {
    RATE_LIMIT.set(ip, { count: 1, windowStart: now });
    return { ok: true };
  }
  if (entry.count >= RATE_LIMIT_MAX) {
    return { ok: false };
  }
  entry.count += 1;
  return { ok: true };
}

function respond(statusCode, body) {
  return {
    statusCode,
    headers: { ...CORS_HEADERS },
    body: typeof body === 'string' ? body : JSON.stringify(body)
  };
}

export async function handler(event) {
  const method = (event.httpMethod || event.method || '').toUpperCase();
  const path = event.path || event.rawPath || '/';

  if (method === 'OPTIONS') {
    return { statusCode: 204, headers: { ...CORS_HEADERS }, body: '' };
  }

  if (method === 'GET' && path === '/health') {
    return respond(200, { ok: true });
  }

  if (method !== 'POST') {
    return respond(405, { error: '方法不允许 / Method not allowed.' });
  }

  // ---- POST handling ----
  let parsed;
  try {
    parsed = JSON.parse(event.body || '{}');
  } catch {
    return respond(400, { error: '请求格式错误 / Invalid request format.' });
  }

  const draft = parsed.draft;
  if (typeof draft !== 'string') {
    return respond(400, { error: '请求格式错误 / Invalid request format.' });
  }

  const words = draft.trim().split(/\s+/).filter(Boolean);
  const n = words.length;

  if (n < 50) {
    return respond(400, {
      error: `请至少写 50 个词 / Please write at least 50 words. (Currently ${n})`
    });
  }
  if (n > 150) {
    return respond(400, {
      error: `请控制在 150 个词以内 / Please keep it under 150 words. (Currently ${n})`
    });
  }

  const ip = getClientIP(event);
  const rl = checkRateLimit(ip);
  if (!rl.ok) {
    return respond(429, {
      error: '请稍后再试，每小时最多 30 次 / Rate limit reached. Max 30 requests per hour.'
    });
  }

  // Zhipu call lives in the next task
  return respond(501, { error: '未实现 / Not implemented yet.' });
}

export default handler;
