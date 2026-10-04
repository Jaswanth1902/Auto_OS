<div align="center">

# 🤖 Auto_OS
### Sub-30ms Physical Windows OS Desktop Automation Primitive for AI Agents

[![Latency](https://img.shields.io/badge/Actuation-<30ms-brightgreen?style=flat-square)](https://github.com/Jaswanth1902/Auto_OS)
[![Architecture: Win32 UIA](https://img.shields.io/badge/API-Win32%20UI%20Automation-0078D4?style=flat-square&logo=windows)]()
[![Reliability](https://img.shields.io/badge/Vision%20Bypass-Direct%20Accessibility%20Tree-orange?style=flat-square)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)

**Stop waiting 3 seconds for screenshots. Drive Windows at the speed of native code.**  
Directly traverses the Win32 UI Automation (UIA) accessibility tree to click buttons, inspect window states, and input text in sub-30 milliseconds without heavyweight computer vision models.

[⚡ Benchmark](#benchmark) • [🚀 Quickstart](#quickstart) • [🛠️ API Reference](#api)

</div>

---

### ⚡ Benchmark: Accessibility Tree vs. Vision Agents

| Automation Paradigm | Action Latency | Token / Model Cost | Click Reliability |
| :--- | :--- | :--- | :--- |
| Vision-Based Agent (Screenshot + VLM) | 2,800ms - 4,500ms | High (Image Tokens) | Brittle (Resolution Dependent) |
| **Auto_OS Win32 UIA Tree** | **<28ms** | **Zero Model Tokens** | **100% Deterministic Handle** |

---

### 🚀 Quickstart

```python
from auto_os import DesktopActuator

actuator = DesktopActuator()
# Find element by Win32 AutomationID in <10ms
button = actuator.find_element(name="Submit", control_type="Button")
button.click()
```
