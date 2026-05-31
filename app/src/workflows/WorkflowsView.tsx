import { useState, useEffect } from 'react';
import { X, Save, Trash2, ListPlus, Loader2 } from 'lucide-react';
import { WorkflowGrid } from './WorkflowGrid';
import { ImportExportControls } from './ImportExportControls';
import { Workflow } from './types';

interface WorkflowsViewProps {
  handleRun: (task: string) => Promise<void>;
  isRunning: boolean;
  faceRegistered?: boolean;
  setFaceAuthAction?: (action: any) => void;
}

const GRADIENTS = [
  "linear-gradient(135deg, #38bdf8 0%, #818cf8 100%)",
  "linear-gradient(135deg, #10b981 0%, #3b82f6 100%)",
  "linear-gradient(135deg, #f59e0b 0%, #ef4444 100%)",
  "linear-gradient(135deg, #8b5cf6 0%, #ec4899 100%)",
  "linear-gradient(135deg, #06b6d4 0%, #8b5cf6 100%)"
];

export default function WorkflowsView({ handleRun, isRunning, faceRegistered, setFaceAuthAction }: WorkflowsViewProps) {
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [activeWorkflow, setActiveWorkflow] = useState<string | null>(null);
  const [currentStep, setCurrentStep] = useState(0);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [wfName, setWfName] = useState('');
  const [wfDesc, setWfDesc] = useState('');
  const [wfSteps, setWfSteps] = useState<string[]>(['']);

  useEffect(() => {
    const handleFaceVerified = (e: any) => {
      const { mode, workflow } = e.detail;
      if (mode === 'verify' && workflow) {
        executeWorkflowSteps(workflow);
      }
    };
    window.addEventListener('face-verified', handleFaceVerified);
    return () => window.removeEventListener('face-verified', handleFaceVerified);
  }, [isRunning]);

  const fetchWorkflows = async () => {
    try {
      const res = await fetch('http://localhost:8765/system/workflows');
      const data = await res.json();
      setWorkflows(data);
    } catch (e) {
      console.error('Failed to load workflows', e);
    }
  };

  useEffect(() => {
    fetchWorkflows();
  }, []);

  const handleSaveWorkflow = async (wfData?: any) => {
    const data = wfData || {
      id: "wf_" + Date.now().toString(36),
      name: wfName,
      description: wfDesc,
      steps: wfSteps.filter(s => s.trim() !== ''),
      color: GRADIENTS[Math.floor(Math.random() * GRADIENTS.length)]
    };

    try {
      await fetch('http://localhost:8765/system/workflows/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      setIsModalOpen(false);
      setWfName('');
      setWfDesc('');
      setWfSteps(['']);
      fetchWorkflows();
    } catch (e) {
      console.error('Failed to save workflow', e);
    }
  };

  const exportWorkflow = (wf: Workflow) => {
    const dataStr = JSON.stringify(wf, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    const exportFileDefaultName = `${wf.name.toLowerCase().replace(/\s+/g, '_')}_routine.json`;

    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  const importWorkflow = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (e) => {
      try {
        const content = e.target?.result as string;
        const importedWf = JSON.parse(content);
        importedWf.id = "imported_" + Date.now().toString(36);
        await handleSaveWorkflow(importedWf);
      } catch (err) {
        alert("Invalid workflow file format.");
      }
    };
    reader.readAsText(file);
    event.target.value = '';
  };

  const executeWorkflowSteps = async (wf: Workflow) => {
    if (isRunning) return;
    setActiveWorkflow(wf.id);
    setCurrentStep(0);

    for (let i = 0; i < wf.steps.length; i++) {
      setCurrentStep(i);
      try {
        await handleRun(wf.steps[i]);
      } catch (e) {
        console.error(`Workflow step ${i} failed`, e);
        break;
      }
      await new Promise(resolve => setTimeout(resolve, 2000)); 
    }
    
    setActiveWorkflow(null);
    setCurrentStep(0);
  };

  const runWorkflow = async (wf: Workflow) => {
    if (!setFaceAuthAction) {
      executeWorkflowSteps(wf);
      return;
    }
    if (!faceRegistered) {
      alert('Face authentication is required to run workflows.\n\nPlease click "Register Face" to set up your face ID first.');
      return;
    }
    setFaceAuthAction({ mode: 'verify', task: '', workflow: wf });
  };

  return (
    <div className="workflows-container">
      <header className="view-header">
        <div>
          <h1>Automated Workflows</h1>
          <p>Execute complex routines with a single click.</p>
        </div>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            {setFaceAuthAction && (
                <button
                className="import-wf-btn"
                onClick={() => setFaceAuthAction({ mode: 'register' })}
                style={!faceRegistered ? { borderColor: '#f59e0b', color: '#f59e0b' } : {}}
                title={!faceRegistered ? 'Register your face to enable workflow authentication' : 'Update registered face'}
                >
                {faceRegistered ? '✓ Re-register Face' : '⚠ Register Face'}
                </button>
            )}
            <ImportExportControls onImport={importWorkflow} onNewWorkflow={() => setIsModalOpen(true)} />
        </div>
      </header>

      <WorkflowGrid
        workflows={workflows}
        activeWorkflow={activeWorkflow}
        currentStep={currentStep}
        isRunning={isRunning}
        onExport={exportWorkflow}
        onRun={runWorkflow}
      />

      {isModalOpen && (
        <div className="modal-overlay">
          <div className="workflow-modal">
            <header className="modal-header">
              <div className="header-title">
                <div className="icon-box"><ZapIcon size={20} color="#38bdf8" /></div>
                <div>
                  <h2>Create New Routine</h2>
                  <p>Define a sequence of instructions.</p>
                </div>
              </div>
              <button className="close-modal-btn" onClick={() => setIsModalOpen(false)}>
                <X size={20} />
              </button>
            </header>

            <div className="modal-body">
              <div className="input-group">
                <label>Routine Name</label>
                <input 
                  placeholder="e.g. Morning Startup" 
                  value={wfName}
                  onChange={(e) => setWfName(e.target.value)}
                />
              </div>
              <div className="input-group">
                <label>Description</label>
                <input 
                  placeholder="What does this workflow do?" 
                  value={wfDesc}
                  onChange={(e) => setWfDesc(e.target.value)}
                />
              </div>

              <div className="steps-builder">
                <div className="builder-header">
                  <label>Automation Steps</label>
                  <button className="add-step-btn" onClick={() => setWfSteps([...wfSteps, ''])}>
                    <ListPlus size={14} /> Add Step
                  </button>
                </div>
                <div className="steps-list-edit">
                  {wfSteps.map((step, i) => (
                    <div key={i} className="step-input-row">
                      <div className="step-num">{i + 1}</div>
                      <input 
                        value={step}
                        onChange={(e) => {
                          const newSteps = [...wfSteps];
                          newSteps[i] = e.target.value;
                          setWfSteps(newSteps);
                        }}
                        placeholder="Type an instruction (e.g. Open Spotify)"
                      />
                      <button 
                        className="remove-step-btn" 
                        onClick={() => setWfSteps(wfSteps.filter((_, idx) => idx !== i))}
                        disabled={wfSteps.length === 1}
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            <footer className="modal-footer">
              <button className="cancel-btn" onClick={() => setIsModalOpen(false)}>Cancel</button>
              <button className="save-wf-btn" onClick={() => handleSaveWorkflow()} disabled={!wfName.trim()}>
                <Save size={18} /> Save Routine
              </button>
            </footer>
          </div>
        </div>
      )}
    </div>
  );
}

function ZapIcon({ size, color }: { size: number, color: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
    </svg>
  );
}
