import React from 'react';
import { Settings as SettingsIcon } from 'lucide-react';
import { APIKeyManager } from './APIKeyManager';
import { VoicePreferenceControls } from './VoicePreferenceControls';
import { AccessibilitySettings } from './AccessibilitySettings';

export default function SettingsView() {
  return (
    <div className="view-container fade-in">
      <div className="view-header">
        <div className="title-group">
          <SettingsIcon className="text-glow" size={24} />
          <h2>System Settings</h2>
        </div>
      </div>

      <div className="settings-grid">
        <APIKeyManager />
        <VoicePreferenceControls />
        <AccessibilitySettings />
      </div>
    </div>
  );
}
