const path = require('node:path');
const { pathToFileURL } = require('node:url');

function isTrustedRendererUrl(candidate, { devServerUrl, packagedIndexPath }) {
  if (typeof candidate !== 'string') return false;
  if (devServerUrl) {
    try {
      const actual = new URL(candidate);
      const expected = new URL(devServerUrl);
      return actual.origin === expected.origin && actual.pathname === expected.pathname;
    } catch {
      return false;
    }
  }
  if (!packagedIndexPath) return false;
  try {
    return candidate === pathToFileURL(path.resolve(packagedIndexPath)).href;
  } catch {
    return false;
  }
}

function isTrustedIpcEvent(event, mainWindow, expectedUrl) {
  return Boolean(
    mainWindow &&
    event.sender === mainWindow.webContents &&
    event.senderFrame === mainWindow.webContents.mainFrame &&
    isTrustedRendererUrl(event.senderFrame.url, expectedUrl),
  );
}

module.exports = { isTrustedRendererUrl, isTrustedIpcEvent };
