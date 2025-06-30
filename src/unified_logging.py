"""
Unified structured logging configuration with Sentry integration
Replaces both logging_config.py and performance_config.py
"""
import logging
import logging.config
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from functools import wraps
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from pythonjsonlogger import jsonlogger

# Module-specific log levels (preserved from original)
MODULE_LOG_LEVELS = {
    # Critical path modules - reduce verbosity
    'src.unified_market_data': logging.WARNING,
    'src.unified_database': logging.WARNING,
    'src.unified_cache': logging.WARNING,
    
    # Engine and core modules - keep INFO for important events
    'src.unified_engine': logging.INFO,
    'src.unified_risk_manager': logging.INFO,
    
    # Strategy modules
    'src.strategies.st0ckg_strategy': logging.INFO,
    'src.strategies.st0cka_strategy': logging.INFO,
    
    # Service modules
    'src.services.market_analysis_service': logging.INFO,
    'src.services.position_service': logging.INFO,
    'src.services.trading_service': logging.INFO,
    
    # Supporting modules
    'src.battle_lines_manager': logging.INFO,
    'src.st0ckg_signals': logging.INFO,
    'src.options_selector': logging.INFO,
    'src.trend_filter_native': logging.INFO,
    'src.error_reporter': logging.INFO,
    
    # Third-party modules (only errors)
    'src.alpaca_broker': logging.INFO,
    'httpx': logging.ERROR,
    'httpcore': logging.ERROR,
}

class StructuredFormatter(jsonlogger.JsonFormatter):
    """Custom JSON formatter that includes standard fields"""
    
    def add_fields(self, log_record, record, message_dict):
        super().add_fields(log_record, record, message_dict)
        
        # Add standard fields
        log_record['timestamp'] = datetime.utcnow().isoformat()
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        
        # Add context if available
        if hasattr(record, 'bot_id'):
            log_record['bot_id'] = record.bot_id
        if hasattr(record, 'correlation_id'):
            log_record['correlation_id'] = record.correlation_id
        
        # Add error details if exception
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)

class BotContextFilter(logging.Filter):
    """Filter that adds bot context to log records"""
    
    def __init__(self, bot_id: Optional[str] = None):
        super().__init__()
        self.bot_id = bot_id
    
    def filter(self, record):
        if self.bot_id and not hasattr(record, 'bot_id'):
            record.bot_id = self.bot_id
        return True

def init_sentry(dsn: Optional[str] = None, environment: str = "production"):
    """Initialize Sentry error tracking"""
    if not dsn:
        dsn = os.getenv('SENTRY_DSN')
    
    if dsn:
        sentry_logging = LoggingIntegration(
            level=logging.INFO,        # Capture info and above as breadcrumbs
            event_level=logging.ERROR  # Send errors as events
        )
        
        sentry_sdk.init(
            dsn=dsn,
            integrations=[sentry_logging],
            environment=environment,
            traces_sample_rate=0.1,  # 10% of transactions for performance monitoring
            attach_stacktrace=True,
            send_default_pii=False
        )

def configure_logging(
    bot_id: Optional[str] = None,
    log_level: int = logging.INFO,
    log_to_file: bool = True,
    use_json: bool = True,
    sentry_dsn: Optional[str] = None
) -> logging.Logger:
    """
    Configure unified structured logging
    
    Args:
        bot_id: Bot identifier for context
        log_level: Default log level
        log_to_file: Whether to log to file
        use_json: Use JSON formatting (recommended)
        sentry_dsn: Sentry DSN for error tracking
    
    Returns:
        Configured root logger
    """
    # Initialize Sentry if DSN provided
    if sentry_dsn or os.getenv('SENTRY_DSN'):
        init_sentry(sentry_dsn)
    
    # Create logs directory
    if log_to_file:
        os.makedirs('logs', exist_ok=True)
    
    # Build logging configuration
    config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': StructuredFormatter,
                'format': '%(timestamp)s %(level)s %(name)s %(message)s'
            },
            'standard': {
                'format': '%(asctime)s - [%(name)s] - %(levelname)s - %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            }
        },
        'filters': {
            'bot_context': {
                '()': BotContextFilter,
                'bot_id': bot_id
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'level': log_level,
                'formatter': 'json' if use_json else 'standard',
                'filters': ['bot_context']
            }
        },
        'root': {
            'level': logging.DEBUG,
            'handlers': ['console']
        }
    }
    
    # Add file handler if requested
    if log_to_file:
        if bot_id:
            log_file = f'logs/{bot_id}_{os.getpid()}.log'
        else:
            log_file = f'logs/st0ck_{datetime.now().strftime("%Y%m%d")}.log'
        
        config['handlers']['file'] = {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': log_file,
            'maxBytes': 10485760,  # 10MB
            'backupCount': 3,
            'level': logging.DEBUG,
            'formatter': 'json' if use_json else 'standard',
            'filters': ['bot_context']
        }
        config['root']['handlers'].append('file')
    
    # Apply configuration
    logging.config.dictConfig(config)
    
    # Apply module-specific log levels
    for module_name, level in MODULE_LOG_LEVELS.items():
        logging.getLogger(module_name).setLevel(level)
    
    # Suppress noisy third-party loggers
    for logger_name in ['urllib3', 'alpaca', 'websocket', 'asyncio']:
        logging.getLogger(logger_name).setLevel(logging.WARNING)
    
    return logging.getLogger()

def get_logger(name: str, bot_id: Optional[str] = None) -> logging.Logger:
    """
    Get a logger with bot context
    
    Args:
        name: Logger name (usually __name__)
        bot_id: Optional bot identifier
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Add bot context filter if bot_id provided
    if bot_id:
        logger.addFilter(BotContextFilter(bot_id))
    
    return logger

class LogContext:
    """Context manager for adding fields to log records"""
    
    def __init__(self, logger: logging.Logger, **kwargs):
        self.logger = logger
        self.context = kwargs
        self.old_factory = None
    
    def __enter__(self):
        self.old_factory = logging.getLogRecordFactory()
        
        def record_factory(*args, **factory_kwargs):
            record = self.old_factory(*args, **factory_kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        logging.setLogRecordFactory(self.old_factory)

def log_performance(func):
    """Decorator to log function performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = logging.getLogger(func.__module__)
        start_time = datetime.now()
        
        try:
            result = func(*args, **kwargs)
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.debug(
                f"Function {func.__name__} completed",
                extra={
                    'function': func.__name__,
                    'duration_seconds': duration,
                    'status': 'success'
                }
            )
            return result
            
        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            
            logger.error(
                f"Function {func.__name__} failed",
                extra={
                    'function': func.__name__,
                    'duration_seconds': duration,
                    'status': 'error',
                    'error_type': type(e).__name__
                },
                exc_info=True
            )
            raise
    
    return wrapper

# Convenience function for critical errors
def log_critical_error(logger: logging.Logger, bot_id: str, error: Exception, context: Dict[str, Any]):
    """Log critical errors with full context"""
    logger.error(
        f"[{bot_id}] Critical error: {str(error)}",
        extra={
            'bot_id': bot_id,
            'error_type': type(error).__name__,
            'context': context
        },
        exc_info=True
    )
    
    # Also send to Sentry with context
    with sentry_sdk.push_scope() as scope:
        scope.set_tag("bot_id", bot_id)
        scope.set_context("error_context", context)
        sentry_sdk.capture_exception(error)