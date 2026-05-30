import os
import sys
from unittest.mock import MagicMock

# Mock pyautogui completely since it needs a real X11 Display
sys.modules['pyautogui'] = MagicMock()
