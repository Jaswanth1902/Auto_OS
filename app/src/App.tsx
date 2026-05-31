import { useState, useEffect, useRef, useCallback } from 'react';
import { HashRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { 
  MessageSquare, 
  LayoutDashboard, 
  Settings, 
  User, 
  Loader2, 
  XCircle, 
  ShieldAlert, 
  Puzzle, 
  Maximize2, 
  Send,
  Zap
} from 'lucide-react';
import ChatView from './ChatView';
import DashboardView from './DashboardView';
import SkillsView from './SkillsView';
import WorkflowsView from './workflows/WorkflowsView';
import SettingsView from './SettingsView';
import RunView from './run/RunView';
import { Message } from './types';
import './index.css';

import { FaceAuthModal } from './FaceAuthModal';

// --- Shared Types ---
declare global {
  interface Window {
    electronAPI: {
      resizeWindow: (w: number, h: number) => void;
      sendMessage: (channel: string, data: any) => void;
      onMessage: (channel: string, func: (...args: any[]) => void) => void;
    }
  }
}

function SidebarDock() {
  const location = useLocation();
  return (
    <nav className="side-dock">
      <div className="dock-top">
        <Link to="/" className={`dock-item ${location.pathname === '/' ? 'active' : ''}`} title="Chat Assistant">
          <MessageSquare size={24} />
        </Link>
        <Link to="/dashboard" className={`dock-item ${location.pathname === '/dashboard' ? 'active' : ''}`} title="System Dashboard">
          <LayoutDashboard size={24} />
        </Link>
        <Link to="/workflows" className={`dock-item ${location.pathname === '/workflows' ? 'active' : ''}`} title="Automated Workflows">
          <Zap size={24} />
        </Link>
        <Link to="/skills" className={`dock-item ${location.pathname === '/skills' ? 'active' : ''}`} title="Skills Marketplace">
          <Puzzle size={24} />
        </Link>
      </div>
      <div className="dock-bottom">
        <Link to="/settings" className={`dock-item ${location.pathname === '/settings' ? 'active' : ''}`} title="Settings">
          <Settings size={24} />
        </Link>
        <div className="dock-item user-avatar" title="Account">
          <User size={24} />
        </div>
      </div>
    </nav>
  );
}

function App() {
  // --- Global State ---
  const [messages, setMessages] = useState<Message[]>([]);
  const [threadId, setThreadId] = useState<string>('');
  const [threadHistory, setThreadHistory] = useState<any[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState<'idle' | 'analyzing' | 'executing'>('idle');

  // Compact state controls only visibility and basic type in App.tsx
  const [isCompact, setIsCompact] = useState(false);
  const [compactType, setCompactType] = useState<'alert' | 'task' | undefined>('task');
  
  // --- Face Auth State ---
  const [faceRegistered, setFaceRegistered] = useState(false);
  const [faceAuthAction, setFaceAuthAction] = useState<{ mode: 'register' } | { mode: 'verify', task: string, workflow: any } | null>(null);

  // Ref for the latest task to run so RunView can pick it up
  const [taskToRun, setTaskToRun] = useState<string | null>(null);
  // Ref to hold a function from RunView to execute the task
  const executeRunTaskRef = useRef<((task: string) => void) | null>(null);

  // --- Guardian Heartbeat ---
  useEffect(() => {
    let reconnectTimeout: ReturnType<typeof setTimeout> | null = null;
    let isMounted = true;
    let guardianWs: WebSocket | null = null;

    const connect = () => {
      if (!isMounted) return;
      guardianWs = new WebSocket(`ws://localhost:8765/ws/execution/global_guardian`);
      guardianWs.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'guardian_alert') {
            setCompactType('alert');
            setIsCompact(true);
            // In a real app we'd dispatch to RunView, but for now we just show it
            window.electronAPI?.resizeWindow(480, 180);
          }
        } catch (e) {
          console.error('Failed to parse guardian message:', e);
        }
      };
      guardianWs.onerror = () => guardianWs?.close();
      guardianWs.onclose = () => {
        if (isMounted) reconnectTimeout = setTimeout(connect, 3000);
      };
    };
    connect();
    return () => {
      isMounted = false;
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
      guardianWs?.close();
    };
  }, []);

  useEffect(() => {
    fetch('http://localhost:8765/api/face-auth/status')
      .then(res => res.json())
      .then(data => setFaceRegistered(data.registered))
      .catch(console.error);
  }, []);

  const addMessage = useCallback((role: Message['role'], content: string, extra?: Record<string, any>) => {
    const msg: Message = {
      id: Math.random().toString(36).slice(2, 8),
      role,
      content,
      ...extra,
    };
    setMessages(prev => [...prev, msg]);
  }, []);

  // --- Initial Hydration ---
  useEffect(() => {
    const loadLatest = async () => {
      try {
        const res = await fetch('http://localhost:8765/system/threads/latest');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.id) {
          setThreadId(data.id);
          setMessages(data.messages || []);
        }
        const historyRes = await fetch('http://localhost:8765/system/threads');
        if (!historyRes.ok) throw new Error(`HTTP ${historyRes.status}`);
        setThreadHistory(await historyRes.json());
      } catch (e) { console.error(e); }
    };
    loadLatest();
  }, []);

  // --- Persistence Sync ---
  useEffect(() => {
    let timeoutId: ReturnType<typeof setTimeout>;
    if (threadId && messages.length > 0) {
      timeoutId = setTimeout(() => {
        const sync = async () => {
          try {
            await fetch('http://localhost:8765/system/threads/save', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ id: threadId, messages })
            });
            const hRes = await fetch('http://localhost:8765/system/threads');
            if (hRes.ok) {
              setThreadHistory(await hRes.json());
            }
          } catch (e) {
            console.error('Persistence sync failed:', e);
          }
        };
        sync();
      }, 1000);
    }
    return () => { if (timeoutId) clearTimeout(timeoutId); };
  }, [threadId, messages]);

  const updateCompact = useCallback((isCompactActive: boolean) => {
    setIsCompact(isCompactActive);
    if (isCompactActive) window.electronAPI?.resizeWindow(480, 180);
    else window.electronAPI?.resizeWindow(900, 700);
  }, []);

  // This is the function called from ChatView, DashboardView, WorkflowsView
  const handleRun = async (taskStr: string) => {
    if (!taskStr.trim() || isRunning) return;
    
    // Set up app state immediately to show it's running
    setIsRunning(true);
    setStatus('analyzing');
    addMessage('user', taskStr);

    // If RunView provides an execution function, use it, otherwise set the state to pass down
    if (executeRunTaskRef.current) {
        executeRunTaskRef.current(taskStr);
    } else {
        setTaskToRun(taskStr);
    }
  };

  // Ref to hold the stop function from RunView
  const executeStopTaskRef = useRef<(() => void) | null>(null);

  const handleStop = async () => {
    if (executeStopTaskRef.current) {
        executeStopTaskRef.current();
    }
    setIsRunning(false);
    setStatus('idle');
  };

  return (
    <div className="app-root">
      {(isCompact || isRunning) && (
        <RunView
          isCompact={isCompact}
          setIsCompact={updateCompact}
          compactType={compactType}
          setCompactType={setCompactType}
          messages={messages}
          addMessage={addMessage}
          isRunning={isRunning}
          setIsRunning={setIsRunning}
          setStatus={setStatus}
          taskToRun={taskToRun}
          setTaskToRun={setTaskToRun}
          executeRunTaskRef={executeRunTaskRef}
          executeStopTaskRef={executeStopTaskRef}
        />
      )}

      <div className="main-app-container" style={{ display: isCompact ? 'none' : 'block' }}>
          <div className="root-layout">
            <SidebarDock />
            <div className="content-area">
              <Routes>
                <Route path="/" element={
                  <ChatView 
                    messages={messages} 
                    setMessages={setMessages} 
                    threadId={threadId} 
                    setThreadId={setThreadId}
                    threadHistory={threadHistory}
                    isRunning={isRunning}
                    status={status}
                    handleRun={handleRun}
                    handleStop={handleStop}
                  />
                } />
                <Route path="/dashboard" element={<DashboardView />} />
                <Route path="/workflows" element={<WorkflowsView handleRun={handleRun} isRunning={isRunning} faceRegistered={faceRegistered} setFaceAuthAction={setFaceAuthAction} />} />
                <Route path="/skills" element={<SkillsView />} />
                <Route path="/settings" element={<SettingsView />} />
              </Routes>
            </div>
          </div>
      </div>

      {/* --- Face Auth Modal --- */}
      {faceAuthAction && (
        <FaceAuthModal
          mode={faceAuthAction.mode}
          onCancel={() => setFaceAuthAction(null)}
          onSuccess={() => {
            if (faceAuthAction.mode === 'register') {
              setFaceRegistered(true);
              setFaceAuthAction(null);
            } else if (faceAuthAction.mode === 'verify') {
              // Dispatch event so WorkflowsView can start the workflow sequence
              window.dispatchEvent(new CustomEvent('face-verified', { detail: faceAuthAction }));
              setFaceAuthAction(null);
            }
          }}
        />
      )}
    </div>
  );
}

export default App;
