import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { spawn } from 'node:child_process';
import net from 'node:net';
import { createServer } from 'vite';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const electronPath = require('electron');
const port = await new Promise((resolve, reject) => {
  const probe = net.createServer();
  probe.once('error', reject);
  probe.listen(0, '127.0.0.1', () => {
    const selectedPort = probe.address().port;
    probe.close((error) => error ? reject(error) : resolve(selectedPort));
  });
});
const vite = await createServer({
  configFile: path.join(root, 'vite.config.ts'),
  server: { host: '127.0.0.1', port, strictPort: true },
});

let child;
let shuttingDown = false;
async function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  if (child && child.exitCode === null) child.kill();
  await vite.close();
  process.exitCode = code;
}

try {
  await vite.listen();
  const devUrl = vite.resolvedUrls?.local?.[0];
  if (!devUrl) throw new Error('Vite did not provide a local URL.');
  process.stdout.write(`Maya renderer: ${devUrl}\n`);
  child = spawn(electronPath, ['.'], {
    cwd: root,
    env: { ...process.env, MAYA_DEV_URL: devUrl, MAYA_DEV_DIAGNOSTICS: '1' },
    stdio: 'inherit',
    windowsHide: false,
  });
  child.once('error', (error) => {
    process.stderr.write(`Could not start Electron: ${error.message}\n`);
    void shutdown(1);
  });
  child.once('exit', (code) => { void shutdown(code ?? 1); });
  process.once('SIGINT', () => { if (child && child.exitCode === null) child.kill(); });
  process.once('SIGTERM', () => { if (child && child.exitCode === null) child.kill(); });
} catch (error) {
  process.stderr.write(`Maya dev startup failed: ${error.message}\n`);
  await shutdown(1);
}
