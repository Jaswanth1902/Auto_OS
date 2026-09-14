# AutoOS v2.0: Comprehensive OS Automation & Gateway Architecture

## 1. Executive Summary
AutoOS is a desktop-first automation platform designed to bridge the gap between web-based tasks and local operating system management. The core innovation is a **Unified Gateway** that interprets natural language user input and intelligently routes it to either a Browser Control module (`browser-use` / Playwright) or a Native OS Control module powered by **Win32/UIA Accessibility Inspection and VLM Visual Perception**.

---

## 2. The Unified Gateway (Decision Engine)
The Gateway acts as the "brain" of the application, serving as the single entry point for all user interactions.

### 2.1 Routing Logic
When a user provides input (via text, hotkey, or voice), the Gateway performs the following:
1. **Intent Classification & Risk Scoring**: Analyzes user intent, checks risk boundaries (`SAFE`, `CAUTION`, `DANGEROUS`, `BLOCKED`), and sets `needs_hitl` if state-altering operations are detected.
2. **Request Type Decision**:
   - **Browser Request**: Tasks requiring web navigation, data extraction, or online form filling (e.g., "Check latest flight prices," "Extract table from URL").
   - **OS Request**: Tasks involving local file systems, native desktop software, system diagnostics, or hardware introspection.
   - **Cognitive Request**: Pure knowledge, math, and analytical inquiries.
3. **Hand-off & Execution**:
   - **HITL Check**: If the task is classified as `DANGEROUS` (deleting files, terminating processes, modifying settings), the `hitl_gate` intercepts execution, issues a signed HMAC-SHA256 challenge, and waits for user confirmation in the HUD.
   - **To Browser Control**: Routes to `browser_executor` via Playwright.
   - **To OS Control**: Routes to `os_executor` via native Win32/psutil/pygetwindow primitives.
   - **To Reasoning Core**: Routes to `reasoning_executor`.
4. **Telemetry & Memory Ingestion**:
   - All executions stream to `logger_node` (recording audit trail to `logs/audit_trail.jsonl` and rendering high-craft Rich panels).
   - State and context persist into `memory_consolidator` and SQLite WAL storage.

---

## 3. OS Control Layer (Native Primitives & Grounding)
Unlike traditional brittle automation that relies entirely on full-screen screenshots, AutoOS utilizes a **Hybrid Grounding Architecture**:

### 3.1 Core OS Capabilities
- **Direct Application Management**: Non-blocking window focus, instance de-duplication, and launching via native Win32/UIA APIs without spawning visible terminal windows (`CREATE_NO_WINDOW = 0x08000000`).
- **Context-Aware File Operations**: Automatic path resolution for OneDrive, Desktop, and user libraries with real-time Explorer selection.
- **Safe Mathematical Computation**: AST-grounded arithmetic compiler eliminating `eval()` vulnerabilities.
- **System Health Diagnostics**: Socket-level network latency telemetry, disk usage analysis, battery drain metrics, and peripheral introspection.

### 3.2 Key OS Feature Portfolio
- **Smart Window Focus**: Detects existing application instances via `pygetwindow` and activates them instantly instead of launching redundant processes.
- **Hardware Telemetry**: Proactive monitoring of battery, network latency, and disk thresholds.
- **Local Sovereignty**: All file reads, screen frames, and system metrics remain strictly on the local machine.

---

## 4. Main Desktop Application Architecture
The desktop client is delivered as an Electron + React application encapsulating the Gateway.

### 4.1 Technical Stack
- **Frontend (Electron + React + Vite + Tailwind CSS)**: Provides the tactile Atelier interface, real-time WebSocket execution streams, and HITL confirmation modals.
- **Backend (FastAPI Gateway)**: Unified ASGI server running on port 8765, interfacing with LangGraph and local system buses.
- **Agent Layer (LangGraph State Machine)**:
  - `planner`: Breaks down user queries into sub-categories and confidence metrics.
  - `router`: Dynamic conditional dispatcher evaluating risk and category.
  - `hitl_gate`: Cryptographic gate enforcing human consent on destructive tasks.
  - `browser_executor`: Playwright web automation.
  - `os_executor`: Native desktop automation.
  - `logger_node`: Telemetry, Rich terminal logging, and persistent JSON-L audit trail.
  - `memory_consolidator`: Epistemic memory updating contextual history.

---

## 5. Security & Engineering Invariants
- **CREATE_NO_WINDOW Mandate**: Every `subprocess.Popen` or `subprocess.run` on Windows MUST include `creationflags=0x08000000`. Bare subprocess calls that flash `cmd.exe` windows are strictly forbidden.
- **Zero `eval()` Policy**: User input and mathematical expressions are never evaluated using Python's `eval()`. Only verified AST operator parsers are permitted.
- **Cryptographic Gate**: Destructive OS actions require HMAC-SHA256 signed approval tokens.
- **Zero Jargon**: User-facing responses are translated into plain, actionable language.
