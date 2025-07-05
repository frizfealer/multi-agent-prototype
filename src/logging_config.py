"""
Centralized logging configuration for the multi-agent system.
"""
import logging
import logging.handlers
import os
from datetime import datetime
from pathlib import Path


def setup_logging(
    log_level: str = "INFO",
    log_dir: str = "logs",
    log_to_console: bool = True,
    log_to_file: bool = False,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5,
    log_format: str = None,
) -> logging.Logger:
    """
    Set up logging configuration for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_dir: Directory to store log files
        log_to_console: Whether to log to console
        log_to_file: Whether to log to file
        max_bytes: Maximum size of log file before rotation
        backup_count: Number of backup files to keep
        log_format: Custom log format string
        
    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    if log_to_file:
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
    
    # Set up log format
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"
    
    # Create formatter
    formatter = logging.Formatter(log_format)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Console handler
    if log_to_console:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, log_level.upper()))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)
    
    # File handler with rotation
    if log_to_file:
        # Create a unique log file name with timestamp
        timestamp = datetime.now().strftime("%Y%m%d")
        log_file = log_path / f"multi_agent_{timestamp}.log"
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for a specific module.
    
    Args:
        name: Name of the module/component
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


# Initialize logging on module import with environment-based configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "false").lower() == "true"
LOG_TO_CONSOLE = os.getenv("LOG_TO_CONSOLE", "true").lower() == "true"
LOG_DIR = os.getenv("LOG_DIR", "logs")

# Set up default logging
setup_logging(
    log_level=LOG_LEVEL,
    log_dir=LOG_DIR,
    log_to_console=LOG_TO_CONSOLE,
    log_to_file=LOG_TO_FILE
)