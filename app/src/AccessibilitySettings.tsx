import React, { useState } from 'react';
import { Eye, ZoomIn } from 'lucide-react';

export function AccessibilitySettings() {
  const [highContrast, setHighContrast] = useState(false);
  const [textSize, setTextSize] = useState<'normal' | 'large' | 'xlarge'>('normal');
  const [magnifier, setMagnifier] = useState(false);

  const handleContrastToggle = () => {
    const newMode = !highContrast;
    setHighContrast(newMode);
    if (newMode) {
      document.documentElement.style.setProperty('--background-hsl', '0, 0%, 0%');
      document.documentElement.style.setProperty('--text-hsl', '0, 0%, 100%');
      document.documentElement.style.setProperty('--primary-hsl', '60, 100%, 50%'); // Yellow for contrast
    } else {
      document.documentElement.style.setProperty('--background-hsl', '224, 71%, 4%');
      document.documentElement.style.setProperty('--text-hsl', '210, 40%, 98%');
      document.documentElement.style.setProperty('--primary-hsl', '198, 93%, 60%');
    }
  };

  const handleTextSizeChange = (size: 'normal' | 'large' | 'xlarge') => {
    setTextSize(size);
    const sizeMap = {
      'normal': '16px',
      'large': '20px',
      'xlarge': '24px'
    };
    document.documentElement.style.fontSize = sizeMap[size];
  };

  return (
    <div className="settings-section">
      <h3><Eye size={18} className="icon-inline" /> Accessibility</h3>
      <div className="settings-form">
        <div className="toggle-row">
          <label>High Contrast Mode</label>
          <button
            className={`toggle-btn ${highContrast ? 'active' : ''}`}
            onClick={handleContrastToggle}
            aria-label="High Contrast Mode Toggle"
          >
            {highContrast ? 'On' : 'Off'}
          </button>
        </div>
        <div className="toggle-row">
          <label>Magnifier Tool</label>
          <button
            className={`toggle-btn ${magnifier ? 'active' : ''}`}
            onClick={() => setMagnifier(!magnifier)}
            aria-label="Magnifier Launch Toggle"
          >
            {magnifier ? 'Active' : 'Disabled'}
          </button>
        </div>
        <div className="toggle-row">
          <label>Text Size Boosting</label>
          <div className="size-buttons">
            <button className={textSize === 'normal' ? 'active' : ''} onClick={() => handleTextSizeChange('normal')}>A</button>
            <button className={textSize === 'large' ? 'active' : ''} onClick={() => handleTextSizeChange('large')}>A+</button>
            <button className={textSize === 'xlarge' ? 'active' : ''} onClick={() => handleTextSizeChange('xlarge')}>A++</button>
          </div>
        </div>
      </div>
    </div>
  );
}
