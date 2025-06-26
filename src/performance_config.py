"""
Performance configuration for AAGRAY trading system
Optimized for speed and efficiency
"""
import logging
import os

# Logging configuration for optimal performance
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'compact': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            'datefmt': '%H:%M:%S'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'compact',
            'level': 'INFO'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': f'logs/aagray_{os.getpid()}.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 3,
            'formatter': 'compact',
            'level': 'DEBUG'
        }
    },
    'loggers': {
        # Critical path - minimize logging
        'src.unified_market_data': {'level': 'WARNING'},
        'src.aagray_signals': {'level': 'WARNING'},
        'src.market_microstructure': {'level': 'WARNING'},
        'src.aagray_options_selector': {'level': 'WARNING'},
        
        # Important operations - keep INFO
        'src.aagray_engine': {'level': 'INFO'},
        'bots.st0ckg.strategy': {'level': 'INFO'},
        
        # Third-party - suppress noise
        'alpaca': {'level': 'WARNING'},
        'urllib3': {'level': 'WARNING'},
        'asyncio': {'level': 'WARNING'}
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console', 'file']
    }
}

# Performance settings
PERFORMANCE_SETTINGS = {
    # Cache TTLs (seconds)
    'quote_cache_ttl': 5,
    'option_chain_cache_ttl': 60,
    'microstructure_cache_ttl': 30,
    'vwap_cache_ttl': 60,
    
    # Batch sizes
    'max_concurrent_api_calls': 5,
    'option_chain_batch_size': 50,
    
    # Timeouts (milliseconds)
    'api_timeout': 5000,
    'order_timeout': 2000,
    
    # Performance thresholds
    'slow_operation_threshold': 100,  # Log operations slower than 100ms
    'memory_warning_threshold': 500 * 1024 * 1024,  # 500MB
}

def configure_logging(bot_id: str = 'aagray'):
    """Apply optimized logging configuration"""
    import logging.config
    import copy
    # Deep copy the config to avoid modifying the original
    config = copy.deepcopy(LOGGING_CONFIG)
    config['handlers']['file']['filename'] = f'logs/{bot_id}_{os.getpid()}.log'
    logging.config.dictConfig(config)
    
def get_performance_setting(key: str, default=None):
    """Get performance setting with fallback"""
    return PERFORMANCE_SETTINGS.get(key, default)