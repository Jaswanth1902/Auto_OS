from typing import Literal, Optional

# Maps task keywords/patterns to a fast-tracked category.
FAST_TRACK_RULES = {
    # If a task starts with these, it's definitively a browser task.
    "browser_prefixes": ["search web", "go to", "open website", "browse"],
    "browser_keywords": [
        "youtube",
        "google",
        "gmail",
        "website",
        "online",
        "download from",
    ],
    # If a task starts with these, it's definitively an OS task.
    "os_prefixes": ["open calculator", "launch app", "open settings"],
    "os_keywords": ["notepad", "paint", "word", "excel", "calculator", "file explorer"],
}


def get_fast_track_category(task: str) -> Optional[Literal["browser", "os"]]:
    """
    Checks the input task against heuristic rules. Returns a category if a match is found.
    """
    task_lower = task.strip().lower()

    for prefix in FAST_TRACK_RULES["browser_prefixes"]:
        if task_lower.startswith(prefix):
            return "browser"

    for keyword in FAST_TRACK_RULES["browser_keywords"]:
        if keyword in task_lower:
            return "browser"

    for prefix in FAST_TRACK_RULES["os_prefixes"]:
        if task_lower.startswith(prefix):
            return "os"

    for keyword in FAST_TRACK_RULES["os_keywords"]:
        if keyword in task_lower:
            return "os"

    return None
