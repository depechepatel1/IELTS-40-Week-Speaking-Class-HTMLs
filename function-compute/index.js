const CORS_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'POST, OPTIONS, GET',
  'Access-Control-Allow-Headers': 'Content-Type',
  'Content-Type': 'application/json'
};

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

  // Rate limit + Zhipu call live in the next tasks
  return respond(501, { error: '未实现 / Not implemented yet.' });
}

export default handler;
