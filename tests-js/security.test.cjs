const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { isTrustedRendererUrl, isTrustedIpcEvent } = require('../electron/security.cjs');

test('development renderer trust requires the expected origin and path', () => {
  const expected = { devServerUrl: 'http://127.0.0.1:5173/' };
  assert.equal(isTrustedRendererUrl('http://127.0.0.1:5173/', expected), true);
  assert.equal(isTrustedRendererUrl('http://localhost:5173/', expected), false);
  assert.equal(isTrustedRendererUrl('http://127.0.0.1:5173/evil', expected), false);
  assert.equal(isTrustedRendererUrl('https://example.com/', expected), false);
});

test('packaged renderer trust requires the exact local document', () => {
  const file = path.resolve('dist/index.html');
  assert.equal(isTrustedRendererUrl(pathToFileURL(file).href, { packagedIndexPath: file }), true);
  assert.equal(isTrustedRendererUrl('file:///C:/other/index.html', { packagedIndexPath: file }), false);
});

test('IPC trust requires the main frame and its trusted renderer URL', () => {
  const frame = { url: 'http://127.0.0.1:5173/' };
  const webContents = { mainFrame: frame };
  const win = { webContents };
  const event = { sender: webContents, senderFrame: frame };
  assert.equal(isTrustedIpcEvent(event, win, { devServerUrl: 'http://127.0.0.1:5173/' }), true);
  assert.equal(isTrustedIpcEvent({ ...event, sender: {} }, win, { devServerUrl: 'http://127.0.0.1:5173/' }), false);
  assert.equal(isTrustedIpcEvent({ ...event, senderFrame: { url: 'https://example.com/' } }, win, { devServerUrl: 'http://127.0.0.1:5173/' }), false);
});
