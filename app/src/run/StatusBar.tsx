import React from 'react';
import { Loader2, MessageSquare, ShieldAlert } from 'lucide-react';

interface StatusBarProps {
  isRunning: boolean;
  isAlert: boolean;
  status: string;
}

export function StatusBar({ isRunning, isAlert, status }: StatusBarProps) {
  return (
    <div className={`compact-status-chip ${isAlert ? 'chip-alert' : ''}`}>
      {isAlert ? <ShieldAlert size={12} /> : (isRunning ? <Loader2 className="animate-spin" size={12} /> : <MessageSquare size={12} />)}
      {status || 'READY'}
    </div>
  );
}
