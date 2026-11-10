const { app, BrowserWindow, dialog, ipcMain, shell, globalShortcut, session } = require('electron');
const { spawn } = require('node:child_process');
const net = require('node:net');
const path = require('node:path');
const { randomBytes } = require('node:crypto');
const { isTrustedIpcEvent } = require('./security.cjs');

const DEV_URL = process.env.MAYA_DEV_URL || 'http://127.0.0.1:5173/';
let mainWindow;
let backendProcess;
let backendHealth;
let quitting = false;
const speechRequests = new Map();

function getBackendDirectory() {
  return app.isPackaged
    ? path.join(process.resourcesPath, 'app.asar.unpacked', 'backend')
    : path.join(__dirname, '..', 'backend');
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const { port } = server.address();
      server.close((error) => error ? reject(error) : resolve(port));
    });
  });
}

function pythonExecutable(backendDirectory) {
  if (process.env.MAYA_PYTHON) return process.env.MAYA_PYTHON;
  const venvPython = process.platform === 'win32'
    ? path.join(backendDirectory, '.venv', 'Scripts', 'python.exe')
    : path.join(backendDirectory, '.venv', 'bin', 'python');
  const fs = require('node:fs');
  return fs.existsSync(venvPython) ? venvPython : (process.platform === 'win32' ? 'python' : 'python3');
}

async function waitForBackend(url, token, child, timeoutMs = 30000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error('The local backend exited during startup.');
    try {
      const response = await fetch(url, { headers: { authorization: `Bearer ${token}` }, signal: AbortSignal.timeout(1000) });
      if (response.ok) {
        const body = await response.json();
        if (body.ok === true && body.database_ready === true && body.mode === 'mock') {
          return Object.freeze({ url, token });
        }
      }
    } catch {
      // The backend may still be starting. No request details or token are logged.
    }
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
  throw new Error('Timed out waiting for the local backend health check.');
}

async function startBackend() {
  const backendDirectory = getBackendDirectory();
  const port = await findFreePort();
  const token = randomBytes(32).toString('hex');
  const env = {
    ...process.env,
    MAYA_HOST: '127.0.0.1',
    MAYA_PORT: String(port),
    MAYA_BACKEND_TOKEN: token,
    MAYA_MODE: 'mock',
    MAYA_DATA_DIR: app.getPath('userData'),
  };
  backendProcess = spawn(
    pythonExecutable(backendDirectory),
    ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(port), '--no-access-log'],
    { cwd: backendDirectory, env, stdio: 'ignore', windowsHide: true },
  );
  backendProcess.once('error', () => {
    if (!quitting) dialog.showErrorBox('Maya backend failed', 'Could not start the local Python service. Follow docs/SETUP.md to install backend dependencies.');
  });
  backendProcess.once('exit', (code) => {
    if (!quitting && code !== 0) {
      dialog.showErrorBox('Maya backend stopped', 'The local Python service stopped unexpectedly. Restart Maya and check the setup instructions.');
      app.quit();
    }
  });
  const url = `http://127.0.0.1:${port}/healthz`;
  return waitForBackend(url, token, backendProcess);
}

function expectedRendererUrl() {
  return app.isPackaged
    ? { packagedIndexPath: path.join(__dirname, '..', 'dist', 'index.html') }
    : { devServerUrl: DEV_URL };
}

function createWindow() {
  const win = new BrowserWindow({
    width: 420,
    height: 620,
    minWidth: 360,
    minHeight: 500,
    title: 'Maya',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      autoplayPolicy: 'no-user-gesture-required',
    },
  });
  mainWindow = win;
  const expected = expectedRendererUrl();
  if (!app.isPackaged && process.env.MAYA_DEV_DIAGNOSTICS === '1') {
    win.webContents.on('console-message', (_event, level, message, line, sourceId) => {
      if (level >= 2) console.error(`[renderer:${level}] ${message} (${sourceId}:${line})`);
    });
    win.webContents.on('did-fail-load', (_event, code, description, url) => {
      console.error(`[renderer:load-failed] code=${code} ${description} ${url}`);
    });
    win.webContents.on('render-process-gone', (_event, details) => {
      console.error(`[renderer:process-gone] ${JSON.stringify(details)}`);
    });
    win.webContents.on('did-finish-load', async () => {
      try {
        const state = await win.webContents.executeJavaScript(`(() => { const root = document.getElementById('root'); return { href: location.href, readyState: document.readyState, rootChildren: root?.childElementCount ?? -1, hasHeading: Boolean(root?.querySelector('h1')) }; })()`);
        console.log(`[renderer:ready] ${JSON.stringify(state)}`);
      } catch (error) {
        console.error(`[renderer:probe-failed] ${error.message}`);
      }
    });
  }
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('https://')) shell.openExternal(url);
    return { action: 'deny' };
  });
  win.webContents.on('will-navigate', (event, url) => {
    if (!require('./security.cjs').isTrustedRendererUrl(url, expected)) event.preventDefault();
  });
  ipcMain.removeHandler('maya:health');
  ipcMain.handle('maya:health', async (event) => {
    if (!isTrustedIpcEvent(event, win, expected)) throw new Error('Untrusted IPC sender.');
    try {
      const response = await fetch(backendHealth.url, {
        headers: { authorization: `Bearer ${backendHealth.token}` },
        signal: AbortSignal.timeout(1500),
      });
      if (!response.ok) throw new Error('Backend health failed.');
      const health = await response.json();
      // Only return non-sensitive status. The port and bearer token stay in main.
      return {
        ok: health.ok === true,
        mode: health.mode === 'mock' ? 'mock' : 'unavailable',
        databaseReady: health.database_ready === true,
        capabilities: Array.isArray(health.capabilities) ? health.capabilities : [],
      };
    } catch {
      return { ok: false, mode: 'unavailable', databaseReady: false, capabilities: [] };
    }
  });
  ipcMain.removeHandler('maya:transcribe');
  ipcMain.handle('maya:transcribe', async (event, payload) => {
    if (!isTrustedIpcEvent(event, win, expected)) throw new Error('Untrusted IPC sender.');
    if (!payload || typeof payload.audioBase64 !== 'string' || payload.audioBase64.length > 12_000_000) return { error: 'Audio payload is invalid or too large.' };
    const controller = new AbortController();
    const requestId = typeof payload.requestId === 'string' ? payload.requestId : randomBytes(12).toString('hex');
    speechRequests.set(requestId, controller);
    try {
      const response = await fetch(backendHealth.url.replace('/healthz', '/voice/transcribe'), {
        method: 'POST', headers: { authorization: `Bearer ${backendHealth.token}`, 'content-type': 'application/json' },
        body: JSON.stringify({ audio_base64: payload.audioBase64, language: payload.language, format: payload.format || 'wav' }),
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(30000)]),
      });
      const result = await response.json();
      return response.ok ? result : { error: result.error || 'Speech request failed.' };
    } catch {
      return { error: 'Speech service is unavailable.' };
    } finally {
      speechRequests.delete(requestId);
    }
  });
  ipcMain.removeHandler('maya:cancel-speech');
  ipcMain.handle('maya:cancel-speech', (event, requestId) => {
    if (!isTrustedIpcEvent(event, win, expected)) throw new Error('Untrusted IPC sender.');
    if (typeof requestId === 'string') speechRequests.get(requestId)?.abort();
  });
  ipcMain.removeAllListeners('maya:start-conversation');
  ipcMain.on('maya:start-conversation', async (event, payload) => {
    if (!isTrustedIpcEvent(event, win, expected)) return;
    if (!payload || typeof payload.requestId !== 'string' || typeof payload.audioBase64 !== 'string' || payload.audioBase64.length > 12_000_000) {
      event.sender.send('maya:conversation-event', { requestId: payload?.requestId, type: 'error', message: 'Conversation audio is invalid or too large.' });
      return;
    }
    const controller = new AbortController();
    speechRequests.set(payload.requestId, controller);
    const send = (data) => { if (!event.sender.isDestroyed()) event.sender.send('maya:conversation-event', { requestId: payload.requestId, ...data }); };
    try {
      const response = await fetch(backendHealth.url.replace('/healthz', '/voice/turn'), {
        method: 'POST', headers: { authorization: `Bearer ${backendHealth.token}`, 'content-type': 'application/json' },
        body: JSON.stringify({ audio_base64: payload.audioBase64, language: payload.language }),
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(180000)]),
      });
      if (!response.ok || !response.body) { send({ type: 'error', message: 'The voice request could not start.' }); return; }
      const reader = response.body.getReader(); const decoder = new TextDecoder(); let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const frames = buffer.split('\n\n'); buffer = frames.pop() || '';
        for (const frame of frames) {
          const line = frame.split('\n').find((part) => part.startsWith('data:'));
          if (line) { try { send(JSON.parse(line.slice(5).trim())); } catch { /* ignore malformed server event */ } }
        }
      }
    } catch {
      if (!controller.signal.aborted) send({ type: 'error', message: 'The voice service is unavailable.' });
    } finally {
      speechRequests.delete(payload.requestId);
    }
  });
  if (app.isPackaged) win.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  else win.loadURL(DEV_URL);
  win.on('closed', () => {
    if (mainWindow === win) mainWindow = undefined;
  });
}

function stopBackend() {
  quitting = true;
  if (backendProcess && backendProcess.exitCode === null) backendProcess.kill();
}

app.whenReady().then(async () => {
  try {
    backendHealth = await startBackend();
    session.defaultSession.setPermissionRequestHandler((_webContents, permission, callback) => callback(permission === 'media'));
    if (!quitting) createWindow();
  } catch {
    stopBackend();
    dialog.showErrorBox('Maya could not start', 'The local backend did not pass its authenticated health check. Check Python and backend dependencies, then try again.');
    app.quit();
  }
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0 && backendHealth) createWindow();
  });
  // Safe fallback only: Caps Lock is deliberately not intercepted because Electron cannot
  // guarantee observing it without changing normal typing state on every Windows setup.
  globalShortcut.register('Control+Space', () => mainWindow?.webContents.send('maya:hotkey'));
});

app.on('before-quit', stopBackend);
app.on('will-quit', () => globalShortcut.unregisterAll());
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
