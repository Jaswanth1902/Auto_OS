import React, { useRef } from 'react';
import { Upload, Plus } from 'lucide-react';

interface ImportExportControlsProps {
  onImport: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onNewWorkflow: () => void;
}

export function ImportExportControls({ onImport, onNewWorkflow }: ImportExportControlsProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImportClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className="header-actions">
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: 'none' }}
        accept=".json"
        onChange={onImport}
      />
      <button className="import-wf-btn" onClick={handleImportClick}>
        <Upload size={18} /> Import
      </button>
      <button className="create-wf-btn" onClick={onNewWorkflow}>
        <Plus size={18} /> New Workflow
      </button>
    </div>
  );
}
