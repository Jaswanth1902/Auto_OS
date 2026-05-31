# Browser Agent Tools

This directory contains modules for the browser automation engine, specifically designed around `browser-use` and `playwright`.

## Modules Overview

- `browser_tool.py`: Main orchestration wrapper that configures Playwright contexts, timeouts, injects credentials securely, and dispatches the main agent loop.
- `browser_utils.py`: Contains robust helper methods for core DOM interactions (`robust_click`, `robust_fill`, `verify_text`, etc.) which retry on transient failures like visibility locks or stale element references.
- `selectors.py`: A centralized registry mapping logical application scopes (like `gov_portal` or `login`) to explicit DOM selector queries.

## Guidelines & Parameters

### Browser Selector Guidelines
- Always decouple low-level selectors (CSS or XPath) into `selectors.py`.
- Prefer robust semantic selectors (like `id` or specific `name`/`type` combinations) over brittle path-based XPaths.
- Example: `#user_email` or `input[type="email"]` over `div > form > input:nth-child(1)`.

### State Initialization Parameters
- **Timeout Defaults:** To avoid session-timeout errors, standard implicit waits are bumped to `30000ms` explicitly for the context instance.
- **Sensitive Data Injection:** Uses the `<secret>` prompt format in tasks to dynamically place values corresponding to matching field contexts.
- **Headless Options:** Always support dynamic headless configurations via `BROWSER_HEADLESS` environment variable for robust deployment matching.
- **Downloads Support:** Explicit absolute downloads are enabled by default and configured to redirect payloads to `server/downloads/`.

### Anti-Bot Mitigation Patterns
- We rely on `playwright` with Chromium in non-headless or properly simulated environments for mitigation.
- The use of robust interactions ensures that the bot does not forcefully interact with incomplete or heavily obfuscated dynamic DOM elements before they are visibly settled.
