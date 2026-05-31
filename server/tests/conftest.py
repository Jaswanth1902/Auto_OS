import pytest
import subprocess
import os

@pytest.fixture(scope="session", autouse=True)
def cleanup_zombie_browsers():
    yield
    # Forcefully terminate any orphaned Chrome instances spawned during tests
    if os.name == "nt":
        subprocess.run("taskkill /f /im chrome.exe /fi \"STATUS eq RUNNING\"", shell=True, capture_output=True)
    else:
        subprocess.run("pkill -f chrome", shell=True, capture_output=True)
