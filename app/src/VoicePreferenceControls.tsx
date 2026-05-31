import React from 'react';
import { Mic } from 'lucide-react';

export function VoicePreferenceControls() {
  return (
    <div className="settings-section">
      <h3><Mic size={18} className="icon-inline" /> Voice Preferences</h3>
      <div className="settings-form">
        <label>Prompt Language</label>
        <select className="settings-select" aria-label="Prompt Language Selector">
          <option value="en">English</option>
          <option value="hi">Hindi</option>
          <option value="kn">Kannada</option>
        </select>
        <label>Voice Speed</label>
        <input type="range" min="0.5" max="2" step="0.1" defaultValue="1" className="settings-range" />
      </div>
    </div>
  );
}
