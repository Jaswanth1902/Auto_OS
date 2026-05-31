import React from 'react';
import { WorkflowCard } from './WorkflowCard';
import { Workflow } from './types';

interface WorkflowGridProps {
  workflows: Workflow[];
  activeWorkflow: string | null;
  currentStep: number;
  isRunning: boolean;
  onExport: (wf: Workflow) => void;
  onRun: (wf: Workflow) => void;
}

export function WorkflowGrid({ workflows, activeWorkflow, currentStep, isRunning, onExport, onRun }: WorkflowGridProps) {
  return (
    <div className="workflows-grid">
      {workflows.map((wf) => (
        <WorkflowCard
          key={wf.id}
          wf={wf}
          activeWorkflow={activeWorkflow}
          currentStep={currentStep}
          isRunning={isRunning}
          onExport={onExport}
          onRun={onRun}
        />
      ))}
    </div>
  );
}
