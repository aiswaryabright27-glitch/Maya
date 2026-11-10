const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('mayaDesktop', Object.freeze({
  getHealth: () => ipcRenderer.invoke('maya:health'),
  transcribe: (payload) => ipcRenderer.invoke('maya:transcribe', payload),
  cancelSpeech: (requestId) => ipcRenderer.invoke('maya:cancel-speech', requestId),
  startConversation: (payload) => ipcRenderer.send('maya:start-conversation', payload),
  onConversationEvent: (callback) => {
    const listener = (_event, payload) => callback(payload);
    ipcRenderer.on('maya:conversation-event', listener);
    return () => ipcRenderer.removeListener('maya:conversation-event', listener);
  },
  onHotkey: (callback) => {
    const listener = () => callback();
    ipcRenderer.on('maya:hotkey', listener);
    return () => ipcRenderer.removeListener('maya:hotkey', listener);
  },
}));
