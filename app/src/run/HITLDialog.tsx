import React from 'react';

interface HITLDialogProps {
  onDismiss: () => void;
}

export function HITLDialog({ onDismiss }: HITLDialogProps) {
  return (
    <div className="compact-input-area">
      <button className="dismiss-btn" onClick={onDismiss}>DISMISS</button>
    </div>
  );
}
