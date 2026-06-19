const https = require('https');
const http = require('http');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const REFERRAL_CODE = 'FIH-S4Z0J9Z3R1LK';
const ACCOUNTS_FILE = path.join(process.cwd(), 'src', 'data', 'hellofresh_accounts.json');

function genPassword() { return crypto.randomBytes(12).toString('base64').replace(/[^a-zA-Z0-9]/g, '') + 'A1!'; }
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function httpGet(url, headers = {}) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const h = { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36', ...headers };
    client.get(url, { headers: h }, res => { let d = ''; res.on('data', c => d += c); res.on('end', () => resolve({ status: res.statusCode, body: d })); }).on('error', reject);
  });
}

function httpPost(url, data, headers = {}) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const body = typeof data === 'string' ? data : JSON.stringify(data);
    const h = { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body), 'Accept': 'application/json', 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36', ...headers };
    const req = client.request(url, { method: 'POST', headers: h }, res => { let d = ''; res.on('data', c => d += c); res.on('end', () => resolve({ status: res.statusCode, body: d })); });
    req.on('error', reject); req.write(body); req.end();
  });
}

async function createTempEmail() {
  const domRes = await httpGet('https://api.mail.tm/domains');
  const dom = JSON.parse(domRes.body);
  const domain = dom['hydra:member']?.[0]?.domain || 'mail.tm';
  const id = crypto.randomBytes(8).toString('hex');
  const email = `${id}@${domain}`;
  const password = genPassword();
  await httpPost('https://api.mail.tm/accounts', { address: email, password });
  const tokRes = await httpPost('https://api.mail.tm/token', { address: email, password });
  const token = JSON.parse(tokRes.body).token || JSON.parse(tokRes.body).id;
  return { email, password, token };
}

async function pollForVerification(token, timeoutMs = 600000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const res = await httpGet('https://api.mail.tm/messages', { Authorization: `Bearer ${token}` });
    try {
      const data = JSON.parse(res.body);
      const msgs = data['hydra:member'] || [];
      if (msgs.length > 0) {
        const msgRes = await httpGet(`https://api.mail.tm${msgs[0]['@id']}`, { Authorization: `Bearer ${token}` });
        const msg = JSON.parse(msgRes.body);
        const html = msg.html || msg.text || '';
        const verifyLink = html.match(/https?:\/\/[^\s"']*verify[^\s"']*/i)?.[0] ||
                           html.match(/https?:\/\/[^\s"']*confirm[^\s"']*/i)?.[0] ||
                           html.match(/https?:\/\/[^\s"']+/)?.[0];
        if (verifyLink) {
          await httpGet(verifyLink);
          return true;
        }
      }
    } catch {}
    await sleep(5000);
  }
  return false;
}

function loadAccounts() {
  try { if (fs.existsSync(ACCOUNTS_FILE)) return JSON.parse(fs.readFileSync(ACCOUNTS_FILE, 'utf8')); } catch {}
  return [];
}

function saveAccounts(accounts) {
  const dir = path.dirname(ACCOUNTS_FILE);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(ACCOUNTS_FILE, JSON.stringify(accounts, null, 2), 'utf8');
}

async function createAccount() {
  console.log('[HF] Creating temp email...');
  const temp = await createTempEmail();
  const password = genPassword();
  const referralLink = `https://www.hellofresh.com/pages/raf_lp11?c=${REFERRAL_CODE}`;
  const createdAt = new Date().toISOString();

  const account = {
    email: temp.email,
    password,
    tempPassword: temp.password,
    mailToken: temp.token,
    referralLink,
    verified: false,
    createdAt
  };

  return account;
}

async function verifyAccount(account, onStatus) {
  if (onStatus) onStatus('polling');
  const ok = await pollForVerification(account.mailToken);
  if (ok) {
    account.verified = true;
    account.verifiedAt = new Date().toISOString();
    if (onStatus) onStatus('verified');
    return true;
  }
  if (onStatus) onStatus('timeout');
  return false;
}

async function createMultiple(amount, onProgress) {
  const accounts = loadAccounts();
  const results = [];

  for (let i = 0; i < amount; i++) {
    console.log(`[HF] Setting up account ${i + 1}/${amount}...`);
    try {
      const acct = await createAccount();
      if (onProgress) onProgress(i + 1, amount, { type: 'created', account: acct });
      results.push(acct);
    } catch (e) {
      console.error(`[HF] Setup ${i + 1} failed:`, e.message);
      if (onProgress) onProgress(i + 1, amount, { type: 'error', error: e.message });
      results.push({ success: false, error: e.message });
    }
  }
  return results;
}

module.exports = { createAccount, createMultiple, verifyAccount, loadAccounts, saveAccounts, REFERRAL_CODE };
