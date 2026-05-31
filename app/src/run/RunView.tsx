import React, { useState, useEffect, useRef } from 'react';
import { Maximize2, XCircle, Send } from 'lucide-react';
import { StatusBar } from './StatusBar';
import { LiveTermLog } from './LiveTermLog';
import { HITLDialog } from './HITLDialog';
import { Message } from '../types';

interface RunViewProps {
  isCompact: boolean;
  setIsCompact: (val: boolean) => void;
  compactType?: 'alert' | 'task';
  setCompactType: React.Dispatch<React.SetStateAction<'alert' | 'task' | undefined>>;
  messages: Message[];
  addMessage: (role: Message['role'], content: string, extra?: Record<string, any>) => void;
  isRunning: boolean;
  setIsRunning: React.Dispatch<React.SetStateAction<boolean>>;
  setStatus: React.Dispatch<React.SetStateAction<'idle' | 'analyzing' | 'executing'>>;
  taskToRun: string | null;
  setTaskToRun: React.Dispatch<React.SetStateAction<string | null>>;
  executeRunTaskRef: React.MutableRefObject<((task: string) => void) | null>;
  executeStopTaskRef: React.MutableRefObject<(() => void) | null>;
}

export default function RunView({
  isCompact,
  setIsCompact,
  compactType,
  setCompactType,
  messages,
  addMessage,
  isRunning,
  setIsRunning,
  setStatus,
  taskToRun,
  setTaskToRun,
  executeRunTaskRef,
  executeStopTaskRef
}: RunViewProps) {
  const [miniInput, setMiniInput] = useState('');

  // Local state for fast updates without triggering App.tsx re-renders
  const [localStatus, setLocalStatus] = useState<string>('');
  const [localDesc, setLocalDesc] = useState<string>('');
  const localDescRef = useRef(localDesc);

  const wsRef = useRef<WebSocket | null>(null);
  const executionIdRef = useRef<string | null>(null);

  // Update local desc when guardian triggers it from outside (App.tsx setting compactType='alert')
  useEffect(() => {
    if (compactType === 'alert') {
      setLocalStatus('GUARDIAN ALERT');
      // In a more robust system, App.tsx would pass the actual alert message down.
      // We will leave it as 'Guardian alert active' for now if localDesc is empty.
      if (!localDesc) setLocalDesc('System requires your attention.');
    }
  }, [compactType]);

  // Expose methods to App.tsx via refs
  useEffect(() => {
    executeRunTaskRef.current = (taskStr: string) => {
      setIsCompact(isCompact);
      setLocalStatus('ANALYZING');
      setLocalDesc('Thinking...');
      startExecution(taskStr);
    };

    executeStopTaskRef.current = () => {
      if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: 'stop' }));
      if (executionIdRef.current) {
        fetch(`http://localhost:8765/executions/${executionIdRef.current}/stop`, { method: 'POST' }).catch(() => {});
      }
      setLocalStatus('IDLE');
      setLocalDesc('Task cancelled.');
      addMessage('system', 'Execution stopped.');
    };

    return () => {
      executeRunTaskRef.current = null;
      executeStopTaskRef.current = null;
    };
  }, [isCompact, setIsCompact, addMessage]);

  // Handle tasks passed via state (e.g. from initial setup)
  useEffect(() => {
    if (taskToRun) {
      setTaskToRun(null);
      setIsCompact(isCompact);
      setLocalStatus('ANALYZING');
      setLocalDesc('Thinking...');
      startExecution(taskToRun);
    }
  }, [taskToRun, setTaskToRun, isCompact, setIsCompact]);

  const startExecution = (taskStr: string) => {
      fetch('http://localhost:8765/executions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ task: taskStr })
      })
      .then(res => res.json())
      .then(data => {
        executionIdRef.current = data.id;
        wsRef.current = new WebSocket(`ws://localhost:8765/ws/execution/${data.id}`);

        wsRef.current.onopen = () => wsRef.current?.send(JSON.stringify({ type: 'start', task: taskStr }));

        wsRef.current.onerror = () => {
           setIsRunning(false);
           setStatus('idle');
           setLocalStatus('ERROR');
           setLocalDesc('WebSocket connection error');
           wsRef.current = null;
        };
        wsRef.current.onclose = () => {
           wsRef.current = null;
        };

        wsRef.current.onmessage = (event) => {
          let msg;
          try {
            msg = JSON.parse(event.data);
          } catch (e) {
            console.error("Malformed websocket message:", e);
            return;
          }

          switch (msg.type) {
            case 'classification':
              setStatus('executing');
              if (msg.plain_english_plan) {
                setIsCompact(true);
                setLocalStatus('EXECUTING');
                setLocalDesc(msg.plain_english_plan);
                addMessage('agent', msg.plain_english_plan, { type: 'info' });
              }
              break;
            case 'complete':
              addMessage('agent', msg.summary);
              setIsRunning(false);
              setStatus('idle');
              setLocalStatus('');
              setLocalDesc(msg.summary);
              break;
            case 'step_error':
              addMessage('system', `Error: ${msg.error}`);
              setIsRunning(false);
              setStatus('idle');
              setLocalStatus('ERROR');
              setLocalDesc(msg.error);
              break;
          }
        };
      })
      .catch(e => {
        addMessage('system', 'Failed to connect to backend.');
        setIsRunning(false);
        setStatus('idle');
        setLocalStatus('ERROR');
        setLocalDesc(String(e));
      });
  };

  const handleMiniRun = async () => {
    const taskStr = miniInput;
    if (!taskStr.trim() || isRunning) return;
    setMiniInput('');
    setIsRunning(true);
    setStatus('analyzing');
    addMessage('user', taskStr);

    setIsCompact(isCompact);
    setLocalStatus('ANALYZING');
    setLocalDesc('Thinking...');
    startExecution(taskStr);
  };

  const handleDismiss = () => {
      setIsCompact(false);
      setCompactType('task');
  };

  const isAlert = compactType === 'alert';

  // Only render the compact popup if it's supposed to be compact
  if (!isCompact) {
    return null;
  }

  return (
    <div className={`compact-popup ${isAlert ? 'alert-mode' : ''}`}>
      <div className="compact-header">
        <div className="compact-top-bar">
          <StatusBar isRunning={isRunning} isAlert={isAlert} status={localStatus} />
          {!isAlert && <button className="compact-action-btn" onClick={() => setIsCompact(false)}><Maximize2 size={14} /></button>}
        </div>
        <LiveTermLog description={localDesc || (messages.length > 0 ? messages[messages.length-1].content : 'Waiting...')} />
      </div>

      {isAlert ? (
        <HITLDialog onDismiss={handleDismiss} />
      ) : (
        <div className="compact-input-area">
          <div className="compact-input-box">
            <input
              value={miniInput}
              onChange={(e) => setMiniInput(e.target.value)}
              placeholder={isRunning ? "Working..." : "Next instruction..."}
              disabled={isRunning}
              onKeyDown={(e) => e.key === 'Enter' && handleMiniRun()}
            />
            {isRunning ? (
              <button className="compact-stop-btn" onClick={() => executeStopTaskRef.current?.()}><XCircle size={18} /></button>
            ) : (
              <button className="compact-send-btn" onClick={handleMiniRun} disabled={!miniInput.trim()}><Send size={18} /></button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
