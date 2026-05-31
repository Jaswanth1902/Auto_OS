import { useState, useRef, useEffect, useCallback } from 'react'
import { MessageSquare, Plus, PanelLeftClose, PanelLeftOpen, Send, XCircle, Sparkles, Mic } from 'lucide-react'
import { Message } from './types'

interface ChatViewProps {
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  threadId: string;
  setThreadId: (id: string) => void;
  threadHistory: any[];
  isRunning: boolean;
  status: 'idle' | 'analyzing' | 'executing';
  handleRun: (task: string) => void;
  handleStop: () => void;
}

const CATEGORY_LABELS: Record<string, string> = {
  web_search: 'Web Search',
  web_form: 'Web Form',
  media_playback: 'Media Playback',
  gov_portal: 'Gov Portal',
  file_ops: 'File Operations',
  app_launch: 'App Launch',
  hardware: 'Hardware',
  settings: 'Settings',
  process_mgmt: 'Process',
  security: 'Security',
  diagnostics: 'Diagnostics',
  unknown: 'Unknown',
}

function ChatView({ 
  messages, 
  setMessages, 
  threadId, 
  setThreadId, 
  threadHistory, 
  isRunning, 
  status, 
  handleRun, 
  handleStop 
}: ChatViewProps) {
  const [input, setInput] = useState('')
  const [isSidebarOpen, setIsSidebarOpen] = useState(true)
  const chatEndRef = useRef<HTMLDivElement>(null)

  // ── Voice state ────────────────────────────────────────────────────────────
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const [recordingDuration, setRecordingDuration] = useState(0)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, status])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach(t => t.stop())
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  const onSend = () => {
    if (!input.trim() || isRunning) return
    handleRun(input)
    setInput('')
  }

  const handleNewChat = () => {
    setThreadId("chat-" + Date.now().toString(36))
    setMessages([])
    setInput('')
  }

  // ── Push-to-talk handlers ──────────────────────────────────────────────────
  const startRecording = useCallback(async () => {
    if (isRunning || isRecording) return

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType: MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
          ? 'audio/webm;codecs=opus'
          : 'audio/webm',
      })
      mediaRecorderRef.current = mediaRecorder
      chunksRef.current = []

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data)
      }

      mediaRecorder.start(100) // Collect in 100ms chunks
      setIsRecording(true)
      setRecordingDuration(0)

      // Duration timer
      timerRef.current = setInterval(() => {
        setRecordingDuration(prev => prev + 0.1)
      }, 100)
    } catch (err) {
      console.error('Microphone access error:', err)
      alert('Microphone access denied. Please allow microphone permissions.')
    }
  }, [isRunning, isRecording])

  const stopRecording = useCallback(async () => {
    if (!isRecording || !mediaRecorderRef.current) return

    // Stop timer
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }

    setIsRecording(false)

    // Stop recording and wait for final data
    const recorder = mediaRecorderRef.current
    
    await new Promise<void>((resolve) => {
      recorder.onstop = () => resolve()
      recorder.stop()
    })

    // Stop mic stream
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null

    // Check if we have enough audio
    if (recordingDuration < 0.3) {
      // Too short, ignore
      return
    }

    // Build audio blob and send to backend
    const audioBlob = new Blob(chunksRef.current, { type: 'audio/webm' })
    
    if (audioBlob.size < 500) return // Too small

    setIsTranscribing(true)

    try {
      const formData = new FormData()
      formData.append('audio', audioBlob, 'recording.webm')

      const res = await fetch('http://localhost:8765/voice/transcribe', {
        method: 'POST',
        body: formData,
      })

      const data = await res.json()

      if (res.ok && data.text) {
        // Auto-send the transcribed text as a command
        handleRun(data.text)
      } else {
        console.error('Transcription failed:', data.detail || data)
      }
    } catch (err) {
      console.error('Voice send error:', err)
    } finally {
      setIsTranscribing(false)
      setRecordingDuration(0)
    }
  }, [isRecording, recordingDuration, handleRun])

  // Keyboard shortcut: hold Space to talk (when input not focused)
  useEffect(() => {
    let spaceDown = false

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !spaceDown && document.activeElement?.tagName !== 'INPUT') {
        e.preventDefault()
        spaceDown = true
        startRecording()
      }
    }

    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space' && spaceDown) {
        e.preventDefault()
        spaceDown = false
        stopRecording()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    }
  }, [startRecording, stopRecording])

  const voiceActive = isRecording || isTranscribing

  return (
    <div className="main-layout">
      <aside className={`sidebar ${!isSidebarOpen ? 'collapsed' : ''}`}>
        <button 
          className="toggle-sidebar-btn" 
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
        >
          {isSidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
        </button>

        <button className="new-chat-btn" onClick={handleNewChat}>
          <Plus size={16} /> New Chat
        </button>
        <div className="history-list">
          {threadHistory.map((thread) => (
            <div 
              key={thread.id} 
              className={`history-item ${threadId === thread.id ? 'active' : ''}`}
              onClick={() => { /* Add handler to load thread */ }}
              role="button"
              tabIndex={0}
            >
              <MessageSquare size={14} style={{ marginRight: '8px' }} />
              {thread.preview}
            </div>
          ))}
        </div>
      </aside>

      <main className="app-container">
        <div className="chat-window">
          {messages.length === 0 && (
            <div style={{ marginTop: '20vh', textAlign: 'center', color: '#64748b' }}>
              <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1rem' }}>
                <div style={{ background: 'rgba(14, 165, 233, 0.1)', padding: '1rem', borderRadius: '50%' }}>
                  <Sparkles size={40} color="#0ea5e9" />
                </div>
              </div>
              <h2 style={{ color: '#38bdf8', marginBottom: '0.5rem' }}>AutoOS Gateway</h2>
              <p>Directly control your computer via natural language.</p>
              <p style={{ fontSize: '0.8rem', color: '#475569', marginTop: '0.5rem' }}>
                Hold <kbd style={{ 
                  background: '#1e293b', padding: '2px 8px', borderRadius: '4px', 
                  border: '1px solid #334155', fontSize: '0.75rem' 
                }}>Space</kbd> or the mic button to speak
              </p>
            </div>
          )}

          {messages.map((m: Message) => {
            const safeContent = typeof m.content === 'string'
              ? m.content
              : typeof (m.content as any)?.text === 'string'
              ? (m.content as any).text
              : JSON.stringify(m.content);
            return (
              <div key={m.id} className={`message message-${m.role}`}>
                {m.subCategory && (
                  <div className={`badge badge-${m.type}`}>
                    {CATEGORY_LABELS[m.subCategory] || m.subCategory}
                  </div>
                )}
                {safeContent}
              </div>
            );
          })}

          {status !== 'idle' && (
            <div className="message message-agent">
              <div className="typing-indicator">
                <div className="dot"></div>
                <div className="dot"></div>
                <div className="dot"></div>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* ── Recording overlay — click/release anywhere to stop ─────── */}
        {voiceActive && (
          <div
            className="voice-overlay"
            onMouseUp={stopRecording}
            onTouchEnd={stopRecording}
            onClick={() => { if (isRecording) stopRecording() }}
          >
            <div className="voice-pulse-ring" />
            <div className="voice-pulse-ring delay-1" />
            <div className="voice-pulse-ring delay-2" />
            <div
              className="voice-mic-icon"
              onClick={(e) => { e.stopPropagation(); stopRecording() }}
              style={{ cursor: isRecording ? 'pointer' : 'default' }}
            >
              <Mic size={32} />
            </div>
            <div className="voice-label">
              {isTranscribing
                ? 'Transcribing...'
                : `Listening... ${recordingDuration.toFixed(1)}s`}
            </div>
            {isRecording && (
              <div className="voice-stop-hint" onClick={(e) => { e.stopPropagation(); stopRecording() }}>
                Tap anywhere or click here to send
              </div>
            )}
          </div>
        )}

        {/* ── Input area ─────────────────────────────────────────────────── */}
        <div className="input-area">
          <div className="input-container">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={voiceActive ? 'Listening...' : 'How can I help you today?'}
              disabled={isRunning || voiceActive}
              onKeyDown={(e) => e.key === 'Enter' && onSend()}
              autoFocus
            />

            {/* Mic button and Language Selector */}
            {!isRunning && !voiceActive && (
              <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                <select
                  className="settings-select"
                  aria-label="Prompt Language Selector"
                  style={{ padding: '0.5rem', width: 'auto', minWidth: '80px', borderRadius: '0.75rem' }}
                  defaultValue="en"
                  onChange={(e) => {
                    // Logic to set language preference would go here
                  }}
                >
                  <option value="en">English</option>
                  <option value="hi">Hindi</option>
                  <option value="kn">Kannada</option>
                </select>
                <button
                  className="btn-mic"
                  onMouseDown={startRecording}
                  onMouseUp={stopRecording}
                  onMouseLeave={() => { if (isRecording) stopRecording() }}
                  onTouchStart={(e) => { e.preventDefault(); startRecording() }}
                  onTouchEnd={(e) => { e.preventDefault(); stopRecording() }}
                  title="Hold to talk"
                >
                  <Mic size={18} />
                </button>
              </div>
            )}

            {isRunning ? (
              <button className="btn-stop" onClick={handleStop}><XCircle size={18} /> Stop</button>
            ) : (
              <button className="btn-send" onClick={onSend} disabled={!input.trim() || voiceActive}>
                <Send size={18} />
              </button>
            )}
          </div>
        </div>
      </main>

      {/* ── Voice mode styles ─────────────────────────────────────────────── */}
      <style>{`
        .btn-mic {
          background: transparent;
          border: 1px solid #334155;
          color: #94a3b8;
          width: 40px;
          height: 40px;
          border-radius: 0.75rem;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          transition: all 0.2s;
          flex-shrink: 0;
          user-select: none;
          -webkit-user-select: none;
        }
        .btn-mic:hover {
          border-color: #38bdf8;
          color: #38bdf8;
          background: rgba(56, 189, 248, 0.1);
        }
        .btn-mic:active {
          background: rgba(239, 68, 68, 0.2);
          border-color: #ef4444;
          color: #ef4444;
          transform: scale(0.95);
        }

        .voice-overlay {
          position: absolute;
          inset: 0;
          z-index: 50;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 16px;
          background: rgba(2, 6, 23, 0.92);
          backdrop-filter: blur(12px);
          animation: voiceFadeIn 0.2s ease;
          cursor: pointer;
        }

        @keyframes voiceFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .voice-mic-icon {
          width: 80px;
          height: 80px;
          border-radius: 50%;
          background: linear-gradient(135deg, #ef4444 0%, #f97316 100%);
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
          z-index: 2;
          box-shadow: 0 0 40px rgba(239, 68, 68, 0.4);
        }

        .voice-pulse-ring {
          position: absolute;
          width: 80px;
          height: 80px;
          border-radius: 50%;
          border: 2px solid rgba(239, 68, 68, 0.3);
          animation: voicePulse 2s ease-out infinite;
        }
        .voice-pulse-ring.delay-1 { animation-delay: 0.4s; }
        .voice-pulse-ring.delay-2 { animation-delay: 0.8s; }

        @keyframes voicePulse {
          0% {
            transform: scale(1);
            opacity: 0.6;
          }
          100% {
            transform: scale(3);
            opacity: 0;
          }
        }

        .voice-label {
          font-size: 1.1rem;
          font-weight: 600;
          color: #f8fafc;
          letter-spacing: 0.03em;
          z-index: 2;
        }

        .voice-stop-hint {
          font-size: 0.85rem;
          color: #020617;
          background: rgba(239, 68, 68, 0.9);
          padding: 10px 28px;
          border-radius: 2rem;
          font-weight: 600;
          cursor: pointer;
          z-index: 2;
          margin-top: 8px;
          animation: voiceBlink 1.5s ease-in-out infinite;
          transition: background 0.2s, transform 0.15s;
        }
        .voice-stop-hint:hover {
          background: #ef4444;
          transform: scale(1.05);
        }

        @keyframes voiceBlink {
          0%, 100% { opacity: 0.85; }
          50% { opacity: 1; }
        }
      `}</style>
    </div>
  )
}

export default ChatView
