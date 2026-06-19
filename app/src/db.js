const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const DATA_DIR = (() => {
  const cwd = process.cwd();
  for (const p of [path.join(cwd, 'src', 'data'), path.join(cwd, 'data')]) {
    if (fs.existsSync(p)) return p;
  }
  return path.join(cwd, 'src', 'data');
})();
const SEEN_POSTS_FILE = path.join(DATA_DIR, 'seen_posts.json');
const SETTINGS_FILE = path.join(DATA_DIR, 'settings.json');

function ensureDir() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
}

function readJSON(file, fallback) {
  ensureDir();
  try {
    if (fs.existsSync(file)) {
      return JSON.parse(fs.readFileSync(file, 'utf8'));
    }
  } catch (e) {
    console.error(`Error reading ${file}:`, e.message);
  }
  return fallback;
}

function writeJSON(file, data) {
  ensureDir();
  fs.writeFileSync(file, JSON.stringify(data, null, 2), 'utf8');
}

function hashPost(title, link) {
  return crypto.createHash('sha256').update(title + link).digest('hex');
}

const seenPosts = readJSON(SEEN_POSTS_FILE, []);

function isPostSeen(title, link) {
  const h = hashPost(title, link);
  return seenPosts.some(p => p.hash === h);
}

function markPostSeen(title, link, source) {
  const h = hashPost(title, link);
  if (!seenPosts.some(p => p.hash === h)) {
    seenPosts.push({ hash: h, title, link, source, seen_at: new Date().toISOString() });
    writeJSON(SEEN_POSTS_FILE, seenPosts);
  }
}

function getSettings() {
  return readJSON(SETTINGS_FILE, {});
}

function saveSettings(settings) {
  writeJSON(SETTINGS_FILE, settings);
}

function getRecentPosts(hours = 24) {
  const cutoff = new Date(Date.now() - hours * 60 * 60 * 1000).toISOString();
  return seenPosts.filter(p => p.seen_at >= cutoff);
}

module.exports = { isPostSeen, markPostSeen, getSettings, saveSettings, getRecentPosts };
