// CORS headers are added automatically by Aliyun FC's HTTP-trigger gateway
// (it echoes the request Origin into Access-Control-Allow-Origin and adds
// Access-Control-Allow-Credentials: true). Setting our own ACAO causes a
// duplicate-header error in browsers ("only one is allowed"). So we ONLY
// set Content-Type and let FC handle the CORS preamble.
const CORS_HEADERS = {
  'Content-Type': 'application/json'
};

// Zhipu integration — model resolved at deploy time per spec §5.8.1.
const ZHIPU_MODEL_ID = process.env.ZHIPU_MODEL_ID || 'glm-4.7-flash';
const ZHIPU_URL = 'https://open.bigmodel.cn/api/paas/v4/chat/completions';
const SYSTEM_PROMPT = `You are a careful English teacher correcting a 14-16 year old Chinese student's
short written answer (50-300 words) for an IELTS speaking lesson.

Make the MINIMUM changes needed for the writing to be grammatically correct and
to use words correctly. Your job is correction, not enhancement.

Fix:
- Grammar errors (verb tense, articles, subject-verb agreement, prepositions,
  word order, plurals, capitalization, punctuation)
- Spelling
- Wrong word choice ONLY when a word is genuinely incorrect (mistranslation,
  wrong sense, non-existent word)

Word-form preference: when fixing a word form, prefer the correction that
shares the most letters with the student's original word. For example:
"tired" used as adjective → "tiring" (NOT "exhausting"); "smooth" used
adverbially → "smoothly" (NOT "in a smooth manner"); "heavy" used
adverbially → "heavily" (NOT "intensely"). Stem-preserving corrections
look like minimal teacher edits.

Do NOT:
- Replace words that are already correct, even if simple or basic
- Add new ideas, examples, details, opinions, or sentences not in the student's draft
- Delete the student's ideas
- Restructure sentences unless grammar requires it
- Change length by more than 20 words from the student's original

Two STRUCTURAL requirements every corrected draft must satisfy. If the
student's draft already meets a requirement, leave it untouched.

1. AT LEAST ONE complex sentence with a subordinating conjunction OTHER
   than "because". If the corrected draft has none, JOIN two adjacent
   simple sentences (with a logical relationship) by:
     - Replace the period+space between them with ", " + the most fitting
       subordinating conjunction from this list + " ":
       while, although, even though, since, after, as soon as, before,
       until, whenever, if, even if, unless, provided that, so that,
       in order that, in order to
     - Lowercase the first letter of the second sentence after the join
   DO NOT rewrite the sentences themselves. Only the period→conjunction
   substitution + lowercasing.

2. AT LEAST TWO transition phrases (e.g. "However,", "In addition,",
   "Therefore,", "For example,", "Moreover,", "Finally,", "In conclusion,",
   "Nevertheless,", "As a result,", "Meanwhile,", "On the other hand,").
   If the corrected draft has fewer than 2, prepend a fitting transition
   to the start of a suitable existing sentence — format: "Transition, "
   followed by the lowercased first letter of that sentence.
   DO NOT rewrite the sentence itself. Only insert at sentence starts.

Return ONLY the corrected text as plain prose. No preamble, no markdown,
no commentary, no quotes, no bullet points.`;

// Injectable for tests — production path uses native fetch.
let _zhipuFetcher = (url, opts) => fetch(url, opts);
export function __setZhipuFetcher(fn) { _zhipuFetcher = fn; }
export function __resetZhipuFetcher() { _zhipuFetcher = (url, opts) => fetch(url, opts); }

// === AI correction cache (in-memory LRU) =====================================
// At start-of-class scale (200+ students within minutes), many drafts collide
// on common errors ("I am go to school", "He don't like…", canned shadowing
// phrases). Caching the corrected output keyed by hash(normalized_draft)
// short-circuits the Zhipu round-trip entirely on a hit (~2-3s saved + 1
// Zhipu API call avoided).
//
// Why in-memory and not Redis/OSS: FC instances stay warm during traffic
// spikes, which is the exact window where cache hit-rate matters most. When
// the instance recycles after idle, the cache resets — that's fine, the
// next class will warm it up again. No external service to provision, no
// extra latency, no extra ops surface.
//
// LRU via JS Map insertion-order: on hit we delete + re-set so the key
// lands at the end (most-recent). When size cap reached, delete the first
// entry (oldest). O(1) per op.
//
// Privacy note: cache keys are the normalized draft text itself. Two
// students typing literally identical 50-300-word drafts is vanishingly
// rare in practice; in the unlikely event it happens, the second student
// receives the same grammar correction the first received. No personal
// information flows between students because the cached value is just
// the corrected sentence the second student would have received anyway.
const AI_CACHE_MAX = 1000;
const _aiCache = new Map();

import { createHash } from 'node:crypto';

function _normalizeForCache(draft) {
  return draft.trim().replace(/\s+/g, ' ').toLowerCase();
}

function _aiCacheKey(draft) {
  return createHash('sha256').update(_normalizeForCache(draft)).digest('hex');
}

function aiCacheGet(draft) {
  const k = _aiCacheKey(draft);
  if (!_aiCache.has(k)) return null;
  const v = _aiCache.get(k);
  // Bump to most-recent.
  _aiCache.delete(k);
  _aiCache.set(k, v);
  return v;
}

function aiCacheSet(draft, corrected) {
  const k = _aiCacheKey(draft);
  if (_aiCache.has(k)) _aiCache.delete(k);
  _aiCache.set(k, corrected);
  // Evict oldest until under cap.
  while (_aiCache.size > AI_CACHE_MAX) {
    const firstKey = _aiCache.keys().next().value;
    _aiCache.delete(firstKey);
  }
}

// Test hooks — allow unit tests to inspect / reset the cache.
export function __resetAICache() { _aiCache.clear(); }
export function __aiCacheSize() { return _aiCache.size; }
// =============================================================================

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
      // GLM-4.7+ models default to thinking/CoT mode, which can consume the
      // entire max_tokens budget on reasoning and leave `content` empty,
      // tripping the "unexpected response" branch below. We don't need
      // chain-of-thought for grammar correction — disable it.
      // (Older models like glm-4-flash ignore this field.)
      thinking: { type: 'disabled' },
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
  // Strip markdown leakage. Despite the system prompt saying "no markdown",
  // Zhipu sometimes wraps transition phrases in **bold** (e.g.
  // "**However,** the food was great"). The diff engine treats `**` as
  // literal characters and renders them as garbage in the corrected output.
  // Sanitise here so cached responses also get the clean version.
  const sanitised = content
    .trim()
    // Bold: **text** -> text (greedy match within asterisks)
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    // Stray paired asterisks at sentence boundaries (rare but seen)
    .replace(/(^|\s)\*\*(\s|$)/g, '$1$2')
    // Any remaining lone ** (defensive; should be 0 after the above)
    .replace(/\*\*/g, '')
    // Italic: *text* -> text (only when wrapping a word, avoid arithmetic)
    .replace(/(^|\s)\*([^\s*][^*]*[^\s*]|[^\s*])\*(\s|$|[.,!?;:])/g, '$1$2$3')
    // Markdown headings / list bullets at line starts (defensive)
    .replace(/^[#\-*]\s+/gm, '')
    .trim();
  return { ok: true, corrected: sanitised };
}

// In-memory rate limiter — Map<ip, { count, windowStart }>.
// Resets when the FC instance recycles, which is acceptable per spec §5.4.
const RATE_LIMIT = new Map();
const RATE_LIMIT_MAX = 30;
const RATE_LIMIT_WINDOW_MS = 60 * 60 * 1000;

export function __resetRateLimit() {
  RATE_LIMIT.clear();
}

function getClientIP(reqLike) {
  const headers = reqLike.headers || {};
  const xff = headers['x-forwarded-for'] || headers['X-Forwarded-For'];
  if (xff) return xff.split(',')[0].trim();
  return reqLike.clientIP || reqLike.requestContext?.identity?.sourceIp || 'unknown';
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

/**
 * Pure request processor — invocation-style-agnostic.
 * Takes a normalized request, returns { statusCode, headers, body }.
 *
 * Test entry point. Adapters below translate from FC v3 (req, resp) and
 * legacy (event) shapes into this signature.
 */
export async function processRequest({ method, path, headers, body, clientIP }) {
  const m = (method || '').toUpperCase();
  const p = path || '/';

  if (m === 'OPTIONS') {
    return { statusCode: 204, headers: { ...CORS_HEADERS }, body: '' };
  }

  if (m === 'GET' && p === '/health') {
    return respond(200, { ok: true });
  }

  if (m !== 'POST') {
    return respond(405, { error: '方法不允许 / Method not allowed.' });
  }

  let parsed;
  try {
    parsed = JSON.parse(body || '{}');
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
  if (n > 300) {
    return respond(400, {
      error: `请控制在 300 个词以内 / Please keep it under 300 words. (Currently ${n})`
    });
  }

  const ip = getClientIP({ headers, clientIP });
  const rl = checkRateLimit(ip);
  if (!rl.ok) {
    return respond(429, {
      error: '请稍后再试，每小时最多 30 次 / Rate limit reached. Max 30 requests per hour.'
    });
  }

  // Cache check BEFORE Zhipu — if another student (or this same student
  // re-clicking Correct) submitted the same draft recently, return the
  // cached result instantly. Saves ~2-3s + 1 Zhipu API call per hit.
  const cached = aiCacheGet(draft);
  if (cached !== null) {
    return respond(200, { corrected: cached, cached: true });
  }

  const result = await callZhipu(draft);
  if (!result.ok) {
    return respond(result.status, { error: result.error });
  }
  // Populate cache on success only — never cache error responses (those
  // might be transient: rate limits, quota exhausted, network blips).
  aiCacheSet(draft, result.corrected);
  return respond(200, { corrected: result.corrected });
}

/**
 * Legacy event-style adapter (kept for compatibility / older tests).
 * Tests call this with `{httpMethod, path, headers, body, clientIP}`.
 */
export async function handler(event) {
  return processRequest({
    method: event.httpMethod || event.method,
    path: event.path || event.rawPath,
    headers: event.headers,
    body: event.body,
    clientIP: event.clientIP
  });
}

/**
 * Aliyun Function Compute v3 HTTP-trigger adapter (event-style).
 *
 * FC v3 invokes HTTP-trigger functions with `(event, context)` where the
 * event shape resembles AWS Lambda HTTP API v2:
 *
 *   event.rawPath                                  — request path
 *   event.body                                     — string (or base64 if isBase64Encoded)
 *   event.isBase64Encoded                          — bool
 *   event.headers                                  — lowercase keys
 *   event.requestContext.http.method               — HTTP method
 *   event.requestContext.http.sourceIp             — client IP
 *
 * The function must return `{ statusCode, headers, body, isBase64Encoded? }`.
 * This is the runtime entry point — do NOT rename without updating s.yaml's `handler:`.
 */
export const fc = async (event /*, context */) => {
  // FC v3 HTTP-trigger nodejs runtime delivers `event` as a Buffer (or string) holding
  // a JSON document with the AWS-Lambda-HTTP-API-v2-shaped event. Parse it.
  let parsed;
  if (Buffer.isBuffer(event)) {
    parsed = JSON.parse(event.toString('utf8'));
  } else if (typeof event === 'string') {
    parsed = JSON.parse(event);
  } else {
    parsed = event; // tests pass an already-parsed object
  }

  // Headers come back Title-Cased from FC; normalize to lowercase for stable lookup.
  const rawHeaders = parsed.headers || {};
  const headers = {};
  for (const [k, v] of Object.entries(rawHeaders)) headers[k.toLowerCase()] = v;

  let bodyString = '';
  if (parsed.body !== undefined && parsed.body !== null) {
    if (parsed.isBase64Encoded) {
      bodyString = Buffer.from(parsed.body, 'base64').toString('utf8');
    } else if (Buffer.isBuffer(parsed.body)) {
      bodyString = parsed.body.toString('utf8');
    } else if (typeof parsed.body === 'string') {
      bodyString = parsed.body;
    } else {
      bodyString = JSON.stringify(parsed.body);
    }
  }

  const result = await processRequest({
    method:
      parsed.requestContext?.http?.method ||
      parsed.httpMethod ||
      parsed.method,
    path:
      parsed.rawPath ||
      parsed.requestContext?.http?.path ||
      parsed.path ||
      '/',
    headers,
    body: bodyString,
    clientIP:
      parsed.requestContext?.http?.sourceIp ||
      (headers['x-forwarded-for'] || '').split(',')[0].trim() ||
      parsed.clientIP ||
      ''
  });

  return {
    statusCode: result.statusCode,
    headers: result.headers || {},
    body: result.body || '',
    isBase64Encoded: false
  };
};

export default fc;
