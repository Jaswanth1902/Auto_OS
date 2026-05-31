import React from 'react';
import { Download, Play, Loader2, ArrowRight, CheckCircle2 } from 'lucide-react';
import { Workflow } from './types';

interface WorkflowCardProps {
  wf: Workflow;
  activeWorkflow: string | null;
  currentStep: number;
  isRunning: boolean;
  onExport: (wf: Workflow) => void;
  onRun: (wf: Workflow) => void;
}

export function WorkflowCard({ wf, activeWorkflow, currentStep, isRunning, onExport, onRun }: WorkflowCardProps) {
  return (
    <div className={`workflow-card ${activeWorkflow === wf.id ? 'running' : ''}`}>
      <div className="card-gradient" style={{ background: wf.color }} />
      <div className="card-content">
        <div className="card-top-actions">
           <h3>{wf.name}</h3>
           <button className="export-mini-btn" title="Export Workflow" onClick={() => onExport(wf)}>
              <Download size={14} />
           </button>
        </div>
        <p>{wf.description}</p>
        <div className="steps-preview">
          {wf.steps.map((step, i) => (
            <div key={i} className={`step-item ${activeWorkflow === wf.id && i === currentStep ? 'active' : ''} ${activeWorkflow === wf.id && i < currentStep ? 'done' : ''}`}>
              {activeWorkflow === wf.id && i < currentStep ? <CheckCircle2 size={14} color="#10b981" /> : (activeWorkflow === wf.id && i === currentStep ? <Loader2 size={14} className="animate-spin" /> : <ArrowRight size={14} />)}
              {step}
            </div>
          ))}
        </div>
        <button
          className="run-btn"
          onClick={() => onRun(wf)}
          disabled={isRunning && activeWorkflow !== wf.id}
        >
          {activeWorkflow === wf.id ? <Loader2 className="animate-spin" /> : <Play size={18} fill="currentColor" />}
          {activeWorkflow === wf.id ? 'Running...' : 'Run Routine'}
        </button>
      </div>
    </div>
  );
}
