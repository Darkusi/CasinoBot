const https = require('https');
const http = require('http');
const db = require('./db');
const bot = require('./bot');

let pollInterval = null;
let isRunning = false;

function fetchURL(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const headers = {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
      'Accept': 'application/rss+xml, application/xml, text/xml, */*',
      'Accept-Language': 'en-US,en;q=0.9',
      'Accept-Encoding': 'identity',
      'Referer': 'https://old.reddit.com/',
      'Cache-Control': 'no-cache',
      'Pragma': 'no-cache'
    };
    client.get(url, { headers }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(data);
        else reject(new Error(`HTTP ${res.statusCode}: ${data.slice(0, 200)}`));
      });
    }).on('error', reject);
  });
}

function decodeEntities(str) {
  return str.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#x27;/g, "'").replace(/&#39;/g, "'").replace(/&apos;/g, "'");
}

function parseFeed(xml) {
  const isAtom = xml.includes('<entry>');
  const items = [];
  if (isAtom) {
    const entryRegex = /<entry>([\s\S]*?)<\/entry>/gi;
    let match;
    while ((match = entryRegex.exec(xml)) !== null) {
      const e = match[1];
      const title = (e.match(/<title>([\s\S]*?)<\/title>/i) || [])[1] || '';
      const link = (e.match(/<link[^>]*href="([^"]+)"[^>]*\/?>/i) || [])[1] || '';
      const pubDate = (e.match(/<published>([\s\S]*?)<\/published>/i) || [])[1] || (e.match(/<updated>([\s\S]*?)<\/updated>/i) || [])[1] || '';
      const content = (e.match(/<content[^>]*>([\s\S]*?)<\/content>/i) || [])[1] || (e.match(/<summary[^>]*>([\s\S]*?)<\/summary>/i) || [])[1] || '';
      if (title || link) items.push({ title: decodeEntities(title.trim()), link, pubDate, description: decodeEntities(content.trim()) });
    }
  } else {
    const itemRegex = /<item>([\s\S]*?)<\/item>/gi;
    let match;
    while ((match = itemRegex.exec(xml)) !== null) {
      const e = match[1];
      const getTag = (tag) => { const re = new RegExp(`<${tag}>(?:<!\\[CDATA\\[)?([\\s\\S]*?)(?:\\]\\]>)?<\\/${tag}>`, 'i'); const m = e.match(re); return m ? decodeEntities(m[1].trim()) : ''; };
      const title = getTag('title');
      const link = getTag('link');
      const pubDate = getTag('pubDate');
      const description = getTag('description');
      if (title || link) items.push({ title, link, pubDate, description });
    }
  }
  return items;
}

const INCLUDE_RE = /free.?spin|free.?sc|sweepscash|no.?deposit|daily.?bonus|promo.?code|bonus.?code|free.?money|free.?dollar|\b\d+\s*(sc|spin|gold|gc)\b/i;
const EXCLUDE_RE = /new.?casino|launch(ing|ed|es)?|coming.?soon|review|referral|question|help|flash.?sale|how.?to|tutorial|guide|tip|strategy/i;

function isRelevantPost(title) {
  if (EXCLUDE_RE.test(title)) return false;
  return INCLUDE_RE.test(title);
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function processItems(items, label) {
  let count = 0;
  for (const item of items) {
    if (db.isPostSeen(item.title, item.link)) continue;
    if (!isRelevantPost(item.title)) continue;
    db.markPostSeen(item.title, item.link, 'reddit');
    try {
      await bot.sendMonitorPost(item);
      await sleep(1500);
    } catch (e) {
      console.error(`[${label}] Send error:`, e.message);
    }
    count++;
  }
  return count;
}

async function pollRSS() {
  if (isRunning) return;
  isRunning = true;
  const settings = db.getSettings();
  const rssUrls = (settings.rssUrls || process.env.REDDIT_RSS_URLS || '').split(',').map(s => s.trim()).filter(Boolean);
  for (const url of rssUrls) {
    try {
      const xml = await fetchURL(url);
      const items = parseFeed(xml);
      const newCount = await processItems(items, 'Poll');
      if (newCount > 0) console.log(`[Poll] ${url}: ${newCount} new posts sent`);
    } catch (e) { console.error(`[Poll] Error fetching ${url}:`, e.message); }
  }
  isRunning = false;
}

async function startupFlood() {
  const settings = db.getSettings();
  const rssUrls = (settings.rssUrls || process.env.REDDIT_RSS_URLS || '').split(',').map(s => s.trim()).filter(Boolean);
  const monChannel = process.env.MONITOR_CHANNEL_ID || 'monitor';
  console.log(`[Startup] Flooding <#${monChannel}> with last 24h posts...`);
  let totalSent = 0;
  const cutoff = new Date(Date.now() - 24 * 60 * 60 * 1000);
  for (const url of rssUrls) {
    try {
      const xml = await fetchURL(url);
      const items = parseFeed(xml);
      const recentItems = items.filter(item => { if (!item.pubDate) return true; const d = new Date(item.pubDate); return !isNaN(d.getTime()) && d >= cutoff; });
      const count = await processItems(recentItems, 'Startup');
      totalSent += count;
    } catch (e) { console.error(`[Startup] Error fetching ${url}:`, e.message); }
  }
  console.log(`[Startup] Flood complete: ${totalSent} posts sent to <#${monChannel}>`);
}

function start(intervalSeconds) {
  console.log('[Monitor] Starting Reddit RSS monitor...');
  startupFlood().then(() => {
    const interval = (intervalSeconds || 10) * 1000;
    pollInterval = setInterval(pollRSS, interval);
    pollRSS();
    console.log(`[Monitor] Polling every ${interval / 1000}s`);
  });
}

function stop() {
  if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
}

module.exports = { start, stop };
