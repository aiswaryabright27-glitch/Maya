const { existsSync } = require('node:fs');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const root = path.resolve(__dirname, '..');
const backend = path.join(root, 'backend');
const venvPython = process.platform === 'win32'
  ? path.join(backend, '.venv', 'Scripts', 'python.exe')
  : path.join(backend, '.venv', 'bin', 'python');
const python = existsSync(venvPython) ? venvPython : (process.platform === 'win32' ? 'python' : 'python3');
const result = spawnSync(python, ['-m', 'pytest', '../tests', '-q'], { cwd: backend, stdio: 'inherit' });
if (result.error) {
  process.stderr.write('Could not run backend tests. Install backend/requirements.txt in backend/.venv.\n');
  process.exit(1);
}
process.exit(result.status ?? 1);
