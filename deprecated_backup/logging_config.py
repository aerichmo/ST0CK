"""
Centralized logging configuration for performance optimization
"""
import logging
import os
from datetime import datetime

# Define log levels for different modules
MODULE_LOG_LEVELS = {
    # Critical path modules - reduce verbosity
    'src.unified_market_data': logging.WARNING,
    'src.market_microstructure': logging.WARNING,
    'src.apex_signals': logging.WARNING,
    'src.apex_options_selector': logging.WARNING,
    'src.database': logging.WARNING,
    
    # Engine modules - keep INFO for important events
    'src.apex_engine': logging.INFO,
    'src.base_fast_engine': logging.INFO,
    'src.st0ckg_engine': logging.INFO,
    
    # Strategy modules
    'bots.st0ckg.strategy': logging.INFO,
    'bots.base.strategy': logging.INFO,
    
    # Less critical modules
    'src.alert_handlers': logging.INFO,
    'src.monitoring': logging.INFO,
    'src.risk_manager': logging.INFO,
    'src.exit_manager': logging.INFO,
    
    # Debug modules (only errors)
    'src.alpaca_broker': logging.ERROR,
}

def configure_logging(log_level=logging.INFO, log_to_file=True):
    """
    Configure logging with performance optimizations
    
    Args:
        log_level: Default log level for modules not in MODULE_LOG_LEVELS
        log_to_file: Whether to log to file
    """
    # Create logs directory if it doesn't exist
    if log_to_file:
        os.makedirs('logs', exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all, filter at handler level
    
    # Clear existing handlers
    root_logger.handlers = []
    
    # Console handler with default level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        '%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S %Z'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if enabled)
    if log_to_file:
        file_handler = logging.FileHandler(
            f'logs/st0ckg_{datetime.now().strftime("%Y%m%d")}.log'
        )
        file_handler.setLevel(logging.DEBUG)  # Log everything to file
        file_formatter = logging.Formatter(
            '%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S %Z'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Apply module-specific log levels
    for module_name, level in MODULE_LOG_LEVELS.items():
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(level)
        
    # Suppress noisy third-party loggers
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('alpaca').setLevel(logging.WARNING)
    logging.getLogger('websocket').setLevel(logging.WARNING)
    
    return root_logger

def get_logger(name):
    """
    Get a logger with appropriate configuration
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Check if module has specific level configured
    for module_prefix, level in MODULE_LOG_LEVELS.items():
        if name.startswith(module_prefix):
            logger.setLevel(level)
            break
            
    return logger