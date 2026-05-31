import '@testing-library/jest-dom';

// Mock electronAPI
(global as any).window = Object.create(window);
Object.defineProperty(window, 'electronAPI', {
  value: {
    resizeWindow: jest.fn(),
    sendMessage: jest.fn(),
    onMessage: jest.fn(),
  }
});

// Mock SpeechSynthesis
Object.defineProperty(window, 'speechSynthesis', {
  value: {
    speak: jest.fn(),
    cancel: jest.fn(),
    pause: jest.fn(),
    resume: jest.fn(),
    getVoices: jest.fn(() => []),
  }
});

// Mock SpeechRecognition
(global as any).SpeechRecognition = jest.fn().mockImplementation(() => ({
  start: jest.fn(),
  stop: jest.fn(),
  abort: jest.fn(),
}));
(global as any).webkitSpeechRecognition = (global as any).SpeechRecognition;

// Mock WebSocket
(global as any).WebSocket = jest.fn().mockImplementation(() => ({
  send: jest.fn(),
  close: jest.fn(),
}));

// Mock scrollIntoView
window.HTMLElement.prototype.scrollIntoView = jest.fn();
// Mock alert
window.alert = jest.fn();
// Mock navigator.mediaDevices
Object.defineProperty(navigator, 'mediaDevices', {
  value: {
    getUserMedia: jest.fn().mockResolvedValue({
      getTracks: () => [{ stop: jest.fn() }]
    })
  },
  configurable: true
});
// Mock MediaRecorder
(global as any).MediaRecorder = jest.fn().mockImplementation(() => ({
  start: jest.fn(),
  stop: jest.fn(),
  ondataavailable: jest.fn(),
  onstop: jest.fn()
}));
(global as any).MediaRecorder.isTypeSupported = jest.fn().mockReturnValue(true);
