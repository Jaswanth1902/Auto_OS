import logging
import logging.handlers
import os

LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

class ColoredFormatter(logging.Formatter):
    COLORS = {
        'WARNING': '\033[93m',
        'INFO': '\033[92m',
        'DEBUG': '\033[94m',
        'CRITICAL': '\033[91m',
        'ERROR': '\033[91m'
    }
    RESET = '\033[0m'

    def format(self, record):
        log_fmt = f"%(asctime)s - {self.COLORS.get(record.levelname, self.RESET)}%(levelname)s{self.RESET} - %(name)s - %(message)s"
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def setup_logger(name: str, log_file: str, level=logging.INFO):
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # File Handler
    file_path = os.path.join(LOGS_DIR, log_file)
    file_handler = logging.handlers.RotatingFileHandler(
        file_path, maxBytes=10*1024*1024, backupCount=5
    )
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
    file_handler.setFormatter(file_formatter)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter())

    if not logger.handlers:
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

api_logger = setup_logger("AutoOS.API", "api.log")
agent_logger = setup_logger("AutoOS.Agent", "agent.log")
db_logger = setup_logger("AutoOS.DB", "database.log")
