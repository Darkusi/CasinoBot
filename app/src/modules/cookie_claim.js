const fs = require('fs');
const path = require('path');
const https = require('https');
const http = require('http');

const DATA_DIR = (() => {
  const cwd = process.cwd();
  for (const p of [path.join(cwd, 'src', 'data'), path.join(cwd, 'data')]) {
    if (fs.existsSync(path.join(p, 'claim_profiles.json'))) return p;
  }
  return path.join(cwd, 'src', 'data');
})();
const PROFILES_FILE = path.join(DATA_DIR, 'claim_profiles.json');
const COOKIE_DIR = path.join(DATA_DIR, 'cookies');

function ensureDir() {
  if (!fs.existsSync(COOKIE_DIR)) fs.mkdirSync(COOKIE_DIR, { recursive: true });
}

function loadProfiles() {
  try {
    if (fs.existsSync(PROFILES_FILE)) return JSON.parse(fs.readFileSync(PROFILES_FILE, 'utf8'));
  } catch (e) {
    console.error('[Cookie-Claim] Error loading profiles:', e.message);
  }
  return [];
}

function loadCookies(casinoName) {
  const safeName = casinoName.toLowerCase().replace(/[^a-z0-9]/g, '_');
  const filePath = path.join(COOKIE_DIR, `${safeName}.txt`);
  try {
    if (fs.existsSync(filePath)) return fs.readFileSync(filePath, 'utf8').trim();
  } catch (e) {}
  return '';
}

function saveCookies(casinoName, cookieString) {
  ensureDir();
  const safeName = casinoName.toLowerCase().replace(/[^a-z0-9]/g, '_');
  const filePath = path.join(COOKIE_DIR, `${safeName}.txt`);
  fs.writeFileSync(filePath, cookieString, 'utf8');
}

function getCookieCasinos() {
  const profiles = loadProfiles().filter(p => p.enabled);
  return profiles.filter(p => loadCookies(p.name).length > 0);
}

function httpGet(urlStr, cookieString) {
  return new Promise((resolve) => {
    const url = new URL(urlStr);
    const client = url.protocol === 'https:' ? https : http;
    const headers = {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'en-US,en;q=0.9',
      'Referer': 'https://www.google.com/'
    };
    if (cookieString) headers['Cookie'] = cookieString;
    const req = client.request(url, { method: 'GET', headers, timeout: 15000 }, (res) => {
      let body = '';
      res.on('data', chunk => body += chunk);
      res.on('end', () => resolve({ status: res.statusCode, body, headers: res.headers }));
    });
    req.on('timeout', () => { req.destroy(); resolve({ status: 0, body: '', headers: {} }); });
    req.on('error', () => resolve({ status: 0, body: '', headers: {} }));
    req.end();
  });
}

const AVAILABILITY_INDICATORS = [
  'claim', 'daily bonus', 'collect', 'get bonus', 'available', 'claim now',
  'free sc', 'free sweeps', 'redeem', 'daily reward'
];

const CLAIMED_INDICATORS = [
  'already claimed', 'come back', 'tomorrow', 'next daily', 'claimed',
  'already redeemed', 'try again', '24 hours', 'already collected'
];

async function scanCasino(profile) {
  const cookie = loadCookies(profile.name);
  if (!cookie) return { casino: profile.name, available: false, error: 'no cookies' };
  const result = await httpGet(profile.claimUrl, cookie);
  if (!result.body) return { casino: profile.name, available: false, error: `HTTP ${result.status}` };
  const body = result.body.toLowerCase();
  const hasAvailable = AVAILABILITY_INDICATORS.some(ind => body.includes(ind));
  const hasClaimed = CLAIMED_INDICATORS.some(ind => body.includes(ind));
  return {
    casino: profile.name,
    available: hasAvailable && !hasClaimed,
    alreadyClaimed: hasClaimed,
    error: null
  };
}

async function scanAll() {
  const profiles = getCookieCasinos();
  if (profiles.length === 0) return [];
  const results = [];
  for (const p of profiles) {
    const r = await scanCasino(p);
    results.push(r);
    await new Promise(r => setTimeout(r, 1500));
  }
  return results;
}

async function claimCasino(profile) {
  const cookie = loadCookies(profile.name);
  if (!cookie) return { casino: profile.name, success: false, error: 'no cookies' };
  const result = await httpGet(profile.claimUrl, cookie);
  if (!result.body) return { casino: profile.name, success: false, error: `HTTP ${result.status}` };
  const indicator = profile.successIndicator || '';
  const success = indicator ? result.body.toLowerCase().includes(indicator.toLowerCase()) : result.status < 400;
  return { casino: profile.name, success, status: result.status };
}

async function claimAll() {
  const profiles = getCookieCasinos();
  if (profiles.length === 0) return [];
  const results = [];
  for (const p of profiles) {
    const r = await claimCasino(p);
    results.push(r);
    await new Promise(r => setTimeout(r, 2000));
  }
  return results;
}

module.exports = { loadCookies, saveCookies, getCookieCasinos, scanCasino, scanAll, claimCasino, claimAll };
