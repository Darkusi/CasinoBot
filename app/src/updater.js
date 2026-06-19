const https = require('https');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const CURRENT_VERSION = '2.0.0';
const REPO = 'glowrius/casino-bonus-monitor';
const RELEASES_URL = `https://api.github.com/repos/${REPO}/releases/latest`;
const EXE_NAME = 'Casino' + 'Bot.exe';

function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    const opts = new URL(url);
    https.get(opts, { headers: { 'User-Agent': 'CasinoBot-Updater/2.0', 'Accept': 'application/vnd.github.v3+json' } }, (res) => {
      let data = '';
      res.on('data', c => data += c);
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          try { resolve(JSON.parse(data)); }
          catch (e) { reject(new Error('Invalid JSON response')); }
        } else {
          reject(new Error(`HTTP ${res.statusCode}: ${data.slice(0, 200)}`));
        }
      });
    }).on('error', reject);
  });
}

function semverCompare(a, b) {
  const pa = a.replace(/^v/, '').split('.').map(Number);
  const pb = b.replace(/^v/, '').split('.').map(Number);
  for (let i = 0; i < 3; i++) {
    if ((pa[i] || 0) > (pb[i] || 0)) return 1;
    if ((pa[i] || 0) < (pb[i] || 0)) return -1;
  }
  return 0;
}

function downloadFile(url, dest) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(dest);
    https.get(url, { headers: { 'User-Agent': 'CasinoBot-Updater/2.0' } }, (res) => {
      if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
        file.close();
        fs.unlinkSync(dest);
        return downloadFile(res.headers.location, dest).then(resolve).catch(reject);
      }
      if (res.statusCode !== 200) {
        file.close();
        fs.unlinkSync(dest);
        return reject(new Error(`HTTP ${res.statusCode}`));
      }
      res.pipe(file);
      file.on('finish', () => { file.close(); resolve(); });
    }).on('error', (e) => {
      file.close();
      try { fs.unlinkSync(dest); } catch (e2) {}
      reject(e);
    });
  });
}

async function checkForUpdate() {
  try {
    const release = await fetchJSON(RELEASES_URL);
    const latestTag = release.tag_name || '';
    const latestVersion = latestTag.replace(/^v/, '');

    if (!latestVersion) {
      return { hasUpdate: false, reason: 'no version tag' };
    }

    if (semverCompare(latestVersion, CURRENT_VERSION) <= 0) {
      return { hasUpdate: false, reason: `already at latest (${CURRENT_VERSION})` };
    }

    const asset = (release.assets || []).find(a => a.name === EXE_NAME);
    if (!asset) {
      return { hasUpdate: true, version: latestVersion, error: 'no CasinoBot.exe asset found in release' };
    }

    return {
      hasUpdate: true,
      version: latestVersion,
      downloadUrl: asset.browser_download_url,
      releaseUrl: release.html_url,
      notes: release.body || ''
    };

  } catch (e) {
    return { hasUpdate: false, reason: e.message, error: e.message };
  }
}

async function applyUpdate(downloadUrl, newVersion) {
  const tmpDir = path.join(require('os').tmpdir(), 'casinobot-update');
  const tmpExe = path.join(tmpDir, 'Casino' + 'Bot.exe.new');
  const baseDir = __dirname;
  const exePath = path.join(baseDir, 'Casino' + 'Bot.exe');
  const batPath = path.join(baseDir, 'update' + '.bat');

  if (!fs.existsSync(tmpDir)) { fs.mkdirSync(tmpDir, { recursive: true }); }

  console.log(`[Updater] Downloading v${newVersion}...`);
  await downloadFile(downloadUrl, tmpExe);

  if (!fs.existsSync(tmpExe)) {
    throw new Error('Download failed - file not found');
  }

  const size = (fs.statSync(tmpExe).length / 1024 / 1024).toFixed(1);
  console.log(`[Updater] Downloaded ${size} MB`);

  const batContent = `@echo off
title Casino Bonus Monitor - Updating...
echo Waiting for CasinoBot.exe to exit...
:wait
tasklist /FI "IMAGENAME eq CasinoBot.exe" 2>NUL | find /I /N "CasinoBot.exe" >NUL
if "%ERRORLEVEL%"=="0" (
  timeout /t 2 /nobreak >NUL
  goto wait
)
echo Replacing executable...
copy /Y "${tmpExe}" "%~dp0CasinoBot.exe" >NUL
echo Cleaning up...
del "${tmpExe}"
echo Starting Casino Bonus Monitor...
start "" "%~dp0CasinoBot.exe"
del "%~f0"
`;

  fs.writeFileSync(batPath, batContent);
  console.log(`[Updater] Update ready. Restarting via update.bat...`);

  execSync(`start "" "${batPath}"`, { shell: 'cmd.exe', detached: true });
  process.exit(0);
}

async function runUpdateCheck(auto = false) {
  console.log(`[Updater] Current version: v${CURRENT_VERSION}`);
  const result = await checkForUpdate();

  if (result.hasUpdate && result.downloadUrl) {
    console.log(`[Updater] Update available: v${result.version}`);
    try {
      await applyUpdate(result.downloadUrl, result.version);
    } catch (e) {
      console.error(`[Updater] Update failed:`, e.message);
    }
  } else if (result.hasUpdate && result.error) {
    console.log(`[Updater] New version v${result.version} available, but: ${result.error}`);
    console.log(`[Updater] Download manually: ${result.releaseUrl}`);
  } else if (auto) {
    console.log(`[Updater] No update available (${result.reason || 'latest'})`);
  } else {
    console.log(`[Updater] ${result.reason || 'No update available'}`);
  }
}

function startAutoCheck() {
  runUpdateCheck(true);
  setInterval(() => runUpdateCheck(true), 24 * 60 * 60 * 1000);
}

module.exports = { checkForUpdate, applyUpdate, runUpdateCheck, startAutoCheck };
