# AutoPattern App

## Overview
This is the Electron-React dashboard for AutoPattern. It acts as the command center for monitoring automated workflows, adjusting accessibility settings, testing voice commands, and viewing telemetry logs.

## Styles
The application uses **HSL-based centralized color tokens** defined in `src/index.css`. This ensures a premium glassmorphic dark aesthetic.

**Standard Tokens:**
```css
:root {
  --primary-hsl: 198, 93%, 60%;
  --background-hsl: 224, 71%, 4%;
  --surface-hsl: 224, 71%, 8%;
  --text-hsl: 210, 40%, 98%;
  --border-hsl: 217, 32%, 17%;
}
```

## Context Bridge Channels
To ensure security, the IPC Context Bridge in `electron/preload.js` is strictly whitelisted:

- **Allowed SEND Channels:**
  - `resize-window` (Requires numeric parameters)
  - `face-auth-register`
  - `face-auth-verify`
  - `stop-execution`
  - `run-task`
- **Allowed RECEIVE Channels:**
  - `guardian_alert`
  - `execution_event`

## State Management
- **Dashboard Views:** Routing is handled via `react-router-dom`. State and execution streams are managed primarily at the view-level (e.g. inside `RunView.tsx` or `WorkflowsView.tsx`) to avoid full-tree re-renders on high-frequency updates.
- **WebSockets:** Live task telemetry and guardian alerts rely on WebSocket connections established against `ws://localhost:8765/ws/execution/...`. Components actively track and tear down socket refs during unmounting.

## Extension Telemetry Schema
The Chrome Extension captures high-fidelity browser automation events using a flat structure. This structure is mapped to a backend Canonical Schema via `shared/telemetryMapper.ts`.

**TelemetryEvent Structure:**
```typescript
interface TelemetryEvent {
  event: 'click' | 'input' | 'scroll' | 'navigation' | 'page_visit';
  timestamp: number;
  url: string;
  title: string;
  automation: {
    selector: string | null;  // Prioritizes id, data-testid, aria-label, relative classes
    xpath: string | null;     // Fallback structural path
    tag: string | null;
    inputType: string | null;
  };
  raw?: {
    text?: string;
    value?: string;
    length?: number;
    fieldName?: string;
    y?: number;
  };
}
```
