const { contextBridge, ipcRenderer } = require('electron');

const ALLOWED_SEND_CHANNELS = ['resize-window', 'face-auth-register', 'face-auth-verify', 'stop-execution', 'run-task'];
const ALLOWED_RECEIVE_CHANNELS = ['guardian_alert', 'execution_event'];

contextBridge.exposeInMainWorld('electronAPI', {
  sendMessage: (channel, data) => {
    if (ALLOWED_SEND_CHANNELS.includes(channel)) {
      ipcRenderer.send(channel, data);
    } else {
      console.warn(`IPC channel not allowed for sending: ${channel}`);
    }
  },
  onMessage: (channel, func) => {
    if (ALLOWED_RECEIVE_CHANNELS.includes(channel)) {
      // Deliberately strip event as it includes `sender`
      ipcRenderer.on(channel, (event, ...args) => func(...args));
    } else {
      console.warn(`IPC channel not allowed for receiving: ${channel}`);
    }
  },
  resizeWindow: (width, height) => {
    if (typeof width === 'number' && typeof height === 'number') {
      ipcRenderer.send('resize-window', { width, height });
    } else {
      console.warn('resizeWindow requires numbers');
    }
  },
});
