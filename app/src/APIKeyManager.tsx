import React from 'react';
import { Key } from 'lucide-react';

export function APIKeyManager() {
  return (
    <div className="settings-section">
      <h3><Key size={18} className="icon-inline" /> API Keys</h3>
      <div className="settings-form">
        <label>OpenAI Key</label>
        <input type="password" placeholder="sk-..." className="settings-input" />
        <label>Anthropic Key</label>
        <input type="password" placeholder="sk-ant-..." className="settings-input" />
      </div>
    </div>
  );
}
