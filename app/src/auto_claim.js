const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');
const cron = require('node-cron');
const bot = require('./bot');

const DATA_DIR = (() => {
  const cwd = process.cwd();
  for (const p of [path.join(cwd, 'src', 'data'), path.join(cwd, 'data')]) {
    if (fs.existsSync(path.join(p, 'claim_profiles.json'))) return p;
  }
  return path.join(cwd, 'src', 'data');
})();
const PROFILES_FILE = path.join(DATA_DIR, 'claim_profiles.json');
const HISTORY_FILE = path.join(DATA_DIR, 'claim_history.json');

function loadProfiles() {
  try {
    if (fs.existsSync(PROFILES_FILE)) {
      return JSON.parse(fs.readFileSync(PROFILES_FILE, 'utf8'));
    }
  } catch (e) {
    console.error('[Auto-Claim] Error loading profiles:', e.message);
  }
  return [];
}

function saveHistory(history) {
  fs.writeFileSync(HISTORY_FILE, JSON.stringify(history, null, 2), 'utf8');
}

function loadHistory() {
  try {
    if (fs.existsSync(HISTORY_FILE)) {
      return JSON.parse(fs.readFileSync(HISTORY_FILE, 'utf8'));
    }
  } catch (e) {}
  return [];
}

function hasClaimedToday(casinoName, history) {
  const today = new Date().toISOString().slice(0, 10);
  return history.some(h => h.casino === casinoName && h.date === today && h.success);
}

async function httpClaim(profile) {
  return new Promise((resolve) => {
    const url = new URL(profile.claimUrl);
    const client = url.protocol === 'https:' ? https : http;

    const headers = {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Referer': 'https://www.google.com/'
    };

    if (profile.cookieFile) {
      try {
        const cookiePath = path.resolve(__dirname, profile.cookieFile);
        if (fs.existsSync(cookiePath)) {
          headers['Cookie'] = fs.readFileSync(cookiePath, 'utf8').trim();
        }
      } catch (e) {}
    }

    const req = client.request(url, {
      method: profile.method || 'GET',
      headers,
      timeout: 15000
    }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => {
        const indicator = profile.successIndicator || '';
        const success = indicator ? body.toLowerCase().includes(indicator.toLowerCase()) : res.statusCode < 400;
        resolve({ success, status: res.statusCode, body: body.slice(0, 500) });
      });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({ success: false, status: 0, body: 'Timeout' });
    });

    req.on('error', (e) => {
      resolve({ success: false, status: 0, body: e.message });
    });

    req.end();
  });
}

async function sendDiscordNotification(results) {
  bot.sendClaimResults(results);
}

async function runDailyClaim() {
  const profiles = loadProfiles().filter(p => p.enabled);
  const history = loadHistory();

  if (profiles.length === 0) {
    console.log('[Auto-Claim] No enabled casinos configured');
    return;
  }

  console.log(`[Auto-Claim] Running daily claim for ${profiles.length} casino(s)...`);
  const results = [];

  for (const profile of profiles) {
    if (hasClaimedToday(profile.name, history)) {
      console.log(`[Auto-Claim] ${profile.name}: already claimed today, skipping`);
      results.push({ casino: profile.name, success: true, status: 'skipped' });
      continue;
    }

    console.log(`[Auto-Claim] ${profile.name}: claiming...`);
    const result = await httpClaim(profile);
    results.push({ casino: profile.name, ...result });

    if (result.success) {
      console.log(`[Auto-Claim] ${profile.name}: ✅ claimed`);
    } else {
      console.log(`[Auto-Claim] ${profile.name}: ❌ failed (${result.status || result.body.slice(0, 60)})`);
    }

    history.push({
      casino: profile.name,
      date: new Date().toISOString().slice(0, 10),
      time: new Date().toISOString(),
      success: result.success,
      status: result.status || result.body.slice(0, 100)
    });

    await new Promise(r => setTimeout(r, 2000));
  }

  saveHistory(history);
  await sendDiscordNotification(results);
  console.log(`[Auto-Claim] Daily run complete: ${results.filter(r => r.success).length}/${results.length}`);
}
function start() {
  const profiles = loadProfiles();
  const enabled = profiles.filter(p => p.enabled).length;
  console.log(`[Auto-Claim] Module ready (${enabled}/${profiles.length} casinos enabled)`);

  cron.schedule('0 10 * * *', () => {
    console.log('[Auto-Claim] Scheduled daily run triggered');
    runDailyClaim();
  });
}

function stop() {}

module.exports = { start, stop, runDailyClaim };
