const http = require('http');
const https = require('https');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const PORT = 3001;
const SECRETS_FILE = process.env.HOME + '/.secrets/ghost_keys.txt';
const GHOST_API = 'http://127.0.0.1:2368';
const GHOST_URL = 'https://alfredstudio.mooo.com/blog';

// Read API key from secrets file
function readApiKey() {
  try {
    const content = fs.readFileSync(SECRETS_FILE, 'utf-8');
    // Staff key (contourne la limitation des integrations) ou cle integration
    const match = content.match(/GHOST_ADMIN_API_KEY_(STAFF|INTEGRATION)=([a-f0-9]+:[a-f0-9]+)/);
    if (match) return match[2];
  } catch (e) {
    console.error('Secrets file not found:', e.message);
  }
  return null;
}

// Generate Ghost Admin API JWT
// The key format is "id:secret" where:
//   id = key ID (used as kid in JWT header)
//   secret = hex-encoded HMAC key
function generateJWT(apiKey) {
  const [id, secretHex] = apiKey.split(':');
  if (!id || !secretHex) throw new Error('Invalid API key format');
  
  const secret = Buffer.from(secretHex, 'hex');
  const now = Math.floor(Date.now() / 1000);
  
  const header = { alg: 'HS256', typ: 'JWT', kid: id };
  const payload = {
    iat: now,
    exp: now + 5 * 60, // 5 minutes
    aud: '/admin/'
  };
  
  const base64 = (obj) => Buffer.from(JSON.stringify(obj)).toString('base64url');
  const signature = crypto.createHmac('sha256', secret)
    .update(base64(header) + '.' + base64(payload))
    .digest('base64url');
  
  return 'Ghost ' + base64(header) + '.' + base64(payload) + '.' + signature;
}

// Parse JSON body from request
function parseBody(req) {
  return new Promise((resolve, reject) => {
    let body = '';
    req.on('data', chunk => body += chunk);
    req.on('end', () => {
      try { resolve(JSON.parse(body)); }
      catch(e) { reject(new Error('Invalid JSON')); }
    });
    req.on('error', reject);
  });
}

// Proxy request to Ghost API
function proxyToGhost(gpath, method, body, token) {
  return new Promise((resolve, reject) => {
    const url = new URL(gpath, GHOST_API);
    const options = {
      hostname: url.hostname,
      port: url.port,
      path: url.pathname + url.search,
      method: method,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': token,
        'Accept-Version': 'v5.0',
        'Host': 'alfredstudio.mooo.com',
        'X-Forwarded-Proto': 'https',
        'X-Forwarded-Host': 'alfredstudio.mooo.com',
        'X-Forwarded-Prefix': '/blog'
      }
    };

    const req = http.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve({ status: res.statusCode, body: JSON.parse(data) });
        } catch(e) {
          resolve({ status: res.statusCode, body: data });
        }
      });
    });

    req.on('error', reject);
    if (body) req.write(JSON.stringify(body));
    req.end();
  });
}

// CORS headers
function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
  };
}

// Main server
const server = http.createServer(async (req, res) => {
  // CORS preflight
  if (req.method === 'OPTIONS') {
    res.writeHead(204, corsHeaders());
    res.end();
    return;
  }

  // Only handle POST /api/newsletter
  if (req.method !== 'POST' || req.url !== '/api/newsletter') {
    res.writeHead(404, { 'Content-Type': 'application/json', ...corsHeaders() });
    res.end(JSON.stringify({ error: 'Not found' }));
    return;
  }

  try {
    const body = await parseBody(req);
    const email = body.email;
    const name = body.name || (email ? email.split('@')[0] : '');

    if (!email || !email.includes('@')) {
      res.writeHead(400, { 'Content-Type': 'application/json', ...corsHeaders() });
      res.end(JSON.stringify({ error: 'Email invalide' }));
      return;
    }

    // Read API key and generate JWT
    const apiKey = readApiKey();
    if (!apiKey) {
      res.writeHead(500, { 'Content-Type': 'application/json', ...corsHeaders() });
      res.end(JSON.stringify({ error: 'Clé API non configurée' }));
      return;
    }

    const token = generateJWT(apiKey);

    // Call Ghost Admin API to create member
    const result = await proxyToGhost('/blog/ghost/api/admin/members/', 'POST', {
      members: [{ email, name }]
    }, token);

    if (result.status >= 200 && result.status < 300) {
      // Deja inscrit (422/conflict) ou cree (201) : success pour l'UX
      const body = result.status === 201 ? { success: true, message: 'Inscription réussie' } : { success: true, message: 'Merci !' };
      res.writeHead(200, { 'Content-Type': 'application/json', ...corsHeaders() });
      res.end(JSON.stringify(body));
    } else {
      console.log('Ghost API response:', result.status, JSON.stringify(result.body).substring(0, 300));
      const msg = result.status === 422 ? 'Cet email est déjà inscrit' : 'Erreur de synchronisation, réessayez plus tard';
      res.writeHead(502, { 'Content-Type': 'application/json', ...corsHeaders() });
      res.end(JSON.stringify({ error: msg }));
    }
  } catch (e) {
    console.error('Error:', e.message);
    res.writeHead(500, { 'Content-Type': 'application/json', ...corsHeaders() });
    res.end(JSON.stringify({ error: 'Erreur serveur' }));
  }
});

server.listen(PORT, '127.0.0.1', () => {
  console.log('Newsletter proxy listening on port ' + PORT);
});
