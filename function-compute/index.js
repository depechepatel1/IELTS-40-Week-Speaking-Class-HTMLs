const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS, GET',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json'
};

// Zhipu integration — model resolved at deploy time per spec §5.8.1.
const ZHIPU_MODEL_ID = process.env.ZHIPU_MODEL_ID || 'glm-4.7-flash';
const ZHIPU_URL = 'https://open.bigmodel.cn/api/paas/v4/chat/completions';
const SYSTEM_PROMPT = `You are a careful English teacher correcting a 14-16 year old Chinese student's
short written answer (50-150 words) for an IELTS speaking lesson.

Make the MINIMUM changes needed for the writing to be grammatically correct and
to use words correctly. Your job is correction, not enhancement.

Fix:
- Grammar errors (verb tense, articles, subject-verb agreement, prepositions,
  word order, plurals, capitalization, punctuation)
- Spelling
- Wrong word choice ONLY when a word is genuinely incorrect (mistranslation,
  wrong sense, non-existent word)

Do NOT:
- Replace words that are already correct, even if simple or basic
- Add new ideas, examples, details, opinions, or sentences not in the student's draft
- Delete the student's ideas
- Restructure sentences unless grammar requires it
- Change length by more than 10 words from the student's original

Return ONLY the corrected text as plain prose. No preamble, no markdown,
no commentary, no quotes, no bullet points.`;

// Injectable for tests — production path uses native fetch.
let _zhipuFetcher = (url, opts) => fetch(url, opts);
export function __setZhipuFetcher(fn) { _zhipuFetcher = fn; }
export function __resetZhipuFetcher() { _zhipuFetcher = (url, opts) => fetch(url, opts); }

function isZhipuQuotaError(parsed) {
  if (!parsed) return false;
  const code = parsed.error?.code;
  if (code === 1113 || code === 1301) return true;
  const msg = (parsed.error?.message || '').toLowerCase();
  return msg.includes('quota') || msg.includes('limit') || msg.includes('余额');
}

async function callZhipu(draft) {
  const apiKey = process.env.ZHIPU_API_KEY;
  if (!apiKey) {
    return { ok: false, status: 503, error: 'AI 服务暂时不可用 / AI service temporarily unavailable.' };
  }
  const requestOpts = {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${apiKey}`
    },
    body: JSON.stringify({
      model: ZHIPU_MODEL_ID,
      temperature: 0.3,
      max_tokens: 500,
      messages: [
        { role: 'system', content: SYSTEM_PROMPT },
        { role: 'user', content: draft }
      ]
    })
  };

  // Spec §5.7: one retry on network errors with 500ms delay. Quota errors are NOT retried.
  let upstream;
  try {
    upstream = await _zhipuFetcher(ZHIPU_URL, requestOpts);
  } catch {
    await new Promise(r => setTimeout(r, 500));
    try {
      upstream = await _zhipuFetcher(ZHIPU_URL, requestOpts);
    } catch {
      return { ok: false, status: 503, error: 'AI 服务暂时不可用 / AI service temporarily unavailable.' };
    }
  }

  let parsed;
  try { parsed = await upstream.json(); } catch { parsed = null; }

  if (!upstream.ok) {
    if (isZhipuQuotaError(parsed)) {
      return { ok: false, status: 503, error: 'AI 今日额度已用完，请明天再试 / AI quota exhausted today. Try again tomorrow.' };
    }
    return { ok: false, status: 503, error: 'AI 服务出错，请稍后再试 / AI service error. Please try later.' };
  }

  const content = parsed?.choices?.[0]?.message?.content;
  if (typeof content !== 'string' || !content.trim()) {
    return { ok: false, status: 500, error: 'AI 返回了意外的响应 / AI returned an unexpected response.' };
  }
  return { ok: true, corrected: content.trim() };
}

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

  // Opportunistic pruning so a long-lived FC instance doesn't accumulate stale entries forever.
  if (RATE_LIMIT.size > 100) {
    for (const [k, v] of RATE_LIMIT) {
      if (now - v.windowStart > RATE_LIMIT_WINDOW_MS) RATE_LIMIT.delete(k);
    }
  }

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

  const result = await callZhipu(draft);
  if (!result.ok) {
    return respond(result.status, { error: result.error });
  }
  return respond(200, { corrected: result.corrected });
}

export default handler;
