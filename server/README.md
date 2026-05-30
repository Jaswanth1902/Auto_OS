# AutoOS Gateway API

This directory contains the core backend systems, FastAPI gateway, and voice transcription utilities.

## Setup

1. Make sure dependencies are synced via `uv`.
   ```bash
   uv pip install -r requirements.txt
   ```
2. Start the database by seeding workflows:
   ```bash
   python ../scripts/seed_workflows.py
   ```
3. Run the development server:
   ```bash
   uvicorn main:app --port 8765 --reload
   ```

## Modular Routers

- `/workflows`: CRUD operations for workflows
- `/executions`: Trigger, cancel, and retrieve LangGraph executions (includes WebSockets)
- `/system/threads`: AI agent conversation threads storage
- `/system`: System health and proactive background daemons
- `/voice`: Speech-to-text transcription endpoints
- `/face_auth`: Face registration and verification

## WebSocket Contracts

Connect via WebSocket to `/ws/execution/{execution_id}`.

### Client Messages (Send)

```json
// Start a new task
{
  "type": "start",
  "task": "Open chrome and go to google",
  "headless": true
}

// Stop the running task
{
  "type": "stop"
}
```

### Server Messages (Receive)

```json
// The task was stopped by the user or client
{
  "type": "stopped",
  "message": "Task stopped by user."
}

// An error occurred during the step
{
  "type": "step_error",
  "error": "Timeout waiting for page load."
}

// A proactive warning from the guardian daemon
{
  "type": "guardian_alert",
  "message": "High CPU Load detected (95%). Suggest closing background apps."
}
```

## Database Models (SQLModel)

Located in `models/`. Standard setup uses SQLite (`autoflow.db`) locally.

- `Workflow`: Contains definitions and run configs for standard tasks.
- `Execution`: Represents a specific run of an agent plan over a workflow. Maps to LangGraph state IDs.

## Logging

Logging is automatically routed to both colored stdout and a rotating file system in the `server/logs/` directory:
- `api.log`: FastAPI requests and general endpoints
- `agent.log`: LangGraph intent planner and node executions
- `database.log`: SQLModel transaction errors
