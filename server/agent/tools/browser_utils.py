import logging
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger("AutoOS.browser_utils")

async def robust_click(page: Page, selector: str, timeout: int = 5000):
    try:
        element = await page.wait_for_selector(selector, state="visible", timeout=timeout)
        if element:
            await element.click()
            return True
    except PlaywrightTimeoutError:
        logger.warning(f"Timeout waiting to click selector: {selector}")
    except Exception as e:
        logger.error(f"Error clicking selector {selector}: {e}")
    return False

async def robust_fill(page: Page, selector: str, text: str, timeout: int = 5000):
    try:
        element = await page.wait_for_selector(selector, state="visible", timeout=timeout)
        if element:
            await element.fill(text)
            return True
    except PlaywrightTimeoutError:
        logger.warning(f"Timeout waiting to fill selector: {selector}")
    except Exception as e:
        logger.error(f"Error filling selector {selector}: {e}")
    return False

async def verify_text(page: Page, text: str, timeout: int = 5000) -> bool:
    try:
        element = await page.wait_for_selector(f"text={text}", state="visible", timeout=timeout)
        return bool(element)
    except PlaywrightTimeoutError:
        return False
    except Exception as e:
        logger.error(f"Error verifying text {text}: {e}")
        return False
