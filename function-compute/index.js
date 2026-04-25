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

  // POST handling lives in subsequent tasks
  return respond(501, { error: '未实现 / Not implemented yet.' });
}

export default handler;
