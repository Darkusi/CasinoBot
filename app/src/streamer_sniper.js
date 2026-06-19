const fs = require('fs');
const path = require('path');
const https = require('https');
const WebSocket = require('ws');
const db = require('./db');
const bot = require('./bot');

const DATA_DIR = (() => {
  const cwd = process.cwd();
  for (const p of [path.join(cwd, 'src', 'data'), path.join(cwd, 'data')]) {
    if (fs.existsSync(path.join(p, 'streamer_profiles.json'))) return p;
  }
  return path.join(cwd, 'src', 'data');
})();
const PROFILES_FILE = path.join(DATA_DIR, 'streamer_profiles.json');
const PUSHER_APP_KEY = '32cbd69e4b950bf97679';
const PUSHER_CLUSTER = 'us2';
const PUSHER_URL = `wss://ws-${PUSHER_CLUSTER}.pusher.com/app/${PUSHER_APP_KEY}?protocol=7&client=js&version=8.4.0-0&flash=false`;

let connections = {};
let reconnectTimers = {};

function loadProfiles() {
  try {
    if (fs.existsSync(PROFILES_FILE)) {
      return JSON.parse(fs.readFileSync(PROFILES_FILE, 'utf8'));
    }
  } catch (e) {
    console.error('[Streamer] Error loading profiles:', e.message);
  }
  return [];
}

function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    client.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try { resolve(JSON.parse(data)); }
          catch (e) { reject(new Error('Invalid JSON')); }
        } else {
          reject(new Error(`HTTP ${res.statusCode}`));
        }
      });
    }).on('error', reject);
  });
}

async function getChatroomId(username) {
  const data = await fetchJSON(`https://kick.com/api/v2/channels/${username}`);
  return data.chatroom?.id || null;
}

function extractUrls(text) {
  const urlRegex = /https?:\/\/[^\s<>"']+/g;
  return text.match(urlRegex) || [];
}

function connectToStreamer(profile) {
  const { kickUsername, name } = profile;

  if (connections[kickUsername]) {
    return;
  }

  console.log(`[Streamer] Connecting to ${name} (${kickUsername})...`);

  const ws = new WebSocket(PUSHER_URL);

  ws.on('open', async () => {
    console.log(`[Streamer] ${name}: WebSocket connected`);

    try {
      const chatroomId = await getChatroomId(kickUsername);
      if (!chatroomId) {
        console.log(`[Streamer] ${name}: could not find chatroom`);
        ws.close();
        return;
      }

      ws.send(JSON.stringify({
        event: 'pusher:subscribe',
        data: { auth: '', channel: `chat.${chatroomId}` }
      }));
      console.log(`[Streamer] ${name}: subscribed to chat.${chatroomId}`);
    } catch (e) {
      console.error(`[Streamer] ${name}: error getting chatroom:`, e.message);
    }
  });

  ws.on('message', (raw) => {
    try {
      const msg = JSON.parse(raw.toString());

      if (msg.event === 'App\\Events\\ChatMessageEvent') {
        const payload = JSON.parse(msg.data);
        const content = payload.content || '';
        const sender = payload.sender?.username || 'unknown';

        const urls = extractUrls(content);
        if (urls.length > 0) {
          console.log(`[Streamer] ${name}: ${sender} dropped ${urls.length} link(s)`);

          urls.forEach(url => {
            if (db.isPostSeen(url, url)) return;
            db.markPostSeen(url, url, `kick_${kickUsername}`);
            bot.sendStreamerAlert(name, url, sender);
          });
        }
      }
    } catch (e) {}
  });

  ws.on('close', () => {
    console.log(`[Streamer] ${name}: disconnected`);
    delete connections[kickUsername];

    reconnectTimers[kickUsername] = setTimeout(() => {
      console.log(`[Streamer] ${name}: reconnecting in 10s...`);
      connectToStreamer(profile);
    }, 10000);
  });

  ws.on('error', (e) => {
    console.error(`[Streamer] ${name}: error:`, e.message);
  });

  connections[kickUsername] = ws;
}

function disconnectAll() {
  Object.keys(connections).forEach(key => {
    try { connections[key].close(); } catch (e) {}
    delete connections[key];
  });
  Object.keys(reconnectTimers).forEach(key => {
    clearTimeout(reconnectTimers[key]);
    delete reconnectTimers[key];
  });
}

function start() {
  const profiles = loadProfiles().filter(p => p.enabled);
  if (profiles.length === 0) {
    console.log('[Streamer] Module loaded. Enable streamers in data/streamer_profiles.json');
    return;
  }

  console.log(`[Streamer] Connecting to ${profiles.length} streamer(s)...`);
  profiles.forEach(p => connectToStreamer(p));
}

function stop() {
  disconnectAll();
}

module.exports = { start, stop };
