import subprocess
import platform
import logging

logger = logging.getLogger("AutoOS.cleanup")

def cleanup_zombie_processes():
    if platform.system() == "Windows":
        logger.info("Cleaning up zombie browser processes on Windows...")
        try:
            subprocess.run('taskkill /f /im chrome.exe /fi "STATUS eq RUNNING"', shell=True, capture_output=True)
            subprocess.run('taskkill /f /im chromedriver.exe /fi "STATUS eq RUNNING"', shell=True, capture_output=True)
        except Exception as e:
            logger.error(f"Error cleaning up zombie processes: {e}")
    else:
        logger.info("Zombie process cleanup is implemented for Windows only.")
