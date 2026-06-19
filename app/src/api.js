const http = require('http');
const fs = require('fs');
const path = require('path');

const PORT = 3456;
const DATA_DIR = (() => {
  const cwd = process.cwd();
  // Try both project-root/src/data and src/data (when run from src/)
  const candidates = [
    path.join(cwd, 'src', 'data'),
    path.join(cwd, 'data'),
  ];
  for (const p of candidates) {
    if (fs.existsSync(path.join(p, 'claim_profiles.json'))) return p;
  }
  return candidates[0]; // fallback
})();
const COOKIE_DIR = path.join(DATA_DIR, 'cookies');

function readJSON(file) {
  try { return JSON.parse(fs.readFileSync(file, 'utf8')); } catch { return null; }
}

function writeJSON(file, data) {
  fs.writeFileSync(file, JSON.stringify(data, null, 2));
}

function parseBody(req) {
  return new Promise((resolve) => {
    let body = '';
    req.on('data', c => body += c);
    req.on('end', () => {
      try { resolve(body ? JSON.parse(body) : {}); } catch { resolve({}); }
    });
  });
}

function sendJSON(res, data, status = 200) {
  res.writeHead(status, { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' });
  res.end(JSON.stringify(data));
}

function start(bot) {
  const server = http.createServer(async (req, res) => {
    if (req.method === 'OPTIONS') {
      res.writeHead(204, { 'Access-Control-Allow-Origin': '*', 'Access-Control-Allow-Methods': 'GET,PUT,POST,DELETE', 'Access-Control-Allow-Headers': 'Content-Type' });
      return res.end();
    }

    const url = new URL(req.url, `http://localhost:${PORT}`);
    const pathname = url.pathname.replace(/\/$/, '');
    const method = req.method;

    try {
      if (method === 'GET' && pathname === '/api/status') {
        return sendJSON(res, {
          online: bot.ready,
          ping: bot.client?.ws?.ping || 0,
          uptime: process.uptime(),
          guilds: bot.client?.guilds?.cache?.size || 0,
          monitorChannel: !!bot.monitorChannel,
          streamerChannel: !!bot.streamerChannel,
          dailyClaimsChannel: !!bot.dailyClaimsChannel
        });
      }

      if (method === 'GET' && pathname === '/api/license') {
        const settings = readJSON(path.join(DATA_DIR, 'settings.json'));
        const key = settings?.licenseKey || null;
        return sendJSON(res, { key, valid: key ? bot.validateLicenseKey(key) : false });
      }

      if (method === 'PUT' && pathname === '/api/license') {
        const body = await parseBody(req);
        if (body.key && bot.validateLicenseKey(body.key)) {
          const settingsPath = path.join(DATA_DIR, 'settings.json');
          const settings = readJSON(settingsPath) || {};
          settings.licenseKey = body.key;
          writeJSON(settingsPath, settings);
          return sendJSON(res, { success: true });
        }
        return sendJSON(res, { success: false, error: 'Invalid license key' }, 400);
      }

      if (method === 'GET' && pathname === '/api/casinos') {
        const profiles = readJSON(path.join(DATA_DIR, 'claim_profiles.json')) || [];
        return sendJSON(res, profiles.map(p => ({ name: p.name, enabled: p.enabled, claimUrl: p.claimUrl })));
      }

      const casinoMatch = pathname.match(/^\/api\/casinos\/(.+)$/);
      if (casinoMatch && method === 'PUT') {
        const body = await parseBody(req);
        const profiles = readJSON(path.join(DATA_DIR, 'claim_profiles.json')) || [];
        const idx = profiles.findIndex(p => p.name.toLowerCase() === decodeURIComponent(casinoMatch[1]).toLowerCase());
        if (idx === -1) return sendJSON(res, { error: 'Casino not found' }, 404);
        if (body.enabled !== undefined) profiles[idx].enabled = body.enabled;
        writeJSON(path.join(DATA_DIR, 'claim_profiles.json'), profiles);
        return sendJSON(res, { success: true, casino: profiles[idx] });
      }

      if (method === 'GET' && pathname === '/api/cookies') {
        const files = fs.existsSync(COOKIE_DIR) ? fs.readdirSync(COOKIE_DIR) : [];
        return sendJSON(res, files.map(f => ({ casino: f.replace(/\.txt$/, '') })));
      }

      const cookiePutMatch = pathname.match(/^\/api\/cookies\/(.+)$/);
      if (cookiePutMatch && method === 'PUT') {
        const body = await parseBody(req);
        if (!body.cookie) return sendJSON(res, { error: 'Cookie string required' }, 400);
        if (!fs.existsSync(COOKIE_DIR)) fs.mkdirSync(COOKIE_DIR, { recursive: true });
        fs.writeFileSync(path.join(COOKIE_DIR, `${decodeURIComponent(cookiePutMatch[1])}.txt`), body.cookie);
        return sendJSON(res, { success: true });
      }

      const cookieDelMatch = pathname.match(/^\/api\/cookies\/(.+)$/);
      if (cookieDelMatch && method === 'DELETE') {
        const file = path.join(COOKIE_DIR, `${decodeURIComponent(cookieDelMatch[1])}.txt`);
        if (fs.existsSync(file)) fs.unlinkSync(file);
        return sendJSON(res, { success: true });
      }

      if (method === 'GET' && pathname === '/api/claims/history') {
        const history = readJSON(path.join(DATA_DIR, 'claim_history.json')) || [];
        return sendJSON(res, history.slice(-50).reverse());
      }

      if (method === 'POST' && pathname === '/api/claims/scan') {
        try {
          const claimModule = require('./modules/cookie_claim');
          const results = await claimModule.scanAll();
          return sendJSON(res, { success: true, results });
        } catch (e) {
          return sendJSON(res, { success: false, error: e.message }, 500);
        }
      }

      if (method === 'POST' && pathname === '/api/claims/claim') {
        try {
          const claimModule = require('./modules/cookie_claim');
          const results = await claimModule.claimAll();
          if (bot.ready && results.length > 0) bot.sendClaimResults(results);
          return sendJSON(res, { success: true, results });
        } catch (e) {
          return sendJSON(res, { success: false, error: e.message }, 500);
        }
      }

      sendJSON(res, { error: 'Not found' }, 404);
    } catch (e) {
      sendJSON(res, { error: e.message }, 500);
    }
  });

  server.listen(PORT, '127.0.0.1', () => {
    console.log(`[API] Dashboard server running on http://127.0.0.1:${PORT}`);
  });

  return server;
}

module.exports = { start };
