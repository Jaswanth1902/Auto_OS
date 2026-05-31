import logging
import os
import platform
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("AutoOS.browser")


@dataclass
class BrowserTaskResult:
    success: bool
    task: str
    final_result: str = ""
    error: str | None = None
    history: Any | None = None

    def as_text(self) -> str:
        if self.success:
            return self.final_result or "Browser task completed."
        return f"Browser task failed: {self.error or 'Unknown error'}"


class BrowserAutomationRunner:
    """Runs browser automation tasks with the browser-use open-source agent."""

    def __init__(
        self,
        *,
        headless: bool | None = None,
        llm_model: str | None = None,
        page_extraction_model: str | None = None,
        use_cloud: bool | None = None,
        max_actions_per_step: int | None = None,
        max_failures: int | None = None,
    ) -> None:
        self.headless = (
            _env_bool("BROWSER_HEADLESS", default=False)
            if headless is None
            else headless
        )
        self.llm_model = llm_model or os.getenv("LLM_MODEL", "gemini-1.5-flash")
        self.page_extraction_model = page_extraction_model or os.getenv(
            "BROWSER_PAGE_EXTRACTION_MODEL",
            "gemini-1.5-flash",
        )
        self.use_cloud = (
            _env_bool("BROWSER_USE_CLOUD", default=False)
            if use_cloud is None
            else use_cloud
        )
        self.max_actions_per_step = max_actions_per_step or int(
            os.getenv("BROWSER_MAX_ACTIONS_PER_STEP", "3")
        )
        self.max_failures = max_failures or int(os.getenv("BROWSER_MAX_FAILURES", "2"))

    def _create_llm(self):
        try:
            from browser_use import ChatBrowserUse, ChatGoogle
        except ImportError as exc:
            raise RuntimeError(
                "browser-use is not installed. Run `uv sync` in the server folder."
            ) from exc

        browser_use_key = os.getenv("BROWSER_USE_API_KEY")
        if browser_use_key and os.getenv("BROWSER_LLM_PROVIDER", "").lower() in {
            "",
            "browser-use",
            "browser_use",
        }:
            return ChatBrowserUse(
                model=os.getenv("BROWSER_USE_MODEL", "bu-latest"),
                api_key=browser_use_key,
            )

        google_api_key = os.getenv("GOOGLE_API_KEY") or _first_csv_value(
            os.getenv("LLM_API_KEYS")
        )
        if not google_api_key:
            raise RuntimeError(
                "Set BROWSER_USE_API_KEY for ChatBrowserUse or GOOGLE_API_KEY for Gemini browser automation."
            )

        os.environ["GOOGLE_API_KEY"] = google_api_key
        return ChatGoogle(model=self.llm_model, api_key=google_api_key)

    def _create_page_extraction_llm(self):
        if not self.page_extraction_model:
            return None

        google_api_key = os.getenv("GOOGLE_API_KEY") or _first_csv_value(
            os.getenv("LLM_API_KEYS")
        )
        if not google_api_key:
            return None

        from browser_use import ChatGoogle

        return ChatGoogle(model=self.page_extraction_model, api_key=google_api_key)

    def _create_browser(self):
        try:
            from browser_use import Browser
        except ImportError as exc:
            raise RuntimeError(
                "browser-use is not installed. Run `uv sync` in the server folder."
            ) from exc

        if self.use_cloud:
            return Browser(use_cloud=True, headless=self.headless)

        executable_path = (
            os.getenv("BROWSER_EXECUTABLE_PATH") or _find_chromium_executable()
        )
        if executable_path:
            logger.info("Using browser executable at %s", executable_path)
            return Browser(
                headless=self.headless,
                executable_path=executable_path,
                keep_alive=_env_bool("BROWSER_KEEP_ALIVE", default=True),
            )

        logger.info(
            "No system Chrome/Chromium found; browser-use will use its default browser."
        )
        return Browser(
            headless=self.headless,
            keep_alive=_env_bool("BROWSER_KEEP_ALIVE", default=True),
        )

    async def run_task(
        self,
        task: str,
        *,
        sensitive_data: dict[str, str] | None = None,
        max_steps: int | None = None,
    ) -> BrowserTaskResult:
        if not task.strip():
            return BrowserTaskResult(
                success=False, task=task, error="No browser task provided"
            )

        try:
            from browser_use import Agent, Tools
        except ImportError as exc:
            raise RuntimeError(
                "browser-use is not installed. Run `uv sync` in the server folder."
            ) from exc

        try:
            enhanced_task = _inject_sensitive_data_instructions(task, sensitive_data)
            llm = self._create_llm()
            page_extraction_llm = self._create_page_extraction_llm()
            browser = self._create_browser()

            agent = Agent(
                task=enhanced_task,
                llm=llm,
                browser=browser,
                tools=Tools(),
                sensitive_data=sensitive_data,
                use_vision=_vision_setting(),
                page_extraction_llm=page_extraction_llm,
                flash_mode=_env_bool("BROWSER_FLASH_MODE", default=True),
                max_actions_per_step=self.max_actions_per_step,
                max_failures=self.max_failures,
                max_history_items=_optional_int("BROWSER_MAX_HISTORY_ITEMS"),
            )

            logger.info("Starting browser task: %s", task[:120])
            history = await agent.run(
                max_steps=max_steps or int(os.getenv("BROWSER_MAX_STEPS", "100"))
            )
            final_result = _extract_final_result(history)
            return BrowserTaskResult(
                success=True,
                task=task,
                final_result=final_result,
                history=history,
            )
        except Exception as exc:
            logger.error("Browser automation failed", exc_info=True)
            return BrowserTaskResult(success=False, task=task, error=str(exc))


async def run_browser_task(
    task: str,
    *,
    headless: bool | None = None,
    input_values: dict[str, str] | None = None,
    max_steps: int | None = None,
) -> str:
    runner = BrowserAutomationRunner(headless=headless)
    result = await runner.run_task(
        task, sensitive_data=input_values, max_steps=max_steps
    )
    return result.as_text()


def _extract_final_result(history: Any) -> str:
    if hasattr(history, "final_result"):
        value = history.final_result()
        if value:
            return str(value)

    if hasattr(history, "all_results"):
        results = history.all_results()
        if results:
            last = results[-1]
            extracted = getattr(last, "extracted_content", None)
            if extracted:
                return str(extracted)

    return str(history) if history is not None else ""


def _inject_sensitive_data_instructions(
    task: str, sensitive_data: dict[str, str] | None
) -> str:
    if not sensitive_data:
        return task

    lines = [
        task,
        "",
        "Use the provided sensitive values only where the task asks for the corresponding field:",
    ]
    for key in sensitive_data:
        lines.append(f"- {key}: <secret>{key}</secret>")
    return "\n".join(lines)


def _find_chromium_executable() -> str | None:
    system_name = platform.system()
    if system_name == "Darwin":
        candidates = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
        ]
        for candidate in candidates:
            if Path(candidate).exists():
                return candidate
        return None

    if system_name == "Windows":
        local_app = os.environ.get("LOCALAPPDATA", "")
        program_files = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        program_files_x86 = os.environ.get(
            "PROGRAMFILES(X86)", r"C:\Program Files (x86)"
        )
        candidates = [
            Path(program_files) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(program_files_x86)
            / "Google"
            / "Chrome"
            / "Application"
            / "chrome.exe",
            Path(local_app) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return None

    for name in (
        "google-chrome",
        "google-chrome-stable",
        "chromium",
        "chromium-browser",
    ):
        executable = shutil.which(name)
        if executable:
            return executable
    return None


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _vision_setting() -> bool | str:
    raw = os.getenv("BROWSER_USE_VISION", "auto").strip().lower()
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return "auto"


def _optional_int(name: str) -> int | None:
    raw = os.getenv(name)
    if not raw:
        return None
    return int(raw)


def _first_csv_value(value: str | None) -> str | None:
    if not value:
        return None
    first = value.split(",", 1)[0].strip()
    return first or None
